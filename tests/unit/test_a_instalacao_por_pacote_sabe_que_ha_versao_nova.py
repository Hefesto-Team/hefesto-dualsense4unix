"""A-INSTALACAO-POR-PACOTE-SABE-QUE-HA-VERSAO-NOVA-01 (20/11/2026): quem instalou o Hefesto por
pacote é avisado da versão nova, com o gesto da forma de instalação na dica.

TUDO É DE MENTIRA: o lar é ``tmp_path`` com ``XDG_*`` desviados, a rede é um dublê de ``_ler`` e a
raiz do código é uma pasta sem ``.git``. Teste que vai à rede reprova pela ``trava_da_rede``.

AS MORDIDAS (feitas com a cura devolvida): ``publicada=None`` sem consultar reprova o caso da
release maior; o gesto fora do item reprova o caso da dica; a peça nova sem ``gesto`` na marca
reprova o caso da caixa de marcar; o Sistema sem apt que some do mapa reprova o caso da linha da
distribuição; o kernel que fica sem o ajudante reprova o caso do ajudante ausente.
"""
from __future__ import annotations

import importlib.metadata as metadata
import json
import shutil
import socket
import sys
import urllib.error
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import atualizador as at
from hefesto_dualsense4unix.app.actions import pecas_do_atualizador as pa
from hefesto_dualsense4unix.interface import atualizacoes as tela
from hefesto_dualsense4unix.utils import repo_files


