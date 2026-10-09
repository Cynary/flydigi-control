# Stick shape and response

Circle and Rectangle change the boundary of the controller's stick output.
Circle limits diagonal travel to the circular boundary; Rectangle can reach
the corners. This setting is separate from response sensitivity and deadzones.

The response editor offers the official app's Default, Quick, Slow and Custom
curves. Quick produces more output early in the stick's travel; Slow produces
less. Custom has two movable control points. Positive center adjustment creates
a deadzone; positive edge adjustment reaches full output before full travel.
Negative center compensation starts above zero to counter a game's deadzone,
and negative edge compensation limits maximum output. Those negative values can
be previewed, but cannot yet be saved with this candidate.

The graph compares the proposed samples with those stored in the active profile.
Opening the editor proposes a new Default curve, with zero center/edge adjustment;
it does not silently reconstruct and rewrite an existing curve. Only Save writes
to the selected stick. Shape, the other stick, lighting and unrelated profile
bytes are preserved. Steam Input can process the resulting input further, and
native controller ownership may bypass onboard mappings; this interaction still
needs a physical comparison.

## Format and evidence

Source inspection used Space Station 4.2.0.9. The source/install provenance is in
[LIGHTING.md](LIGHTING.md). The settings frontend offers Default `(64,64)`, Quick
`(64,96)` and Slow `(64,32)`, with a second control point at `(127,127)`. Choosing
a preset resets center and edge adjustment. Control point coordinates use 0–127.

For mapping format 3.1/3.2, each stick has base fields starting at 109/116 and
additional fields at 790/802. The firmware receives nine samples at input
positions 0, 12.5, …, 100, stored with an offset of 50. Negative sampled values
can describe extrapolation into a deadzone, even with nonnegative deadzone
settings. Both curve type fields are updated together. Shape and unrelated
bytes are left intact.

The implementation's samples match 12 numeric reference cases obtained by
executing the official frontend's sampling function. The test vectors cover
presets, deadzones, compensation, vertical segments, endpoint saturation and
non-monotonic curves. They establish serialization/preview agreement, not the
physical stick response. No proprietary source is included here.

There is an unresolved SDK inconsistency for negative center/edge values:
the writer casts the signed value to a byte, while the reader decodes bytes
above 127 as `127 - value`. For example, writing −10 produces 246, which that
reader interprets as −119. An offline harness now confirms this with the actual SDK writer and reader,
not just decompiled code. All 36 generated cases are saved in the test fixtures.
For center −10, the writer also transforms the first X control point using the
wrapped value 246, producing 218 instead of a coordinate in 0–127. Positive
cases match our field writer. The repository passes values through without
an intervening conversion; see `experimental/curve-reference` for reproduction. We need a configuration/readback and physical-response
comparison to decide which encoding this firmware actually expects. Guessing
could create a large deadzone or compensation, so negative saves are disabled.

## Validation remaining

- Apply a known preset, verify the full profile and check actual stick travel.
- Save, close the app, restart the controller and verify the setting persists.
- Compare Circle and Rectangle during a full stick rotation.
- Verify the result both with native Steam Input and the controller's normal mode.
- Resolve negative compensation with the official application's USB traffic.

The editor and guarded save transaction pass automated tests, and the page was
visually inspected at 1280 pixels wide. The candidate has not been installed in
the running image, and no curve write has been sent to hardware.
