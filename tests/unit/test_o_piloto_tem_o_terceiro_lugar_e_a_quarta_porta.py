#!/usr/bin/env python3
"""AS TRÊS PEÇAS DE INFRA DO PILOTO — ONDA5-P-01, 06/09/2026.

Três relatos que a ONDA CINCO deixou para o piloto, e nenhuma das três frentes
podia escrevê-los: ``hefesto_vivo.py`` está no ``nao_toca`` de todas.

1. **O TERCEIRO LUGAR DO RECADO.** A página pode declarar onde o recado pousa
   (``data-hef-recados``), e o depósito só conhecia cartão e tarja. A metade que
   já existia entrou na costura de 06/09 (`14e0771f`); o que falta aqui é a
   outra metade da decisão: **um lugar por página**. Com dois containers
   declarando o mesmo tom, um ``querySelector`` escolheria o primeiro do
   documento — a tela decidindo por ordem de marcação. O piloto **recusa os
   dois**, diz quais são em ``window.__hef.faixasDemais`` e cai no comportamento
   de sempre.

2. **A QUARTA PORTA — ``data-hef-vivo``.** O ouvinte tinha três portas
   (``change``, ``click``, ``blur``) e nas três quem responde é o gesto de
   ``data-hef-gesto`` — que no campo do jogo da aba 10 **grava o perfil dela**.
   O ``input`` é o único evento que um campo de texto dispara a cada TECLA, e
   ligá-lo ao mesmo atributo regravaria o ``.json`` a cada letra. A porta nova
   carrega endereço PRÓPRIO e de LEITURA.

3. **O DONO DO CAMPO — assento não é modelo.** O desenho compartilhado leva
   ``data-controle="dualsense"`` (``ds_limpo.svg:2``), e ali o valor é o MODELO.
   O piloto resolvia o dono subindo até o primeiro ``data-controle``, então todo
   campo de dentro do ``<svg>`` voltava com dono ``"dualsense"``. **Não é
   hipotético:** ``treme-e`` e ``treme-d`` da ``05-vibracao`` moram lá dentro,
   nas colunas do p1 e do p2.

POR QUE ELA ABRE UM WebKit DE VERDADE, com o piloto do produto: porque a forma
de defeito mais cara desta casa é *alguém curar o caminho e provar a cura num
caminho que ela não usa*. O clique é no botão do produto, o ``input`` é um
``Event`` de verdade no ouvinte de verdade, e a leitura é do DOM.

A JANELA É OCULTA. Ela tem UMA tela.

AS MORDIDAS, uma por peça (as três estão escritas nas docstrings dos testes):

* tire o ``data-hef-recados`` e o recado volta ao cartão; ponha DOIS e a régua
  reprova nomeando os dois;
* ligue ``data-hef-vivo`` ao gesto que grava e a régua reprova nomeando o gesto;
  arranque a quarta porta e o ``input`` volta a não fazer nada;
* ponha um ``data-campo`` dentro do ``<svg>`` de uma coluna ``p2`` e leia o
  dono: tem de ser ``p2``, nunca ``dualsense``.
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

#: A PÁGINA DO CLIQUE. A `02-controles` é a única das dez cujo HTML PUBLICADO
#: traz um botão de gesto dentro do cartão de um controle (`data-mudo`), e é a
#: mesma que a régua irmã do canal de recado usa.
PAGINA = "02-controles.html"

#: A PÁGINA DO DESENHO COMPARTILHADO. A `05-vibracao` é onde o defeito do dono
#: está VIVO no arquivo publicado: `treme-e` e `treme-d` moram dentro do
#: `<svg data-controle="dualsense">`, nas colunas do p1 e do p2.
PAGINA_DO_SVG = "05-vibracao.html"

#: O GESTO DA ABA 02 que a régua sequestra para o clique — o mesmo da irmã.
GESTO_DO_CLIQUE = "mudo"

#: OS TRÊS GESTOS VIVOS que esta régua registra. Nomes próprios, para não
#: colidirem com nenhum dos que os pacotes declaram.
VIVO = "regua-vivo"
VIVO_QUE_GRAVA = "regua-vivo-que-grava"
VIVO_QUE_TROCA_BLOCO = "regua-vivo-com-bloco"

#: O ENDEREÇO QUE O GESTO VIVO PINTA. Ele nasce nesta régua, dentro da coluna do
#: p1 — nenhuma das dez páginas publica um campo vivo, porque publicar é ato
#: dela e a metade do endereço é da frente da aba.
CAMPO_DO_ROTULO = "regua-jogo-rotulo"

FRASE_DO_RECADO = "o motor recebeu, mas o perfil não guardou"


def _ctl(uniq: str, transporte: str, jogador: int) -> dict:
    return {"uniq": uniq, "connected": True, "transport": transporte,
            "player": jogador, "audio": {"mic_mudo": False}}


ESTADO = {
    "active_profile": "regua",
    "gamepad_emulation": {"flavor": "dualsense"},
    "controllers": [_ctl(UNIQ_P1, "usb", 1), _ctl(UNIQ_P2, "bt", 2)],
}

MESA = {"estado": ESTADO}

#: QUANTO O GESTO VIVO LENTO DEMORA. Ele existe para a prova da ordem: sem uma
#: leitura que demore, as duas respostas voltam na ordem em que saíram e o
#: descarte nunca é exercido.
VIVO_LENTO_S = 0.9

#: O QUE A LEITURA DEVOLVE em cada volta. A régua compara o que ficou na tela.
ROTULO_VELHO = "o rótulo da tecla velha"
ROTULO_NOVO = "o rótulo da tecla nova"

#: QUANTO O CLIQUE LENTO DA CORRIDA DEMORA. Ele tem de pousar DEPOIS de o
#: vizinho ter escrito o desfecho dele — é esse atraso que faz a corrida
#: existir — e ANTES de a piscada do vizinho vencer (`MS_DA_PISCADA`, 1,5 s).
CORRIDA_LENTA_S = 0.8


LER_A_TELA = r"""
(function(){
  const recados = [];
  for(const el of document.querySelectorAll('.hef-recado')){
    const pai = el.parentElement;
    recados.push({
      chave: el.getAttribute('data-hef-recado') || '',
      texto: (el.textContent || '').trim(),
      lugar: el.dataset.hefLugar || '',
      classe: el.className,
      pai: pai ? (pai.id || (pai.tagName.toLowerCase() + '.' + pai.className)) : '',
    });
  }
  const campo = document.querySelector('[data-campo="ROTULO"]');
  return JSON.stringify({
    recados: recados,
    faixas_demais: (window.__hef && window.__hef.faixasDemais) || {},
    rotulo: campo ? (campo.textContent || '').trim() : null,
  });
})()
""".replace("ROTULO", CAMPO_DO_ROTULO)

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

#: O CLIQUE NO 🎙 DE UMA COLUNA QUALQUER — o mesmo gesto, dois elementos.
#: É o que exercita as DUAS threads na mesma chave de desfecho: o `click` e o
#: `change` de um `<select>` chegam assim, e dois cliques em colunas diferentes
#: reproduzem a corrida com um roteiro que se lê.
CLICAR_NO_MIC_DE = r"""
(function(pref){
  const b = document.querySelector('[data-controle="' + pref + '"] [data-mudo="microfone"]');
  if(!b) return 'NAO ACHEI O BOTAO DO MICROFONE EM ' + pref;
  b.click();
  return 'cliquei em ' + pref;
})(%s)
"""

#: O QUE CADA BOTÃO DE MICROFONE MOSTRA — a classe do "deu certo" é o que
#: separa a piscada verde do silêncio.
LER_OS_DOIS_BOTOES = r"""
(function(){
  const fora = {};
  for(const pref of ['p1', 'p2']){
    const b = document.querySelector('[data-controle="' + pref + '"] [data-mudo="microfone"]');
    fora[pref] = b ? {deu_certo: b.classList.contains('hef-deu-certo'),
                      em_voo: b.classList.contains('hef-em-voo')} : null;
  }
  return JSON.stringify(fora);
})()
"""

#: AS FAIXAS QUE A PÁGINA DECLARARIA. Nenhuma das dez publicadas traz o
#: atributo — publicar é ato dela —, então a régua o escreve, que é o mesmo que
#: a `ONDA5-05-03` fez no `#vib-estado` da bancada.
#:
#: O TOM DA FAIXA PASSOU A SER `recusa` EM 13/09/2026 (TELA-CALADA-01). Até
#: então a régua declarava `sucesso` e clicava um gesto que devolvia recado; o
#: sucesso deixou de ser depositado por pedido dela (*"em todas as abas da
#: interface"*), e o único tom que ainda atravessa o canal é a recusa. O que
#: esta régua mede — a página declara o lugar, e dois lugares iguais perdem os
#: dois — é do BOOTSTRAP, e não do tom.
POR_AS_FAIXAS = r"""
(function(quantas){
  for(const v of document.querySelectorAll('.regua-faixa')) v.remove();
  for(let i = 0; i < quantas; i++){
    const d = document.createElement('div');
    d.className = 'regua-faixa';
    d.id = 'regua-faixa-' + i;
    d.setAttribute('data-hef-recados', 'recusa');
    d.setAttribute('data-hef-recado-classe', 'est recibo');
    document.body.appendChild(d);
  }
  return String(document.querySelectorAll('[data-hef-recados]').length);
})(%d)
"""

#: O CAMPO VIVO, criado e disparado NA MESMA CHAMADA. Criar antes e disparar
#: depois deixaria uma janela de tiques em que a pintura pode trocar o bloco que
#: o abriga — e a régua mediria o sumiço do elemento, não a porta.
O_CAMPO_VIVO = r"""
(function(vivo, gesto, evento, valor){
  const col = document.querySelector('[data-controle="p1"]') || document.body;
  let el = document.getElementById('regua-campo-vivo');
  if(!el){
    el = document.createElement('input');
    el.id = 'regua-campo-vivo';
    el.setAttribute('data-campo', 'regua-jogo');
    col.appendChild(el);
  }
  let rot = document.querySelector('[data-campo="ROTULO"]');
  if(!rot){
    rot = document.createElement('span');
    rot.setAttribute('data-campo', 'ROTULO');
    col.appendChild(rot);
  }
  // O RUÍDO DE PROPÓSITO: `data-vivo` é um atributo que nenhuma página tem
  // hoje, e o ouvinte manda o DATASET INTEIRO ao Python. Sem a marca do vivo
  // nascer vazia na carga, este atributo faria um CLIQUE cair no caminho do
  // gesto vivo — calado, e com a guarda de gravação por cima.
  el.setAttribute('data-vivo', 'ruido');
  if(vivo){ el.setAttribute('data-hef-vivo', vivo); }
  else { el.removeAttribute('data-hef-vivo'); }
  if(gesto){ el.setAttribute('data-hef-gesto', gesto); }
  else { el.removeAttribute('data-hef-gesto'); }
  el.value = valor;
  el.dispatchEvent(new Event(evento, {bubbles: true}));
  return JSON.stringify({
    em_voo: el.classList.contains('hef-em-voo'),
    voo: el.getAttribute('data-hef-voo') || '',
  });
})(%s, %s, %s, %s)
""".replace("ROTULO", CAMPO_DO_ROTULO)

#: O DONO DE CADA CAMPO, lido pelo INSTRUMENTO DO PRODUTO — `LER_CAMPOS`, o
#: mesmo que o `--prova-de-mockup` usa. Reescrevê-lo aqui mediria a régua, não o
#: piloto.
SO_OS_QUE_TREMEM = ("treme-e", "treme-d")


#: O PERFIL ATIVO PRECISA EXISTIR NO DISCO — mesma razão da régua irmã: desde
#: que a aba 02 aprendeu a GUARDAR o som por controle, o gesto lê o perfil ativo
#: para escrever nele.
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
    """Abre o piloto DE VERDADE, oculto, e roda o roteiro das três peças."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    import argparse
    import json as _json_mod
    import time as _time

    import hefesto_vivo as hv

    chamados: list[str] = []

    # OS DUBLÊS SÃO DEVOLVIDOS NO FIM. `mesa_viva` e o registro `GESTOS` são
    # módulos COMPARTILHADOS do produto: escrever neles sem devolver deixaria,
    # no mesmo processo, uma mesa de mentira para todo vizinho que abrir um
    # `Piloto` depois.
    chaves = [(PAGINA, GESTO_DO_CLIQUE), (PAGINA, VIVO),
              (PAGINA, VIVO_QUE_GRAVA), (PAGINA, VIVO_QUE_TROCA_BLOCO)]
    guardado_gestos = {k: hv.pacotes.GESTOS.get(k) for k in chaves}
    guardado_mexem = {k: hv.pacotes.GESTOS_QUE_MEXEM.get(k) for k in chaves}
    guardado_estado = hv.mesa_viva.estado_do_daemon

    MESA["estado"] = ESTADO
    hv.mesa_viva.estado_do_daemon = lambda *a, **k: MESA["estado"]  # type: ignore[assignment]

    # O CLIQUE RECUSA DESDE 13/09/2026 (TELA-CALADA-01): o recado de sucesso
    # deixou de ser depositado, e a recusa é o tom que ainda chega às faixas e
    # ao cartão. A frase é a mesma; o caminho passou a ser o `RuntimeError`.
    def clique_que_diz(ctx, o, p):
        chamados.append(f"clique:{GESTO_DO_CLIQUE}")
        raise RuntimeError(FRASE_DO_RECADO)

    def vivo_que_le(ctx, o, p):
        """A leitura: devolve carga de pintura, e nada mais.

        A LENTIDÃO É POR VALOR, e é o que torna a ordem mensurável: a "tecla
        velha" demora, a "tecla nova" responde na hora — exatamente o caso em
        que a resposta velha chegaria por último.
        """
        chamados.append(f"vivo:{o.get('valor')}")
        if str(o.get("valor") or "") == "velha":
            _time.sleep(VIVO_LENTO_S)
            return {"colunas": {"p1": {CAMPO_DO_ROTULO: ROTULO_VELHO}}}
        if str(o.get("valor") or "") == "nova":
            return {"colunas": {"p1": {CAMPO_DO_ROTULO: ROTULO_NOVO}}}
        return {"colunas": {"p1": {CAMPO_DO_ROTULO: f"li {o.get('valor')}"}}}

    def vivo_que_grava(ctx, o, p):
        chamados.append("vivo:GRAVOU")
        return None

    def vivo_com_bloco(ctx, o, p):
        chamados.append("vivo:bloco")
        return {"blocos": {"[data-controle=\"p1\"]": "<b>a coluna inteira</b>"}}

    hv.pacotes.GESTOS[(PAGINA, GESTO_DO_CLIQUE)] = clique_que_diz
    hv.pacotes.GESTOS[(PAGINA, VIVO)] = vivo_que_le
    hv.pacotes.GESTOS[(PAGINA, VIVO_QUE_GRAVA)] = vivo_que_grava
    hv.pacotes.GESTOS[(PAGINA, VIVO_QUE_TROCA_BLOCO)] = vivo_com_bloco
    # O `grava=` É O QUE O DECORADOR ESCREVERIA. A guarda do piloto pergunta ao
    # registro, que é o dono — e não a uma lista própria.
    hv.pacotes.GESTOS_QUE_MEXEM[(PAGINA, VIVO_QUE_GRAVA)] = "save_profile"

    args = argparse.Namespace(
        oculta=True, segundos=0.0, passear=False, parada=900, foto="",
        abre=PAGINA, prova_no_aparelho=False, entre=2500,
        espera=1200, incluir_perigosos=False, prova_clique="", sem_cor=True,
        prova_de_mockup=False, voltas_por_aba=8, teto_de_mockup=-1,
        sem_cravado=False, sem_selo=False,
    )
    piloto = hv.Piloto(args)
    fora: dict[str, object] = {"chamados": chamados}

    def ler(rotulo: str):
        def _leu(valor, erro):
            fora[rotulo] = (f"ERRO {erro}" if erro is not None
                            else _json_mod.loads(str(valor)))
        return _leu

    def anotar(rotulo: str):
        def _leu(valor, erro):
            fora[rotulo] = f"ERRO {erro}" if erro is not None else str(valor)
        return _leu

    def js(valor: object) -> str:
        return _json_mod.dumps(valor)

    def campo_vivo(vivo: object, gesto: object, evento: str, valor: str) -> str:
        return O_CAMPO_VIVO % (js(vivo), js(gesto), js(evento), js(valor))

    def por_gesto(fn) -> None:
        """Troca quem atende o 🎙 — pelo REGISTRO do produto, não por atalho.

        `@gesto` grava em `pacotes.GESTOS`, e é daí que o `_gesto` lê. Injetar
        aqui é exercitar exatamente o caminho que um pacote real percorre.
        """
        hv.pacotes.GESTOS[(PAGINA, GESTO_DO_CLIQUE)] = fn

    # ---- o roteiro, um passo por peça ----------------------------------
    def sem_faixa() -> bool:
        if not piloto.pronto:
            return True
        piloto.ponte.perguntar(POR_AS_FAIXAS % 0, anotar("faixas-0"))
        piloto.ponte.perguntar(CLICAR_NO_MIC, anotar("clique-1"))
        GLib.timeout_add(700, leu_sem_faixa)
        return False

    def leu_sem_faixa() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("sem-faixa"))
        GLib.timeout_add(300, com_uma_faixa)
        return False

    def com_uma_faixa() -> bool:
        piloto.ponte.perguntar(POR_AS_FAIXAS % 1, anotar("faixas-1"))
        piloto.ponte.perguntar(CLICAR_NO_MIC, anotar("clique-2"))
        GLib.timeout_add(700, leu_com_uma_faixa)
        return False

    def leu_com_uma_faixa() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("com-uma-faixa"))
        GLib.timeout_add(300, com_duas_faixas)
        return False

    def com_duas_faixas() -> bool:
        piloto.ponte.perguntar(POR_AS_FAIXAS % 2, anotar("faixas-2"))
        piloto.ponte.perguntar(CLICAR_NO_MIC, anotar("clique-3"))
        GLib.timeout_add(700, leu_com_duas_faixas)
        return False

    def leu_com_duas_faixas() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("com-duas-faixas"))
        piloto.ponte.perguntar(POR_AS_FAIXAS % 0, anotar("faixas-fim"))
        GLib.timeout_add(300, a_porta_muda)
        return False

    # ---- a quarta porta ------------------------------------------------
    def a_porta_muda() -> bool:
        # SEM `data-hef-vivo` O `input` NÃO FAZ NADA — é a mordida da peça 2, e
        # ela vem ANTES da cura para que a lista de chamados fique legível.
        fora["chamados-antes-da-porta-muda"] = list(chamados)
        piloto.ponte.perguntar(
            campo_vivo(None, GESTO_DO_CLIQUE, "input", "muda"),
            anotar("porta-muda"))
        GLib.timeout_add(500, a_porta_viva)
        return False

    def a_porta_viva() -> bool:
        fora["chamados-antes-do-vivo"] = list(chamados)
        piloto.ponte.perguntar(
            campo_vivo(VIVO, GESTO_DO_CLIQUE, "input", "abc"),
            anotar("porta-viva"))
        GLib.timeout_add(600, leu_a_porta_viva)
        return False

    def leu_a_porta_viva() -> bool:
        fora["chamados-depois-do-vivo"] = list(chamados)
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-do-vivo"))
        GLib.timeout_add(300, o_vivo_que_grava)
        return False

    def o_vivo_que_grava() -> bool:
        piloto.ponte.perguntar(
            campo_vivo(VIVO_QUE_GRAVA, None, "input", "xyz"),
            anotar("porta-que-grava"))
        GLib.timeout_add(500, o_vivo_com_bloco)
        return False

    def o_vivo_com_bloco() -> bool:
        fora["chamados-depois-do-grava"] = list(chamados)
        piloto.ponte.perguntar(
            campo_vivo(VIVO_QUE_TROCA_BLOCO, None, "input", "bloco"),
            anotar("porta-com-bloco"))
        GLib.timeout_add(500, leu_o_bloco)
        return False

    def leu_o_bloco() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-do-bloco"))
        GLib.timeout_add(300, duas_teclas)
        return False

    def duas_teclas() -> bool:
        # A ORDEM: a "velha" demora, a "nova" responde na hora. A resposta que
        # chegar por último é a velha, e ela NÃO pode pintar.
        piloto.ponte.perguntar(
            campo_vivo(VIVO, None, "input", "velha"), anotar("tecla-velha"))
        GLib.timeout_add(120, a_tecla_nova)
        return False

    def a_tecla_nova() -> bool:
        piloto.ponte.perguntar(
            campo_vivo(VIVO, None, "input", "nova"), anotar("tecla-nova"))
        GLib.timeout_add(int(VIVO_LENTO_S * 1000) + 700, leu_as_duas_teclas)
        return False

    def leu_as_duas_teclas() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-das-duas-teclas"))
        GLib.timeout_add(300, a_terceira_porta)
        return False

    def a_terceira_porta() -> bool:
        # AS TRÊS PORTAS DE HOJE NÃO MUDARAM: um `change` no MESMO elemento, que
        # carrega os dois atributos, continua despachando o `data-hef-gesto`.
        fora["chamados-antes-do-change"] = list(chamados)
        # O DEPÓSITO E A TELA ZERAM ANTES DO `change` — 13/09/2026. O clique
        # passou a RECUSAR (TELA-CALADA-01), e a recusa vive 30 s: sem zerar,
        # a de `clique-3` ainda estaria na tela aqui, e a asserção de que o
        # `change` depositou passaria sobre um recado velho. O recibo de
        # sucesso, que vivia 6 s, já tinha vencido quando esta fase chegava.
        piloto._recados.clear()
        piloto.ponte.perguntar(
            "for(const el of document.querySelectorAll('.hef-recado')) el.remove();"
            " String(document.querySelectorAll('.hef-recado').length)",
            anotar("zerou-antes-do-change"))
        piloto.ponte.perguntar(
            campo_vivo(VIVO, GESTO_DO_CLIQUE, "change", "abc"),
            anotar("porta-change"))
        GLib.timeout_add(700, leu_a_terceira_porta)
        return False

    def leu_a_terceira_porta() -> bool:
        fora["chamados-depois-do-change"] = list(chamados)
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-do-change"))
        GLib.timeout_add(400, a_corrida_do_desfecho)
        return False

    # ---- a corrida do desfecho (achado da ONDA5-01-03) ------------------
    def a_corrida_do_desfecho() -> bool:
        """DUAS THREADS, UMA CHAVE — e a corrida é FORJADA, não esperada.

        **A primeira versão desta fase não mordia**, e a razão é a forma do
        defeito: entre o `except` que ESCREVE o desfecho e o `finally` que o LÊ
        não passa tempo nenhum — nem uma linha. Fazer um gesto demorar não abre
        essa fresta; medido em 06/09/2026, com a cura arrancada e a régua verde.

        Então a fresta se abre POR DENTRO, no dicionário do produto: quando a
        thread que RECUSOU escreve o desfecho dela, este `dict` a segura e deixa
        a vizinha escrever `"aplicou"` na mesma chave. É exatamente o
        entrelaçamento que o escalonador pode produzir sozinho e que ninguém
        consegue agendar de fora.

        O DICIONÁRIO É O DO PRODUTO — a mesma classe, o mesmo atributo, o mesmo
        `__setitem__` que o `_gesto` chama. Não há dublê de comportamento aqui:
        só um ponto de sincronização.
        """
        import threading as _th

        recusou = _th.Event()
        aplicou = _th.Event()

        class DicionarioQueEntrelacaAsDuas(dict):
            def __setitem__(self, chave, valor):
                super().__setitem__(chave, valor)
                if valor and valor[0] == "aplicou":
                    aplicou.set()
                elif valor and valor[0] == "recusou dizendo":
                    # A THREAD QUE RECUSOU ESPERA AQUI, entre a escrita e a
                    # leitura do `finally`. É a única fresta do defeito.
                    recusou.set()
                    aplicou.wait(timeout=5.0)

        piloto.desfechos = DicionarioQueEntrelacaAsDuas(piloto.desfechos)

        def por_controle(ctx, o, p):
            qual = str(o.get("controle") or "")
            chamados.append(f"corrida:{qual}")
            if qual == "p1":
                raise RuntimeError("o daemon não confirmou o mudo do microfone")
            # O p2 SÓ APLICA DEPOIS de o p1 ter escrito a recusa — senão as duas
            # escritas saem na ordem em que o escalonador quiser, e a régua
            # mediria uma corrida diferente a cada execução.
            recusou.wait(timeout=5.0)
            return None

        por_gesto(por_controle)
        piloto.ponte.perguntar(CLICAR_NO_MIC_DE % js("p1"), anotar("corrida-p1"))
        GLib.timeout_add(150, a_corrida_do_p2)
        return False

    def a_corrida_do_p2() -> bool:
        piloto.ponte.perguntar(CLICAR_NO_MIC_DE % js("p2"), anotar("corrida-p2"))
        # LER DENTRO DA PISCADA DOS DOIS: os dois pousam em menos de 300 ms — o
        # p1 destrava assim que o p2 escreve —, e `MS_DA_PISCADA` é 1,5 s. Aos
        # ~700 ms os dois estão dentro da janela, e é o único instante em que
        # "o p2 piscou" e "o p1 não piscou" se medem juntos.
        GLib.timeout_add(700, leu_a_corrida)
        return False

    def leu_a_corrida() -> bool:
        piloto.ponte.perguntar(LER_OS_DOIS_BOTOES, ler("a-corrida"))
        GLib.timeout_add(300, ir_para_o_svg)
        return False

    # ---- o dono do campo ------------------------------------------------
    def ir_para_o_svg() -> bool:
        piloto._ir(PAGINA_DO_SVG)
        GLib.timeout_add(2500, leu_o_svg)
        return False

    def leu_o_svg() -> bool:
        piloto.ponte.perguntar(hv.LER_CAMPOS, ler("campos-do-svg"))
        GLib.timeout_add(500, fim)
        return False

    def fim() -> bool:
        fora["vivos_atendidos"] = list(piloto.vivos_atendidos)
        fora["vivos_recusados"] = list(piloto.vivos_recusados)
        fora["vivos_descartados"] = piloto.vivos_descartados
        fora["gestos"] = [
            {"gesto": g.get("gesto"), "vivo": g.get("vivo", ""),
             "voo": g.get("voo", ""), "evento": g.get("evento", ""),
             "controle": g.get("controle", "")}
            for g in piloto.gestos]
        fora["chamados_finais"] = list(chamados)
        Gtk.main_quit()
        return False

    GLib.timeout_add(400, lambda: piloto._ir(args.abre))
    GLib.timeout_add(2000, sem_faixa)
    # O RELÓGIO DE SEGURANÇA GUARDA O SEU `id` e é desarmado no `finally`: um
    # `timeout_add` pendente depois da fixture dispara DENTRO do laço do PRÓXIMO
    # teste de GUI do mesmo processo. Já matou onze medições de um vizinho.
    guarda = GLib.timeout_add(90000, Gtk.main_quit)
    try:
        # O LAÇO REENTRA ATÉ O ROTEIRO ACABAR, e a condição é a ÚLTIMA etapa —
        # ver a nota inteira em `test_o_recado_de_sucesso_pousa_no_cartao`: um
        # `Gtk.main_quit` pendente de OUTRO teste de GUI do mesmo processo cai
        # dentro deste laço e o encerra no meio.
        limite = _time.monotonic() + 90.0
        while "chamados_finais" not in fora and _time.monotonic() < limite:
            Gtk.main()
    finally:
        GLib.source_remove(guarda)
        # E O PILOTO TAMBÉM PARA: o tique é um `timeout_add` que se reagenda
        # para sempre, e deixá-lo vivo faria esta janela pintar por cima de todo
        # laço GTK que vier depois, no mesmo processo.
        piloto.pronto = False
        piloto.tela.janela.destroy()
        hv.mesa_viva.estado_do_daemon = guardado_estado  # type: ignore[assignment]
        for k, velho in guardado_gestos.items():
            if velho is None:
                hv.pacotes.GESTOS.pop(k, None)
            else:
                hv.pacotes.GESTOS[k] = velho
        for k, velho in guardado_mexem.items():
            if velho is None:
                hv.pacotes.GESTOS_QUE_MEXEM.pop(k, None)
            else:
                hv.pacotes.GESTOS_QUE_MEXEM[k] = velho
        MESA["estado"] = ESTADO
    assert "chamados_finais" in fora, (
        f"o roteiro não chegou ao fim — o que voltou foi {sorted(fora)}. "
        f"O último passo é o `fim()`, e é ele que guarda os `chamados_finais`: "
        f"esperar por qualquer passo anterior deixa a régua verde sobre uma "
        f"medição pela metade.")
    return fora


