#!/usr/bin/env python3
"""AS TRÊS PEÇAS DE INFRA DO PILOTO — ONDA5-P-01, 06/09/2026."""
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

PAGINA = "02-controles.html"

PAGINA_DO_SVG = "05-vibracao.html"

GESTO_DO_CLIQUE = "mudo"

VIVO = "regua-vivo"
VIVO_QUE_GRAVA = "regua-vivo-que-grava"
VIVO_QUE_TROCA_BLOCO = "regua-vivo-com-bloco"

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

VIVO_LENTO_S = 0.9

ROTULO_VELHO = "o rótulo da tecla velha"
ROTULO_NOVO = "o rótulo da tecla nova"

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

CLICAR_NO_MIC = r"""
(function(){
  const b = document.querySelector('[data-controle="p1"] [data-mudo="alto-falante"]');
  if(!b) return 'NAO ACHEI O BOTAO DO MICROFONE NO CARTAO DO P1';
  b.click();
  return 'cliquei';
})()
"""

CLICAR_NO_MIC_DE = r"""
(function(pref){
  const b = document.querySelector('[data-controle="' + pref + '"] [data-mudo="alto-falante"]');
  if(!b) return 'NAO ACHEI O BOTAO DO MICROFONE EM ' + pref;
  b.click();
  return 'cliquei em ' + pref;
})(%s)
"""

LER_OS_DOIS_BOTOES = r"""
(function(){
  const fora = {};
  for(const pref of ['p1', 'p2']){
    const b = document.querySelector('[data-controle="' + pref + '"] [data-mudo="alto-falante"]');
    fora[pref] = b ? {deu_certo: b.classList.contains('hef-deu-certo'),
                      recusou: b.classList.contains('hef-recusou'),
                      em_voo: b.classList.contains('hef-em-voo')} : null;
  }
  return JSON.stringify(fora);
})()
"""

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

SO_OS_QUE_TREMEM = ("treme-e", "treme-d")


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

    chaves = [(PAGINA, GESTO_DO_CLIQUE), (PAGINA, VIVO),
              (PAGINA, VIVO_QUE_GRAVA), (PAGINA, VIVO_QUE_TROCA_BLOCO)]
    guardado_gestos = {k: hv.pacotes.GESTOS.get(k) for k in chaves}
    guardado_mexem = {k: hv.pacotes.GESTOS_QUE_MEXEM.get(k) for k in chaves}
    guardado_estado = hv.mesa_viva.estado_do_daemon

    MESA["estado"] = ESTADO
    hv.mesa_viva.estado_do_daemon = lambda *a, **k: MESA["estado"]  # type: ignore[assignment]

    def clique_que_diz(ctx, o, p):
        chamados.append(f"clique:{GESTO_DO_CLIQUE}")
        raise RuntimeError(FRASE_DO_RECADO)

    def vivo_que_le(ctx, o, p):
        """A leitura: devolve carga de pintura, e nada mais."""
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
        """Troca quem atende o 🎙 — pelo REGISTRO do produto, não por atalho."""
        hv.pacotes.GESTOS[(PAGINA, GESTO_DO_CLIQUE)] = fn

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

    def a_porta_muda() -> bool:
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
        fora["chamados-antes-do-change"] = list(chamados)
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

    def a_corrida_do_desfecho() -> bool:
        """DUAS THREADS, UMA CHAVE — e a corrida é FORJADA, não esperada."""
        import threading as _th

        recusou = _th.Event()
        aplicou = _th.Event()

        class DicionarioQueEntrelacaAsDuas(dict):
            def __setitem__(self, chave, valor):
                super().__setitem__(chave, valor)
                if valor and valor[0] == "aplicou":
                    aplicou.set()
                elif valor and valor[0] == "recusou dizendo":
                    recusou.set()
                    aplicou.wait(timeout=5.0)

        piloto.desfechos = DicionarioQueEntrelacaAsDuas(piloto.desfechos)

        def por_controle(ctx, o, p):
            qual = str(o.get("controle") or "")
            chamados.append(f"corrida:{qual}")
            if qual == "p1":
                raise RuntimeError("o daemon não confirmou o mudo do microfone")
            recusou.wait(timeout=5.0)
            return None

        por_gesto(por_controle)
        piloto.ponte.perguntar(CLICAR_NO_MIC_DE % js("p1"), anotar("corrida-p1"))
        GLib.timeout_add(150, a_corrida_do_p2)
        return False

    def a_corrida_do_p2() -> bool:
        piloto.ponte.perguntar(CLICAR_NO_MIC_DE % js("p2"), anotar("corrida-p2"))
        GLib.timeout_add(700, leu_a_corrida)
        return False

    def leu_a_corrida() -> bool:
        piloto.ponte.perguntar(LER_OS_DOIS_BOTOES, ler("a-corrida"))
        GLib.timeout_add(300, ir_para_o_svg)
        return False

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
             "controle": g.get("controle", ""), "campo": g.get("campo", "")}
            for g in piloto.gestos]
        fora["chamados_finais"] = list(chamados)
        Gtk.main_quit()
        return False

    GLib.timeout_add(400, lambda: piloto._ir(args.abre))
    GLib.timeout_add(2000, sem_faixa)
    guarda = GLib.timeout_add(90000, Gtk.main_quit)
    try:
        limite = _time.monotonic() + 90.0
        while "chamados_finais" not in fora and _time.monotonic() < limite:
            Gtk.main()
    finally:
        GLib.source_remove(guarda)
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


