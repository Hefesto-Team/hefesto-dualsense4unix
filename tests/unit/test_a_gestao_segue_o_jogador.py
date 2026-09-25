"""A-GESTAO-SEGUE-O-JOGADOR-01 — o destaque da Gestão segue o jogador, e a 08 fala USB/BT.

A conferência da AS-FRASES-QUE-A-BANCADA-ACHOU-01 achou três coisas na prova da
tela, e este arquivo guarda as três.

1. **O DESTAQUE DA FITA SEGUIA A POSIÇÃO.** As regras que o `aba08.py` gera
   (`body:has(#gc-…:checked) .fita .chip…`) contavam filhos da fita, e a fita só
   desenha quem está na mesa. Medido no piloto, num lar de mentira, em 24/09:
   com o P1 fora, abrir o P2 acendia o P3; abrir o P3 não abria linha nenhuma
   nem acendia chip — o P3 e o P4 não tinham regra, porque o gerador só as
   escrevia para os dois conectados do desenho. A cura acha o chip pelo
   `data-pref`, o número do jogador (`monta._endereco_do_chip`), e escreve as
   regras dos QUATRO lugares.
2. **AS FRASES CABO/RÁDIO QUE SOBRARAM NA 08.** A palavra de tela do
   transporte é USB/BT (decisão dela de 21/09, a I9 revogada). A régua pergunta
   a palavra ao dono (`home_actions.palavra_do_transporte`) e nunca a digita: a
   régua de 06/09 que negava `"USB"` teria reprovado a decisão dela.
3. **OS TEXTOS QUE NEGAVAM O SOM PELO RÁDIO.** O som sai pelo `0x35` desde
   10/09, e a `PonteDeSomPorRadio` o escreve por controle.

POR QUE NUM WEBKIT DE VERDADE: quem decide qual chip acende é a cascata, com
`:has()` e `:checked`, e reimplementá-la em Python seria medir a reimplementação.
A pergunta vai ao `getComputedStyle` do mesmo WebKitGTK que a janela dela usa,
numa `Gtk.OffscreenWindow` (ela tem UMA tela).

A RÉGUA NÃO DIGITA A MESA: o estado do daemon passa pelos donos do produto —
`mesa_viva.mesa_do_estado` (quem é `p3`), `a08_conexoes._alvo_de_saida` (qual
rádio do acordeão marcar), `monta.fita` (os chips) — e chega à página pelo
pintor do piloto (`window.__hef.pintar`, o `BOOTSTRAP` lido do fonte). A lista do
daemon vem em ordem DECRESCENTE de número, para o índice nunca ser o número.

MORDIDAS (todas rodadas em 24/09/2026):

* devolva a regra por posição ao `aba08.py` (`n = 2 + i`, `.chip:nth-child(n)`,
  e `ESTADOS` dos `CONECTADOS`) e regere a 08: reprovam a régua no WebKit (com
  o P1 fora, o P2 aberto acende o P3) e a régua do texto da página;
* a mordida da posição também roda DENTRO da régua, na mesma ida ao motor
  (:func:`test_a_regua_morde_a_regra_por_posicao`): as regras da página saem e
  entram as de antes, e o mesmo roteiro tem de acusar;
* devolva «no rádio»/«no cabo» a uma frase da 08, ou a um dos donos que ela
  pinta, e o caso daquela frase reprova nomeando-a;
* devolva «não escreve no aparelho» ao cabeçalho do `alto_falante_bt.py` e o
  caso do cabeçalho reprova.
"""
from __future__ import annotations

import ast
import html
import itertools
import json
import pathlib
import re
import sys
from html.parser import HTMLParser
from typing import Any, ClassVar

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
# O `monta.py` importa os irmãos pelo nome curto (`import onde`), como o gerador
# roda: a pasta da interface entra no caminho junto com o `src/`.
for _pasta in (RAIZ / "src", RAIZ / "src/hefesto_dualsense4unix/interface"):
    if str(_pasta) not in sys.path:
        sys.path.insert(0, str(_pasta))

from hefesto_dualsense4unix.app.actions.home_actions import (
    palavra_do_transporte as palavra,
)

#: A BANCADA, e não o publicado: é onde o desenho de hoje está. Quem coordena
#: publica depois, e o publicado é cópia byte a byte dela.
BANCADA = RAIZ / "mockup/08-conexoes.html"
PILOTO = RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"
PAGINA = "08-conexoes.html"

