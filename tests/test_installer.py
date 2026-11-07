"""Run production file operations with console APIs stubbed on the host."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MOCK = r'''
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/statvfs.h>
#include "install/install.h"
#include "install/installed.h"
static int started;
uint32_t kernel_get_fw_version(void){return 0x13600000;}
uid_t geteuid(void){return 0;}
int statvfs(const char *path,struct statvfs *out){(void)path;memset(out,0,sizeof *out);out->f_bavail=1048576;out->f_frsize=4096;return 0;}
int sceKernelSendNotificationRequest(int n,void *p,size_t size,int q){(void)n;(void)size;(void)q;puts((char*)p+45);return 0;}
void installed_read(const char *title,installed_info_t *info){
 (void)title;memset(info,0,sizeof *info);
 info->installed=started || strcmp(getenv("CASE"),"fresh");
 snprintf(info->package_digest,sizeof info->package_digest,"%s",!strcmp(getenv("CASE"),"mismatch")?"different":"expected-package");
}
int install_start(const char *t,const char *p,const char *h,int d){(void)t;(void)p;(void)h;(void)d;started=1;puts("PACKAGE_INSTALL_CALLED");return 0;}
void install_status(install_status_t *s){memset(s,0,sizeof *s);s->state=INSTALL_DONE;}
'''


class InstallerTests(unittest.TestCase):
    def run_case(self, mode, old=None):
        with tempfile.TemporaryDirectory(prefix='y2jb-install-test-') as name:
            root = Path(name)
            work, destination = root/'work', root/'download'
            work.mkdir()
            destination.mkdir()
            (root/'ps5').mkdir()
            (root/'ps5/kernel.h').write_text('#include <stdint.h>\nuint32_t kernel_get_fw_version(void);\n')
            package = b'package fixture'
            expected = b'\0'*65536 + b'official image fixture' + b'\0'*(65536-len(b'official image fixture'))
            packed = b'Y2JBIMG1'+struct.pack('<Q', len(expected))+struct.pack('<QI', 65536, 65536)+expected[65536:]
            if mode == 'corrupt':
                packed = b'INVALID!'+packed[8:]
            sha = lambda data: hashlib.sha256(data).hexdigest()
            header = '#include <stdint.h>\nextern const unsigned char package_start[],package_end[],image_start[],image_end[];\n'
            for key, value in [('PACKAGE_SHA', sha(package)), ('IMAGE_PACKED_SHA', sha(packed)),
                               ('IMAGE_FULL_SHA', sha(expected)), ('PACKAGE_DIGEST', 'expected-package')]:
                header += f'#define {key} "{value}"\n'
            header += f'#define IMAGE_SIZE UINT64_C({len(expected)})\n'
            (root/'assets.h').write_text(header)
            assembly = ['.section .rodata']
            for tag, data in [('package', package), ('image', packed)]:
                (root/tag).write_bytes(data)
                assembly += [f'.global {tag}_start,{tag}_end', f'{tag}_start:',
                             f'.incbin {json.dumps(str(root/tag))}', f'{tag}_end:']
            assembly += ['.section .note.GNU-stack,"",@progbits']
            (root/'assets.S').write_text('\n'.join(assembly))
            (root/'mock.c').write_text(MOCK)
            binary = root/'installer'
            subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation',
                            '-I'+str(root), '-Isrc', '-Ivendor/installer/src',
                            '-DWORK='+json.dumps(str(work)), '-DDIR='+json.dumps(str(destination)),
                            'src/main.c', 'src/image.c', 'vendor/installer/src/crypto/sha256.c',
                            str(root/'mock.c'), str(root/'assets.S'), '-o', str(binary)], cwd=ROOT, check=True)
            target = destination/'download0.dat'
            if old is not None:
                target.write_bytes(old)
            result = subprocess.run([str(binary)], env={**os.environ, 'CASE': mode}, capture_output=True, text=True)
            data = target.read_bytes() if target.exists() else None
            backups = [p.read_bytes() for p in work.glob('*.bak')]
            self.assertFalse(list(destination.glob('*.install-*')))
            return result, data, backups, expected

    def test_fresh_install(self):
        result, data, backups, expected = self.run_case('fresh')
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('PACKAGE_INSTALL_CALLED', result.stdout)
        self.assertEqual(data, expected)
        self.assertEqual(backups, [])

    def test_existing_image_backed_up_and_replaced(self):
        result, data, backups, expected = self.run_case('existing', b'previous image')
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertNotIn('PACKAGE_INSTALL_CALLED', result.stdout)
        self.assertEqual(data, expected)
        self.assertEqual(backups, [b'previous image'])

    def test_wrong_package_preserved(self):
        result, data, backups, _ = self.run_case('mismatch', b'previous image')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(data, b'previous image')
        self.assertEqual(backups, [])

    def test_corrupt_image_preserves_existing(self):
        result, data, backups, _ = self.run_case('corrupt', b'previous image')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(data, b'previous image')
        self.assertEqual(backups, [])


if __name__ == '__main__':
    unittest.main()
