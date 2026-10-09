"""Install into an image root; takes DESTDIR, never starts services."""
from pathlib import Path
import shutil
import sys

source = Path(__file__).resolve().parent.parent
dest = Path(sys.argv[1])
package = dest / 'usr/lib/moonmachine/flydigi-control'
package.mkdir(parents=True, exist_ok=True)
shutil.copytree(source / 'flydigi_control', package / 'flydigi_control', dirs_exist_ok=True,
                ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
for name in ('LICENSE', 'THIRD_PARTY.md'):
    shutil.copy2(source / name, package / name)
for name, target in (
    ('flydigi-control', 'usr/bin/flydigi-control'),
    ('flydigi-control.desktop', 'usr/share/applications/flydigi-control.desktop'),
    ('70-moonmachine-vader5.rules', 'usr/lib/udev/rules.d/70-moonmachine-vader5.rules'),
):
    path = dest / target
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / 'packaging' / name, path)
(dest / 'usr/bin/flydigi-control').chmod(0o755)
