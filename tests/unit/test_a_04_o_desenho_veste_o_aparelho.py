#!/usr/bin/env python3
"""O DESENHO DA 04 VESTE O APARELHO — e o mapa dela cabe inteiro na página.

A LEI, e ela é dela (03/09/2026):

    "imagina que cada pessoa tenha um dualsense diferente. eu mapeei as cores,
     glifos, controles, id e tudo mais. é pro projeto usar esse meu trabalho
     (…) nada hardcoded."

    "os svgs do dualsense, as bordas das fitas das áreas, as escolhas dos
     players com cada controle — tudo isso muda de acordo com o controle
     identificado no canto superior. é white no p1, mas a borda de tudo é
     cosmic red e os svgs não são os que o meu mapa cataloga. isso tá errado"
     (noqa-acento: citação literal)

O DEFEITO ESTAVA FOTOGRAFADO antes desta régua existir. Com a mesa dela — um
White no cabo e um Galactic Purple no rádio — a `04-iluminacao` mostrava, com
três centímetros entre uma coisa e a outra::

    rótulo da coluna (lido do aparelho)     P1 • White • USB
    DualSense desenhado dentro da moldura   cosmic-red
    rótulo da coluna (lido do aparelho)     P2 • Galactic Purple • BT
    DualSense desenhado dentro da moldura   starlight-blue

A moldura já vestia o aparelho (`data-campo="plastico"`, alvo `cor`) e a fileira
de números também (o anel do dono, pelo alvo `html`). O que continuava do MOCKUP
era o maior objeto da tela: o próprio desenho, 146 px de altura por coluna.

SÃO QUATRO METADES, e cada uma sem as outras não pinta nada:

1. o ENDEREÇO existe no desenho, com o alvo que escreve ATRIBUTO — é o
   `data-colorway` que escolhe o modelo na folha de cores;
2. a FOLHA da página conhece os VINTE E OITO do mapa dela, e não os quatro do
   desenho — `monta._so_o_colorway` guarda dentro de cada SVG só as regras do
   modelo pedido, e escrever `galactic-purple` num SVG que só conhece
   `starlight-blue` dá o cinza neutro de um desenho sem identidade;
3. os FUNDOS que a folha pede existem na página — três modelos pintam com
   `url(#…)`, e um `url()` que não acha alvo pinta NADA em silêncio;
4. o PACOTE escreve o colorway que leu, e **cala** o que ninguém leu.

NENHUMA DELAS DIGITA O QUE DEVIA LER: os modelos esperados saem do
`ds_limpo.svg`, que é onde `scripts/gerar_cores_do_dualsense.py` escreve o
`docs/data/cores-do-dualsense.csv`; os alvos do pintor saem do próprio
`hefesto_vivo.py`; e o HTML sai do gerador, nunca de uma cópia colada aqui.
"""
from __future__ import annotations

import pathlib
import re
import sys
from html.parser import HTMLParser
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

