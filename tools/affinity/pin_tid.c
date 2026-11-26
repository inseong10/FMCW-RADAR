/* Minimal taskset -p replacement for the board (busybox has no taskset).
 * Usage: pin-tid MASK TID [TID...]   set CPU mask (hex, e.g. 1 or 2) on each TID
 *        pin-tid -q TID [TID...]     print current mask
 * Prints "tid=<tid> mask=<hex>" read back with sched_getaffinity after each set.
 * Diagnostic tool only; does not modify the receiver. */
#define _GNU_SOURCE
#include <errno.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>

static int show(pid_t tid) {
    cpu_set_t set;
    CPU_ZERO(&set);
    if (sched_getaffinity(tid, sizeof(set), &set)) {
        fprintf(stderr, "tid=%d get failed: %s\n", (int)tid, strerror(errno));
        return 1;
    }
    unsigned long mask = 0;
    for (int c = 0; c < (int)(8 * sizeof(mask)) && c < CPU_SETSIZE; ++c)
        if (CPU_ISSET(c, &set)) mask |= 1UL << c;
    printf("tid=%d mask=%lx\n", (int)tid, mask);
    return 0;
}

static int parse_tid(const char *s, pid_t *tid) {
    char *end = NULL;
    long v = strtol(s, &end, 10);
    if (!s[0] || *end || v <= 0) return 1;
    *tid = (pid_t)v;
    return 0;
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "Usage: %s MASK|-q TID [TID...]\n", argv[0]);
        return 2;
    }
    int query = strcmp(argv[1], "-q") == 0;
    cpu_set_t set;
    CPU_ZERO(&set);
    if (!query) {
        char *end = NULL;
        unsigned long mask = strtoul(argv[1], &end, 16);
        if (!argv[1][0] || *end || !mask) {
            fprintf(stderr, "Invalid hex mask\n");
            return 2;
        }
        for (int c = 0; c < (int)(8 * sizeof(mask)) && c < CPU_SETSIZE; ++c)
            if (mask & (1UL << c)) CPU_SET(c, &set);
    }
    int rc = 0;
    for (int i = 2; i < argc; ++i) {
        pid_t tid;
        if (parse_tid(argv[i], &tid)) {
            fprintf(stderr, "Invalid TID %s\n", argv[i]);
            rc = 2;
            continue;
        }
        if (!query && sched_setaffinity(tid, sizeof(set), &set)) {
            fprintf(stderr, "tid=%d set failed: %s\n", (int)tid, strerror(errno));
            rc = 1;
            continue;
        }
        rc |= show(tid);
    }
    return rc;
}
