"""O que vai no pacote e o que o install grava não trazem adaptador nem endereço reais.

Os títulos de jogo moram na régua `scripts/check_a_biblioteca_pessoal_fica_fora.py`.

Vale para toda constante de texto do `src/`, docstring incluída, para os arquivos de `assets/` e
para o catálogo de tradução que vai no pacote.
O catálogo de `assets/estilos_de_jogo/` fica de fora: é dado do produto, que casa a janela de
qualquer jogo. O `antes=` do gerador do mapa também: ele casa com a origem congelada.
"""

from __future__ import annotations

import ast
import gettext
import importlib.util
import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"
ASSETS = RAIZ / "assets"

ADAPTADORES = (r"TP-Link|\bUB500\b|\bUH700\b|\bAX211\b|Archer T3U|\bC920\b|USB-BT500"
               r"|\b2357[:-][0-9a-f]{4}\b|\b25a7:fa07\b|\b3554:fa09\b|\b258a:010c\b")
OUIS = ("d8.44.89", "a0.fa.9c", "e4.17.d8", "e0.f6.b5", "48.b2.5d", "14.3a.9a", "d4.2f.4b",
        "44.46.48", "ac.a7.f1")
ENDERECOS = r"\b(?:" + "|".join(OUIS) + r")[:_-][0-9a-f]{2}[:_-][0-9a-f]{2}[:_-][0-9a-f]{2}\b"
IDS = (r"(?<!\d)(?:1971870|1245620|1358160|2380050|3357650|1599660|2497900|2111190|851100"
       r"|1088850|2054970)(?!\d)")
LUGAR = (
    r"máquina de teste|\buid 1000\b|/mnt/Apate|/home/[a-z]|[Rr]itual-Aurora|Fronteira Aurora"
    r"|precedente da Aurora|a Aurora (?:cobre|sair)|journal do ensaio|\baurora-[a-z]"
)
PROIBIDO = {
    "adaptador": re.compile(ADAPTADORES),
    "endereço": re.compile(ENDERECOS, re.I),
    "id de jogo": re.compile(IDS),
    "lugar": re.compile(LUGAR, re.I),
}
ID_NA_JANELA = re.compile(r"(?:steam_app_|umu-)(\d{5,})")
FONTES_DE_KERNEL = (".c", ".h", ".patch", ".dtsi")
SEM_TEXTO = (".png", ".svg", ".ttf", ".woff2", ".jpg", ".wav", ".ogg", ".ico", ".mo", ".pyc")


def _faixa_ficticia() -> range:
    caminho = RAIZ / "scripts" / "check_a_biblioteca_pessoal_fica_fora.py"
    spec = importlib.util.spec_from_file_location("regua_da_biblioteca", caminho)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.APPID_FICTICIO


FAIXA_FICTICIA = _faixa_ficticia()


def _acha(texto: str) -> list[str]:
    por_nome = [f"{nome}: {m.group(0)}"
                for nome, rx in PROIBIDO.items() for m in rx.finditer(texto)]
    return por_nome + [f"id fora da faixa fictícia: {m.group(0)}"
                       for m in ID_NA_JANELA.finditer(texto)
                       if int(m.group(1)) not in FAIXA_FICTICIA]


def _trecho_da_origem(arvore: ast.AST) -> set[int]:
    return {id(sub) for no in ast.walk(arvore) if isinstance(no, ast.Call)
            for arg in no.keywords if arg.arg == "antes" for sub in ast.walk(arg.value)}


def _textos_do_py(caminho: pathlib.Path) -> list[tuple[int, str]]:
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    fora = _trecho_da_origem(arvore)
    return [(no.lineno, no.value) for no in ast.walk(arvore)
            if isinstance(no, ast.Constant) and isinstance(no.value, str) and id(no) not in fora]


def _fontes() -> list[pathlib.Path]:
    return sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)


def _arquivos_de_texto() -> list[pathlib.Path]:
    achados = []
    for raiz in (ASSETS, SRC):
        for p in sorted(raiz.rglob("*")):
            if (not p.is_file() or p.suffix in (".py", *SEM_TEXTO, *FONTES_DE_KERNEL)
                    or "__pycache__" in p.parts or "fonte-por-kernel" in p.parts
                    or "main-por-kernel" in p.parts or "paginas" in p.parts  # (noqa-acento)
                    or p.parent.name == "estilos_de_jogo"):
                continue
            achados.append(p)
    return achados


def test_ha_o_que_varrer() -> None:
    assert len(_fontes()) > 300
    nomes = {p.name for p in _arquivos_de_texto()}
    assert {"hefesto-bt-agent.service", "81-hefesto-usb-power.rules",
            "hefesto-dualsense-storm.conf"} <= nomes, nomes


@pytest.mark.parametrize("fonte", _fontes(), ids=lambda p: str(p.relative_to(SRC)))
def test_nenhum_texto_do_src_traz_dado_real(fonte: pathlib.Path) -> None:
    """MORDE: devolva `steam_app_1599660` a uma docstring de `simple_match.py` e reprova."""
    achados = [f"{fonte.name}:{n}: {a}" for n, t in _textos_do_py(fonte) for a in _acha(t)]
    assert not achados, "\n".join(achados)


@pytest.mark.parametrize("arquivo", _arquivos_de_texto(), ids=lambda p: p.name)
def test_nada_que_o_install_grava_traz_dado_real(arquivo: pathlib.Path) -> None:
    """MORDE: devolva «ritual-Aurora» a `81-hefesto-usb-power.rules` e reprova."""
    try:
        linhas = arquivo.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        pytest.skip("arquivo binário")
    achados = [f"{arquivo.name}:{n}: {a}" for n, t in enumerate(linhas, 1) for a in _acha(t)]
    assert not achados, "\n".join(achados)


def _catalogos() -> list[pathlib.Path]:
    return sorted(SRC.glob("locale/*/LC_MESSAGES/*.mo"))


def test_ha_catalogo_para_varrer() -> None:
    assert len(_catalogos()) >= 2


@pytest.mark.parametrize("catalogo", _catalogos(), ids=lambda p: p.parts[-3])
def test_o_catalogo_de_traducao_nao_traz_dado_real(catalogo: pathlib.Path) -> None:
    """MORDE: compile um `msgid` com `TP-Link` em `po/en.po` e reprova."""
    with catalogo.open("rb") as arquivo:
        mensagens = gettext.GNUTranslations(arquivo)._catalog  # type: ignore[attr-defined]
    achados = [a for chave, valor in mensagens.items() for a in _acha(f"{chave} {valor}")]
    assert not achados, "\n".join(achados)
