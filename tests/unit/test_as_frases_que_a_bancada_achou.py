"""AS-FRASES-QUE-A-BANCADA-ACHOU-01 — o que a tela dizia e o produto desmentia."""
from __future__ import annotations

import html
import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.home_actions`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions.home_actions import (
    palavra_do_transporte as palavra,
)
from hefesto_dualsense4unix.interface import conexoes as gestao
from tests.unit.test_a05_a_vibracao_aplica_e_fala import PonteDeMentira

BANCADA = RAIZ / "mockup"

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"


def _pagina(nome: str) -> str:
    """A página gerada, SEM os comentários — o que chega ao olho."""
    bruto = (BANCADA / nome).read_text(encoding="utf-8")
    return re.sub(r"<!--.*?-->", "", bruto, flags=re.S)


def _texto(trecho: str) -> str:
    """O texto visível de um pedaço de HTML: sem tags, com o espaço colapsado."""
    sem_tags = re.sub(r"<[^>]+>", "", trecho)
    return re.sub(r"\s+", " ", html.unescape(sem_tags)).strip()


def _dica_do_testar() -> str:
    """O primeiro parágrafo do `?` do «Testar agora», como a página o mostra."""
    x = _pagina("05-vibracao.html")
    m = re.search(r'<span class="sec-rot">Testar agora\s*<span class="ajuda"[^>]*>\?'
                  r'<span class="dica">(.*?)<br><br>', x, flags=re.S)
    assert m, "o `?` do «Testar agora» sumiu da 05 gerada — a régua ficou cega"
    return _texto(m.group(1))


def test_a_dica_do_testar_nao_promete_duracao() -> None:
    """O «?» diz que o teste vai até o «Parar», e não põe prazo nenhum."""
    dica = _dica_do_testar()
    prazo = re.search(r"\b(segundos?|ms|milissegundos?)\b", dica, flags=re.I)
    assert not prazo, (
        f"o `?` do «Testar agora» voltou a prometer um prazo ({prazo.group(0)!r}) "
        f"— o Testar fica ligado até o Parar desde 07/09: {dica!r}")
    assert re.search(r"\baté o Parar\b", dica), (
        f"o `?` do «Testar agora» não diz mais quem termina o teste: {dica!r}")
    assert re.search(r"\boutro controle\b", dica), (
        f"o `?` do «Testar agora» não diz que o teste de outro controle "
        f"encerra este (um teste só, `_EM_TESTE`): {dica!r}")


@pytest.fixture
def pac() -> Any:
    import pacotes

    return pacotes


@pytest.fixture
def a05() -> Any:
    from pacotes import a05_vibracao

    a05_vibracao.parar_o_teste()
    yield a05_vibracao
    a05_vibracao.parar_o_teste()


def _ctx(pac: Any) -> Any:
    """A mesa com os dois controles, um no USB e um no BT."""
    return pac.Contexto(
        state={"active_profile": "Bancada", "rumble_policy": "max",
               "rumble_motor_pct_padrao": 100, "rumble_motores": {}},
        mesa=[
            {"pref": "p1", "jogador": 1, "uniq": P1, "nome": "Régua 1",
             "via": "USB", "cor": "starlight-blue"},
            {"pref": "p2", "jogador": 2, "uniq": P2, "nome": "Régua 2",
             "via": "BT", "cor": "midnight-black"},
        ],
        conectados=[
            {"uniq": P1, "connected": True, "transport": "usb", "index": 0, "player": 1},
            {"uniq": P2, "connected": True, "transport": "bt", "index": 1,
             "player": 2},
        ],
        estados={})


def test_o_testar_fica_ligado_ate_o_parar_e_o_de_outro_controle_o_encerra(
        pac: Any, a05: Any) -> None:
    """O fato que a frase nova afirma, medido no gesto — não na prosa."""
    testar = pac.gesto_da_pagina("05-vibracao.html", "testar")
    parar = pac.gesto_da_pagina("05-vibracao.html", "parar")
    assert testar is not None and parar is not None, "o par Testar/Parar perdeu o dono"
    ctx = _ctx(pac)

    p = PonteDeMentira()
    testar(ctx, {"uniq": P1, "controle": "p1"}, p)
    paradas = [n for n in p.nomes if n.startswith(("rumble_stop", "rumble_passthrough"))]
    assert not paradas, f"o Testar parou sozinho: {p.nomes}"
    assert "rumble_set_checked" in p.nomes, f"o Testar não mandou vibração: {p.nomes}"
    assert a05.em_teste() == P1, "o Testar do P1 não ficou ligado"

    testar(ctx, {"uniq": P2, "controle": "p2"}, PonteDeMentira())
    assert a05.em_teste() == P2, (
        "o Testar do P2 não encerrou o do P1 — um teste só, `_EM_TESTE`")

    fim = PonteDeMentira()
    parar(ctx, {"uniq": P2, "controle": "p2"}, fim)
    assert a05.em_teste() == "", "o Parar não apagou a marca do teste"
    assert "rumble_stop_checked" in fim.nomes and "rumble_passthrough" in fim.nomes, (
        f"o Parar não devolveu os motores ao jogo: {fim.nomes}")


def _cartoes_da_gestao() -> list[tuple[str, str]]:
    """`(nome, bloco)` de cada linha da Gestão de Controles na página gerada."""
    x = _pagina("08-conexoes.html")
    partes = re.split(r'(?=<div class="gc-item )', x)[1:]
    assert partes, "a Gestão de Controles sumiu da 08 gerada — a régua ficou cega"
    fora = []
    for bloco in partes:
        nome = re.search(r'<span class="gc-nome" data-campo="nome"[^>]*>(.*?)</span>\s*<',
                         bloco, flags=re.S)
        assert nome, "uma linha da Gestão perdeu o nome"
        fora.append((_texto(nome.group(1)), bloco))
    return fora


def _palavra_do_cartao(nome: str) -> str | None:
    """A palavra de transporte que o nome mostra, se mostrar."""
    pedacos = [pedaco.strip() for pedaco in nome.split("•")]
    return next((p for p in pedacos if p in {palavra("usb"), palavra("bt")}), None)


def test_o_canto_da_gestao_nao_conta_mais() -> None:
    """A contagem saiu do canto da Gestão em 26/09/2026, a pedido dela; o dono
    (`interface.conexoes.texto_da_contagem`) segue medido logo abaixo."""
    assert 'data-campo="conta-gestao"' not in _pagina("08-conexoes.html")
    palavras = [_palavra_do_cartao(n) for n, _ in _cartoes_da_gestao()]
    assert any(palavras), "nenhum nome da Gestão traz a palavra de transporte do dono"


@pytest.mark.parametrize(("transportes", "esperada"), [
    (["bt"], "1 controle • 1 {bt}"),
    (["usb", "usb"], "2 controles • 2 {usb}"),
    (["usb", "usb", "bt", "bt"], "4 controles • 2 {usb} • 2 {bt}"),
    ([], "0 controles"),
])
def test_a_contagem_omite_o_transporte_vazio(transportes: list[str], esperada: str) -> None:
    """O transporte sem controle não aparece — a decisão dela de 17/09 no canto
    de cima (`mesa_viva.frase_dos_transportes`) vale para o canto da Gestão.

    MORDIDA: tire os dois `if` de `texto_da_contagem` — o caso de um controle
    só no BT reprova com o `0 USB` na frase.
    """
    controles = [gestao.Controle(uniq=f"c{i}", jogador=i + 1, via=t, bateria=None)
                 for i, t in enumerate(transportes)]
    frase = gestao.texto_da_contagem(controles)
    assert frase == esperada.format(usb=palavra("usb"), bt=palavra("bt"))


@pytest.mark.parametrize("cru", ["usb", "bt", "bluetooth"])
def test_a_tabela_da_gestao_diz_o_que_o_dono_diz(cru: str) -> None:
    """`NOME_DO_TRANSPORTE` é a segunda grafia da tabela do dono — e presa a ela."""
    assert gestao.NOME_DO_TRANSPORTE[cru] == palavra(cru)


@pytest.mark.parametrize("via", ["usb", "bt"])
def test_o_pacote_e_a_gestao_dizem_a_mesma_frase_do_microfone(via: str) -> None:
    """A repintura (`a08_conexoes.caminho_do_microfone`) e a Gestão"""
    from pacotes import a08_conexoes

    do_pacote = _texto(a08_conexoes.caminho_do_microfone(via))
    c = gestao.Controle(uniq="c1", jogador=1, via=via, bateria=None)
    assert c.texto_do_microfone == f"Ligado, {do_pacote}", (
        f"a Gestão diz {c.texto_do_microfone!r} e a repintura {do_pacote!r}")
    assert do_pacote.startswith(f"pelo {palavra(via)} •")


@pytest.mark.parametrize("via", ["usb", "bt"])
def test_a_dica_do_microfone_no_pacote_nao_volta_a_dizer_pelo_cabo(via: str) -> None:
    """A dica que o pacote pinta a cada tique fala a palavra do dono — as DUAS"""
    from pacotes import a08_conexoes

    dica = html.unescape(a08_conexoes.dica_do_microfone(via))
    assert f"<b>pelo {palavra(via)}</b>" in dica, dica[:120]
    velha = re.search(r"\b[Pp]elo (cabo|rádio)\b", dica)
    assert not velha, (
        f"a dica do microfone no {palavra(via)} voltou a dizer {velha.group(0)!r} "
        f"— a palavra do transporte é USB/BT desde 21/09: {dica!r}")


_SOM_PELO_RADIO = ("mapa-audio.saida_dedicada-radio",
                   "mapa-audio.saida_dedicada.payload_do_degrau-radio")
_BRILHO_DAS_LAMPADAS = ("mapa-luz.led_jogador.brilho-cabo",
                        "mapa-luz.led_jogador.brilho-radio")


@pytest.fixture(scope="module")
def pre_marcas() -> dict[str, str]:
    """`{id da célula: a resposta que a mesa pré-marca}` — perguntada à mesa."""
    sys.path.insert(0, str(RAIZ / "scripts"))
    import mesa_de_medicao as med

    testes = med.testes_do_mapa(med.vocabulario_das_pecas())
    fora = {t.id: t.resposta_do_mapa for t in testes}
    faltam = [i for i in (*_SOM_PELO_RADIO, *_BRILHO_DAS_LAMPADAS) if i not in fora]
    assert not faltam, f"a mesa não tem mais as células {faltam} — a régua ficou cega"
    return fora


def _handle_sem_aparelho(*, led_gravavel: bool) -> Any:
    """Um handle da pydualsense sem device, nascido pelo `__init__` de produção."""
    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

    from hefesto_dualsense4unix.core.backend_pydualsense import _PinnedPyDualSense

    h = _PinnedPyDualSense(b"/dev/hidraw-de-bancada", is_edge=False)
    h.audio = DSAudio()
    h.light = DSLight()
    h.triggerL = DSTrigger()
    h.triggerR = DSTrigger()
    h._suppress_leds = led_gravavel
    return h


def test_o_som_pelo_radio_nao_chega_a_bancada_pre_marcado_nada(
        pre_marcas: dict[str, str]) -> None:
    """O produto leva o som de cada controle do rádio pelo `0x35` desde 10/09"""
    for celula in _SOM_PELO_RADIO:
        assert pre_marcas[celula] != "nada", (
            f"a mesa pré-marca «nada» em {celula}, e o produto monta o som do "
            f"rádio desde 10/09 — o mapa voltou a dizer o que o produto não faz")


def test_o_brilho_das_lampadas_e_o_que_o_build_common_manda(
        pre_marcas: dict[str, str]) -> None:
    """A célula do brilho pergunta ao PRODUTO, não ao ensaio de 09/09."""
    from pydualsense.enums import Brightness

    from hefesto_dualsense4unix.core import ds_output_report as rep

    bit = rep.VALID_FLAG2_LED_BRIGHTNESS_CONTROL_ENABLE
    instalado = _handle_sem_aparelho(led_gravavel=True)._build_common(rumble_asserted=False)
    assert instalado[rep.COMMON_VALID_FLAG2] & bit == 0, (
        "com o nó de LED gravável o `flag2` bit0 saiu LIGADO: o produto passou a "
        "mandar o brilho das lâmpadas, e `luz.led_jogador.brilho` no mapa tem de "
        "mudar junto")
    for celula in _BRILHO_DAS_LAMPADAS:
        assert pre_marcas[celula] != "obedeceu", (
            f"a mesa pré-marca «obedeceu» em {celula}, e o produto instalado não "
            f"liga o bit que autoriza o byte — «obedeceu» é o ensaio, não o produto")

    h = _handle_sem_aparelho(led_gravavel=False)
    sem_no = h._build_common(rumble_asserted=False)
    assert sem_no[rep.COMMON_VALID_FLAG2] & bit, (
        "no cabo sem nó gravável o fluxo deixou de autorizar o brilho das "
        "lâmpadas — o `estado_hoje` de `luz.led_jogador.brilho` descreve outro "
        "produto")
    assert sem_no[42] == int(Brightness.low), (
        f"o `common[42]` saiu {sem_no[42]}: todo controle nasce no Fraco (o "
        f"degrau baixo), e é o que o handle leva antes de o perfil escolher")
    h._brilho_das_luzes = 0
    h.light.brightness = Brightness.low
    assert h._build_common(rumble_asserted=False)[42] == 0, (
        "o `common[42]` voltou a sair do `light.brightness` da pydualsense — o "
        "byte tem dono, e é o degrau que o perfil escolheu para o controle")
