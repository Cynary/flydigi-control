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
with `python3 -m flydigi_control.persistence_check check PATH`. The candidate also provides restoration from these files, as described below.
Physical recovery has not yet been tested.

## Validation

Eight tests cover exact packet framing, backup-before-switch ordering, stale
settings, backup failures, unchanged-target no-ops, lost acknowledgments,
verification failures, controller navigation and worker error reporting. The
full candidate suite passes 200 tests on the K17. The profiles page was rendered
and inspected at 1280×1080. No profile-selection command has been sent to the
physical controller during development of this candidate.

## Restore a profile backup

Read the active profile, choose **Find backups**, select a file and review which
sections differ. **Restore profile from backup** asks for a second confirmation
before replacing its mappings/analog settings, LEDs and macros, then saving them
onboard. The model, firmware, connection type, original profile slot and data
formats must match. Use only a backup from this same physical controller: the
protocol does not provide a unique serial number with which to verify identity.

The current profile is backed up before restoration in the same format, so it
can be selected to undo the restore. A separate transaction record contains the
original and requested data. The saved version number is updated, not copied
from the older backup. Global settings, native-mapping permission and Steam
ownership are not restored. Change those through their own settings pages.

Copy an app-generated profile backup into the state directory to import it, then
choose Find backups. These files are not Space Station whole-profile files; that
conversion remains unimplemented. Older transaction logs without the profile
snapshot format are skipped. Unknown formats, incompatible macro events and
invalid data are rejected rather than reinterpreted.

Seven further tests cover restoring all profile sections, using the automatic
backup to undo it, version handling, lost acknowledgments, incompatibility,
stale state, failed backup/readback, file bounds and controller-operated review.
All 207 tests pass on the K17. The restored-state tests use a simulated device;
physical restore and retention after power-off still require validation.

## Restore the active profile's defaults

The candidate also has **Restore active profile defaults**. Its confirmation
names the active profile and explains that it will replace buttons, stick and
trigger settings, motion settings and lighting, and clear that profile's macros.
It backs up the current profile in the ordinary restore format first, so the
backup can be selected to undo the reset. Global settings, Steam ownership and
other profiles are not reset. The operation saves the new profile onboard.

The defaults come from Space Station 4.2.0.9's Vader 5 data, converted by the
[reference harness](../experimental/profile-reference/README.md). They are
restricted to device type 130, firmware 7.1.5.0, the observed 840-byte mapping
format, 320-byte lighting and version-1 macro bank. Other configurations leave
the reset button disabled. This deliberately does not send the vendor SDK's
additional FF mapping padding beyond the controller's reported profile size.

This is still an uninstalled candidate. Automated checks cover every preset,
macro removal, backups and undo, stale snapshots and confirmation cancellation.
A physical reset/undo and controller off/on test are still required.
