#!/usr/bin/env python3
"""UM PADRÃO DE FÁBRICA FORA DO VOCABULÁRIO DA TELA VIRA ESCOLHA DELA NO DISCO.

O DEFEITO QUE ESTA RÉGUA MEDE, e ele foi reproduzido em 02/09/2026 na base
`onda/abas-0209` (242c3e0c): o L3 nasceu alternador
(`core/keyboard_mappings.DEFAULT_BUTTON_BINDINGS`), a página que o produto
RENDERIZA foi congelada antes disso e não tem a `<option>` do rótulo novo, e o
"Guardar" da aba Navegação passou a gravar `{'l3': '__OPEN_OSK__'}` no perfil
ATIVO — uma escolha que ela não fez, em silêncio, bastando um clique para mudar
qualquer OUTRA linha.

A CADEIA TEM QUATRO ELOS, e o terceiro é o que a esconde:

    1. o padrão nasce em `DEFAULT_BUTTON_BINDINGS`;
    2. `core/acoes_de_botao.padrao()` deriva dele o padrão das 21 linhas;
    3. a pintura do `acao-l3` é RECUSADA EM SILÊNCIO — `hefesto_vivo.escrever`
       com alvo `valor` faz `el.value = texto`, e um `<select>` só aceita o
       texto exato de uma opção que ele oferece. A linha fica no desenho
       congelado;
    4. `a06_navegacao.guardar_definicoes` recolhe o `select.value` das 21
       linhas, compara com o padrão e grava a diferença.

POR QUE ELA MORA DO LADO DO `keyboard_mappings`: porque é lá que o padrão nasce,
e é lá que a decisão de trocá-lo é tomada. Quem troca um padrão passa por este
arquivo; quem publica uma página, não.

O QUE ELA **NÃO** É: ela não dirige navegador nenhum. A pergunta aqui é de
VOCABULÁRIO — o rótulo do padrão existe como `<option>` daquela linha? —, e ela
se responde lendo o HTML que o produto renderiza. A régua que dirige o Chrome e
mede o que o clique RECOLHE é
`tests/unit/test_a_tela_entrega_as_vinte_e_uma_linhas.py`; são perguntas
diferentes, e esta roda sem motor.

ELA MORDE NOS DOIS SENTIDOS, de propósito:

* padrão novo fora do vocabulário da tela publicada, sem declaração → vermelho
  no mesmo dia em que alguém o trocar;
* declaração que caducou — ela publicou a página e o rótulo passou a existir →
  vermelho também, e a mensagem manda apagar a linha. É o sino, e não a lápide.
"""
from __future__ import annotations

import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from hefesto_dualsense4unix.core.keyboard_mappings import (
    PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ,
)
from hefesto_dualsense4unix.interface import onde

PAGINA = "06-navegacao.html"

_SELECT = re.compile(r"<select\b(?P<attrs>[^>]*)>(?P<miolo>.*?)</select>", re.S)
_LINHA = re.compile(r'data-linha="(?P<v>[^"]+)"')
_OPCAO = re.compile(r"<option(?P<attrs>[^>]*)>(?P<texto>[^<]*)</option>")


def _listas(caminho: pathlib.Path) -> dict[str, tuple[list[str], str]]:
    """`{data-linha: ([rótulos oferecidos], rótulo que a tela abre mostrando)}`.

    O SEGUNDO VALOR É O QUE O NAVEGADOR DEVOLVERIA em `select.value`: a opção
    marcada com `selected`, ou a primeira quando não há nenhuma marcada. As
    opções desta tela não têm atributo `value` — pô-lo faria toda a marcação
    virar divergência de desenho —, então `select.value` é o TEXTO da opção.
    """
    fora: dict[str, tuple[list[str], str]] = {}
    html = caminho.read_text(encoding="utf-8")
    for m in _SELECT.finditer(html):
        alvo = _LINHA.search(m.group("attrs"))
        if not alvo:
            continue
        rotulos: list[str] = []
        marcada: str | None = None
        for o in _OPCAO.finditer(m.group("miolo")):
            texto = o.group("texto").strip()
            rotulos.append(texto)
            if marcada is None and "selected" in o.group("attrs"):
                marcada = texto
        fora[alvo.group("v")] = (
            rotulos, marcada if marcada is not None else (rotulos[0] if rotulos else ""))
    return fora


def _padrao_fora_da_lista(caminho: pathlib.Path) -> dict[str, tuple[str, str]]:
    """Botão -> (o token de fábrica, o token que a tela poria no lugar).

    Só entram os botões cuja linha existe na página: o que a tela não mostra,
    ela também não grava.
    """
    de_fabrica = acoes.padrao()
    listas = _listas(caminho)
    fora: dict[str, tuple[str, str]] = {}
    for botao, token in de_fabrica.items():
        lista = listas.get(botao)
        if lista is None:
            continue
        rotulos, aberta = lista
        rotulo = acoes.ACOES[token][1] if token in acoes.ACOES else None
        if rotulo is None or rotulo not in rotulos:
            fora[botao] = (token, str(acoes.token_do_rotulo(aberta)))
    return fora


