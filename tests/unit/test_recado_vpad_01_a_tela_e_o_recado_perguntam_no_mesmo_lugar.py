#!/usr/bin/env python3
"""RECADO-VPAD-01 — o recado da Vibração não manda ligar o que já está ligado.

O DEFEITO, visto por ela em 17/09/2026
--------------------------------------
No rodapé da aba Vibração, em laranja::

    "A intensidade não está chegando a jogo nenhum: falta o gamepad virtual,
     por onde ela passa. Ponha o Status em «Ligado» na aba Jogar. Aqui embaixo
     ela ainda vale."

Com o Status **já aceso**. No journal dela, 1 min 59 s de ``rumble_sem_dono
backends=[] emulacao=False`` com o modo vivo em ``mouse_teclado`` — o
``desktop`` do produto, o chip «Navegação», que mora DENTRO do lado Ligado do
interruptor.

A causa é a de sempre nesta casa: **duas leituras paralelas da mesma
pergunta.** O recado perguntava por ``native_mode`` + ``rumble_ff.vpads``
(contagem de objetos vivos) e o interruptor por ``mode_of_state`` →
``MODOS_LIGADOS`` (a flag). É o TERCEIRO par: o primeiro foi a borda do
``launch_env`` contra esta mesma tela, curado pelo ``sem_dono_do_rumble``; o
segundo, a tela contra o journal
(``test_a_tela_e_o_journal_usam_um_criterio_so``, 11/08). Esta régua segue a
forma dos dois — **compara contra o dono, nunca contra um texto digitado
aqui**.

POR QUE ELA NÃO MEDE O TEXTO, e este é o ponto inteiro
------------------------------------------------------
O aviso já tinha régua: ``test_politica_de_vibracao_o_alcance_na_tela`` afirma
``"não está chegando" in texto`` e ``"aqui embaixo" in texto.lower()``. As duas
ficaram VERDES sobre a instrução errada por mais de um mês, porque as duas
mediam a PRIMEIRA e a ÚLTIMA oração — e o defeito estava na do meio.

Então aqui a pergunta é de CONDIÇÃO:

* o que a tela mostra sai de ``jogar.painel.hefesto_ligado`` — o mesmo leitor
  que acende o interruptor da aba Jogar;
* qual ramo o recado escolheu sai de
  ``rumble_actions.CAUSAS_DO_ALCANCE_PERDIDO`` — o dicionário das quatro
  segundas metades, pelo NOME do ramo.

Nenhuma frase de tela é digitada neste arquivo. Trocar as palavras do aviso não
move um caractere daqui; trocar a CONDIÇÃO reprova.

A MEDIÇÃO QUE A SPRINT NÃO TINHA, e ela é pior do que a descrição
-----------------------------------------------------------------
A instrução velha era **inalcançável-correta**: não havia estado nenhum em que
ela pudesse estar certa. O quadrante do ``sem_dono_do_rumble`` exige
``native=False``; com ``native`` falso ``mode_of_state`` só devolve ``gamepad``
ou ``desktop``, que são exatamente os dois membros de ``MODOS_LIGADOS``. Logo
``hefesto_ligado`` é ``True`` em **100% dos estados em que o aviso aparece** — e
o único em que seria ``False`` (o nativo) é o único em que o aviso não sai.
``test_mandar_ligar_era_inalcancavel_correto`` é quem guarda esse fato.

AS MORDIDAS, executadas em 17/09/2026
--------------------------------------
* devolva a instrução velha (``Ponha o Status em “Ligado”``) fixa, sem
  perguntar ao painel → ``test_o_recado_e_o_interruptor_nao_se_contradizem``
  reprova nos DOIS caminhos, dizendo que o painel diz Ligado e o texto manda
  ligar;
* troque ``MODE_DESKTOP`` por ``MODE_GAMEPAD`` na primeira pergunta de
  ``_causa_do_alcance_perdido`` (os dois ramos trocam de lugar) →
  ``test_cada_caminho_ganha_a_frase_do_seu_defeito`` reprova nomeando o ramo
  que saiu e o que era esperado, e a contradição continua verde — que é
  justamente por que os dois casos existem separados.
"""
from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.rumble_actions`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions import rumble_actions
from hefesto_dualsense4unix.app.actions.jogar import painel
from hefesto_dualsense4unix.app.actions.mode_transition import (
    MODE_DESKTOP,
    MODE_GAMEPAD,
)
from hefesto_dualsense4unix.daemon.subsystems.rumble import sem_dono_do_rumble

NAVEGACAO: dict[str, Any] = {
    "native_mode": False,
    "gamepad_emulation": {"enabled": False},
    "rumble_ff": {"vpads": 0},
}

VPAD_NAO_SUBIU: dict[str, Any] = {
    "native_mode": False,
    "gamepad_emulation": {"enabled": True},
    "rumble_ff": {"vpads": 0},
}

#: ``mode_of_state`` o lê como ``desktop``, e o interruptor da aba Jogar também:
DAEMON_SEM_O_BLOCO: dict[str, Any] = {
    "native_mode": False,
    "rumble_ff": {"vpads": 0},
}

ESTADOS_E_O_RAMO_ESPERADO: dict[str, tuple[dict[str, Any], str]] = {
    "navegação": (NAVEGACAO, "navegacao"),
    "vpad não subiu": (VPAD_NAO_SUBIU, "vpad-nao-subiu"),
    "daemon sem o bloco": (DAEMON_SEM_O_BLOCO, "navegacao"),
}


@pytest.mark.parametrize(
    "gamepad_emulation",
    [{"enabled": False}, {"enabled": True}, None],
)
def test_mandar_ligar_era_inalcancavel_correto(
    gamepad_emulation: dict[str, Any] | None,
) -> None:
    """O fato que fecha a sprint: a instrução velha NUNCA podia estar certa.

    O quadrante exige ``native=False``; com ``native`` falso ``mode_of_state``
    só devolve ``gamepad`` ou ``desktop``, e os dois são ``MODOS_LIGADOS``. Não
    existe estado em que o aviso saia com o interruptor em Desligado — então a
    ordem de ligar era um no-op em todos eles.

    Se um dia ``MODOS_LIGADOS`` encolher e este caso deixar de valer, é aqui que
    se descobre, e a instrução volta a ser legítima naquele estado.
    """
    estado: dict[str, Any] = {"native_mode": False, "rumble_ff": {"vpads": 0}}
    if gamepad_emulation is not None:
        estado["gamepad_emulation"] = gamepad_emulation

    assert sem_dono_do_rumble(native=False, backends=()) is True
    assert painel.hefesto_ligado(estado) is True, (
        "o aviso saiu com o interruptor em Desligado — o mapa do quadrante "
        f"mudou: modo_vivo={painel.modo_vivo(estado)!r}"
    )
    assert painel.modo_vivo(estado) in painel.MODOS_LIGADOS


def test_o_aviso_diz_o_que_acontece_e_o_que_sobra_em_todos_os_ramos() -> None:
    """As duas metades que NÃO mudam continuam em todas as combinações."""
    for nome, (estado, _) in ESTADOS_E_O_RAMO_ESPERADO.items():
        texto = rumble_actions.texto_do_alcance_da_intensidade(estado)
        assert texto is not None
        assert texto.startswith(rumble_actions._ALCANCE_O_QUE_ACONTECE), (
            f"«{nome}» perdeu a primeira metade: {texto!r}")
        assert texto.endswith(rumble_actions._ALCANCE_O_QUE_SOBRA), (
            f"«{nome}» perdeu a última oração: {texto!r}")


def test_a_pergunta_tem_um_dono_so() -> None:
    """O recado não pode reconstruir a regra do interruptor por conta própria."""
    fonte = rumble_actions._causa_do_alcance_perdido.__globals__
    assert fonte["hefesto_ligado"] is painel.hefesto_ligado
    assert fonte["modo_vivo"] is painel.modo_vivo
    assert "MODOS_LIGADOS" not in fonte, (
        "o recado ganhou a sua própria cópia de MODOS_LIGADOS — a pergunta "
        "voltou a ter dois donos"
    )
    assert {MODE_GAMEPAD, MODE_DESKTOP} == set(painel.MODOS_LIGADOS), (
        "MODOS_LIGADOS mudou de conteúdo e as frases dos ramos não foram "
        f"junto: {painel.MODOS_LIGADOS!r}"
    )
