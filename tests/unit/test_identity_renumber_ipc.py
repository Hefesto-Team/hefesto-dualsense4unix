"""IPC `identity.renumber` (ONDA-U/U2/U10) — compacta slots 1..N.

Contrato (fixado entre os agentes GUI/daemon do sprint):
  - método `identity.renumber`, args `{}`;
  - gate: só executa com `display_authority != 'game'`; com sessão de jogo
    aberta devolve `{ok: False, reason: "sessao_de_jogo_aberta"}` sem tocar
    nada;
  - compacta AMBOS os registros (DualSense em `identity.py` + externos em
    `external_identity.py`) para 1..N preservando a ORDEM RELATIVA atual,
    regrava `controllers.json` sob o `CONTROLLERS_FILE_LOCK` (NUMA-04) e
    re-pinta os LEDs;
  - retorno `{ok: True, renumbered: {uniq: novo_slot, ...}}` — R-15
    (auditoria 23/07): só as chaves que MUDARAM entram no mapa, e os
    CONECTADOS têm precedência sobre as reservas offline na faixa 1..N
    (ver `test_identity_numeracao_r14_r15.py`).

Cenário-mãe da triagem: 2 DualSense com slots {1, 4} (herdados da tempestade)
+ 1 externo no 5 → compacta para {1, 2, 3} preservando a ordem (o slot 1
continua na frente do 4, que continua na frente do externo).
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
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

#: MACs forjados (faixa aa:bb:cc — teste-guarda de anonimato; NUNCA 14:3a).
UNIQ_ROXO = "aabbcc000001"  # slot 1 (herdado)
UNIQ_BRANCO = "aabbcc000004"  # slot 4 (herdado — o "sony 4" da triagem)
MAC_EXTERNO = "aabbcc0000fe"  # slot 5 (externo)

BOOT = "boot-teste-renumber"


@dataclass
class _FakeDaemon:
    display_authority: str = "daemon"
    identity_registry: Any = None
    external_registry: Any = None


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``config_dir`` isolado + ``boot_id`` fixo nos DOIS registros."""
    from hefesto_dualsense4unix.utils import xdg_paths

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: BOOT)
    monkeypatch.setattr(ei_mod, "_read_boot_id", lambda: BOOT)
    return tmp_path


def _arquivo(tmp: Path) -> dict[str, Any]:
    return json.loads((tmp / "controllers.json").read_text(encoding="utf-8"))


def _server_com_registros(
    tmp_path: Path, *, authority: str = "daemon"
) -> tuple[IpcServer, ControllerIdentityRegistry, ExternalIdentityRegistry]:
    """Monta o cenário-mãe: DualSense em {1, 4} + externo em 5."""
    ds = ControllerIdentityRegistry()
    ds.slot_for(UNIQ_ROXO)  # 1
    # Força o slot 4 diretamente (simula a herança da tempestade — o slot_for
    # lazy não pularia direto pro 4 sem reservas intermediárias).
    ds._slots[UNIQ_BRANCO] = 4

    ext = ExternalIdentityRegistry()
    ext._slots[MAC_EXTERNO] = 5

    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    store.update_controller_state(
        ControllerState(
            battery_pct=100, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
    )
    manager = ProfileManager(controller=fc, store=store)
    daemon = _FakeDaemon(
        display_authority=authority, identity_registry=ds, external_registry=ext
    )
    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=tmp_path / "identity_renumber.sock",
        daemon=daemon,
    )
    return server, ds, ext


class TestGateSessaoDeJogo:
    @pytest.mark.asyncio
    async def test_recusa_com_jogo_aberto(self, isolated_config: Path) -> None:
        server, ds, ext = _server_com_registros(isolated_config, authority="game")
        resultado = await server._handle_identity_renumber({})
        assert resultado == {"ok": False, "reason": "sessao_de_jogo_aberta"}
        # Nada foi tocado — os slots herdados permanecem intactos.
        assert ds.snapshot() == {UNIQ_ROXO: 1, UNIQ_BRANCO: 4}
        assert ext.snapshot() == {MAC_EXTERNO: 5}

    @pytest.mark.asyncio
    async def test_executa_com_daemon(self, isolated_config: Path) -> None:
        server, _ds, _ext = _server_com_registros(isolated_config, authority="daemon")
        resultado = await server._handle_identity_renumber({})
        assert resultado["ok"] is True

    @pytest.mark.asyncio
    async def test_executa_com_unknown(self, isolated_config: Path) -> None:
        server, _ds, _ext = _server_com_registros(isolated_config, authority="unknown")
        resultado = await server._handle_identity_renumber({})
        assert resultado["ok"] is True


