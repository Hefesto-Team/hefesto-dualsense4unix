"""O broker crava cada raiz do sistema uma vez só, na constante dela.

Em 25/10/2026 (`da0fbc48b`), `"/sys/class/bluetooth"` aparecia 7 vezes no broker,
`"/sys/class/input"` 4 e `"/dev"` 7, cada uma como padrão de um parâmetro: até sete lugares para a
mesma raiz divergir no processo root que decide o que se expõe ao jogo. A sprint
O-BROKER-CRAVA-CADA-RAIZ-DO-SISTEMA-UMA-VEZ-SO-01 deu a cada raiz uma constante de módulo, e todo
padrão a lê. A régua lê a árvore de sintaxe do broker e conta, por raiz, o caminho que começa nela
em qualquer texto fora das docstrings (a constante, o padrão de um parâmetro, o começo de uma
f-string, um recado): só a constante dela fica.

O broker não importa o pacote (o install copia só ele e ele roda no python3 do sistema), logo as
constantes moram nele, e não num dono do pacote.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

BROKER = (Path(__file__).resolve().parents[2]
          / "src" / "hefesto_dualsense4unix" / "broker" / "hidraw_broker.py")

#: cada raiz do sistema que o broker lê, e a constante que a crava.
RAIZES = {
    "DEV_ROOT": "/dev",
    "DEV_INPUT_ROOT": "/dev/input",
    "SYS_CLASS_HIDRAW": "/sys/class/hidraw",
    "SYS_CLASS_INPUT": "/sys/class/input",
    "SYS_CLASS_BLUETOOTH": "/sys/class/bluetooth",
    "SYS_CLASS_UDC": "/sys/class/udc",
    "SYS_PLATFORM": "/sys/devices/platform",
    "SYS_BUS_HID_DRIVERS": "/sys/bus/hid/drivers",
    "CONFIGFS_GADGETS": "/sys/kernel/config/usb_gadget",
}

#: a raiz começa o caminho (no começo do texto ou depois de um separador) e termina nele ou numa
#: barra: `/devices` não é `/dev`, e `/dev/input/event3` é da raiz mais longa, a `DEV_INPUT_ROOT`.
_CAMINHO = re.compile(
    r"(?:^|(?<=[\s'\"(=:,]))("
    + "|".join(re.escape(r) for r in sorted(RAIZES.values(), key=len, reverse=True))
    + r")(?=$|[/\s'\")*,:])")
_DONO_DA_RAIZ = {raiz: nome for nome, raiz in RAIZES.items()}


def _docstrings(arvore: ast.Module) -> set[int]:
    ids: set[int] = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            primeiro = no.body[0] if no.body else None
            if isinstance(primeiro, ast.Expr) and isinstance(primeiro.value, ast.Constant):
                ids.add(id(primeiro.value))
    return ids


def _continuacoes(arvore: ast.Module) -> set[int]:
    """O `id` dos pedaços de f-string que seguem um `{...}`: em `f"{sys_dir}/dev"`, o `/dev` é o
    atributo do sysfs, e não a raiz."""
    ids: set[int] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.JoinedStr):
            for antes, pedaco in zip(no.values, no.values[1:], strict=False):
                if isinstance(antes, ast.FormattedValue) and isinstance(pedaco, ast.Constant):
                    ids.add(id(pedaco))
    return ids


def raizes_cravadas(fonte: str) -> dict[str, list[int]]:
    """A constante de cada raiz e as linhas em que o texto dela aparece, fora das docstrings."""
    arvore = ast.parse(fonte)
    docs, continua = _docstrings(arvore), _continuacoes(arvore)
    achados: dict[str, list[int]] = {}
    for no in ast.walk(arvore):
        if not (isinstance(no, ast.Constant) and isinstance(no.value, str)) or id(no) in docs:
            continue
        for casou in _CAMINHO.finditer(no.value):
            if casou.start() == 0 and id(no) in continua:
                continue
            achados.setdefault(_DONO_DA_RAIZ[casou.group(1)], []).append(no.lineno)
    return {nome: sorted(linhas) for nome, linhas in achados.items()}


def constantes_de_cima(fonte: str) -> dict[str, tuple[object, int]]:
    """O valor e a linha de cada nome ligado a um texto no nível de cima do módulo."""
    nomes: dict[str, tuple[object, int]] = {}
    for no in ast.parse(fonte).body:
        if isinstance(no, ast.Assign):
            alvos, valor = no.targets, no.value
        elif isinstance(no, ast.AnnAssign) and no.value is not None:
            alvos, valor = [no.target], no.value
        else:
            continue
        if isinstance(valor, ast.Constant):
            for alvo in alvos:
                if isinstance(alvo, ast.Name):
                    nomes[alvo.id] = (valor.value, no.lineno)
    return nomes


def test_a_regua_pega_cada_forma_da_raiz() -> None:
    assert raizes_cravadas('def f(r="/sys/class/bluetooth"):\n    pass\n') == {
        "SYS_CLASS_BLUETOOTH": [1]}
    assert raizes_cravadas('def f(n):\n    return open(f"/dev/{n}")\n') == {"DEV_ROOT": [2]}
    assert raizes_cravadas('X = "/dev/input/event3"\n') == {"DEV_INPUT_ROOT": [1]}
    assert raizes_cravadas('raise OSError(2, f"nenhum /dev/hidg* tem o dev {a}")\n') == {
        "DEV_ROOT": [1]}
    assert raizes_cravadas('def f(d):\n    return open(f"{d}/dev")\n') == {}
    assert raizes_cravadas('X = "/devices/virtual/"\nY = "/proc/self/fd/3"\n') == {}
    assert raizes_cravadas('"""/sys/class/input na docstring."""\n') == {}
    assert raizes_cravadas('class C:\n    dev: str = "/dev"\n') == {"DEV_ROOT": [2]}
    assert constantes_de_cima('A = "/dev"\nB: str = "/sys/class/input"\n') == {
        "A": ("/dev", 1), "B": ("/sys/class/input", 2)}


def test_cada_raiz_tem_a_constante_dela_no_broker() -> None:
    constantes = constantes_de_cima(BROKER.read_text(encoding="utf-8"))
    errados = {nome: constantes.get(nome, (None, 0))[0] for nome, raiz in RAIZES.items()
               if constantes.get(nome, (None, 0))[0] != raiz}
    assert errados == {}, f"a constante de cada raiz falta ou mudou de valor no broker: {errados}"


def test_cada_raiz_so_aparece_na_constante_dela() -> None:
    fonte = BROKER.read_text(encoding="utf-8")
    constantes = constantes_de_cima(fonte)
    fora = {nome: [linha for linha in linhas if linha != constantes.get(nome, (None, 0))[1]]
            for nome, linhas in raizes_cravadas(fonte).items()}
    fora = {nome: linhas for nome, linhas in fora.items() if linhas}
    assert fora == {}, (
        "a raiz cravada fora da constante dela no broker (linhas): "
        + "; ".join(f"leia `{nome}` em {linhas}" for nome, linhas in sorted(fora.items())))


def test_o_broker_carrega_sozinho_sem_o_pacote() -> None:
    """As constantes moram no broker porque ele roda no python3 do sistema, sem o pacote: o
    broker se carrega sozinho no `python3 -I`, e nenhum módulo `hefesto*` entra junto."""
    roteiro = (
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('broker_sozinho', {str(BROKER)!r})\n"
        "mod = sys.modules[spec.name] = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"
        "print(sorted(m for m in sys.modules if m.startswith('hefesto')))\n"
        f"print(mod.SYS_CLASS_BLUETOOTH, mod.SYS_CLASS_INPUT, mod.DEV_ROOT)\n")
    sistema = "/usr/bin/python3" if Path("/usr/bin/python3").exists() else sys.executable
    saida = subprocess.run([sistema, "-I", "-c", roteiro], capture_output=True,
                           text=True, timeout=30, check=False)
    assert saida.returncode == 0, saida.stderr
    assert saida.stdout.splitlines() == [
        "[]", "/sys/class/bluetooth /sys/class/input /dev"], saida.stdout
