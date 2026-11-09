"""O portal de captura do COSMIC da casa: o construtor, o passo 3f-ter do install e o doctor.

O-PORTAL-DE-CAPTURA-DO-COSMIC-NAO-CAI-NO-COMPARTILHAMENTO-01 (01/11/2026). Nada aqui
compila, instala ou reinicia: o dpkg-query, o apt-get, o sudo e o systemctl são de
mentira no PATH, e o HOME é um lar de mentira.
"""

from __future__ import annotations

import hashlib
import io
import shutil
import stat
import subprocess
import tarfile
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
DPKG = shutil.which("dpkg")
RAIZ = Path(__file__).resolve().parents[2]
ASSETS = RAIZ / "assets" / "portal-cosmic-backport"
INSTALL = (RAIZ / "install.sh").read_text(encoding="utf-8")
CONSTRUTOR = RAIZ / "scripts" / "construir_portal_cosmic_backport.sh"
DOCTOR = RAIZ / "scripts" / "doctor.sh"
RECEITA = RAIZ / "docs" / "usage" / "receita-backport-portal-cosmic.md"

pytestmark = pytest.mark.skipif(DPKG is None, reason="sem dpkg para comparar versões")


def _baseline() -> dict[str, str]:
    campos: dict[str, str] = {}
    for linha in (ASSETS / "BASELINE").read_text(encoding="utf-8").splitlines():
        chave, _, valor = linha.partition("=")
        campos[chave] = valor
    return campos


BASE = _baseline()
PACOTE = BASE["PORTAL_PACOTE"]
UNIDADE = BASE["PORTAL_UNIDADE"]
SUFIXO = BASE["SUFIXO"]
MARCA = next(v for k, v in BASE.items() if k.startswith("MARCA_"))
DE_CIMA = "1.11.0~1792525517~24.04~f448ddf"
DA_CASA = f"{DE_CIMA}{SUFIXO}"
PROXIMO_DO_POP = "1.11.0~1792600000~24.04~0a1b2c3"
COMMIT_DE_CIMA = "c0cff4db14c37ed954983158e4055aa94c7741d9"
FONTE_GIT = f"git+https://github.com/pop-os/cosmic-protocols?rev=c0cff4d#{COMMIT_DE_CIMA}"

DISPATCH_ANTES = """\
            ext_image_copy_capture_frame_v1::Event::PresentationTime {
                tv_sec_hi,
                tv_sec_lo,
                tv_nsec,
            } => {
                let secs = (u64::from(tv_sec_hi) << 32) + u64::from(tv_sec_lo);
                let duration = Duration::new(secs, tv_nsec);
                frame.lock().unwrap().present_time = Some(duration);
            }
            ext_image_copy_capture_frame_v1::Event::Ready => {
                let frame = frame.lock().unwrap().clone();
                app_data.ready(
                    conn,
                    qh,
                    &CaptureFrame {
                        frame: screencopy_frame.clone(),
                    },
                    frame,
                );
                screencopy_frame.destroy();
            }
            ext_image_copy_capture_frame_v1::Event::Failed { reason } => {
                app_data.failed(
                    conn,
                    qh,
                    &CaptureFrame {
                        frame: screencopy_frame.clone(),
                    },
                    reason,
                );
                screencopy_frame.destroy();
            }
            _ => unreachable!(),
        }
    }
}
"""

DISPATCH_DEPOIS = (
    DISPATCH_ANTES.replace(
        "                screencopy_frame.destroy();\n            }\n", "            }\n"
    )
    .replace(
        "                let frame = frame.lock().unwrap().clone();\n",
        "                let frame = frame.lock().unwrap().clone();\n"
        "                screencopy_frame.destroy();\n",
    )
    .replace(
        "Event::Failed { reason } => {\n",
        "Event::Failed { reason } => {\n                screencopy_frame.destroy();\n",
    )
)


def _exe(pasta: Path, nome: str, corpo: str) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / nome
    alvo.write_text("#!/bin/bash\n" + corpo, encoding="utf-8")
    alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC)


def _dpkg_query(fakes: Path, maquina: dict[str, tuple[str, str]]) -> None:
    casos = "\n".join(f'  {p}) st="{st}"; v="{v}" ;;' for p, (st, v) in maquina.items())
    lista = "".join(f"{st} {p}\\n" for p, (st, _v) in maquina.items())
    _exe(
        fakes,
        "dpkg-query",
        'fmt=""; pkg=""\n'
        'for a in "$@"; do case "$a" in -f=*) fmt="${a#-f=}" ;; -W) ;; *) pkg="$a" ;; esac; done\n'
        f'if [[ -z "$pkg" ]]; then printf "{lista}"; exit 0; fi\n'
        f'case "${{pkg%%:*}}" in\n{casos}\n'
        '  *) echo "dpkg-query: nenhum pacote casa com $pkg" >&2; exit 1 ;;\n'
        "esac\n"
        "out=\"${fmt//'${db:Status-Abbrev}'/$st}\"\n"
        "out=\"${out//'${binary:Package}'/$pkg}\"\n"
        "out=\"${out//'${Package}'/$pkg}\"\n"
        "out=\"${out//'${Version}'/$v}\"\n"
        'printf "%b" "$out"\n',
    )


