/* A sonda do GameInput da casa: carrega o xgameruntime como um jogo GDK carrega, deixa a peça
 * puxar o gameinput.dll, e então pede a vibração do jeito do Wwise Motion (o QI v2, o
 * RegisterDeviceCallback bloqueante, o GetDeviceInfo do v0 e o SetRumbleState). Imprime uma
 * linha JSON por prova. Roda num prefixo de teste com o aparelho dublê; quem julga os bytes
 * que chegaram ao aparelho é scripts/ensaios/o_contrato_da_peca_gameinput.py. */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef HRESULT (WINAPI *InitializeApiImpl_t)(UINT64, UINT64);
typedef HRESULT (WINAPI *GameInputCreate_t)(void **);
typedef const char *(WINAPI *HefestoPecaGameInput_t)(void);

typedef HRESULT (WINAPI *QI_t)(void *, const GUID *, void **);
typedef ULONG (WINAPI *Release_t)(void *);
typedef void (WINAPI *cb_t)(uint64_t, void *, void *, uint64_t, uint32_t, uint32_t);
typedef HRESULT (WINAPI *RegisterDeviceCallback_t)(void *, void *, uint32_t, uint32_t, int, void *, cb_t, uint64_t *);
typedef unsigned char (WINAPI *Unregister_t)(void *, uint64_t);
typedef HRESULT (WINAPI *GetCurrentReading_t)(void *, uint32_t, void *, void **);
typedef unsigned char (WINAPI *GetGamepadState_t)(void *, void *);
typedef const unsigned char *(WINAPI *GetDeviceInfo0_t)(void *);
typedef HRESULT (WINAPI *GetDeviceInfo2_t)(void *, const unsigned char **);
typedef void (WINAPI *SetRumbleState_t)(void *, const float *);

static const GUID IID_v2_IGameInput = { 0xbbaa66d2, 0x837a, 0x40f7, { 0xa3, 0x03, 0x91, 0x7d, 0x50, 0x09, 0x55, 0xf4 } };
static const GUID IID_v0_IGameInputDevice = { 0x31dd86fb, 0x4c1b, 0x408a, { 0x86, 0x8f, 0x43, 0x9b, 0x3c, 0xd4, 0x71, 0x25 } };
static const GUID IID_v2_IGameInputDevice = { 0x39a0c9f2, 0xf055, 0x4089, { 0x96, 0xe7, 0x25, 0xb2, 0x75, 0x6d, 0x30, 0x77 } };

#define VT(obj, type, idx) ((type)((*(void ***)(obj))[idx]))

/* O que o Wwise Motion pede (medido no Dungeons II): todo controle, conectado ou com háptica. */
#define KIND_DO_WWISE 0x000F000Eu
#define FILTRO_DO_WWISE 0x00200001u
#define KIND_GAMEPAD 0x00040000u
#define ENUM_BLOCKING 2
#define OFF_ID_V0 0x20
#define OFF_MOTORES_V0 0x6c
#define OFF_ID_V2 0x1a

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

static void *g_dev[8];
static int g_dev_n;

static void WINAPI no_aparelho(uint64_t token, void *ctx, void *dev, uint64_t ts, uint32_t cur, uint32_t prev)
{
    (void)token; (void)ctx; (void)ts; (void)prev;
    if ((cur & 1) && g_dev_n < 8) g_dev[g_dev_n++] = dev;
}

typedef struct {
    uint32_t buttons;
    float lt, rt, lx, ly, rx, ry;
} pad_state;

static int ler_pad(void *gi2, void *dev2, pad_state *s, uint32_t botao, float lx_quer)
{
    int i;
    for (i = 0; i < 40; i++) {
        void *r = NULL;
        HRESULT hr = VT(gi2, GetCurrentReading_t, 4)(gi2, KIND_GAMEPAD, dev2, &r);
        memset(s, 0, sizeof *s);
        if (SUCCEEDED(hr) && r) {
            unsigned char ok = VT(r, GetGamepadState_t, 18)(r, s);
            VT(r, Release_t, 2)(r);
            if (ok && (s->buttons & botao) == botao && s->lx > lx_quer - 0.01f && s->lx < lx_quer + 0.01f)
                return 1;
        }
        Sleep(50);
    }
    return 0;
}

static void hex_id(const unsigned char *id, char *out)
{
    int i;
    for (i = 0; i < 8; i++) sprintf(out + i * 2, "%02x", id[i]);
}

