"""O-RECIBO-E-O-PINO-DO-PROTON-VIAJAM-EM-TODO-FORMATO-01 — o doctor confere o Proton fixado
também numa instalação por pacote.

O `hefesto doctor` procura o recibo (`docs/data/proton-qualificacao.csv`) e o pino
(`assets/proton-pin.conf`) em `<base>/<caminho>`, com as bases de `utils/repo_files.py`;
numa instalação por pacote a base é o `share/hefesto-dualsense4unix` do prefixo. O wheel
os deixava para trás: o bloco novo do doctor dizia «não veio nesta instalação» e não
conferia nada. Só o `install.sh` tinha os dois.

Cinco réguas:

1. o `shared-data` do wheel declara os dois, no destino que espelha o caminho do repositório;
2. o sdist leva os dois (um wheel feito dele sai igual);
3. o wheel de verdade, aberto num prefixo de mentira, deixa o doctor achar e conferir os dois;
4. cada formato de pacote instala esse wheel, sem filtrar o `share/`;
5. o Fedora lista a pasta no `%files` (arquivo instalado e não listado aborta o rpmbuild).

MORDIDAS (cada uma reprova; arrancar a cura, ver cair, devolver):

- tirar um dos dois do `shared-data` (réguas 1 e 3);
- tirar um dos dois do `only-include` do sdist (régua 2);
- tirar o `%files` do Fedora ou trocar o instalador de um formato por cópia à mão (réguas 4 e 5).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

RAIZ = Path(__file__).resolve().parents[2]
NOME = "hefesto-dualsense4unix"
RECIBO = "docs/data/proton-qualificacao.csv"
PINO = "assets/proton-pin.conf"
OS_DOIS = (PINO, RECIBO)


def _projeto() -> dict:
    return tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))


def _alvos() -> dict:
    return _projeto()["tool"]["hatch"]["build"]["targets"]


def _copia_da_arvore(destino: Path) -> Path:
    """A árvore de agora (o que o git rastreia, com o que está editado) num tmp, para o
    `uv build` não deixar `dist/` nem `.egg-info` no repositório."""
    listados = subprocess.run(
        ["git", "ls-files", "-z"], cwd=str(RAIZ), capture_output=True, check=True
    ).stdout.split(b"\0")
    for bruto in listados:
        if not bruto:
            continue
        origem = RAIZ / bruto.decode("utf-8")
        if not origem.is_file():
            continue
        alvo = destino / bruto.decode("utf-8")
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem, alvo, follow_symlinks=False)
    return destino


@pytest.mark.parametrize("origem", OS_DOIS)
def test_o_wheel_declara_o_pino_e_o_recibo_no_share(origem: str) -> None:
    """MORDIDA: tirar a linha do `shared-data` — o wheel sai sem o arquivo."""
    dados = _alvos()["wheel"]["shared-data"]
    assert dados.get(origem) == f"share/{NOME}/{origem}", dados.get(origem)
    assert (RAIZ / origem).is_file(), origem


@pytest.mark.parametrize("origem", OS_DOIS)
def test_o_sdist_lista_o_pino_e_o_recibo(origem: str) -> None:
    """MORDIDA: tirar o caminho do `only-include` — um wheel feito do sdist sai sem ele."""
    assert origem in _alvos()["sdist"]["only-include"]


def test_o_wheel_de_verdade_deixa_o_doctor_achar_e_conferir_o_proton(tmp_path: Path) -> None:
    """`uv build` faz o sdist e, DELE, o wheel — o caminho de um pacote que parte do tarball
    da versão. O wheel é aberto num prefixo de mentira e o doctor é perguntado.

    MORDIDA: tirar um dos dois do `shared-data` ou do `only-include`: o arquivo não chega ao
    prefixo, o doctor não o acha e a conferência do pino contra o recibo não acontece.
    """
    if shutil.which("uv") is None:
        pytest.skip("sem uv neste ambiente")
    fonte = _copia_da_arvore(tmp_path / "fonte")
    saida = tmp_path / "saida"
    proc = subprocess.run(
        ["uv", "build", "--out-dir", str(saida)],
        cwd=str(fonte),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-1500:]
    (sdist,) = list(saida.glob("*.tar.gz"))
    (roda,) = list(saida.glob("*.whl"))
    with tarfile.open(sdist) as tar:
        nomes = {n.split("/", 1)[1] for n in tar.getnames() if "/" in n}
    for origem in OS_DOIS:
        assert origem in nomes, f"o sdist veio sem {origem}"

    prefixo = tmp_path / "prefixo"
    pacotes = tmp_path / "pacotes"
    with zipfile.ZipFile(roda) as zf:
        membros = set(zf.namelist())
        for membro in zf.namelist():
            if membro.endswith("/"):
                continue
            if ".data/data/" in membro:
                alvo = prefixo / membro.split(".data/data/", 1)[1]
            else:
                alvo = pacotes / membro
            alvo.parent.mkdir(parents=True, exist_ok=True)
            alvo.write_bytes(zf.read(membro))
    for origem in OS_DOIS:
        assert any(m.endswith(f".data/data/share/{NOME}/{origem}") for m in membros), (
            f"o wheel veio sem {origem}"
        )

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
    programa = (
        "import sys, json\n"
        f"sys.path.insert(0, {str(pacotes)!r})\n"
        f"sys.prefix = {str(prefixo)!r}\n"
        "from hefesto_dualsense4unix.integrations import proton_pin as pp\n"
        "from hefesto_dualsense4unix.integrations import qualificar_proton as qp\n"
        "from hefesto_dualsense4unix.utils.repo_files import encontrar_arquivo_do_repo\n"
        "assert qp.__file__.startswith(sys.path[0]), qp.__file__\n"
        f"conf = encontrar_arquivo_do_repo({PINO!r})\n"
        "recibo_em = qp.caminho_do_recibo()\n"
        "pino = pp.parse_pin_conf(conf.read_text(encoding='utf-8'))\n"
        "recibo = qp.ler_recibo(recibo_em.read_text(encoding='utf-8'))\n"
        "print(json.dumps({'conf': str(conf), 'recibo': str(recibo_em),\n"
        "                  'problemas': qp.o_pino_sem_recibo(pino, recibo),\n"
        "                  'linhas': len(recibo)}))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", programa],
        cwd=str(tmp_path),
        env=ambiente,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-1500:]
    achado = json.loads(proc.stdout.strip().splitlines()[-1])
    assert achado["conf"].startswith(str(prefixo)), achado
    assert achado["recibo"].startswith(str(prefixo)), achado
    assert achado["linhas"] > 0, "o recibo chegou vazio"
    assert achado["problemas"] == [], achado["problemas"]


def _le(relativo: str) -> str:
    return (RAIZ / relativo).read_text(encoding="utf-8")


def test_o_arch_instala_o_wheel_inteiro() -> None:
    """MORDIDA: trocar o `installer` do PKGBUILD por cópia à mão — o `share/` do wheel se perde."""
    texto = _le("packaging/arch/PKGBUILD")
    assert "python -m build --wheel" in texto
    assert re.search(r"python -m installer[^\n]*\\\n(?:[^\n]*\\\n)*[^\n]*dist/\*\.whl", texto)
    assert "--prefix=/usr" in texto


def test_o_fedora_instala_o_wheel_e_lista_a_pasta() -> None:
    """MORDIDA: tirar o `%files` das duas pastas — o rpmbuild aborta com «Installed (but
    unpackaged)», que é o que o Fedora faria com o `share/` do wheel desde a fábrica."""
    texto = _le("packaging/fedora/hefesto-dualsense4unix.spec")
    assert "python3 -m build --wheel" in texto
    assert re.search(r"python3 -m installer[^\n]*\\\n(?:[^\n]*\\\n)*[^\n]*dist/\*\.whl", texto)
    arquivos = texto.split("\n%files", 1)[1].split("\n%changelog", 1)[0]
    linhas = {linha.strip() for linha in arquivos.splitlines()}
    assert "%{_datadir}/%{app_id}/assets/" in linhas
    assert "%{_datadir}/%{app_id}/docs/" in linhas


def test_o_nix_constroi_o_wheel_da_arvore_inteira() -> None:
    """MORDIDA: trocar o `src` por uma fonte filtrada que deixe `docs/` de fora."""
    texto = _le("packaging/nix/package.nix")
    assert re.search(r"^\s*src = \.\./\.\.;", texto, flags=re.MULTILINE)
    assert re.search(r"build-system = with python3Packages; \[\s*hatchling\s*\];", texto)


def test_o_deb_instala_o_pacote_no_venv_e_copia_os_assets() -> None:
    """O .deb põe o pacote num venv (`pip install .`, que traz o `share/` do wheel para o
    `sys.prefix`, uma das bases do doctor) e copia `assets/` inteiro para o `/usr/share`.

    MORDIDA: trocar o `pip install .` por cópia dos fontes — o `share/` do wheel se perde.
    """
    texto = _le("scripts/build_deb.sh")
    assert re.search(r"\"\$\{VENV_PIP\}\" install [^\n]*--no-cache-dir \.\s*$", texto, re.M)
    assert 'cp -r assets/. "${STAGING}/usr/share/hefesto-dualsense4unix/assets/"' in texto
    for relativo in ("control", "postinst", "postrm", "prerm"):
        assert (RAIZ / "packaging/debian" / relativo).is_file(), relativo
