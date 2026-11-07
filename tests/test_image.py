"""Exercise the production decoder against malformed inputs and real file I/O."""
import ctypes
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
class ImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix='y2jb-image-test-')
        library = Path(cls.workspace.name)/'image.so'
        subprocess.run(['cc','-Wall','-Wextra','-Werror','-shared','-fPIC','-Isrc','src/image.c','-o',str(library)],cwd=ROOT,check=True)
        cls.lib = ctypes.CDLL(str(library))
        cls.lib.image_validate.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint64]
        cls.lib.image_write.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint64]
    @classmethod
    def tearDownClass(cls):
        cls.workspace.cleanup()
    def valid(self, data, size):
        return self.lib.image_validate(data, len(data), size)
    def test_round_trip_with_holes(self):
        size=196608
        block=bytes(range(256))*256
        data=b'Y2JBIMG1'+struct.pack('<Q',size)+struct.pack('<QI',65536,len(block))+block
        with tempfile.TemporaryFile() as out:
            out.write(b'x'*(size+100))
            out.flush()
            self.assertEqual(self.lib.image_write(out.fileno(),data,len(data),size),0)
            out.seek(0)
            self.assertEqual(out.read(),b'\0'*65536+block+b'\0'*65536)
    def test_rejects_malformed_without_touching_file(self):
        header=b'Y2JBIMG1'+struct.pack('<Q',100)
        invalid=[b'',header[:15],b'badmagic'+header[8:],header+b'x',
                 header+struct.pack('<QI',0,0),header+struct.pack('<QI',99,2)+b'xx',
                 header+struct.pack('<QI',2**64-1,1)+b'x',header+struct.pack('<QI',0,65537)+b'x'*65537,
                 header+struct.pack('<QI',0,10)+b'x',
                 header+struct.pack('<QI',5,2)+b'xx'+struct.pack('<QI',6,1)+b'y']
        for data in invalid:
            with self.subTest(data=data[:32]), tempfile.TemporaryFile() as out:
                out.write(b'preserve existing data');out.flush()
                self.assertNotEqual(self.valid(data,100),0)
                self.assertNotEqual(self.lib.image_write(out.fileno(),data,len(data),100),0)
                out.seek(0);self.assertEqual(out.read(),b'preserve existing data')
    def test_size_mismatch(self):
        self.assertNotEqual(self.valid(b'Y2JBIMG1'+struct.pack('<Q',100),101),0)
    def test_write_error(self):
        data=b'Y2JBIMG1'+struct.pack('<Q',100)
        self.assertNotEqual(self.lib.image_write(-1,data,len(data),100),0)
if __name__=='__main__':
    unittest.main()
