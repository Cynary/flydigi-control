import unittest
from flydigi_control.lighting import make_blob, validate_blob

class LightingTests(unittest.TestCase):
    def setUp(self):
        self.original = bytes.fromhex('000300000901140a0700ffffffffffffffffffff') + bytes(300)

    def test_brightness_does_not_change_rgb_channels(self):
        b = make_blob(self.original, 5, [(255,0,255)], 30, 15)
        self.assertEqual(b[6],30)
        self.assertEqual(b[20:50],bytes([255,0,255])*10)
        self.assertEqual(b[50:],bytes(270))
        self.assertEqual(b[9:20],self.original[9:20])

    def test_breathing_inserts_dark_frames(self):
        b=make_blob(self.original,2,[(255,0,0),(0,0,255)],50,15)
        self.assertEqual(b[4],3)
        self.assertEqual(b[50:80],bytes(30))
        self.assertEqual(b[80:110],bytes([0,0,255])*10)

    def test_rejects_invalid_or_truncated_geometry(self):
        for b in (self.original[:-1],bytes(320),self.original[:20]):
            with self.assertRaises(ValueError):validate_blob(b)
        with self.assertRaises(ValueError):make_blob(self.original,2,[(1,2,3)]*6,50,15)
        with self.assertRaises(ValueError):make_blob(self.original,4,[(1,2,3)],50,15)
