"""CONFIG-06 (23/08/2026) — o que a gravação descartou CHEGA à tela.

O DEFEITO, medido na árvore de 23/08: ``gravar_maquina_com_descartes``
(``utils/maquina.py:340``) devolve ``ResultadoDaGravacao(gravou, descartados)``,
e o handler ``machine.declare`` chamava o embrulho ``gravar_maquina``
(``utils/maquina.py:335``), que estreita o resultado para ``bool`` e joga a
lista fora. Nenhum consumidor em ``src/`` — só a bateria de ``utils``. A
informação existia, atravessava a função e morria ali: a pessoa perdia um campo
do ``maquina.json`` dela sem uma palavra.

O ARCO QUE ESTA BATERIA VIGIA, elo por elo:

1. o handler devolve ``descartados`` no corpo do SUCESSO, e **só quando há algo
   a dizer** — lista vazia não entra, porque "descartei zero campos" é ruído;
2. a chave atravessa o JSON-RPC de verdade (socket, não dublê);
3. a ponte traduz o nome CRU do schema para o rótulo da seção que o declara — a
   mesma fronteira e a mesma regra do ``_MOTIVOS_MAQUINA``: a usuária nunca lê
   identificador de protocolo na barra de status;
4. o rodapé compõe a frase, e ela sobrevive ao toast do "Aplicar" pelo contrato
   ADITIVO do A3 (``_recado_da_maquina``) — não por um segundo caminho até a
   statusbar;
5. o mapa de rótulos cobre TODO campo de topo do schema, para um campo novo não
   nascer aparecendo cru na tela.

Bancada: nenhum aparelho, nenhum MAC. O ``config_dir`` é o isolado por
``_hefesto_fake_env`` (``tests/conftest.py``), e a fixture ``arquivo`` prova a
cada teste que ele caiu sob o ``tmp_path``.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("o rodapé importa gui_dialogs, que puxa Gtk no topo")

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from gi.repository import Gtk

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.actions import footer_actions
from hefesto_dualsense4unix.app.actions.footer_actions import FooterActionsMixin
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils.maquina import (
    MAQUINA_SCHEMA_VERSION,
    MaquinaConfig,
    caminho_da_maquina,
)

#: O documento em disco que força um descarte: ``teto`` fora do catálogo derruba
#: o ``orcamento`` sozinho, e a ``mesa`` ao lado dele SOBREVIVE — é a cura de
#: 23/08 (``_o_que_ainda_vale``) que esta bateria assume de pé.
DISCO_COM_CAMPO_INVALIDO: dict[str, Any] = {
    "version": MAQUINA_SCHEMA_VERSION,
    "orcamento": {"teto": "turbo"},
    "mesa": {"altura_da_antena": "acima"},
}

#: O rótulo de tela do campo descartado — o ``TITULO`` de
#: ``app/actions/config/secao_orcamento.py``.
ROTULO_DO_ORCAMENTO = "Orçamento"


@pytest.fixture
def arquivo(tmp_path: Path) -> Path:
    """O ``maquina.json`` desta bancada — e a prova de que ele não é o dela."""
    caminho = caminho_da_maquina()
    assert tmp_path in caminho.parents, f"{caminho} escapou do tmp da bancada"
    return caminho


def _corromper(arquivo: Path) -> None:
    arquivo.write_text(json.dumps(DISCO_COM_CAMPO_INVALIDO), encoding="utf-8")


class _Servidor(IpcHandlersMixin):
    """O mixin de handlers com o mínimo que o ``machine.declare`` toca."""

    def __init__(self) -> None:
        self.daemon = SimpleNamespace(_maquina=MaquinaConfig())  # type: ignore[assignment]


class _Rodape(FooterActionsMixin):
    """O rodapé com uma ``Gtk.Statusbar`` REAL — sem ``_status_toast`` de mentira.

    A barra de verdade é o ponto, e a razão está em
    ``test_a3_o_aplicar_responde_no_rodape.py``: um dublê que só CRESCE não
    enxerga a frase que é apagada no mesmo tique do GTK. A afirmação daqui é
    sobre o texto FINAL do rótulo.
    """

    def __init__(self, declaracao: dict[str, Any]) -> None:
        self.draft = DraftConfig.default()
        self.barra = Gtk.Statusbar()
        self._maquina_pendente: dict[str, Any] | None = dict(declaracao)

    def _get(self, widget_id: str) -> Any:
        return self.barra if widget_id == "status_bar" else None

    def pegar_carona_no_gesto(self, _gesto: str) -> None:
        pass

    @property
    def texto_da_barra(self) -> str:
        rotulo = self.barra.get_message_area().get_children()[0]
        return str(rotulo.get_text())


def _estado() -> ControllerState:
    return ControllerState(
        battery_pct=80, l2_raw=0, r2_raw=0, connected=True,
        transport="usb", buttons_pressed=frozenset(),
    )


# ---------------------------------------------------------------------------
# 1. O handler devolve a lista — e cala quando não há nada a dizer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_o_handler_devolve_os_descartados_no_corpo_do_sucesso(
    arquivo: Path,
) -> None:
    """A metade "e DIZ" da cura de 23/08.

    MORDE: trocando ``gravar_maquina_com_descartes`` por ``gravar_maquina`` no
    ``_handle_machine_declare`` — o embrulho estreita o resultado para ``bool``
    e a chave some do corpo.
    """
    _corromper(arquivo)
    resposta = await _Servidor()._handle_machine_declare(
        {"maquina": {"mesa": {"linha_de_visada": "livre"}}}
    )
    assert resposta == {"ok": True, "descartados": ["orcamento"]}
    # A cura de que esta bateria depende: o estrago parou no campo ruim.
    documento = json.loads(arquivo.read_text(encoding="utf-8"))
    assert documento["mesa"] == {"altura_da_antena": "acima", "linha_de_visada": "livre"}
    assert "orcamento" not in documento


@pytest.mark.asyncio
async def test_sem_descarte_o_corpo_e_o_de_sempre(arquivo: Path) -> None:
    """Lista vazia não vai no corpo — silêncio ali é a resposta certa.

    "Descartei zero campos" é ruído, e a chave presente-e-vazia obrigaria todo
    consumidor a distinguir ``[]`` de ausente.

    MORDE: devolvendo ``{"ok": True, "descartados": list(...)}`` sempre —
    reprova aqui com ``{'ok': True, 'descartados': []}``.
    """
    assert await _Servidor()._handle_machine_declare(
        {"maquina": {"mesa": {"linha_de_visada": "livre"}}}
    ) == {"ok": True}


# ---------------------------------------------------------------------------
# 2 e 3. O fio e a tradução
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_lista_atravessa_o_fio(
    tmp_path: Path, arquivo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ponte da GUI → JSON-RPC → daemon → disco → e a lista de volta.

    Um elo que só existe no fio: a FORMA do corpo. Uma ponte que lesse
    ``result["campos"]`` passa em todo teste de unidade e falha aqui.

    Socket próprio em ``tmp_path`` e ``XDG_RUNTIME_DIR`` isolado: o daemon VIVO
    da máquina dela nunca é tocado.

    MORDE: tirando o ``_rotulos_dos_descartados`` do ramo do ``ok`` na
    ``machine_declare_detalhado`` — reprova com ``()`` no lugar do rótulo.
    """
    _corromper(arquivo)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    servidor = IpcServer(
        controller=FakeController(transport="usb", states=[_estado()]),
        store=StateStore(),
        profile_manager=None,  # type: ignore[arg-type]
        socket_path=tmp_path / "run" / "hefesto-dualsense4unix" / "d.sock",
        daemon=SimpleNamespace(_maquina=MaquinaConfig()),
    )
    monkeypatch.setenv(
        "HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME", "d.sock"
    )
    await servidor.start()
    try:
        laco = asyncio.get_running_loop()
        resposta = await laco.run_in_executor(
            None,
            ipc_bridge.machine_declare_detalhado,
            {"mesa": {"linha_de_visada": "livre"}},
        )
    finally:
        await servidor.stop()
    assert resposta == (True, None, (ROTULO_DO_ORCAMENTO,))


