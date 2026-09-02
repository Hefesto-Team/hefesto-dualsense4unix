#!/usr/bin/env python3
"""O pintor de verdade, num WebKit de verdade, pintando os dois alvos novos.

POR QUE NÃO UM DUBLÊ DE DOM: o ``escrever()`` do BOOTSTRAP é JavaScript, e a
única forma de saber o que ele faz é executá-lo no MOTOR QUE ELA VAI USAR.
Reescrevê-lo em Python para testar seria testar a reescrita. Esta casa já pagou
por medir contra a biblioteca errada, e a armadilha tem nome:
*"medir contra a biblioteca errada produz alarme convincente e falso"*.

A JANELA É ``Gtk.OffscreenWindow`` — sob Xvfb não há gerenciador de janelas e
uma ``Gtk.Window`` fica 1x1 para sempre. E ela é offscreen também porque a dona
do projeto tem UMA tela: janela de teste não nasce na frente dela.

O QUE ELE COBRA, e são cinco coisas que nenhum teste puro alcança:

1. **as irmãs apagam.** Os quatro degraus dividem UM ``data-campo``; pintar
   ``'balanceado'`` tem de apagar o ``'max'`` que estava aceso. Um segundo
   clique não pode deixar dois degraus acesos.
2. **o alvo é IDEMPOTENTE.** Pintar o mesmo valor de novo devolve ``0``. O
   ``cls()`` dos cinco pilotos velhos devolvia ``1`` SEMPRE, e um alvo assim
   infla a contagem de pinturas de toda aba que o use — que é O instrumento com
   que esta casa prova que um endereço existe.
3. **a cor é escrita no ``color``**, não no texto, e apaga com o vazio.
4. **o leitor da régua casa com o parser de Python**, endereço a endereço e
   valor a valor. É a mesma guarda que o ``--prova-de-mockup`` roda em cada aba
   sobre o DOM virgem — aqui ela roda sobre um caso que nenhuma página publicada
   ainda tem.
5. **a normalização de cor é MEDIDA, não transcrita.** ``_cor_css`` é comparada
   com o que o CSSOM deste motor devolve, forma a forma, na mesma carga de
   página. O teste que ela tinha guardava uma tabela DIGITADA à mão — e a
   transcrição já estava errada em duas famílias inteiras (``hsl()``, que o
   WebKit reescreve como ``rgb()``, e o alfa de oito dígitos, que ele serializa
   CURTO: ``#0000ff80`` dá ``0.5``, e a tabela dizia ``0.502``). *A régua
   guardava a PALAVRA de uma sonda que rodou uma vez; agora ela pergunta ao
   motor a cada execução.*

A MORDIDA: tire o ``el.classList.toggle`` do ramo ``classe`` do BOOTSTRAP e
``test_as_irmas_do_grupo_apagam`` reprova; troque ``el.style.color`` por
``el.textContent`` no ramo ``cor`` e ``test_a_cor_vai_para_o_color`` reprova
dizendo que a régua e o pintor discordam; troque o ``_meio_para_cima`` de
``regua_do_mockup`` pelo ``round`` do Python e
``test_a_cor_e_medida_no_webkit_e_nao_transcrita`` reprova em
``rgba(10%, 20%, 30%, 50%)`` — 30% de 255 é 76,5, e o Python arredonda para o
PAR.
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

#: A PÁGINA DE ENSAIO. Ela reproduz, em miniatura, as cinco formas que os dois
#: alvos novos destravam — os quatro degraus da Vibração, o rótulo do teto, o
#: botão de jogador, a coluna da Perfis e o clique do analógico.
PAGINA = """<html><body>
<div data-controle="p1">
  <div class="seg">
    <button data-campo="degrau" data-hef-alvo="classe"
            data-hef-quando="economia">Economia</button>
    <button data-campo="degrau" data-hef-alvo="classe"
            data-hef-quando="balanceado">Balanceado</button>
    <button class="on" data-campo="degrau" data-hef-alvo="classe"
            data-hef-quando="max">M&aacute;ximo</button>
    <button data-campo="degrau" data-hef-alvo="classe"
            data-hef-quando="auto">Auto</button>
  </div>
  <span class="teto" data-campo="mult-teto" data-hef-alvo="classe">M&aacute;x</span>
  <span class="rotl" data-campo="l3" data-hef-alvo="cor"
        style="color:#6272a4">L3</span>
  <span class="rotl" data-campo="r3" data-hef-alvo="cor">R3</span>
