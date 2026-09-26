"""STEAM-FORA-DO-SERVICO-01 — o aplicativo da pessoa nasce fora do serviço do Hefesto.

Medido em 26/09/2026: o botão PS abria a Steam por ``Popen`` de dentro do
daemon, e a Steam e o jogo nasciam no cgroup ``hefesto-dualsense4unix.service``,
com o nice 5 e o oom 200 dele, e morriam no restart da unit. A cura é
``integrations/fora_do_servico.abrir``; a medição que escolheu a forma está no
docstring dele.

Nenhum teste daqui chega ao gerenciador de usuário de quem roda a suíte: o
``executar`` é sempre dublê, e o de verdade RECUSA sob a suíte (a última
classe prova isso).

As três réguas que a sprint pede:

1. a Steam do daemon nasce numa unidade própria quando há systemd de usuário —
   e NÃO por ``Popen`` (``TestADoDaemonNasceFora``);
2. o ``ambiente_limpo`` chega ao filho (``TestOAmbienteChegaAoFilho``), lido
   como o gerenciador o monta: o ambiente dele, o ``--setenv`` por cima, o
   ``UnsetEnvironment`` no fim;
3. sem systemd de usuário, ou com quem chama já sendo da pessoa, o ``Popen``
   de sempre (``TestOPopenDeSempre``).
"""
from __future__ import annotations

import ast
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.integrations import ambiente_do_jogo as adj
from hefesto_dualsense4unix.integrations import fora_do_servico as fds
from hefesto_dualsense4unix.integrations import steam_launcher

_RAIZ = Path(__file__).resolve().parents[2]
_INTEGRACOES = _RAIZ / "src" / "hefesto_dualsense4unix" / "integrations"

#: O cgroup do daemon medido em 26/09 (`/proc/<pid>/cgroup`).
_CGROUP_DO_DAEMON = (
    "/user.slice/user-1000.slice/user@1000.service/app.slice/"
    "hefesto-dualsense4unix.service"
)
#: O da janela aberta pelo painel do COSMIC, medido no mesmo dia.
_CGROUP_DO_PAINEL = (
    "/user.slice/user-1000.slice/user@1000.service/app.slice/"
    "app-cosmic-com.system76.CosmicAppList-2665262.scope"
)

_DENTRO_DO_SERVICO = fds.Contexto(
    gerenciador=True,
    herdaria="dentro do serviço hefesto-dualsense4unix.service",
    oom_do_gerenciador=100,
)


class _Executar:
    """O ``systemd-run`` de mentira: anota a linha e devolve o que mandarem."""

    def __init__(self, *codigos: int, erro: str = "") -> None:
        self.codigos = list(codigos) or [0]
        self.erro = erro
        self.chamadas: list[list[str]] = []

    def __call__(
        self, cmd: Sequence[str], env: Mapping[str, str]
    ) -> subprocess.CompletedProcess[str]:
        self.chamadas.append(list(cmd))
        rc = self.codigos.pop(0) if len(self.codigos) > 1 else self.codigos[0]
        return subprocess.CompletedProcess(cmd, rc, stdout="", stderr=self.erro)


def _popen_proibido(*_a: Any, **_k: Any) -> object:
    raise AssertionError("a Steam nasceu por Popen de dentro do serviço")


def _pgrep(rc: int, saida: str = "") -> Any:
    return lambda _cmd: subprocess.CompletedProcess(["pgrep"], rc, stdout=saida, stderr="")


