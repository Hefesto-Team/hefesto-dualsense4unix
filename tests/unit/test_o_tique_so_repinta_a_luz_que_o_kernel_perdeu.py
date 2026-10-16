"""O tique de 30 s só repinta a luz que o kernel perdeu.

O-TIQUE-DE-30-S-SO-REPINTA-A-LUZ-QUE-O-KERNEL-PERDEU-01.

Quatro controles num `/sys` falso, no molde da régua da reconexão: o Starlight Blue e o White
no cabo, o Cosmic Red e o Galactic Purple no rádio. O espião conta as escritas na classe LED e
os reports que saem pelo handle (`0x02` do cabo, `0x31` do rádio).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from hefesto_dualsense4unix.core import sysfs_leds
from hefesto_dualsense4unix.core.backend_pydualsense import (
    PyDualSenseController,
    _DesiredOutput,
)
from tests.unit.test_backend_multi_controller import _FakeHandle, _null_evdev

# A faixa forjada da casa (aa:bb:cc), nunca endereço de aparelho.
STARLIGHT = "AA:BB:CC:00:00:01"
WHITE = "AA:BB:CC:00:00:02"
COSMIC = "AA:BB:CC:00:00:03"
GALACTIC = "AA:BB:CC:00:00:04"
DO_CABO = (STARLIGHT, WHITE)
DO_RADIO = (COSMIC, GALACTIC)
TODOS = (*DO_CABO, *DO_RADIO)
PREFIXO = {STARLIGHT: "input801", WHITE: "input802", COSMIC: "input803", GALACTIC: "input804"}
COR = {
    STARLIGHT: (0, 64, 255),
    WHITE: (255, 255, 255),
    COSMIC: (255, 0, 0),
    GALACTIC: (128, 0, 255),
}
NUMERO = {
    STARLIGHT: (False, False, True, False, False),
    WHITE: (False, True, False, True, False),
    COSMIC: (True, False, True, False, True),
    GALACTIC: (True, True, False, True, True),
}
AZUL_DO_KERNEL = "0 0 128"


class _Handle(_FakeHandle):
    """Handle aberto que guarda cada report que sai por ele."""

    def __init__(self, transporte: str) -> None:
        super().__init__(transport_name=transporte)
        self.reports: list[bytes] = []

    def writeReport(self, report: list[int]) -> int:  # noqa: N802 — API pydualsense
        self.reports.append(bytes(report))
        return len(report)

    def de(self, report_id: int) -> list[bytes]:
        return [r for r in self.reports if r and r[0] == report_id]


def _monta_no(raiz: Path, key: str) -> None:
    """O nó LED de um controle no layout do kernel: a barra e os cinco do número."""
    prefixo = PREFIXO[key]
    dev = raiz / "devices" / prefixo
    dev.mkdir(parents=True)
    (dev / "uevent").write_text(f"HID_UNIQ={key}\n")
    classe = raiz / "class" / "leds"
    classe.mkdir(parents=True, exist_ok=True)
    indicador = dev / "leds" / f"{prefixo}:rgb:indicator"
    indicador.mkdir(parents=True)
    (indicador / "multi_intensity").write_text(AZUL_DO_KERNEL)
    (indicador / "brightness").write_text("255")
    (classe / indicador.name).symlink_to(indicador)
    for i in range(1, 6):
        luz = dev / "leds" / f"{prefixo}:white:player-{i}"
        luz.mkdir(parents=True)
        (luz / "brightness").write_text("0")
        (classe / luz.name).symlink_to(luz)


class _Espiao:
    """As escritas REAIS na classe LED: `(prefixo, arquivo, dado)`."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.escritas: list[tuple[str, str, str]] = []
        original = sysfs_leds.SysfsLedNode._write

        def espiar(path: str, data: str) -> bool:
            ok = original(path, data)
            pasta = Path(path).parent.name
            self.escritas.append((pasta.split(":", 1)[0], Path(path).name, data))
            return ok

        monkeypatch.setattr(sysfs_leds.SysfsLedNode, "_write", staticmethod(espiar))

    def da_barra(self, key: str) -> list[str]:
        return [
            d for p, arq, d in self.escritas
            if p == PREFIXO[key] and arq == "multi_intensity"
        ]

    def do_numero(self, key: str) -> list[str]:
        return [
            d for p, arq, d in self.escritas
            if p == PREFIXO[key] and arq == "brightness"
        ]


