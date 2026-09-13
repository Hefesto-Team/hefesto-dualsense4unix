#!/usr/bin/env python3
"""TELA-CALADA-02 — o cartão da Steam diz o ESTADO, e não a história.

A palavra dela, 13/09/2026, sobre as frases de status: *"em todas as abas da
interface"*. A frase que ela colou (*"2 jogos nunca receberam as Opções de
Inicialização do Hefesto na Steam: … Feche a Steam e eu reponho."*) saía por
outra porta além do rodapé: o `data-campo="steam-diz"` do cartão da Steam,
**sem clique**, a cada tique. Eram QUATRO canais, e cada um tem teste aqui:

    canal                                   o que o cartão diz agora
    -------------------------------------   ----------------------------------
    1. a frase da sentinela no corpo        «N jogos sem o atalho»
    2. a notícia da vigia na cabeça         nada (vai ao `[relato]` do stderr)
    3. o aviso do jogo aberto               «Jogo aberto sem o atalho»
    4. «Estou lendo…» na primeira volta     nada (o canto já diz `…`)

A RÉGUA DO QUE FICA, e ela é da sprint: rótulo de ESTADO curto — até seis
palavras, sem primeira pessoa, sem instrução. A régua sabe RECUSAR, e o
:func:`test_a_regua_recusa_as_frases_que_sairam` prova isso contra as quatro
frases de antes, palavra por palavra.

A MORDIDA DE CADA CANAL está na docstring do teste dele, e foi rodada: devolver
a frase reprova o teste daquele canal.

NADA AQUI TOCA A MÁQUINA DELA. O `conftest.py` desvia `HOME` e os quatro
`XDG_*`; o censo é dublado, e a carona está desligada em todo teste.
"""
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

#: Dois jogos de mentira — os rótulos não podem casar com biblioteca nenhuma.
JOGO_A = ("990000011", "JOGO QUE PERDEU")
JOGO_B = ("990000012", "JOGO QUE NUNCA TEVE")

#: O que denuncia primeira pessoa, instrução ou pedido. Cada palavra aqui saiu
#: de uma frase que estava na tela antes desta sprint.
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


# --------------------------------------------------------------------------
# a régua sabe recusar
# --------------------------------------------------------------------------
def test_a_regua_recusa_as_frases_que_sairam(a07):
    """A régua que só sabe passar não é régua: as quatro frases de antes reprovam.

    Se esta régua aceitasse qualquer uma delas, todos os testes de baixo
    passariam com a frase de volta na tela.
    """
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


# --------------------------------------------------------------------------
# canal 1 — a frase da sentinela no corpo do cartão
# --------------------------------------------------------------------------
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
    monkeypatch.setattr(a07, "PORTOES", a07._Portoes())
    monkeypatch.setattr(jl, "pastas_de_atalhos", lambda: [tmp_path])
    monkeypatch.setattr(sw, "censo_do_wrapper", lambda **kw: censo)
    monkeypatch.setattr(pdj, "jogos_instalados", list)
    monkeypatch.setattr(pdj, "pontes_confirmadas", list)
    # A LINHA DO STEAM INPUT É OUTRO ASSUNTO, e fica fora desta medida: ela vem
    # depois do `<br>` e responde a outra pergunta.
    monkeypatch.setattr(a07, "_o_que_a_steam_poe_no_meio", lambda: ("", None))
    lida = a07._ler_do_disco()
    assert len(lida.reparaveis) == 2, "a régua mediria o cartão sem pendência"
    assert sw.frase_do_aviso(censo), "o dublê não tem frase — a régua mediria nada"
    return lida


