"""A logo ganha o disco escuro no tema claro (O-TEMA-CLARO-NASCE-COMO-EXTENSAO-01).

A escolha de 20/10/2026, ~23h, é a opção A (o disco escuro): a logo fica a de hoje, e o tema
claro religa o disco `radial-gradient(circle at 35% 30%,#3b2d5c,#1a1b24 70%)` com o aro, que o
`.logo{background:none;border:none}` da folha desligava. O fundo e o aro viram tokens
(`--logo-fundo`, `none` na casa; `--logo-aro`, transparente), e `mods.tema.validar` aceita os dois.

A régua lê o fundo do `.logo` pelo que a página pinta: a última regra `.logo{…}` com
`background`, e o `var()` dela resolvido pelo `:root` da página, com o tema por cima ou sem ele.

MORDIDA (executada em 21/10/2026): com o `background:none` fixo de volta no `.logo` do
`topo.html` e as dez geradas de novo, `test_com_o_tema_a_logo_pinta_o_disco` reprova nas dez.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from hefesto_dualsense4unix.mods import tema

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DEZ = sorted((RAIZ / "mockup").glob("[01][0-9]-*.html"))
DISCO = "radial-gradient(circle at 35% 30%,#3b2d5c,#1a1b24 70%)"
REGRA_DA_LOGO = re.compile(r"(?m)^\s*\.logo\{([^{}]*)\}")
FOLHA_CLARA = (":root{--app-bg:#eef0f5;--panel:#ffffff;--elevated:#f5f6fa;--fg:#1c1e29;"
               "--texto-suave:#383c4c;--texto-mudo:#545a70;--comment:#4a5486;--rot-campo:#1d7a3c;"
               "--green:#1d7a3c;--cyan:#006d85;--purple:#6a3dc2;--orange:#a35200;--pink:#ad2f6c;"
               f"--red:#c01f2e;--yellow:#7a6400;--logo-fundo:{DISCO};--logo-aro:#c9cdd9;"
               "--fundo-da-pagina:#dde1ea}")


def _fundo_da_logo(html: str, por_cima: dict[str, str]) -> str:
    regras = [corpo for corpo in REGRA_DA_LOGO.findall(html) if "background" in corpo]
    assert regras, "a folha não pinta o fundo do .logo"
    valor = re.search(r"background:\s*([^;]+?)\s*(?:;|$)", regras[-1]).group(1)  # type: ignore[union-attr]
    token = re.fullmatch(r"var\((--[a-z-]+)\)", valor)
    if token is None:
        return valor
    raiz = dict(tema._declaracoes_do_root(html))
    return por_cima.get(token.group(1), raiz.get(token.group(1), ""))


@pytest.mark.parametrize("desenho", DEZ, ids=lambda p: p.name)
def test_sem_tema_a_logo_nao_tem_fundo(desenho: pathlib.Path) -> None:
    assert _fundo_da_logo(desenho.read_text(encoding="utf-8"), {}) == "none"


@pytest.mark.parametrize("desenho", DEZ, ids=lambda p: p.name)
def test_com_o_tema_a_logo_pinta_o_disco(desenho: pathlib.Path) -> None:
    aceito = tema.validar(FOLHA_CLARA)
    assert _fundo_da_logo(desenho.read_text(encoding="utf-8"), aceito.tokens) == DISCO


@pytest.mark.parametrize("valor", [
    "none", "#1a1b24", DISCO, "radial-gradient(#3b2d5c, rgba(26,27,36,0.9) 70%)",
])
def test_a_regua_aceita_o_fundo_da_logo(valor: str) -> None:
    assert tema.fundo_da_logo(valor)


@pytest.mark.parametrize("valor", [
    "radial-gradient(circle at 35% 30%,#3b2d5c)",
    "linear-gradient(#000,#fff)",
    "radial-gradient(circle,red,blue)",
    "radial-gradient(circle at 35% 30%,var(--x),#000)",
    "url(x.png)",
])
def test_a_regua_recusa_o_que_nao_e_disco_de_cor(valor: str) -> None:
    assert not tema.fundo_da_logo(valor)
    with pytest.raises(tema.TemaRecusadoError):
        tema.validar(FOLHA_CLARA.replace(DISCO, valor))
