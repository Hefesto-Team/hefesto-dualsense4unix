"""«A FAIXA DELE» no painel do aparelho (desenho 2 aprovado em 04/10/2026; desde 05/10/2026 o
painel único não a repete, e ela mora só na aba Conexões).

O-APARELHO-SE-CORRIGE-ONDE-SE-CLICA-01, o defeito que o conferente achou: a mini-faixa do painel
(os 79 canais, pintado é o bom, vazio com a marca de quem o tomou, e a frase «perde para…» ou
«briga com…») não tinha sido feita. É a MESMA conta da aba 08 (`faixas_do_ar`), dita no painel.

Tudo de mentira: barramento ``usb9``, ``maquina.json`` no ``tmp_path``, cena fabricada à mão.

MORDIDAS: o JS que desenha a faixa; o ``faixa`` que o ``_aparelho`` põe no dado; o ``modelo`` do
lugar na cena; a marca de quem perde na célula ocupada.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from tests.conftest import exigir_gi_real
from tests.unit import test_o_aparelho_se_corrige_onde_se_clica as base
from tests.unit.test_o_aparelho_se_corrige_onde_se_clica import (  # noqa: F401  (a fixture)
    _clicar,
    _js,
    _ler,
    _na_pagina,
    _teclado,
    disco,
)

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08

LER_A_FAIXA = r"""
(function(){
  const ed = document.getElementById('edita');
  const f = ed && !ed.hidden ? ed.querySelector('.faixa-dele') : null;
  const cont = k => f ? f.querySelectorAll('i.' + k).length : -1;
  return JSON.stringify({
    aberto: !!(ed && !ed.hidden),
    celulas: f ? f.querySelectorAll('i').length : -1,
    bons: cont('b'), perdidos: cont('p'), ocupados: cont('o'),
    marca: f && f.querySelector('i.p')
      ? f.querySelector('i.p').style.getPropertyValue('--marca') : '',
    titulo: f && f.querySelector('i.p') ? f.querySelector('i.p').title : '',
    texto: (ed && ed.querySelector('.faixa-dele-txt') || {innerText: ''}).innerText,
    marcas_txt: ed ? [...ed.querySelectorAll('.faixa-dele-txt i.marca-txt')].map(
      i => i.style.getPropertyValue('--marca') + '|' + (i.nextSibling || {}).textContent) : [],
    marca_visivel: ed && ed.querySelector('.faixa-dele-txt i.marca-txt')
      ? ed.querySelector('.faixa-dele-txt i.marca-txt').offsetWidth > 0 : false,
    rotulo: ed ? ed.innerText.toLowerCase().includes('a faixa dele') : false,
    aria: f ? f.getAttribute('aria-label') : '',
  });
})()
"""


def _faixa_de_mentira() -> dict[str, Any]:
    celulas = [["b", "", ""]] * 40 + [["p", "#c3e88d", "Wi-Fi"]] * 20 + [["b", "", ""]] * 19
    return {"celulas": celulas, "cor": "#f8f8f2", "texto": "perde para Wi-Fi",
            "partes": [["perde para ", ""], ["Wi-Fi", "#c3e88d"]]}


def test_o_dado_do_aparelho_leva_a_faixa_pelo_vid_pid(disco: Any) -> None:  # noqa: F811
    from hefesto_dualsense4unix.interface import arranjo_desta_maquina
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina

    fontes = {"carregar": carregar_maquina, "ler_o_barramento": lambda: base._censo(_teclado()),
              "ler_o_serial": lambda _no: ""}
    dado = arranjo_desta_maquina.para_a_pagina(**fontes, faixas=lambda: {"1111:0001": {"x": 1}})
    assert dado is not None
    (teclado,) = [a for a in dado["aparelhos"] if a.get("modelo") == "1111:0001"]
    assert teclado["faixa"] == {"x": 1}
    sem = arranjo_desta_maquina.para_a_pagina(**fontes)
    assert sem is not None
    assert all("faixa" not in a for a in sem["aparelhos"]), "sem leitura, sem faixa"

    def quebra() -> Any:
        raise RuntimeError("a leitura do rádio caiu")

    dado = arranjo_desta_maquina.para_a_pagina(**fontes, faixas=quebra)
    assert dado is not None, "a faixa é um extra: o arranjo chega sem ela"
    assert all("faixa" not in a for a in dado["aparelhos"])


def test_o_painel_unico_nao_repete_a_faixa_que_a_aba_08_desenha(disco: Any) -> None:  # noqa: F811
    """Desenho aprovado de 05/10/2026 (conjunto «Conexões 3»): o painel único do Mapa traz Nome,
    Tipo e uma linha de estado do aparelho; a faixa dele mora na aba Conexões, que a desenha com
    a mesma conta. O dado continua chegando à página (o teste acima), só não se repete ali.

    MORDIDA: devolva o bloco ``faixa-dele`` ao ``htmlDoPainelDoAparelho`` e a régua reprova."""
    dado = _ler(_teclado())
    for a in dado["aparelhos"]:
        if a.get("modelo") == "1111:0001":
            a["faixa"] = _faixa_de_mentira()
    lidas, _m = _na_pagina([_js(dado), _clicar(".ap-btn[data-ap-abre]"), LER_A_FAIXA])
    f = lidas[2]
    assert f["aberto"], f
    assert f["celulas"] == -1 and not f["rotulo"] and f["texto"] == "", f


# --- a conta: a mesma da aba 08 ---------------------------------------------------------------

ADAPTADOR = "AA:BB:CC:00:00:0A"


def _cena() -> dict[str, Any]:
    lug = {"id": ADAPTADOR, "lugar": "L1", "nome": "Esquerda", "entrada": "Entrada 15",
           "sabido": True, "face": "", "hub": False, "varrendo": False, "junto": "",
           "usb3": False, "conectando": False, "chegou": [], "quedas": [], "modelo": "8888:0008"}
    receptor = {"id": "1111:0001", "tipo": "teclado", "nome": "Teclado", "sugestao": "",
                "sugestao_tipo": "", "no": "", "lido": "", "produto": "", "receptor": True,
                "banda": [18, 35], "saude": {"teclas_presas": 3, "buracos": 0, "janela_s": 3600,
                                             "lendo": True}}
    return {
        "lido": True, "lugares": [lug], "aparelhos": [], "enlaces": {},
        "evitados": [{"lugar": ADAPTADOR, "ini": 18, "fim": 24}],
        "canais_medidos": {ADAPTADOR: True},
        "vizinhos": [receptor], "wifi": [], "portas": [], "pedido": None, "proposta": None,
        "ocupado": False, "aberto": None, "perto": [], "procurando": a08.PROCURAR_DESLIGADO,
    }


def test_a_faixa_do_radio_e_a_do_receptor_saem_da_conta_da_aba_08(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(a08, "cena_do_radio", lambda _ctx: _cena())
    faixas = a08.faixas_para_o_mapa(object())  # type: ignore[arg-type]
    radio = faixas["8888:0008"]
    estados = [c[0] for c in radio["celulas"]]
    assert len(estados) == 79 and estados[17] == "b" and estados[18:24] == ["p"] * 6
    assert radio["celulas"][18][2] == "Teclado", "o canal perdido na banda do teclado é dele"
    teclado = faixas["1111:0001"]
    ocupados = [k for k, c in enumerate(teclado["celulas"]) if c[0] == "o"]
    assert ocupados == list(range(18, 35))
    assert "3 teclas presas" in teclado["texto"], teclado["texto"]
    assert ["Teclado", a08.COR_DA_FAIXA_NO_MAPA["teclado"]] in radio["partes"], radio["partes"]
    for faixa in (radio, teclado):
        assert "".join(t for t, _c in faixa["partes"]) == faixa["texto"], faixa
    json.dumps(faixas)  # vai à página: tem de ser JSON


def test_a_marca_de_quem_perde_aparece_no_canal_ocupado_do_receptor(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A briga aparece nos DOIS gráficos: o receptor leva a marca do aparelho que perde ali."""
    cena = _cena()
    cena["aparelhos"] = [{"id": "AA:BB:CC:00:00:01", "lugar": ADAPTADOR, "tipo": "controle",
                          "nome": "Controle", "cor": "#ffffff", "conectado": True,
                          "estado": "conectado", "player": 1}]
    cena["enlaces"] = {ADAPTADOR: {"AABBCC000001": {"canais_evitados": list(range(20, 26))}}}
    monkeypatch.setattr(a08, "cena_do_radio", lambda _ctx: cena)
    faixas = a08.faixas_para_o_mapa(object())  # type: ignore[arg-type]
    teclado = faixas["1111:0001"]["celulas"]
    com_marca = [k for k, c in enumerate(teclado) if c[0] == "o" and c[1]]
    assert com_marca, "o teclado não leva a marca de quem perde nos canais dele"
    texto = faixas["1111:0001"]["texto"]
    assert texto.startswith("briga com Controle"), texto
    assert ["Controle", a08.COR_DA_FAIXA_NO_MAPA["controle"]] in faixas["1111:0001"]["partes"]
    # sem a saúde lida, o selo é o genérico de quem ocupa («briga com 1»): a frase não se repete
    cena["vizinhos"][0].pop("saude")
    texto = a08.faixas_para_o_mapa(object())["1111:0001"]["texto"]  # type: ignore[arg-type]
    assert texto.count("briga com") == 1, texto


