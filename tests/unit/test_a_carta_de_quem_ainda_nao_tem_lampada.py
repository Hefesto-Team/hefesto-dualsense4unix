"""OS-QUATRO-EM-HARMONIA-01, item 2: quem entra sem lâmpada não mexe na carta de quem tem.

Medido em 14/10/2026 (10h42m08,997 a 10h42m11,680): três controles entraram com
o jogo aberto, e o primário trocou três vezes. A carta da mesa caía INTEIRA para
a fila gravada, de outra sessão, enquanto um recém-chegado não acendia número.
O P1 sentado na lâmpada 1 passava a ser o 3º da fila, e voltava a ser o 1 no
tique seguinte, quando a lâmpada do novo acendia.

A régua vale para 1 a 4 controles, cabo e rádio misturados, em qualquer ordem
de entrada: a carta é a lâmpada, e a fila só decide entre quem não tem lâmpada.
"""

from __future__ import annotations

import itertools
from typing import Any

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

UM, DOIS, TRES, QUATRO = (f"aabbcc0000{n:02x}" for n in range(1, 5))


class _Mesa:
    """O provider da camada automática: lâmpadas acesas e a fila gravada."""

    def __init__(self, lampadas: dict[str, int], fila: dict[str, int]) -> None:
        self.lampadas = lampadas
        self.fila = fila

    def __call__(self, _uniq: str) -> Any:
        return None

    def numero_do_slot(self, uniq: str) -> int | None:
        return self.lampadas.get(uniq)

    def posto_na_fila(self, uniq: str) -> int | None:
        return self.fila.get(uniq)


def _backend(chaves: list[str], mesa: _Mesa) -> PyDualSenseController:
    ctl = PyDualSenseController()
    ctl._auto_output_provider = mesa
    for chave in chaves:
        ctl._handles[chave] = object()
    return ctl


def _chave(uniq: str) -> str:
    return uniq


@pytest.mark.parametrize("ordem", list(itertools.permutations([UM, DOIS, TRES, QUATRO])))
def test_o_recem_chegado_sem_lampada_nao_derruba_o_p1(ordem: tuple[str, ...]) -> None:
    """A lâmpada 1 fica no posto, chegue quem chegar, na ordem que for.

    A fila de outra sessão diz o contrário da lâmpada (o 1 aceso é o 4º da fila).
    MORDIDA: devolva o «tudo ou nada» em ``_cartas_locked`` (lâmpada só quando
    todos têm) e o P1 sentado passa para o 1º da fila velha.
    """
    fila_velha = {UM: 4, DOIS: 3, TRES: 2, QUATRO: 1}
    acesas: dict[str, int] = {}
    mesa = _Mesa(acesas, fila_velha)
    chaves: list[str] = []
    ctl = _backend(chaves, mesa)
    sentado: str | None = None
    for n, uniq in enumerate(ordem, start=1):
        chave = _chave(uniq)
        ctl._handles[chave] = object()
        if sentado is None:
            sentado = chave
            acesas[uniq] = 1
            continue
        with ctl._io_lock:
            assert ctl._a_carta_menor_locked(sentado) == sentado, (
                f"o {n}º a entrar, ainda sem lâmpada, derrubou o P1"
            )
        acesas[uniq] = n
        with ctl._io_lock:
            assert ctl._a_carta_menor_locked(sentado) == sentado


def test_quem_nao_tem_lampada_vem_depois_na_ordem_da_fila() -> None:
    mesa = _Mesa({UM: 1, DOIS: 2}, {TRES: 7, QUATRO: 5, UM: 9})
    chaves = [_chave(u) for u in (UM, DOIS, TRES, QUATRO)]
    ctl = _backend(chaves, mesa)
    with ctl._io_lock:
        cartas = ctl._cartas_locked(chaves)
    assert cartas == {chaves[0]: 1, chaves[1]: 2, chaves[3]: 3, chaves[2]: 4}


