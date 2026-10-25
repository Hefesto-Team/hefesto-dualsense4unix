"""O comentário não termina no meio da frase (A-CASA-NAO-DEIXA-PASSAR-COMENTARIO-CORTADO-01).

O commit `8002c142c` deixou só a primeira linha de muitos blocos de comentário, e a primeira
acaba em «…a», «…que», «…e». A régua (`scripts/check_comentario_cortado.py`) conta os blocos que
acabam em conectivo ou em citação `arquivo:linha` sem pontuação, seguidos de código, e o bloco
que o `8002c142c` deixou pela metade sem ponto no fim, seja qual for a última palavra
(A-REGUA-DO-COMENTARIO-CORTADO-VE-O-CORTE-PELO-HISTORICO-01); o piso é por arquivo, contra o
`merge-base` com `dev`: o arquivo que sobe reprova pelo nome.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "check_comentario_cortado.py"

_spec = importlib.util.spec_from_file_location("_cortado", SCRIPT)
assert _spec and _spec.loader
cortado = importlib.util.module_from_spec(_spec)
sys.modules["_cortado"] = cortado
_spec.loader.exec_module(cortado)


def test_o_caso_do_janela_aberta_comum_reprova() -> None:
    texto = (
        "TIQUES_POR_FASE = 40\n\n"
        "#: `TIQUE_MS` do produto (ver `_teto_da_fase_s`). Bater o teto não é pulo: a\n"
        "VEZES_O_NOMINAL = 5\n"
    )
    assert [n for n, _ in cortado.cortados_do_texto(texto)] == [3]


def test_o_bloco_de_varias_linhas_vale_pela_ultima() -> None:
    cortado_no_fim = "# a primeira linha termina em ponto.\n# a segunda acaba no\nx = 1\n"
    inteiro = "# a primeira acaba no\n# meio e a segunda fecha a frase.\nx = 1\n"
    assert [n for n, _ in cortado.cortados_do_texto(cortado_no_fim)] == [2]
    assert cortado.cortados_do_texto(inteiro) == []


def test_a_frase_inteira_e_o_comentario_de_fim_de_arquivo_passam() -> None:
    assert cortado.cortados_do_texto("# a frase fecha aqui.\nx = 1\n") == []
    assert cortado.cortados_do_texto("# lista: um, dois e\n") == [], "fim de arquivo não conta"
    assert cortado.cortados_do_texto("x = 1  # acaba em que\ny = 2\n") == [], (
        "comentário de fim de linha é de outra régua"
    )


def test_o_jogo_velho_dentro_de_string_nao_e_comentario() -> None:
    texto = 'x = """\n# isto é texto, não comentário, e\n"""\ny = 1\n'
    assert cortado.cortados_do_texto(texto) == []


def test_o_bloco_que_acaba_em_citacao_sem_verbo_reprova() -> None:
    """O caso da `aba08` (nota da modos-1-7): o bloco `#:` termina numa citação `arquivo:linha`."""
    texto = (
        "#: A frase já está no `title` / e sem chamador, e a lápide do\n"
        "#: `portao_a_casa_sabe_e_o_produto_nao_faz.py:1188`\n"
        "PENEIRA_QUANDO_ELA_EXISTIR = ()\n"
    )
    assert [n for n, _ in cortado.cortados_do_texto(texto)] == [2]
    fechado = texto.replace("1188`\n", "1188`.\n")
    assert cortado.cortados_do_texto(fechado) == [], "com ponto final a citação é frase inteira"


def test_cada_conectivo_da_lista_corta_a_frase() -> None:
    for palavra in ("a", "o", "de", "que", "e", "para", "com", "em"):
        assert cortado.termina_no_meio(f"# o texto segue {palavra}"), palavra
    assert not cortado.termina_no_meio("# o texto fecha com ponto."), "ponto fecha"
    assert not cortado.termina_no_meio("# o texto fecha em `valor`"), "código fecha"


def test_a_varredura_da_arvore_de_verdade_nao_esta_cega() -> None:
    achados = cortado.varrer(RAIZ, deixadas={})
    assert len(achados) >= 100, (
        f"a varredura achou só {len(achados)}: a régua ficou cega (git ls-files vazio?)"
    )


