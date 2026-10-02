"""PLAYER-01 — um número de jogador, e ele é editável (sprint 2026-07-25).

Os dois relatos:

> "a escolha do player nos LEDs de jogador não sincroniza com o botão superior
> que informa o controle e o player"

> "talvez o nome da seção devesse mudar também"

O achado: a expectativa dela — *escolho o player e o cabeçalho acompanha* — era
IRREALIZÁVEL por construção. Não existia, em lugar nenhum do projeto, comando
que atribuísse um número de jogador a um controle; só o ``identity.renumber``,
que compacta TODOS preservando a ordem relativa e mora na aba Início. Ela
clicava num controle de APARÊNCIA (o desenho das 5 luzinhas) esperando mudar
IDENTIDADE, e o rótulo da tela prometia exatamente isso.

Este arquivo cobre as seis entregas, sempre pelo CAMINHO PÚBLICO — o handler
que o botão de fato chama, nunca o método privado por baixo dele (um teste que
entra por baixo passa com a cura arrancada):

- entrega 2 (principal): o IPC ``identity.number.set``, por
  ``IpcServer._handle_identity_number_set``;
- entrega 3: o selo de alvo aparece TAMBÉM sem endereço estável;
- entrega 4 (absorve UI-SELETOR-01): chips ordenados pelo número de
  identidade, com o índice de enumeração intacto dentro de cada linha;
- entrega 5: a moldura mostra o desenho ACESO, não o rascunho;
- entrega 6: pedido de desenho sem destinatário FALHA visivelmente.

Herméticos: ``config_dir`` monkeypatchado nos DOIS módulos de registro (eles
dividem o MESMO ``controllers.json``) e ``boot_id`` fixo. MACs sempre na faixa
forjada ``aa:bb:cc:*`` — teste-guarda de anonimato.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("player01 um numero de jogador")

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin
from hefesto_dualsense4unix.app.draft_config import DraftConfig
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
from hefesto_dualsense4unix.profiles.schema import LedsConfig, MatchAny, Profile
from hefesto_dualsense4unix.testing import FakeController


UNIQ_A = "aabbcc000001"
UNIQ_B = "aabbcc000002"
UNIQ_C = "aabbcc000003"
MAC_EXTERNO = "aabbcc0000fe"

BOOT = "boot-teste-player01"


@dataclass
class _FakeDaemon:
    display_authority: str = "daemon"
    identity_registry: Any = None
    external_registry: Any = None


@pytest.fixture
def config_isolado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``config_dir`` em tmp + âncora fixa nos dois registros (mesmo arquivo)."""
    from hefesto_dualsense4unix.utils import xdg_paths

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: BOOT)
    monkeypatch.setattr(ei_mod, "_read_boot_id", lambda: BOOT)
    return tmp_path


def _servidor(
    tmp_path: Path,
    ds: ControllerIdentityRegistry | None,
    ext: ExternalIdentityRegistry | None,
    *,
    authority: str = "daemon",
) -> IpcServer:
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    daemon = _FakeDaemon(
        display_authority=authority, identity_registry=ds, external_registry=ext
    )
    return IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=tmp_path / "player01.sock",
        daemon=daemon,
    )


def _fila_no_disco(tmp: Path, kind: str) -> dict[str, int]:
    """Endereço → lugar na fila (campo ``order`` do schema 3 — NUM-01)."""
    dados = json.loads((tmp / "controllers.json").read_text(encoding="utf-8"))
    return {
        str(e["addr"]): int(e["rank"])
        for e in dados[id_mod.ORDER_FIELD]
        if isinstance(e, dict) and e.get("kind") == kind
    }