#: Os quatro lugares da tela, na ordem dos `<input>` do acordeão.
LUGARES = ("p1", "p2", "p3", "p4")

#: O transporte de cada jogador nas cenas. Os dois aparecem, e o número NÃO
#: decide o transporte: o destaque não pode depender dele.
TRANSPORTE = {1: "usb", 2: "bt", 3: "bt", 4: "usb"}


# ---------------------------------------------------------------------------
# As cenas — toda mesa possível, e todo alvo de cada uma
# ---------------------------------------------------------------------------
def _estado(jogadores: tuple[int, ...], alvo: int | str) -> dict[str, Any]:
    """O `state_full` que o daemon publicaria, com o alvo de saída guardado.

    A lista vem em ordem DECRESCENTE de número: o `index` (a posição que o
    daemon guarda em `output_target_index`) nunca é o número menos um, e uma
    cura que confundisse os dois reprova aqui.
    """
    ordem = sorted(jogadores, reverse=True)
    controles = [
        {"uniq": f"aa:bb:cc:00:00:{n:02x}", "connected": True, "index": i,
         "is_primary": i == 0, "transport": TRANSPORTE[n], "player_slot": n}
        for i, n in enumerate(ordem)
    ]
    indice = None if alvo == "todos" else ordem.index(int(alvo))
    return {"controllers": controles, "output_target_index": indice}


def _cenas() -> list[dict[str, Any]]:
    """As 47 cenas: toda mesa não vazia dos quatro lugares, com cada alvo dela."""
    from hefesto_dualsense4unix.interface import mesa_viva, monta
    from hefesto_dualsense4unix.interface.pacotes import Contexto, a08_conexoes

    cenas: list[dict[str, Any]] = []
    for tamanho in range(1, len(LUGARES) + 1):
        for jogadores in itertools.combinations(range(1, len(LUGARES) + 1), tamanho):
            for alvo in ("todos", *jogadores):
                estado = _estado(jogadores, alvo)
                mesa = mesa_viva.mesa_do_estado(estado, {})
                ctx = Contexto(state=estado, mesa=mesa, conectados=estado["controllers"])
                presentes = sorted(str(c["pref"]) for c in mesa)
                fita = monta.fita(ativo=str(mesa[0]["pref"]),
                                  inerte=not monta.a_fita_escolhe(PAGINA),
                                  mesa=mesa, titulo=monta.casca_da_fita(PAGINA))
                if alvo == "todos":
                    acesos = ["todos"] if len(presentes) > 1 else presentes
                    abertas = presentes
                else:
                    acesos = abertas = [f"p{alvo}"]
                cenas.append({
                    "nome": f"mesa {'+'.join(presentes)}, aberto {alvo}",
                    "carga": {"fita": fita,
                              "mesa": {"alvo-aberto": a08_conexoes._alvo_de_saida(ctx)},
                              "vazios": sorted(set(LUGARES) - set(presentes)),
                              "ocupados": presentes},
                    "acesos": acesos,
                    "abertas": abertas,
                })
    return cenas


#: O ROTEIRO INTEIRO NUMA IDA SÓ ao motor. Ele abre o quadro da Gestão, pinta
#: cada cena com o pintor do piloto e lê o PESO computado de cada chip (o
#: destaque é `font-weight:600`) e a ALTURA computada de cada corpo do
#: acordeão (`0px` fechado, `40px` aberto). Depois troca as regras da fita
#: pelas de antes e roda as cenas da mordida.
ROTEIRO = r"""
(function(){
  const quadro = document.getElementById('cx8-1');
  if (quadro) { quadro.checked = true; }
  function ler(){
    const chips = [...document.querySelectorAll('.fita .chip')].map(function(el){
      return [el.getAttribute('data-pref'), getComputedStyle(el).fontWeight]; });
    const linhas = [...document.querySelectorAll('.gc-item')].map(function(el){
      const corpo = el.querySelector('.gc-corpo');
      return [el.getAttribute('data-controle'), corpo ? getComputedStyle(corpo).height : ''];
    });
    return {chips: chips, linhas: linhas};
  }
  function rodar(cenas){
    return cenas.map(function(c){ window.__hef.pintar(c.carga); return ler(); });
  }
  const fora = {cenas: rodar(CENAS_AQUI)};
  for (const folha of Array.from(document.styleSheets)) {
    let regras;
    try { regras = folha.cssRules; } catch (e) { continue; }
    for (let i = regras.length - 1; i >= 0; i--) {
      const s = regras[i].selectorText || '';
      if (s.indexOf('.fita') >= 0 && s.indexOf('#gc-') >= 0) { folha.deleteRule(i); }
    }
  }
  const velha = document.createElement('style');
  velha.textContent = VELHAS_AQUI;
  document.head.appendChild(velha);
  fora.mordida = rodar(MORDIDA_AQUI);
  return JSON.stringify(fora);
})()
"""


