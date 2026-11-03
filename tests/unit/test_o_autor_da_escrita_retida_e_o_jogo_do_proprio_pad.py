"""O autor da escrita retida é o jogo do próprio pad.

O-AUTOR-DA-ESCRITA-RETIDA-E-O-JOGO-DO-PROPRIO-PAD-01.

Com dois jogos abertos, cada um no pad de um controle, a primeira pintura de cada um chega ao
controle dele quando o portão abre. A pergunta «quem escreveu» é feita por pad, numa varredura só
por rajada, no fio de fundo do backend: a escrita do jogo nunca espera o ``/proc``. A abertura usa a
resposta por pad do tique e não varre. O ``/proc`` de mentira é o de
`test_a_primeira_pintura_do_jogo_chega_ao_controle`, com um nó por pad.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.led_control import player_led_pattern
from hefesto_dualsense4unix.daemon.lifecycle import _os_pads_por_alvo
from tests.unit.test_a_primeira_pintura_do_jogo_chega_ao_controle import (
    MACS,
    PID_DO_JOGO,
    _abre_o_portao,
    _escreve,
    _espera_os_autores,
    _mesa,
    _numero,
    _o_que_vale,
    _pad,
    _Proc,
)

PID_DO_OUTRO = 300
COR_DO_JOGO = (0, 200, 40)
COR_DO_OUTRO = (10, 20, 230)

COMBINACOES = [
    (jogadores, via, caminho)
    for jogadores in (2, 3, 4)
    for via in ("cabo", "radio")
    for caminho in ("uhid", "gadget")
]

UM_A_QUATRO = [
    (player, via, caminho)
    for player in (1, 2, 3, 4)
    for via in ("cabo", "radio")
    for caminho in ("uhid", "gadget")
]


class _Contador:
    """O leitor de mentira: conta as varreduras e guarda o fio de cada uma."""

    def __init__(self, leitor: Any, trava: threading.Event | None = None) -> None:
        self.leitor = leitor
        self.trava = trava
        self.fios: list[threading.Thread] = []

    def __call__(self) -> Any:
        self.fios.append(threading.current_thread())
        if self.trava is not None and len(self.fios) == 1:
            assert self.trava.wait(10.0), "a trava do leitor de mentira não se soltou"
        return self.leitor()


def _dois_jogos(tmp_path: Path, via: str) -> tuple[_Proc, Any, Any, Any]:
    proc = _Proc(tmp_path)
    proc._criar(PID_DO_OUTRO, "Outro.exe", "Z:\\outro\\Outro.exe")
    ctl, nos, daemon = _mesa(via, proc)
    return proc, ctl, nos, daemon


def _jogo_de(player: int) -> int:
    return PID_DO_JOGO if player % 2 else PID_DO_OUTRO


def _cor_de(player: int) -> tuple[int, int, int]:
    return COR_DO_JOGO if player % 2 else COR_DO_OUTRO


@pytest.mark.parametrize("quem_abre_primeiro", [PID_DO_JOGO, PID_DO_OUTRO])
@pytest.mark.parametrize(("jogadores", "via", "caminho"), COMBINACOES)
def test_dois_jogos_cada_um_pinta_o_proprio_controle(
    jogadores: int, via: str, caminho: str, quem_abre_primeiro: int, tmp_path: Path
) -> None:
    """MORDIDA: devolver o leitor de todos os pads e o jogo de um dos controles perde a pintura.

    Os dois sentidos de abertura entram porque a ordem do ``/proc`` de mentira é a do disco.
    """
    proc, ctl, nos, daemon = _dois_jogos(tmp_path, via)
    pads = {n: _pad(daemon, n, caminho) for n in range(1, jogadores + 1)}
    ordem = [quem_abre_primeiro, PID_DO_OUTRO + PID_DO_JOGO - quem_abre_primeiro]
    for pid in ordem:
        seus = tuple(n for n in pads if _jogo_de(n) == pid)
        proc.segura(pid, True, players=seus)
        for n in seus:
            _escreve(pads[n], caminho, _numero(n), _cor_de(n))
        _espera_os_autores(ctl)

    _abre_o_portao(ctl, daemon)

    for n in pads:
        assert _o_que_vale(ctl, n) == (player_led_pattern(_numero(n)), _cor_de(n)), (
            f"o P{n} não recebeu o número e a cor do jogo que segura o pad dele"
        )
        assert _cor_de(n) in nos[n].rgb_calls


@pytest.mark.parametrize("via", ["cabo", "radio"])
@pytest.mark.parametrize("caminho", ["uhid", "gadget"])
def test_a_rajada_nos_dois_pads_varre_uma_vez_e_no_fio_de_fundo(
    via: str, caminho: str, tmp_path: Path
) -> None:
    """MORDIDA: devolver a varredura na escrita retida e a conta passa de zero no fio da escrita."""
    proc, ctl, _nos, daemon = _dois_jogos(tmp_path, via)
    proc.segura(PID_DO_JOGO, True, players=(1,))
    proc.segura(PID_DO_OUTRO, True, players=(2,))
    contador = _Contador(daemon.leitor)
    ctl.set_quem_segura_o_pad(contador)
    ctl._espera_da_rajada_s = 0.5
    pads = {n: _pad(daemon, n, caminho) for n in (1, 2)}

    for i in range(10):
        n = 1 + i % 2
        cor = (0, 200, i) if n == 1 else (i, 20, 230)
        _escreve(pads[n], caminho, _numero(n), cor)
        assert contador.fios == [], f"a escrita {i} varreu o /proc no fio de quem escreveu"
    _espera_os_autores(ctl)

    assert len(contador.fios) == 1, "a rajada de dez cores custou mais de uma varredura"
    assert contador.fios[0] is not threading.current_thread()
    _abre_o_portao(ctl, daemon)
    assert _o_que_vale(ctl, 1) == (player_led_pattern(_numero(1)), (0, 200, 8))
    assert _o_que_vale(ctl, 2) == (player_led_pattern(_numero(2)), (9, 20, 230))


@pytest.mark.parametrize(("player", "via", "caminho"), UM_A_QUATRO)
def test_a_abertura_com_a_escrita_sem_autor_usa_a_resposta_do_tique(
    player: int, via: str, caminho: str, tmp_path: Path
) -> None:
    """MORDIDAS: tirar a resolução das pendentes da abertura, ou fazer a abertura varrer de novo.

    O fio de fundo fica preso no leitor: a escrita chega à abertura ainda sem autor.
    """
    proc, ctl, nos, daemon = _dois_jogos(tmp_path, via)
    proc.segura(PID_DO_JOGO, True)
    trava = threading.Event()
    contador = _Contador(daemon.leitor, trava)
    ctl.set_quem_segura_o_pad(contador)
    ctl._espera_da_rajada_s = 0.0
    pad = _pad(daemon, player, caminho)
    try:
        _escreve(pad, caminho, _numero(player), COR_DO_JOGO)
        prazo = time.monotonic() + 5.0
        while not contador.fios:
            assert time.monotonic() < prazo, "o fio de fundo não chegou ao leitor"
            time.sleep(0.005)
        assert ctl._retido_sem_autor, "a escrita já tinha autor antes da abertura"

        _abre_o_portao(ctl, daemon)

        assert all(fio is not threading.current_thread() for fio in contador.fios), (
            "a abertura varreu o /proc em vez de usar a resposta do tique"
        )
        assert _o_que_vale(ctl, player) == (player_led_pattern(_numero(player)), COR_DO_JOGO)
        assert COR_DO_JOGO in nos[player].rgb_calls
    finally:
        trava.set()
    _espera_os_autores(ctl)
    assert _o_que_vale(ctl, player) == (player_led_pattern(_numero(player)), COR_DO_JOGO)


def test_um_jogo_com_dois_pads_e_o_autor_dos_dois(tmp_path: Path) -> None:
    """MORDIDA: a varredura que para no primeiro nó do processo e o segundo pad fica sem jogo."""
    proc = _Proc(tmp_path)
    proc.segura(PID_DO_JOGO, True, players=(1, 2))
    _ctl, _nos, daemon = _mesa("cabo", proc)

    jogos = daemon.leitor()

    assert {chave: segurador.pid for chave, segurador in jogos.items()} == {
        MACS[1]: PID_DO_JOGO,
        MACS[2]: PID_DO_JOGO,
    }


def test_cada_pad_virtual_responde_pelo_fisico_do_seu_jogador() -> None:
    """MORDIDA: chavear o co-op pela posição e a escrita do P2 nunca acha o jogo do pad dele."""
    p1, p2, p3, sem_dono = (SimpleNamespace(nome=f"pad{n}") for n in range(4))
    daemon = SimpleNamespace(
        controller=SimpleNamespace(primary_uniq=MACS[1]),
        _gamepad_device=p1,
        _coop_manager=SimpleNamespace(
            _players={
                "b": SimpleNamespace(identity=MACS[2], vpad=p2),
                "c": SimpleNamespace(identity=MACS[3], vpad=p3),
                "d": SimpleNamespace(identity=MACS[4], vpad=None),
                "e": SimpleNamespace(vpad=sem_dono),
            }
        ),
    )

    pads = _os_pads_por_alvo(daemon)

    assert {chave: pads[chave] for chave in (MACS[1], MACS[2], MACS[3])} == {
        MACS[1]: p1,
        MACS[2]: p2,
        MACS[3]: p3,
    }
    assert MACS[4] not in pads
    assert list(pads.values()).count(sem_dono) == 1
    jogo = SimpleNamespace(pid=PID_DO_JOGO, nome="Jogo.exe")
    assert bp.PyDualSenseController()._jogos_por_alvo({chave: jogo for chave in pads}) == {
        MACS[n].replace(":", "").lower(): (PID_DO_JOGO, "Jogo.exe") for n in (1, 2, 3)
    }
