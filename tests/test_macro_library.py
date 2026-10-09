from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from flydigi_control.macro_bank import Action, Macro
from flydigi_control import macro_library as library


def sample():
    return Macro(16, 1, 100, 'Double tap', (Action(0, 4, 1), Action(40, 4, 0),
                                        Action(60, 4, 1), Action(40, 4, 0)))


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / 'macros'

    def test_unicode_roundtrip_and_private_durable_copy(self):
        macro = replace(sample(), name='Jump ✨')
        filename = library.save_copy(self.folder, macro)
        self.assertEqual(library.load(self.folder, filename), macro)
        self.assertEqual((self.folder/filename).stat().st_mode & 0o777, 0o600)
        self.assertFalse(list(self.folder.glob('.macro-*')))
        second = library.save_copy(self.folder, macro)
        self.assertNotEqual(filename, second)
        self.assertEqual(len(library.entries(self.folder)[0]), 2)

    def test_files_are_portable_and_removal_does_not_touch_others(self):
        name = library.save_copy(self.folder, sample())
        copied = self.folder/'imported.json'; copied.write_bytes((self.folder/name).read_bytes())
        library.remove(self.folder, name)
        self.assertEqual(library.load(self.folder, copied.name), sample())

    def test_invalid_entries_reported_without_hiding_good_macros(self):
        name = library.save_copy(self.folder, sample())
        (self.folder/'bad.json').write_text('{bad')
        records, errors = library.entries(self.folder)
        self.assertEqual(records, [(name, sample())])
        self.assertEqual(len(errors), 1)
        self.assertIn('bad.json', errors[0])

    def test_rejects_unsupported_and_unbalanced_actions(self):
        data = json.loads(library.encode(sample()))
        for field, value in (('mode', 8), ('name', 'x'*21), ('key', True),
                             ('actions', [{'delay_ms':0, 'key':4, 'event':1}]),
                             ('actions', [{'delay_ms':0, 'key':4, 'event':5}])):
            altered = json.loads(json.dumps(data)); altered['macro'][field] = value
            with self.assertRaises(ValueError): library.decode(json.dumps(altered).encode())
        for raw in (b'[]', b'null', b'{}', b'\xff', b' '*65537):
            with self.assertRaises(ValueError): library.decode(raw)

    def test_no_path_escape_or_links(self):
        filename = library.save_copy(self.folder, sample())
        (self.folder/'link.json').symlink_to(self.folder/filename)
        for name in ('../outside.json', '/tmp/other.json', 'link.json', '.hidden.json'):
            with self.assertRaises(ValueError): library.load(self.folder, name)
            with self.assertRaises(ValueError): library.remove(self.folder, name)

    def test_empty_library_and_invalid_save_leave_no_file(self):
        self.assertEqual(library.entries(self.folder), ([], []))
        with self.assertRaises(ValueError):
            library.save_copy(self.folder, replace(sample(), actions=()))
        self.assertFalse(self.folder.exists())