def _rodar_construtor(
    *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [BASH, str(CONSTRUTOR), *args],
        env=env or {"PATH": "/usr/bin:/bin", "HOME": "/nao-existe"},
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_o_baseline_confere_com_o_patch_e_com_a_marca() -> None:
    patch = ASSETS / "patches" / BASE["PATCH"]
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == BASE["PATCH_SHA256"]
    assert MARCA.startswith(BASE["ARVORE_DO_PATCH"] + "/client-toolkit/")
    assert MARCA.endswith("src/screencopy/dispatch.rs")
    assert SUFIXO.startswith("+") and "~hefesto" in SUFIXO
    assert BASE["PROTOCOLOS_URL"] in FONTE_GIT


def test_o_pref_e_a_regra_do_pipewire_a_500_so_para_o_portal() -> None:
    linhas = (
        (ASSETS / "apt" / "hefesto-portal-cosmic.pref").read_text(encoding="utf-8").splitlines()
    )
    assert linhas == [
        f"Package: src:{PACOTE}",
        "Pin: release o=pop-os-release",
        "Pin-Priority: 500",
    ]


def test_a_versao_da_casa_fica_entre_a_do_pop_e_a_proxima_do_pop() -> None:
    """MORDIDA: com o sufixo «~hefesto1» sem o «+0», a da casa fica abaixo da do Pop."""
    assert DPKG is not None
    acima = subprocess.run([DPKG, "--compare-versions", DA_CASA, "gt", DE_CIMA], check=False)
    abaixo = subprocess.run(
        [DPKG, "--compare-versions", DA_CASA, "lt", PROXIMO_DO_POP], check=False
    )
    assert acima.returncode == 0 and abaixo.returncode == 0


def test_o_dispatch_de_cima_nao_tem_a_cura_e_o_do_pr_tem(tmp_path: Path) -> None:
    """MORDIDA: inverter a ordem que a régua exige faz o de cima passar por curado."""
    antes = tmp_path / "antes.rs"
    antes.write_text(DISPATCH_ANTES, encoding="utf-8")
    depois = tmp_path / "depois.rs"
    depois.write_text(DISPATCH_DEPOIS, encoding="utf-8")
    r_antes = _rodar_construtor("--conferir-dispatch", str(antes))
    r_depois = _rodar_construtor("--conferir-dispatch", str(depois))
    assert r_antes.returncode == 6, r_antes.stderr
    assert r_depois.returncode == 0, r_depois.stderr


def test_o_patch_do_pr_aplica_sem_fuzz_e_da_o_dispatch_curado(tmp_path: Path) -> None:
    arvore = tmp_path / "a" / "client-toolkit" / "src" / "screencopy"
    arvore.mkdir(parents=True)
    (arvore / "dispatch.rs").write_text("\n" * 140 + DISPATCH_ANTES, encoding="utf-8")
    patch = ASSETS / "patches" / BASE["PATCH"]
    r = subprocess.run(
        ["patch", "-d", str(tmp_path / "a"), "-p1", "-F0", "-N", "-s", "-i", str(patch)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert (arvore / "dispatch.rs").read_text(encoding="utf-8") == "\n" * 140 + DISPATCH_DEPOIS


def test_o_programa_com_a_marca_passa_e_o_de_cima_reprova(tmp_path: Path) -> None:
    """MORDIDA: a régua sem o grep da MARCA_ aprova o binário de cima."""
    de_cima = tmp_path / "de-cima"
    de_cima.write_bytes(b"\x7fELF" + b"/vendor/cosmic-client-toolkit/src/screencopy/dispatch.rs\0")
    da_casa = tmp_path / "da-casa"
    da_casa.write_bytes(b"\x7fELF/obra/" + MARCA.encode() + b"\0")
    r_cima = _rodar_construtor("--conferir-programa", str(de_cima))
    r_casa = _rodar_construtor("--conferir-programa", str(da_casa))
    assert r_cima.returncode == 6, r_cima.stderr
    assert r_casa.returncode == 0, r_casa.stderr


def _ferramentas(pasta: Path) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    for nome in (
        "bash",
        "env",
        "awk",
        "sed",
        "grep",
        "tar",
        "gzip",
        "find",
        "mv",
        "cp",
        "rm",
        "mkdir",
        "cat",
        "head",
        "tail",
        "dirname",
        "sha256sum",
        "patch",
        "dpkg-parsechangelog",
        "nproc",
        "tr",
        "diff",
        "sort",
        "ls",
        "mktemp",
        "perl",
        "dpkg",
        "printf",
        "chmod",
        "touch",
    ):
        achado = shutil.which(nome)
        if achado:
            (pasta / nome).symlink_to(achado)
    return pasta


def _fonte_de_mentira(pasta: Path, dispatch: str) -> tuple[str, str]:
    vendor = io.BytesIO()
    with tarfile.open(fileobj=vendor, mode="w") as t:
        for nome, texto in (
            ("vendor/cosmic-client-toolkit/src/screencopy/dispatch.rs", "\n" * 140 + dispatch),
            (
                "vendor/cosmic-client-toolkit/Cargo.toml",
                '[package]\nname = "cosmic-client-toolkit"\n',
            ),
            ("vendor/cosmic-protocols/Cargo.toml", '[package]\nname = "cosmic-protocols"\n'),
            (".cargo/config.toml", '[source.vendored-sources]\ndirectory = "vendor"\n'),
        ):
            dado = texto.encode()
            info = tarfile.TarInfo(nome)
            info.size = len(dado)
            t.addfile(info, io.BytesIO(dado))
    lock = (
        f'[[package]]\nname = "cosmic-client-toolkit"\nversion = "0.2.0"\n'
        f'source = "{FONTE_GIT}"\n\n'
        f'[[package]]\nname = "cosmic-protocols"\nversion = "0.2.0"\nsource = "{FONTE_GIT}"\n'
    )
    changelog = (
        f"{PACOTE} ({DE_CIMA}) noble; urgency=medium\n\n  * de cima\n\n"
        " -- Pop OS <info@system76.com>  Sat, 01 Nov 2026 00:00:00 +0000\n"
    )
    nome_tar = f"{PACOTE}_{DE_CIMA}.tar.gz"
    with tarfile.open(pasta / nome_tar, mode="w:gz") as t:
        for nome, dado in (
            ("archive/debian/changelog", changelog.encode()),
            (
                "archive/Cargo.toml",
                b'[package]\nname = "xdg-desktop-portal-cosmic"\nedition = "2021"\n',
            ),
            ("archive/Cargo.lock", lock.encode()),
            ("archive/vendor.tar", vendor.getvalue()),
        ):
            info = tarfile.TarInfo(nome)
            info.size = len(dado)
            t.addfile(info, io.BytesIO(dado))
    dado_tar = (pasta / nome_tar).read_bytes()
    sha = hashlib.sha256(dado_tar).hexdigest()
    dsc = (
        f"Format: 3.0 (native)\nSource: {PACOTE}\n"
        f"Checksums-Sha256:\n {sha} {len(dado_tar)} {nome_tar}\n"
    )
    (pasta / f"{PACOTE}_{DE_CIMA}.dsc").write_text(dsc, encoding="utf-8")
    return nome_tar, sha


@dataclass
class Construcao:
    rc: int
    saida: str
    chamadas: list[str]
    cache: Path


def _construir(tmp_path: Path, dispatch: str, *, curadas: str = "",
               adulterar: bool = False) -> Construcao:
    fonte = tmp_path / "fonte"
    fonte.mkdir()
    nome_tar, _sha = _fonte_de_mentira(fonte, dispatch)
    if adulterar:
        with (fonte / nome_tar).open("ab") as tar:
            tar.write(b"\0")
    diario = tmp_path / "chamadas.log"
    fakes = _ferramentas(tmp_path / "bin")
    _dpkg_query(fakes, {PACOTE: ("ii ", DE_CIMA)})
    _exe(
        fakes,
        "apt-get",
        f'printf "apt-get %s\\n" "$*" >> "{diario}"\ncp "{fonte}"/* .\n',
    )
    cache = tmp_path / "cache"
    if curadas:
        (cache / "portal-cosmic-backport").mkdir(parents=True)
        (cache / "portal-cosmic-backport" / "A-ORIGEM-JA-CURA.txt").write_text(
            curadas, encoding="utf-8"
        )
    r = _rodar_construtor(
        "--preparar",
        env={
            "PATH": str(fakes),
            "HOME": str(tmp_path / "lar"),
            "HEFESTO_PORTAL_CACHE": str(cache),
            "HEFESTO_PORTAL_JOBS": "2",
        },
    )
    chamadas = diario.read_text(encoding="utf-8").splitlines() if diario.exists() else []
    return Construcao(r.returncode, r.stdout + r.stderr, chamadas, cache)


def test_sem_rust_o_construtor_recusa_e_diz_o_que_instalar(tmp_path: Path) -> None:
    """MORDIDA: sem o teste do cargo, o construtor segue e morre no meio do build."""
    c = _construir(tmp_path, DISPATCH_ANTES)
    assert c.rc == 3, c.saida
    assert "o Rust, cargo e rustc" in c.saida, c.saida
    assert "rustup" in c.saida, c.saida
    assert "o stdbool.h" in c.saida or "o gcc" in c.saida, c.saida
    toml = next((c.cache / "portal-cosmic-obra").glob(f"{PACOTE}-*/Cargo.toml")).read_text(
        encoding="utf-8"
    )
    assert '[patch."https://github.com/pop-os/cosmic-protocols"]' in toml
    assert (
        f'cosmic-client-toolkit = {{ path = "../{BASE["ARVORE_DO_PATCH"]}/client-toolkit" }}'
        in toml
    )


def test_o_fonte_do_portal_so_vem_do_apt_assinado(tmp_path: Path) -> None:
    """Prova da D-0911-A-ORIGEM-DO-FONTE-SE-CONFERE-PELA-ASSINATURA: o fonte do portal vem só do
    apt, com a autenticação do índice forçada mesmo que um apt.conf da máquina a desligue."""
    c = _construir(tmp_path, DISPATCH_ANTES)
    busca = [linha for linha in c.chamadas if " source " in linha]
    assert len(busca) == 1, c.chamadas
    for opcao in ("APT::Get::AllowUnauthenticated=false",
                  "Acquire::AllowInsecureRepositories=false",
                  "Acquire::AllowDowngradeToInsecureRepositories=false"):
        assert f"-o {opcao}" in busca[0], busca[0]
    assert "--allow-unauthenticated" not in busca[0] and "trusted=yes" not in busca[0]


def test_o_tarball_do_portal_que_nao_bate_com_o_dsc_nao_se_usa(tmp_path: Path) -> None:
    c = _construir(tmp_path, DISPATCH_ANTES, adulterar=True)
    assert c.rc == 4, c.saida
    assert "não confere com o" in c.saida, c.saida
    assert not list((c.cache / "portal-cosmic-obra").glob(f"{PACOTE}-*/Cargo.toml"))


def test_a_versao_de_cima_que_ja_traz_o_pr_e_nada_a_fazer(tmp_path: Path) -> None:
    """MORDIDA: sem a régua do dispatch de cima, o construtor remenda o que já está curado."""
    c = _construir(tmp_path, DISPATCH_DEPOIS)
    assert c.rc == 9, c.saida
    assert "nada a fazer" in c.saida, c.saida
    curadas = c.cache / "portal-cosmic-backport" / "A-ORIGEM-JA-CURA.txt"
    assert curadas.read_text(encoding="utf-8").splitlines() == [DE_CIMA]
    assert not (c.cache / "portal-cosmic-obra" / BASE["ARVORE_DO_PATCH"]).exists()


def test_a_versao_ja_registrada_como_curada_nem_busca_o_fonte(tmp_path: Path) -> None:
    c = _construir(tmp_path, DISPATCH_ANTES, curadas=f"{DE_CIMA}\n")
    assert c.rc == 9, c.saida
    assert not c.chamadas, c.chamadas


FUNCOES_EXTRAIDAS = (
    "ask_yn",
    "_pacotes_a_meio",
    "_avisa_pacote_a_meio",
    "_pw_versao_ii",
    "_pc_ler",
    "_pc_portal_no_cosmic",
    "_pc_trocas_do_exec",
    "_pc_avisa_trocas_do_exec",
    "_pc_deb_confere",
    "_pc_reiniciar_o_portal",
    "install_portal_cosmic_da_casa",
)


def _funcao(nome: str) -> str:
    inicio = INSTALL.index(f"{nome}() {{\n")
    fim = INSTALL.index("\n}\n", inicio) + 3
    return INSTALL[inicio:fim]


def _guarda_do_passo() -> str:
    marca = "    install_portal_cosmic_da_casa\nfi\n"
    fim = INSTALL.index(marca) + len(marca)
    inicio = INSTALL.rindex('\nif [[ "${SKIP_UDEV}" -eq 0 ]]', 0, fim) + 1
    return INSTALL[inicio:fim]


@dataclass
class Corrida:
    rc: int
    saida: str
    chamadas: list[str]
    lar: Path
    segundos: float

    def chamou(self, trecho: str) -> bool:
        return any(trecho in linha for linha in self.chamadas)


MAQUINA_COSMIC = {PACOTE: ("ii ", DE_CIMA), "cosmic-comp": ("ii ", "1.0.0")}


def _correr(
    tmp_path: Path,
    *,
    maquina: dict[str, tuple[str, str]] | None = None,
    desktop: str = "COSMIC",
    rc_construtor: int = 0,
    estragar: bool = False,
    sudo_ok: bool = True,
    dry_run: bool = False,
    dropins: dict[str, str] | None = None,
) -> Corrida:
    maquina = MAQUINA_COSMIC if maquina is None else maquina
    lar = tmp_path / "lar"
    lar.mkdir()
    raiz = tmp_path / "raiz"
    (raiz / "assets" / "portal-cosmic-backport" / "apt").mkdir(parents=True)
    for rel in ("BASELINE", "apt/hefesto-portal-cosmic.pref"):
        shutil.copy(ASSETS / rel, raiz / "assets" / "portal-cosmic-backport" / rel)
    for nome, texto in (dropins or {}).items():
        alvo = lar / ".config" / "systemd" / "user" / f"{UNIDADE}.d" / nome
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(texto, encoding="utf-8")
    diario = tmp_path / "chamadas.log"
    fakes = tmp_path / "fakes"
    deb = f"{PACOTE}_{DA_CASA}_amd64.deb"
    _exe(
        raiz / "scripts",
        "construir_portal_cosmic_backport.sh",
        f'printf "construtor %s\\n" "$HEFESTO_PORTAL_CACHE" >> "{diario}"\n'
        'saida="$HEFESTO_PORTAL_CACHE/portal-cosmic-backport"\n'
        'mkdir -p "$saida"\n'
        f'printf "deb de mentira" > "$saida/{deb}"\n'
        f'(cd "$saida" && sha256sum {deb} > SHA256SUMS)\n'
        + (f'printf "outros bytes" > "$saida/{deb}"\n' if estragar else "")
        + 'echo "[portal-cosmic-backport] falta, para construir o portal da casa:" >&2\n'
        'echo "    - o Rust, cargo e rustc (pelo rustup)" >&2\n'
        f"exit {rc_construtor}\n",
    )
    _dpkg_query(fakes, maquina)
    _exe(
        fakes,
        "dpkg",
        'if [[ "$1" == "--print-architecture" ]]; then echo amd64; exit 0; fi\n'
        f'exec "{DPKG}" "$@"\n',
    )
    _exe(fakes, "apt-get", f'printf "apt-get %s\\n" "$*" >> "{diario}"\nexit 0\n')
    _exe(
        fakes,
        "sudo",
        f'printf "sudo %s\\n" "$*" >> "{diario}"\n'
        f'if [[ "$1" == "-n" ]]; then exit {0 if sudo_ok else 1}; fi\n'
        'if [[ "$1" == "env" ]]; then exec "$@"; fi\n'
        "exit 0\n",
    )
    _exe(
        fakes,
        "systemctl",
        f'printf "systemctl %s\\n" "$*" >> "{diario}"\n'
        '[[ " $* " == *" --no-block "* ]] || sleep 30\n'
        "exit 0\n",
    )
    funcoes = "".join(_funcao(n) for n in FUNCOES_EXTRAIDAS)
    script = (
        "set -euo pipefail\n"
        'step() { printf \'\\n[%s] %s\\n\' "$1" "$2"; }\n'
        "warn() { printf '      aviso: %s\\n' \"$*\"; }\n"
        "_faria() { printf '      FARIA        %s\\n' \"$*\"; }\n"
        "_faria_root() { printf '      FARIA (root) %s\\n' \"$*\"; }\n"
        "SKIP_UDEV=0\n" + funcoes + _guarda_do_passo()
    )
    sistema = tmp_path / "sistema"
    sistema.mkdir()
    inicio = time.monotonic()
    r = subprocess.run(
        [BASH, "-c", script],
        env={
            "PATH": f"{fakes}:/usr/bin:/bin",
            "HOME": str(lar),
            "ROOT_DIR": str(raiz),
            "AUTO_YES": "1",
            "DRY_RUN": "1" if dry_run else "0",
            "XDG_CURRENT_DESKTOP": desktop,
            "_PC_SYSTEMD_DO_SISTEMA": str(sistema),
        },
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    segundos = time.monotonic() - inicio
    chamadas = diario.read_text(encoding="utf-8").splitlines() if diario.exists() else []
    return Corrida(r.returncode, r.stdout + r.stderr, chamadas, lar, segundos)


def test_no_cosmic_constroi_instala_fixa_o_apt_e_reinicia_sem_prender(tmp_path: Path) -> None:
    """Prova da D-0111-O-INSTALL-CONSTROI-O-PORTAL-DO-COSMIC-DA-CASA.

    MORDIDA: sem o --no-block, o systemctl que espera o portal prende o install.
    """
    c = _correr(tmp_path)
    assert c.rc == 0, c.saida
    assert c.chamou("construtor "), c.chamadas
    assert c.chamou(
        "apt-get install -y -o Dpkg::Options::=--force-confdef "
        "-o Dpkg::Options::=--force-confold "
        f"{c.lar}/.cache/hefesto-dualsense4unix/portal-cosmic-backport/{PACOTE}_{DA_CASA}_amd64.deb"
    ), c.chamadas
    assert c.chamou("/etc/apt/preferences.d/hefesto-portal-cosmic"), c.chamadas
    assert c.chamou(f"systemctl --user try-restart --no-block {UNIDADE}"), c.chamadas
    assert "AVISO: instalar o portal da casa REINICIA o portal de captura" in c.saida, c.saida
    assert "compartilhamento de tela aberto agora cai uma vez" in c.saida, c.saida
    assert c.segundos < 10, c.segundos
    anteriores = (
        c.lar
        / ".cache"
        / "hefesto-dualsense4unix"
        / "portal-cosmic-backport"
        / "VERSOES-ANTERIORES.txt"
    )
    assert anteriores.read_text(encoding="utf-8") == f"{PACOTE}={DE_CIMA}\n"


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize(
    ("maquina", "desktop"),
    [
        ({PACOTE: ("ii ", DE_CIMA)}, "GNOME"),
        ({PACOTE: ("ii ", DE_CIMA)}, ""),
        ({"cosmic-comp": ("ii ", "1.0.0")}, "COSMIC"),
        ({PACOTE: ("rc ", DE_CIMA), "cosmic-comp": ("ii ", "1.0.0")}, "COSMIC"),
    ],
)
def test_fora_do_cosmic_ou_sem_o_portal_o_passo_fica_calado(
    tmp_path: Path, maquina: dict[str, tuple[str, str]], desktop: str, dry_run: bool
) -> None:
    """MORDIDA: sem a guarda do COSMIC, o GNOME com o portal instalado constrói o do COSMIC."""
    c = _correr(tmp_path, maquina=maquina, desktop=desktop, dry_run=dry_run)
    assert c.rc == 0, c.saida
    assert c.saida == "", c.saida
    assert not c.chamadas, c.chamadas


def test_cosmic_pela_sessao_sem_o_cosmic_comp_no_dpkg_tambem_vale(tmp_path: Path) -> None:
    c = _correr(tmp_path, maquina={PACOTE: ("ii ", DE_CIMA)}, desktop="pop:COSMIC")
    assert "[3f-ter]" in c.saida, c.saida
    assert c.chamou("construtor "), c.chamadas


def test_a_versao_de_cima_que_ja_cura_e_nada_a_fazer_sem_instalar(tmp_path: Path) -> None:
    """MORDIDA: tratar o código 9 como falha manda o aviso de construção parada."""
    c = _correr(tmp_path, rc_construtor=9)
    assert c.rc == 0, c.saida
    assert f"o {DE_CIMA} de cima já traz o cosmic-protocols#92 — nada a fazer" in c.saida, c.saida
    assert "aviso:" not in c.saida, c.saida
    assert not c.chamou("apt-get"), c.chamadas
    assert not c.chamou("systemctl"), c.chamadas


def test_o_portal_da_casa_ja_instalado_e_nada_a_fazer_sem_construir(tmp_path: Path) -> None:
    c = _correr(tmp_path, maquina={PACOTE: ("ii ", DA_CASA), "cosmic-comp": ("ii ", "1.0.0")})
    assert c.rc == 0, c.saida
    assert "já é o da casa" in c.saida and "nada a fazer" in c.saida, c.saida
    assert not c.chamadas, c.chamadas


def test_sem_rust_o_passo_diz_o_que_falta_e_nao_instala(tmp_path: Path) -> None:
    c = _correr(tmp_path, rc_construtor=3)
    assert c.rc == 0, c.saida
    assert "faltam dependências de build do portal da casa" in c.saida, c.saida
    assert "o Rust, cargo e rustc (pelo rustup)" in c.saida, c.saida
    assert "receita-backport-portal-cosmic.md" in c.saida, c.saida
    assert not c.chamou("apt-get"), c.chamadas


def test_o_drop_in_de_outro_projeto_que_troca_o_exec_ganha_aviso_e_fica(tmp_path: Path) -> None:
    """MORDIDA: sem o aviso, o portal da casa se instala e o drop-in segue rodando outro binário."""
    outro = "%h/.local/libexec/outro/portal/xdg-desktop-portal-cosmic"
    texto = f"[Service]\nExecStart=\nExecStart={outro}\n"
    c = _correr(tmp_path, dropins={"outro-projeto.conf": texto})
    alvo = c.lar / ".config" / "systemd" / "user" / f"{UNIDADE}.d" / "outro-projeto.conf"
    assert c.rc == 0, c.saida
    assert f"aviso: {alvo} troca o ExecStart do portal de captura por {outro}" in c.saida, c.saida
    assert "o Hefesto não o apaga" in c.saida, c.saida
    assert alvo.read_text(encoding="utf-8") == texto
    assert not c.chamou(str(alvo)), c.chamadas


@pytest.mark.parametrize(
    "texto",
    [
        "[Service]\nEnvironment=RUST_LOG=debug\n",
        f"[Service]\nExecStart=\nExecStart={BASE['PORTAL_EXEC']} --verbose\n",
    ],
)
def test_drop_in_que_nao_troca_o_programa_nao_ganha_aviso(tmp_path: Path, texto: str) -> None:
    c = _correr(tmp_path, dropins={"ajuste.conf": texto})
    assert "troca o ExecStart" not in c.saida, c.saida


def test_entrega_que_nao_confere_pelo_sha256sums_nao_instala(tmp_path: Path) -> None:
    c = _correr(tmp_path, estragar=True)
    assert "não confere pelo SHA256SUMS" in c.saida, c.saida
    assert not c.chamou("apt-get"), c.chamadas
    assert not c.chamou("systemctl"), c.chamadas


def test_sudo_recusado_nao_instala(tmp_path: Path) -> None:
    c = _correr(tmp_path, sudo_ok=False)
    assert "sudo recusado" in c.saida, c.saida
    assert not c.chamou("apt-get"), c.chamadas


def test_o_ensaio_mostra_a_troca_e_nao_constroi(tmp_path: Path) -> None:
    c = _correr(tmp_path, dry_run=True)
    assert "FARIA (root) instalar o" in c.saida, c.saida
    assert "REINICIAR o portal de captura" in c.saida, c.saida
    assert not c.chamadas, c.chamadas


def test_o_passo_extraido_leva_toda_funcao_que_ele_chama() -> None:
    corpo = "".join(_funcao(n) for n in FUNCOES_EXTRAIDAS) + _guarda_do_passo()
    for nome in ("_pc_", "install_portal_cosmic_da_casa"):
        for linha in corpo.splitlines():
            for palavra in linha.replace("(", " ").replace('"', " ").replace("$", " ").split():
                if palavra.startswith(nome) and palavra.isidentifier():
                    assert palavra in FUNCOES_EXTRAIDAS, palavra


def test_o_passo_vem_depois_do_pipewire_e_antes_do_agente_bluetooth() -> None:
    assert (
        INSTALL.index('step "3f-bis"') < INSTALL.index('step "3f-ter"') < INSTALL.index('step "3g"')
    )
    assert "_pc_portal_no_cosmic; then" in _guarda_do_passo()


def _doctor(
    tmp_path: Path,
    *,
    programa: bytes | None = None,
    maquina: dict[str, tuple[str, str]] | None = None,
    desktop: str = "COSMIC",
    curadas: str = "",
    dropins: dict[str, str] | None = None,
    pid_vivo: int | None = None,
) -> str:
    maquina = MAQUINA_COSMIC if maquina is None else maquina
    lar = tmp_path / "lar"
    lar.mkdir(exist_ok=True)
    fakes = tmp_path / "fakes-doctor"
    _dpkg_query(fakes, maquina)
    _exe(fakes, "systemctl", f"echo {pid_vivo or 0}\n")
    for nome, texto in (dropins or {}).items():
        alvo = lar / ".config" / "systemd" / "user" / f"{UNIDADE}.d" / nome
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(texto, encoding="utf-8")
    env = {
        "PATH": f"{fakes}:/usr/bin:/bin",
        "HOME": str(lar),
        "XDG_CURRENT_DESKTOP": desktop,
        "HEFESTO_DOCTOR_SYSTEMD_DO_SISTEMA": str(tmp_path / "sistema-vazio"),
        "HEFESTO_DOCTOR_PORTAL_CURADAS": str(tmp_path / "curadas.txt"),
    }
    original = (ASSETS / "BASELINE").read_text(encoding="utf-8")
    de_mentira = original.replace(
        f"PORTAL_EXEC={BASE['PORTAL_EXEC']}\n",
        f"PORTAL_EXEC={tmp_path / 'sem-portal-oficial'}\n",
    )
    assert de_mentira != original, "o BASELINE de mentira manteria o PORTAL_EXEC da máquina"
    baseline = tmp_path / "BASELINE"
    baseline.write_text(de_mentira, encoding="utf-8")
    env["HEFESTO_DOCTOR_PORTAL_BASELINE"] = str(baseline)
    if curadas:
        (tmp_path / "curadas.txt").write_text(curadas, encoding="utf-8")
    if programa is not None:
        (tmp_path / "portal").write_bytes(programa)
        env["HEFESTO_DOCTOR_PORTAL_COSMIC"] = str(tmp_path / "portal")
    script = (
        f'source "{DOCTOR}"\nQUIET=0\nWARNS=0\n'
        "check_o_portal_de_captura_do_cosmic\n"
        'echo "WARNS=${WARNS}"\n'
    )
    r = subprocess.run(
        [BASH, "-c", script], env=env, capture_output=True, text=True, timeout=60, check=False
    )
    return r.stdout + r.stderr


def test_o_doctor_aprova_o_portal_com_a_marca(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, programa=b"\x7fELF/x/" + MARCA.encode())
    assert "[ OK ] o portal de captura" in saida and "WARNS=0" in saida, saida


def test_o_doctor_avisa_o_portal_de_cima_sem_a_marca(tmp_path: Path) -> None:
    """MORDIDA: sem o grep da MARCA_, o doctor aprova o portal de cima."""
    saida = _doctor(
        tmp_path, programa=b"\x7fELF/vendor/cosmic-client-toolkit/src/screencopy/dispatch.rs"
    )
    assert "[WARN] o portal de captura" in saida, saida
    assert "não traz o cosmic-protocols#92" in saida, saida
    assert "WARNS=1" in saida, saida


def test_o_doctor_aprova_a_versao_de_cima_que_ja_cura(tmp_path: Path) -> None:
    saida = _doctor(tmp_path, programa=b"\x7fELF sem marca", curadas=f"{DE_CIMA}\n")
    assert "já traz de cima a cura" in saida and "WARNS=0" in saida, saida


def test_o_doctor_fica_calado_fora_do_cosmic(tmp_path: Path) -> None:
    saida = _doctor(
        tmp_path, programa=b"\x7fELF", maquina={PACOTE: ("ii ", DE_CIMA)}, desktop="GNOME"
    )
    assert saida.strip() == "WARNS=0", saida


def test_o_doctor_avisa_o_drop_in_de_outro_projeto_e_nao_o_apaga(tmp_path: Path) -> None:
    texto = "[Service]\nExecStart=\nExecStart=/opt/outro/xdg-desktop-portal-cosmic\n"
    saida = _doctor(
        tmp_path, programa=b"\x7fELF/x/" + MARCA.encode(), dropins={"outro.conf": texto}
    )
    alvo = tmp_path / "lar" / ".config" / "systemd" / "user" / f"{UNIDADE}.d" / "outro.conf"
    assert (
        f"[WARN] {alvo} troca o ExecStart do portal de captura por "
        "/opt/outro/xdg-desktop-portal-cosmic" in saida
    ), saida
    assert "o doctor não o apaga" in saida, saida
    assert alvo.read_text(encoding="utf-8") == texto


def _portal_em_execucao(copia: Path) -> subprocess.Popen[bytes]:
    """Uma cópia do ``bash`` com a marca, parada num ``read`` de 30 s dentro do próprio processo.

    O ``sleep`` não serve: no Ubuntu 26.04 ele é o coreutils de Rust, um binário multichamada que
    recusa o nome da cópia (``unknown program``) e morre antes de o doctor ler o ``/proc``."""
    bash = shutil.which("bash")
    assert bash is not None
    copia.write_bytes(Path(bash).read_bytes() + b"\0/obra/" + MARCA.encode() + b"\0")
    copia.chmod(0o755)
    processo = subprocess.Popen([str(copia), "-c", "read -t 30"], stdin=subprocess.PIPE)
    assert processo.poll() is None, "a cópia do programa morreu ao nascer"
    return processo


def _parar(processo: subprocess.Popen[bytes]) -> None:
    assert processo.stdin is not None
    processo.stdin.close()
    processo.kill()
    processo.wait(timeout=10)


def test_o_doctor_le_o_programa_que_o_systemd_executa(tmp_path: Path) -> None:
    """MORDIDA: ler só o /usr/libexec deixa de ver o binário que o processo do portal roda."""
    copia = tmp_path / "xdg-desktop-portal-cosmic"
    processo = _portal_em_execucao(copia)
    try:
        saida = _doctor(tmp_path, pid_vivo=processo.pid)
    finally:
        _parar(processo)
    assert f"[ OK ] o portal de captura ({copia})" in saida, saida


def test_o_doctor_le_o_programa_em_execucao_mesmo_trocado_no_disco(tmp_path: Path) -> None:
    """MORDIDA: ler o caminho do disco, e não o /proc/PID/exe, perde o programa que o apt trocou."""
    copia = tmp_path / "xdg-desktop-portal-cosmic"
    processo = _portal_em_execucao(copia)
    try:
        copia.unlink()
        saida = _doctor(tmp_path, pid_vivo=processo.pid)
    finally:
        _parar(processo)
    assert f"[ OK ] o portal de captura ({copia} (deleted))" in saida, saida


def test_o_programa_de_outro_projeto_sem_a_marca_e_nao_sei_e_nao_reprovado(
    tmp_path: Path,
) -> None:
    """MORDIDA: sem a guarda do drop-in, o doctor afirma que o programa de outro projeto cai."""
    texto = "[Service]\nExecStart=\nExecStart=/opt/outro/xdg-desktop-portal-cosmic\n"
    saida = _doctor(tmp_path, programa=b"\x7fELF outro build", dropins={"outro.conf": texto})
    assert "o doctor não sabe se ele traz o cosmic-protocols#92" in saida, saida
    assert "não traz o cosmic-protocols#92" not in saida, saida
    assert "WARNS=1" in saida, saida


def test_a_receita_diz_o_construtor_a_volta_e_o_drop_in() -> None:
    texto = RECEITA.read_text(encoding="utf-8")
    for trecho in (
        "scripts/construir_portal_cosmic_backport.sh",
        "VERSOES-ANTERIORES.txt",
        "/etc/apt/preferences.d/hefesto-portal-cosmic",
        "ExecStart",
        "cosmic-protocols#92",
        "3f-ter",
    ):
        assert trecho in texto, trecho
