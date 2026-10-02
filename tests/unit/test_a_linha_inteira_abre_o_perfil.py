"""A linha inteira abre o perfil, e a coluna se chama «Preferência».

A-LINHA-INTEIRA-ABRE-O-PERFIL-01 (02/10/2026). O pedido dela de 29/09: clicar
em qualquer célula de uma linha da lista «Perfis salvos» abre aquele perfil no
editor, e a coluna «Prioridade» passa a se chamar «Preferência» (a resposta 41
dela: o rótulo do editor muda junto).

O DEFEITO, MEDIDO: o gesto `selecionar` morava no `<td>` do nome. O ouvinte do
piloto sobe da célula clicada pelo `closest` do seletor dele; da «Prioridade» e
do «Funciona em» ele não achava gesto nenhum, e o clique não fazia nada, com o
cursor de mão na linha inteira. E com a coluna no piso de 48 px que ela gravou,
o cabeçalho saía «Pri…».

AS RÉGUAS (a sprint as numera):

1. toda célula leva ao perfil da linha (WebKit, o seletor LIDO do piloto);
2. o gesto escolhe pelo nome da linha (`hefPerfil`), não pelo texto colado;
3. o rótulo cabe na largura dela (`prioridade:48`);
4. uma palavra só: a página, o pacote, os desfechos e o relatório da sanidade.

AS MORDIDAS (medidas na entrega): o gesto de volta ao `<td>` do nome (a 1
reprova nomeando a coluna); o `selecionar` lendo só o `texto` (a 2); o `PISO`
fixo de volta no roteiro (a 3 mostra o 80 contra o 48); o «Prioridade:» de volta
ao rótulo do editor, e à parte o «· prioridade N» do desfecho (a 4).
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real
from tests.unit.ponte_do_rodape import PonteDoRodape

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import loader, sanidade
from hefesto_dualsense4unix.profiles.schema import Profile

RAIZ = pathlib.Path(__file__).resolve().parents[2]

#: A PALAVRA QUE SAI DA TELA, em qualquer caixa.
VELHA = re.compile(r"prioridade", re.IGNORECASE)


def _seletor_do_ouvinte() -> str:
    """O seletor do `closest` do ouvinte do piloto, LIDO do fonte e nunca digitado."""
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py").read_text(
        encoding="utf-8")
    corpo = fonte[fonte.index("function manda_do_alvo(ev)"):]
    achado = re.search(r"ev\.target\.closest\(\s*((?:'[^']*'\s*\+?\s*)+)\)", corpo)
    assert achado is not None, "o ouvinte do piloto mudou de forma"
    return "".join(re.findall(r"'([^']*)'", achado.group(1)))


class _Visivel(HTMLParser):
    """O texto e as dicas de um pedaço de HTML: o que chega aos olhos dela."""

    ATRIBUTOS = ("title", "aria-label", "placeholder", "data-hef-dica")

    def __init__(self) -> None:
        super().__init__()
        self.pedacos: list[str] = []
        self._fora = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._fora += 1
        for nome, valor in attrs:
            if nome in self.ATRIBUTOS and valor:
                self.pedacos.append(valor)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._fora:
            self._fora -= 1

    def handle_data(self, data: str) -> None:
        if not self._fora and data.strip():
            self.pedacos.append(data.strip())


def _o_que_se_ve(valor: Any) -> list[str]:
    """Toda string de uma carga do pacote, lida como tela (HTML ou texto)."""
    if isinstance(valor, dict):
        return [s for v in valor.values() for s in _o_que_se_ve(v)]
    if isinstance(valor, (list, tuple)):
        return [s for v in valor for s in _o_que_se_ve(v)]
    if not isinstance(valor, str):
        return []
    leitor = _Visivel()
    leitor.feed(valor)
    return leitor.pedacos


# --------------------------------------------------------------------------
# o disco do lar de mentira
# --------------------------------------------------------------------------
PERFIS = [("Mortal Kombat", 90, "steam_app_1971870"), ("Pragmata", 80, "steam_app_3357650"),
          ("Desktop", 0, None)]


@pytest.fixture()
def disco(monkeypatch: pytest.MonkeyPatch) -> None:
    for nome, prioridade, janela in PERFIS:
        regra: dict[str, Any] = ({"type": "criteria", "window_class": [janela]}
                                 if janela else {"type": "any"})
        loader.save_profile(Profile.model_validate(
            {"name": nome, "match": regra, "priority": prioridade}), origem="teste")
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_PROCURA", "", raising=False)


def _ctx() -> Contexto:
    return Contexto(state={"active_profile": "Desktop", "controllers": []},
                    mesa=[], conectados=[], estados={})


# --------------------------------------------------------------------------
# 2. o gesto escolhe pelo nome da linha
# --------------------------------------------------------------------------
def test_o_gesto_escolhe_pelo_nome_da_linha(monkeypatch: pytest.MonkeyPatch) -> None:
    """O clique na `<tr>` traz o nome no `hefPerfil`; o `texto` é a linha colada."""
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    a10_perfis.selecionar(_ctx(), {"hefPerfil": "Pragmata",
                                   "texto": "Pragmata80Steam · Pragmata · 3357650"}, None)
    assert a10_perfis._ESCOLHIDO == "Pragmata", (
        f"o gesto abriu {a10_perfis._ESCOLHIDO!r}, e a linha é a do Pragmata")


def test_o_texto_segue_valendo_sem_o_atributo(monkeypatch: pytest.MonkeyPatch) -> None:
    """As réguas antigas chamam o gesto com `{"texto": nome}`: elas seguem valendo."""
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    a10_perfis.selecionar(_ctx(), {"texto": "Mortal Kombat"}, None)
    assert a10_perfis._ESCOLHIDO == "Mortal Kombat"


def test_as_duas_fontes_da_linha_poem_o_gesto_na_tr() -> None:
    """O gerador e o pacote emitem a mesma linha, com o gesto na `<tr>`."""
    linha = a10_perfis._linha_da_lista("Pragmata", "80", "Steam · Pragmata", False)
    abre = re.match(r"\s*<tr ([^>]*)>", linha)
    assert abre is not None and 'data-hef-gesto="selecionar"' in abre.group(1), linha
    assert linha.count('data-hef-gesto="selecionar"') == 1, linha


# --------------------------------------------------------------------------
# 4. uma palavra só — o que não precisa de tela
# --------------------------------------------------------------------------
def test_o_pacote_da_aba_nao_diz_a_palavra_velha(disco: None) -> None:
    """A carga inteira da aba, lida como tela (texto e dicas)."""
    vistos = [s for s in _o_que_se_ve(a10_perfis.pacote(_ctx())) if VELHA.search(s)]
    assert not vistos, f"o pacote da aba Perfis ainda diz a palavra velha: {vistos}"


def test_os_desfechos_dizem_preferencia(
    disco: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O Salvar do número, a recusa dele, o «Novo» e o «ordenar» da coluna."""
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "Pragmata", raising=False)
    monkeypatch.setattr(a10_perfis, "_com_a_carona", lambda frase="": frase,
                        raising=False)
    frases: list[str] = []
    bom = a10_perfis.editor_prioridade(
        _ctx(), {"valor": "55", "evento": "change", "tipo": "range"}, PonteDoRodape())
    assert bom is not None
    frases.append(str(bom.get("relato") or ""))
    for cru in ("999", "abc"):
        with pytest.raises(RuntimeError) as erro:
            a10_perfis.editor_prioridade(
                _ctx(), {"valor": cru, "evento": "change", "tipo": "range"},
                PonteDoRodape())
        frases.append(str(erro.value))
    frases.append(str(a10_perfis.novo(_ctx(), {}, PonteDoRodape())))
    anotadas: list[str] = []
    monkeypatch.setattr(a10_perfis, "_anotar", anotadas.append)
    a10_perfis.ordenar(_ctx(), {"coluna": "prioridade"}, None)
    frases += anotadas
    assert all(frases), frases
    velhas = [f for f in frases if VELHA.search(f)]
    assert not velhas, f"os desfechos ainda dizem a palavra velha: {velhas}"
    assert any("Preferência" in f or "preferência" in f for f in frases), frases


