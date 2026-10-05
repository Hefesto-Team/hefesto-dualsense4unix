"""Todo texto que abre uma linha começa com maiúscula — e o nome que ela dá também.

TODO-TEXTO-QUE-ABRE-UMA-LINHA-COMECA-COM-MAIUSCULA-01 (05/10/2026). A régua da primeira letra
(``test_todo_botao_da_tela_comeca_com_maiuscula.py``) só lia ``<button>``; a foto dela da aba 08
trazia «nenhum aparelho no ar», «fora da faixa dos controles», «a faixa dele ainda não foi
descoberta», «não se mede agora», «(lido)», «canal 161» e o nome «azul» do controle.

Esta lê, num WebKit, o PRIMEIRO texto de cada bloco visível (o ancestral mais perto que não é
``inline``), e os ``title``, ``aria-label``, ``placeholder`` e o valor dos campos de texto: as
dez abas e o Mapa como o gerador as escreve (``mockup/``), e a 08 também pintada pelo pacote,
caixa por caixa aberta. Exceções, só estas e declaradas: o que não começa por letra (número,
unidade, «·», «—», aspas), a unidade e a marca escritas assim (``_MARCAS``) e o glifo de uma
letra só (o «i» da informação no selo da aba Sistema).

O NOME: ordem dela de 05/10/2026, 13h — *«Nome que o user colocar pra controle mesmo se ele
colocar minúsculo o app corrige colocando a primeira letra maiúscula»*. Só a primeira letra; o
resto como ela escreveu; ao gravar e ao ler o que já estava gravado.
<!-- noqa-acento: citação literal dela -->

TUDO É DE MENTIRA: as páginas num WebKit fora da tela, com o pintor do piloto; o BlueZ e o
``maquina.json`` são dublês; nada chega a daemon nem ao aparelho.

AS MORDIDAS (feitas na sprint, uma de cada vez, com a cura devolvida e o md5 conferido): a
``NAO_DESCOBERTA`` de volta em minúscula reprova a 08 pintada; o «de» do ``aria-label`` do de→para
reprova a 08 parada; o ``title`` da fita da 06 curado sem tirar a pendência reprova a 06 (a
catraca); o ``nome_dado`` que devolve o nome como veio reprova as três réguas do nome.

A PENDÊNCIA DE FORA DA POSSE, numa catraca: a 06 tem UMA linha em minúscula (a dica da fita), e a
cura é uma letra em ``pacotes/a06_navegacao.py``, que três sprints abertas da aba Navegação
reivindicam. Ela fica em ``PENDENTES`` com a dona; a régua exige EXATAMENTE essa lista na página —
uma minúscula nova reprova, e a cura sem tirar a pendência também.
"""

from __future__ import annotations

