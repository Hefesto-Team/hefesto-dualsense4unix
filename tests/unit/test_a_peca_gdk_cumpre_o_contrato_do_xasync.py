"""A peça GDK do Hefesto cumpre o contrato do XAsync, e todo jogo GDK a recebe pelo sinal.

O contrato em si (fila nula, sem fila do processo, Duplicate/Close, composto de composto,
Terminate que espera, a peça certa carregada) se prova no Wine pelo ensaio
`scripts/ensaios/o_contrato_da_peca_gdk.py`, que precisa do mingw e de um Proton. Aqui fica o que a
suíte alcança sem eles: o pino, a marca builtin, o juiz do ensaio, as mordidas que medem um trecho
que existe no fonte, e as três pontas (install, wrapper, tabela) concordando na mesma pasta.
"""
from __future__ import annotations

import importlib.util
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from hefesto_dualsense4unix.integrations import receitas_de_ambiente as rda

_RAIZ = Path(__file__).resolve().parents[2]
_FONTE = _RAIZ / "assets" / "gdk-runtime"
_PINO = _FONTE / "pino.txt"
_CONSTRUIR = _FONTE / "construir.sh"
_ENSAIO = _RAIZ / "scripts" / "ensaios" / "o_contrato_da_peca_gdk.py"
_PASTA_RELATIVA = ".local/share/hefesto-dualsense4unix/wine"
_CC = "x86_64-w64-mingw32-gcc-posix"


def _pino() -> dict[str, str]:
    linhas = _PINO.read_text(encoding="utf-8").splitlines()
    return dict(ln.split("=", 1) for ln in linhas if "=" in ln and not ln.startswith("#"))


def _ensaio() -> ModuleType:
    spec = importlib.util.spec_from_file_location("o_contrato_da_peca_gdk", _ENSAIO)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


# --- o pino --------------------------------------------------------------------------------


def test_o_pino_grava_o_sha256_da_peca_e_da_sonda_e_o_endereco_versionado() -> None:
    pino = _pino()
    for chave in ("sha256", "sonda_sha256"):
        assert re.fullmatch(r"[0-9a-f]{64}", pino[chave]), chave
    for chave in ("url", "sonda_url"):
        assert pino[chave].startswith("https://github.com/Hefesto-Team/"), chave
        assert "/releases/download/v{versao}/" in pino[chave], chave
    assert "construir.sh" in pino["compilar"] and "--conferir" in pino["compilar"]
    assert rda._sha256_do_pino() == pino["sha256"], "a tabela lê outro sha256 que o do pino"


def test_o_pino_sem_sha256_valido_nao_aceita_peca_nenhuma(tmp_path: Path) -> None:
    pino = tmp_path / "pino.txt"
    pino.write_text("sha256=nao-e-hex\n", encoding="utf-8")
    dll = rda.pasta_da_peca(tmp_path) / "x86_64-windows" / "xgameruntime.dll"
    dll.parent.mkdir(parents=True)
    dll.write_bytes(b"MZ")
    assert not rda.peca_do_hefesto_instalada(tmp_path, pino)
    assert not rda.peca_do_hefesto_instalada(tmp_path, tmp_path / "nao-existe.txt")


# --- a marca builtin -----------------------------------------------------------------------


def _pe_de_mentira(caminho: Path, lfanew: int) -> bytes:
    corpo = bytearray(b"MZ" + b"\0" * 254)
    corpo[60:64] = struct.pack("<I", lfanew)
    caminho.write_bytes(bytes(corpo))
    return bytes(corpo)


def _marcar(dll: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(_CONSTRUIR), "--marcar", str(dll)],
        capture_output=True, text=True, timeout=20, check=False,
    )


def test_a_marca_builtin_do_wine_vai_no_0x40(tmp_path: Path) -> None:
    dll = tmp_path / "x.dll"
    antes = _pe_de_mentira(dll, 128)
    assert _marcar(dll).returncode == 0
    depois = dll.read_bytes()
    assert depois[0x40:0x51] == b"Wine builtin DLL\0"
    assert depois[:0x40] == antes[:0x40] and depois[0x51:] == antes[0x51:]


def test_a_marca_recusa_o_pe_cujo_cabecalho_ela_cobriria(tmp_path: Path) -> None:
    dll = tmp_path / "x.dll"
    antes = _pe_de_mentira(dll, 64)
    feito = _marcar(dll)
    assert feito.returncode != 0 and "cobriria" in feito.stderr
    assert dll.read_bytes() == antes, "a recusa escreveu no arquivo"


def test_a_marca_recusa_o_que_nao_e_pe(tmp_path: Path) -> None:
    dll = tmp_path / "x.dll"
    dll.write_bytes(b"\x7fELF" + b"\0" * 200)
    assert _marcar(dll).returncode != 0


