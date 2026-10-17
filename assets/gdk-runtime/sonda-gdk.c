/* A sonda da peça GDK do Hefesto: carrega o xgameruntime como um jogo carrega, pega a ABI do
 * XAsync/XTaskQueue pelo QueryApiImpl e imprime uma linha JSON por prova do contrato.
 * Roda num prefixo de teste, sem jogo; quem julga é scripts/ensaios/o_contrato_da_peca_gdk.py. */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdarg.h>
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

#define OP_BEGIN 0
#define OP_DOWORK 1
#define OP_CLEANUP 4
#define PORT_WORK 0
#define PORT_COMP 1
#define MODE_THREADPOOL 1
#define E_NO_TASK_QUEUE ((HRESULT)0x800701AB)

typedef HRESULT (WINAPI *GetStatus_t)(void *, XAsyncBlock *, BOOLEAN);
typedef HRESULT (WINAPI *Begin_t)(void *, XAsyncBlock *, void *, const void *, const char *, XAsyncProvider);
typedef HRESULT (WINAPI *Schedule_t)(void *, XAsyncBlock *, UINT32);
typedef void (WINAPI *Complete_t)(void *, XAsyncBlock *, HRESULT, SIZE_T);
typedef HRESULT (WINAPI *QueueCreate_t)(void *, UINT32, UINT32, queue_obj **);
typedef HRESULT (WINAPI *QueueCreateComposite_t)(void *, port_obj *, port_obj *, queue_obj **);
typedef HRESULT (WINAPI *GetPort_t)(void *, queue_obj *, UINT32, port_obj **);
typedef HRESULT (WINAPI *Duplicate_t)(void *, queue_obj *, queue_obj **);
typedef void (WINAPI *Close_t)(void *, queue_obj *);
typedef HRESULT (WINAPI *Submit_t)(void *, queue_obj *, UINT32, void *, XTaskQueueCallback);
typedef HRESULT (WINAPI *Terminate_t)(void *, queue_obj *, BOOLEAN, void *, void (__stdcall *)(void *));
typedef BOOLEAN (WINAPI *GetProcessQueue_t)(void *, queue_obj **);
typedef void (WINAPI *SetProcessQueue_t)(void *, queue_obj *);
typedef HRESULT (WINAPI *QueryApiImpl_t)(const GUID *, const GUID *, void **);
typedef const char *(WINAPI *HefestoPecaGdk_t)(void);

static const GUID IID_Threading = { 0x073b7dcb, 0x1fcf, 0x4030, { 0x94, 0xbe, 0xe3, 0xc9, 0xeb, 0x62, 0x34, 0x28 } };

static void *g_self;
static void **g_vt;
#define VT(type, idx) ((type)g_vt[idx])

static void provas_linha(const char *prova, int ok, const char *fmt, ...)
{
    char extra[600];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(extra, sizeof extra, fmt, ap);
    va_end(ap);
    printf("{\"prova\": \"%s\", \"ok\": %s%s%s}\n", prova, ok ? "true" : "false",
           extra[0] ? ", " : "", extra);
    fflush(stdout);
}

/* ---- o provedor de teste ---- */

static volatile LONG g_prov_calls;
static queue_obj *volatile g_prov_queue;
static XAsyncBlock *volatile g_prov_block;
static volatile LONG g_work_ms;
static volatile LONG g_done;

static HRESULT __stdcall provedor(UINT32 op, const XAsyncProviderData *data)
{
    InterlockedIncrement(&g_prov_calls);
    if (op == OP_BEGIN) {
        g_prov_queue = data->async->queue;
        g_prov_block = data->async;
        return VT(Schedule_t, 9)(g_self, data->async, 0);
    }
    if (op == OP_DOWORK) {
        if (g_work_ms) Sleep((DWORD)g_work_ms);
        VT(Complete_t, 10)(g_self, data->async, S_OK, 0);
    }
    return S_OK;
}

