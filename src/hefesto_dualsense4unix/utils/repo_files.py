"""Onde os arquivos do repositório (scripts, confs) estão em CADA instalação.

BG-05 (25/08/2026) — *o Python procura onde o pacote põe*.

O produto roda os scripts de `scripts/` a partir do Python: o `doctor` chama
`scripts/doctor.sh`, o `--fix-safe` chama mais três, e a aba Sistema chama
outros dois. Achar esses arquivos é uma pergunta só — **em que diretório esta
instalação pôs o `share/` do Hefesto?** — e a pergunta tinha DUAS respostas no
código, que já haviam divergido:

- `app/actions/daemon_actions.py:354` (`BASES_DE_INSTALACAO`) — ganhou
  `/app/share` na T-02(b), hoje;
- `cli/cmd_doctor.py:47` (`_find_repo_file`) — ficou com as três bases de
  sempre, e por isso o `doctor` continuava cego no Flatpak.

Este módulo é a resposta única. **BG-BASES-01 (26/08/2026): as outras quatro
listas morreram aqui.** Eram cinco no total, e as quatro que sobreviviam ao
`cmd_doctor` cobriam bases diferentes umas das outras — por isso o mesmo
clique achava o script num formato de instalação e falhava no outro:

| resolvedor | bases | o que faltava |
|---|---|---|
| `daemon_actions.py:354` (`BASES_DE_INSTALACAO`) | 4 | `sys.prefix` e o `share/` do usuário |
| `emulation_actions.py` (`_mic_script`) | 3 | as duas acima **e `/app/share`** |
| `emulation_actions.py` (`_steam_input_script`) | 3 | as mesmas três |
| `cli/cmd_mic.py:91` (`_find_script`) | 3 | as mesmas três |

`sys.prefix/share/…` é AppImage, venv e Nix; `/app/share` é o Flatpak; o
`share/` do usuário é o `pip install --user`.

Todas passaram a chamar `encontrar_arquivo_do_repo()`.

Cada base abaixo é um destino MEDIDO de instalação, não uma suposição.

**O conselho de atualizar mora aqui pelo mesmo motivo** (BG-INSTALL-01):
`esta_instalacao_e_um_checkout()` e `como_atualizar_esta_instalacao()`
nasceram na T-03 dentro de `app/actions/daemon_actions.py`, e três frases de
tela que precisavam desses arquivos vivem FORA do `app/` — `integrations/storm_doctor.py`
é uma dessas frases, e fazer `integrations/` importar de `app/` inverteria a camada.
A pergunta é a mesma deste módulo (*"o que esta instalação tem ao lado do
código?"*), então a resposta fica no mesmo lugar.
"""
from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from pathlib import Path

from hefesto_dualsense4unix.utils import xdg_paths

NOME_NO_SHARE = "hefesto-dualsense4unix"


def bases_de_instalacao() -> tuple[Path, ...]:
    """Os diretórios-base onde os arquivos do repo podem estar, em ordem."""
    candidatas = (
        Path(__file__).resolve().parents[3],
        Path(sys.prefix) / "share" / NOME_NO_SHARE,
        Path("/app/share") / NOME_NO_SHARE,
        xdg_paths.data_dir(),
        Path("/usr/share") / NOME_NO_SHARE,
        Path("/usr/local/share") / NOME_NO_SHARE,
    )
    vistas: set[str] = set()
    ordenadas: list[Path] = []
    for base in candidatas:
        chave = str(base)
        if chave in vistas:
            continue
        vistas.add(chave)
        ordenadas.append(base)
    return tuple(ordenadas)


def encontrar_arquivo_do_repo(
    relpath: str, bases: Sequence[Path] | None = None
) -> Path | None:
    """O caminho REAL de um arquivo do repo (ex.: `scripts/doctor.sh`)."""
    for base in bases if bases is not None else bases_de_instalacao():
        candidato = base / relpath
        if candidato.is_file():
            return candidato
    return None


