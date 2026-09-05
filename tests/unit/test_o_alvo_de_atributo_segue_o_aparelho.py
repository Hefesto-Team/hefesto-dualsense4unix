#!/usr/bin/env python3
"""O alvo ``atributo``: o desenho do controle passa a seguir o APARELHO.

A LEI, e ela é dela — 03/09/2026:

    *"os svgs do dualsense, as bordas das fitas das áreas, as escolhas dos
    players com cada controle — tudo isso muda de acordo com o controle
    identificado no canto superior. É white no p1, mas a borda de tudo é cosmic
    red e os svgs não são os que o meu mapa cataloga. Isso tá errado."*

O SVG escolhe a cor por ATRIBUTO: ``monta.svg()`` grava
``<svg data-colorway="cosmic-red">`` e a folha embutida pinta as dez zonas com
``svg[data-colorway="…"] .z-casca{fill:var(--z-casca)}``. Havia **181**
``data-colorway`` nas dez páginas publicadas e nenhum alcançável — dos oito
alvos do ``escrever()``, nenhum escrevia atributo. A aba 08 desistiu com a razão
escrita no HTML publicado (``08-conexoes.html:1033``): *"a cura certa é um alvo
de atributo no piloto"*.

**POR QUE NUM WEBKIT DE VERDADE**: o ``escrever()`` é JavaScript, e a única
forma de saber o que ele faz é rodá-lo no motor que ela vai usar. Reescrevê-lo
em Python seria testar a reescrita — e a armadilha tem nome nesta casa:
*"medir contra a biblioteca errada produz alarme convincente e falso"*.

O QUE ELE MEDE, e cada número saiu deste motor:

1. **o atributo muda a COR DE VERDADE** — o ``fill`` computado da casca vai de
   ``rgb(174, 51, 90)`` (Cosmic Red) para ``rgb(237, 238, 240)`` (White);
2. **o vazio APAGA, e cai no cinza cru** — sem ``data-colorway`` nenhuma regra
   da folha casa e o desenho volta aos ``fill`` do arquivo:
   ``rgb(58, 63, 75)``, o mesmo de um ``<rect>`` que nunca teve zona. Não é SVG
   quebrado: é o controle SEM identidade, que é o que a regra dela pede quando
   não há informação;
3. **o contador não mente** — pintar o mesmo valor de novo devolve ``0``, e
   apagar o que já está apagado também;
4. **a guarda de nome segura três estragos** — ``data-hef-classe`` (o prefixo do
   piloto, onde mora o SELO da visita), ``style`` (que apagaria o
   ``--plastico`` que outro alvo acabou de pintar) e ``data-campo`` (o endereço
   por onde o alvo foi encontrado). Os três pintam ``0``;
5. **os dois lados leem a mesma coisa** — ``regua_do_mockup._campo`` lê o
   atributo do ARQUIVO e o ``LER_CAMPOS`` lê o mesmo atributo da TELA, byte a
   byte, incluindo o ``style`` que o WebKit devolveu sem normalizar.

E O FATO QUE QUEM FOR LIGAR UMA ABA PRECISA SABER — medido aqui, no caso
:func:`test_o_colorway_que_a_folha_nao_traz_da_o_mesmo_cinza`: **o alvo é
necessário e não é suficiente.** ``monta._so_o_colorway`` guarda na folha de
cada SVG só as regras do modelo pedido (3.082 bytes dos 45.452 dos 28), então
escrever um colorway que não está embutido dá o MESMO cinza do atributo
apagado. Ou o ``monta.svg()`` deixa de podar, ou a página publica a folha
inteira uma vez.

AS TRÊS MORDIDAS, e elas RODAM — não estão num comentário:

* :func:`test_a_mordida_do_pintor_sem_o_ramo_a_tela_fica_no_mockup` arranca o
  ramo ``if(alvo === 'atributo')`` do BOOTSTRAP e roda o piloto mutilado no
  mesmo WebKit: o ``data-colorway`` não anda, e a tela continua Cosmic Red sobre
  um aparelho White — a lei quebrada, na medida;
* :func:`test_a_mordida_da_regua_sem_o_ramo_ela_da_produto_sobre_pagina_virgem`
  arranca o ramo ``elif alvo == "atributo"`` da régua e a vê dar **PRODUTO** a
  uma página que NINGUÉM pintou — verde sobre nada, que é o defeito que a régua
  existe para não ter;
* :func:`test_a_mordida_do_travessao_sem_ele_a_regua_acusa_a_pintura_certa`
  arranca a linha do travessão de ``_declarado_neste_elemento`` e a vê chamar de
  ENDEREÇO MORTO exatamente o caso da mesa dela — pelo rádio o mapa responde que
  a cor do aparelho não se lê, e todo SVG daquele controle é pintado com vazio.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.interface import regua_do_mockup as regua

PILOTO = RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"
REGUA = RAIZ / "src/hefesto_dualsense4unix/interface/regua_do_mockup.py"

#: A PÁGINA DE ENSAIO, e ela é o SVG das dez abas em miniatura: uma folha com
#: DOIS colorways, uma casca que obedece a folha e um retângulo que só tem o
#: ``fill`` cru — o terceiro é a testemunha, e é ele que diz para o que o
#: desenho cai quando nenhuma regra casa.
#:
#: Os três ``mau-*`` são os nomes de atributo que a guarda tem de recusar. Eles
#: dividem a mesma pintura dos legítimos de propósito: se a guarda falhar, o
#: CONTADOR passa de 1, e o contador é o instrumento com que esta casa prova que
#: um endereço existe.
PAGINA = """<html><head><title>Hefesto — aba DE PROVA</title></head><body>
<div data-controle="p1">
  <svg id="desenho" data-campo="desenho" data-hef-alvo="atributo"
       data-hef-atributo="data-colorway" data-colorway="cosmic-red"
       width="20" height="20" xmlns="http://www.w3.org/2000/svg">
    <style>
      svg[data-colorway="cosmic-red"] .z-casca{fill:#ae335a}
      svg[data-colorway="white"] .z-casca{fill:#edeef0}
    </style>
    <rect id="casca" class="z-casca" width="20" height="20" fill="#3a3f4b"/>
    <rect id="crua" width="20" height="20" fill="#3a3f4b"/>
  </svg>
  <i id="mau-hef" data-campo="mau-hef" data-hef-alvo="atributo"
     data-hef-atributo="data-hef-classe"></i>
  <i id="mau-estilo" data-campo="mau-estilo" data-hef-alvo="atributo"
     data-hef-atributo="style" style="--plastico:#ae335a"></i>
  <i id="mau-endereco" data-campo="mau-endereco" data-hef-alvo="atributo"
     data-hef-atributo="data-campo"></i>
  <i id="bom-title" data-campo="bom-title" data-hef-alvo="atributo"
     data-hef-atributo="title" title="o que o desenho congelou"></i>
</div>
</body></html>"""

#: O ROTEIRO INTEIRO NUMA IDA SÓ ao motor. Um round-trip por asserção custaria
#: doze cargas de página para medir o que uma mede.
ROTEIRO = """
(function(){
  const fora = {};
  const svg = document.getElementById('desenho');
  const casca = document.getElementById('casca');
  const crua = document.getElementById('crua');
  const pinta = function(v){ return window.__hef.pintar({colunas: {p1: {
      desenho: v, 'mau-hef': 'x', 'mau-estilo': 'color:red',
      'mau-endereco': 'trocado'}}}); };
  fora.virgem = JSON.parse(LEITOR_AQUI);
  fora.fill_cosmic = getComputedStyle(casca).fill;
  fora.fill_crua = getComputedStyle(crua).fill;
  fora.n1 = pinta('white');
  fora.attr = svg.getAttribute('data-colorway');
  fora.fill_white = getComputedStyle(casca).fill;
  fora.tem_casca = (document.getElementById('casca') !== null);
  fora.mau_hef = document.getElementById('mau-hef').getAttribute('data-hef-classe');
  fora.mau_estilo = document.getElementById('mau-estilo').getAttribute('style');
  fora.mau_endereco = document.getElementById('mau-endereco').getAttribute('data-campo');
  fora.depois = JSON.parse(LEITOR_AQUI);
  fora.n2 = pinta('white');
  fora.n3 = pinta('');
  fora.tem_attr = svg.hasAttribute('data-colorway');
  fora.fill_apagado = getComputedStyle(casca).fill;
  fora.n4 = pinta('');
  fora.n5 = pinta('—');
  fora.n6 = pinta('galactic-purple');
  fora.fill_nao_embutido = getComputedStyle(casca).fill;
  // O `title` NUM TIQUE PRÓPRIO, para não mexer no `n1`: os números acima medem
  // que só o `desenho` pinta entre os quatro endereços daquele pacote.
  fora.n7 = window.__hef.pintar({colunas: {p1: {'bom-title': 'Mortal Kombat'}}});
  fora.bom_title = document.getElementById('bom-title').getAttribute('title');
  return JSON.stringify(fora);
})()
"""


def _constante(nome: str) -> str:
    """O BOOTSTRAP e o LER_CAMPOS lidos do FONTE do piloto, e não importados.

    Importar ``hefesto_vivo`` arrastaria a janela GTK inteira para dentro do
    teste. É como os outros testes do pintor fazem, e pela mesma razão.
    """
    achou = re.search(rf'^{nome} = r"""(.*?)"""$',
                      PILOTO.read_text(encoding="utf-8"), re.S | re.M)
    assert achou, f"o piloto perdeu o {nome} — não há o que testar"
    return achou.group(1)


#: O RAMO DO ALVO NOVO, DENTRO DO BOOTSTRAP. É o que a mordida arranca.
RAMO_DO_PINTOR = re.compile(r"\n    if\(alvo === 'atributo'\)\{.*?\n    \}\n", re.S)

#: O RAMO DO ALVO NOVO, DENTRO DA RÉGUA — de ``elif alvo == "atributo":`` até o
#: ``elif`` seguinte, no mesmo nível.
RAMO_DA_REGUA = re.compile(
    r"\n        elif alvo == \"atributo\":\n.*?(?=\n        elif )", re.S)


def _rodar_no_webkit(bootstrap: str, roteiro: str) -> dict:
    """Abre um WebKit offscreen sobre :data:`PAGINA`, instala o bootstrap e mede.

    A janela é ``Gtk.OffscreenWindow`` — sob Xvfb não há gerenciador de janelas
    e uma ``Gtk.Window`` fica 1x1 para sempre. E offscreen também porque a dona
    do projeto tem UMA tela: janela de teste não nasce na frente dela.
    """
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def guardou(v: object, res: object) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:  # pragma: no cover — só quando o roteiro quebra
            saiu.append(f"ERRO {e}")
        Gtk.main_quit()

    def instalou(v: object, res: object) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:  # pragma: no cover — só quando o bootstrap quebra
            saiu.append(f"ERRO no bootstrap: {e}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(roteiro, -1, None, None, None, guardou)

    def carregou(v: object, evento: object) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(bootstrap, -1, None, None, None, instalou)

    view.connect("load-changed", carregou)
    view.load_html(PAGINA, "file:///")
    # O `timeout_add` PENDENTE DISPARA NO LAÇO DO PRÓXIMO TESTE de GUI do
    # mesmo processo — 05/09/2026, e a cura já existia em cinco arquivos
    # irmãos (*"Já matou onze medições"*). Aqui ela faltava: medido no
    # lote-00 da suíte, DUAS voltas em três davam *"o WebKit não respondeu
    # em 30 s"* com o `saiu` VAZIO — o laço não estourou, ele foi MORTO por
    # um `main_quit` que outro teste deixou armado. Reprodutível só na
    # ordem aleatória, que é o que o torna invisível quando se roda o
    # arquivo sozinho.
    guarda = GLib.timeout_add(20000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu, "o WebKit não respondeu em 20 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return dict(json.loads(saiu[0]))


@pytest.fixture(scope="module")
def medido() -> dict:
    roteiro = ROTEIRO.replace("LEITOR_AQUI", f"({_constante('LER_CAMPOS').strip()})")
    return _rodar_no_webkit(_constante("BOOTSTRAP"), roteiro)


def _tela(linhas: list) -> dict[str, str]:
    """``{endereço: valor}``, da leitura de tela do próprio piloto."""
    return {f"{x[1]}·{x[0]}": str(x[3]) for x in linhas}


def _arquivo() -> dict[str, str]:
    """``{endereço: valor}``, do que a régua lê no ARQUIVO publicado."""
    return {c.endereco: c.valor for c in regua._campos_cravados(PAGINA)}


# ---------------------------------------------------------------------------
# 1. o alvo escreve, e a cor do desenho MUDA
# ---------------------------------------------------------------------------
def test_o_atributo_e_escrito_e_o_desenho_troca_de_cor(medido: dict) -> None:
    assert medido["attr"] == "white", (
        "o alvo não escreveu o `data-colorway` — os 181 SVGs continuam "
        "inalcançáveis")
    assert medido["fill_cosmic"] != medido["fill_white"], (
        f"o atributo mudou e a COR não: {medido['fill_cosmic']} → "
        f"{medido['fill_white']}. Um atributo que não repinta o desenho não "
        f"cumpre a lei — ela olha a tela, não o DOM")
    assert medido["fill_white"] == "rgb(237, 238, 240)", (
        f"o White do mapa dela é #edeef0; a casca ficou {medido['fill_white']}")
    assert medido["tem_casca"] is True, (
        "o desenho foi engolido — escrever num `<svg>` pelo ramo padrão apaga "
        "os filhos dele")


def test_a_contagem_de_pinturas_nao_mente(medido: dict) -> None:
    """Um contador que mente é pior que um campo parado.

    Ele é O instrumento com que esta casa prova que um endereço existe: uma aba
    que devolve 0 com pacote não vazio é endereço que não existe na página.
    """
    assert medido["n1"] == 1, (
        f"a primeira pintura contou {medido['n1']} em vez de 1 — só o "
        f"`desenho` podia ter sido escrito; os três `mau-*` são recusados")
    assert medido["n2"] == 0, "pintar o mesmo valor de novo tem de contar 0"
    assert medido["n3"] == 1, "apagar um atributo que existia é UMA pintura"
    assert medido["n4"] == 0, "apagar o que já está apagado tem de contar 0"
    assert medido["n5"] == 0, (
        "o travessão apaga como o vazio — sobre um atributo já ausente ele "
        "não pode contar pintura")


def test_o_title_e_canal_de_pintura_e_nao_so_uma_lista(medido: dict) -> None:
    """O `title` do rodapé pinta DE VERDADE, medido neste WebKit.

    A guarda `atributo_escrevivel` recusava `title` até 03/09/2026, e o
    `fim.html` — um só para as dez páginas — pedia exatamente isso nos botões
    Salvar e Exportar, para a dica dizer o NOME do perfil ativo em vez de
    congelar um exemplo. Vinte páginas com um endereço que nunca pintava, e a
    recusa era **calada** (`return 0`).

    Abrir a lista não bastaria como prova: uma lista é uma palavra, e o que
    conta é o ato. Aqui o pacote manda `Mortal Kombat` no endereço e o atributo
    do elemento é lido de volta do motor que ela usa.

    A MORDIDA: tire `'title'` de `ATRIBUTO_A_MAIS` no piloto — esta linha
    reprova com `n7 == 0`, e o portão das páginas nomeia as vinte.
    """
    assert medido["n7"] == 1, (
        f"o pacote escreveu no `title` e o piloto contou {medido['n7']} "
        "pintura(s) — a guarda voltou a recusar o nome em silêncio")
    assert medido["bom_title"] == "Mortal Kombat", (
        f"a dica ficou em {medido['bom_title']!r} — o produto não trocou o "
        "texto que o desenho congelou")


# ---------------------------------------------------------------------------
# 2. o vazio apaga, e cai no cinza cru — MEDIDO, não presumido
# ---------------------------------------------------------------------------
def test_o_vazio_apaga_o_atributo_e_o_desenho_cai_no_fill_cru(medido: dict) -> None:
    """A resposta medida para *"apagar o `data-colorway` cai no quê?"*.

    Cai nos ``fill`` do próprio arquivo — o mesmo tom de um ``<rect>`` que nunca
    teve zona. É o controle SEM identidade, e é o que a regra dela pede: campo
    sem informação não mostra nada. Deixar o atributo faria o contrário —
    manteria na tela o colorway do MOCKUP sobre um aparelho que é outro.
    """
    assert medido["tem_attr"] is False, (
        "o vazio tinha de REMOVER o atributo, e ele continua lá")
    assert medido["fill_apagado"] == medido["fill_crua"] == "rgb(58, 63, 75)", (
        f"sem colorway o desenho tinha de cair no `fill` cru "
        f"({medido['fill_crua']}), e ficou em {medido['fill_apagado']}")


def test_o_colorway_que_a_folha_nao_traz_da_o_mesmo_cinza(medido: dict) -> None:
    """O ALVO É NECESSÁRIO E NÃO É SUFICIENTE, e este é o número que prova.

    ``monta._so_o_colorway`` guarda na folha de cada SVG só as regras do modelo
    pedido — 3.082 bytes dos 45.452 dos 28 modelos, para que uma aba com quatro
    controles não carregue quatro cópias dos 28. Consequência: escrever aqui um
    colorway que não está embutido não pinta nada, e dá o MESMO cinza do
    atributo apagado.

    Quem for ligar uma aba tem de resolver isto junto: ou o ``monta.svg()``
    deixa de podar, ou a página publica a folha inteira uma vez.
    """
    assert medido["n6"] == 1, "o atributo foi escrito — a pintura conta"
    assert medido["fill_nao_embutido"] == medido["fill_crua"], (
        "a folha desta página só traz `cosmic-red` e `white`; um "
        "`galactic-purple` escrito nela tinha de cair no cinza cru")


# ---------------------------------------------------------------------------
# 3. a guarda de nome
# ---------------------------------------------------------------------------
def test_a_guarda_recusa_o_prefixo_do_piloto_o_estilo_e_o_endereco(
        medido: dict) -> None:
    """Três estragos que a guarda segura, e cada um tem uma razão medida.

    ``data-hef-*`` é onde mora o SELO da visita (``data-hef-visto``), que é o
    fato com que a régua decide um INDECIDÍVEL — um alvo capaz de escrevê-lo é
    um alvo capaz de FORJAR a medição desta casa. ``style`` apagaria o
    ``--plastico`` e a ``width`` que os alvos vizinhos pintam no mesmo elemento.
    ``data-campo`` é a placa da porta por onde o alvo foi encontrado.
    """
    assert medido["mau_hef"] is None, (
        "um `data-hef-*` foi escrito — o prefixo do piloto está aberto, e com "
        "ele o selo da visita")
    assert medido["mau_estilo"] == "--plastico:#ae335a", (
        f"o `style` foi reescrito ({medido['mau_estilo']!r}) — a cor do "
        f"plástico que outro alvo pinta neste elemento seria apagada")
    assert medido["mau_endereco"] == "mau-endereco", (
        "o `data-campo` foi reescrito — o alvo mudou o próprio endereço")


# ---------------------------------------------------------------------------
# 4. os dois lados leem a MESMA coisa
# ---------------------------------------------------------------------------
def test_a_regua_e_o_leitor_de_tela_leem_o_mesmo_atributo(medido: dict) -> None:
    """O parser de Python e o ``LER_CAMPOS`` do piloto, endereço a endereço.

    É a mesma guarda que o ``--prova-de-mockup`` roda em cada aba sobre o DOM
    virgem. Se as duas leituras divergirem, toda classificação daquela aba está
    comparando o arquivo com outra coisa.
    """
    assert _tela(medido["virgem"]) == _arquivo(), (
        "a régua e o leitor de tela discordam sobre a página virgem")


def test_depois_da_pintura_a_regua_da_produto(medido: dict) -> None:
    cravados = regua._campos_cravados(PAGINA)
    vivos = [str(x[3]) for x in medido["depois"]]
    selos = [bool(x[4]) for x in medido["depois"]]
    vereditos = regua._classificar(
        cravados, vivos, {("p1", "desenho"): "white"}, selos)
    (desenho,) = [v for v in vereditos if v.campo.chave == "desenho"]
    assert desenho.classe == regua.PRODUTO, (
        f"o produto pintou o desenho e a régua disse {desenho.classe}: "
        f"{desenho.nota}")


def test_o_vazio_declarado_nao_vira_travessao_na_comparacao() -> None:
    """O caminho da MESA DELA: pelo rádio a cor do aparelho não se lê.

    ``mesa_viva`` emite ``""`` para aquele controle, o molde o traduz em
    travessão, e o ``escrever()`` APAGA o atributo. Se a régua comparasse o
    travessão com o vazio da tela, acusaria ENDEREÇO MORTO sobre a pintura
    certa — em metade da mesa dela.
    """
    campo = regua._Campo(chave="desenho", dono="p1", alvo="atributo", valor="")
    assert regua._declarado_neste_elemento(campo, regua.TRAVESSAO) == ""


# ---------------------------------------------------------------------------
# 5. AS TRÊS MORDIDAS
# ---------------------------------------------------------------------------
def test_a_mordida_do_pintor_sem_o_ramo_a_tela_fica_no_mockup() -> None:
    """Arranca ``if(alvo === 'atributo')`` do BOOTSTRAP e roda o piloto mutilado.

    Sem o ramo o ``escrever()`` cai no padrão e escreve o valor como TEXTO — e o
    estrago MEDIDO é maior do que "a cor não muda": ``el.textContent = 'white'``
    num ``<svg>`` **apaga os filhos**. A folha de estilo e as duas formas somem
    do documento, e o que sobra é a palavra ``white`` escrita por cima do lugar
    onde havia um controle. O ``data-colorway`` continua ``cosmic-red``.
    """
    inteiro = _constante("BOOTSTRAP")
    mutilado, quantos = RAMO_DO_PINTOR.subn("\n", inteiro)
    assert quantos == 1, (
        "a mordida não achou o ramo do alvo `atributo` no BOOTSTRAP — o teste "
        "não morde mais nada")

    roteiro = ROTEIRO.replace("LEITOR_AQUI", f"({_constante('LER_CAMPOS').strip()})")
    sem_cura = _rodar_no_webkit(mutilado, roteiro)
    assert sem_cura["attr"] == "cosmic-red", (
        "com o ramo arrancado o atributo ainda andou — a cura não é este ramo")
    assert sem_cura["tem_casca"] is False, (
        "com o ramo arrancado o desenho tinha de ser engolido pelo texto, e "
        "ele sobreviveu — o teste está medindo outra coisa")


def _regua_sem(ramo: re.Pattern[str], quem: str) -> object:
    """A régua com um ramo arrancado, carregada num espaço próprio.

    O módulo só importa da biblioteca padrão, então ``exec`` sobre o fonte
    mutilado basta — e não contamina a régua de verdade, que os outros casos
    deste arquivo continuam usando.
    """
    import types

    fonte, quantos = ramo.subn("\n", REGUA.read_text(encoding="utf-8"))
    assert quantos == 1, f"a mordida não achou {quem} — ela não morde mais nada"
    nome = f"regua_mordida_{abs(hash(quem))}"
    modulo = types.ModuleType(nome)
    # REGISTRAR EM `sys.modules` É OBRIGATÓRIO, e não é cerimônia: o
    # `dataclasses` resolve as anotações procurando o módulo da classe em
    # `sys.modules`, e sem ele o `@dataclasses.dataclass` do `_Campo` levanta
    # `AttributeError: 'NoneType' object has no attribute '__dict__'`.
    sys.modules[nome] = modulo
    exec(compile(fonte, str(REGUA), "exec"), modulo.__dict__)
    return modulo


def test_a_mordida_da_regua_sem_o_ramo_ela_da_produto_sobre_pagina_virgem() -> None:
    """Arranca ``elif alvo == "atributo"`` de ``_campo`` e vê o verde sobre nada.

    Sem o ramo a régua lê o TEXTO do ``<svg>`` (a folha de estilo, espremida) e
    o compara com o ``data-colorway`` que o leitor de tela devolve. Como os dois
    diferem, ela conclui *"a tela mudou"* — **PRODUTO** — sobre uma página que
    ninguém pintou. Uma régua que dá por provado o que não aconteceu é pior que
    régua nenhuma.
    """
    mordida = _regua_sem(RAMO_DA_REGUA, 'o ramo `elif alvo == "atributo"` da régua')

    # A TELA, do jeito que o piloto a lê — e aqui ela é a página VIRGEM: o valor
    # de cada endereço é o que o próprio arquivo crava, sem uma pintura sequer.
    vivos = [c.valor for c in regua._campos_cravados(PAGINA)]
    cravados = mordida._campos_cravados(PAGINA)
    vereditos = mordida._classificar(cravados, vivos)
    (desenho,) = [v for v in vereditos if v.campo.chave == "desenho"]
    assert desenho.classe == mordida.PRODUTO, (
        "a mordida não produziu o defeito que ela existe para mostrar")

    # E com a cura de volta, a mesma página virgem é o que ela é.
    curados = regua._classificar(regua._campos_cravados(PAGINA), vivos)
    (certo,) = [v for v in curados if v.campo.chave == "desenho"]
    assert certo.classe != regua.PRODUTO, (
        "com o ramo no lugar a régua ainda dá PRODUTO a uma página virgem")


def test_a_mordida_do_travessao_sem_ele_a_regua_acusa_a_pintura_certa() -> None:
    """Arranca a linha do travessão e vê a régua acusar a mesa dela.

    ``_declarado_neste_elemento`` traduz o que o pacote EMITE para o que a tela
    MOSTRARIA. Sem a linha, o travessão de um controle sem cor lida chega cru à
    comparação e nunca casa com o atributo ausente: ENDEREÇO MORTO sobre a
    pintura certa, em metade da mesa dela.
    """
    linha = re.compile(
        r'\n    if campo\.alvo == "atributo":\n.*?'
        r'\n        return "" if declarado == TRAVESSAO else declarado\n', re.S)
    mordida = _regua_sem(linha, "a linha do travessão do alvo `atributo`")
    campo = mordida._Campo(chave="desenho", dono="p1", alvo="atributo", valor="")
    assert mordida._declarado_neste_elemento(campo, mordida.TRAVESSAO) != "", (
        "a mordida não produziu o defeito — o travessão continua virando vazio")


# ---------------------------------------------------------------------------
# 6. o vocabulário, nas páginas de verdade
# ---------------------------------------------------------------------------
def test_todo_data_hef_atributo_publicado_e_escrevivel() -> None:
    """Nenhuma página pede um nome que a guarda vai recusar.

    A guarda devolve ``0`` calado, e um endereço que nunca pinta é exatamente o
    defeito que esta casa mais paga. O barulho tem de vir daqui, do portão, e
    não da tela dela.

    ELA JÁ COBROU — 03/09/2026, e foi este o barulho. O ``fim.html`` (um só para
    as dez páginas) passou a pedir ``data-hef-atributo="title"`` nos botões
    Salvar e Exportar, para a dica dizer o NOME do perfil ativo em vez de
    congelar um exemplo (``7db1e0e6``). O commit dava por certo que o alvo
    "sabe escrever num ``title``" — e ``atributo_escrevivel`` o recusava CALADA,
    nas vinte páginas. **A cura foi abrir o canal**, com o nome na lista curta e
    a razão escrita no piloto: ``title`` não é ``data-hef`` (não forja o selo),
    não é vocabulário de endereço e não desfaz o que outro alvo pintou.

    A LISTA A MAIS É LIDA DO PILOTO, e não digitada aqui: duas cópias da mesma
    regra divergem, e a que diverge é sempre a da régua — é a forma de
    instrumento falso que esta casa mais achou.
    """
    fonte = PILOTO.read_text(encoding="utf-8")
    crua = r"/^(data|aria)-[a-z0-9]+(-[a-z0-9]+)*$/.test(n)"
    assert crua in fonte, (
        "a forma da guarda `atributo_escrevivel` mudou no piloto e esta régua "
        "ficou medindo a regra de ontem — releia `hefesto_vivo` antes de mexer "
        "no que está escrito aqui")
    a_mais = re.search(r"const ATRIBUTO_A_MAIS = \[([^\]]*)\];", fonte)
    assert a_mais, "não achei `ATRIBUTO_A_MAIS` no piloto"
    permitidos_a_mais = {n.strip().strip("'\"")
                         for n in a_mais.group(1).split(",") if n.strip()}
    permitido = re.compile(r"^(data|aria)-[a-z0-9]+(-[a-z0-9]+)*$")
    proibidos = {"data-campo", "data-papel", "data-controle", "data-uniq",
                 "data-gesto"}
    maus: list[str] = []
    for pasta in (RAIZ / "src/hefesto_dualsense4unix/interface/paginas",
                  RAIZ / "mockup"):
        for caminho in sorted(pasta.glob("[0-9][0-9]-*.html")):
            texto = caminho.read_text(encoding="utf-8", errors="replace")
            for nome in re.findall(r'data-hef-atributo="([^"]*)"', texto):
                n = nome.strip().lower()
                if n in permitidos_a_mais:
                    continue
                if (not permitido.match(n) or n.startswith("data-hef")
                        or n in proibidos):
                    maus.append(f"{caminho.name}: {nome!r}")
    assert not maus, (
        "estas páginas pedem um atributo que o piloto recusa em silêncio:\n  "
        + "\n  ".join(maus))