def test_sem_lampada_nenhuma_a_fila_decide() -> None:
    """O boot: ninguém acendeu ainda, e a fila gravada é a única carta."""
    mesa = _Mesa({}, {UM: 2, DOIS: 1})
    chaves = [_chave(UM), _chave(DOIS), _chave(TRES)]
    ctl = _backend(chaves, mesa)
    with ctl._io_lock:
        assert ctl._cartas_locked(chaves) == {chaves[0]: 2, chaves[1]: 1, chaves[2]: 3}


def test_a_lampada_menor_que_chega_leva_o_posto() -> None:
    """A troca que ela pede na tela continua valendo: a lâmpada 1 nova senta."""
    mesa = _Mesa({UM: 2, DOIS: 1}, {})
    chaves = [_chave(UM), _chave(DOIS)]
    ctl = _backend(chaves, mesa)
    with ctl._io_lock:
        assert ctl._a_carta_menor_locked(chaves[0]) == chaves[1]


from hefesto_dualsense4unix.daemon.subsystems.identity import (
    ControllerIdentityRegistry,
    make_auto_output_provider,
    prazo_do_lugar_guardado,
)
from tests.unit.test_o_jogo_espera_a_carta_do_lugar_guardado import (
    Relogio,
    config_isolado,  # noqa: F401
)

_KEY = {
    u: ":".join(u[i : i + 2] for i in range(0, 12, 2)).upper() for u in (UM, DOIS, TRES, QUATRO)
}


def _sessao_anterior(fila: tuple[str, ...]) -> None:
    """A fila de outra sessão no disco do lar de mentira, na ordem de ``fila``."""
    ControllerIdentityRegistry(clock=Relogio()).sync_connected(list(fila))


def _o_backend_do_registro(
    relogio: Relogio,
) -> tuple[PyDualSenseController, ControllerIdentityRegistry]:
    reg = ControllerIdentityRegistry(clock=relogio)
    reg.load()
    ctl = PyDualSenseController()
    ctl.set_auto_output_provider(make_auto_output_provider(reg))
    return ctl, reg


def _cartas(ctl: PyDualSenseController) -> dict[str, int]:
    with ctl._io_lock:
        return {
            k.replace(":", "").lower(): n for k, n in ctl._cartas_locked(list(ctl._handles)).items()
        }


def _sentar(ctl: PyDualSenseController, uniq: str) -> None:
    ctl._handles[_KEY[uniq]] = object()


def _levantar(ctl: PyDualSenseController, uniq: str) -> None:
    del ctl._handles[_KEY[uniq]]


