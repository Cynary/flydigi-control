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

    def test_flow_preserves_hardware_geometry(self):
        b=make_blob(self.original,1,[],20,4)
        self.assertEqual(len(b),320)
        self.assertEqual(b[4:9],bytes([9,4,20,10,1]))
        self.assertEqual(b[20:29],bytes([0,128,128])*3)
        with self.assertRaises(ValueError):
            make_blob(self.original + bytes(30),1,[],20,4)

    def test_default_animation_matches_vendor_serialized_profiles(self):
        # Independently produced by the actual SDK parser/serializer from
        # default_mapping_130.dat; harness is in experimental/lighting-reference.
        import hashlib
        expected = [
            '585237652a864c5b84ffc03d45ba36d73a85b136a2277b8b782ce206cd0b06cc',
            '031e4cb9590ebb971c98f06cb0f5d05eb5fca7215d189170da49f57e3792f438',
            '031e4cb9590ebb971c98f06cb0f5d05eb5fca7215d189170da49f57e3792f438',
            '031e4cb9590ebb971c98f06cb0f5d05eb5fca7215d189170da49f57e3792f438',
        ]
        for profile, digest in enumerate(expected):
            with self.subTest(profile=profile):
                blob = make_blob(self.original, 7, [], 20, 4, factory_profile=profile)
                self.assertEqual(blob[:9], bytes.fromhex('000300000904140a07'))
                self.assertEqual(hashlib.sha256(blob[20:]).hexdigest(), digest)
                self.assertEqual(blob[9:20], self.original[9:20])

    def test_default_adjustments_preserve_animation_and_unknown_fields(self):
        original = bytearray(self.original)
        original[9:20] = bytes(range(11))
        normal = make_blob(original, 7, [], 20, 4, factory_profile=0)
        adjusted = make_blob(original, 7, [], 83, 12, factory_profile=0)
        self.assertEqual(adjusted[5:7], bytes([12,83]))
        self.assertEqual(adjusted[9:], normal[9:])
        self.assertEqual(adjusted[9:20], original[9:20])

    def test_default_rejects_missing_profile_or_different_geometry(self):
        for profile in (None, -1, 4, True, 1.0):
            with self.assertRaises(ValueError):
                make_blob(self.original, 7, [], 20, 4, factory_profile=profile)
        with self.assertRaises(ValueError):
            make_blob(self.original + bytes(30), 7, [], 20, 4, factory_profile=0)
