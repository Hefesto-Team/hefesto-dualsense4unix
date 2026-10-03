"""TODO-PROGRAMA-DO-DAEMON-NASCE-FORA-DO-SERVICO-01 — o que o daemon abre, e onde nasce."""
from __future__ import annotations

import ast
import contextlib
import functools
import json
import os
import shutil
import signal
import subprocess
import threading
import time
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.keyboard_mappings import TOKEN_TOGGLE_OSK
from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.daemon.subsystems import keyboard as teclado
from hefesto_dualsense4unix.integrations import fora_do_servico as fds
from hefesto_dualsense4unix.integrations import steam_launcher
from hefesto_dualsense4unix.integrations.hotkey_daemon import HotkeyConfig, HotkeyManager

_PACOTE = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"

_POPEN_DE_VERDADE = subprocess.Popen
_PASTAS_DO_DAEMON = ("daemon", "integrations")


VEREDITOS: dict[str, tuple[str, int, str]] = {
    "daemon/subsystems/ouvinte_do_som.py::_uma_volta": (
        "ajudante", 1,
        "o `pactl subscribe` do leitor único do som; morre com o daemon",
    ),
    "integrations/filho_de_som.py::lancar_leitor": (
        "ajudante", 1,
        "os leitores de som (`parec`/`pw-record`), presos ao pai pelo cano e "
        "pelo PDEATHSIG",
    ),
    "integrations/gesto_de_pareamento.py::_abrir_de_verdade": (
        "ajudante", 1,
        "a janela de busca da ponte root (`sudo … descobrir`); morre com quem "
        "a abriu, e o `fechar` a derruba",
    ),
    "integrations/endpoint_de_haptica.py::TocadorDoRumble.__init__": (
        "ajudante", 1,
        "o `pw-cat` (ou o `pacat`) que toca o rumble do jogo como háptica no "
        "endpoint de um lugar (D-2909-RUMBLE-VIRA-HAPTICA): alimentado pelo cano, "
        "sai depois da folga de silêncio e com o `parar`",
    ),
    "integrations/laco_de_audio.py::Lacos.ligar": (
        "ajudante", 1,
        "o `pw-loopback` de um laço de som, com dono que o fecha",
    ),
    "integrations/nivel_do_microfone.py::abrir_fluxo": (
        "ajudante", 1,
        "o `parec` do medidor de nível, preso ao pai",
    ),
    "integrations/steam_launch_options.py::stop_steam": (
        "ajudante", 1,
        "`steam -shutdown`: pede à Steam de pé que feche, e volta em segundos; "
        "não faz nascer Steam nenhuma",
    ),
    "integrations/fora_do_servico.py::abrir": (
        "o dono", 1,
        "o `Popen` de reserva: quem chama já é da pessoa, ou não há systemd de "
        "usuário, ou ele recusou",
    ),
    "integrations/fora_do_servico.py::rodar_e_esperar": (
        "o dono", 1,
        "o `Popen` de reserva do script de um gesto: espera o fim, com teto",
    ),
    "integrations/steam_launcher.py::_default_popen": (
        "reserva do dono", 1,
        "o `popen=` que `_spawn_steam` entrega a `fora_do_servico.abrir`",
    ),
    "integrations/tray.py::TrayController._on_open_tui": (
        "outro processo", 1,
        "roda no processo da bandeja (`app-hefesto…tray@autostart.service`), "
        "não no daemon; a classe tem lápide desde 19/09 e nada a instancia",
    ),
}

VEREDITOS_VALIDOS = frozenset({"ajudante", "o dono", "reserva do dono", "outro processo"})

PROGRAMAS_DELA: dict[str, str] = {
    "daemon/subsystems/keyboard.py::_OSKController._abrir": "o teclado na tela (L3)",
    "daemon/subsystems/hotkey.py::_a_acao_da_maquina": "o programa do PS personalizado",
    "daemon/subsystems/hotkey.py::_abrir_o_ato_da_bandeja": (
        "os três atos da bandeja que um gesto alcança (OS-GESTOS, 01/10/2026)"
    ),
    "integrations/steam_launcher.py::_spawn_steam": "a Steam do PS",
    "integrations/steam_launch_options.py::reopen_steam": "a Steam reaberta",
    "integrations/reposicao_dos_lancadores.py::abrir": (
        "o lançador reposto no «Reiniciar o serviço»"
    ),
}