@pytest.fixture(autouse=True)
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    casa = tmp_path / "casa"
    for var, sub in (("XDG_CONFIG_HOME", ".config"), ("XDG_STATE_HOME", ".local/state"),
                     ("XDG_CACHE_HOME", ".cache"), ("XDG_DATA_HOME", ".local/share"),
                     ("XDG_RUNTIME_DIR", "run")):
        (casa / sub).mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(var, str(casa / sub))
    monkeypatch.setenv("HOME", str(casa))
    for var in ("FLATPAK_ID", "APPIMAGE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(repo_files, "MARCA_DO_FLATPAK", tmp_path / "sem-flatpak-info")
    monkeypatch.setattr(repo_files, "PREFIXO_DO_DEB", tmp_path / "sem-opt")
    return casa


@pytest.fixture(autouse=True)
def trava_da_rede(monkeypatch: pytest.MonkeyPatch) -> None:
    def _recusar(*_a: object, **_k: object) -> None:
        raise OSError("o teste da instalação por pacote foi à rede")

    monkeypatch.setattr(socket.socket, "connect", _recusar)
    monkeypatch.setattr(socket, "getaddrinfo", _recusar)


@pytest.fixture
def raiz_sem_clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raiz = tmp_path / "pacote"
    raiz.mkdir()
    (raiz / "pyproject.toml").write_text('version = "0.9.5.4"\n', encoding="utf-8")
    monkeypatch.setattr(pa, "RAIZ_DO_REPOSITORIO", raiz)
    monkeypatch.setattr(metadata, "version", lambda _n: "0.9.5.4")
    return raiz


def _rede_com_release(monkeypatch: pytest.MonkeyPatch, tag: str) -> list[str]:
    pedidos: list[str] = []

    def ler(url: str) -> bytes:
        pedidos.append(url)
        return json.dumps({"tag_name": tag, "published_at": "2026-11-18T09:00:00Z"}).encode()

    monkeypatch.setattr(pa, "_ler", ler)
    return pedidos


def _peca(ident: str) -> at.Peca:
    return next(p for p in pa.registro() if p.id == ident)


def _item(conferencia: dict[str, Any], ident: str) -> dict[str, Any]:
    return next(i for i in conferencia["pecas"] if i["id"] == ident)


@pytest.mark.parametrize("marca, esperado", [
    ("appimage", "Baixe o AppImage novo na página da versão"),
    ("flatpak", "Baixe o .flatpak novo na página da versão"),
    ("deb", "Abra o .deb novo no instalador do sistema"),
    ("outra", repo_files.GESTO_DE_SUBIR["outra"]),
])
def test_sem_clone_a_release_maior_vira_nova_versao_com_o_gesto_da_forma(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, raiz_sem_clone: Path, marca: str,
        esperado: str) -> None:
    """D-2011-A-INSTALACAO-POR-PACOTE-AVISA-A-VERSAO-NOVA: a release maior vira «Nova versão»."""
    if marca == "appimage":
        monkeypatch.setenv("APPIMAGE", "/tmp/Hefesto.AppImage")
    elif marca == "flatpak":
        monkeypatch.setenv("FLATPAK_ID", "io.github.hefesto_team.hefesto_dualsense4unix")
    elif marca == "deb":
        monkeypatch.setattr(repo_files, "PREFIXO_DO_DEB", Path(sys.prefix))
    pedidos = _rede_com_release(monkeypatch, "v99.0.0")
    conferencia = at.conferir(rede=True, lista=[_peca("hefesto")])
    assert pedidos == [pa.API_DO_GITHUB.format(pa.REPO_DO_PRODUTO)]
    item = _item(conferencia, "hefesto")
    assert (item["estado"], item["de"], item["para"], item["gesto"]) == \
        (at.NOVA, "0.9.5.4", "99.0.0", esperado)
    assert at.novas(conferencia, so_marcadas=False) == []
    mapa = tela.html_do_mapa({"pecas": [{**item, "marcada": True}]})
    assert tela.NOVA_VERSAO in mapa and esperado in mapa
    assert 'type="checkbox"' not in mapa and tela.SEM_REDE not in mapa
    assert tela.ids_para_atualizar({"pecas": [{**item, "marcada": True}]}) == []


def test_sem_clone_a_release_igual_diz_atualizado_e_sem_rede_so_quando_a_consulta_falha(
        monkeypatch: pytest.MonkeyPatch, raiz_sem_clone: Path) -> None:
    _rede_com_release(monkeypatch, "v0.9.5.4")
    em_dia = _item(at.conferir(rede=True, lista=[_peca("hefesto")]), "hefesto")
    assert (em_dia["estado"], em_dia["gesto"]) == (at.EM_DIA, "")

    def sem_rede(_url: str) -> bytes:
        raise urllib.error.URLError("sem rota")

    monkeypatch.setattr(pa, "_ler", sem_rede)
    caiu = at.conferir(rede=True, lista=[_peca("hefesto")])
    assert _item(caiu, "hefesto")["estado"] == at.NAO_CONSULTADO
    assert tela.SEM_REDE in tela.html_do_mapa(caiu)


def test_o_clone_segue_pelo_git_e_nao_pergunta_a_release(
        monkeypatch: pytest.MonkeyPatch, raiz_sem_clone: Path) -> None:
    (raiz_sem_clone / ".git").mkdir()
    monkeypatch.setattr(pa, "_ler", lambda _u: pytest.fail("o clone consultou a release"))
    vao = pa._vao()
    monkeypatch.setattr(vao, "_git", lambda _r, *_a, **_k: None)
    versoes = pa.versoes_do_hefesto(True)
    assert (versoes.publicada, versoes.gesto) == (None, "")
    assert repo_files.forma_da_instalacao(raiz_sem_clone) == repo_files.FORMA_CLONE
    assert repo_files.gesto_de_subir_a_versao_nova(repo_files.FORMA_CLONE) == ""


def test_sem_apt_o_sistema_vira_a_linha_da_distribuicao_e_kernel_e_nvidia_somem(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda nome: None if nome.startswith("apt") else nome)
    monkeypatch.setattr(pa, "_saida", lambda _argv: None)
    monkeypatch.setattr(pa, "_ids_da_distro", lambda: ["nobara", "fedora"])
    monkeypatch.setattr(pa, "_nome_da_distro", lambda: "Fedora Linux 43")
    monkeypatch.setattr(pa, "_versao_da_distro", lambda: "43")
    monkeypatch.setattr(pa, "AJUDANTE", Path("/nao/existe"))
    assert pa.versoes_do_kernel(True).existe is False
    assert pa.versoes_da_nvidia(True).existe is False
    conferencia = at.conferir(rede=True, lista=[_peca("sistema")])
    item = _item(conferencia, "sistema")
    assert (item["estado"], item["rotulo"], item["reinstala"]) == (at.EM_DIA, "Pela distribuição",
                                                                   False)
    mapa = tela.html_do_mapa({"pecas": [{**item, "marcada": True}]})
    gesto = "Atualize pelo gerenciador da distribuição: sudo dnf upgrade"
    assert "Pela distribuição" in mapa and gesto in mapa and "Fedora Linux 43" in mapa
    assert 'type="checkbox"' not in mapa and 'class="mp-l"' in mapa
    assert 'class="mp-s"></span>' in mapa
    assert tela.ids_para_atualizar({"pecas": [{**item, "marcada": True}]}) == []


def test_com_apt_mas_sem_o_ajudante_o_sistema_diz_apt_upgrade_e_o_kernel_some(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda nome: nome)
    monkeypatch.setattr(pa, "_saida", lambda _argv: None)
    monkeypatch.setattr(pa, "_ids_da_distro", lambda: ["ubuntu", "debian"])
    monkeypatch.setattr(pa, "AJUDANTE", Path("/nao/existe"))
    assert pa.versoes_do_kernel(True).existe is False
    assert pa.versoes_da_nvidia(True).existe is False
    assert pa.versoes_do_sistema(True).gesto.endswith("sudo apt upgrade")


def test_distribuicao_sem_comando_conhecido_diz_so_o_gerenciador(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pa, "_ids_da_distro", lambda: ["voidlinux"])
    assert pa._gesto_do_sistema() == "Atualize pelo gerenciador da distribuição"
