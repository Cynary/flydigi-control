# Check extra-button actions through Steam Input

`steam-input-check.py` is a small validation app. It listens for ordinary Qt
keyboard events. It does not read the controller, inject input, or turn a raw
HID report into a passing result.

Add the executable script to Steam as **Flydigi Steam Input Check** and enable
Steam Input for that shortcut. Use a separate configuration from your games.
Map the ten extra buttons to these keyboard keys:

| Button | Key |
| --- | --- |
| M1 | A |
| M2 | B |
| M3 | C |
| M4 | D |
| C | E |
| Z | F |
| LM | G |
| RM | H |
| Fn | I |
| Turbo | J |

Launch through Steam, then press and release each button separately. A tile
turns green only after both key events reach the app. Do not type the test
keys on a keyboard: that would test the display, not the controller mapping.
Use Steam's menu to exit, or press Escape on a keyboard.

The last run is saved to
`~/.local/state/flydigi-control/steam-input-actions.jsonl` (or the corresponding
`XDG_STATE_HOME` directory). Keep the file alongside the raw and Steam event
captures. Remove the test shortcut afterward if you do not need it.
