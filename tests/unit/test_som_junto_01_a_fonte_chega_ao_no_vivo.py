"""SOM-JUNTO-01 — o botão do meio chega ao APARELHO, e não só ao disco.

A QUEIXA DELA, 17/09/2026
--------------------------
    *"o som se eu clicar em um dos 3 botões ele tem que sair o som via canal de
    audio externo do controle"*   <!-- (noqa-acento): é a digitação dela -->

Dos três botões do card Alto-falante, o do meio — «No controle e na TV» —
gravava ``speaker.fonte="mix"`` no perfil e **nunca chegava ao aparelho**. A
fonte só era resolvida ao CONSTRUIR o nó, e a varredura fechava a porta antes
de perguntar qualquer coisa (``if uniq in self._nos: continue``). Medido com
quatro varreduras trocando a fonte no meio: **1 construção, nó vivo em
``sfx``, perfil em ``mix``, zero ``module-loopback`` na máquina dela.**

POR QUE ESTE ARQUIVO EXISTE, se já havia 844 linhas sobre os três botões
------------------------------------------------------------------------
Porque nenhuma delas olhava o NÓ. A que prometia — o
``test_a_escolha_dela_vale_na_varredura_seguinte``, cujo docstring diz *"a
escolha dela ficaria presa até o daemon reiniciar, que é o defeito-mãe desta
casa"* — olhava o CACHE:
``assert sub._fonte_do_controle(_P1) == FONTE_MIX``. O cache invalidava
certinho, o nó continuava com a fonte de antes, e o teste passava. **Uma régua
que ocupa o lugar da que faltava é pior que régua nenhuma**, e é por isso que
ela foi reescrita junto com esta cura, no arquivo dela.

Aqui não há cache: toda asserção é sobre o que ficou CARREGADO no ``pactl``.

O QUE ESTE ARQUIVO TRAVA
-------------------------
1. a fonte que ela gravou chega ao nó que **já está de pé**, com ``source`` e
   ``sink`` certos no ``module-loopback``;
2. **e o nó NÃO renasce** — ``D-0809-O-NO-DE-SOM-POR-CONTROLE-VIVE-SEMPRE``:
   o ``module-null-sink`` fica com o mesmo id, porque o jogo o escolheu;
3. sem divergência, a varredura **não mexe em nada** — nem um ``unload``;
4. ela trocar a saída do sistema (fone ⇄ TV) **sozinha não religa o nó**;
5. **perder a rota não desliga o que está ligado**;
6. o nó **nunca vira alvo de si mesmo** (``source=X.monitor sink=X``);
7. voltar para ``sfx`` derruba o loopback do mix e mantém o da saída.

A MORDIDA, e as três saídas estão na entrega
---------------------------------------------
Troque ``self._reafinar(...)`` de volta por um ``continue`` seco em
``GerenciadorDeNosDeSom.reconciliar`` e os itens 1, 2 e 7 reprovam. Tire a
comparação por ``assinatura_da_rota`` de ``SinkVirtualPipeWire.religar`` e os
itens 3 e 4 reprovam. Tire as recusas de ``_vale_religar`` e os itens 5 e 6
reprovam.
"""
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


# ---------------------------------------------------------------------------
# 1, 2 e 7. A MORDIDA — a escolha dela chega ao nó VIVO, e o nó não sai do lugar
# ---------------------------------------------------------------------------


def test_o_botao_do_meio_chega_ao_no_que_ja_esta_de_pe(
    bancada: Pactl, placa_do_p1: dict[str, str]
) -> None:
    """O defeito inteiro, em uma cena: nó de pé em `sfx`, perfil vai a `mix`.

    A asserção é sobre o ``module-loopback`` CARREGADO — não sobre o cache,
    não sobre `no.rota`, não sobre o argv pedido: sobre o que ficou de pé.
    """
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
    # Item 2 — `D-0809-O-NO-DE-SOM-POR-CONTROLE-VIVE-SEMPRE`.
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
    """O outro sentido do mesmo botão: `mix` → `sfx` desliga SÓ o mix.

    Sem isto, «Sons do jogo» viraria um botão que acende na tela e deixa o
    áudio do sistema inteiro no ouvido dela para sempre.
    """
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
    """A régua de aceitação DELA: *"sem impactar os demais"*.

    Dois no rádio, os dois com nó de pé. Ela troca só o do P1 para `mix`: o
    loopback do P2 não pode nem ser descarregado nem ganhar companhia.
    """
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


# ---------------------------------------------------------------------------
# 3 e 4. O OUTRO LADO — sem divergência a varredura não encosta no nó
# ---------------------------------------------------------------------------


