"""AMBIENTE-DO-JOGO-01 — o interpretador do terminal não vai para a Steam nem para o jogo."""
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
from tests.conftest import lancador_de_mentira, som_de_mentira

_RAIZ = Path(__file__).resolve().parents[2]
_WRAPPER = _RAIZ / "assets" / "hefesto-launch.sh"
_DISABLE = _RAIZ / "scripts" / "disable_steam_input.sh"
_SLO = Path(slo.__file__).resolve()
_LAUNCHER = Path(steam_launcher.__file__).resolve()
_PACOTE = _RAIZ / "src" / "hefesto_dualsense4unix"
_REPOSICAO = _PACOTE / "integrations" / "reposicao_dos_lancadores.py"
_HOTKEY = _PACOTE / "daemon" / "subsystems" / "hotkey.py"

_FUNCOES_EM_SHELL = ("podar_bins_do_interpretador", "limpar_ambiente_do_interpretador")

_LISTAS_DE_BUSCA_DA_STEAM = ("PATH", "SYSTEM_PATH")


def _da_sessao(base: Path) -> dict[str, str]:
    """O que a Steam precisa para abrir e que a limpeza NÃO pode levar junto."""
    runtime = base / "run"
    runtime.mkdir(parents=True, exist_ok=True)
    return {
        "DISPLAY": ":987",
        "WAYLAND_DISPLAY": "wayland-de-mentira",
        "XDG_RUNTIME_DIR": str(runtime),
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={runtime / 'bus'}",
    }


def _terminal_sujo(base: Path) -> dict[str, str]:
    """A classe inteira do dono, com as pastas de verdade de cada prefixo."""
    env: dict[str, str] = {}
    for nome in adj.VARIAVEIS_DO_INTERPRETADOR:
        env[nome] = f"valor-de-{nome.lower()}"
    for nome in adj.PREFIXOS_COM_BIN_NO_PATH:
        pasta = base / nome.lower()
        (pasta / "bin").mkdir(parents=True, exist_ok=True)
        env[nome] = str(pasta)
    env["PYTHONHOME"] = sys.base_prefix
    return env


def _bins_sujos(env: dict[str, str]) -> list[str]:
    return [f"{env[nome]}/bin" for nome in adj.PREFIXOS_COM_BIN_NO_PATH]


def _busca_suja(sujo: dict[str, str], *antes: str) -> dict[str, str]:
    """As listas de busca de um terminal ativado: os `bin/` dele na frente."""
    caminho = ":".join([*antes, *_bins_sujos(sujo), "/usr/bin", "/bin"])
    return {nome: caminho for nome in _LISTAS_DE_BUSCA_DA_STEAM}


def _sem_a_classe(env: dict[str, str]) -> list[str]:
    """O que sobrou da classe; vazio é o certo."""
    return [nome for nome in adj.VARIAVEIS_DO_INTERPRETADOR if nome in env]


