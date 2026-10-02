"""WRAPPER-EM-TODOS-01: o IGNORE do SDL exige COBERTURA, não tipo de vpad.

O `SDL_GAMECONTROLLER_IGNORE_DEVICES` esconde o DualSense físico do SDL **por
VID/PID** — um par cravado (`_IGNORE_VALUE`), que some para TODOS os controles
daquele par de uma vez. Quem devolve cada um ao jogo é o vpad correspondente.

Até 03/08/2026 a decisão era pelo TIPO (`all(b == "uhid")`) e nunca pela
CONTAGEM, e o `_snapshot` só listava vpads que EXISTEM: um jogador de co-op
pendente (aguardando o `EVIOCGRAB`, com `vpad is None`) não entrava na lista, e
o `all(...)` passava trivialmente sobre uma lista incompleta.

O caso que a derrubava é exatamente o que o `EBUSY` de 02/08 produzia o tempo
todo: **2 DualSense físicos e 1 vpad vivo** — o IGNORE escondia os dois e só um
voltava. A mesa caía de dois controles para um, e o que sumia era um DualSense.

A doutrina que estes testes protegem está escrita em três lugares
(`daemon/launch_env.py`, `assets/hefesto-launch.sh`, `install.sh`):

    o pior caso é o controle DUPLICADO — nunca um jogo sem controle.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.daemon.launch_env import compose_env

IGNORE = "SDL_GAMECONTROLLER_IGNORE_DEVICES"
DISABLE = "PROTON_DISABLE_HIDRAW"


def _env(backends: list[str], fisicos: int, flavor: str = "dualsense") -> dict[str, str]:
    return compose_env(
        native_mode=False,
        emulation_enabled=True,
        flavor=flavor,
        backends=backends,
        fisicos=fisicos,
    )


class TestCoberturaDecideOIgnore:
    """A regra: um vpad vivo por DualSense físico, ou o IGNORE não sai."""

    @pytest.mark.parametrize(
        ("backends", "fisicos"),
        [
            (["uhid"], 1),
            (["uhid", "uhid"], 2),
            (["uhid", "uhid", "uhid"], 3),
        ],
    )
    def test_com_cobertura_total_o_ignore_sai(
        self, backends: list[str], fisicos: int
    ) -> None:
        assert IGNORE in _env(backends, fisicos)

    @pytest.mark.parametrize(
        ("backends", "fisicos", "caso"),
        [
            (["uhid"], 2, "o EBUSY de 02/08: um jogador aguardando grab"),
            (["uhid"], 3, "dois pendentes"),
            (["uhid", "uhid"], 4, "co-op de quatro com metade de pé"),
        ],
    )
    def test_sem_cobertura_o_ignore_nao_sai(
        self, backends: list[str], fisicos: int, caso: str
    ) -> None:
        """Mordida: devolver a decisão a `all(b == "uhid")` faz reprovar."""
        assert IGNORE not in _env(backends, fisicos), caso

    def test_sem_saber_quantos_fisicos_o_comportamento_nao_muda(self) -> None:
        """`fisicos=0` é "NÃO SEI", e aí o comportamento HISTÓRICO prevalece."""
        assert IGNORE in _env(["uhid"], 0)


class TestOQueNaoMuda:
    """A cura não pode virar "o dedup parou de funcionar"."""

    @pytest.mark.parametrize("fisicos", [0, 1, 2, 5])
    def test_o_disable_hidraw_sai_sempre(self, fisicos: int) -> None:
        """Ele impede o winebus de entregar o hidraw do físico e NÃO esconde"""
        assert DISABLE in _env(["uhid"], fisicos)

    def test_a_mascara_xbox_segue_a_mesma_regra(self) -> None:
        """Xbox tem caminho próprio no `compose_env`, e a cobertura vale nele"""
        assert IGNORE in _env(["uinput"], 1, flavor="xbox")
        assert IGNORE in _env(["uinput"], 0, flavor="xbox")
        assert IGNORE not in _env(["uinput"], 2, flavor="xbox")

    def test_vpad_degradado_continua_sem_ignore(self) -> None:
        """Um vpad em uinput com máscara dualsense nunca teve IGNORE — a SDL"""
        assert IGNORE in _env(["uinput"], 1)
        assert IGNORE in _env(["uhid", "uinput"], 2)
        assert IGNORE not in _env(["uinput"], 2)

    def test_modo_nativo_nao_esconde_nada(self) -> None:
        env = compose_env(
            native_mode=True,
            emulation_enabled=True,
            flavor="dualsense",
            backends=["uhid"],
            fisicos=1,
        )
        assert IGNORE not in env
        assert DISABLE not in env
