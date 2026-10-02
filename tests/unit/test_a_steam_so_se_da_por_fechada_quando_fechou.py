"""A-STEAM-SO-SE-DA-POR-FECHADA-QUANDO-FECHOU-01 — as réguas.

MEDIDO ANTES (01/10/2026), com um dublê do `pgrep` que tem a semântica do real
sobre a tabela da Steam dela (o cliente em `ubuntu12_32/steam`, que o `-f
steamrt64/steam` não casa, e o webhelper que o cliente relança ~9 s depois de
morto, como no diário dela): o `stop_steam` da árvore-base devolveu `True` em
35 s com o cliente vivo, e o fallback mandou `pkill -TERM -x steamwebhelper`,
pelo NOME e em qualquer `HOME`.

AQUI O `/proc` É DE MENTIRA: cada processo é uma pasta com `status`, `comm`,
`cmdline`, `environ` e `stat`, do usuário que roda a régua. O sinal, a espera e
o `steam -shutdown` são dublês: nada aqui toca a Steam de quem roda.
"""

from __future__ import annotations

import os
import signal
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl
from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.integrations import steam_launcher

CLIENTE = 100
WEBHELPER = 101


class Mesa:
    """O `/proc` de mentira, com um relógio e as regras da Steam dela."""

    def __init__(self, raiz: Path, lar: Path) -> None:
        self.raiz = raiz
        self.lar = lar
        self.agora = 0.0
        self.sinais: list[tuple[int, int]] = []
        self.abertos: list[list[str]] = []
        #: O cliente que nenhum sinal derruba (o caso medido: o KILL não o achou).
        self.cliente_teimoso = False
        #: Em quantos segundos o cliente relança o webhelper morto.
        self.volta_do_webhelper: float | None = None
        self._morto_em: float | None = None
        raiz.mkdir(parents=True, exist_ok=True)

    def processo(self, pid: int, comm: str, argv: list[str], *, lar: Path | None = None,
                 inicio: str = "4242", uid: int | None = None) -> None:
        pasta = self.raiz / str(pid)
        pasta.mkdir(parents=True, exist_ok=True)
        dono = os.getuid() if uid is None else uid
        (pasta / "status").write_text(f"Name:\t{comm}\nUid:\t{dono}\t{dono}\t{dono}\t{dono}\n")
        (pasta / "comm").write_text(comm + "\n")
        (pasta / "cmdline").write_bytes("\0".join(argv).encode() + b"\0")
        casa = self.lar if lar is None else lar
        (pasta / "environ").write_bytes(f"PATH=/usr/bin\0HOME={casa}\0".encode())
        campos = ["S"] + ["0"] * 18 + [inicio] + ["0"] * 5
        (pasta / "stat").write_text(f"{pid} ({comm}) " + " ".join(campos) + "\n")

    def a_steam_dela(self, *, lar: Path | None = None) -> None:
        self.processo(CLIENTE, "steam",
                      ["/x/.steam/debian-installation/ubuntu12_32/steam", "-srt-logger-opened"],
                      lar=lar)
        self.webhelper(lar=lar)

    def webhelper(self, *, lar: Path | None = None) -> None:
        self.processo(WEBHELPER, "steamwebhelper",
                      ["./steamwebhelper", f"-steampid={CLIENTE}", "-lang=pt"], lar=lar)

    def morre(self, pid: int) -> None:
        for arq in (self.raiz / str(pid)).glob("*"):
            arq.unlink()
        (self.raiz / str(pid)).rmdir()

    # -- os dublês que o `stop_steam` recebe ---------------------------------
    def dormir(self, s: float) -> None:
        self.agora += s
        if (self._morto_em is not None and self.volta_do_webhelper is not None
                and self.agora >= self._morto_em + self.volta_do_webhelper
                and (self.raiz / str(CLIENTE)).exists()):
            self.webhelper()
            self._morto_em = None

    def sinalizar(self, pid: int, sig: int) -> None:
        self.sinais.append((pid, sig))
        if not (self.raiz / str(pid)).exists():
            raise ProcessLookupError(pid)
        if pid == CLIENTE and self.cliente_teimoso:
            return
        if pid == WEBHELPER:
            self._morto_em = self.agora
        self.morre(pid)

    def abrir(self, argv: list[str], **_k: Any) -> object:
        self.abertos.append(list(argv))
        return object()


