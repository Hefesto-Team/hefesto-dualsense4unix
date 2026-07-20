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

GYRO-02 (2026-07-19): `ExternalImuEnabler` (enable-IMU do Nintendo Pro REAL,
FASEADO — só USB) tem seção própria mais abaixo.

MACs sempre na faixa forjada canônica (`aa:bb:cc:*`) — regra do teste-guarda
de anonimato. O OUI real do Nintendo (`E0:F6:B5`) NUNCA aparece aqui — os
testes de `ExternalImuEnabler` monkeypatcham `NINTENDO_REAL_OUI` para uma
faixa forjada (`aabbcc`) e usam os MESMOS MACs sintéticos do arquivo.
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
    ExternalImuEnabler,
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


# --- registry: compact (ONDA-U/U2/U10) ---------------------------------------


def test_compact_reescreve_so_as_chaves_do_mapping() -> None:
    """`compact` (`identity.renumber`) — reatribuição EXPLÍCITA, não a lazy.

    Falha-sem: `ExternalIdentityRegistry` no HEAD não tem `compact` nenhum.
    """
    r = ExternalIdentityRegistry()
    r.slot_for(MAC_A, reserve=0)  # slot 1
    r.slot_for(MAC_B, reserve=0)  # slot 2
    key_a, key_b = MAC_A.replace(":", ""), MAC_B.replace(":", "")
    r.compact({key_a: 5, "aabbcc00ff00": 9})  # chave fora do registro ignorada
    assert r.snapshot() == {key_a: 5, key_b: 2}


def test_compact_persiste_no_disco_quando_muda(tmp_path: Path) -> None:
    r = ExternalIdentityRegistry()
    r.slot_for(MAC_A, reserve=0)
    r.sync_connected([MAC_A])  # save inicial
    key_a = MAC_A.replace(":", "")
    r.compact({key_a: 7})
    data = json.loads(_arquivo(tmp_path).read_text(encoding="utf-8"))
    assert data["externals"] == {key_a: 7}


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
    authority: str | None = None,
    auto_enabled: bool = True,
) -> ExternalLedSync:
    """``authority`` ausente preserva o default 'unknown' (sem fiação, NUMA-03)."""
    monkeypatch.setattr(
        er_mod,
        "discover_external_gamepads",
        lambda: [dict(e) for e in inventario],
    )
    identity_registry = SimpleNamespace(
        snapshot=lambda: dict(ds_slots or {}), auto_enabled=auto_enabled
    )
    daemon_kwargs: dict[str, Any] = {"identity_registry": identity_registry}
    if authority is not None:
        daemon_kwargs["display_authority"] = authority
    daemon = SimpleNamespace(**daemon_kwargs)
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


# --- NUMA-03.4: autoridade de exibição modula o tick --------------------------


def test_sem_fiacao_authority_ausente_e_byte_identico_ao_head(
    monkeypatch: pytest.MonkeyPatch, led_escritas: list[tuple[str, int]]
) -> None:
    """`daemon` sem `display_authority` (backend velho/FakeController) degrada
    para 'unknown' — o cache por-valor sozinho decide, IGUAL a HEAD."""
    sync = _sync(monkeypatch, [_entry(MAC_A, "/dev/hidraw6", "/dev/input/event261")])
    sync.tick(now=0.0)
    assert led_escritas == [("/dev/hidraw6", 1)]
    sync.tick(now=10.0)
    assert led_escritas == [("/dev/hidraw6", 1)], "sem mudança, sem escrita"


