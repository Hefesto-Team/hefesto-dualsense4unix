"""O PORTÃO DO PORTÃO — a lista de portões desta casa é UMA SÓ.

O DEFEITO, e ele é medido (INFRA-DE-EXECUCAO-01, M9): até 25/08/2026 a lista de
portões vivia em DOIS lugares -- o bloco "Antes de fechar qualquer leva" do
``CLAUDE.md`` e os jobs de ``.github/workflows/ci.yml``. Duas listas para a
mesma coisa é o defeito que a regra do fato-errado existe para matar, e ele
COBROU: o ``validar-caducos.py`` **roda no CI e não estava no bloco local**, e
foi assim que um literal caduco atravessou uma leva inteira e só apareceu no
vermelho do CI, depois de tudo commitado.

A CURA É DE POSIÇÃO, NÃO DE CONTEÚDO: a lista passou a morar em
``scripts/portoes.sh``, versionada -- o ``CLAUDE.md`` não pode ser a fonte
porque ele **não é versionado** (``.gitignore``:90) e um worktree de agente
nasce sem ele. E este teste é o que impede a divergência de voltar: ele lê os
dois lados e reprova nomeando o script que ficou de fora, em qualquer das duas
direções.

TODA DIFERENÇA LEGÍTIMA TEM DE ESTAR DECLARADA, com o motivo, nas linhas
``FORA-DO-LOCAL`` / ``FORA-DO-CI`` do próprio ``portoes.sh``. Diferença
declarada é decisão; diferença calada é a M9 de novo. É por isso que o teste
não tem lista embutida: uma terceira lista dentro do teste seria o mesmo defeito
com roupa nova.

A MORDIDA (arranque a cura, veja reprovar, devolva):
  - tire a linha ``caducos`` da tabela de ``portoes.sh``: o teste reprova
    nomeando ``scripts/validar-caducos.py`` como rodando no CI e ausente do
    bloco local -- que é, literalmente, o defeito de 24/08 reproduzido;
  - acrescente um passo ``run: python3 scripts/inventado.py`` ao ``ci.yml``: o
    teste reprova nomeando ``scripts/inventado.py``.
  Os dois lados são exercitados por dublê em ``test_a_regua_sabe_recusar_*``,
  porque régua que só sabe passar não é régua (armadilha A2 desta casa).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PORTOES_SH = RAIZ / "scripts" / "portoes.sh"
CI_YML = RAIZ / ".github" / "workflows" / "ci.yml"

# As ferramentas que valem como portão mesmo sem serem um caminho em `scripts/`.
# Não é uma lista de portões -- é o alfabeto que o extrator reconhece dos DOIS
# lados. Acrescentar um nome aqui não declara portão nenhum: só faz o extrator
# enxergá-lo, e a comparação continua sendo entre os dois arquivos.
_FERRAMENTAS = ("ruff", "mypy", "shellcheck", "pytest", "pre-commit")

_RE_SCRIPT = re.compile(r"scripts/[A-Za-z0-9_./-]+\.(?:py|sh)")


def _sem_comentario(linha: str) -> str:
    """Corta o comentário de shell/YAML, preservando `#` colado (cor, âncora)."""
    if linha.lstrip().startswith("#"):
        return ""
    return re.sub(r"\s#.*$", "", linha)


def _fichas(texto: str) -> set[str]:
    """As fichas de portão de um pedaço de linha de comando."""
    achadas = set(_RE_SCRIPT.findall(texto))
    for ferramenta in _FERRAMENTAS:
        if re.search(rf"(?<![\w-]){re.escape(ferramenta)}(?![\w-])", texto):
            achadas.add(ferramenta)
    return achadas


def fichas_do_ci(texto_ci: str) -> set[str]:
    """O que o CI de fato RODA -- só o conteúdo dos blocos ``run:``.

    Ler o arquivo inteiro contaria comentário e `uses:` como portão: o
    ``ci.yml`` cita ``scripts/build_appimage_gui.sh`` e
    ``scripts/install_fonts.sh`` em comentário, e nenhum dos dois é rodado por
    ele. Portão que acusa quem está certo ensina a próxima pessoa a não
    acreditar nele.
    """
    fichas: set[str] = set()
    linhas = texto_ci.splitlines()
    i = 0
    while i < len(linhas):
        bruta = linhas[i]
        m = re.match(r"^(\s*)(?:-\s*)?run:\s*(.*)$", bruta)
        if not m:
            i += 1
            continue
        recuo = len(m.group(1))
        resto = m.group(2).strip()
        if resto in {"|", ">", "|-", ">-", "|+", ">+"} or resto == "":
            i += 1
            while i < len(linhas):
                corpo = linhas[i]
                if corpo.strip() and (len(corpo) - len(corpo.lstrip())) <= recuo:
                    break
                fichas |= _fichas(_sem_comentario(corpo))
                i += 1
        else:
            fichas |= _fichas(_sem_comentario(resto))
            i += 1
    return fichas


def _linhas_declaradas(texto_sh: str) -> list[str]:
    """A tabela crua de ``portoes.sh --listar``, sem rodar o script.

    Ler o arquivo em vez de executá-lo é de propósito: o teste tem de valer
    também dentro de um dublê, onde não há árvore de git nem venv para o script
    resolver.
    """
    saida: list[str] = []
    dentro = None
    for linha in texto_sh.splitlines():
        if re.match(r"^\s*cat <<'TABELA'\s*$", linha):
            dentro = "PORTAO"
            continue
        if re.match(r"^\s*cat <<'DIV'\s*$", linha):
            dentro = "DIV"
            continue
        if linha.strip() in {"TABELA", "DIV"}:
            dentro = None
            continue
        if dentro == "PORTAO" and linha.strip():
            saida.append("PORTAO|" + linha.strip())
        elif dentro == "DIV" and linha.strip():
            saida.append(linha.strip())
    return saida


def fichas_locais(texto_sh: str) -> tuple[set[str], set[str], set[str]]:
    """(o que o bloco local roda, o declarado fora do CI, o declarado fora do local)."""
    rodam: set[str] = set()
    fora_do_ci: set[str] = set()
    fora_do_local: set[str] = set()
    for linha in _linhas_declaradas(texto_sh):
        campos = linha.split("|")
        if campos[0] == "PORTAO" and len(campos) >= 5:
            rodam |= _fichas(campos[4])
        elif campos[0] == "FORA-DO-CI" and len(campos) >= 3:
            assert campos[2].strip(), f"FORA-DO-CI sem motivo escrito: {campos[1]}"
            fora_do_ci.add(campos[1])
        elif campos[0] == "FORA-DO-LOCAL" and len(campos) >= 3:
            assert campos[2].strip(), f"FORA-DO-LOCAL sem motivo escrito: {campos[1]}"
            fora_do_local.add(campos[1])
    return rodam, fora_do_ci, fora_do_local


def confere(texto_sh: str, texto_ci: str) -> list[str]:
    """As queixas. Lista vazia significa uma lista só."""
    locais, fora_do_ci, fora_do_local = fichas_locais(texto_sh)
    do_ci = fichas_do_ci(texto_ci)

    queixas: list[str] = []
    for ficha in sorted(do_ci - locais - fora_do_local):
        queixas.append(
            f"{ficha}: RODA NO CI e NÃO está no bloco local de portoes.sh. "
            "Ou entra na tabela, ou vira uma linha FORA-DO-LOCAL com o motivo. "
            "Foi assim que o validar-caducos.py atravessou uma leva inteira."
        )
    for ficha in sorted(locais - do_ci - fora_do_ci):
        queixas.append(
            f"{ficha}: está no bloco local de portoes.sh e NÃO roda no CI. "
            "Ou entra num job, ou vira uma linha FORA-DO-CI com o motivo."
        )
    for ficha in sorted(fora_do_local & locais):
        queixas.append(
            f"{ficha}: declarado FORA-DO-LOCAL e mesmo assim presente na tabela. "
            "A declaração e a tabela se contradizem."
        )
    return queixas


# ---------------------------------------------------------------------------
# A régua contra a árvore de verdade
# ---------------------------------------------------------------------------


def test_a_lista_local_e_a_do_ci_sao_a_mesma() -> None:
    queixas = confere(
        PORTOES_SH.read_text(encoding="utf-8"), CI_YML.read_text(encoding="utf-8")
    )
    assert not queixas, (
        f"A lista de portões divergiu em {len(queixas)} ficha(s):\n"
        + "\n".join("  - " + q for q in queixas)
    )


def test_todo_portao_declarado_existe_no_disco() -> None:
    """Portão declarado e ausente é portão cego, e portão cego é pior que nenhum."""
    locais, _, _ = fichas_locais(PORTOES_SH.read_text(encoding="utf-8"))
    ausentes = [
        f for f in sorted(locais) if f.startswith("scripts/") and not (RAIZ / f).exists()
    ]
    assert not ausentes, "portões declarados em portoes.sh e ausentes da árvore: " + ", ".join(
        ausentes
    )


def test_listar_imprime_a_mesma_tabela_que_o_script_roda() -> None:
    """`--listar` é a superfície que este teste lê; se ela mentir, o teste mente.

    Roda o script de verdade e compara com a leitura estática. É a régua da
    régua: o dia em que `--listar` filtrar alguma coisa que a corrida executa,
    este teste é quem avisa.
    """
    saida = subprocess.run(
        ["bash", str(PORTOES_SH), "--listar"],
        check=True,
        capture_output=True,
        text=True,
        cwd=RAIZ,
    ).stdout.splitlines()
    assert [linha for linha in saida if linha.strip()] == _linhas_declaradas(
        PORTOES_SH.read_text(encoding="utf-8")
    )


# ---------------------------------------------------------------------------
# A régua sabe RECUSAR — os dois lados, com dublê (armadilha A2)
# ---------------------------------------------------------------------------

_SH_DUBLE = """#!/usr/bin/env bash
_LISTA() {
  cat <<'TABELA'
{tabela}
TABELA
}
_DIVERGENCIAS() {
  cat <<'DIV'
{div}
DIV
}
"""

_CI_DUBLE = """jobs:
  falso:
    steps:
{passos}
"""


def _duble(tabela: list[str], div: list[str], passos: list[str]) -> tuple[str, str]:
    sh = _SH_DUBLE.replace("{tabela}", "\n".join(tabela)).replace("{div}", "\n".join(div))
    ci = _CI_DUBLE.replace("{passos}", "\n".join(f"      - run: {p}" for p in passos))
    return sh, ci


def test_a_regua_sabe_passar_quando_as_duas_listas_batem() -> None:
    sh, ci = _duble(
        ["rapido|um|py|scripts/validar-um.py --all"],
        [],
        ["python3 scripts/validar-um.py --all"],
    )
    assert confere(sh, ci) == []


def test_a_regua_sabe_recusar_o_portao_que_so_roda_no_ci() -> None:
    """O caso literal de 24/08: o validar-caducos.py só existia num dos lados."""
    sh, ci = _duble(
        ["rapido|um|py|scripts/validar-um.py --all"],
        [],
        ["python3 scripts/validar-um.py --all", "python3 scripts/validar-caducos.py --all"],
    )
    queixas = confere(sh, ci)
    assert len(queixas) == 1
    assert "scripts/validar-caducos.py" in queixas[0]
    assert "RODA NO CI" in queixas[0]


def test_a_regua_sabe_recusar_o_portao_que_so_roda_no_bloco_local() -> None:
    sh, ci = _duble(
        ["rapido|um|py|scripts/validar-um.py --all", "rapido|dois|bash|scripts/check_dois.sh"],
        [],
        ["python3 scripts/validar-um.py --all"],
    )
    queixas = confere(sh, ci)
    assert len(queixas) == 1
    assert "scripts/check_dois.sh" in queixas[0]
    assert "NÃO roda no CI" in queixas[0]


def test_a_diferenca_declarada_com_motivo_passa() -> None:
    sh, ci = _duble(
        ["rapido|um|py|scripts/validar-um.py --all"],
        ["FORA-DO-LOCAL|scripts/so_no_runner.sh|mexe no sistema vivo da máquina dela"],
        ["python3 scripts/validar-um.py --all", "bash scripts/so_no_runner.sh"],
    )
    assert confere(sh, ci) == []


def test_o_comentario_do_ci_nao_conta_como_portao() -> None:
    """O ci.yml cita scripts em comentário; contá-los acusaria quem está certo."""
    ci = (
        "jobs:\n  x:\n    steps:\n"
        "      # veja scripts/build_appimage_gui.sh\n"
        "      - run: bash scripts/check_um.sh\n"
    )
    sh, _ = _duble(["rapido|um|bash|scripts/check_um.sh"], [], [])
    assert confere(sh, ci) == []


def test_a_ferramenta_conta_dos_dois_lados() -> None:
    sh, ci = _duble(["rapido|ruff|bin|ruff check src/ tests/"], [], ["ruff check src/ tests/"])
    assert confere(sh, ci) == []
    sh_sem, ci_com = _duble([], [], ["mypy src/hefesto_dualsense4unix"])
    queixas = confere(sh_sem, ci_com)
    assert len(queixas) == 1 and queixas[0].startswith("mypy:")