_DO_OS = frozenset({
    "system", "fork", "forkpty", "posix_spawn", "posix_spawnp",
    "execl", "execle", "execlp", "execlpe", "execv", "execve", "execvp", "execvpe",
    "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp",
    "spawnvpe",
})
_DO_ASYNCIO = frozenset({"create_subprocess_exec", "create_subprocess_shell"})


def _ids_de(no: ast.AST | None) -> set[int]:
    return {id(n) for n in ast.walk(no)} if no is not None else set()


def _nomes_do_dono(arvore: ast.Module) -> tuple[set[str], set[str]]:
    """Os nomes que, neste módulo, são o ``fora_do_servico`` e o ``abrir`` dele."""
    modulos: set[str] = set()
    funcoes: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom):
            origem = no.module or ""
            for alias in no.names:
                if alias.name == "fora_do_servico":
                    modulos.add(alias.asname or alias.name)
                elif alias.name == "abrir" and origem.endswith("fora_do_servico"):
                    funcoes.add(alias.asname or alias.name)
        elif isinstance(no, ast.Import):
            for alias in no.names:
                if alias.name.endswith("fora_do_servico"):
                    modulos.add(alias.asname or alias.name.rsplit(".", 1)[-1])
    return modulos, funcoes


def _chama_o_dono(no: ast.Call, modulos: set[str], funcoes: set[str]) -> bool:
    f = no.func
    if isinstance(f, ast.Attribute) and f.attr == "abrir":
        return isinstance(f.value, ast.Name) and f.value.id in modulos
    return isinstance(f, ast.Name) and f.id in funcoes


def _abre_processo(no: ast.Call) -> bool:
    f = no.func
    if isinstance(f, ast.Name):
        return f.id == "Popen"
    if not isinstance(f, ast.Attribute):
        return False
    if f.attr == "Popen" or f.attr in _DO_ASYNCIO:
        return True
    dono = f.value.id if isinstance(f.value, ast.Name) else None
    return (dono == "os" and f.attr in _DO_OS) or (dono == "pty" and f.attr in {"spawn", "fork"})


def _e_popen(no: ast.AST) -> bool:
    return (isinstance(no, ast.Attribute) and no.attr == "Popen") or (
        isinstance(no, ast.Name) and no.id == "Popen"
    )


def varrer(fonte: str, rel: str) -> tuple[Counter[str], set[str]]:
    """``(quem abre processo, quem chama o dono)`` de um fonte, por função."""
    arvore = ast.parse(fonte)
    modulos, funcoes = _nomes_do_dono(arvore)
    fora: set[int] = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = no.args
            for arg in [*a.posonlyargs, *a.args, *a.kwonlyargs, a.vararg, a.kwarg]:
                if arg is not None:
                    fora |= _ids_de(arg.annotation)
            fora |= _ids_de(no.returns)
        elif isinstance(no, ast.AnnAssign):
            fora |= _ids_de(no.annotation)
        elif isinstance(no, ast.Call) and _chama_o_dono(no, modulos, funcoes):
            for kw in no.keywords:
                if kw.arg == "popen":
                    fora |= _ids_de(kw.value)

    abridores: Counter[str] = Counter()
    donos: set[str] = set()
    pilha: list[str] = []

    class _V(ast.NodeVisitor):
        def _dentro(self, no: Any) -> None:
            pilha.append(no.name)
            self.generic_visit(no)
            pilha.pop()

        def visit_FunctionDef(self, no: ast.FunctionDef) -> None:
            self._dentro(no)

        def visit_AsyncFunctionDef(self, no: ast.AsyncFunctionDef) -> None:
            self._dentro(no)

        def visit_ClassDef(self, no: ast.ClassDef) -> None:
            self._dentro(no)

        def visit_Call(self, no: ast.Call) -> None:
            chave = f"{rel}::{'.'.join(pilha) or '<módulo>'}"
            if _abre_processo(no):
                abridores[chave] += 1
                fora.add(id(no.func))
            if _chama_o_dono(no, modulos, funcoes):
                donos.add(chave)
            self.generic_visit(no)

        def generic_visit(self, no: ast.AST) -> None:
            if _e_popen(no) and id(no) not in fora:
                abridores[f"{rel}::{'.'.join(pilha) or '<módulo>'}"] += 1
                fora.add(id(no))
            super().generic_visit(no)

    _V().visit(arvore)
    return abridores, donos