class TestCompactacaoGlobal:
    @pytest.mark.asyncio
    async def test_compacta_1_a_n_preservando_ordem(
        self, isolated_config: Path
    ) -> None:
        server, ds, ext = _server_com_registros(isolated_config)
        resultado = await server._handle_identity_renumber({})

        assert resultado["ok"] is True
        # R-15 (auditoria 23/07) — CONTRATO TROCADO DE PROPÓSITO: `renumbered`
        # passa a trazer só as chaves que MUDARAM. O roxo já estava no 1 e
        # continua no 1; contá-lo inflava o toast da GUI ("N controle(s)
        # renumerado(s)" conta as chaves), que é justamente a mentira do
        # achado `renumerar-inclui-desconectados`.
        assert resultado["renumbered"] == {
            UNIQ_BRANCO: 2,
            MAC_EXTERNO: 3,
        }
        # Cada registro recebeu só a fatia que é dele.
        assert ds.snapshot() == {UNIQ_ROXO: 1, UNIQ_BRANCO: 2}
        assert ext.snapshot() == {MAC_EXTERNO: 3}

    @pytest.mark.asyncio
    async def test_controllers_json_regravado(self, isolated_config: Path) -> None:
        server, ds, ext = _server_com_registros(isolated_config)
        # Save inicial (estado herdado) — simula o arquivo já existente.
        ds.sync_connected({UNIQ_ROXO, UNIQ_BRANCO})
        ext.sync_connected([MAC_EXTERNO])

        await server._handle_identity_renumber({})

        data = _arquivo(isolated_config)
        assert data["slots"] == {UNIQ_ROXO: 1, UNIQ_BRANCO: 2}
        assert data["externals"] == {MAC_EXTERNO: 3}

    @pytest.mark.asyncio
    async def test_sem_controle_nenhum_e_noop(self, isolated_config: Path) -> None:
        server, ds, ext = _server_com_registros(isolated_config)
        ds._slots.clear()
        ext._slots.clear()

        resultado = await server._handle_identity_renumber({})
        assert resultado == {"ok": True, "renumbered": {}}

    @pytest.mark.asyncio
    async def test_sem_registros_fiados_e_noop(self, isolated_config: Path) -> None:
        """Backend fake/daemon sem identity_registry/external_registry (None)
        — a mesma hermeticidade do resto do módulo, nunca levanta."""
        fc = FakeController(transport="usb")
        fc.connect()
        store = StateStore()
        manager = ProfileManager(controller=fc, store=store)
        daemon = _FakeDaemon()  # identity_registry/external_registry = None
        server = IpcServer(
            controller=fc,
            store=store,
            profile_manager=manager,
            socket_path=isolated_config / "sem_registro.sock",
            daemon=daemon,
        )
        resultado = await server._handle_identity_renumber({})
        assert resultado == {"ok": True, "renumbered": {}}

    @pytest.mark.asyncio
    async def test_ja_compacto_e_no_op_idempotente(
        self, isolated_config: Path
    ) -> None:
        """Rodar duas vezes seguidas não muda nada na segunda (já é 1..N).

        R-15 — CONTRATO TROCADO DE PROPÓSITO: antes as duas respostas eram
        IGUAIS (o plano inteiro voltava sempre), e a GUI toastava "3
        controle(s) renumerado(s)" numa passagem que não mexeu em nada. Agora
        a segunda volta VAZIA, e é o que faz o rodapé dizer "Numeração já
        estava compacta" (`home_actions._ok`, ramo `n == 0`).
        """
        server, ds, ext = _server_com_registros(isolated_config)
        primeiro = await server._handle_identity_renumber({})
        segundo = await server._handle_identity_renumber({})
        assert primeiro["renumbered"] == {UNIQ_BRANCO: 2, MAC_EXTERNO: 3}
        assert segundo["renumbered"] == {}
        assert ds.snapshot() == {UNIQ_ROXO: 1, UNIQ_BRANCO: 2}
        assert ext.snapshot() == {MAC_EXTERNO: 3}