def _r(leitura: object) -> list[dict]:
    assert isinstance(leitura, dict), leitura
    return list(leitura["recados"])


# --------------------------------------------------------------------------
# 1. o terceiro lugar — a página declara onde o recado pousa
# --------------------------------------------------------------------------
def test_sem_o_atributo_o_recado_continua_no_cartao(medido: dict) -> None:
    """A MORDIDA da peça 1, primeira metade: sem `data-hef-recados`, nada muda.

    É a régua de regressão das dez abas. Nenhuma das dez páginas publicadas traz
    o atributo — publicar é ato dela —, então o comportamento de hoje tem de ser
    byte a byte o de ontem: cartão, e tarja para quem não tem cartão.
    """
    recados = _r(medido["sem-faixa"])
    assert recados, (
        "o clique no 🎙 do p1 não deixou recado nenhum na tela — sem recado não "
        f"há lugar a medir. O que chegou: {medido['clique-1']!r}")
    assert [r["texto"] for r in recados] == [FRASE_DO_RECADO], recados
    assert recados[0]["lugar"] in ("grade", "fluxo"), (
        f"sem faixa declarada o recado tinha de pousar no CARTÃO, e pousou em "
        f"{recados[0]['lugar']!r} (pai {recados[0]['pai']!r})")


def test_com_uma_faixa_o_recado_pousa_nela(medido: dict) -> None:
    """A peça 1: a página declara o lugar, e o recado vai para lá.

    E QUEM PINTA É A PÁGINA: o `data-hef-recado-classe` diz com que classes o
    recado se veste. Uma caixa com borda do piloto ao lado das linhas da faixa
    seriam dois desenhos para a mesma linha.
    """
    assert medido["faixas-1"] == "1", (
        f"a régua não conseguiu declarar UMA faixa: {medido['faixas-1']!r}")
    recados = _r(medido["com-uma-faixa"])
    assert recados, "o recado sumiu quando a faixa apareceu"
    r = recados[0]
    assert r["lugar"] == "faixa", (
        f"o recado não pousou na faixa declarada: lugar={r['lugar']!r}, "
        f"pai={r['pai']!r}")
    assert r["pai"] == "regua-faixa-0", (
        f"o recado pousou fora do container declarado: {r['pai']!r}")
    assert "est" in r["classe"] and "recibo" in r["classe"], (
        f"a faixa manda as classes pelo `data-hef-recado-classe`, e o recado "
        f"veste {r['classe']!r}")


