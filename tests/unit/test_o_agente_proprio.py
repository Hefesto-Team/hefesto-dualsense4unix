"""O agente de pareamento é NOSSO para o que ela inicia — R5, BLUEZ-UM-DONO-01.

A decisão R5 dela (23/09/2026) revoga a D2: o ``hefesto-bt-agent`` fica de PISO,
para o que chega sozinho, e o daemon registra o próprio ``Agent1`` e pareia por
ele o que ELA inicia — sem virar o agente padrão e sem mexer na capacidade dos
adaptadores.

O que o fonte do BlueZ 5.86 diz, e é o que esta régua cobra: ``pair_device``
escolhe o agente por ``agent_get(sender)`` (``src/device.c:3374``) — o agente
registrado pelo MESMO remetente do ``Pair`` vence o padrão. O BlueZ de mentira
da bancada (``bluez_de_mentira.py``) faz a mesma escolha.

Duas bancadas: um barramento em processo, rápido, e um ``dbus-daemon``
particular com o Gio de verdade — que é o que prova o caminho que o produto usa.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import diario_do_radio
from hefesto_dualsense4unix.integrations import gesto_de_pareamento as gp
from hefesto_dualsense4unix.integrations.agente_de_pareamento import (
    CAMINHO_DO_AGENTE,
    CAPACIDADE,
    AgenteDePareamento,
)
from tests.unit import bluez_de_mentira as bm

DISPOSITIVO = bm.no_de(bm.CONTROLE)


@pytest.fixture(autouse=True)
def _trava_e_diario_de_mentira(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(tmp_path / "radio.lock"))
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(tmp_path / "radio-diario.jsonl"))


@pytest.fixture()
def barramento() -> bm.BarramentoDeMentira:
    return bm.BarramentoDeMentira()


@pytest.fixture()
def vivo(barramento: bm.BarramentoDeMentira) -> bd.DonoVivo:
    dono = bd.DonoVivo(barramento)
    assert dono.ligar()
    return dono


def _agente(barramento: bm.BarramentoDeMentira) -> AgenteDePareamento:
    agente = AgenteDePareamento(barramento, lambda: barramento.DONO_DO_BLUEZ)
    assert agente.registrar()
    return agente


# ---------------------------------------------------------------------------
# em processo
# ---------------------------------------------------------------------------


def test_o_pair_que_nos_iniciamos_e_atendido_pelo_nosso_agente(
    vivo: bd.DonoVivo, barramento: bm.BarramentoDeMentira
) -> None:
    """MORDIDA: faça ``DonoVivo.parear`` cair no ``parear`` da base (sem agente) —
    quem atende passa a ser o padrão, e esta régua reprova."""
    escrita = vivo.parear(DISPOSITIVO)

    assert escrita.feita, escrita
    assert barramento.agentes[barramento.NOME] == (CAMINHO_DO_AGENTE, CAPACIDADE)
    assert barramento.o_padrao_atendeu == []
    assert (DISPOSITIVO, bd.APARELHO, "Trusted", True) in barramento.escritas


def test_o_padrao_continua_sendo_o_bt_agent(
    vivo: bd.DonoVivo, barramento: bm.BarramentoDeMentira
) -> None:
    """R5: sem ``RequestDefaultAgent``. MORDIDA: pedi-lo em ``registrar`` reprova."""
    vivo.parear(DISPOSITIVO)
    assert "RequestDefaultAgent" not in barramento.metodos()
    assert barramento.padrao == ["bt-agent"]


def test_o_agente_so_aceita_o_aparelho_que_se_pareia_agora(
    barramento: bm.BarramentoDeMentira,
) -> None:
    """MORDIDA: aceite qualquer aparelho em ``_atender`` — o fone da vizinha entra."""
    agente = _agente(barramento)
    tratador = barramento.exportados[CAMINHO_DO_AGENTE]
    dono = barramento.DONO_DO_BLUEZ
    with agente.esperando(DISPOSITIVO):
        assert tratador(dono, "RequestConfirmation", (DISPOSITIVO, 1)) == ()
        with pytest.raises(bd.RecusaNoBarramento):
            tratador(dono, "RequestConfirmation", (bm.no_de(bm.OUTRO), 1))
    with pytest.raises(bd.RecusaNoBarramento):
        tratador(dono, "RequestAuthorization", (DISPOSITIVO,))


def test_o_agente_so_atende_o_bluetoothd(barramento: bm.BarramentoDeMentira) -> None:
    """MORDIDA: tire a conferência do remetente — um terceiro confirma por nós."""
    agente = _agente(barramento)
    tratador = barramento.exportados[CAMINHO_DO_AGENTE]
    with agente.esperando(DISPOSITIVO), pytest.raises(bd.RecusaNoBarramento):
        tratador(":1.666", "RequestConfirmation", (DISPOSITIVO, 1))


def test_pin_e_chave_sao_recusados_e_o_que_so_mostra_passa(
    barramento: bm.BarramentoDeMentira,
) -> None:
    """``NoInputNoOutput``: não há onde digitar, e a tela não ganha janela nova."""
    agente = _agente(barramento)
    tratador = barramento.exportados[CAMINHO_DO_AGENTE]
    dono = barramento.DONO_DO_BLUEZ
    with agente.esperando(DISPOSITIVO):
        for metodo in ("RequestPinCode", "RequestPasskey"):
            with pytest.raises(bd.RecusaNoBarramento):
                tratador(dono, metodo, (DISPOSITIVO,))
        assert tratador(dono, "DisplayPasskey", (DISPOSITIVO, 123456, 0)) == ()


def test_o_agente_atende_sem_pedir_a_trava(
    barramento: bm.BarramentoDeMentira, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Decisão de quem coordena: o agente NUNCA pede a trava do rádio.

    O ``Pair`` segura a trava enquanto o BlueZ chama o agente — e a chamada chega
    no fio do barramento, que não é o fio do ``Pair``: a trava reentrante não o
    reconhece. Se o agente a pedisse, esperaria o próprio ``Pair`` até o prazo,
    de 10 a 30 s em cada pareamento. Aqui o ``Pair`` é o fio da régua, com a
    trava na mão, e o BlueZ é outro fio.

    MORDIDA: faça o ``_atender`` pedir ``bluez_dbus.na_trava`` — a resposta só
    sai no prazo da trava, recusada.
    """
    monkeypatch.setattr(diario_do_radio, "PRAZO_DA_TRAVA_S", 0.5)
    agente = _agente(barramento)
    tratador = barramento.exportados[CAMINHO_DO_AGENTE]
    resposta: dict[str, Any] = {}

    def o_bluez_chamando() -> None:
        inicio = time.monotonic()
        try:
            resposta["valor"] = tratador(
                barramento.DONO_DO_BLUEZ, "RequestConfirmation", (DISPOSITIVO, 1)
            )
        except Exception as problema:
            resposta["erro"] = problema
        resposta["segundos"] = time.monotonic() - inicio

    with bd.na_trava(gp.QUEM), agente.esperando(DISPOSITIVO):
        fio = threading.Thread(target=o_bluez_chamando)
        fio.start()
        fio.join(timeout=3)

    assert resposta.get("valor") == (), resposta
    assert resposta["segundos"] < 0.2, "o agente esperou a trava do Pair que o chamou"


