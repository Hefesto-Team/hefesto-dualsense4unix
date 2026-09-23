"""O motor serve as três telas que ela já aprovou — ENTRADA-A-ENTRADA-02 (23/09/2026).

A conferência da ENTRADA-A-ENTRADA-01 achou o maior problema dela: as três telas
da âncora ``#mapear-entrada-a-entrada`` (a página publicada, ``08-conexoes.html``)
descrevem o fluxo da ``LogicaDaCalibracao`` — uma fase SENTADA sobre os
aparelhos já plugados e uma fase EM PÉ sobre as entradas vazias —, e o motor
perguntava a face a cada plug. Decisão de quem coordena: o motor serve as
telas APROVADAS; as telas não mudam.

UMA RÉGUA POR ITEM DA SPRINT, e cada uma morde (a mordida está no docstring):

1. as duas fases e o contador — cada campo e cada botão das três telas, LIDOS
   da página publicada, chegam ao motor;
2. só o DualSense marca uma porta;
3. a amarra pelo ``ID_PATH`` inteiro, não pelo ``devpath``;
4. as quatro faces são as do produto;
5. ``bluez_dbus.lugar_de`` só com a biblioteca padrão também na CHAMADA;
6. um escritor do ``Alias``: o motor não escreve no BlueZ, e o nome do lugar
   chega ao ``Alias`` pelo ``bt_active_mode.sh``, lido do ``maquina.json``.

O ``/sys`` de mentira é uma árvore de verdade no ``tmp_path``, com os NÓS de
entrada (``usbN-portM``: ``state``, ``connect_type``, ``peer``, ``device``),
lida pelos leitores de verdade (``censo_do_barramento.ler_o_barramento`` e
``entradas_do_gabinete.listar_entradas``): um dublê que devolvesse o censo
pronto seria mais frouxo que o leitor real. O BlueZ é o rádio de mentira da
MOVER-01 (``radio_de_mentira.py``), com o ``DonoVivo`` de verdade por cima.

Faixa sintética da casa: controladores ``0000:0a:00.0`` e ``0000:0b:00.0``,
endereços ``aa:bb:cc`` com os octetos 4 e 5 zerados.
"""

from __future__ import annotations

import ast
import html
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    Censo,
    ler_o_barramento,
)
from hefesto_dualsense4unix.integrations.entradas_do_gabinete import (
    NoDeEntrada,
    listar_entradas,
)
from hefesto_dualsense4unix.utils import maquina
from hefesto_dualsense4unix.utils.maquina import (
    MaquinaConfig,
    caminho_da_maquina,
    carregar_maquina,
)
from tests.unit import radio_de_mentira as rm

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"
PAGINA = SRC / "interface" / "paginas" / "08-conexoes.html"

PCI_A = "0000:0a:00.0"
PCI_B = "0000:0b:00.0"

#: O primeiro boot: ``usb1``/``usb2`` no A, ``usb3``/``usb4`` no B.
BOOT_1 = {1: PCI_A, 2: PCI_A, 3: PCI_B, 4: PCI_B}
#: O segundo boot: os dois controladores subiram na ordem inversa.
BOOT_2 = {1: PCI_B, 2: PCI_B, 3: PCI_A, 4: PCI_A}
#: Os barramentos 3.x — os pares; os ímpares são o lado 2.0.
RAPIDOS = frozenset({2, 4})

DUALSENSE = ("054c", "0ce6", ("03", "00", "00"))
TECLADO = ("258a", "010c", ("03", "01", "01"))
MOUSE = ("25a7", "fa07", ("03", "01", "02"))
CAMERA = ("046d", "0825", ("0e", "01", "00"))
DONGLE_BT = ("2357", "0604", ("e0", "01", "01"))
HUB = ("05e3", "0610", ("09", "00", "00"))

#: Quantas entradas cada hub-raiz publica: o 2.0 tem seis, o 3.x tem quatro, e
#: as quatro primeiras de cada controlador são o mesmo buraco (``peer``).
PORTAS_DO_RAIZ_20 = 6
PORTAS_DO_RAIZ_3X = 4


# ---------------------------------------------------------------------------
# O /sys de mentira — com os nós de entrada, lido pelos leitores de verdade
# ---------------------------------------------------------------------------


