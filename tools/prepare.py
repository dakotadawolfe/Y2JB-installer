#!/usr/bin/env python3
"""Verify vendored inputs and prepare the official image and YouTube package."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import ssl
import struct
import urllib.request
ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / '.build'
def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()
def verify_sources():
    lock = json.loads((ROOT / 'dependencies.json').read_text())
    for name, expected in lock['files'].items():
        if digest(ROOT / name) != expected:
            raise ValueError('Vendored input changed: ' + name)
    return lock
def fetch(part, path, legacy=False):
    if path.exists() and path.stat().st_size == part['size'] and digest(path) == part['sha256']:
        return
    url = part['url']
    # The SC endpoint has a legacy certificate chain. The pinned SHA-256 is
    # mandatory and authenticates the downloaded public file before it is used.
    if legacy and not url.startswith('https://sgst.prod.dl.playstation.net/'):
        raise ValueError('Unexpected legacy endpoint')
    context = ssl._create_unverified_context() if legacy else None
    tmp = path.with_suffix('.partial')
    with urllib.request.urlopen(url, context=context, timeout=120) as response, tmp.open('wb') as out:
        shutil.copyfileobj(response, out)
    if tmp.stat().st_size != part['size'] or digest(tmp) != part['sha256']:
        tmp.unlink()
        raise ValueError('YouTube package verification failed')
    tmp.replace(path)
def pack(source, target):
    with source.open('rb') as inp, target.open('wb') as out:
        out.write(b'Y2JBIMG1' + struct.pack('<Q', source.stat().st_size))
        offset = 0
        while block := inp.read(65536):
            if any(block):
                out.write(struct.pack('<QI', offset, len(block)))
                out.write(block)
            offset += len(block)
def main():
    lock = verify_sources()
    BUILD.mkdir(exist_ok=True)
    (ROOT / 'dist').mkdir(exist_ok=True)
    image = BUILD / 'download0.dat'
    with gzip.open(ROOT / 'assets/download0.dat.gz', 'rb') as src, image.open('wb') as out:
        shutil.copyfileobj(src, out)
    if image.stat().st_size != lock['y2jb']['image_size'] or digest(image) != lock['y2jb']['image_sha256']:
        raise ValueError('Official image verification failed')
    packed = BUILD / 'image.sparse'
    pack(image, packed)
    catalog = json.loads((ROOT / 'vendor/installer/pkgs/youtube.json').read_text())
    selected = next(b for b in catalog['builds'] if b['build'] == 'v01.000.030')
    parts = [('base', selected['base']), ('sc', selected['sc']['usa'])]
    for name, part in parts:
        fetch(part, BUILD / (name + '.pkg'), legacy=name == 'sc')
    package = BUILD / 'youtube.pkg'
    with package.open('wb') as out:
        for name, _ in parts:
            with (BUILD / (name + '.pkg')).open('rb') as inp:
                shutil.copyfileobj(inp, out)
    assets = {'package': package, 'image': packed}
    header = ['#pragma once', '#include <stdint.h>']
    asm = ['.section .rodata']
    for name, path in assets.items():
        header += [f'extern const unsigned char {name}_start[], {name}_end[];']
        asm += ['.balign 16', f'.global {name}_start, {name}_end', f'{name}_start:', '.incbin ' + json.dumps(str(path)), f'{name}_end:']
    header += [f'#define PACKAGE_SHA "{digest(package)}"', f'#define IMAGE_PACKED_SHA "{digest(packed)}"',
               f'#define IMAGE_FULL_SHA "{digest(image)}"', f'#define IMAGE_SIZE UINT64_C({image.stat().st_size})',
               '#define PACKAGE_DIGEST "' + selected['sc']['usa']['package_digest'] + '"']
    (BUILD / 'assets.h').write_text('\n'.join(header) + '\n')
    (BUILD / 'assets.S').write_text('\n'.join(asm) + '\n')
    manifest = {'installer_version': '2.0.0', 'firmware': '13.60', 'title_id': 'PPSA01650',
                'youtube_version': selected['build'], 'upstream': lock['y2jb'],
                'assets': {name: {'size': path.stat().st_size, 'sha256': digest(path)} for name, path in assets.items()},
                'console_tested': False, 'behavior': 'Install YouTube and official download0.dat, then exit.'}
    (ROOT / 'dist/build-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Verified official image, vendored dependencies and YouTube package')
if __name__ == '__main__':
    main()
