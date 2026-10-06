"""A tira do "não sei" é TRACEJADA — e a apagada continua lisa e vazia.

DECISÃO 9 DO USUÁRIO, 03/09/2026::

    "Tira da luz: tracejado para 'não sei'; lisa e vazia para 'apagada'."

O QUE ESTAVA NA TELA, e é o defeito que o usuário nomeou: *"a barra está APAGADA"* e
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
MESA = [
    {"pref": "p1", "uniq": "aa:bb:cc:00:00:01", "jogador": 1, "cor": "white",
     "nome": "White", "via": "USB", "transporte": "usb"},
]

#: O MESMO CONTROLE em cada um dos cinco ramos de `rotulo_lightbar`. A diferença
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


def test_estado_da_tira_separa_os_tres_pelos_cinco_ramos(a04):
    """Cada ramo do motor cai no estado certo, e "não sei" não vira "apagada"."""
    from hefesto_dualsense4unix.interface.cartao_do_controle import rotulo_lightbar

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
    assert estado(ACESO, {"native_mode": True}) == a04.ACESA, (
        "no Nativo a barra é do Hefesto, e a tira voltou ao tracejado")
    assert estado(DESLIGADO, {"native_mode": True}) == a04.APAGADA


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


def test_a_incerta_e_a_apagada_deixaram_de_ser_a_mesma_tira(a04):
    """O defeito que o usuário nomeou, medido: as duas eram iguais byte por byte."""
    apagada = a04.desenho_da_luz("", 1.0, 1, estado=a04.APAGADA)
    incerta = a04.desenho_da_luz("", 1.0, 1, estado=a04.INCERTA)
    assert apagada != incerta, (
        "a tira do 'não sei' voltou a ser byte-idêntica à da 'apagada'. A "
        "ressalva volta a viajar só no `title`, e quem não passa o mouse não "
        "vê.")
    na_classe = f' {a04.CLASSE_DA_INCERTA}"'
    assert na_classe in incerta, (
        "a tira do 'não sei' perdeu a classe que a folha desenha tracejada.")
    assert na_classe not in apagada, (
        "a tira APAGADA ganhou o tracejado do desconhecido — ela é um FATO que "
        "o motor afirma, e não uma dúvida.")


def test_a_incerta_nunca_sai_sem_estilo_de_linha(a04):
    """O PISO, e ele é o que impede a tira branca na página ainda não publicada."""
    incerta = a04.desenho_da_luz("", 1.0, 1, estado=a04.INCERTA)
    assert incerta.count(f'style="{a04.TIRA_APAGADA}"') == 2, (
        "a tira do 'não sei' saiu sem o estilo de linha do piso. Sem ele o "
        "halo `currentColor` herda o `--fg` e a tira acende BRANCA onde a "
        "folha não conhece `.tira-luz.incerta`.")


def test_sem_estado_declarado_a_bancada_nunca_inventa_a_duvida(a04):
    """O gerador não tem motor a perguntar — e por isso nunca diz "não sei"."""
    sem_estado = a04.desenho_da_luz("#7EB8D4", 0.82, 1)
    assert f' {a04.CLASSE_DA_INCERTA}"' not in sem_estado
    assert "background:#7EB8D4" in sem_estado


def test_o_pacote_manda_o_estado_e_so_diz_nao_sei_quando_nao_sabe(a04, carga):
    """`luz-incerta` é `"sim"` só nos três ramos do desconhecido."""
    e = a04.ENDERECO_DA_INCERTA
    assert carga(ACESO)["colunas"][ACESO["uniq"]][e] == ""
    assert carga(DESLIGADO)["colunas"][ACESO["uniq"]][e] == ""
    assert carga(SEM_FONTE)["colunas"][ACESO["uniq"]][e] == "sim"
    assert carga(SEGURADO)["colunas"][ACESO["uniq"]][e] == "sim"


def test_o_valor_e_texto_e_nunca_um_booleano(a04, carga):
    """`str(True)` é `"True"` e o JS escreveria `"true"`."""
    valor = carga(SEM_FONTE)["colunas"][ACESO["uniq"]][a04.ENDERECO_DA_INCERTA]
    assert isinstance(valor, str) and not isinstance(valor, bool)


def test_o_estado_vem_depois_do_luz_porque_o_luz_recria_as_tiras(a04, carga):
    """A ordem do dicionário é CONTRATO, e a razão é mecânica."""
    col = carga(SEM_FONTE)["colunas"][ACESO["uniq"]]
    chaves = list(col)
    assert chaves.index("luz") < chaves.index(a04.ENDERECO_DA_INCERTA)


def test_a_tira_carrega_o_endereco_do_estado_nas_duas_paginas(a04, bancada):
    """Sem endereço, o estado viaja só dentro de um bloco `html`."""
    marca = (f'data-campo="{a04.ENDERECO_DA_INCERTA}" data-hef-alvo="classe" '
             f'data-hef-classe="{a04.CLASSE_DA_INCERTA}"')
    assert bancada.count(marca) == 4, (
        f"a bancada tem {bancada.count(marca)} tiras endereçadas; são duas "
        f"colunas conectadas, duas tiras cada.")


def test_a_folha_desenha_o_contorno_e_so_o_contorno(bancada):
    """O tracejado é CONTORNO, e nunca cor nova — ordem de produto."""
    regra = bancada.split(".tira-luz.incerta{", 1)
    assert len(regra) == 2, "a folha perdeu a regra do tracejado."
    corpo = regra[1].split("}", 1)[0]
    assert "border:1px dashed" in corpo, (
        "o desconhecido deixou de ser tracejado — e é a `border` que o "
        "desenha; medido arrancando cada declaração e fotografando.")
    assert "!important" not in corpo, (
        "voltou um `!important` que a mordida já derrubou uma vez: ele não "
        "muda um pixel, e regra que não morde mente sobre quem manda.")
