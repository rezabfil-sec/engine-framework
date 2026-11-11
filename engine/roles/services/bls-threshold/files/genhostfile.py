import argparse

parser = argparse.ArgumentParser(prog= "genhostfile", description= "Hosts file generator", epilog= "")

parser.add_argument("idlist", type=str, metavar="idlist", nargs='+', help="ids of nodes")
parser.add_argument("iplist", type=str, metavar="iplist", nargs='+', help="ips of nodes")
parser.add_argument("port", type=int, metavar="port",help="same port for all nodes")
parser.add_argument("ofile", type=str, metavar="ofile", help="output file path")

args = parser.parse_args()
id_list = args.idlist[0][1:-1].replace(' ', '').split(',')
ip_list = args.iplist[0][1:-1].replace(' ', '').split(',')
n = len(id_list)

f = open(args.ofile, "w")

f.write("id,ip\n")

index = 0

for i in range(0, n):
    f.write(id_list[i] + "," + ip_list[i] + ":" + str(args.port) + "\n")

f.close()

