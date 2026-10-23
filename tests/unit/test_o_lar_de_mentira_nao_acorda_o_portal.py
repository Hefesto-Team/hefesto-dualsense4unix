"""OS-PORTOES-NAO-ACORDAM-O-PORTAL-DO-COSMIC-01 (22/10/2026): o lar de mentira não tem portal.

Medido no `--rapido` de 22/10: o Chrome dos três portões de tela pedia o
`org.freedesktop.portal.Desktop` ao D-Bus do `dbus-run-session`, que acordava o portal da
máquina. Com o `XDG_CURRENT_DESKTOP=COSMIC` herdado, o backend do COSMIC morria oito vezes
por portão (`NoCompositor` no journal), e o portal montava o `runtime/doc` e o `runtime/gvfs`
do lar. A cura: o portal é um `/bin/false` no `$XDG_DATA_HOME/dbus-1/services` do lar, e o lar
não herda a sessão gráfica da casa.

AS-PARTES-QUE-TOCAM-A-MAQUINA-NAO-ACORDAM-O-PORTAL-01 (23/10/2026): o D-Bus do fecho da suíte
acordava o portal em 17 das 24 partes (8 pânicos por parte). O `servicos_sem_portal` do
`rodar-a-suite.sh` é o dono dos `.service` do lar das partes leves e do `SUITE_SOB_DBUS_PROPRIO=1`.

MORDIDA: arrancar uma das variáveis do `_AMBIENTE_DE_MENTIRA`, ou a chamada do
`_lar_sem_portal`, ou o `servicos_sem_portal "$_bus"`, e a régua reprova.
"""

from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PORTOES = RAIZ / "scripts" / "portoes.sh"
SUITE = RAIZ / "scripts" / "rodar-a-suite.sh"
#: fora do git (`docs/process/`): num clone limpo a régua dele pula, e as duas outras valem
FOTOS = RAIZ / "docs" / "process" / "ferramentas-da-leva" / "fecho-fotos.sh"

VARIAVEIS = ("XDG_CURRENT_DESKTOP=", "WAYLAND_DISPLAY=", "GIO_USE_VFS=local")
PORTAIS = ("org.freedesktop.portal.Desktop", "org.freedesktop.portal.Documents")


def _cobra_o_lar(texto: str, onde: str) -> None:
    for variavel in VARIAVEIS:
        assert re.search(rf"(?<![A-Z_]){re.escape(variavel)}(?=[\s\"]|$)", texto, re.M), (
            f"{onde}: o lar herda a sessão gráfica da casa sem `{variavel}`"
        )
    for portal in PORTAIS:
        assert portal in texto, f"{onde}: o `{portal}` não é um `/bin/false` no lar"
    assert "Exec=/bin/false" in texto and "dbus-1/services" in texto, onde


def test_o_ambiente_dos_portoes_nao_herda_a_sessao_grafica() -> None:
    texto = PORTOES.read_text(encoding="utf-8")
    bloco = re.search(r"^_AMBIENTE_DE_MENTIRA=\((.*?)^\)", texto, re.S | re.M)
    assert bloco, "o `_AMBIENTE_DE_MENTIRA` sumiu do portoes.sh"
    for variavel in VARIAVEIS:
        assert f'"{variavel}"' in bloco.group(1), f"o `_AMBIENTE_DE_MENTIRA` perdeu `{variavel}`"
    _cobra_o_lar(texto, "portoes.sh")


def test_cada_lar_de_pytest_dos_portoes_nasce_sem_portal() -> None:
    texto = PORTOES.read_text(encoding="utf-8")
    comando = re.search(r"^_comando_do_portao\(\).*?^}", texto, re.S | re.M)
    assert comando, "o `_comando_do_portao` sumiu do portoes.sh"
    assert '_lar_sem_portal "$LAR_DE_MENTIRA/$i/data"' in comando.group(0), (
        "o lar de cada `pytest` nasce sem o `_lar_sem_portal`"
    )


