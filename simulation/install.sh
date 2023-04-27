#!/bin/bash

# This script installs OMNeT++ and INET in the current working directory, then builds the simulation specific project.
# Assumes that the simulation specific project is in the current working directory.
# The respective command line option has to be used to provide a different location.
# To avoid downloading, the script checks if the OMNeT++ and INET installation .tgz files are already present in the working directory.
# TODO: contains TODOs for optional tasks which might be convenient; install and enable OMNeT++ debugging functionality

set -e

opp_location=/opt
inet_location=/opt
engine_dir=engine # directory for simulation specific project

function usage {
	echo "Usage: $0 [-e engine_dir]"
	echo ""
	echo "Install OMNeT++ and INET, then build the custom simulation project"
	echo ""
	echo "options:"
	echo -e "\t-e Directory where the simulation project is located (relative to current working directory)"
	echo -e "\t-i Directory where the INET Framework is located (absolute)"
	echo -e "\t-o Directory where OMNeT++ is located (absolute)"
}

function prepare_dir {
	url=$1
	dir=$2
	file=$(echo $url | rev | cut -d / -f 1 | rev)
	echo $file
	if ! [ -f "$file" ]; then
		wget $url
	fi
	if [ -f "$file" ]; then
		tar xvfz $file
		rm $file
		cd $dir
	else
		exit 1
	fi
}

while getopts ":e:i:o:" opt
do
	case "$opt" in
		e )
			engine_dir=$OPTARG ;;
		i )
			inet_location=$OPTARG ;;
		o )
			opp_location=$OPTARG ;;
		? )
			usage	
			exit 1
			;;
	esac
done

# OMNeT++ Dependencies
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install -y build-essential clang lld gdb bison flex perl python3 python3-pip qtbase5-dev qtchooser qt5-qmake qtbase5-dev-tools libqt5opengl5-dev libxml2-dev zlib1g-dev doxygen graphviz libwebkit2gtk-4.0-37
python3 -m pip install --user --upgrade numpy pandas matplotlib scipy seaborn posix_ipc
#sed "s/kernel.yama.ptrace_scope = 1/kernel.yama.ptrace_scope = 0/" /etc/sysctl.d/10-ptrace.conf

wd=$(pwd)

# OMNeT++

cd $opp_location

prepare_dir https://github.com/omnetpp/omnetpp/releases/download/omnetpp-6.0/omnetpp-6.0-linux-x86_64.tgz $opp_location/omnetpp-6.0
source setenv
sed -i "s/WITH_QTENV=yes/WITH_QTENV=no/" configure.user
sed -i "s/WITH_OSG=yes/WITH_OSG=no/" configure.user
rm -r ide
./configure 
make -j8
location_o=$(pwd)

echo "[ -f \"$location_o/setenv\" ] && source \"$location_o/setenv\"" >> ~/.bashrc

cd $wd

# INET

cd $inet_location

prepare_dir https://github.com/inet-framework/inet/releases/download/v4.4.0/inet-4.4.0-src.tgz $inet_location/inet4.4
source setenv
# TODO: disable unused INET features
make makefiles
make -j8
location_i=$(pwd)

cd $wd

# custom simulation project

cd $engine_dir
sed -i "s|KINET4_4_PROJ=[[:graph:]]* |KINET4_4_PROJ=${location_i} |" Makefile
make makefiles
make -j8
