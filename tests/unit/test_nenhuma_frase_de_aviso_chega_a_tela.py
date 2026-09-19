#!/usr/bin/env python3
"""FRASES-E-DICAS-02 — nenhuma frase de aviso chega à tela nas abas 02, 03, 07 e 08.

A PALAVRA DELA, 13/09/2026, no índice da terceira lista
(`docs/process/sprints/arquivados/2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md`): ela colou
a frase da Steam e escreveu *"esse tipo de info segue aparecendo nas abas"*. A
regra da sprint: frase de aviso não chega à tela em forma nenhuma — recado,
faixa, caixa, dica flutuante, `title`. Ficam o ESTADO e a AJUDA (o `?`).

AS ÂNCORAS SÃO LIDAS DOS DONOS onde o dono continua de pé:

    âncora                                 dono
    -------------------------------------  ------------------------------------
    a abertura da confissão do desenho     `mapa_da_mesa.CONFISSAO_ABERTURA`
    o ganho que não foi medido             `ordens_da_mesa.NAO_MEDI`
    o prefixo da cura                      `secao_exame.PREFIXO_DA_CURA`
    as quatro frases do canal de áudio     `controller_card.DICA_CANAL_*`

DUAS PERDERAM O DONO nesta sprint e ficam como FRASE QUE SAIU — o molde é o
`test_o_cartao_da_steam_nao_narra.test_a_regua_recusa_as_frases_que_sairam`:
o aviso da mesa suja (a constante saiu de `secao_controles`) e o trecho da cor
não lida (a literal saiu de `monta.py` e de `a03_gatilhos.py`; a da aba 09 é da
SISTEMA-BOTOES-01 e fica fora desta régua, como o «O que fazer» da 09).

MAIS DUAS ENTRARAM NA FRASES-E-DICAS-03 (13/09/2026), também como FRASE QUE
SAIU, porque nenhuma tem constante de dono: a razão do nascimento na dica da luz
da 08 (a frase vem montada do daemon, e a reserva `FRASE_NASCEU_CONDENADO` saiu)
e a narração depois do travessão no sufixo das exceções do Steam Input, na 07.

AS DUAS METADES, com pontos cegos diferentes de propósito:

1. **o que os pacotes ESCREVEM por tique** — é onde as frases moravam, e a
   página estática não mostra nenhuma delas;
2. **as dez páginas, a publicada e a da bancada** — o que ela vê antes do
   primeiro tique, pelo motor de `frases_que_ela_baniu` (o `title` entra na
   leitura) e SEM o conteúdo dos `.ajuda`, que é ajuda aberta de propósito.

Os três ramos do cartão da Steam têm régua própria, com a de estado da
TELA-CALADA-02: `test_o_cartao_da_steam_nao_narra.
test_os_tres_ramos_que_narravam_viram_rotulo_de_estado`.

O PASSEIO NO PILOTO OCULTO pelas dez abas, com `sem_cor=True`, está na entrega
da sprint (a entrega de 13/09/2026 da `FRASES-E-DICAS-02`), com a
saída e as fotos: ele abre WebKit e fala com o daemon vivo, e a suíte não faz
nenhum dos dois. A sonda da mesa saiu do produto nesta sprint, então o passeio
não tem onde dublar o controle segurado; quem o dubla é esta régua, na sonda de
verdade (`sinal_da_barra.limpo_para_conectar`), passando pelo tique inteiro.

NADA AQUI TOCA A MÁQUINA DELA: o `conftest.py` desvia `HOME` e os `XDG_*`, a
sonda é dublada e a mesa é de mentira, na faixa sintética `aa:bb:cc`.
"""
from __future__ import annotations

import html
import pathlib
import re
import sys
from html.parser import HTMLParser
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

