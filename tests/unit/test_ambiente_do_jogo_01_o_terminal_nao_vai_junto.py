"""AMBIENTE-DO-JOGO-01 — o interpretador do terminal não vai para a Steam nem para o jogo.

Medido em 17/09/2026 no `environ` do `PRAGMATA.exe`: uma Steam aberta de um
terminal passa a todo jogo a venv desse terminal, com o `bin/` dela na frente do
`PATH`. O `proton` é script Python, e quem o roda passa a ser o `python3` que o
terminal escolheu. O produto reabre a Steam de dentro do terminal da pessoa (o
install roda `steam_launch_options.py --stop-steam` e
`disable_steam_input.sh --apply`), e a devolvia assim.

A régua lê as TRÊS pontas contra a lista do dono, `ambiente_do_jogo`:

- as chamadas Python que fazem a Steam nascer (`reopen_steam`,
  `start_steam_game`, `stop_steam` e o `_spawn_steam` do botão PS);
- o gancho `assets/hefesto-launch.sh`, rodado de verdade, por onde todo jogo
  passa — é ele que cobre a Steam que a PESSOA abriu de um terminal;
- o `scripts/disable_steam_input.sh`, rodado de verdade, com uma Steam de
  mentira que só grava o ambiente que recebeu.

Nenhum teste daqui abre, fecha ou mata a Steam da máquina: os dublês ficam na
frente do `PATH`, e o `pkill` também é dublê.
"""
from __future__ import annotations

import ast
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import ambiente_do_jogo as adj
from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.integrations import steam_launcher
from tests.conftest import som_de_mentira

_RAIZ = Path(__file__).resolve().parents[2]
_WRAPPER = _RAIZ / "assets" / "hefesto-launch.sh"
_DISABLE = _RAIZ / "scripts" / "disable_steam_input.sh"
_SLO = Path(slo.__file__).resolve()

#: O que a Steam precisa para abrir e que a limpeza NÃO pode levar junto.
_DA_SESSAO = {
    "DISPLAY": ":0",
    "WAYLAND_DISPLAY": "wayland-1",
    "XDG_RUNTIME_DIR": "/run/user/1000",
    "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
}


def _terminal_sujo(base: Path) -> dict[str, str]:
    """A classe inteira do dono, com as pastas de verdade de cada prefixo.

    Monta-se a partir das listas do dono, e não de uma cópia digitada: uma
    variável nova no dono vira caso novo aqui sem ninguém lembrar.
    """
    env: dict[str, str] = {}
    for nome in adj.VARIAVEIS_DO_INTERPRETADOR:
        env[nome] = f"valor-de-{nome.lower()}"
    for nome in adj.PREFIXOS_COM_BIN_NO_PATH:
        pasta = base / nome.lower()
        (pasta / "bin").mkdir(parents=True, exist_ok=True)
        env[nome] = str(pasta)
    # PYTHONHOME aponta o interpretador da MÁQUINA: o `disable_steam_input.sh`
    # roda `python3` para a ponte, e um PYTHONHOME inventado o derrubaria antes
    # de chegar ao que se mede aqui.
    env["PYTHONHOME"] = sys.base_prefix
    return env


def _bins_sujos(env: dict[str, str]) -> list[str]:
    return [f"{env[nome]}/bin" for nome in adj.PREFIXOS_COM_BIN_NO_PATH]


def _sem_a_classe(env: dict[str, str]) -> list[str]:
    """O que sobrou da classe; vazio é o certo."""
    return [nome for nome in adj.VARIAVEIS_DO_INTERPRETADOR if nome in env]


# ---------------------------------------------------------------------------
# 1. O dono
# ---------------------------------------------------------------------------


