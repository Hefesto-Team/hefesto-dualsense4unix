"""O atualizador reinstala a peça em dia: a versão da máquina, pelo mesmo caminho da subida.

O-ATUALIZADOR-REINSTALA-A-PECA-EM-DIA-01 (09/11/2026). TUDO É DE MENTIRA: o lar é ``tmp_path``
com ``XDG_*`` desviados, a rede é um dicionário, e o ajudante root roda sem root, com as pastas
desviadas e o ``apt-get``, o ``dpkg``, o ``dkms``, o ``uname`` e o ``curl`` como dublês.

AS MORDIDAS (feitas na sprint, com a cura devolvida): o motor sem a reinstalação (a peça em dia
marcada sobe ou não faz nada) reprova o caso da peça em dia; o verbo da reinstalação que aceita
grupo livre reprova o caso dos argumentos; a reinstalação do apt sem a autenticação forçada
reprova o caso do Nvidia; a entrega da casa sem a versão conferida contra a instalada reprova o
caso da versão de outra; o DKMS sem o ``--force`` reprova o caso dos módulos; o MangoHud que
reinstala o baixado de quem chama, ou que aceita o guardado de outra versão, reprova os casos
dele; o Python que reinstala na pasta da subida reprova o caso das rodas; o apt da reinstalação
sem ``--no-remove`` reprova os casos do Nvidia, do conserto e do backport; o porquê gravado fora
de ``motivo`` reprova o contrato com a tela.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import pwd
import socket
import subprocess
import tarfile
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import atualizador as at
from hefesto_dualsense4unix.app.actions import pecas_do_atualizador as pa

RAIZ = Path(__file__).resolve().parents[2]
AJUDANTE = RAIZ / "scripts" / "hefesto_atualizador_raiz.sh"
ALVO = "/usr/local/lib/hefesto-dualsense4unix/atualizador-raiz"


@pytest.fixture(autouse=True)
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    casa = tmp_path / "casa"
    for var, sub in (("XDG_CONFIG_HOME", ".config"), ("XDG_STATE_HOME", ".local/state"),
                     ("XDG_CACHE_HOME", ".cache"), ("XDG_DATA_HOME", ".local/share"),
                     ("XDG_RUNTIME_DIR", "run")):
        (casa / sub).mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(var, str(casa / sub))
    monkeypatch.setenv("HOME", str(casa))
    return casa


@pytest.fixture(autouse=True)
def trava_da_rede(monkeypatch: pytest.MonkeyPatch) -> Any:
    pedidos: list[object] = []

    def _resolver(host: object, *_a: object, **_k: object) -> list[object]:
        pedidos.append(host)
        raise OSError(f"o teste foi à rede: {host}")

    monkeypatch.setattr(socket, "getaddrinfo", _resolver)
    yield pedidos
    assert not pedidos, f"o teste foi à rede: {pedidos}"


def _peca(diario: list[str], ident: str, *, de: str = "1.0", para: str = "1.0",
          falha_em: str = "", reinstala: bool = True, porque: str = "") -> at.Peca:
    def etapa(nome: str) -> Any:
        def fazer(passo: at.Passo, _dados: dict[str, Any]) -> dict[str, Any]:
            diario.append(f"{ident}:{nome}")
            passo.fracao(0.5)
            if nome == falha_em:
                raise at.EtapaFalhouError(f"{ident} quebrou no {nome}")
            return {nome: True}
        return fazer

    reinstalacao = at.Reinstalacao(etapa("baixar-de-novo"), etapa("reinstalar"), etapa("reaplicar"),
                                   lambda _v: porque) if reinstala else None
    return at.Peca(ident, ident.upper(), "dica", "todos", lambda _rede: at.Versoes(de, para),
                   etapa("baixar"), etapa("instalar"), etapa("aplicar"),
                   lambda _anterior: None, reinstalacao=reinstalacao)


def _rodar(lista: list[at.Peca], ids: list[str]) -> int:
    at.conferir(rede=True, lista=lista)
    return at.rodar(ids, lista=lista, jogo_aberto=lambda: False, reiniciar=lambda: True,
                    reabrir=lambda: True, dormir=lambda _s: None)


def test_a_peca_em_dia_marcada_reinstala_a_versao_de_agora() -> None:
    """Prova da D-0911-O-ATUALIZADOR-REINSTALA-A-PECA-EM-DIA: a peça em dia marcada reinstala a
    versão de agora pelo caminho da reinstalação, e a peça com versão nova segue subindo."""
    diario: list[str] = []
    lista = [_peca(diario, "em-dia"), _peca(diario, "nova", para="1.1")]
    assert _rodar(lista, ["em-dia", "nova"]) == 0
    assert diario == ["em-dia:baixar-de-novo", "em-dia:reinstalar", "em-dia:reaplicar",
                      "nova:baixar", "nova:instalar", "nova:aplicar"]
    linhas = {p["id"]: p for p in at.ler_o_andamento()["pecas"]}
    assert linhas["em-dia"]["fazer"] == at.REINSTALAR and linhas["nova"]["fazer"] == at.SUBIR
    assert (linhas["em-dia"]["de"], linhas["em-dia"]["para"]) == ("1.0", "1.0")
    assert linhas["em-dia"]["selo"] == at.PRONTA
    anteriores = at.ler_as_anteriores()
    assert "em-dia" not in anteriores, "reinstalar não vira versão anterior"
    assert anteriores["nova"]["anterior"] == "1.0"


def test_a_reinstalacao_que_quebra_falha_sem_trocar_a_anterior_e_a_fila_segue() -> None:
    diario: list[str] = []
    lista = [_peca(diario, "a", falha_em="reinstalar"), _peca(diario, "b")]
    at._gravar_json(at._estado() / at.ARQUIVO_DAS_ANTERIORES,
                    {"a": {"nome": "A", "agora": "1.0", "anterior": "0.9", "dados": {"x": 1}}})
    assert _rodar(lista, ["a", "b"]) == 1
    assert diario == ["a:baixar-de-novo", "a:reinstalar", "b:baixar-de-novo", "b:reinstalar",
                      "b:reaplicar"]
    linha = next(p for p in at.ler_o_andamento()["pecas"] if p["id"] == "a")
    assert linha["selo"] == at.FALHOU and linha["motivo"] == "a quebrou no reinstalar"
    assert at.ler_as_anteriores()["a"]["anterior"] == "0.9"


def test_a_peca_em_dia_que_nao_se_reinstala_diz_por_que_e_sai_da_fila() -> None:
    diario: list[str] = []
    lista = [_peca(diario, "sem", reinstala=False),
             _peca(diario, "fora", porque="a entrega não é a versão de agora"),
             _peca(diario, "sim")]
    itens = {i["id"]: i for i in at.conferir(rede=True, lista=lista)["pecas"]}
    assert (itens["sem"]["reinstala"], itens["sem"]["motivo"]) == (
        False, at.NAO_SE_REINSTALA)
    assert (itens["fora"]["reinstala"], itens["fora"]["motivo"]) == (
        False, "a entrega não é a versão de agora")
    assert (itens["sim"]["reinstala"], itens["sim"]["motivo"]) == (True, "")
    assert all("sem_reinstalar" not in item for item in itens.values()), "um nome só: motivo"
    assert _rodar(lista, ["sem", "fora", "sim"]) == 0
    assert diario == ["sim:baixar-de-novo", "sim:reinstalar", "sim:reaplicar"]
    assert [p["id"] for p in at.ler_o_andamento()["pecas"]] == ["sim"]


def test_a_tela_le_reinstala_e_motivo_e_o_motor_distingue_pela_conferencia() -> None:
    """O contrato com a tela: cada item traz ``reinstala`` e ``motivo``; os ids chegam misturados
    pelo ``soltar`` e o motor separa subir de reinstalar pela conferência, sem gravar a escolha."""
    diario: list[str] = []
    lista = [_peca(diario, "em-dia"), _peca(diario, "nova", para="1.1"),
             _peca(diario, "fora", porque="a entrega não é a versão de agora")]
    escolha = at._config() / at.ARQUIVO_DA_ESCOLHA
    for item in at.conferir(rede=True, lista=lista)["pecas"]:
        assert isinstance(item["reinstala"], bool) and isinstance(item["motivo"], str), item
        assert item["reinstala"] is (item["motivo"] == ""), item
    assert _rodar(lista, ["fora", "nova", "em-dia"]) == 0
    assert not escolha.exists(), "a marca de reinstalar só vive na tela"
    assert {p["id"]: p["fazer"] for p in at.ler_o_andamento()["pecas"]} == {
        "em-dia": at.REINSTALAR, "nova": at.SUBIR}


def test_a_pergunta_da_reinstalacao_so_vai_a_peca_em_dia() -> None:
    perguntas: list[str] = []
    peca = at.Peca("x", "X", "dica", "todos", lambda _r: at.Versoes("1.0", "1.1"),
                   reinstalacao=at.Reinstalacao(por_que_nao=lambda _v: perguntas.append("x") or ""))
    assert at.conferir(rede=True, lista=[peca])["pecas"][0]["estado"] == at.NOVA
    assert perguntas == []


def _regra() -> set[tuple[str, ...]]:
    feito = subprocess.run(["bash", str(AJUDANTE), "regra-sudo", "fulana"], capture_output=True,
                           text=True, check=True, timeout=30)
    return {tuple(linha.strip().rstrip(", \\").split()[1:]) for linha in feito.stdout.splitlines()
            if linha.strip().startswith(ALVO)}


def test_toda_reinstalacao_pede_ao_root_so_um_verbo_da_regra(
        monkeypatch: pytest.MonkeyPatch) -> None:
    pedidos: list[tuple[str, ...]] = []
    def _raiz(verbo: str, *args: str, **_k: object) -> str:
        pedidos.append((verbo, *args))
        return "reinstala: MangoHud-1.tar.gz"

    monkeypatch.setattr(pa, "_raiz", _raiz)
    pecas = {p.id: p for p in pa.registro()}
    assert all(p.reinstalacao is not None for p in pecas.values()), "toda peça é marcável"
    for ident in ("bluetooth", "som", "portal", "nvidia", "kernel", "dkms", "sistema", "mangohud"):
        r = pecas[ident].reinstalacao
        assert r is not None
        if r.por_que_nao is not None:
            assert r.por_que_nao(at.Versoes("1", "1")) == ""
        for etapa in (r.baixar, r.instalar, r.aplicar):
            if etapa is not None:
                etapa(at.Passo(), {})
    regra = _regra()
    assert pedidos and all(p in regra for p in pedidos), set(pedidos) - regra
    novos = {p[0] for p in pedidos}
    assert {"apt-baixar-de-novo", "apt-reinstalar", "apt-consertar", "dkms-reinstalar",
            "mangohud-reinstalavel", "mangohud-reinstalar", "backport-reinstalavel",
            "backport-reinstalar"} <= novos


class Lar:
    """O ajudante sem root, com as pastas desviadas e o apt, o dpkg e o dkms de mentira."""

    def __init__(self, base: Path) -> None:
        self.base = base
        self.bin = base / "bin"
        self.bin.mkdir()
        self.chamadas = base / "chamadas"
        self.cache = base / "cache"
        self.cache.mkdir(mode=0o700)
        self.casa = base / "casa-root"
        self.casa.mkdir()
        self.src = base / "src"
        self.src.mkdir()
        self.modulos = base / "modules"
        self.sufixos = base / "sufixos"
        self.sufixos.write_text("~hefesto24.04.\n+0~hefesto1\n")
        self.sufixos.chmod(0o644)
        self.segurados = base / "segurados"
        self.segurados.write_text("")
        self.instalados = base / "instalados"
        self.instalar(
            ("nvidia-driver-595", "595.104.02-1pop1"), ("libnvidia-gl-595", "595.104.02-1pop1"),
            ("linux-system76", "7.2.15.76070215"),
            ("linux-image-7.2.15-76070215-generic", "7.2.15-76070215.2026"),
            ("linux-modules-7.2.15-76070215-generic", "7.2.15-76070215.2026"),
            ("linux-image-7.2.12-76070212-generic", "7.2.12-76070212.2026"),
            ("bluez", "5.88-0ubuntu0.1~hefesto24.04.6"),
            ("libbluetooth3", "5.88-0ubuntu0.1~hefesto24.04.6"))
        self.api = ""
        for nome in ("apt-get", "dpkg", "dkms", "update-initramfs"):
            self.duble(nome)
        self.duble("uname", "echo 7.2.15-76070215-generic")
        self.duble("apt-mark", f'[ "$1" = showhold ] && cat "{self.segurados}"; exit 0')
        self.duble("dpkg-query", f'cat "{self.instalados}"')
        self.duble("dpkg-deb", 'n="${2##*/}"; [ "$3" = Package ] && echo "${n%%_*}";'
                               ' v="${n#*_}"; [ "$3" = Version ] && echo "${v%_*}";'
                               ' [ "$3" = Source ] && sed -n "s/^Source: //p" "$2"; exit 0')

    def instalar(self, *pacotes: tuple[str, str]) -> None:
        self.instalados.write_text("".join(f"{p}\tii \t{v}\n" for p, v in pacotes))

    def duble(self, nome: str, corpo: str = "") -> None:
        arq = self.bin / nome
        arq.write_text(f'#!/bin/sh\necho "{nome} $*" >> "{self.chamadas}"\n{corpo}\n')
        arq.chmod(0o755)

    def rodar(self, *args: str) -> subprocess.CompletedProcess[str]:
        ambiente = {"PATH": f"{self.bin}:{os.environ['PATH']}", "HOME": str(self.base),
                    "HEFESTO_ATUALIZADOR_CACHE": str(self.cache),
                    "HEFESTO_ATUALIZADOR_CASA": str(self.casa),
                    "HEFESTO_ATUALIZADOR_SRC": str(self.src),
                    "HEFESTO_ATUALIZADOR_MODULOS": str(self.modulos),
                    "HEFESTO_ATUALIZADOR_SUFIXOS": str(self.sufixos),
                    "HEFESTO_ATUALIZADOR_API": self.api,
                    "HEFESTO_ATUALIZADOR_DONO": pwd.getpwuid(os.getuid()).pw_name}
        return subprocess.run(["bash", str(AJUDANTE), *args], env=ambiente, capture_output=True,
                              text=True, timeout=60, check=False)

    def lidas(self, comeco: str = "") -> list[str]:
        linhas = self.chamadas.read_text().splitlines() if self.chamadas.exists() else []
        return [linha for linha in linhas if linha.startswith(comeco)]


@pytest.fixture
def raiz(tmp_path: Path) -> Lar:
    if os.geteuid() == 0:
        pytest.skip("o ajudante como root usa os caminhos de verdade")
    (tmp_path / "lar-do-ajudante").mkdir()
    return Lar(tmp_path / "lar-do-ajudante")


AUTENTICACAO = ("-o APT::Get::AllowUnauthenticated=false",
                "-o Acquire::AllowInsecureRepositories=false",
                "-o Acquire::AllowDowngradeToInsecureRepositories=false",
                " --no-remove ", "-o APT::Get::allow-downgrades=false",
                "-o APT::Get::allow-remove-essential=false",
                "-o APT::Get::allow-change-held-packages=false")


def test_o_nvidia_e_o_kernel_reinstalam_so_a_versao_instalada_com_o_apt_assinado(
        raiz: Lar) -> None:
    for args in (("apt-baixar-de-novo", "nvidia"), ("apt-reinstalar", "nvidia"),
                 ("apt-reinstalar", "kernel")):
        feito = raiz.rodar(*args)
        assert feito.returncode == 0, feito.stderr
    apt = raiz.lidas("apt-get")
    assert len(apt) == 3
    assert all(o in linha for linha in apt for o in AUTENTICACAO), apt
    assert apt[0].endswith(" -d install --reinstall --no-install-recommends "
                           "libnvidia-gl-595=595.104.02-1pop1 nvidia-driver-595=595.104.02-1pop1")
    assert " -d " not in apt[1] and "nvidia-driver-595=595.104.02-1pop1" in apt[1]
    assert apt[2].endswith(" install --reinstall --no-install-recommends "
                           "linux-image-7.2.15-76070215-generic=7.2.15-76070215.2026 "
                           "linux-modules-7.2.15-76070215-generic=7.2.15-76070215.2026")
    assert "7.2.12" not in apt[2] and "linux-system76" not in apt[2]


def test_o_kernel_de_nome_estranho_e_o_grupo_vazio_nao_reinstalam(raiz: Lar) -> None:
    raiz.duble("uname", "echo '7.2.15;rm'")
    feito = raiz.rodar("apt-reinstalar", "kernel")
    assert feito.returncode == 2 and "nome estranho" in feito.stderr
    raiz.instalar(("bluez", "5.88-0ubuntu0.1~hefesto24.04.6"))
    feito = raiz.rodar("apt-reinstalar", "nvidia")
    assert feito.returncode == 2 and "nada instalado" in feito.stderr
    assert raiz.lidas("apt-get") == []


def test_os_verbos_da_reinstalacao_nao_aceitam_argumento_livre(raiz: Lar) -> None:
    for args in (("apt-reinstalar", "sistema"), ("apt-reinstalar", "tudo"),
                 ("apt-baixar-de-novo", "curl"), ("apt-reinstalar",),
                 ("apt-reinstalar", "nvidia", "x"),
                 ("apt-reinstalar", "nvidia=1.0"), ("apt-consertar", "x"),
                 ("dkms-reinstalar", "--force"), ("mangohud-reinstalar", "0.8.5"),
                 ("backport-reinstalar", "../bluez"), ("backport-reinstalar", "kernel"),
                 ("backport-reinstalavel",), ("backport-reinstalar", "bluez", "x")):
        assert raiz.rodar(*args).returncode == 2, args
    assert raiz.lidas() == []


def test_os_pacotes_do_sistema_consertam_o_apt(raiz: Lar) -> None:
    feito = raiz.rodar("apt-consertar")
    assert feito.returncode == 0, feito.stderr
    assert raiz.lidas("dpkg ") == ["dpkg --force-confdef --force-confold --configure -a"]
    apt = raiz.lidas("apt-get")
    assert len(apt) == 1 and apt[0].endswith(" --no-install-recommends -f install")
    assert all(o in apt[0] for o in AUTENTICACAO)


def test_os_modulos_se_recompilam_mesmo_instalados(raiz: Lar) -> None:
    pasta = raiz.src / "hefesto-hid-playstation-1.0.0"
    pasta.mkdir()
    (pasta / "dkms.conf").write_text("PACKAGE_NAME=x\n")
    pasta.chmod(0o755)
    (pasta / "dkms.conf").chmod(0o644)
    (raiz.modulos / "7.2.15-76070215-generic" / "build").mkdir(parents=True)
    raiz.duble("dkms", '[ "$1" = status ] && echo "hefesto-hid-playstation/1.0.0: installed";'
                       ' exit 0')
    assert raiz.rodar("dkms-refazer").returncode == 0
    assert raiz.lidas("dkms build") == [] and raiz.lidas("dkms install") == []
    feito = raiz.rodar("dkms-reinstalar")
    assert feito.returncode == 0, feito.stderr
    k = "-m hefesto-hid-playstation -v 1.0.0 -k 7.2.15-76070215-generic"
    assert raiz.lidas("dkms build") == [f"dkms build --force {k}"]
    assert raiz.lidas("dkms install") == [f"dkms install --force {k}"]
    raiz.duble("dkms", '[ "$1" = build ] && exit 1; exit 0')
    feito = raiz.rodar("dkms-reinstalar")
    assert feito.returncode != 0
    assert len(raiz.lidas("dkms install")) == 1, "o build que quebra não instala por cima"


def _tar_do_mangohud(raiz: Lar, nome: str) -> Path:
    pasta = raiz.casa / ".cache" / "hefesto-dualsense4unix" / "atualizador" / "mangohud"
    pasta.mkdir(parents=True, exist_ok=True)
    for velho in pasta.iterdir():
        velho.unlink()
    setup = f'#!/bin/sh\necho "setup $*" >> "{raiz.chamadas}"\necho {nome}\n'.encode()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo("MangoHud/mangohud-setup.sh")
        info.size, info.mode = len(setup), 0o755
        tar.addfile(info, io.BytesIO(setup))
    arq = pasta / nome
    arq.write_bytes(buf.getvalue())
    resposta = raiz.base / "release.json"
    resposta.write_text(json.dumps({"assets": [{
        "name": nome, "digest": f"sha256:{hashlib.sha256(arq.read_bytes()).hexdigest()}"}]}))
    raiz.duble("curl", f'cat "{resposta}"')
    raiz.api = "https://exemplo.invalid/release"
    return arq


def test_o_mangohud_reinstala_so_o_que_o_ajudante_instalou_sem_perder_a_anterior(
        raiz: Lar) -> None:
    for verbo in ("mangohud-reinstalavel", "mangohud-reinstalar"):
        feito = raiz.rodar(verbo)
        assert feito.returncode == 2 and "primeira subida" in feito.stderr, verbo
    velho = _tar_do_mangohud(raiz, "MangoHud-0.8.4.tar.gz").read_bytes()
    assert raiz.rodar("mangohud-instalar").returncode == 0
    novo = _tar_do_mangohud(raiz, "MangoHud-0.8.5.tar.gz").read_bytes()
    assert raiz.rodar("mangohud-instalar").returncode == 0
    _tar_do_mangohud(raiz, "MangoHud-0.8.6.tar.gz")
    pasta = raiz.cache / "mangohud"
    feito = raiz.rodar("mangohud-reinstalavel")
    assert feito.returncode == 0 and feito.stdout.strip() == "reinstala: MangoHud-0.8.5.tar.gz"
    feito = raiz.rodar("mangohud-reinstalar")
    assert feito.returncode == 0, feito.stderr
    assert "MangoHud-0.8.5.tar.gz" in feito.stdout
    assert (pasta / "atual.tar.gz").read_bytes() == novo, "o baixado de quem chama não entra"
    assert (pasta / "anterior.tar.gz").read_bytes() == velho, "a reinstalação não gira a anterior"
    assert raiz.lidas("setup").count("setup install") == 3
    assert len(raiz.lidas("curl")) == 2, "a reinstalação não vai à rede"
    assert raiz.rodar("mangohud-voltar").returncode == 0
    assert (pasta / "atual.nome").read_text().strip() == "MangoHud-0.8.4.tar.gz"
    (pasta / "atual.nome").write_text("MangoHud-0.8.4;rm.tar.gz\n")
    feito = raiz.rodar("mangohud-reinstalar")
    assert feito.returncode == 2 and "estragado" in feito.stderr
    assert raiz.lidas("setup").count("setup install") == 4


DEBS_DA_CASA = ("bluez_5.88-0ubuntu0.1~hefesto24.04.6_amd64.deb",
                "libbluetooth3_5.88-0ubuntu0.1~hefesto24.04.6_amd64.deb",
                "bluez-hcidump_5.88-0ubuntu0.1~hefesto24.04.6_amd64.deb")


def _entrega(raiz: Lar, debs: tuple[str, ...] = DEBS_DA_CASA, fonte: str = "bluez") -> Path:
    atual = raiz.cache / "backports" / "bluez" / "atual"
    atual.mkdir(parents=True, mode=0o700)
    (raiz.cache / "backports").chmod(0o700)
    (raiz.cache / "backports" / "bluez").chmod(0o700)
    linhas = []
    for nome in debs:
        conteudo = f"Source: {fonte} (5.88)\n{nome}\n".encode()
        (atual / nome).write_bytes(conteudo)
        (atual / nome).chmod(0o600)
        linhas.append(f"{hashlib.sha256(conteudo).hexdigest()}  {nome}\n")
    (atual / "SHA256SUMS").write_text("".join(linhas))
    (atual / "SHA256SUMS").chmod(0o600)
    return atual


def test_o_backport_reinstala_so_a_entrega_que_o_ajudante_instalou(raiz: Lar) -> None:
    feito = raiz.rodar("backport-reinstalavel", "bluez")
    assert feito.returncode == 2 and "sem a entrega de bluez" in feito.stderr
    atual = _entrega(raiz)
    feito = raiz.rodar("backport-reinstalavel", "bluez")
    assert feito.returncode == 0, feito.stderr
    assert raiz.lidas("apt-get") == []
    feito = raiz.rodar("backport-reinstalar", "bluez")
    assert feito.returncode == 0, feito.stderr
    apt = raiz.lidas("apt-get")
    assert len(apt) == 1 and " install --reinstall --no-install-recommends " in apt[0]
    assert all(o in apt[0] for o in AUTENTICACAO)
    assert f"{atual}/bluez_5.88" in apt[0] and f"{atual}/libbluetooth3_5.88" in apt[0]
    assert "hcidump" not in apt[0], "o pacote que a máquina não tem não entra"
    assert sorted(p.name for p in atual.iterdir()) == sorted([*DEBS_DA_CASA, "SHA256SUMS"])
    assert not (atual.parent / "anterior").exists(), "reinstalar não gira a anterior"


def test_a_entrega_de_outra_versao_nao_se_reinstala(raiz: Lar) -> None:
    _entrega(raiz)
    raiz.instalar(("bluez", "5.89-0ubuntu0.1~hefesto24.04.7"),
                  ("libbluetooth3", "5.88-0ubuntu0.1~hefesto24.04.6"))
    for verbo in ("backport-reinstalavel", "backport-reinstalar"):
        feito = raiz.rodar(verbo, "bluez")
        assert feito.returncode == 2 and "não é a versão de agora" in feito.stderr, verbo
    assert raiz.lidas("apt-get") == []


@pytest.mark.parametrize(("estrago", "diz"), [
    ("soma", "não confere"), ("fonte", "não são da casa"), ("atalho", "sem a entrega"),
    ("dono", "sem a entrega")])
def test_a_entrega_estragada_nao_se_reinstala(raiz: Lar, tmp_path: Path, estrago: str,
                                              diz: str) -> None:
    atual = _entrega(raiz, fonte="sudo" if estrago == "fonte" else "bluez")
    if estrago == "soma":
        (atual / DEBS_DA_CASA[0]).write_text("trocado\n")
    elif estrago == "atalho":
        fora = tmp_path / "fora"
        atual.rename(fora)
        atual.symlink_to(fora)
    elif estrago == "dono":
        atual.chmod(0o777)
    feito = raiz.rodar("backport-reinstalar", "bluez")
    assert feito.returncode == 2 and diz in feito.stderr, feito.stderr
    assert raiz.lidas("apt-get") == []


def test_a_pergunta_ao_ajudante_diz_o_porque_sem_o_prefixo(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pa, "AJUDANTE", tmp_path / "nao-existe")
    assert "rode o install" in pa._pergunta_da_raiz("backport-reinstalavel", "bluez")
    ajudante = tmp_path / "atualizador-raiz"
    ajudante.write_text("", encoding="utf-8")
    monkeypatch.setattr(pa, "AJUDANTE", ajudante)
    monkeypatch.setattr(pa, "_comando", lambda argv, **_k: (
        2, "atualizador-raiz: sem a entrega de bluez que este ajudante instalou"))
    assert pa._pergunta_da_raiz("backport-reinstalavel", "bluez") == \
        "sem a entrega de bluez que este ajudante instalou"
    monkeypatch.setattr(pa, "_comando", lambda argv, **_k: (1, "sudo: a password is required"))
    assert "rode o install" in pa._pergunta_da_raiz("backport-reinstalavel", "bluez")


def test_o_python_reinstala_as_rodas_de_agora_numa_pasta_propria(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pa, "_rodas_de_agora", lambda: {"evdev": "1.9.3", "pydantic": "2.12.0"})
    da_subida = pa._pasta_do_python() / "antes" / "evdev-1.9.2.whl"
    da_subida.parent.mkdir(parents=True)
    da_subida.write_text("a anterior da subida")
    pedidos: list[tuple[str, ...]] = []
    monkeypatch.setattr(pa, "_pip", lambda *args, **_k: (pedidos.append(args), (0, ""))[1])
    monkeypatch.setattr(pa, "_o_produto_sobe", lambda: "")
    r = next(p for p in pa.registro() if p.id == "python").reinstalacao
    assert r is not None and r.baixar is not None and r.instalar is not None
    dados = r.baixar(at.Passo(), {}) or {}
    r.instalar(at.Passo(), dados)
    pasta = str(pa._pasta_da_reinstalacao_do_python())
    assert pedidos[0] == ("wheel", "--wheel-dir", pasta, "evdev==1.9.3", "pydantic==2.12.0")
    assert pedidos[1] == ("install", "--no-index", "--only-binary", ":all:", "--force-reinstall",
                          "--no-deps", "--find-links", pasta, "evdev==1.9.3", "pydantic==2.12.0")
    assert da_subida.read_text() == "a anterior da subida", "a volta da subida fica"
    monkeypatch.setattr(pa, "_o_produto_sobe", lambda: "ImportError: evdev")
    with pytest.raises(at.EtapaFalhouError, match="não sobe depois da reinstalação"):
        r.instalar(at.Passo(), dados)


def _tar_do_proton(caminho: Path, nome: str, conteudo: bytes) -> str:
    with tarfile.open(caminho, "w:gz") as tar:
        for arquivo, dado in (("proton", conteudo), ("version", b"1 GE\n")):
            info = tarfile.TarInfo(f"{nome}/{arquivo}")
            info.size, info.mode = len(dado), 0o755
            tar.addfile(info, io.BytesIO(dado))
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


@pytest.fixture
def proton(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, list[str]]:
    from hefesto_dualsense4unix.integrations import proton_pin as pp

    nome = "GE-Proton11-12"
    publicado = tmp_path / "publicado.tar.gz"
    sha = _tar_do_proton(publicado, nome, b"#!/bin/sh\necho bom\n")
    compat, cache = tmp_path / "steam" / "compatibilitytools.d", tmp_path / "cache-ge"
    (compat / nome).mkdir(parents=True)
    (compat / nome / "proton").write_text("quebrado")
    (compat / nome / "version").write_text("1 GE\n")
    conf = {"name": "GE-Proton11-7", "url": "https://x/11-7.tar.gz", "sha256": "a" * 64}
    monkeypatch.setattr(pp, "_load_conf", lambda _p: conf)
    monkeypatch.setattr(pp, "pino_que_vale", lambda _c, _d=None: nome)
    monkeypatch.setattr(pp, "default_compat_dir", lambda home=None: compat)
    monkeypatch.setattr(pp, "default_cache_dir", lambda home=None: cache)
    monkeypatch.setattr(pp, "_steam_gate", lambda: None)
    pp._gravar_registro(cache, {"name": nome, "url": "https://x/11-12.tar.gz", "sha256": sha})
    baixados: list[str] = []

    def baixar(url: str, destino: Path, _passo: at.Passo, _sha: str = "") -> None:
        baixados.append(url)
        destino.write_bytes(publicado.read_bytes())

    monkeypatch.setattr(pa, "_baixar", baixar)
    return compat / nome, publicado, baixados


def test_o_proton_refaz_a_pasta_do_pino_que_vale(proton) -> None:
    pasta, _publicado, baixados = proton
    r = next(p for p in pa.registro() if p.id == "proton").reinstalacao
    assert r is not None and r.por_que_nao is not None and r.baixar and r.instalar
    assert r.por_que_nao(at.Versoes("11-12", "11-12")) == ""
    dados = r.baixar(at.Passo(), {}) or {}
    r.instalar(at.Passo(), dados)
    assert baixados == ["https://x/11-12.tar.gz"]
    assert (pasta / "proton").read_text() == "#!/bin/sh\necho bom\n"


def test_o_proton_trocado_no_caminho_ou_com_a_steam_aberta_nao_se_refaz(
        proton, monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.integrations import proton_pin as pp

    pasta, publicado, _baixados = proton
    r = next(p for p in pa.registro() if p.id == "proton").reinstalacao
    assert r is not None and r.baixar and r.instalar
    dados = r.baixar(at.Passo(), {}) or {}
    monkeypatch.setattr(pp, "_steam_gate", lambda: "aberta")
    with pytest.raises(at.EtapaFalhouError):
        r.instalar(at.Passo(), dados)
    assert (pasta / "proton").read_text() == "quebrado"
    monkeypatch.setattr(pp, "_steam_gate", lambda: None)
    (pp.default_cache_dir() / "GE-Proton11-12.tar.gz").write_bytes(b"trocado")
    with pytest.raises(at.EtapaFalhouError):
        r.instalar(at.Passo(), dados)
    assert (pasta / "proton").read_text() == "quebrado"
    pp._gravar_registro(pp.default_cache_dir(), {"name": "GE-Proton11-11"})
    assert "soma guardada" in pa._proton_sem_reinstalar(at.Versoes())
    assert publicado.is_file()


def _tar_do_umu(caminho: Path) -> Path:
    with tarfile.open(caminho, "w") as tar:
        info = tarfile.TarInfo("umu/umu-run")
        dado = b"#!/bin/sh\necho bom\n"
        info.size, info.mode = len(dado), 0o755
        tar.addfile(info, io.BytesIO(dado))
    return caminho


def test_o_umu_reinstala_a_tag_do_disco_sem_apagar_a_anterior(
        lar: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for versao in ("1.4.3", "1.4.4"):
        dados = {"tar": str(_tar_do_umu(tmp_path / f"{versao}.tar")), "tag": versao}
        dados.update(pa._instalar_o_umu(at.Passo(), dados))
        pa._aplicar_o_umu(at.Passo(), dados)
    executavel = next((pa._pasta_do_umu() / "1.4.4").rglob("umu-run"))
    executavel.write_text("quebrado")
    zipapp = _tar_do_umu(tmp_path / "publicado.tar").read_bytes()
    nome = "umu-launcher-1.4.4-zipapp.tar"
    pedidas: list[str] = []

    def ler(url: str) -> bytes:
        pedidas.append(url)
        return json.dumps({"tag_name": "1.4.4", "assets": [{
            "name": nome, "browser_download_url": "https://x/umu.tar",
            "digest": f"sha256:{hashlib.sha256(zipapp).hexdigest()}"}]}).encode()

    monkeypatch.setattr(pa, "_ler", ler)
    monkeypatch.setattr(pa, "_baixar", lambda _u, destino, _p, _s="": (
        destino.parent.mkdir(parents=True, exist_ok=True), destino.write_bytes(zipapp)))
    r = next(p for p in pa.registro() if p.id == "umu").reinstalacao
    assert r is not None and r.por_que_nao is not None and r.baixar and r.instalar and r.aplicar
    assert r.por_que_nao(at.Versoes("1.4.4", "1.4.4")) == ""
    dados = r.baixar(at.Passo(), {}) or {}
    dados.update(r.instalar(at.Passo(), dados) or {})
    r.aplicar(at.Passo(), dados)
    assert pedidas == [pa.API_DA_TAG.format(pa.REPO_DO_UMU, "1.4.4")]
    casa = lar / ".local" / "bin" / "umu-run"
    assert "1.4.4" in str(casa.resolve()) and casa.resolve().read_text() == "#!/bin/sh\necho bom\n"
    assert (pa._pasta_do_umu() / "1.4.3").is_dir(), "a anterior da subida fica"
    casa.unlink()
    casa.write_text("#!/bin/sh\n")
    assert "não é o do Hefesto" in r.por_que_nao(at.Versoes("1.4.4", "1.4.4"))


def test_o_mangohud_so_reinstala_o_que_o_ajudante_guardou_na_versao_instalada(
        monkeypatch: pytest.MonkeyPatch) -> None:
    r = next(p for p in pa.registro() if p.id == "mangohud").reinstalacao
    assert r is not None and r.por_que_nao is not None and r.baixar is None
    resposta = ("", "reinstala: MangoHud-v0.8.5.tar.gz")
    monkeypatch.setattr(pa, "_resposta_da_raiz", lambda acao, *a: resposta)
    assert r.por_que_nao(at.Versoes("0.8.5", "0.8.6")) == ""
    assert "não é a versão instalada" in r.por_que_nao(at.Versoes("0.8.4", "0.8.4"))
    assert "não está instalado" in r.por_que_nao(at.Versoes("", "0.8.5"))
    resposta = ("sem o MangoHud que este ajudante instalou", "")
    assert r.por_que_nao(at.Versoes("0.8.5", "0.8.5")) == resposta[0]


def test_a_gdk_reinstala_pelo_pino_sem_trocar_a_anterior(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    dados = {"xgameruntime.dll": b"MZ peca", "gameinput.dll": b"MZ gameinput"}
    pino = {"name": "peca-gdk-2", "url": "https://x/xgameruntime.dll",
            "sha256": hashlib.sha256(dados["xgameruntime.dll"]).hexdigest(),
            "gameinput_url": "https://x/gameinput.dll",
            "gameinput_sha256": hashlib.sha256(dados["gameinput.dll"]).hexdigest()}
    casa = tmp_path / "peca"
    monkeypatch.setattr(pa, "_pino_da_gdk", lambda: pino)
    monkeypatch.setattr(pa, "_pasta_da_gdk", lambda: casa)
    monkeypatch.setattr(pa, "_baixar", lambda url, destino, _p, _s="": (
        destino.parent.mkdir(parents=True, exist_ok=True),
        destino.write_bytes(dados[url.rsplit("/", 1)[-1]])))
    (casa / "x86_64-windows").mkdir(parents=True)
    (casa / "x86_64-windows" / "xgameruntime.dll").write_bytes(b"quebrada")
    anterior = pa._cache() / "gdk" / "anterior" / "xgameruntime.dll"
    anterior.parent.mkdir(parents=True)
    anterior.write_bytes(b"MZ de antes")
    r = next(p for p in pa.registro() if p.id == "gdk").reinstalacao
    assert r is not None and r.baixar and r.instalar
    r.baixar(at.Passo(), {})
    r.instalar(at.Passo(), {})
    assert (casa / "x86_64-windows" / "xgameruntime.dll").read_bytes() == b"MZ peca"
    assert anterior.read_bytes() == b"MZ de antes"


def test_o_hefesto_reinstala_rodando_o_install_com_a_guarda_do_avanco(
        monkeypatch: pytest.MonkeyPatch) -> None:
    feito: list[str] = []

    class Vao:
        def __init__(self) -> None:
            self.motivo = ""
            self.nota: list[str] = []

        def por_que_nao(self, _raiz: Path) -> str:
            return self.motivo

        def _instalar(self, _raiz: Path, _rodar: Any) -> None:
            feito.append("install")

        def _rodar_o_install(self, _raiz: Path) -> str:
            return ""

        def _linhas_da_nota(self) -> list[str]:
            return self.nota

        def _motivo_da_nota(self, linhas: list[str]) -> str:
            return linhas[0] if linhas else ""

    vao = Vao()
    monkeypatch.setattr(pa, "_vao", lambda: vao)
    r = next(p for p in pa.registro() if p.id == "hefesto").reinstalacao
    assert r is not None and r.instalar is not None and r.baixar is None
    r.instalar(at.Passo(), {})
    assert feito == ["install"]
    vao.motivo = "árvore com mudança"
    with pytest.raises(at.EtapaFalhouError, match="árvore com mudança"):
        r.instalar(at.Passo(), {})
    assert feito == ["install"]
    vao.motivo, vao.nota = "", ["o install saiu com o código 1"]
    with pytest.raises(at.EtapaFalhouError, match="código 1"):
        r.instalar(at.Passo(), {})
