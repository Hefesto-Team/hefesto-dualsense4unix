"""O mapa do controle acende todo sensor, e a página fala em branco, sem rodapé nem chassi."""
from __future__ import annotations

import json
import re
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.hefesto_vivo`, que carrega o GTK")

from hefesto_dualsense4unix.interface import hefesto_vivo, onde, pacotes
from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02
from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05
from hefesto_dualsense4unix.interface.pacotes import a13_mapa_do_controle as a13

PAGINA = a13.PAGINA
P1, P2 = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"
ROSA = "rgb(255, 121, 198)"
FUNDO = (0x21, 0x22, 0x2C)


def _mesa() -> list[dict[str, Any]]:
    return [{"pref": f"p{n}", "jogador": n, "uniq": u, "cor": "", "nome": "Não sei",
             "via": "BT", "transporte": "bt", "conectado": True}
            for n, u in enumerate((P1, P2), start=1)]


def _entrada(uniq: str, n: int, **inputs: Any) -> dict[str, Any]:
    return {"uniq": uniq, "connected": True, "is_primary": n == 1, "transport": "bt",
            "player_slot": n, "inputs": {"buttons": [], **inputs}}


def _contexto(escolhido: str = "p1", p1: dict[str, Any] | None = None,
              p2: dict[str, Any] | None = None, **estado: Any) -> pacotes.Contexto:
    conectados = [_entrada(P1, 1, **(p1 or {})), _entrada(P2, 2, **(p2 or {}))]
    return pacotes.Contexto(
        state={"active_profile": "regua", "controllers": conectados, **estado},
        mesa=_mesa(), conectados=conectados, estados={}, escolhido=escolhido)


def _acesos(ctx: pacotes.Contexto) -> set[str]:
    carga = pacotes.pacote_da_pagina(PAGINA, ctx) or {}
    return {k[len(a13.ACESO):] for k, v in carga["mesa"].items()
            if k.startswith(a13.ACESO) and v == "sim"}


def _vpad(jogador: int, par: list[int], idade: float = 0.1) -> dict[str, Any]:
    return {"rumble_ff": {"per_vpad": [
        {"player": jogador, "rumble_no_fisico": par, "rumble_no_fisico_ha_s": idade}]}}


@pytest.fixture(autouse=True)
def _sem_memoria_e_sem_parec(monkeypatch: pytest.MonkeyPatch) -> Any:
    """A régua não abre `parec` e não herda o último acelerômetro de outro teste."""
    monkeypatch.setattr(a02, "_seguir_as_ondas", lambda _alvos: None)
    a13._ULTIMA_ACEL.clear()
    a05._EM_TESTE.clear()
    a05._EM_TESTE_DA_HAPTICA.clear()
    yield
    a13._ULTIMA_ACEL.clear()
    a05._EM_TESTE.clear()
    a05._EM_TESTE_DA_HAPTICA.clear()


def test_o_giroscopio_acende_quando_o_controle_gira() -> None:
    parado = {"gyro": {"x": 1.0, "y": -2.0, "z": 0.5}}
    girando = {"gyro": {"x": 30.0, "y": 0.0, "z": 0.0}}
    assert "feat-giroscopio" not in _acesos(_contexto(p1=parado))
    assert "feat-giroscopio" in _acesos(_contexto(p1=girando))


def test_o_acelerometro_acende_pela_variacao_e_nao_pelo_valor() -> None:
    em_pe = {"accel": {"x": 0.0, "y": 0.0, "z": 1.0}}
    mexeu = {"accel": {"x": 0.4, "y": 0.0, "z": 1.0}}
    primeiro = _acesos(_contexto(p1=em_pe))
    segundo_igual = _acesos(_contexto(p1=em_pe))
    segundo_mexido = _acesos(_contexto(p1=mexeu))
    assert "feat-acelerometro" not in primeiro, "sem leitura anterior não há variação"
    assert "feat-acelerometro" not in segundo_igual, (
        "o 1 g da gravidade acendeu o acelerômetro de um controle parado")
    assert "feat-acelerometro" in segundo_mexido


def test_o_toque_no_touchpad_acende_o_touchpad() -> None:
    sem = {"touchpad": {"pontos": [], "width": 1920, "height": 1080}}
    com = {"touchpad": {"pontos": [{"x": 900, "y": 500}], "width": 1920, "height": 1080}}
    assert "touchpad" not in _acesos(_contexto(p1=sem))
    assert "touchpad" in _acesos(_contexto(p1=com))


def test_o_som_no_mic_acende_o_mic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(a02, "no_do_microfone", lambda _e: "fonte.de.prova")
    piso = a02._piso_da_onda()
    monkeypatch.setattr(a02, "alturas_do_no", lambda _n: tuple([piso] * 14))
    assert "mic" not in _acesos(_contexto()), "o silêncio (o piso) acendeu o mic"
    monkeypatch.setattr(a02, "alturas_do_no", lambda _n: tuple([piso] * 13 + [70]))
    assert "mic" in _acesos(_contexto())
    monkeypatch.setattr(a02, "alturas_do_no", lambda _n: None)
    assert "mic" not in _acesos(_contexto()), "sem leitura (não sei) o mic acendeu"


def test_cada_motor_acende_pelo_que_o_jogo_manda() -> None:
    """O par é (weak, strong): o forte é o motor ESQUERDO, o leve o direito."""
    assert not _acesos(_contexto(**_vpad(1, [0, 0]))) & {"feat-rumble-esquerdo",
                                                         "feat-rumble-direito"}
    so_forte = _acesos(_contexto(**_vpad(1, [0, 200])))
    assert "feat-rumble-esquerdo" in so_forte and "feat-rumble-direito" not in so_forte
    so_leve = _acesos(_contexto(**_vpad(1, [90, 0])))
    assert "feat-rumble-direito" in so_leve and "feat-rumble-esquerdo" not in so_leve
    velho = _acesos(_contexto(**_vpad(1, [90, 200], idade=30.0)))
    assert not velho & {"feat-rumble-esquerdo", "feat-rumble-direito"}, (
        "um par de 30 s atrás acendeu o motor: o jogo já parou")


def test_o_teste_da_aba_vibracao_acende_os_dois_motores_daquele_controle() -> None:
    a05._EM_TESTE.add(P1)
    assert {"feat-rumble-esquerdo", "feat-rumble-direito"} <= _acesos(_contexto("p1"))
    assert not {"feat-rumble-esquerdo", "feat-rumble-direito"} & _acesos(_contexto("p2"))


def test_a_haptica_acende_quando_chega_ao_controle() -> None:
    assert "feat-haptica" not in _acesos(_contexto())
    ctx = _contexto()
    ctx.state["controllers"][0]["haptica_no_ar"] = True
    assert "feat-haptica" in _acesos(ctx)
    a05._EM_TESTE_DA_HAPTICA.add(P1)
    assert "feat-haptica" in _acesos(_contexto())


def test_o_sensor_e_do_controle_escolhido_e_o_todos_e_a_uniao() -> None:
    girando = {"gyro": {"x": 30.0, "y": 0.0, "z": 0.0}}
    assert "feat-giroscopio" in _acesos(_contexto("p1", p1=girando))
    assert "feat-giroscopio" not in _acesos(_contexto("p2", p1=girando))
    assert "feat-giroscopio" in _acesos(_contexto("todos", p1=girando))


# --- a página -------------------------------------------------------------

def _pagina() -> str:
    return onde.pagina(PAGINA, publicado=False).read_text(encoding="utf-8")


def test_a_pagina_nao_tem_rodape_nem_o_nome_de_cada_peca_no_titulo() -> None:
    texto = _pagina()
    assert 'class="rodape"' not in texto, "o rodapé de contagem voltou"
    assert not re.search(r"\d+</b> peças", texto)
    titulo = re.search(r"<h1>(.*?)</h1>", texto, re.S)
    assert titulo and "nome de cada peça" not in titulo.group(1), titulo
    assert "O mapa do controle" in titulo.group(1)


def test_o_chassi_deixa_de_ser_botao() -> None:
    texto = _pagina()
    assert 'class="alvo a-corpo"' not in texto, "o chassi ainda é alvo no desenho"
    assert "item-corpo" not in texto, "o chassi ainda é uma linha clicável"
    assert ">Chassi<" not in texto, "o grupo do chassi ficou, vazio"


def test_a_barra_de_luz_do_banco_de_provas_saiu() -> None:
    """O seletor de cor aqui não gravava nada no controle: o dono é a Iluminação."""
    texto = _pagina()
    assert 'id="luz"' not in texto and 'id="luz-off"' not in texto
    assert 'data-campo="luz-cor"' in texto, "a barra de luz VIVA do desenho sumiu"


def test_todo_sensor_tem_endereco_e_lugar_no_desenho() -> None:
    texto = _pagina()
    for peca in a13.SENSORES:
        assert f'data-campo="{a13.ACESO}{peca}"' in texto, f"a linha de {peca} não acende"
        assert f'id="mp-{peca}"' in texto, f"{peca} não tem lugar no desenho"


# --- o WebKit -------------------------------------------------------------

MEDIDA = """
(function(){
  const cor = s => { const e = document.querySelector(s);
                     return e ? getComputedStyle(e).color : null; };
  const sensor = {};
  SENSORES.forEach(k => {
    const g = document.getElementById('mp-' + k), p = g && g.querySelector('.peca');
    const linha = document.querySelector('.item-' + k);
    sensor[k] = g ? {opacidade: getComputedStyle(g).opacity,
                     fill: p ? getComputedStyle(p).fill : null,
                     linha: linha.classList.contains('on')} : null; });
  return JSON.stringify({sensor: sensor, textos: {
    nome: cor('.item .txt b'), apelido: cor('.item .ap'), id: cor('.item .id'),
    grupo: cor('.grupo-rot'), prova: cor('.prova-rot'), nota: cor('.prova-nota')}});
})()
""".replace("SENSORES", json.dumps(list(a13.SENSORES)))


def _no_webkit(cargas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre (rode com xvfb-run -a)")
    saiu: list[str] = []
    fila = list(cargas)
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(1600, 900)
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def proxima() -> None:
        if not fila:
            Gtk.main_quit()
            return
        pedido = hefesto_vivo.PEDIR_A_PINTURA.replace(
            "CARGA", json.dumps(fila.pop(0), ensure_ascii=False))
        view.evaluate_javascript(pedido, -1, None, None, None, pintou)

    def mediu(v: Any, res: Any) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:
            saiu.append(f"ERRO na medida: {e}")
        proxima()

    def pintou(v: Any, res: Any) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(f"ERRO na pintura: {e}")
            Gtk.main_quit()
            return
        GLib.timeout_add(150, lambda: (v.evaluate_javascript(
            MEDIDA, -1, None, None, None, mediu), False)[1])

    def instalou(v: Any, res: Any) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(f"ERRO no bootstrap: {e}")
            Gtk.main_quit()
            return
        proxima()

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(hefesto_vivo.BOOTSTRAP, -1, None, None, None, instalou)

    view.connect("load-changed", carregou)
    view.load_uri(onde.pagina(PAGINA, publicado=False).as_uri())
    guarda = GLib.timeout_add(20000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert len(saiu) == len(cargas), f"o WebKit não respondeu: {saiu}"
    assert not any(s.startswith("ERRO") for s in saiu), saiu
    return [json.loads(s) for s in saiu]


def _carga(ctx: pacotes.Contexto) -> dict[str, Any]:
    return pacotes.normalizar(pacotes.pacote_da_pagina(PAGINA, ctx) or {},
                              {P1: "p1", P2: "p2"})


def _tudo_ligado() -> pacotes.Contexto:
    ctx = _contexto("p1", p1={
        "gyro": {"x": 30.0, "y": 0.0, "z": 0.0},
        "accel": {"x": 0.4, "y": 0.0, "z": 1.0},
        "touchpad": {"pontos": [{"x": 900, "y": 500}], "width": 1920, "height": 1080},
    }, **_vpad(1, [90, 200]))
    ctx.state["controllers"][0]["haptica_no_ar"] = True
    return ctx


def _luminancia(cor: str) -> float:
    rgb = [int(v) for v in re.findall(r"\d+", cor)[:3]]
    lin = [(c / 255) / 12.92 if c / 255 <= 0.03928 else (((c / 255) + 0.055) / 1.055) ** 2.4
           for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def test_no_webkit_cada_sensor_acende_no_desenho_e_o_texto_e_branco() -> None:
    antes = _acesos(_contexto())
    assert not antes & set(a13.SENSORES), f"a régua começou com sensor aceso: {antes}"
    parado, ligado = _no_webkit([_carga(_contexto("p1", p1={
        "accel": {"x": 0.0, "y": 0.0, "z": 1.0}})), _carga(_tudo_ligado())])
    for peca in a13.SENSORES:
        em_repouso, aceso = parado["sensor"][peca], ligado["sensor"][peca]
        assert em_repouso and em_repouso["opacidade"] == "0" and not em_repouso["linha"], (
            f"{peca} em repouso: {em_repouso}")
        assert aceso["linha"], f"a linha de {peca} não acendeu: {aceso}"
        assert aceso["opacidade"] == "1" and aceso["fill"] == ROSA, (
            f"{peca} aceso no serviço e apagado no desenho: {aceso}")
    brancos = {k: v for k, v in ligado["textos"].items() if v != "rgb(255, 255, 255)"}
    assert not brancos, f"texto que não é branco: {brancos}"
    fundo = _luminancia(f"rgb{FUNDO}")
    assert (1.05) / (fundo + 0.05) >= 7, "o branco não passa o piso de contraste do fundo"