class TestAtribuirNumero:
    """O caminho público: ``identity.number.set`` pelo handler do IPC."""

    @pytest.mark.asyncio
    async def test_trocar_para_1_permuta_com_quem_estava_no_1(
        self, config_isolado: Path
    ) -> None:
        """O gesto dela: "quero que ESTE seja o 1"."""
        ds = ControllerIdentityRegistry()
        ds.sync_connected([UNIQ_A, UNIQ_B])
        assert ds.slot_for(UNIQ_A, assign=False) == 1
        assert ds.slot_for(UNIQ_B, assign=False) == 2

        server = _servidor(config_isolado, ds, None)
        resultado = await server._handle_identity_number_set(
            {"uniq": UNIQ_B, "number": 1}
        )

        assert resultado["ok"] is True
        assert resultado["number"] == 1
        assert ds.slot_for(UNIQ_B, assign=False) == 1
        assert ds.slot_for(UNIQ_A, assign=False) == 2
        assert set(resultado["changed"]) == {UNIQ_A, UNIQ_B}

    @pytest.mark.asyncio
    async def test_empurrar_para_o_fim_troca_com_quem_esta_la(
        self, config_isolado: Path
    ) -> None:
        """A→3 com três na mesa: A e C trocam, **B não se mexe**."""
        ds = ControllerIdentityRegistry()
        ds.sync_connected([UNIQ_A, UNIQ_B, UNIQ_C])

        server = _servidor(config_isolado, ds, None)
        await server._handle_identity_number_set({"uniq": UNIQ_A, "number": 3})

        assert ds.slot_for(UNIQ_A, assign=False) == 3
        assert ds.slot_for(UNIQ_C, assign=False) == 1
        assert ds.slot_for(UNIQ_B, assign=False) == 2
        exibidos = sorted(
            ds.slot_for(u, assign=False) for u in (UNIQ_A, UNIQ_B, UNIQ_C)
        )
        assert exibidos == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_nao_rebaixa_quem_esta_ausente(
        self, config_isolado: Path
    ) -> None:
        """A diferença viva para o "Renumerar agora"."""
        agora = [1000.0]
        ds = ControllerIdentityRegistry(clock=lambda: agora[0])
        ds.sync_connected([UNIQ_A, UNIQ_B, UNIQ_C])
        ds.sync_connected([UNIQ_A, UNIQ_C])

        server = _servidor(config_isolado, ds, None)
        await server._handle_identity_number_set({"uniq": UNIQ_C, "number": 1})

        fila = ds.snapshot()
        assert fila[UNIQ_B] == 2, "o ausente perdeu o lugar dele na fila"
        assert {fila[UNIQ_A], fila[UNIQ_C]} == {1, 3}
        assert fila[UNIQ_C] == 1
        assert ds.slot_for(UNIQ_C, assign=False) == 1
        assert ds.slot_for(UNIQ_A, assign=False) == 3
        agora[0] += id_mod.prazo_do_lugar_guardado() + 1.0
        assert ds.slot_for(UNIQ_C, assign=False) == 1
        assert ds.slot_for(UNIQ_A, assign=False) == 2

    @pytest.mark.asyncio
    async def test_mesa_mista_cada_registro_recebe_a_sua_fatia(
        self, config_isolado: Path
    ) -> None:
        """A fila é ÚNICA entre DualSense e externos (EXT-04/NUM-01).

        Pedir o número 1 para o externo tem de reordenar os DOIS registros —
        cada um recebendo só as chaves que são dele.
        """
        ds = ControllerIdentityRegistry()
        ext = ExternalIdentityRegistry()
        ds.set_external_reserve_provider(lambda: set(ext.snapshot().values()))
        ds.sync_connected([UNIQ_A])
        ext.slot_for(MAC_EXTERNO, reserve=max(ds.snapshot().values(), default=0))
        ext.sync_connected([MAC_EXTERNO])

        server = _servidor(config_isolado, ds, ext)
        resultado = await server._handle_identity_number_set(
            {"uniq": MAC_EXTERNO, "number": 1}
        )

        assert resultado["ok"] is True
        assert ext.snapshot()[MAC_EXTERNO] == 1
        assert ds.snapshot()[UNIQ_A] == 2

    @pytest.mark.asyncio
    async def test_persiste_a_fila_no_controllers_json(
        self, config_isolado: Path
    ) -> None:
        """A troca sobrevive ao restart: vai para o disco no schema 3."""
        ds = ControllerIdentityRegistry()
        ds.sync_connected([UNIQ_A, UNIQ_B])

        server = _servidor(config_isolado, ds, None)
        await server._handle_identity_number_set({"uniq": UNIQ_B, "number": 1})

        assert _fila_no_disco(config_isolado, id_mod.KIND_DUALSENSE) == {
            UNIQ_B: 1,
            UNIQ_A: 2,
        }

    @pytest.mark.asyncio
    async def test_pedir_o_numero_que_ja_tem_e_no_op(
        self, config_isolado: Path
    ) -> None:
        """Idempotente e honesto: nada mudou, ``changed`` volta vazio."""
        ds = ControllerIdentityRegistry()
        ds.sync_connected([UNIQ_A, UNIQ_B])

        server = _servidor(config_isolado, ds, None)
        resultado = await server._handle_identity_number_set(
            {"uniq": UNIQ_A, "number": 1}
        )
        assert resultado == {"ok": True, "number": 1, "changed": {}}


