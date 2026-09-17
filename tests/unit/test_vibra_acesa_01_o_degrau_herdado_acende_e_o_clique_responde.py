#!/usr/bin/env python3
"""A ABA VIBRAÇÃO NO PERFIL DELA: o degrau herdado acende, e o clique responde.

**QUEIXA DELA, 17/09/2026, com a foto da aba aberta:** *"o botão não tá ativo"*.
Nenhum dos três — Economia, Balanceado, Máximo — aceso, e a coluna ao lado
marcando **150%**. A tela negando a força que a mão dela sentia.

O PERFIL EM QUE ISSO ACONTECE é o que estas réguas montam, e ele é o dela:
DON'T SCREAM, `rumble.policy = "max"` no global, e o bloco `controllers[uniq]`
existindo **sem** a seção `rumble`. Medido no disco dela em 17/09: dos 29
perfis, **6** têm política global escrita e só **5** (9 entradas) têm override
por controle. *Na maioria das colunas da maioria dos perfis, a força é HERDADA*
— que é justamente o caso que a tela não sabia mostrar.

**POR QUE NÃO SE MEDE COM UM PERFIL QUE TEM OVERRIDE:** esse caso já funcionava,
e foi por medi-lo que a aba passou de 04/09 a 17/09 assim. Um override próprio
acende o degrau desde 03/09; o buraco inteiro estava na herança.

## SÃO DOIS DEFEITOS, E AS MORDIDAS SÃO SEPARADAS

**1. O degrau herdado não tinha onde acender.** `a05_vibracao` só emitia o
degrau quando aquele controle tinha política PRÓPRIA gravada no perfil; quando
herdava, emitia vazio — e o alvo `classe` do pintor apaga os três quando o valor
não casa com nenhum `data-hef-quando`.

Era **meia decisão**. A [05] dela, de 04/09, mandava a coluna sem ajuste próprio
não acender *"e passar a apontar para essa linha"* — a LINHA DE MESA, que diria
o degrau em vigor. A linha de mesa foi apagada **um dia depois**, em 05/09, por
outra decisão dela (*"não é pra ter mesa em nada da interface"*). O contrapeso
saiu, o vazio ficou, e o estado herdado deixou de ter lugar na tela.

A cura devolve a procedência ao lugar que sobrou — o próprio botão: ele acende
(é a força que vale) e ganha a marca `degrau-herdado` na caixa dos três, que a
folha desenha com borda tracejada. **Herdado continua diferente de escolhido; o
que deixou de existir é "herdado = nada na tela".**

**2. O clique morto, e ele é pior.** Com o global em `max` e nenhum override,
clicar "Máximo" não gravava (`draft_config.with_controller_rumble` limpa o
override igual ao global, regra COR-04), não acendia (defeito 1) e **não dizia
nada**. Ela clicou três vezes achando que estava quebrado.

A DECISÃO, e ela é de produto: **responder, não gravar**. Forçar o override
escreveria no disco um valor que não muda um byte do que chega ao motor — a peça
já vibra em Máximo — e quebraria a COR-04, que é o que faz "voltei os dois para
Balanceado" deixar o perfil limpo. Escrever estado falso para simular resposta é
a família de defeito que esta aba passou 04/09 arrancando: *grava e não aplica*.

**E A FRASE JÁ EXISTIA, SEM NUNCA TER RODADO.** A
``FRASE_DO_QUE_A_COLUNA_MOSTRA`` foi escrita em 04/09 dizendo exatamente *"a sua
escolha é igual à força geral"*, e o ``if mostra != policy`` que a guardava a
tornava inalcançável: quando a escolha é igual ao global, o override é limpo e a
coluna passa a mostrar o próprio global — logo ``mostra == policy``, e o `if`
nunca entrava. :func:`test_a_frase_do_caso_herdado_tem_caminho` é a régua que
impede essa forma de voltar.

## AS MORDIDAS, uma por defeito

* **defeito 1** — em ``a05_vibracao.pacote``, faça o campo ``degrau`` sair
  vazio quando a coluna herda;
  :func:`test_a_coluna_que_herda_acende_o_degrau_em_vigor` reprova com
  ``degrau=''``. Tire só o ``degrau-herdado`` e
  :func:`test_o_degrau_herdado_nao_tem_a_cara_do_escolhido` reprova sozinha — é
  o que impede a cura de virar mentira nova;
* **defeito 2** — em ``_aplicar_a_forca``, apague o ramo ``if not mudou``;
  :func:`test_o_clique_no_degrau_que_ja_vale_responde` reprova com
  ``recado=None``. As duas metades do silêncio são medidas juntas em
  :func:`test_o_silencio_medido_na_tela_dela_nao_volta`, que é a cena inteira.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "05-vibracao.html"

#: O ENDEREÇO DA BANCADA — faixa SINTÉTICA da casa, nunca derivada de um MAC
#: real. Há dois portões de anonimato nesta árvore, e uma máscara aplicada a um
#: endereço de verdade ainda carrega o OUI dela.
UNIQ = "aa:bb:cc:00:00:01"
CHAVE = "aabbcc000001"

#: A FORÇA GERAL DO PERFIL DELA. `max` é o que o DON'T SCREAM tem no disco, e é
#: o degrau que ela clicou três vezes sem resposta.
GLOBAL = "max"


class PonteDeMentira:
    """Guarda o que foi pedido ao daemon. NUNCA fala com o dela."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append(f"profile_switch:{nome}")
        return True

    def chamar(self, metodo: str, **_: Any) -> bool:
        self.chamadas.append(metodo)
        return True


