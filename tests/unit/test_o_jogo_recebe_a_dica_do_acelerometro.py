"""SENSORES-NO-JOGO-02: o jogo recebe `SDL_ACCELEROMETER_AS_JOYSTICK=0`, do daemon ao env(1).

O DEFEITO QUE A DICA CURA, medido em 13/09/2026
-----------------------------------------------
Sem HIDAPI, o giroscópio e o acelerômetro do vpad chegam ao jogo pelo evdev: o
SDL casa o nó «Motion Sensors» ao gamepad da mesma peça pelo `uniq`. A libSDL2
2.30.0 da Ubuntu (e o upstream a partir da 2.30.12) só casa esse nó quando o
udev dela o classifica como acelerômetro, e com a dica no padrão 1 ela o
classifica como joystick. Numa sonda só-leitura com o vpad vivo: sem a dica,
`HasSensor=False` e zero giros; com a dica em 0, `HasSensor=True` e 109 giros
distintos em 2 s. Nas bibliotecas dos runtimes da Steam a dica foi inócua.

A VARIÁVEL NOVA MORRE CALADA, e é por isso que esta régua atravessa os elos
---------------------------------------------------------------------------
O daemon materializa o arquivo; o wrapper `sh` o filtra por NOME. Esquecer um
dos dois lados deixa a dica fora do jogo sem erro nenhum — o risco que a
sprint escreveu em §R. Então a régua não confere só o dicionário: ela roda
`materialize_launch_env`, depois o `assets/hefesto-launch.sh` DE VERDADE contra
um socket de mentira, e lê a variável no processo que o wrapper embrulha.

O wrapper roda com um PATH mínimo: sem `system76-power`, `busctl` e
`dbus-send` o Game Mode dele não tem com quem falar, e a régua não mexe no
perfil de energia da máquina.

A MORDIDA, e as três formas de arrancar
---------------------------------------
* tire a linha `env["SDL_ACCELEROMETER_AS_JOYSTICK"] = "0"` de `compose_env` →
  as variantes e a travessia reprovam;
* tire o nome do `ENV_ALLOWLIST` → o espelho reprova (o `case` tem um nome que
  a allowlist não tem);
* tire o `case` do wrapper → o espelho e a travessia reprovam (o processo
  embrulhado lê «ausente»).
"""
from __future__ import annotations

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

#: Toda variante que `compose_env` distingue — os modos, as três máscaras, o
#: degradado, o co-op misto e a falta de cobertura. A dica não tem `if`.
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

    # AF_UNIX limita o caminho do socket a ~108 bytes: o tmp_path do pytest estoura.
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
    # O `@dataclass` do ensaio procura o próprio módulo em `sys.modules`.
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
