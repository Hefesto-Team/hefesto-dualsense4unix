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

O TEMPO É CONDIÇÃO, NÃO RELÓGIO — FLAKE-DO-PISCA, 13/09/2026. Os marcos do
roteiro eram ``GLib.timeout_add`` de tempo FIXO (700 ms, 2200 ms, o prazo mais
400), e sob carga o produto atravessa essas janelas mais devagar que o relógio.
Medido com ``stress-ng --cpu 64`` em 16 núcleos: **4 voltas reprovadas em 20**,
sempre as mesmas três réguas — o gesto ainda em voo aos 700 ms, e a piscada
ainda acesa aos 2,9 s porque o pouso veio tarde (o primeiro pouso chegou a
levar 2,6 s). Produto sem defeito nenhum. Com as esperas, alternada com a
versão velha sob a mesma carga, nenhuma reprova. E sem carga nenhuma, um gesto
1,6 s mais lento reprova a versão velha nas mesmas três e deixa esta verde.

Agora cada marco ESPERA PELA CONDIÇÃO dele, com teto (``TETO_S``) e com a frase
do que não chegou (``_leitura``). O voo e a piscada são estados de PASSAGEM, e
quem os fotografa é o vigia (``_VIGIA``), no instante em que o botão muda — a
pergunta avulsa só os pegaria se chegasse dentro da janela deles, que é o
defeito inteiro. O que é estado que FICA (a frase no cartão, o botão de volta)
é perguntado até aparecer.

AS SETE COISAS QUE ESTA RÉGUA COBRAVA — E AS CINCO PRIMEIRAS MUDARAM DE CONTRATO
EM 13/09/2026 (TELA-CALADA-01). Pela palavra dela, *"essas frases de status que
aparecem no rodapé isso não deveria estar aparecendo"*, *"em todas as abas da
interface"*, o gesto que deu certo não põe frase na tela — nem a do dono do
assunto: ela vai ao diário da janela. A régua do contrato novo é
``test_a_tela_nao_narra_o_gesto_que_deu_certo``; aqui os itens 1 a 5 viraram o
avesso, e as esperas por condição da FLAKE-DO-PISCA continuam as mesmas:

1. **a frase de sucesso NÃO chega ao DOM** (até 13/09 chegava);
2. **ela não pousa em cartão nenhum** (até 13/09 pousava no do controle);
3. **não há nó verde** — a recusa continua no tom dela, com um tom só;
4. **a frase do DONO DO ASSUNTO também não entra**, e o ``recado`` continua
   sem vazar para a pintura como se fosse endereço de página;
5. **não há recibo a vencer** — nem no pouso, nem depois do prazo;
6. **o botão fica em voo enquanto o gesto está no ar**, com a classe e com o
   rótulo que a página publicar;
7. **ele volta sozinho**, e volta INTEIRO — com os filhos que tinha.

A MORDIDA: devolva o depósito de tom ``sucesso`` em ``_deu_certo_dizendo`` e
os casos 1 a 5 reprovam; apague o ``em_voo(alvo)`` do ouvinte e o botão fica
igual durante os dois segundos de espera. E A DO TEMPO: devolva os marcos de
tempo fixo e rode sob a carga acima — reprova; com as esperas por condição,
verde sob a mesma carga.
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

#: QUANTO DO GESTO LENTO CORRE ANTES DE A RÉGUA LER O BOTÃO — meio segundo de
#: repintura por cima do botão em voo. É PISO, e não marco: a leitura acontece
#: DENTRO do gesto (ver `o_gesto_lento`), então a carga pode atrasá-la e não
#: pode fazê-la cair depois do pouso.
MEIO_DO_VOO_S = 0.5

#: O PASSO DA ESPERA POR CONDIÇÃO. A pergunta seguinte só sai DEPOIS de a
#: anterior voltar, então sob carga elas não se empilham.
PASSO_MS = 50

#: O TETO DE CADA ESPERA — generoso de propósito, e continua sendo régua: um
#: gesto que nunca pousa, uma piscada que nunca apaga ou uma frase que nunca
#: vence reprovam dizendo QUAL marco não chegou.
TETO_S = 10.0

#: O TETO DA PRIMEIRA ESPERA, a da página de pé: carregar a `02` e instalar a
#: ponte é o passo mais pesado do roteiro, e é o que a carga mais atrasa.
TETO_DA_PAGINA_S = 30.0

#: O TETO DO ROTEIRO INTEIRO. Com o produto quebrado cada espera pode gastar o
#: seu teto, e a reprova tem de sair nomeando o marco — não morrer no relógio
#: de parede com "o roteiro não chegou ao fim".
TETO_DO_ROTEIRO_S = 120.0

#: QUANTO A PISCADA PODE PASSAR DE `MS_DA_PISCADA`, no relógio da página. O
#: `setTimeout` que a apaga nunca dispara ANTES; sob carga dispara depois —
#: medido sob `stress-ng --cpu 64`, até 79 ms além.
FOLGA_DA_PISCADA_MS = 1500

