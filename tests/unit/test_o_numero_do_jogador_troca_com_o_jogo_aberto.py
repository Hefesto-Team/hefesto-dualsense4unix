"""O número do jogador troca pela tela com o jogo aberto (23/11/2026).

D-2311-O-NUMERO-DO-JOGADOR-TROCA-PELA-TELA-COM-O-JOGO-ABERTO: o `identity.number.set` vale com o
jogo na autoridade, para todo chamador, e o número que o jogo escreveu nas lâmpadas não desfaz o
pedido da tela até o jogo fechar. As outras recusas ficam, e o gesto da aba Iluminação levanta com
a frase da recusa (é o levantar que põe a linha `[gesto falhou]` no registro da interface).

Dois ensaios. O do serviço: o `IpcServer` real com os dois registros de identidade reais num
`config_dir` de mentira. O do co-op: o `CoopManager` real com os leitores e os vpads falsos da
STEAM-NO-FISICO-01 e o registro de número de `test_o_numero_do_jogo_vira_o_do_hefesto`, com a
máscara do vpad seguindo a pedida.

MORDIDAS: a recusa `sessao_de_jogo_aberta` de volta ao handler reprova os casos do serviço; sem
o pedido guardado no co-op, o número do jogo desfaz a troca no `sync` seguinte; o handler sem a
marca do pedido reprova o caminho inteiro; sem o quadro neutro em `_derrubar_para_renascer`, o
pad que sai leva o botão apertado.
"""
from __future__ import annotations

import asyncio
import itertools
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems import external_identity as ei_mod
from hefesto_dualsense4unix.daemon.subsystems import external_mask  # noqa: F401
from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    ExternalIdentityRegistry,
)
from hefesto_dualsense4unix.daemon.subsystems.identity import ControllerIdentityRegistry
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController
from tests.unit.test_o_numero_do_jogo_vira_o_do_hefesto import (  # noqa: F401
    _daemon,
    _Registro,
    registro,
)
from tests.unit.test_steam_no_fisico_01_o_jogo_ve_p1_a_p4 import (  # noqa: F401
    P1,
    P2,
    P3,
    P4,
    _Vpad,
    nascimentos,
)

BOOT = "boot-numero-2311"
DUALSENSE = ["aabbcc000011", "aabbcc000012", "aabbcc000013", "aabbcc000014"]
EXTERNOS = ["aabbcc0000e1", "aabbcc0000e2"]
MASCARAS = ("dualsense", "xbox", "nintendo")


@dataclass
class _Daemon:
    display_authority: str = "game"
    identity_registry: Any = None
    external_registry: Any = None
    _coop_manager: Any = None


@pytest.fixture
def config_isolado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from hefesto_dualsense4unix.utils import xdg_paths

    def _config_dir(ensure: bool = False) -> Path:
        if ensure:
            tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    monkeypatch.setattr(xdg_paths, "config_dir", _config_dir)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: BOOT)
    monkeypatch.setattr(ei_mod, "_read_boot_id", lambda: BOOT)
    return tmp_path


def _a_mesa(ds_n: int, ext_n: int) -> tuple[ControllerIdentityRegistry, ExternalIdentityRegistry]:
    """`ds_n` DualSense (cabo ou rádio: o número mora no endereço) e `ext_n` controles de fora."""
    ds = ControllerIdentityRegistry()
    ext = ExternalIdentityRegistry()
    ds.set_external_reserve_provider(lambda: set(ext.snapshot().values()))
    ds.sync_connected(DUALSENSE[:ds_n])
    for mac in EXTERNOS[:ext_n]:
        ext.slot_for(mac, reserve=max([*ds.snapshot().values(), *ext.snapshot().values()],
                                      default=0))
    ext.sync_connected(EXTERNOS[:ext_n])
    return ds, ext


def _servidor(tmp: Path, ds: Any, ext: Any, autoridade: str = "game") -> IpcServer:
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    return IpcServer(
        controller=fc,
        store=store,
        profile_manager=ProfileManager(controller=fc, store=store),
        socket_path=tmp / "n.sock",
        daemon=_Daemon(display_authority=autoridade, identity_registry=ds,
                       external_registry=ext),
    )


