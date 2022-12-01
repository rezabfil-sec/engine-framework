/*
 * This program demonstrates transmission of UDP packets using the
 * system TAI timer.
 *
 * Copyright (C) 2017 linutronix GmbH
 *
 * Large portions taken from the linuxptp stack.
 * Copyright (C) 2011, 2012 Richard Cochran <richardcochran@gmail.com>
 *
 * Some portions taken from the sgd test program.
 * Copyright (C) 2015 linutronix GmbH
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 */
#define _GNU_SOURCE /*for CPU_SET*/
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <ifaddrs.h>
#include <linux/errqueue.h>
#include <linux/ethtool.h>
#include <linux/net_tstamp.h>
#include <linux/sockios.h>
#include <net/if.h>
#include <netinet/in.h>
#include <poll.h>
#include <pthread.h>
#include <sched.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#define ONE_SEC 1000000000ULL
#define DEFAULT_PERIOD 1000000
#define DEFAULT_DELAY 500000
#define DEFAULT_PRIORITY 3
#define DEST_IPADDR "10.0.0.1"
#define SERVER_RCV_PORT 7788
#define CLIENT_SEND_PORT 5566
#define MARKER 'a'

#ifndef SO_TXTIME
#define SO_TXTIME 61
#define SCM_TXTIME SO_TXTIME
#endif

#ifndef SO_EE_ORIGIN_TXTIME
#define SO_EE_ORIGIN_TXTIME 6
#define SO_EE_CODE_TXTIME_INVALID_PARAM 1
#define SO_EE_CODE_TXTIME_MISSED 2
#endif

#define pr_err(s) fprintf(stderr, s "\n")
#define pr_info(s) fprintf(stdout, s "\n")

/* The API for SO_TXTIME is the below struct and enum, which will be
 * provided by uapi/linux/net_tstamp.h in the near future.
 */
/*
struct sock_txtime {
	clockid_t clockid;
	uint16_t flags;
};

enum txtime_flags {
	SOF_TXTIME_DEADLINE_MODE = (1 << 0),
	SOF_TXTIME_REPORT_ERRORS = (1 << 1),

	SOF_TXTIME_FLAGS_LAST = SOF_TXTIME_REPORT_ERRORS,
	SOF_TXTIME_FLAGS_MASK = (SOF_TXTIME_FLAGS_LAST - 1) |
				 SOF_TXTIME_FLAGS_LAST
};
*/

static int running = 1, use_so_txtime = 1, send_tsn = 1;
static int period_nsec = DEFAULT_PERIOD;
static int waketx_delay = DEFAULT_DELAY;
static int so_priority = DEFAULT_PRIORITY;
static int server_rcv_port = SERVER_RCV_PORT;
static int client_snd_port = CLIENT_SEND_PORT;
static int use_deadline_mode = 0;
static int receive_errors = 0;
static uint64_t base_time = 0;
static struct sock_txtime sk_txtime;
static char *dest_addr = DEST_IPADDR;
__u64 *tx_timestamps;
__u64 *sched_timestamps;
__u64 *actual_timestamps;
int num_packets;
static void normalize(struct timespec *ts)
{
	while (ts->tv_nsec > 999999999)
	{
		ts->tv_sec += 1;
		ts->tv_nsec -= ONE_SEC;
	}

	while (ts->tv_nsec < 0)
	{
		ts->tv_sec -= 1;
		ts->tv_nsec += ONE_SEC;
	}
}

static int sk_interface_index(int fd, const char *name)
{
	struct ifreq ifreq;
	int err;

	memset(&ifreq, 0, sizeof(ifreq));
	strncpy(ifreq.ifr_name, name, sizeof(ifreq.ifr_name) - 1);
	err = ioctl(fd, SIOCGIFINDEX, &ifreq);
	if (err < 0)
	{
		pr_err("ioctl SIOCGIFINDEX failed: %m");
		return err;
	}
	return ifreq.ifr_ifindex;
}

