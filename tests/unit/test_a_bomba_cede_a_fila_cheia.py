"""RADIO-AFOGADO-02 — a fila cheia CEDE o quadro, não derruba o controle.

**O PAR DESTA RÉGUA É UM PATCH DE KERNEL**, e sem ele nada disto acontece: o
`uhid.ko` de fábrica descarta calado. Medido na máquina dela em 22/09/2026,
com um aparelho HID de mentira e o `/dev/uhid` sem ninguém lendo:

    uhid de fábrica   80 escritas, 80 «sucessos», 0 recusas
                      (e 53 «Output queue is full» no diário do kernel)
    uhid com patch    29 aceitas, 51 recusadas, a primeira em EAGAIN

O patch é de duas linhas em `drivers/hid/uhid.c`: `uhid_queue()` passa a
devolver `int` (`0` / `-EAGAIN`) e `uhid_hid_output_raw()` propaga em vez do
`return count` incondicional. Esse caminho é o de `hidraw_write()` →
`hid_hw_output_report()`, então o `-EAGAIN` chega ao `write(2)` de quem
escreve.

**E ERA AÍ QUE O PRODUTO IA QUEBRAR.** Até esta régua, todo `OSError` do
escritor significava *"o aparelho sumiu"* e o laço da ponte fazia `break` —
com o kernel ganhando voz, o PRIMEIRO engasgo do rádio mataria a ponte inteira
e o controle ficaria mudo até a volta seguinte. A cura tinha de vir junto.

O QUE ESTA RÉGUA COBRA:

1. `EAGAIN` (e os irmãos) cedem o quadro e a ponte SEGUE;
2. qualquer outro `OSError` continua derrubando — o aparelho que sumiu tem de
   derrubar mesmo;
3. o aviso sai na BORDA: a 93,75 escritas por segundo, um por quadro seria a
   enxurrada de volta, no journal em vez de no rádio;
4. o quadro cedido tem contador PRÓPRIO, separado de `escritas_recusadas` —
   os dois números respondem perguntas diferentes.
"""

from __future__ import annotations

import errno
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as af


def _bomba(escritor: Any) -> Any:
    """Uma bomba molhada, com a fonte mais simples que existe."""
    return af.BombaDeSomPeloRadio(
        arranjo=af.ARRANJO_035,
        fonte=lambda n: b"\x00" * n,
        escritor=escritor,
        seco=False,
        common=af.common_de_audio(),
    )


class _EscritorQueEnche:
    """O kernel com voz: aceita `folga` escritas e então diz que a fila encheu."""

    def __init__(self, folga: int, *, erro: int = errno.EAGAIN) -> None:
        self.folga = folga
        self.erro = erro
        self.tentativas = 0

    def __call__(self, report: bytes) -> int:
        self.tentativas += 1
        if self.tentativas > self.folga:
            raise OSError(self.erro, "Resource temporarily unavailable")
        return len(report)


# ---------------------------------------------------------------------------
# 1. ceder é seguir
# ---------------------------------------------------------------------------
def test_a_fila_cheia_cede_o_quadro_e_a_ponte_segue() -> None:
    """MORDIDA: tire o ramo `if erro.errno in FILA_CHEIA_DO_KERNEL` e o
    primeiro engasgo do rádio devolve `False` — a ponte cai e o controle fica
    mudo, que é PIOR que o defeito que o patch do kernel veio curar."""
    kernel = _EscritorQueEnche(folga=2)
    bomba = _bomba(kernel)

    assert bomba.escrever(b"\x35" + b"\x00" * 333) is True
    assert bomba.escrever(b"\x35" + b"\x00" * 333) is True
    assert bomba.escrever(b"\x35" + b"\x00" * 333) is True, (
        "a fila cheia derrubou a ponte"
    )
    assert bomba.contagem.quadros_cedidos_por_fila_cheia == 1
    assert bomba.contagem.escritas_recusadas == 0, (
        "o quadro cedido foi contado como recusa — são perguntas diferentes"
    )
    assert bomba.contagem.escritas_aceitas_pelo_kernel == 2