class Gabinete:
    """Uma árvore ``/sys/bus/usb/devices`` com dois controladores xHCI.

    Cada controlador publica DOIS barramentos (o 2.0 e o 3.x), e cada hub
    publica os NÓS de entrada dele, com o buraco vazio ou cheio — é o que a
    fase em pé conta. ``encaixe`` dá o ``connect_type`` de um nó; o padrão é
    ``hotplug``.

    ``deslocamento`` é a mesa DELA: no ``0000:02:00.0`` o par de
    ``usb2-port1`` é ``usb1-port5`` (medido no ``peer`` em 23/09), e não
    ``usb1-port1``. Com ``deslocamento=2``, a entrada ``n`` da raiz 3.x é o
    par da ``n + 2`` da raiz 2.0 — e os dois lados do buraco têm ``devpath``
    diferente.
    """

    def __init__(
        self,
        raiz: Path,
        barramentos: Mapping[int, str],
        *,
        encaixe: Mapping[str, str] | None = None,
        deslocamento: int = 0,
    ) -> None:
        self.raiz = raiz
        self.lista = raiz / "bus" / "usb" / "devices"
        self.lista.mkdir(parents=True)
        self.barramentos = dict(barramentos)
        self.encaixe = dict(encaixe or {})
        self._dirs: dict[str, Path] = {}
        self._nos: dict[str, Path] = {}
        for bus, pci in sorted(barramentos.items()):
            base = raiz / "devices" / "pci0000:00" / pci / f"usb{bus}"
            self._aparelho(
                base,
                f"usb{bus}",
                bus=bus,
                devpath="0",
                vid="1d6b",
                pid="0003" if bus in RAPIDOS else "0002",
                classe=("09", "00", "00"),
                interface=f"{bus}-0:1.0",
            )
            quantas = PORTAS_DO_RAIZ_3X if bus in RAPIDOS else PORTAS_DO_RAIZ_20
            self._portas(f"usb{bus}", base / f"{bus}-0:1.0", quantas)
        for bus in sorted(barramentos):
            if bus in RAPIDOS and bus - 1 in barramentos:
                for n in range(1, PORTAS_DO_RAIZ_3X + 1):
                    self._parear(f"usb{bus - 1}-port{n + deslocamento}", f"usb{bus}-port{n}")

    # -- a árvore ------------------------------------------------------------

    def _aparelho(
        self,
        caminho: Path,
        nome: str,
        *,
        bus: int,
        devpath: str,
        vid: str,
        pid: str,
        classe: tuple[str, str, str],
        interface: str,
    ) -> None:
        caminho.mkdir(parents=True)
        velocidade = "5000" if bus in RAPIDOS else ("480" if classe[0] == "09" else "12")
        for arquivo, valor in {
            "idVendor": vid,
            "idProduct": pid,
            "busnum": str(bus),
            "devpath": devpath,
            "bDeviceClass": "09" if classe[0] == "09" else "00",
            "speed": velocidade,
        }.items():
            (caminho / arquivo).write_text(valor + "\n", encoding="utf-8")
        interface_dir = caminho / interface
        interface_dir.mkdir()
        for arquivo, valor in zip(
            ("bInterfaceClass", "bInterfaceSubClass", "bInterfaceProtocol"),
            classe,
            strict=True,
        ):
            (interface_dir / arquivo).write_text(valor + "\n", encoding="utf-8")
        (self.lista / nome).symlink_to(caminho)
        (self.lista / interface).symlink_to(interface_dir)
        self._dirs[nome] = caminho

    def _portas(self, hub: str, interface_dir: Path, quantas: int) -> None:
        for n in range(1, quantas + 1):
            no = f"{hub}-port{n}"
            pasta = interface_dir / no
            pasta.mkdir()
            (pasta / "state").write_text("not attached\n", encoding="utf-8")
            (pasta / "connect_type").write_text(
                self.encaixe.get(no, "hotplug") + "\n", encoding="utf-8"
            )
            self._nos[no] = pasta

    def _parear(self, um: str, outro: str) -> None:
        (self._nos[um] / "peer").symlink_to(self._nos[outro])
        (self._nos[outro] / "peer").symlink_to(self._nos[um])

    def _no_do(self, bus: int, devpath: str) -> str:
        hub, _, degrau = devpath.rpartition(".")
        return f"{bus}-{hub}-port{degrau}" if hub else f"usb{bus}-port{devpath}"

    # -- os gestos da mão dela -----------------------------------------------

    def plugar(
        self, bus: int, devpath: str, aparelho: tuple[Any, ...], *, portas: int = 0
    ) -> str:
        """Encaixa um aparelho em ``bus-devpath`` e devolve o nome do kernel.

        Um hub (``portas`` > 0) publica os nós de entrada dele, vazios.
        """
        vid, pid, classe = aparelho
        nome = f"{bus}-{devpath}"
        pai = (
            self._dirs[f"{bus}-{devpath.rsplit('.', 1)[0]}"]
            if "." in devpath
            else self._dirs[f"usb{bus}"]
        )
        self._aparelho(
            pai / nome,
            nome,
            bus=bus,
            devpath=devpath,
            vid=vid,
            pid=pid,
            classe=classe,
            interface=f"{nome}:1.0",
        )
        if portas:
            self._portas(nome, pai / nome / f"{nome}:1.0", portas)
            outro_lado = f"{bus - 1 if bus in RAPIDOS else bus + 1}-{devpath}"
            if outro_lado in self._dirs:
                for n in range(1, portas + 1):
                    self._parear(f"{outro_lado}-port{n}", f"{nome}-port{n}")
        no = self._nos[self._no_do(bus, devpath)]
        (no / "state").write_text("configured\n", encoding="utf-8")
        (no / "device").symlink_to(pai / nome)
        return nome

    def tirar(self, nome: str) -> None:
        """Desencaixa — o nó do buraco volta a dizer ``not attached``."""
        for entrada in list(self.lista.iterdir()):
            base = entrada.name.split(":", 1)[0]
            if base == nome or base.startswith(nome + "."):
                entrada.unlink()
        shutil.rmtree(self._dirs.pop(nome))
        for outro in [n for n in self._dirs if n.startswith(nome + ".")]:
            self._dirs.pop(outro)
        for sob in [n for n in self._nos if n.startswith((nome + "-", nome + "."))]:
            self._nos.pop(sob)
        bus, _, devpath = nome.partition("-")
        buraco = self._nos[self._no_do(int(bus), devpath)]
        (buraco / "state").write_text("not attached\n", encoding="utf-8")
        (buraco / "device").unlink()

    # -- os leitores de verdade ----------------------------------------------

    def ler(self) -> Censo:
        return ler_o_barramento(raiz_usb=str(self.lista))

    def entradas(self) -> tuple[NoDeEntrada, ...]:
        return listar_entradas(raiz_usb=str(self.lista))


def _laco(gabinete: Gabinete, **extra: Any) -> ee.LacoDaEntrada:
    """O laço com o /sys de mentira e o DISCO DE PRODUÇÃO (o do tmp_path)."""
    return ee.LacoDaEntrada(ler=gabinete.ler, entradas=gabinete.entradas, **extra)


@pytest.fixture()
def disco(tmp_path: Path) -> Path:
    """O ``maquina.json`` desta régua mora no ``tmp_path`` — conferido antes."""
    alvo = caminho_da_maquina()
    assert alvo.is_relative_to(tmp_path), f"o maquina.json da régua não está desviado: {alvo}"
    return alvo


def _lugar(pci: str, devpath: str) -> str:
    return maquina.lugar_de(pci, devpath)


# ---------------------------------------------------------------------------
# As três telas, LIDAS da página publicada
# ---------------------------------------------------------------------------

_TELA = re.compile(
    r'<div class="tela-nova" id="(mapear-entrada-a-entrada[^"]*)">(.*?)\n</div>', re.S
)
_BOTAO = re.compile(r'<a class="(?:btn[^"]*|tn-x)"[^>]*>(.*?)</a>', re.S)
_CONTADOR = re.compile(r'<span class="ce-cont">(.*)</span>$', re.M)


def _texto(fragmento: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragmento)).split())


def _as_tres_telas() -> dict[str, str]:
    telas = dict(_TELA.findall(PAGINA.read_text(encoding="utf-8")))
    assert len(telas) == 3, f"a página não tem mais as três telas da âncora: {sorted(telas)}"
    return telas


def _botoes(tela: str) -> list[str]:
    return [_texto(rotulo) for rotulo in _BOTAO.findall(tela)]


#: Cada botão das três telas e o gesto do motor que ele chama — o contrato com a
#: TRANSPLANTE, que fia a página. Um botão novo na página sem gesto aqui reprova.
GESTO_DO_BOTAO: dict[str, tuple[str, tuple[Any, ...]]] = {
    ee.FACE_FRENTE: ("responder", (ee.FACE_FRENTE,)),
    ee.FACE_ATRAS: ("responder", (ee.FACE_ATRAS,)),
    ee.FACE_HUB: ("responder", (ee.FACE_HUB,)),
    ee.FACE_ESCRIVANINHA: ("responder", (ee.FACE_ESCRIVANINHA,)),
    "Não sei onde fica": ("pular", ()),
    "Já chega por hoje": ("parar", ()),
    "Vou mostrar agora": ("levantar", ()),
    "Deixar para quando eu precisar": ("parar", ()),
    "Não alcanço": ("nao_alcanco", ()),
    "\N{MULTIPLICATION SIGN}": ("parar", ()),  # o fechar do topo de cada tela
}


