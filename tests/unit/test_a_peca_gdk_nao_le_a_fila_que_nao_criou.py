"""A peça GDK não lê a fila que ela não criou: a alça vale pela presença na tabela das filas vivas.

Às 22h46 de 17/10/2026 o Minecraft Dungeons II entregou ao `XTaskQueueDuplicateHandle` a alça
0xcf15dc7ed8420217 (um valor que nem é endereço canônico), e a peça caiu no `cmpl $QUEUE_MAGIC`
do `thr_Duplicate`, porque decidia se a fila valia lendo o `magic` no endereço que chegou.

A prova em C carrega a peça compilada deste fonte, como um jogo carrega, e entrega a cada função
que recebe fila (ou porta) cinco alças que a peça não criou ou já destruiu: o -1, o valor do crash,
um ponteiro de pilha zerado, um bloco de pilha forjado com o `magic` da peça e uma fila destruída.
Toda chamada tem de recusar sem cair e sem escrever no bloco forjado. A mordida devolve o `magic`
ao `queue_live` e a prova tem de cair. Precisa do mingw-w64 no PATH e de um Wine
(`HEFESTO_WINE` ou o do ensaio do contrato); o prefixo é de teste, no /tmp.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

_RAIZ = Path(__file__).resolve().parents[2]
_FONTE = _RAIZ / "assets" / "gdk-runtime" / "xgameruntime.c"
_ENSAIO = _RAIZ / "scripts" / "ensaios" / "o_contrato_da_peca_gdk.py"
_CC = "x86_64-w64-mingw32-gcc-posix"

#: As funções da ABI do XTaskQueue/XAsync que recebem uma fila ou uma porta do chamador.
_RECEBEM_FILA = (
    "thr_GetPort", "thr_Duplicate", "thr_Dispatch", "thr_Close", "thr_Submit",
    "thr_SubmitDelayed", "thr_Terminate", "thr_RegMon", "thr_UnregMon",
    "thr_SetProcessQueue", "thr_QueueCreateComposite", "thr_Begin",
)

#: Funções que recebem fila e não a leem (o contrato não é implementado nelas).
_NAO_LEEM = ("thr_RegWaiter", "thr_UnregWaiter")

_ALCAS = ("menos_um", "valor_do_crash", "pilha_zerada", "forjada_com_magic", "destruida")

#: A mordida: o queue_live volta a decidir pelo magic lido no endereço que chegou.
_CURA = "static int queue_live(queue_obj *q)\n{\n"
_QUEBRADO = "static int queue_live(queue_obj *q)\n{\n    return q && q->magic == QUEUE_MAGIC;\n"

_PROVA_C = r"""
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <string.h>

typedef struct queue_obj queue_obj;
typedef struct port_obj port_obj;
typedef struct XAsyncBlock {
    queue_obj *queue;
    void *context;
    void (__stdcall *callback)(struct XAsyncBlock *);
    unsigned char internal[32];
} XAsyncBlock;
typedef struct XAsyncProviderData {
    XAsyncBlock *async;
    SIZE_T bufferSize;
    void *buffer;
    void *context;
} XAsyncProviderData;
typedef HRESULT (__stdcall *XAsyncProvider)(UINT32 op, const XAsyncProviderData *data);
typedef void (__stdcall *XTaskQueueCallback)(void *context, BOOLEAN canceled);

typedef HRESULT (WINAPI *Begin_t)(void *, XAsyncBlock *, void *, const void *, const char *,
                                  XAsyncProvider);
typedef HRESULT (WINAPI *QueueCreate_t)(void *, UINT32, UINT32, queue_obj **);
typedef HRESULT (WINAPI *QueueCreateComposite_t)(void *, port_obj *, port_obj *, queue_obj **);
typedef HRESULT (WINAPI *GetPort_t)(void *, queue_obj *, UINT32, port_obj **);
typedef HRESULT (WINAPI *Duplicate_t)(void *, queue_obj *, queue_obj **);
typedef BOOLEAN (WINAPI *Dispatch_t)(void *, queue_obj *, UINT32, UINT32);
typedef void (WINAPI *Close_t)(void *, queue_obj *);
typedef HRESULT (WINAPI *Submit_t)(void *, queue_obj *, UINT32, void *, XTaskQueueCallback);
typedef HRESULT (WINAPI *SubmitDelayed_t)(void *, queue_obj *, UINT32, UINT32, void *,
                                          XTaskQueueCallback);
