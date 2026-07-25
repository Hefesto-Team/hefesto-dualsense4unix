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

#: Os controles da casa (MACs forjados — faixa aa:bb:cc).
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


# ---------------------------------------------------------------------------
# Entrega 2 — o comando que faltava: atribuir número
# ---------------------------------------------------------------------------


class TestAtribuirNumero:
    """O caminho público: ``identity.number.set`` pelo handler do IPC."""

    @pytest.mark.asyncio
    async def test_trocar_para_1_permuta_com_quem_estava_no_1(
        self, config_isolado: Path
    ) -> None:
        """O gesto dela: "quero que ESTE seja o 1".

        A e B na mesa, A na frente. Pedir 1 para B faz B exibir 1 e A exibir 2
        — os dois lugares que os presentes já ocupavam, trocados entre si.
        """
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
        # Só quem MUDOU de lugar entra no relatório (disciplina do R-15).
        assert set(resultado["changed"]) == {UNIQ_A, UNIQ_B}

    @pytest.mark.asyncio
    async def test_empurrar_para_o_fim_desliza_os_do_meio(
        self, config_isolado: Path
    ) -> None:
        """A→3 com três na mesa: B e C sobem um, ninguém fica sem número."""
        ds = ControllerIdentityRegistry()
        ds.sync_connected([UNIQ_A, UNIQ_B, UNIQ_C])

        server = _servidor(config_isolado, ds, None)
        await server._handle_identity_number_set({"uniq": UNIQ_A, "number": 3})

        assert ds.slot_for(UNIQ_B, assign=False) == 1
        assert ds.slot_for(UNIQ_C, assign=False) == 2
        assert ds.slot_for(UNIQ_A, assign=False) == 3
        # O critério que resume a NUM-01: nunca um jogador 2 sem jogador 1.
        exibidos = sorted(
            ds.slot_for(u, assign=False) for u in (UNIQ_A, UNIQ_B, UNIQ_C)
        )
        assert exibidos == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_nao_rebaixa_quem_esta_ausente(
        self, config_isolado: Path
    ) -> None:
        """A diferença viva para o "Renumerar agora".

        O renumber empurra os ausentes para o fim da fila por construção — é o
        gesto de faxina, e a mantenedora já mediu o efeito ("Renumerar agora
        REBAIXA quem está ausente"). Este comando permuta APENAS os lugares
        dos presentes: quem está na gaveta fica exatamente onde estava.
        """
        ds = ControllerIdentityRegistry()
        ds.sync_connected([UNIQ_A, UNIQ_B, UNIQ_C])  # lugares 1, 2, 3
        ds.sync_connected([UNIQ_A, UNIQ_C])  # B foi para a gaveta

        server = _servidor(config_isolado, ds, None)
        await server._handle_identity_number_set({"uniq": UNIQ_C, "number": 1})

        fila = ds.snapshot()
        assert fila[UNIQ_B] == 2, "o ausente perdeu o lugar dele na fila"
        assert {fila[UNIQ_A], fila[UNIQ_C]} == {1, 3}
        assert fila[UNIQ_C] == 1
        # E na mesa, quem ficou conta 1..N sem o ausente.
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
        ds.sync_connected([UNIQ_A])  # B saiu
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


# ---------------------------------------------------------------------------
# Entrega 4 — chips na ordem do número, índice de enumeração intacto
# (absorve UI-SELETOR-01)
# ---------------------------------------------------------------------------


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


def test_chips_saem_na_ordem_do_numero_de_identidade() -> None:
    """O sintoma medido: "Sony 2 · BT | Sony 1 · BT" com o 2 na frente.

    O daemon entrega na ordem de ENUMERAÇÃO (quem conectou primeiro); o número
    é estável por MAC. Quando ela liga os controles fora de ordem — o caso
    normal — os dois divergem.
    """
    rows = StatusActionsMixin._controller_target_rows(
        [
            _conectado(0, "bt", 2),
            _conectado(1, "bt", 1),
            _conectado(2, "usb", 4),
            _conectado(3, "bt", 3),
        ]
    )
    assert [label for label, _idx in rows] == [
        "Todos os controles",
        "Controle 1 — BT",
        "Controle 2 — BT",
        "Controle 3 — BT",
        "Controle 4 — USB",
    ]


