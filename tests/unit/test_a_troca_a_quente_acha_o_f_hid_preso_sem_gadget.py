"""A troca a quente acha o `usb_f_hid` preso sem gadget, e o pad que caiu solta o `hidg`.

A-TROCA-A-QUENTE-ACHA-O-F-HID-PRESO-SEM-GADGET-01 (03/11/2026). O broker que o install
reinicia desmonta o gadget órfão; o daemon vivo seguia com o `/dev/hidg0` aberto, o
`refcnt` ficava em 1 sem gadget nenhum, e a troca desistia sem parar o daemon. Os testes
do install rodam com `/sys/module`, `/proc` e a pasta de gadgets de mentira, e `sudo` e
`systemctl` de mentira que anotam o que foi pedido: nada toca o kernel. O do daemon usa a
mesa do pad em USB das outras réguas.

AS MORDIDAS: tirar o `_usb_f_hid_esperar_o_refcnt` reprova
`test_o_hidg_do_daemon_que_sai_solta_no_prazo_e_troca` (o `refcnt` cai ~0,6 s depois de o
processo sair, como na medida); tirar o `_usb_f_hid_esperar_o_processo` reprova
`test_o_daemon_que_demora_a_sair_ainda_troca_e_o_aviso_diz`; tirar o
`_usb_f_hid_desmontar_o_que_sobrou` reprova `test_a_funcao_que_sobrou_sai_e_troca`;
tirar o `_usb_f_hid_quem_segura` do aviso reprova
`test_quem_segura_o_hidg_impede_a_troca_e_o_aviso_diz_quem`; tirar o `_largar_o_hidg`
do `_o_gadget_caiu` reprova `test_o_pad_que_caiu_solta_o_hidg_sem_esperar_o_tique`; o
`pad_usb_hidg_nao_largou` abaixo do nível do diário reprova
`test_o_hidg_que_nao_se_larga_diz_por_que_no_diario`.
"""

from __future__ import annotations

import errno
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import uhid_gamepad

from tests.unit.test_o_gadget_que_desce_no_tique_fala_com_o_broker_fora_dele import (
    _ate_a_queda,
    _fechar,
    _mesa,
)
from tests.unit.test_o_pad_que_nasce_pede_o_gadget_fora_do_tique import IDS, MESAS

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
CAMADA = RAIZ / "scripts" / "lib" / "camada_de_maquina.sh"
MARCAS = ("get_report_sized", "get_report_refuses")
SERVICO = "hefesto-dualsense4unix.service"
ESPERA_EM_UM_QUINTO = (
    "#!/bin/sh\n"
    'exec /usr/bin/sleep "$(/usr/bin/awk \'BEGIN { printf "%.4f", ARGV[1] / 5 }\' "$1")"\n'
)
"""O `sleep` de mentira: a camada espera em passos de 0,5 s até o prazo, e os dublês saem e
soltam o `refcnt` em segundos. Cada espera vale um quinto, na mesma ordem (o prazo, a saída
do processo e a soltura do `refcnt` guardam as proporções), e a troca deixa de gastar de 3 a
5 s só esperando."""


def _sys_module(tmp_path: Path, refcnt: int) -> Path:
    raiz = tmp_path / "sys-module"
    modulo = raiz / "usb_f_hid"
    (modulo / "parameters").mkdir(parents=True)
    (modulo / "refcnt").write_text(f"{refcnt}\n", encoding="ascii")
    (modulo / "parameters" / MARCAS[0]).write_text("Y\n", encoding="ascii")
    return raiz


def _processo(proc: Path, pid: int, comm: str, *, hidg: bool) -> None:
    (proc / str(pid) / "fd").mkdir(parents=True)
    (proc / str(pid) / "comm").write_text(f"{comm}\n", encoding="utf-8")
    (proc / str(pid) / "environ").write_bytes(b"HOME=/x\0")
    if hidg:
        (proc / str(pid) / "fd" / "7").symlink_to("/dev/hidg0")


def _gadget_que_sobrou(raiz: Path, nome: str) -> Path:
    g = raiz / nome
    (g / "functions" / "hid.usb0").mkdir(parents=True)
    (g / "configs" / "c.1" / "strings" / "0x409").mkdir(parents=True)
    (g / "strings" / "0x409").mkdir(parents=True)
    (g / "configs" / "c.1" / "hid.usb0").symlink_to(g / "functions" / "hid.usb0")
    return g