#: O MIOLO DA FRASE QUE SAIU de `secao_controles.AVISO_DA_MESA_SUJA`, 13/09/2026.
#: Sem a abertura nem a instrução, para morder também uma redação nova que só
#: troque uma das duas.
AVISO_QUE_SAIU = "outro programa está segurando controle"

#: O TRECHO QUE SAIU das dicas da cor da fita e da aba 03, 13/09/2026.
COR_QUE_SAIU = "não foi lida"

#: O MIOLO DA RAZÃO DO NASCIMENTO que saiu da dica da luz, 13/09/2026. Comum às
#: duas redações que chegavam à tela: a do daemon (`sinal_da_barra`, montada na
#: hora) e a reserva que saiu de `secao_controles`.
RAZAO_QUE_SAIU = "a barra não obedece"

#: A NARRAÇÃO DO SUFIXO DO STEAM INPUT, que saiu em 13/09/2026: o travessão
#: depois da contagem das exceções. Morde qualquer redação nova depois dele.
NARRACAO_QUE_SAIU = "jogo(s) —"

#: A âncora que só vale na 08: o «O que fazer» da aba Sistema é de outra sprint.
SO_NA_08 = "o prefixo da cura"

#: A mesa de mentira: um controle com a cor lida e um sem.
UNIQ_1, UNIQ_2 = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"
MESA = [
    {"pref": "p1", "uniq": UNIQ_1, "jogador": 1, "cor": "white", "nome": "White",
     "via": "USB", "transporte": "usb", "mascara": "DualSense"},
    {"pref": "p2", "uniq": UNIQ_2, "jogador": 2, "cor": "", "nome": "Galactic Purple",
     "via": "BT", "transporte": "bt", "mascara": "DualSense"},
]


def _ancoras() -> dict[str, str]:
    """`{nome: trecho}` — lidos do dono quando ele existe."""
    from hefesto_dualsense4unix.app.actions.config.secao_exame import PREFIXO_DA_CURA
    from hefesto_dualsense4unix.app.widgets import controller_card as cc
    from hefesto_dualsense4unix.app.widgets.mapa_da_mesa import CONFISSAO_ABERTURA
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import NAO_MEDI

    return {
        "o aviso da mesa suja": AVISO_QUE_SAIU,
        "a cor não lida": COR_QUE_SAIU,
        "a razão do nascimento": RAZAO_QUE_SAIU,
        "a narração do sufixo": NARRACAO_QUE_SAIU,
        "a confissão do desenho": str(CONFISSAO_ABERTURA),
        "o ganho não medido": str(NAO_MEDI),
        "o canal dormindo": str(cc.DICA_CANAL_DORMINDO),
        "o canal acordado": str(cc.DICA_CANAL_ACORDADO),
        "o canal é o padrão": str(cc.DICA_CANAL_E_PADRAO),
        "a regra que falta": str(cc.DICA_CANAL_SEM_A_REGRA),
        SO_NA_08: str(PREFIXO_DA_CURA).strip(),
    }


def _achadas(texto: str, *, com_a_cura: bool = False) -> list[str]:
    """Os nomes das âncoras que aparecem no texto."""
    return [nome for nome, trecho in _ancoras().items()
            if trecho in texto and (com_a_cura or nome != SO_NA_08)]


