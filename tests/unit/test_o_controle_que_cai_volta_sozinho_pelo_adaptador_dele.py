"""O-CONTROLE-QUE-CAI-VOLTA-SOZINHO-PELO-ADAPTADOR-DELE-01 — as réguas.

O controle pareado e confiável que está fora é chamado de volta pela faxina da central, pelo
adaptador do vínculo, com recuo, um ``Connect`` por vez. Nenhuma chave muda.
MORDIDAS: ``caminhos_para_conectar`` sem filtro reprova o vínculo em dois adaptadores; tirar a
junção de ``dualsenses_do_radio`` reprova as duas linhas; tirar o ``self.religar()`` da faxina
reprova o daemon que sobe.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import central_do_radio as cr
from hefesto_dualsense4unix.integrations import diario_do_radio
from hefesto_dualsense4unix.integrations import gesto_de_pareamento as gp
from hefesto_dualsense4unix.integrations import gesto_de_reconexao as gr
from hefesto_dualsense4unix.interface.pacotes import perfil
from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import AZUL, QUARTO, ROXO, SALA, VARANDA, VERDE, VERMELHO

_DORMINDO = bd.Escrita(False, "org.bluez.Error.Failed", "br-connection-page-timeout")
_CHAVE_VELHA = bd.Escrita(False, "org.bluez.Error.AuthenticationFailed", "Authentication Failed")
_NA_ORDEM_DE_P1_A_P4 = (VERMELHO, AZUL, VERDE, ROXO)


class _Radio(rm.RadioDeMentira):
    """O rádio de mentira com a resposta do ``Connect`` de quem dorme e da chave velha."""

    def __init__(self, **k: Any) -> None:
        super().__init__(**k)
        self.dormindo: set[str] = set()
        self.chave_velha: set[str] = set()
        self.no_connect: list[bool] = []

    def _no_aparelho(self, caminho: str, metodo: str) -> bd.Escrita:
        aparelho = bd.endereco_do_aparelho(caminho) or ""
        if metodo == "Connect":
            self.no_connect.append(bd.a_trava_esta_tomada())
            for grupo, resposta in ((self.dormindo, _DORMINDO), (self.chave_velha, _CHAVE_VELHA)):
                if aparelho in grupo:
                    self.linha_do_tempo.append(
                        ("Connect", self._endereco_do_hci(caminho.rsplit("/", 1)[0]), aparelho))
                    return resposta
        return super()._no_aparelho(caminho, metodo)

    def connects(self) -> list[tuple[str, str]]:
        return [(onde, quem) for tipo, onde, quem in self.linha_do_tempo if tipo == "Connect"]


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(tmp_path / "radio.lock"))
    caminho = tmp_path / "radio-diario.jsonl"
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(caminho))
    return caminho


@pytest.fixture()
def mundo() -> _Radio:
    return _Radio()


@pytest.fixture()
def relogio() -> rm.Relogio:
    return rm.Relogio()


@pytest.fixture()
def dono(mundo: _Radio) -> Iterator[bd.DonoVivo]:
    vivo = bd.DonoVivo(mundo)
    yield vivo
    vivo.fechar()


@pytest.fixture()
def no_cabo() -> set[str]:
    return set()


def _central(
    dono: bd.DonoVivo, mundo: _Radio, relogio: rm.Relogio, no_cabo: set[str] | None = None,
) -> cr.CentralDoRadio:
    assert dono.ligar()
    cabo = no_cabo if no_cabo is not None else set()
    return cr.CentralDoRadio(
        dono=dono, onde_esta=mundo.onde_esta, movimento=mundo.hz,
        no_kernel=lambda aparelho: aparelho in cabo, relogio=relogio, dormir=relogio.dormir,
        sysfs={"listar": lambda _p: [], "raiz": "/nao/existe"})


def _andar(central: cr.CentralDoRadio, relogio: rm.Relogio, segundos: int) -> list[float]:
    """Uma volta por segundo: os segundos em que a volta chamou alguém, desde o gatilho."""
    central.religar()
    inicio = relogio.agora
    chamou: list[float] = []
    for _ in range(segundos):
        relogio.dormir(1.0)
        if central.religar() is not None:
            chamou.append(relogio.agora - inicio)
    return chamou


def _no(adaptador: str, aparelho: str) -> str:
    return rm.no_de(adaptador, aparelho)


@pytest.mark.parametrize("onde_ele_mora,sobra", [(SALA, QUARTO), (QUARTO, SALA)])
def test_o_vinculo_em_dois_adaptadores_conecta_no_segundo_se_o_primeiro_falha(
    diario: Path, mundo: _Radio, dono: bd.DonoVivo, relogio: rm.Relogio,
    onde_ele_mora: str, sobra: str,
) -> None:
    mundo.pareado(sobra, VERMELHO, conectado=False, host=False)
    mundo.pareado(onde_ele_mora, VERMELHO, conectado=False)
    central = _central(dono, mundo, relogio)
    central.pedir_o_religador()

    _andar(central, relogio, 6)

    assert mundo.onde_esta(rm.uniq(VERMELHO)) == onde_ele_mora
    assert mundo.connects()[-1] == (onde_ele_mora, VERMELHO)
    assert len(mundo.connects()) == len(set(mundo.connects())), "dois Connect no mesmo hci"


def test_o_adaptador_em_que_ele_estava_no_ar_vem_primeiro(
    diario: Path, mundo: _Radio, dono: bd.DonoVivo, relogio: rm.Relogio,
) -> None:
    mundo.pareado(SALA, VERMELHO, conectado=False, host=False)
    mundo.pareado(QUARTO, VERMELHO, conectado=True)
    central = _central(dono, mundo, relogio)
    central._onde_caiu[VERMELHO] = QUARTO
    mundo.dormindo.add(VERMELHO)
    mundo.desligar(VERMELHO)

    _andar(central, relogio, 6)

    assert [onde for onde, _ in mundo.connects()] == [QUARTO, SALA]


def test_quem_nao_esta_pareado_ali_nunca_e_chamado_ali(
    diario: Path, mundo: _Radio, dono: bd.DonoVivo, relogio: rm.Relogio,
) -> None:
    mundo.pareado(SALA, VERMELHO, conectado=False, host=False)
    mundo.pareado(QUARTO, VERMELHO, conectado=False)
    mundo.mesa[_no(SALA, VERMELHO)][bd.APARELHO]["Paired"] = False
    central = _central(dono, mundo, relogio)
    central.pedir_o_religador()

    _andar(central, relogio, 6)

    assert mundo.connects() == [(QUARTO, VERMELHO)]


def test_adaptador_desligado_nao_e_candidato(
    diario: Path, mundo: _Radio, dono: bd.DonoVivo,
) -> None:
    mundo.pareado(SALA, VERMELHO, conectado=False, host=False)
    mundo.pareado(QUARTO, VERMELHO, conectado=False)
    mundo.mesa[rm.HCIS[SALA]][bd.ADAPTADOR]["Powered"] = False
    assert dono.ligar()

    assert dono.caminhos_para_conectar(VERMELHO) == (_no(QUARTO, VERMELHO),)


def test_dois_adaptadores_com_o_mesmo_endereco_dao_uma_tentativa_em_cada_hci(
    diario: Path, mundo: _Radio, dono: bd.DonoVivo, relogio: rm.Relogio,
) -> None:
    """Clones com o mesmo endereço: o caminho é o nó, nunca o endereço do adaptador."""
    gemeo = "/org/bluez/hci5"
    mundo.mesa[gemeo] = {bd.ADAPTADOR: dict(mundo.mesa[rm.HCIS[SALA]][bd.ADAPTADOR])}
    mundo.pareado(SALA, VERMELHO, conectado=False, host=False)
    no_do_gemeo = f"{gemeo}/dev_{VERMELHO.replace(':', '_').upper()}"
    mundo.mesa[no_do_gemeo] = {bd.APARELHO: dict(mundo.mesa[_no(SALA, VERMELHO)][bd.APARELHO])}
    assert dono.ligar()

    assert sorted(dono.caminhos_para_conectar(VERMELHO) or ()) == sorted(
        [no_do_gemeo, _no(SALA, VERMELHO)])


def test_no_tempo_o_recuo_vai_ate_a_janela_e_o_segundo_gatilho_reabre(
    diario: Path, mundo: _Radio, dono: bd.DonoVivo, relogio: rm.Relogio,
) -> None:
    mundo.pareado(SALA, VERMELHO, conectado=False)
    mundo.dormindo.add(VERMELHO)
    central = _central(dono, mundo, relogio)
    central.pedir_o_religador()

    chamou = _andar(central, relogio, 720)

    assert chamou == [5.0, 20.0, 65.0, 185.0, 305.0, 425.0, 545.0]
    assert not central._chamadas, "a janela não fechou"

    central.pedir_o_religador()
    assert _andar(central, relogio, 21) == [5.0, 20.0]


@pytest.mark.parametrize("onde", ["mesa", "cabo", "bluez", "nao_sei"])
def test_quem_esta_no_ar_ou_no_cabo_nao_recebe_connect(
    diario: Path, mundo: _Radio, dono: bd.DonoVivo, relogio: rm.Relogio, no_cabo: set[str],
    onde: str,
) -> None:
    mundo.pareado(SALA, VERMELHO, conectado=onde == "bluez")
    central = _central(dono, mundo, relogio, no_cabo)
    if onde == "mesa":
        central.conhecer([{"uniq": rm.uniq(VERMELHO), "jogador": 2}])
    elif onde == "cabo":
        no_cabo.add(VERMELHO)
    elif onde == "nao_sei":
        central._no_kernel = lambda _a: None
    central.pedir_o_religador()

    _andar(central, relogio, 70)

    assert mundo.connects() == []


@pytest.mark.parametrize("razao,gesto,chama", [
    (bd.RAZAO_TIMEOUT, False, True),
    ("", False, True),
    (bd.RAZAO_DO_CONTROLE, False, False),
    (bd.RAZAO_DAQUI, False, False),
    (bd.RAZAO_TIMEOUT, True, False),
])
def test_a_queda_chama_de_volta_e_o_gesto_nao(
    diario: Path, mundo: _Radio, dono: bd.DonoVivo, relogio: rm.Relogio,
    monkeypatch: pytest.MonkeyPatch, razao: str, gesto: bool, chama: bool,
) -> None:
    mundo.pareado(SALA, VERMELHO, conectado=True)
    central = _central(dono, mundo, relogio)
    if gesto:
        monkeypatch.setattr(dono._vaga, "tomar", lambda _a: True)
    if razao:
        mundo._emitir(bd.Sinal("desconectou", caminho=_no(SALA, VERMELHO), razao=razao))
    mundo.desligar(VERMELHO)

    _andar(central, relogio, 6)

    assert mundo.connects() == ([(SALA, VERMELHO)] if chama else [])
    assert (mundo.onde_esta(rm.uniq(VERMELHO)) == SALA) is chama


def test_a_queda_logo_depois_do_aviso_nao_se_perde_com_o_kernel_atrasado(
    diario: Path, mundo: _Radio, dono: bd.DonoVivo, relogio: rm.Relogio, no_cabo: set[str],
) -> None:
    """O ``hidraw`` sai depois do ``Connected`` no BlueZ: a janela abre do mesmo jeito."""
    mundo.pareado(SALA, VERMELHO, conectado=True)
    central = _central(dono, mundo, relogio, no_cabo)
    no_cabo.add(VERMELHO)
    mundo.desligar(VERMELHO)
    central.religar()
    no_cabo.clear()

    _andar(central, relogio, 6)

    assert mundo.connects() == [(SALA, VERMELHO)]


def test_o_adaptador_que_volta_reabre_a_janela(
    diario: Path, mundo: _Radio, dono: bd.DonoVivo, relogio: rm.Relogio,
) -> None:
    mundo.pareado(SALA, VERMELHO, conectado=False)
    central = _central(dono, mundo, relogio)
    mundo.dormindo.add(VERMELHO)
    central.religar()
    assert _andar(central, relogio, 10) == []

    mundo._mudar(rm.HCIS[QUARTO], bd.ADAPTADOR, "Powered", False)
    central.religar()
    mundo._mudar(rm.HCIS[QUARTO], bd.ADAPTADOR, "Powered", True)

    assert _andar(central, relogio, 6) == [5.0]


def test_o_bluetoothd_que_reinicia_reabre_a_janela(
    diario: Path, mundo: _Radio, dono: bd.DonoVivo, relogio: rm.Relogio,
) -> None:
    mundo.pareado(SALA, VERMELHO, conectado=False)
    central = _central(dono, mundo, relogio)
    mundo.dormindo.add(VERMELHO)
    central.religar()

    mundo.reiniciar_o_bluetoothd()

    assert _andar(central, relogio, 6) == [5.0]


def test_o_daemon_que_sobe_chama_pela_faxina(
    diario: Path, mundo: _Radio, dono: bd.DonoVivo, relogio: rm.Relogio,
) -> None:
    mundo.pareado(SALA, VERMELHO, conectado=False)
    central = _central(dono, mundo, relogio)
    central.comecar_a_faxina(60.0, passo_s=0.01)
    try:
        prazo = time.monotonic() + 5.0
        while not mundo.connects() and time.monotonic() < prazo:
            relogio.agora += 1.0
            time.sleep(0.02)
    finally:
        central.fechar()

    assert mundo.connects() == [(SALA, VERMELHO)]
    assert mundo.onde_esta(rm.uniq(VERMELHO)) == SALA


def test_a_chave_velha_para_e_fica_no_diario_com_o_texto_do_bluez(
    diario: Path, mundo: _Radio, dono: bd.DonoVivo, relogio: rm.Relogio,
) -> None:
    mundo.pareado(SALA, VERMELHO, conectado=False)
    mundo.chave_velha.add(VERMELHO)
    central = _central(dono, mundo, relogio)
    central.pedir_o_religador()

    assert _andar(central, relogio, 70) == [5.0]
    assert not central._chamadas

    linhas = [e for e in diario_do_radio.ler(caminhos=[diario]) if e.get("chamada") == "Connect"]
    assert len(linhas) == 1
    assert linhas[0]["quem"] == cr.QUEM
    assert linhas[0]["depois"] == {
        "feita": False, "erro": _CHAVE_VELHA.erro, "mensagem": _CHAVE_VELHA.mensagem,
        "motivo": bd.MOTIVO_CHAVE_VELHA}


def test_dormindo_num_e_chave_velha_no_outro_segue_chamando(
    diario: Path, mundo: _Radio, dono: bd.DonoVivo, relogio: rm.Relogio, monkeypatch: Any,
) -> None:
    mundo.pareado(SALA, VERMELHO, conectado=False)
    mundo.pareado(QUARTO, VERMELHO, conectado=False, host=False)
    respostas = iter([_DORMINDO, _CHAVE_VELHA] * 8)
    monkeypatch.setattr(dono, "conectar", lambda *_a, **_k: next(respostas))
    central = _central(dono, mundo, relogio)
    central.pedir_o_religador()

    assert _andar(central, relogio, 21) == [5.0, 20.0]


def test_o_connect_vai_sob_a_trava_comum(
    diario: Path, mundo: _Radio, dono: bd.DonoVivo, relogio: rm.Relogio,
) -> None:
    mundo.pareado(SALA, VERMELHO, conectado=False)
    central = _central(dono, mundo, relogio)
    central.pedir_o_religador()

    _andar(central, relogio, 6)

    assert mundo.no_connect == [True]


def test_com_a_trava_ocupada_a_tentativa_espera_a_vez(
    diario: Path, mundo: _Radio, dono: bd.DonoVivo, relogio: rm.Relogio,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mundo.pareado(SALA, VERMELHO, conectado=False)
    central = _central(dono, mundo, relogio)
    central.pedir_o_religador()
    monkeypatch.setattr(cr, "ESPERA_DA_TRAVA_DO_RELIGADOR_S", 0.01)
    solta, pegou = threading.Event(), threading.Event()

    def outro_gesto() -> None:
        with diario_do_radio.trava_do_radio("outro", prazo_s=1.0):
            pegou.set()
            solta.wait(5.0)

    fio = threading.Thread(target=outro_gesto)
    fio.start()
    pegou.wait(5.0)
    try:
        assert _andar(central, relogio, 6) == []
        assert mundo.connects() == []
        assert central._chamadas[VERMELHO].passo == 0
    finally:
        solta.set()
        fio.join(5.0)

    assert central.religar() == VERMELHO
    assert mundo.connects() == [(SALA, VERMELHO)]


def test_com_a_busca_aberta_o_religador_espera(
    diario: Path, mundo: _Radio, dono: bd.DonoVivo, relogio: rm.Relogio,
) -> None:
    mundo.pareado(SALA, VERMELHO, conectado=False)
    central = _central(dono, mundo, relogio)
    central.pedir_o_religador()
    central._janela_da_busca = object()  # type: ignore[assignment]

    assert _andar(central, relogio, 6) == []


_MESAS = {
    "3 cabos e 1 rádio": (("cabo", "cabo", "cabo", "radio"), SALA),
    "1 cabo e 3 rádios": (("radio", "cabo", "radio", "radio"), QUARTO),
    "2 e 2": (("cabo", "radio", "radio", "cabo"), VARANDA),
    "4 rádios": (("radio", "radio", "radio", "radio"), SALA),
}


@pytest.mark.parametrize("mesa", _MESAS)
def test_os_quatro_juntos_um_connect_por_volta_e_so_quem_esta_no_radio(
    diario: Path, mundo: _Radio, dono: bd.DonoVivo, relogio: rm.Relogio, no_cabo: set[str],
    mesa: str,
) -> None:
    transportes, adaptador = _MESAS[mesa]
    pelo_radio = []
    for aparelho, transporte in zip(_NA_ORDEM_DE_P1_A_P4, transportes, strict=True):
        mundo.pareado(adaptador, aparelho, conectado=False)
        if transporte == "cabo":
            no_cabo.add(aparelho)
        else:
            pelo_radio.append(aparelho)
    central = _central(dono, mundo, relogio, no_cabo)
    central.pedir_o_religador()

    voltas = []
    for _ in range(12):
        relogio.dormir(1.0)
        antes = len(mundo.connects())
        central.religar()
        voltas.append(len(mundo.connects()) - antes)

    assert max(voltas) == 1, voltas
    assert sorted(quem for _, quem in mundo.connects()) == sorted(pelo_radio)
    for aparelho in pelo_radio:
        assert mundo.onde_esta(rm.uniq(aparelho)) == adaptador


def test_so_o_p3_de_pe_e_a_ordem_de_chegada_nao_conta(
    diario: Path, mundo: _Radio, dono: bd.DonoVivo, relogio: rm.Relogio,
) -> None:
    mundo.pareado(SALA, VERDE, conectado=True)
    mundo.pareado(QUARTO, VERMELHO, conectado=False)
    central = _central(dono, mundo, relogio)
    central.pedir_o_religador()
    mundo.dormindo.add(VERMELHO)

    _andar(central, relogio, 6)

    assert mundo.connects() == [(QUARTO, VERMELHO)]


class TestOGestoDeReconectar:
    @pytest.fixture(autouse=True)
    def _sem_kernel(
        self, diario: Path, dono: bd.DonoVivo, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(gr, "tem_hid_no_kernel", lambda _m: False)
        monkeypatch.setattr(bd, "dono", lambda: dono)

    def test_a_lista_traz_cada_controle_uma_vez(self, mundo: _Radio, dono: bd.DonoVivo) -> None:
        mundo.pareado(SALA, VERMELHO, conectado=False, host=False)
        mundo.pareado(QUARTO, VERMELHO, conectado=True)
        mundo.pareado(SALA, AZUL, conectado=False)
        assert dono.ligar()

        assert sorted(gr.dualsenses_do_radio()) == [(VERMELHO, True), (AZUL, False)]

    def test_quem_nao_respondeu_nao_vira_fora(self) -> None:
        assert gr._juntar_o_conectado(False, None) is None
        assert gr._juntar_o_conectado(None, True) is True
        assert gr._juntar_o_conectado(False, False) is False

    def test_o_gesto_acha_o_adaptador_certo(self, mundo: _Radio, dono: bd.DonoVivo) -> None:
        mundo.pareado(SALA, VERMELHO, conectado=False, host=False)
        mundo.pareado(QUARTO, VERMELHO, conectado=False)
        assert dono.ligar()

        assert gr.reconectar(VERMELHO).estado == gr.ESTADO_VOLTOU
        assert mundo.onde_esta(rm.uniq(VERMELHO)) == QUARTO

    def test_o_gesto_nao_chama_quem_nao_esta_pareado_em_lugar_nenhum(
        self, mundo: _Radio, dono: bd.DonoVivo,
    ) -> None:
        mundo.pareado(SALA, VERMELHO, conectado=False)
        mundo.mesa[_no(SALA, VERMELHO)][bd.APARELHO]["Paired"] = False
        assert dono.ligar()

        assert gr.reconectar(VERMELHO).estado == gr.ESTADO_SEM_ALVO
        assert mundo.connects() == []

    def test_o_elo_morto_cai_no_no_conectado(self, mundo: _Radio, dono: bd.DonoVivo) -> None:
        mundo.pareado(SALA, VERMELHO, conectado=False, host=False)
        mundo.pareado(QUARTO, VERMELHO, conectado=True)
        assert dono.ligar()

        assert gr.caminho_do_controle(VERMELHO) == _no(QUARTO, VERMELHO)
        assert gr.esta_conectado(VERMELHO) is True
        assert gr.reconectar(VERMELHO).estado == gr.ESTADO_VOLTOU
        assert mundo.metodos("Disconnect")[0][0] == _no(QUARTO, VERMELHO)

    def test_o_motivo_vai_ao_diario_de_quem_reconecta(
        self, diario: Path, mundo: _Radio, dono: bd.DonoVivo,
    ) -> None:
        mundo.pareado(SALA, VERMELHO, conectado=False)
        mundo.dormindo.add(VERMELHO)
        assert dono.ligar()

        assert gr.reconectar(VERMELHO).estado == gr.ESTADO_SO_O_PS

        linha = [e for e in diario_do_radio.ler(caminhos=[diario])
                 if e.get("chamada") == "Connect"][-1]
        assert linha["quem"] == gr.QUEM
        assert linha["depois"]["mensagem"] == _DORMINDO.mensagem
        assert linha["depois"]["motivo"] == bd.MOTIVO_DORMINDO


def test_o_radio_de_volta_nao_tenta_o_mesmo_controle_duas_vezes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamados: list[str] = []

    def reconectar(mac: str, **_k: Any) -> gr.Resultado:
        chamados.append(mac)
        return gr.Resultado(gr.ESTADO_VOLTOU, gr.FRASE_VOLTOU, mac)

    monkeypatch.setattr(gr, "dualsenses_do_radio", lambda **_k: [
        (VERMELHO, False), (VERMELHO, False), (AZUL, False)])
    monkeypatch.setattr(gr, "reconectar", reconectar)

    class Ctx:
        mesa: list[dict[str, str]] = []  # noqa: RUF012

    assert perfil.o_radio_de_volta(Ctx()) == (2, 0)
    assert chamados == [VERMELHO, AZUL]


@pytest.mark.parametrize("escrita,motivo", [
    (bd.Escrita(True), ""),
    (bd.Escrita(False, "org.bluez.Error.Failed", "br-connection-create-socket"),
     bd.MOTIVO_DORMINDO),
    (bd.Escrita(False, "org.bluez.Error.Failed", "Page Timeout"), bd.MOTIVO_DORMINDO),
    (bd.Escrita(False, "org.bluez.Error.Failed", "Host is down"), bd.MOTIVO_DORMINDO),
    (bd.Escrita(False, "", "Timeout was reached"), bd.MOTIVO_DORMINDO),
    (bd.Escrita(False, "org.freedesktop.DBus.Error.NoReply", ""), bd.MOTIVO_DORMINDO),
    (bd.Escrita(False, "org.bluez.Error.AuthenticationFailed", ""), bd.MOTIVO_CHAVE_VELHA),
    (bd.Escrita(False, "org.bluez.Error.Failed", "br-connection-key-missing"),
     bd.MOTIVO_CHAVE_VELHA),
    (bd.Escrita(False, "org.bluez.Error.AlreadyConnected", ""), bd.MOTIVO_JA_CONECTADO),
    (bd.Escrita(False, "org.bluez.Error.NotReady", "Resource Not Ready"), bd.MOTIVO_ADAPTADOR),
    (bd.Escrita(False, "org.bluez.Error.Failed", ""), bd.MOTIVO_ADAPTADOR),
])
def test_o_motivo_do_connect(escrita: bd.Escrita, motivo: str) -> None:
    assert bd.motivo_do_connect(escrita) == motivo


class _DonoQueChega:
    """O ``Device1`` que a varredura publica aos poucos."""

    atende_o_proprio_pareamento = True

    def __init__(self, depois_de: int) -> None:
        self.perguntas = 0
        self.depois_de = depois_de

    def caminho_do_aparelho(self, _alvo: str, *, adaptador: str | None = None) -> str | None:
        self.perguntas += 1
        return "/org/bluez/hci7/dev_X" if self.perguntas > self.depois_de else None

    def parear(self, no: str, **_k: Any) -> bd.Escrita:
        return bd.Escrita(True)


def _janela_aberta(dono: Any) -> gp.JanelaDeBusca:
    janela = gp.JanelaDeBusca(SALA, 5, dono=dono)
    janela._dono = dono
    janela._fim = time.monotonic() + 60.0
    return janela


def test_o_parear_espera_o_objeto_chegar(
    diario: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gp, "PASSO_DA_ESPERA_DO_OBJETO_S", 0.01)
    dono = _DonoQueChega(depois_de=3)

    desfecho = _janela_aberta(dono)._parear_pelo_dono(dono, VERMELHO, "x")

    assert desfecho.estado == gp.ESTADO_PAREOU
    assert dono.perguntas == 4


def test_o_parear_desiste_no_prazo(diario: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gp, "PASSO_DA_ESPERA_DO_OBJETO_S", 0.01)
    monkeypatch.setattr(gp, "ESPERA_DO_OBJETO_S", 0.05)
    dono = _DonoQueChega(depois_de=10_000)

    assert _janela_aberta(dono)._parear_pelo_dono(dono, VERMELHO, "x").estado == gp.ESTADO_NAO_DEU


def test_a_janela_que_fecha_nao_espera_o_objeto(
    diario: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    dono = _DonoQueChega(depois_de=10_000)
    janela = _janela_aberta(dono)
    janela._fechada = True
    t0 = time.monotonic()

    assert janela._esperar_o_objeto(dono, VERMELHO) is None
    assert time.monotonic() - t0 < 1.0