import copy
import json
import re
from types import SimpleNamespace
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes.a08_conexoes`, que carrega o GTK")

from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08
from tests.unit.test_a_conexoes_cabe_na_tela import _clicar, _no_webkit

TAMANHO = (1512, 860)
ABAS = ("01-jogar", "02-controles", "03-gatilhos", "04-iluminacao", "05-vibracao",
        "06-navegacao", "07-lancadores", "08-conexoes", "09-sistema", "10-perfis",
        "mapa-das-portas")

LER = r"""(function(){
  const _MARCAS = /^(iPhone|iPad|iPod|iOS|macOS|dB|dBm|mA|ms|kHz|MHz|GHz)\b/;
  const FORA = new Set(['SCRIPT', 'STYLE', 'TEMPLATE', 'NOSCRIPT']);
  const visivel = e => {
    for (let x = e; x && x.nodeType === 1; x = x.parentElement) {
      if (FORA.has(x.tagName) || x.tagName.toLowerCase() === 'svg' || x.hidden) return false;
      const cs = getComputedStyle(x);
      if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    }
    const r = e.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const bloco = e => {
    for (let x = e; x; x = x.parentElement) {
      const d = getComputedStyle(x).display;
      if (d !== 'inline' && d !== 'contents') return x;
    }
    return document.body;
  };
  const minuscula = (t, el) => {
    t = (t || '').trim();
    if (t.length < 2 || !/\p{L}/u.test(t[0]) || _MARCAS.test(t)) return false;
    if (el && /uppercase|capitalize/.test(getComputedStyle(el).textTransform)) return false;
    return t[0] !== t[0].toUpperCase();
  };
  const onde = el => {
    const p = [];
    for (let x = el; x && x !== document.body && p.length < 3; x = x.parentElement)
      p.unshift(x.tagName.toLowerCase() + (typeof x.className === 'string' && x.className.trim()
        ? '.' + x.className.trim().split(/\s+/)[0] : ''));
    return p.join('>');
  };
  const primeiro = new Map();
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    if (!n.textContent.trim() || !n.parentElement || !visivel(n.parentElement)) continue;
    const b = bloco(n.parentElement);
    if (!primeiro.has(b)) primeiro.set(b, n);
  }
  const achados = [];
  for (const n of primeiro.values())
    if (minuscula(n.textContent, n.parentElement))
      achados.push('texto ' + onde(n.parentElement) + ': ' + n.textContent.trim().slice(0, 60));
  for (const el of document.querySelectorAll('[title],[aria-label],[placeholder],input')) {
    if (!visivel(el)) continue;
    for (const a of ['title', 'aria-label', 'placeholder']) {
      const v = el.getAttribute(a);
      if (minuscula(v, null)) achados.push(a + ' ' + onde(el) + ': ' + v.trim().slice(0, 60));
    }
    if (el.tagName === 'INPUT' && /^(text|search|)$/.test(el.type || '') && minuscula(el.value, el))
      achados.push('valor ' + onde(el) + ': ' + el.value.slice(0, 60));
  }
  return JSON.stringify({achados: [...new Set(achados)]});
})()"""

ABRIR_A_CAIXA = ("(function(){{const l=[...document.querySelectorAll('.lugar .abre-lugar')];"
                 "if(!l[{n}]) return 'sem caixa'; l[{n}].click(); return 'clicou';}})()")


#: o que ficou para a dona da página, com a razão: ``{aba: (achado, dona e cura)}``
PENDENTES: dict[str, tuple[str, str]] = {
    "06-navegacao": (  # sai com: TODO-TEXTO-QUE-ABRE-UMA-LINHA-COMECA-COM-MAIUSCULA-01
        "title div.fita-linha>div.fita>label.chip: a borda é a cor do plástico",
        "a dica da fita em pacotes/a06_navegacao.py, que as sprints abertas da aba Navegação "
        "reivindicam (A-ABA-NAVEGACAO-FAZ-O-QUE-DIZ-…); a cura é «A borda…» — 05/10/2026"),
}


def _achados(lidas: list[Any]) -> list[str]:
    return sorted({a for x in lidas if isinstance(x, dict) for a in x["achados"]})


# ───────────────────────── as páginas paradas ─────────────────────────


@pytest.mark.parametrize("aba", ABAS)
def test_a_pagina_parada_abre_toda_linha_com_maiuscula(aba: str) -> None:
    """A página como o gerador a escreve. O Mapa também nos três modos e com o painel aberto."""
    passos = [LER]
    if aba == "mapa-das-portas":
        passos += [_clicar('.modo[data-modo="ideal"]'), LER, _clicar('.modo[data-modo="mao"]'),
                   LER, _clicar(".ap-btn[data-ap-abre]"), LER]
    achados = _achados(_no_webkit(onde.BANCADA / f"{aba}.html", TAMANHO, passos))
    esperados = [PENDENTES[aba][0]] if aba in PENDENTES else []
    assert achados == esperados, f"{aba}: linha que abre em minúscula: {achados}"


# ───────────────────────── a 08 pintada pelo pacote ─────────────────────────


def _cenas() -> list[dict[str, Any]]:
    """A cena do desenho e uma com o que ela não mostra: quem espera, o receptor por descobrir,
    o Wi-Fi em 2,4 GHz que cai e o adaptador que não mede a faixa."""
    from hefesto_dualsense4unix.interface import aba08

    base = aba08.CENA_DO_RADIO
    outra = copy.deepcopy(base)
    lug = outra["lugares"][1]["id"]
    outra["aparelhos"].append({**outra["aparelhos"][0], "id": "aa:bb:cc:00:00:77",
                               "lugar": lug, "nome": "Verde", "esperando": True})
    outra["vizinhos"] = [*outra.get("vizinhos", []), {
        "id": "aaaa:bbbb", "tipo": "mouse", "nome": "Mouse", "sugestao": "", "sugestao_tipo": "",
        "no": "", "lido": "", "produto": "", "receptor": True, "banda": None, "saude": None}]
    outra["wifi"] = [{"no": "", "mhz": 2462, "largura": 20, "chave": "usb:2357:012d",
                      "quedas": {"n": 3, "min": 30}}]
    outra["canais_medidos"] = {**outra.get("canais_medidos", {}), lug: False}
    outra["evitados"] = [e for e in outra.get("evitados", []) if e["lugar"] != lug]
    return [base, outra]


def _pintar(campos: dict[str, Any]) -> str:
    textos = {k: v for k, v in campos.items() if isinstance(v, str)}
    return f"String(window.__hef.pintar({json.dumps({'mesa': textos})}))"


@pytest.mark.parametrize("qual", [0, 1], ids=["desenho", "o-resto"])
def test_a_08_pintada_pelo_pacote_abre_toda_linha_com_maiuscula(qual: str) -> None:
    cena = _cenas()[int(qual)]
    campos = a08.campos_da_secao(cena)
    passos = [_pintar(campos), _clicar('label[for="cx8-3"]'), LER]
    for n in range(len(cena["lugares"])):
        passos += [ABRIR_A_CAIXA.format(n=n), LER]
    passos += [_clicar('[data-gesto="aparelho-menu"]'), LER]
    achados = _achados(_no_webkit(onde.BANCADA / "08-conexoes.html", TAMANHO, passos))
    assert not achados, f"a 08 pintada abre linha em minúscula: {achados}"


def test_o_receptor_que_nao_achou_a_faixa_nao_fala_em_primeira_pessoa(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.integrations import receptor_sem_fio

    monkeypatch.setattr(a08, "_passo_da_linha", lambda _c: receptor_sem_fio.PASSO_NADA)
    html = a08.html_dos_canais(_cenas()[1])
    assert "Não achei" not in html and a08.FAIXA_NAO_ENCONTRADA in html


def test_o_que_fazer_da_dica_chama_a_ferramenta_pelo_nome_do_botao_e_sem_primeira_pessoa() -> None:
    """O «O que fazer» do porquê manda ao «Mapear entradas»: o nome que o botão da 08 tem desde
    05/10, e sem o app falar em primeira pessoa («Para eu dizer qual…»)."""
    from hefesto_dualsense4unix.integrations import ordens_da_mesa as ordens
    from hefesto_dualsense4unix.interface import aba08

    assert f"«{aba08.MAPEAR_ENTRADAS}»" in ordens.NAO_DECLARADO
    assert not re.search(r"\b(eu|me|meu|minha)\b", ordens.NAO_DECLARADO, re.I), ordens.NAO_DECLARADO


# ───────────────────────── o nome que ela dá ─────────────────────────


@pytest.mark.parametrize(("digitado", "gravado"), [
    ("vermelho", "Vermelho"), ("  azul ", "Azul"), ("vERDE", "VERDE"), ("ána", "Ána"),
    ("Roxo", "Roxo"), ("", ""), ("2º controle", "2º controle")])
def test_o_nome_ganha_so_a_primeira_letra_maiuscula(digitado: str, gravado: str) -> None:
    assert a08.nome_dado(digitado) == gravado


def test_renomear_o_controle_grava_com_a_primeira_maiuscula(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O campo do dono e o nome da linha: o `Alias` que vai ao BlueZ já sai «Vermelho»."""
    escritos: list[tuple[str, str]] = []
    monkeypatch.setattr(a08, "_alias_do_aparelho", lambda end, nome: escritos.append(
        (end, nome)) or SimpleNamespace(feita=True))
    monkeypatch.setattr(a08, "_nomes_dos_donos", dict)
    a08.dono_renomear(None, {"uniq": "aa:bb:cc:00:00:01", "valor": "vermelho"}, None)
    monkeypatch.setattr(a08, "_CENA_NA_TELA", {"aparelhos": [
        {"id": "aa:bb:cc:00:00:02", "tipo": "controle", "nome": ""},
        {"id": "aa:bb:cc:00:00:03", "tipo": "celular", "nome": ""}]})
    a08.aparelho_renomear(None, {"alvo": "aa:bb:cc:00:00:02", "valor": "azul"}, None)
    a08.aparelho_renomear(None, {"alvo": "aa:bb:cc:00:00:03", "valor": "iPhone"}, None)
    assert [n for _e, n in escritos] == ["Vermelho", "Azul", "iPhone"], escritos


def test_renomear_o_adaptador_grava_com_a_primeira_maiuscula(
        monkeypatch: pytest.MonkeyPatch) -> None:
    gravados: list[tuple[str, str]] = []
    monkeypatch.setattr(a08, "_gravar_o_nome", lambda end, nome: gravados.append(
        (end, nome)) or SimpleNamespace(gravou=True))
    monkeypatch.setattr(a08, "_CENA_NA_TELA", {"lugares": [{"id": "AABBCC000009", "nome": ""}]})
    a08.adaptador_renomear(None, {"alvo": "AABBCC000009", "valor": "esquerda"}, None)
    assert gravados == [("AABBCC000009", "Esquerda")]


def test_o_nome_gravado_em_minuscula_se_le_com_a_primeira_maiuscula(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O que já estava no BlueZ como «azul» aparece «Azul»; o celular fica como ela escreveu."""
    monkeypatch.setattr(a08, "_e_controle_do_bluez", lambda a: a.classe == 0x2508)
    lidos = (SimpleNamespace(nome="azul", endereco="AA:BB:CC:00:00:01", conectado=True,
                             classe=0x2508),
             SimpleNamespace(nome="iPhone de Ana", endereco="AA:BB:CC:00:00:02",
                             conectado=True, classe=0x5A020C))
    nomes = a08._nomes_por_endereco(lidos)
    assert nomes == {"AABBCC000001": "Azul", "AABBCC000002": "iPhone de Ana"}, nomes