def _o_perfil_dela(com_override: str | None = None) -> dict[str, Any]:
    """O perfil DELA na forma CRUA que a pintura lê — global `max`, sem override.

    CRU E SEM PYDANTIC de propósito: é o que `pacotes/perfil.ativo` entrega à
    tela, lendo o JSON direto. Montar um `Profile` aqui mediria a borda do
    esquema, e o que esta régua persegue é o caminho da PINTURA.

    O BLOCO `controllers[uniq]` EXISTE E NÃO TEM `rumble` — é a forma exata do
    disco dela, e não um `controllers` vazio: o DON'T SCREAM guarda `leds`,
    `speaker` e `mic` para aquele controle e nenhuma opinião sobre vibração. Um
    dicionário vazio mediria um perfil mais pobre que o dela e deixaria passar
    uma cura que só olhasse a presença da chave do controle.
    """
    dele: dict[str, Any] = {"leds": {"lightbar": [65, 9, 55]},
                            "speaker": {"volume": 102, "muted": False}}
    if com_override:
        dele["rumble"] = {"policy": com_override}
    return {"name": "Bancada",
            "rumble": {"policy": GLOBAL, "custom_mult": None},
            "controllers": {CHAVE: dele}}


@pytest.fixture
def pac():
    import pacotes

    return pacotes


@pytest.fixture
def a05():
    from pacotes import a05_vibracao

    return a05_vibracao


@pytest.fixture
def disco_dela(monkeypatch, a05):
    """Desvia o perfil ATIVO para o dela, e o disco para a memória.

    DOIS DESVIOS PORQUE SÃO DOIS CAMINHOS, e confundi-los foi o que fez esta
    aba ser medida com o perfil errado: a PINTURA lê por `perfil.ativo` (JSON
    cru) e o GESTO grava por `loader.load_profile`/`save_profile` (pydantic).
    Desviar só o primeiro deixaria o clique falando com o disco de verdade —
    que é o perfil DELA, e ela está com o controle na mão.
    """
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import Profile

    vivo: dict[str, Any] = {"cru": _o_perfil_dela()}
    gravados: list[Any] = []

    def _ativo(_nome: str = "") -> dict[str, Any]:
        return vivo["cru"]

    def _nome_do_ativo(_state: Any = None) -> str:
        return "Bancada"

    def _load(_nome: str) -> Any:
        cru = dict(vivo["cru"])
        return Profile.model_validate({**cru, "match": {"type": "criteria"}})

    def _save(prof: Any, **_: Any) -> None:
        gravados.append(prof)

    monkeypatch.setattr(a05._perfil, "ativo", _ativo, raising=False)
    monkeypatch.setattr(a05._perfil, "nome_do_ativo", _nome_do_ativo,
                        raising=False)
    monkeypatch.setattr(loader, "load_profile", _load, raising=False)
    monkeypatch.setattr(loader, "save_profile", _save, raising=False)
    return vivo, gravados


