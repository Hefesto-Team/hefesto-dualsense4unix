"""Sem leitura deste computador, o mapa diz o porquê e não desenha o gabinete de exemplo."""

from __future__ import annotations

import json
import os
import pathlib
import sys
import threading
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import arranjo_desta_maquina, onde, pagina_do_mapa
from hefesto_dualsense4unix.utils.maquina import (
    FaceDeclarada,
    MaquinaConfig,
    MapaDaMesa,
    PortaDeclarada,
)
from tests.conftest import skip_sem_gi_real

RAIZ = pathlib.Path(__file__).resolve().parents[2]

# O que só o gabinete de exemplo da página diz (a leitura congelada de 24/08/2026).
_DO_EXEMPLO = ("Leitura de exemplo", "coisas para mudar de lugar", "8 de 16 entradas mapeadas")

_LER_O_MAPA = r"""
(function(){
  var q = function(s){ return document.querySelector(s); };
  var vis = function(el){ return !!el && !el.hidden && el.getBoundingClientRect().height > 0; };
  return JSON.stringify({
    quando: (q('#de-quando') || {}).textContent || null,
    examinar: !!q('#reexaminar'),
    painel: vis(q('#painel')) ? q('#painel').innerText.trim() : '',
    faces: document.querySelectorAll('#faces .face-cab').length,
    palco: vis(q('.palco')),
    corpo: document.body.innerText
  });
})()
"""


def _modo(modo: str) -> str:
    return ("(function(){var b=document.querySelector('.modo[data-modo=" + json.dumps(modo)
            + "]');if(!b){return 'sem';}b.click();return 'ok';})()")


def _o_mapa() -> MapaDaMesa:
    return MapaDaMesa(
        faces=[FaceDeclarada(nome="Frente", portas=["1", "2"], perto=True)],
        portas={"1": PortaDeclarada(caminho="9-1"), "2": PortaDeclarada(caminho=None)})


def test_sem_mapa_declarado_o_porque_e_que_nada_foi_mapeado() -> None:
    assert arranjo_desta_maquina.porque_sem_leitura(MaquinaConfig) == pagina_do_mapa.SEM_MAPA


def test_com_mapa_declarado_o_porque_e_que_nao_deu_para_ler() -> None:
    porque = arranjo_desta_maquina.porque_sem_leitura(lambda: MaquinaConfig(mapa=_o_mapa()))
    assert porque == pagina_do_mapa.SEM_LEITURA


def test_o_arquivo_que_nao_se_le_e_nao_deu_para_ler() -> None:
    def carregar() -> MaquinaConfig:
        raise OSError("sem permissão")

    assert arranjo_desta_maquina.porque_sem_leitura(carregar) == pagina_do_mapa.SEM_LEITURA


def test_a_entrega_sem_dado_e_o_porque() -> None:
    for porque in pagina_do_mapa.FRASES_SEM_LEITURA:
        js = arranjo_desta_maquina.js_da_entrega(None, porque=porque)
        assert js == f"window.hefestoSemLeitura({json.dumps(porque)})"
    with pytest.raises(ValueError):
        arranjo_desta_maquina.js_sem_leitura("")
    with pytest.raises(ValueError):
        arranjo_desta_maquina.js_da_entrega(None)


