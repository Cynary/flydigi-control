#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc, char **argv) {
    if (argc != 3 || getenv("FLYDIGI_SDL_LIBRARY") || getenv("LD_PRELOAD")) return 2;
    void *lib = dlopen(argv[1], RTLD_NOW);
    if (!lib) {fprintf(stderr,"%s\n",dlerror());return 3;}
    void *symbol = dlsym(lib,"SDL_GetRevision");
    Dl_info info;
    if (!symbol || !dladdr(symbol,&info)) return 4;
    printf("SDL implementation: %s\n", info.dli_fname);
    if (strcmp(info.dli_fname,argv[2])) return 5;
    FILE *maps = fopen("/proc/self/maps", "r");
    if (!maps) return 6;
    char line[4096];
    while (fgets(line, sizeof(line), maps)) {
        if (strstr(line, argv[1])) return 7;
    }
    fclose(maps);
    return system("test -z \"${LD_PRELOAD-}\" && test -z \"${FLYDIGI_SDL_LIBRARY-}\"") == 0 ? 0 : 8;
}