def test_sem_o_atributo_nenhum_recado_no_cartao(medido: dict) -> None:
    """ERA `test_sem_o_atributo_o_recado_continua_no_cartao` — 13/09/2026."""
    assert medido["clique-1"] == "cliquei", (
        f"o clique no 🎙 do p1 não aconteceu — a régua passaria sobre nada: "
        f"{medido['clique-1']!r}")
    recados = _r(medido["sem-faixa"])
    assert recados == [], recados
    assert FRASE_DO_RECADO not in json.dumps(medido["sem-faixa"]), (
        "a frase da recusa chegou à leitura da tela por outro caminho")


def test_com_uma_faixa_nenhum_recado_pousa_nela(medido: dict) -> None:
    """ERA `test_com_uma_faixa_o_recado_pousa_nela` — 13/09/2026."""
    assert medido["faixas-1"] == "1", (
        f"a régua não conseguiu declarar UMA faixa: {medido['faixas-1']!r}")
    assert _r(medido["com-uma-faixa"]) == [], medido["com-uma-faixa"]


def test_com_dois_lugares_nenhum_recado_e_nada_a_recusar(medido: dict) -> None:
    """ERA `test_dois_lugares_iguais_a_pagina_perde_os_dois` — 13/09/2026."""
    assert medido["faixas-2"] == "2", (
        f"a régua não conseguiu declarar DUAS faixas: {medido['faixas-2']!r}")
    leitura = medido["com-duas-faixas"]
    assert isinstance(leitura, dict), leitura
    assert leitura["faixas_demais"] == {}, (
        f"o piloto ainda escolhe faixa de recado: {leitura['faixas_demais']!r}")
    assert _r(leitura) == [], leitura["recados"]


def test_sem_o_atributo_o_input_nao_faz_nada(medido: dict) -> None:
    """A MORDIDA da peça 2, primeira metade: o `input` nasce mudo sem endereço."""
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
    """O cursor `progress` a cada tecla seria a tela mentindo sobre o trabalho."""
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
    """A MORDIDA da peça 2, segunda metade: ligue o vivo ao gesto que grava."""
    novos = [c for c in medido["chamados-depois-do-grava"]
             if c not in medido["chamados-depois-do-vivo"]]
    assert "vivo:GRAVOU" not in novos, (
        f"o gesto vivo que DECLARA gravação foi chamado: {novos!r}")
    recusados = medido["vivos_recusados"]
    assert isinstance(recusados, list)
    assert any(VIVO_QUE_GRAVA in r and "save_profile" in r for r in recusados), (
        f"a recusa não nomeou o gesto nem o que ele grava: {recusados!r}")


def test_o_gesto_vivo_nao_troca_bloco(medido: dict) -> None:
    """Uma troca de HTML a cada tecla arrancaria o campo debaixo do dedo dela."""
    recusados = medido["vivos_recusados"]
    assert any(VIVO_QUE_TROCA_BLOCO in r and "blocos" in r for r in recusados), (
        f"a recusa do bloco não aparece: {recusados!r}")
    leitura = medido["depois-do-bloco"]
    assert isinstance(leitura, dict), leitura
    assert leitura["rotulo"] is not None, (
        "a coluna do p1 foi trocada pelo bloco do gesto vivo — o campo do "
        "rótulo sumiu com ela")


def test_a_resposta_velha_nao_pinta_por_cima_da_nova(medido: dict) -> None:
    """UM VIVO EM VOO POR ELEMENTO: a tecla nova cancela a leitura anterior."""
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
    """A regressão: o `change` continua despachando o `data-hef-gesto`."""
    antes = list(medido["chamados-antes-do-change"])
    depois = list(medido["chamados-depois-do-change"])
    novos = depois[len(antes):]
    assert f"clique:{GESTO_DO_CLIQUE}" in novos, (
        f"o `change` deixou de despachar o gesto de `data-hef-gesto`: "
        f"{novos!r} — o que chegou ao Python foi {medido['gestos']!r}, e o "
        f"disparo devolveu {medido['porta-change']!r}")
    assert "vivo:abc" not in novos, (
        f"o `change` despachou o gesto VIVO: {novos!r}")
    do_change = [g for g in medido["gestos"]
                 if g["gesto"] == GESTO_DO_CLIQUE and g["campo"] == "regua-jogo"]
    assert do_change, (
        f"o `change` do campo não chegou ao Python: {medido['gestos']!r}")
    assert all(g["vivo"] == "" and g["voo"] for g in do_change), (
        f"o `change` caiu no caminho do gesto vivo por causa de um `data-vivo` "
        f"no dataset — ele chegou sem voo: {do_change!r}")


def test_o_botao_que_recusou_nao_pisca_verde_pelo_vizinho(medido: dict) -> None:
    """A piscada é do desfecho DESTA execução, e não do que está na chave."""
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
    assert lido["p1"]["recusou"] and not lido["p2"]["recusou"], (
        f"a piscada de recusa não é a do desfecho de cada botão: {lido!r}")
    assert not lido["p1"]["em_voo"], (
        "o botão do p1 continua 'trabalhando' — o pouso não chegou, e a "
        "medição acima não vale")
    corridas = [c for c in medido["chamados_finais"] if c.startswith("corrida:")]
    assert sorted(corridas) == ["corrida:p1", "corrida:p2"], (
        f"os dois cliques não chegaram ao mesmo gesto: {corridas!r}")


def test_o_dono_de_um_campo_dentro_do_desenho_e_o_assento(medido: dict) -> None:
    """A MORDIDA da peça 3, medida no arquivo publicado e não num dublê."""
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
    """A segunda régua do dono impossível — os três lados dizem o mesmo."""
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
        generico = "[data-controle],[data-uniq]"
        assert generico not in js, (
            f"o {nome} ainda resolve o dono pelo seletor genérico — o campo de "
            f"dentro do desenho compartilhado volta com o nome do modelo")
