"""MIGRACAO-BLUEZ-DEPRECIADOS-01 nos dois instaladores.

A migração de 19/08/2026 tirou `hciconfig`, `hcitool` e `sdptool` de seis
scripts (`doctor.sh`, `bt_active_mode.sh`, `bt_nosniff_now.sh`,
`bt_health_watchdog.sh`, `storm_watch.sh`, `medir_w3_coex.sh`), e
`tests/unit/test_migracao_bluez_depreciados.py` é o portão daqueles seis. O
`install.sh` e o `uninstall.sh` NÃO estavam na lista — nem na da migração, nem
na do portão. Este arquivo fecha os dois lados que ficaram de fora:

* **o uninstall**: ele achava o adaptador só pelo `hciconfig`. Numa distro que
  moveu as depreciadas para `bluez-deprecated` — Fedora e Arch, que são
  EXATAMENTE o público da migração — `_hci` saía vazio e o bloco inteiro era
  pulado **em silêncio**, inclusive a reversão do Alias, que sai por D-Bus e não
  precisava do `hciconfig` para nada. O adaptador dela ficava chamado
  "Nintendo ..." para sempre depois de desinstalar o Hefesto.

* **o install**: o censo `_DEPS_DE_SISTEMA` pedia só o `bluetoothctl`, e desde a
  migração o produto também chama o `btmgmt`. A tabela de PACOTES não muda — os
  dois viajam juntos nas três famílias, medido em contêiner limpo em
  19/08/2026 (`bluez` no Debian e no Fedora, `bluez-utils` no Arch, que o
  install já instala junto). O que muda é a régua: ela agora pergunta pelas duas
  ferramentas que o produto usa, em vez de por uma só.

A bancada é a dos irmãos: fakes no PATH, nada do sistema real é tocado. O
`sandbox_sem_velhas` é a máquina que não tem as depreciadas — sem ele não há
como exercitar o cenário que recebia o silêncio.
"""
from __future__ import annotations

import contextlib
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
INSTALL = RAIZ / "install.sh"
UNINSTALL = RAIZ / "uninstall.sh"
BASH = shutil.which("bash") or "/bin/bash"

#: Depreciadas do BlueZ — as três que a upstream aposentou.
VELHAS = ("hciconfig", "hcitool", "sdptool")

#: Âncoras do bloco do uninstall que reverte a cura do Pro. O fim é a PRÓXIMA
#: seção (os snapshots de bond) e não um `fi` — a escada tem quatro `fi` pelo
#: caminho, e casar o primeiro recortaria o bloco pela metade em silêncio.
ANCORA_INICIO = "# BT-NINTENDO-ACTIVE-01: reverter a link policy"
ANCORA_FIM = "    if [[ -d /var/lib/hefesto-dualsense4unix/bt-bonds ]]; then"


