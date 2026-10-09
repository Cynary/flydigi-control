# Onboard motion mapping

The development app's **Motion mapping** page edits the controller's gyro-to-stick
settings. The choices are Off, Left stick for racing, and Right stick for aiming.
An activation button can toggle the mapping or enable it while held. Hold mode
also offers a second activation button. The exact two-button behavior still
needs physical validation.

Sensitivity and stick deadzone compensation range from 0 to 100, matching the
official app. Deadzone compensation helps the generated stick output get past
a game's deadzone; it is not the raw gyro's filtering threshold. Space Station
warns that enabling motion mapping lowers the controller's report rate. We have
not measured that effect on this firmware yet.

These settings are separate from Steam Input's gyro bindings and the raw gyro
and accelerometer reports in our analog test. Steam can bypass onboard mappings
while it owns the controller's native interface. Both paths need testing before
claiming that an onboard change affects a Steam game.

## What is stored

In mapping formats 3.0–3.2, bytes 137–144 contain output type, first activation
button, activation mode, deadzone compensation, X/Y sensitivity, use mode, and
second activation button. Space Station selects Racing use mode with left-stick
output and FPS use mode with right-stick output.

The vendor reads sensitivity as the larger of X and Y, then writes one setting
to both axes. The recorded 7.1.5.0 profile contains **25 and 20**. Our editor
preserves that difference unless sensitivity itself is edited. Turning motion
mapping off changes only its output-type byte and keeps the previous setup.
Switching to toggle activation preserves the unused second-button field.

Formats 3.1/3.2 also hold six response/smoothing bytes at 830–835. This version of
the official app hides its smoothing controls. We preserve those bytes rather
than inventing a curve or changing them when another motion setting is saved.
The separate global motion-filtering switch is covered in
[hardware settings](HARDWARE-SETTINGS.md).

## Mouse mode

The official app offers mouse output, but its SDK does not store the mouse
sensitivity and activation settings in the onboard block. Its Windows service
restores those from PC files and injects keyboard/mouse input. A profile already
set to mouse output is therefore read-only in this candidate. The Linux mouse
path remains to be implemented; storing output type 3 alone would not reproduce
that feature.

## Verification

The layouts and choices were checked against `MappingConfigParserV30/V31`, the
motion enums, and the motion page of Space Station 4.2.0.9. Tests use the recorded
read-only profile to check axis preservation, output/use-mode changes, activation
buttons, invalid values and the guarded profile save. Unknown data is not
silently clamped. The complete profile and lighting are backed up and checked
before and after the onboard-save command.

No motion settings have been written to hardware. Remaining physical checks:

- Confirm off/left/right output, activation modes and the second-button behavior.
- Check sensitivity and compensation across their range, with a way to restore
  the original profile if controls become difficult to use.
- Measure native report rate with mapping off/on, and compare Steam's native and
  Xbox-compatible input paths.
- Close the app and verify the saved values after controller off/on, receiver
  replug and PC restart.
