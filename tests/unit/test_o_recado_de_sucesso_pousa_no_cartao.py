#!/usr/bin/env python3
"""O RECADO DE SUCESSO NO CARTÃO — e o botão que diz que está trabalhando.

Duas decisões dela de 04/09/2026, medidas na JANELA e não no terminal:

**D-01 — o canal de sucesso.** *"No próprio cartão, como a recusa."* Até aqui a
interface nova só falava quando RECUSAVA: um gesto que dava certo imprimia
``[gesto] … → aplicado`` no terminal de quem lançou a janela, e quem clica não
lê terminal. **Cinco linhas do CSV paravam nesse buraco**, em cinco abas (02,
03, 05, 06 e 09) — e uma peça só as fecha.

**`09` [03] — o estado "em voo".** *"O botão diz que está trabalhando"*, e diz
DURANTE a espera, no lugar exato do clique. Há um gesto desta casa que leva
**9,5 segundos** (``daemon.reload``, medido no daemon dela em 01/09) e nenhuma
das dez abas tinha estado em voo: o clique sumia por nove segundos e meio e o
segundo clique parecia o primeiro.

DOIS SEGUNDOS CANAIS FORAM RECUSADOS POR ELA NO MESMO DIA, e esta régua existe
também para que ninguém os construa: *o campo que pisca* (aba 03, conflito C-3)
e *a faixa embaixo da grade* (aba 05, conflito C-6). **Um fato, um sinal.**

POR QUE ELA ABRE UM WebKit DE VERDADE, com o piloto do produto: porque a forma
de defeito mais cara desta casa é *alguém curar o caminho e provar a cura num
caminho que ela não usa*. Foi assim com a recusa em 02/09 — dois cliques deram
duas linhas no terminal, o ``desfechos`` guardou a frase certa e o DOM não tinha
uma letra dela. Aqui o clique é no botão do produto, com o ``data-mudo`` que a
página publicada traz, e a leitura é do DOM.

A JANELA É OCULTA. Ela tem UMA tela.

AS SETE COISAS QUE ESTA RÉGUA COBRA:

1. **a frase de sucesso chega ao DOM** — não ao ``desfechos``, não ao ``stderr``;
2. **ela pousa no cartão DAQUELE controle**, como a recusa;
3. **ela é VERDE**, e a recusa continua laranja: dois desfechos, dois tons, um
   canal só;
4. **a frase do DONO DO ASSUNTO vence a do piloto** — é onde a D-12 pousa
   (*"o microfone ligou, mas o canal dele está mudo no sistema"*), e o ``recado``
   não vaza para a pintura como se fosse endereço de página;
5. **ela vence mais cedo que a recusa** — recibo é aviso, não estado;
6. **o botão fica em voo enquanto o gesto está no ar**, com a classe e com o
   rótulo que a página publicar;
7. **ele volta sozinho**, e volta INTEIRO — com os filhos que tinha.

A MORDIDA: troque ``_deu_certo_dizendo`` por ``_deu_certo`` na chamada do
``_gesto`` e o cartão fica mudo depois de um gesto que deu certo; apague o
``em_voo(alvo)`` do ouvinte e o botão fica igual durante os dois segundos de
espera.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: OS DOIS CONTROLES DA MESA DUBLÊ, na faixa sintética da casa. Nada de MAC real
#: em arquivo versionado — há dois portões, e eles não perdoam.
UNIQ_P1 = "aa:bb:cc:00:00:01"
UNIQ_P2 = "aa:bb:cc:00:00:02"

#: O `uniq` NORMALIZADO é a chave do depósito. Escrito à mão de propósito: a
#: régua confere o VALOR que o produto usa, e importar a mesma função dos dois
#: lados faria os dois errarem juntos em silêncio.
CHAVE_P1 = "aabbcc000001"


def _ctl(uniq: str, transporte: str, jogador: int) -> dict:
    return {"uniq": uniq, "connected": True, "transport": transporte,
            "player": jogador, "audio": {"mic_mudo": False}}


ESTADO = {
    "active_profile": "regua",
    "gamepad_emulation": {"flavor": "dualsense"},
    "controllers": [_ctl(UNIQ_P1, "usb", 1), _ctl(UNIQ_P2, "bt", 2)],
}

MESA = {"estado": ESTADO}

#: QUANTO O RECIBO VIVE NESTA MEDIÇÃO. O produto usa 6 s; aqui encolhe para a
#: régua ver a frase VENCER sem esperar. É a constante DO PRODUTO que muda, e não
#: uma segunda regra escrita para o teste — a régua mede o mesmo caminho. E o
#: valor do produto é lido ANTES, para dar dono à decisão dela.
VENCE_EM_S = 3.0

#: QUANTO O GESTO LENTO DEMORA. Ele existe para o item 6: um gesto instantâneo
#: não tem "durante", e o estado em voo é justamente o que se vê DURANTE.
GESTO_LENTO_S = 1.6

#: A FRASE QUE O DONO DO ASSUNTO MANDA. É a forma da D-12, e ela chega pelo
#: retorno do gesto — o piloto não a inventa nem a conhece.
FRASE_DO_DONO = "o microfone ligou, mas o canal dele está mudo no sistema"

LER_A_TELA = r"""
(function(){
  const recados = [];
  for(const el of document.querySelectorAll('.hef-recado')){
    const cartao = el.closest('[data-controle],[data-uniq]');
    const cs = getComputedStyle(el);
    recados.push({
      chave: el.getAttribute('data-hef-recado') || '',
      texto: (el.textContent || '').trim(),
      dentro_de: cartao ? (cartao.dataset.controle || cartao.dataset.uniq || '') : '',
      tom: el.dataset.hefTom || '',
      // A COR VEM DO CSSOM, e não do `cssText`: é o que a tela MOSTRA. Ler o
      // texto do atributo diria que a regra foi escrita, não que ela pegou.
      cor: cs.color,
      borda: cs.borderTopColor,
    });
  }
  const b = document.querySelector('[data-controle="p1"] [data-mudo="microfone"]');
  return JSON.stringify({
    recados: recados,
    // A CONTA DA RÉGUA DO MOCKUP, no mesmo instante: o aviso não pode mexer no
    // número de endereços da página.
    enderecos: document.querySelectorAll('[data-campo],[data-papel],[data-hef]').length,
    botao: b ? {
      classes: b.className,
      em_voo: b.classList.contains('hef-em-voo'),
      voo: b.getAttribute('data-hef-voo') || '',
      texto: (b.textContent || '').trim(),
      filhos: b.children.length,
    } : null,
  });
})()
"""

#: O CLIQUE, no 🎙 do cartão do p1 — o botão do produto, com o `data-mudo` que a
#: página publicada traz. Clicar por coordenada é a armadilha que esta casa já
#: pagou duas vezes.
CLICAR_NO_MIC = r"""
(function(){
  const b = document.querySelector('[data-controle="p1"] [data-mudo="microfone"]');
  if(!b) return 'NAO ACHEI O BOTAO DO MICROFONE NO CARTAO DO P1';
  b.click();
  return 'cliquei';
})()
"""

#: O RÓTULO EM VOO QUE UMA PÁGINA PUBLICARIA. A `09` publicará
#: `data-hef-em-voo="Reaplicando…"`; aqui a régua o escreve no botão da `02`,
#: porque nenhuma página o traz ainda — e a metade do endereço é da frente da
#: aba, não desta.
PUBLICAR_O_ROTULO = r"""
(function(){
  const b = document.querySelector('[data-controle="p1"] [data-mudo="microfone"]');
  if(!b) return 'sem botao';
  b.setAttribute('data-hef-em-voo', 'Calando…');
  return b.innerHTML;
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
    import time as _time

    import hefesto_vivo as hv

    # OS DUBLÊS, E ELES SÃO DEVOLVIDOS NO FIM. `mesa_viva`, `pacotes.ponte` e o
    # registro `GESTOS` são módulos COMPARTILHADOS do produto: escrever neles sem
    # devolver deixaria, no mesmo processo, uma mesa de mentira e um `mic.set`
    # que sempre passa para todo vizinho que abrir um `Piloto` depois.
    chave = ("02-controles.html", "mudo")
    # **O DUBLÊ MUDOU DE FUNÇÃO EM 04/09/2026 — S-05, a D-12 dela.** O gesto
    # `mudo` da aba 02 passou a chamar o ATO inteiro do microfone
    # (`mic_canal_set_detalhado`), e com o dublê no nome VELHO esta régua
    # mediria o caminho da RECUSA no lugar do sucesso: a chamada iria ao
    # socket, não achava daemon, e o cartão recebia a frase laranja. É o mesmo
    # arranjo do `test_a_recusa_chega_ao_cartao`, do outro lado do desfecho.
    guardado = (hv.mesa_viva.estado_do_daemon, hv.ponte.mic_canal_set_detalhado,
                hv.SEGUNDOS_DO_RECADO_DE_SUCESSO,
                hv.pacotes.GESTOS.get(chave))
    #: O VALOR DO PRODUTO, lido ANTES de a régua o encolher. É o que dá dono à
    #: decisão dela: sem ele, trocar `6.0` por `600.0` deixaria os testes verdes,
    #: porque a fixture sobrescreve a constante antes de qualquer medição.
    do_produto = {
        "sucesso": float(hv.SEGUNDOS_DO_RECADO_DE_SUCESSO),
        "recusa": float(hv.SEGUNDOS_DO_RECADO),
        "frase": str(hv.FRASE_DE_SUCESSO),
    }
    MESA["estado"] = ESTADO
    hv.mesa_viva.estado_do_daemon = lambda *a, **k: MESA["estado"]  # type: ignore[assignment]
    # `mic.set` PASSANDO — é o caminho do SUCESSO, e é o que nunca foi medido.
    # `status: "ok"` É O QUE O ATO RESPONDE COM AS DUAS METADES FEITAS, e é o
    # único corpo em que `frase_do_ato_do_microfone` devolve `None` — o caminho
    # do SUCESSO, que é o que este arquivo existe para medir. Um `True` seria
    # mais frouxo que a ponte real, que devolve `dict | None`.
    hv.ponte.mic_canal_set_detalhado = (  # type: ignore[assignment]
        lambda *a, **k: {"status": "ok", "canal_feito": True,
                         "firmware_pedido": True})
    hv.SEGUNDOS_DO_RECADO_DE_SUCESSO = VENCE_EM_S

    args = argparse.Namespace(
        oculta=True, segundos=0.0, passear=False, parada=900, foto="",
        abre="02-controles.html", prova_no_aparelho=False, entre=2500,
        espera=1200, incluir_perigosos=False, prova_clique="", sem_cor=True,
        prova_de_mockup=False, voltas_por_aba=8, teto_de_mockup=-1,
        sem_cravado=False, sem_selo=False,
    )
    piloto = hv.Piloto(args)
    fora: dict[str, object] = {"produto": do_produto}

    def ler(rotulo: str):
        def _leu(valor, erro):
            fora[rotulo] = (f"ERRO {erro}" if erro is not None
                            else json.loads(str(valor)))
        return _leu

    def anotar(rotulo: str):
        def _leu(valor, erro):
            fora[rotulo] = f"ERRO {erro}" if erro is not None else str(valor)
        return _leu

    def por_gesto(fn) -> None:
        """Troca quem atende o 🎙 — pelo REGISTRO do produto, não por atalho.

        `@gesto` grava em `pacotes.GESTOS`, e é daí que o `_gesto` lê. Injetar
        aqui é exercitar exatamente o caminho que um pacote real percorre.
        """
        hv.pacotes.GESTOS[chave] = fn

    def antes_do_clique() -> bool:
        # A PÁGINA TEM DE ESTAR PRONTA, e não "já deve ter carregado": sem o
        # bootstrap o `el.click()` acha o botão sem ouvinte que responda — o
        # clique some, calado. Já custou uma medição a esta casa.
        if not piloto.pronto:
            return True
        piloto.ponte.perguntar(LER_A_TELA, ler("antes"))
        piloto.ponte.perguntar(CLICAR_NO_MIC, anotar("clique-1"))
        GLib.timeout_add(700, depois_do_sucesso)
        return False

    def depois_do_sucesso() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-do-sucesso"))
        GLib.timeout_add(2200, sobreviveu)
        return False

    def sobreviveu() -> bool:
        # ~22 tiques de 100 ms depois do clique: a repintura correu por cima.
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-de-muitos-tiques"))
        GLib.timeout_add(int(VENCE_EM_S * 1000) + 400, venceu)
        return False

    def venceu() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-de-vencer"))
        GLib.timeout_add(300, com_a_frase_do_dono)
        return False

    def com_a_frase_do_dono() -> bool:
        # A FRASE DO DONO DO ASSUNTO, pelo retorno do gesto. É a forma da D-12.
        por_gesto(lambda ctx, o, p: {"recado": FRASE_DO_DONO,
                                     "mesa": {"perfil-ativo": "regua"}})
        piloto.ponte.perguntar(CLICAR_NO_MIC, anotar("clique-2"))
        GLib.timeout_add(700, leu_a_frase_do_dono)
        return False

    def leu_a_frase_do_dono() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("com-a-frase-do-dono"))
        GLib.timeout_add(int(VENCE_EM_S * 1000) + 400, agora_a_recusa)
        return False

    def agora_a_recusa() -> bool:
        # E A RECUSA, PARA COMPARAR OS DOIS TONS no mesmo cartão e no mesmo dia.
        def recusa(ctx, o, p):
            raise RuntimeError("o daemon não confirmou o mudo do microfone")

        por_gesto(recusa)
        piloto.ponte.perguntar(CLICAR_NO_MIC, anotar("clique-3"))
        GLib.timeout_add(700, leu_a_recusa)
        return False

    def leu_a_recusa() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("com-a-recusa"))
        GLib.timeout_add(300, o_gesto_lento)
        return False

    def o_gesto_lento() -> bool:
        # O ESTADO EM VOO, e ele só existe DURANTE. Um gesto instantâneo não tem
        # "durante": o `daemon.reload` do produto leva 9,5 s, e é essa espera que
        # a decisão dela manda anunciar.
        por_gesto(lambda ctx, o, p: (_time.sleep(GESTO_LENTO_S), None)[1])
        piloto.ponte.perguntar(PUBLICAR_O_ROTULO, anotar("rotulo-original"))
        piloto.ponte.perguntar(CLICAR_NO_MIC, anotar("clique-4"))
        GLib.timeout_add(500, no_meio_do_voo)
        return False

    def no_meio_do_voo() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("no-meio-do-voo"))
        GLib.timeout_add(int(GESTO_LENTO_S * 1000) + 700, pousou)
        return False

    def pousou() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-do-pouso"))
        GLib.timeout_add(500, fim)
        return False

    def fim() -> bool:
        fora["desfechos"] = {k: list(v) for k, v in piloto.desfechos.items()}
        fora["deposito"] = {k: [v[0], v[2]] for k, v in piloto._recados.items()}
        Gtk.main_quit()
        return False

    GLib.timeout_add(400, lambda: piloto._ir(args.abre))
    GLib.timeout_add(2000, antes_do_clique)
    # O RELÓGIO DE SEGURANÇA GUARDA O SEU `id` e é desarmado no `finally`: um
    # `timeout_add` pendente depois da fixture dispara DENTRO do laço do PRÓXIMO
    # teste de GUI do mesmo processo. Já matou onze medições de um vizinho.
    guarda = GLib.timeout_add(60000, Gtk.main_quit)
    try:
        # O LAÇO REENTRA ATÉ O ROTEIRO ACABAR, e isto NÃO é zelo — é um defeito
        # MEDIDO em 04/09/2026. Rodada sozinha, esta régua fecha em 17,7 s e
        # passa nos catorze testes; rodada no lote com os 24 vizinhos, ela morria
        # com `o roteiro não chegou ao fim`, faltando **só o último passo**. A
        # causa é a bomba que esta casa já documentou noutro arquivo: um
        # `Gtk.main_quit` pendente de OUTRO teste de GUI do mesmo processo cai
        # DENTRO deste `Gtk.main()` e o encerra no meio.
        #
        # Um `timeout_add` não morre com o `main_quit`, então reentrar no laço
        # retoma o roteiro exatamente de onde ele estava. O relógio de parede é
        # o teto real, e ele é o mesmo de antes.
        #
        # A CONDIÇÃO É A ÚLTIMA ETAPA DO ROTEIRO, E ISSO CUSTOU UMA MEDIÇÃO —
        # 04/09/2026, na integração desta leva. Ela era `"depois-do-pouso" not
        # in fora`, que é a PENÚLTIMA: quem preenche `desfechos` é o `fim()`,
        # agendado 500 ms DEPOIS do `pousou()`. Rodada sozinha a janela dava
        # tempo; rodada no lote, o `main_quit` do vizinho caía exatamente nesses
        # 500 ms, o laço via a condição satisfeita e voltava sem `desfechos` —
        # `KeyError`, reprodutível, e o produto sem defeito nenhum.
        #
        # Esperar pelo penúltimo passo de um roteiro é esperar por quase tudo, e
        # "quase tudo" é o que falha só quando há vizinho.
        limite = _time.monotonic() + 60.0
        while "desfechos" not in fora and _time.monotonic() < limite:
            Gtk.main()
    finally:
        GLib.source_remove(guarda)
        # E O PILOTO TAMBÉM PARA: o tique é um `timeout_add` que se reagenda
        # para sempre, e deixá-lo vivo faria esta janela pintar por cima de todo
        # laço GTK que vier depois, no mesmo processo.
        piloto.pronto = False
        piloto.tela.janela.destroy()
        (hv.mesa_viva.estado_do_daemon, hv.ponte.mic_canal_set_detalhado,
         hv.SEGUNDOS_DO_RECADO_DE_SUCESSO, velho) = guardado
        if velho is None:
            hv.pacotes.GESTOS.pop(chave, None)
        else:
            hv.pacotes.GESTOS[chave] = velho
        MESA["estado"] = ESTADO
    assert "desfechos" in fora, (
        f"o roteiro não chegou ao fim — o que voltou foi {sorted(fora)}. "
        f"O último passo é o `fim()`, e é ele que guarda os `desfechos`: "
        f"esperar por qualquer passo anterior deixa a régua verde sobre uma "
        f"medição pela metade.")
    return fora


