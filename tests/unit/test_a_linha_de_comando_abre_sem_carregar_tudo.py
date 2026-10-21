"""A linha de comando abre sem carregar tudo (A-LINHA-DE-COMANDO-ABRE-SEM-CARREGAR-TUDO-01).

Medido em 21/10/2026, por `python -X importtime`: `import hefesto_dualsense4unix.cli.app` custava
0,27 s e 48 MB, e todo comando, até o `--help`, pagava o que só um subcomando usa: `cmd_mod` puxava
`mods.instalador` -> `mods.manifesto` -> `utils.maquina` -> `profiles.schema`, `cmd_profile` o
`profiles.loader`, `cmd_test` o `core.*` e o `structlog`, o pacote lia o `importlib.metadata` para a
versão. A cura é o import local na função que usa (sem truque de `sys.modules`), e a versão sai por
`__getattr__` do módulo (PEP 562).

A régua lê `sys.modules` de um processo LIMPO, depois de importar a raiz da linha de comando. Em
processo de teste isso não mede: o pytest já carregou metade do pacote.

MORDIDAS (executadas em 21/10/2026, uma por vez, devolvidas, md5 conferido):

* `from ...mods.instalador import ...` de volta ao topo do `cmd_mod.py` reprova
  `test_importar_a_raiz_nao_carrega_o_que_so_um_subcomando_usa` (mods.instalador, mods.manifesto,
  utils.maquina e profiles.schema aparecem juntos; os outros dois testes caem junto, porque o
  instalador arrasta o `importlib.metadata`);
* o `from importlib.metadata import ...` de volta ao topo do `__init__.py` reprova o mesmo teste
  (`importlib.metadata`) e `test_a_versao_so_se_le_quando_alguem_pede`; os outros dois passam.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

#: o que a raiz da linha de comando NÃO pode carregar ao ser importada: cada item é de um
#: subcomando só (ou de uma chamada) e entra pela função que o usa.
PROIBIDOS_AO_IMPORTAR = (
    "hefesto_dualsense4unix.mods.instalador",
    "hefesto_dualsense4unix.mods.manifesto",
    "hefesto_dualsense4unix.utils.maquina",
    "hefesto_dualsense4unix.profiles.schema",
    "hefesto_dualsense4unix.profiles.loader",
    "hefesto_dualsense4unix.profiles.slug",
    "hefesto_dualsense4unix.core.controller",
    "hefesto_dualsense4unix.core.led_control",
    "hefesto_dualsense4unix.core.trigger_effects",
    "hefesto_dualsense4unix.utils.logging_config",
    "hefesto_dualsense4unix.cli.ipc_client",
    "hefesto_dualsense4unix.app.ipc_bridge",
    "importlib.metadata",
    "structlog",
    "asyncio",
)

_SONDA = """
import json, sys
{antes}
import hefesto_dualsense4unix.cli.app
{depois}
print(json.dumps(sorted(sys.modules)))
"""


def _carregados(antes: str = "", depois: str = "") -> set[str]:
    """Os módulos de um processo limpo depois do import (e do `depois`, se houver)."""
    ambiente = {**os.environ, "PYTHONPATH": str(RAIZ / "src")}
    saida = subprocess.run(
        [sys.executable, "-c", _SONDA.format(antes=antes, depois=depois)],
        cwd=RAIZ, env=ambiente, check=True, capture_output=True, text=True, timeout=60,
    ).stdout
    return set(json.loads(saida.strip().splitlines()[-1]))


def test_importar_a_raiz_nao_carrega_o_que_so_um_subcomando_usa() -> None:
    carregados = _carregados()
    carregou = [m for m in PROIBIDOS_AO_IMPORTAR if m in carregados]
    assert not carregou, (
        "importar a raiz da linha de comando carregou o que só um subcomando usa; "
        "o import vai para dentro da função que o usa:\n" + "\n".join(carregou)
    )


def test_os_subcomandos_continuam_registrados_sem_o_import_de_topo() -> None:
    carregados = _carregados(
        depois=(
            "from typer.testing import CliRunner\n"
            "r = CliRunner().invoke(hefesto_dualsense4unix.cli.app.app, ['--help'])\n"
            "assert r.exit_code == 0, r.output\n"
            "for nome in ('mod', 'profile', 'test', 'plugin', 'native', 'gamepad', 'rumble'):\n"
            "    assert nome in r.output, nome\n"
        ),
    )
    assert "hefesto_dualsense4unix.mods.instalador" not in carregados, (
        "o --help listou os subcomandos e carregou o instalador: ele não precisa dele"
    )


def test_a_versao_so_se_le_quando_alguem_pede() -> None:
    sem_pedir = _carregados()
    assert "importlib.metadata" not in sem_pedir

    pedindo = _carregados(
        depois=(
            "import hefesto_dualsense4unix as h\n"
            "assert isinstance(h.__version__, str) and h.__version__.count('.') >= 2\n"
        ),
    )
    assert "importlib.metadata" in pedindo, "a versão deixou de ser lida do pacote instalado"


def test_o_atributo_que_nao_existe_continua_sendo_erro() -> None:
    import hefesto_dualsense4unix as h

    try:
        h.nada_disso_existe  # noqa: B018
    except AttributeError as exc:
        assert "nada_disso_existe" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("o __getattr__ do pacote engoliu um atributo inexistente")


def test_o_mypy_nao_ve_o_getattr_do_pacote() -> None:
    """O `__getattr__` visível ao mypy faria todo atributo do pacote valer `str`.

    Medido em 21/10/2026: com ele no topo, `from hefesto_dualsense4unix import nao_existe` passa no
    mypy calado. Ele mora no `else` do `if TYPE_CHECKING`, e o mypy lê só `__version__: str`.
    MORDIDA (21/10/2026): o `__getattr__` de volta ao topo do `__init__.py` reprova este teste.
    """
    import ast

    arvore = ast.parse((RAIZ / "src" / "hefesto_dualsense4unix" / "__init__.py").read_text("utf-8"))
    no_topo = [n.name for n in arvore.body if isinstance(n, ast.FunctionDef)]
    assert "__getattr__" not in no_topo, "o __getattr__ no topo: o mypy aceita qualquer atributo"
    guardas = [
        n for n in arvore.body
        if isinstance(n, ast.If) and ast.unparse(n.test) == "TYPE_CHECKING"
    ]
    assert any(
        any(isinstance(f, ast.FunctionDef) and f.name == "__getattr__" for f in g.orelse)
        and any(isinstance(a, ast.AnnAssign) and ast.unparse(a.target) == "__version__"
                for a in g.body)
        for g in guardas
    ), "o __getattr__ vai no else do `if TYPE_CHECKING`, e o corpo declara `__version__: str`"
