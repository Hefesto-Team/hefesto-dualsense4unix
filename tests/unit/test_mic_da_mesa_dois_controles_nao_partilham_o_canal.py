"""MIC-DA-MESA-ELEICAO-01 — a colisão do nome curto na ponte de mic por BT.

**ESTA RÉGUA NASCE VERMELHA, E ISSO É O CORRETO.** Ela não descreve uma cura
desta leva: descreve um buraco ABERTO que a mesa de quatro passa por cima, e
que a eleição de microfone por controle torna consequente.

O QUE ESTÁ MEDIDO NO CÓDIGO (01/09/2026):

* `NoDualSenseBT.nome_curto` devolve os SEIS últimos dígitos hex do MAC. Dois
  controles cujos três últimos octetos coincidam geram o **mesmo**
  `source_name` (`hefesto_dualsense_bt_<hex6>`) **e o mesmo fifo**;
* `PontePyDualSenseBT.iniciar()` faz `os.unlink` incondicional do fifo —
  apagando o fifo da ponte que já estava de pé;
* o docstring de `nome_curto` promete o contrário, com todas as letras: *"o
  que não pode é dois controles gerarem o MESMO nome de source e um
  sobrescrever o outro"*;
* `grep nome_curto tests/` devolvia ZERO antes deste arquivo.

Com a eleição por `uniq`, isso deixa de ser um incômodo de nome: `escolher_fonte`
resolveria os DOIS controles para a MESMA source, e a eleição do Jogador 3
acenderia o LED do Jogador 1.

Por que `xfail(strict=True)` e não um teste comentado: `strict` REPROVA se um
dia passar sem ninguém avisar. Assim o vermelho fica registrado, o portão fica
verde, e no dia em que a cura chegar a régua cobra que este arquivo seja
atualizado em vez de esquecido.

**Curar aqui não é desta leva** — é sprint própria, porque a cura muda o nome de
uma source publicada (contrato com o PipeWire e com quem já tem a ponte de pé).
"""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.integrations.dualsense_bt_audio import NoDualSenseBT


def _no(uniq: str, caminho: str) -> NoDualSenseBT:
    return NoDualSenseBT(caminho=caminho, uniq=uniq, produto=0x0CE6)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "BURACO ABERTO: `nome_curto` usa só os 6 últimos dígitos hex do MAC. "
        "Dois controles com os TRÊS últimos octetos iguais colidem no nome da "
        "source e no fifo, e `iniciar()` faz unlink incondicional. A cura muda "
        "o contrato de nome com o PipeWire e é sprint própria."
    ),
)
def test_dois_controles_com_o_rabo_igual_nao_podem_gerar_o_mesmo_nome() -> None:
    """Dois MACs distintos, mesmos três últimos octetos: nomes TÊM de diferir."""
    a = _no("aa:bb:cc:00:00:01", "/dev/hidraw3")
    b = _no("02:fe:00:00:00:01", "/dev/hidraw4")

    assert a.uniq != b.uniq, "são dois controles diferentes"
    assert a.nome_curto != b.nome_curto, (
        "mesmo nome de source e mesmo fifo — a segunda ponte apaga a primeira"
    )


def test_o_docstring_de_nome_curto_promete_o_que_o_codigo_nao_entrega() -> None:
    """A promessa está escrita, e é ela que faz o buraco parecer curado.

    Esta metade PASSA hoje, e existe para que a divergência entre a prosa e o
    ato fique registrada onde alguém a encontre — em vez de descoberta de novo
    na mesa dela, com quatro controles na mão.
    """
    doc = NoDualSenseBT.nome_curto.__doc__ or ""
    assert "MESMO nome de\n        source" in doc or "MESMO nome de" in doc
    a = _no("aa:bb:cc:00:00:01", "/dev/hidraw3")
    b = _no("02:fe:00:00:00:01", "/dev/hidraw4")
    assert a.nome_curto == b.nome_curto, (
        "o código faz exatamente o que o docstring diz que não pode"
    )
