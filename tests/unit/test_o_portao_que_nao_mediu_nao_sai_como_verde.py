"""RC=0 NÃO É «MEDIU» — a régua do terceiro estado do `portoes.sh`.

O DEFEITO, medido em 20/09/2026 e não suposto. O portão `sprints-fechadas`
nasceu naquele dia lendo `docs/process/sprints/`, que é `.gitignore:178` e
**não viaja pelo git** — então todo worktree de agente nasce sem ela, e um
clone limpo também. Para não mentir, o portão passou a imprimir *"NÃO MEDIDO:
não há docs/process/sprints/ nesta árvore"* e devolver 0.

Só que o `portoes.sh` **engolia a saída de quem devolve 0**. Rodado numa
árvore sem a pasta, o relatório inteiro dizia::

    sprints-fechadas       ok          39 ms
    ...
    TODOS VERDES — 44 portões.

A frase honesta existia no script e **não chegava a ninguém** — verde sobre 46
sprints que o portão não abriu. É a cicatriz que o próprio `portoes.sh` já
carrega escrita duas vezes (o interpretador e o `PYTHONPATH`): *aviso no
cabeçalho de um comando que termina verde ninguém lê; instrumento que sabe do
próprio risco RESOLVE, não avisa.*

O CONTRATO QUE ESTA RÉGUA COBRA, e ele vale para QUALQUER portão, não só para
o `sprints-fechadas` — trava-se a classe, nunca a instância:

  1. portão que não pôde medir imprime `NÃO MEDIDO` na PRIMEIRA linha e
     devolve 0;
  2. o `portoes.sh` o nomeia com o rótulo `NÃO MEDIDO`, **mostra a saída dele**
     (a razão é metade da resposta) e o conta à parte no fim;
  3. ele NÃO reprova — faltou o dado, não o conserto — e a corrida ainda sai
     `rc=0`;
  4. e ele **não entra na conta dos verdes**: o fecho deixa de ser «TODOS
     VERDES — N portões» e passa a dizer quantos ficaram sem medição.

COMO ELA MEDE, e é de propósito o `portoes.sh` DE VERDADE: a régua copia o
script real para uma árvore de mentira e troca **só os dados** — o corpo da
tabela `_LISTA` — por dois portões de brinquedo. Toda a lógica de corrida e de
relatório exercitada é a de produção, byte por byte. Um dublê do relatório
provaria apenas que o dublê funciona.

A MORDIDA ARRANCA o ramo `NÃO MEDIDO` do `portoes.sh` (deixe o `if
[ "$rc" -eq 0 ]` sozinho, como era até 20/09/2026) e as quatro réguas abaixo
reprovam: o portão de brinquedo volta a sair `ok`, a razão dele some do
relatório e o fecho volta a chamá-lo de verde.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTOES = RAIZ / "scripts" / "portoes.sh"

#: O rótulo é o contrato. Ele mora aqui numa constante só para que a régua
#: fale dele uma vez; quem o mudar no `portoes.sh` sem mudar aqui vê as quatro
#: reprovarem, que é o ponto.
ROTULO = "NÃO MEDIDO"


def _arvore_de_mentira(tmp_path: Path) -> Path:
    """Uma árvore git com o `portoes.sh` REAL e uma tabela de dois portões.

    Só a TABELA é de mentira. O `_LISTA` do script real é um heredoc de dados;
    trocar os dados e manter o código é o que faz esta régua medir produção.
    """
    texto = PORTOES.read_text(encoding="utf-8")
    abre = texto.index("_LISTA() {")
    corpo = texto.index("TABELA\n}", abre)
    tabela = (
        "_LISTA() {\n"
        "  cat <<'TABELA'\n"
        "rapido|falso-sem-dado|bash|scripts/falso-sem-dado.sh\n"
        "rapido|falso-com-dado|bash|scripts/falso-com-dado.sh\n"
    )
    novo = texto[:abre] + tabela + texto[corpo:]
    assert novo.count("rapido|falso-sem-dado") == 1, (
        "a troca da tabela não pegou — o formato do `_LISTA` mudou e esta "
        "régua passou a medir outra coisa")

    (tmp_path / "scripts").mkdir(parents=True)
    alvo = tmp_path / "scripts" / "portoes.sh"
    alvo.write_text(novo, encoding="utf-8")
    alvo.chmod(0o755)

    sem_dado = tmp_path / "scripts" / "falso-sem-dado.sh"
    sem_dado.write_text(
        "#!/usr/bin/env bash\n"
        f"echo '{ROTULO}: o dado deste portão de brinquedo não está no disco.'\n"
        "echo '  e esta segunda linha é a razão, que tem de chegar junto.'\n"
        "exit 0\n", encoding="utf-8")
    sem_dado.chmod(0o755)

    com_dado = tmp_path / "scripts" / "falso-com-dado.sh"
    com_dado.write_text(
        "#!/usr/bin/env bash\n"
        "echo 'medi tudo e está certo'\n"
        "exit 0\n", encoding="utf-8")
    com_dado.chmod(0o755)

    feito = subprocess.run(["git", "init", "-q", str(tmp_path)],
                           capture_output=True, text=True, check=False)
    assert feito.returncode == 0, feito.stderr
    return tmp_path


@pytest.fixture
def relatorio(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    """A corrida do `portoes.sh` real sobre os dois portões de brinquedo."""
    arvore = _arvore_de_mentira(tmp_path)
    ambiente = dict(os.environ)
    ambiente.pop("HEFESTO_PY", None)
    return subprocess.run(
        ["bash", str(arvore / "scripts" / "portoes.sh"), "--rapido"],
        cwd=arvore, capture_output=True, text=True, check=False, env=ambiente,
    )


def _linha_do(saida: str, portao: str) -> str:
    for linha in saida.splitlines():
        if linha.strip().startswith(portao):
            return linha
    raise AssertionError(f"o portão `{portao}` não apareceu no relatório:\n{saida}")


def test_quem_nao_mediu_sai_rotulado_e_nao_como_ok(relatorio):
    """A linha dele diz NÃO MEDIDO; a de quem mediu continua dizendo `ok`."""
    linha = _linha_do(relatorio.stdout, "falso-sem-dado")
    assert ROTULO in linha, (
        "o portão que declarou não ter medido saiu como qualquer outro — é "
        f"verde sobre nada, e foi o defeito de 20/09/2026:\n{relatorio.stdout}")
    assert not re.search(r"\bok\b", linha), linha
    assert re.search(r"\bok\b", _linha_do(relatorio.stdout, "falso-com-dado")), (
        "a cura passou do ponto e comeu o `ok` de quem MEDIU:\n"
        f"{relatorio.stdout}")


def test_a_razao_de_nao_ter_medido_chega_junto(relatorio):
    """A saída dele é mostrada. Sem a razão, o rótulo é só outro silêncio.

    E a de quem mediu continua engolida — o relatório de 61 portões só é
    legível porque o verde não fala.
    """
    assert "o dado deste portão de brinquedo não está no disco" in relatorio.stdout
    assert "e esta segunda linha é a razão" in relatorio.stdout, (
        "só a primeira linha chegou; a razão vem depois dela e é o que "
        f"transforma o rótulo em conserto:\n{relatorio.stdout}")
    assert "medi tudo e está certo" not in relatorio.stdout, (
        f"a saída de quem passou vazou para o relatório:\n{relatorio.stdout}")


def test_nao_medido_nao_reprova_a_corrida(relatorio):
    """`rc=0`: faltou o DADO, não o conserto.

    Se isto reprovasse, o portão ficaria vermelho em toda árvore de agente —
    vermelho sem conserto, que é portão que alguém desliga na semana seguinte.
    """
    assert relatorio.returncode == 0, relatorio.stdout + relatorio.stderr
    assert "REPROVOU" not in relatorio.stdout, relatorio.stdout


def test_o_fecho_nao_chama_de_verde_quem_nao_mediu(relatorio):
    """O total de verdes desconta quem não mediu, e o fecho os nomeia.

    Era aqui que a conta mentia: `TODOS VERDES — 44 portões` incluía o que
    não tinha aberto um arquivo sequer.
    """
    saida = relatorio.stdout
    assert "TODOS VERDES" not in saida, (
        "o fecho chamou de verde uma corrida com portão não medido:\n" + saida)
    assert f"{ROTULO}S (1): falso-sem-dado" in saida, saida
    assert "VERDES — 1 de 2 portões" in saida, (
        "a conta dos verdes não descontou o não medido:\n" + saida)