def test_daemon_repinta_escritor_estrangeiro_detectado_por_classe_led(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, led_escritas: list[tuple[str, int]]
) -> None:
    """NUMA-03.4(a): sob 'daemon', o tick RE-LÊ o padrão físico (classe LED,
    zero subcomando BT) antes do skip por-valor. Um escritor estrangeiro (o
    'player 1+3' que a Steam pinta, padrão NÃO-canônico) é detectado e
    repintado DENTRO do rate-limit de 2s."""
    import hefesto_dualsense4unix.core.external_leds as leds_mod

    inst = "0003:057E:2009.000E"
    leds_root = tmp_path / "leds"
    for i in range(1, 5):
        node = leds_root / f"{inst}:green:player-{i}"
        node.mkdir(parents=True)
        (node / "brightness").write_text("0", encoding="ascii")
    monkeypatch.setattr(leds_mod, "LEDS_ROOT", str(leds_root))
    monkeypatch.setattr(leds_mod, "hid_instance_for_hidraw", lambda h: inst)

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
        authority="daemon",
    )
    sync.tick(now=0.0)
    assert led_escritas == [("/dev/hidraw6", 1)]

    # Escritor estrangeiro pinta um padrão com BURACO por fora (1+3 aceso).
    for i, aceso in enumerate(["1", "0", "1", "0"], start=1):
        (leds_root / f"{inst}:green:player-{i}" / "brightness").write_text(
            aceso, encoding="ascii"
        )

    sync.tick(now=0.5)  # detecta, mas dentro do rate-limit: NÃO escreve ainda
    assert led_escritas == [("/dev/hidraw6", 1)], "<2s não repinta"

    sync.tick(now=2.1)  # fora do rate-limit: repinta
    assert led_escritas == [("/dev/hidraw6", 1), ("/dev/hidraw6", 1)]
    repintados = [kw for ev, kw in eventos if ev == "external_led_repintado"]
    assert repintados == [{"uniq": MAC_A, "intruso": -1}]


def test_daemon_leitura_falha_e_skip_como_hoje(
    monkeypatch: pytest.MonkeyPatch, led_escritas: list[tuple[str, int]]
) -> None:
    """Nó sumido/ilegível (BT dormiu) NUNCA vira falso estrangeiro — skip,
    igual ao comportamento de hoje (veto dos juízes, NUMA-03.1/.4)."""
    import hefesto_dualsense4unix.core.external_leds as leds_mod

    monkeypatch.setattr(leds_mod, "hid_instance_for_hidraw", lambda h: None)
    sync = _sync(
        monkeypatch,
        [_entry(MAC_A, "/dev/hidraw6", "/dev/input/event261")],
        authority="daemon",
    )
    sync.tick(now=0.0)
    assert led_escritas == [("/dev/hidraw6", 1)]
    sync.tick(now=10.0)
    assert led_escritas == [("/dev/hidraw6", 1)], "sem leitura, sem repaint"


def test_authority_game_numera_device_novo_mas_nao_corrige_cacheado(
    monkeypatch: pytest.MonkeyPatch, led_escritas: list[tuple[str, int]]
) -> None:
    """NUMA-03.4(b): sob 'game'/'unknown' um device já cacheado NÃO é
    corrigido (externos não são disputados em jogo) — mas o 8BitDo chegando
    NO MEIO do jogo (device NOVO) ainda recebe o número 1x."""
    sync = _sync(
        monkeypatch,
        [_entry(MAC_A, "/dev/hidraw6", "/dev/input/event261")],
        authority="game",
    )
    sync.tick(now=0.0)
    assert led_escritas == [("/dev/hidraw6", 1)]

    # Divergência simulada no cache do device JÁ numerado — não deve mexer.
    sync._last_value[(MAC_A, "/dev/hidraw6")] = 99

    monkeypatch.setattr(
        er_mod,
        "discover_external_gamepads",
        lambda: [
            _entry(MAC_A, "/dev/hidraw6", "/dev/input/event261"),
            _entry(MAC_B, "/dev/hidraw7", "/dev/input/event262"),
        ],
    )
    sync.tick(now=5.0)
    assert led_escritas == [("/dev/hidraw6", 1), ("/dev/hidraw7", 2)], (
        "A cacheado (mesmo com cache divergente) fica intocado; B novo numera"
    )


def test_queda_game_para_daemon_reacende_incondicionalmente(
    monkeypatch: pytest.MonkeyPatch, led_escritas: list[tuple[str, int]]
) -> None:
    """NUMA-03.4(d): a transição `game|unknown -> daemon` re-arma os caches —
    o tick seguinte reacende os slots do daemon SEM esperar o rate-limit
    normal (não dá pra confiar no que ficou aceso sem disputa)."""
    sync = _sync(
        monkeypatch,
        [_entry(MAC_A, "/dev/hidraw6", "/dev/input/event261")],
        authority="game",
    )
    sync.tick(now=0.0)
    assert led_escritas == [("/dev/hidraw6", 1)]

    sync.tick(now=0.1)  # ainda 'game': cacheado, sem disputa — nada muda
    assert led_escritas == [("/dev/hidraw6", 1)]

    sync._daemon.display_authority = "daemon"
    sync.tick(now=0.2)  # queda -> daemon: re-arm reacende MESMO <2s depois
    assert led_escritas == [("/dev/hidraw6", 1), ("/dev/hidraw6", 1)]