def _no_tique(ctl: PyDualSenseController, reg: ControllerIdentityRegistry) -> None:
    """O ``sync_connected`` do tique lento, com quem o backend tem na mão."""
    reg.sync_connected([k.replace(":", "").lower() for k in ctl._handles])


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize("quantos", [2, 3, 4])
def test_quem_volta_depois_do_prazo_e_a_carta_dele_ja_no_hotplug(quantos: int) -> None:
    """A carta 1 sai, o prazo passa, ela volta: a carta não muda quando a lâmpada acende.

    MORDIDA: tire a ``_mesa_que_vai_sentar`` de ``_cartas_locked`` e, no
    hotplug, a carta põe quem voltou depois das acesas (o 2 vira o 1), e um
    tique depois inverte.

    Prova da D-1710-A-CARTA-SEM-LAMPADA-E-A-MESA-QUE-VAI-SENTAR.
    """
    relogio = Relogio()
    mesa = (UM, DOIS, TRES, QUATRO)[:quantos]
    _sessao_anterior(mesa)
    ctl, reg = _o_backend_do_registro(relogio)
    for uniq in mesa:
        _sentar(ctl, uniq)
    _no_tique(ctl, reg)
    cheia = {u: n for n, u in enumerate(mesa, start=1)}
    assert _cartas(ctl) == cheia, "premissa: a mesa nasce na ordem da fila"

    _levantar(ctl, UM)
    _no_tique(ctl, reg)
    relogio.avancar(prazo_do_lugar_guardado() + 1.0)
    _no_tique(ctl, reg)
    assert _cartas(ctl) == {u: n for n, u in enumerate(mesa[1:], start=1)}, (
        "premissa: passado o prazo, quem ficou anda"
    )

    relogio.avancar(2.0)
    _sentar(ctl, UM)
    no_hotplug = _cartas(ctl)
    _no_tique(ctl, reg)
    assert no_hotplug == _cartas(ctl) == cheia, (
        f"a carta da volta mudou quando a lâmpada acendeu: {no_hotplug} -> {_cartas(ctl)}"
    )
    with ctl._io_lock:
        assert ctl._a_carta_menor_locked(_KEY[DOIS]) == _KEY[UM]


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize("ordem", list(itertools.permutations([UM, DOIS, TRES, QUATRO])))
def test_quem_estreia_na_sessao_vem_depois_mesmo_com_a_fila_velha_contra(
    ordem: tuple[str, ...],
) -> None:
    """O caso de 14/10 ao registro de verdade: a fila velha diz o contrário da lâmpada.

    O sentado é o último da fila de outra sessão, e cada um que entra tem lugar
    melhor que todos os da mesa. A lâmpada 1 fica, no hotplug e no tique.
    """
    relogio = Relogio()
    _sessao_anterior(tuple(reversed(ordem)))
    ctl, reg = _o_backend_do_registro(relogio)
    sentado = ordem[0]
    _sentar(ctl, sentado)
    _no_tique(ctl, reg)
    for n, uniq in enumerate(ordem[1:], start=2):
        relogio.avancar(2.0)
        _sentar(ctl, uniq)
        no_hotplug = _cartas(ctl)
        _no_tique(ctl, reg)
        assert no_hotplug == _cartas(ctl), (
            f"o {n}º a entrar trocou a carta quando a lâmpada acendeu: "
            f"{no_hotplug} -> {_cartas(ctl)}"
        )
        assert no_hotplug[sentado] == 1 and no_hotplug[uniq] == n
        with ctl._io_lock:
            assert ctl._a_carta_menor_locked(_KEY[sentado]) == _KEY[sentado]


@pytest.mark.usefixtures("config_isolado")
@pytest.mark.parametrize("jogo", [False, True], ids=["sem-jogo", "com-jogo"])
@pytest.mark.parametrize("volta", [False, True], ids=["gente-nova", "o-dono-do-lugar"])
def test_a_mesa_que_vai_sentar_e_a_do_tique_seguinte(jogo: bool, volta: bool) -> None:
    """Com um lugar guardado no prazo: quem chega solta ou não, e a carta acerta.

    Gente nova solta o lugar guardado sem jogo e não o solta com o jogo
    segurando (D-3009); o dono do lugar o retoma. A carta do hotplug é a mesa
    depois do tique. A gente nova é o ``QUATRO``, com lugar na fila de outra
    sessão e sem lâmpada no hotplug, como quem volta.

    Prova da D-1710-A-CARTA-SEM-LAMPADA-E-A-MESA-QUE-VAI-SENTAR.
    """
    relogio = Relogio()
    _sessao_anterior((UM, DOIS, TRES, QUATRO))
    ctl, reg = _o_backend_do_registro(relogio)
    for uniq in (UM, DOIS, TRES):
        _sentar(ctl, uniq)
    _no_tique(ctl, reg)
    reg.segurar_os_prazos(jogo)
    _levantar(ctl, UM)
    _no_tique(ctl, reg)
    relogio.avancar(2.0)
    chega = UM if volta else QUATRO
    _sentar(ctl, chega)
    previsto = _cartas(ctl)
    _no_tique(ctl, reg)
    assert previsto == reg.numeros_da_mesa() == _cartas(ctl)
