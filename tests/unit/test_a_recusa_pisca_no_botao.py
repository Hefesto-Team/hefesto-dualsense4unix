#!/usr/bin/env python3
"""A RECUSA PISCA NO BOTÃO, E A FRASE NÃO CHEGA À TELA — FRASES-E-DICAS-01, 13/09/2026.

A palavra dela está no índice da leva
(`docs/process/sprints/arquivados/2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md`, linha 19):
com a foto da aba Gatilhos e a caixa laranja *«Esse número é maior do que a
quantidade de controles ligados»*, ela mandou que esse tipo de frase parasse de
aparecer. A caixa era a recusa do gesto `player` da aba 04 — um número `.fora`
clicado com um controle só na mesa —, que o piloto pousava no cartão do P1 por
30 s. O §0 da sprint: frase de aviso não chega à tela em forma nenhuma (recado,
faixa, caixa, dica flutuante, `title`); a tela mostra estado e responde ao
clique pelo sinal do botão.

O QUE ESTA RÉGUA COBRA, no piloto do produto com a janela OCULTA e UM controle
na mesa dublê:

1. **a recusa não pousa recado nem frase**, COM coluna (`player` da 04, `mudo`
   da 02) e SEM coluna (o cadeado da 01): zero `.hef-recado`, e a frase ausente
   do texto visível, de todo `data-hef-dica` e de todo `title`;
2. **o botão veste a recusa e a perde sozinho**: `hef-recusou` acende no pouso,
   sem `hef-deu-certo`, e apaga em `MS_DA_PISCADA`;
3. **a frase vai ao diário da janela**: `[gesto falhou] <página> · <gesto>: …`;
4. **o número fora diz só o número**: o `#hef-dica` do `.fora` diz «Player 2»;
5. **o clique que só arma não pisca**: um gesto que devolve `{"armou": True}`
   pousa sem `hef-deu-certo` e sem `hef-recusou`;
6. **a aba 05 não declara lugar de recado**, na bancada e no publicado;
7. **o clique sem dono também pisca a recusa** (sem janela, no `Piloto._gesto`);
8. **a casa tomada da 04 diz de quem é, sem a regra colada** (sem janela);
9. **a colisão da troca de botões da 06** — F1-REMAPEAR-02, 13/09/2026: o
   «Guardar» da tela "Trocar os botões" com a Cruz e o Quadrado indo para o
   Círculo é recusado pelo motor, e a recusa segue as regras 1 a 3 — sem frase,
   com a piscada no botão e a frase no diário. O gesto é o REAL, e o disco é o
   de mentira da suíte: a recusa acontece antes de qualquer leitura de perfil.

O TEMPO É CONDIÇÃO, NÃO RELÓGIO — a lição da FLAKE-DO-PISCA, escrita em
`test_o_recado_de_sucesso_pousa_no_cartao`: a piscada é estado de PASSAGEM, e
quem a fotografa é um vigia (`MutationObserver`) no instante em que o botão
muda. A régua lê a TRILHA do botão, e cada marco espera pela condição dele, com
teto e com a frase do que não chegou.

AS MORDIDAS, medidas e coladas na entrega da sprint:

* devolva o piloto de antes da cura (`249af1f6`) → reprovam os casos 1, 2 e 5;
* troque o `'hef-recusou'` do `voltouDoVoo` por `''` → reprova o caso 2;
* tire o `so_armou` do pouso em `Piloto._gesto` → reprova o caso 5;
* devolva a frase à dica do `.fora` em `a04_iluminacao.um_botao_de_player` →
  reprovam os casos 1 (na 04) e 4;
* faça `Piloto._recusou_dizendo` pousar a frase na página quando ela for a 06
  → reprova o caso 1 na 06 (F1-REMAPEAR-02).
"""
from __future__ import annotations

import contextlib
import io
import json
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: O CONTROLE DA MESA DUBLÊ, na faixa sintética da casa. Nada de MAC real em
#: arquivo versionado — há dois portões, e eles não perdoam.
UNIQ_P1 = "aa:bb:cc:00:00:01"

#: UM CONTROLE SÓ, e é o que faz o `.fora` existir: com um na mesa, os números
#: 2, 3 e 4 da aba 04 passam da conta — é o gatilho da caixa da foto dela.
ESTADO = {
    "active_profile": "regua",
    "gamepad_emulation": {"flavor": "dualsense"},
    "controllers": [{"uniq": UNIQ_P1, "connected": True, "transport": "bt",
                     "player": 1, "audio": {"mic_mudo": False}}],
}