def test_dois_reparaveis_o_corpo_diz_so_a_contagem(a07, desenho, monkeypatch,
                                                   tmp_path):
    """O corpo diz «2 jogos sem o atalho» — sem «Feche», sem «reponho», sem nomes.

    O caminho é o do produto inteiro: `_ler_do_disco` → `cartoes` →
    `com_o_que_o_daemon_diz` → `Quadro.valores()["steam-diz"]`, que é o valor
    que o piloto escreve no DOM a cada tique.

    MORDIDA (rodada): devolva `_e(lida.frase) or …` ao `cartao_da_steam` (com o
    campo `frase` da `Leitura` e o `frase=sw.frase_do_aviso(censo)` do
    `_ler_do_disco`) e este teste reprova no «Feche».
    """
    lida = _leitura_com_dois_reparaveis(a07, monkeypatch, tmp_path)
    cartoes = a07.com_o_que_o_daemon_diz(desenho.cartoes(lida), None, lida)
    valores = desenho.Quadro(lancadores=cartoes).valores()
    diz = valores["steam-diz"]

    for proibida in ("Feche", "reponho", "Preciso", JOGO_A[1], JOGO_B[1]):
        assert proibida.lower() not in diz.lower(), (
            f"o corpo do cartão da Steam narra: achei {proibida!r} em {diz!r}")
    linhas = _linhas(diz)
    assert linhas == ["2 jogos sem o atalho"], (
        f"o corpo não é o rótulo de estado: {linhas!r}")
    assert all(_e_rotulo_de_estado(x) for x in linhas)

    # O QUE NÃO SE PERDEU: os nomes na lista, o selo e o «Consertar».
    assert JOGO_A[1] in valores["steam-fora"] and JOGO_B[1] in valores["steam-fora"], (
        "os nomes dos jogos sumiram da tela junto com a frase — era para sair "
        "só a narração")
    assert desenho.SELOS["warn"] in valores["steam-selo"]
    assert 'data-gesto="consertar"' in valores["steam-acoes"]


def test_o_consertar_continua_chegando_a_pergunta_de_fechar_a_steam(
        a07, desenho, monkeypatch, tmp_path):
    """Calar o corpo não pode calar a RECUSA nem apagar a saída pela Steam.

    Com a Steam aberta o «Consertar» recusa com a frase da sentinela — é a
    resposta a um CLIQUE, e ela fica. E o botão «Posso fechar a Steam…»
    continua no cartão, que é o caminho que a recusa aponta.
    """
    import pacotes

    from hefesto_dualsense4unix.integrations import sentinela_do_wrapper as sw

    lida = _leitura_com_dois_reparaveis(a07, monkeypatch, tmp_path)
    assert a07.PORTOES.steam_aberta and not a07.PORTOES.jogo_aberto
    steam = a07.com_o_que_o_daemon_diz(desenho.cartoes(lida), None, lida)[0]
    rotulos = [x.rotulo for x in steam.acoes]
    assert "Consertar" in rotulos and a07.PERGUNTA_DA_STEAM in rotulos, rotulos

    censo = sw.Censo(
        faltantes=[sw.JogoSemWrapper(JOGO_A[0], JOGO_A[1], None,
                                     sw.MOTIVO_REGRESSAO, "/dev/null")],
        steam_aberta=True)
    monkeypatch.setattr(sw, "reparar_ou_adiar",
                        lambda *a, **kw: (sw.REPARO_ADIADO_STEAM, censo, None))
    consertar = pacotes.gesto_da_pagina(PAGINA, "consertar")
    ctx = pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})
    with pytest.raises(RuntimeError, match="Steam"):
        consertar(ctx, {"v": "steam"}, None)


# --------------------------------------------------------------------------
# canal 2 — a notícia da vigia
# --------------------------------------------------------------------------
FRASE_DA_VIGIA = ("Reposta a Opção de Inicialização do Hefesto em 1 jogo da "
                  "Steam: JOGO QUE PERDEU.")


def test_a_noticia_da_vigia_vai_ao_relato_e_nao_ao_cartao(a07, desenho, capsys):
    """O que a vigia repôs vai ao `[relato]` do stderr; o cartão fica igual.

    MORDIDA (rodada): some a frase guardada pelo `_anotar` à `cabeca` de
    `com_o_que_o_daemon_diz` e este teste reprova — o cartão devolvido deixa
    de ser o mesmo e passa a conter a frase.
    """
    antes = desenho.cartoes(None)
    a07.VIGIA_DA_STEAM._anotar(FRASE_DA_VIGIA)
    depois = a07.com_o_que_o_daemon_diz(list(antes), None, None)
    assert FRASE_DA_VIGIA not in depois[0].diz, (
        "a notícia da vigia voltou ao corpo do cartão da Steam")
    assert depois == antes, "a notícia mudou o cartão sem mudar o estado"
    erro = capsys.readouterr().err
    assert "[relato]" in erro and FRASE_DA_VIGIA in erro, (
        "a vigia repôs e não escreveu o relato — o diário da janela ficaria "
        "sem saber que o Hefesto cumpriu")


