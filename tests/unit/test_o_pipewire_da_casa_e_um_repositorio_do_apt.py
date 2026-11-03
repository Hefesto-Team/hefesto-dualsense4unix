"""O PipeWire da casa é uma fonte do apt: o pacote irmão pedido depois sai na mesma versão.

O-PIPEWIRE-DA-CASA-E-UM-REPOSITORIO-DO-APT-01 (02/11/2026). Com a 1.6.9 só no
``dpkg/status``, o ``gstreamer1.0-pipewire`` e o ``pipewire-jack`` do Pop exigem a
1.6.8 exata e o apt acusa pacotes quebrados. O passo 3f-bis publica a entrega
conferida como fonte local do apt, no caminho que instala e no «curado».

O apt é o de verdade: os pacotes são ``.deb`` construídos pelo ``dpkg-deb``, o Pop é
uma fonte local com a origem ``pop-os-release`` e o pino 1001 dele, e o ``dpkg/status``
é próprio (``DPKG_ADMINDIR`` e ``APT_CONFIG``). Só o ``sudo`` (roda sem subir), o
construtor, o ``pgrep``, o ``systemctl`` e o ``apt-get install`` que instalaria são de
mentira.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.unit.test_o_pipewire_entra_no_install import FUNCOES_EXTRAIDAS, OS_RELEASE, _funcao

BASH = shutil.which("bash") or "/bin/bash"
FERRAMENTAS = ("apt-get", "apt-cache", "apt-ftparchive", "dpkg-deb", "dpkg-query", "dpkg")
FALTAM = [f for f in FERRAMENTAS if shutil.which(f) is None]
pytestmark = pytest.mark.skipif(bool(FALTAM), reason=f"sem {FALTAM} para o apt de verdade")

RAIZ = Path(__file__).resolve().parents[2]
INSTALL = (RAIZ / "install.sh").read_text(encoding="utf-8")
UNINSTALL = (RAIZ / "uninstall.sh").read_text(encoding="utf-8")
RECEITA = (RAIZ / "docs" / "usage" / "receita-backport-pipewire.md").read_text(encoding="utf-8")
BASELINE = (RAIZ / "assets" / "pipewire-backport" / "BASELINE").read_text(encoding="utf-8")


def _revisao(chave: str) -> str:
    m = re.search(rf"^{chave}=(.+)$", BASELINE, re.MULTILINE)
    assert m is not None, chave
    return m.group(1)


PW = _revisao("PW_REVISAO")
WP = _revisao("WP_REVISAO")
PW_POP = "1.6.8-1pop1~1787688714~24.04~fdff050"
WP_POP = "0.5.12-2pop1~1766191027~24.04~d4bf441"
PW_POP_NOVO = "1.6.10-1pop1~1799999999~24.04~0000000"

REPO = "/var/lib/hefesto-pipewire"
FONTE = "/etc/apt/sources.list.d/hefesto-pipewire.sources"


def _pacotes(pw: str, wp: str) -> dict[str, tuple[str, str, str]]:
    """nome -> (versão, fonte, Depends)."""
    return {
        "libpipewire-0.3-0t64": (pw, "pipewire", ""),
        "libpipewire-0.3-modules": (pw, "pipewire", f"libpipewire-0.3-0t64 (= {pw})"),
        "pipewire": (pw, "pipewire", f"libpipewire-0.3-modules (= {pw})"),
        "gstreamer1.0-pipewire": (
            pw,
            "pipewire",
            f"pipewire (= {pw}), libpipewire-0.3-0t64 (= {pw})",
        ),
        "pipewire-jack": (pw, "pipewire", f"pipewire (= {pw})"),
        "wireplumber": (wp, "wireplumber", "libpipewire-0.3-0t64 (>= 1.0)"),
    }


INSTALADOS = ("libpipewire-0.3-0t64", "libpipewire-0.3-modules", "pipewire", "wireplumber")


def _exe(pasta: Path, nome: str, corpo: str) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / nome
    alvo.write_text("#!/bin/bash\n" + corpo, encoding="utf-8")
    alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC)


def _deb(pasta: Path, nome: str, ver: str, fonte: str, dep: str) -> Path:
    obra = pasta / f".obra-{nome}"
    (obra / "DEBIAN").mkdir(parents=True)
    campos = [
        f"Package: {nome}",
        f"Version: {ver}",
        "Architecture: amd64",
        "Maintainer: Ninguém <ninguem@example.invalid>",
        f"Description: {nome} de mentira",
    ]
    if fonte != nome:
        campos.insert(1, f"Source: {fonte}")
    if dep:
        campos.append(f"Depends: {dep}")
    (obra / "DEBIAN" / "control").write_text("\n".join(campos) + "\n", encoding="utf-8")
    deb = pasta / f"{nome}_{ver}_amd64.deb"
    subprocess.run(
        ["dpkg-deb", "--root-owner-group", "--build", str(obra), str(deb)],
        check=True,
        capture_output=True,
    )
    shutil.rmtree(obra)
    return deb


def _fonte_plana(pasta: Path, origem: str) -> None:
    pacotes = subprocess.run(
        ["apt-ftparchive", "packages", "."], cwd=pasta, check=True, capture_output=True, text=True
    ).stdout
    (pasta / "Packages").write_text(pacotes, encoding="utf-8")
    release = subprocess.run(
        ["apt-ftparchive", "-o", f"APT::FTPArchive::Release::Origin={origem}", "release", "."],
        cwd=pasta,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    (pasta / "Release").write_text(release, encoding="utf-8")


@dataclass
class Cenario:
    raiz: Path
    env: dict[str, str]
    diario: Path
    entrega: Path
    repo: Path
    fonte: Path

    def apt(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["apt-get", *args], env=self.env, capture_output=True, text=True, check=False
        )

    def candidato(self, pacote: str) -> str:
        r = subprocess.run(
            ["apt-cache", "policy", pacote], env=self.env, capture_output=True, text=True
        )
        m = re.search(r"Candidate: (\S+)", r.stdout)
        return m.group(1) if m else r.stdout + r.stderr

    def passo(self, *, dry_run: bool = False, steam_aberta: bool = False) -> str:
        env = dict(self.env, DRY_RUN="1" if dry_run else "0")
        _exe(
            self.raiz / "fakes",
            "pgrep",
            f'printf "pgrep %s\\n" "$*" >> "{self.diario}"\nexit {0 if steam_aberta else 1}\n',
        )
        funcoes = "".join(_funcao(n) for n in FUNCOES_EXTRAIDAS)
        script = (
            "set -euo pipefail\n"
            'step() { printf \'\\n[%s] %s\\n\' "$1" "$2"; }\n'
            "warn() { printf '      aviso: %s\\n' \"$*\"; }\n"
            "_faria() { printf '      FARIA        %s\\n' \"$*\"; }\n"
            "_faria_root() { printf '      FARIA (root) %s\\n' \"$*\"; }\n"
            f'source "{RAIZ}/scripts/lib/som_da_sessao.sh"\n'
            + funcoes
            + "install_pipewire_da_casa\n"
        )
        r = subprocess.run(
            [BASH, "-c", script], env=env, capture_output=True, text=True, timeout=120, check=False
        )
        assert r.returncode == 0, r.stdout + r.stderr
        return r.stdout + r.stderr

    def chamadas(self) -> list[str]:
        return self.diario.read_text(encoding="utf-8").splitlines() if self.diario.exists() else []


def _cenario(
    tmp_path: Path,
    *,
    instalada: str = PW,
    pop: str = PW_POP,
    estragar: str = "",
) -> Cenario:
    t = tmp_path
    raiz = t / "raiz"
    (raiz / "assets" / "pipewire-backport" / "apt").mkdir(parents=True)
    for rel in (
        "assets/pipewire-backport/BASELINE",
        "assets/pipewire-backport/apt/hefesto-pipewire.pref",
    ):
        shutil.copy(RAIZ / rel, raiz / rel)
    diario = t / "chamadas.log"
    _exe(
        raiz / "scripts",
        "construir_pipewire_backport.sh",
        f'printf "construtor %s\\n" "$HEFESTO_PIPEWIRE_CACHE" >> "{diario}"\nexit 0\n',
    )
    fakes = raiz / "fakes"
    _exe(
        fakes,
        "sudo",
        f'printf "sudo %s\\n" "$*" >> "{diario}"\n'
        'if [[ "$1" == "-n" ]]; then shift; [[ "$1" == "true" ]] && exit 0; fi\n'
        'for a in "$@"; do case "$a" in /etc/*|/var/*|/usr/*) exit 0 ;; esac; done\n'
        'exec "$@"\n',
    )
    _exe(
        fakes,
        "apt-get",
        f'printf "apt-get %s\\n" "$*" >> "{diario}"\n'
        "simula=0; instala=0\n"
        'for a in "$@"; do case "$a" in -s) simula=1 ;; install) instala=1 ;; esac; done\n'
        '[[ "$instala" -eq 1 && "$simula" -eq 0 ]] && exit 0\n'
        'exec /usr/bin/apt-get "$@"\n',
    )
    _exe(fakes, "systemctl", f'printf "systemctl %s\\n" "$*" >> "{diario}"\nexit 0\n')

    lar = t / "lar"
    entrega = lar / ".cache" / "hefesto-dualsense4unix" / "pipewire-backport"
    entrega.mkdir(parents=True)
    linhas = []
    for nome, (ver, fonte, dep) in _pacotes(PW, WP).items():
        deb = _deb(entrega, nome, ver, fonte, dep)
        linhas.append(f"{hashlib.sha256(deb.read_bytes()).hexdigest()}  {deb.name}")
    (entrega / "SHA256SUMS").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    if estragar:
        alvo = next(entrega.glob(f"{estragar}_*.deb"))
        alvo.write_bytes(alvo.read_bytes() + b"\0")

    pop_dir = t / "pop"
    pop_dir.mkdir()
    for nome, (ver, fonte, dep) in _pacotes(pop, WP_POP).items():
        _deb(pop_dir, nome, ver, fonte, dep)
    _fonte_plana(pop_dir, "pop-os-release")

    etc = t / "etc"
    (etc / "sources.list.d").mkdir(parents=True)
    (etc / "preferences.d").mkdir()
    (etc / "apt.conf.d").mkdir()
    (etc / "sources.list").write_text(f"deb [trusted=yes] file:{pop_dir} ./\n", encoding="utf-8")
    (etc / "preferences.d" / "pop-default-settings").write_text(
        "Package: *\nPin: release o=pop-os-release\nPin-Priority: 1001\n", encoding="utf-8"
    )
    shutil.copy(
        RAIZ / "assets/pipewire-backport/apt/hefesto-pipewire.pref",
        etc / "preferences.d" / "hefesto-pipewire",
    )
    dpkg = t / "dpkg"
    for sub in ("info", "updates"):
        (dpkg / sub).mkdir(parents=True)
    instalados = _pacotes(instalada, WP)
    blocos = []
    for nome in INSTALADOS:
        ver, fonte, dep = instalados[nome]
        bloco = [
            f"Package: {nome}",
            "Status: install ok installed",
            "Maintainer: Ninguém <ninguem@example.invalid>",
            "Architecture: amd64",
            f"Version: {ver}",
            f"Description: {nome} de mentira",
        ]
        if fonte != nome:
            bloco.insert(2, f"Source: {fonte}")
        if dep:
            bloco.append(f"Depends: {dep}")
        blocos.append("\n".join(bloco))
    (dpkg / "status").write_text("\n\n".join(blocos) + "\n", encoding="utf-8")
    for sub in ("lists/partial", "cache/archives/partial", "estado", "log"):
        (t / sub).mkdir(parents=True)
    conf = t / "apt.conf"
    conf.write_text(
        f'Dir::State "{t}/estado";\n'
        f'Dir::State::Lists "{t}/lists";\n'
        f'Dir::State::status "{dpkg}/status";\n'
        f'Dir::Cache "{t}/cache";\n'
        f'Dir::Log "{t}/log";\n'
        f'Dir::Etc "{etc}";\n'
        f'Dir::Etc::SourceList "{etc}/sources.list";\n'
        f'Dir::Etc::SourceParts "{etc}/sources.list.d";\n'
        f'Dir::Etc::Preferences "{etc}/preferences";\n'
        f'Dir::Etc::PreferencesParts "{etc}/preferences.d";\n'
        f'Dir::Etc::Parts "{etc}/apt.conf.d";\n'
        'APT::Architecture "amd64";\n'
        'APT::Architectures { "amd64"; };\n'
        'APT::Sandbox::User "root";\n'
        'Debug::NoLocking "1";\n',
        encoding="utf-8",
    )
    os_release = t / "os-release"
    os_release.write_text(OS_RELEASE["pop-24.04"], encoding="utf-8")
    repo = t / "var" / "apt-pipewire"
    fonte_da_casa = etc / "sources.list.d" / "hefesto-pipewire.sources"
    env = {
        "PATH": f"{fakes}:/usr/bin:/bin",
        "HOME": str(lar),
        "ROOT_DIR": str(raiz),
        "AUTO_YES": "1",
        "DRY_RUN": "0",
        "LC_ALL": "C",
        "TMPDIR": str(t),
        "APT_CONFIG": str(conf),
        "DPKG_ADMINDIR": str(dpkg),
        "_OS_RELEASE": str(os_release),
        "_PW_REPO": str(repo),
        "_PW_FONTE": str(fonte_da_casa),
    }
    b = Cenario(raiz, env, diario, entrega, repo, fonte_da_casa)
    r = b.apt("update")
    assert r.returncode == 0, r.stdout + r.stderr
    return b


def test_no_curado_a_fonte_entra_e_os_irmaos_saem_na_versao_da_casa(tmp_path: Path) -> None:
    """MORDIDA: sem a chamada da fonte no caminho «curado», o apt segue quebrado."""
    b = _cenario(tmp_path)
    antes = b.apt("-s", "install", "gstreamer1.0-pipewire", "pipewire-jack")
    assert antes.returncode == 100, antes.stdout + antes.stderr
    assert f"pipewire (= {PW_POP})" in antes.stdout, antes.stdout

    saida = b.passo()
    assert "nada a trocar" in saida, saida
    assert b.fonte.is_file(), saida
    assert f"URIs: file:{b.repo}" in b.fonte.read_text(encoding="utf-8")
    assert (b.repo / "Packages").is_file() and (b.repo / "Release").is_file()
    assert not any("apt-get install -y" in c for c in b.chamadas()), b.chamadas()
    assert any("Dir::Etc::SourceParts=-" in c for c in b.chamadas()), b.chamadas()

    depois = b.apt("-s", "install", "gstreamer1.0-pipewire", "pipewire-jack")
    assert depois.returncode == 0, depois.stdout + depois.stderr
    assert f"Inst gstreamer1.0-pipewire ({PW} " in depois.stdout, depois.stdout
    assert f"Inst pipewire-jack ({PW} " in depois.stdout, depois.stdout
    assert "Remv" not in depois.stdout, depois.stdout


def test_o_install_de_novo_publica_de_novo_sem_sobra(tmp_path: Path) -> None:
    b = _cenario(tmp_path)
    b.passo()
    b.passo()
    assert not Path(f"{b.repo}.novo").exists()
    assert b.apt("-s", "install", "gstreamer1.0-pipewire").returncode == 0


def test_quando_o_pop_passa_da_casa_o_apt_fica_com_o_do_pop(tmp_path: Path) -> None:
    b = _cenario(tmp_path, pop=PW_POP_NOVO)
    b.passo()
    assert b.fonte.is_file()
    assert b.candidato("gstreamer1.0-pipewire") == PW_POP_NOVO
    assert b.candidato("pipewire") == PW_POP_NOVO


def test_a_entrega_que_nao_confere_nao_vira_fonte(tmp_path: Path) -> None:
    b = _cenario(tmp_path, estragar="pipewire-jack")
    saida = b.passo()
    assert "não confere pelo SHA256SUMS" in saida, saida
    assert not b.fonte.exists() and not b.repo.exists()


def test_a_entrega_com_versao_alheia_nao_vira_fonte(tmp_path: Path) -> None:
    """MORDIDA: sem a conferência da versão, um .deb de outra revisão entraria na fonte."""
    b = _cenario(tmp_path)
    alheio = _deb(b.entrega, "pipewire-v4l2", PW_POP, "pipewire", f"pipewire (= {PW_POP})")
    with (b.entrega / "SHA256SUMS").open("a", encoding="utf-8") as somas:
        somas.write(f"{hashlib.sha256(alheio.read_bytes()).hexdigest()}  {alheio.name}\n")
    saida = b.passo()
    assert "não confere pelo SHA256SUMS" in saida, saida
    assert not b.fonte.exists() and not b.repo.exists()


@pytest.mark.parametrize("pronta", [True, False])
def test_no_curado_a_construcao_so_se_anuncia_sem_a_entrega(tmp_path: Path, pronta: bool) -> None:
    b = _cenario(tmp_path)
    if not pronta:
        (b.entrega / "SHA256SUMS").unlink()
    saida = b.passo()
    assert ("construindo pelo scripts/construir_pipewire_backport.sh" in saida) is not pronta, saida
    ensaio = b.passo(dry_run=True)
    assert ("FARIA        construir o PipeWire" in ensaio) is not pronta, ensaio


def test_com_a_cura_da_distro_nao_ha_fonte_nem_construcao(tmp_path: Path) -> None:
    b = _cenario(tmp_path, instalada="1.6.10-1")
    b.passo()
    assert not b.fonte.exists()
    assert not any(c.startswith("construtor") for c in b.chamadas()), b.chamadas()


def test_no_caminho_que_instala_a_fonte_entra_depois_do_apt_install(tmp_path: Path) -> None:
    """MORDIDA: publicar antes do install deixaria um `apt upgrade` trocar o PipeWire recusado.

    Prova da D-0211-O-PIPEWIRE-DA-CASA-E-FONTE-DO-APT.
    """
    b = _cenario(tmp_path, instalada=PW_POP)
    b.passo()
    chamadas = b.chamadas()
    instala = next(i for i, c in enumerate(chamadas) if c.startswith("apt-get install -y"))
    fonte = next(
        i
        for i, c in enumerate(chamadas)
        if f"install -m 0644 {b.raiz.parent}" in c and c.endswith(str(b.fonte))
    )
    assert instala < fonte, chamadas
    assert b.fonte.is_file()


def test_com_a_steam_aberta_o_pipewire_nao_troca_e_a_fonte_nao_entra(tmp_path: Path) -> None:
    b = _cenario(tmp_path, instalada=PW_POP)
    saida = b.passo(steam_aberta=True)
    assert "a Steam está aberta" in saida, saida
    assert not b.fonte.exists() and not b.repo.exists()


@pytest.mark.parametrize("instalada", [PW, PW_POP])
def test_o_ensaio_diz_a_fonte_e_nao_escreve(tmp_path: Path, instalada: str) -> None:
    b = _cenario(tmp_path, instalada=instalada)
    saida = b.passo(dry_run=True)
    assert f"FARIA (root) publicar o PipeWire da casa como fonte do apt ({REPO}" in saida, saida
    assert not b.fonte.exists() and not b.repo.exists()
    assert not any(c.startswith(("sudo", "construtor")) for c in b.chamadas()), b.chamadas()


def test_a_copia_se_confere_antes_de_a_fonte_ser_escrita() -> None:
    corpo = _funcao("_pw_publica_o_repositorio")
    copia = corpo.index('_pw_entrega_confere "${novo}"')
    assert copia < corpo.index("apt-ftparchive packages") < corpo.index('"${fonte}"')
    assert corpo.index('sudo mv "${novo}" "${repo}"') < corpo.index('"${obra}/fonte" "${fonte}"')


def test_os_caminhos_do_install_e_do_uninstall_sao_os_mesmos() -> None:
    assert f"_PW_REPO:-{REPO}" in INSTALL and f"_PW_FONTE:-{FONTE}" in INSTALL
    assert f"PIPEWIRE_REPO={REPO}\n" in UNINSTALL
    assert f"PIPEWIRE_FONTE={FONTE}\n" in UNINSTALL
    corpo = UNINSTALL[UNINSTALL.index("devolver_o_pipewire() {") :]
    corpo = corpo[: corpo.index("\n}\n")]
    assert 'sudo rm -f "${PIPEWIRE_FONTE}"' in corpo
    assert 'sudo rm -rf "${PIPEWIRE_REPO}"' in corpo
    lista = REPO.lstrip("/").replace("/", "_")
    assert f"-name '_{lista}_*' -delete" in corpo


def test_a_receita_publica_e_tira_a_fonte() -> None:
    assert f"URIs: file:{REPO}" in RECEITA
    volta = RECEITA[RECEITA.index("Para voltar:") :]
    assert FONTE in volta[:400] and REPO in volta[:400]


def test_o_curativo_do_pipewiresrc_saiu_e_a_tela_vem_depois_do_passo() -> None:
    assert "_tela_deb_da_casa" not in INSTALL and "_tela_pela_casa" not in INSTALL
    passo = INSTALL.index("    install_pipewire_da_casa\nfi\n")
    tela = INSTALL.index("if ! _tela_presente; then")
    assert passo < tela
    bloco = INSTALL[tela : INSTALL.index("\nfi\n", tela)]
    assert "run_pkg gst-pipewire" in bloco
