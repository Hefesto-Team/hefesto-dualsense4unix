"""O GTK mora só na moldura da interface e na bandeja (21/10/2026).

A janela GTK antiga saiu em 06/09 (D-0609-GTK-LEVA-INTEIRA), mas a lógica de
`app/actions/` seguiu declarando o `gi` sem usá-lo: nove módulos só tinham o
`gi.require_version("Gtk", "3.0")`, e sem o `gi` doze dos 31 módulos não
importavam. Aqui moram as duas metades da cura: o portão que reprova o Gtk/Gdk
fora das duas pontas (com a mordida) e a medida de que a lógica importa SEM o `gi`.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import skip_sem_gi_real

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts/check_o_gtk_fica_na_moldura.py"
PACOTE = "src/hefesto_dualsense4unix"


def _portao():
    spec = importlib.util.spec_from_file_location("check_o_gtk_fica_na_moldura", SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _rodar(raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--raiz", str(raiz)],
        capture_output=True, text=True, timeout=60, check=False,
    )


def _arvore_em_ordem(tmp_path: Path) -> Path:
    """Uma árvore de mentira onde cada dono do GTK importa Gtk, e mais nada."""
    portao = _portao()
    base = tmp_path / PACOTE
    donos = [*portao.DONOS_DO_GTK, "interface/exemplo_vivo.py"]
    for relativo in donos:
        arquivo = base / relativo
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text("from gi.repository import Gtk\n", encoding="utf-8")
    (base / "app/actions").mkdir(parents=True, exist_ok=True)
    (base / "app/actions/limpo.py").write_text("X = 1\n", encoding="utf-8")
    return tmp_path


def test_o_portao_passa_na_arvore_de_hoje() -> None:
    """Prova da D-2110-O-GTK-FICA-SO-NA-MOLDURA-E-NA-BANDEJA."""
    saida = _rodar(RAIZ)
    assert saida.returncode == 0, saida.stdout + saida.stderr


def test_a_arvore_de_mentira_em_ordem_passa(tmp_path: Path) -> None:
    """A régua não reprova tudo: as duas pontas, sozinhas, são verde."""
    saida = _rodar(_arvore_em_ordem(tmp_path))
    assert saida.returncode == 0, saida.stdout


@pytest.mark.parametrize(
    "linha",
    [
        "from gi.repository import Gtk",
        "from gi.repository import GLib, Gdk",
        "import gi.repository.Gtk",
        "from gi.repository.Gtk import Window",
        'gi.require_version("Gtk", "3.0")',
        'gi.require_version("Gdk", "3.0")',
        "from gi.repository import WebKit2",
        'gi.require_version("WebKit2", "4.1")',
    ],
)
@pytest.mark.parametrize(
    "onde", ["app/actions/intruso.py", "daemon/subsystems/intruso.py", "cli/intruso.py"]
)
def test_gtk_ou_gdk_fora_das_duas_pontas_reprova_nomeando_a_linha(
    tmp_path: Path, linha: str, onde: str
) -> None:
    raiz = _arvore_em_ordem(tmp_path)
    alvo = raiz / PACOTE / onde
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(f"import gi\n\n{linha}\n", encoding="utf-8")
    saida = _rodar(raiz)
    assert saida.returncode == 1, saida.stdout
    assert f"{PACOTE}/{onde}:3" in saida.stdout, saida.stdout


def test_require_version_puxado_do_gi_tambem_reprova(tmp_path: Path) -> None:
    raiz = _arvore_em_ordem(tmp_path)
    alvo = raiz / PACOTE / "daemon/versao.py"
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text('from gi import require_version\n\nrequire_version("Gtk", "3.0")\n',
                    encoding="utf-8")
    saida = _rodar(raiz)
    assert saida.returncode == 1, saida.stdout
    assert f"{PACOTE}/daemon/versao.py:3" in saida.stdout, saida.stdout


def test_import_dentro_de_funcao_tambem_reprova(tmp_path: Path) -> None:
    raiz = _arvore_em_ordem(tmp_path)
    alvo = raiz / PACOTE / "app/actions/tardio.py"
    alvo.write_text(
        "def f():\n    from gi.repository import Gtk\n    return Gtk\n", encoding="utf-8"
    )
    saida = _rodar(raiz)
    assert saida.returncode == 1
    assert "app/actions/tardio.py:2" in saida.stdout


def test_glib_e_gio_nao_sao_widget(tmp_path: Path) -> None:
    """O laço e o dconf não são janela: o daemon e a bluez_dbus podem usá-los."""
    raiz = _arvore_em_ordem(tmp_path)
    alvo = raiz / PACOTE / "integrations/laco.py"
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text("from gi.repository import Gio, GLib\n", encoding="utf-8")
    assert _rodar(raiz).returncode == 0


def test_o_piloto_novo_entra_pelo_nome(tmp_path: Path) -> None:
    raiz = _arvore_em_ordem(tmp_path)
    alvo = raiz / PACOTE / "interface/outra_viva.py"
    alvo.write_text("from gi.repository import Gtk\n", encoding="utf-8")
    assert _rodar(raiz).returncode == 0


def test_entrada_da_lista_que_envelheceu_reprova(tmp_path: Path) -> None:
    """A lista é a fonte: dono que já não importa Gtk, ou que sumiu, sai dela."""
    raiz = _arvore_em_ordem(tmp_path)
    (raiz / PACOTE / "app/tray.py").write_text("X = 1\n", encoding="utf-8")
    saida = _rodar(raiz)
    assert saida.returncode == 1
    assert "app/tray.py" in saida.stdout and "já não importa" in saida.stdout
    (raiz / PACOTE / "app/tray.py").unlink()
    saida = _rodar(raiz)
    assert saida.returncode == 1 and "não existe mais" in saida.stdout


def test_cada_dono_do_gtk_tem_motivo_e_o_tema_morou_na_moldura() -> None:
    portao = _portao()
    assert all(m.strip() for m in portao.DONOS_DO_GTK.values())
    assert all(m.strip() for m in portao.PADROES_DOS_PILOTOS.values())
    assert "interface/tema_da_sessao.py" in portao.DONOS_DO_GTK
    assert not (RAIZ / PACOTE / "app/theme.py").exists(), "o tema da janela mora na moldura"


_SEM_GI = r"""
import importlib, pkgutil, sys
sys.modules["gi"] = None
sys.modules["gi.repository"] = None
import hefesto_dualsense4unix.app.actions as pacote
nomes = [m.name for m in pkgutil.walk_packages(pacote.__path__, pacote.__name__ + ".")]
nomes += [
    "hefesto_dualsense4unix.app.mesa",
    "hefesto_dualsense4unix.cli.app",
    "hefesto_dualsense4unix.cli.cmd_profile",
    "hefesto_dualsense4unix.daemon.subsystems.rumble",
    "hefesto_dualsense4unix.daemon.subsystems.hotkey",
    "hefesto_dualsense4unix.interface.sistema",
    "hefesto_dualsense4unix.interface.pacotes.a07_lancadores",
    "hefesto_dualsense4unix.interface.pacotes.a09_sistema",
]
ruins = []
for nome in nomes:
    try:
        importlib.import_module(nome)
    except BaseException as erro:
        ruins.append(f"{nome}: {type(erro).__name__}: {erro}")
