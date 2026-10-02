"""README-DKMS-SUDO-01 — nenhum arquivo versionado manda rodar o `install.sh` com sudo."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SUDO_INSTALL_RE = re.compile(
    r"sudo\b(?:\s+-\w+)*\s+(?:(?:bash|sh|zsh)\s+)?(?:\./)?(?<!un)install\.sh\b"
)

_SEM_TEXTO = {".png", ".svg", ".mo", ".ico", ".gif", ".jpg", ".jpeg", ".webp"}

DISPENSAS: dict[str, str] = {
    "tests/unit/test_nenhum_arquivo_manda_rodar_install_com_sudo.py": (
        "é o portão; ele escreve a forma proibida para reconhecê-la"
    ),
}


def _arquivos_rastreados() -> list[Path]:
    saida = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [
        REPO_ROOT / nome
        for nome in saida.split("\0")
        if nome and Path(nome).suffix.lower() not in _SEM_TEXTO
    ]


def test_o_regex_reconhece_as_formas_e_poupa_o_uninstall() -> None:
    """A régua antes da medição — senão o portão verde não prova nada."""
    for proibida in (
        "sudo install.sh",
        "sudo bash install.sh",
        "sudo sh install.sh",
        "sudo ./install.sh",
        "sudo bash ./install.sh",
        "sudo -E bash install.sh",
        "sudo -E ./install.sh",
    ):
        assert SUDO_INSTALL_RE.search(proibida), f"o portão é cego a {proibida!r}"
    for permitida in (
        "./install.sh --yes",
        "bash install.sh",
        "sudo bash uninstall.sh",
        "sudo ./uninstall.sh",
        "re-execute ./install.sh",
        'warn "sudo recusado — passo pulado (re-execute ./install.sh)"',
        "sudo apt install dkms",
    ):
        assert not SUDO_INSTALL_RE.search(permitida), (
            f"o portão reprova o que é legítimo: {permitida!r}"
        )


def test_nenhum_arquivo_versionado_manda_instalar_com_sudo() -> None:
    violacoes: list[str] = []
    for caminho in _arquivos_rastreados():
        rel = caminho.relative_to(REPO_ROOT).as_posix()
        if rel in DISPENSAS:
            continue
        try:
            texto = caminho.read_text(encoding="utf-8", errors="ignore")
        except (OSError, IsADirectoryError):
            continue
        for numero, linha in enumerate(texto.splitlines(), start=1):
            if SUDO_INSTALL_RE.search(linha):
                violacoes.append(f"{rel}:{numero}: {linha.strip()}")
    assert not violacoes, (
        "`install.sh` NUNCA com sudo — com sudo o HOME vira /root e a instalação "
        "não existe para o usuário. A forma certa é `./install.sh` (ou "
        "`./install.sh --yes` sem terminal interativo): o script pede a senha "
        "sozinho no passo que precisa dela.\n  " + "\n  ".join(violacoes)
    )


def test_toda_dispensa_e_um_arquivo_que_de_fato_cita_a_forma_proibida() -> None:
    """A dispensa vale por ARQUIVO INTEIRO — então ela não pode ser barata."""
    rastreados = {
        c.relative_to(REPO_ROOT).as_posix() for c in _arquivos_rastreados()
    }
    for rel, razao in DISPENSAS.items():
        assert rel in rastreados, (
            f"dispensa aponta para arquivo que o git não rastreia: {rel} — "
            "o portão nem o varreria, então a linha só engorda a lista"
        )
        texto = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        assert SUDO_INSTALL_RE.search(texto), (
            f"dispensa RANÇOSA: {rel} já não cita a forma proibida ({razao!r}). "
            "Apague a linha — enquanto ela existir, o portão está desligado "
            "para esse arquivo inteiro sem que nada o justifique"
        )


def test_o_readme_do_dkms_ensina_a_forma_certa() -> None:
    """O arquivo que viaja no .deb/PKGBUILD/RPM tem de trazer a forma correta."""
    readme = REPO_ROOT / "assets" / "dkms" / "hid-nintendo" / "README.md"
    texto = readme.read_text(encoding="utf-8")
    assert "./install.sh --yes" in texto, (
        "o README empacotado tem de mostrar a invocação certa, não só deixar de "
        "mostrar a errada — quem instala por pacote lê este arquivo na máquina"
    )
    assert re.search(r"HOME vira /root", texto), (
        "e tem de dizer POR QUE, ali mesmo: sem a razão, o `sudo` volta na "
        "primeira vez que alguém encontrar um passo pedindo senha"
    )
