#!/usr/bin/env python3
"""A RÉGUA DA IDENTIDADE NA ABA 06: o controle da tela é o da MESA, nunca o do desenho.

A LEI É DELA, 03/09/2026:

    "se no topo tá mostrando controle white player 1, então cada aba vai usar
    os controles lá de cima. Não mistura com a info dos mockups. (…) Por isso
    temos o mapa pra servir como variável de identificação"

(A frase elidida — *"Cada feature faz referência ao controle conectado"* — está
inteira em `docs/process/sprints/2026-09-03-IDENTIDADE-VEM-DE-CIMA-01-a-fita-manda-nas-dez-abas.md`.
Ela sai daqui porque a palavra dela vem sem o acento e o portão `acentuacao`
varre este arquivo; a elisão é honesta e a fonte fica apontada.)

O QUE ESTA ABA MOSTRAVA, medido em 03/09/2026 com os dois controles dela na
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

E ELA COBRA O SILÊNCIO, que é regra dela: *campo sem informação não mostra
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

#: DOIS CONTROLES SINTÉTICOS, na faixa da casa — há dois portões de anonimato
#: nesta árvore. O segundo é o caso que importa: está no RÁDIO, e pelo rádio a
#: cor do plástico não chega.
UM = "aa:bb:cc:00:00:01"
DOIS = "aa:bb:cc:00:00:02"

CONTROLES = [
    {"uniq": UM, "connected": True, "transport": "usb", "player_slot": 1,
     "player": 1, "is_primary": True, "modelo": "White"},
    {"uniq": DOIS, "connected": True, "transport": "bt", "player_slot": 2,
     "player": 2, "is_primary": False},
]

#: A MESA COMO O PILOTO A MONTA. `cor` é o slug do desenho, e o do rádio vem
#: VAZIO — é o que `mesa_viva.mesa_do_estado` devolve quando o leitor de cor não
#: respondeu, e é o estado de verdade da mesa dela hoje.
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

#: OS NOMES DE PLÁSTICO DO MOCKUP desta aba. Eles não se digitam: saem da
#: `monta.MESA`, que é o dono do desenho — digitá-los aqui criaria uma segunda
#: lista que envelhece calada no dia em que ela trocar o desenho.
def _nomes_do_desenho() -> list[str]:
    import monta

    return [str(c["nome"]) for c in monta.MESA]


@pytest.fixture
def bancada() -> str:
    from hefesto_dualsense4unix.interface import onde

    return onde.pagina(PAGINA).read_text(encoding="utf-8")


@pytest.fixture
def miolo(bancada: str) -> str:
    """Só o miolo, sem comentário HTML e sem `<style>`.

    As três armadilhas que já fizeram as réguas das abas irmãs reprovarem o que
    estava certo: a prosa do comentário, a folha de estilo e a legenda do
    mockup, que fala SOBRE o desenho e não É a tela.
    """
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


# ---------------------------------------------------------------------------
# 1. O ENDEREÇO EXISTE — em cada lugar onde a aba diz identidade
# ---------------------------------------------------------------------------
def test_os_cartoes_enderecam_o_nome_e_a_cor(miolo):
    """Os QUATRO lugares têm endereço de cor E de nome.

    A CONTA DO NOME ERA `len(conectados)` — DOIS — e ela mediu o mundo de
    ontem (07/09/2026, O-LUGAR-VAZIO-TEM-ENDERECO). O gerador tinha dois ramos
    para a mesma caixa, e só o CHEIO ganhou `data-campo="identidade"` em 03/09;
    esta régua congelou a metade que existia e teria dado verde sobre o defeito
    para sempre.

    O DEFEITO QUE ELA DEIXAVA PASSAR, medido com os QUATRO DualSense dela na
    mesa: o daemon publicava quatro, a carga chegava com `colunas` dos quatro,
    e a tela mostrava DOIS — o P3 e o P4 diziam "P3 · Desconectado" com o
    aparelho ligado na mão dela, porque `hefesto_vivo.achar(raiz, k)` procura
    `data-campo` DENTRO do bloco e ali não havia nenhum.

    O CONTRATO DE HOJE é `len(MESA)` nos dois: quatro lugares, quatro endereços
    de cor, quatro de nome. O lugar vazio nasce dizendo `Desconectado` e o
    piloto reescreve quando o controle chega.
    """
    import monta

    assert miolo.count('data-campo="plastico" data-hef-alvo="cor"') == len(monta.MESA), (
        "um lugar da mesa perdeu o endereço da cor — a borda dele volta a ser a "
        "cor cravada do desenho, e nada a reescreve")
    assert miolo.count('data-campo="identidade"') == len(monta.MESA), (
        "um lugar da mesa perdeu o `data-campo=\"identidade\"` — no lugar cheio "
        "o nome do plástico volta a ser o do mockup; no vazio, o controle que "
        "chegar não tem onde se nomear e o lugar segue dizendo 'Desconectado'")


def test_o_miolo_nao_tem_plastico_cravado(miolo):
    """`--plastico:#hex` não tem alvo de pintura, logo não pode existir aqui.

    O piloto escreve texto, valor, classe, cor, largura, fundo e `innerHTML`, e
    **nenhum deles alcança uma variável CSS**. Um `--plastico` no `style` de um
    elemento é, por construção, uma cor que o produto não consegue trocar.
    """
    assert "--plastico" not in miolo, (
        "voltou um `--plastico` cravado ao miolo da 06 — a cor ficaria a do "
        "mockup para sempre, porque nenhum alvo do piloto escreve variável CSS")


def test_a_fita_e_as_duas_dicas_tem_endereco(bancada):
    assert 'data-campo="fita-chips" data-hef-alvo="html"' in bancada, (
        "a fita da 06 perdeu o endereço — e `hefesto_vivo._fita`, o dono "
        "compartilhado dela, DESISTE quando um controle da mesa não tem cor "
        "lida, que é o caso do rádio hoje")
    assert bancada.count('data-campo="quem-navega"') == 2, (
        "as duas dicas das telas de botões voltaram a nomear o controle do "
        "desenho no meio do texto")


def test_nenhum_title_nomeia_o_controle(bancada):
    """`title` é texto que a tela mostra, e não tem alvo de pintura."""
    for nome in _nomes_do_desenho():
        assert f'title="{nome} ' not in bancada, (
            f"um `title` voltou a nomear o plástico {nome!r} — a dica ficaria "
            f"nomeando o controle do desenho por cima de um rótulo já vivo")
    assert 'title="Player ' not in bancada, (
        "o `title` do cartão voltou: ele repete o rótulo em texto que nada "
        "reescreve")


# ---------------------------------------------------------------------------
# 2. O PACOTE ESCREVE — e escreve o que LEU
# ---------------------------------------------------------------------------
def test_o_pacote_escreve_os_quatro_enderecos(carga):
    """Cada endereço da identidade recebe valor, e nenhum sai vazio por engano."""
    mesa = carga["mesa"]
    for chave in ("fita-chips", "plastico", "quem-navega"):
        assert chave in mesa, f"o pacote parou de emitir {chave!r}"
    assert mesa["quem-navega"] == "P1 White USB", mesa["quem-navega"]
    assert [v.get("identidade") for v in carga["colunas"].values() if "identidade" in v]


def test_o_nome_do_cartao_e_o_do_aparelho_e_nao_o_do_desenho(carga):
    """O cartão do P1 diz `White`, que é o modelo que o daemon decodificou."""
    nomes = {k: v.get("identidade") for k, v in carga["colunas"].items()}
    assert nomes.get("p1") == "White", nomes
    for nome in _nomes_do_desenho():
        assert nome not in set(nomes.values()) - {"White"}, (
            f"o cartão voltou a dizer {nome!r} — um nome do desenho, não da mesa")


def test_a_cor_da_borda_sai_do_mapa(carga):
    """O hex do plástico é LIDO de `monta.cor_da_zona`, nunca digitado."""
    import monta

    assert carga["mesa"]["plastico"][0] == monta.cor_da_zona("white")


def test_a_folha_viva_pinta_o_casco_de_quem_tem_cor(carga):
    """O casco do desenho é `var(--z-…)`, e quem o troca é a folha do pacote."""
    import monta

    folha = carga["blocos"]["#plastico-vivo"]
    assert '.nav-ctl[data-controle="p1"] .ds-svg{' in folha
    assert monta.cor_da_zona("white") in folha, (
        "a folha viva parou de pintar o casco — o desenho do cartão fica no "
        "colorway do mockup, que endereço nenhum alcança")


# ---------------------------------------------------------------------------
# 3. O SILÊNCIO — campo sem informação não mostra nada
# ---------------------------------------------------------------------------
def test_o_controle_sem_cor_lida_nao_ganha_cor_nenhuma(carga):
    """Pelo rádio a cor não chega, e a tela tem de dizer isso calando.

    A regra é dela, e o oposto dela é o defeito que esta onda existe para
    matar: cair de volta na cor do mockup.
    """
    assert carga["mesa"]["plastico"][1] == "", (
        "o lugar do controle sem cor lida ganhou um hex — ou o pacote inventou "
        "uma cor, ou caiu de volta no desenho")
    folha = carga["blocos"]["#plastico-vivo"]
    regra = folha.split('.nav-ctl[data-controle="p2"] .ds-svg{', 1)[-1].split("}", 1)[0]
    assert regra and "#" not in regra, (
        "o casco do controle sem cor recebeu um hex — o neutro do CSS é a "
        "única resposta honesta")


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


def test_sem_primario_a_dica_nao_inventa_um(monkeypatch):
    """Sem primário na mesa, `quem-navega` sai vazio — nunca a posição.

    Numerar por ordem de chegada é o defeito que a ROTA-A mediu: o MESMO
    controle mudava de nome quando o segundo entrava na mesa.
    """
    import pacotes
    from pacotes import a06_navegacao, perfil

    monkeypatch.setattr(perfil, "ativo", lambda nome: {"name": "Régua"} if nome else {})
    sem_chefe = [dict(c, is_primary=False) for c in CONTROLES]
    ctx = pacotes.Contexto(state=dict(ESTADO, controllers=sem_chefe), mesa=MESA,
                           conectados=sem_chefe, estados={})
    assert a06_navegacao.pacote(ctx)["mesa"]["quem-navega"] == ""
