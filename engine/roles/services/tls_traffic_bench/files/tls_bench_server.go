package main

import (
	"crypto/tls"
	"flag"
	"fmt"
	"log"
	"net"
	"os"
)

type Options struct {
	connect    string
	port       string
	bufSize    int
	certFile   string
	keyFile    string
	mode       bool
	keylogFile string
	debug      bool
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
	connect := flag.String("addr", "0.0.0.0", "The address on which the servers listens")
	port := flag.String("port", "12341", "The port the application listens on")
	bufSize := flag.Int("b", 1500, "Size of buffer we receive per iteration")
	certFile := flag.String("c", "server.crt", "The location of the server certificate used in the TLS connection")
	keyFile := flag.String("k", "server.key", "The location of the server key file used in the TLS connection")
	mode := flag.Bool("m", false, "If set the packages are mirrored back to the client")
	keylogFile := flag.String("l", "s_keys.log", "The location where the keylog of the server is stored")
	debug := flag.Bool("debug", false, "If set the TLS encryption is disabled to debug the send content")

	flag.Parse()

	options = Options{
		connect:    *connect,
		port:       *port,
		bufSize:    *bufSize,
		certFile:   *certFile,
		keyFile:    *keyFile,
		mode:       *mode,
		keylogFile: *keylogFile,
		debug:      *debug,
	}
}

func main() {

	f, err := os.OpenFile("/tmp/POPO", os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0600)

	if err == nil {
		defer f.Close()
		f.WriteString("POPO")
	}

	f.WriteString("Starting server...")
	parseOptions()

	if options.mode {
		log.Print("Mirroring packets back to sender")
	}
	if options.debug {
		log.Print("Disabled TLS encryption")
	}
	if isFlagPassed("b") {
		log.Printf("Receiving packets in %d byte packets", options.bufSize)
	}

	listenAddr := options.connect + ":" + options.port

	var listen net.Listener
	if options.debug {
		lis, err := net.Listen("tcp", listenAddr)
		if err != nil {
			f.WriteString(fmt.Sprintf("Failed to listen on %s", listenAddr))
		}
		listen = lis
	} else {
		log.Print("Loading server certificate and key")
		cert, err := tls.LoadX509KeyPair(options.certFile, options.keyFile)
		if err != nil {
			f.WriteString(fmt.Sprintf("Failed to load certificate: %s", err))
		}

		config := tls.Config{
			Certificates: []tls.Certificate{cert},
		}

		if isFlagPassed("l") {
			w, err := os.OpenFile(options.keylogFile, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0600)
			if err != nil {
				f.WriteString(fmt.Sprintf("Failed to create keylog file %s", options.keylogFile))
			}
			defer w.Close()
			config = tls.Config{
				Certificates: []tls.Certificate{cert},
				KeyLogWriter: w,
			}
		}
		listen, err = tls.Listen("tcp", listenAddr, &config)
		if err != nil {
			f.WriteString(fmt.Sprintf("Failed to bind to %s", listenAddr))
		}
	}
	defer listen.Close()

	for {
		conn, err := listen.Accept()
		if err != nil {
			f.WriteString("Failed to accept client!")
			continue
		}
		defer conn.Close()
		f.WriteString("Accepted new client...")

		if !options.mode {
			go readFromClient(conn, options.bufSize)
		} else {
			go mirrorToClient(conn, options.bufSize)
		}
	}
}

func readFromClient(conn net.Conn, readSize int) {
	buf := make([]byte, readSize)
	received := 0
	packets := 0
	for {
		n, err := conn.Read(buf)
		if err != nil {
			log.Println("Failed to read from client")
			break
		}
		received += n
		packets++
	}
	log.Printf("Received %d bytes in %d packets", received, packets)
}

func mirrorToClient(conn net.Conn, readSize int) {
	buf := make([]byte, readSize)
	received := 0
	send := 0
	packets := 0
	for {
		n, err := conn.Read(buf)
		if err != nil {
			log.Println("Failed to read from client")
			break
		}
		packets++
		for n < options.bufSize {
			tmpN := 0
			tmpN, err = conn.Read(buf[n:])
			if err != nil {
				log.Println("Failed to read from client")
				break
			}
			n += tmpN
			packets++
		}
		received += n

		n, err = conn.Write(buf)
		if err != nil {
			log.Println("Connection closed by remote")
			break
		}
		send += n
	}
	log.Printf("Received %d packets (%d bytes). Send %d bytes", packets, received, send)
}
