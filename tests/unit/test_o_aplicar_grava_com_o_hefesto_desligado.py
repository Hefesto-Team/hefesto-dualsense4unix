"""O "Aplicar" desce ao disco com o Hefesto PARADO — e sem um segundo dono.

CONEXÕES · MAPA 2D 01 / G3 (25/08/2026).

O DEFEITO, EM UMA FRASE
------------------------

O ``maquina.json`` não depende de daemon nenhum — é um arquivo de configuração
que a própria janela sabe gravar, com o mesmo lock e a mesma gravação atômica.
Mesmo assim, o ÚNICO escritor de produção era o handler ``machine.declare``,
atrás do IPC: com o Hefesto desligado, o rodapé respondia *"não gravei o que
você declarou"* e a mesa, o desenho do gabinete, os controles e o orçamento que
ela acabara de declarar iam embora.

``utils/maquina.gravar_rascunho_da_mesa`` foi escrita em 24/08 exatamente para
isto e nasceu com zero chamadores; ``integrations/lugar_declarado`` nasceu em
25/08 como o chamador que faltava, e também sem ninguém. Esta bateria é o
portão do último palmo: o gesto do rodapé chegando ao disco.

O QUE ELA TAMBÉM GUARDA
------------------------

**Que não nasceu um segundo dono do gesto de gravar.** A objeção está escrita em
``config/secao_mesa._ao_declarar`` — *"chamar ``machine.declare`` daqui criaria
um segundo dono do gesto de gravar, que é a classe de defeito que a ABAS-01
curou"*. O dono continua sendo ``_gravar_declaracao_de_maquina``; o que mudou é
o que ele faz quando a ponte está morta.

**E que o daemon VIVO que recusa não é atropelado.** ``motivo is None`` é o
contrato de ``machine_declare_detalhado`` para "o daemon não respondeu". Gravar
por trás de um daemon que disse "não" deixaria a memória dele divergindo do
arquivo, que é pior que não gravar.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi`, como em
# `test_footer_actions.py`. `footer_actions` puxa `gui_dialogs`, que é GTK.
exigir_gi_real("o Aplicar com o Hefesto desligado")

import json
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import footer_actions
from hefesto_dualsense4unix.app.actions.footer_actions import FooterActionsMixin
from hefesto_dualsense4unix.utils.maquina import caminho_da_maquina, carregar_maquina

#: A frase que a tela mostrava — e ainda mostra quando nem o disco aceita. É a
#: evidência do defeito, não texto de produto deste arquivo: a dona única do
#: texto da aba é a `CONFIGURACOES-O-LEXICO-01`.
FRASE_DO_DEFEITO = "O Hefesto está desligado — não gravei o que você declarou"

#: Uma declaração com as QUATRO chaves de topo que a aba acumula. Existe assim
#: de propósito: a porta estreita (`declarar_a_mesa`) gravaria só a primeira e
#: perderia as outras três em silêncio.
DECLARACAO_INTEIRA: dict[str, Any] = {
    "mesa": {"altura_da_antena": "acima"},
    "mapa": {
        "faces": [{"nome": "Frente", "portas": ["1", "2"], "perto": True}],
        "portas": {"1": {"caminho": "1-3"}},
    },
    "orcamento": {"teto": "balanceado"},
    "controles": {"aabbcc0000a1": {"cor": "roxo"}},
}


class _Rodape(FooterActionsMixin):
    """O mínimo de hospedeiro que ``_gravar_declaracao_de_maquina`` toca."""

    def __init__(self, pendente: dict[str, Any] | None) -> None:
        self._maquina_pendente = pendente


@pytest.fixture
def daemon_parado(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """A ponte não responde — ``(False, None, ())``, o contrato de "offline"."""
    pedidos: list[dict[str, Any]] = []

    def _sem_resposta(maquina: dict[str, Any]) -> tuple[bool, None, tuple[()]]:
        pedidos.append(maquina)
        return (False, None, ())

    monkeypatch.setattr(
        footer_actions.ipc_bridge, "machine_declare_detalhado", _sem_resposta
    )
    return pedidos


# --- 1. A mordida: o disco muda, e a tela para de mentir ----------------------


def test_o_que_ela_declarou_desce_ao_disco(daemon_parado: list[Any]) -> None:
    """Com o Hefesto parado, o "Aplicar" grava — e a releitura devolve tudo.

    **A MORDIDA.** Arranquei o desvio para o disco (as duas linhas
    ``if not ok and motivo is None`` de ``_gravar_declaracao_de_maquina``) e
    rodei: o ``maquina.json`` não nasceu, ``gravou`` voltou ``False``, a frase
    voltou a ser a do defeito e as quatro asserções abaixo reprovaram. Devolvi,
    e as quatro passaram.
    """
    alvo = caminho_da_maquina()
    assert not alvo.exists(), "a bateria começa com o disco limpo"

    gravou, frase = _Rodape(DECLARACAO_INTEIRA)._gravar_declaracao_de_maquina()

    assert daemon_parado, "a ponte tem de ser tentada PRIMEIRO — o disco é o plano B"
    assert gravou is True, f"a tela diria: {FRASE_DO_DEFEITO!r}"
    assert alvo.exists(), f"nada chegou ao disco — a tela diria: {FRASE_DO_DEFEITO!r}"
    assert frase != FRASE_DO_DEFEITO


def test_o_documento_inteiro_desce_ao_disco_e_nao_so_a_mesa(
    daemon_parado: list[Any],
) -> None:
    """As quatro chaves de topo sobrevivem — nenhuma se perde no caminho.

    ``lugar_declarado.declarar_a_mesa`` é escopada à seção ``mesa``: mandar por
    ela a declaração pendente do rodapé gravaria a altura da antena e perderia
    calado o desenho do gabinete, os controles e o orçamento. Este teste é o que
    impede essa economia de parecer inofensiva.
    """
    _Rodape(DECLARACAO_INTEIRA)._gravar_declaracao_de_maquina()

    gravado = carregar_maquina()
    assert gravado.mesa.altura_da_antena == "acima"
    assert gravado.orcamento.teto == "balanceado"
    assert gravado.controles["aabbcc0000a1"].cor == "roxo"
    assert [f.nome for f in gravado.mapa.faces] == ["Frente"]
    assert gravado.mapa.faces[0].perto is True, (
        "o fato físico da face tem de atravessar o mesmo caminho que o resto"
    )


def test_a_pendencia_e_limpa_so_quando_a_gravacao_confirma(
    daemon_parado: list[Any],
) -> None:
    """Gravou no disco, então a aba para de marcar "há escolhas por aplicar".

    Fonte única do estado: ``_maquina_pendente``, a mesma que o portão do
    fechamento da janela consulta. Deixá-la de pé depois de gravar faria o
    diálogo de saída acusar perda de uma coisa que já está em disco.
    """
    rodape = _Rodape(DECLARACAO_INTEIRA)
    rodape._gravar_declaracao_de_maquina()
    assert rodape._maquina_pendente is None


# --- 2. O que o desvio para o disco NÃO pode fazer ---------------------------


def test_o_daemon_vivo_que_recusa_nao_e_atropelado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Daemon que RESPONDEU "não" mantém o disco intacto.

    ``motivo`` preenchido quer dizer que o daemon falou. Gravar por trás dele
    deixaria a memória do processo divergindo do arquivo — duas verdades sobre a
    mesma coisa, que é o defeito que esta leva inteira existe para matar.

    Mordida: troquei o gatilho por ``if not ok`` (sem o ``motivo is None``). O
    arquivo nasceu com o daemon vivo dizendo não, e este teste reprovou.
    """
    recusa = "Não vou sobrescrever o que está lá"
    monkeypatch.setattr(
        footer_actions.ipc_bridge,
        "machine_declare_detalhado",
        lambda _maquina: (False, recusa, ()),
    )
    rodape = _Rodape(DECLARACAO_INTEIRA)

    gravou, frase = rodape._gravar_declaracao_de_maquina()

    assert (gravou, frase) == (False, recusa)
    assert not caminho_da_maquina().exists()
    assert rodape._maquina_pendente == DECLARACAO_INTEIRA, (
        "recusa deixa a declaração de pé: clicar de novo tenta de novo"
    )