PAGINA_01 = "01-jogar.html"
PAGINA_02 = "02-controles.html"
PAGINA_04 = "04-iluminacao.html"
PAGINA_06 = "06-navegacao.html"  # (noqa-acento) nome de arquivo

#: OS QUATRO BOTÕES QUE RECUSAM: página, gesto e o seletor do botão do produto.
BOTOES = {
    "04": (PAGINA_04, "player",
           '[data-controle="p1"] .players button.fora[data-player="2"]'),
    "02": (PAGINA_02, "mudo", '[data-controle="p1"] [data-mudo="microfone"]'),
    "01": (PAGINA_01, "cadeado", 'input[data-gesto="cadeado"]'),
    "06": (PAGINA_06, "guardar-remapeamento",
           '#remapeamento [data-gesto="guardar-remapeamento"]'),
}
CASOS = ("04", "02", "01", "06")

#: A COLISÃO DA 06 — duas linhas para o mesmo destino, a recusa que só o
#: «Guardar» faz (a linha anota; quem confere o mapa inteiro é ele).
COLISAO_DA_06 = {"cross": "circle", "square": "circle"}

#: ESCREVE AS LINHAS NA MESMA CHAMADA DO CLIQUE: entre duas chamadas o tique
#: repinta as listas com o que o perfil guarda, e a `forma` perderia a colisão.
#: Sem `change`, de propósito — nenhum `linha-de-troca` antes do «Guardar».
ARMAR_AS_LINHAS = r"""
(function(linhas){
  return function(){
    Object.keys(linhas).forEach(function(l){
      const el = document.querySelector('#remapeamento select[data-linha="' + l + '"]');
      if(el) el.value = linhas[l];
    });
  };
})(%s)
"""

#: A FRASE QUE O ATO DO MICROFONE DEVOLVE quando falha pela metade. É frase de
#: PROVA, a mesma de `test_a_recusa_chega_ao_cartao`: o que se mede é se a frase
#: do dono ATRAVESSA até a tela, e digitar a do daemon mediria a própria régua.
RECUSA_DO_MIC = ("o microfone foi ligado no canal deste controle, mas o "
                 "Hefesto não conseguiu escrever o mudo no aparelho")

#: O PASSO E OS TETOS DAS ESPERAS POR CONDIÇÃO — generosos de propósito, e
#: continuam sendo régua: um marco que não chega reprova dizendo qual.
PASSO_MS = 50
TETO_S = 10.0
TETO_DA_PAGINA_S = 30.0
TETO_DO_ROTEIRO_S = 180.0

#: QUANTO A PISCADA PODE PASSAR DE `MS_DA_PISCADA` no relógio da página: o
#: `setTimeout` nunca apaga ANTES, e sob carga apaga depois.
FOLGA_DA_PISCADA_MS = 1500

#: O VIGIA E O CLIQUE NA MESMA CHAMADA. O vigia anota o botão só quando ele
#: MUDA (classe ou carimbo de voo) e relê o seletor a cada mutação: a pintura
#: pode trocar o nó, e uma referência guardada mediria um nó fora do documento.
VIGIAR_E_CLICAR = r"""
(function(sel, marco, armar){
  const b = document.querySelector(sel);
  if(!b) return 'NAO ACHEI ' + sel;
  window.__reguaTrilhas = window.__reguaTrilhas || {};
  const trilha = window.__reguaTrilhas[marco] = [];
  let visto = null;
  function anotar(){
    const el = document.querySelector(sel);
    const assinatura = el
      ? el.className + '|' + (el.getAttribute('data-hef-voo') || '') : '';
    if(assinatura === visto) return;
    visto = assinatura;
    trilha.push({t: performance.now(), classes: el ? el.className : '',
                 voo: el ? (el.getAttribute('data-hef-voo') || '') : ''});
  }
  new MutationObserver(anotar).observe(document.documentElement,
    {subtree: true, childList: true, attributes: true});
  anotar();
  if(armar) armar();
  b.click();
  return 'cliquei';
})(%s, %s, %s)
"""

LER_A_TRILHA = r"""
(function(marco){
  const t = (window.__reguaTrilhas || {})[marco];
  return JSON.stringify({agora: performance.now(), trilha: t === undefined ? null : t});
})(%s)
"""

