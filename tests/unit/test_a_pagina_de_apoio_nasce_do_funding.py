"""A seção «Apoie» da página do produto nasce do `.github/FUNDING.yml`, e só dele."""

from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PASTA = RAIZ / "scripts" / "github"
CODIGO_FALSO = (
    "00020126330014br.gov.bcb.pix0111exemplo-fake"
    "5204000053039865802BR5904Nome6004Cida62070503***6304"
)


def _carrega(nome: str) -> Any:
    spec = importlib.util.spec_from_file_location(f"{nome}_do_apoio", PASTA / f"{nome}.py")
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[f"{nome}_do_apoio"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def mp() -> Any:
    return _carrega("montar_pagina")


@pytest.fixture(scope="module")
def qr() -> Any:
    return _carrega("qr_svg")


def _raiz(tmp_path: Path, funding: str | None) -> Path:
    raiz = tmp_path / "raiz"
    (raiz / ".github").mkdir(parents=True)
    (raiz / "README.md").write_text("# Titulo\n\nTexto.\n", encoding="utf-8")
    if funding is not None:
        (raiz / ".github" / "FUNDING.yml").write_text(funding, encoding="utf-8")
    return raiz


def _pagina(mp: Any, raiz: Path, tmp_path: Path) -> str:
    assert mp.montar(raiz, tmp_path / "site") == []
    return (tmp_path / "site" / "index.html").read_text(encoding="utf-8")


TUDO = """# comentário
github: [conta-um]
ko_fi: conta-dois
patreon: Conta_Tres
custom: [https://exemplo.org/doar]
"""
COMENTADO = """patreon: Conta_Tres
# github: [conta-comentada]
# ko_fi: conta-comentada
# custom: [https://exemplo.org/comentado]
"""


# ---------------------------------------------------------------------------
# A leitura do arquivo
# ---------------------------------------------------------------------------


def test_so_a_chave_ativa_conta(mp: Any) -> None:
    assert mp.chaves_do_funding(COMENTADO) == {"patreon": ["Conta_Tres"]}
    assert mp.chaves_do_funding("github: []\nko_fi:\ncustom:\n") == {}


def test_as_formas_de_lista_do_yaml(mp: Any) -> None:
    texto = (
        "github: [a, 'b']  # duas\n"
        "ko_fi: \"c\"\n"
        "custom:\n"
        "  - https://exemplo.org/x#y\n"
        "  - https://exemplo.org/z\n"
    )
    assert mp.chaves_do_funding(texto) == {
        "github": ["a", "b"],
        "ko_fi": ["c"],
        "custom": ["https://exemplo.org/x#y", "https://exemplo.org/z"],
    }


def test_o_funding_de_verdade_le_sem_erro(mp: Any) -> None:
    formas = mp.apoios(RAIZ)
    assert all(f.rotulo for f in formas)
    # O Patreon fica: a chave que está ativa hoje continua na página.
    texto = (RAIZ / ".github" / "FUNDING.yml").read_text(encoding="utf-8")
    ativas = mp.chaves_do_funding(texto)
    assert ("patreon" in ativas) == any(f.rotulo == "Patreon" for f in formas)


# ---------------------------------------------------------------------------
# A página
# ---------------------------------------------------------------------------


def test_preencher_a_chave_basta_e_cada_forma_leva_o_que_e_dela(
    mp: Any, tmp_path: Path
) -> None:
    pagina = _pagina(mp, _raiz(tmp_path, TUDO), tmp_path)
    assert 'id="apoie"' in pagina and 'href="#apoie"' in pagina
    assert 'href="https://github.com/sponsors/conta-um"' in pagina
    assert 'href="https://ko-fi.com/conta-dois"' in pagina
    assert 'href="https://www.patreon.com/Conta_Tres"' in pagina
    assert 'href="https://exemplo.org/doar"' in pagina
    assert pagina.count("<svg") == 1 and 'aria-label="QR code do PIX"' in pagina
    assert mp.links_relativos(pagina) == []


def test_chave_comentada_nao_aparece_nem_inventa_link_ou_qr(mp: Any, tmp_path: Path) -> None:
    pagina = _pagina(mp, _raiz(tmp_path, COMENTADO), tmp_path)
    assert "patreon.com/Conta_Tres" in pagina
    for ausente in ("github.com/sponsors", "ko-fi.com", "<svg", "PIX", "comentad"):
        assert ausente not in pagina, ausente


def test_sem_nenhuma_chave_nao_ha_secao_nem_link_no_menu(mp: Any, tmp_path: Path) -> None:
    for funding in ("# github: []\n# ko_fi:\n", None):
        pasta = tmp_path / ("sem" if funding is None else "comentado")
        pagina = _pagina(mp, _raiz(pasta, funding), pasta)
        assert 'id="apoie"' not in pagina and 'href="#apoie"' not in pagina


def test_o_codigo_copia_e_cola_vira_qr_e_texto_sem_link(mp: Any, tmp_path: Path) -> None:
    pagina = _pagina(mp, _raiz(tmp_path, f"custom: [{CODIGO_FALSO}]\n"), tmp_path)
    assert pagina.count("<svg") == 1
    assert f"{CODIGO_FALSO}</textarea>" in pagina
    assert f'href="{CODIGO_FALSO}' not in pagina


@pytest.mark.parametrize(
    "funding",
    [
        "custom: [http://exemplo.org/sem-tls]\n",
        "custom: [uma-chave-pix-solta]\n",
        'custom: ["https://exemplo.org/a b"]\n',
        "ko_fi: nome com espaço\n",
        "github: ['<script>']\n",
    ],
)
def test_valor_que_nao_e_conta_endereco_nem_codigo_reprova_e_nada_se_adivinha(
    mp: Any, tmp_path: Path, funding: str, capsys: pytest.CaptureFixture[str]
) -> None:
    raiz = _raiz(tmp_path, funding)
    with pytest.raises(ValueError):
        mp.montar(raiz, tmp_path / "site")
    assert mp.principal(["--raiz", str(raiz), "--saida", str(tmp_path / "s2")]) == 1
    assert "FUNDING.yml" in capsys.readouterr().err


def test_o_texto_da_conta_nao_escapa_do_html(mp: Any) -> None:
    secao = mp.secao_de_apoio([mp.Apoio('A "B" <i>', "https://exemplo.org/?a=1&b=2")])
    assert "<i>" not in secao and "&amp;b=2" in secao and "&quot;B&quot;" in secao


def test_o_fonte_nao_carrega_conta_de_doacao() -> None:
    """A chave mora só no `FUNDING.yml`: o módulo não leva conta nem endereço de doação escrito."""
    fonte = (PASTA / "montar_pagina.py").read_text(encoding="utf-8")
    destinos = r"https://(?:ko-fi\.com|www\.patreon\.com|github\.com/sponsors)/[^\s{\"']+"
    achados = re.findall(destinos, fonte)
    assert achados == [], "conta de verdade no fonte: a chave mora só no FUNDING.yml"


def test_o_fluxo_das_paginas_remonta_quando_a_chave_ou_o_qr_mudam() -> None:
    texto = (RAIZ / ".github" / "workflows" / "paginas.yml").read_text(encoding="utf-8")
    assert ".github/FUNDING.yml" in texto and "scripts/github/qr_svg.py" in texto


# ---------------------------------------------------------------------------
# O QR
# ---------------------------------------------------------------------------

# O SHA-256 dos módulos, conferido contra o `qrencode` (nível M, modo byte):
# as três matrizes saíram idênticas.
VETORES = {
    "https://exemplo.org/doar": ("11955347ddc1b26e7874139c", 25),
    "x" * 150: ("1336208e161628515a3ac797", 49),
    CODIGO_FALSO: ("972e4ee0baa81c2e054b4750", 41),
}


def _impressao(matriz: list[list[bool]]) -> str:
    bits = "".join("1" if c else "0" for linha in matriz for c in linha)
    return hashlib.sha256(bits.encode()).hexdigest()[:24]


@pytest.mark.parametrize("texto", list(VETORES))
def test_o_qr_sai_igual_ao_de_um_codificador_independente(qr: Any, texto: str) -> None:
    impressao, lado = VETORES[texto]
    m = qr.matriz(texto)
    assert len(m) == lado and _impressao(m) == impressao


def test_o_qr_tem_as_tres_marcas_de_canto_e_o_tempo(qr: Any) -> None:
    m = qr.matriz("https://exemplo.org/doar")
    n = len(m)
    for x0, y0 in ((0, 0), (n - 7, 0), (0, n - 7)):
        for dy in range(7):
            for dx in range(7):
                borda = max(abs(dx - 3), abs(dy - 3))
                assert m[y0 + dy][x0 + dx] == (borda != 2), (x0, y0, dx, dy)
    assert all(m[6][i] == (i % 2 == 0) for i in range(8, n - 8))


def test_o_svg_desenha_exatamente_os_modulos_da_matriz(qr: Any) -> None:
    texto = "https://exemplo.org/doar"
    svg = qr.svg_do_qr(texto)
    m = qr.matriz(texto)
    borda = 4
    escuros = set()
    for x, y, w in re.findall(r"M(\d+) (\d+)h(\d+)v1", svg):
        escuros |= {(int(x) - borda + i, int(y) - borda) for i in range(int(w))}
    esperados = {(x, y) for y, lin in enumerate(m) for x, c in enumerate(lin) if c}
    assert escuros == esperados
    assert f'viewBox="0 0 {len(m) + 2 * borda} {len(m) + 2 * borda}"' in svg


def test_texto_que_nao_cabe_reprova_em_vez_de_cortar(qr: Any) -> None:
    assert len(qr.matriz("a" * qr.capacidade())) == 17 + 4 * qr.VERSAO_MAXIMA
    with pytest.raises(ValueError):
        qr.matriz("a" * (qr.capacidade() + 1))


def test_mordida_o_qr_com_um_modulo_trocado_deixa_de_ser_o_do_vetor(qr: Any) -> None:
    texto = "https://exemplo.org/doar"
    m = qr.matriz(texto)
    m[20][20] = not m[20][20]
    assert _impressao(m) != VETORES[texto][0]
