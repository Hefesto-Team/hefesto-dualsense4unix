"""O-BOTAO-ENTREGA-O-QUE-PROMETE-01 — o FIO entre o clique dela e o nó vivo."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import fontes_de_captura
from tests.unit.bancada_do_som_junto import (
    HDMI,
    P1,
    P2,
    SINK_P1,
    Pactl,
    Store,
    cabo,
    ela_clica,
    escrever_perfil,
)


def _calar_o_laco(sub: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """A thread do `start()` sobe, e não tem o que fazer."""
    monkeypatch.setattr(sub, "_loop", lambda: None)


@pytest.fixture()
def bancada(monkeypatch: pytest.MonkeyPatch) -> Pactl:
    """O `pactl` desviado no dono único dele: `alto_falante_bt._rodar`."""
    pactl = Pactl(placas=(SINK_P1,))
    monkeypatch.setattr(af, "_rodar", pactl)
    return pactl


@pytest.fixture()
def placa_do_p1(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quem casa `uniq` com a placa USB do controle no cabo."""
    monkeypatch.setattr(
        fontes_de_captura,
        "escolher_sink",
        lambda sinks, uniq, conhecidos, usb: SINK_P1 if uniq == P1 else "",
    )


@pytest.fixture()
def subsystem_de_pe(monkeypatch: pytest.MonkeyPatch) -> Any:
    """O subsystem com o `start()` DE VERDADE — e o `stop()` real no fim."""
    sub = mod.AltoFalanteSubsystem(fonte_de_controles=lambda: [])
    _calar_o_laco(sub, monkeypatch)

    def subir(perfil: str | None) -> Any:
        ctx = SimpleNamespace(controller=None, store=Store(perfil))
        asyncio.run(sub.start(ctx))
        return sub

    yield subir
    asyncio.run(sub.stop())


def test_o_start_fia_a_fonte_no_gerenciador_que_ele_constroi(
    bancada: Pactl, subsystem_de_pe: Any
) -> None:
    """MORDIDA: apague `fonte_por_controle=self._fonte_do_controle` do `start`."""
    sub = subsystem_de_pe(escrever_perfil({P1: af.FONTE_MIX}))
    ger = sub._gerenciador

    assert ger is not None, "o `start` não construiu gerenciador nenhum"
    assert ger._fonte_por_controle is not None, (
        "o gerenciador do `start` nasceu sem quem lhe diga a fonte — todo nó "
        "vive no padrão e o clique dela não chega ao som")
    assert ger._fonte_por_controle(P1) == af.FONTE_MIX, (
        "o fio existe mas não fala com o dono da escolha")


def test_o_gerenciador_injetado_continua_vencendo(
    bancada: Pactl, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Quem injeta um gerenciador não o vê trocado pelo `start` — é contrato."""
    meu = mod.GerenciadorDeNosDeSom()
    sub = mod.AltoFalanteSubsystem(fonte_de_controles=lambda: [],
                                   gerenciador=meu)
    _calar_o_laco(sub, monkeypatch)
    try:
        asyncio.run(sub.start(SimpleNamespace(controller=None, store=Store(None))))
        assert sub._gerenciador is meu
    finally:
        asyncio.run(sub.stop())


def test_a_escolha_viva_chega_ao_no_sem_passar_pelo_perfil(
    bancada: Pactl, placa_do_p1: None, subsystem_de_pe: Any
) -> None:
    """O caminho do `speaker.set {fonte}`, do IPC até o `module-loopback`."""
    sub = subsystem_de_pe(None)
    ger = sub._gerenciador

    ger.reconciliar([cabo(P1)])
    no = ger.nos[P1]
    id_do_no = no.module_id
    assert (f"{HDMI}.monitor", no.nome) not in bancada.loopbacks, (
        "o nó nasceu com o som da máquina dentro sem ninguém ter escolhido — "
        "`FONTE_PADRAO` é `sfx` por decisão dela, de 08/09")

    assert sub.escolher_a_fonte(P1, af.FONTE_MIX) is True
    ger.reconciliar([cabo(P1)])

    assert (f"{HDMI}.monitor", no.nome) in bancada.loopbacks, (
        f"o `speaker.set {{fonte}}` não chegou ao nó vivo — de pé: "
        f"{bancada.loopbacks}")
    assert (f"{no.nome}.monitor", SINK_P1) in bancada.loopbacks, (
        "a saída para o alto-falante do controle caiu junto com a chegada do mix")
    assert ger.nos[P1].module_id == id_do_no, (
        "o nó RENASCEU — `D-0809-O-NO-DE-SOM-POR-CONTROLE-VIVE-SEMPRE`: o jogo "
        "escolheu este id e ele não pode trocar debaixo dele")


def test_a_escolha_viva_vence_o_perfil_no_no_e_nao_so_no_cache(
    bancada: Pactl, placa_do_p1: None, subsystem_de_pe: Any
) -> None:
    """Perfil em `sfx`, clique em `mix`: quem manda no NÓ é o clique."""
    sub = subsystem_de_pe(escrever_perfil({P1: af.FONTE_SFX}))
    ger = sub._gerenciador

    ger.reconciliar([cabo(P1)])
    no = ger.nos[P1]
    assert (f"{HDMI}.monitor", no.nome) not in bancada.loopbacks

    sub.escolher_a_fonte(P1, af.FONTE_MIX)
    ger.reconciliar([cabo(P1)])

    assert (f"{HDMI}.monitor", no.nome) in bancada.loopbacks, (
        f"o perfil venceu o clique de agora: {bancada.loopbacks}")


def test_o_perfil_continua_mandando_em_quem_nao_clicou(
    bancada: Pactl, placa_do_p1: None, subsystem_de_pe: Any
) -> None:
    """O caminho novo não atropela o antigo, e o `mtime` continua valendo."""
    nome = escrever_perfil({P1: af.FONTE_SFX})
    sub = subsystem_de_pe(nome)
    ger = sub._gerenciador

    ger.reconciliar([cabo(P1)])
    no = ger.nos[P1]

    ela_clica(P1, af.FONTE_MIX, nome)
    ger.reconciliar([cabo(P1)])

    assert (f"{HDMI}.monitor", no.nome) in bancada.loopbacks, (
        f"a escolha gravada no perfil parou de chegar ao nó: {bancada.loopbacks}")


def test_a_escolha_viva_e_de_um_controle_so(
    bancada: Pactl, subsystem_de_pe: Any
) -> None:
    """Escolher para o P1 não põe o som da máquina no ouvido do P2."""
    sub = subsystem_de_pe(None)
    ger = sub._gerenciador

    sub.escolher_a_fonte(P1, af.FONTE_MIX)

    assert ger._fonte_por_controle(P1) == af.FONTE_MIX
    assert ger._fonte_por_controle(P2) == af.FONTE_PADRAO


def test_um_nome_que_o_no_nao_sabe_tratar_nao_entra_no_fio(
    bancada: Pactl, subsystem_de_pe: Any
) -> None:
    """Tipo FECHADO no dono, e não só na porta do IPC."""
    sub = subsystem_de_pe(None)

    assert sub.escolher_a_fonte(P1, "hdmi") is False
    assert sub._gerenciador._fonte_por_controle(P1) == af.FONTE_PADRAO
