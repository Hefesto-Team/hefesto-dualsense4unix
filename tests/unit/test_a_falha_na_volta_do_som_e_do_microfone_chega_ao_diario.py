"""A falha na volta do som e do microfone chega ao diário (A-FALHA-NA-VOLTA-DO-SOM-E-DO-MICROFONE).

Cada passo da volta tem o seu isolamento, o do laço do daemon (``_PassosDoLaco``): o que levanta
não cala os seguintes, soma ``poll.erro.<passo>`` no store e deixa UM aviso com a pilha por
episódio. A mesa dos dois laços é a real, com os passos dublados.

MORDIDAS: devolver o ``try`` único que engole em ``debug`` em ``BtMicSubsystem._volta`` ou em
``AltoFalanteSubsystem._reconciliar`` reprova o teste do laço dele (os seguintes não rodam e o
diário fica sem aviso).
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

import pytest
from structlog.testing import capture_logs

from hefesto_dualsense4unix.daemon import state_store
from hefesto_dualsense4unix.daemon.subsystems import alto_falante as af
from hefesto_dualsense4unix.daemon.subsystems import bt_mic
from hefesto_dualsense4unix.integrations import dualsense_bt_audio

PASSOS_DO_MIC = (
    "_esquecer_quem_saiu_da_mesa", "_soltar_os_que_o_usuario_desmarcou",
    "_reerguer_os_canais", "_reconciliar_o_cabo", "_reconciliar_as_pontes",
    "_refazer_quem_esperava_o_canal", "_aplicar_a_palavra_do_usuario", "_varrer_os_orfaos",
    "_renomear_os_canais_velhos", "_devolver_a_fonte_padrao",
)
PASSOS_DO_SOM = (
    "_marcar_os_do_radio", "_anotar_o_que_a_volta_viu", "_anotar_as_placas",
    "_anotar_o_pc_inteiro", "_casar_as_pontes",
)


class _Gerenciador:
    pontes: tuple[str, ...] = ()

    def __init__(self) -> None:
        self.voltas = 0

    def reconciliar(self, _alvos: Any) -> None:
        self.voltas += 1


def _roteiro(
    sub: Any, nomes: tuple[str, ...], quebra: str, monkeypatch: pytest.MonkeyPatch,
) -> dict[str, int]:
    chamados = dict.fromkeys(nomes, 0)

    def passo(nome: str) -> Callable[..., None]:
        def roda(*_a: Any) -> None:
            chamados[nome] += 1
            if nome == quebra:
                raise RuntimeError(f"{nome} caiu")
        return roda

    for nome in nomes:
        monkeypatch.setattr(sub, nome, passo(nome))
    return chamados


def _avisos(diario: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [e for e in diario if e.get("event") == "passo_do_laco_falhou"]


def _volta_do_mic(monkeypatch: pytest.MonkeyPatch, quebra: str) -> tuple[Any, Any, dict[str, int]]:
    monkeypatch.setattr(dualsense_bt_audio, "nos_dualsense_bluetooth", lambda: [])
    gerenciador = _Gerenciador()
    sub = bt_mic.BtMicSubsystem(gerenciador=gerenciador)
    sub._store = state_store.StateStore()
    return sub, gerenciador, _roteiro(sub, PASSOS_DO_MIC, quebra, monkeypatch)


def test_o_passo_do_microfone_que_falha_nao_cala_os_seguintes_e_chega_ao_diario(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-1911-A-FALHA-NA-VOLTA-CHEGA-AO-DIARIO: o microfone isola o passo e diz a falha."""
    sub, gerenciador, chamados = _volta_do_mic(monkeypatch, "_reconciliar_o_cabo")
    with capture_logs() as diario:
        for _ in range(3):
            sub._volta(gerenciador)
    assert set(chamados.values()) == {3}, f"um passo ficou sem rodar: {chamados}"
    avisos = _avisos(diario)
    assert len(avisos) == 1, "a mesma falha a cada volta inunda o diário"
    assert avisos[0]["log_level"] == "warning" and avisos[0]["passo"] == "bt_mic.cabo"
    assert isinstance(avisos[0]["exc_info"], RuntimeError), "o aviso saiu sem a pilha"
    assert sub._store.counter("poll.erro.bt_mic.cabo") == 3


def test_sem_a_lista_dos_nos_o_microfone_nao_esquece_nem_fecha_controle_nenhum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-1911-A-FALHA-NA-VOLTA-CHEGA-AO-DIARIO: a lista que falha não vira lista vazia."""
    sub, gerenciador, chamados = _volta_do_mic(monkeypatch, "")

    def sem_lista() -> list[Any]:
        raise OSError("pactl não respondeu")

    monkeypatch.setattr(dualsense_bt_audio, "nos_dualsense_bluetooth", sem_lista)
    with capture_logs() as diario:
        sub._volta(gerenciador)
    com_os_nos = {"_esquecer_quem_saiu_da_mesa", "_reconciliar_o_cabo", "_reconciliar_as_pontes",
                  "_varrer_os_orfaos"}
    assert {n for n, v in chamados.items() if v} == set(PASSOS_DO_MIC) - com_os_nos
    assert [a["passo"] for a in _avisos(diario)] == ["bt_mic.nos"]


def test_o_passo_do_som_que_falha_nao_cala_os_seguintes_e_chega_ao_diario(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-1911-A-FALHA-NA-VOLTA-CHEGA-AO-DIARIO: o som isola cada passo e diz a falha uma vez."""
    gerenciador = _Gerenciador()
    sub = af.AltoFalanteSubsystem(fonte_de_controles=lambda: [])
    sub._store = state_store.StateStore()
    chamados = _roteiro(sub, PASSOS_DO_SOM, "_anotar_as_placas", monkeypatch)
    with capture_logs() as diario:
        for _ in range(3):
            sub._reconciliar(gerenciador)
    assert set(chamados.values()) == {3}, f"um passo ficou sem rodar: {chamados}"
    assert gerenciador.voltas == 3, "o nó de som não foi reconciliado depois da falha"
    avisos = _avisos(diario)
    assert len(avisos) == 1, "a mesma falha a cada volta inunda o diário"
    assert avisos[0]["log_level"] == "warning" and avisos[0]["passo"] == "som.placas"
    assert isinstance(avisos[0]["exc_info"], RuntimeError), "o aviso saiu sem a pilha"
    assert sub._store.counter("poll.erro.som.placas") == 3


def test_a_falha_que_some_e_volta_e_dita_de_novo(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1911-A-FALHA-NA-VOLTA-CHEGA-AO-DIARIO: o passo que curou e quebra avisa de novo."""
    gerenciador = _Gerenciador()
    sub = af.AltoFalanteSubsystem(fonte_de_controles=lambda: [])
    sub._store = state_store.StateStore()
    _roteiro(sub, PASSOS_DO_SOM, "_anotar_as_placas", monkeypatch)
    with capture_logs() as diario:
        sub._reconciliar(gerenciador)
        sub._reconciliar(gerenciador)
        _roteiro(sub, PASSOS_DO_SOM, "", monkeypatch)
        sub._reconciliar(gerenciador)
        _roteiro(sub, PASSOS_DO_SOM, "_anotar_as_placas", monkeypatch)
        sub._reconciliar(gerenciador)
    assert len(_avisos(diario)) == 2
