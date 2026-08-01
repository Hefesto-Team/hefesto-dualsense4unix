"""A linha de comando e a janela falam a MESMA régua de volume (SOM-02).

Por que este arquivo existe, medido em 01/08/2026 no hardware dela:

A resposta do registrador de volume do DualSense é fortemente NÃO-LINEAR. Curva
medida com o microfone do próprio controle como instrumento (tom de 1 kHz no
sink do controle, Goertzel no bin de 1 kHz, sink do PipeWire e mixer ALSA
travados, só o registrador variando):

    cru 0 -> 3,9      cru 13 -> 5,3     cru 26 -> 3,1    cru 38 -> 6,2   (mudo)
    cru 51 -> 35      cru 64 -> 172     cru 76 -> 687             (a faixa util)
    cru 102 -> 8759   cru 128 -> 8488   cru 255 -> 8793           (saturado)

Consequência: uma régua linear faz `speaker volume 60` na linha de comando e os
60 % do controle deslizante da janela mandarem valores diferentes para o MESMO
registrador — e o pior, com resultados audíveis diferentes. Duas contas para a
mesma grandeza é a receita de a interface contradizer a linha de comando, que é
a classe de defeito que esta casa mais paga (três escritores do perfil sem
dono, os dois cadastros do Steam Input, as três grafias do socket).

A cura foi importar a conta da janela no `cmd_speaker`. Estes testes MORDEM se
alguém duplicar a régua de volta, ou se o import puxar GTK — a linha de comando
roda em ambiente sem interface, e um `gi` no caminho derrubaria o comando
inteiro num servidor.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CMD_SPEAKER = REPO / "src" / "hefesto_dualsense4unix" / "cli" / "cmd_speaker.py"


def test_a_linha_de_comando_usa_a_regua_da_janela() -> None:
    """`cmd_speaker` importa as conversões, em vez de reimplementá-las."""
    from hefesto_dualsense4unix.core.speaker_scale import (
        percentual_do_volume,
        volume_do_percentual,
    )
    from hefesto_dualsense4unix.cli import cmd_speaker

    assert cmd_speaker.volume_do_percentual is volume_do_percentual
    assert cmd_speaker.percentual_do_volume is percentual_do_volume


@pytest.mark.parametrize("pct", [0, 1, 25, 50, 60, 75, 99, 100])
def test_o_mesmo_percentual_vira_o_mesmo_bruto_nos_dois_caminhos(pct: int) -> None:
    """O 60 % da janela e o `speaker volume 60` mandam o MESMO valor cru."""
    from hefesto_dualsense4unix.core.speaker_scale import volume_do_percentual
    from hefesto_dualsense4unix.cli.cmd_speaker import _pct_para_bruto

    assert _pct_para_bruto(pct) == volume_do_percentual(pct)


def test_a_regua_nao_e_linear_senao_nao_ha_o_que_unificar() -> None:
    """Guarda da premissa: se a régua virar linear, este arquivo perde sentido.

    Não trava as bordas (são empíricas de um rig e podem ser reaferidas), trava
    o FATO de o remapeamento existir. Uma régua linear mandaria 153 para 60 %;
    a remapeada manda bem menos, porque o registrador satura por volta de 102.
    """
    from hefesto_dualsense4unix.core.speaker_scale import volume_do_percentual

    assert volume_do_percentual(100) < 255, (
        "a régua voltou a ser linear: 100 % manda 255, mas o registrador satura "
        "muito antes disso e os últimos 60 % do curso seriam inertes"
    )
    assert volume_do_percentual(0) == 0, "0 % tem de ser mudo de verdade, não o piso"
    assert volume_do_percentual(100) > volume_do_percentual(50) > volume_do_percentual(1)


def test_o_zero_por_cento_emudece_e_nao_cai_no_piso_da_faixa() -> None:
    """0 % é mudo; o piso da faixa útil é outra coisa e não pode ser confundido."""
    from hefesto_dualsense4unix.core.speaker_scale import volume_do_percentual

    assert volume_do_percentual(0) == 0
    assert volume_do_percentual(1) > 0, "1 % não pode colapsar em mudo"


def test_a_ida_e_volta_nao_desloca_o_valor() -> None:
    """`pct -> cru -> pct` fica dentro de 1 ponto — a barra não briga com a escala."""
    from hefesto_dualsense4unix.cli.cmd_speaker import _bruto_para_pct, _pct_para_bruto

    for pct in range(0, 101):
        assert abs(_bruto_para_pct(_pct_para_bruto(pct)) - pct) <= 1, (
            f"{pct} % ida e volta saiu deslocado — a leitura contradiria o comando"
        )


def test_a_linha_de_comando_nao_puxa_gtk() -> None:
    """O comando roda em servidor sem interface: `gi` no caminho o derrubaria.

    Importa num interpretador limpo e falha se `gi` aparecer em `sys.modules`.
    Subprocesso de propósito: nesta máquina a suíte já carregou GTK por outros
    testes, e olhar o `sys.modules` deste processo daria falso-vermelho.
    """
    codigo = (
        "import sys; import hefesto_dualsense4unix.cli.cmd_speaker as m; "
        "print('gi' in sys.modules)"
    )
    saida = subprocess.run(
        [sys.executable, "-c", codigo],
        capture_output=True,
        text=True,
        cwd=str(REPO),
        timeout=120,
    )
    assert saida.returncode == 0, f"o import do comando falhou: {saida.stderr[-600:]}"
    assert saida.stdout.strip() == "False", (
        "importar `cli.cmd_speaker` puxou GTK — o comando deixaria de funcionar "
        "em servidor sem interface"
    )


def test_nenhuma_conta_de_255_sobrou_no_corpo_das_conversoes() -> None:
    """Morde a duplicação de volta: `* 255 / 100` reaparecendo no comando.

    Lê a árvore sintática das duas funções em vez de varrer o arquivo por texto,
    porque a docstring EXPLICA a régua e citaria os números — um `grep` reprovaria
    pela própria explicação, que é a armadilha que o gate anti-emoji desta casa
    já pagou uma vez.
    """
    arvore = ast.parse(CMD_SPEAKER.read_text(encoding="utf-8"))
    alvos = {"_pct_para_bruto", "_bruto_para_pct"}
    achadas: set[str] = set()

    for no in ast.walk(arvore):
        if not isinstance(no, ast.FunctionDef) or no.name not in alvos:
            continue
        achadas.add(no.name)
        corpo = [x for x in no.body if not isinstance(x, ast.Expr)]
        constantes = [
            c.value
            for c in ast.walk(ast.Module(body=corpo, type_ignores=[]))
            if isinstance(c, ast.Constant) and isinstance(c.value, (int, float))
        ]
        assert 255 not in constantes and 100 not in constantes, (
            f"{no.name} voltou a fazer a conta em vez de delegar: a régua da "
            f"linha de comando divergiria da janela no mesmo hardware"
        )

    assert achadas == alvos, f"as funções sumiram ou mudaram de nome: {achadas}"
