"""O que é da bancada fica na bancada (O-QUE-E-DA-BANCADA-FICA-NA-BANCADA-01).

Curas medidas num desktop com um adaptador Wi-Fi Realtek USB não são padrão de
toda máquina. Cada uma continua valendo onde a causa existe; nas outras, o
install pula com uma linha que diz o porquê:

- energia: as duas regras udev largas (todo host USB, todo Bluetooth USB) e o
  ``usbcore.autosuspend=-1`` só valem em computador sem bateria;
- rede: o DKMS do rtw88 só com um adaptador que o ``rtw88_usb`` atenda, e o
  vigia do Wi-Fi USB só com uma interface Wi-Fi sob o barramento USB;
- primeira instalação: o extra ``dev`` só com ``--dev``.

Tudo roda em dublês dentro de ``tmp_path`` (sysfs de mentira, ``modprobe`` de
mentira, ``sudo`` ausente): nada toca o aparelho nem o ``/etc`` de quem roda.
"""

from __future__ import annotations

import fnmatch
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import kernel_cmdline as kc

RAIZ = Path(__file__).resolve().parents[2]
INSTALL = RAIZ / "install.sh"
LIB = RAIZ / "scripts" / "lib" / "camada_de_maquina.sh"
REGRA_DISPOSITIVOS = RAIZ / "assets" / "81-hefesto-usb-power.rules"
REGRA_HOSTS = RAIZ / "assets" / "81-hefesto-usb-host-power.rules"
BASH = shutil.which("bash") or "/bin/bash"


# ---------------------------------------------------------------------------
# Um casador mínimo de regra udev: o mesmo casamento do `udevadm test` para as
# chaves que estas regras usam (ACTION, SUBSYSTEM, ENV{}, ATTR{}, TEST), contra
# um sysfs de mentira. Não é o udev: é a leitura da regra com o mesmo casamento.
# ---------------------------------------------------------------------------
def _chaves(linha: str) -> list[str]:
    """Separa por vírgula FORA de aspas."""
    return [c.strip() for c in re.findall(r'(?:[^,"]|"[^"]*")+', linha) if c.strip()]


def _glob(valor: str, alvo: str) -> bool:
    return any(fnmatch.fnmatchcase(alvo, alt) for alt in valor.split("|"))


def _casa(
    linha: str,
    *,
    evento: str,
    subsistema: str,
    atributos: dict[str, str],
    ambiente: dict[str, str],
    pasta_do_aparelho: Path,
    sys_falso: Path,
) -> bool:
    """A linha casa? (As atribuições `=` não entram: só o lado esquerdo.)"""
    for chave in _chaves(linha):
        m = re.fullmatch(r'(?P<k>[A-Z]+)(?:\{(?P<a>[^}]*)\})?(?P<op>==|!=|=)"(?P<v>[^"]*)"', chave)
        assert m is not None, f"chave que o casador não entende: {chave!r}"
        k, a, op, v = m["k"], m["a"], m["op"], m["v"]
        if op == "=":
            continue
        if k == "ACTION":
            bate = _glob(v, evento)
        elif k == "SUBSYSTEM":
            bate = _glob(v, subsistema)
        elif k == "ENV":
            bate = _glob(v, ambiente.get(a or "", ""))
        elif k == "ATTR":
            bate = _glob(v, atributos.get(a or "", ""))
        elif k == "TEST":
            if v.startswith("/sys/"):
                bate = (sys_falso / v[len("/sys/") :]).exists()
            else:
                bate = (pasta_do_aparelho / v).exists()
        else:  # pragma: no cover - chave nova numa regra: a régua tem de ser ampliada
            raise AssertionError(f"chave {k} fora do que o casador conhece")
        if (op == "==") != bate:
            return False
    return True


