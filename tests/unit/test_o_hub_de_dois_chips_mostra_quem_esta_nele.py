"""O hub de dois chips mostra quem está nele — e só quem ela plugou.

26/09/2026, foto dela do mapa das conexões: *«dentro do hub identificou errado
são 4 dispositivos conectados»*. E a pergunta que veio junto: *«se o wifi não
foi detectado a webcam não seria também né»* — sim, qualquer aparelho USB 3.0.

A causa, medida na bancada dela: a entrada declara o caminho do lado USB 2.0
(``3-1.1.4``) e os nós dos DOIS lados do buraco (``3-1.1-port4`` e
``4-1.1-port4``), e o motor casava aparelho com entrada só pelo caminho. O
Wi-Fi que enumera no lado 3.0 (``4-1.1.4``) caía em «sem entrada», junto com o
chip de dentro do hub (``3-1.1``, ``4-1.1``) e o gêmeo 3.0 do próprio hub
(``4-1``) — nenhum dos três é coisa que ela plugou.

TUDO AQUI É DE MENTIRA E DE NINGUÉM: barramentos ``usb9``/``usb10`` e caminhos
``9-*``/``10-*``. A forma é a do hub dela: um plástico, dois chips, dois
barramentos.

A MORDIDA: devolva ao ``mesa_do_motor`` a leitura ``{id: id}`` (sem o
``_leitura_pelas_entradas``) — o Wi-Fi volta a «sem entrada» e os três chips
voltam a ser aparelho, e as duas réguas reprovam.
"""

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


#: O hub na entrada 3, os dois chips dele, e três aparelhos: o Wi-Fi no lado
#: 3.0 da entrada 9, o teclado na 11 e o adaptador na 13.
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
    """Quem nunca mapeou continua vendo tudo o que o barramento tem: sem entrada
    declarada não há como saber qual hub é chip de qual."""
    mesa = mapa_das_portas.mesa_do_motor(MapaDaMesa(), _CENSO).mesa
    assert len(mesa.aparelhos) == len(_CENSO.conectados())
    assert all(mesa.leitura[a.id] == a.id for a in mesa.aparelhos)
