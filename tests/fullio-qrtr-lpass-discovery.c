/* Bounded LPASS DIAG. Optional capture uses only log 0x1586, writes only
 * records with wire tap IDs 1 through 4, and sends a zero mask on exit.
 * No command-channel writes, external socket, or other subsystem registration.
 * Service/version assignments: linux-msm/diag 23c12c167e93, peripheral-qrtr.c.
 */
#include <endian.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/qrtr.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define DIAG_SERVICE 4097u
#define LPASS_COMMAND 65u
#define LPASS_NODE 5u
#define FEATURE 8u
#define DIAG_ID 33u
#define REFERENCE_LPASS_FEATURES 0x000bbef7u
#define REFERENCE_ROUTER_FEATURES 0x0008a053u
#define TAP_LOG_ITEM 0x586u
#define CAPTURE_SECONDS 4u
static volatile sig_atomic_t cancelled;

static void request_stop(int sig)
{
	(void)sig;
	cancelled = 1;
}

static int control_socket(unsigned int type, unsigned int version, uint32_t *node)
{
	struct sockaddr_qrtr local = { 0 };
	struct qrtr_ctrl_pkt pkt = { .cmd = htole32(type) };
	socklen_t len = sizeof(local);
	int fd = socket(AF_QIPCRTR, SOCK_DGRAM | SOCK_CLOEXEC, 0);

	if (fd < 0)
		return -1;
	if (getsockname(fd, (struct sockaddr *)&local, &len) < 0 || len != sizeof(local))
		goto failed;
	*node = local.sq_node;
	local.sq_port = QRTR_PORT_CTRL;
	pkt.server.service = htole32(DIAG_SERVICE);
	pkt.server.instance = htole32(version);
	if (sendto(fd, &pkt, sizeof(pkt), MSG_DONTWAIT, (struct sockaddr *)&local,
		   sizeof(local)) != sizeof(pkt))
		goto failed;
	return fd;
failed:
	{
		int saved = errno;
		close(fd);
		errno = saved;
	}
	return -1;
}

static uint32_t word(const unsigned char *p)
{
	uint32_t value;

	memcpy(&value, p, sizeof(value));
	return le32toh(value);
}

static void put_word(unsigned char *p, uint32_t value)
{
	value = htole32(value);
	memcpy(p, &value, sizeof(value));
}

static int reply_feature(int fd, const struct sockaddr_qrtr *peer, uint32_t offered)
{
	unsigned char message[18] = { 0 };
	ssize_t sent;

	if (offered != REFERENCE_LPASS_FEATURES)
		return -EPROTO;
	put_word(message, FEATURE);
	put_word(message + 4, sizeof(message) - 8);
	put_word(message + 8, 4);
	put_word(message + 12, offered & REFERENCE_ROUTER_FEATURES);
	sent = sendto(fd, message, sizeof(message), MSG_DONTWAIT,
		      (const struct sockaddr *)peer, sizeof(*peer));
	if (sent != sizeof(message))
		return sent < 0 ? -errno : -EIO;
	printf("LPASS FEATURE reply sent: %#08x (no log masks or command traffic)\n",
	       offered & REFERENCE_ROUTER_FEATURES);
	return 0;
}

struct observation {
	struct sockaddr_qrtr control;
	unsigned int ids;
	int register_ids;
};

