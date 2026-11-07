"""A mira vale em toda família com nó de movimento, e quem não tem aparece como ausente.

A tabela só leva o que se mediu: Pro e 8BitDo entram com os 3 s de gesto no aparelho.
Até lá, o nó é achado, a leitura aparece, a mira não anda e o chip recusa com frase. As réguas da
tabela usam uma linha de exemplo, só no teste.

MORDIDAS: tirar o `orientar` do `angulo_do_movimento` deixa o Pro andar com o eixo da Sony; a
família do 8BitDo sem o `id/version` vira Pro; o `mira.set` sem a pergunta grava no controle sem
nó, e o chip acende; o `_locate` pela lista só da Sony perde o Pro na reconexão.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import evdev_reader as er
from hefesto_dualsense4unix.core import roteador_de_movimento as rot
from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub
from hefesto_dualsense4unix.integrations.o_que_o_jogo_ve import PELO_HEFESTO
from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.testing import FakeController
from tests.unit.test_a_mira_vale_nos_quatro import _Mesa, P1, P2, P3, P4, QUATRO

_DIR = rot.DESTINO_ANALOGICO_DIREITO
_LINHA_DE_EXEMPLO = ((2, 1.0), (0, -1.0), (1, 1.0))
_NOME_PRO = "Nintendo Co., Ltd. Pro Controller"


@pytest.mark.parametrize(
    ("vendor", "product", "nome", "bcd", "familia"),
    [
        (0x054C, 0x0CE6, "DualSense Wireless Controller Motion Sensors", None, er.FAMILIA_SONY),
        (0x054C, 0x0DF2, "DualSense Edge Wireless Controller Motion Sensors", None,
         er.FAMILIA_SONY),
        (0x057E, 0x2009, f"{_NOME_PRO} (IMU)", 0x0210, er.FAMILIA_PRO),
        (0x057E, 0x2009, f"{_NOME_PRO} (IMU)", 0x0200, er.FAMILIA_8BITDO),
        (0x057E, 0x2009, _NOME_PRO, 0x0210, None),
        (0x054C, 0x0CE6, "DualSense Wireless Controller", None, None),
        (0x045E, 0x028E, "Xbox 360 Controller", None, None),
    ],
)
def test_a_familia_do_no(
    vendor: int, product: int, nome: str, bcd: int | None, familia: str | None
) -> None:
    assert er._familia_pela_identidade(vendor, product, nome, bcd) == familia


def test_a_descoberta_acha_toda_familia_e_deixa_o_virtual_de_fora(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nos = {
        "/dev/input/event3": (0x054C, 0x0CE6, "DualSense Wireless Controller Motion Sensors",
                              "aa:bb:cc:00:00:01"),
        "/dev/input/event4": (0x057E, 0x2009, f"{_NOME_PRO} (IMU)", "aa:bb:cc:00:00:02"),
        "/dev/input/event5": (0x057E, 0x2009, _NOME_PRO, "aa:bb:cc:00:00:02"),
        "/dev/input/event6": (0x054C, 0x0CE6, "DualSense Wireless Controller Motion Sensors",
                              "aa:bb:cc:00:00:03"),
    }
    monkeypatch.setattr(er, "_nos_de_evento", lambda _lista: sorted(nos))
    monkeypatch.setattr(er, "_identidade_no_sysfs", lambda p: nos.get(str(p)))
    monkeypatch.setattr(er, "_is_virtual_evdev", lambda p: str(p).endswith("event6"))
    achados = {str(v) for v in er.discover_motion_evdevs().values()}
    assert achados == {"/dev/input/event3", "/dev/input/event4"}


def test_a_reconexao_acha_o_no_pelo_endereco_em_qualquer_grafia(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(er, "discover_motion_evdevs",
                        lambda: {"aabbcc000002": Path("/dev/input/event4")})
    leitor = er.MotionSensorReader(device_path=Path("/dev/input/event9"), target_uniq=P2)
    assert leitor._locate() == Path("/dev/input/event4")


def test_o_leitor_real_guarda_a_familia_do_no_que_abriu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem isto o Pro de verdade andaria com a tabela da Sony: só o dublê diria o contrário."""
    monkeypatch.setattr(er, "familia_do_no_de_movimento", lambda _no: "pro")
    leitor = er.MotionSensorReader(device_path=None, target_uniq=P2)
    assert leitor.familia() is None
    leitor._on_device_opened(SimpleNamespace(
        path="/dev/input/event9", absinfo=lambda _c: SimpleNamespace(resolution=1)))
    assert leitor.familia() == "pro"


