"""A-ENERGIA-DE-NOTEBOOK-NUM-DESKTOP-01 — o install pergunta pelo modo desempenho.

Decisão dela (02/10/2026): o install pergunta; `--desempenho` / `--sem-desempenho`
respondem sem perguntar; sem TTY vale o padrão (sim no desktop, não no notebook
com bateria); cada ajuste é um arquivo permanente; o uninstall desfaz; o doctor
diz o estado de cada um. Só entra o que a prova no aparelho mostrou: o perfil de
energia é decisão dela, e os três ajustes de hipótese (NVIDIA, áudio HDA, ASPM)
nascem escritos e DESLIGADOS.

Tudo roda em prefixo de mentira (`HEFESTO_DESEMPENHO_RAIZ`): sem root, sem
systemctl, sem tocar em /etc nem em /sys.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "desempenho.sh"
DOCTOR = RAIZ / "scripts" / "doctor.sh"
INSTALL = RAIZ / "install.sh"
UNINSTALL = RAIZ / "uninstall.sh"
LIB = RAIZ / "scripts" / "lib" / "camada_de_maquina.sh"
ASSETS = RAIZ / "assets" / "desempenho"

UNIT = "etc/systemd/system/hefesto-desempenho.service"
WANTS = "etc/systemd/system/multi-user.target.wants/hefesto-desempenho.service"
NVIDIA = "etc/modprobe.d/hefesto-desempenho-nvidia.conf"
AUDIO = "etc/modprobe.d/hefesto-desempenho-audio.conf"
ASPM = "etc/tmpfiles.d/hefesto-desempenho-aspm.conf"
OS_QUATRO = (NVIDIA, AUDIO, ASPM)
TODOS = (UNIT, WANTS, NVIDIA, AUDIO, ASPM)


class Maquina:
    """Uma máquina de mentira: /etc num prefixo, /sys, /proc e os binários de energia."""

    def __init__(
        self,
        tmp: Path,
        *,
        gerenciador: str | None = "system76-power",
        nvidia: bool = False,
        hda: bool = False,
        aspm: bool = False,
        bateria: bool = False,
        perfil_agora: str = "Balanced",
        ppd_com_performance: bool = True,
    ) -> None:
        self.raiz = tmp / "raiz"
        self.sys = tmp / "sys"
        self.proc = tmp / "proc"
        self.bin = tmp / "bin"
        for pasta in (self.raiz, self.sys, self.proc, self.bin):
            pasta.mkdir(parents=True)
        if gerenciador == "system76-power":
            self._cliente("system76-power", f'echo "Power Profile: {perfil_agora}"\n')
        elif gerenciador == "power-profiles-daemon":
            # Como o real: `get` diz o perfil, `list` só traz «performance» quando
            # um driver da máquina o sustenta.
            desempenho = (
                "  performance:\n    CpuDriver:\tamd_pstate\n    Degraded:   no\n\n"
                if ppd_com_performance
                else ""
            )
            self._cliente(
                "powerprofilesctl",
                'case "$1" in\n'
                f'  get) echo "{perfil_agora.lower()}" ;;\n'
                f"  list) printf '{desempenho}* balanced:\\n    CpuDriver:\\tamd_pstate\\n\\n"
                "  power-saver:\\n    CpuDriver:\\tamd_pstate\\n' ;;\n"
                "esac\n",
            )
        if nvidia:
            (self.sys / "module/nvidia").mkdir(parents=True)
            (self.proc / "driver/nvidia").mkdir(parents=True)
            (self.proc / "driver/nvidia/params").write_text(
                "DynamicPowerManagement: 3\nDynamicPowerManagementVideoMemoryThreshold: 200\n",
                encoding="utf-8",
            )
        if hda:
            par = self.sys / "module/snd_hda_intel/parameters"
            par.mkdir(parents=True)
            (par / "power_save").write_text("1\n", encoding="utf-8")
            (par / "power_save_controller").write_text("Y\n", encoding="utf-8")
        if aspm:
            par = self.sys / "module/pcie_aspm/parameters"
            par.mkdir(parents=True)
            (par / "policy").write_text(
                "[default] performance powersave powersupersave\n", encoding="utf-8"
            )
        energia = self.sys / "class/power_supply"
        energia.mkdir(parents=True)
        # A bateria de um controle não é a do computador e não conta.
        (energia / "ps-controller-battery-aa:bb:cc:00:00:01").mkdir()
        if bateria:
            (energia / "BAT0").mkdir()
        (self.proc / "stat").write_text("cpu 1 2 3\nbtime 1000000000\n", encoding="utf-8")

    def _cliente(self, nome: str, corpo: str) -> None:
        alvo = self.bin / nome
        alvo.write_text("#!/bin/sh\n" + corpo, encoding="utf-8")
        alvo.chmod(0o755)

    def env(self, **extra: str) -> dict[str, str]:
        amb = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.raiz.parent / "casa"),
            "LC_ALL": "C.UTF-8",
            "HEFESTO_DESEMPENHO_RAIZ": str(self.raiz),
            "HEFESTO_DESEMPENHO_SYS": str(self.sys),
            "HEFESTO_SYSFS": str(self.sys),
            "HEFESTO_DESEMPENHO_PROC": str(self.proc),
            "HEFESTO_PROC": str(self.proc),
            "HEFESTO_DESEMPENHO_BIN": str(self.bin),
        }
        amb.update(extra)
        return amb

    def escritos(self) -> set[str]:
        return {
            str(p.relative_to(self.raiz))
            for p in self.raiz.rglob("*")
            if p.is_file() or p.is_symlink()
        }


def _roda(
    maquina: Maquina, *args: str, script: Path = SCRIPT, **extra: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [BASH, str(script), *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=maquina.env(**extra),
        cwd=str(RAIZ),
    )


# ---------------------------------------------------------------------------
# O mecanismo: scripts/desempenho.sh
# ---------------------------------------------------------------------------


class TestOMecanismo:
    def test_o_perfil_e_o_unico_que_entra_sem_prova(self, tmp_path: Path) -> None:
        m = Maquina(tmp_path, nvidia=True, hda=True, aspm=True)
        r = _roda(m, "aplicar")
        assert r.returncode == 0, r.stdout + r.stderr
        assert m.escritos() == {UNIT, WANTS}, m.escritos()
        for id_ in ("nvidia", "audio", "aspm"):
            assert f"{id_}: não aplicado, a provar" in r.stdout, r.stdout

    def test_a_unit_pede_performance_ao_system76_power(self, tmp_path: Path) -> None:
        m = Maquina(tmp_path)
        _roda(m, "aplicar")
        unit = (m.raiz / UNIT).read_text(encoding="utf-8")
        assert "ExecStart=/usr/bin/env system76-power profile performance" in unit
        assert "After=com.system76.PowerDaemon.service" in unit
        assert "__" not in unit, "sobrou marcador sem trocar"
        assert (m.raiz / WANTS).is_symlink()

    def test_a_unit_pede_performance_ao_power_profiles_daemon(self, tmp_path: Path) -> None:
        m = Maquina(tmp_path, gerenciador="power-profiles-daemon")
        _roda(m, "aplicar")
        unit = (m.raiz / UNIT).read_text(encoding="utf-8")
        assert "ExecStart=/usr/bin/env powerprofilesctl set performance" in unit
        assert "After=power-profiles-daemon.service" in unit
        codigo = "\n".join(ln for ln in unit.splitlines() if not ln.startswith("#"))
        assert "system76" not in codigo

    def test_ppd_sem_o_perfil_performance_e_pulado_e_dito_sem_erro(self, tmp_path: Path) -> None:
        # Sem driver que sustente «performance», a unit falharia a cada boot.
        m = Maquina(tmp_path, gerenciador="power-profiles-daemon", ppd_com_performance=False)
        r = _roda(m, "aplicar")
        assert r.returncode == 0, r.stdout + r.stderr
        assert m.escritos() == set()
        assert "perfil: pulado, o power-profiles-daemon desta máquina não oferece" in r.stdout

    def test_sem_gerenciador_o_perfil_e_pulado_e_dito_sem_erro(self, tmp_path: Path) -> None:
        m = Maquina(tmp_path, gerenciador=None, nvidia=True)
        r = _roda(m, "aplicar")
        assert r.returncode == 0, r.stdout + r.stderr
        assert m.escritos() == set()
        assert "perfil: pulado, sem system76-power nem power-profiles-daemon" in r.stdout

    def test_os_tres_provados_gravam_os_arquivos_certos(self, tmp_path: Path) -> None:
        m = Maquina(tmp_path, nvidia=True, hda=True, aspm=True)
        r = _roda(m, "aplicar", HEFESTO_DESEMPENHO_PROVADOS="nvidia audio aspm")
        assert r.returncode == 0, r.stdout + r.stderr
        assert m.escritos() == set(TODOS), m.escritos()
        assert "NVreg_DynamicPowerManagement=0x00" in (m.raiz / NVIDIA).read_text(encoding="utf-8")
        assert "power_save=0 power_save_controller=N" in (m.raiz / AUDIO).read_text(
            encoding="utf-8"
        )
        assert "performance" in (m.raiz / ASPM).read_text(encoding="utf-8")

    def test_o_que_a_maquina_nao_tem_e_pulado_e_dito(self, tmp_path: Path) -> None:
        """AMD ou Intel na GPU, áudio de outra marca, kernel sem ASPM: sem erro."""
        m = Maquina(tmp_path, nvidia=False, hda=False, aspm=False)
        r = _roda(m, "aplicar", HEFESTO_DESEMPENHO_PROVADOS="nvidia audio aspm")
        assert r.returncode == 0, r.stdout + r.stderr
        assert m.escritos() == {UNIT, WANTS}
        assert "nvidia: pulado, sem o driver NVIDIA" in r.stdout
        assert "audio: pulado, sem snd_hda_intel" in r.stdout
        assert "aspm: pulado, este kernel não expõe" in r.stdout

    def test_pedido_explicito_vale_sem_estar_na_lista_dos_provados(self, tmp_path: Path) -> None:
        m = Maquina(tmp_path, nvidia=True, hda=True, aspm=True)
        _roda(m, "aplicar", "nvidia")
        assert m.escritos() == {NVIDIA}

    def test_id_desconhecido_e_dito_e_nao_derruba(self, tmp_path: Path) -> None:
        m = Maquina(tmp_path)
        r = _roda(m, "aplicar", "turbo")
        assert r.returncode == 0
        assert "ajuste desconhecido: turbo" in r.stdout

    def test_aplicar_duas_vezes_da_o_mesmo_disco(self, tmp_path: Path) -> None:
        m = Maquina(tmp_path, nvidia=True, hda=True, aspm=True)
        _roda(m, "aplicar", HEFESTO_DESEMPENHO_PROVADOS="nvidia audio aspm")
        antes = {p: (m.raiz / p).read_bytes() for p in (*OS_QUATRO, UNIT)}
        _roda(m, "aplicar", HEFESTO_DESEMPENHO_PROVADOS="nvidia audio aspm")
        assert antes == {p: (m.raiz / p).read_bytes() for p in (*OS_QUATRO, UNIT)}

    def test_o_uninstall_apaga_tudo(self, tmp_path: Path) -> None:
        """O `remover` é o que o uninstall chama: o disco volta a ficar vazio."""
        m = Maquina(tmp_path, nvidia=True, hda=True, aspm=True)
        _roda(m, "aplicar", HEFESTO_DESEMPENHO_PROVADOS="nvidia audio aspm")
        assert m.escritos() == set(TODOS)
        r = _roda(m, "remover")
        assert r.returncode == 0, r.stdout + r.stderr
        assert m.escritos() == set(), m.escritos()
        again = _roda(m, "remover")
        assert again.returncode == 0
        assert "nenhum ajuste do modo desempenho estava instalado" in again.stdout

    def test_o_uninstall_chama_o_mesmo_dono(self) -> None:
        texto = UNINSTALL.read_text(encoding="utf-8")
        assert 'bash "${ROOT_DIR}/scripts/desempenho.sh" remover' in texto
        for arq in (
            "hefesto-desempenho.service",
            "hefesto-desempenho-nvidia.conf",
            "hefesto-desempenho-audio.conf",
            "hefesto-desempenho-aspm.conf",
        ):
            assert arq in texto, f"o uninstall não olha {arq} (nem para pedir a credencial)"

    def test_o_uninstall_pede_a_credencial_por_cada_arquivo(self) -> None:
        # Sem a credencial pedida no começo, o bloco cai no «sudo indisponível» e
        # os arquivos de root ficam: cada um tem de armar o `_NEEDS_SUDO`.
        texto = UNINSTALL.read_text(encoding="utf-8")
        armam = " ".join(
            re.findall(r"\[\[ -e (?:[^\]]|\](?!\]))*\]\] && _NEEDS_SUDO=1", texto)
        )
        for arq in (
            "/etc/systemd/system/hefesto-desempenho.service",
            "/etc/modprobe.d/hefesto-desempenho-nvidia.conf",
            "/etc/modprobe.d/hefesto-desempenho-audio.conf",
            "/etc/tmpfiles.d/hefesto-desempenho-aspm.conf",
        ):
            assert arq in armam, f"{arq} não arma o _NEEDS_SUDO do uninstall"


# ---------------------------------------------------------------------------
# A decisão: a pergunta, as flags e o padrão sem TTY — pela função do install
# ---------------------------------------------------------------------------


def _ask_yn_do_install() -> str:
    texto = INSTALL.read_text(encoding="utf-8")
    achado = re.search(r"^ask_yn\(\) \{.*?^\}\n", texto, re.M | re.S)
    assert achado, "perdi a função ask_yn do install.sh"
    return achado.group(0)


def _roda_o_passo(
    maquina: Maquina, tmp: Path, *, pedido: str = "", auto_yes: int = 0, provados: str = ""
) -> tuple[str, set[str]]:
    """Roda `install_desempenho_host` da lib, com o `ask_yn` de verdade e sem TTY."""
    prelude = (
        "set -euo pipefail\n"
        "DRY_RUN=0\n"
        f"{_ask_yn_do_install()}\n"
        f'ROOT_DIR="{RAIZ}"\n'
        f'source "{LIB}"\n'
        f'DESEMPENHO_PEDIDO="{pedido}"\n'
        f'DESEMPENHO_PROVADOS="{provados}"\n'
        f"AUTO_YES={auto_yes}\n"
        "install_desempenho_host\n"
    )
    r = subprocess.run(
        [BASH, "-c", prelude],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=maquina.env(),
        stdin=subprocess.DEVNULL,
        cwd=str(RAIZ),
    )
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout + r.stderr, maquina.escritos()


class TestADecisao:
    def test_desempenho_escreve_os_arquivos_do_perfil(self, tmp_path: Path) -> None:
        m = Maquina(tmp_path, bateria=True)  # até no notebook: a flag manda
        _, escritos = _roda_o_passo(m, tmp_path, pedido="sim")
        assert escritos == {UNIT, WANTS}

    def test_sem_desempenho_nao_escreve_nada(self, tmp_path: Path) -> None:
        m = Maquina(tmp_path, bateria=False)  # até no desktop: a flag manda
        saida, escritos = _roda_o_passo(m, tmp_path, pedido="sem", auto_yes=1)
        assert escritos == set()
        assert "modo desempenho não pedido" in saida

    def test_sem_tty_no_desktop_o_padrao_e_sim(self, tmp_path: Path) -> None:
        m = Maquina(tmp_path, bateria=False)
        saida, escritos = _roda_o_passo(m, tmp_path, auto_yes=1)
        assert escritos == {UNIT, WANTS}
        assert "sem bateria" in saida

    def test_sem_tty_no_notebook_o_padrao_e_nao(self, tmp_path: Path) -> None:
        m = Maquina(tmp_path, bateria=True)
        saida, escritos = _roda_o_passo(m, tmp_path, auto_yes=1)
        assert escritos == set()
        assert "com bateria" in saida

    def test_sem_yes_e_sem_tty_vale_o_mesmo_padrao(self, tmp_path: Path) -> None:
        desktop = Maquina(tmp_path / "d", bateria=False)
        notebook = Maquina(tmp_path / "n", bateria=True)
        assert _roda_o_passo(desktop, tmp_path, auto_yes=0)[1] == {UNIT, WANTS}
        assert _roda_o_passo(notebook, tmp_path, auto_yes=0)[1] == set()

    def test_a_bateria_do_controle_nao_faz_o_desktop_virar_notebook(self, tmp_path: Path) -> None:
        """A Maquina já traz `ps-controller-battery-*`: não pode contar."""
        m = Maquina(tmp_path, bateria=False)
        assert any(
            p.name.startswith("ps-controller-battery")
            for p in (m.sys / "class/power_supply").iterdir()
        )
        assert _roda_o_passo(m, tmp_path, auto_yes=1)[1] == {UNIT, WANTS}

    def test_os_provados_entram_quando_a_prova_os_liga(self, tmp_path: Path) -> None:
        m = Maquina(tmp_path, nvidia=True, hda=True, aspm=True)
        saida, escritos = _roda_o_passo(m, tmp_path, pedido="sim", provados="nvidia audio aspm")
        assert escritos == set(TODOS)
        assert "Reinicie o computador" not in saida  # o fecho é do install; o passo só anota

    def test_sem_a_prova_os_tres_ficam_de_fora(self, tmp_path: Path) -> None:
        m = Maquina(tmp_path, nvidia=True, hda=True, aspm=True)
        _, escritos = _roda_o_passo(m, tmp_path, pedido="sim")
        assert not escritos & set(OS_QUATRO)

    def test_com_no_udev_nada_e_escrito(self, tmp_path: Path) -> None:
        m = Maquina(tmp_path)
        prelude = (
            "set -euo pipefail\n"
            f'ROOT_DIR="{RAIZ}"\nSKIP_UDEV=1\nDESEMPENHO_PEDIDO=sim\n'
            f'source "{LIB}"\ninstall_desempenho_host\n'
        )
        r = subprocess.run(
            [BASH, "-c", prelude],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env=m.env(),
            cwd=str(RAIZ),
        )
        assert r.returncode == 0, r.stdout + r.stderr
        assert "pulado (--no-udev)" in r.stdout
        assert m.escritos() == set()


# ---------------------------------------------------------------------------
# O ensaio e as flags do install (o `--dry-run` real, num lar de mentira)
# ---------------------------------------------------------------------------


def _ensaio(tmp: Path, m: Maquina, *flags: str) -> str:
    from tests.unit.test_o_ensaio_do_install_nao_escreve import _bancada

    _lar, _diario, amb = _bancada(tmp)
    amb["HEFESTO_DESEMPENHO_SYS"] = str(m.sys)
    amb["HEFESTO_DESEMPENHO_RAIZ"] = str(m.raiz)
    r = subprocess.run(
        [BASH, str(INSTALL), "--dry-run", *flags],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=amb,
        cwd=str(RAIZ),
        stdin=subprocess.DEVNULL,
    )
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    return r.stdout


class TestOEnsaioEAsFlags:
    def test_as_duas_flags_estao_no_parser_e_no_help(self) -> None:
        texto = INSTALL.read_text(encoding="utf-8")
        assert '--desempenho)         DESEMPENHO_PEDIDO="sim"' in texto
        assert '--sem-desempenho)     DESEMPENHO_PEDIDO="sem"' in texto
        ajuda = subprocess.run(
            [BASH, str(INSTALL), "--help"], capture_output=True, text=True, timeout=30, check=False
        ).stdout
        assert "--desempenho" in ajuda and "--sem-desempenho" in ajuda

    def test_com_a_flag_o_plano_tem_a_unit_e_nao_tem_os_tres(self, tmp_path: Path) -> None:
        m = Maquina(tmp_path, bateria=True)
        saida = _ensaio(tmp_path, m, "--desempenho")
        faria = "\n".join(ln for ln in saida.splitlines() if "FARIA" in ln)
        assert "hefesto-desempenho.service" in faria, saida[-3000:]
        assert "hefesto-desempenho-nvidia.conf" not in faria
        assert "o doctor os diz «a provar»" in saida

    def test_com_sem_desempenho_o_plano_nao_tem_nada(self, tmp_path: Path) -> None:
        m = Maquina(tmp_path, bateria=False)
        saida = _ensaio(tmp_path, m, "--sem-desempenho")
        assert "hefesto-desempenho" not in "\n".join(
            ln for ln in saida.splitlines() if "FARIA" in ln
        )
        assert "modo desempenho (--sem-desempenho)" in saida

    def test_o_ensaio_assume_o_padrao_da_maquina(self, tmp_path: Path) -> None:
        desktop = _ensaio(tmp_path / "d", Maquina(tmp_path / "d", bateria=False))
        notebook = _ensaio(tmp_path / "n", Maquina(tmp_path / "n", bateria=True))
        assert "hefesto-desempenho.service" in "\n".join(
            ln for ln in desktop.splitlines() if "FARIA" in ln
        )
        assert "perguntaria" in desktop
        assert "a resposta assumida é não" in notebook
        assert "hefesto-desempenho.service" not in "\n".join(
            ln for ln in notebook.splitlines() if "FARIA" in ln
        )

    def test_com_no_udev_o_plano_pula(self, tmp_path: Path) -> None:
        saida = _ensaio(tmp_path, Maquina(tmp_path), "--no-udev", "--desempenho")
        assert "modo desempenho (--no-udev)" in saida


# ---------------------------------------------------------------------------
# O doctor: o estado de cada ajuste, com o comando de ligar e de desligar
# ---------------------------------------------------------------------------


def _doctor(m: Maquina, **extra: str) -> str:
    r = subprocess.run(
        [BASH, "-c", f'source "{DOCTOR}"; check_desempenho'],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=m.env(**extra),
        cwd=str(RAIZ),
    )
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout + r.stderr


def _linha(saida: str, rotulo: str) -> str:
    achadas = [ln for ln in saida.splitlines() if rotulo in ln]
    assert len(achadas) == 1, (rotulo, saida)
    return achadas[0]


class TestODoctor:
    def test_nada_instalado_diz_nao_pedido_e_a_provar_com_os_comandos(self, tmp_path: Path) -> None:
        m = Maquina(tmp_path, nvidia=True, hda=True, aspm=True)
        saida = _doctor(m)
        assert "[WARN]" not in saida and "[FAIL]" not in saida
        perfil = _linha(saida, "perfil de energia")
        assert "não pedido" in perfil and "./install.sh --desempenho" in perfil
        for rotulo, conf in (
            ("GPU NVIDIA", "hefesto-desempenho-nvidia.conf"),
            ("áudio da placa-mãe", "hefesto-desempenho-audio.conf"),
            ("PCIe", "hefesto-desempenho-aspm.conf"),
        ):
            linha = _linha(saida, rotulo)
            assert "não aplicado: a provar" in linha, linha
            assert f"sudo install -Dm644 {RAIZ}/assets/desempenho/{conf}" in linha, linha
            assert "sudo rm /etc/" in linha and conf in linha, linha

    def test_perfil_ja_em_performance_mas_sem_a_unit_diz_que_nada_o_guarda(
        self, tmp_path: Path
    ) -> None:
        m = Maquina(tmp_path, perfil_agora="Performance")
        assert "nada o guarda depois do boot" in _linha(_doctor(m), "perfil de energia")

    def test_aplicado_passa_com_o_valor_de_agora(self, tmp_path: Path) -> None:
        m = Maquina(tmp_path, perfil_agora="Performance")
        _roda(m, "aplicar")
        linha = _linha(_doctor(m), "perfil de energia")
        assert linha.startswith("[ OK ]") and "aplicado (agora: performance)" in linha
        assert "systemctl disable --now hefesto-desempenho.service" in linha

    def test_perfil_gravado_e_depois_trocado_no_menu_e_estado_nao_alarme(
        self, tmp_path: Path
    ) -> None:
        # O perfil não é arquivo de módulo: trocá-lo no menu de energia depois do
        # boot é direito de quem usa. O doctor diz o estado e o caminho de volta,
        # em qualquer época de gravação da unit (ela roda na hora do install).
        m = Maquina(tmp_path, perfil_agora="Balanced")
        _roda(m, "aplicar")
        for boot, mtime in (("1000", 100), ("1", None)):
            if mtime is not None:
                os.utime(m.raiz / UNIT, (mtime, mtime))
            linha = _linha(_doctor(m, HEFESTO_DESEMPENHO_BOOT=boot), "perfil de energia")
            assert not linha.startswith(("[WARN]", "[FAIL]", "[ OK ]")), linha
            assert "agora está balanced" in linha and "PRÓXIMO BOOT" not in linha, linha
            assert "systemctl restart hefesto-desempenho.service" in linha, linha

    def test_ppd_sem_o_perfil_performance_o_doctor_diz_pulado(self, tmp_path: Path) -> None:
        m = Maquina(tmp_path, gerenciador="power-profiles-daemon", ppd_com_performance=False)
        linha = _linha(_doctor(m), "perfil de energia")
        assert not linha.startswith("[WARN]") and "pulado" in linha, linha
        assert "não oferece o perfil performance" in linha, linha

    def test_arquivo_gravado_depois_do_boot_diz_proximo_boot(self, tmp_path: Path) -> None:
        m = Maquina(tmp_path, nvidia=True)
        _roda(m, "aplicar", "nvidia")
        # gravada DEPOIS do boot (agora > 1): ainda não teve um boot para valer
        linha = _linha(_doctor(m, HEFESTO_DESEMPENHO_BOOT="1"), "GPU NVIDIA")
        assert "PRÓXIMO BOOT" in linha and not linha.startswith("[WARN]"), linha
        # gravada ANTES do boot e o driver segue com 3: alguém desfez
        os.utime(m.raiz / NVIDIA, (100, 100))
        linha = _linha(_doctor(m, HEFESTO_DESEMPENHO_BOOT="1000"), "GPU NVIDIA")
        assert linha.startswith("[WARN]") and "DESFEITO" in linha, linha

    def test_arquivo_gravado_e_valor_igual_passa(self, tmp_path: Path) -> None:
        m = Maquina(tmp_path, nvidia=True, hda=True, aspm=True)
        _roda(m, "aplicar", "nvidia", "audio", "aspm")
        (m.proc / "driver/nvidia/params").write_text(
            "DynamicPowerManagement: 0\n", encoding="utf-8"
        )
        (m.sys / "module/snd_hda_intel/parameters/power_save").write_text("0\n", encoding="utf-8")
        (m.sys / "module/snd_hda_intel/parameters/power_save_controller").write_text(
            "N\n", encoding="utf-8"
        )
        (m.sys / "module/pcie_aspm/parameters/policy").write_text(
            "default [performance] powersave\n", encoding="utf-8"
        )
        saida = _doctor(m, HEFESTO_DESEMPENHO_BOOT="1")  # o valor igual passa em qualquer época
        for rotulo in ("GPU NVIDIA", "áudio da placa-mãe", "PCIe"):
            assert _linha(saida, rotulo).startswith("[ OK ]"), saida

    def test_o_que_a_maquina_nao_tem_e_dito_sem_erro(self, tmp_path: Path) -> None:
        m = Maquina(tmp_path, gerenciador=None)
        saida = _doctor(m)
        assert "[WARN]" not in saida and "[FAIL]" not in saida
        assert "perfil de energia: pulado, sem system76-power nem power-profiles-daemon" in saida
        assert "GPU NVIDIA: pulado" in saida
        assert "áudio da placa-mãe: pulado" in saida
        assert "ASPM do PCIe: pulado" in saida

    def test_o_main_do_doctor_pergunta(self) -> None:
        assert "\n    check_desempenho\n" in DOCTOR.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Os quatro lugares falam do mesmo
# ---------------------------------------------------------------------------


class TestOsQuatroLugaresFalamDoMesmo:
    def _provados(self, arquivo: Path, var: str) -> str:
        achado = re.search(rf'^{var}="([^"]*)"', arquivo.read_text(encoding="utf-8"), re.M)
        assert achado, f"{arquivo.name} perdeu {var}"
        return achado.group(1).strip()

    def test_o_espelho_do_doctor_e_a_lista_do_install_estao_de_acordo(self) -> None:
        no_install = self._provados(INSTALL, "DESEMPENHO_PROVADOS")
        no_doctor = self._provados(DOCTOR, "_DESEMPENHO_PROVADOS")
        assert no_install == no_doctor, (
            f"o install liga [{no_install}]; o doctor diz «a provar» para o que "
            f"não está em [{no_doctor}]"
        )

    def test_a_lista_dos_provados_so_tem_ids_que_o_roteiro_conhece(self) -> None:
        ids = subprocess.run(
            [BASH, str(SCRIPT), "ids"], capture_output=True, text=True, timeout=30, check=True
        ).stdout.split()
        for id_ in self._provados(INSTALL, "DESEMPENHO_PROVADOS").split():
            assert id_ in ids

    @pytest.mark.parametrize(
        "arq",
        [
            "hefesto-desempenho.service",
            "hefesto-desempenho-nvidia.conf",
            "hefesto-desempenho-audio.conf",
            "hefesto-desempenho-aspm.conf",
        ],
    )
    def test_cada_arquivo_esta_no_roteiro_no_doctor_e_no_asset(self, arq: str) -> None:
        for dono in (SCRIPT, DOCTOR):
            assert arq in dono.read_text(encoding="utf-8"), f"{dono.name} não cita {arq}"
        assert (ASSETS / arq).is_file()

    def test_o_install_chama_o_passo_dos_dois_lados_da_cerca(self) -> None:
        texto = INSTALL.read_text(encoding="utf-8")
        assert len(re.findall(r"^\s*install_desempenho_host\s*$", texto, re.M)) == 2
        assert '"install_desempenho_host:desempenho"' in texto
