"""O ``dev`` só avança para um commit assinado por uma chave da lista do ``HEAD`` de agora.

Repositório de mentira em ``tmp_path``, chaves ``ed25519`` geradas no teste e o ``git`` real com a
configuração global e a do sistema desligadas: a conferência é a do produto, sem dublê.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import troca_no_fim_do_jogo as troca
from hefesto_dualsense4unix.app.actions import versao_ao_abrir as va

RAIZ = Path(__file__).resolve().parents[2]
LISTA = "assets/assinaturas/quem-assina"
MOTIVO = "o commit novo não tem a assinatura da casa"


def _git(pasta: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(pasta), *args], capture_output=True, text=True, check=True,
    ).stdout.strip()


def _chave(pasta: Path, nome: str) -> Path:
    caminho = pasta / "chaves" / nome
    caminho.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", nome, "-f", str(caminho)],
                   check=True, capture_output=True)
    return caminho


def _linha_da_lista(chave: Path) -> str:
    tipo, corpo = chave.with_suffix(".pub").read_text(encoding="utf-8").split()[:2]
    return f'{chave.name} namespaces="git" {tipo} {corpo}\n'


class Casa:
    """O remoto do produto, o clone de quem usa e o clone de quem publica, com a lista no início."""

    def __init__(self, base: Path, chave: Path) -> None:
        self.base = base
        self.chave = chave
        self.remoto = base / "Hefesto-Team" / "hefesto-dualsense4unix.git"
        self.remoto.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "--bare", "-b", "dev", str(self.remoto)], check=True)
        self.autor = base / "autor"
        subprocess.run(["git", "clone", "-q", str(self.remoto), str(self.autor)], check=True,
                       capture_output=True)
        _git(self.autor, "checkout", "-q", "-B", "dev")
        self.escrever(LISTA, _linha_da_lista(chave))
        self.inicio = self.commitar(chave)
        _git(self.autor, "push", "-q", "origin", "dev")
        self.clone = base / "clone"
        subprocess.run(["git", "clone", "-q", "-b", "dev", str(self.remoto), str(self.clone)],
                       check=True, capture_output=True)

    def escrever(self, caminho: str, texto: str) -> None:
        arquivo = self.autor / caminho
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(texto, encoding="utf-8")
        _git(self.autor, "add", caminho)

    def commitar(self, chave: Path | None) -> str:
        assina = ["-c", "commit.gpgsign=true", "-c", "gpg.format=ssh",
                  "-c", f"user.signingkey={chave}"] if chave else ["-c", "commit.gpgsign=false"]
        _git(self.autor, *assina, "commit", "-q", "-m", "muda")
        return _git(self.autor, "rev-parse", "HEAD")

    def publicar(self, chave: Path | None, caminho: str = "src/um.py", texto: str = "x\n") -> str:
        self.escrever(caminho, texto)
        alvo = self.commitar(chave)
        _git(self.autor, "push", "-q", "origin", "dev")
        return alvo

    def topo(self) -> str:
        return _git(self.clone, "rev-parse", "HEAD")


@pytest.fixture
def base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("SSH_AUTH_SOCK", raising=False)
    for papel in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{papel}_NAME", "t")
        monkeypatch.setenv(f"GIT_{papel}_EMAIL", "t@t.t")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "estado"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    (tmp_path / "run").mkdir()
    (tmp_path / "estado").mkdir()
    from hefesto_dualsense4unix.utils import xdg_paths

    monkeypatch.setattr(xdg_paths, "state_dir", lambda ensure=False: tmp_path / "estado")
    monkeypatch.setattr(troca, "_jogo_aberto", lambda: False)
    return tmp_path


@pytest.fixture
def casa(base: Path) -> Casa:
    return Casa(base, _chave(base, "da-casa"))


class Pedidos:
    def __init__(self) -> None:
        self.feitos: list[str] = []

    def disparar(self, _itens: Any) -> None:
        self.feitos.append("serviço")

    def instalar(self, _raiz: Path) -> None:
        self.feitos.append("install")


def _avancar(casa: Casa, alvo: str, pedidos: Pedidos) -> bool:
    _git(casa.clone, "fetch", "-q", "origin", "dev")
    return va.aplicar(casa.clone, alvo, jogo_aberto=lambda: False,
                      disparar=pedidos.disparar, instalar=pedidos.instalar)


def test_o_commit_assinado_pela_lista_do_head_avanca(casa: Casa) -> None:
    alvo = casa.publicar(casa.chave, "install.sh")
    pedidos = Pedidos()

    assert va.baixar(casa.clone, jogo_aberto=lambda: False) == alvo
    assert va.aplicar(casa.clone, alvo, jogo_aberto=lambda: False,
                      disparar=pedidos.disparar, instalar=pedidos.instalar)
    assert casa.topo() == alvo
    assert pedidos.feitos == ["install"]
    assert va.pendencia_do_install() is None


@pytest.mark.parametrize("quem", ["sem assinatura", "chave fora da lista"])
def test_o_commit_sem_a_assinatura_da_casa_fica_de_fora(
        casa: Casa, base: Path, quem: str, capsys: pytest.CaptureFixture[str]) -> None:
    chave = None if quem == "sem assinatura" else _chave(base, "de-fora")
    alvo = casa.publicar(chave, "install.sh")
    antes = casa.topo()
    pedidos = Pedidos()

    assert va.baixar(casa.clone, jogo_aberto=lambda: False) is None
    assert not _avancar(casa, alvo, pedidos)
    assert casa.topo() == antes
    assert pedidos.feitos == []
    assert capsys.readouterr().out.count(f"fica como está ({MOTIVO})") == 2
    pendencia = va.pendencia_do_install()
    assert pendencia is not None and MOTIVO in pendencia[1]


def test_a_lista_nova_que_so_existe_na_faixa_nao_vale(casa: Casa, base: Path) -> None:
    de_fora = _chave(base, "de-fora")
    casa.escrever(LISTA, _linha_da_lista(casa.chave) + _linha_da_lista(de_fora))
    casa.commitar(de_fora)
    alvo = casa.publicar(de_fora)
    antes = casa.topo()
    pedidos = Pedidos()

    assert not _avancar(casa, alvo, pedidos)
    assert casa.topo() == antes
    assert pedidos.feitos == []


def test_a_chave_nova_entra_pelo_commit_que_a_casa_assinou(casa: Casa, base: Path) -> None:
    nova = _chave(base, "nova")
    casa.escrever(LISTA, _linha_da_lista(casa.chave) + _linha_da_lista(nova))
    entrada = casa.commitar(casa.chave)
    _git(casa.autor, "push", "-q", "origin", "dev")
    pedidos = Pedidos()
    assert _avancar(casa, entrada, pedidos)

    alvo = casa.publicar(nova)
    assert _avancar(casa, alvo, pedidos)
    assert casa.topo() == alvo


def test_a_recusa_sai_da_aba_sistema_quando_o_assinado_entra(casa: Casa) -> None:
    pedidos = Pedidos()
    assert not _avancar(casa, casa.publicar(None), pedidos)
    assert va.pendencia_do_install() is not None

    alvo = casa.publicar(casa.chave, "README.md")
    assert _avancar(casa, alvo, pedidos)
    assert va.pendencia_do_install() is None


def test_sem_a_lista_no_head_nada_avanca(casa: Casa) -> None:
    casa.escrever("README.md", "x\n")
    _git(casa.autor, "rm", "-q", LISTA)
    sem_lista = casa.commitar(casa.chave)
    _git(casa.autor, "push", "-q", "origin", "dev")
    pedidos = Pedidos()
    assert _avancar(casa, sem_lista, pedidos)

    alvo = casa.publicar(casa.chave)
    assert not _avancar(casa, alvo, pedidos)
    assert casa.topo() == sem_lista


GPG_QUE_CONFIA_EM_TUDO = """#!/bin/sh
case " $* " in
  *" -bsau "*) cat >/dev/null
    printf '\\n[GNUPG:] SIG_CREATED D 22 8 00 1 X\\n' >&2
    printf -- '-----BEGIN PGP SIGNATURE-----\\n\\nAAAA\\n-----END PGP SIGNATURE-----\\n' ;;
  *) cat >/dev/null
    printf '[GNUPG:] NEWSIG\\n[GNUPG:] GOODSIG 0123456789ABCDEF quem\\n'
    printf '[GNUPG:] VALIDSIG X\\n[GNUPG:] TRUST_ULTIMATE\\n' ;;
