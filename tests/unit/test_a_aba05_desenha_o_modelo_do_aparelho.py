#!/usr/bin/env python3
"""A 05 DESENHA O CONTROLE DO USUÁRIO, e não o do mockup — os 28 modelos do mapa."""
from __future__ import annotations

import csv
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
from hefesto_dualsense4unix.interface.pacotes import a05_vibracao

BANCADA = RAIZ / "mockup/05-vibracao.html"
CORES_CSV = RAIZ / "docs/data/cores-do-dualsense.csv"
PILOTO = RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"

#: descuido: é o que `mesa_viva.mesa_do_estado` põe quando o mapa de canais diz
LIDO = "white"
SEM_LEITURA = ""

ALVO = "atributo"
PARAMETRO = "data-hef-atributo"


def modelos_do_mapa() -> set[str]:
    """Os 28 `id` do CSV dela — `white`, `cosmic-red`, `ghost-of-yotei`…"""
    linhas = [
        linha
        for linha in CORES_CSV.read_text(encoding="utf-8").splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    ]
    return {
        (linha.get("id") or "").strip()
        for linha in csv.DictReader(linhas)
        if (linha.get("id") or "").strip()
    }


SEM_CONTROLE = "nao"  # (noqa-acento) valor de atributo

#: `data-conectado="nao"` — a mesma que o piloto põe e tira.
MARCA_DO_LUGAR_VAZIO = "lugar-sem-controle"


class _Pagina(HTMLParser):
    """Os elementos com a PILHA de ancestrais, e o texto de cada `<style>`.

    A pilha é o que responde *este `<svg>` está dentro de um lugar vazio?* — a
    pergunta que separa o controle que a mesa tem do lugar que ela não tem. Uma
    régua que olhasse só a tag à esquerda erraria: entre o
    `<div class="ctrl off" data-conectado="nao">` e o `<svg>` há a moldura.
    """

    VAZIAS = frozenset([
        "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr",
    ])

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pilha: list[dict[str, str]] = []
        self.elementos: list[tuple[str, dict[str, str], list[str]]] = []
        self.folhas: list[str] = []
        self._folha: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = {k: (v or "") for k, v in attrs}
        heranca = [c for pai in self.pilha
                   for c in (pai.get("class") or "").split()]
        # classe: é o `data-conectado="nao"`, que é o que o piloto escreve e
        heranca += [MARCA_DO_LUGAR_VAZIO for pai in self.pilha
                    if (pai.get("data-conectado") or "") == SEM_CONTROLE]
        self.elementos.append((tag, d, heranca))
        if tag == "style":
            self._folha = []
        if tag not in self.VAZIAS:
            self.pilha.append(d)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in self.VAZIAS and self.pilha:
            self.pilha.pop()

    def handle_endtag(self, tag: str) -> None:
        if tag == "style" and self._folha is not None:
            self.folhas.append("".join(self._folha))
            self._folha = None
        if tag not in self.VAZIAS and self.pilha:
            self.pilha.pop()

    def handle_data(self, data: str) -> None:
        if self._folha is not None:
            self._folha.append(data)


def _pagina(html: str) -> _Pagina:
    leitor = _Pagina()
    leitor.feed(html)
    return leitor


def _desenhos(html: str) -> list[tuple[dict[str, str], bool]]:
    """Os `<svg class="ds-svg">` da página, e se cada um está num lugar vazio.

    A MARCA DO LUGAR VAZIO MUDOU EM 07/09/2026: era a classe `vazia`, e passou a
    ser a dupla `class="ctrl off"` + `data-conectado="nao"` — as MESMAS marcas
    que o piloto põe e TIRA (`hefesto_vivo._pintar`, passos 1b e 1c). A `vazia`
    morreu porque o piloto não a conhece: um cartão que nascesse com ela ficaria
    cinza para sempre depois que o controle chegasse.

    E A LEITURA TEM DE SEGUIR A MARCA. Procurar `"vazia" in heranca` aqui
    devolveria SEMPRE lista vazia, e a régua daria verde por vacuidade — que é
    o pior desfecho de uma guarda que existe para comparar os dois estados.
    """
    return [
        (attrs, MARCA_DO_LUGAR_VAZIO in heranca)
        for tag, attrs, heranca in _pagina(html).elementos
        if tag == "svg" and "ds-svg" in (attrs.get("class") or "").split()
    ]