static void __stdcall ao_concluir(XAsyncBlock *b)
{
    (void)b;
    InterlockedExchange(&g_done, 1);
}

static int espera(volatile LONG *flag, DWORD ms)
{
    DWORD t0 = GetTickCount();
    while (!*flag && GetTickCount() - t0 < ms) Sleep(5);
    return *flag != 0;
}

/* 1. XAsyncBegin com fila nula: o provedor vê a fila do processo, numa cópia do bloco. */
static void prova_fila_nula(void)
{
    XAsyncBlock b;
    queue_obj *proc = NULL;
    HRESULT hr, st;
    memset(&b, 0, sizeof b);
    g_prov_queue = NULL;
    g_prov_block = NULL;
    g_work_ms = 0;
    VT(GetProcessQueue_t, 25)(g_self, &proc);
    hr = VT(Begin_t, 7)(g_self, &b, NULL, NULL, "sonda.fila_nula", provedor);
    st = SUCCEEDED(hr) ? VT(GetStatus_t, 3)(g_self, &b, TRUE) : hr;
    provas_linha("fila_nula", SUCCEEDED(hr) && st == S_OK && proc && g_prov_queue == proc && g_prov_block != &b,
                 "\"begin\": \"0x%08lX\", \"status\": \"0x%08lX\", \"fila_do_processo\": \"%p\", "
                 "\"fila_que_o_provedor_viu\": \"%p\", \"provedor_recebeu_copia\": %s",
                 (unsigned long)hr, (unsigned long)st, (void *)proc, (void *)g_prov_queue,
                 g_prov_block && g_prov_block != &b ? "true" : "false");
    if (proc) VT(Close_t, 17)(g_self, proc);
}

/* 2. Depois de SetCurrentProcessTaskQueue(NULL): E_NO_TASK_QUEUE, e o provedor não roda. */
static void prova_sem_fila_do_processo(void)
{
    XAsyncBlock b;
    queue_obj *antes = NULL;
    LONG calls;
    HRESULT hr;
    memset(&b, 0, sizeof b);
    VT(GetProcessQueue_t, 25)(g_self, &antes);
    VT(SetProcessQueue_t, 26)(g_self, NULL);
    calls = g_prov_calls;
    hr = VT(Begin_t, 7)(g_self, &b, NULL, NULL, "sonda.sem_fila", provedor);
    provas_linha("sem_fila_do_processo", hr == E_NO_TASK_QUEUE && g_prov_calls == calls,
                 "\"begin\": \"0x%08lX\", \"provedor_chamado\": %ld",
                 (unsigned long)hr, (long)(g_prov_calls - calls));
    VT(SetProcessQueue_t, 26)(g_self, antes);
    if (antes) VT(Close_t, 17)(g_self, antes);
}

/* 3. Cem pares Duplicate/Close num composto: o CreateComposite sobre ele ainda dá S_OK. */
static void prova_duplicate_close(void)
{
    queue_obj *base = NULL, *comp = NULL, *dup, *neto = NULL;
    port_obj *bw = NULL, *bc = NULL, *cw = NULL, *cc = NULL;
    HRESULT hr, hp1 = E_FAIL, hp2 = E_FAIL;
    int i, falhas = 0;
    VT(QueueCreate_t, 12)(g_self, MODE_THREADPOOL, MODE_THREADPOOL, &base);
    VT(GetPort_t, 14)(g_self, base, PORT_WORK, &bw);
    VT(GetPort_t, 14)(g_self, base, PORT_COMP, &bc);
    VT(QueueCreateComposite_t, 13)(g_self, bw, bc, &comp);
    for (i = 0; i < 100; i++) {
        dup = NULL;
        if (FAILED(VT(Duplicate_t, 15)(g_self, comp, &dup)) || !dup) { falhas++; continue; }
        VT(Close_t, 17)(g_self, dup);
    }
    hp1 = VT(GetPort_t, 14)(g_self, comp, PORT_WORK, &cw);
    hp2 = VT(GetPort_t, 14)(g_self, comp, PORT_COMP, &cc);
    hr = (SUCCEEDED(hp1) && SUCCEEDED(hp2)) ? VT(QueueCreateComposite_t, 13)(g_self, cw, cc, &neto) : E_FAIL;
    provas_linha("duplicate_close", falhas == 0 && hr == S_OK,
                 "\"duplicate_falhou\": %d, \"getport\": \"0x%08lX\", \"create_composite\": \"0x%08lX\"",
                 falhas, (unsigned long)(FAILED(hp1) ? hp1 : hp2), (unsigned long)hr);
    if (neto) VT(Close_t, 17)(g_self, neto);
    if (comp) VT(Close_t, 17)(g_self, comp);
    if (base) VT(Close_t, 17)(g_self, base);
}

