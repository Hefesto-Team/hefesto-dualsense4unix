"""O sinal de cada controle diz se ele está longe — SINAL-DE-CADA-CONTROLE-01.

A bancada de 03/10/2026: o Hz mistura «adaptador dividido» com «distância», e só o sinal (o
RSSI do enlace, lido sem root) segue quem se afasta. A cor e a frase saem dos dois números
JUNTOS, e o Hz se mede contra o que o controle dava naquele adaptador.
"""

from __future__ import annotations

import socket
import struct
import threading
import time
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes.a08_conexoes`, que carrega o GTK")

from hefesto_dualsense4unix.integrations import ar_do_adaptador as ar
from hefesto_dualsense4unix.integrations import radio_da_mesa as rm
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08
from tests.unit.test_o_ar_do_adaptador import _SocketDeMentira

#: faixa forjada (`aa:bb:cc`)
APARELHO_A = "aa:bb:cc:00:00:11"
APARELHO_B = "aa:bb:cc:00:00:12"
ADAPTADOR = "aa:bb:cc:00:00:0a"


def _resposta_rssi(handle: int, rssi: int, *, status: int = 0) -> bytes:
    params = bytes([status]) + struct.pack("<H", handle) + struct.pack("<b", rssi)
    corpo = bytes([0x01]) + struct.pack("<H", ar.OPCODE_LER_RSSI) + params
    return bytes([0x04, 0x0E, len(corpo)]) + corpo


# --- 1. o serviço lê o sinal, sem root -----------------------------------------------------

def test_o_read_rssi_e_o_que_o_filtro_do_kernel_deixa_sem_root() -> None:
    """``hci_sec_filter``: ``OGF_STATUS_PARAM`` = ``0x000000ea``, bit do OCF."""
    ogf, ocf = ar.OPCODE_LER_RSSI >> 10, ar.OPCODE_LER_RSSI & 0x3FF
    assert (ogf, ocf) == (0x05, 0x0005)
    assert (0x000000EA >> ocf) & 1 == 1


@pytest.mark.parametrize("rssi", [-58, -53, -31, -10, 0, 4])
def test_o_rssi_sai_assinado_da_resposta(rssi: int) -> None:
    assert ar.rssi_da_resposta(_resposta_rssi(12, rssi), 12) == rssi


def test_resposta_de_outro_enlace_ou_com_erro_nao_e_o_sinal() -> None:
    assert ar.rssi_da_resposta(_resposta_rssi(13, -40), 12) is None
    assert ar.rssi_da_resposta(_resposta_rssi(12, -40, status=0x02), 12) is None


def test_ler_rssi_manda_so_o_comando_de_leitura_e_filtra_a_resposta() -> None:
    falso = _SocketDeMentira(_resposta_rssi(12, -53))
    assert ar.ler_rssi(0, 12, abrir=lambda _hci: falso) == -53  # type: ignore[arg-type,return-value]
    assert falso.enviados == [struct.pack("<BHBH", 0x01, ar.OPCODE_LER_RSSI, 2, 12)]
    ((nivel, nome, filtro),) = falso.opcoes
    assert (nivel, nome) == (0, 2)
    _tipos, _eventos, _, opcode = struct.unpack("<IIIH2x", filtro)
    assert opcode == ar.OPCODE_LER_RSSI


def test_ler_rssi_sem_resposta_ou_sem_socket_e_nao_sei() -> None:
    mudo = _SocketDeMentira(None)
    assert ar.ler_rssi(0, 12, prazo_s=0.05, abrir=lambda _hci: mudo) is None  # type: ignore[arg-type,return-value]

    def recusa(_hci: int) -> socket.socket:
        raise PermissionError(1, "Operation not permitted")

    assert ar.ler_rssi(0, 12, abrir=recusa) is None


def test_no_modo_falso_o_rssi_nunca_pergunta_ao_radio_de_verdade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_FAKE", "1")
    monkeypatch.setattr(socket, "socket", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("a suíte abriu um socket HCI para perguntar o sinal")))
    assert ar.ler_rssi(0, 12) is None


def _leitura(*enlaces: ar.Enlace) -> ar.ArDoAdaptador:
    return ar.ArDoAdaptador(hci=2, endereco=ADAPTADOR, entrada_por_s=700.0, conexoes=enlaces)


def test_o_sinal_de_cada_enlace_acl_chega_pelo_uniq_do_controle() -> None:
    leitura = _leitura(
        ar.Enlace(12, APARELHO_A, ar.TIPO_ACL, True, 1, 7),
        ar.Enlace(13, APARELHO_B, ar.TIPO_ACL, True, 1, 7),
        ar.Enlace(14, "aa:bb:cc:00:00:13", 0x00, True, 1, 7),
    )
    perguntados: list[tuple[int, int]] = []

    def ler(hci: int, handle: int) -> int | None:
        perguntados.append((hci, handle))
        return {12: -31, 13: None}[handle]

    sinais = rm.sinais_dos_enlaces({ADAPTADOR: leitura}, ler=ler)
    assert sinais == {"aabbcc000011": -31, "aabbcc000012": None}
    assert perguntados == [(2, 12), (2, 13)], "só o enlace ACL de dados tem sinal"


def test_o_servico_pergunta_o_sinal_numa_thread_de_segundo_em_segundo() -> None:
    from tests.unit.test_os_hz_de_cada_controle import _handlers

    handlers = _handlers(pytest.MonkeyPatch())[1]
    perguntas: list[tuple[int, int]] = []
    nomes: list[str] = []

    def ler(hci: int, handle: int) -> int:
        perguntas.append((hci, handle))
        nomes.append(threading.current_thread().name)
        return -42

    handlers._ler_sinal = ler  # type: ignore[attr-defined]
    ar_do_adaptador = {ADAPTADOR: _leitura(ar.Enlace(12, APARELHO_A, ar.TIPO_ACL, True, 1, 7))}
    handlers._talvez_ler_o_sinal(ar_do_adaptador)  # type: ignore[attr-defined]
    prazo = time.monotonic() + 2.0
    while handlers._sinal_em_voo and time.monotonic() < prazo:  # type: ignore[attr-defined]
        time.sleep(0.01)
    assert perguntas == [(2, 12)] and nomes == ["radio-sinal"]
    assert handlers._sinal_dos_enlaces == {"aabbcc000011": -42}  # type: ignore[attr-defined]
    handlers._talvez_ler_o_sinal(ar_do_adaptador)  # type: ignore[attr-defined]
    assert perguntas == [(2, 12)], "o sinal foi perguntado de novo antes do período"


def test_o_state_full_publica_o_sinal_do_controle_no_radio_e_nada_no_cabo() -> None:
    from tests.unit.test_os_hz_de_cada_controle import UNIQ_1, UNIQ_CABO, _handlers

    handlers = _handlers(pytest.MonkeyPatch())[1]
    handlers._sinal_dos_enlaces = {UNIQ_1: -53}  # type: ignore[attr-defined]
    entradas: list[dict[str, Any]] = [
        {"uniq": UNIQ_1, "transport": "bt", "connected": True},
        {"uniq": UNIQ_CABO, "transport": "usb", "connected": True},
    ]
    handlers._merge_radio(entradas)  # type: ignore[attr-defined]
    assert [e["sinal_dbm"] for e in entradas] == [-53, None]


# --- 2. a cor e a frase vêm dos dois números juntos ----------------------------------------

REFERENCIA_DE_DOIS = 280.0


def test_sinal_fraco_com_hz_caindo_e_longe_e_sinal_bom_com_hz_caindo_e_interferencia() -> None:
    longe = rm.diagnosticar_o_movimento(21, sinal_dbm=-53, referencia_hz=REFERENCIA_DE_DOIS)
    interferencia = rm.diagnosticar_o_movimento(30, sinal_dbm=-31, referencia_hz=REFERENCIA_DE_DOIS)
    liso = rm.diagnosticar_o_movimento(237, sinal_dbm=-28, referencia_hz=REFERENCIA_DE_DOIS)
    assert (longe.causa, interferencia.causa, liso.causa) == (rm.CAUSA_LONGE,
                                                              rm.CAUSA_INTERFERENCIA, "")
    assert longe.nivel == interferencia.nivel == rm.NIVEL_ENGASGA and liso.nivel == rm.NIVEL_LISO
    # com a cura arrancada (a cor só pelo Hz absoluto) o 1º e o 2º saem iguais:
    assert rm.nivel_do_movimento(21) == rm.nivel_do_movimento(30)


def test_o_adaptador_cheio_diz_a_conta_de_quem_divide() -> None:
    d = rm.diagnosticar_o_movimento(30, sinal_dbm=-31, referencia_hz=REFERENCIA_DE_DOIS,
                                    adaptador_cheio=True)
    assert d.causa == rm.CAUSA_ADAPTADOR_CHEIO


def test_sinal_no_limiar_que_atrasa_ja_e_longe() -> None:
    d = rm.diagnosticar_o_movimento(60, sinal_dbm=rm.SINAL_QUE_ATRASA_DBM,
                                    referencia_hz=REFERENCIA_DE_DOIS)
    assert d.causa == rm.CAUSA_LONGE
    d = rm.diagnosticar_o_movimento(60, sinal_dbm=rm.SINAL_QUE_ATRASA_DBM + 1,
                                    referencia_hz=REFERENCIA_DE_DOIS)
    assert d.causa == rm.CAUSA_INTERFERENCIA


def test_o_x_perdido_mora_abaixo_do_limiar_que_perde_aperto() -> None:
    """A medida de 18h33: os X perdidos moram em -52 a -58, com o Hz de 0 a 15."""
    assert rm.SINAL_QUE_PERDE_APERTO_DBM < rm.SINAL_QUE_ATRASA_DBM
    d = rm.diagnosticar_o_movimento(10, sinal_dbm=-55, referencia_hz=REFERENCIA_DE_DOIS)
    assert (d.nivel, d.causa) == (rm.NIVEL_ENGASGA, rm.CAUSA_LONGE)


# --- 3. o limiar do Hz é relativo ao adaptador ---------------------------------------------

@pytest.fixture()
def tela_limpa(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    relogio = [1000.0]
    monkeypatch.setattr(a08, "_RELOGIO_DO_NIVEL", lambda: relogio[0])
    for nome in ("_NIVEL_NA_TELA", "_CAUSA_NA_TELA", "_REFERENCIA_DO_HZ"):
        monkeypatch.setattr(a08, nome, {})
    return relogio


def _cena(controles: dict[str, dict[str, Any]], *, lugar: str = "L1") -> dict[str, Any]:
    aparelhos = [{"id": ident, "tipo": "controle", "lugar": campos.pop("lugar", lugar),
                  "nome": "", "rotulo": "DualSense", "cor": "", "mic": False, "ponte": None,
                  "alem": False, "esperando": False, "fixo": False, "luz": True, **campos}
                 for ident, campos in controles.items()]
    return {"lugares": [{"id": "L1", "nome": "A"}, {"id": "L2", "nome": "B"}],
            "aparelhos": aparelhos, "evitados": [], "canais_medidos": {}, "vizinhos": [],
            "wifi": [], "portas": [], "procurando": a08.PROCURAR_DESLIGADO}


def _nivel_e_dica(cena: dict[str, Any], ident_ordem: int = 0) -> tuple[str, str]:
    campos = a08.campos_da_secao(cena, segurar=True)
    return campos["hz-nivel"][ident_ordem], campos["hz-dica"][ident_ordem]


def test_um_controle_sozinho_a_250_depois_de_650_fica_amarelo(tela_limpa: list[float]) -> None:
    for hz in (650.0, 640.0, 660.0):
        tela_limpa[0] += 1.0
        assert _nivel_e_dica(_cena({"a": {"hz_mov": hz, "sinal": -30}}))[0] == rm.NIVEL_LISO
    tela_limpa[0] += 10.0
    nivel, dica = _nivel_e_dica(_cena({"a": {"hz_mov": 250.0, "sinal": -30}}))
    assert nivel == rm.NIVEL_MEDIO
    assert dica == a08.FRASE_DA_CAUSA[rm.CAUSA_INTERFERENCIA]


def test_dois_dividindo_o_adaptador_a_250_ficam_verdes(tela_limpa: list[float]) -> None:
    for _ in range(3):
        tela_limpa[0] += 1.0
        campos = a08.campos_da_secao(_cena({"a": {"hz_mov": 270.0, "sinal": -30},
                                            "b": {"hz_mov": 250.0, "sinal": -28}}), segurar=True)
    assert campos["hz-nivel"] == [rm.NIVEL_LISO, rm.NIVEL_LISO]


def test_quando_chega_o_segundo_a_referencia_do_primeiro_recomeca(tela_limpa: list[float]) -> None:
    for _ in range(3):
        tela_limpa[0] += 1.0
        a08.campos_da_secao(_cena({"a": {"hz_mov": 650.0, "sinal": -30}}), segurar=True)
    tela_limpa[0] += 1.0
    campos = a08.campos_da_secao(_cena({"a": {"hz_mov": 300.0, "sinal": -30},
                                        "b": {"hz_mov": 300.0, "sinal": -30}}), segurar=True)
    assert campos["hz-nivel"] == [rm.NIVEL_LISO, rm.NIVEL_LISO], (
        "o 650 de quando ele estava sozinho não vale com dois no adaptador")


def test_o_controle_que_muda_de_adaptador_recomeca_a_referencia(tela_limpa: list[float]) -> None:
    """A referência é do controle NAQUELE adaptador: o 650 que ele dava sozinho no L1 não
    vale no L2, onde ele também está sozinho (a conta de quem divide não muda)."""
    for _ in range(3):
        tela_limpa[0] += 1.0
        a08.campos_da_secao(_cena({"a": {"hz_mov": 650.0, "sinal": -30}}), segurar=True)
    tela_limpa[0] += 1.0
    nivel, _ = _nivel_e_dica(_cena({"a": {"hz_mov": 300.0, "sinal": -30, "lugar": "L2"}}))
    assert nivel == rm.NIVEL_LISO, "o 650 do L1 não é a referência dele no L2"


# --- 4. sem o sinal a linha diz «sinal desconhecido», e não verde ---------------------------

def test_pelo_radio_sem_sinal_a_linha_nao_e_verde_e_diz_que_nao_sabe(
    tela_limpa: list[float],
) -> None:
    tela_limpa[0] += 1.0
    nivel, dica = _nivel_e_dica(_cena({"a": {"hz_mov": 300.0, "sinal": None}}))
    assert nivel != rm.NIVEL_LISO
    assert dica == a08.FRASE_DA_CAUSA[rm.CAUSA_SEM_SINAL] and "desconhecido" in dica


def test_pelo_cabo_nao_ha_sinal_a_pedir(tela_limpa: list[float]) -> None:
    tela_limpa[0] += 1.0
    nivel, dica = _nivel_e_dica(_cena({"a": {"hz_mov": 900.0, "sinal": None, "usb": True}}))
    assert nivel == rm.NIVEL_LISO and dica == a08.DICA_DO_MOVIMENTO[rm.NIVEL_LISO]


# --- 5. a cor piora na hora e melhora devagar, com a frase junto ----------------------------

def test_o_mergulho_de_um_segundo_fica_na_tela_com_a_frase_dele(tela_limpa: list[float]) -> None:
    for _ in range(3):
        tela_limpa[0] += 1.0
        _nivel_e_dica(_cena({"a": {"hz_mov": 280.0, "sinal": -30}}))
    tela_limpa[0] += 1.0
    nivel, dica = _nivel_e_dica(_cena({"a": {"hz_mov": 36.0, "sinal": -52}}))
    assert (nivel, dica) == (rm.NIVEL_ENGASGA, a08.FRASE_DA_CAUSA[rm.CAUSA_LONGE])
    tela_limpa[0] += 1.0
    nivel, dica = _nivel_e_dica(_cena({"a": {"hz_mov": 280.0, "sinal": -30}}))
    assert (nivel, dica) == (rm.NIVEL_ENGASGA, a08.FRASE_DA_CAUSA[rm.CAUSA_LONGE]), (
        "melhorou depois de um segundo: a cor tem de segurar, e a frase com ela")
    tela_limpa[0] += rm.SEGURA_O_NIVEL_S
    assert _nivel_e_dica(_cena({"a": {"hz_mov": 280.0, "sinal": -30}}))[0] == rm.NIVEL_LISO


def test_so_o_controle_que_se_afastou_muda_o_vizinho_no_mesmo_adaptador_nao(
    tela_limpa: list[float],
) -> None:
    """O teste com testemunha: P3 longe, P4 parado perto, no mesmo adaptador."""
    for _ in range(3):
        tela_limpa[0] += 1.0
        a08.campos_da_secao(_cena({"p3": {"hz_mov": 282.0, "sinal": -30},
                                   "p4": {"hz_mov": 227.0, "sinal": -31}}), segurar=True)
    tela_limpa[0] += 1.0
    campos = a08.campos_da_secao(_cena({"p3": {"hz_mov": 21.0, "sinal": -53},
                                        "p4": {"hz_mov": 237.0, "sinal": -28}}), segurar=True)
    assert campos["hz-nivel"] == [rm.NIVEL_ENGASGA, rm.NIVEL_LISO]
    assert campos["hz-dica"] == [a08.FRASE_DA_CAUSA[rm.CAUSA_LONGE],
                                 a08.DICA_DO_MOVIMENTO[rm.NIVEL_LISO]]


def test_a_tela_le_o_sinal_que_o_servico_publica() -> None:
    controle = {"uniq": "aabbcc000011", "transport": "bt", "adaptador": ADAPTADOR,
                "hz_movimento": 21.0, "sinal_dbm": -53, "connected": True}
    ctx = a08.Contexto(state={"controllers": [controle]}, mesa=[], conectados=[], estados={})
    aparelhos = a08._aparelhos_da_cena(ctx, ctx.state, {}, [], (), {}, [a08._mac(ADAPTADOR)])
    assert [a["sinal"] for a in aparelhos] == [-53]
