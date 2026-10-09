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

The numeric lighting presets in `flydigi_control/lighting.py` describe Space
Station 4.2.0.9's Flow animation and device-type-130 factory lighting. They are
included for interoperability with the Vader 5 Pro, not claimed as original
artwork. The factory data came from
`Configs/Controller/f5/default/default_mapping_130.dat`; the reference harness
and [lighting notes](docs/LIGHTING.md) document the extraction and validation.
Vendor executables, assemblies, configuration files and decompiled source are
not distributed here.

`flydigi_control/factory_vader5.json` contains numeric profile-reset settings
converted from that same device-type-130 file. The profile reference harness
reproduces the conversion; only the controller's observed mapping extent is
included. These vendor-authored settings are included for interoperability,
not claimed as original project work.
