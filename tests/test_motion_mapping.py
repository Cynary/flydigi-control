import tempfile
import unittest
from flydigi_control.motion_mapping import KEYS, read_motion, with_motion
from flydigi_control.persistence import apply_mapping_edit
from test_persistence import Controller
from test_button_mappings import profile as base_profile


def profile(minor=2):
    mapping=bytearray(base_profile(minor))
    # Recorded read-only 7.1.5.0 profile: off, LT toggle, deadzone 4,
    # asymmetric sensitivity 25/20, FPS, second key Up. Preserve unused values.
    mapping[137:145]=bytes.fromhex('000c000419140000')
    return bytes(mapping)


def values(mapping):
    result=read_motion(mapping)
    return {key:result[key] for key in ('target','key','activation','deadzone','sensitivity','second')}


class MotionMappingTests(unittest.TestCase):
    def change(self,mapping,**changes):
        params=values(mapping);params.update(changes)
        return with_motion(mapping,**params)

    def test_recorded_fields_and_unchanged_save_preserved(self):
        m=profile();current=read_motion(m)
        self.assertEqual(current['raw_sensitivity'],(25,20))
        self.assertEqual(current['key'],12)
        self.assertEqual(current['sensitivity'],25)
        self.assertEqual(current['deadzone'],4)
        self.assertEqual(self.change(m),m)
        self.assertEqual(read_motion(profile(0))['smoothness'],None)

    def test_each_mode_uses_vendor_racing_or_fps_without_clobbering_other_bytes(self):
        for minor in (0,1,2):
            for target,mode in ((1,1),(2,0)):
                m=profile(minor);result=self.change(m,target=target)
                expected=bytearray(m);expected[137]=target;expected[143]=mode
                self.assertEqual(result,expected)
                self.assertEqual(result[141:143],bytes([25,20]))

    def test_disable_preserves_previous_setup(self):
        m=self.change(profile(),target=1,activation=1,second=255,sensitivity=38,deadzone=15)
        result=self.change(m,target=0,sensitivity=70,deadzone=50)
        expected=bytearray(m);expected[137]=0
        self.assertEqual(result,expected)

    def test_both_axes_only_change_when_sensitivity_is_edited(self):
        m=self.change(profile(),target=2)
        result=self.change(m,deadzone=15)
        self.assertEqual(result[141:143],m[141:143])
        result=self.change(m,sensitivity=26)
        self.assertEqual(result[141:143],bytes([26,26]))
        self.assertEqual(result[:141],m[:141])
        self.assertEqual(result[143:],m[143:])

    def test_hold_buttons_and_toggle_preservation(self):
        m=self.change(profile(),target=2,activation=1,key=12,second=13)
        self.assertEqual(m[138],12);self.assertEqual(m[144],13)
        toggled=self.change(m,activation=0)
        self.assertEqual(toggled[144],13)
        with self.assertRaises(ValueError):self.change(toggled,second=255)
        for key,_ in KEYS:
            if key==255:continue
            result=self.change(profile(),target=2,activation=1,key=key,second=255)
            self.assertEqual(read_motion(result)['key'],key)

    def test_unknown_and_pc_mouse_modes_rejected(self):
        for offset,value in [(137,3),(137,7),(138,26),(139,2),(140,101),(141,101),(143,8),(144,26)]:
            m=bytearray(profile());m[offset]=value
            with self.assertRaises(ValueError):read_motion(m)
        for invalid in (bytes(840),b''):
            with self.assertRaises(ValueError):read_motion(invalid)

    def test_invalid_input_never_writes(self):
        for changes in [dict(target=3),dict(target=True),dict(deadzone=-1),dict(sensitivity=101),
                        dict(activation=True),dict(target=2,key=255),dict(target=2,activation=1,key=12,second=12)]:
            with self.assertRaises(ValueError):self.change(profile(),**changes)

    def test_save_preserves_other_fields_smoothing_and_lighting(self):
        device=Controller();device.mapping=bytearray(profile());device.mapping[225:227]=(20).to_bytes(2,'little')
        original=bytes(device.mapping);lights=device.lighting
        edit=lambda m:self.change(m,target=2,activation=1,second=255,deadzone=15)
        with tempfile.TemporaryDirectory() as tmp:
            apply_mapping_edit(device,original,edit,tmp,expected_profile=1)
        expected=bytearray(edit(original));expected[225:227]=device.mapping[225:227]
        self.assertEqual(device.mapping,expected)
        self.assertEqual(device.mapping[830:840],original[830:840])
        self.assertEqual(device.lighting,lights)
        self.assertEqual([k for k,_ in device.writes],['mapping','save'])
