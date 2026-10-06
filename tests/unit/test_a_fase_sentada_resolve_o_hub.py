"""Um toque em "Num hub" coloca o hub **e tudo que pende dele**."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from hefesto_dualsense4unix.integrations.censo_do_barramento import Aparelho, Censo
from hefesto_dualsense4unix.integrations.lugar_declarado import Recibo

RAIZ = "/mentira/bus/usb/devices"
USB3 = f"{RAIZ}/usb3"


class GravadorDeMentira:
    """O disco, em memória. Guarda o que foi mandado gravar e quantas vezes."""

    def __init__(self, *, recusa: bool = False) -> None:
        self.recusa = recusa
        self.chamadas: list[dict[str, Any]] = []

    def __call__(self, declaracao: Mapping[str, Any]) -> Recibo:
        self.chamadas.append(dict(declaracao))
        if self.recusa:
            return Recibo(False, "disco")
        return Recibo(True)


def _aparelho(
    nome: str,
    *,
    pai: str = "",
    e_hub: bool = False,
    e_raiz: bool = False,
    especie: str = "aparelho",
) -> Aparelho:
    return Aparelho(
        no=f"{USB3}/{nome}",
        nome_do_kernel=nome,
        pai=f"{USB3}/{pai}" if pai else "",
        e_hub=e_hub,
        e_raiz=e_raiz,
        especie=especie,
        busnum=3,
    )


def mesa_com_hub_e_tres_aparelhos() -> Censo:
    """O hub ``3-1`` e três aparelhos pendurados nele — quatro ao todo."""
    raiz = Aparelho(no=USB3, nome_do_kernel="usb3", e_hub=True, e_raiz=True, busnum=3)
    hub = _aparelho("3-1", pai="", e_hub=True, especie="hub")
    filhos = [
        _aparelho("3-1.1", pai="3-1", especie="adaptador Bluetooth"),
        _aparelho("3-1.2", pai="3-1", especie="DualSense"),
        _aparelho("3-1.3", pai="3-1", especie="receptor 2,4 GHz"),
    ]
    return Censo(aparelhos=(raiz, hub, *filhos))


def test_as_quatro_palavras_sao_as_que_ela_carimbou() -> None:
    """Verbatim do carimbo dela de 25/08/2026, às ~03h55, vendo o mockup."""
    from hefesto_dualsense4unix.interface.calibracao_das_entradas import FACES

    assert FACES == (
        "Frente do gabinete",
        "Atrás do gabinete",
        "Num hub ou extensão",
        "Na escrivaninha",
    )


def test_nenhuma_face_e_mais_longa_do_que_a_maior_que_ela_aprovou() -> None:
    """Nenhum rótulo de face passa de "Num hub ou extensão", a maior das quatro."""
    from hefesto_dualsense4unix.interface import calibracao_das_entradas as calibrar_entradas

    teto = len(calibrar_entradas.FACE_HUB)
    assert teto == 19, "a maior das quatro mudou de tamanho — reveja este teto"
    for face in calibrar_entradas.FACES:
        assert len(face) <= teto, (
            f"o rótulo {face!r} tem {len(face)} caracteres e o teto é {teto} "
            f"(o de {calibrar_entradas.FACE_HUB!r}). Acima disso ele quebra em "
            "duas linhas dentro do botão, que é o defeito que ela reportou em "
            "31/08/2026 — escolha um sinônimo mais curto."
        )


def test_nenhuma_face_diz_mesa() -> None:
    """A palavra saiu da tela em 05/09/2026, ordem de produto."""
    from hefesto_dualsense4unix.interface import calibracao_das_entradas as calibrar_entradas

    for face in calibrar_entradas.FACES:
        assert "mesa" not in face.lower(), (
            f"a face {face!r} diz a palavra que ela mandou tirar da tela em "
            "05/09/2026 — o termo é 'objeto' ou o sinônimo que couber"
        )