def _r(leitura: object) -> list[dict]:
    assert isinstance(leitura, dict), leitura
    return list(leitura["recados"])


def _frases(leitura: object) -> list[str]:
    return [r["texto"] for r in _r(leitura)]


# --------------------------------------------------------------------------
# 0. o gesto deu certo — senão não há o que medir
# --------------------------------------------------------------------------
def test_o_gesto_aplicou(medido: dict) -> None:
    assert medido["clique-1"] == "cliquei", medido["clique-1"]
    assert medido["desfechos"].get("02-controles.html:mudo"), medido["desfechos"]


def test_a_tela_estava_muda_antes(medido: dict) -> None:
    """A LINHA DE BASE. Sem ela, uma página que já tivesse um aviso passaria."""
    assert _frases(medido["antes"]) == [], (
        f"a página já tinha aviso antes do clique: {_frases(medido['antes'])}")


# --------------------------------------------------------------------------
# 1. a frase de sucesso chega ao DOM, e chega ao cartão certo
# --------------------------------------------------------------------------
def test_a_frase_de_sucesso_chega_ao_dom(medido: dict) -> None:
    frases = _frases(medido["depois-do-sucesso"])
    assert frases, (
        "o gesto deu certo e o cartão ficou MUDO. É o defeito que a D-01 fecha: "
        "'aplicado' saía no terminal de quem lançou a janela, e quem clica não "
        "lê terminal.")
    assert medido["produto"]["frase"] in frases[0], (
        f"a frase que chegou não é a do produto: {frases[0]!r}")


