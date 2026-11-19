"""O-OUVIDO-DO-JOGO-OUVE-O-SOM-E-NAO-A-HAPTICA-01: o ouvido grava o som do jogo, e não a háptica.

No modo DualSense o processo do jogo abre dois fluxos: o som, para a TV, e a háptica de quatro
canais, para o endpoint ``HEFESTO<marca>`` de cada controle. A procura descarta o que vai a um
endpoint da háptica e prefere o que vai à saída padrão; a surdez diz o motivo.

A MORDIDA (executada, com o md5 conferido na volta): sem o filtro do destino, a procura volta
ao serial 900 (a háptica de P1) → ``test_com_a_haptica_listada_antes_o_ouvido_acha_o_som``; a
lista das saídas que não veio lida como vazia → ``test_sem_saber_os_destinos_a_procura_nao_chuta``.
"""
from __future__ import annotations

from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.integrations import quem_o_jogo_le as q
from hefesto_dualsense4unix.integrations import transiente_do_jogo as tj
from tests.unit import pactl_json_de_mentira as pj
from tests.unit.test_o_diario_diz_o_que_o_corpo_tocou import _Alto, _passo

PID = 4242
TV = "alsa_output.pci-0000_00_1f.3.hdmi-stereo"
CONTROLES = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02")


def _servidor(fluxos: list[tuple[int, int, int]], padrao: str = TV) -> Any:
    """``fluxos`` = (índice, sink, serial), todos do processo do jogo."""
    nos = [pj.no(50, TV)] + [
        pj.no(60 + n, eh.nome_do_endpoint(u), formato="float32le 4ch 48000Hz")
        for n, u in enumerate(CONTROLES)
    ]

    def rodar(argv: list[str]) -> str | None:
        if pj.e_lista_json(argv, "sinks"):
            return pj.texto(*nos)
        if pj.e_lista_json(argv, "sink-inputs"):
            return pj.texto(*(
                pj.fluxo(i, sink, props={
                    "application.process.id": str(PID), "node.name": "jogo",
                    "object.serial": str(serial),
                })
                for i, sink, serial in fluxos))
        if list(argv[:2]) == ["pactl", "get-default-sink"]:
            return f"{padrao}\n"
        return ""

    return rodar


@pytest.fixture
def jogo(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(q, "pids_de_jogo", lambda *_a, **_k: {PID})

    def montar(fluxos: list[tuple[int, int, int]], padrao: str = TV) -> None:
        monkeypatch.setattr(af, "_rodar", _servidor(fluxos, padrao))

    return montar


def test_com_a_haptica_listada_antes_o_ouvido_acha_o_som(jogo: Any) -> None:
    """D-1911-O-OUVIDO-DO-JOGO-OUVE-SO-O-SOM: a háptica de cada controle fica fora da procura."""
    jogo([(1, 60, 900), (2, 61, 901), (3, 50, 902)], padrao="")
    achado = tj.achar_o_fluxo_do_jogo()
    assert isinstance(achado, tj.FluxoDoJogo)
    assert achado.serial == 902, "o ouvido gravaria a vibração do próprio jogo"
    assert achado.fluxos == 3


def test_so_com_a_haptica_nao_ha_som_a_ouvir(jogo: Any) -> None:
    """D-1911-O-OUVIDO-DO-JOGO-OUVE-SO-O-SOM: só a háptica é «só háptica», e não o som."""
    jogo([(1, 60, 900), (2, 61, 901)])
    assert tj.achar_o_fluxo_do_jogo() == tj.SemFluxo(tj.MOTIVO_SO_HAPTICA, 2)
    jogo([])
    assert tj.achar_o_fluxo_do_jogo() == tj.SemFluxo(tj.MOTIVO_SEM_FLUXO, 0)


def test_sem_saber_os_destinos_a_procura_nao_chuta(
    jogo: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-1911-O-OUVIDO-DO-JOGO-OUVE-SO-O-SOM: sem a lista das saídas, «não sei», e não a háptica."""
    jogo([(1, 60, 900), (3, 50, 902)], padrao="")
    rodar = af._rodar
    monkeypatch.setattr(
        af, "_rodar", lambda argv: None if pj.e_lista_json(argv, "sinks") else rodar(argv))
    assert tj.achar_o_fluxo_do_jogo() is None, "o ouvido gravaria a háptica sem saber o destino"


def test_entre_os_sons_vale_o_da_saida_padrao(jogo: Any) -> None:
    """D-1911-O-OUVIDO-DO-JOGO-OUVE-SO-O-SOM: o som que vai à saída padrão vem antes."""
    outra = "alsa_output.usb-fone"
    jogo([(1, 70, 800), (2, 50, 801)], padrao=TV)
    achado = tj.achar_o_fluxo_do_jogo()
    assert isinstance(achado, tj.FluxoDoJogo) and achado.serial == 801
    jogo([(1, 70, 800), (2, 50, 801)], padrao=outra)
    achado = tj.achar_o_fluxo_do_jogo()
    assert isinstance(achado, tj.FluxoDoJogo) and achado.serial == 800


def test_o_surdo_diz_o_motivo_e_os_fluxos(jogo: Any) -> None:
    """D-1911-O-OUVIDO-DO-JOGO-OUVE-SO-O-SOM: a surdez leva o motivo e quantos fluxos havia."""
    jogo([(1, 60, 900)])
    agora = [0.0]
    ouvido = tj.OuvidoDoJogo(lambda: True, relogio=lambda: agora[0])
    passo = _passo(_Alto())
    passo.jogo = True
    passo.motor.ouvido = ouvido
    passo.motor.ligado = True
    ouvido.uma_volta()
    agora[0] = 1000.0
    with structlog.testing.capture_logs() as linhas:
        passo.andar_o_diario(agora[0])
    (surdo,) = [x for x in linhas if x["event"] == "tato_ouvido_surdo"]
    assert (surdo["motivo"], surdo["fluxos"]) == (tj.MOTIVO_SO_HAPTICA, 1)
    jogo([])
    ouvido.uma_volta()
    assert ouvido.por_que_surdo() == (tj.MOTIVO_SEM_FLUXO, 0)