def test_dois_lugares_iguais_a_pagina_perde_os_dois(medido: dict) -> None:
    """A MORDIDA da peça 1, segunda metade: DOIS containers, e a régua nomeia.

    Um `querySelector` escolheria o primeiro do documento — a tela decidindo por
    ordem de marcação, que é o defeito da lista plana (T-04). O piloto recusa os
    dois e volta ao cartão, que é o comportamento sem atributo nenhum.

    ARRANQUE A CURA — troque a recusa por `document.querySelector(…)` — e o
    recado volta a pousar na primeira faixa, com `faixas_demais` vazio: esta
    régua reprova nas duas asserções.
    """
    assert medido["faixas-2"] == "2", (
        f"a régua não conseguiu declarar DUAS faixas: {medido['faixas-2']!r}")
    leitura = medido["com-duas-faixas"]
    assert isinstance(leitura, dict), leitura
    demais = leitura["faixas_demais"]
    # O TOM É `recusa` DESDE 13/09/2026 — ver a nota do `POR_AS_FAIXAS`.
    assert "recusa" in demais, (
        "com dois containers declarando o mesmo tom o piloto tinha de RECUSAR "
        f"os dois e dizer quais são; `faixasDemais` veio {demais!r}")
    assert sorted(demais["recusa"]) == ["regua-faixa-0", "regua-faixa-1"], (
        f"a recusa não nomeou os dois: {demais['recusa']!r}")
    recados = _r(leitura)
    assert recados, "o recado sumiu com as duas faixas"
    assert recados[0]["lugar"] in ("grade", "fluxo"), (
        f"com dois lugares declarados o recado tinha de voltar ao cartão, e "
        f"pousou em {recados[0]['lugar']!r} (pai {recados[0]['pai']!r}) — a "
        f"tela escolheu por ordem do documento")


