"""A mesa de quatro no jogo GDK: o que a peça GameInput garante de dois a quatro aparelhos.

O jogo GDK lê a entrada pela XInput e pelo HID da biblioteca Sony; a peça `gameinput.dll`
responde ao Wwise Motion, que pede a vibração. Para a mesa de quatro, a peça garante, em cabo
e rádio e de P1 a P4: cada pad é um aparelho só, achado pelo caminho; o controle que sai e
volta pelo mesmo caminho é o mesmo aparelho, com o mesmo `deviceId`; o rumble e o reenvio de
1 s são de cada aparelho; o aparelho que sai leva o rumble dele, e o que volta pelo mesmo
caminho nasce calado, sem tocar no vizinho; e cabem os quatro jogadores e as voltas deles numa
partida, como pede a D-2210-O-JOGO-GDK-VIBRA-PELO-GAMEINPUT-DA-CASA («P1 a P4»). A troca de
transporte no meio do jogo não chega à peça: o jogador que troca fica com o mesmo pad virtual,
logo com o mesmo caminho. O comportamento no jogo de verdade se mede no prefixo, não aqui.
"""
from __future__ import annotations

import re
from pathlib import Path

_FONTE = Path(__file__).resolve().parents[2] / "assets" / "gdk-runtime" / "gameinput.c"


def _fonte() -> str:
    return _FONTE.read_text(encoding="utf-8")


def _corpo(fonte: str, assinatura: str) -> str:
    assert assinatura in fonte, f"a função sumiu da peça: {assinatura}"
    return fonte.split(assinatura, 1)[1].split("\n}\n", 1)[0]


def test_o_controle_que_volta_pelo_mesmo_caminho_e_o_mesmo_aparelho() -> None:
    """A lista procura o caminho conhecido antes de criar outro; o `deviceId` sai do caminho."""
    fonte = _fonte()
    lista = _corpo(fonte, "static int listar_hid(mudanca *m, int max)\n{")
    procura = lista.find("a = ap_por_caminho(det->DevicePath);")
    cria = lista.find("novo_aparelho(det->DevicePath")
    assert procura != -1, "a lista não procura o caminho conhecido: quem volta vira outro"
    assert cria != -1 and procura < cria, "a lista cria o aparelho antes de procurar o conhecido"
    busca = _corpo(fonte, "static aparelho *ap_por_caminho(const WCHAR *caminho)\n{")
    assert "_wcsicmp(g_ap[i].caminho, caminho)" in busca
    info = _corpo(
        fonte,
        "static void preencher_info(aparelho *a, uint16_t vid, uint16_t pid, uint16_t rev)\n{",
    )
    assert "sha256((const BYTE *)baixo" in info, "o deviceId não sai mais do caminho"


def test_o_rumble_e_o_reenvio_sao_de_cada_aparelho() -> None:
    """O par dos motores, a trava e o relógio do reenvio moram no aparelho; o vigia vai um a um."""
    fonte = _fonte()
    estrutura = fonte.split("typedef struct aparelho {", 1)[1].split("} aparelho;", 1)[0]
    for campo in ("CRITICAL_SECTION wlock;", "BYTE fraco, forte;", "ULONGLONG ultima_escrita_ms;"):
        assert campo in estrutura, f"o rumble saiu do aparelho: {campo}"
    vigia = _corpo(fonte, "static DWORD WINAPI vigia_thread(void *arg)\n{")
    assert "aparelho *a = &g_ap[i];" in vigia
    assert "EnterCriticalSection(&a->wlock);" in vigia
    assert "escrever_rumble(a, a->fraco, a->forte);" in vigia, "o reenvio não é do aparelho"
    rumble = _corpo(fonte, "static void rumble_de(aparelho *a, const gi_rumble *p)\n{")
    assert "a->fraco = fraco;" in rumble
    assert "escrever_rumble(a, fraco, forte);" in rumble


def test_o_aparelho_que_sai_leva_o_rumble_dele() -> None:
    """A saída zera o par só daquele aparelho, sob a trava dele, e escreve o zero uma vez."""
    fonte = _fonte()
    lista = _corpo(fonte, "static int listar_hid(mudanca *m, int max)\n{")
    saida = lista.split("SetupDiDestroyDeviceInfoList(set);", 1)[1]
    poe_zero = saida.find("g_ap[j].status = 0;")
    assert poe_zero != -1, "a lista não marca mais a saída"
    assert "calar(&g_ap[j]);" in saida[poe_zero:], (
        "o aparelho que sai deixa o rumble para quem volta"
    )
    calar = _corpo(fonte, "static void calar(aparelho *a)\n{")
    assert "g_ap[" not in calar, "o calar mexe no rumble de outro aparelho"
    trava = calar.find("EnterCriticalSection(&a->wlock);")
    solta = calar.find("LeaveCriticalSection(&a->wlock);")
    for linha in ("a->fraco = 0;", "a->forte = 0;", "escrever_rumble(a, 0, 0);"):
        assert trava < calar.find(linha) < solta, f"o calar perdeu, sob a trava: {linha}"


def test_o_aparelho_que_volta_nasce_calado() -> None:
    """Reabrir o caminho que saiu zera o par: o vigia não reenvia o tranco de antes da saída.

    A reabertura de um aparelho que segue conectado para o jogo (a leitura caiu e o caminho
    voltou antes da lista seguinte, sem aviso de saída) guarda o par que o jogo pediu.
    """
    abrir = _corpo(_fonte(), "static int abrir(aparelho *a)\n{")
    trava = abrir.find("EnterCriticalSection(&a->wlock);")
    solta = abrir.find("LeaveCriticalSection(&a->wlock);")
    for linha in ("a->fraco = 0;", "a->forte = 0;"):
        assert trava < abrir.find(linha) < solta, "quem volta reenvia o rumble velho"
    guarda = abrir.find("if (a->status != STATUS_CONNECTED) {")
    assert trava < guarda < abrir.find("a->fraco = 0;"), (
        "a reabertura sem saída cala o tranco que o jogo segue pedindo"
    )


def test_cabem_os_quatro_jogadores_e_as_voltas_deles() -> None:
    """Quatro jogadores e uma volta de cada por caminho novo cabem nas vagas da peça."""
    achado = re.search(r"^#define MAX_APARELHOS (\d+)$", _fonte(), re.MULTILINE)
    assert achado, "a peça perdeu o teto de aparelhos"
    vagas = int(achado.group(1))
    assert vagas >= 8, f"só {vagas} vagas: a quarta volta fica sem aparelho"
