#!/usr/bin/env python3
"""O RECADO DE SUCESSO NO CARTÃO — e o botão que diz que está trabalhando.

Duas decisões de 04/09/2026, medidas na JANELA e não no terminal:

**D-01 — o canal de sucesso.** *"No próprio cartão, como a recusa."* Até aqui a
interface nova só falava quando RECUSAVA: um gesto que dava certo imprimia
``[gesto] … → aplicado`` no terminal de quem lançou a janela, e quem clica não
lê terminal. **Cinco linhas do CSV paravam nesse buraco**, em cinco abas (02,
03, 05, 06 e 09) — e uma peça só as fecha.

**`09` [03] — o estado "em voo".** *"O botão diz que está trabalhando"*, e diz
DURANTE a espera, no lugar exato do clique. Há um gesto desta casa que leva
**9,5 segundos** (``daemon.reload``, medido no daemon do usuário em 01/09) e nenhuma
das dez abas tinha estado em voo: o clique sumia por nove segundos e meio e o
segundo clique parecia o primeiro.

**UM FATO, UM SINAL** — e é a razão inteira de o canal do cartão não se
duplicar. Esta metade continua valendo.

A OUTRA METADE CADUCOU EM 05/09/2026. Este parágrafo dizia que ELA recusara
*o campo que pisca* (aba 03) e *a faixa embaixo da grade* (aba 05), e que esta
régua existia também para que ninguém os construísse. Quem recusou foi o PO,
lendo a D-01 como se ela fechasse a forma — os conflitos C-3 e C-6 são dele. Em
05/09 ela respondeu a `03-Q4` vendo as quatro formas lado a lado e escolheu o
campo que pisca. **A palavra de produto vence a leitura que o PO fez da palavra
de produto.**

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
EM 13/09/2026 (TELA-CALADA-01). Pela palavra de produto, *"essas frases de status que
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

E A RECUSA SAIU DA TELA NO MESMO DIA (FRASES-E-DICAS-01): as réguas que a
usavam como o outro lado da comparação — o tom, o recibo que sobrevivia aos
tiques, os dois prazos — passaram a medir a piscada de recusa no botão e
nenhuma frase na tela.

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

UNIQ_P1 = "aa:bb:cc:00:00:01"
UNIQ_P2 = "aa:bb:cc:00:00:02"

CHAVE_P1 = "aabbcc000001"


def _ctl(uniq: str, transporte: str, jogador: int) -> dict:
    return {"uniq": uniq, "connected": True, "transport": transporte,
            "player": jogador, "audio": {"mic_mudo": False},
            "speaker": {"volume": 100, "muted": False, "rota": 2}}


ESTADO = {
    "active_profile": "regua",
    "gamepad_emulation": {"flavor": "dualsense"},
    "controllers": [_ctl(UNIQ_P1, "usb", 1), _ctl(UNIQ_P2, "bt", 2)],
}

MESA = {"estado": ESTADO}

VENCE_EM_S = 3.0

GESTO_LENTO_S = 1.6

MEIO_DO_VOO_S = 0.5

PASSO_MS = 50

TETO_S = 10.0

TETO_DA_PAGINA_S = 30.0

TETO_DO_ROTEIRO_S = 120.0

FOLGA_DA_PISCADA_MS = 1500

FRASE_DO_DONO = "o microfone ligou, mas o canal dele está mudo no sistema"

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
  const b = document.querySelector('[data-controle="p1"] [data-mudo="alto-falante"]');
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
      // A PISCADA DO "DEU CERTO" — 05/09/2026, decisão de produto na `03-Q4`.
      deu_certo: b.classList.contains('hef-deu-certo'),
      // A PISCADA DA RECUSA — 13/09/2026, FRASES-E-DICAS-01: a recusa saiu do
      // cartão e passou a responder no botão.
      recusou: b.classList.contains('hef-recusou'),
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
      // A GEOMETRIA, arredondada ao pixel: é a metade da decisão de produto que
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

_VIGIA = r"""
function(ler){
  if(!(window.__hef && window.__hef.voltouDoVoo)) return 'sem ponte';
  const seletor = '[data-controle="p1"] [data-mudo="alto-falante"]';
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

_CLICAR_NO_MIC = r"""
function(marco){
  const b = document.querySelector('[data-controle="p1"] [data-mudo="alto-falante"]');
  if(!b) return 'NAO ACHEI O BOTAO DO MICROFONE NO CARTAO DO P1';
  if(!window.__reguaTrilha) return 'SEM O VIGIA — o clique não teria marco na trilha';
  window.__reguaTrilha.push({marco: marco, t: performance.now()});
  b.click();
  return 'cliquei';
}
"""

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


PUBLICAR_O_ROTULO = r"""
(function(){
  const b = document.querySelector('[data-controle="p1"] [data-mudo="alto-falante"]');
  if(!b) return 'sem botao';
  b.setAttribute('data-hef-em-voo', 'Calando…');
  return b.innerHTML;
})()
"""


def _pouso(trilha: object) -> dict | None:
    """A foto em que o 🎙 SAIU do voo depois de ter entrado nele — ou nada ainda."""
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
    """A foto em que a piscada do pouso apagou, com quanto ela durou."""
    fotos = trilha if isinstance(trilha, list) else []
    pouso = _pouso(fotos)
    if pouso is None or not pouso["botao"]["deu_certo"]:
        return None
    for foto in fotos[fotos.index(pouso) + 1:]:
        botao = foto.get("botao")
        if botao is not None and not botao["deu_certo"]:
            return dict(foto, piscada_ms=round(foto["t"] - pouso["t"]))
    return None


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

    chave = ("02-controles.html", "mudo")
    guardado = (hv.mesa_viva.estado_do_daemon, hv.ponte.mic_canal_set_detalhado,
                hv.ponte.speaker_set, hv.pacotes.GESTOS.get(chave))
    do_produto = {
        "prazos_do_recado": [n for n in ("SEGUNDOS_DO_RECADO",
                                         "SEGUNDOS_DO_RECADO_DE_SUCESSO")
                             if hasattr(hv, n)],
        "piscada_ms": int(hv.MS_DA_PISCADA),
    }
    MESA["estado"] = ESTADO
    hv.mesa_viva.estado_do_daemon = lambda *a, **k: MESA["estado"]  # type: ignore[assignment]
    hv.ponte.mic_canal_set_detalhado = (  # type: ignore[assignment]
        lambda *a, **k: {"status": "ok", "canal_feito": True,
                         "firmware_pedido": True})
    hv.ponte.speaker_set = lambda *a, **k: True  # type: ignore[assignment]

    args = argparse.Namespace(
        oculta=True, segundos=0.0, passear=False, parada=900, foto="",
        abre="02-controles.html", prova_no_aparelho=False, entre=2500,
        espera=1200, incluir_perigosos=False, prova_clique="", sem_cor=True,
        prova_de_mockup=False, voltas_por_aba=8, teto_de_mockup=-1,
        sem_cravado=False, sem_selo=False,
    )
    piloto = hv.Piloto(args)
    faltou: dict[str, str] = {}
    esperas_s: dict[str, float] = {}
    fora: dict[str, object] = {"produto": do_produto, "faltou": faltou,
                               "esperas_s": esperas_s}
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
        """Troca quem atende o 🎙 — pelo REGISTRO do produto, não por atalho."""
        hv.pacotes.GESTOS[chave] = fn

    def esperar(marco: str, pergunta: str, achar, depois, o_que: str,
                teto_s: float = TETO_S) -> None:
        """UMA espera por condição: pergunta, e só segue quando `achar` achar."""
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
        esperar("depois-de-muitos-tiques", _trilha_desde("clique-1"), _apagou,
                com_a_frase_do_dono,
                "a piscada do clique 1 acender no pouso e apagar sozinha")

    def com_a_frase_do_dono() -> None:
        por_gesto(lambda ctx, o, p: {"recado": FRASE_DO_DONO,
                                     "mesa": {"perfil-ativo": "regua"}})
        piloto.ponte.perguntar(_clicar_no_mic("clique-2"), anotar("clique-2"))
        esperar("com-a-frase-do-dono", _trilha_desde("clique-2"), _pouso,
                a_frase_vence, "o 🎙 pousar (o carimbo `data-hef-voo` sair) depois do clique 2")

    def a_frase_vence() -> None:
        esperar("depois-de-vencer", LER_A_TELA,
                lambda leitura: leitura if (
                    not _frases(leitura) and leitura["botao"]
                    and not leitura["botao"]["deu_certo"]) else None,
                agora_a_recusa,
                f"a frase do dono sair do cartão ({VENCE_EM_S:.0f} s de prazo "
                f"nesta medição), com o 🎙 em repouso",
                teto_s=VENCE_EM_S + TETO_S)

    def agora_a_recusa() -> None:
        def recusa(ctx, o, p):
            raise RuntimeError("o daemon não confirmou o mudo do microfone")

        por_gesto(recusa)
        piloto.ponte.perguntar(_clicar_no_mic("clique-3"), anotar("clique-3"))
        esperar("com-a-recusa", _trilha_desde("clique-3"), _pouso,
                o_gesto_lento,
                "o 🎙 pousar (o carimbo `data-hef-voo` sair) depois do clique 3, o que recusa")

    def o_gesto_lento() -> None:
        # "durante": o `daemon.reload` do produto leva 9,5 s, e é essa espera que
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
        fora["deposito"] = sorted(getattr(piloto, "_recados", {}))
        Gtk.main_quit()

    GLib.timeout_add(400, comecar)
    guarda = GLib.timeout_add(int(TETO_DO_ROTEIRO_S * 1000), Gtk.main_quit)
    try:
        limite = _time.monotonic() + TETO_DO_ROTEIRO_S
        while "desfechos" not in fora and _time.monotonic() < limite:
            Gtk.main()
    finally:
        no_ar["sim"] = False
        GLib.source_remove(guarda)
        piloto.pronto = False
        piloto.tela.janela.destroy()
        (hv.mesa_viva.estado_do_daemon, hv.ponte.mic_canal_set_detalhado,
         hv.ponte.speaker_set, velho) = guardado
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
    """A foto de um marco do roteiro — ou a reprova dizendo o que não chegou."""
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


def test_o_gesto_aplicou(medido: dict) -> None:
    assert _leitura(medido, "vigia") == "vigiando"
    assert medido["clique-1"] == "cliquei", medido["clique-1"]
    assert medido["desfechos"].get("02-controles.html:mudo"), medido["desfechos"]


def test_a_tela_estava_muda_antes(medido: dict) -> None:
    """A LINHA DE BASE. Sem ela, uma página que já tivesse um aviso passaria."""
    antes = _leitura(medido, "antes")
    assert _frases(antes) == [], (
        f"a página já tinha aviso antes do clique: {_frases(antes)}")


def test_o_sucesso_calado_pisca_e_nao_fala(medido: dict) -> None:
    """A PERGUNTA FOI INVERTIDA EM 05/09/2026, e a medição é a mesma."""
    botao = _leitura(medido, "depois-do-sucesso")["botao"]
    assert botao and botao["deu_certo"], (
        "o gesto deu certo e o campo não piscou — é o defeito que a D-01 fecha, "
        f"na forma que ela escolheu na 03-Q4: {botao}")
    antes = _leitura(medido, "antes")["botao"]
    assert botao["borda"] != antes["borda"] or botao["contorno_larg"] != antes["contorno_larg"], (
        "a classe entrou e a tela não mudou de cor — o `!important` da folha "
        f"não pegou: antes={antes['borda']}/{antes['contorno_larg']} "
        f"durante={botao['borda']}/{botao['contorno_larg']}")
    marcos = ["depois-do-sucesso"]
    if "depois-de-muitos-tiques" not in medido["faltou"]:
        marcos.append("depois-de-muitos-tiques")
    for marco in marcos:
        frases = _frases(_leitura(medido, marco))
        assert frases == [], (
            "o gesto não trouxe notícia e a tela falou mesmo assim — a palavra "
            f"nova é o que a decisão dela tirou ({marco}): {frases}")


def test_a_piscada_apaga_sozinha(medido: dict) -> None:
    """A classe saiu sozinha, durou o que o produto diz, e o `data-hef-voo` não ficou."""
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
    """Recusa é laranja, e o campo NÃO pisca verde."""
    com_a_recusa = _leitura(medido, "com-a-recusa")
    botao = com_a_recusa["botao"]
    assert botao and not botao["deu_certo"], (
        f"o gesto levantou e o campo piscou verde mesmo assim: {botao}")
    assert botao["recusou"], (
        f"o gesto levantou e o botão não piscou a recusa: {botao}")
    assert com_a_recusa["recados"] == [], com_a_recusa["recados"]


def test_o_pisca_nao_move_a_tela(medido: dict) -> None:
    """A metade da decisão de produto que nenhuma leitura de classe mede."""
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
    de sucesso no cartão do p1. A palavra de produto, com a foto do rodapé: *"essas
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


def test_nenhuma_frase_volta_nos_tiques(medido: dict) -> None:
    """ERA `test_o_aviso_sobrevive_aos_tiques` — 13/09/2026. A tela repinta a cada"""
    assert _frases(_leitura(medido, "depois-do-pouso")) == [], (
        "a repintura trouxe uma frase à tela depois da recusa")


def test_a_recusa_tem_o_tom_dela_e_o_sucesso_nao_tem_no(medido: dict) -> None:
    """ERA `test_o_sucesso_e_verde_e_a_recusa_e_laranja` — 13/09/2026."""
    assert _r(_leitura(medido, "com-a-recusa")) == []
    for marco in ("depois-do-sucesso", "com-a-frase-do-dono"):
        fotos = _r(_leitura(medido, marco))
        assert not [r for r in fotos if r["tom"] == "sucesso"], (
            f"{marco}: há nó de sucesso na tela — {fotos!r}")


def test_o_mesmo_cartao_troca_de_tom(medido: dict) -> None:
    """Recusa depois de sucesso, na MESMA chave: a cor tem de acompanhar."""
    botao = _leitura(medido, "com-a-recusa")["botao"]
    assert botao and botao["recusou"] and not botao["deu_certo"], (
        f"o botão reaproveitado ficou com a cor do desfecho anterior: {botao}")


def test_a_frase_do_dono_nao_chega_a_tela(medido: dict) -> None:
    """ERA `test_a_frase_do_dono_vence` — invertida em 13/09/2026."""
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


def test_nao_ha_recibo_a_vencer(medido: dict) -> None:
    """ERA `test_o_recibo_vence_e_some` — o contrato mudou em 13/09/2026."""
    pouso = _leitura(medido, "com-a-frase-do-dono")
    assert pouso["botao"] and pouso["botao"]["deu_certo"], (
        "o gesto com a frase do dono não piscou verde no pouso — sem o sucesso, "
        "esta régua passaria sobre o vazio")
    for marco in ("com-a-frase-do-dono", "depois-de-vencer"):
        frases = _frases(_leitura(medido, marco))
        assert frases == [], (
            f"há recibo na tela em `{marco}`: {frases}. Desde 13/09 o gesto "
            f"que deu certo não escreve na tela.")


def test_os_prazos_do_recado_sairam_com_o_canal(medido: dict) -> None:
    """ERA `test_o_prazo_do_sucesso_e_menor_que_o_da_recusa` — 13/09/2026."""
    assert medido["produto"]["prazos_do_recado"] == [], (
        f"voltaram ao piloto prazos de frase na tela: "
        f"{medido['produto']['prazos_do_recado']}")


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
    """Quem publica um `data-hef-em-voo` ganha a palavra dentro do botão."""
    voando = _leitura(medido, "no-meio-do-voo")["botao"]
    assert "Calando" in voando["texto"], (
        f"o rótulo em voo não entrou: {voando['texto']!r}")


def test_o_botao_volta_sozinho_e_volta_inteiro(medido: dict) -> None:
    """E volta com os filhos que tinha."""
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
    """A segunda régua do dono impossível — o Python e o JavaScript concordam."""
    import re

    import hefesto_vivo as hv

    achados = re.findall(r"\}, (\d+)\);", hv.BOOTSTRAP)
    assert achados, "o `setTimeout` da piscada sumiu do BOOTSTRAP"
    assert str(hv.MS_DA_PISCADA) in achados, (
        f"o Python diz {hv.MS_DA_PISCADA} ms e o JavaScript diz {achados} — "
        "a piscada duraria o que a tela mandasse, não o que ela decidiu")


def test_o_bootstrap_e_a_primeira_ocorrencia_de_si_mesmo() -> None:
    """Seis réguas extraem o BOOTSTRAP do fonte, e nem todas ancoram no início."""
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

    extraido = re.search(re.escape(abertura) + r'(.*?)' + '"' * 3, fonte, re.S)
    assert extraido and len(extraido.group(1)) > 10_000, (
        "o que a extração sem âncora devolve não é o bootstrap inteiro: "
        f"{len(extraido.group(1)) if extraido else 0} caracteres")
