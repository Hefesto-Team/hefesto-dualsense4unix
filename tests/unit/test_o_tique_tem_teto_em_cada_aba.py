"""O TIQUE TEM TETO EM CADA ABA — O-APP-RESPONDE-NA-HORA-01, réguas 8 e 9.

A janela parada na aba Perfis gastava de 38 a 41% de um núcleo no lar de mentira
(e 46% na máquina dela), porque cada tique perguntava ao catálogo de jogos por
linha. As nove outras abas custavam de 0,6 a 4,5 ms por tique.

    R8  o tique de cada uma das dez abas tem teto (a CPU do fio do GTK)
    R9  a abertura pede a página antes de importar as abas

A janela é OCULTA e nasce no Xvfb da suíte; sem display, as duas pulam (o
conferente as roda dentro de `dbus-run-session -- xvfb-run -a`). A R8 é o
piloto de verdade, no processo da suíte, com os dublês da R1 da janela aberta
(`test_a_janela_aberta_nao_gasta_o_processador`): o estado da fixture de quatro
controles, a ponte e os `pactl` de mentira, e a casa da régua 1 de
`test_o_app_responde_na_hora`. A R9 roda o piloto como o produto o abre
(`__main__`, por `runpy`), num subprocesso com lar de mentira e guarda que sai.
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.unit.test_a_janela_aberta_nao_gasta_o_processador import (
    _args,
    _Estado,
    _gtk,
    _PonteDeMentira,
)
from tests.unit.test_o_app_responde_na_hora import casa  # noqa: F401 (a casa da régua 1)

RAIZ = Path(__file__).resolve().parents[2]

ABAS = ("01-jogar.html", "02-controles.html", "03-gatilhos.html", "04-iluminacao.html",
        "05-vibracao.html", "06-navegacao.html", "07-lancadores.html",
        "08-conexoes.html", "09-sistema.html", "10-perfis.html")

#: Os tiques medidos por aba, depois de `ASSENTAR` tiques de folga na chegada.
TIQUES = 40
ASSENTAR = 3
#: O teto, em CPU do fio do GTK por tique. Medido em 02/10 no lar de mentira: a
#: mais cara das nove sadias é a 08 (mediana 4,4 ms); a 10 era 37 ms antes da
#: foto do catálogo e 6,5 ms depois.
TETO_DA_MEDIANA_MS = 15.0
TETO_DO_P95_MS = 40.0
#: Quanto uma aba pode levar para juntar os tiques (40 a 100 ms, cinco vezes).
TETO_DA_ABA_S = 20.0


# ===========================================================================
# R8 — o tique de cada uma das dez abas tem teto
# ===========================================================================
def _medir_as_dez(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[float]]:
    """O piloto oculto passa pelas dez abas e anota a CPU de cada tique."""
    gtk = _gtk()
    from gi.repository import GLib

    from hefesto_dualsense4unix.app import audio_saida
    from hefesto_dualsense4unix.integrations import eleicao_de_microfone as el
    from hefesto_dualsense4unix.integrations import ondas_de_som
    from hefesto_dualsense4unix.interface import hefesto_vivo as hv

    estado = _Estado(4)
    monkeypatch.setattr(hv.mesa_viva, "estado_do_daemon", estado)
    monkeypatch.setattr(hv, "ponte", _PonteDeMentira())
    monkeypatch.setattr(audio_saida, "rodar_leitura", lambda _argv: "")
    monkeypatch.setattr(el, "_rodar", lambda _argv: (1, ""))
    monkeypatch.setattr(ondas_de_som, "_LIGADO", [False])

    custos: dict[str, list[float]] = {aba: [] for aba in ABAS}
    roteiro = SimpleNamespace(i=0, chegou=0, desde=time.monotonic(), acabou=False,
                              famintas=[])
    with hv._o_processo_da_janela():
        piloto = hv.Piloto(_args(sem_ondas=True))
        tique_original = piloto._tique

        def tique() -> bool:
            if roteiro.acabou:
                return False
            t0 = time.thread_time()
            volta = tique_original()
            custo = (time.thread_time() - t0) * 1000
            aba = ABAS[roteiro.i] if roteiro.i < len(ABAS) else ""
            if aba and piloto.pagina == aba and piloto.pronto and piloto.tela.na_aba:
                roteiro.chegou += 1
                if roteiro.chegou > ASSENTAR:
                    custos[aba].append(custo)
            return volta

        piloto._tique = tique  # type: ignore[method-assign]

        def passo() -> bool:
            if roteiro.i >= len(ABAS):
                gtk.main_quit()
                return False
            aba = ABAS[roteiro.i]
            # NAVEGAR ANTES DE A PÁGINA CONFIRMAR mata a janela (`_ir` com o
            # título vazio): a vez de trocar é a da página de pé.
            de_pe = piloto.pronto and piloto.tela.na_aba
            if not de_pe and time.monotonic() - roteiro.desde <= TETO_DA_ABA_S:
                return True
            if len(custos[aba]) >= TIQUES or time.monotonic() - roteiro.desde > TETO_DA_ABA_S:
                if len(custos[aba]) < TIQUES:
                    roteiro.famintas.append((aba, len(custos[aba])))
                roteiro.i += 1
                roteiro.chegou = 0
                roteiro.desde = time.monotonic()
                return True
            if piloto.pagina != aba:
                piloto._ir(aba)
            return True

        guarda = GLib.timeout_add(int((TETO_DA_ABA_S * len(ABAS) + 30) * 1000), gtk.main_quit)
        GLib.timeout_add(50, passo)
        try:
            gtk.main()
        finally:
            roteiro.acabou = True
            piloto.pronto = False
            GLib.source_remove(guarda)
            piloto._estado_vivo.parar()
            piloto.tela.janela.destroy()
            ondas_de_som.o_de_sempre().seguir({})
    assert not roteiro.famintas, (
        f"abas que não juntaram {TIQUES} tiques em {TETO_DA_ABA_S:.0f} s: "
        f"{roteiro.famintas} (a página não ficou de pé, ou o laço andou devagar)")
    return custos


def _p95(valores: list[float]) -> float:
    ordenados = sorted(valores)
    return ordenados[min(len(ordenados) - 1, round(0.95 * (len(ordenados) - 1)))]


def test_o_tique_de_cada_aba_tem_teto(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """Dez abas, 40 tiques cada, a CPU do fio do GTK em cada tique: mediana até
    15 ms e p95 até 40 ms em toda aba, com a casa da régua 1 (33 jogos da
    Steam, 30 perfis, 200 atalhos).

    MORDIDA: devolva o catálogo por linha (a 10 sem a foto do tique) — a 10
    reprova pela mediana, e só ela.
    """
    custos = _medir_as_dez(monkeypatch)
    acima = {}
    for aba, valores in custos.items():
        mediana, p95 = statistics.median(valores), _p95(valores)
        if mediana > TETO_DA_MEDIANA_MS or p95 > TETO_DO_P95_MS:
            acima[aba] = f"mediana {mediana:.1f} ms · p95 {p95:.1f} ms"
    assert not acima, (
        f"o tique passou do teto (mediana {TETO_DA_MEDIANA_MS:.0f} ms, p95 "
        f"{TETO_DO_P95_MS:.0f} ms de CPU do fio do GTK): {acima}")


# ===========================================================================
# R9 — a abertura pede a página antes de importar as abas
# ===========================================================================
_PELO_PRODUTO = r'''
import json, os, pathlib, runpy, sys
LAR = pathlib.Path(os.environ["LAR_DA_REGUA"]).resolve()
if not str(pathlib.Path.home().resolve()).startswith(str(LAR)):
    sys.exit("GUARDA: o HOME não é o de mentira")
from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira
garantir_tela_de_mentira()
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk, WebKit2

ABA_10 = "hefesto_dualsense4unix.interface.pacotes.a10_perfis"
EV = {}
_load_uri = WebKit2.WebView.load_uri


def load_uri(self, uri):
    if "a10_no_pedido" not in EV:
        EV["a10_no_pedido"] = ABA_10 in sys.modules
        EV["aba"] = uri.rsplit("/", 1)[-1]
    return _load_uri(self, uri)


def conferir():
    if ABA_10 in sys.modules and "a10_no_pedido" in EV:
        Gtk.main_quit()
        return False
    return True


WebKit2.WebView.load_uri = load_uri
GLib.timeout_add(50, conferir)
GLib.timeout_add(30000, Gtk.main_quit)
sys.argv = [sys.argv[1], "--oculta", "--sem-cor", "--sem-ondas"]
try:
    runpy.run_path(sys.argv[0], run_name="__main__")
except SystemExit:
    pass
EV["a10_depois"] = ABA_10 in sys.modules
pathlib.Path(os.environ["SAIDA_DA_REGUA"]).write_text(json.dumps(EV))
'''


def test_a_abertura_pede_a_pagina_antes_de_importar_as_abas(tmp_path: Path) -> None:
    """O piloto aberto como o produto (`__main__`): quando a janela pede a 01
    (`load_uri`), o pacote da aba 10 ainda não está no `sys.modules`; e ele
    chega depois, na mesma abertura.

    MORDIDA: devolva o import das abas ao topo de `hefesto_vivo` (o `if
    __name__ != "__main__":` sem a condição) — o módulo já está lá no pedido.
    """
    _gtk()
    lar = tmp_path / "lar"
    for sub in (".config", ".local/share", ".local/state", ".cache", "run", "bin"):
        (lar / sub).mkdir(parents=True)
    (lar / "run").chmod(0o700)
    pactl = lar / "bin/pactl"
    pactl.write_text("#!/bin/sh\nexit 1\n")
    pactl.chmod(0o755)
    roteiro = tmp_path / "pelo_produto.py"
    roteiro.write_text(_PELO_PRODUTO, encoding="utf-8")
    saida = tmp_path / "saida.json"
    ambiente = {k: v for k, v in os.environ.items()
                if k not in ("WAYLAND_DISPLAY", "PULSE_SERVER", "PIPEWIRE_REMOTE")}
    ambiente.update(
        LAR_DA_REGUA=str(lar), SAIDA_DA_REGUA=str(saida), HOME=str(lar),
        XDG_CONFIG_HOME=str(lar / ".config"), XDG_DATA_HOME=str(lar / ".local/share"),
        XDG_STATE_HOME=str(lar / ".local/state"), XDG_CACHE_HOME=str(lar / ".cache"),
        XDG_RUNTIME_DIR=str(lar / "run"), PATH=f"{lar / 'bin'}:{os.environ.get('PATH', '')}",
        DBUS_SESSION_BUS_ADDRESS=f"unix:path={lar / 'run/sem-barramento'}",
        DBUS_SYSTEM_BUS_ADDRESS=f"unix:path={lar / 'run/sem-barramento-de-sistema'}",
        PYTHONPATH=str(RAIZ / "src"), GDK_BACKEND="x11")
    piloto = RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"
    r = subprocess.run([sys.executable, str(roteiro), str(piloto)], capture_output=True,
                       text=True, timeout=90, env=ambiente, cwd=str(RAIZ))
    assert saida.exists(), f"o piloto não abriu (rc={r.returncode}):\n{r.stderr[-2000:]}"
    medida = json.loads(saida.read_text())
    assert medida.get("aba") == "01-jogar.html", medida
    assert medida["a10_no_pedido"] is False, (
        "a janela pediu a página com as dez abas já importadas: a abertura "
        "esperou o import antes de mostrar qualquer coisa")
    assert medida["a10_depois"] is True, (
        "as abas nunca chegaram depois do pedido da página")


# ===========================================================================
# R9b — quem fecha a janela durante a espera da abertura, fecha o processo
# ===========================================================================
def _vista_de_mentira() -> object:
    """Um objeto com o sinal `load-changed` da `WebKit2.WebView`, e nada mais."""
    from typing import Any, ClassVar

    from gi.repository import GObject

    class _Vista(GObject.Object):
        __gsignals__: ClassVar[dict[str, tuple[Any, ...]]] = {
            "load-changed": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
        }

    return _Vista()


def _o_laco_que_vem_s(gtk: object, teto_s: float) -> float:
    """Quanto um `Gtk.main` dura depois da espera, com uma guarda de `teto_s`."""
    from gi.repository import GLib

    guarda_no_ar = [True]

    def guarda() -> bool:
        guarda_no_ar[0] = False
        gtk.main_quit()  # type: ignore[attr-defined]
        return False

    fonte = GLib.timeout_add(int(teto_s * 1000), guarda)
    t0 = time.monotonic()
    gtk.main()  # type: ignore[attr-defined]
    dura = time.monotonic() - t0
    if guarda_no_ar[0]:
        GLib.source_remove(fonte)
    return dura


def test_quem_fecha_a_janela_durante_a_espera_fecha_o_processo() -> None:
    """A janela do produto aparece antes de as abas chegarem, e a abertura
    espera o WebKit começar (`_esperar_o_webkit_comecar`). O «X» da janela (e
    a carga que falha) chama `Gtk.main_quit` nesse meio-tempo: a espera acaba
    na hora, e o `Gtk.main` que vem depois sai sozinho, como saía antes de a
    espera existir. Sem pedido de sair, a espera acaba no `committed` e o laço
    seguinte segue de pé.

    MORDIDA: volte a espera às voltas à mão do laço (`Gtk.main_iteration_do`),
    como ela nasceu — o `Gtk.main_quit` sem laço rodando se perde, a espera vai
    até o teto e o laço que vem não sai mais: o processo pendura sem janela.
    """
    gtk = _gtk()
    from gi.repository import GLib, WebKit2

    from hefesto_dualsense4unix.interface import hefesto_vivo as hv

    # 1. O «X» aos 20 ms: a espera acaba, e o laço que vem sai sozinho.
    tela = SimpleNamespace(view=_vista_de_mentira(), morreu=None)
    GLib.timeout_add(20, lambda: (gtk.main_quit(), False)[1])
    t0 = time.monotonic()
    hv._esperar_o_webkit_comecar(tela, teto_s=3.0)
    espera = time.monotonic() - t0
    laco = _o_laco_que_vem_s(gtk, teto_s=4.0)
    assert espera < 1.5, f"o «X» não encerrou a espera: ela durou {espera:.2f} s"
    assert laco < 1.5, (
        f"o pedido de sair se perdeu na espera: o laço que vem durou {laco:.2f} s, "
        "e o processo ficaria pendurado sem janela")

    # 2. O WebKit começa aos 20 ms: a espera acaba, e o laço que vem fica de pé.
    tela = SimpleNamespace(view=_vista_de_mentira(), morreu=None)
    GLib.timeout_add(20, lambda: (tela.view.emit("load-changed",
                                                 WebKit2.LoadEvent.COMMITTED), False)[1])
    t0 = time.monotonic()
    hv._esperar_o_webkit_comecar(tela, teto_s=3.0)
    espera = time.monotonic() - t0
    laco = _o_laco_que_vem_s(gtk, teto_s=0.4)
    assert espera < 1.5, f"o `committed` não encerrou a espera: {espera:.2f} s"
    assert laco >= 0.3, f"a espera inventou um pedido de sair: o laço durou {laco:.2f} s"