# --------------------------------------------------------------------------
# 2. a quarta porta — `data-hef-vivo`, o gesto que lê e não grava
# --------------------------------------------------------------------------
def test_sem_o_atributo_o_input_nao_faz_nada(medido: dict) -> None:
    """A MORDIDA da peça 2, primeira metade: o `input` nasce mudo sem endereço.

    É a régua de regressão das dez abas: nenhuma delas publica `data-hef-vivo`,
    então a porta nova não pode acordar gesto nenhum por conta própria. O
    elemento do disparo CARREGA um `data-hef-gesto` — e é justamente ele que não
    pode ser chamado por uma tecla.
    """
    antes = list(medido["chamados-antes-da-porta-muda"])
    depois = list(medido["chamados-antes-do-vivo"])
    novos = depois[len(antes):]
    assert novos == [], (
        f"um `input` sem `data-hef-vivo` acordou um gesto: {novos!r}. O "
        f"elemento carrega `data-hef-gesto`, e é justamente ele que não pode "
        f"ser chamado por uma tecla")


def test_a_quarta_porta_despacha_o_gesto_de_leitura(medido: dict) -> None:
    """A peça 2: o `input` chama o gesto de `data-hef-vivo`, e só ele.

    O elemento carrega os DOIS atributos de propósito: é a forma que o campo do
    jogo da aba 10 terá — `data-hef-gesto="editor.jogo"` para o `change`, que
    grava, e `data-hef-vivo` para a tecla, que lê.
    """
    novos = [c for c in medido["chamados-depois-do-vivo"]
             if c not in medido["chamados-antes-do-vivo"]]
    assert "vivo:abc" in novos, (
        f"a quarta porta não despachou o gesto vivo: {novos!r}")
    assert f"clique:{GESTO_DO_CLIQUE}" not in novos, (
        f"o `input` despachou TAMBÉM o gesto de `data-hef-gesto`, que grava no "
        f"disco dela: {novos!r}")
    assert f"{PAGINA}:{VIVO}" in medido["vivos_atendidos"], (
        f"o piloto não contou a leitura: {medido['vivos_atendidos']!r}")