static int open_socket(const char *name, short port, clockid_t clkid)
{
	struct sockaddr_in addr;
	int fd, index, on = 1;

	memset(&addr, 0, sizeof(addr));
	addr.sin_family = AF_INET;
	addr.sin_addr.s_addr = htonl(INADDR_ANY);
	addr.sin_port = htons(port);

	fd = socket(AF_INET, SOCK_DGRAM, 0);
	if (fd < 0)
	{
		pr_err("socket failed: %m");
		goto no_socket;
	}
	index = sk_interface_index(fd, name);
	if (index < 0)
		goto no_option;

	if (setsockopt(fd, SOL_SOCKET, SO_PRIORITY, &so_priority, sizeof(so_priority)))
	{
		pr_err("Couldn't set priority");
		goto no_option;
	}
	if (setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on)))
	{
		pr_err("setsockopt SO_REUSEADDR failed: %m");
		goto no_option;
	}
	if (bind(fd, (struct sockaddr *)&addr, sizeof(addr)))
	{
		pr_err("bind failed: %m");
		goto no_option;
	}
	if (setsockopt(fd, SOL_SOCKET, SO_BINDTODEVICE, name, strlen(name)))
	{
		pr_err("setsockopt SO_BINDTODEVICE failed: %m");
		goto no_option;
	}

	sk_txtime.clockid = clkid;
	sk_txtime.flags = (use_deadline_mode | receive_errors);
	if (use_so_txtime && setsockopt(fd, SOL_SOCKET, SO_TXTIME, &sk_txtime, sizeof(sk_txtime)))
	{
		pr_err("setsockopt SO_TXTIME failed: %m");
		goto no_option;
	}

	return fd;
no_option:
	close(fd);
no_socket:
	return -1;
}

static int udp_open(const char *name, clockid_t clkid)
{
	int fd;

	fd = open_socket(name, client_snd_port, clkid);

	return fd;
}

static int udp_send(int fd, void *buf, int len, __u64 txtime)
{
	char control[CMSG_SPACE(sizeof(txtime))] = {};
	struct sockaddr_in sin;
	struct cmsghdr *cmsg;
	struct msghdr msg;
	struct iovec iov;
	ssize_t cnt;

	memset(&sin, 0, sizeof(sin));
	sin.sin_family = AF_INET;
	sin.sin_port = htons(server_rcv_port);
	if (inet_aton(dest_addr, &sin.sin_addr) == 0)
	{
		fprintf(stderr, "inet_aton() failed\n");
		exit(-1);
	}

	iov.iov_base = buf;
	iov.iov_len = len;

	memset(&msg, 0, sizeof(msg));
	msg.msg_name = &sin;
	msg.msg_namelen = sizeof(sin);
	msg.msg_iov = &iov;
	msg.msg_iovlen = 1;

	/*
	 * We specify the transmission time in the CMSG.
	 */
	if (use_so_txtime)
	{
		msg.msg_control = control;
		msg.msg_controllen = sizeof(control);

		cmsg = CMSG_FIRSTHDR(&msg);
		cmsg->cmsg_level = SOL_SOCKET;
		cmsg->cmsg_type = SCM_TXTIME;
		cmsg->cmsg_len = CMSG_LEN(sizeof(__u64));
		*((__u64 *)CMSG_DATA(cmsg)) = txtime;
	}
	cnt = sendmsg(fd, &msg, 0);
	if (cnt < 1)
	{
		pr_err("sendmsg failed: %m");
		return cnt;
	}
	return cnt;
}

static unsigned char tx_buffer[256];
char *file_name = NULL;
static unsigned int num_missed_deadline = 0;
static unsigned int num_invalid_params = 0;
static __u64 missed_deadline_tx_timestamp[1000];
static __u64 invalid_params_tx_timestamp[1000];
static unsigned int num_timestamps = 0;

