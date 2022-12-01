#define _GNU_SOURCE
#include <stdlib.h>
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <netdb.h>
#include <sched.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/ioctl.h>
#include <sys/types.h>
#include <arpa/inet.h>
#include <time.h>
#include <poll.h>
#include <pthread.h>
#include <string.h>
#include <linux/sockios.h>
#include <linux/net_tstamp.h>
#include <linux/ethtool.h>
#include <linux/errqueue.h>
#include <net/if.h>
#include <netinet/in.h>
#include <unistd.h>
#include <ifaddrs.h>
#include <fcntl.h>
#include <signal.h>

#define ONE_SEC 1000000000ULL
#define DEFAULT_PERIOD 1000000
#define DEFAULT_DELAY 200000 // 200us
#define DEFAULT_PRIORITY 3

#define BUFSIZE 2048
#define SERVER_RCV_PORT 7788

#define MARKER_1 'a'
#define MARKER_2 'b'
#define MARKER_3 'c'

#ifndef SO_TXTIME
#define SO_TXTIME 61
#define SCM_TXTIME SO_TXTIME
#endif

static int send_tsn = 0, use_so_txtime = 1;
static int running = 1;
static uint64_t base_time = 0;
static int waketx_delay = DEFAULT_DELAY;
static int period_nsec = DEFAULT_PERIOD;
static int so_priority = DEFAULT_PRIORITY;
static int udp_port = SERVER_RCV_PORT;
static int use_deadline_mode = 0;
static int receive_errors = 0;
static struct sock_txtime sk_txtime;
__u64 *tx_timestamps;
__u64 *sched_timestamps;
__u64 *actual_timestamps;
int num_packets = 61000;

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
        perror("ioctl SIOCGIFINDEX failed: %m");
        return err;
    }
    return ifreq.ifr_ifindex;
}

static int open_socket(const char *name, clockid_t clkid, struct sockaddr_in socket_str)
{
    int socket_fd, index, on = 1;
    //struct sockaddr_in socket_str;
    int flags;

    flags = SOF_TIMESTAMPING_TX_HARDWARE | SOF_TIMESTAMPING_TX_SOFTWARE | SOF_TIMESTAMPING_RX_HARDWARE | SOF_TIMESTAMPING_RX_SOFTWARE | SOF_TIMESTAMPING_SOFTWARE | SOF_TIMESTAMPING_RAW_HARDWARE;

    //new stuff for HW timestamping

    /* create a UDP socket */
    // Might need to be changed to listen on any IP any any port
    memset((char *)&socket_str, 0, sizeof(socket_str));
    socket_str.sin_family = AF_INET;
    socket_str.sin_addr.s_addr = htonl(INADDR_ANY);
    socket_str.sin_port = htons(udp_port);

    socket_fd = socket(PF_INET, SOCK_DGRAM, 0);
    if (socket_fd < 0)
    {
        perror("socket failed: %m");
        goto no_socket;
    }
    index = sk_interface_index(socket_fd, name);
    if (index < 0)
        goto no_option;

    if (setsockopt(socket_fd, SOL_SOCKET, SO_PRIORITY, &so_priority, sizeof(so_priority)))
    {
        perror("Couldn't set priority");
        goto no_option;
    }
    if (setsockopt(socket_fd, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on)))
    {
        perror("setsockopt SO_REUSEADDR failed: %m");
        goto no_option;
    }
    if (setsockopt(socket_fd, SOL_SOCKET, SO_TIMESTAMPING, &flags, sizeof(flags)) < 0)
    {
        perror("cannot create socket opt\n");
        return 0;
    }
    // can cause issues
    if (bind(socket_fd, (struct sockaddr *)&socket_str, sizeof(socket_str)))
    {
        perror("bind failed: %m");
        goto no_option;
    }
    if (setsockopt(socket_fd, SOL_SOCKET, SO_BINDTODEVICE, name, strlen(name)))
    {
        perror("setsockopt SO_BINDTODEVICE failed: %m");
        goto no_option;
    }

    sk_txtime.clockid = clkid;
    sk_txtime.flags = (use_deadline_mode | receive_errors);
    if (use_so_txtime && setsockopt(socket_fd, SOL_SOCKET, SO_TXTIME, &sk_txtime, sizeof(sk_txtime)))
    {
        perror("setsockopt SO_TXTIME failed: %m");
        goto no_option;
    }

    return socket_fd;
