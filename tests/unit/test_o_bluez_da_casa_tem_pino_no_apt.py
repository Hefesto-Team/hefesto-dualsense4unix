"""O BlueZ da casa tem pino no apt: nenhuma origem troca a versão ~hefesto.

O-BLUEZ-DA-CASA-TEM-PINO-NO-APT-01 (07/11/2026). O apt é o de verdade, com três origens de
mentira (o ``pop-os-release`` a 1001, o archive e um PPA), cada uma com um ``bluez`` maior e outro
menor que o da casa, e um ``dpkg/status`` próprio onde só mora o da casa. O passo do install e o
do uninstall rodam extraídos, com ``sudo`` e ``dpkg-query`` de mentira.

AS MORDIDAS (feitas na sprint, com a cura devolvida): sem o arquivo, o candidato vira o do Pop (e o
do PPA sem o Pop); o pino que só nomeia o ``pop-os-release`` reprova o caso do PPA; o pino por
glob de versão (``*~hefesto*``) não pega a versão que só mora no ``dpkg/status`` e reprova os três;
o install sem a chamada no «curado» reprova o caso da máquina que já tem o backport; o uninstall
sem a função reprova o caso da remoção.
"""
from __future__ import annotations

import shutil
import stat
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PREF = RAIZ / "assets" / "bluez-backport" / "apt" / "hefesto-bluez.pref"
INSTALL = (RAIZ / "install.sh").read_text(encoding="utf-8")
UNINSTALL = (RAIZ / "uninstall.sh").read_text(encoding="utf-8")
BASH = shutil.which("bash") or "/bin/bash"
FALTAM = [f for f in ("apt-get", "apt-cache", "apt-ftparchive") if shutil.which(f) is None]

CASA = "5.87-0ubuntu0.1~hefesto24.04.5"
PACOTES = ("bluez", "libbluetooth3", "bluez-cups")
ORIGENS = {
    "pop": ("pop-os-release", ("5.99-1pop1", "5.72-1pop1")),
    "arquivo": ("Ubuntu", ("5.95-0ubuntu1", "5.72-0ubuntu5.8")),
    "ppa": ("LP-PPA-bluez", ("5.97-1ppa1", "5.80-1ppa1")),
}
POP_SO = "Package: src:bluez\nPin: release o=pop-os-release\nPin-Priority: -1\n"
GLOB = "Package: src:bluez\nPin: version *~hefesto*\nPin-Priority: 1002\n"


def _bloco(pacote: str, versao: str, *extra: str) -> str:
    linhas = [f"Package: {pacote}", *extra]
    if pacote != "bluez":
        linhas.append("Source: bluez")
    linhas += [f"Version: {versao}", "Architecture: amd64",
               "Maintainer: Ninguém <ninguem@example.invalid>", "Description: de mentira"]
    return "\n".join(linhas) + "\n\n"


def _apt(t: Path, origens: tuple[str, ...], pino: str | None) -> dict[str, str]:
    etc = t / "etc"
    for sub in ("preferences.d", "sources.list.d", "apt.conf.d"):
        (etc / sub).mkdir(parents=True, exist_ok=True)
    fontes = []
    for nome in origens:
        origem, versoes = ORIGENS[nome]
        pasta = t / nome
        pasta.mkdir(exist_ok=True)
        (pasta / "Packages").write_text("".join(
            _bloco(p, v, f"Filename: ./{p}_{v}_amd64.deb", "Size: 1")
            for v in versoes for p in PACOTES), encoding="utf-8")
        release = subprocess.run(
            ["apt-ftparchive", "-o", f"APT::FTPArchive::Release::Origin={origem}", "release", "."],
            cwd=pasta, check=True, capture_output=True, text=True).stdout
        (pasta / "Release").write_text(release, encoding="utf-8")
        fontes.append(f"deb [trusted=yes] file:{pasta} ./\n")
    (etc / "sources.list").write_text("".join(fontes), encoding="utf-8")
    (etc / "preferences.d" / "pop-default-settings").write_text(
        "Package: *\nPin: release o=pop-os-release\nPin-Priority: 1001\n", encoding="utf-8")
    if pino is not None:
        (etc / "preferences.d" / "hefesto-bluez").write_text(pino, encoding="utf-8")
    (t / "dpkg").mkdir(exist_ok=True)
    (t / "dpkg" / "status").write_text("".join(
        _bloco(p, CASA, "Status: install ok installed") for p in PACOTES), encoding="utf-8")
    for sub in ("lists/partial", "cache/archives/partial", "estado"):
        (t / sub).mkdir(parents=True, exist_ok=True)
    conf = t / "apt.conf"
    conf.write_text(
        f'Dir::State "{t}/estado";\nDir::State::Lists "{t}/lists";\n'
        f'Dir::State::status "{t}/dpkg/status";\nDir::Cache "{t}/cache";\n'
        f'Dir::Etc "{etc}";\nDir::Etc::SourceList "{etc}/sources.list";\n'
        f'Dir::Etc::SourceParts "{etc}/sources.list.d";\n'
        f'Dir::Etc::Preferences "{etc}/preferences";\n'
        f'Dir::Etc::PreferencesParts "{etc}/preferences.d";\n'
        f'Dir::Etc::Parts "{etc}/apt.conf.d";\n'
        'APT::Architecture "amd64";\nAPT::Architectures { "amd64"; };\n'
        'APT::Sandbox::User "root";\nDebug::NoLocking "1";\n', encoding="utf-8")
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "APT_CONFIG": str(conf), "TMPDIR": str(t)}
    feito = subprocess.run(["apt-get", "update"], env=env, capture_output=True, text=True)
    assert feito.returncode == 0, feito.stdout + feito.stderr
    candidatos = {}
    for pacote in PACOTES:
        saida = subprocess.run(["apt-cache", "policy", pacote], env=env, capture_output=True,
                               text=True, check=True).stdout
        candidatos[pacote] = next(linha.split(":", 1)[1].strip() for linha in saida.splitlines()
                                  if linha.strip().startswith("Candidate:"))
    simulado = subprocess.run(["apt-get", "-s", "full-upgrade"], env=env, capture_output=True,
                              text=True, check=True).stdout
    candidatos["full-upgrade"] = " ".join(
        linha.split()[1] for linha in simulado.splitlines() if linha.startswith("Inst "))
    return candidatos