def _bancada() -> str:
    return BANCADA.read_text(encoding="utf-8")


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


def test_todo_desenho_de_controle_pede_o_alvo_de_atributo() -> None:
    """Os quatro `<svg>` da mesa trazem o par alvo/parâmetro, e o nome certo."""
    desenhos = _desenhos(_bancada())
    assert desenhos, "a bancada da 05 não tem um desenho de controle sequer"

    sem_endereco = [a.get("data-colorway") for a, _v in desenhos
                    if a.get("data-campo") != "colorway"]
    sem_alvo = [a.get("data-campo") for a, _v in desenhos
                if a.get("data-hef-alvo") != ALVO]
    nome_errado = [a.get(PARAMETRO) for a, _v in desenhos
                   if a.get(PARAMETRO) != "data-colorway"]

    assert not sem_endereco, (
        f"há desenho de controle sem `data-campo=\"colorway\"`: {sem_endereco} "
        "— o pintor não tem por onde trocar o modelo")
    assert not sem_alvo, (
        f"há desenho com endereço e sem o alvo `{ALVO}`: {sem_alvo} — o "
        "`escrever()` cairia no ramo padrão e escreveria o nome do modelo como "
        "TEXTO por cima do desenho")
    assert not nome_errado, (
        f"o `{PARAMETRO}` não nomeia `data-colorway`: {nome_errado}")


def test_o_lugar_vazio_nao_afirma_modelo_nenhum() -> None:
    """O `<svg>` de um lugar sem controle sai SEM `data-colorway`.

    É a regra de produto — campo sem informação não mostra nada. Um lugar vazio não
    tem aparelho, logo não tem modelo: afirmar "Galactic Purple" ali é o desenho
    falando por um controle que não existe.

    E NÃO MUDA UM PIXEL, o que foi medido no Chrome antes de ser escrito: o
    lugar sem controle não mostra desenho nenhum — quem responde por isso é a
    folha COMPARTILHADA (`monta.py`, a S-04 de 05/09/2026, ), com
    `[data-controle][data-conectado="nao"] .ds-svg{visibility:hidden}`. Medido
    em 07/09/2026 com a fusão dos dois ramos de coluna: o PNG da aba saiu
    **byte a byte idêntico** ao de antes.

    O ENDEREÇO FICA, e isso é o par desta função: o dia em que um terceiro
    controle entrar na mesa, o pintor tem onde escrever o modelo dele.
    """
    vazios = [a for a, vazio in _desenhos(_bancada()) if vazio]
    cheios = [a for a, vazio in _desenhos(_bancada()) if not vazio]
    assert vazios and cheios, (
        "a mesa do desenho deixou de ter lugar vazio E lugar com controle — "
        "esta régua compara os dois")

    afirmam = [a.get("data-colorway") for a in vazios if "data-colorway" in a]
    assert not afirmam, (
        f"um lugar vazio afirma um modelo de controle: {afirmam}")
    assert all("data-campo" in a for a in vazios), (
        "o lugar vazio perdeu o endereço da cor — quando um controle chegar "
        "nele, o desenho continuará cinza")

    mudos = [a.get("class") for a in cheios if not a.get("data-colorway")]
    assert not mudos, (
        f"um lugar COM controle deixou de trazer o modelo do desenho: {mudos}")


def test_a_pagina_publica_os_28_modelos_dela() -> None:
    """A página traz as regras dos 28 do mapa, e nenhum SVG guarda a podada."""
    html = _bancada()
    esperados = modelos_do_mapa()
    assert len(esperados) >= 28, (
        f"o mapa dela encolheu para {len(esperados)} modelos")

    declarados = set(re.findall(r'svg\[data-colorway="([^"]+)"\]', html))
    faltam = esperados - declarados
    assert not faltam, (
        f"a página não publica {len(faltam)} dos modelos dela: {sorted(faltam)}"
        " — escrever um deles no `data-colorway` não casaria regra nenhuma e o"
        " desenho cairia no cinza cru")

    podadas = re.findall(r'<style id="[^"]*cores-do-dualsense-folha"', html)
    assert not podadas, (
        f"{len(podadas)} desenho(s) ainda carregam a folha de um modelo só")

    so_um = re.sub(r'svg\[data-colorway="(?!cosmic-red)[^"]+"\][^\n]*\n', "", html)
    assert modelos_do_mapa() - set(
        re.findall(r'svg\[data-colorway="([^"]+)"\]', so_um)), (
        "a régua não acusa uma página com um modelo só — ela não mede nada")


