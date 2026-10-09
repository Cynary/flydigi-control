# Macro storage and editing work

Vader 5's mapping format 3.2 stores macros in a separate bank. The older mapping
block still has a per-button macro marker, but backing up only that block does
not preserve the macro actions themselves.

The candidate now reads the active bank with command AC before saving any
format-3.2 profile, including LED-only changes. The backup includes the complete
bank. It is checked again before writes, before the permanent save, and afterward.
A missing/inconsistent bank prevents saving; a change after save is reported
without replaying the save command. Formats 3.0/3.1 retain their embedded macro
storage and do not issue this newer read command.

This is implemented but has not been exercised on real hardware. The receiver
was absent during development, and no AC reply capture is available yet.

## Bank format

The SDK writes 81 packets of 20 bytes. Vader 5 firmware 7.1.5.0 returns 83
packets when reading the bank. We preserve the extra 40 bytes verbatim and do
not use them as additional macro capacity. Edits, restores and factory defaults
must retain the controller's readback length and those trailing bytes.
The bank starts with a 16-bit version
and macro count, followed by ten 16-bit offsets measured in four-byte units from
byte 24. Each macro has a 32-byte header and four bytes per action:

- Activation key, action count, repeat mode, repeat interval and a 20-byte UTF-8 name.
- Reserved header bytes, which our offline editor preserves.
- Cumulative 16-bit millisecond timestamps, a key/direction and an event type.

The official repository limits the bank to ten macros and 256 total actions.
Repeat modes are disabled, once, while held, and toggle. Button press/release and
left/right stick direction events have known encodings. The official frontend
uses Hold (event 5) only while editing: it expands a hold into press/release
actions before saving. We likewise upload separate presses and releases, and
reject missing or duplicate edges. The reader still preserves unknown events.
Our encoder rejects timestamp overflow and overlong names rather than silently
wrapping or cutting a UTF-8 character.

## Candidate editor and save path

Controller settings → Onboard macros opens the controller-operated editor.
Read the active profile, choose an activation button and a repeat mode, then
insert button press/release or stick-direction actions with delays. Actions can
be replaced, removed and reordered. The summary shows the action count and total
duration. Editing a draft sends no commands; Save performs the transaction below.
Names from existing macros are preserved; new macros receive a name based on the
activation button. Rename opens a controller-operated keyboard. It preserves
existing Unicode names and accepts ASCII letters, digits, spaces and punctuation
within the bank's 20-byte UTF-8 limit. The PC library and file exchange are
described below; an international on-screen keyboard remains future work.

Record 15 seconds listens to native HID input without acquiring the controller,
changing its mode or writing any settings. Release all controls first, so the
button used to start recording is excluded. App navigation stays disabled during
recording. The result replaces the draft's actions; review it before saving.
It captures all 24 remappable button edges and eight-way stick directions. Stick
movement above half travel selects a direction; this is our recorder threshold,
not a change to the controller's deadzone. Timings use local monotonic receipt
times and millisecond deltas. The first action starts at zero.

The recorder reserves room for releases and stick-centering actions. At the
recording/action limit it closes held controls instead of leaving them active.
A disconnect or missing native reports aborts recording without applying it.
Receiver removal also clears the profile snapshot and requires a fresh read.
Fn, Turbo and Home are excluded because they are not onboard macro targets.

Remove saved macro requires confirmation. It restores the selected button's
ordinary output, removes its record and compacts the remaining bank without
rewriting unrelated records. This matches the vendor `UpdateConfig` order:
base mapping first, macro bank second, then permanent save after verification.
Disabled mode instead retains the macro and its bank slot. The official app's
Delete Local Macro operation deletes a PC library file; it does not by itself
remove a macro already applied to a controller.

The replacement function preserves every other macro's full record. The
candidate writer uses AD to select a changed range and AE for its 20-byte chunks,
with indexes relative to that range. It never retries an uncertain write. It
backs up the original bank, verifies the new bank and checks that mappings and
LEDs are unchanged before sending the single A6 permanent-save command. The
whole profile is read back afterward. Unknown bank versions are rejected.

In Space Station 4.2.0.9, `ControllerRepository.ApplyMacroConfig` calls
`ControllerSdk.WriteMacroConfigPartial` for format 3.2. Following this through
the SDK reaches only the AD/AE commands; it does not issue a separate A4/A5
button-map write. The activation button lives in the macro record. Our candidate
follows that path. If firmware changes the base mapping as a side effect,
verification stops before A6 rather than assuming that change is harmless.
A physical test must establish activation and readback behavior before release.

This candidate is not installed on the K17. No macro write or permanent-save
command has been sent to its controller during this work.

## Independent checks

The reference harness in `experimental/macro-reference` invokes the actual
Space Station 4.2.0.9 serializer and parser on generated examples. Four cases
(0, 1, 2 and 10 macros) match our encoder byte-for-byte, including cumulative
16-bit timing, repeat intervals, stick directions and non-ASCII names. Only
synthetic byte vectors and our harness are stored here, not vendor binaries.

