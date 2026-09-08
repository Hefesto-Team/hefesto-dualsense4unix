#!/usr/bin/env python3
"""O co-op na Conexão Nativa: o número existe, e a tela para de calar.

**COOP-NA-CONEXAO-NATIVA-01, 06/09/2026.** O defeito, em uma frase: *quem
escolhe a Conexão Nativa — o modo mais fiel ao controle — perdia o conceito de
jogador por construção, e a tela desse modo dizia textualmente que "não há aqui
o que medir"*.

Duas coisas eram verdade ao mesmo tempo, e é isso que esta régua trava:

1. **o número já estava calculado.** O ``identity_registry`` é chaveado pelo
   MAC e não consulta modo nenhum — o ``_sync_identity_registry`` roda a cada
   2 s antes do gate de conexão. ``resolve_player_numbers`` devolvia
   ``[None] * N`` sem sequer olhar para ele;
2. **e a premissa estava ESCRITA.** O docstring dizia *"sem gamepad virtual
   (modo desktop/nativo): não existe jogador"*. Curar isto foi derrubar uma
   decisão, não consertar um descuido — por isso a contraprova do
   **Controlar o PC** vale tanto quanto a cura: ali não há jogador mesmo, e
   alargar a cura para os dois modos trocaria um defeito por outro.

O QUE ESTA RÉGUA NÃO MEDE, e é honesto dizer
--------------------------------------------

**Se o JOGO vê dois jogadores.** Essa é a §5 da sprint, e nenhuma leitura de
código a responde: quem conta gamepads é o jogo. Ela é bancada dela (dois
DualSense num jogo de co-op local, no cabo e no rádio), e vive na
MESA-DE-QUATRO-01. É exatamente por ela ainda estar aberta que o Caminho A — a
tela dizendo de quem é a conta — é o piso desta sprint e não um extra: sem a
frase, o número novo seria uma afirmação sobre o jogo que ninguém mediu.

O DUBLÊ É A FUNÇÃO REAL
-----------------------

O ``ControllerIdentityRegistry`` entra aqui de verdade, não como
``SimpleNamespace``. Esta casa já pagou três vezes pelo *dublê mais frouxo que
a função real*, e aqui o risco era concreto: um dublê ``lambda uniq: {...}[uniq]``
não conhece o ``assign=False``, e passaria verde sobre uma leitura que dá lugar
na fila a quem só perguntou o número.
"""
from __future__ import annotations

import pathlib
import sys
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.app.actions import home_actions
from hefesto_dualsense4unix.app.actions.jogar import painel
from hefesto_dualsense4unix.daemon.subsystems.coop import (
    CoopManager,
    resolve_player_numbers,
)
from hefesto_dualsense4unix.daemon.subsystems.identity import (
    ControllerIdentityRegistry,
)
from hefesto_dualsense4unix.interface import aba01
from pacotes import Contexto
from pacotes import a01_jogar as aba

#: Faixa FORJADA da casa (`aa:bb:cc`), sem sequência simples — a régua de
#: anonimato de fixtures reprova endereço real podado.
MAC_1 = "aa:bb:cc:00:00:1f"
MAC_2 = "aa:bb:cc:00:00:d8"
MAC_3 = "aa:bb:cc:00:00:7a"


def _registro(*macs: str) -> ControllerIdentityRegistry:
    """Um registro REAL com os MACs já na fila, na ordem em que chegaram.

    ``slot_for`` com o padrão ``assign=True`` é o caminho por onde o produto dá
    lugar na fila (`identity.py:668`), e é o único I/O-free: quem grava em
    disco é o ``sync_connected``, que não entra aqui.
    """
    reg = ControllerIdentityRegistry()
    for mac in macs:
        reg.slot_for(mac)
    return reg


def _daemon(
    *,
    nativo: bool,
    registro: ControllerIdentityRegistry | None = None,
    gamepad: bool = False,
) -> Any:
    """Um daemon com o mínimo que ``resolve_player_numbers`` consulta."""
    return SimpleNamespace(
        config=SimpleNamespace(coop_enabled=True, gamepad_flavor="dualsense"),
        _gamepad_device=object() if gamepad else None,
        _coop_manager=None,
        identity_registry=registro,
        is_native_mode=lambda: nativo,
    )


def _ctrl(uniq: str | None, conectado: bool = True) -> dict[str, Any]:
    return {"uniq": uniq, "connected": conectado, "transport": "usb"}