def test_a_leitura_pinta_o_que_trouxe(medido: dict) -> None:
    """A resposta do gesto vivo é carga de pintura, e ela chega à tela."""
    leitura = medido["depois-do-vivo"]
    assert isinstance(leitura, dict), leitura
    assert leitura["rotulo"] == "li abc", (
        f"a leitura não pintou o rótulo: {leitura['rotulo']!r}")


def test_o_gesto_vivo_nao_veste_o_em_voo(medido: dict) -> None:
    """O cursor `progress` a cada tecla seria a tela mentindo sobre o trabalho.

    O `hef-em-voo` diz *"estou trabalhando"* e existe para um gesto de 9,5 s. Uma
    leitura de milissegundos vestida com ele faria o campo piscar de opacidade a
    cada letra digitada.
    """
    resposta = medido["porta-viva"]
    assert isinstance(resposta, str), resposta
    lido = json.loads(resposta)
    assert lido["em_voo"] is False, "o campo vivo vestiu `hef-em-voo`"
    assert lido["voo"] == "", (
        f"o campo vivo foi carimbado com um número de voo: {lido['voo']!r}")
    vivos = [g for g in medido["gestos"] if g["vivo"]]
    assert vivos, "nenhum gesto chegou ao Python marcado como vivo"
    assert all(g["voo"] == "" for g in vivos), (
        f"um gesto vivo chegou com número de voo: {vivos!r}")


