/*
 * A mordida do hefesto-0002, sem rádio, sem root e sem BlueZ instalado.
 *
 * Quem monta: `scripts/construir_bluez_backport.sh --mordida <device.c>`.
 * Ele recorta do `profiles/input/device.c` informado a `struct input_device`
 * e toda função `hidp_send_*` (mais os `#define HIDP_SEND_*` do patch), grava
 * o recorte em `recorte.inc` e compila este arquivo por cima. As funções que o
 * recorte chama e que não são dele — o `uhid_disconnect`, as respostas ao
 * kernel, o relógio — são dublês daqui, e cada uma CONTA o que aconteceu.
 *
 * O socket NÃO é dublê: é um `socketpair` de verdade, não bloqueante, cheio
 * até o kernel devolver EAGAIN — o mesmo errno que o L2CAP devolveu ao
 * bluetoothd nos quatro episódios de 22/09/2026.
 *
 * Saída: uma linha por cenário, `cenario=<nome> destruido=<n> ...`.
 * Sem o patch, `eagain` sai com destruido > 0 (o aparelho some); com ele,
 * destruido=0 e os descartes contados. Os erros terminais derrubam nos dois.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/uio.h>
#include <unistd.h>
#include <linux/uhid.h>

/* --- os tipos que a struct input_device cita -------------------------- */
typedef unsigned int guint;
typedef void *gpointer;
typedef struct { uint8_t b[6]; } bdaddr_t;
typedef struct sdp_record sdp_record_t;
struct btd_service;
struct btd_device;
struct bt_uhid;
struct hidp_connadd_req;
typedef struct { int fd; } GIOChannel;

static int g_io_channel_unix_get_fd(GIOChannel *chan)
{
	return chan->fd;
}

/* --- o relógio: parado, e quem anda com ele é o cenário --------------- */
static int64_t relogio_us = 1000000;

static int64_t g_get_monotonic_time(void)
{
	return relogio_us;
}

/* --- o log: conta as linhas e guarda a última ------------------------- */
static int linhas_de_log;
static char ultima_linha[512];

#define error(fmt, ...) do { \
	linhas_de_log++; \
	snprintf(ultima_linha, sizeof(ultima_linha), fmt, ##__VA_ARGS__); \
} while (0)
#define DBG(fmt, ...) do { } while (0)

/* --- as constantes de profiles/input/hidp_defs.h do 5.86 -------------- */
#define HIDP_TRANS_HANDSHAKE		0x00
#define HIDP_TRANS_HID_CONTROL		0x10
#define HIDP_TRANS_GET_REPORT		0x40
#define HIDP_TRANS_SET_REPORT		0x50
#define HIDP_TRANS_DATA			0xa0
#define HIDP_CTRL_VIRTUAL_CABLE_UNPLUG	0x05
#define HIDP_DATA_RTYPE_INPUT		0x01
#define HIDP_DATA_RTYPE_OUTPUT		0x02
#define HIDP_DATA_RTYPE_FEATURE		0x03
#define REPORT_REQ_TIMEOUT		3

/* --- os dublês que contam --------------------------------------------- */
struct input_device;

static int destruidos;
static int respostas_de_erro;

static int uhid_disconnect(struct input_device *idev, bool force)
{
	(void) idev;
	(void) force;
	destruidos++;
	return 0;
}

static void input_device_idle_reset(struct input_device *idev)
{
	(void) idev;
}

static bool uhid_send_set_report_reply(struct input_device *idev,
					uint32_t id, uint16_t err)
{
	(void) idev;
	(void) id;
	if (err)
		respostas_de_erro++;
	return true;
}

static bool uhid_send_get_report_reply(struct input_device *idev,
					const uint8_t *data, size_t size,
					uint32_t id, uint16_t err)
{
	(void) idev;
	(void) data;
	(void) size;
	(void) id;
	if (err)
		respostas_de_erro++;
	return true;
}

static unsigned int timeout_add_seconds(unsigned int timeout,
					bool (*func)(void *), void *user_data,
					void (*destroy)(void *))
{
	(void) timeout;
	(void) func;
	(void) user_data;
	(void) destroy;
	return 1;
}

static bool hidp_report_req_timeout(gpointer data)
{
	(void) data;
	return false;
}

/* --- o recorte do device.c em teste ----------------------------------- */
#include "recorte.inc"

/* --- os sockets de verdade -------------------------------------------- */

