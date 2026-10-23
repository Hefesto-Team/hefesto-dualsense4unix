#!/usr/bin/env python3
"""A fileira do som da aba 02 não chama a duplicação do Terror de «o PC fica mudo».

O Terror, no Modo automático, escreve a fonte `mix` com a rota 2 (o «Ouvir junto»): o som do PC toca
no controle e continua no PC. A regra velha acendia «Canais sonoros apenas no DualSense» (a rota 3,
cuja dica diz que o PC fica mudo) por cima da rota que o controle tem. Agora o botão aceso segue a
rota, e a fonte `mix` aparece como uma marca no botão aceso.
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import aba02 as a02_gerador
from hefesto_dualsense4unix.app import audio_saida
from hefesto_dualsense4unix.interface import onde
from pacotes import Contexto
from pacotes import a02_controles as a02

UNIQ = "aa:bb:cc:00:00:01"
SINK = "alsa_output.usb-Sony-DualSense"
BYTE_JOGO = audio_saida.BYTE_SONS_DO_JOGO
BYTE_PC = audio_saida.BYTE_TODO_O_SOM_DO_PC
BYTE_NADA = audio_saida.BYTE_NADA_NO_CONTROLE

BASE: dict[str, Any] = {
    "uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
    "battery_pct": 50, "is_primary": True, "inputs": {"buttons": []},
}


@pytest.fixture(autouse=True)
def _camada_1_parada(monkeypatch: pytest.MonkeyPatch) -> None:
    """A camada 1 não conversa com o PipeWire desta máquina durante a suíte."""
    monkeypatch.setattr(a02, "_CAMADA_1", {})
    monkeypatch.setattr(a02, "_CAMADA_1_EM_VOO", [True])
    monkeypatch.setattr(a02, "_CAMADA_1_QUANDO", [0.0])


def _entrada(rota: int | None, fonte: str | None) -> dict[str, Any]:
    speaker: dict[str, Any] = {"volume": 80, "muted": False}
    if rota is not None:
        speaker["rota"] = rota
    if fonte is not None:
        speaker["fonte"] = fonte
    return {**BASE, "speaker": speaker}


def _card(entry: dict[str, Any]) -> dict[str, Any]:
    """Os campos do card, com o DESENHO DE HOJE (o mockup) endereçado."""
    doc = onde.pagina("02-controles.html").read_text(encoding="utf-8")
    a02._ENDERECOS = frozenset(re.findall(r'data-campo="([^"]+)"', doc))
    try:
        fora = a02.pacote(Contexto(state={}, mesa=[], conectados=[entry], estados={}))
    finally:
        a02._ENDERECOS = None
    return dict(fora["cards"][UNIQ])


def _no_controle() -> None:
    """A camada 1 diz que a saída padrão é o controle: o byte 3 pode acender."""
    a02._CAMADA_1[UNIQ] = audio_saida.RotaDasDuasCamadas(
        byte=BYTE_PC, sink_do_controle=SINK, sink_padrao=SINK)


def test_rota_2_com_mix_acende_jogo_e_nao_pc() -> None:
    """O Terror (rota 2 + `mix`) acende «Sons do jogo», que é o que a rota faz.

    MORDE: devolva a linha `return ROTA_TUDO_NO_CONTROLE if fonte_do_controle(entry) == "mix"`
    ao `aceso_da_fileira` e este caso reprova com `'pc' != 'jogo'`.
    """
    entry = _entrada(BYTE_JOGO, "mix")
    assert a02.aceso_da_fileira(UNIQ, entry) == "jogo"
    assert _card(entry)["alto-rota"] == "jogo"


def test_rota_2_com_mix_leva_a_marca_e_rota_2_com_sfx_nao() -> None:
    """A fonte `mix` aparece no botão aceso; sem `mix` a marca não existe.

    MORDE: faça `junto_na_tela` devolver `""` e o primeiro `assert` reprova.
    """
    com = _card(_entrada(BYTE_JOGO, "mix"))
    sem = _card(_entrada(BYTE_JOGO, "sfx"))
    sem_fonte = _card(_entrada(BYTE_JOGO, None))
    assert com["alto-junto"] == "sim"
    assert sem["alto-rota"] == sem_fonte["alto-rota"] == "jogo"
    assert sem["alto-junto"] == "" and sem_fonte["alto-junto"] == ""


def test_rota_3_com_mix_acende_pc_sem_a_marca() -> None:
    """A rota 3 cala o PC de verdade: o botão é o do PC mudo, e não há «junto» a mostrar.

    MORDE: tire a guarda `aceso == "jogo"` do `junto_na_tela` e a marca aparece no botão errado.
    """
    _no_controle()
    entry = _entrada(BYTE_PC, "mix")
    assert a02.aceso_da_fileira(UNIQ, entry) == "pc"
    card = _card(entry)
    assert card["alto-rota"] == "pc"
    assert card["alto-junto"] == ""


def test_rota_nada_com_mix_continua_nada() -> None:
    """O `mix` que sobrou num perfil não desfaz o «apenas no PC»."""
    entry = _entrada(BYTE_NADA, "mix")
    assert a02.aceso_da_fileira(UNIQ, entry) == "nada"
    assert _card(entry)["alto-junto"] == ""


def test_sem_rota_publicada_o_mix_nao_acende_botao_nenhum() -> None:
    """Sem a rota o controle não afirma nada: o `mix` sozinho não escolhe botão."""
    entry = _entrada(None, "mix")
    assert a02.aceso_da_fileira(UNIQ, entry) == ""
    assert _card(entry)["alto-junto"] == ""


def _botoes_da_fileira(doc: str) -> dict[str, str]:
    """O HTML de cada botão da fileira do primeiro card: `{rota: html do botão}`."""
    fila = doc[doc.index('<div class="rota trio">'):]
    fila = fila[:fila.index("</div>")]
    return {m.group(1): m.group(0) for m in re.finditer(
        r'<button[^>]*data-rota="(\w+)".*?</button>', fila, re.S)}


def test_o_desenho_da_marca_mora_so_no_botao_jogo_e_a_dica_diz_o_que_acontece() -> None:
    """No desenho: a marca é filha do botão «jogo», o endereço é `alto-junto`, e a frase é dica.

    A dica do botão do PC mudo continua dizendo que o PC fica mudo (é o que a rota 3 faz); a da
    marca diz que o som do PC também toca no controle, e nenhuma frase nova ocupa a tela (a marca é
    uma sigla, e a frase mora no `data-dica`).
    """
    doc = onde.pagina("02-controles.html").read_text(encoding="utf-8")
    botoes = _botoes_da_fileira(doc)
    assert set(botoes) == {"jogo", "pc", "nada"}
    assert 'data-campo="alto-junto"' in botoes["jogo"]
    assert 'data-campo="alto-junto"' not in botoes["pc"] + botoes["nada"]
    marca = re.search(r'<span[^>]*data-campo="alto-junto"[^>]*>', botoes["jogo"])
    assert marca is not None
    dica = re.search(r'data-dica="([^"]+)"', marca.group(0))
    assert dica is not None and "PC também toca no controle" in dica.group(1)
    assert "mudo" not in dica.group(1)
    assert "mudo" not in re.search(r'data-dica="([^"]+)"', botoes["jogo"]).group(1)
    assert "mudo" in re.search(r'data-dica="([^"]+)"', botoes["pc"]).group(1)


def test_o_gerador_e_o_mockup_dizem_a_mesma_marca() -> None:
    """O desenho em disco vem do gerador: a constante do gerador é a dica da marca no mockup."""
    doc = onde.pagina("02-controles.html").read_text(encoding="utf-8")
    assert a02_gerador.DICA_JUNTO_NO_CONTROLE in doc
    assert a02_gerador.MARCA_SIGLA_JUNTO in _botoes_da_fileira(doc)["jogo"]
