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


from hefesto_dualsense4unix.integrations import ar_do_adaptador as ar
from hefesto_dualsense4unix.integrations import radio_da_mesa as rm
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08
from tests.unit.test_o_ar_do_adaptador import _SocketDeMentira
from hefesto_dualsense4unix.interface.pacotes import nome_do_jogador

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


def test_o_servico_pergunta_o_sinal_numa_thread_de_segundo_em_segundo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.unit.test_os_hz_de_cada_controle import _handlers

    handlers = _handlers(monkeypatch)[1]
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
    while handlers._leitor_proprio_do_sinal.em_voo and time.monotonic() < prazo:  # type: ignore[attr-defined]
        time.sleep(0.01)
    assert perguntas == [(2, 12)] and nomes == ["radio-sinal"]
    assert handlers._sinal_dos_enlaces == {"aabbcc000011": -42}  # type: ignore[attr-defined]
    handlers._talvez_ler_o_sinal(ar_do_adaptador)  # type: ignore[attr-defined]
    assert perguntas == [(2, 12)], "o sinal foi perguntado de novo antes do período"


def test_o_state_full_publica_o_sinal_do_controle_no_radio_e_nada_no_cabo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.unit.test_os_hz_de_cada_controle import UNIQ_1, UNIQ_CABO, _handlers

    handlers = _handlers(monkeypatch)[1]
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
    aparelhos = a08._aparelhos_da_cena(ctx, ctx.state, {}, [], (), {},
                                       [nome_do_jogador.mac(ADAPTADOR)])
    assert [a["sinal"] for a in aparelhos] == [-53]


# --- 6. o enlace fraco protege o botão: a ponte do controle longe cede a vez ---------------

LIMIAR = rm.SINAL_QUE_ATRASA_DBM


def test_a_pausa_comeca_na_primeira_leitura_fraca_e_so_acaba_com_folga_e_duas_leituras() -> None:
    # A decisão: D-0810-O-ENLACE-FRACO-PAUSA-A-PONTE-DO-CONTROLE-LONGE.
    pausa = rm.PausaPeloSinal()
    assert pausa.ver(-31, 1.0, 1) is False
    assert pausa.ver(LIMIAR, 2.0, 2) is True, "no limiar que atrasa a ponte já cede"
    assert pausa.ver(-47, 3.0, 3) is True, "passou o limiar mas não a folga: segue pausada"
    boa = LIMIAR + rm.FOLGA_DO_SINAL_DBM + 1
    assert pausa.ver(boa, 4.0, 4) is True, "uma leitura boa não basta"
    assert pausa.ver(-30, 5.0, 5) is False, "duas leituras boas seguidas soltam"


def test_a_leitura_boa_que_o_tique_relê_nao_conta_duas_vezes() -> None:
    """O governador olha a cada 250 ms; a leitura é de 1 s. O número da leitura é quem conta."""
    pausa = rm.PausaPeloSinal()
    pausa.ver(-60, 1.0, 1)
    for tique in range(4):
        assert pausa.ver(-30, 2.0 + tique * 0.25, 2) is True, "a mesma leitura valeu 2 vezes"
    assert pausa.ver(-30, 3.0, 3) is False


def test_uma_leitura_ruim_no_meio_zera_a_volta() -> None:
    pausa = rm.PausaPeloSinal()
    pausa.ver(-60, 1.0, 1)
    pausa.ver(-30, 2.0, 2)
    assert pausa.ver(-60, 3.0, 3) is True
    assert pausa.ver(-30, 4.0, 4) is True, "a contagem de volta recomeçou do zero"
    assert pausa.ver(-30, 5.0, 5) is False


def test_nao_sei_nunca_pausa_e_nao_segura_a_pausa_para_sempre() -> None:
    pausa = rm.PausaPeloSinal()
    assert pausa.ver(None, 1.0, 1) is False, "sem leitura a ponte pausou"
    assert pausa.ver(None, 2.0, 2) is False
    pausa.ver(-60, 3.0, 3)
    assert pausa.ver(None, 4.0, 4) is True, "um segundo sem resposta não prova que voltou"
    assert pausa.ver(None, 3.0 + rm.SEM_SINAL_SOLTA_A_PAUSA_S + 1, 5) is False