def test_auto_player_colors_off_para_de_escrever_e_limpa_cache(
    monkeypatch: pytest.MonkeyPatch, led_escritas: list[tuple[str, int]]
) -> None:
    """NUMA-03.4(c): simetria com o provider DualSense — OFF para de afirmar
    (zero escritas) e limpa o cache; achado ao vivo sem o fix: o externo
    continuava aceso com o DualSense já apagado. OFF->ON reescreve."""
    sync = _sync(monkeypatch, [_entry(MAC_A, "/dev/hidraw6", "/dev/input/event261")])
    sync.tick(now=0.0)
    assert led_escritas == [("/dev/hidraw6", 1)]

    sync._daemon.identity_registry.auto_enabled = False
    sync.tick(now=1.0)
    assert led_escritas == [("/dev/hidraw6", 1)], "OFF: zero escritas novas"
    assert sync._last_value == {}, "cache limpo enquanto OFF"

    sync._daemon.identity_registry.auto_enabled = True
    sync.tick(now=1.5)
    assert led_escritas == [("/dev/hidraw6", 1), ("/dev/hidraw6", 1)], (
        "OFF->ON reescreve"
    )


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


# ---------------------------------------------------------------------------
# GYRO-02 — ExternalImuEnabler: enable-IMU do Nintendo Pro REAL (FASEADO)
# ---------------------------------------------------------------------------

#: MAC com OUI forjado (aabbcc, mesma faixa de MAC_A/MAC_B) usado como
#: "Nintendo real" nestes testes — o teste monkeypatcha `NINTENDO_REAL_OUI`
#: para esta MESMA faixa, nunca a OUI real (`E0:F6:B5`).
MAC_NINTENDO_FAKE = "aa:bb:cc:00:99:01"
#: MAC com outra faixa forjada (`e8:47:3a`, "Edge físico" no guarda de
#: anonimato) representando um controle QUALQUER com OUI diferente do
#: Nintendo real (ex.: o 8BitDo, que nunca deve disparar o enable-IMU).
MAC_OUTRA_MARCA = "e8:47:3a:00:00:09"


def _imu_entry(uniq: str | None, hidraw: str | None, *, bus: str = "usb") -> dict[str, Any]:
    return {
        "name": "Nintendo Co., Ltd. Pro Controller",
        "vid": "057e",
        "pid": "2009",
        "bus": bus,
        "uniq": uniq,
        "driver": "nintendo",
        "evdev_path": "/dev/input/event7",
        "hidraw": hidraw,
    }


@pytest.fixture()
def oui_nintendo_forjada(monkeypatch: pytest.MonkeyPatch) -> str:
    """Aponta `NINTENDO_REAL_OUI` para a faixa forjada `aabbcc` (anonimato)."""
    monkeypatch.setattr(ei_mod, "NINTENDO_REAL_OUI", "aabbcc")
    return "aabbcc"


@pytest.fixture()
def imu_escritas(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int]]:
    """Captura chamadas a `enable_imu` (nunca toca hidraw real)."""
    import hefesto_dualsense4unix.core.external_leds as leds_mod

    chamadas: list[tuple[str, int]] = []

    def _fake(hidraw: str, *, packet_num: int = 0) -> bool:
        chamadas.append((hidraw, packet_num))
        return True

    monkeypatch.setattr(leds_mod, "enable_imu", _fake)
    return chamadas


