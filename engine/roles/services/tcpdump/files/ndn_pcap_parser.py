#!/usr/bin/env python3

# Parse ndn pcap files to csv files

import os
import pandas
import sys
import time
import numpy as np
from pypacker import ppcap
from pypacker.layer12 import ethernet
import ndn.encoding as ndn
import glob


def parse(pd):
    parse_probe(pd)

def to_dict(pkt, packetLengthCorrection, pd, p, ts, buf, iface, direction):
    ''' Store packet contents in a dict '''

    # this part is to get the packet size, I couldn't find a way to do this in pypacker easily
    p._fh.seek(-1 * len(buf) - 16, 1)
    buf2 = p._fh.read(16)
    p._fh.seek(len(buf), 1)
    dx = p._callback_unpack_meta(buf2)

    d = {}
    d['timestamp_ns'] = ts
    d['packet_size_bytes'] = dx[3] - packetLengthCorrection
    d['interface'] = iface
    d['direction'] = direction
    
    return d

# Classes for python-ndn custom TLV parsing
# You can define what to parse in the classes
# UintField = just one unsigned integer parse
# BytesField = random bytes, the content of the bytes is stored but ignored by parser
# ModelField = parse another model recursively
# ignore_critical=True is important, otherwise if parser finds a type that is not defined in the class, it throws an exception
# while parsing, add ignore_critical=True to the parameters too, example: Interest.parse(data, ignore_critical=True)
# not every variable in a class needs to get parsed, if it does not get parsed it will have value of None
class InnerInterest(ndn.TlvModel):
    name = ndn.NameField()
class Interest(ndn.TlvModel):
    interest = ndn.ModelField(ndn.TypeNumber.INTEREST, InnerInterest, ignore_critical=True)

class InnerData(ndn.TlvModel):
    name = ndn.NameField()
class Data(ndn.TlvModel):
    data = ndn.ModelField(ndn.TypeNumber.DATA, InnerData, ignore_critical=True)

class Fragment(ndn.TlvModel):
    data = ndn.ModelField(ndn.TypeNumber.DATA, InnerData, ignore_critical=True)
    interest = ndn.ModelField(ndn.TypeNumber.INTEREST, InnerInterest, ignore_critical=True)
class Nack(ndn.TlvModel):
    nack_reason = ndn.UintField(ndn.LpTypeNumber.NACK_REASON)
class FragmentInfo(ndn.TlvModel):
    seq = ndn.UintField(ndn.LpTypeNumber.SEQUENCE)
    frag_index = ndn.UintField(ndn.LpTypeNumber.FRAG_INDEX)
    frag_count = ndn.UintField(ndn.LpTypeNumber.FRAG_COUNT)
    pit_token = ndn.BytesField(ndn.LpTypeNumber.PIT_TOKEN)
    nack = ndn.ModelField(ndn.LpTypeNumber.NACK, Nack, ignore_critical=True)
    incoming_face_id = ndn.UintField(ndn.LpTypeNumber.INCOMING_FACE_ID)
    frag = ndn.ModelField(ndn.LpTypeNumber.FRAGMENT, Fragment, ignore_critical=True)
class LpPacket(ndn.TlvModel):
    data = ndn.ModelField(ndn.LpTypeNumber.LP_PACKET, FragmentInfo, ignore_critical=True)

class FragmentInfo2(ndn.TlvModel):
    seq = ndn.UintField(ndn.LpTypeNumber.SEQUENCE)
    frag_index = ndn.UintField(ndn.LpTypeNumber.FRAG_INDEX)
    frag_count = ndn.UintField(ndn.LpTypeNumber.FRAG_COUNT)
    pit_token = ndn.BytesField(ndn.LpTypeNumber.PIT_TOKEN)
    nack = ndn.ModelField(ndn.LpTypeNumber.NACK, Nack, ignore_critical=True)
    incoming_face_id = ndn.UintField(ndn.LpTypeNumber.INCOMING_FACE_ID)
class LpPacket2(ndn.TlvModel):
    data = ndn.ModelField(ndn.LpTypeNumber.LP_PACKET, FragmentInfo2, ignore_critical=True)

# add parsed packet to dict
def add_row(rows, row, pd): 
    name = row['ndn_name']
    # convert ndn name so that it can be used in file names
    # remove sequence number, convert '/' to '_'
    name = pd.get_port(name)
    if name not in rows.keys():
        rows[name] = []
    # append packet to the list specific to the name
    rows[name].append(row)

def parse_interest(data, row, rows, pd):
    parsed = Interest.parse(data, ignore_critical=True)
    # print (data)
    # print(parsed)
    name = ndn.Name.to_str(parsed.interest.name)
    seqStr = str(data).split(name.split('/')[-1]+'!')[-1].split('\n')[-1]
    seqNum = int.from_bytes(seqStr.encode(), 'little')
    seq = '/seq=' + str(seqNum) if 'seq' not in name else ''
    # print(seqStr, seqNum)
    # print(seq)
    row['type'] = ndn.TypeNumber.INTEREST
    row['ndn_name'] = name + seq
    # print(name+seq)
    add_row(rows, row, pd)

def parse_data(data, row, rows, pd):
    parsed = Data.parse(data, ignore_critical=True)
    name = ndn.Name.to_str(parsed.data.name)
    # print(name)
    seq = str(data).split(name)[-1].split('&%_')[0] if 'seq' not in name else str(data).split(name)[-1].split('&%_')[0].split('/')[-1]
    # print(name+seq)
    row['type'] = ndn.TypeNumber.DATA
    row['ndn_name'] = name + seq
    add_row(rows, row, pd)