class TestRecusasVisiveis:
    """Toda recusa é explícita e nenhuma escreve nada (PLAYER-01)."""

    @pytest.mark.asyncio
    async def test_recusa_com_jogo_aberto(self, config_isolado: Path) -> None:
        ds = ControllerIdentityRegistry()
        ds.sync_connected([UNIQ_A, UNIQ_B])
        antes = ds.snapshot()

        server = _servidor(config_isolado, ds, None, authority="game")
        resultado = await server._handle_identity_number_set(
            {"uniq": UNIQ_B, "number": 1}
        )

        assert resultado == {"ok": False, "reason": "sessao_de_jogo_aberta"}
        assert ds.snapshot() == antes

    @pytest.mark.asyncio
    async def test_recusa_controle_ausente(self, config_isolado: Path) -> None:
        """Número exibido só existe para quem está na mesa (NUM-01)."""
        ds = ControllerIdentityRegistry()
        ds.sync_connected([UNIQ_A, UNIQ_B])
        ds.sync_connected([UNIQ_A])
        antes = ds.snapshot()

        server = _servidor(config_isolado, ds, None)
        resultado = await server._handle_identity_number_set(
            {"uniq": UNIQ_B, "number": 1}
        )

        assert resultado == {"ok": False, "reason": "controle_ausente"}
        assert ds.snapshot() == antes

    @pytest.mark.asyncio
    async def test_recusa_numero_fora_da_mesa_com_o_teto(
        self, config_isolado: Path
    ) -> None:
        """Corrida real: a janela desenhou 4 botões e um controle caiu."""
        ds = ControllerIdentityRegistry()
        ds.sync_connected([UNIQ_A, UNIQ_B])
        antes = ds.snapshot()

        server = _servidor(config_isolado, ds, None)
        resultado = await server._handle_identity_number_set(
            {"uniq": UNIQ_A, "number": 4}
        )

        assert resultado == {
            "ok": False,
            "reason": "numero_fora_da_mesa",
            "max": 2,
        }
        assert ds.snapshot() == antes

    @pytest.mark.asyncio
    async def test_sem_registros_fiados_recusa_sem_levantar(
        self, config_isolado: Path
    ) -> None:
        """Daemon sem os registros (fake/boot parcial): recusa, nunca estoura."""
        server = _servidor(config_isolado, None, None)
        resultado = await server._handle_identity_number_set(
            {"uniq": UNIQ_A, "number": 1}
        )
        assert resultado == {"ok": False, "reason": "controle_ausente"}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "params",
        [
            {"number": 1},
            {"uniq": "", "number": 1},
            {"uniq": UNIQ_A},
            {"uniq": UNIQ_A, "number": 0},
            {"uniq": UNIQ_A, "number": "1"},
            {"uniq": UNIQ_A, "number": True},
        ],
    )
    async def test_params_invalidos_viram_erro_de_parametro(
        self, config_isolado: Path, params: dict[str, Any]
    ) -> None:
        """``ValueError`` vira ``-32003`` no dispatcher (contrato do IPC)."""
        server = _servidor(config_isolado, ControllerIdentityRegistry(), None)
        with pytest.raises(ValueError):
            await server._handle_identity_number_set(params)


def test_identity_number_set_no_dict_de_handlers(tmp_path: Path) -> None:
    """Armadilha A-07: handler escrito e nunca roteado é handler que não existe."""
    fc = FakeController(transport="usb")
    store = StateStore()
    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=ProfileManager(controller=fc, store=store),
        socket_path=tmp_path / "wireado.sock",
    )
    assert "identity.number.set" in server._handlers


def _conectado(
    index: int, transport: str, slot: int | None, uniq: str | None = None
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "index": index,
        "connected": True,
        "transport": transport,
    }
    if slot is not None:
        entry["player_slot"] = slot
    if uniq is not None:
        entry["uniq"] = uniq
    return entry


class _FakeBotaoNumero:
    def __init__(self) -> None:
        self.ativo = False

    def set_active(self, valor: bool) -> None:
        self.ativo = bool(valor)

    def get_active(self) -> bool:
        return self.ativo


class _FakeFaixa:
    def __init__(self) -> None:
        self.visivel = False

    def show(self) -> None:
        self.visivel = True

    def hide(self) -> None:
        self.visivel = False

    def get_children(self) -> list[Any]:
        return []

    def remove(self, _child: Any) -> None:
        return None


