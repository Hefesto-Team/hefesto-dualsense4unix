"""Fixtures compartilhadas entre testes unit e integration."""

import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root():
    return Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _hefesto_fake_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Ativa HEFESTO_DUALSENSE4UNIX_FAKE=1 e ISOLA os diretórios XDG em todo teste.

    FAKE=1 — garantia defensiva: subsystems que fazem probing de hardware real
    (TouchpadReader enumerando evdev, ex.) devem pular a inicialização quando o
    flag está presente — caso contrário testes em ambiente dev com DualSense
    conectado sofrem latência extra (>60ms) que empurra janelas de teste curtas
    para fora do budget. FakeController já é o padrão nas suítes; o env var apenas
    torna esse contrato explícito para outros módulos consumirem.

    BUG-TEST-CONFIG-LEAK-01 — isola XDG_CONFIG_HOME (e data/cache/state/runtime)
    num tmp por teste. `utils.xdg_paths.config_dir()` resolve via `platformdirs`,
    que respeita `XDG_CONFIG_HOME`; sem isolamento, qualquer teste que sobe o
    Daemon lia o `~/.config/hefesto-dualsense4unix` REAL do dev e herdava as flags
    de sessão (gamepad/mouse/paused), o session.json e os profiles. Numa máquina
    com a emulação de gamepad LIGADA de verdade, o daemon de teste nascia com o
    gamepad ativo e os testes de dispatch de mouse/teclado/hotkey
    (test_poll_loop_evdev_cache, test_keyboard_wire_up) falhavam — enquanto a CI
    (HOME limpo) passava. Isolar torna a suíte hermética e independente do estado
    real do dev. Testes que precisam de config própria continuam livres para
    monkeypatchar `config_dir`/`XDG_CONFIG_HOME` por cima.
    """
    if not os.environ.get("HEFESTO_DUALSENSE4UNIX_FAKE"):
        monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_FAKE", "1")
    # XDG_RUNTIME_DIR NÃO é isolado de propósito: os testes de single_instance
    # dependem da semântica real do runtime dir (pid/socket, permissões 0700) e
    # quebram sob um tmp. O socket IPC já é isolável por nome via
    # HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME quando um teste precisa.
    #
    # Os dirs ficam sob um subdir dedicado (`.xdg/`) para NÃO colidir com testes
    # que criam `tmp_path / "config"` etc. com `exist_ok=False` na própria fixture
    # (ex.: test_service_install.isolated_systemd_user) — pytest entrega o MESMO
    # tmp_path a todas as fixtures do teste. Testes que setam o próprio
    # XDG_CONFIG_HOME por cima continuam vencendo (este é só o default hermético).
    xdg_root = tmp_path / ".xdg"
    for var, sub in (
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_DATA_HOME", "data"),
        ("XDG_CACHE_HOME", "cache"),
        ("XDG_STATE_HOME", "state"),
    ):
        target = xdg_root / sub
        target.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(var, str(target))
    # FIX-PACKAGING-SEED-PARITY-01 — desliga a semeadura automática de presets
    # (profiles.loader._maybe_seed_presets). Sem isto, o PRIMEIRO teste do
    # processo a carregar perfis receberia os JSONs de assets/profiles_default/
    # do repo no seu tmp (o flag once-per-process faria só um teste, dependente
    # da ordem, quebrar asserções de listas exatas). Os testes da semeadura
    # chamam seed_default_presets() com paths injetados ou re-habilitam via
    # monkeypatch (delenv + _seed_attempted=False).
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED", "1")
    # BROKER-01: aponta o cliente do broker hide-hidraw para um socket
    # INEXISTENTE em TODO teste. Na máquina da mantenedora o broker REAL está
    # de pé em /run/hefesto-hidraw-broker/broker.sock — um teste que
    # resolvesse o default esconderia/abriria hidraw DE VERDADE no meio da
    # suíte. Testes do próprio cliente passam o caminho explicitamente.
    monkeypatch.setenv("HEFESTO_BROKER_SOCKET", str(xdg_root / "no-broker.sock"))