class _Controles:
    """O governador de pé com dois controles no mesmo adaptador e o sinal na mão da régua."""

    def __init__(self) -> None:
        from tests.unit.test_o_governador_do_radio import (
            ADAPTADOR_A,
            CONTROLE_1,
            CONTROLE_2,
            _Diario,
            _governador,
            _Kernel,
            _Relogio,
        )

        self.c1, self.c2 = CONTROLE_1, CONTROLE_2
        self.relogio, self.registro = _Relogio(), _Diario()
        kernel = _Kernel()
        dado = kernel.por(0, ADAPTADOR_A)
        dado["enlaces"] = [(12, CONTROLE_1, ar.TIPO_ACL), (13, CONTROLE_2, ar.TIPO_ACL)]
        self.governador = _governador(kernel, self.relogio, self.registro)
        self.sinal = {12: -30, 13: -30}
        self.perguntas: list[tuple[int, int]] = []

        def ler(hci: int, handle: int) -> int | None:
            self.perguntas.append((hci, handle))
            return self.sinal[handle]

        self.leitor = rm.LeitorDoSinal(ler, relogio=self.relogio)
        self.governador.leitor_do_sinal = self.leitor
        self.governador.tique()
        self.vagas = {}
        for uniq in (CONTROLE_1, CONTROLE_2):
            for tipo in ("som", "haptica"):
                vaga = self.governador.pedir_vaga(uniq, tipo)
                assert not hasattr(vaga, "motivo"), "a ponte foi recusada"
                vaga.subiu(tipo)  # type: ignore[union-attr]
                self.vagas[(uniq, tipo)] = vaga

    def um_segundo(self) -> None:
        """Passa um segundo, o leitor pergunta (a thread acaba) e o governador olha."""
        self.relogio.agora += 1.0
        self.leitor.talvez_ler(self.governador.ultima_amostra() or {})
        prazo = time.monotonic() + 2.0
        while self.leitor.em_voo and time.monotonic() < prazo:
            time.sleep(0.002)
        self.governador.tique()

    def cedendo(self, uniq: str, tipo: str) -> bool:
        return bool(self.vagas[(uniq, tipo)].cedendo)  # type: ignore[attr-defined]


def test_o_controle_longe_pausa_o_som_e_a_vibracao_e_o_vizinho_segue() -> None:
    mesa = _Controles()
    mesa.um_segundo()
    assert not any(mesa.cedendo(u, t) for u in (mesa.c1, mesa.c2) for t in ("som", "haptica"))
    mesa.sinal[12] = LIMIAR - 5
    mesa.um_segundo()
    assert mesa.cedendo(mesa.c1, "som") and mesa.cedendo(mesa.c1, "haptica")
    assert not mesa.cedendo(mesa.c2, "som") and not mesa.cedendo(mesa.c2, "haptica"), (
        "o vizinho no mesmo adaptador, perto, pausou junto")
    [borda] = mesa.registro.de(gov_pausada())
    assert borda["controle"] == mesa.c1 and borda["depois"] == {"sinal_dbm": LIMIAR - 5}


def gov_pausada() -> str:
    from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov

    return gov.PAUSADA_PELO_SINAL


def test_o_controle_volta_depois_de_duas_leituras_boas_e_o_diario_so_marca_as_bordas() -> None:
    from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov

    mesa = _Controles()
    mesa.sinal[12] = -60
    mesa.um_segundo()
    mesa.um_segundo()
    assert mesa.cedendo(mesa.c1, "som")
    assert len(mesa.registro.de(gov.PAUSADA_PELO_SINAL)) == 1, "o diário repetiu a borda"
    mesa.sinal[12] = -30
    mesa.um_segundo()
    assert mesa.cedendo(mesa.c1, "som"), "uma leitura boa soltou a pausa"
    mesa.um_segundo()
    assert not mesa.cedendo(mesa.c1, "som") and not mesa.cedendo(mesa.c1, "haptica")
    assert len(mesa.registro.de(gov.VOLTOU_DO_SINAL)) == 1


def test_sem_leitura_do_sinal_a_ponte_nao_pausa() -> None:
    mesa = _Controles()
    mesa.sinal[12] = None  # type: ignore[assignment]
    for _ in range(3):
        mesa.um_segundo()
    assert not mesa.cedendo(mesa.c1, "som")
    assert mesa.registro.de(gov_pausada()) == []


