"""O portão não roda com o python de outra árvore — e, se rodar, ele GRITA.

O DEFEITO, medido em 04/09/2026 dentro de uma árvore de voo (`hefesto-voo/`):
o cabeçalho do `portoes.sh` imprimia

    python  /mnt/.../hefesto-dualsense4unix-estavel/venv/bin/python

— a venv de OUTRA CÓPIA do repositório, sem ``structlog``, sem ``playwright``,
sem ``ruff`` e sem ``mypy``. Quatro portões saíam VERMELHOS sem que houvesse
nada de errado no código. A causa era uma suposição escrita no próprio script:
``git worktree list | awk NR==1`` devolve a árvore PRINCIPAL do ``.git``, e esta
casa tem três árvores — a principal do git é a ``-estavel``, que não é a de
trabalho. *"A primeira da lista"* nunca foi *"a que tem as dependências"*.

É a família de defeito que esta casa persegue acima de todas — **o instrumento
apontando para outra coisa** —, e ela é pior que um portão vermelho: um portão
que roda com o interpretador errado **não mede**.

POR QUE ESTA RÉGUA PRECISOU DE UMA OPÇÃO NOVA no script (``--interpretador``):
sem ela a única forma de conferir a resolução seria ler o texto do `.sh`, que é
*digitar o que se devia LER* — o defeito que esta casa já pagou onze vezes em
26/08/2026, quando réguas reprovavam a melhora em vez do defeito. A opção torna
a resolução **observável**: o script diz qual python escolheu e sai ``rc=1`` se
faltar coisa nele.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTOES = RAIZ / "scripts" / "portoes.sh"


def _rodar(env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("HEFESTO_PY", None)
    env.update(env_extra or {})
    return subprocess.run(
        ["bash", str(PORTOES), "--interpretador"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def test_a_opcao_existe_e_nao_roda_portao_nenhum() -> None:
    """`--interpretador` responde em milissegundos: ele não roda a leva."""
    r = _rodar()
    assert "portões — árvore" in r.stdout, r.stdout + r.stderr
    assert "python  " in r.stdout, r.stdout
    # Se ele tivesse rodado a leva, a saída traria linhas de portão.
    assert " ok " not in r.stdout, (
        "`--interpretador` rodou portão: ele existe para responder SÓ o "
        "cabeçalho, e uma régua que espera a leva inteira ninguém roda.\n"
        + r.stdout
    )


def test_o_interpretador_escolhido_tem_o_que_os_portoes_precisam() -> None:
    """Nesta árvore, a resolução automática acha uma venv COMPLETA."""
    r = _rodar()
    assert r.returncode == 0, (
        "o `portoes.sh` escolheu um interpretador incompleto nesta árvore — "
        "é o defeito de 04/09/2026 de volta.\n" + r.stdout + r.stderr
    )
    assert "INTERPRETADOR INCOMPLETO" not in r.stdout, r.stdout


def test_o_python_escolhido_importa_o_que_os_portoes_importam() -> None:
    """Não basta o script dizer que está bem: PERGUNTA-SE ao python escolhido.

    Esta é a metade que LÊ em vez de digitar — ela executa o interpretador que
    o cabeçalho nomeou, em vez de confiar na palavra do script.
    """
    r = _rodar()
    linha = next(
        (ln for ln in r.stdout.splitlines() if ln.strip().startswith("python ")),
        None,
    )
    assert linha, "o cabeçalho não declarou o interpretador:\n" + r.stdout
    py = linha.split(maxsplit=1)[1].strip()
    assert Path(py).exists(), f"o python declarado não existe no disco: {py}"

    sonda = subprocess.run(
        [py, "-c", "import structlog, playwright"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert sonda.returncode == 0, (
        f"o interpretador que o portão declarou ({py}) não importa o que os "
        "portões importam — o vermelho que vier dele é do instrumento, não do "
        "código.\n" + sonda.stderr
    )


def test_um_interpretador_capenga_e_acusado_em_vez_de_medir(tmp_path: Path) -> None:
    """A MORDIDA: aponte de propósito para um python sem as dependências.

    Sem a cura, o script aceitava calado e deixava os quatro vermelhos falsos
    explicarem-se sozinhos. Com ela, o cabeçalho nomeia o que falta e o
    `--interpretador` sai `rc=1`.
    """
    falso = tmp_path / "bin"
    falso.mkdir()
    py = falso / "python"
    py.write_text(
        "#!/bin/sh\n"
        '# um python que existe e NÃO tem as dependências dos portões.\n'
        'case "$*" in *structlog*|*playwright*) exit 1 ;; esac\n'
        "exit 0\n",
        encoding="utf-8",
    )
    py.chmod(0o755)

    r = _rodar({"HEFESTO_PY": str(py)})

    assert r.returncode == 1, (
        "o portão aceitou um interpretador sem structlog/playwright/ruff/mypy "
        "sem dizer nada — é o defeito de 04/09/2026, e desta vez pela porta do "
        "`HEFESTO_PY`.\n" + r.stdout + r.stderr
    )
    assert "INTERPRETADOR INCOMPLETO" in r.stdout, r.stdout
    for peca in ("structlog", "ruff", "mypy"):
        assert peca in r.stdout, (
            f"o cabeçalho não NOMEOU o que falta ({peca}) — 'algo está errado' "
            "manda a próxima pessoa procurar de novo.\n" + r.stdout
        )


def _venv_falsa(raiz: Path, nome: str, *, completa: bool) -> Path:
    """Uma venv de mentira, completa ou capenga, no molde que o script procura."""
    d = raiz / nome / "bin"
    d.mkdir(parents=True)
    py = d / "python"
    if completa:
        py.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        for bin_ in ("ruff", "mypy"):
            alvo = d / bin_
            alvo.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            alvo.chmod(0o755)
    else:
        py.write_text(
            "#!/bin/sh\n"
            'case "$*" in *structlog*|*playwright*) exit 1 ;; esac\n'
            "exit 0\n",
            encoding="utf-8",
        )
    py.chmod(0o755)
    return d


def test_uma_venv_capenga_na_frente_nao_ganha_de_uma_completa(tmp_path: Path) -> None:
    """A MORDIDA QUE PEGA O DEFEITO DE VERDADE: a ORDEM não decide sozinha.

    O bug de 04/09 era de ORDEM: o script pegava a primeira venv que
    ENCONTRAVA, e a primeira era a de outra cópia do repositório. Rodar a régua
    na árvore de trabalho não o revela — aqui a primeira candidata JÁ é a certa,
    e por isso a versão anterior desta régua passava com a cura arrancada. Ela
    foi reescrita depois de eu medir exatamente isso.

    Aqui as duas candidatas existem e a PRIMEIRA é a capenga: `.venv` é olhado
    antes de `venv`. Com a regra velha (posição) o script escolhe a capenga;
    com a nova (capacidade) ele pula para a completa.
    """
    raiz = tmp_path / "arvore"
    (raiz / "scripts").mkdir(parents=True)
    # Fora de repositório git: `RAIZ` cai no `dirname dirname $0`, que é o que
    # dá o controle das candidatas sem tocar no `.git` desta casa.
    copia = raiz / "scripts" / "portoes.sh"
    copia.write_text(PORTOES.read_text(encoding="utf-8"), encoding="utf-8")
    copia.chmod(0o755)

    _venv_falsa(raiz, ".venv", completa=False)   # a primeira da fila, capenga
    _venv_falsa(raiz, "venv", completa=True)     # a segunda, completa

    env = dict(os.environ)
    env.pop("HEFESTO_PY", None)
    r = subprocess.run(
        ["bash", str(copia), "--interpretador"],
        cwd=raiz, capture_output=True, text=True, env=env, timeout=60,
    )

    assert r.returncode == 0, (
        "o script parou na PRIMEIRA venv que achou, e ela era a capenga — é a "
        "regra da POSIÇÃO, que foi o defeito de 04/09/2026. A regra é de "
        "CAPACIDADE: pergunta-se à venv se ela tem o que os portões precisam.\n"
        + r.stdout + r.stderr
    )
    assert "INTERPRETADOR INCOMPLETO" not in r.stdout, r.stdout
    assert "/venv/bin/python" in r.stdout and "/.venv/bin/python" not in r.stdout, (
        "o cabeçalho declarou a venv errada:\n" + r.stdout
    )


def test_sem_nenhuma_venv_completa_ele_avisa_em_vez_de_medir(tmp_path: Path) -> None:
    """E quando NÃO há saída boa, o cabeçalho diz — não finge que mediu."""
    raiz = tmp_path / "arvore"
    (raiz / "scripts").mkdir(parents=True)
    copia = raiz / "scripts" / "portoes.sh"
    copia.write_text(PORTOES.read_text(encoding="utf-8"), encoding="utf-8")
    copia.chmod(0o755)
    _venv_falsa(raiz, ".venv", completa=False)

    env = dict(os.environ)
    env.pop("HEFESTO_PY", None)
    r = subprocess.run(
        ["bash", str(copia), "--interpretador"],
        cwd=raiz, capture_output=True, text=True, env=env, timeout=60,
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "INTERPRETADOR INCOMPLETO" in r.stdout, r.stdout


@pytest.mark.parametrize("bandeira", ["--rapido", "--listar"])
def test_as_outras_bandeiras_continuam_valendo(bandeira: str) -> None:
    """A bandeira nova não pode ter comido as antigas."""
    if bandeira == "--listar":
        r = subprocess.run(
            ["bash", str(PORTOES), bandeira],
            cwd=RAIZ, capture_output=True, text=True, timeout=60,
        )
        assert "PORTAO|" in r.stdout, r.stdout
    else:
        # `--rapido` só precisa PARTIR: rodar a leva aqui custaria segundos e
        # duplicaria o que o próprio `portoes.sh` já faz na integração.
        r = subprocess.run(
            ["bash", "-n", str(PORTOES)],
            cwd=RAIZ, capture_output=True, text=True, timeout=60,
        )
        assert r.returncode == 0, "o script não passa nem no `bash -n`:\n" + r.stderr