def test_a_cena_inteira_diz_de_que_dongle_e_cada_adaptador(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Do BlueZ de mentira à cena: o lugar leva o `vid:pid` do rádio USB (a chave do painel)."""
    from hefesto_dualsense4unix.integrations.bluez_dbus import AdaptadorDoBluez
    from hefesto_dualsense4unix.integrations.mesa_de_radio import Adaptador, Mesa
    from hefesto_dualsense4unix.interface import pacotes
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

    for nome in ("_FUNDO", "_ABERTO", "_CENA_NA_TELA", "_NIVEL_NA_TELA"):
        monkeypatch.setattr(a08, nome, {})
    monkeypatch.setattr(a08, "LER_NA_HORA", True)
    mesa = Mesa(adaptadores=(Adaptador(interface="hci0", no="9-2", vid="8888", pid="0008",
                                       busnum=9, devpath="2"),))
    monkeypatch.setattr(a08, "_mesa_do_radio", lambda recarregar=False: mesa)
    adaptador = AdaptadorDoBluez("/org/bluez/hci0", "hci0", ADAPTADOR, varrendo=False)
    monkeypatch.setattr(a08, "_ler_o_bluez", lambda: ((adaptador,), ()))
    monkeypatch.setattr(a08, "_ler_a_maquina", lambda: (MaquinaConfig(), {}))
    monkeypatch.setattr(a08, "_ler_o_historico", lambda: {})
    monkeypatch.setattr(a08, "_ler_o_wifi", lambda: None)
    monkeypatch.setattr(a08, "_ler_os_zumbis", lambda: {})
    cena = a08.cena_do_radio(pacotes.Contexto(state={"controllers": []}, mesa=[], conectados=[]))
    assert [lug["modelo"] for lug in cena["lugares"]] == ["8888:0008"]