# ---------------------------------------------------------------------------
# 1. O NÚMERO — NATIVA-2 / Caminho B
# ---------------------------------------------------------------------------
def test_o_numero_do_jogador_sobrevive_sem_vpad() -> None:
    """Dois controles na Conexão Nativa recebem 1 e 2, na ordem do registro.

    A MORDIDA: troque o corpo de ``coop._numeros_sem_vpad`` por
    ``return [None] * len(controllers)`` — o que a função fazia até 06/09/2026 —
    e esta régua reprova nomeando os dois controles que ficaram sem número.
    """
    daemon = _daemon(nativo=True, registro=_registro(MAC_1, MAC_2))
    numeros = resolve_player_numbers(daemon, [_ctrl(MAC_1), _ctrl(MAC_2)])
    assert numeros == [1, 2], (
        "na Conexão Nativa os controles voltaram a não ter jogador: "
        f"{MAC_1} e {MAC_2} receberam {numeros}, e o identity_registry — que "
        "não consulta modo nenhum — já sabia que são o 1 e o 2"
    )


def test_no_controlar_o_pc_ninguem_e_jogador() -> None:
    """A CONTRAPROVA, e ela vale tanto quanto a cura.

    Sem vpad e sem Modo Nativo o controle mexe no PC: não há jogo do outro lado
    e não há jogador. Alargar a cura para os dois modos seria trocar um defeito
    por outro — o cartão passaria a prometer um jogador para quem está movendo
    um cursor.

    A MORDIDA: apague o ``if ligado is not True`` de ``_numeros_sem_vpad`` e
    esta régua reprova.
    """
    daemon = _daemon(nativo=False, registro=_registro(MAC_1, MAC_2))
    assert resolve_player_numbers(daemon, [_ctrl(MAC_1), _ctrl(MAC_2)]) == [
        None,
        None,
    ], "o Controlar o PC começou a numerar jogadores que não existem"


def test_um_daemon_dublado_nao_numera_a_sala_inteira() -> None:
    """``is_native_mode`` que devolve algo TRUTHY mas não ``True`` não vale.

    É a blindagem que o irmão ``isinstance(number, int)`` já tinha: com o
    daemon dublado por ``MagicMock`` toda chamada devolve um mock truthy, e um
    ``if`` solto numeraria a mesa num teste que nunca falou de modo nenhum.

    A MORDIDA: troque ``if ligado is not True`` por ``if not ligado`` e esta
    régua reprova.
    """
    daemon = _daemon(nativo=True, registro=_registro(MAC_1))
    daemon.is_native_mode = lambda: "sim"  # truthy, e não é o booleano
    assert resolve_player_numbers(daemon, [_ctrl(MAC_1)]) == [None]


def test_daemon_sem_a_pergunta_do_modo_continua_calado() -> None:
    """Daemon velho (sem ``is_native_mode``) não ganha número por acidente.

    O install editable deixa daemon e janela de versões diferentes convivendo
    até o próximo start — é o mesmo caso que o ``native_bt_fragil`` já trata.
    """
    daemon = _daemon(nativo=True, registro=_registro(MAC_1))
    del daemon.is_native_mode
    assert resolve_player_numbers(daemon, [_ctrl(MAC_1)]) == [None]


def test_desconectado_nao_ganha_numero_na_conexao_nativa() -> None:
    """Quem não está na sala não é jogador — nem com lugar gravado na fila."""
    daemon = _daemon(nativo=True, registro=_registro(MAC_1, MAC_2))
    assert resolve_player_numbers(
        daemon, [_ctrl(MAC_1), _ctrl(MAC_2, conectado=False)]
    ) == [1, None]


def test_controle_sem_mac_nao_recebe_numero_chutado() -> None:
    """Sem MAC não há identidade, e a resposta a *não sei* é não mostrar nada."""
    daemon = _daemon(nativo=True, registro=_registro(MAC_1))
    assert resolve_player_numbers(daemon, [_ctrl(MAC_1), _ctrl(None)]) == [1, None]


def test_perguntar_o_numero_nao_da_lugar_na_fila() -> None:
    """LEITURA PURA, e o ``assign=False`` é o que a mantém assim.

    ``resolve_player_numbers`` roda no ``state_full``, dez vezes por segundo.
    Se perguntar o número atribuísse lugar, a ordem da fila passaria a depender
    de quem abriu a tela — e o número dela nasceria de um efeito colateral de
    olhar. É o mesmo contrato do ``ipc_handlers._player_slot_for``.

    A MORDIDA: tire o ``assign=False`` da chamada de ``slot_for`` em
    ``_numeros_sem_vpad`` e esta régua reprova — o desconhecido volta com 2.
    """
    registro = _registro(MAC_1)
    daemon = _daemon(nativo=True, registro=registro)
    # MAC_3 nunca foi apresentado ao registro.
    assert resolve_player_numbers(daemon, [_ctrl(MAC_1), _ctrl(MAC_3)]) == [1, None]
    assert registro.slot_for(MAC_3, assign=False) is None, (
        "a leitura do número deu lugar na fila a um controle que só passou "
        "pela tela — `resolve_player_numbers` deixou de ser pura"
    )


