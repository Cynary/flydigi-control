import json
import tempfile
import unittest
from unittest.mock import patch
from dataclasses import replace
from flydigi_control import protocol
from flydigi_control.macro_bank import decode_bank, replace_macro, remove_macro
from flydigi_control.persistence import apply_macro,remove_saved_macro
from flydigi_control.transport import ConfigurationDevice
from test_persistence import Controller
from test_macro_bank import empty_bank, sample


class MacroController(Controller):
    def write_macros(self, profile, original, updated):
        assert profile == self.profile and self.macros == original
        self.writes.append(('macros', updated))
        self.macros = updated


class MacroEditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.device = MacroController()
        self.mapping = bytes(self.device.mapping)
        self.macros = self.device.macros

    def save(self):
        return apply_macro(self.device,self.mapping,self.macros,sample(),self.tmp.name,expected_profile=1)

    def test_save_changes_only_requested_macro_then_commits_once(self):
        self.device.macros = replace_macro(empty_bank(),sample(19)); self.macros = self.device.macros
        lighting = self.device.lighting
        backup = self.save()
        saved = json.loads(backup.read_text())
        self.assertEqual(saved['mapping'],self.mapping.hex())
        self.assertEqual(saved['macros'],self.macros.hex())
        self.assertEqual(saved['requested_macros'],self.device.macros.hex())
        self.assertEqual([kind for kind,_ in self.device.writes],['macros','save'])
        self.assertEqual(self.device.lighting,lighting)
        before,after = decode_bank(self.macros),decode_bank(self.device.macros)
        self.assertEqual(before.records[0].raw,after.records[0].raw)
        self.assertEqual(after.records[1].macro,sample())
        self.assertEqual(self.device.mapping[:225],self.mapping[:225])
        self.assertEqual(self.device.mapping[227:],self.mapping[227:])

    def test_stale_macro_mapping_or_active_profile_never_writes(self):
        for field in ('macros','mapping','profile'):
            self.device = MacroController()
            if field=='macros':self.device.macros = replace_macro(empty_bank(),sample(19))
            elif field=='mapping':self.device.mapping[15] = 4
            else:self.device.profile = 2
            with self.assertRaises(RuntimeError):self.save()
            self.assertEqual(self.device.writes,[])

    def test_older_profile_is_not_written(self):
        self.device.mapping[0] = 1; self.mapping = bytes(self.device.mapping)
        with self.assertRaises(ValueError):self.save()
        self.assertEqual(self.device.writes,[])

    def test_backup_failure_prevents_macro_write(self):
        with patch('flydigi_control.persistence._backup',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.save()
        self.assertEqual(self.device.writes,[])

    def test_partial_write_timeout_does_not_commit_or_retry(self):
        def partial(*args):
            self.device.writes.append(('partial',b''));raise TimeoutError('lost ACK')
        with patch.object(self.device,'write_macros',side_effect=partial):
            with self.assertRaises(TimeoutError):self.save()
        self.assertEqual([kind for kind,_ in self.device.writes],['partial'])

    def test_unrelated_firmware_mapping_change_prevents_save(self):
        original_write = self.device.write_macros
        def changed(*args):
            original_write(*args);self.device.mapping[13] = 32
        with patch.object(self.device,'write_macros',side_effect=changed):
            with self.assertRaisesRegex(RuntimeError,'no save sent'):self.save()
        self.assertEqual([kind for kind,_ in self.device.writes],['macros'])

    def test_incorrect_macro_readback_prevents_save(self):
        with patch.object(self.device,'write_macros'):
            with self.assertRaisesRegex(RuntimeError,'Macros changed'):self.save()
        self.assertEqual(self.device.writes,[])

    def test_lost_commit_ack_uses_readback_without_second_commit(self):
        self.device.save_timeout = True
        self.save()
        self.assertEqual([kind for kind,_ in self.device.writes],['macros','save'])

    def test_transport_ranges_use_absolute_start_relative_data_index(self):
        device = ConfigurationDevice('unused');original = empty_bank();updated = replace_macro(original,sample())
        with patch.object(device,'read_macros',return_value=original), \
             patch.object(device,'profile_state',return_value=(1,(1,2,3,4))), \
             patch.object(device,'exchange') as exchange:
            device.write_macros(1,original,updated)
        calls = [call.args[0] for call in exchange.call_args_list]
        indexes = [i for i in range(81) if original[i*20:(i+1)*20]!=updated[i*20:(i+1)*20]]
        self.assertEqual(len(calls),2*len(indexes))
        for i,index in enumerate(indexes):
            self.assertEqual(calls[2*i],protocol.macro_write_start(1,index,1))
            self.assertEqual(calls[2*i+1],protocol.macro_write_pack(0,updated[index*20:(index+1)*20]))

    def test_transport_failure_stops_at_first_uncertain_packet(self):
        device = ConfigurationDevice('unused');original = empty_bank();updated = replace_macro(original,sample())
        with patch.object(device,'read_macros',return_value=original), \
             patch.object(device,'profile_state',return_value=(1,(1,2,3,4))), \
             patch.object(device,'exchange',side_effect=[b'ack',TimeoutError()]) as exchange:
            with self.assertRaises(TimeoutError):device.write_macros(1,original,updated)
            self.assertEqual(exchange.call_count,2)

    def test_profile_switch_during_write_stops_next_range(self):
        device = ConfigurationDevice('unused');original = empty_bank();updated = replace_macro(original,sample())
        with patch.object(device,'read_macros',return_value=original), \
             patch.object(device,'profile_state',side_effect=[(1,()),(2,())]), \
             patch.object(device,'exchange') as exchange:
            with self.assertRaises(RuntimeError):device.write_macros(1,original,updated)
            self.assertEqual(exchange.call_count,2)

    def test_packet_validation_and_vendor_framing(self):
        self.assertEqual(protocol.macro_write_start(2,80,1)[:9],bytes.fromhex('5aa5ad06025001141a'))
        device = ConfigurationDevice('unused')
        for packet in (protocol.macro_write_start(2,0,81),protocol.macro_write_pack(80,bytes(20))):
            with patch('os.write',return_value=33) as write:
                device.send(packet);self.assertEqual(write.call_args.args[1],b'\0'+packet)
            broken = bytearray(packet);broken[-1] = 1
            with patch('os.write') as write:
                with self.assertRaises(ValueError):device.send(bytes(broken))
                write.assert_not_called()
        for start,count in ((80,2),(81,1),(0,0),(-1,1),(True,1)):
            with self.assertRaises(ValueError):protocol.macro_write_start(0,start,count)
        bad = bytearray(empty_bank());bad[1] = 2
        with self.assertRaises(ValueError):decode_bank(bad)

    def test_removal_preserves_other_macros_and_restores_default_button(self):
        self.device.macros=replace_macro(replace_macro(empty_bank(),sample(18)),sample(19))
        self.device.mapping[67:70]=bytes([32,0,0])
        before=decode_bank(self.device.macros).records[1].raw
        with tempfile.TemporaryDirectory() as folder:
            remove_saved_macro(self.device,bytes(self.device.mapping),self.device.macros,18,folder,expected_profile=1)
        after=decode_bank(self.device.macros)
        self.assertEqual(len(after.records),1);self.assertEqual(after.records[0].raw,before)
        self.assertEqual(self.device.mapping[67:70],bytes([255,0,0]))
        self.assertEqual([kind for kind,_ in self.device.writes],['mapping','macros','save'])

    def test_remove_unknown_mapping_or_absent_macro_never_writes(self):
        for marker in (254,33):
            self.device=MacroController();self.device.macros=replace_macro(empty_bank(),sample())
            self.device.mapping[67:70]=bytes([marker,0,0])
            with self.assertRaises(ValueError):
                remove_saved_macro(self.device,bytes(self.device.mapping),self.device.macros,18,self.tmp.name,expected_profile=1)
            self.assertEqual(self.device.writes,[])
        self.device=MacroController()
        with self.assertRaises(ValueError):
            remove_saved_macro(self.device,self.mapping,empty_bank(),18,self.tmp.name,expected_profile=1)
        self.assertEqual(remove_macro(empty_bank(),18),empty_bank())

    def test_incomplete_macro_never_reaches_hardware(self):
        with self.assertRaises(ValueError):
            apply_macro(self.device,self.mapping,self.macros,replace(sample(),actions=sample().actions[:1]),self.tmp.name,expected_profile=1)
        self.assertEqual(self.device.writes,[])
