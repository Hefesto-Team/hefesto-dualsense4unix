"""A coluna da janela da extensão mostra a bateria e a força em percentual e esconde o adaptador
já escolhido.

A-COLUNA-DA-JANELA-DA-EXTENSAO-MOSTRA-BATERIA-E-FORCA-E-ESCONDE-O-ADAPTADOR-01 (01/11/2026). O
aparelho ativo traz dois pares ícone + percentual (a bateria, quando a extensão a dá, e a força de
agora); a conexão conectada com escolhas mostra o nome escolhido num botão na própria linha, e os
nomes só se abrem no clique dele, sem fechar sozinhos no tique que repinta a coluna; o deslizante
que segue a grade de um ``por_botao`` abre uma seção própria. O manifesto é sintético, com as abas
«Controle» e «Conexão».

MORDIDAS (01/11/2026, executadas sobre a cura e devolvidas):

- ``_aparelho_html`` de volta à pilha e à onda reprova
  ``test_o_aparelho_ativo_traz_a_bateria_e_a_forca_em_percentual``,
  ``test_sem_bateria_so_a_forca`` e ``test_no_webkit_a_coluna_cabe_e_o_adaptador_abre_e_fecha``;
- ``fechavel`` sempre falso (as escolhas à mostra como antes) reprova
  ``test_a_conexao_conectada_esconde_as_escolhas_atras_do_nome`` e a régua do WebKit;
- o observador do ``comportamento.js`` arrancado (o tique repinta a coluna e fecha as escolhas)
  reprova ``test_no_webkit_a_coluna_cabe_e_o_adaptador_abre_e_fecha``;
- ``_secao_da_opcao`` trocada por ``_linha_da_opcao`` reprova
  ``test_o_deslizante_depois_da_grade_abre_uma_secao`` e a régua do WebKit.
"""

from __future__ import annotations

import json
import pathlib
import re
from html.parser import HTMLParser
from typing import Any

from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
from tests.unit.test_a_linha_sem_aparelho_fica_a_direita_do_parear import no_webkit
from tests.unit.test_a_lista_da_janela_configurar_nao_pula_ao_clicar_um_efeito import (  # noqa: F401
    ENDERECO,
    pagina_fresca,
)

MOD = "exemplo"
NOMES = ["Automático", "Meio", "Direita"]
LIGAS = {"bluetooth": exp.Liga(MOD, "usar_o_bluetooth", True, "adaptador_bluetooth", "Meio"),
         "usb": exp.Liga(MOD, "usar_o_adaptador", True)}
AGORA = ("conexoes", "aparelhos")  # (noqa-acento)


def _estado(estado_bt: str = "ligado", forca: float = 0.3) -> dict[str, Any]:
    return {"ligado": True,
            "conexoes": [  # (noqa-acento)
                {"id": "usb", "tipo": "Adaptador USB", "transporte": "usb", "estado": "ligado"},
                {"id": "bluetooth", "tipo": "Bluetooth do computador",
                 "transporte": "bluetooth", "estado": estado_bt, "escolhas": NOMES,
                 "escolha": "Meio"}],
            "aparelhos": [
                {"nome": "Aparelho 1", "estado": "ligado", "bateria": 80, "forca": forca},
                {"nome": "Aparelho 2", "estado": "ligado", "forca": 0.0},
                {"nome": "Aparelho 3", "estado": "desligado", "bateria": 40}]}


OPCOES = (
    exp.OpcaoDaJanela(MOD, "toques", "Controle", "ligado", True, (), "Controle"),
    exp.OpcaoDaJanela(MOD, "botoes", "Botões", "por_botao", {"cross": "Toque"}, (), "Controle",
                      formas=exp.FORMAS_DO_DESENHO, botoes=exp.BOTOES_DO_DESENHO),
    exp.OpcaoDaJanela(MOD, "forca_dos_toques", "Força", "deslizante", "100", (), "Controle",
                      0, 100, 5, degraus=20),
    exp.OpcaoDaJanela(MOD, "espera", "Espera", "deslizante", "3", (), "Controle", 0, 10, 1),
    exp.OpcaoDaJanela(MOD, "usar_o_bluetooth", "Bluetooth do computador", "ligado", True, (),
                      "Conexão"),
    exp.OpcaoDaJanela(MOD, "adaptador_bluetooth", "Adaptador Bluetooth", "escolha", "Meio",
                      tuple(NOMES), "Conexão"),
)


def _aparelhos(html: str) -> list[str]:
    return re.findall(r'<div class="ap[ "].*?</div>', html)