class TestODono:
    def test_tira_a_classe_e_guarda_a_sessao(self, tmp_path: Path) -> None:
        sujo = {**_terminal_sujo(tmp_path), **_DA_SESSAO, "HOME": "/home/x"}
        limpo = adj.ambiente_limpo(sujo)
        assert _sem_a_classe(limpo) == []
        for nome, valor in {**_DA_SESSAO, "HOME": "/home/x"}.items():
            assert limpo[nome] == valor

    def test_tira_os_bins_e_guarda_o_resto_na_ordem(self, tmp_path: Path) -> None:
        sujo = _terminal_sujo(tmp_path)
        venv_bin, conda_bin = _bins_sujos(sujo)
        sujo["PATH"] = f"{venv_bin}:/usr/local/bin:{conda_bin}/:/usr/bin::/bin"
        assert adj.ambiente_limpo(sujo)["PATH"] == "/usr/local/bin:/usr/bin::/bin"

    def test_nao_muda_o_dicionario_de_quem_chama(self, tmp_path: Path) -> None:
        sujo = _terminal_sujo(tmp_path)
        sujo["PATH"] = f"{_bins_sujos(sujo)[0]}:/usr/bin"
        copia = dict(sujo)
        adj.ambiente_limpo(sujo)
        assert sujo == copia

    def test_sem_a_classe_devolve_o_mesmo_ambiente(self) -> None:
        env = {**_DA_SESSAO, "PATH": "/usr/bin:/bin", "HOME": "/home/x"}
        assert adj.ambiente_limpo(env) == env

    def test_prefixo_raiz_nao_leva_o_bin_da_maquina(self) -> None:
        env = {"VIRTUAL_ENV": "/", "PATH": "/usr/bin:/bin"}
        assert adj.ambiente_limpo(env)["PATH"] == "/usr/bin:/bin"

    def test_path_que_ficaria_vazio_fica_como_veio(self) -> None:
        env = {"VIRTUAL_ENV": "/opt/v", "PATH": "/opt/v/bin"}
        limpo = adj.ambiente_limpo(env)
        assert limpo["PATH"] == "/opt/v/bin"
        assert "VIRTUAL_ENV" not in limpo


# ---------------------------------------------------------------------------
# 2. A ponta Python: quem faz a Steam nascer
# ---------------------------------------------------------------------------


@pytest.fixture()
def terminal_sujo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, str]:
    """O `os.environ` deste processo vira o de um terminal com venv e conda."""
    sujo = _terminal_sujo(tmp_path)
    for nome, valor in {**sujo, **_DA_SESSAO}.items():
        monkeypatch.setenv(nome, valor)
    monkeypatch.setenv("PATH", ":".join([*_bins_sujos(sujo), "/usr/bin", "/bin"]))
    return sujo