# --- o piso por arquivo (A-DIVIDA-DA-BASE-DESCE-POR-ARQUIVO-E-POR-QUEM-TOCA-01) -------------

CORTADO = "# a frase acaba no\nx = 1\n"
INTEIRO = "# a frase fecha aqui.\nx = 1\n"


def _git(raiz: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
         "-c", "user.name=t", "-c", "user.email=t@exemplo.invalid", *args],
        cwd=raiz, check=True, capture_output=True,
    )


def _repo(raiz: Path, arquivos: dict[str, str], ramo_base: str = "dev", corte: bool = False,
          ) -> None:
    """Um repositório de mentira com `arquivos` commitados em `ramo_base` e o ramo `ramo` aberto.

    `corte`: a base leva a etiqueta `corte`, que o `corte_de_mentira` faz de commit do corte.
    """
    _git(raiz, "init", "-q", "-b", ramo_base)
    _git(raiz, "commit", "-q", "--allow-empty", "-m", "pai")
    for nome, texto in arquivos.items():
        (raiz / nome).parent.mkdir(parents=True, exist_ok=True)
        (raiz / nome).write_text(texto, encoding="utf-8")
    _git(raiz, "add", ".")
    _git(raiz, "commit", "-q", "-m", "base")
    if corte:
        _git(raiz, "tag", "corte")
    _git(raiz, "checkout", "-q", "-b", "ramo")


def _commitar(raiz: Path, arquivos: dict[str, str]) -> None:
    for nome, texto in arquivos.items():
        (raiz / nome).write_text(texto, encoding="utf-8")
    _git(raiz, "commit", "-q", "-am", "ramo")


@pytest.fixture(autouse=True)
def _git_sem_a_casa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.mark.usefixtures("corte_de_mentira")
def test_o_arquivo_que_sobe_reprova_mesmo_com_outro_descendo(tmp_path: Path) -> None:
    """(a) +1 em `x.py` e -1 em `y.py`: o total não muda (1 - 1 = 0), e `x.py` reprova pelo nome."""
    _repo(tmp_path, {"src/x.py": INTEIRO, "src/y.py": CORTADO}, corte=True)
    _commitar(tmp_path, {"src/x.py": CORTADO, "src/y.py": INTEIRO})
    rc, linhas = cortado.verificar(tmp_path)
    assert rc == 1, linhas
    falhas = [linha for linha in linhas if linha.startswith("FALHA")]
    assert len(falhas) == 1 and "src/x.py: cortado 0 -> 1" in falhas[0], falhas


@pytest.mark.usefixtures("corte_de_mentira")
def test_o_ramo_que_so_desce_passa(tmp_path: Path) -> None:
    """(b) só tira: passa, e não pede para baixar número nenhum."""
    _repo(tmp_path, {"src/x.py": CORTADO, "src/y.py": CORTADO}, corte=True)
    _commitar(tmp_path, {"src/y.py": INTEIRO})
    rc, linhas = cortado.verificar(tmp_path)
    assert rc == 0, linhas
    assert not [linha for linha in linhas if linha.startswith("FALHA")], linhas


@pytest.mark.usefixtures("corte_de_mentira")
def test_o_arquivo_que_nasce_com_cortado_reprova(tmp_path: Path) -> None:
    _repo(tmp_path, {"src/x.py": INTEIRO}, corte=True)
    (tmp_path / "src" / "novo.py").write_text(CORTADO, encoding="utf-8")
    _git(tmp_path, "add", "src/novo.py")
    rc, linhas = cortado.verificar(tmp_path)
    assert rc == 1 and any("src/novo.py: cortado 0 -> 1" in linha for linha in linhas), linhas


@pytest.mark.usefixtures("corte_de_mentira")
def test_o_arquivo_que_muda_de_nome_compara_com_o_nome_antigo(tmp_path: Path) -> None:
    _repo(tmp_path, {"src/x.py": CORTADO + "y = 2\nz = 3\n"}, corte=True)
    _git(tmp_path, "mv", "src/x.py", "src/w.py")
    rc, linhas = cortado.verificar(tmp_path)
    assert rc == 0, linhas


