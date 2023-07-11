from bitarray import bitarray
from warnings import warn
from io import BufferedIOBase, BytesIO
from struct import pack
from functools import reduce
from arithmetic_compressor import AECompressor
from arithmetic_compressor.models import StaticModel
from bloom_filter import CompressedBloomFilter


class ABOM():
    ''' An Automated Bill of Materials. '''

    # Number of elements in Bloom filter
    m = 2**16
    # Number of hash functions in Bloom filter
    k = 16
    # The highest tolerated false positive rate
    f = 0.0001

    def __init__(self):
        self.bfs = []

    def insert(self, x: bytes|str) -> 'ABOM':
        ''' Inserts `x` into the ABOM using syntax `abom.insert(x)`. '''
        for bf in self.bfs:
            if ~bf < self.f:
                bf.insert(x)
                return self
        self.bfs.append(CompressedBloomFilter(self.m, self.k, prehashed=True))
        self.bfs[-1].insert(x)
        return self
    
    def union(self, abom: 'ABOM') -> 'ABOM':
        ''' Updates the ABOM to be the union of itself and `abom` using syntax `abom.union(abom2)`. '''
        if self.m != abom.m or self.k != abom.k:
            raise ValueError('ABOMs must have same `m` and `k`.')
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
    
    def dump(self, f: BufferedIOBase) -> None:
        ''' Serialize ABOM to buffer `f`. '''
        # Binary Format (little endian):
        # - Header:
        #   - Magic Word: `ABOM`
        #   - Protocol Version: `1` (unsigned char)
        #   - Byte length of Bloom filter blob: `n` (long unsigned int)
        # - Compressed Bloom Filters Blob:
        #   - Arithmetic Model p(1) of concatenated Bloom filters (double)
        #   - Arithmetically-compressed concatenated Bloom filters (bf_0 bf_1 ... bf_n)
        header = pack('<ccccBL', b'A', b'B', b'O', b'M', 1, len(self.bfs))
        f.write(header)
        bf_blob = reduce(lambda x, y: x + y.serialize(compressed=False), self.bfs, b'')
        p_1 = reduce(lambda x, y: x + y.A.count(), self.bfs, 0) / (len(self.bfs) * self.m)
        model = StaticModel({ 1: p_1, 0: 1-p_1 })
        coder = AECompressor(model)
        cbfs = bitarray(coder.compress(bf_blob), endian='little').tobytes()
        warn('Should this be a double or float?')
        f.write(pack('<d', p_1))
        f.write(cbfs)
        f.flush()

    def serialize(self) -> bytes:
        ''' Returns ABOM serialized as bytes. '''
        with BytesIO() as f:
            self.dump(f)
            return f.getvalue()
    
    def __iadd__(self, x: bytes|str) -> 'ABOM':
        ''' Inserts `x` into the ABOM using syntax `abom += x`. '''
        return self.insert(x)
    
    def __contains__(self, x: bytes|str) -> bool:
        ''' Returns True if `x` is in the ABOM using syntax `x in abom`. '''
        return self.contains(x)