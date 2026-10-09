import json
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch
from flydigi_control.macro_bank import Action, Macro
from flydigi_control.vendor_macro import decode, read, encode, export_copy


def fixture():
    return bytes.fromhex(json.loads(Path(__file__).with_name('vendor_macro_file_vectors.json').read_text())[0]['hex'])


class VendorMacroTests(unittest.TestCase):
    def test_export_matches_independent_vendor_serializer(self):
        for value in json.loads(Path(__file__).with_name('vendor_macro_file_vectors.json').read_text()):
            if value['key'] > 23: continue  # Export a bound macro, not a vendor template.
            raw = bytes.fromhex(value['hex'])
            self.assertEqual(encode(decode(raw, value['key'])), raw)

    def test_export_default_fields_maximum_values_and_both_sticks(self):
        macros = (
            Macro(0, 0, 0, '', (Action(0, 0, 1), Action(0, 0, 0))),
            Macro(23, 3, 65535, 'é猫', (Action(0, 168, 3), Action(65535, 160, 3))),
            Macro(16, 2, 150, 'Many actions', tuple(Action(0, 4, 1-i%2) for i in range(256))),
        )
        for macro in macros:
            self.assertEqual(decode(encode(macro), macro.key, macro.name), macro)

    def test_export_is_private_new_file_without_changing_import(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'source.dat'; source.write_bytes(fixture())
            macro = read(source, 18)
            first, second = export_copy(Path(folder)/'exports', macro), export_copy(Path(folder)/'exports', macro)
            self.assertNotEqual(first, second)
            self.assertEqual(first.stat().st_mode & 0o777, 0o600)
            self.assertEqual(read(first, 18), macro)
            self.assertEqual(source.read_bytes(), fixture())
            self.assertFalse(list(first.parent.glob('.macro-*')))

    def test_export_invalid_macro_and_failed_write_leave_no_output(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'exports'
            with self.assertRaises(ValueError):export_copy(target, replace(decode(fixture(),18),actions=()))
            self.assertFalse(target.exists())
            with patch('flydigi_control.vendor_macro.os.fsync',side_effect=OSError('disk')):
                with self.assertRaises(OSError):export_copy(target, decode(fixture(),18))
            self.assertEqual(list(target.iterdir()), [])

    def test_actual_vendor_files_keep_actions_and_rebind_templates(self):
        for value in json.loads(Path(__file__).with_name('vendor_macro_file_vectors.json').read_text()):
            macro = decode(bytes.fromhex(value['hex']), 19)
            self.assertEqual((macro.key, macro.name, macro.mode, macro.interval_ms), (19, 'é猫', 1, 100))
            self.assertEqual(macro.actions, (Action(0,4,1),Action(50,4,0),Action(150,163,2),Action(200,160,2)))

    def test_missing_count_and_title_use_defaults(self):
        raw = fixture()[2:]
        raw = raw[:raw.index(bytes.fromhex('3205'))]
        self.assertEqual(decode(raw, 0).name, 'Imported macro')
        self.assertEqual(decode(raw, 0, 'Custom title').name, 'Custom title')

    def test_unknown_fields_count_and_malformed_wire_are_rejected(self):
        for raw in (fixture()+b'\x38\x01', fixture()+b'\x08\x80',
                    fixture()+b'\x32\x40x', fixture()+b'\x22\x02\x00\x00',
                    fixture().replace(b'\x10\x04',b'\x10\x05',1),
                    b'\x08'+b'\xff'*11, b'\x08'+b'\xff'*9+b'\x02', b' '*65537):
            with self.subTest(raw=raw[:10]):
                with self.assertRaises(ValueError): decode(raw, 16)

    def test_incomplete_actions_and_edit_only_hold_do_not_get_applied(self):
        raw = fixture().replace(bytes.fromhex('220408041801'), bytes.fromhex('220408041805'),1)
        with self.assertRaisesRegex(ValueError, 'Hold'): decode(raw, 16)
        raw = fixture().replace(bytes.fromhex('220408041032'), bytes.fromhex('220408031032'),1)
        with self.assertRaisesRegex(ValueError, 'release'): decode(raw, 16)
        with self.assertRaises(ValueError): decode(fixture(), 255)

    def test_file_read_does_not_modify_original_and_rejects_links(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'example.dat'; path.write_bytes(fixture())
            self.assertEqual(read(path, 18).key, 18)
            self.assertEqual(path.read_bytes(), fixture())
            link = Path(folder)/'link.dat'; link.symlink_to(path)
            with self.assertRaises(OSError): read(link, 18)