CENARIOS = {
    "pop-arquivo-ppa": (("pop", "arquivo", "ppa"), "5.99-1pop1"),
    "arquivo-ppa": (("arquivo", "ppa"), "5.97-1ppa1"),
    "so-o-arquivo": (("arquivo",), "5.95-0ubuntu1"),
}


@pytest.mark.skipif(bool(FALTAM), reason=f"sem {FALTAM} para o apt de verdade")
@pytest.mark.parametrize("cenario", sorted(CENARIOS))
def test_o_candidato_e_o_da_casa_em_toda_origem(tmp_path: Path, cenario: str) -> None:
    """Prova da D-0711-O-BLUEZ-DA-CASA-VENCE-NO-APT: o candidato é o da casa."""
    origens, _de_fora = CENARIOS[cenario]
    candidatos = _apt(tmp_path, origens, PREF.read_text(encoding="utf-8"))
    assert all(candidatos[p] == CASA for p in PACOTES), candidatos
    assert not any(p in candidatos["full-upgrade"].split() for p in PACOTES), candidatos


@pytest.mark.skipif(bool(FALTAM), reason=f"sem {FALTAM} para o apt de verdade")
@pytest.mark.parametrize("cenario", sorted(CENARIOS))
def test_sem_o_pino_a_origem_de_fora_troca_o_da_casa(tmp_path: Path, cenario: str) -> None:
    origens, de_fora = CENARIOS[cenario]
    candidatos = _apt(tmp_path, origens, None)
    assert candidatos["bluez"] == de_fora, candidatos


@pytest.mark.skipif(bool(FALTAM), reason=f"sem {FALTAM} para o apt de verdade")
@pytest.mark.parametrize("errado", [POP_SO, GLOB], ids=["so-o-pop", "glob-de-versao"])
def test_o_pino_de_forma_errada_perde_o_ppa(tmp_path: Path, errado: str) -> None:
    candidatos = _apt(tmp_path, CENARIOS["arquivo-ppa"][0], errado)
    assert candidatos["bluez"] == "5.97-1ppa1", candidatos


def test_o_pino_vale_para_os_tres_pacotes_e_nao_nomeia_a_origem() -> None:
    texto = PREF.read_text(encoding="utf-8")
    assert "Package: src:bluez" in texto and "Pin: version /~hefesto/" in texto
    assert "release" not in texto and "Pin-Priority: 1002" in texto


def _funcao(fonte: str, nome: str) -> str:
    inicio = fonte.index(f"{nome}() {{\n")
    return fonte[inicio:fonte.index("\n}\n", inicio) + 3]


def _exe(pasta: Path, nome: str, corpo: str) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / nome
    alvo.write_text("#!/bin/bash\n" + corpo, encoding="utf-8")
    alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC)


