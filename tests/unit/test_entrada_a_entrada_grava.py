"""O «Mapear Entrada a Entrada» grava de verdade — ENTRADA-A-ENTRADA-01 (23/09/2026).

A R9 das doze decisões dela do rádio: *ligar de verdade*. Até aqui a cerimônia
da aba 08 era eco — três telas por âncora, zero gesto, e um «Gravado na hora»
que não gravava nada.

O QUE ESTA RÉGUA COBRA:

1. **o laço:** a pergunta dá o LUGAR certo; responder grava na hora. As duas
   fases e o contador das telas aprovadas são da ENTRADA-A-ENTRADA-02, e a
   régua delas é ``test_entrada_a_entrada_02_as_telas_aprovadas.py``;
2. **a chave é o lugar:** gravar num boot e reler noutro, com os barramentos
   trocados e as portas visitadas em outra ordem, dá o MESMO nome. É a mordida
   da sprint: chavear pelo caminho de barramento, pelo ``hciN`` ou pela ordem
   de chegada reprova aqui;
3. **interligado com o resto:** o ``mapa-das-portas`` e os leitores de hoje
   leem o que a cerimônia gravou; o conselho de porta do vigia diz o nome
   dela; o adaptador herda o nome da porta — e o ``Alias`` tem UM escritor, o
   ``bt_active_mode.sh`` (ENTRADA-A-ENTRADA-02);
4. **um dono:** a grafia do lugar mora em ``utils/lugar.py`` (reexportada pelo
   ``utils/maquina.py``), e os dois módulos que o doctor carrega continuam
   stdlib no import — e, desde a ENTRADA-A-ENTRADA-02, também na chamada.

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
import re
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
from hefesto_dualsense4unix.integrations import mesa_de_radio
from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    Censo,
    ler_o_barramento,
)
from hefesto_dualsense4unix.utils import lugar as grafia
from hefesto_dualsense4unix.utils import maquina
from hefesto_dualsense4unix.utils.maquina import (
    MaquinaConfig,
    caminho_da_maquina,
    carregar_maquina,
)

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
            # ``platform/…`` é o controlador que não é PCI (o ``vhci_hcd`` do
            # usbip): o censo não acha controlador na cadeia, e não há lugar.
            pai = raiz / "devices" / pci if pci.startswith("platform/") else (
                raiz / "devices" / "pci0000:00" / pci
            )
            base = pai / f"usb{bus}"
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


def _laco(sysfs: SysfsDeMentira, **extra: Any) -> ee.LacoDaEntrada:
    """O laço com o /sys de mentira e o DISCO DE PRODUÇÃO (o do tmp_path).

    Esta bancada não publica os nós de entrada (a da 02 publica): os ``nos``
    gravados saem vazios, e nenhum ``/sys`` dela é lido.
    """
    extra.setdefault("entradas", tuple)
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


def test_a_pergunta_da_o_lugar_certo(boot_1: SysfsDeMentira, disco: Path) -> None:
    """O hub da mesa é a pergunta, e o DualSense pendurado nele vai junto."""
    boot_1.plugar(3, "4.2", DUALSENSE)
    foto = _laco(boot_1).comecar()

    assert foto["estado"] == ee.SENTADA
    pergunta = foto["pergunta"]
    assert pergunta["lugar"] == f"pci-{PCI_B}-usb-0:4"
    assert pergunta["caminho"] == "3-4" and pergunta["e_hub"] is True
    assert pergunta["pendentes"] == ["3-4.2"]
    assert pergunta["entrada"] is None, "porta nunca mapeada não tem número"


def test_responder_grava_na_hora(boot_1: SysfsDeMentira, disco: Path) -> None:
    boot_1.plugar(3, "4.2", DUALSENSE)
    laco = _laco(boot_1)
    laco.comecar()

    gravacao = laco.responder(ee.FACE_FRENTE)

    assert gravacao.gravou, gravacao
    assert gravacao.entradas == ("1", "2")
    documento = carregar_maquina()
    assert documento.mapa.faces[0].nome == ee.FACE_FRENTE
    assert documento.mapa.faces[0].portas == ["1", "2"]
    assert documento.mapa.faces[0].perto is True, "a frente é a face perto (fato dela)"
    assert documento.mapa.portas["2"].caminho == "3-4.2"
    assert documento.lugares[f"pci-{PCI_B}-usb-0:4.2"].entrada == "2"
    assert laco.estado()["estado"] == ee.FIM
    assert laco.estado()["feitas"] == 2


def test_parado_e_no_fim_o_laco_nao_le_o_barramento(boot_1: SysfsDeMentira) -> None:
    leituras: list[int] = []

    def ler() -> Censo:
        leituras.append(1)
        return boot_1.ler()

    laco = ee.LacoDaEntrada(ler=ler, entradas=tuple)
    laco.olhar()
    laco.olhar()
    assert leituras == [], "a cerimônia fechada relia o /sys a cada tique"
    boot_1.tirar("3-4")
    assert laco.comecar()["estado"] == ee.FIM
    leituras.clear()
    laco.olhar()
    assert leituras == [], "o fim relia o /sys a cada tique"


def test_a_face_fora_das_quatro_e_recusada(boot_1: SysfsDeMentira, disco: Path) -> None:
    """«Traseira» é do mockup, não do produto: uma quinta resposta abriria
    uma segunda língua para a mesma pergunta."""
    laco = _laco(boot_1)
    laco.comecar()
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


def test_o_hub_usb3_chega_pelos_dois_lados_e_e_uma_pergunta_so(
    tmp_path: Path, disco: Path
) -> None:
    sysfs = SysfsDeMentira(tmp_path / "sys", BOOT_1)
    sysfs.plugar(3, "2", HUB)
    sysfs.plugar(4, "2", HUB)
    foto = _laco(sysfs).comecar()
    assert foto["total"] == 1, "os dois lados do mesmo hub viraram duas perguntas"
    porta = foto["pergunta"]
    assert porta["lugar"] == f"pci-{PCI_B}-usb-0:2"
    assert porta["caminho"] == "3-2", "o lado 2.0 é onde o DualSense enumera"


# ---------------------------------------------------------------------------
# 2. a chave é o lugar — a mordida da sprint
# ---------------------------------------------------------------------------


def _mapear(sysfs: SysfsDeMentira, bus: int, devpath: str, face: str) -> ee.Gravacao:
    """Ela pluga, abre a cerimônia, responde e tira o cabo."""
    nome = sysfs.plugar(bus, devpath, DUALSENSE)
    laco = _laco(sysfs)
    assert laco.comecar()["pergunta"]["caminho"] == nome
    gravacao = laco.responder(face)
    assert gravacao.gravou, gravacao
    laco.parar()
    sysfs.tirar(nome)
    return gravacao


def test_gravar_e_reler_noutro_boot_da_o_mesmo_nome(tmp_path: Path, disco: Path) -> None:
    """A MORDIDA DA SPRINT. No primeiro boot, a porta 4 do controlador B é
    ``3-4`` e a porta 4 do controlador A é ``1-4``. No segundo, os
    controladores sobem na ordem inversa: a porta B vira ``1-4`` e a A vira
    ``3-4`` — o caminho de barramento de uma é o da outra.

    Chaveado pelo caminho de barramento, o motor diria que a porta A é a
    «Entrada 1» — o nome da outra metade da mesa, calado, que é o que a D3
    proíbe. Pelo lugar, cada porta continua sendo a dela.
    """
    boot = SysfsDeMentira(tmp_path / "boot1", BOOT_1)
    assert _mapear(boot, 3, "4", ee.FACE_FRENTE).entrada == "1"  # porta B
    assert _mapear(boot, 1, "4", ee.FACE_ATRAS).entrada == "2"  # porta A

    depois = SysfsDeMentira(tmp_path / "boot2", BOOT_2)
    depois.plugar(3, "4", DUALSENSE)  # a porta A, agora com o caminho da B
    depois.plugar(1, "4", DUALSENSE)  # a porta B
    assert _laco(depois).comecar()["estado"] == ee.FIM, "porta mapeada voltou a ser pergunta"
    assert ee.nome_da_porta("3-4", controladores=depois.controladores()) == "Entrada 2"
    assert ee.nome_da_porta("1-4", controladores=depois.controladores()) == "Entrada 1"


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

    boot_1.plugar(3, "4.2", DUALSENSE)
    laco = _laco(boot_1)
    laco.comecar()
    laco.responder(ee.FACE_HUB)

    documento = carregar_maquina()
    assert porta_de(documento.mapa, "3-4.2") == "2", "o leitor de hoje não viu a entrada"
    arranjo = arranjo_desta_maquina.arranjo(carregar=carregar_maquina, ler_o_barramento=boot_1.ler)
    assert arranjo is not None, "o mapa das portas não leu o que a cerimônia gravou"
    assert ee.FACE_HUB in json.dumps(arranjo, ensure_ascii=False)


def test_a_entrada_numerada_na_outra_janela_nao_vira_pergunta(
    boot_1: SysfsDeMentira, disco: Path
) -> None:
    """O desenho de hoje (``mapa``, pelo caminho) é a ponte com o que ela já
    numerou: o aparelho na entrada 7 não é pergunta, e a porta se chama 7."""
    maquina.gravar_maquina(
        {
            "mapa": {
                "faces": [{"nome": "Hub da mesa", "portas": ["7", "8"]}],
                "portas": {"7": {"caminho": "3-4.2"}, "8": {"caminho": "3-4"}},
            }
        }
    )
    boot_1.plugar(3, "4.2", DUALSENSE)
    assert _laco(boot_1).comecar()["estado"] == ee.FIM
    assert ee.nome_da_porta("3-4.2", controladores=BOOT_1) == "Entrada 7"


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


#: As frases que a ponte root escreve no diário com a porta dentro — LIDAS do
#: script, nunca digitadas aqui: digitada, a régua continuaria verde no dia em
#: que o escritor mudasse a redação e a troca deixasse de casar.
_FRASES_DA_PONTE_ROOT = re.compile(r'"(O adaptador da porta \$\{porta\}[^"]*)"')


def test_o_conselho_de_porta_do_vigia_diz_o_nome_dela() -> None:
    """A ponte root escreve o caminho do sistema no diário; quem lê o diário
    troca pelo nome dela. As frases são as de ``bt_ponte_privilegiada.sh``,
    todas elas, lidas do script."""
    documento = MaquinaConfig.model_validate(
        {
            "mapa": {
                "faces": [{"nome": ee.FACE_ATRAS, "portas": ["3"]}],
                "portas": {"3": {"caminho": "3-4.1.4"}},
            },
            "lugares": {
                f"pci-{PCI_B}-usb-0:4.1.4": {"entrada": "3", "caminho": "3-4.1.4"}
            },
        }
    )
    script = (RAIZ / "scripts" / "bt_ponte_privilegiada.sh").read_text(encoding="utf-8")
    moldes = sorted(set(_FRASES_DA_PONTE_ROOT.findall(script)))
    assert moldes, "a ponte root não escreve mais «O adaptador da porta …» — a régua perdeu o alvo"
    for molde in moldes:
        linha = {
            "o_que": "reiniciou o adaptador",
            "porta": "3-4.1.4",
            "familia": "3",
            "frase": molde.replace("${porta}", "3-4.1.4"),
        }
        com_nome = ee.com_o_nome_dela(linha, maquina=documento, controladores=BOOT_1)
        assert com_nome["frase"] == molde.replace("porta ${porta}", "Entrada 3"), molde
        assert com_nome["porta_nome"] == "Entrada 3"

    do_dono = {"o_que": bd.MUDOU_DE_LUGAR, "porta": f"pci-{PCI_B}-usb-0:4.1.4",
               "frase": "Este adaptador mudou de porta."}
    assert ee.com_o_nome_dela(do_dono, maquina=documento)["porta_nome"] == "Entrada 3"

    sem_mapa = ee.com_o_nome_dela(linha, maquina=MaquinaConfig(), controladores=BOOT_1)
    assert sem_mapa == linha, "sem nome conhecido, a linha volta como veio"


def test_dar_nome_grava_e_apaga_o_nome_do_lugar(disco: Path) -> None:
    """O nome é NOSSO e mora no ``maquina.json``; o ``Alias`` é do script
    (ENTRADA-A-ENTRADA-02). Nome vazio apaga o nome do lugar."""
    lugar = f"pci-{PCI_A}-usb-0:3"
    feito = ee.dar_nome(lugar, "  Extensor à esquerda ")
    assert feito.gravou and feito.nome == "Extensor à esquerda"
    assert carregar_maquina().lugares[lugar].nome == "Extensor à esquerda"
    assert ee.nome_do_lugar(lugar, controladores=BOOT_1) == "Extensor à esquerda"

    apagado = ee.dar_nome(lugar, "")
    assert apagado.gravou and lugar not in carregar_maquina().lugares
    with pytest.raises(ValueError):
        ee.dar_nome("3-4.1.4", "Sofá")


def test_o_estado_do_laco_e_o_que_o_piloto_pinta(boot_1: SysfsDeMentira, disco: Path) -> None:
    laco = _laco(boot_1)
    assert laco.estado()["estado"] == ee.PARADO and laco.estado()["tela"] is None
    laco.comecar()
    laco.responder(ee.FACE_ATRAS)
    foto = laco.estado()
    assert foto["estado"] == ee.FIM and foto["gravou"] is True
    ultima = foto["ultima"]  # (noqa-acento) chave de máquina, ASCII por contrato
    assert ultima["entrada"] == "1" and ultima["face"] == ee.FACE_ATRAS
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
        "lugares": {lugar: {"entrada": "1", "caminho": "3-4.2"}},
    }
    assert maquina.entrada_do_lugar(MaquinaConfig.model_validate(base), lugar) == "1"
    assert maquina.entrada_do_lugar(MaquinaConfig.model_validate(base), lugar, BOOT_2) == "1", (
        "a testemunha vale em qualquer boot"
    )

    renumerado = json.loads(json.dumps(base))
    renumerado["mapa"]["portas"]["1"]["caminho"] = "1-4.2"  # redesenhada noutro boot
    doc = MaquinaConfig.model_validate(renumerado)
    assert maquina.entrada_do_lugar(doc, lugar, BOOT_2) == "1", "no boot 2 o B é o barramento 1"
    assert maquina.entrada_do_lugar(doc, lugar, BOOT_1) is None, "no boot 1 o 1-4.2 é o A"

    movido = json.loads(json.dumps(base))
    movido["mapa"]["portas"]["1"]["caminho"] = "3-5"  # a outra janela pôs outro ali
    assert maquina.entrada_do_lugar(MaquinaConfig.model_validate(movido), lugar, BOOT_1) is None

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
    with pytest.raises(ValueError):
        MaquinaConfig.model_validate({"lugares": {f"pci-{PCI_A}-usb-0:1": {"caminho": "usb3"}}})
    esquecido = MaquinaConfig.model_validate({"lugares": {f"pci-{PCI_A}-usb-0:1": None}})
    assert esquecido.lugares == {}
    assert "lugares" in MaquinaConfig.model_fields


def test_a_traducao_entre_as_duas_chaves() -> None:
    assert maquina.lugar_do_caminho("3-4.1.4", BOOT_1) == f"pci-{PCI_B}-usb-0:4.1.4"
    assert maquina.lugar_do_caminho("3-4.1.4", BOOT_2) == f"pci-{PCI_A}-usb-0:4.1.4"
    assert maquina.lugar_do_caminho("9-1", BOOT_1) == "", "barramento que não existe"
    assert maquina.lugar_do_caminho("usb3", BOOT_1) == ""
    assert maquina.caminhos_do_lugar(f"pci-{PCI_B}-usb-0:4", BOOT_1) == ("3-4", "4-4")
    assert maquina.caminho_do_no("usb3-port4") == "3-4"
    assert maquina.caminho_do_no("3-4-port2") == "3-4.2"
    assert maquina.lugar_do_no("3-4.1-port4", BOOT_1) == f"pci-{PCI_B}-usb-0:4.1.4"
    assert maquina.caminho_do_no("3-4.2") == "", "aparelho não é nó de entrada"


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
    """Quem monta ``…-usb-0:…`` é ``utils/lugar.py``, e ninguém mais.

    MORDIDA: devolva ao ``bluez_dbus.lugar_de`` a montagem própria dele — ele
    volta a aparecer aqui, e a segunda grafia diverge da primeira no dia em que
    uma delas mudar.
    """
    dono = SRC / "utils" / "lugar.py"
    fora: list[str] = []
    for arquivo in sorted(SRC.rglob("*.py")):
        if arquivo == dono:
            continue
        for linha, texto in _literais(arquivo.read_text(encoding="utf-8")):
            if "usb-0:" in texto:
                fora.append(f"{arquivo.relative_to(RAIZ)}:{linha}: {texto!r}")
    assert not fora, "a grafia do lugar tem um segundo dono:\n" + "\n".join(fora)


def test_os_leitores_perguntam_ao_dono(monkeypatch: pytest.MonkeyPatch) -> None:
    assert maquina.lugar_de is grafia.lugar_de, "o maquina.py deixou de reexportar o dono"
    monkeypatch.setattr(grafia, "lugar_de", lambda pci, devpath: f"DONO:{pci}:{devpath}")
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


# ---------------------------------------------------------------------------
# 5. as regras do laço que não tinham dente (conferência, 23/09/2026)
# ---------------------------------------------------------------------------
#
# Cada teste abaixo nasceu de uma cura que passava com a régua inteira verde
# quando arrancada. O nome diz a regra; a mordida está no docstring.
#
# Desde a ENTRADA-A-ENTRADA-02 a fase sentada só pergunta o que NÃO tem lugar,
# então quatro destas regras (a fileira, o caminho repetido, a amarra velha e a
# extensão) não se alcançam mais pelo laço: elas continuam no GRAVADOR, que é
# quem as cumpre se o desenho mudar entre o tique e o toque — e a régua fala
# com ele direto.


def _gravar_direto(lugar: str, caminho: str, face: str) -> ee.Gravacao:
    porta = ee.PortaVista(lugar=lugar, caminho=caminho)
    return ee._gravar_as_portas(
        [(porta, ())], face, maquina=carregar_maquina(), controladores=BOOT_1
    )


def test_responder_de_novo_a_mesma_face_nao_embaralha_a_fileira(disco: Path) -> None:
    """A ordem da fileira é o desenho dela: confirmar a face de uma porta já
    mapeada não pode mandar o número para o fim.

    MORDIDA: tirar o número de TODAS as faces (inclusive a escolhida) e
    acrescentá-lo de novo — a fileira ``1, 2, 3`` vira ``2, 3, 1``.
    """
    for degrau in ("1", "2", "3"):
        lugar = f"pci-{PCI_B}-usb-0:4.{degrau}"
        assert _gravar_direto(lugar, f"3-4.{degrau}", ee.FACE_FRENTE).gravou
    assert _gravar_direto(f"pci-{PCI_B}-usb-0:4.1", "3-4.1", ee.FACE_FRENTE).entrada == "1"

    fileira = {f.nome: f.portas for f in carregar_maquina().mapa.faces}
    assert fileira[ee.FACE_FRENTE] == ["1", "2", "3"], "a fileira dela foi embaralhada"


def test_o_hub_que_chega_com_o_dualsense_dentro_e_a_porta_do_hub(
    tmp_path: Path, disco: Path
) -> None:
    """O buraco é onde o HUB entrou, não a porta do hub onde o DualSense está.

    MORDIDA: tirar o filtro de quem pende do hub — o DualSense vira pergunta
    própria, e a pergunta da vez vira ``3-2.1``.
    """
    sysfs = SysfsDeMentira(tmp_path / "sys", BOOT_1)
    sysfs.plugar(3, "2", HUB)
    sysfs.plugar(4, "2", HUB)
    sysfs.plugar(3, "2.1", DUALSENSE)

    foto = _laco(sysfs).comecar()
    assert foto["total"] == 1
    assert foto["pergunta"]["caminho"] == "3-2", "a porta do hub virou pergunta própria"
    assert foto["pergunta"]["lugar"] == f"pci-{PCI_B}-usb-0:2"
    assert foto["pergunta"]["pendentes"] == ["3-2.1"]


def test_o_aparelho_sem_controlador_pci_nao_e_pergunta(tmp_path: Path, disco: Path) -> None:
    """Sem controlador PCI não há lugar (o ``vhci_hcd`` do usbip, por exemplo),
    e sem lugar não há o que gravar: não pode virar pergunta.

    MORDIDA: aceitar o aparelho sem ``controlador_pci`` — a pergunta nasce com
    lugar vazio, e a resposta dela vira ``sem_lugar``.
    """
    sysfs = SysfsDeMentira(tmp_path / "sys", {**BOOT_1, 9: "platform/vhci_hcd.0"})
    sysfs.plugar(9, "1", DUALSENSE)
    assert _laco(sysfs).comecar()["estado"] == ee.FIM, "aparelho sem lugar virou pergunta"


def test_o_caminho_repetido_noutra_entrada_fica_vazio(disco: Path) -> None:
    """Um aparelho está em UMA entrada. Se o desenho ainda dava o mesmo caminho
    a outra entrada (a outra janela, ou um boot que trocou os barramentos), ela
    perde o caminho — senão os leitores de hoje respondem pela entrada errada.

    MORDIDA: não esvaziar a outra — ``porta_de`` (o leitor de hoje) responde
    ``3``, que é o número que ela deu a OUTRO buraco.
    """
    from hefesto_dualsense4unix.integrations.mapa_das_portas import porta_de

    lugar = f"pci-{PCI_B}-usb-0:4.2"
    maquina.gravar_maquina(
        {
            "mapa": {
                "faces": [{"nome": ee.FACE_FRENTE, "portas": ["3", "7"]}],
                "portas": {"3": {"caminho": "3-4.2"}, "7": {"caminho": "3-4.2"}},
            },
            "lugares": {lugar: {"entrada": "7", "caminho": "3-4.2"}},
        }
    )
    assert _gravar_direto(lugar, "3-4.2", ee.FACE_FRENTE).entrada == "7"

    documento = carregar_maquina()
    assert porta_de(documento.mapa, "3-4.2") == "7", "o leitor de hoje achou a outra entrada"
    outra = documento.mapa.portas.get("3")
    assert outra is None or outra.caminho is None, "a outra entrada ficou com o caminho"


def test_o_lugar_que_dizia_ser_esta_entrada_perde_a_amarra_e_guarda_o_nome(
    disco: Path,
) -> None:
    """Um número é de UM lugar. A amarra velha de outro lugar (que já não vale:
    o desenho pôs esta entrada noutro buraco) cai; o nome dele fica.

    MORDIDA: não tirar a amarra do outro — os dois lugares dizem «7», e a
    amarra que ACABOU de ser gravada já nasce "não sei".
    """
    novo = f"pci-{PCI_B}-usb-0:4.2"
    velho = f"pci-{PCI_A}-usb-0:9"
    maquina.gravar_maquina(
        {
            "mapa": {
                "faces": [{"nome": ee.FACE_ATRAS, "portas": ["7"]}],
                "portas": {"7": {"caminho": "3-4.2"}},
            },
            "lugares": {velho: {"entrada": "7", "nome": "Velho"}},
        }
    )
    assert _gravar_direto(novo, "3-4.2", ee.FACE_ATRAS).entrada == "7"

    documento = carregar_maquina()
    assert maquina.entrada_do_lugar(documento, novo) == "7", "a amarra nova nasceu «não sei»"
    assert documento.lugares[velho].entrada is None
    assert documento.lugares[velho].nome == "Velho", "o nome do outro lugar foi junto"


def test_dois_numeros_para_o_mesmo_lugar_e_nao_sei() -> None:
    """Sem amarra, o desenho de hoje dá nome pelos caminhos deste lugar — e os
    dois lados do mesmo buraco (``3-4`` e ``4-4``) com números diferentes é
    "não sei", nunca o primeiro da lista.

    MORDIDA: escolher um dos dois — sai «Entrada 1» para um buraco que o
    desenho diz ser também a 2.
    """
    documento = MaquinaConfig.model_validate(
        {
            "mapa": {
                "faces": [{"nome": ee.FACE_ATRAS, "portas": ["1", "2"]}],
                "portas": {"1": {"caminho": "3-4"}, "2": {"caminho": "4-4"}},
            }
        }
    )
    lugar = f"pci-{PCI_B}-usb-0:4"
    assert ee.nome_do_lugar(lugar, maquina=documento, controladores=BOOT_1) is None


def test_a_extensao_fica_no_quadrado_de_quem_a_hospeda(disco: Path) -> None:
    """A entrada que nasce de uma extensão desenha dentro do quadrado da que a
    hospeda e não entra em fileira nenhuma (``FaceDeclarada``).

    MORDIDA: pôr a extensão na face respondida — o ``15a`` aparece numa
    fileira «Na escrivaninha» que o desenho dela não tem.
    """
    maquina.gravar_maquina(
        {
            "mapa": {
                "faces": [{"nome": ee.FACE_FRENTE, "portas": ["15"]}],
                "portas": {"15a": {"filha_de": "15", "caminho": "3-4.2"}},
            }
        }
    )
    gravacao = _gravar_direto(f"pci-{PCI_B}-usb-0:4.2", "3-4.2", ee.FACE_ESCRIVANINHA)

    assert gravacao.entrada == "15a" and gravacao.face == ee.FACE_FRENTE
    documento = carregar_maquina()
    assert [(f.nome, f.portas) for f in documento.mapa.faces] == [(ee.FACE_FRENTE, ["15"])]
    assert documento.mapa.portas["15a"].filha_de == "15"


def test_o_rotulo_do_rodape_diz_entrada_e_nunca_porta() -> None:
    """O rótulo do campo ``lugares`` vai para a barra de status dela quando o
    campo é descartado, e a tela diz «entrada», nunca «porta»
    (``D-A-PALAVRA-ENTRADA``: «porta» colide com porta de rede).

    MORDIDA: devolva o rótulo «Qual entrada é cada porta» — reprova nomeando o
    campo.
    """
    from hefesto_dualsense4unix.app import ipc_bridge

    com_porta = {
        campo: rotulo
        for campo, rotulo in ipc_bridge._ROTULOS_SEM_SECAO.items()
        if re.search(r"\bportas?\b", rotulo, re.IGNORECASE)
    }
    assert "lugares" in ipc_bridge._ROTULOS_SEM_SECAO
    assert not com_porta, f"rótulo de tela com a palavra «porta»: {com_porta}"
