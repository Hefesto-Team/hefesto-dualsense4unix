"""O install troca o `usb_f_hid` a quente, o doctor e o pad leem a marca.

O-F-HID-FECHA-A-RESPOSTA (14/10/2026). O de fábrica faz o jogo no Proton esperar
5 s por pedido de feature. O curado se reconhece só pela marca
`/sys/module/usb_f_hid/parameters/get_report_sized`. Tudo aqui roda com um
`/sys/module` e uma pasta de gadgets de mentira, e com `sudo`, `systemctl` e
`modprobe` de mentira que anotam o que foi pedido: nada toca o kernel.

AS MORDIDAS: tirar o `_usb_f_hid_tem_a_marca` da volta cedo da troca reprova
`test_com_a_marca_nao_toca`; trocar a lista de gadgets alheios por nada reprova
`test_gadget_alheio_nao_troca_e_pede_o_reinicio`; tirar o `systemctl --user stop`
reprova `test_pads_nossos_param_o_daemon_trocam_e_sobem`; trocar o `fail` do
doctor por `warn` reprova `test_o_doctor_sem_a_marca_e_defeito`; arrancar o
`medir_a_marca_do_f_hid` do `_o_pad_em_usb` reprova
`test_o_pad_anota_a_marca_ao_montar`.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
CAMADA = RAIZ / "scripts" / "lib" / "camada_de_maquina.sh"
DOCTOR = RAIZ / "scripts" / "doctor.sh"
KERNEL_CONFERIDO = "7.1.5-76070105-generic"


def _sys_module(tmp_path: Path, *, carregado: bool, marca: bool, refcnt: int) -> Path:
    raiz = tmp_path / "sys-module"
    modulo = raiz / "usb_f_hid"
    raiz.mkdir()
    if carregado:
        (modulo / "parameters").mkdir(parents=True)
        (modulo / "refcnt").write_text(f"{refcnt}\n", encoding="ascii")
        if marca:
            (modulo / "parameters" / "get_report_sized").write_text("Y\n", encoding="ascii")
    return raiz


def _gadgets(tmp_path: Path, *nomes: str) -> Path:
    raiz = tmp_path / "usb_gadget"
    raiz.mkdir()
    for nome in nomes:
        (raiz / nome / "functions" / "hid.usb0").mkdir(parents=True)
    return raiz


def _bin(tmp_path: Path, sys_module: Path, *, daemon_ativo: bool) -> Path:
    """Os dublês: o `modprobe usb_f_hid` traz a marca, o `stop` do daemon solta os pads."""
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
        f' echo Y > "{modulo}/parameters/get_report_sized";;\n'
        "esac\n"
        "exit 0\n",
        encoding="utf-8",
    )
    (bin_ / "systemctl").write_text(
        "#!/bin/sh\n"
        f'echo "systemctl $*" >> "{log}"\n'
        'case "$*" in\n'
        f'  *is-active*) exit {0 if daemon_ativo else 3};;\n'
        f'  *stop*) echo 0 > "{modulo}/refcnt";;\n'
        "esac\n"
        "exit 0\n",
        encoding="utf-8",
    )
    for nome in ("sudo", "systemctl"):
        (bin_ / nome).chmod(0o755)
    return bin_


def _trocar(
    tmp_path: Path,
    *,
    carregado: bool = True,
    marca: bool = False,
    refcnt: int = 0,
    gadgets: tuple[str, ...] = (),
    daemon_ativo: bool = False,
) -> tuple[str, list[str], Path]:
    sys_module = _sys_module(tmp_path, carregado=carregado, marca=marca, refcnt=refcnt)
    bin_ = _bin(tmp_path, sys_module, daemon_ativo=daemon_ativo)
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
            "HEFESTO_USB_GADGET_ROOT": str(_gadgets(tmp_path, *gadgets)),
            "HEFESTO_USB_F_HID_PRAZO_S": "1",
        },
    )
    assert r.returncode == 0, r.stderr
    log = tmp_path / "chamadas.log"
    chamadas = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return r.stdout, chamadas, sys_module


def test_sem_a_marca_e_sem_pad_troca(tmp_path: Path) -> None:
    saida, chamadas, sys_module = _trocar(tmp_path)
    assert chamadas == ["sudo modprobe -r usb_f_hid", "sudo modprobe usb_f_hid"], chamadas
    assert "trocado a quente" in saida, saida
    assert (sys_module / "usb_f_hid" / "parameters" / "get_report_sized").exists()
    assert "PENDENTE: \n" in saida or saida.rstrip().endswith("PENDENTE:"), saida


def test_com_a_marca_nao_toca(tmp_path: Path) -> None:
    """A segunda volta do install: o mesmo estado, sem troca à toa."""
    saida, chamadas, _ = _trocar(tmp_path, marca=True, refcnt=4, gadgets=("hefesto-pad-1",))
    assert chamadas == [], chamadas
    assert "nada a trocar" in saida, saida


def test_descarregado_nao_toca(tmp_path: Path) -> None:
    saida, chamadas, _ = _trocar(tmp_path, carregado=False)
    assert chamadas == [], chamadas
    assert "próximo carregamento" in saida, saida


def test_gadget_alheio_nao_troca_e_pede_o_reinicio(tmp_path: Path) -> None:
    saida, chamadas, _ = _trocar(
        tmp_path, refcnt=2, gadgets=("hefesto-pad-1", "teclado-da-raspberry"), daemon_ativo=True
    )
    assert not any("modprobe" in c for c in chamadas), chamadas
    assert not any("stop" in c for c in chamadas), chamadas
    assert "teclado-da-raspberry" in saida, saida
    assert "PENDENTE: a função HID dos pads USB virtuais (usb_f_hid)" in saida, saida


def test_pads_nossos_param_o_daemon_trocam_e_sobem(tmp_path: Path) -> None:
    saida, chamadas, _ = _trocar(
        tmp_path, refcnt=4, gadgets=("hefesto-pad-1", "hefesto-pad-2"), daemon_ativo=True
    )
    parar = "systemctl --user stop hefesto-dualsense4unix.service"
    subir = "systemctl --user start hefesto-dualsense4unix.service"
    assert parar in chamadas and subir in chamadas, chamadas
    assert chamadas.index(parar) < chamadas.index("sudo modprobe -r usb_f_hid"), chamadas
    assert chamadas.index("sudo modprobe usb_f_hid") < chamadas.index(subir), chamadas
    assert "trocado a quente" in saida, saida


def test_refcnt_preso_nao_troca_e_sobe_o_daemon(tmp_path: Path) -> None:
    """O daemon parado não soltou os pads no prazo: não troca, e o daemon volta."""
    sys_module = tmp_path / "sys-module"
    saida, chamadas, _ = _trocar(
        tmp_path, refcnt=4, gadgets=("hefesto-pad-1",), daemon_ativo=False
    )
    assert not any("modprobe" in c for c in chamadas), chamadas
    assert "não se soltaram" in saida, saida
    assert "PENDENTE: a função HID dos pads USB virtuais (usb_f_hid)" in saida, saida
    assert (sys_module / "usb_f_hid" / "refcnt").read_text().strip() == "4"


def test_o_install_chama_a_troca_depois_do_dkms(tmp_path: Path) -> None:
    """O passo inteiro com o `dkms_lib.sh` de mentira: staged, e a troca vem atrás."""
    raiz = tmp_path / "raiz"
    (raiz / "scripts").mkdir(parents=True)
    (raiz / "scripts" / "dkms_lib.sh").write_text(
        "dkms_warn_secureboot_once() { :; }\n"
        "dkms_pkg_version() { echo 1.0.0; }\n"
        f'dkms_install_patched_module() {{ echo "dkms $*" >> "{tmp_path}/chamadas.log"; }}\n'
        "dkms_module_from_updates() { return 0; }\n",
        encoding="utf-8",
    )
    sys_module = _sys_module(tmp_path, carregado=True, marca=False, refcnt=0)
    bin_ = _bin(tmp_path, sys_module, daemon_ativo=False)
    script = "\n".join(
        (
            "set -euo pipefail",
            f"ROOT_DIR='{RAIZ}'",
            f"source '{CAMADA}'",
            f"ROOT_DIR='{raiz}'",
            "NO_DKMS=0",
            'warn() { printf "WARN: %s\\n" "$*"; }',
            "_distro_so_leitura() { return 1; }",
            "install_dkms_usb_f_hid_host",
            "install_dkms_usb_f_hid_host",
        )
    )
    r = subprocess.run(
        [BASH, "-c", script], capture_output=True, text=True, timeout=60, check=False,
        env={
            "PATH": f"{bin_}:/usr/bin:/bin",
            "HOME": str(tmp_path),
            "HEFESTO_SYS_MODULE": str(sys_module),
            "HEFESTO_USB_GADGET_ROOT": str(_gadgets(tmp_path)),
        },
    )
    assert r.returncode == 0, r.stderr
    chamadas = (tmp_path / "chamadas.log").read_text(encoding="utf-8").splitlines()
    dkms = [c for c in chamadas if c.startswith("dkms ")]
    assert len(dkms) == 2, chamadas
    assert dkms[0].startswith("dkms hefesto-usb-f-hid 1.0.0 "), chamadas
    assert dkms[0].endswith("/assets/dkms/usb-f-hid usb_f_hid"), chamadas
    assert chamadas.index(dkms[0]) < chamadas.index("sudo modprobe -r usb_f_hid"), chamadas
    # a segunda volta acha a marca e não recarrega nada
    assert chamadas.count("sudo modprobe usb_f_hid") == 1, chamadas
    assert "nada a trocar" in r.stdout, r.stdout


def _passo_do_install(
    tmp_path: Path, *, no_dkms: int = 0, staged: bool = True
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """O passo `install_dkms_usb_f_hid_host` com o `dkms_lib.sh` de mentira."""
    raiz = tmp_path / "raiz"
    (raiz / "scripts").mkdir(parents=True)
    (raiz / "scripts" / "dkms_lib.sh").write_text(
        "dkms_warn_secureboot_once() { :; }\n"
        "dkms_pkg_version() { echo 1.0.0; }\n"
        f'dkms_install_patched_module() {{ echo "dkms $*" >> "{tmp_path}/chamadas.log"; }}\n'
        f"dkms_module_from_updates() {{ return {0 if staged else 1}; }}\n",
        encoding="utf-8",
    )
    sys_module = _sys_module(tmp_path, carregado=True, marca=False, refcnt=0)
    bin_ = _bin(tmp_path, sys_module, daemon_ativo=False)
    script = "\n".join(
        (
            "set -euo pipefail",
            f"ROOT_DIR='{RAIZ}'",
            f"source '{CAMADA}'",
            f"ROOT_DIR='{raiz}'",
            f"NO_DKMS={no_dkms}",
            'warn() { printf "WARN: %s\\n" "$*"; }',
            "_distro_so_leitura() { return 1; }",
            "install_dkms_usb_f_hid_host",
        )
    )
    r = subprocess.run(
        [BASH, "-c", script], capture_output=True, text=True, timeout=60, check=False,
        env={
            "PATH": f"{bin_}:/usr/bin:/bin",
            "HOME": str(tmp_path),
            "HEFESTO_SYS_MODULE": str(sys_module),
            "HEFESTO_USB_GADGET_ROOT": str(_gadgets(tmp_path)),
        },
    )
    assert r.returncode == 0, r.stderr
    log = tmp_path / "chamadas.log"
    return r, log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def test_no_dkms_nao_constroi_nem_troca(tmp_path: Path) -> None:
    """A MORDIDA: tire o portão `NO_DKMS` da função e o `--no-dkms` constrói e troca."""
    r, chamadas = _passo_do_install(tmp_path, no_dkms=1)
    assert chamadas == [], chamadas
    assert "pulado (--no-dkms)" in r.stdout, r.stdout


def test_fora_do_baseline_nao_troca_o_de_fabrica(tmp_path: Path) -> None:
    """Kernel fora do pino: o DKMS pula (rc 77), nada fica staged e o carregado fica.

    A MORDIDA: tire a volta cedo do `dkms_module_from_updates` e a troca recarrega o
    de fábrica à toa, sem cura nenhuma em `updates/dkms`.
    """
    r, chamadas = _passo_do_install(tmp_path, staged=False)
    assert [c for c in chamadas if c.startswith("dkms ")], chamadas
    assert not any("modprobe" in c for c in chamadas), chamadas
    assert "KERNELS_VALIDADOS" in r.stdout and "patch/BASELINE" in r.stdout, r.stdout


def _doctor(tmp_path: Path, *, carregado: bool, marca: bool, staged: bool,
            kernel: str = KERNEL_CONFERIDO) -> str:
    bin_ = tmp_path / "bin-doctor"
    bin_.mkdir()
    arquivo = (
        "/lib/modules/k/updates/dkms/usb_f_hid.ko.zst" if staged
        else "/lib/modules/k/kernel/drivers/usb/gadget/function/usb_f_hid.ko.zst"
    )
    (bin_ / "modinfo").write_text(f'#!/bin/sh\necho "{arquivo}"\n', encoding="utf-8")
    # o dkms presente e o Secure Boot desligado (efivars vazia): a frase é a do
    # install, a mesma em qualquer máquina que rode a régua
    (bin_ / "dkms").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    for nome in ("modinfo", "dkms"):
        (bin_ / nome).chmod(0o755)
    sys_module = _sys_module(tmp_path, carregado=carregado, marca=marca, refcnt=0)
    efivars = tmp_path / "efivars-vazia"
    efivars.mkdir()
    r = subprocess.run(
        [BASH, "-c", f'source "{DOCTOR}"; check_hefesto_usb_f_hid_dkms'],
        env={
            "PATH": f"{bin_}:/usr/bin:/bin",
            "HOME": str(tmp_path),
            "HEFESTO_DOCTOR_KERNEL": kernel,
            "HEFESTO_DOCTOR_SYS_MODULE": str(sys_module),
            "HEFESTO_EFIVARS_ROOT": str(efivars),
        },
        capture_output=True, text=True, timeout=30, check=False,
    )
    return r.stdout + r.stderr


def test_o_doctor_sem_a_marca_e_defeito(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, carregado=True, marca=False, staged=False)
    assert "[FAIL]" in saida, saida
    assert "o jogo no Proton espera 5 s por pedido de feature e perde os controles" in saida
    assert "não está instalada para o kernel 7.1.5-76070105-generic" in saida, saida
    assert "install.sh" in saida, saida


def test_o_doctor_com_o_curado_staged_diz_que_falta_trocar(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, carregado=True, marca=False, staged=True)
    assert "[FAIL]" in saida and "não foi trocada" in saida, saida


def test_o_doctor_em_kernel_nao_conferido_aponta_o_baseline(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, carregado=True, marca=False, staged=False,
                    kernel="7.3.0-76070300-generic")
    assert "[FAIL]" in saida and "patch/BASELINE" in saida, saida
    assert "7.1.5-76070105" in saida, saida


def test_o_doctor_com_a_marca_passa(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, carregado=True, marca=True, staged=True)
    assert "[ OK ]" in saida and "[FAIL]" not in saida, saida


def test_o_doctor_sem_pad_no_ar_nao_reclama(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, carregado=False, marca=False, staged=True)
    assert "[FAIL]" not in saida and "[WARN]" not in saida, saida
    assert "próximo carregamento" in saida, saida


@pytest.mark.parametrize(
    ("carregado", "marca", "esperado"), [(True, True, True), (True, False, False),
                                         (False, False, None)]
)
def test_o_pad_usb_le_a_marca(
    tmp_path: Path, carregado: bool, marca: bool, esperado: bool | None
) -> None:
    from hefesto_dualsense4unix.integrations import pad_usb

    sys_module = _sys_module(tmp_path, carregado=carregado, marca=marca, refcnt=0)
    caminho = str(sys_module / "usb_f_hid" / "parameters" / "get_report_sized")
    assert pad_usb.f_hid_fecha_a_resposta(caminho) is esperado
    assert pad_usb.medir_a_marca_do_f_hid(caminho) is esperado
    assert pad_usb.marca_do_f_hid_medida() is esperado


def test_o_pad_anota_a_marca_ao_montar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O `_o_pad_em_usb` mede a marca com o gadget na mão, e o pad sobe igual."""
    from hefesto_dualsense4unix.integrations import pad_usb, uhid_gamepad

    medidas: list[bool] = []

    def medir(caminho: str = pad_usb.MARCA_DO_F_HID) -> bool:
        medidas.append(True)
        return False

    class _Gadget:
        fd = -1
        interface = None  # sem a interface, o pad entra na fila do vudc
        serial = "hefesto-pad-02fe00000001"
        identidade = "02fe00000001"
        a_caminho_s = 0.0

        def desmontar(self) -> None:
            raise AssertionError("o pad sem a marca não pode ser desmontado")

    class _Pad:
        _sem_gadget = False
        identity = "02:fe:00:00:00:01"
        mac = "02:fe:00:00:00:01"
        player = 1
        product = 0x0CE6

        def __init__(self) -> None:
            self.blueprint = {"descriptor": b"\x05\x01"}

    monkeypatch.setattr(pad_usb, "medir_a_marca_do_f_hid", medir)
    monkeypatch.setattr(uhid_gamepad._GADGETS_ESTACIONADOS, "retomar", lambda _i: _Gadget())
    monkeypatch.setattr(pad_usb, "escrever_get_report", lambda *_a: None)
    monkeypatch.setattr(uhid_gamepad, "_F_HID_SEM_MARCA_AVISADO", [])

    class _ChegouNaFilaError(Exception):
        """A medida já passou: a fila do vudc é o passo seguinte, e o teste para ali."""

    def _parar(*_a: object, **_k: object) -> float:
        raise _ChegouNaFilaError

    monkeypatch.setattr(uhid_gamepad, "_entrar_na_fila", _parar)
    monkeypatch.setattr(uhid_gamepad, "_GADGET_ENUMERA_S", 0.0)
    with pytest.raises(_ChegouNaFilaError):
        uhid_gamepad._o_pad_em_usb(_Pad(), {0x05: b"\x05"})  # type: ignore[arg-type]
    assert medidas == [True]
    assert uhid_gamepad._F_HID_SEM_MARCA_AVISADO == [True]


def test_o_state_full_publica_so_da_memoria(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon import ipc_handlers
    from hefesto_dualsense4unix.integrations import pad_usb

    monkeypatch.setattr(pad_usb, "marca_do_f_hid_medida", lambda: False)
    result: dict[str, object] = {"gamepad_emulation": {"enabled": True}}
    ipc_handlers._com_a_marca_do_f_hid(result)
    assert result["gamepad_emulation"] == {"enabled": True, "get_report_sized": False}
    sem_bloco: dict[str, object] = {}
    ipc_handlers._com_a_marca_do_f_hid(sem_bloco)
    assert sem_bloco == {}