def ler_arquivo_do_repo(relpath: str, bases: Sequence[Path] | None = None) -> str | None:
    """O texto de um arquivo do repo em UTF-8, ou ``None`` quando nenhuma base o tem."""
    achado = encontrar_arquivo_do_repo(relpath, bases)
    return achado.read_text(encoding="utf-8") if achado is not None else None


PASTAS_DOS_GLIFOS = ("assets/glyphs", "glyphs")


def encontrar_glifo(arquivo: str, bases: Sequence[Path] | None = None) -> Path | None:
    """O SVG de um glifo (``cross_active.svg``): ``assets/glyphs`` no clone e no wheel, ``glyphs``
    no Flatpak, no AppImage e no ``install.sh``."""
    for pasta in PASTAS_DOS_GLIFOS:
        achado = encontrar_arquivo_do_repo(f"{pasta}/{arquivo}", bases)
        if achado is not None:
            return achado
    return None


FRASE_DE_ATUALIZAR: dict[bool, str] = {
    True: "rode ./install.sh para atualizar o Hefesto",
    False: "atualize o Hefesto pelo mesmo caminho por onde você o instalou",
}


def esta_instalacao_e_um_checkout(bases: Sequence[Path] | None = None) -> bool:
    """Há um `install.sh` ao lado deste código?"""
    lista = bases if bases is not None else bases_de_instalacao()
    return (lista[0] / "install.sh").is_file()


def como_atualizar_esta_instalacao(e_checkout: bool | None = None) -> str:
    """O gesto de atualizar que serve para ESTA instalação, sem jargão."""
    if e_checkout is None:
        e_checkout = esta_instalacao_e_um_checkout()
    return FRASE_DE_ATUALIZAR[bool(e_checkout)]


FORMA_CLONE, FORMA_DEB, FORMA_FLATPAK, FORMA_APPIMAGE, FORMA_OUTRA = (
    "clone", "deb", "flatpak", "appimage", "outra")
MARCA_DO_FLATPAK = Path("/.flatpak-info")
PREFIXO_DO_DEB = Path("/opt") / NOME_NO_SHARE

GESTO_DE_SUBIR: dict[str, str] = {
    FORMA_DEB: "Abra o .deb novo no instalador do sistema",
    FORMA_FLATPAK: "Baixe o .flatpak novo na página da versão",
    FORMA_APPIMAGE: "Baixe o AppImage novo na página da versão",
    FORMA_OUTRA: "Atualize o Hefesto pelo mesmo caminho por onde você o instalou",
}


def forma_da_instalacao(raiz: Path | None = None) -> str:
    """Como esta instalação chegou: clone (``.git`` na raiz), ``.deb``, Flatpak, AppImage ou
    outra (wheel, Arch, Fedora, Nix)."""
    base = raiz if raiz is not None else bases_de_instalacao()[0]
    if (base / ".git").exists():
        return FORMA_CLONE
    if MARCA_DO_FLATPAK.is_file() or os.environ.get("FLATPAK_ID"):
        return FORMA_FLATPAK
    if os.environ.get("APPIMAGE"):
        return FORMA_APPIMAGE
    if Path(sys.prefix).is_relative_to(PREFIXO_DO_DEB):
        return FORMA_DEB
    return FORMA_OUTRA


def gesto_de_subir_a_versao_nova(forma: str | None = None) -> str:
    """O gesto de quem usa para instalar a versão nova quando o Hefesto não a sobe sozinho;
    vazio no clone, que ele mesmo sobe."""
    return GESTO_DE_SUBIR.get(forma if forma is not None else forma_da_instalacao(), "")


__all__ = [
    "FORMA_CLONE",
    "FRASE_DE_ATUALIZAR",
    "GESTO_DE_SUBIR",
    "NOME_NO_SHARE",
    "PASTAS_DOS_GLIFOS",
    "bases_de_instalacao",
    "como_atualizar_esta_instalacao",
    "encontrar_arquivo_do_repo",
    "encontrar_glifo",
    "esta_instalacao_e_um_checkout",
    "forma_da_instalacao",
    "gesto_de_subir_a_versao_nova",
    "ler_arquivo_do_repo",
]
