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

The offline replacement function preserves every other macro's full record.
There is no hardware writer or couch macro editor yet. Commands AD/AE remain
blocked by the configuration transport. Writing a bank, updating a button's
binding and permanently saving need to be verified together before exposing Save.

## Independent checks

The reference harness in `experimental/macro-reference` invokes the actual
Space Station 4.2.0.9 serializer and parser on generated examples. Four cases
(0, 1, 2 and 10 macros) match our encoder byte-for-byte, including cumulative
16-bit timing, repeat intervals, stick directions and non-ASCII names. Only
synthetic byte vectors and our harness are stored here, not vendor binaries.

Tests also cover corrupt offsets, overlapping/duplicate records, limits,
missing or changed macro backups, unrelated HID input, out-of-order packets,
and changes observed after saving. These validate our implementation against
the format; they do not establish device behavior or power-cycle persistence.

Read-only inspection once a receiver is connected:

```sh
python3 -m flydigi_control --macros
```

This reports the active bank and decoded actions. It does not select a different
profile, execute a macro or write settings.