def _ctx(pac):
    """Um tique com UM controle na mesa e a força geral do perfil dela.

    O `rumble_policy` do `state` é o que o daemon publica da MESA, e é de onde a
    coluna HERDA quando não tem opinião própria — a mesma precedência de
    `app/draft_config.effective_rumble_for`.
    """
    return pac.Contexto(
        state={"active_profile": "Bancada", "rumble_policy": GLOBAL,
               "rumble_mult_applied": 1.5},
        mesa=[{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
               "via": "USB", "cor": "starlight-blue", "plastico": "#123456",
               "conectado": True}],
        conectados=[{"uniq": UNIQ, "player": 1, "connected": True, "index": 0,
                     "transport": "usb", "battery_pct": 90, "inputs": {}}],
        estados={})


def _coluna(pac) -> dict[str, Any]:
    """A coluna do P1 como o pacote a manda para a tela."""
    fora = pac.pacote_da_pagina(PAGINA, _ctx(pac))["colunas"]
    assert UNIQ in fora, f"a coluna do P1 sumiu do pacote: {sorted(fora)}"
    return fora[UNIQ]


# ---------------------------------------------------------------------------
# 1. O DEGRAU HERDADO ACENDE
# ---------------------------------------------------------------------------
def test_a_coluna_que_herda_acende_o_degrau_em_vigor(pac, disco_dela) -> None:
    """Sem override, a coluna acende o degrau da força geral.

    É A QUEIXA DELA, na asserção mais curta que ela cabe: com `max` no global e
    nenhum override, o produto está vibrando em Máximo — e a tela tem de dizer
    Máximo. Emitir `""` apaga os três e é o que ela fotografou.
    """
    col = _coluna(pac)
    assert col["degrau"] == GLOBAL, (
        f"a coluna emitiu {col['degrau']!r} com a força geral em {GLOBAL!r} e "
        f"sem override — os três botões apagam, que é exatamente o que ela "
        f"fotografou em 17/09: 'o botão não tá ativo'")


def test_o_degrau_herdado_nao_tem_a_cara_do_escolhido(pac, disco_dela) -> None:
    """Aceso, sim — igual ao escolhido, não. A decisão [05] dela continua de pé.

    ESTA RÉGUA É O CONTRAPESO DA DE CIMA, e sem ela a cura seria uma mentira
    nova: um degrau herdado com a mesma cara de um escolhido devolve a aba ao
    estado de 03/09, em que ela não tinha como saber se aquilo era escolha dela
    ou herança.
    """
    col = _coluna(pac)
    assert col["degrau-herdado"] == "1", (
        "a coluna herdou o degrau e não marcou a procedência — aceso igual ao "
        "escolhido é a mentira que a decisão [05] dela nasceu para matar")


def test_a_coluna_com_override_proprio_nao_se_diz_herdada(
        pac, disco_dela) -> None:
    """O par da régua acima: com ajuste próprio, a marca NÃO sai.

    Uma marca cravada em `"1"` passaria as duas réguas de cima e diria "herdado"
    sobre uma escolha dela — o defeito espelhado. Aqui o override é `economia`,
    DIFERENTE do global `max`, senão o produto o limparia e a cena mediria
    herança de novo.
    """
    vivo, _ = disco_dela
    vivo["cru"] = _o_perfil_dela(com_override="economia")

    col = _coluna(pac)
    assert col["degrau"] == "economia", (
        f"a coluna com override próprio emitiu {col['degrau']!r} — a "
        f"precedência do produto é o override vencendo o global")
    assert col["degrau-herdado"] == "", (
        "a coluna tem ajuste próprio e a tela disse que ele é herdado")


