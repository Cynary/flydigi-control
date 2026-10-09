# Validation work

The finished integration must expose all available buttons to Steam Input,
provide lighting controls and a controller-navigable interface in Big Picture,
and test wake from suspend. A passing parser test is not evidence that Steam
sees the physical controls.

| Requirement | Evidence so far | Still needed |
| --- | --- | --- |
| M1–M4, C/Z, LM/RM, Fn, Turbo | All ten captured from hardware; patched parser agrees. Steam events confirm M1–M4, C/Z, Fn and Turbo | LM/RM Steam events and an assigned-action test; Turbo reports a short pulse rather than a held state |
| LEDs | Steady, breathing and gradient configurations pass complete readback; user confirmed corrected colors | Visual animation and brightness/off checks |
| Steam Input | All ten extra controls accept bindings in Steam's editor. Native/fallback transitions expose one controller and release stale button state | Physical binding delivery and controller reconnect |
| Couch app | Installed image app launches through its Steam shortcut; user operated the color picker and button test; automated navigation checks pass | Controller-only reconnect/navigation check; navigation polish remains |
| Wake | Receiver `37d7:2401` reports `bmAttributes=0x80`, without remote wake; Linux has no device wake control | No supported controller-wake method found; no wake policy is installed |
| Image | Full candidate built and booted; Steam maps its packaged SDL with no local library override | Remaining physical checks before promoting the public update channel |

Lighting changes are deliberately temporary: controller power-off restores its
stored lighting. Persistence is not implemented through a firmware flash write.

