import tempfile
import unittest
from flydigi_control.button_mappings import BUTTONS, read_button, with_button
from flydigi_control.persistence import apply_mapping_edit
from test_persistence import Controller


def profile(minor=2):
    m=bytearray((i*17+3)%256 for i in range(840 if minor else 790))
    m[:3]=bytes([minor,3,79])
    for i in range(32):m[13+3*i:16+3*i]=bytes([255,0,0])
    return bytes(m)


class ButtonMappingTests(unittest.TestCase):
    def test_default_means_identity_not_disabled(self):
        for source in range(24):
            value=read_button(profile(),source)
            self.assertEqual((value.kind,value.target),('button',source))
        self.assertEqual(BUTTONS[18:24],('M1','M2','M3','M4','LM','RM'))

    def test_all_single_mappings_preserve_every_other_byte(self):
        for minor in (0,1,2):
            original=profile(minor)
            for source in range(24):
                for target in range(24):
                    with self.subTest(minor=minor,source=source,target=target):
                        result=with_button(original,source,kind='button',target=target)
                        offset=13+source*3
                        self.assertEqual(result[:offset],original[:offset])
                        self.assertEqual(result[offset+3:],original[offset+3:])
                        self.assertEqual(result[offset:offset+3],bytes([255 if source==target else target,0,0]))
                        self.assertEqual(read_button(result,source).target,target)

    def test_rapid_fire_and_normal_transition(self):
        original=profile()
        for source in range(24):
            for activation in (0,1,2):
                for frequency in (1,15,30):
                    target=(source+1)%24
                    result=with_button(original,source,kind='rapid_fire',target=target,activation=activation,frequency=frequency)
                    off=13+source*3
                    self.assertEqual(result[off:off+3],bytes([target,activation,frequency]))
                    value=read_button(result,source)
                    self.assertEqual((value.kind,value.target,value.activation,value.frequency),('rapid_fire',target,activation,frequency))
                    restored=with_button(result,source,kind='button',target=source)
                    self.assertEqual(restored,original)

    def test_macro_pc_and_unknown_records_are_not_rewritten(self):
        for raw,kind in [(b'\x20\x00\x00','macro'),(b'\xfe\x00\x00','keyboard_mouse'),
                (b'\x26\x00\x00','unknown'),(b'\xff\x00\xff','unknown'),
                (b'\x04\x03\x0f','unknown'),(b'\x04\x01\x1f','unknown'),(b'\x04\x01\x00','unknown')]:
            m=bytearray(profile());m[13:16]=raw
            self.assertEqual(read_button(m,0).kind,kind)
            with self.assertRaises(ValueError):with_button(m,0,kind='button',target=4)

    def test_equivalent_explicit_self_mapping_is_preserved(self):
        m=bytearray(profile());m[25:28]=bytes([4,0,0])
        self.assertEqual(with_button(m,4,kind='button',target=4),m)

    def test_fn_home_and_turbo_are_not_onboard_sources(self):
        for source in (24,25,26,27,28,31,True,-1):
            with self.assertRaises(ValueError):read_button(profile(),source)

    def test_bad_inputs_rejected(self):
        for values in [dict(kind='button',target=255),dict(kind='button',target=True),
                       dict(kind='button',target=4,frequency=1),dict(kind='button',target=4,activation=1),
                       dict(kind='rapid_fire',target=4,activation=1,frequency=0),
                       dict(kind='rapid_fire',target=4,activation=1,frequency=31),
                       dict(kind='rapid_fire',target=4,activation=True,frequency=15),dict(kind='macro',target=4)]:
            with self.assertRaises(ValueError):with_button(profile(),0,**values)
        for mapping in (b'', bytes(800), bytes([3,3])+bytes(838)):
            with self.assertRaises(ValueError):read_button(mapping,0)

    def test_save_preserves_lights_macros_and_other_controls(self):
        device=Controller()
        mapping=bytearray(profile());mapping[225:227]=(20).to_bytes(2,'little')
        device.mapping=mapping
        before=bytes(mapping);lights=device.lighting
        edit=lambda m:with_button(m,18,kind='button',target=4)
        with tempfile.TemporaryDirectory() as tmp:
            apply_mapping_edit(device,before,edit,tmp,expected_profile=1)
        expected=bytearray(edit(before));expected[225:227]=device.mapping[225:227]
        self.assertEqual(device.mapping,expected)
        self.assertEqual(device.lighting,lights)
        self.assertEqual([kind for kind,_ in device.writes],['mapping','save'])
