from dataclasses import replace
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from flydigi_control import protocol
from flydigi_control.macro_bank import Action, Macro, BANK_SIZE, decode_bank, replace_macro
from flydigi_control.persistence import apply_lighting
from flydigi_control.transport import ConfigurationDevice
from test_persistence import Controller


def empty_bank():
    return bytes.fromhex('00010000') + b'\xff'*(BANK_SIZE-4)


def sample(key=18):
    return Macro(key,1,100,'Test',(Action(0,4,1),Action(50,4,0)))


class MacroBankTests(unittest.TestCase):
    def test_physical_83_chunk_readback_preserves_tail_on_edit_and_remove(self):
        from flydigi_control.macro_bank import remove_macro
        data=json.loads((Path(__file__).parent/'fixtures/vader5-7150-macro-readback.json').read_text())
        blob=bytes.fromhex(data['hex'])
        self.assertEqual(len(blob),1660)
        self.assertEqual(decode_bank(blob).records,())
        # Non-FF sentinels also survive, rather than accidentally being rebuilt.
        blob=blob[:BANK_SIZE]+bytes(range(40))
        edited=replace_macro(blob,sample())
        removed=remove_macro(edited,sample().key)
        for value in (edited,removed):
            self.assertEqual(len(value),1660)
            self.assertEqual(value[BANK_SIZE:],blob[BANK_SIZE:])
        self.assertEqual(len(decode_bank(edited).records),1)
        self.assertEqual(decode_bank(removed).records,())

    def test_macro_transport_rejects_resize_or_reserved_tail_write(self):
        d=ConfigurationDevice('unused')
        blob=empty_bank()+bytes(range(40))
        for updated in (empty_bank(),blob[:-1]+b'X'):
            with patch.object(d,'read_macros') as read, patch.object(d,'exchange') as write:
                with self.assertRaisesRegex(ValueError,'geometry or reserved tail'):
                    d.write_macros(0,blob,updated)
                read.assert_not_called();write.assert_not_called()

    def test_save_rejects_macro_resize_before_any_write(self):
        from flydigi_control.persistence import apply_configuration
        device=Controller();device.macros=empty_bank()+bytes(range(40))
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,'geometry and reserved tail'):
                apply_configuration(device,folder,macro_update=lambda b:b[:BANK_SIZE])
        self.assertEqual(device.writes,[])

    def test_matches_actual_vendor_serializer_vectors(self):
        vectors=json.loads(Path(__file__).with_name('macro_reference_vectors.json').read_text())
        for vector in vectors:
            blob=empty_bank()
            for i in range(vector['count']):
                macro=Macro(i+4,1+i%3,10+i*5,'é猫' if i==1 else 'Test'+str(i),
                    (Action(0,4,1),Action(37+i,4,0),Action(258+i,163,2),Action(14,160,3)))
                blob=replace_macro(blob,macro)
            expected=bytes.fromhex(vector['hex']).ljust(BANK_SIZE,b'\xff')
            self.assertEqual(blob,expected)
            self.assertEqual(len(decode_bank(expected).records),vector['count'])

    def test_edit_preserves_unrelated_record_and_reserved_bytes(self):
        blob=replace_macro(replace_macro(empty_bank(),sample()),sample(19))
        blob=bytearray(blob);blob[30:36]=b'ABCDEF'  # selected record's reserved header
        before=decode_bank(blob)
        edited=replace(before.records[0].macro,name='Changed',actions=before.records[0].macro.actions+(Action(12,5,1),Action(8,5,0)))
        after=decode_bank(replace_macro(blob,edited))
        self.assertEqual(after.records[1].raw,before.records[1].raw)
        self.assertEqual(after.records[0].raw[6:12],b'ABCDEF')
        self.assertEqual(replace_macro(blob,before.records[0].macro),blob)

    def test_bounds_and_unknown_bank_are_rejected(self):
        for blob in (b'',b'\xff'*BANK_SIZE):
            with self.assertRaises(ValueError):decode_bank(blob)
        blob=bytearray(replace_macro(empty_bank(),sample()))
        for offset,value in [(2,11),(4,255),(26,2)]:
            broken=bytearray(blob);broken[offset]=value
            with self.assertRaises(ValueError):decode_bank(broken)
        # The second event cannot precede the first on the cumulative clock.
        broken=bytearray(blob);struct.pack_into('<H',broken,56,100)
        with self.assertRaises(ValueError):decode_bank(broken)

    def test_duplicate_key_or_overlapping_offsets_are_rejected(self):
        blob=bytearray(replace_macro(replace_macro(empty_bank(),sample()),sample(19)))
        duplicate=bytearray(blob);duplicate[64]=18
        with self.assertRaises(ValueError):decode_bank(duplicate)
        struct.pack_into('<H',blob,6,0)
        with self.assertRaises(ValueError):decode_bank(blob)

    def test_limits_do_not_silently_wrap_truncate_or_drop_macros(self):
        for macro in (replace(sample(),name='猫'*7),replace(sample(),mode=4),
                      replace(sample(),key=24),replace(sample(),interval_ms=65536),
                      replace(sample(),actions=(Action(65535,4,1),Action(1,4,0))),
                      replace(sample(),actions=(Action(1,4,5),)),replace(sample(),actions=()),
                      replace(sample(),actions=(Action(-1,4,1),)),
                      replace(sample(),actions=(Action(1,4,True),))):
            with self.assertRaises(ValueError):replace_macro(empty_bank(),macro)
        bank=empty_bank()
        for key in range(10):bank=replace_macro(bank,sample(key))
        with self.assertRaises(ValueError):replace_macro(bank,sample(10))
        bank=replace_macro(empty_bank(),replace(sample(),actions=tuple(Action(1,4,i%2) for i in range(256))))
        with self.assertRaises(ValueError):replace_macro(bank,sample(19))

    def test_read_command_and_transport_allow_only_read(self):
        self.assertEqual(protocol.macro_read_request(2)[:7],bytes.fromhex('5aa5ac040214c6'))
        d=ConfigurationDevice('unused')
        with patch('os.write',return_value=33) as write:
            d.send(protocol.macro_read_request(2))
            self.assertEqual(write.call_args.args[1],b'\0'+protocol.macro_read_request(2))
        with patch('os.write') as write:
            for command in (0xad,0xae):
                with self.assertRaises(ValueError):d.send(protocol.request(command))
            write.assert_not_called()

    def test_macro_chunks_assemble_out_of_order_without_consuming_inputs(self):
        d=ConfigurationDevice('unused');d.fd=9
        blob=replace_macro(empty_bank(),sample())
        def reply(index):
            return bytes([0x5a,0xa5,0xac,81,index,1])+blob[index*20:(index+1)*20]+bytes(6)
        replies=[b'\x5a\xa5\xef'+bytes(29)]+[reply(i) for i in reversed(range(81))]
        with patch.object(d,'profile_state',return_value=(1,(1,2,3,4))),patch.object(d,'send'),\
             patch.object(d,'_read',side_effect=[[],replies]),patch('select.select'):
            self.assertEqual(d.read_macros(1),blob)

    def test_physical_chunk_count_is_read_without_truncation(self):
        d=ConfigurationDevice('unused');d.fd=9
        blob=empty_bank()+bytes(range(40))
        replies=[bytes([0x5a,0xa5,0xac,83,i,1])+blob[i*20:(i+1)*20]+bytes(6)
                 for i in reversed(range(83))]
        with patch.object(d,'profile_state',return_value=(1,(1,2,3,4))),patch.object(d,'send'),\
             patch.object(d,'_read',side_effect=[[],replies]),patch('select.select'):
            self.assertEqual(d.read_macros(1),blob)

    def test_wrong_profile_or_conflicting_chunks_fail(self):
        d=ConfigurationDevice('unused');d.fd=9
        first=bytes([0x5a,0xa5,0xac,81,0,1])+bytes(26)
        wrong=bytearray(first);wrong[5]=2
        conflict=bytearray(first);conflict[6]=1
        for replies in ([bytes(wrong)],[first,bytes(conflict)]):
            with patch.object(d,'profile_state',return_value=(1,(1,2,3,4))),patch.object(d,'send'),\
                 patch.object(d,'_read',side_effect=[[],replies]),patch('select.select'):
                with self.assertRaises(ValueError):d.read_macros(1)

    def test_every_profile_save_backs_up_separate_macros(self):
        device=Controller();device.macros=replace_macro(empty_bank(),sample())
        with tempfile.TemporaryDirectory() as tmp:
            path=apply_lighting(device,5,[(255,0,0)],30,15,tmp)
            self.assertEqual(json.loads(path.read_text())['macros'],device.macros.hex())
        self.assertEqual([kind for kind,_ in device.writes],['lighting','save'])

    def test_failed_or_changed_macro_read_prevents_saving(self):
        for values in ([TimeoutError()], [empty_bank(),bytes(BANK_SIZE)],
                       [empty_bank(),empty_bank(),bytes(BANK_SIZE)]):
            device=Controller()
            with tempfile.TemporaryDirectory() as tmp,patch.object(device,'read_macros',side_effect=values):
                with self.assertRaises((TimeoutError,RuntimeError)):
                    apply_lighting(device,5,[(255,0,0)],30,15,tmp)
            self.assertNotIn('save',[kind for kind,_ in device.writes])

    def test_macro_change_after_save_reported_without_replay(self):
        device=Controller()
        with tempfile.TemporaryDirectory() as tmp,patch.object(device,'read_macros',side_effect=[empty_bank()]*3+[bytes(BANK_SIZE)]):
            with self.assertRaisesRegex(RuntimeError,'Macros differ after saving'):
                apply_lighting(device,5,[(255,0,0)],30,15,tmp)
        self.assertEqual([kind for kind,_ in device.writes],['lighting','save'])

    def test_older_mapping_does_not_query_separate_macros(self):
        device=Controller();device.mapping[0]=1
        with tempfile.TemporaryDirectory() as tmp,patch.object(device,'read_macros',side_effect=AssertionError('not 3.2')):
            apply_lighting(device,5,[(255,0,0)],30,15,tmp)