#: A FRASE QUE O DONO DO ASSUNTO MANDA. É a forma da D-12, e ela chega pelo
#: retorno do gesto — o piloto não a inventa nem a conhece.
FRASE_DO_DONO = "o microfone ligou, mas o canal dele está mudo no sistema"

#: A LEITURA DO DOM, e ela é UMA para os dois instrumentos: a pergunta avulsa
#: (`LER_A_TELA`) e a foto que o vigia tira no instante da mudança. Duas
#: leituras escritas à mão divergiriam, e a régua compararia coisas diferentes.
_LEITURA = r"""
function(){
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
  return {
    // O RELÓGIO DA PÁGINA, o mesmo do `setTimeout` que apaga a piscada. É ele
    // que mede quanto ela durou: o do Python somaria o atraso da pergunta.
    t: performance.now(),
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
  };
}
"""

LER_A_TELA = "(function(){ return JSON.stringify((" + _LEITURA + ")()); })()"

#: O VIGIA DO BOTÃO — a peça que tira a régua do relógio (FLAKE-DO-PISCA).
#:
#: O VOO E A PISCADA SÃO ESTADOS DE PASSAGEM. Uma pergunta avulsa só os pega se
#: chegar dentro da janela deles, e sob carga ela chega fora: aos 700 ms o gesto
#: ainda voava, aos 2,9 s a piscada ainda estava acesa. Esperar "mais tempo" só
#: troca a janela que falha.
#:
#: O `MutationObserver` entrega a mudança num microtask logo depois do script
#: que a fez — antes de qualquer outra tarefa da página, o `setTimeout` que
#: apaga a piscada incluído. Então a foto do pouso SEMPRE pega a piscada que o
#: pouso acendeu, com a carga que for.
#:
#: SÓ ANOTA QUANDO O BOTÃO MUDA: a repintura mexe no documento dez vezes por
#: segundo, e a assinatura barata evita uma leitura cheia por tique. E ele
#: confere a PONTE neste documento — o `pronto` do piloto é do documento em que
#: ele instalou, e uma carga nova de página a leva embora.
_VIGIA = r"""
function(ler){
  if(!(window.__hef && window.__hef.voltouDoVoo)) return 'sem ponte';
  const seletor = '[data-controle="p1"] [data-mudo="microfone"]';
  if(!document.querySelector(seletor)) return 'sem botão';
  if(window.__reguaTrilha) return 'vigiando';
  const trilha = window.__reguaTrilha = [];
  let visto = null;
  function anotar(){
    const b = document.querySelector(seletor);
    const assinatura = b
      ? b.className + '|' + (b.getAttribute('data-hef-voo') || '') + '|' + b.innerHTML
      : '';
    if(assinatura === visto) return;
    visto = assinatura;
    trilha.push(ler());
  }
  new MutationObserver(anotar).observe(document.documentElement,
    {subtree: true, childList: true, attributes: true, characterData: true});
  anotar();
  return 'vigiando';
}
"""

VIGIAR_O_BOTAO = "JSON.stringify((" + _VIGIA + ")(" + _LEITURA + "))"

#: O CLIQUE, no 🎙 do cartão do p1 — o botão do produto, com o `data-mudo` que a
#: página publicada traz. Clicar por coordenada é a armadilha que esta casa já
#: pagou duas vezes. O MARCO entra na trilha ANTES do clique, e é por ele que a
#: espera separa o voo deste clique do voo do anterior.
_CLICAR_NO_MIC = r"""
function(marco){
  const b = document.querySelector('[data-controle="p1"] [data-mudo="microfone"]');
  if(!b) return 'NAO ACHEI O BOTAO DO MICROFONE NO CARTAO DO P1';
  if(!window.__reguaTrilha) return 'SEM O VIGIA — o clique não teria marco na trilha';
  window.__reguaTrilha.push({marco: marco, t: performance.now()});
  b.click();
  return 'cliquei';
}
"""

#: AS FOTOS DE UM CLIQUE: da marca dele até a marca do próximo.
_TRILHA_DESDE = r"""
function(marco){
  const trilha = window.__reguaTrilha || [];
  let i = trilha.length - 1;
  while(i >= 0 && trilha[i].marco !== marco) i -= 1;
  if(i < 0) return JSON.stringify(null);
  let fim = i + 1;
  while(fim < trilha.length && trilha[fim].marco === undefined) fim += 1;
  return JSON.stringify(trilha.slice(i + 1, fim));
}
"""


def _clicar_no_mic(marco: str) -> str:
    return "(" + _CLICAR_NO_MIC + ")(" + json.dumps(marco) + ")"


def _trilha_desde(marco: str) -> str:
    return "(" + _TRILHA_DESDE + ")(" + json.dumps(marco) + ")"


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


