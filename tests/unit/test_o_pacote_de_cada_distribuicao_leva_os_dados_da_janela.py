"""O pacote de cada distribuição leva os dados da janela, e o glifo que falta não derruba.

O-PACOTE-DE-CADA-DISTRIBUICAO-LEVA-OS-DADOS-DA-JANELA-E-O-GLIFO-QUE-FALTA-NAO-DERRUBA-01. Os dados
da janela (os dois CSV, o ícone e os glifos) viajam no shared-data do wheel do `pyproject.toml`.
Arch, Nix, o venv do .deb e o Flatpak recebem o `share/` instalando o wheel; o RPM, além disso,
só empacota o que o `%files` lista, e instalado e não listado aborta o rpmbuild. A régua confere,
receita por receita, que o caminho do wheel está de pé e que o `%files` cobre todo destino.
"""
from __future__ import annotations

import pathlib
import re
import sys
import tomllib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
RECEITAS = RAIZ / "packaging"
SPEC = RECEITAS / "fedora" / "hefesto-dualsense4unix.spec"
PKGBUILD = RECEITAS / "arch" / "PKGBUILD"
NIX = RECEITAS / "nix" / "package.nix"
DEB = RAIZ / "scripts" / "build_deb.sh"
FLATPAK = RAIZ / "flatpak" / "io.github.hefesto_team.hefesto_dualsense4unix.yml"

DADOS_DA_JANELA = (
    "docs/data/mapa-controles.csv",
    "docs/data/pecas-do-dualsense.csv",
    "docs/data/cores-do-dualsense.csv",
    "assets/appimage/Hefesto-Dualsense4Unix.png",
)
PREFIXO = "share/hefesto-dualsense4unix/"

MACROS_DO_SPEC = {"%{_datadir}": "/usr/share", "%{app_id}": "hefesto-dualsense4unix"}


def _shared_data() -> dict[str, str]:
    dados = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    return dados["tool"]["hatch"]["build"]["targets"]["wheel"]["shared-data"]


def _entradas_do_files_do_spec() -> list[str]:
    texto = SPEC.read_text(encoding="utf-8")
    corpo = texto.split("\n%files", 1)[1]
    entradas: list[str] = []
    for linha in corpo.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith(("#", "%license", "%doc", "%changelog")):
            continue
        linha = linha.removeprefix("%pycached ")
        for macro, valor in MACROS_DO_SPEC.items():
            linha = linha.replace(macro, valor)
        entradas.append(linha)
    return entradas


def _coberto_pelo_files(destino: str, entradas: list[str]) -> bool:
    caminho = "/usr/" + destino
    return any(
        caminho == e or (e.endswith("/") and caminho.startswith(e)) for e in entradas
    )


def test_os_dados_da_janela_estao_no_shared_data_do_wheel_e_no_sdist():
    """Os dois CSV da janela, as cores, o ícone e todos os glifos que existem no repositório."""
    dados = _shared_data()
    sdist = set(
        tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
        ["tool"]["hatch"]["build"]["targets"]["sdist"]["only-include"]
    )
    glifos = sorted(p.relative_to(RAIZ).as_posix() for p in (RAIZ / "assets/glyphs").glob("*.svg"))
    assert glifos, "o repositório não tem glifo nenhum: a régua estaria vazia"
    for fonte in (*DADOS_DA_JANELA, *glifos):
        assert dados.get(fonte) == PREFIXO + fonte, f"o wheel não leva {fonte}"
        assert fonte in sdist, f"o sdist não leva {fonte}"


def test_o_rpm_lista_no_files_todo_destino_do_shared_data():
    """O `%files` do spec cobre cada arquivo que o wheel põe no `share/`: nenhum fica sem dono."""
    entradas = _entradas_do_files_do_spec()
    sem_dono = sorted(d for d in _shared_data().values() if not _coberto_pelo_files(d, entradas))
    assert not sem_dono, f"instalado pelo wheel e fora do %files do spec: {sem_dono[:5]}"


def test_a_regua_do_files_enxerga_um_destino_descoberto():
    """A régua não é cega: tirado o diretório, o destino fica sem dono."""
    entradas = [e for e in _entradas_do_files_do_spec() if not e.endswith("/docs/")]
    descobertos = [d for d in _shared_data().values() if not _coberto_pelo_files(d, entradas)]
    assert descobertos
    assert all(d.startswith(PREFIXO + "docs/") for d in descobertos)


@pytest.mark.parametrize(
    ("receita", "caminho", "regex"),
    [
        ("arch", PKGBUILD, r"python -m installer .*\\?\s*--prefix=/usr\s*\\?\s*dist/\*\.whl"),
        ("rpm", SPEC, r"python3 -m installer .*\\?\s*--prefix=%\{_prefix\}\s*\\?\s*dist/\*\.whl"),
        ("nix", NIX, r"pyproject = true;"),
        ("deb", DEB, r'"\$\{VENV_PIP\}" install .* "\.\['),
        ("flatpak", FLATPAK, r"pip3 install --prefix=/app --no-deps \./dist/\*\.whl"),
    ],
)
def test_cada_receita_instala_o_projeto_pelo_caminho_que_traz_o_shared_data(
    receita, caminho, regex
):
    """Arch, RPM, Nix, o venv do .deb e o Flatpak instalam o wheel inteiro, com o seu `share/`."""
    texto = caminho.read_text(encoding="utf-8")
    assert re.search(regex, texto), f"a receita {receita} não instala o wheel como a régua espera"


def test_nenhuma_receita_descarta_o_share_do_wheel():
    """Nenhuma receita corta o `share/` depois de instalar (`rm -rf .../share`, `--no-data`)."""
    for caminho in (PKGBUILD, SPEC, NIX, DEB, FLATPAK):
        texto = caminho.read_text(encoding="utf-8")
        assert "--no-data" not in texto, caminho
        assert not re.search(r"rm -rf [^\n]*/share/hefesto-dualsense4unix/(assets|docs)", texto)


def _monta():
    for caminho in (str(RAIZ / "src"), str(INTERFACE)):
        if caminho not in sys.path:
            sys.path.insert(0, caminho)
    import monta

    return monta


def test_o_glifo_que_falta_sai_vazio_com_o_titulo_e_o_diario_diz_qual_faltou(monkeypatch):
    """Sem o SVG, a página monta: glifo vazio com o título, e um aviso por arquivo que faltou."""
    from structlog.testing import capture_logs

    monta = _monta()
    monkeypatch.setattr(monta, "encontrar_glifo", lambda _arquivo, bases=None: None)
    monkeypatch.setattr(monta, "GLIFOS_QUE_FALTARAM", set())
    with capture_logs() as diario:
        primeiro = monta.glifo("cross", ativo=True)
        segundo = monta.glifo("cross", ativo=True)
    assert primeiro == segundo
    assert primeiro.startswith("<svg") and primeiro.endswith("</svg>")
    assert f"<title>{monta.nome_do_glifo('cross')}</title>" in primeiro
    avisos = [e for e in diario if e["event"] == "glifo_ausente_da_instalacao"]
    assert [e["arquivo"] for e in avisos] == ["cross_active.svg"]


def test_o_glifo_que_existe_segue_saindo_inteiro():
    """Com a instalação completa o glifo sai com o desenho, como antes."""
    monta = _monta()
    saida = monta.glifo("cross")
    assert "<path" in saida or "<circle" in saida or "<line" in saida or "<g" in saida
    assert 'class="gl"' in saida