/* 4. Composto de composto: o trabalho submetido e a operação assíncrona rodam. */
static volatile LONG g_submit_ran;
static void __stdcall ao_submeter(void *ctx, BOOLEAN canceled)
{
    (void)ctx; (void)canceled;
    InterlockedExchange(&g_submit_ran, 1);
}

static void prova_composto_de_composto(void)
{
    queue_obj *base = NULL, *c1 = NULL, *c2 = NULL;
    port_obj *bw = NULL, *bc = NULL, *w1 = NULL, *k1 = NULL;
    XAsyncBlock b;
    HRESULT hs, hb, st = E_FAIL;
    int ran;
    VT(QueueCreate_t, 12)(g_self, MODE_THREADPOOL, MODE_THREADPOOL, &base);
    VT(GetPort_t, 14)(g_self, base, PORT_WORK, &bw);
    VT(GetPort_t, 14)(g_self, base, PORT_COMP, &bc);
    VT(QueueCreateComposite_t, 13)(g_self, bw, bc, &c1);
    VT(GetPort_t, 14)(g_self, c1, PORT_WORK, &w1);
    VT(GetPort_t, 14)(g_self, c1, PORT_COMP, &k1);
    VT(QueueCreateComposite_t, 13)(g_self, w1, k1, &c2);
    g_submit_ran = 0;
    hs = c2 ? VT(Submit_t, 18)(g_self, c2, PORT_WORK, NULL, ao_submeter) : E_FAIL;
    ran = SUCCEEDED(hs) && espera(&g_submit_ran, 5000);
    memset(&b, 0, sizeof b);
    b.queue = c2;
    b.callback = ao_concluir;
    g_done = 0;
    g_work_ms = 0;
    hb = c2 ? VT(Begin_t, 7)(g_self, &b, NULL, NULL, "sonda.composto", provedor) : E_FAIL;
    if (SUCCEEDED(hb)) {
        espera(&g_done, 5000);
        st = g_done ? S_OK : E_PENDING;
    }
    provas_linha("composto_de_composto", ran && SUCCEEDED(hb) && st == S_OK,
                 "\"submit\": \"0x%08lX\", \"trabalho_rodou\": %s, \"begin\": \"0x%08lX\", \"conclusao_entregue\": %s",
                 (unsigned long)hs, ran ? "true" : "false", (unsigned long)hb, st == S_OK ? "true" : "false");
    if (c2) VT(Close_t, 17)(g_self, c2);
    if (c1) VT(Close_t, 17)(g_self, c1);
    if (base) VT(Close_t, 17)(g_self, base);
}

/* 5. XTaskQueueTerminate(wait) só volta depois de a operação em voo entregar a conclusão. */
static volatile LONG g_term_cb;
static void __stdcall ao_terminar(void *ctx)
{
    (void)ctx;
    InterlockedExchange(&g_term_cb, 1);
}