#: A TELA, lida pelo que ela MOSTRA: `innerText` respeita o `display:none` da
#: folha da casa (a `.nota` do mockup não conta), e as duas formas de dica —
#: `title` cru e o `data-hef-dica` que a camada da casa colhe dele — entram.
LER_A_TELA = r"""
(function(frase){
  const em = function(atr){
    return Array.prototype.filter.call(document.querySelectorAll('[' + atr + ']'),
      function(e){ return (e.getAttribute(atr) || '').indexOf(frase) >= 0; }).length;
  };
  const visivel = document.body ? (document.body.innerText || '') : '';
  return JSON.stringify({
    aba: location.pathname.split('/').pop(),
    recados: document.querySelectorAll('.hef-recado').length,
    visivel: visivel.indexOf(frase) >= 0,
    dica: em('data-hef-dica'),
    title: em('title'),
  });
})(%s)
"""

EXISTE = "JSON.stringify(document.querySelector(%s) ? 'sim' : null)"

#: O PONTEIRO EM CIMA DO BOTÃO: o `mousemove` é o evento que a camada da dica
#: escuta, e ela abre depois do atraso dela. Nada toca o mouse dela.
PASSAR_O_MOUSE = r"""
(function(sel){
  const b = document.querySelector(sel);
  if(!b) return 'NAO ACHEI ' + sel;
  const r = b.getBoundingClientRect();
  b.dispatchEvent(new MouseEvent('mousemove', {bubbles: true,
    clientX: r.left + r.width / 2, clientY: r.top + r.height / 2}));
  return 'passei';
})(%s)
"""

LER_A_DICA = r"""
(function(){
  const d = document.getElementById('hef-dica');
  const aberta = !!(window.__hefDica && window.__hefDica.aberta());
  return JSON.stringify(aberta ? {texto: d ? (d.textContent || '').trim() : ''} : null);
})()
"""

FECHAR_A_DICA = (
    "document.dispatchEvent(new MouseEvent('mouseout', "
    "{bubbles: true, relatedTarget: null})); 'fechei'")


def _pousou(trilha: list[dict]) -> dict | None:
    """A foto em que o botão SAIU do voo depois de ter entrado nele."""
    voou = False
    for foto in trilha:
        if foto.get("voo"):
            voou = True
        elif voou:
            return foto
    return None


def _piscada(trilha: list[dict], classe: str) -> dict | None:
    """Quando `classe` acendeu e quando apagou, no relógio da página."""
    acendeu = None
    for foto in trilha:
        tem = classe in str(foto.get("classes") or "").split()
        if tem and acendeu is None:
            acendeu = foto["t"]
        elif not tem and acendeu is not None:
            return {"ms": round(foto["t"] - acendeu)}
    return None


def _a_recusa_assentou(leitura: dict) -> dict | None:
    """O pouso chegou — e, se ele acendeu a recusa, ela já apagou."""
    trilha = leitura.get("trilha")
    if not isinstance(trilha, list):
        return None
    pouso = _pousou(trilha)
    if pouso is None:
        return None
    if "hef-recusou" not in str(pouso.get("classes") or "").split():
        return {"pouso": pouso, "piscada": None, "trilha": trilha}
    piscada = _piscada(trilha, "hef-recusou")
    if piscada is None:
        return None
    return {"pouso": pouso, "piscada": piscada, "trilha": trilha}


#: O PERFIL ATIVO NO DISCO — mesma razão das réguas irmãs: a pintura da 02 lê o
#: perfil ativo, e sem arquivo o gesto recusaria por outro caminho.
@pytest.fixture(scope="module", autouse=True)
def _perfil_ativo_no_disco() -> None:
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    profiles_dir().mkdir(parents=True, exist_ok=True)
    if not (profiles_dir() / "regua.json").exists():
        loader.save_profile(Profile(name="regua", match=MatchManual()),
                            origem="regua")