def test_a_frase_pousa_no_cartao_de_quem_foi_clicado(medido: dict) -> None:
    """Como a recusa: na coluna do controle em que ela clicou.

    Na mesa de quatro, o sucesso de um no cartão do vizinho é pior que sucesso
    nenhum — é a tela afirmando, sobre um aparelho, um ato que foi de outro.
    """
    (r,) = _r(medido["depois-do-sucesso"])
    assert r["dentro_de"] == "p1", r
    assert r["chave"] == CHAVE_P1, (
        f"o aviso foi endereçado por {r['chave']!r} — a chave é o `uniq` "
        f"normalizado, porque a COLUNA troca de dono e o endereço não.")


def test_o_aviso_sobrevive_aos_tiques(medido: dict) -> None:
    """A tela repinta a cada 100 ms e troca blocos inteiros.

    Um recibo que só existisse no instante do clique não seria visto por
    ninguém — é a mesma razão pela qual este canal é um DEPÓSITO e não um evento.
    """
    assert _frases(medido["depois-de-muitos-tiques"]), (
        "o recibo sumiu depois de ~22 tiques, e não por vencimento")


# --------------------------------------------------------------------------
# 2. o tom — dois desfechos, duas cores, um canal só
# --------------------------------------------------------------------------
def test_o_sucesso_e_verde_e_a_recusa_e_laranja(medido: dict) -> None:
    (sucesso,) = _r(medido["depois-do-sucesso"])
    (recusa,) = _r(medido["com-a-recusa"])
    assert sucesso["tom"] == "sucesso", sucesso
    assert recusa["tom"] == "recusa", recusa
    assert sucesso["cor"] != recusa["cor"], (
        f"os dois desfechos saíram da mesma cor ({sucesso['cor']}) — quem olha "
        f"o cartão não distingue 'deu certo' de 'recusei'.")
    assert sucesso["borda"] != recusa["borda"], (
        "a borda não acompanhou o tom; o aviso fica com a cara do outro")


