#!/usr/bin/env python3
"""A calibração mostra os controles de QUEM A ABRE — zero, um ou quatro.

F3-CALIBRAR, 11/09/2026. A ordem dela é de 11/09 e vale para o produto inteiro:

    *"a ideia é que todas as features mesmo do app funcionem nao so  # (noqa-acento) cita ela
    pra mim mas pra qualquer outro user"*

O DEFEITO QUE ESTA RÉGUA IMPEDE DE VOLTAR, medido no daemon dela em 11/09 com
os dois DualSense na bancada::

    a tela dizia                    o `daemon.state_full` respondia
    P1 · Cosmic Red · USB           P1 · Starlight Blue · USB
    P2 · Starlight Blue · BT        P2 · Cosmic Red · BT
    giro +0.2 / -0.1 / +0.0         `inputs` sem chave `gyro` nenhuma

A lista era `monta.CONECTADOS` — o DESENHO, que tem sempre dois — e os números
eram a constante `calibrar.REPOUSO`. **Com quatro na bancada ela veria dois.**

O QUE CADA TESTE MORDE está no docstring dele. Nenhum número fixo entra aqui
que não venha do dublê: a régua monta a bancada que quer e cobra que a página
mostre EXATAMENTE aquela.
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(INTERFACE))

PAGINA = "calibrar-sensores.html"

#: A BANCADA DE MENTIRA, na faixa sintética da casa (`aa:bb:cc`). Nada de
#: endereço real em arquivo versionado — há dois portões e eles não perdoam.
CORES = ["Starlight Blue", "Cosmic Red", "Galactic Purple", "White"]
SLUGS = ["starlight-blue", "cosmic-red", "galactic-purple", "white"]
VIAS = ["usb", "bt", "bt", "usb"]

#: UM GIRO DIFERENTE POR CONTROLE, e a diferença é o teste: se a página casar o
#: cartão errado com a leitura errada, estes números denunciam. Foi assim que o
#: card do Controle 1 passou a mostrar o registro do Controle 2 em 25/08.
GIRO = [(-12.5, 3.25, 0.75), (48.0, -7.5, 2.0), (-1.0, -2.0, -3.0), (99.0, 0.0, -99.0)]
ACEL = [(0.11, 0.95, 0.20), (-0.30, 0.88, 0.05), (0.0, 1.0, 0.0), (1.9, -1.9, 0.5)]


@pytest.fixture(scope="module")
def pacotes_mod() -> Any:
    import pacotes
    return pacotes


@pytest.fixture(scope="module")
def calibrar_mod() -> Any:
    import calibrar
    return calibrar


def _uniq(i: int) -> str:
    return f"aa:bb:cc:00:00:0{i + 1}"


def _bancada(quantos: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """`(mesa, conectados)` de N controles — a forma que o piloto monta."""
    mesa = [{"pref": f"p{i + 1}", "uniq": _uniq(i), "jogador": i + 1,
             "cor": SLUGS[i], "nome": CORES[i], "via": VIAS[i].upper(),
             "transporte": VIAS[i], "alvo": i == 0, "mascara": "DualSense"}
            for i in range(quantos)]
    conectados = [{
        "uniq": _uniq(i), "player": i + 1, "transport": VIAS[i],
        "is_primary": i == 0, "battery_pct": 90, "connected": True,
        "inputs": {"lx": 128, "ly": 128, "rx": 128, "ry": 128, "l2_raw": 0,
                   "r2_raw": 0, "buttons": [],
                   "gyro": dict(zip("xyz", GIRO[i], strict=True)),
                   "accel": dict(zip("xyz", ACEL[i], strict=True))},
    } for i in range(quantos)]
    return mesa, conectados


def _carga(pacotes_mod: Any, quantos: int) -> dict[str, Any]:
    mesa, conectados = _bancada(quantos)
    ctx = pacotes_mod.Contexto(state={"active_profile": "x"}, mesa=mesa,
                               conectados=conectados, estados={})
    pacote = pacotes_mod.pacote_da_pagina(PAGINA, ctx)
    assert pacote is not None, f"{PAGINA} não tem quem a pinte"
    return pacote


def _html_dos_controles(pacotes_mod: Any, quantos: int) -> str:
    from pacotes import a11_calibrar_sensores as a11
    return str(_carga(pacotes_mod, quantos)["blocos"][a11.BLOCO_DOS_CONTROLES])


# ---------------------------------------------------------------------------
# 1. OS TRÊS CASOS — zero, um e quatro
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("quantos", [0, 1, 2, 4])
def test_a_pagina_mostra_um_cartao_por_controle_conectado(pacotes_mod, quantos):
    """Um cartão por controle da bancada, e NENHUM a mais.

    A MORDIDA: faça `calibrar.controles()` devolver `monta.CONECTADOS` em vez do
    que recebeu — é o que a página fazia até 11/09 — e os casos 0, 1 e 4 caem
    juntos, todos acusando DOIS cartões.
    """
    html = _html_dos_controles(pacotes_mod, quantos)
    cartoes = re.findall(r'<div class="ctr"', html)
    assert len(cartoes) == quantos, (
        f"{quantos} na bancada e {len(cartoes)} cartões na tela")
    lugares = re.findall(r'data-controle="(p\d)"', html)
    assert lugares == [f"p{i + 1}" for i in range(quantos)], (
        f"os lugares da tela não são os da bancada: {lugares}")


def test_sem_controle_a_pagina_diz_o_que_falta_e_nao_desenha_cartao(
        pacotes_mod, calibrar_mod):
    """Zero é estado LEGÍTIMO: uma frase, nenhum cartão, nenhum travessão solto.

    **Linha fantasma é o defeito que esta casa já nomeou sete vezes** — a tela
    afirmando um controle que não está na bancada.

    A MORDIDA: tire o ramo `if not quem` de `calibrar.controles()` e a página
    volta a não dizer nada com a bancada vazia.
    """
    html = _html_dos_controles(pacotes_mod, 0)
    assert "ctr" not in html, "cartão fantasma com a bancada vazia"
    assert calibrar_mod.SEM_CONTROLE in html, "a bancada vazia não diz o que falta"
    # A FRASE DIZ O QUE FAZER, nas palavras do glossário (§1: `cabo` · `rádio`).
    assert "cabo" in calibrar_mod.SEM_CONTROLE and "rádio" in calibrar_mod.SEM_CONTROLE


def test_cada_cartao_recebe_a_leitura_do_seu_proprio_controle(pacotes_mod, calibrar_mod):
    """O número do P3 é o do P3 — e não o do P1, nem o de uma constante.

    A MORDIDA: troque `ctx.por_uniq(...)` por `ctx.conectados[0]` no pacote e os
    quatro cartões passam a mostrar a leitura do primeiro; este teste acusa nos
    três que sobram.
    """
    colunas = _carga(pacotes_mod, 4)["colunas"]
    assert sorted(colunas) == ["p1", "p2", "p3", "p4"]
    # A GRAFIA É A DO DONO, perguntada — nunca redigitada aqui. `texto_eixo`
    # escreve em largura fixa (`+7.1f`) para o painel não "respirar", e um
    # `f"{v:+.1f}"` escrito nesta régua seria a segunda cópia do formato: ela
    # passaria a reprovar a tela no dia em que o dono mudasse de ideia.
    from hefesto_dualsense4unix.app.widgets.sensor_widgets import (
        texto_eixo, texto_eixo_g,
    )
    for i in range(4):
        campos = colunas[f"p{i + 1}"]
        assert campos["giro-x"] == texto_eixo(GIRO[i][0]), (
            f"p{i + 1}: giro-x é {campos['giro-x']!r} e o aparelho disse "
            f"{GIRO[i][0]}")
        assert campos["accel-y"] == texto_eixo_g(ACEL[i][1]), (
            f"p{i + 1}: accel-y é {campos['accel-y']!r} e o aparelho disse "
            f"{ACEL[i][1]}")


def test_sem_leitura_de_sensor_a_tela_escreve_travessao(pacotes_mod, calibrar_mod):
    """Controle SEM `gyro` no `inputs` mostra `—`, nunca zero fingindo repouso.

    **É o caso da bancada dela HOJE**, e não uma hipótese: medido em 11/09, os
    dois controles publicam `sensores.grab_do_movimento = "sem_reader"` e o
    `inputs` sai sem a chave `gyro` até alguém abrir o nó de movimento.

    A MORDIDA: devolva `0.0` no lugar do `None` em `_eixos_do_controle` e a tela
    volta a desenhar repouso onde ninguém leu.
    """
    mesa, conectados = _bancada(1)
    del conectados[0]["inputs"]["gyro"]
    del conectados[0]["inputs"]["accel"]
    ctx = pacotes_mod.Contexto(state={}, mesa=mesa, conectados=conectados, estados={})
    campos = pacotes_mod.pacote_da_pagina(PAGINA, ctx)["colunas"]["p1"]
    for eixo in ("giro-x", "giro-y", "giro-z", "accel-x", "accel-y", "accel-z"):
        assert campos[eixo] == calibrar_mod.SEM_LEITURA, (
            f"{eixo} inventou {campos[eixo]!r} sem leitura nenhuma")
        assert campos[f"{eixo}-neg"] == "0" and campos[f"{eixo}-pos"] == "0"


def test_o_travessao_desta_pagina_e_o_da_casa(calibrar_mod):
    """`calibrar.SEM_LEITURA` e `mesa_viva.SEM_LEITOR` são o MESMO caractere.

    Dois travessões diferentes na mesma tela é a segunda verdade que esta casa
    persegue — e o gerador não pode importar `mesa_viva` (ele roda sozinho, por
    `python3 calibrar.py`), então a cópia se mede por régua.
    """
    import mesa_viva
    assert calibrar_mod.SEM_LEITURA == mesa_viva.SEM_LEITOR


# ---------------------------------------------------------------------------
# 2. A CONCORDÂNCIA — `1 controle` · `2 controles`, nunca `dos 1 controles`
# ---------------------------------------------------------------------------
def test_a_contagem_concorda_com_o_numero(calibrar_mod):
    """O defeito que batizou esta sprint: `calibrar.py:219` escrevia «dos 1 controles».

    A MORDIDA: faça `plural()` devolver sempre o plural e o caso de UM acusa.
    """
    assert calibrar_mod.contagem(1) == "1 controle conectado"
    assert calibrar_mod.contagem(2) == "2 controles conectados"
    assert calibrar_mod.contagem(4) == "4 controles conectados"
    # ZERO NÃO ESCREVE NADA: quem fala é o lugar dos cartões, com a frase
    # inteira. Duas frases para a mesma ausência é a pergunta 4 da vistoria.
    assert calibrar_mod.contagem(0) == ""


def test_a_pagina_nunca_escreve_plural_entre_parenteses(calibrar_mod):
    """`controle(s)` não existe em língua nenhuma além da nossa, e não se traduz."""
    fonte = (INTERFACE / "calibrar.py").read_text(encoding="utf-8")
    fonte += (INTERFACE / "pacotes" / "a11_calibrar_sensores.py").read_text(encoding="utf-8")
    # A PRÓPRIA PROIBIÇÃO NÃO PODE SER A PRIMEIRA OCORRÊNCIA — 11/09/2026, e a
    # armadilha é de PROSA: um comentário que CITA o padrão proibido vira a
    # ocorrência que ele descreve. Por isso a régua monta o padrão em vez de
    # escrevê-lo, e por isso este arquivo não é varrido por ele.
    proibido = "controle" + "(s)"
    assert proibido not in fonte, (
        f"o plural entre parênteses voltou: {proibido!r}")


def test_a_contagem_viva_e_a_do_gerador(pacotes_mod, calibrar_mod):
    """O que o tique escreve no rodapé sai do MESMO dono que o arquivo carrega."""
    for quantos in (0, 1, 2, 4):
        assert _carga(pacotes_mod, quantos)["quantos"] == calibrar_mod.contagem(quantos)


# ---------------------------------------------------------------------------
# 3. O PRODUTO E A PÁGINA FALAM O MESMO ENDEREÇO
# ---------------------------------------------------------------------------
def test_o_seletor_do_bloco_existe_na_pagina_publicada():
    """O `blocos` do pacote e o `data-bloco` do gerador são dois lugares, um fato.

    Um seletor que não casa nada não levanta erro nenhum: o laço do BOOTSTRAP
    faz `if(!alvo) continue`, e a página ficaria com o desenho para sempre — em
    silêncio, que é a forma do defeito de 11 dias que esta sprint curou.
    """
    from pacotes import a11_calibrar_sensores as a11
    publicado = (INTERFACE / "paginas" / PAGINA).read_text(encoding="utf-8")  # noqa-acento: nome de PASTA
    atributo = a11.BLOCO_DOS_CONTROLES.strip("[]")
    assert atributo in publicado, (
        f"o seletor {a11.BLOCO_DOS_CONTROLES} não existe na página publicada")


def test_todo_endereco_que_o_pacote_emite_existe_na_pagina(pacotes_mod):
    """Pacote que pinta num endereço que a página não tem pinta no vazio.

    Foi o buraco que a medição de 01/09 achou: 72 endereços para 172 valores.
    Aqui a conta é a da própria página REMONTADA — o bloco que o pacote emite —,
    porque é ela que o produto mostra depois do primeiro tique.
    """
    carga = _carga(pacotes_mod, 4)
    from pacotes import a11_calibrar_sensores as a11
    html = str(carga["blocos"][a11.BLOCO_DOS_CONTROLES])
    publicado = (INTERFACE / "paginas" / PAGINA).read_text(encoding="utf-8")  # noqa-acento: nome de PASTA
    for campos in carga["colunas"].values():
        for chave in campos:
            assert f'data-campo="{chave}"' in html, (
                f"o pacote escreve {chave!r} e o bloco não tem esse endereço")
    assert 'data-campo="quantos"' in publicado, (
        "a contagem não tem onde pousar na página publicada")


def test_a_pagina_esta_no_despachante(pacotes_mod):
    """Sem `@registrar`, o tique devolve `None` e a página fica com o desenho.

    A MORDIDA: tire o decorador do `pacote()` e esta régua acusa — que é o
    estado em que a calibração viveu de 31/08 a 11/09.
    """
    assert PAGINA in pacotes_mod.PACOTES


def test_o_arquivo_publicado_nao_carrega_leitura_inventada():
    """Nenhum número de sensor mora no HTML: eles nascem no travessão.

    O arquivo ficou ELOQUENTE por onze dias sem ninguém o pintar, e o que estava
    na tela era afirmação. Um arquivo que nasce com número é um arquivo que
    mente quando o tique não vem.
    """
    publicado = (INTERFACE / "paginas" / PAGINA).read_text(encoding="utf-8")  # noqa-acento: nome de PASTA
    for bloco in re.findall(r'<span class="v" data-campo="[^"]+">([^<]*)</span>',
                            publicado):
        assert bloco == "—", f"o arquivo carrega a leitura {bloco!r}"
    assert not re.search(r"^REPOUSO\s*=", (INTERFACE / "calibrar.py").read_text(
        encoding="utf-8"), re.M), "a constante das leituras inventadas voltou"
