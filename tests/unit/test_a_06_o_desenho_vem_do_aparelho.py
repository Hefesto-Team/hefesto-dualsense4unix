#!/usr/bin/env python3
"""A RÉGUA DO DESENHO NA ABA 06: o SVG é o do APARELHO, nunca o do mockup.

A LEI É DELA, 03/09/2026:

    "os svgs do dualsense, as bordas das fitas das areas, as escolhas dos
    players com cada controle — tudo isso muda de acordo com o controle
    identificado no canto superior. os svgs (…) nao sao os que  # noqa-acento: dela
    o meu mapa cataloga. isso ta errado"  # noqa-acento: citação literal dela

(Ela escreve sem acento, e a palavra dela não se corrige: as duas linhas levam
`noqa-acento` com a razão, que é o que o portão `acentuacao` pede.)

O QUE ESTA ABA TINHA, medido em 03/09/2026 com
`scripts/check_a_cor_vem_do_aparelho.py --aba 06`::

    06-navegacao.html    plastico 0   colorway 4   zona 72   TOTAL 76

Os QUATRO `data-colorway` eram os do desenho, sem endereço nenhum — nada no
produto tinha por onde trocá-los. As SETENTA E DUAS declarações de zona eram
quatro folhas PODADAS: `monta._so_o_colorway` guarda em cada SVG só as regras
do modelo pedido (3.082 bytes dos 45.452 dos 28), e um SVG assim **não tem como
virar outro aparelho**.

E UM FATO CAIU NO CAMINHO, porque medir é diferente de supor: **a tela desta
aba já mostrava a cor certa**. Medido no WebKit em 03/09, com os dois controles
dela na mesa, ANTES de qualquer conserto: o casco do P1 saía
`rgb(228, 224, 216)` — o White do mapa —, porque a `folha_do_plastico`
sobrescrevia as variáveis do modelo. O defeito não era o pixel, era o
mecanismo: as regras que leem essas variáveis são
`svg[data-colorway="cosmic-red"] …`, e casavam **porque o atributo do mockup
tinha ficado**. Ligar o atributo sem publicar os 28 teria apagado a cor em vez
de acertá-la — que é a armadilha que o alvo de atributo documenta.

AS DUAS METADES DA CURA, e cada uma sozinha é inútil:

1. o `<svg>` ganha `data-campo="desenho"`, `data-hef-alvo="atributo"` e
   `data-hef-atributo="data-colorway"` — o alvo de atributo do piloto;
2. a página publica a folha INTEIRA, os 28 modelos, uma vez. Sem isso o alvo
   escreve um colorway que nenhuma regra casa e o desenho cai nos `fill` crus.

E UMA TERCEIRA, que a mordida na tela revelou: sem `data-colorway` o
`ds_limpo.svg` mostra DOIS `fill="#b11f54"` crus — o Cosmic Red VELHO e errado
(a amostragem de 27/08 devolveu `#A51C48`). Um controle que ninguém
identificou aparecia com o Share, o Options e as bolas dos analógicos em carmim.
As zonas de um desenho sem colorway caem no neutro.

A MORDIDA: tire o `ENDERECO_DO_DESENHO` do `aba06.desenho()`, ou faça-o parar
de arrancar a folha podada, ou tire o `"desenho"` do `a06_navegacao.pacote()`,
ou apague a regra do neutro — cada um reprova um teste diferente, nomeando o
que se perdeu.
"""
from __future__ import annotations

import csv
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "06-navegacao.html"  # (noqa-acento) nome de arquivo
CORES_CSV = RAIZ / "docs/data/cores-do-dualsense.csv"

