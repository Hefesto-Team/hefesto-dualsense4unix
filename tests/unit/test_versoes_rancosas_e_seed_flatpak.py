"""Regressão das versões rançosas e da semeadura de presets no Flatpak."""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]

GATE_REL = "scripts/check_version_consistency.py"
ENTRYPOINT_REL = "assets/appimage/entrypoint.sh"
METAINFO_REL = "flatpak/io.github.hefesto_team.hefesto_dualsense4unix.metainfo.xml"
MANIFESTO_REL = "flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml"
BUILD_GUI_REL = "scripts/build_appimage_gui.sh"

_ALVOS_NOVOS: tuple[tuple[str, str], ...] = (
    (ENTRYPOINT_REL, 'HEFESTO_VERSION_FALLBACK="{v}"\n'),
    (METAINFO_REL, '<releases>\n  <release version="{v}" date="2026-07-28"/>\n</releases>\n'),
)


def _versao_canonica() -> str:
    """Lê pyproject.toml — a mesma fonte de verdade que o portão usa."""
    try:
        import tomllib
    except ImportError:  # pragma: no cover
        import tomli as tomllib
    dados = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    return str(dados["project"]["version"])


def _portao():
    """Importa o portão real sem executá-lo."""
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        import check_version_consistency as gate
    finally:
        sys.path.pop(0)
    return gate


def _targets_do_portao() -> list[tuple[str, str, str]]:
    """Lê `_TARGETS` do portão real sem executá-lo."""
    return list(_portao()._TARGETS)


def _esperado_no_alvo(relpath: str) -> str:
    """A versão que o portão exige NAQUELE alvo."""
    gate = _portao()
    canonica = _versao_canonica()
    return gate._TRADUTORES.get(relpath, lambda v: v)(canonica)


@pytest.mark.parametrize(
    "relpath", [ENTRYPOINT_REL, METAINFO_REL]
)
def test_alvo_novo_esta_no_portao(relpath: str) -> None:
    """O portão de release precisa VER cada artefato."""
    caminhos = {alvo[1] for alvo in _targets_do_portao()}
    assert relpath in caminhos, (
        f"{relpath} não é alvo de {GATE_REL} — voltou a poder envelhecer em "
        "silêncio (VERSOES-RANCOSAS-01)"
    )


@pytest.mark.parametrize(
    "relpath", [ENTRYPOINT_REL, METAINFO_REL]
)
def test_regex_do_alvo_extrai_a_versao_canonica_do_arquivo_real(relpath: str) -> None:
    """Cada sintaxe é diferente (shell, XML, semver) — o regex tem que pegar."""
    esperado = _esperado_no_alvo(relpath)
    padrao = next(alvo[2] for alvo in _targets_do_portao() if alvo[1] == relpath)
    texto = (REPO / relpath).read_text(encoding="utf-8")
    achado = re.search(padrao, texto, re.MULTILINE)
    assert achado is not None, f"regex do portão não casa nada em {relpath}"
    assert achado.group(1) == esperado


