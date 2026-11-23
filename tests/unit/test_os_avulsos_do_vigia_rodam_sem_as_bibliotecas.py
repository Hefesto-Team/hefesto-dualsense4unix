"""OS-AVULSOS-DO-VIGIA-DA-STEAM-RODAM-SEM-AS-BIBLIOTECAS-DO-PRODUTO-01: o avulso roda sem a venv.

A unidade do vigia, o ``disable_steam_input.sh``, o ``doctor.sh``, o ``install.sh`` e
``scripts/lib`` chamam módulos de ``integrations`` por ``python3``, o do sistema, sem
``structlog``, ``pydantic`` nem o pacote. Cada chamada que esses arquivos fazem sai deles
(nenhuma lista digitada) e roda aqui com ``-S -E`` num lar de mentira com uma biblioteca da Steam
de mentira, um jogo sem a linha e uma linha na tabela de opções por jogo. Nada que feche ou abra
a Steam roda: ``--fechar-steam`` e ``--reabrir-steam`` só com ``--help``, ``--stop-steam`` cai
fora da linha e o que escreve vai com ``--dry-run``.
"""

from __future__ import annotations

import re
import shlex
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
INTEGRACOES = RAIZ / "src" / "hefesto_dualsense4unix" / "integrations"
UNIDADE = RAIZ / "assets" / "hefesto-steam-input-guard.service"
ARQUIVOS_SHELL = (
    RAIZ / "scripts" / "disable_steam_input.sh",
    RAIZ / "scripts" / "doctor.sh",
    RAIZ / "install.sh",
    *sorted((RAIZ / "scripts" / "lib").glob("*.sh")),
)

APPID = "9912410"
CONTA = "1000"
BASE_DO_STEAMID64 = 76561197960265728
TAB = "\t"

FORA = {
    "proton_pin.py": "roda pelo Python do produto (PYTHON_DO_PINO): importa o pacote inteiro",
}
SO_COM_HELP = frozenset({"--fechar-steam", "--reabrir-steam", "--gravar-vdf", "escrever"})
SAI_DA_LINHA = frozenset({"--stop-steam"})
ESCREVEM = frozenset(
    {"--reparar", "--ligar", "--desligar-fora-da-lista", "--aplicar", "--apply", "--migrate"}
)
ACEITOS = (0, 3)

_CHAMADA = re.compile(
    r"python3(?:\s+-I)?\s+\"?(?:(?P<literal>\$\{ROOT_DIR\}/[\w./-]+\.py)|\$\{(?P<var>\w+)\})\"?"
)
_PREFIXOS_DE_COMANDO = (
    "$(", "if", "if !", "elif", "elif !", "!", "|", "||", "&&", ";", "then", "do", "{",
)
_CORTE = re.compile(r";|&&|\|\||\||\s\d?>|\s<|\)")
_UNIDADE = re.compile(
    r"^ExecStart\w*=.*?/usr/bin/env\s+python3\s+(?P<alvo>__\w+__)(?P<resto>.*)$"
)


@dataclass(frozen=True)
class Chamada:
    """Uma chamada de avulso lida de um arquivo: de onde veio, qual módulo e com que argumentos."""

    origem: str
    modulo: Path
    argumentos: tuple[str, ...]
    isolado: bool

    def __str__(self) -> str:
        return f"{self.origem}: {self.modulo.name} {' '.join(self.argumentos)}"


def _expande(valor: str, arquivo: Path) -> str:
    valor = valor.replace("${ROOT_DIR}", str(RAIZ)).replace("${_SCRIPT_DIR}", str(RAIZ / "scripts"))
    return re.sub(r"\$\{(\w+):-([^}]*)\}", r"\2", valor)


def _atribuicoes(arquivo: Path) -> dict[str, list[tuple[int, str]]]:
    achadas: dict[str, list[tuple[int, str]]] = {}
    for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
        par = re.match(r'^\s*(?:local\s+)?(\w+)="([^"]*)"\s*$', linha)
        if par:
            achadas.setdefault(par.group(1), []).append((n, par.group(2)))
    return achadas