def test_o_padrao_de_todas_as_linhas_tem_nome_na_lista_da_tela() -> None:
    """Todo token que o produto usa de fábrica é uma ação que a tela sabe dizer.

    Um padrão sem rótulo em `acoes_de_botao.ACOES` é pior que um fora do
    `<select>`: a linha não teria como mostrar a verdade em página nenhuma, nem
    na bancada.
    """
    sem_nome = {b: t for b, t in acoes.padrao().items() if t not in acoes.ACOES}
    assert not sem_nome, (
        "estes botões fazem de fábrica algo que a lista da tela não nomeia: "
        f"{sem_nome}. Acrescente o rótulo em `core/acoes_de_botao.ACOES` — sem "
        "ele a linha não pode mostrar a verdade em página nenhuma.")


def test_o_que_a_tela_publicada_nao_diz_esta_declarado_e_nada_mais() -> None:
    """A MEDIÇÃO E A DECLARAÇÃO TÊM DE SER A MESMA COISA — nos dois sentidos.

    A mais: alguém trocou um padrão e a página que o produto renderiza não sabe
    dizê-lo. O "Guardar" da Navegação vai gravar isso no perfil ATIVO dela sem
    ela pedir, e no tique seguinte a pintura volta a casar — o rastro some.

    A menos: a página foi publicada e o rótulo passou a existir. A declaração
    caducou e tem de sair, ou ela vira lápide.
    """
    medido = _padrao_fora_da_lista(onde.pagina(PAGINA, publicado=True))
    declarado = dict(PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ)
    a_mais = {b: v for b, v in medido.items() if declarado.get(b) != v}
    a_menos = {b: v for b, v in declarado.items() if medido.get(b) != v}
    assert not a_mais, (
        "a página que o produto RENDERIZA não sabe dizer o que estes botões "
        f"fazem de fábrica: {a_mais} (botão -> (de fábrica, o que a tela poria "
        "no lugar)).\nO 'Guardar' da aba Navegação grava a diferença no perfil "
        "ATIVO dela — e isto não é escolha dela, é o desenho congelado. "
        "Publique a aba (`scripts/check_o_desenho_aprovado.py --publicar 06`, "
        "que é ato DELA) ou declare a linha em "
        "`core/keyboard_mappings.PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ` com a "
        "razão e a medição.")
    assert not a_menos, (
        f"a declaração caducou: {a_menos} já não vale. A página publicada "
        "passou a oferecer o rótulo do padrão — apague estas linhas de "
        "`core/keyboard_mappings.PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ`. "
        "Declaração que sobrevive ao defeito é lápide.")


def test_a_bancada_ja_sabe_dizer_todos_os_padroes() -> None:
    """O que falta é a PUBLICAÇÃO, e a régua diz isso em vez de deixar supor.

    Se a bancada também não souber, o buraco não é de ordem de merge: é do
    gerador da aba, que ficou para trás do padrão. São duas curas diferentes, e
    confundi-las custa uma leva.
    """
    fora = _padrao_fora_da_lista(onde.pagina(PAGINA))
    assert not fora, (
        f"nem a BANCADA sabe dizer o padrão destes botões: {fora}. Não adianta "
        "publicar — rode o gerador da aba primeiro "
        "(`src/hefesto_dualsense4unix/interface/aba06.py`), porque a lista da "
        "tela sai de `core/acoes_de_botao.por_grupo()`.")


def test_o_que_a_tela_publicada_poria_no_lugar_muda_o_que_o_device_faz() -> None:
    """A divergência NÃO é cosmética — ela troca o comportamento do controle.

    Segue o fio do daemon sem daemon nenhum: `acoes_de_botao.resolver` monta o
    que vai ao device de teclado e `profiles.manager.resolve_key_bindings` o
    mescla sobre o de fábrica, que é exatamente o caminho de
    `apply_button_actions`.

    MEDIDO em 02/09/2026 para o L3: sem override o device recebe
    `['__TOGGLE_OSK__']`; com o que o "Guardar" gravaria ele recebe
    `['__OPEN_OSK__']` — o L3 para de alternar naquele perfil.
    """
    from hefesto_dualsense4unix.profiles.manager import resolve_key_bindings

    def no_device(escolhas: dict[str, str] | None) -> dict[str, list[str]]:
        _mouse, do_teclado, _sem = acoes.resolver(escolhas)
        return {
            b: list(t) for b, t in resolve_key_bindings(
                {k: list(v) for k, v in do_teclado.items()}).items()}

    de_fabrica = no_device(None)
    iguais = []
    for botao, (_padrao, da_tela) in PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ.items():
        depois = no_device({botao: da_tela})
        if depois.get(botao) == de_fabrica.get(botao):
            iguais.append(botao)
    assert not iguais, (
        f"estes botões estão declarados como divergência e o device não vê "
        f"diferença nenhuma: {iguais}. Ou a declaração está errada, ou o "
        "override não chega ao teclado virtual — e nos dois casos a tabela de "
        "`core/keyboard_mappings.PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ` está "
        "medindo a palavra em vez do ato.")


# "O homem é a medida de todas as coisas." — Protágoras
