"""SLOT-JOGADOR-01 — "Controle N" e "Jogador N" são dois números, e a tela diz isso.

Medido em 25/07/2026 com quatro controles ligados: a janela mostrava
``Controle 2 - BT . Jogador 1`` e ``Controle 1 - BT . Jogador 2`` ao mesmo
tempo, sem nada indicando que aqueles dois números vinham de espaços
diferentes. Os dois estavam certos:

- ``player_slot`` é a colocação na fila de preferência do `identity_registry`
  (NUM-01) — e é o número que o daemon ACENDE na barra de jogador do aparelho
  (R-24). Na máquina da mantenedora o ``controllers.json`` tinha a ordem
  ``[143a... = 1, a0fa... = 2]``.
- ``player`` é o índice de alocação de vpad do co-op, ancorado no PRIMÁRIO do
  backend — que é eleito por ordem de enumeração do hidapi
  (`backend_pydualsense._recompute_primary`). O primário naquela sessão era o
  ``a0fa...``, cuja colocação na fila é 2.

Duas âncoras sem nada em comum; nenhuma renumeração faz as duas coincidirem.
Este arquivo trava as três regras que saíram daí:

1. o daemon publica os DOIS números, mais o único cuja autoridade é o JOGO
   (``player_game``, decodificado dos bits que o jogo escreveu);
2. o rótulo cola a autoridade no número do jogador, para os dois não serem
   lidos como um só (CONTAGEM-01: nenhuma tela exibe dois números para a
   mesma pergunta ao mesmo tempo);
3. com o co-op DESLIGADO só o primário é jogador — o segundo DualSense não
   alimenta vpad nenhum.

A fiação é a de verdade: `IpcServer` real, socket real, `daemon.state_full`
real; o rótulo é montado a partir das entradas QUE VOLTARAM do servidor,
nunca de um dicionário escrito à mão no teste. MACs fake (regra da casa).
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.cli.ipc_client import IpcClient
from hefesto_dualsense4unix.core.led_control import player_led_pattern
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.testing import FakeController

#: MACs fake. `PRIMARIO` reproduz o papel do `a0fa...` medido: é o primário do
#: backend E o segundo da fila de preferência.
PRIMARIO = "aabbcc000001"
SEGUNDO = "aabbcc000002"

#: A inversão MEDIDA: quem é primário está em segundo na fila.
SLOTS = {PRIMARIO: 2, SEGUNDO: 1}


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


def _daemon_double(*, coop: bool) -> Any:
    """Daemon dublê com as DUAS fontes de número plugadas de verdade.

    `identity_registry.slot_for` é a fila de preferência; `_coop_manager.
    player_indexes` é a alocação de vpad do co-op. Nenhuma das duas é
    calculada pelo teste: cada uma devolve o que a sua fonte devolveria.
    """
    daemon = MagicMock()
    daemon._last_state = None
    daemon.external_registry = None
    daemon.config = MagicMock(
        coop_enabled=coop,
        mouse_emulation_enabled=False,
        mouse_speed=6,
        mouse_scroll_speed=1,
        rumble_policy="balanceado",
        rumble_policy_custom_mult=0.7,
    )
    daemon._gamepad_device = object()
    daemon.identity_registry = SimpleNamespace(
        slot_for=lambda uniq, assign=True: SLOTS.get(uniq)
    )
    daemon._coop_manager = SimpleNamespace(
        player_indexes=lambda: ({PRIMARIO: 1, SEGUNDO: 2} if coop else {}),
        live_snapshots=dict,
        _players={},
        player_count=lambda: 2 if coop else 1,
    )
    return daemon


async def _state_full(socket_path: Path) -> dict[str, Any]:
    async with IpcClient.connect(socket_path) as client:
        result = await client.call("daemon.state_full")
    assert isinstance(result, dict)
    return result


async def _controllers(
    tmp_path: Path, *, coop: bool, leds_do_jogo: Any = None
) -> list[dict[str, Any]]:
    """Sobe o servidor IPC de verdade e devolve o bloco `controllers` publicado."""
    fc = FakeController(transport="bt")
    fc.connect()
    fc.describe_controllers = lambda: [
        {
            "index": 0,
            "connected": True,
            "transport": "bt",
            "is_primary": True,
            "uniq": PRIMARIO,
            "player_leds_game": leds_do_jogo,
        },
        {
            "index": 1,
            "connected": True,
            "transport": "bt",
            "is_primary": False,
            "uniq": SEGUNDO,
            "player_leds_game": None,
        },
    ]
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))
    socket_path = tmp_path / "hefesto-dualsense4unix.sock"
    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=socket_path,
        daemon=_daemon_double(coop=coop),
    )
    await server.start()
    try:
        result = await _state_full(socket_path)
    finally:
        await server.stop()
    entradas = result.get("controllers")
    assert isinstance(entradas, list)
    return [e for e in entradas if isinstance(e, dict)]


class TestOsDoisNumerosSaemDoDaemon:
    """O daemon publica os dois, e eles divergem — não é erro de exibição."""

    @pytest.mark.asyncio
    async def test_o_primario_e_o_jogador_1_mesmo_sendo_o_controle_2(
        self, tmp_path: Path, isolated_profiles_dir: Path
    ) -> None:
        """A medição de 25/07, reproduzida pelo caminho real do payload."""
        c1, c2 = await _controllers(tmp_path, coop=True)

        assert (c1["player_slot"], c1["player"]) == (2, 1)
        assert (c2["player_slot"], c2["player"]) == (1, 2)

    @pytest.mark.asyncio
    async def test_o_numero_que_o_jogo_declarou_vira_campo_proprio(
        self, tmp_path: Path, isolated_profiles_dir: Path
    ) -> None:
        """`player_game` é o único número do payload com autoridade de fora.

        Falha-sem: sem este campo, o número que o JOGO escreveu fica preso nos
        cinco bits e a interface só tem os números que nós inventamos.
        """
        c1, c2 = await _controllers(
            tmp_path, coop=True, leds_do_jogo=list(player_led_pattern(4))
        )

        assert c1["player_game"] == 4
        assert c2["player_game"] is None

    @pytest.mark.asyncio
    async def test_padrao_fora_da_tabela_nao_vira_numero(
        self, tmp_path: Path, isolated_profiles_dir: Path
    ) -> None:
        """Padrão desconhecido não vira palpite — a tabela é a única tradução.

        `_PLAYER_LED_OVERFLOW` (o desenho de "slot >= 9") é de propósito o
        padrão escolhido: ele é o mais parecido com um número de verdade que
        existe no projeto, e mesmo assim não pode virar um.
        """
        c1, _c2 = await _controllers(
            tmp_path, coop=True, leds_do_jogo=[True, False, True, True, False]
        )

        assert c1["player_game"] is None


class TestCoopDesligadoSoOPrimarioEJogador:
    """SLOT-JOGADOR-01: quem não alimenta vpad não recebe número."""

    @pytest.mark.asyncio
    async def test_o_segundo_controle_nao_ganha_um_jogador_1_duplicado(
        self, tmp_path: Path, isolated_profiles_dir: Path
    ) -> None:
        """`read_state` lê SEMPRE o handle do primário: o segundo é mudo.

        Falha-sem: com `[1, 1]` a tela punha dois cartões com o mesmo número —
        e prometia à mantenedora um jogador que não existe.
        """
        c1, c2 = await _controllers(tmp_path, coop=False)

        assert c1["player"] == 1
        assert c2["player"] is None


class TestORotuloColaAAutoridade:
    """O rótulo da aba Início, montado a partir do payload que VOLTOU do IPC."""

    @pytest.mark.asyncio
    async def test_os_dois_numeros_aparecem_dizendo_de_quem_sao(
        self, tmp_path: Path, isolated_profiles_dir: Path
    ) -> None:
        """CONTAGEM-01: dois números na mesma linha, cada um com a sua pergunta.

        Falha-sem: o rótulo antigo era "Controle 2 - P1", dois números crus lado
        a lado — o que fez a mantenedora ler a divergência como defeito.
        """
        from hefesto_dualsense4unix.app.actions.home_actions import (
            _format_controller_title,
        )

        c1, c2 = await _controllers(tmp_path, coop=True)

        assert _format_controller_title(c1) == "Controle 2 — P1 no co-op"
        assert _format_controller_title(c2) == "Controle 1 — P2 no co-op"

    @pytest.mark.asyncio
    async def test_o_numero_do_jogo_vence_o_do_coop_no_rotulo(
        self, tmp_path: Path, isolated_profiles_dir: Path
    ) -> None:
        """Nenhuma opinião nossa supera o jogo tendo escrito o número."""
        from hefesto_dualsense4unix.app.actions.home_actions import (
            _format_controller_title,
        )

        c1, _c2 = await _controllers(
            tmp_path, coop=True, leds_do_jogo=list(player_led_pattern(3))
        )

        assert _format_controller_title(c1) == "Controle 2 — P3 no jogo"

    @pytest.mark.asyncio
    async def test_sem_coop_o_segundo_card_nao_inventa_jogador(
        self, tmp_path: Path, isolated_profiles_dir: Path
    ) -> None:
        from hefesto_dualsense4unix.app.actions.home_actions import (
            _format_controller_title,
        )

        c1, c2 = await _controllers(tmp_path, coop=False)

        assert _format_controller_title(c1) == "Controle 2 — P1 no co-op"
        assert _format_controller_title(c2) == "Controle 1"


class TestARegraTemUmDonoSo:
    """A regra do sufixo mora em `base` — a aba Início não tem cópia dela."""

    def test_o_titulo_do_card_nao_formata_o_numero_por_conta_propria(self) -> None:
        """Falha-sem: uma segunda cópia da regra é uma segunda chance de a
        janela voltar a dizer duas coisas sobre o mesmo controle — que é
        exatamente como esta numeração divergiu da primeira vez."""
        import inspect

        from hefesto_dualsense4unix.app.actions import home_actions

        fonte = inspect.getsource(home_actions._format_controller_title)
        corpo = fonte.split('"""')[-1]
        assert "sufixo_de_jogador(" in corpo
        # Nenhum "P{...}" montado à mão no corpo: o único literal com "P" é o
        # travessão do externo (CONTAGEM-01, entrega 6).
        assert "P{" not in corpo