def test_o_gesto_vivo_que_grava_e_recusado_nomeando(medido: dict) -> None:
    """A MORDIDA da peça 2, segunda metade: ligue o vivo ao gesto que grava.

    Quem declara o que muda na máquina dela é o próprio gesto, no decorador
    (`grava=`), e é esse registro que a guarda consulta. **A função nem chega a
    ser chamada** — recusar depois de gravar seria recusar tarde.

    ARRANQUE A GUARDA e o gesto entra na lista de chamados: as duas asserções
    reprovam.
    """
    novos = [c for c in medido["chamados-depois-do-grava"]
             if c not in medido["chamados-depois-do-vivo"]]
    assert "vivo:GRAVOU" not in novos, (
        f"o gesto vivo que DECLARA gravação foi chamado: {novos!r}")
    recusados = medido["vivos_recusados"]
    assert isinstance(recusados, list)
    assert any(VIVO_QUE_GRAVA in r and "save_profile" in r for r in recusados), (
        f"a recusa não nomeou o gesto nem o que ele grava: {recusados!r}")


def test_o_gesto_vivo_nao_troca_bloco(medido: dict) -> None:
    """Uma troca de HTML a cada tecla arrancaria o campo debaixo do dedo dela.

    É o defeito que a `A-TELA-SAMBA-01` mediu em 06/09: `innerHTML =` destrói
    todos os descendentes, e quem estava digitando perde o nó. Aqui o bloco
    pedido é a COLUNA INTEIRA do p1 — o cartão em que o campo mora.
    """
    recusados = medido["vivos_recusados"]
    assert any(VIVO_QUE_TROCA_BLOCO in r and "blocos" in r for r in recusados), (
        f"a recusa do bloco não aparece: {recusados!r}")
    leitura = medido["depois-do-bloco"]
    assert isinstance(leitura, dict), leitura
    assert leitura["rotulo"] is not None, (
        "a coluna do p1 foi trocada pelo bloco do gesto vivo — o campo do "
        "rótulo sumiu com ela")


