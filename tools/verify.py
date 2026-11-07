#!/usr/bin/env python3
"""Independently check the image, packed representation and installer assets."""
import hashlib
import json
import mmap
import struct
import subprocess
from prepare import ROOT, BUILD, digest, verify_sources
lock = verify_sources()
raw = (BUILD / 'download0.dat').read_bytes()
packed = (BUILD / 'image.sparse').read_bytes()
assert packed[:8] == b'Y2JBIMG1'
size = struct.unpack_from('<Q', packed, 8)[0]
assert size == len(raw)
reconstructed = bytearray(size)
pos, end = 16, 0
while pos < len(packed):
    off, length = struct.unpack_from('<QI', packed, pos); pos += 12
    assert end <= off <= size and 0 < length <= 65536 and length <= size - off and length <= len(packed) - pos
    reconstructed[off:off+length] = packed[pos:pos+length]
    pos += length; end = off + length
assert reconstructed == raw
assert hashlib.sha256(raw).hexdigest() == lock['y2jb']['image_sha256']
listing = subprocess.check_output(['fls', '-f', 'ufs2', '-r', '-p', str(BUILD/'download0.dat')], text=True)
files = {}
for line in listing.splitlines():
    if line.startswith('r/r '):
        entry, path = line.split('\t', 1)
        inode = entry.split()[1].rstrip(':')
        content = subprocess.check_output(['icat', '-f', 'ufs2', str(BUILD/'download0.dat'), inode])
        files[path] = hashlib.sha256(content).hexdigest()
        if path.endswith('/splash.html'):
            assert 'r--r--r--' in subprocess.check_output(['istat','-f','ufs2',str(BUILD/'download0.dat'),inode],text=True)
assert any(p.endswith('/main.js') for p in files)
assert any(p.endswith('/ps5-unified-autoloader.elf') for p in files)
elf = ROOT/'dist/Y2JB-installer.elf'
with elf.open('rb') as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as b:
    assert b[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<H', b, 18)[0] == 62
    for asset in ['youtube.pkg', 'image.sparse']:
        assert b.find((BUILD/asset).read_bytes()) >= 0
    for forbidden in [b'sceSystemServiceRequestReboot', b'sceRegMgrSetInt', b'sceRegMgrSetBin', b'np-fake-signin']:
        assert forbidden not in b, forbidden
manifest = ROOT/'dist/build-manifest.json'
m = json.loads(manifest.read_text())
m['runtime_files'] = files
m['build_inputs'] = {
    p.relative_to(ROOT).as_posix(): digest(p)
    for p in sorted([ROOT/'build.sh', ROOT/'dependencies.json'] +
                    list((ROOT/'src').glob('*')) + list((ROOT/'tools').glob('*.py')))
    if p.is_file()
}
m['installer'] = {'size': elf.stat().st_size, 'sha256': digest(elf)}
manifest.write_text(json.dumps(m, indent=2) + '\n')
(ROOT/'dist/SHA256SUMS.txt').write_text(digest(elf) + '  Y2JB-installer.elf\n')
print('Verified official UFS2 image, sparse round trip, embedded assets and x86-64 ELF')
print('Installer SHA-256:', digest(elf))