def _regras_por_posicao() -> str:
    """As regras da fita como o gerador as escrevia ATÉ esta sprint.

    É a cura ARRANCADA, escrita aqui para a mordida rodar em vez de morar num
    comentário: um estado por conectado do desenho (`todos`, `p1`, `p2`) e o
    chip achado pelo `:nth-child(2 + i)`.
    """
    fora = []
    for i, estado in enumerate(("todos", "p1", "p2")):
        fora.append(f"body:has(#gc-{estado}:checked) .fita .chip:nth-child({2 + i})"
                    "{background:var(--sel-bg);color:var(--fg);font-weight:600;"
                    "border-color:var(--purple)}")
    return "\n".join(fora)


def _bootstrap() -> str:
    """O BOOTSTRAP lido do FONTE do piloto — importar o piloto traria a janela."""
    achou = re.search(r'^BOOTSTRAP = r"""(.*?)"""$',
                      PILOTO.read_text(encoding="utf-8"), re.S | re.M)
    assert achou, "o piloto perdeu o BOOTSTRAP — não há o que testar"
    return achou.group(1)


def _confere(cena: dict[str, Any], lida: dict[str, Any]) -> str | None:
    """`None` se a tela acendeu e abriu o que a cena pede; senão, a queixa."""
    acesos = [p for p, peso in lida["chips"] if int(float(peso or 0)) >= 600]
    abertas = sorted(p for p, altura in lida["linhas"] if altura not in ("", "0px"))
    if acesos != cena["acesos"]:
        return f"{cena['nome']}: a fita acende {acesos}, e o aberto pede {cena['acesos']}"
    if abertas != sorted(cena["abertas"]):
        return (f"{cena['nome']}: o acordeão abre {abertas}, e o aberto pede "
                f"{sorted(cena['abertas'])}")
    return None


