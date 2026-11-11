package main

import (
	"crypto/tls"
	"encoding/binary"
	"flag"
	"log"
	"math"
	"net"
	"os"
	"time"
)

// Cmdline options struct
type Options struct {
	connect         string
	port            string
	bufSize         int
	packets         int
	speed           float64
	data            int
	totalData       int
	iterPerSec      float64
	bytesPerSec     float64
	totalIterations uint32
	mode            bool
	keylog          string
	sendPktNum      bool
	debug           bool
	nodelay         bool
}

var options Options

// From: https://stackoverflow.com/questions/35809252/check-if-flag-was-provided-in-go
func isFlagPassed(name string) bool {
	found := false
	flag.Visit(func(f *flag.Flag) {
		if f.Name == name {
			found = true
		}
	})
	return found
}

func parseOptions() {
	connect := flag.String("addr", "10.20.114.4", "The address to which we try to connect")
	port := flag.String("port", "12341", "The port to which we try to connect")
	bufSize := flag.Int("b", 1420, "Buffer size in byte")
	speed := flag.Float64("s", 10000, "Network speed in Mbps")
	data := flag.Int("d", 2000, "The overall data size to send in MB")
	mode := flag.Bool("m", false, "If set the client expects the server to mirror the packages back")
	keylog := flag.String("l", "keys.log", "The file in which key informations are stored")
	debug := flag.Bool("debug", false, "Disables the TLS encryption to debug what is actually send")
	nodelay := flag.Bool("nodelay", false, "If set it disables TCP_NODELAY and writes data immediately")
	// This option does not really make sense (should either be included in the mirror mode) -> keep it for more precise configuration
	sendPktNum := flag.Bool("n", false, "If set the client will send an increasing packet number to the server")
	packets := flag.Int("p", -1, "The number of packets to send. If set to \"-1\" the buffer size has precedence. Otherwise the packet flag has higher priority.")

	flag.Parse()

	options = Options{
		connect:         *connect,
		port:            *port,
		bufSize:         *bufSize,
		packets:         *packets,
		speed:           *speed,
		data:            *data,
		totalData:       0,
		iterPerSec:      0,
		bytesPerSec:     0,
		totalIterations: 0,
		mode:            *mode,
		keylog:          *keylog,
		sendPktNum:      *sendPktNum,
		debug:           *debug,
		nodelay:         *nodelay,
	}
}

func calculateSpeed() []byte {
	log.Print("Calculating the sending speed...")
	// Unit is MB (1^6)
	factor := 1e6
	bytesPerSec := options.speed * factor / 8
	iterPerSec := math.Ceil(bytesPerSec / float64(options.bufSize))
	totalData := options.data * int(factor)
	totalIterations := uint32(math.Ceil(float64(totalData) / float64(options.bufSize)))

	if options.packets > 0 {
		// The packet option has precedence over the total data option
		iterPerSec = math.Min(iterPerSec, float64(options.packets))
		totalData = options.packets * options.bufSize
		totalIterations = uint32(math.Ceil(float64(totalData) / float64(options.bufSize)))

		log.Printf("Sending %d packets in total", totalIterations)
	} else {
		log.Printf("Sending %.4f GB in total", float64(totalData)/1e9)
	}

	log.Printf("Trying to achieve: %.2f Mbps (%.3f pps * %d B)", bytesPerSec/factor*8, iterPerSec, options.bufSize)
	buf := make([]byte, totalData)

	options.iterPerSec = iterPerSec
	options.totalData = totalData
	options.bytesPerSec = bytesPerSec
	options.totalIterations = totalIterations

	log.Print("Sending speed calculated!")
	return buf
}

func dialWithRetries(connectAddr string, config *tls.Config, retries int) (net.Conn, error) {
	var conn net.Conn
	var err error
	for i := 0; i < retries; i++ {
		conn, err = tls.Dial("tcp", connectAddr, config)
		if err == nil {
			return conn, nil
		}
		time.Sleep(time.Second * 30)
	}
	return nil, err
}

func connectToDestination(connectAddr string) net.Conn {
	var conn net.Conn

	if !options.debug {
		// Writing key information to file (used for packet decryption)
		w, err := os.OpenFile(options.keylog, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0600)
		if err != nil {
			log.Panicf("Failed to create file %s", options.keylog)
		}
		defer w.Close()

		config := tls.Config{
			Certificates:       []tls.Certificate{},
			InsecureSkipVerify: true,
			KeyLogWriter:       w,
		}

		conn, err = dialWithRetries(connectAddr, &config, 3)
		if err != nil {
			log.Panicf("Failed to connect to %s", connectAddr)
		}
	} else {
		var err error
		conn, err = net.Dial("tcp", connectAddr)
		if err != nil {
			log.Panicf("Failed to connect to %s", connectAddr)
		}
	}

	// Set the nodelay option if given by the user
	if options.nodelay {
		switch conn := conn.(type) {
		case *net.TCPConn:
			err := conn.SetNoDelay(true)
			if err != nil {
				log.Panicf("Failed to set NODELAY option")
			}
		case *tls.Conn:
			if tcpConn, ok := conn.NetConn().(*net.TCPConn); ok {
				if err := tcpConn.SetNoDelay(true); err != nil {
					log.Panic("Could not set NODELAY option")
				}
			}
		default:
			log.Panicf("Wrong connection type to set option on")
		}
	}

	log.Printf("Connected to %s", connectAddr)
	return conn
}