def _wmctrl_sem_janela(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(cmd, 0, stdout="0x01 0 Firefox.firefox h t\n", stderr="")


def _depois_do_traco(cmd: list[str]) -> list[str]:
    return cmd[cmd.index("--") + 1 :]


# ---------------------------------------------------------------------------
# 1 — a Steam do daemon nasce numa unidade própria
# ---------------------------------------------------------------------------


class TestADoDaemonNasceFora:
    """MORDE: troque o ``fora_do_servico.abrir`` de ``_spawn_steam`` pelo
    ``runner([STEAM_BINARY], ..., start_new_session=True, env=...)`` de antes e
    as duas primeiras reprovam — o ``Popen`` proibido é chamado."""

    @pytest.mark.parametrize(
        ("pgrep", "desfecho"),
        [(_pgrep(1), "spawned"), (_pgrep(0, "4242\n"), "refocus_fallback_spawn")],
        ids=["spawned", "refocus_fallback_spawn"],
    )
    def test_a_steam_do_botao_ps_nasce_numa_unidade(
        self, pgrep: Any, desfecho: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(steam_launcher.shutil, "which", lambda n: f"/usr/bin/{n}")
        executar = _Executar(0)
        assert steam_launcher.open_or_focus_steam(
            which=lambda n: f"/usr/bin/{n}",
            pgrep_runner=pgrep,
            wmctrl_runner=_wmctrl_sem_janela,
            popen_runner=_popen_proibido,
            contexto=_DENTRO_DO_SERVICO,
            executar=executar,
        ) is True, desfecho
        assert len(executar.chamadas) == 1
        cmd = executar.chamadas[0]
        assert cmd[:2] == ["systemd-run", "--user"]
        assert "--scope" not in cmd, "um scope é filho do daemon e herda nice e oom"
        assert "--property=Type=exec" in cmd
        assert "--property=ExitType=cgroup" in cmd
        assert "--property=OOMScoreAdjust=100" in cmd
        # O DEVNULL do Popen de sempre, e não o diário de todo serviço.
        assert "--property=StandardOutput=null" in cmd
        assert "--property=StandardError=null" in cmd
        assert _depois_do_traco(cmd) == ["steam"]
        unidade = next(a for a in cmd if a.startswith("--unit="))
        assert unidade.startswith("--unit=app-hefesto-steam-")
        assert unidade.endswith(".service")

    def test_o_comando_proprio_do_ps_nasce_fora(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O ``custom`` do PS é o programa DELA, e mora no mesmo serviço.

        MORDE: devolva o ``_sp.Popen(command, ...)`` ao ``_on_ps_solo`` e o
        ``abrir`` não é chamado.
        """
        chamadas: list[dict[str, Any]] = []

        def _abrir(argv: Sequence[str], **kwargs: Any) -> fds.Abertura:
            chamadas.append({"argv": list(argv), **kwargs})
            return fds.Abertura(caminho="unidade", motivo="teste", unidade="u")

        monkeypatch.setattr(fds, "abrir", _abrir)
        monkeypatch.setenv("VIRTUAL_ENV", "/tmp/venv-de-mentira")
        daemon = SimpleNamespace(
            config=SimpleNamespace(
                ps_button_action="custom", ps_button_command=["meu-programa", "--x"]
            ),
            _emulation_suppressed=False,
            store=SimpleNamespace(native_mode_active=False),
            _keyboard_device=None,
        )
        hotkey.definir_acao_do_ps(daemon, None)
        hotkey.build_ps_solo_callback(daemon)()
        assert [c["argv"] for c in chamadas] == [["meu-programa", "--x"]]
        assert "VIRTUAL_ENV" not in chamadas[0]["env"]

    def test_o_servico_do_daemon_herda_e_o_painel_nao(self) -> None:
        """A pergunta que decide, com os três números medidos em 26/09."""
        assert fds.motivo_de_herdar(
            cgroup=_CGROUP_DO_DAEMON, nice=5, oom=200, oom_do_gerenciador=100
        ) == "dentro do serviço hefesto-dualsense4unix.service"
        assert fds.motivo_de_herdar(
            cgroup=_CGROUP_DO_PAINEL, nice=0, oom=0, oom_do_gerenciador=100
        ) is None
        # Fora de serviço, mas com o nice ou o oom do daemon (o daemon rodado
        # de um terminal): o filho herdaria do mesmo jeito.
        assert fds.motivo_de_herdar(
            cgroup=_CGROUP_DO_PAINEL, nice=5, oom=0, oom_do_gerenciador=100
        ) == "nice 5"
        assert fds.motivo_de_herdar(
            cgroup=_CGROUP_DO_PAINEL, nice=0, oom=200, oom_do_gerenciador=100
        ) == "oom_score_adj 200"

    def test_o_contexto_le_o_proc_e_o_piso_do_gerenciador(self, tmp_path: Path) -> None:
        """``contexto_atual`` lê ``/proc/self`` e acha o oom do gerenciador.

        Duas rotas: o ``MANAGERPID`` que o gerenciador põe nos serviços dele, e
        o ``init.scope`` do ``user@<uid>.service`` para quem está num scope.
        """
        proc = tmp_path / "proc"
        (proc / "self").mkdir(parents=True)
        (proc / "self" / "cgroup").write_text(f"0::{_CGROUP_DO_DAEMON}\n")
        # Depois do `)`: o 3º campo (estado) é o índice 0, então o 18º
        # (prioridade) é o 15 e o 19º (nice) é o 16.
        campos = ["S", "1"] + ["0"] * 13 + ["25", "5"] + ["0"] * 30
        (proc / "self" / "stat").write_text("4242 (python) " + " ".join(campos) + "\n")
        (proc / "self" / "oom_score_adj").write_text("200\n")
        (proc / "1703").mkdir()
        (proc / "1703" / "oom_score_adj").write_text("100\n")
        runtime = tmp_path / "run"
        (runtime / "systemd").mkdir(parents=True)
        (runtime / "systemd" / "private").write_text("")
        env = {"MANAGERPID": "1703", "XDG_RUNTIME_DIR": str(runtime)}

        ctx = fds.contexto_atual(environ=env, raiz_proc=str(proc))
        assert ctx.herdaria == "dentro do serviço hefesto-dualsense4unix.service"
        assert ctx.oom_do_gerenciador == 100

        cg = tmp_path / "cgroup" / "user.slice" / "user-1000.slice" / "user@1000.service"
        (cg / "init.scope").mkdir(parents=True)
        (cg / "init.scope" / "cgroup.procs").write_text("1703\n1755\n")
        assert fds.oom_do_gerenciador(
            cgroup=_CGROUP_DO_PAINEL,
            environ={},
            raiz_proc=str(proc),
            raiz_cgroup=str(tmp_path / "cgroup"),
        ) == 100


# ---------------------------------------------------------------------------
# 2 — o ambiente_limpo chega ao filho
# ---------------------------------------------------------------------------


def _ambiente_do_filho(cmd: list[str], do_gerenciador: Mapping[str, str]) -> dict[str, str]:
    """O ambiente que o gerenciador monta para a unidade (``systemd.exec(5)``).

    O dele primeiro; o ``Environment=`` (``--setenv``) por cima; o
    ``UnsetEnvironment=`` no fim. As variáveis que o gerenciador escreve para a
    unidade nova (``INVOCATION_ID``…) entram antes do ``Environment=``: por
    isso um ``--setenv`` com a do daemon as trocaria.
    """
    env = dict(do_gerenciador)
    env["INVOCATION_ID"] = "da-unidade-nova"
    for arg in cmd[: cmd.index("--")]:
        if arg.startswith("--setenv="):
            nome, _, valor = arg.removeprefix("--setenv=").partition("=")
            env[nome] = valor
    for arg in cmd:
        if arg.startswith("--property=UnsetEnvironment="):
            for nome in arg.split("=", 2)[2].split():
                env.pop(nome, None)
    return env


class TestOAmbienteChegaAoFilho:
    """MORDE: mande ``os.environ`` em vez de ``ambiente_limpo(os.environ)`` no
    ``_spawn_steam`` e a primeira reprova pela venv; tire o ``--setenv`` do
    ``argv_da_unidade`` e ela reprova pela sessão."""

    @pytest.fixture()
    def daemon_sujo(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, str]:
        venv = tmp_path / "venv"
        sujo = {
            "VIRTUAL_ENV": str(venv),
            "CONDA_PREFIX": str(tmp_path / "conda"),
            "PYTHONPATH": "/algum/src",
            "PATH": f"{venv}/bin:/usr/local/bin:/usr/bin:/usr/games",
            # As da unidade do daemon, medidas no environ dele em 26/09.
            "INVOCATION_ID": "do-daemon",
            "JOURNAL_STREAM": "10:30588975",
            "MANAGERPID": "1703",
            "SYSTEMD_EXEC_PID": "2491964",
            "MEMORY_PRESSURE_WATCH": "/sys/fs/cgroup/do/daemon/memory.pressure",
            # A sessão, de que a Steam precisa.
            "WAYLAND_DISPLAY": "wayland-1",
            "DISPLAY": ":0",
            "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
            "XDG_RUNTIME_DIR": "/run/user/1000",
            "COM_DOLAR": "a$b",
        }
        for nome, valor in sujo.items():
            monkeypatch.setenv(nome, valor)
        return sujo

    def test_o_filho_recebe_o_ambiente_limpo_e_nada_da_unidade_do_daemon(
        self, daemon_sujo: dict[str, str]
    ) -> None:
        executar = _Executar(0)
        assert steam_launcher._spawn_steam(
            popen_runner=_popen_proibido, contexto=_DENTRO_DO_SERVICO, executar=executar
        ) is True
        cmd = executar.chamadas[0]
        # O gerenciador de uma sessão aberta de um terminal sujo tem a venv no
        # ambiente dele também: o UnsetEnvironment é quem a tira desse lado.
        do_gerenciador = {"VIRTUAL_ENV": "/venv/do/gerenciador", "LANG": "C.UTF-8"}
        filho = _ambiente_do_filho(cmd, do_gerenciador)

        esperado = adj.ambiente_limpo(daemon_sujo)
        for nome in fds.VARIAVEIS_DA_UNIDADE:
            esperado.pop(nome, None)
        for nome, valor in esperado.items():
            assert filho.get(nome) == valor, f"{nome} não chegou ao filho como o dono o limpou"
        for nome in adj.VARIAVEIS_DO_INTERPRETADOR:
            assert nome not in filho, f"{nome} atravessou para a Steam"
        assert f"{daemon_sujo['VIRTUAL_ENV']}/bin" not in filho["PATH"].split(":")
        assert filho["INVOCATION_ID"] == "da-unidade-nova"
        assert "JOURNAL_STREAM" not in filho
        assert "MEMORY_PRESSURE_WATCH" not in filho
        assert filho["COM_DOLAR"] == "a$b"

    def test_variavel_que_o_systemd_run_recusaria_fica_de_fora(self) -> None:
        """Uma só recusada derrubaria a abertura inteira (medido:
        ``Cannot assign environment variable BASH_FUNC_x%%``)."""
        mantidas, fora = fds.ambiente_da_unidade(
            {
                "BASH_FUNC_x%%": "() { :; }",
                "COM_QUEBRA": "a\nb",
                "SURROGATE": "a\udcffb",
                "TAB_PODE": "a\tb",
                "PATH": "/usr/bin",
            }
        )
        assert mantidas == {"TAB_PODE": "a\tb", "PATH": "/usr/bin"}
        assert fora == ("BASH_FUNC_x%%", "COM_QUEBRA", "SURROGATE")

    def test_o_dolar_do_comando_nao_vira_variavel(self) -> None:
        """O gerenciador expande ``$NOME`` no ``ExecStart``; ``$$`` é o ``$``.
        Medido em 26/09: o ``sh`` recebeu ``a$b`` pela unidade."""
        cmd = fds.argv_da_unidade(
            ["prog", "a$b", "${HOME}"], {}, unidade="u.service", forma="ExitType=cgroup", oom=None
        )
        assert _depois_do_traco(cmd) == ["prog", "a$$b", "$${HOME}"]
        assert not any(a.startswith("--property=OOMScoreAdjust") for a in cmd)


# ---------------------------------------------------------------------------
# 3 — o Popen de sempre, quando é ele o caminho
# ---------------------------------------------------------------------------


class _Popen:
    def __init__(self) -> None:
        self.chamadas: list[dict[str, Any]] = []

    def __call__(self, cmd: list[str], **kwargs: Any) -> object:
        self.chamadas.append({"cmd": list(cmd), **kwargs})
        return object()


class TestOPopenDeSempre:
    def test_sem_systemd_de_usuario(self) -> None:
        popen = _Popen()
        ctx = fds.Contexto(gerenciador=False, herdaria="dentro do serviço x.service",
                           oom_do_gerenciador=None)
        ab = fds.abrir(["steam"], env={"PATH": "/usr/bin"}, contexto=ctx,
                       executar=_Executar(0), popen=popen)
        assert ab.caminho == "popen"
        assert popen.chamadas[0]["cmd"] == ["steam"]
        assert popen.chamadas[0]["start_new_session"] is True
        assert popen.chamadas[0]["env"] == {"PATH": "/usr/bin"}

    def test_quem_chama_ja_e_da_pessoa(self) -> None:
        popen = _Popen()
        executar = _Executar(0)
        ctx = fds.Contexto(gerenciador=True, herdaria=None, oom_do_gerenciador=100)
        assert fds.abrir(["steam"], env={}, contexto=ctx, executar=executar,
                         popen=popen).caminho == "popen"
        assert executar.chamadas == []

    def test_systemd_antigo_cai_no_killmode_process(self) -> None:
        """Antes do systemd 250 o ``ExitType`` não existe (``Unknown
        assignment``); o ``KillMode=process`` foi medido com o mesmo efeito."""
        executar = _Executar(1, 0, erro="Unknown assignment: ExitType=cgroup")
        ab = fds.abrir(["steam"], env={}, contexto=_DENTRO_DO_SERVICO,
                       executar=executar, popen=_popen_proibido)
        assert ab.caminho == "unidade"
        assert "--property=ExitType=cgroup" in executar.chamadas[0]
        assert "--property=KillMode=process" in executar.chamadas[1]
        assert "Unknown assignment" in ab.tentativas[0]

    def test_o_systemd_run_que_recusa_as_duas_cai_no_popen(self) -> None:
        popen = _Popen()
        ab = fds.abrir(["steam"], env={}, contexto=_DENTRO_DO_SERVICO,
                       executar=_Executar(1, erro="Failed to connect to bus"), popen=popen)
        assert ab.caminho == "popen"
        assert len(ab.tentativas) == 2
        assert popen.chamadas[0]["cmd"] == ["steam"]

    def test_sem_resposta_nao_abre_duas_vezes(self) -> None:
        def _pendurado(cmd: Sequence[str], _env: Mapping[str, str]) -> Any:
            raise subprocess.TimeoutExpired(list(cmd), fds.ESPERA_DO_SYSTEMD_RUN_S)

        ab = fds.abrir(["steam"], env={}, contexto=_DENTRO_DO_SERVICO,
                       executar=_pendurado, popen=_popen_proibido)
        assert ab.caminho == "unidade"
        assert ab.unidade is not None


# ---------------------------------------------------------------------------
# 4 — a suíte nunca chega ao gerenciador de verdade
# ---------------------------------------------------------------------------


class TestASuiteNaoAbreUnidade:
    def test_o_systemd_run_de_verdade_recusa_sob_a_suite(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDE: tire a pergunta ``_a_suite_esta_rodando`` do
        ``_executar_de_verdade`` e o ``subprocess.run`` proibido é chamado."""

        def _run_proibido(*_a: Any, **_k: Any) -> Any:
            raise AssertionError("a suíte chegou ao gerenciador de verdade")

        monkeypatch.setattr(fds.subprocess, "run", _run_proibido)
        popen = _Popen()
        ab = fds.abrir(["steam"], env={}, contexto=_DENTRO_DO_SERVICO, popen=popen)
        assert ab.caminho == "popen"
        assert "a suíte está no ar" in ab.tentativas[0]


# ---------------------------------------------------------------------------
# 5 — nenhum Popen novo abre aplicativo da pessoa por fora do dono
# ---------------------------------------------------------------------------

#: Os módulos que abrem aplicativo da pessoa, e o Popen que cada um ainda pode
#: ter: o ``steam -shutdown`` fala com a Steam de pé, não faz nascer nenhuma, e
#: o ``_default_popen`` só repassa o que o dono mandou.
_DONOS = {
    _INTEGRACOES / "steam_launcher.py": 1,
    _INTEGRACOES / "steam_launch_options.py": 1,
    _INTEGRACOES / "reposicao_dos_lancadores.py": 0,
    _RAIZ / "src" / "hefesto_dualsense4unix" / "daemon" / "subsystems" / "hotkey.py": 0,
}


@pytest.mark.parametrize("arquivo", list(_DONOS), ids=lambda p: p.name)
def test_nenhum_aplicativo_nasce_por_popen_fora_do_dono(arquivo: Path) -> None:
    """Um ``Popen`` novo num destes módulos reprova aqui: quem abre aplicativo
    da pessoa passa por ``fora_do_servico.abrir``.

    MORDE: devolva o ``_sp.Popen`` ao comando próprio do PS e ``hotkey.py``
    reprova com um Popen a mais.
    """
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    popens = [
        no for no in ast.walk(arvore)
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Attribute)
        and no.func.attr == "Popen"
    ]
    assert len(popens) == _DONOS[arquivo], (
        f"{arquivo.name}: Popen nas linhas {[n.lineno for n in popens]}"
    )
    abrires = [
        no for no in ast.walk(arvore)
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Attribute)
        and no.func.attr == "abrir"
        and isinstance(no.func.value, ast.Name)
        and no.func.value.id == "fora_do_servico"
    ]
    assert abrires, f"{arquivo.name} não abre nada pelo dono"
