from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flydigi_control import protocol
from flydigi_control.hardware_settings import SETTINGS, parse_status, setting_packet, apply_setting
from flydigi_control.transport import ConfigurationDevice


def status():
    reply = bytearray(32)
    reply[:3] = bytes.fromhex('5aa503')
    reply[5:13] = bytes([0x7f, 0x08, 0, 0, 15, 1, 3, 17])
    return bytes(reply)


@dataclass
class Identity:
    device_id: int = 130


class Device:
    def __init__(self):
        self.reply = status()
        self.writes = []
        self.lose_ack = False
        self.ignore_write = False
        self.change_other = False

    def info(self):
        return Identity()

    def exchange(self, packet):
        if packet == protocol.request(0x03):
            return self.reply
        self.writes.append(packet)
        changed = bytearray(self.reply)
        if not self.ignore_write:
            if packet[2] == 0x13:
                bit = 1 << (packet[4]-1)
                changed[6] = changed[6] | bit if packet[5] else changed[6] & ~bit
            else:
                changed[{0x15:11, 0x16:12, 0x17:9}[packet[2]]] = packet[4]
            if self.change_other:
                changed[10] ^= 1
            self.reply = bytes(changed)
        if self.lose_ack:
            raise TimeoutError()
        return packet


class HardwareSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.device = Device()

    def apply(self, key, value):
        return apply_setting(self.device, status(), key, value, self.tmp.name)

    def test_parse_flags_and_scalar_fields(self):
        data = parse_status(status())
        self.assertEqual(data['turbo'], dict(supported=True, value=True))
        self.assertEqual(data['rebound'], dict(supported=True, value=False))
        self.assertEqual(data['precision']['value'], 3)
        self.assertEqual(data['sensitivity']['value'], 17)
        self.assertEqual(data['sleep']['value'], 15)
        for invalid in (b'', status()[:-1], b'\x00'*32):
            with self.assertRaises(ValueError): parse_status(invalid)

    def test_zero_means_no_scalar_capability_except_sleep(self):
        reply = bytearray(status());reply[9:13] = bytes(4)
        data = parse_status(reply)
        self.assertFalse(data['precision']['supported'])
        self.assertFalse(data['sensitivity']['supported'])
        self.assertTrue(data['sleep']['supported'])
        self.assertEqual(data['sleep']['value'], 0)

    def test_packets_match_sdk_field_positions_and_checksums(self):
        expected = {
            ('auto_calibration', True): '5aa5130406011e',
            ('rebound', False): '5aa5130407001e',
            ('precision', 5): '5aa51503051d',
            ('sensitivity', 19): '5aa51603132c',
            ('sleep', 180): '5aa51703b4ce',
        }
        for args, hexval in expected.items():
            self.assertEqual(setting_packet(*args),bytes.fromhex(hexval).ljust(32,b'\x00'))
        for args in (('sleep',True),('home_button',1),('precision',7),('sensitivity',16),('sleep',255),('report_rate',1)):
            with self.assertRaises(ValueError):setting_packet(*args)

    def test_each_setting_changes_only_its_field_and_is_backed_up(self):
        for key,item in SETTINGS.items():
            for value,_ in item.choices:
                with self.subTest(key=key,value=value):
                    self.device=Device()
                    actual=self.apply(key,value)
                    self.assertEqual(parse_status(actual)[key]['value'],value)
                    for other in SETTINGS.keys()-{key}:
                        self.assertEqual(parse_status(actual)[other],parse_status(status())[other])
        backups=list(Path(self.tmp.name).glob('*.json'))
        self.assertTrue(backups)
        saved=json.loads(backups[0].read_text())
        self.assertEqual(saved['status'],status().hex())
        self.assertEqual(saved['controller']['device_id'],130)
        self.assertEqual(backups[0].stat().st_mode & 0o777,0o600)

    def test_noop_does_not_write(self):
        self.apply('sleep',15)
        self.assertEqual(self.device.writes,[])
        self.assertEqual(list(Path(self.tmp.name).glob('*.json')),[])

    def test_stale_or_unknown_value_or_capability_blocks_write(self):
        for offset,value,key,new in [(9,60,'sleep',1),(5,0,'rebound',True),(11,7,'precision',1)]:
            self.device=Device();r=bytearray(status());r[offset]=value;self.device.reply=bytes(r)
            with self.assertRaises((ValueError,RuntimeError)):
                apply_setting(self.device,self.device.reply if offset!=9 else status(),key,new,self.tmp.name)
            self.assertFalse(self.device.writes)

    def test_backup_failure_prevents_write(self):
        with patch('flydigi_control.hardware_settings._backup',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.apply('sleep',1)
        self.assertFalse(self.device.writes)

    def test_lost_ack_is_verified_never_replayed(self):
        self.device.lose_ack=True
        self.assertEqual(parse_status(self.apply('sleep',1))['sleep']['value'],1)
        self.assertEqual(len(self.device.writes),1)
        self.device=Device();self.device.lose_ack=self.device.ignore_write=True
        with self.assertRaisesRegex(RuntimeError,'not retried'):self.apply('sleep',1)
        self.assertEqual(len(self.device.writes),1)

    def test_change_in_other_field_is_reported_without_automatic_rollback(self):
        self.device.change_other=True
        with self.assertRaisesRegex(RuntimeError,'differs'):self.apply('sleep',1)
        self.assertEqual(len(self.device.writes),1)

    def test_transport_only_accepts_exact_known_packets(self):
        d=ConfigurationDevice('unused')
        for key,item in SETTINGS.items():
            for value,_ in item.choices:
                packet=setting_packet(key,value)
                with patch('os.write',return_value=33) as write:
                    d.send(packet)
                    self.assertEqual(write.call_args.args[1],b'\x00'+packet)
                for offset in (3,31):
                    bad=bytearray(packet);bad[offset]^=1
                    with patch('os.write') as write:
                        with self.assertRaises(ValueError):d.send(bytes(bad))
                        write.assert_not_called()
        with patch('os.write') as write:
            with self.assertRaises(ValueError):d.send(protocol.request(0x14,1))
            write.assert_not_called()
