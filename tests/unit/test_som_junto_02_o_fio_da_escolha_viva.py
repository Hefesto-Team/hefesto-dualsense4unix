"""O-BOTAO-ENTREGA-O-QUE-PROMETE-01 — o FIO entre o clique dela e o nó vivo.

**POR QUE ESTE ARQUIVO EXISTE, com 354 linhas de SOM-JUNTO-01 ao lado.**
Porque aquelas medem o gerenciador com a fiação montada **à mão**:

    tests/unit/bancada_do_som_junto.subsystem_e_gerenciador
        return sub, mod.GerenciadorDeNosDeSom(
            fonte_por_controle=sub._fonte_do_controle, ...)

A docstring de lá diz, com todas as letras, que aquilo *"é o que
``AltoFalanteSubsystem.start`` monta"* — e é: uma **cópia** do que o `start`
monta. Cópia não é o produto. Medido em 20/09/2026, apagando a linha
`fonte_por_controle=self._fonte_do_controle` do `start` de verdade: **150
réguas desta área verdes**, com o nó de cada controle de volta ao
`FONTE_PADRAO` para sempre.

É a assinatura que esta casa já nomeou quatro vezes — *o instrumento respondia
sobre outra coisa que não o produto* —, e aqui a outra coisa era uma fiação de
conveniência escrita pela própria bancada.

**O QUE ESTE ARQUIVO TRAVA, e são os dois elos que faltavam:**

1. o `start()` DE VERDADE injeta `fonte_por_controle` no gerenciador que ele
   constrói — apagar a linha reprova aqui, e em lugar nenhum antes;
2. a escolha VIVA (`escolher_a_fonte`, que é por onde o `speaker.set` do IPC
   entra) atravessa o fio inteiro e muda o `module-loopback` que fica de pé —
   sem passar pelo perfil, que é o intervalo em que a escolha dela se perdia.

**NENHUM BYTE VAI A SERVIDOR NENHUM.** O `pactl` é o dublê da bancada
compartilhada, o LAÇO do subsystem é calado antes do `start()`, e o `stop()`
real devolve os dois registros globais que o `start()` instala.

**E O LAÇO SE CALA NO DONO DELE, nunca no `threading` do módulo.** A primeira
versão desta régua trocou `alto_falante.threading.Thread` por um dublê — e
`alto_falante.threading` **é o módulo `threading` inteiro**, o mesmo de que o
`asyncio.to_thread` do `stop()` tira o executor. A corrida travou sem uma
palavra, com o primeiro teste verde. *Desviar um módulo importado por outro é
desviá-lo para a casa toda.*
"""
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
    """A thread do `start()` sobe, e não tem o que fazer.

    O `start()` é o objeto da medição, então ele roda INTEIRO — inclusive a
    `threading.Thread`, que é de verdade. Quem fica sem trabalho é o LAÇO, que
    varreria o sysfs desta máquina e falaria com o servidor de som dela. O
    laço não tem nada a dizer sobre a fiação: quem constrói o gerenciador é a
    linha acima dele.
    """
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
    """O subsystem com o `start()` DE VERDADE — e o `stop()` real no fim.

    O `stop()` não é higiene opcional: o `start()` instala DOIS registros de
    módulo (o numerador de assento e o dizedor da fonte), e um teste que os
    deixa de pé envenena o vizinho que rodar depois no mesmo processo. Esta
    casa já pagou por estado de módulo sem dono duas vezes nesta mesma área.
    """
    sub = mod.AltoFalanteSubsystem(fonte_de_controles=lambda: [])
    _calar_o_laco(sub, monkeypatch)

    def subir(perfil: str | None) -> Any:
        ctx = SimpleNamespace(controller=None, store=Store(perfil))
        asyncio.run(sub.start(ctx))
        return sub

    yield subir
    asyncio.run(sub.stop())


# ---------------------------------------------------------------------------
# 1. O `start()` DE VERDADE fia a fonte — a linha que régua nenhuma olhava
# ---------------------------------------------------------------------------


