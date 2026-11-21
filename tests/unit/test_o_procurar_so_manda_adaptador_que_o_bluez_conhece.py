"""O-PROCURAR-SO-MANDA-ADAPTADOR-QUE-O-BLUEZ-CONHECE-01 — o destino do pedido é do BlueZ.

A lista de adaptadores da Conexões soma aos do BlueZ os endereços que só apareceram no
``radio_ar`` e no ``radio_governador``; a central recusa o que não está em ``dono.adaptadores()``
(``sem_destino``). O destino do «Procurar» (e do «Conectar» e do «Parear») sai só dos que o
BlueZ descreve, e sem nenhum o pedido vai sem destino e a central escolhe.

A ponte é de mentira e registra o que ``radio.busca.set`` recebeu; nada abre o barramento. Faixa
sintética da casa: ``aa:bb:cc``.
"""
from __future__ import annotations

from typing import Any

import pytest

FANTASMA = "AABBCC0000F1"
REAL = "AABBCC0000F2"
OUTRO = "AABBCC0000F3"


@pytest.fixture
def a08() -> Any:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes.a08_conexoes`, que carrega o GTK")
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    a08_conexoes._ABERTO.clear()
    yield a08_conexoes
    a08_conexoes._ABERTO.clear()
    a08_conexoes._CENA_NA_TELA.clear()


class _Ponte:
    def __init__(self, resposta: dict[str, Any] | None = None) -> None:
        self.pedidos: list[dict[str, Any]] = []
        self.resposta = resposta

    def resultado(self, metodo: str, **parametros: Any) -> dict[str, Any]:
        assert metodo == "radio.busca.set"
        self.pedidos.append(parametros)
        if self.resposta is not None:
            return self.resposta
        destino = parametros.get("destino") or REAL
        return {"status": "ok", "busca": {"adaptador": destino}}


def _cena(a08: Any, lugares: list[dict[str, Any]], aberto: str | None = None) -> dict[str, Any]:
    cena = {"lugares": lugares, "aberto": aberto, "procurando": a08.PROCURAR_DESLIGADO}
    cena["destino_da_central"] = a08._destino_da_central(cena, {})
    cena["destino_do_conectar"] = a08._destino_do_conectar(cena)
    return cena


def test_o_destino_nunca_e_o_endereco_que_so_o_radio_ar_conhece(a08: Any) -> None:
    """D-2011-O-PROCURAR-SO-MANDA-ADAPTADOR-QUE-O-BLUEZ-CONHECE: o fantasma não é destino.

    O primeiro da lista só existe no ``radio_ar``; nem sozinho, nem como aberto, nem como o da
    central ele vai no pedido.

    MORDIDA: devolva ``cena["lugares"]`` inteiro em ``_os_que_o_bluez_conhece``.
    """
    lugares = [{"id": FANTASMA, "no_bluez": False}, {"id": REAL, "no_bluez": True},
               {"id": OUTRO, "no_bluez": True}]
    assert _cena(a08, lugares)["destino_do_conectar"] == REAL
    assert _cena(a08, lugares, aberto=FANTASMA)["destino_do_conectar"] == REAL
    assert _cena(a08, lugares, aberto=OUTRO)["destino_do_conectar"] == OUTRO
    assert _cena(a08, [{"id": FANTASMA, "no_bluez": False}])["destino_do_conectar"] == ""
    assert _cena(a08, [])["destino_do_conectar"] == ""


def test_o_procurar_liga_no_primeiro_clique_e_o_pedido_leva_so_o_adaptador_conhecido(
        a08: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2011-O-PROCURAR-SO-MANDA-ADAPTADOR-QUE-O-BLUEZ-CONHECE: sem abrir nenhum, a busca liga.

    Sem nenhum adaptador descrito, o pedido vai sem ``destino`` e a central escolhe; a recusa da
    central chega à pessoa pela resposta, nunca por uma frase de antes do pedido.

    MORDIDA: faça o ``_ligar_a_busca`` mandar ``destino`` vazio, ou volte a recusar o «Procurar»
    sem destino no ``radio_procurar``.
    """
    monkeypatch.setattr(a08, "_acordar_o_radio", lambda: False)
    lugares = [{"id": FANTASMA, "no_bluez": False}, {"id": REAL, "no_bluez": True}]
    a08._CENA_NA_TELA.clear()
    a08._CENA_NA_TELA.update(_cena(a08, lugares))
    ponte = _Ponte()
    assert a08.radio_procurar(None, {"evento": "click"}, ponte) == {"armou": True}
    assert ponte.pedidos == [{"ligada": True, "destino": REAL}]

    a08._CENA_NA_TELA.clear()
    a08._CENA_NA_TELA.update(_cena(a08, [{"id": FANTASMA, "no_bluez": False}]))
    ponte = _Ponte()
    assert a08.radio_procurar(None, {"evento": "click"}, ponte) == {"armou": True}
    assert ponte.pedidos == [{"ligada": True}]

    a08._CENA_NA_TELA.clear()
    a08._CENA_NA_TELA.update(_cena(a08, []))
    recusa = _Ponte({"status": "sem_destino", "busca": None})
    with pytest.raises(RuntimeError, match=r"sem_destino"):
        a08.radio_procurar(None, {"evento": "click"}, recusa)
    assert recusa.pedidos == [{"ligada": True}]


def test_a_cena_marca_so_o_adaptador_que_o_bluez_descreve(
        a08: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-2011-O-PROCURAR-SO-MANDA-ADAPTADOR-QUE-O-BLUEZ-CONHECE: a cena marca quem o BlueZ tem.

    O BlueZ de mentira descreve um adaptador; o ``radio_governador`` publica outro, que segue na
    lista da tela e não é destino.

    MORDIDA: marque ``no_bluez`` como verdadeiro em todo lugar de ``cena_do_radio``.
    """
    from hefesto_dualsense4unix.integrations.bluez_dbus import AdaptadorDoBluez
    from hefesto_dualsense4unix.integrations.mesa_de_radio import Mesa
    from hefesto_dualsense4unix.interface import pacotes
    from hefesto_dualsense4unix.interface.pacotes import em_fundo
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

    monkeypatch.setattr(em_fundo, "_FUNDO", {})
    for nome in ("_ABERTO", "_CENA_NA_TELA", "_NIVEL_NA_TELA"):
        monkeypatch.setattr(a08, nome, {})
    monkeypatch.setattr(em_fundo, "LER_NA_HORA", True)
    monkeypatch.setattr(a08, "_mesa_do_radio", lambda recarregar=False: Mesa())
    descrito = AdaptadorDoBluez("/org/bluez/hci1", "hci1", "aa:bb:cc:00:00:f2", varrendo=False)
    monkeypatch.setattr(em_fundo, "ler_o_bluez", lambda: ((descrito,), ()))
    monkeypatch.setattr(a08, "_ler_a_maquina", lambda: (MaquinaConfig(), {}))
    monkeypatch.setattr(a08, "_ler_o_wifi", lambda: None)
    monkeypatch.setattr(a08, "_ler_os_zumbis", lambda: {})
    estado = {"controllers": [], "radio_governador": {"aa:bb:cc:00:00:f1": {}}}
    cena = a08.cena_do_radio(pacotes.Contexto(state=estado, mesa=[], conectados=[]))
    marcas = {a08._so_hex(lug["id"]).upper(): lug["no_bluez"] for lug in cena["lugares"]}
    assert marcas == {REAL: True, FANTASMA: False}
    assert a08._so_hex(cena["destino_do_conectar"]).upper() == REAL
