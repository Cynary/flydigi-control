"""Steam updates and session flags must survive the controller integration."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'packaging/steam-sdl'

class SteamLauncherTests(unittest.TestCase):
    def test_session_flags_and_wrappers_survive(self):
        cases = {
            'steam -gamepadui -custom': '/usr/bin/steam-flydigi -gamepadui -custom',
            'opengamepadui --overlay-mode -- steam -gamepadui':
                'opengamepadui --overlay-mode -- /usr/bin/steam-flydigi -gamepadui',
            '/usr/bin/other-client --steam-test': '/usr/bin/other-client --steam-test',
        }
        for before, after in cases.items():
            result = subprocess.check_output(['bash', '-c',
                'CLIENTCMD=$1; source "$2"; printf "%s" "$CLIENTCMD"',
                'test', before, str(SOURCE / 'session.sh')], text=True)
            self.assertEqual(result, after)

    def test_update_or_missing_library_uses_original_steam(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / 'replacement'
            root.mkdir()
            steam = base / 'steam'
            steam.write_text('#!/usr/bin/python3\nimport json,os,sys\n'
                             'print(json.dumps([sys.argv[1:], os.environ.get("DEBUGGER"), '
                             'os.environ.get("FLYDIGI_SDL_LIBRARY")]))\n')
            steam.chmod(0o755)
            loader = base / 'loader'
            loader.write_text((SOURCE / 'steam-flydigi-loader').read_text().replace(
                'root=/usr/lib/moonmachine/steam-sdl', f'root="{root}"'))
            original = base / 'libSDL3.so.0'
            for case in ('missing-original', 'changed', 'missing-replacement'):
                if case != 'missing-original':
                    original.write_bytes(b'current Steam SDL')
                    digest = hashlib.sha256(original.read_bytes()).hexdigest()
                    (root / 'steam-sdl.sha256').write_text(digest if case == 'missing-replacement' else '0'*64)
                result = subprocess.run(['bash', str(loader), str(steam), 'with spaces', '-gamepadui'],
                    env={**os.environ, 'DEBUGGER': 'this-launcher'}, text=True, capture_output=True, check=True)
                self.assertEqual(json.loads(result.stdout), [['with spaces', '-gamepadui'], None, None])
