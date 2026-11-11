#!/usr/bin/env python3

# send_udp specific stuff to be used by general processing scripts

from pypacker.layer4 import udp

#sequence = 'udp_tai_sequence' # column with sequence numbers
merge = ['udp_tai_nanoseconds', 'udp_tai_sequence'] # columns to be merged on

# to be called by csv_parser_pcap_single.py
def to_dict(d, pkt):
    pkt_udp = pkt[udp.UDP]
    # send udp stores in ns len of 8B, requires 
    # read_tstamp = int(struct.unpack('<Q', bytearray(pkt['Raw'].load[:8]))[0])
    # d['udp_tai_nanoseconds'] = read_tstamp
    # d['udp_tai_sequence'] = struct.unpack('<i', bytearray(pkt['Raw'].load[8:12]))[0]
    d['udp_tai_nanoseconds'] = int.from_bytes(bytes(pkt_udp.body_bytes)[0:8], 'big')
    d['udp_tai_sequence'] = int.from_bytes(bytes(pkt_udp.body_bytes)[8:12], 'big')