def test_o_start_fia_a_fonte_no_gerenciador_que_ele_constroi(
    bancada: Pactl, subsystem_de_pe: Any
) -> None:
    """MORDIDA: apague `fonte_por_controle=self._fonte_do_controle` do `start`.

    Sem esta régua a arrancada é INVISÍVEL: `_fonte_do_no` cai no
    `if self._fonte_por_controle is None: return FONTE_PADRAO`, todo nó nasce
    e vive em `sfx`, e as 150 réguas da área continuam verdes — medido.
    """
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
    """Quem injeta um gerenciador não o vê trocado pelo `start` — é contrato.

    MORDIDA: faça o `start` construir o gerenciador sempre. As réguas que
    injetam o seu para medir a reconciliação passariam a medir outro objeto,
    e a fiação nova viraria uma regressão silenciosa nelas.
    """
    meu = mod.GerenciadorDeNosDeSom()
    sub = mod.AltoFalanteSubsystem(fonte_de_controles=lambda: [],
                                   gerenciador=meu)
    _calar_o_laco(sub, monkeypatch)
    try:
        asyncio.run(sub.start(SimpleNamespace(controller=None, store=Store(None))))
        assert sub._gerenciador is meu
    finally:
        asyncio.run(sub.stop())


# ---------------------------------------------------------------------------
# 2. A ESCOLHA VIVA atravessa o fio — e muda o que fica CARREGADO
# ---------------------------------------------------------------------------


def test_a_escolha_viva_chega_ao_no_sem_passar_pelo_perfil(
    bancada: Pactl, placa_do_p1: None, subsystem_de_pe: Any
) -> None:
    """O caminho do `speaker.set {fonte}`, do IPC até o `module-loopback`.

    É o que a `CORREÇÃO DE FATO` da sprint deixou de pé: o caminho velho
    dependia de haver perfil ATIVO, e *o produto é para qualquer usuário*
    (ordem dela, 11/09). Aqui **não há perfil nenhum** — e o nó tem de mudar
    assim mesmo.

    MORDIDA: faça `escolher_a_fonte` devolver `True` sem guardar, ou apague o
    `if viva:` de `_fonte_do_controle`. Nos dois casos o mix nunca cai no nó.
    """
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
    """Perfil em `sfx`, clique em `mix`: quem manda no NÓ é o clique.

    A régua irmã do IPC já mede a precedência no cache
    (`test_a_escolha_viva_vence_o_perfil`); esta mede o que ficou CARREGADO.
    A diferença é a que a SOM-JUNTO-01 pagou para descobrir: o cache invalidava
    certinho e o nó continuava com a fonte de antes.

    MORDIDA: apague o `if viva:` de `_fonte_do_controle`.
    """
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
    """O caminho novo não atropela o antigo, e o `mtime` continua valendo.

    MORDIDA: faça `_fonte_do_controle` devolver a viva SEMPRE, com um `or`
    invertido. A escolha dela deixaria de sobreviver ao reinício do daemon,
    que é o único lugar onde ela dura.
    """
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
    """Escolher para o P1 não põe o som da máquina no ouvido do P2.

    É a família do `_handle_for(None)` de 18/09, medida no FIO e não no cache:
    um ato de áudio sem endereço é um ato no jogador errado.

    MORDIDA: guarde a fonte numa variável única em vez do dicionário por
    controle.
    """
    sub = subsystem_de_pe(None)
    ger = sub._gerenciador

    sub.escolher_a_fonte(P1, af.FONTE_MIX)

    assert ger._fonte_por_controle(P1) == af.FONTE_MIX
    assert ger._fonte_por_controle(P2) == af.FONTE_PADRAO


def test_um_nome_que_o_no_nao_sabe_tratar_nao_entra_no_fio(
    bancada: Pactl, subsystem_de_pe: Any
) -> None:
    """Tipo FECHADO no dono, e não só na porta do IPC.

    O handler já recusa `"hdmi"`; esta régua diz que o dono recusa igual, para
    o dia em que nascer um segundo chamador. Um terceiro nome aceito em
    silêncio mandaria o áudio para um arranjo que `rota_do_no` não monta, e o
    nó ficaria mudo sem ninguém saber por quê.

    MORDIDA: troque a conferência de `escolher_a_fonte` por um `str(fonte)`.
    """
    sub = subsystem_de_pe(None)

    assert sub.escolher_a_fonte(P1, "hdmi") is False
    assert sub._gerenciador._fonte_por_controle(P1) == af.FONTE_PADRAO
