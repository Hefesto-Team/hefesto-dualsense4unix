"""O-TESTE-ANTERIOR-NAO-DEIXA-PAD-NA-MESA-DO-SEGUINTE-01 — o pad parado no tique sai do jogo.

**O que se mediu (25/10/2026, na integração ``e9d2dffdb``).** Os 146 vermelhos
de quatro arquivos (a háptica que segue o vpad, os atalhos na espera, o buraco
de quem saiu e o PS em qualquer controle) não vinham do arquivo anterior: os
quatro reprovavam SOZINHOS, cada um num processo, e passavam no ``683eac399``.
O que os derrubou foi a ``739074a43`` (O-JOGADOR-QUE-SAI-NAO-PRENDE-O-TIQUE-NO-
BROKER-01): o co-op para o vpad de quem sai pelo ``parar_fora_do_tique``, que
desce a casa do pad ``uhid`` sem passar pelo ``stop`` dele, e a
:class:`MesaHonesta` só via a morte no ``stop``. O pad seguia vivo para o
:class:`JogoPorFora`, com a identidade de quem o co-op já tinha renascido.

A régua: o pad de quem sai, e o de quem renasce atrás dele, parados no tique,
somem do jogo da bancada, de dois a quatro controles, no cabo, no rádio e na
mesa mista. MORDIDA: devolva o ``MesaHonesta.__init__`` sem o
``_parar_na_casa`` da bancada e esta régua reprova com a mensagem da
``MesaDoJogo`` («a mesa que o co-op guarda não é a que o jogo vê»).

Nenhum endereço real: faixa forjada ``aa:bb:cc`` com os octetos 4 e 5 zerados.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from hefesto_dualsense4unix.integrations.uhid_gamepad import parar_fora_do_tique
from tests.unit.test_dois_vpads_nunca_tem_o_mesmo_mac import (
    KernelDoHidPlaystation,
    kernel_de_mentira,
)
from tests.unit.test_o_buraco_de_quem_saiu_se_fecha_no_jogo import (
    MesaHonesta,
    _o_prazo_passa_e_ela_renumera,
    montar_honesto,
)
from tests.unit.test_o_jogo_espera_a_carta_do_lugar_guardado import (  # noqa: F401
    MATRIZ,
    UNIQS,
    config_isolado,
)


@pytest.fixture
def kernel(monkeypatch: pytest.MonkeyPatch) -> Iterator[KernelDoHidPlaystation]:
    """O kernel de mentira da O-VPAD: nenhum ``/dev/uhid`` ou ``/dev/uinput`` de verdade."""
    with kernel_de_mentira(monkeypatch) as k:
        yield k


def _o_jogo_nao_ve(bancada: MesaHonesta, vpad: object) -> None:
    assert not getattr(vpad, "vivo", True), "o pad parado segue vivo na bancada"
    assert all(v is not vpad for v in bancada.jogo.ve()[1].values()), (
        f"o jogo segue vendo o pad parado: {bancada.jogo.ve()[1]}"
    )


@pytest.mark.usefixtures("config_isolado")
class TestOPadParadoNoTiqueSaiDoJogo:
    """O vpad ``uhid`` que o co-op para no laço do tique morre também para o jogo."""

    @MATRIZ
    def test_quem_sai_e_quem_renasce_atras_dele_saem_do_jogo(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation,
        quantos: int, transporte: str,
    ) -> None:
        bancada = montar_honesto(monkeypatch, kernel, quantos, transporte)
        antes = {u: bancada.vpad_de(u) for u in UNIQS[1:quantos]}
        assert all(getattr(v, "backend", None) == "uhid" for v in antes.values())

        bancada.mesa.levantar(UNIQS[1])
        _o_prazo_passa_e_ela_renumera(bancada, 0.0)

        parados = [v for u, v in antes.items() if bancada.vpad_de(u) is not v]
        assert len(parados) == quantos - 1, "quem saiu ou quem ficou atrás não desceu"
        for velho in parados:
            _o_jogo_nao_ve(bancada, velho)
        bancada.o_jogo_segue_a_tela()

    @MATRIZ
    def test_a_parada_no_tique_e_a_do_stop_saem_do_jogo_igual(
        self, monkeypatch: pytest.MonkeyPatch, kernel: KernelDoHidPlaystation,
        quantos: int, transporte: str,
    ) -> None:
        bancada = montar_honesto(monkeypatch, kernel, quantos, transporte)
        no_tique = bancada.vpad_de(UNIQS[quantos - 1])
        posto = bancada.vpad_do_p1

        parar_fora_do_tique(no_tique)
        _o_jogo_nao_ve(bancada, no_tique)
        posto.stop()
        _o_jogo_nao_ve(bancada, posto)