#: OS TRÊS ATRIBUTOS DO CONTRATO, escritos AQUI e não importados de `aba06`.
#: `import aba06` RODA o gerador — ele monta a página no import e a escreve na
#: bancada. Um teste que reescreve o arquivo que ele mede não é teste, é o
#: gerador com outro nome; e sob mordida ele morre de `SystemExit` antes de
#: qualquer `assert`, escondendo o que a mordida devia mostrar. Medido nesta
#: régua em 03/09/2026, na primeira mordida.
ENDERECO_DO_DESENHO = ('data-campo="desenho" data-hef-alvo="atributo"'
                       ' data-hef-atributo="data-colorway"')

#: DOIS CONTROLES SINTÉTICOS, na faixa da casa — há dois portões de anonimato
#: nesta árvore. O segundo está no RÁDIO, e pelo rádio a cor não chega.
UM = "aa:bb:cc:00:00:01"
DOIS = "aa:bb:cc:00:00:02"

CONTROLES = [
    {"uniq": UM, "connected": True, "transport": "usb", "player_slot": 1,
     "player": 1, "is_primary": True, "modelo": "White"},
    {"uniq": DOIS, "connected": True, "transport": "bt", "player_slot": 2,
     "player": 2, "is_primary": False},
]

#: A MESA COMO O PILOTO A MONTA. O `cor` do P1 é um slug que o mapa conhece e
#: que DISCORDA do desenho; o do rádio vem vazio, que é o estado real da mesa
#: dela quando o leitor de cor ainda não respondeu.
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


def _modelos_do_mapa() -> set[str]:
    """Os 28 ids, lidos do CSV que é dono deles.

    Digitá-los aqui criaria a segunda lista que envelhece calada — o defeito
    que o `cores-do-dualsense.csv` existe para não ter.
    """
    linhas = [linha for linha in CORES_CSV.read_text(encoding="utf-8").splitlines()
              if linha.strip() and not linha.lstrip().startswith("#")]
    return {(linha.get("id") or "").strip()
            for linha in csv.DictReader(linhas)
            if (linha.get("id") or "").strip()}


def _zonas_do_mapa() -> list[str]:
    """As classes de zona, lidas da folha que o gerador de cores pintou no SVG.

    Pelo caminho do TESTE, não pelo do gerador: `import monta` só lê arquivos,
    enquanto `import aba06` montaria a página inteira.
    """
    import monta

    return sorted(set(re.findall(
        r'svg\[data-colorway="[^"]+"\] (\.z-[a-z0-9_]+)', monta.DS)))


@pytest.fixture
def bancada() -> str:
    from hefesto_dualsense4unix.interface import onde

    return onde.pagina(PAGINA).read_text(encoding="utf-8")


@pytest.fixture
def miolo(bancada: str) -> str:
    """Só o miolo, sem comentário HTML e sem `<style>` — as três armadilhas que
    já fizeram as réguas das abas irmãs reprovarem o que estava certo."""
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
# 0. A DEPENDÊNCIA DURA — e ela some em SILÊNCIO quando falta
# ---------------------------------------------------------------------------
def test_o_piloto_tem_o_alvo_de_atributo():
    """Sem o alvo `atributo` no piloto, esta aba não fica igual: fica PIOR.

    MEDIDO NA TELA em 03/09/2026, com o `hefesto_vivo` sem o alvo e a página
    desta frente publicada: `escrever()` não reconhece `atributo`, cai no ramo
    padrão e faz `el.textContent = "white"` no `<svg>` — os QUATRO desenhos
    SOMEM da tela, e o cartão fica um retângulo vazio com o rótulo embaixo.
    *Endereço com o alvo errado é pior que endereço nenhum.*

    Este teste é o alarme do MERGE FORA DE ORDEM. Ele não mede a aba 06: mede
    que o degrau em que ela pisa está no lugar.
    """
    vivo = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py").read_text(
        encoding="utf-8")
    assert "alvo === 'atributo'" in vivo, (
        "o piloto não tem o ramo `atributo` do `escrever()` — publicar a 06 "
        "assim APAGA os quatro desenhos da tela dela")
    assert "atributo_escrevivel" in vivo, (
        "o piloto tem o ramo `atributo` sem a guarda de nome — um "
        "`data-hef-atributo` mal escrito passaria a mexer no endereço ou no "
        "selo da medição desta casa")


