from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flydigi_control.factory_profile import source_for
from flydigi_control.persistence_check import snapshot
from flydigi_control.profile_restore import restore, read_backup
from flydigi_control.macro_bank import replace_macro, decode_bank
from test_profile_restore import Controller
from test_macro_bank import sample


def ready_controller():
    device = Controller()
    device.mapping[2] = 77  # Header seen on firmware 7.1.5.0, not a byte count.
    return device


class FactoryProfileTests(unittest.TestCase):
    def test_physical_macro_extent_preserved_by_factory_restore(self):
        device=ready_controller();device.macros+=bytes(range(40))
        current=snapshot(device);source=source_for(current)
        self.assertEqual(bytes.fromhex(source['macros'])[1620:],bytes(range(40)))
        with tempfile.TemporaryDirectory() as folder:
            actual,_=restore(device,source,current,folder)
        self.assertEqual(len(bytes.fromhex(actual['macros'])),1660)

    def test_each_profile_matches_vendor_values_without_version_reset(self):
        digests = json.loads((Path(__file__).parent/'fixtures/factory-profile-digests.json').read_text())
        for profile in range(4):
            device = ready_controller();device.profile = profile
            device.mapping[225:227] = device.versions[profile].to_bytes(2,'little')
            current = snapshot(device); source = source_for(current)
            with self.subTest(profile=profile):
                mapping = bytearray.fromhex(source['mapping'])
                self.assertEqual(mapping[225:227],device.mapping[225:227])
                mapping[225:227] = bytes(2)
                self.assertEqual(hashlib.sha256(mapping).hexdigest(),digests[profile]['mapping'])
                for field in ('lighting','macros'):
                    self.assertEqual(hashlib.sha256(bytes.fromhex(source[field])).hexdigest(),digests[profile][field])
                self.assertEqual(current,snapshot(device))
                self.assertEqual(device.writes,[])

    def test_reset_clears_macros_and_backup_can_undo_all_three_sections(self):
        device = ready_controller()
        device.macros = replace_macro(device.macros,sample())
        current = snapshot(device); source = source_for(current)
        with tempfile.TemporaryDirectory() as folder:
            actual,backup = restore(device,source,current,folder)
            self.assertEqual(decode_bank(bytes.fromhex(actual['macros'])).records,())
            self.assertEqual(actual['lighting'],source['lighting'])
            for field in ('profile','identity','hardware_settings','native_mapping_permission'):
                self.assertEqual(actual[field],current[field])
            self.assertEqual(read_backup(backup),current)
            undone,_ = restore(device,read_backup(backup),actual,folder)
            for field in ('lighting','macros'):
                self.assertEqual(undone[field],current[field])
            self.assertEqual(device.mapping[:225],bytes.fromhex(current['mapping'])[:225])
            self.assertEqual(device.mapping[227:],bytes.fromhex(current['mapping'])[227:])

    def test_unknown_firmware_model_profile_or_geometry_is_rejected(self):
        current = snapshot(ready_controller())
        for field,value in (('device_id',128),('firmware','7.1.6.0')):
            data = deepcopy(current);data['identity'][field] = value
            with self.assertRaises(ValueError):source_for(data)
        for field,value in (('profile',True),('profile',4),('mapping','02034d'),
                            ('lighting','0003'),('macros',None)):
            data = deepcopy(current);data[field] = value
            with self.assertRaises(ValueError):source_for(data)
        data=deepcopy(current);data['mapping']+='ff'*840
        with self.assertRaises(ValueError):source_for(data)

    def test_stale_snapshot_or_failed_backup_prevents_factory_write(self):
        device=ready_controller(); current=snapshot(device); source=source_for(current)
        with tempfile.TemporaryDirectory() as folder:
            device.mapping[800]^=1
            with self.assertRaisesRegex(RuntimeError,'changed'):
                restore(device,source,current,folder)
            device.mapping[800]^=1
            with patch('flydigi_control.profile_restore._backup',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):restore(device,source,current,folder)
        self.assertEqual(device.writes,[])
