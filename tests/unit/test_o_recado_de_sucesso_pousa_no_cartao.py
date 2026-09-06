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

**UM FATO, UM SINAL** — e é a razão inteira de o canal do cartão não se
duplicar. Esta metade continua valendo.

A OUTRA METADE CADUCOU EM 05/09/2026. Este parágrafo dizia que ELA recusara
*o campo que pisca* (aba 03) e *a faixa embaixo da grade* (aba 05), e que esta
régua existia também para que ninguém os construísse. Quem recusou foi o PO,
lendo a D-01 como se ela fechasse a forma — os conflitos C-3 e C-6 são dele. Em
05/09 ela respondeu a `03-Q4` vendo as quatro formas lado a lado e escolheu o
campo que pisca. **A palavra dela vence a leitura que o PO fez da palavra
dela.**

E a piscada não é um segundo canal para o mesmo fato: é o mesmo fato num sinal
mais barato. Desde então o cartão diz só o que tem NOTÍCIA, e o gesto que só
repete o que ela acabou de fazer responde piscando. As duas peças deixaram de
disputar, e esta régua mede as duas.

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
      // A PISCADA DO "DEU CERTO" — 05/09/2026, decisão dela na `03-Q4`.
      deu_certo: b.classList.contains('hef-deu-certo'),
      // A COR VEM DO CSSOM, e não da classe — mesma razão do `cor` dos recados
      // acima: a classe diz que a regra foi ESCRITA, o CSSOM diz que ela PEGOU.
      // Sem isto, arrancar o `!important` da folha deixa a régua verde e o olho
      // sem ver nada, que é o defeito que o `cursor:pointer` já produziu em
      // 04/09 um degrau antes.
      borda: getComputedStyle(b).borderTopColor,
      contorno: getComputedStyle(b).outlineColor,
      contorno_larg: getComputedStyle(b).outlineWidth,
      voo: b.getAttribute('data-hef-voo') || '',
      texto: (b.textContent || '').trim(),
      filhos: b.children.length,
      // A GEOMETRIA, arredondada ao pixel: é a metade da decisão dela que
      // nenhuma leitura de classe mede — *"nada muda de lugar"*. É o que separa
      // o `outline` (que não ocupa espaço) de uma borda mais grossa.
      caixa: (function(r){ return {x: Math.round(r.x), y: Math.round(r.y),
                                   larg: Math.round(r.width),
                                   alt: Math.round(r.height)}; })(
               b.getBoundingClientRect()),
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