def _numeros(ds: Any, ext: Any) -> dict[str, int]:
    """O número exibido de cada presente: a colocação do lugar dele na fila única."""
    lugares = {**ds.snapshot(), **ext.snapshot()}
    presentes = [k for k in lugares if k in {*DUALSENSE, *EXTERNOS}]
    ordem = sorted(presentes, key=lambda k: lugares[k])
    return {k: i + 1 for i, k in enumerate(ordem)}


@pytest.mark.asyncio
async def test_jogo_aberto_dois_controles_o_2_vai_a_quem_e_o_1(config_isolado: Path) -> None:
    """D-2311-O-NUMERO-DO-JOGADOR-TROCA-PELA-TELA-COM-O-JOGO-ABERTO."""
    ds, ext = _a_mesa(2, 0)
    server = _servidor(config_isolado, ds, ext)

    resposta = await server._handle_identity_number_set({"uniq": DUALSENSE[0], "number": 2})

    assert resposta["ok"] is True, resposta
    assert _numeros(ds, ext) == {DUALSENSE[1]: 1, DUALSENSE[0]: 2}


MESAS = [(ds_n, ext_n) for ds_n in range(1, 5) for ext_n in range(0, 3)
         if 2 <= ds_n + ext_n <= 4]


@pytest.mark.parametrize(("ds_n", "ext_n"), MESAS)
@pytest.mark.asyncio
async def test_toda_mesa_de_dois_a_quatro_troca_de_p1_a_p4_com_o_jogo(
    config_isolado: Path, ds_n: int, ext_n: int
) -> None:
    """D-2311-O-NUMERO-DO-JOGADOR-TROCA-PELA-TELA-COM-O-JOGO-ABERTO: cada controle, cada número."""
    for chaves in itertools.product(range(ds_n + ext_n), range(1, ds_n + ext_n + 1)):
        (config_isolado / "controllers.json").unlink(missing_ok=True)
        ds, ext = _a_mesa(ds_n, ext_n)
        antes = _numeros(ds, ext)
        alvo = sorted(antes, key=antes.__getitem__)[chaves[0]]
        pedido = chaves[1]
        dono = next(k for k, n in antes.items() if n == pedido)
        server = _servidor(config_isolado, ds, ext)

        resposta = await server._handle_identity_number_set({"uniq": alvo, "number": pedido})

        assert resposta["ok"] is True, (alvo, pedido, resposta)
        depois = _numeros(ds, ext)
        esperado = dict(antes)
        esperado[alvo], esperado[dono] = pedido, antes[alvo]
        assert depois == esperado, (alvo, pedido)


@pytest.mark.asyncio
async def test_as_outras_recusas_ficam_com_o_jogo_aberto(config_isolado: Path) -> None:
    ds, ext = _a_mesa(2, 0)
    ds.sync_connected([DUALSENSE[0]])
    server = _servidor(config_isolado, ds, ext)

    ausente = await server._handle_identity_number_set({"uniq": DUALSENSE[1], "number": 1})
    fora = await server._handle_identity_number_set({"uniq": DUALSENSE[0], "number": 3})

    assert ausente == {"ok": False, "reason": "controle_ausente"}
    assert fora["ok"] is False and fora["reason"] == "numero_fora_da_mesa"