no_option:
    close(socket_fd);
no_socket:
    return -1;
}

static unsigned char tx_buffer[256];
static unsigned int num_missed_deadline = 0;
static unsigned int num_invalid_params = 0;
static __u64 missed_deadline_tx_timestamp[1000];
static __u64 invalid_params_tx_timestamp[1000];
static unsigned int num_timestamps = 0;
char *file_name = NULL;
static int process_socket_error_queue(int fd)
{
    uint8_t msg_control[CMSG_SPACE(sizeof(struct sock_extended_err))];
    unsigned char err_buffer[sizeof(BUFSIZE / 8)];
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
        perror("recvmsg failed");
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
    int cnt, err, i, j, k, index;
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
    fprintf(fd, "Sched,Actual,Transmit, %u\n", num_packets);
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

static int udp_recv(int recv_fd, __u64 *HW_time, __u64 *sys_time, unsigned char *buf, size_t buf_size, struct sockaddr_in forwarder_in)
{
    int recvMsgSize, level, type;
    struct timespec arrival_time;

    //All info for recvmsg
    struct msghdr msg_receive;
    struct iovec iov_receive;
    char ctrl[BUFSIZE];
    iov_receive.iov_base = buf;
    iov_receive.iov_len = buf_size;
    msg_receive.msg_control = (char *)ctrl;
    msg_receive.msg_controllen = sizeof(ctrl);
    msg_receive.msg_name = &forwarder_in;
    msg_receive.msg_namelen = sizeof(forwarder_in);
    msg_receive.msg_iov = &iov_receive;
    msg_receive.msg_iovlen = 1;

    recvMsgSize = recvmsg(recv_fd, &msg_receive, 0);
    if (recvMsgSize > 0)
    {
        clock_gettime(CLOCK_REALTIME, &arrival_time);
        *sys_time = arrival_time.tv_sec * ONE_SEC + arrival_time.tv_nsec;
        for (struct cmsghdr *cmsg = CMSG_FIRSTHDR(&msg_receive); cmsg; cmsg = CMSG_NXTHDR(&msg_receive, cmsg))
        {
            level = cmsg->cmsg_level;
            type = cmsg->cmsg_type;

            if (level == SOL_IP && type == IP_RECVERR)
            {
                struct sock_extended_err *ext =
                    (struct sock_extended_err *)CMSG_DATA(cmsg);
                continue;
            }
            if (level != SOL_SOCKET)
                continue;

            switch (type)
            {
            case SO_TIMESTAMPNS:
            {
                struct scm_timestamping *ts = (struct scm_timestamping *)CMSG_DATA(cmsg);
            }
            break;
            // We are mostly here!
            // Queue infos: 0. SO_TIMESTAMPING, 1. HW transformed, 2. HW raw
            // https://github.com/spotify/linux/blob/master/Documentation/networking/timestamping/timestamping.c
            case SO_TIMESTAMPING:
            {
                struct scm_timestamping *ts = (struct scm_timestamping *)CMSG_DATA(cmsg);

                *HW_time = ts->ts[2].tv_sec * ONE_SEC + ts->ts[2].tv_nsec;
            }
            break;
            default:
                printf("other cmsg options\n");
                break;
            }
        }
        return 1;
    }
    else
    {
        printf("uh oh - something went wrong with receiving!\n");
        return -1;
    }
}

//Send
static int udp_send(int send_fd, clockid_t clkid, __u64 HW_time, __u64 sys_time, unsigned char *buf, size_t buf_size, __u64 *tx_time_TSN, __u64 *tx_time_SW, struct sockaddr_in forwarder_out)
{

    int actuallySendMsgSize, err; /* length of actually send bytes */
    struct timespec ts;
    struct pollfd p_fd = {
        .fd = send_fd,
    };
    __u64 send_time;
    char control[CMSG_SPACE(sizeof(send_time))] = {};
    struct cmsghdr *cmsg_send;
    struct msghdr msg_send;
    struct iovec iov_send;
    unsigned char buf_forward[BUFSIZE / 8]; /* send buffer */
    ssize_t cnt;

    iov_send.iov_base = buf_forward;
    iov_send.iov_len = sizeof(buf_forward);

    memset(&msg_send, 0, sizeof(msg_send));
    // Here might need to change
    msg_send.msg_name = &forwarder_out;
    msg_send.msg_namelen = sizeof(forwarder_out);
    msg_send.msg_iov = &iov_send;
    msg_send.msg_iovlen = 1;

    // CLOCK REALTIME is the best option for us since it should be sync with HW timestampt due to php2sys
    // https://www.cs.rutgers.edu/~pxk/416/notes/c-tutorials/gettime.html
    // https://standards.ieee.org/content/dam/ieee-standards/standards/web/documents/other/d2-05_ong_comparative_analysis_of_precision_time_protocol.pdf
    // Format of .tv_sec - second since epoch (tv_nsec before decimal point and tv_nsec after decimal point)

    // Form a response payload
    memset(buf_forward, MARKER_1, sizeof(buf_forward));

    // 4 timestamps - sent client, arrival tstamp, process tstamp, control send TSN or time right before send
    // | send tstamp | 8B markers 'a' | sys tstamp | 8B markers 'b' | HW timestamp | 8B markers 'c' | send tstamp | 'a' until 256 |
    // starting with first 3
    // memcpy first few bytes
    // For now uncomment
    // memcpy(buf_response, buf, 16);
    // // copy systime - 8B
    // memcpy(buf_response + 16, &sys_time, sizeof(__u64));
    // // Set marker fields - 8B
    // memset(buf_response + 24, MARKER_2, sizeof(__u64));
    // // copy HW time - 8B
    // memcpy(buf_response + 32, &HW_time, sizeof(__u64));
    // //Null chars at the end of both payloads
    // buf_response[BUFSIZE / 8] = 0;

    // Prepare stuff for sendmsg, https://stackoverflow.com/questions/47313383/linux-udp-datagrams-and-kernel-timestamps-lots-of-examples-and-stackoversflow?noredirect=1&lq=1
    // Set response buf to 'a'

    size_t numOfElements = sizeof(buf_forward);
    //TSN
    tx_time_TSN = HW_time;
    tx_time_TSN += waketx_delay;

    //Normal
    clock_gettime(clkid, &ts);
    normalize(&ts);
    tx_time_SW = ts.tv_sec * ONE_SEC + ts.tv_nsec;

    // Add final marker
    // memset(buf_response + 40, MARKER_3, sizeof(__u64));
    // Add send time
    // if (!send_tsn)
    // {
    //     memcpy(buf_response + 48, &tx_time_SW, sizeof(__u64));
    // }
    // else
    // {
    //     memcpy(buf_response + 48, &tx_time_TSN, sizeof(__u64));
    // }
    err = clock_nanosleep(clkid, TIMER_ABSTIME, &ts, NULL);
    switch (err)
    {
    case 0:
        if (use_so_txtime)
        {
            msg_send.msg_control = control;
            msg_send.msg_controllen = sizeof(control);

            cmsg_send = CMSG_FIRSTHDR(&msg_send);
            cmsg_send->cmsg_level = SOL_SOCKET;
            cmsg_send->cmsg_type = SCM_TXTIME;
            cmsg_send->cmsg_len = CMSG_LEN(sizeof(__u64));
            *((__u64 *)CMSG_DATA(cmsg_send)) = tx_time_TSN;
        }
        actuallySendMsgSize = sendmsg(send_fd, &msg_send, 0);
        if (actuallySendMsgSize < 0)
        {
            perror("Send msg");
        }
        else if (actuallySendMsgSize < numOfElements)
        {
            perror("Not all msg send");
        }
        // /* Check if errors are pending on the error queue. */
        err = poll(&p_fd, 1, 0);
        if (err == 1 && p_fd.revents & POLLERR)
        {
            if (process_socket_error_queue(send_fd))
                return -ECANCELED;
        }

        break;
    case EINTR:
        break;
    default:
        fprintf(stderr, "clock_nanosleep returned %d: %s",
                err, strerror(err));
        return err;
    }
    return 1;
}

static int run_forwarder(clockid_t clkid, int recv_fd, int send_fd, struct sockaddr_in forwarder_in, struct sockaddr_in forwarder_out)
{ // other values

    struct timespec arrival_time, ts;
    __u64 sys_time, HW_time, tx_time_TSN, tx_time_SW; // Timestamps
    int level, type, err, num;
    unsigned char buf[BUFSIZE];
    int recvMsgSize; /* length of received bytes */

    num = 0;
    /* now loop, receiving data and printing what we received */
    printf("waiting on port %d\n", udp_port);
	tx_timestamps = malloc(sizeof *tx_timestamps * num_packets);
	sched_timestamps = malloc(sizeof *sched_timestamps * num_packets);
	actual_timestamps = malloc(sizeof *actual_timestamps * num_packets);

	if (!tx_timestamps || !sched_timestamps || !actual_timestamps)
	{
		perror("Arrays not allocated correctly.");
		return -1;
	}

    while (running)
    {
        // Work rcv

        err = udp_recv(recv_fd, &HW_time, &sys_time, buf, sizeof(buf), forwarder_in);
        err = udp_send(send_fd, clkid, HW_time, sys_time, buf, sizeof(buf), &tx_time_TSN, &tx_time_SW, forwarder_out);
        
        tx_timestamps[num_timestamps] = tx_time_TSN; //
        sched_timestamps[num_timestamps] = tx_time_TSN;
        actual_timestamps[num_timestamps++] = tx_time_SW; //Sys tstamp

        if (num_timestamps == (num_packets - 1))
        {
            num_timestamps = 0;
        }
        num++;
        if (num >= num_packets)
        {
            running = 0;
        }
    }
    return 0;
}

static void usage(char *progname)
{
    fprintf(stderr,
            "\n"
            "usage: %s [options]\n"
            "\n"

            " -d [num]      delay when the packet should be sent if TSN mode active (default %d)\n"
            " -h            prints this message and exits\n"
            " -i [name]     use network interface to listen 'name'\n"
            " -I [name]     use network interface to send 'name'\n"
            " -n [num]      number of packets to send\n"
            " -p [num]      run with RT priorty 'num'\n"
            " -P [num]      period in nanoseconds (default %d)\n"
            " -s            do not use SO_TXTIME\n"
            " -r            use TSN method on response\n"
            " -t [num]      set SO_PRIORITY to 'num' (default %d)\n"
            " -D            set deadline mode for SO_TXTIME\n"
            " -E            enable error reporting on the socket error queue for SO_TXTIME\n"
            " -b [tstamp]   txtime of 1st packet as a 64bit [tstamp]. Default: now + ~2seconds\n"
            " -U [port]     use udp port 'port'\n"
            " -f [name]     provide file name\n"
            "\n",
            progname, DEFAULT_DELAY, DEFAULT_PERIOD, DEFAULT_PRIORITY);
}

int main(int argc, char **argv)
{
    int recv_fd, send_fd, priority = -1; /* server socket */
    int c, err;
    clockid_t clkid = CLOCK_TAI;
    char *iface_in = NULL, *progname;
    char *iface_out = NULL;
    int num_packets_in = 60000;
    signal(SIGINT, sigint_handler);
    struct sockaddr_in forwarder_in, forwarder_out;
    /* Process the command line arguments. */
    progname = strrchr(argv[0], '/');
    progname = progname ? 1 + progname : argv[0];
    while (EOF != (c = getopt(argc, argv, "d:hi:I:n:p:P:srt:DEb:U:f:")))
    {
        switch (c)
        {
        case 'd':
            waketx_delay = atoi(optarg);
            break;
        case 'h':
            usage(progname);
            return 0;
        case 'i':
            iface_in = optarg;
            break;
        case 'I':
            iface_out = optarg;
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
            // if 0 no TSN features!
            use_so_txtime = 0;
            break;
        case 'r':
            // Use TSN for response
            send_tsn = 1;
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
        case 'U':
            udp_port = atoi(optarg);
            break;
        case 'f':
            file_name = optarg;
            break;
        case '?':
            usage(progname);
            return -1;
        }
    }
    if (num_packets_in >= 0)
	{
		num_packets = num_packets_in;
	}
	else
	{
		perror("Number of packets is negative.");
		usage(progname);
		return -1;
	}

    if (!iface_in || !iface_out)
    {
        perror("Need a network interface.");
        usage(progname);
        return -1;
    }
    // Setup socket
    // Needs two sockets
    recv_fd = open_socket(iface_in, clkid, forwarder_in);
    send_fd = open_socket(iface_out, clkid, forwarder_out);
    if (recv_fd < 0 || send_fd < 0 )
    {
        return -1;
    }

    if (send_tsn)
    {
        printf("Forwarding TSN\n");
    }
    // Change to run forwarder
    err = run_forwarder(clkid, recv_fd, send_fd, forwarder_in, forwarder_out);

    close(recv_fd);
    close(send_fd);
    sigint_handler(err);
}