# ---------------------------------------------------------------------------
# 1. O DESENHO TEM ENDEREÇO — e o alvo que ALCANÇA um atributo
# ---------------------------------------------------------------------------
def test_os_quatro_desenhos_tem_o_endereco_do_colorway(miolo):
    """Os quatro lugares da mesa, inclusive os vazios.

    OS VAZIOS ENTRAM, e não é zelo: o piloto distribui a lista pelos elementos
    de mesmo `data-campo` NA ORDEM do HTML. Um lugar sem endereço tira uma casa
    da fila e o P4 recebe a cor do P3.
    """
    import monta

    assert miolo.count(ENDERECO_DO_DESENHO) == len(monta.MESA), (
        "um desenho da 06 perdeu o endereço do colorway — o `data-colorway` "
        "volta a ser o do mockup, e nada no produto o alcança")


def test_o_alvo_nomeia_o_atributo_certo(miolo):
    """`data-hef-alvo="atributo"` sem `data-hef-atributo="data-colorway"` é
    pior que endereço nenhum: o `escrever()` recusa o nome e a tela fica com o
    colorway do desenho, agora com uma régua verde por cima."""
    assert miolo.count('data-hef-alvo="atributo"') == miolo.count(
        'data-hef-atributo="data-colorway"'), (
        "há alvo `atributo` sem dizer QUAL atributo — o piloto recusa o nome "
        "vazio e não pinta nada")


def test_nao_ha_colorway_cravado_fora_dos_desenhos(miolo):
    """Todo `data-colorway` do miolo pertence a um `<svg>` endereçado."""
    import monta

    assert miolo.count("data-colorway=") == len(monta.MESA), (
        "apareceu `data-colorway` no miolo fora dos desenhos endereçados — "
        "cor de aparelho cravada onde o produto não tem como chegar")


# ---------------------------------------------------------------------------
# 2. A PÁGINA PUBLICA A TABELA DELA — os 28, uma vez
# ---------------------------------------------------------------------------
def test_a_pagina_publica_os_28_modelos(bancada):
    """A folha das cores é a TABELA dela, e tem de estar inteira.

    Uma folha podada não é tabela, é escolha: o SVG que a carrega só sabe ser
    UM modelo. Com os 28 publicados, o alvo de atributo pode escrever qualquer
    controle que ela ligar.
    """
    do_mapa = _modelos_do_mapa()
    na_pagina = set(re.findall(r'svg\[data-colorway="([^"]+)"\]', bancada))
    assert do_mapa, "o `cores-do-dualsense.csv` parou de declarar modelos"
    assert do_mapa <= na_pagina, (
        f"a 06 publica {len(na_pagina)} dos {len(do_mapa)} modelos do mapa — "
        f"faltam {sorted(do_mapa - na_pagina)}; quem tiver um desses vê o "
        f"desenho no cinza cru do `ds_limpo.svg`")


def test_nenhum_svg_carrega_a_folha_podada(bancada):
    """A folha do SVG SAI — a página já publica os 28, e a podada é justamente
    a que impede o desenho de virar outro aparelho."""
    assert "cores-do-dualsense-folha" not in bancada, (
        "voltou uma folha podada para dentro de um SVG da 06: ela traz UM "
        "modelo, e quatro cópias dela são a mesma escolha cravada quatro vezes")


def test_a_folha_publicada_e_uma_so(bancada):
    """Uma cópia, não quatro: o `monta.svg()` poda porque quatro cópias dos 28
    seriam 180 KB de CSS que ninguém lê. Publicar uma vez é o que paga a
    tabela inteira."""
    for modelo in ("white", "cosmic-red", "galactic-purple"):
        assert bancada.count(f'svg[data-colorway="{modelo}"]{{') == 1, (
            f"o bloco de variáveis de {modelo!r} aparece mais de uma vez — a "
            f"folha voltou a ser publicada por SVG")


