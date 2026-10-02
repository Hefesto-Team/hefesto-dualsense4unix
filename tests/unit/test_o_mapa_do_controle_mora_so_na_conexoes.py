"""O «Mapa do controle» mora só na aba Conexões."""
from __future__ import annotations

import html.parser
import importlib.util
import pathlib
import re
import sys

from hefesto_dualsense4unix.interface import onde

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MAPA = "mapa-do-controle.html"

CASA = ("08-conexoes.html", "btn", "ferramentas")

_VAZIAS = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input",
                     "link", "meta", "source", "track", "wbr"})


def _declaradas() -> set[str]:
    alvo = RAIZ / "scripts/check_o_desenho_aprovado.py"
    spec = importlib.util.spec_from_file_location("check_desenho_da_casa_do_mapa", alvo)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_desenho_da_casa_do_mapa"] = mod
    spec.loader.exec_module(mod)
    return set(mod.declaradas())


def _paginas() -> list[pathlib.Path]:
    em_trabalho = _declaradas()
    return [onde.BANCADA / p.name if p.name in em_trabalho else p
            for p in onde.paginas(publicado=True)]


class _PortasDoMapa(html.parser.HTMLParser):
    """Cada link para o mapa, com a classe dele e as classes dos ancestrais."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pilha: list[tuple[str, set[str]]] = []
        self.portas: list[tuple[str, set[str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        classes = set((a.get("class") or "").split())
        if a.get("href") == MAPA:
            acima: set[str] = set()
            for _, c in self.pilha:
                acima |= c
            self.portas.append((" ".join(sorted(classes)), acima))
        if tag not in _VAZIAS:
            self.pilha.append((tag, classes))

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self.pilha) - 1, -1, -1):
            if self.pilha[i][0] == tag:
                del self.pilha[i:]
                return


def _portas() -> dict[str, list[tuple[str, set[str]]]]:
    fora = {}
    for pagina in _paginas():
        if pagina.name == MAPA:
            continue
        leitor = _PortasDoMapa()
        leitor.feed(pagina.read_text(encoding="utf-8"))
        if leitor.portas:
            fora[pagina.name] = leitor.portas
    return fora


def test_o_mapa_mora_so_na_conexoes() -> None:
    portas = _portas()
    pagina, classe, fileira = CASA
    fora_de_casa = sorted(set(portas) - {pagina})
    assert not fora_de_casa, (
        f"o Mapa do controle mora só na aba Conexões (decisão dela, 29/09) e "
        f"ainda se abre por: {fora_de_casa}")
    na_casa = portas.get(pagina, [])
    assert len(na_casa) == 1, (
        f"a casa ficou sem a porta do mapa (ou com {len(na_casa)}): {na_casa}")
    classes, acima = na_casa[0]
    assert classe in classes.split() and fileira in acima, (
        f"a porta da {pagina} não é o `a.{classe}` da `.{fileira}`: "
        f"classe {classes!r}, dentro de {sorted(acima)}")


def test_o_voltar_do_mapa_tem_a_casa_como_reserva() -> None:
    casa = sorted(_portas())
    assert len(casa) == 1, casa
    mapa = next(p for p in _paginas() if p.name == MAPA)
    achado = re.search(r'<a class="voltar" href="([^"]+)"', mapa.read_text(encoding="utf-8"))
    assert achado, "o mapa perdeu o «← Voltar»"
    assert achado.group(1) == casa[0], (
        f"a reserva do «← Voltar» é {achado.group(1)!r}, e a casa do mapa é {casa[0]!r}")