def _pouso(trilha: object) -> dict | None:
    """A foto em que o 🎙 SAIU do voo depois de ter entrado nele — ou nada ainda.

    É a condição de quase todo marco deste roteiro, e é a que a sprint nomeia:
    *o campo sair de `hef-em-voo`*. A foto é do INSTANTE do pouso, tirada pelo
    vigia no mesmo passo em que o `voltouDoVoo` tirou a classe — e é por isso
    que ela traz a piscada acesa sem depender de a pergunta chegar a tempo.

    O QUE SE LÊ É O CARIMBO (`data-hef-voo`), e não a classe: os dois entram no
    mesmo passo e saem no mesmo passo. Medido por mordida em 13/09/2026 —
    lendo a classe, arrancá-la do ouvinte reprovava DOZE réguas (as de frase
    inclusive, que nada têm com o voo); lendo o carimbo, reprova só a do voo.
    """
    voou = False
    for foto in trilha if isinstance(trilha, list) else []:
        botao = foto.get("botao")
        if botao is None:
            continue
        if botao["voo"]:
            voou = True
        elif voou:
            return foto
    return None


def _apagou(trilha: object) -> dict | None:
    """A foto em que a piscada do pouso apagou, com quanto ela durou.

    As duas pontas da duração são do relógio da PÁGINA — o do `setTimeout` que
    apaga. Sem piscada no pouso não há o que apagar, e a espera vence no teto:
    a régua irmã já reprova o pouso que não piscou.
    """
    fotos = trilha if isinstance(trilha, list) else []
    pouso = _pouso(fotos)
    if pouso is None or not pouso["botao"]["deu_certo"]:
        return None
    for foto in fotos[fotos.index(pouso) + 1:]:
        botao = foto.get("botao")
        if botao is not None and not botao["deu_certo"]:
            return dict(foto, piscada_ms=round(foto["t"] - pouso["t"]))
    return None


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
    """Abre o piloto DE VERDADE, oculto, e roda o roteiro — marco a marco, por condição."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    import argparse
    import threading
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
    #: O QUE NÃO CHEGOU, por marco — é daqui que `_leitura` tira a reprova.
    faltou: dict[str, str] = {}
    #: QUANTO CADA ESPERA LEVOU, para quem for recalibrar um teto.
    esperas_s: dict[str, float] = {}
    fora: dict[str, object] = {"produto": do_produto, "faltou": faltou,
                               "esperas_s": esperas_s}
    # O ROTEIRO PARA DE PERGUNTAR QUANDO A FIXTURE FECHA. Uma espera pendente
    # que acordasse depois do `destroy` perguntaria a uma janela que já não
    # existe — dentro do laço do PRÓXIMO teste de GUI do mesmo processo.
    no_ar = {"sim": True}

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

    def esperar(marco: str, pergunta: str, achar, depois, o_que: str,
                teto_s: float = TETO_S) -> None:
        """UMA espera por condição: pergunta, e só segue quando `achar` achar.

        `achar` recebe a resposta já lida do JSON e devolve o que guardar no
        marco — ou `None`, para perguntar de novo. No teto o roteiro SEGUE, e o
        marco fica em `faltou` com a frase do que não chegou: as outras réguas
        continuam medindo o que é delas, e a deste marco reprova dizendo o quê.
        """
        comeco = _time.monotonic()

        def perguntar() -> bool:
            if no_ar["sim"]:
                piloto.ponte.perguntar(pergunta, respondeu)
            return False

        def respondeu(valor, erro) -> None:
            if not no_ar["sim"]:
                return
            leitura = None
            if erro is None and valor is not None:
                try:
                    leitura = json.loads(str(valor))
                except ValueError:
                    leitura = None
            achado = None if leitura is None else achar(leitura)
            gasto = _time.monotonic() - comeco
            if achado is not None:
                fora[marco] = achado
                esperas_s[marco] = round(gasto, 2)
                depois()
            elif gasto >= teto_s:
                visto = f"ERRO {erro}" if erro is not None else repr(leitura)
                faltou[marco] = (f"{o_que} — não chegou em {teto_s:.0f} s; a "
                                 f"última leitura foi …{visto[-500:]}")
                depois()
            else:
                GLib.timeout_add(PASSO_MS, perguntar)

        perguntar()

    def comecar() -> bool:
        piloto._ir(args.abre)
        # A PÁGINA TEM DE ESTAR PRONTA, e não "já deve ter carregado": sem o
        # bootstrap o `el.click()` acha o botão sem ouvinte que responda — o
        # clique some, calado. Já custou uma medição a esta casa.
        esperar("vigia", VIGIAR_O_BOTAO,
                lambda v: v if v == "vigiando" and piloto.pronto else None,
                o_sucesso_calado,
                "a página 02 de pé, com a ponte do piloto e o 🎙 do p1",
                teto_s=TETO_DA_PAGINA_S)
        return False

    def o_sucesso_calado() -> None:
        piloto.ponte.perguntar(LER_A_TELA, ler("antes"))
        piloto.ponte.perguntar(_clicar_no_mic("clique-1"), anotar("clique-1"))
        esperar("depois-do-sucesso", _trilha_desde("clique-1"), _pouso,
                a_piscada_apaga, "o 🎙 pousar (o carimbo `data-hef-voo` sair) depois do clique 1")

    def a_piscada_apaga() -> None:
        # A PISCADA DO POUSO APAGA SOZINHA, com a repintura correndo por cima
        # o tempo todo.
        esperar("depois-de-muitos-tiques", _trilha_desde("clique-1"), _apagou,
                com_a_frase_do_dono,
                "a piscada do clique 1 acender no pouso e apagar sozinha")

    def com_a_frase_do_dono() -> None:
        # A FRASE DO DONO DO ASSUNTO, pelo retorno do gesto. É a forma da D-12.
        # Até 13/09/2026 o `_depositar` a pintava NA HORA e antes do pouso, e a
        # foto do pouso a trazia no cartão. Desde a TELA-CALADA-01 o sucesso não
        # deposita: a foto do pouso é a prova de que o cartão ficou como estava.
        por_gesto(lambda ctx, o, p: {"recado": FRASE_DO_DONO,
                                     "mesa": {"perfil-ativo": "regua"}})
        piloto.ponte.perguntar(_clicar_no_mic("clique-2"), anotar("clique-2"))
        esperar("com-a-frase-do-dono", _trilha_desde("clique-2"), _pouso,
                a_frase_vence, "o 🎙 pousar (o carimbo `data-hef-voo` sair) depois do clique 2")

    def a_frase_vence() -> None:
        # E O 🎙 EM REPOUSO ANTES DO PRÓXIMO CLIQUE: o gesto da frase também
        # pisca, e sem frase no cartão a espera terminaria na hora — a recusa
        # pousaria com a piscada do clique 2 ainda acesa e pareceria piscar
        # verde. Medido por mordida em 13/09/2026; o relógio fixo de antes
        # escondia isto esperando 3,4 s.
        esperar("depois-de-vencer", LER_A_TELA,
                lambda leitura: leitura if (
                    not _frases(leitura) and leitura["botao"]
                    and not leitura["botao"]["deu_certo"]) else None,
                agora_a_recusa,
                f"a frase do dono sair do cartão ({VENCE_EM_S:.0f} s de prazo "
                f"nesta medição), com o 🎙 em repouso",
                teto_s=VENCE_EM_S + TETO_S)

    def agora_a_recusa() -> None:
        # E A RECUSA, PARA COMPARAR OS DOIS TONS no mesmo cartão e no mesmo dia.
        def recusa(ctx, o, p):
            raise RuntimeError("o daemon não confirmou o mudo do microfone")

        por_gesto(recusa)
        piloto.ponte.perguntar(_clicar_no_mic("clique-3"), anotar("clique-3"))
        esperar("com-a-recusa", _trilha_desde("clique-3"), _pouso,
                o_gesto_lento,
                "o 🎙 pousar (o carimbo `data-hef-voo` sair) depois do clique 3, o que recusa")

    def o_gesto_lento() -> None:
        # O ESTADO EM VOO, e ele só existe DURANTE. Um gesto instantâneo não tem
        # "durante": o `daemon.reload` do produto leva 9,5 s, e é essa espera que
        # a decisão dela manda anunciar.
        #
        # A LEITURA MORA DENTRO DO GESTO, e é o que a torna imune à carga: o
        # pouso só é agendado quando o gesto volta, e o gesto só volta depois de
        # a leitura voltar. As duas atravessam a mesma fila até a página, na
        # ordem — a foto é DURANTE o voo por construção, não por relógio.
        def lento(ctx, o, p):
            leu = threading.Event()

            def ler_no_voo() -> bool:
                def _leu(valor, erro):
                    ler("no-meio-do-voo")(valor, erro)
                    leu.set()

                if no_ar["sim"]:
                    piloto.ponte.perguntar(LER_A_TELA, _leu)
                return False

            _time.sleep(MEIO_DO_VOO_S)
            GLib.idle_add(ler_no_voo)
            if not leu.wait(TETO_S):
                faltou["no-meio-do-voo"] = (
                    f"a leitura do botão durante o gesto lento — não voltou em "
                    f"{TETO_S:.0f} s")
            _time.sleep(max(0.0, GESTO_LENTO_S - MEIO_DO_VOO_S))

        por_gesto(lento)
        piloto.ponte.perguntar(PUBLICAR_O_ROTULO, anotar("rotulo-original"))
        piloto.ponte.perguntar(_clicar_no_mic("clique-4"), anotar("clique-4"))
        esperar("pouso-do-lento", _trilha_desde("clique-4"), _pouso,
                depois_do_pouso,
                "o 🎙 pousar (o carimbo `data-hef-voo` sair) depois do gesto lento",
                teto_s=GESTO_LENTO_S + 2 * TETO_S)

    def depois_do_pouso() -> None:
        # O QUE SE LÊ AQUI É ESTADO QUE FICA — o botão fora do voo, o rótulo
        # devolvido, a recusa viva por 30 s. Por isso o meio segundo
        # abaixo é PISO e não marco: a carga só pode atrasá-lo, e atrasar não
        # muda nenhuma destas leituras. É a repintura correndo por cima do botão
        # que acabou de voltar.
        #
        # E O `fim()` MORA NA RESPOSTA, não num relógio depois da pergunta: um `fim()`
        # agendado podia fechar o laço antes de a leitura voltar, e o marco
        # sumia com a janela.
        def ler_e_fechar(valor, erro) -> None:
            ler("depois-do-pouso")(valor, erro)
            fim()

        def perguntar() -> bool:
            if no_ar["sim"]:
                piloto.ponte.perguntar(LER_A_TELA, ler_e_fechar)
            return False

        GLib.timeout_add(500, perguntar)

    def fim() -> None:
        fora["desfechos"] = {k: list(v) for k, v in piloto.desfechos.items()}
        fora["deposito"] = {k: [v[0], v[2]] for k, v in piloto._recados.items()}
        Gtk.main_quit()

    GLib.timeout_add(400, comecar)
    # O RELÓGIO DE SEGURANÇA GUARDA O SEU `id` e é desarmado no `finally`: um
    # `timeout_add` pendente depois da fixture dispara DENTRO do laço do PRÓXIMO
    # teste de GUI do mesmo processo. Já matou onze medições de um vizinho.
    guarda = GLib.timeout_add(int(TETO_DO_ROTEIRO_S * 1000), Gtk.main_quit)
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
        # o teto real: `TETO_DO_ROTEIRO_S`.
        #
        # A CONDIÇÃO É A ÚLTIMA ETAPA DO ROTEIRO, E ISSO CUSTOU UMA MEDIÇÃO —
        # 04/09/2026, na integração desta leva. Ela era `"depois-do-pouso" not
        # in fora`, que é a PENÚLTIMA: quem preenche `desfechos` é o `fim()`.
        # Rodada sozinha a janela dava tempo; rodada no lote, o `main_quit` do
        # vizinho caía exatamente entre as duas, o laço via a condição
        # satisfeita e voltava sem `desfechos` — `KeyError`, reprodutível, e o
        # produto sem defeito nenhum.
        #
        # Esperar pelo penúltimo passo de um roteiro é esperar por quase tudo, e
        # "quase tudo" é o que falha só quando há vizinho.
        limite = _time.monotonic() + TETO_DO_ROTEIRO_S
        while "desfechos" not in fora and _time.monotonic() < limite:
            Gtk.main()
    finally:
        no_ar["sim"] = False
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
        f"o roteiro não chegou ao fim — o que voltou foi {sorted(fora)}, e o "
        f"que não chegou foi {faltou}. O último passo é o `fim()`, e é ele que "
        f"guarda os `desfechos`: esperar por qualquer passo anterior deixa a "
        f"régua verde sobre uma medição pela metade.")
    return fora


def _leitura(medido: dict, marco: str) -> dict:
    """A foto de um marco do roteiro — ou a reprova dizendo o que não chegou.

    Cada marco é uma espera por condição com teto. Quando o teto vence, a foto
    não existe, e `medido[marco]` daria um `KeyError` que não diz nada: aqui
    sai, no lugar dele, a frase do que o produto não fez.
    """
    falta = medido["faltou"].get(marco)
    assert falta is None, f"o marco `{marco}` não chegou: {falta}"
    assert marco in medido, (
        f"o roteiro não passou pelo marco `{marco}`: {sorted(medido)}")
    return medido[marco]


def _r(leitura: object) -> list[dict]:
    assert isinstance(leitura, dict), leitura
    return list(leitura["recados"])


def _frases(leitura: object) -> list[str]:
    return [r["texto"] for r in _r(leitura)]


# --------------------------------------------------------------------------
# 0. o gesto deu certo — senão não há o que medir
# --------------------------------------------------------------------------
def test_o_gesto_aplicou(medido: dict) -> None:
    assert _leitura(medido, "vigia") == "vigiando"
    assert medido["clique-1"] == "cliquei", medido["clique-1"]
    assert medido["desfechos"].get("02-controles.html:mudo"), medido["desfechos"]


def test_a_tela_estava_muda_antes(medido: dict) -> None:
    """A LINHA DE BASE. Sem ela, uma página que já tivesse um aviso passaria."""
    antes = _leitura(medido, "antes")
    assert _frases(antes) == [], (
        f"a página já tinha aviso antes do clique: {_frases(antes)}")


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

    A FOTO É DO INSTANTE DO POUSO desde 13/09/2026 (FLAKE-DO-PISCA), e o DOM
    sem frase é conferido duas vezes: no pouso e quando a piscada apaga, um
    segundo e meio de repintura depois. Uma frase que só o tique trouxesse
    apareceria na segunda.
    """
    botao = _leitura(medido, "depois-do-sucesso")["botao"]
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
    antes = _leitura(medido, "antes")["botao"]
    assert botao["borda"] != antes["borda"] or botao["contorno_larg"] != antes["contorno_larg"], (
        "a classe entrou e a tela não mudou de cor — o `!important` da folha "
        f"não pegou: antes={antes['borda']}/{antes['contorno_larg']} "
        f"durante={botao['borda']}/{botao['contorno_larg']}")
    # A SEGUNDA FOTO SÓ ENTRA SE CHEGOU: a piscada que não apaga é da régua
    # irmã, e não deste "não fala".
    marcos = ["depois-do-sucesso"]
    if "depois-de-muitos-tiques" not in medido["faltou"]:
        marcos.append("depois-de-muitos-tiques")
    for marco in marcos:
        frases = _frases(_leitura(medido, marco))
        assert frases == [], (
            "o gesto não trouxe notícia e a tela falou mesmo assim — a palavra "
            f"nova é o que a decisão dela tirou ({marco}): {frases}")