@pytest.mark.usefixtures("corte_de_mentira")
def test_sem_base_a_regua_falha_e_diz(tmp_path: Path) -> None:
    """(c) sem `dev` nem `origin/dev`: FALHA dizendo «sem base», nunca passa calada."""
    _repo(tmp_path, {"src/x.py": INTEIRO}, ramo_base="principal", corte=True)
    rc, linhas = cortado.verificar(tmp_path)
    assert rc == 1, linhas
    assert any("sem base" in linha for linha in linhas), linhas


@pytest.mark.usefixtures("corte_de_mentira")
def test_o_origin_dev_serve_de_base_no_ci(tmp_path: Path) -> None:
    _repo(tmp_path, {"src/x.py": INTEIRO}, ramo_base="principal", corte=True)
    _git(tmp_path, "update-ref", "refs/remotes/origin/dev", "principal")
    _commitar(tmp_path, {"src/x.py": CORTADO})
    rc, linhas = cortado.verificar(tmp_path)
    assert rc == 1 and any("src/x.py: cortado 0 -> 1" in linha for linha in linhas), linhas


def test_o_de_lista_os_candidatos_dos_arquivos_dados(tmp_path: Path) -> None:
    (tmp_path / "x.py").write_text(CORTADO, encoding="utf-8")
    (tmp_path / "y.py").write_text(INTEIRO, encoding="utf-8")
    assert cortado.candidatos_de(["x.py", "y.py"], tmp_path, deixadas={}) == [
        "x.py:1 # a frase acaba no"
    ]
    feito = subprocess.run(
        [sys.executable, str(SCRIPT), "--de", "scripts/check_comentario_cortado.py"],
        cwd=RAIZ, capture_output=True, text=True, check=False,
    )
    if cortado.linhas_que_o_corte_deixou(RAIZ) is None:  # clone raso: o `--de` diz que não vê
        assert feito.returncode == 1 and "sem o histórico" in feito.stderr, feito.stderr
        return
    assert feito.returncode == 0, feito.stdout + feito.stderr
    assert feito.stdout.strip() == "nenhum candidato.", feito.stdout


# --- o corte pelo histórico (A-REGUA-DO-COMENTARIO-CORTADO-VE-O-CORTE-PELO-HISTORICO-01) -----

#: a forma do `hidraw_broker.py:122`: o bloco perdeu a segunda linha e acaba em substantivo
O_QUE_FICOU = "#: STEAM-NO-FISICO-01 (24/09/2026) — os PIDs de DualSense FÍSICO que o broker"
PAI = (
    "VPAD = 0x0DF2\n"
    f"{O_QUE_FICOU}\n"
    "#: aceita como físicos: o comum e o Edge.\n"
    "PHYS = frozenset({VPAD})\n"
    "# uma frase sem ponto que o corte não tocou\n"
    "BUS = 3\n"
)
CORTE = PAI.replace("#: aceita como físicos: o comum e o Edge.\n", "")


def test_o_bloco_que_o_corte_deixou_conta_seja_qual_for_a_ultima_palavra() -> None:
    deixadas = frozenset({O_QUE_FICOU, "# uma linha que ficou."})
    assert cortado.cortados_do_texto(CORTE) == [], "o conectivo sozinho não vê «…o broker»"
    assert [n for n, _ in cortado.cortados_do_texto(CORTE, deixadas)] == [2], (
        "o bloco que o corte deixou e não acaba em ponto conta; o que ele não tocou, não"
    )
    curado = CORTE.replace("o broker\n", "o broker aceita.\n")
    assert cortado.cortados_do_texto(curado, deixadas | {O_QUE_FICOU + " aceita."}) == []
    for fim in (".", "!", "?", "…", ".)", ".»", ".  # (noqa-acento)"):
        assert not cortado.termina_sem_ponto(f"# a frase fecha{fim}"), fim
    for fim in ("", ",", ":", " —", " `valor`", " (ver `x`)", "  # (noqa-acento)"):
        assert cortado.termina_sem_ponto(f"# a frase segue{fim}"), fim
    assert not cortado.termina_sem_ponto("# " + "-" * 60), "régua de traços não é frase"
    assert not cortado.termina_sem_ponto("#!/usr/bin/env python3")


