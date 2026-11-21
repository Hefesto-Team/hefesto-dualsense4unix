"""O-LACO-DE-AUDIO-MORRE-COM-A-JANELA-01: o `pw-loopback` não sobrevive à janela que o lançou.

O defeito, medido em 19/11/2026: `Lacos.ligar` lançava o `pw-loopback` sem prendê-lo ao pai, e a
única saída era o `atexit`. Com a janela morta por SIGKILL, o laço seguia levando o microfone à
saída, e a janela nova somava um segundo.

O instrumento é o `Lacos` do produto sobre um `pw-loopback` de mentira num PATH temporário (um
script que grava o próprio PID e dorme). A morte da janela é real: um processo filho do teste cria
o laço e leva SIGKILL. Nada aqui fala com o servidor de som, e a varredura de órfãos corre sempre
num `/proc` de mentira com um `matar` que só anota: nunca contra a máquina.
"""

from __future__ import annotations

import ast
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import laco_de_audio
from hefesto_dualsense4unix.integrations.laco_de_audio import Lacos, varrer_orfaos

FAMILIA = "teste-do-conjunto-som"
RAIZ = Path(__file__).resolve().parents[2]
P = 5_000_000


def _pw_loopback_de_mentira(pasta: Path) -> Path:
    """Um `pw-loopback` que grava o PID em `$PIDFILE` e dorme."""
    binario = pasta / "bin"
    binario.mkdir()
    script = binario / "pw-loopback"
    script.write_text('#!/bin/sh\necho $$ > "$PIDFILE"\nexec sleep 300\n', encoding="utf-8")
    script.chmod(0o755)
    return binario


def _vivo(pid: int) -> bool:
    try:
        estado = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rpartition(")")[2].split()[0]
    except OSError:
        return False
    return estado != "Z"


def _espera_morrer(pid: int, prazo_s: float = 5.0) -> bool:
    fim = time.monotonic() + prazo_s
    while time.monotonic() < fim:
        if not _vivo(pid):
            return True
        time.sleep(0.02)
    return not _vivo(pid)


def _pid_do_arquivo(arquivo: Path, prazo_s: float = 5.0) -> int:
    fim = time.monotonic() + prazo_s
    while time.monotonic() < fim:
        texto = arquivo.read_text(encoding="utf-8").strip() if arquivo.exists() else ""
        if texto:
            return int(texto)
        time.sleep(0.02)
    raise AssertionError("o pw-loopback de mentira não gravou o PID")


@pytest.fixture(autouse=True)
def _sem_familia_de_teste() -> Any:
    antes = list(laco_de_audio._FAMILIAS)
    yield
    laco_de_audio._FAMILIAS[:] = antes


@pytest.fixture()
def mesa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    binario = _pw_loopback_de_mentira(tmp_path)
    pidfile = tmp_path / "pid"
    monkeypatch.setenv("PATH", f"{binario}:{os.environ['PATH']}")
    monkeypatch.setenv("PIDFILE", str(pidfile))
    nascidos: list[int] = []
    yield pidfile, nascidos
    for pid in nascidos:
        if _vivo(pid):
            os.kill(pid, signal.SIGKILL)


def _sem_maquina(tmp_path: Path) -> tuple[Path, list[tuple[int, int]], Any]:
    """Um `/proc` vazio e um `matar` que só anota: a varredura do `Lacos` sem tocar a máquina."""
    raiz = tmp_path / "proc-vazio"
    raiz.mkdir()
    sinais: list[tuple[int, int]] = []
    return raiz, sinais, lambda pid, sinal: sinais.append((pid, sinal))


def test_a_janela_que_leva_sigkill_leva_o_laco_junto(tmp_path: Path, mesa: Any) -> None:
    """D-2011-O-LACO-DE-AUDIO-MORRE-COM-A-JANELA: o laço cai com a janela que levou SIGKILL."""
    pidfile, nascidos = mesa
    codigo = (
        "import os, signal, sys\n"
        "from pathlib import Path\n"
        "from hefesto_dualsense4unix.integrations.laco_de_audio import Lacos\n"
        "lacos = Lacos(sys.argv[1], raiz=Path(sys.argv[2]), matar=lambda pid, sinal: None)\n"
        "assert lacos.ligar('a1', captura='mic')\n"
        "os.kill(os.getpid(), signal.SIGKILL)\n"
    )
    proc_vazio = _sem_maquina(tmp_path)[0]
    casa = tmp_path / "casa"
    casa.mkdir()
    ambiente = {
        **os.environ,
        "PYTHONPATH": str(RAIZ / "src"),
        "HOME": str(casa),
        "XDG_STATE_HOME": str(casa / "state"),
        "XDG_CONFIG_HOME": str(casa / "config"),
    }
    janela = subprocess.run(
        [sys.executable, "-c", codigo, FAMILIA, str(proc_vazio)], env=ambiente, timeout=60,
        check=False,
        capture_output=True)
    assert janela.returncode == -signal.SIGKILL, janela.stderr.decode()[-400:]

    pid = _pid_do_arquivo(pidfile)
    nascidos.append(pid)
    assert _espera_morrer(pid), "o pw-loopback seguiu vivo depois da janela morrer"


