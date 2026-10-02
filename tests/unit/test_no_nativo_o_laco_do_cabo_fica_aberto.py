"""NO-MODO-XBOX-TUDO-FUNCIONA-01, parte 4: no Modo Nativo, o laço do cabo fica aberto."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.subsystems import rumble
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.integrations.haptica_do_cabo import chave_do_aparelho
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

_ABERTO = ["100%", "100%", "100%", "100%"]
_FECHADO = ["100%", "100%", "0%", "0%"]


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
@pytest.mark.parametrize(
    "mexeram", [(), (_P1,)], ids=["ninguem-marcado", "so-o-posto-marcado"]
)
def test_no_nativo_os_motores_de_todo_controle_no_cabo_abrem(
    mesa: _Mesa,  # noqa: F811
    n: int,
    mexeram: tuple[str, ...],
) -> None:
    """No Modo Nativo, o jogo manda nos motores de todos no cabo, P1 a P4."""
    controles = _no_cabo_os_primeiros(mesa, n)
    mesa.jogando.update(mexeram)
    mesa.sub._daemon = _daemon(nativo=True)
    mesa.volta(*controles)
    assert set(mesa.lacos.vivos) == {chave_do_aparelho(_marca(k)) for k in range(1, n + 1)}
    for k in range(1, n + 1):
        assert _motores(mesa, k) == _ABERTO, (
            f"no Modo Nativo o motor do P{k} fechou: {_motores(mesa, k)}"
        )


def test_fora_do_nativo_a_escolha_b_segue_valendo(mesa: _Mesa) -> None:  # noqa: F811
    """A cura não abre tudo sempre: fora do Nativo, vibra só quem mexeu."""
    controles = _no_cabo_os_primeiros(mesa, 2)
    mesa.jogando.add(_P1)
    mesa.sub._daemon = _daemon(nativo=False)
    mesa.volta(*controles)
    assert _motores(mesa, 1) == _ABERTO, "o P1 na mão não vibrou"
    assert _motores(mesa, 2) == _FECHADO, "o P2 parado vibrou fora do Modo Nativo"


def test_sair_do_nativo_fecha_de_novo_quem_nao_mexeu(mesa: _Mesa) -> None:  # noqa: F811
    """O portão segue o modo a cada volta, nos dois sentidos."""
    controles = _no_cabo_os_primeiros(mesa, 2)
    mesa.jogando.add(_P1)
    daemon = _daemon(nativo=True)
    mesa.sub._daemon = daemon
    mesa.volta(*controles)
    assert _motores(mesa, 2) == _ABERTO
    daemon._native_mode = False
    mesa.volta(*controles)
    assert _motores(mesa, 2) == _FECHADO, "saiu do Modo Nativo e o P2 parado seguiu vibrando"
    assert _motores(mesa, 1) == _ABERTO
    daemon._native_mode = True
    mesa.volta(*controles)
    assert _motores(mesa, 2) == _ABERTO, "voltou ao Modo Nativo e o P2 não reabriu"


def test_o_servidor_mudo_no_nativo_segue_com_os_motores_abertos(
    mesa: _Mesa,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Com o ``pipewire-pulse`` mudo, o laço fica, e no Nativo fica aberto."""
    controles = _no_cabo_os_primeiros(mesa, 2)
    mesa.jogando.add(_P1)
    mesa.sub._daemon = _daemon(nativo=True)
    mesa.volta(*controles)
    pedidos: list[tuple[set[str], set[str]]] = []
    casar = mesa.sub._cabo.casar

    def _espiar(rotas: Any, abertos: Any) -> None:
        pedidos.append((set(rotas), set(abertos)))
        casar(rotas, abertos)

    monkeypatch.setattr(mesa.sub._cabo, "casar", _espiar)
    monkeypatch.setattr(af, "_rodar", lambda _argv: None)
    mesa.volta(*controles)
    assert pedidos, "o laço do cabo não foi casado com o servidor mudo"
    rotas, abertos = pedidos[-1]
    assert rotas == {_marca(1), _marca(2)}, "o servidor mudo derrubou um laço de quem segue no cabo"
    assert abertos == {_marca(1), _marca(2)}, (
        f"no Modo Nativo com o servidor mudo abriu só {sorted(abertos)}"
    )


def test_o_laco_pergunta_ao_dono_do_rumble(
    mesa: _Mesa,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quem responde «o jogo manda nos motores» é o ``rumble``, e só ele."""
    controles = _no_cabo_os_primeiros(mesa, 2)
    mesa.jogando.add(_P1)
    mesa.sub._daemon = _daemon(nativo=False)
    monkeypatch.setattr(rumble, "modo_nativo_manda_nos_motores", lambda _daemon: True)
    mesa.volta(*controles)
    assert _motores(mesa, 2) == _ABERTO, "o laço do cabo não perguntou ao dono do rumble"


def test_o_duble_que_responde_tudo_nao_abre_os_motores(mesa: _Mesa) -> None:  # noqa: F811
    """Um ``MagicMock`` responde verdadeiro a tudo, e não é Modo Nativo."""
    controles = _no_cabo_os_primeiros(mesa, 2)
    mesa.jogando.add(_P1)
    mesa.sub._daemon = MagicMock()
    mesa.volta(*controles)
    assert _motores(mesa, 2) == _FECHADO, "o dublê que responde tudo abriu o motor do P2"
    assert _motores(mesa, 1) == _ABERTO