#: O PERFIL ATIVO PRECISA EXISTIR NO DISCO — 05/09/2026. Desde que a aba 02
#: aprendeu a GUARDAR o som por controle, o gesto lê o perfil ativo para
#: escrever nele; sem arquivo, ele recusa com *"o ajuste chegou ao controle,
#: mas não consegui ler o perfil"* — e a recusa está CERTA: dizer "Pronto."
#: sobre um ajuste que amanhã volta ao de ontem seria a mentira que a frase
#: existe para evitar. O que faltava era esta régua ter um perfil.
#: `scope="module"` PORQUE O PILOTO TAMBÉM É — uma fixture de função
#: correria DEPOIS da `medido`, que abre a janela, e o perfil chegaria
#: tarde. Autouse do mesmo escopo corre antes das outras.
@pytest.fixture(scope="module", autouse=True)
def _perfil_ativo_no_disco() -> None:
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    profiles_dir().mkdir(parents=True, exist_ok=True)
    for nome in ("regua", "Bancada"):
        if not (profiles_dir() / f"{nome.lower()}.json").exists():
            loader.save_profile(Profile(name=nome, match=MatchManual()),
                                origem="regua")


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
        # A PISCADA É DELA E TEM DONO: sem ler o valor do produto aqui, trocar
        # 1500 por 15 deixaria a régua verde, porque ela só mede "acendeu" e
        # "apagou". O número entra na MENSAGEM de erro, que é onde ele serve.
        "piscada_ms": int(hv.MS_DA_PISCADA),
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
# 1. o sucesso CALADO pisca e não fala — e o que ele guarda é o mesmo defeito
# --------------------------------------------------------------------------
def test_o_sucesso_calado_pisca_e_nao_fala(medido: dict) -> None:
    """A PERGUNTA FOI INVERTIDA EM 05/09/2026, e a medição é a mesma.

    Ela era `test_a_frase_de_sucesso_chega_ao_dom` e exigia o ``"Pronto."`` no
    DOM. O defeito de origem que ela guarda continua sendo *o gesto deu certo e
    o cartão ficou MUDO* — "aplicado" saía no terminal de quem lançou a janela,
    e quem clica não lê terminal. O que mudou é a RESPOSTA, por decisão dela na
    `03-Q4`:

        *"O campo que você acabou de mexer ganha uma borda verde por cerca de um
        segundo e meio e volta ao normal sozinho; nada muda de lugar e nenhuma
        palavra nova entra na tela."*

    O gesto deste trecho é o `mic.set` PASSANDO, e `frase_do_ato_do_microfone`
    devolve `None` no caminho de sucesso — não há notícia. Então a tela pisca.

    AS DUAS ASSERÇÕES, e nenhuma vale sozinha: o botão com a classe (a tela
    respondeu) e o DOM sem frase (a palavra saiu). Sem a segunda, o Passo 4
    poderia entrar com o ``"Pronto."`` ainda na tela e esta régua não veria.
    """
    botao = medido["depois-do-sucesso"]["botao"]
    assert botao and botao["deu_certo"], (
        "o gesto deu certo e o campo não piscou — é o defeito que a D-01 fecha, "
        f"na forma que ela escolheu na 03-Q4: {botao}")
    # E A REGRA TEM DE PEGAR, não só existir. Comparado contra o MESMO botão
    # antes do clique, que é a régua independente — não há verde digitado aqui.
    #
    # O QUE ESTA LINHA **NÃO** PROVA, e a ausência é medida (05/09/2026):
    # arrancar o `!important` da folha e rodar esta régua dá VERDE. O botão que
    # ela clica (`.mudo-i`, apagado) não declara `border-color` própria, então a
    # folha de usuário vence sem precisar do `!important`. Quem provaria são os
    # elementos que declaram cor: `.mudo-i.on` (`02-controles.html:1420`, que
    # pede `var(--red)`) e `select.modo` (`03-gatilhos.html:1050`, que pede
    # `var(--purple)`) — e nenhum dos dois está no caminho deste clique.
    #
    # O `!important` FICA MESMO ASSIM, e não por precaução: a mesma folha já
    # pagou exatamente este preço em 04/09, quando o `cursor` saiu `pointer` e
    # não `progress` porque as dez páginas declaram `cursor` nos botões. É a
    # mesma classe de defeito, medida, no mesmo arquivo.
    antes = medido["antes"]["botao"]
    assert botao["borda"] != antes["borda"] or botao["contorno_larg"] != antes["contorno_larg"], (
        "a classe entrou e a tela não mudou de cor — o `!important` da folha "
        f"não pegou: antes={antes['borda']}/{antes['contorno_larg']} "
        f"durante={botao['borda']}/{botao['contorno_larg']}")
    assert _frases(medido["depois-do-sucesso"]) == [], (
        "o gesto não trouxe notícia e a tela falou mesmo assim — a palavra nova "
        f"é o que a decisão dela tirou: {_frases(medido['depois-do-sucesso'])}")


def test_a_piscada_apaga_sozinha(medido: dict) -> None:
    """~2,9 s depois do clique a classe saiu, e o `data-hef-voo` não ficou.

    Um campo que ficasse verde para sempre afirmaria um clique de dez minutos
    atrás — a mesma doença do botão que fica em voo, que o piloto já nomeia.

    E O ATRIBUTO ÓRFÃO É A SEGUNDA METADE: se o `data-hef-voo` sobrevivesse à
    piscada, o pouso seguinte acharia DOIS elementos com o mesmo número e
    devolveria o rótulo errado a um deles. É por isso que a retirada agendada
    procura pela CLASSE, e o número sai antes.
    """
    botao = medido["depois-de-muitos-tiques"]["botao"]
    assert botao and not botao["deu_certo"], (
        f"a piscada não apagou sozinha em {medido['produto']['piscada_ms']} ms: {botao}")
    assert botao["voo"] == "", (
        f"o número do voo ficou para trás no elemento: {botao}")


def test_a_piscada_nao_acende_na_recusa(medido: dict) -> None:
    """Recusa é laranja, e o campo NÃO pisca verde.

    É a régua do Passo 2: sem o desfecho no pouso, o `voltouDoVoo` piscaria
    verde em cima de um cartão laranja — a tela dizendo as duas coisas de uma
    vez sobre o mesmo clique.
    """
    botao = medido["com-a-recusa"]["botao"]
    assert botao and not botao["deu_certo"], (
        f"o gesto levantou e o campo piscou verde mesmo assim: {botao}")
    tons = [r["tom"] for r in medido["com-a-recusa"]["recados"]]
    assert "recusa" in tons or "erro" in tons, (
        f"a recusa não chegou ao cartão — o outro lado da mesma medição: {tons}")


def test_o_pisca_nao_move_a_tela(medido: dict) -> None:
    """A metade da decisão dela que nenhuma leitura de classe mede.

        *"nada muda de lugar"*

    É o que separa o `outline` (que não ocupa espaço na caixa) de uma borda mais
    grossa, que empurraria o vizinho. A comparação é do MESMO elemento, antes do
    clique e com a piscada acesa, na mesma unidade.
    """
    antes = medido["antes"]["botao"]
    piscando = medido["depois-do-sucesso"]["botao"]
    assert antes and piscando, (antes, piscando)
    assert piscando["deu_certo"], "a foto do 'durante' não pegou a piscada acesa"
    assert antes["caixa"] == piscando["caixa"], (
        "a piscada mexeu na geometria do campo — `outline` não ocupa espaço, "
        f"borda ocupa: antes={antes['caixa']} durante={piscando['caixa']}")