def _passo(t: Path, *, versao: str, dry_run: bool, chamada: str = "_bz_pino",
           ja: bool = False) -> tuple[str, list[str], Path]:
    destino = t / "etc-apt" / "hefesto-bluez"
    destino.parent.mkdir(parents=True, exist_ok=True)
    if ja:
        shutil.copy(PREF, destino)
    diario = t / "diario"
    falsos = t / "falsos"
    _exe(falsos, "dpkg-query", f'printf "%s" "{versao}"\n')
    _exe(falsos, "sudo", f'printf "sudo %s\\n" "$*" >> "{diario}"\nexec "$@"\n')
    script = (
        "set -euo pipefail\n"
        "warn() { printf '      aviso: %s\\n' \"$*\"; }\n"
        "_faria_root() { printf '      FARIA (root) %s\\n' \"$*\"; }\n"
        + _funcao(INSTALL, "_bz_pino") + chamada + "\n")
    env = {"PATH": f"{falsos}:/usr/bin:/bin", "ROOT_DIR": str(RAIZ), "_BZ_PINO": str(destino),
           "DRY_RUN": "1" if dry_run else "0", "LC_ALL": "C"}
    feito = subprocess.run([BASH, "-c", script], env=env, capture_output=True, text=True,
                           timeout=30)
    assert feito.returncode == 0, feito.stdout + feito.stderr
    chamadas = diario.read_text(encoding="utf-8").splitlines() if diario.exists() else []
    return feito.stdout, chamadas, destino


def test_o_install_grava_o_pino_quando_o_backport_esta_instalado(tmp_path: Path) -> None:
    saida, chamadas, destino = _passo(tmp_path, versao=CASA, dry_run=False)
    assert destino.read_bytes() == PREF.read_bytes()
    assert any(c.startswith("sudo install -m 0644") for c in chamadas)
    assert "pino do apt gravado" in saida


def test_o_install_nao_grava_o_pino_sem_o_backport(tmp_path: Path) -> None:
    saida, chamadas, destino = _passo(tmp_path, versao="5.72-0ubuntu5.8", dry_run=False)
    assert not destino.exists() and not chamadas and not saida


def test_o_ensaio_do_install_lista_o_pino(tmp_path: Path) -> None:
    saida, chamadas, destino = _passo(tmp_path, versao=CASA, dry_run=True)
    assert "FARIA (root) fixar o BlueZ da casa no apt" in saida
    assert not destino.exists() and not chamadas
    saida, _c, _d = _passo(tmp_path / "antes", versao="5.72-0ubuntu5.8", dry_run=True,
                           chamada="_bz_pino vai-instalar")
    assert "FARIA (root) fixar o BlueZ da casa no apt" in saida


def test_o_pino_igual_nao_se_regrava(tmp_path: Path) -> None:
    saida, chamadas, _d = _passo(tmp_path, versao=CASA, dry_run=False, ja=True)
    assert not chamadas and "pino do apt:" in saida


def test_o_passo_3f_chama_o_pino_no_curado_e_depois_de_instalar() -> None:
    passo = INSTALL[INSTALL.index('step "3f"'):INSTALL.index("_pw_versao_ii() {")]
    curado = passo[passo.index("        curado)"):passo.index("        sem-binario)")]
    assert "_bz_pino\n" in curado
    assert "_bz_pino vai-instalar" in passo
    depois = passo[passo.index("backport %s aplicado"):]
    assert "_bz_pino\n" in depois[:200]


def _uninstall(t: Path, *, dry_run: bool) -> tuple[str, Path]:
    destino = t / "etc-apt" / "hefesto-bluez"
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(PREF, destino)
    sudo = ('sudo() { case "$*" in "-n true") return 0 ;; esac; '
            'printf "FARIA: (root) %s\\n" "$*"; }\n' if dry_run
            else 'sudo() { [[ "$1" == "-n" ]] && return 0; "$@"; }\n')
    linha = next(x for x in UNINSTALL.splitlines() if x.startswith("BLUEZ_PREF="))
    script = ("set -euo pipefail\nlog() { printf '[uninstall] %s\\n' \"$*\"; }\n" + sudo
              + linha + "\n" + _funcao(UNINSTALL, "tirar_o_pino_do_bluez")
              + "tirar_o_pino_do_bluez\n")
    feito = subprocess.run([BASH, "-c", script], capture_output=True, text=True, timeout=30,
                           env={"PATH": "/usr/bin:/bin", "_BZ_PINO": str(destino)})
    assert feito.returncode == 0, feito.stdout + feito.stderr
    return feito.stdout, destino


def test_o_uninstall_tira_o_pino_sempre(tmp_path: Path) -> None:
    saida, destino = _uninstall(tmp_path, dry_run=False)
    assert not destino.exists() and "removido o pino do apt do BlueZ" in saida
    assert "tirar_o_pino_do_bluez\n" in UNINSTALL.split("tirar_o_pino_do_bluez() {", 1)[1]


def test_o_ensaio_do_uninstall_lista_o_pino(tmp_path: Path) -> None:
    saida, destino = _uninstall(tmp_path, dry_run=True)
    assert destino.exists() and f"FARIA: (root) rm -f {destino}" in saida
