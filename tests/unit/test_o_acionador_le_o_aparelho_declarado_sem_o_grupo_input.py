"""O-ACIONADOR-LE-O-APARELHO-DECLARADO-SEM-O-GRUPO-INPUT-01 — a permissão é do aparelho declarado.

O teclado ou o pedal do «Usar como botões de» não ganha a ACL da sessão (o uaccess só cobre o
joystick), e o grupo ``input`` é proibido (item 3.3 de ``docs/history/RESPOSTAS_V1.md``): quem
está nele lê todo teclado da máquina. O nó que o sistema não deixa abrir se pede ao broker pela
identidade do aparelho, e o broker serve o fd, só de leitura, do nó daquele aparelho e de nenhum
outro, sem mexer na permissão do nó. O doctor mede só o declarado.

A régua nunca abre o ``/dev/input`` nem o ``/sys`` da máquina: os dois são pastas de mentira, e o
broker é o ``BrokerState`` de verdade sobre elas.
"""
from __future__ import annotations

import fcntl
import os
import stat
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import evdev
import pytest

from hefesto_dualsense4unix.broker import hidraw_broker as hb
from hefesto_dualsense4unix.cli import cmd_doctor
from hefesto_dualsense4unix.core import evdev_reader, system_check
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations.hidraw_broker_client import HidrawBrokerClient
from hefesto_dualsense4unix.utils import maquina

UID = 1000
#: O ``capabilities/key`` de um teclado, o de um controle (com ``BTN_SOUTH``) e o de nenhuma tecla.
TECLAS_DE_TECLADO = "fffffffffffffffe"
TECLAS_DE_CONTROLE = "7fff000000000000 0 0 0 0"
NOME = "Pedal de mentira ação"
FISICO = "usb-0000:00:14.0-9/input0"
CHAVE = maquina.chave_do_acionador("1234", "abcd", NOME, FISICO)
CONTROLE = "aabbcc000002"


class _Mesa:
    """O ``/sys/class/input`` e o ``/dev/input`` de mentira: cada nó é um arquivo comum."""

    def __init__(self, raiz: Path) -> None:
        self.sys = raiz / "sys" / "class" / "input"
        self.devices = raiz / "sys" / "devices"
        self.dev = raiz / "dev" / "input"
        self.sys.mkdir(parents=True)
        self.devices.mkdir(parents=True)
        self.dev.mkdir(parents=True)

    def no(self, evento: str, *, nome: str = NOME, fisico: str = FISICO, vendor: str = "1234",
           product: str = "abcd", teclas: str = TECLAS_DE_TECLADO, uinput: bool = False) -> str:
        casa = self.devices / ("virtual/input" if uinput else "pci0000:00/usb1") / evento
        dentro = casa / "device"
        (dentro / "id").mkdir(parents=True)
        (dentro / "capabilities").mkdir()
        (dentro / "name").write_text(nome + "\n", encoding="utf-8")
        (dentro / "phys").write_text(fisico + "\n", encoding="utf-8")
        (dentro / "id" / "vendor").write_text(vendor + "\n", encoding="utf-8")
        (dentro / "id" / "product").write_text(product + "\n", encoding="utf-8")
        (dentro / "capabilities" / "key").write_text(teclas + "\n", encoding="utf-8")
        (casa / "dev").write_text("0:0\n", encoding="ascii")
        (self.sys / evento).symlink_to(casa)
        caminho = self.dev / evento
        caminho.write_bytes(f"o nó {evento}".encode())
        caminho.chmod(0o600)
        return str(caminho)

    def ops(self) -> hb.FsAclOps:
        ops = hb.FsAclOps(dev_input_root=str(self.dev), sys_class_input=str(self.sys))
        # O arquivo comum faz o papel do char device: o resto da revalidação é a de verdade.
        ops._e_char_device = staticmethod(lambda _modo: True)
        return ops

    def broker(self) -> hb.BrokerState:
        def char(caminho: str) -> Any:
            os.stat(caminho)
            return SimpleNamespace(st_mode=stat.S_IFCHR | 0o600, st_rdev=os.makedev(0, 0))

        def validar(no: str, chave: str) -> str | None:
            motivo: str | None = hb.motivo_de_recusar_o_acionador(
                no, chave, dev_input_root=str(self.dev), sys_class_input=str(self.sys),
                stat_fn=char, lstat_fn=lambda c: os.lstat(c))
            return motivo

        return hb.BrokerState(allowed_uid=UID, ops=self.ops(), validator_acionador=validar,
                              dev_input_root=str(self.dev), sys_class_input=str(self.sys),
                              log=lambda *_a, **_k: None, sleep_fn=lambda _s: None)


