"""O «← Voltar» do mapa do controle volta para a aba de onde ela veio."""
from __future__ import annotations

import importlib.util
import json
import pathlib
import re
import sys

import pytest

from hefesto_dualsense4unix.interface import onde

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MAPA = "mapa-do-controle.html"
LINK = f'href="{MAPA}"'


def _declaradas() -> set[str]:
    """As páginas em trabalho na bancada, perguntado ao portão `desenho-aprovado`."""
    alvo = RAIZ / "scripts/check_o_desenho_aprovado.py"
    spec = importlib.util.spec_from_file_location("check_desenho_do_voltar", alvo)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_desenho_do_voltar"] = mod
    spec.loader.exec_module(mod)
    return set(mod.declaradas())


PASTA = onde.BANCADA if MAPA in _declaradas() else onde.PUBLICADO


def _origens() -> list[str]:
    return sorted(
        p.name for p in PASTA.glob("*.html")
        if p.name != MAPA and not p.name.endswith(".dc.html")
        and LINK in p.read_text(encoding="utf-8")
    )


def _fora_da_reserva() -> str:
    """Uma aba que não é a reserva nem o mapa, a primeira por nome, do disco."""
    return next(p.name for p in sorted(PASTA.glob("*.html"))
                if p.name not in (MAPA, _reserva()) and not p.name.endswith(".dc.html"))


def _reserva() -> str:
    """O `href` do «← Voltar», lido do mapa no disco."""
    achado = re.search(r'<a class="voltar" href="([^"]+)"',
                       (PASTA / MAPA).read_text(encoding="utf-8"))
    assert achado, f"o {MAPA} ({PASTA.name}) não tem o «← Voltar»"
    return achado.group(1)


CLICAR_O_LINK = (
    "(function(){var a=document.querySelector('a[href=\"ALVO\"]');"
    "if(!a){return 'sem link';} a.click(); return 'clicou';})()").replace("ALVO", MAPA)
IR_AO_MAPA = f"(function(){{location.href='{MAPA}'; return 'clicou';}})()"
CLICAR_O_VOLTAR = (
    "(function(){var a=document.querySelector('a.voltar');"
    "if(!a){return 'sem voltar';} a.click(); return 'clicou';})()")


@pytest.fixture(scope="module")
def viagens() -> dict[str, dict]:
    """Cada viagem num WebView novo (histórico limpo): origem → mapa → «Voltar»."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre (rode com xvfb-run -a)")

    casos = ([(o, "link") for o in _origens()] + [(MAPA, "direto")]
             + [(_fora_da_reserva(), "endereco")])
    fora: dict[str, dict] = {}
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(1600, 900)
    vez = {"i": -1, "view": None, "fase": "", "modo": "", "reg": {}}

    def proximo() -> bool:
        vez["i"] += 1
        if vez["i"] >= len(casos):
            Gtk.main_quit()
            return False
        origem, modo = casos[vez["i"]]
        if vez["view"] is not None:
            janela.remove(vez["view"])
        view = WebKit2.WebView()
        view.connect("load-changed", carregou)
        janela.add(view)
        janela.show_all()
        vez.update(view=view, fase="mapa" if modo == "direto" else "origem",
                   modo=modo, reg={"cargas": []})
        fora[{"direto": "(direto)", "endereco": "(endereço)"}.get(modo, origem)] = vez["reg"]
        view.load_uri((PASTA / origem).as_uri())
        return False

    def rodar(js: str, chave: str) -> None:
        def fim(v, res) -> None:
            try:
                vez["reg"][chave] = v.evaluate_javascript_finish(res).to_string()
            except Exception as erro:
                vez["reg"][chave] = f"ERRO {erro}"
        vez["view"].evaluate_javascript(js, -1, None, None, None, fim)

    def terminou() -> bool:
        vez["reg"]["terminou_em"] = (vez["view"].get_uri() or "").rsplit("/", 1)[-1]
        GLib.idle_add(proximo)
        return False

    def carregou(view, evento) -> None:
        if evento != WebKit2.LoadEvent.FINISHED or view is not vez["view"]:
            return
        vez["reg"]["cargas"].append((view.get_uri() or "").rsplit("/", 1)[-1])
        if vez["fase"] == "origem":
            vez["fase"] = "mapa"
            ida = IR_AO_MAPA if vez["modo"] == "endereco" else CLICAR_O_LINK
            GLib.timeout_add(200, lambda: (rodar(ida, "link"), False)[1])
        elif vez["fase"] == "mapa":
            vez["fase"] = "voltou"
            GLib.timeout_add(200, lambda: (rodar(CLICAR_O_VOLTAR, "voltar"), False)[1])
            GLib.timeout_add(1500, terminou)

    GLib.idle_add(proximo)
    guarda = GLib.timeout_add(20000 + 4000 * len(casos), Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    return fora


def test_ha_pagina_que_leva_ao_mapa() -> None:
    """Sem origem nenhuma a régua de baixo seria verde por vacuidade."""
    assert _origens(), f"nenhuma página em {PASTA} tem {LINK}"


def test_o_voltar_volta_para_a_aba_que_abriu_o_mapa(viagens) -> None:
    for origem in _origens():
        reg = viagens.get(origem, {})
        assert reg.get("link") == "clicou" and reg.get("voltar") == "clicou", (
            f"a viagem a partir de {origem} não completou: "
            f"{json.dumps(reg, ensure_ascii=False)}")
        assert reg.get("terminou_em") == origem, (
            f"aberto pela {origem} ({PASTA.name}), o «← Voltar» do mapa levou a "
            f"{reg.get('terminou_em')!r} — cargas {reg.get('cargas')}")


def test_o_mapa_aberto_direto_vai_para_a_reserva(viagens) -> None:
    reg = viagens.get("(direto)", {})
    assert reg.get("voltar") == "clicou", json.dumps(reg, ensure_ascii=False)
    assert reg.get("terminou_em") == _reserva(), (
        f"o mapa aberto direto foi a {reg.get('terminou_em')!r}, e a reserva "
        f"que o «← Voltar» declara é {_reserva()!r}")


def test_o_voltar_volta_para_uma_aba_que_nao_e_a_reserva(viagens) -> None:
    """A origem que distingue a lista de volta da reserva: sem ela, a régua de"""
    origem = _fora_da_reserva()
    reg = viagens.get("(endereço)", {})
    assert reg.get("link") == "clicou" and reg.get("voltar") == "clicou", (
        json.dumps(reg, ensure_ascii=False))
    assert reg.get("cargas", [])[1:2] == [MAPA], f"a ida ao mapa não aconteceu: {reg}"
    assert reg.get("terminou_em") == origem, (
        f"aberto a partir da {origem}, o «← Voltar» levou a {reg.get('terminou_em')!r} "
        f"(a reserva é {_reserva()!r}) — cargas {reg.get('cargas')}")
