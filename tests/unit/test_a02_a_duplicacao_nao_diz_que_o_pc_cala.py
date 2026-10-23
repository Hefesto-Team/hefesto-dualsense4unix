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
    return dict(fora["cards"][entry["uniq"]])


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


@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("backend", ["uhid", "uinput"])
def test_a_regra_vale_para_todo_jogador_transporte_e_modo(
        jogador: int, transporte: str, backend: str) -> None:
    """De P1 a P4, no cabo e no rádio, no DualSense e no Xbox: rota 2 + `mix` é «jogo» com a marca.

    MORDE: a mesma do primeiro caso; aqui o que se prova é que nenhuma dessas chaves entra na regra.
    """
    entry = {**_entrada(BYTE_JOGO, "mix"), "uniq": f"aa:bb:cc:00:00:0{jogador}", "player": jogador,
             "transport": transporte, "vpad_backend": backend, "is_primary": jogador == 1}
    card = _card(entry)
    assert card["alto-rota"] == "jogo"
    assert card["alto-junto"] == "sim"


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


def _fileira(doc: str) -> str:
    """O HTML da fileira do som do primeiro card (da abertura de `.rota trio` ao seu fim)."""
    ini = doc.index('<div class="rota trio">')
    return doc[ini:doc.index("</div>", ini)]


def _botoes_da_fileira(doc: str) -> dict[str, str]:
    """O HTML de cada botão da fileira do primeiro card: `{rota: html do botão}`."""
    return {m.group(1): m.group(0) for m in re.finditer(
        r'<button[^>]*data-rota="(\w+)".*?</button>', _fileira(doc), re.S)}


def _dica(html: str) -> str:
    achado = re.search(r'data-dica="([^"]+)"', html)
    assert achado is not None, html
    return achado.group(1)


def test_o_desenho_da_marca_envolve_so_o_botao_jogo_e_a_dica_a_explica() -> None:
    """No desenho: o invólucro do botão «jogo» carrega o endereço `alto-junto`; os outros não.

    A marca é pintada pela folha (sem nó de texto e sem dica própria: o alvo que abre dica tem de
    ter 24px, e a régua dos alvos reprova o que não tem). A dica do botão «jogo» a explica e não
    diz que o PC cala; a do botão do PC mudo continua dizendo que ele fica mudo (a rota 3).
    """
    doc = onde.pagina("02-controles.html").read_text(encoding="utf-8")
    fileira = _fileira(doc)
    botoes = _botoes_da_fileira(doc)
    assert set(botoes) == {"jogo", "pc", "nada"}
    assert fileira.count('data-campo="alto-junto"') == 1
    envolucro = re.search(
        r'<span class="fonte-mix[^"]*"[^>]*data-campo="alto-junto"[^>]*>\s*<button'
        r'[^>]*data-rota="jogo"', fileira)
    assert envolucro is not None, "o invólucro da marca não é pai do botão `jogo`"
    assert 'data-hef-alvo="classe"' in envolucro.group(0)
    assert 'data-hef-quando="sim"' in envolucro.group(0)
    jogo = _dica(botoes["jogo"])
    assert "também toca no controle" in jogo and "mudo" not in jogo
    assert "mudo" in _dica(botoes["pc"])


def test_a_folha_pinta_a_marca_que_o_gerador_declara() -> None:
    """O desenho em disco vem do gerador: a sigla da folha é a constante, e a dica a cita."""
    doc = onde.pagina("02-controles.html").read_text(encoding="utf-8")
    marca = a02_gerador.MARCA_SIGLA_JUNTO
    assert f'.fonte-mix.junto button.on::after{{content:"{marca}"' in doc
    assert a02_gerador.MARCA_SIGLA_JUNTO in a02_gerador.DICA_SO_OS_EFEITOS
    assert a02_gerador.DICA_SO_OS_EFEITOS in doc
