import unittest
from flydigi_control.profile_controls import read_grip,with_grip,read_trigger,with_trigger


def profile():
    data=bytearray(i%251 for i in range(840))
    data[:3]=bytes([2,3,77])
    # Fields from the read-only 7.1.5.0 hardware snapshot.
    data[123:137]=bytes([0,0,0,0,255,255,255]*2)
    data[145:154]=bytes([0,0,60,255,50,0,80,255,50])
    data[154:183]=bytes([0]+[1,51,114,5,1,50,0,255,40,120,5,0,50,0]*2)
    return bytes(data)


class ProfileControlsTests(unittest.TestCase):
    def test_hardware_snapshot_decodes_with_vendor_units(self):
        self.assertEqual(read_grip(profile(),0),dict(master_enabled=True,enabled=True,strength=50,minimum=60,maximum=255))
        self.assertEqual(read_grip(profile(),1)['minimum'],80)
        self.assertEqual(read_trigger(profile(),0),dict(start=0,end=255,enabled=True,minimum=20,maximum=45,threshold=5,strength=50))

    def test_grip_edit_preserves_thresholds_and_other_motor(self):
        original=profile()
        after=with_grip(original,1,master_enabled=True,enabled=False,strength=30)
        self.assertEqual({i for i,(a,b) in enumerate(zip(original,after)) if a!=b},{150,153})
        self.assertEqual(read_grip(after,0),read_grip(original,0))
        self.assertFalse(read_grip(after,1)['enabled'])

    def test_trigger_travel_edit_sets_endpoint_fields_only(self):
        original=profile()
        values=read_trigger(original,1);values.update(start=20,end=230)
        after=with_trigger(original,1,**values)
        self.assertEqual(after[131:137],bytes([20,20,20,230,230,230]))
        self.assertEqual(after[:131],original[:131]);self.assertEqual(after[137:],original[137:])

    def test_trigger_amplitude_conversion_and_preserved_noneditable_fields(self):
        original=profile();values=read_trigger(original,0)
        values.update(minimum=21,maximum=60,strength=80,threshold=9,enabled=False)
        after=with_trigger(original,0,**values)
        self.assertEqual(after[156],53);self.assertEqual(after[157],153)
        self.assertEqual(after[158],9);self.assertEqual(after[160],80)
        self.assertEqual({i for i,(a,b) in enumerate(zip(original,after)) if a!=b},{154,156,157,158,160})
        self.assertFalse(read_trigger(after,1)['enabled'])  # One shared switch.

    def test_read_then_save_untouched_amplitudes_is_byte_exact(self):
        for level in range(1,256):
            original=bytearray(profile());original[156]=original[157]=level
            original=bytes(original)
            self.assertEqual(with_trigger(original,0,**read_trigger(original,0)),original)

    def test_invalid_ranges_flags_and_types_fail_without_normalizing(self):
        for change in (dict(start=255),dict(end=-1),dict(minimum=60,maximum=20),
                       dict(strength=101),dict(threshold=0),dict(enabled=1),dict(start=True)):
            values=read_trigger(profile(),0);values.update(change)
            with self.assertRaises(ValueError):with_trigger(profile(),0,**values)
        bad=bytearray(profile());bad[154]=9
        with self.assertRaises(ValueError):read_trigger(bytes(bad),0)
        with self.assertRaises(ValueError):with_grip(profile(),0,master_enabled=True,enabled=True,strength=0)
        with self.assertRaises(ValueError):read_grip(profile(),True)
