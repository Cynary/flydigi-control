# Vader 5 Pro lighting

We inspected Flydigi Space Station 4.2.0.9 from its [official download page](https://shops.flydigi.com/pages/game-center). The installer was extracted, without installing the app or its drivers. The Electron interface and the .NET service were inspected separately. These notes describe interoperability findings; vendor binaries and decompiled sources are not included in this repository.

## What Flydigi's app offers

For the Vader 5 Pro (`f5`), the service offers Default, Flow, Breathing, Gradient, Steady and Off. Button-feedback lighting appears in the shared interface, but the service offers it only for the Vader 4 (`f4`). The grip-vibration lighting switch is visible only for the APEX 5 (`k5`). Neither should be advertised as a Vader 5 feature.

The color picker has these six shortcuts, plus a color wheel, RGB fields and a hex field:

| Color | RGB | Hex |
|---|---|---|
| Red | 255, 0, 0 | `#ff0000` |
| Yellow | 255, 255, 0 | `#ffff00` |
| Green | 0, 255, 0 | `#00ff00` |
| Cyan | 0, 255, 255 | `#00ffff` |
| Blue | 0, 0, 255 | `#0000ff` |
| Magenta | 255, 0, 255 | `#ff00ff` |

Breathing allows one to five colors; gradient requires two to five. Brightness is independent of RGB. Cycle time controls animation speed; a smaller value is faster.

The Vader-specific defaults are:

| Mode | Colors | Brightness | Period value |
|---|---|---|---|
| Steady | orange `(255, 80, 5)` | 30% | 1 |
| Breathing | orange `(255, 80, 5)` | 50% | 15 |
| Gradient | `(0, 0, 100)`, `(100, 0, 0)`, `(0, 100, 0)` | 50% | 15 |
| Flow / Default | animation data | 20% | 4 |

The prototype's earlier “Purple” preset was `(160, 120, 255)`, scaled to `(80, 60, 128)` at 50% brightness. Hardware readback confirmed those exact bytes. That pale color was our preset choice, not evidence of reversed RGB channels. The picker now uses Flydigi's saturated shortcuts.

## Implementation and validation

The temporary `F5` color override has been replaced in the UI by the normal lighting upload (`A8`/`A9`). It preserves the active profile's format and LED count, keeps RGB channels separate from brightness, and reads the entire configuration back after applying it. Only the active profile is read because reading a different profile can select it.

The tested wireless controller, firmware 7.1.5.0, reports **10 LED zones and 10 animation frames**, a 320-byte version-3 configuration. Do not hardcode 12 zones from the service's generic animation table. Reading hardware geometry avoids that mismatch.

Steady, breathing and gradient uploads passed byte-for-byte readback on hardware. Visual animation and color checks remain necessary. The candidate UI offers those modes, Off, Flow, Default, the six color shortcuts, RGB sliders and up to five colors for Breathing and Gradient. Hex values are displayed alongside each color.

Flow uses the numeric frames from the service’s generic preset, cropped to the LED count reported by the controller. It sets the loop end to the last valid frame. This adaptation still needs a physical animation check; it is not a claim of identical factory lighting.

### Default lighting

Default uses the animation from Space Station 4.2.0.9's
`Configs/Controller/f5/default/default_mapping_130.dat`. Profile 1 has its own
animation; profiles 2–4 use the first ten LED zones of the Flow preset. All four
have ten frames, a loop from 0 through 9, mode 7, 20% brightness and period 4.
The editor lets you change brightness and speed while keeping the preset colors.

This changes only lighting in the active profile. It does not restore factory
button mappings, calibration or other settings. We preserve the existing grip-sync
and reserved fields; the vendor files differ in grip-sync between profiles, which
is separate from the Default animation. Other device IDs or LED geometries are
rejected rather than receiving the Vader 5 preset.

The [reference harness](../experimental/lighting-reference/README.md) reads all four
profiles with Flydigi's own protobuf parser and lighting serializer. Our animation
bytes match each serialized result. The tests also check that a profile change
stops Apply before any write. Physical appearance and power-cycle persistence
still need a controller test; the new option is not installed yet.

Each UI upload first saves a backup beneath `~/.local/state/flydigi-control/`. The persistence candidate also backs up the complete active mapping profile and sends one onboard-save command after verifying that the lighting changed and the mappings did not. This candidate is not yet installed or validated across controller power-off. Missing acknowledgements for indexed LED chunks are retried once after a read-only query, followed by whole-configuration verification. A missing acknowledgement is not itself proof that a write failed.

## Settings persistence

The installed application uploads working settings but does not save them onboard. The candidate in this branch implements guarded onboard saving.
The user reported that reconnecting the Vader loses the newly applied lighting
and restores the previously stored settings.
Saving the last successfully applied settings is required before release, including
color, brightness, animation and speed. Turbo, Fn shortcuts and native-mapping
permission need their own off/on checks rather than assuming they share the LED
persistence mechanism.

Inspection of Space Station 4.2.0.9 found an onboard-save operation:
`ControllerRepository.SaveConfig` calls `PermanentSaveMappingConfig` with a new
16-bit version identifier. The SDK's NewXInput save command is `0xA6`, carrying
that identifier little-endian. The service generates a different identifier from
the current profile's version. This saves the active configuration; it is not
an LED-only save command. No such command has been sent in our hardware tests.

Prefer onboard persistence if testing confirms that saving leaves all unrelated
mapping and calibration settings intact. Back up the active configuration first,
verify the lighting upload, save once after an explicit Apply, then check an
off/on cycle with the app closed. Do not repeatedly write onboard storage during
reconnection or slider movement. Acknowledgment and immediate readback alone do
not prove that settings survive power loss.

If onboard saving cannot safely preserve the rest of the profile, use PC-side
storage and a reconnect helper that runs without the UI. It must remember only
successful changes, distinguish controllers and profiles, bound retries, and avoid
changing Steam's ownership or input mode during lighting restoration. Settings
changed on another computer should not be silently overwritten by an old local
copy.

The kernel-panic investigation is still open; no persistence commands or
reconnect service have been deployed. A read-only hardware check on firmware
7.1.5.0 returned the expected 840-byte mapping format 3.2 and matching profile
versions. The candidate tests cover backup failure, changes to mappings or the
active profile, lost acknowledgments, unsupported formats and readback failures.
A lost save acknowledgment is checked through the profile version without
replaying the write. Successful readback is not power-cycle validation.

### Checking persistence without restoring anything

After applying and saving the settings to test, close the configuration app and
take a baseline from the candidate checkout:

```sh
python3 -m flydigi_control.persistence_check snapshot ~/.local/state/flydigi-control/persistence-tests
```

The command prints the path of a private JSON file. Turn the controller fully
off and back on, then compare against that file:

```sh
python3 -m flydigi_control.persistence_check check /path/printed/by/the/first/command.json
```

Repeat the check after unplugging/reconnecting the receiver and after restarting
the PC. Leave the app closed during these checks: otherwise a future restore
helper could hide that the controller lost its onboard settings. The temporary
`--color` command is not an onboard save and should not be used to prepare this
test.

The check reads the active profile's complete mapping, lighting and macro bank,
the profile versions, global setting values and native-mapping permission. It
reads them twice to reject changing state. Differences include byte offsets for
the profile data. It does not send save, restore, mode-change or reset commands.
Exit status is 0 for a match, 1 for differences and 2 for an incomplete check.

Battery level and Steam's current ownership are excluded. Use the same physical
controller, firmware, connection type and active profile: the identity reply
does not contain a unique serial number. This checks stored data, not whether
every setting has the intended physical effect. A match only establishes
persistence if the stated off/on, replug or reboot actually took place.

## Evidence locations

Installer SHA-256: `736070b18d99ef77b0eb4622fb670613cf86b6fcc1bcded923a4bae8dfdc373a`.

Within `resources/app.asar`, `.vite/renderer/main_window/assets/index-DM6mSbRo.js` contains the controller lighting page and saturated picker shortcuts. Its `getConfigLedResult` response determines the available modes. `SpaceStationService.dll` contains `Flydigi.ControllerService.data.mapper.ControllerDataMapper`: `GetDefaultLedConfigsByDevice`, `GetDefaultColor`, `GetDefaultBrightness`, `GetDefaultPeriod` and `ConvertLedConfigToBean` establish the model-specific behavior and serialization.

Research and implementation were performed with Codex. Readback tests verify configuration transfer, not visual LED calibration or every firmware version.
