"""O install troca o `gameinput.dll` de `nativa/` pelo do pino, num HOME de mentira.

Roda a função `_peca_gdk_instalar` do `install.sh` de verdade, recortada do arquivo, com dublês
no PATH (`curl` que falha ou entrega outra DLL, o compilador do pino presente ou ausente) e um
`construir.sh` de mentira. Com o compilador no PATH, a DLL compilada que bate com o pino troca a
de antes; o arquivo novo entra noutro inode, e quem já tinha a de antes aberta (o jogo rodando)
segue lendo a de antes até reabrir. Sem o compilador e sem a release, a de antes fica no lugar.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

_INSTALL = Path(__file__).resolve().parents[2] / "install.sh"
_NOVA = b"MZ o gameinput de mentira do pino"
_ANTES = b"MZ o gameinput de mentira de antes"
_DA_RELEASE_VELHA = b"MZ o gameinput de mentira de uma release velha"
_FERRAMENTAS = ("bash", "sed", "head", "cut", "sha256sum", "mktemp", "install", "rm", "mkdir",
                "cp", "touch")


def _recorte() -> str:
    texto = _INSTALL.read_text(encoding="utf-8")
    inicio = texto.index("_peca_gdk_pino() {")
    fim = texto.index("\n}\n", texto.index("_peca_gdk_instalar() {")) + 3
    return texto[inicio:fim]


def _sha(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def _executavel(caminho: Path, corpo: str) -> None:
    caminho.write_text("#!/usr/bin/env bash\n" + corpo, encoding="utf-8")
    caminho.chmod(0o755)


class _Lar:
    def __init__(self, base: Path) -> None:
        self.casa = base / "casa"
        assert not str(self.casa).startswith("/home/"), "o lar de mentira caiu numa casa de verdade"
        self.raiz = base / "raiz"
        self.duble = base / "duble"
        self.tmp = base / "tmp"
        self.marca = base / "compilou"
        self.ferramentas = base / "ferramentas"
        for pasta in (
            self.casa, self.raiz / "assets" / "gdk-runtime", self.duble, self.tmp, self.ferramentas
        ):
            pasta.mkdir(parents=True)
        for nome in _FERRAMENTAS:
            achada = shutil.which(nome)
            assert achada, f"falta {nome} na máquina"
            (self.ferramentas / nome).symlink_to(achada)
        (self.raiz / "pyproject.toml").write_text('version = "9.9.9"\n', encoding="utf-8")
        (self.raiz / "assets" / "gdk-runtime" / "pino.txt").write_text(
            f"gameinput_url=https://exemplo.invalid/gameinput.dll\n"
            f"gameinput_sha256={_sha(_NOVA)}\n",
            encoding="utf-8",
        )
        nova = base / "nova.dll"
        nova.write_bytes(_NOVA)
        _executavel(
            self.raiz / "assets" / "gdk-runtime" / "construir.sh",
            f'mkdir -p "$1"; cp "{nova}" "$1/gameinput.dll"; touch "{self.marca}"\n',
        )
        self.alvo = (
            self.casa / ".local" / "share" / "hefesto-dualsense4unix" / "wine" / "nativa"
            / "gameinput.dll"
        )
        self.alvo.parent.mkdir(parents=True)
        self.alvo.write_bytes(_ANTES)

    def curl(self, entrega: bytes | None) -> None:
        if entrega is None:
            _executavel(self.duble / "curl", "exit 22\n")
            return
        velha = self.duble / "da-release.dll"
        velha.write_bytes(entrega)
        _executavel(
            self.duble / "curl",
            f'while [ $# -gt 0 ]; do [ "$1" = -o ] && cp "{velha}" "$2"; shift; done\n',
        )

    def compilador(self) -> None:
        _executavel(self.duble / "x86_64-w64-mingw32-gcc-posix", "exit 0\n")

    def instalar(self) -> subprocess.CompletedProcess[str]:
        roteiro = (
            "set -u\n"
            f'ROOT_DIR="{self.raiz}"\n'
            'PECA_GDK_PINO="${ROOT_DIR}/assets/gdk-runtime/pino.txt"\n'
            'warn() { printf "AVISO %s\\n" "$*"; }\n'
            'ok() { printf "OK\\n"; }\n'
            + _recorte()
            + '_peca_gdk_instalar "o GameInput do Hefesto" gameinput_sha256 gameinput_url '
            'gameinput.dll '
            '"${HOME}/.local/share/hefesto-dualsense4unix/wine/nativa/gameinput.dll"\n'
        )
        env = {
            "HOME": str(self.casa),
            "PATH": f"{self.duble}:{self.ferramentas}",
            "TMPDIR": str(self.tmp),
            "LC_ALL": "C.UTF-8",
        }
        return subprocess.run(
            [str(self.ferramentas / "bash"), "-c", roteiro],
            env=env, capture_output=True, text=True, timeout=60, check=False,
        )


@pytest.fixture
def lar(tmp_path: Path) -> _Lar:
    return _Lar(tmp_path)


def test_com_o_compilador_a_dll_nova_troca_a_de_antes(lar: _Lar) -> None:
    lar.curl(None)
    lar.compilador()
    inode_antes = lar.alvo.stat().st_ino
    with lar.alvo.open("rb") as aberta:
        feito = lar.instalar()
        assert feito.returncode == 0, feito.stderr
        assert lar.alvo.read_bytes() == _NOVA, (
            "com o compilador no PATH a DLL nova não chega ao alvo: " + feito.stdout
        )
        assert aberta.read() == _ANTES, "o jogo aberto perdeu a DLL que já tinha carregado"
    assert lar.alvo.stat().st_ino != inode_antes
    assert "OK" in feito.stdout and not list(lar.tmp.iterdir())


def test_a_release_velha_nao_vence_a_compilacao(lar: _Lar) -> None:
    lar.curl(_DA_RELEASE_VELHA)
    lar.compilador()
    feito = lar.instalar()
    assert lar.alvo.read_bytes() == _NOVA, "a DLL da release que não bate com o pino entrou"
    assert feito.returncode == 0


def test_sem_compilador_e_sem_release_a_de_antes_fica(lar: _Lar) -> None:
    lar.curl(None)
    feito = lar.instalar()
    assert lar.alvo.read_bytes() == _ANTES
    assert not lar.marca.exists()
    assert "AVISO o GameInput do Hefesto ficou de fora" in feito.stdout


def test_a_dll_que_ja_bate_com_o_pino_nao_se_refaz(lar: _Lar) -> None:
    lar.alvo.write_bytes(_NOVA)
    lar.curl(None)
    lar.compilador()
    feito = lar.instalar()
    assert "já no lugar, e bate com o pino" in feito.stdout
    assert not lar.marca.exists()
    assert os.environ.get("HOME") != str(lar.casa)
