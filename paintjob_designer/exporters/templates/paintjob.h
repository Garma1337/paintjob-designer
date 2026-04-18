#ifndef PAINTJOB_H
#define PAINTJOB_H

/*
 * Minimal Texture union used by paintjob source files exported by the
 * Paintjob Designer tool. The 8-slot order matches the standard
 * layout for CTR kart paintjobs: front / back / floor / brown / motorside /
 * motortop / bridge / exhaust.
 */

typedef union {
    struct {
        const char* front;
        const char* back;
        const char* floor;
        const char* brown;
        const char* motorside;
        const char* motortop;
        const char* bridge;
        const char* exhaust;
    };
    const char* p[8];
} Texture;

#endif