def test_o_mesmo_cartao_troca_de_tom(medido: dict) -> None:
    """Recusa depois de sucesso, na MESMA chave: a cor tem de acompanhar.

    A chave é o controle, não o desfecho. Sem refazer o estilo quando o tom
    muda, o aviso trocaria de frase e ficaria verde dizendo que recusou.
    """
    (recusa,) = _r(medido["com-a-recusa"])
    assert recusa["chave"] == CHAVE_P1, recusa
    assert recusa["tom"] == "recusa", (
        "o nó reaproveitado ficou com o tom do desfecho anterior")


# --------------------------------------------------------------------------
# 3. a frase do dono do assunto vence a do piloto — é onde a D-12 pousa
# --------------------------------------------------------------------------
def test_a_frase_do_dono_vence(medido: dict) -> None:
    frases = _frases(medido["com-a-frase-do-dono"])
    assert frases == [FRASE_DO_DONO], (
        f"o piloto ignorou a frase que o gesto devolveu e disse a dele: "
        f"{frases}. O piloto é o CANAL; o texto é de quem sabe — é assim que a "
        f"D-12 chega à tela.")


def test_o_recado_nao_vira_endereco_de_pagina(medido: dict) -> None:
    """O ``recado`` sai da carga antes de a resposta ir para a pintura.

    Deixá-lo entrar faria o ``escrever()`` procurar um ``data-campo="recado"``
    que não existe em página nenhuma — e a régua do mockup passaria a contar o
    próprio instrumento como endereço.
    """
    antes = medido["antes"]["enderecos"]
    depois = medido["com-a-frase-do-dono"]["enderecos"]
    assert antes == depois, (
        f"o número de endereços da página mudou de {antes} para {depois} — o "
        f"aviso está sendo contado pela régua do mockup como campo da página.")


