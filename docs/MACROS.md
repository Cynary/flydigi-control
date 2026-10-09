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

The separate bank contains 81 packets of 20 bytes. It starts with a 16-bit version
and macro count, followed by ten 16-bit offsets measured in four-byte units from
byte 24. Each macro has a 32-byte header and four bytes per action:

- Activation key, action count, repeat mode, repeat interval and a 20-byte UTF-8 name.
- Reserved header bytes, which our offline editor preserves.
- Cumulative 16-bit millisecond timestamps, a key/direction and an event type.

The official repository limits the bank to ten macros and 256 total actions.
Repeat modes are disabled, once, while held, and toggle. Button press/release and
left/right stick direction events have known encodings. Event 5 (Hold) still
needs investigation before generating it; the reader preserves unknown events.
Our encoder rejects timestamp overflow and overlong names rather than silently
wrapping or cutting a UTF-8 character.

## Candidate editor and save path

Controller settings → Onboard macros opens the controller-operated editor.
Read the active profile, choose an activation button and a repeat mode, then
insert button press/release or stick-direction actions with delays. Actions can
be replaced, removed and reordered. The summary shows the action count and total
duration. Editing a draft sends no commands; Save performs the transaction below.
Names from existing macros are preserved; new macros receive a name based on the
activation button. Renaming, recording live input and deleting an entire macro
are not implemented yet. Disabled mode retains the macro in its bank slot.

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
layout. An offscreen preview was inspected with synthetic macro data.
These validate our implementation against
the format; they do not establish device behavior or power-cycle persistence.

Read-only inspection once a receiver is connected:

```sh
python3 -m flydigi_control --macros
```

This reports the active bank and decoded actions. It does not select a different
profile, execute a macro or write settings.