def test_as_tres_telas_da_pagina_sao_as_tres_fases_do_motor() -> None:
    """Cada fase do motor diz qual tela a pinta, e as três são as da página.

    MORDIDA: troque um valor de ``ee.TELAS`` — a fase aponta uma âncora que a
    página não tem, e reprova.
    """
    assert set(ee.TELAS.values()) == set(_as_tres_telas())
    assert ee.TELAS[ee.SENTADA] == "mapear-entrada-a-entrada"
    assert ee.TELAS[ee.FIM].endswith("-fim")
    assert ee.TELAS[ee.EM_PE].endswith("-em-pe")
    assert ee.PARADO not in ee.TELAS, "parado é a janela fechada, sem tela"


def test_cada_botao_das_tres_telas_tem_gesto_no_motor() -> None:
    """Todo botão das três telas chega a um gesto que EXISTE no motor.

    MORDIDA: apague ``LacoDaEntrada.nao_alcanco`` (ou ``levantar``) — o botão
    da página aponta um gesto que o motor não tem. E um botão novo na página
    sem gesto aqui também reprova.
    """
    vistos: set[str] = set()
    for ancora, tela in _as_tres_telas().items():
        for rotulo in _botoes(tela):
            assert rotulo in GESTO_DO_BOTAO, f"{ancora}: o botão «{rotulo}» não chega ao motor"
            vistos.add(rotulo)
    for rotulo, (gesto, _args) in GESTO_DO_BOTAO.items():
        assert callable(getattr(ee.LacoDaEntrada, gesto, None)), (rotulo, gesto)
    assert set(GESTO_DO_BOTAO) == vistos, "gesto declarado para um botão que a página não tem"


# ---------------------------------------------------------------------------
# 1. as duas fases e o contador
# ---------------------------------------------------------------------------


@pytest.fixture()
def mesa(tmp_path: Path) -> Gabinete:
    """A mesa: câmera na 3-5 e teclado na 1-3, e um hub USB 3 na porta 4 do B
    (os dois lados, 3-4 e 4-4) com o mouse na 3-4.1."""
    gabinete = Gabinete(tmp_path / "sys", BOOT_1)
    gabinete.plugar(1, "3", TECLADO)
    gabinete.plugar(3, "5", CAMERA)
    gabinete.plugar(3, "4", HUB, portas=4)
    gabinete.plugar(4, "4", HUB, portas=4)
    gabinete.plugar(3, "4.1", MOUSE)
    return gabinete


def test_a_fase_sentada_pergunta_o_que_esta_plugado_e_o_hub_leva_o_que_pende(
    mesa: Gabinete, disco: Path
) -> None:
    """A tela sentada: «Onde fica esta entrada?», o aparelho como «espécie ·
    caminho», e «entrada N de M · sem sair da cadeira». Um toque no HUB vale
    para o que pende dele — os dois lados do hub são uma pergunta só.

    MORDIDA: devolva a cada aparelho a pergunta própria (``pendentes`` vazio
    em ``_perguntas_sentadas``) — o total passa de 3 para 4, e o mouse vira
    pergunta.
    """
    laco = _laco(mesa)
    foto = laco.comecar()
    assert foto["estado"] == ee.SENTADA and foto["tela"] == ee.TELAS[ee.SENTADA]
    assert (foto["passo"], foto["total"]) == (1, 3), foto
    pergunta = foto["pergunta"]
    assert (pergunta["especie"], pergunta["caminho"]) == ("Teclado", "1-3")

    laco.responder(ee.FACE_FRENTE)
    foto = laco.estado()
    assert (foto["passo"], foto["total"]) == (2, 3)
    pergunta = foto["pergunta"]
    assert pergunta["caminho"] == "3-4" and pergunta["e_hub"] is True
    assert pergunta["pendentes"] == ["3-4.1"], "o mouse do hub virou pergunta própria"

    gravacao = laco.responder(ee.FACE_HUB)
    assert gravacao.gravou and len(gravacao.entradas) == 2, gravacao
    documento = carregar_maquina()
    hub, mouse = gravacao.entradas
    assert documento.mapa.portas[hub].caminho == "3-4"
    assert documento.mapa.portas[hub].nos == ["usb3-port4", "usb4-port4"]
    assert documento.mapa.portas[mouse].caminho == "3-4.1"
    assert documento.lugares[_lugar(PCI_B, "4")].entrada == hub
    assert documento.lugares[_lugar(PCI_B, "4.1")].entrada == mouse
    face_do_hub = next(f for f in documento.mapa.faces if f.nome == ee.FACE_HUB)
    assert face_do_hub.portas == [hub, mouse] and face_do_hub.alto is True

    foto = laco.estado()
    assert foto["pergunta"]["especie"] == "Câmera" and (foto["passo"], foto["total"]) == (3, 3)
    laco.responder(ee.FACE_ATRAS)
    foto = laco.estado()
    assert foto["estado"] == ee.FIM and foto["tela"] == ee.TELAS[ee.FIM]
    assert (foto["passo"], foto["total"]) == (None, None), "no fim o contador some"
    assert foto["feitas"] == 4


def test_quem_ja_tem_lugar_para_tudo_abre_direto_no_fim(mesa: Gabinete, disco: Path) -> None:
    """*"Quem já tem lugar para tudo abre a janela direto aqui."* — e o laço
    novo não pergunta o que ela já respondeu.

    MORDIDA: tire a conferência de ``porta.entrada`` em ``_perguntas_sentadas``
    — o segundo laço volta a perguntar tudo.
    """
    laco = _laco(mesa)
    laco.comecar()
    while laco.estado()["estado"] == ee.SENTADA:
        laco.responder(ee.FACE_FRENTE)
    assert _laco(mesa).comecar()["estado"] == ee.FIM


def test_nao_sei_onde_fica_pula_sem_gravar_e_sem_perguntar_de_novo(
    mesa: Gabinete, disco: Path
) -> None:
    """«Pula esta entrada, sem gravar nada e sem perguntar de novo.»

    MORDIDA: não guardar o lugar pulado — o tique seguinte devolve o teclado
    como a pergunta da vez.
    """
    laco = _laco(mesa)
    laco.comecar()
    foto = laco.pular()
    assert (foto["passo"], foto["total"]) == (2, 3)
    assert laco.olhar()["pergunta"]["caminho"] == "3-4", "o pulado voltou como pergunta"
    assert not disco.exists(), "pular gravou"


def test_a_pergunta_da_vez_nao_muda_quando_chega_aparelho_e_o_que_sai_sai(
    mesa: Gabinete, disco: Path
) -> None:
    """A lista é refeita pela leitura de agora: o aparelho que chega entra no
    FIM da fila, e o que sai sai — nunca a pergunta da vez trocada sob o dedo.

    MORDIDA: ordenar as perguntas pelo barramento a cada tique — o DualSense
    que chega na 1-1 passa na frente do teclado.
    """
    laco = _laco(mesa)
    laco.comecar()
    mesa.plugar(1, "1", DUALSENSE)
    foto = laco.olhar()
    assert foto["pergunta"]["caminho"] == "1-3" and foto["total"] == 4
    mesa.tirar("3-5")
    assert laco.olhar()["total"] == 3, "a câmera saiu e continuou na conta"
    mesa.tirar("1-3")
    with pytest.raises(RuntimeError):
        laco.responder(ee.FACE_FRENTE)  # o teclado saiu entre o tique e o toque
    assert laco.estado()["pergunta"]["caminho"] == "3-4"
    assert not disco.exists()