esac
"""


def test_a_assinatura_que_nao_e_ssh_fica_de_fora(casa: Casa, base: Path) -> None:
    gpg = base / "gpg-que-confia-em-tudo"
    gpg.write_text(GPG_QUE_CONFIA_EM_TUDO, encoding="utf-8")
    gpg.chmod(0o755)
    for pasta in (casa.autor, casa.clone):
        _git(pasta, "config", "gpg.program", str(gpg))
    casa.escrever("src/um.py", "x\n")
    _git(casa.autor, "-c", "gpg.format=openpgp", "-c", "user.signingkey=X",
         "commit", "-q", "-S", "-m", "muda")
    alvo = _git(casa.autor, "rev-parse", "HEAD")
    _git(casa.autor, "push", "-q", "origin", "dev")
    _git(casa.clone, "fetch", "-q", "origin", "dev")
    assert subprocess.run(["git", "-C", str(casa.clone), "-c", "gpg.minTrustLevel=fully",
                           "verify-commit", alvo], capture_output=True).returncode == 0
    antes = casa.topo()

    assert not _avancar(casa, alvo, Pedidos())
    assert casa.topo() == antes


def test_a_lista_da_casa_tem_o_formato_do_git() -> None:
    linhas = (RAIZ / LISTA).read_text(encoding="utf-8").splitlines()
    assert linhas
    for linha in linhas:
        assert re.fullmatch(r'\S+ namespaces="git" ssh-ed25519 [A-Za-z0-9+/]+=*', linha), linha