class TestConcorrenciaTOCTOU:
    """Achado MEDIUM 2026-07-20 (corretora final): sem lock cobrindo o span
    inteiro ``snapshot()``→plano→``compact()``, um ``slot_for(assign=True)``
    concorrente (hotplug real sob o ``_io_lock`` do backend, ou o tick do
    ``ExternalLedSync``) podia ler o estado AINDA não-compactado e roubar o
    slot-alvo que o ``compact()`` estava prestes a devolver a outro
    controle — dois "Controle 1" simultâneos. Falha-sem: antes do fix
    (``lock_for_renumber`` + ``ExitStack`` em ``_handle_identity_renumber``),
    o ``slot_for`` concorrente disparado de dentro do ``snapshot()`` não
    tinha lock nenhum para esperar e terminava IMEDIATAMENTE (a `threading.
    Event` abaixo era setada bem antes do handler terminar).
    """

    @pytest.mark.asyncio
    async def test_slot_for_concorrente_bloqueia_ate_renumber_terminar(
        self, isolated_config: Path
    ) -> None:
        server, ds, ext = _server_com_registros(isolated_config)
        novo_uniq = "aabbcc009999"
        # Mesma fiação de produção (`lifecycle._wire_external_registry`): o
        # DualSense une os slots dos externos ao `used` — sem isto o teste
        # mediria uma colisão de wiring de fixture, não do TOCTOU.
        ds.set_external_reserve_provider(lambda: set(ext.snapshot().values()))

        resultado_thread: dict[str, int | None] = {}
        thread_terminou = threading.Event()
        original_snapshot = ds.snapshot

        def snapshot_com_hotplug_concorrente() -> dict[str, int]:
            # Disparado DE DENTRO do span que o fix agora protege — simula o
            # hotplug real acontecendo bem entre o snapshot() e o compact().
            copia = original_snapshot()

            def _hotplug() -> None:
                resultado_thread["slot"] = ds.slot_for(novo_uniq, assign=True)
                thread_terminou.set()

            threading.Thread(target=_hotplug, daemon=True).start()
            return copia

        ds.snapshot = snapshot_com_hotplug_concorrente  # type: ignore[method-assign]

        resultado = await server._handle_identity_renumber({})

        # Com o fix: o handler já terminou (soltou o lock) e mesmo assim a
        # thread do hotplug pode não ter rodado ainda (agendamento do SO) —
        # o que a asserção abaixo GARANTE é que ela só girou DEPOIS da
        # compactação, nunca no meio dela.
        assert thread_terminou.wait(timeout=1.0), "hotplug concorrente nunca rodou"
        assert resultado["ok"] is True

        slot_do_hotplug = resultado_thread["slot"]
        slots_compactados = set(ds.snapshot().values()) | set(ext.snapshot().values())
        # Nenhuma colisão: o hotplug só pode ter recebido um slot LIVRE em
        # relação ao estado JÁ compactado — nunca um dos slots-alvo que o
        # compact atribuiu (1, 2 ou 3 no cenário-mãe).
        assert slot_do_hotplug not in (resultado["renumbered"].values())
        assert slot_do_hotplug not in slots_compactados - {slot_do_hotplug}

    @pytest.mark.asyncio
    async def test_lock_for_renumber_bloqueia_slot_for_de_outra_thread(
        self, isolated_config: Path
    ) -> None:
        """Prova direta da trava: com `lock_for_renumber()` tomado, um
        `slot_for` de OUTRA thread fica bloqueado até a liberação."""
        _server, ds, _ext = _server_com_registros(isolated_config)
        novo_uniq = "aabbcc008888"

        thread_pegou_o_lock = threading.Event()
        thread_terminou = threading.Event()
        resultado_thread: dict[str, int | None] = {}

        def _concorrente() -> None:
            resultado_thread["slot"] = ds.slot_for(novo_uniq, assign=True)
            thread_pegou_o_lock.set()
            thread_terminou.set()

        with ds.lock_for_renumber():
            threading.Thread(target=_concorrente, daemon=True).start()
            # Enquanto o lock está tomado, a thread concorrente NÃO consegue
            # terminar (fica esperando o `with self._lock:` de `slot_for`).
            assert not thread_pegou_o_lock.wait(timeout=0.2)

        # Lock liberado: agora sim a thread concorrente conclui.
        assert thread_terminou.wait(timeout=1.0)
        assert resultado_thread["slot"] is not None


class TestHandlerWireado:
    def test_identity_renumber_no_dict_de_handlers(self, tmp_path: Path) -> None:
        """`identity.renumber` deve estar no dict `_handlers` (armadilha A-07)."""
        fc = FakeController(transport="usb")
        store = StateStore()
        manager = ProfileManager(controller=fc, store=store)
        server = IpcServer(
            controller=fc,
            store=store,
            profile_manager=manager,
            socket_path=tmp_path / "wireado.sock",
        )
        assert "identity.renumber" in server._handlers