def test_a_ponte_nunca_entrega_identificador_de_protocolo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``orcamento`` vira "Orçamento"; ``mesa`` vira "A mesa".

    MORDE: devolvendo ``tuple(descartados)`` cru em vez de passar pelo
    ``_CAMPOS_DA_MAQUINA`` — reprova, e a barra de status passaria a mostrar o
    nome do campo JSON.
    """
    monkeypatch.setattr(
        ipc_bridge,
        "_safe_call",
        lambda *a, **k: (
            True,
            {"ok": True, "descartados": ["mesa", "orcamento"]},
        ),
    )
    ok, motivo, descartados = ipc_bridge.machine_declare_detalhado(
        {"mesa": {"linha_de_visada": "livre"}}
    )
    assert (ok, motivo) == (True, None)
    assert descartados == ("A mesa", ROTULO_DO_ORCAMENTO)


def test_o_embrulho_de_duas_pontas_continua_valendo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``machine_declare`` segue devolvendo ``(ok, motivo)`` — contrato de quem já chama.

    A função está no ``__all__``, e trocar a aridade dela quebraria todo
    chamador que não fosse migrado na mesma leva. Aditivo é a regra desta
    fronteira (ver ``apply_draft``/``apply_draft_detalhado``).
    """
    monkeypatch.setattr(
        ipc_bridge,
        "_safe_call",
        lambda *a, **k: (True, {"ok": True, "descartados": ["mesa"]}),
    )
    assert ipc_bridge.machine_declare({"mesa": {"linha_de_visada": "livre"}}) == (True, None)