def _varrer_pastas(pastas: Sequence[str]) -> tuple[Counter[str], set[str]]:
    abridores: Counter[str] = Counter()
    donos: set[str] = set()
    for pasta in pastas:
        for arquivo in sorted((_PACOTE / pasta).rglob("*.py")):
            rel = arquivo.relative_to(_PACOTE).as_posix()
            a, d = varrer(arquivo.read_text(encoding="utf-8"), rel)
            abridores.update(a)
            donos |= d
    return abridores, donos


def test_todo_processo_que_o_daemon_abre_tem_veredito() -> None:
    """A régua 1, nos dois sentidos, com a contagem."""
    abridores, _ = _varrer_pastas(_PASTAS_DO_DAEMON)
    sem_veredito = {k: n for k, n in abridores.items() if k not in VEREDITOS}
    sem_popen = sorted(set(VEREDITOS) - set(abridores))
    contagem_errada = {
        k: (VEREDITOS[k][1], n) for k, n in abridores.items()
        if k in VEREDITOS and VEREDITOS[k][1] != n
    }
    assert not sem_veredito, (
        f"processo aberto sem veredito (programa dela vai pelo "
        f"`fora_do_servico.abrir`; ajudante ganha linha em VEREDITOS): {sem_veredito}"
    )
    assert not sem_popen, f"veredito para quem não abre mais processo: {sem_popen}"
    assert not contagem_errada, f"(esperado, achado): {contagem_errada}"
    assert {v for v, _, _ in VEREDITOS.values()} <= VEREDITOS_VALIDOS


def test_todo_programa_dela_passa_pelo_dono() -> None:
    """A régua 2: quem chama ``fora_do_servico.abrir`` em ``src/``, nos dois sentidos."""
    pastas = [p.name for p in sorted(_PACOTE.iterdir()) if p.is_dir()]
    _, donos = _varrer_pastas(pastas)
    assert donos == set(PROGRAMAS_DELA), (
        f"a mais: {sorted(donos - set(PROGRAMAS_DELA))}; "
        f"a menos: {sorted(set(PROGRAMAS_DELA) - donos)}"
    )


def test_o_teclado_na_tela_abre_pelo_dono_e_so_por_ele() -> None:
    """O item 3 da sprint, dito do arquivo: nenhum ``Popen`` no teclado, e o"""
    arquivo = _PACOTE / "daemon" / "subsystems" / "keyboard.py"
    abridores, donos = varrer(
        arquivo.read_text(encoding="utf-8"), "daemon/subsystems/keyboard.py")
    assert not abridores, f"o teclado voltou a abrir processo por fora do dono: {abridores}"
    assert "daemon/subsystems/keyboard.py::_OSKController._abrir" in donos


def test_a_varredura_ve_o_popen_escondido() -> None:
    """A régua não é cega ao ``Popen`` guardado num nome, nem ao do ``os``."""
    fonte = (
        "import os, subprocess\n"
        "from hefesto_dualsense4unix.integrations import fora_do_servico\n"
        "def escondido():\n"
        "    f = subprocess.Popen\n"
        "    f(['x'])\n"
        "def pelo_os():\n"
        "    os.system('x')\n"
        "def pelo_dono(p: subprocess.Popen[str]) -> subprocess.Popen[str]:\n"
        "    return fora_do_servico.abrir(['x'], env={}, popen=subprocess.Popen)\n"
    )
    abridores, donos = varrer(fonte, "x.py")
    assert abridores == Counter({"x.py::escondido": 1, "x.py::pelo_os": 1})
    assert donos == {"x.py::pelo_dono"}


_DENTRO_DO_SERVICO = fds.Contexto(
    gerenciador=True,
    herdaria="dentro do serviço hefesto-dualsense4unix.service",
    oom_do_gerenciador=100,
)

_DUBLE = "sleep"


