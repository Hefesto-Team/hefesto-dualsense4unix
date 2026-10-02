"""Todo botão da tela começa com maiúscula."""
from __future__ import annotations

import html.parser
import importlib.util
import pathlib
import sys

from hefesto_dualsense4unix.interface import onde

RAIZ = pathlib.Path(__file__).resolve().parents[2]


def _declaradas() -> set[str]:
    """As páginas em trabalho na bancada, perguntado ao portão `desenho-aprovado`."""
    alvo = RAIZ / "scripts/check_o_desenho_aprovado.py"
    spec = importlib.util.spec_from_file_location("check_desenho_da_maiuscula", alvo)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_desenho_da_maiuscula"] = mod
    spec.loader.exec_module(mod)
    return set(mod.declaradas())


class _Rotulos(html.parser.HTMLParser):
    """O texto visível de cada `<button>` e de cada `<a class=…>`."""

    MUDOS = ("script", "style", "svg")

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.abertos: list[tuple[str, str, list[str]]] = []
        self.mudo = 0
        self.rotulos: list[tuple[str, str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.MUDOS:
            self.mudo += 1
        classe = dict(attrs).get("class") or ""
        if tag == "button" or (tag == "a" and classe):
            self.abertos.append((tag, classe, []))

    def handle_endtag(self, tag: str) -> None:
        if tag in self.MUDOS:
            self.mudo = max(0, self.mudo - 1)
        if self.abertos and tag == self.abertos[-1][0]:
            nome, classe, pedacos = self.abertos.pop()
            texto = " ".join("".join(pedacos).split())
            if texto:
                self.rotulos.append((nome, classe, texto))
            if self.abertos:
                self.abertos[-1][2].append("".join(pedacos))

    def handle_data(self, data: str) -> None:
        if self.abertos and not self.mudo:
            self.abertos[-1][2].append(data)


def _paginas() -> list[pathlib.Path]:
    em_trabalho = _declaradas()
    return [onde.BANCADA / p.name if p.name in em_trabalho else p
            for p in onde.paginas(publicado=True)]


def test_ha_rotulo_para_medir() -> None:
    """Uma leitura que não acha botão nenhum seria verde por vacuidade."""
    total = 0
    for pagina in _paginas():
        leitor = _Rotulos()
        leitor.feed(pagina.read_text(encoding="utf-8"))
        total += len(leitor.rotulos)
    assert total > 400, f"só {total} rótulos nas páginas da tela: o leitor ficou cego"


def test_todo_botao_comeca_com_maiuscula() -> None:
    minusculos = []
    for pagina in _paginas():
        leitor = _Rotulos()
        leitor.feed(pagina.read_text(encoding="utf-8"))
        for tag, classe, texto in leitor.rotulos:
            primeiro = texto[0]
            if primeiro.isalpha() and primeiro.islower():
                origem = "bancada" if pagina.parent == onde.BANCADA else "publicada"
                minusculos.append(f"{pagina.name} ({origem}): <{tag} class={classe!r}> «{texto}»")
    assert not minusculos, (
        "botão que começa com minúscula (a regra dela da primeira letra):\n  "
        + "\n  ".join(minusculos))