for _p in (str(RAIZ / "src"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao

import monta

BANCADA = RAIZ / "mockup/04-iluminacao.html"
PILOTO = RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"

#: `""` NÃO é descuido: é o que `mesa_viva.mesa_do_estado` põe quando o mapa de
LIDO = "white"
SEM_LEITURA = ""

def _colorway_do_desenho() -> str:
    for tag, attrs in _elementos(BANCADA):
        if tag == "svg" and attrs.get("data-campo") == "desenho":
            return attrs.get("data-colorway", "")
    return ""


class _Elementos(HTMLParser):
    """Os elementos da página com os atributos de cada um, em ordem."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.achados: list[tuple[str, dict[str, str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.achados.append((tag, {k: (v or "") for k, v in attrs}))

    handle_startendtag = handle_starttag


def _elementos(caminho: pathlib.Path) -> list[tuple[str, dict[str, str]]]:
    leitor = _Elementos()
    leitor.feed(caminho.read_text(encoding="utf-8"))
    return leitor.achados


def _modelos_do_mapa() -> set[str]:
    """Os colorways que o mapa DELA cataloga, lidos de onde o gerador os escreve."""
    return set(re.findall(r'svg\[data-colorway="([a-z0-9-]+)"\]', monta.DS))


def _mesa(*cores: str) -> list[dict[str, Any]]:
    """Uma mesa de mentira, na forma que `mesa_viva.mesa_do_estado` devolve."""
    return [
        {
            "pref": f"p{i}",
            "uniq": f"{i}" * 12,
            "jogador": i,
            "cor": cor,
            "nome": "White" if cor else "Não sei",
            "via": "USB" if i == 1 else "BT",
            "transporte": "usb" if i == 1 else "bt",
            "alvo": i == 1,
            "mascara": "DualSense",
        }
        for i, cor in enumerate(cores, start=1)
    ]


def _contexto(mesa: list[dict[str, Any]]) -> Contexto:
    return Contexto(
        state={"controllers": []},
        mesa=mesa,
        conectados=[{"uniq": c["uniq"], "transport": c["transporte"]} for c in mesa],
        estados={},
    )


def test_o_desenho_de_cada_coluna_conectada_pede_o_alvo_do_atributo() -> None:
    """Cada `<svg>` de coluna conectada traz os TRÊS atributos, e o vazio nenhum."""
    elementos = _elementos(BANCADA)
    conectadas = [
        a for _t, a in elementos
        if "ctrl" in (a.get("class") or "").split()
        and "vazia" not in (a.get("class") or "").split()
    ]
    desenhos = [
        a for tag, a in elementos
        if tag == "svg" and "ds-svg" in (a.get("class") or "").split()
    ]
    declarados = [a for a in desenhos if a.get("data-campo") == "desenho"]
    vestidos = [
        a for a in declarados
        if a.get("data-hef-alvo") == a04_iluminacao.ALVO_DO_DESENHO
        and a.get("data-hef-atributo") == "data-colorway"
    ]

    assert conectadas, "a bancada da 04 não tem uma coluna de controle sequer"

    # a desenhar as QUATRO colunas (o foco dela são quatro DualSense), com as
    assert declarados, "nenhum `<svg>` da bancada declara `data-campo=desenho`"
    assert len(vestidos) == len(declarados), (
        f"{len(declarados)} desenhos declarados e só {len(vestidos)} com o "
        "endereço COMPLETO — um `data-campo=desenho` sem `data-hef-alvo` faz o "
        "pintor escrever texto dentro do `<svg>` e apagar o desenho")
    assert len(conectadas) <= len(declarados), (
        "há coluna conectada sem desenho declarado")

    com_colorway = [a for a in desenhos if a.get("data-colorway")]
    assert len(com_colorway) == len(conectadas), (
        "há `data-colorway` num desenho sem aparelho — identidade do mockup "
        f"parada num lugar vazio: {len(com_colorway)} de {len(declarados)}")


def test_a_pagina_conhece_todos_os_modelos_que_ela_mapeou() -> None:
    """Os colorways da página são os do mapa dela, e o bloco aparece UMA vez."""
    html = BANCADA.read_text(encoding="utf-8")
    assert html.count('id="cores-do-dualsense"') == 1, (
        "as cores do mapa não estão UMA vez na página — ou voltaram para dentro "
        "dos SVGs (cada desenho sabendo pintar um modelo só), ou saíram de vez")

    na_pagina = set(re.findall(r'svg\[data-colorway="([a-z0-9-]+)"\]', html))
    do_mapa = _modelos_do_mapa()
    assert do_mapa, "o `ds_limpo.svg` não traz colorway nenhum — mapa vazio"
    assert na_pagina == do_mapa, (
        "a página não conhece o mapa dela inteiro. Falta: "
        f"{sorted(do_mapa - na_pagina)}; sobra: {sorted(na_pagina - do_mapa)}")


def test_todo_fundo_que_a_folha_pede_existe_na_pagina() -> None:
    """Nenhum `url(#id)` da página aponta para um id que ela não tem."""
    html = BANCADA.read_text(encoding="utf-8")
    ids = set(re.findall(r'id="([^"]+)"', html))
    pedidos = set(re.findall(r"url\(#([a-zA-Z0-9_-]+)\)", html))
    orfaos = sorted(pedidos - ids)
    assert not orfaos, (
        f"a página pede fundos que ela não tem: {orfaos} — o modelo que usa "
        "cada um deles pinta NADA, sem erro e sem aviso")


def test_o_pacote_veste_o_colorway_lido_e_nao_inventa_o_que_faltou(monkeypatch) -> None:
    """`desenho` sai com o colorway do APARELHO, ou vazio."""
    monkeypatch.setattr(a04_iluminacao, "_PINTA_O_DESENHO", True)
    mesa = _mesa(LIDO, SEM_LEITURA)
    colunas = a04_iluminacao.pacote(_contexto(mesa)).get("colunas") or {}
    assert set(colunas) == {c["uniq"] for c in mesa}, (
        f"as colunas do pacote não são as da mesa: {sorted(colunas)}")

    campo = a04_iluminacao.CAMPO_DO_DESENHO
    lido, sem = mesa[0]["uniq"], mesa[1]["uniq"]
    assert colunas[lido].get(campo) == LIDO, (
        "a coluna do controle lido não recebeu o colorway dele: "
        f"{colunas[lido].get(campo)!r}")
    assert _colorway_do_desenho() != LIDO, (
        "o colorway lido é o mesmo que o desenho crava — esta régua não mede "
        "nada assim; troque a mesa de mentira")
    assert colunas[sem].get(campo) == "", (
        "a coluna do controle sem cor legível recebeu um colorway — o pacote "
        f"inventou o que ninguém leu: {colunas[sem].get(campo)!r}")


def test_o_pacote_nao_manda_o_desenho_para_quem_nao_sabe_receber(monkeypatch) -> None:
    """Sem página com o endereço, ou sem pintor com o alvo, o campo NÃO sai.

    O DESENHO E O PACOTE CHEGAM AO PRODUTO EM TEMPOS DIFERENTES — é a régua
    `test_o_pacote_cabe_na_pagina_publicada`, e as três frentes devolvidas em
    02/09 que a fizeram nascer. Aqui a consequência de errar é a pior desta aba:
    com o endereço na página e o alvo faltando no pintor, `escrever()` cai no
    ramo padrão e escreve o colorway como TEXTO dentro do `<svg>` — o DualSense
    de 146 px some da tela dela e vira a palavra `white`.

    ELE FALHA FECHADO de propósito: qualquer coisa que a guarda não reconheça
    vira "não emita".
    """
    monkeypatch.setattr(a04_iluminacao, "_PINTA_O_DESENHO", False)
    colunas = a04_iluminacao.pacote(_contexto(_mesa(LIDO))).get("colunas") or {}
    assert colunas, "o pacote parou de emitir coluna nenhuma"
    for uniq, vals in colunas.items():
        assert a04_iluminacao.CAMPO_DO_DESENHO not in vals, (
            f"a coluna {uniq} recebeu o colorway com a pintura fora de alcance — "
            "é assim que o desenho vira uma palavra na tela dela")


def test_nenhum_alvo_da_04_chega_ao_pintor_sem_ele_saber_escrever() -> None:
    """Todo `data-hef-alvo` da bancada, ou o pintor escreve, ou a guarda barra."""
    pedidos = {
        a["data-hef-alvo"] for _t, a in _elementos(BANCADA) if a.get("data-hef-alvo")
    }
    sabidos = set(re.findall(r"alvo === '([a-z]+)'", PILOTO.read_text(encoding="utf-8")))
    sabidos.add("texto")

    assert a04_iluminacao.ALVO_DO_DESENHO in pedidos, (
        "a bancada da 04 deixou de pedir o alvo do atributo — o desenho voltou "
        "a ser o do mockup")
    desconhecidos = pedidos - sabidos
    assert desconhecidos <= {a04_iluminacao.ALVO_DO_DESENHO}, (
        f"a página pede alvo que o pintor não escreve: {sorted(desconhecidos)}")
    if desconhecidos:
        assert not a04_iluminacao.a_pintura_alcanca_o_desenho(), (
            "o pintor ainda não tem o alvo `atributo` e a guarda deixou o campo "
            "passar — publicada, esta aba apagaria o desenho do controle")