def _pedir(broker: hb.BrokerState, no: str, chave: str) -> tuple[dict[str, Any], int | None]:
    import json

    pedido = json.dumps({"cmd": "open", "node": no, "acionador": chave}).encode()
    resposta, fd = broker.handle_line(1, UID, pedido)
    return dict(resposta), fd


# --- o broker ------------------------------------------------------------------------------------


def test_a_chave_do_broker_e_a_que_o_daemon_declara(tmp_path: Path) -> None:
    """O broker não importa o pacote: a conta dele tem de dar a mesma chave da declaração."""
    mesa = _Mesa(tmp_path)
    for n, (nome, fisico, vendor) in enumerate((
            (NOME, FISICO, "1234"), ("Teclado sem físico", "", "0x46d"), ("", "", ""))):
        mesa.no(f"event{n}", nome=nome, fisico=fisico, vendor=vendor)
    for aparelho in maquina.aparelhos_de_entrada(mesa.sys):
        assert hb.chave_do_acionador_no_sys(str(mesa.sys / aparelho.evento)) == aparelho.chave


def test_o_broker_serve_so_o_no_do_aparelho_declarado(tmp_path: Path) -> None:
    """O fd é só de leitura e é o do nó pedido; o nó de outro aparelho com a mesma chave pedida é
    recusado pela identidade, não pelo número do ``event``. A permissão do nó não muda."""
    mesa = _Mesa(tmp_path)
    declarado = mesa.no("event3")
    outro = mesa.no("event5", nome="Teclado da casa", fisico="usb-0000:00:14.0-1/input0")
    broker = mesa.broker()

    resposta, fd = _pedir(broker, declarado, CHAVE)
    assert resposta["ok"] and resposta["state"] == "acionador", resposta
    assert fd is not None
    try:
        assert fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY
        assert os.read(fd, 64) == b"o n\xc3\xb3 event3"
    finally:
        os.close(fd)

    resposta, fd = _pedir(broker, outro, CHAVE)
    assert fd is None
    assert resposta["error"] == "reject_nao_e_o_aparelho_declarado"

    for no in (declarado, outro):
        assert stat.S_IMODE(os.stat(no).st_mode) == 0o600, "o broker nunca abre o nó a ninguém"
        assert "system.posix_acl_access" not in os.listxattr(no)


@pytest.mark.parametrize(("como", "erro"), [
    ({"teclas": TECLAS_DE_CONTROLE}, "reject_controle_de_jogo"),
    ({"vendor": "054c"}, "reject_controle_de_jogo"),
    ({"uinput": True}, "reject_controle_de_jogo"),
    ({"teclas": "0"}, "reject_controle_de_jogo"),
])
def test_o_broker_recusa_controle_dualsense_uinput_e_no_sem_tecla(
        tmp_path: Path, como: dict[str, Any], erro: str) -> None:
    """A permissão do controle é do uaccess, a do DualSense é do broker e o uinput é do Hefesto."""
    mesa = _Mesa(tmp_path)
    no = mesa.no("event7", **como)
    chave = maquina.chave_do_acionador(como.get("vendor", "1234"), "abcd", NOME, FISICO)

    resposta, fd = _pedir(mesa.broker(), no, chave)

    assert fd is None
    assert resposta["error"] == erro


@pytest.mark.parametrize("pedido", [
    {"node": "/dev/input/../input/event3"}, {"node": "/dev/hidraw3"}, {"acionador": "nada"},
    {"acionador": None},
])
def test_o_broker_recusa_o_pedido_torto(tmp_path: Path, pedido: dict[str, Any]) -> None:
    mesa = _Mesa(tmp_path)
    no = mesa.no("event3")
    completo = {"node": no, "acionador": CHAVE, **pedido}

    resposta, fd = _pedir(mesa.broker(), completo["node"], completo["acionador"])

    assert fd is None and resposta["error"] == "reject_bad_path"


def test_o_no_que_troca_de_aparelho_entre_validar_e_abrir_sai_velho(tmp_path: Path) -> None:
    """A revalidação no fd: o ``event`` que passou a ser outro aparelho não serve."""
    mesa = _Mesa(tmp_path)
    no = mesa.no("event3")
    (mesa.sys / "event3" / "device" / "name").write_text("Outro teclado\n", encoding="utf-8")

    with pytest.raises(hb.StaleNodeError):
        mesa.ops().open_acionador(no, "event3", CHAVE)


