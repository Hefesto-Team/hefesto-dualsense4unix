"""O rádio parado não acorda com uma pergunta (07/11/2026).

``org.bluez`` é ativável, e toda pergunta ao nome sem dono sobe o ``bluetoothd``: quem para o
Bluetooth de propósito o via voltar em até 2 min. O ``--auto-start=no`` do ``busctl`` só vale em
``call`` e ``emit``; ``tree``, ``get-property``, ``introspect`` e ``set-property`` o ignoram (medido
no systemd 255). A guarda é o ``busctl status``, que não ativa, e o ``NO_AUTO_START`` do Gio.

O barramento daqui é um ``dbus-daemon`` particular, com o ``org.bluez`` ativável de mentira que
conta as ativações, e o ``busctl`` é o de verdade, preso a ele por um envelope no ``PATH``.

Entre uma pergunta e outra o rádio pode parar: ``_o_radio_para_no_meio`` usa um ``busctl`` de
mentira que diz «de pé» até um verbo escolhido e anota o que vier depois.

MORDIDA: tirar o ``_bluez_de_pe`` de qualquer ponto dos três scripts, o ``_o_bluez_tem_dono`` do
``busctl``, o ``--auto-start=no`` do ``Connect`` ou o ``NO_AUTO_START`` do ``BarramentoGio``
reprova.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import diario_do_radio
from tests.unit import bluez_de_mentira as bm
from tests.unit.test_a_captura_nao_acorda_o_portal_antes_da_sessao import (
    _ATIVADOR,
    _CONFIG,
    _SERVICO,
    Atendente,
)

RAIZ = Path(__file__).resolve().parents[2]
ATIVO = RAIZ / "scripts" / "bt_active_mode.sh"
VIGIA = RAIZ / "scripts" / "bt_health_watchdog.sh"
PONTE = RAIZ / "scripts" / "bt_ponte_privilegiada.sh"

_ADAPTADOR = "/org/bluez/hci9"
_APARELHO = f"{_ADAPTADOR}/dev_AA_BB_CC_00_00_22"
_ENDERECO = "AA:BB:CC:00:00:11"
_CONTROLE = "AA:BB:CC:00:00:22"
_FILHOS = {"/": "org", "/org": "bluez", "/org/bluez": "hci9"}

_ha_o_barramento = pytest.mark.skipif(
    shutil.which("dbus-daemon") is None or shutil.which("busctl") is None,
    reason="sem dbus-daemon ou sem busctl, não há barramento particular")


def _executavel(arquivo: Path, corpo: str) -> None:
    arquivo.write_text(f"#!/usr/bin/env bash\n{corpo}", encoding="utf-8")
    arquivo.chmod(0o755)


class Banca:
    """O barramento particular, o ``busctl`` preso a ele e o disco de mentira dos scripts."""

    def __init__(self, pasta: Path) -> None:
        self.pasta = pasta
        servicos = pasta / "ativaveis"
        servicos.mkdir()
        self.marca = pasta / "ativacoes"
        ativador = pasta / "ativador.sh"
        ativador.write_text(_ATIVADOR.format(contagem=self.marca), encoding="utf-8")
        (servicos / "org.bluez.service").write_text(
            _SERVICO.format(nome=bd.SERVICO, ativador=ativador), encoding="utf-8")
        config = pasta / "barramento.conf"
        config.write_text(_CONFIG.format(soquete=pasta / "barramento", servicos=servicos),
                          encoding="utf-8")
        self._processo = subprocess.Popen(
            ["dbus-daemon", "--config-file", str(config), "--print-address", "--nofork",
             "--nopidfile"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        assert self._processo.stdout is not None
        self.endereco = self._processo.stdout.readline().strip()
        assert self.endereco, "o dbus-daemon particular não disse o endereço"
        self.binarios = pasta / "bin"
        self.binarios.mkdir()
        real = shutil.which("busctl")
        _executavel(self.binarios / "busctl", f'exec "{real}" --address="{self.endereco}" "$@"\n')
        _executavel(self.binarios / "id", "echo 0\n")
        _executavel(self.binarios / "logger", "exit 0\n")
        _executavel(self.binarios / "sleep", "exit 0\n")
        _executavel(self.binarios / "journalctl", "exit 0\n")
        _executavel(self.binarios / "systemctl", "exit 0\n")
        for ausente in ("btmgmt", "hciconfig", "hcitool", "bluetoothctl"):
            _executavel(self.binarios / ausente, "exit 1\n")
        for nome in ("sys/hci9", "hid", "usb", "hdrv", "udrv", "rebind", "lib/AA:BB:CC:00:00:11"):
            (pasta / nome).mkdir(parents=True)
        bond = pasta / "lib" / _ENDERECO / "AA:BB:CC:00:00:22"
        bond.mkdir()
        (bond / "info").write_text(
            "[General]\nName=Pro Controller\n"
            "Services=00001124-0000-1000-8000-00805f9b34fb;\n", encoding="utf-8")

    def ativacoes(self) -> int:
        if not self.marca.exists():
            return 0
        return len(self.marca.read_text(encoding="utf-8").splitlines())

    def ambiente(self) -> dict[str, str]:
        pasta = self.pasta
        ambiente = {
            **os.environ,
            "PATH": f"{self.binarios}{os.pathsep}{os.environ['PATH']}",
            "HEFESTO_BT_BIN": str(self.binarios),
            "HEFESTO_BT_LOG_DEST": "none",
            "HEFESTO_BT_SRC": str(pasta / "lib"),
            "HEFESTO_BT_LIB": str(pasta / "lib"),
            "HEFESTO_BT_STAMP_DIR": str(pasta / "stamps"),
            "HEFESTO_SYS_BLUETOOTH": str(pasta / "sys"),
            "HEFESTO_HIDRAW_ROOT": str(pasta / "hid"),
            "HEFESTO_HID_DEVICES_DIR": str(pasta / "hid"),
            "HEFESTO_HID_DRIVERS_DIR": str(pasta / "hdrv"),
            "HEFESTO_USB_DEVICES_DIR": str(pasta / "usb"),
            "HEFESTO_USB_DRIVERS_DIR": str(pasta / "udrv"),
            "HEFESTO_REBIND_STAMP_DIR": str(pasta / "rebind"),
            "HEFESTO_RADIO_TRAVA": str(pasta / "radio.lock"),
            "HEFESTO_RADIO_DIARIO_ROOT": str(pasta / "diario.jsonl"),
        }
        ambiente.pop("SUDO_UID", None)
        ambiente.pop("SUDO_USER", None)
        return ambiente

    def rodar(
        self, script: Path, *argumentos: str, entrada: str = ""
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["bash", str(script), *argumentos], capture_output=True, text=True,
                              input=entrada, timeout=60, check=False, env=self.ambiente())

    def fechar(self) -> None:
        self._processo.terminate()
        self._processo.wait(timeout=5)


class BluezDePe(Atendente):
    """O dono do ``org.bluez``, com um adaptador só: ``tree``, ``get-property`` e a foto."""

    def __init__(self, endereco: str) -> None:
        super().__init__(endereco, bd.SERVICO)

    def responder(self, mensagem: Any) -> None:
        from jeepney import HeaderFields, new_method_return

        campos = mensagem.header.fields
        metodo = campos.get(HeaderFields.member)
        if metodo == "Introspect":
            filho = _FILHOS.get(campos.get(HeaderFields.path, ""), "")
            no = f'<node name="{filho}"/>' if filho else ""
            self._conexao.send(new_method_return(mensagem, "s", (f"<node>{no}</node>",)))
        elif metodo == "Get":
            self._conexao.send(new_method_return(mensagem, "v", (("s", _ENDERECO),)))
        else:
            objetos = {_ADAPTADOR: {bd.ADAPTADOR: {"Address": ("s", _ENDERECO)}}}
            self._conexao.send(new_method_return(mensagem, "a{oa{sa{sv}}}", (objetos,)))


@pytest.fixture
def banca(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Banca]:
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(tmp_path / "radio.lock"))
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(tmp_path / "radio-diario.jsonl"))
    viva = Banca(tmp_path)
    monkeypatch.setenv("PATH", f"{viva.binarios}{os.pathsep}{os.environ['PATH']}")
    try:
        yield viva
    finally:
        viva.fechar()


@_ha_o_barramento
@pytest.mark.parametrize("pergunta", [
    lambda leitor: leitor.caminhos(),
    lambda leitor: leitor.propriedade(_ADAPTADOR, bd.ADAPTADOR, "Address"),
    lambda leitor: leitor.adaptadores(),
    lambda _leitor: bd.busctl(["introspect", bd.SERVICO, _ADAPTADOR]),
], ids=["tree", "get-property", "adaptadores", "introspect"])
def test_sem_o_dono_a_leitura_do_produto_nao_ativa(banca: Banca, pergunta: Any) -> None:
    assert pergunta(bd.PeloBusctl()) is None
    assert banca.ativacoes() == 0


@_ha_o_barramento
@pytest.mark.parametrize("escrita", [
    lambda leitor: leitor.conectar(_APARELHO),
    lambda leitor: leitor.confiar(_APARELHO),
], ids=["call", "set-property"])
def test_sem_o_dono_a_escrita_do_produto_nao_ativa(
    banca: Banca, monkeypatch: pytest.MonkeyPatch, escrita: Any
) -> None:
    monkeypatch.setattr(bd, "a_suite_esta_rodando", lambda: False)
    assert not escrita(bd.PeloBusctl()).feita
    assert banca.ativacoes() == 0


@_ha_o_barramento
@pytest.mark.parametrize(("escrita", "pedido"), [
    (lambda leitor: leitor.conectar(_APARELHO), f"{bd.APARELHO}.Connect"),
    (lambda leitor: leitor.confiar(_APARELHO), f"{bd.PROPRIEDADES}.Set"),
], ids=["call", "set-property"])
def test_com_o_dono_a_escrita_chega_a_ele(
    banca: Banca, monkeypatch: pytest.MonkeyPatch, escrita: Any, pedido: str
) -> None:
    monkeypatch.setattr(bd, "a_suite_esta_rodando", lambda: False)
    bluez = BluezDePe(banca.endereco)
    try:
        assert escrita(bd.PeloBusctl()).feita
        assert pedido in bluez.pedidos
    finally:
        bluez.fechar()
    assert banca.ativacoes() == 0


def test_a_guarda_e_o_verbo_dividem_o_mesmo_teto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pasta = tmp_path / "bin"
    pasta.mkdir()
    _executavel(pasta / "busctl", "sleep 0.3\necho resposta\n")
    monkeypatch.setenv("PATH", f"{pasta}{os.pathsep}{os.environ['PATH']}")
    assert bd.busctl(["tree", bd.SERVICO], espera=0.45) is None


@_ha_o_barramento
def test_com_o_dono_a_leitura_segue_igual(banca: Banca) -> None:
    bluez = BluezDePe(banca.endereco)
    try:
        leitor = bd.PeloBusctl()
        assert _ADAPTADOR in (leitor.caminhos() or ())
        assert leitor.propriedade(_ADAPTADOR, bd.ADAPTADOR, "Address") == _ENDERECO
        saida = banca.rodar(PONTE, "adaptadores")
    finally:
        bluez.fechar()
    assert saida.returncode == 0, saida.stderr
    assert saida.stdout.split("\t")[0] == _ENDERECO
    assert banca.ativacoes() == 0


@pytest.mark.skipif(not bm.ha_dbus_daemon(), reason="sem dbus-daemon ou sem Gio nesta máquina")
def test_pelo_gio_a_foto_nao_ativa_e_o_bluez_que_volta_e_visto(banca: Banca) -> None:
    barramento = bd.BarramentoGio(banca.endereco)
    assert barramento.abrir()
    vivo = bd.DonoVivo(barramento)
    bluez = None
    try:
        assert vivo.ligar()
        assert vivo.caminhos() is None
        assert not barramento.chamar(bd.SERVICO, "/", bd.OBJETOS, "GetManagedObjects", "", (),
                                     espera=2.0).feita
        assert banca.ativacoes() == 0
        bluez = BluezDePe(banca.endereco)
        assert bm.esperar(lambda: _ADAPTADOR in (vivo.caminhos() or ()))
        assert banca.ativacoes() == 0
    finally:
        vivo.fechar()
        if bluez is not None:
            bluez.fechar()


@_ha_o_barramento
@pytest.mark.parametrize(("script", "argumentos"), [
    (ATIVO, ("--quiet",)),
    (VIGIA, ("--sdp-cache-only",)),
    (VIGIA, ()),
    (PONTE, ("adaptadores",)),
], ids=["modo-ativo", "vigia-sdp", "vigia", "ponte"])
def test_sem_o_dono_os_scripts_nao_ativam(
    banca: Banca, script: Path, argumentos: tuple[str, ...]
) -> None:
    saida = banca.rodar(script, *argumentos)
    assert saida.returncode == 0, saida.stderr
    assert banca.ativacoes() == 0


@_ha_o_barramento
def test_sem_o_dono_e_sem_o_sysfs_o_modo_ativo_nao_ativa(banca: Banca) -> None:
    (banca.pasta / "sys" / "hci9").rmdir()
    saida = banca.rodar(ATIVO, "--quiet")
    assert saida.returncode == 0, saida.stderr
    assert banca.ativacoes() == 0


@_ha_o_barramento
def test_sem_o_dono_o_gesto_da_ponte_recusa_sem_ativar(banca: Banca) -> None:
    saida = banca.rodar(PONTE, "parear", entrada=f"{_ENDERECO}\n{_CONTROLE}\n")
    assert saida.returncode != 0
    assert "não está na mesa" in saida.stderr
    assert banca.ativacoes() == 0


def _o_radio_para_no_meio(
    banca: Banca, parar_em: str, respostas: dict[str, str]
) -> tuple[list[str], list[str]]:
    """Põe o ``busctl`` de mentira: a primeira lista devolvida guarda todo verbo, e a segunda, o
    que veio com o rádio já parado."""
    todos, depois, parou = (banca.pasta / nome for nome in ("todos", "depois", "parou"))
    casos = "".join(f"    *{shlex.quote(chave)}*) echo {shlex.quote(valor)} ;;\n"
                    for chave, valor in respostas.items())
    _executavel(banca.binarios / "busctl", f'''
if [[ "$1" == status ]]; then [[ ! -e "{parou}" ]]; exit; fi
printf '%s\\n' "$*" >> "{todos}"
[[ -e "{parou}" ]] && printf '%s\\n' "$*" >> "{depois}"
case "$*" in
{casos}esac
[[ "$*" == *{shlex.quote(parar_em)}* ]] && : > "{parou}"
exit 0
''')
    return todos, depois


def _linhas(arquivo: Path) -> list[str]:
    return arquivo.read_text(encoding="utf-8").splitlines() if arquivo.exists() else []


_ARVORE = {"tree": f"{_ADAPTADOR}\n{_APARELHO}"}
_DO_CONTROLE_SEM_CONFIANCA = {
    **_ARVORE, "Connected": "b false", "Bonded": "b true", "Trusted": "b false", "Paired": "b true",
    "Class": "u 1288", "Appearance": "q 964",
}


def test_parado_no_meio_o_vigia_nao_aplica_a_confianca(banca: Banca) -> None:
    _, depois = _o_radio_para_no_meio(banca, "Appearance", _DO_CONTROLE_SEM_CONFIANCA)
    saida = banca.rodar(VIGIA)
    assert saida.returncode == 0, saida.stderr
    assert "falha ao aplicar Trusted=true" in saida.stdout
    assert not [linha for linha in _linhas(depois) if linha.startswith("set-property")]


def test_parado_no_meio_o_modo_ativo_nao_escreve_o_alias(banca: Banca) -> None:
    respostas = {**_ARVORE, "Device1 Alias": 's "Pro Controller"', "Adapter1 Alias": 's "Rádio"',
                 "Address": f's "{_ENDERECO}"'}
    todos, depois = _o_radio_para_no_meio(banca, "Adapter1 Alias", respostas)
    saida = banca.rodar(ATIVO, "--quiet")
    assert saida.returncode == 0, saida.stderr
    assert any("Adapter1 Alias" in linha for linha in _linhas(todos))
    assert not [linha for linha in _linhas(depois) if linha.startswith("set-property")]


@pytest.mark.parametrize(("script", "argumentos", "entrada", "parar_em", "verbo"), [
    (PONTE, ("descobrir", "1"), f"{_ENDERECO}\n", "Adapter1 Address", "tree"),
    (PONTE, ("parear",), f"{_ENDERECO}\n{_CONTROLE}\n", "Adapter1 Address", "get-property"),
    (ATIVO, ("--quiet",), "", "Adapter1 Address", "tree"),
    (ATIVO, ("--quiet",), "", "Connected", "tree"),
    (VIGIA, (), "", "tree", "get-property"),
], ids=["descobrir", "parear", "nintendo", "nome-do-controle", "vigia"])
def test_parado_no_meio_ninguem_pergunta_mais(
    banca: Banca, script: Path, argumentos: tuple[str, ...], entrada: str, parar_em: str, verbo: str
) -> None:
    respostas = {**_ARVORE, "Adapter1 Address": f's "{_ENDERECO}"', "Connected": "b true"}
    todos, depois = _o_radio_para_no_meio(banca, parar_em, respostas)
    banca.rodar(script, *argumentos, entrada=entrada)
    assert any(parar_em in linha for linha in _linhas(todos))
    assert not [linha for linha in _linhas(depois) if linha.startswith(verbo)]


def test_o_connect_do_vigia_nao_ativa(banca: Banca) -> None:
    todos, _ = _o_radio_para_no_meio(banca, "nunca", {**_ARVORE, "Connected": "b true"})
    saida = banca.rodar(VIGIA, "--sdp-cache-only")
    assert saida.returncode == 0, saida.stderr
    chamadas = [linha for linha in _linhas(todos) if linha.startswith("call")]
    assert chamadas and all("--auto-start=no" in linha for linha in chamadas)


def test_a_guarda_mora_antes_de_toda_leitura_dos_scripts() -> None:
    for script in (ATIVO, VIGIA, PONTE):
        texto = script.read_text(encoding="utf-8")
        assert "_bluez_de_pe()" in texto, script.name
        assert "if command -v busctl" not in texto, script.name
