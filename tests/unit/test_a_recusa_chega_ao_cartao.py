#!/usr/bin/env python3
"""A RECUSA DO PRODUTO CHEGA AO CARTÃO — medida na JANELA, não no terminal.

POR QUE ESTA RÉGUA EXISTE, e a data é 02/09/2026. O contrato desta casa é
explícito: `RuntimeError` num gesto quer dizer *"o produto recusou, e a frase
VAI PARA A TELA"*, escrita para quem está com o controle na mão. A recusa
humanizada existia, estava testada — e saía no `stderr` do processo:

    [gesto falhou] 02-controles.html · mudo: o daemon não confirmou o mudo do
    microfone — ou o Hefesto está parado, ou este controle saiu da mesa

Quem clica na janela não lê o terminal de quem a lançou. **É a forma de defeito
mais cara desta casa: alguém curou o caminho e provou a cura num caminho que ela
não usa.** Medido pelo caminho DELA — dois cliques no 🎙 da `02-controles`, com
um dublê que faz o `mic.set` recusar: os dois recusaram com a frase certa, o
`desfechos` do piloto a guardou, e o DOM não tinha uma letra dela. O segundo
clique parecia o primeiro.

AS CINCO COISAS QUE ESTA RÉGUA COBRA, e cada uma é um jeito diferente de o
canal mentir:

1. **A FRASE CHEGA AO DOM.** Não ao `desfechos`, não ao `stderr` — ao documento
   que ela está olhando.
2. **ELA CHEGA AO CARTÃO DAQUELE CONTROLE.** Na mesa de quatro, a recusa de um
   no cartão do vizinho é pior que recusa nenhuma.
3. **ELA SOBREVIVE À REPINTURA.** A tela repinta a cada 500 ms e troca blocos
   inteiros. Uma frase que só existe no instante do clique não é vista por
   ninguém — é a mesma razão pela qual
   `daemon/subsystems/recado_do_microfone.py` é um DEPÓSITO e não um evento.
4. **O SEGUNDO CLIQUE TAMBÉM RESPONDE**, que é o enunciado desta frente em uma
   linha.
5. **ELA VENCE.** Decisão dela: *"a frase de recusa SOME depois de um tempo —
   ~30 s e desaparece. É aviso, não estado."*

E A SEXTA, que é sobre o instrumento e não sobre o produto: **o aviso não pode
entrar na conta da régua do mockup.** Ele é um nó que o piloto desenha, e se
ganhasse `data-campo`/`data-papel`/`data-hef` o `LER_CAMPOS` passaria a contá-lo
como campo da página — a régua mediria o próprio instrumento.

A MORDIDA, e são três, cada uma reprovando um item diferente. **Devolva por
CÓPIA (`cp`), nunca por `git checkout --`** — isso já custou trabalho quatro
vezes nesta casa:

* apague o `self._recados[pref] = …` de `Piloto._recusou_dizendo` → reprovam 4
  (a frase não chega a lugar nenhum);
* troque `pai.insertBefore(el, pai.firstChild)` do BOOTSTRAP por
  `document.body.appendChild(el)` → reprova 1 (a frase não está no cartão);
* apague o `carga["recados"] = self._recados_para_a_tela()` de `Piloto._tique` →
  reprovam 2 (o aviso não volta depois de o bloco ser trocado, e não vence
  nunca).

Os três números acima são os MEDIDOS em 02/09/2026, e não uma previsão.

POR QUE ELA ABRE UM WEBKIT DE VERDADE: porque foi a leitura do fonte que se
enganou da primeira vez. `Gtk.OffscreenWindow` — sob Xvfb não há gerenciador de
janelas e uma `Gtk.Window` fica 1x1 para sempre.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src/hefesto_dualsense4unix/interface"
sys.path.insert(0, str(INTERFACE))

#: A mesa de mentira, na faixa sintética da casa — há dois portões de anonimato
#: nesta árvore e um endereço mascarado ainda carrega o OUI do aparelho dela.
UNIQ_P1 = "aa:bb:cc:00:00:01"
UNIQ_P2 = "aa:bb:cc:00:00:02"

#: O ESTADO DUBLÊ. Ele é o mínimo que `mesa_viva.mesa_do_estado` precisa para
#: montar `p1` e `p2` — a régua não fala com o daemon dela, e em máquina sem
#: daemon o `_tique` sairia calado pelo `[daemon mudo]` e a janela nunca pintaria.
ESTADO = {
    "active_profile": "regua",
    "gamepad_emulation": {"flavor": "dualsense"},
    "controllers": [
        {"uniq": UNIQ_P1, "connected": True, "transport": "usb", "player": 1,
         "audio": {"mic_mudo": False}},
        {"uniq": UNIQ_P2, "connected": True, "transport": "bt", "player": 2,
         "audio": {"mic_mudo": False}},
    ],
}

#: QUANTO O AVISO VIVE NESTA MEDIÇÃO. O produto usa 30 s (decisão dela); aqui a
#: constante encolhe para a régua poder ver a frase VENCER sem ficar meio minuto
#: parada. É a constante do produto que muda, e não uma segunda regra escrita
#: para o teste — a régua mede o mesmo caminho.
VENCE_EM_S = 8.0

#: O que se lê do DOM a cada parada do roteiro. `dentro_de` é o item 2: de quem
#: é o cartão em que a frase pousou.
LER_A_TELA = r"""
(function(){
  const recados = [];
  for(const el of document.querySelectorAll('.hef-recado')){
    const cartao = el.closest('[data-controle],[data-uniq]');
    recados.push({
      chave: el.getAttribute('data-hef-recado') || '',
      texto: (el.textContent || '').trim(),
      dentro_de: cartao ? (cartao.dataset.controle || cartao.dataset.uniq || '') : '',
    });
  }
  return JSON.stringify({
    recados: recados,
    // A CONTA DA RÉGUA DO MOCKUP, no mesmo instante: os três vocabulários de
    // endereço que o `LER_CAMPOS` varre. O aviso não pode mexer neste número.
    enderecos: document.querySelectorAll('[data-campo],[data-papel],[data-hef]').length,
  });
})()
"""

#: O CLIQUE, no 🎙 do cartão do p1 — e é o botão do produto, com o `data-gesto`
#: que a página publicada traz. Clicar por coordenada é a armadilha que esta casa
#: já pagou duas vezes.
CLICAR_NO_MIC = r"""
(function(){
  const b = document.querySelector('[data-controle="p1"] [data-mudo="microfone"]');
  if(!b) return 'NAO ACHEI O BOTAO DO MICROFONE NO CARTAO DO P1';
  b.click();
  return 'cliquei';
})()
"""

#: A TROCA DE BLOCO, simulada como a pintura a faz de verdade: `alvo.innerHTML =
#: html`, com um `html` que vem do PACOTE e não sabe que existe aviso nenhum. É o
#: que acontece com a fita, com a tabela de perfis e com o mapa do gabinete — um
#: bloco cujo número de filhos muda com o dado não tem como ser pintado campo a
#: campo.
#:
#: O `remove()` VEM ANTES, E É O PONTO: a primeira versão desta sonda fazia só
#: `c.innerHTML = c.innerHTML` e o aviso VOLTAVA sozinho — o `innerHTML` que se
#: lê já traz o `<div class="hef-recado">` serializado, e reatribuí-lo o recria.
#: Aquilo não simulava troca de bloco nenhuma: simulava o navegador copiando o
#: aviso. A sonda dizia `1` onde tinha de dizer `0`, e a régua teria passado
#: sobre nada.
MATAR_O_CARTAO = r"""
(function(){
  const c = document.querySelector('[data-controle="p1"]');
  if(!c) return 'sem cartao';
  for(const el of document.querySelectorAll('.hef-recado')) el.remove();
  c.innerHTML = c.innerHTML;
  return String(document.querySelectorAll('.hef-recado').length);
})()
"""


@pytest.fixture(scope="module")
def medido() -> dict:
    """Abre o piloto DE VERDADE, oculto, e roda o roteiro de tempo."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    import argparse

    import hefesto_vivo as hv

    # OS DOIS DUBLÊS. O primeiro tira o daemon do caminho; o segundo faz o
    # `mic.set` recusar, que é o caminho do `RuntimeError` em
    # `a02_controles.mudo`. Nada sai para aparelho nenhum.
    hv.mesa_viva.estado_do_daemon = lambda *a, **k: ESTADO  # type: ignore[assignment]
    hv.ponte.mic_set = lambda *a, **k: False  # type: ignore[assignment]
    hv.SEGUNDOS_DO_RECADO = VENCE_EM_S

    args = argparse.Namespace(
        oculta=True, segundos=0.0, passear=False, parada=900, foto="",
        abre="02-controles.html", prova_no_aparelho=False, entre=2500,
        espera=1200, incluir_perigosos=False, prova_clique="", sem_cor=True,
        prova_de_mockup=False, voltas_por_aba=8, teto_de_mockup=-1,
        sem_cravado=False, sem_selo=False,
    )
    piloto = hv.Piloto(args)
    fora: dict[str, object] = {}

    def ler(rotulo: str):
        def _leu(valor, erro):
            fora[rotulo] = (f"ERRO {erro}" if erro is not None
                            else json.loads(str(valor)))
        return _leu

    def anotar(rotulo: str):
        def _leu(valor, erro):
            fora[rotulo] = f"ERRO {erro}" if erro is not None else str(valor)
        return _leu

    def antes_do_clique() -> bool:
        # A PÁGINA TEM DE ESTAR PRONTA, e não "já deve ter carregado": aos 600 ms
        # o bootstrap ainda não instalou e o `el.click()` acha o botão sem
        # ouvinte que responda — o clique some, calado. Já custou uma medição.
        if not piloto.pronto:
            return True
        piloto.ponte.perguntar(LER_A_TELA, ler("antes"))
        piloto.ponte.perguntar(CLICAR_NO_MIC, anotar("clique"))
        GLib.timeout_add(700, logo_depois)
        return False

    def logo_depois() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("logo-depois"))
        GLib.timeout_add(2300, sobreviveu)
        return False

    def sobreviveu() -> bool:
        # ~6 tiques de 500 ms depois do clique: a repintura correu por cima.
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-de-seis-tiques"))
        piloto.ponte.perguntar(MATAR_O_CARTAO, anotar("matei-o-cartao"))
        GLib.timeout_add(1100, voltou)
        return False

    def voltou() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-da-troca-de-bloco"))
        # O SEGUNDO CLIQUE, e ele é o defeito de origem em pessoa: o relato
        # anterior dizia que ele respondia, e respondia para quem roda pelo
        # terminal. Aqui ele também RENOVA o depósito — e é o que dá dente ao
        # teste do vencimento. Sem esta renovação, o aviso já estava morto
        # (levado pela troca de bloco) quando a régua foi ver se ele tinha
        # vencido: ela dava verde sobre um DOM vazio, que é a forma exata de
        # "verde sobre nada" que esta casa persegue. Medido arrancando o
        # `carga["recados"]` do tique — a régua passava.
        piloto.ponte.perguntar(CLICAR_NO_MIC, anotar("segundo-clique"))
        GLib.timeout_add(900, depois_do_segundo)
        return False

    def depois_do_segundo() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-do-segundo-clique"))
        GLib.timeout_add(int(VENCE_EM_S * 1000), venceu)
        return False

    def venceu() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-de-vencer"))
        GLib.timeout_add(900, fim)
        return False

    def fim() -> bool:
        fora["desfechos"] = {k: list(v) for k, v in piloto.desfechos.items()}
        Gtk.main_quit()
        return False

    GLib.timeout_add(400, lambda: piloto._ir(args.abre))
    GLib.timeout_add(2000, antes_do_clique)
    # O RELÓGIO DE SEGURANÇA GUARDA O SEU `id`, e isso NÃO é zelo — é um defeito
    # que esta régua causou e que foi medido em 02/09/2026. Sem o
    # `source_remove`, este `Gtk.main_quit` fica pendente depois de a fixture
    # terminar e dispara DENTRO do laço do PRÓXIMO teste de GUI do mesmo
    # processo: rodando esta régua junto das outras que tocam o piloto, as ONZE
    # medições do `test_o_pintor_acende_a_classe_e_apaga_as_irmas` morreram com
    # *"o WebKit não respondeu em 20 s"* — e o pintor está certo, ele nunca teve
    # 20 s. Aos pares os dois passavam, porque a bomba só chega ao vizinho
    # quando há trabalho suficiente entre os dois.
    #
    # E A CULPA É DESTA LINHA, e não das duas abaixo: com as três curas no lugar
    # a leva dá 333 verdes; arrancando SÓ o `source_remove` ela volta a 322 com
    # os mesmos 11 erros. Não foi diagnóstico por eliminação de gosto — foi
    # medido, e as duas linhas abaixo ficam por serem certas, não por serem a
    # cura.
    guarda = GLib.timeout_add(int(30000 + VENCE_EM_S * 1000), Gtk.main_quit)
    Gtk.main()
    GLib.source_remove(guarda)
    # E O PILOTO TAMBÉM PARA. O tique dele é um `timeout_add` de 500 ms que se
    # reagenda para sempre; deixá-lo vivo faria esta janela pintar por cima de
    # todo laço GTK que vier depois, no mesmo processo.
    piloto.pronto = False
    piloto.tela.janela.destroy()
    assert "depois-de-vencer" in fora, (
        f"o roteiro não chegou ao fim — o que voltou foi {sorted(fora)}")
    return fora


