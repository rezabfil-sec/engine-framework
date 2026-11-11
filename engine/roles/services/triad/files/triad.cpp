#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <chrono>
#include <math.h>
#include <errno.h>
#include <assert.h>

double get_curr_time() {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec * 1e-9;
}

double calculate_checksum(long dataset_size, const volatile double* vector) {
    double checksum = 0;
    for (long i = 0; i < dataset_size; i++) {
        checksum += vector[i];
    }
    return checksum;
}

double triad(const long n, const long rep) {
    double time_spent = 0.0;
    std::chrono::system_clock::time_point begin, end;

    double *a, *b, *c, *d;
    a = (double*) malloc(n * sizeof(double));
    b = (double*) malloc(n * sizeof(double));
    c = (double*) malloc(n * sizeof(double));
    d = (double*) malloc(n * sizeof(double));

    for (long j = 0; j < n; j++) {
        a[j] = 0.0;
        b[j] = 1.0;
        c[j] = 2.0;
        d[j] = 3.0;
    }

    for (long i = 0; i < rep; i++) {
        for (long j = 0; j < n; j++) {
            a[j] = b[j] + c[j] * d[j];
        }
    }

    begin = std::chrono::high_resolution_clock::now();
    for (long i = 0; i < rep; i++) {
        for (long j = 0; j < n; j++) {
            a[j] = b[j] + c[j] * d[j];
        }
    }
    end = std::chrono::high_resolution_clock::now();

    using dsec = std::chrono::duration<double>;
    time_spent = std::chrono::duration_cast<dsec>(end - begin).count();

    double sum = calculate_checksum(n, a);
    assert(abs(sum - n * 7.0) < 0.1);

    free(a);
    free(b);
    free(c);
    free(d);

    return time_spent;
}

int main(int argc, char *argv[]) {
    long int n, rep;
    double time_a;
    double performance_a;

    if (argc != 3 && argc != 4) {
        printf("Usage: %s <N> <REP> [output_file]>\n", argv[0]);
        exit(1);
    }

    char * pEnd;
    n = strtol(argv[1], &pEnd, 10);
    if (errno == ERANGE) {
        printf("Can't parse argument <N>. Exiting..");
        exit(1);
    }
    rep = strtol(argv[2], &pEnd, 10);
    if (errno == ERANGE) {
        printf("Can't parse argument <REP>. Exiting..");
        exit(1);
    }

    const char *output_filename = nullptr;

    if (argc == 4) {
        output_filename = argv[3];
    } else {
        output_filename = "triad.csv";        
    }

    // Delete the output file if it exists
    remove(output_filename);

    FILE *output_file = fopen(output_filename, "w");

    if (output_file == nullptr) {
        printf("Error opening output file.\n");
        exit(1);
    }

    fprintf(output_file, "%s,%s,%s,%s,%s\n", "\"Dataset size\"", "\"MFLOPS\"", "\"Cycles\"", "\"Duration\"", "\"Execute Duration\"");

    long dataset_size = 32;
    double m_flop = 0;
    long cycles = 10;

    while (dataset_size <= n && cycles > 1) {
        cycles = rep / dataset_size;

        auto time_start = std::chrono::high_resolution_clock::now();
        time_a = triad(dataset_size, cycles);
        auto time_end = std::chrono::high_resolution_clock::now();

        m_flop = 2.0 * (double) dataset_size * (double) cycles * 1.0e-6;
        performance_a = m_flop / time_a;

        using dsec = std::chrono::duration<double>;
        double spent = std::chrono::duration_cast<dsec>(time_end - time_start).count();
        fprintf(output_file, "%ld,%f,%ld,%f,%f\n", dataset_size, performance_a, cycles, time_a, spent);

        dataset_size *= 2;
    }

    fclose(output_file);

    return 0;
}