class _GerenciadorDeMentira:
    """O ``systemd-run`` de mentira, e ele não é mais frouxo que o real."""

    def __init__(self, raiz: Path, *, nascer: bool = True) -> None:
        self.raiz = raiz
        self.nascer = nascer
        self.chamadas: list[list[str]] = []
        self.nascidos: list[subprocess.Popen[bytes]] = []
        self.segurar: threading.Event | None = None
        self.demora_s = 0.0

    def pasta(self, unidade: str) -> Path:
        base = str(fds._base_do_gerenciador(fds.RAIZ_DO_PROC))
        return Path(self.raiz, base, "app.slice", unidade)

    def __call__(
        self, cmd: Sequence[str], env: Mapping[str, str]
    ) -> subprocess.CompletedProcess[str]:
        self.chamadas.append(list(cmd))
        if self.segurar is not None:
            self.segurar.wait(10.0)
        if self.demora_s:
            time.sleep(self.demora_s)
        if self.nascer:
            unidade = next(a.split("=", 1)[1] for a in cmd if a.startswith("--unit="))
            argv = [a.replace("$$", "$") for a in cmd[list(cmd).index("--") + 1 :]]
            proc = _POPEN_DE_VERDADE(
                argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, start_new_session=True,
            )
            self.nascidos.append(proc)
            pasta = self.pasta(unidade)
            pasta.mkdir(parents=True)
            (pasta / "cgroup.procs").write_text(f"{proc.pid}\n", encoding="utf-8")
        return subprocess.CompletedProcess(list(cmd), 0, stdout="", stderr="")

    def recolher(self, unidade: str) -> None:
        """O ``--collect``: a unidade que esvaziou sai da árvore."""
        shutil.rmtree(self.pasta(unidade), ignore_errors=True)


def _unidade_de(cmd: Sequence[str]) -> str:
    return next(a.split("=", 1)[1] for a in cmd if a.startswith("--unit="))


def _morreu(proc: subprocess.Popen[bytes], segundos: float = 5.0) -> bool:
    limite = time.monotonic() + segundos
    while proc.poll() is None:
        if time.monotonic() > limite:
            return False
        time.sleep(0.02)
    return True


