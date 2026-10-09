# Global controller settings

The development app has a **Global controller settings** page under Controller
settings. Read the controller, choose a setting and a value, then press Apply.
Changing the selection alone does not send a command. These settings are global;
they are separate from the active profile's response curves and deadzones.

| Setting | Choices |
| --- | --- |
| Fn profile shortcuts | Off / On |
| Home button output | Off / On; disabling it may prevent opening Steam's menu |
| Motion filtering | Off / On |
| Stick filtering | Off / On |
| Automatic stick calibration | Off / On; this does not start manual calibration |
| Stick rebound suppression | Off / On |
| Turbo shortcuts | Off / On |
| Stick precision | 8, 9, 10, 11 or 12 bit |
| Stick center sensitivity | Fast, Medium, Slow |
| Controller sleep | 1, 5, 15, 60 or 180 minutes, or Never |

Unsupported settings remain disabled. Unknown current values are displayed
without replacing them with a default. The firmware implements the filtering;
its behavior and effect on native Steam Input still need hardware measurements.
The controller sleep timer neither changes the PC's timer nor enables USB wake.

## Writes and persistence

Each Apply verifies the controller identity and rereads the global settings.
If they changed since the page was loaded, it asks for a fresh read. Before
writing, it saves the identity, original reply and requested change in a private
backup file under `~/.local/state/flydigi-control/`.

The app sends one command and compares all documented global fields afterward.
A missing acknowledgment is resolved by readback, never by repeating the write.
An unexpected change is reported without automatically writing more settings.
A failed operation invalidates the editor's snapshot until the next read.

The official app uses these global commands directly. It does **not** follow
them with the A6 command used to save a mapping/lighting profile. Whether each
global setting survives power-off remains a hardware validation item. The app
currently does not reapply these settings on reconnect or promise persistence
based solely on a successful readback.

## Protocol evidence

Layouts were checked against Space Station 4.2.0.9's NewXInput command factories,
its shared enums, and the settings page in `index-BDdWMsEd.js`. The installer
hash is recorded in [LIGHTING.md](LIGHTING.md). Vendor binaries and decompiled
source are not included in this repository.

For command 03's reply, byte 5 advertises supported features and byte 6 holds
their current states. Bits 0–6 are Fn shortcuts, Home output, motion filtering,
Turbo shortcuts, stick filtering, automatic calibration and rebound suppression.
Command 13 uses subcommands 1–7 in that same order, followed by 0 or 1.

Bytes 9–12 hold sleep minutes, report-rate code, precision and center sensitivity.
Commands 17, 15 and 16 change sleep, precision and sensitivity respectively
(command numbers here are hexadecimal). Precision codes 1/2/3/4/5 represent
8/10/12/9/11 bit. The UI's Fast/Medium/Slow values are 14/17/19.

### Report rate is not offered for Vader 5

The SDK enum maps 1/2/4/8 to 1000/500/250/125 Hz, but the official UI sends
1/2/3/4 for those labels and only shows that control for Vader 4 (`f4`). We do not
send command 14 to Vader 5 or claim its raw code measures the actual input rate.
Tracing the settings event through Electron IPC, the Windows service and the
SDK command factory confirmed that the value is forwarded unchanged: there is
no hidden conversion that reconciles the labels. This is not a missing Vader 5
control from the official settings page.
The passive analog test separately counts received native reports per second.

## Validation status

The global-settings checks include field preservation, exact
packet framing, unsupported/unknown values, stale snapshots, backup failure,
missing acknowledgments, controller navigation and the 1080p page layout. The
page was visually inspected offscreen with simulated status data.

The [command reference harness](../experimental/settings-reference/README.md)
uses the actual vendor SDK to generate all 28 supported setting/value pairs.
Every command body, including length and checksum, matches our encoder. The
fixture coverage test also rejects a new UI choice without a corresponding
reference case. These checks run without hardware; they do not validate the
firmware’s behavior or onboard persistence.

No new global-setting command has been sent to hardware and this candidate is
not installed in the running image. To validate each supported setting:

1. Read and record the current value. Apply one change and check its effect.
2. Close the app, turn the controller off/on and read again.
3. Repeat across receiver replug and PC restart, with the app closed.
4. Restore the original value and verify it. Check Steam navigation throughout.

Read-only command-line capture:

```sh
python3 -m flydigi_control --hardware-settings
```
