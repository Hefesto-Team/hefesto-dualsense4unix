"""A janela abre em Wayland NATIVO, e os dois caminhos dizem a mesma coisa."""
from __future__ import annotations

import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parents[2]
RUN = RAIZ / "run.sh"
INSTALL = RAIZ / "install.sh"


def _bloco_da_gui() -> str:
    """O ramo `MODE == gui` do `run.sh`, onde o backend se decide."""
    t = RUN.read_text(encoding="utf-8")
    i = t.index('if [[ "$MODE" == "gui" ]]; then')
    return t[i:i + 4000]


def test_o_run_nao_forca_xwayland_por_conta_propria() -> None:
    """Sem opt-in explícito, `GDK_BACKEND` não é tocado."""
    bloco = _bloco_da_gui()
    sem_comentario = "\n".join(
        x for x in bloco.splitlines() if not x.lstrip().startswith("#"))
    assert "export GDK_BACKEND=x11" in sem_comentario, (
        "o escape sumiu — quem precisar de XWayland ficou sem caminho")
    assert "COSMIC" not in sem_comentario.upper().replace("COSMIC_", ""), (
        "o `run.sh` voltou a decidir o backend pelo NOME DA SESSÃO. Isso não é "
        "opt-in: é a máquina dela sob XWayland de novo, e com ela o tema do "
        "portal que o GTK3 não lê ali.")
    assert "HEFESTO_DUALSENSE4UNIX_XWAYLAND" in sem_comentario, (
        "o opt-in explícito saiu do `run.sh`")


def test_o_opt_in_e_uma_variavel_que_se_declara() -> None:
    """`…_XWAYLAND=1` liga; a ausência dela NÃO liga nada."""
    bloco = _bloco_da_gui()
    m = re.search(
        r'if \[\[ "\$\{HEFESTO_DUALSENSE4UNIX_XWAYLAND:-\}" == "1" \]\]', bloco)
    assert m, (
        "a guarda do XWayland deixou de ser uma igualdade a `1`. Qualquer "
        "outra forma (um `!=`, um `-n`) volta a ligar por omissão, que é o "
        "defeito que esta régua existe para não deixar voltar.")


def test_o_install_nao_poe_x11_no_desktop_sem_a_flag() -> None:
    """O `.desktop` do menu dela e o lançador do tray dizem a MESMA coisa."""
    t = INSTALL.read_text(encoding="utf-8")
    m = re.search(r'if \[\[ "\$\{FORCE_XWAYLAND\}" -eq 1 \]\]; then\n'
                  r'\s*_EXEC_LINE="env GDK_BACKEND=x11 (.*?)"\n'
                  r'.*?else\n\s*_EXEC_LINE="(.*?)"', t, re.S)
    assert m, "o bloco que monta o `Exec=` do `.desktop` mudou de forma"
    sem_flag = m.group(2)
    assert "GDK_BACKEND" not in sem_flag, (
        f"sem `--force-xwayland`, o `Exec=` ainda força o backend: {sem_flag!r}")
    assert "GDK_BACKEND=x11" not in sem_flag


def test_a_flag_de_escape_continua_existindo() -> None:
    """Tirar o default não é tirar o caminho."""
    t = INSTALL.read_text(encoding="utf-8")
    assert "--force-xwayland)" in t, "a flag de escape sumiu do `install.sh`"
    assert "FORCE_XWAYLAND=0" in t, (
        "o default do `install.sh` voltou a ser XWayland")
