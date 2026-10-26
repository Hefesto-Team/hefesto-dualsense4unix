"""O perfil de fábrica e o serviço chegam em qualquer forma de instalar.

Seis réguas, uma por defeito medido em 09/10/2026:

1. o loader procura a fábrica onde a instalação a pôs (as bases do dono único);
2. o wheel leva `assets/profiles_default` e `assets/estilos_de_jogo`;
3. as units de usuário saem vestidas em todo formato de pacote;
4. `daemon install-service` gera a unit com o executável em uso, e sem caminho
   diz a frase em vez de estourar;
5. o portão de paridade renderiza as units de cada formato;
6. o ensaio do install pergunta o GTK a um Python que existe.

Cada régua tem a sua MORDIDA anotada no docstring.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner, Result

from hefesto_dualsense4unix.daemon import service_install as si
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.utils import units_de_usuario as uu
from tests.unit.test_install_garante_deps_em_qualquer_familia import (
    BASH,
    PRELUDO,
    _extrai_funcao,
    _roda,
)

RAIZ = Path(__file__).resolve().parents[2]
NOME = "hefesto-dualsense4unix"
FORMATOS = [
    ("deb", "/usr/bin", "/opt/hefesto-dualsense4unix/venv/bin/python"),
    ("arch", "/usr/bin", "/usr/bin/python3"),
    ("fedora", "/usr/bin", "/usr/bin/python3"),
    ("nix", "/nix/store/aaaa-hefesto/bin", "/nix/store/bbbb-python3/bin/python3"),
]


def _pyproject() -> dict[str, Any]:
    tomllib = pytest.importorskip("tomllib", reason="tomllib exige Python 3.11+")
    projeto: dict[str, Any] = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    return projeto


def test_as_fontes_do_loader_sao_as_bases_do_dono_unico() -> None:
    """MORDIDA: devolver ao loader a lista própria de três lugares."""
    from hefesto_dualsense4unix.utils import xdg_paths
    from hefesto_dualsense4unix.utils.repo_files import bases_de_instalacao

    bases = [b for b in bases_de_instalacao() if b != xdg_paths.data_dir()]
    for pasta, fontes in (
        ("profiles_default", loader._DEFAULT_SEED_SOURCE_DIRS),
        ("estilos_de_jogo", loader._ESTILO_DE_JOGO_SOURCE_DIRS),
    ):
        assert len(fontes) == len(bases_de_instalacao())
        for base in bases:
            assert base / "assets" / pasta in fontes, (pasta, base)


@pytest.mark.parametrize(
    "pasta,fontes",
    [
        ("profiles_default", "_DEFAULT_SEED_SOURCE_DIRS"),
        ("estilos_de_jogo", "_ESTILO_DE_JOGO_SOURCE_DIRS"),
    ],
)
def test_o_flatpak_e_o_usr_share_estao_entre_as_fontes(pasta: str, fontes: str) -> None:
    """O `/app/share` é onde o Flatpak instala a fábrica (o `sys.prefix` do runtime é
    `/usr`, não `/app`). MORDIDA: a lista antiga não o tinha."""
    candidatas = getattr(loader, fontes)
    assert Path(f"/app/share/{NOME}/assets/{pasta}") in candidatas
    assert Path(f"/usr/share/{NOME}/assets/{pasta}") in candidatas


@pytest.mark.parametrize("pasta", ["profiles_default", "estilos_de_jogo"])
def test_o_sys_prefix_de_mentira_acha_a_fabrica(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pasta: str
) -> None:
    """Um venv/pipx: a fábrica mora só em `<sys.prefix>/share/...`."""
    prefixo = tmp_path / "prefixo"
    pasta_da_fabrica = prefixo / "share" / NOME / "assets" / pasta
    pasta_da_fabrica.mkdir(parents=True)
    (pasta_da_fabrica / "x.json").write_text(
        json.dumps({"name": "x", "match": {"type": "any"}}), encoding="utf-8"
    )
    monkeypatch.setattr(sys, "prefix", str(prefixo))

    fontes = loader._fontes_de_fabrica(pasta)

    assert pasta_da_fabrica in fontes
    copiados = loader.seed_default_presets(
        dest_dir=tmp_path / "perfis", source_dirs=[f for f in fontes if f == pasta_da_fabrica]
    )
    assert copiados == ["x.json"]


def test_a_falta_de_fonte_diz_onde_olhou(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: tirar o aviso (o `return []` mudo de antes)."""
    from structlog.testing import capture_logs

    monkeypatch.setattr(loader, "_sem_fonte_avisada", False)
    fonte = tmp_path / "nao-existe"
    with capture_logs() as eventos:
        assert loader.seed_default_presets(dest_dir=tmp_path / "d", source_dirs=[fonte]) == []
    (aviso,) = [e for e in eventos if e["event"] == "perfis_de_fabrica_sem_fonte"]
    assert aviso["bases"] == [str(fonte)]
    assert "Freestyle" in aviso["efeito"]


