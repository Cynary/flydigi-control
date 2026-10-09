# Sources

`flydigi_control/protocol.py` and `flydigi_control/led.py` come from
[Tux InVader](https://github.com/TJLawInOrbit/tux-invader), commit
`2b1a1f5458f1b0261d7d8e096c8483f2b7776174`, under GPL-3.0.
Its protocol work credits SDL, BANANASJIM/flydigi-vader5, and
rR6kULhc5xgS/flydigi-vader-pro-5-ctl. Their attribution is retained in the files.

The configuration transport and couch interface are new code written with Codex.
This project is distributed under GPL-3.0; see LICENSE.

Turbo and Fn profile feature IDs and capability bits were cross-checked against
[rR6kULhc5xgS/flydigi-vader-pro-5-ctl](https://github.com/rR6kULhc5xgS/flydigi-vader-pro-5-ctl),
`docs/protocol-settings.md` and `flydigi/commands.py`. New transport code implements
only these two feature toggles, with capability checks and state read-back.