def _frases(leitura: object) -> list[str]:
    assert isinstance(leitura, dict), leitura
    return [r["texto"] for r in leitura["recados"]]


# --------------------------------------------------------------------------
# 0. o clique aconteceu e o produto recusou — senão não há o que medir
# --------------------------------------------------------------------------
def test_o_gesto_recusou_dizendo(medido: dict) -> None:
    assert medido["clique"] == "cliquei", medido["clique"]
    desfechos = medido["desfechos"]
    assert isinstance(desfechos, dict)
    assert "02-controles.html:mudo" in desfechos, (
        f"o clique não chegou ao gesto — os desfechos foram {desfechos}")
    classe, frase = desfechos["02-controles.html:mudo"]
    assert classe == "recusou dizendo", (classe, frase)
    assert frase.startswith("RuntimeError:"), frase


# --------------------------------------------------------------------------
# 1. a frase chega ao DOM
# --------------------------------------------------------------------------
def test_a_frase_da_recusa_chega_ao_dom(medido: dict) -> None:
    """Ao DOM que ela olha — não ao `desfechos`, não ao `stderr`."""
    assert _frases(medido["antes"]) == [], (
        "a tela já tinha recado antes do clique — a medição não vale")
    frases = _frases(medido["logo-depois"])
    assert len(frases) == 1, (
        f"depois do clique recusado a tela mostra {frases!r}. Um botão que "
        f"aceita o clique e não diz nada é o defeito mais caro desta casa: o "
        f"segundo clique parece o primeiro.")
    assert "não confirmou o mudo do microfone" in frases[0], frases[0]


