"""O chip da mira liga só o giro: a inclinação saiu da mira, sem chave.

MORDIDAS: devolver o `"acelerometro": rota` ao `_handle_mira_set` reprova o disco; tirar o campo
da lista de `_a_secao_antiga_vira_a_da_mira_nova` faz o perfil antigo recusar; somar a gravidade ao
analógico no `aplicar_o_movimento` reprova a matriz dos quatro.
"""

from __future__ import annotations

import asyncio
import math
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core import roteador_de_movimento as rot
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.profiles import loader, schema
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    MatchAny,
    Profile,
    ProfileMovimentoConfig,
)
from hefesto_dualsense4unix.testing import FakeController
from tests.unit.test_a_mira_vale_nos_quatro import (
    _Mesa,
    P1,
    P2,
    P3,
    P4,
    PARADO,
    QUATRO,
)

_DIR = rot.DESTINO_ANALOGICO_DIREITO
_ESQ = rot.DESTINO_ANALOGICO_ESQUERDO


def _inclinado(graus: float) -> tuple[float, float, float]:
    r = math.radians(graus)
    return math.sin(r), math.cos(r), 0.0


@pytest.fixture
def perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _dir(ensure: bool = False) -> Path:
        return alvo

    monkeypatch.setattr(loader, "profiles_dir", _dir)
    return alvo


def _servidor(tmp_path: Path) -> IpcServer:
    loader.save_profile(Profile(name="Ensaio", match=MatchAny(type="any")))
    controle = FakeController(transport="usb")  # type: ignore[arg-type]
    controle.primary_uniq = P1  # type: ignore[attr-defined]
    daemon = Daemon(controller=controle)
    gerente = ProfileManager(controller=controle, store=daemon.store)
    servidor = IpcServer(
        controller=controle, store=daemon.store, profile_manager=gerente,
        socket_path=tmp_path / "m.sock", daemon=daemon,
    )
    daemon.store.set_active_profile("Ensaio")
    return servidor


def _set(servidor: IpcServer, **params: Any) -> dict[str, Any]:
    return asyncio.run(servidor._handlers["mira.set"](params))  # type: ignore[arg-type]


def test_acender_o_chip_deixa_o_acelerometro_fora_do_arranjo(
    perfis: Path, tmp_path: Path
) -> None:
    servidor = _servidor(tmp_path)
    corpo = _set(servidor, uniq=P2, ligada=True)
    assert corpo["status"] == "ok" and corpo["lado"] == _DIR
    arranjo = rot.da_peca(servidor.store, P2, rot.ativo(servidor.store))
    assert arranjo is not None and arranjo.destino == _DIR
    assert not hasattr(arranjo, "acelerometro")
    gravados = [p.read_text(encoding="utf-8") for p in perfis.glob("*.json")]
    assert gravados and not any("acelerometro" in g for g in gravados)
    assert _set(servidor, uniq=P2, ligada=True)["gravado"] is False, (
        "o chip aceso de novo escreveu um campo que a seção não guarda")


def test_mira_set_com_inclinacao_recusa_com_frase(perfis: Path, tmp_path: Path) -> None:
    servidor = _servidor(tmp_path)
    with pytest.raises(ValueError, match="inclinação saiu"):
        _set(servidor, uniq=P2, inclinacao=_ESQ)
    assert not loader.load_profile("Ensaio").controllers


def test_o_chip_nao_diz_mais_a_inclinacao_no_estado(perfis: Path, tmp_path: Path) -> None:
    servidor = _servidor(tmp_path)
    _set(servidor, uniq=P2, ligada=True)
    entradas: list[dict[str, Any]] = [{"uniq": P2}]
    servidor._merge_mira(entradas)
    assert "inclinacao" not in entradas[0]["mira"]
    assert "inclinacao_parada" not in entradas[0]["mira"]
    assert entradas[0]["mira"]["parada"] is False


def test_perfil_antigo_com_acelerometro_carrega_e_o_campo_nao_volta(
    perfis: Path,
) -> None:
    bruto = Profile(name="Velho", match=MatchAny(type="any")).model_dump(mode="json")
    antigo = {"destino": _DIR, "sensibilidade": 6, "eixo_horizontal": "yaw",
              "teto_graus_s": 220.0, "acelerometro": _DIR, "lado": _DIR}
    bruto["movimento"] = antigo
    bruto["controllers"] = {"aabbcc000002": {"movimento": antigo}}
    perfil = Profile.model_validate(bruto)
    assert perfil.movimento.destino == _DIR
    assert perfil.controllers["aabbcc000002"].movimento.destino == _DIR
    dump = perfil.model_dump(mode="json")
    assert "acelerometro" not in dump["movimento"]
    assert "acelerometro" not in dump["controllers"]["aabbcc000002"]["movimento"]


def test_a_secao_com_so_o_acelerometro_carrega_sem_nada_ligado() -> None:
    secao = ProfileMovimentoConfig.model_validate({"acelerometro": _ESQ})
    arranjo = rot.montar(secao)
    assert not arranjo.roteia
    assert not rot.virtual_aceso(arranjo)


def test_o_campo_do_sensor_por_controle_nao_e_a_rota() -> None:
    """O interruptor do acelerômetro do controle segue: é a leitura, não a inclinação na mira."""
    assert ControllerOverrides(sensores=schema.ControllerSensoresOverride(
        acelerometro=False)).sensores.acelerometro is False


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_inclinar_parado_nao_move_o_analogico_de_ninguem(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transporte: str
) -> None:
    pecas = {
        P1: {"destino": _DIR},
        P2: {"destino": _ESQ},
        P3: {"destino": _DIR, "inverter_horizontal": True},
        P4: {"destino": _ESQ, "sensibilidade_h": 10},
    }
    mesa = _Mesa(monkeypatch, tmp_path, transporte, pecas)
    for uniq in QUATRO:
        mesa.nos[uniq].giro = PARADO
        mesa.nos[uniq].acel = _inclinado(25.0)
    mesa.segundos(0.5)
    for uniq, pad in mesa.pads.items():
        assert pad.centro(), f"inclinar sem girar andou o analógico de {uniq}: {pad.analog[-1]}"


def test_o_giro_segue_cada_um_no_seu_lado(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pecas = {P1: {"destino": _DIR}, P2: {"destino": _ESQ}}
    mesa = _Mesa(monkeypatch, tmp_path, "bt", pecas, secundarios=(P2,))
    assert mesa.gira(P1, (0.0, 90.0, 0.0))["rx"] < 128
    assert mesa.gira(P2, (0.0, 90.0, 0.0))["lx"] < 128