def test_o_wheel_declara_a_fabrica_e_as_units_no_share() -> None:
    """MORDIDA: tirar o `shared-data` do pyproject (o wheel voltava sem a fábrica)."""
    projeto = _pyproject()
    dados = projeto["tool"]["hatch"]["build"]["targets"]["wheel"]["shared-data"]
    esperado = {
        "assets/profiles_default",
        "assets/estilos_de_jogo",
        *(f"assets/{u}" for u in uu.UNITS_DE_PACOTE),
    }
    assert esperado <= set(dados), sorted(esperado - set(dados))
    for origem, destino in dados.items():
        assert destino == f"share/{NOME}/{origem}", (origem, destino)
        assert (RAIZ / origem).exists(), origem


def test_o_sdist_leva_o_que_o_wheel_pede() -> None:
    """Um wheel feito a partir do sdist precisa dos mesmos arquivos."""
    projeto = _pyproject()
    so_isto = set(projeto["tool"]["hatch"]["build"]["targets"]["sdist"]["only-include"])
    dados = projeto["tool"]["hatch"]["build"]["targets"]["wheel"]["shared-data"]
    assert set(dados) <= so_isto, sorted(set(dados) - so_isto)


def test_o_wheel_de_verdade_semeia_o_freestyle_e_acha_os_estilos(tmp_path: Path) -> None:
    """Constrói o wheel, "instala" num prefixo de mentira e semeia num lar de mentira.

    MORDIDA: tirar o `shared-data` — o wheel sai sem `share/` e a semeadura não acha nada.
    """
    pytest.importorskip("hatchling", reason="hatchling não está neste Python")
    saida = tmp_path / "wheel"
    saida.mkdir()
    construcao = subprocess.run(
        [
            sys.executable,
            "-c",
            "import hatchling.build as b, sys; print(b.build_wheel(sys.argv[1]))",
            str(saida),
        ],
        cwd=str(RAIZ),
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert construcao.returncode == 0, construcao.stderr[-1500:]
    (roda,) = list(saida.glob("*.whl"))

    prefixo = tmp_path / "prefixo"
    pacotes = tmp_path / "pacotes"
    with zipfile.ZipFile(roda) as zf:
        for membro in zf.namelist():
            if ".data/data/" in membro:
                alvo = prefixo / membro.split(".data/data/", 1)[1]
            else:
                alvo = pacotes / membro
            if membro.endswith("/"):
                continue
            alvo.parent.mkdir(parents=True, exist_ok=True)
            alvo.write_bytes(zf.read(membro))

    lar = tmp_path / "lar"
    lar.mkdir()
    ambiente = {
        **os.environ,
        "HOME": str(lar),
        "XDG_CONFIG_HOME": str(lar / "c"),
        "XDG_DATA_HOME": str(lar / "d"),
        "XDG_STATE_HOME": str(lar / "s"),
        "XDG_CACHE_HOME": str(lar / "k"),
    }
    ambiente.pop("PYTHONPATH", None)
    ambiente.pop("HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED", None)
    programa = (
        "import sys, json\n"
        f"sys.path.insert(0, {str(pacotes)!r})\n"
        f"sys.prefix = {str(prefixo)!r}\n"
        "from hefesto_dualsense4unix.profiles import loader\n"
        "assert loader.__file__.startswith(sys.path[0]), loader.__file__\n"
        "copiados = loader.seed_default_presets(dest_dir=__import__('pathlib').Path(sys.argv[1]))\n"
        "estilos = [n for n in loader.ARQUIVOS_DOS_ESTILOS_DE_JOGO\n"
        "           if loader._seed_source_file(n) is not None]\n"
        "print(json.dumps({'copiados': copiados, 'estilos': estilos}))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", programa, str(tmp_path / "perfis")],
        cwd=str(tmp_path),
        env=ambiente,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-1500:]
    resultado = json.loads(proc.stdout.strip().splitlines()[-1])
    assert "freestyle.json" in resultado["copiados"]
    assert resultado["estilos"] == list(loader.ARQUIVOS_DOS_ESTILOS_DE_JOGO)


