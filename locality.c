#define _POSIX_C_SOURCE 200809L

#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static volatile uint64_t sink;

static double now_seconds(void) {
    struct timespec ts;

    if (clock_gettime(CLOCK_MONOTONIC_RAW, &ts) != 0) {
        perror("clock_gettime");
        exit(EXIT_FAILURE);
    }

    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

static void flush_cache(uint8_t *buffer, size_t bytes) {
    uint64_t sum = 0;

    for (size_t i = 0; i < bytes; i += 64) {
        buffer[i]++;
        sum += buffer[i];
    }

    sink = sum;
}

static double measure_row_major(const uint32_t *matrix, size_t n) {
    uint64_t sum = 0;
    double start = now_seconds();

    for (size_t row = 0; row < n; row++) {
        size_t base = row * n;
        for (size_t column = 0; column < n; column++) {
            sum += matrix[base + column];
        }
    }

    double elapsed = now_seconds() - start;
    sink = sum;
    return elapsed;
}

static double measure_column_major(const uint32_t *matrix, size_t n) {
    uint64_t sum = 0;
    double start = now_seconds();

    for (size_t column = 0; column < n; column++) {
        for (size_t row = 0; row < n; row++) {
            sum += matrix[row * n + column];
        }
    }

    double elapsed = now_seconds() - start;
    sink = sum;
    return elapsed;
}

static int compare_doubles(const void *left, const void *right) {
    double a = *(const double *)left;
    double b = *(const double *)right;
    return (a > b) - (a < b);
}

static size_t parse_size(const char *value, const char *name) {
    char *end = NULL;
    errno = 0;
    unsigned long parsed = strtoul(value, &end, 10);

    if (errno != 0 || *value == '\0' || *end != '\0' || parsed == 0) {
        fprintf(stderr, "Invalid %s: %s\n", name, value);
        exit(EXIT_FAILURE);
    }

    return (size_t)parsed;
}

int main(int argc, char **argv) {
    size_t n = 4096;
    size_t trials = 7;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--size") == 0 && i + 1 < argc) {
            n = parse_size(argv[++i], "size");
        } else if (strcmp(argv[i], "--trials") == 0 && i + 1 < argc) {
            trials = parse_size(argv[++i], "trial count");
        } else {
            fprintf(stderr, "Usage: %s [--size N] [--trials N]\n", argv[0]);
            return EXIT_FAILURE;
        }
    }

    if (n > SIZE_MAX / n || n * n > SIZE_MAX / sizeof(uint32_t)) {
        fputs("Matrix size is too large.\n", stderr);
        return EXIT_FAILURE;
    }

    size_t element_count = n * n;
    size_t matrix_bytes = element_count * sizeof(uint32_t);
    size_t flush_bytes = 64U * 1024U * 1024U;
    uint32_t *matrix = NULL;
    uint8_t *cache_buffer = NULL;
    double *row_times = calloc(trials, sizeof(*row_times));
    double *column_times = calloc(trials, sizeof(*column_times));

    if (posix_memalign((void **)&matrix, 64, matrix_bytes) != 0 ||
        posix_memalign((void **)&cache_buffer, 64, flush_bytes) != 0 ||
        row_times == NULL || column_times == NULL) {
        fputs("Memory allocation failed.\n", stderr);
        free(matrix);
        free(cache_buffer);
        free(row_times);
        free(column_times);
        return EXIT_FAILURE;
    }

    for (size_t i = 0; i < element_count; i++) {
        matrix[i] = (uint32_t)(i % 251U);
    }
    memset(cache_buffer, 0, flush_bytes);

    for (size_t trial = 0; trial < trials; trial++) {
        flush_cache(cache_buffer, flush_bytes);
        if (trial % 2 == 0) {
            row_times[trial] = measure_row_major(matrix, n);
            flush_cache(cache_buffer, flush_bytes);
            column_times[trial] = measure_column_major(matrix, n);
        } else {
            column_times[trial] = measure_column_major(matrix, n);
            flush_cache(cache_buffer, flush_bytes);
            row_times[trial] = measure_row_major(matrix, n);
        }
    }

    double *sorted_rows = malloc(trials * sizeof(*sorted_rows));
    double *sorted_columns = malloc(trials * sizeof(*sorted_columns));
    if (sorted_rows == NULL || sorted_columns == NULL) {
        fputs("Memory allocation failed.\n", stderr);
        return EXIT_FAILURE;
    }

    memcpy(sorted_rows, row_times, trials * sizeof(*sorted_rows));
    memcpy(sorted_columns, column_times, trials * sizeof(*sorted_columns));
    qsort(sorted_rows, trials, sizeof(*sorted_rows), compare_doubles);
    qsort(sorted_columns, trials, sizeof(*sorted_columns), compare_doubles);

    double row_median = sorted_rows[trials / 2];
    double column_median = sorted_columns[trials / 2];

    printf("{\n");
    printf("  \"matrix_size\": %zu,\n", n);
    printf("  \"element_count\": %zu,\n", element_count);
    printf("  \"matrix_bytes\": %zu,\n", matrix_bytes);
    printf("  \"trials\": %zu,\n", trials);
    printf("  \"row_major_ms\": [");
    for (size_t i = 0; i < trials; i++) {
        printf("%s%.6f", i == 0 ? "" : ", ", row_times[i] * 1000.0);
    }
    printf("],\n");
    printf("  \"column_major_ms\": [");
    for (size_t i = 0; i < trials; i++) {
        printf("%s%.6f", i == 0 ? "" : ", ", column_times[i] * 1000.0);
    }
    printf("],\n");
    printf("  \"row_median_ms\": %.6f,\n", row_median * 1000.0);
    printf("  \"column_median_ms\": %.6f,\n", column_median * 1000.0);
    printf("  \"column_to_row_ratio\": %.6f,\n", column_median / row_median);
    printf("  \"checksum\": %" PRIu64 "\n", sink);
    printf("}\n");

    free(matrix);
    free(cache_buffer);
    free(row_times);
    free(column_times);
    free(sorted_rows);
    free(sorted_columns);
    return EXIT_SUCCESS;
}