def _servicos_da_suite(texto: str) -> str:
    funcao = re.search(r"^servicos_sem_portal\(\).*?^}", texto, re.S | re.M)
    assert funcao, "o `servicos_sem_portal` sumiu do rodar-a-suite.sh"
    return funcao.group(0)


def test_o_lar_da_parte_leve_da_suite_nao_acorda_o_portal() -> None:
    texto = SUITE.read_text(encoding="utf-8")
    filho = re.search(r"^\s*lancar_filho\(\).*?^\s*\) &", texto, re.S | re.M)
    assert filho, "o `lancar_filho` sumiu do rodar-a-suite.sh"
    assert 'servicos_sem_portal "$lar/data"' in filho.group(0), (
        "o lar da parte leve nasce sem o `servicos_sem_portal`"
    )
    _cobra_o_lar(filho.group(0) + _servicos_da_suite(texto), "rodar-a-suite.sh")


#: o pytest de mentira: pede o portal ao D-Bus em que nasceu e anota a resposta e o `XDG_DATA_HOME`
PY_QUE_PEDE_O_PORTAL = """#!/usr/bin/env bash
[ "$1 $2" = "-m pytest" ] || exec python3 "$@"
dbus-send --session --print-reply --reply-timeout=10000 --dest=org.freedesktop.DBus \\
  /org/freedesktop/DBus org.freedesktop.DBus.StartServiceByName \\
  string:org.freedesktop.portal.Desktop uint32:0 > "$CHAMADAS.resposta" 2>&1
echo "rc=$? dados=${XDG_DATA_HOME-sem}" > "$CHAMADAS"
echo "1 passed in 0.01s"
"""


@pytest.mark.skipif(
    not (shutil.which("dbus-run-session") and shutil.which("dbus-send")),
    reason="sem dbus-run-session ou dbus-send",
)
@pytest.mark.parametrize("dados", ["/caminho/de/quem/chama", None])
def test_a_suite_sob_dbus_proprio_nao_acorda_o_portal(
    tmp_path: pathlib.Path, dados: str | None
) -> None:
    # AS-PARTES-QUE-TOCAM-A-MAQUINA-NAO-ACORDAM-O-PORTAL-01
    """O `SUITE_SOB_DBUS_PROPRIO=1` de verdade (o do fecho): o pytest pede o portal e não o acorda.

    A pasta dos serviços vai só ao `dbus-daemon`; o pytest vê o `XDG_DATA_HOME` de quem chamou.
    """
    raiz = tmp_path / "arvore"
    (raiz / "scripts").mkdir(parents=True)
    shutil.copy2(SUITE, raiz / "scripts" / "rodar-a-suite.sh")
    (raiz / "tests" / "unit").mkdir(parents=True)
    (raiz / "tests" / "unit" / "test_pede.py").write_text("def test_pede():\n    pass\n")
    (raiz / "lista").write_text("tests/unit/test_pede.py\n")
    bins = tmp_path / "bin"
    bins.mkdir()
    (bins / "xvfb-run").write_text('#!/usr/bin/env bash\n[ "$1" = -a ] && shift\nexec "$@"\n')
    py = tmp_path / "py"
    py.write_text(PY_QUE_PEDE_O_PORTAL)
    for exe in (bins / "xvfb-run", py):
        exe.chmod(0o755)
    for pasta in ("runtime", "tmp"):
        (tmp_path / pasta).mkdir()
    (tmp_path / "runtime").chmod(0o700)
    chamadas = tmp_path / "chamadas.txt"
    fora = {"XDG_DATA_HOME", "DBUS_SESSION_BUS_ADDRESS", "DISPLAY", "WAYLAND_DISPLAY", "LOTE",
            "PARTES", "PARTIDO", "PARTES_EM_PARALELO", "A_SECO", "LISTAR_O_WEBKIT", "LD_PRELOAD",
            "PYTEST_ADDOPTS", "SUITE_PYTEST_ARGS"}
    ambiente = {k: v for k, v in os.environ.items() if k not in fora}
    ambiente.update({
        "PATH": f"{bins}:{os.environ['PATH']}",
        "HOME": str(tmp_path),
        "XDG_RUNTIME_DIR": str(tmp_path / "runtime"),
        "TMPDIR": str(tmp_path / "tmp"),
        "XDG_CURRENT_DESKTOP": "COSMIC",
        "PY": str(py),
        "CHAMADAS": str(chamadas),
        "SAIDA": str(tmp_path / "saida"),
        "SUITE_SOB_DBUS_PROPRIO": "1",
    })
    if dados:
        ambiente["XDG_DATA_HOME"] = dados
    feito = subprocess.run(
        ["bash", str(raiz / "scripts" / "rodar-a-suite.sh"), "--lote", str(raiz / "lista")],
        cwd=raiz, env=ambiente, capture_output=True, text=True, timeout=120,
    )
    assert chamadas.is_file(), (
        "o pytest não rodou sob o D-Bus próprio", feito.stdout, feito.stderr
    )
    resposta = pathlib.Path(f"{chamadas}.resposta").read_text()
    anotado = chamadas.read_text().strip()
    assert not anotado.startswith("rc=0") and "uint32 1" not in resposta, (
        "o D-Bus da suíte acordou o portal da máquina", anotado, resposta
    )
    # o `/bin/false` do lar respondeu: não foi o bus que faltou
    assert "ChildExited" in resposta, ("o pedido não chegou ao serviço do lar", resposta)
    assert anotado.endswith(f"dados={dados or 'sem'}"), (
        "a pasta dos serviços vazou para o pytest", anotado
    )
    assert not list((tmp_path / "tmp").glob("suite-bus-*")), "a pasta dos serviços ficou para trás"