Tests also cover corrupt offsets, overlapping/duplicate records, limits,
missing or changed macro backups, unrelated HID input, out-of-order packets,
and changes observed after saving. Transaction tests cover stale editor snapshots,
backup failure, interrupted chunk writes, active-profile changes and preservation
of every unrelated record. The Qt tests cover building/reordering actions,
controller navigation, unknown events, all activation-button defaults and 1080p
layout. Recorder tests cover overlapping presses, shared timestamps, held-control
closure, input/action limits, clock errors and exclusion of firmware shortcuts. An offscreen preview was inspected with synthetic macro data.
These validate our implementation against
the format; they do not establish device behavior or power-cycle persistence.

Read-only inspection once a receiver is connected:

```sh
python3 -m flydigi_control --macros
```

This reports the active bank and decoded actions. It does not select a different
profile, execute a macro or write settings.

## PC macro library

Open **PC macro library** from the macro editor. **Save editor draft as a new PC
copy** stores a complete macro locally; it does not write to the controller.
Choose a saved macro and **Load into the selected button’s draft** to reuse it.
The target is the button already selected in the editor, not the button used
when the PC copy was made. Review the draft and save it to the controller only
when ready. A full controller bank leaves the draft unchanged and reports why
the macro cannot fit.

Each save creates a new copy. To rename or modify a stored macro, load it, edit
it, save a new PC copy, then delete the old copy if wanted. Deleting asks for a
second confirmation and affects only the PC file. The library can be browsed
without a receiver; loading into a controller draft requires reading its active
profile first.

Files live in `~/.local/share/flydigi-control/macros/` (or beneath
`$XDG_DATA_HOME`). Copy a library's `.json` files into this folder on another PC,
then choose **Refresh library** to import them. These are Flydigi Control's
versioned JSON files, not Space Station's file format. Bad or unsupported files
are reported and left untouched. Individual vendor macro files can be imported as described below. Flydigi’s
online sharing service is not integrated.

The loader validates action types, timing, names and paired press/release events;
a loaded macro does not execute on the PC. File names are independent of macro
names, and files are saved with private permissions. Hardware uploads continue
through the existing backup and readback procedure.

### Importing Space Station macros

The candidate imports individual Space Station 4.2.0.9 macro `.dat` files. Copy
these into `~/.local/share/flydigi-control/macros/imports/`, open the PC library,
choose **Refresh library**, select the file and press **Import Space
Station .dat**. This creates a new PC-library JSON copy. The source file and
controller are unchanged. Load the copy into the editor to review and apply it.

Use the individual files from Space Station's `Configs/.../macro/` directory,
not `index.dat`, an entire profile backup, or a share-code string. The candidate
understands the `MacroItem` message stored by the official service. Button
press/release and both sticks' directional actions, repeat mode and repeat delay
are imported. Source activation buttons are rebound when loading into the
selected editor button, including vendor templates with Macro/None activation.

Space Station keeps its library titles in `index.dat`; an individual file may
only carry its optional onboard name. When that name is absent, the copy is named
“Imported macro.” Rename it with the app's keyboard before applying. The importer
does not guess or truncate names exceeding the controller's 20-byte limit.

Unknown fields, incompatible events, malformed data, inconsistent explicit action
counts and unbalanced presses are rejected. The official frontend expands its
editing-only Hold control into press/release actions before saving; a file that
still contains event 5 is rejected rather than assigning an invented duration.
This is local-file import, not access to Flydigi's online sharing service.

The importer was checked against four files generated by the vendor's actual
MacroItem serializer, covering ordinary buttons, button zero (omitted protobuf
default) and Macro/None templates, UTF-8 names and multibyte timings. The fixtures
are synthetic; they contain no vendor executable code or user macros.

### Exporting Space Station macro files

Select a PC-library macro and press **Export PC copy as Space Station .dat**.
The result shows the new file's path in the library's `exports/` subfolder.
Export works without a controller connected. It preserves the saved copy's
button, repeat mode, delay, name and actions; it does not export an unsaved
editor draft. Save a PC copy first if you want to export draft changes.

Every export creates a new file with private permissions. It does not modify
the source macro, Space Station's installation or the controller. The file uses
Space Station 4.2.0.9's individual `MacroItem` format, not a whole profile, library
index or online share code. Importing it into Flydigi Control follows the steps
above. Registration in Space Station's own library UI is not automated or
verified; that library also maintains `index.dat` metadata.

The encoder matches the vendor serializer's reference files. Three additional
exports were decoded with the actual vendor parser and compared field by field:
default-valued fields, maximum timing, both stick/button events, UTF-8 names and
256 actions. This checks file interoperability, not macro execution on hardware.
