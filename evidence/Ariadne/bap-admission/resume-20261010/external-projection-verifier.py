import hashlib
import json
import mmap
import struct
from pathlib import Path

ROOT = Path('/home/nzsn/Workspace/Electron_SRC/.analysis/dump_03958DA4FCA844A786262A1053')
OUT = Path('/home/nzsn/Repos/Ariadne/target/bap-admission-resume-20261010')
PIN = '9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab'

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1048576), b''):
            h.update(data)
    return h.hexdigest()

class Dump:
    def __init__(self, path):
        self.file = path.open('rb')
        self.data = mmap.mmap(self.file.fileno(), 0, access=mmap.ACCESS_READ)
        assert self.data[:4] == b'MDMP'
        count, offset = struct.unpack_from('<II', self.data, 8)
        self.streams = {}
        for i in range(count):
            kind, size, rva = struct.unpack_from('<III', self.data, offset + i * 12)
            assert kind not in self.streams and rva + size <= len(self.data)
            self.streams[kind] = (rva, size)
        rva, size = self.streams[9]
        count, payload = struct.unpack_from('<QQ', self.data, rva)
        assert size == 16 + count * 16
        self.ranges = []
        for i in range(count):
            start, length = struct.unpack_from('<QQ', self.data, rva + 16 + i * 16)
            assert payload + length <= len(self.data)
            self.ranges.append((start, length, payload))
            payload += length

    def read(self, va, size):
        result = bytearray()
        while size:
            candidates = [(a, n, p) for a, n, p in self.ranges if a <= va < a + n]
            assert candidates, 'missing original range'
            boundaries = [a + n for a, n, _ in candidates]
            boundaries.extend(a for a, _, _ in self.ranges if a > va)
            take = min(size, min(boundaries) - va)
            alternatives = [bytes(self.data[p + va - a:p + va - a + take])
                            for a, _, p in candidates]
            assert all(raw == alternatives[0] for raw in alternatives), 'conflicting capture bytes'
            result.extend(alternatives[0])
            va += take
            size -= take
        return bytes(result)

    def threads(self):
        rva, _ = self.streams[3]
        count, = struct.unpack_from('<I', self.data, rva)
        return {struct.unpack_from('<I', self.data, rva + 4 + i * 48)[0]:
                bytes(self.data[rva + 4 + i * 48:rva + 4 + (i + 1) * 48])
                for i in range(count)}

provenance = ROOT / 'ariadne/projection-provenance.json'
receipt = json.loads(provenance.read_text())
original = ROOT / 'original.dmp'
derivative = ROOT / 'ariadne/exception-thread-projection.dmp'
assert sha(original) == receipt['original_sha256'] == PIN
assert sha(derivative) == receipt['projection_sha256']
assert original.stat().st_size == receipt['original_bytes']
assert derivative.stat().st_size == receipt['projection_bytes']
old, new = Dump(original), Dump(derivative)
rows = []
assert set(new.streams) == set(receipt['published_streams'])
assert len(new.ranges) == len(receipt['memory_ranges'])
for actual, claimed in zip(new.ranges, receipt['memory_ranges']):
    va, length, offset = actual
    assert va == int(claimed['start'], 16) and length == claimed['size']
    assert offset == claimed['projection_offset']
    data = new.read(va, length)
    assert data == old.read(va, length)
    assert hashlib.sha256(data).hexdigest() == claimed['sha256']
    rows.append(dict(va=hex(va), bytes=length, sha256=claimed['sha256'], originalBytesEqual=True))
for kind in [4, 6, 7, 16]:
    a, n = old.streams[kind]
    b, m = new.streams[kind]
    assert n == m and old.data[a:a+n] == new.data[b:b+m]
old_threads, new_threads = old.threads(), new.threads()
assert set(new_threads) == {0x5c74} and len(old_threads) == receipt['original_threads']
o, d = old_threads[0x5c74], new_threads[0x5c74]
assert o[:36] == d[:36] and o[40:] == d[40:]
size, rva = struct.unpack_from('<II', o, 40)
assert old.data[rva:rva+size] == new.data[rva:rva+size]
stack_va, stack_size, stack_rva = struct.unpack_from('<QII', d, 24)
assert new.data[stack_rva:stack_rva+stack_size] == old.read(stack_va, stack_size)
e, _ = old.streams[6]
assert struct.unpack_from('<I', old.data, e)[0] == 0x5c74
size, rva = struct.unpack_from('<II', old.data, e + 160)
assert old.data[rva:rva+size] == new.data[rva:rva+size]
witnesses = {}
for name in ['pass1-triage.log', 'pass3-caller.log', 'pass5-consumer.log', 'dump-identity.json']:
    p = ROOT / name
    witnesses[name] = sha(p)
record = dict(schema='ariadne.bap-admission-external-projection-check/v1', passed=True,
              originalPath=str(original), originalSha256=PIN, derivativePath=str(derivative),
              derivativeSha256=sha(derivative), provenanceSha256=sha(provenance),
              publishedThread='0x5c74', threadContextEqual=True, exceptionContextEqual=True,
              metadataStreamsEqual=[4, 6, 7, 16], ranges=rows, witnessHashes=witnesses,
              verifierSha256=sha(Path(__file__)), scope='Independent binary parsing and byte equality; query/runtime qualification remains separate.')
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'external-projection-check.json').write_text(json.dumps(record, indent=2) + '\n')
print('External projection verified:', len(rows), 'ranges, copied contexts and metadata; exact original SHA-256 matches')