def test_sem_politica_nenhuma_a_marca_nao_afirma_procedencia(
        pac, disco_dela) -> None:
    """Campo sem informação NÃO MOSTRA NADA — a regra dela, 02/09/2026.

    Com o daemon sem responder política, não há degrau aceso e não há herança a
    confessar. Marcar a coluna ali seria afirmar a procedência de um valor que a
    tela não está mostrando — a tela inventando um fato.
    """
    ctx = _ctx(pac)
    ctx.state["rumble_policy"] = ""
    col = pac.pacote_da_pagina(PAGINA, ctx)["colunas"][UNIQ]
    assert col["degrau"] == "", f"acendeu {col['degrau']!r} sem política"
    assert col["degrau-herdado"] == "", (
        "sem degrau aceso a tela marcou 'herdado' — procedência de quê?")


def test_a_marca_tem_onde_pousar_nos_quatro_lugares() -> None:
    """O endereço existe no desenho, e nos QUATRO lugares.

    Um campo que o pacote emite e o desenho não endereça é dado que chega e cai
    no chão, calado — o defeito que ela mediu com os quatro DualSense na mesa e
    que o `check_os_quatro_lugares` guarda. A marca é da CAIXA dos três botões,
    não de cada botão: a mesma verdade em três elementos divergiria no primeiro
    degrau novo.
    """
    import onde

    html = onde.pagina(PAGINA).read_text(encoding="utf-8")
    quantos = html.count('data-campo="degrau-herdado"')
    assert quantos == 4, (
        f"a marca do herdado aparece {quantos} vez(es) na bancada, e a mesa "
        f"tem quatro lugares — sem ela o degrau do controle que chegar naquela "
        f"coluna acende sem dizer de onde veio")
    assert 'data-hef-classe="herdado"' in html, (
        "a marca perdeu a classe própria e voltaria a acender com a cara do "
        "escolhido")
    assert ".vib .seg.herdado button.on{" in html, (
        "a folha não desenha mais o degrau herdado — o endereço existe e não "
        "muda um pixel, que é verde sobre nada")


# ---------------------------------------------------------------------------
# 2. O CLIQUE QUE JÁ VALE RESPONDE
# ---------------------------------------------------------------------------
def test_o_clique_no_degrau_que_ja_vale_responde(pac, disco_dela) -> None:
    """Clicar "Máximo" com o global em `max` devolve uma linha para a faixa.

    **É O CLIQUE MORTO INTEIRO.** Não grava (e não deve: a peça já vibra em
    Máximo), e até 17/09 também não dizia nada — três desfechos do produto e
    nenhum canal de volta.
    """
    fn = pac.gesto_da_pagina(PAGINA, "forca")
    assert fn is not None, "o gesto `forca` perdeu o dono"

    fora = fn(_ctx(pac), {"uniq": UNIQ, "forca": GLOBAL}, PonteDeMentira())

    assert fora is not None and fora.get("recado"), (
        "clicar o degrau que já vale devolveu SILÊNCIO — é a queixa dela de "
        "17/09, e o gesto não tem outro canal para a tela")
    assert "Máximo" in fora["recado"], (
        f"o recado não nomeia o degrau: {fora['recado']!r}")


def test_o_recado_do_clique_que_ja_vale_diz_a_procedencia(
        pac, disco_dela) -> None:
    """A frase do caso HERDADO é a que fala da força geral.

    E ela carrega a procedência em PALAVRAS — o que faz o defeito 1 chegar à
    tela dela mesmo antes de a marca nova ser publicada: até o `--publicar 05`,
    a página que o produto renderiza não tem o endereço `degrau-herdado`, e esta
    linha é o canal que sobra.
    """
    from pacotes import a05_vibracao as a05

    fn = pac.gesto_da_pagina(PAGINA, "forca")
    fora = fn(_ctx(pac), {"uniq": UNIQ, "forca": GLOBAL}, PonteDeMentira())

    esperado = a05.FRASE_DO_QUE_A_COLUNA_MOSTRA % "Máximo"
    assert esperado in fora["recado"], (
        f"o recado do caso herdado é {fora['recado']!r} e a frase que fala da "
        f"força geral é {esperado!r}")


