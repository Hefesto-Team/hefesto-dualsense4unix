"""LUGAR-À-MESA-01 / E2 — descoberta única, normalizador de eixo e reencontro.

Entrega 2 da `MÁSCARA-01` na versão correta (ver a nota datada de 07/08/2026 nas
duas sprints): **sem adoção nenhuma**. Nada aqui dá controle virtual, lugar na
partida ou número de jogador a um externo — isso é a `E3`, e o veto de 19/07
(*"externo não ganha controle virtual"*) segue de pé.

O que estas baterias mordem, e por que cada uma existe:

1. **o normalizador de eixo** — `EvdevReader._handle_abs` fazia `value & 0xFF`
   seis vezes seguidas, supondo "DualSense, 0..255". Com o Nintendo Pro
   (-32767..32767) o CENTRO do analógico virava `0`, que em 0..255 é **talo à
   esquerda e para cima**: o personagem anda sozinho para o canto e não para;
2. **o DualSense sai bit a bit idêntico ao de hoje** — é o caminho quente de
   input de TODOS os controles. Consertar quem não funcionava mudando o número
   de quem já funcionava seria o defeito, não a cura;
3. **o gatilho digital sintetizado** — o Pro não publica `ABS_Z`/`ABS_RZ` (o
   ZL/ZR dele é botão). Sem síntese o gatilho fica 0 para sempre;
4. **a descoberta única** — dois laços abriam TODOS os nodes, cada um com a sua
   regra de identidade;
5. **o reencontro por identidade** — `_locate` só procurava em
   `discover_dualsense_evdevs()`, então externo nenhum voltava de um replug.

MACs: SEMPRE na faixa forjada canônica da casa (`aa:bb:cc:*`) — o teste-guarda
de anonimato só permite essas faixas.
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from evdev import AbsInfo, ecodes

from hefesto_dualsense4unix.core import evdev_reader as er_mod
from hefesto_dualsense4unix.core.evdev_reader import (
    ESPECIE_DUALSENSE,
    ESPECIE_EXTERNAL,
    EixoAbsoluto,
    EvdevReader,
    discover_dualsense_evdevs,
    discover_external_gamepads,
    discover_gamepads,
    normalizar_eixo,
)

MAC_DUALSENSE_FORJADO = "aa:bb:cc:00:d5:01"
MAC_PRO_FORJADO = "aa:bb:cc:00:be:ef"
IDENT_DUALSENSE = "aabbcc00d501"
IDENT_PRO = "aabbcc00beef"

#: A forma dos eixos medida em 06/08/2026 com os aparelhos na mesa dela
#: (LUGAR-À-MESA-01, "uma segunda medição, feita FORA da entregue").
FAIXA_DUALSENSE = AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)
FAIXA_PRO = AbsInfo(value=0, min=-32767, max=32767, fuzz=250, flat=500, resolution=0)
FAIXA_HAT = AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)


def _caps_dualsense() -> dict[int, Any]:
    """Caps do DualSense: quatro eixos de analógico MAIS os dois gatilhos."""
    return {
        ecodes.EV_KEY: [ecodes.BTN_SOUTH, ecodes.BTN_TL2, ecodes.BTN_TR2],
        ecodes.EV_ABS: [
            (ecodes.ABS_X, FAIXA_DUALSENSE),
            (ecodes.ABS_Y, FAIXA_DUALSENSE),
            (ecodes.ABS_RX, FAIXA_DUALSENSE),
            (ecodes.ABS_RY, FAIXA_DUALSENSE),
            (ecodes.ABS_Z, FAIXA_DUALSENSE),
            (ecodes.ABS_RZ, FAIXA_DUALSENSE),
            (ecodes.ABS_HAT0X, FAIXA_HAT),
            (ecodes.ABS_HAT0Y, FAIXA_HAT),
        ],
    }


def _caps_pro() -> dict[int, Any]:
    """Caps do Nintendo Pro: eixos com sinal e **sem** `ABS_Z`/`ABS_RZ`."""
    return {
        ecodes.EV_KEY: [ecodes.BTN_SOUTH, ecodes.BTN_TL2, ecodes.BTN_TR2],
        ecodes.EV_ABS: [
            (ecodes.ABS_X, FAIXA_PRO),
            (ecodes.ABS_Y, FAIXA_PRO),
            (ecodes.ABS_RX, FAIXA_PRO),
            (ecodes.ABS_RY, FAIXA_PRO),
            (ecodes.ABS_HAT0X, FAIXA_HAT),
            (ecodes.ABS_HAT0Y, FAIXA_HAT),
        ],
    }


class _DevFalso:
    """Só o que `_on_device_opened` toca: o `capabilities()` do node aberto."""

    def __init__(self, caps: Any) -> None:
        self._caps = caps

    def capabilities(self) -> Any:
        if isinstance(self._caps, Exception):
            raise self._caps
        return self._caps


def _reader_com(caps: Any) -> EvdevReader:
    """Reader com o node JÁ aberto (o normalizador nasce no open, não no init)."""
    reader = EvdevReader(device_path=Path("/dev/input/event999"))
    reader._on_device_opened(_DevFalso(caps))
    return reader


# --- 1. o normalizador: o centro do Pro deixa de ser talo no canto ----------


def test_o_centro_do_pro_controller_deixa_de_ser_talo_no_canto() -> None:
    """Valor cru `0` no Pro é o CENTRO; o `& 0xFF` de hoje devolvia `0`, que em
    0..255 significa talo à esquerda e para cima."""
    reader = _reader_com(_caps_pro())

    reader._handle_abs(ecodes.ABS_X, 0, ecodes)
    reader._handle_abs(ecodes.ABS_Y, 0, ecodes)
    snap = reader.snapshot()
    assert (snap.lx, snap.ly) == (128, 128), (
        "centro do analógico do Pro lido como talo — o personagem anda sozinho"
    )

    # E os extremos continuam sendo extremos, nos dois sentidos.
    reader._handle_abs(ecodes.ABS_X, -32767, ecodes)
    reader._handle_abs(ecodes.ABS_Y, 32767, ecodes)
    snap = reader.snapshot()
    assert (snap.lx, snap.ly) == (0, 255)


def test_o_normalizador_e_do_aparelho_nao_de_uma_tabela_de_conhecidos() -> None:
    """O MESMO valor cru vira números diferentes em aparelhos com faixas
    diferentes — é a propriedade que faz a cura valer na máquina de um
    desconhecido, e não só nesta bancada."""
    faixa_de_255 = EixoAbsoluto(minimo=0, maximo=255)
    faixa_com_sinal = EixoAbsoluto(minimo=-32767, maximo=32767, flat=500)
    faixa_de_1023 = EixoAbsoluto(minimo=0, maximo=1023)

    assert normalizar_eixo(0, faixa_de_255) == 0
    assert normalizar_eixo(0, faixa_com_sinal) == 128
    assert normalizar_eixo(0, faixa_de_1023) == 0
    assert normalizar_eixo(512, faixa_de_1023) == 128
    assert normalizar_eixo(1023, faixa_de_1023) == 255


# --- 2. o DualSense sai bit a bit idêntico ao de hoje ------------------------


def test_o_dualsense_sai_bit_a_bit_identico_ao_de_hoje() -> None:
    """Regressão do caminho quente: com a faixa 0..255 declarada, TODO valor sai
    exatamente como o `value & 0xFF` de sempre — inclusive FORA da faixa, onde
    um `clamp` e o `& 0xFF` discordam (256 vira 0, não 255)."""
    reader = _reader_com(_caps_dualsense())

    for cru in range(256):
        reader._handle_abs(ecodes.ABS_X, cru, ecodes)
        reader._handle_abs(ecodes.ABS_Y, cru, ecodes)
        reader._handle_abs(ecodes.ABS_RX, cru, ecodes)
        reader._handle_abs(ecodes.ABS_RY, cru, ecodes)
        reader._handle_abs(ecodes.ABS_Z, cru, ecodes)
        reader._handle_abs(ecodes.ABS_RZ, cru, ecodes)
        snap = reader.snapshot()
        assert (snap.lx, snap.ly, snap.rx, snap.ry) == (cru, cru, cru, cru)
        assert (snap.l2_raw, snap.r2_raw) == (cru, cru)

    reader._handle_abs(ecodes.ABS_X, 256, ecodes)
    assert reader.snapshot().lx == 0, "o contrato fora da faixa é `& 0xFF`, não clamp"
    reader._handle_abs(ecodes.ABS_X, -1, ecodes)
    assert reader.snapshot().lx == 255


def test_sem_absinfo_legivel_o_reader_cai_no_comportamento_de_hoje() -> None:
    """Node que não declara `absinfo` (ou cujo `capabilities()` explode) NÃO
    pode virar um moedor de eixo: degradar para o que já rodava é o único modo
    de falha aceitável num caminho quente de input."""
    nunca_abriu = EvdevReader(device_path=Path("/dev/input/event999"))
    nunca_abriu._handle_abs(ecodes.ABS_X, 300, ecodes)
    assert nunca_abriu.snapshot().lx == 300 & 0xFF

    explodiu = _reader_com(OSError("node sumiu no meio do open"))
    explodiu._handle_abs(ecodes.ABS_X, 300, ecodes)
    assert explodiu.snapshot().lx == 300 & 0xFF
    assert explodiu._eixos == {}


# --- 3. o gatilho digital sintetizado ---------------------------------------


def test_gatilho_digital_sintetizado_quando_o_eixo_falta() -> None:
    """Sem `ABS_Z`/`ABS_RZ`, o `BTN_TL2`/`BTN_TR2` tem de valer 255 pressionado;
    hoje o gatilho fica 0 para sempre e o dedo não chega ao jogo."""
    reader = _reader_com(_caps_pro())
    assert reader.snapshot().l2_raw == 0

    reader._handle_key(ecodes.BTN_TL2, 1, ecodes)
    reader._handle_key(ecodes.BTN_TR2, 1, ecodes)
    snap = reader.snapshot()
    assert (snap.l2_raw, snap.r2_raw) == (255, 255)
    assert {"l2_btn", "r2_btn"} <= snap.buttons_pressed

    reader._handle_key(ecodes.BTN_TL2, 0, ecodes)
    assert reader.snapshot().l2_raw == 0
    assert reader.snapshot().r2_raw == 255, "soltar um gatilho não solta o outro"


def test_o_dualsense_nao_sofre_sintese_de_gatilho() -> None:
    """No DualSense o eixo EXISTE: o `BTN_TL2` continua sendo só um botão.
    Sobrescrever o analógico com 255 ao cruzar o limiar mataria o gatilho
    adaptativo, que é metade do produto."""
    reader = _reader_com(_caps_dualsense())

    reader._handle_abs(ecodes.ABS_Z, 120, ecodes)
    reader._handle_key(ecodes.BTN_TL2, 1, ecodes)
    snap = reader.snapshot()
    assert snap.l2_raw == 120, "a síntese pisou no gatilho analógico do DualSense"
    assert "l2_btn" in snap.buttons_pressed

    reader._handle_key(ecodes.BTN_TL2, 0, ecodes)
    assert reader.snapshot().l2_raw == 120


def test_a_queda_do_device_nao_deixa_gatilho_sintetizado_travado() -> None:
    """Gatilho SINTETIZADO vem do botão, e o reset solta os botões à força —
    deixá-lo em 255 seria um gatilho travado no fundo. O gatilho ANALÓGICO não
    é tocado: ali o valor congelado é o comportamento de sempre."""
    pro = _reader_com(_caps_pro())
    pro._handle_key(ecodes.BTN_TL2, 1, ecodes)
    assert pro.snapshot().l2_raw == 255
    pro._reset_on_disconnect()
    assert pro.snapshot().l2_raw == 0

    dualsense = _reader_com(_caps_dualsense())
    dualsense._handle_abs(ecodes.ABS_Z, 200, ecodes)
    dualsense._reset_on_disconnect()
    assert dualsense.snapshot().l2_raw == 200, (
        "zerar o gatilho analógico no reset é mudança que ninguém pediu"
    )


# --- fakes de evdev + sysfs para a descoberta -------------------------------


def _instalar_evdev_fake(
    monkeypatch: pytest.MonkeyPatch,
    registry: dict[str, dict[str, Any]],
    aberturas: list[str] | None = None,
) -> None:
    """`evdev.list_devices`/`evdev.InputDevice` sobre um registro fake.

    `aberturas` (quando passada) registra CADA construção de `InputDevice` — é
    como se conta quantas vezes a descoberta abre cada node.
    """

    class _FakeDev:
        def __init__(self, path: str) -> None:
            if aberturas is not None:
                aberturas.append(path)
            spec = registry[path]
            self.path = path
            self.name = spec["name"]
            self.info = SimpleNamespace(
                vendor=spec["vid"], product=spec["pid"], bustype=spec["bus"]
            )
            self.uniq = spec.get("uniq", "")
            self._caps: dict[int, Any] = spec["caps"]

        def capabilities(self) -> dict[int, Any]:
            return self._caps

        def close(self) -> None: ...

    monkeypatch.setattr("evdev.list_devices", lambda: list(registry))
    monkeypatch.setattr("evdev.InputDevice", _FakeDev)


def _instalar_realpath_fake(
    monkeypatch: pytest.MonkeyPatch, device_dirs: dict[str, str]
) -> None:
    """`os.path.realpath` fake só para `/sys/class/input/<eventN>/device`."""
    real = os.path.realpath

    def fake(path: Any, **kw: Any) -> str:
        mapped = device_dirs.get(os.fspath(path))
        if mapped is not None:
            return mapped
        return real(path, **kw)

    monkeypatch.setattr("os.path.realpath", fake)


def _arvore_hid(
    tmp_path: Path, rel: str, driver: str | None, hidraw: str | None = None
) -> str:
    """Árvore sysfs mínima `<pai>/input/inputN`; devolve o dir do input device."""
    base = tmp_path / "sys" / "devices" / rel
    input_dir = base / "input" / f"input{abs(hash(rel)) % 1000}"
    input_dir.mkdir(parents=True)
    if driver is not None:
        drivers = tmp_path / "sys" / "bus" / "drivers" / driver
        drivers.mkdir(parents=True, exist_ok=True)
        (base / "driver").symlink_to(drivers)
    if hidraw is not None:
        (base / "hidraw" / hidraw).mkdir(parents=True)
    return str(input_dir)


DS_PATH = "/dev/input/event30"
PRO_PATH = "/dev/input/event42"
PRO_IMU_PATH = "/dev/input/event43"
VPAD_PATH = "/dev/input/event20"


def _mesa_de_tres(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, aberturas: list[str] | None = None
) -> None:
    """A mesa dela: um DualSense, um Pro, o nosso vpad e o IMU do Pro."""
    ds_dir = _arvore_hid(
        tmp_path, "bt/hci0/hci0:20/0005:054C:0CE6.0004", "playstation", "hidraw6"
    )
    pro_dir = _arvore_hid(
        tmp_path, "bt/hci0/hci0:21/0005:057E:2009.0007", "nintendo", "hidraw7"
    )
    imu_dir = _arvore_hid(
        tmp_path, "bt/hci0/hci0:21/0005:057E:2009.0008", "nintendo"
    )
    _instalar_evdev_fake(
        monkeypatch,
        {
            VPAD_PATH: {
                "name": "Hefesto Virtual DualSense P1",
                "vid": 0x054C,
                "pid": 0x0DF2,
                "bus": 0x03,
                "uniq": "",
                "caps": _caps_dualsense(),
            },
            DS_PATH: {
                "name": "DualSense Wireless Controller",
                "vid": 0x054C,
                "pid": 0x0CE6,
                "bus": 0x05,
                "uniq": MAC_DUALSENSE_FORJADO,
                "caps": _caps_dualsense(),
            },
            PRO_PATH: {
                "name": "Pro Controller",
                "vid": 0x057E,
                "pid": 0x2009,
                "bus": 0x05,
                "uniq": MAC_PRO_FORJADO,
                "caps": _caps_pro(),
            },
            PRO_IMU_PATH: {
                "name": "Pro Controller (IMU)",
                "vid": 0x057E,
                "pid": 0x2009,
                "bus": 0x05,
                "uniq": MAC_PRO_FORJADO,
                # Sem caps de gamepad: o nó de motion fica FORA da descoberta.
                "caps": {ecodes.EV_ABS: [(ecodes.ABS_X, FAIXA_PRO)]},
            },
        },
        aberturas,
    )
    _instalar_realpath_fake(
        monkeypatch,
        {
            "/sys/class/input/event20/device": "/sys/devices/virtual/input/input99",
            "/sys/class/input/event30/device": ds_dir,
            "/sys/class/input/event42/device": pro_dir,
            "/sys/class/input/event43/device": imu_dir,
        },
    )


# --- 4. a descoberta única --------------------------------------------------


def test_descoberta_unica_classifica_os_dois_lados_num_laco_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Uma chamada devolve DualSense e externo, cada node aberto UMA vez.

    A duplicação que a E2 mata é literal: dois laços abrindo todos os nodes.
    Contar as aberturas é o que impede a "descoberta única" de virar duas
    descobertas empilhadas num nome novo.
    """
    aberturas: list[str] = []
    _mesa_de_tres(tmp_path, monkeypatch, aberturas)

    gamepads = discover_gamepads()

    por_especie = {gp.especie: gp for gp in gamepads}
    assert len(gamepads) == 2, "uma entrada por PLÁSTICO (o IMU não é controle)"
    assert por_especie[ESPECIE_DUALSENSE].identidade == IDENT_DUALSENSE
    assert por_especie[ESPECIE_DUALSENSE].evdev_path == DS_PATH
    assert por_especie[ESPECIE_EXTERNAL].identidade == IDENT_PRO
    assert por_especie[ESPECIE_EXTERNAL].evdev_path == PRO_PATH
    assert por_especie[ESPECIE_EXTERNAL].driver == "nintendo"
    assert por_especie[ESPECIE_EXTERNAL].hidraw == "/dev/hidraw7"

    assert VPAD_PATH not in aberturas, "o vpad nem chega a ser aberto"
    assert sorted(aberturas) == sorted([DS_PATH, PRO_PATH, PRO_IMU_PATH]), (
        "algum node foi aberto duas vezes — a descoberta voltou a ser dois laços"
    )