def test_o_cliente_pede_o_acionador_pela_chave(monkeypatch: pytest.MonkeyPatch) -> None:
    pedidos: list[dict[str, Any]] = []
    leitura, escrita = os.pipe()
    os.close(escrita)

    def responder(_self: Any, pedido: dict[str, Any]) -> tuple[dict[str, Any], list[int]]:
        pedidos.append(pedido)
        return {"ok": True, "cmd": "open", "state": "acionador"}, [leitura]

    monkeypatch.setattr(HidrawBrokerClient, "_request_with_fds", responder)
    fd, _motivo = HidrawBrokerClient("/nao/existe.sock").abrir_acionador("/dev/input/event3", CHAVE)

    assert fd == leitura
    os.close(leitura)
    assert pedidos == [{"cmd": "open", "node": "/dev/input/event3", "acionador": CHAVE}]


# --- o dono da abertura --------------------------------------------------------------------------


def _recusar(caminho: str, *_: Any, **__: Any) -> Any:
    raise PermissionError(13, "Permission denied", caminho)


class _Dispositivo:
    def __init__(self, fd: int, caminho: str) -> None:
        self.fd, self.path = fd, caminho
        self.fechado = False

    def read_one(self) -> Any:
        return None

    def close(self) -> None:
        self.fechado = True
        os.close(self.fd)


@pytest.fixture
def sem_permissao(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """O evdev recusa todo nó, o ``/sys`` tem o acionador e o broker é um de mentira."""
    mesa = _Mesa(tmp_path)
    mesa.no("event3")
    monkeypatch.setattr(maquina, "RAIZ_DAS_ENTRADAS", str(mesa.sys))
    monkeypatch.setattr(evdev, "InputDevice", _recusar)
    cena: dict[str, Any] = {"mesa": mesa, "pedidos": [], "serve": True, "abertos": []}

    def broker(no: str, chave: str) -> int | None:
        cena["pedidos"].append((no, chave))
        return os.open(os.devnull, os.O_RDONLY) if cena["serve"] else None

    def embrulhar(fd: int, caminho: str) -> _Dispositivo:
        dispositivo = _Dispositivo(fd, caminho)
        cena["abertos"].append(dispositivo)
        return dispositivo

    monkeypatch.setattr(maquina, "_pedir_o_acionador_ao_broker", broker)
    monkeypatch.setattr(evdev_reader, "_input_device_do_fd", embrulhar)
    return cena


def test_o_no_que_o_sistema_recusa_se_pede_ao_broker_pela_chave(
        sem_permissao: dict[str, Any]) -> None:
    dispositivo = maquina.abrir_o_aparelho_de_entrada("event3")

    assert sem_permissao["pedidos"] == [("/dev/input/event3", CHAVE)]
    assert dispositivo is sem_permissao["abertos"][0]
    assert dispositivo.path == "/dev/input/event3"
    dispositivo.close()


def test_sem_o_broker_a_recusa_diz_a_frase_do_dono(sem_permissao: dict[str, Any]) -> None:
    sem_permissao["serve"] = False
    with pytest.raises(maquina.SemPermissaoDeLerError) as erro:
        maquina.abrir_o_aparelho_de_entrada("event3")
    assert str(erro.value) == maquina.FRASE_SEM_PERMISSAO_DE_LER
    assert erro.value.filename == "/dev/input/event3"


def test_o_broker_fora_do_ar_nao_levanta_nem_espera() -> None:
    """O socket que não existe (o da suíte) devolve None na hora, sem exceção."""
    assert maquina._pedir_o_acionador_ao_broker("/dev/input/event3", CHAVE) is None


def test_a_ponte_le_o_declarado_pelo_broker_e_a_retirada_o_fecha(
        sem_permissao: dict[str, Any]) -> None:
    """A ponte do daemon, pelo dono de verdade: declarado, abre pelo broker; fora da
    declaração, o fd se fecha (nada fica aberto no ``/dev``, nada a devolver)."""
    declarados = dict(maquina.MaquinaConfig.model_validate({"acionadores": {CHAVE: {
        "controle": CONTROLE, "teclas": {"28": "cross"}}}}).acionadores)
    ponte = gp.PonteDosAcionadores(raiz=sem_permissao["mesa"].sys, relogio=lambda: 0.0)

    ponte.andar(declarados, lambda: False)
    assert sem_permissao["pedidos"] == [("/dev/input/event3", CHAVE)]
    (dispositivo,) = sem_permissao["abertos"]
    assert not dispositivo.fechado

    ponte.andar({}, lambda: False)
    assert dispositivo.fechado


# --- a frase -------------------------------------------------------------------------------------

_GRUPO = "usermod -aG " + "input"


def test_a_frase_manda_ao_doctor_e_a_grupo_nenhum() -> None:
    frase = maquina.FRASE_SEM_PERMISSAO_DE_LER
    assert "doctor" in frase
    assert "grupo" not in frase and "usermod" not in frase and "sudo" not in frase


def test_nenhum_codigo_nem_teste_ensina_a_entrar_no_grupo_input() -> None:
    raiz = Path(__file__).resolve().parents[2]
    achados = [
        f"{arquivo.relative_to(raiz)}:{n}"
        for pasta in ("src", "tests")
        for arquivo in sorted((raiz / pasta).rglob("*.py"))
        for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1)
        if _GRUPO in linha
    ]
    assert achados == []


