"""POINT-AND-CLICK-01 — a tabela dos chips e a fileira da tela são a MESMA lista.

O defeito que esta régua fecha: `painel.CHIPS_DA_ESCADA` tinha CINCO linhas e a
página publicada tem QUATRO `data-degrau`. A quinta — `pointclick` — saiu do
desenho em 31/08/2026 por ordem dela (*"nos mockups tira o point and click e
deixa só o navegação."*) e ficou dezessete dias viva na tabela, envenenando
`chips_sem_dono()`, que devolvia um chip que a tela não mostra.

SÃO DUAS PERGUNTAS, e confundi-las é o defeito inteiro:

    1. toda chave de `CHIPS_DA_ESCADA` tem `data-degrau` na página publicada;
    2. toda chave da página está em `CHIPS_DA_ESCADA`.

POR QUE ELA É NECESSÁRIA AO LADO DA TRAVA DE `aba01.py`, e é regra desta casa
ter duas réguas independentes sobre dois objetos: aquela mede a PÁGINA (*"o
Point And Click voltou à fileira"*) e ficava **verde com a linha morta viva na
tabela**, que é o estado que atravessou os dezessete dias.

A PÁGINA É LIDA DO DISCO, nunca digitada — e o recorte tem trava de tamanho,
porque *uma régua que mede 0 caractere passa com qualquer desenho*.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PAGINA = (
    RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
    / "paginas"  # (noqa-acento) nome de PASTA; caminho não leva acento
    / "01-jogar.html"
)

#: O menor tamanho que o corpo da página pode ter para a medição valer. A
#: página publicada tem centenas de KB; 2.000 caracteres é o piso que separa
#: "li o arquivo" de "li um arquivo vazio e passei".
PISO_DO_RECORTE = 2000


def _degraus_da_pagina() -> list[str]:
    corpo = PAGINA.read_text(encoding="utf-8")
    assert len(corpo) >= PISO_DO_RECORTE, (
        f"a página publicada tem {len(corpo)} caracteres — abaixo do piso de "
        f"{PISO_DO_RECORTE}. Uma régua que mede 0 caractere passa com qualquer "
        "desenho, e esta para aqui em vez de dar verde sobre nada."
    )
    return re.findall(r'data-degrau="([^"]+)"', corpo)


def test_todo_chip_da_tabela_tem_lugar_na_fileira_publicada() -> None:
    """A pergunta 1: nenhuma linha fantasma na tabela."""
    from hefesto_dualsense4unix.app.actions.jogar import painel

    da_tabela = [c.chave for c in painel.CHIPS_DA_ESCADA]
    da_pagina = _degraus_da_pagina()

    fantasmas = [chave for chave in da_tabela if chave not in da_pagina]
    assert not fantasmas, (
        f"a tabela `painel.CHIPS_DA_ESCADA` tem {fantasmas} e a página "
        f"publicada não. Uma linha que a tela não mostra envenena "
        "`chips_sem_dono()`, que passa a responder sobre a TABELA quando a "
        f"pergunta é sobre a TELA. A fileira publicada é {da_pagina}."
    )


def test_todo_degrau_da_fileira_esta_na_tabela() -> None:
    """A pergunta 2: nenhum chip na tela sem linha que o descreva.

    É o lado que `degraus_sem_chip()` não cobre: aquela pergunta sobre a ESCADA
    do produto, esta sobre o HTML publicado.
    """
    from hefesto_dualsense4unix.app.actions.jogar import painel

    da_tabela = {c.chave for c in painel.CHIPS_DA_ESCADA}
    orfaos = [chave for chave in _degraus_da_pagina() if chave not in da_tabela]
    assert not orfaos, (
        f"a página publica {orfaos} e a tabela não os conhece — o rótulo, o "
        "algarismo e a ponte de cada um saem de `CHIPS_DA_ESCADA`, então um "
        "chip sem linha é um chip sem dono na primeira leitura de estado."
    )


def test_a_regua_dos_chips_sem_dono_devolve_vazio() -> None:
    """O efeito medido da linha fantasma ter saído.

    Não é redundância com a pergunta 1: aquela compara duas listas, esta cobra
    o VALOR que a tela usa para pintar. Se um chip novo entrar sem ponte e sem
    modo, a pergunta 1 continua verde e esta reprova.
    """
    from hefesto_dualsense4unix.app.actions.jogar import painel

    sem_dono = [c.chave for c in painel.chips_sem_dono()]
    assert sem_dono == [], (
        f"`chips_sem_dono()` devolve {sem_dono}. Se o chip está na tela e não "
        "tem quem o atenda, a marca é legítima e esta régua precisa de nota "
        "datada; se ele NÃO está na tela, é linha fantasma e sai da tabela."
    )


def test_o_gerador_continua_recusando_o_point_and_click_na_fileira() -> None:
    """A trava de `aba01.py` fica de pé, e ela mede OUTRA COISA.

    Ela vigia a PÁGINA; as duas acima vigiam o par página/tabela. Duas réguas
    independentes sobre dois objetos é o que revela o que uma sozinha esconde —
    e foi exatamente assim que a linha fantasma sobreviveu dezessete dias.
    """
    fonte = (
        RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "aba01.py"
    ).read_text(encoding="utf-8")
    assert 'o Point And Click voltou à fileira' in fonte, (
        "a trava do gerador saiu. A ordem dela de 31/08/2026 é que o Point And "
        "Click sai da FILEIRA, e sem a trava a próxima geração pode devolvê-lo "
        "sem ninguém ver."
    )
