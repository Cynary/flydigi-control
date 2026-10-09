# Validation work

The finished integration must expose all available buttons to Steam Input,
provide lighting controls and a controller-navigable interface in Big Picture,
and test wake from suspend. A passing parser test is not evidence that Steam
sees the physical controls.

| Requirement | Evidence so far | Still needed |
| --- | --- | --- |
| M1–M4, C/Z, LM/RM, Fn, Turbo | Protocol locations match existing implementations; independent-bit parser tests pass | Capture presses from the actual controller, verify firmware and Steam Input mappings, decide Turbo behavior in enhanced mode |
| LEDs | Color command framing and input validation tested | Actual color/brightness/off; acknowledgements; reconnect persistence |
| Steam Input | SDL supports native Flydigi and contains May 2026 transport fix | Detect controller once, verify all mappings, reconnect and rumble |
| Couch app | Runs on K17; offscreen rendering and navigation tests pass | Physical controller-only use, Steam shortcut, test alongside native Flydigi ownership |
| Wake | Probe decodes USB remote-wake flag and ancestor wake settings | Receiver connected, descriptors and power policy, controller-triggered suspend/resume with timed fallback |
| Image | DESTDIR installer ready | Pin validated repository revision in image, build and boot-test |

## Current evidence

2026-10-08: K17 reached over SSH after a magic packet to its verified Ethernet
address. No USB device with Flydigi VID 37d7 was present. The user was asked to
connect the receiver and turn the controller on. No driver or wake configuration
was changed. Steam's bundled 64-bit SDL identifies as
`SDL-release-3.4.0-1359-g70e9cc86d` (version API 3005000).

Twelve automated tests passed on the K17: independent button-bit decoding,
USB identity filtering and wake capability extraction, zero report-ID framing,
invalid command rejection, incomplete writes, acknowledgement filtering,
feature capability/read-back behavior, and UI navigation/disconnected state.
The configuration window was rendered offscreen; no game or stream was started.

## Hardware procedure

1. Capture `--probe` output, USB descriptors, bound drivers, firmware identity,
   Steam controller log and current mappings before changing anything.
2. Confirm whether Steam's existing Flydigi driver can initialize the vendor
   interface. Preserve the current Xbox input path until native input works.
3. Press every standard and extra button separately. Compare raw reports,
   SDL events and Steam Input's input test. Verify releases and simultaneous
   presses; do not infer success from device enumeration.
4. Test LED commands and hardware feature read-back. Keep a backup of settings;
   do not issue reset or firmware commands. Check whether instant-color replies
   exist on this firmware before choosing a no-ack transport path.
5. Test app navigation and rumble while Steam owns the controller. Reconnect the
   controller and receiver; verify that only one controller is exposed.
6. Inspect receiver and ancestor wake support. Enable wake only where applicable;
   suspend with an RTC fallback and record the actual wake source. Test both
   controller power-on and button press; an RTC wake is not a success.
7. Publish and pin the validated code in Moonmachine, build the image and repeat
   input, reconnect and wake checks after booting it.

## References

- [SDL native support fix](https://github.com/libsdl-org/SDL/pull/15594)
- [Kernel driver v5 proposal and Steam limitations](https://patchew.org/linux/20260915171425.11058-1-denis.benato@linux.dev/)
- [Tux InVader protocol and lighting implementation](https://github.com/TJLawInOrbit/tux-invader)
- [Configuration protocol research](https://github.com/rR6kULhc5xgS/flydigi-vader-pro-5-ctl)
- [Linux USB power management](https://www.kernel.org/doc/html/latest/driver-api/usb/power-management.html)
