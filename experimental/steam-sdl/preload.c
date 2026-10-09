#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>

/* Steam also opens SDL by absolute filename. Route that explicit open to the
 * preloaded library so it cannot create a second, independent SDL instance. */
static void *(*real_dlopen)(const char *, int);
static pthread_once_t resolve_once = PTHREAD_ONCE_INIT;
static char *replacement;

static void resolve_dlopen(void) {
    real_dlopen = dlsym(RTLD_NEXT, "dlopen");
}

__attribute__((constructor)) static void initialize(void) {
    const char *path = getenv("FLYDIGI_SDL_LIBRARY");
    if (path && *path) replacement = strdup(path);
    const char *previous = getenv("FLYDIGI_SAVED_PRELOAD");
    if (previous && *previous) setenv("LD_PRELOAD", previous, 1);
    else unsetenv("LD_PRELOAD");
    unsetenv("FLYDIGI_SAVED_PRELOAD");
    unsetenv("FLYDIGI_SDL_LIBRARY");
}

void *dlopen(const char *filename, int flags) {
    pthread_once(&resolve_once, resolve_dlopen);
    if (replacement && filename) {
        const char *base = strrchr(filename, '/');
        base = base ? base + 1 : filename;
        if (!strcmp(base, "libSDL3.so.0")) filename = replacement;
    }
    return real_dlopen(filename, flags);
}