def test_o_atalho_do_cartao_poe_a_pergunta_dele_primeiro(mesa: Gabinete, disco: Path) -> None:
    """O «Onde fica?» do cartão do ``mapa-do-radio.html`` abre a mesma âncora
    com o lugar da dúvida: a pergunta que o cobre vem primeiro — e a do mouse
    é a do hub, que o leva junto.

    MORDIDA: ignorar o ``lugar`` de ``comecar`` — a pergunta da vez é o
    teclado.
    """
    laco = _laco(mesa)
    foto = laco.comecar(_lugar(PCI_B, "4.1"))
    assert foto["pergunta"]["caminho"] == "3-4", foto["pergunta"]


@pytest.fixture()
def vazia(tmp_path: Path) -> Gabinete:
    """Nada plugado: seis buracos no controlador A (quatro deles 3.x) e seis
    no B. O B tem dois internos: ``usb3-port5`` e ``usb3-port6``."""
    return Gabinete(
        tmp_path / "sys",
        BOOT_1,
        encaixe={"usb3-port5": "hardwired", "usb3-port6": "hardwired"},
    )


def _em_pe(gabinete: Gabinete, **extra: Any) -> ee.LacoDaEntrada:
    laco = _laco(gabinete, **extra)
    assert laco.comecar()["estado"] == ee.FIM, "sem aparelho, a janela abre no fim"
    foto = laco.levantar()
    assert foto["estado"] == ee.EM_PE, foto
    return laco


def test_a_fase_em_pe_conta_as_vazias_e_grava_atras_do_gabinete(
    vazia: Gabinete, disco: Path
) -> None:
    """A tela em pé: «entrada N de M», e a face não se pergunta — «Atrás do
    gabinete». O buraco USB 3 (dois nós, ``peer``) conta UMA vez.

    MORDIDA: contar nós em vez de buracos (``vazias`` por nó) — o total vira
    20; ou gravar a face perguntada em vez da fixa.
    """
    laco = _em_pe(vazia)
    foto = laco.estado()
    assert foto["tela"] == ee.TELAS[ee.EM_PE] and foto["face"] == ee.FACE_ATRAS
    assert (foto["passo"], foto["total"]) == (1, 12), foto

    ds = vazia.plugar(1, "2", DUALSENSE)
    foto = laco.olhar()
    assert (foto["passo"], foto["total"]) == (2, 12), "o total andou para trás"
    ultima = foto["ultima"]
    assert ultima["gravou"] and ultima["face"] == ee.FACE_ATRAS
    documento = carregar_maquina()
    numero = ultima["entrada"]
    assert documento.mapa.portas[numero].nos == ["usb1-port2", "usb2-port2"]
    assert documento.lugares[_lugar(PCI_A, "2")].entrada == numero
    assert [f.nome for f in documento.mapa.faces] == [ee.FACE_ATRAS]

    vazia.tirar(ds)
    assert laco.olhar()["total"] == 12, "a entrada aprendida voltou para a conta ao sair o cabo"


def test_a_entrada_aprendida_de_pe_e_conhecida_pelo_lugar_noutro_boot(
    tmp_path: Path, disco: Path
) -> None:
    """Aprendida no primeiro boot, a porta 2 do A não volta à conta no segundo
    — e a porta 2 do B, que no segundo boot tem os NÓS que a do A tinha
    (``usb1-port2``), continua vaga.

    MORDIDA: responder «já conhecido» só pelos nós gravados no ``mapa`` (tire
    a amarra de ``_o_furo_e_conhecido``, ou deixe os nós valerem para a
    entrada amarrada) — o DualSense na porta do B não é aprendido, ou o da
    porta do A é aprendido de novo.
    """
    boot = Gabinete(tmp_path / "boot1", BOOT_1)
    laco = _em_pe(boot)
    boot.plugar(1, "2", DUALSENSE)  # a porta 2 do controlador A
    numero = laco.olhar()["ultima"]["entrada"]
    assert carregar_maquina().mapa.portas[numero].nos == ["usb1-port2", "usb2-port2"]

    depois = Gabinete(tmp_path / "boot2", BOOT_2)
    novo = _em_pe(depois)
    assert novo.estado()["total"] == 11
    depois.plugar(3, "2", DUALSENSE)  # a porta 2 do A, agora no barramento 3
    assert novo.olhar()["ultima"] is None, "a entrada aprendida foi aprendida de novo"
    depois.tirar("3-2")
    novo.olhar()
    depois.plugar(1, "2", DUALSENSE)  # a porta 2 do B, com os nós que a do A tinha
    foto = novo.olhar()
    assert foto["ultima"] is not None and foto["ultima"]["gravou"], "a vaga do B sumiu da conta"
    assert foto["ultima"]["lugar"] == _lugar(PCI_B, "2")


def test_nao_alcanco_tira_da_conta_de_vez(vazia: Gabinete, disco: Path) -> None:
    """«Tira esta entrada da conta de vez: não vira dívida, não vira aviso, e o
    Hefesto não volta a perguntar. Ela diminui o TOTAL do contador, não o
    feito.» — e o primeiro a sair é o que o kernel não diz ser de fora.

    MORDIDA: guardar o «Não alcanço» só na memória do laço — a cerimônia de
    amanhã volta a contar 12.
    """
    laco = _em_pe(vazia)
    foto = laco.nao_alcanco()
    assert (foto["passo"], foto["total"]) == (1, 11), foto
    fora = carregar_maquina().lugares
    assert fora[_lugar(PCI_B, "5")].fora is True, "saiu da conta um buraco de fora primeiro"

    amanha = _em_pe(vazia)
    assert amanha.estado()["total"] == 11, "o Hefesto voltou a perguntar"

    vazia.plugar(3, "5", DUALSENSE)  # ela alcançou, afinal: a leitura vence
    foto = amanha.olhar()
    assert foto["ultima"]["gravou"], foto
    declarado = carregar_maquina().lugares[_lugar(PCI_B, "5")]
    assert declarado.fora is None and declarado.entrada == foto["ultima"]["entrada"]


