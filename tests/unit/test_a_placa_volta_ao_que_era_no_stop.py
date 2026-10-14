"""A placa do cabo volta ao que o sistema tinha quando o daemon para.

O Hefesto enche a placa de quatro canais do DualSense no cabo (`garantir_a_placa_cheia`, desde
d61af1907), e o WirePlumber guarda os 100 %: com o daemon parado, o som da máquina no controle
saía ~24 dB mais alto. A escolha é a mais reversível: cada placa física volta aos por cento que
tinha antes da primeira escrita nossa; o endpoint do produto (`HEFESTO`) fica de fora.

MORDIDAS: arrancar o `setdefault` de `garantir_a_placa_cheia` reprova a devolução; arrancar a
chamada a `devolver_as_placas` do `stop` reprova `test_o_stop_devolve_as_placas_no_orcamento`.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as sub_mod
from hefesto_dualsense4unix.integrations import alto_falante_bt as afb
from tests.unit import pactl_json_de_mentira as pj

PLACA = "alsa_output.usb-Sony_DualSense_Wireless_Controller-00.HiFi__Speaker__sink"
ENDPOINT = "alsa_output.usb-HEFESTO_DualSense-00.analog-surround-40"


def _linha(porcentos: list[int]) -> str:
    canais = ("front-left", "front-right", "rear-left", "rear-right")
    partes = [
        f"{c}: {round(p * 655.36)} / {p:3d}% / 0.00 dB"
        for c, p in zip(canais, porcentos, strict=True)
    ]
    return "Volume: " + ",   ".join(partes)


class _Servidor:
    """O `pactl` de mentira: responde o volume de cada sink e aplica o `set-sink-volume`."""

    def __init__(self, volumes: dict[str, list[int]]) -> None:
        self.volumes = {k: list(v) for k, v in volumes.items()}
        self.escritas: list[list[str]] = []

    def __call__(self, argv: list[str]) -> str | None:
        if pj.e_lista_json(argv, "sinks"):
            longo = "".join(
                f"Sink #{i}\n\tName: {nome}\n\t{_linha(v)}\n"
                for i, (nome, v) in enumerate(self.volumes.items(), start=1)
            )
            return pj.json_do_longo(longo)
        if argv[:2] == ["pactl", "set-sink-volume"]:
            self.escritas.append(list(argv))
            self.volumes[argv[2]] = [int(p.rstrip("%")) for p in argv[3:7]]
            return ""
        return None


def test_a_placa_volta_aos_quarenta_que_o_sistema_tinha() -> None:
    servidor = _Servidor({PLACA: [40, 40, 40, 40]})
    assert afb.garantir_a_placa_cheia(PLACA, servidor) is True
    assert servidor.volumes[PLACA] == [100, 100, 100, 100]

    assert afb.devolver_as_placas(servidor) == [PLACA]
    assert servidor.volumes[PLACA] == [40, 40, 40, 40]
    assert afb.devolver_as_placas(servidor) == [], "o segundo stop não reescreve nada"


def test_vale_o_que_havia_antes_da_primeira_escrita() -> None:
    """Se alguém mexe depois, a placa enche de novo, e a devolução é a do começo."""
    servidor = _Servidor({PLACA: [35, 35, 35, 35]})
    afb.garantir_a_placa_cheia(PLACA, servidor)
    servidor.volumes[PLACA] = [70, 70, 70, 70]
    afb.garantir_a_placa_cheia(PLACA, servidor)
    afb.devolver_as_placas(servidor)
    assert servidor.volumes[PLACA] == [35, 35, 35, 35]


def test_a_placa_que_ja_estava_cheia_nao_tem_o_que_devolver() -> None:
    servidor = _Servidor({PLACA: [100, 100, 100, 100]})
    assert afb.garantir_a_placa_cheia(PLACA, servidor) is False
    assert afb.devolver_as_placas(servidor) == []
    assert servidor.escritas == []


def test_o_endpoint_do_produto_fica_de_fora() -> None:
    servidor = _Servidor({ENDPOINT: [40, 40, 0, 0]})
    afb.garantir_a_placa_cheia(ENDPOINT, servidor)
    assert afb.devolver_as_placas(servidor) == []
    assert servidor.volumes[ENDPOINT] == [100, 100, 100, 100]


def test_servidor_calado_nao_recebe_a_devolucao(monkeypatch: pytest.MonkeyPatch) -> None:
    servidor = _Servidor({PLACA: [40, 40, 40, 40]})
    afb.garantir_a_placa_cheia(PLACA, servidor)

    class _Calado:
        def mudo(self) -> bool:
            return True

    monkeypatch.setattr(afb, "_o_recuo", lambda: _Calado())
    assert afb.devolver_as_placas(servidor) == []


def test_o_stop_devolve_as_placas_no_orcamento(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[float | None] = []

    def _espiao(*_a: Any, **_k: Any) -> list[str]:
        chamadas.append(afb._FIM_DO_ORCAMENTO.get())
        return []

    monkeypatch.setattr(afb, "devolver_as_placas", _espiao)
    sub = sub_mod.AltoFalanteSubsystem(fonte_de_controles=lambda: [])
    asyncio.run(sub.stop())
    assert len(chamadas) == 1, "o stop não devolveu as placas"
    assert chamadas[0] is not None, "a devolução corre dentro do orçamento do stop"