def test_a_piscada_apaga_sozinha(medido: dict) -> None:
    """A classe saiu sozinha, durou o que o produto diz, e o `data-hef-voo` não ficou.

    Um campo que ficasse verde para sempre afirmaria um clique de dez minutos
    atrás — a mesma doença do botão que fica em voo, que o piloto já nomeia.

    E O ATRIBUTO ÓRFÃO É A SEGUNDA METADE: se o `data-hef-voo` sobrevivesse à
    piscada, o pouso seguinte acharia DOIS elementos com o mesmo número e
    devolveria o rótulo errado a um deles. É por isso que a retirada agendada
    procura pela CLASSE, e o número sai antes.

    A DURAÇÃO É DO RELÓGIO DA PÁGINA desde 13/09/2026 (FLAKE-DO-PISCA). Até ali
    esta régua lia o botão 2,9 s depois do clique — e sob carga o pouso vinha
    tarde e a piscada ainda estava acesa, sem defeito nenhum. O `setTimeout`
    nunca apaga ANTES do número; uma piscada mais curta é a repintura
    arrancando o nó, e uma bem mais longa é o número errado.
    """
    apagou = _leitura(medido, "depois-de-muitos-tiques")
    botao = apagou["botao"]
    ms = medido["produto"]["piscada_ms"]
    assert botao and not botao["deu_certo"], (
        f"a piscada não apagou sozinha em {ms} ms: {botao}")
    assert botao["voo"] == "", (
        f"o número do voo ficou para trás no elemento: {botao}")
    assert ms - 100 <= apagou["piscada_ms"] <= ms + FOLGA_DA_PISCADA_MS, (
        f"a piscada durou {apagou['piscada_ms']} ms no relógio da página, e o "
        f"`MS_DA_PISCADA` é {ms} ms (folga de carga: {FOLGA_DA_PISCADA_MS} ms)")


