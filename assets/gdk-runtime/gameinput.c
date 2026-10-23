/* O GameInput do Hefesto: o gameinput.dll que o jogo GDK recebe no lugar do stub do Proton.
 *
 * Responde ao IGameInput v0, v1 e v2, lista cada DualSense (o pad virtual do Hefesto ou um
 * DualSense direto) como IGameInputDevice com motores de rumble e entrega a leitura do Gamepad.
 * O SetRumbleState vira o report 0x02 do DualSense com flag0 = 0x03 (só os motores), escrito no
 * HID do aparelho: o pad virtual repassa ao controle físico, no cabo e no rádio, de um a quatro
 * jogadores. A peça xgameruntime a carrega pelo caminho inteiro no XGameRuntimeInitialize; sem
 * isso, o jogo fica com o GameInput do Proton, como sempre ficou.
 *
 * Escrita do zero sobre a ABI pública do GameInput (IIDs, vtables e layout das estruturas).
 *
 * Copyright (c) 2026 Hefesto-Team
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software
 * and associated documentation files (the "Software"), to deal in the Software without
 * restriction, including without limitation the rights to use, copy, modify, merge, publish,
 * distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the
 * Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or
 * substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
 * BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 * NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
 * DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE. */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <setupapi.h>
#include <hidsdi.h>
#include <hidpi.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define PECA_GAMEINPUT_ID "hefesto-peca-gameinput-1"

/* ---------- a ABI ---------- */

#define GAMEINPUT_E_DEVICE_NOT_FOUND ((HRESULT)0x838a0002)
#define GAMEINPUT_E_READING_NOT_FOUND ((HRESULT)0x838a0003)
#define GAMEINPUT_E_HAPTIC_INFO_NOT_FOUND ((HRESULT)0x838a000a)

#define KIND_CONTROLLER 0x0000000eu
#define KIND_GAMEPAD 0x00040000u
#define KINDS_DO_PAD (KIND_CONTROLLER | KIND_GAMEPAD)

#define STATUS_CONNECTED 0x00000001u
#define ENUM_NONE 0
#define ENUM_ASYNC 1
#define ENUM_BLOCKING 2

#define RUMBLE_LOW 0x1u
#define RUMBLE_HIGH 0x2u
#define RUMBLE_LT 0x4u
#define RUMBLE_RT 0x8u
/* Os gatilhos não têm motor no DualSense e não vibram; o bit vai declarado porque o Wwise
 * descarta o aparelho que não declara motor nenhum. */
#define MOTORES_DE_RUMBLE (RUMBLE_LOW | RUMBLE_HIGH | RUMBLE_LT | RUMBLE_RT)

/* O byte de validade do report 0x02: 0x01 (vibração compatível) e 0x02 (seleção dos motores).
 * O DualSense e o pad virtual só olham o campo cujo bit veio ligado; a luz e os gatilhos que o
 * jogo manda pelo mesmo HID ficam intocados. */
#define FLAG0_VIBRACAO 0x03

/* O pad virtual zera o rumble parado há mais de 3 s; o valor diferente de zero se reenvia antes. */
#define REENVIO_MS 1000ull

typedef uint64_t gi_token;

typedef struct { BYTE value[32]; } gi_app_id;
typedef struct { uint16_t page, id; } gi_usage;
typedef struct { uint16_t major, minor, build, revision; } gi_version;
typedef struct { uint32_t sizeInBytes, codePointCount; const char *data; } gi_string;
typedef struct { int32_t label[14]; } gi_gamepad_info;

typedef struct {
    uint32_t buttons;
    float leftTrigger, rightTrigger;
    float leftThumbstickX, leftThumbstickY, rightThumbstickX, rightThumbstickY;
} gi_gamepad_state;

typedef struct { float lowFrequency, highFrequency, leftTrigger, rightTrigger; } gi_rumble;

typedef struct {
    float chargeRate, maxChargeRate, remainingCapacity, fullChargeCapacity;
    int32_t status;
} gi_battery;

typedef struct {
    uint32_t infoSize;
    uint16_t vendorId, productId, revisionNumber;
    uint8_t interfaceNumber, collectionNumber;
    gi_usage usage;
    gi_version hardwareVersion, firmwareVersion;
    gi_app_id deviceId, deviceRootId;
    int32_t deviceFamily;
    uint32_t capabilities, supportedInput, supportedRumbleMotors;
    uint32_t inputReportCount, outputReportCount, featureReportCount;
    uint32_t controllerAxisCount, controllerButtonCount, controllerSwitchCount;
    uint32_t touchPointCount, touchSensorCount, forceFeedbackMotorCount, hapticFeedbackMotorCount;
    uint32_t deviceStringCount, deviceDescriptorSize;
    const void *inputReportInfo, *outputReportInfo, *featureReportInfo;
    const void *controllerAxisInfo, *controllerButtonInfo, *controllerSwitchInfo;
    const void *keyboardInfo, *mouseInfo, *touchSensorInfo, *motionInfo;
    const void *arcadeStickInfo, *flightStickInfo;
    const gi_gamepad_info *gamepadInfo;
    const void *racingWheelInfo, *uiNavigationInfo, *forceFeedbackMotorInfo, *hapticFeedbackMotorInfo;
    const gi_string *displayName, *deviceStrings;
    const void *deviceDescriptorData;
    uint32_t supportedSystemButtons;
} gi_info_v0;

typedef struct {
    uint16_t vendorId, productId;
    gi_usage usage;
    gi_app_id deviceId, deviceRootId;
    int32_t deviceFamily;
    uint32_t supportedInput, supportedRumbleMotors, supportedSystemButtons;
    const char *displayName, *pnpPath;
    const void *keyboardInfo, *mouseInfo, *arcadeStickInfo, *flightStickInfo;
    const gi_gamepad_info *gamepadInfo;
    const void *racingWheelInfo, *uiNavigationInfo;
    uint32_t controllerAxisCount;
    const void *controllerAxisInfo;
    uint32_t controllerButtonCount;
    const void *controllerButtonInfo;
    uint32_t controllerSwitchCount;
    const void *controllerSwitchInfo;
    uint32_t forceFeedbackMotorCount;
    const void *forceFeedbackMotorInfo;
} gi_info_v1;

typedef struct {
    uint16_t vendorId, productId, revisionNumber;
    gi_usage usage;
    gi_version hardwareVersion, firmwareVersion;
    gi_app_id deviceId, deviceRootId;
    int32_t deviceFamily;
    uint32_t supportedInput, supportedRumbleMotors, supportedSystemButtons;
    GUID containerId;
    const char *displayName, *pnpPath;
    const void *keyboardInfo, *mouseInfo, *sensorsInfo, *arcadeStickInfo, *flightStickInfo;
    const gi_gamepad_info *gamepadInfo;
    const void *racingWheelInfo, *uiNavigationInfo;
    uint32_t controllerAxisCount;
    const void *controllerAxisInfo;
    uint32_t controllerButtonCount;
    const void *controllerButtonInfo;
    uint32_t controllerSwitchCount;
    const void *controllerSwitchInfo;
    uint32_t forceFeedbackMotorCount;
    const void *forceFeedbackMotorInfo;
} gi_info_v2;

/* Os offsets que o Wwise Motion lê do v0 (deviceId e supportedRumbleMotors). */
_Static_assert(offsetof(gi_info_v0, deviceId) == 0x20, "deviceId fora do lugar");
_Static_assert(offsetof(gi_info_v0, supportedRumbleMotors) == 0x6c, "motores fora do lugar");

static const GUID IID_IUnknown_ = { 0x00000000, 0x0000, 0x0000, { 0xc0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46 } };
static const GUID IID_v0_IGameInput = { 0x11be2a7e, 0x4254, 0x445a, { 0x9c, 0x09, 0xff, 0xc4, 0x0f, 0x00, 0x69, 0x18 } };
static const GUID IID_v1_IGameInput = { 0x40ffb7e4, 0x6150, 0x407a, { 0xb4, 0x39, 0x13, 0x2b, 0xad, 0xc0, 0x8d, 0x2d } };
static const GUID IID_v2_IGameInput = { 0xbbaa66d2, 0x837a, 0x40f7, { 0xa3, 0x03, 0x91, 0x7d, 0x50, 0x09, 0x55, 0xf4 } };
static const GUID IID_v0_IGameInputReading = { 0x2156947a, 0xe1fa, 0x4de0, { 0xa3, 0x0b, 0xd8, 0x12, 0x93, 0x1d, 0xbd, 0x8d } };
static const GUID IID_v1_IGameInputReading = { 0x86318e60, 0x0b3c, 0x40d6, { 0xbe, 0xfa, 0xc6, 0x2f, 0x2d, 0x95, 0x27, 0x24 } };
static const GUID IID_v2_IGameInputReading = { 0x65f06483, 0xdb76, 0x40b7, { 0xb7, 0x45, 0xf5, 0x91, 0xfa, 0xe5, 0x5f, 0xc9 } };
static const GUID IID_v0_IGameInputDevice = { 0x31dd86fb, 0x4c1b, 0x408a, { 0x86, 0x8f, 0x43, 0x9b, 0x3c, 0xd4, 0x71, 0x25 } };
static const GUID IID_v1_IGameInputDevice = { 0xb169652a, 0x4a32, 0x40d7, { 0x9f, 0xa9, 0x90, 0x59, 0x97, 0x95, 0x25, 0x16 } };
static const GUID IID_v2_IGameInputDevice = { 0x39a0c9f2, 0xf055, 0x4089, { 0x96, 0xe7, 0x25, 0xb2, 0x75, 0x6d, 0x30, 0x77 } };