def _status_com_numero(total_botoes: int = 0) -> StatusActionsMixin:
    inst = StatusActionsMixin.__new__(StatusActionsMixin)
    inst._numero_faixa = _FakeFaixa()
    inst._numero_box = _FakeFaixa()
    inst._numero_botoes = [_FakeBotaoNumero() for _ in range(total_botoes)]
    inst._numero_total = total_botoes
    inst._numero_updating = False
    inst._numero_visivel = False
    inst._edit_target_uniq = None
    inst._edit_target_slot = None
    return inst


def test_ipc_bridge_traduz_o_motivo_da_recusa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ponte traduz o ``reason`` do protocolo para a frase da janela."""
    from hefesto_dualsense4unix.app import ipc_bridge

    monkeypatch.setattr(
        ipc_bridge,
        "_safe_call",
        lambda *_a, **_k: (
            True,
            {"ok": False, "reason": "sessao_de_jogo_aberta"},
        ),
    )
    ok, motivo = ipc_bridge.identity_number_set(UNIQ_A, 2)
    assert ok is False
    assert motivo is not None and "Feche o jogo" in motivo

    monkeypatch.setattr(ipc_bridge, "_safe_call", lambda *_a, **_k: (False, None))
    assert ipc_bridge.identity_number_set(UNIQ_A, 2) == (False, None)


class _FakeRotulo:
    def __init__(self) -> None:
        self.texto = ""

    def set_text(self, texto: str) -> None:
        self.texto = texto

    def set_active(self, _valor: bool) -> None:
        return None


def _aceitou(uniq: str | None) -> dict[str, Any]:
    """Corpo de um ``led.player_set`` que ESCREVEU em ``uniq`` (BG-01)."""
    return {
        "status": "ok",
        "bits": [],
        "aplicado_em": [uniq] if uniq else [],
        "guardado_em": [],
    }


def _host_lightbar(draft: DraftConfig, uniq: str | None, slot: int | None) -> Any:
    """Hospedeiro mínimo do mixin: draft + alvo + rótulo de leitura de volta."""
    from hefesto_dualsense4unix.app.actions.lightbar_actions import (
        LightbarActionsMixin,
    )

    class _HostLightbar(LightbarActionsMixin):
        def __init__(self) -> None:
            self.draft = draft
            self._edit_target_uniq = uniq
            self._edit_target_slot = slot
            self._refresh_guard = False
            self.rotulo = _FakeRotulo()
            self.toasts: list[str] = []

        def _get(self, widget_id: str) -> Any:
            if widget_id == "player_leds_estado":
                return self.rotulo
            return None

        def _toast_light(self, msg: str) -> None:
            self.toasts.append(msg)

    return _HostLightbar()


def _perfil_novo() -> Profile:
    """Perfil recém-criado: ``player_leds`` no default do schema (tudo apagado)."""
    return Profile(name="novo", match=MatchAny(), leds=LedsConfig())


def test_moldura_mostra_o_desenho_automatico_num_perfil_novo() -> None:
    """O relato: "a moldura mostra nada selecionado enquanto o controle exibe"""
    host = _host_lightbar(DraftConfig.from_profile(_perfil_novo()), UNIQ_A, 3)
    host._refresh_lightbar_from_draft()
    assert host.rotulo.texto == (
        "Desenho que mandamos: desenho do P3 — automático, do número deste "
        "controle."
    )


def test_moldura_diz_quando_a_escolha_e_dela() -> None:
    """Desenho não-vazio no rascunho vence o automático por campo (D5)."""
    draft = DraftConfig.from_profile(_perfil_novo())
    draft = draft.model_copy(
        update={
            "leds": draft.leds.model_copy(
                update={"player_leds": (False, True, False, True, False)}
            )
        }
    )
    host = _host_lightbar(draft, UNIQ_A, 3)
    host._refresh_lightbar_from_draft()
    assert host.rotulo.texto == (
        "Desenho que mandamos: desenho do P2 — escolha sua."
    )


def test_moldura_avisa_que_o_co_op_governa_o_desenho() -> None:
    """Critério 3 da validação da sprint: com co-op ligado, a tela avisa."""
    host = _host_lightbar(DraftConfig.from_profile(_perfil_novo()), UNIQ_A, 3)
    host._coop_ligado = True
    host._refresh_lightbar_from_draft()
    assert "co-op" in host.rotulo.texto
    assert "manda nas 5 luzes" in host.rotulo.texto


def _host_sem_mapa_de_controles() -> Any:
    """Alvo "Todos" e nenhum tique do daemon ainda — o cenário do achado."""
    host = _host_lightbar(DraftConfig.from_profile(_perfil_novo()), None, None)
    host._target_uniq_by_index = {}
    return host


