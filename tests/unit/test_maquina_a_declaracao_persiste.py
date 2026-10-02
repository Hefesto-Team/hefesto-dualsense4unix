"""CONFIG-03 — o que ela DECLAROU sobre a mesa sobrevive a fechar a janela."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("o rodapé importa gui_dialogs, que puxa Gtk no topo")

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils.maquina import (
    MAQUINA_SCHEMA_VERSION,
    MaquinaConfig,
    caminho_da_maquina,
    carregar_maquina,
    fundir_declaracao,
    gravar_maquina,
)
from hefesto_dualsense4unix.utils import xdg_paths

CHAVE_DE_HARDWARE = "aabbcc00beef"

CHAVE_SINTETIZADA = "02057e20090001"[:12]

CHAVE_VOLATIL = "dev:0003:057E:2009.0001"


@pytest.fixture
def arquivo(tmp_path: Path) -> Path:
    """O ``maquina.json`` desta bancada — e a prova de que ele não é o dela.

    CANÁRIO: se algum dia o módulo resolver ``config_dir`` no topo (o defeito de
    ``app/gui_prefs.py:13``), o caminho deixa de cair no ``tmp_path`` e esta
    asserção é a única coisa entre a suíte e o ``~/.config`` da mantenedora.
    """
    caminho = caminho_da_maquina()
    assert tmp_path in caminho.parents, f"{caminho} escapou do tmp da bancada"
    return caminho


def _documento(arquivo: Path) -> dict[str, Any]:
    return dict(json.loads(arquivo.read_text(encoding="utf-8")))


class _Servidor(IpcHandlersMixin):
    """O mixin de handlers com o mínimo que o ``machine.declare`` toca."""

    def __init__(self) -> None:
        self.daemon = SimpleNamespace(_maquina=MaquinaConfig())  # type: ignore[assignment]


def _estado() -> ControllerState:
    return ControllerState(
        battery_pct=80, l2_raw=0, r2_raw=0, connected=True,
        transport="usb", buttons_pressed=frozenset(),
    )


def _config_de_daemon() -> DaemonConfig:
    return DaemonConfig(  # type: ignore[arg-type]
        poll_hz=200, auto_reconnect=False, ipc_enabled=False, udp_enabled=False,
        autoswitch_enabled=False, mouse_emulation_enabled=False,
        keyboard_emulation_enabled=False, ps_button_action="none",
        mic_button_toggles_system=False,
    )


def test_sem_arquivo_tudo_em_nao_sei(arquivo: Path) -> None:
    """Instalação nova: nenhum campo tem opinião, e nada levanta."""
    assert not arquivo.exists()
    cfg = carregar_maquina()

    assert cfg.version == MAQUINA_SCHEMA_VERSION
    assert cfg.mesa.altura_da_antena is None
    assert cfg.mesa.linha_de_visada is None
    assert cfg.mesa.radios == {}
    assert cfg.controles == {}
    assert cfg.orcamento.teto is None


def test_json_truncado_e_nao_objeto_caem_no_default(arquivo: Path) -> None:
    """Metade de um JSON, e um JSON que é lista: os dois viram "não sei"."""
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text('{"version": 1, "mesa": {"altura_da', encoding="utf-8")
    assert carregar_maquina().mesa.altura_da_antena is None
    assert gravar_maquina({"mesa": {"altura_da_antena": "abaixo"}})
    assert carregar_maquina().mesa.altura_da_antena == "abaixo"

    arquivo.write_text('["nem objeto é"]', encoding="utf-8")
    assert carregar_maquina().mesa.altura_da_antena is None
    assert gravar_maquina({"orcamento": {"teto": "auto"}})
    assert carregar_maquina().orcamento.teto == "auto"

    arquivo.write_text('{"version": 1, "orcamento": {"teto": "plan9"}}', encoding="utf-8")
    assert carregar_maquina().orcamento.teto is None


def test_ida_e_volta(arquivo: Path) -> None:
    """O que foi declarado volta igual — e o arquivo só tem o que ela declarou."""
    assert gravar_maquina(
        {
            "mesa": {"altura_da_antena": "acima", "linha_de_visada": "livre"},
            "orcamento": {"teto": "economia"},
            "controles": {CHAVE_DE_HARDWARE: {"modo": "switch", "cor": "Volcanic Red"}},
        }
    )

    cfg = carregar_maquina()
    assert cfg.mesa.altura_da_antena == "acima"
    assert cfg.mesa.linha_de_visada == "livre"
    assert cfg.orcamento.teto == "economia"
    assert cfg.controles[CHAVE_DE_HARDWARE].modo == "switch"
    assert cfg.controles[CHAVE_DE_HARDWARE].cor == "Volcanic Red"

    documento = _documento(arquivo)
    assert documento["version"] == 1
    assert "botoes" not in documento["controles"][CHAVE_DE_HARDWARE]
    assert "radios" not in documento["mesa"]


def test_a_fusao_nao_apaga_o_que_outra_secao_declarou(arquivo: Path) -> None:
    """Cinco seções, um arquivo: a última a gravar não apaga as outras quatro."""
    assert gravar_maquina({"mesa": {"altura_da_antena": "acima"}})
    assert gravar_maquina({"orcamento": {"teto": "max"}})
    assert gravar_maquina({"mesa": {"linha_de_visada": "com_gente"}})
    assert gravar_maquina(
        {"mesa": {"radios": {"046d:c52b": {"tipo": "mouse", "apelido": "Da TV"}}}}
    )

    cfg = carregar_maquina()
    assert cfg.mesa.altura_da_antena == "acima"
    assert cfg.mesa.linha_de_visada == "com_gente"
    assert cfg.orcamento.teto == "max"
    assert cfg.mesa.radios["046d:c52b"].tipo == "mouse"
    assert cfg.mesa.radios["046d:c52b"].apelido == "Da TV"


def test_none_declarado_volta_para_nao_sei(arquivo: Path) -> None:
    """``None`` presente é escolha ("voltei para 'Não sei'"), e sobrescreve."""
    assert gravar_maquina(
        {"mesa": {"altura_da_antena": "acima", "linha_de_visada": "livre"}}
    )
    assert gravar_maquina({"mesa": {"altura_da_antena": None}})

    cfg = carregar_maquina()
    assert cfg.mesa.linha_de_visada == "livre"
    assert cfg.mesa.altura_da_antena is None


def test_fundir_declaracao_nao_escreve_no_dicionario_de_origem() -> None:
    """A fusão devolve documento novo até no fundo; ninguém edita o de origem."""
    base: dict[str, Any] = {
        "mesa": {"altura_da_antena": "acima", "radios": {"046d:c52b": {"tipo": "mouse"}}}
    }
    fundido = fundir_declaracao(base, {"mesa": {"linha_de_visada": "livre"}})

    assert fundido["mesa"]["altura_da_antena"] == "acima"
    assert fundido["mesa"]["linha_de_visada"] == "livre"
    assert "linha_de_visada" not in base["mesa"]

    fundido["mesa"]["radios"]["046d:c52b"]["tipo"] = "webcam"
    assert base["mesa"]["radios"]["046d:c52b"]["tipo"] == "mouse"


def test_versao_desconhecida_nao_e_lida_nem_sobrescrita(arquivo: Path) -> None:
    """Escolha de alguém não se destrói para registrar outra."""
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(
        '{"version": 2, "mesa": {"altura_da_antena": "no_teto"}}', encoding="utf-8"
    )
    antes = arquivo.read_bytes()

    assert gravar_maquina({"mesa": {"altura_da_antena": "abaixo"}}) is False
    assert arquivo.read_bytes() == antes
    assert carregar_maquina().mesa.altura_da_antena is None


def test_chave_de_topo_de_uma_versao_futura_sobrevive_ao_save(arquivo: Path) -> None:
    """O save preserva o que não entende — a lição do ``identity.py:633``."""
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(
        json.dumps({"version": 1, "ambiente": "gnome", "planeta": {"gravidade": 1}}),
        encoding="utf-8",
    )

    assert gravar_maquina({"orcamento": {"teto": "auto"}})

    documento = _documento(arquivo)
    assert documento["ambiente"] == "gnome"
    assert documento["orcamento"] == {"teto": "auto"}
    assert documento["planeta"] == {"gravidade": 1}


def test_ambiente_de_um_maquina_json_antigo_nao_apaga_a_mesa(arquivo: Path) -> None:
    """T2, CONFIGURAÇÕES-FECHA-01: o campo saiu do esquema — um arquivo antigo"""
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(
        json.dumps(
            {"version": 1, "ambiente": "gnome", "mesa": {"altura_da_antena": "acima"}}
        ),
        encoding="utf-8",
    )

    cfg = carregar_maquina()

    assert cfg.mesa.altura_da_antena == "acima"
    assert not hasattr(cfg, "ambiente")


def test_campo_invalido_ao_carregar_nao_apaga_o_resto(arquivo: Path) -> None:
    """O resgate campo a campo vale na LEITURA, não só na escrita."""
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(
        json.dumps(
            {
                "version": 1,
                "mesa": {"altura_da_antena": "acima"},
                "orcamento": {"teto": "generosa"},
            }
        ),
        encoding="utf-8",
    )

    cfg = carregar_maquina()

    assert cfg.mesa.altura_da_antena == "acima"
    assert cfg.orcamento.teto is None


@pytest.mark.parametrize("chave", [CHAVE_SINTETIZADA, CHAVE_VOLATIL, "AABBCC00BEEF"])
def test_chave_de_controle_que_nao_e_mac_de_hardware_e_recusada(
    arquivo: Path, chave: str
) -> None:
    """Sintetizada, volátil e maiúscula: as três ficam fora do disco."""
    with pytest.raises(ValueError):
        gravar_maquina({"controles": {chave: {"cor": "Branco"}}})
    assert not arquivo.exists()


def test_a_faixa_forjada_da_bancada_nao_e_confundida_com_sintese(arquivo: Path) -> None:
    """``aa:bb:cc:*`` tem o bit 0x02 ligado sem ser síntese nossa — e passa."""
    assert gravar_maquina({"controles": {CHAVE_DE_HARDWARE: {"botoes": "nintendo"}}})
    assert carregar_maquina().controles[CHAVE_DE_HARDWARE].botoes == "nintendo"


def test_chave_de_radio_fora_de_vid_pid_e_recusada(arquivo: Path) -> None:
    """``extra="forbid"`` não protege chave de DICIONÁRIO — o validador protege."""
    with pytest.raises(ValueError):
        gravar_maquina({"mesa": {"radios": {"Fone da TV": {"tipo": "outro"}}}})
    with pytest.raises(ValueError):
        gravar_maquina({"mesa": {"radios": {"046D:C52B": {"tipo": "mouse"}}}})
    assert not arquivo.exists()


def test_chave_desconhecida_e_recusada_pelo_forbid(arquivo: Path) -> None:
    """Campo que não conhecemos não entra — nem no topo, nem dentro de uma seção."""
    with pytest.raises(ValueError):
        gravar_maquina({"altura_da_antena": "acima"})
    with pytest.raises(ValueError):
        gravar_maquina({"mesa": {"altura_da_antenna": "acima"}})
    assert not arquivo.exists()


def test_o_rotulo_maximo_e_recusado_e_a_chave_max_e_aceita(arquivo: Path) -> None:
    """A chave é ``max``; ``"Máximo"`` é o rótulo de tela, e não vai ao disco."""
    with pytest.raises(ValueError):
        gravar_maquina({"orcamento": {"teto": "máximo"}})
    assert gravar_maquina({"orcamento": {"teto": "max"}})
    assert carregar_maquina().orcamento.teto == "max"


@pytest.mark.asyncio
async def test_o_daemon_le_no_boot(arquivo: Path) -> None:
    """O boot do daemon carrega a declaração do disco, sem exceção."""
    assert gravar_maquina(
        {"orcamento": {"teto": "economia"}, "mesa": {"altura_da_antena": "acima"}}
    )

    store = StateStore()
    daemon = Daemon(
        controller=FakeController(transport="usb", states=[_estado()]),
        bus=EventBus(), store=store, config=_config_de_daemon(),
    )
    assert daemon._maquina.orcamento.teto is None

    tarefa = asyncio.create_task(daemon.run())
    for _ in range(500):
        if store.counter("poll.tick") >= 1:
            break
        await asyncio.sleep(0.01)
    lido = daemon._maquina
    daemon.stop()
    await tarefa

    assert lido.orcamento.teto == "economia"
    assert lido.mesa.altura_da_antena == "acima"


def test_o_metodo_esta_no_dispatcher() -> None:
    """``machine.declare`` está registrado — a metade declarativa."""
    servidor = IpcServer(
        controller=FakeController(transport="usb", states=[_estado()]),
        store=StateStore(),
        profile_manager=None,  # type: ignore[arg-type]
    )
    assert servidor._handlers["machine.declare"].__name__ == "_handle_machine_declare"


@pytest.mark.asyncio
async def test_o_handler_grava_e_recusa_no_corpo(arquivo: Path) -> None:
    """Sucesso, recusa por versão e declaração inválida — as três NO CORPO."""
    servidor = _Servidor()

    assert await servidor._handle_machine_declare(
        {"maquina": {"mesa": {"linha_de_visada": "com_gente"}}}
    ) == {"ok": True}
    assert servidor.daemon._maquina.mesa.linha_de_visada == "com_gente"

    arquivo.write_text('{"version": 2}', encoding="utf-8")
    antes = arquivo.read_bytes()
    assert await servidor._handle_machine_declare(
        {"maquina": {"mesa": {"linha_de_visada": "livre"}}}
    ) == {"ok": False, "reason": "versao_desconhecida"}
    assert arquivo.read_bytes() == antes

    assert await servidor._handle_machine_declare({"maquina": {"nao_existe": 1}}) == {
        "ok": False,
        "reason": "declaracao_invalida",
    }
    assert await servidor._handle_machine_declare({"maquina": "texto"}) == {
        "ok": False,
        "reason": "declaracao_invalida",
    }


def test_a_ponte_traduz_o_motivo_e_distingue_daemon_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tela nunca lê ``versao_desconhecida``, e "offline" não é "recusado"."""
    respostas: list[Any] = []
    monkeypatch.setattr(
        ipc_bridge, "_safe_call", lambda *a, **k: respostas.pop(0)
    )

    respostas.append((True, {"ok": True}))
    assert ipc_bridge.machine_declare({"orcamento": {"teto": "auto"}}) == (True, None)

    respostas.append((True, {"ok": False, "reason": "versao_desconhecida"}))
    ok, motivo = ipc_bridge.machine_declare({"orcamento": {"teto": "auto"}})
    assert ok is False
    assert motivo is not None
    assert "versao_desconhecida" not in motivo
    assert "versão mais nova" in motivo

    respostas.append((False, None))
    assert ipc_bridge.machine_declare({"orcamento": {"teto": "auto"}}) == (False, None)