@pytest.fixture
def mesa(tmp_path: Path) -> Mesa:
    lar = tmp_path / "lar"
    lar.mkdir()
    return Mesa(tmp_path / "proc", lar)


def _parar(mesa: Mesa) -> bool:
    return slo.stop_steam(proc=mesa.raiz, lar=mesa.lar, dormir=mesa.dormir,
                          sinalizar=mesa.sinalizar, abrir=mesa.abrir)


# ---------------------------------------------------------------------------
# 1 · «Fechada» só quando fechou
# ---------------------------------------------------------------------------
def test_o_stop_steam_nao_diz_fechada_com_o_cliente_vivo(mesa: Mesa) -> None:
    """O caso medido: o cliente fica, e o webhelper volta 9 s depois de morto.
    ARRANQUE o ramo do cliente do `processos_da_steam` e este teste reprova: a
    conferência cai na janela sem webhelper e diz «fechada» com a Steam de pé
    — o `True` que a árvore-base devolveu em 35 s."""
    mesa.a_steam_dela()
    mesa.cliente_teimoso = True
    mesa.volta_do_webhelper = 9.0
    assert _parar(mesa) is False
    assert (mesa.raiz / str(CLIENTE)).exists()


def test_o_fechar_tira_a_steam_inteira_pelo_pid(mesa: Mesa) -> None:
    """A Steam que não atende o `-shutdown` sai pelo PID, o cliente primeiro,
    e o `True` só vem com os dois fora."""
    mesa.a_steam_dela()
    assert _parar(mesa) is True
    assert mesa.sinais[:2] == [(CLIENTE, signal.SIGTERM), (WEBHELPER, signal.SIGTERM)]
    assert not any(mesa.raiz.iterdir())


def test_com_o_home_trocado_nenhum_processo_leva_sinal(mesa: Mesa, tmp_path: Path) -> None:
    """A Steam de outro `HOME` (a suíte, o `sudo`) não é de quem pede: nem
    `-shutdown`, nem sinal. ARRANQUE a pergunta do lar (`do_meu_lar`) e este
    teste reprova — o fallback mataria a Steam dela."""
    mesa.a_steam_dela(lar=tmp_path / "home-dela")
    assert _parar(mesa) is True
    assert mesa.sinais == []
    assert mesa.abertos == []
    assert (mesa.raiz / str(WEBHELPER)).exists()


def test_o_pid_reciclado_nao_leva_o_tiro(mesa: Mesa, monkeypatch: pytest.MonkeyPatch) -> None:
    """Entre a leitura e o sinal o pid pode ter virado outro processo: o tiro
    só sai com a mesma hora de nascimento. ARRANQUE a conferência do `inicio`
    e este teste reprova."""
    mesa.processo(CLIENTE, "steam", ["/x/ubuntu12_32/steam"], inicio="novo")
    velho = slo.ProcessoDaSteam(CLIENTE, "cliente", str(mesa.lar), "velho")
    monkeypatch.setattr(slo, "steam_deste_lar", lambda *a, **k: [velho])
    _parar(mesa)
    assert mesa.sinais == []


def test_o_cliente_se_acha_pelo_steampid_do_webhelper(mesa: Mesa) -> None:
    """O cliente num caminho que não é o do runtime (o flatpak, por exemplo)
    se acha pelo `-steampid=` que o webhelper carrega. ARRANQUE essa leitura
    e o cliente some da conta."""
    mesa.processo(CLIENTE, "steam", ["/app/bin/steam-wrapper"])
    mesa.webhelper()
    papeis = {x.pid: x.papel for x in slo.processos_da_steam(mesa.raiz)}
    assert papeis == {CLIENTE: "cliente", WEBHELPER: "webhelper"}


def test_o_lar_e_o_usuario_se_conferem(mesa: Mesa, tmp_path: Path) -> None:
    """Deste lar: o mesmo usuário e o mesmo `HOME` (ou um dentro dele, a Snap)."""
    mesa.processo(200, "heroic", ["heroic"])
    mesa.processo(201, "heroic", ["heroic"], lar=tmp_path / "outro")
    mesa.processo(202, "steam", ["steam"], lar=mesa.lar / "snap/steam/common")
    mesa.processo(203, "heroic", ["heroic"], uid=os.getuid() + 1)
    assert slo.e_deste_lar(200, mesa.raiz, mesa.lar)
    assert not slo.e_deste_lar(201, mesa.raiz, mesa.lar)
    assert slo.e_deste_lar(202, mesa.raiz, mesa.lar)
    assert not slo.e_deste_lar(203, mesa.raiz, mesa.lar)
    assert not slo.e_deste_lar(999, mesa.raiz, mesa.lar)


