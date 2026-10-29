"""A permissão ``jogos`` mostra à extensão as bibliotecas da Steam, só de leitura.

A-LOVENSE-MOSTRA-QUE-O-JOGO-APONTA-PARA-OUTRA-MAQUINA-01 (28/10/2026). A extensão roda na caixa do
``bwrap`` com a ``HOME`` vazia, e não enxergava o ``steamapps`` da ``HOME`` nem a lista das
bibliotecas: a configuração que o jogo grava (o endereço do kit) ficava fora do alcance. Com a
permissão, cada ``steamapps`` aparece só de leitura e o ``HEFESTO_MOD_JOGOS`` as lista.

MORDIDA (28/10/2026, executada sobre a cura e devolvida): sem o ``--ro-bind`` das pastas em
``comando_na_caixa``, ``test_na_caixa_a_biblioteca_da_casa_aparece_so_de_leitura`` reprova.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from hefesto_dualsense4unix.mods.manifesto import Manifesto
from hefesto_dualsense4unix.mods.supervisor import comando_na_caixa, pastas_dos_jogos

APPID = "720050"


def _manifesto(*permissoes: str) -> Manifesto:
    corpo: dict[str, Any] = {
        "id": "exemplo", "nome": "Exemplo", "versao": "0.1.0", "api": ">=1,<3",  # (noqa-acento)
        "licenca": "MIT", "tipos": ["processo"], "processo": {"executar": ["python3", "m.py"]},
        "permissoes": list(permissoes),  # (noqa-acento)
    }
    return Manifesto.model_validate(corpo)


@pytest.fixture
def casa(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Uma casa com a Steam e uma segunda biblioteca fora dela, no ``libraryfolders.vdf``."""
    casa = tmp_path / "casa"
    principal = casa / ".local" / "share" / "Steam" / "steamapps"
    outra = tmp_path / "outra" / "steamapps"
    for apps in (principal, outra):
        (apps / "common").mkdir(parents=True)
    (principal / "libraryfolders.vdf").write_text(
        f'"libraryfolders"\n{{\n\t"1"\n\t{{\n\t\t"path"\t\t"{outra.parent}"\n\t}}\n}}\n',
        encoding="utf-8")
    (principal / f"appmanifest_{APPID}.acf").write_text('"installdir"\t"Jogo"', encoding="utf-8")
    return casa, principal.resolve(), outra.resolve()


def test_so_com_a_permissao_as_pastas_dos_jogos_saem(casa: tuple[Path, Path, Path]) -> None:
    lar, principal, outra = casa
    assert pastas_dos_jogos(_manifesto("jogos"), lar) == (principal, outra)
    assert pastas_dos_jogos(_manifesto("ler:estado"), lar) == ()
    assert "jogos" in _manifesto("jogos").permissoes


def _caixa(tmp_path: Path, lar: Path, manifesto: Manifesto, jogos: tuple[Path, ...],
           comando: list[str]) -> list[str]:
    fonte, dados = tmp_path / "fonte", tmp_path / "dados"
    for pasta in (fonte, dados):
        pasta.mkdir(exist_ok=True)
    porta = tmp_path / "porta.sock"
    porta.touch()
    bwrap = shutil.which("bwrap") or "bwrap"
    return comando_na_caixa(bwrap=bwrap, comando=comando, codigo=fonte, dados=dados, porta=porta,
                            manifesto=manifesto, casa=lar, execucao=(), jogos=jogos)


def test_na_caixa_a_biblioteca_da_casa_aparece_so_de_leitura(
        tmp_path: Path, casa: tuple[Path, Path, Path]) -> None:
    lar, principal, outra = casa
    manifesto = _manifesto("jogos")
    jogos = pastas_dos_jogos(manifesto, lar)
    sem = _caixa(tmp_path, lar, _manifesto("ler:estado"), jogos, ["true"])
    assert str(principal) not in sem, "sem a permissão, nenhuma pasta"
    if shutil.which("bwrap") is None:
        pytest.skip("sem bwrap nesta máquina")
    ler = f"cat {principal}/appmanifest_{APPID}.acf && ls {outra} && touch {principal}/x"
    feito = subprocess.run(_caixa(tmp_path, lar, manifesto, jogos, ["sh", "-c", ler]),
                           capture_output=True, text=True, timeout=30, check=False)
    assert '"installdir"' in feito.stdout and "common" in feito.stdout, feito.stderr
    assert feito.returncode != 0 and not (principal / "x").exists(), "só de leitura"
    vazia = subprocess.run(_caixa(tmp_path, lar, _manifesto("ler:estado"), jogos,
                                  ["sh", "-c", f"ls {principal}"]),
                           capture_output=True, text=True, timeout=30, check=False)
    if principal.is_relative_to(lar.resolve()):
        assert vazia.returncode != 0, "sem a permissão, a HOME segue vazia"
