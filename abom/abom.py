from bitarray import bitarray
from io import BufferedIOBase, BytesIO
from struct import pack, unpack
from functools import reduce
from math import ceil
from arithmetic_compressor import AECompressor
from arithmetic_compressor.models import StaticModel
from abom.bloom_filter import CompressedBloomFilter


class AbomError(Exception):
    ''' Internal exception within ABOM operation. '''
    pass


class ABOM():
    ''' An Automated Bill of Materials. '''

    # Number of elements in Bloom filter
    m = 2**16
    # Number of hash functions in Bloom filter
    k = 16
    # The highest tolerated false positive rate
    f = 0.0001

    # Contant for max unsigned 32-bit integer (2^32-1)
    MAX_INT = 4294967295

    def __init__(self):
        self.bfs = [CompressedBloomFilter(self.m, self.k, prehashed=True)]

    def insert(self, x: bytes|str) -> 'ABOM':
        ''' Inserts `x` into the ABOM using syntax `abom.insert(x)`. '''
        for bf in self.bfs:
            if ~bf < self.f:
                bf += x
                return self
        self.bfs.append(CompressedBloomFilter(self.m, self.k, prehashed=True))
        self.bfs[-1] += x
        return self
    
    def union(self, abom: 'ABOM') -> 'ABOM':
        ''' Updates the ABOM to be the union of itself and `abom` using syntax `abom.union(abom2)`. '''
        if self.m != abom.m or self.k != abom.k:
            raise AbomError('ABOMs must have same `m` and `k`.')
        for bf in abom.bfs:
            for i in range(len(self.bfs)):
                u = self.bfs[i] | bf
                if ~u < self.f:
                    self.bfs[i] = u
                    break
            self.bfs.append(bf)
        return self
    
    def contains(self, x: bytes|str) -> bool:
        ''' Returns True if `x` is in the ABOM using syntax `abom.contains(x)`. '''
        for bf in self.bfs:
            if bf.contains(x):
                return True
        return False
    
    def dump(self, f: BufferedIOBase|str) -> None:
        ''' Serialize ABOM to buffer `f`. '''
        # Binary Format (little endian):
        # - Header:
        #   - Magic Word: `ABOM`
        #   - Protocol Version: `1` (unsigned char)
        #   - Number of Bloom filters: `n` (unsigned short)
        #   - Arithmetic Model p(1) of concatenated Bloom filters as '[0,1] x (2^32-1)' (unsigned int)
        #   - Bit length of Compressed Bloom Filters b=Blob: `l` (unsigned long)
        # - Compressed Bloom Filters Blob:
        #   - Arithmetically-compressed concatenated Bloom filters (bf_0 bf_1 ... bf_n)
        if isinstance(f, str):
            with open(f, 'wb') as f:
                return self.dump(f)
        bf_blob = reduce(lambda x, y: x + y.A.tolist(), self.bfs, [])
        p_1 = reduce(lambda x, y: x + y.A.count(), self.bfs, 0) / (len(self.bfs) * self.m)
        model = StaticModel({ 1: p_1, 0: 1-p_1 })
        coder = AECompressor(model)
        cbfs = bitarray(coder.compress(bf_blob), endian='little')
        header = pack('<ccccBHIL', b'A', b'B', b'O', b'M', 1, len(self.bfs), int(p_1 * self.MAX_INT), len(cbfs))
        f.write(header)
        f.write(cbfs.tobytes())
        f.flush()

    @classmethod
    def load(cls, f: BufferedIOBase|str) -> 'ABOM':
        ''' Deserialize ABOM from buffer or filename `f`. '''
        if isinstance(f, str):
            with open(f, 'rb') as f:
                return cls.load(f)
        magic_word = f.read(4)
        if magic_word != b'ABOM':
            raise AbomError('Invalid magic word.')
        protocol_version = f.read(1)
        if protocol_version != b'\x01':
            raise AbomError('Invalid protocol version.')
        n, p_1, l = unpack('<HIL', f.read(10))
        p_1 /= cls.MAX_INT
        cbfs = bitarray(endian='little')
        cbfs.frombytes(f.read(ceil(l/8)))
        if p_1 == 0:
            model = StaticModel({ 0: 1 })
        else:
            model = StaticModel({ 1: p_1, 0: 1-p_1 })
        coder = AECompressor(model)
        try:
            bf_blob = coder.decompress(cbfs[:l].tolist(), n*cls.m)
        except ValueError:
            print(cbfs)
        abom = ABOM()
        for i in range(0,len(bf_blob), cls.m):
            A = bitarray(bf_blob[i:i+cls.m], endian='little')
            bf = CompressedBloomFilter(cls.m, cls.k, A=A, prehashed=True)
            abom.bfs.append(bf)
        return abom

    def serialize(self) -> bytes:
        ''' Returns ABOM serialized as bytes. '''
        with BytesIO() as f:
            self.dump(f)
            return f.getvalue()
    
    def __iadd__(self, x: bytes|str) -> 'ABOM':
        ''' Inserts `x` into the ABOM using syntax `abom += x`. '''
        return self.insert(x)
    
    def __ior__(self, abom: 'ABOM') -> 'ABOM':
        ''' Updates the ABOM to be the union of itself and `abom` using syntax `abom |= abom2`. '''
        return self.union(abom)
    
    def __contains__(self, x: bytes|str) -> bool:
        ''' Returns True if `x` is in the ABOM using syntax `x in abom`. '''
        return self.contains(x)