def test_ao_sair_o_agente_desregistra(
    vivo: bd.DonoVivo, barramento: bm.BarramentoDeMentira
) -> None:
    vivo.parear(DISPOSITIVO)
    vivo.fechar()
    assert "UnregisterAgent" in barramento.metodos()
    assert barramento.agentes == {} and barramento.exportados == {}


def test_o_bluetoothd_que_reinicia_leva_o_registro_e_o_proximo_parear_registra(
    vivo: bd.DonoVivo, barramento: bm.BarramentoDeMentira
) -> None:
    assert vivo.parear(DISPOSITIVO).feita
    barramento.agentes.clear()  # o bluetoothd novo não conhece ninguém
    barramento.emitir(bd.Sinal("dono", dono_novo=""))
    barramento.emitir(bd.Sinal("dono", dono_novo=":1.8"))
    assert bm.esperar(lambda: vivo.caminhos() is not None)

    assert vivo.parear(bm.no_de(bm.OUTRO)).feita
    assert barramento.metodos().count("RegisterAgent") == 2
    assert barramento.o_padrao_atendeu == []


def test_sem_conexao_viva_o_pareamento_fica_com_o_piso() -> None:
    """Pelo ``busctl`` não há conexão onde o agente more: quem atende é o padrão."""
    chamadas: list[list[str]] = []

    def executar(argumentos: list[str]) -> str:
        chamadas.append(list(argumentos))
        return ""

    leitor = bd.pelo_executor(executar)
    assert not leitor.atende_o_proprio_pareamento
    assert leitor.parear(DISPOSITIVO).feita
    assert [c[4] for c in chamadas] == ["Pair", "Trusted"]