@pytest.mark.parametrize("formato,bin_dir,python", FORMATOS)
def test_as_units_de_pacote_saem_sem_marcador_em_todo_formato(
    tmp_path: Path, formato: str, bin_dir: str, python: str
) -> None:
    """MORDIDA: devolver ao Fedora o `for unit in assets/*.service` (cópia às cegas) — o
    portão de paridade e esta régua veem `%h/.local` e `__PYTHON__` na unit."""
    escritas = uu.renderizar_para(RAIZ / "assets", tmp_path, bin_dir=bin_dir, python=python)
    assert [p.name for p in escritas] == list(uu.UNITS_DE_PACOTE)
    for unit in escritas:
        sem_comentario = [
            ln
            for ln in unit.read_text(encoding="utf-8").splitlines()
            if not ln.lstrip().startswith("#")
        ]
        corpo = "\n".join(sem_comentario)
        assert not re.search(r"__[A-Z][A-Z_]*__", corpo), unit.name
        assert "%h/.local/" not in corpo, unit.name
    daemon = (tmp_path / uu.UNITS_DE_PACOTE[0]).read_text(encoding="utf-8")
    assert f"ExecStart={bin_dir}/{NOME} daemon start --foreground" in daemon
    janela = (tmp_path / uu.UNITS_DE_PACOTE[1]).read_text(encoding="utf-8")
    assert f"ExecStart={bin_dir}/{NOME}-gui" in janela
    presenca = (tmp_path / uu.UNITS_DE_PACOTE[2]).read_text(encoding="utf-8")
    assert f"ExecStart=-{python} -m hefesto_dualsense4unix.integrations" in presenca


def test_a_unit_do_daemon_chama_uma_unit_que_o_pacote_leva() -> None:
    """O Arch levava só o daemon e a janela; o `OnFailure=` do daemon apontava para a
    presença, que faltava. MORDIDA: tirar a presença de `UNITS_DE_PACOTE`."""
    daemon = (RAIZ / "assets" / uu.UNITS_DE_PACOTE[0]).read_text(encoding="utf-8")
    chamadas = re.findall(r"^(?:OnFailure|Requires|Wants)=(\S+\.service)", daemon, re.M)
    assert chamadas, "o daemon deixou de chamar a presença"
    for chamada in chamadas:
        assert chamada in uu.UNITS_DE_PACOTE, chamada


def test_as_units_que_dependem_do_install_nativo_ficam_fora_do_pacote() -> None:
    fora = {p.name for p in (RAIZ / "assets").glob("*.service")} - set(uu.UNITS_DE_PACOTE)
    assert fora, "esperava storm-watch e steam-input-guard fora do pacote"
    for nome in fora:
        texto = (RAIZ / "assets" / nome).read_text(encoding="utf-8")
        assert re.search(r"__[A-Z][A-Z_]*__|%h/\.local/share", texto), (
            f"{nome} não precisa do install nativo: ele pode entrar em UNITS_DE_PACOTE"
        )


