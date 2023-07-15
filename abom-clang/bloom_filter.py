from bitarray import bitarray
from bitarray.util import ba2int
from hashlib import sha3_256
from warnings import warn
from io import BufferedIOBase, BytesIO
from struct import pack
from arithmetic_compressor import AECompressor
from arithmetic_compressor.models import StaticModel


class CompressedBloomFilter():
    ''' A Compressed Bloom Filter according to M. Mitzenmacher, IEEE/ACM 2002. '''

    # Contant for max unsigned 32-bit integer (2^32-1)
    MAX_INT = 4294967295

    def __init__(self, m: int, k: int, A: bitarray|None = None, endian='little', prehashed: bool = False):
        ''' Creates a new compressed Bloom filter with `m` bits and `k` hash functions. '''
        if m == 0 or (m & (m-1) != 0):
            raise ValueError('`m` must be a non-zero power of 2.')
        # Number of elements in Bloom filter
        self.m = m
        # Number of bits needed to represent an index in A
        self.idx_bits = m.bit_length() - 1
        # Number of hash functions in Bloom filter
        self.k = k
        # Bloom filter bit array
        self.A = bitarray(m, endian=endian)
        if A is None:
            self.A.setall(0)
        else:
            self.A = A
        # Whether objects inserted to filter are already hashed
        self.prehashed = prehashed

    def __hash(self, x: bytes|str) -> list[int]:
        ''' Returns `k` indices into `A` of 0<i<m. `x` must be a SHA3-256 hash in bytes or hex string. '''
        # Convert x to bytes
        if isinstance(x, str):
            if self.prehashed:
                x = bytes.fromhex(x)
            else:
                x = x.encode()
        # Convert x to bitarray
        b = bitarray()
        if self.prehashed:
            b.frombytes(x)
            if len(b) > self.k * self.idx_bits:
                warn('Parameters do not utilize all bits in hash.')
        # Expand hash if needed
        while len(b) < self.k * self.idx_bits:
            x = sha3_256(x).digest()
            b.frombytes(x)
        # Convert to list of indices
        h = []
        for i in range(0, self.k*self.idx_bits, self.idx_bits):
            h.append(ba2int(b[i:i+self.idx_bits]))
        return h
        
    def insert(self, x: bytes|str) -> 'CompressedBloomFilter':
        ''' Inserts `x` into the Bloom filter using syntax `bf.insert(x)`. '''
        for i in self.__hash(x):
            self.A[i] = 1
        return self
    
    def union(self, bf: 'CompressedBloomFilter') -> 'CompressedBloomFilter':
        ''' Updates the bloom filter to be the union of itself and `bf` using syntax `bf.union(bf2)`. '''
        if self.m != bf.m or self.k != bf.k:
            raise ValueError('Bloom filters must have same `m` and `k`.')
        self.A |= bf.A
        return self
    
    def contains(self, x: bytes|str) -> bool:
        ''' Returns True if `x` is in the Bloom filter using syntax `bf.contains(x)`. '''
        try:
            h = self.__hash(x)
        except ValueError:
            return False
        for i in h:
            if not self.A[i]:
                return False
        return True
    
    def false_positive_rate(self) -> float:
        ''' Returns the estimated false positive rate of the Bloom filter for its current saturation. '''
        return (self.A.count() / self.m) ** self.k

    def serialize(self, compressed: bool = True) -> bytes:
        ''' Returns the Bloom filter as bytes, optionally compresseed. '''
        with BytesIO() as f:
            self.dump(f, compressed=compressed)
            return f.getvalue()
        
    def dump(self, f: BufferedIOBase, compressed: bool = True) -> None:
        ''' Serialize Bloom filter to buffer `f`, optionally compressed. '''
        if compressed:
            # Compressed Binary Format:
            # - Number of elements in Bloom filter: `m` (unsigned int)
            # - Number of hash functions in Bloom filter `k` (unsigned char)
            # - Arithmetic Model p(1) of concatenated Bloom filters as '[0,1] x (2^32-1)' (unsigned int)
            # - Arithmetically-compressed Bloom filter
            p_1 = self.A.count() / self.m
            model = StaticModel({ 1: p_1, 0: 1-p_1 })
            coder = AECompressor(model)
            cbf = bitarray(coder.compress(self.A), endian=self.A.endian).tobytes()
            endian = '<' if self.A.endian == 'little' else '>'
            f.write(pack(f'{endian}IHI', self.m, self.k, int(p_1*self.MAX_INT)))
            f.write(cbf)
        else:
            self.A.tofile(f)
        f.flush()

    def clone(self) -> 'CompressedBloomFilter':
        ''' Returns a copy of the Bloom filter. '''
        return CompressedBloomFilter(self.m, self.k, self.A.copy(), self.A.endian(), self.prehashed)
    
    def __iadd__(self, x: bytes|str) -> 'CompressedBloomFilter':
        ''' Inserts `x` into the Bloom filter using syntax `bf += x`. '''
        return self.insert(x)
    
    def __ior__(self, bf: 'CompressedBloomFilter') -> 'CompressedBloomFilter':
        ''' Updates the Bloom filter to be the union of itself and `bf` using syntax `bf |= bf2`. '''
        return self.union(bf)
    
    def __contains__(self, x: bytes|str) -> bool:
        ''' Returns True if `x` is in the Bloom filteru using syntax `x in bf`. '''
        return self.contains(x)
    
    def __or__(self, bf: 'CompressedBloomFilter') -> 'CompressedBloomFilter':
        ''' Returns the union of the Bloom filter and `bf` using syntax `bf | bf2`. In-place union is preferred. '''
        return self.clone().union(bf)
    
    def __add__(self, x: bytes|str) -> 'CompressedBloomFilter':
        ''' Returns a copy of the Bloom filter with `x` inserted using syntax `bf + x`. In-place insertion is preferred. '''
        return self.clone().insert(x)
    
    def __invert__(self) -> 'CompressedBloomFilter':
        ''' Returns the false positive rate of the Bloom filter at its current saturation using the syntax `~bf`. '''
        return self.false_positive_rate()
    
    def __eq__(self, bf: 'CompressedBloomFilter') -> bool:
        ''' Returns True if the Bloom filter is equal to `bf` using syntax `bf == bf2`. '''
        return self.m == bf.m and self.k == bf.k and self.A == bf.A