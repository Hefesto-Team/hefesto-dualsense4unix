"""SENSORES-NO-JOGO-02: o jogo recebe `SDL_ACCELEROMETER_AS_JOYSTICK=0`, do daemon ao env(1)."""
from __future__ import annotations

import ctypes
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import launch_env
from hefesto_dualsense4unix.daemon.launch_env import (
    ENV_ALLOWLIST,
    compose_env,
    materialize_launch_env,
)

_DICA = "SDL_ACCELEROMETER_AS_JOYSTICK"
_RAIZ = Path(__file__).resolve().parents[2]
_WRAPPER = _RAIZ / "assets" / "hefesto-launch.sh"

_VARIANTES: dict[str, dict[str, Any]] = {
    "nativo": dict(native_mode=True, emulation_enabled=False, flavor="dualsense", backends=[]),
    "emulacao_desligada": dict(
        native_mode=False, emulation_enabled=False, flavor="dualsense", backends=[]
    ),
    "sem_vpad_vivo": dict(
        native_mode=False, emulation_enabled=True, flavor="dualsense", backends=[]
    ),
    "dualsense_uhid": dict(
        native_mode=False, emulation_enabled=True, flavor="dualsense",
        backends=["uhid"], fisicos=1,
    ),
    "dualsense_degradado": dict(
        native_mode=False, emulation_enabled=True, flavor="dualsense",
        backends=["uinput"], fisicos=1,
    ),
    "coop_misto": dict(
        native_mode=False, emulation_enabled=True, flavor="dualsense",
        backends=["uhid", "uinput"], fisicos=2,
    ),
    "sem_cobertura": dict(
        native_mode=False, emulation_enabled=True, flavor="dualsense",
        backends=["uhid"], fisicos=2,
    ),
    "xbox": dict(
        native_mode=False, emulation_enabled=True, flavor="xbox",
        backends=["uinput"], fisicos=1,
    ),
    "nintendo": dict(
        native_mode=False, emulation_enabled=True, flavor="nintendo",
        backends=["uinput"], fisicos=1,
    ),
}


@pytest.mark.parametrize("variante", sorted(_VARIANTES))
def test_toda_variante_do_env_do_jogo_leva_a_dica_em_zero(variante: str) -> None:
    env = compose_env(**_VARIANTES[variante])
    assert env.get(_DICA) == "0", (
        f"a variante «{variante}» saiu sem {_DICA}=0: um jogo com a libSDL2 "
        "2.30.x volta a ouvir que o vpad não tem giroscópio"
    )


def test_a_dica_mora_na_allowlist() -> None:
    assert _DICA in ENV_ALLOWLIST


def _nomes_do_case_do_wrapper() -> set[str]:
    """Os nomes que o `case` de `decide_envs` deixa passar, lidos do `sh` real."""
    texto = _WRAPPER.read_text(encoding="utf-8")
    corpo = texto.split("decide_envs() {", 1)[1].split("\n}\n", 1)[0]
    return set(re.findall(r"^\s+([A-Za-z_][A-Za-z0-9_]*)=\*\)", corpo, re.MULTILINE))


def test_o_case_do_wrapper_e_a_allowlist_sao_o_mesmo_conjunto() -> None:
    """O espelho nos DOIS sentidos: nome só de um lado é variável morta calada."""
    no_case = _nomes_do_case_do_wrapper()
    na_allowlist = set(ENV_ALLOWLIST)
    assert no_case == na_allowlist, (
        f"só no wrapper: {sorted(no_case - na_allowlist)}; "
        f"só na allowlist: {sorted(na_allowlist - no_case)}"
    )


