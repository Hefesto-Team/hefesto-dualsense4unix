"""As citações `arquivo:linha` andam com o código — o `scripts/reapontar-citacoes.py`."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "reapontar-citacoes.py"
REGUA_DO_SRC = RAIZ / "tests" / "unit" / "test_portao_o_par_com_metade_ligada.py"

ALVO = '''"""O alvo de mentira."""

VALOR = 1


def primeira():
    return 1


def segunda():
    x = 2
    return x


def terceira():
    return 3
'''

CSV = (
    "id,prosa\n"
    'linha.um,"a conta em src/hefesto_dualsense4unix/alvo.py:10-12 (`segunda`, que soma)'
    ' · outra em src/hefesto_dualsense4unix/alvo.py:15 (`terceira`)"\n'
)
MD = "# Doc\n\nO `terceira` em `src/hefesto_dualsense4unix/alvo.py:15-16` responde.\n"
CITANTE = '"""Quem cita."""\n\n# `segunda` mora em `alvo.py:10-12`.\nVALOR = 2\n'


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


@pytest.fixture()
def repo(tmp_path: Path) -> Iterator[Path]:
    """Um repositório com o alvo, um CSV do mapa, um `.md` da canônica e um citante em src/."""
    raiz = tmp_path / "repo"
    pacote = raiz / "src" / "hefesto_dualsense4unix"
    pacote.mkdir(parents=True)
    (pacote / "alvo.py").write_text(ALVO, encoding="utf-8")
    (pacote / "citante.py").write_text(CITANTE, encoding="utf-8")
    (raiz / "docs" / "data").mkdir(parents=True)
    (raiz / "docs" / "data" / "mapa.csv").write_text(CSV, encoding="utf-8")
    (raiz / "docs" / "protocol").mkdir(parents=True)
    (raiz / "docs" / "protocol" / "x.md").write_text(MD, encoding="utf-8")
    (raiz / "tests" / "unit").mkdir(parents=True)
    shutil.copy(REGUA_DO_SRC, raiz / "tests" / "unit" / REGUA_DO_SRC.name)
    _git(raiz, "init", "-q")
    _git(raiz, "add", ".")
    _git(raiz, "commit", "-q", "-m", "o alvo nasce")
    yield raiz


def _script():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("reapontar_citacoes", SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["reapontar_citacoes"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _inserir_no_topo(raiz: Path, linhas: int, *, commitar: bool) -> None:
    alvo = raiz / "src" / "hefesto_dualsense4unix" / "alvo.py"
    texto = alvo.read_text(encoding="utf-8").split("\n")
    novo = texto[:2] + [f"EXTRA_{n} = {n}" for n in range(linhas)] + texto[2:]
    alvo.write_text("\n".join(novo), encoding="utf-8")
    if commitar:
        _git(raiz, "commit", "-q", "-am", "o código anda")


def _rodar(raiz: Path, *, escrever: bool = True) -> tuple[list[str], list[str]]:
    return _script().reapontar(raiz, escrever=escrever)  # type: ignore[no-any-return]


def _validar(raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(RAIZ / "scripts" / "validar-citacoes-de-linha.py"),
            "--all",
            "--root",
            str(raiz),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("commitar", [True, False], ids=["andou-num-commit", "andou-sem-commit"])
def test_o_codigo_anda_e_as_citacoes_vao_junto(repo: Path, commitar: bool) -> None:
    """O caso de toda costura: código inserido acima do que se cita."""
    _inserir_no_topo(repo, 3, commitar=commitar)
    assert _validar(repo).returncode == 1, "a premissa: as citações apodreceram"

    _feitos, a_mao = _rodar(repo)

    assert a_mao == [], a_mao
    assert _validar(repo).returncode == 0, _validar(repo).stdout
    csv = (repo / "docs" / "data" / "mapa.csv").read_text(encoding="utf-8")
    assert "alvo.py:13-15 (`segunda`" in csv and "alvo.py:18 (`terceira`)" in csv, csv
    md = (repo / "docs" / "protocol" / "x.md").read_text(encoding="utf-8")
    assert "alvo.py:18-19`" in md, md
    citante = (repo / "src" / "hefesto_dualsense4unix" / "citante.py").read_text(encoding="utf-8")
    assert "`alvo.py:13-15`" in citante, citante
    assert csv == CSV.replace(":10-12", ":13-15").replace(":15 (", ":18 ("), csv


def test_a_funcao_que_mudou_de_lugar_e_achada_pelo_bloco(repo: Path) -> None:
    """``segunda`` vai para o fim do arquivo: nenhum hunk a leva, o bloco idêntico sim."""
    alvo = repo / "src" / "hefesto_dualsense4unix" / "alvo.py"
    texto = alvo.read_text(encoding="utf-8")
    bloco = "def segunda():\n    x = 2\n    return x\n\n\n"
    alvo.write_text(texto.replace(bloco, "") + "\n\n" + bloco.rstrip("\n") + "\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "segunda muda de lugar")

    feitos, a_mao = _rodar(repo)

    assert _validar(repo).returncode == 0, (feitos, a_mao, _validar(repo).stdout)
    linhas = alvo.read_text(encoding="utf-8").splitlines()
    onde = linhas.index("def segunda():") + 1
    csv = (repo / "docs" / "data" / "mapa.csv").read_text(encoding="utf-8")
    assert f"alvo.py:{onde}-{onde + 2} (`segunda`" in csv, csv


def test_o_que_sumiu_nao_se_chuta(repo: Path) -> None:
    """``segunda`` apagada: não há onde apontar, e o documento não muda."""
    alvo = repo / "src" / "hefesto_dualsense4unix" / "alvo.py"
    alvo.write_text(
        alvo.read_text(encoding="utf-8").replace("def segunda():\n    x = 2\n    return x\n", ""),
        encoding="utf-8",
    )
    _git(repo, "commit", "-q", "-am", "segunda sai")
    antes = (repo / "docs" / "data" / "mapa.csv").read_text(encoding="utf-8")

    plano, _ = _rodar(repo, escrever=False)
    assert not any("alvo.py:10-12" in linha for linha in plano), plano

    _feitos, a_mao = _rodar(repo)

    assert any("segunda" in linha for linha in a_mao), a_mao
    depois = (repo / "docs" / "data" / "mapa.csv").read_text(encoding="utf-8")
    assert "alvo.py:10-12 (`segunda`" in depois, "a citação sem casa foi mexida"
    assert antes.count("\n") == depois.count("\n")


def test_endereco_que_serve_a_duas_promessas_volta_como_estava(repo: Path) -> None:
    """O mesmo endereço, escrito antes e depois de o código andar, com duas promessas."""
    md = repo / "docs" / "protocol" / "x.md"
    md.write_text(
        "# Doc\n\nO `primeira` em `src/hefesto_dualsense4unix/alvo.py:6`.\n", encoding="utf-8"
    )
    _git(repo, "commit", "-q", "-am", "a primeira promessa")
    _inserir_no_topo(repo, 3, commitar=True)
    md.write_text(
        md.read_text(encoding="utf-8")
        + "\nE o `VALOR` em `src/hefesto_dualsense4unix/alvo.py:6`.\n",
        encoding="utf-8",
    )
    _git(repo, "commit", "-q", "-am", "a segunda promessa, no mesmo endereço")
    antes = md.read_text(encoding="utf-8")

    _feitos, a_mao = _rodar(repo)

    assert md.read_text(encoding="utf-8") == antes
    assert any("devolvido como estava" in linha for linha in a_mao), a_mao


def test_a_funcao_inteira_a_deriva_volta_ao_lugar(repo: Path) -> None:
    """A citação de ``segunda`` nasceu uma linha acima: 9-11, e a função é 10-12."""
    csv = repo / "docs" / "data" / "mapa.csv"
    csv.write_text(
        csv.read_text(encoding="utf-8").replace(
            "alvo.py:10-12 (`segunda`", "alvo.py:9-11 (`segunda`"
        ),
        encoding="utf-8",
    )
    _git(repo, "commit", "-q", "-am", "a citação nasce à deriva")
    assert _validar(repo).returncode == 0, "a premissa: o validador não vê a deriva"

    _feitos, a_mao = _rodar(repo)

    assert a_mao == [], a_mao
    assert "alvo.py:10-12 (`segunda`" in csv.read_text(encoding="utf-8")


def test_a_funcao_que_cresceu_e_achada_no_historico(repo: Path) -> None:
    """``segunda`` ganha duas linhas por dentro e uma no topo: 11-15, com 10-12 ainda verde."""
    alvo = repo / "src" / "hefesto_dualsense4unix" / "alvo.py"
    alvo.write_text(
        alvo.read_text(encoding="utf-8").replace(
            "    x = 2\n", "    x = 2\n    y = x\n    x = y\n"
        ),
        encoding="utf-8",
    )
    _git(repo, "commit", "-q", "-am", "segunda cresce")
    _inserir_no_topo(repo, 1, commitar=True)

    _feitos, a_mao = _rodar(repo)

    assert a_mao == [], a_mao
    assert "alvo.py:11-15 (`segunda`" in (repo / "docs" / "data" / "mapa.csv").read_text(
        encoding="utf-8"
    )


def test_o_trecho_de_dentro_da_funcao_nao_e_desta_pergunta(repo: Path) -> None:
    """Citar as duas primeiras linhas de ``segunda`` não é citar a função inteira."""
    csv = repo / "docs" / "data" / "mapa.csv"
    csv.write_text(
        csv.read_text(encoding="utf-8").replace(
            "alvo.py:10-12 (`segunda`", "alvo.py:10-11 (`segunda`"
        ),
        encoding="utf-8",
    )
    _git(repo, "commit", "-q", "-am", "o trecho de dentro")

    feitos, _a_mao = _rodar(repo)

    assert not any("10-11" in linha for linha in feitos), feitos
    assert "alvo.py:10-11 (`segunda`" in csv.read_text(encoding="utf-8")


def test_o_trecho_que_abraca_o_def_de_fora_anda_com_a_funcao(repo: Path) -> None:
    """As duas primeiras linhas de ``segunda`` (10-11), e uma linha nasce em cima dela."""
    csv = repo / "docs" / "data" / "mapa.csv"
    csv.write_text(
        csv.read_text(encoding="utf-8").replace(
            "alvo.py:10-12 (`segunda`", "alvo.py:10-11 (`segunda`"
        ),
        encoding="utf-8",
    )
    _git(repo, "commit", "-q", "-am", "o trecho do começo")
    alvo = repo / "src" / "hefesto_dualsense4unix" / "alvo.py"
    alvo.write_text(
        alvo.read_text(encoding="utf-8").replace("\ndef segunda", "\nOUTRO = 2\ndef segunda"),
        encoding="utf-8",
    )
    _git(repo, "commit", "-q", "-am", "uma linha nasce em cima de segunda")
    assert _validar(repo).returncode == 1, "a premissa: a pergunta 3 do validador vê a deriva"

    _feitos, a_mao = _rodar(repo)

    assert a_mao == [], a_mao
    assert "alvo.py:11-12 (`segunda`" in csv.read_text(encoding="utf-8")
    assert _validar(repo).returncode == 0


MD_CURTA = (
    "# Doc\n\nO `segunda` em `src/hefesto_dualsense4unix/alvo.py:10-12`, "
    "e o `terceira` em `:15-16`.\n"
)


def test_a_forma_curta_da_mesma_linha_anda_junto(repo: Path) -> None:
    """A forma curta ``:N`` herda o arquivo da citação inteira da mesma linha."""
    doc = repo / "docs" / "protocol" / "curta.md"
    doc.write_text(MD_CURTA, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "a forma curta")
    _inserir_no_topo(repo, 3, commitar=True)

    feitos, a_mao = _rodar(repo)

    assert a_mao == [], a_mao
    texto = doc.read_text(encoding="utf-8")
    assert "alvo.py:13-15`" in texto and "`:18-19`" in texto, texto
    assert not any("(0x)" in f for f in feitos), feitos
    assert _validar(repo).returncode == 0, _validar(repo).stdout


def test_o_endereco_que_nao_esta_escrito_vai_para_a_mao(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Troca que não escreveu nada não entra nos feitos."""
    doc = repo / "docs" / "protocol" / "curta.md"
    doc.write_text(MD_CURTA, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "a forma curta")
    _inserir_no_topo(repo, 3, commitar=True)
    modulo = _script()
    monkeypatch.setattr(modulo, "_trocar_curta", lambda texto, _cit, _end: (texto, 0))

    feitos, a_mao = modulo.reapontar(repo, escrever=True)

    assert any("`:15-16`" not in f and "curta.md" in f and "forma curta" in f for f in a_mao), a_mao
    assert not any("curta.md" in f and "15-16" in f for f in feitos), feitos
    assert "`:15-16`" in doc.read_text(encoding="utf-8")


def test_sem_escrever_nada_muda(repo: Path) -> None:
    _inserir_no_topo(repo, 3, commitar=True)
    antes = {p: p.read_bytes() for p in repo.rglob("*") if p.is_file() and ".git" not in p.parts}

    feitos, _a_mao = _rodar(repo, escrever=False)

    assert feitos, "a seco, ele tem de dizer o que faria"
    depois = {p: p.read_bytes() for p in repo.rglob("*") if p.is_file() and ".git" not in p.parts}
    assert antes == depois


def test_o_script_roda_pela_linha_de_comando(repo: Path) -> None:
    _inserir_no_topo(repo, 2, commitar=True)
    feito = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(repo), "--escrever"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert feito.returncode == 0, feito.stdout + feito.stderr
    assert "reapontada(s)" in feito.stdout
    assert _validar(repo).returncode == 0