def test_o_diff_do_corte_diz_o_que_ficou_de_cada_bloco() -> None:
    diff = (
        "diff --git a/src/x.py b/src/x.py\n--- a/src/x.py\n+++ b/src/x.py\n@@ -1,10 +1,7 @@\n"
        " x = 1\n"
        " # o fim saiu e\n-# esta linha saiu.\n y = 2\n"
        "-# o começo saiu e\n # o fim ficou.\n z = 3\n"
        "-# o bloco inteiro saiu.\n v = 4\n"
        " # o bloco inteiro ficou\n w = 5\n"
    )
    assert cortado.deixadas_do_diff(diff) == {"src/x.py": {"# o fim saiu e", "# o fim ficou."}}


@pytest.fixture
def corte_de_mentira(monkeypatch: pytest.MonkeyPatch) -> None:
    """O commit do corte do repositório de mentira é a etiqueta `corte`."""
    monkeypatch.setattr(cortado, "COMMIT_DO_CORTE", "corte")


def _repo_com_corte(raiz: Path) -> None:
    """`PAI`, o commit do corte (etiqueta `corte`) e o `dev` nele, com o ramo `ramo` aberto."""
    _git(raiz, "init", "-q", "-b", "dev")
    (raiz / "src").mkdir()
    (raiz / "src" / "x.py").write_text(PAI, encoding="utf-8")
    _git(raiz, "add", ".")
    _git(raiz, "commit", "-q", "-m", "pai")
    _commitar(raiz, {"src/x.py": CORTE})
    _git(raiz, "tag", "corte")
    _git(raiz, "checkout", "-q", "-b", "ramo")


@pytest.mark.usefixtures("corte_de_mentira")
def test_o_corte_pelo_historico_aparece_e_o_arquivo_intocado_nao_reprova(tmp_path: Path) -> None:
    _repo_com_corte(tmp_path)
    assert cortado.candidatos_de(["src/x.py"], tmp_path) == [f"src/x.py:2 {O_QUE_FICOU}"]
    rc, linhas = cortado.verificar(tmp_path)
    assert rc == 0, f"o arquivo que ninguém tocou não reprova pela régua mais larga: {linhas}"
    _commitar(tmp_path, {"src/x.py": CORTE + "OUTRO = 4\n"})
    rc, linhas = cortado.verificar(tmp_path)
    assert rc == 0, f"tocar sem cortar não sobe: a base e o disco leem o mesmo histórico: {linhas}"
    _git(tmp_path, "mv", "src/x.py", "src/w.py")
    assert cortado.candidatos_de(["src/w.py"], tmp_path) == [f"src/w.py:2 {O_QUE_FICOU}"], (
        "o arquivo que mudou de nome depois do corte guarda o que o corte deixou"
    )


@pytest.mark.usefixtures("corte_de_mentira")
def test_sem_o_historico_do_corte_a_regua_falha_e_diz(tmp_path: Path) -> None:
    _repo(tmp_path, {"src/x.py": INTEIRO})
    rc, linhas = cortado.verificar(tmp_path)
    assert rc == 1 and any("sem o histórico" in linha for linha in linhas), linhas
    with pytest.raises(cortado.SemHistorico):
        cortado.candidatos_de(["src/x.py"], tmp_path)
    _git(tmp_path, "tag", "corte", "dev~1")  # a raiz: o corte sem pai
    rc, linhas = cortado.verificar(tmp_path)
    assert rc == 1 and any("sem o histórico" in linha for linha in linhas), (
        f"o corte sem o pai também não se lê: {linhas}"
    )


def test_o_historico_da_arvore_de_verdade_traz_o_corte_do_broker() -> None:
    deixadas = cortado.linhas_que_o_corte_deixou(RAIZ)
    if deixadas is None:  # clone raso (o checkout sem `fetch-depth: 0`): a régua diz, não cala
        with pytest.raises(cortado.SemHistorico):
            cortado.varrer(RAIZ)
        return
    assert sum(map(len, deixadas.values())) >= 2000, "o `8002c142c` cortou 2112 blocos"
    assert O_QUE_FICOU in deixadas["src/hefesto_dualsense4unix/broker/hidraw_broker.py"]