def test_a_tinta_dos_modelos_por_url_existe_na_pagina() -> None:
    """Os `url(#…)` da folha acham o elemento — e ele NÃO é o de um controle."""
    html = _bancada()
    pedidos = set(re.findall(r"url\(#([^)]+)\)", html))
    assert pedidos, "a folha desta página não pede tinta nenhuma"

    ids = set(re.findall(r'\sid="([^"]+)"', html))
    orfaos = sorted(p for p in pedidos if p not in ids)
    assert not orfaos, (
        f"a folha pede tinta que a página não tem: {orfaos} — os modelos que "
        "pintam por referência ficariam sem casca")


def test_o_pacote_emite_o_modelo_lido_e_cala_o_que_nao_leu() -> None:
    """`colorway` sai do pacote com o `id` do mapa, ou vazio."""
    mesa = _mesa(LIDO, SEM_LEITURA)
    ctx = Contexto(
        state={"controllers": []},
        mesa=mesa,
        conectados=[{"uniq": c["uniq"], "transport": c["transporte"]} for c in mesa],
        estados={},
    )
    colunas = a05_vibracao.pacote(ctx).get("colunas") or {}
    assert set(colunas) == {c["uniq"] for c in mesa}, (
        f"as colunas do pacote não são as da mesa: {sorted(colunas)}")

    lido, sem = mesa[0]["uniq"], mesa[1]["uniq"]
    assert colunas[lido].get("colorway") == LIDO, (
        "a coluna do controle lido não recebeu o modelo dele: "
        f"{colunas[lido].get('colorway')!r}")
    assert colunas[sem].get("colorway") == "", (
        "a coluna do controle sem cor legível recebeu um modelo — o pacote "
        f"inventou o que ninguém leu: {colunas[sem].get('colorway')!r}")


def test_o_modelo_emitido_e_um_dos_do_mapa_dela() -> None:
    """O que o pacote emite é um `id` do CSV — nunca um nome de vitrine."""
    conhecidos = modelos_do_mapa()
    for slug in sorted(conhecidos)[:6] + sorted(conhecidos)[-6:]:
        mesa = _mesa(slug)
        ctx = Contexto(
            state={"controllers": []},
            mesa=mesa,
            conectados=[{"uniq": mesa[0]["uniq"], "transport": "usb"}],
            estados={},
        )
        colunas = a05_vibracao.pacote(ctx).get("colunas") or {}
        emitido = colunas[mesa[0]["uniq"]].get("colorway")
        assert emitido in conhecidos, (
            f"o pacote emitiu {emitido!r}, que não é um modelo do mapa dela")


def test_o_pintor_sabe_escrever_atributo() -> None:
    """O `escrever()` tem o ramo `atributo`, e ele respeita a guarda de nome."""
    fonte = PILOTO.read_text(encoding="utf-8")
    sabidos = set(re.findall(r"alvo === '([a-z]+)'", fonte))
    assert ALVO in sabidos, (
        f"o piloto não escreve o alvo `{ALVO}` — os quatro desenhos da 05 têm "
        "endereço e nenhum troca de modelo. Ele vem da frente base de "
        "03/09/2026 (`hefesto_vivo.escrever`), e até o merge esta aba está "
        f"endereçada e muda. Alvos que ele conhece: {sorted(sabidos)}")
    assert "atributo_escrevivel" in fonte, (
        "o ramo `atributo` perdeu a guarda de nome — um "
        "`data-hef-atributo=\"data-hef-visto\"` forjaria o selo com que esta "
        "casa decide um INDECIDÍVEL")