class _SocketQueResponde:
    """O gate de vida do wrapper: aceita e responde uma linha JSON-RPC com `result`."""

    def __init__(self, caminho: Path) -> None:
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(str(caminho))
        self._sock.listen(2)
        self._parar = threading.Event()
        self._fio = threading.Thread(target=self._servir, daemon=True)
        self._fio.start()

    def _servir(self) -> None:
        while not self._parar.is_set():
            try:
                self._sock.settimeout(0.2)
                conexao, _ = self._sock.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with conexao:
                try:
                    conexao.settimeout(1.0)
                    pedido = json.loads(conexao.recv(4096).decode("utf-8"))
                    resposta = {"jsonrpc": "2.0", "id": pedido.get("id"), "result": {}}
                    conexao.sendall(json.dumps(resposta).encode("utf-8") + b"\n")
                except (OSError, ValueError):
                    pass

    def parar(self) -> None:
        self._parar.set()
        self._sock.close()
        self._fio.join(timeout=2)


def _path_minimo(pasta: Path) -> str:
    """Só o que o wrapper precisa para exportar e fazer o `exec` — sem Game Mode."""
    pasta.mkdir()
    for ferramenta in ("sh", "python3", "env", "date", "mkdir", "mv"):
        real = shutil.which(ferramenta)
        assert real is not None, f"ferramenta de teste ausente: {ferramenta}"
        (pasta / ferramenta).symlink_to(real)
    return str(pasta)


def _daemon_de_mentira() -> SimpleNamespace:
    return SimpleNamespace(
        is_native_mode=lambda: False,
        config=SimpleNamespace(gamepad_emulation_enabled=True, gamepad_flavor="dualsense"),
        _gamepad_device=SimpleNamespace(backend="uhid"),
        _coop_manager=None,
        controller=SimpleNamespace(),
    )


def test_a_dica_atravessa_o_arquivo_e_o_wrapper_ate_o_processo_do_jogo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    estado = tmp_path / "estado"
    pasta = estado / "hefesto-dualsense4unix" / "launch_env"
    pasta.mkdir(parents=True)
    monkeypatch.setattr(launch_env, "launch_env_dir", lambda ensure=False: pasta)
    materialize_launch_env(_daemon_de_mentira())
    linhas = (pasta / "default.env").read_text(encoding="utf-8").splitlines()
    assert f"{_DICA}=0" in linhas, "o daemon não materializou a dica no default.env"

    runtime = Path(tempfile.mkdtemp(prefix="hefa-"))
    (runtime / "hefesto-dualsense4unix").mkdir()
    servidor = _SocketQueResponde(
        runtime / "hefesto-dualsense4unix" / "hefesto-dualsense4unix.sock"
    )
    try:
        feito = subprocess.run(
            ["sh", str(_WRAPPER), "sh", "-c", f'printf "%s\\n" "${{{_DICA}:-ausente}}"'],
            env={
                "PATH": _path_minimo(tmp_path / "bin"),
                "HOME": os.environ.get("HOME", "/tmp"),
                "XDG_RUNTIME_DIR": str(runtime),
                "XDG_STATE_HOME": str(estado),
                "SteamAppId": "1599660",
            },
            capture_output=True,
            text=True,
            timeout=15.0,
            check=False,
        )
    finally:
        servidor.parar()
        shutil.rmtree(runtime, ignore_errors=True)
    assert feito.returncode == 0, feito.stderr
    assert feito.stdout.strip() == "0", (
        f"o processo embrulhado leu «{feito.stdout.strip()}»: a dica não passou do wrapper"
    )