def test_o_tique_que_repoe_repinta_pelo_estado_e_nao_pela_frase(
        a07, desenho, monkeypatch, capsys):
    """O tique que repõe ESQUECE a leitura — é isso que muda o cartão.

    Sem a notícia, quem diz que o Hefesto cumpriu é o próprio cartão, relido
    com o atalho de volta. O `esquecer()` é a metade que sobra, e ele tem de
    continuar sendo chamado.
    """
    from hefesto_dualsense4unix.app.actions import carona_do_wrapper as cdw

    esquecidas: list[int] = []
    monkeypatch.setattr(a07.VIGIA, "esquecer", lambda: esquecidas.append(1))
    monkeypatch.setattr(
        cdw, "passada",
        lambda **kw: cdw.ResultadoDaCarona("reparo_feito", FRASE_DA_VIGIA,
                                           frozenset(), False))
    assert a07.VIGIA_DA_STEAM.tique() is False
    assert esquecidas == [1]
    assert FRASE_DA_VIGIA in capsys.readouterr().err
    lida = desenho.Leitura(com_wrapper=("1",), instalados=1)
    steam = a07.com_o_que_o_daemon_diz(desenho.cartoes(lida), None, lida)[0]
    assert FRASE_DA_VIGIA not in steam.diz


# --------------------------------------------------------------------------
# canal 3 — o aviso do jogo aberto
# --------------------------------------------------------------------------
def test_o_aviso_do_jogo_aberto_e_um_rotulo_de_estado(a07, desenho):
    """Jogo aberto sem o atalho: o cartão diz o ESTADO, e o botão se explica.

    A escolha, medida na foto do piloto: sem nada escrito, o «Não perguntar
    para este jogo» aparece no cartão sem dizer sobre o quê. O rótulo é o
    estado que o botão dispensa — cinco palavras, sem «Reponho», sem pedido.

    MORDIDA (rodada): devolva `_texto(texto)` (a frase da janela velha) ao
    retorno de `aviso_do_jogo_aberto` e este teste reprova.
    """
    from hefesto_dualsense4unix.app.actions import home_actions as ha

    lida = desenho.Leitura(com_wrapper=("1",), instalados=1)
    steam = a07.com_o_que_o_daemon_diz(desenho.cartoes(lida), SEM_ATALHO, lida)[0]
    assert ha.WRAPPER_MISSING_TEXT not in steam.diz, (
        "a frase longa do jogo aberto voltou ao cartão, a cada tique")
    linhas = _linhas(steam.diz)
    assert linhas and linhas[0] == a07.JOGO_ABERTO_SEM_O_ATALHO, linhas
    assert _e_rotulo_de_estado(linhas[0])
    marcacao = desenho.acoes_html(steam)
    assert 'data-gesto="nao-perguntar"' in marcacao and 'data-v="3357650"' in marcacao, (
        "o rótulo acendeu sem o botão que o dispensa")


def test_sem_jogo_aberto_o_rotulo_nao_acende(a07, desenho, monkeypatch):
    """Quem decide SE acende continua sendo o dono — o rótulo só troca o texto."""
    from hefesto_dualsense4unix.app.actions import home_actions as ha

    monkeypatch.setattr(ha, "wrapper_banner_text", lambda s: "")
    lida = desenho.Leitura(com_wrapper=("1",), instalados=1)
    steam = a07.com_o_que_o_daemon_diz(desenho.cartoes(lida), SEM_ATALHO, lida)[0]
    assert a07.JOGO_ABERTO_SEM_O_ATALHO not in steam.diz
    assert 'data-gesto="nao-perguntar"' not in desenho.acoes_html(steam)


# --------------------------------------------------------------------------
# canal 4 — «Estou lendo…» na primeira volta
# --------------------------------------------------------------------------
def test_enquanto_le_o_corpo_do_cartao_cala(desenho):
    """Na primeira meia volta o corpo não mostra texto — e não vira travessão.

    O canto do cartão já diz que está lendo (`AINDA_LENDO`). Um `""` no corpo
    viraria `—` no `escrever()` do BOOTSTRAP; o comentário não.

    MORDIDA (rodada): devolva *«Estou lendo a sua biblioteca da Steam…»* ao
    ramo `lida is None` de `cartao_da_steam` e este teste reprova.
    """
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
    """O literal da página — o que ela vê antes do primeiro tique — também cala.

    As DUAS: a bancada que o gerador escreve e a publicada que o produto
    renderiza. Curar só o desenho deixa a tela dela igual (*curar o mockup não
    cura o produto*).
    """
    texto = arquivo.read_text(encoding="utf-8")
    achado = re.search(r'data-campo="steam-diz"[^>]*>(.*?)</div>', texto,
                       flags=re.DOTALL)
    assert achado, f"{arquivo.name} sem o endereço `steam-diz`"
    assert _visivel(achado.group(1)) == "", (
        f"{arquivo.parent.name}/{arquivo.name} nasce narrando: "
        f"{_visivel(achado.group(1))!r}")
    assert "Estou lendo" not in texto
