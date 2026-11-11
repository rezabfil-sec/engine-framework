#!/bin/bash

# Downloads and installs iperf3

set -e

location=/data
multisend=10
version=12

function usage {
	echo "Usage: $0 [-l location]"
	echo ""
	echo "Download and install iperf"
	echo ""
	echo "options:"
	echo -e "\t-l location (relative to current working directory, or absolute)"
	echo -e "\t-m replacement for multisend value"
	echo -e "\t-v iperf3 (sub)version (default: 12)"
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
		tar xvfz $file -C $location
		rm $file
		cd $dir
	else
		exit 1
	fi
}

while getopts ":l:m:v:" opt
do
	case "$opt" in
		l )
			location=$OPTARG ;;
		m )
			multisend=$OPTARG ;;
		v )
			version=$OPTARG ;;
		? )
			usage	
			exit 1
			;;
	esac
done

prepare_dir https://downloads.es.net/pub/iperf/iperf-3.$version.tar.gz $location/iperf-3.$version

sed -i "s/testp->multisend = 10;/testp->multisend = $multisend;/" src/iperf_api.c

./configure
make
make install

echo "Run via binary $(pwd)/src/iperf3"