def test_o_que_nao_se_mediu_nao_entra_na_tabela() -> None:
    assert set(rot.ORIENTACAO_MEDIDA) == {"sony"}, "a tabela só leva família medida no aparelho"
    assert rot.orientar("pro", (1.0, 2.0, 3.0)) is None
    assert rot.orientar("8bitdo", (1.0, 2.0, 3.0)) is None
    vetor = (1.0, 2.0, 3.0)
    assert rot.orientar("sony", vetor) is vetor and rot.orientar(None, vetor) is vetor


def test_a_linha_da_tabela_vira_os_eixos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(rot.ORIENTACAO_MEDIDA, "pro", _LINHA_DE_EXEMPLO)
    assert rot.orientar("pro", (1.0, 2.0, 3.0)) == (3.0, -1.0, 2.0)


def _mesa_mista(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transporte: str, familias: dict[str, str]
) -> _Mesa:
    mesa = _Mesa(monkeypatch, tmp_path, transporte,
                 {uniq: {"destino": _DIR} for uniq in QUATRO})
    for uniq, familia in familias.items():
        mesa.nos[uniq].familia = lambda f=familia: f  # type: ignore[attr-defined]
    return mesa


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_mesa_mista_cada_um_com_a_tabela_da_sua_familia(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transporte: str
) -> None:
    monkeypatch.setitem(rot.ORIENTACAO_MEDIDA, "pro", _LINHA_DE_EXEMPLO)
    mesa = _mesa_mista(monkeypatch, tmp_path, transporte,
                       {P1: "sony", P2: "pro", P3: "8bitdo", P4: "sony"})
    assert mesa.gira(P1, (0.0, 180.0, 0.0))["rx"] < 128, "a Sony perdeu o eixo"
    no_do_pro = mesa.gira(P2, (0.0, 0.0, 180.0))
    assert no_do_pro["rx"] == 128 and no_do_pro["ry"] != 128, "o Pro andou pelo eixo da Sony"
    assert mesa.gira(P4, (0.0, -180.0, 0.0))["rx"] > 128, "a mesa misturada calou o P4"