def test_o_aparelho_ativo_traz_a_bateria_e_a_forca_em_percentual() -> None:
    ap = _aparelhos(exp.agora_html(AGORA, _estado(), ligas=LIGAS))[0]
    pares = re.findall(r'<span class="ap-par (ap-\w+)"><svg class="ic".*?</svg><b>(\d+)%</b>', ap)
    assert pares == [("ap-bateria", "80"), ("ap-forca", "30")], ap
    assert 'class="vivo"' not in ap and 'class="bat"' not in ap, "a onda e a pilha seguem na linha"


def test_sem_bateria_so_a_forca() -> None:
    ap = _aparelhos(exp.agora_html(AGORA, _estado(), ligas=LIGAS))[1]
    assert re.findall(r'class="ap-par (ap-\w+)"', ap) == ["ap-forca"], ap
    assert "<b>0%</b>" in ap


def test_o_aparelho_fora_segue_com_a_pilula_do_estado() -> None:
    ap = _aparelhos(exp.agora_html(AGORA, _estado(), ligas=LIGAS))[2]
    assert "ap-par" not in ap and 'class="est est-mudo"' in ap and " fora" in ap, ap


class _Arvore(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__()
        self.pilha: list[dict[str, str]] = []
        self.vistos: list[tuple[dict[str, str], list[dict[str, str]]]] = []
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs} | {"_tag": tag}
        self.vistos.append((a, list(self.pilha)))
        if tag not in ("i", "input", "svg", "path", "rect", "line", "circle", "polyline"):
            self.pilha.append(a)

    def handle_endtag(self, tag: str) -> None:
        if tag not in ("i", "input", "svg", "path", "rect", "line", "circle", "polyline"):
            self.pilha.pop()


def test_a_conexao_conectada_esconde_as_escolhas_atras_do_nome() -> None:
    html = exp.agora_html(AGORA, _estado(), ligas=LIGAS)
    arvore = _Arvore(html)
    botao = [(a, pais) for a, pais in arvore.vistos if "cx-escolhido" in a.get("class", "")]
    assert len(botao) == 1, "a conexão conectada não ganhou o botão do nome escolhido"
    attrs, pais = botao[0]
    assert attrs["_tag"] == "button" and attrs.get("aria-expanded") == "false"
    assert not any("data-gesto" in p or "data-v" in p for p in [attrs, *pais]), (
        "o clique no botão do nome chegaria ao produto e ligaria ou desligaria a conexão")
    assert any(p.get("data-cx") == f"{MOD}:usar_o_bluetooth" for p in pais)
    assert re.search(r'class="cx-escolhido[^>]*><i></i><span>Meio</span>', html)
    escolhas = [pais for a, pais in arvore.vistos if a.get("class", "").startswith("cx-escolha ")
                or a.get("class") == "cx-escolha"]
    assert len(escolhas) == 3 and all(any("data-cx" in p for p in ps) for ps in escolhas)
    assert html.count("cx-com-escolhas") == 1, "a conexão sem escolhas ganhou o botão"


def test_a_conexao_que_nao_esta_conectada_segue_com_as_escolhas_abertas() -> None:
    for estado in ("procurando", "desligado", "falhou"):
        html = exp.agora_html(AGORA, _estado(estado), ligas=LIGAS)
        assert "cx-escolhido" not in html and "data-cx" not in html, estado
        assert html.count('class="cx-escolha') == 3 + 1, estado


def test_o_deslizante_depois_da_grade_abre_uma_secao() -> None:
    html = exp._linhas_das_opcoes(OPCOES[1:4])
    assert re.search(r'<div class="ky-sec" id="mod-op-forca_dos_toques"><div class="ky-rot">'
                     r'<span>Força</span></div><span class="ext-desl">', html), html
    assert '<div class="ky-linha" id="mod-op-espera">' in html, "a seção pegou o seguinte"
    solto = exp._linhas_das_opcoes(OPCOES[2:4])
    assert "ky-sec" not in solto, "o deslizante sem a grade antes virou seção"