def test_a_frase_pousa_no_cartao_de_quem_foi_clicado(medido: dict) -> None:
    """Como a recusa: na coluna do controle em que ela clicou.

    Na mesa de quatro, o sucesso de um no cartão do vizinho é pior que sucesso
    nenhum — é a tela afirmando, sobre um aparelho, um ato que foi de outro.

    A LEITURA MUDOU EM 05/09/2026, E A MEDIÇÃO NÃO. Ela lia o
    `depois-do-sucesso`, que é o gesto CALADO — e desde a `03-Q4` ele não
    deposita frase nenhuma, ele pisca. A pergunta *"em que cartão pousa uma
    frase de sucesso"* continua inteira: o que mudou é onde há uma frase de
    sucesso para medir, e é o `com-a-frase-do-dono`, o gesto que devolve
    `{"recado": …}`.
    """
    (r,) = _r(medido["com-a-frase-do-dono"])
    assert r["dentro_de"] == "p1", r
    assert r["chave"] == CHAVE_P1, (
        f"o aviso foi endereçado por {r['chave']!r} — a chave é o `uniq` "
        f"normalizado, porque a COLUNA troca de dono e o endereço não.")


def test_o_aviso_sobrevive_aos_tiques(medido: dict) -> None:
    """A tela repinta a cada 100 ms e troca blocos inteiros.

    Um recibo que só existisse no instante do clique não seria visto por
    ninguém — é a mesma razão pela qual este canal é um DEPÓSITO e não um evento.

    ELA MEDE O RECIBO DA RECUSA desde 05/09/2026, e a razão é a mesma da irmã
    acima: o sucesso calado não deposita mais nada, então não há recibo dele a
    sobreviver. A recusa deposita, dura 30 s, e atravessa os tiques da mesma
    forma — o depósito é um só. **O `com-a-recusa` é lido 700 ms depois do
    clique e o `depois-do-pouso` uns 3 s depois**, com a repintura correndo por
    cima o tempo todo: é o mesmo "sobreviveu aos tiques" que ela sempre mediu.
    """
    assert _frases(medido["depois-do-pouso"]), (
        "o recibo sumiu com a repintura, e não por vencimento")


# --------------------------------------------------------------------------
# 2. o tom — dois desfechos, duas cores, um canal só
# --------------------------------------------------------------------------
def test_o_sucesso_e_verde_e_a_recusa_e_laranja(medido: dict) -> None:
    """Os dois tons do cartão, e eles não mudaram.

    A leitura do lado do sucesso passou do `depois-do-sucesso` para o
    `com-a-frase-do-dono` em 05/09/2026, pela razão escrita em
    `test_a_frase_pousa_no_cartao_de_quem_foi_clicado`: o sucesso CALADO não
    deposita mais, e um sucesso com NOTÍCIA continua depositando igual.
    """
    (sucesso,) = _r(medido["com-a-frase-do-dono"])
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


def test_o_numero_da_piscada_e_o_mesmo_nos_dois_lados() -> None:
    """A segunda régua do dono impossível — o Python e o JavaScript concordam.

    `MS_DA_PISCADA` não pode ser interpolado no `BOOTSTRAP`: ele é uma string
    CRUA de aspas triplas, e **cinco réguas desta casa a extraem do fonte** por
    uma regex ancorada no fecho, para rodá-la mutilada num WebKit. Um
    `.replace()` colado nesse fecho quebra a âncora, e a regex passa a engolir o
    Python que vem depois — medido em 05/09/2026, e o sintoma foram 41 erros de
    `SyntaxError` no bootstrap, que não se leem como "alguém mexeu na
    constante". Uma f-string também não serve: o JS é cheio de chaves.

    Então o número vive nos dois sítios, e esta linha é o que impede que eles se
    afastem. É a mesma forma de `PRIORIDADE_SESSAO_DA_PONTE`, que convive com um
    `.conf` do WirePlumber pela mesma impossibilidade.
    """
    import re

    import hefesto_vivo as hv

    achados = re.findall(r"\}, (\d+)\);", hv.BOOTSTRAP)
    assert achados, "o `setTimeout` da piscada sumiu do BOOTSTRAP"
    assert str(hv.MS_DA_PISCADA) in achados, (
        f"o Python diz {hv.MS_DA_PISCADA} ms e o JavaScript diz {achados} — "
        "a piscada duraria o que a tela mandasse, não o que ela decidiu")
