"""T-14 (SISTEMA-O-VIGIA-VIVO-01) — receita da máquina, ou perfil do jogo?

`profiles/schema.py` não tem **nenhum** campo alimentado pela aba Sistema. O
único ponto de contato é `PonteConfirmada.steam_input`, que é **carimbo** e
não escolha — quem o escreve é `profiles/manager.confirmar_ponte`, e o único
chamador real é `daemon/launch_env.py`.

Isso quer dizer que a aba inteira fica de fora da receita do jogo: doze
gestos, e nenhum deles viaja com o perfil. **A decisão é dela** (a D-A do
plano): se o lado "do jogo" entrar, esta aba vira parte da receita do jogo.

Este portão **não toma essa decisão**. Ele impede o que está antes dela: um
gesto novo nascer sem que ninguém tenha perguntado de quem ele é. A pergunta
que ele obriga a responder é verificável, e não depende do gosto de ninguém —
*o estado deste gesto é gravado por jogo, ou uma vez para a máquina inteira?*

A declaração mora no PRODUTO (`daemon_actions.DONO_DO_GESTO`), não aqui: é
ela que a próxima pessoa lê ao acrescentar um botão, e é ela que a mantenedora
vai conferir quando decidir a D-A.

**Aguarda o olho dela:** as duas linhas marcadas `PROVISÓRIO` — o "Deixar
tudo pronto" e o "Aplicar aos jogos da Steam" escrevem estado POR JOGO
(a opção de inicialização de cada um) sem que exista um jogo escolhido. Foram
lidos como da máquina *pelo que fazem hoje*; a leitura é minha, e a decisão
é dela.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.actions.daemon_actions import (
    DA_MAQUINA,
    DO_JOGO,
    DONO_DO_GESTO,
)

RAIZ = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("gesto", sorted(DONO_DO_GESTO))
def test_a_declaracao_tem_valor_valido_e_evidencia(gesto: str) -> None:
    """Declarar "máquina" sem dizer por quê é declarar nada.

    A evidência é o que permite ela DISCORDAR de uma linha sem ter de ler o
    código — e é o que separa esta tabela de um palpite organizado.
    """
    dono, evidencia = DONO_DO_GESTO[gesto]

    assert dono in (DO_JOGO, DA_MAQUINA), (gesto, dono)
    assert len(evidencia) >= 20, f"{gesto}: evidência curta demais: {evidencia!r}"


def test_os_tres_gestos_que_a_sprint_leu_como_do_jogo() -> None:
    """A leitura da sprint, travada: marca do Steam Input, Proton, camadas.

    *"O que é do JOGO (marca do Steam Input, Proton por jogo, camadas por
    prefixo) tem lugar no perfil; o que é da MÁQUINA (autostart, WirePlumber,
    quirk de áudio) não tem."*

    Se alguém reclassificar um dos três sem passar por ela, isto reprova — e
    a reclassificação é justamente o conteúdo da decisão D-A.
    """
    do_jogo = {g for g, (dono, _) in DONO_DO_GESTO.items() if dono == DO_JOGO}

    assert do_jogo == {
        "btn_steam_game_broken",
        "btn_proton_lock",
        "btn_camadas_engasgo",
    }


def test_o_perfil_continua_sem_um_campo_desta_aba() -> None:
    """A medição que dá sentido a tudo isto — e que vai caducar um dia.

    Hoje o `Profile` não tem campo nenhum alimentado pela aba Sistema. No dia
    em que a D-A for decidida e o primeiro campo entrar, este teste reprova e
    obriga quem entrou a atualizar a leitura acima em vez de deixar a tabela
    contando uma história velha.
    """
    from hefesto_dualsense4unix.profiles import schema

    fonte = Path(schema.__file__).read_text(encoding="utf-8")

    assert "class PonteConfirmada" in fonte
    for gesto in DONO_DO_GESTO:
        assert gesto not in fonte, (
            f"{gesto} apareceu em profiles/schema.py — a aba Sistema entrou "
            "no perfil. Se foi decisão dela, atualize a leitura de "
            "`DONO_DO_GESTO` e este teste; se não foi, é a decisão D-A "
            "sendo tomada sem ela."
        )