@pytest.mark.asyncio
async def test_ida_e_volta_pelo_socket_de_verdade(
    tmp_path: Path, arquivo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O caminho inteiro sobre o fio: ponte da GUI → JSON-RPC → daemon → disco."""
    import shutil
    import tempfile

    berco = Path(tempfile.mkdtemp(prefix="hef-e2e-"))
    runtime = berco / "run"
    runtime.mkdir(mode=0o700)
    runtime.chmod(0o700)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))
    assert xdg_paths.runtime_dir().parent == runtime, (
        "o runtime resolveu fora do berço: a ponte falaria com o da máquina")
    caminho = runtime / "hefesto-dualsense4unix" / "e2e.sock"
    assert len(str(caminho)) < 100, (
        f"o berço do socket mede {len(str(caminho))} caracteres e o teto do "
        f"`AF_UNIX` é 108: {caminho}. Esta régua morreria por endereço longo, "
        f"não por defeito.")
    servidor = IpcServer(
        controller=FakeController(transport="usb", states=[_estado()]),
        store=StateStore(),
        profile_manager=None,  # type: ignore[arg-type]
        socket_path=caminho,
        daemon=SimpleNamespace(_maquina=MaquinaConfig()),
    )
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME", "e2e.sock")
    await servidor.start()
    try:
        laco = asyncio.get_running_loop()
        primeira = await laco.run_in_executor(
            None, ipc_bridge.machine_declare, {"mesa": {"altura_da_antena": "acima"}}
        )
        assert primeira == (True, None)
        segunda = await laco.run_in_executor(
            None, ipc_bridge.machine_declare, {"orcamento": {"teto": "economia"}}
        )
        assert segunda == (True, None)
    finally:
        await servidor.stop()
        shutil.rmtree(berco, ignore_errors=True)

    assert _documento(arquivo) == {
        "version": 1,
        "mesa": {"altura_da_antena": "acima"},
        "orcamento": {"teto": "economia"},
    }
    assert servidor.daemon._maquina.orcamento.teto == "economia"