def test_a_piscada_nao_acende_na_recusa(medido: dict) -> None:
    """Recusa é laranja, e o campo NÃO pisca verde.

    É a régua do Passo 2: sem o desfecho no pouso, o `voltouDoVoo` piscaria
    verde em cima de um cartão laranja — a tela dizendo as duas coisas de uma
    vez sobre o mesmo clique. A foto é do instante do pouso, e é nele que a
    piscada acenderia.
    """
    com_a_recusa = _leitura(medido, "com-a-recusa")
    botao = com_a_recusa["botao"]
    assert botao and not botao["deu_certo"], (
        f"o gesto levantou e o campo piscou verde mesmo assim: {botao}")
    tons = [r["tom"] for r in com_a_recusa["recados"]]
    assert "recusa" in tons or "erro" in tons, (
        f"a recusa não chegou ao cartão — o outro lado da mesma medição: {tons}")


def test_o_pisca_nao_move_a_tela(medido: dict) -> None:
    """A metade da decisão dela que nenhuma leitura de classe mede.

        *"nada muda de lugar"*

    É o que separa o `outline` (que não ocupa espaço na caixa) de uma borda mais
    grossa, que empurraria o vizinho. A comparação é do MESMO elemento, antes do
    clique e com a piscada acesa, na mesma unidade.
    """
    antes = _leitura(medido, "antes")["botao"]
    piscando = _leitura(medido, "depois-do-sucesso")["botao"]
    assert antes and piscando, (antes, piscando)
    assert piscando["deu_certo"], "a foto do 'durante' não pegou a piscada acesa"
    assert antes["caixa"] == piscando["caixa"], (
        "a piscada mexeu na geometria do campo — `outline` não ocupa espaço, "
        f"borda ocupa: antes={antes['caixa']} durante={piscando['caixa']}")