def test_portao_real_passa_no_repo_real() -> None:
    """Acrescentar alvos só vale se o repo está consistente AGORA."""
    proc = subprocess.run(
        [sys.executable, GATE_REL], cwd=REPO, capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "OK:" in proc.stdout


def _repo_fake(tmp_path: Path, versao: str, relpath: str, versao_alvo: str) -> Path:
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO / GATE_REL, tmp_path / GATE_REL)
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "fake"\nversion = "{versao}"\n', encoding="utf-8"
    )
    molde = next(molde for rel, molde in _ALVOS_NOVOS if rel == relpath)
    destino = tmp_path / relpath
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(molde.format(v=versao_alvo), encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("relpath", [rel for rel, _ in _ALVOS_NOVOS])
def test_portao_reprova_alvo_novo_defasado(tmp_path: Path, relpath: str) -> None:
    repo = _repo_fake(tmp_path, versao="9.9.9", relpath=relpath, versao_alvo="0.0.1")
    proc = subprocess.run(
        [sys.executable, GATE_REL], cwd=repo, capture_output=True, text=True
    )
    assert proc.returncode == 1, (
        f"o portão PASSOU com {relpath} em 0.0.1 contra 9.9.9: "
        + proc.stdout
        + proc.stderr
    )
    assert relpath in proc.stdout
    assert "0.0.1" in proc.stdout


@pytest.mark.parametrize("relpath", [rel for rel, _ in _ALVOS_NOVOS])
def test_portao_aprova_alvo_novo_em_dia(tmp_path: Path, relpath: str) -> None:
    repo = _repo_fake(tmp_path, versao="9.9.9", relpath=relpath, versao_alvo="9.9.9")
    proc = subprocess.run(
        [sys.executable, GATE_REL], cwd=repo, capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "1 alvo" in proc.stdout


def test_banner_do_appimage_deriva_a_versao() -> None:
    texto = (REPO / ENTRYPOINT_REL).read_text(encoding="utf-8")
    assert "'BANNER'" not in texto, (
        "o heredoc voltou a ser quoted (<<'BANNER'): dentro dele "
        "${HEFESTO_VERSION} sairia literal, sem expandir"
    )
    achado = re.search(r"cat <<'?BANNER'? >&2\n(.*?)\nBANNER\n", texto, re.DOTALL)
    assert achado is not None, "heredoc BANNER não encontrado no entrypoint"
    corpo = achado.group(1)
    assert "${HEFESTO_VERSION}" in corpo, "o banner não usa a versão derivada"
    assert re.search(r"v\d+\.\d+\.\d+", corpo) is None, (
        f"versão digitada de volta no banner: {corpo!r}"
    )


def test_deb_sugerido_pelo_banner_casa_o_nome_que_o_build_deb_gera() -> None:
    """O nome sugerido era `..._3.0.0_amd64.deb`, que não existe no formato"""
    texto = (REPO / ENTRYPOINT_REL).read_text(encoding="utf-8")
    linha = next(ln for ln in texto.splitlines() if "apt install" in ln and "$" in ln)
    assert "${HEFESTO_VERSION}" in linha
    assert "_amd64_py" in linha, (
        "a sugestão perdeu a tag de Python do nome — o arquivo sugerido não "
        f"existe: {linha.strip()!r}"
    )
    build_deb = (REPO / "scripts/build_deb.sh").read_text(encoding="utf-8")
    assert "_amd64_${PYTAG}.deb" in build_deb, (
        "o build_deb.sh mudou o padrão do nome; a sugestão do banner precisa "
        "acompanhar"
    )


def test_fallback_do_banner_e_o_unico_literal_de_versao() -> None:
    texto = (REPO / ENTRYPOINT_REL).read_text(encoding="utf-8")
    esperado = _versao_canonica()
    literais = re.findall(r'"(\d+\.\d+\.\d+(?:\.\d+)?)"', texto)
    assert literais == [esperado], (
        f"literais de versão em {ENTRYPOINT_REL}: {literais} "
        f"(esperado apenas o fallback {esperado})"
    )


def test_metainfo_tem_a_versao_corrente_e_a_linha_0x() -> None:
    from xml.etree import ElementTree

    raiz = ElementTree.parse(REPO / METAINFO_REL).getroot()
    releases = raiz.find("releases")
    assert releases is not None
    versoes = [r.get("version") for r in releases.findall("release")]
    assert versoes[0] == _versao_canonica(), (
        f"a primeira <release> é {versoes[0]} — é essa que a loja anuncia. "
        f"Lista: {versoes[:4]}"
    )
    assert any(v is not None and v.startswith("0.") for v in versoes), (
        "nenhuma release 0.x no metainfo (a numeração voltou para 0.x em 24/07)"
    )


def test_metainfo_releases_em_ordem_decrescente_sem_linha_3x() -> None:
    """Réplica local do portão do .github/workflows/flatpak.yml."""
    from xml.etree import ElementTree

    raiz = ElementTree.parse(REPO / METAINFO_REL).getroot()
    releases = raiz.find("releases")
    assert releases is not None
    versoes = [r.get("version") or "" for r in releases.findall("release")]

    def como_tupla(v: str) -> tuple[int, ...]:
        return tuple(int(parte) for parte in v.split("."))

    tuplas = [como_tupla(v) for v in versoes]
    assert tuplas == sorted(tuplas, reverse=True), (
        f"releases fora de ordem decrescente: {versoes} — o appstreamcli "
        "reprova com releases-not-in-order"
    )
    assert all(t[0] == 0 for t in tuplas), (
        f"release pré-0.x de volta no metainfo: {versoes}. Com uma 3.x na "
        "lista a loja nunca oferece a 0.3.0 como atualização."
    )


def test_appstreamcli_valida_o_metainfo() -> None:
    """O mesmo comando do CI (job `validate-manifest` do flatpak.yml)."""
    if shutil.which("appstreamcli") is None:
        pytest.skip("appstreamcli ausente (o CI instala o pacote `appstream`)")
    proc = subprocess.run(
        ["appstreamcli", "validate", "--no-net", METAINFO_REL],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_metainfo_e_xml_valido_e_cada_release_tem_descricao() -> None:
    from xml.etree import ElementTree

    raiz = ElementTree.parse(REPO / METAINFO_REL).getroot()
    releases = raiz.find("releases")
    assert releases is not None
    for rel in releases.findall("release"):
        assert rel.get("date"), f"release {rel.get('version')} sem data"
        assert rel.find("description") is not None, (
            f"release {rel.get('version')} sem <description> — o AppStream "
            "mostra entrada vazia na loja"
        )


def _comandos_do_modulo_hefesto() -> list[str]:
    manifesto = yaml.safe_load((REPO / MANIFESTO_REL).read_text(encoding="utf-8"))
    modulo = next(
        m
        for m in manifesto["modules"]
        if isinstance(m, dict) and m.get("name") == "hefesto"
    )
    return [" ".join(str(c).split()) for c in modulo["build-commands"]]


def _destino_do_loader_no_sandbox() -> str:
    """Onde o loader procura os presets quando sys.prefix é /app."""
    from hefesto_dualsense4unix.profiles.loader import _DEFAULT_SEED_SOURCE_DIRS

    relativo = _DEFAULT_SEED_SOURCE_DIRS[1].relative_to(sys.prefix)
    return str(Path("/app") / relativo)


def test_flatpak_semeia_presets_no_caminho_que_o_loader_procura() -> None:
    destino = _destino_do_loader_no_sandbox()
    comandos = _comandos_do_modulo_hefesto()
    casando = [c for c in comandos if "profiles_default" in c]
    assert casando, (
        "o manifesto Flatpak não instala assets/profiles_default — quem "
        "instala pelo Flatpak abre a janela sem perfil nenhum "
        "(FIX-FLATPAK-PRESET-SEED-01)"
    )
    assert any(destino in c for c in casando), (
        f"instala presets, mas fora de {destino} (o segundo candidato do "
        f"profiles/loader.py). Comandos: {casando}"
    )
    from hefesto_dualsense4unix.profiles.loader import ARQUIVOS_DE_FABRICA

    for nome in ARQUIVOS_DE_FABRICA:
        assert any(f"assets/profiles_default/{nome}" in c for c in casando), (
            f"o manifesto não instala {nome}, que está em ARQUIVOS_DE_FABRICA. "
            f"Comandos: {casando}"
        )
    assert not any("profiles_default/*" in c for c in casando), (
        "o manifesto voltou ao glob: a fonte `dir` copia o disco de quem empacota, "
        f"e um JSON solto viraria perfil de fábrica. Comandos: {casando}"
    )


def test_flatpak_e_appimage_gui_semeiam_o_mesmo_conjunto() -> None:
    """Os dois levam só o que o loader lista: o AppImage pelo `git ls-files`, o Flatpak por nome."""
    gui = (REPO / BUILD_GUI_REL).read_text(encoding="utf-8")
    assert "ls-files" in gui and "assets/profiles_default" in gui, (
        "o build_appimage_gui.sh perdeu a semeadura de presets pelo versionado"
    )
    assert "profiles_default/*.json" not in gui and 'profiles_default/"*.json' not in gui
    from hefesto_dualsense4unix.profiles.loader import (
        ARQUIVO_DO_PADRAO,
        ARQUIVOS_DE_FABRICA,
        ARQUIVOS_DOS_ESTILOS_DE_JOGO,
    )

    assert ARQUIVO_DO_PADRAO in ARQUIVOS_DE_FABRICA
    assert "assets/estilos_de_jogo" in gui, (
        "o build_appimage_gui.sh não leva assets/estilos_de_jogo/ — a migração "
        "dos gêneros fica sem o asset de referência dentro do AppImage"
    )
    comandos = _comandos_do_modulo_hefesto()
    for nome in ARQUIVOS_DOS_ESTILOS_DE_JOGO:
        assert any(f"assets/estilos_de_jogo/{nome}" in c for c in comandos), (
            f"o manifesto Flatpak não leva assets/estilos_de_jogo/{nome}"
        )
    assert "fallback.json" in ARQUIVOS_DOS_ESTILOS_DE_JOGO


def test_manifesto_flatpak_continua_instalando_os_glyphs() -> None:
    """Guarda de não-regressão: a linha nova entrou colada na dos glyphs."""
    comandos = _comandos_do_modulo_hefesto()
    assert any("assets/glyphs/*.svg" in c for c in comandos)
