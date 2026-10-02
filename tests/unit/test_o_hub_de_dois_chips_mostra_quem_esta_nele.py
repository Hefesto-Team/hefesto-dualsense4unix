"""O hub de dois chips mostra quem está nele — e só quem ela plugou."""

from __future__ import annotations

from hefesto_dualsense4unix.integrations import arranjo_da_mesa as motor
from hefesto_dualsense4unix.integrations import mapa_das_portas
from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    Aparelho,
    Barramento,
    Censo,
)
from hefesto_dualsense4unix.utils.maquina import FaceDeclarada, MapaDaMesa, PortaDeclarada


def _aparelho(caminho: str, mbps: float, classe: str, *, hub: bool = False) -> Aparelho:
    return Aparelho(
        no=f"/sys/{caminho}", nome_do_kernel=caminho, produto=f"Aparelho {caminho}",
        classe=classe, velocidade_mbps=mbps, e_hub=hub,
    )


_CENSO = Censo(
    aparelhos=(
        _aparelho("9-1", 480.0, "09", hub=True),
        _aparelho("9-1.1", 480.0, "09", hub=True),
        _aparelho("10-1", 5000.0, "09", hub=True),
        _aparelho("10-1.1", 5000.0, "09", hub=True),
        _aparelho("10-1.1.4", 5000.0, "ff"),
        _aparelho("9-1.1.2", 12.0, "03"),
        _aparelho("9-1.4", 12.0, "e0"),
    ),
    barramentos=(
        Barramento(no="/sys/usb9", nome_do_kernel="usb9", velocidade_mbps=480.0),
        Barramento(no="/sys/usb10", nome_do_kernel="usb10", velocidade_mbps=5000.0),
    ),
)

_MAPA = MapaDaMesa(
    faces=[FaceDeclarada(nome="Atrás", portas=["3"]),
           FaceDeclarada(nome="Hub", portas=["9", "11", "13"])],
    portas={
        "3": PortaDeclarada(caminho="9-1", nos=["usb9-port1", "usb10-port1"]),
        "9": PortaDeclarada(caminho="9-1.1.4", nos=["9-1.1-port4", "10-1.1-port4"]),
        "11": PortaDeclarada(caminho="9-1.1.2", nos=["9-1.1-port2", "10-1.1-port2"]),
        "13": PortaDeclarada(caminho="9-1.4", nos=["9-1-port4", "10-1-port4"]),
    },
)


def test_o_aparelho_do_lado_usb3_esta_na_entrada_dele() -> None:
    mesa = mapa_das_portas.mesa_do_motor(_MAPA, _CENSO).mesa
    assert motor.alocacao(mesa.mapa, mesa.leitura) == {
        "3": "9-1", "9": "10-1.1.4", "11": "9-1.1.2", "13": "9-1.4",
    }
    assert motor.sem_entrada(mesa) == [], "sobrou aparelho sem entrada"


def test_os_chips_do_hub_nao_sao_aparelho() -> None:
    mesa = mapa_das_portas.mesa_do_motor(_MAPA, _CENSO).mesa
    ids = {a.id for a in mesa.aparelhos}
    assert not ids & {"9-1.1", "10-1", "10-1.1"}, ids
    assert motor.caminho_do_hub(mesa) == "9-1"


def test_sem_o_mapa_nada_some() -> None:
    """Quem nunca mapeou continua vendo tudo o que o barramento tem: sem entrada"""
    mesa = mapa_das_portas.mesa_do_motor(MapaDaMesa(), _CENSO).mesa
    assert len(mesa.aparelhos) == len(_CENSO.conectados())
    assert all(mesa.leitura[a.id] == a.id for a in mesa.aparelhos)


def test_a_entrada_do_aparelho_usb3_nao_esta_livre() -> None:
    """26/09/2026: a Sugestão mandava o adaptador para a entrada do Wi-Fi."""
    assert "9" not in mapa_das_portas.portas_livres(_MAPA, _CENSO)
    assert mapa_das_portas.ocupante_de(_MAPA, "9", _CENSO) == "10-1.1.4"
    assert mapa_das_portas.ocupante_de(_MAPA, "11", _CENSO) == "9-1.1.2"