_ABRIR = """(function(endereco, h){
  location.hash = endereco;
  window.__hef.pintar({blocos: {'#mod-janela': h}});
  const j = document.getElementById('mod-janela');
  const rot = [...j.querySelectorAll('.mj-abas > label')]
    .find(l => l.textContent.trim() === 'Controle');
  if (!rot) return 'sem a aba Controle';
  rot.click();
  return 'ok';
})(%s, %s)"""
_LER = """(function(){
  const j = document.getElementById('mod-janela');
  const r = e => { if (!e) return null; const x = e.getBoundingClientRect();
    return {x: Math.round(x.left), y: Math.round(x.top), d: Math.round(x.right),
            b: Math.round(x.bottom), h: Math.round(x.height)}; };
  const caixa = j.querySelector('.cx-com-escolhas');
  const esc = caixa && caixa.querySelector('.cx-escolhas');
  const aps = [...j.querySelectorAll('#mod-agora .ap')].map(a => ({ap: r(a),
    pares: [...a.querySelectorAll('.ap-par')].map(p => ({p: r(p), t: p.textContent.trim()}))}));
  const sec = j.querySelector('#mod-op-forca_dos_toques');
  return JSON.stringify({
    coluna: r(j.querySelector('#mod-agora')),
    linha: r(caixa && caixa.querySelector('.cx-liga')),
    botao: r(caixa && caixa.querySelector('.cx-escolhido')),
    nome: caixa && caixa.querySelector('.cx-escolhido').textContent.trim(),
    aberta: !!(esc && esc.getClientRects().length && esc.getBoundingClientRect().height > 0),
    expandido: caixa && caixa.querySelector('.cx-escolhido').getAttribute('aria-expanded'),
    aps,
    titulo: r(sec && sec.querySelector('.ky-rot')),
    faixa: r(sec && sec.querySelector('input[type=range]'))});
})()"""
_CLICAR = """(function(sel){
  const el = document.querySelector('#mod-janela ' + sel);
  if (!el) return 'sem ' + sel;
  el.click();
  return 'ok';
})(%s)"""
_PINTAR = "(function(b){ window.__hef.pintar({blocos: b}); return 'ok'; })(%s)"


def _medir(pagina: pathlib.Path) -> dict[str, Any]:
    from hefesto_dualsense4unix.interface import hefesto_vivo

    html = exp.modificacao_miolo_html("Brinquedo", OPCOES, mod=MOD, agora=AGORA,
                                      estado=_estado(), parar_tudo=True, ligas=LIGAS)
    tique = {"#mod-agora": exp.agora_html(AGORA, _estado(forca=0.65), ligas=LIGAS)}
    escolha = '.cx-escolha[value="Direita"]'
    passos: list[list[Any]] = [["js", hefesto_vivo.BOOTSTRAP],
              ["js", _ABRIR % (json.dumps(ENDERECO), json.dumps(html))], ["espera", 0.3],
              ["js", _LER],
              ["js", _CLICAR % json.dumps(".cx-escolhido")], ["espera", 0.1], ["js", _LER],
              ["js", _PINTAR % json.dumps(tique)], ["espera", 0.2], ["js", _LER],
              ["js", _CLICAR % json.dumps(escolha)], ["espera", 0.1], ["js", _LER]]
    lidos = no_webkit(pagina, {"1212x809": (1212, 809, passos)})["1212x809"]
    print(json.dumps(lidos, ensure_ascii=False))
    assert lidos[1] == "ok" and lidos[3] == "ok" and lidos[5] == "ok" and lidos[7] == "ok", lidos
    return {"antes": json.loads(lidos[2]), "aberta": json.loads(lidos[4]),
            "tique": json.loads(lidos[6]), "escolhida": json.loads(lidos[8])}


def test_no_webkit_a_coluna_cabe_e_o_adaptador_abre_e_fecha(
        pagina_fresca: pathlib.Path) -> None:  # noqa: F811
    m = _medir(pagina_fresca)
    antes = m["antes"]
    assert antes["linha"] and antes["botao"], antes
    assert not antes["aberta"] and antes["expandido"] == "false", "as escolhas nascem abertas"
    assert antes["nome"] == "Meio"
    meio = (antes["botao"]["y"] + antes["botao"]["b"]) / 2
    assert antes["linha"]["y"] <= meio <= antes["linha"]["b"], "o botão não está na linha"
    assert antes["botao"]["d"] <= antes["coluna"]["d"] + 1, "o botão sai da coluna"
    ativo = antes["aps"][0]
    assert [p["t"] for p in ativo["pares"]] == ["80%", "30%"], ativo
    for p in ativo["pares"]:
        assert ativo["ap"]["y"] <= p["p"]["y"] and p["p"]["b"] <= ativo["ap"]["b"], ativo
        assert p["p"]["d"] <= antes["coluna"]["d"] + 1, "o percentual sai da coluna"
    assert ativo["ap"]["h"] == 28, ativo
    assert antes["titulo"] and antes["faixa"], antes
    assert antes["faixa"]["y"] >= antes["titulo"]["b"], "o deslizante segue na linha do rótulo"
    assert m["aberta"]["aberta"] and m["aberta"]["expandido"] == "true", "o clique não abriu"
    assert m["tique"]["aberta"], "o tique que repinta a coluna fechou as escolhas"
    assert [p["t"] for p in m["tique"]["aps"][0]["pares"]] == ["80%", "65%"], m["tique"]
    assert not m["escolhida"]["aberta"], "a escolha feita não fechou as escolhas"