@pytest.fixture
def gerenciador(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[_GerenciadorDeMentira]:
    """O teclado na tela, de dentro do serviço, com o gerenciador de mentira."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    (tmp_path / "run").mkdir()
    monkeypatch.setattr(teclado, "_OSK_CANDIDATES", (_DUBLE,))
    monkeypatch.setattr(teclado, "_osk_candidatos", lambda: (_DUBLE,))
    monkeypatch.setattr(teclado, "_OSK_SPAWN_ARGS", {_DUBLE: [_DUBLE, "600"]})
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.keyboard.shutil.which",
        lambda nome: f"/usr/bin/{nome}" if nome == _DUBLE else None,
    )
    monkeypatch.setattr(teclado, "_OSK_SONDA", [(float("-inf"), False)])
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.desktop_notifications."
        "notify_teclado_na_tela_aberto",
        lambda: True,
    )

    def _popen_proibido(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("o teclado nasceu por Popen de dentro do serviço")

    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.keyboard.subprocess.Popen", _popen_proibido
    )
    ger = _GerenciadorDeMentira(tmp_path / "cgroup")
    monkeypatch.setattr(fds, "RAIZ_DO_CGROUP", str(ger.raiz))
    monkeypatch.setattr(fds, "contexto_atual", lambda **_k: _DENTRO_DO_SERVICO)
    monkeypatch.setattr(fds, "_executar_de_verdade", ger)
    try:
        yield ger
    finally:
        if ger.segurar is not None:
            ger.segurar.set()
        for proc in ger.nascidos:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                proc.kill()
            with contextlib.suppress(Exception):
                proc.wait(timeout=5)


def test_o_teclado_nasce_numa_unidade_e_o_pid_vem_dela(
    gerenciador: _GerenciadorDeMentira,
) -> None:
    """Prova 1 da sprint, em bancada: a linha é a do dono, e o PID é o da unidade."""
    ctrl = teclado._OSKController()
    ctrl.open()
    assert len(gerenciador.chamadas) == 1
    cmd = gerenciador.chamadas[0]
    assert cmd[:2] == ["systemd-run", "--user"]
    assert "--property=OOMScoreAdjust=100" in cmd
    assert _unidade_de(cmd).startswith(f"{fds.PREFIXO_DA_UNIDADE}{_DUBLE}-")
    assert cmd[cmd.index("--") + 1 :] == [_DUBLE, "600"]
    assert ctrl._process is None, "o daemon não segura o processo do systemd-run"
    assert ctrl.aberto() is True
    sessao = json.loads(teclado._sessao_do_teclado().read_text(encoding="utf-8"))
    assert sessao["pid"] == gerenciador.nascidos[0].pid, (
        "o PID anotado não é o do teclado — o do systemd-run não fecharia nada")
    assert sessao["unidade"] == _unidade_de(cmd)


def test_sem_o_arquivo_de_sessao_a_unidade_responde(
    gerenciador: _GerenciadorDeMentira, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem ``XDG_RUNTIME_DIR`` gravável o arquivo de sessão não nasce, e o"""
    monkeypatch.setattr(teclado, "_gravar_sessao", lambda *_a, **_k: None)
    ctrl = teclado._OSKController()
    ctrl.open()
    assert ctrl.aberto() is True
    ctrl.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    assert ctrl.esperar_os_toques(5.0)
    assert _morreu(gerenciador.nascidos[0]), "o L3 não fechou o teclado da unidade"
    assert len(gerenciador.chamadas) == 1, "o L3 abriu um segundo teclado"


def test_o_r3_fecha_o_teclado_da_unidade(gerenciador: _GerenciadorDeMentira) -> None:
    """Fechar pelo PID que a unidade deu, e não por nome."""
    ctrl = teclado._OSKController()
    ctrl.open()
    ctrl.close()
    assert _morreu(gerenciador.nascidos[0]), "o R3 não fechou o teclado da unidade"
    gerenciador.recolher(_unidade_de(gerenciador.chamadas[0]))
    assert ctrl.aberto() is False
    assert not teclado._sessao_do_teclado().exists()


def test_o_r3_fecha_o_teclado_e_nao_o_vizinho_da_unidade(
    gerenciador: _GerenciadorDeMentira,
) -> None:
    """Na unidade pode haver mais de um processo; o R3 fecha o que tem o nome"""
    ctrl = teclado._OSKController()
    ctrl.open()
    teclado_de_pe = gerenciador.nascidos[0]
    vizinho = _POPEN_DE_VERDADE(
        ["tail", "-f", "/dev/null"], stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )
    gerenciador.nascidos.append(vizinho)
    procs = gerenciador.pasta(_unidade_de(gerenciador.chamadas[0])) / "cgroup.procs"
    procs.write_text(f"{vizinho.pid}\n{teclado_de_pe.pid}\n", encoding="utf-8")
    ctrl.close()
    assert _morreu(teclado_de_pe), "o R3 não fechou o teclado da unidade"
    assert vizinho.poll() is None, "o R3 fechou o vizinho no lugar do teclado"


def test_o_teclado_fechado_por_fora_faz_o_l3_abrir_de_novo(
    gerenciador: _GerenciadorDeMentira,
) -> None:
    """Ela fechou o teclado; a unidade esvaziou; o L3 abre, e não «fecha» o morto."""
    ctrl = teclado._OSKController()
    ctrl.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    assert ctrl.esperar_os_toques(5.0)
    primeiro = gerenciador.nascidos[0]
    os.kill(primeiro.pid, signal.SIGTERM)
    assert _morreu(primeiro)
    gerenciador.recolher(_unidade_de(gerenciador.chamadas[0]))

    ctrl.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    assert ctrl.esperar_os_toques(5.0)
    assert len(gerenciador.chamadas) == 2, "o L3 não abriu de novo"
    assert ctrl.aberto() is True


def test_a_parada_nao_deixa_teclado_sem_dono(gerenciador: _GerenciadorDeMentira) -> None:
    """Um L3 na fila não abre o teclado DEPOIS da parada do daemon."""
    gerenciador.segurar = threading.Event()
    ctrl = teclado._OSKController()
    ctrl.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    limite = time.monotonic() + 5.0
    while not gerenciador.chamadas and time.monotonic() < limite:
        time.sleep(0.01)
    assert gerenciador.chamadas, "o primeiro L3 nem chegou ao gerenciador"
    ctrl.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    ctrl.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    parada = threading.Thread(target=ctrl.close)
    parada.start()
    limite = time.monotonic() + 5.0
    while ctrl._fio._fila and time.monotonic() < limite:
        time.sleep(0.02)
    gerenciador.segurar.set()
    parada.join(10.0)
    assert not parada.is_alive()
    assert ctrl.esperar_os_toques(5.0)
    assert len(gerenciador.chamadas) == 1, (
        f"um toque da fila correu depois da parada: {len(gerenciador.chamadas)} aberturas")
    assert all(_morreu(p) for p in gerenciador.nascidos), "ficou teclado de pé"


def test_a_parada_espera_o_toque_que_ja_saiu_da_fila(
    gerenciador: _GerenciadorDeMentira, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O toque que o fio já tirou da fila termina antes de a parada fechar."""
    ctrl = teclado._OSKController()
    atender = ctrl._atender
    saiu_da_fila = threading.Event()

    def _perde_a_vez(token: str) -> None:
        saiu_da_fila.set()
        time.sleep(0.5)
        atender(token)

    monkeypatch.setattr(ctrl, "_atender", _perde_a_vez)
    ctrl.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    assert saiu_da_fila.wait(5.0)
    ctrl.close()
    assert ctrl.esperar_os_toques(5.0)
    assert len(gerenciador.chamadas) == 1
    assert all(_morreu(p) for p in gerenciador.nascidos), (
        "o toque abriu o teclado depois da parada, e ninguém o fecha")


_DEMORA_DO_GERENCIADOR_S = 2.0
_TIQUE_S = _DEMORA_DO_GERENCIADOR_S / 4


def test_o_l3_nao_segura_o_laco(gerenciador: _GerenciadorDeMentira) -> None:
    """Com o gerenciador lento, o toque volta na hora."""
    gerenciador.demora_s = _DEMORA_DO_GERENCIADOR_S
    ctrl = teclado._OSKController()
    t0 = time.monotonic()
    ctrl.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    assert time.monotonic() - t0 < _TIQUE_S, "o L3 segurou o laço até o systemd-run voltar"
    assert ctrl.esperar_os_toques(5.0)
    assert ctrl.aberto() is True


def _daemon_do_ps() -> Any:
    return SimpleNamespace(
        config=SimpleNamespace(ps_button_action="steam", ps_button_command=[]),
        _emulation_suppressed=False,
        store=SimpleNamespace(native_mode_active=False),
        _keyboard_device=None,
    )


@pytest.fixture
def steam_lenta(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _GerenciadorDeMentira:
    """A Steam fechada, e o gerenciador lento. Nada nasce."""
    ger = _GerenciadorDeMentira(tmp_path / "cgroup", nascer=False)
    ger.demora_s = _DEMORA_DO_GERENCIADOR_S
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.steam_launcher.shutil.which",
        lambda n: f"/usr/bin/{n}",
    )
    monkeypatch.setattr(
        steam_launcher, "_default_pgrep",
        lambda cmd: subprocess.CompletedProcess(cmd, 1, stdout="", stderr=""),
    )
    monkeypatch.setattr(fds, "contexto_atual", lambda **_k: _DENTRO_DO_SERVICO)
    monkeypatch.setattr(fds, "_executar_de_verdade", ger)
    return ger


def test_o_ps_nao_segura_o_laco(steam_lenta: _GerenciadorDeMentira) -> None:
    """A régua do achado 9 da auditoria, pelo detector de verdade."""
    gesto = hotkey.build_ps_solo_callback(_daemon_do_ps())
    mgr = HotkeyManager(on_ps_solo=gesto, config=HotkeyConfig(buffer_ms=0))
    mgr.observe(["ps"], now=0.0)
    tiques: list[float] = []
    for i in range(10):
        t0 = time.monotonic()
        mgr.observe([], now=0.1 + i * 0.016)
        tiques.append(time.monotonic() - t0)
    assert max(tiques) < _TIQUE_S, f"um tique esperou o gerenciador: {tiques}"
    assert gesto.esperar(5.0)
    assert len(steam_lenta.chamadas) == 1
    cmd = steam_lenta.chamadas[0]
    assert cmd[:2] == ["systemd-run", "--user"]
    assert cmd[cmd.index("--") + 1 :] == ["steam"]


def test_o_segundo_ps_com_o_primeiro_em_voo_nao_abre_outra_steam(
    steam_lenta: _GerenciadorDeMentira,
) -> None:
    """Um toque em voo por vez: o segundo, com a Steam ainda nascendo, sai."""
    gesto = hotkey.build_ps_solo_callback(_daemon_do_ps())
    gesto()
    gesto()
    assert gesto.esperar(5.0)
    assert len(steam_lenta.chamadas) == 1


def test_um_pedido_que_levanta_nao_trava_o_fio() -> None:
    """Um toque que levanta não pode deixar o fio «ocupado» para sempre."""
    avisos: list[str] = []
    fio = fds.FioDeTrabalho("hefesto-teste", ao_falhar=lambda e: avisos.append(str(e)))

    def _levanta() -> None:
        raise RuntimeError("o gerenciador caiu")

    assert fio.disparar(_levanta)
    assert fio.esperar(5.0)
    feitos: list[int] = []
    assert fio.disparar(lambda: feitos.append(1))
    assert fio.esperar(5.0)
    assert feitos == [1]
    assert avisos == ["o gerenciador caiu"]


def test_a_fila_do_fio_guarda_a_ordem() -> None:
    """Com ``espera``, os pedidos correm na ordem em que chegaram."""
    solta = threading.Event()
    ordem: list[int] = []
    fio = fds.FioDeTrabalho("hefesto-teste", espera=3)
    def _primeiro() -> None:
        solta.wait(5.0)
        ordem.append(0)

    assert fio.disparar(_primeiro)
    for i in (1, 2, 3):
        assert fio.disparar(functools.partial(ordem.append, i))
    assert not fio.disparar(lambda: ordem.append(9)), "a fila passou do tamanho"
    solta.set()
    assert fio.esperar(5.0)
    assert ordem == [0, 1, 2, 3]


def test_pids_da_unidade_pelo_proc_quando_a_fatia_e_outra(tmp_path: Path) -> None:
    """Sem a pasta da unidade onde se espera, o ``/proc`` de cada processo responde."""
    proc = tmp_path / "proc"
    (proc / "self").mkdir(parents=True)
    (proc / "self" / "cgroup").write_text(
        "0::/user.slice/user-1000.slice/user@1000.service/app.slice/"
        "hefesto-dualsense4unix.service\n", encoding="utf-8")
    unidade = fds.nome_da_unidade("wvkbd-mobintl", "de-mentira")
    for pid, caminho in ((4321, f"outra.slice/{unidade}"), (4322, "app.slice/x.service")):
        (proc / str(pid)).mkdir()
        (proc / str(pid) / "cgroup").write_text(
            f"0::/user.slice/user-1000.slice/user@1000.service/{caminho}\n",
            encoding="utf-8")
    vazio = tmp_path / "cgroup"
    vazio.mkdir()
    assert fds.pids_da_unidade(unidade, raiz_cgroup=str(vazio), raiz_proc=str(proc)) == (4321,)


def test_pids_da_unidade_no_cgroup_v1(tmp_path: Path) -> None:
    """Numa máquina só com o cgroup v1 não há linha ``0::``: quem diz a"""
    proc = tmp_path / "proc"
    (proc / "self").mkdir(parents=True)
    fatia = "/user.slice/user-1000.slice/user@1000.service/app.slice"
    (proc / "self" / "cgroup").write_text(
        "4:memory:/user.slice/user-1000.slice/user@1000.service\n"
        f"1:name=systemd:{fatia}/hefesto-dualsense4unix.service\n", encoding="utf-8")
    unidade = fds.nome_da_unidade("wvkbd-mobintl", "de-mentira")
    for pid, ultimo in ((4321, unidade), (4322, "x.service")):
        (proc / str(pid)).mkdir()
        (proc / str(pid) / "cgroup").write_text(
            "4:memory:/user.slice/user-1000.slice/user@1000.service\n"
            f"1:name=systemd:{fatia}/{ultimo}\n", encoding="utf-8")
    vazio = tmp_path / "cgroup"
    vazio.mkdir()
    assert fds.pids_da_unidade(unidade, raiz_cgroup=str(vazio), raiz_proc=str(proc)) == (4321,)


def test_pids_da_unidade_so_para_nome_nosso(tmp_path: Path) -> None:
    """Um nome que não é de ``nome_da_unidade`` não vira caminho de arquivo, nem"""
    proc = tmp_path / "proc"
    (proc / "self").mkdir(parents=True)
    servico = (
        "0::/user.slice/user-1000.slice/user@1000.service/app.slice/"
        "hefesto-dualsense4unix.service\n"
    )
    (proc / "self" / "cgroup").write_text(servico, encoding="utf-8")
    (proc / "4321").mkdir()
    (proc / "4321" / "cgroup").write_text(servico, encoding="utf-8")
    vazio = tmp_path / "cgroup"
    vazio.mkdir()
    for nome in ("hefesto-dualsense4unix.service", "app-hefesto-../../etc", ""):
        assert fds.pids_da_unidade(nome, raiz_cgroup=str(vazio), raiz_proc=str(proc)) == ()