def test_a_resposta_velha_nao_pinta_por_cima_da_nova(medido: dict) -> None:
    """UM VIVO EM VOO POR ELEMENTO: a tecla nova cancela a leitura anterior.

    Sem a série, a leitura da tecla `1` pode voltar DEPOIS da leitura de `15` e
    pintar o rótulo errado — e ficar assim até a próxima tecla, porque nada mais
    repinta aquele endereço.

    ARRANQUE o descarte (`self._vivos.get(chave) != serial`) e o rótulo termina
    com a resposta VELHA, que chegou por último.
    """
    novos = [c for c in medido["chamados_finais"]
             if c in ("vivo:velha", "vivo:nova")]
    assert novos == ["vivo:velha", "vivo:nova"], (
        f"as duas teclas não chegaram na ordem esperada: {novos!r}")
    leitura = medido["depois-das-duas-teclas"]
    assert isinstance(leitura, dict), leitura
    assert leitura["rotulo"] == ROTULO_NOVO, (
        f"a resposta velha pintou por cima da nova: {leitura['rotulo']!r}")
    assert medido["vivos_descartados"] >= 1, (
        "nenhuma resposta foi descartada — a leitura velha chegou depois da "
        "nova e mesmo assim contou como atendida")


def test_as_tres_portas_de_hoje_nao_mudaram(medido: dict) -> None:
    """A regressão: o `change` continua despachando o `data-hef-gesto`.

    O MESMO elemento carrega os dois atributos. Se a quarta porta tivesse
    roubado o despacho, o gesto que GRAVA deixaria de ser chamado no evento em
    que ele deve ser chamado — e a cura teria trocado um defeito por outro.
    """
    antes = list(medido["chamados-antes-do-change"])
    depois = list(medido["chamados-depois-do-change"])
    novos = depois[len(antes):]
    assert f"clique:{GESTO_DO_CLIQUE}" in novos, (
        f"o `change` deixou de despachar o gesto de `data-hef-gesto`: "
        f"{novos!r} — o que chegou ao Python foi {medido['gestos']!r}, e o "
        f"disparo devolveu {medido['porta-change']!r}")
    assert "vivo:abc" not in novos, (
        f"o `change` despachou o gesto VIVO: {novos!r}")
    # E ELE SEGUIU O CAMINHO DO CLIQUE INTEIRO, não só o despacho. O elemento
    # carrega um `data-vivo` de ruído — um atributo que nenhuma página tem, e
    # que o ouvinte manda ao Python junto com o dataset. Se a marca do vivo não
    # nascesse vazia na carga, este clique cairia no caminho do gesto vivo:
    # sem voo, e com o `recado` RECUSADO por ser chave de aviso. O recado na
    # tela é o que separa os dois caminhos.
    leitura = medido["depois-do-change"]
    assert isinstance(leitura, dict), leitura
    assert [r["texto"] for r in _r(leitura)] == [FRASE_DO_RECADO], (
        f"o `change` não depositou o recado do gesto — ele caiu no caminho do "
        f"gesto vivo por causa de um `data-vivo` no dataset: {_r(leitura)!r}")


