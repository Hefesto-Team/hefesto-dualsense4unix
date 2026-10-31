"""O install e os pacotes levam só a fábrica que o loader lista, nunca o JSON solto no disco.

Um JSON que não está no git, largado em `assets/profiles_default/`, virava perfil de fábrica:
o `install_profiles.sh` e o semeador copiavam a pasta por glob, e o `.deb`, o AppImage, o
Flatpak e o wheel levavam a pasta inteira. Aqui cada caminho roda com um intruso de mentira.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.profiles import loader

RAIZ = Path(__file__).resolve().parents[2]
INTRUSO = "jogo_ficticio_intruso.json"
LEIA = "LEIA-PRIMEIRO.md"
SHARE = Path("usr/share/hefesto-dualsense4unix")
_PASTAS_DA_FABRICA = ("assets/profiles_default", "assets/estilos_de_jogo")
_GIT_ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def _perfil(nome: str) -> str:
    return json.dumps({"name": nome, "match": {"type": "process", "process_names": [nome]}})


def _fabrica_com_intruso(raiz: Path) -> Path:
    pasta = raiz / "assets" / "profiles_default"
    pasta.mkdir(parents=True)
    for nome in loader.ARQUIVOS_DE_FABRICA:
        (pasta / nome).write_text(_perfil(nome.removesuffix(".json")), encoding="utf-8")
    (pasta / INTRUSO).write_text(_perfil("jogo_ficticio_intruso"), encoding="utf-8")
    return pasta


def _repo_com_intruso(raiz: Path) -> Path:
    _fabrica_com_intruso(raiz)
    estilos = raiz / "assets" / "estilos_de_jogo"
    estilos.mkdir(parents=True)
    for nome in loader.ARQUIVOS_DOS_ESTILOS_DE_JOGO:
        (estilos / nome).write_text(_perfil(nome.removesuffix(".json")), encoding="utf-8")
    (estilos / LEIA).write_text("", encoding="utf-8")
    (raiz / "assets" / "71-uinput.rules").write_text("", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=raiz, check=True, env=_GIT_ENV)
    versionados = [
        *(f"assets/profiles_default/{n}" for n in loader.ARQUIVOS_DE_FABRICA),
        *(f"assets/estilos_de_jogo/{n}" for n in loader.ARQUIVOS_DOS_ESTILOS_DE_JOGO),
        f"assets/estilos_de_jogo/{LEIA}",
        "assets/71-uinput.rules",
    ]
    subprocess.run(["git", "add", "--", *versionados], cwd=raiz, check=True, env=_GIT_ENV)
    (estilos / INTRUSO).write_text(_perfil("jogo_ficticio_intruso"), encoding="utf-8")
    return raiz


def _bloco(script: str, comeco: str) -> str:
    linhas = (RAIZ / "scripts" / script).read_text(encoding="utf-8").splitlines()
    (inicio,) = [i for i, ln in enumerate(linhas) if ln.startswith(comeco)]
    return "\n".join(linhas[inicio : linhas.index("", inicio)])


def _pyproject() -> dict[str, Any]:
    tomllib = pytest.importorskip("tomllib", reason="tomllib exige Python 3.11+")
    projeto: dict[str, Any] = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    return projeto


def _versionados(pasta: str) -> list[str]:
    saida = subprocess.run(
        ["git", "ls-files", "--", pasta], cwd=RAIZ, check=True, capture_output=True, text=True
    ).stdout
    return sorted(Path(linha).name for linha in saida.splitlines() if linha.endswith(".json"))


def test_o_install_profiles_copia_so_a_fabrica(tmp_path: Path) -> None:
    """MORDIDA: devolver o `for src in "${SRC_DIR}"/*.json` ao script."""
    raiz = tmp_path / "repo"
    _fabrica_com_intruso(raiz)
    lar = tmp_path / "lar"
    lar.mkdir()

    rodada = subprocess.run(
        ["bash", str(RAIZ / "scripts" / "install_profiles.sh"), str(raiz)],
        env={"HOME": str(lar), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=False,
    )

    assert rodada.returncode == 0, rodada.stderr
    destino = lar / ".config" / "hefesto-dualsense4unix" / "profiles"
    assert sorted(p.name for p in destino.glob("*.json")) == sorted(loader.ARQUIVOS_DE_FABRICA)


def test_o_semeador_copia_so_a_fabrica(tmp_path: Path) -> None:
    """MORDIDA: devolver o `sorted(source.glob("*.json"))` ao `seed_default_presets`."""
    fonte = _fabrica_com_intruso(tmp_path / "repo")
    destino = tmp_path / "perfis"

    copiados = loader.seed_default_presets(dest_dir=destino, source_dirs=[fonte])

    assert sorted(copiados) == sorted(loader.ARQUIVOS_DE_FABRICA)
    assert not (destino / INTRUSO).exists()


def test_a_lista_do_shell_e_a_do_loader() -> None:
    texto = (RAIZ / "scripts" / "install_profiles.sh").read_text(encoding="utf-8")
    (lista,) = re.findall(r"^readonly ARQUIVOS_DE_FABRICA=\(([^)]*)\)$", texto, re.M)
    assert tuple(lista.split()) == loader.ARQUIVOS_DE_FABRICA


def test_o_que_o_git_versiona_e_o_que_o_loader_lista() -> None:
    assert _versionados("assets/profiles_default") == sorted(loader.ARQUIVOS_DE_FABRICA)
    assert _versionados("assets/estilos_de_jogo") == sorted(loader.ARQUIVOS_DOS_ESTILOS_DE_JOGO)


def test_o_wheel_e_o_sdist_listam_a_fabrica_por_nome() -> None:
    """MORDIDA: devolver `"assets/profiles_default"` inteiro ao `shared-data`."""
    alvos = _pyproject()["tool"]["hatch"]["build"]["targets"]
    dados = set(alvos["wheel"]["shared-data"])
    so_isto = set(alvos["sdist"]["only-include"])
    esperado = {
        *(f"assets/profiles_default/{n}" for n in loader.ARQUIVOS_DE_FABRICA),
        *(f"assets/estilos_de_jogo/{n}" for n in loader.ARQUIVOS_DOS_ESTILOS_DE_JOGO),
    }
    for conjunto in (dados, so_isto):
        da_fabrica = {c for c in conjunto if c.startswith(_PASTAS_DA_FABRICA)}
        assert da_fabrica == esperado, sorted(da_fabrica ^ esperado)
    assert "tests" not in so_isto, "o sdist não leva a suíte, que é do repositório"


def test_o_flatpak_instala_a_fabrica_por_nome() -> None:
    texto = (RAIZ / "flatpak" / "io.github.hefesto_team.hefesto_dualsense4unix.yml").read_text(
        encoding="utf-8"
    )
    assert "profiles_default/*" not in texto and "estilos_de_jogo/*" not in texto
    for nome in loader.ARQUIVOS_DE_FABRICA:
        assert f"assets/profiles_default/{nome}" in texto, nome
    for nome in loader.ARQUIVOS_DOS_ESTILOS_DE_JOGO:
        assert f"assets/estilos_de_jogo/{nome}" in texto, nome


def test_o_deb_nao_leva_o_json_solto(tmp_path: Path) -> None:
    """Roda o bloco do próprio `build_deb.sh` num repositório de mentira.

    MORDIDA: devolver o `cp -r assets/.` ao script.
    """
    repo = _repo_com_intruso(tmp_path / "repo")
    staging = tmp_path / "staging"
    (staging / SHARE / "assets").mkdir(parents=True)

    subprocess.run(
        ["bash", "-euo", "pipefail", "-c", _bloco("build_deb.sh", "git ls-files -z -- assets ")],
        cwd=repo,
        check=True,
        env={**_GIT_ENV, "STAGING": str(staging)},
    )

    levados = sorted(p.name for p in (staging / SHARE / "assets").rglob("*.json"))
    esperado = sorted([*loader.ARQUIVOS_DE_FABRICA, *loader.ARQUIVOS_DOS_ESTILOS_DE_JOGO])
    assert levados == esperado
    assert (staging / SHARE / "assets" / "71-uinput.rules").is_file()


def test_o_appimage_nao_leva_o_json_solto(tmp_path: Path) -> None:
    """O AppImage leva só os JSON versionados, nem o intruso nem o `LEIA-PRIMEIRO.md` da pasta.

    MORDIDA: devolver o `install ... "$HERE/assets/profiles_default/"*.json` ao script, ou tirar o
    `*.json` do `git ls-files`.
    """
    repo = _repo_com_intruso(tmp_path / "repo")
    appdir = tmp_path / "AppDir"
    (appdir / SHARE).mkdir(parents=True)

    subprocess.run(
        [
            "bash",
            "-euo",
            "pipefail",
            "-c",
            _bloco("build_appimage_gui.sh", 'git -C "$HERE" ls-files'),
        ],
        cwd=repo,
        check=True,
        env={**_GIT_ENV, "HERE": str(repo), "APPDIR": str(appdir)},
    )

    assets = appdir / SHARE / "assets"
    fabrica = sorted(p.name for p in (assets / "profiles_default").iterdir())
    estilos = sorted(p.name for p in (assets / "estilos_de_jogo").iterdir())
    assert fabrica == sorted(loader.ARQUIVOS_DE_FABRICA)
    assert estilos == sorted(loader.ARQUIVOS_DOS_ESTILOS_DE_JOGO)