def test_o_buraco_usb3_da_raiz_que_numera_diferente_tem_o_lugar_do_lado_20(
    tmp_path: Path, disco: Path
) -> None:
    """A mesa DELA: no ``0000:02:00.0`` o par de ``usb2-port1`` é
    ``usb1-port5`` (o ``peer``, medido em 23/09). Os dois lados do buraco têm
    ``devpath`` diferente, e o lugar do buraco é o do lado 2.0 — o que o
    DualSense ganha ali.

    Exigir que os dois lados concordassem dava "não sei" a esses buracos: a
    entrada aprendida de pé voltava para a conta ao sair o cabo, e o «Não
    alcanço» não ia ao disco (a cerimônia de amanhã voltava a perguntar).

    MORDIDA: devolva a ``_lugar_do_furo`` o "só quando os nós concordam" —
    as duas metades reprovam.
    """
    deslocada = Gabinete(
        tmp_path / "sys",
        BOOT_1,
        encaixe={"usb1-port3": "hardwired", "usb2-port1": "hardwired"},
        deslocamento=2,
    )
    laco = _em_pe(deslocada)
    total = laco.estado()["total"]
    ds = deslocada.plugar(1, "4", DUALSENSE)  # usb1-port4, o par de usb2-port2
    foto = laco.olhar()
    assert foto["ultima"]["gravou"] and foto["ultima"]["lugar"] == _lugar(PCI_A, "4"), foto
    deslocada.tirar(ds)
    assert laco.olhar()["total"] == total, "a entrada aprendida voltou para a conta"

    foto = laco.nao_alcanco()  # o primeiro a sair: usb1-port3 + usb2-port1
    assert foto["ultima"]["gravou"], foto["ultima"]
    assert carregar_maquina().lugares[_lugar(PCI_A, "3")].fora is True
    assert _em_pe(deslocada).estado()["total"] == total - 2, "o Hefesto voltou a perguntar"


def test_o_contador_em_pe_e_refeito_pela_leitura_de_agora(vazia: Gabinete, disco: Path) -> None:
    """*"O total encolhe — ele é recalculado pela leitura de agora."*

    MORDIDA: congelar as vagas no ``levantar`` — o teclado encaixado numa vaga
    continua contando.
    """
    laco = _em_pe(vazia)
    teclado = vazia.plugar(1, "5", TECLADO)
    assert laco.olhar()["total"] == 11
    vazia.tirar(teclado)
    assert laco.olhar()["total"] == 12
    assert laco.pular()["total"] == 11, "«Não sei onde fica» em pé tira a vaga desta vez"
    assert not disco.exists(), "pular em pé gravou"


def test_ja_chega_por_hoje_fecha_em_qualquer_fase(mesa: Gabinete, disco: Path) -> None:
    laco = _laco(mesa)
    for fase in (ee.SENTADA, ee.FIM, ee.EM_PE):
        laco.comecar()
        if fase != ee.SENTADA:
            while laco.estado()["estado"] == ee.SENTADA:
                laco.pular()
        if fase == ee.EM_PE:
            laco.levantar()
        assert laco.estado()["estado"] == fase
        laco.parar()
        assert laco.estado() == {
            "estado": ee.PARADO,
            "tela": None,
            "passo": None,
            "total": None,
            "pergunta": None,
            "face": None,
            "feitas": 0,
            "gravou": None,
            "ultima": None,
        }
    with pytest.raises(RuntimeError):
        laco.levantar()  # «Vou mostrar agora» só existe no fim
    json.dumps(laco.comecar())  # vai pela ponte do piloto: tem de ser JSON


# ---------------------------------------------------------------------------
# As três telas CLICADAS, botão por botão, com o motor de mentira
# ---------------------------------------------------------------------------


def _clicar(laco: ee.LacoDaEntrada, rotulo: str) -> Any:
    gesto, argumentos = GESTO_DO_BOTAO[rotulo]
    return getattr(laco, gesto)(*argumentos)


