"""O Wine que a Steam roda para preparar um jogo não é o jogo e não abre a cena de jogo.

D-0311-QUEM-NAO-E-JOGO-NAO-SEGURA-MOTOR: só o processo de jogo que segura o nó do pad conta. O
`winedevice.exe` neto do reaper do avaliador do script de instalação (`Install=1`) roda com o
`STEAM_COMPAT_DATA_PATH` do prefixo; a assinatura no ambiente o aprovava antes de a pergunta pelo
reaper ser feita.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems.game_signal import classify
from hefesto_dualsense4unix.integrations import quem_segura_o_pad as qsp
from hefesto_dualsense4unix.integrations.quem_o_jogo_le import por_que_conta

MEU_PID = 4242
AVALIADOR = "/x/reaper SteamLaunch AppId=9924420 Install=1 -- /x/proton waitforexitandrun /x/s.exe"
REAPER_DO_JOGO = "/x/reaper SteamLaunch AppId=9924420 -- /x/proton waitforexitandrun /x/jogo.exe"
PREFIXO = {"STEAM_COMPAT_DATA_PATH": "/home/u/.steam/compatdata/9924420"}
MOTIVO_DO_AVALIADOR = "o avaliador do script de instalação da Steam"
FRASE = "o Wine do avaliador da Steam não é jogo"

SEM_OUTRA_EVIDENCIA: dict[str, Any] = {
    "window_healthy": True,
    "window_class_current": "cosmic-files",
    "window_seen_age": None,
    "profile_rule_match": False,
    "marker": None,
    "marker_pid_alive": False,
    "exit_marker": None,
    "session_open": True,
    "now": 0.0,
}


class Proc:
    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self.no = raiz / "dev" / "event7"
        self.no.parent.mkdir(parents=True)
        self.no.write_bytes(b"")
        (raiz / "proc").mkdir()

    @property
    def proc(self) -> str:
        return str(self.raiz / "proc")

    def processo(
        self,
        pid: int,
        comm: str,
        cmdline: str,
        *,
        pai: int = 1,
        ambiente: dict[str, str] | None = None,
        segura: bool = False,
    ) -> int:
        pasta = self.raiz / "proc" / str(pid)
        (pasta / "fd").mkdir(parents=True)
        (pasta / "comm").write_text(comm + "\n")
        (pasta / "cmdline").write_bytes(cmdline.replace(" ", "\0").encode() + b"\0")
        (pasta / "stat").write_text(f"{pid} ({comm}) S {pai} {pid} {pid} 0\n")
        (pasta / "environ").write_bytes(
            b"".join(f"{k}={v}".encode() + b"\0" for k, v in (ambiente or {}).items())
        )
        if segura:
            (pasta / "fd" / "3").symlink_to(self.no)
        return pid

    def libera(self, pid: int) -> None:
        (self.raiz / "proc" / str(pid) / "fd" / "3").unlink()

    def por_que(self, pid: int, nome: str, cmdline: str) -> tuple[bool, str]:
        return por_que_conta(nome, cmdline, pid=pid, meu_pid=MEU_PID, raiz_proc=self.proc)

    def jogos(self) -> dict[str, Any]:
        pad = SimpleNamespace(mac="aa:bb:cc:00:00:01", name="pad (Hefesto)")
        ino = self.no.stat().st_ino

        def resolvedor(**_kw: Any) -> dict[str, Any]:
            return {"evdev": str(self.no), "ino": ino}

        return qsp.jogos_por_pad(
            {"p1": pad},
            raiz_proc=self.proc,
            resolver=resolvedor,
            raiz_dev=str(self.raiz / "dev"),
            meu_pid=MEU_PID,
        )


@pytest.fixture
def proc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Proc:
    monkeypatch.setattr(qsp, "_APROVADOS_NO_DIARIO", {})
    return Proc(tmp_path)


@pytest.fixture
def diario(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    registros: list[dict[str, Any]] = []
    monkeypatch.setattr(
        qsp.logger, "info", lambda evento, **kw: registros.append({"evento": evento, **kw})
    )
    return registros


def _avaliador(proc: Proc) -> int:
    proc.processo(100, "reaper", AVALIADOR)
    proc.processo(101, "proton", "/x/proton waitforexitandrun /x/setup.exe", pai=100)
    return proc.processo(
        102, "winedevice.exe", "C:\\windows\\system32\\winedevice.exe", pai=101,
        ambiente=PREFIXO, segura=True,
    )


def _partida(proc: Proc) -> int:
    proc.processo(200, "reaper", REAPER_DO_JOGO)
    proc.processo(201, "proton", "/x/proton waitforexitandrun /x/jogo.exe", pai=200)
    return proc.processo(
        202, "winedevice.exe", "C:\\windows\\system32\\winedevice.exe", pai=201,
        ambiente=PREFIXO, segura=True,
    )


def test_o_wine_neto_do_avaliador_do_install_script_nao_e_jogo(proc: Proc) -> None:
    pid = _avaliador(proc)
    assert proc.por_que(pid, "winedevice.exe", "winedevice.exe") == (
        False,
        MOTIVO_DO_AVALIADOR,
    ), FRASE


def test_o_wine_neto_do_reaper_sem_install_e_jogo(proc: Proc) -> None:
    pid = _partida(proc)
    assert proc.por_que(pid, "winedevice.exe", "winedevice.exe") == (
        True,
        "STEAM_COMPAT_DATA_PATH no ambiente",
    )


def test_o_wine_sem_reaper_com_umu_id_e_jogo(proc: Proc) -> None:
    pid = proc.processo(
        300, "winedevice.exe", "winedevice.exe", ambiente={"UMU_ID": "umu-0"}, segura=True
    )
    assert proc.por_que(pid, "winedevice.exe", "winedevice.exe") == (True, "UMU_ID no ambiente")


def test_o_wine_sem_assinatura_nem_reaper_segue_pelo_nome(proc: Proc) -> None:
    pid = proc.processo(301, "winedevice.exe", "winedevice.exe", segura=True)
    assert proc.por_que(pid, "winedevice.exe", "winedevice.exe") == (True, "o Wine")


def test_o_reaper_mais_perto_decide_quando_ha_mais_de_um_acima(proc: Proc) -> None:
    proc.processo(400, "reaper", AVALIADOR)
    proc.processo(401, "reaper", REAPER_DO_JOGO, pai=400)
    pid = proc.processo(402, "winedevice.exe", "winedevice.exe", pai=401, ambiente=PREFIXO)
    assert proc.por_que(pid, "winedevice.exe", "winedevice.exe")[0] is True
    proc.processo(410, "reaper", REAPER_DO_JOGO)
    proc.processo(411, "reaper", AVALIADOR, pai=410)
    pid = proc.processo(412, "winedevice.exe", "winedevice.exe", pai=411, ambiente=PREFIXO)
    assert proc.por_que(pid, "winedevice.exe", "winedevice.exe") == (False, MOTIVO_DO_AVALIADOR)


def test_o_pad_segurado_so_pelo_wine_do_avaliador_fica_sem_jogo_e_sem_cena(
    proc: Proc, diario: list[dict[str, Any]]
) -> None:
    _avaliador(proc)
    por_pad = proc.jogos()
    assert por_pad == {}, FRASE
    segurador = next(iter(por_pad.values()), None)
    veredito = classify(
        **SEM_OUTRA_EVIDENCIA, processo_no_pad=segurador.nome if segurador else None
    )
    assert veredito == "daemon", FRASE
    assert diario == []


def test_o_pad_segurado_pelo_wine_da_partida_abre_a_cena_e_diz_o_motivo_uma_vez(
    proc: Proc, diario: list[dict[str, Any]]
) -> None:
    pid = _partida(proc)
    for _ in range(2):
        por_pad = proc.jogos()
        assert por_pad["p1"].pid == pid
    segurador = por_pad["p1"]
    assert classify(**SEM_OUTRA_EVIDENCIA, processo_no_pad=segurador.nome) == "game"
    assert diario == [
        {
            "evento": "pad_segurado_por_jogo",
            "pad": "p1",
            "processo": "winedevice.exe",
            "pid": pid,
            "motivo": "STEAM_COMPAT_DATA_PATH no ambiente",
        }
    ]


def test_o_registro_volta_quando_o_jogo_larga_o_pad_e_volta(
    proc: Proc, diario: list[dict[str, Any]]
) -> None:
    pid = _partida(proc)
    proc.jogos()
    proc.libera(pid)
    assert proc.jogos() == {}
    (proc.raiz / "proc" / str(pid) / "fd" / "3").symlink_to(proc.no)
    proc.jogos()
    assert [r["pid"] for r in diario] == [pid, pid]


def test_o_registro_muda_com_o_processo_que_segura(
    proc: Proc, diario: list[dict[str, Any]]
) -> None:
    primeiro = _partida(proc)
    proc.jogos()
    proc.libera(primeiro)
    outro = proc.processo(
        500, "forja", "/opt/a-forja/forja", segura=True
    )
    assert proc.jogos()["p1"].pid == outro
    assert [(r["processo"], r["motivo"]) for r in diario] == [
        ("winedevice.exe", "STEAM_COMPAT_DATA_PATH no ambiente"),
        ("forja", "aplicativo aberto que lê o controle"),
    ]


def _quatro_pads(proc: Proc) -> tuple[dict[str, Any], dict[str, Path]]:
    pads: dict[str, Any] = {}
    nos: dict[str, Path] = {}
    for n in range(1, 5):
        no = proc.raiz / "dev" / f"event{20 + n}"
        no.write_bytes(b"")
        mac = f"aa:bb:cc:00:00:0{n}"
        pads[f"p{n}"] = SimpleNamespace(mac=mac, name="pad (Hefesto)")
        nos[mac] = no
    return pads, nos


def _jogos_dos_quatro(proc: Proc, pads: dict[str, Any], nos: dict[str, Path]) -> dict[str, Any]:
    def resolvedor(*, uniq: str, **_kw: Any) -> dict[str, Any]:
        return {"evdev": str(nos[uniq]), "ino": nos[uniq].stat().st_ino}

    return qsp.jogos_por_pad(
        pads,
        raiz_proc=proc.proc,
        resolver=resolvedor,
        raiz_dev=str(proc.raiz / "dev"),
        meu_pid=MEU_PID,
    )


def _segura_os_quatro(proc: Proc, pid: int, nos: dict[str, Path]) -> None:
    for fd, no in enumerate(nos.values(), start=10):
        (proc.raiz / "proc" / str(pid) / "fd" / str(fd)).symlink_to(no)


def test_os_quatro_pads_segurados_pelo_wine_do_avaliador_ficam_sem_jogo(
    proc: Proc, diario: list[dict[str, Any]]
) -> None:
    pads, nos = _quatro_pads(proc)
    pid = _avaliador(proc)
    _segura_os_quatro(proc, pid, nos)
    assert _jogos_dos_quatro(proc, pads, nos) == {}, FRASE
    assert diario == []


def test_os_quatro_pads_da_partida_dizem_o_motivo_uma_vez_cada_e_o_que_sai_volta_sozinho(
    proc: Proc, diario: list[dict[str, Any]]
) -> None:
    pads, nos = _quatro_pads(proc)
    pid = _partida(proc)
    _segura_os_quatro(proc, pid, nos)
    for _ in range(2):
        assert sorted(_jogos_dos_quatro(proc, pads, nos)) == ["p1", "p2", "p3", "p4"]
    assert sorted(r["pad"] for r in diario) == ["p1", "p2", "p3", "p4"]
    (proc.raiz / "proc" / str(pid) / "fd" / "12").unlink()
    assert sorted(_jogos_dos_quatro(proc, pads, nos)) == ["p1", "p2", "p4"]
    (proc.raiz / "proc" / str(pid) / "fd" / "12").symlink_to(nos["aa:bb:cc:00:00:03"])
    _jogos_dos_quatro(proc, pads, nos)
    assert [r["pad"] for r in diario[4:]] == ["p3"]
