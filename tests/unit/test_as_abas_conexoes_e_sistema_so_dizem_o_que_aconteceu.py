"""AS-ABAS-CONEXOES-E-SISTEMA-SO-DIZEM-O-QUE-ACONTECEU-01 — o verde e a frase têm base.

O «Retomar» e o «Só este» só ficam verdes com a resposta do serviço; o recibo das correções cita
só botão que a página tem e só fala em reconectar quando há controle; a dica do Wi-Fi em USB 3.0
aconselha sem prometer. A ponte é de mentira e nada abre o barramento.
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.daemon_actions import format_fix_safe_result
from hefesto_dualsense4unix.interface import onde

RAIZ = Path(__file__).resolve().parents[2]
PUBLICADAS = ("01-jogar.html", "08-conexoes.html", "09-sistema.html")
SEM_RESPOSTA = [False, (False, None)]
UNIQ = "aabbcc000001"


class _Ponte:
    def __init__(self, resposta: Any) -> None:
        self.resposta = resposta
        self.pedidos: list[tuple[str, dict[str, Any]]] = []

    def chamar_detalhado(self, metodo: str, **parametros: Any) -> Any:
        self.pedidos.append((metodo, parametros))
        return self.resposta

    def chamar(self, metodo: str, **parametros: Any) -> bool:
        raise AssertionError(f"{metodo}: o gesto descartou a resposta do serviço")


@pytest.fixture
def a08() -> Any:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes.a08_conexoes`, que carrega o GTK")
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


@pytest.fixture
def a09(monkeypatch: pytest.MonkeyPatch) -> Any:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes.a09_sistema`, que carrega o GTK")
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema

    monkeypatch.setattr(a09_sistema, "_trava", lambda ctx, nome, travas=None: None)
    return a09_sistema


@pytest.mark.parametrize("resposta", SEM_RESPOSTA)
def test_o_retomar_so_fica_verde_com_a_resposta_do_servico(a09: Any, resposta: Any) -> None:
    """D-2011-AS-ABAS-SO-DIZEM-O-QUE-ACONTECEU: sem resposta, levanta.

    MORDIDA: volte o ``retomar`` a ``p.chamar("daemon.resume")``.
    """
    ponte = _Ponte(resposta)
    with pytest.raises(RuntimeError, match="continuar pausado"):
        a09.retomar(SimpleNamespace(state={"paused": True}), {}, ponte)
    assert ponte.pedidos == [("daemon.resume", {})]
    with pytest.raises(RuntimeError, match="o serviço disse não"):
        a09.retomar(SimpleNamespace(state={}), {}, _Ponte((False, "o serviço disse não")))
    a09.retomar(SimpleNamespace(state={}), {}, _Ponte((True, None)))
    a09.retomar(SimpleNamespace(state={}), {}, _Ponte(True))


@pytest.mark.parametrize("resposta", SEM_RESPOSTA)
def test_o_so_este_so_fica_verde_com_a_resposta_do_servico(a08: Any, resposta: Any) -> None:
    """D-2011-AS-ABAS-SO-DIZEM-O-QUE-ACONTECEU: sem resposta, levanta.

    MORDIDA: volte o ``alvo`` a ``p.chamar("controller.target.set", index=indice)``.
    """
    ctx = SimpleNamespace(por_uniq=lambda uniq: {"index": 2})
    ponte = _Ponte(resposta)
    with pytest.raises(RuntimeError, match="o alvo pode não ter mudado"):
        a08.alvo(ctx, {"uniq": UNIQ}, ponte)
    assert ponte.pedidos == [("controller.target.set", {"index": 2})]
    with pytest.raises(RuntimeError, match="recusa do serviço"):
        a08.alvo(ctx, {"uniq": UNIQ}, _Ponte((False, "recusa do serviço")))
    a08.alvo(ctx, {"uniq": UNIQ}, _Ponte((True, None)))
    a08.alvo(ctx, {"uniq": UNIQ}, _Ponte(True))


def _recibos() -> list[str]:
    saidas = []
    for tag in ("adiado-steam-aberta", "recusado-jogo-aberto", "aplicado", "erro"):
        saidas.append(format_fix_safe_result({
            "ran": 2, "missing": 0,
            "steam_input": (0 if tag != "erro" else 1, f"[steam-input] resultado={tag}\n"),
            "steam_input_jogos": ["Jogo (appid 1)"]}))
    return saidas


def test_o_recibo_so_cita_botao_que_a_pagina_tem() -> None:
    """D-2011-AS-ABAS-SO-DIZEM-O-QUE-ACONTECEU: todo «nome» do recibo é botão.

    O nome entre «» de cada recibo existe como texto de botão numa página publicada; o recibo
    que adia a Steam manda o gesto de hoje, e o «Deixar tudo pronto» (da janela antiga) saiu.

    MORDIDA: devolva a frase velha do recibo (``Use o botão 'Deixar tudo pronto'``).
    """
    paginas = "\n".join(
        onde.pagina(nome, publicado=True).read_text(encoding="utf-8") for nome in PUBLICADAS)
    citados = {n for recibo in _recibos() for n in re.findall(r"«([^»]+)»", recibo)}
    assert citados == {"Permitir correções automáticas"}
    for nome in citados:
        assert re.search(rf"(?:>|</span>)\s*{re.escape(nome)}\s*</(?:button|a)>", paginas), nome
    adiado = _recibos()[0]
    assert "duplo clique em «Permitir correções automáticas»" in adiado
    assert all("Deixar tudo pronto" not in r for r in _recibos())


def test_a_linha_do_anti_storm_so_sai_com_controle_a_reconectar(
        a09: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2011-AS-ABAS-SO-DIZEM-O-QUE-ACONTECEU: sem controle conectado, a linha some do recibo.

    MORDIDA: faça ``frase_do_anti_storm`` devolver a frase sem olhar a contagem.
    """
    monkeypatch.setattr(a09, "_reaplicar_as_correcoes", lambda: "Correções aplicadas.")
    com = a09._o_recibo_do_duplo_clique({"controllers": [{"connected": True}]})
    assert com.startswith("Correções aplicadas. A cura anti-storm")
    assert "reconecte o controle" in com
    assert a09._o_recibo_do_duplo_clique({"controllers": []}) == "Correções aplicadas."
    assert a09._o_recibo_do_duplo_clique(None) == "Correções aplicadas."
    assert "anti-storm" not in " ".join(_recibos())


def test_a_dica_do_wifi_em_usb_3_aconselha_sem_prometer(a08: Any) -> None:
    """D-2011-AS-ABAS-SO-DIZEM-O-QUE-ACONTECEU: a placa cai nos dois modos.

    A medida de 23/10 viu a queda também em 5 GHz e em USB 2.0; a dica diz o que costuma ajudar.
    O desenho (``mockup``) traz a mesma frase.

    MORDIDA: devolva «a placa não cai» à ``DICA_DO_USB_3_NO_2_4``.
    """
    assert "não cai" not in a08.DICA_DO_USB_3_NO_2_4
    assert a08.DICA_DO_USB_3_NO_2_4.endswith(
        "Trocar para 5 GHz ou para uma porta USB 2.0 costuma ajudar.")
    mockup = (RAIZ / "mockup" / "08-conexoes.html").read_text(encoding="utf-8")
    assert "a placa não cai" not in mockup
    assert "Trocar para 5 GHz ou para uma porta USB 2.0 costuma ajudar." in mockup