# --------------------------------------------------------------------------
# 2b. a corrida do desfecho — dois cliques, uma chave (achado da ONDA5-01-03)
# --------------------------------------------------------------------------
def test_o_botao_que_recusou_nao_pisca_verde_pelo_vizinho(medido: dict) -> None:
    """A piscada é do desfecho DESTA execução, e não do que está na chave.

    A chave de `self.desfechos` é `página:gesto`, e o MESMO gesto pode estar em
    voo duas vezes — o `click` e o `change` de um `<select>`, ou dois cliques em
    colunas diferentes. As duas threads escrevem na mesma chave, e o `finally`
    de cada uma lia dali para decidir a cor do pouso.

    Aqui o p1 demora e RECUSA; o p2 responde na hora e aplica. Quando o p1
    pousa, a chave já diz `"aplicou"` — do vizinho.

    ARRANQUE a cura (volte o `finally` a ler `self.desfechos`) e o botão do p1
    pousa **verde**, dizendo que deu certo o que o produto acabou de recusar.
    """
    lido = medido["a-corrida"]
    assert isinstance(lido, dict), lido
    assert lido["p1"] and lido["p2"], (
        f"a régua não achou os dois botões de microfone: {lido!r} — sem os "
        f"dois não há corrida a medir")
    assert lido["p2"]["deu_certo"], (
        "o botão do p2 (que APLICOU) não piscou verde — a régua está medindo "
        "fora da janela da piscada, e por isso não veria o verde falso do p1")
    assert not lido["p1"]["deu_certo"], (
        "o botão do p1 piscou VERDE depois de o produto ter RECUSADO: o pouso "
        "leu o desfecho que o vizinho escreveu na mesma chave")
    assert not lido["p1"]["em_voo"], (
        "o botão do p1 continua 'trabalhando' — o pouso não chegou, e a "
        "medição acima não vale")
    corridas = [c for c in medido["chamados_finais"] if c.startswith("corrida:")]
    assert sorted(corridas) == ["corrida:p1", "corrida:p2"], (
        f"os dois cliques não chegaram ao mesmo gesto: {corridas!r}")


# --------------------------------------------------------------------------
# 3. o dono do campo — assento não é modelo
# --------------------------------------------------------------------------
def test_o_dono_de_um_campo_dentro_do_desenho_e_o_assento(medido: dict) -> None:
    """A MORDIDA da peça 3, medida no arquivo publicado e não num dublê.

    `treme-e` e `treme-d` da `05-vibracao` moram DENTRO do
    `<svg data-controle="dualsense">`, nas colunas do p1 e do p2. Antes desta
    cura o `LER_CAMPOS` os devolvia com dono `"dualsense"` — o MODELO no lugar
    do assento —, e a régua do mockup não os casava com a coluna que os pinta.

    ARRANQUE a lista de permitidos (volte ao seletor genérico) e os quatro
    voltam a dizer `dualsense`.
    """
    campos = medido["campos-do-svg"]
    assert isinstance(campos, list), campos
    donos = {}
    for chave, dono, _alvo, _v, _visto in campos:
        if chave in SO_OS_QUE_TREMEM:
            donos.setdefault(dono, []).append(chave)
    assert donos, (
        f"os campos {SO_OS_QUE_TREMEM} não apareceram na leitura da "
        f"{PAGINA_DO_SVG} — a régua não mediu o que prometeu medir")
    assert "dualsense" not in donos, (
        f"o dono do campo continua sendo o MODELO: {donos!r}")
    assert set(donos) <= {"p1", "p2", "p3", "p4"}, (
        f"o dono não é um assento: {donos!r}")


def test_o_seletor_do_dono_pergunta_ao_dono() -> None:
    """A segunda régua do dono impossível — os três lados dizem o mesmo.

    O bootstrap e o leitor de campos são strings CRUAS que seis réguas desta
    casa extraem do fonte por expressão regular; nenhuma das duas pode ser
    concatenada nem interpolada, e uma f-string não serve porque o JS é cheio de
    chaves. Então o seletor vive escrito nas três e a igualdade é cobrada aqui —
    a mesma forma de `MS_DA_PISCADA`.

    E ELA PERGUNTA AO DONO: os assentos saem de `pacotes.TODOS_OS_LUGARES`, não
    de uma lista digitada nesta régua. Acrescentar um quinto lugar lá e esquecer
    o piloto reprova aqui.
    """
    import hefesto_vivo as hv

    esperado = hv.SELETOR_DO_DONO
    for lugar in hv.pacotes.TODOS_OS_LUGARES:
        assert f'[data-controle="{lugar}"]' in esperado, (
            f"o assento {lugar!r} não está no seletor do piloto: {esperado!r}")
    assert '[data-controle=""]' in esperado, (
        "o vazio saiu do seletor — ele é o ESCUDO dos chips da fita "
        "(`monta._endereco_do_chip`), e sem ele o 'deu certo' de trocar do P1 "
        "para o P2 volta a pousar no cartão do P1")
    for nome in ("BOOTSTRAP", "LER_CAMPOS", "CLIQUE_COM_ALVO"):
        js = getattr(hv, nome)
        assert esperado in js, (
            f"o {nome} não usa o seletor do dono — ele resolve o dono de outro "
            f"jeito, e um instrumento que resolve diferente do produto mede "
            f"outra coisa")
        # O SELETOR GENÉRICO NÃO PODE SOBRAR EM LUGAR NENHUM: é ele que devolve
        # o MODELO como se fosse assento. Descrever, e não escrever, é a regra
        # que o BOOTSTRAP já paga — por isso ele é montado aqui, não citado.
        generico = "[data-controle],[data-uniq]"
        assert generico not in js, (
            f"o {nome} ainda resolve o dono pelo seletor genérico — o campo de "
            f"dentro do desenho compartilhado volta com o nome do modelo")