static int observe_diag_id(int fd, struct observation *session,
			   const unsigned char *body, uint32_t bytes)
{
	static const char *const names[] = {
		"msm/adsp/root_pd", "msm/adsp/charger_pd", "msm/adsp/audio_pd", "msm/adsp/sensor_pd"
	};
	uint32_t version, offset;
	const unsigned char *name, *end;

	if (bytes < 13)
		return 0;
	version = word(body);
	if (version != 2 || word(body + 8) > bytes - 13)
		return 0;
	offset = 12 + word(body + 8);
	name = body + offset;
	end = memchr(name, 0, bytes - offset);
	if (!end || end + 1 != body + bytes)
		return 0;
	for (unsigned int i = 0; i < sizeof(names) / sizeof(names[0]); i++) {
		unsigned char response[64] = { 0 };
		size_t length = strlen(names[i]) + 1;
		ssize_t sent;

		if (length != (size_t)(end - name + 1) || memcmp(name, names[i], length))
			continue;
		if (!session->register_ids) {
			printf("LPASS DIAG-ID request: %s (not acknowledged)\n", names[i]);
			return 0;
		}
		put_word(response, DIAG_ID);
		put_word(response + 4, 8 + length);
		put_word(response + 8, 1); /* reply v1 to a v2 registration */
		put_word(response + 12, i + 2);
		memcpy(response + 16, names[i], length);
		sent = sendto(fd, response, 16 + length, MSG_DONTWAIT,
			      (const struct sockaddr *)&session->control, sizeof(session->control));
		if (sent < 0 || (size_t)sent != 16 + length)
			return sent < 0 ? -errno : -EIO;
		session->ids |= 1u << i;
		printf("LPASS DIAG-ID %u replied: %s\n", i + 2, names[i]);
		return 0;
	}
	return 0;
}

static int observe_feature(int fd, int negotiate, struct observation *session)
{
	struct pollfd wait = { .fd = fd, .events = POLLIN };
	unsigned char packet[512];
	struct sockaddr_qrtr peer = { 0 };
	socklen_t len = sizeof(peer);
	ssize_t n;

	if (poll(&wait, 1, 100) <= 0 || !(wait.revents & POLLIN))
		return 0;
	n = recvfrom(fd, packet, sizeof(packet), MSG_TRUNC | MSG_DONTWAIT,
		     (struct sockaddr *)&peer, &len);
	if (n < 8 || n > (ssize_t)sizeof(packet) || len != sizeof(peer) ||
	    peer.sq_node != LPASS_NODE || peer.sq_port == QRTR_PORT_CTRL ||
	    (session->control.sq_port && peer.sq_port != session->control.sq_port))
		return 0;
	for (size_t i = 0; i + 8 <= (size_t)n;) {
		uint32_t cmd = word(packet + i), bytes = word(packet + i + 4);

		if (bytes > (size_t)n - i - 8)
			return 0;
		if (cmd == FEATURE && bytes >= 5) {
			uint32_t width = word(packet + i + 8), features = 0;

			if (width && width <= 4 && width <= bytes - 4) {
				for (uint32_t j = 0; j < width; j++)
					features |= (uint32_t)packet[i + 12 + j] << (8 * j);
				printf("LPASS passive FEATURE: node=%u port=%u capabilities=%#08x\n",
				       peer.sq_node, peer.sq_port, features);
				session->control = peer;
				if (negotiate) {
					int result = reply_feature(fd, &peer, features);

					if (result)
						return result;
				}
				return 1;
			}
		}
		printf("LPASS passive control header: node=%u port=%u cmd=%u bytes=%u\n",
		       peer.sq_node, peer.sq_port, cmd, bytes);
		if (cmd == DIAG_ID && session->control.sq_port) {
			int result = observe_diag_id(fd, session, packet + i + 8, bytes);

			if (result)
				return result;
		}
		i += 8 + bytes;
	}
	return 0;
}

static int send_tap_mask(int fd, const struct sockaddr_qrtr *peer, int on)
{
	enum { MASK_BYTES = TAP_LOG_ITEM / 8 + 1 };
	unsigned char message[19 + MASK_BYTES] = { 0 };
	ssize_t sent;

	put_word(message, 9); /* DIAG_CNTL_CMD_LOG_MASK */
	put_word(message + 4, sizeof(message) - 8);
	message[8] = 1; /* stream */
	message[9] = 3; /* valid mask */
	message[10] = 1; /* equipment = upper nibble of 0x1586 */
	put_word(message + 11, TAP_LOG_ITEM + 1);
	put_word(message + 15, MASK_BYTES);
	if (on)
		message[19 + TAP_LOG_ITEM / 8] = 1u << (TAP_LOG_ITEM % 8);
	sent = sendto(fd, message, sizeof(message), MSG_DONTWAIT,
		      (const struct sockaddr *)peer, sizeof(*peer));
	return sent == sizeof(message) ? 0 : sent < 0 ? -errno : -EIO;
}

