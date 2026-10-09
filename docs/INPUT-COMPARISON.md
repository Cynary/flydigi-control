# Native input and mapped output

In **Sticks / motion test**, choose an OS gamepad in the comparison selector,
then start the 60-second test. The two native stick plots appear alongside the
two OS plots. Triggers and button names are also shown for both paths. App
navigation is disabled during the test so moving the sticks does not leave it.

The selector defaults to native reports only. Choose the gamepad that responds
to the Vader; the app cannot infer that an arbitrary Steam virtual controller
belongs to this physical device. It shows each SDL instance ID to distinguish
duplicate names. If the selected device disappears, the comparison reports that
it disconnected. It does not silently switch to another controller. A reconnect
may create a new ID, which must be selected before the next test.

## What the two paths mean

- **Native** is the Flydigi `EF` HID report already used by our input tests and
  Steam's native support. We read it passively without taking ownership or
  changing report modes. This is before Steam's action mapping, but is not proof
  that firmware calibration or filtering has been bypassed.
- **OS** is a standard SDL gamepad obtained through Linux input devices, with
  SDL HIDAPI disabled. If Steam exposes a virtual gamepad for this app, these
  values include that Steam Input mapping. Standard SDL gamepad axes establish
  which values are sticks and triggers; we do not guess based on raw joystick
  axis numbers. Both displays use positive Y for upward movement.

This follows the distinction in Space Station 4.2.0.9: its native path parses
Flydigi reports, while its mapped-input frontend uses `navigator.getGamepads()`.
An OS controller with no known standard SDL mapping is not offered for comparison.

## Measurement limits

The native reader processes each received report; its count is HID reports per
second, not USB poll frequency. OS values are sampled by the UI. Their circularity
plot therefore reports *sampled RMS*, with sector coverage, and may miss points
between samples. Neither path measures input latency or establishes precise
synchronization between a native report and its corresponding mapped event.

The candidate passes tests for selection, disconnection, standard axis conversion,
button names, plot calculations and layout. Its SDL API initialization was checked
on the K17, but no controller was connected for a physical comparison. It is not
yet installed in the released image.