@pytest.fixture()
def popen_de_mentira(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """`subprocess` e `shutil` do módulo trocados por dublês que só anotam.

    Troca-se o NOME dentro do módulo, e não o `subprocess` global: o `run` de
    mentira explode, e nenhum `pkill` real sai daqui.
    """
    chamadas: list[dict[str, Any]] = []

    def _popen(cmd: list[str], **kwargs: Any) -> object:
        chamadas.append({"cmd": list(cmd), **kwargs})
        return object()

    def _run(*_a: Any, **_k: Any) -> object:
        raise AssertionError("o teste não pode chegar ao pkill")

    monkeypatch.setattr(
        slo,
        "subprocess",
        SimpleNamespace(
            Popen=_popen,
            run=_run,
            DEVNULL=subprocess.DEVNULL,
            SubprocessError=subprocess.SubprocessError,
        ),
    )
    monkeypatch.setattr(slo, "shutil", SimpleNamespace(which=lambda n: f"/usr/bin/{n}"))
    return chamadas


def _confere_limpo(env: dict[str, str], sujo: dict[str, str]) -> None:
    assert _sem_a_classe(env) == [], "a Steam nasceria com o interpretador do terminal"
    for bin_sujo in _bins_sujos(sujo):
        assert bin_sujo not in env["PATH"].split(":"), env["PATH"]
    for nome, valor in _DA_SESSAO.items():
        assert env[nome] == valor, f"{nome} é da sessão e a Steam precisa dele"


class TestAPontaPython:
    def test_reopen_steam(
        self, terminal_sujo: dict[str, str], popen_de_mentira: list[dict[str, Any]]
    ) -> None:
        assert slo.reopen_steam() is True
        assert popen_de_mentira[0]["cmd"] == ["steam"]
        _confere_limpo(popen_de_mentira[0]["env"], terminal_sujo)

    def test_start_steam_game(
        self, terminal_sujo: dict[str, str], popen_de_mentira: list[dict[str, Any]]
    ) -> None:
        assert slo.start_steam_game(1599660) is True
        assert popen_de_mentira[0]["cmd"] == ["steam", "steam://rungameid/1599660"]
        _confere_limpo(popen_de_mentira[0]["env"], terminal_sujo)

    def test_stop_steam(
        self,
        terminal_sujo: dict[str, str],
        popen_de_mentira: list[dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        respostas = iter([True, False, False, False])
        monkeypatch.setattr(slo, "steam_running", lambda: next(respostas))
        monkeypatch.setattr(slo, "time", SimpleNamespace(sleep=lambda _s: None))
        assert slo.stop_steam() is True
        assert popen_de_mentira[0]["cmd"] == ["steam", "-shutdown"]
        _confere_limpo(popen_de_mentira[0]["env"], terminal_sujo)

    def test_o_botao_ps_do_daemon(self, terminal_sujo: dict[str, str]) -> None:
        chamadas: list[dict[str, Any]] = []

        def _popen(cmd: list[str], **kwargs: Any) -> object:
            chamadas.append({"cmd": list(cmd), **kwargs})
            return object()

        assert steam_launcher._spawn_steam(popen_runner=_popen) is True
        assert chamadas[0]["cmd"] == ["steam"]
        _confere_limpo(chamadas[0]["env"], terminal_sujo)

    def test_todo_popen_do_modulo_da_steam_passa_pelo_dono(self) -> None:
        """Um `Popen` novo em `steam_launch_options.py` sem o dono reprova aqui."""
        arvore = ast.parse(_SLO.read_text(encoding="utf-8"))
        popens = [
            no
            for no in ast.walk(arvore)
            if isinstance(no, ast.Call)
            and isinstance(no.func, ast.Attribute)
            and no.func.attr == "Popen"
        ]
        assert popens, "a régua não achou Popen nenhum: ela mede o arquivo certo?"
        sem_dono = [
            no.lineno
            for no in popens
            if not any(
                kw.arg == "env"
                and isinstance(kw.value, ast.Call)
                and isinstance(kw.value.func, ast.Name)
                and kw.value.func.id == "ambiente_limpo"
                for kw in no.keywords
            )
        ]
        assert sem_dono == [], f"Popen sem env=ambiente_limpo(...) nas linhas {sem_dono}"

    def test_o_modulo_avulso_acha_o_dono(self, tmp_path: Path) -> None:
        """O install roda `steam_launch_options.py` como SCRIPT, com o python3
        do sistema e sem o pacote: o dono tem de chegar pelo irmão."""
        proc = subprocess.run(
            [sys.executable, "-S", "-E", str(_SLO), "--help"],
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
            cwd=str(tmp_path),
            timeout=60,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        assert "Error" not in proc.stderr, proc.stderr


# ---------------------------------------------------------------------------
# 3. As pontas em shell
# ---------------------------------------------------------------------------


def _corpo_da_funcao(caminho: Path) -> str:
    texto = caminho.read_text(encoding="utf-8")
    achado = re.search(
        r"^limpar_ambiente_do_interpretador\(\) \{\n(.*?)^\}\n",
        texto,
        re.MULTILINE | re.DOTALL,
    )
    assert achado, f"{caminho.name} perdeu limpar_ambiente_do_interpretador"
    return achado.group(1)


class TestAListaDasPontasEmShell:
    @pytest.mark.parametrize("caminho", [_WRAPPER, _DISABLE], ids=lambda p: p.name)
    def test_o_unset_e_a_lista_do_dono(self, caminho: Path) -> None:
        linhas = [
            linha.split()[1:]
            for linha in _corpo_da_funcao(caminho).splitlines()
            if linha.strip().startswith("unset ")
        ]
        assert len(linhas) == 1, linhas
        assert sorted(linhas[0]) == sorted(adj.VARIAVEIS_DO_INTERPRETADOR)

    @pytest.mark.parametrize("caminho", [_WRAPPER, _DISABLE], ids=lambda p: p.name)
    def test_os_prefixos_sao_os_do_dono(self, caminho: Path) -> None:
        lidos = re.findall(r'la_base="\$\{([A-Z_]+):-\}"', _corpo_da_funcao(caminho))
        assert sorted(lidos) == sorted(adj.PREFIXOS_COM_BIN_NO_PATH)

    def test_as_duas_copias_em_shell_sao_a_mesma(self) -> None:
        assert _corpo_da_funcao(_WRAPPER) == _corpo_da_funcao(_DISABLE)


def _dubles(pasta: Path, corpos: dict[str, str]) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    for nome, corpo in corpos.items():
        caminho = pasta / nome
        caminho.write_text(f"#!/bin/sh\n{corpo}\n", encoding="utf-8")
        caminho.chmod(0o755)


def _path_sem_o_som_da_suite(caminho: str) -> str:
    """O PATH que o processo recebeu, sem o diretório que a `conftest` põe na
    frente dos de sistema para a suíte não falar com o servidor de som."""
    duble = som_de_mentira()
    return ":".join(e for e in caminho.split(":") if duble is None or e != str(duble))


def _le_env(texto: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for linha in texto.splitlines():
        nome, sep, valor = linha.partition("=")
        if sep:
            env[nome] = valor
    return env


class TestOGanchoDoJogo:
    """O `hefesto-launch` de verdade, com `env` no lugar do jogo."""

    def _roda(self, tmp_path: Path, *jogo: str) -> tuple[dict[str, str], dict[str, str]]:
        sujo = _terminal_sujo(tmp_path)
        mudos = tmp_path / "mudos"
        # O Game Mode do gancho fala com o daemon de energia: dublês mudos na
        # frente do PATH, como em `test_hefesto_launch_wrapper.py`.
        _dubles(mudos, {n: "exit 1" for n in ("system76-power", "busctl", "dbus-send")})
        runtime = tmp_path / "run"
        runtime.mkdir()
        env = {
            **sujo,
            **_DA_SESSAO,
            "XDG_RUNTIME_DIR": str(runtime),  # sem socket: nenhuma env nossa
            "XDG_STATE_HOME": str(tmp_path / "state"),
            "HOME": str(tmp_path),
            "HEFESTO_SYSFS": str(tmp_path / "sysfs"),
            "SteamAppId": "1599660",
            "PATH": ":".join([str(mudos), *_bins_sujos(sujo), "/usr/bin", "/bin"]),
        }
        proc = subprocess.run(
            ["sh", str(_WRAPPER), *jogo],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        return _le_env(proc.stdout), sujo

    def test_o_jogo_nasce_sem_o_interpretador_do_terminal(self, tmp_path: Path) -> None:
        jogo, sujo = self._roda(tmp_path, "env")
        assert _sem_a_classe(jogo) == []
        for bin_sujo in _bins_sujos(sujo):
            assert bin_sujo not in jogo["PATH"].split(":")
        assert _path_sem_o_som_da_suite(jogo["PATH"]) == f"{tmp_path / 'mudos'}:/usr/bin:/bin"
        for nome in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS"):
            assert jogo[nome] == _DA_SESSAO[nome]
        assert jogo["SteamAppId"] == "1599660"

    def test_o_que_ela_escreve_na_opcao_de_inicializacao_sobrevive(
        self, tmp_path: Path
    ) -> None:
        """A Opção de Inicialização vem em "$@", DEPOIS da limpeza."""
        jogo, _ = self._roda(tmp_path, "PYTHONPATH=/escolha/dela", "env")
        assert jogo["PYTHONPATH"] == "/escolha/dela"
        assert "VIRTUAL_ENV" not in jogo


class TestOInstallReabreASteamLimpa:
    """O `disable_steam_input.sh --apply` de verdade, como o install o roda."""

    _VDF = (
        '"UserLocalConfigStore"\n{\n\t"system"\n\t{\n'
        '\t\t"SteamController_PSSupport"\t\t"2"\n'
        '\t\t"SteamController_SwitchSupport"\t\t"2"\n'
        "\t}\n}\n"
    )

    def test_a_steam_fecha_e_reabre_sem_o_terminal(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        vdf = home / ".steam" / "steam" / "userdata" / "1234" / "config" / "localconfig.vdf"
        vdf.parent.mkdir(parents=True)
        vdf.write_text(self._VDF, encoding="utf-8")
        estado = tmp_path / "estado"
        estado.mkdir()
        dubles = tmp_path / "dubles"
        dorme = shutil.which("sleep", path="/usr/bin:/bin") or "/bin/sleep"
        _dubles(
            dubles,
            {
                # Steam "aberta" até o -shutdown; jogo nenhum aberto.
                "pgrep": (
                    'case "$*" in *SteamLaunch*) exit 1 ;; esac\n'
                    '[ -f "$FAKE_STATE/steam_down" ] && exit 1\n'
                    "exit 0"
                ),
                "steam": (
                    'case "$1" in\n'
                    '  -shutdown) env > "$FAKE_STATE/env_do_shutdown"\n'
                    '             touch "$FAKE_STATE/steam_down" ;;\n'
                    '  *) env > "$FAKE_STATE/reabertura.tmp"\n'
                    '     mv "$FAKE_STATE/reabertura.tmp" "$FAKE_STATE/env_da_reabertura" ;;\n'
                    "esac"
                ),
                # O pkill é dublê: se a espera perder a corrida, a régua
                # reprova em vez de matar a Steam de alguém.
                "pkill": 'printf "%s\\n" "$*" >> "$FAKE_STATE/pkill"; exit 0',
                "sleep": f"exec {dorme} 0.05",
            },
        )
        sujo = _terminal_sujo(tmp_path)
        env = {
            **sujo,
            **_DA_SESSAO,
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "FAKE_STATE": str(estado),
            "PATH": ":".join([str(dubles), *_bins_sujos(sujo), "/usr/bin", "/bin"]),
        }
        proc = subprocess.run(
            [shutil.which("bash") or "/bin/bash", str(_DISABLE), "--apply"],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "resultado=aplicado" in proc.stdout, proc.stdout
        assert "reabrindo Steam" in proc.stdout, proc.stdout
        assert not (estado / "pkill").exists()

        # A reabertura é desanexada (`setsid nohup steam &`): espera curta pelo
        # arquivo que o dublê grava por último.
        reabertura = estado / "env_da_reabertura"
        prazo = time.monotonic() + 10
        while not reabertura.exists() and time.monotonic() < prazo:
            time.sleep(0.05)
        assert reabertura.exists(), "a Steam de mentira não foi reaberta"

        for arquivo in ("env_do_shutdown", "env_da_reabertura"):
            steam = _le_env((estado / arquivo).read_text(encoding="utf-8"))
            assert _sem_a_classe(steam) == [], arquivo
            assert _path_sem_o_som_da_suite(steam["PATH"]) == f"{dubles}:/usr/bin:/bin", arquivo
            assert steam["DISPLAY"] == _DA_SESSAO["DISPLAY"], arquivo
