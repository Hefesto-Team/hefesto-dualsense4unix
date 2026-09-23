"""O «Mapear Entrada a Entrada» grava de verdade — ENTRADA-A-ENTRADA-01 (23/09/2026).

A R9 das doze decisões dela do rádio: *ligar de verdade*. Até aqui a cerimônia
da aba 08 era eco — três telas por âncora, zero gesto, e um «Gravado na hora»
que não gravava nada.

O QUE ESTA RÉGUA COBRA:

1. **o laço:** plugar numa porta dá o LUGAR certo; responder grava; tirar o
   cabo volta a esperar; «Não sei onde fica» não grava nem pergunta de novo;
2. **a chave é o lugar:** gravar num boot e reler noutro, com os barramentos
   trocados e as portas visitadas em outra ordem, dá o MESMO nome. É a mordida
   da sprint: chavear pelo caminho de barramento, pelo ``hciN`` ou pela ordem
   de chegada reprova aqui;
3. **interligado com o resto:** o ``mapa-das-portas`` e os leitores de hoje
   leem o que a cerimônia gravou; o conselho de porta do vigia diz o nome
   dela; o adaptador herda o nome da porta, e a projeção no ``Alias`` passa
   pelo dono do D-Bus, dentro da trava comum;
4. **um dono:** a grafia do lugar mora em ``utils/maquina.py``, e os dois
   módulos que o doctor carrega continuam stdlib no import.

O «udev falso» é uma árvore ``/sys`` de mentira no ``tmp_path``, lida pelo
``censo_do_barramento.ler_o_barramento`` DE VERDADE: um dublê que devolvesse o
censo pronto seria mais frouxo que o leitor real, e não pegaria o dia em que o
leitor deixasse de publicar o controlador PCI.

Faixa sintética da casa: controladores ``0000:0a:00.0`` e ``0000:0b:00.0``,
endereços ``aa:bb:cc`` com os octetos 4 e 5 zerados.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import diario_do_radio
from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
from hefesto_dualsense4unix.integrations import mesa_de_radio
from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    Censo,
    ler_o_barramento,
)
from hefesto_dualsense4unix.utils import maquina
from hefesto_dualsense4unix.utils.maquina import (
    MaquinaConfig,
    caminho_da_maquina,
    carregar_maquina,
)
from tests.unit import bluez_de_mentira as bm

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"

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
DONGLE_BT = ("2357", "0604", ("e0", "01", "01"))
HUB = ("05e3", "0610", ("09", "00", "00"))


# ---------------------------------------------------------------------------
# O /sys de mentira — lido pelo leitor de verdade
# ---------------------------------------------------------------------------


class SysfsDeMentira:
    """Uma árvore ``/sys/bus/usb/devices`` com dois controladores xHCI.

    Cada controlador publica DOIS barramentos (o 2.0 e o 3.x), como os desta
    bancada, e o número de cada barramento é a ordem do boot — por isso o
    segundo boot da régua troca os números sem mexer em porta nenhuma.
    """

    def __init__(self, raiz: Path, barramentos: Mapping[int, str]) -> None:
        self.raiz = raiz
        self.lista = raiz / "bus" / "usb" / "devices"
        self.lista.mkdir(parents=True)
        self.barramentos = dict(barramentos)
        self._dirs: dict[str, Path] = {}
        for bus, pci in sorted(barramentos.items()):
            base = raiz / "devices" / "pci0000:00" / pci / f"usb{bus}"
            self._no(
                base,
                f"usb{bus}",
                bus=bus,
                devpath="0",
                vid="1d6b",
                pid="0003" if bus in RAPIDOS else "0002",
                classe=("09", "00", "00"),
                interface=f"{bus}-0:1.0",
            )

    def _no(
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
        produto: str = "",
    ) -> None:
        caminho.mkdir(parents=True)
        velocidade = "5000" if bus in RAPIDOS else ("480" if classe[0] == "09" else "12")
        campos = {
            "idVendor": vid,
            "idProduct": pid,
            "busnum": str(bus),
            "devpath": devpath,
            "bDeviceClass": "09" if classe[0] == "09" else "00",
            "speed": velocidade,
            "product": produto,
        }
        for arquivo, valor in campos.items():
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

    def plugar(self, bus: int, devpath: str, aparelho: tuple[Any, ...]) -> str:
        """Encaixa um aparelho em ``bus-devpath`` e devolve o nome do kernel."""
        vid, pid, classe = aparelho
        nome = f"{bus}-{devpath}"
        pai = (
            self._dirs[f"{bus}-{devpath.rsplit('.', 1)[0]}"]
            if "." in devpath
            else self._dirs[f"usb{bus}"]
        )
        self._no(
            pai / nome,
            nome,
            bus=bus,
            devpath=devpath,
            vid=vid,
            pid=pid,
            classe=classe,
            interface=f"{nome}:1.0",
        )
        return nome

    def tirar(self, nome: str) -> None:
        """Desencaixa — o nó e tudo que pendura nele somem do /sys."""
        for entrada in list(self.lista.iterdir()):
            base = entrada.name.split(":", 1)[0]
            if base == nome or base.startswith(nome + "."):
                entrada.unlink()
        shutil.rmtree(self._dirs.pop(nome))
        for outro in [n for n in self._dirs if n.startswith(nome + ".")]:
            self._dirs.pop(outro)

    def ler(self) -> Censo:
        return ler_o_barramento(raiz_usb=str(self.lista))

    def controladores(self) -> dict[int, str]:
        return mesa_de_radio.controladores_dos_barramentos(raiz_usb=str(self.lista))


def _sem_nos(_caminho: str) -> tuple[str, ...]:
    return ()


def _laco(sysfs: SysfsDeMentira, **extra: Any) -> ee.LacoDaEntrada:
    """O laço com o /sys de mentira e o DISCO DE PRODUÇÃO (o do tmp_path)."""
    extra.setdefault("nos_do_furo", _sem_nos)
    return ee.LacoDaEntrada(ler=sysfs.ler, **extra)


@pytest.fixture()
def disco(tmp_path: Path) -> Path:
    """O ``maquina.json`` desta régua mora no ``tmp_path`` — conferido antes."""
    alvo = caminho_da_maquina()
    assert alvo.is_relative_to(tmp_path), f"o maquina.json da régua não está desviado: {alvo}"
    return alvo


@pytest.fixture()
def boot_1(tmp_path: Path) -> SysfsDeMentira:
    sysfs = SysfsDeMentira(tmp_path / "boot1", BOOT_1)
    sysfs.plugar(3, "4", HUB)  # o hub da mesa, na porta 4 do controlador B
    return sysfs


# ---------------------------------------------------------------------------
# 1. o laço
# ---------------------------------------------------------------------------


def test_plugar_numa_porta_da_o_lugar_certo(boot_1: SysfsDeMentira, disco: Path) -> None:
    laco = _laco(boot_1)
    assert laco.comecar()["estado"] == ee.ESPERANDO
    assert laco.olhar()["estado"] == ee.ESPERANDO, "o hub já estava: não é chegada"

    boot_1.plugar(3, "4.2", DUALSENSE)
    foto = laco.olhar()

    assert foto["estado"] == ee.VISTA
    porta = foto["porta"]
    assert porta["lugar"] == f"pci-{PCI_B}-usb-0:4.2"
    assert porta["caminho"] == "3-4.2"
    assert porta["e_dualsense"] is True
    assert porta["entrada"] is None, "porta nunca mapeada não tem número"


def test_responder_grava_na_hora_e_tirar_o_cabo_volta_a_esperar(
    boot_1: SysfsDeMentira, disco: Path
) -> None:
    def nos(caminho: str) -> tuple[str, ...]:
        hub, _, degrau = caminho.rpartition(".")
        return (f"{hub}-port{degrau}",)

    laco = _laco(boot_1, nos_do_furo=nos)
    laco.comecar()
    ds = boot_1.plugar(3, "4.2", DUALSENSE)
    laco.olhar()

    gravacao = laco.responder(ee.FACE_FRENTE)

    assert gravacao.gravou, gravacao
    assert gravacao.entrada == "1"
    documento = carregar_maquina()
    assert documento.mapa.faces[0].nome == ee.FACE_FRENTE
    assert documento.mapa.faces[0].portas == ["1"]
    assert documento.mapa.faces[0].perto is True, "a frente é a face perto (fato dela)"
    assert documento.mapa.portas["1"].caminho == "3-4.2"
    assert documento.mapa.portas["1"].nos == ["3-4-port2"]
    lugar = f"pci-{PCI_B}-usb-0:4.2"
    assert documento.lugares[lugar].entrada == "1"
    assert laco.estado()["estado"] == ee.GRAVADA
    assert laco.estado()["feitas"] == 1

    boot_1.tirar(ds)
    assert laco.olhar()["estado"] == ee.ESPERANDO


def test_tirar_o_cabo_sem_responder_nao_grava(boot_1: SysfsDeMentira, disco: Path) -> None:
    laco = _laco(boot_1)
    laco.comecar()
    ds = boot_1.plugar(3, "4.3", DUALSENSE)
    assert laco.olhar()["estado"] == ee.VISTA
    boot_1.tirar(ds)

    assert laco.olhar()["estado"] == ee.ESPERANDO
    assert not disco.exists(), "nada foi respondido, e nada pode ter ido ao disco"
    with pytest.raises(RuntimeError):
        laco.responder(ee.FACE_FRENTE)


def test_nao_sei_onde_fica_nao_grava_nem_pergunta_de_novo(
    boot_1: SysfsDeMentira, disco: Path
) -> None:
    laco = _laco(boot_1)
    laco.comecar()
    ds = boot_1.plugar(3, "4.3", DUALSENSE)
    laco.olhar()

    assert laco.pular()["estado"] == ee.ESPERANDO
    assert laco.olhar()["estado"] == ee.ESPERANDO, "a mesma porta voltou como chegada"
    assert not disco.exists()

    boot_1.tirar(ds)
    laco.olhar()
    boot_1.plugar(3, "4.3", DUALSENSE)
    assert laco.olhar()["estado"] == ee.VISTA, "plugar de novo é chegar de novo"


def test_parado_nao_le_o_barramento(boot_1: SysfsDeMentira) -> None:
    leituras: list[int] = []

    def ler() -> Censo:
        leituras.append(1)
        return boot_1.ler()

    laco = ee.LacoDaEntrada(ler=ler, nos_do_furo=_sem_nos)
    laco.olhar()
    laco.olhar()
    assert leituras == [], "a cerimônia fechada relia o /sys a cada tique"


def test_a_face_fora_das_quatro_e_recusada(boot_1: SysfsDeMentira, disco: Path) -> None:
    """«Traseira» é do mockup, não da janela de hoje: uma quinta resposta abriria
    uma segunda língua para a mesma pergunta."""
    laco = _laco(boot_1)
    laco.comecar()
    boot_1.plugar(3, "4.2", DUALSENSE)
    laco.olhar()
    with pytest.raises(ValueError):
        laco.responder("Traseira")
    assert not disco.exists()


def test_as_quatro_respostas_sao_as_da_janela_de_hoje() -> None:
    """As quatro moram também em ``calibrar_entradas`` (o gerador da aba 08 as
    lê de lá por AST). Esta régua trava as duas juntas, e a regra do perto e do
    alto junto com elas."""
    from hefesto_dualsense4unix.app.widgets import calibrar_entradas as janela

    assert janela.FACES == ee.FACES
    assert janela.FACE_QUE_E_PERTO == ee.FACE_QUE_E_PERTO
    assert janela.FACE_QUE_E_ALTO == ee.FACE_QUE_E_ALTO
    assert janela.PALAVRA_DA_ENTRADA == ee.PALAVRA_DA_ENTRADA


def test_o_hub_usb3_chega_pelos_dois_lados_e_e_uma_porta_so(
    tmp_path: Path, disco: Path
) -> None:
    sysfs = SysfsDeMentira(tmp_path / "sys", BOOT_1)
    laco = _laco(sysfs)
    laco.comecar()
    sysfs.plugar(3, "2", HUB)
    sysfs.plugar(4, "2", HUB)
    porta = laco.olhar()["porta"]
    assert porta is not None, "os dois lados do mesmo hub foram lidos como dúvida"
    assert porta["lugar"] == f"pci-{PCI_B}-usb-0:2"
    assert porta["caminho"] == "3-2", "o lado 2.0 é onde o DualSense enumera"


def test_dois_lugares_ao_mesmo_tempo_nao_se_chuta(tmp_path: Path, disco: Path) -> None:
    sysfs = SysfsDeMentira(tmp_path / "sys", BOOT_1)
    laco = _laco(sysfs)
    laco.comecar()
    sysfs.plugar(1, "3", TECLADO)
    sysfs.plugar(1, "5", MOUSE)
    assert laco.olhar()["estado"] == ee.ESPERANDO, "dois lugares e o motor escolheu um"

    sysfs.plugar(3, "1", DUALSENSE)
    porta = laco.olhar()["porta"]
    assert porta is not None and porta["caminho"] == "3-1", "o DualSense é o da mão dela"


# ---------------------------------------------------------------------------
# 2. a chave é o lugar — a mordida da sprint
# ---------------------------------------------------------------------------


def _mapear(sysfs: SysfsDeMentira, laco: ee.LacoDaEntrada, bus: int, devpath: str,
            face: str) -> ee.Gravacao:
    nome = sysfs.plugar(bus, devpath, DUALSENSE)
    assert laco.olhar()["estado"] == ee.VISTA
    gravacao = laco.responder(face)
    assert gravacao.gravou, gravacao
    sysfs.tirar(nome)
    assert laco.olhar()["estado"] == ee.ESPERANDO
    return gravacao


def test_gravar_e_reler_noutro_boot_da_o_mesmo_nome(tmp_path: Path, disco: Path) -> None:
    """A MORDIDA DA SPRINT. No primeiro boot, a porta 4 do controlador B é
    ``3-4`` e a porta 4 do controlador A é ``1-4``. No segundo, os
    controladores sobem na ordem inversa: a porta B vira ``1-4`` e a A vira
    ``3-4`` — o caminho de barramento de uma é o da outra. E ela visita as
    portas na ordem contrária.

    Chaveado pelo caminho de barramento, o motor diria que a porta A é a
    «Entrada 1» — o nome da outra metade da mesa, calado, que é o que a D3
    proíbe. Chaveado pela ordem de chegada, a primeira visitada seria a 1.
    Pelo lugar, cada porta continua sendo a dela.
    """
    boot = SysfsDeMentira(tmp_path / "boot1", BOOT_1)
    laco = _laco(boot)
    laco.comecar()
    assert _mapear(boot, laco, 3, "4", ee.FACE_FRENTE).entrada == "1"  # porta B
    assert _mapear(boot, laco, 1, "4", ee.FACE_ATRAS).entrada == "2"  # porta A

    depois = SysfsDeMentira(tmp_path / "boot2", BOOT_2)
    novo = _laco(depois)  # o laço de outro boot não lembra de nada
    novo.comecar()

    depois.plugar(3, "4", DUALSENSE)  # a porta A, agora com o caminho da B
    porta_a = novo.olhar()["porta"]
    assert porta_a["caminho"] == "3-4"
    assert porta_a["entrada"] == "2", "a porta A ganhou o número da B"
    assert porta_a["face"] == ee.FACE_ATRAS
    assert ee.nome_da_porta("3-4", controladores=depois.controladores()) == "Entrada 2"

    depois.tirar("3-4")
    novo.olhar()
    depois.plugar(1, "4", DUALSENSE)  # a porta B
    porta_b = novo.olhar()["porta"]
    assert porta_b["entrada"] == "1"
    assert ee.nome_da_porta("1-4", controladores=depois.controladores()) == "Entrada 1"


def test_responder_de_novo_numa_porta_conhecida_nao_cria_numero(
    boot_1: SysfsDeMentira, disco: Path
) -> None:
    laco = _laco(boot_1)
    laco.comecar()
    _mapear(boot_1, laco, 3, "4.2", ee.FACE_FRENTE)
    segunda = _mapear(boot_1, laco, 3, "4.2", ee.FACE_HUB)

    assert segunda.entrada == "1", "a mesma porta ganhou outro número"
    documento = carregar_maquina()
    por_face = {f.nome: f.portas for f in documento.mapa.faces}
    assert por_face[ee.FACE_FRENTE] == [], "a entrada ficou em duas faces"
    assert por_face[ee.FACE_HUB] == ["1"]
    assert next(f for f in documento.mapa.faces if f.nome == ee.FACE_HUB).alto is True


def test_o_adaptador_herda_o_nome_pelo_lugar_e_nao_pelo_hci() -> None:
    """D3. Os dois adaptadores trocam de ``hciN`` entre boots; o nome segue a porta."""
    l1 = f"pci-{PCI_A}-usb-0:3"
    l2 = f"pci-{PCI_B}-usb-0:4.1.4"
    documento = MaquinaConfig.model_validate(
        {
            "mapa": {"faces": [{"nome": ee.FACE_ATRAS, "portas": ["1", "2"]}]},
            "lugares": {l1: {"entrada": "1"}, l2: {"entrada": "2", "nome": "Sofá"}},
        }
    )
    antes = [
        bd.AdaptadorDoBluez("/org/bluez/hci0", "hci0", "aa:bb:cc:00:00:01", lugar=l1),
        bd.AdaptadorDoBluez("/org/bluez/hci1", "hci1", "aa:bb:cc:00:00:02", lugar=l2),
    ]
    depois = [
        bd.AdaptadorDoBluez("/org/bluez/hci0", "hci0", "aa:bb:cc:00:00:02", lugar=l2),
        bd.AdaptadorDoBluez("/org/bluez/hci1", "hci1", "aa:bb:cc:00:00:01", lugar=l1),
    ]
    nomes_antes = {a.endereco: ee.nome_do_adaptador(a, maquina=documento) for a in antes}
    nomes_depois = {a.endereco: ee.nome_do_adaptador(a, maquina=documento) for a in depois}
    assert nomes_antes == {"aa:bb:cc:00:00:01": "Entrada 1", "aa:bb:cc:00:00:02": "Sofá"}
    assert nomes_depois == nomes_antes, "o nome foi junto com o hciN para o outro dongle"


# ---------------------------------------------------------------------------
# 3. interligado com o resto
# ---------------------------------------------------------------------------


def test_os_leitores_de_hoje_e_o_mapa_das_portas_leem_o_que_ela_gravou(
    boot_1: SysfsDeMentira, disco: Path
) -> None:
    from hefesto_dualsense4unix.integrations.mapa_das_portas import porta_de
    from hefesto_dualsense4unix.interface import arranjo_desta_maquina

    laco = _laco(boot_1)
    laco.comecar()
    boot_1.plugar(3, "4.2", DUALSENSE)
    laco.olhar()
    laco.responder(ee.FACE_HUB)

    documento = carregar_maquina()
    assert porta_de(documento.mapa, "3-4.2") == "1", "o leitor de hoje não viu a entrada"
    arranjo = arranjo_desta_maquina.arranjo(carregar=carregar_maquina, ler_o_barramento=boot_1.ler)
    assert arranjo is not None, "o mapa das portas não leu o que a cerimônia gravou"
    assert ee.FACE_HUB in json.dumps(arranjo, ensure_ascii=False)


def test_a_entrada_numerada_na_outra_janela_ganha_a_amarra(
    boot_1: SysfsDeMentira, disco: Path
) -> None:
    """O desenho de hoje (``mapa``, pelo caminho) é a ponte com o que ela já
    numerou: a entrada 7 não vira uma entrada 1 nova."""
    maquina.gravar_maquina(
        {
            "mapa": {
                "faces": [{"nome": "Hub da mesa", "portas": ["7"]}],
                "portas": {"7": {"caminho": "3-4.2"}},
            }
        }
    )
    laco = _laco(boot_1)
    laco.comecar()
    boot_1.plugar(3, "4.2", DUALSENSE)
    assert laco.olhar()["porta"]["entrada"] == "7"

    assert laco.responder(ee.FACE_HUB).entrada == "7"
    assert carregar_maquina().lugares[f"pci-{PCI_B}-usb-0:4.2"].entrada == "7"


def test_o_adaptador_na_entrada_numerada_na_outra_janela_herda_o_numero() -> None:
    """Sem amarra pelo lugar, o desenho de hoje (pelo caminho DESTE boot) ainda
    dá nome ao adaptador — e só quando o caminho não é de outro lugar."""
    lugar = f"pci-{PCI_B}-usb-0:4.1.4"
    adaptador = bd.AdaptadorDoBluez("/org/bluez/hci0", "hci0", "aa:bb:cc:00:00:01", lugar=lugar)
    desenho = {
        "mapa": {
            "faces": [{"nome": "Hub da mesa", "portas": ["9"]}],
            "portas": {"9": {"caminho": "3-4.1.4"}},
        }
    }
    documento = MaquinaConfig.model_validate(desenho)
    assert ee.nome_do_adaptador(adaptador, maquina=documento, controladores=BOOT_1) == "Entrada 9"
    assert ee.nome_do_adaptador(adaptador, maquina=documento, controladores=BOOT_2) is None, (
        "noutro boot o caminho 3-4.1.4 é outra porta, e o nome foi junto"
    )

    de_outro = MaquinaConfig.model_validate(
        {**desenho, "lugares": {f"pci-{PCI_A}-usb-0:4.1.4": {"entrada": "9"}}}
    )
    assert ee.nome_do_adaptador(adaptador, maquina=de_outro, controladores=BOOT_1) is None


def test_o_conselho_de_porta_do_vigia_diz_o_nome_dela() -> None:
    """A ponte root escreve o caminho do sistema no diário; quem lê o diário
    troca pelo nome dela. A frase é a de ``bt_ponte_privilegiada.sh``."""
    documento = MaquinaConfig.model_validate(
        {
            "mapa": {
                "faces": [{"nome": ee.FACE_ATRAS, "portas": ["3"]}],
                "portas": {"3": {"caminho": "3-4.1.4"}},
            },
            "lugares": {f"pci-{PCI_B}-usb-0:4.1.4": {"entrada": "3"}},
        }
    )
    linha = {
        "o_que": "resetou a porta",
        "porta": "3-4.1.4",
        "familia": "3",
        "frase": "O adaptador da porta 3-4.1.4 travou de novo. Tire e ponha ele.",
    }
    com_nome = ee.com_o_nome_dela(linha, maquina=documento, controladores=BOOT_1)
    assert com_nome["frase"] == "O adaptador da Entrada 3 travou de novo. Tire e ponha ele."
    assert com_nome["porta_nome"] == "Entrada 3"

    do_dono = {"o_que": bd.MUDOU_DE_LUGAR, "porta": f"pci-{PCI_B}-usb-0:4.1.4",
               "frase": "Este adaptador mudou de porta."}
    assert ee.com_o_nome_dela(do_dono, maquina=documento)["porta_nome"] == "Entrada 3"

    sem_mapa = ee.com_o_nome_dela(linha, maquina=MaquinaConfig(), controladores=BOOT_1)
    assert sem_mapa == linha, "sem nome conhecido, a linha volta como veio"


def test_dar_nome_grava_o_lugar_e_projeta_no_adaptador_que_esta_nele(
    disco: Path,
) -> None:
    lugar = f"pci-{PCI_A}-usb-0:3"
    pedidos: list[tuple[str, str]] = []

    def adaptadores() -> list[bd.AdaptadorDoBluez]:
        return [
            bd.AdaptadorDoBluez("/org/bluez/hci0", "hci0", "aa:bb:cc:00:00:01",
                                lugar=f"pci-{PCI_B}-usb-0:4"),
            bd.AdaptadorDoBluez("/org/bluez/hci1", "hci1", "aa:bb:cc:00:00:02", lugar=lugar),
        ]

    def renomear(endereco: str, nome: str) -> Any:
        pedidos.append((endereco, nome))
        return type("R", (), {"aplicado": True})()

    feito = ee.dar_nome(
        lugar,
        "  Extensor à esquerda ",
        projetar=lambda qual, n: ee.projetar_o_nome(
            qual, n, adaptadores=adaptadores, renomear=renomear
        ),
    )

    assert feito.gravou and feito.projetado is True
    assert pedidos == [("aa:bb:cc:00:00:02", "Extensor à esquerda")]
    assert carregar_maquina().lugares[lugar].nome == "Extensor à esquerda"
    assert ee.nome_do_lugar(lugar) == "Extensor à esquerda"

    apagado = ee.dar_nome(lugar, "", projetar=lambda *_: pytest.fail("apagar não projeta"))
    assert apagado.gravou and lugar not in carregar_maquina().lugares


def test_o_dongle_plugado_numa_porta_com_nome_herda_o_nome(
    boot_1: SysfsDeMentira, disco: Path
) -> None:
    """D3: ela deu nome à porta; o dongle que entra nela recebe o nome no Alias."""
    lugar = f"pci-{PCI_B}-usb-0:4.2"
    assert ee.dar_nome(lugar, "Sofá", projetar=lambda *_: None).gravou
    projetados: list[tuple[str, str]] = []
    laco = _laco(boot_1, projetar=lambda qual, nome: projetados.append((qual, nome)))
    laco.comecar()
    boot_1.plugar(3, "4.2", DONGLE_BT)
    porta = laco.olhar()["porta"]
    assert porta["e_bluetooth"] is True and porta["nome"] == "Sofá"

    assert laco.responder(ee.FACE_ESCRIVANINHA).gravou
    assert projetados == [(lugar, "Sofá")]
    assert ee.nome_do_lugar(lugar) == "Sofá", "o nome dela vence o «Entrada 1»"


@pytest.fixture()
def trava_de_mentira(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    caminho = tmp_path / "radio.lock"
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(caminho))
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(tmp_path / "radio-diario.jsonl"))
    return caminho


def test_a_projecao_passa_pelo_dono_do_dbus_e_pela_trava_comum(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, trava_de_mentira: Path
) -> None:
    """O mapeamento grava pelo dono do D-Bus (BLUEZ-UM-DONO-01), dentro da trava.

    O caminho é o de produção: ``projetar_o_nome`` → ``apelido_do_dongle`` →
    ``bluez_dbus`` → o barramento (aqui, o de mentira). Com a trava na mão de
    outro motor, o ``Alias`` NÃO sai. E com um Pro Controller naquele
    adaptador, o nome sai COSTURADO — o Pro cai sob carga sem o prefixo, e é
    por isso que a projeção não escreve o ``Alias`` por conta própria.
    """
    lugar = f"pci-{PCI_A}-usb-0:3"
    barramento = bm.BarramentoDeMentira()
    vivo = bd.DonoVivo(barramento, lugares=lambda: {"hci9": lugar})
    assert vivo.ligar()
    monkeypatch.setattr(bd, "dono", lambda: vivo)
    hidraw = tmp_path / "hidraw"
    (hidraw / "hidraw0" / "device").mkdir(parents=True)
    (hidraw / "hidraw0" / "device" / "uevent").write_text(
        f"HID_NAME=Pro Controller\nHID_PHYS={bm.ADAPTADOR}\nHID_UNIQ=aa:bb:cc:00:00:44\n",
        encoding="utf-8",
    )

    def renomear(endereco: str, nome: str) -> Any:
        from hefesto_dualsense4unix.integrations.apelido_do_dongle import renomear_o_dongle

        return renomear_o_dongle(endereco, nome, raiz_hidraw=str(hidraw))

    monkeypatch.setattr(diario_do_radio, "PRAZO_DA_TRAVA_S", 0.2)
    with diario_do_radio.trava_do_radio("bt-watchdog", prazo_s=1.0):
        ocupado = ee.projetar_o_nome(lugar, "Sofá", renomear=renomear)
    assert ocupado is not None and not ocupado.aplicado
    assert barramento.escritas == [], "o Alias saiu com a trava na mão de outro motor"

    feito = ee.projetar_o_nome(lugar, "Sofá", renomear=renomear)
    assert feito is not None and feito.aplicado
    assert (bm.HCI, bd.ADAPTADOR, "Alias", "Nintendo Sofá") in barramento.escritas

    assert ee.projetar_o_nome(f"pci-{PCI_B}-usb-0:9", "X", renomear=renomear) is None


def test_o_estado_do_laco_e_o_que_o_piloto_pinta(boot_1: SysfsDeMentira, disco: Path) -> None:
    laco = _laco(boot_1)
    assert laco.estado() == {"estado": ee.PARADO, "feitas": 0, "porta": None, "gravou": None}
    laco.comecar()
    boot_1.plugar(3, "4.2", DUALSENSE)
    laco.olhar()
    laco.responder(ee.FACE_ATRAS)
    foto = laco.estado()
    assert foto["estado"] == ee.GRAVADA and foto["gravou"] is True
    assert foto["porta"]["entrada"] == "1" and foto["porta"]["face"] == ee.FACE_ATRAS
    json.dumps(foto)  # vai pela ponte do piloto: tem de ser JSON
    laco.parar()
    assert laco.estado()["estado"] == ee.PARADO
    assert ee.o_laco() is ee.o_laco(), "dois laços no mesmo processo"


# ---------------------------------------------------------------------------
# 4. a amarra, o esquema e o dono da grafia
# ---------------------------------------------------------------------------


def test_a_amarra_caduca_quando_o_desenho_muda_e_nao_quando_o_barramento_muda() -> None:
    lugar = f"pci-{PCI_B}-usb-0:4.2"
    base = {
        "mapa": {
            "faces": [{"nome": ee.FACE_FRENTE, "portas": ["1"]}],
            "portas": {"1": {"caminho": "3-4.2"}},
        },
        "lugares": {lugar: {"entrada": "1"}},
    }
    assert maquina.entrada_do_lugar(MaquinaConfig.model_validate(base), lugar) == "1"

    renumerado = json.loads(json.dumps(base))
    renumerado["mapa"]["portas"]["1"]["caminho"] = "1-4.2"  # outro boot, mesma porta
    assert maquina.entrada_do_lugar(MaquinaConfig.model_validate(renumerado), lugar) == "1"

    movido = json.loads(json.dumps(base))
    movido["mapa"]["portas"]["1"]["caminho"] = "3-5"  # a outra janela pôs outro ali
    assert maquina.entrada_do_lugar(MaquinaConfig.model_validate(movido), lugar) is None

    fora = json.loads(json.dumps(base))
    fora["mapa"] = {}
    assert maquina.entrada_do_lugar(MaquinaConfig.model_validate(fora), lugar) is None

    dois = json.loads(json.dumps(base))
    dois["lugares"][f"pci-{PCI_A}-usb-0:1"] = {"entrada": "1"}
    assert maquina.entrada_do_lugar(MaquinaConfig.model_validate(dois), lugar) is None


def test_o_esquema_do_lugar() -> None:
    with pytest.raises(ValueError):
        MaquinaConfig.model_validate({"lugares": {"3-4.1.4": {"entrada": "1"}}})
    with pytest.raises(ValueError):
        MaquinaConfig.model_validate({"lugares": {f"pci-{PCI_A}-usb-0:1": {"entrada": "um"}}})
    esquecido = MaquinaConfig.model_validate({"lugares": {f"pci-{PCI_A}-usb-0:1": None}})
    assert esquecido.lugares == {}
    assert "lugares" in MaquinaConfig.model_fields


def test_a_traducao_entre_as_duas_chaves() -> None:
    assert maquina.lugar_do_caminho("3-4.1.4", BOOT_1) == f"pci-{PCI_B}-usb-0:4.1.4"
    assert maquina.lugar_do_caminho("3-4.1.4", BOOT_2) == f"pci-{PCI_A}-usb-0:4.1.4"
    assert maquina.lugar_do_caminho("9-1", BOOT_1) == "", "barramento que não existe"
    assert maquina.lugar_do_caminho("usb3", BOOT_1) == ""
    assert maquina.caminhos_do_lugar(f"pci-{PCI_B}-usb-0:4", BOOT_1) == ("3-4", "4-4")


def test_o_leitor_dos_controladores_le_o_sys(boot_1: SysfsDeMentira, tmp_path: Path) -> None:
    assert boot_1.controladores() == BOOT_1
    assert mesa_de_radio.controladores_dos_barramentos(raiz_usb=str(tmp_path / "nada")) == {}
    adaptador = mesa_de_radio.Adaptador(
        "hci9", no="x", busnum=3, devpath="4.1.4", controlador_pci=PCI_B
    )
    assert adaptador.caminho == "3-4.1.4"
    assert adaptador.lugar == f"pci-{PCI_B}-usb-0:4.1.4"
    assert mesa_de_radio.Adaptador("hci8").lugar == "", "o embutido não tem lugar USB"


def _literais(fonte: str) -> list[tuple[int, str]]:
    arvore = ast.parse(fonte)
    docs: set[int] = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            primeiro = no.body[0] if no.body else None
            if isinstance(primeiro, ast.Expr) and isinstance(primeiro.value, ast.Constant):
                docs.add(id(primeiro.value))
    return [
        (no.lineno, no.value)
        for no in ast.walk(arvore)
        if isinstance(no, ast.Constant) and isinstance(no.value, str) and id(no) not in docs
    ]


def test_a_grafia_do_lugar_tem_um_dono_so() -> None:
    """Quem monta ``…-usb-0:…`` é ``utils/maquina.py``, e ninguém mais.

    MORDIDA: devolva ao ``bluez_dbus.lugar_de`` a montagem própria dele — ele
    volta a aparecer aqui, e a segunda grafia diverge da primeira no dia em que
    uma delas mudar.
    """
    dono = SRC / "utils" / "maquina.py"
    fora: list[str] = []
    for arquivo in sorted(SRC.rglob("*.py")):
        if arquivo == dono:
            continue
        for linha, texto in _literais(arquivo.read_text(encoding="utf-8")):
            if "usb-0:" in texto:
                fora.append(f"{arquivo.relative_to(RAIZ)}:{linha}: {texto!r}")
    assert not fora, "a grafia do lugar tem um segundo dono:\n" + "\n".join(fora)


def test_os_leitores_perguntam_ao_dono(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(maquina, "lugar_de", lambda pci, devpath: f"DONO:{pci}:{devpath}")
    assert bd.lugar_de(PCI_A, "1") == f"DONO:{PCI_A}:1"
    adaptador = mesa_de_radio.Adaptador("hci9", no="x", busnum=3, devpath="1",
                                        controlador_pci=PCI_A)
    assert adaptador.lugar == f"DONO:{PCI_A}:1"


def test_os_dois_do_doctor_continuam_stdlib_no_import() -> None:
    """O doctor carrega o ``exame_da_mesa`` — e por ele o ``bluez_dbus`` e o
    ``mesa_de_radio`` — pelo ``python3`` do sistema. Pedir a grafia ao
    ``utils/maquina`` (pydantic) no TOPO quebraria a conferência dela.

    MORDIDA: suba o ``from …utils.maquina import lugar_de`` para o topo de um
    dos dois — o import reprova aqui.
    """
    codigo = (
        "import sys\n"
        "sys.modules['pydantic'] = None\n"
        "import hefesto_dualsense4unix.integrations.exame_da_mesa\n"
        "import hefesto_dualsense4unix.integrations.bluez_dbus\n"
        "import hefesto_dualsense4unix.integrations.mesa_de_radio\n"
        "print('ok')\n"
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
    assert feito.returncode == 0 and feito.stdout.strip() == "ok", feito.stderr[-800:]
