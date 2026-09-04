#!/usr/bin/env python3
"""Clica os gestos MUDOS da aba Perfis no WebKit vivo e lê a tira do desfecho.

POR QUE ELE EXISTE, e é a regra desta casa: o teste de unidade
``test_aba10_os_cinco_gestos_calados_passaram_a_falar`` prova que os cinco
handlers DEVOLVEM a frase. Isso prova a CONTA. O que prova o PRODUTO é o mesmo
clique dentro do ``WebKit2.WebView`` que ela usa — porque entre o handler e o
olho dela ainda há o embrulho (``{"mesa": …}``), o ``_deu_certo`` do piloto, o
``window.__hef.pintar`` e a folha de estilo que acende a `.desfecho` pela
classe. Cada um desses degraus já quebrou calado nesta casa.

**ELE NÃO TOCA UM PERFIL DELA.** ``XDG_CONFIG_HOME`` é desviado para uma pasta
de mentira ANTES de qualquer import do produto — é lá que `platformdirs` decide
onde ficam os perfis —, e o ensaio semeia dois perfis próprios. O
``XDG_RUNTIME_DIR`` fica o real, para a janela achar o daemon dela e pintar com
estado de verdade; o que ela pode receber daqui é um ``launch_env.refresh``,
que relê e não escreve.

**POR QUE NÃO O `--prova-clique` DO PILOTO:** ele faz ``el.click()``, e num
``<input>`` isso chega ao gesto como ``evento=click`` — que o ``_so_mudou``
RECUSA, de propósito (clicar dentro de um campo manda o valor que já estava lá).
Um clique sintético nesses dois campos não escreve nada, e um ensaio que o
usasse daria verde sobre um caminho que nunca correu. Aqui o evento é o
``change`` de verdade, com valor novo.

**ELE LÊ A TIRA DUAS VEZES POR GESTO, e a segunda leitura é o ponto:**

* **no ato** (250 ms) — abaixo do tique de 500 ms. Só o ``_dizer`` chega aqui:
  ele DEVOLVE a carga e o ``_deu_certo`` do piloto pinta na hora.
* **assentado** (1,4 s) — depois do tique. O ``_anotar`` sozinho também chega
  aqui, porque a pintura do tique seguinte busca o desfecho guardado.

Sem as duas colunas o ensaio não separaria "responde ao clique" de "responde
meio segundo depois", que é exatamente a diferença que o ``remover`` tinha.

**E A COLUNA "no ato" NÃO É PRECISA — está escrito porque medido.** O tique de
500 ms não é sincronizado com o clique: um ``_anotar`` cujo clique caia logo
antes de um tique já aparece "falando" aos 250 ms. Medido em 03/09/2026, contra
o código de ANTES da cura: o ``remover`` (que era ``_anotar``) saiu "fala" nas
duas colunas. Logo, a segunda coluna só produz FALSO NEGATIVO — ela pode deixar
passar um ``_anotar``, nunca acusar um ``_dizer``. Quem separa os dois com
precisão é o teste de unidade, que lê o RETORNO do handler
(``test_o_remover_pinta_no_ato_e_nao_no_tique_seguinte``). Aqui ela é indício,
e o que REPROVA de verdade é a coluna "assentado".

**O TRAVESSÃO CONTA COMO MUDO.** O ``escrever()`` do piloto põe ``'—'`` no
lugar de um valor vazio, então uma régua que só perguntasse "tem texto?" daria
VERDE sobre a tira apagada — foi o que a primeira versão deste ensaio fez, e o
ensaio inteiro passou contra o código de ANTES da cura.

Uso (sempre oculto; ela tem UMA tela)::

    scripts/ensaios/a_tira_do_desfecho_acende_na_aba_perfis.py
    scripts/ensaios/a_tira_do_desfecho_acende_na_aba_perfis.py --foto /tmp/x.png
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# O DESVIO VEM ANTES DE TUDO. `utils/xdg_paths` calcula `_DIRS` no import, e
# `platformdirs` lê `XDG_CONFIG_HOME` naquele instante — mexer depois não
# adianta, e o ensaio escreveria na pasta de perfis DELA.
# ---------------------------------------------------------------------------
CASA = pathlib.Path(tempfile.mkdtemp(prefix="hef-ensaio-desfecho-"))
os.environ["XDG_CONFIG_HOME"] = str(CASA / "config")
os.environ["XDG_DATA_HOME"] = str(CASA / "share")
os.environ["XDG_CACHE_HOME"] = str(CASA / "cache")
#: A semeadura de fábrica encheria a pasta de nove perfis e a lista rolaria; o
#: ensaio quer duas linhas para saber em qual clicou.
os.environ["HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED"] = "1"

sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

# A janela deste instrumento NÃO nasce na tela dela (TELA-DELA-02).
# Ela pediu duas vezes em 04/09/2026; o `park` do workspace chega tarde,
# porque move a janela DEPOIS de ela existir. Escape: HEFESTO_NA_TELA=1.
_RAIZ_TELA = str(pathlib.Path(__file__).resolve().parents[2] / 'src')
if _RAIZ_TELA not in sys.path:
    sys.path.insert(0, _RAIZ_TELA)
from hefesto_dualsense4unix.utils.tela_de_mentira import (
    garantir_tela_de_mentira,
)

garantir_tela_de_mentira()

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.interface import hefesto_vivo
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

ABA = "10-perfis.html"

#: Os dois perfis do ensaio. Nomes que NÃO são os dela, para que um erro de
#: desvio apareça como colisão em vez de sobrescrever algo real.
ALVO = "Ensaio Do Desfecho"
VIZINHO = "Ensaio Vizinho"

#: O ROTEIRO, num JS só. Ele faz o caminho DELA em quatro tempos e devolve a
#: tira depois de cada um — o que se mede é o texto que fica na tela, não o
#: retorno do handler (esse já tem régua de unidade).
#:
#: O `change` É DISPARADO À MÃO porque o `el.value = …` do JS não o dispara
#: sozinho — é a mesma razão pela qual o piloto escuta `change` e não `input`.
ROTEIRO = r"""
(function(){
  function tira(){
    const el = document.querySelector('[data-hef="perfis.desfecho"] span')
            || document.querySelector('[data-hef="perfis.desfecho"]');
    const caixa = document.querySelector('div[data-hef="perfis.desfecho"]');
    return {texto: el ? (el.textContent || '').trim() : null,
            acesa: caixa ? caixa.classList.contains('on') : null};
  }
  function mandar(gesto, valor){
    const el = document.querySelector('[data-hef-gesto="' + gesto + '"]');
    if(!el){ return 'NAO ACHEI ' + gesto; }
    if(valor !== null){ el.value = valor; }
    el.dispatchEvent(new Event(valor === null ? 'click' : 'change',
                               {bubbles: true}));
    return 'ok';
  }
  const passos = [];
  passos.push({passo: 'antes de tudo', tira: tira()});
  window.__ensaio = {passos: passos, tira: tira, mandar: mandar};
  return JSON.stringify(tira());
})()
"""

#: O que perguntar depois de cada gesto — o mesmo leitor, uma linha.
LER_A_TIRA = "JSON.stringify(window.__ensaio.tira())"

#: MS até a primeira leitura. ABAIXO do tique de 500 ms de propósito: é o que
#: separa `_dizer` (devolve, e o piloto pinta no ato) de `_anotar` (guarda, e a
#: tela espera o tique).
NO_ATO_MS = 250
#: MS até a segunda. Acima do tique: aqui os dois caminhos já pintaram.
ASSENTADO_MS = 1400


def _mudo(tira: dict[str, object] | None) -> bool:
    """A tira está apagada?

    O `'—'` CONTA COMO MUDO, e essa linha é a régua inteira: o `escrever()` do
    piloto troca valor vazio por travessão antes de escrever
    (`hefesto_vivo.py`), então "tem texto" é verdade sobre uma tira apagada. A
    primeira versão deste ensaio perguntava só isso e passou contra o código de
    ANTES da cura — verde sobre nada, no mesmo dia em que ele foi escrito.
    """
    if not tira:
        return True
    texto = str(tira.get("texto") or "").strip()
    return texto in ("", "—") or tira.get("acesa") is not True

BANDEIRAS = dict(oculta=True, foto="", segundos=0.0, passear=False, parada=900,
                 espera=1200, incluir_perigosos=False, prova_clique="",
                 prova_de_mockup=False, sem_cravado=False, sem_selo=False,
                 teto_de_mockup=-1, voltas_por_aba=8, sem_cor=False,
                 prova_no_aparelho=False, entre=2500)


def _semear() -> None:
    """Os dois perfis do ensaio, na pasta de mentira."""
    save_profile(Profile(name=VIZINHO, match=MatchAny(), priority=5),
                 origem="ensaio")
    save_profile(Profile(name=ALVO, match=MatchAny(), priority=10),
                 origem="ensaio")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--foto", default="",
                    help="salva a janela em PNG depois do último gesto")
    ap.add_argument("--foto-antes", default="",
                    help="salva a janela ANTES do primeiro gesto")
    meu = ap.parse_args()

    _semear()
    args = argparse.Namespace(**BANDEIRAS, abre=ABA)
    piloto = hefesto_vivo.Piloto(args)
    lido: list[dict[str, object]] = []
    passos = [
        # (rótulo, gesto, valor · `None` = clique sem valor)
        ("selecionar o alvo", "selecionar", None),
        ("editor.jogo ← 1599660", "editor.jogo", "1599660"),
        ("editor.nome ← Ensaio Renomeado", "editor.nome", "Ensaio Renomeado"),
        ("remover (1º clique: arma)", "remover", None),
        ("remover (2º clique: apaga)", "remover", None),
    ]
    estado = {"i": 0}

    def proximo() -> bool:
        if not piloto.pronto:
            return True
        if meu.foto_antes and estado["i"] == 0:
            piloto.tela.fotografar(meu.foto_antes)
        if estado["i"] >= len(passos):
            if meu.foto:
                piloto.tela.fotografar(meu.foto)
            Gtk.main_quit()
            return False
        rotulo, gesto, valor = passos[estado["i"]]
        estado["i"] += 1
        medida: dict[str, object] = {"passo": rotulo, "erro": ""}

        def _ler(texto: str | None, erro: Exception | None, *, chave: str) -> None:
            medida[chave] = (json.loads(texto) if texto and not erro
                             else {"texto": None, "acesa": None})
            if erro:
                medida["erro"] = str(erro)

        def no_ato(texto: str | None, erro: Exception | None) -> None:
            _ler(texto, erro, chave="no_ato")

        def depois(texto: str | None, erro: Exception | None) -> None:
            _ler(texto, erro, chave="assentado")
            lido.append(medida)
            GLib.timeout_add(600, proximo)

        # A SELEÇÃO DA LINHA é por texto, e o `selecionar` mora na célula do
        # nome — o `[data-hef-gesto]` genérico pegaria a primeira linha da
        # lista, que pode ser a outra.
        alvo = (f"(function(){{const c=[...document.querySelectorAll("
                f"'[data-hef-gesto=\"selecionar\"]')].find(x=>"
                f"(x.textContent||'').trim()==={ALVO!r});"
                f"if(!c) return 'NAO ACHEI A LINHA'; c.click(); return 'ok';}})()"
                if gesto == "selecionar"
                else f"window.__ensaio.mandar({gesto!r}, "
                     f"{'null' if valor is None else repr(valor)})")
        piloto.ponte.rodar(alvo)
        GLib.timeout_add(NO_ATO_MS,
                         lambda: piloto.ponte.perguntar(LER_A_TIRA, no_ato) or False)
        GLib.timeout_add(ASSENTADO_MS,
                         lambda: piloto.ponte.perguntar(LER_A_TIRA, depois) or False)
        return False

    def comecar() -> bool:
        if not piloto.pronto:
            return True
        piloto.ponte.rodar(ROTEIRO)
        GLib.timeout_add(600, proximo)
        return False

    GLib.timeout_add(400, lambda: piloto._ir(ABA))
    GLib.timeout_add(3000, comecar)
    GLib.timeout_add(60000, Gtk.main_quit)
    Gtk.main()

    print(f"a pasta de perfis do ensaio: {CASA}/config/hefesto-dualsense4unix")
    print(f"{'passo':34s} {'no ato':7s} {'assent':7s} tira (assentada)")
    #: OS QUE DEVEM NOTÍCIA. `selecionar` não grava nada e o `remover` de ARMAR
    #: termina em recusa — a fala dele é a TARJA, não a tira.
    cobrados = {"editor.jogo ← 1599660", "editor.nome ← Ensaio Renomeado",
                "remover (2º clique: apaga)"}
    mudos: list[str] = []
    tarde: list[str] = []
    for x in lido:
        t = x.get("assentado") or {}
        print(f"  {str(x['passo']):32s} "
              f"{('MUDA' if _mudo(x.get('no_ato')) else 'fala'):7s} "
              f"{('MUDA' if _mudo(t) else 'fala'):7s} "
              f"{str(t.get('texto'))!r}"
              f"{('  ERRO: ' + str(x['erro'])) if x['erro'] else ''}")
        if str(x["passo"]) not in cobrados:
            continue
        if _mudo(t):
            mudos.append(str(x["passo"]))
        elif _mudo(x.get("no_ato")):
            tarde.append(str(x["passo"]))

    shutil.rmtree(CASA, ignore_errors=True)
    if len(lido) < len(passos):
        print(f"\nREPROVA: só {len(lido)} de {len(passos)} passos responderam — "
              f"a janela não chegou ao fim.")
        return 1
    if mudos:
        print(f"\nREPROVA: {len(mudos)} gesto(s) gravaram no disco e a tira "
              f"ficou apagada: {', '.join(mudos)}")
        return 1
    if tarde:
        print(f"\nREPROVA: {len(tarde)} gesto(s) só falaram DEPOIS do tique de "
              f"500 ms — é o `_anotar` sem o `_dizer`: {', '.join(tarde)}. Meio "
              f"segundo de silêncio é o intervalo em que ela clica de novo.")
        return 1
    print(f"\nOK: os {len(cobrados)} gestos que gravam acenderam a tira do "
          f"desfecho NO ATO, dentro do WebKit vivo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