def test_corpo_torto_do_daemon_nao_derruba_o_aplicar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Daemon velho (sem a chave) e valor torto caem no silêncio, não no traceback.

    É fronteira entre processos: o daemon vivo desta casa é mais velho que o
    código (install editable), e um "Aplicar" que gravou não pode explodir por
    causa do aviso.
    """
    corpos: list[dict[str, Any]] = [
        {"ok": True},
        {"ok": True, "descartados": "orcamento"},
        {"ok": True, "descartados": [None, "", "orcamento"]},
    ]
    monkeypatch.setattr(
        ipc_bridge, "_safe_call", lambda *a, **k: (True, corpos.pop(0))
    )
    assert ipc_bridge.machine_declare_detalhado({"mesa": {"linha_de_visada": "livre"}})[2] == ()
    assert ipc_bridge.machine_declare_detalhado({"mesa": {"linha_de_visada": "livre"}})[2] == ()
    assert ipc_bridge.machine_declare_detalhado({"mesa": {"linha_de_visada": "livre"}})[2] == (
        ROTULO_DO_ORCAMENTO,
    )


# ---------------------------------------------------------------------------
# 4. A MORDIDA: a frase chega ao rótulo do rodapé
# ---------------------------------------------------------------------------


def test_a_frase_do_descarte_chega_ao_rotulo_do_rodape(
    arquivo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Disco corrompido + declaração nova → o rótulo NOMEIA o que se perdeu.

    O caminho inteiro sem dublê no meio: o ``_safe_call`` da ponte entra no
    handler DE VERDADE, que grava no disco DE VERDADE, e a resposta volta pela
    ponte real até a statusbar real. O único dublê é o ``call_async`` da
    aplicação de perfil, que não é assunto desta bateria.

    MORDE: em qualquer elo do encanamento — o handler voltando a chamar
    ``gravar_maquina``, a ponte largando a lista, ou o rodapé devolvendo
    ``"Configurações gravadas."`` sem olhar os descartes.
    """
    _corromper(arquivo)
    servidor = _Servidor()

    def _pelo_handler(metodo: str, params: Any, **_kw: Any) -> tuple[bool, Any]:
        assert metodo == "machine.declare"
        return True, asyncio.run(servidor._handle_machine_declare(params))

    monkeypatch.setattr(ipc_bridge, "_safe_call", _pelo_handler)
    monkeypatch.setattr(
        footer_actions.ipc_bridge,
        "call_async",
        lambda *_a, on_success=None, **_k: on_success(
            {"status": "ok", "applied": ["leds"]}
        ),
    )

    rodape = _Rodape({"mesa": {"linha_de_visada": "livre"}})
    rodape.on_apply_draft()

    texto = rodape.texto_da_barra
    assert ROTULO_DO_ORCAMENTO in texto, (
        "a pessoa tem de saber O QUE se perdeu; o rótulo diz " f"{texto!r}"
    )
    assert "descartou" in texto
    assert "aplicado" in texto, (
        "o recado do descarte não pode COMER o resultado da aplicação — é o "
        "contrato aditivo do `_recado_da_maquina` (A3)"
    )
    assert rodape._maquina_pendente is None, "gravou: a pendência sai"


def test_sem_descarte_o_rodape_nao_inventa_aviso(
    arquivo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Disco são → a frase de sempre, sem uma palavra sobre descarte.

    MORDE: compondo a frase do descarte com lista vazia — reprova aqui, e todo
    "Aplicar" passaria a dizer "descartou: ." no rodapé.
    """
    servidor = _Servidor()
    monkeypatch.setattr(
        ipc_bridge,
        "_safe_call",
        lambda _m, params, **_k: (
            True,
            asyncio.run(servidor._handle_machine_declare(params)),
        ),
    )
    monkeypatch.setattr(
        footer_actions.ipc_bridge,
        "call_async",
        lambda *_a, on_success=None, **_k: on_success({"status": "ok"}),
    )

    rodape = _Rodape({"mesa": {"linha_de_visada": "livre"}})
    rodape.on_apply_draft()

    texto = rodape.texto_da_barra
    assert "Configurações gravadas." in texto
    assert "descart" not in texto


# ---------------------------------------------------------------------------
# 5. O portão do mapa de rótulos
# ---------------------------------------------------------------------------


def test_todo_campo_do_schema_tem_rotulo_de_tela() -> None:
    """Campo novo no schema nasce com rótulo — ou esta bateria reprova.

    Sem este portão, alargar o ``MaquinaConfig`` faria a frase do descarte
    mostrar o nome cru do campo JSON na barra de status, e ninguém notaria até
    o dia em que o arquivo de alguém tivesse aquele campo corrompido.

    ``version`` fica de fora de propósito: ele nunca entra na lista de
    descartados (``_o_que_ainda_vale`` o pula), e não é escolha de ninguém.
    """
    do_schema = set(MaquinaConfig.model_fields) - {"version"}
    faltando = do_schema - set(ipc_bridge._CAMPOS_DA_MAQUINA)
    assert not faltando, (
        f"campo(s) sem rótulo de tela em `_CAMPOS_DA_MAQUINA`: {sorted(faltando)}"
    )
    sobrando = set(ipc_bridge._CAMPOS_DA_MAQUINA) - do_schema
    assert not sobrando, (
        f"rótulo para campo que o schema não tem mais: {sorted(sobrando)}"
    )
