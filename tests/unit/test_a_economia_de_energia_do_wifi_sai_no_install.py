"""A economia de energia do Wi-Fi sai no install (23/10/2026).

O NetworkManager da distro liga `wifi.powersave = 3`, e o dongle rtw88 USB caiu
seis vezes num dia. O passo 3d-bis do `install.sh` deixou de ser opt-in: grava o
conf.d do NetworkManager e desliga a economia NA HORA, em cada interface que a
tem ligada, sem reconectar (um `nmcli connection up` derrubou a máquina no mesmo
dia). A régua roda o passo de verdade, com `sudo`, `iw`, `iwconfig` e `nmcli`
de mentira no PATH e um `/etc` de mentira: nenhum rádio, nenhum NetworkManager.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
ASSET = REPO_ROOT / "assets" / "NetworkManager" / "hefesto-wifi-powersave.conf"

FUNCOES = (
    "_wifi_ferramenta",
    "_wifi_interfaces",
    "_wifi_economia_ligada",
    "_wifi_comando_desliga",
    "_wifi_desliga_economia",
    "aplicar_wifi_powersave_off",
)
# O que um passo que não pode derrubar a conexão jamais chama.
PROIBIDOS = (
    "nmcli",
    "rfkill",
    "connection up",
    "device reapply",
    "general reload",
)
FERRAMENTAS = ("awk", "grep", "cmp", "install", "cat", "mkdir", "dirname", "sed", "true")


def _sem_comentarios(texto: str) -> str:
    linhas = [re.sub(r"(^|\s)#.*$", r"\1", linha) for linha in texto.splitlines()]
    return "\n".join(linhas)


def _extrai_funcao(nome: str) -> str:
    achou = re.search(rf"^{re.escape(nome)}\(\) \{{\n", INSTALL, re.MULTILINE)
    assert achou is not None, f"função {nome}() não encontrada no install.sh"
    fim = re.search(r"^\}$", INSTALL[achou.end() :], re.MULTILINE)
    assert fim is not None, f"fim de {nome}() não encontrado"
    return INSTALL[achou.start() : achou.end() + fim.end()]


def _stub(caminho: Path, corpo: str) -> None:
    caminho.write_text("#!/bin/sh\n" + corpo, encoding="utf-8")
    caminho.chmod(0o755)


class Cena:
    """Uma máquina de mentira: PATH só com dublês, `/etc` e rádio em tmp."""

    def __init__(self, base: Path, *, com_iw: bool = True, com_iwconfig: bool = False,
                 com_sudo: bool = True, iw_no_sbin: bool = False) -> None:
        self.base = base
        self.nm = base / "etc" / "NetworkManager"
        self.alvo = self.nm / "conf.d" / "hefesto-wifi-powersave.conf"
        self.chamadas = base / "chamadas.log"
        self.chamadas.write_text("", encoding="utf-8")
        self.estado = base / "estado"
        self.estado.mkdir()
        self.ifaces = base / "ifaces"
        self.ifaces.write_text("", encoding="utf-8")
        bin_ = base / "bin"
        bin_.mkdir()
        self.bin = bin_
        # O `/usr/sbin` de mentira: fora do PATH, como no usuário comum do Debian.
        self.sbin = base / "sbin"
        self.sbin.mkdir()
        for nome in FERRAMENTAS:
            real = shutil.which(nome)
            assert real, f"{nome} ausente na máquina de teste"
            (bin_ / nome).symlink_to(real)
        log = f'echo "$0 $*" >> "{self.chamadas}"\n'
        if com_sudo:
            _stub(
                bin_ / "sudo",
                log + '[ "$1" = "-n" ] && shift\nexec "$@"\n',
            )
        for nome in ("nmcli", "rfkill"):
            _stub(bin_ / nome, log + "exit 0\n")
        lista = f'while read -r i; do {{ARGS}}; done < "{self.ifaces}"\n'
        if com_iw:
            _stub(
                (self.sbin if iw_no_sbin else bin_) / "iw",
                log
                + f'est="{self.estado}"\n'
                + 'if [ "$1" = dev ] && [ -z "$2" ]; then\n'
                + "  "
                + lista.replace("{ARGS}", 'printf "phy#0\\n\\tInterface %s\\n" "$i"')
                + 'elif [ "$3" = get ]; then\n'
                + '  printf "Power save: %s\\n" "$(cat "$est/$2")"\n'
                + 'elif [ "$3" = set ]; then\n'
                + '  echo off > "$est/$2"\n'
                + "fi\n",
            )
        if com_iwconfig:
            _stub(
                bin_ / "iwconfig",
                log
                + f'est="{self.estado}"\n'
                + 'if [ -z "$1" ]; then\n'
                + "  "
                + lista.replace("{ARGS}", 'printf "%s  IEEE 802.11\\n" "$i"')
                + '  printf "lo        no wireless extensions.\\n"\n'
                + 'elif [ "$2" = power ]; then\n'
                + '  echo off > "$est/$1"\n'
                + "else\n"
                + '  printf "%s  IEEE 802.11\\n" "$1"\n'
                + '  printf "          Power Management:%s\\n" "$(cat "$est/$1")"\n'
                + "fi\n",
            )

    def interface(self, nome: str, economia: str) -> None:
        with self.ifaces.open("a", encoding="utf-8") as f:
            f.write(nome + "\n")
        (self.estado / nome).write_text(economia + "\n", encoding="utf-8")

    def roda(self, *, dry_run: int = 0, skip_udev: int = 0) -> subprocess.CompletedProcess[str]:
        funcoes = "\n".join(_extrai_funcao(n) for n in FUNCOES)
        # O `/etc` do passo aponta para o de mentira; o resto do texto é o do install.
        funcoes = funcoes.replace("/etc/NetworkManager", str(self.nm))
        # O `/usr/sbin /sbin` do passo aponta para o de mentira: o real não vaza.
        assert "for dir in /usr/sbin /sbin; do" in funcoes
        funcoes = funcoes.replace("for dir in /usr/sbin /sbin; do", f"for dir in {self.sbin}; do")
        cena = (
            "set -euo pipefail\n"
            'warn() { printf "AVISO: %s\\n" "$*"; }\n'
            '_faria_root() { printf "FARIA-ROOT: %s\\n" "$*"; }\n'
            '_nao_faria() { printf "NAO-FARIA: %s\\n" "$*"; }\n'
            f'ROOT_DIR="{REPO_ROOT}"\nDRY_RUN={dry_run}\nSKIP_UDEV={skip_udev}\n'
            f"{funcoes}\naplicar_wifi_powersave_off\nprintf 'RC=0\\n'\n"
        )
        script = self.base / "cena.sh"
        script.write_text(cena, encoding="utf-8")
        env = {"PATH": str(self.bin), "HOME": str(self.base), "LC_ALL": "C"}
        return subprocess.run(
            [BASH, str(script)], capture_output=True, text=True, check=False, env=env
        )

    def log(self) -> list[str]:
        return self.chamadas.read_text(encoding="utf-8").splitlines()

    def escritas(self) -> list[str]:
        """Chamadas que MUDAM algo: o sudo e o `set`/`power off` do rádio."""
        return [
            c for c in self.log()
            if c.endswith("/sudo") or "/sudo " in c or " set " in c or " power off" in c
        ]

    def proibidas(self) -> list[str]:
        return [c for c in self.log() if any(p in c for p in PROIBIDOS)]


@pytest.fixture
def cena(tmp_path: Path) -> Cena:
    return Cena(tmp_path)


class TestPrimeiraCorrida:
    def test_sem_opcao_grava_o_conf_e_desliga_so_a_interface_ligada(self, cena: Cena) -> None:
        cena.interface("wlan0", "on")
        cena.interface("wlan1", "off")
        r = cena.roda()
        assert "RC=0" in r.stdout, r.stderr
        assert cena.alvo.read_bytes() == ASSET.read_bytes(), "o conf do asset não foi gravado"
        log = cena.log()
        assert any(c.endswith("iw dev wlan0 set power_save off") for c in log), log
        assert not any("wlan1 set" in c for c in log), (
            "wlan1 já estava desligada: o passo não pode chamá-la"
        )
        assert (cena.estado / "wlan0").read_text(encoding="utf-8").strip() == "off"
        assert "desligada agora" in r.stdout

    def test_sem_o_iw_usa_o_iwconfig(self, tmp_path: Path) -> None:
        c = Cena(tmp_path, com_iw=False, com_iwconfig=True)
        c.interface("wlan0", "on")
        r = c.roda()
        assert "RC=0" in r.stdout, r.stderr
        assert any(x.endswith("iwconfig wlan0 power off") for x in c.log()), c.log()
        assert (c.estado / "wlan0").read_text(encoding="utf-8").strip() == "off"

    def test_conf_ausente_e_economia_ja_desligada_so_grava_o_conf(self, cena: Cena) -> None:
        cena.interface("wlan0", "off")
        r = cena.roda()
        assert "RC=0" in r.stdout, r.stderr
        assert cena.alvo.read_bytes() == ASSET.read_bytes()
        assert not any(" set " in c or " power off" in c for c in cena.log())

    def test_sem_wifi_nenhum_so_grava_o_conf(self, cena: Cena) -> None:
        r = cena.roda()
        assert "RC=0" in r.stdout, r.stderr
        assert cena.alvo.read_bytes() == ASSET.read_bytes()

    def test_sem_sudo_avisa_o_comando_e_nao_escreve(self, tmp_path: Path) -> None:
        c = Cena(tmp_path, com_sudo=False)
        c.interface("wlan0", "on")
        r = c.roda()
        assert "RC=0" in r.stdout, r.stderr
        assert not c.alvo.exists()
        assert f"sudo {c.bin}/iw dev wlan0 set power_save off" in r.stdout
        assert (c.estado / "wlan0").read_text(encoding="utf-8").strip() == "on"

    def test_sem_sudo_e_sem_o_iw_avisa_o_comando_do_iwconfig(self, tmp_path: Path) -> None:
        c = Cena(tmp_path, com_iw=False, com_iwconfig=True, com_sudo=False)
        c.interface("wlan0", "on")
        r = c.roda()
        assert "RC=0" in r.stdout, r.stderr
        assert f"sudo {c.bin}/iwconfig wlan0 power off" in r.stdout
        assert " iw " not in r.stdout

    def test_o_iw_fora_do_path_mora_no_sbin_e_e_achado(self, tmp_path: Path) -> None:
        """No Debian 12 o `/usr/sbin` não está no PATH de usuário comum."""
        c = Cena(tmp_path, iw_no_sbin=True)
        c.interface("wlan0", "on")
        r = c.roda()
        assert "RC=0" in r.stdout, r.stderr
        assert any(x.endswith(f"sudo {c.sbin}/iw dev wlan0 set power_save off") for x in c.log())
        assert (c.estado / "wlan0").read_text(encoding="utf-8").strip() == "off"

    def test_sem_iw_nem_iwconfig_nao_diz_que_esta_desligada(self, tmp_path: Path) -> None:
        """Não saber o estado da interface não é «nenhuma interface ligada»."""
        c = Cena(tmp_path, com_iw=False)
        assert "RC=0" in c.roda().stdout
        r = c.roda()
        assert "RC=0" in r.stdout, r.stderr
        assert "já desligada" not in r.stdout
        assert "sem iw nem iwconfig" in r.stdout
        r = c.roda(dry_run=1)
        assert "já está desligada" not in r.stdout
        assert "sem iw nem iwconfig" in r.stdout


class TestSegundaCorrida:
    def test_nao_grava_nem_chama_nada_e_diz_ja_desligada(self, cena: Cena) -> None:
        cena.interface("wlan0", "on")
        assert "RC=0" in cena.roda().stdout
        antes = cena.alvo.stat().st_mtime_ns
        cena.chamadas.write_text("", encoding="utf-8")
        r = cena.roda()
        assert "RC=0" in r.stdout, r.stderr
        assert "já desligada" in r.stdout
        assert cena.escritas() == [], cena.escritas()
        assert cena.alvo.stat().st_mtime_ns == antes, "o conf foi regravado sem mudança"

    def test_conf_igual_mas_interface_religada_so_desliga_a_interface(self, cena: Cena) -> None:
        cena.interface("wlan0", "on")
        assert "RC=0" in cena.roda().stdout
        (cena.estado / "wlan0").write_text("on\n", encoding="utf-8")  # o NM religou
        antes = cena.alvo.stat().st_mtime_ns
        cena.chamadas.write_text("", encoding="utf-8")
        assert "RC=0" in cena.roda().stdout
        assert any(c.endswith("iw dev wlan0 set power_save off") for c in cena.log())
        assert not any("install" in c for c in cena.log()), "o conf igual não se regrava"
        assert cena.alvo.stat().st_mtime_ns == antes


class TestNuncaDerrubaAConexao:
    def test_nenhuma_corrida_chama_nmcli_rfkill_nem_reload(self, tmp_path: Path) -> None:
        for i, (com_iw, ligada) in enumerate(((True, "on"), (False, "on"), (True, "off"))):
            base = tmp_path / f"c{i}"
            base.mkdir()
            c = Cena(base, com_iw=com_iw, com_iwconfig=not com_iw)
            c.interface("wlan0", ligada)
            for _ in range(2):
                assert "RC=0" in c.roda().stdout
            assert c.proibidas() == [], c.proibidas()

    def test_o_codigo_do_passo_nao_tem_o_que_reconecta(self) -> None:
        codigo = _sem_comentarios("\n".join(_extrai_funcao(n) for n in FUNCOES))
        for proibido in PROIBIDOS:
            assert proibido not in codigo, f"o passo chama `{proibido}`"
        assert not re.search(r"\bsystemctl\b", codigo)

    def test_o_install_inteiro_continua_sem_nmcli_nem_rfkill(self) -> None:
        codigo = _sem_comentarios(INSTALL)
        assert not re.search(r"\bnmcli\b", codigo)
        assert not re.search(r"\brfkill\b", codigo)


class TestDryRun:
    def test_diz_o_que_faria_e_nao_chama_nada_que_mude(self, cena: Cena) -> None:
        cena.interface("wlan0", "on")
        r = cena.roda(dry_run=1)
        assert "RC=0" in r.stdout, r.stderr
        assert "FARIA-ROOT:" in r.stdout and "wlan0" in r.stdout
        assert cena.escritas() == [], cena.escritas()
        assert not cena.alvo.exists()

    def test_com_tudo_em_dia_diz_que_nao_faria(self, cena: Cena) -> None:
        cena.interface("wlan0", "on")
        assert "RC=0" in cena.roda().stdout
        r = cena.roda(dry_run=1)
        assert "NAO-FARIA:" in r.stdout and "FARIA-ROOT" not in r.stdout

    def test_no_udev_pula_o_passo(self, cena: Cena) -> None:
        cena.interface("wlan0", "on")
        r = cena.roda(skip_udev=1)
        assert "RC=0" in r.stdout, r.stderr
        assert cena.escritas() == []
        assert not cena.alvo.exists()


class TestOPassoEPadrao:
    def test_a_chamada_esta_na_coluna_zero_e_sem_portao_de_opcao(self) -> None:
        assert re.search(r"^aplicar_wifi_powersave_off$", INSTALL, re.MULTILINE), (
            "o passo 3d-bis tem de ser chamado na coluna 0: indentado, é opt-in de novo"
        )
        assert re.search(
            r'^step "3d-bis"[^\n]*\naplicar_wifi_powersave_off$', INSTALL, re.MULTILINE
        ), "a chamada vem logo depois do `step` do 3d-bis, fora de qualquer bloco"
        assert "WIFI_POWERSAVE_OFF" not in INSTALL, (
            "não existe mais portão de opção: o padrão é desligar a economia"
        )

    def test_a_secao_do_passo_nao_tem_bloco_na_coluna_zero(self) -> None:
        """Na seção do 3d-bis, só as funções, o `step` e a chamada vivem na coluna 0."""
        ini = INSTALL.index("\n# 3d-bis.")
        fim = INSTALL.index("\n# 3e.", ini)
        soltas = [
            linha
            for linha in INSTALL[ini:fim].splitlines()
            if linha
            and not linha[0].isspace()
            and not linha.startswith("#")
            and linha != "}"
            and not re.match(r"^\w+\(\) \{$", linha)
        ]
        assert len(soltas) == 2, soltas
        assert soltas[0].startswith('step "3d-bis" ')
        assert soltas[1] == "aplicar_wifi_powersave_off"

    def test_a_opcao_velha_continua_aceita_sem_aviso(self) -> None:
        r = subprocess.run(
            [BASH, str(REPO_ROOT / "install.sh"), "--wifi-powersave-off", "--help"],
            capture_output=True, text=True, check=False, env=dict(os.environ),
        )
        assert r.returncode == 0, r.stderr
        assert "argumento desconhecido" not in r.stdout + r.stderr
        assert "--wifi-powersave-off" in r.stdout

    def test_o_asset_ainda_e_so_a_cura(self) -> None:
        efetivas = [
            linha.strip()
            for linha in ASSET.read_text(encoding="utf-8").splitlines()
            if linha.strip() and not linha.strip().startswith("#")
        ]
        assert efetivas == [
            "[connection.hefesto-wifi-powersave]",
            "match-device=type:wifi",
            "wifi.powersave=2",
        ]
