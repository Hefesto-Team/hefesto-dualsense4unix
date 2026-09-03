#!/usr/bin/env python3
"""A ABA VIBRAÇÃO: o degrau aceso vem do daemon, e a largura sai sem `%`.

DUAS COISAS, e as duas foram medidas em 02/09/2026 com o daemon dela vivo e
DOIS controles na mesa (um no `usb`, um no `bt`).

1. **O DEGRAU ACESO SAÍA DO DESENHO, e o desenho MENTIA.** A política de
   vibração é UMA, da mesa (``state_full.rumble_policy``), e o mockup crava um
   degrau aceso por coluna: o P1 nasce em "Máximo" e o P2 em "Balanceado". Com
   o daemon respondendo ``rumble_policy = 'balanceado'``, a coluna do P1
   afirmava o contrário do que está no disco. Não era desenho esperando dado —
   era a tela dizendo o oposto.

   A cura NÃO É ESCREVER TEXTO nos botões: isso já foi tentado na manhã do
   mesmo dia e apagou os quatro rótulos, tirando dela a escolha. QUAL dos
   quatro está aceso é a **classe** ``on``, e o alvo ``classe`` do
   ``escrever()`` (``hefesto_vivo.py:227``) acende quem casa com o
   ``data-hef-quando`` e apaga as irmãs.

2. **``motor-e-pct`` NÃO É ENDEREÇO MORTO** — a acusação da régua do mockup é
   FALSA, e esta régua pina o contrato que a desmente. O alvo ``largura`` do
   ``escrever()`` faz ``el.style.width = valor + '%'``: quem emite escreve o
   número PELADO. A régua do mockup compara a declaração (``'0'``) com o que o
   CSSOM devolve (``'0%'``) sem refazer essa tradução — e só percebe a
   diferença quando o valor pintado COINCIDE com o cravado, que é o caso do
   ``motor-e-pct`` do P1 (o desenho crava ``width:0.0%``). O ``motor-d-pct``
   emite o MESMO ``'0'`` e é contado PRODUTO só porque o desenho crava
   ``23.5%``. Mesmo código, veredito oposto: a diferença está no cravado, não
   no endereço. A cura mora em ``regua_do_mockup._declarado_neste_elemento``,
   que é território de outra frente.

A MORDIDA:

* tire o ``data-hef-quando`` dos quatro botões em ``aba05._coluna``, rode o
  gerador, e ``test_cada_degrau_diz_quem_ele_e`` reprova — e a reprovação não é
  cosmética: sem ele o alvo ``classe`` vira BOOLEANO e ``'balanceado'`` acende
  os QUATRO ao mesmo tempo;
* tire a chave ``degrau`` do ``a05_vibracao.pacote`` e
  ``test_o_pacote_emite_o_degrau_que_o_produto_calculou`` reprova;
* devolva o ``%`` ao ``forca-pct`` e ``test_a_largura_sai_sem_o_por_cento``
  reprova — a barra viraria ``width:46.7%%``, que o CSS descarta.

ONDE ELA MEDE: na **BANCADA**, que é onde o gerador escreve e onde o endereço
existe. A página publicada ainda não o tem, e é por isso que a tela dela não
muda até o ``--publicar 05``.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.app.telas import vibracao as _tela
from hefesto_dualsense4unix.interface import regua_do_mockup as _regua

PAGINA = "05-vibracao.html"

#: Dois controles de mentira. MAC da faixa SINTÉTICA da casa — há dois portões
#: de anonimato nesta árvore, e um endereço mascarado ainda carrega o OUI dela.
UNIQS = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02")

#: O TOKEN QUE NENHUM BOTÃO CONHECE — vizinho do certo, e sem acento de
#: propósito: chave de máquina não leva acento nesta casa. Ele mora numa
#: constante para não se repetir em prosa, onde o portão de acentuação o leria
#: como palavra mal escrita.
TOKEN_VIZINHO = "maximo"  # (noqa-acento) chave de máquina


@pytest.fixture(scope="module")
def bancada() -> str:
    import onde

    arq = onde.pagina(PAGINA)
    assert arq.exists(), f"a bancada não tem {PAGINA} — rode `python3 aba05.py`"
    return arq.read_text(encoding="utf-8")


def _ctx(policy: str = "balanceado"):
    """Um tique de mentira com dois controles — o pacote não toca o aparelho."""
    import pacotes

    conectados = [
        {"uniq": u, "player": i, "connected": True, "index": i - 1,
         "transport": "usb" if i == 1 else "bt", "battery_pct": 90, "inputs": {}}
        for i, u in enumerate(UNIQS, start=1)
    ]
    mesa = [{"pref": f"p{i}", "jogador": i, "uniq": u, "nome": "Régua",
             "via": "USB" if i == 1 else "BT", "cor": "starlight-blue",
             "plastico": "#123456", "conectado": True}
            for i, u in enumerate(UNIQS, start=1)]
    return pacotes.Contexto(
        state={"rumble_policy": policy, "rumble_mult_applied": 0.7,
               "active_profile": "regua"},
        mesa=mesa, conectados=conectados, estados={})


@pytest.fixture(scope="module")
def pacote():
    import pacotes

    return pacotes.pacote_da_pagina(PAGINA, _ctx())


# --------------------------------------------------------------------------
# 1. o endereço existe, e cada botão diz quem ele é
# --------------------------------------------------------------------------
def test_cada_degrau_diz_quem_ele_e(bancada) -> None:
    """Os quatro botões dividem UM `data-campo` e se distinguem pelo `quando`.

    SEM O `data-hef-quando` O ALVO VIRA BOOLEANO (`hefesto_vivo.py:229`), e
    `ligado('balanceado')` é verdadeiro: os quatro degraus acenderiam juntos, e
    a tela passaria a afirmar quatro políticas ao mesmo tempo.

    OS DEGRAUS VÊM DO PRODUTO, e não de uma lista digitada aqui:
    `app/telas/vibracao.degraus_da_forca()` é o dono. E o gerador NÃO é
    importado — importar `aba05` REESCREVE a bancada dela como efeito de um
    `import`, e uma régua não mexe no que mede.
    """
    for chave in _tela.degraus_da_forca():
        alvo = (f'data-campo="degrau" data-hef-alvo="classe" '
                f'data-hef-quando="{chave}"')
        assert alvo in bancada, f"o degrau {chave!r} não tem endereço de classe"

    quandos = re.findall(r'data-hef-quando="([^"]+)"', bancada)
    colunas_vivas = bancada.count('<div class="ctrl" data-controle=')
    esperado = len(_tela.degraus_da_forca()) * colunas_vivas
    assert len(quandos) == esperado, (
        f"são {len(_tela.degraus_da_forca())} degraus em {colunas_vivas} "
        f"colunas conectadas = {esperado}, e achei {len(quandos)}")
    assert set(quandos) == set(_tela.degraus_da_forca()), (
        f"os degraus endereçados não são os do produto: {sorted(set(quandos))}")


def test_o_degrau_nunca_e_nome_de_clique(bancada) -> None:
    """`degrau` é endereço de PINTURA; `forca` é endereço de CLIQUE.

    O ouvinte lê `data-papel` como o nome do gesto (`hefesto_vivo.py:288`) e o
    pintor procura o valor pelos três endereços. Um nome nos dois papéis faz a
    pintura escrever dentro do botão — foi o defeito da manhã de 02/09.
    """
    assert 'data-papel="degrau"' not in bancada
    assert 'data-campo="forca"' not in bancada


def test_o_lugar_vazio_nao_tem_degrau(bancada) -> None:
    """Uma coluna sem controle não acende degrau nenhum.

    Ela não tem política para mostrar, e acender um seria a mesma mentira em
    outro lugar. O gerador já não põe ajuste vivo num lugar vazio; esta régua
    guarda que o endereço novo não abriu a exceção.
    """
    for pedaco in bancada.split('class="ctrl vazia"')[1:]:
        bloco = pedaco.split('<div class="ctrl', 1)[0]
        assert 'data-campo="degrau"' not in bloco, (
            "um lugar vazio ganhou degrau endereçado")


# --------------------------------------------------------------------------
# 2. o pacote emite o que o produto calculou
# --------------------------------------------------------------------------
def test_o_pacote_emite_o_degrau_que_o_produto_calculou(pacote) -> None:
    """O valor é a CHAVE do produto, e ele sai do `app/telas/vibracao`.

    Não se calcula degrau aqui: `pacote_da_coluna` já monta `forca` a partir do
    `state_full.rumble_policy`. A interface só traduz o nome do campo.
    """
    colunas = pacote["colunas"]
    assert len(colunas) == 2, f"a mesa de mentira tem dois controles: {list(colunas)}"
    for uniq, col in colunas.items():
        assert col["degrau"] == "balanceado", (
            f"a coluna {uniq} emitiu {col.get('degrau')!r}")
    assert set(_tela.degraus_da_forca()) >= {"balanceado"}, (
        "o degrau emitido tem de ser uma das chaves do produto")


def test_o_degrau_emitido_e_sempre_um_dos_quatro() -> None:
    """Um token que nenhum botão conhece APAGA os quatro, calado.

    O `escrever()` só acende quem casa com o `data-hef-quando`; o
    :data:`TOKEN_VIZINHO` no lugar de `'max'` deixaria a coluna inteira
    apagada e ninguém veria erro. Por isso o que sai daqui é a chave do
    produto, e não um rótulo.
    """
    import pacotes

    conhecidos = set(_tela.degraus_da_forca())
    for policy in sorted(conhecidos):
        pac = pacotes.pacote_da_pagina(PAGINA, _ctx(policy))
        for col in pac["colunas"].values():
            assert col["degrau"] in conhecidos, (
                f"o pacote emitiu {col['degrau']!r} para a política {policy!r}")


def test_a_mesa_sem_politica_nao_acende_degrau_nenhum() -> None:
    """Campo sem informação NÃO MOSTRA NADA — a regra dela, 02/09/2026.

    *"Se não tá mostrando agora, não tem info pra mostrar no produto. Mas quando
    tiver, aparece a info correta."* Com o daemon calado sobre a política, o
    valor emitido é vazio, o `escrever()` põe o travessão, e travessão não casa
    com `data-hef-quando` nenhum: os quatro apagam.
    """
    import pacotes

    pac = pacotes.pacote_da_pagina(PAGINA, _ctx(policy=""))
    for col in pac["colunas"].values():
        assert col["degrau"] == "", f"o vazio virou {col['degrau']!r}"


# --------------------------------------------------------------------------
# 3. a régua do mockup julga o degrau, e julga certo
# --------------------------------------------------------------------------
def _campos(bancada: str, chave: str) -> list:
    return [c for c in _regua._campos_cravados(bancada) if c.chave == chave]


def test_a_regua_ve_os_oito_degraus_com_alvo_classe(bancada) -> None:
    """O parser da régua lê o mesmo endereço que o pintor escreve.

    Se os dois lerem coisas diferentes, a medição da aba passa a falar de uma
    página que não existe — é a cegueira que o `--prova-de-mockup` reprova.
    """
    degraus = _campos(bancada, "degrau")
    assert len(degraus) == 8, f"a régua achou {len(degraus)} degraus, e são 8"
    assert {c.alvo for c in degraus} == {"classe"}
    assert {c.quando for c in degraus} == {"economia", "balanceado", "max", "auto"}
    # O CRAVADO de um alvo `classe` é o `quando` de quem tem a classe `on`, e
    # `''` para as irmãs. O desenho acende UM por coluna — e são dois diferentes,
    # que é exatamente a razão de este endereço existir.
    acesos = sorted(c.quando for c in degraus if c.valor)
    assert acesos == ["balanceado", "max"], (
        f"o desenho crava {acesos} — se virarem iguais, a prova perde o caso")


def test_o_degrau_deixa_de_ser_desenho_quando_o_pacote_o_declara(bancada, pacote) -> None:
    """O veredito da régua sobre os quatro botões da coluna do P1.

    ANTES do endereço eles eram `MOCKUP` — *"nenhum pacote declara este
    endereço"*. Com o endereço e a declaração, a régua julga `PRODUTO`, e o
    "Máximo" que o desenho cravava sai do ar.
    """
    cravados = [c for c in _regua._campos_cravados(bancada)
                if c.chave == "degrau" and c.dono == "p1"]
    declarados = {("p1", "degrau"): "balanceado"}
    # O QUE A TELA MOSTRA depois da pintura, medido no WebKit em 02/09/2026 e
    # transcrito aqui: acende `balanceado`, apagam as três irmãs.
    vivos = ["balanceado" if c.quando == "balanceado" else "" for c in cravados]
    selos = [True] * len(cravados)
    vereditos = _regua._classificar(cravados, vivos, declarados, selos)
    classes = {v.classe for v in vereditos}
    assert classes == {_regua.PRODUTO}, (
        f"a régua ainda vê desenho nos degraus: "
        f"{[(v.campo.quando, v.classe, v.nota) for v in vereditos]}")


def test_a_regua_acusa_o_degrau_que_ninguem_conhece(bancada) -> None:
    """A MORDIDA de dentro: um token errado tem de ser ACUSADO, não perdoado.

    Com o :data:`TOKEN_VIZINHO` os quatro apagariam e a tela ficaria sem
    degrau aceso. A régua distingue isso de "apagado de propósito" porque
    conhece os `quando` do grupo inteiro.
    """
    cravados = [c for c in _regua._campos_cravados(bancada)
                if c.chave == "degrau" and c.dono == "p1"]
    vivos = ["" for _ in cravados]
    vereditos = _regua._classificar(
        cravados, vivos, {("p1", "degrau"): TOKEN_VIZINHO},
        [True] * len(cravados))
    assert any(v.classe == _regua.MOCKUP for v in vereditos), (
        "a régua deu verde sobre um grupo inteiramente apagado")


# --------------------------------------------------------------------------
# 4. o contrato da largura — o que desmente o "endereço morto" do motor-e-pct
# --------------------------------------------------------------------------
def test_a_largura_sai_sem_o_por_cento(pacote, bancada) -> None:
    """O alvo `largura` faz `el.style.width = valor + '%'` — o `%` é do pintor.

    Emitir `'46.7%'` produziria `width:46.7%%`, que o CSS descarta: a barra
    ficaria congelada no que o desenho cravou. É por isso que o pacote emite o
    número pelado — e é essa tradução que a régua do mockup não refaz quando
    acusa o `motor-e-pct` de endereço morto.
    """
    largura = {c.chave for c in _regua._campos_cravados(bancada)
               if c.alvo == "largura"}
    assert {"forca-pct", "motor-e-pct", "motor-d-pct"} <= largura, (
        f"os endereços de largura desta aba mudaram: {sorted(largura)}")
    for uniq, col in pacote["colunas"].items():
        for chave in sorted(largura & set(col)):
            assert "%" not in str(col[chave]), (
                f"{uniq}·{chave} saiu {col[chave]!r} — o pintor acrescenta o `%`")


def test_os_dois_motores_tem_o_mesmo_destino(pacote) -> None:
    """`motor-e-pct` e `motor-d-pct` saem do MESMO laço, com a MESMA forma.

    A acusação de que só o esquerdo é endereço morto não sobrevive a isto: os
    dois são emitidos pelo mesmo `for` sobre `motores_do_controle`, com o mesmo
    `_barra` por trás. O que difere entre eles, na régua, é só o valor que o
    DESENHO cravou.
    """
    for uniq, col in pacote["colunas"].items():
        for lado in ("e", "d"):
            assert f"motor-{lado}-pct" in col, f"{uniq} não emite o motor {lado}"
            assert f"motor-{lado}" in col, f"{uniq} não emite o número do motor {lado}"
        assert col["motor-e-pct"] == col["motor-d-pct"], (
            "sem pedido de vibração fresco os dois lados respondem igual — "
            f"e saíram {col['motor-e-pct']!r} e {col['motor-d-pct']!r}")
