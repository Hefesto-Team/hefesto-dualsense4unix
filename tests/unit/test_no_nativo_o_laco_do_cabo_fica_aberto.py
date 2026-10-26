"""O laço do cabo fica aberto em todo modo, para todo controle no cabo, sem esperar toque."""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.profiles.schema import HAPTICA_PCT_PADRAO
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.integrations.haptica_do_cabo import (
    VOLUME_ABERTO,
    chave_do_aparelho,
)
from tests.unit.test_a_haptica_chega_a_quem_entra_depois import (  # noqa: F401
    _P1,
    _P2,
    _P3,
    _P4,
    _Controle,
    _Mesa,
    _no_cabo,
    mesa,
)

_QUATRO = (_P1, _P2, _P3, _P4)
_APARELHOS = (("3-8", 28), ("3-7", 29), ("3-6", 30), ("3-5", 31))

_ABERTO = [VOLUME_ABERTO, VOLUME_ABERTO, *[f"{HAPTICA_PCT_PADRAO / 100:.4f}"] * 2]


def _daemon(*, nativo: bool) -> Any:
    """O ``Daemon`` de verdade, com o Modo Nativo no atributo que o gesto escreve."""
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.testing import FakeController

    daemon = Daemon(controller=FakeController(), config=DaemonConfig())
    daemon._native_mode = nativo
    assert daemon.is_native_mode() is nativo
    return daemon


def _no_cabo_os_primeiros(m: _Mesa, n: int) -> list[_Controle]:
    """Os ``n`` primeiros no cabo, cada um com o seu número, e o jogo tocando nos ``n``."""
    controles = [
        _no_cabo(m, uniq, numero, *_APARELHOS[numero - 1])
        for numero, uniq in enumerate(_QUATRO[:n], 1)
    ]
    m.servidor.jogo_em.update(eh.nome_do_endpoint(uniq) for uniq in _QUATRO[:n])
    return controles


def _motores(m: _Mesa, numero: int) -> list[str]:
    """O volume do laço do controle de número ``numero`` (P1 a P4)."""
    return m.servidor.volumes[m.servidor.fluxo_do_laco(_QUATRO[numero - 1])]


def _marca(numero: int) -> str:
    return eh.marca_do_aparelho(_QUATRO[numero - 1])


@pytest.mark.parametrize("n", [2, 3, 4], ids=["dois", "três", "quatro"])
@pytest.mark.parametrize("nativo", [True, False], ids=["nativo", "xbox"])
def test_os_motores_de_todo_controle_no_cabo_abrem_em_todo_modo(
    mesa: _Mesa,  # noqa: F811
    n: int,
    nativo: bool,
) -> None:
    """O jogo manda nos motores de todos no cabo, P1 a P4, no Nativo e no Xbox, sem toque."""
    controles = _no_cabo_os_primeiros(mesa, n)
    mesa.sub._daemon = _daemon(nativo=nativo)
    mesa.volta(*controles)
    assert set(mesa.lacos.vivos) == {chave_do_aparelho(_marca(k)) for k in range(1, n + 1)}
    for k in range(1, n + 1):
        assert _motores(mesa, k) == _ABERTO, f"o motor do P{k} fechou: {_motores(mesa, k)}"


def test_trocar_de_modo_nao_fecha_o_motor_de_ninguem(mesa: _Mesa) -> None:  # noqa: F811
    """Nativo para Xbox e de volta: o laço segue aberto nos dois sentidos."""
    controles = _no_cabo_os_primeiros(mesa, 2)
    daemon = _daemon(nativo=True)
    mesa.sub._daemon = daemon
    mesa.volta(*controles)
    for nativo in (False, True):
        daemon._native_mode = nativo
        mesa.volta(*controles)
        assert _motores(mesa, 1) == _ABERTO
        assert _motores(mesa, 2) == _ABERTO, f"o P2 fechou com nativo={nativo}"


def test_o_servidor_mudo_segue_com_o_laco_do_cabo_no_ganho(
    mesa: _Mesa,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Com o ``pipewire-pulse`` mudo, o laço fica, e o pedido leva só rotas e ganhos."""
    controles = _no_cabo_os_primeiros(mesa, 2)
    mesa.sub._daemon = _daemon(nativo=True)
    mesa.volta(*controles)
    pedidos: list[set[str]] = []
    casar = mesa.sub._cabo.casar

    def _espiar(rotas: Any, ganhos: Any = None) -> None:
        pedidos.append(set(rotas))
        casar(rotas, ganhos)

    monkeypatch.setattr(mesa.sub._cabo, "casar", _espiar)
    monkeypatch.setattr(af, "_rodar", lambda _argv: None)
    mesa.volta(*controles)
    assert pedidos, "o laço do cabo não foi casado com o servidor mudo"
    assert pedidos[-1] == {_marca(1), _marca(2)}, "o servidor mudo derrubou um laço do cabo"
