"""EXT-04 — identidade persistente dos EXTERNOS + LED no tick do daemon.

Cobre as três peças da cura da "morte do 8BitDo" (estudo 2026-07-18
§P3-BÔNUS):

1. `ExternalIdentityRegistry`: slot estável por uniq (menor livre ACIMA da
   reserva dos DualSense), reserva no disconnect (replug recupera o número),
   persistência POR BOOT no namespace `externals` do controllers.json — cada
   registro (DualSense/externos) preserva o namespace do outro.
2. `ExternalLedSync.tick()`: escreve LED SÓ em mudança (cache por-valor),
   com rate-limit por dispositivo e telemetria `external_led_written`.
3. Fiação do lifecycle: com backend fake (identity_registry None) NADA é
   fiado — hermeticidade (a suíte roda na máquina da mantenedora com um
   8BitDo REAL plugado).

MACs sempre na faixa forjada canônica (`aa:bb:cc:*`) — regra do teste-guarda
de anonimato.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import evdev_reader as er_mod
from hefesto_dualsense4unix.daemon.subsystems import external_identity as ei_mod
from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    LED_MIN_INTERVAL_SEC,
    ExternalIdentityRegistry,
    ExternalLedSync,
)

MAC_A = "aa:bb:cc:00:be:ef"
MAC_B = "aa:bb:cc:00:be:f0"
MAC_DS = "aa:bb:cc:00:00:01"
MAC_DS_B = "aa:bb:cc:00:00:02"
MAC_DS_C = "aa:bb:cc:00:00:03"

BOOT = "boot-atual"


@pytest.fixture(autouse=True)
def _hermetico(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """config_dir em tmp + boot_id fixo nos DOIS registros (mesmo arquivo)."""
    from hefesto_dualsense4unix.utils import xdg_paths

    target = tmp_path / "config"

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    monkeypatch.setattr(ei_mod, "_read_boot_id", lambda: BOOT)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: BOOT)
    return target


def _arquivo(tmp_path: Path) -> Path:
    return tmp_path / "config" / "controllers.json"


# --- registry: numeração e reserva -------------------------------------------


def test_slot_comeca_acima_da_reserva_dos_dualsense() -> None:
    r = ExternalIdentityRegistry()
    assert r.slot_for(MAC_A, reserve=2) == 3
    assert r.slot_for(MAC_B, reserve=2) == 4
    # Consulta repetida não renumera.
    assert r.slot_for(MAC_A, reserve=2) == 3


def test_disconnect_reserva_e_replug_recupera_o_numero() -> None:
    r = ExternalIdentityRegistry()
    assert r.slot_for(MAC_A, reserve=1) == 2
    r.sync_connected([])  # sumiu (BT dormiu) → slot vira RESERVA
    assert r.peek(MAC_A) == 2, "a reserva mantém o número do uniq"
    r.sync_connected([MAC_A])  # replug
    assert r.slot_for(MAC_A, reserve=1) == 2


def test_reserva_maior_depois_nao_renumera_slot_ja_atribuido() -> None:
    """Estabilidade vence: um 3º DualSense chegando DEPOIS não rouba o número
    do externo (fim do 'LED muda sozinho')."""
    r = ExternalIdentityRegistry()
    assert r.slot_for(MAC_A, reserve=1) == 2
    assert r.slot_for(MAC_A, reserve=5) == 2
    # Externo NOVO respeita a reserva nova.
    assert r.slot_for(MAC_B, reserve=5) == 6


def test_dualsense_novo_nao_colide_com_slot_de_externo() -> None:
    """EXT-04: numeração global ÚNICA no co-op misto. 2 DualSense (1,2) + 1
    externo (slot 3); um 3º DualSense conectando DEPOIS recebe 4 — nunca o 3
    do externo (que antes deixava dois 'Controle 3' acesos).

    Espelha `lifecycle._wire_external_registry`: o registro DualSense pula os
    slots já detidos pelos externos via o provider de reserva.
    """
    ds = id_mod.ControllerIdentityRegistry()
    ext = ExternalIdentityRegistry()
    ds.set_external_reserve_provider(lambda: set(ext.snapshot().values()))

    assert ds.slot_for(MAC_DS) == 1
    assert ds.slot_for(MAC_DS_B) == 2
    # Externo continua os DualSense: reserve=max(1,2)=2 → slot 3.
    assert ext.slot_for(MAC_A, reserve=2) == 3
    # 3º DualSense DEPOIS: menor livre próprio seria 3, mas o 3 é do externo.
    assert ds.slot_for(MAC_DS_C) == 4
    # Ninguém renumera: os slots já atribuídos permanecem.
    assert ds.slot_for(MAC_DS) == 1
    assert ds.slot_for(MAC_DS_B) == 2
    assert ext.peek(MAC_A) == 3


def test_peek_e_leitura_pura() -> None:
    r = ExternalIdentityRegistry()
    assert r.peek(MAC_A) is None
    assert r.snapshot() == {}, "peek jamais atribui slot"
    assert r.peek(None) is None
    assert r.peek("") is None


def test_identidade_sem_mac_e_volatil_nunca_persistida(tmp_path: Path) -> None:
    r = ExternalIdentityRegistry()
    assert r.slot_for("path:/dev/input/event9", reserve=0) == 1
    r.slot_for(MAC_A, reserve=0)
    r.sync_connected([MAC_A])  # persiste os sujos
    data = json.loads(_arquivo(tmp_path).read_text(encoding="utf-8"))
    assert list(data["externals"]) == [MAC_A.replace(":", "")]


# --- persistência: namespace `externals` no MESMO controllers.json -----------


def test_persistencia_por_boot_e_restauracao(tmp_path: Path) -> None:
    r = ExternalIdentityRegistry()
    r.slot_for(MAC_A, reserve=2)
    r.sync_connected([MAC_A])

    novo = ExternalIdentityRegistry()
    novo.load()
    assert novo.peek(MAC_A) == 3, "restart do daemon preserva o número"

    # Arquivo de OUTRO boot é sessão morta.
    data = json.loads(_arquivo(tmp_path).read_text(encoding="utf-8"))
    data["boot_id"] = "boot-antigo"
    _arquivo(tmp_path).write_text(json.dumps(data), encoding="utf-8")
    frio = ExternalIdentityRegistry()
    frio.load()
    assert frio.peek(MAC_A) is None


def test_namespaces_coexistem_no_mesmo_arquivo(tmp_path: Path) -> None:
    """O registro DualSense (`slots`) e o de externos (`externals`) escrevem o
    MESMO controllers.json e cada save preserva o namespace do outro."""
    ds = id_mod.ControllerIdentityRegistry()
    ds.slot_for(MAC_DS)
    ds.sync_connected([MAC_DS])  # grava `slots`

    ext = ExternalIdentityRegistry()
    ext.slot_for(MAC_A, reserve=1)
    ext.sync_connected([MAC_A])  # grava `externals` preservando `slots`

    data = json.loads(_arquivo(tmp_path).read_text(encoding="utf-8"))
    assert data["slots"] == {MAC_DS.replace(":", ""): 1}
    assert data["externals"] == {MAC_A.replace(":", ""): 2}

    # E o save do lado DualSense preserva `externals` (read-modify-write).
    ds2 = id_mod.ControllerIdentityRegistry()
    ds2.load()
    ds2.slot_for(MAC_DS)
    ds2.sync_connected([MAC_DS])
    data = json.loads(_arquivo(tmp_path).read_text(encoding="utf-8"))
    assert data["externals"] == {MAC_A.replace(":", ""): 2}
    assert data["slots"] == {MAC_DS.replace(":", ""): 1}


# --- ExternalLedSync: cache por-valor + rate-limit + telemetria ---------------


def _entry(uniq: str | None, hidraw: str | None, path: str) -> dict[str, Any]:
    return {
        "name": "Nintendo Co., Ltd. Pro Controller",
        "vid": "057e",
        "pid": "2009",
        "bus": "bluetooth",
        "uniq": uniq,
        "driver": "nintendo",
        "evdev_path": path,
        "hidraw": hidraw,
    }


@pytest.fixture()
def led_escritas(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int]]:
    """Captura `apply_player_number` (nunca toca o sysfs real)."""
    import hefesto_dualsense4unix.core.external_leds as leds_mod

    escritas: list[tuple[str, int]] = []
    monkeypatch.setattr(
        leds_mod,
        "apply_player_number",
        lambda hidraw, slot, *a, **k: (escritas.append((hidraw, slot)), True)[1],
    )
    return escritas


def _sync(
    monkeypatch: pytest.MonkeyPatch,
    inventario: list[dict[str, Any]],
    *,
    ds_slots: dict[str, int] | None = None,
) -> ExternalLedSync:
    monkeypatch.setattr(
        er_mod,
        "discover_external_gamepads",
        lambda: [dict(e) for e in inventario],
    )
    daemon = SimpleNamespace(
        identity_registry=SimpleNamespace(
            snapshot=lambda: dict(ds_slots or {})
        )
    )
    return ExternalLedSync(daemon, ExternalIdentityRegistry())


def test_tick_escreve_uma_vez_e_cacheia_por_valor(
    monkeypatch: pytest.MonkeyPatch, led_escritas: list[tuple[str, int]]
) -> None:
    """1º tick escreve o slot (continuando os DualSense); ticks seguintes SEM
    mudança não escrevem NADA — é o fim do bombardeio de subcomandos BT que
    matou o 8BitDo ao vivo (`joycon_enforce_subcmd_rate`)."""
    sync = _sync(
        monkeypatch,
        [_entry(MAC_A, "/dev/hidraw6", "/dev/input/event261")],
        ds_slots={"m1": 1, "m2": 2},
    )

    sync.tick(now=0.0)
    assert led_escritas == [("/dev/hidraw6", 3)]

    for i in range(1, 6):
        sync.tick(now=float(i * 10))
    assert led_escritas == [("/dev/hidraw6", 3)], (
        "poll repetido sem mudança não pode escrever LED de novo"
    )


def test_tick_rate_limita_por_dispositivo(
    monkeypatch: pytest.MonkeyPatch, led_escritas: list[tuple[str, int]]
) -> None:
    """Escrita que FALHOU (sem regra udev) não entra no cache — o retry
    respeita o rate-limit mínimo por dispositivo."""
    import hefesto_dualsense4unix.core.external_leds as leds_mod

    sync = _sync(monkeypatch, [_entry(MAC_A, "/dev/hidraw6", "/dev/input/event261")])
    tentativas: list[float] = []

    def falha(_hidraw: str, _slot: int, *a: Any, **k: Any) -> bool:
        tentativas.append(1.0)
        return False

    monkeypatch.setattr(leds_mod, "apply_player_number", falha)
    sync.tick(now=0.0)
    sync.tick(now=LED_MIN_INTERVAL_SEC / 2)  # dentro do rate-limit: nem tenta
    assert len(tentativas) == 1
    sync.tick(now=LED_MIN_INTERVAL_SEC + 0.1)  # fora: retry natural
    assert len(tentativas) == 2


def test_tick_replug_com_hidraw_novo_reescreve(
    monkeypatch: pytest.MonkeyPatch, led_escritas: list[tuple[str, int]]
) -> None:
    """Replug (nó hidraw novo) invalida o cache daquele device: o LED renasce
    apagado no hardware e o tick o reescreve — com o MESMO slot (reserva)."""
    inventario = [_entry(MAC_A, "/dev/hidraw6", "/dev/input/event261")]
    sync = _sync(monkeypatch, inventario)
    sync.tick(now=0.0)
    assert led_escritas == [("/dev/hidraw6", 1)]

    # some (BT dormiu)...
    monkeypatch.setattr(er_mod, "discover_external_gamepads", lambda: [])
    sync.tick(now=10.0)
    # ...e volta noutro nó.
    monkeypatch.setattr(
        er_mod,
        "discover_external_gamepads",
        lambda: [_entry(MAC_A, "/dev/hidraw9", "/dev/input/event300")],
    )
    sync.tick(now=20.0)
    assert led_escritas == [("/dev/hidraw6", 1), ("/dev/hidraw9", 1)], (
        "mesmo slot (reserva por uniq), nó novo reescrito"
    )


def test_tick_telemetria_external_led_written(
    monkeypatch: pytest.MonkeyPatch, led_escritas: list[tuple[str, int]]
) -> None:
    """EXT-04 item 3c: cada escrita EFETIVA loga `external_led_written` com
    slot e uniq (antes era silencioso via contextlib.suppress)."""
    eventos: list[tuple[str, dict[str, Any]]] = []

    class _SpyLogger:
        def info(self, evento: str, **kw: Any) -> None:
            eventos.append((evento, kw))

        def debug(self, *_a: Any, **_kw: Any) -> None: ...

        def warning(self, *_a: Any, **_kw: Any) -> None: ...

    monkeypatch.setattr(ei_mod, "logger", _SpyLogger())
    sync = _sync(
        monkeypatch,
        [_entry(MAC_A, "/dev/hidraw6", "/dev/input/event261")],
        ds_slots={"m1": 1},
    )
    sync.tick(now=0.0)

    escritos = [kw for ev, kw in eventos if ev == "external_led_written"]
    assert escritos == [{"slot": 2, "uniq": MAC_A, "hidraw": "/dev/hidraw6"}]


def test_externo_sem_mac_gui_bate_com_led_do_tick(
    monkeypatch: pytest.MonkeyPatch, led_escritas: list[tuple[str, int]]
) -> None:
    """Achado EXT-04: um externo SEM MAC exibia na GUI número != do LED aceso
    quando havia slot de DualSense RESERVADO. O tick numera por
    `path:<evdev_path>` com reserve=max(reservas DualSense); o IPC precisa
    consultar o registry pela MESMA identidade (não por uniq=None → posicional).

    Cenário: 2 DualSense {A:1,B:2}, A desconectou (slot 1 RESERVADO, snapshot
    inclui reservas) mas B segue conectado; 1 externo sem MAC. O LED acende
    player 3; a GUI (que conta só os CONECTADOS) exibia 'Controle 2'.
    """
    import hefesto_dualsense4unix.daemon.ipc_handlers as ih_mod

    # A desconectou → slot 1 fica RESERVADO no snapshot; só B conectado.
    ds_snapshot = {"dsa": 1, "dsb": 2}
    inventario = [_entry(None, "/dev/hidraw6", "/dev/input/event261")]
    sync = _sync(monkeypatch, inventario, ds_slots=ds_snapshot)

    sync.tick(now=0.0)
    # LED aceso como player 3 (reserve=max(1,2)=2 → menor livre acima = 3).
    assert led_escritas == [("/dev/hidraw6", 3)]

    # IPC: a GUI conta só os DualSense CONECTADOS (1 = B). Sem o fix,
    # peek(None) → None → posicional 1+0+1=2, divergindo do LED. Com o fix,
    # peek pela MESMA identidade path:... → 3.
    monkeypatch.setattr(ih_mod, "_steam_hidraw_holders", lambda: {})
    inv = ih_mod._external_inventory(
        dualsense_count=1, slot_resolver=sync._registry.peek
    )
    assert inv[0]["player_slot"] == 3, "GUI deve exibir o MESMO número do LED"


def test_tick_enumeracao_quebrada_nao_derruba(
    monkeypatch: pytest.MonkeyPatch, led_escritas: list[tuple[str, int]]
) -> None:
    def explode() -> list[dict[str, Any]]:
        raise RuntimeError("evdev sumiu")

    monkeypatch.setattr(er_mod, "discover_external_gamepads", explode)
    sync = ExternalLedSync(SimpleNamespace(), ExternalIdentityRegistry())
    sync.tick(now=0.0)  # não levanta
    assert led_escritas == []


# --- fiação do lifecycle: hermeticidade com backend fake ----------------------


def test_wire_external_registry_exige_identity_registry() -> None:
    """Backend fake (identity_registry None) → nada de externos: nenhuma
    enumeração de /dev/input nem LED em teste/smoke (hermeticidade)."""
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.testing import FakeController

    daemon = Daemon(
        controller=FakeController(transport="usb"),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )
    assert daemon.identity_registry is None
    daemon._wire_external_registry()
    assert daemon.external_registry is None
    assert daemon._external_led_sync is None


async def test_sync_external_leds_e_noop_sem_fiacao() -> None:
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.testing import FakeController

    daemon = Daemon(
        controller=FakeController(transport="usb"),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )
    # Sem executor e sem fiação: precisa ser no-op silencioso.
    await daemon._sync_external_leds()
