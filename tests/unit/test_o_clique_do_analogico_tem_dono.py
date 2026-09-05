#!/usr/bin/env python3
"""A RÉGUA DO CLIQUE DO ANALÓGICO — e do terceiro estado que o produto não via.

POR QUE ELA EXISTE. `data-campo="l3"` e `data-campo="r3"` estão na página da aba
Controles desde o primeiro desenho, e até 02/09/2026 **ninguém os pintava**.
Medido pelo `casamento.medir("02-controles.html")` na ponta de `dev`
(2b219284): `vazios: ['l3', 'r3']` — a tela tinha onde e não havia quem
mandasse. Um endereço sem pintor não dá erro: `querySelector` acha o elemento,
o pacote não emite a chave, e o rótulo do mockup fica lá para sempre.

O QUE ELA COBRA, e o item 3 é o que dói:

1. os dois endereços recebem valor quando há leitura;
2. o clicado se distingue do solto;
3. **sem leitor, o valor é o travessão — nunca "solto".** `inputs` é `None`
   para todo controle que não seja o primário nem tenha retrato vivo do co-op
   (`daemon/ipc_handlers.py:3379-3383`), e foi assim que a mesa dela estava
   medida em 02/09/2026 às 04:23:

       uniq aabbcc000001 · bt  · is_primary True  · inputs presente · buttons []
       uniq aabbcc000002 · usb · is_primary False · inputs None

   Dizer "solto" sobre `None` é a tela afirmando uma leitura que ninguém fez —
   o mesmo defeito que `mesa_viva.SEM_LEITOR` nomeia: *"nunca o último valor
   como se fosse vivo, nunca zero fingindo repouso"*.

4. o mesmo para o touchpad, que era pior: `"touch-estado"` era a **constante**
   `"Sem toque"`. A tela afirmava, sem ler nada, que ninguém estava encostando.

5. e o espelho do item 1: **nada do que o pacote emite cai fora da página.**
   Eram três — `l2`, `r2` e `via` —, e os três entravam na conta de
   `cobertura.pintados` sem escrever um pixel.

A MORDIDA está escrita em cada teste, no lugar onde ela reprova.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: MAC da faixa sintética da casa — há dois portões de anonimato nesta árvore.
UNIQ = "aa:bb:cc:00:00:01"

#: O controle da régua. `is_primary` e `inputs` são o par que decide o terceiro
#: estado, e por isso cada teste os monta explicitamente em vez de herdar.
BASE = {
    "uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
    "battery_pct": 95, "lightbar_rgb": [0, 0, 255], "is_primary": True,
    "audio": {}, "speaker": {},
}


@pytest.fixture(scope="module")
def pac():
    import pacotes

    return pacotes


@pytest.fixture(scope="module")
def a02():
    from pacotes import a02_controles

    return a02_controles


@pytest.fixture(scope="module")
def desenho(a02):
    """O TEXTO DE TELA, e o dono dele é o PACOTE — não o gerador.

    A seta aponta para o produto por medição: o
    `portao_a_casa_sabe_e_o_produto_nao_faz` poda os `abaNN.py` da conta por
    serem BANCADA, e importar o gerador de dentro do pacote arrasta a bancada
    para o fecho de produção — em 02/09/2026 isso acendeu três lápides de
    `interface/monta.py` e reprovou o portão. Quem lê é o gerador.
    """
    return a02


def _card(pac, a02, entrada: dict) -> dict:
    """O dicionário de UM card, do pacote real, sem janela e sem daemon."""
    ctx = pac.Contexto(state={}, mesa=[], conectados=[entrada], estados={})
    return next(iter(a02.pacote(ctx)["cards"].values()))


# --------------------------------------------------------------------------
# 1 e 2. o clique, quando há leitura
# --------------------------------------------------------------------------
def test_sem_apertar_o_rotulo_e_o_do_desenho(pac, a02, desenho):
    """Solto, o círculo mostra o rótulo que o gerador desenhou — e só ele.

    MORDE: se o pacote emitir a marca do clicado por engano (trocar a condição
    por `not campo in apertados`), este teste reprova com `[L3]` no lugar de
    `L3` — e essa troca não apareceria em foto nenhuma, porque um analógico em
    repouso é o estado de 99% do tempo.
    """
    d = _card(pac, a02, {**BASE, "inputs": {}})
    assert d["l3"] == desenho.ROTULO_DO_CLIQUE["l"]
    assert d["r3"] == desenho.ROTULO_DO_CLIQUE["r"]


@pytest.mark.parametrize(
    ("botao", "campo", "lado"),
    [("l3", "l3", "l"), ("r3", "r3", "r")],
)
def test_o_clique_de_cada_analogico_aparece_sozinho(
    pac, a02, desenho, botao, campo, lado
):
    """Clicar L3 marca L3 e **não** marca R3, e vice-versa.

    O par é testado junto de propósito: a forma mais fácil de errar aqui é ler
    `apertados` uma vez e escrever nos dois campos — o defeito que a GTK evita
    com duas variáveis separadas (`controller_card.py:5453-5454`).

    MORDE: fazer os dois campos lerem o mesmo botão reprova na segunda metade.
    """
    d = _card(pac, a02, {**BASE, "inputs": {"buttons": [botao, "cross"]}})
    assert d[campo] == desenho.CLICADO % desenho.ROTULO_DO_CLIQUE[lado]
    outro = "r3" if campo == "l3" else "l3"
    outro_lado = "r" if lado == "l" else "l"
    assert d[outro] == desenho.ROTULO_DO_CLIQUE[outro_lado], (
        "o clique de um analógico acendeu o outro")


# --------------------------------------------------------------------------
# 3. O TERCEIRO ESTADO — e é o que esta régua existe para trancar
# --------------------------------------------------------------------------
def test_sem_leitor_os_dois_analogicos_dao_travessao(pac, a02, desenho):
    """`inputs: None` é "não sei", e nunca "não apertado".

    MEDIDO na mesa dela em 02/09/2026: o controle não-primário chega com
    `inputs` valendo `None` — o daemon só preenche a chave para o primário ou
    para quem tem retrato vivo do co-op (`ipc_handlers.py:3379-3383`). Antes
    desta cura o pacote nem emitia os campos, e o círculo mostrava o `L3` do
    mockup como se fosse leitura.

    MORDE: trocar o `tem_leitor` por `e.get("buttons")` (que é o que um `or {}`
    convida a fazer) faz este teste reprovar com `'L3' != '—'`. É a mordida
    exata: o `or {}` apaga a diferença entre `None` e `{}`.
    """
    import mesa_viva

    d = _card(pac, a02, {**BASE, "is_primary": False, "inputs": None})
    assert d["l3"] == mesa_viva.SEM_LEITOR
    assert d["r3"] == mesa_viva.SEM_LEITOR
    assert d["l3"] != desenho.ROTULO_DO_CLIQUE["l"], (
        "sem leitura, a tela mostrou o rótulo como se tivesse medido o repouso")


def test_dicionario_de_inputs_vazio_nao_e_falta_de_leitor(pac, a02, desenho):
    """`{}` é leitura que veio sem botão apertado — e isso é diferente de `None`.

    Os dois casos vizinhos, no mesmo teste, porque a régua só vale se separar
    os dois: um `inputs` vazio é o primário com as mãos paradas.

    MORDE: tratar `{}` como ausência (um `if not e:` no lugar do `isinstance`)
    põe travessão num controle que o daemon ESTÁ lendo, e reprova aqui.
    """
    d = _card(pac, a02, {**BASE, "inputs": {}})
    assert d["l3"] == desenho.ROTULO_DO_CLIQUE["l"]


# --------------------------------------------------------------------------
# 4. o touchpad, que era uma constante
# --------------------------------------------------------------------------
#: O bloco `touchpad` COMO O DAEMON O PUBLICA — as cinco chaves saem de UM
#: literal (`daemon/sensor_hub.py:155-161`). Esta régua montava
#: `{"touching": True}` sozinho, e **esse estado não existe**: medido em
#: 02/09/2026 às 19h, 60 leituras de `daemon.state_full` com os dois controles
#: dela, 36 blocos publicados, os 36 com `height,touching,width,x,y`. Medir um
#: estado que o produto não produz foi o que sustentou a recusa de
#: `touchpad_do_inputs` nesta aba — e a recusa custou a POSIÇÃO do dedo.
TOUCHPAD_PUBLICADO = {
    "touching": False, "x": 960, "y": 540, "width": 1920, "height": 1080,
}


def test_o_touchpad_deixou_de_ser_constante(pac, a02):
    """"Sem toque" era literal no código: um dedo não mudava um pixel.

    A PALAVRA É A DO PRODUTO desde 02/09/2026 (decisão dela, item 15):
    `texto_toques(1 if tocando else 0)`, a MESMA linha que a GTK escreve
    (`controller_card.py:5079`). Era `COM_TOQUE = "Tocando"`, palavra do
    desenho redigitada no pacote.

    MORDE: devolver a constante (`"touch-estado": "Sem toque"`) faz o caso do
    dedo reprovar — e era exatamente esse o estado do produto até 02/09/2026.
    """
    import mesa_viva
    from hefesto_dualsense4unix.app.widgets.sensor_widgets import texto_toques

    tocando = _card(pac, a02, {**BASE, "inputs": {
        "touchpad": {**TOUCHPAD_PUBLICADO, "touching": True}}})
    solto = _card(pac, a02, {**BASE, "inputs": {"touchpad": TOUCHPAD_PUBLICADO}})
    cego = _card(pac, a02, {**BASE, "is_primary": False, "inputs": None})
    assert tocando["touch-estado"] == texto_toques(1) == "1 toque"
    assert solto["touch-estado"] == texto_toques(0) == "Sem toque"
    assert cego["touch-estado"] == mesa_viva.SEM_LEITOR


# --------------------------------------------------------------------------
# 5. o espelho: nada emitido cai fora da página
# --------------------------------------------------------------------------
#: OS ÓRFÃOS QUE ESPERAM O `--publicar`, e não são desta aba: o `topo()` emite
#: `rodape.salvar` e `rodape.exportar` para as DEZ páginas, porque o `fim.html`
#: é um só para todas. A cura de 03/09/2026 fez a dica parar de nomear um perfil
#: que não é o dela — o desenho congelara o EXEMPLO do pedido dela (*"Salvar
#: Perfil grava no Mortal Kombat"*) em vez do nome, e as dez abas diziam "Grava
#: no perfil Mortal Kombat" com `meu_perfil` ativo.
#:
#: OS DOIS ENDEREÇOS ESTÃO NAS DEZ PÁGINAS DA BANCADA E EM NENHUMA PUBLICADA,
#: e a `mockup/DIVERGENCIAS.md` diz isso com todas as letras: *"o valor certo é
#: emitido e fica órfão até você publicar"*. Emitir antes não custa nada — o
#: `achar()` do piloto não encontra o endereço e escreve zero, calado.
#:
#: O teste abaixo é o que impede esta linha de apodrecer: no dia da publicação
#: ele reprova, e quem publicar esvazia a lista no mesmo commit.
#: VAZIA DESDE 03/09/2026 — ela mandou publicar as dez, o `fim.html` chegou às
#: páginas que o produto renderiza, e os dois deixaram de estar órfãos. Este
#: teste reprovou no mesmo minuto, que é o que ele foi feito para fazer.
ESPERAM_A_PUBLICACAO: tuple[str, ...] = ()


def test_a_aba_controles_nao_emite_para_endereco_que_a_pagina_nao_tem():
    """Órfão é valor calculado a cada tique e jogado fora — e conta cobertura falsa.

    Eram três em 02/09/2026, medidos na ponta de `dev`: `l2`, `r2` e `via`. Os
    três entravam em `cobertura.pintados` sem escrever um pixel, e o `via` é o
    pior deles: o cabeçalho do card mostra o transporte como TEXTO DO DESENHO,
    e medido às 04:23 os dois cabeçalhos diziam o contrário da mesa viva
    (`p1 → BT`, `p2 → USB`, e a tela dizia USB e BT).

    **A RÉGUA ENVELHECEU EM 03/09/2026 e ganhou a distinção que lhe faltava.**
    Ela exigia lista vazia, e ficou vermelha sobre os dois `rodape.*` — que não
    são desta aba nem são desperdício: são a cura do rodapé, emitida para as dez
    páginas e esperando o `--publicar` dela, DECLARADA em
    `mockup/DIVERGENCIAS.md`. Reprovar ali é reprovar a melhora em vez do
    defeito.

    A DIFERENÇA QUE ELA PASSOU A FAZER, e é a única que importa aqui: órfão
    **por descuido** (o pacote calcula e ninguém pintará nunca) contra órfão
    **por espera** (a bancada já tem o endereço, a publicada ainda não). O
    primeiro continua proibido; o segundo tem de estar NOMEADO em
    `ESPERAM_A_PUBLICACAO`, e some no dia da publicação.

    MORDE (três, e cada uma tem a sua frase): devolver
    `"via": (c.get("transport") or "").upper()` ao pacote reprova nomeando
    `via`; publicar a 02 sem esvaziar `ESPERAM_A_PUBLICACAO` reprova dizendo que
    a espera acabou; esvaziá-la antes de publicar reprova nomeando os dois.
    """
    import casamento

    m = casamento.medir("02-controles.html")
    orfaos = sorted(m["orfaos"])
    de_descuido = [k for k in orfaos if k not in ESPERAM_A_PUBLICACAO]
    assert de_descuido == [], (
        f"a aba Controles emite {de_descuido} e a página publicada não "
        f"tem endereço para eles — valor calculado a cada tique e jogado fora.")
    # O OUTRO LADO, e é ele que impede a declaração de apodrecer: quem está na
    # lista tem de estar REALMENTE órfão. No dia em que a 02 for publicada, os
    # dois endereços passam a existir na página, saem de `orfaos`, e esta
    # igualdade reprova pedindo que a lista seja esvaziada.
    ainda_esperando = tuple(k for k in ESPERAM_A_PUBLICACAO if k in orfaos)
    assert ainda_esperando == ESPERAM_A_PUBLICACAO, (
        f"a declaração diz que {list(ESPERAM_A_PUBLICACAO)} esperam o "
        f"`--publicar`, e hoje só {list(ainda_esperando)} estão órfãos. Ou a "
        f"publicação aconteceu e a lista ficou para trás, ou ela foi escrita "
        f"antes da hora — nos dois casos a declaração parou de dizer a verdade.")


def test_a_aba_controles_nao_deixa_endereco_da_pagina_sem_pintor():
    """O outro lado do espelho: `vazios` era `['l3', 'r3']`.

    MORDE: tirar do pacote as duas chaves do clique faz este teste reprovar
    nomeando as duas — que é o estado em que a aba viveu até 02/09/2026.
    """
    import casamento

    m = casamento.medir("02-controles.html")
    # O QUE O PILOTO PINTA NÃO É ÓRFÃO, e a lista é PERGUNTADA — 03/09/2026.
    # A publicação das dez levou a fita nova à 02, e `fita-chip` apareceu aqui
    # como "ninguém pinta". Ele tem dono: `monta.fita()` o emite e o piloto
    # troca o bloco `fita` INTEIRO a cada tique (`hefesto_vivo._fita`), então o
    # pacote da aba não tem — nem deve ter — opinião sobre ele.
    #
    # A LISTA SAI DO GERADOR, e não de nomes digitados: `monta.fita([])` devolve
    # o HTML que o piloto escreve, e dele se leem os endereços. Digitá-los faria
    # a quarta régua do dia a envelhecer por literal.
    import re as _re

    import monta

    do_piloto = set(_re.findall(r'data-campo="([^"]+)"', monta.fita([])))

    # E OS ENDEREÇOS QUE SÃO SÓ DE LEITURA — 05/09/2026. Um `data-campo` existe
    # para o piloto ESCREVER **ou** para ele LER; esta régua só conhecia a
    # primeira espécie, e por isso acusava a segunda de órfã.
    #
    # `card-aberto` é o caso, e a razão está escrita no gerador
    # (`aba02.py`, no `<input class="radio-mesa">`): os quatro rádios são um
    # GRUPO. Pintar `sim` num deles a cada tique reabriria, dez vezes por
    # segundo, o card que ela acabou de fechar; pintar `""` nos quatro fecharia
    # todos, porque um grupo de rádio sem nenhum marcado não tem card aberto.
    # O endereço existe para o piloto SABER qual está aberto — e é o que a
    # `--prova-de-mockup` lê para decidir se mede o card ou a tira.
    #
    # A LISTA É DECLARADA AQUI e não no pacote de propósito: quem a lê é esta
    # régua, e uma isenção mora onde ela é cobrada. Entrada nova pede a RAZÃO,
    # como as três acima — isenção sem motivo é a porta por onde um órfão de
    # verdade entra calado.
    so_de_leitura = {
        "card-aberto": "grupo de rádio: pintar reabriria o card que ela fechou",
    }
    sobrando = sorted(set(m["vazios"]) - do_piloto - set(so_de_leitura))
    assert sobrando == [], (
        f"a página 02-controles.html tem {sobrando} e ninguém os "
        f"pinta — o rótulo do mockup fica na tela como se fosse leitura.")

    # E A ISENÇÃO É COBRADA NOS DOIS SENTIDOS: no dia em que o endereço sair da
    # página, a declaração tem de sair junto, senão ela vira perdão a um nome
    # que já não existe.
    na_pagina = set(_re.findall(
        r'data-campo="([^"]+)"',
        (RAIZ / "src/hefesto_dualsense4unix/interface/paginas/02-controles.html")
        .read_text(encoding="utf-8")))
    mortas = sorted(set(so_de_leitura) - na_pagina)
    assert mortas == [], (
        f"{mortas} está declarado como só-de-leitura e não existe mais na "
        f"página — tire a declaração no mesmo commit que tirou o endereço")


# --------------------------------------------------------------------------
# 6. o texto de tela tem UM dono, e é o gerador
# --------------------------------------------------------------------------
def test_o_gerador_le_o_texto_de_tela_do_pacote(a02):
    """O `aba02.py` não pode ter uma SEGUNDA cópia das mesmas palavras.

    MORDE: redigitar `SEM_TOQUE = "Sem toque"` no gerador passa neste teste por
    igualdade de valor — por isso a régua compara IDENTIDADE (`is`), que só o
    import satisfaz. Foi por cópia divergente que o "Sem toque" já nasceu duas
    vezes nesta aba.
    """
    import aba02
    from hefesto_dualsense4unix.app.widgets import sensor_widgets

    #: ONDE MORA CADA PALAVRA DE TELA DESTA ABA. `SEM_TOQUE`/`COM_TOQUE` saíram
    #: da lista em 02/09/2026 e não é regressão: a palavra do touchpad passou a
    #: ser a do MOTOR (`texto_toques`), por decisão dela, e o gerador a lê de
    #: lá. O dono mudou de casa; a régua vai atrás dele em vez de cravar a
    #: casa antiga.
    donos = {"ROTULO_DO_CLIQUE": a02, "CLICADO": a02, "texto_toques": sensor_widgets}
    achados = [n for n in donos if hasattr(aba02, n)]
    #: O PISO CAIU DE TRÊS PARA DOIS, e é medição, não afrouxamento: o gerador
    #: importa `ROTULO_DO_CLIQUE` e `texto_toques`, e nunca importou `CLICADO`
    #: (ele monta a marca do clicado sozinho? não — quem a monta é o pacote, e
    #: o gerador não precisa dela). Eram TRÊS enquanto `SEM_TOQUE` e
    #: `COM_TOQUE` existiam; hoje a palavra do touchpad é UMA e vem do motor.
    #: Deixar o piso em três reprovaria a entrega, que é a forma exata do
    #: defeito que esta casa chama de "régua que cimenta o que existia".
    assert len(achados) >= 2, (
        f"o gerador só conhece {achados} — se ele parou de importar o texto de "
        f"tela do dono, esta régua ficou vazia e não mede mais nada.")
    for nome in achados:
        assert getattr(aba02, nome) is getattr(donos[nome], nome), (
            f"o gerador tem uma cópia própria de {nome} — duas verdades sobre "
            f"a mesma palavra de tela.")


def test_o_rotulo_do_circulo_e_o_mesmo_no_desenho_e_na_pintura(desenho):
    """A página publicada e o pacote têm de dizer a mesma palavra.

    Sem esta régua, mudar `ROTULO_DO_CLIQUE` no gerador e esquecer de republicar
    faria o primeiro tique TROCAR o rótulo do círculo — e a troca só apareceria
    numa foto que ninguém tira.

    MORDE: mude `ROTULO_DO_CLIQUE["l"]` para `"L³"` sem rodar o gerador; este
    teste reprova dizendo que a página publicada ainda diz `L3`.
    """
    from hefesto_dualsense4unix.interface import onde

    html = onde.pagina("02-controles.html", publicado=True).read_text(encoding="utf-8")
    for lado, campo in (("l", "l3"), ("r", "r3")):
        marca = f'data-campo="{campo}">{desenho.ROTULO_DO_CLIQUE[lado]}<'
        assert marca in html, (
            f"a página publicada não traz {marca!r} — o gerador e o pacote "
            f"passaram a dizer palavras diferentes sobre o mesmo círculo.")