def test_o_laco_ligado_de_um_gesto_passageiro_continua_de_pe(tmp_path: Path, mesa: Any) -> None:
    """MORDIDA: lançar do fio do gesto mata o laço quando o gesto acaba.

    O `PR_SET_PDEATHSIG` dispara na morte do fio que fez o fork. Os gestos da janela correm cada um
    num fio que acaba com o gesto; o laço tem de nascer de um fio que vive com o processo.
    """
    pidfile, nascidos = mesa
    proc_vazio, sinais, matar = _sem_maquina(tmp_path)
    lacos = Lacos(FAMILIA, raiz=proc_vazio, matar=matar)
    resultado: list[bool] = []
    gesto = threading.Thread(
        target=lambda: resultado.append(lacos.ligar("g1", captura="mic")), name="gesto")
    gesto.start()
    gesto.join()
    assert resultado == [True]
    pid = _pid_do_arquivo(pidfile)
    nascidos.append(pid)

    assert not _espera_morrer(pid, prazo_s=0.5), "o laço morreu junto com o fio do gesto"
    assert lacos.esta_ligado("g1")
    assert lacos.desligar("g1")
    assert _espera_morrer(pid)
    assert sinais == []


def _fingir_processo(raiz: Path, pid: int, argv: list[str], pai: int) -> None:
    """Uma entrada de `/proc`: `cmdline` com NUL e `stat` com o `comm` entre parênteses."""
    pasta = raiz / str(pid)
    pasta.mkdir(parents=True)
    (pasta / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
    campos = ["S", str(pai)] + ["0"] * 17 + ["12345"]
    (pasta / "stat").write_text(f"{pid} ({Path(argv[0]).name}) " + " ".join(campos) + " 0 0\n")


def _laco(familia: str, chave: str = "x1") -> list[str]:
    return ["pw-loopback", "--capture", "mic", "--name", f"hefesto-{familia}-{chave}"]


def test_a_varredura_recolhe_so_o_laco_da_familia_sem_pai_do_hefesto(tmp_path: Path) -> None:
    """MORDIDA: sem a varredura, o laço órfão da janela morta segue de pé."""
    raiz = tmp_path / "proc"
    _fingir_processo(raiz, P + 10, ["/usr/lib/systemd/systemd", "--user"], 1)
    janela = ["python3", "/home/x/.local/bin/hefesto-dualsense4unix-gui"]
    _fingir_processo(raiz, P + 11, janela, P + 10)
    _fingir_processo(raiz, P + 20, _laco(FAMILIA), P + 10)
    _fingir_processo(raiz, P + 21, _laco(FAMILIA, "x2"), 1)
    _fingir_processo(raiz, P + 22, _laco(FAMILIA, "x3"), P + 11)
    _fingir_processo(raiz, P + 23, _laco("outra-familia"), 1)
    _fingir_processo(raiz, P + 24, ["sleep", "--name", f"hefesto-{FAMILIA}-x4"], 1)
    _fingir_processo(raiz, P + 25, ["/usr/bin/pw-loopback", "--name", f"outro-{FAMILIA}-x5"], 1)
    sinais: list[tuple[int, int]] = []

    recolhidos = varrer_orfaos(FAMILIA, raiz=raiz, matar=lambda p, s: sinais.append((p, s)))

    assert sorted(recolhidos) == [P + 20, P + 21]
    assert sorted(sinais) == [(P + 20, signal.SIGTERM), (P + 21, signal.SIGTERM)]


def test_laco_de_outro_usuario_nao_e_tocado(tmp_path: Path) -> None:
    raiz = tmp_path / "proc"
    _fingir_processo(raiz, P + 30, _laco(FAMILIA), 1)
    sinais: list[tuple[int, int]] = []

    recolhidos = varrer_orfaos(
        FAMILIA, raiz=raiz, uid=os.getuid() + 1, matar=lambda p, s: sinais.append((p, s)))

    assert recolhidos == [] and sinais == []


def test_o_laco_que_mudou_entre_as_duas_leituras_nao_leva_sinal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O PID é conferido: processo que trocou de cara entre a leitura e o sinal não é morto."""
    raiz = tmp_path / "proc"
    _fingir_processo(raiz, P + 40, _laco(FAMILIA), 1)
    leitura = laco_de_audio._ler_o_processo
    lidas: list[int] = []

    def _troca(proc: Path) -> Any:
        lido = leitura(proc)
        if proc.name == str(P + 40):
            lidas.append(1)
            if len(lidas) > 1 and lido is not None:
                return (lido[0], lido[1], "99999", lido[3])
        return lido

    monkeypatch.setattr(laco_de_audio, "_ler_o_processo", _troca)
    sinais: list[tuple[int, int]] = []

    assert varrer_orfaos(FAMILIA, raiz=raiz, matar=lambda p, s: sinais.append((p, s))) == []
    assert sinais == []


def test_toda_familia_varre_os_orfaos_no_primeiro_contato(tmp_path: Path) -> None:
    """MORDIDA: a família que nunca varre deixa a janela nova sem saber do laço antigo."""
    raiz = tmp_path / "proc"
    _fingir_processo(raiz, P + 50, _laco(FAMILIA), 1)
    sinais: list[tuple[int, int]] = []

    lacos = Lacos(FAMILIA, raiz=raiz, matar=lambda p, s: sinais.append((p, s)))
    assert sinais == []
    assert not lacos.esta_ligado("x1")

    assert sinais == [(P + 50, signal.SIGTERM)]


def test_o_pid_1_este_processo_e_o_pai_dele_nunca_levam_sinal(tmp_path: Path) -> None:
    """MORDIDA: sem a lista dos intocáveis, um laço com o PID de casa leva SIGTERM."""
    raiz = tmp_path / "proc"
    intocaveis = {1, os.getpid(), os.getppid()}
    for pid in intocaveis:
        _fingir_processo(raiz, pid, _laco(FAMILIA, f"i{pid}"), 0)
    _fingir_processo(raiz, P + 60, _laco(FAMILIA), 0)
    sinais: list[tuple[int, int]] = []

    recolhidos = varrer_orfaos(FAMILIA, raiz=raiz, matar=lambda p, s: sinais.append((p, s)))

    assert recolhidos == [P + 60]
    assert sinais == [(P + 60, signal.SIGTERM)]


_ALVOS_DA_VARREDURA = {"Lacos", "varrer_orfaos"}


def _nome_chamado(no: ast.Call) -> str:
    funcao = no.func
    if isinstance(funcao, ast.Attribute):
        return funcao.attr
    return funcao.id if isinstance(funcao, ast.Name) else ""


def _e_a_maquina(valor: ast.expr) -> bool:
    texto = ast.unparse(valor)
    return texto in {"os.kill", "kill", "_PROC"} or "'/proc'" in texto or '"/proc"' in texto


def _varreduras_na_maquina(fonte: str) -> list[str]:
    """Cada `Lacos(` ou `varrer_orfaos(` sem `raiz=` e `matar=` de mentira, no teste ou no filho."""
    achados: list[str] = []
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.Call) and _nome_chamado(no) in _ALVOS_DA_VARREDURA:
            chaves = {k.arg: k.value for k in no.keywords if k.arg}
            faltam = [k for k in ("raiz", "matar") if k not in chaves or _e_a_maquina(chaves[k])]
            if faltam:
                achados.append(f"linha {no.lineno}: {ast.unparse(no)} sem {', '.join(faltam)}")
        elif isinstance(no, ast.Constant) and isinstance(no.value, str):
            if any(f"{alvo}(" in no.value for alvo in _ALVOS_DA_VARREDURA):
                try:
                    achados += _varreduras_na_maquina(no.value)
                except SyntaxError:
                    continue
        elif isinstance(no, ast.JoinedStr) and any(
            isinstance(v, ast.Constant) and f"{alvo}(" in str(v.value)
            for v in no.values for alvo in _ALVOS_DA_VARREDURA
        ):
            achados.append(f"linha {no.lineno}: código de filho em f-string não se confere")
    return achados


def test_nenhum_teste_roda_a_varredura_de_orfaos_contra_a_maquina() -> None:
    """MORDIDA: um `Lacos(FAMILIA)` cru num teste varre o `/proc` real com o `os.kill` real.

    Em 21/11/2026 uma mordida que tirava o filtro da família, com um teste que criava `Lacos` cru,
    mandou SIGTERM a todo processo do usuário, o gerente de usuário entre eles.
    """
    achados = {
        str(caminho.relative_to(RAIZ)): erros
        for caminho in sorted((RAIZ / "tests").rglob("*.py"))
        if (erros := _varreduras_na_maquina(caminho.read_text(encoding="utf-8")))
    }
    assert achados == {}
