#!/usr/bin/env python3
"""OS RESTOS DA ONDA DOIS — RESTOS-DA-ONDA-DOIS-01, 13/09/2026."""
from __future__ import annotations

import contextlib
import html
import inspect
import io
import json
import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA_02 = "02-controles.html"
PAGINA_06 = "06-navegacao.html"  # (noqa-acento) nome de arquivo
PAGINA_09 = "09-sistema.html"

UNIQ_P1 = "aa:bb:cc:00:00:3a"
UNIQ_P3 = "aa:bb:cc:00:00:c4"
ESTADO_02 = {
    "active_profile": "regua",
    "gamepad_emulation": {"flavor": "dualsense"},
    "controllers": [
        {"uniq": uniq, "connected": True, "transport": via, "player": n,
         "is_primary": n == 1, "battery_pct": 64, "inputs": {},
         "audio": {"mic_mudo": False}, "speaker": {"volume": 60, "muted": False}}
        for n, (uniq, via) in enumerate(
            ((UNIQ_P1, "usb"), ("", "bt"), (UNIQ_P3, "bt")), start=1)],
}

PASSO_MS = 80
TETO_S = 20.0
TETO_DA_PAGINA_S = 40.0
TETO_DO_ROTEIRO_S = 120.0

LER_AS_MOLDURAS = r"""
(function(){
  const efetiva = function(el){
    if(!el) return null;
    let o = 1;
    for(let n = el; n && n.nodeType === 1; n = n.parentElement){
      o *= parseFloat(getComputedStyle(n).opacity || '1');
    }
    return Math.round(o * 100) / 100;
  };
  const cur = function(el){ return el ? getComputedStyle(el).cursor : null; };
  const out = [];
  for(const c of document.querySelectorAll('.ctl')){
    const alto = c.querySelector('.moldura[data-bloco="alto-falante"]');
    if(!alto) continue;
    const bat = c.querySelector('[data-campo="bateria"]');
    out.push({
      controle: c.getAttribute('data-controle'),
      bateria: bat ? (bat.textContent || '').trim() : null,
      alto_apagado: alto.getAttribute('data-apagado'),
      alto_title: alto.getAttribute('title'),
      alto_dica: alto.getAttribute('data-hef-dica'),
      alto_vol: efetiva(alto.querySelector('.vol')),
      alto_rota: efetiva(alto.querySelector('.rota')),
      alto_cursor_deslizante: cur(alto.querySelector('.puxa-vol')),
      alto_cursor_rota: cur(alto.querySelector('.rota button')),
    });
  }
  return JSON.stringify(out);
})()
"""

LER_A_TELA = r"""
(function(frase){
  const em = function(atr){
    return Array.prototype.filter.call(document.querySelectorAll('[' + atr + ']'),
      function(e){ return (e.getAttribute(atr) || '').indexOf(frase) >= 0; }).length;
  };
  const visivel = document.body ? (document.body.innerText || '') : '';
  return JSON.stringify({recados: document.querySelectorAll('.hef-recado').length,
    visivel: visivel.indexOf(frase) >= 0, dica: em('data-hef-dica'), title: em('title')});
})(%s)
"""


@pytest.fixture(scope="module", autouse=True)
def _perfil_ativo_no_disco() -> None:
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    profiles_dir().mkdir(parents=True, exist_ok=True)
    if not (profiles_dir() / "regua.json").exists():
        loader.save_profile(Profile(name="regua", match=MatchManual()),
                            origem="regua")