class TestODono:
    def test_tira_a_classe_e_guarda_a_sessao(self, tmp_path: Path) -> None:
        sessao = _da_sessao(tmp_path)
        sujo = {**_terminal_sujo(tmp_path), **sessao, "HOME": "/home/x"}
        limpo = adj.ambiente_limpo(sujo)
        assert _sem_a_classe(limpo) == []
        for nome, valor in {**sessao, "HOME": "/home/x"}.items():
            assert limpo[nome] == valor

    def test_tira_os_bins_e_guarda_o_resto_na_ordem(self, tmp_path: Path) -> None:
        sujo = _terminal_sujo(tmp_path)
        venv_bin, conda_bin = _bins_sujos(sujo)
        sujo["PATH"] = f"{venv_bin}:/usr/local/bin:{conda_bin}/:/usr/bin::/bin"
        assert adj.ambiente_limpo(sujo)["PATH"] == "/usr/local/bin:/usr/bin::/bin"

    def test_o_system_path_da_steam_tambem_sai_podado(self, tmp_path: Path) -> None:
        """O portador medido no PRAGMATA: a Steam Linux Runtime devolve o"""
        sujo = _terminal_sujo(tmp_path)
        venv_bin, conda_bin = _bins_sujos(sujo)
        sujo["PATH"] = "/usr/bin:/bin"
        sujo["SYSTEM_PATH"] = f"{conda_bin}:{venv_bin}/:/usr/bin:/bin"
        limpo = adj.ambiente_limpo(sujo)
        assert limpo["SYSTEM_PATH"] == "/usr/bin:/bin"
        assert limpo["PATH"] == "/usr/bin:/bin"

    def test_sem_system_path_nao_inventa_um(self, tmp_path: Path) -> None:
        sujo = _terminal_sujo(tmp_path)
        sujo["PATH"] = f"{_bins_sujos(sujo)[0]}:/usr/bin"
        assert "SYSTEM_PATH" not in adj.ambiente_limpo(sujo)

    def test_nao_muda_o_dicionario_de_quem_chama(self, tmp_path: Path) -> None:
        sujo = {**_terminal_sujo(tmp_path)}
        sujo.update(_busca_suja(sujo))
        copia = dict(sujo)
        adj.ambiente_limpo(sujo)
        assert sujo == copia

    def test_sem_a_classe_devolve_o_mesmo_ambiente(self, tmp_path: Path) -> None:
        env = {
            **_da_sessao(tmp_path),
            "PATH": "/usr/bin:/bin",
            "SYSTEM_PATH": "/usr/bin:/bin",
            "HOME": "/home/x",
        }
        assert adj.ambiente_limpo(env) == env

    def test_prefixo_raiz_nao_leva_o_bin_da_maquina(self) -> None:
        env = {"VIRTUAL_ENV": "/", "PATH": "/usr/bin:/bin", "SYSTEM_PATH": "/bin"}
        limpo = adj.ambiente_limpo(env)
        assert limpo["PATH"] == "/usr/bin:/bin"
        assert limpo["SYSTEM_PATH"] == "/bin"

    def test_lista_que_ficaria_vazia_fica_como_veio(self) -> None:
        env = {"VIRTUAL_ENV": "/opt/v", "PATH": "/opt/v/bin", "SYSTEM_PATH": "/opt/v/bin/"}
        limpo = adj.ambiente_limpo(env)
        assert limpo["PATH"] == "/opt/v/bin"
        assert limpo["SYSTEM_PATH"] == "/opt/v/bin/"
        assert "VIRTUAL_ENV" not in limpo


@pytest.fixture()
def sessao(tmp_path: Path) -> dict[str, str]:
    return _da_sessao(tmp_path)