def test_a_frase_do_dono_nao_pousa_em_cartao_nenhum(medido: dict) -> None:
    """A PERGUNTA FOI INVERTIDA EM 13/09/2026 — TELA-CALADA-01.

    Ela era `test_a_frase_pousa_no_cartao_de_quem_foi_clicado` e exigia a frase
    de sucesso no cartão do p1. A palavra dela, com a foto do rodapé: *"essas
    frases de status que aparecem no rodapé isso não deveria estar
    aparecendo"*, *"em todas as abas da interface"*. O gesto que devolve
    `{"recado": …}` continua dando certo e continua piscando; a frase vai ao
    diário da janela, e o cartão fica como estava.

    A FOTO É A DO POUSO (o vigia da FLAKE-DO-PISCA), e é por isso que a primeira
    asserção vale: a piscada acesa nela prova que o gesto DEU CERTO, e o zero de
    recados que vem depois não é o de um clique que não chegou.

    O endereço por `uniq` que esta régua guardava continua medido — do lado da
    recusa, em `test_o_mesmo_cartao_troca_de_tom` e em
    `test_a_recusa_chega_ao_cartao`.
    """
    pouso = _leitura(medido, "com-a-frase-do-dono")
    assert pouso["botao"] and pouso["botao"]["deu_certo"], (
        f"o gesto com a frase do dono não piscou verde no pouso — sem o "
        f"sucesso, o zero abaixo mediria outra coisa: {pouso['botao']}")
    assert _r(pouso) == [], (
        f"o gesto que deu certo pôs recado na tela: {_r(pouso)!r}")