@pytest.fixture
def mesa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[PyDualSenseController, dict[str, _Handle], _Espiao, Path]:
    raiz = tmp_path / "sys"
    for key in TODOS:
        _monta_no(raiz, key)
    monkeypatch.setattr(sysfs_leds, "LEDS_ROOT", str(raiz / "class" / "leds"))
    inst = PyDualSenseController(evdev_reader=_null_evdev())
    handles = {key: _Handle("USB" if key in DO_CABO else "BT") for key in TODOS}
    inst._handles = dict(handles)  # type: ignore[arg-type]
    inst._primary_key = STARLIGHT
    inst._desired_default = _DesiredOutput(player_led_brightness=1)
    for key in TODOS:
        uniq = inst._key_to_uniq(key)
        assert uniq is not None
        inst._desired_by_uniq[uniq] = _DesiredOutput(led=COR[key], player_leds=NUMERO[key])
    espiao = _Espiao(monkeypatch)
    return inst, handles, espiao, raiz


def _connect(inst: PyDualSenseController) -> None:
    """Uma volta do laço de reconexão com os quatro no ar, pelos mesmos nós."""
    want = [(key, f"/dev/hidraw{i}".encode(), False) for i, key in enumerate(TODOS)]
    with patch.object(
        PyDualSenseController, "_enumerate_device_keys", return_value=want
    ), patch(
        "hefesto_dualsense4unix.integrations.radio_da_mesa.adaptador_por_uniq",
        return_value={},
    ):
        inst.connect()


def _limpar(handles: dict[str, _Handle], espiao: _Espiao) -> None:
    espiao.escritas.clear()
    for handle in handles.values():
        handle.reports.clear()


def _no_do(raiz: Path, key: str) -> Path:
    prefixo = PREFIXO[key]
    return raiz / "devices" / prefixo / "leds" / f"{prefixo}:rgb:indicator" / "multi_intensity"


def _texto(rgb: tuple[int, int, int]) -> str:
    return " ".join(str(c) for c in rgb)


def test_o_primeiro_tique_pinta_os_quatro(mesa: Any) -> None:
    """A base: a mesa que nasce recebe cor e número em todos, pelo cabo e pelo rádio."""
    inst, handles, _espiao, raiz = mesa
    _connect(inst)
    for key in TODOS:
        assert _no_do(raiz, key).read_text() == _texto(COR[key]), key
    for key in DO_RADIO:
        assert handles[key].de(0x31), f"o rádio de {key} não recebeu o 0x31"


def test_o_segundo_tique_sem_mudanca_nao_escreve_nada(mesa: Any) -> None:
    """Dois `connect()` seguidos sem mudança: o segundo não manda um report sequer."""
    inst, handles, espiao, _raiz = mesa
    _connect(inst)
    _limpar(handles, espiao)
    _connect(inst)
    assert espiao.escritas == [], (
        "o tique de 30 s reescreveu a classe LED sem a cor ter mudado: cada escrita é um "
        f"output report do kernel (escritas: {espiao.escritas})"
    )
    for key in DO_CABO:
        assert handles[key].de(0x02) == [], f"o brilho do cabo saiu de novo em {key}"
    for key in DO_RADIO:
        assert handles[key].de(0x31) == [], f"o 0x31 saiu de novo em {key}"


