#!/usr/bin/env python3
"""TELA-CALADA-02 — o cartão da Steam diz o ESTADO, e não a história."""
from __future__ import annotations

import html
import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

PAGINA = "07-lancadores.html"

#: O `state_full` de quando HÁ jogo aberto e ele não passou pelo atalho.
SEM_ATALHO: dict[str, Any] = {
    "gamepad_emulation": {"enabled": True, "wrapper_used": False},
    "window_detect_last_class": "steam_app_3357650",
}

JOGO_A = ("990000011", "JOGO QUE PERDEU")
JOGO_B = ("990000012", "JOGO QUE NUNCA TEVE")

_NARRA = re.compile(
    r"\b(eu|me|reponho|repor|preciso|vou|estou|posso|consegui|feche|fechar|"
    r"clique|use|abra|mexo|lendo)\b",
    re.IGNORECASE,
)


@pytest.fixture(scope="module")
def a07():
    """O módulo em que os GESTOS REGISTRADOS vivem — ver a régua irmã da 07."""
    import pacotes

    fn = pacotes.gesto_da_pagina(PAGINA, "procurar")
    assert fn is not None, f"{PAGINA}:procurar não tem dono — a régua ficaria cega"
    return sys.modules[fn.__module__]


@pytest.fixture(scope="module")
def desenho():
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as dl

    return dl


def _visivel(marcacao: str) -> str:
    """O texto que a tela MOSTRA: sem comentário, sem etiqueta, espaço normalizado."""
    sem_comentario = re.sub(r"<!--.*?-->", "", marcacao, flags=re.DOTALL)
    sem_etiqueta = re.sub(r"<[^>]+>", " ", sem_comentario)
    return " ".join(html.unescape(sem_etiqueta).split())


def _e_rotulo_de_estado(texto: str) -> bool:
    """Até seis palavras, e nenhuma que narre, peça ou mande."""
    palavras = texto.split()
    return 0 < len(palavras) <= 6 and not _NARRA.search(texto)


def _linhas(marcacao: str) -> list[str]:
    """As linhas visíveis de um corpo de cartão, separadas pelo `<br>`."""
    return [x for x in (_visivel(p) for p in re.split(r"<br\s*/?>", marcacao)) if x]


_CONTADOR = re.compile(r"^◆ \d+ jogos? já sabem? por onde entrar$")


def _estados(marcacao: str) -> list[str]:
    """As linhas do corpo que são ESTADO — o contador fica de fora."""
    return [x for x in _linhas(marcacao) if not _CONTADOR.match(x)]


def test_a_regua_recusa_as_frases_que_sairam(a07):
    """A régua que só sabe passar não é régua: as quatro frases de antes reprovam."""
    from hefesto_dualsense4unix.app.actions import home_actions as ha
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw

    censo = sw.Censo(
        faltantes=[sw.JogoSemWrapper(JOGO_A[0], JOGO_A[1], None,
                                     sw.MOTIVO_REGRESSAO, "/dev/null")],
        steam_aberta=True)
    antes = (
        sw.frase_do_aviso(censo),
        ha.WRAPPER_MISSING_TEXT,
        "Estou lendo a sua biblioteca da Steam…",
        "Reposta a Opção de Inicialização do Hefesto em 1 jogo da Steam: X.",
    )
    for frase in antes:
        assert frase and not _e_rotulo_de_estado(frase), (
            f"a régua aceitou uma frase que narra: {frase[:70]!r}")
    for rotulo in ("2 jogos sem o atalho", "1 jogo sem o atalho",
                   a07.JOGO_ABERTO_SEM_O_ATALHO):
        assert _e_rotulo_de_estado(rotulo), f"a régua recusou um estado: {rotulo!r}"


def _leitura_com_dois_reparaveis(a07, monkeypatch, tmp_path):
    """A leitura que a VIGIA monta — pelo `_ler_do_disco` de verdade, censo dublado."""
    from hefesto_dualsense4unix.integrations import jogos_locais as jl
    from hefesto_dualsense4unix.integrations import prontuario_dos_jogos as pdj
    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw

    censo = sw.Censo(
        com_wrapper=["7"],
        faltantes=[
            sw.JogoSemWrapper(JOGO_A[0], JOGO_A[1], "-x", sw.MOTIVO_REGRESSAO,
                              "/dev/null"),
            sw.JogoSemWrapper(JOGO_B[0], JOGO_B[1], None, sw.MOTIVO_NOVO,
                              "/dev/null"),
        ],
        steam_aberta=True,
    )
    monkeypatch.setattr(jl, "pastas_de_atalhos", lambda: [tmp_path])
    monkeypatch.setattr(sw, "censo_do_wrapper", lambda **kw: censo)
    monkeypatch.setattr(pdj, "jogos_instalados", list)
    monkeypatch.setattr(pdj, "pontes_confirmadas", list)
    lida = a07._ler_do_disco()
    assert len(lida.reparaveis) == 2, "a régua mediria o cartão sem pendência"
    assert sw.frase_do_aviso(censo), "o dublê não tem frase — a régua mediria nada"
    return lida