def _resolve(variavel: str, arquivo: Path, linha: int) -> Path | None:
    """A atribuição mais próxima antes da linha, no mesmo arquivo; senão a de outro arquivo."""
    candidatas: list[tuple[Path, int, str]] = []
    for dono in (arquivo, *[a for a in ARQUIVOS_SHELL if a != arquivo]):
        atribuicoes = _atribuicoes(dono).get(variavel, [])
        if dono == arquivo:
            atribuicoes = [a for a in atribuicoes if a[0] < linha][-1:]
        candidatas.extend((dono, n, v) for n, v in atribuicoes)
        if any(c[0] == dono for c in candidatas):
            break
    for dono, _, valor in candidatas:
        caminho = Path(_expande(valor, dono))
        if caminho.suffix == ".py":
            return caminho.resolve()
    return None


def _argumentos(resto: str, onde: str) -> tuple[str, ...]:
    cortado = _CORTE.split(resto, maxsplit=1)[0]
    try:
        pedacos = shlex.split(cortado)
    except ValueError as erro:
        pytest.fail(f"{onde}: argumentos que a régua não lê ({erro}): {resto!r}")
    return tuple("@NADA@" if "$" in p else p for p in pedacos)


def _chamadas_da_unidade() -> list[Chamada]:
    substituicoes = {
        marca: variavel
        for marca, variavel in re.findall(
            r"-e \"s#(__\w+__)#\$\{(\w+)\}#g\"", (RAIZ / "install.sh").read_text(encoding="utf-8")
        )
    }
    achadas: list[Chamada] = []
    for n, linha in enumerate(UNIDADE.read_text(encoding="utf-8").splitlines(), 1):
        par = _UNIDADE.match(linha)
        if not par:
            continue
        onde = f"{UNIDADE.relative_to(RAIZ)}:{n}"
        variavel = substituicoes.get(par.group("alvo"))
        modulo = _resolve(variavel, RAIZ / "install.sh", 10**9) if variavel else None
        if modulo is None:
            pytest.fail(f"{onde}: a régua não resolve {par.group('alvo')} para um módulo")
        achadas.append(Chamada(onde, modulo, _argumentos(par.group("resto"), onde), False))
    return achadas


def _linhas_logicas(arquivo: Path) -> list[tuple[int, str]]:
    """As linhas do shell com a continuação colada, cada uma com o número da primeira."""
    logicas: list[tuple[int, str]] = []
    pendente: tuple[int, str] | None = None
    for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
        if pendente is not None:
            n, linha = pendente[0], pendente[1] + " " + linha.strip()
            pendente = None
        if linha.endswith("\\"):
            pendente = (n, linha[:-1].rstrip())
            continue
        logicas.append((n, linha))
    if pendente is not None:
        logicas.append(pendente)
    return logicas


def _chamadas_do_shell() -> list[Chamada]:
    achadas: list[Chamada] = []
    for arquivo in ARQUIVOS_SHELL:
        for n, linha in _linhas_logicas(arquivo):
            if linha.lstrip().startswith("#"):
                continue
            for par in _CHAMADA.finditer(linha):
                antes = linha[: par.start()].rstrip().removesuffix("sudo").rstrip()
                if antes and not antes.endswith(_PREFIXOS_DE_COMANDO):
                    continue
                onde = f"{arquivo.relative_to(RAIZ)}:{n}"
                if par.group("var"):
                    modulo = _resolve(par.group("var"), arquivo, n)
                else:
                    modulo = Path(_expande(par.group("literal"), arquivo)).resolve()
                if modulo is None or not modulo.is_file():
                    pytest.fail(f"{onde}: a régua não resolve o módulo de {par.group(0)!r}")
                isolado = "-I" in par.group(0).split()
                achadas.append(
                    Chamada(onde, modulo, _argumentos(linha[par.end():], onde), isolado)
                )
    return achadas


def os_avulsos() -> list[Chamada]:
    todas = [*_chamadas_da_unidade(), *_chamadas_do_shell()]
    return [c for c in todas if c.modulo.name not in FORA]


