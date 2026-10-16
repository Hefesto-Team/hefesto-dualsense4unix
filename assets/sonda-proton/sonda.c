/*
 * A sonda do Proton candidato: o .exe que a rodada lança sob a versão que se
 * qualifica (scripts/ensaios/a_rodada_do_proton_candidato.py). Ela faz o que
 * um jogo faz, e diz em JSON, uma linha por prova, o que achou:
 *
 *   contagem  quantos HID Sony, quantas vagas XInput e quantos devices
 *             KSCATEGORY_AUDIO por ContainerId o jogo vê;
 *   haptica   acha o endpoint de saída pelo ContainerId do HID Sony (o caminho
 *             do setupapi que a RE Engine usa) e toca um pulso conhecido nos
 *             canais 3-4; a rodada o mede no monitor do nó;
 *   gatilho   escreve no HID Sony o output report 0x02 com um efeito
 *             conhecido; a rodada compara byte a byte com o que chega ao uhid;
 *   microfone captura um segundo do endpoint de captura do mesmo ContainerId
 *             e diz a potência no tom que a rodada pôs na fonte vestida.
 *
 * A sonda não julga: quem julga é a rodada, com o que mediu do outro lado.
 * Compilação (no CI): x86_64-w64-mingw32-gcc -O2 -o sonda.exe sonda.c
 *   -lsetupapi -lhid -lole32 -lxinput1_4 -luuid
 */
#define COBJMACROS
#define INITGUID
#include <windows.h>
#include <initguid.h>
#include <setupapi.h>
#include <hidsdi.h>
#include <devpkey.h>
#include <ks.h>
#include <ksmedia.h>
#include <mmdeviceapi.h>
#include <audioclient.h>
#include <functiondiscoverykeys_devpkey.h>
#include <xinput.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#define VID_SONY 0x054C
#define PULSO_HZ 120.0
#define PULSO_MS 300
#define TOM_HZ 440.0
#define MAX_CONTAINERS 32

/* O efeito conhecido do gatilho: o report 0x02 do cabo, 48 bytes, com o
 * gatilho direito em modo rígido (0x01), início 0x40 e força 0xA0. */
static const unsigned char REPORT_DO_GATILHO[48] = {
    0x02, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x01, 0x40, 0xA0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
};

static GUID container_sony;
static int tem_container_sony = 0;
static WCHAR caminho_sony[512];

static void guid_texto(const GUID *g, char *saida, size_t n)
{
    snprintf(saida, n, "%08lx-%04x-%04x-%02x%02x-%02x%02x%02x%02x%02x%02x",
             (unsigned long)g->Data1, g->Data2, g->Data3, g->Data4[0], g->Data4[1],
             g->Data4[2], g->Data4[3], g->Data4[4], g->Data4[5], g->Data4[6], g->Data4[7]);
}

static int container_do_device(HDEVINFO set, SP_DEVINFO_DATA *dev, GUID *saida)
{
    DEVPROPTYPE tipo;
    return SetupDiGetDevicePropertyW(set, dev, &DEVPKEY_Device_ContainerId, &tipo,
                                     (PBYTE)saida, sizeof(*saida), NULL, 0)
           && tipo == DEVPROP_TYPE_GUID;
}

static void contar_hid(void)
{
    GUID hid;
    HidD_GetHidGuid(&hid);
    HDEVINFO set = SetupDiGetClassDevsW(&hid, NULL, NULL, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);
    int sony = 0, total = 0;
    SP_DEVICE_INTERFACE_DATA itf = {sizeof(itf)};
    for (DWORD i = 0; SetupDiEnumDeviceInterfaces(set, NULL, &hid, i, &itf); i++) {
        BYTE buf[sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W) + 1024];
        SP_DEVICE_INTERFACE_DETAIL_DATA_W *det = (SP_DEVICE_INTERFACE_DETAIL_DATA_W *)buf;
        det->cbSize = sizeof(*det);
        SP_DEVINFO_DATA dev = {sizeof(dev)};
        if (!SetupDiGetDeviceInterfaceDetailW(set, &itf, det, sizeof(buf), NULL, &dev))
            continue;
        HANDLE h = CreateFileW(det->DevicePath, 0, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL,
                               OPEN_EXISTING, 0, NULL);
        if (h == INVALID_HANDLE_VALUE)
            continue;
        HIDD_ATTRIBUTES at = {sizeof(at)};
        if (HidD_GetAttributes(h, &at)) {
            total++;
            if (at.VendorID == VID_SONY) {
                sony++;
                if (!tem_container_sony && container_do_device(set, &dev, &container_sony)) {
                    tem_container_sony = 1;
                    wcsncpy(caminho_sony, det->DevicePath, 511);
                }
            }
        }
        CloseHandle(h);
    }
    SetupDiDestroyDeviceInfoList(set);

    int vagas = 0;
    char ordem[16] = "";
    for (DWORD v = 0; v < XUSER_MAX_COUNT; v++) {
        XINPUT_STATE st;
        int ligada = XInputGetState(v, &st) == ERROR_SUCCESS;
        vagas += ligada;
        ordem[v] = ligada ? '1' : '0';
    }

    GUID vistos[MAX_CONTAINERS];
    int contas[MAX_CONTAINERS], n = 0;
    set = SetupDiGetClassDevsW(&KSCATEGORY_AUDIO, NULL, NULL, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);
    for (DWORD i = 0; SetupDiEnumDeviceInterfaces(set, NULL, &KSCATEGORY_AUDIO, i, &itf); i++) {
        SP_DEVINFO_DATA dev = {sizeof(dev)};
        if (!SetupDiGetDeviceInterfaceDetailW(set, &itf, NULL, 0, NULL, &dev)
            && GetLastError() != ERROR_INSUFFICIENT_BUFFER)
            continue;
        GUID c;
        if (!container_do_device(set, &dev, &c))
            continue;
        int j;
        for (j = 0; j < n && !IsEqualGUID(&vistos[j], &c); j++)
            ;
        if (j == n && n < MAX_CONTAINERS) {
            vistos[n] = c;
            contas[n++] = 0;
        }
        if (j < MAX_CONTAINERS)
            contas[j]++;
    }
    SetupDiDestroyDeviceInfoList(set);

    printf("{\"prova\":\"contagem\",\"hid_total\":%d,\"hid_sony\":%d,\"vagas_xinput\":%d,"
           "\"ordem_xinput\":\"%s\",\"ks_por_container\":{", total, sony, vagas, ordem);
    for (int j = 0; j < n; j++) {
        char g[48];
        guid_texto(&vistos[j], g, sizeof(g));
        printf("%s\"%s\":%d", j ? "," : "", g, contas[j]);
    }
    printf("}}\n");
}

