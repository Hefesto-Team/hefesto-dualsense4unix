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


def _inventario(*uniqs: str) -> list[dict[str, Any]]:
    return [{"name": "Controle de fora", "vid": "2dc8", "pid": "6003", "bus": "usb", "uniq": u,
             "driver": "hid-generic", "player_slot": 2 + n} for n, u in enumerate(uniqs)]


def test_o_inventario_dos_externos_leva_o_bloco_da_mira(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-1911-A-MIRA-DO-CONTROLE-DE-FORA-TEM-DOIS-BOTOES: o `controller.list` do externo diz se a
    mira anda e por que não, pelo dono do `mira.set`.

    MORDIDA: tirar o `_merge_mira` do `controller.list` deixa o externo sem o bloco.
    """
    from hefesto_dualsense4unix.daemon import ipc_handlers

    monkeypatch.setitem(rot.ORIENTACAO_MEDIDA, "pro", _LINHA_DE_EXEMPLO)
    servidor = _servidor(tmp_path, {P3: "8bitdo", P4: "pro"})
    rot.definir_ativo(servidor.store, rot.ArranjoDeMovimento(destino=_DIR))
    monkeypatch.setattr(ipc_handlers, "_external_inventory",
                        lambda *_a, **_k: _inventario(P2, P3, P4))
    lista = asyncio.run(servidor._handlers["controller.list"]({"external": True}))["external"]
    mira = {e["uniq"]: e["mira"] for e in lista}
    assert mira[P2]["motivo"] == rot.FRASE_SEM_SENSOR and mira[P2]["virtual"] is False
    assert mira[P3]["motivo"] == rot.FRASE_SEM_MEDIDA and mira[P3]["virtual"] is False
    assert "motivo" not in mira[P4] and mira[P4]["virtual"] is True and mira[P4]["lado"] == _DIR


def _externo(uniq: str, **mira: Any) -> dict[str, Any]:
    entrada = _inventario(uniq)[0]
    return {**entrada, "mira": {"ligada": False, "virtual": False, "lado": _DIR, **mira}}


def _botoes_da_mira(html: str) -> list[tuple[str, bool, bool]]:
    import re

    return [(lado, "chip-virtual on" in chip, 'aria-disabled="true"' in chip)
            for chip, lado in re.findall(
                r'(<span class="chip-virtual[^"]*"><button.*?data-lado="(\w+)".*?</span>)', html)]


def test_o_cartao_do_externo_tem_os_dois_botoes_da_mira() -> None:
    """D-1911-A-MIRA-DO-CONTROLE-DE-FORA-TEM-DOIS-BOTOES: um botão por analógico em todo
    controle de fora com sensor; sem medida ele fica cinza e a linha diz por quê.

    MORDIDA: tirar o `mira_do_externo` do `_html_dos_externos` apaga os botões e a linha.
    """
    from hefesto_dualsense4unix.interface.pacotes import Contexto
    from hefesto_dualsense4unix.interface.pacotes import a01_jogar as jogar

    esq = "analogico_esquerdo"
    externos = [
        _externo(P2, motivo=rot.FRASE_SEM_SENSOR),
        _externo(P3, motivo=rot.FRASE_SEM_MEDIDA),
        _externo(P4, ligada=True, virtual=True),
    ]
    ctx = Contexto(state={}, mesa=[], conectados=[], externos=externos)
    cartoes = jogar._html_dos_externos(ctx).split('<div class="ext-cartao"')[1:]
    assert len(cartoes) == 3
    assert "ext-mira" not in cartoes[0], "sem sensor não há botão"
    assert _botoes_da_mira(cartoes[1]) == [(esq, False, True), (_DIR, False, True)]
    assert a02.AVISO_DA_MIRA_SEM_MEDIDA in cartoes[1]
    assert rot.FRASE_SEM_MEDIDA in cartoes[1], "a frase do daemon é a dica do botão"
    assert _botoes_da_mira(cartoes[2]) == [(esq, False, False), (_DIR, True, False)]
    assert a02.AVISO_DA_MIRA_SEM_MEDIDA not in cartoes[2]
    assert f'data-uniq="{P4}"' in cartoes[2], "o clique tem de dizer de qual controle é"


def test_o_cartao_sem_o_bloco_da_mira_nao_leva_botao() -> None:
    """O daemon que não respondeu à mira não ganha botão inventado: nada se pinta sem leitura."""
    assert a02.mira_do_externo(_inventario(P4)[0]) == ("", "")


class _PonteDaMira:
    def __init__(self, corpo: dict[str, Any]) -> None:
        self.corpo = corpo
        self.chamadas: list[dict[str, Any]] = []

    def mira_set_detalhado(self, **kw: Any) -> dict[str, Any]:
        self.chamadas.append(kw)
        return self.corpo


def _clicar(externo: dict[str, Any], lado: str, corpo: dict[str, Any]) -> _PonteDaMira:
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    ponte = _PonteDaMira(corpo)
    ctx = Contexto(state={}, mesa=[], conectados=[], externos=[externo])
    a02.analogico_lado(ctx, {"uniq": externo["uniq"], "lado": lado}, ponte)
    return ponte


def test_o_clique_no_botao_do_externo_liga_o_lado_e_no_aceso_desliga() -> None:
    """D-1911-A-MIRA-DO-CONTROLE-DE-FORA-TEM-DOIS-BOTOES: o botão apagado liga o lado dele, o
    aceso desliga a mira.

    MORDIDA: tirar o `_dele` do `analogico_lado` faz o aceso religar o lado em vez de desligar.
    """
    ok = {"status": "ok"}
    apagado = _clicar(_externo(P4), _DIR, ok)
    assert apagado.chamadas == [{"lado": _DIR, "uniq": P4}]
    aceso = _clicar(_externo(P4, ligada=True, virtual=True), _DIR, ok)
    assert aceso.chamadas == [{"ligada": False, "uniq": P4}]


def test_o_clique_no_botao_cinza_do_externo_diz_a_frase_e_nao_acende() -> None:
    corpo = {"status": "sem_movimento", "motivo": rot.FRASE_SEM_MEDIDA}
    with pytest.raises(RuntimeError, match="não vale neste controle"):
        _clicar(_externo(P3, motivo=rot.FRASE_SEM_MEDIDA), _DIR, corpo)