def test_o_absinfo_de_cada_eixo_viaja_na_descoberta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A forma do eixo é o que decide se o controle é jogável — ela sai da
    descoberta junto com a identidade, não de uma tabela de VID/PID."""
    _mesa_de_tres(tmp_path, monkeypatch)

    por_especie = {gp.especie: gp for gp in discover_gamepads()}

    pro = por_especie[ESPECIE_EXTERNAL].eixos
    assert pro[ecodes.ABS_X].minimo == -32767
    assert pro[ecodes.ABS_X].maximo == 32767
    assert pro[ecodes.ABS_X].flat == 500, "a zona morta declarada pelo aparelho"
    assert ecodes.ABS_Z not in pro, "o Pro não publica gatilho analógico"

    dualsense = por_especie[ESPECIE_DUALSENSE].eixos
    assert dualsense[ecodes.ABS_Z].minimo == 0
    assert dualsense[ecodes.ABS_Z].maximo == 255


def test_as_duas_portas_antigas_mantem_o_contrato(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`discover_dualsense_evdevs` e `discover_external_gamepads` viraram vistas
    da descoberta única — e nenhum consumidor pode notar."""
    _mesa_de_tres(tmp_path, monkeypatch)

    assert discover_dualsense_evdevs() == {IDENT_DUALSENSE: Path(DS_PATH)}

    inventario = discover_external_gamepads()
    assert inventario == [
        {
            "name": "Pro Controller",
            "vid": "057e",
            "pid": "2009",
            "bus": "bluetooth",
            "uniq": MAC_PRO_FORJADO,
            "driver": "nintendo",
            "evdev_path": PRO_PATH,
            "hidraw": "/dev/hidraw7",
        }
    ]
    # Os consumidores MUTAM o dict (`holders`, identidade carimbada): cada
    # chamada tem de devolver objetos novos, nunca um cache compartilhado.
    inventario[0]["holders"] = {"steam_pids": [1]}
    assert "holders" not in discover_external_gamepads()[0]


