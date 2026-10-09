# Vader 5 Pro settings and tests

The target is the Vader 5 Pro settings and tests offered by Space Station, not
just LED control. This inventory is in progress; a source field or a passing
parser test does not establish that the corresponding control works on hardware.

| Area | Current state | Remaining work |
| --- | --- | --- |
| Buttons | All ten extras verified through Steam Input; existing button test | Full analog live view and vendor mapping options |
| Lighting | Colors verified, effect uploads read back | Flow/brightness/off visual checks; onboard persistence power-cycle test |
| Persistence | Guarded candidate saves the active profile after backing it up and checking mappings | Verify off/on, receiver replug and reboot with the app closed; check feature switches individually |
| Grip motors | Separate SDL left/right values; Identify physically confirmed | Individual strength controls and repeatable per-motor tests |
| Trigger motors | Four motor fields identified in official protocol; current SDL trigger callback unsupported | Driver, app controls, simultaneous four-motor test and streaming-path verification |
| Stick output | Read-only profile confirms circle/rectangle fields for each stick | Shape, center deadzone, edge adjustment, response curve and mapping UI; verified writes |
| Stick diagnostics | Protocol and official UI identified | Live XY, circularity error, center/edge tests, original versus mapped output and polling-rate test |
| Triggers | Analog values are decoded | Travel/range controls and tests; enumerate Vader-specific vibration settings |
| Motion | Gyro and acceleration decoded | Official motion mappings/sensitivity/smoothing options; visible sensor tests and streaming verification |
| Profiles | Active profile can be read; Fn shortcut control exists | Profile management, backups/import/export and safe save/restore |
| Macros/Turbo | Extra Turbo button exposed; firmware shortcuts documented | Compare macro editor and firmware feature semantics with the official app |
| Calibration/device tools | Not implemented | Inventory calibration, firmware/receiver and other Vader tools before claiming parity |
| Wake | Receiver does not advertise USB remote wake | No supported method identified; do not claim controller wake works |

## Circle and rectangle

This is a setting in the controller's onboard profile, applied to each stick's
output. Circular output constrains the output boundary to a circle; rectangular
output can reach the corners of the X/Y range. It is separate from a game's or
Steam Input's deadzone settings. The official circularity test measures the
reported stick boundary as the user rotates it; it does not itself change the
controller setting.

The vendor's mapping-format 3.1/3.2 parser places left/right shape at offsets
800/812 (`0` rectangle, `1` circle), next to the response-curve and edge fields.
Both sticks on the tested controller read back as rectangle. No stick settings
have been changed. Unknown mapping formats must be rejected before writes.

## Evidence and scope

Source inspection used Space Station 4.2.0.9, whose installer hash is recorded in
[LIGHTING.md](LIGHTING.md). `FlydigiControllerFactory.GenerateControllerVader5`
advertises grip vibration, trigger vibration, motion, LEDs and analog controls;
it explicitly does not advertise force-feedback triggers or a display. Those
APEX-only controls should not be shown as working Vader features.

`MappingConfigParserV31` defines the stick shape fields. The official renderer's
joystick settings offer circle/rectangle, center, edge and response curves,
plus joystick/keyboard/mouse mappings. Its test page distinguishes original and
mapped output and includes polling rate, circularity and separate grip tests.
Remaining UI pages and model/firmware gates still need a complete audit. Vendor
binaries and decompiled sources are not distributed in this repository.
