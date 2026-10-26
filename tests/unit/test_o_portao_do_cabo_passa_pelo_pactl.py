"""O portão dos motores do cabo abre de verdade: o ``pactl`` aceita o comando.

A rodada 1 da bancada (14/10/2026, Sackboy, só o White no cabo): o laço da
háptica ficou com a frente a 100 % e os motores a 0 % a partida inteira, com o
White marcado em ``haptica_quem_joga``. O portão aberto mandava
``100% 100% 1.0000 1.0000`` — por cento na frente, fator nos motores —, e o
``pactl`` recusa o comando que mistura unidades (``Inconsistent volume
specification.``, rc 1, antes de falar com o servidor). O fechado
(``100% 100% 0% 0%``) passava, e por isso a única linha do portão no diário era
a de ``motores_abertos=False``. A falha de aplicar não deixava rastro.

A regra das unidades se mediu no ``pactl`` 16.1 desta máquina, com um servidor
que não existe (``PULSE_SERVER=unix:/nenhum``): ``100% 100% 2.0000 2.0000`` sai
com ``Inconsistent volume specification.``, e ``1.0000 1.0000 2.0000 2.0000`` e
``100% 100% 0% 0%`` chegam à falha de conexão. A suíte troca o ``pactl`` por um
dublê (``BINARIOS_DO_SERVIDOR_DE_SOM`` no ``conftest``), então quem guarda a
regra é ``pactl_json_de_mentira.o_pactl_aceita_os_volumes``, que os dublês do
cabo passaram a aplicar.
"""

from __future__ import annotations

import pytest
import structlog

from hefesto_dualsense4unix.integrations.haptica_do_cabo import HapticaDoCabo, RotaDoCabo
from tests.unit import pactl_json_de_mentira as pj

_BRANCO = "aa:bb:cc:00:00:0b"
_MARCA = "APARELHOBRANCO"
_ROTA = RotaDoCabo(captura="61157", destino="60332", dono=_BRANCO)


class _Lacos:
    def __init__(self) -> None:
        self.ligados: set[str] = set()

    def esta_ligado(self, chave: str) -> bool:
        return chave in self.ligados

    def ligar(self, chave: str, **_kw: object) -> bool:
        self.ligados.add(chave)
        return True

    def desligar(self, chave: str) -> None:
        self.ligados.discard(chave)


def _portoes(ganho: float) -> list[list[str]]:
    """Os comandos que o laço manda ao ``pactl`` para um controle."""
    escritas: list[list[str]] = []

    def pactl(argv: list[str]) -> str:
        escritas.append(list(argv))
        return ""

    cabo = HapticaDoCabo(_Lacos(), indice_do_fluxo=lambda _no: "61178", pactl=pactl)
    cabo.casar({_MARCA: _ROTA}, {_MARCA: ganho})
    return escritas


_CASOS = [1.0, 2.0, 0.3, 0.0]


@pytest.mark.parametrize("ganho", _CASOS)
def test_os_quatro_canais_vao_na_mesma_unidade(ganho: float) -> None:
    """MORDIDA: devolva ``VOLUME_ABERTO = "100%"`` e os portões abertos reprovam."""
    (argv,) = _portoes(ganho)
    assert pj.o_pactl_aceita_os_volumes(argv[3:]), f"o pactl recusa {argv[3:]}"


def test_duzentos_por_cento_sai_como_fator_dois() -> None:
    """A háptica a 200 % chega ao fluxo como 2,0 nos motores: nem satura a 1, nem vira 0."""
    (argv,) = _portoes(2.0)
    assert argv[3:] == ["1.0000", "1.0000", "2.0000", "2.0000"]


def test_a_falha_do_portao_deixa_rastro_em_info_uma_vez() -> None:
    """MORDIDA: tire o ``_dizer_a_falha`` e a recusa do ``pactl`` volta a ser muda."""
    respostas: list[str | None] = [None, None, ""]

    def pactl(_argv: list[str]) -> str | None:
        return respostas.pop(0)

    cabo = HapticaDoCabo(_Lacos(), indice_do_fluxo=lambda _no: "61178", pactl=pactl)
    with structlog.testing.capture_logs() as diario:
        for _ in range(3):
            cabo.casar({_MARCA: _ROTA}, {_MARCA: 1.0})
    falhas = [r for r in diario if r["event"] == "haptica_do_cabo_portao_falhou"]
    assert [(r["log_level"], r["uniq"], r["motivo"]) for r in falhas] == [
        ("info", _BRANCO, "pactl_recusou")
    ], "a recusa sai uma vez, e não a cada volta"
    assert cabo.leva_os_motores(_MARCA) is True, "a volta seguinte tentou de novo e abriu"


def test_sem_o_fluxo_do_laco_a_falha_diz_o_motivo() -> None:
    cabo = HapticaDoCabo(_Lacos(), indice_do_fluxo=lambda _no: None, pactl=lambda _a: "")
    with structlog.testing.capture_logs() as diario:
        cabo.casar({_MARCA: _ROTA}, {_MARCA: 1.0})
    motivos = [r["motivo"] for r in diario if r["event"] == "haptica_do_cabo_portao_falhou"]
    assert motivos == ["sem_fluxo_do_laco"]
