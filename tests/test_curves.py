import json
from pathlib import Path
import unittest
from flydigi_control.curves import Curve, preset, samples, with_curve


def mapping():
    data = bytearray(i % 251 for i in range(840))
    data[:3] = bytes([2,3,84])
    data[800] = data[812] = 1
    return bytes(data)


class CurveTests(unittest.TestCase):
    def test_samples_match_official_editor_reference_vectors(self):
        # Numeric outputs from Space Station 4.2.0.9's curve sampler. Includes
        # vertical segments, compensation, saturation and non-monotonic curves.
        vectors = json.loads(Path(__file__).with_name('curve_reference_vectors.json').read_text())
        for vector in vectors:
            expected = tuple(vector.pop('expected'))
            with self.subTest(vector=vector):
                self.assertEqual(samples(Curve(**vector)), expected)

    def test_response_edit_preserves_shape_other_stick_and_other_profile_fields(self):
        before = mapping()
        for side in (0, 1):
            after = with_curve(before, side, preset(1))
            base, extra = 109+7*side, 790+12*side
            allowed = set(range(base,base+6)) | set(range(extra,extra+10)) | {extra+11}
            changed = {i for i,(a,b) in enumerate(zip(before,after)) if a!=b}
            self.assertTrue(changed <= allowed)
            self.assertEqual(after[800],1)
            self.assertEqual(after[812],1)
            self.assertEqual(after[base:base+6],bytes([1,0,64,96,127,127]))
            self.assertEqual(tuple(after[extra+1:extra+10]),samples(preset(1)))

    def test_center_is_applied_to_editor_x_coordinates_using_sdk_scale(self):
        after=with_curve(mapping(),0,Curve(kind=3,center=10,edge=20,point1=(64,80)))
        self.assertEqual(list(after[109:115]), [3,10,70,80,127,127])
        self.assertEqual(after[801],20)

    def test_unknown_and_ambiguous_writes_rejected(self):
        for curve in (Curve(center=-1),Curve(edge=-1),Curve(center=70,edge=40),
                      Curve(point1=(100,40),point2=(60,80)),Curve(kind=9),Curve(center=True)):
            with self.assertRaises(ValueError):with_curve(mapping(),0,curve)
        with self.assertRaises(ValueError):with_curve(mapping(),True,Curve())
        keyboard = bytearray(mapping())
        keyboard[110] = 127
        with self.assertRaisesRegex(ValueError,'non-joystick'):
            with_curve(bytes(keyboard),0,Curve())

    def test_presets_reset_deadzones(self):
        for kind,y in enumerate((64,96,32)):
            self.assertEqual(preset(kind),Curve(kind,0,0,(64,y),(127,127)))
        for kind in (3,True,-1):
            with self.assertRaises(ValueError):preset(kind)

    def test_positive_fields_match_actual_vendor_serializer(self):
        cases=json.loads(Path(__file__).with_name('curve_serialization_vectors.json').read_text())
        for case in cases:
            center,edge=case['center'],case['edge']
            if center<0 or edge<0 or center+edge>100:continue
            result=with_curve(mapping(),0,Curve(center=center,edge=edge))
            self.assertEqual(result[109:115],bytes.fromhex(case['base_hex'])[:6])
            self.assertEqual(result[801],bytes.fromhex(case['extra_hex'])[11])
            self.assertEqual(case['read_center'],center)
            self.assertEqual(case['read_edge'],edge)

    def test_vendor_negative_roundtrip_is_ambiguous_and_remains_unsavable(self):
        cases=json.loads(Path(__file__).with_name('curve_serialization_vectors.json').read_text())
        example=next(case for case in cases if case['center']==-10 and case['edge']==-10)
        self.assertEqual(bytes.fromhex(example['base_hex'])[1:3],bytes([246,218]))
        self.assertEqual((example['read_center'],example['read_edge']),(-119,-119))
        for case in cases:
            if case['center']<0 or case['edge']<0:
                with self.assertRaises(ValueError):
                    with_curve(mapping(),0,Curve(center=case['center'],edge=case['edge']))
