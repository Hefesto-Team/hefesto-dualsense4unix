"""A tira do "não sei" é TRACEJADA — e a apagada continua lisa e vazia.

DECISÃO 9 DELA, 03/09/2026::

    "Tira da luz: tracejado para 'não sei'; lisa e vazia para 'apagada'."

O QUE ESTAVA NA TELA, e é o defeito que ela nomeou: *"a barra está APAGADA"* e
*"não sei se está acesa"* pintavam a MESMA tira, **byte por byte** —
`background:var(--panel);color:transparent;opacity:1` nas duas. A única coisa
que as separava era o `title`, e quem não passa o mouse não vê.

SÃO TRÊS ESTADOS, e o motor já os distinguia: `rotulo_lightbar` responde por
CINCO ramos, e o primeiro retorno é o discriminador — a cor devolvida é *"a
BASE do accent"* e vem preenchida nos dois ramos em que o próprio motor avisa
que ela pode não estar no plástico (Nativo e Steam). Ler a base como "há luz?"
colapsa dois estados; foi o que a `a02_controles` mediu com sonda em 02/09.

O QUE ESTES TESTES COBREM, cada um com a mordida escrita:

1. `estado_da_tira` separa os TRÊS, pelos cinco ramos do motor;
2. a frase da apagada é PERGUNTADA ao motor, nunca digitada;
3. o desenho da incerta e o da apagada deixaram de ser iguais;
4. a incerta nunca sai sem estilo de linha — o PISO contra a tira branca;
5. o estado tem endereço próprio, e ele vem DEPOIS do `luz` no dicionário;
6. a folha da bancada desenha o contorno, e com o `!important` que ele precisa.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"), str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


#: A MESA, na forma que `mesa_viva.mesa_do_estado` devolve. MAC da faixa
#: sintética da casa — há dois portões de anonimato nesta árvore.
MESA = [
    {"pref": "p1", "uniq": "aa:bb:cc:00:00:01", "jogador": 1, "cor": "white",
     "nome": "White", "via": "USB", "transporte": "usb"},
]

#: O MESMO CONTROLE em cada um dos cinco ramos de `rotulo_lightbar`. A diferença
#: entre eles é só o que o daemon publicou sobre a barra — que é exatamente o
#: que o produto tem para decidir.
ACESO = {"uniq": "aa:bb:cc:00:00:01", "transport": "usb", "connected": True,
         "player": 1, "player_slot": 1, "is_primary": True,
         "lightbar_rgb": [0, 0, 255], "lightbar_on": True,
         "lightbar_source": "sysfs"}
DESLIGADO = dict(ACESO, lightbar_on=False)
SEM_FONTE = dict(ACESO, lightbar_source="desconhecida")
SEM_COR = {k: v for k, v in ACESO.items() if k != "lightbar_rgb"}
SEGURADO = dict(ACESO, lightbar_disputada=True)


@pytest.fixture
def a04():
    from pacotes import a04_iluminacao

    return a04_iluminacao


@pytest.fixture
def carga():
    """O pacote da `04` com UM controle, no estado que o teste pedir."""
    import pacotes

    def montar(entrada, state=None):
        ctx = pacotes.Contexto(
            state=dict(state or {}, active_profile=""),
            mesa=list(MESA), conectados=[dict(entrada)], estados={})
        return pacotes.pacote_da_pagina("04-iluminacao.html", ctx)

    return montar


@pytest.fixture
def bancada():
    """O HTML da bancada — o desenho de HOJE, que é o que ela olha."""
    import onde

    return onde.pagina("04-iluminacao.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. os TRÊS estados, pelos cinco ramos do motor
# ---------------------------------------------------------------------------
def test_estado_da_tira_separa_os_tres_pelos_cinco_ramos(a04):
    """Cada ramo do motor cai no estado certo, e "não sei" não vira "apagada".

    A MORDIDA: faça `estado_da_tira` devolver `APAGADA` para todo `recado` que
    não seja `None` — que é exatamente o que o código fazia antes de hoje, com
    a pergunta *"há tinta?"* no lugar da pergunta *"o que o motor disse?"* — e
    as três últimas linhas reprovam.
    """
    from hefesto_dualsense4unix.app.widgets.controller_card import rotulo_lightbar

    def estado(entrada, state=None):
        return a04.estado_da_tira(rotulo_lightbar(entrada, state or {})[0])

    assert estado(ACESO) == a04.ACESA
    assert estado(DESLIGADO) == a04.APAGADA
    assert estado(SEM_FONTE) == a04.INCERTA, (
        "cor desconhecida virou 'apagada'. O motor diz, com todas as letras, "
        "que o 0,0,0 do sysfs sem escrita nossa *pode ser o azul-kernel "
        "brilhando neste exato momento*.")
    assert estado(SEM_COR) == a04.INCERTA
    assert estado(SEGURADO) == a04.INCERTA, (
        "com a Steam segurando o `fd`, o que a classe LED devolve é o que o "
        "Hefesto PEDIU — não o que está no plástico.")
    assert estado(ACESO, {"native_mode": True}) == a04.INCERTA, (
        "em Nativo o jogo é dono do LED e escreve por hidraw; o daemon não "
        "pisa nele.")


def test_a_frase_da_apagada_e_perguntada_ao_motor_e_nao_digitada(a04):
    """Nenhuma das quatro frases do motor está digitada neste pacote.

    Das quatro que `rotulo_lightbar` devolve, só `ROTULO_LIGHTBAR_SEGURADA` é
    constante exportada. A da apagada se PERGUNTA — e o dono da pergunta é
    `a02_controles.ROTULO_DA_LUZ_APAGADA`, que já a resolveu para a aba irmã.

    A MORDIDA: troque o `ROTULO_DA_LUZ_APAGADA` por `"Lightbar: apagada"`
    digitado, e as duas linhas reprovam — a primeira porque o import some, a
    segunda porque a frase passa a aparecer numa COMPARAÇÃO. Uma cópia da frase
    envelhece calada: no dia em que o motor a trocasse, esta aba voltaria a
    colapsar os dois estados sem régua nenhuma reprovar.

    A SEGUNDA ASSERÇÃO OLHA SÓ AS LINHAS QUE COMPARAM, e não o arquivo inteiro:
    a frase é citada de propósito no docstring de `estado_da_tira`, que lista os
    cinco ramos do motor. Prosa que ENSINA não é cópia que DECIDE — a régua que
    não separasse as duas obrigaria a documentação a ficar vaga.
    """
    from pacotes.a02_controles import ROTULO_DA_LUZ_APAGADA

    fonte = pathlib.Path(a04.__file__).read_text(encoding="utf-8")
    assert "from .a02_controles import ROTULO_DA_LUZ_APAGADA" in fonte, (
        "a frase da apagada deixou de ser perguntada ao dono. Ela não se "
        "digita: `a02_controles.ROTULO_DA_LUZ_APAGADA` já a resolveu para a "
        "aba irmã, perguntando ao motor com a entrada mínima.")
    comparam = [linha for linha in fonte.splitlines()
                if "Lightbar: apagada" in linha and ("==" in linha or "!=" in linha)]
    assert not comparam, (
        f"a frase do motor virou literal numa comparação: {comparam}")
    assert a04.estado_da_tira(ROTULO_DA_LUZ_APAGADA) == a04.APAGADA


# ---------------------------------------------------------------------------
# 2. o desenho — o que ela vê sem passar o mouse
# ---------------------------------------------------------------------------
def test_a_incerta_e_a_apagada_deixaram_de_ser_a_mesma_tira(a04):
    """O defeito que ela nomeou, medido: as duas eram iguais byte por byte.

    A MORDIDA: tire o `estado=` da chamada (ou faça `incerta` sempre falso em
    `desenho_da_luz`) e esta linha reprova com as duas cadeias idênticas — que
    é a tela de hoje.
    """
    apagada = a04.desenho_da_luz("", 1.0, 1, estado=a04.APAGADA)
    incerta = a04.desenho_da_luz("", 1.0, 1, estado=a04.INCERTA)
    assert apagada != incerta, (
        "a tira do 'não sei' voltou a ser byte-idêntica à da 'apagada'. A "
        "ressalva volta a viajar só no `title`, e quem não passa o mouse não "
        "vê.")
    # A CLASSE, e não o nome solto: `data-hef-classe="incerta"` está nas DUAS
    # tiras — é a declaração do endereço, e não o estado. O que discrimina é o
    # fim do atributo `class`.
    na_classe = f' {a04.CLASSE_DA_INCERTA}"'
    assert na_classe in incerta, (
        "a tira do 'não sei' perdeu a classe que a folha desenha tracejada.")
    assert na_classe not in apagada, (
        "a tira APAGADA ganhou o tracejado do desconhecido — ela é um FATO que "
        "o motor afirma, e não uma dúvida.")


def test_a_incerta_nunca_sai_sem_estilo_de_linha(a04):
    """O PISO, e ele é o que impede a tira branca na página ainda não publicada.

    O halo é `box-shadow: … currentColor` (`.tira-luz.esq`/`.dir`). Uma tira
    sem `color` de linha herda o `--fg` desta página — `#f8f8f2` — e a barra
    que o produto diz NÃO CONHECER acenderia branca, mais forte que a acesa.
    É o mesmo defeito que o `TIRA_APAGADA` já aprendeu na foto de 02/09.

    A MORDIDA: faça `desenho_da_luz` emitir a incerta sem o atributo `style` —
    confiando só na folha nova — e esta linha reprova. Na tela, o preço aparece
    em qualquer página cuja folha ainda não tenha `.tira-luz.incerta`: o
    publicado de hoje.
    """
    incerta = a04.desenho_da_luz("", 1.0, 1, estado=a04.INCERTA)
    assert incerta.count(f'style="{a04.TIRA_APAGADA}"') == 2, (
        "a tira do 'não sei' saiu sem o estilo de linha do piso. Sem ele o "
        "halo `currentColor` herda o `--fg` e a tira acende BRANCA onde a "
        "folha não conhece `.tira-luz.incerta`.")


def test_sem_estado_declarado_a_bancada_nunca_inventa_a_duvida(a04):
    """O gerador não tem motor a perguntar — e por isso nunca diz "não sei".

    A MORDIDA: troque o padrão de `estado` para `INCERTA` e esta linha reprova.
    Na tela, o preço seria a bancada inteira tracejada: uma dúvida que ninguém
    levantou, no desenho que é a especificação dela.
    """
    sem_estado = a04.desenho_da_luz("#7EB8D4", 0.82, 1)
    assert f' {a04.CLASSE_DA_INCERTA}"' not in sem_estado
    assert "background:#7EB8D4" in sem_estado


# ---------------------------------------------------------------------------
# 3. o endereço — o que faz o estado ser MEDÍVEL, e não só visível
# ---------------------------------------------------------------------------
def test_o_pacote_manda_o_estado_e_so_diz_nao_sei_quando_nao_sabe(a04, carga):
    """`luz-incerta` é `"sim"` só nos três ramos do desconhecido.

    A MORDIDA: emita `"sim"` sempre (ou troque por `True`) e a primeira linha
    reprova — a tela passaria a tracejar a barra de um controle cuja cor o
    produto conhece.
    """
    e = a04.ENDERECO_DA_INCERTA
    assert carga(ACESO)["colunas"][ACESO["uniq"]][e] == ""
    assert carga(DESLIGADO)["colunas"][ACESO["uniq"]][e] == ""
    assert carga(SEM_FONTE)["colunas"][ACESO["uniq"]][e] == "sim"
    assert carga(SEGURADO)["colunas"][ACESO["uniq"]][e] == "sim"


def test_o_valor_e_texto_e_nunca_um_booleano(a04, carga):
    """`str(True)` é `"True"` e o JS escreveria `"true"`.

    As duas réguas desta casa que traduzem o declarado dizem, por escrito, que
    erram nesse par — e para uma CLASSE o erro é o pior dos dois: a régua
    acusaria endereço morto sobre uma tira que acende certo.

    A MORDIDA: emita `estado == INCERTA` cru e esta linha reprova.
    """
    valor = carga(SEM_FONTE)["colunas"][ACESO["uniq"]][a04.ENDERECO_DA_INCERTA]
    assert isinstance(valor, str) and not isinstance(valor, bool)


def test_o_estado_vem_depois_do_luz_porque_o_luz_recria_as_tiras(a04, carga):
    """A ordem do dicionário é CONTRATO, e a razão é mecânica.

    O `luz` troca o miolo do `.aceso` inteiro (alvo `html`) e recria as duas
    tiras; o pintor percorre os campos na ordem em que este dicionário os
    declara. Escrever a classe ANTES seria escrevê-la num elemento que a linha
    seguinte está prestes a substituir — e o selo da visita, que é o que a
    régua do mockup lê, iria embora junto.

    A MORDIDA: mova o `ENDERECO_DA_INCERTA` para antes do `"luz"` no
    `pacote()` e esta linha reprova.
    """
    col = carga(SEM_FONTE)["colunas"][ACESO["uniq"]]
    chaves = list(col)
    assert chaves.index("luz") < chaves.index(a04.ENDERECO_DA_INCERTA)


def test_a_tira_carrega_o_endereco_do_estado_nas_duas_paginas(a04, bancada):
    """Sem endereço, o estado viaja só dentro de um bloco `html`.

    E os alvos `html` e `fundo` são lidos pelo TEXTO visível — um desenho não
    tem texto. Sem esta marca, régua nenhuma consegue dizer se a tira que está
    na tela é a do produto ou a do desenho.

    A MORDIDA: tire o `marca` de `desenho_da_luz`, rode `python3 aba04.py`, e
    as quatro tiras da bancada perdem o endereço — esta linha reprova.
    """
    marca = (f'data-campo="{a04.ENDERECO_DA_INCERTA}" data-hef-alvo="classe" '
             f'data-hef-classe="{a04.CLASSE_DA_INCERTA}"')
    assert bancada.count(marca) == 4, (
        f"a bancada tem {bancada.count(marca)} tiras endereçadas; são duas "
        f"colunas conectadas, duas tiras cada.")


# ---------------------------------------------------------------------------
# 4. a folha — quem desenha o contorno
# ---------------------------------------------------------------------------
def test_a_folha_desenha_o_contorno_e_so_o_contorno(bancada):
    """O tracejado é CONTORNO, e nunca cor nova — ordem dela.

    Nesta aba tudo o que é CHEIO de cor é LUZ: as duas tiras, as cinco lâmpadas
    e os oito tons da guia. Uma cor inventada para "não sei" seria lida como
    uma luz que ninguém mediu.

    A REGRA É SÓ A `border`, e isso é resultado de mordida, não de gosto. Ela
    nasceu com `background:transparent !important;color:transparent;
    box-shadow:none;opacity:1`, e o comentário afirmava que sem o `!important` o
    contorno *"nunca aparece"*. Arranquei o `!important`, regerei e FOTOGRAFEI:
    o tracejado continua idêntico. As quatro declarações já vêm do `style=` de
    linha (`TIRA_APAGADA`, o piso), e o fundo que o `!important` disputava é
    `var(--panel)` — indistinguível do `--app-bg` atrás dele.

    A MORDIDA DESTA LINHA: tire a `border` da regra, rode o gerador e
    fotografe — a tira do "não sei" volta a ser igual à da apagada, que é o
    defeito da decisão 9. Esta asserção reprova antes disso.
    """
    regra = bancada.split(".tira-luz.incerta{", 1)
    assert len(regra) == 2, "a folha perdeu a regra do tracejado."
    corpo = regra[1].split("}", 1)[0]
    assert "border:1px dashed" in corpo, (
        "o desconhecido deixou de ser tracejado — e é a `border` que o "
        "desenha; medido arrancando cada declaração e fotografando.")
    assert "!important" not in corpo, (
        "voltou um `!important` que a mordida já derrubou uma vez: ele não "
        "muda um pixel, e regra que não morde mente sobre quem manda.")