def _bin(
    tmp_path: Path, sys_module: Path, proc: Path, *, ativo: bool, pid: int,
    sai_em: float, solta_em: float,
) -> Path:
    """Os dublês: o `stop` volta na hora, o processo sai em ``sai_em`` e o `refcnt` cai em
    ``solta_em`` (na medida de 03/11, o `hidg0` sem dono às 46,5 e o `refcnt` 0 às 47,1).

    O `sudo` executa o `rmdir`, o `rm` e o `tee` na árvore de mentira, como o configfs:
    o grupo vazio de dentro sai junto com o de fora, e o `rmdir` da função solta
    a referência do módulo.
    """
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    log = tmp_path / "chamadas.log"
    modulo = sys_module / "usb_f_hid"
    (bin_ / "sudo").write_text(
        "#!/bin/sh\n"
        f'echo "sudo $*" >> "{log}"\n'
        'case "$*" in\n'
        f'  "modprobe -r usb_f_hid") rm -rf "{modulo}";;\n'
        f'  "modprobe usb_f_hid") mkdir -p "{modulo}/parameters"; echo 0 > "{modulo}/refcnt";'
        f' for m in {" ".join(MARCAS)}; do echo Y > "{modulo}/parameters/$m"; done;;\n'
        f'  "rmdir "*/functions/hid.*) rmdir "$2" && echo 0 > "{modulo}/refcnt";;\n'
        '  rmdir*) for s in "$2"/*/; do rmdir "$s" 2>/dev/null; done; rmdir "$2";;\n'
        '  rm*|tee*) "$@";;\n'
        "esac\n"
        "exit 0\n",
        encoding="utf-8",
    )
    (bin_ / "systemctl").write_text(
        "#!/bin/sh\n"
        f'echo "systemctl $*" >> "{log}"\n'
        'case "$*" in\n'
        f"  *is-active*) exit {0 if ativo else 3};;\n"
        f"  *MainPID*) echo {pid};;\n"
        f'  *stop*) (sleep {sai_em}; rm -rf "{proc}/{pid}"; sleep {round(solta_em - sai_em, 3)};'
        f' echo 0 > "{modulo}/refcnt") >/dev/null 2>&1 &;;\n'
        "esac\n"
        "exit 0\n",
        encoding="utf-8",
    )
    (bin_ / "sleep").write_text(ESPERA_EM_UM_QUINTO, encoding="utf-8")
    for nome in ("sudo", "systemctl", "sleep"):
        (bin_ / nome).chmod(0o755)
    return bin_


def _trocar(
    tmp_path: Path,
    *,
    refcnt: int,
    ativo: bool = False,
    pid: int = 4242,
    segura: tuple[tuple[int, str], ...] = (),
    sobrou: tuple[str, ...] = (),
    sai_em: float = 1.2,
    solta_em: float = 1.8,
) -> tuple[str, list[str], Path]:
    sys_module = _sys_module(tmp_path, refcnt)
    proc = tmp_path / "proc"
    proc.mkdir()
    _processo(proc, 42, "bash", hidg=False)
    for p, comm in segura:
        _processo(proc, p, comm, hidg=True)
    gadgets = tmp_path / "usb_gadget"
    gadgets.mkdir()
    for nome in sobrou:
        _gadget_que_sobrou(gadgets, nome)
    bin_ = _bin(
        tmp_path, sys_module, proc, ativo=ativo, pid=pid, sai_em=sai_em, solta_em=solta_em
    )
    script = "\n".join(
        (
            "set -euo pipefail",
            f"ROOT_DIR='{RAIZ}'",
            'warn() { printf "WARN: %s\\n" "$*"; }',
            f"source '{CAMADA}'",
            "trocar_usb_f_hid_a_quente",
            'printf "PENDENTE: %s\\n" "${_REINICIO_PENDENTE[@]}"',
        )
    )
    r = subprocess.run(
        [BASH, "-c", script], capture_output=True, text=True, timeout=60, check=False,
        env={
            "PATH": f"{bin_}:/usr/bin:/bin",
            "HOME": str(tmp_path),
            "LC_ALL": "C.UTF-8",
            "HEFESTO_SYS_MODULE": str(sys_module),
            "HEFESTO_USB_GADGET_ROOT": str(gadgets),
            "HEFESTO_USB_F_HID_PRAZO_S": "3",
            "HEFESTO_RAIZ_PROC": str(proc),
        },
    )
    assert r.returncode == 0, r.stderr
    log = tmp_path / "chamadas.log"
    chamadas = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return r.stdout, chamadas, gadgets


