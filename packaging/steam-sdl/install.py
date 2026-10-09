"""Package a built 32-bit SDL and loader into DESTDIR; no runtime changes."""
from pathlib import Path
import shutil
import sys

source = Path(__file__).resolve().parent
root, sdl, preload = map(Path, sys.argv[1:])
lib = root / 'usr/lib/moonmachine/steam-sdl'
(lib / 'lib32').mkdir(parents=True, exist_ok=True)
shutil.copy2(sdl, lib / 'lib32/libSDL3.so.0')
shutil.copy2(preload, lib / 'preload.so')
shutil.copy2(source / 'steam-sdl.sha256', lib / 'steam-sdl.sha256')
for name, target in [('steam-flydigi', 'usr/bin/steam-flydigi'),
                     ('steam-flydigi-loader', 'usr/libexec/steam-flydigi-loader')]:
    dest = root / target
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / name, dest)
    dest.chmod(0o755)
for session in ('steam', 'ogui-steam'):
    dest = root / 'etc/gamescope-session-plus/sessions.d' / session
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / 'session.sh', dest)
