/*
 * pilha_nativa.c: a pilha nativa de um processo da suíte que morre por sinal.
 *
 * O `scripts/rodar-a-suite.sh` compila isto e o carrega por `LD_PRELOAD` em
 * cada pytest (não há `catchsegv` na glibc 2.35+, e o `core_pattern` desta
 * casa vai para o apport). O construtor arma o tratador antes do Python; o
 * `faulthandler` entra depois, escreve a pilha Python, devolve este tratador
 * e levanta o sinal de novo. Aqui sai a pilha da linha que falhou e, com o
 * `eu-stack`, a de todas; então o sinal volta ao padrão e o processo morre
 * com o mesmo número. O construtor também tira a biblioteca do `LD_PRELOAD`:
 * os filhos do pytest nascem sem ela.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <execinfo.h>
#include <fcntl.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static const int SINAIS[] = {SIGSEGV, SIGBUS, SIGILL, SIGFPE, SIGABRT};
#define N_SINAIS (sizeof(SINAIS) / sizeof(SINAIS[0]))
#define ESPERA_MAXIMA_EM_DECIMOS 100 /* dez segundos para o eu-stack */

static char eu_stack[256];
/* O stderr de quando o processo nasceu: o pytest desvia o 2 enquanto o teste
 * roda, e o que se escrevesse ali morreria com a captura. */
static int saida = STDERR_FILENO;
static char pilha_alternativa[1 << 16];

static void escreve(const char *texto) {
    ssize_t r = write(saida, texto, strlen(texto));
    (void)r;
}

static void escreve_numero(long n) {
    char buf[24];
    int i = (int)sizeof(buf) - 1;
    buf[i] = '\0';
    if (n == 0) buf[--i] = '0';
    while (n > 0 && i > 0) {
        buf[--i] = (char)('0' + n % 10);
        n /= 10;
    }
    escreve(buf + i);
}

/* Todas as linhas, pelo eu-stack. O filho só existe depois de a porta abrir. */
static void todas_as_linhas(pid_t eu) {
    char alvo[24];
    int canal[2];
    if (eu_stack[0] == '\0' || pipe(canal) != 0) return;
    int i = (int)sizeof(alvo) - 1;
    alvo[i] = '\0';
    for (long n = eu; n > 0 && i > 0; n /= 10) alvo[--i] = (char)('0' + n % 10);
    long filho = syscall(SYS_clone, SIGCHLD, 0, 0, 0, 0);
    if (filho < 0) return;
    if (filho == 0) {
        char porta;
        close(canal[1]);
        if (read(canal[0], &porta, 1) != 1) _exit(1);
        dup2(saida, STDOUT_FILENO);
        dup2(saida, STDERR_FILENO);
        char *const argv[] = {eu_stack, "-p", alvo + i, "-m", NULL};
        char *const envp[] = {"LC_ALL=C", NULL};
        execve(eu_stack, argv, envp);
        _exit(1);
    }
    prctl(PR_SET_PTRACER, (unsigned long)filho, 0, 0, 0);
    close(canal[0]);
    ssize_t r = write(canal[1], "x", 1);
    (void)r;
    close(canal[1]);
    struct timespec decimo = {0, 100000000L};
    for (int n = 0; n < ESPERA_MAXIMA_EM_DECIMOS; n++) {
        if (waitpid((pid_t)filho, NULL, WNOHANG) != 0) return;
        nanosleep(&decimo, NULL);
    }
    kill((pid_t)filho, SIGKILL);
    waitpid((pid_t)filho, NULL, 0);
    escreve("pilha nativa: o eu-stack passou de dez segundos e saiu\n");
}

static void ao_morrer(int sinal) {
    void *quadros[128];
    pid_t eu = getpid();
    escreve("\npilha nativa: sinal ");
    escreve_numero(sinal);
    escreve(" no processo ");
    escreve_numero(eu);
    escreve(", linha ");
    escreve_numero((long)syscall(SYS_gettid));
    escreve("\npilha nativa: a linha que recebeu o sinal\n");
    int n = backtrace(quadros, 128);
    backtrace_symbols_fd(quadros, n, saida);
    if (eu_stack[0] != '\0') escreve("pilha nativa: todas as linhas (eu-stack)\n");
    todas_as_linhas(eu);
    escreve("pilha nativa: fim\n");
    signal(sinal, SIG_DFL);
    raise(sinal);
}

/* Tira esta biblioteca do LD_PRELOAD e deixa as outras, na mesma ordem. */
static void sai_do_ambiente(void) {
    Dl_info eu;
    char resto[4096];
    size_t n = 0;
    const char *p = getenv("LD_PRELOAD");
    if (p == NULL || dladdr((void *)ao_morrer, &eu) == 0 || eu.dli_fname == NULL) return;
    size_t tamanho_do_meu = strlen(eu.dli_fname);
    while (*p != '\0') {
        while (*p == ' ' || *p == ':') p++;
        const char *inicio = p;
        while (*p != '\0' && *p != ' ' && *p != ':') p++;
        size_t tamanho = (size_t)(p - inicio);
        if (tamanho == 0) break;
        if (tamanho == tamanho_do_meu && strncmp(inicio, eu.dli_fname, tamanho) == 0) continue;
        if (n + tamanho + 2 > sizeof(resto)) return;
        if (n > 0) resto[n++] = ' ';
        memcpy(resto + n, inicio, tamanho);
        n += tamanho;
    }
    resto[n] = '\0';
    if (n > 0)
        setenv("LD_PRELOAD", resto, 1);
    else
        unsetenv("LD_PRELOAD");
}

__attribute__((constructor)) static void armar(void) {
    void *um[1];
    sai_do_ambiente();
    int copia = fcntl(STDERR_FILENO, F_DUPFD_CLOEXEC, 3);
    if (copia >= 0) saida = copia;
    /* A primeira chamada carrega a libgcc_s; no tratador ela já está aqui. */
    backtrace(um, 1);
    const char *caminho = getenv("HEFESTO_EU_STACK");
    if (caminho == NULL) caminho = "/usr/bin/eu-stack";
    if (caminho[0] != '\0' && strlen(caminho) < sizeof(eu_stack) && access(caminho, X_OK) == 0)
        strcpy(eu_stack, caminho);
    stack_t alternativa = {.ss_sp = pilha_alternativa, .ss_size = sizeof(pilha_alternativa)};
    sigaltstack(&alternativa, NULL);
    struct sigaction acao;
    memset(&acao, 0, sizeof(acao));
    acao.sa_handler = ao_morrer;
    acao.sa_flags = SA_ONSTACK | SA_NODEFER | SA_RESETHAND;
    sigemptyset(&acao.sa_mask);
    for (size_t i = 0; i < N_SINAIS; i++) sigaction(SINAIS[i], &acao, NULL);
}