@pytest.mark.parametrize(
    "errno_do_kernel", [errno.EAGAIN, errno.EWOULDBLOCK, errno.ENOBUFS]
)
def test_os_tres_errnos_da_fila_cheia_cedem(errno_do_kernel: int) -> None:
    """`EWOULDBLOCK` é `EAGAIN` no Linux, e `ENOBUFS` é o mesmo recado vindo do
    socket — nenhum dos três é o aparelho sumindo."""
    bomba = _bomba(_EscritorQueEnche(folga=0, erro=errno_do_kernel))
    assert bomba.escrever(b"\x35" + b"\x00" * 333) is True
    assert bomba.contagem.quadros_cedidos_por_fila_cheia == 1


# ---------------------------------------------------------------------------
# 2. o aparelho que sumiu continua derrubando
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("errno_do_kernel", [errno.ENODEV, errno.EIO, errno.ENXIO])
def test_o_aparelho_que_sumiu_derruba_a_ponte(errno_do_kernel: int) -> None:
    """A cura não pode virar «nunca mais desisto»: o controle que caiu do rádio
    tem de derrubar a ponte, senão o `pw-record` fica lendo para ninguém.

    MORDIDA: devolva `True` para todo `OSError` e esta régua reprova.
    """
    bomba = _bomba(_EscritorQueEnche(folga=0, erro=errno_do_kernel))
    assert bomba.escrever(b"\x35" + b"\x00" * 333) is False
    assert bomba.contagem.escritas_recusadas == 1
    assert bomba.contagem.quadros_cedidos_por_fila_cheia == 0


# ---------------------------------------------------------------------------
# 3. o aviso sai na BORDA
# ---------------------------------------------------------------------------
def test_o_aviso_sai_na_borda_e_nao_por_quadro(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 93,75 escritas por segundo, um aviso por quadro seria a enxurrada de
    volta — no journal em vez de no rádio.

    MORDIDA: tire o `if not self._cedendo` e a contagem de avisos vira 40.
    """
    ditos: list[str] = []
    monkeypatch.setattr(
        af.logger, "info", lambda evento, **_k: ditos.append(str(evento))
    )

    class _AbreEFecha:
        def __init__(self) -> None:
            self.n = 0

        def __call__(self, report: bytes) -> int:
            self.n += 1
            if 3 <= self.n <= 42:
                raise OSError(errno.EAGAIN, "cheia")
            return len(report)

    bomba = _bomba(_AbreEFecha())
    for _ in range(50):
        assert bomba.escrever(b"\x35" + b"\x00" * 333) is True

    assert ditos.count("som_radio_cedendo_a_fila_cheia") == 1, ditos
    assert ditos.count("som_radio_voltou_a_caber") == 1, ditos
    assert bomba.contagem.quadros_cedidos_por_fila_cheia == 40


def test_a_fila_que_enche_de_novo_avisa_de_novo() -> None:
    """A borda é borda nos DOIS sentidos: sem isto, um segundo afogamento
    passaria calado porque o primeiro já tinha avisado."""

    class _DuasVezes:
        def __init__(self) -> None:
            self.n = 0

        def __call__(self, report: bytes) -> int:
            self.n += 1
            if self.n in (2, 6):
                raise OSError(errno.EAGAIN, "cheia")
            return len(report)

    bomba = _bomba(_DuasVezes())
    for _ in range(8):
        bomba.escrever(b"\x35" + b"\x00" * 333)
    assert bomba.contagem.quadros_cedidos_por_fila_cheia == 2
    assert bomba._cedendo is False


# ---------------------------------------------------------------------------
# 4. o laço da ponte não morre com a fila cheia
# ---------------------------------------------------------------------------
def test_o_laco_da_bomba_atravessa_o_afogamento() -> None:
    """De ponta a ponta: a bomba roda e entrega contagem, sem parar no engasgo.

    MORDIDA: devolva `False` no ramo da fila cheia — `rodar` faz `break` no
    primeiro engasgo e a contagem sai com um punhado de reports em vez da
    corrida inteira.
    """
    kernel = _EscritorQueEnche(folga=5)
    bomba = _bomba(kernel)
    tiques = [0.0]

    def _relogio() -> float:
        return tiques[0]

    def _dormir(_s: float) -> None:
        tiques[0] += 0.01

    contagem = bomba.rodar(segundos=0.2, agora=_relogio, dormir=_dormir)
    assert contagem.reports_montados >= 15, contagem
    assert contagem.quadros_cedidos_por_fila_cheia >= 10, contagem
    assert contagem.escritas_recusadas == 0
