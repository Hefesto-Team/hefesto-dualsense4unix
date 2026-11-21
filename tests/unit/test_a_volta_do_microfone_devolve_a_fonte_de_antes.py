"""A-VOLTA-DO-MICROFONE-DEVOLVE-A-FONTE-DE-ANTES-01: a volta devolve a entrada de antes.

O defeito, medido em 19/11/2026: com a webcam como entrada padrão e a captura da
placa-mãe antes da webcam na lista, ligar e desligar o microfone do controle deixava a
placa-mãe como padrão. A volta elegia a primeira captura que não é controle
(`outra_captura_elegivel`) e o `anterior` guardado só alimentava o diário.

O instrumento é o eleitor do produto sobre um `pactl` e um script dublados. O
dublê responde o que o `fix_wireplumber_default_source.sh` e o `doctor.sh`
respondem, e a primeira régua confere isso rodando os dois de verdade sobre a
mesma lista. Nada aqui toca o servidor de som de quem usa.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import eleicao_de_microfone as elm
from tests.unit.test_a_volta_do_microfone_nao_elege_controle import (
    HEADSET,
    MONITOR_HDMI,
    MONITOR_SPDIF,
    PLACA,
    ROXO,
    SCRIPT,
    VERMELHO,
    _canal,
    _Fonte,
    _PipeWire,
    _script_de_verdade,
)

WEBCAM = "alsa_input.usb-Webcam_C920-02.analog-stereo"


def _lista(*, com_headset: bool = False, webcam: bool = True) -> list[_Fonte]:
    """A placa-mãe antes da webcam, as duas com porta de captura usável."""
    fontes = [
        _Fonte(67, MONITOR_SPDIF),
        _Fonte(68, PLACA, porta=True),
        _Fonte(69, MONITOR_HDMI),
    ]
    if webcam:
        fontes.append(_Fonte(70, WEBCAM, porta=True))
    if com_headset:
        fontes.append(_Fonte(71, HEADSET, porta=True))
    fontes += [_Fonte(280, _canal(ROXO)), _Fonte(330, _canal(VERMELHO))]
    return fontes


@pytest.fixture()
def mesa(monkeypatch: pytest.MonkeyPatch) -> Callable[..., _PipeWire]:
    def _montar(fontes: list[_Fonte], ativo: str) -> _PipeWire:
        pw = _PipeWire(fontes=fontes, ativo=ativo)
        monkeypatch.setattr(elm, "_rodar", pw.rodar)
        monkeypatch.setattr(elm, "_script_do_wireplumber", lambda: SCRIPT)
        monkeypatch.setattr(elm, "SETTLE_PASSOS", 2)
        monkeypatch.setattr(elm, "SETTLE_PASSO_S", 0.0)
        return pw

    return _montar


def _ligar(eleitor: elm.EleitorDeMicrofone, uniq: str) -> None:
    canal = _canal(uniq)
    r = eleitor.eleger_por_uniq(uniq, fontes=[canal], uniqs_com_audio=[uniq])
    assert r.ok, r.motivo


def _desligar(eleitor: elm.EleitorDeMicrofone) -> elm.ResultadoDaEleicao:
    return eleitor.passar_o_padrao([], [], None)


def test_o_critério_dos_scripts_escolhe_a_placa_mãe_na_lista_do_defeito(tmp_path: Path) -> None:
    """O script e o doctor de verdade, sobre a lista do defeito, respondem a placa-mãe."""
    fontes = _lista()
    assert _script_de_verdade(tmp_path, fontes, "--outra-captura-elegivel") == PLACA


def test_a_volta_devolve_a_webcam_e_nao_a_placa_mae(mesa: Callable[..., _PipeWire]) -> None:
    """D-2011-A-VOLTA-DO-MICROFONE-DEVOLVE-A-FONTE-DE-ANTES: a webcam volta, não a placa-mãe."""
    pw = mesa(_lista(), WEBCAM)
    eleitor = elm.EleitorDeMicrofone()
    _ligar(eleitor, ROXO)
    assert pw.ativo == _canal(ROXO)

    r = _desligar(eleitor)

    assert r.ok and pw.ativo == WEBCAM
    assert pw.escritas == [_canal(ROXO), WEBCAM]


def test_a_entrada_trocada_no_meio_da_sessao_e_a_que_volta(
    mesa: Callable[..., _PipeWire],
) -> None:
    """MORDIDA: guardar uma vez por sessão devolve a webcam depois da troca para o headset."""
    pw = mesa(_lista(com_headset=True), WEBCAM)
    eleitor = elm.EleitorDeMicrofone()
    _ligar(eleitor, ROXO)
    _desligar(eleitor)
    assert pw.ativo == WEBCAM

    pw.ativo = HEADSET
    _ligar(eleitor, ROXO)
    _desligar(eleitor)

    assert pw.ativo == HEADSET


def test_de_controle_para_controle_a_memoria_continua_a_entrada_de_antes(
    mesa: Callable[..., _PipeWire],
) -> None:
    """A ida que parte de um canal nosso não vira o `anterior`."""
    pw = mesa(_lista(), WEBCAM)
    eleitor = elm.EleitorDeMicrofone()
    _ligar(eleitor, ROXO)
    _ligar(eleitor, VERMELHO)

    _desligar(eleitor)

    assert eleitor.anterior == WEBCAM and pw.ativo == WEBCAM


def test_o_canal_que_o_nome_nao_entrega_nao_vira_o_anterior(
    mesa: Callable[..., _PipeWire], monkeypatch: pytest.MonkeyPatch
) -> None:
    """MORDIDA: sem a identidade, o canal do J1 (nome sem marca de controle) vira o de antes."""
    canais = {ROXO: "bluez_input.canal_do_j1", VERMELHO: "bluez_input.canal_do_j2"}
    pw = mesa(_lista() + [_Fonte(290 + i, c) for i, c in enumerate(canais.values())], WEBCAM)
    monkeypatch.setattr(elm, "escolher_fonte", lambda _f, uniq, _a, _usb: canais.get(uniq))
    eleitor = elm.EleitorDeMicrofone()
    for uniq, canal in canais.items():
        assert eleitor.eleger_por_uniq(uniq, fontes=[canal], uniqs_com_audio=[uniq]).ok

    _desligar(eleitor)

    assert eleitor.anterior == WEBCAM and pw.ativo == WEBCAM


@pytest.mark.parametrize(
    "caso",
    ["sumiu-da-lista", "porta-sem-captura", "era-controle", "era-monitor"],
)
def test_anterior_que_nao_serve_cai_no_criterio_de_hoje(
    mesa: Callable[..., _PipeWire], caso: str
) -> None:
    """Fonte que sumiu, que não se sustenta, controle ou monitor: a primeira captura da máquina."""
    inicial = {"era-controle": _canal(VERMELHO), "era-monitor": MONITOR_HDMI}.get(caso, WEBCAM)
    pw = mesa(_lista(), inicial)
    eleitor = elm.EleitorDeMicrofone()
    _ligar(eleitor, ROXO)
    if caso == "sumiu-da-lista":
        pw.fontes = _lista(webcam=False)
    if caso == "porta-sem-captura":
        pw.fontes = [
            _Fonte(f.indice, f.nome, porta=False) if f.nome == WEBCAM else f for f in pw.fontes
        ]

    r = _desligar(eleitor)

    assert r.ok and pw.ativo == PLACA
    assert pw.ativo != WEBCAM


def test_a_leitura_do_padrao_que_e_controle_nao_vira_o_anterior(
    mesa: Callable[..., Any],
) -> None:
    """O padrão que já é canal de controle fica fora da memória."""
    mesa(_lista(), _canal(VERMELHO))
    eleitor = elm.EleitorDeMicrofone()

    assert eleitor.guardar_anterior() is None
