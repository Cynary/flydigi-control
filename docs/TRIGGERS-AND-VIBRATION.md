# Trigger travel and saved vibration

Controller settings now includes candidate pages for trigger travel/vibration
and saved grip vibration. These edit the active onboard profile. The Motors
page separately sends temporary pulses for testing; it does not save strengths.

Each trigger has a travel start and end, measured from 0 to 255. They select the
physical interval over which the trigger reaches its full output range, rather
than limiting the output values sent to a game. Start must be below End.

Trigger vibration has a shared enable switch for both sides. Amplitude limits,
strength and the threshold that suppresses small vibrations are stored separately
for each side. The official app describes this as converting game-supplied grip
vibration into trigger vibration. Whether native Steam Input uses or bypasses
these profile settings still needs a hardware comparison. This is distinct from
a game sending independent trigger-motor commands through the new SDL callback.

Grip vibration has a master enable, individual motor enables and individual
strengths. The official app writes both grip configurations together; this
editor changes only the selected side and the explicitly displayed master flag.
Existing minimum/maximum amplitude values are shown and preserved.

## Format

Space Station 4.2.0.9's mapping parser and service establish these fields:

| Settings | Mapping offsets | Write behavior |
| --- | --- | --- |
| Trigger travel | 123–136, seven bytes per side | Update start/end and their control-point coordinates; preserve type |
| Grip vibration | 145–153 | Master and side enables use 0/on, 255/off; strength is a percentage |
| Trigger vibration | 154–182 | Shared enable uses 0/on, 1/off; edit only the selected side's linear amplitude/filter/scale fields |

Trigger amplitude percentages use ceiling when reading byte values and floor
when writing percentages. That conversion is lossy, so a read/save without
editing amplitude preserves the original bytes. Tests cover all nonzero byte
values. The micro-trigger and APEX force-feedback fields remain untouched.

Every save backs up the profile, rejects stale snapshots and a changed active
profile, writes only changed chunks, checks the full mapping, and commits once.
Unknown saved values are reported instead of silently clamped into an editor's
range. There is no write on slider movement.

## Status

Protocol, preservation and UI tests pass. The pages have not been installed in
the running image, and no trigger or saved-vibration settings have been written
to hardware. Physical behavior, persistence after power-off and interaction
with Steam Input remain to be verified. Vendor source is not distributed here;
the source provenance is recorded in [LIGHTING.md](LIGHTING.md).
