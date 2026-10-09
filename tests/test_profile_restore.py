from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flydigi_control import protocol
from flydigi_control.persistence_check import snapshot
from flydigi_control.profile_restore import restore, preview, read_backup
from flydigi_control.macro_bank import replace_macro
from test_macro_edit import MacroController
from test_macro_bank import sample
from test_hardware_settings import status


class Controller(MacroController):
    def exchange(self, packet, timeout=10):
        if packet == protocol.request(0x03): return status()
        return super().exchange(packet, timeout)

    def mapping_status(self):
        return {'third_party_control': True}


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.device = Controller()
        self.source = snapshot(self.device)
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)

    def changed(self):
        self.device.mapping[800] = 1
        self.device.lighting = self.device.lighting[:6]+b'\x32'+self.device.lighting[7:]
        self.device.macros = replace_macro(self.device.macros, sample())
        return snapshot(self.device)

    def test_restore_all_profile_blocks_and_preserve_global_settings(self):
        previous = self.changed()
        self.source['hardware_settings']['sleep']['value'] = 60
        self.source['native_mapping_permission'] = False
        self.assertEqual(preview(self.source, previous)['mapping'], 1)
        actual, backup = restore(self.device, self.source, previous, self.temp.name)
        saved = json.loads(backup.read_text())
        self.assertEqual(saved['mapping'], previous['mapping'])
        self.assertEqual(saved['macros'], previous['macros'])
        self.assertEqual(actual['lighting'], self.source['lighting'])
        self.assertEqual(actual['macros'], self.source['macros'])
        self.assertEqual(self.device.mapping[800], 0)
        self.assertEqual(actual['hardware_settings'], previous['hardware_settings'])
        self.assertTrue(actual['native_mapping_permission'])
        self.assertEqual([kind for kind,_ in self.device.writes], ['lighting','mapping','macros','save'])
        self.assertEqual(saved, previous)
        undone, _ = restore(self.device, read_backup(backup), actual, self.temp.name)
        self.assertEqual(undone['lighting'], previous['lighting'])
        self.assertEqual(undone['macros'], previous['macros'])
        self.assertEqual(self.device.mapping[800], 1)

    def test_old_saved_version_is_replaced_and_lost_ack_is_not_retried(self):
        self.source['versions'][1] = 123
        mapping = bytearray.fromhex(self.source['mapping']); mapping[225:227] = (123).to_bytes(2,'little')
        self.source['mapping'] = mapping.hex()
        previous = self.changed(); self.device.save_timeout = True
        with patch('flydigi_control.persistence.secrets.randbelow',return_value=456):
            actual,_ = restore(self.device,self.source,previous,self.temp.name)
        self.assertEqual(actual['versions'][1],456)
        self.assertEqual(sum(kind=='save' for kind,_ in self.device.writes),1)

    def test_incompatible_sources_never_write(self):
        current = snapshot(self.device)
        for field,value in (('profile',2),('mapping','00'),('macros',None),('lighting','ffff'),('kind','unknown')):
            source=deepcopy(self.source);source[field]=value
            with self.assertRaises(ValueError):restore(self.device,source,current,self.temp.name)
        source=deepcopy(self.source);source['identity']['firmware']='new'
        with self.assertRaises(ValueError):restore(self.device,source,current,self.temp.name)
        self.assertEqual(self.device.writes,[])

    def test_stale_read_and_failed_backup_never_write(self):
        previous = snapshot(self.device); self.changed()
        with self.assertRaisesRegex(RuntimeError,'changed'):restore(self.device,self.source,previous,self.temp.name)
        previous = snapshot(self.device)
        with patch('flydigi_control.persistence._backup',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):restore(self.device,self.source,previous,self.temp.name)
        self.assertEqual(self.device.writes,[])

    def test_failed_lighting_readback_prevents_save(self):
        previous = self.changed()
        with patch.object(self.device,'write_lighting'):
            with self.assertRaisesRegex(RuntimeError,'Lighting verification'):
                restore(self.device,self.source,previous,self.temp.name)
        self.assertFalse(any(kind=='save' for kind,_ in self.device.writes))

    def test_backup_file_bounds_and_type(self):
        path=Path(self.temp.name)/'profile.json';path.write_text(json.dumps(self.source))
        self.assertEqual(read_backup(path),self.source)
        link=path.with_name('link.json');link.symlink_to(path)
        with self.assertRaises(OSError):read_backup(link)
        for text in ('[]','{}',' '*65537):
            path.write_text(text)
            with self.assertRaises(ValueError):read_backup(path)
