"""Clicar num aparelho abre o painel dele: nome, tipo, extensor, o que fazer — e o resto.

O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01 (04/10/2026), com a A-ENTRADA-SEM-LUGAR-APARECE-NO-MAPA-01
absorvida. Ela pediu: *«clicar num dispositivo não oferece modificá-lo ou identificá-lo»*.

A página sob prova é a da BANCADA (``publicado=False``): o painel novo só vira o produto no
``--publicar`` de quem coordena, depois do olho dela. TUDO É DE MENTIRA: barramento ``usb9``,
caminhos ``9-*``, ``maquina.json`` no ``tmp_path``.

AS MORDIDAS (arrancando a cura e vendo reprovar): ``cuidarDoAviso`` sem o ``setTimeout`` (o aviso
não some), o ``data-gesto`` do tipo, o ``modelo`` que ``_aparelho`` põe no dado, a exclusão da
fileira «Sem Lugar» do plano.
"""

from __future__ import annotations

import gc
import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
from hefesto_dualsense4unix.integrations import mapa_das_portas
from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    Aparelho,
    Barramento,
    Censo,
)
from hefesto_dualsense4unix.interface import arranjo_desta_maquina, onde
from hefesto_dualsense4unix.utils.maquina import (
    FaceDeclarada,
    MapaDaMesa,
    PortaDeclarada,
    caminho_da_maquina,
    carregar_maquina,
    gravar_maquina,
)

_TECLADO = ("03", "01", "01")
_CHIP = ("ff", "ff", "ff")


def _aparelho(caminho: str, vid: str, pid: str, especie: str, tripla: tuple[str, str, str],
              produto: str, mbps: float = 480.0) -> Aparelho:
    return Aparelho(
        no=f"/sys/de-mentira/{caminho}", nome_do_kernel=caminho, vid=vid, pid=pid,
        produto=produto, especie=especie, classe=tripla[0], subclasse=tripla[1],
        protocolo=tripla[2], velocidade_mbps=mbps,
    )


def _teclado(caminho: str = "9-1") -> Aparelho:
    return _aparelho(caminho, "1111", "0001", "Teclado", _TECLADO, "Teclado de prova")


def _placa(caminho: str = "9-5") -> Aparelho:
    return _aparelho(caminho, "3333", "0003", "", _CHIP, "Placa de prova", 5000.0)


def _censo(*aparelhos: Aparelho) -> Censo:
    return Censo(
        aparelhos=aparelhos,
        barramentos=(Barramento(no="/sys/usb9", nome_do_kernel="usb9", velocidade_mbps=480.0),),
    )


def _mapa(sem_lugar: bool = False) -> MapaDaMesa:
    caminhos = {"1": "9-1", "2": "9-2", "5": "9-5"}
    faces = [FaceDeclarada(nome="Frente", portas=["1", "2"], perto=True),
             FaceDeclarada(nome="Traseira", portas=["5"])]
    portas = {n: PortaDeclarada(caminho=c) for n, c in caminhos.items()}
    if sem_lugar:
        portas["6"] = PortaDeclarada(caminho="9-6")
    return MapaDaMesa(faces=faces, portas=portas)