# --- o doctor ------------------------------------------------------------------------------------


def _declaracao() -> dict[str, Any]:
    return dict(maquina.MaquinaConfig.model_validate({"acionadores": {CHAVE: {
        "nome": NOME, "controle": CONTROLE, "teclas": {"28": "cross"}}}}).acionadores)


def test_sem_declaracao_o_doctor_da_info_e_nao_abre_nada(tmp_path: Path) -> None:
    """O teclado da casa que recusa não é pergunta de ninguém: sem declaração, nada se abre."""
    mesa = _Mesa(tmp_path)
    mesa.no("event5", nome="Teclado da casa")

    def abrir(evento: str) -> Any:
        raise AssertionError(f"sem declaração, abriu {evento}")

    linha = system_check.permissao_de_ler_a_entrada(raiz=str(mesa.sys), abrir=abrir,
                                                     declarados={})

    assert linha == ("[INFO]", system_check.LINHA_SEM_ACIONADOR_DECLARADO)
    assert cmd_doctor._gravidade_das_linhas([linha]) == 0


def test_o_doctor_sem_declaracao_no_disco_sai_com_zero() -> None:
    """O bloco do doctor, pelo ``maquina.json`` do lar da suíte, que não declara nada."""
    assert cmd_doctor._print_bloco_entrada() == 0


def test_o_declarado_que_recusa_da_warn_com_a_frase(tmp_path: Path) -> None:
    mesa = _Mesa(tmp_path)
    mesa.no("event3")
    mesa.no("event5", nome="Teclado da casa")
    abertos: list[str] = []

    def abrir(evento: str) -> Any:
        abertos.append(evento)
        raise maquina.SemPermissaoDeLerError(13, maquina.FRASE_SEM_PERMISSAO_DE_LER, evento)

    tag, mensagem = system_check.permissao_de_ler_a_entrada(
        raiz=str(mesa.sys), abrir=abrir, declarados=_declaracao())

    assert tag == "[WARN]"
    assert NOME in mensagem and maquina.FRASE_SEM_PERMISSAO_DE_LER in mensagem
    assert abertos == ["event3"], "só o declarado se mede"
    assert cmd_doctor._gravidade_das_linhas([(tag, mensagem)]) > 0


def test_o_declarado_que_abre_da_ok_e_fecha_na_hora(tmp_path: Path) -> None:
    mesa = _Mesa(tmp_path)
    mesa.no("event3")
    fechados: list[bool] = []

    def abrir(_evento: str) -> Any:
        return SimpleNamespace(close=lambda: fechados.append(True))

    linha = system_check.permissao_de_ler_a_entrada(
        raiz=str(mesa.sys), abrir=abrir, declarados=_declaracao())

    assert linha == ("[ OK ]", system_check.LINHA_LE_A_ENTRADA)
    assert fechados == [True], "o doctor nunca segura o aparelho aberto"


def test_o_declarado_fora_da_porta_da_info(tmp_path: Path) -> None:
    mesa = _Mesa(tmp_path)
    mesa.no("event5", nome="Teclado da casa")

    linha = system_check.permissao_de_ler_a_entrada(
        raiz=str(mesa.sys), abrir=_recusar, declarados=_declaracao())

    assert linha == ("[INFO]", system_check.LINHA_ACIONADOR_FORA)