def test_a_pausa_pelo_sinal_nao_entra_na_conta_da_fila_do_adaptador() -> None:
    """``cedendo`` é o que a ponte lê; a fila do governador só vê o que ela mesma mandou ceder."""
    mesa = _Controles()
    mesa.sinal[12] = -60
    mesa.um_segundo()
    vaga = mesa.vagas[(mesa.c1, "som")]
    assert vaga.cedendo is True and vaga._cedendo_pela_fila is False  # type: ignore[attr-defined]
    estado = next(iter(mesa.governador._estados.values()))  # type: ignore[attr-defined]
    assert estado.cedendo is False, "a pausa do sinal virou episódio de fila"


def test_a_ponte_publica_a_pausa_pelo_sinal_por_controle() -> None:
    from tests.unit.test_o_governador_do_radio import ADAPTADOR_A

    mesa = _Controles()
    mesa.sinal[12] = -60
    mesa.um_segundo()
    pontes = mesa.governador.publicar()[ADAPTADOR_A]["pontes"]
    assert {(p["uniq"], p["tipo"]): p["pausada_pelo_sinal"] for p in pontes} == {
        (mesa.c1, "som"): True, (mesa.c1, "vibracao"): True,
        (mesa.c2, "som"): False, (mesa.c2, "vibracao"): False,
    }


def test_a_ponte_que_sobe_com_o_controle_ja_longe_nasce_pausada() -> None:
    mesa = _Controles()
    mesa.sinal[12] = -60
    mesa.um_segundo()
    mesa.vagas[(mesa.c1, "som")].soltar("sem som")  # type: ignore[attr-defined]
    nova = mesa.governador.pedir_vaga(mesa.c1, "som")
    assert nova.cedendo is True, "a ponte nova escreveu antes da próxima leitura"  # type: ignore[union-attr]


def test_o_controle_pelo_cabo_nunca_pausa_porque_nao_tem_sinal() -> None:
    mesa = _Controles()
    mesa.sinal[12] = -80
    mesa.um_segundo()
    assert mesa.leitor.sinais().get("aabbcc000099") is None
    mesa.vagas[(mesa.c2, "som")].soltar("sem som")  # type: ignore[attr-defined]
    cabo = mesa.governador.pedir_vaga("aa:bb:cc:00:00:99", "som")
    assert cabo.cedendo is False  # type: ignore[union-attr]


def test_um_leitor_so_pergunta_uma_vez_por_segundo_por_enlace() -> None:
    """O governador e o ``state_full`` dividem o leitor: não dobram a pergunta."""
    mesa = _Controles()
    mesa.um_segundo()
    antes = len(mesa.perguntas)
    for _ in range(4):
        mesa.leitor.talvez_ler(mesa.governador.ultima_amostra() or {})
        mesa.governador.tique()
    assert len(mesa.perguntas) == antes, "perguntou de novo antes do período"
    assert antes == 2, "uma pergunta por enlace"


def test_o_leitor_do_servico_e_o_do_governador_quando_ele_existe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.unit.test_os_hz_de_cada_controle import _handlers

    handlers = _handlers(monkeypatch)[1]
    leitor = rm.LeitorDoSinal(lambda _hci, _handle: -42)
    handlers._o_governador = lambda: type("G", (), {"leitor_do_sinal": leitor})()  # type: ignore[attr-defined]
    handlers._ler_sinal = None  # type: ignore[attr-defined]
    ar_do_adaptador = {ADAPTADOR: _leitura(ar.Enlace(12, APARELHO_A, ar.TIPO_ACL, True, 1, 7))}
    handlers._talvez_ler_o_sinal(ar_do_adaptador)  # type: ignore[attr-defined]
    prazo = time.monotonic() + 2.0
    while leitor.em_voo and time.monotonic() < prazo:
        time.sleep(0.002)
    assert leitor.sinais() == {"aabbcc000011": -42}
    assert handlers._leitor_proprio_do_sinal is None, "o serviço abriu um segundo leitor"  # type: ignore[attr-defined]