typedef HRESULT (WINAPI *Terminate_t)(void *, queue_obj *, BOOLEAN, void *,
                                      void (__stdcall *)(void *));
typedef HRESULT (WINAPI *RegMon_t)(void *, queue_obj *, void *, void *, UINT64 *);
typedef void (WINAPI *UnregMon_t)(void *, queue_obj *, UINT64);
typedef BOOLEAN (WINAPI *GetProcessQueue_t)(void *, queue_obj **);
typedef void (WINAPI *SetProcessQueue_t)(void *, queue_obj *);
typedef HRESULT (WINAPI *QueryApiImpl_t)(const GUID *, const GUID *, void **);
typedef const char *(WINAPI *Ident_t)(void);

static const GUID IID_Threading = {
    0x073b7dcb, 0x1fcf, 0x4030, { 0x94, 0xbe, 0xe3, 0xc9, 0xeb, 0x62, 0x34, 0x28 }
};
static void *g_self;
static void **g_vt;
#define VT(type, idx) ((type)g_vt[idx])
#define E_INVALIDARG_ ((HRESULT)0x80070057)
#define SENTINELA ((queue_obj *)(UINT_PTR)0x5E57E5E57E5E57E5ull)

static const char *volatile g_onde = "inicio";
static volatile LONG g_cb_rodou;
static volatile LONG g_prov_rodou;
static volatile LONG g_term_cb;

static LONG WINAPI ao_cair(EXCEPTION_POINTERS *e)
{
    DWORD c = e->ExceptionRecord->ExceptionCode;
    if (c == 0xC0000005u || c == 0xC000001Du || c == 0xC0000096u || c == 0xC0000094u) {
        printf("{\"caiu\": \"%s\", \"código\": \"0x%08lX\"}\n", g_onde, (unsigned long)c);
        fflush(stdout);
        ExitProcess(9);
    }
    return EXCEPTION_CONTINUE_SEARCH;
}

static void __stdcall cb_fila(void *ctx, BOOLEAN canceled)
{
    (void)ctx; (void)canceled;
    InterlockedIncrement(&g_cb_rodou);
}
static void __stdcall cb_termino(void *ctx) { (void)ctx; InterlockedIncrement(&g_term_cb); }
static void __stdcall cb_monitor(void *ctx, queue_obj *q, unsigned p)
{
    (void)ctx; (void)q; (void)p;
}
static HRESULT __stdcall provedor(UINT32 op, const XAsyncProviderData *d)
{
    (void)op; (void)d;
    InterlockedIncrement(&g_prov_rodou);
    return S_OK;
}

static void linha(const char *caso, int ok, const char *det)
{
    printf("{\"caso\": \"%s\", \"ok\": %s, \"det\": \"%s\"}\n", caso, ok ? "true" : "false", det);
    fflush(stdout);
}

