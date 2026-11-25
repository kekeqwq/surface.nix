/* Read only the local QRTR service registry; never opens a DIAG session. */
#include <endian.h>
#include <linux/qrtr.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/socket.h>
#include <unistd.h>

int main(void)
{
	struct sockaddr_qrtr local = {0}, peer = {0};
	struct qrtr_ctrl_pkt pkt = { .cmd = htole32(QRTR_TYPE_NEW_LOOKUP) };
	socklen_t len = sizeof(local);
	int fd, result = EXIT_FAILURE;

	alarm(3);
	fd = socket(AF_QIPCRTR, SOCK_DGRAM | SOCK_CLOEXEC, 0);
	if (fd < 0) {
		perror("QRTR socket");
		return EXIT_FAILURE;
	}
	if (getsockname(fd, (struct sockaddr *)&local, &len) < 0) {
		perror("QRTR local node");
		goto out;
	}
	local.sq_port = QRTR_PORT_CTRL;
	if (sendto(fd, &pkt, sizeof(pkt), 0, (struct sockaddr *)&local,
		   sizeof(local)) != sizeof(pkt)) {
		perror("local QRTR lookup");
		goto out;
	}

	for (int i = 0; i < 256; i++) {
		len = sizeof(peer);
		ssize_t n = recvfrom(fd, &pkt, sizeof(pkt), MSG_TRUNC,
				     (struct sockaddr *)&peer, &len);
		if (n < 0) {
			perror("QRTR lookup response");
			goto out;
		}
		if (n != sizeof(pkt) || len != sizeof(peer) ||
		    peer.sq_node != local.sq_node || peer.sq_port != QRTR_PORT_CTRL ||
		    le32toh(pkt.cmd) != QRTR_TYPE_NEW_SERVER)
			continue;
		if (!pkt.server.service && !pkt.server.instance &&
		    !pkt.server.node && !pkt.server.port) {
			result = EXIT_SUCCESS;
			goto out;
		}
		printf("service=%u instance=%u node=%u port=%u\n",
		       le32toh(pkt.server.service), le32toh(pkt.server.instance),
		       le32toh(pkt.server.node), le32toh(pkt.server.port));
	}
	fprintf(stderr, "QRTR lookup did not finish within 256 replies\n");
out:
	close(fd);
	return result;
}
