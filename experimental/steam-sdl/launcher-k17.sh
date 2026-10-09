#!/bin/bash
set -euo pipefail
root="$HOME/.local/share/flydigi-sdl"
if ! sha256sum --status -c "$root/steam-libraries.sha256"; then
    echo 'Steam SDL changed; using unmodified libraries.' >&2
    exec "$@"
fi
export FLYDIGI_SAVED_PRELOAD="${LD_PRELOAD-}"
export FLYDIGI_SAVED_LIBRARY_PATH="${LD_LIBRARY_PATH-}"
export FLYDIGI_SDL_LIBRARY="$root/libSDL3-32.so.0"
export LD_LIBRARY_PATH="$root/lib32${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export LD_PRELOAD="$root/preload-v3.so:$FLYDIGI_SDL_LIBRARY${LD_PRELOAD:+:$LD_PRELOAD}"
exec "$@"
