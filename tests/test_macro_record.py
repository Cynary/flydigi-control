from dataclasses import replace
import unittest
from unittest.mock import patch
from flydigi_control import protocol
from flydigi_control.macro_record import Recorder,direction,record
from flydigi_control.macro_bank import Action,validate_execution
from test_macro_bank import sample


def state(buttons=(), left=(0,0), right=(0,0)):
    return protocol.InputState(left,right,0,0,frozenset(buttons),(),(0,0,0),(0,0,0),b'')


class MacroRecordTests(unittest.TestCase):
    def test_start_button_is_ignored_until_controls_released(self):
        r=Recorder()
        r.feed(state(['A']),0);r.feed(state(['A']),.05)
        self.assertFalse(r.armed)
        r.feed(state(),.1);r.feed(state(['A']),.25);r.feed(state(),.325)
        self.assertEqual(r.finish(.4),(Action(0,4,1),Action(75,4,0)))
        validate_execution(replace(sample(),actions=tuple(r.actions)))

    def test_overlapping_buttons_preserve_timing_without_duplicate_delays(self):
        r=Recorder();r.feed(state(),0)
        r.feed(state(['M1','LM']),.1);r.feed(state(['M1','LM']),.12)
        r.feed(state(['M1']),.15);r.feed(state(['B']),.2);r.feed(state(),.25)
        self.assertEqual(r.finish(.3),(Action(0,18,1),Action(0,22,1),Action(50,22,0),
                                      Action(50,18,0),Action(0,5,1),Action(50,5,0)))
        validate_execution(replace(sample(),actions=tuple(r.actions)))

    def test_directions_and_neutral_return(self):
        pairs=[(0,32767),(32767,32767),(32767,0),(32767,-32768),(0,-32768),
               (-32768,-32768),(-32768,0),(-32768,32767)]
        self.assertEqual([direction(pair) for pair in pairs],list(range(161,169)))
        self.assertEqual(direction((200,200)),160)
        r=Recorder();r.feed(state(),0);r.feed(state(left=pairs[0],right=pairs[2]),.1)
        self.assertEqual(r.finish(.3),(Action(0,161,2),Action(0,163,3),Action(200,160,2),Action(0,160,3)))

    def test_limit_reserves_releases_and_neutral_without_dropping_unmatched_events(self):
        r=Recorder(4);r.feed(state(),0);r.feed(state(['A'],left=(32767,0)),.1)
        r.feed(state(['A','B'],left=(32767,0)),.2)
        self.assertTrue(r.done)
        self.assertEqual(r.actions,[Action(0,4,1),Action(0,163,2),Action(100,4,0),Action(0,160,2)])
        validate_execution(replace(sample(),actions=tuple(r.actions)))
        self.assertEqual(r.finish(99),tuple(r.actions))

    def test_time_limit_closes_held_buttons_without_uint16_overflow(self):
        r=Recorder();r.feed(state(),0);r.feed(state(['A']),.1)
        r.feed(state(),70)
        self.assertTrue(r.done)
        self.assertEqual(r.actions,[Action(0,4,1),Action(65535,4,0)])

    def test_stopped_or_invalid_clock_is_not_silently_accepted(self):
        for value in (float('nan'),float('inf'),-1):
            r=Recorder();r.feed(state(),0)
            with self.assertRaises(ValueError):r.feed(state(['A']),value)
        with self.assertRaises(ValueError):Recorder(1)

    def test_fn_turbo_home_are_not_recorded_as_onboard_macro_keys(self):
        r=Recorder();r.feed(state(),0);r.feed(state(['FN','TURBO','HOME']),.1)
        self.assertEqual(r.finish(.2),())

    def test_no_known_interface_never_opens_or_writes_hid(self):
        with patch('flydigi_control.macro_record.discover',return_value=[]),patch('os.open') as opened,patch('os.write') as written:
            with self.assertRaises(ValueError):record('unknown',15,256,lambda value:None)
            opened.assert_not_called();written.assert_not_called()

    def test_execution_requires_balanced_button_actions(self):
        for actions in ((Action(0,4,0),),(Action(0,4,1),),
                        (Action(0,4,1),Action(50,4,1),Action(50,4,0))):
            with self.assertRaises(ValueError):validate_execution(replace(sample(),actions=actions))
        validate_execution(sample())

    def test_recording_disconnect_closes_fd_and_never_writes(self):
        with patch('flydigi_control.macro_record.discover',return_value=[{'path':'test'}]), \
             patch('os.open',return_value=123),patch('select.select',return_value=([123],[],[])), \
             patch('os.read',return_value=b''),patch('os.close') as closed,patch('os.write') as written:
            with self.assertRaisesRegex(OSError,'disconnected'):record('test',15,256,lambda value:None)
            closed.assert_called_once_with(123);written.assert_not_called()

    def test_recording_stops_when_native_input_is_missing(self):
        with patch('flydigi_control.macro_record.discover',return_value=[{'path':'test'}]), \
             patch('os.open',return_value=123),patch('select.select',return_value=([],[],[])), \
             patch('time.monotonic',side_effect=[0,0,3.1]),patch('os.close') as closed:
            with self.assertRaisesRegex(RuntimeError,'reports stopped'):record('test',15,256,lambda value:None)
            closed.assert_called_once_with(123)
