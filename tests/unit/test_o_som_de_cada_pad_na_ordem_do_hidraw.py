"""O som de cada pad nasce na ordem do pad — O-SOM-DE-CADA-PAD-NA-ORDEM-DO-HIDRAW-01.

O par pad → nó de som já era por identidade (a âncora do gadget do aparelho
vence tudo); a ORDEM em que os nós nascem não era: o laço do
``AltoFalanteSubsystem._casar_as_pontes`` andava na ordem do ENDEREÇO dos
controles, e o Wine dá o identificador canônico da Sony ao primeiro DualSense
da lista (patch 0187; o nosso nó não tem ``alsa.card`` para o 0189 reordenar).

A régua monta um ``/sys`` de mentira (âncoras emprestadas e o gadget de cada
pad sob o ``vhci_hcd``), o registro do gadget do próprio ``pad_usb`` e um
servidor de som de mentira, e mede, com dois e com quatro pads, no cabo e no
rádio: cada nó aponta para o gadget do SEU pad, nenhum gadget serve a dois nós,
e os nós nascem na ordem dos assentos. O controle que sai e volta renasce no
fim da lista; sem jogo aberto, os que ficaram fora da ordem renascem atrás
dele, e com jogo aberto nenhum nó é recriado.

O que só a bancada prova (qual endpoint o jogo abre para cada jogador) é do
ensaio ``scripts/ensaios/o_som_de_cada_pad_no_wine.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

import sys

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as dba
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.integrations import pad_usb
from hefesto_dualsense4unix.integrations.haptica_do_cabo import HapticaDoCabo

#: Os quatro controles, da faixa sintética, NA ORDEM DO ENDEREÇO.
_U = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04")
#: O assento de cada um: o contrário do endereço, para a ordem velha reprovar.
_ASSENTO = {_U[0]: 4, _U[1]: 3, _U[2]: 2, _U[3]: 1}


def _escrever(caminho: Path, texto: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto, encoding="utf-8")


def _usb_device(sysfs: Path, real: Path, *, busnum: str, devnum: int, serial: str = "") -> None:
    """Um ``usb_device`` com a interface ``:1.0`` e o atalho em ``bus/usb/devices``."""
    interface = real / f"{real.name}:1.0"
    _escrever(interface / "uevent", "DEVTYPE=usb_interface\n")
    for arquivo, valor in (("busnum", busnum), ("devnum", str(devnum)), ("product", "x")):
        _escrever(real / arquivo, f"{valor}\n")
    if serial:
        _escrever(real / "serial", f"{serial}\n")
    atalhos = sysfs / "bus" / "usb" / "devices"
    atalhos.mkdir(parents=True, exist_ok=True)
    (atalhos / real.name).symlink_to(real)


def _interface_do_gadget(n: int) -> str:
    return f"/devices/platform/vhci_hcd.0/usb9/9-{n}/9-{n}:1.0"


class _Servidor:
    """O ``pipewire-pulse`` de mentira: módulos com índice que só cresce."""

    def __init__(self) -> None:
        self.modulos: dict[str, tuple[str, str]] = {}
        self.cargas: list[str] = []
        self.quedas: list[str] = []
        self.jogo_em: set[str] = set()
        self._proximo = 500

    def lista(self) -> list[tuple[str, str]]:
        """``(nome, sysfs.path)`` na ordem da lista do servidor (a do índice)."""
        return [self.modulos[m] for m in sorted(self.modulos, key=int)]

    def __call__(self, argv: list[str]) -> str | None:
        if argv[:4] == ["pactl", "list", "short", "modules"]:
            return "\n".join(
                f"{mid}\tmodule-null-sink\tsink_name={nome} format=float32le "
                f'sink_properties="device.bus=usb sysfs.path={caminho} priority.session=0"\t'
                for mid, (nome, caminho) in self.modulos.items()
            ) or "1\tmodule-native-protocol-unix\t\t"
        if argv[:2] == ["pactl", "load-module"]:
            nome = next(a.split("=", 1)[1] for a in argv if a.startswith("sink_name="))
            props = next(a for a in argv if a.startswith("sink_properties="))
            caminho = next(
                p.split("=", 1)[1] for p in props.split() if p.startswith("sysfs.path=")
            )
            self._proximo += 1
            self.modulos[str(self._proximo)] = (nome, caminho)
            self.cargas.append(nome)
            return f"{self._proximo}\n"
        if argv[:2] == ["pactl", "unload-module"]:
            if self.modulos.pop(argv[2], None) is not None:
                self.quedas.append(argv[2])
            return ""
        if argv[:4] == ["pactl", "list", "short", "sinks"]:
            return "\n".join(
                f"{mid}\t{nome}\tPipeWire\tfloat32le 4ch 48000Hz\tRUNNING"
                for mid, (nome, _c) in self.modulos.items()
            )
        if argv[:4] == ["pactl", "list", "short", "sink-inputs"]:
            return "\n".join(
                f"9{mid}\t{mid}\t12\tprotocol-native.c\tfloat32le 4ch 48000Hz"
                for mid, (nome, _c) in self.modulos.items()
                if nome in self.jogo_em
            )
        return None


class _Lacos:
    def esta_ligado(self, _chave: str) -> bool:
        return False

    def ligar(self, _chave: str, **_kw: Any) -> bool:
        return True

    def desligar(self, _chave: str) -> bool:
        return False


class _PonteDeMentira:
    criadas: ClassVar[list[Any]] = []

    def __init__(self, **kw: Any) -> None:
        self.uniq = kw["uniq"]
        self.kw = kw
        self.motivo = ""
        self.desceu = False

    def subir(self) -> bool:
        return True

    def descer(self, **_: Any) -> bool:
        self.desceu = True
        return True

    def esta_de_pe(self) -> bool:
        return not self.desceu

    @property
    def leva(self) -> bool:
        return False


@dataclass
class _Controle:
    uniq: str
    transporte: str
    caminho: str = "/dev/hidraw9"


@dataclass
class _Mesa:
    sub: Any
    servidor: _Servidor
    sysfs: Path
    emprestadas: set[str]
    assentos: dict[str, int] = field(default_factory=dict)
    jogo: bool = False

    def volta(self, uniqs: tuple[str, ...], transporte: str) -> None:
        self.sub._casar_as_pontes([_Controle(u, transporte) for u in uniqs])

    def gadget(self, uniq: str) -> None:
        """O pad deste controle subiu no gadget: o registro do ``pad_usb`` o diz."""
        pad_usb.registrar_gadget(uniq, _interface_do_gadget(_U.index(uniq) + 1))

    def ordem_no_servidor(self) -> list[str]:
        nomes = {eh.nome_do_endpoint(u): u for u in _U}
        return [nomes[n] for n, _c in self.servidor.lista()]

    def ancora_de(self, uniq: str) -> str:
        nome = eh.nome_do_endpoint(uniq)
        (caminho,) = [c for n, c in self.servidor.modulos.values() if n == nome]
        return caminho


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _Mesa:
    from hefesto_dualsense4unix.integrations import hidraw_broker_client as broker

    monkeypatch.delenv(eh.INTERRUPTOR_DA_ORDEM_DOS_NOS, raising=False)
    sysfs = tmp_path / "sys"
    emprestadas: set[str] = set()
    for i in range(1, 6):
        real = sysfs / "devices" / "pci0000:00" / "usb3" / f"3-{i}"
        _usb_device(sysfs, real, busnum="3", devnum=10 + i)
        emprestadas.add(f"/devices/pci0000:00/usb3/3-{i}/3-{i}:1.0")
    for n in range(1, 5):
        real = sysfs / "devices" / "platform" / "vhci_hcd.0" / "usb9" / f"9-{n}"
        _usb_device(
            sysfs, real, busnum="9", devnum=n + 1,
            serial=pad_usb.serial_do_pad(f"02:fe:00:00:00:0{n}"),
        )
    servidor = _Servidor()
    sub = mod.AltoFalanteSubsystem(gerenciador=None, fonte_de_controles=list)
    sub._cabo = HapticaDoCabo(lacos=_Lacos(), conferir=lambda _no: None)
    m = _Mesa(sub=sub, servidor=servidor, sysfs=sysfs, emprestadas=emprestadas)
    monkeypatch.setattr(af, "_rodar", servidor)
    monkeypatch.setattr(eh, "RAIZ_DO_SYSFS", sysfs)
    monkeypatch.setattr(pad_usb, "_INTERFACE_DO_APARELHO", {})
    monkeypatch.setattr(dba, "_NUMERADOR_DE_ASSENTO", lambda u: m.assentos.get(u))
    monkeypatch.setattr(af, "PonteDeSomPorRadio", _PonteDeMentira)
    monkeypatch.setattr(af, "garantir_motores_audiveis", lambda *_a, **_k: False)
    monkeypatch.setattr(af, "sink_do_controle", lambda *_a, **_k: "")
    monkeypatch.setattr(
        af, "fonte_do_monitor_do_no", lambda no, **_kw: ((lambda _n: b""), f"g:{no}", "")
    )
    monkeypatch.setattr(broker, "abrir_hidraw", lambda no, **_: type("N", (), {"fd": 7})())
    monkeypatch.setattr(mod.AltoFalanteSubsystem, "_quem_o_jogo_le", lambda self, c: set())
    monkeypatch.setattr(mod.AltoFalanteSubsystem, "_quem_mexeu_na_partida", lambda self, c: set())
    monkeypatch.setattr(mod.AltoFalanteSubsystem, "_ha_jogo_aberto", lambda self: m.jogo)
    return m


def _por_assento(uniqs: tuple[str, ...], assentos: dict[str, int]) -> list[str]:
    return sorted(uniqs, key=lambda u: assentos[u])


# A conta pura


def _assento_de(tabela: dict[str, int]) -> Any:
    return lambda marca: tabela.get(marca)


def test_a_ordem_de_nascimento_e_a_dos_assentos() -> None:
    tabela = {"APARELHOcc": 3, "APARELHOdd": 1, "APARELHOee": 2}
    na_ordem, refazer = eh.plano_da_ordem(tabela, _assento_de(tabela))
    assert na_ordem == ["APARELHOdd", "APARELHOee", "APARELHOcc"]
    assert refazer == []


def test_quem_nao_tem_assento_nasce_por_ultimo() -> None:
    tabela = {"APARELHOcc": 2, "APARELHOdd": 1}
    na_ordem, _ = eh.plano_da_ordem([*tabela, "APARELHOaa"], _assento_de(tabela))
    assert na_ordem == ["APARELHOdd", "APARELHOcc", "APARELHOaa"]


def test_o_que_volta_faz_renascer_so_quem_ficou_fora_da_ordem() -> None:
    """P1, P3 e P4 de pé; o P2 volta: P3 e P4 renascem atrás dele, o P1 fica."""
    p = {"APARELHOaa": 1, "APARELHObb": 2, "APARELHOcc": 3, "APARELHOdd": 4}
    no_servidor = {"APARELHOaa": 10, "APARELHOcc": 11, "APARELHOdd": 12}
    na_ordem, refazer = eh.plano_da_ordem(p, _assento_de(p), no_servidor)
    assert na_ordem == ["APARELHOaa", "APARELHObb", "APARELHOcc", "APARELHOdd"]
    assert refazer == ["APARELHOcc", "APARELHOdd"]
    assert eh.plano_da_ordem(p, _assento_de(p), no_servidor, refazer=False)[1] == []


def test_a_lista_ja_em_ordem_nao_renasce() -> None:
    p = {"APARELHOaa": 1, "APARELHObb": 2, "APARELHOcc": 3}
    no_servidor = {"APARELHOaa": 10, "APARELHObb": 11}
    assert eh.plano_da_ordem(p, _assento_de(p), no_servidor)[1] == []


def test_o_interruptor_escolhe_entre_as_tres_e_ignora_o_resto() -> None:
    chave = eh.INTERRUPTOR_DA_ORDEM_DOS_NOS
    assert eh.ordem_dos_nos({}) == eh.ORDEM_DOS_NOS == eh.ORDEM_PELO_ASSENTO
    assert eh.ordem_dos_nos({chave: "endereco"}) == eh.ORDEM_PELO_ENDERECO
    assert eh.ordem_dos_nos({chave: " Assento-Sem-Refazer "}) == eh.ORDEM_PELO_ASSENTO_SEM_REFAZER
    assert eh.ordem_dos_nos({chave: "qualquer"}) == eh.ORDEM_DOS_NOS


# A volta do daemon, com dois e com quatro pads, no cabo e no rádio


@pytest.mark.parametrize("transporte", ["usb", "bluetooth"])
@pytest.mark.parametrize("quantos", [2, 4])
def test_cada_no_nasce_no_gadget_do_seu_pad_na_ordem_dos_assentos(
    mesa: _Mesa, quantos: int, transporte: str
) -> None:
    uniqs = _U[:quantos]
    mesa.assentos = {u: _ASSENTO[u] - (4 - quantos) for u in uniqs}
    for u in uniqs:
        mesa.gadget(u)
    mesa.volta(uniqs, transporte)
    assert mesa.servidor.cargas == [
        eh.nome_do_endpoint(u) for u in _por_assento(uniqs, mesa.assentos)
    ], "os nós nasceram fora da ordem dos assentos"
    assert mesa.ordem_no_servidor() == _por_assento(uniqs, mesa.assentos)
    for u in uniqs:
        assert mesa.ancora_de(u) == _interface_do_gadget(_U.index(u) + 1), (
            f"o nó do controle {mesa.assentos[u]} não aponta para o gadget do pad dele"
        )
    caminhos = [mesa.ancora_de(u) for u in uniqs]
    assert len(set(caminhos)) == quantos, f"um gadget serve a dois nós: {caminhos}"


def test_sem_o_gadget_o_no_volta_a_ancora_emprestada(mesa: _Mesa) -> None:
    uniqs = _U[:2]
    mesa.assentos = {_U[0]: 2, _U[1]: 1}
    mesa.gadget(_U[1])
    mesa.volta(uniqs, "bluetooth")
    assert mesa.ancora_de(_U[1]) == _interface_do_gadget(2)
    assert mesa.ancora_de(_U[0]) in mesa.emprestadas
    assert mesa.ancora_de(_U[0]) != mesa.ancora_de(_U[1])


def _sai_e_volta(mesa: _Mesa, transporte: str) -> tuple[list[str], list[str]]:
    """Os quatro na mesa; o P2 sai e volta. Devolve a ordem antes e depois."""
    mesa.assentos = {u: n for n, u in enumerate(_U, start=1)}
    for u in _U:
        mesa.gadget(u)
    mesa.volta(_U, transporte)
    antes = mesa.ordem_no_servidor()
    sem_o_p2 = (_U[0], _U[2], _U[3])
    mesa.volta(sem_o_p2, transporte)
    assert eh.nome_do_endpoint(_U[1]) not in {n for n, _c in mesa.servidor.lista()}
    mesa.volta(_U, transporte)
    return antes, mesa.ordem_no_servidor()


@pytest.mark.parametrize("transporte", ["usb", "bluetooth"])
def test_o_controle_que_volta_retoma_o_lugar_sem_jogo_aberto(
    mesa: _Mesa, transporte: str
) -> None:
    antes, depois = _sai_e_volta(mesa, transporte)
    assert antes == list(_U)
    assert depois == list(_U), "o nó do P2 renasceu no fim da lista"
    for u in _U:
        assert mesa.ancora_de(u) == _interface_do_gadget(_U.index(u) + 1)


def test_com_jogo_aberto_nenhum_no_renasce(mesa: _Mesa) -> None:
    mesa.assentos = {u: n for n, u in enumerate(_U, start=1)}
    for u in _U:
        mesa.gadget(u)
    mesa.volta(_U, "usb")
    mesa.volta((_U[0], _U[2], _U[3]), "usb")
    quedas = list(mesa.servidor.quedas)
    mesa.jogo = True
    mesa.volta(_U, "usb")
    assert mesa.servidor.quedas == quedas, "um nó foi recriado com o jogo aberto"
    assert mesa.ordem_no_servidor() == [_U[0], _U[2], _U[3], _U[1]]


def test_o_no_que_toca_nao_renasce(mesa: _Mesa) -> None:
    mesa.assentos = {u: n for n, u in enumerate(_U, start=1)}
    for u in _U:
        mesa.gadget(u)
    mesa.volta(_U, "usb")
    mesa.volta((_U[0], _U[2], _U[3]), "usb")
    mesa.servidor.jogo_em = {eh.nome_do_endpoint(_U[3])}
    quedas = list(mesa.servidor.quedas)
    mesa.volta(_U, "usb")
    assert mesa.servidor.quedas == quedas
    assert mesa.ordem_no_servidor() == [_U[0], _U[2], _U[3], _U[1]]


# O interruptor de bancada


def test_o_interruptor_devolve_a_ordem_do_endereco(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(eh.INTERRUPTOR_DA_ORDEM_DOS_NOS, eh.ORDEM_PELO_ENDERECO)
    mesa.assentos = dict(_ASSENTO)
    mesa.volta(_U, "bluetooth")
    assert mesa.servidor.cargas == [eh.nome_do_endpoint(u) for u in _U]


def test_o_interruptor_sem_refazer_nasce_na_ordem_e_nao_recria(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(eh.INTERRUPTOR_DA_ORDEM_DOS_NOS, eh.ORDEM_PELO_ASSENTO_SEM_REFAZER)
    antes, depois = _sai_e_volta(mesa, "bluetooth")
    assert antes == list(_U)
    assert depois == [_U[0], _U[2], _U[3], _U[1]]


# O ensaio da bancada (só leitura): a conta dele, sem servidor de som


def _ensaio() -> Any:
    import importlib.util

    caminho = Path(__file__).resolve().parents[2] / "scripts/ensaios/o_som_de_cada_pad_no_wine.py"
    spec = importlib.util.spec_from_file_location("o_som_de_cada_pad_no_wine", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo  # o @dataclass procura o módulo aqui
    spec.loader.exec_module(modulo)
    return modulo


def _sinks_json(ordem: list[tuple[str, int]]) -> str:
    """A lista ``pactl --format=json list sinks`` com os nós na ordem dada."""
    import json

    sinks = [{"index": 30, "name": "alsa_output.pci-0000_00_1f.3.analog-stereo",
              "description": "Áudio interno", "properties": {}}]
    for i, (uniq, assento) in enumerate(ordem):
        sinks.append({
            "index": 40 + i,
            "name": eh.nome_do_endpoint(uniq),
            "description": eh.rotulo_da_haptica(assento),
            "properties": {"sysfs.path": _interface_do_gadget(_U.index(uniq) + 1)},
        })
    return json.dumps(sinks)


def test_o_ensaio_le_a_ordem_e_nao_imprime_endereco(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ensaio = _ensaio()
    sinks = tmp_path / "sinks.json"
    sinks.write_text(_sinks_json([(_U[3], 1), (_U[0], 2), (_U[2], 3), (_U[1], 4)]))
    entradas = tmp_path / "entradas.json"
    entradas.write_text('[{"index": 7, "sink": 41, "properties": '
                        '{"application.process.binary": "Jogo.exe"}}]')
    log = tmp_path / "wine.log"
    log.write_text("\n".join(f"trace:mmdevapi:x {eh.nome_do_endpoint(u)}" for u in (_U[0], _U[3])))
    rc = ensaio.main(["--sinks-json", str(sinks), "--entradas-json", str(entradas),
                      "--log-do-wine", str(log)], env={})
    saida = capsys.readouterr().out
    assert rc == 0
    assert "VARIÁVEL ordem na lista do servidor: assento" in saida
    assert "VARIÁVEL âncora: 4 de 4 no gadget" in saida
    assert "Jogo.exe → controle 2" in saida
    assert "VARIÁVEL Wine: controle 2, controle 1" in saida
    assert "aa:bb:cc" not in saida.lower() and "HEFESTOAPARELHO" not in saida


def test_o_ensaio_ve_a_lista_fora_da_ordem_e_o_conteiner_repetido(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    ensaio = _ensaio()
    sinks = tmp_path / "sinks.json"
    lista = json.loads(_sinks_json([(_U[0], 2), (_U[1], 1)]))
    lista[2]["properties"]["sysfs.path"] = lista[1]["properties"]["sysfs.path"]
    sinks.write_text(json.dumps(lista))
    assert ensaio.main(["--sinks-json", str(sinks)], env={}) == 0
    saida = capsys.readouterr().out
    assert "VARIÁVEL ordem na lista do servidor: outra (controle 2, controle 1)" in saida
    assert "contêiner REPETIDO: controle 2 e controle 1" in saida


def test_o_ensaio_recusa_com_o_daemon_no_ar_sem_medir(capsys: pytest.CaptureFixture[str]) -> None:
    ensaio = _ensaio()
    perguntas: list[list[str]] = []

    def _pactl(argv: list[str]) -> str | None:
        perguntas.append(argv)
        return "[]"

    rc = ensaio.main([], env={}, ler_pactl=_pactl, daemon_no_ar=lambda _e, _u: True)
    assert rc == ensaio.RC_RECUSADO
    assert perguntas == []
    assert "RECUSADO" in capsys.readouterr().out
    assert ensaio.main([], env={}, ler_pactl=_pactl, daemon_no_ar=lambda _e, _u: False) == 0
    assert perguntas == []


def test_o_ensaio_recusa_sem_pad_no_gadget(capsys: pytest.CaptureFixture[str]) -> None:
    ensaio = _ensaio()
    perguntas: list[list[str]] = []

    def _pactl(argv: list[str]) -> str | None:
        perguntas.append(argv)
        return "[]"

    assert ensaio.main(["--medir"], env={}, ler_pactl=_pactl, contar_pads=lambda: 0) == 2
    assert perguntas == []
    rc = ensaio.main(["--medir", "--sem-gadget"], env={}, ler_pactl=_pactl, contar_pads=lambda: 0)
    assert rc == 0
    assert all("load-module" not in a and "unload-module" not in a for a in perguntas)
    assert "VARIÁVEL âncora: 0 de 0 no gadget; pads no gadget: 0" in capsys.readouterr().out