def test_as_tres_telas_clicadas_cada_botao_chega_ao_motor(
    tmp_path: Path, disco: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Os botões de CADA tela, lidos da página, clicados na tela que os mostra,
    com o BlueZ de mentira da MOVER-01 no lugar do dono — e cada um muda o
    motor como a dica dele promete. Nada fala com o BlueZ: o ``Alias`` é do
    ``bt_active_mode.sh`` (item 6).

    MORDIDA: faça o «Não alcanço» não mexer no total, ou o «Vou mostrar
    agora» não sair do fim — reprova nomeando o botão.
    """
    radio = rm.RadioDeMentira()
    vivo = bd.DonoVivo(radio, lugares=lambda: {})
    assert vivo.ligar()
    monkeypatch.setattr(bd, "dono", lambda: vivo)
    chamadas, escritas = len(radio.chamadas), len(radio.escritas)

    telas = _as_tres_telas()
    gabinete = Gabinete(tmp_path / "sys", BOOT_1)
    gabinete.plugar(1, "3", TECLADO)
    gabinete.plugar(3, "5", CAMERA)
    gabinete.plugar(1, "4", DONGLE_BT)
    laco = _laco(gabinete)

    sentada = _botoes(telas[ee.TELAS[ee.SENTADA]])
    contador = _CONTADOR.search(telas[ee.TELAS[ee.SENTADA]])
    assert contador is not None and _texto(contador.group(1)).endswith("sem sair da cadeira")
    for rotulo in sentada:
        foto = laco.comecar()
        antes = foto["passo"], foto["total"], foto["feitas"]
        resposta = _clicar(laco, rotulo)
        depois = laco.estado()
        if rotulo in ee.FACES:
            assert resposta.gravou and depois["feitas"] == antes[2] + 1, rotulo
            laco.parar()
            disco.unlink()  # a próxima face começa da mesa sem desenho
        elif GESTO_DO_BOTAO[rotulo][0] == "pular":
            assert depois["passo"] == antes[0] + 1, rotulo
        else:
            assert depois["estado"] == ee.PARADO, rotulo

    fim = _botoes(telas[ee.TELAS[ee.FIM]])
    for rotulo in fim:
        laco.comecar()
        while laco.estado()["estado"] == ee.SENTADA:
            laco.pular()
        assert laco.estado()["tela"] == ee.TELAS[ee.FIM]
        _clicar(laco, rotulo)
        esperado = ee.EM_PE if rotulo == "Vou mostrar agora" else ee.PARADO
        if GESTO_DO_BOTAO[rotulo][0] == "pular":
            esperado = ee.FIM
        assert laco.estado()["estado"] == esperado, rotulo

    em_pe = _botoes(telas[ee.TELAS[ee.EM_PE]])
    for rotulo in em_pe:
        laco.comecar()
        while laco.estado()["estado"] == ee.SENTADA:
            laco.pular()
        foto = laco.levantar()
        assert foto["tela"] == ee.TELAS[ee.EM_PE]
        _clicar(laco, rotulo)
        depois = laco.estado()
        if GESTO_DO_BOTAO[rotulo][0] in ("nao_alcanco", "pular"):
            assert depois["total"] == foto["total"] - 1 and depois["passo"] == foto["passo"], rotulo
        else:
            assert depois["estado"] == ee.PARADO, rotulo

    assert radio.escritas[escritas:] == [], "a cerimônia escreveu no BlueZ"
    assert radio.chamadas[chamadas:] == [], "a cerimônia chamou o BlueZ"


# ---------------------------------------------------------------------------
# 2. só o DualSense marca uma porta
# ---------------------------------------------------------------------------


def test_so_o_dualsense_marca_uma_porta(vazia: Gabinete, disco: Path) -> None:
    """Palavra dela na R9: *«usarmos um dualsense e o USB pra sairmos de porta
    em porta»*. <!-- noqa-acento: citação literal dela -->

    MORDIDA: aceitar qualquer aparelho em ``_o_dualsense_no_furo`` — o dongle
    encaixado numa vaga vira entrada «Atrás do gabinete».
    """
    laco = _em_pe(vazia)
    dongle = vazia.plugar(1, "2", DONGLE_BT)
    foto = laco.olhar()
    assert foto["ultima"] is None and not disco.exists(), "o dongle marcou uma porta"
    vazia.tirar(dongle)
    laco.olhar()
    vazia.plugar(1, "2", DUALSENSE)
    assert laco.olhar()["ultima"]["gravou"], "o DualSense não marcou"


def test_a_re_enumeracao_do_dongle_nao_vira_a_porta_que_ela_plugou(
    tmp_path: Path, disco: Path
) -> None:
    """O ``-71`` e o reset de porta da ponte root: o dongle SOME e VOLTA na
    mesma porta, sem mão nenhuma. O buraco fica vazio por um tique — e volta
    com um aparelho dentro.

    MORDIDA: a mesma — aceitar qualquer aparelho grava a porta do dongle como
    «Atrás do gabinete».
    """
    gabinete = Gabinete(tmp_path / "sys", BOOT_1)
    dongle = gabinete.plugar(3, "1", DONGLE_BT)
    laco = _laco(gabinete)
    laco.comecar()
    laco.pular()  # «Não sei onde fica» para o dongle
    laco.levantar()
    gabinete.tirar(dongle)
    laco.olhar()
    gabinete.plugar(3, "1", DONGLE_BT)
    assert laco.olhar()["ultima"] is None
    assert not disco.exists()


# ---------------------------------------------------------------------------
# 3. a amarra pelo ID_PATH inteiro
# ---------------------------------------------------------------------------


def _documento(caminho_no_mapa: str, testemunha: str | None) -> MaquinaConfig:
    amarra: dict[str, Any] = {"entrada": "1"}
    if testemunha is not None:
        amarra["caminho"] = testemunha
    return MaquinaConfig.model_validate(
        {
            "mapa": {
                "faces": [{"nome": ee.FACE_ATRAS, "portas": ["1"]}],
                "portas": {"1": {"caminho": caminho_no_mapa}},
            },
            "lugares": {_lugar(PCI_B, "4"): amarra},
        }
    )


def test_a_amarra_confere_o_id_path_inteiro_e_nao_so_o_devpath() -> None:
    """A porta 4 do controlador A e a porta 4 do B têm o MESMO ``devpath``.

    Ela mapeou a porta 4 do B como Entrada 1 (``3-4`` no primeiro boot). A
    outra janela, depois, pôs a Entrada 1 na porta 4 do A (``1-4``, o mesmo
    boot). A amarra do B tem de cair.

    MORDIDA: devolva a comparação pelo ``devpath`` sozinho em
    ``utils/maquina.entrada_do_lugar`` — a amarra do B sobrevive, e a porta 4
    do B continua dizendo ser a Entrada 1 que o desenho pôs no A.
    """
    lugar = _lugar(PCI_B, "4")
    movido = _documento("1-4", testemunha="3-4")
    assert maquina.entrada_do_lugar(movido, lugar, BOOT_1) is None
    assert maquina.entrada_do_lugar(movido, lugar) is None, "sem controladores, «não sei»"

    # A testemunha: o desenho não mudou desde a amarra, em QUALQUER boot.
    intacto = _documento("3-4", testemunha="3-4")
    assert maquina.entrada_do_lugar(intacto, lugar, BOOT_2) == "1"
    assert maquina.entrada_do_lugar(intacto, lugar) == "1"

    # O desenho mudou num boot em que o B é o barramento 1: é a mesma porta.
    redesenhado = _documento("1-4", testemunha="3-4")
    assert maquina.entrada_do_lugar(redesenhado, lugar, BOOT_2) == "1"


def test_o_motor_grava_a_testemunha_e_o_nome_sobrevive_ao_boot_que_troca_os_barramentos(
    tmp_path: Path, disco: Path
) -> None:
    """Mapeada no primeiro boot, a porta 4 do B continua a Entrada dela no
    segundo, quando o caminho gravado (``3-4``) virou o da porta 4 do A.

    MORDIDA: não gravar ``caminho`` na amarra (``_gravar_as_portas``) — no
    segundo boot a amarra só tem a tradução de agora, que diz A, e a porta
    perde o número.
    """
    boot = Gabinete(tmp_path / "boot1", BOOT_1)
    boot.plugar(3, "4", DUALSENSE)
    laco = _laco(boot)
    laco.comecar()
    numero = laco.responder(ee.FACE_ATRAS).entrada
    assert carregar_maquina().lugares[_lugar(PCI_B, "4")].caminho == "3-4"

    depois = Gabinete(tmp_path / "boot2", BOOT_2)
    depois.plugar(1, "4", DUALSENSE)  # a porta 4 do B, agora no barramento 1
    novo = _laco(depois)
    foto = novo.comecar()
    assert foto["estado"] == ee.FIM, "a porta mapeada voltou a ser pergunta"
    assert ee.nome_do_lugar(_lugar(PCI_B, "4"), controladores=BOOT_2) == f"Entrada {numero}"
    assert ee.nome_do_lugar(_lugar(PCI_A, "4"), controladores=BOOT_2) is None


# ---------------------------------------------------------------------------
# 4. as quatro faces são as do produto
# ---------------------------------------------------------------------------


def test_as_quatro_faces_sao_as_do_produto_e_da_tela_aprovada() -> None:
    """Uma língua só para a mesma pergunta: os quatro botões da tela sentada,
    na ordem, são as quatro faces do motor, e a face fixa da fase em pé é a
    que a dica da tela em pé nomeia. «Traseira» (do ``mapa-do-radio.html``)
    não é resposta.

    MORDIDA: troque ``FACE_ATRAS`` por «Traseira» — a tela sentada e a dica em
    pé deixam de bater.
    """
    telas = _as_tres_telas()
    faces_da_tela = [
        r for r in _botoes(telas[ee.TELAS[ee.SENTADA]]) if GESTO_DO_BOTAO[r][0] == "responder"
    ]
    assert tuple(faces_da_tela) == ee.FACES
    dica = re.search(r'<span class="dica">(.*?)</span></span>', telas[ee.TELAS[ee.EM_PE]], re.S)
    assert dica is not None
    assert f"gravada em {ee.FACE_EM_PE}" in _texto(dica.group(1)), dica.group(1)
    assert "Traseira" not in ee.FACES
    with pytest.raises(ValueError):
        ee.LacoDaEntrada().responder("Traseira")


# ---------------------------------------------------------------------------
# 5. a grafia do lugar vive sem pydantic — também na CHAMADA
# ---------------------------------------------------------------------------


def test_a_grafia_do_lugar_responde_sem_pydantic_na_chamada() -> None:
    """Pelo ``python3`` do sistema (o recurso do doctor, pydantic 1.10) a
    CHAMADA de ``bluez_dbus.lugar_de`` levantava ``ImportError``
    (``field_validator``): o import tardio só adiava o erro, e todo adaptador
    ficava sem lugar, calado. Aqui o pydantic some do processo inteiro, e as
    duas chamadas do caminho do doctor têm de responder o lugar.

    MORDIDA: devolva ao ``bluez_dbus.lugar_de`` (ou ao
    ``mesa_de_radio._lugar``) o ``from …utils.maquina import lugar_de`` — o
    ``ImportError`` volta, e a régua reprova nomeando a chamada.
    """
    codigo = (
        "import sys\n"
        "sys.modules['pydantic'] = None\n"
        "from hefesto_dualsense4unix.integrations import bluez_dbus, mesa_de_radio\n"
        f"print(bluez_dbus.lugar_de({PCI_B!r}, '4.1.4'))\n"
        f"a = mesa_de_radio.Adaptador('hci9', no='x', busnum=3, devpath='1',"
        f" controlador_pci={PCI_A!r})\n"
        "print(a.lugar)\n"
        "print('pydantic' in sys.modules and sys.modules['pydantic'] is not None)\n"
    )
    ambiente = dict(os.environ)
    ambiente["PYTHONPATH"] = str(RAIZ / "src")
    feito = subprocess.run(
        [sys.executable, "-c", codigo],
        capture_output=True,
        text=True,
        env=ambiente,
        timeout=60,
        check=False,
    )
    assert feito.returncode == 0, feito.stderr[-1200:]
    assert feito.stdout.split() == [
        f"pci-{PCI_B}-usb-0:4.1.4",
        f"pci-{PCI_A}-usb-0:1",
        "False",
    ], feito.stdout


# ---------------------------------------------------------------------------
# 6. um escritor do Alias
# ---------------------------------------------------------------------------


def test_o_motor_nao_escreve_no_bluez() -> None:
    """O ``Alias`` tem UM escritor, o ``bt_active_mode.sh``
    (``D-COSTURA-BLUEZ``): o motor não importa nada que escreva no BlueZ.

    MORDIDA: devolva o ``projetar_o_nome`` (o ``apelido_do_dongle`` ou o
    ``bluez_dbus``) ao motor — o import reprova aqui.
    """
    arvore = ast.parse((SRC / "integrations" / "entrada_a_entrada.py").read_text(encoding="utf-8"))
    importados = {
        (no.module or "") + "." + nome.name
        for no in ast.walk(arvore)
        if isinstance(no, ast.ImportFrom)
        for nome in no.names
    } | {
        nome.name for no in ast.walk(arvore) if isinstance(no, ast.Import) for nome in no.names
    }
    proibidos = ("bluez_dbus", "apelido_do_dongle", "busctl", "renomear")
    assert not [i for i in importados if any(p in i for p in proibidos)], importados
    assert not hasattr(ee, "projetar_o_nome")


def test_dar_nome_so_grava_o_nome_no_maquina_json(disco: Path) -> None:
    """O renomear da entrada (a TRANSPLANTE chama ``dar_nome``) grava o nome e
    SÓ o nome: a projeção é do script.

    MORDIDA: ``dar_nome`` voltar a pedir o ``Alias`` — ele ganha um segundo
    parâmetro de projeção e a assinatura reprova.
    """
    lugar = _lugar(PCI_A, "3")
    feito = ee.dar_nome(lugar, "  Extensor à esquerda ")
    assert feito == ee.NomeDado(lugar, "Extensor à esquerda", True)
    assert carregar_maquina().lugares[lugar].nome == "Extensor à esquerda"
    assert list(ee.dar_nome.__kwdefaults__ or {}) == ["gravar"]


# -- o script ----------------------------------------------------------------

SCRIPT = RAIZ / "scripts" / "bt_active_mode.sh"
ADAPTADORES = {"hci0": "AA:BB:CC:00:00:01", "hci1": "AA:BB:CC:00:00:02"}
#: O ``ID_PATH`` que o udev publica para o aparelho USB de cada adaptador.
ID_PATH = {"hci0": _lugar(PCI_B, "4.1.4"), "hci1": _lugar(PCI_A, "3")}


def _executavel(caminho: Path, corpo: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("#!/usr/bin/env bash\n" + corpo, encoding="utf-8")
    caminho.chmod(caminho.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


class Bancada:
    """Dois adaptadores e um ``maquina.json``: o que o script lê e o que escreve.

    ``busctl``, ``udevadm``, ``hciconfig``, ``hcitool`` e ``id`` são dublês num
    ``PATH`` montado à mão; ``HEFESTO_SYS_BLUETOOTH``, ``HEFESTO_BT_LIB`` e
    ``HEFESTO_MAQUINA_JSON`` desviam as três raízes. Nenhum adaptador vivo é
    lido, e nenhum é renomeado.
    """

    def __init__(self, tmp: Path, *, alias: Mapping[str, str], lugares: Mapping[str, Any]) -> None:
        self.tmp = tmp
        self.fakes = tmp / "fakes"
        self.escritas = tmp / "set-property.tsv"
        self.sys_bt = tmp / "sys-class-bluetooth"
        self.lib = tmp / "var-lib-bluetooth"
        self.lib.mkdir(parents=True)
        self.json = tmp / "casa" / "maquina.json"
        self.json.parent.mkdir(parents=True)
        self.json.write_text(json.dumps({"version": 1, "lugares": lugares}), encoding="utf-8")
        for hci in ADAPTADORES:
            interface = self.sys_bt / "usb" / f"{hci}-usb" / f"{hci}-usb:1.0"
            (interface / "bluetooth" / hci).mkdir(parents=True)
            (self.sys_bt / hci).symlink_to(interface / "bluetooth" / hci)
            (interface / "bluetooth" / hci / "device").symlink_to(interface)
        mapa = " ".join(f'["{self.sys_bt}/usb/{h}-usb"]="{v}"' for h, v in ID_PATH.items())
        _executavel(
            self.fakes / "udevadm",
            f"declare -A ID=({mapa})\n"
            'alvo=""; while [[ $# -gt 0 ]]; do [[ "$1" == "-p" ]] && alvo="$2"; shift; done\n'
            'alvo="$(readlink -f "${alvo}")"\n'
            '[[ -n "${ID[$alvo]:-}" ]] && printf \'ID_PATH=%s\\n\' "${ID[$alvo]}"\n'
            "exit 0\n",
        )
        _executavel(self.fakes / "id", "echo 0\n")
        dos_alias = " ".join(f'["/org/bluez/{h}"]="{a}"' for h, a in alias.items())
        endereco = " ".join(f'["/org/bluez/{h}"]="{e}"' for h, e in ADAPTADORES.items())
        _executavel(
            self.fakes / "busctl",
            f"declare -A ALIAS=({dos_alias})\ndeclare -A ENDERECO=({endereco})\n"
            + f"""
case "$1" in
  tree) printf '%s\\n' /org/bluez/hci0 /org/bluez/hci1 ;;
  get-property)
    case "$5" in
      Alias)   printf 's "%s"\\n' "${{ALIAS[$3]:-}}" ;;
      Address) printf 's "%s"\\n' "${{ENDERECO[$3]:-}}" ;;
    esac ;;
  set-property) printf '%s\\t%s\\n' "$3" "$7" >> '{self.escritas}' ;;
