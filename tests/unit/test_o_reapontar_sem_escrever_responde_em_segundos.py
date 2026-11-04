"""O `reapontar-citacoes.py` sem `--escrever` não repete a busca na história por citação.

Medido em 03/11/2026 na árvore da casa: ~147 s. O custo era a repetição: o `git log`, o `git show`
e o `ast` do MESMO arquivo refeitos a cada citação, a leitura das MESMAS células do documento em
cada versão da história e um `ast.walk` que descia por todas as expressões. A régua conta o trabalho
(processos do git, `ast.parse`, leituras de célula), que não varia com a carga da máquina, em vez de
cronometrar.
"""

from __future__ import annotations

import importlib.util
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "reapontar-citacoes.py"
REGUA_DO_SRC = RAIZ / "tests" / "unit" / "test_portao_o_par_com_metade_ligada.py"
PACOTE = "src/hefesto_dualsense4unix"
FUNCOES = 6
COMMITS = 12


def _git(raiz: Path, *args: str) -> str:
    feito = subprocess.run(
        [
            "git",
            "-C",
            str(raiz),
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "user.name=régua",
            "-c",
            "user.email=regua@exemplo.invalid",
            *args,
        ],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"},
    )
    return feito.stdout


def _alvo(extras: int) -> str:
    topo = "".join(f"EXTRA_{n} = {n}\n" for n in range(extras))
    corpos = "".join(f"\n\ndef funcao_{n}():\n    x = {n}\n    return x\n" for n in range(FUNCOES))
    return '"""O alvo de mentira."""\n' + topo + corpos


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """Seis funções citadas por nome; o código anda por 12 commits sem o documento."""
    raiz = tmp_path / "r"
    (raiz / PACOTE).mkdir(parents=True)
    (raiz / "docs" / "data").mkdir(parents=True)
    (raiz / "docs" / "protocol").mkdir(parents=True)
    (raiz / "tests" / "unit").mkdir(parents=True)
    (raiz / "tests" / "unit" / REGUA_DO_SRC.name).write_bytes(REGUA_DO_SRC.read_bytes())
    alvo = raiz / PACOTE / "alvo.py"
    alvo.write_text(_alvo(0), encoding="utf-8")
    linhas = alvo.read_text(encoding="utf-8").splitlines()
    csv = ["id,prosa"]
    md = ["# Doc", ""]
    for n in range(FUNCOES):
        inicio = linhas.index(f"def funcao_{n}():") + 1
        csv.append(f'f.{n},"{PACOTE}/alvo.py:{inicio}-{inicio + 2} (`funcao_{n}`)"')
        md.append(f"A `funcao_{n}` em `{PACOTE}/alvo.py:{inicio}-{inicio + 2}`.")
        md.append("")
    for nome, funcoes in (("y", (1,)), ("z", (3,)), ("r", (0, 2, 4, 5))):
        citas = []
        for n in funcoes:
            inicio = linhas.index(f"def funcao_{n}():") + 1
            citas.append(f"O bloco em `{PACOTE}/alvo.py:{inicio}-{inicio + 2}`.")
        (raiz / "docs" / "protocol" / f"{nome}.md").write_text(
            f"# {nome}\n\n" + "\n\n".join(citas) + "\n", encoding="utf-8"
        )
    (raiz / "docs" / "data" / "mapa.csv").write_text("\n".join(csv) + "\n", encoding="utf-8")
    (raiz / "docs" / "protocol" / "x.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    _git(raiz, "init", "-q")
    _git(raiz, "add", ".")
    _git(raiz, "commit", "-q", "-m", "o alvo nasce")
    for passo in range(1, COMMITS):
        alvo.write_text(_alvo(passo), encoding="utf-8")
        _git(raiz, "commit", "-q", "-am", f"o código anda {passo}")
    return raiz


def _script() -> Any:
    spec = importlib.util.spec_from_file_location("reapontar_citacoes", SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["reapontar_citacoes"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _contar(modulo: Any, nome: str, contagem: list[int]) -> None:
    original = getattr(modulo, nome)

    def contado(*args: Any, **kwargs: Any) -> Any:
        contagem[0] += 1
        return original(*args, **kwargs)

    setattr(modulo, nome, contado)


def test_o_log_do_arquivo_se_le_uma_vez_por_arquivo(repo: Path) -> None:
    """Seis citações do MESMO arquivo: um `git log` dele, não um por citação."""
    modulo = _script()
    logs = [0]
    original = modulo._git

    def contado(raiz: Path, *args: str) -> Any:
        if args[0] == "log" and args[-1].endswith("alvo.py"):
            logs[0] += 1
        return original(raiz, *args)

    modulo._git = contado

    feitos, a_mao = modulo.reapontar(repo, escrever=False)

    assert a_mao == [], a_mao
    assert len([f for f in feitos if "alvo.py" in f]) >= FUNCOES, feitos
    assert logs[0] <= 1, f"{logs[0]} `git log` do mesmo arquivo: a busca voltou a ser por citação"


def test_o_ast_so_se_le_onde_a_linha_citada_abre_uma_definicao(repo: Path) -> None:
    """Seis citações da linha do `def`, de antes de o código andar.

    O `ast` de hoje se lê UMA vez, e o de cada versão só onde a linha citada começa uma definição
    (a resposta exige ``antes[0] == a``).
    """
    modulo = _script()
    arvores = [0]
    _contar(modulo, "_definicoes", arvores)
    alvo = f"{PACOTE}/alvo.py"
    primeira = _git(repo, "rev-list", "--max-parents=0", "HEAD").split()[0]
    velho = _git(repo, "show", f"{primeira}:{alvo}").splitlines()
    achadas = []
    with modulo._Cat(repo) as cat:
        for n in range(FUNCOES):
            linha = velho.index(f"def funcao_{n}():") + 1
            achadas.append(modulo.pelo_simbolo(repo, alvo, linha, linha, f"funcao_{n}", cat=cat))

    hoje = (repo / alvo).read_text(encoding="utf-8").splitlines()
    esperado = [(hoje.index(f"def funcao_{n}():") + 1,) * 2 for n in range(FUNCOES)]
    assert achadas == esperado, achadas
    assert arvores[0] <= 1 + FUNCOES, (
        f"{arvores[0]} leituras de `ast` para {COMMITS} versões: a de hoje voltou a ser "
        "refeita por "
        "citação, ou a de cada versão deixou de esperar a linha que abre uma definição"
    )


def test_a_mesma_celula_nao_se_le_de_novo_em_cada_versao(repo: Path) -> None:
    """Cada commit repete as linhas dos outros: `_achar` roda uma vez por texto distinto."""
    md = repo / "docs" / "protocol" / "r.md"
    for passo in range(COMMITS):
        md.write_text(
            md.read_text(encoding="utf-8") + f"\nUma linha nova {passo}: sem endereço.\n",
            encoding="utf-8",
        )
        _git(repo, "commit", "-q", "-am", f"o documento cresce {passo}")
    modulo = _script()
    lidas = [0]
    original = modulo._achar

    def contado(unidade: str, *args: Any, **kwargs: Any) -> Any:
        lidas[0] += "O bloco em" in unidade
        return original(unidade, *args, **kwargs)

    modulo._achar = contado

    modulo.reapontar(repo, escrever=False)

    teto = 3 * 6
    assert lidas[0] <= teto, (
        f"{lidas[0]} leituras das 6 linhas com endereço dos documentos crus em {COMMITS + 1} "
        f"versões (teto {teto}): a história voltou a reler as mesmas linhas"
    )


def test_o_paralelo_por_documento_da_o_mesmo_que_a_serie(repo: Path) -> None:
    """Vários documentos correm em processos; resultado, estatística e ordem são os da série."""
    resultados = []
    for limite in (1, 99):
        modulo = _script()
        modulo._DOCUMENTOS_PARA_PARALELO = limite
        feitos, a_mao = modulo.reapontar(repo, escrever=False)
        resultados.append((feitos, a_mao, dict(modulo.ESTATISTICA), dict(modulo.ESTADO_DA_MAO)))

    assert resultados[0] == resultados[1]
    for nome in ("y.md", "z.md", "r.md"):
        assert any(nome in f for f in resultados[0][0]), (nome, resultados[0][0])


_PAI_QUE_CAI = """
import importlib.util, sys
spec = importlib.util.spec_from_file_location("reapontar_citacoes", sys.argv[1])
m = importlib.util.module_from_spec(spec)
sys.modules["reapontar_citacoes"] = m
spec.loader.exec_module(m)
m._DOCUMENTOS_PARA_PARALELO = 1
original = m._um_documento

def maior_que_o_cano(*args, **kwargs):
    trocas, a_mao, estatistica, estado = original(*args, **kwargs)
    return trocas, a_mao + [f"{n:05d}" + "x" * 200 for n in range(2000)], estatistica, estado

def cai(raiz):
    raise RuntimeError("o pai caiu antes de colher")

m._um_documento = maior_que_o_cano
m.com_promessa = cai
m.reapontar(__import__("pathlib").Path(sys.argv[2]), escrever=False)
"""


def test_o_pai_que_cai_antes_de_colher_nao_trava_esperando_os_filhos(repo: Path) -> None:
    """Os filhos correm enquanto o pai segue; se o pai cair, o script sai com o erro, não trava.

    Com o resultado do filho maior que o cano, o filho espera o pai ler; o pai, ao sair, esperava
    o filho: a saída nunca vinha, e no fecho isso é um passo que não termina.
    """
    try:
        feito = subprocess.run(
            [sys.executable, "-c", _PAI_QUE_CAI, str(SCRIPT), str(repo)],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("o pai caiu e o script ficou esperando os filhos: nunca saiu")
    assert feito.returncode != 0, feito
    assert "o pai caiu antes de colher" in feito.stderr, feito.stderr[-2000:]


def _vivo(pid: int) -> bool:
    try:
        estado = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError):
        return False
    return estado != "Z"


def test_o_pai_que_morre_nao_deixa_filho_preso_no_cano(repo: Path, tmp_path: Path) -> None:
    """O pai morto por sinal (o `timeout` de quem roda o fecho) não deixa filho órfão para sempre.

    O filho que herda a ponta de leitura do próprio cano (ou a de uma irmã) nunca vê o cano sem
    leitor: com o pai morto, ele fica preso no `send` e não sai mais.
    """
    pids = tmp_path / "filhos.txt"
    morre = _PAI_QUE_CAI.replace(
        '    raise RuntimeError("o pai caiu antes de colher")',
        "    import multiprocessing, os, signal\n"
        "    filhos = [p.pid for p in multiprocessing.active_children()]\n"
        "    open(sys.argv[3], 'w').write(' '.join(map(str, filhos)))\n"
        "    os.kill(os.getpid(), signal.SIGKILL)",
    )
    assert morre != _PAI_QUE_CAI
    subprocess.run(
        [sys.executable, "-c", morre, str(SCRIPT), str(repo), str(pids)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=60,
    )
    filhos = [int(p) for p in pids.read_text(encoding="utf-8").split()]
    assert filhos, "o pai morreu antes de abrir os filhos: a régua não mediu nada"
    try:
        for _ in range(300):
            if not any(_vivo(p) for p in filhos):
                break
            time.sleep(0.1)
        presos = [p for p in filhos if _vivo(p)]
        assert not presos, f"filhos presos no cano depois de o pai morrer: {presos}"
    finally:
        for p in filhos:
            if _vivo(p):
                os.kill(p, signal.SIGKILL)