/* Um socket cheio: o próximo write devolve EAGAIN, dado pelo kernel. */
static int socket_cheio(void)
{
	int sv[2];
	int pequeno = 4096;
	char bloco[512] = { 0 };

	if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, sv) < 0) {
		perror("socketpair");
		exit(2);
	}
	fcntl(sv[0], F_SETFL, fcntl(sv[0], F_GETFL) | O_NONBLOCK);
	setsockopt(sv[0], SOL_SOCKET, SO_SNDBUF, &pequeno, sizeof(pequeno));

	while (write(sv[0], bloco, sizeof(bloco)) > 0)
		;
	if (errno != EAGAIN) {
		perror("encher o socket");
		exit(2);
	}
	/* sv[1] fica aberto e sem leitor: é o rádio que não escoa */
	return sv[0];
}

/* Um socket cujo outro lado fechou: EPIPE, o enlace que morreu. */
static int socket_morto(void)
{
	int sv[2];

	if (socketpair(AF_UNIX, SOCK_SEQPACKET, 0, sv) < 0) {
		perror("socketpair");
		exit(2);
	}
	close(sv[1]);
	return sv[0];
}

/* Um socket que nunca conectou: ENOTCONN. */
static int socket_sem_conexao(void)
{
	int fd = socket(AF_UNIX, SOCK_SEQPACKET, 0);

	if (fd < 0) {
		perror("socket");
		exit(2);
	}
	return fd;
}

static struct input_device *aparelho(int fd)
{
	struct input_device *idev = calloc(1, sizeof(*idev));
	GIOChannel *chan = calloc(1, sizeof(*chan));

	chan->fd = fd;
	idev->intr_io = fd >= 0 ? chan : NULL;
	idev->ctrl_io = fd >= 0 ? chan : NULL;
	return idev;
}

static void zerar(void)
{
	destruidos = 0;
	respostas_de_erro = 0;
	linhas_de_log = 0;
	ultima_linha[0] = '\0';
}

static long long descartados(struct input_device *idev)
{
#ifdef HIDP_SEND_DROP_LOG_INTERVAL_US
	return (long long) idev->send_dropped;
#else
	(void) idev;
	return -1;
#endif
}

static void relatar(const char *nome, struct input_device *idev)
{
	printf("cenario=%s destruido=%d linhas=%d respostas_de_erro=%d "
		"descartados=%lld ultima_linha=\"%s\"\n", nome, destruidos,
		linhas_de_log, respostas_de_erro, descartados(idev),
		ultima_linha);
}

static void saida(struct input_device *idev, int vezes)
{
	struct uhid_event ev;

	memset(&ev, 0, sizeof(ev));
	ev.type = UHID_OUTPUT;
	ev.u.output.size = 78;
	for (int i = 0; i < vezes; i++)
		hidp_send_output(&ev, idev);
}

int main(void)
{
	struct input_device *idev;
	struct uhid_event ev;

	signal(SIGPIPE, SIG_IGN);

	/* O 2A de 22/09: a saída encontra o socket cheio, mil vezes no mesmo
	 * segundo, e depois mais uma, um segundo adiante. */
	zerar();
	idev = aparelho(socket_cheio());
	saida(idev, 1000);
	relogio_us += 1000000;
	saida(idev, 1);
	relatar("eagain", idev);

	/* O enlace que morreu de verdade: tem de derrubar, com ou sem patch. */
	zerar();
	idev = aparelho(socket_morto());
	saida(idev, 1);
	relatar("epipe", idev);

	zerar();
	idev = aparelho(socket_sem_conexao());
	saida(idev, 1);
	relatar("enotconn", idev);

	zerar();
	idev = aparelho(-1);
	saida(idev, 1);
	relatar("sem_canal", idev);

	/* O canal de controle tem o mesmo defeito: SET_REPORT e GET_REPORT
	 * com o socket cheio respondem erro ao kernel e, sem o patch, destroem. */
	zerar();
	idev = aparelho(socket_cheio());
	memset(&ev, 0, sizeof(ev));
	ev.type = UHID_SET_REPORT;
	ev.u.set_report.rtype = UHID_FEATURE_REPORT;
	ev.u.set_report.size = 8;
	hidp_send_set_report(&ev, idev);
	relatar("set_report_eagain", idev);

	zerar();
	idev = aparelho(socket_cheio());
	memset(&ev, 0, sizeof(ev));
	ev.type = UHID_GET_REPORT;
	ev.u.get_report.rtype = UHID_FEATURE_REPORT;
	hidp_send_get_report(&ev, idev);
	relatar("get_report_eagain", idev);

	return 0;
}