def test_a_bomba_de_verdade_cala_com_o_controle_longe_e_volta_a_escrever_perto() -> None:
    """A régua do governador lê ``vaga.cedendo``; quem cala é a bomba que o lê. Esta é a ponta."""
    from tests.unit.test_o_governador_do_radio import _bomba

    mesa = _Controles()
    mesa.um_segundo()
    escritos: list[bytes] = []

    def escritor(report: bytes) -> int:
        escritos.append(report)
        return len(report)

    bomba = _bomba(mesa.vagas[(mesa.c1, "som")], mesa.relogio, escritor)
    quadro = b"\x35" + b"\x00" * 333
    mesa.sinal[12] = LIMIAR - 5
    mesa.um_segundo()
    for _ in range(10):
        assert bomba.escrever(quadro) is True, "a bomba tratou a pausa como queda"
    assert escritos == [], "a bomba escreveu no rádio com o controle longe"
    assert bomba.contagem.quadros_cedidos_ao_governador == 10
    mesa.sinal[12] = -30
    mesa.um_segundo()
    mesa.um_segundo()
    bomba.escrever(quadro)
    assert escritos == [quadro], "o controle voltou e a bomba seguiu calada"


def test_a_dica_da_linha_diz_que_a_ponte_esta_pausada_e_nao_por_causa_do_hz(
    tela_limpa: list[float],
) -> None:
    tela_limpa[0] += 1.0
    nivel, dica = _nivel_e_dica(_cena({"a": {"hz_mov": 21.0, "sinal": -53, "ponte_pausada": True}}))
    assert nivel == rm.NIVEL_ENGASGA
    assert dica == a08.FRASE_DA_CAUSA[rm.CAUSA_LONGE_PAUSADA]
    assert "pausados" in dica and "mesa" not in dica.lower()
    tela_limpa[0] += 1.0
    _, dica = _nivel_e_dica(_cena({"a": {"hz_mov": 21.0, "sinal": -53, "ponte_pausada": False}}))
    assert dica == a08.FRASE_DA_CAUSA[rm.CAUSA_LONGE]


def test_a_tela_le_a_pausa_que_o_governador_publica() -> None:
    controle = {"uniq": "aabbcc000011", "transport": "bt", "adaptador": ADAPTADOR,
                "hz_movimento": 21.0, "sinal_dbm": -53, "connected": True}
    ctx = a08.Contexto(state={"controllers": [controle]}, mesa=[], conectados=[], estados={})
    governador = {ADAPTADOR: {"pontes": [{"uniq": APARELHO_A, "tipo": "som",
                                           "alem_do_limite": False, "pausada_pelo_sinal": True}]}}
    aparelhos = a08._aparelhos_da_cena(ctx, ctx.state, governador, [], (), {},
                                       [nome_do_jogador.mac(ADAPTADOR)])
    assert [a["ponte_pausada"] for a in aparelhos] == [True]


# --- 7. o «Equilibrar» lê o sinal: o fraco vai para onde um outro adaptador o ouve melhor ---

SALA = "aa:bb:cc:00:00:a1"
QUARTO = "aa:bb:cc:00:00:b2"
FRACO, FORTE, OUTRO, ULTIMO = (f"aabbcc0000{n:02x}" for n in (1, 2, 3, 4))


def _controle(uniq: str, sinal: int | None, ponte: str | None = "som") -> rm.ControleNoAr:
    return rm.ControleNoAr(uniq=uniq, ponte=ponte, sinal_dbm=sinal)


def _plano(endereco: str, controles: tuple[rm.ControleNoAr, ...], n_max: int = 2) -> Any:
    from hefesto_dualsense4unix.integrations import plano_de_radio as plano

    return plano.PlanoDoAdaptador(
        endereco=endereco, apelido="Sala" if endereco == SALA else "Quarto",
        orcamento=rm.OrcamentoDoAdaptador(adaptador=endereco, controles=controles, n_max=n_max))


def _mesa(a: tuple[rm.ControleNoAr, ...], b: tuple[rm.ControleNoAr, ...], **kw: int) -> Any:
    return {SALA: _plano(SALA, a, **kw), QUARTO: _plano(QUARTO, b, **kw)}


def _ordem(planos: Any, ouvidos: Any = None) -> Any:
    from hefesto_dualsense4unix.integrations import plano_de_radio as plano

    return plano.ordem_de_redistribuicao(planos, ouvidos=ouvidos)


def _mesa_equilibrada() -> Any:
    """Dois na Sala e um no Quarto: pela contagem (diferença 1) ninguém se move."""
    return _mesa((_controle(FRACO, -55), _controle(FORTE, -30)), (_controle(OUTRO, -30),))