@pytest.fixture(scope="module")
def medido() -> dict[str, Any]:
    """Abre a bancada num WebKit offscreen, instala o pintor e roda as cenas."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("a Gestão da 08 no WebKit")
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    cenas = _cenas()
    # A MORDIDA: as duas cenas que a prova do piloto mediu, com as regras de antes.
    mordida = [c for c in cenas if c["nome"] in (
        "mesa p2+p3, aberto 2", "mesa p1+p2+p4, aberto 4")]
    assert len(mordida) == 2, "as cenas da mordida sumiram — a régua ficou cega"
    roteiro = (ROTEIRO.replace("CENAS_AQUI", json.dumps([{"carga": c["carga"]} for c in cenas]))
               .replace("MORDIDA_AQUI", json.dumps([{"carga": c["carga"]} for c in mordida]))
               .replace("VELHAS_AQUI", json.dumps(_regras_por_posicao())))
    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    view = WebKit2.WebView()
    view.set_size_request(1280, 900)
    janela.add(view)
    janela.show_all()

    def guardou(v: Any, res: Any) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:  # pragma: no cover — só quando o roteiro quebra
            saiu.append(f"ERRO {e}")
        Gtk.main_quit()

    def instalou(v: Any, res: Any) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:  # pragma: no cover — só quando o bootstrap quebra
            saiu.append(f"ERRO no bootstrap: {e}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(roteiro, -1, None, None, None, guardou)

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(_bootstrap(), -1, None, None, None, instalou)

    view.connect("load-changed", carregou)
    view.load_uri(BANCADA.as_uri())
    # O RELÓGIO DE SEGURANÇA É DESARMADO: um `timeout_add` pendente dispara no
    # laço do PRÓXIMO teste de GUI do mesmo processo (já matou medições vizinhas).
    guarda = GLib.timeout_add(60000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu, "o WebKit não respondeu em 60 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    lido = json.loads(saiu[0])
    return {"cenas": cenas, "lido": lido["cenas"], "mordida": mordida,
            "lido_na_mordida": lido["mordida"]}


# ---------------------------------------------------------------------------
# 1. O chip aceso é o do jogador aberto — em toda mesa, com qualquer lugar vazio
# ---------------------------------------------------------------------------
def test_o_chip_aceso_e_o_do_jogador_aberto_em_toda_mesa(medido: dict[str, Any]) -> None:
    """As 47 cenas: cada mesa não vazia dos quatro lugares, com cada alvo dela.

    Entre elas, as duas da prova do piloto: o P1 fora (P2 no USB, P3 no BT) e o
    P3 fora (P1, P2 e P4). Com UM controle só não há chip «Todos», e o dele é
    o todos (`monta.escolha_da_fita`).

    MORDIDA: devolva a regra por posição ao `aba08.py` e regere a 08 — reprova
    em «mesa p2+p3, aberto 2» com a fita acendendo o P3.
    """
    queixas = [q for c, lida in zip(medido["cenas"], medido["lido"], strict=True)
               if (q := _confere(c, lida))]
    assert not queixas, "\n".join(queixas)


#: O defeito como a prova do piloto o MEDIU em 24/09, na 08 publicada: com o P1
#: fora, o P2 aberto acendia o P3; com o P3 fora, o P4 aberto não acendia nada.
DEFEITO_MEDIDO = {"mesa p2+p3, aberto 2": ["p3"], "mesa p1+p2+p4, aberto 4": []}


def test_a_regua_morde_a_regra_por_posicao(medido: dict[str, Any]) -> None:
    """A cura arrancada, na mesma ida ao motor: com as regras de antes, as duas
    cenas da prova do piloto reproduzem O MESMO defeito que o piloto mediu — e
    não um defeito qualquer, que um pintor quebrado também daria. O acordeão
    continua certo (as regras dele ficam), e isso prova que a cena foi pintada."""
    for cena, lida in zip(medido["mordida"], medido["lido_na_mordida"], strict=True):
        acesos = [p for p, peso in lida["chips"] if int(float(peso or 0)) >= 600]
        assert acesos == DEFEITO_MEDIDO[cena["nome"]], (
            f"{cena['nome']}: com a regra por posição a fita acende {acesos}, e o "
            f"piloto mediu {DEFEITO_MEDIDO[cena['nome']]} — a régua não reproduz o defeito")
        abertas = sorted(p for p, altura in lida["linhas"] if altura not in ("", "0px"))
        assert abertas == cena["abertas"], (
            f"{cena['nome']}: o acordeão abriu {abertas} — a cena não foi pintada")
        assert _confere(cena, lida), f"{cena['nome']}: a conferência não acusou o defeito"


# ---------------------------------------------------------------------------
# 2. O texto da página: as regras são do jogador, e dos quatro
# ---------------------------------------------------------------------------
def _css_da_pagina() -> str:
    x = BANCADA.read_text(encoding="utf-8")
    return "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", x, flags=re.S))


def test_a_pagina_acha_o_chip_pelo_jogador_e_nunca_pela_posicao() -> None:
    """Sem WebKit também morde: a folha da 08 não conta filho da fita, e cada um
    dos cinco estados tem a regra do SEU chip e, cada lugar, a do seu corpo.

    MORDIDA: a mesma da régua do WebKit — reprova no primeiro `:nth-child`.
    """
    css = _css_da_pagina()
    posicao = re.search(r"\.fita \.chip[^{]*:nth-child", css)
    assert not posicao, f"a folha da 08 voltou a achar o chip pela posição: {posicao.group(0)!r}"
    for estado in ("todos", *LUGARES):
        assert f'body:has(#gc-{estado}:checked) .fita .chip[data-pref="{estado}"]' in css, (
            f"o estado {estado!r} não tem a regra do chip DELE")
    for lugar in LUGARES:
        assert f".quadro-corpo:has(#gc-{lugar}:checked) .gc-{lugar} .gc-corpo" in css, (
            f"o {lugar.upper()} não tem a regra que abre a linha dele — com ele na "
            f"mesa, abrir a linha não abriria nada")


# ---------------------------------------------------------------------------
# 3. A 08 fala USB/BT onde nomeia o transporte
# ---------------------------------------------------------------------------
#: As palavras da língua do MAPA (`cabo`/`rádio`), que a tela não diz como
#: transporte — menos a que o dono disser, se um dia ela voltar a ser a de tela.
_DO_MAPA = {"cabo", "rádio"} - {palavra("usb").lower(), palavra("bt").lower()}
_TRANSPORTE_NA_FRASE = re.compile(
    r"\b(?:no|na|pelo|pela|do|da|por|em)\s+(" + "|".join(sorted(_DO_MAPA)) + r")\b",
    re.I) if _DO_MAPA else None

#: ONDE O RÁDIO É O RECURSO, e não o transporte — a regra da sprint: «turno de
#: rádio» fica quando nomeia o custo. Cada uma com o dono dela.
O_RADIO_E_O_RECURSO = (
    "falando no rádio",   # o `?` do Check-up: quem mais fala na faixa (aba08)
    "pesa no rádio",      # «Barra de luz: não pesa no rádio» (a08_conexoes)
    "ruído no rádio",     # «Entrada USB 3.0: faz ruído no rádio» (a08_conexoes)
)

#: A FRASE QUE NÃO É DESTA SPRINT, e a razão é de POSSE: ela mora no
#: `topo.html`, o esqueleto das dez abas, e mudar uma palavra ali é regerar as
#: dez — com outras frentes nas abas delas. Está no «pendente» do relatório.
#: Não é tolerância: :func:`test_a_frase_de_fora_da_posse_continua_la` exige que
#: ela continue lá, então quem a curar tem de tirá-la daqui.
DE_OUTRA_POSSE = ("em outra porta ou no rádio",)


class _TextoDeTela(HTMLParser):
    """O que chega ao olho: texto e as quatro dicas, sem comentário, `<script>`,
    `<style>` e a legenda do mockup (`.nota`, que o produto esconde)."""

    ATRIBUTOS = ("title", "aria-label", "placeholder", "data-hef-dica")
    VAZIOS: ClassVar[frozenset[str]] = frozenset({
        "br", "img", "input", "meta", "link", "hr", "wbr", "source", "use",
        "path", "rect", "circle", "line", "polyline", "polygon", "ellipse", "stop"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pilha: list[tuple[str, bool]] = []
        self.frases: list[str] = []

    def _escondido(self) -> bool:
        return any(nota or tag in ("script", "style") for tag, nota in self.pilha)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        nota = "nota" in (dict(attrs).get("class") or "").split()
        if tag not in self.VAZIOS:
            self.pilha.append((tag, nota))
        if not self._escondido():
            self.frases += [html.unescape(v) for k, v in attrs if k in self.ATRIBUTOS and v]

    def handle_endtag(self, tag: str) -> None:
        while self.pilha:
            if self.pilha.pop()[0] == tag:
                break

    def handle_data(self, data: str) -> None:
        texto = " ".join(data.split())
        if texto and not self._escondido():
            self.frases.append(texto)


def _frases_da_pagina() -> list[str]:
    leitor = _TextoDeTela()
    leitor.feed(re.sub(r"<!--.*?-->", "", BANCADA.read_text(encoding="utf-8"), flags=re.S))
    assert len(leitor.frases) > 500, "a 08 gerada perdeu o texto — a régua ficou cega"
    return leitor.frases


def _transporte_na_lingua_do_mapa(frase: str) -> list[str]:
    """Os trechos em que a frase nomeia o transporte com a palavra do mapa."""
    if _TRANSPORTE_NA_FRASE is None:
        return []
    baixa = frase.lower()
    fora = []
    for m in _TRANSPORTE_NA_FRASE.finditer(frase):
        janela = baixa[max(0, m.start() - 12):m.end()]
        if any(r in janela for r in O_RADIO_E_O_RECURSO):
            continue
        if any(d in baixa for d in DE_OUTRA_POSSE):
            continue
        fora.append(m.group(0))
    return fora


def test_a_pagina_nao_nomeia_o_transporte_na_lingua_do_mapa() -> None:
    """Toda frase de tela da 08 gerada — texto, `title`, `aria-label` — diz o
    transporte com a palavra do dono.

    MORDIDA: devolva *"Só funciona com o controle no rádio"* ao
    `aba08.LUZ_NO_CABO` e regere a 08 — reprova nomeando a frase.
    """
    achados = [f"{trechos} em {frase[:110]!r}" for frase in _frases_da_pagina()
               if (trechos := _transporte_na_lingua_do_mapa(frase))]
    assert not achados, "a 08 ainda nomeia o transporte na língua do mapa:\n" + "\n".join(achados)


def test_a_frase_de_fora_da_posse_continua_la() -> None:
    """A exceção de posse só vale enquanto a frase existe: curada, ela sai daqui."""
    texto = " ".join(_frases_da_pagina()).lower()
    for frase in DE_OUTRA_POSSE:
        assert frase in texto, (
            f"«{frase}» saiu da 08 — tire-a de `DE_OUTRA_POSSE`, que ela não "
            f"precisa mais de exceção")


def test_a_linha_do_radio_diz_a_palavra_do_dono() -> None:
    """«Pelo BT, som ou vibração, um por vez» — a linha de cada controle na
    seção do rádio, como a página a mostra.

    MORDIDA: devolva «Pelo rádio» ao `a08_conexoes._linha_do_controle` e regere
    a 08 — reprova.
    """
    alvo = f"Pelo {palavra('bt')}, som ou vibração, um por vez."
    assert any(alvo in f for f in _frases_da_pagina()), (
        f"nenhuma linha da seção do rádio diz {alvo!r}")


@pytest.fixture(scope="module")
def a08() -> Any:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("os donos das dicas da 08 (`secao_controles`)")
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


@pytest.mark.parametrize("via", ["usb", "bt"])
def test_a_dica_da_luz_que_a_08_pinta_fala_usb_e_bt(a08: Any, via: str) -> None:
    """O `title` do «A luz não acende» é repintado a cada tique pelo dono
    (`secao_controles.dica_do_botao`), por cima do que o desenho escreveu.

    MORDIDA: devolva *"Só vale no rádio. Pelo cabo…"* ao
    `secao_controles.DICA_NO_CABO` — reprova no USB.
    """
    dica = a08.dica_da_luz(via)
    assert palavra("bt") in dica, (
        f"a dica da luz no {palavra(via)} não diz {palavra('bt')!r}: {dica!r}")
    assert not _transporte_na_lingua_do_mapa(dica), (
        f"a dica da luz no {palavra(via)} voltou à língua do mapa: {dica!r}")


def test_a_dica_do_microfone_no_bt_conta_o_custo_na_palavra_do_dono(a08: Any) -> None:
    """A metade do custo vem de `secao_controles.frase_da_capacidade_do_mic`.

    MORDIDA: devolva *"um controle no rádio troca"* à frase — reprova.
    """
    dica = html.unescape(a08.dica_do_microfone("bt"))
    assert "relatórios de entrada por segundo" in dica, (
        f"a dica do microfone no BT perdeu a frase do custo — a régua ficou cega: {dica!r}")
    assert f"um controle no {palavra('bt')} troca" in dica, dica
    assert not _transporte_na_lingua_do_mapa(dica), dica


def test_o_exame_diz_o_pareamento_na_palavra_do_dono() -> None:
    """«Nenhum controle pareado por BT» — o `?` de uma linha do Check-up.

    MORDIDA: devolva «pareado por rádio» ao `exame_da_mesa.pareamentos` —
    reprova.
    """
    from hefesto_dualsense4unix.integrations.exame_da_mesa import pareamentos

    def busctl(argv: list[str]) -> str:
        return "/\n/org\n/org/bluez\n"

    item = pareamentos(executar=busctl)
    assert f"pareado por {palavra('bt')}" in item.porque, item.porque
    assert not _transporte_na_lingua_do_mapa(item.porque), item.porque


# ---------------------------------------------------------------------------
# 4. O som sai pelo rádio desde 10/09 — e os dois cabeçalhos dizem isso
# ---------------------------------------------------------------------------
_CABECALHOS = (
    "src/hefesto_dualsense4unix/integrations/alto_falante_bt.py",
    "src/hefesto_dualsense4unix/daemon/subsystems/alto_falante.py",
)

#: O que os cabeçalhos diziam antes de 10/09 e deixou de ser verdade. Minúsculas.
_O_QUE_NEGAVA = (
    "não escreve no aparelho.**",
    "quem escreve é o ensaio",
    "mandou um byte de áudio por rádio",
    "não escreve um byte no aparelho",
)


@pytest.mark.parametrize("relativo", _CABECALHOS)
def test_o_cabecalho_nao_nega_o_som_pelo_radio(relativo: str) -> None:
    """O cabeçalho diz quem escreve o `0x35` e não nega que ele toque.

    MORDIDA: devolva *"**não escreve no aparelho.** Ele MONTA bytes; quem
    escreve é o ensaio"* ao cabeçalho do `alto_falante_bt.py` — reprova.
    """
    doc = ast.get_docstring(ast.parse((RAIZ / relativo).read_text(encoding="utf-8"))) or ""
    baixa = doc.lower()
    negou = [f for f in _O_QUE_NEGAVA if f in baixa]
    assert not negou, f"o cabeçalho de {relativo} ainda nega o som pelo rádio: {negou}"
    assert "PonteDeSomPorRadio" in doc and "0x35" in doc, (
        f"o cabeçalho de {relativo} não diz quem escreve o som no rádio, nem o degrau")