# ---------------------------------------------------------------------------
# 2 · Abrir e reabrir não põem uma segunda Steam por cima
# ---------------------------------------------------------------------------
def _sem_wmctrl(monkeypatch: pytest.MonkeyPatch, abertos: list[list[str]]) -> None:
    monkeypatch.setattr(steam_launcher.shutil, "which",
                        lambda n: None if n == "wmctrl" else f"/usr/bin/{n}")
    monkeypatch.setattr(steam_launcher, "_default_pgrep",
                        lambda cmd: __import__("subprocess").CompletedProcess(cmd, 0, "100\n", ""))
    monkeypatch.setattr(steam_launcher, "_spawn_steam",
                        lambda **_k: abertos.append(["steam"]) or True)


def test_sem_wmctrl_a_steam_de_outro_lar_nao_ganha_outra(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Sem `wmctrl` e com a Steam de pé num `HOME` que não é o de quem pede, o
    «abrir ou focar» não lança processo. ARRANQUE a pergunta do lar do
    `open_or_focus_steam` e este teste reprova: nasce um `steam` com este
    `HOME`, a segunda Steam que disputou o barramento em 29/09."""
    abertos: list[list[str]] = []
    _sem_wmctrl(monkeypatch, abertos)
    monkeypatch.setattr(slo, "processos_da_steam", lambda *a, **k: [
        slo.ProcessoDaSteam(CLIENTE, "cliente", str(tmp_path / "home-dela"), "1")])
    assert steam_launcher.open_or_focus_steam(
        which=lambda n: f"/usr/bin/{n}") is False
    assert abertos == []


def test_a_steam_deste_lar_na_bandeja_ainda_se_mostra(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Steam deste lar sem janela (na bandeja) ou sem `wmctrl`: o `steam`
    repassa o pedido a ela, que se mostra — é o PS da bandeja. Decisão de
    01/10 pelo padrão dela; sem isto o PS com a Steam aberta não faria nada."""
    abertos: list[list[str]] = []
    _sem_wmctrl(monkeypatch, abertos)
    monkeypatch.setattr(slo, "processos_da_steam", lambda *a, **k: [
        slo.ProcessoDaSteam(CLIENTE, "cliente", str(Path.home()), "1")])
    assert steam_launcher.open_or_focus_steam(which=lambda n: f"/usr/bin/{n}") is True
    assert abertos == [["steam"]]


def test_reabrir_com_a_steam_de_pe_nao_lanca_outra(monkeypatch: pytest.MonkeyPatch) -> None:
    """O cliente voltou sozinho (ou nunca fechou): o reabrir não repassa nada.
    ARRANQUE a pergunta do `reopen_steam` e este teste reprova."""
    pedidos: list[list[str]] = []
    monkeypatch.setattr(slo, "steam_running", lambda: True)
    monkeypatch.setattr(slo.fora_do_servico, "abrir",
                        lambda cmd, **_k: pedidos.append(list(cmd)))
    monkeypatch.setattr(slo.shutil, "which", lambda n: f"/usr/bin/{n}")
    assert slo.reopen_steam() is True
    assert pedidos == []


def test_a_foto_do_reiniciar_so_ve_o_lancador_deste_lar(monkeypatch: pytest.MonkeyPatch) -> None:
    """O «Reiniciar o serviço» só fecha (e reabre) o lançador deste lar.
    ARRANQUE o filtro do `pids_de` e este teste reprova: o Heroic de outro
    `HOME` levaria `SIGTERM`."""
    monkeypatch.setattr(rl, "_rodar", lambda argv: __import__("subprocess").CompletedProcess(
        argv, 0, "300\n301\n", ""))
    monkeypatch.setattr(rl, "_pids_de_flatpak", lambda app: [])
    monkeypatch.setattr(slo, "e_deste_lar", lambda pid, *a, **k: pid == 300)
    heroic = next(x for x in rl.LANCADORES if x.chave == "heroic")
    assert rl.pids_de(heroic) == [300]