def test_o_pro_andou_e_o_8bitdo_sem_medida_fica_no_centro(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setitem(rot.ORIENTACAO_MEDIDA, "pro", ((1, 1.0), (0, 1.0), (2, 1.0)))
    mesa = _mesa_mista(monkeypatch, tmp_path, "bt", {P2: "pro", P3: "8bitdo"})
    mesa.nos[P2].acel = (1.0, 0.0, 0.0)
    mesa.segundos(rot.SILENCIO_DA_DRENAGEM_S + 0.1)
    assert mesa.gira(P2, (180.0, 0.0, 0.0))["rx"] < 128, "o Pro não andou pela linha dele"
    mesa.nos[P3].giro = (0.0, 180.0, 0.0)
    mesa.tiques(4)
    assert mesa.pads[P3].centro(), "a família sem medida andou com o eixo da Sony"


def test_sem_medida_a_leitura_segue_viva(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    mesa = _mesa_mista(monkeypatch, tmp_path, "usb", {P3: "8bitdo"})
    mesa.nos[P3].giro = (1.0, 2.0, 3.0)
    assert mesa.hub.velocidade_do_movimento(P3) == (1.0, 2.0, 3.0)
    assert mesa.hub.angulo_do_movimento(P3) is None


@pytest.fixture
def perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _dir(ensure: bool = False) -> Path:
        return alvo

    monkeypatch.setattr(loader, "profiles_dir", _dir)
    return alvo


def _servidor(tmp_path: Path, familias: dict[str, str | None]) -> IpcServer:
    loader.save_profile(Profile(name="Ensaio", match=MatchAny(type="any")))
    controle = FakeController(transport="usb")  # type: ignore[arg-type]
    controle.primary_uniq = P1  # type: ignore[attr-defined]
    daemon = Daemon(controller=controle)
    daemon.external_registry = SimpleNamespace(snapshot_connected=lambda: {P2, P3, P4})
    gerente = ProfileManager(controller=controle, store=daemon.store)
    servidor = IpcServer(
        controller=controle, store=daemon.store, profile_manager=gerente,
        socket_path=tmp_path / "p.sock", daemon=daemon,
    )
    servidor._sensor_hub = SensorHub(
        descobrir_motion=lambda: {u.replace(":", ""): Path(f"/dev/input/{u}")
                                  for u, f in familias.items() if f},
        descobrir_touch=dict, descobrir_gamepad=dict, auto_manutencao=False,
        familia_do_no=lambda no: familias.get(Path(str(no)).name),
    )
    daemon._ipc_server = servidor
    daemon.store.set_active_profile("Ensaio")
    return servidor


def _set(servidor: IpcServer, **params: Any) -> dict[str, Any]:
    return asyncio.run(servidor._handlers["mira.set"](params))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("uniq", "frase"),
    [(P2, "não tem sensor de movimento"), (P3, "não vale neste controle")],
)
@pytest.mark.parametrize("pedido", [{"ligada": True}, {"lado": _DIR}])
def test_o_chip_recusa_com_frase_e_nada_vai_ao_disco(
    perfis: Path, tmp_path: Path, uniq: str, frase: str, pedido: dict[str, Any]
) -> None:
    servidor = _servidor(tmp_path, {P3: "8bitdo"})
    corpo = _set(servidor, uniq=uniq, **pedido)
    assert corpo["status"] == "sem_movimento" and frase in corpo["motivo"]
    assert not loader.load_profile("Ensaio").controllers


def test_o_controle_medido_e_o_dualsense_ligam(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(rot.ORIENTACAO_MEDIDA, "pro", _LINHA_DE_EXEMPLO)
    servidor = _servidor(tmp_path, {P4: "pro"})
    assert _set(servidor, uniq=P4, ligada=True)["status"] == "ok"
    assert _set(servidor, uniq=P1, ligada=True)["status"] == "ok"


def test_apagar_e_ajustar_nao_perguntam_pelo_movimento(perfis: Path, tmp_path: Path) -> None:
    servidor = _servidor(tmp_path, {})
    assert _set(servidor, uniq=P2, ligada=False)["status"] == "ok"
    assert _set(servidor, uniq=P2, sensibilidade_h=7)["status"] == "ok"


def test_na_mira_da_mesa_o_chip_de_quem_nao_tem_no_fica_apagado(
    perfis: Path, tmp_path: Path
) -> None:
    servidor = _servidor(tmp_path, {})
    rot.definir_ativo(servidor.store, rot.ArranjoDeMovimento(destino=_DIR))
    entradas: list[dict[str, Any]] = [{"uniq": P1}, {"uniq": P2}]
    servidor._merge_mira(entradas)
    assert entradas[0]["mira"]["virtual"] is True
    assert entradas[1]["mira"]["virtual"] is False
    assert entradas[1]["mira"]["ligada"] is False
    assert entradas[1]["mira"]["destino"] == rot.DESTINO_NENHUM


def test_a_rampa_recusa_quem_a_mira_nao_move(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    servidor = _servidor(tmp_path, {})
    rot.definir_ativo(servidor.store, rot.ArranjoDeMovimento(destino=_DIR))
    monkeypatch.setattr(REGISTRO, "jogo_aberto", lambda: True)
    corpo = asyncio.run(servidor._handlers["motion.rampa"]({"uniq": P2, "pedido": "comecar"}))
    assert corpo["status"] == "sem_mira"
    assert asyncio.run(
        servidor._handlers["motion.rampa"]({"uniq": P1, "pedido": "comecar"})
    )["status"] == "subindo"
    rot.parar_a_rampa(servidor.store, P1, 0.0)


def test_quem_nao_tem_no_nao_diz_que_o_giro_chega_ao_jogo(perfis: Path, tmp_path: Path) -> None:
    servidor = _servidor(tmp_path, {})
    rot.definir_ativo(servidor.store, rot.ArranjoDeMovimento(destino=_DIR))
    pad = SimpleNamespace(flavor="xbox", backend="uinput")
    chave = "funcoes"  # (noqa-acento)
    assert servidor._o_que_o_jogo_ve_de(pad, P1, "usb")[chave]["giroscopio"] == PELO_HEFESTO
    assert servidor._o_que_o_jogo_ve_de(pad, P2, "usb")[chave]["giroscopio"] != PELO_HEFESTO


def test_o_estado_nao_paga_o_sysfs_a_cada_volta(perfis: Path, tmp_path: Path) -> None:
    servidor = _servidor(tmp_path, {})
    rot.definir_ativo(servidor.store, rot.ArranjoDeMovimento(destino=_DIR))
    voltas = {"n": 0}
    descobrir = servidor._sensor_hub._descobrir_motion

    def contada() -> dict[str, Any]:
        voltas["n"] += 1
        return descobrir()

    servidor._sensor_hub._descobrir_motion = contada
    for _ in range(50):
        servidor._merge_mira([{"uniq": P2}])
    assert voltas["n"] == 1


def test_a_tela_diz_a_frase_de_quem_recusou() -> None:
    with pytest.raises(RuntimeError, match="não tem sensor"):
        a02._recusa_da_mira({"status": "sem_movimento",
                             "motivo": "Este controle não tem sensor de movimento neste modo"})
    a02._recusa_da_mira({"status": "ok"})