def test_o_aviso_sobrevive_aos_tiques(medido: dict) -> None:
    """A tela repinta a cada 100 ms e troca blocos inteiros.

    Um recibo que só existisse no instante do clique não seria visto por
    ninguém — é a mesma razão pela qual este canal é um DEPÓSITO e não um evento.

    ELA MEDE O RECIBO DA RECUSA desde 05/09/2026, e a razão é a mesma da irmã
    acima: o sucesso calado não deposita mais nada, então não há recibo dele a
    sobreviver. A recusa deposita, dura 30 s, e atravessa os tiques da mesma
    forma — o depósito é um só. **O `com-a-recusa` é a foto do pouso da recusa,
    e o `depois-do-pouso` vem depois do gesto lento inteiro e de mais meio
    segundo**, com a repintura correndo por cima o tempo todo: é o mesmo
    "sobreviveu aos tiques" que ela sempre mediu.
    """
    assert _frases(_leitura(medido, "depois-do-pouso")), (
        "o recibo sumiu com a repintura, e não por vencimento")


# --------------------------------------------------------------------------
# 2. o tom — dois desfechos, duas cores, um canal só
# --------------------------------------------------------------------------
def test_a_recusa_tem_o_tom_dela_e_o_sucesso_nao_tem_no(medido: dict) -> None:
    """ERA `test_o_sucesso_e_verde_e_a_recusa_e_laranja` — 13/09/2026.

    Os dois tons se comparavam no mesmo cartão, lado a lado. Desde a
    TELA-CALADA-01 o sucesso não deposita (*"em todas as abas da interface"*),
    e não há nó verde a comparar: o que sobra medir é a recusa no tom dela, com
    o desenho de um tom só (cor e borda iguais, lidas do CSSOM), e nenhum nó de
    tom `sucesso` nas fotos dos dois pousos de sucesso.
    """
    (recusa,) = _r(_leitura(medido, "com-a-recusa"))
    assert recusa["tom"] == "recusa", recusa
    assert recusa["cor"] == recusa["borda"], (
        f"a recusa perdeu o desenho de um tom só — cor {recusa['cor']} e borda "
        f"{recusa['borda']}")
    for marco in ("depois-do-sucesso", "com-a-frase-do-dono"):
        fotos = _r(_leitura(medido, marco))
        assert not [r for r in fotos if r["tom"] == "sucesso"], (
            f"{marco}: há nó de sucesso na tela — {fotos!r}")


def test_o_mesmo_cartao_troca_de_tom(medido: dict) -> None:
    """Recusa depois de sucesso, na MESMA chave: a cor tem de acompanhar.

    A chave é o controle, não o desfecho. Sem refazer o estilo quando o tom
    muda, o aviso trocaria de frase e ficaria verde dizendo que recusou.
    """
    (recusa,) = _r(_leitura(medido, "com-a-recusa"))
    assert recusa["chave"] == CHAVE_P1, recusa
    assert recusa["tom"] == "recusa", (
        "o nó reaproveitado ficou com o tom do desfecho anterior")


# --------------------------------------------------------------------------
# 3. a frase do dono do assunto vence a do piloto — é onde a D-12 pousa
# --------------------------------------------------------------------------
def test_a_frase_do_dono_nao_chega_a_tela(medido: dict) -> None:
    """ERA `test_a_frase_do_dono_vence` — invertida em 13/09/2026.

    Ela exigia que a frase devolvida pelo gesto fosse a que o cartão mostrava.
    Pela palavra dela (*"em todas as abas da interface"*, TELA-CALADA-01), a
    frase de um gesto que deu certo não entra na tela: vai ao diário da janela.
    O texto continua sendo do dono do assunto — quem o leva ao diário é o
    piloto, e `test_a_tela_nao_narra_o_gesto_que_deu_certo` cobra a linha
    `[relato]`.
    """
    frases = _frases(_leitura(medido, "com-a-frase-do-dono"))
    assert FRASE_DO_DONO not in frases and frases == [], (
        f"a frase do gesto que deu certo chegou à tela: {frases}")


def test_o_recado_nao_vira_endereco_de_pagina(medido: dict) -> None:
    """O ``recado`` sai da carga antes de a resposta ir para a pintura.

    Deixá-lo entrar faria o ``escrever()`` procurar um ``data-campo="recado"``
    que não existe em página nenhuma — e a régua do mockup passaria a contar o
    próprio instrumento como endereço.
    """
    antes = _leitura(medido, "antes")["enderecos"]
    depois = _leitura(medido, "com-a-frase-do-dono")["enderecos"]
    assert antes == depois, (
        f"o número de endereços da página mudou de {antes} para {depois} — o "
        f"aviso está sendo contado pela régua do mockup como campo da página.")


