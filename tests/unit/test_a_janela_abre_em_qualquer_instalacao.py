"""D-2511-A-JANELA-ABRE-EM-QUALQUER-INSTALACAO: a janela abre com só o pacote e o `share/` do wheel.

Copia só o pacote para uma pasta sem `docs/` nem `assets/` ao lado, monta o `share/` a partir do
`shared-data` do `pyproject.toml` sob um `sys.prefix` de mentira (onde o wheel o põe) e abre a
janela num processo próprio. O `sys.prefix` do Python que roda a suíte fica de fora: o `pip
install -e` da casa e do CI já pôs ali o `share/` da árvore, que responderia no lugar da cópia.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

RAIZ = Path(__file__).resolve().parents[2]
NOME = "hefesto-dualsense4unix"

DADOS_DA_JANELA = (
    "docs/data/mapa-controles.csv",
    "docs/data/pecas-do-dualsense.csv",
    "assets/glyphs/cross.svg",
    "assets/appimage/Hefesto-Dualsense4Unix.png",
)

CONSULTAS = """
import json, pathlib, sys

sys.prefix = PREFIXO

fora = {}


def tenta(nome, fn):
    try:
        fora[nome] = fn()
    except BaseException as erro:
        fora[nome] = "FALHOU: " + type(erro).__name__ + ": " + str(erro)[:160]


def abre():
    import hefesto_dualsense4unix.interface.hefesto_vivo as vivo
    return "ok" if "/lib/hefesto_dualsense4unix/" in vivo.__file__ else "FALHOU: " + vivo.__file__


from hefesto_dualsense4unix.interface import abrir, calibrar, controle_vivo, mapa, mesa_viva, monta
from hefesto_dualsense4unix.utils import repo_files

if ABRE_A_JANELA:
    tenta("abre", abre)
tenta("mapa_de_canais", lambda: "ok" if len(mesa_viva.MAPA) > 0 else "FALHOU: o mapa veio vazio")
tenta("pecas", lambda: "ok" if len(mapa.le_csv()) > 0 else "FALHOU: sem peças")
tenta("glifo", lambda: "ok" if monta.glifo("cross").startswith("<svg") else "FALHOU: sem svg")
tenta("glifo_aceso", lambda: "ok" if monta.glifo("cross", ativo=True).startswith("<svg")
      else "FALHOU: sem svg")
tenta("mapa_desenhado", lambda: "ok" if "<svg" in controle_vivo.molde_svg() else "FALHOU: sem svg")
tenta("icone", lambda: "ok" if abrir.achar_o_icone() is not None else "FALHOU: sem ícone")
tenta("calibrar", lambda: "ok" if calibrar.nome_do_botao("cross") else "FALHOU: sem nome")
fora["achado_em"] = str(repo_files.encontrar_arquivo_do_repo("docs/data/mapa-controles.csv"))
print("RESULTADO=" + json.dumps(fora))
"""


def _shared_data() -> dict[str, str]:
    projeto = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    return dict(projeto["tool"]["hatch"]["build"]["targets"]["wheel"]["shared-data"])


def _instalar_sem(tmp_path: Path, sem: str | None) -> tuple[Path, Path]:
    """`(lib, prefixo)`: o pacote copiado e o `share/` do wheel no prefixo, sem o arquivo `sem`."""
    lib = tmp_path / "lib"
    shutil.copytree(
        RAIZ / "src" / NOME.replace("-", "_"), lib / NOME.replace("-", "_"),
        ignore=shutil.ignore_patterns("__pycache__"))
    prefixo = tmp_path / "prefixo"
    for origem, destino in _shared_data().items():
        if origem == sem:
            continue
        alvo = prefixo / destino
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(RAIZ / origem, alvo)
    return lib, prefixo


def _abrir(tmp_path: Path, sem: str | None, janela: bool) -> dict[str, str]:
    lib, prefixo = _instalar_sem(tmp_path, sem)
    casa = tmp_path / "casa"
    casa.mkdir()
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(casa),
        "XDG_DATA_HOME": str(casa / "data"),
        "XDG_CONFIG_HOME": str(casa / "config"),
        "XDG_CACHE_HOME": str(casa / "cache"),
        "XDG_STATE_HOME": str(casa / "state"),
        "XDG_RUNTIME_DIR": str(casa / "run"),
        "PYTHONPATH": str(lib),
        "HEFESTO_NA_TELA": "0",
    }
    codigo = f"ABRE_A_JANELA = {janela!r}\nPREFIXO = {str(prefixo)!r}\n{CONSULTAS}"
    proc = subprocess.run(
        [sys.executable, "-c", codigo], cwd=str(tmp_path), env=env,
        capture_output=True, text=True, timeout=180)
    linhas = [x for x in proc.stdout.splitlines() if x.startswith("RESULTADO=")]
    assert linhas, f"o processo não respondeu (rc={proc.returncode}):\n{proc.stderr[-1500:]}"
    return dict(json.loads(linhas[-1].removeprefix("RESULTADO=")))


def test_o_pacote_com_o_share_do_wheel_abre_a_janela_sem_a_arvore(tmp_path: Path) -> None:
    pytest.importorskip("gi")
    assert not (tmp_path / "docs").exists() and not (tmp_path / "assets").exists()
    visto = _abrir(tmp_path, None, janela=True)
    assert visto.pop("achado_em").startswith(str(tmp_path / "prefixo" / "share")), visto
    assert visto == {nome: "ok" for nome in visto} and len(visto) == 8, visto


@pytest.mark.parametrize("sem", DADOS_DA_JANELA)
def test_sem_um_dado_do_shared_data_a_instalacao_acusa(tmp_path: Path, sem: str) -> None:
    """MORDIDA: tirar do `shared-data` um dos dados da janela devolve a falha na consulta dele."""
    visto = _abrir(tmp_path, sem, janela=False)
    visto.pop("achado_em")
    assert any(v != "ok" for v in visto.values()), (sem, visto)


def test_o_wheel_e_o_sdist_levam_todo_dado_que_a_janela_le() -> None:
    projeto = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    alvos = projeto["tool"]["hatch"]["build"]["targets"]
    no_wheel = alvos["wheel"]["shared-data"]
    no_sdist = set(alvos["sdist"]["only-include"])
    glifos = {f"assets/glyphs/{g.name}" for g in (RAIZ / "assets/glyphs").glob("*.svg")}
    quer = {*DADOS_DA_JANELA, "docs/data/cores-do-dualsense.csv", *glifos}
    for relativo in sorted(quer):
        assert (RAIZ / relativo).is_file(), relativo
        assert no_wheel.get(relativo) == f"share/{NOME}/{relativo}", relativo
        assert relativo in no_sdist, relativo