def test_sem_divergencia_a_varredura_nao_mexe_em_nada(
    bancada: Pactl, placa_do_p1: dict[str, str]
) -> None:
    """Um nó que renasce a cada varredura é PIOR que a escolha presa.

    Quatro varreduras seguidas com o perfil parado: nenhum `unload-module`,
    nenhum `load-module` a mais, o mesmo objeto e o mesmo id.
    """
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
    """A comparação tem de ser ESTÁVEL, e o monitor da saída padrão não é.

    `monitor_da_saida_padrao` muda quando ela troca a TV pelo fone, e vira
    `""` a cada soluço do servidor. Compará-lo poria a varredura a religar o
    nó em laço — e a arrancar o loopback que está tocando por causa de dois
    segundos de silêncio do `pipewire-pulse`.

    MORDIDA: ponha `monitor_do_mix` em `assinatura_da_rota` e esta régua
    reprova.
    """
    nome = escrever_perfil({P1: af.FONTE_MIX})
    _sub, ger = subsystem_e_gerenciador(nome)

    ger.reconciliar([cabo(P1)])
    carregados = dict(bancada.carregados)

    bancada.padrao = FONE  # ela põe o fone
    ger.reconciliar([cabo(P1)])
    bancada.padrao = HDMI  # e volta para a TV
    ger.reconciliar([cabo(P1)])

    assert bancada.descarregados == [], (
        "trocar a saída do sistema religou o nó — com ela mexendo no som, "
        "isso vira o nó piscando debaixo do jogo"
    )
    assert bancada.carregados == carregados


# ---------------------------------------------------------------------------
# 5 e 6. AS DUAS RECUSAS — a varredura não pode estragar o que funciona
# ---------------------------------------------------------------------------


def test_perder_a_rota_nao_desliga_o_que_esta_ligado(bancada: Pactl) -> None:
    """A ponte do rádio cai: isso é *"agora não sei"*, não *"desligue"*.

    Trocar um silêncio de cinco segundos por um permanente é o defeito que a
    decisão dela de 08/09 existe para impedir.

    MORDIDA: tire a recusa `not rota.tem_rota` de `_vale_religar` e o
    `module-loopback` do mix é arrancado aqui.
    """
    nome = escrever_perfil({P1: af.FONTE_MIX})
    no_ar = {P1}
    _sub, ger = subsystem_e_gerenciador(
        nome, ponte_do_radio_por_controle=lambda uniq: (lambda: uniq in no_ar)
    )

    ger.reconciliar([radio(P1)])
    no = ger.nos[P1]
    assert bancada.loopbacks == [(f"{HDMI}.monitor", no.nome)], bancada.loopbacks

    no_ar.clear()  # a ponte caiu
    ger.reconciliar([radio(P1)])

    assert bancada.loopbacks == [(f"{HDMI}.monitor", no.nome)], (
        "a rota sumiu por um instante e a varredura arrancou o loopback que "
        "estava tocando"
    )
    assert bancada.descarregados == []


def test_o_no_nunca_vira_alvo_de_si_mesmo(
    bancada: Pactl, placa_do_p1: dict[str, str]
) -> None:
    """`sink_do_controle` devolve o PRÓPRIO nó como recuo — e ele está vivo.

    O recuo existe para a pergunta *"qual é o sink deste controle?"* da tela,
    não para ser alvo de loopback. Sem a recusa, a varredura montaria
    `source=X.monitor sink=X` — e, pior, a assinatura da rota passaria a
    depender de o nó estar de pé, que é a receita exata do nó que renasce a
    cada varredura.

    MORDIDA: tire a recusa do `nome_do_sink` de `_vale_religar` e esta régua
    reprova com o fio em si mesmo.
    """
    nome = escrever_perfil({P1: af.FONTE_SFX})
    _sub, ger = subsystem_e_gerenciador(nome)

    ger.reconciliar([cabo(P1)])
    no = ger.nos[P1]
    assert bancada.loopbacks == [(f"{no.nome}.monitor", SINK_P1)]

    placa_do_p1.clear()  # o casamento por USB deixou de resolver
    ger.reconciliar([cabo(P1)])

    assert (f"{no.nome}.monitor", no.nome) not in bancada.loopbacks, (
        "o nó virou a origem e o destino do mesmo loopback"
    )
    assert bancada.loopbacks == [(f"{no.nome}.monitor", SINK_P1)]
    assert bancada.descarregados == []


# ---------------------------------------------------------------------------
# A ASSINATURA — o que ela compara, e o que ela deixa de fora
# ---------------------------------------------------------------------------


def test_a_assinatura_ignora_o_monitor_e_a_frase_e_ve_a_fonte() -> None:
    """Quatro campos entram; o monitor e o motivo ficam de fora.

    O motivo é TEXTO para a tela: frase nova não é fiação nova.
    """
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
    """Religar um nó que não subiu não pode mandar `pactl` nenhum.

    Um `module-loopback` para um sink que não existe é o `paplay --device=`
    que esta casa já pagou: aceito, e o som vai para outro lugar.
    """
    no = af.SinkVirtualPipeWire(uniq=P2, runner=bancada)
    rota = af.RotaDoNo(True, sink=SINK_P1, por_onde=af.POR_CABO)

    assert no.religar(rota) is False
    assert no.rota is rota
    assert bancada.carregados == {}