int main(void)
{
    HMODULE xgr, gi;
    InitializeApiImpl_t init;
    GameInputCreate_t create;
    void *gi0 = NULL, *gi2 = NULL, *d0[2] = { NULL, NULL }, *d2[2] = { NULL, NULL };
    const unsigned char *info0[2] = { NULL, NULL }, *info2[2] = { NULL, NULL };
    uint64_t token = 0;
    HRESULT hr;
    int i, ok;
    char id0[17], id1[17];

    /* preload: o LoadLibrary("GameInput.dll") do jogo recebe a peça da casa, e não a embutida */
    xgr = LoadLibraryA("xgameruntime.dll");
    init = xgr ? (InitializeApiImpl_t)(void *)GetProcAddress(xgr, "InitializeApiImpl") : NULL;
    if (init) init(0, 0);
    gi = LoadLibraryW(L"GameInput.dll");
    ok = gi && GetProcAddress(gi, "HefestoPecaGameInput");
    provas_linha("preload", ok, "\"xgameruntime\": %s, \"gameinput\": %s", xgr ? "true" : "false",
                 gi ? "true" : "false");

    create = gi ? (GameInputCreate_t)(void *)GetProcAddress(gi, "GameInputCreate") : NULL;
    hr = create ? create(&gi0) : E_FAIL;
    if (SUCCEEDED(hr) && gi0) hr = VT(gi0, QI_t, 0)(gi0, &IID_v2_IGameInput, &gi2);
    provas_linha("qi_v2", SUCCEEDED(hr) && gi2 != NULL, "\"hr\": \"%08lX\"", (unsigned long)hr);
    if (!gi2) {
        printf("{\"fim\": true}\n");
        return 0;
    }

    /* aparelhos: a enumeração bloqueante lista os dois, com o filtro do Wwise */
    hr = VT(gi2, RegisterDeviceCallback_t, 8)(gi2, NULL, KIND_DO_WWISE, FILTRO_DO_WWISE, ENUM_BLOCKING,
                                               NULL, no_aparelho, &token);
    provas_linha("aparelhos", SUCCEEDED(hr) && token && g_dev_n == 2 && g_dev[0] != g_dev[1],
                 "\"hr\": \"%08lX\", \"n\": %d", (unsigned long)hr, g_dev_n);
    if (g_dev_n < 2) {
        printf("{\"fim\": true}\n");
        return 0;
    }

    for (i = 0; i < 2; i++) {
        VT(g_dev[i], QI_t, 0)(g_dev[i], &IID_v0_IGameInputDevice, &d0[i]);
        VT(g_dev[i], QI_t, 0)(g_dev[i], &IID_v2_IGameInputDevice, &d2[i]);
        if (d0[i]) info0[i] = VT(d0[i], GetDeviceInfo0_t, 3)(d0[i]);
        if (d2[i]) VT(d2[i], GetDeviceInfo2_t, 3)(d2[i], &info2[i]);
    }

    /* motores: o Wwise descarta o aparelho cujo supportedRumbleMotors é zero */
    ok = info0[0] && info0[1] && *(const uint32_t *)(info0[0] + OFF_MOTORES_V0) != 0 &&
         *(const uint32_t *)(info0[1] + OFF_MOTORES_V0) != 0;
    provas_linha("motores", ok, "\"motores\": %u",
                 info0[0] ? *(const uint32_t *)(info0[0] + OFF_MOTORES_V0) : 0u);

    /* device_id: estável, igual no v0 e no v2, e distinto entre os dois aparelhos */
    ok = info0[0] && info0[1] && info2[0] && info2[1];
    if (ok) {
        const unsigned char *de_novo = VT(d0[0], GetDeviceInfo0_t, 3)(d0[0]);
        ok = !memcmp(de_novo + OFF_ID_V0, info0[0] + OFF_ID_V0, 32) &&
             !memcmp(info0[0] + OFF_ID_V0, info2[0] + OFF_ID_V2, 32) &&
             !memcmp(info0[1] + OFF_ID_V0, info2[1] + OFF_ID_V2, 32) &&
             memcmp(info0[0] + OFF_ID_V0, info0[1] + OFF_ID_V0, 32) != 0;
        hex_id(info0[0] + OFF_ID_V0, id0);
        hex_id(info0[1] + OFF_ID_V0, id1);
    } else {
        strcpy(id0, "-");
        strcpy(id1, "-");
    }
    provas_linha("device_id", ok, "\"id0\": \"%s\", \"id1\": \"%s\"", id0, id1);

    /* leitura: o cabo com o direcional esquerdo à direita, R2 no fundo e a cruz; o rádio com o
     * direcional à esquerda, o hat para cima e o triângulo */
    {
        pad_state s0, s1;
        int ok0 = d2[0] && ler_pad(gi2, d2[0], &s0, 0x0004, 1.0f) && s0.rt > 0.99f;
        int ok1 = d2[1] && ler_pad(gi2, d2[1], &s1, 0x0020 | 0x0040, -1.0f);
        provas_linha("leitura", ok0 && ok1,
                     "\"cabo\": {\"botoes\": %u, \"lx\": %.3f, \"rt\": %.3f}, "
                     "\"radio\": {\"botoes\": %u, \"lx\": %.3f}",
                     s0.buttons, s0.lx, s0.rt, s1.buttons, s1.lx);
    }

    /* rumble: o cabo pelo v0 (o caminho do Wwise), o rádio pelo v2; segura 2,3 s para o
     * reenvio aparecer, e zera três vezes (só a primeira chega ao aparelho) */
    {
        float cabo[4] = { 1.0f, 0.5f, 0.0f, 0.0f };
        float radio[4] = { 0.25f, 0.75f, 0.0f, 0.0f };
        float zero[4] = { 0.0f, 0.0f, 0.0f, 0.0f };
        VT(d0[0], SetRumbleState_t, 10)(d0[0], cabo);
        VT(d2[1], SetRumbleState_t, 9)(d2[1], radio);
        VT(d0[0], SetRumbleState_t, 10)(d0[0], cabo);
        Sleep(2300);
        for (i = 0; i < 3; i++) {
            VT(d0[0], SetRumbleState_t, 10)(d0[0], zero);
            VT(d2[1], SetRumbleState_t, 9)(d2[1], zero);
        }
        provas_linha("rumble", 1, "");
    }

    VT(gi2, Unregister_t, 12)(gi2, token);
    printf("{\"fim\": true}\n");
    fflush(stdout);
    return 0;
}
