#!/usr/bin/env python3
"""O pintor de verdade, num WebKit de verdade, pintando os dois alvos novos."""
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

FORMAS_DE_COR = [
    "#6272a4", "#FF5555", "#7EB8D4", "#fff", "#6272A4", " #6272a4 ",
    "#ff5555aa", "#fffa", "#abc4",
    "#0000ff80", "#0000ff01", "#0000ff00", "#0000ffff",
    "rgba(0,0,0,.5)", "rgba(0,0,0,0.502)", "rgba(0,0,0,0.6667)",
    "rgba(0,0,0,1)", "rgba(0,0,0,-1)", "rgba(1,2,3,4)",
    "rgba(255,255,255,0.0039)",
    "rgb(186, 218, 85)", "rgb(1,2,3)", "rgb(1 2 3)", "RGB(1,2,3)",
    "rgb(37.355% 50.439% 0%)", "rgb(0 0 0 / 50%)", "rgb(1,2,3,0.5)",
    "rgb(300, -5, 10)", "rgb(1.5, 2.4, 3.6)", "rgba(10%, 20%, 30%, 50%)",
    "hsl(210, 50%, 40%)", "hsl(0 100% 50%)", "hsla(120, 60%, 30%, 0.4)",
    "hsl(210deg, 50%, 40%)", "hsl(-30, 50%, 40%)", "hsl(210, 150%, 40%)",
    "hsl(210, -50%, 40%)", "hsl(210, 50%, 150%)", "hsl(0.5turn, 50%, 40%)",
    "hsl(3.665rad, 50%, 40%)", "hsl(200grad, 50%, 40%)", "hsl(570, 50%, 40%)",
    "red", "transparent", "currentColor", "WHITE", "AliceBlue",
    "var(--plastico)", "color-mix(in srgb, red, blue)", "",
    "Cosmic Red", "#12345", "#GGG", "rgb(1,2)", "rgb()",
]


def _constante(nome: str) -> str:
    """O BOOTSTRAP e o LER_CAMPOS lidos do FONTE do piloto, e não importados."""
    fonte = PILOTO.read_text(encoding="utf-8")
    achou = re.search(rf'^{nome} = r"""(.*?)"""$', fonte, re.S | re.M)
    assert achou, f"o piloto perdeu o {nome} — não há o que testar"
    return achou.group(1)


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
    guarda = GLib.timeout_add(20000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
    assert saiu, "o WebKit não respondeu em 20 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return json.loads(saiu[0])


def _endereco(linha: list) -> str:
    return f"{linha[1]}·{linha[0]}" if linha[1] else str(linha[0])


def _campos(linhas: list) -> dict[str, list[str]]:
    """``{endereço: [valores]}``, da leitura de tela do próprio piloto."""
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


def test_o_leitor_de_tela_casa_com_o_parser_do_arquivo(medido):
    """A guarda do DOM virgem, aplicada a um caso que nenhuma página tem ainda."""
    cravados = regua._campos_cravados(PAGINA)
    virgem = medido["virgem"]
    assert len(virgem) == len(cravados)
    for c, linha in zip(cravados, virgem, strict=True):
        assert (str(linha[0]), str(linha[1])) == (c.chave, c.dono)
        assert str(linha[3]) == c.valor, (
            f"{c.endereco}: o arquivo diz {c.valor!r} e a tela virgem mostra "
            f"{linha[3]!r} — o parser e o leitor discordam no alvo {c.alvo}")


def test_as_irmas_do_grupo_apagam(medido):
    """Pintar ``balanceado`` apaga o ``max`` que estava aceso — e só um fica."""
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


def test_a_cor_e_medida_no_webkit_e_nao_transcrita(medido):
    """``_cor_css`` contra o CSSOM deste motor, forma a forma."""
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
    """O CSS que o motor RECUSA não pode virar valor de comparação."""
    medidas = dict(medido["cores"])
    for forma in ("Cosmic Red", "#12345", "#GGG", "rgb(1,2)", "rgb()"):
        assert medidas[forma] == "", (
            f"{forma!r} passou a ser CSS válido neste motor — a razão deste "
            "teste mudou")
        assert regua._cor_css(forma) == ""


def test_um_tique_que_pinta_zero_nao_vira_pagina_trocada(medido):
    """``0 || -1`` é ``-1`` — e era assim que o piloto pedia a pintura."""
    assert medido["zero"] == 0, (
        f"o pedido de pintura devolveu {medido['zero']!r} para um tique que "
        "pintou zero valores — se for negativo, o piloto o conta como 'a "
        "página trocou' e a aba muda volta a ser invisível")
    assert medido["zero_com_ou"] == -1, (
        "a forma antiga (`|| -1`) deixou de confundir zero com página trocada "
        "neste motor — a razão desta régua mudou")


def test_o_selo_casa_com_o_proprio_elemento_e_nao_com_o_vizinho():
    """``_selos_alinhados`` é quem virou 74 INDECIDÍVEIS em PRODUTO — e não tinha régua."""
    cravados = regua._campos_cravados(
        '<div data-controle="p1">'
        '<b data-campo="degrau" data-hef-alvo="classe" data-hef-quando="a">A</b>'
        '<b data-campo="degrau" data-hef-alvo="classe" data-hef-quando="b">B</b>'
        '</div><span data-campo="solto">x</span>')
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
    """Bloco trocado por ``innerHTML`` não tem elemento — logo não tem visita."""
    cravados = regua._campos_cravados(
        '<span data-campo="a">1</span><span data-campo="b">2</span>')
    assert regua._selos_alinhados(cravados, [("a", "", "texto", "1", True)]) == [
        True, False]


def test_o_selo_decide_o_indecidivel_e_so_ele():
    """O mesmo campo, mesmo valor: com selo é PRODUTO, sem selo é INDECIDÍVEL."""
    cravados = regua._campos_cravados('<span data-campo="bateria">95%</span>')
    declarado = {("", "bateria"): "95%"}
    (com,) = regua._classificar(cravados, ["95%"], declarado, [True])
    (sem,) = regua._classificar(cravados, ["95%"], declarado, [False])
    assert (com.classe, sem.classe) == (regua.PRODUTO, regua.INDECIDIVEL)


def test_o_selo_da_visita_marca_so_quem_o_pintor_tocou(medido):
    """O selo é o que decide um INDECIDÍVEL — e ele não pode selar tudo."""
    selos: dict[str, list[bool]] = {}
    for x in medido["fim"]:
        selos.setdefault(_endereco(x), []).append(bool(x[4]))
    assert selos["p1·degrau"] == [True] * 4
    assert selos["p1·l3"] == [True]
    assert selos["p1·r3"] == [False], (
        "ninguém pintou o `r3` neste roteiro — ele não pode ter selo")