static int guid_eq(const GUID *a, const GUID *b) { return memcmp(a, b, sizeof(GUID)) == 0; }

/* ---------- o log (C:\gameinput-hefesto.log, com teto de tamanho) ---------- */

#define LOG_TETO_BYTES (1024 * 1024)
static CRITICAL_SECTION g_lock;
static int g_lock_ready;

static void glog(const char *fmt, ...)
{
    char buf[640];
    va_list ap;
    DWORD wrote;
    HANDLE h;
    LARGE_INTEGER size;
    SYSTEMTIME t;
    int n, k;

    GetLocalTime(&t);
    k = snprintf(buf, sizeof buf, "%02u:%02u:%02u.%03u [%lu] ", t.wHour, t.wMinute, t.wSecond,
                 t.wMilliseconds, (unsigned long)GetCurrentThreadId());
    if (k < 0 || k >= (int)sizeof(buf) - 2) k = 0;
    va_start(ap, fmt);
    n = vsnprintf(buf + k, sizeof(buf) - 2 - (size_t)k, fmt, ap);
    va_end(ap);
    if (n < 0) return;
    n += k;
    if (n > (int)sizeof(buf) - 2) n = (int)sizeof(buf) - 2;
    buf[n++] = '\n';
    h = CreateFileA("C:\\gameinput-hefesto.log", FILE_APPEND_DATA,
                    FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL, OPEN_ALWAYS,
                    FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) return;
    if (GetFileSizeEx(h, &size) && size.QuadPart > (LONGLONG)LOG_TETO_BYTES) {
        CloseHandle(h);
        MoveFileExA("C:\\gameinput-hefesto.log", "C:\\gameinput-hefesto.log.1", MOVEFILE_REPLACE_EXISTING);
        h = CreateFileA("C:\\gameinput-hefesto.log", FILE_APPEND_DATA,
                        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL, OPEN_ALWAYS,
                        FILE_ATTRIBUTE_NORMAL, NULL);
        if (h == INVALID_HANDLE_VALUE) return;
    }
    WriteFile(h, buf, (DWORD)n, &wrote, NULL);
    CloseHandle(h);
}

static const char *g_vistos[96];
static int g_vistos_n;

/* Uma linha por nome: o método que a peça não implementa aparece no log uma vez só. */
static void log_uma_vez(const char *s)
{
    int i;
    if (g_lock_ready) EnterCriticalSection(&g_lock);
    for (i = 0; i < g_vistos_n; i++) {
        if (g_vistos[i] == s) {
            if (g_lock_ready) LeaveCriticalSection(&g_lock);
            return;
        }
    }
    if (g_vistos_n < (int)(sizeof g_vistos / sizeof g_vistos[0])) g_vistos[g_vistos_n++] = s;
    if (g_lock_ready) LeaveCriticalSection(&g_lock);
    glog("FIXME %s: não implementado", s);
}

/* ---------- SHA-256 (o deviceId) e CRC32 (o report do rádio) ---------- */

static const uint32_t K256[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
};

#define ROTR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))

static void sha256_bloco(uint32_t h[8], const BYTE *b)
{
    uint32_t w[64], a, bb, c, d, e, f, g, hh, t1, t2;
    int i;
    for (i = 0; i < 16; i++)
        w[i] = (uint32_t)b[i * 4] << 24 | (uint32_t)b[i * 4 + 1] << 16 | (uint32_t)b[i * 4 + 2] << 8 | b[i * 4 + 3];
    for (i = 16; i < 64; i++) {
        uint32_t s0 = ROTR(w[i - 15], 7) ^ ROTR(w[i - 15], 18) ^ (w[i - 15] >> 3);
        uint32_t s1 = ROTR(w[i - 2], 17) ^ ROTR(w[i - 2], 19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16] + s0 + w[i - 7] + s1;
    }
    a = h[0]; bb = h[1]; c = h[2]; d = h[3]; e = h[4]; f = h[5]; g = h[6]; hh = h[7];
    for (i = 0; i < 64; i++) {
        t1 = hh + (ROTR(e, 6) ^ ROTR(e, 11) ^ ROTR(e, 25)) + ((e & f) ^ (~e & g)) + K256[i] + w[i];
        t2 = (ROTR(a, 2) ^ ROTR(a, 13) ^ ROTR(a, 22)) + ((a & bb) ^ (a & c) ^ (bb & c));
        hh = g; g = f; f = e; e = d + t1; d = c; c = bb; bb = a; a = t1 + t2;
    }
    h[0] += a; h[1] += bb; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
}

static void sha256(const BYTE *dados, size_t n, BYTE out[32])
{
    uint32_t h[8] = { 0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                      0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19 };
    BYTE bloco[64];
    size_t i, resto = n;
    uint64_t bits = (uint64_t)n * 8;
    while (resto >= 64) {
        sha256_bloco(h, dados);
        dados += 64;
        resto -= 64;
    }
    memset(bloco, 0, sizeof bloco);
    memcpy(bloco, dados, resto);
    bloco[resto] = 0x80;
    if (resto >= 56) {
        sha256_bloco(h, bloco);
        memset(bloco, 0, sizeof bloco);
    }
    for (i = 0; i < 8; i++) bloco[63 - i] = (BYTE)(bits >> (8 * i));
    sha256_bloco(h, bloco);
    for (i = 0; i < 8; i++) {
        out[i * 4] = (BYTE)(h[i] >> 24);
        out[i * 4 + 1] = (BYTE)(h[i] >> 16);
        out[i * 4 + 2] = (BYTE)(h[i] >> 8);
        out[i * 4 + 3] = (BYTE)h[i];
    }
}

static uint32_t crc32_continua(uint32_t crc, const BYTE *p, size_t n)
{
    size_t i;
    int k;
    crc = ~crc;
    for (i = 0; i < n; i++) {
        crc ^= p[i];
        for (k = 0; k < 8; k++) crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
    }
    return ~crc;
}

/* ---------- os aparelhos ---------- */

#define MAX_APARELHOS 16
#define EIXOS 6
#define BOTOES 14

typedef struct { const void *const *lpVtbl; } iface;

typedef struct aparelho {
    iface i0, i1, i2;
    LONG refs;
    int usado;
    int dubla;                 /* o aparelho dublê da régua: um arquivo comum, sem HID */
    int bt;                    /* o report de saída é o 0x31 do rádio (78 B, com CRC32) */
    WCHAR caminho[512];
    char caminho_utf8[512];
    DWORD saida_len, entrada_len;
    HANDLE escrita;
    HANDLE leitor;
    volatile LONG perdido;     /* a leitura falhou: o aparelho saiu */
    uint32_t status;
    /* a última leitura */
    uint64_t seq, ts;
    gi_gamepad_state pad;
    float eixos[EIXOS];
    bool botoes[BOTOES];
    int32_t chave;
    /* o rumble */
    CRITICAL_SECTION wlock;
    BYTE fraco, forte;
    ULONGLONG ultima_escrita_ms;
    BYTE bt_seq;
    /* o que a ABI entrega */
    gi_info_v0 info0;
    gi_info_v1 info1;
    gi_info_v2 info2;
} aparelho;

static aparelho g_ap[MAX_APARELHOS];
static int g_ap_n;
static int g_modo_duble = -1;
static gi_gamepad_info g_gamepad_info;
static gi_string g_nome = { 29, 29, "DualSense Wireless Controller" };

#define AP_DE(p, campo) ((aparelho *)((char *)(p) - offsetof(aparelho, campo)))

static aparelho *ap_de_iface(void *p, int ver)
{
    if (!p) return NULL;
    if (ver == 0) return AP_DE(p, i0);
    if (ver == 1) return AP_DE(p, i1);
    return AP_DE(p, i2);
}

static void *iface_do_ap(aparelho *a, int ver)
{
    if (!a) return NULL;
    return ver == 0 ? (void *)&a->i0 : ver == 1 ? (void *)&a->i1 : (void *)&a->i2;
}