def test_sem_ninguem_que_ouca_o_fraco_a_conta_por_contagem_segue_como_era() -> None:
    assert _ordem(_mesa_equilibrada()) is None
    assert _ordem(_mesa_equilibrada(), {}) is None
    assert _ordem(_mesa_equilibrada(), {FRACO: {}}) is None
    desequilibrada = _mesa((_controle(FRACO, -55, None), _controle(FORTE, -30, None),
                            _controle(ULTIMO, -30, None)), ())
    antes = _ordem(desequilibrada)
    assert antes is not None and antes.controle == ULTIMO, "a regra antiga move o último a chegar"
    assert _ordem(desequilibrada, {FRACO: {}}) == antes, "ouvidos vazios mudaram a conta"


def test_o_fraco_que_o_outro_adaptador_ouve_bem_melhor_e_o_que_se_propoe_mover() -> None:
    # A decisão: D-0810-O-EQUILIBRAR-MOVE-O-FRACO-PELO-SINAL.
    ordem = _ordem(_mesa_equilibrada(), {FRACO: {QUARTO.replace(":", ""): -40}})
    assert ordem is not None
    assert (ordem.controle, ordem.origem, ordem.destino, ordem.modo) == (
        FRACO, SALA, QUARTO, "som")
    assert (ordem.pontes_na_origem_depois, ordem.pontes_no_destino_depois) == (1, 2)
    assert "-55" in ordem.o_que_eu_vi and "-40" in ordem.o_que_eu_vi


def test_a_melhora_pequena_e_ruido_e_nao_move() -> None:
    """O fraco está a -55: 7 dB de melhora é ruído entre duas leituras; 8 dB já compensa."""
    quarto = QUARTO.replace(":", "")
    assert _ordem(_mesa_equilibrada(), {FRACO: {quarto: -48}}) is None
    assert _ordem(_mesa_equilibrada(), {FRACO: {quarto: -47}}) is not None


def test_o_controle_de_sinal_bom_nao_se_move_por_mais_que_o_outro_o_ouca() -> None:
    assert _ordem(_mesa_equilibrada(), {FORTE: {QUARTO.replace(":", ""): -10}}) is None


def test_sinal_que_o_radio_nao_leu_nunca_e_fraco() -> None:
    mesa = _mesa((_controle(FRACO, None), _controle(FORTE, -30)), (_controle(OUTRO, -30),))
    assert _ordem(mesa, {FRACO: {QUARTO.replace(":", ""): -10}}) is None


def test_o_destino_sem_vaga_de_ponte_nao_recebe_o_fraco() -> None:
    cheio = _mesa((_controle(FRACO, -55), _controle(FORTE, -30)),
                  (_controle(OUTRO, -30), _controle(ULTIMO, -30)))
    assert _ordem(cheio, {FRACO: {QUARTO.replace(":", ""): -40}}) is None
    sem_ponte = _mesa((_controle(FRACO, -55, None), _controle(FORTE, -30)),
                      (_controle(OUTRO, -30), _controle(ULTIMO, -30)))
    ordem = _ordem(sem_ponte, {FRACO: {QUARTO.replace(":", ""): -40}})
    assert ordem is not None and ordem.modo == "", "o controle sem ponte não ocupa vaga de ponte"


def test_com_dois_fracos_vai_o_mais_fraco() -> None:
    mesa = _mesa((_controle(FRACO, -55), _controle(FORTE, -62)), (_controle(OUTRO, -30),))
    ordem = _ordem(mesa, {FRACO: {QUARTO.replace(":", ""): -30},
                          FORTE: {QUARTO.replace(":", ""): -35}})
    assert ordem is not None and ordem.controle == FORTE


def test_o_adaptador_que_ouve_o_controle_e_o_que_ele_ja_esta_nao_e_destino() -> None:
    folgado = _mesa_equilibrada()
    folgado = {e: _plano(e, p.orcamento.controles, n_max=4) for e, p in folgado.items()}
    assert _ordem(folgado, {FRACO: {SALA.replace(":", ""): -20}}) is None


