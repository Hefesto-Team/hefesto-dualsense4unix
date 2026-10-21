"""A moldura da página segue o tema (A-MOLDURA-DA-PAGINA-SEGUE-O-TEMA-01).

O fundo em volta da janela era `#11121a` por extenso no `body` de cinco donos (`topo.html`,
`calibrar.py`, `mapa.py`, `pagina_do_mapa.py` e a barra de luz da `experimental.css`), e tema
nenhum o alcançava: com o tema claro, a janela clara ficava num fundo quase preto. Agora ele é o
token `--fundo-da-pagina` do `:root`, e o `#11121a` só mora ali.

As publicadas e as três páginas avulsas recebem a cura pelo `--publicar` da costura; até lá,
`test_a_publicada_nao_pinta_a_cor_fora_do_root` reprova nelas.

MORDIDA (executada em 21/10/2026): com o `background:#11121a` de volta no `body` do `topo.html` e as
dez geradas de novo, `test_o_desenho_nao_pinta_a_cor_fora_do_root` reprova nas dez.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from hefesto_dualsense4unix.interface import calibrar, mapa, pagina_do_mapa
from hefesto_dualsense4unix.mods import tema

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
DEZ = sorted((RAIZ / "mockup").glob("[01][0-9]-*.html"))
PUBLICADAS = sorted((INTERFACE / "paginas").glob("*.html"))  # (noqa-acento): nome da pasta
COR = "#11121a"
COMENTARIO = re.compile(r"/\*.*?\*/", re.S)
ROOT = re.compile(r":root\s*\{[^{}]*\}")
FOLHA_CLARA = (":root{--app-bg:#eef0f5;--panel:#ffffff;--elevated:#f5f6fa;--fg:#1c1e29;"
               "--texto-suave:#383c4c;--texto-mudo:#545a70;--comment:#4a5486;--rot-campo:#1d7a3c;"
               "--green:#1d7a3c;--cyan:#006d85;--purple:#6a3dc2;--orange:#a35200;--pink:#ad2f6c;"
               "--red:#c01f2e;--yellow:#7a6400;--fundo-da-pagina:#dde1ea}")


def _fora_do_root(texto: str) -> int:
    return ROOT.sub("", COMENTARIO.sub("", texto)).lower().count(COR)


@pytest.mark.parametrize("desenho", DEZ, ids=lambda p: p.name)
def test_o_desenho_nao_pinta_a_cor_fora_do_root(desenho: pathlib.Path) -> None:
    texto = desenho.read_text(encoding="utf-8")
    assert _fora_do_root(texto) == 0
    assert tema.tokens_do_root(texto)[tema.FUNDO_DA_PAGINA] == COR


@pytest.mark.parametrize("dono, texto", [
    pytest.param("calibrar", calibrar.CSS, id="calibrar"),
    pytest.param("mapa", mapa.CSS_BASE, id="mapa"),
    pytest.param("pagina_do_mapa", pagina_do_mapa.pagina(), id="pagina_do_mapa"),
    pytest.param("experimental", (INTERFACE / "experimental" / "experimental.css")
                 .read_text(encoding="utf-8"), id="experimental"),
])
def test_os_outros_donos_pintam_o_token(dono: str, texto: str) -> None:
    assert _fora_do_root(texto) == 0, dono
    assert "var(--fundo-da-pagina)" in texto, dono


@pytest.mark.parametrize("publicada", PUBLICADAS, ids=lambda p: p.name)
def test_a_publicada_nao_pinta_a_cor_fora_do_root(publicada: pathlib.Path) -> None:
    assert _fora_do_root(publicada.read_text(encoding="utf-8")) == 0


def test_o_tema_claro_troca_a_moldura() -> None:
    aceito = tema.validar(FOLHA_CLARA, casa=tema.tokens_do_root(DEZ[0].read_text(encoding="utf-8")))
    assert aceito.tokens[tema.FUNDO_DA_PAGINA] == "#dde1ea"


def test_a_regua_mede_o_texto_do_body_sobre_a_moldura() -> None:
    casa = tema.tokens_do_root(DEZ[0].read_text(encoding="utf-8"))
    with pytest.raises(tema.TemaRecusadoError, match="--fundo-da-pagina"):
        tema.validar(FOLHA_CLARA.replace("#dde1ea", "#2a2c38"), casa=casa)
    # o tema claro que não diz a moldura fica com a da casa, e o texto escuro some nela
    with pytest.raises(tema.TemaRecusadoError, match="--fundo-da-pagina"):
        tema.validar(FOLHA_CLARA.replace(";--fundo-da-pagina:#dde1ea", ""), casa=casa)
