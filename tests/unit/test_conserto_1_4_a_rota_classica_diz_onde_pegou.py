"""CONSERTO 1.4 — a rota clássica do gatilho, e o default otimista.

Três defeitos, medidos contra o código de 14/08:

* **B** — sem ``uniq``, o ``trigger.set``/``trigger.reset`` respondia
  ``aplicado_em: []`` **mesmo tendo escrito**, enquanto a rota irmã ``led.set``
  respondia a mesa inteira pelo ``_registrar_em_todos``. Duas rotas irmãs,
  respostas opostas, e a tela lê as duas — "Todos" no seletor da aba Gatilhos
  manda o pedido SEM ``uniq``.
* **C** — o comentário de ``_handle_trigger_set`` listava os três casos de
  mentira como "(desconectado, sem MAC, mesa vazia)"; o terceiro da sprint é
  **Modo Nativo com output mutado**. Fato errado se substitui.
* **D** — ``_destinos_por_uniq`` caía em ``[uniq], []`` para QUALQUER palavra
  fora das listas: a sexta palavra que o backend aprendesse a dizer entraria
  calada como "aplicado".

O que este arquivo guarda com mais cuidado é o que a cura se RECUSA a afirmar.
O espelho literal do ``led.set`` seria chamar ``_registrar_em_todos`` na rota
clássica, e isso importaria uma mentira medida: com o output mutado, o
``led.set`` sem ``uniq`` responde ``aplicado_em`` com todos os MACs e ZERO byte
no fio, porque aquele laço ignora a palavra que o backend devolve.

A mesa é a de 14/08: os MACs saem do payload real de quatro controles em
``tests/fixtures/state_full_quatro_controles.json``.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import ProfileManager

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "state_full_quatro_controles.json"
)
UNIQS: list[str] = [
    c["uniq"] for c in json.loads(FIXTURE.read_text(encoding="utf-8"))["controllers"]
]
PRIMEIRO, SEGUNDO = UNIQS[0], UNIQS[1]


def _key_de(uniq: str) -> str:
    return ":".join(uniq[i : i + 2] for i in range(0, 12, 2)).upper()


class _FakeTrigger:
    def __init__(self) -> None:
        self.mode = 0
        self.forces = [0] * 7

    def setForce(self, idx: int, value: int) -> None:  # noqa: N802 — API pydualsense
        self.forces[idx] = value


class _FakeHandle:
    def __init__(self) -> None:
        self.connected = True
        self.conType = type("CT", (), {"name": "USB"})()
        self.light = type("L", (), {"setColorI": lambda self, r, g, b: None})()
        self.triggerL = _FakeTrigger()
        self.triggerR = _FakeTrigger()

    def setLeftMotor(self, intensity: int) -> None:  # noqa: N802 — API pydualsense
        return

    def setRightMotor(self, intensity: int) -> None:  # noqa: N802 — API pydualsense
        return


class _DaemonDeMentira:
    """Só o que o handler pergunta: se o Modo Nativo está ligado.

    O ``_output_mute`` do backend é escrito por UM caminho só
    (``lifecycle.set_native_mode``, conferido por grep em 14/08), então este é
    o mesmo eixo — e é a mesma fonte que o ``daemon.state_full`` publica como
    ``native_mode`` para a janela.
    """

    def __init__(self, nativo: bool = False) -> None:
        self._nativo = nativo

    def is_native_mode(self) -> bool:
        return self._nativo


def _mesa(
    tmp_path: Path, quantos: int, *, nativo: bool = False
) -> tuple[IpcServer, Any]:
    reader = EvdevReader(device_path=None)
    reader._device_path = None
    backend = PyDualSenseController(evdev_reader=reader)
    backend._handles = {  # type: ignore[assignment]
        _key_de(u): _FakeHandle() for u in UNIQS[:quantos]
    }
    if quantos:
        backend._primary_key = _key_de(PRIMEIRO)
    if nativo:
        backend.set_output_mute(True)
    store = StateStore()
    store.update_controller_state(
        ControllerState(
            battery_pct=100, l2_raw=0, r2_raw=0, connected=bool(quantos), transport="usb"
        )
    )
    server = IpcServer(
        controller=backend,
        store=store,
        profile_manager=ProfileManager(controller=backend, store=store),
        socket_path=tmp_path / "conserto_1_4.sock",
        daemon=_DaemonDeMentira(nativo),
    )
    return server, backend


_RIGIDO = {"side": "left", "mode": "Rigid", "params": [5, 200]}


class TestDefeitoBARotaClassicaDiziaVazioTendoEscrito:
    """MORDIDA — arranque `_destinos_do_broadcast` e devolva `[], []`."""

    @pytest.mark.asyncio
    async def test_com_dois_na_mesa_diz_os_dois(self, tmp_path: Path) -> None:
        server, _b = _mesa(tmp_path, 2)
        resposta = await server._handle_trigger_set(dict(_RIGIDO))
        assert resposta["aplicado_em"] == [PRIMEIRO, SEGUNDO], (
            "a escrita global pegou nos dois conectados, e a rota irmã "
            "(`led.set` sem uniq) já dizia isso — dizer `[]` aqui era a tela "
            "ler duas respostas opostas para o mesmo fato"
        )
        assert resposta["guardado_em"] == []

    @pytest.mark.asyncio
    async def test_o_desligar_sem_uniq_tambem_diz(self, tmp_path: Path) -> None:
        server, _b = _mesa(tmp_path, 2)
        resposta = await server._handle_trigger_reset({"side": "both"})
        assert resposta["aplicado_em"] == [PRIMEIRO, SEGUNDO]
        assert resposta["guardado_em"] == []

    @pytest.mark.asyncio
    async def test_o_gatilho_continua_saindo_de_verdade(self, tmp_path: Path) -> None:
        """Hipótese tem de explicar o que JÁ funcionava: a escrita não mudou."""
        server, backend = _mesa(tmp_path, 2)
        await server._handle_trigger_set(dict(_RIGIDO))
        for handle in backend._handles.values():
            assert handle.triggerL.mode != 0, "a rota clássica ainda ESCREVE"
        assert backend._desired_default.trigger_left is not None, (
            "e continua gravando no default — é ele que pinta quem chegar depois"
        )
        assert backend._desired_by_uniq == {}, (
            "e continua NIVELANDO: nenhum override por-uniq foi criado. É por "
            "isto que o espelho literal do `led.set` (`_registrar_em_todos`) "
            "não serve aqui — ele mudaria a ESCRITA, não a resposta"
        )


class TestOQueARotaClassicaSeRecusaAAfirmar:
    """O outro lado da cura: onde ela devolve vazio, e por quê."""

    @pytest.mark.asyncio
    async def test_em_modo_nativo_nao_diz_aplicado(self, tmp_path: Path) -> None:
        server, _b = _mesa(tmp_path, 2, nativo=True)
        resposta = await server._handle_trigger_set(dict(_RIGIDO))
        assert resposta["aplicado_em"] == [], (
            "o report_thread está mudo: nenhum byte sai. É exatamente o que a "
            "rota irmã ainda afirma (medido: `led.set` sem uniq com o output "
            "mutado responde os dois MACs), e importar isso seria trocar uma "
            "mentira por outra"
        )
        assert resposta["guardado_em"] == [], (
            "e nem promete: o broadcast nivela e não carimba dono, então não "
            "há promessa POR CONTROLE a publicar"
        )

    @pytest.mark.asyncio
    async def test_com_a_mesa_vazia_nao_inventa_ninguem(self, tmp_path: Path) -> None:
        server, _b = _mesa(tmp_path, 0)
        resposta = await server._handle_trigger_set(dict(_RIGIDO))
        assert resposta["aplicado_em"] == []
        assert resposta["guardado_em"] == []

    @pytest.mark.asyncio
    async def test_com_o_seletor_mirando_um_diz_so_ele(self, tmp_path: Path) -> None:
        """`_for_each` escreve SÓ no alvo — afirmar a mesa seria a mentira antiga."""
        server, backend = _mesa(tmp_path, 2)
        backend.set_output_target(1)
        resposta = await server._handle_trigger_set(dict(_RIGIDO))
        assert resposta["aplicado_em"] == [SEGUNDO]
        assert resposta["guardado_em"] == []

    @pytest.mark.asyncio
    async def test_backend_que_nao_sabe_onde_o_seletor_esta_nao_afirma(
        self, tmp_path: Path
    ) -> None:
        """Sem o getter do alvo, a resposta volta a ser o "não sei em quem".

        Backend legado que sabe LISTAR a mesa mas não sabe dizer se o seletor
        está mirando alguém: afirmar a mesa inteira aí seria adivinhar.
        """
        from hefesto_dualsense4unix.testing import FakeController

        class _SabeQuemMasNaoOndeMira(FakeController):
            def describe_controllers(self) -> list[dict[str, object]]:
                return [
                    {"index": 0, "connected": True, "uniq": PRIMEIRO},
                    {"index": 1, "connected": True, "uniq": SEGUNDO},
                ]

        fc = _SabeQuemMasNaoOndeMira(transport="usb")
        fc.connect()
        assert not hasattr(fc, "get_output_target_index")
        store = StateStore()
        server = IpcServer(
            controller=fc,
            store=store,
            profile_manager=ProfileManager(controller=fc, store=store),
            socket_path=tmp_path / "sem_seletor.sock",
            daemon=_DaemonDeMentira(),
        )
        resposta = await server._handle_trigger_set(dict(_RIGIDO))
        assert resposta["aplicado_em"] == []
        assert resposta["guardado_em"] == []


class TestDefeitoDOPadraoOtimistaDoMapa:
    """MORDIDA — devolva `[uniq], []` no fim de `_destinos_por_uniq`."""

    def test_palavra_desconhecida_nao_vira_aplicado(self) -> None:
        assert IpcServer._destinos_por_uniq("chegou_amanha", PRIMEIRO) == ([], []), (
            "vocabulário que não conhecemos não pode entrar como 'aplicado' — "
            "é a mentira que esta sprint existe para matar, com nome novo"
        )

    def test_as_cinco_palavras_de_hoje_continuam_como_estavam(self) -> None:
        """Hipótese tem de explicar o que JÁ funcionava."""
        assert IpcServer._destinos_por_uniq("escreveu", PRIMEIRO) == ([PRIMEIRO], [])
        assert IpcServer._destinos_por_uniq("registrado", PRIMEIRO) == ([], [PRIMEIRO])
        assert IpcServer._destinos_por_uniq("sem_alvo", PRIMEIRO) == ([], [])
        assert IpcServer._destinos_por_uniq("nada_a_fazer", PRIMEIRO) == ([], [])
        assert IpcServer._destinos_por_uniq("falhou", PRIMEIRO) == ([], [])

    def test_o_backend_mudo_continua_com_a_resposta_historica(self) -> None:
        """`None` é "não sei dizer", e `_apply_por_uniq` já o traduz para
        «escreveu» antes de chegar aqui — o dublê antigo não vira "guardado"."""
        assert IpcServer._destinos_por_uniq(None, PRIMEIRO) == ([], [])


class TestDefeitoCOComentarioQueListaOsTresCasos:
    """Fato errado se SUBSTITUI — a lista dos três casos estava errada."""

    def test_o_terceiro_caso_e_o_modo_nativo_e_nao_a_mesa_vazia(self) -> None:
        fonte = inspect.getsource(IpcServer._handle_trigger_set)
        assert "Modo Nativo" in fonte, (
            "o terceiro caso da sprint é o Modo Nativo com output mutado; "
            "trocá-lo por 'mesa vazia' escondia justamente o que sobrou"
        )
        assert "desconectado, sem MAC, mesa vazia" not in fonte
