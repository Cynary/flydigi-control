# Flydigi Control

A controller-friendly configuration app for the Flydigi Vader 5 Pro on Linux.
It is being developed for Moonmachine and can be launched as a non-Steam game
from Big Picture.

**Work in progress.** The interface and protocol tests run on the K17. Physical
lighting, button mapping in Steam, and waking the PC have not been validated yet.
Do not treat this as a finished driver replacement.

The app provides color and brightness controls, plus switches for the controller's
own Turbo function and Fn profile shortcuts. It talks to the configuration HID
interface. Gameplay input stays with Steam Input; this app does not create a
second virtual controller, detach xpad, or change the controller's input mode.

## Run

Requires Python 3.11+, PySide6, and SDL3. Fedora's GUI package is `python3-pyside6`.

```sh
python3 -m flydigi_control
```

Add the installed `flydigi-control` executable as a non-Steam game to launch it
from Big Picture. Use the D-pad or left stick to navigate, A to select and B to
exit. Keyboard navigation also works. The app currently offers temporary solid
colors; controller power-off restores its stored lighting.

Command-line checks:

```sh
python3 -m flydigi_control --probe       # USB identity and wake capability; no commands sent
python3 -m flydigi_control --info        # controller identity and firmware
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
That is the first path being tested for Steam Input support.

The current SDL driver exposes the paddles, C/Z, LM/RM and Fn. It does not expose
the Turbo pulse as a separate button. The kernel driver proposal also describes
Steam ignoring its extra evdev controls, so installing that driver alone would
not meet this project's requirements. See [validation work](docs/VALIDATION.md).

## Turbo and Fn

These are also controller-side functions, described in the
[Flydigi manual](https://shops.flydigi.com/pages/flydigi-user-manual):

- Turbo + a button toggles rapid fire for that button.
- Hold Turbo + an extra button for 1.5 seconds to begin recording a macro; press
  Turbo again to finish. Recording nothing clears that mapping.
- Fn + A/B/X/Y chooses onboard profile 1/2/3/4.

Turbo and profile shortcuts are disabled by default. Their configuration toggles
are separate. How the firmware shortcuts coexist with Steam's enhanced input
mode must be checked on the connected controller.

## Development and image packaging

```sh
python3 -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen python3 -m flydigi_control --screenshot preview.png
python3 packaging/install.py /path/to/image-root
```

The image installer copies the app, desktop entry and a device-specific uaccess
rule. It does not start anything or replace a driver. The runtime also needs
`python3-pyside6` and SDL3. Wake policy will be added after checking the receiver's
USB descriptors and completing a real suspend/wake test.

The new code was written with Codex. Protocol and lighting code is adapted from
Tux InVader; see [THIRD_PARTY.md](THIRD_PARTY.md) and the GPL-3.0 [license](LICENSE).
