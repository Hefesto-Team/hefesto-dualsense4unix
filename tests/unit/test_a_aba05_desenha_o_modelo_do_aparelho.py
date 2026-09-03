#!/usr/bin/env python3
"""A 05 DESENHA O CONTROLE DELA, e não o do mockup — os 28 modelos do mapa.

A LEI, e ela é dela (03/09/2026):

    (noqa-acento: as duas citações abaixo são literais dela)

    "imagina que cada pessoa tenha um dualsense diferente. eu mapeei as cores,
    glifos, controles, id e tudo mais. é pro projeto usar esse meu trabalho
    entende? nada hardcoded."

    "os svgs do dualsense, as bordas das fitas das áreas, as escolhas dos
    players com cada controle — tudo isso muda de acordo com o controle
    identificado no canto superior. é white no p1, mas a borda de tudo é
    cosmic red e os svgs não são os que o meu mapa cataloga. isso tá errado"

A BORDA JÁ OBEDECIA — o alvo `plastico` entrou na manhã de 03/09 e a régua irmã
(`test_a_aba05_veste_a_cor_do_controle_lido`) a vigia. O DESENHO dentro dela,
não: cada `<svg>` nascia com o `data-colorway` da `monta.MESA` e não havia como
reescrevê-lo.

AS DUAS METADES, e uma sem a outra não pinta um pixel:

1. o ENDEREÇO no `<svg>` — `data-campo="colorway"` mais o par
   `data-hef-alvo="atributo"` / `data-hef-atributo="data-colorway"`;
2. a FOLHA DOS 28 publicada na página. `monta._so_o_colorway` guarda dentro de
   cada SVG só as regras do modelo pedido, então escrever `white` num desenho
   que só embute `cosmic-red` **não casa regra nenhuma** e o controle cai nos
   `fill` crus. Sem esta metade, o endereço troca uma cor errada por um cinza.

MEDIDO NO CHROME, com a página desta bancada e os 28 `id` do mapa escritos um a
um no `data-colorway` do P1: **28 de 28 pintam**, nenhum cai no cinza cru
`rgb(58, 63, 75)`, e os doze que pintam por `url(#…)` acham a tinta. Arrancar o
bloco da tinta muda o raster do desenho (15.690 → 12.807 bytes), que é a prova
de que ele não é enfeite.

NENHUMA COR É DIGITADA AQUI: os 28 `id` saem de `docs/data/cores-do-dualsense.csv`,
o HTML sai do gerador e os alvos saem do próprio piloto.
"""
from __future__ import annotations

import csv
import pathlib
import re
import sys
from html.parser import HTMLParser
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# O import do PACOTE é o que põe `interface/` no `sys.path` (`pacotes/__init__`
# faz o `insert`) — a mesma porta pela qual o piloto entra.
from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a05_vibracao

BANCADA = RAIZ / "mockup/05-vibracao.html"
CORES_CSV = RAIZ / "docs/data/cores-do-dualsense.csv"
PILOTO = RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"

#: O colorway que o cabo respondeu, e o do controle que ninguém leu. `""` não é
#: descuido: é o que `mesa_viva.mesa_do_estado` põe quando o mapa de canais diz
#: que aquele transporte não entrega a cor — o caso do rádio, que é metade da
#: mesa dela.
LIDO = "white"
SEM_LEITURA = ""

#: O que o `escrever()` do piloto precisa ver no elemento para trocar o modelo.
ALVO = "atributo"
PARAMETRO = "data-hef-atributo"


def modelos_do_mapa() -> set[str]:
    """Os 28 `id` do CSV dela — `white`, `cosmic-red`, `ghost-of-yotei`…

    É a coluna `id`, e não `nome`: o `id` é o que o
    `scripts/gerar_cores_do_dualsense.py` escreve em `svg[data-colorway="…"]`.
    Digitá-los aqui seria a segunda lista que esse CSV existe para não ter.
    """
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


