"""AMBIENTE-DO-JOGO-01 — o interpretador do terminal não vai para a Steam nem para o jogo.

Medido em 17/09/2026 no `environ` do `PRAGMATA.exe`: uma Steam aberta de um
terminal passa a todo jogo a venv desse terminal, com o `bin/` dela na frente do
`SYSTEM_PATH`. O `proton` é script Python, e quem o roda passa a ser o `python3`
que o terminal escolheu. O produto reabre a Steam de dentro do terminal da
pessoa (o install roda `steam_launch_options.py --stop-steam` e
`disable_steam_input.sh --apply`), e a devolvia assim.

O `SYSTEM_PATH` é o portador que decide: o `steam.sh` o grava com o `PATH` da
Steam, e a Steam Linux Runtime o devolve ao `PATH` DEPOIS do gancho do jogo,
antes do `proton`. Podar só o `PATH` no gancho não chegava ao jogo Proton.

A régua lê as TRÊS pontas contra o dono, `ambiente_do_jogo`:

- as chamadas Python que fazem a Steam nascer (`reopen_steam`,
  `start_steam_game`, `stop_steam` e o `_spawn_steam` do botão PS);
- o gancho `assets/hefesto-launch.sh`, rodado de verdade, por onde todo jogo
  passa — é ele que cobre a Steam que a PESSOA abriu de um terminal;
- o `scripts/disable_steam_input.sh`, rodado de verdade, com uma Steam de
  mentira que só grava o ambiente que recebeu.

Das pontas em shell a régua compara os NOMES e o COMPORTAMENTO: as duas
funções rodam sob o shell de cada arquivo, caso a caso, e o dono Python é o
oráculo de cada resposta.

Nenhum teste daqui abre, fecha ou mata a Steam da máquina: os dublês ficam na
frente do `PATH`, e o `pkill` também é dublê. Nenhum chega à sessão de quem
roda a suíte: o `XDG_RUNTIME_DIR` (a porta do daemon) e o barramento de
sessão apontam para o tmp do teste.
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
_LAUNCHER = Path(steam_launcher.__file__).resolve()

#: As funções em shell que repetem o dono, na ordem em que aparecem.
_FUNCOES_EM_SHELL = ("podar_bins_do_interpretador", "limpar_ambiente_do_interpretador")

#: As listas de busca que a Steam lê: o `PATH`, e o `SYSTEM_PATH` que o
#: `steam.sh` grava ao subir e a Steam Linux Runtime devolve ao `PATH` antes
#: do `proton`. É fato da Steam, e não do dono, e por isso está digitado: se o
#: dono esquecer uma delas, a régua tem de reprovar, e não esquecer junto.
_LISTAS_DE_BUSCA_DA_STEAM = ("PATH", "SYSTEM_PATH")


def _da_sessao(base: Path) -> dict[str, str]:
    """O que a Steam precisa para abrir e que a limpeza NÃO pode levar junto.

    Valores de MENTIRA, sob o tmp do teste: o `XDG_RUNTIME_DIR` é a porta do
    daemon de quem roda a suíte (o socket IPC mora nele), e o barramento de
    sessão também. O `DISPLAY` aponta um servidor que não existe: uma janela
    que nascesse por engano falharia, em vez de aparecer na tela de alguém.
    """
    runtime = base / "run"
    runtime.mkdir(parents=True, exist_ok=True)
    return {
        "DISPLAY": ":987",
        "WAYLAND_DISPLAY": "wayland-de-mentira",
        "XDG_RUNTIME_DIR": str(runtime),
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={runtime / 'bus'}",
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


def _busca_suja(sujo: dict[str, str], *antes: str) -> dict[str, str]:
    """As listas de busca de um terminal ativado: os `bin/` dele na frente.

    O `SYSTEM_PATH` é o que o `steam.sh` grava com o `PATH` da Steam que subiu
    daquele terminal, então as duas nascem iguais.
    """
    caminho = ":".join([*antes, *_bins_sujos(sujo), "/usr/bin", "/bin"])
    return {nome: caminho for nome in _LISTAS_DE_BUSCA_DA_STEAM}


def _sem_a_classe(env: dict[str, str]) -> list[str]:
    """O que sobrou da classe; vazio é o certo."""
    return [nome for nome in adj.VARIAVEIS_DO_INTERPRETADOR if nome in env]


# ---------------------------------------------------------------------------
# 1. O dono
# ---------------------------------------------------------------------------


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
        """O portador medido no PRAGMATA: a Steam Linux Runtime devolve o
        `SYSTEM_PATH` ao `PATH` antes do `proton`."""
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


# ---------------------------------------------------------------------------
# 2. A ponta Python: quem faz a Steam nascer
# ---------------------------------------------------------------------------


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

    def test_start_steam_game(
        self,
        terminal_sujo: dict[str, str],
        sessao: dict[str, str],
        popen_de_mentira: list[dict[str, Any]],
    ) -> None:
        assert slo.start_steam_game(1599660) is True
        assert popen_de_mentira[0]["cmd"] == ["steam", "steam://rungameid/1599660"]
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

    @pytest.mark.parametrize("arquivo", [_SLO, _LAUNCHER], ids=lambda p: p.name)
    def test_toda_steam_que_nasce_do_modulo_passa_pelo_dono(self, arquivo: Path) -> None:
        """Um `Popen` novo, ou uma chamada nova com a Steam no argv, sem
        `env=ambiente_limpo(os.environ)` reprova aqui.

        Nos dois módulos que fazem a Steam nascer. O argumento tem de ser o
        ambiente do processo: `ambiente_limpo({})` tiraria a sessão junto, e a
        Steam não abriria.
        """
        chamadas = _quem_abre_processo(ast.parse(arquivo.read_text(encoding="utf-8")))
        assert chamadas, f"a régua não achou chamada nenhuma em {arquivo.name}"
        sem_dono = [no.lineno for no in chamadas if not _env_pelo_dono(no)]
        assert sem_dono == [], (
            f"{arquivo.name}: sem env=ambiente_limpo(os.environ) nas linhas {sem_dono}"
        )

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
    """`Popen(cmd, **kwargs)` sem `env` próprio: quem decide é quem chamou.

    É o `_default_popen` do botão PS; a chamada que o alcança leva a Steam no
    argv e é cobrada por `_argv_da_steam`.
    """
    nomes = [kw.arg for kw in chamada.keywords]
    return None in nomes and "env" not in nomes


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
        )
    ]


# ---------------------------------------------------------------------------
# 3. As pontas em shell
# ---------------------------------------------------------------------------


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
        """O `SYSTEM_PATH` entra aqui: sem ele o jogo Proton volta a achar o
        `python3` do terminal depois da Steam Linux Runtime."""
        corpo = _funcao(caminho, "limpar_ambiente_do_interpretador")
        lidas = re.findall(r'podar_bins_do_interpretador "\$\{([A-Z_]+):-\}"', corpo)
        gravadas = re.findall(r'&& (?:export )?([A-Z_]+)="\$la_novo"', corpo)
        assert sorted(lidas) == sorted(adj.VARIAVEIS_DE_BUSCA)
        assert sorted(gravadas) == sorted(adj.VARIAVEIS_DE_BUSCA)

    def test_as_duas_copias_em_shell_sao_a_mesma(self) -> None:
        assert _funcoes(_WRAPPER) == _funcoes(_DISABLE)


#: A borda, caso a caso. Cada um roda sob o shell de cada ponta, e o dono
#: Python responde o que devia sair. Os valores não precisam existir no disco:
#: a poda é só texto.
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
    """O gancho roda sob `sh` (a Steam o chama pelo shebang); o roteiro, sob
    bash com o `set -u` que ele liga no topo."""
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
        # O ambiente é lido ANTES e DEPOIS no mesmo processo: o oráculo recebe
        # exatamente o que o shell recebeu, inclusive o que a `conftest` põe
        # no PATH de todo subprocesso da suíte.
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


#: O que a Steam Linux Runtime faz entre o gancho e o `proton`, copiado do
#: `pressure-vessel-unruntime` (o `%command%` de todo jogo Proton passa por ele).
_A_STEAM_LINUX_RUNTIME = (
    'if [ -n "${SYSTEM_PATH+set}" ]; then export PATH="$SYSTEM_PATH"; fi; exec env'
)


class TestOGanchoDoJogo:
    """O `hefesto-launch` de verdade, com `env` no lugar do jogo."""

    def _roda(self, tmp_path: Path, *jogo: str) -> tuple[dict[str, str], dict[str, str]]:
        sujo = _terminal_sujo(tmp_path)
        mudos = tmp_path / "mudos"
        # O Game Mode do gancho fala com o daemon de energia: dublês mudos na
        # frente do PATH, como em `test_hefesto_launch_wrapper.py`.
        _dubles(mudos, {n: "exit 1" for n in ("system76-power", "busctl", "dbus-send")})
        env = {
            **sujo,
            # Sem socket no XDG_RUNTIME_DIR de mentira: nenhuma env nossa.
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
        """O caminho inteiro de um jogo Proton: o gancho e, DEPOIS dele, a
        Steam Linux Runtime devolvendo o `SYSTEM_PATH` ao `PATH`. É o `PATH`
        que o `#!/usr/bin/env python3` do `proton` usa."""
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
            for nome in _LISTAS_DE_BUSCA_DA_STEAM:
                assert _path_sem_o_som_da_suite(steam[nome]) == f"{dubles}:/usr/bin:/bin", (
                    arquivo,
                    nome,
                )
            # A sessão atravessa, e é a de MENTIRA: o roteiro nunca recebeu a
            # porta do daemon nem o barramento de quem roda a suíte.
            for nome, valor in sessao.items():
                assert steam[nome] == valor, (arquivo, nome)
            assert steam["XDG_RUNTIME_DIR"].startswith(str(tmp_path)), arquivo
