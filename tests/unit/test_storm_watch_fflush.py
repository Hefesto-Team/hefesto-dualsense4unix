"""O `classify()` do `storm_watch.sh` descarrega cada linha que escreve.

CADERNO-QUE-NÃO-ESCREVE-01 (08/08/2026). O defeito de produto é MEDIDO: o
caderno `~/.local/state/hefesto-dualsense4unix/kernel.log` tem **120 linhas,
todas banners** do próprio shell, zero eventos classificados — contra **723**
eventos de storm no journal do mesmo período, com a vigia `enabled` e `active`
o tempo todo. Ela pediu a explicação da queda dos controles; o arquivo que a
guardaria estava vazio.

O mecanismo lido de ponta a ponta: o `awk` do `classify()` escreve num arquivo
por `>>`, então a libc usa buffer de bloco (256 KiB). A vigia é um processo de
vida longa que só termina por sinal — e o `SIGTERM` que o systemd manda ao
cgroup **destrói** o buffer em vez de descarregá-lo. O `trap ... EXIT INT TERM`
da linha 162 faz o *shell* sobreviver e escrever o banner de encerramento,
enquanto o `awk` morre com o conteúdo dentro: é isso que faz o caderno parecer
vivo estando vazio.

POR QUE ESTE TESTE É ESTÁTICO, E A HONESTIDADE QUE VEM COM ISSO
===============================================================
O teste de comportamento seria melhor, e ele foi tentado. **Não foi possível
construí-lo de forma confiável nesta bancada:** três variantes (`awk` sem
`fflush`, com `fflush()`, e com `stdbuf -oL`) devolveram **zero byte** com o
processo vivo. Como o `stdbuf -oL` é sabidamente line-buffered, o resultado
idêntico nas três acusa o instrumento, não o `awk`.

Um teste de comportamento que não distingue a cura da ausência dela é pior que
nenhum: ele passa verde nos dois casos e dá a impressão de cobertura. Então este
arquivo trava o que é possível travar com honestidade — que a cura está escrita e
no lugar certo — e **declara** que a prova de comportamento continua devendo.

O grau, pela régua da casa: o defeito é **MEDIDO**; a atribuição ao `fflush`
ausente é **SUSPEITA COM MECANISMO**. Este teste protege a cura de sumir por
descuido; ele não prova que ela funciona.
"""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "storm_watch.sh"


def _corpo_do_classify() -> str:
    """O texto entre `classify() {` e a próxima função do script."""
    texto = SCRIPT.read_text(encoding="utf-8")
    inicio = texto.index("classify() {")
    fim = texto.index("bt_read_errors()", inicio)
    return texto[inicio:fim]


def _bloco_do_classify() -> str:
    """O corpo MAIS o cabeçalho de comentários que o precede.

    O porquê da cura mora nos comentários ACIMA do `classify() {` — é onde a
    convenção deste script põe explicação. Quem for ler a linha do `fflush()`
    encontra o motivo subindo o olho, e é isso que este bloco captura.
    """
    texto = SCRIPT.read_text(encoding="utf-8")
    inicio = texto.index("classify() {")
    # sobe até a primeira linha que não seja comentário
    linhas = texto[:inicio].splitlines()
    topo = len(linhas)
    while topo > 0 and linhas[topo - 1].lstrip().startswith("#"):
        topo -= 1
    cabecalho = "\n".join(linhas[topo:])
    return cabecalho + "\n" + _corpo_do_classify()


def test_a_cura_esta_escrita() -> None:
    """O `fflush()` está no `classify()`.

    ARRANQUE A CURA e este teste REPROVA. É o portão barato contra remoção por
    descuido — alguém "limpando" o `awk` levaria a linha junto, e o caderno
    voltaria a ficar vazio em silêncio, que é o pior modo de falha que existe:
    ausência de dado é indistinguível de ausência de defeito.
    """
    assert "fflush()" in _corpo_do_classify(), (
        "o `fflush()` sumiu do `classify()` de `scripts/storm_watch.sh`. Sem ele "
        "o caderno da vigia não escreve até o processo morrer — e ele morre por "
        "sinal, que destrói o buffer. Ver "
        "docs/process/sprints/2026-08-08-CADERNO-QUE-NAO-ESCREVE-01-*.md"
    )


def test_a_cura_esta_no_lugar_certo() -> None:
    """O `fflush()` vem DEPOIS do `print`, no mesmo bloco por linha.

    Fora dali ele não descarrega o que acabou de ser escrito: um `fflush()` no
    `BEGIN` ou no `END` satisfaria o teste de cima e não curaria nada.
    """
    linhas = _corpo_do_classify().splitlines()
    idx_print = next(
        (i for i, ln in enumerate(linhas) if 'print ts " " tag " " rest' in ln), None
    )
    idx_fflush = next((i for i, ln in enumerate(linhas) if "fflush()" in ln), None)

    assert idx_print is not None, "o `print` do classificador sumiu do `classify()`"
    assert idx_fflush is not None, "o `fflush()` sumiu do `classify()`"
    assert idx_fflush > idx_print, (
        "o `fflush()` precisa vir DEPOIS do `print`, dentro do mesmo bloco por "
        "linha do `awk`. Antes dele, ou num BEGIN/END, ele não descarrega a "
        "linha que acabou de ser escrita."
    )

    entre = "\n".join(linhas[idx_print:idx_fflush])
    assert "}" not in entre, (
        "o `fflush()` saiu do bloco do `print` — há um `}` entre os dois, então "
        "ele deixou de rodar por linha."
    )


def test_o_defeito_esta_documentado_no_script() -> None:
    """Quem abrir o script encontra o porquê, não só a linha.

    A casa registra que conhecimento perdido custa tempo de alguém. Uma linha
    de `fflush()` sem explicação é candidata a ser removida por quem acha que é
    higiene — e foi por isso que ela nunca existiu.
    """
    corpo = _bloco_do_classify()
    assert "CADERNO-QUE-NÃO-ESCREVE-01" in corpo, (
        "o comentário que explica por que o `fflush()` existe saiu do "
        "`classify()`. Sem ele a linha vira mistério e alguém a remove."
    )