def parse_fragment(data, row, rows, pd, fragments, src):
    # LpPacket2 is to check if the fragment is the first fragment or not
    # if fragment is first, we will additionally parse the name later
    parsed = LpPacket2.parse(data, ignore_critical=True)

    # if it is a NACK packet do nothing and return
    if parsed.data.nack is not None:
        return
    
    # if the fragment is the first one, parse again with the name included in the class
    if parsed.data.frag_index is not None and parsed.data.frag_index == 0: 
        parsed = LpPacket.parse(data, ignore_critical=True)
        if parsed.data.frag is None or parsed.data.frag.data.name is None: 
            pd.print_log('Tcpdump packet capture size too low to capture fragment name!!')
            return
        name = ndn.Name.to_str(parsed.data.frag.data.name)
    # convert big number to negative, seq starts at -1 but parser parses only unsigned ints
    if parsed.data.seq >= 2**31:
        parsed.data.seq = -1    
    row['type'] = ndn.LpTypeNumber.LP_PACKET
    row['ndn_name'] = name if parsed.data.frag_index == 0 else ''
    # store fragment with the mac address of the source to the list, for combining fragments later
    fragments[(parsed.data.seq, src)] = row
    # check if all fragments of a packet is in 'fragments' list
    start = parsed.data.seq - parsed.data.frag_index
    if all((start + i, src) in fragments.keys() for i in range(parsed.data.frag_count)):
        # sum bytes of fragments, combine and add packet to rows
        ts_first = row['timestamp_ns']
        ts_end = row['timestamp_ns']
        # calculate total byte size of fragment, and largest and smallest timestamp of the fragments
        total_bytes = 0
        for i in range(parsed.data.frag_count):
            frag = fragments[(start + i, src)]
            fragments.pop((start + i, src))
            total_bytes += frag['packet_size_bytes']
            ts_first = min(ts_first, frag['timestamp_ns'])
            ts_end = max(ts_end, frag['timestamp_ns'])
            # get name from first fragment
            if i == 0:
                name = frag['ndn_name']
        row['ndn_name'] = name
        row['timestamp_ns_first'] = int(ts_first)
        row['packet_size_bytes'] = total_bytes
        add_row(rows, row, pd)


def parse_probe(pd):
    start = time.time()
    # create results folder if they do not exist
    if not os.path.exists(pd.node_path()):
        os.makedirs(pd.node_path(), exist_ok=True)
    #check if csv's already exist, if so return (should mean parse_on_nodes is enabled)
    csvPath = pd.node_path() + 'csv-' + pd.service_name('') + '-single_' + '*' + '_' + pd.iface + '.csv'
    files = glob.glob(csvPath)
    if len(files) >= 1:
        pd.print_log(f'csv files already exist for node {pd.node}')
        pd.print_log(f'Parsing pcap took {time.time() - start}s.')
        return
    # get all probe pcaps names
    pcap_names = pd.find_file_name('tcpdump_probe_*.pcap', single=False)
    if type(pcap_names) is not list:
        pcap_names = [pcap_names]
    pd.print_log(f'Starting NDN pcap parse for node {pd.node}')
    rows = {}
    if pcap_names == ['']:
        pcap_names = []
    # iterate over every probe pcap and parse them
    # itr = 0
    for pcap_name in pcap_names:
        # extract interface name and direction from tcpdump_probe_****.pcap file name
        interface_name = pcap_name.split('_')[-1][:-5]
        direction = pcap_name.split('_')[-2]
        pcap = ppcap.Reader(filename=pcap_name)
        fragments = {}
        # Iterate over all packets that are of interest to us
        for index, (ts, buf) in enumerate(pcap):
            pkt = ethernet.Ethernet(buf)
            # skip packet if it is not a NDN packet
            if pkt.type != 34340:
                continue
            row = to_dict(pkt, 0, pd, pcap, ts, buf, interface_name, direction)
            data = pkt.body_bytes
            # parse type and size of the whole ndn packet
            typ, typ_len = ndn.parse_tl_num(data, 0)
            size, size_len = ndn.parse_tl_num(data, typ_len)

            # prune data if the actual size of the packet is smaller than tcpdump packet capture size (avoids crash of parser)
            if len(data) > typ_len + size_len + size:
                data = data[:typ_len + size_len + size]

            # Interest
            if typ == ndn.TypeNumber.INTEREST:
                parse_interest(data, row, rows, pd)
                # itr += 1
                # if itr > 2: break
            # Data
            elif typ == ndn.TypeNumber.DATA:
                parse_data(data, row, rows, pd)
            #LpPacket
            elif typ == ndn.LpTypeNumber.LP_PACKET:
                parse_fragment(data, row, rows, pd, fragments, pkt.src_s)
            else:
                print('Pkt type unsupported', typ)
    # print(rows)
    for name in rows.keys():
        csvPath = pd.node_path() + 'csv-' + pd.service_name('') + '-single_' + name + '_' + pd.iface + '.csv'
        # sort the packets by timestamp, as we parse different probe pcaps ndn packets with same name can come from different ifaces
        rows[name] = sorted(rows[name], key=lambda x:x['timestamp_ns'])
        df = pandas.DataFrame(rows[name])
        df.to_csv(csvPath)
    pd.print_log(f'Parsing pcap took {time.time() - start}s.')