def test_o_piloto_sem_leitura_diz_o_porque_a_pagina(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem arranjo, a abertura não cala: a página ouve o porquê, pelo laço do GTK."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa o piloto, que carrega o GTK")
    from gi.repository import GLib

    from hefesto_dualsense4unix.interface import hefesto_vivo

    leu = threading.Event()

    def para_a_pagina(**_fontes: Any) -> None:
        leu.set()

    monkeypatch.setattr(arranjo_desta_maquina, "para_a_pagina", para_a_pagina)
    monkeypatch.setattr(arranjo_desta_maquina, "porque_sem_leitura",
                        lambda: pagina_do_mapa.SEM_MAPA)
    perguntas: list[str] = []

    class _Ponte:
        def perguntar(self, js: str, volta: Any) -> None:
            perguntas.append(js)

    class _Piloto:
        _arranjo_entregue = hefesto_vivo.Piloto._arranjo_entregue
        _entregar = hefesto_vivo.Piloto._entregar
        _as_faixas_do_mapa = hefesto_vivo.Piloto._as_faixas_do_mapa

        def __init__(self) -> None:
            self.pagina = arranjo_desta_maquina.PAGINA
            self.ponte = _Ponte()
            self.cegueiras: list[str] = []

    hefesto_vivo.Piloto._entregar_o_arranjo(_Piloto())
    assert leu.wait(5), "a leitura não aconteceu"
    contexto = GLib.MainContext.default()
    for _ in range(200):
        if perguntas:
            break
        contexto.iteration(False)
        leu.wait(0.01)
    assert perguntas == [arranjo_desta_maquina.js_sem_leitura(pagina_do_mapa.SEM_MAPA)], (
        "sem leitura o piloto não disse nada à página, e ela fica no gabinete de exemplo")


@pytest.fixture
def tela() -> Any:
    """O desenho do mapa num WebView oculto."""
    if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
        pytest.skip("sem servidor gráfico: rode sob `xvfb-run -a` (pulo não é verde)")
    sys.path.insert(0, str(RAIZ / "scripts"))
    import regua_de_tela

    t = regua_de_tela.Tela(onde.BANCADA / arranjo_desta_maquina.PAGINA,
                           largura=1280, altura=900)
    yield t
    t.fechar()


def _ler(tela: Any) -> dict[str, Any]:
    lido: dict[str, Any] = json.loads(tela.executar(_LER_O_MAPA))
    return lido


@skip_sem_gi_real
@pytest.mark.parametrize("porque", sorted(pagina_do_mapa.FRASES_SEM_LEITURA))
def test_a_pagina_sem_leitura_nao_mostra_o_exemplo(tela: Any, porque: str) -> None:
    antes = _ler(tela)
    assert antes["faces"] and _DO_EXEMPLO[0] in antes["corpo"], (
        "a página não abriu no exemplo, e a régua não mede nada")
    assert tela.executar(arranjo_desta_maquina.js_sem_leitura(porque)) == "ok"
    frase = pagina_do_mapa.FRASES_SEM_LEITURA[porque]
    for modo in ("mesa", "ideal", "mao"):  # (noqa-acento) o data-modo da página
        assert tela.executar(_modo(modo)) == "ok", modo
        lido = _ler(tela)
        mostra = [f for f in _DO_EXEMPLO if f.lower() in lido["corpo"].lower()]
        assert not mostra, f"{modo}: sem leitura o mapa mostra {mostra}"
        assert lido["faces"] == 0 and not lido["palco"], f"{modo}: desenha o gabinete"
        assert lido["quando"] == frase and not lido["examinar"], (modo, lido["quando"])
        esperado = "" if modo == "mesa" else pagina_do_mapa.NADA_A_SUGERIR
        assert lido["painel"] == esperado, (modo, lido["painel"])


@skip_sem_gi_real
def test_a_leitura_que_chega_depois_desenha_o_gabinete(tela: Any) -> None:
    from hefesto_dualsense4unix.integrations.censo_do_barramento import Barramento, Censo

    assert tela.executar(arranjo_desta_maquina.js_sem_leitura(pagina_do_mapa.SEM_MAPA)) == "ok"
    dado = arranjo_desta_maquina.para_a_pagina(
        carregar=lambda: MaquinaConfig(mapa=_o_mapa()),
        ler_o_barramento=lambda: Censo(aparelhos=(), barramentos=(
            Barramento(no="/sys/usb9", nome_do_kernel="usb9", velocidade_mbps=480.0),)),
        ler_o_serial=lambda _no: "")
    assert dado is not None
    assert tela.executar(arranjo_desta_maquina.js_da_entrega(dado)) == "ok"
    lido = _ler(tela)
    assert lido["faces"] == 1 and lido["palco"], lido
    assert pagina_do_mapa.NADA_A_SUGERIR not in lido["corpo"]