print(len(nomes))
print("\n".join(ruins))
sys.exit(1 if ruins else 0)
"""


def test_a_logica_importa_num_python_sem_o_gi() -> None:
    env = {**os.environ, "PYTHONPATH": str(RAIZ / "src")}
    saida = subprocess.run(
        [sys.executable, "-c", _SEM_GI], capture_output=True, text=True,
        timeout=120, env=env, check=False,
    )
    assert saida.returncode == 0, saida.stdout + saida.stderr
    assert int(saida.stdout.splitlines()[0]) >= 39, "a varredura achou módulos de menos"


def test_a_area_de_transferencia_sem_gtk_diz_que_nao_deu() -> None:
    """Sem a moldura (sem `gi`), o «Copiar» responde `False` e a aba diz que não deu."""
    codigo = (
        "import sys\n"
        'sys.modules["gi"] = None\n'
        'sys.modules["gi.repository"] = None\n'
        "from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09\n"
        'print(a09._por_na_area_de_transferencia("x"))\n'
    )
    env = {**os.environ, "PYTHONPATH": str(RAIZ / "src")}
    saida = subprocess.run(
        [sys.executable, "-c", codigo], capture_output=True, text=True,
        timeout=60, env=env, check=False,
    )
    assert saida.returncode == 0, saida.stderr
    assert saida.stdout.strip() == "False"


_COPIAR_PELA_MOLDURA = r"""
import sys
from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira
garantir_tela_de_mentira(anunciar=False)
from hefesto_dualsense4unix.interface import janela
from gi.repository import Gdk, GLib, Gtk
if not Gtk.init_check(None)[0]:
    print("SEM-TELA")
    sys.exit(0)
print(janela.por_na_area_de_transferencia("o registro de teste"))
contexto = GLib.MainContext.default()
while contexto.pending():
    contexto.iteration(False)
print(Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text())
"""


@skip_sem_gi_real
def test_a_moldura_poe_o_texto_na_area_de_transferencia(tmp_path: Path) -> None:
    """Com o GTK real, numa tela de mentira: o «Copiar» da aba Sistema chega à área de verdade."""
    lar = tmp_path / "lar"
    env = {**os.environ, "PYTHONPATH": str(RAIZ / "src"), "HOME": str(lar),
           "XDG_CONFIG_HOME": str(lar / ".config"), "XDG_DATA_HOME": str(lar / ".local/share"),
           "XDG_STATE_HOME": str(lar / ".local/state"), "XDG_CACHE_HOME": str(lar / ".cache")}
    saida = subprocess.run(
        [sys.executable, "-c", _COPIAR_PELA_MOLDURA], capture_output=True, text=True,
        timeout=120, env=env, check=False,
    )
    assert saida.returncode == 0, saida.stderr[-2000:]
    linhas = saida.stdout.splitlines()
    if linhas == ["SEM-TELA"]:
        pytest.skip("sem tela para o GTK (rode sob xvfb-run)")
    assert linhas[-2:] == ["True", "o registro de teste"], saida.stdout