static uint64_t agora_us(void)
{
    static LARGE_INTEGER freq;
    LARGE_INTEGER c;
    if (!freq.QuadPart) QueryPerformanceFrequency(&freq);
    QueryPerformanceCounter(&c);
    return (uint64_t)(c.QuadPart / freq.QuadPart) * 1000000ull +
           (uint64_t)(c.QuadPart % freq.QuadPart) * 1000000ull / (uint64_t)freq.QuadPart;
}

static float eixo_de(BYTE v) { return ((float)v - 127.5f) / 127.5f; }

/* O hat do DualSense (0 = cima, horário, 8 = solto) na posição do GameInput (0 = centro, 1 = cima). */
static int32_t chave_de(BYTE hat) { return hat < 8 ? (int32_t)hat + 1 : 0; }

/* O report de entrada: 0x01 do cabo (o corpo começa no byte 1) ou 0x31 do rádio (no byte 2). */
static void ler_report(aparelho *a, const BYTE *r, DWORD n)
{
    const BYTE *c;
    gi_gamepad_state s;
    BYTE b0, b1, hat;
    uint32_t bt = 0;
    int i;
    if (n >= 11 && r[0] == 0x01) c = r + 1;
    else if (n >= 12 && r[0] == 0x31) c = r + 2;
    else return;
    b0 = c[7];
    b1 = c[8];
    hat = b0 & 0x0f;
    if (b0 & 0x20) bt |= 0x0004;            /* cruz -> A */
    if (b0 & 0x40) bt |= 0x0008;            /* bola -> B */
    if (b0 & 0x10) bt |= 0x0010;            /* quadrado -> X */
    if (b0 & 0x80) bt |= 0x0020;            /* triângulo -> Y */
    if (b1 & 0x20) bt |= 0x0001;            /* options -> menu */
    if (b1 & 0x10) bt |= 0x0002;            /* create -> view */
    if (b1 & 0x01) bt |= 0x0400;            /* L1 */
    if (b1 & 0x02) bt |= 0x0800;            /* R1 */
    if (b1 & 0x40) bt |= 0x1000;            /* L3 */
    if (b1 & 0x80) bt |= 0x2000;            /* R3 */
    if (hat == 0 || hat == 1 || hat == 7) bt |= 0x0040;
    if (hat >= 3 && hat <= 5) bt |= 0x0080;
    if (hat >= 5 && hat <= 7) bt |= 0x0100;
    if (hat >= 1 && hat <= 3) bt |= 0x0200;
    s.buttons = bt;
    s.leftThumbstickX = eixo_de(c[0]);
    s.leftThumbstickY = -eixo_de(c[1]);
    s.rightThumbstickX = eixo_de(c[2]);
    s.rightThumbstickY = -eixo_de(c[3]);
    s.leftTrigger = (float)c[4] / 255.0f;
    s.rightTrigger = (float)c[5] / 255.0f;
    EnterCriticalSection(&g_lock);
    a->pad = s;
    for (i = 0; i < EIXOS; i++) a->eixos[i] = (float)c[i] / 255.0f;
    for (i = 0; i < 4; i++) a->botoes[i] = (b0 >> (4 + i)) & 1;
    for (i = 0; i < 8; i++) a->botoes[4 + i] = (b1 >> i) & 1;
    a->botoes[12] = c[9] & 0x01;
    a->botoes[13] = (c[9] >> 1) & 0x01;
    a->chave = chave_de(hat);
    a->seq++;
    a->ts = agora_us();
    LeaveCriticalSection(&g_lock);
}

static DWORD WINAPI leitor_thread(void *arg)
{
    aparelho *a = arg;
    BYTE buf[128];
    DWORD n;
    WCHAR entrada[540];
    HANDLE h;
    if (a->dubla) {
        _snwprintf(entrada, sizeof entrada / sizeof entrada[0] - 1, L"%ls.entrada", a->caminho);
        entrada[sizeof entrada / sizeof entrada[0] - 1] = 0;
        h = CreateFileW(entrada, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL,
                        OPEN_EXISTING, 0, NULL);
    } else {
        h = CreateFileW(a->caminho, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL,
                        OPEN_EXISTING, 0, NULL);
    }
    if (h == INVALID_HANDLE_VALUE) {
        if (!a->dubla) InterlockedExchange(&a->perdido, 1);
        return 0;
    }
    for (;;) {
        DWORD quer = a->entrada_len && a->entrada_len <= sizeof buf ? a->entrada_len : sizeof buf;
        if (!ReadFile(h, buf, quer, &n, NULL) || n == 0) break;
        ler_report(a, buf, n);
        if (a->dubla) break;  /* o dublê traz um report só */
    }
    CloseHandle(h);
    if (!a->dubla) InterlockedExchange(&a->perdido, 1);
    return 0;
}

static void escrever_rumble(aparelho *a, BYTE fraco, BYTE forte)
{
    BYTE r[78];
    DWORD len, w = 0;
    uint32_t crc;
    BYTE semente = 0xA2;
    memset(r, 0, sizeof r);
    if (a->bt) {
        r[0] = 0x31;
        r[1] = (BYTE)((a->bt_seq++ & 0x0f) << 4);
        r[2] = 0x10;
        r[3] = FLAG0_VIBRACAO;
        r[4] = 0x00;
        r[5] = fraco;
        r[6] = forte;
        crc = crc32_continua(crc32_continua(0, &semente, 1), r, 74);
        r[74] = (BYTE)crc;
        r[75] = (BYTE)(crc >> 8);
        r[76] = (BYTE)(crc >> 16);
        r[77] = (BYTE)(crc >> 24);
        len = 78;
    } else {
        r[0] = 0x02;
        r[1] = FLAG0_VIBRACAO;
        r[2] = 0x00;
        r[3] = fraco;
        r[4] = forte;
        len = a->saida_len >= 5 && a->saida_len <= sizeof r ? a->saida_len : 48;
    }
    if (a->escrita != INVALID_HANDLE_VALUE &&
        !WriteFile(a->escrita, r, len, &w, NULL) && !a->dubla)
        HidD_SetOutputReport(a->escrita, r, len);
    a->ultima_escrita_ms = GetTickCount64();
}

static BYTE para_byte(float x)
{
    if (!(x > 0.0f)) return 0;
    if (x >= 1.0f) return 255;
    return (BYTE)(x * 255.0f + 0.5f);
}

static int g_rumbles_no_log;

static void rumble_de(aparelho *a, const gi_rumble *p)
{
    BYTE forte, fraco;
    if (!a) return;
    /* lowFrequency é o motor forte (o da esquerda); highFrequency, o fraco. */
    forte = p ? para_byte(p->lowFrequency) : 0;
    fraco = p ? para_byte(p->highFrequency) : 0;
    EnterCriticalSection(&a->wlock);
    if (fraco != a->fraco || forte != a->forte) {
        a->fraco = fraco;
        a->forte = forte;
        escrever_rumble(a, fraco, forte);
        if (g_rumbles_no_log < 64) {
            g_rumbles_no_log++;
            glog("SetRumbleState %s fraco=%u forte=%u", a->caminho_utf8, fraco, forte);
        }
    }
    LeaveCriticalSection(&a->wlock);
}

static void preencher_info(aparelho *a, uint16_t vid, uint16_t pid, uint16_t rev)
{
    BYTE id[32];
    WCHAR baixo[512];
    size_t i;
    for (i = 0; a->caminho[i] && i < 511; i++) baixo[i] = towlower(a->caminho[i]);
    baixo[i] = 0;
    sha256((const BYTE *)baixo, i * sizeof(WCHAR), id);
    WideCharToMultiByte(CP_UTF8, 0, a->caminho, -1, a->caminho_utf8, sizeof a->caminho_utf8, NULL, NULL);

    memset(&a->info0, 0, sizeof a->info0);
    a->info0.infoSize = sizeof a->info0;
    a->info0.vendorId = vid;
    a->info0.productId = pid;
    a->info0.revisionNumber = rev;
    a->info0.usage.page = 0x01;
    a->info0.usage.id = 0x05;
    memcpy(a->info0.deviceId.value, id, 32);
    memcpy(a->info0.deviceRootId.value, id, 32);
    a->info0.deviceFamily = 3; /* HID */
    a->info0.supportedInput = KINDS_DO_PAD;
    a->info0.supportedRumbleMotors = MOTORES_DE_RUMBLE;
    a->info0.gamepadInfo = &g_gamepad_info;
    a->info0.displayName = &g_nome;

    memset(&a->info1, 0, sizeof a->info1);
    a->info1.vendorId = vid;
    a->info1.productId = pid;
    a->info1.usage = a->info0.usage;
    a->info1.deviceId = a->info0.deviceId;
    a->info1.deviceRootId = a->info0.deviceRootId;
    a->info1.deviceFamily = 3;
    a->info1.supportedInput = KINDS_DO_PAD;
    a->info1.supportedRumbleMotors = MOTORES_DE_RUMBLE;
    a->info1.displayName = g_nome.data;
    a->info1.pnpPath = a->caminho_utf8;
    a->info1.gamepadInfo = &g_gamepad_info;

    memset(&a->info2, 0, sizeof a->info2);
    a->info2.vendorId = vid;
    a->info2.productId = pid;
    a->info2.revisionNumber = rev;
    a->info2.usage = a->info0.usage;
    a->info2.deviceId = a->info0.deviceId;
    a->info2.deviceRootId = a->info0.deviceRootId;
    a->info2.deviceFamily = 3;
    a->info2.supportedInput = KINDS_DO_PAD;
    a->info2.supportedRumbleMotors = MOTORES_DE_RUMBLE;
    a->info2.displayName = g_nome.data;
    a->info2.pnpPath = a->caminho_utf8;
    a->info2.gamepadInfo = &g_gamepad_info;
}