static int process_socket_error_queue(int fd)
{
	uint8_t msg_control[CMSG_SPACE(sizeof(struct sock_extended_err))];
	unsigned char err_buffer[sizeof(tx_buffer)];
	struct sock_extended_err *serr;
	struct cmsghdr *cmsg;
	__u64 tstamp = 0;

	struct iovec iov = {
		.iov_base = err_buffer,
		.iov_len = sizeof(err_buffer)};
	struct msghdr msg = {
		.msg_iov = &iov,
		.msg_iovlen = 1,
		.msg_control = msg_control,
		.msg_controllen = sizeof(msg_control)};

	if (recvmsg(fd, &msg, MSG_ERRQUEUE) == -1)
	{
		pr_err("recvmsg failed");
		return -1;
	}

	cmsg = CMSG_FIRSTHDR(&msg);
	while (cmsg != NULL)
	{
		serr = (void *)CMSG_DATA(cmsg);
		if (serr->ee_origin == SO_EE_ORIGIN_TXTIME)
		{
			tstamp = ((__u64)serr->ee_data << 32) + serr->ee_info;

			switch (serr->ee_code)
			{
			case SO_EE_CODE_TXTIME_INVALID_PARAM:
				// fprintf(stderr, "packet with tstamp %llu dropped due to invalid params\n", tstamp);
				fprintf(stderr, "*");
				invalid_params_tx_timestamp[num_invalid_params++] = tstamp;
				return 0;
			case SO_EE_CODE_TXTIME_MISSED:
				//fprintf(stderr, "packet with tstamp %llu dropped due to missed deadline\n", tstamp);
				fprintf(stderr, "*");
				missed_deadline_tx_timestamp[num_missed_deadline++] = tstamp;
				return 0;
			default:
				return -1;
			}
		}

		cmsg = CMSG_NXTHDR(&msg, cmsg);
	}

	return 0;
}

void sigint_handler(int s)
{
	struct timespec ts, actual_ts;
	int cnt, err, i, j = 0, k, index;
	__u64 txtime, base_ts, invalid_param_ts, missed_deadline_ts;
	FILE *fd;

	fd = fopen(file_name, "w");

	fprintf(stderr, "\nCaught signal %d - Writing packet log...", s);

	fprintf(fd, "Missed Deadline\n");
	for (i = 0; i < num_missed_deadline; i++)
	{
		index = 0;
		for (j = 0; j < num_packets; j++)
		{
			if (tx_timestamps[j] == missed_deadline_tx_timestamp[i])
			{
				index = j;
			}
		}
		fprintf(fd, "%u,%llu,\n", index, missed_deadline_tx_timestamp[i] - base_ts);
	}
	fprintf(fd, "Invalid Params\n");
	for (i = 0; i < num_invalid_params; i++)
	{
		index = 0;
		for (j = 0; j < num_packets; j++)
		{
			if (tx_timestamps[j] == invalid_params_tx_timestamp[i])
			{
				index = j;
			}
		}
		fprintf(fd, "%u,%llu,\n", index, invalid_params_tx_timestamp[i] - base_ts);
	}

	base_ts = (sched_timestamps[0] / 100000000000ULL) * 100000000000ULL;
	fprintf(fd, "Sched,Actual,Transmit, %u\n", num_timestamps);
	for (i = 0; i < num_packets; i++)
	{
		j = i + 1;
		if (sched_timestamps[j] != 0)
		{
			missed_deadline_ts = base_ts; // means that 0 gets printed out if the packet didn't drop
			for (k = 0; k < num_missed_deadline; k++)
			{
				if (tx_timestamps[j] == missed_deadline_tx_timestamp[k])
				{
					missed_deadline_ts = tx_timestamps[j];
				}
			}
			invalid_param_ts = base_ts; // means that 0 gets printed out if the packet didn't drop
			for (k = 0; k < num_invalid_params; k++)
			{
				if (tx_timestamps[j] == invalid_params_tx_timestamp[k])
				{
					invalid_param_ts = tx_timestamps[j];
				}
			}
			fprintf(fd, "%d,%llu,%llu,%llu,%llu,%llu\n", j, sched_timestamps[j] - base_ts, actual_timestamps[j] - base_ts, tx_timestamps[j] - base_ts, missed_deadline_ts - base_ts, invalid_param_ts - base_ts);
		}
	}
	free(tx_timestamps);
	free(sched_timestamps);
	free(actual_timestamps);
	fclose(fd);
	fprintf(stderr, "Done\n\n");
	exit(0);
}