# --------------------------------------------------------------------------
# 4. o recibo vence, e vence antes da recusa
# --------------------------------------------------------------------------
def test_o_recibo_vence_e_some(medido: dict) -> None:
    assert _frases(medido["depois-de-vencer"]) == [], (
        f"o recibo continuou na tela depois de vencer: "
        f"{_frases(medido['depois-de-vencer'])}. A palavra dela sobre este "
        f"canal é de 02/09: é aviso, não estado.")


def test_o_prazo_do_sucesso_e_menor_que_o_da_recusa(medido: dict) -> None:
    """Os dois números são decisão dela, e o produto tem de carregá-los.

    A recusa é uma coisa a resolver e fica os 30 s que ela decidiu; o sucesso é
    um recibo, e a informação inteira dele se esgota na leitura.
    """
    p = medido["produto"]
    assert p["recusa"] == 30.0, (
        f"o prazo da recusa saiu de 30 s (decisão dela, 02/09): {p['recusa']}")
    assert 0 < p["sucesso"] < p["recusa"], (
        f"o recibo vive {p['sucesso']} s contra {p['recusa']} s da recusa — "
        f"um recibo que dura tanto quanto o problema vira estado.")


# --------------------------------------------------------------------------
# 5. o botão em voo — a decisão `09` [03]
# --------------------------------------------------------------------------
def test_o_botao_diz_que_esta_trabalhando(medido: dict) -> None:
    antes = medido["antes"]["botao"]
    voando = medido["no-meio-do-voo"]["botao"]
    assert antes and voando, "não achei o botão do microfone no cartão do p1"
    assert not antes["em_voo"], "o botão já nasceu em voo — não há o que medir"
    assert voando["em_voo"], (
        "o botão ficou IGUAL durante a espera. É a decisão `09` [03] em uma "
        "linha: o clique some por segundos e o segundo clique parece o "
        "primeiro.")
    assert voando["voo"], "o botão não foi carimbado com o número do voo"


