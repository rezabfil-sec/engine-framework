CXX=c++
CFLAGS=-Wall -Wextra -O2 -march=native -std=c++17 -fstrict-aliasing

all: triad

triad: triad.cpp
	$(CXX) $(CFLAGS) -o triad $^

clean:
	rm -f triad