extern const void *const g_vt_dev0[], *const g_vt_dev1[], *const g_vt_dev2[];

static aparelho *ap_por_caminho(const WCHAR *caminho)
{
    int i;
    for (i = 0; i < g_ap_n; i++)
        if (!_wcsicmp(g_ap[i].caminho, caminho)) return &g_ap[i];
    return NULL;
}

/* Abre (ou reabre) o aparelho e põe a leitura para andar. Chamado com g_lock; a troca do handle
 * vai sob o wlock, porque o SetRumbleState do jogo escreve nele de outra thread. */
static int abrir(aparelho *a)
{
    HANDLE t;
    EnterCriticalSection(&a->wlock);
    if (a->escrita != INVALID_HANDLE_VALUE) CloseHandle(a->escrita);
    a->escrita = CreateFileW(a->caminho, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
                             NULL, OPEN_EXISTING, 0, NULL);
    LeaveCriticalSection(&a->wlock);
    if (a->escrita == INVALID_HANDLE_VALUE) return 0;
    InterlockedExchange(&a->perdido, 0);
    t = CreateThread(NULL, 0, leitor_thread, a, 0, NULL);
    if (t) CloseHandle(t);
    return 1;
}

static aparelho *novo_aparelho(const WCHAR *caminho, int dubla, int bt, DWORD saida, DWORD entrada,
                               uint16_t vid, uint16_t pid, uint16_t rev)
{
    aparelho *a;
    if (g_ap_n >= MAX_APARELHOS) return NULL;
    a = &g_ap[g_ap_n];
    memset(a, 0, sizeof *a);
    a->i0.lpVtbl = g_vt_dev0;
    a->i1.lpVtbl = g_vt_dev1;
    a->i2.lpVtbl = g_vt_dev2;
    a->refs = 1;
    a->dubla = dubla;
    a->bt = bt;
    a->saida_len = saida;
    a->entrada_len = entrada;
    a->escrita = INVALID_HANDLE_VALUE;
    lstrcpynW(a->caminho, caminho, 512);
    InitializeCriticalSection(&a->wlock);
    preencher_info(a, vid, pid, rev);
    if (!abrir(a)) {
        DeleteCriticalSection(&a->wlock);
        return NULL;
    }
    a->usado = 1;
    g_ap_n++;
    glog("aparelho %s %s saída=%lu", a->caminho_utf8, bt ? "rádio" : "cabo", (unsigned long)saida);
    return a;
}

static int tem_ig(const WCHAR *caminho)
{
    const WCHAR *p;
    for (p = caminho; *p; p++)
        if (p[0] == L'&' && (p[1] == L'I' || p[1] == L'i') && (p[2] == L'G' || p[2] == L'g') && p[3] == L'_')
            return 1;
    return 0;
}

/* O PID do DualSense e do DualSense Edge (o pad virtual do Hefesto veste um dos dois). */
static int e_dualsense(USHORT vid, USHORT pid) { return vid == 0x054c && (pid == 0x0ce6 || pid == 0x0df2); }

typedef struct { aparelho *a; uint32_t antes, depois; } mudanca;

/* A lista do aparelho dublê vem de uma variável só de teste: caminhos separados por `;`, cada
 * um um arquivo comum que recebe os reports de saída; `.bt` no fim é o rádio. */
static int listar_duble(mudanca *m, int max)
{
    WCHAR lista[2048], *p, *fim;
    int n = 0;
    DWORD k = GetEnvironmentVariableW(L"HEFESTO_GAMEINPUT_DUBLE_DE_TESTE", lista, 2048);
    if (!k || k >= 2048) return 0;
    for (p = lista; p && *p; p = fim) {
        size_t len;
        int bt;
        fim = wcschr(p, L';');
        if (fim) *fim++ = 0;
        if (!*p || ap_por_caminho(p)) continue;
        len = wcslen(p);
        bt = len > 3 && !_wcsicmp(p + len - 3, L".bt");
        EnterCriticalSection(&g_lock);
        {
            aparelho *a = novo_aparelho(p, 1, bt, bt ? 78 : 48, bt ? 78 : 64, 0x054c, 0x0df2, 0x0100);
            if (a) {
                a->status = STATUS_CONNECTED;
                if (n < max) { m[n].a = a; m[n].antes = 0; m[n].depois = STATUS_CONNECTED; n++; }
            }
        }
        LeaveCriticalSection(&g_lock);
    }
    return n;
}

static int listar_hid(mudanca *m, int max)
{
    GUID hid;
    HDEVINFO set;
    SP_DEVICE_INTERFACE_DATA ifd;
    BYTE buf[sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W) + 1024 * sizeof(WCHAR)];
    SP_DEVICE_INTERFACE_DETAIL_DATA_W *det = (SP_DEVICE_INTERFACE_DETAIL_DATA_W *)buf;
    int visto[MAX_APARELHOS] = { 0 };
    DWORD i;
    int j, n = 0;

    HidD_GetHidGuid(&hid);
    set = SetupDiGetClassDevsW(&hid, NULL, NULL, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);
    if (set == INVALID_HANDLE_VALUE) return 0;
    ifd.cbSize = sizeof ifd;
    for (i = 0; SetupDiEnumDeviceInterfaces(set, NULL, &hid, i, &ifd); i++) {
        HIDD_ATTRIBUTES attr;
        PHIDP_PREPARSED_DATA pre;
        HIDP_CAPS caps;
        HANDLE f;
        aparelho *a;
        int bt;
        det->cbSize = sizeof(*det);
        if (!SetupDiGetDeviceInterfaceDetailW(set, &ifd, det, sizeof buf, NULL, NULL)) continue;
        if (tem_ig(det->DevicePath)) continue;  /* a máscara Xbox: o jogo já a pega pela XInput */
        a = ap_por_caminho(det->DevicePath);
        if (a) {
            visto[a - g_ap] = 1;
            if (a->status == STATUS_CONNECTED && !a->perdido) continue;
            EnterCriticalSection(&g_lock);
            if (abrir(a)) {
                if (a->status != STATUS_CONNECTED && n < max) {
                    m[n].a = a; m[n].antes = a->status; m[n].depois = STATUS_CONNECTED; n++;
                }
                a->status = STATUS_CONNECTED;
            }
            LeaveCriticalSection(&g_lock);
            continue;
        }
        f = CreateFileW(det->DevicePath, 0, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
        if (f == INVALID_HANDLE_VALUE) continue;
        attr.Size = sizeof attr;
        if (!HidD_GetAttributes(f, &attr) || !e_dualsense(attr.VendorID, attr.ProductID) ||
            !HidD_GetPreparsedData(f, &pre)) {
            CloseHandle(f);
            continue;
        }
        HidP_GetCaps(pre, &caps);
        HidD_FreePreparsedData(pre);
        CloseHandle(f);
        if (caps.UsagePage != 0x01 || caps.Usage != 0x05) continue;
        if (caps.OutputReportByteLength == 48) bt = 0;
        else if (caps.OutputReportByteLength == 78) bt = 1;
        else continue;
        EnterCriticalSection(&g_lock);
        a = novo_aparelho(det->DevicePath, 0, bt, caps.OutputReportByteLength, caps.InputReportByteLength,
                          attr.VendorID, attr.ProductID, attr.VersionNumber);
        if (a) {
            visto[a - g_ap] = 1;
            a->status = STATUS_CONNECTED;
            if (n < max) { m[n].a = a; m[n].antes = 0; m[n].depois = STATUS_CONNECTED; n++; }
        }
        LeaveCriticalSection(&g_lock);
    }
    SetupDiDestroyDeviceInfoList(set);
    EnterCriticalSection(&g_lock);
    for (j = 0; j < g_ap_n; j++) {
        if (!visto[j] && g_ap[j].status == STATUS_CONNECTED) {
            g_ap[j].status = 0;
            if (n < max) { m[n].a = &g_ap[j]; m[n].antes = STATUS_CONNECTED; m[n].depois = 0; n++; }
        }
    }
    LeaveCriticalSection(&g_lock);
    return n;
}