def _como_roda(chamada: Chamada, lar: Path) -> list[str]:
    argumentos = [a for a in chamada.argumentos if a not in SAI_DA_LINHA]
    if SO_COM_HELP & set(argumentos):
        return ["--help"]
    argumentos = [str(lar / "nada") if a == "@NADA@" else a for a in argumentos]
    fonte = chamada.modulo.read_text(encoding="utf-8")
    if ESCREVEM & set(argumentos) and '"--dry-run"' in fonte:
        argumentos.append("--dry-run")
    return argumentos


def _escrever(caminho: Path, texto: str) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto, encoding="utf-8")
    return caminho


@pytest.fixture
def lar(tmp_path: Path) -> Path:
    """Um lar de mentira com uma biblioteca da Steam, um jogo sem a linha e uma linha de opções."""
    casa = tmp_path / "casa"
    steam = casa / ".local" / "share" / "Steam"
    _escrever(
        steam / "steamapps" / f"appmanifest_{APPID}.acf",
        '"AppState"\n{\n'
        f'{TAB}"appid"{TAB}{TAB}"{APPID}"\n'
        f'{TAB}"name"{TAB}{TAB}"Jogo de Mentira"\n'
        f'{TAB}"installdir"{TAB}{TAB}"JogoDeMentira"\n}}\n',
    )
    (steam / "steamapps" / "common" / "JogoDeMentira").mkdir(parents=True)
    _escrever(
        steam / "config" / "loginusers.vdf",
        '"users"\n{\n'
        f'{TAB}"{BASE_DO_STEAMID64 + int(CONTA)}"\n{TAB}{{\n'
        f'{TAB}{TAB}"MostRecent"{TAB}{TAB}"1"\n{TAB}{TAB}"Timestamp"{TAB}{TAB}"1"\n{TAB}}}\n}}\n',
    )
    _escrever(
        steam / "userdata" / CONTA / "config" / "localconfig.vdf",
        '"UserLocalConfigStore"\n{\n'
        f'{TAB}"Software"\n{TAB}{{\n{TAB * 2}"Valve"\n{TAB * 2}{{\n'
        f'{TAB * 3}"Steam"\n{TAB * 3}{{\n{TAB * 4}"apps"\n{TAB * 4}{{\n'
        f'{TAB * 5}"{APPID}"\n{TAB * 5}{{\n{TAB * 6}"playtime"{TAB}{TAB}"42"\n{TAB * 5}}}\n'
        f"{TAB * 4}}}\n{TAB * 3}}}\n{TAB * 2}}}\n{TAB}}}\n}}\n",
    )
    _escrever(
        casa / ".config" / "hefesto-dualsense4unix" / "opcoes_por_jogo.txt",
        f"{APPID}{TAB}PROTON_LOG=1 %command%\n",
    )
    return casa


def _ambiente(lar: Path) -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(lar),
        "XDG_CONFIG_HOME": str(lar / ".config"),
        "XDG_STATE_HOME": str(lar / ".local" / "state"),
        "XDG_DATA_HOME": str(lar / ".local" / "share"),
    }


def _roda(
    chamada: Chamada, lar: Path, *, pre: str = ""
) -> subprocess.CompletedProcess[str]:
    argumentos = _como_roda(chamada, lar)
    interprete = [sys.executable, *(["-I"] if chamada.isolado else []), "-S", "-E"]
    if pre:
        comando = [
            *interprete,
            "-c",
            textwrap.dedent(
                f"""
                import runpy, sys
                {pre}
                sys.path.insert(0, {str(chamada.modulo.parent)!r})
                sys.argv = [{str(chamada.modulo)!r}, *{argumentos!r}]
                runpy.run_path({str(chamada.modulo)!r}, run_name="__main__")
                """
            ),
        ]
    else:
        comando = [*interprete, str(chamada.modulo), *argumentos]
    return subprocess.run(
        comando,
        capture_output=True,
        text=True,
        env=_ambiente(lar),
        cwd=str(lar),
        timeout=120,
    )


def _ids(chamadas: list[Chamada]) -> list[str]:
    return [f"{c.modulo.stem}@{c.origem}" for c in chamadas]


AVULSOS = os_avulsos()


