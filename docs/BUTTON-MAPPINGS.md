# Onboard button mappings

The development app has an **Onboard button mappings** page under Controller
settings. It edits the active profile stored in the controller. Steam Input
bindings are separate: Steam can bypass onboard mappings while it owns the
native interface, so these edits are not a replacement for Steam's editor.

Read the active profile, select a physical button, and choose its output. The
candidate supports ordinary button remapping and rapid fire with three modes:
Off, While held, and Press to start / press to stop. The rate is 1–30 presses per
second, matching the official app's range. Nothing is written until Save.

The 24 editable controls are the D-pad directions, A/B/X/Y, View/Menu, LB/RB,
LT/RT, stick clicks, C/Z, M1–M4 and LM/RM. Fn, Turbo and Home are not editable in
the official app's onboard mapping page. They remain available to our Steam
Input driver; their firmware shortcuts have separate controls in this app.

## Save behavior

Saving backs up the entire active profile and lighting, rejects a stale read or
changed profile, then edits only the selected three-byte button record. Complete
readback must pass before the single onboard-save command is sent. The resulting
profile version and contents are checked afterward. No other button, macro,
lighting or analog setting is rebuilt from defaults.

A selected record containing a macro, PC keyboard/mouse mapping, or an unknown
format is currently read-only. Supporting those editors is still required;
rewriting their marker without handling their other data would be incomplete.

The current candidate has not changed a hardware mapping. Save, actual button
output and persistence across off/on, receiver replug and PC restart still need
hardware validation, including with native Steam Input both enabled and disabled.

## Format and evidence

Space Station 4.2.0.9's `MappingConfigParserV30` reads and writes 32 three-byte
records starting at byte 13. The same base records are used by formats 3.1 and
3.2. `ControllerKey` supplies the key numbers; the Vader 5 device definition
marks keys 0–23 editable. Its M5/M6 names correspond to this model's LM/RM.

An ordinary mapping stores the target key, zero, zero. Target 255 means the
source key itself; it does **not** disable a button. Rapid fire stores target,
activation (0 Off, 1 Hold, 2 Toggle), and nonzero frequency. Marker 32 denotes a
macro, while 254 denotes a keyboard/mouse or multifunction mapping. Those require
separate handling and are preserved by this editor.

The Windows app merges keyboard/mouse mapping details from its PC files and
uses `KeyboardMouseInjectRunner` to supply keyboard/mouse input. An onboard
marker alone cannot reproduce that behavior on Linux. A Linux implementation
will need either equivalent local processing or an explicit Steam Input mapping;
that choice has not been implemented here.

Tests cover every source/target pair in all three supported profile formats,
rapid-fire transitions, preservation of all other bytes, unsupported records,
and the complete backup/write/readback/save transaction. Offscreen UI tests
cover controller navigation, disconnected state and the 1080p layout. The page
was rendered using the saved read-only hardware profile; no writes were sent.