# --------------------------------------------------------------------------
# 2. no cartão daquele controle, e não no do vizinho
# --------------------------------------------------------------------------
def test_a_frase_pousa_no_cartao_de_quem_foi_clicado(medido: dict) -> None:
    leitura = medido["logo-depois"]
    assert isinstance(leitura, dict)
    recado = leitura["recados"][0]
    assert recado["chave"] == "p1", (
        f"o recado foi endereçado a {recado['chave']!r}; o clique foi no p1")
    assert recado["dentro_de"] == "p1", (
        f"a frase está dentro de {recado['dentro_de']!r} — na mesa de quatro, a "
        f"recusa de um controle no cartão do vizinho é pior que recusa nenhuma")


# --------------------------------------------------------------------------
# 3. sobrevive à repintura — aos tiques e à troca de bloco
# --------------------------------------------------------------------------
def test_o_aviso_sobrevive_aos_tiques(medido: dict) -> None:
    """~6 repinturas depois do clique a frase continua na tela."""
    frases = _frases(medido["depois-de-seis-tiques"])
    assert len(frases) == 1 and "microfone" in frases[0], (
        f"a frase sumiu na repintura: {frases!r}. Uma frase que só existe no "
        f"instante do clique não é vista por ninguém.")


def test_o_aviso_volta_quando_a_pintura_troca_o_bloco(medido: dict) -> None:
    """A pintura troca blocos inteiros — o aviso tem de renascer no tique."""
    assert medido["matei-o-cartao"] == "0", (
        f"a simulação não levou o aviso embora ({medido['matei-o-cartao']!r}) — "
        f"sem isso este teste passa sobre nada")
    frases = _frases(medido["depois-da-troca-de-bloco"])
    assert len(frases) == 1 and "microfone" in frases[0], (
        f"o aviso não voltou depois de o bloco ser trocado: {frases!r}. É o "
        f"tique que o recria, lendo o depósito — sem isso ele morre com o "
        f"primeiro bloco que a pintura substituir.")