def test_sob_a_suite_o_agente_nao_se_registra_no_sistema() -> None:
    sistema = bm.BarramentoDeMentira(e_do_sistema=True)
    assert not AgenteDePareamento(sistema, lambda: sistema.DONO_DO_BLUEZ).registrar()
    assert sistema.chamadas == [] and sistema.exportados == {}


# ---------------------------------------------------------------------------
# pelo barramento de verdade — um dbus-daemon particular
# ---------------------------------------------------------------------------

sem_barramento = pytest.mark.skipif(
    not bm.ha_dbus_daemon(), reason="sem dbus-daemon ou sem Gio nesta máquina"
)


@sem_barramento
def test_pelo_gio_o_pair_e_nosso_e_o_padrao_continua_o_bt_agent(tmp_path: Path) -> None:
    """O caminho que o produto usa, de ponta a ponta: foto, sinal, agente, ``Pair``.

    MORDIDAS: pedir ``RequestDefaultAgent`` em ``registrar`` põe o nosso nome na
    pilha de padrões; tirar o agente do ``DonoVivo.parear`` faz o bt-agent atender.
    """
    with bm.BluezParticular(tmp_path) as bluez:
        barramento = bd.BarramentoGio(bluez.endereco)
        assert barramento.abrir(), barramento.erro
        vivo = bd.DonoVivo(barramento)
        try:
            assert vivo.ligar()
            assert vivo.propriedade(DISPOSITIVO, bd.APARELHO, "Paired") is False

            escrita = vivo.parear(DISPOSITIVO)
            assert escrita.feita, escrita

            nosso = barramento.nome_unico()
            assert bluez.agentes[nosso] == (CAMINHO_DO_AGENTE, CAPACIDADE)
            assert bluez.padroes == [bluez.nome_do_bt_agent]
            assert bluez.o_padrao_atendeu == []
            assert bluez.mesa[DISPOSITIVO][bd.APARELHO]["Trusted"] is True
            # O sinal do BlueZ chega à foto: ninguém perguntou de novo.
            assert bm.esperar(
                lambda: vivo.propriedade(DISPOSITIVO, bd.APARELHO, "Paired") is True
            )

            # O que chega por outro cliente — o watchdog — é do padrão.
            outro = bluez.outro_cliente()
            outro.chamar(bd.SERVICO, bm.no_de(bm.OUTRO), bd.APARELHO, "Pair")
            assert bluez.o_padrao_atendeu == [bm.no_de(bm.OUTRO)]
        finally:
            vivo.fechar()
        assert nosso not in bluez.agentes


@sem_barramento
def test_pelo_gio_a_janela_de_busca_e_nossa(tmp_path: Path) -> None:
    """A busca abre na NOSSA conexão, os candidatos vêm da foto, o parear é nosso.

    A busca é por cliente: um ``StopDiscovery`` de quem não abriu é recusado
    pelo BlueZ de mentira, como pelo de verdade (medido em 19/09).
    """
    with bm.BluezParticular(tmp_path) as bluez:
        barramento = bd.BarramentoGio(bluez.endereco)
        assert barramento.abrir(), barramento.erro
        vivo = bd.DonoVivo(barramento)
        try:
            assert vivo.ligar()
            janela = gp.JanelaDeBusca(bm.ADAPTADOR, 5, dono=vivo)
            assert janela.pelo_dono
            assert janela.abrir_a_janela() == ""
            assert bluez.dono_da_busca == barramento.nome_unico()
            assert bm.esperar(lambda: vivo.propriedade(bm.HCI, bd.ADAPTADOR, "Discovering"))

            por_endereco = {c.endereco: c for c in janela.candidatos()}
            assert por_endereco[bm.CONTROLE].e_controle
            assert por_endereco[bm.OUTRO].nome == "fone da vizinha"

            assert janela.parear(bm.CONTROLE).estado == gp.ESTADO_PAREOU
            assert bluez.o_padrao_atendeu == []

            janela.fechar()
            assert bluez.dono_da_busca == ""
            assert janela.parear(bm.OUTRO).estado == gp.ESTADO_JANELA_FECHADA
        finally:
            vivo.fechar()