The booted candidate and exact source revisions are recorded in Moonmachine's
[Flydigi integration notes](https://github.com/Cynary/bazzite-k17/blob/flydigi-integration/docs/FLYDIGI.md).
The sections below preserve the individual experiments; earlier pending checks
are superseded by this table and the later results.

## Current evidence

2026-10-08: K17 reached over SSH after a magic packet to its verified Ethernet
address. No USB device with Flydigi VID 37d7 was present. The user was asked to
connect the receiver and turn the controller on. No driver or wake configuration
was changed. Steam's bundled 64-bit SDL identifies as
`SDL-release-3.4.0-1359-g70e9cc86d` (version API 3005000).

Eighteen automated tests passed on the K17: independent button-bit decoding,
USB identity filtering and wake capability extraction, zero report-ID framing,
invalid command rejection, incomplete writes, acknowledgement filtering,
feature capability/read-back behavior, and UI navigation/disconnected state.
The configuration window was rendered offscreen; no game or stream was started.

The recorded firmware 7.1.4.0 wireless identity reply does not use the wired
additive-checksum convention. Reply matching now checks framing and command;
the trailer comparison is diagnostic only. A regression test uses the public
wireless capture. This does not establish support for every firmware version.

The vendor SDK has no acknowledgement handler for the instant-color command
(`0xF5`), and Tux InVader sends it without waiting for a reply. The app now does
the same after verifying controller identity. It reports “command sent,” not
“applied”; the LED result still needs a physical check. A regression test verifies
that the command does not wait for an acknowledgement.

## Hardware procedure

1. Capture `--probe` output, USB descriptors, bound drivers, firmware identity,
   Steam controller log and current mappings before changing anything.
2. Confirm whether Steam's existing Flydigi driver can initialize the vendor
   interface. Preserve the current Xbox input path until native input works.
3. Press every standard and extra button separately. Compare raw reports,
   SDL events and Steam Input's input test. Verify releases and simultaneous
   presses; do not infer success from device enumeration.
4. Test LED commands and hardware feature read-back. Keep a backup of settings;
   do not issue reset or firmware commands. Instant color is sent without waiting for an acknowledgement; verify the
   visible result because a successful USB write cannot prove it.
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

## First receiver check

Firmware 7.1.5.0 identified successfully over the wireless configuration
interface. Turbo and Fn profile shortcuts were supported but disabled.
The native mapping permission was also disabled: command 0x10 returned byte 9
as zero, which makes SDL reject the native interface. After enabling that flag
with command 0x11 (leaving the four reporting flags unchanged), read-back showed
it enabled and a fresh probe using Steam's bundled SDL detected the native
Vader 5 Pro. The same probe also detected the generic Xbox interface; duplication
and physical button mapping are not yet validated.

The receiver's USB configuration has `bmAttributes=0x80`, without remote wake,
and no device-level `power/wakeup` control. Controller-triggered USB wake is not
established. Changing the parent hub policy alone is not evidence of support.

Consecutive identical read queries received no reply, including after pauses
of 20, 60, 150, 300 and 600 ms. Alternating identity, feature and mapping queries
received replies in about 20–22 ms. The transport now makes one bounded retry
following an alternate read-only query. It never retries setting writes.
One initial trial also lost the alternate query's reply; that no longer prevents
checking the requested query again. All 18 queries in the subsequent hardware
run succeeded, including nine deliberate repeats. Most repeats took about
546 ms; one took 1026 ms. This is evidence for query recovery, not a claim that
wireless communication cannot fail. No reset or firmware update was performed.

## Steam and library check

After setting native mapping permission, restarting Steam activated the native
HIDAPI path. A comparison restart without `SDL_JOYSTICK_HIDAPI_FLYDIGI` also
activated it, so no environment override or replacement SDL library is required
by this test. Steam's current controller list contained one controller of type
30, and its mapping exposed paddles 1–4 plus misc2–misc6 (C/Z, LM/RM, Fn).
The firmware status reported owner `SDL`, raw reports enabled and Xbox reports
disabled. Physical presses and reconnect behavior remain to be checked.

The configuration app was installed in the test user's application directory,
added through Steam's shortcut API and launched through Steam. Steam's process
log tracks its Python process as the shortcut. Controller-only navigation and
visible LED results still need user verification.

## 2026-10-08: official lighting app and safe button testing

Inspected the official Space Station 4.2.0.9 Electron UI and .NET service. See
[Lighting](LIGHTING.md) for exact presets, supported modes, evidence and gaps.
On firmware 7.1.5.0, steady, breathing and gradient configurations passed exact
hardware readback, including repeated uploads. The active profile reports 10
zones / 10 frames. One LED chunk acknowledgement was lost despite its data
arriving; indexed retries are bounded, and UI uploads verify the complete result.

The native-mapping permission was found disabled after a settings-page button
test, with no USB disconnect. A paddle mapped to activation is a plausible cause,
not a proven one. A dedicated 60-second test page now suppresses navigation and
setting changes while collecting reports. Native permission was restored and
Steam restarted; Steam reports the native controller style and extra-button
capabilities again. Physical validation of every extra button remains pending.

All 23 unit/UI tests pass on the K17. An offscreen screenshot was inspected for
clipped controls. Visual color/animation confirmation is still pending.


## Complete physical button capture, 2026-10-08

A 60-second passive test received 27,339 reports and observed all 27 named
button states, including M1–M4, C/Z, LM/RM, Fn, Turbo and the digital trigger
thresholds. No button was missing. The 184 button-change reports replayed
successfully through the patched SDL V2 parser. This proves the reports and
parser agree; it does not yet prove the Steam binding UI exposes Turbo.

The app's current RGB/multicolor editor passes 26 tests on the K17. The app is
installed and launched from its Steam shortcut. The user confirmed the corrected color looks better and that the test screen
recognized every button. Flow animation still needs visual confirmation. LED uploads keep backups and
verify the complete controller readback.

## Steam physical events, 2026-10-08

Recorded Steam's own controller-state notification feed alongside the app's
second passive 60-second test (27,478 reports). The Steam capture has 102 state
updates. Matching isolated presses confirm these inputs and their releases:

| Physical button | Steam state |
| --- | --- |
| M1 | R5, bit 42 |
| M2 | L5, bit 41 |
| M3 | R4, bit 16 |
| M4 | L4, bit 15 |
| C | Bit 32 |
| Z | Bit 33 |
| Fn | Bit 36 |
| Turbo | Capture/misc, bit 29 |

The paddle labels above are Steam's labels, not the controller's printed labels.
C, Z and Fn are present in the complete button bitfield even though this Steam
notification does not provide named Boolean fields for them. Turbo produces the
named `button_mute_capture` event. This verifies the patched driver is supplying
physical Turbo presses to Steam, beyond just advertising a mapping.

LM and RM were absent from both recordings in this particular run. Both were
present in the first raw capture, but their Steam events still need confirmation.
A Steam binding that triggers an application action is a separate remaining check.


## Native/fallback handoff and image boot

SDL kept the Xbox interface visible when native mode took over, even though the
receiver stopped sending Xbox reports. Steam retained a held A state in that
entry alongside the native controller. The Linux fix removes the fallback with
SDL's normal button-release/recentering path and rediscovers it when native
permission is disabled. Live permission off/on checks showed one controller in
each mode, with no Steam restart. This does not replace a physical reconnect test.

The SDL fork includes the actual Linux reconciliation function's regression
harness and the 12,289-case button parser replay. The full image passed these,
28 app tests, the existing Gamescope/setup checks and bootc validation, then booted
successfully. Steam mapped the image's replacement SDL and launched the image
app through its shortcut; temporary test library overrides were removed.

The controller was off after the final reboot. Steam capture is prepared for its
next connection. LM/RM events, assigned-action delivery and physical reconnection
remain unverified; the image is a candidate, not a public-channel release.


## App hotplug and missing native reports

The next physical run found that a controller turned on after app launch could
navigate Steam but not the app. The app called `SDL_UpdateJoysticks` without
pumping SDL events; udev hotplug processing needs the event pump. The Qt timer
now pumps and drains SDL events before discovering joystick handles. A regression
test covers initial absence, connection, disconnection and a new device ID.

That run also produced zero raw reports because Steam had only acquired the Xbox
fallback. The button test now reports this after three seconds instead of waiting
silently for a minute. It does not claim the interface or change input settings.
The app suite passes all 30 tests on K17, including Qt UI tests. Physical hotplug
validation is pending alongside the SDL startup recovery candidate.