static int run_nanosleep(clockid_t clkid, int fd)
{
	struct timespec ts, actual_ts;
	int cnt, err, i, j, k, index, num;
	__u64 txtime, base_tc, invalid_param_ts, missed_deadline_ts, actual_time;

	tx_timestamps = malloc(sizeof *tx_timestamps * num_packets);
	sched_timestamps = malloc(sizeof *sched_timestamps * num_packets);
	actual_timestamps = malloc(sizeof *actual_timestamps * num_packets);

	if (!tx_timestamps || !sched_timestamps || !actual_timestamps)
	{
		pr_err("Arrays not allocated correctly.");
		return -1;
	}
	struct pollfd p_fd = {
		.fd = fd,
	};

	memset(tx_buffer, MARKER, sizeof(tx_buffer));

	/* If no base-time was specified, start one to two seconds in the
	 * future.
	 */
	if (base_time == 0)
	{
		clock_gettime(clkid, &ts);
		ts.tv_sec += 1;
		ts.tv_nsec = ONE_SEC - waketx_delay;
	}
	else
	{
		ts.tv_sec = base_time / ONE_SEC;
		ts.tv_nsec = (base_time % ONE_SEC) - waketx_delay;
	}

	normalize(&ts);

	txtime = ts.tv_sec * ONE_SEC + ts.tv_nsec;
	txtime += waketx_delay;

	fprintf(stderr, "\ntxtime of 1st packet is: %llu\n", txtime);
	num = 0;

	while (running)
	{
		if (!send_tsn)
		{
			clock_gettime(clkid, &ts);
			normalize(&ts);
			txtime = ts.tv_sec * ONE_SEC + ts.tv_nsec;
		}
		memcpy(tx_buffer, &txtime, sizeof(__u64));
		err = clock_nanosleep(clkid, TIMER_ABSTIME, &ts, NULL);
		switch (err)
		{
		case 0:
			clock_gettime(clkid, &actual_ts);
			// Real clock time to see the RTT for other modes
			normalize(&actual_ts);
			// |timestamp_sec|timestamp_micro|sequence_num| each 4B in case of Iperf3, for us 8B, 4B
			actual_time = actual_ts.tv_sec * ONE_SEC + actual_ts.tv_nsec;
			// 4B sequence number
			memcpy(tx_buffer + 8, &num, sizeof(int));
			// Additional 8B closer to send
			memcpy(tx_buffer + 12, &actual_time, sizeof(__u64));
			
			cnt = udp_send(fd, tx_buffer, sizeof(tx_buffer), txtime);
			if (cnt != sizeof(tx_buffer))
			{
				pr_err("udp_send failed");
			}
			tx_timestamps[num_timestamps] = txtime;
			sched_timestamps[num_timestamps] = ts.tv_sec * ONE_SEC + ts.tv_nsec;
			actual_timestamps[num_timestamps++] = actual_time;
			if (num_timestamps == (num_packets - 1))
			{
				num_timestamps = 0;
			}

			ts.tv_nsec += period_nsec;
			normalize(&ts);
			txtime += period_nsec;

			/* Check if errors are pending on the error queue. */
			err = poll(&p_fd, 1, 0);
			if (err == 1 && p_fd.revents & POLLERR)
			{
				if (process_socket_error_queue(fd))
					return -ECANCELED;
			}
			// Adding sleep, otherwise sends too fast to process on the other side
			if (!send_tsn)
			{
				sleep(0.001);
			}
			num++;
			if (num >= num_packets)
			{
				running = 0;
			}

			break;
		case EINTR:
			continue;
		default:
			fprintf(stderr, "clock_nanosleep returned %d: %s",
					err, strerror(err));
			return err;
		}
	}

	return 0;
}

static int set_realtime(pthread_t thread, int priority, int cpu)
{
	cpu_set_t cpuset;
	struct sched_param sp;
	int err, policy;

	int min = sched_get_priority_min(SCHED_FIFO);
	int max = sched_get_priority_max(SCHED_FIFO);

	fprintf(stderr, "min %d max %d\n", min, max);

	if (priority < 0)
	{
		return 0;
	}

	err = pthread_getschedparam(thread, &policy, &sp);
	if (err)
	{
		fprintf(stderr, "pthread_getschedparam: %s\n", strerror(err));
		return -1;
	}

	sp.sched_priority = priority;

	err = pthread_setschedparam(thread, SCHED_FIFO, &sp);
	if (err)
	{
		fprintf(stderr, "pthread_setschedparam: %s\n", strerror(err));
		return -1;
	}

	if (cpu < 0)
	{
		return 0;
	}
	CPU_ZERO(&cpuset);
	CPU_SET(cpu, &cpuset);
	err = pthread_setaffinity_np(thread, sizeof(cpu_set_t), &cpuset);
	if (err)
	{
		fprintf(stderr, "pthread_setaffinity_np: %s\n", strerror(err));
		return -1;
	}

	return 0;
}