def test_o_relatorio_da_sanidade_diz_preferencia(tmp_path: Path) -> None:
    """Os achados que falam do número: o catch-all que vence, o empate, a faixa."""
    from hefesto_dualsense4unix.profiles.schema import MatchAny, MatchCriteria

    perfis = [
        Profile(name="vitoria", match=MatchAny(), priority=100),
        Profile(name="pragmata", match=MatchCriteria(window_class=["p"]), priority=100),
        Profile(name="outro", match=MatchCriteria(window_class=["p"]), priority=100),
        Profile(name="fora", match=MatchCriteria(window_class=["f"]), priority=250),
        Profile(name="sobra1", match=MatchAny(), priority=5),
        Profile(name="sobra2", match=MatchAny(), priority=6),
    ]
    achados = sanidade.verificar_perfis(perfis)
    regras = {a.regra for a in achados}
    assert {"catch_all_vence_especifico", "prioridades_empatadas",
            "prioridade_fora_da_faixa", "catch_all_com_cara_de_jogo",
            "catch_all_demais"} <= regras, regras
    velhas = [f"{a.regra}: {texto}" for a in achados
              for texto in (a.mensagem, a.cura) if VELHA.search(texto)]
    assert not velhas, "o relatório da aba Sistema ainda diz:\n  " + "\n  ".join(velhas)


