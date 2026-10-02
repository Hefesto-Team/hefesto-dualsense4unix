#!/usr/bin/env python3
"""O "STATUS DO MODO" DIZ O QUE O DAEMON DIZ — ou não diz nada."""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.interface import onde

PAGINA = "06-navegacao.html"  # (noqa-acento) nome de arquivo

UNIQ = "aa:bb:cc:00:00:01"
FALSO = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
         "battery_pct": 90, "is_primary": True, "inputs": {}, "audio": {},
         "speaker": {}}
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "USB", "cor": "cosmic-red", "mascara": "DualSense"}]


@pytest.fixture(scope="module")
def bancada() -> str:
    return onde.pagina(PAGINA).read_text(encoding="utf-8")


def _mesa(rato: dict | None) -> dict:
    """O que o pacote manda para a tela, com este bloco `mouse_emulation`."""
    from pacotes import Contexto
    from pacotes import a06_navegacao as mod

    estado: dict = {"active_profile": "regua", "controllers": [FALSO]}
    if rato is not None:
        estado["mouse_emulation"] = rato
    ctx = Contexto(state=estado, mesa=MESA, conectados=[FALSO])
    return mod.pacote(ctx)["mesa"]


def test_o_interruptor_tem_os_dois_enderecos(bancada: str) -> None:
    """A classe no rótulo e a palavra no `.txt`, com o MESMO `data-campo`."""
    assert bancada.count('data-campo="rato-ligado"') == 2, (
        "o 'Status do Modo' precisa dos dois endereços: a classe no rótulo "
        "(`data-hef-alvo=\"classe\"`) e a palavra no `.txt`. Com um só, ou a "
        "cor não acende ou a palavra não muda.")
    rotulo = re.search(r"<label[^>]*class=\"tog\"[^>]*>", bancada)
    assert rotulo is not None, "o rótulo `.tog` sumiu do desenho"
    marcacao = rotulo.group(0)
    assert 'data-hef-alvo="classe"' in marcacao, marcacao
    assert 'data-hef-classe="ligado"' in marcacao, marcacao
    assert 'data-hef-quando="Ligado"' in marcacao, marcacao
    assert 'data-gesto="modo"' in marcacao, (
        "o `data-gesto` saiu do rótulo — quem recebe o clique é ele, e é dele "
        f"que o `closest()` do piloto parte: {marcacao}")


def test_a_caixa_de_marcar_nao_volta(bancada: str) -> None:
    """Sem `<input>`, sem `:checked`, sem palavra de CSS."""
    assert 'id="st-modo"' not in bancada and 'class="tog-in"' not in bancada, (
        "voltou o `<input type=\"checkbox\">` do 'Status do Modo': clicar no "
        "rótulo vira a caixa no DOM mesmo quando o gesto RECUSA, e nada a "
        "devolve.")
    assert "content:'Ligado'" not in bancada, (
        "a palavra do interruptor voltou a sair de um `content:` de CSS — o "
        "piloto não escreve pseudoelemento, e a palavra ficaria a do desenho "
        "para sempre.")
    assert re.search(r'class="txt"[^>]*>—<', bancada), (
        "o `.txt` do 'Status do Modo' não nasce mais em '—'. Antes do primeiro "
        "tique ninguém perguntou ao Hefesto: qualquer das duas palavras é uma "
        "afirmação, e foi assim que a tela dizia 'Ligado' com a emulação "
        "desligada.")


@pytest.mark.parametrize("ligado, palavra", [(True, "Ligado"), (False, "Desligado")])
def test_a_palavra_e_a_do_daemon(ligado: bool, palavra: str) -> None:
    """Os dois lados chegam à tela, e a palavra é a que acende a classe.

    A palavra é DUAS coisas: o texto do `.txt` e o gatilho do
    `data-hef-quando="Ligado"` do rótulo. Uma sem a outra acenderia a cor sem a
    palavra, ou o contrário — por isso as duas saem das mesmas constantes.
    """
    mesa = _mesa({"enabled": ligado, "speed": 6, "scroll_speed": 1})
    assert mesa["rato-ligado"] == palavra, (
        f"com `enabled={ligado}` o pacote mandou {mesa['rato-ligado']!r}")


def test_a_palavra_que_acende_a_classe_e_a_do_desenho(bancada: str) -> None:
    """O `data-hef-quando` do desenho é a MESMA string que o pacote emite.

    Duas escritas do mesmo rótulo é como o desenho e o produto divergem
    calados: bastaria o desenho dizer `ligado` (minúsculo) para a cor nunca
    acender, com a palavra certa na tela e ninguém acusando.
    """
    from pacotes import a06_navegacao as mod

    assert f'data-hef-quando="{mod.LIGADO}"' in bancada, (
        f"o desenho acende a classe por outra palavra que não {mod.LIGADO!r} — "
        "a cor e o texto se separaram.")


def test_sem_o_bloco_do_daemon_a_tela_nao_afirma_lado_nenhum() -> None:
    """Chave ausente = a pintura não toca no interruptor."""
    assert "rato-ligado" not in _mesa(None), (
        "o pacote afirmou o lado do interruptor sem o bloco `mouse_emulation` "
        "do daemon — é a mentira antiga com o sinal trocado.")
    assert "rato-ligado" not in _mesa({"speed": 6}), (
        "sem `enabled` no bloco o pacote afirmou um lado — `bool(None)` vira "
        "'Desligado', que é dizer o que não se sabe.")


def test_o_endereco_saiu_da_lista_de_orfaos() -> None:
    """Declaração que sobrevive à cura é a régua se desligando sozinha."""
    from pacotes import a06_navegacao as mod

    assert "rato-ligado" not in mod.SEM_ENDERECO, (
        "`rato-ligado` tem endereço no desenho desde 03/09/2026 e continua "
        "declarado como órfão.")


