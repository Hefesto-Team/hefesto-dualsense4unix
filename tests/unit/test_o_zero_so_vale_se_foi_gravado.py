"""O ZERO SÓ VALE SE FOI GRAVADO.

A sprint: A-CALIBRAR-GRAVA-O-ZERO-DESCONTA-EM-TODO-CAMINHO-E-CABE-A-940-PX-01.

O defeito medido em 08/10/2026: `_medir_o_zero` ignorava o retorno de `gravar_os_zeros`.
Com o disco sem escrita a tela dizia «Calibrado» e `zero.guardado: true`, e o zero sumia no
próximo início do serviço, que carrega do disco.

O contrato: se a gravação falha, o zero em memória volta ao que era (nenhum, ou o anterior),
o estado é «parado» (o selo que já existe) e `guardado` reflete a memória restaurada. A chave
do sensor é o endereço, igual no cabo e no rádio, então vale do P1 ao P4.

MORDIDA (08/10/2026, devolvida): sem o teste do retorno, o estado volta a «pronto» e o zero
novo fica na memória; as duas primeiras réguas reprovam.

Endereços: faixa SINTÉTICA da casa (``aa:bb:cc``).
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core import roteador_de_movimento as rot

_P1, _P2 = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"
_GRAVIDADE = (0.0, 0.0, 1.0)
_VIES = (0.6, -2.4, 1.1)
_ANTES = (0.1, 0.2, 0.3)


class _Hub:
    """Os dois controles parados, cada um com o seu viés."""

    def velocidade_do_movimento(self, u: str) -> tuple[float, float, float] | None:
        return _VIES if u in (_P1, _P2) else None

    def aceleracao_do_movimento(self, u: str) -> tuple[float, float, float] | None:
        return _GRAVIDADE if u in (_P1, _P2) else None


def _servidor(casa: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """O `Daemon` e o `IpcServer` do produto, com a configuração em `casa`."""
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.testing import FakeController
    from hefesto_dualsense4unix.utils import session

    def _config_dir(ensure: bool = False) -> Path:
        if ensure:
            casa.mkdir(parents=True, exist_ok=True)
        return casa

    monkeypatch.setattr(session, "config_dir", _config_dir)
    monkeypatch.setattr(rot, "SEGUNDOS_DO_ZERO", 0.6)
    controle = FakeController(transport="bt")  # type: ignore[arg-type]
    daemon = Daemon(controller=controle)
    gerente = ProfileManager(controller=controle, store=daemon.store)
    servidor = IpcServer(controller=controle, store=daemon.store, profile_manager=gerente,
                         socket_path=tmp_path / "zero.sock", daemon=daemon)
    monkeypatch.setattr(servidor, "_garantir_sensor_hub", lambda: _Hub())
    return servidor


def _medir(servidor: Any, uniq: str) -> dict[str, Any]:
    """Pede a medida, espera ela acabar e devolve o `zero` do `state_full` do controle."""

    async def _a_medida() -> None:
        await servidor._handlers["motion.calibrate"]({"uniq": uniq})
        await asyncio.gather(*list(servidor._medidas_do_zero_em_voo))

    asyncio.run(_a_medida())
    entradas = [{"uniq": uniq}]
    servidor._merge_zero(entradas)
    zero: dict[str, Any] = entradas[0]["zero"]
    return zero


def _casa_sem_escrita(tmp_path: Path) -> Path:
    casa = tmp_path / "somente-leitura"
    casa.mkdir()
    casa.chmod(0o500)
    assert not os.access(casa, os.W_OK), "a bancada roda como root: o diretório escreve"
    return casa


def test_disco_sem_escrita_deixa_o_estado_parado_e_nenhum_zero(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O defeito: o estado ia a «pronto» e o zero ficava na memória, sem arquivo."""
    casa = _casa_sem_escrita(tmp_path)
    try:
        servidor = _servidor(casa, tmp_path, monkeypatch)
        zero = _medir(servidor, _P1)
        assert zero == {"estado": "parado", "guardado": False}, zero
        assert rot.zero_de(servidor.store, _P1) is None, (
            "o zero ficou na memória sem ter ido ao disco: some no próximo início")
        assert list(casa.iterdir()) == []
    finally:
        casa.chmod(0o700)


def test_disco_sem_escrita_devolve_o_zero_anterior_intacto(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O zero que já estava guardado não é trocado por um que não foi gravado."""
    casa = _casa_sem_escrita(tmp_path)
    try:
        servidor = _servidor(casa, tmp_path, monkeypatch)
        anterior = rot.ZeroDoControle(giro=_ANTES, gravidade=_GRAVIDADE)
        rot.definir_o_zero(servidor.store, _P1, anterior)
        zero = _medir(servidor, _P1)
        assert zero["estado"] == "parado", zero
        assert rot.zero_de(servidor.store, _P1) is anterior, "o zero anterior não voltou"
        assert zero["guardado"] is True, "o anterior continua valendo e a tela diz isso"
    finally:
        casa.chmod(0o700)


def test_o_zero_de_um_controle_nao_mexe_no_do_outro_quando_o_disco_falha(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """P1 a P4: a falha de um controle desfaz só o dele."""
    casa = _casa_sem_escrita(tmp_path)
    try:
        servidor = _servidor(casa, tmp_path, monkeypatch)
        do_p2 = rot.ZeroDoControle(giro=_ANTES, gravidade=_GRAVIDADE)
        rot.definir_o_zero(servidor.store, _P2, do_p2)
        _medir(servidor, _P1)
        assert rot.zero_de(servidor.store, _P2) is do_p2
        assert rot.zero_de(servidor.store, _P1) is None
    finally:
        casa.chmod(0o700)


def test_com_o_disco_bom_o_zero_vai_ao_arquivo_e_o_estado_e_pronto(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A cura não pode desligar o caminho que já funcionava."""
    casa = tmp_path / "config"
    servidor = _servidor(casa, tmp_path, monkeypatch)
    zero = _medir(servidor, _P1)
    assert zero == {"estado": "pronto", "guardado": True}, zero
    gravado = json.loads((casa / "zeros-dos-sensores.json").read_text("utf-8"))
    assert gravado["aabbcc000001"]["giro"] == pytest.approx(list(_VIES))
