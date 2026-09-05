#!/usr/bin/env python3
"""A ABA 01 VESTE O CONTROLE DE PONTA A PONTA — do daemon ao pixel.

A LEI, e ela é dela (03/09/2026):

    "imagina que cada pessoa tenha um dualsense diferente. eu mapeei as cores,
    glifos, controles, id e tudo mais. é pro projeto usar esse meu trabalho
    entende? nada hardcoded. eu quero que cada user ao usar seu controle se
    toque disso que o app se adaptou ao controle dele"   (noqa-acento: dela)

O QUE ESTA RÉGUA MEDE, E POR QUE ELA NÃO É A TERCEIRA CÓPIA DE NADA
--------------------------------------------------------------------
A cura de 03/09 (`c95737d1`) tem TRÊS elos, e cada um já tem a sua régua:

    daemon → `a01_jogar.pacote`      `test_a_aba01_veste_a_cor_do_controle`
    `escrever(alvo=atributo)`        — NINGUÉM
    folha das 28 → pixel             `test_o_desenho_da_aba01_veste_o_controle_lido`

**O elo do meio não tinha régua nenhuma**, e é o mais novo dos três: o alvo
`atributo` nasceu em 03/09/2026, noutra frente, e chegou aqui por merge. A régua
do motor que já existe escreve o `data-colorway` com um `setAttribute` do
PRÓPRIO roteiro — ela prova a folha, e passaria intacta se o `escrever()` do
piloto escrevesse o atributo errado, recusasse o nome, ou nunca chegasse ao SVG.
A régua do pacote prova o slug, e passaria intacta se ele nunca fosse pintado.

Esta abre a bancada num WebKit, injeta o **`BOOTSTRAP` do piloto de verdade**
(`hefesto_vivo.BOOTSTRAP`, o mesmo texto que a janela dela executa), monta a
carga com o **pacote de verdade** (`a01_jogar.pacote` + `pacotes.normalizar`) e
chama `window.__hef.pintar`. Depois LÊ o `fill` computado do chassi. Nenhum elo
é imitado: o que se mede é a corrente inteira.

E ELA USA OS VINTE E QUATRO MODELOS QUE O MOCKUP **NÃO** TEM
-------------------------------------------------------------
O desenho traz quatro (`monta.MESA`: Cosmic Red, Starlight Blue, Galactic
Purple, White). Uma cura que só funcionasse para esses quatro seria um cravado
trocado por outro — e passaria numa régua que testasse a mesa do mockup. Aqui a
mesa é FORÇADA, um modelo por vez, aos 24 que sobram: Nova Pink, Astro Bot,
Sterling Silver, os camuflados que pintam com `<pattern>` e os dois que pintam
com `<linearGradient>`.

AS MORDIDAS QUE ELA SOFRE (medidas em 03/09/2026, uma a uma)
-------------------------------------------------------------
* devolver a poda da folha ao `aba01._desenho` — 24 dos 24 no cinza cru;
* tirar o `data-hef-atributo` do `<svg>` — o alvo não sabe o que escrever e
  `atributo_escrevivel('')` recusa: 24 ficam no Cosmic Red do mockup;
* trocar o alvo por `texto` — o piloto escreve o slug POR CIMA do desenho;
* o pacote devolver o slug do desenho em vez do lido — o P1 fica Cosmic Red.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# O import do PACOTE põe `interface/` no `sys.path` (`pacotes/__init__` faz o
# `insert`), e é o que deixa `import monta` funcionar logo abaixo.
from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a01_jogar

import hefesto_vivo
import monta

#: A BANCADA, e não o publicado. É onde `aba01.py` escreve, e é o desenho de
#: HOJE — apontar para `paginas/` daria verde sobre a página congelada, que é a
#: armadilha mais cara do `COMO-OLHAR-A-TELA.md`.
BANCADA = RAIZ / "mockup/01-jogar.html"

#: O `fill` cru do `ds_limpo.svg` — o que o chassi mostra quando regra nenhuma
#: casa. Lido do desenho, no mesmo `<g class="z-casca">` que a folha pinta;
#: digitá-lo aqui seria a segunda verdade que esta casa persegue.
CRU = re.compile(r'<g id="jg-p1-corpo" class="z-casca"[^>]*>\s*'
                 r'(?:<title>[^<]*</title>\s*)?<path[^>]*fill="(#[0-9a-fA-F]{6})"')

#: O `uniq` do controle forçado. Mascarado pela regra da casa (octetos 4 e 5
#: zerados), como todo endereço de rádio em arquivo versionado.
UNIQ = "aa:bb:cc:00:00:01"


def _modelos_do_mapa() -> list[str]:
    """Os 28 do mapa dela, lidos da folha que o gerador de cores escreveu."""
    return sorted(set(re.findall(r'svg\[data-colorway="([^"]+)"\]', monta.DS)))


def _fora_do_mockup() -> list[str]:
    """Os modelos que o desenho NÃO traz — os 24 que provam a lei.

    A lista do mockup sai de `monta.MESA`, que é o dono dela: digitar os quatro
    aqui faria esta régua envelhecer no dia em que ela trocar um controle de
    lugar na bancada.
    """
    do_mockup = {str(c["cor"]) for c in monta.MESA}
    return [m for m in _modelos_do_mapa() if m not in do_mockup]


def _carga(slug: str) -> dict[str, Any]:
    """A carga que o piloto pintaria com ESTE modelo no cabo do P1.

    Ela atravessa o caminho inteiro do produto: `a01_jogar.pacote` monta,
    `pacotes.normalizar` traduz `uniq → pref` e achata para `{mesa, colunas}`,
    e `apagar_os_lugares_sem_dono` marca os três lugares que sobram. É a MESMA
    sequência de `hefesto_vivo`, e nenhuma linha dela é imitada aqui.
    """
    cru = {"uniq": UNIQ, "connected": True, "player_slot": 1,
           "transport": "usb", "battery_pct": 95}
    da_mesa = {"uniq": UNIQ, "pref": "p1", "jogador": 1,
               "nome": slug, "cor": slug, "via": "USB"}
    ctx = Contexto(state={"controllers": [cru]}, mesa=[da_mesa],
                   conectados=[cru], estados={})
    carga = pacotes.normalizar(a01_jogar.pacote(ctx), {UNIQ: "p1"})
    return dict(pacotes.apagar_os_lugares_sem_dono(carga))


#: O ROTEIRO, e ele vai numa IDA SÓ. Uma carga por modelo custaria 24 aberturas
#: de página para medir o que uma abertura mede — e a régua irmã já pagou essa
#: lição.
#:
#: `__hef.pintar` é o do piloto: o roteiro não escreve atributo nenhum por conta
#: própria, e é exatamente isso que faz esta régua medir o elo do meio.
ROTEIRO = """
(function(){
  const svg = document.querySelector('[data-controle="p1"] svg[data-campo="desenho"]');
  if(!svg) return JSON.stringify({erro: 'não achei o desenho do p1'});
  const casca = svg.querySelector('.z-casca path:not([fill="none"])');
  if(!casca) return JSON.stringify({erro: 'não achei o chassi do desenho'});
  const pele = document.querySelector('[data-controle="p1"] [data-campo="plastico"]');
  if(!pele) return JSON.stringify({erro: 'não achei a pele do cartão do p1'});
  const fora = {chassi: {}, pele: {}, colorway: {}, pintou: {}};
  for(const [slug, carga] of CARGAS){
    fora.pintou[slug] = window.__hef.pintar(carga);
    fora.chassi[slug] = getComputedStyle(casca).fill;
    fora.pele[slug] = getComputedStyle(pele).color;
    fora.colorway[slug] = svg.getAttribute('data-colorway');
  }
  return JSON.stringify(fora);
})()
"""


def _no_webkit(roteiro: str) -> dict[str, Any]:
    """Abre a bancada num WebKit offscreen, com o BOOTSTRAP do piloto dentro.

    `Gtk.OffscreenWindow` e não `Gtk.Window`: sob Xvfb não há gerenciador de
    janelas e uma janela comum fica 1x1 para sempre. E offscreen também porque
    ela tem UMA tela — janela de teste não nasce na frente dela.
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

    def guardou(v: Any, res: Any) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:  # pragma: no cover — só quando o roteiro quebra
            saiu.append(f"ERRO {e}")
        Gtk.main_quit()

    def bootou(v: Any, res: Any) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:  # pragma: no cover
            saiu.append(f"ERRO no BOOTSTRAP: {e}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(roteiro, -1, None, None, None, guardou)

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            # O BOOTSTRAP É O DO PILOTO, lido do módulo — nunca copiado. Uma
            # cópia aqui viraria a segunda verdade sobre o `escrever()`, e esta
            # régua ficaria verde no dia em que o piloto mudasse de forma.
            v.evaluate_javascript(hefesto_vivo.BOOTSTRAP, -1, None, None, None,
                                  bootou)

    view.connect("load-changed", carregou)
    view.load_uri(BANCADA.as_uri())
    # O `timeout_add` PENDENTE DISPARA NO LAÇO DO PRÓXIMO TESTE de GUI do
    # mesmo processo — 05/09/2026, e a cura já existia em cinco arquivos
    # irmãos (*"Já matou onze medições"*). Aqui ela faltava: medido no
    # lote-00 da suíte, DUAS voltas em três davam *"o WebKit não respondeu
    # em 30 s"* com o `saiu` VAZIO — o laço não estourou, ele foi MORTO por
    # um `main_quit` que outro teste deixou armado. Reprodutível só na
    # ordem aleatória, que é o que o torna invisível quando se roda o
    # arquivo sozinho.
    guarda = GLib.timeout_add(30000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu, "o WebKit não respondeu em 30 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return dict(json.loads(saiu[0]))


def _rgb(hexa: str) -> str:
    """`#e35b8c` → `rgb(227, 91, 140)`, a forma em que o WebKit devolve a cor."""
    h = hexa.lstrip("#")
    return f"rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})"


def _como_o_motor_diz(valor: str) -> str:
    """O que o WebKit devolve para o valor que a folha dela escreveu.

    SEIS DOS 28 NÃO SÃO HEXADECIMAL: `god-of-war-20th` e `spider-man-2` pintam
    com `<linearGradient>`, e os sem hex medido pintam com o
    `<pattern id="hachura-sem-hex">`. Os três moram no `<defs>` que a página
    publica UMA vez — logo, o `url(#…)` de um SVG resolve num `<defs>` que está
    em OUTRO `<svg>` da mesma página, e é a prova mais dura de que a tabela
    compartilhada funciona. Medido neste motor: o WebKit devolve
    `url("#hachura-sem-hex")`, com aspas.
    """
    if valor.startswith("#"):
        return _rgb(valor)
    return valor.replace("url(#", 'url("#').replace(")", '")')


@pytest.fixture(scope="module")
def medido() -> dict[str, Any]:
    """Uma abertura de WebKit para as três asserções abaixo."""
    if not BANCADA.is_file():
        pytest.skip(f"a bancada não tem {BANCADA.name} — rode aba01.py")
    cargas = [[slug, _carga(slug)] for slug in _fora_do_mockup()]
    fora = _no_webkit(ROTEIRO.replace("CARGAS", json.dumps(cargas)))
    assert "erro" not in fora, fora.get("erro")
    return fora


def test_o_piloto_escreve_o_colorway_que_o_pacote_leu(medido: dict[str, Any]) -> None:
    """O elo do meio: o `escrever()` do piloto chega ao atributo do `<svg>`.

    Esta é a asserção que a régua irmã não pode fazer — ela escreve o atributo
    com a própria mão. Aqui quem escreve é o `BOOTSTRAP` do piloto, e o que se
    cobra é que o valor no DOM seja o SLUG que o pacote leu do controle.
    """
    for slug in _fora_do_mockup():
        assert medido["colorway"][slug] == slug, (
            f"com {slug!r} na mesa o `<svg>` ficou com "
            f"{medido['colorway'][slug]!r}. O `escrever()` não chegou ao "
            f"atributo: confira `data-hef-alvo` e `data-hef-atributo` no "
            f"desenho, e `atributo_escrevivel` no piloto.")


def test_os_vinte_e_quatro_modelos_de_fora_do_mockup_pintam(
        medido: dict[str, Any]) -> None:
    """A lei dela, no pixel: o controle DELE, não o do desenho.

    O esperado sai de `monta.cor_da_zona`, que lê a folha gerada do
    `docs/data/cores-do-dualsense.csv`. Nenhum hexadecimal é digitado aqui.
    """
    achou = CRU.search(BANCADA.read_text(encoding="utf-8"))
    assert achou, "o chassi do desenho do P1 mudou de forma — não há neutro a medir"
    cru = _rgb(achou.group(1))
    fora = _fora_do_mockup()
    assert len(fora) == 24, (
        f"o mapa dela mudou de tamanho: {len(fora)} modelos fora do mockup. "
        f"Releia esta régua antes de mexer no número.")

    cinzas = [s for s in fora if medido["chassi"][s] == cru]
    assert not cinzas, (
        f"{len(cinzas)} de {len(fora)} modelos caíram no cinza cru ({cru}) — "
        f"o desenho ficou SEM identidade em vez de vestir o aparelho: "
        f"{cinzas[:6]}")

    do_mockup = monta.cor_da_zona(str(monta.MESA[0]["cor"]), "casca")
    presos = [s for s in fora if medido["chassi"][s] == _rgb(do_mockup)]
    assert not presos, (
        f"{len(presos)} modelos continuaram com a cor do MOCKUP ({do_mockup}) "
        f"sobre um aparelho que é outro — é o defeito que esta leva mata: "
        f"{presos[:6]}")

    erradas = {s: (medido["chassi"][s], monta.cor_da_zona(s, "casca"))
               for s in fora
               if medido["chassi"][s]
               != _como_o_motor_diz(monta.cor_da_zona(s, "casca"))}
    assert not erradas, f"o chassi não vestiu a cor do mapa dela: {erradas}"


def test_a_borda_e_o_desenho_nunca_discordam(medido: dict[str, Any]) -> None:
    """A queixa dela era a DISTÂNCIA entre os dois, e ela tinha quatro pixels.

        *"é white no p1, mas a borda de tudo é cosmic red e os svgs não são os
        que o meu mapa cataloga. isso tá errado"*

    A borda (`--plastico`, pela pele) e o desenho (`data-colorway`) são pintados
    por alvos DIFERENTES, a partir de duas chaves diferentes do pacote. Nada os
    obrigava a concordar além de chamarem o mesmo `monta.cor_da_zona` — e é
    isso que esta régua cobra no motor, no mesmo tique.

    A comparação é com a zona `casca-solida` de propósito: é o que
    `cor_da_zona` devolve por omissão, e é o que o pacote escreve na pele. Os
    modelos que pintam com `<pattern>` saem da conta porque a pele não pode
    receber um `url(#…)` — mas o desenho pode, e a asserção acima já os cobre.
    """
    for slug in _fora_do_mockup():
        esperado = monta.cor_da_zona(slug)
        if not esperado.startswith("#"):
            continue
        assert medido["pele"][slug] == _rgb(esperado), (
            f"com {slug!r} na mesa a borda do cartão ficou "
            f"{medido['pele'][slug]} e o mapa dela diz {esperado}")


def test_a_pintura_nao_deu_verde_sobre_nada(medido: dict[str, Any]) -> None:
    """Um contador em zero é endereço que não existe — e é verde sobre nada.

    A primeira carga pinta tudo; as seguintes só mexem no que mudou, e por isso
    a régua cobra do PRIMEIRO tique. Sem ela, uma página sem endereço nenhum
    passaria nas asserções acima no dia em que o `fill` cru coincidisse com a
    cor esperada.
    """
    primeiro = _fora_do_mockup()[0]
    assert medido["pintou"][primeiro] > 0, (
        "o piloto pintou ZERO valores na bancada — nenhum endereço da carga "
        "existe na página")