def test_a_lista_dos_avulsos_sai_dos_arquivos() -> None:
    """Cada chamador conhecido aparece; a lista não é digitada, e o pino fica de fora com motivo."""
    modulos = {c.modulo.name for c in AVULSOS}
    assert {
        "sentinela_do_wrapper.py",
        "opcoes_por_jogo.py",
        "steam_input_ponte.py",
        "steam_launch_options.py",
    } <= modulos
    origens = {c.origem.split(":")[0] for c in AVULSOS}
    assert {
        "assets/hefesto-steam-input-guard.service",
        "scripts/disable_steam_input.sh",
        "scripts/doctor.sh",
        "install.sh",
        "scripts/lib/a_steam_fechada_uma_vez.sh",
    } <= origens
    assert "proton_pin.py" in FORA


@pytest.mark.parametrize("chamada", AVULSOS, ids=_ids(AVULSOS))
def test_o_avulso_roda_sem_as_bibliotecas_do_produto(chamada: Chamada, lar: Path) -> None:
    """MORDIDA: um import de fora na cadeia do avulso reprova pela frase do módulo que falta."""
    proc = _roda(chamada, lar)
    saida = proc.stdout + proc.stderr
    assert "Traceback" not in proc.stderr, f"{chamada}\n{proc.stderr}"
    assert "No module named" not in saida, f"{chamada}\n{saida}"
    assert proc.returncode in ACEITOS, f"{chamada} rc={proc.returncode}\n{saida}"


def test_o_vigia_cobre_o_jogo_novo_com_o_python_do_sistema(lar: Path) -> None:
    """A frase do jogo novo prova que o prontuário rodou de verdade, não só que o avulso subiu."""
    chamadas = [
        c
        for c in AVULSOS
        if c.modulo.name == "sentinela_do_wrapper.py" and "--reparar" in c.argumentos
    ]
    assert chamadas
    for chamada in chamadas:
        proc = _roda(chamada, lar)
        assert "SEM wrapper (novo)" in proc.stdout, f"{chamada}\n{proc.stdout}\n{proc.stderr}"
        assert "reparo:" in proc.stdout


_ESTRUTURA_DE_MENTIRA = """
import os
import sys

DO_AVULSO = {"logger_do_avulso.py", "api_de_entrada.py", "ficha_declarada.py", "a_roupa_do_jogo.py"}
quadro = sys._getframe()
vistos = set()
while quadro is not None:
    vistos.add(os.path.basename(quadro.f_code.co_filename))
    quadro = quadro.f_back
if vistos & DO_AVULSO:
    sys.stderr.write("structlog de mentira importado pelo avulso\\n")
    os._exit(97)
raise ModuleNotFoundError("No module named 'structlog'")
"""


@pytest.mark.parametrize(
    ("nome", "gesto"),
    [
        ("sentinela_do_wrapper.py", "--reparar"),
        ("opcoes_por_jogo.py", "--aplicar"),
        ("steam_input_ponte.py", "--ligar"),
    ],
)
def test_o_modo_decide_e_nao_a_presenca_da_biblioteca(
    nome: str, gesto: str, lar: Path, tmp_path: Path
) -> None:
    """MORDIDA: o adaptador que tenta o dono primeiro importa o `structlog` do sistema e sai 97."""
    falso = tmp_path / "falso"
    _escrever(falso / "structlog.py", _ESTRUTURA_DE_MENTIRA)
    chamada = next(
        c for c in AVULSOS if c.modulo.name == nome and gesto in c.argumentos
    )
    proc = _roda(chamada, lar, pre=f"sys.path.insert(0, {str(falso)!r})")
    assert "importado pelo avulso" not in proc.stderr, f"{chamada}\n{proc.stderr}"
    assert proc.returncode in ACEITOS, f"{chamada} rc={proc.returncode}\n{proc.stderr}"


def test_a_regua_enxerga_o_traceback_de_um_avulso_que_cai(lar: Path, tmp_path: Path) -> None:
    """O instrumento morde: um módulo que pede biblioteca de fora reprova a saída que a régua lê."""
    modulo = _escrever(tmp_path / "cai.py", "import biblioteca_que_nao_existe\n")
    chamada = Chamada("cai.py:1", modulo, (), False)
    proc = _roda(chamada, lar)
    assert "Traceback" in proc.stderr
    assert "No module named" in proc.stderr
    assert proc.returncode not in ACEITOS
