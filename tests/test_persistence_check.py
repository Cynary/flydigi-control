from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from flydigi_control import protocol
from flydigi_control.persistence_check import snapshot, compare, main
from test_hardware_settings import status
from test_persistence import Controller


class ReadOnlyController(Controller):
    def exchange(self, packet):
        if packet != protocol.request(0x03):
            raise AssertionError('Unexpected configuration command')
        return status()

    def mapping_status(self):
        return {'third_party_control': True, 'owner': 'Steam', 'raw_data': True}


class PersistenceCheckTests(unittest.TestCase):
    def setUp(self):
        self.device = ReadOnlyController()

    def test_complete_snapshot_and_no_writes(self):
        data = snapshot(self.device)
        self.assertEqual(data['profile'], 1)
        self.assertEqual(bytes.fromhex(data['macros']), self.device.macros)
        self.assertTrue(data['hardware_settings']['turbo']['value'])
        self.assertTrue(data['native_mapping_permission'])
        self.assertEqual(self.device.writes, [])
        self.assertEqual(compare(data, snapshot(self.device)), [])

    def test_ignores_battery_and_current_ownership(self):
        before = snapshot(self.device)
        info = self.device.info()
        with patch.object(self.device, 'info', return_value=replace(info, battery='20%')), \
             patch.object(self.device, 'mapping_status', return_value={'third_party_control': True, 'owner': ''}):
            self.assertEqual(compare(before, snapshot(self.device)), [])

    def test_detects_unsaved_leds_and_other_settings(self):
        before = snapshot(self.device)
        self.device.lighting = bytes([1]) + self.device.lighting[1:]
        self.device.mapping[800] = 1
        self.device.macros = self.device.macros[:-1] + bytes([0])
        differences = compare(before, snapshot(self.device))
        self.assertEqual({d['field'] for d in differences}, {'mapping', 'lighting', 'macros'})
        self.assertEqual(next(d for d in differences if d['field'] == 'lighting')['first_offsets'], [0])
        self.assertEqual(self.device.writes, [])

    def test_identity_and_profile_changes_are_not_a_pass(self):
        before = snapshot(self.device)
        after = deepcopy(before)
        after['identity']['firmware'] = '7.1.6.0'
        after['profile'] = 2
        self.assertEqual({d['field'] for d in compare(before, after)}, {'identity', 'profile'})

    def test_rejects_torn_reads_even_without_version_change(self):
        original = self.device.lighting
        with patch.object(self.device, 'read_lighting', side_effect=[(1, original), (1, original[:-1]+b'\x01')]):
            with self.assertRaisesRegex(RuntimeError, 'between reads'):
                snapshot(self.device)
        with patch.object(self.device, 'profile_state', side_effect=[(1, self.device.versions), (0, self.device.versions)]):
            with self.assertRaisesRegex(RuntimeError, 'profile changed'):
                snapshot(self.device)

    def test_incompatible_backup_rejected(self):
        actual = snapshot(self.device)
        for before in ({}, [], dict(actual, kind='hardware-settings')):
            with self.assertRaises(ValueError):
                compare(before, actual)

    def test_cli_private_snapshot_and_mismatch_exit(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch('flydigi_control.persistence_check.discover', return_value=[{'path': '/dev/hidraw1'}]), \
             patch('flydigi_control.persistence_check.ConfigurationDevice') as transport, \
             patch('builtins.print'):
            transport.return_value.__enter__.return_value = self.device
            self.assertEqual(main(['snapshot', directory]), 0)
            saved = next(Path(directory).glob('*.json'))
            self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(saved.read_text()), snapshot(self.device))
            self.assertEqual(main(['check', str(saved)]), 0)
            self.device.lighting = b'\x01' + self.device.lighting[1:]
            self.assertEqual(main(['check', str(saved)]), 1)
            with patch.object(self.device, 'read_lighting', side_effect=TimeoutError('No reply')):
                self.assertEqual(main(['check', str(saved)]), 2)