# ---------------------------------------------------------------------------
# 3. SEM COLORWAY, SEM COR DE APARELHO — e sem carmim
# ---------------------------------------------------------------------------
def test_a_zona_sem_colorway_cai_no_neutro(bancada):
    """Todas as zonas do mapa, e não algumas.

    MEDIDO NA TELA em 03/09/2026 com `hefesto_vivo --sem-cor`: sem esta regra o
    desenho de um controle não identificado mostra dois `#b11f54` crus — o
    Cosmic Red velho que o `ds_limpo.svg` guarda no `style` do Share, do
    Options e nas bolas dos analógicos.
    """
    zonas = _zonas_do_mapa()
    assert len(zonas) >= 8, f"o mapa declara só {len(zonas)} zonas: {zonas}"
    for zona in zonas:
        assert f".ds-svg:not([data-colorway]) {zona} " in bancada, (
            f"a zona {zona} não cai no neutro quando o desenho fica sem "
            f"colorway — o `fill` cru do arquivo aparece como cor de aparelho")


# ---------------------------------------------------------------------------
# 4. O PACOTE ESCREVE O QUE LEU — e cala o que não leu
# ---------------------------------------------------------------------------
def test_o_pacote_manda_o_colorway_de_cada_lugar(carga):
    """Quatro entradas, na ordem da mesa, e o do rádio VAZIO."""
    desenho = carga["mesa"].get("desenho")
    assert desenho is not None, (
        "o pacote parou de emitir `desenho` — o `data-colorway` de cada SVG "
        "fica sendo o do mockup para sempre")
    assert len(desenho) == 4, f"a lista não cobre os quatro lugares: {desenho}"
    assert desenho[0] == "white", desenho
    assert desenho[1] == "", (
        "o lugar do rádio, sem cor lida, recebeu um colorway — campo sem "
        "informação não mostra nada, e um colorway inventado pinta um aparelho")
    assert desenho[2:] == ["", ""], desenho


def test_o_colorway_emitido_nao_e_o_do_desenho(carga):
    """O P1 da mesa é White; o P1 do mockup não é. A régua morre se alguém
    voltar a mandar o desenho para a tela."""
    import monta

    assert carga["mesa"]["desenho"][0] != str(monta.MESA[0]["cor"]), (
        "o pacote mandou para a tela o colorway do MOCKUP — é o defeito que "
        "esta onda inteira existe para matar")


def test_o_colorway_que_o_mapa_nao_conhece_vira_vazio():
    """Um slug fora do mapa pintaria o cinza cru PARECENDO cor lida.

    `""` dá o mesmo cinza — mas dizendo a verdade, e o neutro que a folha desta
    aba pinta por cima.
    """
    from pacotes.a06_navegacao import colorway_do_aparelho

    assert colorway_do_aparelho("white") == "white"
    assert colorway_do_aparelho("") == ""
    assert colorway_do_aparelho("nao-existe-no-mapa") == ""


def test_o_desenho_tem_dono_e_nao_uma_tabela_nova():
    """`colorway_do_aparelho` LÊ a folha do mapa; ele não guarda cor nenhuma.

    Se um dia alguém digitar aqui a lista dos modelos, este teste continua
    passando — mas o de cima, que lê o CSV, é quem cobra os 28. O que este
    cobra é que os modelos do mapa TODOS atravessem, e não só os do desenho.
    """
    from pacotes.a06_navegacao import colorway_do_aparelho

    for modelo in sorted(_modelos_do_mapa()):
        assert colorway_do_aparelho(modelo) == modelo, (
            f"o modelo {modelo!r} do mapa dela não atravessa — quem tiver um "
            f"vê o desenho sem cor")
