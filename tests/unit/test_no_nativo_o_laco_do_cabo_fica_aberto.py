"""NO-MODO-XBOX-TUDO-FUNCIONA-01, parte 4: no Modo Nativo, o laço do cabo fica aberto.

A regressão que a conferência da A-HAPTICA-CHEGA-A-QUEM-ENTRA-DEPOIS-01 deixou
(28/09): desde aquela leva, a háptica do cabo passa por um laço do endpoint do
LUGAR até a placa do controle, e os motores do laço (os canais traseiros) abrem
só para quem joga, que é quem mexeu desde que o jogo abriu. No Modo Nativo o
co-op desmonta e o daemon só lê o físico do posto (o limite escrito em
``quem_mexe.py``): com dois ou mais no cabo, o portão fechava os motores dos
secundários, que ninguém podia ver mexer. Até 28/09 eles vibravam, porque o
jogo tocava direto na placa de cada um.

No Modo Nativo o dono dos motores é o JOGO, e o laço do cabo pergunta isso ao
mesmo dono que as três portas do rumble perguntam
(``rumble.modo_nativo_manda_nos_motores``), sem uma segunda cópia da pergunta.

O mundo é o da régua da A-HAPTICA-CHEGA (o servidor de som com memória, o
``/sys`` no ``tmp_path``, os laços de mentira que viram fluxo na placa), e o
daemon é o ``Daemon`` de verdade com o Modo Nativo ligado pelo mesmo atributo
que o ``set_native_mode`` escreve. Os ``uniq`` são da faixa sintética.

LIMITE DECLARADO: é fiação e conta. Se o jogo em Modo Nativo toca no endpoint
do lugar de cada controle, e a vibração na mão, são a prova no aparelho, e são
dela.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.subsystems import rumble
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.integrations.haptica_do_cabo import chave_do_lugar
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

#: Os quatro, na ordem dos lugares, e o aparelho USB de cada um no cabo.
_QUATRO = (_P1, _P2, _P3, _P4)
_APARELHOS = (("3-8", 28), ("3-7", 29), ("3-6", 30), ("3-5", 31))

#: O volume do fluxo do laço na placa: a frente (o alto-falante) sempre cheia,
#: os traseiros (os motores) pelo portão.
_ABERTO = ["100%", "100%", "100%", "100%"]
_FECHADO = ["100%", "100%", "0%", "0%"]


def _daemon(*, nativo: bool) -> Any:
    """O ``Daemon`` de verdade, com o Modo Nativo no atributo que o gesto escreve.

    O ``set_native_mode`` também grava a bandeira no disco e solta a emulação;
    aqui só importa a pergunta, e ela lê ``_native_mode``.
    """
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.testing import FakeController

    daemon = Daemon(controller=FakeController(), config=DaemonConfig())
    daemon._native_mode = nativo
    assert daemon.is_native_mode() is nativo
    return daemon


def _no_cabo_os_primeiros(m: _Mesa, n: int) -> list[_Controle]:
    """Os ``n`` primeiros no cabo, cada um no seu lugar, e o jogo tocando nos ``n``."""
    controles = [
        _no_cabo(m, uniq, lugar, *_APARELHOS[lugar - 1])
        for lugar, uniq in enumerate(_QUATRO[:n], 1)
    ]
    m.servidor.jogo_em.update(eh.nome_do_endpoint(lugar) for lugar in range(1, n + 1))
    return controles


def _motores(m: _Mesa, lugar: int) -> list[str]:
    return m.servidor.volumes[m.servidor.fluxo_do_laco(lugar)]


# ---------------------------------------------------------------------------
# A regressão: de dois a quatro no cabo, no Modo Nativo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n", [2, 3, 4], ids=["dois", "três", "quatro"])
@pytest.mark.parametrize(
    "mexeram", [(), (_P1,)], ids=["ninguem-marcado", "so-o-posto-marcado"]
)
def test_no_nativo_os_motores_de_todo_controle_no_cabo_abrem(
    mesa: _Mesa,  # noqa: F811
    n: int,
    mexeram: tuple[str, ...],
) -> None:
    """No Modo Nativo, o jogo manda nos motores de todos no cabo, P1 a P4.

    O daemon só lê o posto no Modo Nativo: os secundários nunca entram em quem
    mexeu. Com o posto marcado ou sem ninguém marcado, os ``n`` laços abrem os
    motores, como a placa abria até 28/09.

    MORDIDA: em ``AltoFalanteSubsystem._casar_o_cabo``, tire a pergunta ao
    ``rumble.modo_nativo_manda_nos_motores`` da conta de quem abre (o
    ``o_jogo_manda``) — os secundários voltam a fechar.
    """
    controles = _no_cabo_os_primeiros(mesa, n)
    mesa.jogando.update(mexeram)
    mesa.sub._daemon = _daemon(nativo=True)
    mesa.volta(*controles)
    assert set(mesa.lacos.vivos) == {chave_do_lugar(lugar) for lugar in range(1, n + 1)}
    for lugar in range(1, n + 1):
        assert _motores(mesa, lugar) == _ABERTO, (
            f"no Modo Nativo o motor do lugar {lugar} fechou: {_motores(mesa, lugar)}"
        )


def test_fora_do_nativo_a_escolha_b_segue_valendo(mesa: _Mesa) -> None:  # noqa: F811
    """A cura não abre tudo sempre: fora do Nativo, vibra só quem mexeu.

    O mesmo mundo, com o mesmo ``Daemon`` e o Modo Nativo desligado: é a
    escolha (b) dela para o jogo que espelha a vibração.

    MORDIDA: em ``_casar_o_cabo``, faça o ``o_jogo_manda`` valer sempre
    ``True`` — o P2 parado passa a vibrar.
    """
    controles = _no_cabo_os_primeiros(mesa, 2)
    mesa.jogando.add(_P1)
    mesa.sub._daemon = _daemon(nativo=False)
    mesa.volta(*controles)
    assert _motores(mesa, 1) == _ABERTO, "o P1 na mão não vibrou"
    assert _motores(mesa, 2) == _FECHADO, "o P2 parado vibrou fora do Modo Nativo"


def test_sair_do_nativo_fecha_de_novo_quem_nao_mexeu(mesa: _Mesa) -> None:  # noqa: F811
    """O portão segue o modo a cada volta, nos dois sentidos.

    Entra no Nativo: os dois abrem. Sai: o P2, que o daemon não viu mexer,
    fecha na volta seguinte. Volta ao Nativo: abre de novo.

    MORDIDA: guarde o ``o_jogo_manda`` da primeira volta num atributo e não o
    pergunte de novo — a saída do Nativo deixa o P2 aberto.
    """
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
    """Com o ``pipewire-pulse`` mudo, o laço fica, e no Nativo fica aberto.

    O ramo do servidor mudo guarda os laços de quem segue no cabo e decide o
    portão sem perguntar ao servidor. Ele pergunta ao mesmo dono do modo.

    MORDIDA: no ramo ``motores is None`` de ``_casar_o_cabo``, abra só
    ``dono.lower() in jogando`` (sem o ``o_jogo_manda``) — o P2 vai ao
    ``casar`` fechado.
    """
    controles = _no_cabo_os_primeiros(mesa, 2)
    mesa.jogando.add(_P1)
    mesa.sub._daemon = _daemon(nativo=True)
    mesa.volta(*controles)
    pedidos: list[tuple[set[int], set[int]]] = []
    casar = mesa.sub._cabo.casar

    def _espiar(rotas: Any, abertos: Any) -> None:
        pedidos.append((set(rotas), set(abertos)))
        casar(rotas, abertos)

    monkeypatch.setattr(mesa.sub._cabo, "casar", _espiar)
    monkeypatch.setattr(af, "_rodar", lambda _argv: None)
    mesa.volta(*controles)
    assert pedidos, "o laço do cabo não foi casado com o servidor mudo"
    rotas, abertos = pedidos[-1]
    assert rotas == {1, 2}, "o servidor mudo derrubou um laço de quem segue no cabo"
    assert abertos == {1, 2}, f"no Modo Nativo com o servidor mudo abriu só {sorted(abertos)}"


# ---------------------------------------------------------------------------
# Um dono só para a pergunta
# ---------------------------------------------------------------------------


def test_o_laco_pergunta_ao_dono_do_rumble(
    mesa: _Mesa,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quem responde «o jogo manda nos motores» é o ``rumble``, e só ele.

    Com o daemon FORA do Nativo e o dono respondendo que o jogo manda, o laço
    abre: é a resposta do dono que decide, e não uma segunda cópia da pergunta
    escrita no ``alto_falante``.

    MORDIDA: no ``_casar_o_cabo``, troque a chamada por
    ``bool(getattr(self._daemon, "is_native_mode", lambda: False)())`` — a
    cópia não ouve o dono, e o P2 fica fechado.
    """
    controles = _no_cabo_os_primeiros(mesa, 2)
    mesa.jogando.add(_P1)
    mesa.sub._daemon = _daemon(nativo=False)
    monkeypatch.setattr(rumble, "modo_nativo_manda_nos_motores", lambda _daemon: True)
    mesa.volta(*controles)
    assert _motores(mesa, 2) == _ABERTO, "o laço do cabo não perguntou ao dono do rumble"


def test_o_duble_que_responde_tudo_nao_abre_os_motores(mesa: _Mesa) -> None:  # noqa: F811
    """Um ``MagicMock`` responde verdadeiro a tudo, e não é Modo Nativo.

    É o contrato do dono (``is True``, e não ``bool(...)``): um dublê não decide
    o destino da vibração dela. Com o daemon de mentira, vale a escolha (b).

    MORDIDA: a mesma da régua anterior — a cópia com ``bool(...)`` lê o
    ``MagicMock`` como Nativo, e o P2 parado abre.
    """
    controles = _no_cabo_os_primeiros(mesa, 2)
    mesa.jogando.add(_P1)
    mesa.sub._daemon = MagicMock()
    mesa.volta(*controles)
    assert _motores(mesa, 2) == _FECHADO, "o dublê que responde tudo abriu o motor do P2"
    assert _motores(mesa, 1) == _ABERTO
