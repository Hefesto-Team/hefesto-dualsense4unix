"""A onda do microfone segue o mudo vivo, e não a cena do desenho."""
from __future__ import annotations

import html.parser
import itertools
import os
import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
MOCKUP = RAIZ / "mockup"
PUBLICADO = INTERFACE / "paginas"  # noqa-acento: nome da pasta

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import aba02 as a02_gerador
import mesa_viva
from hefesto_dualsense4unix.interface import onde
from pacotes import Contexto
from pacotes import a02_controles as a02

PAGINAS_COM_CARTAO = (
    "01-jogar.html",
    "02-controles.html",
    "03-gatilhos.html",
    "04-iluminacao.html",
    "05-vibracao.html",
    "06-navegacao.html",
    "08-conexoes.html",
    "calibrar-sensores.html",
)

AINDA_NAO_PUBLICADAS: frozenset[str] = frozenset()

_VAZIOS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
    "param", "source", "track", "wbr",
})


class _Arvore(html.parser.HTMLParser):
    """Os elementos com alvo `classe`, cada um com o cartão que o contém."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._pilha: list[tuple[str, str | None]] = []
        self.achados: list[tuple[str | None, str, str, frozenset[str]]] = []

    def _cartao(self) -> str | None:
        for _tag, controle in reversed(self._pilha):
            if controle is not None:
                return controle
        return None

    def _abrir(self, tag: str, attrs: list[tuple[str, str | None]],
               fecha: bool) -> None:
        a = {k: (v or "") for k, v in attrs}
        controle = a.get("data-controle")
        dono = controle if controle in {"p1", "p2", "p3", "p4"} else None
        if a.get("data-hef-alvo") == "classe" and a.get("data-campo"):
            acesa = a.get("data-hef-classe") or "on"
            resto = frozenset(c for c in a.get("class", "").split() if c != acesa)
            self.achados.append((dono or self._cartao(), a["data-campo"], acesa, resto))
        if not fecha and tag not in _VAZIOS:
            self._pilha.append((tag, dono))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._abrir(tag, attrs, fecha=False)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._abrir(tag, attrs, fecha=True)

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self._pilha) - 1, -1, -1):
            if self._pilha[i][0] == tag:
                del self._pilha[i:]
                return


def _elementos(texto: str) -> list[tuple[str | None, str, str, frozenset[str]]]:
    arvore = _Arvore()
    arvore.feed(texto)
    arvore.close()
    return arvore.achados


def _divergencias(texto: str) -> list[str]:
    """Os endereços cuja classe fora do `data-hef-classe` muda de cartão a cartão."""
    por_campo: dict[str, dict[str, list[tuple[str, ...]]]] = {}
    for cartao, campo, _acesa, resto in _elementos(texto):
        if cartao is None:
            continue
        por_campo.setdefault(campo, {}).setdefault(cartao, []).append(tuple(sorted(resto)))
    ruins = []
    for campo, cartoes in sorted(por_campo.items()):
        if len(cartoes) < 2:
            continue
        if len({tuple(formas) for formas in cartoes.values()}) > 1:
            ruins.append(f"{campo}: {dict(sorted(cartoes.items()))}")
    return ruins


@pytest.mark.parametrize("nome", PAGINAS_COM_CARTAO)
def test_a_bancada_nao_crava_estado_no_que_o_produto_pinta(nome: str) -> None:
    """Em cada página da bancada, a classe de fora do endereço é a mesma em todo cartão."""
    texto = (MOCKUP / nome).read_text(encoding="utf-8")
    assert _divergencias(texto) == []


def test_a_regua_ve_os_quatro_cartoes_da_onda() -> None:
    """Zero cartões não é «nada diverge»: a régua tem de ver a onda nos quatro."""
    texto = (MOCKUP / "02-controles.html").read_text(encoding="utf-8")
    cartoes = {c for c, campo, *_ in _elementos(texto) if campo == f"{a02.LADO_MIC}-onda-lida"}
    assert cartoes == {"p1", "p2", "p3", "p4"}


@pytest.mark.parametrize(
    "nome",
    [
        pytest.param(n, marks=pytest.mark.xfail(
            strict=True, reason="o publicado só muda no --publicar, que é da costura"))
        if n in AINDA_NAO_PUBLICADAS else n
        for n in PAGINAS_COM_CARTAO
    ],
)
def test_o_publicado_nao_crava_estado_no_que_o_produto_pinta(nome: str) -> None:
    """A mesma pergunta no publicado. A 02 fica marcada até o `--publicar 02`."""
    caminho = PUBLICADO / nome
    if not caminho.exists():
        pytest.skip(f"{nome} não está publicada")
    assert _divergencias(caminho.read_text(encoding="utf-8")) == []


def _classes_do(campo: str, trecho: str) -> tuple[str, ...]:
    achado = re.search(r'<span class="([^"]*)" data-campo="' + re.escape(campo) + '"', trecho)
    assert achado, f"`{campo}` não saiu do gerador"
    return tuple(achado.group(1).split())


def test_o_gerador_com_e_sem_o_mudo_da_a_mesma_onda() -> None:
    """A cena mudo e a cena aberta mudam só o invólucro com endereço."""
    vals = [22, 48, 72, 95, 64, 38, 52, 80, 44, 26, 58, 88, 40, 20]
    calado = a02_gerador.onda(vals, True, a02.LADO_MIC)
    aberto = a02_gerador.onda(vals, False, a02.LADO_MIC)
    lida = f"{a02.LADO_MIC}-onda-lida"
    assert _classes_do(lida, calado) == _classes_do(lida, aberto) == ("onda",)
    campo = a02.campo_da_onda_calada(a02.LADO_MIC)
    assert "calada" in _classes_do(campo, calado)
    assert "calada" not in _classes_do(campo, aberto)
    assert set(_classes_do(campo, calado)) - {"calada"} == set(_classes_do(campo, aberto))


UNIQ = "aa:bb:cc:00:00:01"
BASE: dict[str, Any] = {
    "uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
    "battery_pct": 50, "is_primary": True, "inputs": {"buttons": []},
}
MUDO = mesa_viva.selo_do_mic(True, True)


def _card(audio: dict[str, Any]) -> dict[str, Any]:
    """Os campos do card, com os endereços da BANCADA (é lá que o mudo nasce)."""
    doc = onde.pagina("02-controles.html").read_text(encoding="utf-8")
    a02._ENDERECOS = frozenset(re.findall(r'data-campo="([^"]+)"', doc))
    try:
        dele = {**BASE, "audio": audio}
        fora = a02.pacote(Contexto(state={}, mesa=[], conectados=[dele], estados={}))
    finally:
        a02._ENDERECOS = None
    return dict(fora["cards"][UNIQ])


ARRANJOS = [
    {"mic_mudo": firmware, "mic_mudo_desejado": desejo,
     "canal_ativo": ativo, "canal_mudo": canal}
    for firmware, desejo, ativo, canal in itertools.product((False, True), repeat=4)
] + [{}, {"mic_mudo": False}, {"mic_mudo": True}, {"mic_mudo": False, "canal_ativo": True,
                                                   "canal_mudo": None}]


@pytest.mark.parametrize("audio", ARRANJOS)
def test_o_cinza_da_onda_segue_o_selo(audio: dict[str, Any]) -> None:
    """`"sim"` exatamente quando o selo diz MUDO; o «não sei» não acinzenta."""
    card = _card(audio)
    campo = a02.campo_da_onda_calada(a02.LADO_MIC)
    assert campo in card, "o pacote não pinta o endereço do mudo"
    esperado = "sim" if a02.selo_composto(audio) == MUDO else "nao"  # noqa-acento: valor de atributo
    assert card[campo] == esperado, audio


def test_o_endereco_so_sai_quando_a_pagina_o_tem() -> None:
    """Sem o endereço na página publicada, o pacote não o emite (órfão)."""
    a02._ENDERECOS = frozenset({"mic-selo"})
    try:
        dele = {**BASE, "audio": {"mic_mudo": True}}
        fora = a02.pacote(Contexto(state={}, mesa=[], conectados=[dele], estados={}))
    finally:
        a02._ENDERECOS = None
    assert a02.campo_da_onda_calada(a02.LADO_MIC) not in fora["cards"][UNIQ]


_JS_DA_COR = r"""
(function(){
  const envolto = document.querySelectorAll('[data-campo="%(campo)s"]')[%(i)d];
  const onda = envolto.querySelector('.onda');
  const quando = envolto.dataset.hefQuando;
  const classe = envolto.dataset.hefClasse;
  envolto.classList.toggle(classe, '%(valor)s' === quando);
  onda.classList.toggle('sem-leitura', %(sem_leitura)s);
  const barra = onda.querySelector('i');
  const raiz = getComputedStyle(document.documentElement);
  const tinta = (v) => { const d = document.createElement('i');
    d.style.background = raiz.getPropertyValue(v).trim(); document.body.appendChild(d);
    const c = getComputedStyle(d).backgroundColor; d.remove(); return c; };
  return JSON.stringify({fundo: getComputedStyle(barra).backgroundColor,
    opacidade: getComputedStyle(barra).opacity,
    altura: barra.getBoundingClientRect().height,
    caixa: onda.getBoundingClientRect().height,
    cinza: tinta('--border-forte'), ciano: tinta('--cyan')});
})()
"""


def test_o_webkit_pinta_a_onda_pelo_endereco_do_mudo() -> None:
    """Com o endereço em `"sim"` as barras são cinza; em `""`, cianas; sem leitura, cinza e no piso.
    """
    import importlib
    import json

    if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
        pytest.skip("sem servidor gráfico: rode sob `xvfb-run -a`")
    sys.path.insert(0, str(RAIZ / "scripts"))
    try:
        regua_de_tela = importlib.import_module("regua_de_tela")
    except (ImportError, ValueError) as erro:  # pragma: no cover
        pytest.skip(f"o instrumento não importou ({erro})")
    campo = a02.campo_da_onda_calada(a02.LADO_MIC)
    with regua_de_tela.Tela(MOCKUP / "02-controles.html", titulo_esperado="Hefesto") as tela:
        def medir(valor: str, sem_leitura: bool) -> dict[str, Any]:
            bruto = tela.executar(_JS_DA_COR % {
                "campo": campo, "i": 0, "valor": valor,
                "sem_leitura": "true" if sem_leitura else "false"})
            return dict(json.loads(bruto))

        calada = medir("sim", False)
        aberta = medir("", False)
        sem_leitura = medir("", True)
        calada_sem_leitura = medir("sim", True)
    transparente = "rgba(0, 0, 0, 0)"
    assert transparente not in {calada["cinza"], calada["ciano"]}, calada
    assert calada["cinza"] != calada["ciano"], calada
    assert calada["caixa"] > 0, calada
    assert calada["fundo"] == calada["cinza"], calada
    assert aberta["fundo"] == aberta["ciano"], aberta
    assert sem_leitura["fundo"] == sem_leitura["cinza"], sem_leitura
    assert sem_leitura["altura"] <= sem_leitura["caixa"] * 0.2, sem_leitura
    assert calada_sem_leitura == sem_leitura, (calada_sem_leitura, sem_leitura)
    assert calada["opacidade"] != sem_leitura["opacidade"], (calada, sem_leitura)
