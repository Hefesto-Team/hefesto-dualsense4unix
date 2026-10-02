"""SOM-JUNTO-01 — o botão do meio chega ao APARELHO, e não só ao disco."""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import fontes_de_captura
from tests.unit.bancada_do_som_junto import (
    FONE,
    HDMI,
    P1,
    P2,
    SINK_P1,
    Pactl,
    cabo,
    ela_clica,
    escrever_perfil,
    radio,
    subsystem_e_gerenciador,
)


@pytest.fixture()
def bancada(monkeypatch: pytest.MonkeyPatch) -> Pactl:
    """O `pactl` desviado no dono único dele: `alto_falante_bt._rodar`."""
    pactl = Pactl(placas=(SINK_P1,))
    monkeypatch.setattr(af, "_rodar", pactl)
    return pactl


@pytest.fixture()
def placa_do_p1(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Quem casa `uniq` com placa USB — mutável, para a placa poder SUMIR."""
    casamento = {P1: SINK_P1}
    monkeypatch.setattr(
        fontes_de_captura,
        "escolher_sink",
        lambda sinks, uniq, conhecidos, usb: casamento.get(uniq, ""),
    )
    return casamento


def test_o_botao_do_meio_chega_ao_no_que_ja_esta_de_pe(
    bancada: Pactl, placa_do_p1: dict[str, str]
) -> None:
    """O defeito inteiro, em uma cena: nó de pé em `sfx`, perfil vai a `mix`."""
    nome = escrever_perfil({P1: af.FONTE_SFX})
    _sub, ger = subsystem_e_gerenciador(nome)

    ger.reconciliar([cabo(P1)])
    no = ger.nos[P1]
    id_do_no = no.module_id
    assert bancada.loopbacks == [(f"{no.nome}.monitor", SINK_P1)], (
        "o nó nasceu sem a saída para o alto-falante do controle"
    )

    ela_clica(P1, af.FONTE_MIX)
    ger.reconciliar([cabo(P1)])

    assert (f"{HDMI}.monitor", no.nome) in bancada.loopbacks, (
        "ela clicou «No controle e na TV», o perfil gravou `mix` e o nó vivo "
        f"continuou sem o mix — loopbacks de pé: {bancada.loopbacks}"
    )
    assert (f"{no.nome}.monitor", SINK_P1) in bancada.loopbacks, (
        "a saída para o alto-falante caiu junto — o `mix` tirou o som do "
        "controle em vez de somar a TV a ele"
    )
    assert ger.nos[P1] is no, "o nó foi reconstruído: o jogo perdeu o objeto"
    assert no.module_id == id_do_no, (
        "o `module-null-sink` mudou de id — o nó saiu do servidor e voltou, e "
        "o jogo que o escolheu pegou o dispositivo sumindo debaixo dele"
    )
    assert id_do_no not in bancada.descarregados, (
        f"o nó foi descarregado do servidor: {bancada.descarregados}"
    )


def test_a_volta_para_so_no_controle_derruba_o_mix_e_mantem_a_saida(
    bancada: Pactl, placa_do_p1: dict[str, str]
) -> None:
    """O outro sentido do mesmo botão: `mix` → `sfx` desliga SÓ o mix."""
    nome = escrever_perfil({P1: af.FONTE_MIX})
    _sub, ger = subsystem_e_gerenciador(nome)

    ger.reconciliar([cabo(P1)])
    no = ger.nos[P1]
    assert len(bancada.loopbacks) == 2, bancada.loopbacks

    ela_clica(P1, af.FONTE_SFX)
    ger.reconciliar([cabo(P1)])

    assert bancada.loopbacks == [(f"{no.nome}.monitor", SINK_P1)], (
        f"o mix ficou de pé depois de ela desligá-lo: {bancada.loopbacks}"
    )
    assert no.module_id is not None and no.module_id not in bancada.descarregados


def test_a_escolha_de_um_nao_mexe_no_no_do_vizinho(
    bancada: Pactl, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A régua de aceitação DELA: *"sem impactar os demais"*."""
    nome = escrever_perfil({P1: af.FONTE_SFX, P2: af.FONTE_MIX})
    _sub, ger = subsystem_e_gerenciador(
        nome, ponte_do_radio_por_controle=lambda _uniq: (lambda: True)
    )

    ger.reconciliar([radio(P1), radio(P2)])
    no_p2 = ger.nos[P2]
    assert bancada.loopbacks == [(f"{HDMI}.monitor", no_p2.nome)], bancada.loopbacks

    ela_clica(P1, af.FONTE_MIX)
    ger.reconciliar([radio(P1), radio(P2)])

    assert (f"{HDMI}.monitor", ger.nos[P1].nome) in bancada.loopbacks
    assert (f"{HDMI}.monitor", no_p2.nome) in bancada.loopbacks, (
        "o vizinho perdeu o mix que ele já tinha — a escolha de um chegou ao "
        "nó do outro"
    )
    assert bancada.descarregados == []


def test_sem_divergencia_a_varredura_nao_mexe_em_nada(
    bancada: Pactl, placa_do_p1: dict[str, str]
) -> None:
    """Um nó que renasce a cada varredura é PIOR que a escolha presa."""
    nome = escrever_perfil({P1: af.FONTE_MIX})
    _sub, ger = subsystem_e_gerenciador(nome)

    ger.reconciliar([cabo(P1)])
    no = ger.nos[P1]
    carregados = dict(bancada.carregados)

    for _ in range(4):
        ger.reconciliar([cabo(P1)])

    assert bancada.descarregados == [], (
        "a varredura derrubou módulo sem ninguém ter mudado nada: "
        f"{bancada.descarregados}"
    )
    assert bancada.carregados == carregados, (
        "a varredura carregou módulo a mais — em uma hora seriam 720 "
        "`module-loopback` empilhados no servidor de som dela"
    )
    assert ger.nos[P1] is no


def test_ela_trocar_a_saida_do_sistema_sozinha_nao_religa_o_no(
    bancada: Pactl, placa_do_p1: dict[str, str]
) -> None:
    """A comparação tem de ser ESTÁVEL, e o monitor da saída padrão não é."""
    nome = escrever_perfil({P1: af.FONTE_MIX})
    _sub, ger = subsystem_e_gerenciador(nome)

    ger.reconciliar([cabo(P1)])
    carregados = dict(bancada.carregados)

    bancada.padrao = FONE
    ger.reconciliar([cabo(P1)])
    bancada.padrao = HDMI
    ger.reconciliar([cabo(P1)])

    assert bancada.descarregados == [], (
        "trocar a saída do sistema religou o nó — com ela mexendo no som, "
        "isso vira o nó piscando debaixo do jogo"
    )
    assert bancada.carregados == carregados


def test_perder_a_rota_nao_desliga_o_que_esta_ligado(bancada: Pactl) -> None:
    """A ponte do rádio cai: isso é *"agora não sei"*, não *"desligue"*."""
    nome = escrever_perfil({P1: af.FONTE_MIX})
    no_ar = {P1}
    _sub, ger = subsystem_e_gerenciador(
        nome, ponte_do_radio_por_controle=lambda uniq: (lambda: uniq in no_ar)
    )

    ger.reconciliar([radio(P1)])
    no = ger.nos[P1]
    assert bancada.loopbacks == [(f"{HDMI}.monitor", no.nome)], bancada.loopbacks

    no_ar.clear()
    ger.reconciliar([radio(P1)])

    assert bancada.loopbacks == [(f"{HDMI}.monitor", no.nome)], (
        "a rota sumiu por um instante e a varredura arrancou o loopback que "
        "estava tocando"
    )
    assert bancada.descarregados == []


def test_o_no_nunca_vira_alvo_de_si_mesmo(
    bancada: Pactl, placa_do_p1: dict[str, str]
) -> None:
    """`sink_do_controle` devolve o PRÓPRIO nó como recuo — e ele está vivo."""
    nome = escrever_perfil({P1: af.FONTE_SFX})
    _sub, ger = subsystem_e_gerenciador(nome)

    ger.reconciliar([cabo(P1)])
    no = ger.nos[P1]
    assert bancada.loopbacks == [(f"{no.nome}.monitor", SINK_P1)]

    placa_do_p1.clear()
    ger.reconciliar([cabo(P1)])

    assert (f"{no.nome}.monitor", no.nome) not in bancada.loopbacks, (
        "o nó virou a origem e o destino do mesmo loopback"
    )
    assert bancada.loopbacks == [(f"{no.nome}.monitor", SINK_P1)]
    assert bancada.descarregados == []


def test_a_assinatura_ignora_o_monitor_e_a_frase_e_ve_a_fonte() -> None:
    """Quatro campos entram; o monitor e o motivo ficam de fora."""
    base = af.RotaDoNo(
        True, sink=SINK_P1, por_onde=af.POR_CABO, fonte=af.FONTE_MIX,
        monitor_do_mix=f"{HDMI}.monitor",
    )
    outro_monitor = af.RotaDoNo(
        True, sink=SINK_P1, por_onde=af.POR_CABO, fonte=af.FONTE_MIX,
        monitor_do_mix=f"{FONE}.monitor", motivo="outra frase",
    )
    outra_fonte = af.RotaDoNo(
        True, sink=SINK_P1, por_onde=af.POR_CABO, fonte=af.FONTE_SFX
    )

    assert af.assinatura_da_rota(base) == af.assinatura_da_rota(outro_monitor)
    assert af.assinatura_da_rota(base) != af.assinatura_da_rota(outra_fonte)
    assert af.assinatura_da_rota(None) == (False, "", "", "")


def test_o_no_no_chao_so_guarda_a_rota(bancada: Pactl) -> None:
    """Religar um nó que não subiu não pode mandar `pactl` nenhum."""
    no = af.SinkVirtualPipeWire(uniq=P2, runner=bancada)
    rota = af.RotaDoNo(True, sink=SINK_P1, por_onde=af.POR_CABO)

    assert no.religar(rota) is False
    assert no.rota is rota
    assert bancada.carregados == {}