static void usage(char *progname)
{
	fprintf(stderr,
			"\n"
			"usage: %s [options]\n"
			"\n"
			" -c [num]      run on CPU 'num'\n"
			" -d [num]      delta from wake up to txtime in nanoseconds (default %d)\n"
			" -h            prints this message and exits\n"
			" -i [name]     use network interface 'name'\n"
			" -n [num]      number of packets to send\n"
			" -p [num]      run with RT priorty 'num'\n"
			" -P [num]      period in nanoseconds (default %d)\n"
			" -s            do not use SO_TXTIME\n"
			" -r            use sysclock as send time in payload\n"
			" -t [num]      set SO_PRIORITY to 'num' (default %d)\n"
			" -D            set deadline mode for SO_TXTIME\n"
			" -E            enable error reporting on the socket error queue for SO_TXTIME\n"
			" -b [tstamp]   txtime of 1st packet as a 64bit [tstamp]. Default: now + ~2seconds\n"
			" -u [port]     use udp port server side 'port'\n"
			" -U [port]     use udp port client side 'port'\n"
			" -f [name]     provide file name\n"
			" -S [IP]       provide destination IP address\n"
			"\n",
			progname, DEFAULT_DELAY, DEFAULT_PERIOD, DEFAULT_PRIORITY);
}

int main(int argc, char *argv[])
{
	int c, cpu = -1, err, fd, priority = -1;
	clockid_t clkid = CLOCK_TAI;
	char *iface = NULL, *progname;
	int num_packets_in = 60000;
	signal(SIGINT, sigint_handler);

	/* Process the command line arguments. */
	progname = strrchr(argv[0], '/');
	progname = progname ? 1 + progname : argv[0];
	while (EOF != (c = getopt(argc, argv, "c:d:hi:n:p:P:st:DEb:u:rU:f:S:")))
	{
		switch (c)
		{
		case 'c':
			cpu = atoi(optarg);
			break;
		case 'd':
			waketx_delay = atoi(optarg);
			break;
		case 'h':
			usage(progname);
			return 0;
		case 'i':
			iface = optarg;
			break;
		case 'n':
			num_packets_in = atoi(optarg);
			break;
		case 'p':
			priority = atoi(optarg);
			break;
		case 'P':
			period_nsec = atoi(optarg);
			break;
		case 's':
			use_so_txtime = 0;
			break;
		case 'r':
			send_tsn = 0;
			break;
		case 't':
			so_priority = atoi(optarg);
			break;
		case 'D':
			use_deadline_mode = SOF_TXTIME_DEADLINE_MODE;
			break;
		case 'E':
			receive_errors = SOF_TXTIME_REPORT_ERRORS;
			break;
		case 'b':
			base_time = atoll(optarg);
			break;
		case 'u':
			server_rcv_port = atoi(optarg);
			break;
		case 'U':
			client_snd_port = atoi(optarg);
			break;
		case 'f':
			file_name = optarg;
			break;
		case 'S':
			dest_addr = optarg;
			break;
		case '?':
			usage(progname);
			return -1;
		}
	}
	printf("Sending to IP address %s and port %d \n", dest_addr, server_rcv_port);
	if (num_packets_in >= 0)
	{
		num_packets = num_packets_in;
	}
	else
	{
		pr_err("Number of packets is negative.");
		usage(progname);
		return -1;
	}
	if (waketx_delay > 999999999 || waketx_delay < 0)
	{
		pr_err("Bad wake up to transmission delay.");
		usage(progname);
		return -1;
	}

	if (period_nsec < 1000)
	{
		pr_err("Bad period.");
		usage(progname);
		return -1;
	}

	if (!iface)
	{
		pr_err("Need a network interface.");
		usage(progname);
		return -1;
	}

	if (set_realtime(pthread_self(), priority, cpu))
	{
		return -1;
	}

	fd = udp_open(iface, clkid);
	if (fd < 0)
	{
		return -1;
	}
	if (send_tsn)
	{
		printf("Sending response TSN\n");
	}

	err = run_nanosleep(clkid, fd);

	close(fd);
	sigint_handler(err);
	return err;
}