# --- o juiz do ensaio ----------------------------------------------------------------------


def test_o_juiz_passa_so_a_prova_que_apareceu_com_ok() -> None:
    ensaio = _ensaio()
    linhas = [
        "lixo do wine que não é JSON",
        '{"prova": "fila_nula", "ok": true}',
        '{"prova": "sem_fila_do_processo", "ok": false}',
        '{"prova": "duplicate_close", "ok": "true"}',
        "{quebrado",
        '{"fim": true}',
    ]
    veredito = ensaio.julgar(linhas)
    assert set(veredito) == set(ensaio.PROVAS)
    assert veredito["fila_nula"] is True
    assert veredito["sem_fila_do_processo"] is False
    assert veredito["duplicate_close"] is False, "só o booleano true conta"
    assert veredito["terminate_espera"] is False, "a prova que não apareceu reprova"


def test_toda_mordida_do_fonte_acha_o_trecho_da_cura_uma_vez() -> None:
    """Mordida cujo trecho sumiu do fonte não quebra nada e passaria calada."""
    ensaio = _ensaio()
    for nome, (arquivo, cura, quebrado, prova) in ensaio.MORDIDAS.items():
        assert prova in ensaio.PROVAS, nome
        if not arquivo:
            continue
        texto = (_FONTE / arquivo).read_text(encoding="utf-8")
        assert texto.count(cura) == 1, f"mordida {nome}: o trecho da cura não está uma vez"
        assert ensaio.quebrar(texto, cura, quebrado) != texto
    with pytest.raises(SystemExit):
        ensaio.quebrar("abc", "x", "y")


def test_o_ensaio_recusa_prefixo_no_home(tmp_path: Path) -> None:
    ensaio = _ensaio()
    with pytest.raises(SystemExit):
        ensaio.prefixo_seguro(Path.home())
    with pytest.raises(SystemExit):
        ensaio.prefixo_seguro(Path.home() / ".wine")
    assert ensaio.prefixo_seguro(Path("/tmp/vz-prefixo-de-teste")) == Path(
        "/tmp/vz-prefixo-de-teste"
    ).resolve()


# --- as três pontas na mesma pasta ---------------------------------------------------------


def test_install_wrapper_e_tabela_nomeiam_a_mesma_pasta_da_peca() -> None:
    install = (_RAIZ / "install.sh").read_text(encoding="utf-8")
    uninstall = (_RAIZ / "uninstall.sh").read_text(encoding="utf-8")
    wrapper = (_RAIZ / "assets" / "hefesto-launch.sh").read_text(encoding="utf-8")
    assert f"${{HOME}}/{_PASTA_RELATIVA}/x86_64-windows/xgameruntime.dll" in install
    assert f'PECA_GDK_PASTA="${{HOME}}/{_PASTA_RELATIVA}"' in uninstall
    assert f'pr_pasta="$HOME/{_PASTA_RELATIVA}"' in wrapper
    assert rda.pasta_da_peca(Path("/c")) == Path("/c") / _PASTA_RELATIVA


def test_o_install_so_aceita_a_peca_com_o_sha256_do_pino() -> None:
    # D-1710-A-PECA-GDK-DO-HEFESTO-VAI-PELO-PAR-B-E-WINEDLLPATH
    install = (_RAIZ / "install.sh").read_text(encoding="utf-8")
    bloco = install.split("# 4b-5. A peça GDK", 1)[1].split("# 4c.", 1)[0]
    assert bloco.count('== "${_peca_sha_pino}"') >= 3, "um caminho do install não confere o pino"
    assert "install -Dm644" in bloco and "sudo" not in bloco


def test_a_release_compila_confere_e_publica_a_peca() -> None:
    release = (_RAIZ / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    job = release.split("\n  peca-gdk:\n", 1)[1].split("\n  integridade:\n", 1)[0]
    assert "runs-on: ubuntu-24.04" in job, "o sha256 do pino só se repete com o compilador fixo"
    assert "construir.sh dist/peca-gdk --conferir" in job
    assert "'xgameruntime.dll' 'sonda-gdk.exe'" in release


# --- a compilação bate com o pino (só com o mingw à mão) -----------------------------------


@pytest.mark.skipif(shutil.which(_CC) is None, reason="sem o mingw-w64 no PATH")
def test_o_fonte_de_hoje_compila_no_binario_do_pino(tmp_path: Path) -> None:
    feito = subprocess.run(
        ["bash", str(_CONSTRUIR), str(tmp_path / "saida"), "--conferir"],
        capture_output=True, text=True, timeout=300, check=False,
    )
    assert feito.returncode == 0, feito.stderr
    dll = (tmp_path / "saida" / "xgameruntime.dll").read_bytes()
    assert dll[0x40:0x51] == b"Wine builtin DLL\0"