def test_a_conexao_nativa_continua_sem_ligar_o_vpad() -> None:
    """§9 da sprint: o gate do co-op fica FECHADO no Modo Nativo, de propósito.

    O mecanismo do co-op é *grab do físico + um vpad por jogador*; pôr-se no
    meio é exatamente o que a Conexão Nativa dispensa. Esta régua existe para
    que a próxima pessoa que ler «co-op na Conexão Nativa» não abra
    ``should_be_active`` achando que era isso que faltava: o que a sprint curou
    foi a tela dizer que ninguém é jogador, não o Hefesto voltar para o meio.
    """
    daemon = _daemon(nativo=True, registro=_registro(MAC_1, MAC_2))
    assert CoopManager(daemon).should_be_active() is False, (
        "o co-op passou a se ligar sem vpad: ou o grab e o vpad deixaram de ser "
        "o mecanismo, ou alguém desfez o Modo Nativo que ela pediu"
    )


# ---------------------------------------------------------------------------
# 2. A TELA — NATIVA-1 / Caminho A
# ---------------------------------------------------------------------------
def _estado(nativo: bool, quantos: int) -> dict[str, Any]:
    return {
        "connected": True,
        "native_mode": nativo,
        "gamepad_emulation": {"enabled": not nativo, "flavor": "dualsense"},
        "paused": False,
        "controllers": [
            {"uniq": mac, "connected": True, "transport": "usb", "player_slot": i}
            for i, mac in enumerate((MAC_1, MAC_2, MAC_3)[:quantos], start=1)
        ],
    }


def test_o_texto_do_modo_nativo_fala_de_jogadores() -> None:
    """Com dois controles na Conexão Nativa, a tela diz de quem é a conta.

    A MORDIDA: tire o ``Aviso(SELO_DO_MODO, …)`` de ``painel.AVISOS_DA_TELA`` e
    esta régua reprova imprimindo a coluna inteira — que é o que ela mostrava
    até 06/09/2026: nada sobre jogadores no único modo em que o número muda de
    dono.
    """
    linhas = painel.avisos_do_estado(_estado(nativo=True, quantos=2))
    do_modo = [a for a in linhas if a["fonte"] == "painel.aviso_do_modo_nativo"]
    assert do_modo, (
        "a coluna Atenção calou sobre a Conexão Nativa com dois controles; "
        f"o que ela publicou foi {[a['selo'] for a in linhas]}"
    )
    texto = do_modo[0]["texto"]
    assert "jogadores" in texto, (
        f"a linha do modo não fala de jogadores: {texto!r}")
    assert "2 controles" in texto, (
        f"a linha do modo não diz quantos controles estão ligados: {texto!r}")
    assert do_modo[0]["selo"] == "MODO"


def test_com_um_controle_so_a_linha_do_modo_cala() -> None:
    """Sem dois controles não existe pergunta de co-op — e a coluna é Atenção.

    A MORDIDA: troque o ``if quantos < 2`` por ``if quantos < 1`` em
    ``painel.aviso_do_modo_nativo`` e esta régua reprova: a linha passaria a
    falar sempre, empurrando para o ``+N`` os avisos que falam quando dói.
    """
    assert painel.aviso_do_modo_nativo(_estado(nativo=True, quantos=1)) is None


def test_fora_do_modo_nativo_a_linha_nao_existe() -> None:
    """Com o Hefesto no meio quem responde pelos jogadores é o co-op."""
    assert painel.aviso_do_modo_nativo(_estado(nativo=False, quantos=3)) is None