def test_ordenar_a_exibicao_nao_mexe_no_indice_enviado() -> None:
    """A separação que dá nome à sprint, no ponto mais perigoso dela.

    O índice que cada linha CARREGA é o 0-based de enumeração, que é o que o
    ``controller.target.set`` espera. Reordená-lo junto com a exibição faria
    ela clicar no chip do Controle 1 e editar outro controle — defeito pior
    que a ordem torta que estamos consertando.
    """
    rows = StatusActionsMixin._controller_target_rows(
        [_conectado(0, "bt", 2), _conectado(1, "bt", 1)]
    )
    assert rows[1] == ("Controle 1 — BT", 1)
    assert rows[2] == ("Controle 2 — BT", 0)
    # E o mapeamento alvo→posição continua achando o alvo certo na fita nova.
    assert StatusActionsMixin._target_active_position(rows, 0) == 2
    assert StatusActionsMixin._target_active_position(rows, 1) == 1


def test_controle_sem_numero_vai_para_o_fim_preservando_a_ordem() -> None:
    """Sem ``player_slot`` (registro sem opinião ainda) não há como ordenar —
    esses vão para o fim na ordem de enumeração, que é a de sempre."""
    rows = StatusActionsMixin._controller_target_rows(
        [
            _conectado(0, "usb", None),
            _conectado(1, "bt", 1),
            _conectado(2, "bt", None),
        ]
    )
    assert [idx for _label, idx in rows] == [None, 1, 0, 2]


# ---------------------------------------------------------------------------
# Entrega 2 (janela) — o seletor "Número deste controle"
# ---------------------------------------------------------------------------


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


def test_seletor_de_numero_marca_o_numero_atual_do_alvo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Com o Controle 3 escolhido e quatro na mesa, o botão "3" fica marcado."""
    inst = _status_com_numero()
    monkeypatch.setattr(
        StatusActionsMixin,
        "_rebuild_numero_buttons",
        lambda self, caixa, total: setattr(
            self, "_numero_botoes", [_FakeBotaoNumero() for _ in range(total)]
        ),
    )
    inst._edit_target_uniq = UNIQ_A
    inst._edit_target_slot = 3

    inst._refresh_numero_selector(4)

    assert inst._numero_faixa.visivel is True
    assert [b.ativo for b in inst._numero_botoes] == [False, False, True, False]


def test_seletor_de_numero_some_sem_alvo_ou_com_um_controle_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem alvo não há o que numerar; com um controle só o único número é 1."""
    inst = _status_com_numero()
    monkeypatch.setattr(
        StatusActionsMixin,
        "_rebuild_numero_buttons",
        lambda self, caixa, total: None,
    )

    inst._edit_target_uniq = None
    inst._refresh_numero_selector(4)
    assert inst._numero_faixa.visivel is False

    inst._edit_target_uniq = UNIQ_A
    inst._edit_target_slot = 1
    inst._refresh_numero_selector(1)
    assert inst._numero_faixa.visivel is False


def test_clicar_no_numero_manda_identity_number_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O caminho público do botão: clique → IPC com o MAC e o número.

    Nada é pintado na janela por conta própria — quem repinta chip, cartões e
    LED é o próximo ``state_full``. Pintar antes da confirmação é como nasce a
    terceira verdade que esta sprint mata.
    """
    from hefesto_dualsense4unix.app.actions import status_actions as sa

    inst = _status_com_numero()
    inst._edit_target_uniq = UNIQ_B
    toasts: list[tuple[str, str]] = []
    inst._status_toast = lambda ctx, msg: toasts.append((ctx, msg))  # type: ignore[method-assign]

    chamadas: list[tuple[str, int]] = []
    monkeypatch.setattr(
        sa.ipc_bridge,
        "identity_number_set",
        lambda uniq, numero: chamadas.append((uniq, numero)) or (True, None),
    )
    monkeypatch.setattr(
        sa.ipc_bridge,
        "run_in_thread",
        lambda fn, on_success, on_failure=None: on_success(fn()),
    )

    botao = _FakeBotaoNumero()
    botao.set_active(True)
    inst._on_numero_button_toggled(botao, 2)

    assert chamadas == [(UNIQ_B, 2)]
    assert toasts and "agora é o 2" in toasts[-1][1]


def test_clique_no_numero_mostra_o_motivo_da_recusa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recusa do daemon vira a frase do daemon, não "pode estar desligado"."""
    from hefesto_dualsense4unix.app.actions import status_actions as sa

    inst = _status_com_numero()
    inst._edit_target_uniq = UNIQ_B
    toasts: list[str] = []
    inst._status_toast = lambda _ctx, msg: toasts.append(msg)  # type: ignore[method-assign]

    monkeypatch.setattr(
        sa.ipc_bridge,
        "identity_number_set",
        lambda _uniq, _numero: (False, "feche o jogo antes de trocar o número"),
    )
    monkeypatch.setattr(
        sa.ipc_bridge,
        "run_in_thread",
        lambda fn, on_success, on_failure=None: on_success(fn()),
    )

    botao = _FakeBotaoNumero()
    botao.set_active(True)
    inst._on_numero_button_toggled(botao, 3)

    assert toasts == ["feche o jogo antes de trocar o número"]