def _linhas(regra: Path) -> list[str]:
    return [
        ln.strip()
        for ln in regra.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


def _sys_com(tmp_path: Path, *baterias: str) -> Path:
    sys_falso = tmp_path / "sys"
    (sys_falso / "class" / "power_supply").mkdir(parents=True)
    for nome in baterias:
        (sys_falso / "class" / "power_supply" / nome).mkdir()
    return sys_falso


def _aparelho(tmp_path: Path) -> Path:
    pasta = tmp_path / "aparelho"
    (pasta / "power").mkdir(parents=True, exist_ok=True)
    (pasta / "power" / "control").write_text("auto\n", encoding="utf-8")
    return pasta


def _alguma_linha_casa(regra: Path, tmp_path: Path, sys_falso: Path, **kw) -> bool:
    return any(
        _casa(
            ln,
            pasta_do_aparelho=_aparelho(tmp_path),
            sys_falso=sys_falso,
            **kw,
        )
        for ln in _linhas(regra)
    )


BLUETOOTH_INTERNO = {
    "evento": "add",
    "subsistema": "usb",
    "atributos": {"idVendor": "0489", "bDeviceClass": "e0"},
    "ambiente": {"DEVTYPE": "usb_device"},
}
HOST_XHCI = {
    "evento": "change",
    "subsistema": "pci",
    "atributos": {"class": "0x0c0330"},
    "ambiente": {},
}
DUALSENSE = {
    "evento": "add",
    "subsistema": "usb",
    "atributos": {"idVendor": "054c", "bDeviceClass": "00"},
    "ambiente": {"DEVTYPE": "usb_device"},
}


class TestEnergiaSoSemBateria:
    @pytest.mark.parametrize("bateria", ["BAT0", "BAT1"])
    def test_com_bateria_o_host_fica_em_auto(self, tmp_path: Path, bateria: str) -> None:
        sys_falso = _sys_com(tmp_path, bateria)
        assert not _alguma_linha_casa(REGRA_HOSTS, tmp_path, sys_falso, **HOST_XHCI)

    def test_sem_bateria_o_host_fica_ligado(self, tmp_path: Path) -> None:
        sys_falso = _sys_com(tmp_path)
        assert _alguma_linha_casa(REGRA_HOSTS, tmp_path, sys_falso, **HOST_XHCI)

    @pytest.mark.parametrize("bateria", ["BAT0", "BAT1"])
    def test_com_bateria_o_bluetooth_interno_nao_e_escrito(
        self, tmp_path: Path, bateria: str
    ) -> None:
        sys_falso = _sys_com(tmp_path, bateria)
        assert not _alguma_linha_casa(REGRA_DISPOSITIVOS, tmp_path, sys_falso, **BLUETOOTH_INTERNO)

    def test_sem_bateria_o_bluetooth_usb_segue_como_hoje(self, tmp_path: Path) -> None:
        sys_falso = _sys_com(tmp_path)
        assert _alguma_linha_casa(REGRA_DISPOSITIVOS, tmp_path, sys_falso, **BLUETOOTH_INTERNO)

    def test_a_bateria_do_controle_nao_e_a_do_computador(self, tmp_path: Path) -> None:
        sys_falso = _sys_com(tmp_path, "ps-controller-battery-aa:bb:cc:00:00:ff")
        assert _alguma_linha_casa(REGRA_HOSTS, tmp_path, sys_falso, **HOST_XHCI)
        assert _alguma_linha_casa(REGRA_DISPOSITIVOS, tmp_path, sys_falso, **BLUETOOTH_INTERNO)

    def test_o_controle_sony_vale_em_notebook_tambem(self, tmp_path: Path) -> None:
        sys_falso = _sys_com(tmp_path, "BAT0")
        assert _alguma_linha_casa(REGRA_DISPOSITIVOS, tmp_path, sys_falso, **DUALSENSE)

    def test_o_casador_morde_uma_regra_sem_a_guarda(self, tmp_path: Path) -> None:
        """O casador não é tapete: com a guarda arrancada ele diz que casa."""
        sem_guarda = [re.sub(r'TEST!="[^"]*",\s*', "", ln) for ln in _linhas(REGRA_HOSTS)]
        sys_falso = _sys_com(tmp_path, "BAT0")
        assert any(
            _casa(
                ln,
                pasta_do_aparelho=_aparelho(tmp_path),
                sys_falso=sys_falso,
                **HOST_XHCI,
            )
            for ln in sem_guarda
        )


class TestCmdlineComBateria:
    VIRGEM = "quiet splash"

    def test_com_bateria_o_plano_nao_traz_o_autosuspend_e_mantem_os_quirks(self) -> None:
        plano = {a.param: a for a in kc.plan_cmdline(self.VIRGEM, com_bateria=True)}
        assert plano[kc.AUTOSUSPEND_PARAM].op == kc.OP_PULA
        assert plano[kc.QUIRKS_PARAM].op == kc.OP_ADD
        final = kc.apply_plan(
            kc.parse_cmdline(self.VIRGEM), kc.plan_cmdline(self.VIRGEM, com_bateria=True)
        )
        assert kc.AUTOSUSPEND_TOKEN not in final
        assert any(t.startswith("usbcore.quirks=054c:0ce6:gn") for t in final)
        assert kc.forbidden_reintroductions(kc.plan_cmdline(self.VIRGEM, com_bateria=True)) == []

    def test_sem_bateria_o_plano_e_o_de_hoje(self) -> None:
        plano = {a.param: a for a in kc.plan_cmdline(self.VIRGEM)}
        assert plano[kc.AUTOSUSPEND_PARAM].op == kc.OP_ADD
        assert plano[kc.AUTOSUSPEND_PARAM].token == kc.AUTOSUSPEND_TOKEN
        assert kc.plan_cmdline(self.VIRGEM) == kc.plan_cmdline(self.VIRGEM, com_bateria=False)

    def test_o_que_a_pessoa_ja_tinha_e_preservado_com_bateria(self) -> None:
        tokens = f"quiet {kc.AUTOSUSPEND_TOKEN}"
        plano = {a.param: a for a in kc.plan_cmdline(tokens, com_bateria=True)}
        assert plano[kc.AUTOSUSPEND_PARAM].op == kc.OP_NONE
        assert plano[kc.AUTOSUSPEND_PARAM].owner == kc.OWNER_TERCEIRO

    def test_valor_divergente_nao_e_trocado_em_notebook(self) -> None:
        plano = {
            a.param: a for a in kc.plan_cmdline("quiet usbcore.autosuspend=2", com_bateria=True)
        }
        assert plano[kc.AUTOSUSPEND_PARAM].op == kc.OP_PULA
        assert plano[kc.AUTOSUSPEND_PARAM].remove_tokens == ()


def _heredoc_do_passo_3e() -> str:
    texto = INSTALL.read_text(encoding="utf-8")
    m = re.search(
        r"_cmdline_plan=\"\$\(python3 - [^\n]*<<'PYEOF'\n(?P<py>.*?)\nPYEOF\n",
        texto,
        re.S,
    )
    assert m is not None, "o python do passo 3e saiu do install.sh"
    return m["py"]


def _roda_o_passo_3e(tmp_path: Path, bateria: str) -> list[list[str]]:
    """Roda o python REAL do passo 3e do install.sh contra um grub de mentira."""
    grub = tmp_path / "grub"
    grub.write_text('GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"\n', encoding="utf-8")
    codigo = _heredoc_do_passo_3e()
    codigo = codigo.replace("/etc/default/grub", str(grub))
    codigo = codigo.replace("/etc/kernelstub/configuration", str(tmp_path / "nao-ha"))
    codigo = codigo.replace("/etc/kernel/cmdline", str(tmp_path / "nao-ha"))
    r = subprocess.run(
        [sys.executable, "-", str(RAIZ), bateria],
        input=codigo,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return [ln.split("\t") for ln in r.stdout.splitlines() if ln.startswith("plan\t")]


class TestOPassoDoInstallPergunta:
    def test_com_bateria_o_install_pede_o_plano_sem_autosuspend(self, tmp_path: Path) -> None:
        linhas = _roda_o_passo_3e(tmp_path, "1")
        por_param = {ln[1]: ln for ln in linhas}
        assert por_param["usbcore.autosuspend"][2] == "skip"
        assert por_param["usbcore.autosuspend"][4] == "-", "campo vazio some no read do shell"
        assert por_param["usbcore.quirks"][2] == "add"

    def test_sem_bateria_o_install_pede_o_plano_de_hoje(self, tmp_path: Path) -> None:
        linhas = _roda_o_passo_3e(tmp_path, "0")
        por_param = {ln[1]: ln for ln in linhas}
        assert por_param["usbcore.autosuspend"][2] == "add"
        assert por_param["usbcore.autosuspend"][3] == "usbcore.autosuspend=-1"

    def test_o_shell_pergunta_pela_bateria_e_trata_o_skip(self) -> None:
        texto = INSTALL.read_text(encoding="utf-8")
        bloco = texto[texto.index('step "3e" "cmdline do kernel') :]
        bloco = bloco[: bloco.index('step "3e-trava"')]
        assert "_desempenho_tem_bateria" in bloco, "o passo 3e não pergunta pela bateria"
        assert re.search(r"^\s+skip\)\s*$", bloco, re.M), "o loop do plano não trata o skip"
        assert "tem bateria" in bloco

    def test_a_pergunta_da_bateria_tem_um_dono_so(self) -> None:
        lib = LIB.read_text(encoding="utf-8")
        assert len(re.findall(r"^_desempenho_tem_bateria\(\)", lib, re.M)) == 1
        assert "_desempenho_tem_bateria" not in REGRA_HOSTS.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# A rede: o DKMS do rtw88 e o vigia do Wi-Fi USB.
# ---------------------------------------------------------------------------
_MODPROBE_FALSO = """#!/bin/sh
# modprobe -R <alias>: o módulo que o kernel escolheria para o alias.
case "$2" in
  *v2357p012D*) echo rtw88_8822bu ;;
  *v0BDApB82C*) echo rtw88_8822cu ;;
  *) echo usbtouchscreen ;;
esac
"""


def _usb(sysfs: Path, nome: str, vid: str, pid: str, classe: str = "ff") -> None:
    dev = sysfs / "bus" / "usb" / "devices" / nome
    ifc = dev / f"{nome}:1.0"
    ifc.mkdir(parents=True)
    (dev / "idVendor").write_text(vid + "\n", encoding="utf-8")
    (dev / "idProduct").write_text(pid + "\n", encoding="utf-8")
    (ifc / "bInterfaceClass").write_text(classe + "\n", encoding="utf-8")
    (ifc / "modalias").write_text(
        f"usb:v{vid.upper()}p{pid.upper()}d0210dc00dsc00dp00ic{classe.upper()}iscFFipFFin00\n",
        encoding="utf-8",
    )
    # A interface mora ao lado do aparelho: o glob `*:*` do dono a enxerga.
    (sysfs / "bus" / "usb" / "devices" / f"{nome}:1.0").symlink_to(ifc)


def _bin(tmp_path: Path, *, com_modprobe: bool = True) -> Path:
    """PATH só com o que o dono usa — e SEM `sudo`, para a função parar nele."""
    pasta = tmp_path / "bin"
    pasta.mkdir(exist_ok=True)
    for nome in ("cat", "tr", "sed", "grep", "dirname", "basename"):
        alvo = shutil.which(nome)
        assert alvo, nome
        (pasta / nome).symlink_to(alvo)
    if com_modprobe:
        falso = pasta / "modprobe"
        falso.write_text(_MODPROBE_FALSO, encoding="utf-8")
        falso.chmod(0o755)
    return pasta


def _roda_lib(tmp_path: Path, corpo: str, env_extra: dict[str, str], pasta_bin: Path):
    env = {
        "PATH": str(pasta_bin),
        "HOME": str(tmp_path / "casa"),
        "LC_ALL": "C.UTF-8",
        "ROOT_DIR": str(RAIZ),
        **env_extra,
    }
    return subprocess.run(
        [
            BASH,
            "-c",
            f"warn() {{ printf 'WARN: %s\\n' \"$*\"; }}\nsource {shlex.quote(str(LIB))}\n{corpo}",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=env,
    )


def _sysfs(tmp_path: Path) -> Path:
    s = tmp_path / "usbsys"
    (s / "bus" / "usb" / "devices").mkdir(parents=True)
    return s


class TestRtw88SoComAdaptador:
    def test_sem_adaptador_a_pergunta_diz_nenhum(self, tmp_path: Path) -> None:
        s = _sysfs(tmp_path)
        _usb(s, "1-1", "054c", "0ce6")  # o DualSense não é Wi-Fi
        r = _roda_lib(
            tmp_path, "_rtw88_adaptadores_presentes", {"HEFESTO_USB_SYS": str(s)}, _bin(tmp_path)
        )
        assert r.returncode == 1 and r.stdout == ""

    def test_o_adaptador_que_o_kernel_resolve_para_o_rtw88_conta(self, tmp_path: Path) -> None:
        s = _sysfs(tmp_path)
        _usb(s, "3-1.4", "2357", "012d")
        r = _roda_lib(
            tmp_path, "_rtw88_adaptadores_presentes", {"HEFESTO_USB_SYS": str(s)}, _bin(tmp_path)
        )
        assert r.returncode == 0
        assert r.stdout.strip() == "2357:012d"

    def test_interface_de_outra_classe_nao_e_perguntada(self, tmp_path: Path) -> None:
        s = _sysfs(tmp_path)
        _usb(s, "3-1.4", "2357", "012d", classe="e0")  # o Bluetooth do TP-Link
        r = _roda_lib(
            tmp_path, "_rtw88_adaptadores_presentes", {"HEFESTO_USB_SYS": str(s)}, _bin(tmp_path)
        )
        assert r.returncode == 1

    def test_sem_a_ferramenta_de_modulos_a_resposta_e_nao_sei(self, tmp_path: Path) -> None:
        s = _sysfs(tmp_path)
        _usb(s, "3-1.4", "2357", "012d")
        r = _roda_lib(
            tmp_path,
            "_rtw88_adaptadores_presentes",
            {"HEFESTO_USB_SYS": str(s), "HEFESTO_MODPROBE": str(tmp_path / "nao-ha")},
            _bin(tmp_path, com_modprobe=False),
        )
        assert r.returncode == 2

    def test_a_cura_pula_sem_adaptador_e_diz_o_porque(self, tmp_path: Path) -> None:
        s = _sysfs(tmp_path)
        r = _roda_lib(
            tmp_path,
            "NO_DKMS=0; install_dkms_rtw88_usb_host; echo RC=$?",
            {"HEFESTO_USB_SYS": str(s)},
            _bin(tmp_path),
        )
        assert "nenhum adaptador Wi-Fi USB que o rtw88_usb atenda" in r.stdout
        assert "rode ./install.sh de novo" in r.stdout
        assert "sudo ausente" not in r.stdout, (
            "pulou depois do portão do sudo: a pergunta vem antes"
        )
        assert "RC=0" in r.stdout

    def test_com_adaptador_a_cura_segue_para_os_portoes_de_sempre(self, tmp_path: Path) -> None:
        s = _sysfs(tmp_path)
        _usb(s, "3-1.4", "2357", "012d")
        r = _roda_lib(
            tmp_path,
            "NO_DKMS=0; install_dkms_rtw88_usb_host; echo RC=$?",
            {"HEFESTO_USB_SYS": str(s)},
            _bin(tmp_path),
        )
        assert "presente: 2357:012d" in r.stdout
        assert "sudo ausente" in r.stdout, "com adaptador a função segue (aqui para no sudo)"
        assert "RC=0" in r.stdout

    def test_o_ensaio_faz_a_mesma_pergunta_que_a_cura(self) -> None:
        texto = INSTALL.read_text(encoding="utf-8")
        ramo = texto[texto.index("        dkms-rtw88)") :]
        ramo = ramo[: ramo.index("        wifi-usb)")]
        assert "_rtw88_adaptadores_presentes" in ramo, "o --dry-run promete o que o install pula"
        ramo = texto[texto.index("        wifi-usb)") :]
        ramo = ramo[: ramo.index("        desempenho)")]
        assert "_wifi_usb_agora" in ramo, "o --dry-run promete o vigia que o install pula"


class TestVigiaSoComWifiUsb:
    def test_o_dono_da_pergunta_e_o_wifi_usb_sh(self) -> None:
        lib = LIB.read_text(encoding="utf-8")
        corpo = lib[lib.index("_wifi_usb_agora() {") :]
        corpo = corpo[: corpo.index("\n}\n")]
        assert "scripts/wifi_usb.sh" in corpo and "--lista" in corpo

    def test_a_cura_pergunta_antes_do_sudo(self) -> None:
        lib = LIB.read_text(encoding="utf-8")
        corpo = lib[lib.index("install_wifi_usb_host() {") :]
        corpo = corpo[: corpo.index("\n}\n")]
        assert corpo.index("_wifi_usb_agora") < corpo.index("command -v sudo")


# ---------------------------------------------------------------------------
# A primeira instalação: o extra dev só com --dev.
# ---------------------------------------------------------------------------
def _extras_para(with_dev: str) -> str:
    texto = INSTALL.read_text(encoding="utf-8")
    ini = texto.index('_extras="emulation,cosmic"')
    fim = texto.index("\n# AS VERSÕES QUE A CASA MEDIU", ini)
    trecho = texto[ini:fim]
    r = subprocess.run(
        [BASH, "-c", f"WITH_DEV={with_dev}\n{trecho}\nprintf '%s' \"$_extras\""],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return r.stdout


class TestExtraDev:
    def test_o_padrao_nao_traz_o_dev(self) -> None:
        texto = INSTALL.read_text(encoding="utf-8")
        assert re.search(r"^WITH_DEV=0$", texto, re.M)
        assert _extras_para("0") == "emulation,cosmic"

    def test_com_dev_o_extra_entra(self) -> None:
        assert _extras_para("1") == "emulation,cosmic,dev"

    def test_a_flag_dev_liga_e_a_no_dev_continua_aceita(self) -> None:
        texto = INSTALL.read_text(encoding="utf-8")
        assert re.search(r"--dev\)\s+WITH_DEV=1", texto)
        assert re.search(r"--no-dev\)\s+WITH_DEV=0", texto), (
            "quem tem --no-dev num script não quebra"
        )

    def test_o_help_e_a_doc_dizem_o_padrao_novo(self) -> None:
        texto = INSTALL.read_text(encoding="utf-8")
        assert "#   --dev " in texto
        doc = (RAIZ / "docs" / "usage" / "instalacao.md").read_text(encoding="utf-8")
        assert "| `--dev` |" in doc
        assert "| `--no-dev` |" not in doc


# ---------------------------------------------------------------------------
# O doctor não cobra o que o install decidiu não fazer.
# ---------------------------------------------------------------------------
DOCTOR = RAIZ / "scripts" / "doctor.sh"


def _sys_do_doctor(tmp_path: Path, *, bateria: bool) -> Path:
    """Um /sys: host xHCI em economia, teclado e Bluetooth em 'auto', DualSense em 'on'."""
    sysfs = tmp_path / "sys-doctor"
    host = sysfs / "bus" / "pci" / "devices" / "0000:00:14.0"
    (host / "power").mkdir(parents=True)
    (host / "class").write_text("0x0c0330\n", encoding="utf-8")
    (host / "power" / "control").write_text("auto\n", encoding="utf-8")
    for nome, vid, ctl in (("1-1", "046d", "auto"), ("1-2", "8087", "auto"), ("1-3", "054c", "on")):
        dev = sysfs / "bus" / "usb" / "devices" / nome
        (dev / "power").mkdir(parents=True)
        (dev / "idVendor").write_text(f"{vid}\n", encoding="utf-8")
        (dev / "power" / "control").write_text(f"{ctl}\n", encoding="utf-8")
    fonte = sysfs / "class" / "power_supply" / ("BAT0" if bateria else "ps-controller-battery-aa")
    fonte.mkdir(parents=True)
    return sysfs


def _doctor_roda(tmp_path: Path, funcao: str, *, bateria: bool) -> str:
    sysfs = _sys_do_doctor(tmp_path, bateria=bateria)
    vazio = tmp_path / "vazio"
    vazio.write_text("", encoding="utf-8")
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_path),
        "HEFESTO_DOCTOR_SYS": str(sysfs),
        "HEFESTO_DOCTOR_CMDLINE": str(vazio),
        "HEFESTO_DOCTOR_KERNELSTUB": str(vazio),
        "HEFESTO_DOCTOR_GRUB": str(vazio),
        "HEFESTO_DOCTOR_KERNEL_CMDLINE": str(tmp_path / "nao-ha"),
    }
    r = subprocess.run(
        [BASH, "-c", f'source "{DOCTOR}"; QUIET=0; {funcao}'],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=env,
    )
    return r.stdout


class TestODoctorSabeDaBateria:
    def test_com_bateria_o_host_em_economia_nao_e_aviso(self, tmp_path: Path) -> None:
        saida = _doctor_roda(tmp_path, "check_usb_power_hosts", bateria=True)
        assert "[WARN]" not in saida, saida
        assert "tem bateria" in saida

    def test_sem_bateria_o_host_em_economia_segue_aviso(self, tmp_path: Path) -> None:
        saida = _doctor_roda(tmp_path, "check_usb_power_hosts", bateria=False)
        assert "[WARN] host(s) USB em economia" in saida, saida

    def test_com_bateria_so_o_controle_e_cobrado(self, tmp_path: Path) -> None:
        saida = _doctor_roda(tmp_path, "check_usb_power_devices", bateria=True)
        assert "[WARN]" not in saida, saida
        assert "2 outro(s) device(s) em 'auto'" in saida

    def test_com_bateria_o_controle_em_economia_segue_aviso(self, tmp_path: Path) -> None:
        sysfs = _sys_do_doctor(tmp_path, bateria=True)
        (sysfs / "bus" / "usb" / "devices" / "1-3" / "power" / "control").write_text("auto\n")
        r = subprocess.run(
            [BASH, "-c", f'source "{DOCTOR}"; QUIET=0; check_usb_power_devices'],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "HEFESTO_DOCTOR_SYS": str(sysfs)},
        )
        esperado = "[WARN] economia de energia ATIVA em 1 device(s) USB: 1-3 (054c"
        assert esperado in r.stdout, r.stdout

    def test_sem_bateria_todo_device_em_economia_e_aviso(self, tmp_path: Path) -> None:
        saida = _doctor_roda(tmp_path, "check_usb_power_devices", bateria=False)
        assert "[WARN] economia de energia ATIVA em 2 device(s)" in saida, saida

    def test_com_bateria_o_autosuspend_ausente_nao_e_aviso_e_os_quirks_seguem(
        self, tmp_path: Path
    ) -> None:
        saida = _doctor_roda(tmp_path, "check_cmdline_platform", bateria=True)
        assert "[WARN] cmdline: usbcore.autosuspend=-1" not in saida, saida
        assert "usbcore.autosuspend=-1 fica de fora, de propósito" in saida
        assert "[WARN] cmdline: 054c:0ce6:gn ausente" in saida

    def test_sem_bateria_o_autosuspend_ausente_segue_aviso(self, tmp_path: Path) -> None:
        saida = _doctor_roda(tmp_path, "check_cmdline_platform", bateria=False)
        assert "[WARN] cmdline: usbcore.autosuspend=-1 ausente" in saida, saida

    def test_sem_carregador_conhecido_o_doctor_da_o_token_e_nao_manda_reinstalar(
        self, tmp_path: Path,
    ) -> None:
        """O-CMDLINE-DO-DUALSENSE-SO-SE-ESCREVE-NO-KERNELSTUB-01: sem onde escrever."""
        sysfs = _sys_do_doctor(tmp_path, bateria=False)
        nada = str(tmp_path / "nao-ha")
        r = subprocess.run(
            [BASH, "-c", f'source "{DOCTOR}"; QUIET=0; check_cmdline_platform'],
            capture_output=True, text=True, timeout=60, check=False,
            env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "HEFESTO_DOCTOR_SYS": str(sysfs),
                 "HEFESTO_DOCTOR_CMDLINE": nada, "HEFESTO_DOCTOR_KERNELSTUB": nada,
                 "HEFESTO_DOCTOR_GRUB": nada, "HEFESTO_DOCTOR_KERNEL_CMDLINE": nada},
        )
        assert "[WARN] cmdline: 054c:0ce6:gn ausente" not in r.stdout, r.stdout
        assert "ponha à mão no cmdline do kernel usbcore.quirks=054c:0ce6:gn" in r.stdout, r.stdout
        assert "ponha à mão no cmdline do kernel usbcore.autosuspend=-1" in r.stdout, r.stdout

    def test_o_doctor_le_o_proximo_boot_no_etc_kernel_cmdline(self, tmp_path: Path) -> None:
        sysfs = _sys_do_doctor(tmp_path, bateria=False)
        nada = str(tmp_path / "nao-ha")
        kcmd = tmp_path / "kernel-cmdline"
        kcmd.write_text("rw usbcore.autosuspend=-1 usbcore.quirks=054c:0ce6:gn\n", encoding="utf-8")
        r = subprocess.run(
            [BASH, "-c", f'source "{DOCTOR}"; QUIET=0; check_cmdline_platform'],
            capture_output=True, text=True, timeout=60, check=False,
            env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "HEFESTO_DOCTOR_SYS": str(sysfs),
                 "HEFESTO_DOCTOR_CMDLINE": nada, "HEFESTO_DOCTOR_KERNELSTUB": nada,
                 "HEFESTO_DOCTOR_GRUB": nada, "HEFESTO_DOCTOR_KERNEL_CMDLINE": str(kcmd)},
        )
        assert "054c:0ce6:gn agendado mas NÃO ativo" in r.stdout, r.stdout

    def test_o_n_no_pad_virtual_e_defeito_no_doctor(self, tmp_path: Path) -> None:
        """14/10/2026: o 054c:0df2:gn espera 200 ms por pedido ao pad virtual."""
        saida = _doctor_roda(tmp_path, "check_cmdline_pad_virtual", bateria=False)
        assert "054c:0df2" not in saida, "sem o token velho o doctor não fala dele"
        sysq = tmp_path / "sys-doctor" / "module" / "usbcore" / "parameters" / "quirks"
        sysq.parent.mkdir(parents=True)
        sysq.write_text("054c:0ce6:gn,054c:0df2:gn\n", encoding="utf-8")
        r = subprocess.run(
            [BASH, "-c", f'source "{DOCTOR}"; QUIET=0; check_cmdline_pad_virtual'],
            capture_output=True, text=True, timeout=60, check=False,
            env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
                 "HEFESTO_DOCTOR_SYS": str(tmp_path / "sys-doctor"),
                 "HEFESTO_DOCTOR_CMDLINE": str(tmp_path / "vazio"),
                 "HEFESTO_DOCTOR_KERNELSTUB": str(tmp_path / "vazio"),
                 "HEFESTO_DOCTOR_GRUB": str(tmp_path / "vazio")},
        )
        assert "[WARN] DEFEITO: cmdline: 054c:0df2:gn (no sysfs)" in r.stdout, r.stdout
        assert "200 ms por pedido" in r.stdout
        assert "reinicie o computador" in r.stdout, "com o bootloader curado, o conselho é o reboot"

    def test_depois_do_install_o_doctor_manda_reiniciar_e_nao_reinstalar(
        self, tmp_path: Path,
    ) -> None:
        """O install curou o bootloader; o boot de agora ainda traz o 0df2:gn.

        MORDIDA: com o conselho único de antes, a linha deste boot sozinha dava
        DEFEITO com «rode ./install.sh», que ela já rodou.
        """
        boot = tmp_path / "cmdline"
        boot.write_text("quiet usbcore.quirks=054c:0ce6:gn,054c:0df2:gn\n", encoding="utf-8")
        stub = tmp_path / "kernelstub.json"
        stub.write_text('{"user": {"kernel_options": ["usbcore.quirks=054c:0df2:gn"]}}\n',
                        encoding="utf-8")

        def _roda(kernelstub: Path) -> str:
            return subprocess.run(
                [BASH, "-c", f'source "{DOCTOR}"; QUIET=0; check_cmdline_pad_virtual'],
                capture_output=True, text=True, timeout=60, check=False,
                env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
                     "HEFESTO_DOCTOR_SYS": str(tmp_path / "sys-vazio"),
                     "HEFESTO_DOCTOR_CMDLINE": str(boot),
                     "HEFESTO_DOCTOR_KERNELSTUB": str(kernelstub),
                     "HEFESTO_DOCTOR_GRUB": str(tmp_path / "vazio")},
            ).stdout

        so_o_boot = _roda(tmp_path / "vazio")
        assert "DEFEITO" not in so_o_boot, so_o_boot
        assert "some no próximo boot" in so_o_boot, so_o_boot
        com_o_bootloader = _roda(stub)
        defeito = "[WARN] DEFEITO: cmdline: 054c:0df2:gn (neste boot no kernelstub)"
        assert defeito in com_o_bootloader, com_o_bootloader

    def test_a_pergunta_do_doctor_e_a_do_install(self) -> None:
        """O mesmo glob nos dois: um BAT2 contaria num e não no outro."""
        doctor = DOCTOR.read_text(encoding="utf-8")
        lib = LIB.read_text(encoding="utf-8")
        assert "/class/power_supply/BAT*" in doctor
        assert "/class/power_supply/BAT*" in lib
