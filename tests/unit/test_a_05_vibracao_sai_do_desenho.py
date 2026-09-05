#!/usr/bin/env python3
"""05 · Vibração — a aba pior da casa, medida pela régua do mockup.

O NÚMERO QUE ESTA RÉGUA GUARDA, medido em 03/09/2026 com a mesa dela (um
DualSense White no cabo e um Galactic Purple no rádio), pelo
``hefesto_vivo.py --prova-de-mockup --voltas-por-aba 6``::

    antes    45 campos ·  25 PRODUTO ·  0 RÓTULO · 20 MOCKUP ·  55% pronto
    depois   47 campos ·  35 PRODUTO ·  8 RÓTULO ·  4 MOCKUP ·  91% pronto

OS VINTE ERAM TRÊS FAMÍLIAS, e o ponto desta régua é que elas NÃO recebem o
mesmo tratamento — dar a mesma marca às três seria maquiar:

* **8 x ``forca``** (os quatro degraus, nas duas colunas) — **DÍVIDA, e fechou.**
  Parecia rótulo e não era: o nome do degrau é fixo, mas QUAL deles está aceso é
  dado, e saía do desenho. A foto de 02/09 mostra o P1 em "Máximo" e o P2 em
  "Balanceado" com uma ``rumble_policy`` só no daemon — pelo menos uma das
  colunas mentia. A cura é o endereço ``data-campo="degrau"`` com o alvo
  ``classe``: a régua passa a medir o ESTADO, e o texto do botão sai de cena
  sem precisar de marca nenhuma.
* **4 x ``lado`` + 2 x ``testar`` + 2 x ``parar``** — **RÓTULO.** O que a régua
  lia neles era o ``<title>`` do glifo (o nome da peça, de
  ``docs/data/pecas-do-dualsense.csv``) e o texto de dois botões que ela decidiu
  em 30/08 justamente para não mudarem. Nenhum estado do produto os move.
* **2 x ``plastico`` + 2 x ``desenho``** — **NEM UM NEM OUTRO, e ficam
  cobrados.** São as quatro molduras do SVG. A régua as lê pelo ``textContent``,
  que num ``<div>`` com o desenho dentro devolve o ``<style>`` e os ``<title>``
  do SVG — texto que não muda nunca. As duas vivas o produto PINTA (o alvo
  ``plastico`` do ``escrever()``, medido em pixel: a borda do P1 é
  ``rgb(228,224,216)`` = ``#E4E0D8`` = White, e vira ``rgb(68,71,90)`` com
  ``--sem-cor``), e mesmo assim a régua as chama de ENDEREÇO MORTO — porque
  ``regua_do_mockup._campo`` e ``hefesto_vivo.LER_CAMPOS`` conhecem
  ``largura|valor|cor|classe|fundo|html`` e **não conhecem ``plastico``**. É
  buraco de régua, não dívida desta aba, e marcá-las de rótulo esconderia a
  única coisa que ainda falta medir aqui.

A MORDIDA: tire o ``data-campo="degrau"`` dos quatro botões em ``aba05._coluna``,
rode ``python3 aba05.py``, e ``test_os_oito_degraus_saem_do_produto`` reprova
nomeando os oito. Tire o ``data-hef-rotulo`` e
``test_os_oito_rotulos_estao_declarados`` reprova nomeando os oito.

ONDE ELA MEDE: na **BANCADA** (``mockup/``), que é onde o gerador escreve.
Apontá-la para o publicado daria verde sobre a página congelada.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "05-vibracao.html"

#: DOIS controles de mentira, que é a mesa desta cena — o desenho tem duas
#: colunas vivas e dois lugares vazios. MACs da faixa sintética da casa: há dois
#: portões de anonimato nesta árvore e eles não perdoam.
UNIQS = {"p1": "aa:bb:cc:00:00:01", "p2": "aa:bb:cc:00:00:02"}

#: O degrau que o daemon de mentira responde. Ele é DIFERENTE do que a cena do
#: mockup acende no P1 (`max`) de propósito: é essa divergência que separa
#: "a tela mudou" de "a tela continua no desenho".
POLITICA = "balanceado"


@pytest.fixture(scope="module")
def regua():
    import regua_do_mockup

    return regua_do_mockup


@pytest.fixture(scope="module")
def cravados(regua):
    """Os campos do arquivo da BANCADA, em ordem de documento."""
    import onde

    arq = onde.pagina(PAGINA)
    assert arq.exists(), f"a bancada não tem {PAGINA} — rode `python3 aba05.py`"
    return regua._campos_cravados(arq.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def declarados(regua):
    """O que o pacote MANDARIA pintar num tique, na forma que o piloto usa.

    Vem do pacote de verdade, nunca de uma lista digitada aqui: uma chave nova
    entra nesta régua sozinha, e uma que suma faz a régua acusar.
    """
    import pacotes

    conectados = [
        {"uniq": u, "player": i, "connected": True, "transport": "usb",
         "battery_pct": 95, "is_primary": i == 1, "inputs": {}}
        for i, u in enumerate(UNIQS.values(), start=1)]
    mesa = [{"pref": p, "jogador": i, "uniq": UNIQS.get(p, ""),
             "nome": "Régua", "via": "USB", "cor": "starlight-blue",
             "conectado": p in UNIQS}
            for i, p in enumerate(("p1", "p2", "p3", "p4"), start=1)]
    ctx = pacotes.Contexto(
        state={"rumble_policy": POLITICA, "rumble_mult_applied": 0.7,
               "active_profile": "regua"},
        mesa=mesa, conectados=conectados, estados={})
    carga = pacotes.normalizar(pacotes.pacote_da_pagina(PAGINA, ctx))
    # A CHAVE DA COLUNA É O `uniq`, e a tela endereça por `pref`. O piloto
    # traduz; aqui a tradução é uma linha, e sem ela o `dono` nunca casa.
    de_volta = {u: p for p, u in UNIQS.items()}
    return {(de_volta.get(dono, dono), chave): valor
            for (dono, chave), valor in regua._declarados_do_pacote(carga).items()}


def _quandos(cravados):
    """Os `data-hef-quando` de cada grupo do alvo `classe`, por endereço."""
    fora: dict[tuple[str, str], set[str]] = {}
    for c in cravados:
        if c.alvo == "classe" and c.quando:
            fora.setdefault((c.dono, c.chave), set()).add(c.quando)
    return fora


def _a_tela_depois_da_pintura(regua, cravados, declarados):
    """O que cada campo mostraria depois de um tique — e os selos da visita.

    O valor de um campo pintado é o que o `escrever()` deixa nele, e quem sabe
    dizer isso sem abrir navegador é a própria régua: `_declarado_neste_elemento`
    existe justamente para traduzir a declaração do pacote na língua daquele
    elemento. Usá-la aqui não é uma segunda implementação do pintor — é a mesma
    tradução, e o navegador CONCORDA: a prova em Chrome de 03/09 acende
    `economia` e apaga `max` com exatamente estes valores.

    Quem o pacote NÃO declara fica como está no arquivo, sem selo — que é o
    caso dos oito rótulos e das duas molduras dos lugares vazios.

    O ALVO `plastico` É A EXCEÇÃO, e ela É O ACHADO DESTA FRENTE: o
    `escrever()` do piloto o escreve numa PROPRIEDADE DE CSS
    (`el.style.setProperty('--plastico', …)`), então o texto do elemento não se
    mexe — mas ele ganha o selo da visita, como todo alvo. `_declarado_neste_
    elemento` não conhece esse alvo (nem `regua_do_mockup._campo`, nem o
    `LER_CAMPOS` do piloto), e devolveria o `#hex` como se fosse texto de tela.
    Reproduzir aqui o que o navegador faz é o que faz esta régua bater com o
    `--prova-de-mockup` de verdade, campo a campo.
    """
    quandos = _quandos(cravados)
    vivos, selos, vistos = [], [], {}
    for c in cravados:
        endereco = (c.dono, c.chave)
        i = vistos.get(endereco, 0)
        vistos[endereco] = i + 1
        bruto = declarados.get(endereco, declarados.get(("", c.chave), ...))
        if bruto is ...:
            vivos.append(c.valor)
            selos.append(False)
            continue
        if isinstance(bruto, list):
            bruto = bruto[i] if i < len(bruto) else ""
        if c.alvo == "plastico":
            vivos.append(c.valor)
        else:
            vivos.append(regua._declarado_neste_elemento(
                c, regua._como_a_tela_escreveria(bruto),
                frozenset(quandos.get(endereco, ()))))
        selos.append(True)
    return vivos, selos


@pytest.fixture(scope="module")
def vereditos(regua, cravados, declarados):
    vivos, selos = _a_tela_depois_da_pintura(regua, cravados, declarados)
    return regua._classificar(cravados, vivos, declarados, selos)


def _por_chave(vereditos, chave):
    return [v for v in vereditos if v.campo.chave == chave]


# --------------------------------------------------------------------------
# 1. os oito degraus são DADO, e saem do produto
# --------------------------------------------------------------------------
def test_os_oito_degraus_saem_do_produto(regua, vereditos):
    """Os quatro botões das duas colunas vivas deixaram de mostrar o desenho.

    Antes desta cura os oito eram `MOCKUP` — o pacote não emitia nada e a classe
    `on` saía da cena do mockup. Hoje o pacote emite `degrau` e o alvo `classe`
    acende quem casa, o que faz os oito virarem `PRODUTO`.
    """
    degraus = _por_chave(vereditos, "degrau")
    assert len(degraus) == 8, (
        f"são quatro degraus em duas colunas vivas, e a régua achou "
        f"{len(degraus)} — o endereço `degrau` sumiu do desenho")
    presos = [(v.campo.dono, v.campo.quando, v.classe) for v in degraus
              if v.classe != regua.PRODUTO]
    assert not presos, (
        f"degrau ainda mostrando o desenho: {presos}. O pacote emite "
        f"`degrau={POLITICA!r}` e a tela tem de mover a classe `on`.")


def test_o_degrau_aceso_e_o_da_mesa_e_nao_o_do_mockup(regua, cravados,
                                                      declarados):
    """A cena do mockup acende `max` no P1; o daemon diz que ele HERDA.

    É esta divergência que prova que a tela SAIU do desenho — se a régua fosse
    alimentada com o mesmo degrau que o mockup cravou, os oito ficariam iguais e
    o verde não diria nada.

    **E O QUE O DAEMON DIZ MUDOU EM 04/09/2026 — decisão [05] dela.** Nenhum
    dos dois controles desta cena tem override no perfil, então os dois HERDAM:
    o campo da coluna sai VAZIO e os quatro botões apagam. Quem acende é a
    LINHA DE MESA, e é ela que diz o degrau que o produto está usando. A
    divergência com o desenho ficou MAIOR, não menor: o mockup crava um aceso
    onde a tela viva não acende nenhum.
    """
    cena = {(c.dono, c.quando) for c in cravados
            if c.chave == "degrau" and c.valor}
    assert ("p1", "max") in cena, (
        "a cena do mockup deixou de acender `max` no P1 — a razão desta régua "
        "mudou, e ela virou vácuo")
    assert declarados[("p1", "degrau")] == "", (
        f"a coluna do P1 declarou {declarados[('p1', 'degrau')]!r} sem ter "
        f"ajuste próprio — o degrau herdado é o da linha de mesa")
    assert declarados[("", "degrau-mesa")] == POLITICA, (
        "a linha de mesa não declara o degrau geral — era ela que a decisão "
        "[05] existe para pôr na tela")

    vivos, _ = _a_tela_depois_da_pintura(regua, cravados, declarados)
    acesos = {(c.dono, c.quando) for c, v in zip(cravados, vivos, strict=True)
              if c.chave == "degrau" and v}
    assert not acesos, (
        f"depois do tique os acesos das colunas são {sorted(acesos)} — nenhuma "
        f"das duas tem ajuste próprio, e acender um degrau ali seria a coluna "
        f"afirmando uma escolha dela que não existe no disco")
    da_mesa = {c.quando for c, v in zip(cravados, vivos, strict=True)
               if c.chave == "degrau-mesa" and v}
    assert da_mesa == {POLITICA}, (
        f"a linha de mesa acendeu {sorted(da_mesa)} — ela é o único lugar da "
        f"tela que mostra o degrau que o produto está usando")


# --------------------------------------------------------------------------
# 2. os oito rótulos, e SÓ eles
# --------------------------------------------------------------------------
#: Os endereços marcados `data-hef-rotulo` nesta aba, e por quê. A lista é
#: EXAUSTIVA de propósito: a categoria dela só não vira esconderijo enquanto
#: alguém tiver de escrever aqui o nome de cada marca nova.
ROTULOS = {
    "lado": "o `<title>` do glifo é o NOME DO MOTOR, de "
            "docs/data/pecas-do-dualsense.csv — não muda em estado nenhum",
    "testar": "o texto do botão, decidido por ela em 30/08 para NÃO mudar",
    "parar": "o texto do botão, o par do Testar",
}


def test_os_oito_rotulos_estao_declarados(regua, vereditos):
    """Rótulo declarado sai da conta — e a marca é EXIGIDA, nunca inferida."""
    marcados = [v for v in vereditos if v.classe == regua.ROTULO]
    assert len(marcados) == 8, (
        f"os rótulos desta aba são oito (4 lado + 2 testar + 2 parar), e a "
        f"régua contou {len(marcados)}: "
        f"{sorted((v.campo.dono, v.campo.chave) for v in marcados)}")
    assert {v.campo.chave for v in marcados} == set(ROTULOS)


def test_a_marca_de_rotulo_nao_alcanca_dado(regua, cravados):
    """A PARCÍMONIA, e ela é o que separa a categoria do esconderijo.

    Um `data-hef-rotulo` num campo que o produto PINTA apagaria o campo da
    medição para sempre — o veredito `ROTULO` vem antes de todos os outros
    ramos do `_classificar`. Então nenhum elemento marcado pode ter alvo de
    pintura, e nenhum pode ser endereço que o pacote emita.
    """
    import pacotes

    marcados = [c for c in cravados if c.rotulo]
    com_alvo = [(c.dono, c.chave, c.alvo) for c in marcados if c.alvo != "texto"]
    assert not com_alvo, (
        f"campo marcado como rótulo TEM alvo de pintura: {com_alvo} — ou ele é "
        "dado, ou o alvo está sobrando")

    ctx = pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})
    emitidos = set()
    for col in (pacotes.pacote_da_pagina(PAGINA, ctx).get("colunas") or {}).values():
        emitidos |= set(col)
    colisao = {c.chave for c in marcados} & emitidos
    assert not colisao, (
        f"o pacote emite {sorted(colisao)} e o desenho o declara rótulo: uma "
        "das duas afirmações está errada")


# --------------------------------------------------------------------------
# 3. o `Máx` — decisão 11 dela
# --------------------------------------------------------------------------
def test_o_max_e_estado_e_o_espaco_fica_reservado(regua, cravados):
    """*"esconder RESERVANDO o espaço (`visibility:hidden`)"* — decisão dela.

    Duas metades, e as duas têm de valer: a palavra está SEMPRE no HTML das
    duas colunas vivas (senão não há o que esconder), e o CSS a esconde por
    `visibility`, nunca por `display:none` — que tiraria o elemento do fluxo e
    faria o número ao lado pular a cada mudança de degrau.
    """
    import onde

    doc = onde.pagina(PAGINA).read_text(encoding="utf-8")
    tetos = [c for c in cravados if c.chave == "mult-teto"]
    assert len(tetos) == 2, (
        f"o `Máx` é um por coluna viva, e a régua achou {len(tetos)}")
    assert all(c.alvo == "classe" for c in tetos), (
        "o `Máx` voltou a ser texto — o pintor poria `—` onde o desenho não põe "
        "nada, afirmando 'não sei' onde a resposta é 'não está no teto'")
    assert doc.count('data-campo="mult-teto" data-hef-alvo="classe">Máx<') == 2, (
        "a palavra `Máx` deixou de estar sempre no HTML")
    assert ".motor .teto.mx{visibility:hidden}" in doc, (
        "o `Máx` deixou de esconder RESERVANDO o espaço")
    assert "display:none" not in doc.split(".teto.mx")[1][:80], (
        "o `Máx` passou a sumir do fluxo, e o número ao lado desloca")


def test_o_teto_do_multiplicador_sai_do_produto():
    """`_no_teto` pergunta o teto a quem é dono dele, e não sabe o que é `—`.

    O DONO TROCOU EM 03/09/2026, decisão dela: *"0 a 200%"*. A barra deixou de
    parar no degrau `Máximo` (`app/telas/vibracao.teto_da_barra`, 150) e vai até
    onde ela pode ARRASTAR — `a05_vibracao.teto_da_barra`, que sai do
    `RUMBLE_CUSTOM_MULT_MAX` do esquema. A régua continua PERGUNTANDO; o que
    mudou é a quem.
    """
    from pacotes.a05_vibracao import _no_teto, teto_da_barra

    teto = teto_da_barra()
    assert _no_teto({"n": f"{teto}%", "sabe": "1"}) == "1"
    assert _no_teto({"n": f"{teto - 1}%", "sabe": "1"}) == ""
    assert _no_teto({"n": "—", "sabe": ""}) == "", (
        "campo sem informação acendeu o `Máx` — a tela afirmaria um teto que "
        "ninguém mediu")


# --------------------------------------------------------------------------
# 4. o que AINDA falta, e ele fica cobrado
# --------------------------------------------------------------------------
def test_as_quatro_molduras_continuam_cobradas(regua, vereditos):
    """As quatro molduras do SVG não viraram rótulo — e não podiam virar.

    Duas delas o produto PINTA (o alvo `plastico`), e a régua as chama de
    ENDEREÇO MORTO porque não sabe LER esse alvo; as outras duas são o lugar
    VAZIO, onde não há controle e não há o que escrever. Nenhuma das duas
    coisas é rótulo, e esta régua existe para que o número continue subindo
    quando a régua do mockup aprender o alvo que falta.

    A CONTA É DAS QUATRO MOLDURAS, e não da aba inteira: a fita do topo é de
    todas as dez (quem a emite é o `topo()` do piloto) e as duas linhas-mãe das
    barras (`forca`, `motor`) são CONTAINERS, cujo texto na tela é a soma dos
    filhos — coisa que este tique de mentira não sabe somar e o navegador sabe.
    O `--prova-de-mockup` de verdade mede as duas, e mediu: as quatro que
    sobram na `05-vibracao` são exatamente estas.
    """
    molduras = {(v.campo.dono, v.campo.chave): v.classe for v in vereditos
                if v.campo.chave in ("plastico", "desenho")}
    assert set(molduras) == {("p1", "plastico"), ("p2", "plastico"),
                             ("p3", "desenho"), ("p4", "desenho")}, (
        f"as molduras desta aba mudaram de endereço: {sorted(molduras)}")
    assert set(molduras.values()) == {regua.MOCKUP}, (
        f"uma moldura saiu da conta sem que a régua aprendesse a LER o alvo "
        f"`plastico`: {molduras}")