# --------------------------------------------------------------------------
# 4. não há recibo a vencer — nem no pouso, nem depois do prazo
# --------------------------------------------------------------------------
def test_nao_ha_recibo_a_vencer(medido: dict) -> None:
    """ERA `test_o_recibo_vence_e_some` — o contrato mudou em 13/09/2026.

    A FLAKE-DO-PISCA, no mesmo dia, tinha dado dente a esta régua: ela passara a
    exigir que o recibo ESTIVESSE no cartão antes de conferir que ele vencia,
    porque com o prazo em 600 s ela dava verde sobre um recibo eterno. A
    TELA-CALADA-01 tira o recibo da tela (*"em todas as abas da interface"*), e
    o recibo eterno deixa de poder existir: o que se mede agora é a AUSÊNCIA, nos
    dois instantes em que ele apareceria — a foto do pouso e a leitura depois do
    prazo encolhido desta medição.

    O VERDE SOBRE O VAZIO continua vigiado: a piscada acesa no pouso prova que o
    gesto com a frase do dono deu certo, então o zero é de um sucesso que não
    falou, e não de um clique que não chegou.
    """
    pouso = _leitura(medido, "com-a-frase-do-dono")
    assert pouso["botao"] and pouso["botao"]["deu_certo"], (
        "o gesto com a frase do dono não piscou verde no pouso — sem o sucesso, "
        "esta régua passaria sobre o vazio")
    for marco in ("com-a-frase-do-dono", "depois-de-vencer"):
        frases = _frases(_leitura(medido, marco))
        assert frases == [], (
            f"há recibo na tela em `{marco}`: {frases}. Desde 13/09 o gesto "
            f"que deu certo não escreve na tela.")


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
    antes = _leitura(medido, "antes")["botao"]
    voando = _leitura(medido, "no-meio-do-voo")["botao"]
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
    voando = _leitura(medido, "no-meio-do-voo")["botao"]
    assert "Calando" in voando["texto"], (
        f"o rótulo em voo não entrou: {voando['texto']!r}")


def test_o_botao_volta_sozinho_e_volta_inteiro(medido: dict) -> None:
    """E volta com os filhos que tinha.

    O original é guardado como `innerHTML` justamente por isto: os botões desta
    casa têm `<span>` dentro, e devolver só o `textContent` os achataria — o
    botão voltaria da espera diferente de como entrou.
    """
    antes = _leitura(medido, "antes")["botao"]
    depois = _leitura(medido, "depois-do-pouso")["botao"]
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


def test_o_bootstrap_e_a_primeira_ocorrencia_de_si_mesmo() -> None:
    """Seis réguas extraem o BOOTSTRAP do fonte, e nem todas ancoram no início.

    O DEFEITO QUE ISTO NÃO DEIXA VOLTAR foi medido em 05/09/2026, e ele é de
    PROSA: um comentário sobre o próprio BOOTSTRAP citou LITERALMENTE o padrão
    com que as réguas o extraem. O comentário mora acima da definição, então
    virou a **primeira ocorrência** do arquivo — e as réguas sem âncora de
    início passaram a extrair o comentário em vez do JavaScript. Treze testes
    caíram com `Unexpected token '.'`, que não se lê como *"alguém escreveu uma
    frase infeliz num comentário"*.

    A régua é simples e é a que faltava: **a primeira ocorrência do texto que
    abre a constante tem de ser a própria constante**, no começo de uma linha.
    """
    import re
    from pathlib import Path

    piloto = (
        Path(__file__).resolve().parents[2]
        / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"
    )
    fonte = piloto.read_text(encoding="utf-8")

    abertura = 'BOOTSTRAP = r' + '"' * 3
    primeira = fonte.find(abertura)
    assert primeira != -1, "o BOOTSTRAP mudou de forma — as seis réguas cegaram"
    assert primeira == 0 or fonte[primeira - 1] == "\n", (
        "a primeira ocorrência do texto que abre o BOOTSTRAP não está no começo "
        "de uma linha — alguém a citou numa prosa acima da definição, e as "
        "réguas sem âncora vão extrair a prosa. Descreva o padrão, não o "
        f"escreva: …{fonte[max(0, primeira - 90):primeira + 30]!r}")

    # E O QUE SAI TEM DE SER JAVASCRIPT, não uma linha de comentário: a régua
    # acima pega o caso de hoje, esta pega o que ele vier a ser amanhã.
    extraido = re.search(re.escape(abertura) + r'(.*?)' + '"' * 3, fonte, re.S)
    assert extraido and len(extraido.group(1)) > 10_000, (
        "o que a extração sem âncora devolve não é o bootstrap inteiro: "
        f"{len(extraido.group(1)) if extraido else 0} caracteres")