</div>
<table><tr><td class="gr on" data-campo="ajuste"
             data-hef-alvo="classe">&#10003;</td></tr></table>
<span id="sonda-de-cor"></span>
</body></html>"""

#: AS FORMAS DE COR QUE A SONDA PERGUNTA AO MOTOR. Elas não são a resposta — a
#: resposta vem do CSSOM, nesta mesma carga de página. A lista cobre as seis
#: famílias que ``regua_do_mockup._cor_css`` declara conhecer e as duas que ela
#: declara NÃO conhecer, para que o buraco também fique medido.
FORMAS_DE_COR = [
    # hexadecimal, nas quatro larguras
    "#6272a4", "#FF5555", "#7EB8D4", "#fff", "#6272A4", " #6272a4 ",
    "#ff5555aa", "#fffa", "#abc4",
    # o alfa, que o CSSOM serializa CURTO — e some quando é cheio
    "#0000ff80", "#0000ff01", "#0000ff00", "#0000ffff",
    "rgba(0,0,0,.5)", "rgba(0,0,0,0.502)", "rgba(0,0,0,0.6667)",
    "rgba(0,0,0,1)", "rgba(0,0,0,-1)", "rgba(1,2,3,4)",
    "rgba(255,255,255,0.0039)",
    # rgb(), com vírgula, com espaço, com barra, em porcentagem
    "rgb(186, 218, 85)", "rgb(1,2,3)", "rgb(1 2 3)", "RGB(1,2,3)",
    "rgb(37.355% 50.439% 0%)", "rgb(0 0 0 / 50%)", "rgb(1,2,3,0.5)",
    "rgb(300, -5, 10)", "rgb(1.5, 2.4, 3.6)", "rgba(10%, 20%, 30%, 50%)",
    # hsl(), que a régua dizia devolver intacto
    "hsl(210, 50%, 40%)", "hsl(0 100% 50%)", "hsla(120, 60%, 30%, 0.4)",
    "hsl(210deg, 50%, 40%)", "hsl(-30, 50%, 40%)", "hsl(210, 150%, 40%)",
    "hsl(210, -50%, 40%)", "hsl(210, 50%, 150%)", "hsl(0.5turn, 50%, 40%)",
    "hsl(3.665rad, 50%, 40%)", "hsl(200grad, 50%, 40%)", "hsl(570, 50%, 40%)",
    # o que volta como foi escrito
    "red", "transparent", "currentColor", "WHITE", "AliceBlue",
    "var(--plastico)", "color-mix(in srgb, red, blue)", "",
    # e o CSS INVÁLIDO, que o CSSOM recusa devolvendo ''
    "Cosmic Red", "#12345", "#GGG", "rgb(1,2)", "rgb()",
]


def _constante(nome: str) -> str:
    """O BOOTSTRAP e o LER_CAMPOS lidos do FONTE do piloto, e não importados.

    Importar ``hefesto_vivo`` arrastaria a janela GTK inteira para dentro do
    teste. O ``test_a_regua_le_os_mesmos_enderecos_do_bootstrap`` já lê o piloto
    assim, e pela mesma razão.
    """
    fonte = PILOTO.read_text(encoding="utf-8")
    achou = re.search(rf'^{nome} = r"""(.*?)"""$', fonte, re.S | re.M)
    assert achou, f"o piloto perdeu o {nome} — não há o que testar"
    return achou.group(1)


#: O ROTEIRO INTEIRO NUMA IDA SÓ ao motor: cada passo devolve o que precisa ser
#: julgado do lado Python. Um round-trip por asserção custaria dez cargas de
#: página para medir o que uma mede.
ROTEIRO = """
(function(){
  const fora = {};
  fora.virgem = JSON.parse(LEITOR_AQUI);
  fora.n_balanceado = window.__hef.pintar({colunas: {p1: {
      degrau: 'balanceado', 'mult-teto': false, l3: 'var(--plastico)'}},
      mesa: {ajuste: false}});
  fora.depois = JSON.parse(LEITOR_AQUI);
  fora.classes_depois = Array.prototype.map.call(
      document.querySelectorAll('[data-campo="degrau"]'),
      function(el){ return el.className; });
  fora.cor_depois = document.querySelector('[data-campo="l3"]').style.color;
  fora.texto_l3 = document.querySelector('[data-campo="l3"]').textContent;
  fora.n_denovo = window.__hef.pintar({colunas: {p1: {
      degrau: 'balanceado', 'mult-teto': false, l3: 'var(--plastico)'}},
      mesa: {ajuste: false}});
  fora.n_max = window.__hef.pintar({colunas: {p1: {degrau: 'max',
      'mult-teto': true, l3: ''}}, mesa: {ajuste: true}});
  fora.fim = JSON.parse(LEITOR_AQUI);
  fora.classes_fim = Array.prototype.map.call(
      document.querySelectorAll('[data-campo="degrau"]'),
      function(el){ return el.className; });
  fora.cor_fim = document.querySelector('[data-campo="l3"]').style.color;
  // A SONDA DE COR, no mesmo motor e na mesma carga: escreve cada forma no
  // `style.color` de um elemento de rascunho e devolve o que o CSSOM guardou.
  const rascunho = document.getElementById('sonda-de-cor');
  fora.cores = [];
  for(const forma of CORES_AQUI){
    rascunho.style.color = '';
    rascunho.style.color = forma;
    fora.cores.push([forma, rascunho.style.color]);
  }
  // O PEDIDO DE PINTURA DO PILOTO, lido do fonte dele e rodado aqui: a carga é
  // a MESMA que acabou de ser pintada, logo o pintor escreve ZERO valores.
  fora.zero = PEDIDO_AQUI;
  // E a forma ANTIGA, guardada como prova do defeito: `0 || -1` é `-1`.
  fora.zero_com_ou = (window.__hef && window.__hef.pintar({colunas: {p1: {
      degrau: 'max', 'mult-teto': true, l3: ''}}, mesa: {ajuste: true}})) || -1;
  return JSON.stringify(fora);
})()
"""

#: A CARGA QUE NÃO MUDA NADA — é a mesma que o roteiro acabou de pintar em
#: ``n_max``, então o pintor tem de devolver zero.
CARGA_QUE_NAO_MUDA = ('{colunas: {p1: {degrau: "max", "mult-teto": true, '
                      'l3: ""}}, mesa: {ajuste: true}}')


@pytest.fixture(scope="module")
def medido() -> dict:
    """Abre um WebKit offscreen, instala o BOOTSTRAP e roda o roteiro."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    leitor = _constante("LER_CAMPOS").strip()
    pedido = _constante("PEDIR_A_PINTURA").strip().replace(
        "CARGA", CARGA_QUE_NAO_MUDA)
    roteiro = (ROTEIRO.replace("LEITOR_AQUI", f"({leitor})")
               .replace("CORES_AQUI", json.dumps(FORMAS_DE_COR))
               .replace("PEDIDO_AQUI", f"({pedido})"))
    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def guardou(v, res):
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:
            saiu.append(f"ERRO {e}")
        Gtk.main_quit()

    def instalou(v, res):
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(f"ERRO no bootstrap: {e}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(roteiro, -1, None, None, None, guardou)

    def carregou(v, evento):
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(_constante("BOOTSTRAP"), -1, None, None,
                                  None, instalou)

    view.connect("load-changed", carregou)
    view.load_html(PAGINA, "file:///")
    GLib.timeout_add(20000, Gtk.main_quit)
    Gtk.main()
    assert saiu, "o WebKit não respondeu em 20 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return json.loads(saiu[0])


def _endereco(linha: list) -> str:
    return f"{linha[1]}·{linha[0]}" if linha[1] else str(linha[0])


def _campos(linhas: list) -> dict[str, list[str]]:
    """``{endereço: [valores]}``, da leitura de tela do próprio piloto.

    É uma LISTA por endereço, e não um valor: os quatro degraus dividem um
    ``data-campo`` só, e um dicionário simples guardaria o último — que é
    justamente o que nunca acende.
    """
    fora: dict[str, list[str]] = {}
    for x in linhas:
        fora.setdefault(_endereco(x), []).append(str(x[3]))
    return fora


def _um(linhas: list, endereco: str) -> str:
    (valor,) = _campos(linhas)[endereco]
    return valor


def _aceso(linhas: list, endereco: str) -> list[str]:
    """Quais membros do grupo estão acesos, pela leitura do próprio piloto."""
    return [v for v in _campos(linhas)[endereco] if v]


# -- o leitor de tela e o parser de arquivo têm de dizer o MESMO ----------
def test_o_leitor_de_tela_casa_com_o_parser_do_arquivo(medido):
    """A guarda do DOM virgem, aplicada a um caso que nenhuma página tem ainda.

    Se os dois discordarem, a régua está lendo uma coisa e comparando outra — e
    diria PRODUTO sobre um campo que ninguém tocou.
    """
    cravados = regua._campos_cravados(PAGINA)
    virgem = medido["virgem"]
    assert len(virgem) == len(cravados)
    for c, linha in zip(cravados, virgem, strict=True):
        assert (str(linha[0]), str(linha[1])) == (c.chave, c.dono)
        assert str(linha[3]) == c.valor, (
            f"{c.endereco}: o arquivo diz {c.valor!r} e a tela virgem mostra "
            f"{linha[3]!r} — o parser e o leitor discordam no alvo {c.alvo}")


# -- (a) ligar uma classe desliga as irmãs -------------------------------
def test_as_irmas_do_grupo_apagam(medido):
    """Pintar ``balanceado`` apaga o ``max`` que estava aceso — e só um fica.

    O DEFEITO QUE ISTO IMPEDE está escrito no enunciado desta frente: *"senão o
    segundo clique deixa dois degraus acesos"*.
    """
    assert _aceso(medido["depois"], "p1·degrau") == ["balanceado"], (
        f"a tela devolveu {_campos(medido['depois'])['p1·degrau']} — o `max` "
        f"cravado no arquivo tinha de ter apagado")
    acesos = [c for c in medido["classes_depois"] if "on" in c.split()]
    assert len(acesos) == 1, (
        f"os quatro degraus acabaram com {len(acesos)} acesos: "
        f"{medido['classes_depois']}")


def test_o_grupo_volta_quando_o_valor_volta(medido):
    """E o caminho de volta também apaga: pintar ``max`` de novo devolve UM só."""
    assert _aceso(medido["fim"], "p1·degrau") == ["max"]
    assert len([c for c in medido["classes_fim"] if "on" in c.split()]) == 1


# -- (b) o alvo é idempotente e devolve 0 --------------------------------
def test_pintar_o_mesmo_valor_de_novo_devolve_zero(medido):
    """Um alvo que sempre diz "1" infla a contagem de todas as abas."""
    assert medido["n_balanceado"] > 0, (
        "a primeira pintura mudou classe, cor e booleano — tinha de contar")
    assert medido["n_denovo"] == 0, (
        f"pintar os MESMOS valores contou {medido['n_denovo']} pintura(s). O "
        f"`cls()` dos pilotos velhos devolvia 1 sempre, e é esse o defeito.")


def test_o_booleano_acende_e_apaga_por_si(medido):
    """O rótulo ``Máx`` e a coluna "Ajuste próprio": sem grupo, sem ``quando``."""
    assert _um(medido["depois"], "p1·mult-teto") == ""
    assert _um(medido["depois"], "ajuste") == ""
    assert _um(medido["fim"], "p1·mult-teto") == "sim"
    assert _um(medido["fim"], "ajuste") == "sim"


# -- a cor vai para o `color`, e o texto fica em paz ---------------------
def test_a_cor_vai_para_o_color(medido):
    """O clique do analógico é COR na GTK — e o rótulo ``L3`` continua ``L3``."""
    assert medido["cor_depois"] == "var(--plastico)"
    assert medido["texto_l3"] == "L3", (
        "pintar a cor não pode escrever nada dentro do círculo — foi por não "
        "haver este alvo que `a02_controles.py` teve de escrever `[L3]` em texto")
    assert _um(medido["depois"], "p1·l3") == "var(--plastico)"


def test_a_cor_vazia_apaga_e_devolve_a_folha_de_estilo(medido):
    """Um analógico solto volta à cor de sempre, em vez de ficar aceso."""
    assert medido["cor_fim"] == ""
    assert _um(medido["fim"], "p1·l3") == "", (
        "o vazio tem de APAGAR a cor de linha; sem isso o clique nunca acaba")


# -- a normalização de cor, PERGUNTADA ao motor -------------------------
def test_a_cor_e_medida_no_webkit_e_nao_transcrita(medido):
    """``_cor_css`` contra o CSSOM deste motor, forma a forma.

    O TESTE QUE ISTO SUBSTITUI comparava ``_cor_css`` com um dicionário de 17
    pares DIGITADO no arquivo. Ele era verde para sempre, e a única coisa capaz
    de derrubá-lo era alguém editar a função — a PALAVRA no lugar do ATO. Duas
    das famílias que a transcrição declarava cobrir estavam erradas:

        hsl(210, 50%, 40%)   o WebKit devolve rgb(51, 102, 153); a régua devolvia
                             a string intacta e chamava a cor certa de MORTA
        #0000ff80            o WebKit serializa o alfa CURTO — 0.5 —, e a régua
                             arredondava a três casas: 0.502

    Aqui não há tabela de respostas: a resposta vem do motor, nesta carga de
    página, a cada execução. Se o WebKit de amanhã normalizar diferente, este
    teste reprova NOMEANDO a forma — em vez de a divergência sair muda numa aba.
    """
    medidas = {forma: devolvido for forma, devolvido in medido["cores"]}
    assert len(medidas) >= 50, (
        f"a sonda só mediu {len(medidas)} formas — as famílias que a régua "
        "declara cobrir não cabem nisso")
    diferentes = {forma: (devolvido, regua._cor_css(forma))
                  for forma, devolvido in medidas.items()
                  if regua._cor_css(forma) != devolvido}
    assert not diferentes, (
        "a régua e o CSSOM discordam — `webkit` é o que a tela devolve e "
        f"`python` é o que a régua compara com ele: {diferentes}")


def test_a_cor_invalida_volta_vazia_dos_dois_lados(medido):
    """O CSS que o motor RECUSA não pode virar valor de comparação.

    Devolver a string crua diria ENDEREÇO MORTO sobre um campo que o navegador
    nem chegou a aceitar — e, do lado do arquivo, faria a régua esperar da tela
    um valor que a tela nunca vai mostrar.
    """
    medidas = dict(medido["cores"])
    for forma in ("Cosmic Red", "#12345", "#GGG", "rgb(1,2)", "rgb()"):
        assert medidas[forma] == "", (
            f"{forma!r} passou a ser CSS válido neste motor — a razão deste "
            "teste mudou")
        assert regua._cor_css(forma) == ""


def test_um_tique_que_pinta_zero_nao_vira_pagina_trocada(medido):
    """``0 || -1`` é ``-1`` — e era assim que o piloto pedia a pintura.

    O `-1` significa "a página trocou no meio", e o `contou()` do piloto
    descartava tudo que voltasse negativo. Logo TODO tique que pintava zero
    sumia da conta, e o detector de aba muda do relato (`if conta and pico == 0`)
    era **ramo morto**: para o pico ser zero a lista teria de ser só de zeros, e
    zero nunca entrava. Era a linha escrita para pegar exatamente o defeito da
    `06-navegacao`, que publicou zero endereços em 01/09 sem ninguém ver.

    Aqui a expressão é lida do FONTE do piloto e rodada no motor, com a carga
    que ele acabou de pintar — o pintor não tem o que mudar e devolve zero.
    """
    assert medido["zero"] == 0, (
        f"o pedido de pintura devolveu {medido['zero']!r} para um tique que "
        "pintou zero valores — se for negativo, o piloto o conta como 'a "
        "página trocou' e a aba muda volta a ser invisível")
    assert medido["zero_com_ou"] == -1, (
        "a forma antiga (`|| -1`) deixou de confundir zero com página trocada "
        "neste motor — a razão desta régua mudou")


# -- o selo, do lado Python: casar com o VIZINHO é pior que não ter selo --
def test_o_selo_casa_com_o_proprio_elemento_e_nao_com_o_vizinho():
    """``_selos_alinhados`` é quem virou 74 INDECIDÍVEIS em PRODUTO — e não tinha régua.

    O ``--sem-selo`` prova que o selo é CONSULTADO, não que ele é MEDIDO: um
    selo constante ``True`` devolvia a MESMA tabela da régua do mockup (medido
    em 02/09/2026: ``330 · 262 · 68 · 0`` com e sem a mordida, linha por linha)
    e os mesmos verdes no CI. E selo constante ``True`` é, por definição,
    *acreditar no que o pacote declarou* — a leitura-de-código que esta régua
    existe para não fazer.

    A razão de o instrumento vivo não ver: nos 330 campos de hoje não existe um
    só caso de ``declarado == vivo == cravado`` SEM selo, então o selo não
    particiona nada. Quem separa é este teste, com dois elementos de MESMO
    endereço e selos DIFERENTES.

    A MORDIDA: troque o corpo por ``fora.append(True)`` e ele reprova em
    ``[True, False]``; troque por ``disponiveis[0]`` (casar sempre com o
    primeiro) e ele reprova na ordem invertida.
    """
    cravados = regua._campos_cravados(
        '<div data-controle="p1">'
        '<b data-campo="degrau" data-hef-alvo="classe" data-hef-quando="a">A</b>'
        '<b data-campo="degrau" data-hef-alvo="classe" data-hef-quando="b">B</b>'
        '</div><span data-campo="solto">x</span>')
    # o LER_CAMPOS devolve cinco colunas: chave, dono, alvo, valor, selo.
    vivos = [("degrau", "p1", "classe", "", True),
             ("degrau", "p1", "classe", "", False),
             ("solto", "", "texto", "x", False)]
    assert regua._selos_alinhados(cravados, vivos) == [True, False, False], (
        "o selo do primeiro degrau não pode vazar para o segundo — casar selo "
        "com o vizinho é pior que não ter selo nenhum")

    invertido = [vivos[1], vivos[0], vivos[2]]
    assert regua._selos_alinhados(cravados, invertido) == [False, True, False], (
        "a ordem de ocorrência dentro do endereço É o casamento; ignorá-la "
        "daria o mesmo resultado nas duas leituras")


def test_o_campo_que_sumiu_da_tela_nao_ganha_selo():
    """Bloco trocado por ``innerHTML`` não tem elemento — logo não tem visita.

    Selá-lo por omissão faria todo campo de um bloco trocado virar PRODUTO por
    um caminho que ninguém mediu. O ``_classificar`` já o julga PRODUTO pelo
    ``SUMIU``, que é o fato de verdade.
    """
    cravados = regua._campos_cravados(
        '<span data-campo="a">1</span><span data-campo="b">2</span>')
    assert regua._selos_alinhados(cravados, [("a", "", "texto", "1", True)]) == [
        True, False]


def test_o_selo_decide_o_indecidivel_e_so_ele():
    """O mesmo campo, mesmo valor: com selo é PRODUTO, sem selo é INDECIDÍVEL.

    É a asserção que o número da leva inteira apoia — e ela tem de existir num
    caso em que os dois vereditos são possíveis, que é o que a mesa de hoje não
    oferece.
    """
    cravados = regua._campos_cravados('<span data-campo="bateria">95%</span>')
    declarado = {("", "bateria"): "95%"}
    (com,) = regua._classificar(cravados, ["95%"], declarado, [True])
    (sem,) = regua._classificar(cravados, ["95%"], declarado, [False])
    assert (com.classe, sem.classe) == (regua.PRODUTO, regua.INDECIDIVEL)


def test_o_selo_da_visita_marca_so_quem_o_pintor_tocou(medido):
    """O selo é o que decide um INDECIDÍVEL — e ele não pode selar tudo.

    ``r3`` tem endereço na página e nenhum pacote o declara. Se ele voltar
    selado, o selo não está registrando a visita: está sendo escrito no ar, e
    todo campo coincidente viraria PRODUTO de graça.
    """
    selos: dict[str, list[bool]] = {}
    for x in medido["fim"]:
        selos.setdefault(_endereco(x), []).append(bool(x[4]))
    assert selos["p1·degrau"] == [True] * 4
    assert selos["p1·l3"] == [True]
    assert selos["p1·r3"] == [False], (
        "ninguém pintou o `r3` neste roteiro — ele não pode ter selo")