/* Consume only complete consecutive non-HDLC frames. Do not scan packet
 * payload for delimiters after an invalid framing header.
 */
static size_t non_hdlc_frame(const unsigned char *buf, size_t bytes)
{
	size_t payload;

	if (bytes < 5 || buf[0] != 0x7e || buf[1] != 1)
		return 0;
	payload = buf[2] | ((unsigned int)buf[3] << 8);
	return payload + 5 <= bytes && buf[payload + 4] == 0x7e ? payload + 5 : 0;
}

static int capture_taps(int data_fd, int control_fd, const struct observation *session,
			const char *file)
{
	struct timespec begin, now;
	unsigned int count[5] = { 0 }, received = 0, framed = 0, log_1586 = 0;
	unsigned int unmatched = 0, oversize = 0, other_taps = 0, invalid_log = 0;
	FILE *out;
	int ret, clear;

	int fd = open(file, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
	if (fd < 0)
		return -errno;
	out = fdopen(fd, "wb");
	if (!out) {
		ret = -errno;
		close(fd);
		return ret;
	}
	ret = send_tap_mask(control_fd, &session->control, 1);
	if (ret) {
		fclose(out);
		return ret;
	}
	if (clock_gettime(CLOCK_MONOTONIC, &begin) < 0) {
		ret = -errno;
		goto mask_off;
	}
	printf("LPASS 0x1586 capture armed (wire tap IDs 1–4 only), monotonic origin=%lld.%09ld\n",
	       (long long)begin.tv_sec, begin.tv_nsec);
	fflush(stdout);
	while (!cancelled && received < 4096) {
		unsigned char buf[65536];
		struct sockaddr_qrtr peer = { 0 };
		struct pollfd wait = { .fd = data_fd, .events = POLLIN };
		socklen_t addrsize = sizeof(peer);
		ssize_t n;
		double timestamp;

		if (clock_gettime(CLOCK_MONOTONIC, &now) < 0) {
			ret = -errno;
			break;
		}
		timestamp = (now.tv_sec - begin.tv_sec) + (now.tv_nsec - begin.tv_nsec) / 1e9;
		if (timestamp >= CAPTURE_SECONDS)
			break;
		if (poll(&wait, 1, 40) <= 0 || !(wait.revents & POLLIN))
			continue;
		n = recvfrom(data_fd, buf, sizeof(buf), MSG_DONTWAIT | MSG_TRUNC,
			     (struct sockaddr *)&peer, &addrsize);
		if (n < 5 || addrsize != sizeof(peer) || peer.sq_node != LPASS_NODE ||
		    peer.sq_port == QRTR_PORT_CTRL)
			continue;
		if (n > (ssize_t)sizeof(buf)) {
			oversize++;
			break;
		}
		/* Use the post-receive timestamp, not the preceding poll entry. */
		if (clock_gettime(CLOCK_MONOTONIC, &now) < 0) {
			ret = -errno;
			break;
		}
		timestamp = (now.tv_sec - begin.tv_sec) + (now.tv_nsec - begin.tv_nsec) / 1e9;
		if (timestamp >= CAPTURE_SECONDS)
			break;
		received++;
		size_t pos = 0, bytes;
		while ((bytes = non_hdlc_frame(buf + pos, (size_t)n - pos)) != 0) {
			const unsigned char *pkt = buf + pos + 4;
			unsigned int length = bytes - 5, tap;
			uint32_t archive_size;

			pos += bytes;
			framed++;
			if (length < 8 || pkt[0] != 0x10 || pkt[6] != 0x86 || pkt[7] != 0x15)
				continue;
			log_1586++;
			if (length < 104 || (pkt[2] | ((unsigned int)pkt[3] << 8)) != length - 4 ||
			    pkt[4] != pkt[2] || pkt[5] != pkt[3] || word(pkt + 28) != length - 104) {
				invalid_log++;
				continue;
			}
			tap = word(pkt + 52);
			if (tap < 1 || tap >= sizeof(count) / sizeof(count[0])) {
				if (other_taps++ < 8)
					printf("LPASS other tap: id=%#x bytes=%u\n", tap, length);
				continue;
			}
			archive_size = htole32(length);
#if __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error This archive format requires a little-endian Linux host.
#endif
			if (fwrite(&timestamp, sizeof(timestamp), 1, out) != 1 ||
			    fwrite(&archive_size, sizeof(archive_size), 1, out) != 1 ||
			    fwrite(pkt, length, 1, out) != 1) {
				ret = -EIO;
				goto mask_off;
			}
			count[tap]++;
		}
		if (pos != (size_t)n && unmatched++ < 8)
			printf("LPASS unmatched envelope: bytes=%zd consumed=%zu delimiter=%d version1=%d\n",
			       n, pos, buf[pos] == 0x7e, (size_t)n - pos > 1 && buf[pos + 1] == 1);
	}
mask_off:
	clear = send_tap_mask(control_fd, &session->control, 0);
	if (fclose(out) && !ret)
		ret = -EIO;
	if (clear)
		fprintf(stderr, "LPASS zero-mask send failed: %s\n", strerror(-clear));
	else
		puts("LPASS zero mask sent (no hardware acknowledgement exposed)");
	printf("LPASS data datagrams=%u, valid frames=%u, 0x1586=%u, tap1=%u, tap2=%u, tap3=%u, tap4=%u, other=%u, invalid=%u, unmatched=%u, oversize=%u\n",
	       received, framed, log_1586, count[1], count[2], count[3], count[4], other_taps, invalid_log, unmatched, oversize);
	return ret ?: clear ?: (oversize ? -EMSGSIZE : 0);
}

int main(int argc, char **argv)
{
	static const unsigned int versions[] = {64, 66, 68};
	int publish[] = {-1, -1, -1};
	uint32_t local, node;
	int lookup, status = EXIT_FAILURE;
	const char *capture = argc == 3 && !strcmp(argv[1], "--capture-1586") ? argv[2] : NULL;
	struct observation session = {
		.register_ids = capture || (argc == 2 && !strcmp(argv[1], "--register-ids"))
	};
	int negotiate = session.register_ids || (argc == 2 && !strcmp(argv[1], "--negotiate"));

	if (argc != 1 && !negotiate) {
		fprintf(stderr, "usage: %s [--negotiate|--register-ids|--capture-1586 NEW-ARCHIVE]\n", argv[0]);
		return status;
	}
	if (capture) {
		struct sigaction stop = { .sa_handler = request_stop };
		const char *sound = "/sys/firmware/devicetree/base/sound/";
		char path[128];
		const char *required[] = {
			"microsoft,denali-fullio-muted-test", "microsoft,denali-fullio-clock-off-audit",
			"microsoft,denali-fullio-dsp-start-audit",
		};

		for (unsigned int i = 0; i < sizeof(required) / sizeof(required[0]); i++) {
			snprintf(path, sizeof(path), "%s%s", sound, required[i]);
			if (access(path, F_OK)) {
				fputs("LPASS capture requires the PA-off START/STOP audit DT\n", stderr);
				return status;
			}
		}
		snprintf(path, sizeof(path), "%smicrosoft,denali-fullio-post-pa-test", sound);
		if (!access(path, F_OK)) {
			fputs("LPASS capture helper will not run on a post-PA fixture\n", stderr);
			return status;
		}

		if (sigaction(SIGALRM, &stop, NULL) || sigaction(SIGTERM, &stop, NULL) ||
		    sigaction(SIGINT, &stop, NULL))
			return status;
	}
	alarm(capture ? 11 : 6); /* Publications are withdrawn when the sockets close. */
	lookup = control_socket(QRTR_TYPE_NEW_LOOKUP, LPASS_COMMAND, &local);
	if (lookup < 0) {
		perror("LPASS command service lookup");
		return status;
	}
	for (size_t i = 0; i < sizeof(publish) / sizeof(publish[0]); i++) {
		publish[i] = control_socket(QRTR_TYPE_NEW_SERVER, versions[i], &node);
		if (publish[i] < 0) {
			perror("temporary LPASS service publication");
			goto out;
		}
		if (local != node)
			goto out;
	}

	/* The initial zero tuple means the preexisting lookup list ended,
	 * not that a subsequent dynamically published service cannot appear.
	 */
	for (unsigned int i = 0; i < 20; i++) {
		struct pollfd wait = { .fd = lookup, .events = POLLIN };
		struct sockaddr_qrtr peer = { 0 };
		struct qrtr_ctrl_pkt pkt;
		socklen_t len = sizeof(peer);
		ssize_t n;

		if (poll(&wait, 1, 180) <= 0 || !(wait.revents & POLLIN))
			continue;
		n = recvfrom(lookup, &pkt, sizeof(pkt), MSG_TRUNC | MSG_DONTWAIT,
			     (struct sockaddr *)&peer, &len);
		if (n != sizeof(pkt) || len != sizeof(peer) || peer.sq_node != local ||
		    peer.sq_port != QRTR_PORT_CTRL || le32toh(pkt.cmd) != QRTR_TYPE_NEW_SERVER ||
		    le32toh(pkt.server.service) != DIAG_SERVICE ||
		    le32toh(pkt.server.instance) != LPASS_COMMAND ||
		    le32toh(pkt.server.node) != LPASS_NODE || !pkt.server.port)
			continue;
		printf("LPASS command service discovered: node=%u port=%u version=%u\n",
		       le32toh(pkt.server.node), le32toh(pkt.server.port), LPASS_COMMAND);
		int feature = 0;
		for (unsigned int j = 0; j < 8 && !feature; j++)
			feature = observe_feature(publish[0], negotiate, &session);
		if (feature < 0) {
			fprintf(stderr, "LPASS FEATURE reply refused: %s\n", strerror(-feature));
			goto out;
		}
		if (!feature)
			puts("No well-formed passive LPASS FEATURE in the observation window");
		if (negotiate && feature) {
			/* Never alter logging or buffering state in this helper. */
			for (unsigned int j = 0; j < 7; j++) {
				int result = observe_feature(publish[0], 0, &session);

				if (result < 0) {
					fprintf(stderr, "LPASS control exchange failed: %s\n", strerror(-result));
					goto out;
				}
			}
		}
		if (session.register_ids && session.ids != 0xf)
			fprintf(stderr, "LPASS DIAG-ID reply set incomplete: %#x\n", session.ids);
		else if (capture && !cancelled) {
			int result = capture_taps(publish[1], publish[0], &session, capture);

			if (!result)
				status = EXIT_SUCCESS;
			else
				fprintf(stderr, "LPASS capture failed: %s\n", strerror(-result));
		} else if (!negotiate || feature)
			status = EXIT_SUCCESS;
		goto out;
	}
	fprintf(stderr, "LPASS command service did not appear after bounded publication\n");
out:
	for (size_t i = 0; i < sizeof(publish) / sizeof(publish[0]); i++)
		if (publish[i] >= 0)
			close(publish[i]);
	close(lookup);
	return status;
}