esac
exit 0
""",
        )
        _executavel(self.fakes / "hciconfig", "exit 0\n")
        _executavel(self.fakes / "hcitool", "exit 0\n")
        self.getent = tmp / "getent.log"
        _executavel(self.fakes / "getent", f"echo \"$*\" >> '{self.getent}'\nexit 0\n")

    def rodar(self, **extra: str | None) -> subprocess.CompletedProcess[str]:
        """Roda o script; uma variável em ``None`` sai do ambiente."""
        ambiente: dict[str, str | None] = {
            "PATH": ":".join([str(self.fakes), "/usr/bin", "/bin"]),
            "HOME": str(self.tmp),
            "LANG": os.environ.get("LANG", "pt_BR.UTF-8"),
            "HEFESTO_SYS_BLUETOOTH": str(self.sys_bt),
            "HEFESTO_BT_LIB": str(self.lib),
            "HEFESTO_BT_LOG_DEST": str(self.tmp / "diario.log"),
            "HEFESTO_MAQUINA_JSON": str(self.json),
            **extra,
        }
        return subprocess.run(
            ["bash", str(SCRIPT), "--quiet"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env={k: v for k, v in ambiente.items() if v is not None},
        )

    def aliases_escritos(self) -> dict[str, str]:
        if not self.escritas.exists():
            return {}
        return {
            caminho.rsplit("/", 1)[-1]: valor
            for caminho, _, valor in (
                linha.partition("\t")
                for linha in self.escritas.read_text(encoding="utf-8").splitlines()
                if linha.strip()
            )
        }


def test_o_nome_do_lugar_chega_ao_alias_pelo_script(tmp_path: Path) -> None:
    """D3 com UM escritor: o ``bt_active_mode.sh`` lê o nome do lugar no
    ``maquina.json`` e o escreve no ``Alias`` do adaptador que está nele — o
    lugar vem do ``ID_PATH`` do udev, a mesma grafia do dono.

    MORDIDA: arranque do script o bloco do nome do lugar — o ``Alias`` do
    adaptador na porta com nome não muda.
    """
    banca = Bancada(
        tmp_path,
        alias={"hci0": "Sala", "hci1": "Quarto"},
        lugares={ID_PATH["hci0"]: {"entrada": "3", "nome": "Sofá"}},
    )
    feito = banca.rodar()
    assert feito.returncode == 0, feito.stderr[-800:]
    assert banca.aliases_escritos() == {"hci0": "Sofá"}, banca.aliases_escritos()


def test_o_nome_do_lugar_leva_o_prefixo_onde_a_linhagem_mora(tmp_path: Path) -> None:
    """O adaptador que hospeda um Pro Controller recebe o nome COSTURADO — o Pro
    cai sob carga sem o prefixo, e é por isso que o nome passa pelo mesmo
    escritor da costura.

    MORDIDA: escrever o nome cru (sem olhar a linhagem) — o ``hci1`` sai
    «Quarto novo», e o Pro volta ao sniff frágil.
    """
    banca = Bancada(
        tmp_path,
        alias={"hci0": "Sala", "hci1": "Quarto"},
        lugares={ID_PATH["hci1"]: {"entrada": "2", "nome": "Quarto novo"}},
    )
    bond = banca.lib / ADAPTADORES["hci1"] / "AA:BB:CC:00:00:53"
    bond.mkdir(parents=True)
    (bond / "info").write_text("[General]\nName=Pro Controller\n", encoding="utf-8")
    assert banca.rodar().returncode == 0
    assert banca.aliases_escritos() == {"hci1": "Nintendo Quarto novo"}


def test_o_script_nao_reescreve_o_nome_que_ja_esta_la(tmp_path: Path) -> None:
    """O watchdog roda a cada 2 min: nome que já está no ``Alias`` não se
    reescreve, e lugar sem nome não mexe no ``Alias`` dela.

    MORDIDA: escrever sem comparar — o ``Alias`` é reescrito a cada tique.
    """
    banca = Bancada(
        tmp_path,
        alias={"hci0": "Sofá", "hci1": "Quarto"},
        lugares={ID_PATH["hci0"]: {"nome": "Sofá"}, ID_PATH["hci1"]: {"entrada": "2"}},
    )
    assert banca.rodar().returncode == 0
    assert banca.aliases_escritos() == {}


def test_sob_sudo_o_gancho_do_maquina_json_morre(tmp_path: Path) -> None:
    """O script é root e lê o arquivo que ``HEFESTO_MAQUINA_JSON`` aponta — sem a
    conferência de dono, que só vale para a casa achada pelo ``getent``. Sob
    ``sudo`` o gancho morre junto com os outros dois de caminho: o
    ``env_reset`` já o apagaria, e o ``unset`` é o cinto para a máquina que o
    desligou.

    Roda SÓ o prólogo do script (até a primeira raiz lida), com uma sonda no
    fim: nenhum adaptador, nenhum ``/sys`` e nenhum ``busctl`` entram aqui.

    MORDIDA: tire ``HEFESTO_MAQUINA_JSON`` do ``unset`` do bloco do ``SUDO_UID``
    — sob sudo o gancho sobrevive e a sonda o imprime.
    """
    prologo, marca, _ = SCRIPT.read_text(encoding="utf-8").partition("\nSYS_BLUETOOTH=")
    assert marca and "SUDO_UID" in prologo, "o prólogo do script mudou de forma"
    sonda = prologo + '\nprintf "%s" "${HEFESTO_MAQUINA_JSON-morto}"\n'
    ambiente = {
        "PATH": "/usr/bin:/bin",
        "HEFESTO_MAQUINA_JSON": str(tmp_path / "maquina.json"),
    }

    def rodar(**extra: str) -> str:
        feito = subprocess.run(
            ["bash", "-c", sonda],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env={**ambiente, **extra},
        )
        assert feito.returncode == 0, feito.stderr[-800:]
        return feito.stdout

    assert rodar(SUDO_UID="1000") == "morto", "o gancho do maquina.json sobreviveu ao sudo"
    assert rodar(SUDO_USER="ela") == "morto"
    #: A régua da sonda: sem sudo, o MESMO gancho chega. Sem esta metade, a de
    #: cima passaria com a sonda quebrada.
    assert rodar() == str(tmp_path / "maquina.json")


def test_sob_a_suite_o_script_nao_le_o_maquina_json_dela(tmp_path: Path) -> None:
    """Com os ganchos de teste e sem ``HEFESTO_MAQUINA_JSON``, o script não
    procura a casa de ninguém: um teste não lê o ``maquina.json`` DELA.

    MORDIDA: procurar pelas casas do ``getent`` também sob os ganchos.
    """
    banca = Bancada(
        tmp_path,
        alias={"hci0": "Sala", "hci1": "Quarto"},
        lugares={ID_PATH["hci0"]: {"nome": "Sofá"}},
    )
    feito = banca.rodar(HEFESTO_MAQUINA_JSON=None)
    assert feito.returncode == 0, feito.stderr[-800:]
    assert not banca.getent.exists(), "o script procurou a casa de alguém sob a suíte"
    assert banca.aliases_escritos() == {}