@pytest.mark.insumo_fora_do_git("docs/process/ferramentas-da-leva/fecho-fotos.sh")
def test_o_lar_das_fotos_nao_acorda_o_portal() -> None:
    _cobra_o_lar(FOTOS.read_text(encoding="utf-8"), "fecho-fotos.sh")


@pytest.mark.skipif(
    not (shutil.which("dbus-run-session") and shutil.which("dbus-send")),
    reason="sem dbus-run-session ou dbus-send",
)
def test_o_bus_do_lar_recusa_acordar_o_portal(tmp_path: pathlib.Path) -> None:
    # D-2210-O-LAR-DE-MENTIRA-NAO-TEM-PORTAL
    """O `_lar_sem_portal` de verdade, num bus próprio: pedir o portal falha, e nada sobe."""
    texto = PORTOES.read_text(encoding="utf-8")
    funcao = re.search(r"^_lar_sem_portal\(\).*?^}", texto, re.S | re.M)
    assert funcao, "o `_lar_sem_portal` sumiu do portoes.sh"
    for pasta in ("data", "runtime"):
        (tmp_path / pasta).mkdir()
    (tmp_path / "runtime").chmod(0o700)
    ambiente = {
        **os.environ,
        "HOME": str(tmp_path),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "XDG_RUNTIME_DIR": str(tmp_path / "runtime"),
        "XDG_CURRENT_DESKTOP": "",
        "WAYLAND_DISPLAY": "",
        "GIO_USE_VFS": "local",
    }
    roteiro = (
        f'{funcao.group(0)}\n_lar_sem_portal "$XDG_DATA_HOME"\n'
        "exec dbus-run-session -- dbus-send --session --print-reply "
        "--dest=org.freedesktop.DBus /org/freedesktop/DBus "
        "org.freedesktop.DBus.StartServiceByName "
        "string:org.freedesktop.portal.Desktop uint32:0\n"
    )
    feito = subprocess.run(
        ["bash", "-c", roteiro], env=ambiente, capture_output=True, text=True, timeout=60
    )
    assert feito.returncode != 0 and "uint32 1" not in feito.stdout, (
        "o bus do lar acordou o portal da máquina", feito.stdout, feito.stderr
    )
