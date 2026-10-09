# Check extra-button actions through Steam Input

`steam-input-check.py` is a small validation app. It listens for ordinary Qt
keyboard events. It does not read the controller, inject input, or turn a raw
HID report into a passing result.

Add the executable script to Steam as **Flydigi Steam Input Check** and enable
Steam Input for that shortcut. Use a separate configuration from your games.
Map the ten extra buttons to these keyboard keys:

| Button | Steam state | Configuration input ID | Key |
| --- | --- | --- | --- |
| M1 | R5 | 58 | A |
| M2 | L5 | 57 | B |
| M3 | R4 | 56 | C |
| M4 | L4 | 55 | D |
| C | Bit 32 | 69 | E |
| Z | Bit 33 | 70 | F |
| LM | Bit 34 | 71 | G |
| RM | Bit 35 | 72 | H |
| Fn | Bit 36 | 73 | I |
| Turbo | Capture/misc | 68 | J |

The numeric IDs refer to the tested Steam configuration API, not SDL button
indices. In that API, `RightGrip_Upper` (58) corresponds to R5, while
`RightGrip` (56) corresponds to R4. Assuming the opposite swapped the paddle
labels in the first test configuration. The driver reports were unchanged.

Launch through Steam, then press and release each button separately. A tile
turns green only after both key events reach the app. Do not type the test
keys on a keyboard: that would test the display, not the controller mapping.
Use Steam's menu to exit, or press Escape on a keyboard.

The last run is saved to
`~/.local/state/flydigi-control/steam-input-actions.jsonl` (or the corresponding
`XDG_STATE_HOME` directory). Keep the file alongside the raw and Steam event
captures. Remove the test shortcut afterward if you do not need it.