@pytest.fixture()
def disco(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from hefesto_dualsense4unix.integrations import censo_do_barramento

    alvo = caminho_da_maquina()
    assert alvo.is_relative_to(tmp_path), f"o maquina.json da régua não está desviado: {alvo}"
    assert gravar_maquina({"mapa": _mapa().model_dump(mode="json")})
    monkeypatch.setattr(censo_do_barramento, "ler_o_barramento", lambda: _censo(_teclado()))
    monkeypatch.setattr(mapa_das_portas, "serial_do_no", lambda _no: "")
    return alvo


def _ler(*aparelhos: Aparelho, reexame: bool = False) -> dict[str, Any]:
    fontes: dict[str, Any] = {
        "carregar": carregar_maquina,
        "ler_o_barramento": lambda: _censo(*aparelhos),
        "ler_o_serial": lambda _no: "",
    }
    dado = (arranjo_desta_maquina.reexaminar(**fontes) if reexame
            else arranjo_desta_maquina.para_a_pagina(**fontes))
    assert dado is not None
    return dado


# ───────────────────────── o dado que a página recebe ─────────────────────────


def test_o_aparelho_chega_a_pagina_com_o_modelo_e_o_que_a_maquina_ve(disco: Path) -> None:
    dado = _ler(_teclado(), _placa())
    por_tipo = {a["nome"]: a for a in dado["aparelhos"]}
    teclado = por_tipo["Teclado de prova"]
    assert teclado["modelo"] == "1111:0001", "sem o vid:pid o painel não sabe a quem gravar"
    assert "USB 2.0" in teclado["etiquetas"]
    assert "tipoDeclarado" not in teclado and "nomeDeclarado" not in teclado

    assert ee.declarar_o_aparelho("1111:0001", tipo="mouse", apelido="O teclado dela").gravou
    depois = {a["nome"]: a for a in _ler(_teclado(), _placa())["aparelhos"]}["Teclado de prova"]
    assert depois["tipoDeclarado"] == "mouse" and depois["nomeDeclarado"] == "O teclado dela"
    assert depois["cor"] != teclado["cor"], "o tipo que ela disse não decide a cor"


def test_o_tipo_que_ela_diz_so_pesa_no_motor_quando_a_maquina_nao_leu_a_classe(
    disco: Path,
) -> None:
    """QUEM VENCE: a máquina no que mede. A placa ``ff/ff/ff`` não tem classe; o teclado tem."""
    assert ee.declarar_o_aparelho("3333:0003", tipo="wifi").gravou
    assert ee.declarar_o_aparelho("1111:0001", tipo="mouse").gravou
    tipos = mapa_das_portas.tipos_declarados(carregar_maquina())
    assert tipos == {"3333:0003": "wifi", "1111:0001": "mouse"}
    bancada = mapa_das_portas.mesa_do_motor(_mapa(), _censo(_teclado(), _placa()), tipos)
    classes = {a.id: a.classe for a in bancada.mesa.aparelhos}
    assert classes["9-5"] == "wifi", "a placa sem classe não ganhou o tipo que ela disse"
    assert classes["9-1"] == "teclado", "o tipo dito venceu o que o kernel mede"


def test_a_velocidade_dita_so_vale_na_entrada_vazia(disco: Path) -> None:
    """Com aparelho na entrada a máquina mede, e a medida vence o que ela declarou."""
    mapa = MapaDaMesa(
        faces=[FaceDeclarada(nome="Frente", portas=["1", "2"])],
        portas={"1": PortaDeclarada(caminho="9-1", usb=3), "2": PortaDeclarada(usb=3)},
    )
    bancada = mapa_das_portas.mesa_do_motor(mapa, _censo(_teclado()))
    usb = {e.n: e.usb for f in bancada.mesa.faces for e in f.entradas}
    assert usb["1"] == 2, "ela disse 3.0, mas há um teclado a 480M nela: vale a medida"
    assert usb["2"] == 3, "na entrada vazia a máquina não sabe: vale o que ela disse"


def test_a_entrada_sem_lugar_aparece_fora_do_plano(disco: Path) -> None:
    """O «Salvar» do Mapear com o lugar vazio numera a entrada, e ela some do mapa: agora não."""
    assert gravar_maquina({"mapa": _mapa(sem_lugar=True).model_dump(mode="json")})
    dado = _ler(_teclado())
    fileira = next((f for f in dado["faces"] if f.get("semLugar")), None)
    assert fileira is not None, "a entrada numerada sem face não foi desenhada"
    assert [p["n"] for p in fileira["portas"]] == ["6"]
    assert all(not f.get("semLugar") or f is fileira for f in dado["faces"])


def test_a_leitura_da_maquina_so_diz_o_que_se_mede(disco: Path) -> None:
    mapa = MapaDaMesa(
        faces=[FaceDeclarada(nome="Traseira", portas=["1", "2", "3", "4"])],
        portas={n: PortaDeclarada(caminho=f"9-{n}") for n in "1234"},
    )
    radios = tuple(
        _aparelho(f"9-{n}", f"44{n}{n}", "0001", "Teclado", _TECLADO, f"Radio {n}")
        for n in "123"
    )
    frases = mapa_das_portas.leitura_da_maquina(mapa, _censo(*radios))
    assert frases == ["3 rádios colados nas entradas 1 a 3"], frases
    assert not any("longe" in f for f in frases), "posição física entre entradas não se lê"
    assert mapa_das_portas.leitura_da_maquina(mapa, _censo(radios[0])) == []


def test_a_leitura_diz_o_wifi_em_usb3_encostado_no_bluetooth(disco: Path) -> None:
    from dataclasses import replace

    mapa = MapaDaMesa(
        faces=[FaceDeclarada(nome="Traseira", portas=["1", "2", "3"])],
        portas={n: PortaDeclarada(caminho=f"9-{n}") for n in "123"},
    )
    wifi = replace(_placa("9-1"), ligado_como="wifi")
    bt = _aparelho("9-2", "2222", "0002", "Bluetooth", ("e0", "01", "01"), "Dongle de prova")
    frases = mapa_das_portas.leitura_da_maquina(mapa, _censo(wifi, bt))
    assert frases == ["Wi-Fi em USB 3.0 encostado na Entrada 2"], frases
    # o Wi-Fi a 480M não ocupa o SuperSpeed: nada a dizer
    lento = replace(wifi, velocidade_mbps=480.0)
    assert mapa_das_portas.leitura_da_maquina(mapa, _censo(lento, bt)) == []
    # dois bluetooths lado a lado não formam o par
    outro = _aparelho("9-1", "2223", "0002", "Bluetooth", ("e0", "01", "01"), "Outro dongle")
    assert mapa_das_portas.leitura_da_maquina(mapa, _censo(outro, bt)) == []


# ───────────────────────── os gestos gravam ─────────────────────────


def test_os_gestos_do_painel_gravam_no_disco_dela(disco: Path) -> None:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")
    from hefesto_dualsense4unix.interface import pacotes

    def gesto(nome: str) -> Any:
        achado = pacotes.gesto_da_pagina(arranjo_desta_maquina.PAGINA, nome)
        assert achado is not None, f"o gesto {nome} não tem dono"
        return achado

    gesto("aparelho-tipo")(None, {"modelo": "1111:0001", "tipodito": "webcam"}, None)
    gesto("aparelho-nome")(None, {"modelo": "1111:0001", "valor": "Meu aparelho"}, None)
    gesto("entrada-extensor")(None, {"entrada": "2", "ligado": "true"}, None)
    gesto("entrada-lugar")(None, {"entrada": "2", "valor": "Traseira"}, None)
    maquina = carregar_maquina()
    assert maquina.mesa.radios["1111:0001"].tipo == "webcam"
    assert maquina.mesa.radios["1111:0001"].apelido == "Meu aparelho"
    assert maquina.mapa.portas["2"].extensor is True
    assert next(f for f in maquina.mapa.faces if f.nome == "Traseira").portas == ["5", "2"] or (
        "2" in next(f for f in maquina.mapa.faces if f.nome == "Traseira").portas)
    assert "2" not in next(f for f in maquina.mapa.faces if f.nome == "Frente").portas

    gesto("voltar-ao-automatico")(None, {"modelo": "1111:0001", "entrada": "2"}, None)
    maquina = carregar_maquina()
    assert maquina.mesa.radios.get("1111:0001") is None or not (
        maquina.mesa.radios["1111:0001"].tipo or maquina.mesa.radios["1111:0001"].apelido)
    assert not maquina.mapa.portas["2"].extensor

    for ruim in ({"modelo": "", "tipodito": "wifi"}, {"modelo": "1111:0001", "tipodito": "avião"},
                 {"modelo": "nada", "tipodito": "wifi"}):
        with pytest.raises(ValueError):
            gesto("aparelho-tipo")(None, ruim, None)
    with pytest.raises(ValueError):
        gesto("entrada-extensor")(None, {"entrada": "2", "ligado": ""}, None)
    with pytest.raises(ValueError):
        gesto("entrada-lugar")(None, {"entrada": "2", "valor": "Cozinha"}, None)


# ───────────────────────── a página (WebKit, bancada) ─────────────────────────


def _clicar(seletor: str) -> str:
    alvo = json.dumps(seletor)
    return (f"(function(){{const b=document.querySelector({alvo});"
            f"if(!b){{return 'sem ' + {alvo};}} b.click(); return 'clicou';}})()")


_LER = r"""
(function(){
  const ed = document.getElementById('edita');
  const q = s => ed && !ed.hidden ? [...ed.querySelectorAll(s)] : [];
  const chave = ed && ed.querySelector('[data-extensor]');
  return JSON.stringify({
    aberto: !!(ed && !ed.hidden),
    texto: ed && !ed.hidden ? ed.innerText.replace(/\s+/g, ' ').trim() : '',
    tipos: q('.tipo-do-aparelho').map(
      b => b.dataset.tipodito + ':' + b.getAttribute('aria-pressed')),
    extensor: chave ? chave.getAttribute('aria-checked') : null,
    nome: (ed && ed.querySelector('.campo-nome') || {}).value,
    identificar: !!(ed && ed.querySelector('#identificar')),
    aviso: (document.querySelector('.aviso-uma-linha') || {innerText: ''})
      .innerText.replace(/\s+/g, ' ').trim(),
    detalhe: !!document.querySelector('.aviso-detalhe'),
    semLugar: [...document.querySelectorAll('.face-cab h3')].map(h => h.textContent.trim()),
    botoes: [...document.querySelectorAll('.ap-btn')].map(b => b.dataset.apAbre || ''),
  });
})()
"""


def _na_pagina(passos: list[str]) -> tuple[list[Any], list[dict[str, Any]]]:
    try:
        return _na_pagina_sem_recolher(passos)
    finally:
        gc.collect()
        from gi.repository import Gtk

        while Gtk.events_pending():
            Gtk.main_iteration_do(False)


def _na_pagina_sem_recolher(passos: list[str]) -> tuple[list[Any], list[dict[str, Any]]]:
    """A página da BANCADA num WebKit fora da tela, com o BOOTSTRAP do piloto."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("abre a página num WebKit")
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    from hefesto_dualsense4unix.interface import hefesto_vivo

    mensagens: list[dict[str, Any]] = []
    respostas: list[str] = []
    ucm = WebKit2.UserContentManager()
    ucm.register_script_message_handler("hefesto")
    ucm.connect("script-message-received::hefesto",
                lambda _u, r: mensagens.append(json.loads(r.get_js_value().to_string())))
    view = WebKit2.WebView.new_with_user_content_manager(ucm)
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(1400, 1000)
    janela.add(view)
    janela.show_all()
    fila = [hefesto_vivo.BOOTSTRAP, *passos]

    def seguinte() -> bool:
        if not fila:
            GLib.timeout_add(400, lambda: (Gtk.main_quit(), False)[1])
            return False
        js = fila.pop(0)

        def respondeu(v: Any, res: Any, _u: Any = None) -> None:
            try:
                respostas.append(v.evaluate_javascript_finish(res).to_string())
            except Exception as erro:
                respostas.append(f"ERRO {erro}")
            GLib.idle_add(seguinte)

        view.evaluate_javascript(js, -1, None, None, None, respondeu, None)
        return False

    def carregou(_v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            seguinte()

    view.connect("load-changed", carregou)
    view.load_uri(onde.pagina(arranjo_desta_maquina.PAGINA, publicado=False).as_uri())
    guarda = GLib.timeout_add(30000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert len(respostas) == len(passos) + 1, f"o WebKit parou no meio: {respostas}"
    assert respostas[0] == "ok", f"o BOOTSTRAP do piloto não instalou: {respostas[0]}"
    lidas = [json.loads(r) if r.startswith("{") else r for r in respostas[1:]]
    return lidas, mensagens


def _js(dado: dict[str, Any], reexame: bool = False) -> str:
    return arranjo_desta_maquina.js_da_entrega(dado, reexame=reexame)


def test_clicar_no_aparelho_abre_o_painel_no_exemplo() -> None:
    """No exemplo (sem produto) o painel abre, mostra os seis tipos e a chave do extensor."""
    lidas, mensagens = _na_pagina([
        _LER,
        _clicar(".ap-btn[data-ap-abre]"),
        _LER,
    ])
    antes, _, depois = lidas
    assert not antes["aberto"]
    assert depois["aberto"], "o clique no aparelho não abriu o painel"
    assert len(depois["tipos"]) == 6, depois["tipos"]
    assert depois["extensor"] in ("true", "false"), "o painel não tem a chave do extensor"
    texto = depois["texto"].lower()  # a folha de estilo põe Maiúsculas Nas Palavras
    assert "voltar ao automático" in texto and "mais desta entrada" in texto, texto
    assert depois["identificar"]
    assert not [m for m in mensagens if m.get("gesto")], (
        f"o exemplo não grava nada: {mensagens}")


def test_o_painel_no_produto_manda_o_gesto_de_cada_clique(disco: Path) -> None:
    """Tipo, extensor e «Voltar ao automático» chegam ao piloto com o ``vid:pid`` e a entrada."""
    dado = _ler(_teclado())
    lidas, mensagens = _na_pagina([
        _js(dado),
        _clicar(".ap-btn[data-ap-abre]"),
        _LER,
        _clicar('.tipo-do-aparelho[data-tipodito="webcam"]'),
        _clicar("[data-extensor]"),
        _clicar("#voltar-ao-automatico"),
    ])
    painel = lidas[2]
    assert painel["aberto"], "o clique no aparelho do produto não abriu o painel"
    assert "teclado:true" in painel["tipos"], (
        f"o painel não marca o tipo que a máquina leu: {painel['tipos']}")
    gestos = [m for m in mensagens if m.get("gesto")]
    por_nome = {m["gesto"]: m for m in gestos}
    assert por_nome["aparelho-tipo"]["tipodito"] == "webcam"
    assert por_nome["aparelho-tipo"]["modelo"] == "1111:0001"
    assert por_nome["entrada-extensor"]["entrada"] == "1"
    assert por_nome["entrada-extensor"]["ligado"] == "true"
    assert por_nome["voltar-ao-automatico"]["modelo"] == "1111:0001"


def test_identificar_so_pede_para_tirar_e_por_e_nao_mexe_no_aparelho(disco: Path) -> None:
    dado = _ler(_teclado())
    lidas, mensagens = _na_pagina([
        _js(dado),
        _clicar(".ap-btn[data-ap-abre]"),
        _clicar("#identificar"),
        _LER,
    ])
    texto = lidas[3]["texto"]
    assert "tire o aparelho e ponha de novo" in texto.lower(), texto
    assert not [m for m in mensagens if m.get("gesto")], (
        f"«Identificar» mandou gesto ao aparelho: {mensagens}")


def test_o_aparelho_da_fileira_sem_lugar_fica_no_lugar_e_a_fileira_aparece(disco: Path) -> None:
    """Sem lugar o motor não vê a entrada: o aparelho fica, e o painel diz porquê."""
    assert gravar_maquina({"mapa": _mapa(sem_lugar=True).model_dump(mode="json")})
    dado = _ler(_teclado("9-6"))
    lidas, _ = _na_pagina([
        _js(dado),
        _LER,
        _clicar(".ap-btn[data-ap-abre]"),
        _LER,
    ])
    assert "Sem Lugar" in lidas[1]["semLugar"], lidas[1]["semLugar"]
    texto = lidas[3]["texto"].lower()
    assert "sem lugar no gabinete" in texto, texto
    assert "mostrar a entrada boa" not in texto, "o plano mandou sair da fileira sem lugar"


_RELOGIO_DE_MENTIRA = """
(function(){
  window.__esperas = [];
  const real = window.setTimeout;
  window.setTimeout = function(f, ms){
    window.__esperas.push([f, ms]); return window.__esperas.length;
  };
  window.__real = real;
  return 'ok';
})()
"""

_DISPARAR_OS_10_S = """
(function(){
  const e = window.__esperas.filter(x => x[1] === 10000);
  if (!e.length) {
    return 'sem espera de 10 s: ' + JSON.stringify(window.__esperas.map(x => x[1]));
  }
  e[e.length - 1][0]();
  return 'disparou';
})()
"""


def test_o_aviso_de_mudou_de_lugar_some_em_dez_segundos_e_o_x_fecha_na_hora(disco: Path) -> None:
    """O tempo é de mentira (o relógio da página é capturado): 10 s, ✕ e «Ver» que segura."""
    aberta = _ler(_teclado("9-1"))
    mudou = _ler(_teclado("9-2"), reexame=True)
    lidas, _ = _na_pagina([
        _js(aberta),
        _RELOGIO_DE_MENTIRA,
        _js(mudou, reexame=True),
        _LER,
        _DISPARAR_OS_10_S,
        _LER,
        _js(mudou, reexame=True),
        _clicar("#aviso-ver"),
        _LER,
        _clicar("#aviso-fecha"),
        _LER,
    ])
    com_aviso, disparo, sumiu, _, _, segurado, _, fechado = lidas[3:]
    assert "mudou" in com_aviso["aviso"].lower(), com_aviso
    assert disparo == "disparou", disparo
    assert not sumiu["aviso"], "passados os 10 s o aviso ficou na tela"
    assert segurado["detalhe"], "o «Ver» não abriu o detalhe"
    assert not fechado["aviso"] and not fechado["detalhe"], "o ✕ não fechou o aviso"