/* Toda função que recebe fila, contra uma alça que a peça não criou (ou já destruiu). */
static void contra(const char *nome, queue_obj *alca, const unsigned char *bloco,
                   const unsigned char *copia, size_t n)
{
    char caso[96], det[160];
    HRESULT hr;
    queue_obj *out, *proc;
    port_obj *porta;
    UINT64 tok = 0;
    XAsyncBlock b;
    BOOLEAN hit;

#define CASO(api) snprintf(caso, sizeof caso, "%s/%s", api, nome); g_onde = caso
    CASO("Duplicate");
    out = SENTINELA;
    hr = VT(Duplicate_t, 15)(g_self, alca, &out);
    snprintf(det, sizeof det, "hr=0x%08lX", (unsigned long)hr);
    linha(caso, hr == E_INVALIDARG_ && out == SENTINELA, det);

    CASO("Close");
    VT(Close_t, 17)(g_self, alca);
    linha(caso, 1, "");

    CASO("Submit");
    g_cb_rodou = 0;
    hr = VT(Submit_t, 18)(g_self, alca, 0, NULL, cb_fila);
    Sleep(20);
    snprintf(det, sizeof det, "hr=0x%08lX cb=%ld", (unsigned long)hr, (long)g_cb_rodou);
    linha(caso, hr == E_INVALIDARG_ && g_cb_rodou == 0, det);

    CASO("SubmitDelayed");
    g_cb_rodou = 0;
    hr = VT(SubmitDelayed_t, 19)(g_self, alca, 1, 0, NULL, cb_fila);
    Sleep(20);
    snprintf(det, sizeof det, "hr=0x%08lX cb=%ld", (unsigned long)hr, (long)g_cb_rodou);
    linha(caso, hr == E_INVALIDARG_ && g_cb_rodou == 0, det);

    CASO("GetPort");
    porta = (port_obj *)SENTINELA;
    hr = VT(GetPort_t, 14)(g_self, alca, 0, &porta);
    snprintf(det, sizeof det, "hr=0x%08lX", (unsigned long)hr);
    linha(caso, hr == E_INVALIDARG_ && porta == NULL, det);

    CASO("Dispatch");
    hit = VT(Dispatch_t, 16)(g_self, alca, 0, 0);
    linha(caso, !hit, "");

    CASO("Terminate");
    g_term_cb = 0;
    hr = VT(Terminate_t, 22)(g_self, alca, FALSE, NULL, cb_termino);
    snprintf(det, sizeof det, "hr=0x%08lX cb=%ld", (unsigned long)hr, (long)g_term_cb);
    linha(caso, hr == S_OK && g_term_cb == 1, det);

    CASO("RegMon");
    hr = VT(RegMon_t, 23)(g_self, alca, NULL, (void *)cb_monitor, &tok);
    snprintf(det, sizeof det, "hr=0x%08lX", (unsigned long)hr);
    linha(caso, FAILED(hr), det);

    CASO("UnregMon");
    VT(UnregMon_t, 24)(g_self, alca, 1);
    linha(caso, 1, "");

    CASO("SetProcessQueue");
    VT(SetProcessQueue_t, 26)(g_self, alca);
    proc = NULL;
    VT(GetProcessQueue_t, 25)(g_self, &proc);
    linha(caso, proc != NULL && proc != alca, "");
    if (proc) VT(Close_t, 17)(g_self, proc);

    CASO("QueueCreateComposite");
    out = SENTINELA;
    hr = VT(QueueCreateComposite_t, 13)(g_self, (port_obj *)alca, (port_obj *)alca, &out);
    snprintf(det, sizeof det, "hr=0x%08lX", (unsigned long)hr);
    linha(caso, hr == E_INVALIDARG_, det);

    CASO("Begin");
    memset(&b, 0, sizeof b);
    b.queue = alca;
    g_prov_rodou = 0;
    hr = VT(Begin_t, 7)(g_self, &b, NULL, NULL, "prova.fila-estranha", provedor);
    snprintf(det, sizeof det, "hr=0x%08lX prov=%ld", (unsigned long)hr, (long)g_prov_rodou);
    linha(caso, hr == E_INVALIDARG_ && g_prov_rodou == 0, det);

    if (bloco) {
        CASO("intacto");
        linha(caso, memcmp(bloco, copia, n) == 0, "a peça escreveu no bloco que não criou");
    }
#undef CASO
}

/* A tabela aguenta o vaivém: dois mil compostos fechados fora de ordem,
   e cada um recusado depois. */
