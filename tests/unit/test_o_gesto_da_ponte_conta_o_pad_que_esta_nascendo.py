"""O-GESTO-DA-PONTE-CONTA-O-PAD-QUE-ESTA-NASCENDO-01 — o PS + R3 espera o pad que pediu.

Medido em 21/11/2026 (Avatar Legends, dois DualSense): das dez trocas do gesto, as sete que
subiam para um modo de controle deram `ponte_nao_subiu` e o aviso de falha no controle,
porque o veredito lia `ponte_atual` logo depois de pedir o pad ao fio, e o P1 em voo ainda
não existia.

O ensaio é o do fio de nascimento (`Daemon` real, `CoopManager` real, broker de mentira que
o tique solta), com o callback REAL do gesto no mesmo laço do tique. Dublados só a lightbar,
o diário e a escada do jogo (quem devolve o degrau).

Morde, e são duas curas independentes:

* o veredito voltando a ler na hora: o primeiro caso reprova por `ponte_nao_subiu`;
* `ponte_atual` voltando a ignorar o P1 em voo: o caso dos dois apertos reprova pelo «de onde».
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.numeros_da_sony import ROUPA_PADRAO
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.integrations import ponte_tentativa
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.utils import xdg_paths
from tests.unit.test_o_p1_que_nasce_fora_do_tique_nasce_no_fio_de_nascimento import (
    _GUARDA_S,
    _PEDIDO,
    _TIQUE_S,
    _no_laco,
    _Pad,
    _soltar,
    mesa,
)

__all__ = ["mesa"]

_DEGRAU = "degrau-de-mentira"


class _Diario:
    """O diário de mentira do gesto: guarda cada evento com os campos que ele disse."""

    def __init__(self) -> None:
        self.linhas: list[tuple[str, str, dict[str, Any]]] = []

    def _anotar(self, nivel: str) -> Callable[..., None]:
        def _dizer(evento: str, **campos: Any) -> None:
            self.linhas.append((nivel, evento, campos))

        return _dizer

    def __getattr__(self, nivel: str) -> Callable[..., None]:
        if nivel.startswith("_") or nivel == "linhas":
            raise AttributeError(nivel)
        return self._anotar(nivel)

    def dos(self, evento: str) -> list[dict[str, Any]]:
        return [campos for _n, e, campos in self.linhas if e == evento]


@pytest.fixture
def ensaio(
    mesa: SimpleNamespace, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> SimpleNamespace:
    """A mesa do fio com o P1 num pad DualSense, o diário, a lightbar e a escada de mentira."""
    monkeypatch.setattr(xdg_paths, "config_dir", lambda ensure=False: tmp_path)
    diario = _Diario()
    monkeypatch.setattr(hotkey, "logger", diario)
    luzes: list[list[Any]] = []

    async def _luz(daemon: Any, cores: Any) -> None:
        luzes.append(list(cores))

    monkeypatch.setattr(hotkey, "_sinalizar_lightbar", _luz)
    monkeypatch.setattr(hotkey, "_appid_do_jogo_do_wrapper", lambda: None)
    escada = SimpleNamespace(passo=None, subiu=[], de_pe=[])
    monkeypatch.setattr(
        ponte_tentativa, "avancar_por_gesto", lambda daemon, jogo_vivo: escada.passo)
    monkeypatch.setattr(
        ponte_tentativa, "degrau_subiu", lambda daemon, degrau: escada.subiu.append(degrau))
    monkeypatch.setattr(
        ponte_tentativa, "gesto_deixou_de_pe",
        lambda daemon, **campos: escada.de_pe.append(campos))
    velho = _Pad(None, "dualsense", vp.CAMINHO_DUALSENSE, ROUPA_PADRAO)
    mesa.daemon._gamepad_device = velho
    mesa.daemon.config.gamepad_emulation_enabled = True
    return SimpleNamespace(m=mesa, diario=diario, luzes=luzes, escada=escada, velho=velho)


def _o_p1_novo(b: SimpleNamespace) -> Any:
    novo = b.m.estado.pads.get("None")
    atual = b.m.daemon._gamepad_device
    return atual if atual is not None and atual is novo and atual is not b.velho else None


def _pisca_de_falha(b: SimpleNamespace) -> list[list[Any]]:
    return [seq for seq in b.luzes if seq and seq[0][0] == hotkey.COR_AVISO_RISCO]


def test_o_ps_r3_com_o_p1_em_voo_nao_acusa_e_anda_o_degrau(ensaio: SimpleNamespace) -> None:
    """O pad pedido ao fio ainda não existe quando o gesto volta de `_aplicar_ponte`."""
    b = ensaio
    b.escada.passo = SimpleNamespace(
        caminho=hotkey.PONTE_XBOX, degrau=_DEGRAU, motivo="teste", pulados=[])
    _no_laco(b.m, hotkey.build_next_bridge_callback(b.m.daemon))
    assert b.diario.dos("ponte_nao_subiu") == [], "o gesto acusou o pad que ainda nascia"
    assert _pisca_de_falha(b) == [], "o controle piscou a falha do pad que nasceu"
    novo = _o_p1_novo(b)
    assert novo is not None and novo.caminho == vp.CAMINHO_XBOX, "o P1 não nasceu no pedido"
    assert b.m.estado.pedidos == ["hefesto-nascimento-do-pad"], b.m.estado.pedidos
    assert b.escada.subiu == [_DEGRAU], "a escada não registrou o degrau que subiu"
    assert [c["caminho"] for c in b.escada.de_pe] == [hotkey.PONTE_XBOX]
    trocas = b.diario.dos("ponte_trocada_por_gesto")
    assert len(trocas) == 1 and trocas[0]["efetiva"] == hotkey.PONTE_XBOX, trocas
    assert trocas[0]["ok"] is True, trocas
    assert b.m.estado.ordem.index("respondeu") > b.m.estado.ordem.index(_PEDIDO)


def test_o_ps_r3_com_o_fio_que_falha_acusa_com_a_ponte_que_ficou(
    ensaio: SimpleNamespace,
) -> None:
    b = ensaio
    b.escada.passo = SimpleNamespace(
        caminho=hotkey.PONTE_XBOX, degrau=_DEGRAU, motivo="teste", pulados=[])
    b.m.estado.falhar = True
    _no_laco(b.m, hotkey.build_next_bridge_callback(b.m.daemon))
    acusadas = b.diario.dos("ponte_nao_subiu")
    assert len(acusadas) == 1, b.diario.linhas
    assert acusadas[0]["pedida"] == hotkey.PONTE_XBOX
    assert acusadas[0]["efetiva"] == hotkey.PONTE_MOUSE_TECLADO, acusadas
    assert len(_pisca_de_falha(b)) == 1, "o pad que não nasceu não piscou a falha"
    assert b.escada.subiu == [] and b.escada.de_pe == [], "a escada anotou o que não subiu"


def test_dois_apertos_no_meio_do_voo_andam_dois_degraus(ensaio: SimpleNamespace) -> None:
    """O segundo PS + R3 conta o modo pedido como o de onde, e o primeiro cede o veredito."""
    b = ensaio
    daemon = b.m.daemon
    daemon._gamepad_device = None
    daemon.config.gamepad_emulation_enabled = False
    gesto = hotkey.build_next_bridge_callback(daemon)

    async def _dois() -> None:
        primeiro = asyncio.ensure_future(gesto())
        limite = time.monotonic() + _GUARDA_S
        while _PEDIDO not in b.m.estado.ordem:
            assert time.monotonic() < limite, "o primeiro pedido não chegou ao broker"
            await asyncio.sleep(_TIQUE_S)
        assert not b.m.estado.soltar.is_set(), "o segundo aperto chegou fora do voo"
        assert hotkey.ponte_atual(daemon) == hotkey.PONTE_DUALSENSE, (
            "o P1 em voo não conta como a ponte de pé")
        await gesto()
        await primeiro

    _no_laco(b.m, _dois)
    pedidas = [(c["de"], c["para"]) for c in b.diario.dos("ponte_troca_pedida_por_gesto")]
    assert pedidas == [
        (hotkey.PONTE_MOUSE_TECLADO, hotkey.PONTE_DUALSENSE),
        (hotkey.PONTE_DUALSENSE, hotkey.PONTE_XBOX),
    ], pedidas
    novo = _o_p1_novo(b)
    assert novo is not None and novo.caminho == vp.CAMINHO_XBOX, "o P1 não ficou no segundo modo"
    assert b.diario.dos("ponte_nao_subiu") == [], "um dos apertos acusou falha"
    assert _pisca_de_falha(b) == [], "o controle piscou a falha"
    trocas = b.diario.dos("ponte_trocada_por_gesto")
    assert [t["efetiva"] for t in trocas] == [hotkey.PONTE_XBOX], (
        "só o último aperto dá o veredito", trocas)


def test_o_segundo_aperto_para_mouse_e_teclado_larga_o_pad_em_voo_sem_acusar(
    ensaio: SimpleNamespace,
) -> None:
    """Do DualSense de pé: o primeiro pede o Xbox ao fio, o segundo vai a mouse e teclado."""
    b = ensaio
    daemon = b.m.daemon
    gesto = hotkey.build_next_bridge_callback(daemon)

    async def _dois() -> None:
        primeiro = asyncio.ensure_future(gesto())
        limite = time.monotonic() + _GUARDA_S
        while _PEDIDO not in b.m.estado.ordem:
            assert time.monotonic() < limite, "o primeiro pedido não chegou ao broker"
            await asyncio.sleep(_TIQUE_S)
        assert daemon._gamepad_device is None, "o pad velho seguiu de pé no voo"
        await gesto()
        await primeiro

    _no_laco(b.m, _dois)
    pedidas = [(c["de"], c["para"]) for c in b.diario.dos("ponte_troca_pedida_por_gesto")]
    assert pedidas == [
        (hotkey.PONTE_DUALSENSE, hotkey.PONTE_XBOX),
        (hotkey.PONTE_XBOX, hotkey.PONTE_MOUSE_TECLADO),
    ], pedidas
    assert hotkey.ponte_atual(daemon) == hotkey.PONTE_MOUSE_TECLADO
    assert b.diario.dos("ponte_nao_subiu") == [], "o pad largado pelo segundo aperto acusou falha"
    assert _pisca_de_falha(b) == [], "o controle piscou a falha"
    trocas = b.diario.dos("ponte_trocada_por_gesto")
    assert [t["efetiva"] for t in trocas] == [hotkey.PONTE_MOUSE_TECLADO], trocas


def test_o_ps_r3_sem_o_p1_em_voo_da_o_veredito_na_hora(ensaio: SimpleNamespace) -> None:
    """Fora do laço o pad nasce na hora, sem fio: o veredito segue como sempre."""
    b = ensaio
    b.m.daemon._gamepad_device = None
    b.m.daemon.config.gamepad_emulation_enabled = False
    _soltar(b.m)
    fio = threading.Thread(
        target=lambda: asyncio.run(hotkey.build_next_bridge_callback(b.m.daemon)()))
    fio.start()
    fio.join(timeout=_GUARDA_S)
    assert not fio.is_alive(), "o gesto não voltou"
    assert gp.o_p1_que_nasce(b.m.daemon) is None
    assert hotkey.ponte_atual(b.m.daemon) == hotkey.PONTE_DUALSENSE
    trocas = b.diario.dos("ponte_trocada_por_gesto")
    assert len(trocas) == 1 and trocas[0]["efetiva"] == hotkey.PONTE_DUALSENSE, trocas
    assert b.diario.dos("ponte_nao_subiu") == [] and _pisca_de_falha(b) == []


def test_a_ponte_de_pe_conta_o_pedido_em_voo_e_o_descartado_volta_a_mouse_e_teclado(
    ensaio: SimpleNamespace,
) -> None:
    b = ensaio
    daemon = b.m.daemon
    daemon._gamepad_device = None
    daemon.config.gamepad_emulation_enabled = False
    assert hotkey.ponte_atual(daemon) == hotkey.PONTE_MOUSE_TECLADO

    async def _pedir_e_descartar() -> tuple[str, str]:
        hotkey._aplicar_ponte(daemon, hotkey.PONTE_XBOX)
        em_voo = hotkey.ponte_atual(daemon)
        hotkey._aplicar_ponte(daemon, hotkey.PONTE_MOUSE_TECLADO)
        return em_voo, hotkey.ponte_atual(daemon)

    em_voo, depois = _no_laco(b.m, _pedir_e_descartar)
    assert em_voo == hotkey.PONTE_XBOX, "o pedido em voo não contou"
    assert depois == hotkey.PONTE_MOUSE_TECLADO, "o pedido descartado ainda contou"
