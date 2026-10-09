# Onboard profiles

Under **Controller settings → Onboard profiles and backups**, read the active
profile, choose one of the four PC profiles and select **Use selected profile**.
A second press confirms switching and discarding unsaved editor drafts. Changes
to controller output can take effect immediately. Steam Input may bypass onboard
button mappings while it owns the native controller interface.

Before switching, the app reads the current profile twice and compares it with
the settings originally shown. It backs up the current mapping, lighting, macro
bank, versions and global settings under `~/.local/state/flydigi-control/` (or
`$XDG_STATE_HOME`). A failed backup or a stale settings page prevents the command.
**Back up active profile to PC** performs the same read without selecting another
profile. It does not cycle through the other profiles to back them up.

Selection uses the official SDK's NewXInput `0xA2` command with profile index
0–3. Readback must show the requested profile, unchanged saved versions and
unchanged global settings. A missing acknowledgment is resolved by reading;
there is no automatic retry or rollback. Old editor snapshots are cleared after
selection, including uncertain failures, so they cannot overwrite the new profile.

This operation selects existing settings. It does not issue the permanent-save
command, restore factory defaults or persist unsaved editor drafts. Whether the
selection itself survives power-off still needs a physical test. Switch-mode
profiles are not selected through this PC-mode editor.

Backups use the read-only persistence-check format, so they can also be compared
with `python3 -m flydigi_control.persistence_check check PATH`. A restore/import
UI for whole profiles remains to be implemented; do not manually replay the raw
bytes or treat these files as a tested recovery utility.

## Validation

Eight tests cover exact packet framing, backup-before-switch ordering, stale
settings, backup failures, unchanged-target no-ops, lost acknowledgments,
verification failures, controller navigation and worker error reporting. The
full candidate suite passes 200 tests on the K17. The profiles page was rendered
and inspected at 1280×1080. No profile-selection command has been sent to the
physical controller during development of this candidate.
