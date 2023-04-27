all: checkmakefiles
	cd src && $(MAKE)

clean: checkmakefiles
	cd src && $(MAKE) clean

cleanall: checkmakefiles
	cd src && $(MAKE) MODE=release clean
	cd src && $(MAKE) MODE=debug clean
	rm -f src/Makefile

makefiles:
	cd src && opp_makemake -f --deep -O out -KINET4_4_PROJ=~/programs/omnetpp-6.0/samples/inet4.4 -DINET_IMPORT -I$$\(INET4_4_PROJ\)/src -L$$\(INET4_4_PROJ\)/src -lINET$$\(D\)
	# set folder name to your own inet location
	# the options used here were retrieved using the IDE:
	# go to 'Properties for engine > OMNeT++ > Makemake', select folder 'src', under 'Build' click 'Options...' for 'Makemake', choose appropriate options, then copy&paste from tab 'Preview'

checkmakefiles:
	@if [ ! -f src/Makefile ]; then \
	echo; \
	echo '======================================================================='; \
	echo 'src/Makefile does not exist. Please use "make makefiles" to generate it!'; \
	echo '======================================================================='; \
	echo; \
	exit 1; \
	fi