def test_a_linha_do_modo_chega_a_coluna_da_aba(monkeypatch: pytest.MonkeyPatch) -> None:
    """O caminho INTEIRO: do estado ao ``aviso-texto`` que o piloto pinta.

    As outras fontes ficam caladas porque esta régua mede o TRAJETO, não a
    concorrência: a coluna mostra três de cada vez, e um aviso do disco desta
    máquina empurraria o meu para o ``+N`` — verde aqui, vermelho no CI, e
    nenhum dos dois falando do defeito medido. `painel.avisos_do_estado` fica
    REAL de propósito: é ele que está sob medição.
    """
    monkeypatch.setattr(aba, "_do_exame", lambda: [])
    monkeypatch.setattr(aba, "_aviso_da_ponte", lambda _s: None)
    monkeypatch.setattr(aba, "_aviso_da_cura_do_travamento", lambda: None)
    monkeypatch.setattr(
        home_actions, "aviso_de_opt_out_antigo", lambda *a, **k: None)
    ctx = Contexto(
        state=_estado(nativo=True, quantos=2), mesa=[], conectados=[], estados={})
    fora = aba.coluna_de_atencao(ctx)
    assert "MODO" in fora["aviso-selo"], (
        f"o selo do modo não chegou à coluna: {fora['aviso-selo']}")
    escritos = [t for t in fora["aviso-texto"] if t]
    assert any("jogadores" in t for t in escritos), (
        f"a coluna publicou {escritos} e nenhuma linha fala de jogadores")


def test_o_selo_do_modo_esta_na_escada_da_gravidade() -> None:
    """Selo fora de ``ORDEM_DA_GRAVIDADE`` vai para DEPOIS DE TUDO.

    E «depois de tudo» com três linhas na coluna é *escondido atrás do ``+N``*.
    Um selo nomeado no produto e ausente da escada é um aviso que a máquina
    cheia cala — que é o defeito que esta régua trava.
    """
    assert painel.SELO_DO_MODO in aba.ORDEM_DA_GRAVIDADE, (
        f"o selo {painel.SELO_DO_MODO!r} não está na escada de gravidade")
    ordem = aba.ORDEM_DA_GRAVIDADE
    assert ordem.index("GAMEPAD") < ordem.index(painel.SELO_DO_MODO) < ordem.index(
        "PONTE"
    ), "a linha do modo saiu de junto do GAMEPAD, que responde à mesma pergunta"


def test_a_dica_do_desligado_fala_de_jogadores() -> None:
    """A herdeira do ``TEXTO_NATIVO``: o ``title`` da posição Desligado.

    Ela é o par CRAVADO da linha viva — está sempre lá, mesmo com um controle
    só, porque explica o modo e não o estado da sala.

    A MORDIDA: devolva a dica de ontem (*"Modo Nativo: o Hefesto sai do meio e
    o jogo fala direto com o controle."*) e esta régua reprova imprimindo-a.
    """
    dicas = {chave: dica for chave, _modo, _rot, dica in aba01.INTERRUPTOR}
    dica = dicas["desligado"]
    assert "jogadores" in dica, (
        "a dica do Modo Nativo voltou a calar sobre quantos jogadores existem "
        f"nele: {dica!r}")
    assert aba01.NATIVO_E_OS_JOGADORES in dica


def test_a_pagina_diz_isto_nos_dois_lugares_e_por_um_dono_so() -> None:
    """O ``title`` da posição Desligado E o ``?`` da linha Status.

    Os dois já repetiam palavra por palavra a metade velha da frase. Estender
    um só deixaria o ``?`` explicando o Modo Nativo e calando exatamente sobre
    o que mudou — a correção pela metade que esta casa proíbe.

    A MORDIDA: tire o ``{NATIVO_E_OS_JOGADORES}`` do bloco ``<span
    class="ajuda">`` do ``MIOLO`` e esta régua reprova contando uma ocorrência
    onde tem de haver duas.
    """
    quantas = aba01.MIOLO.count(aba01.NATIVO_E_OS_JOGADORES)
    assert quantas == 2, (
        f"a frase do Modo Nativo aparece {quantas} vez(es) na página e tem de "
        "aparecer nas duas — o `title` da posição Desligado e o `?` da linha "
        "Status")


def test_nenhuma_das_duas_frases_afirma_o_que_ninguem_mediu() -> None:
    """A §4.2 é INFERIDO DO CÓDIGO, e a tela não pode publicá-la como medida.

    *"O jogo vê dois jogadores"* seria afirmação forte sem régua — quem conta
    gamepads é o jogo, e a medição que fecharia a pergunta é bancada dela
    (MESA-DE-QUATRO-01). As duas frases dizem de QUEM é a conta, nunca qual é
    o resultado dela.
    """
    dicas = {chave: dica for chave, _modo, _rot, dica in aba01.INTERRUPTOR}
    for frase in (dicas["desligado"], painel.FRASE_DO_MODO_NATIVO):
        baixo = frase.lower()
        assert "o jogo vê dois" not in baixo, (
            f"a tela afirmou o resultado da §5, que ninguém mediu: {frase!r}")
        assert "quem conta os jogadores é o jogo" in baixo, (
            f"a frase deixou de dizer de quem é a conta: {frase!r}")