def _sem_etiqueta(marcacao: str) -> str:
    """O texto de um valor `html` do pacote, sem as etiquetas."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", marcacao)).split())


# --------------------------------------------------------------------------
# a régua sabe recusar
# --------------------------------------------------------------------------
def test_a_regua_acha_cada_ancora_e_deixa_o_estado_passar() -> None:
    """Uma régua que só sabe passar não é régua — e uma que recusa estado também não."""
    for nome, trecho in _ancoras().items():
        assert trecho, f"a âncora {nome!r} veio vazia do dono — a régua ficaria cega"
        assert nome in _achadas(f"… {trecho} …", com_a_cura=True), nome
    for estado in ("Canal de áudio dormindo", "Galactic Purple", "uma coisa",
                   "Fora dos caminhos conhecidos", "Ligado em 2 jogos",
                   "Desligado — tudo certo · Exceção por jogo: 1 jogo(s)"):
        assert _achadas(estado, com_a_cura=True) == [], estado


# --------------------------------------------------------------------------
# 08 — a dica da luz, com outro programa segurando o controle
# --------------------------------------------------------------------------
def _ctx() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    conectados = [
        {"uniq": UNIQ_1, "transport": "usb", "connected": True, "battery_pct": 100},
        {"uniq": UNIQ_2, "transport": "bt", "connected": True, "battery_pct": 64},
    ]
    return Contexto(state={"controllers": conectados}, mesa=MESA,
                    conectados=conectados, estados={})


def test_a_dica_da_luz_nao_avisa_com_outro_programa_segurando_o_controle(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A sonda de verdade dublada em SUSPEITA, e a dica continua sem o aviso.

    As duas portas: a função e o tique inteiro (`pacote()`), que é quem a chama
    para cada controle. A razão do nascimento tem régua própria, logo abaixo.
    """
    from hefesto_dualsense4unix.integrations import sinal_da_barra as sb
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as p

    monkeypatch.setattr(sb, "limpo_para_conectar",
                        lambda *a, **k: (sb.CONFIANCA_SUSPEITA, "dublê", (4242,)))
    for via in ("bt", "usb", ""):
        dica = p.dica_da_luz(via)
        assert not _achadas(dica), (via, dica)
    dicas = [coluna.get("luz-dica", "") for coluna in p.pacote(_ctx())["colunas"].values()]
    assert dicas and all(dicas), f"o tique não escreveu a dica da luz: {dicas!r}"
    assert not [d for d in dicas if _achadas(d)], dicas


def test_a_dica_da_luz_nao_traz_a_razao_do_nascimento() -> None:
    """Os dois controles chegam condenados no estado, e o tique não escreve a razão.

    FRASES-E-DICAS-03, 13/09/2026. O carimbo de cada controle traz o miolo que a
    tela mostrava. MORDIDA: devolva a razão à `dica_da_luz` e o `nascimento` à
    chamada dela no `pacote()`, e esta régua reprova nos dois controles.
    """
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as p

    ctx = _ctx()
    for controle in ctx.conectados:
        controle["nascimento"] = {
            "pede_reconexao": True,
            "porque": ("nasceu com 1 processo(s) segurando o nó do controle — nesta "
                       f"condição {RAZAO_QUE_SAIU}, e só a reconexão devolve")}
    dicas = [coluna.get("luz-dica", "") for coluna in p.pacote(ctx)["colunas"].values()]
    assert len(dicas) == 2 and all(dicas), dicas
    assert not [d for d in dicas if _achadas(d)], dicas


