"""R-14 + R-15 (auditoria 23/07) — numeração honesta de controle.

Queixa da mantenedora que estes casos fecham: "aparecem dois 'player 2' e
dois 'player 1' em vez de 1-2-3-4".

R-14 — ``auto_player_colors`` acoplava TRÊS coisas num flag só (cor,
numeração e os externos), e a GUI o desligava por engano num clique de cor
com alvo "Todos", persistindo isso no perfil. Aqui: os dois eixos do
automático são independentes, a ATRIBUIÇÃO de slot nunca depende de flag, e
a aba Lightbar deixa de derrubar o automático quando sabe quem está
conectado (escreve override por-MAC, que vence a camada automática — D5).

R-15 — a expiração de slot era assimétrica (só o lado DualSense) e o
"Renumerar agora" compactava incluindo RESERVAS OFFLINE, virando no-op com
toast de sucesso. Aqui: os conectados descem para 1..N, a reserva vai para o
fim sem ser dropada, e o relatório traz só o que mudou.

Herméticos: ``config_dir`` monkeypatchado e ``boot_id`` fixo nos dois
registros; MACs sempre na faixa forjada ``aa:bb:cc:*`` (teste-guarda de
anonimato).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import external_identity as ei_mod
from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    ExternalIdentityRegistry,
)
from hefesto_dualsense4unix.daemon.subsystems.identity import (
    ControllerIdentityRegistry,
)
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController

#: MACs forjados (faixa aa:bb:cc — teste-guarda de anonimato).
UNIQ_BRANCO = "aabbcc000001"
UNIQ_ROXO = "aabbcc000002"
MAC_8BITDO = "aabbcc0000fe"

BOOT = "boot-teste-r15"


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from hefesto_dualsense4unix.utils import xdg_paths

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: BOOT)
    monkeypatch.setattr(ei_mod, "_read_boot_id", lambda: BOOT)
    return tmp_path


class _FakeDaemon:
    def __init__(self, ds: Any, ext: Any) -> None:
        self.display_authority = "daemon"
        self.identity_registry = ds
        self.external_registry = ext


def _server(tmp_path: Path, ds: Any, ext: Any) -> IpcServer:
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    store.update_controller_state(
        ControllerState(
            battery_pct=100, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
    )
    return IpcServer(
        controller=fc,
        store=store,
        profile_manager=ProfileManager(controller=fc, store=store),
        socket_path=tmp_path / "r15.sock",
        daemon=_FakeDaemon(ds, ext),
    )


# ---------------------------------------------------------------------------
# R-15 — "Renumerar agora" com reserva offline segurando a faixa baixa
# ---------------------------------------------------------------------------


class TestRenumerarNaoPresoNaReservaOffline:
    @pytest.mark.asyncio
    async def test_conectados_descem_para_1_a_n_e_reserva_vai_para_o_fim(
        self, isolated_config: Path
    ) -> None:
        """Cenário medido: 8BitDo DESLIGADO segurando o slot 1; os dois
        DualSense conectados em 2 e 3.

        Falha-sem: a compactação ordenava o mapa INTEIRO por slot, então o
        8BitDo offline continuava no 1 e os conectados continuavam em 2 e 3 —
        um no-op perfeito que ainda respondia "3 controle(s) renumerado(s)".
        """
        ds = ControllerIdentityRegistry()
        ds._slots[UNIQ_BRANCO] = 2
        ds._slots[UNIQ_ROXO] = 3
        ds.sync_connected({UNIQ_BRANCO, UNIQ_ROXO})

        ext = ExternalIdentityRegistry()
        ext._slots[MAC_8BITDO] = 1
        ext.sync_connected([])  # dormindo: só RESERVA

        server = _server(isolated_config, ds, ext)
        resultado = await server._handle_identity_renumber({})

        assert resultado["ok"] is True
        assert ds.snapshot() == {UNIQ_BRANCO: 1, UNIQ_ROXO: 2}
        # A reserva NÃO é dropada (promessa D2) — só perde a fila.
        assert ext.snapshot() == {MAC_8BITDO: 3}
        assert resultado["renumbered"] == {
            UNIQ_BRANCO: 1,
            UNIQ_ROXO: 2,
            MAC_8BITDO: 3,
        }

    @pytest.mark.asyncio
    async def test_ja_compacto_responde_vazio(self, isolated_config: Path) -> None:
        """Numeração já compacta = nenhum controle renumerado.

        Falha-sem: o retorno era o plano inteiro, e a GUI (que conta as
        chaves) toastava "2 controle(s) renumerado(s)" sem nada ter mudado.
        """
        ds = ControllerIdentityRegistry()
        ds.slot_for(UNIQ_BRANCO)
        ds.slot_for(UNIQ_ROXO)
        ds.sync_connected({UNIQ_BRANCO, UNIQ_ROXO})

        server = _server(isolated_config, ds, ExternalIdentityRegistry())
        resultado = await server._handle_identity_renumber({})
        assert resultado == {"ok": True, "renumbered": {}}

    @pytest.mark.asyncio
    async def test_registro_sem_snapshot_connected_degrada(
        self, isolated_config: Path
    ) -> None:
        """Dublê antigo (sem ``snapshot_connected``) não quebra o handler:
        todo mundo conta como conectado e o plano vira a compactação global do
        HEAD."""

        class _RegistroAntigo:
            def __init__(self) -> None:
                self.mapa = {MAC_8BITDO: 4}

            def snapshot(self) -> dict[str, int]:
                return dict(self.mapa)

            def compact(self, mapping: dict[str, int]) -> None:
                self.mapa.update(mapping)

        antigo = _RegistroAntigo()
        server = _server(isolated_config, None, antigo)
        resultado = await server._handle_identity_renumber({})
        assert resultado == {"ok": True, "renumbered": {MAC_8BITDO: 1}}
        assert antigo.mapa == {MAC_8BITDO: 1}


class TestSnapshotConnected:
    def test_dualsense_e_externos_expoem_os_conectados(
        self, isolated_config: Path
    ) -> None:
        """R-15: o ``_connected`` dos dois registros era escrito e NUNCA lido."""
        ds = ControllerIdentityRegistry()
        ds.slot_for(UNIQ_BRANCO)
        ds.slot_for(UNIQ_ROXO)
        ds.sync_connected({UNIQ_BRANCO})
        assert ds.snapshot_connected() == {UNIQ_BRANCO}
        assert set(ds.snapshot()) == {UNIQ_BRANCO, UNIQ_ROXO}  # reserva viva

        ext = ExternalIdentityRegistry()
        ext.slot_for(MAC_8BITDO, reserve=2)
        ext.sync_connected([MAC_8BITDO])
        assert ext.snapshot_connected() == {MAC_8BITDO}
        ext.sync_connected([])
        assert ext.snapshot_connected() == set()
        assert ext.snapshot() == {MAC_8BITDO: 3}


# ---------------------------------------------------------------------------
# R-14 — o piso dos externos não depende mais do flag de cor
# ---------------------------------------------------------------------------


class TestNumeracaoGlobalComAutoDesligado:
    def test_dualsense_ganha_slot_com_a_cor_desligada(
        self, isolated_config: Path
    ) -> None:
        """Regressão da colisão 8BitDo contra DualSense com ``fps.json`` ativo.

        Falha-sem: com ``auto_player_colors:false`` o provider devolvia None
        ANTES de atribuir, o registro DualSense ficava vazio, o piso dos
        externos (``_ds_reserve``) lia 0 e o 8BitDo reivindicava o slot 1 —
        que o DualSense também exibiria assim que o flag voltasse.
        """
        ds = ControllerIdentityRegistry()
        ds.configure(enabled=False)
        provider = id_mod.make_auto_output_provider(ds)
        ext = ExternalIdentityRegistry()
        ds.set_external_reserve_provider(lambda: set(ext.snapshot().values()))

        provider(UNIQ_BRANCO)
        provider(UNIQ_ROXO)
        piso = max(ds.snapshot().values())
        assert piso == 2
        assert ext.slot_for(MAC_8BITDO, reserve=piso) == 3