# --------------------------------------------------------------------------
# 1, 3 e 4 na tela — o WebKit, sob `xvfb-run -a`
# --------------------------------------------------------------------------
LER_AS_CELULAS = r"""
(function(seletor){
  var fora = [];
  document.querySelectorAll('tbody[data-hef="perfis.lista"] tr').forEach(function(tr){
    var nome = tr.querySelector('td[data-hef="perfis.linha.nome"]');
    tr.querySelectorAll('td').forEach(function(td){
      var alvo = td.closest(seletor);
      fora.push({coluna: td.getAttribute('data-hef') || td.className,
                 nome: nome ? nome.textContent : null,
                 gesto: alvo ? (alvo.dataset.hefGesto || '') : null,
                 perfil: alvo ? (alvo.dataset.hefPerfil || '') : null});
    });
  });
  return JSON.stringify(fora);
})(%s)
"""

LER_O_CABECALHO = r"""
(function(){
  var th = document.querySelector('th[data-coluna="prioridade"]');
  return JSON.stringify({texto: th ? th.firstChild.textContent : null,
                         scroll: th ? th.scrollWidth : null,
                         client: th ? th.clientWidth : null});
})()
"""

LER_O_QUE_SE_VE = r"""
(function(){
  var miolo = document.querySelector('.miolo');
  var fora = [miolo ? miolo.innerText : ''];
  miolo.querySelectorAll('[title],[aria-label],[placeholder],[data-hef-dica]').forEach(
    function(el){
      ['title','aria-label','placeholder','data-hef-dica'].forEach(function(a){
        var v = el.getAttribute(a); if(v){ fora.push(v); }
      });
    });
  return JSON.stringify(fora);
})()
"""


@pytest.fixture(scope="module")
def tela() -> Any:
    """A página do gerador num WebView oculto, com a folha do produto."""
    if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
        pytest.skip("sem servidor gráfico: rode sob `xvfb-run -a` (pulo não é verde)")
    sys.path.insert(0, str(RAIZ / "scripts"))
    import regua_de_tela

    from hefesto_dualsense4unix.gui.ponte_da_tela import FOLHA_DA_CASA

    t = regua_de_tela.Tela(onde.BANCADA / "10-perfis.html", titulo_esperado="Hefesto",
                           largura=1280, altura=900)
    t.executar(
        "(function(){var s=document.createElement('style');"
        f"s.textContent={json.dumps(FOLHA_DA_CASA)};"
        "document.head.appendChild(s);return 'ok';})()")
    yield t
    t.fechar()


def _celulas(tela: Any) -> list[dict[str, Any]]:
    return json.loads(tela.executar(LER_AS_CELULAS % json.dumps(_seletor_do_ouvinte())))


def _quebradas(celulas: list[dict[str, Any]]) -> list[str]:
    return [f"{c['coluna']} da linha {c['nome']!r}: gesto={c['gesto']!r} perfil={c['perfil']!r}"
            for c in celulas
            if c["gesto"] != "selecionar" or c["perfil"] != c["nome"]]


def test_toda_celula_do_desenho_leva_ao_perfil_da_linha(tela: Any) -> None:
    """A página do gerador, como ela abre: cada célula sobe até a linha."""
    celulas = _celulas(tela)
    assert len(celulas) >= 9, f"a lista do desenho tem {len(celulas)} células"
    assert not _quebradas(celulas), "\n".join(_quebradas(celulas))


def test_toda_celula_do_pacote_leva_ao_perfil_da_linha(tela: Any) -> None:
    """O `<tbody>` que o pacote pinta a cada tique, posto como o `blocos` o põe."""
    lista = [{"nome": n, "prioridade": str(p), "quando": f"Steam · {n}",
              "ativo": n == "Desktop", "dica": ""} for n, p, _j in PERFIS]
    html = a10_perfis._html_da_lista(lista, "", "Pragmata")
    tela.executar(
        f"(function(){{document.querySelector({json.dumps(a10_perfis.SELETOR_DA_LISTA)})"
        f".innerHTML={json.dumps(html)};return 'ok';}})()")
    celulas = _celulas(tela)
    assert len(celulas) == 3 * len(PERFIS), celulas
    assert not _quebradas(celulas), "\n".join(_quebradas(celulas))


def test_o_rotulo_cabe_na_largura_que_ela_gravou(tela: Any) -> None:
    """`prioridade:48`, a forma que o pacote escreve: o cabeçalho sai inteiro."""
    tela.executar(
        "(function(){var t=document.querySelector('table[data-tabela]');"
        "t.setAttribute('data-larguras','nome:380·prioridade:48');return 'ok';})()")
    tela.avancar(0.3)
    medida = json.loads(tela.executar(LER_O_CABECALHO))
    assert medida["texto"] == "Preferência", medida
    assert medida["scroll"] <= medida["client"], (
        f"o rótulo foi cortado: pede {medida['scroll']} px numa coluna de "
        f"{medida['client']}")


def test_a_pagina_nao_diz_a_palavra_velha(tela: Any) -> None:
    """O texto visível e as dicas do miolo da página do gerador."""
    vistos = [s for s in json.loads(tela.executar(LER_O_QUE_SE_VE)) if VELHA.search(s)]
    assert not vistos, f"a página da aba Perfis ainda diz: {vistos}"