static int listar(mudanca *m, int max)
{
    if (g_modo_duble < 0) g_modo_duble = GetEnvironmentVariableW(L"HEFESTO_GAMEINPUT_DUBLE_DE_TESTE", NULL, 0) > 0;
    return g_modo_duble ? listar_duble(m, max) : listar_hid(m, max);
}

/* ---------- os retornos de chamada dos aparelhos ---------- */

typedef void (WINAPI *cb_aparelho_t)(gi_token, void *, void *, uint64_t, uint32_t, uint32_t);

typedef struct {
    gi_token token;
    int usado, parado, ver;
    aparelho *so;
    uint32_t kind, filtro;
    void *ctx;
    cb_aparelho_t fn;
} registro;

#define MAX_REGISTROS 64
static registro g_reg[MAX_REGISTROS];
static gi_token g_proximo_token = 1;

static int casa(const registro *r, aparelho *a, uint32_t antes, uint32_t depois)
{
    if (!r->usado || r->parado) return 0;
    if (r->so && r->so != a) return 0;
    if (!(r->kind & a->info0.supportedInput)) return 0;
    return ((antes ^ depois) & r->filtro) != 0;
}

static void avisar(const mudanca *m, int n)
{
    registro copia[MAX_REGISTROS];
    int i, j, k;
    if (!n) return;
    EnterCriticalSection(&g_lock);
    memcpy(copia, g_reg, sizeof copia);
    LeaveCriticalSection(&g_lock);
    for (i = 0; i < n; i++) {
        uint64_t ts = agora_us();
        for (j = 0; j < MAX_REGISTROS; j++) {
            if (!casa(&copia[j], m[i].a, m[i].antes, m[i].depois)) continue;
            /* o registro pode ter saído desde a cópia */
            for (k = 0; k < MAX_REGISTROS; k++)
                if (g_reg[k].usado && !g_reg[k].parado && g_reg[k].token == copia[j].token) break;
            if (k == MAX_REGISTROS) continue;
            copia[j].fn(copia[j].token, copia[j].ctx, iface_do_ap(m[i].a, copia[j].ver), ts,
                        m[i].depois, m[i].antes);
        }
    }
}

static DWORD WINAPI vigia_thread(void *arg)
{
    mudanca m[MAX_APARELHOS * 2];
    unsigned tique = 0;
    int i, n;
    (void)arg;
    for (;;) {
        Sleep(500);
        /* o reenvio do rumble que não é zero */
        for (i = 0; i < g_ap_n; i++) {
            aparelho *a = &g_ap[i];
            if (a->status != STATUS_CONNECTED) continue;
            EnterCriticalSection(&a->wlock);
            if ((a->fraco || a->forte) && GetTickCount64() - a->ultima_escrita_ms >= REENVIO_MS)
                escrever_rumble(a, a->fraco, a->forte);
            LeaveCriticalSection(&a->wlock);
        }
        if (++tique % 2) continue;
        n = listar(m, (int)(sizeof m / sizeof m[0]));
        avisar(m, n);
    }
    return 0;
}

static int g_iniciado;

/* Lista os aparelhos na primeira chamada que acha um DualSense, e só então põe o vigia para andar.
 * Devolve quantos há. */
static int iniciar(void)
{
    mudanca m[MAX_APARELHOS * 2];
    HANDLE t;
    int n;
    EnterCriticalSection(&g_lock);
    if (!g_iniciado) {
        memset(&g_gamepad_info, 0xff, sizeof g_gamepad_info); /* GameInputLabelUnknown */
        listar(m, (int)(sizeof m / sizeof m[0]));
        if (g_ap_n) {
            g_iniciado = 1;
            glog("iniciado: %d aparelho(s)%s", g_ap_n, g_modo_duble ? " (dublê de teste)" : "");
            t = CreateThread(NULL, 0, vigia_thread, NULL, 0, NULL);
            if (t) CloseHandle(t);
        }
    }
    n = g_ap_n;
    LeaveCriticalSection(&g_lock);
    return n;
}

/* Sem DualSense na partida, a peça responde como o GameInput do Proton (E_NOTIMPL): o jogo que lê
 * a entrada pelo GameInput cai na XInput, como sempre caiu, e o controle Xbox (a máscara do
 * Hefesto ou um de verdade, que a peça não lista) segue no jogo. */
static int sem_dualsense(void)
{
    if (iniciar()) return 0;
    glog("sem DualSense: E_NOTIMPL, como o GameInput do Proton");
    return 1;
}

/* ---------- IGameInputReading ---------- */

typedef struct leitura {
    iface i0, i1, i2;
    LONG refs;
    aparelho *ap;
    uint64_t seq, ts;
    gi_gamepad_state pad;
    float eixos[EIXOS];
    bool botoes[BOTOES];
    int32_t chave;
} leitura;

extern const void *const g_vt_lei0[], *const g_vt_lei1[], *const g_vt_lei2[];

static leitura *lei_de(void *p, int ver)
{
    return (leitura *)((char *)p - (ver == 0 ? offsetof(leitura, i0) : ver == 1 ? offsetof(leitura, i1) : offsetof(leitura, i2)));
}

static void *iface_da_lei(leitura *l, int ver)
{
    return ver == 0 ? (void *)&l->i0 : ver == 1 ? (void *)&l->i1 : (void *)&l->i2;
}

static leitura *nova_leitura(aparelho *a)
{
    leitura *l = HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, sizeof *l);
    if (!l) return NULL;
    l->i0.lpVtbl = g_vt_lei0;
    l->i1.lpVtbl = g_vt_lei1;
    l->i2.lpVtbl = g_vt_lei2;
    l->refs = 1;
    l->ap = a;
    EnterCriticalSection(&g_lock);
    l->seq = a->seq;
    l->ts = a->ts;
    l->pad = a->pad;
    memcpy(l->eixos, a->eixos, sizeof l->eixos);
    memcpy(l->botoes, a->botoes, sizeof l->botoes);
    l->chave = a->chave;
    LeaveCriticalSection(&g_lock);
    return l;
}

#define LEI_IUNKNOWN(V)                                                                         \
    static HRESULT WINAPI lei##V##_QueryInterface(void *t, const GUID *riid, void **out)       \
    {                                                                                           \
        leitura *l = lei_de(t, V);                                                              \
        if (!out) return E_POINTER;                                                             \
        *out = NULL;                                                                            \
        if (guid_eq(riid, &IID_IUnknown_)) *out = iface_da_lei(l, V);                           \
        else if (guid_eq(riid, &IID_v0_IGameInputReading)) *out = &l->i0;                       \
        else if (guid_eq(riid, &IID_v1_IGameInputReading)) *out = &l->i1;                       \
        else if (guid_eq(riid, &IID_v2_IGameInputReading)) *out = &l->i2;                       \
        else return E_NOINTERFACE;                                                              \
        InterlockedIncrement(&l->refs);                                                         \
        return S_OK;                                                                            \
    }                                                                                           \
    static ULONG WINAPI lei##V##_AddRef(void *t) { return (ULONG)InterlockedIncrement(&lei_de(t, V)->refs); } \
    static ULONG WINAPI lei##V##_Release(void *t)                                               \
    {                                                                                           \
        leitura *l = lei_de(t, V);                                                              \
        LONG r = InterlockedDecrement(&l->refs);                                                \
        if (!r) HeapFree(GetProcessHeap(), 0, l);                                               \
        return (ULONG)r;                                                                        \
    }                                                                                           \
    static uint32_t WINAPI lei##V##_GetInputKind(void *t) { (void)t; return KINDS_DO_PAD; }    \
    static uint64_t WINAPI lei##V##_GetTimestamp(void *t) { return lei_de(t, V)->ts; }          \
    static void WINAPI lei##V##_GetDevice(void *t, void **out)                                  \
    {                                                                                           \
        leitura *l = lei_de(t, V);                                                              \
        if (!out) return;                                                                       \
        InterlockedIncrement(&l->ap->refs);                                                     \
        *out = iface_do_ap(l->ap, V);                                                           \
    }                                                                                           \
    static uint32_t WINAPI lei##V##_GetControllerAxisState(void *t, uint32_t n, float *s)       \
    {                                                                                           \
        leitura *l = lei_de(t, V);                                                              \
        uint32_t i;                                                                             \
        if (!s) return 0;                                                                       \
        for (i = 0; i < n && i < EIXOS; i++) s[i] = l->eixos[i];                                \
        return i;                                                                               \
    }                                                                                           \
    static uint32_t WINAPI lei##V##_GetControllerButtonState(void *t, uint32_t n, bool *s)      \
    {                                                                                           \
        leitura *l = lei_de(t, V);                                                              \
        uint32_t i;                                                                             \
        if (!s) return 0;                                                                       \
        for (i = 0; i < n && i < BOTOES; i++) s[i] = l->botoes[i];                              \
        return i;                                                                               \
    }                                                                                           \
    static uint32_t WINAPI lei##V##_GetControllerSwitchState(void *t, uint32_t n, int32_t *s)   \
    {                                                                                           \
        if (!s || !n) return 0;                                                                 \
        s[0] = lei_de(t, V)->chave;                                                             \
        return 1;                                                                               \
    }