def _pagina(nome: str, publicado: bool) -> str:
    from hefesto_dualsense4unix.interface import onde

    return onde.pagina(nome, publicado=publicado).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def na_02() -> dict[str, Any]:
    """Abre o piloto DE VERDADE, oculto, na 02, com a mesa dublê de três."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    import argparse
    import time as _time

    import hefesto_vivo as hv
    from hefesto_dualsense4unix.app.widgets.controller_card import (
        TEXTO_AUDIO_SEM_ENDERECO,
    )

    guardado = hv.mesa_viva.estado_do_daemon
    hv.mesa_viva.estado_do_daemon = lambda *a, **k: ESTADO_02  # type: ignore[assignment]
    args = argparse.Namespace(
        oculta=True, segundos=0.0, passear=False, parada=900, foto="",
        abre=PAGINA_02, prova_no_aparelho=False, entre=2500, espera=1200,
        incluir_perigosos=False, prova_clique="", sem_cor=True, sem_ondas=True,
        prova_de_mockup=False, voltas_por_aba=8, teto_de_mockup=-1,
        sem_cravado=False, sem_selo=False, conta_mutacoes=0,
    )
    piloto = hv.Piloto(args)
    fora: dict[str, Any] = {"faltou": {}}
    no_ar = {"sim": True}
    diario = io.StringIO()
    comeco = {"t": 0.0}

    def esperar(marco: str, pergunta: str, achar, depois, o_que: str) -> None:
        """UMA espera por condição: pergunta, e só segue quando `achar` achar."""
        desde = _time.monotonic()

        def perguntar() -> bool:
            if no_ar["sim"]:
                piloto.ponte.perguntar(pergunta, respondeu)
            return False

        def respondeu(valor, erro) -> None:
            if not no_ar["sim"]:
                return
            lido = None
            if erro is None and valor is not None:
                try:
                    lido = json.loads(str(valor))
                except ValueError:
                    lido = None
            achado = None if lido is None else achar(lido)
            if achado is not None:
                fora[marco] = achado
                depois()
            elif _time.monotonic() - desde >= TETO_S:
                fora["faltou"][marco] = (f"{o_que} — não chegou em {TETO_S:.0f} s; a "
                                         f"última leitura foi {lido!r}")[:600]
                depois()
            else:
                GLib.timeout_add(PASSO_MS, perguntar)

        perguntar()

    def pintados(lido: object) -> object:
        if not isinstance(lido, list):
            return None
        return lido if sum(1 for m in lido if m.get("bateria") == "64 %") >= 3 else None

    def fim() -> None:
        fora["fim"] = True
        Gtk.main_quit()

    def ler_a_frase() -> None:
        esperar("tela", LER_A_TELA % json.dumps(TEXTO_AUDIO_SEM_ENDERECO),
                lambda lido: lido, fim, "a leitura da frase de «sem endereço»")

    def um_tique_depois() -> bool:
        esperar("molduras", LER_AS_MOLDURAS, pintados, ler_a_frase,
                "as molduras de som depois de mais um tique")
        return False

    def comecar() -> bool:
        if not piloto.tela.na_aba:
            return True
        if not comeco["t"]:
            comeco["t"] = _time.monotonic()
            piloto._ir(PAGINA_02)
            return True
        if not (piloto.pagina == PAGINA_02 and piloto.pronto):
            if _time.monotonic() - comeco["t"] >= TETO_DA_PAGINA_S:
                fora["faltou"]["abertura"] = f"a {PAGINA_02} não ficou de pé"
                fim()
                return False
            return True
        esperar("pintados", LER_AS_MOLDURAS, pintados,
                lambda: GLib.timeout_add(1200, um_tique_depois),
                "os três cartões pintados pelo tique")
        return False

    GLib.timeout_add(300, comecar)
    guarda = GLib.timeout_add(int(TETO_DO_ROTEIRO_S * 1000), Gtk.main_quit)
    try:
        limite = _time.monotonic() + TETO_DO_ROTEIRO_S
        with contextlib.redirect_stderr(diario):
            while "fim" not in fora and _time.monotonic() < limite:
                Gtk.main()
    finally:
        no_ar["sim"] = False
        with contextlib.suppress(Exception):
            GLib.source_remove(guarda)
        piloto.pronto = False
        piloto.tela.janela.destroy()
        hv.mesa_viva.estado_do_daemon = guardado  # type: ignore[assignment]
    assert "fim" in fora, (
        f"o roteiro não chegou ao fim — voltou {sorted(fora)}, faltou {fora['faltou']}")
    return fora


def _marco(medido: dict[str, Any], marco: str) -> Any:
    falta = medido["faltou"].get(marco)
    assert falta is None, f"o marco `{marco}` não chegou: {falta}"
    assert marco in medido, f"o roteiro não passou por `{marco}`: {sorted(medido)}"
    return medido[marco]


def _cartao(na_02: dict[str, Any], pref: str) -> dict[str, Any]:
    achados = [m for m in _marco(na_02, "molduras") if m.get("controle") == pref]
    assert len(achados) == 1, (pref, na_02["molduras"])
    return achados[0]


def test_a_02_o_alto_falante_sem_endereco_apaga_no_webkit(na_02: dict[str, Any]) -> None:
    """Sem endereço, todo comando de som deste cartão iria para o controle primário."""
    from hefesto_dualsense4unix.interface.pacotes.a02_controles import MIC_SEM_ALVO

    p2 = _cartao(na_02, "p2")
    assert p2["alto_apagado"] == MIC_SEM_ALVO, (
        f"a moldura do alto-falante do controle sem endereço não veste o cinza: {p2}")
    assert p2["alto_vol"] < 1 and p2["alto_rota"] < 1, p2
    assert p2["alto_cursor_deslizante"] == "not-allowed", p2
    assert p2["alto_cursor_rota"] == "not-allowed", p2
    assert p2["alto_title"] is None and p2["alto_dica"] is None, (
        f"a moldura do alto-falante carrega uma frase: {p2}")


@pytest.mark.parametrize("pref", ["p1", "p3"])
def test_a_02_os_cartoes_com_endereco_ficam_acesos(na_02: dict[str, Any], pref: str) -> None:
    """A metade contrária: a guarda é POR CARTÃO, e apagar o vizinho seria pior."""
    cartao = _cartao(na_02, pref)
    assert cartao["alto_apagado"] is None, cartao
    assert cartao["alto_vol"] == 1 and cartao["alto_rota"] == 1, cartao
    assert cartao["alto_cursor_deslizante"] == "pointer", cartao


def test_a_02_a_frase_sem_endereco_nao_chega_a_tela(na_02: dict[str, Any]) -> None:
    """A frase de aviso não chega à tela em forma nenhuma — nem como dica."""
    assert _marco(na_02, "tela") == {"recados": 0, "visivel": False, "dica": 0,
                                     "title": 0}


def _seletores_de_som(doc: str) -> list[str]:
    estilo = "".join(re.findall(r"<style[^>]*>(.*?)</style>", doc, flags=re.S))
    estilo = re.sub(r"/\*.*?\*/", "", estilo, flags=re.S)
    return [" ".join(seletor.split())
            for bloco, _declaracao in re.findall(r"([^{}]*)\{([^{}]*)\}", estilo)
            for seletor in bloco.split(",")
            if 'data-bloco="alto-falante"' in seletor]


@pytest.mark.parametrize("publicado", [False, True], ids=["bancada", "publicado"])
def test_a_02_a_moldura_do_alto_falante_tem_endereco_proprio(publicado: bool) -> None:
    """A folha casa o `data-apagado`, e a moldura o recebe pelo alvo `atributo`."""
    doc = _pagina(PAGINA_02, publicado)
    seletores = _seletores_de_som(doc)
    assert seletores, "a folha perdeu a guarda do alto-falante"
    assert [s for s in seletores if "[title]" in s] == [], seletores
    assert all('[data-apagado="sem-alvo"]' in s for s in seletores), seletores
    molduras = re.findall(r'<div class="moldura"[^>]*data-bloco="alto-falante"[^>]*>', doc)
    assert molduras, "o desenho perdeu a moldura do alto-falante"
    for tag in molduras:
        assert 'data-campo="alto-apagado"' in tag, tag
        assert 'data-hef-atributo="data-apagado"' in tag, tag


def _tela(doc: str, ident: str) -> str:
    return doc.split(f'id="{ident}"', 1)[-1].split('class="tela-nova"', 1)[0]


@pytest.mark.parametrize("publicado", [False, True], ids=["bancada", "publicado"])
def test_a_06_a_marca_sai_da_troca_e_fica_nas_definicoes(publicado: bool) -> None:
    """MORDIDA: devolva a marca às linhas da troca — o gerador para, e o publicado"""
    doc = _pagina(PAGINA_06, publicado)
    for ident, com_marca in (("remapeamento", False), ("definicoes-mouse", True)):
        celulas = [c for c in re.findall(r'<td class="b">(.*?)</td>', _tela(doc, ident), re.S)
                   if 'class="nm">Touchpad<' in c]
        assert len(celulas) == 3, (ident, len(celulas))
        marcadas = ["marca-nao-dispara" in c for c in celulas]
        assert marcadas == [com_marca] * 3, (ident, marcadas)


def test_a_07_a_assinatura_do_status_nao_pede_o_efetiva() -> None:
    """O valor sem leitor saiu da assinatura, e o nome antigo da leitura saiu junto."""
    from hefesto_dualsense4unix.app.actions import emulation_actions as ea

    assert list(inspect.signature(ea.markup_status_steam_input).parameters) == [
        "on", "jogos", "excecoes"]
    assert not hasattr(ea.EmulationActionsMixin, "_steam_input_excecao_status")


DIGITO = re.compile(r"\d")


@pytest.mark.parametrize("publicado", [False, True], ids=["bancada", "publicado"])
def test_a_09_o_title_do_parar_nao_crava_numero(publicado: bool) -> None:
    """MORDIDA: devolva o `{N}` ao `title` do Parar em `aba09.py` e publique."""
    tags = [t for t in re.findall(r"<button\b[^>]*>", _pagina(PAGINA_09, publicado))
            if 'data-gesto="parar-ou-retomar"' in t]
    assert len(tags) == 1, tags
    dica = re.search(r'title="([^"]*)"', tags[0])
    assert dica, tags[0]
    texto = html.unescape(dica.group(1))
    assert not DIGITO.search(texto), f"o `title` do Parar crava um número: {texto!r}"
    assert "os controles" in texto, texto


def test_a_09_a_pergunta_do_parar_nao_crava_numero() -> None:
    """A pergunta do clique 1 é o `title` publicado: um número ali é a tela errando."""
    from pacotes import a09_sistema as a09

    a09._DICAS.clear()
    try:
        pergunta = a09._pergunta_do_botao(a09.DESLIGAR)
    finally:
        a09._DICAS.clear()
    assert a09.CLIQUE_DE_NOVO in pergunta, pergunta
    assert "os controles" in pergunta, pergunta
    assert not DIGITO.search(pergunta), f"a pergunta do Parar crava um número: {pergunta!r}"
