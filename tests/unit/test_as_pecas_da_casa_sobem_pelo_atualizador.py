"""O Bluetooth, o Som, o Portal do COSMIC e o GameInput sobem pelo atualizador.

O-HEFESTO-SE-ATUALIZA-INTEIRO-01, volta 2 (09/11/2026). Cada peça da casa deixa de ser «fixa»: a
versão nova publicada se reconstrói pela receita, com a série da casa triada (o patch que aplica
sem fuzz fica, o que o upstream já traz sai, o resto para tudo com «a casa precisa revisar os
patches»), e o ajudante root a constrói numa caixa e instala de uma pasta só do root, por verbos
fechados. O GameInput é de quem usa e sobe sem root, pelo sha256 do pino. TUDO É DE MENTIRA: a
rede é uma pasta, o ``apt-get`` e o ``dpkg`` são dublês, e o ajudante roda sem root.

AS MORDIDAS (feitas na sprint, com a cura devolvida): a triagem que mantém o patch que não aplica
reprova o caso da série; a assinatura do BlueZ não conferida reprova os casos da assinatura
adulterada, da chave de fora e da digital não fixada; o PipeWire que compila sem a soma revisada
reprova o caso da versão nova sem soma; o ajudante que
segue o atalho da entrega reprova o caso do atalho; o instalar sem filtrar o sufixo da casa reprova
o caso do pacote de fora; a série nova sem «revisar» reprova o caso do BlueZ 6; a GDK instalada
sem conferir o sha256 reprova o caso do download trocado.

AS ASSINATURAS DE TESTE (``tests/fixtures/receita-assinada``): os ``.tar`` têm a raiz
``bluez-5.89``, e os ``.sign`` saíram de duas chaves ed25519 de uso único («casa» e «estranha»),
geradas num GNUPGHOME descartável e apagadas depois; só a pública da «casa» ficou.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import lzma
import os
import pwd
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.parse
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import atualizador as at
from hefesto_dualsense4unix.app.actions import pecas_do_atualizador as pa

RAIZ = Path(__file__).resolve().parents[2]
RECEITA = RAIZ / "scripts" / "hefesto_receita_nova.py"
AJUDANTE = RAIZ / "scripts" / "hefesto_atualizador_raiz.sh"
ASSETS_BZ = RAIZ / "assets" / "bluez-backport"
DEVICE_C = RAIZ / "tests" / "fixtures" / "bluez-5.87" / "device.c"
INDICE = "https://www.kernel.org/pub/linux/bluetooth/"
ASSINADA = RAIZ / "tests" / "fixtures" / "receita-assinada"
DIGITAL_DE_TESTE = "3F76C5C83C4E42B67F80D68F5F2075CD29306BA5"
DIGITAL_DO_BLUEZ = "E932D120BC2AEC444E558F0106CA9F5D1DCF2659"
COM_GPGV = pytest.mark.skipif(shutil.which("gpgv") is None, reason="sem o gpgv")


@pytest.fixture(autouse=True)
def casa_de_mentira(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    casa = tmp_path / "casa-xdg"
    for var, sub in (("XDG_CONFIG_HOME", ".config"), ("XDG_STATE_HOME", ".local/state"),
                     ("XDG_CACHE_HOME", ".cache"), ("XDG_DATA_HOME", ".local/share"),
                     ("XDG_RUNTIME_DIR", "run")):
        (casa / sub).mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(var, str(casa / sub))
    monkeypatch.setenv("HOME", str(casa))
    return casa


def _receita() -> Any:
    spec = importlib.util.spec_from_file_location("hefesto_receita_nova", RECEITA)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["hefesto_receita_nova"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _sha(dado: bytes) -> str:
    return hashlib.sha256(dado).hexdigest()


def _tar_xz(raiz: str, arquivos: dict[str, bytes]) -> bytes:
    saida = io.BytesIO()
    with tarfile.open(fileobj=saida, mode="w:xz") as tar:
        for nome, dado in arquivos.items():
            info = tarfile.TarInfo(f"{raiz}/{nome}")
            info.size = len(dado)
            tar.addfile(info, io.BytesIO(dado))
    return saida.getvalue()


class Rede:
    def __init__(self, pasta: Path) -> None:
        self.pasta = pasta
        pasta.mkdir(parents=True, exist_ok=True)

    def por(self, url: str, dado: bytes | str) -> None:
        (self.pasta / urllib.parse.quote(url, safe="")).write_bytes(
            dado.encode() if isinstance(dado, str) else dado)


def _bluez_publicado(rede: Rede, publicada: str = "5.89", *, tar: str = "bluez-5.89.tar",
                     assinatura: str = "bluez-5.89.tar.sign", adulterar: bool = False) -> bytes:
    nome = f"bluez-{publicada}.tar.xz"
    cru = bytearray((ASSINADA / tar).read_bytes())
    if adulterar:
        cru[1024] ^= 0x20
    xz = lzma.compress(bytes(cru), format=lzma.FORMAT_XZ)
    rede.por(INDICE, f'<a href="bluez-5.88.tar.xz">x</a> <a href="{nome}">y</a>')
    rede.por(INDICE + nome, xz)
    rede.por(INDICE + f"bluez-{publicada}.tar.sign", (ASSINADA / assinatura).read_bytes())
    return xz


def _fixar_digitais(assets: Path, digitais: str) -> None:
    baseline = assets / "BASELINE"
    texto, trocas = re.subn(r"^CHAVES_DE_RELEASE=.*$", f"CHAVES_DE_RELEASE={digitais}",
                            baseline.read_text(), flags=re.MULTILINE)
    assert trocas == 1
    baseline.write_text(texto)


@pytest.fixture
def receita_bz(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Path, Rede]:
    rn = _receita()
    receita = tmp_path / "receita"
    assets = receita / "assets" / "bluez-backport"
    shutil.copytree(ASSETS_BZ, assets)
    shutil.copy2(ASSINADA / "chaves-de-teste.asc", assets / "chaves-de-release.asc")
    _fixar_digitais(assets, DIGITAL_DE_TESTE)
    rede = Rede(tmp_path / "rede")
    monkeypatch.setenv("HEFESTO_RECEITA_REDE", str(rede.pasta))
    return rn, receita, rede


@COM_GPGV
def test_o_bluez_novo_se_reconstroi_com_a_serie_da_casa(receita_bz) -> None:
    """Prova da D-0911-AS-PECAS-DA-CASA-SE-RECONSTROEM-NA-VERSAO-NOVA: o 5.89 publicado vira a
    revisão 7, com o hefesto-0001 e o 0002 aplicados sem fuzz e o device.c conferido."""
    rn, receita, rede = receita_bz
    xz = _bluez_publicado(rede)
    assert rn.receita_do_bluez(receita, receita / "fontes") == "5.89"
    base = rn.ler_baseline((receita / "assets" / "bluez-backport" / "BASELINE").read_text())
    velho = rn.ler_baseline((ASSETS_BZ / "BASELINE").read_text())
    assert base["VERSAO_UPSTREAM"] == "5.89" and base["REVISAO_ULTIMA"] == "7"
    assert base["FONTE_UPSTREAM_SHA256"] == _sha(xz)
    assert base["VERSAO_BASE"] == "5.89-0ubuntu0.1"
    assert base["PATCHES_R7"] == velho["PATCHES_R6"]
    assert base["SHA256_DEVICE_C_R7"] == velho["SHA256_DEVICE_C_R6"]
    entrada = (receita / "assets" / "bluez-backport" / "debian" / "changelog.hefesto").read_text()
    topo = entrada.split("\n -- ", 1)[0]
    assert entrada.startswith("bluez (5.89-0ubuntu0.1~hefesto24.04.7) noble;")
    assert "Cobre a segurança da distro até: 5.72-0ubuntu5.8" in topo


@COM_GPGV
@pytest.mark.parametrize(("como", "diz"), [
    ({"adulterar": True}, "a assinatura não confere"),
    ({"assinatura": "bluez-5.89.tar.sign-da-estranha"}, "não está no chaveiro da casa"),
    ({"publicada": "5.90"}, "abre bluez-5.89, não bluez-5.90"),
])
def test_o_bluez_sem_a_assinatura_da_casa_nao_se_constroi(receita_bz, como: dict[str, Any],
                                                          diz: str) -> None:
    """Prova da D-0911-A-ORIGEM-DO-FONTE-SE-CONFERE-PELA-ASSINATURA: o tarball adulterado, o
    assinado por chave de fora do chaveiro e o assinado de outra versão param na fonte."""
    rn, receita, rede = receita_bz
    _bluez_publicado(rede, **como)
    with pytest.raises(rn.FonteNaoConfere, match=diz):
        rn.receita_do_bluez(receita, receita / "fontes")
    base = rn.ler_baseline((receita / "assets" / "bluez-backport" / "BASELINE").read_text())
    assert base["VERSAO_UPSTREAM"] == "5.88"


@COM_GPGV
def test_a_chave_do_chaveiro_sem_a_digital_fixada_nao_assina(receita_bz) -> None:
    rn, receita, rede = receita_bz
    _fixar_digitais(receita / "assets" / "bluez-backport", DIGITAL_DO_BLUEZ)
    _bluez_publicado(rede)
    with pytest.raises(rn.FonteNaoConfere, match="fora das digitais fixadas"):
        rn.receita_do_bluez(receita, receita / "fontes")


@COM_GPGV
def test_a_assinatura_que_nao_confere_para_antes_da_receita(
        receita_bz, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rn, receita, rede = receita_bz
    _bluez_publicado(rede, adulterar=True)
    (receita / "scripts").mkdir()
    marca = tmp_path / "construiu"
    (receita / "scripts" / "construir_bluez_backport.sh").write_text(f'touch "{marca}"\n')
    assert rn.construir("bluez", receita, tmp_path / "obra") == rn.RC_FONTE
    assert "a fonte não confere" in capsys.readouterr().out and not marca.exists()


def _digital_v4(chave: bytes) -> str:
    tag = chave[0]
    if tag & 0x40:
        tamanho, corpo = chave[2] if chave[2] < 192 else ((chave[2] - 192) << 8) + chave[3] + 192, \
            3 if chave[2] < 192 else 4
    else:
        largura = {0: 1, 1: 2, 2: 4}[tag & 0x03]
        tamanho, corpo = int.from_bytes(chave[1:1 + largura], "big"), 1 + largura
    pacote = chave[corpo:corpo + tamanho]
    return hashlib.sha1(b"\x99" + len(pacote).to_bytes(2, "big") + pacote).hexdigest().upper()


def test_o_chaveiro_versionado_e_a_chave_das_digitais_fixadas() -> None:
    rn = _receita()
    base = rn.ler_baseline((ASSETS_BZ / "BASELINE").read_text())
    chave = rn.desarmar((ASSETS_BZ / "chaves-de-release.asc").read_text())
    assert base["CHAVES_DE_RELEASE"].split() == [DIGITAL_DO_BLUEZ]
    assert _digital_v4(chave) == DIGITAL_DO_BLUEZ
    assert _digital_v4(rn.desarmar((ASSINADA / "chaves-de-teste.asc").read_text())) == \
        DIGITAL_DE_TESTE
    with pytest.raises(rn.FonteNaoConfere):
        rn.desarmar("nada aqui\n")


@COM_GPGV
def test_o_patch_da_casa_que_nao_aplica_pede_revisao(receita_bz) -> None:
    rn, receita, rede = receita_bz
    _bluez_publicado(rede, tar="bluez-5.89-sem-a-serie.tar",
                     assinatura="bluez-5.89-sem-a-serie.tar.sign")
    with pytest.raises(rn.Revisar, match="hefesto-0001"):
        rn.receita_do_bluez(receita, receita / "fontes")


ASSETS_PW = RAIZ / "assets" / "pipewire-backport"
API_PW = "https://gitlab.freedesktop.org/api/v4/projects/pipewire%2F{}/releases?per_page=40"


@pytest.fixture
def receita_pw(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Path, Rede]:
    rn = _receita()
    receita = tmp_path / "receita"
    shutil.copytree(ASSETS_PW, receita / "assets" / "pipewire-backport")
    rede = Rede(tmp_path / "rede")
    rede.por(API_PW.format("pipewire"), '[{"tag_name": "1.6.12"}, {"tag_name": "1.6.11"}]')
    rede.por(API_PW.format("wireplumber"), '[{"tag_name": "0.5.19"}]')
    monkeypatch.setenv("HEFESTO_RECEITA_REDE", str(rede.pasta))
    return rn, receita, rede


def _pipewire_publicado(rede: Rede) -> bytes:
    saida = io.BytesIO()
    with tarfile.open(fileobj=saida, mode="w:bz2") as tar:
        dado = b"metadata\n"
        info = tarfile.TarInfo("pipewire-1.6.12/src/modules/module-metadata/metadata.c")
        info.size = len(dado)
        tar.addfile(info, io.BytesIO(dado))
    rede.por("https://gitlab.freedesktop.org/pipewire/pipewire/-/archive/1.6.12/"
             "pipewire-1.6.12.tar.bz2", saida.getvalue())
    return saida.getvalue()


def test_o_som_novo_sem_a_soma_revisada_pede_revisao_e_nao_baixa(receita_pw) -> None:
    rn, receita, rede = receita_pw
    _pipewire_publicado(rede)
    with pytest.raises(rn.Revisar, match=r"pipewire 1\.6\.12") as erro:
        rn.receita_do_pipewire(receita, receita / "fontes")
    assert erro.value.o_que == "a versão nova"
    assert not (receita / "fontes").exists(), "sem a soma revisada, nada se baixa"


def test_o_som_novo_com_a_soma_revisada_que_nao_bate_nao_se_constroi(receita_pw) -> None:
    rn, receita, rede = receita_pw
    dado = _pipewire_publicado(rede)
    somas = receita / "assets" / "pipewire-backport" / "SOMAS-REVISADAS"
    somas.write_text(somas.read_text() + f"pipewire 1.6.12 {'0' * 64}\n")
    with pytest.raises(rn.FonteNaoConfere, match="a soma que a casa revisou"):
        rn.receita_do_pipewire(receita, receita / "fontes")
    somas.write_text(somas.read_text().replace("0" * 64, _sha(dado)))
    with pytest.raises(rn.Revisar) as erro:
        rn.receita_do_pipewire(receita, receita / "fontes")
    assert erro.value.o_que == "os patches", "com a soma que bate, a fonte passa e a série se tria"


def test_as_somas_revisadas_trazem_as_versoes_de_hoje() -> None:
    rn = _receita()
    base = rn.ler_baseline((ASSETS_PW / "BASELINE").read_text())
    somas = rn.somas_revisadas((ASSETS_PW / "SOMAS-REVISADAS").read_text())
    for prefixo, projeto in (("PW", "pipewire"), ("WP", "wireplumber")):
        versao, sha = base[f"{prefixo}_VERSAO_UPSTREAM"], base[f"{prefixo}_FONTE_SHA256"]
        assert somas[(projeto, versao)] == sha


def test_a_receita_le_a_tag_uma_vez_so() -> None:
    texto = RECEITA.read_text()
    assert "ler(url), ler(url)" not in texto and "sha256sums.asc" not in texto


@pytest.mark.skipif(shutil.which("patch") is None, reason="sem o patch")
def test_a_triagem_mantem_tira_e_para(tmp_path: Path) -> None:
    rn = _receita()
    arvore = tmp_path / "a"
    arvore.mkdir()
    (arvore / "x.c").write_text("um\ndois\ncinco\n")
    (arvore / "y.c").write_text("alfa\nBETA\ngama\n")
    fica = tmp_path / "fica.patch"
    fica.write_text("--- a/x.c\n+++ b/x.c\n@@ -1,3 +1,3 @@\n um\n-dois\n+DOIS\n cinco\n")
    sai = tmp_path / "sai.patch"
    sai.write_text("--- a/y.c\n+++ b/y.c\n@@ -1,3 +1,3 @@\n alfa\n-beta\n+BETA\n gama\n")
    quebra = tmp_path / "quebra.patch"
    quebra.write_text("--- a/y.c\n+++ b/y.c\n@@ -1,3 +1,3 @@\n zeta\n-eta\n+ETA\n teta\n")
    serie = [("fica", fica, True), ("sai", sai, False), ("quebra", quebra, False)]
    triagem = rn.triar(arvore, serie)
    assert (triagem.manter, triagem.sairam, triagem.revisar) == (["fica"], ["sai"], ["quebra"])
    assert (arvore / "x.c").read_text() == "um\nDOIS\ncinco\n"
    (arvore / "y.c").write_text("alfa\nBETA\ngama\n")
    da_casa = rn.triar(arvore, [("sai", sai, True)])
    assert da_casa.revisar == ["sai"], "o upstream levou um patch da casa: alguém olha"


def test_as_versoes_publicadas_se_comparam_por_partes() -> None:
    rn = _receita()
    assert rn.ultima_do_bluez('bluez-5.9.tar.xz bluez-5.10.tar.xz bluez-5.10.tar.xz.sign') == "5.10"
    tags = [{"tag_name": t} for t in ("1.6.9", "1.6.12", "1.7.0", "1.6.10", "lixo")]
    assert rn.ultima_da_serie(tags, (1, 6)) == "1.6.12"
    assert pa.mesma_serie(["1.6.9", "1.6.12", "1.8.0"], "1.6.11") == ("1.6.12", "1.8.0")
    assert pa.mesma_serie(["1.6.9"], "1.6.11") == ("1.6.11", None)


def _receitas_falsas(base: Path, corpo_do_build: str) -> Path:
    receitas = base / "receitas"
    shutil.copytree(ASSETS_BZ, receitas / "assets" / "bluez-backport")
    (receitas / "scripts").mkdir(parents=True)
    script = receitas / "scripts" / "construir_bluez_backport.sh"
    script.write_text("#!/usr/bin/env bash\n" + corpo_do_build + "\n")
    return receitas


@pytest.mark.parametrize(("corpo", "rc", "diz"), [
    ('s="${HEFESTO_BLUEZ_CACHE}/bluez-backport"; mkdir -p "$s"; echo x > "$s/bluez_1_amd64.deb";'
     ' (cd "$s" && sha256sum bluez_1_amd64.deb > SHA256SUMS)', 0, "entregue: bluez"),
    ("exit 3", 3, "faltam dependências"),
    ("exit 5", 10, "a casa precisa revisar os patches"),
])
def test_a_receita_diz_o_que_a_construcao_deu(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                              capsys: pytest.CaptureFixture[str], corpo: str,
                                              rc: int, diz: str) -> None:
    rn = _receita()
    rede = Rede(tmp_path / "rede")
    rede.por(INDICE, '<a href="bluez-5.88.tar.xz">x</a>')
    monkeypatch.setenv("HEFESTO_RECEITA_REDE", str(rede.pasta))
    receitas = _receitas_falsas(tmp_path, corpo)
    assert rn.construir("bluez", receitas, tmp_path / "obra") == rc
    assert diz in capsys.readouterr().out
    if rc == 0:
        assert (tmp_path / "obra" / "entrega" / "SHA256SUMS").is_file()


class Lar:
    """O ajudante sem root, com as pastas desviadas e o apt, o dpkg e o madison de mentira."""

    def __init__(self, base: Path) -> None:
        self.base = base
        self.bin = base / "bin"
        self.bin.mkdir()
        self.cache = base / "cache"
        self.cache.mkdir(mode=0o700)
        self.chamadas = base / "chamadas"
        self.receitas = base / "receitas"
        (self.receitas / "scripts").mkdir(parents=True)
        self.sufixos = base / "sufixos"
        self.sufixos.write_text("~hefesto24.04.\n+0~hefesto1\n")
        self.sufixos.chmod(0o644)
        self.instalados = base / "instalados"
        self.instalados.write_text("bluez\tii \t5.88-0ubuntu0.1~hefesto24.04.6\n"
                                   "libbluetooth3\tii \t5.88-0ubuntu0.1~hefesto24.04.6\n")
        self.duble("apt-get")
        self.duble("dpkg-query", f'cat "{self.instalados}"')
        self.duble("dpkg-deb", 'n="${2##*/}"; [ "$3" = Package ] && echo "${n%%_*}";'
                               ' v="${n#*_}"; [ "$3" = Version ] && echo "${v%_*}";'
                               ' [ "$3" = Source ] && sed -n "s/^Source: //p" "$2"; exit 0')
        self.receita("")

    def duble(self, nome: str, corpo: str = "") -> None:
        arq = self.bin / nome
        arq.write_text(f'#!/bin/sh\necho "{nome} $*" >> "{self.chamadas}"\n{corpo}\n')
        arq.chmod(0o755)

    def receita(self, entrega: str, rc: int = 0, ultima: str = "") -> None:
        script = self.receitas / "scripts" / "hefesto_receita_nova.py"
        script.write_text(
            "import os, sys, subprocess\n"
            "obra = sys.argv[sys.argv.index('--obra') + 1]\n"
            "e = os.path.join(obra, 'entrega')\n"
            "os.makedirs(e, exist_ok=True)\n"
            f"subprocess.run(['bash', '-c', {entrega!r}, '_', e], check=True)\n"
            f"print({ultima!r})\n"
            f"sys.exit({rc})\n")
        for caminho in (self.receitas, self.receitas / "scripts", script):
            caminho.chmod(0o755 if caminho.is_dir() else 0o644)

    def rodar(self, *args: str) -> subprocess.CompletedProcess[str]:
        ambiente = {"PATH": f"{self.bin}:{os.environ['PATH']}", "HOME": str(self.base),
                    "HEFESTO_ATUALIZADOR_CACHE": str(self.cache),
                    "HEFESTO_ATUALIZADOR_RECEITAS": str(self.receitas),
                    "HEFESTO_ATUALIZADOR_SUFIXOS": str(self.sufixos),
                    "HEFESTO_ATUALIZADOR_DONO": pwd.getpwuid(os.getuid()).pw_name}
        return subprocess.run(["bash", str(AJUDANTE), *args], env=ambiente, capture_output=True,
                              text=True, timeout=60, check=False)

    def lidas(self) -> list[str]:
        return self.chamadas.read_text().splitlines() if self.chamadas.exists() else []


ENTREGA_BOA = ('cd "$1" && for p in bluez_5.89-0ubuntu0.1~hefesto24.04.7_amd64.deb '
               'libbluetooth3_5.89-0ubuntu0.1~hefesto24.04.7_amd64.deb '
               'bluez-hcidump_5.89-0ubuntu0.1~hefesto24.04.7_amd64.deb; do'
               ' printf "Source: bluez (5.89)\\n%s\\n" "$p" > "$p"; done;'
               ' sha256sum *.deb > SHA256SUMS')


@pytest.fixture
def lar(tmp_path: Path) -> Lar:
    if os.geteuid() == 0:
        pytest.skip("o ajudante como root usa os caminhos de verdade")
    return Lar(tmp_path)


def test_o_ajudante_constroi_e_instala_so_os_pacotes_da_maquina(lar: Lar) -> None:
    lar.receita(ENTREGA_BOA)
    feito = lar.rodar("backport-construir", "bluez")
    assert feito.returncode == 0, feito.stderr
    novo = lar.cache / "backports" / "bluez" / "novo"
    nomes = {p.name for p in novo.iterdir()}
    assert "SHA256SUMS" in nomes and len(nomes) == 4
    assert all(oct(p.stat().st_mode)[-3:] == "600" for p in novo.iterdir())
    feito = lar.rodar("backport-instalar", "bluez")
    assert feito.returncode == 0, feito.stderr
    apt = [linha for linha in lar.lidas() if linha.startswith("apt-get")]
    assert len(apt) == 1 and " install --no-install-recommends " in apt[0]
    assert "bluez_5.89" in apt[0] and "libbluetooth3_5.89" in apt[0]
    assert "hcidump" not in apt[0], "pacote que a máquina não tem não entra"
    assert (lar.cache / "backports" / "bluez" / "atual").is_dir() and not novo.exists()


def test_a_segunda_subida_guarda_a_anterior_que_volta_uma_vez(lar: Lar) -> None:
    lar.receita(ENTREGA_BOA)
    for _ in range(2):
        assert lar.rodar("backport-construir", "bluez").returncode == 0
        assert lar.rodar("backport-instalar", "bluez").returncode == 0
    feito = lar.rodar("backport-voltar", "bluez")
    assert feito.returncode == 0, feito.stderr
    assert "--allow-downgrades" in lar.lidas()[-1]
    assert lar.rodar("backport-voltar", "bluez").returncode == 2, "a anterior volta uma vez só"


def test_a_construcao_que_pede_revisao_sai_com_o_porque(lar: Lar) -> None:
    lar.receita("true", rc=10, ultima="a casa precisa revisar os patches: hefesto-0001 não aplica")
    feito = lar.rodar("backport-construir", "bluez")
    assert feito.returncode == 10
    assert feito.stdout.strip().splitlines()[-1].startswith("a casa precisa revisar os patches")
    assert not (lar.cache / "backports" / "bluez" / "novo").exists()


def test_o_atalho_na_entrega_nao_se_copia(lar: Lar, tmp_path: Path) -> None:
    segredo = tmp_path / "segredo"
    segredo.write_text("de outro dono\n")
    lar.receita(f'ln -s "{segredo}" "$1/bluez_5.89-0ubuntu0.1~hefesto24.04.7_amd64.deb";'
                ' cd "$1" && sha256sum *.deb > SHA256SUMS')
    feito = lar.rodar("backport-construir", "bluez")
    assert feito.returncode == 2
    assert not (lar.cache / "backports" / "bluez" / "novo").exists()


def test_o_pacote_de_fora_da_casa_nao_se_instala(lar: Lar) -> None:
    lar.receita('cd "$1" && echo x > bluez_5.89-1ubuntu1_amd64.deb && sha256sum *.deb > SHA256SUMS')
    assert lar.rodar("backport-construir", "bluez").returncode == 0
    feito = lar.rodar("backport-instalar", "bluez")
    assert feito.returncode == 2 and "não são da casa" in feito.stderr
    assert not any(linha.startswith("apt-get") for linha in lar.lidas())


def test_o_pacote_da_casa_de_outro_fonte_nao_se_instala(lar: Lar) -> None:
    lar.instalados.write_text(lar.instalados.read_text() + "sudo\tii \t1.9.15p5-3ubuntu5\n")
    lar.receita('cd "$1" && echo "Source: sudo" > sudo_1.9.99~hefesto24.04.7_amd64.deb'
                ' && echo bluez > bluez_5.89-0ubuntu0.1~hefesto24.04.7_amd64.deb'
                ' && sha256sum *.deb > SHA256SUMS')
    assert lar.rodar("backport-construir", "bluez").returncode == 0
    feito = lar.rodar("backport-instalar", "bluez")
    assert feito.returncode == 2 and "vem do fonte sudo, não do de bluez" in feito.stderr
    assert not any(linha.startswith("apt-get") for linha in lar.lidas())


def test_a_entrega_que_e_atalho_nao_se_le(lar: Lar, tmp_path: Path) -> None:
    fora = tmp_path / "fora"
    fora.mkdir()
    (fora / "bluez_5.89-0ubuntu0.1~hefesto24.04.7_amd64.deb").write_text("Source: bluez\n")
    lar.receita(f'cd "{fora}" && sha256sum *.deb > SHA256SUMS'
                f' && rmdir "$1" && ln -s "{fora}" "$1"')
    feito = lar.rodar("backport-construir", "bluez")
    assert feito.returncode == 2 and "não é uma pasta da caixa" in feito.stderr
    assert not (lar.cache / "backports" / "bluez" / "novo").exists()


def test_a_soma_trocada_depois_da_construcao_nao_se_instala(lar: Lar) -> None:
    lar.receita(ENTREGA_BOA)
    assert lar.rodar("backport-construir", "bluez").returncode == 0
    alvo = (lar.cache / "backports" / "bluez" / "novo"
            / "bluez_5.89-0ubuntu0.1~hefesto24.04.7_amd64.deb")
    alvo.write_text("trocado\n")
    feito = lar.rodar("backport-instalar", "bluez")
    assert feito.returncode == 2 and "não confere" in feito.stderr


def test_receitas_que_outro_escreve_e_peca_fora_da_lista_se_recusam(lar: Lar) -> None:
    lar.receita(ENTREGA_BOA)
    (lar.receitas / "scripts").chmod(0o777)
    feito = lar.rodar("backport-construir", "bluez")
    assert feito.returncode == 2 and "receitas" in feito.stderr
    (lar.receitas / "scripts").chmod(0o755)
    for args in (("backport-construir", "kernel"), ("backport-instalar",),
                 ("backport-voltar", "bluez", "x"), ("backport-construir", "../bluez")):
        assert lar.rodar(*args).returncode == 2, args
    assert lar.lidas() == []


def _versoes_com(monkeypatch: pytest.MonkeyPatch, instalados: dict[str, str],
                 respostas: dict[str, str]) -> None:
    monkeypatch.setattr(pa, "_instalados", lambda *pacotes: {
        p: v for p, v in instalados.items() if p in pacotes})
    monkeypatch.setattr(pa, "_ler", lambda url: respostas[url].encode())


def test_o_bluetooth_diz_a_curta_a_completa_e_a_serie_nova(monkeypatch: pytest.MonkeyPatch) -> None:
    casa = {"bluez": "5.88-0ubuntu0.1~hefesto24.04.6"}
    _versoes_com(monkeypatch, casa, {pa.INDICE_DO_BLUEZ: "bluez-5.88.tar.xz bluez-5.89.tar.xz"})
    v = pa.versoes_do_bluetooth(True)
    assert (v.instalada, v.publicada, v.tem_nova(), v.revisar) == ("5.88", "5.89", True, "")
    assert v.completa.startswith("5.88-0ubuntu0.1~hefesto24.04.6 → 5.89")
    _versoes_com(monkeypatch, casa, {pa.INDICE_DO_BLUEZ: "bluez-5.88.tar.xz bluez-6.0.tar.xz"})
    v = pa.versoes_do_bluetooth(True)
    assert pa.PRECISA_REVISAR in v.revisar
    peca = next(p for p in pa.registro() if p.id == "bluetooth")
    assert at._estado_da_peca(peca, v, at.Escolha()) == at.REVISAR
    _versoes_com(monkeypatch, {"bluez": "5.72-0ubuntu5.8"}, {})
    assert pa.versoes_do_bluetooth(True).existe is False, "sem o BlueZ da casa, o apt cuida"


def test_o_som_sobe_na_serie_e_a_serie_nova_pede_revisao(monkeypatch: pytest.MonkeyPatch,
                                                         tmp_path: Path) -> None:
    casa = {"pipewire": "1.6.11-0~hefesto24.04.1", "wireplumber": "0.5.19-0~hefesto24.04.1"}
    api = pa.API_DO_GITLAB.format
    _versoes_com(monkeypatch, casa, {
        api("pipewire"): '[{"tag_name": "1.6.12"}, {"tag_name": "1.8.0"}]',
        api("wireplumber"): '[{"tag_name": "0.5.19"}]'})
    v = pa.versoes_do_som(True)
    assert not v.tem_nova() and v.revisar == (
        f"PipeWire 1.6.12 sem a soma que a casa revisou: {pa.REVISAR_A_VERSAO_NOVA}")
    peca = next(p for p in pa.registro() if p.id == "som")
    assert at._estado_da_peca(peca, v, at.Escolha()) == at.REVISAR
    somas = tmp_path / "SOMAS-REVISADAS"
    somas.write_text(f"pipewire 1.6.12 {'a' * 64}\n")
    monkeypatch.setattr(pa, "SOMAS_REVISADAS_DO_SOM", somas)
    v = pa.versoes_do_som(True)
    assert (v.instalada, v.publicada, v.tem_nova(), v.revisar) == (
        "1.6.11 · 0.5.19", "1.6.12 · 0.5.19", True, "")
    _versoes_com(monkeypatch, casa, {
        api("pipewire"): '[{"tag_name": "1.8.0"}]', api("wireplumber"): "[]"})
    v = pa.versoes_do_som(True)
    assert "PipeWire 1.8.0" in v.revisar and pa.PRECISA_REVISAR in v.revisar


def test_o_portal_compara_pela_ordem_do_debian(monkeypatch: pytest.MonkeyPatch) -> None:
    _versoes_com(monkeypatch, {pa.PACOTE_DO_PORTAL: "1.11.0~1792525517~24.04~f448ddf+0~hefesto1"},
                 {})
    monkeypatch.setattr(pa, "_atualizar_a_lista_do_apt", lambda _rede: None)
    madison = (f" {pa.PACOTE_DO_PORTAL} | 1.11.0~1792525517~24.04~f448ddf+0~hefesto1 | dpkg\n"
               f" {pa.PACOTE_DO_PORTAL} | 1.12.0~1794000000~24.04~aaaaaaa | http://x noble/main\n"
               f" {pa.PACOTE_DO_PORTAL} | 1.11.0~1792525517~24.04~f448ddf | http://x noble/main\n")
    monkeypatch.setattr(pa, "_saida", lambda argv: madison if "madison" in argv else None)
    v = pa.versoes_do_portal(True)
    assert (v.instalada, v.publicada, v.tem_nova()) == ("1.11.0", "1.12.0", True)
    assert v.completa.endswith("1.12.0~1794000000~24.04~aaaaaaa, com a correção da casa")


def test_as_tres_pecas_da_casa_pedem_os_verbos_do_ajudante(monkeypatch: pytest.MonkeyPatch) -> None:
    pedidos: list[tuple[str, ...]] = []
    monkeypatch.setattr(pa, "_raiz", lambda acao, *args, passo=None: pedidos.append((acao, *args)))
    pecas = {p.id: p for p in pa.registro()}
    for ident, backport in (("bluetooth", "bluez"), ("som", "pipewire"), ("portal", "portal")):
        peca = pecas[ident]
        assert peca.volta == 1 and peca.baixar and peca.instalar and peca.voltar
        peca.baixar(at.Passo(), {})
        peca.voltar(peca.instalar(at.Passo(), {}) or {})
        assert pedidos[-3:] == [("backport-construir", backport), ("backport-instalar", backport),
                                ("backport-voltar", backport)]


@pytest.fixture
def gdk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, dict[str, bytes]]:
    from hefesto_dualsense4unix.integrations import receitas_de_ambiente as receitas

    dados = {"xgameruntime.dll": b"MZ nova peca", "gameinput.dll": b"MZ novo gameinput"}
    pino = tmp_path / "pino.txt"
    marca = pa.MARCA_DA_VERSAO_NO_PINO
    pino.write_text(f"name=peca-gdk-2\nurl=https://x/v{marca}/xgameruntime.dll\n"
                    f"sha256={_sha(dados['xgameruntime.dll'])}\n"
                    f"gameinput_url=https://x/v{marca}/gameinput.dll\n"
                    f"gameinput_sha256={_sha(dados['gameinput.dll'])}\n")
    monkeypatch.setattr(receitas, "PINO_DA_PECA", pino)
    casa = tmp_path / "casa"
    monkeypatch.setattr(receitas, "pasta_da_peca", lambda home=None: casa)
    monkeypatch.setattr(pa, "_cache", lambda: tmp_path / "cache")
    (casa / "x86_64-windows").mkdir(parents=True)
    (casa / "x86_64-windows" / "xgameruntime.dll").write_bytes(b"MZ velha")
    (casa / "nativa").mkdir()
    (casa / "nativa" / "gameinput.dll").write_bytes(b"MZ velho gameinput")
    return casa, dados


def test_o_gameinput_sobe_pelo_pino_e_volta(gdk, monkeypatch: pytest.MonkeyPatch) -> None:
    casa, dados = gdk
    baixados: list[str] = []

    def baixar(url: str, destino: Path, passo: at.Passo, sha256: str = "") -> None:
        baixados.append(url)
        dado = dados[destino.name]
        assert _sha(dado) == sha256
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(dado)

    monkeypatch.setattr(pa, "_baixar", baixar)
    antes = pa.versoes_da_gdk(False)
    assert (antes.instalada, antes.publicada, antes.tem_nova()) == ("antiga", "2", True)
    pa._baixar_a_gdk(at.Passo(), {})
    assert all(pa.MARCA_DA_VERSAO_NO_PINO not in url for url in baixados)
    anterior = pa._instalar_a_gdk(at.Passo(), {})
    depois = pa.versoes_da_gdk(False)
    assert (depois.instalada, depois.tem_nova()) == ("2", False)
    pa._voltar_a_gdk(anterior)
    assert (casa / "x86_64-windows" / "xgameruntime.dll").read_bytes() == b"MZ velha"
    assert (casa / "nativa" / "gameinput.dll").read_bytes() == b"MZ velho gameinput"


def test_o_gameinput_trocado_no_caminho_nao_se_instala(gdk, monkeypatch: pytest.MonkeyPatch,
                                                      tmp_path: Path) -> None:
    casa, _dados = gdk
    nova = tmp_path / "cache" / "gdk" / "nova"
    nova.mkdir(parents=True)
    (nova / "xgameruntime.dll").write_bytes(b"MZ trocada")
    (nova / "gameinput.dll").write_bytes(b"MZ trocado")
    with pytest.raises(at.EtapaFalhouError, match="não é o do pino"):
        pa._instalar_a_gdk(at.Passo(), {})
    assert (casa / "x86_64-windows" / "xgameruntime.dll").read_bytes() == b"MZ velha"


def test_a_conferencia_leva_a_completa_e_o_porque_da_revisao() -> None:
    def versoes(_rede: bool) -> at.Versoes:
        return at.Versoes("1.6.11", "1.6.11", completa="PipeWire 1.6.11-0~hefesto24.04.1",
                          revisar="pipewire 1.8.0 é série nova: a casa precisa revisar os patches")

    peca = at.Peca("som", "Som", "PipeWire", "No próximo início da sessão", versoes)
    item = at.conferir(rede=True, lista=[peca])["pecas"][0]
    assert item["estado"] == at.REVISAR and item["completa"].startswith("PipeWire 1.6.11")
    assert item["dica"].endswith("a casa precisa revisar os patches")