def test_dois_reparaveis_o_corpo_diz_so_a_contagem(a07, desenho, monkeypatch,
                                                   tmp_path):
    """O corpo diz «2 jogos sem o atalho» — sem «Feche», sem «reponho», sem nomes."""
    lida = _leitura_com_dois_reparaveis(a07, monkeypatch, tmp_path)
    cartoes = a07.com_o_que_o_daemon_diz(desenho.cartoes(lida), None, lida)
    valores = desenho.Quadro(lancadores=cartoes).valores()
    diz = valores["steam-diz"]

    for proibida in ("Feche", "reponho", "Preciso", JOGO_A[1], JOGO_B[1]):
        assert proibida.lower() not in diz.lower(), (
            f"o corpo do cartão da Steam narra: achei {proibida!r} em {diz!r}")
    linhas = _estados(diz)
    assert linhas == ["2 jogos sem o atalho"], (
        f"o corpo não é o rótulo de estado: {linhas!r}")
    assert all(_e_rotulo_de_estado(x) for x in linhas)

    assert JOGO_A[1] in valores["steam-fora"] and JOGO_B[1] in valores["steam-fora"], (
        "os nomes dos jogos sumiram da tela junto com a frase — era para sair "
        "só a narração")
    assert desenho.SELOS["warn"] in valores["steam-selo"]


def test_o_aviso_do_jogo_aberto_e_um_rotulo_de_estado(a07, desenho):
    """Jogo aberto sem o atalho: o cartão diz o ESTADO — cinco palavras."""
    from hefesto_dualsense4unix.app.actions import home_actions as ha

    lida = desenho.Leitura(com_wrapper=("1",), instalados=1)
    steam = a07.com_o_que_o_daemon_diz(desenho.cartoes(lida), SEM_ATALHO, lida)[0]
    assert ha.WRAPPER_MISSING_TEXT not in steam.diz, (
        "a frase longa do jogo aberto voltou ao cartão, a cada tique")
    linhas = _linhas(steam.diz)
    assert linhas and linhas[0] == a07.JOGO_ABERTO_SEM_O_ATALHO, linhas
    assert _e_rotulo_de_estado(linhas[0])
    assert 'data-gesto="nao-perguntar"' not in desenho.acoes_html(steam), (
        "o «Não perguntar» voltou ao cartão — um botão que os outros sete não têm")


def test_sem_jogo_aberto_o_rotulo_nao_acende(a07, desenho, monkeypatch):
    """Quem decide SE acende continua sendo o dono — o rótulo só troca o texto."""
    from hefesto_dualsense4unix.app.actions import home_actions as ha

    monkeypatch.setattr(ha, "wrapper_banner_text", lambda s: "")
    lida = desenho.Leitura(com_wrapper=("1",), instalados=1)
    steam = a07.com_o_que_o_daemon_diz(desenho.cartoes(lida), SEM_ATALHO, lida)[0]
    assert a07.JOGO_ABERTO_SEM_O_ATALHO not in steam.diz
    assert 'data-gesto="nao-perguntar"' not in desenho.acoes_html(steam)


def test_enquanto_le_o_corpo_do_cartao_cala(desenho):
    """Na primeira meia volta o corpo não mostra texto — e não vira travessão."""
    steam = desenho.cartoes(None)[0]
    assert steam.diz, "corpo vazio vira travessão na tela"
    assert _visivel(steam.diz) == "", (
        f"o corpo do cartão narra enquanto lê: {_visivel(steam.diz)!r}")
    assert steam.jogos == desenho.AINDA_LENDO


@pytest.mark.parametrize("arquivo", [
    RAIZ / "mockup" / PAGINA,
    INTERFACE / "paginas" / PAGINA,  # (noqa-acento): nome de pasta
])
def test_a_pagina_nasce_com_o_corpo_calado(arquivo):
    """O literal da página — o que ela vê antes do primeiro tique — também cala."""
    texto = arquivo.read_text(encoding="utf-8")
    achado = re.search(r'data-campo="steam-diz"[^>]*>(.*?)</div>', texto,
                       flags=re.DOTALL)
    assert achado, f"{arquivo.name} sem o endereço `steam-diz`"
    assert _visivel(achado.group(1)) == "", (
        f"{arquivo.parent.name}/{arquivo.name} nasce narrando: "
        f"{_visivel(achado.group(1))!r}")
    assert "Estou lendo" not in texto


def test_os_tres_ramos_que_narravam_viram_rotulo_de_estado(desenho):
    """Não localizada · biblioteca ilegível · jogo sem o atalho: cada linha é estado."""
    ramos = {
        "não localizada": desenho.Leitura(onde_estao=(("steam", ""),)),
        "biblioteca ilegível": desenho.Leitura(erros=("o vdf sumiu",),
                                               onde_estao=(("steam", ""),)),
        "jogo sem o atalho": desenho.Leitura(
            reparaveis=((JOGO_A[0], JOGO_A[1], "nunca recebeu o atalho"),)),
    }
    for nome, lida in ramos.items():
        linhas = _estados(desenho.cartao_da_steam(lida).diz)
        assert linhas, f"o ramo {nome!r} ficou sem corpo — vazio vira travessão"
        narram = [x for x in linhas if not _e_rotulo_de_estado(x)]
        assert not narram, f"o ramo {nome!r} narra: {narram!r}"