class TestExternalImuEnabler:
    def test_oui_nintendo_real_usb_envia_uma_vez(
        self, oui_nintendo_forjada: str, imu_escritas: list[tuple[str, int]]
    ) -> None:
        enabler = ExternalImuEnabler()
        inventario = [_imu_entry(MAC_NINTENDO_FAKE, "/dev/hidraw5", bus="usb")]
        enabler.tick(inventario, now=0.0)
        assert imu_escritas == [("/dev/hidraw5", 0)]
        # Ticks seguintes (mesmo device, mesmo inventário): sucesso já
        # aconteceu — nunca reenvia dentro da MESMA adoção.
        enabler.tick(inventario, now=100.0)
        enabler.tick(inventario, now=200.0)
        assert imu_escritas == [("/dev/hidraw5", 0)]

    def test_oui_errado_zero_escrita(
        self, oui_nintendo_forjada: str, imu_escritas: list[tuple[str, int]]
    ) -> None:
        enabler = ExternalImuEnabler()
        inventario = [_imu_entry(MAC_OUTRA_MARCA, "/dev/hidraw5", bus="usb")]
        enabler.tick(inventario, now=0.0)
        assert imu_escritas == []

    def test_bus_bluetooth_zero_escrita_fase1(
        self, oui_nintendo_forjada: str, imu_escritas: list[tuple[str, int]]
    ) -> None:
        """FASE 1: só USB — BT é o mesmo território que matou o 8BitDo."""
        enabler = ExternalImuEnabler()
        inventario = [_imu_entry(MAC_NINTENDO_FAKE, "/dev/hidraw5", bus="bluetooth")]
        enabler.tick(inventario, now=0.0)
        assert imu_escritas == []

    def test_sem_uniq_zero_escrita(
        self, oui_nintendo_forjada: str, imu_escritas: list[tuple[str, int]]
    ) -> None:
        """Sem MAC não há OUI para checar — nunca dispara (não é sobre VID)."""
        enabler = ExternalImuEnabler()
        inventario = [_imu_entry(None, "/dev/hidraw5", bus="usb")]
        enabler.tick(inventario, now=0.0)
        assert imu_escritas == []

    def test_sem_hidraw_zero_escrita(
        self, oui_nintendo_forjada: str, imu_escritas: list[tuple[str, int]]
    ) -> None:
        enabler = ExternalImuEnabler()
        inventario = [_imu_entry(MAC_NINTENDO_FAKE, None, bus="usb")]
        enabler.tick(inventario, now=0.0)
        assert imu_escritas == []

    def test_backoff_no_maximo_duas_tentativas_espacadas(
        self, oui_nintendo_forjada: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Falha nunca vira loop: no máximo 2 tentativas, ≥2s entre elas."""
        import hefesto_dualsense4unix.core.external_leds as leds_mod

        tentativas: list[float] = []

        def _falha(hidraw: str, *, packet_num: int = 0) -> bool:
            tentativas.append(1.0)
            return False

        monkeypatch.setattr(leds_mod, "enable_imu", _falha)
        enabler = ExternalImuEnabler()
        inventario = [_imu_entry(MAC_NINTENDO_FAKE, "/dev/hidraw5", bus="usb")]

        enabler.tick(inventario, now=0.0)
        assert len(tentativas) == 1
        enabler.tick(inventario, now=1.0)  # dentro do backoff: nem tenta
        assert len(tentativas) == 1
        enabler.tick(inventario, now=2.5)  # fora do backoff: 2ª tentativa
        assert len(tentativas) == 2
        # Esgotado (2/2): nunca mais tenta nesta adoção, mesmo esperando.
        enabler.tick(inventario, now=100.0)
        assert len(tentativas) == 2

    def test_replug_reinicia_a_adocao(
        self, oui_nintendo_forjada: str, imu_escritas: list[tuple[str, int]]
    ) -> None:
        """Device some do inventário (unplug) e volta (replug) → nova
        adoção → envia de novo (o firmware reinicia a IMU em standby)."""
        enabler = ExternalImuEnabler()
        inventario = [_imu_entry(MAC_NINTENDO_FAKE, "/dev/hidraw5", bus="usb")]
        enabler.tick(inventario, now=0.0)
        assert imu_escritas == [("/dev/hidraw5", 0)]

        enabler.tick([], now=10.0)  # sumiu
        enabler.tick(inventario, now=20.0)  # replug
        assert imu_escritas == [("/dev/hidraw5", 0), ("/dev/hidraw5", 0)]

    def test_telemetria_enviado_e_falhou(
        self, oui_nintendo_forjada: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        eventos: list[tuple[str, dict[str, Any]]] = []

        class _SpyLogger:
            def info(self, evento: str, **kw: Any) -> None:
                eventos.append(("info", evento, kw))

            def warning(self, evento: str, **kw: Any) -> None:
                eventos.append(("warning", evento, kw))

            def debug(self, *_a: Any, **_kw: Any) -> None: ...

        monkeypatch.setattr(ei_mod, "logger", _SpyLogger())

        import hefesto_dualsense4unix.core.external_leds as leds_mod

        monkeypatch.setattr(leds_mod, "enable_imu", lambda hidraw, **k: True)
        ok_enabler = ExternalImuEnabler()
        ok_enabler.tick(
            [_imu_entry(MAC_NINTENDO_FAKE, "/dev/hidraw5", bus="usb")], now=0.0
        )
        sucesso = [
            kw
            for nivel, ev, kw in eventos
            if nivel == "info" and ev == "external_imu_enable_enviado"
        ]
        assert sucesso == [
            {"uniq": "aabbcc009901", "bus": "usb", "tentativa": 1}
        ]

        eventos.clear()
        monkeypatch.setattr(leds_mod, "enable_imu", lambda hidraw, **k: False)
        falha_enabler = ExternalImuEnabler()
        falha_enabler.tick(
            [_imu_entry(MAC_NINTENDO_FAKE, "/dev/hidraw5", bus="usb")], now=0.0
        )
        falha = [
            kw
            for nivel, ev, kw in eventos
            if nivel == "warning" and ev == "external_imu_enable_falhou"
        ]
        assert falha == [{"uniq": "aabbcc009901", "bus": "usb", "tentativa": 1}]

    def test_enable_imu_explode_nunca_propaga(
        self, oui_nintendo_forjada: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`enable_imu` levantando (bug/EIO inesperado) não pode derrubar o
        tick — suppress + warn (mesma disciplina do resto do módulo)."""
        import hefesto_dualsense4unix.core.external_leds as leds_mod

        def _explode(hidraw: str, **k: Any) -> bool:
            raise OSError("EIO")

        monkeypatch.setattr(leds_mod, "enable_imu", _explode)
        enabler = ExternalImuEnabler()
        enabler.tick(
            [_imu_entry(MAC_NINTENDO_FAKE, "/dev/hidraw5", bus="usb")], now=0.0
        )  # não levanta

    def test_tick_enumeracao_vazia_nao_levanta(self, oui_nintendo_forjada: str) -> None:
        ExternalImuEnabler().tick([], now=0.0)  # não levanta, sem device nenhum


class TestExternalLedSyncChamaImuEnabler:
    """Integração: `ExternalLedSync.tick()` também dispara o enable-IMU,
    reusando o MESMO inventário — sem enumeração extra de /dev/input."""

    def test_tick_do_led_sync_dispara_enable_imu(
        self,
        monkeypatch: pytest.MonkeyPatch,
        oui_nintendo_forjada: str,
        imu_escritas: list[tuple[str, int]],
        led_escritas: list[tuple[str, int]],
    ) -> None:
        sync = _sync(
            monkeypatch,
            [_imu_entry(MAC_NINTENDO_FAKE, "/dev/hidraw5", bus="usb")],
        )
        sync.tick(now=0.0)
        assert imu_escritas == [("/dev/hidraw5", 0)]
        # O LED também foi aceso normalmente — o enable-IMU não atrapalha.
        assert led_escritas == [("/dev/hidraw5", 1)]

    def test_auto_player_colors_off_nao_bloqueia_o_enable_imu(
        self,
        monkeypatch: pytest.MonkeyPatch,
        oui_nintendo_forjada: str,
        imu_escritas: list[tuple[str, int]],
    ) -> None:
        """`auto_player_colors` OFF para de afirmar LED, mas o enable-IMU (não
        é sobre cor/número) segue independente."""
        sync = _sync(
            monkeypatch,
            [_imu_entry(MAC_NINTENDO_FAKE, "/dev/hidraw5", bus="usb")],
            auto_enabled=False,
        )
        sync.tick(now=0.0)
        assert imu_escritas == [("/dev/hidraw5", 0)]
