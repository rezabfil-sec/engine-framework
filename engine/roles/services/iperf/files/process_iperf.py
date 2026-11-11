#!/usr/bin/env python3

# iperf specific stuff to be used by general processing scripts

from pypacker.layer4 import udp

#sequence = 'iperf_sequence' # column with sequence numbers
merge = ['iperf_ts_seconds', 'iperf_ts_microseconds', 'iperf_sequence'] # columns to be merged on

# to be called by csv_parser_pcap_single.py
def to_dict(d, pkt):
    pkt_udp = pkt[udp.UDP]
    d['iperf_ts_seconds'] = int.from_bytes(bytes(pkt_udp.body_bytes)[0:4], 'big')
    d['iperf_ts_microseconds'] = int.from_bytes(bytes(pkt_udp.body_bytes)[4:8], 'big')
    d['iperf_sequence'] = int.from_bytes(bytes(pkt_udp.body_bytes)[8:12], 'big')
