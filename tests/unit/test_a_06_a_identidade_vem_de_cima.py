#!/usr/bin/env python3
"""A RÉGUA DA IDENTIDADE NA ABA 06: o controle da tela é o da MESA, nunca o do desenho.

A LEI É DO USUÁRIO, 03/09/2026:

    "se no topo tá mostrando controle white player 1, então cada aba vai usar
    os controles lá de cima. Não mistura com a info dos mockups. (…) Por isso
    temos o mapa pra servir como variável de identificação"

(A frase elidida — *"Cada feature faz referência ao controle conectado"* — está
inteira em `docs/process/sprints/arquivados/`, na
`2026-09-03-IDENTIDADE-VEM-DE-CIMA-01-a-fita-manda-nas-dez-abas.md`.
Ela sai daqui porque a palavra de produto vem sem o acento e o portão `acentuacao`
varre este arquivo; a elisão é honesta e a fonte fica apontada.)

O QUE ESTA ABA MOSTRAVA, medido em 03/09/2026 com os dois controles do usuário na
mesa e o daemon no ar — a fita, os dois cartões e as duas dicas das telas de
botões, todos ao lado de um cabeçalho que já contava certo::

    a mesa VIVA     P1 · White · USB        P2 · (cor não lida) · BT
    a fita da 06    P1 · Cosmic Red · USB   P2 · Starlight Blue · BT
    os cartões      P1 • Cosmic Red         P2 • Starlight Blue
    as duas dicas   "Valem para … o P1 Cosmic Red USB"

`scripts/check_identidade_vem_de_cima.py --bancada --aba 06` contava **16**
valores congelados. Esta régua é a metade que roda no CI — sem GTK, sem display
e sem daemon — e ela cobra as DUAS coisas que o número 16 não separa:

1. **o endereço existe** na bancada, em cada lugar onde a aba diz identidade;
2. **o pacote escreve nele** — e escreve o que LEU, não o que o desenho cravou.

O segundo é o que distingue uma frente honesta de uma que só maquia: um
`data-campo` sem ninguém escrevendo nele zera a régua da onda e deixa a tela
igualmente mentindo. Aqui o pacote é chamado com uma mesa de mentira que
DISCORDA do desenho em tudo, e o que ele emite tem de ser a mesa, não o mockup.

E ELA COBRA O SILÊNCIO, que é regra de produto: *campo sem informação não mostra
nada*. Pelo rádio a cor do plástico não se lê (o mapa de canais responde
`identidade.cor_do_aparelho` · `radio_aciona = não`), e o controle sem cor tem
de sair da tela **sem cor** — nunca com a do desenho.

A MORDIDA: tire o `data-campo="identidade"` do `controle()` do gerador, ou o
`chips_da_fita` da pós-troca, ou faça `cor_do_plastico` devolver um hex quando
o slug é vazio — cada um reprova um teste diferente, nomeando o que se perdeu.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "06-navegacao.html"  # (noqa-acento) nome de arquivo

UM = "aa:bb:cc:00:00:01"
DOIS = "aa:bb:cc:00:00:02"

CONTROLES = [
    {"uniq": UM, "connected": True, "transport": "usb", "player_slot": 1,
     "player": 1, "is_primary": True, "modelo": "White"},
    {"uniq": DOIS, "connected": True, "transport": "bt", "player_slot": 2,
     "player": 2, "is_primary": False},
]

#: VAZIO — é o que `mesa_viva.mesa_do_estado` devolve quando o leitor de cor não
MESA = [
    {"pref": "p1", "uniq": UM, "jogador": 1, "cor": "white", "nome": "White",
     "via": "USB", "transporte": "usb", "alvo": True, "mascara": "DualSense"},
    {"pref": "p2", "uniq": DOIS, "jogador": 2, "cor": "", "nome": "Não sei",
     "via": "BT", "transporte": "bt", "alvo": False, "mascara": "DualSense"},
]

ESTADO = {
    "active_profile": "regua",
    "mouse_emulation": {"enabled": True, "speed": 9, "scroll_speed": 3,
                        "bloqueio": "", "despachando": True},
    "keyboard_emulation": {"enabled": True, "osk_disponivel": True},
    "controllers": CONTROLES,
}

def _nomes_do_desenho() -> list[str]:
    import monta

    return [str(c["nome"]) for c in monta.MESA]


@pytest.fixture
def bancada() -> str:
    from hefesto_dualsense4unix.interface import onde

    return onde.pagina(PAGINA).read_text(encoding="utf-8")


@pytest.fixture
def miolo(bancada: str) -> str:
    """Só o miolo, sem comentário HTML e sem `<style>`."""
    corpo = bancada.split('<div class="miolo">', 1)[-1].split('<div class="nota">', 1)[0]
    corpo = re.sub(r"<!--.*?-->", "", corpo, flags=re.S)
    return re.sub(r"<style[^>]*>.*?</style>", "", corpo, flags=re.S)


@pytest.fixture
def carga(monkeypatch):
    """O que o pacote emitiria NESTE tique, já na forma que a tela consome."""
    import pacotes
    from pacotes import a06_navegacao, perfil

    monkeypatch.setattr(perfil, "ativo", lambda nome: {"name": "Régua"} if nome else {})
    ctx = pacotes.Contexto(state=ESTADO, mesa=MESA, conectados=CONTROLES, estados={})
    return pacotes.normalizar(a06_navegacao.pacote(ctx),
                              {str(c["uniq"]): str(c["pref"]) for c in MESA})


def test_nenhum_title_nomeia_o_controle(bancada):
    """`title` é texto que a tela mostra, e não tem alvo de pintura."""
    for nome in _nomes_do_desenho():
        assert f'title="{nome} ' not in bancada, (
            f"um `title` voltou a nomear o plástico {nome!r} — a dica ficaria "
            f"nomeando o controle do desenho por cima de um rótulo já vivo")
    assert 'title="Player ' not in bancada, (
        "o `title` do cartão voltou: ele repete o rótulo em texto que nada "
        "reescreve")


def test_a_fita_cala_o_nome_que_nao_se_leu(carga):
    """O chip do controle no rádio sai `P2 • BT`, sem nome de plástico."""
    chips = carga["mesa"]["fita-chips"]
    assert "White" in chips, chips
    for nome in _nomes_do_desenho():
        if nome != "White":
            assert nome not in chips, (
                f"a fita voltou a dizer {nome!r} — o controle do desenho")
    from pacotes import NOME_SEM_LEITURA

    assert NOME_SEM_LEITURA not in chips, (
        f"{NOME_SEM_LEITURA!r} não é nome: é a ausência de leitura, e pô-lo na "
        f"tela é dizer algo onde não há nada")


def test_cada_chip_pintado_da_fita_tem_endereco_proprio(carga):
    """O `--plastico` do chip mora no `style` do PRÓPRIO elemento.

    O endereço do bloco (`fita-chips`) não alcança a régua da identidade, que lê
    o `style` de cada elemento: em 09/10/2026 a 06 publicada reprovava
    `identidade-de-cima` com dois `--plastico` cravados na fita. O chip ganha o
    `data-campo="fita-chip"` que o `monta.fita()`, a 03 e a 09 já dão.
    """
    chips = re.findall(r"<label [^>]*>", carga["mesa"]["fita-chips"])
    pintados = [c for c in chips if "--plastico" in c]
    assert pintados, f"a mesa de mentira tem um controle com cor e nenhum chip pintou: {chips}"
    sem = [c for c in pintados if 'data-campo="fita-chip"' not in c]
    assert not sem, f"chip pintado sem endereço próprio: {sem}"