LEI_IUNKNOWN(0)
LEI_IUNKNOWN(1)
LEI_IUNKNOWN(2)

static uint64_t WINAPI lei0_GetSequenceNumber(void *t, uint32_t kind) { (void)kind; return lei_de(t, 0)->seq; }
static bool WINAPI lei0_GetRawReport(void *t, void **out) { (void)t; if (out) *out = NULL; return false; }
static uint32_t WINAPI lei_eixos(void *t) { (void)t; return EIXOS; }
static uint32_t WINAPI lei_botoes(void *t) { (void)t; return BOTOES; }
static uint32_t WINAPI lei_chaves(void *t) { (void)t; return 1; }
static uint32_t WINAPI zero32(void *t) { (void)t; return 0; }
static bool WINAPI falso(void *t) { (void)t; return false; }
static void WINAPI nada(void *t) { (void)t; }

static bool gamepad_de(leitura *l, gi_gamepad_state *state)
{
    if (!state) return false;
    *state = l->pad;
    return true;
}

static bool WINAPI lei0_GetGamepadState(void *t, gi_gamepad_state *s) { return gamepad_de(lei_de(t, 0), s); }
static bool WINAPI lei1_GetGamepadState(void *t, gi_gamepad_state *s) { return gamepad_de(lei_de(t, 1), s); }
static bool WINAPI lei2_GetGamepadState(void *t, gi_gamepad_state *s) { return gamepad_de(lei_de(t, 2), s); }

#define F(x) ((const void *)(x))

const void *const g_vt_lei0[] = {
    F(lei0_QueryInterface), F(lei0_AddRef), F(lei0_Release),
    F(lei0_GetInputKind), F(lei0_GetSequenceNumber), F(lei0_GetTimestamp), F(lei0_GetDevice),
    F(lei0_GetRawReport), F(lei_eixos), F(lei0_GetControllerAxisState), F(lei_botoes),
    F(lei0_GetControllerButtonState), F(lei_chaves), F(lei0_GetControllerSwitchState),
    F(zero32) /* GetKeyCount */, F(zero32) /* GetKeyState */, F(falso) /* GetMouseState */,
    F(zero32) /* GetTouchCount */, F(zero32) /* GetTouchState */, F(falso) /* GetMotionState */,
    F(falso) /* GetArcadeStickState */, F(falso) /* GetFlightStickState */, F(lei0_GetGamepadState),
    F(falso) /* GetRacingWheelState */, F(falso) /* GetUiNavigationState */,
};

const void *const g_vt_lei1[] = {
    F(lei1_QueryInterface), F(lei1_AddRef), F(lei1_Release),
    F(lei1_GetInputKind), F(lei1_GetTimestamp), F(lei1_GetDevice),
    F(lei_eixos), F(lei1_GetControllerAxisState), F(lei_botoes), F(lei1_GetControllerButtonState),
    F(lei_chaves), F(lei1_GetControllerSwitchState),
    F(zero32) /* GetKeyCount */, F(zero32) /* GetKeyState */, F(falso) /* GetMouseState */,
    F(falso) /* GetArcadeStickState */, F(falso) /* GetFlightStickState */, F(lei1_GetGamepadState),
    F(falso) /* GetRacingWheelState */, F(falso) /* GetUiNavigationState */,
};

const void *const g_vt_lei2[] = {
    F(lei2_QueryInterface), F(lei2_AddRef), F(lei2_Release),
    F(lei2_GetInputKind), F(lei2_GetTimestamp), F(lei2_GetDevice),
    F(lei_eixos), F(lei2_GetControllerAxisState), F(lei_botoes), F(lei2_GetControllerButtonState),
    F(lei_chaves), F(lei2_GetControllerSwitchState),
    F(zero32) /* GetKeyCount */, F(zero32) /* GetKeyState */, F(falso) /* GetMouseState */,
    F(falso) /* GetSensorsState */, F(falso) /* GetArcadeStickState */, F(falso) /* GetFlightStickState */,
    F(lei2_GetGamepadState), F(falso) /* GetRacingWheelState */, F(falso) /* GetUiNavigationState */,
};

/* ---------- IGameInputDevice ---------- */

#define DEV_IUNKNOWN(V)                                                                         \
    static HRESULT WINAPI dev##V##_QueryInterface(void *t, const GUID *riid, void **out)       \
    {                                                                                           \
        aparelho *a = ap_de_iface(t, V);                                                        \
        if (!out) return E_POINTER;                                                             \
        *out = NULL;                                                                            \
        if (guid_eq(riid, &IID_IUnknown_)) *out = iface_do_ap(a, V);                            \
        else if (guid_eq(riid, &IID_v0_IGameInputDevice)) *out = &a->i0;                        \
        else if (guid_eq(riid, &IID_v1_IGameInputDevice)) *out = &a->i1;                        \
        else if (guid_eq(riid, &IID_v2_IGameInputDevice)) *out = &a->i2;                        \
        else return E_NOINTERFACE;                                                              \
        InterlockedIncrement(&a->refs);                                                         \
        return S_OK;                                                                            \
    }                                                                                           \
    /* o aparelho vive enquanto o processo vive: a contagem anda, mas nunca libera */          \
    static ULONG WINAPI dev##V##_AddRef(void *t) { return (ULONG)InterlockedIncrement(&ap_de_iface(t, V)->refs); } \
    static ULONG WINAPI dev##V##_Release(void *t)                                               \
    {                                                                                           \
        aparelho *a = ap_de_iface(t, V);                                                        \
        LONG r = InterlockedDecrement(&a->refs);                                                \
        if (r < 1) r = InterlockedExchange(&a->refs, 1), r = 1;                                 \
        return (ULONG)r;                                                                        \
    }                                                                                           \
    static uint32_t WINAPI dev##V##_GetDeviceStatus(void *t) { return ap_de_iface(t, V)->status; } \
    static void WINAPI dev##V##_SetRumbleState(void *t, const gi_rumble *p) { rumble_de(ap_de_iface(t, V), p); }

DEV_IUNKNOWN(0)
DEV_IUNKNOWN(1)
DEV_IUNKNOWN(2)

static const gi_info_v0 *WINAPI dev0_GetDeviceInfo(void *t) { return &ap_de_iface(t, 0)->info0; }

static HRESULT WINAPI dev1_GetDeviceInfo(void *t, const gi_info_v1 **out)
{
    if (!out) return E_POINTER;
    *out = &ap_de_iface(t, 1)->info1;
    return S_OK;
}

static HRESULT WINAPI dev2_GetDeviceInfo(void *t, const gi_info_v2 **out)
{
    if (!out) return E_POINTER;
    *out = &ap_de_iface(t, 2)->info2;
    return S_OK;
}

/* Sem háptica por áudio: o sink de háptica do Wwise não sobe, e o rumble segue pelos motores. */
static HRESULT WINAPI dev2_GetHapticInfo(void *t, void *info)
{
    (void)t; (void)info;
    return GAMEINPUT_E_HAPTIC_INFO_NOT_FOUND;
}

static void WINAPI dev0_GetBatteryState(void *t, gi_battery *s)
{
    (void)t;
    if (!s) return;
    memset(s, 0, sizeof *s);
    s->status = -1; /* GameInputBatteryUnknown */
}

static HRESULT WINAPI dev_CreateForceFeedbackEffect(void *t, uint32_t motor, const void *p, void **out)
{
    (void)t; (void)motor; (void)p;
    if (out) *out = NULL;
    log_uma_vez("IGameInputDevice::CreateForceFeedbackEffect");
    return E_NOTIMPL;
}

#define NAO_IMPL(nome, texto)                                                                   \
    static HRESULT WINAPI nome(void *t)                                                         \
    {                                                                                           \
        (void)t;                                                                                \
        log_uma_vez(texto);                                                                     \
        return E_NOTIMPL;                                                                       \
    }