def test_marcacao_programatica_nao_dispara_pedido(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O eco do sync a 2 Hz não pode virar um ``identity.number.set`` por tique."""
    from hefesto_dualsense4unix.app.actions import status_actions as sa

    inst = _status_com_numero()
    inst._edit_target_uniq = UNIQ_B
    inst._numero_updating = True
    chamadas: list[Any] = []
    monkeypatch.setattr(
        sa.ipc_bridge,
        "run_in_thread",
        lambda fn, on_success, on_failure=None: chamadas.append(fn),
    )

    botao = _FakeBotaoNumero()
    botao.set_active(True)
    inst._on_numero_button_toggled(botao, 2)

    assert chamadas == []


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
    assert motivo is not None and "feche o jogo" in motivo

    monkeypatch.setattr(ipc_bridge, "_safe_call", lambda *_a, **_k: (False, None))
    assert ipc_bridge.identity_number_set(UNIQ_A, 2) == (False, None)


# ---------------------------------------------------------------------------
# Entrega 3 — o chip é um seletor de ALVO, e o selo diz isso sempre
# ---------------------------------------------------------------------------


def test_selo_aparece_tambem_sem_endereco_estavel() -> None:
    """Metade do trabalho já era feita — mas justamente no caso fácil."""
    assert (
        StatusActionsMixin._edit_badge_text("Controle 1 (USB)", com_endereco=False)
        == "Editando: Controle 1 (USB) — sem endereço fixo, vale para todos"
    )
    assert (
        StatusActionsMixin._edit_badge_text("Controle 1 (USB)")
        == "Editando: Controle 1 (USB)"
    )
    assert StatusActionsMixin._edit_badge_text(None, com_endereco=False) == ""


# ---------------------------------------------------------------------------
# Entrega 5 — a moldura mostra o que está ACESO, não o rascunho
# ---------------------------------------------------------------------------


class _FakeRotulo:
    def __init__(self) -> None:
        self.texto = ""

    def set_text(self, texto: str) -> None:
        self.texto = texto

    def set_active(self, _valor: bool) -> None:  # checkbox stub
        return None


def _host_lightbar(draft: DraftConfig, uniq: str | None, slot: int | None) -> Any:
    """Hospedeiro mínimo do mixin: draft + alvo + rótulo de leitura de volta.

    O mixin é importado LAZY (padrão de ``test_controller_target_ui.py``):
    ``lightbar_actions`` faz ``from gi.repository import Gdk, Gtk`` e o ``Gdk``
    sem ``require_version`` puxa a 4.0 quando é o PRIMEIRO import de gi do
    processo — rodar este arquivo sozinho derrubava a coleta inteira.
    """
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
    """O relato: "a moldura mostra nada selecionado enquanto o controle exibe
    três luzes acesas". Três luzes é o desenho do P3 — o do NÚMERO dele."""
    host = _host_lightbar(DraftConfig.from_profile(_perfil_novo()), UNIQ_A, 3)
    host._refresh_lightbar_from_draft()
    assert host.rotulo.texto == (
        "Aceso agora: desenho do P3 — automático, do número deste controle."
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
    assert host.rotulo.texto == "Aceso agora: desenho do P2 — escolha sua."


def test_moldura_avisa_que_o_co_op_governa_o_desenho() -> None:
    """Critério 3 da validação da sprint: com co-op ligado, a tela avisa."""
    host = _host_lightbar(DraftConfig.from_profile(_perfil_novo()), UNIQ_A, 3)
    host._coop_ligado = True
    host._refresh_lightbar_from_draft()
    assert "co-op" in host.rotulo.texto
    assert "manda nas 5 luzes" in host.rotulo.texto


def test_texto_do_desenho_sem_numero_conhecido_nao_inventa_numero() -> None:
    """Registro ainda sem opinião: diz que o automático manda, e só."""
    from hefesto_dualsense4unix.app.actions.lightbar_actions import (
        texto_do_desenho_aceso,
    )

    texto = texto_do_desenho_aceso((False,) * 5, None)
    assert "automático" in texto
    assert "P1" not in texto


def test_nome_do_desenho_usa_a_tabela_canonica() -> None:
    """Os nomes vêm de ``player_led_pattern`` — a MESMA fonte do daemon."""
    from hefesto_dualsense4unix.app.actions.lightbar_actions import nome_do_desenho
    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    assert nome_do_desenho(player_led_pattern(1)) == "desenho do P1"
    assert nome_do_desenho(player_led_pattern(4)) == "desenho do P4"
    # A varredura vai até 8 porque o espaço de numeração é único (R-24/R-25) e
    # um DualSense pode cair no 5+; o 9 é o padrão de OVERFLOW, que não nomeia
    # jogador nenhum.
    assert nome_do_desenho(player_led_pattern(8)) == "desenho do P8"
    assert nome_do_desenho((True, False, False, True, False)) is None


def test_troca_do_flag_de_co_op_repinta_a_moldura() -> None:
    """A aba Lightbar não tem poller: quem publica o co-op é a aba Status."""

    class _Host(StatusActionsMixin):
        def __init__(self) -> None:
            self.repintou = 0

        def _refresh_lightbar_from_draft(self) -> None:  # type: ignore[override]
            self.repintou += 1

    host = _Host()
    host._sync_coop_governa_luzes({"coop": {"enabled": True}})
    assert host._coop_ligado is True
    assert host.repintou == 1
    # Idempotente: mesmo estado não repinta a 2 Hz.
    host._sync_coop_governa_luzes({"coop": {"enabled": True}})
    assert host.repintou == 1


# ---------------------------------------------------------------------------
# Entrega 6 — pedido sem destinatário falha VISIVELMENTE
# ---------------------------------------------------------------------------


def _host_sem_mapa_de_controles() -> Any:
    """Alvo "Todos" e nenhum tique do daemon ainda — o cenário do achado."""
    host = _host_lightbar(DraftConfig.from_profile(_perfil_novo()), None, None)
    host._target_uniq_by_index = {}
    return host


def test_preset_sem_destinatario_recusa_em_vez_de_gravar_abaixo_do_automatico(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O "volta sozinho", pelo caminho público do botão de preset.

    Sem saber quem está na mesa, o pedido saía sem ``uniq`` e o daemon o
    gravava no default GLOBAL — camada ABAIXO da automática no merge por campo
    (D5). O automático o desfazia no reforço seguinte, depois de o toast já ter
    dito que aplicou.
    """
    from hefesto_dualsense4unix.app.actions import lightbar_actions as la

    enviados: list[Any] = []
    monkeypatch.setattr(
        la,
        "player_leds_set",
        lambda bits, uniq=None: enviados.append((bits, uniq)) or True,
    )

    host = _host_sem_mapa_de_controles()
    host.on_player_leds_preset_p2(None)

    assert enviados == [], "mandou um pedido sem destinatário"
    assert host.toasts
    assert "sem destinatário" in host.toasts[-1]
    assert "ainda não sei quais controles estão na mesa" in host.toasts[-1]


def test_aplicar_sem_destinatario_tambem_recusa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O mesmo pelo botão "Aplicar o desenho" (o outro caminho público)."""
    from hefesto_dualsense4unix.app.actions import lightbar_actions as la

    enviados: list[Any] = []
    monkeypatch.setattr(
        la,
        "player_leds_set",
        lambda bits, uniq=None: enviados.append((bits, uniq)) or True,
    )

    host = _host_sem_mapa_de_controles()
    host.get_current_player_leds = lambda: (False, True, False, True, False)  # type: ignore[method-assign]
    host.on_player_leds_apply(None)

    assert enviados == []
    assert "ainda não sei quais controles estão na mesa" in host.toasts[-1]


def test_com_alvo_escolhido_o_pedido_vai_por_mac(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contraprova: com destinatário, o caminho segue exatamente como era."""
    from hefesto_dualsense4unix.app.actions import lightbar_actions as la

    enviados: list[Any] = []
    monkeypatch.setattr(
        la,
        "player_leds_set",
        lambda bits, uniq=None: enviados.append((tuple(bits), uniq)) or True,
    )

    host = _host_lightbar(DraftConfig.from_profile(_perfil_novo()), UNIQ_A, 1)
    host.on_player_leds_preset_p2(None)

    assert enviados == [((False, True, False, True, False), UNIQ_A)]
    assert "Desenho das luzes atualizado" in host.toasts[-1]