def test_o_daemon_que_aceitou_grava_sozinho_e_a_janela_nao_grava_de_novo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Com a ponte viva e o ``ok``, o disco não é tocado por aqui.

    Quem grava é o handler, do outro lado. Uma segunda escrita pela janela seria
    o segundo dono do gesto — e ela ainda chegaria DEPOIS, sobrescrevendo o que
    o daemon acabou de fundir.
    """
    monkeypatch.setattr(
        footer_actions.ipc_bridge,
        "machine_declare_detalhado",
        lambda _maquina: (True, None, ()),
    )
    rodape = _Rodape(DECLARACAO_INTEIRA)

    gravou, _frase = rodape._gravar_declaracao_de_maquina()

    assert gravou is True
    assert not caminho_da_maquina().exists()
    assert rodape._maquina_pendente is None


def test_disco_que_recusa_volta_a_frase_do_defeito_e_guarda_os_bytes(
    daemon_parado: list[Any],
) -> None:
    """Arquivo de uma versão futura não é lido nem sobrescrito, nem por aqui.

    Escolha de alguém não se destrói para registrar outra. E o rodapé tem de
    dizer que não gravou, em vez de mentir "gravei" e deixar a declaração dela
    sumir na próxima abertura.
    """
    alvo = caminho_da_maquina()
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(json.dumps({"version": 99, "mesa": {}}), encoding="utf-8")
    antes = alvo.read_bytes()
    rodape = _Rodape(DECLARACAO_INTEIRA)

    gravou, frase = rodape._gravar_declaracao_de_maquina()

    assert (gravou, frase) == (False, FRASE_DO_DEFEITO)
    assert alvo.read_bytes() == antes
    assert rodape._maquina_pendente == DECLARACAO_INTEIRA


def test_declaracao_vazia_nao_cria_arquivo_nem_com_o_daemon_parado(
    daemon_parado: list[Any],
) -> None:
    """Sem nada declarado, sai cedo — o desvio novo não muda essa porta.

    Criar um ``maquina.json`` só porque alguém clicou "Aplicar" poria em disco
    um documento que ela nunca declarou.
    """
    assert _Rodape(None)._gravar_declaracao_de_maquina() == (True, None)
    assert not daemon_parado, "nem a ponte é tentada quando não há o que declarar"
    assert not caminho_da_maquina().exists()


# --- 3. O caminho novo não reabre a porta do daemon --------------------------


def test_o_desvio_para_o_disco_nao_fala_com_o_daemon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A gravação de plano B não passa pela ponte, nem por engano.

    Se ela passasse, o defeito voltaria inteiro no dia em que alguém
    "reaproveitasse" o caminho do IPC aqui — e todos os testes acima
    continuariam verdes, porque o dublê da ponte responde.
    """

    def _explode(*_: object, **__: object) -> None:
        raise AssertionError("o plano B não pode falar com o daemon")

    monkeypatch.setattr(
        footer_actions.ipc_bridge,
        "machine_declare_detalhado",
        lambda _maquina: (False, None, ()),
    )
    for nome in ("call_async", "run_in_thread"):
        monkeypatch.setattr(footer_actions.ipc_bridge, nome, _explode)

    gravou, _frase = _Rodape({"mesa": {"linha_de_visada": "livre"}})._gravar_declaracao_de_maquina()

    assert gravou is True
    assert carregar_maquina().mesa.linha_de_visada == "livre"