# --------------------------------------------------------------------------
# 4. o SEGUNDO clique responde — que é o defeito de origem desta frente
# --------------------------------------------------------------------------
def test_o_segundo_clique_tambem_responde_na_tela(medido: dict) -> None:
    """O enunciado desta frente em uma linha: *o segundo clique de um gesto
    continua sem resposta nenhuma na tela dela*. Aqui ele responde."""
    assert medido["segundo-clique"] == "cliquei", medido["segundo-clique"]
    frases = _frases(medido["depois-do-segundo-clique"])
    assert len(frases) == 1 and "microfone" in frases[0], (
        f"o segundo clique deixou a tela em {frases!r}. Um segundo clique que "
        f"parece o primeiro é o botão que responde calado — e é ele que faz "
        f"quem clica concluir que funcionou.")


# --------------------------------------------------------------------------
# 5. e vence — é aviso, não estado
# --------------------------------------------------------------------------
def test_o_aviso_vence_e_some(medido: dict) -> None:
    """Decisão dela: *"a frase de recusa SOME depois de um tempo (…) ~30 s"*.

    A LEITURA VEM DEPOIS DO SEGUNDO CLIQUE de propósito: ele renova o depósito,
    e sem essa renovação a régua chegava aqui com o DOM já vazio pela troca de
    bloco — verde sobre nada.
    """
    frases = _frases(medido["depois-de-vencer"])
    assert frases == [], (
        f"passados {VENCE_EM_S:.0f} s a tela ainda mostra {frases!r}. Aviso que "
        f"não vence virou estado, e a tela passa a afirmar uma recusa velha.")


# --------------------------------------------------------------------------
# 6. o instrumento não entra na conta da régua do mockup
# --------------------------------------------------------------------------
def test_o_aviso_nao_conta_como_campo_da_pagina(medido: dict) -> None:
    """Se o aviso tivesse `data-campo`, a régua mediria o próprio instrumento."""
    antes, com_aviso = medido["antes"], medido["logo-depois"]
    assert isinstance(antes, dict) and isinstance(com_aviso, dict)
    assert antes["enderecos"] == com_aviso["enderecos"], (
        f"a página tinha {antes['enderecos']} endereços de pintura e passou a "
        f"ter {com_aviso['enderecos']} com o aviso na tela. O `LER_CAMPOS` varre "
        f"`data-campo`/`data-papel`/`data-hef`: o aviso não pode carregar "
        f"nenhum dos três, ou a régua do mockup passa a contá-lo como campo.")