def test_a_frase_do_caso_herdado_tem_caminho(pac, disco_dela) -> None:
    """A ``FRASE_DO_QUE_A_COLUNA_MOSTRA`` é ALCANÇÁVEL — e não era.

    **ESTA RÉGUA GUARDA UMA FORMA DE DEFEITO, não uma linha.** A frase foi
    escrita em 04/09 para o caso *"a sua escolha é igual à força geral"*, e o
    `if mostra != policy` que a guardava a tornava inalcançável: quando a
    escolha é igual ao global o override é limpo, a coluna passa a mostrar o
    próprio global, e `mostra == policy`. Texto certo, sem caminho que o
    produzisse — o que o `casa-sabe` chama de promessa sem chamador, e que
    nenhum portão pegou porque a constante ERA citada no código.

    Se alguém voltar a fechar o caminho, esta régua reprova antes da tela dela.
    """
    from pacotes import a05_vibracao as a05

    fn = pac.gesto_da_pagina(PAGINA, "forca")
    fora = fn(_ctx(pac), {"uniq": UNIQ, "forca": GLOBAL}, PonteDeMentira())
    assert a05.FATO_DO_AJUSTE_GERAL not in (fora or {}).get("recado", ""), (
        "o clique que já valia respondeu com a frase do `Auto` — ela fala de "
        "uma peça que VOLTOU ao ajuste geral, e aqui nada voltou")


def test_o_clique_que_ja_vale_nao_escreve_no_perfil(pac, disco_dela) -> None:
    """Responder não é gravar — a COR-04 continua de pé.

    **ERA A OUTRA SAÍDA POSSÍVEL, e foi recusada com razão medida.** Gravar o
    override do degrau que já vale faria a tela parecer viva escrevendo no disco
    um valor que não muda um byte do que chega ao motor, e quebraria a regra de
    `draft_config.with_controller_rumble` (*"o override guarda só o que DIVERGE
    do global"*) — a mesma que faz "voltei os dois para Balanceado" deixar o
    perfil limpo, e a mesma de `with_controller_leds`.

    Se um dia a casa decidir o contrário, é esta régua que tem de cair primeiro,
    com a decisão dela escrita ao lado.
    """
    _, gravados = disco_dela
    ponte = PonteDeMentira()

    pac.gesto_da_pagina(PAGINA, "forca")(
        _ctx(pac), {"uniq": UNIQ, "forca": GLOBAL}, ponte)

    assert gravados == [], (
        f"o clique gravou {len(gravados)} perfil(is) para dizer uma frase — a "
        f"peça já vibra em {GLOBAL!r}, e escrever estado que não muda o motor é "
        f"'grava e não aplica' pelo avesso")
    assert not ponte.chamadas, (
        f"o clique mandou {ponte.chamadas} ao daemon sem ter o que mudar")


def test_o_clique_que_muda_alguma_coisa_continua_calado(
        pac, disco_dela) -> None:
    """O desfecho 1 não virou ruído: quem muda a tela não precisa de frase.

    **É O CONTRAPESO DA CURA, e sem ele ela viraria o defeito oposto.** Uma
    frase por clique bem sucedido é ruído crônico — a tarja nasceria a cada
    degrau que ela escolhesse. O silêncio só é resposta quando a TELA responde,
    e aqui ela responde: o override vai ao disco e o tique seguinte acende
    "Economia" com a cara de escolhido.
    """
    _, gravados = disco_dela

    fora = pac.gesto_da_pagina(PAGINA, "forca")(
        _ctx(pac), {"uniq": UNIQ, "forca": "economia"}, PonteDeMentira())

    assert gravados, "o clique que DIVERGE do global tinha de gravar o override"
    assert fora is None, (
        f"o clique que mudou a tela também falou: {fora!r} — duas respostas "
        f"para o mesmo gesto, e a de baixo é ruído")