def test_o_hidg_do_daemon_que_sai_solta_no_prazo_e_troca(tmp_path: Path) -> None:
    """A medida de 03/11: `refcnt 1`, nenhum gadget, o `hidg0` no daemon que ainda sai."""
    saida, chamadas, _ = _trocar(
        tmp_path, refcnt=1, ativo=True, segura=((4242, "python3"),)
    )
    parar = f"systemctl --user stop {SERVICO}"
    subir = f"systemctl --user start {SERVICO}"
    assert parar in chamadas and subir in chamadas, chamadas
    assert "sudo modprobe -r usb_f_hid" in chamadas, saida
    assert chamadas.index(parar) < chamadas.index("sudo modprobe -r usb_f_hid"), chamadas
    assert chamadas.index("sudo modprobe usb_f_hid") < chamadas.index(subir), chamadas
    assert "trocado a quente" in saida, saida
    assert "PENDENTE: \n" in saida or saida.rstrip().endswith("PENDENTE:"), saida


def test_o_daemon_que_demora_a_sair_ainda_troca_e_o_aviso_diz(tmp_path: Path) -> None:
    """O processo passa do prazo para sair: o aviso diz o PID, e a troca espera o `refcnt`."""
    saida, chamadas, _ = _trocar(
        tmp_path, refcnt=1, ativo=True, segura=((4242, "python3"),), sai_em=4.0, solta_em=4.6
    )
    assert "o daemon parado (PID 4242) não saiu em 3 s" in saida, saida
    assert "sudo modprobe -r usb_f_hid" in chamadas, saida
    assert "trocado a quente" in saida, saida


def test_a_funcao_que_sobrou_sai_e_troca(tmp_path: Path) -> None:
    """O gadget nosso sem daemon e sem quem abra o `hidg`: ele sai, e a troca troca."""
    saida, chamadas, gadgets = _trocar(tmp_path, refcnt=2, sobrou=("hefesto-pad-0",))
    assert not (gadgets / "hefesto-pad-0").exists(), chamadas
    assert "hefesto-pad-0 sobrou" in saida, saida
    assert "sudo modprobe -r usb_f_hid" in chamadas, saida
    assert "trocado a quente" in saida, saida


def test_quem_segura_o_hidg_impede_a_troca_e_o_aviso_diz_quem(tmp_path: Path) -> None:
    """Um processo de fora com o `hidg` aberto: não troca, e o aviso diz o PID e o nome."""
    saida, chamadas, gadgets = _trocar(
        tmp_path, refcnt=1, segura=((777, "segurador"),), sobrou=("hefesto-pad-0",)
    )
    assert not any("modprobe" in c for c in chamadas), chamadas
    assert (gadgets / "hefesto-pad-0").is_dir(), "o gadget com o hidg aberto foi desmontado"
    assert "777 (segurador)" in saida, saida
    assert "PENDENTE: a função HID dos pads USB virtuais (usb_f_hid)" in saida, saida


@pytest.mark.parametrize(("jogadores", "quem_volta"), MESAS, ids=IDS)
def test_o_pad_que_caiu_solta_o_hidg_sem_esperar_o_tique(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, jogadores: tuple[int, ...],
    quem_volta: int,
) -> None:
    """A queda se sabe no fio do gadget: o `hidg` sai dali, e o fio para, sem tique nenhum.

    O número do fd fica (no `/dev/null`) e o dos outros pads não muda: a descida do tique
    o fecha como sempre.
    """
    m = _mesa(monkeypatch, tmp_path)
    pads: list[Any] = []
    try:
        pads = _ate_a_queda(m, jogadores, quem_volta, "caiu")
        volta = pads[jogadores.index(quem_volta)]
        gadget = volta._gadget
        assert gadget is not None
        assert os.readlink(f"/proc/self/fd/{gadget.fd}") == os.devnull, (
            "o pad cujo gadget caiu segue com o hidg aberto até o tique"
        )
        for pad in pads:
            if pad is not volta:
                assert os.readlink(f"/proc/self/fd/{pad._gadget.fd}") != os.devnull
        fio = volta._fio_do_uhid
        if fio is not None:
            fio.join(2.0)
            assert not fio.is_alive(), "o fio do gadget que caiu segue rodando no /dev/null"
    finally:
        _fechar(m, pads)


def test_o_hidg_que_nao_se_larga_diz_por_que_no_diario(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem `/dev/null` para o fd, o `hidg` segue preso: a linha sai no nível que o diário guarda."""
    avisos: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(
        uhid_gamepad.logger, "warning", lambda evento, **kw: avisos.append((evento, kw))
    )

    def _sem_fd(*_a: Any, **_k: Any) -> int:
        raise OSError(errno.EMFILE, "Too many open files")

    monkeypatch.setattr(uhid_gamepad.os, "open", _sem_fd)
    uhid_gamepad._largar_o_hidg(SimpleNamespace(fd=-1, gadget="hefesto-pad-0"))  # type: ignore[arg-type]
    assert [evento for evento, _ in avisos] == ["pad_usb_hidg_nao_largou"], avisos
    assert avisos[0][1]["gadget"] == "hefesto-pad-0"
