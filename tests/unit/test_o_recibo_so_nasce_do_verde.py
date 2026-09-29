"""O recibo só nasce do verde, e da árvore que foi medida.

O-PUSH-SO-COM-O-RECIBO-DOS-PORTOES-01, 28/09/2026. A trava do push da máquina
pede ``<git comum>/hefesto-recibos/<árvore>.portoes-completo`` e ``….suite``
para a árvore do commit que sobe, e até aqui nenhum roteiro os escrevia (a
contraprova de 27/09, T1: o push do fecho, com tudo rodado, era recusado).
Quem escreve agora é ``scripts/recibo_da_medida.py``, chamado pelo
``portoes.sh`` na camada completa e pelo ``rodar-a-suite.sh`` na corrida
inteira.

Tudo aqui roda num repositório git de mentira em ``tmp_path``, com a
configuração global e a do sistema desligadas: o diretório comum de verdade
nunca é tocado (``_pasta`` confere).

AS MORDIDAS:

* arranque a comparação da árvore em ``fechar`` e o arquivo acrescentado ao
  índice no meio da corrida passa a deixar recibo — o
  ``test_a_mordida_sem_a_comparacao_da_arvore`` faz isso sozinho, numa cópia;
* tire o ``abrir`` do ``case`` da camada completa do ``portoes.sh`` e o
  ``--rapido`` passa a deixar recibo;
* tire a guarda ``so_esta`` do ``rodar-a-suite.sh`` e uma parte só passa a
  deixar o recibo da suíte inteira;
* tire o ``PULADOS+=`` do ``portoes.sh`` e o portão pytest que pulou teste
  sai do recibo como se tivesse medido tudo.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "recibo_da_medida.py"
PORTOES = RAIZ / "scripts" / "portoes.sh"
SUITE = RAIZ / "scripts" / "rodar-a-suite.sh"

#: A comparação que a mordida arranca. Mora aqui uma vez: quem a reescrever no
#: script sem reescrever aqui vê a mordida recusar a troca, que é o aviso certo.
COMPARACAO_DA_ARVORE = 'agora.arvore != aberta["arvore"]'


def _ambiente() -> dict[str, str]:
    """O ambiente do teste, sem nenhum ``GIT_*`` herdado de um gancho.

    Nem as opções do pytest de quem chama: a suíte e o portão de brinquedo rodam
    um pytest próprio, e um ``PYTEST_ADDOPTS`` de fora mudaria o que eles medem.
    """
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_") and k not in {"PYTEST_ADDOPTS", "SUITE_PYTEST_ARGS"}}
    env.update({
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "teste", "GIT_AUTHOR_EMAIL": "teste@example.com",
        "GIT_COMMITTER_NAME": "teste", "GIT_COMMITTER_EMAIL": "teste@example.com",
        "HEFESTO_PY": sys.executable,
    })
    return env


def _git(repo: Path, *args: str) -> str:
    feito = subprocess.run(["git", *args], cwd=repo, env=_ambiente(), capture_output=True,
                           text=True, check=False)
    assert feito.returncode == 0, f"git {args}: {feito.stderr}"
    return feito.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Um repositório com um commit, o ``.gitignore`` da casa para bytecode, e nada sujo."""
    r = tmp_path / "arvore"
    r.mkdir()
    _git(r, "init", "-q")
    (r / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    (r / "a.txt").write_text("a\n", encoding="utf-8")
    _git(r, "add", "--", ".gitignore", "a.txt")
    _git(r, "commit", "-q", "-m", "base")
    return r


def _pasta(repo: Path) -> Path:
    pasta = repo / ".git" / "hefesto-recibos"
    assert pasta.resolve().is_relative_to(repo.parent.resolve()), pasta
    return pasta


def _recibos(repo: Path) -> set[str]:
    pasta = _pasta(repo)
    return {p.name for p in pasta.iterdir()} if pasta.is_dir() else set()


def _recibo(repo: Path, *args: str, script: Path = SCRIPT) -> subprocess.CompletedProcess[str]:
    corrida = repo.parent / "corrida.json"
    return subprocess.run([sys.executable, str(script), *args, "--corrida", str(corrida),
                           "--raiz", str(repo)],
                          cwd=repo, env=_ambiente(), capture_output=True, text=True, check=False)


def _arvore_do_indice(repo: Path) -> str:
    return _git(repo, "write-tree")


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def _acrescenta(repo: Path, nome: str = "b.txt") -> None:
    (repo / nome).write_text(nome + "\n", encoding="utf-8")
    _git(repo, "add", "--", nome)


# ---------------------------------------------------------------------------
# O script
# ---------------------------------------------------------------------------
def test_o_verde_com_a_arvore_intacta_deixa_o_recibo_com_a_arvore_do_indice(repo: Path) -> None:
    _acrescenta(repo)                      # a árvore do índice não é a do HEAD
    indice = repo / ".git" / "index"
    antes = _md5(indice)                   # antes de qualquer write-tree, inclusive o deste teste

    assert _recibo(repo, "abrir", "portoes-completo").returncode == 0
    fecho = _recibo(repo, "fechar", "portoes-completo", "0", "--contagem", "2 de 2 portões verdes",
                    "--nao-medido", "sprints-fechadas")
    depois = _md5(indice)

    assert fecho.returncode == 0, fecho.stdout + fecho.stderr
    assert depois == antes, (
        "o recibo mexeu no índice de verdade, que é compartilhado entre as sessões "
        "da árvore; as leituras são sobre uma cópia")
    arvore = _arvore_do_indice(repo)
    assert _recibos(repo) == {f"{arvore}.portoes-completo"}
    texto = (_pasta(repo) / f"{arvore}.portoes-completo").read_text(encoding="utf-8")
    assert f"arvore: {arvore}" in texto
    assert f"head: {_git(repo, 'rev-parse', 'HEAD')}" in texto
    assert "contagem: 2 de 2 portões verdes" in texto
    assert "nao_medidos: sprints-fechadas" in texto, (
        "o recibo escondeu o não medido — ele diz o que não foi medido, sempre:\n" + texto)
    assert re.search(r"^data: \d{4}-\d{2}-\d{2}T", texto, re.M), texto


@pytest.mark.parametrize("rc", ["1", "2", "130"])
def test_a_medida_que_nao_passou_nao_deixa_recibo(repo: Path, rc: str) -> None:
    _recibo(repo, "abrir", "suite")
    fecho = _recibo(repo, "fechar", "suite", rc)
    assert fecho.returncode != 0
    assert _recibos(repo) == set(), f"rc={rc} deixou recibo"


def test_o_arquivo_acrescentado_ao_indice_no_meio_nao_deixa_recibo(repo: Path) -> None:
    """O que foi medido não é o que subiria: a árvore mudou entre abrir e fechar.

    O arquivo nasce DEPOIS do ``abrir``: se existisse antes, a regra do arquivo
    fora do git o pegaria, e a comparação da árvore ficaria sem prova.
    """
    _recibo(repo, "abrir", "portoes-completo")
    _acrescenta(repo)
    fecho = _recibo(repo, "fechar", "portoes-completo", "0")

    assert _recibos(repo) == set(), "a árvore mudou no meio e o recibo nasceu mesmo assim"
    assert "árvore do índice mudou" in fecho.stdout, fecho.stdout


@pytest.mark.parametrize("quando", ["antes de abrir", "depois de abrir"])
def test_a_mudanca_rastreada_fora_do_indice_nao_deixa_recibo(repo: Path, quando: str) -> None:
    if quando == "antes de abrir":
        (repo / "a.txt").write_text("mudou\n", encoding="utf-8")
    _recibo(repo, "abrir", "suite")
    if quando == "depois de abrir":
        (repo / "a.txt").write_text("mudou\n", encoding="utf-8")
    fecho = _recibo(repo, "fechar", "suite", "0")

    assert _recibos(repo) == set(), f"mudança fora do índice {quando} deixou recibo"
    assert "a.txt" in fecho.stdout, "a recusa não nomeou o arquivo mudado:\n" + fecho.stdout


def test_a_mudanca_de_antes_da_abertura_desfeita_no_meio_nao_deixa_recibo(repo: Path) -> None:
    """Os primeiros portões mediram o arquivo mudado; no fecho ele já voltou ao do índice.

    O fecho sozinho vê a árvore limpa e a mesma árvore do começo: só a
    abertura sabe que a medida começou sobre outro conteúdo.
    """
    original = (repo / "a.txt").read_text(encoding="utf-8")
    (repo / "a.txt").write_text("mudou\n", encoding="utf-8")
    _recibo(repo, "abrir", "suite")
    (repo / "a.txt").write_text(original, encoding="utf-8")
    fecho = _recibo(repo, "fechar", "suite", "0")

    assert _recibos(repo) == set(), "a medida começou sobre um arquivo mudado e deixou recibo"
    assert "no começo" in fecho.stdout and "a.txt" in fecho.stdout, fecho.stdout


def test_a_corrida_aberta_numa_arvore_nao_fecha_em_outra(repo: Path, tmp_path: Path) -> None:
    """Outra árvore com o MESMO conteúdo: o que foi medido não foi ela."""
    outra = tmp_path / "outra"
    _git(tmp_path, "clone", "-q", str(repo), str(outra))
    assert _arvore_do_indice(outra) == _arvore_do_indice(repo)
    _recibo(repo, "abrir", "portoes-completo")
    corrida = repo.parent / "corrida.json"
    fecho = subprocess.run([sys.executable, str(SCRIPT), "fechar", "portoes-completo", "0",
                            "--corrida", str(corrida), "--raiz", str(outra)],
                           cwd=outra, env=_ambiente(), capture_output=True, text=True, check=False)

    assert fecho.returncode != 0, fecho.stdout
    assert _recibos(repo) == set() and _recibos(outra) == set(), fecho.stdout


def test_o_arquivo_ignorado_nao_impede_o_recibo(repo: Path) -> None:
    """O ``docs/process`` e os outros ignorados estão em toda árvore de integração."""
    (repo / "__pycache__").mkdir()
    (repo / "__pycache__" / "x.pyc").write_bytes(b"\0")
    arvore = _arvore_do_indice(repo)
    abertura = _recibo(repo, "abrir", "portoes-completo")
    assert "não vai deixar recibo" not in abertura.stdout, abertura.stdout
    assert _recibo(repo, "fechar", "portoes-completo", "0").returncode == 0
    assert _recibos(repo) == {f"{arvore}.portoes-completo"}


def test_o_arquivo_fora_do_git_no_comeco_impede_o_recibo(repo: Path) -> None:
    """A medida lê o disco: o arquivo esquecido fora do ``git add`` entra nela e não na árvore."""
    (repo / "tests_novos.py").write_text("x = 1\n", encoding="utf-8")
    abertura = _recibo(repo, "abrir", "portoes-completo")
    assert "tests_novos.py" in abertura.stdout, (
        "quem roda só sabe no fim que a corrida não serve:\n" + abertura.stdout)
    _recibo(repo, "fechar", "portoes-completo", "0")
    assert _recibos(repo) == set()


def test_a_sobra_que_aparece_durante_a_corrida_sai_nomeada_sem_impedir(repo: Path) -> None:
    arvore = _arvore_do_indice(repo)
    _recibo(repo, "abrir", "suite")
    (repo / "sobra.log").write_text("x\n", encoding="utf-8")
    assert _recibo(repo, "fechar", "suite", "0").returncode == 0
    texto = (_pasta(repo) / f"{arvore}.suite").read_text(encoding="utf-8")
    assert "apareceu_fora_do_git: sobra.log" in texto, texto


def test_o_commit_depois_do_recibo_tem_a_arvore_do_nome(repo: Path) -> None:
    """O fecho da casa: portões depois do ``git add``, o commit depois, e o push lê ``^{tree}``."""
    _acrescenta(repo)
    _recibo(repo, "abrir", "portoes-completo")
    _recibo(repo, "fechar", "portoes-completo", "0")
    _git(repo, "commit", "-q", "-m", "a leva")

    (nome,) = _recibos(repo)
    assert nome == f"{_git(repo, 'rev-parse', 'HEAD^{tree}')}.portoes-completo"


def test_sem_abertura_desta_corrida_nao_ha_recibo(repo: Path, tmp_path: Path) -> None:
    assert _recibo(repo, "fechar", "suite", "0").returncode != 0      # nunca abriu
    _recibo(repo, "abrir", "portoes-completo")
    assert _recibo(repo, "fechar", "suite", "0").returncode != 0      # abriu outro nome
    # a abertura que falha apaga a velha: a corrida seguinte não herda a anterior
    fora = tmp_path / "fora-do-git"
    fora.mkdir()
    corrida = repo.parent / "corrida.json"
    subprocess.run([sys.executable, str(SCRIPT), "abrir", "suite", "--corrida", str(corrida),
                    "--raiz", str(fora)], cwd=fora,
                   env={**_ambiente(), "GIT_CEILING_DIRECTORIES": str(tmp_path)},
                   capture_output=True, text=True, check=False)
    assert not corrida.exists()
    assert _recibos(repo) == set()


def test_o_nome_nao_sai_da_pasta(repo: Path) -> None:
    assert _recibo(repo, "abrir", "../fora").returncode == 2
    assert not (repo.parent / "corrida.json").exists()


def test_a_mordida_sem_a_comparacao_da_arvore(repo: Path, tmp_path: Path) -> None:
    """Arrancada a comparação, o caso do arquivo acrescentado no meio deixa recibo."""
    texto = SCRIPT.read_text(encoding="utf-8")
    assert texto.count(COMPARACAO_DA_ARVORE) == 1, (
        "a comparação da árvore mudou de forma e a mordida não a acha mais — "
        "atualize COMPARACAO_DA_ARVORE, senão esta régua mede outra coisa")
    mutante = tmp_path / "recibo_mutante.py"
    mutante.write_text(texto.replace(COMPARACAO_DA_ARVORE, "False"), encoding="utf-8")

    _recibo(repo, "abrir", "portoes-completo", script=mutante)
    _acrescenta(repo)
    _recibo(repo, "fechar", "portoes-completo", "0", script=mutante)

    assert _recibos(repo), (
        "sem a comparação da árvore o recibo continuou sem nascer: outra regra "
        "está segurando o caso, e o teste do arquivo acrescentado não prova a comparação")


# ---------------------------------------------------------------------------
# Os chamadores, pelo texto
# ---------------------------------------------------------------------------
def _blocos_case(texto: str) -> list[str]:
    return re.findall(r'case " \$CAMADAS " in\n(.*?)\nesac', texto, re.S)


def test_o_portoes_sh_abre_so_no_ramo_da_camada_completa() -> None:
    texto = PORTOES.read_text(encoding="utf-8")
    assert texto.count("recibo_da_medida.py\" abrir portoes-completo") == 1
    assert texto.count("recibo_da_medida.py\" fechar portoes-completo") == 1
    (bloco,) = [b for b in _blocos_case(texto) if "abrir portoes-completo" in b]
    ramo = bloco.split("abrir portoes-completo")[0].strip().splitlines()
    padroes = [ln.strip() for ln in ramo if re.match(r"\s*\*.*\)\s*$", ln)]
    assert padroes and padroes[-1] == '*" completo "*)', (
        "o `abrir` saiu do ramo da camada completa: o `--rapido` passaria a deixar recibo")
    assert re.search(r'--rapido\)\s+CAMADAS="rapido"', texto)


def test_o_portoes_sh_fecha_com_o_rc_do_veredito() -> None:
    """Os dois fins do veredito passam por ``_sair``, que é quem fecha o recibo."""
    texto = PORTOES.read_text(encoding="utf-8")
    fim = texto[texto.index("done < <(_LISTA)"):]
    assert re.findall(r"^\s*_sair (\d)\s*$", fim, re.M) == ["0", "1"], fim
    assert not re.search(r"^\s*exit [01]\s*$", fim, re.M), (
        "um `exit` do veredito não passa por `_sair` e não fecha o recibo")
    sair = texto[texto.index("_sair() {"):texto.index("\n}\n", texto.index("_sair() {"))]
    assert "fechar portoes-completo \"$rc\"" in sair


def test_o_rodar_a_suite_abre_so_na_corrida_inteira() -> None:
    texto = SUITE.read_text(encoding="utf-8")
    assert texto.count("recibo_da_medida.py\" abrir suite") == 1
    guarda = texto[:texto.index("abrir suite")].rsplit("\nif ", 1)[1].splitlines()[0]
    assert '[ -z "$so_esta" ]' in guarda, (
        "o `abrir` da suíte perdeu a guarda da parte única:\n" + guarda)
    assert "${#extra[@]} -eq 0" in guarda, (
        "o `abrir` da suíte perdeu a guarda dos argumentos a mais:\n" + guarda)


# ---------------------------------------------------------------------------
# Os chamadores, rodando: o script DE VERDADE, só com os dados trocados
# ---------------------------------------------------------------------------
def _casa_com_portoes(repo: Path, tabela: str) -> None:
    texto = PORTOES.read_text(encoding="utf-8")
    abre = texto.index("_LISTA() {")
    corpo = texto.index("TABELA\n}", abre)
    (repo / "scripts").mkdir(exist_ok=True)
    alvo = repo / "scripts" / "portoes.sh"
    alvo.write_text(texto[:abre] + "_LISTA() {\n  cat <<'TABELA'\n" + tabela + texto[corpo:],
                    encoding="utf-8")
    (repo / "scripts" / "recibo_da_medida.py").write_text(SCRIPT.read_text(encoding="utf-8"),
                                                          encoding="utf-8")
    for nome, rc, primeira in (("verde", 0, "medi"), ("vermelho", 1, "reprovei"),
                               ("sem-dado", 0, "NÃO MEDIDO: sem o dado")):
        (repo / "scripts" / f"{nome}.sh").write_text(
            f"#!/usr/bin/env bash\necho '{primeira}'\nexit {rc}\n", encoding="utf-8")
    _git(repo, "add", "--", "scripts")


def _portoes(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", "scripts/portoes.sh", *args], cwd=repo, env=_ambiente(),
                          capture_output=True, text=True, check=False, timeout=120)


def test_o_portoes_de_verdade_deixa_recibo_so_na_camada_completa(repo: Path) -> None:
    _casa_com_portoes(repo, "rapido|r|bash|scripts/verde.sh\ncompleto|c|bash|scripts/verde.sh\n")
    arvore = _arvore_do_indice(repo)

    rapido = _portoes(repo, "--rapido")
    assert rapido.returncode == 0, rapido.stdout + rapido.stderr
    assert _recibos(repo) == set(), "o `--rapido` deixou recibo:\n" + rapido.stdout

    completo = _portoes(repo)
    assert completo.returncode == 0, completo.stdout + completo.stderr
    assert _recibos(repo) == {f"{arvore}.portoes-completo"}, completo.stdout
    texto = (_pasta(repo) / f"{arvore}.portoes-completo").read_text(encoding="utf-8")
    assert "contagem: 2 de 2 portões verdes" in texto and "nao_medidos: nenhum" in texto, texto


def test_o_portoes_vermelho_nao_deixa_recibo_e_o_rc_e_o_dele(repo: Path) -> None:
    _casa_com_portoes(repo, "rapido|r|bash|scripts/verde.sh\ncompleto|c|bash|scripts/vermelho.sh\n")
    feito = _portoes(repo)
    assert feito.returncode == 1, feito.stdout
    assert _recibos(repo) == set(), feito.stdout


def test_o_portoes_com_nao_medido_deixa_recibo_que_o_nomeia(repo: Path) -> None:
    _casa_com_portoes(repo, "completo|c|bash|scripts/verde.sh\n"
                            "completo|sd|bash|scripts/sem-dado.sh\n")
    arvore = _arvore_do_indice(repo)
    feito = _portoes(repo)
    assert feito.returncode == 0, feito.stdout
    texto = (_pasta(repo) / f"{arvore}.portoes-completo").read_text(encoding="utf-8")
    assert "nao_medidos: sd" in texto and "contagem: 1 de 2 portões verdes" in texto, texto


def test_o_portao_pytest_que_pulou_teste_sai_nomeado_no_recibo(repo: Path) -> None:
    """Pulo não é verde: o pytest devolve 0 com teste pulado, e o portão sai `ok`.

    O recibo da suíte já nomeia os pulados dela; o dos portões nomeia os de
    cada portão de runner ``pytest``, pelo mesmo motivo (sem tela, os testes
    de tela pulam calados).
    """
    _casa_com_portoes(repo, "completo|c|bash|scripts/verde.sh\n"
                            "completo|pt|pytest|tests/unit/test_pula.py\n")
    (repo / "tests" / "unit").mkdir(parents=True)
    (repo / "tests" / "unit" / "test_pula.py").write_text(_PASSA + "\n\n" + _PULA,
                                                         encoding="utf-8")
    _git(repo, "add", "--", "tests")
    arvore = _arvore_do_indice(repo)
    feito = _portoes(repo)

    assert feito.returncode == 0, feito.stdout + feito.stderr
    assert "1 teste(s) pulado(s)" in feito.stdout, feito.stdout
    texto = (_pasta(repo) / f"{arvore}.portoes-completo").read_text(encoding="utf-8")
    assert "nao_medidos: pt: 1 teste(s) pulado(s)" in texto, (
        "o portão pytest pulou teste e o recibo o escondeu:\n" + texto)
    assert "contagem: 2 de 2 portões verdes" in texto, texto


def _casa_com_suite(repo: Path, testes: dict[str, str]) -> None:
    (repo / "scripts").mkdir(exist_ok=True)
    (repo / "scripts" / "rodar-a-suite.sh").write_text(SUITE.read_text(encoding="utf-8"),
                                                        encoding="utf-8")
    (repo / "scripts" / "recibo_da_medida.py").write_text(SCRIPT.read_text(encoding="utf-8"),
                                                          encoding="utf-8")
    (repo / "tests" / "unit").mkdir(parents=True)
    for nome, corpo in testes.items():
        (repo / "tests" / "unit" / nome).write_text(corpo, encoding="utf-8")
    _git(repo, "add", "--", "scripts", "tests")


def _suite(repo: Path, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
    """A suíte de brinquedo, com a saída FORA da árvore (dentro, ela seria arquivo fora do git)."""
    ambiente = _ambiente()
    ambiente.pop("SUITE_PYTEST_ARGS", None)
    ambiente.update({"PY": sys.executable, "PARTES": "1",
                     "SAIDA": tempfile.mkdtemp(prefix="saida-", dir=repo.parent), **env})
    return subprocess.run(["bash", "scripts/rodar-a-suite.sh", *args], cwd=repo, env=ambiente,
                          capture_output=True, text=True, check=False, timeout=300)


_PASSA = "def test_passa():\n    assert True\n"
_PULA = "import pytest\n\n\ndef test_pula():\n    pytest.skip('sem o dado')\n"
_REPROVA = "def test_reprova():\n    assert False\n"


def test_a_suite_de_verdade_deixa_recibo_so_na_corrida_inteira(repo: Path) -> None:
    _casa_com_suite(repo, {"test_um.py": _PASSA, "test_dois.py": _PULA})
    arvore = _arvore_do_indice(repo)

    parte = _suite(repo, "00")
    assert parte.returncode == 0, parte.stdout + parte.stderr
    assert _recibos(repo) == set(), "uma parte só deixou o recibo da suíte:\n" + parte.stdout

    com_args = _suite(repo, SUITE_PYTEST_ARGS="-k passa")
    assert com_args.returncode == 0, com_args.stdout
    assert _recibos(repo) == set(), "a suíte encolhida por argumento deixou recibo"

    inteira = _suite(repo)
    assert inteira.returncode == 0, inteira.stdout + inteira.stderr
    assert _recibos(repo) == {f"{arvore}.suite"}, inteira.stdout
    texto = (_pasta(repo) / f"{arvore}.suite").read_text(encoding="utf-8")
    assert "1 testes passaram; 1 pulados" in texto, texto
    assert "nao_medidos: testes pulados: 1" in texto, (
        "pulo não é verde, e o recibo o escondeu:\n" + texto)


def test_a_suite_com_vermelho_nao_deixa_recibo(repo: Path) -> None:
    _casa_com_suite(repo, {"test_um.py": _PASSA, "test_tres.py": _REPROVA})
    feito = _suite(repo)
    assert feito.returncode == 1, feito.stdout
    assert _recibos(repo) == set(), feito.stdout