def test_o_clique_no_override_que_ja_e_dela_diz_a_outra_frase(
        pac, disco_dela) -> None:
    """Dois estados por baixo, duas frases — e a diferença é de FATO.

    Com um override próprio `economia` e a força geral em `max`, clicar
    "Economia" também não muda nada. Mas a frase do outro ramo diria *"a sua
    escolha é igual à força geral"*, e aqui ela NÃO é: `economia` não é `max`. A
    tela afirmaria uma igualdade que não existe.
    """
    from pacotes import a05_vibracao as a05

    vivo, gravados = disco_dela
    vivo["cru"] = _o_perfil_dela(com_override="economia")

    fora = pac.gesto_da_pagina(PAGINA, "forca")(
        _ctx(pac), {"uniq": UNIQ, "forca": "economia"}, PonteDeMentira())

    assert gravados == [], "nada mudou no disco e algo foi gravado"
    assert fora and fora.get("recado"), (
        "clicar o degrau que ela já escolheu para esta coluna respondeu com "
        "silêncio — o mesmo buraco, no outro estado")
    assert a05.FRASE_JA_E_A_ESCOLHA_DESTA_COLUNA % "Economia" in fora["recado"]
    assert a05.FRASE_DO_QUE_A_COLUNA_MOSTRA % "Economia" not in fora["recado"], (
        "a tela disse que a escolha dela é igual à força geral, e o override é "
        "`economia` contra um global `max` — afirmação falsa")


def test_o_arraste_da_barra_nao_ganhou_um_recibo_por_tique(
        pac, disco_dela) -> None:
    """O `custom` fica FORA do recado, e não é esquecimento.

    A barra "Personalizado" chega DUAS VEZES por arraste — o ouvinte do piloto
    escuta `change` e `click`, e soltar o polegar dispara os dois com o mesmo
    valor (está escrito em `a05_vibracao.intensidade`). A segunda passagem é
    sempre um não-mudou; um recibo ali seria uma tarja por arraste, que é o
    ruído que a cura do desfecho 1 existe para não criar.
    """
    fn = pac.gesto_da_pagina(PAGINA, "intensidade")
    assert fn is not None, "o gesto `intensidade` perdeu o dono"
    ctx = _ctx(pac)

    primeira = fn(ctx, {"uniq": UNIQ, "valor": "120"}, PonteDeMentira())
    segunda = fn(ctx, {"uniq": UNIQ, "valor": "120"}, PonteDeMentira())

    assert primeira is None, f"o arraste falou na primeira passagem: {primeira!r}"
    assert segunda is None, (
        f"o arraste falou na SEGUNDA passagem: {segunda!r} — o ouvinte manda o "
        f"mesmo valor duas vezes, e isto vira uma tarja por arraste")


# ---------------------------------------------------------------------------
# 3. A CENA INTEIRA, como ela a viveu
# ---------------------------------------------------------------------------
def test_o_silencio_medido_na_tela_dela_nao_volta(pac, disco_dela) -> None:
    """As TRÊS ausências de 17/09 numa cena só: não grava, não acende, não fala.

    É a linha que a sprint mediu — ``gravou_override=False,
    degrau_pintado='', recado=NENHUM`` — e o que esta régua exige é que as duas
    últimas tenham mudado. A primeira **continua `False` de propósito**: é a
    decisão, não o defeito.

    ELA MEDE NA ORDEM EM QUE ELA VIVEU: abrir a aba (o pacote), clicar (o
    gesto), e olhar de novo (o pacote outra vez). Medir só o gesto deixaria
    passar uma cura que respondesse a frase certa sobre uma tela ainda apagada.
    """
    _, gravados = disco_dela

    antes = _coluna(pac)
    assert antes["degrau"] == GLOBAL and antes["degrau-herdado"] == "1", (
        f"ao ABRIR a aba a coluna dela mostra {antes['degrau']!r} / "
        f"herdado={antes['degrau-herdado']!r} — era '' / '' em 17/09")

    fora = pac.gesto_da_pagina(PAGINA, "forca")(
        _ctx(pac), {"uniq": UNIQ, "forca": GLOBAL}, PonteDeMentira())
    assert fora and fora.get("recado"), "o clique voltou calado"

    depois = _coluna(pac)
    assert depois == antes, (
        "a tela mudou depois de um clique que não mudou nada no produto")
    assert gravados == [], "o clique escreveu no perfil dela"
