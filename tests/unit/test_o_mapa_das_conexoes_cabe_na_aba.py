"""O Mapa das Conexões cabe na aba e fala menos — O-MAPA-DAS-CONEXOES-CABE-NA-ABA-E-FALA-MENOS-01.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from dataclasses import replace
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    Aparelho,
    Barramento,
    Censo,
)
from hefesto_dualsense4unix.interface import arranjo_desta_maquina, onde, pagina_do_mapa
from hefesto_dualsense4unix.utils.maquina import (
    FaceDeclarada,
    MaquinaConfig,
    MapaDaMesa,
    PortaDeclarada,
)

SPRINT = "O-MAPA-DAS-CONEXOES-CABE-NA-ABA-E-FALA-MENOS-01"

NA_BANCADA = any(SPRINT in e.porque for e in pagina_do_mapa.EDICOES_ESPERANDO_A_SESSAO_DELA)
QUAL = "bancada" if NA_BANCADA else "publicada"

VISTAS = {"foto-3": (1920, 887), "dela": (1918, 840), "ladrilhada": (1212, 809),
          "estreita": (860, 809)}

SOBRA_NA_LADRILHADA = 60

PALAVRAS_DO_SUGESTOES = 60


def _ap(caminho: str, vid: str, pid: str, especie: str, tripla: tuple[str, str, str],
        **kw: Any) -> Aparelho:
    aparelho = Aparelho(
        no=f"/sys/de-mentira/{vid}{pid}", nome_do_kernel=caminho, vid=vid, pid=pid,
        produto=f"{especie or 'Aparelho'} de prova", especie=especie, classe=tripla[0],
        subclasse=tripla[1], protocolo=tripla[2], velocidade_mbps=480.0)
    return replace(aparelho, **kw) if kw else aparelho


APARELHOS = (
    _ap("9-4", "5555", "0005", "Hub", ("09", "00", "00"), e_hub=True),
    _ap("9-4.1", "2222", "0002", "Bluetooth", ("e0", "01", "01")),
    _ap("9-4.2", "2222", "0012", "Bluetooth", ("e0", "01", "01")),
    _ap("9-3", "2222", "0022", "Bluetooth", ("e0", "01", "01")),
    _ap("9-5", "6666", "0006", "", ("ff", "ff", "ff")),
    _ap("9-1", "4444", "0004", "Webcam", ("0e", "01", "00")),
    _ap("9-4.5", "1111", "0001", "Teclado", ("03", "01", "01")),
    _ap("9-6", "3333", "0003", "Mouse", ("03", "01", "02")),
    _ap("9-4.6", "7777", "0007", "Áudio", ("01", "01", "00")),
)


def _maquina() -> MaquinaConfig:
    portas = {str(n): PortaDeclarada(caminho=f"9-{n}", nos=[f"usb9-port{n}"])
              for n in range(1, 9)}
    for k, n in enumerate(range(9, 16), 1):
        portas[str(n)] = PortaDeclarada(caminho=f"9-4.{k}", nos=[f"9-4-port{k}"])
    return MaquinaConfig(mapa=MapaDaMesa(
        faces=[FaceDeclarada(nome="Frente do gabinete", portas=["1", "2"], perto=True),
               FaceDeclarada(nome="Atrás do gabinete", portas=[str(n) for n in range(3, 9)]),
               FaceDeclarada(nome="Num hub ou extensão",
                             portas=[str(n) for n in range(9, 16)])],
        portas=portas))


def _arranjo() -> dict[str, Any]:
    dado = arranjo_desta_maquina.para_a_pagina(
        agora=dt.datetime(2026, 10, 1, 23, 0), carregar=_maquina,
        ler_o_barramento=lambda: Censo(aparelhos=APARELHOS, barramentos=(
            Barramento(no="/sys/usb9", nome_do_kernel="usb9", velocidade_mbps=480.0),)),
        ler_o_serial=lambda _no: "")
    assert dado is not None, "o arranjo sintético não saiu — a régua mediria o exemplo"
    assert len(dado["faces"]) == 3 and len(dado["aparelhos"]) == 9, dado
    return dado


MEDIR = r"""
(function(){
  const q = s => document.querySelector(s);
  const r = el => el.getBoundingClientRect();
  const corpo = q('.pagina > .corpo'), painel = q('#painel');
  const visivel = el => !el.closest('button');
  const palavras = [], linhas = new Set();
  const anda = document.createTreeWalker(painel, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = anda.nextNode())) {
    const p = n.parentElement;
    if (!p || !visivel(p) || p.closest('.dica')) continue;
    n.textContent.split(/\s+/).filter(w => /[A-Za-zÀ-ÿ0-9]/.test(w)).forEach(w => palavras.push(w));
  }
  const chapas = [...document.querySelectorAll('#faces .chapa')];
  const resumo = q('#painel > p');
  const alturaDaLinha = resumo ? parseFloat(getComputedStyle(resumo).lineHeight) : 0;
  return JSON.stringify({
    modo: (q('.modo[aria-pressed="true"]') || {}).textContent,
    corpo: [corpo.scrollHeight, corpo.clientHeight], corpo_top: r(corpo).top,
    corpo_bottom: r(corpo).bottom,
    caixa: [Math.round(r(q('.pagina')).left), Math.round(r(q('.pagina')).top),
            Math.round(r(q('.pagina')).width), Math.round(r(q('.pagina')).height)],
    resumo: resumo ? {altura: r(resumo).height, retangulos: resumo.getClientRects().length,
                      linha: alturaDaLinha, texto: resumo.innerText} : null,
    palavras: palavras.length, texto: (painel.innerText || '').replace(/\s+/g, ' ').trim(),
    legenda_bottom: r(q('#legenda')).bottom,
    primeira_chapa_top: chapas.length ? r(chapas[0]).top : null,
    faces_bottom: r(q('#faces')).bottom, bandeja_bottom: r(q('.palco > .bandeja')).bottom,
    lista: [q('#bandeja').scrollHeight, q('#bandeja').clientHeight],
    titulo_da_bandeja: (q('.bandeja h3') || {}).textContent,
    chapas: chapas.map(c => ({n: c.querySelectorAll(':scope > .soquete').length,
      linhas: [...new Set([...c.querySelectorAll(':scope > .soquete')]
        .map(s => Math.round(r(s).top)))]})),
    ids_reexaminar: document.querySelectorAll('[id="reexaminar"]').length,
    ja_movi: !!q('#painel .ja-movi'),
    entao: (function(){ const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      let n, achou = false; while ((n = w.nextNode())) {
        if (n.parentElement && !n.parentElement.closest('script,style')
            && /\bentao\b/i.test(n.textContent)) achou = true; }
      return achou; })(),
    pergunta: (q('#chamada-mao') || {}).innerText || null,
    pergunta_e_escolhas: q('#chamada-mao') && q('#painel .escolhas .escolha')
      ? [Math.round(r(q('#chamada-mao')).top), Math.round(r(q('#painel .escolhas .escolha')).top),
         Math.round(r(q('#chamada-mao')).bottom),
         Math.round(r(q('#painel .escolhas .escolha')).bottom)]
      : null,
    nao_presumo: /n[ãa]o presumo/i.test(painel.innerText),
    porques: [...document.querySelectorAll('#faces .porque')]
      .map(e => e.textContent.trim()).filter(Boolean),
    faces_null: /\bnull\b|\bundefined\b/i.test(q('#faces').innerText),
  });
})()
"""

DICA = r"""
(function(){
  const a = document.querySelector('#painel .receita .ajuda');
  if (!a) return JSON.stringify({existe: false});
  const d = a.querySelector('.dica');
  const regras = [];
  for (const folha of document.styleSheets) {
    for (const regra of folha.cssRules) {
      if (regra.selectorText && /\.receita \.ajuda:(focus|hover) \.dica/.test(regra.selectorText)
          && regra.style.display && regra.style.display !== 'none') regras.push(regra.selectorText);
    }
  }
  const fechada = getComputedStyle(d).display;
  d.style.display = 'flex';
  const rd = d.getBoundingClientRect();
  const rp = document.querySelector('.pagina').getBoundingClientRect();
  const fora = {existe: true, focavel: a.tabIndex === 0, fechada: fechada, regras: regras,
    cabe: rd.right <= rp.right + 1 && rd.width > 0, texto: d.innerText.replace(/\s+/g, ' ')};
  d.style.display = '';
  return JSON.stringify(fora);
})()
"""


def _clicar(seletor: str) -> str:
    alvo = json.dumps(seletor)
    return (f"(function(){{const b=document.querySelector({alvo});"
            f"if(!b){{return 'sem ' + {alvo};}} b.click(); return 'clicou';}})()")


def _no_webkit(pagina: str, tamanho: tuple[int, int], passos: list[str]) -> list[Any]:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("abre a página num WebKit")
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    from hefesto_dualsense4unix.interface import hefesto_vivo

    respostas: list[str] = []
    view = WebKit2.WebView()
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(*tamanho)
    view.set_size_request(*tamanho)
    janela.add(view)
    janela.show_all()
    fila = [hefesto_vivo.BOOTSTRAP, *passos]

    def seguinte() -> bool:
        if not fila:
            Gtk.main_quit()
            return False

        def respondeu(v: Any, res: Any, _u: Any = None) -> None:
            try:
                respostas.append(v.evaluate_javascript_finish(res).to_string())
            except Exception as erro:
                respostas.append(f"ERRO {erro}")
            GLib.timeout_add(80, seguinte)

        view.evaluate_javascript(fila.pop(0), -1, None, None, None, respondeu, None)
        return False

    def carregou(_v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            GLib.timeout_add(50, seguinte)

    view.connect("load-changed", carregou)
    view.load_uri(onde.pagina(pagina, publicado=not NA_BANCADA).as_uri())
    guarda = GLib.timeout_add(40000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert len(respostas) == len(passos) + 1, f"o WebKit parou no meio ({QUAL}): {respostas}"
    return [json.loads(x) if x.startswith(("{", "[")) else x for x in respostas[1:]]


_MEDIDAS: dict[str, dict[str, Any]] = {}


def _medido(vista: str) -> dict[str, Any]:
    """Atual, Sugestões (e a dica aberta), Adicionar, e a caixa da 08 na mesma vista."""
    if vista not in _MEDIDAS:
        tamanho = VISTAS[vista]
        lidas = _no_webkit(arranjo_desta_maquina.PAGINA, tamanho, [
            arranjo_desta_maquina.js_da_entrega(_arranjo()), MEDIR,
            _clicar('.modo[data-modo="ideal"]'), MEDIR, DICA,
            _clicar('.modo[data-modo="mao"]'), MEDIR,
        ])
        aba = _no_webkit("08-conexoes.html", tamanho, [
            "(function(){const r=document.querySelector('.janela').getBoundingClientRect();"
            "return JSON.stringify([Math.round(r.left),Math.round(r.top),"
            "Math.round(r.width),Math.round(r.height)]);})()"])
        _MEDIDAS[vista] = {"atual": lidas[1], "sugestoes": lidas[3], "dica": lidas[4],
                           "adicionar": lidas[6], "janela_da_08": aba[0]}
    return _MEDIDAS[vista]


@pytest.mark.parametrize("vista", ["foto-3", "dela"])
def test_o_atual_cabe_na_caixa_da_aba_sem_rolar(vista: str) -> None:
    """MORDIDA: tire a regra da bandeja do ``@media (min-width: 901px)`` →"""
    m = _medido(vista)
    atual = m["atual"]
    assert atual["caixa"] == m["janela_da_08"], (
        f"({QUAL}) a caixa do mapa {atual['caixa']} não é a da aba 08 {m['janela_da_08']}")
    rolagem, visivel = atual["corpo"]
    assert rolagem <= visivel + 1, (
        f"({QUAL}) na vista {vista} o Atual rola {rolagem - visivel} px: a aba não rola")


def test_na_janela_ladrilhada_sobra_no_maximo_uma_linha_de_chapa() -> None:
    atual = _medido("ladrilhada")["atual"]
    rolagem, visivel = atual["corpo"]
    sobra = rolagem - visivel
    print(f"({QUAL}) ladrilhada {VISTAS['ladrilhada']}: o Atual rola {sobra} px")
    assert sobra <= SOBRA_NA_LADRILHADA, f"({QUAL}) o Atual rola {sobra} px na janela ladrilhada"


@pytest.mark.parametrize("vista", ["foto-3", "dela", "ladrilhada"])
def test_atualmente_conectado_acaba_no_fim_do_hub_e_rola(vista: str) -> None:
    atual = _medido(vista)["atual"]
    assert atual["titulo_da_bandeja"].lower() == "atualmente conectado"
    assert abs(atual["bandeja_bottom"] - atual["faces_bottom"]) < 2, (
        f"({QUAL}) a bandeja acaba em {atual['bandeja_bottom']:.0f} e a última face em "
        f"{atual['faces_bottom']:.0f}")
    conteudo, altura = atual["lista"]
    assert conteudo > altura > 0, f"({QUAL}) a lista não rola por dentro: {atual['lista']}"


def test_com_o_palco_numa_coluna_a_lista_tem_altura_e_rola() -> None:
    """MORDIDA: tire o ``@media (min-width: 901px)`` (a regra vale em toda"""
    conteudo, altura = _medido("estreita")["atual"]["lista"]
    assert conteudo > altura > 0, f"({QUAL}) a 860 px a lista mede {altura} de {conteudo}"


def test_as_entradas_se_arrumam_em_quantas_colunas_couberem() -> None:
    """MORDIDA: tire a ``.chapa.coluna`` do ``auto-fill`` → a Frente volta a uma"""
    chapas = _medido("dela")["atual"]["chapas"]
    assert [c["n"] for c in chapas] == [2, 6, 7], chapas
    assert len(chapas[0]["linhas"]) == 1, f"({QUAL}) as duas da Frente não estão lado a lado"
    for chapa in chapas:
        assert len(chapa["linhas"]) <= math.ceil(chapa["n"] / 4), (
            f"({QUAL}) {chapa['n']} entradas em {len(chapa['linhas'])} linhas")
    estreita = _medido("ladrilhada")["atual"]["chapas"]
    print(f"({QUAL}) ladrilhada: linhas por chapa {[len(c['linhas']) for c in estreita]}")


def test_o_resumo_do_atual_e_uma_linha_e_a_legenda_mora_no_alto() -> None:
    """MORDIDA: volte o resumo a dois ``<p>``, ou tire a legenda da linha dos modos."""
    atual = _medido("dela")["atual"]
    resumo = atual["resumo"]
    assert resumo is not None and "entradas mapeadas" in resumo["texto"].lower(), resumo
    assert resumo["altura"] < 1.5 * resumo["linha"], (
        f"({QUAL}) o resumo tem {resumo['altura']:.0f} px para uma linha de {resumo['linha']}")
    assert atual["legenda_bottom"] <= atual["primeira_chapa_top"], (
        f"({QUAL}) a legenda acaba em {atual['legenda_bottom']:.0f}, abaixo da primeira face")
    assert atual["legenda_bottom"] <= atual["corpo_bottom"], "a legenda saiu da vista"


def test_nenhum_texto_sem_acento_e_um_so_reexaminar() -> None:
    """MORDIDA: desfaça um «então», ou devolva o ``id="reexaminar"`` ao «Já movi»."""
    for modo in ("atual", "sugestoes", "adicionar"):
        lido = _medido("dela")[modo]
        assert not lido["entao"], f"({QUAL}) o {modo} diz uma palavra sem acento"
        assert lido["ids_reexaminar"] == 1, (
            f"({QUAL}) {lido['ids_reexaminar']} elementos com o id `reexaminar` no {modo}")
    assert _medido("dela")["sugestoes"]["ja_movi"], "o «Já movi» sumiu do Sugestões"


@pytest.mark.parametrize("vista", ["foto-3", "dela"])
def test_o_sugestoes_fala_menos_e_o_mapa_comeca_na_vista(vista: str) -> None:
    """MORDIDA: devolva o parágrafo «Eu não presumo» (ou a chamada das variantes)"""
    sug = _medido(vista)["sugestoes"]
    assert not sug["nao_presumo"], f"({QUAL}) o parágrafo «Eu não presumo» voltou"
    assert sug["palavras"] <= PALAVRAS_DO_SUGESTOES, (
        f"({QUAL}) o Sugestões tem {sug['palavras']} palavras: {sug['texto']}")
    assert "não foi medido nesta máquina" in sug["texto"].lower(), (
        "a linha do ganho não medido saiu (D-LINHA-DO-GANHO-NAO-MEDIDO: sempre visível)")
    assert sug["primeira_chapa_top"] < sug["corpo_bottom"], (
        f"({QUAL}) o mapa do Sugestões começa em {sug['primeira_chapa_top']:.0f}, "
        f"fora da vista (que acaba em {sug['corpo_bottom']:.0f})")


def test_o_mapa_do_sugestoes_diz_so_o_veredito() -> None:
    """No mapa do Sugestões cada entrada diz só o veredito («vem para cá», «sai"""
    sug = _medido("dela")["sugestoes"]
    assert sug["porques"] == [], (
        f"({QUAL}) o mapa do Sugestões explica o veredito: {sug['porques']}")
    assert not sug["faces_null"], f"({QUAL}) o mapa do Sugestões diz «null» ou «undefined»"


def test_a_razao_de_cada_movimento_mora_no_interrogacao() -> None:
    """As razões com selo saem da tela e vão para o «?» do movimento, que abre"""
    dica = _medido("dela")["dica"]
    assert dica["existe"], f"({QUAL}) o movimento não tem o «?» das razões"
    assert dica["focavel"], f"({QUAL}) o «?» não recebe o foco: o controle não o abre"
    assert dica["fechada"] == "none", f"({QUAL}) a dica nasce aberta: {dica}"
    regras = dica["regras"]
    assert any(":focus" in r for r in regras) and any(":hover" in r for r in regras), (
        f"({QUAL}) a folha não abre a dica no foco e sob o ponteiro: {dica['regras']}")
    assert dica["cabe"], f"({QUAL}) a dica aberta passa da borda da caixa"
    assert "medido" in dica["texto"].lower() or "derivado" in dica["texto"].lower(), dica


def test_o_adicionar_e_uma_linha_com_a_pergunta_dela() -> None:
    mao = _medido("dela")["adicionar"]
    assert mao["pergunta"] and mao["pergunta"].lower() == "o que você pretende conectar?", mao
    topo_p, topo_e, fim_p, fim_e = mao["pergunta_e_escolhas"]
    assert topo_e < fim_p and topo_p < fim_e, (
        f"({QUAL}) a pergunta e as escolhas não estão na mesma linha: {mao['pergunta_e_escolhas']}")
