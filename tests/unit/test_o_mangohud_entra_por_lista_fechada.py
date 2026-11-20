"""O MangoHud entra por lista fechada: o ajudante root nunca roda o script do pacote.

O-AJUDANTE-DO-ROOT-NAO-RODA-O-SCRIPT-DO-PACOTE-DO-MANGOHUD-01 (19/11/2026). O ajudante roda sem
root, com o tarball de mentira na casa de mentira, a raiz de mentira em
``HEFESTO_ATUALIZADOR_DESTINO`` e os dublês do ``test_o_ajudante_do_atualizador``.

AS MORDIDAS (feitas na sprint, com a cura devolvida e o md5 conferido): o
``bash ./mangohud-setup.sh install`` devolvido faz a marca nascer no caso do pacote bom; a lista
sem a recusa do link reprova o caso do link; a conferência de ``..`` arrancada reprova o caso dele.
Em 20/11/2026, medido no pacote 0.8.4 de verdade (a pasta ``.``, o ícone e o metainfo recusavam o
pacote inteiro, e as pastas nasciam 0700 sob o ``umask`` do ajudante): a pasta ``.`` recusada, o
ícone fora da lista e o ``umask`` do ajudante reprovam o caso do pacote bom; sem os links, o caso
dos links.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from tests.unit.test_o_ajudante_do_atualizador import (
    PACOTE_DO_MANGOHUD,
    Lar,
    _api,
    _tar_do_mangohud,
)


@pytest.fixture
def lar(tmp_path: Path) -> Lar:
    if os.geteuid() == 0:
        pytest.skip("o ajudante como root usa os caminhos de verdade")
    return Lar(tmp_path)


def _instalar(lar: Lar, membros: tuple[tuple[str, int, bytes, str], ...]) -> tuple[int, str]:
    arq = _tar_do_mangohud(lar, membros=membros)
    _api(lar, arq.name, hashlib.sha256(arq.read_bytes()).hexdigest())
    feito = lar.rodar("mangohud-instalar")
    return feito.returncode, feito.stderr


def _arvore(raiz: Path) -> list[str]:
    return sorted(str(p.relative_to(raiz)) for p in raiz.rglob("*"))


def test_o_pacote_bom_chega_aos_destinos_e_o_script_nao_roda(lar: Lar) -> None:
    """D-1911-O-MANGOHUD-ENTRA-POR-LISTA-FECHADA: os destinos da lista chegam e o setup não roda."""
    rc, erro = _instalar(lar, PACOTE_DO_MANGOHUD)
    assert rc == 0, erro
    assert not any(linha.startswith("setup") for linha in lar.lidas()), lar.lidas()
    lib = lar.destino / "usr/lib/mangohud/lib64/libMangoHud.so"
    assert lib.read_bytes() == b"ELF64" and lib.stat().st_mode & 0o7777 == 0o755
    assert (lar.destino / "usr/share/man/man1/mangohud.1").stat().st_mode & 0o7777 == 0o644
    assert (lar.destino / "usr/bin/mangohud").stat().st_mode & 0o7777 == 0o755
    assert (lar.destino / "usr/share/vulkan/implicit_layer.d/MangoHud.x86_64.json").exists()
    assert (lar.destino / "usr/share/metainfo").is_dir()
    pastas = {p.stat().st_mode & 0o777 for p in lar.destino.rglob("*") if p.is_dir()}
    assert pastas == {0o755}, pastas


@pytest.mark.parametrize(("distro", "lib"), [("pop", "lib32"), ("arch", "lib64")])
def test_os_links_que_o_setup_criava_o_ajudante_cria(lar: Lar, distro: str, lib: str) -> None:
    """D-1911-O-MANGOHUD-ENTRA-POR-LISTA-FECHADA: o pacote não traz links; o carregador acha a
    biblioteca pelos links que o ajudante cria, os mesmos do setup, sem trocar o que já existe."""
    (lar.destino / "etc").mkdir()
    (lar.destino / "etc/os-release").write_text(f"ID={distro}\n", encoding="utf-8")
    (lar.destino / "usr/lib/mangohud").mkdir(parents=True)
    (lar.destino / "usr/lib/mangohud/i686").symlink_to("outra")
    rc, erro = _instalar(lar, PACOTE_DO_MANGOHUD)
    assert rc == 0, erro
    base = lar.destino / "usr/lib/mangohud"
    assert os.readlink(base / "lib") == lib
    assert os.readlink(base / "x86_64") == "lib64"
    assert os.readlink(base / "i686") == "outra"
    assert (base / lib / "x86_64-linux-gnu").resolve() == (base / "lib64").resolve()
    assert (base / "lib" / "x86_64-linux-gnu" / "libMangoHud_shim.so").read_bytes() == b"ELF64"
    assert (base / "tls" / "i686" / "libMangoHud.so").read_bytes() == b"ELF32"
    assert "ldconfig " in lar.lidas()
    assert (lar.cache / "mangohud" / "atual.nome").read_text().strip() == "MangoHud-0.8.5.r0.tar.gz"


@pytest.mark.parametrize(("ruim", "frase"), [
    (("usr/lib/libc.so.6", 0o644, b"x", ""), "entrada fora da lista"),
    (("usr/lib/mangohud/../../../etc/cron.d/x", 0o644, b"x", ""), "caminho fora da lista"),
    (("usr/lib/mangohud/lib64/fora", 0o777, b"", "../../../../etc/shadow"), "link para fora"),
    (("usr/lib/mangohud/lib64/abs", 0o777, b"", "/etc/passwd"), "link para fora"),
    (("usr/bin/mangohud", 0o4755, b"#!/bin/sh\n", ""), "bit especial"),
    (("usr/share/vulkan/implicit_layer.d/evil.json", 0o644, b"{}", ""), "entrada fora da lista"),
])
def test_entrada_fora_da_lista_recusa_o_pacote_inteiro(
        lar: Lar, ruim: tuple[str, int, bytes, str], frase: str) -> None:
    """D-1911-O-MANGOHUD-ENTRA-POR-LISTA-FECHADA: uma entrada ruim recusa o pacote inteiro."""
    rc, erro = _instalar(lar, (*PACOTE_DO_MANGOHUD, ruim))
    assert rc != 0
    assert frase in erro, erro
    assert _arvore(lar.destino) == []
    assert not (lar.cache / "mangohud" / "atual.tar.gz").exists()
    assert not any(linha.startswith(("setup", "ldconfig")) for linha in lar.lidas())

