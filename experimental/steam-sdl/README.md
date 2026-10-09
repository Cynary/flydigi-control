# Steam SDL loading experiment

The Turbo patch is in [Cynary/SDL, vader5-turbo](https://github.com/Cynary/SDL/tree/vader5-turbo), based on Steam's reported source revision. This directory tests loading it without modifying Steam's installed libraries.

A bind mount over Steam's SDL files does not work with its integrity check: the updater tries to replace the mounted files. Launching Steam through `ld.so --preload` changes `/proc/self/exe` and causes Steam to resolve its installation under the loader's directory. Neither approach is suitable.

The current candidate preloads the replacement SDL into the 32-bit Steam process and redirects explicit `dlopen` and `dlmopen` calls for `libSDL3.so.0` to that same library. The constructor restores the caller's original preload environment before Steam starts any children. Games and steamwebhelper keep their normal libraries. Steam also loads dependencies into isolated namespaces. The launcher puts the replacement directory first in `LD_LIBRARY_PATH` at process startup; the constructor then restores that environment variable for children, while the current dynamic loader retains its startup search path.

A launcher must restrict this to Steam and check the original library hashes; a Steam update must fall back to its bundled libraries until compatibility is revalidated.

`test-loader.c` checks explicit library resolution, absence of the original SDL mapping, and removal of the experimental environment from children. Build both files for 32-bit and run the test against Steam's original library path and the replacement path:

```sh
cc -m32 -shared -fPIC -Wall -Wextra -Werror preload.c -ldl -pthread -o preload.so
cc -m32 -Wall -Wextra -Werror test-loader.c -ldl -o test-loader
env FLYDIGI_SDL_LIBRARY=/absolute/patched-SDL.so FLYDIGI_SAVED_PRELOAD= \
    LD_PRELOAD=/absolute/preload.so:/absolute/patched-SDL.so \
    ./test-loader /absolute/original/libSDL3.so.0 /absolute/patched-SDL.so
```

This isolated test passes on the K17. The loader is running in Steam on the K17: process maps show only the replacement SDL in the 32-bit client, steamwebhelper retains its bundled SDL, and Steam’s own controller mapping contains `misc1:b20`. Its controller capability mask gained the corresponding extra-button bit. The earlier preload-only trial allowed Steam to open its original SDL as well, so seeing the patched library in process maps alone is insufficient proof that its driver is used. Physical Turbo press and release events are now confirmed in Steam’s controller-state feed. Actual bindings, reconnect behavior and updater compatibility remain release gates. Tests also cover explicit loads into an isolated namespace, which the initial preload-only experiment missed. This is not installed by the image packaging script.