def _carregar_ensaio(nome: str) -> ModuleType:
    caminho = _RAIZ / "scripts" / "ensaios" / nome
    spec = importlib.util.spec_from_file_location(f"_ensaio_{caminho.stem}", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    monkeypatch_modulos = sys.modules
    monkeypatch_modulos[spec.name] = modulo
    try:
        spec.loader.exec_module(modulo)
    finally:
        monkeypatch_modulos.pop(spec.name, None)
    return modulo


def test_o_ensaio_de_ambiente_do_jogo_le_a_dica() -> None:
    """`quem_o_jogo_abre.py` lê do `/proc` do jogo as variáveis que decidem a entrada."""
    assert _DICA in _carregar_ensaio("quem_o_jogo_abre.py").VARS


def test_o_ensaio_do_giro_mede_com_a_dica_que_o_jogo_recebe() -> None:
    """Medir com outro valor é medir outro jogo — foi assim que o zero de 10/09 nasceu."""
    ensaio = _carregar_ensaio("o_jogo_para_de_ver_o_giro.py")
    o_jogo_recebe = compose_env(**_VARIANTES["dualsense_uhid"])[_DICA]
    o_ensaio_mede = ensaio.VALOR_QUE_O_JOGO_RECEBE
    assert ensaio.DICA_DO_ACELEROMETRO == _DICA
    assert o_ensaio_mede == o_jogo_recebe


def test_a_struct_da_enumeracao_poe_o_next_onde_a_biblioteca_o_poe() -> None:
    """O `next` do `SDL_hid_device_info` mora no deslocamento 72, na SDL2 e no SDL3."""
    if ctypes.sizeof(ctypes.c_void_p) != 8:
        pytest.skip("os deslocamentos medidos são os de 64 bits")
    ensaio = _carregar_ensaio("o_jogo_para_de_ver_o_giro.py")
    assert ensaio._InfoHid.next.offset == 72
    assert ensaio._InfoHid3.bus_type.offset == 68
    assert ensaio._InfoHid3.next.offset == 72


def test_o_so_medir_da_a_cada_biblioteca_um_ambiente_que_nao_abre_hidraw(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--so-medir` promete que biblioteca nenhuma abre `hidraw` nem nasce com tela."""
    for nome in ("DISPLAY", "WAYLAND_DISPLAY"):
        monkeypatch.setenv(nome, "de-mentira")
    monkeypatch.setenv("SDL_JOYSTICK_HIDAPI", "1")
    monkeypatch.delenv("SDL_HIDAPI_ENUMERATE_ONLY_CONTROLLERS", raising=False)
    ensaio = _carregar_ensaio("o_jogo_para_de_ver_o_giro.py")
    lib = tmp_path / "libSDL3.so.0"
    lib.write_bytes(b"")
    chamadas: dict[str, tuple[list[str], dict[str, str]]] = {}

    def _run(comando: list[str], *, env: dict[str, str], **_: Any) -> SimpleNamespace:
        papel = comando[comando.index("--processo") + 1]
        chamadas[papel] = (comando, env)
        carga: dict[str, Any] = {"hid": []}
        if papel == "controles":
            carga = {"versao": "0", "revisao": "", "controles": []}  # noqa-acento: chave de dado do ensaio
        return SimpleNamespace(returncode=0, stdout=json.dumps(carga), stderr="")

    monkeypatch.setattr(
        ensaio, "subprocess",
        SimpleNamespace(run=_run, TimeoutExpired=subprocess.TimeoutExpired),
    )
    medida = ensaio.medir_uma_biblioteca(
        lib, [], segundos=0.1, so_medir=True, dica=ensaio.VALOR_QUE_O_JOGO_RECEBE
    )
    assert "erro" not in medida, medida
    assert sorted(chamadas) == ["controles", "enumerar"]
    for papel, (comando, env) in chamadas.items():
        assert "--so-medir" in comando, f"o filho «{papel}» refaria o ambiente com HIDAPI"
        assert env.get("SDL_JOYSTICK_HIDAPI") == "0", papel
        assert env.get("SDL_HIDAPI_LIBUSB") == "0", papel
        assert not {"DISPLAY", "WAYLAND_DISPLAY"} & set(env), papel
        assert env.get(_DICA) == "0", papel
    assert chamadas["enumerar"][1].get(ensaio.FILTRO_SO_CONTROLES) == "0"
    assert ensaio.FILTRO_SO_CONTROLES not in chamadas["controles"][1]