def test_o_no_segue_o_mesmo_objeto_entre_os_tiques(mesa: Any) -> None:
    """O mecanismo do teste acima: mesmo handle e mesmo nó, o mesmo objeto (e a memória dele)."""
    inst, _handles, _espiao, _raiz = mesa
    _connect(inst)
    antes = dict(inst._sysfs)
    _connect(inst)
    for key in TODOS:
        assert inst._sysfs[key] is antes[key], f"o nó de {key} nasceu de novo no tique"


def test_o_kernel_que_perdeu_a_cor_do_radio_ganha_a_cor_de_volta(mesa: Any) -> None:
    """O wake: o kernel devolve o nó do Cosmic Red ao azul dele, o handle segue o mesmo."""
    inst, handles, espiao, raiz = mesa
    _connect(inst)
    _connect(inst)
    _limpar(handles, espiao)
    _no_do(raiz, COSMIC).write_text(AZUL_DO_KERNEL)
    _connect(inst)
    assert espiao.da_barra(COSMIC) == [_texto(COR[COSMIC])], (
        "a barra ficou no azul do kernel: a divergência lida não fez o nó esquecer "
        f"(escritas: {espiao.escritas})"
    )
    assert len(handles[COSMIC].de(0x31)) == 1, "o rádio não repintou pelo 0x31"
    for key in TODOS:
        if key == COSMIC:
            continue
        assert espiao.da_barra(key) == [], f"{key} foi repintado sem ter perdido nada"
        assert handles[key].reports == [], f"{key} recebeu report sem ter perdido nada"


def test_o_kernel_que_perdeu_a_cor_do_cabo_ganha_a_cor_de_volta(mesa: Any) -> None:
    """Quem escreve na classe por fora (ou o kernel) no cabo: o tique devolve a cor resolvida."""
    inst, handles, espiao, raiz = mesa
    _connect(inst)
    _limpar(handles, espiao)
    _no_do(raiz, WHITE).write_text("0 255 0")
    _connect(inst)
    assert espiao.da_barra(WHITE) == [_texto(COR[WHITE])]
    assert espiao.da_barra(STARLIGHT) == []


def test_no_modo_nativo_a_divergencia_repinta_pelo_no_sem_report_cru(mesa: Any) -> None:
    """Sob o mudo do Modo Nativo o nó repinta e nenhum report cru sai por baixo do jogo."""
    inst, handles, espiao, raiz = mesa
    _connect(inst)
    inst.set_output_mute(True)
    _limpar(handles, espiao)
    _no_do(raiz, GALACTIC).write_text(AZUL_DO_KERNEL)
    _connect(inst)
    assert espiao.da_barra(GALACTIC) == [_texto(COR[GALACTIC])]
    for key in TODOS:
        assert handles[key].reports == [], f"report cru saiu sob o mudo em {key}"


def test_com_o_cache_quente_o_vigia_escreve_barra_e_numero_nos_quatro(mesa: Any) -> None:
    """O vigia do sequestro escreve SEMPRE: o cache do tique não o cala."""
    inst, handles, espiao, _raiz = mesa
    _connect(inst)
    _connect(inst)
    _limpar(handles, espiao)
    uniqs = [inst._key_to_uniq(key) for key in TODOS]
    resultado = inst.reafirmar_barra_e_numero([u for u in uniqs if u])
    assert set(resultado) == set(TODOS)
    for key in DO_CABO:
        assert espiao.da_barra(key) == [_texto(COR[key])], key
        assert len(espiao.do_numero(key)) >= 5, f"o número de {key} não foi reescrito"
        assert len(handles[key].de(0x02)) == 1, f"o brilho do cabo não saiu em {key}"
    for key in DO_RADIO:
        assert len(handles[key].de(0x31)) == 1, key


def test_o_brilho_do_cabo_sai_quando_o_degrau_muda(mesa: Any) -> None:
    """O brilho das luzes do cabo só sai quando o degrau daquele controle mudou."""
    inst, handles, espiao, _raiz = mesa
    _connect(inst)
    _limpar(handles, espiao)
    inst._desired_default = _DesiredOutput(player_led_brightness=2)
    _connect(inst)
    for key in DO_CABO:
        assert len(handles[key].de(0x02)) == 1, f"o degrau novo não chegou a {key}"