# ---------------------------------------------------------------------------
# Bancada
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def sandbox_sem_velhas(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """PATH com tudo do sistema MENOS as três depreciadas.

    Links, não cópias: os binários de verdade (grep, sed, awk...) continuam
    rodando — o sandbox só apaga as três da vista.
    """
    alvo = tmp_path_factory.mktemp("bin-sem-velhas")
    for origem in ("/usr/bin", "/bin", "/usr/sbin", "/sbin"):
        d = Path(origem)
        if not d.is_dir():
            continue
        for entrada in d.iterdir():
            if entrada.name in VELHAS:
                continue
            destino = alvo / entrada.name
            if destino.exists() or destino.is_symlink():
                continue
            with contextlib.suppress(OSError):
                destino.symlink_to(entrada)
    for velha in VELHAS:
        assert shutil.which(velha, path=str(alvo)) is None, (
            f"o sandbox precisa NÃO ter {velha} — é o cenário sob teste"
        )
    return alvo


def _fake(dirbin: Path, nome: str, corpo: str) -> Path:
    dirbin.mkdir(parents=True, exist_ok=True)
    alvo = dirbin / nome
    alvo.write_text("#!/usr/bin/env bash\n" + corpo, encoding="utf-8")
    alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return alvo


def _bloco_do_uninstall() -> str:
    """Recorta o bloco REAL da reversão, do comentário até o `fi` que o fecha."""
    texto = UNINSTALL.read_text(encoding="utf-8")
    inicio = texto.find(ANCORA_INICIO)
    assert inicio != -1, (
        f"a âncora {ANCORA_INICIO!r} sumiu do uninstall.sh — reaponte este teste "
        "antes de confiar nele."
    )
    fim = texto.find(ANCORA_FIM, inicio)
    assert fim != -1, (
        f"a âncora de fim {ANCORA_FIM!r} sumiu do uninstall.sh — reaponte este "
        "teste antes de confiar nele."
    )
    bloco = texto[inicio:fim]
    assert "Adapter1 Alias" in bloco, (
        "o recorte não tem mais a reversão do Alias — pegou o pedaço errado:\n"
        + bloco
    )
    return bloco


def _roda_reversao(
    *dirs: Path,
    sysfs: Path,
    home: Path,
) -> subprocess.CompletedProcess[str]:
    """Roda o bloco de reversão do uninstall com o PATH e o sysfs dados."""
    script = (
        "set -uo pipefail\n"
        'log() { printf "[uninstall] %s\\n" "$*"; }\n'
        f"{_bloco_do_uninstall()}\n"
    )
    return subprocess.run(
        [BASH, "-c", script],
        env={
            "PATH": ":".join(str(d) for d in dirs),
            "HOME": str(home),
            "HEFESTO_SYSFS_BLUETOOTH": str(sysfs),
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


@pytest.fixture
def bancada(tmp_path: Path) -> tuple[Path, Path, Path]:
    """`(fakes, sysfs_vazio, home)` — o cenário da distro sem as depreciadas.

    O sysfs nasce VAZIO de propósito: é o degrau que a máquina de quem roda a
    suíte tem e o contêiner do CI não, e deixá-lo real faria o primeiro degrau
    vencer sempre — os três de baixo, que são a migração, nunca seriam medidos.
    """
    fakes = tmp_path / "fakes"
    sysfs = tmp_path / "sysfs-vazio"
    sysfs.mkdir()
    home = tmp_path / "casa"
    home.mkdir()
    fakes.mkdir()
    # `sudo` que só ecoa o que teria rodado: o teste NUNCA escala privilégio.
    _fake(fakes, "sudo", 'printf "SUDO: %s\\n" "$*"\nexit 0\n')
    return fakes, sysfs, home


def _busctl_fake(dirbin: Path, *, alias: str) -> Path:
    """`busctl` de mentira: um adaptador hci0 com o Alias pedido."""
    return _fake(
        dirbin,
        "busctl",
        f"""
case "$1 $2" in
  "tree org.bluez") printf '/org/bluez/hci0\\n' ;;
  "get-property org.bluez") echo 's "{alias}"' ;;
  "set-property org.bluez") printf 'SET-ALIAS: %s\\n' "$*" ;;
esac
exit 0
""",
    )


# ---------------------------------------------------------------------------
# 1. O uninstall acha o adaptador SEM as depreciadas.
# ---------------------------------------------------------------------------
class TestOUninstallAchaOAdaptadorSemAsVelhas:
    def test_pelo_dbus_o_alias_nintendo_e_revertido(
        self, bancada: tuple[Path, Path, Path], sandbox_sem_velhas: Path
    ) -> None:
        """O caso da distro que não tem `hciconfig`: a metade que dá para
        desfazer TEM de ser desfeita."""
        fakes, sysfs, home = bancada
        _busctl_fake(fakes, alias="Nintendo meowsystem")

        r = _roda_reversao(fakes, sandbox_sem_velhas, sysfs=sysfs, home=home)

        # A escrita do Alias vai por `sudo busctl set-property`, então quem a
        # registra é o `sudo` de mentira.
        assert "SUDO: busctl set-property" in r.stdout, (
            "sem hciconfig o uninstall NÃO achou o adaptador e pulou o bloco em "
            "silêncio: o adaptador dela fica chamado 'Nintendo ...' para sempre "
            "depois de desinstalar o Hefesto.\n" + r.stdout + r.stderr
        )
        assert "nome do adaptador revertido para 'meowsystem'" in r.stdout

    def test_sem_hciconfig_ele_diz_que_a_link_policy_ficou(
        self, bancada: tuple[Path, Path, Path], sandbox_sem_velhas: Path
    ) -> None:
        """A link policy não tem sucessor vivo. Calar sobre isso seria mentir
        por omissão — a mesma regra dos contadores de erro do rádio."""
        fakes, sysfs, home = bancada
        _busctl_fake(fakes, alias="Nintendo meowsystem")

        r = _roda_reversao(fakes, sandbox_sem_velhas, sysfs=sysfs, home=home)

        assert "link policy de hci0 NÃO revertida" in r.stdout, (
            "o uninstall deixou o SNIFF do adaptador como a cura do Pro o pôs e "
            "não avisou.\n" + r.stdout
        )
        assert "bluez-deprecated" in r.stdout, "tem de dizer COMO recuperar"

    def test_pelo_btmgmt_quando_nem_o_busctl_existe(
        self, bancada: tuple[Path, Path, Path], sandbox_sem_velhas: Path
    ) -> None:
        """O terceiro degrau: a ferramenta que a upstream indica."""
        fakes, sysfs, home = bancada
        _fake(fakes, "btmgmt", 'printf "hci0:\\tPrimary controller\\n"\nexit 0\n')
        # Sem `busctl` no PATH — o sandbox tem o do sistema, então um `busctl`
        # de mentira que FALHA é o jeito de provar que o degrau seguinte assume.
        _fake(fakes, "busctl", "exit 1\n")

        r = _roda_reversao(fakes, sandbox_sem_velhas, sysfs=sysfs, home=home)

        assert "link policy de hci0 NÃO revertida" in r.stdout, (
            "o `btmgmt info` não foi consultado: o adaptador saiu vazio e o "
            "bloco inteiro foi pulado.\n" + r.stdout + r.stderr
        )

    def test_quem_ainda_tem_hciconfig_nao_perde_a_link_policy(
        self, bancada: tuple[Path, Path, Path]
    ) -> None:
        """Plano B preservado: migrar não pode TIRAR leitura de quem a tinha."""
        fakes, sysfs, home = bancada
        _busctl_fake(fakes, alias="Nintendo meowsystem")
        _fake(fakes, "hciconfig", 'printf "hci0:\\tType: Primary\\n"\nexit 0\n')

        r = _roda_reversao(fakes, "/usr/bin", "/bin", sysfs=sysfs, home=home)

        assert "SUDO: hciconfig hci0 lp rswitch,hold,sniff,park" in r.stdout, (
            "com o hciconfig na máquina a link policy TEM de voltar — a lista "
            "separada por vírgula, que é a que ele lê.\n" + r.stdout
        )
        assert "NÃO revertida" not in r.stdout

    def test_o_sysfs_e_o_primeiro_degrau(
        self, bancada: tuple[Path, Path, Path], sandbox_sem_velhas: Path
    ) -> None:
        """Kernel puro: sem pacote, sem privilégio, sem D-Bus de pé.

        E o filtro `^hci[0-9]+$` importa: em `/sys/class/bluetooth` as entradas
        de CONEXÃO nascem como `hci0:256`, e pegar uma delas montaria um caminho
        D-Bus que não existe.
        """
        fakes, sysfs, home = bancada
        (sysfs / "hci0:256").mkdir()
        (sysfs / "hci0").mkdir()
        _busctl_fake(fakes, alias="Nintendo meowsystem")

        r = _roda_reversao(fakes, sandbox_sem_velhas, sysfs=sysfs, home=home)

        assert "nome do adaptador revertido para 'meowsystem'" in r.stdout, r.stdout
        assert "hci0:256" not in r.stdout, (
            "o filtro deixou passar a entrada de CONEXÃO como se fosse adaptador"
        )

    def test_sem_adaptador_nenhum_o_bloco_cala_sem_morrer(
        self, bancada: tuple[Path, Path, Path], sandbox_sem_velhas: Path
    ) -> None:
        """Máquina sem rádio: nada a reverter, e o uninstall segue vivo."""
        fakes, sysfs, home = bancada
        _fake(fakes, "busctl", "exit 1\n")

        r = _roda_reversao(fakes, sandbox_sem_velhas, sysfs=sysfs, home=home)

        assert r.returncode == 0, f"o bloco morreu sem adaptador:\n{r.stderr}"
        assert "set-property" not in r.stdout
        assert "NÃO revertida" not in r.stdout


# ---------------------------------------------------------------------------
# 2. O censo do install pergunta pelas DUAS ferramentas que o produto usa.
# ---------------------------------------------------------------------------
def _linha_do_bluez() -> str:
    texto = INSTALL.read_text(encoding="utf-8")
    m = re.search(r"_DEPS_DE_SISTEMA=\((.*?)\n\)", texto, re.S)
    assert m is not None, "array _DEPS_DE_SISTEMA não encontrado em install.sh"
    linhas = [ln for ln in re.findall(r'"([^"]*\|[^"]*)"', m.group(1))
              if ln.startswith("bluez|")]
    assert len(linhas) == 1, f"esperava UMA linha `bluez|` no censo, achei {linhas}"
    return linhas[0]


class TestOCensoDoInstallConheceOBtmgmt:
    def test_a_regua_pede_bluetoothctl_e_btmgmt(self) -> None:
        """Os dois, porque o produto chama os dois.

        `bt_active_mode.sh`, `doctor.sh` e agora o `uninstall.sh` usam `btmgmt`;
        o pareamento e o diagnóstico usam `bluetoothctl`. Pedir só um deixava a
        régua cega para metade do que ela promete conferir.
        """
        _, _, checagem, _ = _linha_do_bluez().split("|")
        pedidos = checagem.removeprefix("cmd:").split(",")
        assert "bluetoothctl" in pedidos and "btmgmt" in pedidos, (
            f"o censo pede {pedidos} — o produto chama bluetoothctl E btmgmt"
        )

    def test_a_tabela_de_pacotes_nao_muda_e_o_arch_leva_o_bluez_utils(self) -> None:
        """MEDIDO em contêiner limpo em 19/08/2026, família por família:

            debian:12   dpkg -S /usr/bin/btmgmt                    -> bluez
            fedora:40   dnf repoquery --whatprovides .../btmgmt    -> bluez
            archlinux   pacman -F usr/bin/btmgmt                   -> bluez-utils

        No Arch a dupla mora em `bluez-utils`, e por isso a linha `bluez)` do
        `_pkg_nome` instala os DOIS nomes. Tirar o `bluez-utils` de lá deixaria
        o Arch sem `bluetoothctl` e sem `btmgmt` com o portão dizendo OK.
        """
        texto = INSTALL.read_text(encoding="utf-8")
        m = re.search(r"\n        bluez\)\n(.*?);;\n", texto, re.S)
        assert m is not None, "a linha `bluez)` sumiu de _pkg_nome"
        corpo = m.group(1)
        assert re.search(r'_apt="bluez"', corpo), corpo
        assert re.search(r'_dnf="bluez"', corpo), corpo
        assert re.search(r'_pacman="bluez bluez-utils"', corpo), (
            "no Arch o `bluetoothctl`/`btmgmt` vem do `bluez-utils`, não do "
            f"`bluez`:\n{corpo}"
        )

    def test_a_regua_reprova_quando_o_btmgmt_falta(
        self, tmp_path: Path, sandbox_sem_velhas: Path
    ) -> None:
        """A régua REAL do install.sh, rodada contra um PATH sem `btmgmt`.

        É o teste que separa "a linha do censo mudou" de "a checagem morde": a
        função `_dep_presente` é recortada do arquivo e executada.
        """
        texto = INSTALL.read_text(encoding="utf-8")
        m = re.search(r"^_dep_presente\(\) \{\n", texto, re.M)
        assert m is not None, "_dep_presente() não encontrada em install.sh"
        fim = re.search(r"^\}\n", texto[m.end():], re.M)
        assert fim is not None
        fn = texto[m.start() : m.end() + fim.end()]

        _, _, checagem, _ = _linha_do_bluez().split("|")

        so_bluetoothctl = tmp_path / "so-bluetoothctl"
        _fake(so_bluetoothctl, "bluetoothctl", "exit 0\n")
        _fake(so_bluetoothctl, "command", "exit 0\n")  # nunca usado: `command` é builtin

        def roda(path: str) -> int:
            return subprocess.run(
                [BASH, "-c", f'set -uo pipefail\nVENV_DIR=/nao-existe\n{fn}\n'
                             f'_dep_presente "{checagem}"'],
                env={"PATH": path},
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            ).returncode

        assert roda(str(so_bluetoothctl)) != 0, (
            "com `bluetoothctl` presente e `btmgmt` AUSENTE a régua aprovou — é "
            "exatamente o buraco que a migração abriu."
        )
        _fake(so_bluetoothctl, "btmgmt", "exit 0\n")
        assert roda(str(so_bluetoothctl)) == 0, (
            "com as duas ferramentas presentes a régua tem de aprovar"
        )