def test_o_rotulo_publicado_entra_no_lugar(medido: dict) -> None:
    """Quem publica um `data-hef-em-voo` ganha a palavra dentro do botão.

    O texto continua sendo dela — o piloto só o troca. Sem o atributo, o botão
    ganha o sinal da classe e nenhuma palavra inventada.
    """
    voando = medido["no-meio-do-voo"]["botao"]
    assert "Calando" in voando["texto"], (
        f"o rótulo em voo não entrou: {voando['texto']!r}")


def test_o_botao_volta_sozinho_e_volta_inteiro(medido: dict) -> None:
    """E volta com os filhos que tinha.

    O original é guardado como `innerHTML` justamente por isto: os botões desta
    casa têm `<span>` dentro, e devolver só o `textContent` os achataria — o
    botão voltaria da espera diferente de como entrou.
    """
    antes = medido["antes"]["botao"]
    depois = medido["depois-do-pouso"]["botao"]
    assert not depois["em_voo"], (
        "o botão ficou 'trabalhando' depois de o gesto voltar — um botão que "
        "afirma um trabalho que ninguém está fazendo é pior que o silêncio")
    assert depois["voo"] == "", "o carimbo do voo não foi retirado"
    assert depois["texto"] == antes["texto"], (
        f"o rótulo não voltou: {antes['texto']!r} -> {depois['texto']!r}")
    assert depois["filhos"] == antes["filhos"], (
        f"o botão voltou achatado: {antes['filhos']} filhos -> "
        f"{depois['filhos']}")