def test_na_sobra_de_pontes_o_fraco_que_o_outro_ouve_melhor_sai_no_lugar_do_ultimo() -> None:
    sobra = _mesa((_controle(FRACO, -55), _controle(FORTE, -30), _controle(ULTIMO, -30)), ())
    antes = _ordem(sobra)
    assert antes is not None and antes.controle == ULTIMO
    depois = _ordem(sobra, {FRACO: {QUARTO.replace(":", ""): -38}})
    assert depois is not None and (depois.controle, depois.destino) == (FRACO, QUARTO)


def test_a_central_monta_o_que_cada_adaptador_ouve_do_dono_vivo_sem_perguntar() -> None:
    from types import SimpleNamespace

    from hefesto_dualsense4unix.integrations import central_do_radio as cr
    from tests.unit.test_o_controle_que_pede_para_parear_aparece import _adaptadores, _objeto

    ctrl = "aa:bb:cc:00:00:01"
    aparelhos = [
        _objeto(SALA, ctrl, pareado=True, conectado=True),
        _objeto(QUARTO, ctrl, pareado=False, rssi=-41),
    ]
    dono = SimpleNamespace(
        pode_perguntar=lambda: True, atende_o_proprio_pareamento=True,
        adaptadores=lambda: _adaptadores(), aparelhos=lambda: aparelhos)
    central = cr.CentralDoRadio(dono=dono)  # type: ignore[arg-type]
    central._dono_visto = dono  # type: ignore[assignment]
    assert central._ouvidos_publicados() == {"aabbcc000001": {QUARTO.replace(":", ""): -41}}
    central._dono_visto = None
    assert central._ouvidos_publicados() == {}, "sem dono vivo a central abriu o D-Bus"


def test_o_equilibrar_da_central_propoe_pelo_sinal_que_o_dono_ouviu() -> None:
    from types import SimpleNamespace

    from hefesto_dualsense4unix.integrations import central_do_radio as cr
    from tests.unit.test_o_controle_que_pede_para_parear_aparece import _adaptadores, _objeto

    ctrl = "aa:bb:cc:00:00:01"
    aparelhos = [_objeto(SALA, ctrl, pareado=True, conectado=True),
                 _objeto(QUARTO, ctrl, rssi=-40)]
    dono = SimpleNamespace(
        pode_perguntar=lambda: True, atende_o_proprio_pareamento=True,
        adaptadores=lambda: _adaptadores(), aparelhos=lambda: aparelhos)
    central = cr.CentralDoRadio(dono=dono)  # type: ignore[arg-type]
    central._dono_visto = dono  # type: ignore[assignment]
    central._planos = lambda ar=None, *, esperar=True: (_mesa_equilibrada(), frozenset())  # type: ignore[method-assign]
    ordem = central.propor(esperar=False)
    assert ordem is not None and (ordem.controle, ordem.destino) == (FRACO, QUARTO)
    central._dono_visto = None
    assert central.propor(esperar=False) is None, "sem leitura do ar a proposta é a de contagem"


def test_o_sinal_que_o_state_full_publica_chega_ao_equilibrar_sem_dubles_no_meio() -> None:
    """A central pesa o ``state["controllers"]`` depois do ``_merge_radio``: o ``sinal_dbm`` de
    cada controle passa pelo ``plano_por_adaptador`` até a conta do «Equilibrar»."""
    from hefesto_dualsense4unix.integrations import plano_de_radio as plano

    def entrada(uniq: str, adaptador: str, sinal: int | None, slot: int) -> dict[str, Any]:
        return {"uniq": uniq, "transport": "bt", "connected": True, "adaptador": adaptador,
                "ponte_do_radio": "som", "sinal_dbm": sinal, "player_slot": slot}

    controles = [entrada(FRACO, SALA, -55, 1), entrada(FORTE, SALA, -30, 2),
                 entrada(OUTRO, QUARTO, -30, 3)]
    planos = plano.plano_por_adaptador(controles, adaptadores=[SALA, QUARTO],
                                       listar=lambda _raiz: [])
    ouvidos = {FRACO: {QUARTO.replace(":", ""): -40}}
    ordem = plano.ordem_de_redistribuicao(planos, ouvidos=ouvidos)
    assert ordem is not None and (ordem.controle, ordem.destino) == (FRACO, QUARTO)
    controles[0]["sinal_dbm"] = None
    planos = plano.plano_por_adaptador(controles, adaptadores=[SALA, QUARTO],
                                       listar=lambda _raiz: [])
    assert plano.ordem_de_redistribuicao(planos, ouvidos=ouvidos) is None
