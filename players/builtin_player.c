#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

#ifndef MOVE_DELAY_SECONDS
#define MOVE_DELAY_SECONDS 0
#endif

/* Local developer utility; not built or invoked by the website. */
int main(void) {
    char line[65536];
    srand((unsigned int)time(NULL));
    while (fgets(line, sizeof line, stdin)) {
        char *board = strstr(line, "\"board\"");
        int cell = 0;
        int choices[42];
        int choice_count = 0;
        if (board) {
            for (char *p = board; *p; ++p) {
                if (p[0] == '\"' && p[2] == '\"' &&
                    (p[1] == ' ' || p[1] == 'X' || p[1] == 'O' ||
                     p[1] == 'R' || p[1] == 'B')) {
                    if (p[1] == ' ') choices[choice_count++] = cell;
                    ++cell;
#ifdef CONNECT_FOUR
                    if (cell == BOARD_SIZE) break;
#endif
                    p += 2;
                }
            }
        }
        if (choice_count == 0) return 1;
        int chosen = choices[rand() % choice_count];
        if (MOVE_DELAY_SECONDS > 0) sleep(MOVE_DELAY_SECONDS);
#ifdef CONNECT_FOUR
        printf("{\"col\":%d}\n", chosen);
#else
        printf("{\"row\":%d,\"col\":%d}\n", chosen / BOARD_SIZE, chosen % BOARD_SIZE);
#endif
        fflush(stdout);
    }
    return 0;
}