@pytest.fixture()
def terminal_sujo(
    tmp_path: Path, sessao: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> dict[str, str]:
    """O `os.environ` deste processo vira o de um terminal com venv e conda."""
    sujo = _terminal_sujo(tmp_path)
    for nome, valor in {**sujo, **sessao, **_busca_suja(sujo)}.items():
        monkeypatch.setenv(nome, valor)
    return sujo


@pytest.fixture()
def popen_de_mentira(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """`subprocess` e `shutil` do módulo trocados por dublês que só anotam."""
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


def _confere_limpo(
    env: dict[str, str], sujo: dict[str, str], sessao: dict[str, str]
) -> None:
    assert _sem_a_classe(env) == [], "a Steam nasceria com o interpretador do terminal"
    for nome in _LISTAS_DE_BUSCA_DA_STEAM:
        for bin_sujo in _bins_sujos(sujo):
            assert bin_sujo not in env[nome].split(":"), (nome, env[nome])
    for nome, valor in sessao.items():
        assert env[nome] == valor, f"{nome} é da sessão e a Steam precisa dele"


class TestAPontaPython:
    def test_reopen_steam(
        self,
        terminal_sujo: dict[str, str],
        sessao: dict[str, str],
        popen_de_mentira: list[dict[str, Any]],
    ) -> None:
        assert slo.reopen_steam() is True
        assert popen_de_mentira[0]["cmd"] == ["steam"]
        _confere_limpo(popen_de_mentira[0]["env"], terminal_sujo, sessao)


    def test_stop_steam(
        self,
        terminal_sujo: dict[str, str],
        sessao: dict[str, str],
        popen_de_mentira: list[dict[str, Any]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        respostas = iter([True, False, False, False])
        monkeypatch.setattr(slo, "steam_running", lambda: next(respostas))
        monkeypatch.setattr(slo, "time", SimpleNamespace(sleep=lambda _s: None))
        assert slo.stop_steam() is True
        assert popen_de_mentira[0]["cmd"] == ["steam", "-shutdown"]
        _confere_limpo(popen_de_mentira[0]["env"], terminal_sujo, sessao)

    def test_o_botao_ps_do_daemon(
        self, terminal_sujo: dict[str, str], sessao: dict[str, str]
    ) -> None:
        chamadas: list[dict[str, Any]] = []

        def _popen(cmd: list[str], **kwargs: Any) -> object:
            chamadas.append({"cmd": list(cmd), **kwargs})
            return object()

        assert steam_launcher._spawn_steam(popen_runner=_popen) is True
        assert chamadas[0]["cmd"] == ["steam"]
        _confere_limpo(chamadas[0]["env"], terminal_sujo, sessao)

    @pytest.mark.parametrize(
        "arquivo", [_SLO, _LAUNCHER, _REPOSICAO, _HOTKEY], ids=lambda p: p.name
    )
    def test_toda_steam_que_nasce_do_modulo_passa_pelo_dono(self, arquivo: Path) -> None:
        """Um `Popen` novo, ou uma chamada nova com a Steam no argv, sem"""
        chamadas = _quem_abre_processo(ast.parse(arquivo.read_text(encoding="utf-8")))
        assert chamadas, f"a régua não achou chamada nenhuma em {arquivo.name}"
        sem_dono = [no.lineno for no in chamadas if not _env_pelo_dono(no)]
        assert sem_dono == [], (
            f"{arquivo.name}: sem env=ambiente_limpo(os.environ) nas linhas {sem_dono}"
        )

    def test_o_modulo_avulso_acha_o_dono(self, tmp_path: Path) -> None:
        """O install roda `steam_launch_options.py` como SCRIPT, com o python3"""
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


def _e_os_environ(no: ast.expr) -> bool:
    return (
        isinstance(no, ast.Attribute)
        and isinstance(no.value, ast.Name)
        and no.value.id == "os"
        and no.attr == "environ"
    )


def _env_pelo_dono(chamada: ast.Call) -> bool:
    """`env=ambiente_limpo(os.environ)`, e nenhum outro argumento."""
    for kw in chamada.keywords:
        if kw.arg == "env":
            valor = kw.value
            return (
                isinstance(valor, ast.Call)
                and isinstance(valor.func, ast.Name)
                and valor.func.id == "ambiente_limpo"
                and len(valor.args) == 1
                and not valor.keywords
                and _e_os_environ(valor.args[0])
            )
    return False


def _argv_da_steam(chamada: ast.Call) -> bool:
    """O primeiro argumento é uma linha de comando que começa pela Steam."""
    if not chamada.args:
        return False
    argv = chamada.args[0]
    if not isinstance(argv, (ast.List, ast.Tuple)) or not argv.elts:
        return False
    primeiro = argv.elts[0]
    return (isinstance(primeiro, ast.Constant) and primeiro.value == "steam") or (
        isinstance(primeiro, ast.Name) and primeiro.id == "STEAM_BINARY"
    )


def _so_repassa(chamada: ast.Call) -> bool:
    """`Popen(cmd, **kwargs)` sem `env` próprio: quem decide é quem chamou."""
    nomes = [kw.arg for kw in chamada.keywords]
    return None in nomes and "env" not in nomes


def _pelo_dono_de_abrir(chamada: ast.Call) -> bool:
    """`fora_do_servico.abrir(...)` — STEAM-FORA-DO-SERVICO-01, 26/09/2026."""
    return (
        isinstance(chamada.func, ast.Attribute)
        and chamada.func.attr == "abrir"
        and isinstance(chamada.func.value, ast.Name)
        and chamada.func.value.id == "fora_do_servico"
    )


def _quem_abre_processo(arvore: ast.AST) -> list[ast.Call]:
    return [
        no
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call)
        and (
            (
                isinstance(no.func, ast.Attribute)
                and no.func.attr == "Popen"
                and not _so_repassa(no)
            )
            or _argv_da_steam(no)
            or _pelo_dono_de_abrir(no)
        )
    ]


def _funcao(caminho: Path, nome: str) -> str:
    """A definição inteira de `nome` em `caminho`, da assinatura à chave final."""
    texto = caminho.read_text(encoding="utf-8")
    achado = re.search(
        rf"^{nome}\(\) \{{\n.*?^\}}\n",
        texto,
        re.MULTILINE | re.DOTALL,
    )
    assert achado, f"{caminho.name} perdeu {nome}"
    return achado.group(0)


def _funcoes(caminho: Path) -> str:
    return "\n".join(_funcao(caminho, nome) for nome in _FUNCOES_EM_SHELL)


_PONTAS_EM_SHELL = [_WRAPPER, _DISABLE]


class TestAListaDasPontasEmShell:
    @pytest.mark.parametrize("caminho", _PONTAS_EM_SHELL, ids=lambda p: p.name)
    def test_o_unset_e_a_lista_do_dono(self, caminho: Path) -> None:
        linhas = [
            linha.split()[1:]
            for linha in _funcao(caminho, "limpar_ambiente_do_interpretador").splitlines()
            if linha.strip().startswith("unset ")
        ]
        assert len(linhas) == 1, linhas
        assert sorted(linhas[0]) == sorted(adj.VARIAVEIS_DO_INTERPRETADOR)

    @pytest.mark.parametrize("caminho", _PONTAS_EM_SHELL, ids=lambda p: p.name)
    def test_os_prefixos_sao_os_do_dono(self, caminho: Path) -> None:
        corpo = _funcao(caminho, "limpar_ambiente_do_interpretador")
        lidos = re.findall(r'la_base="\$\{([A-Z_]+):-\}"', corpo)
        assert sorted(lidos) == sorted(adj.PREFIXOS_COM_BIN_NO_PATH)

    @pytest.mark.parametrize("caminho", _PONTAS_EM_SHELL, ids=lambda p: p.name)
    def test_as_listas_podadas_sao_as_do_dono(self, caminho: Path) -> None:
        """O `SYSTEM_PATH` entra aqui: sem ele o jogo Proton volta a achar o"""
        corpo = _funcao(caminho, "limpar_ambiente_do_interpretador")
        lidas = re.findall(r'podar_bins_do_interpretador "\$\{([A-Z_]+):-\}"', corpo)
        gravadas = re.findall(r'&& (?:export )?([A-Z_]+)="\$la_novo"', corpo)
        assert sorted(lidas) == sorted(adj.VARIAVEIS_DE_BUSCA)
        assert sorted(gravadas) == sorted(adj.VARIAVEIS_DE_BUSCA)

    def test_as_duas_copias_em_shell_sao_a_mesma(self) -> None:
        assert _funcoes(_WRAPPER) == _funcoes(_DISABLE)


_CASOS_DE_BORDA: dict[str, dict[str, str]] = {
    "a-classe-inteira": {
        **{nome: f"valor-de-{nome.lower()}" for nome in adj.VARIAVEIS_DO_INTERPRETADOR},
        "VIRTUAL_ENV": "/opt/venv",
        "CONDA_PREFIX": "/opt/conda/",
        "PATH": "/opt/venv/bin:/usr/local/bin:/opt/conda/bin/:/usr/bin::/bin",
        "SYSTEM_PATH": "/opt/conda/bin:/opt/venv/bin/:/usr/bin:/bin",
    },
    "prefixo-raiz": {"VIRTUAL_ENV": "/", "PATH": "/usr/bin:/bin", "SYSTEM_PATH": "/bin"},
    "prefixo-com-barra-final": {
        "VIRTUAL_ENV": "/opt/v/",
        "PATH": "/opt/v/bin:/usr/bin",
        "SYSTEM_PATH": "/usr/bin:/opt/v/bin/",
    },
    "prefixo-com-barra-dupla": {
        "VIRTUAL_ENV": "/opt/v//",
        "PATH": "/opt/v//bin:/opt/v/bin:/usr/bin",
    },
    "so-o-bin-do-venv": {
        "VIRTUAL_ENV": "/opt/v",
        "PATH": "/opt/v/bin",
        "SYSTEM_PATH": "/opt/v/bin/",
    },
    "entradas-vazias": {
        "VIRTUAL_ENV": "/opt/v",
        "PATH": ":/opt/v/bin::/usr/bin:",
        "SYSTEM_PATH": "::/opt/v/bin",
    },
    "so-vazias-depois-da-poda": {
        "VIRTUAL_ENV": "/opt/v",
        "PATH": "/opt/v/bin:",
        "SYSTEM_PATH": "/opt/v/bin::",
    },
    "sem-system-path": {"CONDA_PREFIX": "/opt/c", "PATH": "/opt/c/bin:/usr/bin"},
    "system-path-vazio": {"VIRTUAL_ENV": "/opt/v", "PATH": "/usr/bin", "SYSTEM_PATH": ""},
    "sem-a-classe": {"PATH": "/opt/v/bin:/usr/bin", "SYSTEM_PATH": "/opt/v/bin"},
    "prefixo-vazio": {"VIRTUAL_ENV": "", "PATH": "/bin:/usr/bin", "SYSTEM_PATH": "/bin"},
    "espaco-e-curinga": {
        "VIRTUAL_ENV": "/opt/meu env",
        "PATH": "/opt/meu env/bin:/tmp/[a]*:/usr/bin",
        "SYSTEM_PATH": "/tmp/*:/opt/meu env/bin",
    },
    "venv-e-conda-na-mesma-pasta": {
        "VIRTUAL_ENV": "/opt/x",
        "CONDA_PREFIX": "/opt/x/",
        "PATH": "/opt/x/bin:/usr/bin",
        "SYSTEM_PATH": "/usr/bin:/opt/x/bin",
    },
}

_DIVISA = "--hefesto-antes-e-depois--"


def _shell_da_ponta(caminho: Path) -> list[str]:
    """O gancho roda sob `sh` (a Steam o chama pelo shebang); o roteiro, sob"""
    nome, opcoes = ("sh", []) if caminho == _WRAPPER else ("bash", ["-u"])
    achado = shutil.which(nome, path="/usr/bin:/bin")
    assert achado, f"sem {nome} na máquina"
    return [achado, *opcoes]


class TestAPontaEmShellSegueODono:
    """O dono Python é o oráculo das duas cópias em shell, caso a caso."""

    @pytest.mark.parametrize("caso", sorted(_CASOS_DE_BORDA))
    @pytest.mark.parametrize("caminho", _PONTAS_EM_SHELL, ids=lambda p: p.name)
    def test_a_borda_e_a_do_dono(self, caminho: Path, caso: str, tmp_path: Path) -> None:
        env_bin = shutil.which("env", path="/usr/bin:/bin")
        assert env_bin, "sem env(1) na máquina"
        roteiro = (
            _funcoes(caminho)
            + f'\n"$1"\nprintf "%s\\n" "{_DIVISA}"\n'
            + 'limpar_ambiente_do_interpretador\nexec "$1"\n'
        )
        proc = subprocess.run(
            [*_shell_da_ponta(caminho), "-c", roteiro, "ponta", env_bin],
            env=_CASOS_DE_BORDA[caso],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        antes, sep, depois = proc.stdout.partition(f"{_DIVISA}\n")
        assert sep, proc.stdout
        esperado = adj.ambiente_limpo(_le_env(antes))
        obtido = _le_env(depois)
        nomes = {
            *adj.VARIAVEIS_DO_INTERPRETADOR,
            *adj.VARIAVEIS_DE_BUSCA,
            *_LISTAS_DE_BUSCA_DA_STEAM,
        }
        assert {n: obtido.get(n) for n in nomes} == {n: esperado.get(n) for n in nomes}


def _dubles(pasta: Path, corpos: dict[str, str]) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    for nome, corpo in corpos.items():
        caminho = pasta / nome
        caminho.write_text(f"#!/bin/sh\n{corpo}\n", encoding="utf-8")
        caminho.chmod(0o755)


def _path_sem_o_som_da_suite(caminho: str) -> str:
    """O PATH que o processo recebeu, sem os diretórios que a `conftest` põe na"""
    da_suite = {str(d) for d in (som_de_mentira(), lancador_de_mentira()) if d is not None}
    return ":".join(e for e in caminho.split(":") if e not in da_suite)


def _le_env(texto: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for linha in texto.splitlines():
        nome, sep, valor = linha.partition("=")
        if sep:
            env[nome] = valor
    return env


_A_STEAM_LINUX_RUNTIME = (
    'if [ -n "${SYSTEM_PATH+set}" ]; then export PATH="$SYSTEM_PATH"; fi; exec env'
)


class TestOGanchoDoJogo:
    """O `hefesto-launch` de verdade, com `env` no lugar do jogo."""

    def _roda(self, tmp_path: Path, *jogo: str) -> tuple[dict[str, str], dict[str, str]]:
        sujo = _terminal_sujo(tmp_path)
        mudos = tmp_path / "mudos"
        _dubles(mudos, {n: "exit 1" for n in ("system76-power", "busctl", "dbus-send")})
        env = {
            **sujo,
            **_da_sessao(tmp_path),
            "XDG_STATE_HOME": str(tmp_path / "state"),
            "HOME": str(tmp_path),
            "HEFESTO_SYSFS": str(tmp_path / "sysfs"),
            "SteamAppId": "1599660",
            **_busca_suja(sujo, str(mudos)),
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
        limpo = f"{tmp_path / 'mudos'}:/usr/bin:/bin"
        for nome in _LISTAS_DE_BUSCA_DA_STEAM:
            for bin_sujo in _bins_sujos(sujo):
                assert bin_sujo not in jogo[nome].split(":"), (nome, jogo[nome])
            assert _path_sem_o_som_da_suite(jogo[nome]) == limpo, nome
        sessao = _da_sessao(tmp_path)
        for nome in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS"):
            assert jogo[nome] == sessao[nome]
        assert jogo["SteamAppId"] == "1599660"

    def test_o_proton_nao_acha_o_python_do_terminal_depois_da_runtime(
        self, tmp_path: Path
    ) -> None:
        """O caminho inteiro de um jogo Proton: o gancho e, DEPOIS dele, a"""
        proton, sujo = self._roda(tmp_path, "sh", "-c", _A_STEAM_LINUX_RUNTIME)
        for bin_sujo in _bins_sujos(sujo):
            assert bin_sujo not in proton["PATH"].split(":"), proton["PATH"]
        assert proton["PATH"] == f"{tmp_path / 'mudos'}:/usr/bin:/bin"

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
                "pkill": 'printf "%s\\n" "$*" >> "$FAKE_STATE/pkill"; exit 0',
                "sleep": f"exec {dorme} 0.05",
            },
        )
        sujo = _terminal_sujo(tmp_path)
        sessao = _da_sessao(tmp_path)
        env = {
            **sujo,
            **sessao,
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "FAKE_STATE": str(estado),
            **_busca_suja(sujo, str(dubles)),
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

        reabertura = estado / "env_da_reabertura"
        prazo = time.monotonic() + 10
        while not reabertura.exists() and time.monotonic() < prazo:
            time.sleep(0.05)
        assert reabertura.exists(), "a Steam de mentira não foi reaberta"

        for arquivo in ("env_do_shutdown", "env_da_reabertura"):
            steam = _le_env((estado / arquivo).read_text(encoding="utf-8"))
            assert _sem_a_classe(steam) == [], arquivo
            for nome in _LISTAS_DE_BUSCA_DA_STEAM:
                assert _path_sem_o_som_da_suite(steam[nome]) == f"{dubles}:/usr/bin:/bin", (
                    arquivo,
                    nome,
                )
            for nome, valor in sessao.items():
                assert steam[nome] == valor, (arquivo, nome)
            assert steam["XDG_RUNTIME_DIR"].startswith(str(tmp_path)), arquivo