@pytest.mark.parametrize("razao", ["controle_ausente", "numero_fora_da_mesa", "lock_timeout"])
def test_a_recusa_vira_o_levantar_do_gesto_que_poe_a_linha(
    razao: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A janela escreve `[gesto falhou] 04-iluminacao.html · player: <frase>` quando o gesto
    levanta; o gesto levanta com a frase de toda recusa que sobrou."""
    from hefesto_dualsense4unix.app import ipc_bridge
    from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao

    monkeypatch.setattr(ipc_bridge, "_safe_call",
                        lambda *_a, **_k: (True, {"ok": False, "reason": razao}))
    monkeypatch.setattr(a04_iluminacao, "_nao_no_automatico", lambda _ctx: None)
    monkeypatch.setattr(a04_iluminacao, "_uniq", lambda _o: "aa:bb:cc:00:00:11")

    with pytest.raises(RuntimeError) as erro:
        a04_iluminacao.player(SimpleNamespace(), {"player": "2"}, ipc_bridge)

    assert str(erro.value) == ipc_bridge._MOTIVOS_NUMERO[razao]


@pytest.fixture
def mascara_que_nasce(nascimentos: list[str], monkeypatch: pytest.MonkeyPatch  # noqa: F811
                      ) -> dict[str, list[Any]]:
    """O vpad nasce com a máscara pedida, e cada pad guarda o que recebeu."""
    quadros: dict[str, list[Any]] = {}

    class _VpadQueGuarda(_Vpad):
        def forward_buttons(self, pressed: frozenset[str]) -> None:
            quadros.setdefault(self.identidade, []).append(("botoes", pressed))

        def forward_analog(self, **kw: int) -> None:
            quadros.setdefault(self.identidade, []).append(("eixos", kw))

        def stop(self) -> None:
            quadros.setdefault(self.identidade, []).append(("parou",))

    def _nasce(flavor: Any, *, identity: str | None = None, **_kw: Any) -> _Vpad:
        nascimentos.append(str(identity))
        vpad = _VpadQueGuarda(str(identity))
        vpad.flavor = str(getattr(flavor, "value", flavor))
        return vpad

    monkeypatch.setattr("hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
                        _nasce)
    monkeypatch.setattr(coop_mod, "_parar_fora_do_tique", lambda vpad: vpad.stop())
    return quadros


def _o_co_op(reg: _Registro, mascara: str) -> tuple[Any, CoopManager]:
    daemon = _daemon(reg)
    daemon.config.gamepad_flavor = mascara
    gerente = CoopManager(daemon)
    daemon._coop_manager = gerente
    gerente.sync()
    daemon.display_authority = "game"
    daemon._numero_que_o_jogo_escreveu = {
        mac: (n, n) for mac, n in reg.numeros.items() if mac != P1
    }
    return daemon, gerente


def _a_tela_pede(daemon: Any, reg: _Registro, alvo: str, numero: int) -> None:
    """O caminho do handler: o pedido guardado ANTES da escrita, e a troca do registro."""
    gerente = daemon._coop_manager
    gerente.o_numero_pedido_pela_tela((alvo,))
    mudou = IpcHandlersMixin._set_number_locked(reg, None, alvo, numero)
    gerente.o_numero_pedido_pela_tela(tuple(mudou))


@pytest.mark.parametrize("mascara", MASCARAS)
def test_o_numero_do_jogo_nao_desfaz_o_pedido_e_cada_pad_renasce_uma_vez(
    mascara: str, nascimentos: list[str], registro: _Registro,  # noqa: F811
    mascara_que_nasce: dict[str, list[Any]],
) -> None:
    """D-2311-O-NUMERO-DO-JOGADOR-TROCA-PELA-TELA-COM-O-JOGO-ABERTO: o P2 e o P3 trocam."""
    daemon, gerente = _o_co_op(registro, mascara)
    assert nascimentos == [P2, P3, P4]

    _a_tela_pede(daemon, registro, P2, 3)
    for _ in range(5):
        gerente.sync(force=True)

    assert registro.numeros == {P1: 1, P2: 3, P3: 2, P4: 4}
    assert nascimentos[3:] == [P3, P2, P4], "o sufixo renasce uma vez, na ordem das cartas"
    assert [gerente._mesa_do_jogo[i] for i in (1, 2, 3)] == [P3, P2, P4]


@pytest.mark.parametrize("mascara", MASCARAS)
def test_sem_o_pedido_guardado_o_jogo_desfaria_a_troca(
    mascara: str, nascimentos: list[str], registro: _Registro,  # noqa: F811
    mascara_que_nasce: dict[str, list[Any]],
) -> None:
    """O defeito que o pedido guardado cura, medido no mesmo ensaio: a marca velha do jogo."""
    _, gerente = _o_co_op(registro, mascara)
    IpcHandlersMixin._set_number_locked(registro, None, P2, 3)
    gerente.sync(force=True)

    assert registro.numeros == {P1: 1, P2: 2, P3: 3, P4: 4}


def test_o_jogo_fecha_e_reabre_e_o_numero_pedido_fica(
    nascimentos: list[str], registro: _Registro,  # noqa: F811
    mascara_que_nasce: dict[str, list[Any]],
) -> None:
    daemon, gerente = _o_co_op(registro, "dualsense")
    _a_tela_pede(daemon, registro, P4, 2)
    gerente.sync(force=True)

    daemon.display_authority = "daemon"
    daemon._numero_que_o_jogo_escreveu = {}
    gerente.sync(force=True)
    assert gerente._pedidos_da_tela == frozenset(), "o pedido vale até o jogo fechar"

    daemon.display_authority = "game"
    daemon._numero_que_o_jogo_escreveu = {
        mac: (n, n) for mac, n in registro.numeros.items() if mac != P1
    }
    for _ in range(3):
        gerente.sync(force=True)

    assert registro.numeros == {P1: 1, P2: 4, P3: 3, P4: 2}


def test_o_pedido_recusado_nao_segura_o_numero_do_jogo(
    nascimentos: list[str], registro: _Registro,  # noqa: F811
    mascara_que_nasce: dict[str, list[Any]],
) -> None:
    _, gerente = _o_co_op(registro, "dualsense")
    marca = gerente.o_numero_pedido_pela_tela(("aa:bb:cc:00:00:02",))
    gerente.esquecer_o_pedido_da_tela(marca)

    assert gerente._pedidos_da_tela == frozenset()


def _o_servico_do_co_op(tmp: Path, daemon: Any) -> IpcServer:
    """O `IpcServer` real sobre o daemon do ensaio do co-op: o handler fala com o co-op real."""
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    return IpcServer(controller=fc, store=store,
                     profile_manager=ProfileManager(controller=fc, store=store),
                     socket_path=tmp / "c.sock", daemon=daemon)


async def _a_repintura_termina(server: IpcServer) -> None:
    for _ in range(50):
        em_voo = set(getattr(server, "_repinturas_em_voo", set()))
        if not em_voo:
            return
        await asyncio.gather(*em_voo, return_exceptions=True)
    raise AssertionError("a repintura despachada nunca terminou")


@pytest.mark.parametrize("mascara", MASCARAS)
@pytest.mark.asyncio
async def test_o_pedido_pelo_handler_vence_o_numero_do_jogo(
    config_isolado: Path, mascara: str, nascimentos: list[str],  # noqa: F811
    registro: _Registro, mascara_que_nasce: dict[str, list[Any]],  # noqa: F811
) -> None:
    """O caminho inteiro do pedido: o handler real guarda o pedido no co-op real."""
    daemon, gerente = _o_co_op(registro, mascara)
    server = _o_servico_do_co_op(config_isolado, daemon)

    resposta = await server._handle_identity_number_set({"uniq": P2, "number": 3})
    await _a_repintura_termina(server)
    for _ in range(3):
        gerente.sync(force=True)

    assert resposta["ok"] is True, resposta
    assert registro.numeros == {P1: 1, P2: 3, P3: 2, P4: 4}


@pytest.mark.asyncio
async def test_o_pedido_que_quebra_no_meio_nao_segura_o_numero_do_jogo(
    config_isolado: Path, nascimentos: list[str], registro: _Registro,  # noqa: F811
    mascara_que_nasce: dict[str, list[Any]], monkeypatch: pytest.MonkeyPatch,
) -> None:
    daemon, gerente = _o_co_op(registro, "dualsense")
    server = _o_servico_do_co_op(config_isolado, daemon)

    def _quebra(*_a: Any, **_k: Any) -> dict[str, int]:
        raise OSError("o disco recusou")

    monkeypatch.setattr(IpcHandlersMixin, "_set_number_locked", staticmethod(_quebra))
    with pytest.raises(OSError):
        await server._handle_identity_number_set({"uniq": P2, "number": 3})

    assert gerente._pedidos_da_tela == frozenset()


def test_o_pad_que_sai_para_renascer_sai_sem_nada_apertado(
    nascimentos: list[str], registro: _Registro,  # noqa: F811
    mascara_que_nasce: dict[str, list[Any]],
) -> None:
    daemon, gerente = _o_co_op(registro, "dualsense")
    mascara_que_nasce.clear()

    _a_tela_pede(daemon, registro, P2, 3)
    gerente.sync(force=True)

    for mac in (P2, P3):
        quadros = mascara_que_nasce[mac]
        parou = quadros.index(("parou",))
        antes = quadros[:parou]
        assert ("botoes", frozenset()) in antes, (mac, quadros)
        assert ("eixos", {"lx": 128, "ly": 128, "rx": 128, "ry": 128, "l2": 0, "r2": 0}) in antes
