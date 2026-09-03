"""O doctor não pode contar o passado no presente.

O DEFEITO, achado POR ELA em 03/09/2026, lendo a saída do install:

    *"nem o 8bitdo tá conectado nem o usb pareceu ter dado pau. acho que essas
    4 mensagens tão erradas não?"*

**Estavam.** O bloco do kernel-watch fazia ``grep -c "[JOYCON]"`` sobre o log
INTEIRO — que começa em 20/07 — e escrevia o número no PRESENTE: *"o kernel deu
rate-limit no controle Nintendo/8BitDo 9 vez(es)"*. Os nove eventos eram de
11/08 (três) e 26/08 (seis), e o 8BitDo estava desligado havia semanas. O mesmo
valia para *"storm USB registrado 113 vezes"*, cujo último foi em 30/08.

**O DEFEITO NÃO É O NÚMERO — É O TEMPO VERBAL.** Um aviso que afirma com
confiança um estado que não é o de agora manda procurar defeito onde não há, e
para quem lê tela é o pior arranjo que existe: ele parece medição.

A CURA TEM DUAS METADES, e este arquivo cobra as duas:

1. só é AVISO o que aconteceu dentro da janela (``HEFESTO_DOCTOR_JANELA_DIAS``,
   7 por padrão);
2. todo número vem com a DATA do último evento, e o histórico é dito como
   histórico.

A MORDIDA: tire o corte da janela (faça ``_quantos_desde`` devolver o total) e
:func:`test_evento_velho_nao_vira_aviso` reprova.
"""

from __future__ import annotations

import datetime
import os
import pathlib
import subprocess
import textwrap

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts/doctor.sh"

#: SÓ O BLOCO DO KERNEL-WATCH, extraído do doctor e rodado num bash mínimo.
#: Rodar o doctor inteiro traria sudo, systemd e o daemon vivo para dentro de um
#: teste — e o que se mede aqui é UMA decisão: o que vira aviso e o que vira
#: histórico.
_PREAMBULO = textwrap.dedent(
    """
    set -uo pipefail
    HOME="$TMPHOME"
    warn() { printf 'WARN %s\\n' "$*"; }
    info() { printf 'INFO %s\\n' "$*"; }
    pass() { :; }
    conselho_de_instalacao() { :; }
    so_no_checkout() { :; }
    """
)


def _bloco_do_kernel_watch() -> str:
    """O corpo de ``check_kernel_watch``, do fonte — nunca uma cópia.

    Copiar o bloco para dentro deste arquivo faria a régua medir a si mesma: no
    dia em que o doctor mudasse, ela continuaria verde sobre o texto antigo. É
    o defeito que esta casa persegue com o nome de *segunda verdade*.
    """
    fonte = DOCTOR.read_text(encoding="utf-8")
    i = fonte.index("    local log=\"${HOME}/.local/state/hefesto-dualsense4unix/kernel.log\"")
    j = fonte.index("\n}\n", i)
    return fonte[i:j]


def _rodar(linhas: list[str], janela: int = 7) -> str:
    """Escreve um `kernel.log` de mentira e devolve o que o bloco imprime."""
    import tempfile

    with tempfile.TemporaryDirectory() as lar:
        estado = pathlib.Path(lar) / ".local/state/hefesto-dualsense4unix"
        estado.mkdir(parents=True)
        (estado / "kernel.log").write_text("\n".join(linhas) + "\n", encoding="utf-8")
        env = dict(os.environ, TMPHOME=lar, HEFESTO_DOCTOR_JANELA_DIAS=str(janela))
        # O BLOCO USA `local`, que só existe dentro de função — então ele roda
        # dentro de uma. É o mesmo contexto do doctor de verdade, onde ele é o
        # corpo de `check_kernel_watch`.
        roteiro = (_PREAMBULO + "\n_bloco() {\n"
                   + _bloco_do_kernel_watch() + "\n}\n_bloco\n")
        r = subprocess.run(
            ["bash", "-c", roteiro],
            capture_output=True, text=True, env=env, cwd=str(RAIZ))
        return r.stdout + r.stderr


def _linha(dias_atras: int, tag: str) -> str:
    d = datetime.date.today() - datetime.timedelta(days=dias_atras)
    return f"{d.isoformat()} 12:00:00 [{tag}] alguma coisa aconteceu"


def test_evento_de_hoje_vira_aviso() -> None:
    """O que acontece AGORA continua sendo aviso — a cura não pode calar."""
    saida = _rodar(["# 2026-07-20 kernel-watch iniciado", _linha(0, "JOYCON")])
    assert "WARN" in saida, saida
    assert "JOYCON" in saida


def test_evento_velho_nao_vira_aviso() -> None:
    """Um evento de 24 dias atrás é HISTÓRICO, e o doctor diz isso.

    É o caso exato que ela pegou: nove `[JOYCON]` de 11/08 e 26/08 anunciados
    como se fossem de agora, com o 8BitDo desligado.
    """
    saida = _rodar(["# 2026-07-20 kernel-watch iniciado", _linha(24, "JOYCON")])
    assert "WARN" not in saida, (
        f"um evento de 24 dias atrás virou aviso:\n{saida}")
    assert "histórico" in saida, saida


def test_o_aviso_diz_a_data_do_ultimo() -> None:
    """Todo número vem com QUANDO — sem isso ele não é verificável.

    Um "113 vezes" sem data é uma afirmação que ninguém pode conferir, e foi
    exatamente por não ter data que a frase enganou.
    """
    d = datetime.date.today() - datetime.timedelta(days=2)
    saida = _rodar(["# 2026-07-20 kernel-watch iniciado",
                    _linha(30, "USB-71"), _linha(2, "USB-71")])
    assert f"{d.day:02d}/{d.month:02d}" in saida, saida
    assert "no log inteiro" in saida, (
        "o aviso deixou de separar a janela do total — as duas contas importam")


def test_o_total_do_log_continua_dito() -> None:
    """O histórico não se apaga: ele muda de lugar e de tempo verbal.

    Esconder o total trocaria um exagero por uma omissão. A linha de resumo
    continua trazendo o log inteiro, dizendo que é o log inteiro.
    """
    saida = _rodar(["# 2026-07-20 kernel-watch iniciado"]
                   + [_linha(40, "USB-71")] * 5)
    assert "USB-71=5" in saida, saida
    assert "log INTEIRO" in saida, saida


def test_log_limpo_nao_diz_nada() -> None:
    """Sem evento nenhum, nem aviso nem histórico — só o resumo."""
    saida = _rodar(["# 2026-07-20 kernel-watch iniciado"])
    assert "WARN" not in saida, saida
    assert "histórico" not in saida, saida


@pytest.mark.parametrize("tag", ["JOYCON", "JOYCON-PROBE", "USB-71", "BT-ERR"])
def test_os_quatro_contadores_obedecem_a_janela(tag: str) -> None:
    """A janela vale para os QUATRO, e não só para o que ela notou.

    Curar um contador e deixar três com o defeito seria a cura pela metade que
    esta casa já pagou várias vezes — e o próximo a enganar seria outro.
    """
    velho = _rodar(["# 2026-07-20 kernel-watch iniciado", _linha(30, tag)])
    assert "WARN" not in velho, f"{tag} de 30 dias atrás virou aviso:\n{velho}"
    novo = _rodar(["# 2026-07-20 kernel-watch iniciado", _linha(1, tag)])
    assert "WARN" in novo, f"{tag} de ontem não virou aviso:\n{novo}"