func fillBuffer(buf []byte, iterations int) []byte {
	log.Print("Starting buffer fill...")

	// Fill the whole buffer with a random number so that
	// it's easier to see when decrypted
	for index, _ := range buf {
		buf[index] = 42
	}

	// log.Printf("Buffer [100 byte]: %02x", buf[:100])

	if options.sendPktNum {
		// Now, calculate the pkt. number and insert at the correct positions
		pktNum := 0
		for iteration := 0; iteration < len(buf); iteration += options.bufSize {
			binary.BigEndian.PutUint32(buf[iteration:], uint32(pktNum))
			pktNum += 1
		}

		// log.Printf("Buffer [300 byte]: %02x", buf[:300])
	}

	log.Print("Buffer filled")

	return buf
}

func sendPackets(conn net.Conn, buf []byte) {
	log.Println("Started sending to server...")

	if options.mode {
		go receivePackets(conn, options.bufSize, options.totalData)
	}

	send := 0
	var iteration uint32
	iteration = 0
	pktStart := 0
	pktEnd := options.bufSize

	interval, _ := time.ParseDuration("1s")
	// breakBurst, _ := time.ParseDuration("1ns")
	// breakIter := options.iterPerSec / 4.0 // Make 4 "pauses" during the bursts

	// if options.speed >= 5000 {
	// 	// To even be able and achieve these speeds we are going to send all packets
	// 	// at once...
	// 	n, err := conn.Write(buf)
	// 	if err != nil {
	// 		log.Panicf("Failed to write data to %s", options.connect)
	// 	}
	// 	send += n
	// } else {
outer:
	for {
		tStart := time.Now()
		for l := 0; l < int(options.iterPerSec); l++ {
			// log.Printf("Sending: %02x", buf[pktStart:pktEnd])
			n, err := conn.Write(buf[pktStart:pktEnd])
			if err != nil {
				log.Panicf("Failed to write data to %s: %s", options.connect, err)
			}
			pktStart += options.bufSize
			pktEnd += options.bufSize

			send += n
			iteration += 1
			if iteration >= options.totalIterations {
				break outer
			}

			// don't let pktEnd overflow!
			if pktEnd > len(buf) {
				log.Printf("pktEnd overflowed: %d", pktEnd)
				pktEnd = len(buf)
				iteration = options.totalIterations
				log.Printf(("new range: %d, %d"), pktStart, pktEnd)
			}
			// if iteration%uint32(breakIter) == 0 {
			// 	time.Sleep(breakBurst)
			// }
		}
		tEnd := time.Now()
		dur := tEnd.Sub(tStart)
		if dur > interval {
			continue
		}
		time.Sleep(interval - dur)
	}
	// }

	log.Printf("Send %d bytes in %d packets", send, iteration)
}

func receivePackets(conn net.Conn, receiveSize int, totalData int) {
	buf := make([]byte, receiveSize)
	received := 0
	packets := 0
	for {
		// In this case it is not as relevant to read the data as a unit of packets but rather to receive as fast as possible
		n, err := conn.Read(buf)
		if err != nil {
			break
		}
		if n == 0 {
			break
		}
		received += n
		packets++
		if received >= totalData {
			break
		}
	}
	log.Printf("Received from server")
}

func main() {
	log.Println("Starting client...")

	f, err := os.OpenFile("/tmp/POPO", os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0600)

	if err == nil {
		defer f.Close()
		f.WriteString("POPO")
	}

	parseOptions()

	if options.data < 1 {
		options.data = 1
	}

	if options.mode {
		log.Print("Expecting the server to mirror packets back")
	}
	if options.sendPktNum {
		log.Print("Inserting packet numbers into packet")
	}
	if options.debug {
		log.Print("Disabling TLS encryption")
	}
	if options.packets > 0 && options.data != 2000 {
		log.Print("Warning: Both the number of packets and the total amount of data is given. In this case the packet option takes precedence!")
	}

	// Calculate sending speed
	buf := calculateSpeed()
	buf = fillBuffer(buf, options.packets)

	connectAddr := options.connect + ":" + options.port
	conn := connectToDestination(connectAddr)
	defer conn.Close()
	sendPackets(conn, buf)

	log.Print("Client finished!")
}