def test_o_renderizador_recusa_unit_com_marcador_sobrando(tmp_path: Path) -> None:
    """MORDIDA: tirar o `sobras()` do `renderizar` — a unit sairia com o marcador cru."""
    modelos = tmp_path / "modelos"
    modelos.mkdir()
    (modelos / "a.service").write_text("[Service]\nExecStart=__SCRIPT__ --x\n", encoding="utf-8")
    with pytest.raises(uu.UnitComMarcadorSobrandoError, match="__SCRIPT__"):
        uu.renderizar_para(
            modelos,
            tmp_path / "o",
            bin_dir="/usr/bin",
            python="/usr/bin/python3",
            nomes=["a.service"],
        )
    proc = subprocess.run(
        [
            sys.executable,
            "-I",
            str(RAIZ / "src" / "hefesto_dualsense4unix" / "utils" / "units_de_usuario.py"),
            "--assets",
            str(modelos),
            "--out",
            str(tmp_path / "o2"),
            "--bin-dir",
            "/usr/bin",
            "--python",
            "/usr/bin/python3",
            "--unit",
            "a.service",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert proc.returncode == 1
    assert "__SCRIPT__" in proc.stderr


def test_o_renderizador_roda_como_arquivo_sem_o_pacote_instalado(tmp_path: Path) -> None:
    """É assim que o `.deb`, o Arch, o Fedora e o Nix o chamam, sem importar o pacote."""
    proc = subprocess.run(
        [
            sys.executable,
            "-I",
            str(RAIZ / "src" / "hefesto_dualsense4unix" / "utils" / "units_de_usuario.py"),
            "--assets",
            str(RAIZ / "assets"),
            "--out",
            str(tmp_path / "u"),
            "--bin-dir",
            "/usr/bin",
            "--python",
            "/usr/bin/python3",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        cwd=str(tmp_path),
    )
    assert proc.returncode == 0, proc.stderr
    assert sorted(Path(linha).name for linha in proc.stdout.split()) == sorted(uu.UNITS_DE_PACOTE)


@pytest.mark.parametrize(
    "empacotador",
    [
        "scripts/build_deb.sh",
        "packaging/arch/PKGBUILD",
        "packaging/fedora/hefesto-dualsense4unix.spec",
        "packaging/nix/package.nix",
    ],
)
def test_todo_empacotador_passa_pelo_renderizador_e_nenhum_copia_as_cegas(
    empacotador: str,
) -> None:
    """MORDIDA: devolver o `for unit in assets/*.service` à spec ou ao Nix."""
    texto = (RAIZ / empacotador).read_text(encoding="utf-8")
    assert "utils/units_de_usuario.py" in texto
    assert "for unit in assets/*.service" not in texto
    assert 'cp "$service_file"' not in texto


def test_o_nix_da_a_presenca_o_caminho_do_pacote() -> None:
    """O python do store não enxerga o `hefesto_dualsense4unix` sozinho."""
    texto = (RAIZ / "packaging" / "nix" / "package.nix").read_text(encoding="utf-8")
    assert "Environment=PYTHONPATH=" in texto
    assert "makePythonPath dependencies" in texto


@pytest.fixture
def lar_de_mentira(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config = tmp_path / "config"
    config.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("HEFESTO_DUALSENSE4UNIX_ASSETS_DIR", raising=False)
    monkeypatch.setattr(si.ServiceInstaller, "_systemctl", lambda self, *a, **k: None)
    return config / "systemd" / "user"


def test_o_install_service_escreve_o_executavel_em_uso(
    lar_de_mentira: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MORDIDA: devolver o `shutil.copy2` do modelo — a unit chegaria com `%h/.local/bin`."""
    executavel = Path("/opt/pipx/venvs/hefesto/bin") / NOME
    monkeypatch.setattr(si, "executavel_do_produto", lambda: executavel)

    destino = si.ServiceInstaller().install()

    texto = destino.read_text(encoding="utf-8")
    assert f"ExecStart={executavel} daemon start --foreground" in texto
    assert "%h/.local/bin" not in texto


def test_o_install_service_acha_o_modelo_no_share_do_prefixo(
    lar_de_mentira: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Instalação por wheel: o modelo mora em `<prefixo>/share/hefesto-dualsense4unix/assets`.

    MORDIDA: devolver o `find_assets_dir` que só subia pelos pais do arquivo e olhava
    `/usr/share`.
    """
    base = tmp_path / "prefixo" / "share" / NOME
    (base / "assets").mkdir(parents=True)
    (base / "assets" / si.SERVICE_NORMAL).write_text(
        "[Service]\nExecStart=%h/.local/bin/hefesto-dualsense4unix daemon start\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(si, "bases_de_instalacao", lambda: (base,))
    monkeypatch.setattr(si, "executavel_do_produto", lambda: Path("/x/bin") / NOME)

    assert si.find_assets_dir() == base / "assets"
    destino = si.ServiceInstaller().install()

    assert (
        destino.read_text(encoding="utf-8")
        .strip()
        .endswith(f"ExecStart=/x/bin/{NOME} daemon start")
    )


def _invocar(args: list[str]) -> Result:
    from hefesto_dualsense4unix.cli.app import app

    return CliRunner().invoke(app, args)


@pytest.mark.parametrize("como", ["nenhuma-base-tem", "o-override-aponta-para-uma-pasta-vazia"])
def test_sem_modelo_a_instalacao_diz_a_frase_e_sai_com_1(
    lar_de_mentira: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, como: str
) -> None:
    """Antes: `FileNotFoundError: assets/ não encontrado` com a pilha inteira.

    MORDIDA: tirar o `try/except FileNotFoundError` do `install`.
    """
    vazio = tmp_path / "sem-assets"
    vazio.mkdir()
    if como == "nenhuma-base-tem":
        monkeypatch.setattr(si, "bases_de_instalacao", lambda: (vazio,))
    else:
        monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_ASSETS_DIR", str(vazio))

    resultado = _invocar(["daemon", "install-service"])

    assert resultado.exit_code == 1
    assert isinstance(resultado.exception, SystemExit), resultado.exception
    assert "unit não instalada" in resultado.output
    assert "Traceback" not in resultado.output
    assert not (lar_de_mentira / si.SERVICE_NORMAL).exists()


def test_sem_executavel_a_instalacao_diz_a_frase_e_sai_com_1(
    lar_de_mentira: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MORDIDA: devolver o `%h/.local/bin` fixo quando `executavel_do_produto` dá None."""
    monkeypatch.setattr(si, "executavel_do_produto", lambda: None)

    resultado = _invocar(["daemon", "install-service"])

    assert resultado.exit_code == 1
    assert isinstance(resultado.exception, SystemExit), resultado.exception
    assert "não achei o executável" in resultado.output
    assert not (lar_de_mentira / si.SERVICE_NORMAL).exists()


def test_o_executavel_do_produto_segue_a_ordem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PATH, depois `argv[0]`, depois o que mora ao lado do Python."""
    pasta = tmp_path / "bin"
    pasta.mkdir()
    no_path = pasta / NOME
    no_path.write_text("#!/bin/sh\n", encoding="utf-8")
    no_path.chmod(0o755)
    monkeypatch.setattr(shutil, "which", lambda n: str(no_path) if n == NOME else None)
    assert si.executavel_do_produto() == no_path

    monkeypatch.setattr(shutil, "which", lambda _n: "/usr/bin/systemctl")
    monkeypatch.setattr(sys, "argv", [str(no_path)])
    assert si.executavel_do_produto() == no_path

    monkeypatch.setattr(sys, "argv", ["pytest"])
    ao_lado = tmp_path / "venv" / "bin"
    ao_lado.mkdir(parents=True)
    (ao_lado / NOME).write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(sys, "executable", str(ao_lado / "python"))
    assert si.executavel_do_produto() == ao_lado / NOME

    monkeypatch.setattr(sys, "executable", str(tmp_path / "vazio" / "python"))
    assert si.executavel_do_produto() is None


def test_o_portao_de_paridade_renderiza_as_units_de_cada_formato() -> None:
    """MORDIDA: pôr `__PYTHON__` solto em ``assets/hefesto-dualsense4unix-gui-hotplug.service``
    ou devolver a cópia às cegas à spec — o portão reprova."""
    proc = subprocess.run(
        [BASH, str(RAIZ / "scripts" / "check_packaging_parity.sh")],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
        cwd=str(RAIZ),
    )
    assert "[ OK ] units de usuário" in proc.stdout, proc.stdout[-2500:]
    assert "[FAIL] units de usuário" not in proc.stdout


def _python_de_mentira(pasta: Path, *, enxerga: bool) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / "python"
    alvo.write_text(f"#!/bin/sh\nexit {0 if enxerga else 1}\n", encoding="utf-8")
    alvo.chmod(0o755)
    return alvo


PRELUDO_DO_GI = "\n".join([PRELUDO, _extrai_funcao("_dep_presente")])


@pytest.mark.parametrize("checagem", ["svg", "appindicator", "webkit"])
def test_sem_venv_o_ensaio_pergunta_ao_python_que_criaria_o_venv(
    tmp_path: Path, checagem: str
) -> None:
    """MORDIDA: voltar ao `${VENV_DIR}/bin/python` fixo — o venv do ensaio não existe, a
    resposta é «não tem» e o plano promete instalar o que a máquina já tem."""
    sistema = _python_de_mentira(tmp_path / "sistema", enxerga=True)
    corpo = f'VENV_DIR="{tmp_path}/sem-venv"\n_VENV_PYTHON="{sistema}"\n_dep_presente {checagem}'
    assert _roda(corpo, preludo=PRELUDO_DO_GI).returncode == 0

    sistema_cego = _python_de_mentira(tmp_path / "cego", enxerga=False)
    corpo = (
        f'VENV_DIR="{tmp_path}/sem-venv"\n_VENV_PYTHON="{sistema_cego}"\n_dep_presente {checagem}'
    )
    assert _roda(corpo, preludo=PRELUDO_DO_GI).returncode == 1, "o Python de mentira diz que não"


@pytest.mark.parametrize("checagem", ["svg", "appindicator", "webkit"])
def test_com_venv_o_venv_vence_o_python_do_sistema(tmp_path: Path, checagem: str) -> None:
    sistema = _python_de_mentira(tmp_path / "sistema", enxerga=True)
    venv = tmp_path / "venv"
    _python_de_mentira(venv / "bin", enxerga=False)
    corpo = f'VENV_DIR="{venv}"\n_VENV_PYTHON="{sistema}"\n_dep_presente {checagem}'
    assert _roda(corpo, preludo=PRELUDO_DO_GI).returncode == 1


def test_a_checagem_do_gtk3_do_passo_2_usa_o_mesmo_python() -> None:
    """MORDIDA: voltar ao `"${VENV_DIR}/bin/python" -c "import gi; gi.require_version('Gtk'`."""
    texto = (RAIZ / "install.sh").read_text(encoding="utf-8")
    assert (
        "if ! \"${_PY_DO_GTK}\" -c \\\n        \"import gi; gi.require_version('Gtk','3.0')\""
        in texto
    )
    assert '[[ -x "${_PY_DO_GTK}" ]] || _PY_DO_GTK="${_VENV_PYTHON}"' in texto
    assert (
        'if ! "${VENV_DIR}/bin/python" -c \\\n        "import gi; gi.require_version(\'Gtk\''
        not in texto
    )


def _gi_do_sistema_enxerga_o_gtk3() -> bool:
    if not Path("/usr/bin/python3").exists():
        return False
    return (
        subprocess.run(
            ["/usr/bin/python3", "-c", "import gi; gi.require_version('Gtk','3.0')"],
            capture_output=True,
            timeout=30,
            check=False,
        ).returncode
        == 0
    )


@pytest.mark.skipif(
    (RAIZ / ".venv").exists() or not _gi_do_sistema_enxerga_o_gtk3(),
    reason="precisa de um clone sem .venv e de uma máquina com o GTK3 no Python do sistema",
)
def test_o_ensaio_em_clone_sem_venv_nao_diz_que_falta_o_gtk3(tmp_path: Path) -> None:
    from tests.unit.test_o_ensaio_do_install_nao_escreve import INSTALL_PATH, _bancada

    _lar, _diario, ambiente = _bancada(tmp_path)
    proc = subprocess.run(
        [BASH, str(INSTALL_PATH), "--dry-run", "--yes"],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
        env=ambiente,
        cwd=str(RAIZ),
    )
    assert proc.returncode == 0, proc.stdout[-1500:] + proc.stderr
    assert "Bindings GTK3 não encontrados" not in proc.stdout