static IMMDevice *endpoint_do_container(EDataFlow fluxo)
{
    IMMDeviceEnumerator *en = NULL;
    IMMDeviceCollection *col = NULL;
    IMMDevice *achado = NULL;
    if (FAILED(CoCreateInstance(&CLSID_MMDeviceEnumerator, NULL, CLSCTX_ALL,
                                &IID_IMMDeviceEnumerator, (void **)&en)))
        return NULL;
    if (SUCCEEDED(IMMDeviceEnumerator_EnumAudioEndpoints(en, fluxo, DEVICE_STATE_ACTIVE, &col))) {
        UINT n = 0;
        IMMDeviceCollection_GetCount(col, &n);
        for (UINT i = 0; i < n && !achado; i++) {
            IMMDevice *dev;
            IPropertyStore *ps;
            PROPVARIANT v;
            if (FAILED(IMMDeviceCollection_Item(col, i, &dev)))
                continue;
            PropVariantInit(&v);
            if (SUCCEEDED(IMMDevice_OpenPropertyStore(dev, STGM_READ, &ps))) {
                if (SUCCEEDED(IPropertyStore_GetValue(ps, &PKEY_Device_ContainerId, &v))
                    && v.vt == VT_CLSID && IsEqualGUID(v.puuid, &container_sony))
                    achado = dev;
                PropVariantClear(&v);
                IPropertyStore_Release(ps);
            }
            if (achado != dev)
                IMMDevice_Release(dev);
        }
        IMMDeviceCollection_Release(col);
    }
    IMMDeviceEnumerator_Release(en);
    return achado;
}

static void provar_haptica(void)
{
    IMMDevice *dev = tem_container_sony ? endpoint_do_container(eRender) : NULL;
    if (!dev) {
        printf("{\"prova\":\"haptica\",\"achou\":false}\n");
        return;
    }
    IAudioClient *cli = NULL;
    IAudioRenderClient *ren = NULL;
    WAVEFORMATEX *fmt = NULL;
    int canais = 0, tocou = 0;
    if (SUCCEEDED(IMMDevice_Activate(dev, &IID_IAudioClient, CLSCTX_ALL, NULL, (void **)&cli))
        && SUCCEEDED(IAudioClient_GetMixFormat(cli, &fmt))) {
        canais = fmt->nChannels;
        if (canais >= 4
            && SUCCEEDED(IAudioClient_Initialize(cli, AUDCLNT_SHAREMODE_SHARED, 0,
                                                 10000000, 0, fmt, NULL))
            && SUCCEEDED(IAudioClient_GetService(cli, &IID_IAudioRenderClient, (void **)&ren))) {
            UINT32 tam = 0;
            IAudioClient_GetBufferSize(cli, &tam);
            UINT32 quadros = fmt->nSamplesPerSec * PULSO_MS / 1000;
            if (quadros > tam)
                quadros = tam;
            BYTE *dados;
            if (SUCCEEDED(IAudioRenderClient_GetBuffer(ren, quadros, &dados))) {
                /* O formato misto do Wine é float32; os canais 3-4 levam o pulso. */
                float *f = (float *)dados;
                for (UINT32 q = 0; q < quadros; q++) {
                    float s = (float)(0.8 * sin(2.0 * M_PI * PULSO_HZ * q / fmt->nSamplesPerSec));
                    for (int c = 0; c < canais; c++)
                        f[q * canais + c] = (c == 2 || c == 3) ? s : 0.0f;
                }
                IAudioRenderClient_ReleaseBuffer(ren, quadros, 0);
                IAudioClient_Start(cli);
                Sleep(PULSO_MS + 200);
                IAudioClient_Stop(cli);
                tocou = 1;
            }
            IAudioRenderClient_Release(ren);
        }
    }
    printf("{\"prova\":\"haptica\",\"achou\":true,\"canais\":%d,\"tocou\":%s,\"hz\":%.0f}\n",
           canais, tocou ? "true" : "false", PULSO_HZ);
    if (fmt)
        CoTaskMemFree(fmt);
    if (cli)
        IAudioClient_Release(cli);
    IMMDevice_Release(dev);
}