static void prova_terminate_espera(void)
{
    queue_obj *q = NULL;
    XAsyncBlock b;
    HRESULT hb, ht = E_FAIL;
    LONG conclusao_antes_do_fim = 0;
    DWORD t0, gasto = 0;
    VT(QueueCreate_t, 12)(g_self, MODE_THREADPOOL, MODE_THREADPOOL, &q);
    memset(&b, 0, sizeof b);
    b.queue = q;
    b.callback = ao_concluir;
    g_done = 0;
    g_term_cb = 0;
    g_work_ms = 400;
    hb = q ? VT(Begin_t, 7)(g_self, &b, NULL, NULL, "sonda.terminate", provedor) : E_FAIL;
    Sleep(20);
    t0 = GetTickCount();
    if (SUCCEEDED(hb)) {
        ht = VT(Terminate_t, 22)(g_self, q, TRUE, NULL, ao_terminar);
        gasto = GetTickCount() - t0;
        conclusao_antes_do_fim = g_done;
    }
    g_work_ms = 0;
    provas_linha("terminate_espera", SUCCEEDED(hb) && ht == S_OK && conclusao_antes_do_fim && g_term_cb,
                 "\"begin\": \"0x%08lX\", \"terminate\": \"0x%08lX\", \"conclusao_antes_de_voltar\": %s, "
                 "\"callback_do_termino\": %s, \"ms\": %lu",
                 (unsigned long)hb, (unsigned long)ht, conclusao_antes_do_fim ? "true" : "false",
                 g_term_cb ? "true" : "false", (unsigned long)gasto);
    if (q) VT(Close_t, 17)(g_self, q);
}

/* 6. O módulo carregado é a peça do Hefesto (marca builtin no 0x40 e a exportação de identidade),
 * mesmo com uma DLL forjada ao lado do exe. O GetModuleFileName do builtin aponta para a pasta do
 * app, então ele vai junto só como informação. */
static void prova_peca_carregada(HMODULE mod)
{
    static const char marca[] = "Wine builtin DLL";
    WCHAR wpath[MAX_PATH];
    char path[MAX_PATH * 3], esc[MAX_PATH * 6];
    const char *id = NULL;
    HefestoPecaGdk_t ident;
    int tem_marca, i, j;
    tem_marca = memcmp((const unsigned char *)mod + 0x40, marca, sizeof marca) == 0;
    ident = (HefestoPecaGdk_t)(void *)GetProcAddress(mod, "HefestoPecaGdk");
    if (ident) id = ident();
    path[0] = 0;
    if (GetModuleFileNameW(mod, wpath, MAX_PATH))
        WideCharToMultiByte(CP_UTF8, 0, wpath, -1, path, sizeof path, NULL, NULL);
    for (i = j = 0; path[i] && j + 2 < (int)sizeof esc; i++) {
        if (path[i] == '\\' || path[i] == '"') esc[j++] = '\\';
        esc[j++] = path[i];
    }
    esc[j] = 0;
    provas_linha("peca_carregada", tem_marca && id && strcmp(id, "hefesto-peca-gdk-1") == 0,
                 "\"marca_builtin\": %s, \"identidade\": \"%s\", \"caminho\": \"%s\"",
                 tem_marca ? "true" : "false", id ? id : "", esc);
}

int main(void)
{
    HMODULE mod = LoadLibraryA("xgameruntime.dll");
    QueryApiImpl_t query;
    HRESULT hr;
    if (!mod) {
        provas_linha("carregar", 0, "\"erro\": %lu", (unsigned long)GetLastError());
        return 2;
    }
    prova_peca_carregada(mod);
    query = (QueryApiImpl_t)(void *)GetProcAddress(mod, "QueryApiImpl");
    hr = query ? query(&IID_Threading, &IID_Threading, &g_self) : E_FAIL;
    if (FAILED(hr) || !g_self) {
        provas_linha("threading", 0, "\"query\": \"0x%08lX\"", (unsigned long)hr);
        return 3;
    }
    g_vt = *(void ***)g_self;
    prova_fila_nula();
    prova_sem_fila_do_processo();
    prova_duplicate_close();
    prova_composto_de_composto();
    prova_terminate_espera();
    printf("{\"fim\": true}\n");
    fflush(stdout);
    return 0;
}