NAO_IMPL(dev_SetHapticMotorState, "IGameInputDevice::SetHapticMotorState")
NAO_IMPL(dev_CreateRawDeviceReport, "IGameInputDevice::CreateRawDeviceReport")
NAO_IMPL(dev_GetRawDeviceFeature, "IGameInputDevice::GetRawDeviceFeature")
NAO_IMPL(dev_SetRawDeviceFeature, "IGameInputDevice::SetRawDeviceFeature")
NAO_IMPL(dev_SendRawDeviceOutput, "IGameInputDevice::SendRawDeviceOutput")
NAO_IMPL(dev_SendRawDeviceOutputWithResponse, "IGameInputDevice::SendRawDeviceOutputWithResponse")
NAO_IMPL(dev_ExecuteRawDeviceIoControl, "IGameInputDevice::ExecuteRawDeviceIoControl")
NAO_IMPL(dev_DirectInputEscape, "IGameInputDevice::DirectInputEscape")

const void *const g_vt_dev0[] = {
    F(dev0_QueryInterface), F(dev0_AddRef), F(dev0_Release),
    F(dev0_GetDeviceInfo), F(dev0_GetDeviceStatus), F(dev0_GetBatteryState),
    F(dev_CreateForceFeedbackEffect), F(falso) /* IsForceFeedbackMotorPoweredOn */,
    F(nada) /* SetForceFeedbackMotorGain */, F(dev_SetHapticMotorState), F(dev0_SetRumbleState),
    F(nada) /* SetInputSynchronizationState */, F(nada) /* SendInputSynchronizationHint */,
    F(nada) /* PowerOff */, F(dev_CreateRawDeviceReport), F(dev_GetRawDeviceFeature),
    F(dev_SetRawDeviceFeature), F(dev_SendRawDeviceOutput), F(dev_SendRawDeviceOutputWithResponse),
    F(dev_ExecuteRawDeviceIoControl), F(falso) /* AcquireExclusiveRawDeviceAccess */,
    F(nada) /* ReleaseExclusiveRawDeviceAccess */,
};

const void *const g_vt_dev1[] = {
    F(dev1_QueryInterface), F(dev1_AddRef), F(dev1_Release),
    F(dev1_GetDeviceInfo), F(dev1_GetDeviceStatus), F(dev_CreateForceFeedbackEffect),
    F(falso) /* IsForceFeedbackMotorPoweredOn */, F(nada) /* SetForceFeedbackMotorGain */,
    F(dev1_SetRumbleState),
};

const void *const g_vt_dev2[] = {
    F(dev2_QueryInterface), F(dev2_AddRef), F(dev2_Release),
    F(dev2_GetDeviceInfo), F(dev2_GetHapticInfo), F(dev2_GetDeviceStatus),
    F(dev_CreateForceFeedbackEffect), F(falso) /* IsForceFeedbackMotorPoweredOn */,
    F(nada) /* SetForceFeedbackMotorGain */, F(dev2_SetRumbleState), F(dev_DirectInputEscape),
};

/* ---------- IGameInput ---------- */

typedef struct { iface i0, i1, i2; } gameinput;
extern const void *const g_vt_gi0[], *const g_vt_gi1[], *const g_vt_gi2[];
static gameinput g_gi = { { g_vt_gi0 }, { g_vt_gi1 }, { g_vt_gi2 } };

static HRESULT WINAPI gi_QueryInterface(void *t, const GUID *riid, void **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    if (!riid) return E_INVALIDARG;
    if (guid_eq(riid, &IID_IUnknown_)) { *out = t; return S_OK; }
    if (guid_eq(riid, &IID_v0_IGameInput)) { *out = &g_gi.i0; return S_OK; }
    if (guid_eq(riid, &IID_v1_IGameInput)) { *out = &g_gi.i1; return S_OK; }
    if (guid_eq(riid, &IID_v2_IGameInput)) { *out = &g_gi.i2; return S_OK; }
    glog("IGameInput::QueryInterface %08lX-%04X-%04X: E_NOINTERFACE", (unsigned long)riid->Data1,
         riid->Data2, riid->Data3);
    return E_NOINTERFACE;
}

/* um objeto só, do tamanho do processo */
static ULONG WINAPI gi_AddRef(void *t) { (void)t; return 2; }
static ULONG WINAPI gi_Release(void *t) { (void)t; return 1; }
static uint64_t WINAPI gi_GetCurrentTimestamp(void *t) { (void)t; return agora_us(); }

/* O aparelho da leitura: o pedido, ou o que leu por último. */
static aparelho *aparelho_da_leitura(aparelho *pedido)
{
    aparelho *melhor = NULL;
    int i;
    if (pedido) return pedido->seq ? pedido : NULL;
    for (i = 0; i < g_ap_n; i++)
        if (g_ap[i].status == STATUS_CONNECTED && g_ap[i].seq && (!melhor || g_ap[i].ts > melhor->ts))
            melhor = &g_ap[i];
    return melhor;
}

static HRESULT leitura_atual(int ver, uint32_t kind, void *dev, void **out)
{
    aparelho *a;
    leitura *l;
    if (!out) return E_POINTER;
    *out = NULL;
    if (!(kind & KINDS_DO_PAD)) return GAMEINPUT_E_READING_NOT_FOUND;
    EnterCriticalSection(&g_lock);
    a = aparelho_da_leitura(ap_de_iface(dev, ver));
    LeaveCriticalSection(&g_lock);
    if (!a) return GAMEINPUT_E_READING_NOT_FOUND;
    if (!(l = nova_leitura(a))) return E_OUTOFMEMORY;
    *out = iface_da_lei(l, ver);
    return S_OK;
}

static HRESULT leitura_seguinte(int ver, void *ref, uint32_t kind, void *dev, void **out)
{
    leitura *r, *l;
    aparelho *a;
    int nova;
    if (!out) return E_POINTER;
    *out = NULL;
    if (!ref) return E_INVALIDARG;
    if (!(kind & KINDS_DO_PAD)) return GAMEINPUT_E_READING_NOT_FOUND;
    r = lei_de(ref, ver);
    EnterCriticalSection(&g_lock);
    a = dev ? ap_de_iface(dev, ver) : aparelho_da_leitura(NULL);
    nova = a && a->seq && (a == r->ap ? a->seq > r->seq : a->ts > r->ts);
    LeaveCriticalSection(&g_lock);
    if (!nova) return GAMEINPUT_E_READING_NOT_FOUND;
    if (!(l = nova_leitura(a))) return E_OUTOFMEMORY;
    *out = iface_da_lei(l, ver);
    return S_OK;
}

static HRESULT WINAPI gi0_GetCurrentReading(void *t, uint32_t k, void *d, void **o) { (void)t; return leitura_atual(0, k, d, o); }
static HRESULT WINAPI gi1_GetCurrentReading(void *t, uint32_t k, void *d, void **o) { (void)t; return leitura_atual(1, k, d, o); }
static HRESULT WINAPI gi2_GetCurrentReading(void *t, uint32_t k, void *d, void **o) { (void)t; return leitura_atual(2, k, d, o); }
static HRESULT WINAPI gi0_GetNextReading(void *t, void *r, uint32_t k, void *d, void **o) { (void)t; return leitura_seguinte(0, r, k, d, o); }
static HRESULT WINAPI gi1_GetNextReading(void *t, void *r, uint32_t k, void *d, void **o) { (void)t; return leitura_seguinte(1, r, k, d, o); }
static HRESULT WINAPI gi2_GetNextReading(void *t, void *r, uint32_t k, void *d, void **o) { (void)t; return leitura_seguinte(2, r, k, d, o); }

/* Só a última leitura fica guardada: não há leitura anterior a devolver. */
static HRESULT WINAPI gi_GetPreviousReading(void *t, void *r, uint32_t k, void *d, void **o)
{
    (void)t; (void)r; (void)k; (void)d;
    if (o) *o = NULL;
    return GAMEINPUT_E_READING_NOT_FOUND;
}

static HRESULT registrar(int ver, void *dev, uint32_t kind, uint32_t filtro, int enumeracao, void *ctx,
                         void *fn, gi_token *token)
{
    mudanca m[MAX_APARELHOS];
    registro *r = NULL;
    aparelho *so = ap_de_iface(dev, ver);
    int i, n = 0;
    if (!fn || !token) return E_INVALIDARG;
    *token = 0;
    EnterCriticalSection(&g_lock);
    for (i = 0; i < MAX_REGISTROS; i++) {
        if (!g_reg[i].usado) { r = &g_reg[i]; break; }
    }
    if (!r) {
        LeaveCriticalSection(&g_lock);
        return E_OUTOFMEMORY;
    }
    memset(r, 0, sizeof *r);
    r->token = g_proximo_token++;
    r->ver = ver;
    r->so = so;
    r->kind = kind;
    r->filtro = filtro;
    r->ctx = ctx;
    r->fn = (cb_aparelho_t)fn;
    r->usado = 1;
    *token = r->token;
    if (enumeracao != ENUM_NONE) {
        for (i = 0; i < g_ap_n && n < MAX_APARELHOS; i++) {
            if (g_ap[i].status != STATUS_CONNECTED) continue;
            m[n].a = &g_ap[i]; m[n].antes = 0; m[n].depois = g_ap[i].status; n++;
        }
    }
    LeaveCriticalSection(&g_lock);
    glog("RegisterDeviceCallback v%d kind=%08lX filtro=%08lX enum=%d: %d aparelho(s)", ver,
         (unsigned long)kind, (unsigned long)filtro, enumeracao, n);
    /* Bloqueante ou assíncrona, a enumeração dos conectados sai já, antes do retorno. */
    avisar(m, n);
    return S_OK;
}

