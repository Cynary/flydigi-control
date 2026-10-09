import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import patch
try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication
    from flydigi_control.ui import Window, ApplyColor
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False


@unittest.skipUnless(QT_AVAILABLE, 'PySide6 not installed')
class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.discovery = patch('flydigi_control.ui.discover', return_value=[])
        self.discovery.start()
        self.nav = patch('flydigi_control.ui.GamepadNavigation')
        self.nav.start().return_value.mapped_devices.return_value=[]
        self.window = Window()
        # Each test drives discovery/navigation explicitly. Background timer
        # ticks during processEvents make mock counts and UI state race.
        self.window.timer.stop()
        self.window.discovery_timer.stop()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.app.processEvents()
        self.discovery.stop()
        self.nav.stop()

    def press(self, key):
        self.window.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))

    def test_hotplug_processing_continues_without_dispatch_when_unfocused(self):
        self.window.navigation.devices = {}
        self.window.navigation.poll.return_value = ['accept']
        with patch.object(self.window, 'isActiveWindow', return_value=False), \
             patch.object(self.window, 'keyPressEvent') as dispatch:
            self.window.poll_navigation()
            self.window.navigation.poll.assert_called_once()
            dispatch.assert_not_called()

    def test_no_device_disables_writes(self):
        for button in (self.window.apply, self.window.off, self.window.turbo, self.window.hotkeys, self.window.native):
            self.assertFalse(button.isEnabled())
        for button in self.window.motor_panel.buttons:
            self.assertFalse(button.isEnabled())

    def test_motor_selection_keeps_four_levels_independent(self):
        panel = self.window.motor_panel
        for slider, level in zip(panel.sliders, (20, 40, 60, 80)):
            slider.setValue(level)
        requested = []
        panel.requested.connect(requested.append)
        for side in range(4):
            panel.request(side)
        panel.request(None)
        self.assertEqual(requested, [(51,0,0,0), (0,102,0,0),
                                     (0,0,153,0), (0,0,0,204), (51,102,153,204)])

    def test_curve_preview_has_no_writes_and_rejects_unvalidated_negative_save(self):
        panel = self.window.curve_panel
        panel.set_available(True)
        panel.kind.setCurrentIndex(1)
        self.assertEqual(panel.curve().point1,(64,96))
        self.assertTrue(panel.save.isEnabled())
        panel.sliders[0].setValue(-10)
        self.assertEqual(panel.kind.currentIndex(),3)
        self.assertFalse(panel.save.isEnabled())
        self.assertIn('preview-only',panel.note.text())
        self.assertEqual(len(panel.plot.proposed),9)
        self.assertIsNone(self.window.worker)
        panel.kind.setCurrentIndex(0)
        self.assertEqual(panel.curve().center,0)
        self.assertTrue(panel.save.isEnabled())

    def test_curve_editor_fits_1080p_and_is_controller_navigable(self):
        self.window.pages.setCurrentIndex(6)
        self.app.processEvents()
        self.assertLessEqual(self.window.minimumSizeHint().height(),1080)
        panel = self.window.curve_panel
        panel.sliders[2].setFocus()
        initial = panel.sliders[2].value()
        self.press(Qt.Key.Key_Right)
        self.assertEqual(panel.sliders[2].value(),initial+1)
        self.assertEqual(panel.kind.currentIndex(),3)
        panel.back.setFocus()
        self.press(Qt.Key.Key_Return)
        self.assertEqual(self.window.pages.currentIndex(),3)

    def test_profile_fields_load_without_writes_and_reject_invalid_travel(self):
        from test_profile_controls import profile
        panel=self.window.trigger_panel
        panel.set_available(True)
        panel.load(dict(mapping=profile(),profile=0))
        self.assertEqual(panel.values()['maximum'],45)
        self.assertTrue(panel.save.isEnabled())
        panel.fields['start'].setValue(255)
        self.assertFalse(panel.save.isEnabled())
        self.assertIsNone(self.window.worker)
        panel.side.setCurrentIndex(1)
        self.assertTrue(panel.save.isEnabled())
        self.assertEqual(panel.values()['start'],0)

    def test_unknown_saved_profile_value_is_not_clamped_and_saved(self):
        from test_profile_controls import profile
        value=bytearray(profile());value[149]=150
        panel=self.window.grip_panel
        panel.set_available(True)
        panel.load(dict(mapping=bytes(value),profile=0))
        self.assertFalse(panel.save.isEnabled())
        self.assertIn('Unknown saved strength',panel.details.text())
        panel.clear()
        self.assertIsNone(panel.mapping)

    def test_trigger_page_does_not_clip_motor_fields(self):
        from test_profile_controls import profile
        panel=self.window.trigger_panel
        self.window.pages.setCurrentIndex(7)
        panel.load(dict(mapping=profile(),profile=0))
        for _ in range(3):self.app.processEvents()
        last=panel.fields['strength']
        self.assertLess(last.mapTo(panel,last.rect().bottomLeft()).y(),panel.details.y())
        self.assertLessEqual(self.window.minimumSizeHint().height(),1080)

    def test_hardware_settings_are_read_first_and_controller_navigable(self):
        from test_hardware_settings import status
        panel=self.window.hardware_panel
        self.window.pages.setCurrentIndex(9)
        panel.set_available(True)
        self.assertFalse(panel.apply.isEnabled())
        panel.load(status())
        self.assertFalse(panel.apply.isEnabled())
        panel.choice.setFocus()
        self.press(Qt.Key.Key_Right)
        self.assertIs(panel.choice.currentData(),True)
        self.assertTrue(panel.apply.isEnabled())
        self.assertIsNone(self.window.worker)
        for _ in range(3): self.app.processEvents()
        self.assertLessEqual(self.window.minimumSizeHint().height(),1080)
        panel.back.setFocus()
        self.press(Qt.Key.Key_Return)
        self.assertEqual(self.window.pages.currentIndex(),1)

    def test_hardware_settings_unknown_and_unsupported_values_are_not_clamped(self):
        from test_hardware_settings import status
        panel=self.window.hardware_panel
        panel.set_available(True)
        value=bytearray(status());value[11]=7
        panel.load(bytes(value))
        panel.setting.setCurrentIndex(panel.setting.findData('precision'))
        self.assertFalse(panel.choice.isEnabled())
        self.assertFalse(panel.apply.isEnabled())
        self.assertIn('Unrecognized',panel.current.text())
        value[5]=0;panel.load(bytes(value))
        panel.setting.setCurrentIndex(panel.setting.findData('rebound'))
        self.assertIn('Not advertised',panel.current.text())
        panel.clear()
        self.assertIsNone(panel.snapshot)
        self.assertFalse(panel.apply.isEnabled())

    def test_failed_hardware_write_invalidates_snapshot(self):
        from test_hardware_settings import status
        panel=self.window.hardware_panel
        panel.load(status())
        self.window.hardware_result(False,'Uncertain write')
        self.assertIsNone(panel.snapshot)
        self.assertEqual(panel.result.text(),'Uncertain write')

    def test_onboard_button_editor_loads_without_writes_and_uses_controller(self):
        from test_button_mappings import profile
        panel=self.window.button_panel
        panel.set_available(True)
        panel.load(dict(mapping=profile(),profile=0))
        self.window.pages.setCurrentIndex(10)
        self.assertFalse(panel.save.isEnabled())
        self.assertFalse(panel.frequency.isEnabled())
        panel.source.setCurrentIndex(18)
        self.assertEqual(panel.target.currentData(),18)
        panel.target.setCurrentIndex(4)
        self.assertTrue(panel.save.isEnabled())
        self.assertIsNone(self.window.worker)
        panel.kind.setCurrentIndex(1)
        self.assertTrue(panel.frequency.isEnabled())
        panel.frequency.setFocus()
        initial=panel.frequency.value()
        self.press(Qt.Key.Key_Right)
        self.assertEqual(panel.frequency.value(),initial+1)
        for _ in range(3):self.app.processEvents()
        self.assertLessEqual(self.window.minimumSizeHint().height(),1080)
        panel.back.setFocus();self.press(Qt.Key.Key_Return)
        self.assertEqual(self.window.pages.currentIndex(),1)

    def test_onboard_button_editor_preserves_unsupported_mapping(self):
        from test_button_mappings import profile
        panel=self.window.button_panel
        panel.set_available(True)
        value=bytearray(profile());value[13]=32
        panel.load(dict(mapping=bytes(value),profile=0))
        self.assertFalse(panel.save.isEnabled())
        self.assertFalse(panel.kind.isEnabled())
        self.assertIn('macro',panel.details.text())
        panel.source.setCurrentIndex(1)
        self.assertTrue(panel.kind.isEnabled())
        self.window.device_changed()
        self.assertIsNone(panel.mapping)
        self.assertFalse(panel.save.isEnabled())

    def test_motion_editor_navigation_and_unchanged_read(self):
        from test_motion_mapping import profile
        panel=self.window.motion_panel
        self.window.pages.setCurrentIndex(11)
        panel.set_available(True);panel.load(dict(mapping=profile(),profile=0))
        self.assertFalse(panel.save.isEnabled())
        self.assertFalse(panel.fields['key'].isEnabled())
        panel.fields['target'].setCurrentIndex(2)
        self.assertTrue(panel.fields['key'].isEnabled())
        self.assertFalse(panel.fields['second'].isEnabled())
        self.assertTrue(panel.save.isEnabled())
        panel.fields['activation'].setCurrentIndex(1)
        self.assertTrue(panel.fields['second'].isEnabled())
        panel.fields['sensitivity'].setFocus()
        self.press(Qt.Key.Key_Right)
        self.assertEqual(panel.fields['sensitivity'].value(),26)
        self.assertIsNone(self.window.worker)
        for _ in range(3):self.app.processEvents()
        self.assertLessEqual(self.window.minimumSizeHint().height(),1080)
        panel.back.setFocus();self.press(Qt.Key.Key_Return)
        self.assertEqual(self.window.pages.currentIndex(),1)

    def test_motion_editor_rejects_pc_mouse_and_invalid_activation(self):
        from test_motion_mapping import profile
        panel=self.window.motion_panel;panel.set_available(True)
        m=bytearray(profile());m[137]=3
        panel.load(dict(mapping=bytes(m),profile=0))
        self.assertFalse(panel.save.isEnabled())
        self.assertFalse(panel.fields['target'].isEnabled())
        self.assertIn('PC-side',panel.details.text())
        panel.load(dict(mapping=profile(),profile=0))
        panel.fields['target'].setCurrentIndex(2)
        panel.fields['key'].setCurrentIndex(panel.fields['key'].findData(255))
        self.assertFalse(panel.save.isEnabled())
        self.assertIn('activation',panel.result.text())
        self.window.device_changed()
        self.assertIsNone(panel.mapping)
        self.assertFalse(panel.save.isEnabled())

    def test_motor_stop_remains_available_while_settings_are_locked(self):
        from flydigi_control.motor_ui import MotorTest
        self.window.devices = [dict(path='/dev/test', remote_wake_advertised=False)]
        worker = MotorTest('/dev/test', (0,0,0,0))
        self.window.worker = worker
        self.window.show_device()
        self.assertFalse(self.window.apply.isEnabled())
        self.assertTrue(self.window.motor_panel.stop.isEnabled())
        self.assertFalse(self.window.motor_panel.all.isEnabled())
        self.window.motor_panel.stop.click()
        self.assertTrue(worker.cancel.is_set())
        self.window.worker = None

    def test_first_receiver_is_selected(self):
        device = {'path': '/dev/hidraw99', 'name': 'Vader 5 Pro',
                  'remote_wake_advertised': False}
        with patch('flydigi_control.ui.discover', return_value=[device]):
            self.window.refresh()
        self.assertEqual(self.window.device_box.currentData(), '/dev/hidraw99')
        self.assertTrue(self.window.read_settings.isEnabled())

    def test_navigation_stays_on_visible_page(self):
        self.window.settings_tab.setFocus()
        self.press(Qt.Key.Key_Return)
        self.assertEqual(self.window.pages.currentIndex(), 1)
        self.press(Qt.Key.Key_Right)
        self.assertIs(QApplication.focusWidget(), self.window.test_tab)
        self.window.lighting_tab.setFocus()
        self.press(Qt.Key.Key_Return)
        self.assertEqual(self.window.pages.currentIndex(), 0)
        self.window.brightness.setFocus()
        self.press(Qt.Key.Key_Left)
        self.assertEqual(self.window.brightness.value(), 25)

    def test_button_test_cannot_activate_settings_or_exit(self):
        self.window.testing = True
        self.window.settings_tab.setFocus()
        before = self.window.pages.currentIndex()
        self.press(Qt.Key.Key_Return)
        self.press(Qt.Key.Key_Escape)
        self.assertEqual(self.window.pages.currentIndex(), before)
        self.assertTrue(self.window.isVisible())
        self.window.testing = False

    def test_spatial_navigation_follows_color_grid(self):
        self.window.color_buttons[0].setFocus()
        self.press(Qt.Key.Key_Right)
        self.assertIs(QApplication.focusWidget(), self.window.color_buttons[1])
        self.press(Qt.Key.Key_Down)
        self.assertIs(QApplication.focusWidget(), self.window.color_buttons[4])

    def test_multicolor_editing_and_rgb_are_independent(self):
        self.window.effect.setCurrentIndex(2)
        self.assertEqual(len(self.window.colors), 3)
        self.window.color_slot.setCurrentIndex(1)
        self.window.rgb_sliders[0].setValue(237)
        self.assertEqual(self.window.colors[1][0],237)
        self.assertEqual(self.window.colors[0],(0,0,100))
        self.window.brightness.setValue(7)
        self.assertEqual(self.window.colors[1][0],237)
        self.window.effect.setCurrentIndex(0)
        self.assertEqual(len(self.window.colors),1)
        self.assertFalse(self.window.add_color.isEnabled())

    def test_device_change_clears_feature_state(self):
        self.window.feature_values = {'turbo': {'supported': True, 'enabled': True}}
        self.window.device_changed()
        self.assertEqual(self.window.feature_values, {})
        self.assertIsNone(self.window.stick_values)
        self.assertFalse(self.window.stick_apply.isEnabled())

    def test_stick_page_displays_each_stick_without_copying_settings(self):
        self.window.pages.setCurrentIndex(3)
        self.window.set_stick_values({'profile': 2, 'mapping': b'example',
            'sticks': [{'shape': 0, 'center': 2, 'edge': 4}, {'shape': 1, 'center': 5, 'edge': 6}]})
        self.assertEqual(self.window.stick_shape.currentIndex(), 0)
        self.window.stick_side.setCurrentIndex(1)
        self.assertEqual(self.window.stick_shape.currentIndex(), 1)
        self.assertIn('Center: 5', self.window.stick_summary.text())

    def test_apply_uses_guarded_save_and_reports_failure(self):
        worker = ApplyColor('/dev/hidraw99', 5, [(255, 0, 255)], 30, 15)
        results = []
        worker.result.connect(lambda ok, message: results.append((ok, message)))
        with patch('flydigi_control.ui.ConfigurationDevice') as device, \
             patch('flydigi_control.ui.apply_lighting') as apply:
            worker.run()
            self.assertIs(apply.call_args.args[0], device.return_value.__enter__.return_value)
            self.assertTrue(results[-1][0])
            apply.side_effect = RuntimeError('Save not confirmed')
            worker.run()
            self.assertEqual(results[-1], (False, 'Save not confirmed'))

    def test_macro_editor_builds_actions_without_writing(self):
        from test_macro_bank import empty_bank
        from test_profile_controls import profile
        from flydigi_control.macro_bank import decode_bank,replace_macro,Action
        panel=self.window.macro_panel
        panel.set_available(True)
        panel.load(dict(mapping=profile(),macros=empty_bank(),profile=0))
        panel.source.setCurrentIndex(18)
        self.assertFalse(panel.save.isEnabled())
        panel.target.setCurrentIndex(4);panel.add.click()
        panel.event.setCurrentIndex(panel.event.findData(0));panel.target.setCurrentIndex(4)
        panel.delay.setValue(50);panel.add.click()
        self.assertEqual(panel.macro().actions,(Action(0,4,1),Action(50,4,0)))
        self.assertTrue(panel.save.isEnabled())
        encoded=replace_macro(empty_bank(),panel.macro())
        self.assertEqual(decode_bank(encoded).records[0].macro.key,18)
        self.assertIsNone(self.window.worker)
        panel.earlier.click()
        self.assertEqual(panel.actions[0],Action(50,4,0))
        panel.remove.click()
        self.assertEqual(len(panel.actions),1)
        panel.remove.click()
        self.assertFalse(panel.save.isEnabled())

    def test_macro_editor_preserves_unknown_events_and_rejects_save(self):
        from test_macro_bank import empty_bank,sample
        from test_profile_controls import profile
        from flydigi_control.macro_bank import replace_macro
        blob=bytearray(replace_macro(empty_bank(),sample()));blob[59]=5
        panel=self.window.macro_panel
        panel.set_available(True)
        panel.source.setCurrentIndex(18)
        panel.load(dict(mapping=profile(),macros=bytes(blob),profile=0))
        self.assertEqual(panel.actions[0].event,5)
        self.assertFalse(panel.save.isEnabled())
        self.assertIn('Unknown event',panel.action.itemText(0))
        panel.clear();self.assertFalse(panel.add.isEnabled())

    def test_macro_editor_fits_1080p_and_controller_edits_delay(self):
        from test_macro_bank import empty_bank,sample
        from test_profile_controls import profile
        from flydigi_control.macro_bank import replace_macro
        self.window.pages.setCurrentIndex(12)
        panel=self.window.macro_panel
        panel.set_available(True);panel.source.setCurrentIndex(18)
        panel.load(dict(mapping=profile(),macros=replace_macro(empty_bank(),sample()),profile=0))
        for _ in range(3):self.app.processEvents()
        self.assertLessEqual(self.window.minimumSizeHint().height(),1080)
        self.assertLessEqual(panel.save.geometry().bottom(),panel.height())
        panel.delay.setFocus();before=panel.delay.value()
        self.press(Qt.Key.Key_Right)
        self.assertEqual(panel.delay.value(),before+10)
        panel.back.setFocus();self.press(Qt.Key.Key_Return)
        self.assertEqual(self.window.pages.currentIndex(),1)

    def test_macro_new_names_fit_every_activation_button(self):
        from test_macro_bank import empty_bank
        from test_profile_controls import profile
        from flydigi_control.macro_bank import replace_macro
        panel=self.window.macro_panel
        panel.set_available(True);panel.load(dict(mapping=profile(),macros=empty_bank(),profile=0))
        for source in range(24):
            panel.source.setCurrentIndex(source)
            panel.event.setCurrentIndex(panel.event.findData(1));panel.target.setCurrentIndex(4)
            panel.add.click()
            self.assertFalse(panel.save.isEnabled())
            panel.event.setCurrentIndex(panel.event.findData(0));panel.target.setCurrentIndex(4);panel.add.click()
            self.assertTrue(panel.save.isEnabled(),panel.name)
            replace_macro(empty_bank(),panel.macro())

    def test_macro_worker_reads_before_edit_and_reports_failed_save(self):
        from flydigi_control.macro_ui import MacroOperation
        from test_macro_edit import MacroController
        from test_macro_bank import sample
        device=MacroController()
        snapshot=dict(mapping=bytes(device.mapping),macros=device.macros,profile=1)
        worker=MacroOperation('unused',snapshot,sample())
        results=[];values=[]
        worker.result.connect(lambda ok,text:results.append((ok,text)))
        worker.values.connect(values.append)
        with patch('flydigi_control.macro_ui.ConfigurationDevice') as context, \
             patch('flydigi_control.macro_ui.apply_macro',side_effect=TimeoutError('lost ACK')):
            context.return_value.__enter__.return_value=device
            worker.run()
        self.assertEqual(results,[(False,'lost ACK')]);self.assertEqual(values,[])
        reader=MacroOperation('unused')
        reader.values.connect(values.append)
        with patch('flydigi_control.macro_ui.ConfigurationDevice') as context:
            context.return_value.__enter__.return_value=device
            reader.run()
        self.assertEqual(values,[snapshot])


    def test_macro_recording_creates_draft_only_and_name_keyboard_works(self):
        from test_macro_bank import empty_bank,sample
        from test_profile_controls import profile
        panel=self.window.macro_panel
        panel.set_available(True);panel.load(dict(mapping=profile(),macros=empty_bank(),profile=0))
        panel.set_recording(sample().actions)
        self.assertTrue(panel.save.isEnabled());self.assertIsNone(self.window.worker)
        self.window.rename_macro();self.assertEqual(self.window.pages.currentIndex(),13)
        name=self.window.name_panel;name.clear_button.click()
        name.keys[0].setFocus();self.press(Qt.Key.Key_Return)
        name.case.click();name.keys[1].click();name.done.click()
        self.assertEqual(panel.name,'aB');self.assertEqual(self.window.pages.currentIndex(),12)
        name.set_value('猫'*6);name.append('a');name.append('b');name.append('c')
        self.assertEqual(name.value,'猫'*6+'AB')
        self.assertLessEqual(self.window.minimumSizeHint().height(),1080)

    def test_macro_delete_requires_confirmation_and_clears_on_source_change(self):
        from test_macro_bank import empty_bank,sample
        from test_profile_controls import profile
        from flydigi_control.macro_bank import replace_macro
        panel=self.window.macro_panel;panel.set_available(True);panel.source.setCurrentIndex(18)
        panel.load(dict(mapping=profile(),macros=replace_macro(empty_bank(),sample()),profile=0))
        signals=[];panel.delete_requested.connect(lambda:signals.append(True))
        panel.delete.click();self.assertEqual(signals,[])
        panel.source.setCurrentIndex(19);self.assertFalse(panel.delete_pending)
        self.assertFalse(panel.delete.isEnabled())
        panel.source.setCurrentIndex(18);panel.delete.click();panel.delete.click()
        self.assertEqual(signals,[True])


    def test_macro_recording_disabled_when_all_bank_slots_used(self):
        from test_macro_bank import empty_bank,sample
        from test_profile_controls import profile
        from flydigi_control.macro_bank import replace_macro
        bank=empty_bank()
        for key in range(10):bank=replace_macro(bank,sample(key))
        panel=self.window.macro_panel;panel.set_available(True)
        panel.load(dict(mapping=profile(),macros=bank,profile=0))
        self.assertTrue(panel.record.isEnabled())
        panel.source.setCurrentIndex(18)
        self.assertFalse(panel.record.isEnabled())
        self.assertEqual(panel.recording_capacity(),0)
        panel.source.setCurrentIndex(0)
        self.assertEqual(panel.recording_capacity(),256-18)


    def test_mapped_comparison_requires_selection_and_does_not_change_it_on_hotplug(self):
        nav=self.window.navigation
        nav.mapped_devices.return_value=[(7,'Steam Virtual Gamepad'),(8,'Another controller')]
        self.window.refresh_output_devices()
        self.assertIsNone(self.window.output_device.currentData())
        nav.select_output.assert_not_called()
        self.window.output_device.setCurrentIndex(1)
        nav.select_output.assert_called_once_with(7)
        nav.mapped_devices.return_value=[(8,'Another controller')]
        self.window.refresh_output_devices()
        self.assertEqual(self.window.output_device.currentData(),7)
        self.assertIn('Disconnected',self.window.output_device.currentText())
        self.assertIn('disconnected',self.window.analog_panel.mapped_values.text())
        nav.select_output.assert_called_once_with(7)

    def test_mapped_four_plot_page_fits_1080p(self):
        self.window.pages.setCurrentIndex(4)
        panel=self.window.analog_panel
        panel.reset_comparison(True)
        panel.show_mapped(dict(id=7,sticks=[(1,1),(-1,0)],triggers=[.5,1],buttons=['A']))
        panel.show_report(dict(sticks=[(1,1),(-1,0)],triggers=[.5,1],gyro=(0,0,0),accel=(0,0,1),
                               buttons=['A','LB'],reports_per_second=500,remaining=30,
                               circles=[dict(radii={},coverage=0,error_percent=None)]*2))
        for _ in range(3):self.app.processEvents()
        self.assertEqual(panel.mapped_plots[0].point,(1,1))
        self.assertIn('41.4%',panel.mapped_labels[0].text())
        self.assertIn('do not measure USB',panel.mapped_values.text())
        self.assertLessEqual(self.window.minimumSizeHint().height(),1080)
        self.assertLessEqual(self.window.minimumSizeHint().width(),1280)
        for plot in panel.mapped_plots:
            self.assertTrue(plot.isVisible())
        panel.reset_comparison(False)
        self.assertFalse(panel.mapped_plots[0].isVisible())



    def test_pc_macro_library_roundtrip_uses_selected_target_and_never_writes(self):
        import tempfile
        from pathlib import Path
        from test_macro_bank import empty_bank, sample
        from test_profile_controls import profile
        from flydigi_control import macro_library
        editor = self.window.macro_panel; panel = self.window.macro_library
        with tempfile.TemporaryDirectory() as directory:
            panel.folder = Path(directory)
            editor.set_available(True)
            editor.load(dict(mapping=profile(), macros=empty_bank(), profile=0))
            editor.source.setCurrentIndex(19)
            name = macro_library.save_copy(directory, sample(16))
            self.window.open_macro_library()
            self.assertEqual(panel.items.currentData(), name)
            panel.load.setFocus(); self.press(Qt.Key.Key_Return)
            self.assertEqual(editor.macro().key, 19)
            self.assertEqual(editor.macro().actions, sample().actions)
            self.assertEqual(editor.snapshot['macros'], empty_bank())
            self.assertIsNone(self.window.worker)
            self.assertEqual(self.window.pages.currentIndex(), 12)
            self.window.open_macro_library()
            panel.save.click()
            self.assertEqual(len(macro_library.entries(directory)[0]), 2)
            panel.delete.click()
            self.assertEqual(len(macro_library.entries(directory)[0]), 2)
            panel.delete.click()
            self.assertEqual(len(macro_library.entries(directory)[0]), 1)
            for _ in range(3): self.app.processEvents()
            self.assertLessEqual(self.window.minimumSizeHint().height(), 1080)
            panel.back.setFocus(); self.press(Qt.Key.Key_Return)
            self.assertEqual(self.window.pages.currentIndex(), 12)

    def test_pc_library_available_offline_but_busy_and_missing_snapshot_block_loading(self):
        import tempfile
        from pathlib import Path
        from test_macro_bank import sample
        from flydigi_control import macro_library
        panel = self.window.macro_library
        with tempfile.TemporaryDirectory() as directory:
            panel.folder = Path(directory)
            macro_library.save_copy(directory, sample())
            self.window.show_device(); self.window.open_macro_library()
            self.assertTrue(self.window.macro_panel.library.isEnabled())
            self.assertFalse(panel.load.isEnabled())
            self.assertFalse(panel.save.isEnabled())
            self.assertTrue(panel.delete.isEnabled())
            panel.set_busy(True)
            panel.delete_copy(); panel.save_draft(); panel.load_draft()
            self.assertEqual(len(macro_library.entries(directory)[0]), 1)
            self.assertFalse(panel.delete.isEnabled())
            self.assertIsNone(self.window.worker)

    def test_pc_library_rejects_bank_overflow_without_changing_draft(self):
        import tempfile
        from pathlib import Path
        from test_macro_bank import sample, empty_bank
        from test_profile_controls import profile
        from flydigi_control.macro_bank import replace_macro
        from flydigi_control import macro_library
        editor = self.window.macro_panel; panel = self.window.macro_library
        with tempfile.TemporaryDirectory() as directory:
            panel.folder = Path(directory)
            bank = empty_bank()
            for key in range(10): bank = replace_macro(bank, sample(key))
            editor.set_available(True); editor.load(dict(mapping=profile(), macros=bank, profile=0))
            editor.source.setCurrentIndex(18)
            old = editor.macro()
            macro_library.save_copy(directory, sample())
            self.window.open_macro_library(); panel.load.click()
            self.assertEqual(editor.macro(), old)
            self.assertIn('10 macros', panel.result.text())
            self.assertIsNone(self.window.worker)


    def test_import_vendor_macro_creates_only_a_pc_copy(self):
        import tempfile
        from pathlib import Path
        from test_vendor_macro import fixture
        from flydigi_control import macro_library
        panel = self.window.macro_library
        with tempfile.TemporaryDirectory() as directory:
            panel.folder = Path(directory)
            imports = panel.folder/'imports'; imports.mkdir()
            original = imports/'example.dat'; original.write_bytes(fixture())
            (imports/'index.dat').write_bytes(b'not a macro')
            self.window.open_macro_library()
            self.assertEqual(panel.imports.count(), 1)
            panel.import_vendor.setFocus(); self.press(Qt.Key.Key_Return)
            records, errors = macro_library.entries(panel.folder)
            self.assertEqual(len(records), 1); self.assertEqual(errors, [])
            self.assertEqual(records[0][1].name, 'é猫')
            self.assertEqual(original.read_bytes(), fixture())
            self.assertIsNone(self.window.worker)
            self.assertIsNone(self.window.macro_panel.snapshot)
            for _ in range(3): self.app.processEvents()
            self.assertLessEqual(self.window.minimumSizeHint().height(), 1080)
            original.write_bytes(b'bad macro')
            panel.import_vendor.click()
            self.assertEqual(len(macro_library.entries(panel.folder)[0]), 1)


if __name__ == '__main__':
    unittest.main()