@pytest.fixture(scope="module")
def medido() -> dict:
    """Abre o piloto DE VERDADE, oculto, e anda 04 → 02 → 01, marco a marco."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    import argparse
    import time as _time

    import hefesto_vivo as hv
    import pacotes.a01_jogar as a01
    import pacotes.a06_navegacao as a06
    from hefesto_dualsense4unix.app.ipc_bridge import _MOTIVOS_NUMERO
    from hefesto_dualsense4unix.core import remapeamento_de_botao as remap

    #: AS FRASES DOS DONOS, lidas deles: a da ponte para o número fora, a do
    #: pacote para o cadeado, a de prova para o ato do microfone, e a do motor
    #: com os nomes da tela para a colisão da 06.
    try:
        remap.resolver(COLISAO_DA_06)
    except remap.RemapeamentoRecusadoError as exc:
        frase_da_06 = a06._frase_da_troca(exc)
    else:
        pytest.fail(f"o motor aceitou a colisão {COLISAO_DA_06} — o caso 06 não mede nada")
    rotulo_de = {destino: rotulo for rotulo, destino in a06.ROTULOS_DA_TROCA.items()}
    armar = {"06": ARMAR_AS_LINHAS % json.dumps(
        {linha: rotulo_de[destino] for linha, destino in COLISAO_DA_06.items()})}
    frases = {"04": _MOTIVOS_NUMERO["numero_fora_da_mesa"], "02": RECUSA_DO_MIC,
              "01": a01.CADEADO_RECUSA, "06": frase_da_06}

    # OS DUBLÊS SÃO DEVOLVIDOS NO FIM: `mesa_viva`, `pacotes.ponte` e o registro
    # `GESTOS` são módulos compartilhados do produto, e deixá-los sujos entrega
    # uma mesa de mentira a todo vizinho que abrir um `Piloto` depois.
    chave_01 = (PAGINA_01, "cadeado")
    chave_02 = (PAGINA_02, "mudo")
    guardado = (hv.mesa_viva.estado_do_daemon, hv.ponte.identity_number_set,
                hv.ponte.mic_canal_set_detalhado)
    guardado_gestos = {k: hv.pacotes.GESTOS.get(k) for k in (chave_01, chave_02)}
    hv.mesa_viva.estado_do_daemon = lambda *a, **k: ESTADO  # type: ignore[assignment]
    # O NÚMERO FORA RECUSA PELO GESTO REAL: a ponte devolve `(False, motivo)`,
    # que é o corpo que `identity_number_set` devolve quando o daemon recusa.
    hv.ponte.identity_number_set = (  # type: ignore[assignment]
        lambda uniq, n: (False, frases["04"]))
    # O MICROFONE RECUSA PELO GESTO REAL: `status: "incompleto"` com motivo é o
    # que o ato responde quando falha pela metade.
    hv.ponte.mic_canal_set_detalhado = lambda *a, **k: {  # type: ignore[assignment]
        "status": "incompleto", "canal_feito": False, "firmware_pedido": True,
        "motivo": RECUSA_DO_MIC}

    def cadeado_que_recusa(ctx, o, p):
        raise RuntimeError(frases["01"])

    def mudo_que_so_arma(ctx, o, p):
        return {"armou": True}

    hv.pacotes.GESTOS[chave_01] = cadeado_que_recusa

    args = argparse.Namespace(
        oculta=True, segundos=0.0, passear=False, parada=900, foto="",
        abre=PAGINA_04, prova_no_aparelho=False, entre=2500,
        espera=1200, incluir_perigosos=False, prova_clique="", sem_cor=True,
        prova_de_mockup=False, voltas_por_aba=8, teto_de_mockup=-1,
        sem_cravado=False, sem_selo=False,
    )
    piloto = hv.Piloto(args)
    faltou: dict[str, str] = {}
    fora: dict[str, object] = {"faltou": faltou, "frases": frases}
    diario = io.StringIO()
    no_ar = {"sim": True}

    def js(valor: object) -> str:
        return json.dumps(valor)

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
                depois()
            elif gasto >= teto_s:
                visto = f"ERRO {erro}" if erro is not None else repr(leitura)
                faltou[marco] = (f"{o_que} — não chegou em {teto_s:.0f} s; a "
                                 f"última leitura foi …{visto[-400:]}")
                depois()
            else:
                GLib.timeout_add(PASSO_MS, perguntar)

        perguntar()

    def abrir(pagina: str, seletor: str, depois) -> None:
        """Navega, e só segue com a página NOVA de pé e o botão nela."""
        piloto._ir(pagina)
        comeco = _time.monotonic()

        def de_pe() -> bool:
            if piloto.pagina == pagina and piloto.pronto:
                esperar(f"botao-{pagina}", EXISTE % js(seletor),
                        lambda v: v if v == "sim" else None, depois,
                        f"o botão {seletor} na {pagina}")
                return False
            if _time.monotonic() - comeco >= TETO_DA_PAGINA_S:
                faltou[f"pagina-{pagina}"] = f"a {pagina} não ficou de pé"
                depois()
                return False
            return True

        GLib.timeout_add(200, de_pe)

    def clicar_e_esperar_a_recusa(caso: str, depois) -> None:
        pagina, gesto, seletor = BOTOES[caso]
        piloto.ponte.perguntar(
            VIGIAR_E_CLICAR % (js(seletor), js(caso), armar.get(caso, "null")),
                               lambda v, e: fora.__setitem__(f"{caso}-clique", str(v)))

        def assentou() -> None:
            fora[f"{caso}-desfecho"] = list(
                piloto.desfechos.get(f"{pagina}:{gesto}", ()))
            esperar(f"{caso}-tela", LER_A_TELA % js(frases[caso]),
                    lambda leitura: leitura, depois,
                    f"a leitura da {pagina} depois da recusa")

        esperar(f"{caso}-recusa", LER_A_TRILHA % js(caso), _a_recusa_assentou,
                assentou, f"o botão da {pagina} pousar e a piscada apagar")

    # ---- 04: a dica do número fora, e a recusa com coluna ---------------
    def comecar() -> bool:
        if not piloto.tela.na_aba:
            return True
        abrir(PAGINA_04, BOTOES["04"][2], a_dica_da_04)
        return False

    def a_dica_da_04() -> None:
        piloto.ponte.perguntar(PASSAR_O_MOUSE % js(BOTOES["04"][2]),
                               lambda v, e: None)
        esperar("04-dica", LER_A_DICA, lambda leitura: leitura, recusa_da_04,
                "a dica do número fora abrir com o ponteiro em cima")

    def recusa_da_04() -> None:
        piloto.ponte.perguntar(FECHAR_A_DICA, lambda v, e: None)
        clicar_e_esperar_a_recusa(
            "04", lambda: abrir(PAGINA_02, BOTOES["02"][2], recusa_da_02))

    # ---- 02: a recusa com coluna, e o clique que só arma -----------------
    def recusa_da_02() -> None:
        clicar_e_esperar_a_recusa("02", o_clique_que_so_arma)

    def o_clique_que_so_arma() -> None:
        hv.pacotes.GESTOS[chave_02] = mudo_que_so_arma
        piloto.ponte.perguntar(
            VIGIAR_E_CLICAR % (js(BOTOES["02"][2]), js("02-armou"), "null"),
            lambda v, e: fora.__setitem__("02-armou-clique", str(v)))

        def pousou_e_passou_a_piscada(leitura: dict) -> dict | None:
            trilha = leitura.get("trilha")
            if not isinstance(trilha, list):
                return None
            pouso = _pousou(trilha)
            if pouso is None:
                return None
            # A PISCADA QUE NÃO DEVIA EXISTIR teria acendido no pouso e
            # apagado MS_DA_PISCADA depois: a leitura espera o prazo inteiro
            # passar, para ver as duas pontas de uma piscada que houvesse.
            if leitura["agora"] - pouso["t"] < hv.MS_DA_PISCADA + 300:
                return None
            return {"pouso": pouso, "trilha": trilha}

        def depois() -> None:
            fora["02-armou-desfecho"] = list(
                piloto.desfechos.get(f"{PAGINA_02}:mudo", ()))
            abrir(PAGINA_01, BOTOES["01"][2], recusa_da_01)

        esperar("02-armou", LER_A_TRILHA % js("02-armou"),
                pousou_e_passou_a_piscada, depois,
                "o botão do clique que só arma pousar, e o prazo da piscada passar")

    # ---- 01: a recusa sem coluna ------------------------------------------
    def recusa_da_01() -> None:
        clicar_e_esperar_a_recusa(
            "01", lambda: abrir(PAGINA_06, BOTOES["06"][2], recusa_da_06))

    # ---- 06: a colisão da troca de botões, pelo gesto real ----------------
    def recusa_da_06() -> None:
        clicar_e_esperar_a_recusa("06", fim)

    def fim() -> None:
        fora["diario"] = diario.getvalue()
        Gtk.main_quit()

    GLib.timeout_add(300, comecar)
    guarda = GLib.timeout_add(int(TETO_DO_ROTEIRO_S * 1000), Gtk.main_quit)
    try:
        # O LAÇO REENTRA ATÉ O ÚLTIMO PASSO: um `Gtk.main_quit` pendente de outro
        # teste de GUI do mesmo processo cai dentro deste `Gtk.main()` e o
        # encerra no meio (ver `test_o_recado_de_sucesso_pousa_no_cartao`). E o
        # DIÁRIO É O `stderr` DO PROCESSO: o `print(..., file=sys.stderr)` do
        # piloto resolve o nome na hora da chamada, então cai aqui.
        limite = _time.monotonic() + TETO_DO_ROTEIRO_S
        with contextlib.redirect_stderr(diario):
            while "diario" not in fora and _time.monotonic() < limite:
                Gtk.main()
    finally:
        no_ar["sim"] = False
        GLib.source_remove(guarda)
        piloto.pronto = False
        piloto.tela.janela.destroy()
        (hv.mesa_viva.estado_do_daemon, hv.ponte.identity_number_set,
         hv.ponte.mic_canal_set_detalhado) = guardado
        for k, velho in guardado_gestos.items():
            if velho is None:
                hv.pacotes.GESTOS.pop(k, None)
            else:
                hv.pacotes.GESTOS[k] = velho
    assert "diario" in fora, (
        f"o roteiro não chegou ao fim — o que voltou foi {sorted(fora)}, e o que "
        f"não chegou foi {faltou}")
    return fora


def _marco(medido: dict, marco: str) -> object:
    """A leitura de um marco — ou a reprova dizendo o que não chegou."""
    falta = medido["faltou"].get(marco)
    assert falta is None, f"o marco `{marco}` não chegou: {falta}"
    assert marco in medido, f"o roteiro não passou por `{marco}`: {sorted(medido)}"
    return medido[marco]


# --------------------------------------------------------------------------
# 0. os três botões recusaram — senão não há o que medir
# --------------------------------------------------------------------------
@pytest.mark.parametrize("caso", CASOS)
def test_o_botao_recusou_dizendo(medido: dict, caso: str) -> None:
    assert medido.get(f"{caso}-clique") == "cliquei", medido.get(f"{caso}-clique")
    desfecho = _marco(medido, f"{caso}-desfecho")
    assert isinstance(desfecho, list) and desfecho, desfecho
    classe, frase = desfecho
    assert classe == "recusou dizendo", (caso, desfecho)
    assert medido["frases"][caso] in frase, (caso, desfecho)


# --------------------------------------------------------------------------
# 1. a recusa não pousa recado nem frase — com coluna e sem coluna
# --------------------------------------------------------------------------
@pytest.mark.parametrize("caso", CASOS)
def test_a_recusa_nao_poe_frase_na_tela(medido: dict, caso: str) -> None:
    """A caixa da foto dela, e as outras três portas por onde a frase chegava.

    A leitura acontece DEPOIS de a piscada apagar — um segundo e meio de
    repintura por cima do clique. O canal antigo mantinha a frase 30 s no
    cartão, então ela estaria aqui.
    """
    tela = _marco(medido, f"{caso}-tela")
    assert isinstance(tela, dict), tela
    assert tela["aba"] == BOTOES[caso][0], tela
    assert tela["recados"] == 0, (
        f"{tela['aba']}: a recusa pousou {tela['recados']} recado(s) na tela — é a "
        f"caixa laranja que ela mandou parar de aparecer")
    assert not tela["visivel"], (
        f"{tela['aba']}: a frase da recusa está no texto visível da página")
    assert tela["dica"] == 0 and tela["title"] == 0, (
        f"{tela['aba']}: a frase da recusa está em {tela['dica']} dica(s) e "
        f"{tela['title']} `title` — a dica flutuante é uma das formas que saem")


# --------------------------------------------------------------------------
# 2. o botão veste a recusa, e a perde sozinho
# --------------------------------------------------------------------------
@pytest.mark.parametrize("caso", CASOS)
def test_o_botao_veste_a_recusa_e_a_perde_na_piscada(medido: dict, caso: str) -> None:
    import hefesto_vivo as hv

    recusa = _marco(medido, f"{caso}-recusa")
    assert isinstance(recusa, dict), recusa
    classes = str(recusa["pouso"]["classes"]).split()
    assert "hef-recusou" in classes, (
        f"{BOTOES[caso][0]}: o botão pousou sem a piscada de recusa ({classes}) — "
        f"sem frase na tela, é o sinal do botão que diz que o clique não valeu. "
        f"Trilha: {recusa['trilha']}")
    assert "hef-deu-certo" not in classes, (
        f"{BOTOES[caso][0]}: o botão que recusou piscou verde: {classes}")
    ms = int(hv.MS_DA_PISCADA)
    duracao = recusa["piscada"]["ms"]
    assert ms - 100 <= duracao <= ms + FOLGA_DA_PISCADA_MS, (
        f"{BOTOES[caso][0]}: a piscada de recusa durou {duracao} ms no relógio da "
        f"página, e o `MS_DA_PISCADA` é {ms} ms (folga de carga: "
        f"{FOLGA_DA_PISCADA_MS} ms)")


# --------------------------------------------------------------------------
# 3. a frase vai ao diário da janela
# --------------------------------------------------------------------------
@pytest.mark.parametrize("caso", CASOS)
def test_a_frase_da_recusa_vai_ao_diario(medido: dict, caso: str) -> None:
    pagina, gesto, _seletor = BOTOES[caso]
    prefixo = f"[gesto falhou] {pagina} · {gesto}: "
    linhas = [linha for linha in str(medido["diario"]).splitlines()
              if linha.startswith(prefixo)]
    assert any(medido["frases"][caso] in linha for linha in linhas), (
        f"a frase da recusa de {pagina} · {gesto} não chegou ao diário — ela saiu "
        f"da tela, e não pode sumir inteira. Linhas: {linhas!r}")


# --------------------------------------------------------------------------
# 4. o número fora diz só o número
# --------------------------------------------------------------------------
def test_o_numero_fora_diz_so_o_numero(medido: dict) -> None:
    """O cinza `.fora` já diz que o número não cabe; a dica diz qual é."""
    dica = _marco(medido, "04-dica")
    assert isinstance(dica, dict), dica
    assert dica["texto"] == "Player 2", (
        f"a dica do número fora diz {dica['texto']!r} — a frase da recusa não "
        f"chega à tela nem como dica flutuante")


# --------------------------------------------------------------------------
# 5. o clique que só arma não pisca
# --------------------------------------------------------------------------
def test_o_clique_que_so_arma_nao_pisca(medido: dict) -> None:
    """Verde sobre um clique que não aplicou nada afirma o que não aconteceu."""
    assert medido.get("02-armou-clique") == "cliquei", medido.get("02-armou-clique")
    assert _marco(medido, "02-armou-desfecho") == ["aplicou", ""]
    armou = _marco(medido, "02-armou")
    assert isinstance(armou, dict), armou
    acesas = [foto for foto in armou["trilha"]
              if {"hef-deu-certo", "hef-recusou"} & set(str(foto["classes"]).split())]
    assert acesas == [], (
        f"o clique que só armou piscou: {acesas} — a carga trouxe `armou`, e o "
        f"pouso não pode afirmar nem que aplicou nem que recusou")


# --------------------------------------------------------------------------
# 6. a aba 05 não declara lugar de recado
# --------------------------------------------------------------------------
@pytest.mark.parametrize("publicado", [False, True], ids=["bancada", "publicado"])
def test_a_aba_05_nao_declara_lugar_de_recado(publicado: bool) -> None:
    """A faixa `#vib-estado` era o terceiro lugar do recado; o recado saiu da tela."""
    import onde

    corpo = onde.pagina("05-vibracao.html", publicado=publicado).read_text(encoding="utf-8")
    assert 'class="vib-estado" id="vib-estado"' in corpo, (
        "a faixa de estado da 05 sumiu — sem ela a régua passaria sobre nada")
    assert "data-hef-recado" not in corpo, (
        "a 05 voltou a declarar lugar de recado — o piloto não põe frase na tela, "
        "e um endereço que ninguém lê é dado morto")


# --------------------------------------------------------------------------
# 7. as duas metades sem janela — a folha e a recusa que não escreve
# --------------------------------------------------------------------------
def test_a_folha_veste_a_recusa_sem_esconder_nada() -> None:
    """A classe mora na folha da casa, com a cor de aviso e sem ocupar espaço."""
    from hefesto_dualsense4unix.interface.folha_da_casa import (
        FOLHA_DA_CASA,
        seletores_escondidos,
    )

    partes = FOLHA_DA_CASA.split(".hef-recusou{", 1)
    assert len(partes) == 2, "a folha da casa perdeu a classe da piscada de recusa"
    regra = partes[1].split("}", 1)[0]
    assert "outline:" in regra and "var(--orange" in regra, regra
    assert regra.count("!important") >= 2, (
        f"a regra da recusa perdeu o `!important` — as páginas declaram "
        f"`border-color` e a folha de usuário perderia: {regra}")
    assert seletores_escondidos(FOLHA_DA_CASA) == (".nota",)


class _PilotoQueAnota:
    """Um piloto que anota TUDO o que a recusa tentar fazer além do diário."""

    def __init__(self) -> None:
        self.feito: list[str] = []

    def __getattr__(self, nome: str):
        def anotar(*args: object, **kwargs: object) -> None:
            self.feito.append(nome)
        return anotar


def test_a_recusa_so_escreve_no_diario(capsys) -> None:
    """A MORDIDA sem janela: devolva o depósito e esta lista deixa de ser vazia."""
    pytest.importorskip("gi", reason="o piloto importa o GTK")
    import hefesto_vivo as hv

    anotador = _PilotoQueAnota()
    volta = hv.Piloto._recusou_dizendo(
        anotador, PAGINA_04, "player", "aabbcc000001", RuntimeError("frase de prova"))
    assert volta is False
    assert anotador.feito == [], (
        f"a recusa fez mais que o diário: {anotador.feito} — a frase voltaria à "
        f"tela por ali")
    assert (f"[gesto falhou] {PAGINA_04} · player: frase de prova"
            in capsys.readouterr().err)


def test_a_chave_do_clique_que_so_arma_e_armou() -> None:
    """O NOME é contrato com a SISTEMA-BOTOES-01, que escreve a chave na carga."""
    pytest.importorskip("gi", reason="o piloto importa o GTK")
    import hefesto_vivo as hv

    assert hv.CHAVE_DO_CLIQUE_QUE_SO_ARMOU == "armou"


class _PilotoDoCliqueSemDono:
    """O mínimo que `Piloto._gesto` lê num clique sem dono, com o pouso anotado."""

    def __init__(self) -> None:
        self.gestos: list[dict] = []
        self.recusados: list[str] = []
        self.desfechos: dict[str, tuple[str, str]] = {}
        self.pagina = PAGINA_04
        self.pousos: list[tuple[str, object]] = []

    def _pousou(self, voo: str, certo: object = None) -> bool:
        self.pousos.append((voo, certo))
        return False


def test_o_clique_sem_dono_pisca_a_recusa(capsys) -> None:
    """Ninguém atende o clique: o botão pousa com `False`, a piscada de recusa.

    Visto no piloto oculto na validação desta sprint: o «Guardar» do
    remapeamento da aba 06, declarado sem dono em `a06_navegacao`, pousou
    `hef-recusou`; na base ele voltava do voo sem sinal nenhum.

    MORDIDA: troque `self._pousou(voo, False)` por `self._pousou(voo)` no ramo
    sem dono de `Piloto._gesto` — o pouso vira `None`, e esta régua reprova.
    """
    pytest.importorskip("gi", reason="o piloto importa o GTK")
    import hefesto_vivo as hv

    nome = "gesto-sem-dono-de-prova"
    falso = _PilotoDoCliqueSemDono()
    carga = {"gesto": nome, "voo": "7",
             "pagina": PAGINA_04}  # noqa-acento: chave da carga do piloto
    hv.Piloto._gesto(falso, carga)
    assert falso.desfechos == {f"{PAGINA_04}:{nome}": ("sem dono", "")}, falso.desfechos
    assert falso.pousos == [("7", False)], (
        f"o clique sem dono pousou {falso.pousos} — sem `False` o botão volta do "
        f"voo sem a piscada de recusa")
    assert f"[gesto sem dono] {PAGINA_04} · {nome}" in capsys.readouterr().out


def test_a_casa_tomada_diz_de_quem_e_sem_a_regra() -> None:
    """A dica do tom tomado da 04 é o nome do dono, e a regra colada saiu.

    MORDIDA: devolva «… já está neste tom — duas peças nunca ficam da mesma
    cor.» ao `titulo` de `a04_iluminacao.fileira_de_tons` e esta régua reprova;
    troque o nome pela frase da casa livre e reprova também a régua do X, em
    `test_fecha_iluminacao_01_duas_pecas_nunca_tem_a_mesma_cor`.
    """
    from hefesto_dualsense4unix.core.led_control import player_slot_color
    from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

    tomado = "#{:02X}{:02X}{:02X}".format(*player_slot_color(2))
    html = a04.fileira_de_tons(
        "", {tomado: {"nome": "P2 (DualSense)", "plastico": "#1c1c1c"}})
    casas = [linha for linha in html.splitlines() if "tomado" in linha]
    assert len(casas) == 1, html
    assert 'title="P2 (DualSense)"' in casas[0], casas[0]
    assert "duas peças" not in html, casas[0]