def test_o_handle_novo_ganha_no_novo_e_repinta(mesa: Any) -> None:
    """A reconexão do White por outro handle, pelo mesmo nó: nó sem memória; os outros seguem."""
    inst, handles, espiao, _raiz = mesa
    _connect(inst)
    antes = dict(inst._sysfs)
    _limpar(handles, espiao)
    novo = _Handle("USB")
    inst._handles[WHITE] = novo  # type: ignore[assignment]
    _connect(inst)
    assert inst._sysfs[WHITE] is not antes[WHITE]
    assert espiao.da_barra(WHITE) == [_texto(COR[WHITE])]
    assert inst._sysfs[STARLIGHT] is antes[STARLIGHT]
    assert espiao.da_barra(STARLIGHT) == []


def test_o_numero_tem_memoria_e_o_invalidate_esquece(tmp_path: Path) -> None:
    """`set_players` igual ao último não escreve; `invalidate_cache` faz escrever de novo."""
    luzes = []
    for i in range(1, 6):
        d = tmp_path / f"p:white:player-{i}"
        d.mkdir()
        (d / "brightness").write_text("0")
        luzes.append(str(d))
    (tmp_path / "ind").mkdir()
    no = sysfs_leds.SysfsLedNode(str(tmp_path / "ind"), luzes)
    escritas: list[str] = []
    original = no._write

    def contar(path: str, data: str) -> bool:
        escritas.append(path)
        return original(path, data)

    no._write = contar  # type: ignore[method-assign]
    bits = (True, False, True, False, True)
    assert no.set_players(bits)
    assert len(escritas) == 5
    assert no.set_players(bits)
    assert len(escritas) == 5, "o número igual ao último foi reescrito"
    assert no.set_players((False,) * 5)
    assert len(escritas) == 10
    no.invalidate_cache()
    assert no.set_players((False,) * 5)
    assert len(escritas) == 15, "o invalidate_cache não fez o número escrever de novo"


@pytest.mark.parametrize("key", [WHITE, COSMIC])
def test_o_quadro_do_efeito_que_nos_pintamos_nao_conta_como_luz_perdida(
    mesa: Any, key: str
) -> None:
    """O efeito da luz (respirar, arco-íris) pinta quadros no nó sem lembrá-los no desejado: a
    cor lida é a do último quadro, NOSSA, e o tique não a toma por luz que o kernel perdeu.
    O número e o brilho do cabo não saem de novo; a barra volta à cor resolvida pelo reassert.
    """
    inst, handles, espiao, raiz = mesa
    _connect(inst)
    _connect(inst)
    uniq = inst._key_to_uniq(key)
    assert uniq is not None
    quadro = (10, 20, 30)
    assert inst.pintar_a_barra_sem_lembrar(uniq, quadro)
    assert _no_do(raiz, key).read_text() == _texto(quadro)
    esqueceu: list[tuple[str, bool]] = []
    original = inst._esquecer_a_luz_que_o_kernel_perdeu

    def contar(k: str, *args: Any) -> bool:
        resultado = original(k, *args)
        esqueceu.append((k, resultado))
        return resultado

    inst._esquecer_a_luz_que_o_kernel_perdeu = contar  # type: ignore[method-assign]
    _limpar(handles, espiao)
    _connect(inst)
    assert (key, True) not in esqueceu, (
        "o quadro do efeito, escrito por nós, virou «lightbar_perdida_repintada» no tique"
    )
    assert espiao.do_numero(key) == [], f"o número de {key} saiu de novo sem ter sido perdido"
    if key in DO_CABO:
        assert handles[key].de(0x02) == [], f"o brilho do cabo saiu de novo em {key}"
    assert espiao.da_barra(key) == [_texto(COR[key])], "a barra não voltou à cor resolvida"