# --------------------------------------------------------------------------
# 08 — a linha da confissão e a coluna da direita
# --------------------------------------------------------------------------
def test_a_linha_da_confissao_diz_a_conta_e_nao_confessa(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Fica a contagem; a abertura e os itens não chegam ao `title`."""
    from hefesto_dualsense4unix.app.widgets import mapa_da_mesa
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as p

    monkeypatch.setattr(p, "_bancada", lambda: object())
    monkeypatch.setattr(mapa_da_mesa, "confissao_do_desenho",
                        lambda _b: ("o que é algum dos aparelhos da lista",))
    campos = p._confissao_do_mapa()
    assert campos.get("confissao-conta") == p.palavra_da_conta(1), campos
    assert "confissao-dica" not in campos, campos
    assert not [v for v in campos.values() if _achadas(str(v))], campos


def _cena(destino: str) -> list[Any]:
    """Duas ordens com o ganho não medido e uma conferência com cura."""
    from hefesto_dualsense4unix.integrations.exame_da_mesa import ESTADO_ATENCAO, Item
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import (
        DERIVADO_DA_CONTA,
        MEDIDO_AQUI,
        NAO_MEDI,
        Identidade,
        Linha,
        Ordem,
    )

    def ordem(chave: str) -> Ordem:
        return Ordem(
            chave=chave, acao=f"Leve o adaptador {chave} para uma entrada do computador",
            o_que_eu_vi=Linha(texto="dois rádios no mesmo hub", selo=MEDIDO_AQUI),
            por_que_importa=Linha(texto="o hub divide o caminho", selo=MEDIDO_AQUI),
            ganho_esperado=Linha(texto=NAO_MEDI, selo=DERIVADO_DA_CONTA),
            alvo=Identidade(vid="2357", pid="0604", caminho="3-1.2"),
            arranjo="3-1.2 3-1.4", destino=destino)

    return [
        Item(chave="uma", rotulo="A", estado=ESTADO_ATENCAO, porque="vi isto",
             cura="mova o cabo", ordem=ordem("uma")),
        Item(chave="outra", rotulo="B", estado=ESTADO_ATENCAO, porque="vi aquilo",
             cura="tire o hub", ordem=ordem("outra")),
        Item(chave="conf-1", rotulo="C", estado=ESTADO_ATENCAO,
             porque="a economia de energia está ligada",
             cura="desligue a economia de energia"),
    ]


@pytest.mark.parametrize("destino", ["", "Entrada 9"])
def test_a_coluna_da_direita_da_08_nao_instrui_nem_confessa(
        monkeypatch: pytest.MonkeyPatch, destino: str) -> None:
    """Sem o imperativo, sem o ganho, sem o cartão de cura — fica o de→para.

    Sem destino (as duas ordens desta máquina) a coluna não tem card e manda o
    marcador de nada, que não vira travessão.
    """
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as p

    cena = _cena(destino)
    monkeypatch.setattr(p, "_ORDENS_NA_TELA", tuple(i.ordem for i in cena))
    coluna = p._html_da_ordem(cena)
    visivel = _sem_etiqueta(coluna)
    assert not _achadas(visivel, com_a_cura=True), visivel
    for item in cena:
        if item.ordem is not None:
            assert item.ordem.acao not in visivel, visivel
        assert item.cura not in visivel, visivel
    if destino:
        assert 'class="receita"' in coluna and destino in coluna, coluna
        assert visivel.endswith("+1 recomendação não coube aqui"), visivel
    else:
        assert coluna.strip() and visivel == "", coluna


def test_o_interrogacao_do_exame_continua_dizendo_o_que_fazer() -> None:
    """O que saiu da coluna mora no `?` da linha — e continua lá."""
    from hefesto_dualsense4unix.app.actions.config.secao_exame import PREFIXO_DA_CURA
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as p

    for item in _cena(""):
        dica = _sem_etiqueta(p._dica_da_linha(item))
        assert str(PREFIXO_DA_CURA).strip() in dica and item.cura in dica, dica


# --------------------------------------------------------------------------
# a fita e a 03 — a cor não lida diz o nome, ou nada
# --------------------------------------------------------------------------
def test_a_cor_nao_lida_diz_o_nome_ou_nada() -> None:
    import monta

    from hefesto_dualsense4unix.interface.pacotes import a03_gatilhos as p3

    fita = monta.fita(ativo="p1", mesa=MESA)
    assert not _achadas(fita), fita
    chips = re.findall(r'<label class="chip[^"]*" data-campo="fita-chip"[^>]*>', fita)
    sem_cor = [c for c in chips if "plastico" not in c.split("data-campo")[0]]
    assert len(chips) == 2 and len(sem_cor) == 1, chips
    titulo = re.search(r'title="([^"]*)"', sem_cor[0])
    assert titulo is None or "—" not in titulo.group(1), sem_cor[0]

    com_nome = p3.chip_do_controle(2, "Galactic Purple", "BT", "", True)
    assert 'title="Galactic Purple"' in com_nome, com_nome
    assert "title=" not in p3.chip_do_controle(2, "", "BT", "", True)


# --------------------------------------------------------------------------
# 02 — o canal do alto-falante
# --------------------------------------------------------------------------
def test_a_dica_do_canal_e_rotulo_de_estado() -> None:
    from hefesto_dualsense4unix.app import audio_saida
    from hefesto_dualsense4unix.interface.pacotes import a02_controles as p2
    from tests.unit.test_o_cartao_da_steam_nao_narra import _e_rotulo_de_estado

    assert p2.dica_do_canal("") == ""
    for sono in (audio_saida.CANAL_ACORDADO, audio_saida.CANAL_DORMINDO):
        dica = p2.dica_do_canal(sono)
        assert not _achadas(dica), dica
        assert "PipeWire" not in dica and "medido" not in dica, dica
        assert sono in dica and _e_rotulo_de_estado(dica), dica


# --------------------------------------------------------------------------
# 07 — o sufixo das exceções do Steam Input
# --------------------------------------------------------------------------
def test_o_sufixo_das_excecoes_conta_e_nao_narra(monkeypatch: pytest.MonkeyPatch) -> None:
    """A linha do Steam Input pelo caminho do produto, com uma exceção na lista.

    FRASES-E-DICAS-03, 13/09/2026. A contagem fica, porque a 07 não mostra a
    lista das exceções em outro lugar. MORDIDA: devolva a narração depois da
    contagem em `emulation_actions.markup_status_steam_input`, e esta régua
    reprova.

    A ÂNCORA SÓ CONHECE O TRAVESSÃO. Medido pela validação: a narração devolvida
    com dois-pontos no lugar dele passava aqui. Por isso a linha visível tem de
    terminar na contagem.

    NOTA DATADA — 13/09/2026 (RESTOS-DA-ONDA-DOIS-01). A régua passava pelos três
    valores do `efetiva` e cobrava a mesma linha nos três. O `efetiva` saiu da
    leitura e da assinatura, e não há mais estado da exceção que a linha possa
    narrar; o que continua valendo é a linha terminar na contagem.
    """
    from hefesto_dualsense4unix.app.actions import emulation_actions as ea
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as p7

    monkeypatch.setattr(ea.EmulationActionsMixin, "_steam_input_is_on",
                        staticmethod(lambda: False))
    monkeypatch.setattr(ea.EmulationActionsMixin, "_steam_input_excecoes",
                        staticmethod(lambda: [990000011]))
    frase, _ligado = p7._o_que_a_steam_poe_no_meio()
    visivel = _sem_etiqueta(frase)
    assert "Exceção por jogo: 1 jogo(s)" in visivel, visivel
    assert not _achadas(visivel), visivel
    assert visivel.rstrip().endswith("Exceção por jogo: 1 jogo(s)"), visivel


# --------------------------------------------------------------------------
# as dez páginas — a publicada e a da bancada
# --------------------------------------------------------------------------
def _paginas() -> list[pathlib.Path]:
    publicadas = sorted((INTERFACE / "paginas").glob("??-*.html"))  # (noqa-acento) nome de pasta
    bancada = sorted((RAIZ / "mockup").glob("??-*.html"))
    assert len(publicadas) == 10 and len(bancada) == 10, (
        "a régua não achou as dez abas — o caminho mudou, e uma régua que não "
        "acha a tela não mede a tela")
    return publicadas + bancada


def _visivel_sem_a_ajuda(pagina: str) -> str:
    """O que a janela mostra, com o `title` junto e sem o conteúdo dos `?`."""
    from hefesto_dualsense4unix.interface.folha_da_casa import seletores_escondidos
    from hefesto_dualsense4unix.interface.frases_que_ela_baniu import _ler

    return " ".join(_ler(pagina, (*seletores_escondidos(), ".ajuda")).split())


@pytest.mark.parametrize("arquivo", _paginas(),
                         ids=lambda p: f"{p.parent.name}/{p.name}")
def test_nenhuma_pagina_traz_aviso_fora_do_interrogacao(arquivo: pathlib.Path) -> None:
    visivel = _visivel_sem_a_ajuda(arquivo.read_text(encoding="utf-8"))
    achadas = _achadas(visivel, com_a_cura=arquivo.name.startswith("08-"))
    trechos = {nome: visivel[max(0, visivel.find(t) - 60):visivel.find(t) + 80]
               for nome, t in _ancoras().items() if nome in achadas}
    assert not achadas, f"{arquivo.parent.name}/{arquivo.name}: {trechos}"


# --------------------------------------------------------------------------
# 08 — a coluna da ordem que a página CRAVA antes do primeiro tique
# --------------------------------------------------------------------------
#: Os elementos sem etiqueta de fecho: não abrem nível.
_VAZIOS = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input",
                     "link", "meta", "source", "track", "wbr"})

#: As classes do cartão da ordem que saíram da coluna visível em 13/09/2026: o
#: imperativo, a linha do ganho, a marca de procedência e o cartão de cura.
CLASSES_QUE_SAIRAM_DA_COLUNA = frozenset({"faca", "ganho", "proc", "cura"})


class _ClassesDoCampo(HTMLParser):
    """As classes de tudo o que mora DENTRO do elemento de um `data-campo`."""

    def __init__(self, campo: str) -> None:
        super().__init__(convert_charrefs=True)
        self.campo = campo
        self.fundo = 0
        self.achou = False
        self.classes: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        atributos = dict(attrs)
        if self.fundo:
            self.classes += (atributos.get("class") or "").split()
            if tag not in _VAZIOS:
                self.fundo += 1
        elif atributos.get("data-campo") == self.campo and tag not in _VAZIOS:
            self.achou = True
            self.fundo = 1

    def handle_endtag(self, tag: str) -> None:
        if self.fundo and tag not in _VAZIOS:
            self.fundo -= 1


def _campo_da_ordem() -> str:
    """O endereço da coluna, lido do gerador da 08 sem importá-lo."""
    fonte = (INTERFACE / "aba08.py").read_text(encoding="utf-8")
    achado = re.search(r'^CAMPO_DA_ORDEM = "([^"]+)"$', fonte, flags=re.M)
    assert achado, "o gerador da 08 perdeu `CAMPO_DA_ORDEM`: a régua ficaria cega"
    return achado.group(1)


@pytest.mark.parametrize("arquivo", [p for p in _paginas() if p.name.startswith("08-")],
                         ids=lambda p: f"{p.parent.name}/{p.name}")
def test_a_coluna_da_ordem_cravada_na_08_nao_traz_imperativo_nem_ganho(
        arquivo: pathlib.Path) -> None:
    """A §D da sprint vale também para o que a página crava antes do primeiro tique.

    O imperativo e o ganho cravados no desenho são prosa do mockup, sem âncora
    de dono, e a régua de cima não os via. MEDIDO NA VALIDAÇÃO, 13/09/2026: com o
    `div.faca` e o `div.ganho` de volta no gerador da 08, sem o cartão de cura
    (que traz o «O que fazer» e morde lá em cima), e a página regerada, as 76
    réguas da coluna passavam. Esta lê a CLASSE, que é o endereço do desenho.
    """
    leitor = _ClassesDoCampo(_campo_da_ordem())
    leitor.feed(arquivo.read_text(encoding="utf-8"))
    assert leitor.achou and leitor.classes, (
        f"{arquivo.parent.name}/{arquivo.name}: a régua não achou a coluna da ordem")
    voltaram = sorted(CLASSES_QUE_SAIRAM_DA_COLUNA & set(leitor.classes))
    assert not voltaram, (
        f"{arquivo.parent.name}/{arquivo.name}: a coluna da ordem crava {voltaram}")
