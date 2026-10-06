"""Os portões rodam em paralelo e lembram o verde, sem perder o que mordem.

OS-PORTOES-RODAM-EM-PARALELO-E-LEMBRAM-O-VERDE-01 (06/10/2026). O `scripts/portoes.sh` rodava 66
portões um por um e não lembrava nada: a mesma árvore, verde há cinco minutos, rodava de novo. Estas
réguas rodam o `portoes.sh` REAL (com a tabela trocada por portões de brinquedo, numa árvore git de
mentira) e conferem:

- o veredito da corrida paralela é o da corrida em série, sobre a árvore verde e com uma mordida
  plantada em cada classe (um `py`, um `pytest` de tela, um `bin`);
- dois portões ao mesmo tempo nunca dividem lar, bus nem display;
- a saída sai na ordem da lista, e a parede é menor que a soma;
- a memória não esconde nada: arquivo mudado, arquivo novo (também o não rastreado), o próprio
  portão e o ignorado de `scripts/` fazem o portão rodar de novo; vermelho, «NÃO MEDIDO» e pulo
  nunca são lembrados;
- o recibo do push continua pedindo a camada completa da MESMA árvore.

Cada cura tem a mordida ao lado: o motor arrancado de propósito (numa cópia) tem de ser reprovado
pela régua.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
from datetime import date
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTOES = RAIZ / "scripts" / "portoes.sh"
RECIBO = RAIZ / "scripts" / "recibo_da_medida.py"

TELA = shutil.which("xvfb-run") is not None
_STATUS = re.compile(r"^  (\S+)\s+(ok|VERMELHO|lembrado|NÃO MEDIDO|AUSENTE)")


# --- a árvore de mentira ------------------------------------------------------------------------


def _ambiente(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("GIT_")
        and k
        not in {
            "PYTEST_ADDOPTS",
            "CI",
            "HEFESTO_VEZ_DO_PYTEST",
            "PORTOES_VAGAS",
            "PORTOES_VAGAS_PYTEST",
        }
    }
    env.update(
        {
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "teste",
            "GIT_AUTHOR_EMAIL": "teste@example.com",
            "GIT_COMMITTER_NAME": "teste",
            "GIT_COMMITTER_EMAIL": "teste@example.com",
            "HEFESTO_PY": sys.executable,
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    env.update(extra or {})
    return env


def _git(repo: Path, *args: str) -> str:
    feito = subprocess.run(
        ["git", *args], cwd=repo, env=_ambiente(), capture_output=True, text=True, check=False
    )
    assert feito.returncode == 0, f"git {args}: {feito.stderr}"
    return feito.stdout.strip()


def _com_tabela(texto: str, tabela: str) -> str:
    abre = texto.index("_LISTA() {")
    corpo = texto.index("TABELA\n}", abre)
    novo = (
        texto[:abre] + "_LISTA() {\n  cat <<'TABELA'\n" + tabela.strip("\n") + "\n" + texto[corpo:]
    )
    assert "cat <<'TABELA'\n" + tabela.strip("\n").splitlines()[0] in novo, (
        "a troca da tabela não pegou — o formato do `_LISTA` mudou"
    )
    return novo


_PY_MARCA = textwrap.dedent("""\
    import pathlib, sys
    sys.exit(1 if "MORDIDA" in pathlib.Path("dados/marca.txt").read_text() else 0)
    """)
_PY_OK = "import sys\nsys.exit(0)\n"
_TESTE_TELA = textwrap.dedent("""\
    import pathlib


    def test_a_tela_nao_foi_mordida():
        assert "MORDIDA" not in pathlib.Path("dados/tela.txt").read_text()
    """)

ARQUIVOS_BASE = {
    ".gitignore": "__pycache__/\n*.tmp\nlixo/\nscripts/ig.sh\n",
    "dados/marca.txt": "limpo\n",
    "dados/tela.txt": "limpo\n",
    "dados/bin.txt": "igual\n",
    "dados/bin.ok": "igual\n",
    "dados/a/x.txt": "a\n",
    "dados/b/x.txt": "b\n",
    "scripts/g_marca.py": _PY_MARCA,
    "scripts/g_ok.py": _PY_OK,
    "tests/test_tela.py": _TESTE_TELA,
}

#: uma linha por classe, na ordem de propósito: `py`, `pytest` (de tela) e `bin`.
TABELA_DAS_TRES = """
rapido|py-marca|py|scripts/g_marca.py
completo|pytest-tela|pytest|tests/test_tela.py
completo|bin-marca|bin|cmp -s dados/bin.txt dados/bin.ok
"""


def _monta(
    tmp_path: Path,
    tabela: str,
    *,
    arquivos: dict[str, str] | None = None,
    portoes: str | None = None,
    recibo: str | None = None,
) -> Path:
    repo = tmp_path / "arvore"
    repo.mkdir()
    _git(repo, "init", "-q")
    todos = dict(ARQUIVOS_BASE)
    todos.update(arquivos or {})
    for rel, conteudo in todos.items():
        alvo = repo / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(conteudo, encoding="utf-8")
    texto = _com_tabela(
        portoes if portoes is not None else PORTOES.read_text(encoding="utf-8"), tabela
    )
    (repo / "scripts" / "portoes.sh").write_text(texto, encoding="utf-8")
    (repo / "scripts" / "recibo_da_medida.py").write_text(
        recibo if recibo is not None else RECIBO.read_text(encoding="utf-8"), encoding="utf-8"
    )
    _git(repo, "add", "--", *todos, "scripts/portoes.sh", "scripts/recibo_da_medida.py")
    _git(repo, "commit", "-q", "-m", "base")
    return repo


def _corre(
    repo: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "scripts/portoes.sh", *args],
        cwd=repo,
        env=_ambiente(env),
        capture_output=True,
        text=True,
        check=False,
        timeout=240,
    )


def _status(saida: str) -> dict[str, str]:
    achados: dict[str, str] = {}
    for linha in saida.splitlines():
        m = _STATUS.match(linha)
        if m:
            achados[m.group(1)] = m.group(2)
    return achados


def _recibos(repo: Path) -> set[str]:
    pasta = repo / ".git" / "hefesto-recibos"
    return {p.name for p in pasta.iterdir()} if pasta.is_dir() else set()


# --- 1. O veredito é o da série -----------------------------------------------------------------

_MORDIDAS = {
    "a-arvore-verde": {},
    "mordida-no-py": {"dados/marca.txt": "MORDIDA\n"},
    "mordida-no-pytest-de-tela": {"dados/tela.txt": "MORDIDA\n"},
    "mordida-no-bin": {"dados/bin.txt": "diferente\n"},
    "uma-em-cada-classe": {
        "dados/marca.txt": "MORDIDA\n",
        "dados/tela.txt": "MORDIDA\n",
        "dados/bin.txt": "diferente\n",
    },
}
_VERMELHOS_ESPERADOS = {
    "a-arvore-verde": set(),
    "mordida-no-py": {"py-marca"},
    "mordida-no-pytest-de-tela": {"pytest-tela"},
    "mordida-no-bin": {"bin-marca"},
    "uma-em-cada-classe": {"py-marca", "pytest-tela", "bin-marca"},
}


def _as_duas_corridas(repo: Path) -> tuple[dict[str, str], dict[str, str]]:
    serie = _corre(repo, "--em-serie", "--sem-memoria")
    paralela = _corre(repo, "--sem-memoria")
    return _status(serie.stdout), _status(paralela.stdout)


@pytest.mark.parametrize("cenario", sorted(_MORDIDAS))
def test_a_corrida_paralela_da_o_mesmo_veredito_da_serie(tmp_path: Path, cenario: str) -> None:
    repo = _monta(tmp_path, TABELA_DAS_TRES, arquivos=_MORDIDAS[cenario])
    serie, paralela = _as_duas_corridas(repo)
    assert set(serie) == {"py-marca", "pytest-tela", "bin-marca"}, serie
    assert serie == paralela, (
        f"{cenario}: o paralelo deu outro veredito.\nsérie:   {serie}\nparalelo: {paralela}"
    )
    vermelhos = {k for k, v in paralela.items() if v == "VERMELHO"}
    assert vermelhos == _VERMELHOS_ESPERADOS[cenario], (cenario, paralela)
    assert {k for k, v in paralela.items() if v == "ok"} == set(paralela) - vermelhos, paralela


def test_o_rc_da_corrida_e_o_do_veredito_nos_dois_modos(tmp_path: Path) -> None:
    repo = _monta(tmp_path, TABELA_DAS_TRES, arquivos=_MORDIDAS["mordida-no-bin"])
    assert _corre(repo, "--em-serie", "--sem-memoria").returncode == 1
    assert _corre(repo, "--sem-memoria").returncode == 1
    (tmp_path / "outra").mkdir()
    limpo = _monta(tmp_path / "outra", TABELA_DAS_TRES)
    assert _corre(limpo, "--sem-memoria").returncode == 0


def test_morde_o_paralelo_que_engole_vermelho(tmp_path: Path) -> None:
    """A MORDIDA: o motor que, em paralelo, devolve rc=0 a quem reprovou é pego pela régua."""
    texto = PORTOES.read_text(encoding="utf-8")
    velho = '''printf '%d' "$rc" > "$OUT/$n.rc.tmp"'''
    assert texto.count(velho) == 1, (
        "o motor mudou: a mordida precisa apontar para onde o rc é escrito"
    )
    mutante = texto.replace(
        velho, '''printf '%d' "$(( VAGAS_GERAIS > 1 ? 0 : rc ))" > "$OUT/$n.rc.tmp"'''
    )
    repo = _monta(tmp_path, TABELA_DAS_TRES, arquivos=_MORDIDAS["mordida-no-py"], portoes=mutante)
    serie, paralela = _as_duas_corridas(repo)
    assert serie != paralela, (
        "a régua não viu o paralelo engolir um vermelho: ela não mede o veredito"
    )
    assert serie["py-marca"] == "VERMELHO" and paralela["py-marca"] == "ok"


# --- 2. Dois portões não se pisam ---------------------------------------------------------------

_TESTE_DE_PAR = textwrap.dedent("""\
    import os
    import pathlib
    import time

    ponto = pathlib.Path(os.environ["PONTO_DE_ENCONTRO"])
    NOME = "{nome}"
    OUTRO = "{outro}"


    def test_o_outro_nao_ve_o_que_eu_planto():
        lar = pathlib.Path(os.environ["HOME"])
        (lar / ("marca-" + NOME)).write_text(NOME)
        env = {{k: os.environ.get(k, "") for k in ("HOME", "XDG_CONFIG_HOME", "XDG_RUNTIME_DIR",
                                                   "TMPDIR",
                                                   "DISPLAY", "DBUS_SESSION_BUS_ADDRESS")}}
        (ponto / NOME).write_text(repr(env))
        limite = time.monotonic() + 40
        while not (ponto / OUTRO).exists():
            assert time.monotonic() < limite, "o outro portão não rodou junto: foi em série"
            time.sleep(0.05)
        assert not (lar / ("marca-" + OUTRO)).exists(), "o outro portão escreveu NO MEU lar"
        outro = eval((ponto / OUTRO).read_text())
        for nome in ("HOME", "XDG_CONFIG_HOME", "XDG_RUNTIME_DIR", "TMPDIR"):
            assert env[nome] and env[nome] != outro[nome], nome + " dividido entre dois portões"
        if os.environ.get("EXIGE_TELA"):
            assert env["DISPLAY"] and env["DISPLAY"] != outro["DISPLAY"], "mesmo display"
            assert env["DBUS_SESSION_BUS_ADDRESS"] != outro["DBUS_SESSION_BUS_ADDRESS"], "mesmo bus"
    """)

TABELA_DO_PAR = """
rapido|par-a|pytest|tests/test_par_a.py
rapido|par-b|pytest|tests/test_par_b.py
"""


def _repo_do_par(tmp_path: Path, **kw: str) -> tuple[Path, Path]:
    ponto = tmp_path / "ponto"
    ponto.mkdir()
    arquivos = {
        "tests/test_par_a.py": _TESTE_DE_PAR.format(nome="a", outro="b"),
        "tests/test_par_b.py": _TESTE_DE_PAR.format(nome="b", outro="a"),
    }
    return _monta(tmp_path, TABELA_DO_PAR, arquivos=arquivos, **kw), ponto


@pytest.mark.skipif(not TELA, reason="sem xvfb-run a régua do display não mede (pulo não é verde)")
def test_dois_pytest_ao_mesmo_tempo_nao_dividem_lar_bus_nem_display(tmp_path: Path) -> None:
    repo, ponto = _repo_do_par(tmp_path)
    r = _corre(
        repo,
        "--rapido",
        "--sem-memoria",
        env={"PORTOES_VAGAS_PYTEST": "2", "PONTO_DE_ENCONTRO": str(ponto), "EXIGE_TELA": "1"},
    )
    assert _status(r.stdout) == {"par-a": "ok", "par-b": "ok"}, r.stdout + r.stderr


def test_dois_pytest_ao_mesmo_tempo_nao_dividem_o_lar(tmp_path: Path) -> None:
    repo, ponto = _repo_do_par(tmp_path)
    r = _corre(
        repo,
        "--rapido",
        "--sem-memoria",
        env={"PORTOES_VAGAS_PYTEST": "2", "PONTO_DE_ENCONTRO": str(ponto)},
    )
    assert _status(r.stdout) == {"par-a": "ok", "par-b": "ok"}, r.stdout + r.stderr


def test_morde_o_lar_dividido(tmp_path: Path) -> None:
    """A MORDIDA: com o lar único de antes, o par se enxerga e a régua reprova."""
    texto = PORTOES.read_text(encoding="utf-8")
    velho = "${_AMBIENTE_DE_MENTIRA[*]//$LAR_DE_MENTIRA/$LAR_DE_MENTIRA/$i}"
    assert texto.count(velho) == 1
    mutante = texto.replace(velho, "${_AMBIENTE_DE_MENTIRA[*]}")
    repo, ponto = _repo_do_par(tmp_path, portoes=mutante)
    r = _corre(
        repo,
        "--rapido",
        "--sem-memoria",
        env={"PORTOES_VAGAS_PYTEST": "2", "PONTO_DE_ENCONTRO": str(ponto)},
    )
    assert "VERMELHO" in r.stdout, (
        "o lar dividido passou: a régua não mede o isolamento\n" + r.stdout
    )


def test_em_serie_os_dois_pytest_nao_se_encontram(tmp_path: Path) -> None:
    """O encontro só acontece em paralelo: é ele que prova a simultaneidade."""
    repo, ponto = _repo_do_par(tmp_path)
    texto = (repo / "tests" / "test_par_a.py").read_text(encoding="utf-8").replace("40", "3")
    (repo / "tests" / "test_par_a.py").write_text(texto, encoding="utf-8")
    _git(repo, "add", "--", "tests/test_par_a.py")
    r = _corre(
        repo, "--rapido", "--sem-memoria", "--em-serie", env={"PONTO_DE_ENCONTRO": str(ponto)}
    )
    assert _status(r.stdout)["par-a"] == "VERMELHO", r.stdout


# --- 3. A ordem, a parede e a vaga --------------------------------------------------------------


def _tabela_de_sonos(n: int) -> tuple[str, dict[str, str]]:
    linhas, arquivos = [], {}
    for i in range(n):
        # o primeiro é o mais lento: se a impressão seguisse a conclusão, ele sairia por último
        segundos = 2.0 if i == 0 else 0.5
        arquivos[f"scripts/dorme{i}.py"] = f"import time\ntime.sleep({segundos})\n"
        linhas.append(f"rapido|dorme{i}|py|scripts/dorme{i}.py")
    return "\n".join(linhas), arquivos


def test_a_saida_sai_na_ordem_da_lista_e_a_parede_e_menor_que_a_soma(tmp_path: Path) -> None:
    tabela, arquivos = _tabela_de_sonos(8)
    repo = _monta(tmp_path, tabela, arquivos=arquivos)
    comeco = time.monotonic()
    r = _corre(repo, "--rapido", "--sem-memoria", env={"PORTOES_VAGAS": "8"})
    parede = time.monotonic() - comeco
    ordem = [m.group(1) for linha in r.stdout.splitlines() if (m := _STATUS.match(linha))]
    assert ordem == [f"dorme{i}" for i in range(8)], r.stdout
    soma = 2.0 + 7 * 0.5
    assert parede < soma * 0.8, (
        f"parede de {parede:.1f} s para {soma:.1f} s de portões: não houve paralelo"
    )
    assert "tempo:" in r.stdout


def test_em_serie_e_uma_vaga_so(tmp_path: Path) -> None:
    tabela, arquivos = _tabela_de_sonos(4)
    repo = _monta(tmp_path, tabela, arquivos=arquivos)
    comeco = time.monotonic()
    _corre(repo, "--rapido", "--sem-memoria", "--em-serie", env={"PORTOES_VAGAS": "8"})
    assert time.monotonic() - comeco >= 2.0 + 3 * 0.5 - 0.1


_VEZ_DE_MENTIRA = textwrap.dedent("""\
    #!/usr/bin/env bash
    echo "vez $*" >> "$ANOTA_A_VEZ"
    exec "$@"
    """)


def _repo_da_vez(tmp_path: Path, **kw: str) -> tuple[Path, Path, dict[str, str]]:
    anota = tmp_path / "vez.log"
    vez = tmp_path / "vez-do-pytest.sh"
    vez.write_text(_VEZ_DE_MENTIRA, encoding="utf-8")
    repo = _monta(tmp_path, "rapido|pytest-tela|pytest|tests/test_tela.py", **kw)
    return repo, anota, {"HEFESTO_VEZ_DO_PYTEST": str(vez), "ANOTA_A_VEZ": str(anota)}


def test_o_pytest_pede_a_vez_da_casa_quando_ela_existe(tmp_path: Path) -> None:
    repo, anota, env = _repo_da_vez(tmp_path)
    r = _corre(repo, "--rapido", "--sem-memoria", env=env)
    assert _status(r.stdout) == {"pytest-tela": "ok"}, r.stdout
    assert anota.is_file() and "pytest" in anota.read_text(encoding="utf-8"), (
        "o pytest não passou pela vez"
    )


def _corre_dentro_de_uma_vaga(
    repo: Path, tmp_path: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    vagas = tmp_path / "estado" / "vagas"
    vagas.mkdir(parents=True)
    return subprocess.run(
        ["bash", "-c", f'exec 9>"{vagas}/vaga-2"; bash scripts/portoes.sh --rapido --sem-memoria'],
        cwd=repo,
        env=_ambiente(env),
        capture_output=True,
        text=True,
        check=False,
        timeout=240,
    )


def test_quem_ja_esta_numa_vaga_nao_pede_vaga_de_novo(tmp_path: Path) -> None:
    """Três corridas de agente, cada uma numa vaga e esperando outra, se travariam para sempre."""
    repo, anota, env = _repo_da_vez(tmp_path)
    r = _corre_dentro_de_uma_vaga(repo, tmp_path, env)
    assert _status(r.stdout) == {"pytest-tela": "ok"}, r.stdout + r.stderr
    assert not anota.exists(), "o portão pediu vaga de novo estando dentro de uma"
    assert "dentro de uma vaga" in r.stdout


def test_morde_o_pedido_de_vaga_dentro_da_vaga(tmp_path: Path) -> None:
    texto = PORTOES.read_text(encoding="utf-8")
    velho = "*/vagas/vaga-*) _dentro_da_vaga=1 ;;"
    assert texto.count(velho) == 1
    repo, anota, env = _repo_da_vez(tmp_path, portoes=texto.replace(velho, "*/vagas/vaga-*) : ;;"))
    _corre_dentro_de_uma_vaga(repo, tmp_path, env)
    assert anota.exists(), "sem a detecção da vaga o pedido continua: a régua de cima não morde"


# --- 4. A memória não esconde nada --------------------------------------------------------------

TABELA_DA_MEMORIA = """
rapido|inteiro|py|scripts/g_ok.py
rapido|estreito|py|scripts/g_estreito.py|dados/a/**
rapido|sempre|py|scripts/g_ok.py|@sempre
rapido|sem-arquivo|py|scripts/g_ok.py|nada/**
"""
_ARQUIVOS_DA_MEMORIA = {"scripts/g_estreito.py": _PY_OK}


def _repo_da_memoria(tmp_path: Path, **kw: str) -> Path:
    return _monta(tmp_path, TABELA_DA_MEMORIA, arquivos=_ARQUIVOS_DA_MEMORIA, **kw)


def _roda_duas_vezes(repo: Path) -> dict[str, str]:
    primeira = _status(_corre(repo, "--rapido").stdout)
    assert set(primeira.values()) == {"ok"}, primeira
    return _status(_corre(repo, "--rapido").stdout)


def test_o_verde_de_antes_nao_roda_de_novo_e_o_que_nao_se_lembra_roda(tmp_path: Path) -> None:
    segunda = _roda_duas_vezes(_repo_da_memoria(tmp_path))
    assert segunda == {
        "inteiro": "lembrado",
        "estreito": "lembrado",
        "sempre": "ok",
        "sem-arquivo": "ok",
    }


def test_a_entrada_que_nao_casa_arquivo_e_dita_e_o_portao_roda(tmp_path: Path) -> None:
    repo = _repo_da_memoria(tmp_path)
    r = _corre(repo, "--rapido")
    assert "«nada/**» não casa arquivo nenhum" in r.stdout, r.stdout


def _mexer(repo: Path, como: str) -> dict[str, str]:
    """Corre, muda a árvore DE UM JEITO, corre de novo: devolve o que rodou na segunda."""
    assert set(_status(_corre(repo, "--rapido").stdout).values()) == {"ok"}
    (repo / "lixo").mkdir(exist_ok=True)
    if como == "arquivo-rastreado-sem-git-add-dentro":
        (repo / "dados/a/x.txt").write_text("mudou\n", encoding="utf-8")
    elif como == "arquivo-rastreado-fora":
        (repo / "dados/b/x.txt").write_text("mudou\n", encoding="utf-8")
    elif como == "arquivo-novo-nao-rastreado-dentro":
        (repo / "dados/a/novo.txt").write_text("novo\n", encoding="utf-8")
    elif como == "arquivo-novo-nao-rastreado-fora":
        (repo / "dados/b/novo.txt").write_text("novo\n", encoding="utf-8")
    elif como == "o-proprio-portao":
        (repo / "scripts/g_estreito.py").write_text(_PY_OK + "# mudou\n", encoding="utf-8")
    elif como == "ignorado-dentro-da-entrada":
        (repo / "dados/a/ig.tmp").write_text("ignorado\n", encoding="utf-8")
    elif como == "ignorado-de-scripts":
        (repo / "scripts/ig.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    elif como == "ignorado-de-outro-lugar":
        (repo / "lixo/x").write_text("ignorado\n", encoding="utf-8")
    else:  # pragma: no cover
        raise AssertionError(como)
    return _status(_corre(repo, "--rapido").stdout)


@pytest.mark.parametrize(
    ("como", "inteiro", "estreito"),
    [
        ("arquivo-rastreado-sem-git-add-dentro", "ok", "ok"),
        ("arquivo-rastreado-fora", "ok", "lembrado"),
        ("arquivo-novo-nao-rastreado-dentro", "ok", "ok"),
        ("arquivo-novo-nao-rastreado-fora", "ok", "lembrado"),
        ("o-proprio-portao", "ok", "ok"),
        ("ignorado-dentro-da-entrada", "lembrado", "ok"),
        ("ignorado-de-scripts", "ok", "lembrado"),
        ("ignorado-de-outro-lugar", "lembrado", "lembrado"),
    ],
)
def test_o_que_muda_faz_o_portao_rodar_de_novo(
    tmp_path: Path, como: str, inteiro: str, estreito: str
) -> None:
    depois = _mexer(_repo_da_memoria(tmp_path), como)
    assert (depois["inteiro"], depois["estreito"]) == (inteiro, estreito), (como, depois)


def test_morde_a_memoria_que_ignora_o_arquivo_novo(tmp_path: Path) -> None:
    """A MORDIDA: com a memória que não vê arquivo não rastreado, o `estreito` fica «lembrado» sobre
    um arquivo novo dentro das entradas dele, e é exatamente o que a régua de cima reprova."""
    texto = RECIBO.read_text(encoding="utf-8")
    velho = '"--cached", "--others", "--exclude-standard"'
    assert texto.count(velho) == 2, (
        "a memória mudou: a mordida precisa apontar para as duas listagens"
    )
    mutante = texto.replace(velho, '"--cached", "--exclude-standard"')
    depois = _mexer(_repo_da_memoria(tmp_path, recibo=mutante), "arquivo-novo-nao-rastreado-dentro")
    assert depois["estreito"] == "lembrado", (
        "a mordida não pegou: a régua não distingue o arquivo novo"
    )
    (tmp_path / "real").mkdir()
    depois_real = _mexer(_repo_da_memoria(tmp_path / "real"), "arquivo-novo-nao-rastreado-dentro")
    assert depois_real["estreito"] == "ok"


def test_morde_a_memoria_que_ignora_o_proprio_portao(tmp_path: Path) -> None:
    texto = RECIBO.read_text(encoding="utf-8")
    velho = "if (ent.raiz / pedaco).is_file():\n            arquivos.add(pedaco)"
    assert texto.count(velho) == 1
    mutante = texto.replace(velho, "if False:\n            arquivos.add(pedaco)")
    depois = _mexer(_repo_da_memoria(tmp_path, recibo=mutante), "o-proprio-portao")
    assert depois["estreito"] == "lembrado", (
        "sem o arquivo do portão na chave, mudá-lo não o roda de novo"
    )


# O PORTÃO QUE LÊ O ÍNDICE (`git ls-files`, `git show :caminho`) é cego ao arquivo novo antes do
# `git add`, e a memória não pode piorar isso: o mesmo arquivo, com os mesmos bytes, agora no índice, é
# outra pergunta. A chave tem de ver o índice, não só o disco.

_PY_INDICE = textwrap.dedent("""\
    import subprocess, sys
    rastreados = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout
    sys.exit(1 if "dados/proibido.txt" in rastreados.splitlines() else 0)
    """)
_PY_ENCENADO = textwrap.dedent("""\
    import subprocess, sys
    encenado = subprocess.run(["git", "show", ":dados/a/x.txt"], capture_output=True, text=True).stdout
    sys.exit(1 if "MORDIDA" in encenado else 0)
    """)
TABELA_DO_INDICE = """
rapido|indice|py|scripts/g_indice.py
rapido|encenado|py|scripts/g_encenado.py
"""


def _mexer_no_indice(repo: Path, como: str) -> list[dict[str, str]]:
    """Corre na árvore limpa, muda o DISCO, corre, dá o `git add`, corre: devolve as duas últimas."""
    assert set(_status(_corre(repo, "--rapido").stdout).values()) == {"ok"}
    if como == "arquivo-novo":
        (repo / "dados/proibido.txt").write_text("novo\n", encoding="utf-8")
        caminho = "dados/proibido.txt"
    else:
        (repo / "dados/a/x.txt").write_text("MORDIDA\n", encoding="utf-8")
        caminho = "dados/a/x.txt"
    antes_do_add = _status(_corre(repo, "--rapido").stdout)
    _git(repo, "add", "--", caminho)
    return [antes_do_add, _status(_corre(repo, "--rapido").stdout)]


def _repo_do_indice(tmp_path: Path, **kw: str) -> Path:
    return _monta(
        tmp_path,
        TABELA_DO_INDICE,
        arquivos={"scripts/g_indice.py": _PY_INDICE, "scripts/g_encenado.py": _PY_ENCENADO},
        **kw,
    )


@pytest.mark.parametrize(("como", "portao"), [("arquivo-novo", "indice"), ("encenado", "encenado")])
def test_o_git_add_faz_o_portao_que_le_o_indice_rodar_de_novo(
    tmp_path: Path, como: str, portao: str
) -> None:
    antes_do_add, depois_do_add = _mexer_no_indice(_repo_do_indice(tmp_path), como)
    assert antes_do_add[portao] == "ok", antes_do_add
    assert depois_do_add[portao] == "VERMELHO", (
        "o mesmo disco com outro índice ficou «lembrado»: a memória piorou a cegueira do `git add`",
        depois_do_add,
    )


def test_morde_a_memoria_que_ignora_o_indice(tmp_path: Path) -> None:
    texto = RECIBO.read_text(encoding="utf-8")
    velho = 'h.update(f"{rel}\\0{ent.sha(rel)}\\0{ent.no_indice(rel)}\\n".encode())'
    assert texto.count(velho) == 1, "a memória mudou: a mordida precisa apontar para a linha do índice"
    mutante = texto.replace(velho, 'h.update(f"{rel}\\0{ent.sha(rel)}\\n".encode())')
    _, depois_do_add = _mexer_no_indice(_repo_do_indice(tmp_path, recibo=mutante), "arquivo-novo")
    assert depois_do_add["indice"] == "lembrado", (
        "a mordida não pegou: a régua não distingue o índice do disco"
    )


# A ÁRVORE QUE MUDA DURANTE A CORRIDA: a chave é a do começo, e o portão mede os bytes do meio. O portão
# abaixo faz, na primeira vez, o papel de quem salva um arquivo enquanto os portões rodam: troca a marca
# mordida pela limpa antes de ler. O verde dele é dos bytes limpos, e não pode ficar lembrado sob a chave
# dos mordidos.

_PY_QUEM_SALVA_NO_MEIO = textwrap.dedent("""\
    import pathlib, sys
    vez = pathlib.Path("lixo/ja-salvou")
    if not vez.exists():
        vez.parent.mkdir(exist_ok=True)
        vez.write_text("1")
        pathlib.Path("dados/marca.txt").write_text("limpo\\n")
    sys.exit(1 if "MORDIDA" in pathlib.Path("dados/marca.txt").read_text() else 0)
    """)


def _a_arvore_muda_no_meio(tmp_path: Path, **kw: str) -> dict[str, str]:
    repo = _monta(
        tmp_path,
        "rapido|salva|py|scripts/g_salva.py",
        arquivos={"scripts/g_salva.py": _PY_QUEM_SALVA_NO_MEIO, "dados/marca.txt": "MORDIDA\n"},
        **kw,
    )
    assert _status(_corre(repo, "--rapido").stdout) == {"salva": "ok"}
    (repo / "dados/marca.txt").write_text("MORDIDA\n", encoding="utf-8")
    return _status(_corre(repo, "--rapido").stdout)


def test_o_verde_de_uma_arvore_que_mudou_no_meio_nao_fica_lembrado(tmp_path: Path) -> None:
    assert _a_arvore_muda_no_meio(tmp_path) == {"salva": "VERMELHO"}, (
        "o verde dos bytes do meio ficou lembrado sob a chave dos bytes do começo"
    )


def test_morde_a_memoria_que_nao_confere_a_chave_depois(tmp_path: Path) -> None:
    texto = PORTOES.read_text(encoding="utf-8")
    velho = 'if [ "${_CHAVE_DEPOIS[$_a]:-}" = "$_b" ]; then'
    assert texto.count(velho) == 1
    depois = _a_arvore_muda_no_meio(tmp_path, portoes=texto.replace(velho, "if true; then"))
    assert depois == {"salva": "lembrado"}, (
        "a mordida não pegou: a régua não vê a chave que não foi conferida depois da corrida"
    )


def test_vermelho_nao_e_lembrado(tmp_path: Path) -> None:
    repo = _monta(
        tmp_path, "rapido|py-marca|py|scripts/g_marca.py", arquivos=_MORDIDAS["mordida-no-py"]
    )
    assert _status(_corre(repo, "--rapido").stdout) == {"py-marca": "VERMELHO"}
    assert _status(_corre(repo, "--rapido").stdout) == {"py-marca": "VERMELHO"}


def test_o_nao_medido_nao_e_lembrado(tmp_path: Path) -> None:
    repo = _monta(
        tmp_path,
        "rapido|sem-dado|py|scripts/g_sem_dado.py",
        arquivos={"scripts/g_sem_dado.py": "print('NÃO MEDIDO: faltou o dado')\n"},
    )
    for _ in range(2):
        assert _status(_corre(repo, "--rapido").stdout) == {"sem-dado": "NÃO MEDIDO"}


def test_o_pytest_com_pulo_nao_e_lembrado(tmp_path: Path) -> None:
    repo = _monta(
        tmp_path,
        "rapido|pulo|pytest|tests/test_pulo.py",
        arquivos={
            "tests/test_pulo.py": "import pytest\n\n\ndef test_x():\n    pytest.skip('sem dado')\n"
        },
    )
    for _ in range(2):
        r = _corre(repo, "--rapido")
        assert _status(r.stdout) == {"pulo": "ok"}, r.stdout
        assert "pulado" in r.stdout


def test_morde_a_memoria_que_lembra_o_pulo(tmp_path: Path) -> None:
    texto = PORTOES.read_text(encoding="utf-8")
    velho = '[ -z "$pulos" ] && [ -n "${G_CHAVE[n]}" ] && VERDES_TSV+='
    assert texto.count(velho) == 1
    mutante = texto.replace(velho, '[ -n "${G_CHAVE[n]}" ] && VERDES_TSV+=')
    repo = _monta(
        tmp_path,
        "rapido|pulo|pytest|tests/test_pulo.py",
        portoes=mutante,
        arquivos={
            "tests/test_pulo.py": "import pytest\n\n\ndef test_x():\n    pytest.skip('sem dado')\n"
        },
    )
    _corre(repo, "--rapido")
    assert _status(_corre(repo, "--rapido").stdout) == {"pulo": "lembrado"}, (
        "a mordida não pegou: a régua do pulo não vê o portão que lembra o que não mediu"
    )


def test_morde_a_memoria_que_lembra_o_vermelho(tmp_path: Path) -> None:
    texto = PORTOES.read_text(encoding="utf-8")
    velho = '    VERMELHOS+=("$id")\n'
    assert texto.count(velho) == 1
    anota = (
        '    [ -n "${G_CHAVE[n]}" ] && VERDES_TSV+="$id"$\'\\t\'"${G_CHAVE[n]}"'
        '$\'\\t\'"$ms"$\'\\n\'\n'
    )
    mutante = texto.replace(velho, velho + anota)
    repo = _monta(
        tmp_path,
        "rapido|py-marca|py|scripts/g_marca.py",
        portoes=mutante,
        arquivos=_MORDIDAS["mordida-no-py"],
    )
    _corre(repo, "--rapido")
    assert _status(_corre(repo, "--rapido").stdout) == {"py-marca": "lembrado"}, (
        "a mordida não pegou: a régua do vermelho não vê o portão que lembra a reprovação"
    )


def test_a_opcao_sem_memoria_e_a_variavel_ci_rodam_tudo(tmp_path: Path) -> None:
    repo = _repo_da_memoria(tmp_path)
    assert set(_status(_corre(repo, "--rapido").stdout).values()) == {"ok"}
    assert _status(_corre(repo, "--rapido").stdout)["inteiro"] == "lembrado"
    assert set(_status(_corre(repo, "--rapido", "--sem-memoria").stdout).values()) == {"ok"}
    assert set(_status(_corre(repo, "--rapido", env={"CI": "true"}).stdout).values()) == {"ok"}


def test_em_serie_lembra_e_pula_igual(tmp_path: Path) -> None:
    repo = _repo_da_memoria(tmp_path)
    _corre(repo, "--rapido", "--em-serie")
    assert _status(_corre(repo, "--rapido", "--em-serie").stdout)["inteiro"] == "lembrado"


def _chaves(repo: Path, linha: str) -> str:
    feito = subprocess.run(
        [sys.executable, "scripts/recibo_da_medida.py", "chaves", "--raiz", str(repo)],
        cwd=repo,
        env=_ambiente(),
        input=linha + "\n",
        capture_output=True,
        text=True,
        check=False,
    )
    assert feito.returncode == 0, feito.stderr
    return next(ln.split("\t")[1] for ln in feito.stdout.splitlines() if not ln.startswith("#"))


def test_o_prazo_que_vence_poe_a_data_na_chave(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo_da_memoria(tmp_path)
    espec = importlib.util.spec_from_file_location(
        "recibo_sob_teste", repo / "scripts" / "recibo_da_medida.py"
    )
    assert espec and espec.loader
    modulo = importlib.util.module_from_spec(espec)
    sys.modules["recibo_sob_teste"] = modulo
    espec.loader.exec_module(modulo)
    ent = modulo.Entradas(repo)
    ambiente = "x"

    def chave(dia: date, sinais: list[str]) -> str | None:
        class Hoje(date):
            @classmethod
            def today(cls) -> date:  # type: ignore[override]
                return dia

        monkeypatch.setattr(modulo, "date", Hoje)
        return modulo.chave_do_portao(ent, ambiente, "p", "py", "scripts/g_ok.py", sinais)

    assert chave(date(2026, 10, 6), ["@dia"]) != chave(date(2026, 10, 7), ["@dia"]), (
        "o prazo vence amanhã e a chave de hoje continua valendo"
    )
    assert chave(date(2026, 10, 6), []) == chave(date(2026, 10, 7), [])
    assert chave(date(2026, 10, 6), ["@sempre"]) is None
    assert chave(date(2026, 10, 6), ["@que-nao-existe"]) is None


def test_os_mesmos_bytes_em_outra_arvore_nao_sao_o_mesmo_verde(tmp_path: Path) -> None:
    """O portão que confere a PRÓPRIA árvore pode passar numa e reprovar noutra."""
    (tmp_path / "um").mkdir()
    (tmp_path / "dois").mkdir()
    um = _repo_da_memoria(tmp_path / "um")
    dois = _repo_da_memoria(tmp_path / "dois")
    linha = "p|py|scripts/g_ok.py|dados/a/**"
    assert _chaves(um, linha) != _chaves(dois, linha)


def test_o_head_na_chave_acompanha_a_historia(tmp_path: Path) -> None:
    repo = _repo_da_memoria(tmp_path)
    sem = "p|py|scripts/g_ok.py|dados/a/**"
    com = "p|py|scripts/g_ok.py|dados/a/** @head"
    antes = (_chaves(repo, sem), _chaves(repo, com))
    _git(repo, "commit", "-q", "--allow-empty", "-m", "só a história mudou")
    depois = (_chaves(repo, sem), _chaves(repo, com))
    assert antes[0] == depois[0], "a árvore é a mesma e a chave sem @head mudou"
    assert antes[1] != depois[1], "o @head não entrou na chave"


# --- 5. O recibo do push ------------------------------------------------------------------------


def _repo_do_recibo(tmp_path: Path, **kw: str) -> Path:
    return _monta(tmp_path, TABELA_DAS_TRES, **kw)


def test_o_recibo_continua_pedindo_a_camada_completa_da_mesma_arvore(tmp_path: Path) -> None:
    repo = _repo_do_recibo(tmp_path)
    arvore = _git(repo, "write-tree")
    _corre(repo, "--rapido")
    assert _recibos(repo) == set(), "o --rapido deixou recibo"

    r = _corre(repo)  # a camada completa, com os verdes do rápido na memória
    assert r.returncode == 0, r.stdout
    assert _recibos(repo) == {f"{arvore}.portoes-completo"}, r.stdout
    texto = (repo / ".git" / "hefesto-recibos" / f"{arvore}.portoes-completo").read_text(
        encoding="utf-8"
    )
    assert "lembrados: py-marca" in texto, texto
    assert "arvore: " + arvore in texto

    # outra árvore (um arquivo novo no índice): os portões rodam e o recibo é de OUTRA árvore
    (repo / "dados" / "novo.txt").write_text("novo\n", encoding="utf-8")
    _git(repo, "add", "--", "dados/novo.txt")
    nova = _git(repo, "write-tree")
    assert nova != arvore
    r2 = _corre(repo)
    assert r2.returncode == 0, r2.stdout
    assert _status(r2.stdout) == {"py-marca": "ok", "pytest-tela": "ok", "bin-marca": "ok"}, (
        r2.stdout
    )
    assert f"{nova}.portoes-completo" in _recibos(repo)


def test_o_vermelho_de_antes_nao_vira_recibo_pela_memoria(tmp_path: Path) -> None:
    repo = _repo_do_recibo(tmp_path, arquivos=_MORDIDAS["mordida-no-bin"])
    _corre(repo)
    r = _corre(repo)
    assert r.returncode == 1
    assert _recibos(repo) == set()


# --- 6. A quinta coluna não quebra quem lê as quatro --------------------------------------------


def test_a_tabela_real_so_acrescenta_uma_quinta_coluna_conhecida() -> None:
    saida = subprocess.run(
        ["bash", str(PORTOES), "--listar"], capture_output=True, text=True, check=True, cwd=RAIZ
    ).stdout
    quantas = 0
    for linha in saida.splitlines():
        if not linha.startswith("PORTAO|") or linha.startswith("PORTAO|#"):
            continue
        campos = linha.split("|")
        assert campos[1] in {"rapido", "completo", "suite"}, linha
        assert len(campos) in (5, 6), f"a tabela tem de ter 4 ou 5 colunas: {linha}"
        # quem lê as quatro (o `ci-local.sh`, o portão do portão) acha o comando na quarta
        assert campos[3] in {"py", "bash", "bin", "pytest"}, linha
        if len(campos) == 6:
            quantas += 1
            for token in campos[5].split():
                assert token in {"@sempre", "@dia", "@head"} or not token.startswith("@"), linha
    assert quantas >= 1, "nenhum portão declara entradas: a quinta coluna não tem uso"


def test_o_portoes_sh_nao_usa_o_pytest_sem_lar_proprio() -> None:
    texto = PORTOES.read_text(encoding="utf-8")
    assert "-p no:cacheprovider" in texto
    assert "//$LAR_DE_MENTIRA/$LAR_DE_MENTIRA/$i" in texto


# --- 7. O que a árvore não guarda, o portão declara ----------------------------------------------
#
# Medido em 06/10/2026 com `strace -f -e trace=execve` sobre os 66 portões: estes leem a história do
# git, a máquina ou a data, que a chave por conteúdo não alcança. Sem a declaração, o verde de ontem
# valeria hoje.

_DECLARADOS = {
    "a-origem": ("@sempre", "git log base..HEAD, merge-base com o dev, rev-parse HEAD"),
    "autoria-historia": ("@sempre", "rev-parse das tags e a história inteira"),
    "autoria-arvore": ("@sempre", "git config hooks.anonimato.isento"),
    "endereco-dela-em-toda-forma": ("@sempre", "pergunta à máquina: bluetoothctl e sysfs"),
    "regua-de-tela": ("@sempre", "git diff --cached, git show e rev-list"),
    "interpretador-do-portao": ("@sempre", "git worktree list: as outras árvores da máquina"),
    "src-desta-arvore": ("@sempre", "git worktree list: as outras árvores da máquina"),
    "paridade-transporte": ("@dia", "date.today(): dívida com prazo que vence"),
    "fala-de-tela": ("@dia", "date.today(): prazo que vence"),
}


def _tokens_da_tabela(texto_sh: str) -> dict[str, str]:
    achados: dict[str, str] = {}
    abre = texto_sh.index("_LISTA() {")
    corpo = texto_sh[texto_sh.index("cat <<'TABELA'\n", abre) :]
    for linha in corpo[: corpo.index("\nTABELA\n")].splitlines():
        campos = linha.split("|")
        if len(campos) >= 5 and not linha.startswith("#"):
            tokens = [t for t in campos[4].split() if t.startswith("@")]
            if tokens:
                achados[campos[1]] = " ".join(tokens)
    return achados


def test_o_portao_que_le_o_que_a_arvore_nao_guarda_declara_isso() -> None:
    achados = _tokens_da_tabela(PORTOES.read_text(encoding="utf-8"))
    esperados = {nome: token for nome, (token, _) in _DECLARADOS.items()}
    assert achados == esperados, (
        "a declaração de um portão mudou: quem lê a história, a máquina ou a data tem de dizer, "
        "ou o verde de ontem vale hoje.\n"
        + "\n".join(f"  {n}: {m}" for n, (_, m) in _DECLARADOS.items())
    )


def test_morde_o_token_arrancado_da_tabela() -> None:
    texto = PORTOES.read_text(encoding="utf-8")
    velho = "rapido|a-origem|py|scripts/check_a_origem.py|@sempre\n"
    assert texto.count(velho) == 1
    sem = _tokens_da_tabela(texto.replace(velho, velho.replace("|@sempre", "")))
    assert "a-origem" not in sem, "a régua não vê o token arrancado"
    assert sem != {n: t for n, (t, _) in _DECLARADOS.items()}
