CXX=c++
CFLAGS=-Wall -Wextra -O2 -march=native -std=c++17 -fstrict-aliasing

all: matrix_mul

matrix_mul: matrix_mul.cpp
	$(CXX) $(CFLAGS) -o matrix_mul $^

clean:
	rm -f matrix_mul