static void vaivem(void)
{
    enum { N = 2000 };
    static queue_obj *qs[N];
    static int vivo[N];
    queue_obj *base = NULL, *out;
    port_obj *pw = NULL, *pc = NULL;
    unsigned s = 12345u;
    int i, criados = 0, erros = 0, ordem[N];
    char det[96];
    g_onde = "vaivem";
    VT(QueueCreate_t, 12)(g_self, 1, 1, &base);
    VT(GetPort_t, 14)(g_self, base, 0, &pw);
    VT(GetPort_t, 14)(g_self, base, 1, &pc);
    for (i = 0; i < N; i++) {
        vivo[i] = SUCCEEDED(VT(QueueCreateComposite_t, 13)(g_self, pw, pc, &qs[i]));
        criados += vivo[i];
        ordem[i] = i;
    }
    for (i = N - 1; i > 0; i--) {
        int j, t;
        s = s * 1103515245u + 12345u;
        j = (int)((s >> 8) % (unsigned)(i + 1));
        t = ordem[i]; ordem[i] = ordem[j]; ordem[j] = t;
    }
    for (i = 0; i < N; i++) {
        int k = ordem[i], j;
        VT(Close_t, 17)(g_self, qs[k]);
        vivo[k] = 0;
        if ((i % 250) != 249) continue;
        for (j = 0; j < N; j++) {
            HRESULT hr = VT(Duplicate_t, 15)(g_self, qs[j], &out);
            if (vivo[j] != SUCCEEDED(hr)) erros++;
            if (SUCCEEDED(hr)) VT(Close_t, 17)(g_self, out);
        }
    }
    snprintf(det, sizeof det, "criados=%d erros=%d", criados, erros);
    linha("vaivem", criados == N && erros == 0, det);
    VT(Close_t, 17)(g_self, base);
}

/* A fila que a peça criou continua valendo: Duplicate, Submit e o composto sobre ela. */
static void a_fila_dela_vale(void)
{
    queue_obj *q = NULL, *d = NULL, *c = NULL;
    port_obj *pw = NULL;
    HRESULT h1, h2, h3;
    int espera;
    char det[128];
    g_onde = "fila_criada";
    VT(QueueCreate_t, 12)(g_self, 1, 1, &q);
    h1 = VT(Duplicate_t, 15)(g_self, q, &d);
    g_cb_rodou = 0;
    h2 = VT(Submit_t, 18)(g_self, d, 0, NULL, cb_fila);
    for (espera = 0; espera < 200 && !g_cb_rodou; espera++) Sleep(5);
    VT(GetPort_t, 14)(g_self, q, 0, &pw);
    h3 = VT(QueueCreateComposite_t, 13)(g_self, pw, pw, &c);
    snprintf(det, sizeof det, "dup=0x%08lX submit=0x%08lX cb=%ld comp=0x%08lX",
             (unsigned long)h1, (unsigned long)h2, (long)g_cb_rodou, (unsigned long)h3);
    linha("fila_criada", h1 == S_OK && d == q && h2 == S_OK && g_cb_rodou == 1 && h3 == S_OK, det);
    if (c) VT(Close_t, 17)(g_self, c);
    if (d) VT(Close_t, 17)(g_self, d);
    if (q) VT(Close_t, 17)(g_self, q);
}

