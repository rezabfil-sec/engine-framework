#include <math.h>
#include <string.h>

#include <chrono>
#include <cstdio>

// use a 1d array to guarantee a dense and sequential memory layout
#define TWO_D_ACCESS(row, col, width) ((width) * (row) + (col))

double mm(int n, int rep)
{
    //////////////////////////////////////////////////////////////////////////
    // ALLOCATION
    /////////////////////////////////////////////////////////////////////////

    double* a = (double*)malloc(n * n * sizeof(double));
    double* b = (double*)malloc(n * n * sizeof(double));
    double* c = (double*)malloc(n * n * sizeof(double));

    //////////////////////////////////////////////////////////////////////////
    // ALLOCATION
    /////////////////////////////////////////////////////////////////////////

    for (int i = 0; i < n * n; ++i) {
        a[i] = 0;
        // initialize with something so the compiler/cpu cannot optimize 0*0=0
        b[i] = atan(i);
        c[i] = cos(i);
    }

    //////////////////////////////////////////////////////////////////////////
    // WARM UP
    /////////////////////////////////////////////////////////////////////////

    for (int r = 0; r < rep; ++r) {
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                for (int k = 0; k < n; k++) {
                    a[TWO_D_ACCESS(i, j, n)] += b[TWO_D_ACCESS(i, k, n)] * c[TWO_D_ACCESS(k, j, n)];
                }
            }
        }
    }

    //////////////////////////////////////////////////////////////////////////
    // MATRIX MULTIPLICATION KERNELS
    /////////////////////////////////////////////////////////////////////////
    auto t0 = std::chrono::high_resolution_clock::now();

    for (int r = 0; r < rep; ++r) {
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                for (int k = 0; k < n; k++) {
                    a[TWO_D_ACCESS(i, j, n)] += b[TWO_D_ACCESS(i, k, n)] * c[TWO_D_ACCESS(k, j, n)];
                }
            }
        }
    }
    auto t1 = std::chrono::high_resolution_clock::now();

    // simple correctness check
    double array_sum = 0;

    for (int i = 0; i < n * n; ++i) {
        array_sum += a[i];
    }

    free((void*)a);
    free((void*)b);
    free((void*)c);

    using dsec = std::chrono::duration<double>;
    double dur = std::chrono::duration_cast<dsec>(t1 - t0).count();
    printf("Duration: %.4fs\n", dur);

    double mflop = 2.0 * (double)n * (double)n * (double)n * (double)rep * 1.0e-6;
    return mflop / dur;
}

int main(int argc, char* argv[])
{
    if (argc < 3) {
        printf("Usage: %s <N> <REP> [output_file]\n", argv[0]);
        return 1;
    }

    int n, rep;
    const char *output_filename = nullptr;

    n = atoi(argv[1]);
    rep = atoi(argv[2]);

    if (n <= 0 || rep <= 0) {
        printf("Wrong parameter size for N or REP!\n");
        return 1;
    }

    if (argc == 4) {
        output_filename = argv[3];
    } else {
        output_filename = "matrix_mul.csv";
    }

    // Delete the output file if it exists
    remove(output_filename);

    FILE *output_file = fopen(output_filename, "w");

    if (output_file == nullptr) {
        printf("Error opening output file!\n");
        return 1;
    }

    printf("N: %d, REP: %d\n", n, rep);
    fprintf(output_file, "N,Rep,MFLOPS\n");

    double mf;

    mf = mm(n, rep);
    printf("MFLOPs (N=%d): %.3f\n", n, mf);
    fprintf(output_file, "%d,%d,%.3f\n", n, rep, mf);

    return 0;
}