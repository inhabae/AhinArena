#include <stdio.h>
#include <string.h>

/* Minimal deterministic system opponent; build artifacts are never user input. */
int main(void) {
    char line[65536];
    while (fgets(line, sizeof line, stdin)) {
        char *board = strstr(line, "\"board\"");
        int cell = 0;
        int chosen = -1;
        if (board) {
            for (char *p = board; *p; ++p) {
                if (p[0] == '\"' && p[2] == '\"' &&
                    (p[1] == ' ' || p[1] == 'X' || p[1] == 'O' ||
                     p[1] == 'R' || p[1] == 'B')) {
                    if (p[1] == ' ' && chosen < 0) chosen = cell;
                    ++cell;
#ifdef CONNECT_FOUR
                    if (cell == BOARD_SIZE) break;
#endif
                    p += 2;
                }
            }
        }
        if (chosen < 0) chosen = 0;
#ifdef CONNECT_FOUR
        printf("{\"col\":%d}\n", chosen);
#else
        printf("{\"row\":%d,\"col\":%d}\n", chosen / BOARD_SIZE, chosen % BOARD_SIZE);
#endif
        fflush(stdout);
    }
    return 0;
}
