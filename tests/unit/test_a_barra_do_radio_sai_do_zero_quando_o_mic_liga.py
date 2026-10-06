"""QUATRO-MICROFONES-01 (E2) — o medidor de rádio responde ao microfone.

O medidor de `CONFIG-04` já sabia pintar a fatia de áudio: a conta de ocupação (hoje
`plano_por_adaptador`) recebe `com_ponte_de_mic` desde o dia em que nasceu, e o
`test_medidor_de_radio` prova a aritmética dela. O que faltava era o
**parâmetro estar ligado à verdade**: o `daemon.state_full` não publicava de
QUAIS controles a ponte estava de pé, e a seção "A mesa" lia uma chave que não
existia. Com quatro controles no rádio e uma ponte viva, a barra pintava áudio
zero nos quatro.

A CADEIA TEM TRÊS ELOS, e este arquivo guarda os três
------------------------------------------------------

1. o subsystem sabe de quem é cada ponte (`BtMicSubsystem.uniqs_com_ponte`);
2. o `daemon.state_full` publica isso em `bt_mic.uniqs` — a terceira chave do
   bloco, e a única das três que fala de CONTROLE em vez de PROCESSO;
3. a seção "A mesa" lê aquela chave e a repassa a `plano_por_adaptador`.

A LINHA DE BASE, e ela é o controle negativo desta entrega
-----------------------------------------------------------

Medida na bancada às 22h de 22/08/2026 e refeita às 00h de 23/08, com a
régua do PRODUTO (`daemon.state_full` mais `ocupacao_por_adaptador`): quatro
DualSense no rádio, distribuídos 1/2/1 em três adaptadores, e a coluna de áudio
em **zero nos três** — não porque o rádio recusou, mas porque ninguém pediu.

AS MORDIDAS, EXERCIDAS EM 23/08/2026 — a saída real está no relatório da leva
------------------------------------------------------------------------------

1. **`"uniqs": com_ponte` fora do bloco do `state_full`.** Reprovou
   `test_o_state_full_publica_de_quem_e_cada_ponte` — e é exatamente o estado
   em que a barra ficou cega por um mês.
2. **`com_ponte = sorted(bt_mic_sub.uniqs_pedidos(...))` no lugar de
   `uniqs_com_ponte()`.** Reprovaria o contrato de honestidade: uma ponte
   PEDIDA que não subiu não ocupa fatia de rádio nenhuma. O caso está em
   `test_o_pedido_que_nao_subiu_nao_pinta_a_barra`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.cli.ipc_client import IpcClient
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem
from hefesto_dualsense4unix.integrations.radio_da_mesa import (
    HZ_AUDIO_COM_MIC,
    HZ_INPUT_SEM_MIC,
)
from hefesto_dualsense4unix.integrations.plano_de_radio import plano_por_adaptador
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.testing import FakeController

UM = "aabbcc000001"
DOIS = "aabbcc000002"
TRES = "aabbcc000003"
QUATRO = "aabbcc000004"

ADAPTADOR_A = "aa:bb:cc:00:00:0a"
ADAPTADOR_B = "aa:bb:cc:00:00:41"
ADAPTADOR_C = "aa:bb:cc:00:00:ce"

MESA = {UM: ADAPTADOR_A, DOIS: ADAPTADOR_B, TRES: ADAPTADOR_B, QUATRO: ADAPTADOR_C}


def _bancada() -> tuple[Any, Any]:
    """Um `/sys/class/hidraw` de mentira com os quatro nós da bancada."""
    nos = {
        f"hidraw{indice}": {"HID_UNIQ": uniq, "HID_PHYS": adaptador}
        for indice, (uniq, adaptador) in enumerate(MESA.items())
    }

    def listar(_raiz: str) -> list[str]:
        return sorted(nos)

    def ler(caminho: str) -> str:
        no = Path(caminho).parent.parent.name
        campos = nos.get(no, {})
        return "".join(f"{chave}={valor}\n" for chave, valor in campos.items())

    return listar, ler


def _controles() -> list[dict[str, Any]]:
    return [
        {"uniq": uniq, "transport": "bt", "connected": True} for uniq in MESA
    ]


# 1. O elo do daemon: o `state_full` diz de QUEM é cada ponte


class _Ponte:
    def __init__(self, uniq: str) -> None:
        self.no = type("No", (), {"uniq": uniq})()


class _Gerenciador:
    def __init__(self, *uniqs: str) -> None:
        self.pontes = {uniq: _Ponte(uniq) for uniq in uniqs}


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "profiles"
    alvo.mkdir()
    monkeypatch.setattr(loader_module, "profiles_dir", lambda ensure=False: alvo)
    return alvo


@pytest.fixture
async def servidor(tmp_path: Path, isolated_profiles_dir: Path) -> Any:
    fc = FakeController(transport="bt")
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))

    daemon_mock = MagicMock()
    daemon_mock._last_state = None
    daemon_mock._bt_mic_subsystem = None
    daemon_mock._hotkey_manager = None
    daemon_mock.config = MagicMock(
        mouse_emulation_enabled=False, mouse_speed=6, mouse_scroll_speed=1,
        rumble_policy="balanceado", rumble_policy_custom_mult=0.7,
        mic_button_toggles_system=True,
    )

    socket_path = tmp_path / "hefesto-dualsense4unix.sock"
    server = IpcServer(
        controller=fc, store=store, profile_manager=manager,
        socket_path=socket_path, daemon=daemon_mock,
    )
    await server.start()
    try:
        yield socket_path, daemon_mock
    finally:
        await server.stop()


async def _state_full(socket_path: Path) -> dict[str, Any]:
    async with IpcClient.connect(socket_path) as client:
        resultado = await client.call("daemon.state_full")
    assert isinstance(resultado, dict)
    return resultado


class TestOStateFullDizDeQuemEACadaPonte:
    @pytest.mark.asyncio
    async def test_sem_subsystem_o_bloco_diz_desligado_e_a_lista_vem_vazia(
        self, servidor: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O controle negativo: a chave EXISTE, e é uma lista vazia."""
        monkeypatch.delenv("HEFESTO_DUALSENSE4UNIX_BT_MIC", raising=False)
        socket_path, _daemon = servidor
        bloco = (await _state_full(socket_path))["bt_mic"]

        assert bloco["running"] is False
        assert bloco["enabled"] is False
        assert bloco["uniqs"] == []

    @pytest.mark.asyncio
    async def test_o_state_full_publica_de_quem_e_cada_ponte(
        self, servidor: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A mordida principal desta entrega."""
        monkeypatch.delenv("HEFESTO_DUALSENSE4UNIX_BT_MIC", raising=False)
        socket_path, daemon_mock = servidor
        daemon_mock.config.bt_mic_uniqs = lambda: frozenset({UM, TRES})
        subsystem = BtMicSubsystem()
        subsystem._config = daemon_mock.config
        subsystem._gerenciador = _Gerenciador(UM, TRES)
        daemon_mock._bt_mic_subsystem = subsystem

        bloco = (await _state_full(socket_path))["bt_mic"]

        assert bloco["running"] is True
        assert bloco["enabled"] is True
        assert sorted(bloco["uniqs"]) == sorted([UM, TRES]), (
            "o `state_full` não diz de QUAIS controles a ponte está de pé — a "
            "barra de rádio fica cega e pinta áudio zero"
        )

    @pytest.mark.asyncio
    async def test_o_pedido_que_nao_subiu_nao_pinta_a_barra(
        self, servidor: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O produto responde pelo EFEITO, nunca pelo pedido."""
        monkeypatch.delenv("HEFESTO_DUALSENSE4UNIX_BT_MIC", raising=False)
        socket_path, daemon_mock = servidor
        daemon_mock.config.bt_mic_uniqs = lambda: frozenset({UM, DOIS})
        subsystem = BtMicSubsystem()
        subsystem._config = daemon_mock.config
        subsystem._gerenciador = _Gerenciador(UM)
        daemon_mock._bt_mic_subsystem = subsystem

        bloco = (await _state_full(socket_path))["bt_mic"]

        assert bloco["enabled"] is True, "os dois foram PEDIDOS"
        assert bloco["uniqs"] == [UM], "só um SUBIU"

    @pytest.mark.asyncio
    async def test_o_state_full_diz_o_que_do_sistema_segura_a_ponte(
        self, servidor: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O driver sem a guarda do áudio segura a ponte, e a tela precisa saber.

        O-PRODUTO-EM-QUALQUER-MAQUINA-01 (28/09/2026): o `BtMicSubsystem.motivo`
        diz o que do SISTEMA segura a ponte; sem a chave no `state_full`, quem
        lê o bloco vê «Desligado» sem motivo, como se fosse escolha do usuário.
        """
        from hefesto_dualsense4unix.daemon.subsystems import bt_mic

        monkeypatch.delenv("HEFESTO_DUALSENSE4UNIX_BT_MIC", raising=False)
        socket_path, daemon_mock = servidor
        assert (await _state_full(socket_path))["bt_mic"]["motivo"] == ""

        daemon_mock.config.bt_mic_uniqs = lambda: frozenset({UM})
        subsystem = BtMicSubsystem()
        subsystem._config = daemon_mock.config
        subsystem._gerenciador = _Gerenciador()
        subsystem._motivo = bt_mic.MOTIVO_SEM_A_GUARDA
        daemon_mock._bt_mic_subsystem = subsystem

        bloco = (await _state_full(socket_path))["bt_mic"]
        assert bloco["motivo"] == bt_mic.MOTIVO_SEM_A_GUARDA


def ocupacao_por_adaptador(controles, **kw):
    """A conta de ocupação de cada adaptador, pelo dono que a tela e o daemon usam."""
    return {end: plano.agora for end, plano in plano_por_adaptador(controles, **kw).items()}


class TestABarraSeMexe:


    def test_o_controle_negativo_a_coluna_de_audio_e_zero_nos_tres(self) -> None:
        """A linha de base de 22/08: quatro no rádio, nenhuma ponte."""
        listar, ler = _bancada()
        ocupacoes = ocupacao_por_adaptador(
            _controles(), com_ponte_de_mic=(), listar=listar, ler=ler
        )

        assert {end: oc.controles for end, oc in ocupacoes.items()} == {
            ADAPTADOR_A: 1, ADAPTADOR_B: 2, ADAPTADOR_C: 1
        }
        assert [oc.slots_audio for oc in ocupacoes.values()] == [0.0, 0.0, 0.0]
        assert ocupacoes[ADAPTADOR_B].slots_input == pytest.approx(
            2 * HZ_INPUT_SEM_MIC
        )


    def test_com_os_quatro_microfones_o_pior_radio_continua_abaixo_do_teto(
        self,
    ) -> None:
        """A pergunta que ela vai fazer ao ver o interruptor: *cabe em quatro?*"""
        listar, ler = _bancada()
        ocupacoes = ocupacao_por_adaptador(
            _controles(), com_ponte_de_mic=list(MESA), listar=listar, ler=ler
        )

        pior = max(oc.fracao_total for oc in ocupacoes.values())
        assert pior < 1.0, f"o pior adaptador estourou o teto: {pior:.3f}"
        assert all(oc.rotulo == "Folgada" for oc in ocupacoes.values())

    def test_ligar_um_microfone_nao_mexe_no_adaptador_do_vizinho(self) -> None:
        """"Por controle" tem de valer também na barra: uma ponte, um adaptador."""
        listar, ler = _bancada()
        ocupacoes = ocupacao_por_adaptador(
            _controles(), com_ponte_de_mic={UM}, listar=listar, ler=ler
        )

        assert ocupacoes[ADAPTADOR_A].slots_audio == pytest.approx(HZ_AUDIO_COM_MIC)
        assert ocupacoes[ADAPTADOR_B].slots_audio == 0.0
        assert ocupacoes[ADAPTADOR_C].slots_audio == 0.0

    def test_dois_adaptadores_do_mesmo_oui_nao_se_fundem(self) -> None:
        """O aviso de produto que a bancada deu em 22/08."""
        assert ADAPTADOR_A[:8] == ADAPTADOR_B[:8] == ADAPTADOR_C[:8], (
            "o cenário perdeu o OUI comum, que é a coisa toda que ele mede"
        )
        listar, ler = _bancada()

        ocupacoes = ocupacao_por_adaptador(_controles(), listar=listar, ler=ler)

        assert len(ocupacoes) == 3
        assert ocupacoes[ADAPTADOR_B].controles == 2
        assert ocupacoes[ADAPTADOR_C].controles == 1