# --- 5. o reencontro por identidade -----------------------------------------


def test_reencontro_acha_o_externo_depois_do_replug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`eventN` é volátil; a identidade é o que sobrevive. Sem isto o externo
    nunca mais é achado depois de um replug."""
    _mesa_de_tres(tmp_path, monkeypatch)
    reader = EvdevReader(device_path=Path(PRO_PATH), target_uniq=IDENT_PRO)
    assert reader._locate() == Path(PRO_PATH)

    # Replug: o kernel renumera o node do MESMO aparelho.
    novo_path = "/dev/input/event300"
    novo_dir = _arvore_hid(
        tmp_path, "bt/hci0/hci0:31/0005:057E:2009.0011", "nintendo", "hidraw9"
    )
    _instalar_evdev_fake(
        monkeypatch,
        {
            novo_path: {
                "name": "Pro Controller",
                "vid": 0x057E,
                "pid": 0x2009,
                "bus": 0x05,
                "uniq": MAC_PRO_FORJADO,
                "caps": _caps_pro(),
            }
        },
    )
    _instalar_realpath_fake(
        monkeypatch, {"/sys/class/input/event300/device": novo_dir}
    )

    assert reader._locate() == Path(novo_path), (
        "externo perdido depois do replug — o reencontro só olhava DualSense"
    )


def test_reencontro_do_dualsense_segue_igual_e_sem_alvo_nao_adota_ninguem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Com alvo DualSense o reencontro não mudou. **Sem** alvo, uma mesa só de
    externos devolve `None` — adotar um externo sem ninguém ter pedido seria
    adoção por acidente, e a adoção é a `E3`."""
    _mesa_de_tres(tmp_path, monkeypatch)

    com_alvo = EvdevReader(
        device_path=Path(DS_PATH), target_uniq=IDENT_DUALSENSE
    )
    assert com_alvo._locate() == Path(DS_PATH)

    pro_dir = _arvore_hid(
        tmp_path, "bt/hci0/hci0:41/0005:057E:2009.0013", "nintendo", "hidraw4"
    )
    _instalar_evdev_fake(
        monkeypatch,
        {
            PRO_PATH: {
                "name": "Pro Controller",
                "vid": 0x057E,
                "pid": 0x2009,
                "bus": 0x05,
                "uniq": MAC_PRO_FORJADO,
                "caps": _caps_pro(),
            }
        },
    )
    _instalar_realpath_fake(monkeypatch, {"/sys/class/input/event42/device": pro_dir})

    sem_alvo = EvdevReader(device_path=Path("/dev/input/event999"))
    assert sem_alvo._locate() is None, (
        "sem alvo o reader adotou um externo — isso é a E3, e ela é dela"
    )


# --- o portão anti-recaída da adoção ----------------------------------------


def test_a_e2_nao_adota_ninguem_o_coop_segue_fechado_em_dualsense() -> None:
    """O veto de 19/07 (*"externo não ganha controle virtual"*) foi ADIADO COM
    CONDIÇÃO, não derrubado: enquanto a máscara por controle não existir, ele
    vale. A E2 entrega a descoberta e o normalizador; quem promove jogador
    continua vendo só DualSense.

    Portão de TEXTO de propósito: a recaída aqui não é um valor errado, é uma
    linha nova no `want` — e ela passaria em qualquer teste de comportamento
    da E2.
    """
    coop = Path(er_mod.__file__).resolve().parents[1] / "daemon/subsystems/coop.py"
    fonte = coop.read_text(encoding="utf-8")

    assert "discover_dualsense_evdevs()" in fonte
    assert "discover_gamepads" not in fonte, (
        "o co-op passou a enxergar externos — isso é a E3, e ela precisa dela"
    )
    assert "discover_external_gamepads" not in fonte