int main(int argc, char **argv)
{
    HMODULE mod;
    QueryApiImpl_t query;
    Ident_t ident;
    unsigned char pilha[512], forjada[512], copia_pilha[512], copia_forjada[512];
    unsigned int magic = 0x51554555u;
    queue_obj *destruida = NULL;
    if (argc < 2) return 2;
    AddVectoredExceptionHandler(1, ao_cair);
    mod = LoadLibraryA(argv[1]);
    if (!mod) { printf("{\"carregar\": %lu}\n", (unsigned long)GetLastError()); return 2; }
    ident = (Ident_t)(void *)GetProcAddress(mod, "HefestoPecaGdk");
    query = (QueryApiImpl_t)(void *)GetProcAddress(mod, "QueryApiImpl");
    if (!ident || strcmp(ident(), "hefesto-peca-gdk-1") != 0 || !query) return 3;
    if (FAILED(query(&IID_Threading, &IID_Threading, &g_self)) || !g_self) return 4;
    g_vt = *(void ***)g_self;

    a_fila_dela_vale();

    memset(pilha, 0, sizeof pilha);
    memcpy(copia_pilha, pilha, sizeof pilha);
    memset(forjada, 0, sizeof forjada);
    memcpy(forjada, &magic, sizeof magic);
    forjada[16] = 1;
    memcpy(copia_forjada, forjada, sizeof forjada);
    VT(QueueCreate_t, 12)(g_self, 1, 1, &destruida);
    VT(Close_t, 17)(g_self, destruida);
    Sleep(50);

    contra("menos_um", (queue_obj *)(INT_PTR)-1, NULL, NULL, 0);
    contra("valor_do_crash", (queue_obj *)(UINT_PTR)0xcf15dc7ed8420217ull, NULL, NULL, 0);
    contra("pilha_zerada", (queue_obj *)pilha, pilha, copia_pilha, sizeof pilha);
    contra("forjada_com_magic", (queue_obj *)forjada, forjada, copia_forjada, sizeof forjada);
    contra("destruida", destruida, NULL, NULL, 0);

    vaivem();
    printf("{\"fim\": true}\n");
    fflush(stdout);
    return 0;
}
"""

_CASOS_POR_ALCA = (
    "Duplicate", "Close", "Submit", "SubmitDelayed", "GetPort", "Dispatch", "Terminate", "RegMon",
    "UnregMon", "SetProcessQueue", "QueueCreateComposite", "Begin",
)


def _ensaio() -> ModuleType:
    spec = importlib.util.spec_from_file_location("o_contrato_da_peca_gdk_fila", _ENSAIO)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _achar_wine() -> Path | None:
    candidato = os.environ.get("HEFESTO_WINE")
    caminho = Path(candidato) if candidato else _ensaio().WINE_PADRAO
    return caminho if caminho.exists() else None


# Resolvido uma vez, na coleta: o conftest desvia o HOME de cada teste para um lar de mentira.
_WINE = _achar_wine()


def _corpo(texto: str, nome: str) -> str:
    """O corpo da função `nome` no fonte, da assinatura até a chave que fecha na coluna zero."""
    m = re.search(rf"^static [^\n]*\b{nome}\([^)]*\)\n\{{\n(.*?)^\}}\n", texto, re.S | re.M)
    assert m, f"{nome} sumiu do fonte"
    return m.group(1)


# --- o fonte: nenhuma função decide pelo magic do endereço que chegou -------------------


def test_queue_live_decide_pela_tabela_e_nao_pelo_magic() -> None:
    texto = _FONTE.read_text(encoding="utf-8")
    corpo = _corpo(texto, "queue_live")
    assert "magic" not in corpo, "o queue_live voltou a ler o magic no endereço que chegou"
    assert "viva_tem_locked" in corpo


def test_nenhuma_funcao_compara_o_magic_da_fila() -> None:
    texto = _FONTE.read_text(encoding="utf-8")
    assert not re.search(r"->magic\s*[!=]=\s*QUEUE_MAGIC", texto), (
        "há função decidindo se a fila vale pelo magic lido no endereço"
    )


def test_toda_funcao_que_recebe_fila_esta_na_prova() -> None:
    """Função nova da ABI que recebe fila e fica fora da prova é a próxima que cai calada."""
    texto = _FONTE.read_text(encoding="utf-8")
    padrao = r"^static [^\n(]*\bWINAPI (thr_\w+)\(void \*self, (?:queue_obj|port_obj) \*\w"
    recebem = set(re.findall(padrao, texto, re.M))
    recebem.add("thr_Begin")  # a fila vem dentro do XAsyncBlock
    assert recebem - set(_NAO_LEEM) == set(_RECEBEM_FILA), recebem ^ set(_RECEBEM_FILA)
    for api in _CASOS_POR_ALCA:
        assert f'CASO("{api}")' in _PROVA_C, api
    assert {f"thr_{api}" for api in _CASOS_POR_ALCA} == set(_RECEBEM_FILA)


def test_a_mordida_acha_o_trecho_da_cura_uma_vez() -> None:
    texto = _FONTE.read_text(encoding="utf-8")
    assert texto.count(_CURA) == 1


# --- a peça compilada, no Wine ----------------------------------------------------------

_precisa = pytest.mark.skipif(
    shutil.which(_CC) is None or _WINE is None, reason="sem o mingw-w64 no PATH ou sem um Wine"
)


@pytest.fixture(scope="module")
def _bancada() -> Iterator[tuple[Path, Path]]:
    wine = _WINE
    assert wine is not None
    ensaio = _ensaio()
    raiz = Path(tempfile.mkdtemp(prefix="gdkfila-", dir="/tmp"))
    try:
        prefixo = ensaio.prefixo_seguro(raiz / "pfx")
        ensaio.preparar_prefixo(wine, prefixo)
        (raiz / "prova.c").write_text(_PROVA_C, encoding="utf-8")
        subprocess.run([_CC, "-O2", "-Wall", "-o", str(raiz / "prova.exe"), str(raiz / "prova.c")],
                       check=True, capture_output=True, timeout=120)
        yield raiz, prefixo
    finally:
        env = ensaio.ambiente_wine(raiz / "pfx")
        subprocess.run([str(wine.with_name("wineserver")), "-k"], env=env, check=False, timeout=60,
                       capture_output=True)
        shutil.rmtree(raiz, ignore_errors=True)


def _rodar(bancada: tuple[Path, Path], fonte: str, nome: str) -> list[dict[str, object]]:
    raiz, prefixo = bancada
    wine = _WINE
    assert wine is not None
    pasta = raiz / nome
    pasta.mkdir()
    (pasta / "xgameruntime.c").write_text(fonte, encoding="utf-8")
    # As mesmas bandeiras do construir.sh; sem a marca builtin, carregada pelo caminho.
    cmd = [_CC, "-shared", "-O2", "-s", "-Wall", "-fno-ident",
           "-o", str(pasta / "peca.dll"), "xgameruntime.c"]
    subprocess.run(cmd, cwd=pasta, check=True, capture_output=True, timeout=300)
    shutil.copy2(raiz / "prova.exe", pasta / "prova.exe")
    env = _ensaio().ambiente_wine(prefixo)
    env["WINEDLLOVERRIDES"] = "mscoree,mshtml,winemenubuilder.exe="
    proc = subprocess.run([str(wine), "prova.exe", "peca.dll"], cwd=pasta, env=env, check=False,
                          timeout=240, capture_output=True, text=True, errors="replace")
    subprocess.run([str(wine.with_name("wineserver")), "-w"], env=env, check=False, timeout=120)
    linhas = []
    for linha in proc.stdout.replace("\r", "").splitlines():
        if linha.startswith("{"):
            linhas.append(json.loads(linha))
    return linhas


@_precisa
def test_a_peca_recusa_a_fila_que_nao_criou_sem_cair(_bancada: tuple[Path, Path]) -> None:
    linhas = _rodar(_bancada, _FONTE.read_text(encoding="utf-8"), "cura")
    caiu = [ln for ln in linhas if "caiu" in ln]
    assert not caiu, f"a peça caiu: {caiu}"
    assert {"fim": True} in linhas, "a prova não chegou ao fim"
    casos = {str(ln["caso"]): ln for ln in linhas if "caso" in ln}
    esperados = {f"{api}/{alca}" for api in _CASOS_POR_ALCA for alca in _ALCAS}
    esperados |= {"intacto/pilha_zerada", "intacto/forjada_com_magic", "fila_criada", "vaivem"}
    assert set(casos) == esperados, set(casos) ^ esperados
    reprovados = {k: v.get("det") for k, v in casos.items() if v["ok"] is not True}
    assert not reprovados, reprovados


@_precisa
def test_a_mordida_o_magic_lido_de_volta_derruba_a_prova(_bancada: tuple[Path, Path]) -> None:
    texto = _FONTE.read_text(encoding="utf-8")
    quebrado = texto.replace(_CURA, _QUEBRADO, 1)
    assert quebrado != texto
    linhas = _rodar(_bancada, quebrado, "mordida")
    caiu = [ln for ln in linhas if "caiu" in ln]
    assert caiu, "com o magic lido de volta a prova devia cair, e não caiu: a régua não morde"
    assert {"fim": True} not in linhas
