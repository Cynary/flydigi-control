# Flydigi Control

A controller-friendly configuration app for the Flydigi Vader 5 Pro on Linux.
It is being developed for Moonmachine and can be launched as a non-Steam game
from Big Picture.

**Work in progress.** All extra buttons have been captured from a Vader 5 Pro,
and the corrected lighting colors have been checked on the controller. Steam
receives all ten extra buttons with the SDL fork, and assigned actions and
reconnect navigation have been checked. Persistence, the remaining animation
checks and the expanded settings are still in development. A recent kernel panic
also keeps the image release on hold. The tested receiver does
not advertise USB remote wake. See [validation](docs/VALIDATION.md).

The app provides color and brightness controls, plus switches for the controller's
own Turbo function and Fn profile shortcuts. It talks to the configuration HID
interface. Gameplay input stays with Steam Input; this app does not create a
second virtual controller or detach xpad. Its Native Steam Input permission
switch lets Steam acquire the extended interface.

The [official-app coverage checklist](docs/FEATURES.md) tracks remaining settings,
independent motor control and diagnostic tests.

The development branch adds a stick-shape editor, a live stick/trigger/motion
test and separate grip/trigger motor tests. These are candidates awaiting hardware
validation; they are not yet included in the published image. It also adds
[global controller settings](docs/HARDWARE-SETTINGS.md) for filtering, automatic
calibration, precision, center sensitivity and sleep, plus an
[onboard button and rapid-fire editor](docs/BUTTON-MAPPINGS.md) and
[gyro-to-stick mapping](docs/MOTION-MAPPING.md).

## Run

Requires Python 3.11+, PySide6, and SDL3. Fedora's GUI package is `python3-pyside6`.

```sh
python3 -m flydigi_control
```

Add the installed `flydigi-control` executable as a non-Steam game to launch it
from Big Picture. Use the D-pad or left stick to navigate, A to select and B to
exit. Keyboard navigation also works. Lighting modes include Steady, Breathing,
Gradient, Flow and Off, with RGB, brightness and cycle controls. The installed release applies temporary lighting. This branch contains an
onboard-saving candidate that backs up the active profile and checks that its
mappings stay intact; controller power-cycle validation is still pending. See
[lighting details and validation](docs/LIGHTING.md).

Command-line checks:

```sh
python3 -m flydigi_control --probe       # USB identity and wake capability; no commands sent
python3 -m flydigi_control --info        # controller identity and firmware
python3 -m flydigi_control --hardware-settings  # global settings; read only
python3 -m flydigi_control --features    # current Turbo and Fn profile shortcut settings
python3 -m flydigi_control --monitor 60  # passive button capture while Steam owns native input
python3 -m flydigi_control --color '#0080ff'
python3 -m flydigi_control --turbo on
python3 -m flydigi_control --profile-hotkeys on
```

With more than one receiver, choose a `--device` from the probe output. Settings
writes check firmware support and read the state back. The app does not flash
firmware or reset the controller. Lighting and feature commands still need a
hardware validation run before release.

## Extra buttons and Steam

The Xbox-compatible USB interface only carries the usual Xbox controls. The
vendor interface carries M1–M4, C/Z, LM/RM, Fn, Turbo and motion data. SDL has a
native Flydigi driver, including a Vader 5 Pro transport fix merged in May 2026.
That is the input path used here.

Steam’s bundled SDL driver exposes the paddles, C/Z, LM/RM and Fn. Our
[SDL fork](https://github.com/Cynary/SDL/tree/vader5-turbo) adds Turbo as a
separate button. The parser passes captured-report replay tests, and Steam
receives physical Turbo press and release events. All ten extra-button bindings have been verified through a Steam Input action test. The kernel driver proposal also describes
Steam ignoring its extra evdev controls, so installing that driver alone would
not meet this project's requirements. See [validation work](docs/VALIDATION.md).

## Turbo and Fn

These are also controller-side functions, described in the
[Flydigi manual](https://shops.flydigi.com/pages/flydigi-user-manual):

- Turbo + a button toggles rapid fire for that button.
- Hold Turbo + an extra button for 1.5 seconds to begin recording a macro; press
  Turbo again to finish. Recording nothing clears that mapping.
- Fn + A/B/X/Y chooses onboard profile 1/2/3/4.

Turbo and profile shortcuts were disabled on the tested controller. Their
configuration toggles are separate. With both off, Fn and Turbo still send
independent button reports for Steam to map. Turbo sends a short pulse (about
50 ms in the capture), rather than reporting how long you hold it. Fn reports
press and release normally. Firmware shortcuts with native Steam Input enabled
still need testing.

## Development and image packaging

```sh
python3 -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen python3 -m flydigi_control --screenshot preview.png
python3 packaging/install.py /path/to/image-root
```

The image installer copies the app, desktop entry and a device-specific uaccess
rule. It does not start anything or replace a driver. The runtime also needs
`python3-pyside6` and SDL3. The Moonmachine candidate also packages the matching
Steam SDL fork and has been built and boot-tested; remaining hardware checks
are listed in [validation](docs/VALIDATION.md).

The tested wireless receiver does not advertise USB remote wake, and Linux exposes
no device-level wake control. Keeping its USB port powered does not supply that
missing capability. No controller-wake method is established, so the image does
not install a wake quirk or change USB power policies.

The new code was written with Codex. Protocol and lighting code is adapted from
Tux InVader; see [THIRD_PARTY.md](THIRD_PARTY.md) and the GPL-3.0 [license](LICENSE).

### Enable the extended input interface

Under **Controller settings**, read the current settings, then enable
**Native Steam Input**. This is Flydigi's permission for Steam to take over
mapping; it leaves the reporting flags alone. With the patched Linux SDL, Steam
switches between native and Xbox-compatible input without restarting. Earlier
Steam drivers may need a restart. While Steam owns the controller, its mappings take
precedence over the controller's onboard profiles.

The command-line equivalent is `python3 -m flydigi_control --native-input on`.
Use `--mapping-status` to read the permission and current owner.
Native detection has been checked on firmware 7.1.5.0; complete Steam button
mapping and physical reconnects are still being validated. The fork fixes the
duplicate Xbox entry and stale held buttons during native-mode transitions.

For the supported lighting modes, official presets and current implementation gaps, see [Lighting](docs/LIGHTING.md). Use **Test buttons** when checking extra buttons: navigation is disabled during recording.
