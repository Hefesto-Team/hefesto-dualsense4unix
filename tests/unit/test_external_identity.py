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

#: Forma CANÔNICA (12-hex, sem separadores) de MAC_A — a key do registro.
_KEY_A = MAC_A.replace(":", "")

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


def _fila_no_disco(tmp_path: Path, kind: str) -> dict[str, int]:
    """Endereço → lugar na fila, do campo ``order`` (NUM-01, schema 3).

    Os dois registros gravam UMA fila só (lista de ``{addr, kind, rank}``) em
    vez dos mapas ``slots``/``externals`` de número absoluto: era essa forma
    que não conseguia dizer "quem está na mesa é 1..N".
    """
    dados = json.loads(_arquivo(tmp_path).read_text(encoding="utf-8"))
    return {
        str(e["addr"]): int(e["rank"])
        for e in dados[id_mod.ORDER_FIELD]
        if isinstance(e, dict) and e.get("kind") == kind
    }


def _gravar_fila(
    tmp_path: Path,
    *,
    dualsense: dict[str, int] | None = None,
    externos: dict[str, int] | None = None,
    version: object = None,
    boot: str = BOOT,
) -> None:
    """Escreve um ``controllers.json`` no schema vigente (NUM-01)."""
    entradas: list[dict[str, object]] = [
        {"addr": addr, "kind": id_mod.KIND_DUALSENSE, "rank": rank}
        for addr, rank in (dualsense or {}).items()
    ]
    entradas += [
        {"addr": addr, "kind": id_mod.KIND_EXTERNAL, "rank": rank}
        for addr, rank in (externos or {}).items()
    ]
    _arquivo(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    _arquivo(tmp_path).write_text(
        json.dumps(
            {
                "version": (
                    id_mod.CONTROLLERS_SCHEMA_VERSION if version is None else version
                ),
                "boot_id": boot,
                id_mod.ORDER_FIELD: entradas,
            }
        ),
        encoding="utf-8",
    )


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
    assert _fila_no_disco(tmp_path, id_mod.KIND_EXTERNAL) == {key_a: 7}


def test_identidade_sem_mac_e_volatil_nunca_persistida(tmp_path: Path) -> None:
    r = ExternalIdentityRegistry()
    assert r.slot_for("path:/dev/input/event9", reserve=0) == 1
    r.slot_for(MAC_A, reserve=0)
    r.sync_connected([MAC_A])  # persiste os sujos
    assert list(_fila_no_disco(tmp_path, id_mod.KIND_EXTERNAL)) == [
        MAC_A.replace(":", "")
    ]


# --- persistência: namespace `externals` no MESMO controllers.json -----------


def test_persistencia_atravessa_o_boot_e_so_o_schema_renumera(
    tmp_path: Path,
) -> None:
    """R-23 (25/07): o número do externo sobrevive ao REBOOT.

    TROCA DELIBERADA de contrato: este caso era
    `test_persistencia_por_boot_e_restauracao` e assertava que um arquivo com
    `boot_id` diferente devolvia `peek() is None` (sessão morta). Simetria
    obrigatória com o lado DualSense — os dois dividem UM espaço de numeração
    (R-24); se um restaurasse e o outro não, o que sobrasse escolheria slots
    por cima de reservas invisíveis e as duplicatas voltariam. Quem renumera
    agora é o SCHEMA.
    """
    r = ExternalIdentityRegistry()
    r.slot_for(MAC_A, reserve=2)
    r.sync_connected([MAC_A])

    novo = ExternalIdentityRegistry()
    novo.load()
    # NUM-01 precisou o que "preserva o número" quer dizer: o que atravessa o
    # restart é o LUGAR NA FILA (3). O número exibido é recalculado — com os
    # dois DualSense de volta na mesa ele volta a ser 3; sem nenhum deles
    # ligado o externo é o jogador 1, que é a cura desta frente.
    assert novo.snapshot() == {_KEY_A: 3}, "restart do daemon preserva o lugar"
    assert novo.slot_for(MAC_A, reserve=2) == 3

    # Reboot da máquina (âncora diferente): o lugar CONTINUA sendo do MAC.
    data = json.loads(_arquivo(tmp_path).read_text(encoding="utf-8"))
    data["boot_id"] = "boot-antigo"
    _arquivo(tmp_path).write_text(json.dumps(data), encoding="utf-8")
    outro_boot = ExternalIdentityRegistry()
    outro_boot.load()
    assert outro_boot.snapshot() == {_KEY_A: 3}

    # Só um SCHEMA diferente (outra regra de numeração) descarta.
    data["version"] = 0
    _arquivo(tmp_path).write_text(json.dumps(data), encoding="utf-8")
    frio = ExternalIdentityRegistry()
    frio.load()
    assert frio.snapshot() == {}
    assert frio.peek(MAC_A) is None


def test_schema_antigo_nao_ressuscita_pelo_save_do_outro_lado(
    tmp_path: Path,
) -> None:
    """R-23: bump de schema descarta o arquivo INTEIRO, não meio arquivo.

    Falha-sem (achado ao simular o `controllers.json` real dela): cada
    `_save_locked` faz read-modify-write PRESERVANDO o namespace do outro
    registro. Num bump de versão, o primeiro save carimbava `version` NOVA
    por cima do namespace VELHO do outro lado — a numeração que o `load`
    acabara de recusar voltava com selo de válida no boot seguinte, e o
    externo reaparecia segurando o slot 1 na frente dos DualSense.
    """
    _gravar_fila(
        tmp_path,
        # Schema 2 (o que a máquina dela tinha): mapas de NÚMERO ABSOLUTO,
        # com o externo à frente dos DualSense.
        dualsense={MAC_DS.replace(":", ""): 2},
        externos={_KEY_A: 1},
        version=2,
    )

    ds = id_mod.ControllerIdentityRegistry()
    ds.load()
    ext = ExternalIdentityRegistry()
    ext.load()
    assert ds.snapshot() == {} and ext.snapshot() == {}, "schema velho recusado"

    ds.sync_connected([MAC_DS])  # 1º save: carimba a versão nova
    data = json.loads(_arquivo(tmp_path).read_text(encoding="utf-8"))
    assert data["version"] == id_mod.CONTROLLERS_SCHEMA_VERSION
    assert _fila_no_disco(tmp_path, id_mod.KIND_EXTERNAL) == {}, (
        "a fila velha do outro registro não pode ser recarimbada"
    )

    # Boot seguinte: só a numeração NOVA sobrevive; o externo numera acima.
    ds2 = id_mod.ControllerIdentityRegistry()
    ds2.load()
    ext2 = ExternalIdentityRegistry()
    ext2.load()
    assert ds2.snapshot() == {MAC_DS.replace(":", ""): 1}
    assert ext2.snapshot() == {}
    assert ext2.slot_for(MAC_A, reserve=1) == 2


def test_os_dois_registros_gravam_a_mesma_versao_de_schema(tmp_path: Path) -> None:
    """R-23: DualSense e externos escrevem o MESMO arquivo — um save do lado
    externo não pode deixar o arquivo sem a versão que o outro lado exige (o
    load do DualSense o descartaria no boot seguinte)."""
    ext = ExternalIdentityRegistry()
    ext.slot_for(MAC_A, reserve=0)
    ext.sync_connected([MAC_A])
    data = json.loads(_arquivo(tmp_path).read_text(encoding="utf-8"))
    assert data["version"] == id_mod.CONTROLLERS_SCHEMA_VERSION

    ds = id_mod.ControllerIdentityRegistry()
    ds.sync_connected([MAC_DS])
    data = json.loads(_arquivo(tmp_path).read_text(encoding="utf-8"))
    assert data["version"] == id_mod.CONTROLLERS_SCHEMA_VERSION
    assert _fila_no_disco(tmp_path, id_mod.KIND_EXTERNAL) == {_KEY_A: 1}, (
        "as entradas do outro registro foram preservadas"
    )


def test_namespaces_coexistem_no_mesmo_arquivo(tmp_path: Path) -> None:
    """O registro DualSense (`slots`) e o de externos (`externals`) escrevem o
    MESMO controllers.json e cada save preserva o namespace do outro."""
    ds = id_mod.ControllerIdentityRegistry()
    ds.slot_for(MAC_DS)
    ds.sync_connected([MAC_DS])  # grava `slots`

    ext = ExternalIdentityRegistry()
    ext.slot_for(MAC_A, reserve=1)
    ext.sync_connected([MAC_A])  # grava `externals` preservando `slots`

    assert _fila_no_disco(tmp_path, id_mod.KIND_DUALSENSE) == {
        MAC_DS.replace(":", ""): 1
    }
    assert _fila_no_disco(tmp_path, id_mod.KIND_EXTERNAL) == {
        MAC_A.replace(":", ""): 2
    }

    # E o save do lado DualSense preserva as entradas externas (RMW).
    ds2 = id_mod.ControllerIdentityRegistry()
    ds2.load()
    ds2.slot_for(MAC_DS)
    ds2.sync_connected([MAC_DS])
    assert _fila_no_disco(tmp_path, id_mod.KIND_EXTERNAL) == {
        MAC_A.replace(":", ""): 2
    }
    assert _fila_no_disco(tmp_path, id_mod.KIND_DUALSENSE) == {
        MAC_DS.replace(":", ""): 1
    }


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
    quando havia slot de DualSense RESERVADO. O tick numera pela identidade
    volátil do aparelho com reserve=max(reservas DualSense); o IPC precisa
    consultar o registry pela MESMA identidade (não por uniq=None → posicional).

    Cenário: 2 DualSense {A:1,B:2}, A desconectou (slot 1 RESERVADO, snapshot
    inclui reservas) mas B segue conectado; 1 externo sem MAC. O LED acende
    player 3; a GUI (que conta só os CONECTADOS) exibia 'Controle 2'.
    """
    import hefesto_dualsense4unix.daemon.ipc_handlers as ih_mod

    # A desconectou → slot 1 fica RESERVADO no snapshot; só B conectado.
    ds_snapshot = {"dsa": 1, "dsb": 2}
    # Hermético (CLONE-01): sem MAC a identidade é o DONO no sysfs — sem este
    # dublê a subida sairia de um `/dev/input/event261` inexistente e acabaria
    # varrendo o `/sys` REAL da máquina da mantenedora.
    monkeypatch.setattr(
        er_mod,
        "_evdev_owner_dir",
        lambda _p: "/sys/devices/usb1/1-2/1-2:1.0/0003:057E:2009.0004",
    )
    inventario = [_entry(None, "/dev/hidraw6", "/dev/input/event261")]
    sync = _sync(monkeypatch, inventario, ds_slots=ds_snapshot)

    sync.tick(now=0.0)
    # LED aceso como player 3 (reserve=max(1,2)=2 → menor livre acima = 3).
    assert led_escritas == [("/dev/hidraw6", 3)]

    # IPC: a GUI conta só os DualSense CONECTADOS (1 = B). Sem o fix,
    # peek(None) → None → posicional 1+0+1=2, divergindo do LED. Com o fix,
    # peek pela MESMA identidade (`identity_for_entry`) → 3.
    monkeypatch.setattr(ih_mod, "_steam_hidraw_holders", lambda: {})
    inv = ih_mod._external_inventory(
        dualsense_count=1, slot_resolver=sync._registry.peek
    )
    assert inv[0]["player_slot"] == 3, "GUI deve exibir o MESMO número do LED"


def test_externo_nao_rouba_o_slot_1_dos_dualsense_presentes(
    monkeypatch: pytest.MonkeyPatch, led_escritas: list[tuple[str, int]]
) -> None:
    """R-24: reproduz o "não existe Controle 1" MEDIDO no controllers.json dela.

    Estado ao vivo (25/07): `externals: {<Pro>: 1}` e `slots: {<DS>: 2, <DS>:
    3}` — o Pro Nintendo USB segurava o slot 1 e os dois DualSense exibiam 2 e
    3, sem nenhum "Controle 1" na listagem. A causa não era o piso dos
    externos: era o registro dos DualSense estar VAZIO no primeiro tick
    (atribuição só-lazy, via provider de cor), então `_ds_reserve()` lia 0.

    Aqui os DOIS registros são os reais e a ordem é a do poll loop
    (`_sync_identity_registry` ANTES de `_schedule_external_tick`). Falha-sem:
    com `sync_connected` só reconciliando, `ds.snapshot()` fica `{}`, o
    externo recebe 1 e os DualSense herdam 2 e 3.
    """
    ds = id_mod.ControllerIdentityRegistry()
    ext = ExternalIdentityRegistry()
    ds.set_external_reserve_provider(lambda: set(ext.snapshot().values()))
    monkeypatch.setattr(
        er_mod,
        "discover_external_gamepads",
        lambda: [_entry(MAC_A, "/dev/hidraw6", "/dev/input/event261")],
    )
    sync = ExternalLedSync(SimpleNamespace(identity_registry=ds), ext)

    ds.sync_connected([MAC_DS, MAC_DS_B])  # tick lento numera quem está na mesa
    sync.tick(now=0.0)  # só então o tick dos externos pede número

    assert ds.snapshot() == {
        MAC_DS.replace(":", ""): 1,
        MAC_DS_B.replace(":", ""): 2,
    }, "os DualSense ocupam 1..N — existe Controle 1"
    assert ext.snapshot() == {_KEY_A: 3}, "o externo CONTINUA a contagem"
    assert led_escritas == [("/dev/hidraw6", 3)], "o LED bate com o número"


# --- MODO-01: um controle, DUAS identidades (25/07) --------------------------
#
# O 8BitDo Pro se apresenta conforme o MODO em que é ligado: em modo Switch no
# cabo o `hid-nintendo` degrada (`usb_probe_degrade`) e SINTETIZA um "MAC"
# `0x02` + VID + PID + bus; em modo PS4 por Bluetooth ele chega pelo
# `hid-playstation` com o MAC de verdade. Nada liga as duas identidades — OUI,
# VID/PID e driver são todos diferentes —, então a cura não é adivinhar que é o
# mesmo plástico: é reconhecer que a sintética não é identidade de aparelho.

#: Endereço SINTETIZADO. Na máquina real o valor é `0x02` + VID + PID + bus do
#: controle degradado; aqui a FORMA é a mesma (1º octeto `02`) com o resto na
#: faixa forjada que o gate de anonimato permite — o que está sob teste é o
#: octeto que marca "administrado localmente", nunca um VID/PID específico.
MAC_SINTETIZADO = "02:fe:00:20:09:03"
_KEY_SINTETIZADO = MAC_SINTETIZADO.replace(":", "")


def test_identidade_sintetizada_ganha_numero_mas_nunca_vai_ao_disco(
    tmp_path: Path,
) -> None:
    """O controle degradado no cabo PRECISA de número (o LED acende), mas o
    endereço sintético não pode virar reserva eterna no `controllers.json`.

    Falha-sem: `_canonical` só olhava a FORMA do MAC, então `02:...` era
    persistível igual a um MAC de hardware.
    """
    r = ExternalIdentityRegistry()
    assert r.slot_for(MAC_SINTETIZADO, reserve=2) == 3, "na mesa, tem número"
    r.slot_for(MAC_A, reserve=2)
    r.sync_connected([MAC_SINTETIZADO, MAC_A])

    assert _fila_no_disco(tmp_path, id_mod.KIND_EXTERNAL) == {_KEY_A: 4}, (
        "só MAC de hardware persiste; o sintético fica na sessão"
    )


def test_load_expulsa_identidade_sintetizada_ja_gravada(tmp_path: Path) -> None:
    """MIGRAÇÃO sem bump de schema: o fantasma já gravado morre no `load`.

    O `controllers.json` REAL da máquina dela tem a entrada sintética do modo
    Switch guardando um slot. Como o `load` já pulava `if not persistable`,
    reclassificar o endereço sintético cura o arquivo existente sem tocar na
    `CONTROLLERS_SCHEMA_VERSION` — bumpar renumeraria TODO mundo (inclusive os
    dois DualSense que estão certos) para consertar uma entrada só.
    """
    _gravar_fila(
        tmp_path,
        dualsense={MAC_DS.replace(":", ""): 1, MAC_DS_B.replace(":", ""): 2},
        externos={_KEY_A: 3, _KEY_SINTETIZADO: 4},
    )

    ext = ExternalIdentityRegistry()
    ext.load()
    assert ext.snapshot() == {_KEY_A: 3}, "o fantasma não volta do disco"
    assert ext.peek(MAC_SINTETIZADO) is None

    ds = id_mod.ControllerIdentityRegistry()
    ds.load()
    assert ds.snapshot() == {
        MAC_DS.replace(":", ""): 1,
        MAC_DS_B.replace(":", ""): 2,
    }, "os DualSense certos NÃO são renumerados pela cura"

    # E o disco é limpo pelo PRIMEIRO save (o `load` marca sujo ao descartar):
    # sem isso o fantasma ficava inerte no arquivo, inofensivo mas inexplicável.
    ext.sync_connected([MAC_A])
    assert _fila_no_disco(tmp_path, id_mod.KIND_EXTERNAL) == {_KEY_A: 3}
    assert _fila_no_disco(tmp_path, id_mod.KIND_DUALSENSE) == {
        MAC_DS.replace(":", ""): 1,
        MAC_DS_B.replace(":", ""): 2,
    }, "as entradas do outro registro sobrevivem à migração"


def test_identidade_sintetizada_ausente_solta_o_slot() -> None:
    """Dentro da MESMA sessão, a identidade do modo que saiu libera o número.

    É o coração do bug medido: a identidade do modo Switch (desconectada)
    segurava o slot e o 8BitDo CONECTADO por BT ia para o seguinte. A ausência
    é CONTADA (`VOLATILE_ABSENCE_LIMIT`) — um hiccup de enumeração não pode
    renumerar ninguém.
    """
    r = ExternalIdentityRegistry()
    assert r.slot_for(MAC_SINTETIZADO, reserve=2) == 3
    r.sync_connected([MAC_SINTETIZADO])

    r.sync_connected([])  # 1ª ausência: pode ter sido um `open` que falhou
    assert r.peek(MAC_SINTETIZADO) == 3, "uma ausência só não renumera nada"

    r.sync_connected([])  # 2ª seguida: saiu de verdade
    assert r.snapshot() == {}, "o slot volta para o pote"

    # E o MESMO plástico, agora em modo PS4 por BT, recebe o número livre.
    assert r.slot_for(MAC_B, reserve=2) == 3


def test_poda_nao_toca_reserva_de_mac_de_hardware() -> None:
    """A GUARDA da cura (D2/R-15): controle desligado NÃO perde o número.

    "A config que eu deixo nunca é respeitada" é queixa antiga; a poda vale só
    para identidade VOLÁTIL, que não identifica aparelho nenhum.
    """
    r = ExternalIdentityRegistry()
    assert r.slot_for(MAC_A, reserve=2) == 3
    for _ in range(20):
        r.sync_connected([])
    assert r.snapshot() == {_KEY_A: 3}, "MAC de hardware ausente mantém o lugar"
    # NUM-01: o que ninguém herda é o LUGAR (B entra no 4). O NÚMERO exibido
    # de B é 3 justamente porque A não está na mesa — antes desta frente o
    # ausente segurava o número e empurrava o presente para cima, que é o
    # defeito relatado ("ligo sozinho e sou o player 2").
    assert r.slot_for(MAC_B, reserve=2) == 3
    assert r.snapshot()[MAC_B.replace(":", "")] == 4, "ninguém herda o lugar"


def test_dois_aparelhos_do_mesmo_oui_nunca_se_fundem() -> None:
    """Guarda contra a cura ERRADA: herdar slot por OUI funde dois controles.

    Dois 8BitDo de verdade dividem o OUI. Se a cura fosse "OUI conhecido +
    entrada antiga desconectada ⇒ herda o slot", os dois acenderiam o MESMO
    número — a queixa "dois player 1" por outro caminho. A cura desta frente
    não olha OUI nenhum, e este caso trava isso.
    """
    r = ExternalIdentityRegistry()
    assert MAC_A[:8] == MAC_B[:8], "mesma OUI, aparelhos distintos"
    assert r.slot_for(MAC_A, reserve=2) == 3
    r.sync_connected([MAC_A])
    r.sync_connected([])  # o primeiro dorme
    assert r.slot_for(MAC_B, reserve=2) == 3, "B é o 3 porque A não está na mesa"
    assert r.snapshot() == {_KEY_A: 3, MAC_B.replace(":", ""): 4}, (
        "o segundo NÃO herda o lugar 3 do primeiro"
    )


def test_quatro_controles_e_o_fantasma_do_outro_modo_ninguem_no_slot_5(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    led_escritas: list[tuple[str, int]],
) -> None:
    """I4 — o cenário MEDIDO ao vivo, ponta a ponta.

    Estado do `controllers.json` real: 2 DualSense (1, 2), o Pro Nintendo (3) e
    a identidade do 8BitDo em modo Switch, DESCONECTADA, segurando o 4. Com os
    4 jogadores na mesa, o 8BitDo conectado por Bluetooth caía no slot 5 — e o
    DualSense só tem 5 LEDs de player, então o número 5 é bug visível.

    Falha-sem: o fantasma volta do disco segurando o 4 e o `slot_for` do
    controle presente acha o menor livre em 5.
    """
    _gravar_fila(
        tmp_path,
        dualsense={MAC_DS.replace(":", ""): 1, MAC_DS_B.replace(":", ""): 2},
        externos={_KEY_A: 3, _KEY_SINTETIZADO: 4},
    )

    ds = id_mod.ControllerIdentityRegistry()
    ds.load()
    ext = ExternalIdentityRegistry()
    ext.load()
    ds.set_external_reserve_provider(lambda: set(ext.snapshot().values()))
    monkeypatch.setattr(
        er_mod,
        "discover_external_gamepads",
        lambda: [
            _entry(MAC_A, "/dev/hidraw0", "/dev/input/event2"),
            _entry(MAC_B, "/dev/hidraw8", "/dev/input/event259"),
        ],
    )
    sync = ExternalLedSync(SimpleNamespace(identity_registry=ds), ext)

    ds.sync_connected([MAC_DS, MAC_DS_B])  # ordem do poll loop (R-24)
    sync.tick(now=0.0)

    numeros = sorted(ds.snapshot().values()) + sorted(ext.snapshot().values())
    assert numeros == [1, 2, 3, 4], (
        "4 controles na mesa ocupam 1..4 — ninguém no slot 5"
    )
    assert ext.peek(MAC_B) == 4
    assert led_escritas == [("/dev/hidraw0", 3), ("/dev/hidraw8", 4)]

    # E o arquivo sai curado: o fantasma não volta no próximo boot.
    sync.tick(now=LED_MIN_INTERVAL_SEC * 2)
    assert _fila_no_disco(tmp_path, id_mod.KIND_EXTERNAL) == {
        _KEY_A: 3,
        MAC_B.replace(":", ""): 4,
    }


def test_externo_sem_mac_conta_como_conectado(
    monkeypatch: pytest.MonkeyPatch, led_escritas: list[tuple[str, int]]
) -> None:
    """`sync_connected` e a atribuição têm que ver a MESMA identidade.

    O tick só mandava as entradas com `uniq` string ao `sync_connected`, então
    o externo sem MAC (numerado por `path:...`) nunca entrava no conjunto de
    CONECTADOS que aquele método reescreve inteiro. Duas consequências, e a
    segunda é nova:

    - o `snapshot_connected` que o "Renumerar agora" lê ficava ERRADO na
      janela entre o `sync_connected` e o `slot_for` do MESMO tick (os dois
      tomam o `RLock` separadamente) — o controle presente ia para o fim da
      fila das reservas;
    - a poda de identidade volátil (MODO-01) passaria a contar ausência para
      ele a cada tick, mesmo com ele na mesa.

    CLONE-01: a identidade de um externo SEM MAC deixou de ser o node
    (`path:...`) e passou a ser o DONO no sysfs (`dev:...`) — a mesma chave com
    que a enumeração já deduplicava os nodes irmãos. O dublê de
    `_evdev_owner_dir` mantém o teste hermético (sem ele a subida sairia de um
    `/dev/input/event261` inexistente e varreria o `/sys` REAL da máquina).
    """
    dono = "/sys/devices/usb1/1-2/1-2:1.0/0003:057E:2009.0004"
    monkeypatch.setattr(er_mod, "_evdev_owner_dir", lambda _p: dono)
    inventario = [_entry(None, "/dev/hidraw6", "/dev/input/event261")]
    sync = _sync(monkeypatch, inventario)
    for i in range(4):
        sync.tick(now=float(i * 10))

    key = f"dev:{dono}"
    assert sync._registry.snapshot() == {key: 1}, "o slot não some sob poda"
    assert sync._registry.snapshot_connected() == {key}
    assert sync._registry._volatile_absences == {}, (
        "quem está PRESENTE nunca arma o contador de ausências"
    )
    assert led_escritas == [("/dev/hidraw6", 1)], "e o LED não pisca de número"


def test_tick_enumeracao_quebrada_nao_derruba(
    monkeypatch: pytest.MonkeyPatch, led_escritas: list[tuple[str, int]]
) -> None:
    def explode() -> list[dict[str, Any]]:
        raise RuntimeError("evdev sumiu")

    monkeypatch.setattr(er_mod, "discover_external_gamepads", explode)
    sync = ExternalLedSync(SimpleNamespace(), ExternalIdentityRegistry())
    sync.tick(now=0.0)  # não levanta
    assert led_escritas == []


# --- CLONE-01: dois clones degradados são DOIS jogadores (25/07) -------------
#
# O DKMS `hid-nintendo` deste projeto (patch 0003, parâmetro `usb_probe_degrade`)
# FABRICA um endereço quando o controle não responde ao `REQ_DEV_INFO` no cabo:
# `02` + VID + PID + número do barramento. Não há um bit do APARELHO ali, e o
# comentário do próprio patch admite: "two identical clones plugged at once
# would share it". É o caso rotineiro dela — Pro genuíno + 8BitDo em modo
# Switch, ambos 057e:2009.
#
# A enumeração já parou de ENGOLIR o segundo (dedup por dono no sysfs). Esta
# seção trava o passo seguinte: rio abaixo, os dois precisam receber SLOTS e
# LEDs DIFERENTES — e um aparelho só, visto por nodes diferentes, continua um.
#
# O endereço sintético nunca é escrito como literal (o guarda de anonimato
# reprova MAC-forma fora das faixas da casa): é DERIVADO da fórmula do kernel,
# o que de quebra documenta a fórmula aqui.

VID_NINTENDO = 0x057E
PID_PRO_CONTROLLER = 0x2009
BUS_USB = 0x03

#: Diretórios das instâncias HID no sysfs — o que separa dois clones idênticos.
#: O hid-core numera em sequência, então dois aparelhos caem em dirs diferentes
#: e os nodes irmãos de UM aparelho caem no mesmo.
DONO_PRO = "/sys/devices/usb1/1-2/1-2:1.0/0003:057E:2009.0001"
DONO_CLONE = "/sys/devices/usb1/1-6/1-6:1.0/0003:057E:2009.0006"


def _uniq_sintetico(vid: int, pid: int, bus: int) -> str:
    """Reproduz o endereço que o `hid-nintendo` degradado sintetiza.

    Espelho fiel de `joycon_read_mac` no patch 0003: `mac_addr[0] = 0x02`
    (unicast administrado localmente), `[1..2]` = VID, `[3..4]` = PID e `[5]` =
    barramento — em maiúsculas, como o `devm_kasprintf` do kernel formata.
    """
    octetos = (0x02, vid >> 8, vid & 0xFF, pid >> 8, pid & 0xFF, bus)
    return ":".join(f"{b:02X}" for b in octetos)


def _entry_degradado(path: str, hidraw: str) -> dict[str, Any]:
    """Entrada de inventário de um Nintendo-class DEGRADADO no cabo."""
    entry = _entry(
        _uniq_sintetico(VID_NINTENDO, PID_PRO_CONTROLLER, BUS_USB), hidraw, path
    )
    entry["bus"] = "usb"
    return entry


def _donos(monkeypatch: pytest.MonkeyPatch, mapa: dict[str, str]) -> None:
    """Dublê HERMÉTICO de `_evdev_owner_dir` (node evdev → dir da instância HID).

    Sem ele a subida sairia de um `/dev/input/eventN` inexistente e acabaria
    varrendo o `/sys` REAL da máquina da mantenedora — que tem controle de
    verdade plugado enquanto a suíte roda.
    """
    monkeypatch.setattr(er_mod, "_evdev_owner_dir", lambda p: mapa.get(p))


def test_identity_for_entry_e_a_mesma_chave_da_deduplicacao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A FONTE ÚNICA da identidade, nos quatro casos que importam."""
    node_pro = "/dev/input/event30"
    node_clone = "/dev/input/event34"
    node_irmao = "/dev/input/event31"  # 2º node do MESMO Pro (IMU/touchpad)
    _donos(
        monkeypatch,
        {node_pro: DONO_PRO, node_irmao: DONO_PRO, node_clone: DONO_CLONE},
    )
    pro = _entry_degradado(node_pro, "/dev/hidraw2")
    clone = _entry_degradado(node_clone, "/dev/hidraw5")
    irmao = _entry_degradado(node_irmao, "/dev/hidraw2")

    # 1. o endereço sintético NÃO identifica: quem identifica é o dono no sysfs.
    assert pro["uniq"] == clone["uniq"], "premissa: o kernel dá o MESMO endereço"
    assert ei_mod.identity_for_entry(pro) == f"dev:{DONO_PRO}"
    assert ei_mod.identity_for_entry(pro) != ei_mod.identity_for_entry(clone)
    # 2. nodes irmãos do MESMO aparelho colapsam em UMA identidade.
    assert ei_mod.identity_for_entry(irmao) == ei_mod.identity_for_entry(pro)
    # 3. MAC de HARDWARE segue mandando — nem olha o dono (é a identidade que
    #    sobrevive a replug e casa a sessão USB com a Bluetooth do mesmo pad).
    real = _entry(MAC_A, "/dev/hidraw2", node_clone)
    assert ei_mod.identity_for_entry(real) == _KEY_A
    # 4. campo já carimbado VENCE: é assim que a identidade atravessa o
    #    JSON-RPC sem a GUI recalcular (e divergir).
    carimbada = {**pro, ei_mod.EXTERNAL_IDENTITY_FIELD: "dev:veio-pronta"}
    assert ei_mod.identity_for_entry(carimbada) == "dev:veio-pronta"


def test_dois_clones_degradados_recebem_slots_e_leds_distintos(
    monkeypatch: pytest.MonkeyPatch, led_escritas: list[tuple[str, int]]
) -> None:
    """O sintoma dela: os dois Nintendo-class exibiam o MESMO número de jogador.

    Falha-sem: com a identidade sendo `uniq or path:` o endereço sintético —
    idêntico nos dois — virava UMA chave só; o registro ficava com uma entrada,
    o segundo controle herdava o slot do primeiro e os dois LEDs acendiam o
    mesmo número.
    """
    node_pro = "/dev/input/event30"
    node_clone = "/dev/input/event34"
    _donos(monkeypatch, {node_pro: DONO_PRO, node_clone: DONO_CLONE})
    inventario = [
        _entry_degradado(node_pro, "/dev/hidraw2"),
        _entry_degradado(node_clone, "/dev/hidraw5"),
    ]
    sync = _sync(monkeypatch, inventario)

    sync.tick(now=0.0)

    assert sync._registry.snapshot() == {
        f"dev:{DONO_PRO}": 1,
        f"dev:{DONO_CLONE}": 2,
    }, "dois aparelhos, dois slots"
    assert led_escritas == [("/dev/hidraw2", 1), ("/dev/hidraw5", 2)], (
        "e cada LED acende o SEU número"
    )


def test_clones_degradados_seguem_volateis_e_nunca_vao_ao_disco(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, led_escritas: list[tuple[str, int]]
) -> None:
    """MODO-01 continua valendo: separar os clones não os torna persistíveis.

    Nenhuma das duas identidades identifica um APARELHO entre boots (o dir da
    instância HID é do plug de agora), então elas valem pela SESSÃO — o disco
    fica intocado, e a reserva eterna segue sendo privilégio de MAC de
    hardware (D2/R-15).
    """
    node_pro = "/dev/input/event30"
    node_clone = "/dev/input/event34"
    _donos(monkeypatch, {node_pro: DONO_PRO, node_clone: DONO_CLONE})
    inventario = [
        _entry_degradado(node_pro, "/dev/hidraw2"),
        _entry_degradado(node_clone, "/dev/hidraw5"),
    ]
    sync = _sync(monkeypatch, inventario)

    sync.tick(now=0.0)
    sync.tick(now=LED_MIN_INTERVAL_SEC * 2)

    assert sorted(sync._registry.snapshot().values()) == [1, 2]
    assert not _arquivo(tmp_path).exists(), (
        "identidade de sessão jamais vai ao controllers.json"
    )


def test_dois_clones_degradados_chegam_distintos_na_gui(
    monkeypatch: pytest.MonkeyPatch, led_escritas: list[tuple[str, int]]
) -> None:
    """A ponta da corrente: rota IPC e GUI também têm que ver DOIS controles.

    Falha-sem (dois pontos independentes): a rota IPC resolvia o slot por
    `uniq or path:` — mesma string nos dois clones, logo o MESMO `player_slot`
    para ambos; e `external_key` (a chave do botão do seletor) caía no `uniq`,
    então os dois botões respondiam pela MESMA entrada do inventário.
    """
    import hefesto_dualsense4unix.daemon.ipc_handlers as ih_mod
    from hefesto_dualsense4unix.app.actions.external_controllers import (
        external_key,
        slot_of,
    )

    node_pro = "/dev/input/event30"
    node_clone = "/dev/input/event34"
    _donos(monkeypatch, {node_pro: DONO_PRO, node_clone: DONO_CLONE})
    inventario = [
        _entry_degradado(node_pro, "/dev/hidraw2"),
        _entry_degradado(node_clone, "/dev/hidraw5"),
    ]
    sync = _sync(monkeypatch, inventario)
    sync.tick(now=0.0)

    monkeypatch.setattr(ih_mod, "_steam_hidraw_holders", lambda: {})
    inv = ih_mod._external_inventory(
        dualsense_count=0, slot_resolver=sync._registry.peek
    )

    # 1. o número que a GUI exibe é, controle a controle, o que o LED acendeu.
    assert [(e["hidraw"], slot_of(e, 0, i)) for i, e in enumerate(inv)] == (
        led_escritas
    )
    # 2. e os botões do seletor são DOIS botões, cada um casando com o SEU
    #    controle (`_on_external_clicked` procura a entrada por esta chave).
    chaves = [external_key(e) for e in inv]
    assert len(set(chaves)) == 2
    achado = next(e for e in inv if external_key(e) == chaves[1])
    assert achado["hidraw"] == "/dev/hidraw5"


def test_um_aparelho_que_troca_de_node_nao_vira_controle_novo(
    monkeypatch: pytest.MonkeyPatch, led_escritas: list[tuple[str, int]]
) -> None:
    """O outro lado da moeda, que a correção não pode quebrar.

    Um controle publica VÁRIOS nodes evdev (gamepad, IMU, touchpad, headset
    jack) e o vencedor da deduplicação é o de menor número — que muda se um
    node irmão nasce/morre no meio da sessão. A identidade é o DONO no sysfs
    justamente por isso: ela não se mexe quando o node se mexe.

    Falha-sem: numerando por `path:<node>`, a troca de node vira aparelho NOVO
    — slot 2, LED repintado, e o "o número muda sozinho" de volta.
    """
    dono = DONO_PRO
    primeiro = "/dev/input/event41"
    irmao = "/dev/input/event42"
    _donos(monkeypatch, {primeiro: dono, irmao: dono})
    # Sem MAC (é o caso do X-input e do firmware sem serial): a identidade não
    # tem para onde ir a não ser o node — ou o dono.
    sync = _sync(monkeypatch, [_entry(None, "/dev/hidraw2", primeiro)])
    sync.tick(now=0.0)

    monkeypatch.setattr(
        er_mod,
        "discover_external_gamepads",
        lambda: [_entry(None, "/dev/hidraw2", irmao)],
    )
    sync.tick(now=LED_MIN_INTERVAL_SEC * 2)

    assert sync._registry.snapshot() == {f"dev:{dono}": 1}, "continua UM aparelho"
    assert led_escritas == [("/dev/hidraw2", 1)], "sem renumerar, sem repintar"


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


def test_auto_numbers_off_para_de_escrever_e_limpa_cache(
    monkeypatch: pytest.MonkeyPatch, led_escritas: list[tuple[str, int]]
) -> None:
    """NUMA-03.4(c): simetria com o provider DualSense — OFF para de afirmar
    (zero escritas) e limpa o cache; achado ao vivo sem o fix: o externo
    continuava aceso com o DualSense já apagado. OFF->ON reescreve.

    R-14 (auditoria 23/07) — o EIXO mudou de propósito: o gate deste tick era
    ``auto_enabled`` (o ``auto_player_colors`` do perfil), mas o que se
    escreve aqui é ``apply_player_number``, o NÚMERO do jogador. Agora quem
    manda é ``auto_numbers_enabled``; a simetria "OFF para de afirmar" é a
    mesma, só que no flag certo. O par deste caso é
    ``test_auto_colors_off_nao_congela_a_numeracao_dos_externos``.
    """
    sync = _sync(monkeypatch, [_entry(MAC_A, "/dev/hidraw6", "/dev/input/event261")])
    sync.tick(now=0.0)
    assert led_escritas == [("/dev/hidraw6", 1)]

    sync._daemon.identity_registry.auto_numbers_enabled = False
    sync.tick(now=1.0)
    assert led_escritas == [("/dev/hidraw6", 1)], "OFF: zero escritas novas"
    assert sync._last_value == {}, "cache limpo enquanto OFF"

    sync._daemon.identity_registry.auto_numbers_enabled = True
    sync.tick(now=1.5)
    assert led_escritas == [("/dev/hidraw6", 1), ("/dev/hidraw6", 1)], (
        "OFF->ON reescreve"
    )


def test_auto_colors_off_nao_congela_a_numeracao_dos_externos(
    monkeypatch: pytest.MonkeyPatch, led_escritas: list[tuple[str, int]]
) -> None:
    """R-14: desligar a COR não pode calar o número do 8BitDo/Pro Nintendo.

    Falha-sem: com o gate no ``auto_enabled``, o ``fps.json`` dela (salvo com
    ``auto_player_colors:false`` por um clique de cor em "Todos") deixava o
    externo sem escrita NENHUMA — e, pior, sem sequer receber slot no
    registro, porque o ``slot_for`` morava depois do early-return.
    """
    sync = _sync(
        monkeypatch,
        [_entry(MAC_A, "/dev/hidraw6", "/dev/input/event261")],
        ds_slots={"m1": 1, "m2": 2},
        auto_enabled=False,
    )
    sync.tick(now=0.0)
    assert led_escritas == [("/dev/hidraw6", 3)], "cor OFF não cala o número"
    assert sync._registry.snapshot() == {_KEY_A: 3}


def test_numeracao_off_ainda_atribui_o_slot(
    monkeypatch: pytest.MonkeyPatch, led_escritas: list[tuple[str, int]]
) -> None:
    """R-14 §1: ATRIBUIR é identidade — o flag governa só a ESCRITA.

    Falha-sem: o ``slot_for`` rodava DEPOIS do early-return, então com o
    automático desligado o externo ficava fora do registro; o espaço de
    numeração global (que o lado DualSense também consulta) ganhava um buraco
    e a colisão nascia na próxima atribuição.
    """
    sync = _sync(
        monkeypatch,
        [_entry(MAC_A, "/dev/hidraw6", "/dev/input/event261")],
        ds_slots={"m1": 1},
    )
    sync._daemon.identity_registry.auto_numbers_enabled = False
    sync.tick(now=0.0)
    assert led_escritas == [], "numeração OFF: nenhuma escrita de LED"
    assert sync._registry.snapshot() == {_KEY_A: 2}, "mas o slot foi atribuído"


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