static void provar_gatilho(void)
{
    if (!tem_container_sony) {
        printf("{\"prova\":\"gatilho\",\"escreveu\":false}\n");
        return;
    }
    HANDLE h = CreateFileW(caminho_sony, GENERIC_READ | GENERIC_WRITE,
                           FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
    DWORD escritos = 0;
    BOOL ok = h != INVALID_HANDLE_VALUE
              && WriteFile(h, REPORT_DO_GATILHO, sizeof(REPORT_DO_GATILHO), &escritos, NULL);
    if (h != INVALID_HANDLE_VALUE)
        CloseHandle(h);
    printf("{\"prova\":\"gatilho\",\"escreveu\":%s,\"bytes\":\"", ok ? "true" : "false");
    for (size_t i = 0; i < sizeof(REPORT_DO_GATILHO); i++)
        printf("%02x", REPORT_DO_GATILHO[i]);
    printf("\"}\n");
}

static void provar_microfone(void)
{
    IMMDevice *dev = tem_container_sony ? endpoint_do_container(eCapture) : NULL;
    if (!dev) {
        printf("{\"prova\":\"microfone\",\"achou\":false}\n");
        return;
    }
    IAudioClient *cli = NULL;
    IAudioCaptureClient *cap = NULL;
    WAVEFORMATEX *fmt = NULL;
    double re = 0, im = 0, energia = 0;
    unsigned long n = 0;
    if (SUCCEEDED(IMMDevice_Activate(dev, &IID_IAudioClient, CLSCTX_ALL, NULL, (void **)&cli))
        && SUCCEEDED(IAudioClient_GetMixFormat(cli, &fmt))
        && SUCCEEDED(IAudioClient_Initialize(cli, AUDCLNT_SHAREMODE_SHARED, 0, 10000000, 0,
                                             fmt, NULL))
        && SUCCEEDED(IAudioClient_GetService(cli, &IID_IAudioCaptureClient, (void **)&cap))) {
        IAudioClient_Start(cli);
        DWORD fim = GetTickCount() + 1000;
        while (GetTickCount() < fim) {
            Sleep(20);
            BYTE *dados;
            UINT32 quadros;
            DWORD flags;
            while (SUCCEEDED(IAudioCaptureClient_GetBuffer(cap, &dados, &quadros, &flags, NULL, NULL))
                   && quadros) {
                float *f = (float *)dados;
                for (UINT32 q = 0; q < quadros; q++, n++) {
                    double s = (flags & AUDCLNT_BUFFERFLAGS_SILENT) ? 0.0 : f[q * fmt->nChannels];
                    double fase = 2.0 * M_PI * TOM_HZ * n / fmt->nSamplesPerSec;
                    re += s * cos(fase);
                    im += s * sin(fase);
                    energia += s * s;
                }
                IAudioCaptureClient_ReleaseBuffer(cap, quadros);
            }
        }
        IAudioClient_Stop(cli);
        IAudioCaptureClient_Release(cap);
    }
    /* A fração da energia que está no tom: perto de 1 para um seno puro. */
    double no_tom = (energia > 0 && n) ? 2.0 * (re * re + im * im) / (energia * n) : 0.0;
    printf("{\"prova\":\"microfone\",\"achou\":true,\"amostras\":%lu,\"rms\":%.5f,"
           "\"fracao_no_tom\":%.4f,\"hz\":%.0f}\n",
           n, n ? sqrt(energia / n) : 0.0, no_tom, TOM_HZ);
    if (fmt)
        CoTaskMemFree(fmt);
    if (cli)
        IAudioClient_Release(cli);
    IMMDevice_Release(dev);
}

int main(void)
{
    CoInitializeEx(NULL, COINIT_MULTITHREADED);
    contar_hid();
    provar_haptica();
    provar_gatilho();
    provar_microfone();
    char g[48] = "";
    if (tem_container_sony)
        guid_texto(&container_sony, g, sizeof(g));
    printf("{\"prova\":\"fim\",\"container_sony\":\"%s\"}\n", g);
    fflush(stdout);
    CoUninitialize();
    return 0;
}