static HRESULT WINAPI gi0_RegisterDeviceCallback(void *t, void *d, uint32_t k, uint32_t f, int e, void *c, void *fn, gi_token *tok) { (void)t; return registrar(0, d, k, f, e, c, fn, tok); }
static HRESULT WINAPI gi1_RegisterDeviceCallback(void *t, void *d, uint32_t k, uint32_t f, int e, void *c, void *fn, gi_token *tok) { (void)t; return registrar(1, d, k, f, e, c, fn, tok); }
static HRESULT WINAPI gi2_RegisterDeviceCallback(void *t, void *d, uint32_t k, uint32_t f, int e, void *c, void *fn, gi_token *tok) { (void)t; return registrar(2, d, k, f, e, c, fn, tok); }

static registro *achar_registro(gi_token token)
{
    int i;
    for (i = 0; i < MAX_REGISTROS; i++)
        if (g_reg[i].usado && g_reg[i].token == token) return &g_reg[i];
    return NULL;
}

static void WINAPI gi_StopCallback(void *t, gi_token token)
{
    registro *r;
    (void)t;
    EnterCriticalSection(&g_lock);
    if ((r = achar_registro(token))) r->parado = 1;
    LeaveCriticalSection(&g_lock);
}

static bool WINAPI gi_UnregisterCallback(void *t, gi_token token)
{
    registro *r;
    bool achou = false;
    (void)t;
    EnterCriticalSection(&g_lock);
    if ((r = achar_registro(token))) {
        r->usado = 0;
        achou = true;
    }
    LeaveCriticalSection(&g_lock);
    return achou;
}

static HRESULT WINAPI gi_FindDeviceFromId(void *t, const gi_app_id *id, void **out, int ver)
{
    int i;
    (void)t;
    if (!out) return E_POINTER;
    *out = NULL;
    if (!id) return E_INVALIDARG;
    for (i = 0; i < g_ap_n; i++) {
        if (!memcmp(g_ap[i].info0.deviceId.value, id->value, 32)) {
            InterlockedIncrement(&g_ap[i].refs);
            *out = iface_do_ap(&g_ap[i], ver);
            return S_OK;
        }
    }
    return GAMEINPUT_E_DEVICE_NOT_FOUND;
}

static HRESULT WINAPI gi_FindDeviceFromPlatformString(const WCHAR *s, void **out, int ver)
{
    aparelho *a;
    if (!out) return E_POINTER;
    *out = NULL;
    if (!s) return E_INVALIDARG;
    if (!(a = ap_por_caminho(s))) return GAMEINPUT_E_DEVICE_NOT_FOUND;
    InterlockedIncrement(&a->refs);
    *out = iface_do_ap(a, ver);
    return S_OK;
}

static HRESULT WINAPI gi0_FindDeviceFromId(void *t, const gi_app_id *id, void **o) { return gi_FindDeviceFromId(t, id, o, 0); }
static HRESULT WINAPI gi1_FindDeviceFromId(void *t, const gi_app_id *id, void **o) { return gi_FindDeviceFromId(t, id, o, 1); }
static HRESULT WINAPI gi2_FindDeviceFromId(void *t, const gi_app_id *id, void **o) { return gi_FindDeviceFromId(t, id, o, 2); }
static HRESULT WINAPI gi0_FindDeviceFromPlatformString(void *t, const WCHAR *s, void **o) { (void)t; return gi_FindDeviceFromPlatformString(s, o, 0); }
static HRESULT WINAPI gi1_FindDeviceFromPlatformString(void *t, const WCHAR *s, void **o) { (void)t; return gi_FindDeviceFromPlatformString(s, o, 1); }
static HRESULT WINAPI gi2_FindDeviceFromPlatformString(void *t, const WCHAR *s, void **o) { (void)t; return gi_FindDeviceFromPlatformString(s, o, 2); }

NAO_IMPL(gi_GetTemporalReading, "IGameInput::GetTemporalReading")
NAO_IMPL(gi_RegisterReadingCallback, "IGameInput::RegisterReadingCallback")
NAO_IMPL(gi_RegisterSystemButtonCallback, "IGameInput::RegisterSystemButtonCallback")
NAO_IMPL(gi_RegisterKeyboardLayoutCallback, "IGameInput::RegisterKeyboardLayoutCallback")
NAO_IMPL(gi_CreateDispatcher, "IGameInput::CreateDispatcher")
NAO_IMPL(gi_CreateAggregateDevice, "IGameInput::CreateAggregateDevice")
NAO_IMPL(gi_FindDeviceFromObject, "IGameInput::FindDeviceFromObject")
NAO_IMPL(gi_FindDeviceFromPlatformHandle, "IGameInput::FindDeviceFromPlatformHandle")
NAO_IMPL(gi_EnableOemDeviceSupport, "IGameInput::EnableOemDeviceSupport")

static bool WINAPI gi0_UnregisterCallback(void *t, gi_token token, uint64_t timeout)
{
    (void)timeout;
    return gi_UnregisterCallback(t, token);
}

const void *const g_vt_gi0[] = {
    F(gi_QueryInterface), F(gi_AddRef), F(gi_Release),
    F(gi_GetCurrentTimestamp), F(gi0_GetCurrentReading), F(gi0_GetNextReading), F(gi_GetPreviousReading),
    F(gi_GetTemporalReading), F(gi_RegisterReadingCallback), F(gi0_RegisterDeviceCallback),
    F(gi_RegisterSystemButtonCallback), F(gi_RegisterKeyboardLayoutCallback), F(gi_StopCallback),
    F(gi0_UnregisterCallback), F(gi_CreateDispatcher), F(gi_CreateAggregateDevice),
    F(gi0_FindDeviceFromId), F(gi_FindDeviceFromObject), F(gi_FindDeviceFromPlatformHandle),
    F(gi0_FindDeviceFromPlatformString), F(gi_EnableOemDeviceSupport), F(nada) /* SetFocusPolicy */,
};

const void *const g_vt_gi1[] = {
    F(gi_QueryInterface), F(gi_AddRef), F(gi_Release),
    F(gi_GetCurrentTimestamp), F(gi1_GetCurrentReading), F(gi1_GetNextReading), F(gi_GetPreviousReading),
    F(gi_RegisterReadingCallback), F(gi1_RegisterDeviceCallback), F(gi_RegisterSystemButtonCallback),
    F(gi_RegisterKeyboardLayoutCallback), F(gi_StopCallback), F(gi_UnregisterCallback),
    F(gi_CreateDispatcher), F(gi1_FindDeviceFromId), F(gi1_FindDeviceFromPlatformString),
    F(nada) /* SetFocusPolicy */,
};

const void *const g_vt_gi2[] = {
    F(gi_QueryInterface), F(gi_AddRef), F(gi_Release),
    F(gi_GetCurrentTimestamp), F(gi2_GetCurrentReading), F(gi2_GetNextReading), F(gi_GetPreviousReading),
    F(gi_RegisterReadingCallback), F(gi2_RegisterDeviceCallback), F(gi_RegisterSystemButtonCallback),
    F(gi_RegisterKeyboardLayoutCallback), F(gi_StopCallback), F(gi_UnregisterCallback),
    F(gi_CreateDispatcher), F(gi2_FindDeviceFromId), F(gi2_FindDeviceFromPlatformString),
    F(nada) /* SetFocusPolicy */,
};

/* ---------- as exportações ---------- */

__declspec(dllexport) HRESULT WINAPI GameInputCreate(void **out)
{
    if (!out) return E_POINTER;
    if (sem_dualsense()) return E_NOTIMPL;
    glog("GameInputCreate");
    *out = &g_gi.i0;
    return S_OK;
}

__declspec(dllexport) HRESULT WINAPI GameInputInitialize(const GUID *riid, void **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    if (sem_dualsense()) return E_NOTIMPL;
    glog("GameInputInitialize");
    return gi_QueryInterface(&g_gi.i0, riid, out);
}

/* A identidade da peça: a peça xgameruntime confere que o Wine carregou esta, e não a embutida. */
__declspec(dllexport) const char *WINAPI HefestoPecaGameInput(void)
{
    return PECA_GAMEINPUT_ID;
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, void *reserved)
{
    (void)inst; (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        InitializeCriticalSection(&g_lock);
        g_lock_ready = 1;
    }
    return TRUE;
}