class _Pagina(HTMLParser):
    """Os elementos com a PILHA de ancestrais, e o texto de cada `<style>`.

    A pilha é o que responde *este `<svg>` está dentro de um lugar vazio?* — a
    pergunta que separa o controle que a mesa tem do lugar que ela não tem. Uma
    régua que olhasse só a tag à esquerda erraria: entre o `<div class="ctrl
    vazia">` e o `<svg>` há a moldura.
    """

    VAZIAS = frozenset([
        "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr",
    ])

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pilha: list[dict[str, str]] = []
        #: `(tag, atributos, classes dos ancestrais)`
        self.elementos: list[tuple[str, dict[str, str], list[str]]] = []
        self.folhas: list[str] = []
        self._folha: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = {k: (v or "") for k, v in attrs}
        heranca = [c for pai in self.pilha
                   for c in (pai.get("class") or "").split()]
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
    """Os `<svg class="ds-svg">` da página, e se cada um está num lugar vazio."""
    return [
        (attrs, "vazia" in heranca)
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


# ---------------------------------------------------------------------------
# 1. O ENDEREÇO — o desenho pode virar outro modelo
# ---------------------------------------------------------------------------
def test_todo_desenho_de_controle_pede_o_alvo_de_atributo() -> None:
    """Os quatro `<svg>` da mesa trazem o par alvo/parâmetro, e o nome certo.

    O NOME DO ATRIBUTO É COBRADO À PARTE, e não é zelo: um
    `data-hef-atributo="data-modelo"` deixa o `escrever()` trocar outra coisa e
    o `data-colorway` fica cravado — presença de string não é funcionamento.

    A CONTA SAI DA PÁGINA: são tantos quantos forem os desenhos de controle que
    a mesa publicar. No dia em que a mesa mudar de tamanho, a régua acompanha em
    vez de reprovar a mudança.
    """
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

    É a regra dela — campo sem informação não mostra nada. Um lugar vazio não
    tem aparelho, logo não tem modelo: afirmar "Galactic Purple" ali é o desenho
    falando por um controle que não existe.

    E NÃO MUDA UM PIXEL, o que foi medido no Chrome antes de ser escrito: o
    `.ctrl.vazia` já pinta as formas com `var(--linha)` e `!important`, e a
    especificidade dele (0,5,1) ganha da regra de zona (0,2,2). Com e sem o
    atributo, a casca dos dois lugares vazios computa `rgb(83, 87, 111)`.

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


# ---------------------------------------------------------------------------
# 2. A FOLHA — os 28 modelos dela, uma vez, na página
# ---------------------------------------------------------------------------
def test_a_pagina_publica_os_28_modelos_dela() -> None:
    """A página traz as regras dos 28 do mapa, e nenhum SVG guarda a podada.

    AS DUAS METADES SÃO A MESMA COISA e por isso moram juntas: enquanto cada
    `<svg>` embutir a folha de UM modelo, o desenho não tem como virar outro; e
    publicar as 28 sem tirar a podada seria carregar a mesma folha cinco vezes.

    A MORDIDA está no fim desta função: com as regras de um modelo só, ela
    acusa — que é o estado em que a página estava até 03/09/2026.
    """
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

    # A MORDIDA, e ela roda toda vez: uma página com as regras de um modelo só é
    # o que esta régua existe para acusar.
    so_um = re.sub(r'svg\[data-colorway="(?!cosmic-red)[^"]+"\][^\n]*\n', "", html)
    assert modelos_do_mapa() - set(
        re.findall(r'svg\[data-colorway="([^"]+)"\]', so_um)), (
        "a régua não acusa uma página com um modelo só — ela não mede nada")


def test_a_tinta_dos_modelos_por_url_existe_na_pagina() -> None:
    """Os `url(#…)` da folha acham o elemento — e ele NÃO é o de um controle.

    Doze dos 28 pintam por referência: a hachura dos que ela não amostrou e os
    dois gradientes de casca. Esses `id` moram no `<defs>` do desenho, e
    `monta.svg()` PREFIXA todo id por controle (`vb-p1-hachura-sem-hex`) — uma
    folha de página que dissesse `url(#hachura-sem-hex)` não acharia nada, e os
    doze ficariam com uma referência morta: nem a cor do aparelho, nem o cinza
    do "não sei", um terceiro estado que não quer dizer nada.

    MEDIDO: arrancar o bloco da tinta do documento muda o raster do desenho em
    `ghost-of-yotei` (15.690 → 12.807 bytes no Chrome desta máquina).
    """
    html = _bancada()
    pedidos = set(re.findall(r"url\(#([^)]+)\)", html))
    assert pedidos, "a folha desta página não pede tinta nenhuma"

    ids = set(re.findall(r'\sid="([^"]+)"', html))
    orfaos = sorted(p for p in pedidos if p not in ids)
    assert not orfaos, (
        f"a folha pede tinta que a página não tem: {orfaos} — os modelos que "
        "pintam por referência ficariam sem casca")


# ---------------------------------------------------------------------------
# 3. O PACOTE — escreve o modelo lido, cala o que não leu
# ---------------------------------------------------------------------------
def test_o_pacote_emite_o_modelo_lido_e_cala_o_que_nao_leu() -> None:
    """`colorway` sai do pacote com o `id` do mapa, ou vazio.

    O VAZIO É METADE DA RÉGUA, e é a metade que a mesa dela exercita todo dia:
    pelo rádio o mapa de canais responde `identidade.cor_do_aparelho = não`, o
    `LeitorDeCor` guarda `None` e o item chega com `cor = ""`. O alvo
    `atributo` APAGA o `data-colorway` nesse caso, e o desenho cai no cinza
    neutro — o controle sem identidade. Um pacote que caísse no colorway do
    mockup manteria o Cosmic Red sobre um aparelho que é outro, que é o defeito
    que esta leva existe para matar.
    """
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
    """O que o pacote emite é um `id` do CSV — nunca um nome de vitrine.

    `mesa_viva.CORES` traduz o código de fábrica no `id` do mapa (`white`), e é
    esse `id` que a folha usa no seletor. Emitir `White` (o `nome`) casaria zero
    regras e apagaria o desenho em silêncio — a mesma classe de defeito que o
    `data-hef-atributo` errado, um andar acima.
    """
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


# ---------------------------------------------------------------------------
# 4. O ELO — o alvo que a página pede é um que o pintor sabe escrever
# ---------------------------------------------------------------------------
def test_o_pintor_sabe_escrever_atributo() -> None:
    """O `escrever()` tem o ramo `atributo`, e ele respeita a guarda de nome.

    É O ELO QUE FAZ ISTO SER ENTREGA E NÃO MAQUIAGEM. Um endereço com um alvo
    que o pintor não implementa deixa a tela igualmente mentindo: o `escrever()`
    cai no ramo padrão e escreve o nome do modelo como TEXTO por cima do
    desenho.

    ELA PODE FICAR VERMELHA POR ESPERA, e isso está declarado: o alvo `atributo`
    nasceu numa frente irmã em 03/09/2026 e chega ao `dev` pelo merge. Enquanto
    não chegar, esta função é o relógio dessa espera — e ela reprova dizendo
    exatamente isso, em vez de deixar a aba parecer pronta.
    """
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
