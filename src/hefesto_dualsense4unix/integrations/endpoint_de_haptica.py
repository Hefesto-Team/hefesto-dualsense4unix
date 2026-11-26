"""O endpoint que o rádio não tem — HAPTICA-POR-RADIO-01, P3.

Pelo CABO a vibração dos jogos da Sony viaja como áudio: o jogo abre o endpoint
de quatro canais do controle e toca os canais 3 e 4, que são os dois motores.
Pelo RÁDIO o DualSense não tem placa de som nenhuma, e sem endpoint o jogo não
tem onde tocar — ele desiste antes de olhar o HID.

Este módulo publica o endpoint que falta: um ``module-null-sink`` do PipeWire
vestido de DualSense, um por APARELHO — ver «UM ENDPOINT POR APARELHO», abaixo.

O QUE O GE-PROTON LÊ, E POR QUE UM NÓ BASTA
--------------------------------------------
Lido no fonte em 18/09/2026 e medido no jogo no mesmo dia:

* ``fill_device_info`` (``winepulse.drv/pulse.c:668``) lê ``device.bus``,
  ``device.vendor.id`` e ``device.product.id`` **do proplist do sink** — não
  pergunta ao aparelho;
* ``is_dualsense_audio_device`` (patch 0063) exige ``usb`` + ``054c`` +
  ``0ce6``/``0df2``, tudo do proplist;
* o NOME tem de conter ``alsa_output.usb-Sony_Interactive_Entertainment_``,
  ``Wireless_Controller`` e ``Speaker__sink`` (patch 0060);
* o formato é ``FLOAT32LE``, 48 kHz, **quatro canais** (patch 0063).

**Nada disso pergunta como o CONTROLE está ligado** — mas a biblioteca da
Sony casa o HID com o áudio pelo ``ContainerId``, e o áudio sem HID do mesmo
contêiner é varrido sem parar (o engasgo de 12/10). Por isso a âncora é a
interface do gadget USB do PRÓPRIO pad (``usbip-vudc`` + ``vhci_hcd``), e o
aparelho sem gadget fica sem endpoint (:func:`a_porta_e_dele`, 14/10/2026).

A ÂNCORA, E O ERRO DE UM NÍVEL QUE CUSTOU UM LANÇAMENTO
--------------------------------------------------------
O ``ContainerId`` do endpoint é o que casa o nó com o device KS do prefixo. Ele
sai de ``get_container_id`` (``pulse.c:608``), que só roda quando o proplist
traz ``sysfs.path`` e que sobe ao **pai** ``usb_device`` desse caminho.

* **sem ``sysfs.path``** o GUID sai ZERADO — e zerado é o valor de toda saída
  que não é USB, então o jogo poderia abrir a háptica na caixa de som da
  pessoa;
* **com o caminho de um ``usb_device``** o GUID sai do PAI dele. Medido no
  jogo às 03h40 de 18/09: declarando o hub âncora, o jogo gravou o GUID do
  **hub raiz**, e o device KS nunca casou.

Por isso o nó declara a INTERFACE da âncora (``<bus>-<porta>:1.0``), que é a
forma de uma placa de som de verdade — o caminho da âncora é o do ``sound/card``,
cujo pai é o aparelho. Com isso, às 03h54, os dois lados deram o mesmo GUID e o
jogo abriu o stream de quatro canais.

**Nada é escrito na âncora.** A âncora é só um endereço de onde o Wine tira quatro
números.

O RÓTULO DIZ O CONTROLE, E NÃO O ENDEREÇO — 24/09/2026
------------------------------------------------------
A-HAPTICA-TEM-NOME-DE-CONTROLE-01. O nó aparecia na lista de saídas de som da
pessoa como «DualSense <os seis hex do endereço> (háptica)». Passou à FORMA A
dos outros dois nós do controle: «Háptica do Controle N (DualSense Wireless
Controller)», com o número do jogador, que se renova quando o número anda
(:meth:`EndpointDeHaptica.renovar_o_rotulo`, nunca com jogo aberto).

**O que o jogo lê não mudou, e isso foi medido no código** — o GE-Proton11-7
com os 182 patches ``proton-ds5-haptic`` aplicados em ordem. A descrição vira
o ``drv_id`` do endpoint no ``mmdevapi`` (``get_device_name``), e é só ali que
o rótulo pesa: os casamentos sobre ele dão o MESMO resultado para o rótulo velho e
para o novo — «DualSense» presente (``is_dualsense_endpoint_name``, o 0187
inclusive), «… Speaker» e «Internal Mono Speaker» ausentes
(``is_dualsense_audioendpoint_name``, o mono), «Direct Wireless Controller»
ausente. O nome que o JOGO lê (``DEVPKEY_Device_FriendlyName``) nem passa pela
descrição: o nó declara USB ``054c:0ce6``, e o ``find_product_name_override``
do ``mmdevapi`` o troca por «Speakers (DualSense Wireless Controller)», antes e
depois desta cura. O id do endpoint sai do NOME, e a âncora do
``ContainerId`` — o que a RE Engine casa com o device KS — sai do
``sysfs.path``. Nenhum dos dois mudou. A régua é
``tests/unit/test_a_haptica_tem_nome_de_controle.py``.

UM ENDPOINT POR APARELHO — 02/10/2026
-------------------------------------
A-HAPTICA-E-POR-APARELHO-01, pela palavra de 29/09, à pergunta da háptica
de P1 a P4: toda feature é uma por aparelho, sempre. A decisão REVOGA a
``D-2909-A-HAPTICA-TEM-UM-ENDPOINT-POR-LUGAR``: de 28/09 a 02/10 eram QUATRO
nós, um por lugar, de pé desde o primeiro DualSense
(A-HAPTICA-CHEGA-A-QUEM-ENTRA-DEPOIS-01), e o número que andava trocava a
ponte ou o laço de quem se sentava ali.

Agora é UM nó por DualSense da mesa, nos dois transportes, com o nome, a
âncora e o rótulo DELE: a marca é :func:`dualsense_bt_audio.marca_do_aparelho`
(seis letras que não são hex, e não o rabo do endereço). No rádio a ponte lê o
endpoint do aparelho; no cabo um laço o leva à placa dele
(``integrations/haptica_do_cabo.py``). Renumerar a mesa não troca nada disso.
O nó do aparelho que saiu FICA enquanto um jogo toca nele (nó que some quebra
o jogo que o escolheu).

**O preço, que o usuário aceitou na pergunta:** o registro que o jogo lê (o device
KS, ``audio_ks_dualsense``) se grava no lançamento, e o aparelho que chega com
o jogo aberto ganha um endpoint que o jogo não conhece até reabrir. O diário
diz a linha ``haptica_aparelho_sem_registro_no_jogo``, uma vez por aparelho e
partida.

O RUMBLE DO PAD SEM HÁPTICA TOCA NO APARELHO — 29/09/2026
---------------------------------------------------------
NO-MODO-XBOX-TUDO-FUNCIONA-01, parte 4. No modo Xbox o jogo vê um pad de
Xbox 360 no ``uinput`` e só manda rumble (dois motores, 0 a 255); o áudio de
háptica que ele toca num DualSense não existe ali. :class:`TocadorDoRumble`
toca esse rumble como háptica nos canais traseiros do endpoint do aparelho que
o recebe (desde 02/10; era o do lugar), e o laço do cabo e a ponte do rádio o
levam ao controle como levam o do jogo.

**O ALVO É O ``object.serial``, COM O RECUO PROIBIDO** (:func:`argv_do_tocador`):
um fluxo de reprodução cujo alvo não resolve cai na saída PADRÃO sem erro — a
TV ou a caixa de som do usuário, tocando um zumbido de 60 Hz. O fluxo pede
``node.dont-fallback`` e ``node.dont-reconnect``, e o destino é conferido no
grafo (:func:`conferir_o_destino_do_tocador`): ligado a outro nó, morre.
"""

from __future__ import annotations

import contextlib
import fcntl
import math
import os
import re
import select
import shutil
import subprocess
import threading
import time
from array import array
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from hefesto_dualsense4unix.integrations import classe_do_rumble, pad_usb, porta_do_som
from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    CANAIS_DA_HAPTICA,
    o_servidor_e_o_pipewire,
    rodar_pactl,
    serial_do_no,
)
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
    LETRAS_DA_MARCA_DO_APARELHO,
    PREFIXO_DA_MARCA_DO_APARELHO,
    TAMANHO_DA_MARCA_DO_APARELHO,
    campo_do_controle,
    marca_do_aparelho,
)
from hefesto_dualsense4unix.integrations.filho_de_som import lancar_filho
from hefesto_dualsense4unix.integrations.vestido_de_dualsense import (
    PID_DUALSENSE,
    VID_SONY,
    campos_da_identidade,
    campos_do_nome,
    com_o_nome_da_sony,
    sem_o_nome_da_sony,
)
from hefesto_dualsense4unix.profiles import formas_de_haptica as formas
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


TAXA_DO_ENDPOINT = 48000

MOLDE_DO_NOME = (
    "alsa_output.usb-Sony_Interactive_Entertainment_"
    "DualSense_Wireless_Controller_HEFESTO{marca}-00.HiFi__Speaker__sink"
)
MARCA_DO_NOME = "HEFESTO"

MOLDE_DO_NOME_SEM_PORTA = "hefesto_haptica_HEFESTO{marca}"

MARCA_DO_ENSAIO = "hefesto.origem=ensaio"

AGULHAS = (
    "alsa_output.usb-Sony_Interactive_Entertainment_",
    "Wireless_Controller",
    "Speaker__sink",
)
MAX_NOME = 127

PRIORIDADE_DA_SESSAO = 0

PRIORIDADE_DO_RELOGIO = 3000

VOLUME_DOS_MOTORES = "100%"

NOME_DA_HAPTICA_DO_CONTROLE = "Háptica do Controle"

_MODULO_NULL_SINK = "module-null-sink"

_ROTULO_NO_ARGUMENTO = re.compile(r"device\.description='([^']*)'")


@dataclass(frozen=True)
class Ancora:
    """Um ``usb_device`` de onde o Wine tira o ``ContainerId`` do endpoint."""

    syspath: str
    declarado: str
    nome: str = ""


SEM_PORTA = Ancora(syspath="", declarado="")


def ancora_do_gadget(uniq: str) -> Ancora | None:
    """A âncora do aparelho: a interface do gadget do pad dele, a ÚNICA que ele tem.

    O-PAD-VIRTUAL-E-O-SOM-DELE-NASCEM-NO-MESMO-USB-01 (07/10/2026). O pad em
    USB e o nó de som sobem ao MESMO ``usb_device``: o ``winebus`` e o
    ``winepulse`` tiram dele o mesmo ``ContainerId``, e o jogo casa o som com
    o controle. None = o aparelho não tem gadget, e fica sem endpoint
    (TODO-PAD-TEM-PORTA-PROPRIA-01, 14/10/2026: a âncora emprestada saiu).
    """
    return ancora_da_interface(pad_usb.interface_do_aparelho(str(uniq or "")))


def ancora_da_interface(interface: str | None) -> Ancora | None:
    """A âncora de uma interface de gadget (o ``usb_device`` é o pai da interface)."""
    if not interface:
        return None
    return Ancora(syspath=os.path.dirname(interface), declarado=interface)


def e_sem_porta(ancora: object) -> bool:
    """O nó é o do aparelho sem porta USB própria: sem âncora, sem o nome da Sony.

    TODAS-AS-FEATURES-VALEM-EM-TODO-MODO-LIGADO-01 (31/10/2026): o pad que não nasce no
    gadget (o modo Xbox e o Nintendo vão ao ``uinput``; o gadget que não enumerou) ainda
    tem a háptica fina, os efeitos e a ponte do rádio. O nó dele é só do Hefesto: nenhum
    jogo o acha pelo nome nem o casa com HID nenhum, e o engasgo de 14/10 não volta.
    """
    return isinstance(ancora, Ancora) and not ancora.declarado


def a_porta_e_dele(uniq: str, ancora: Ancora) -> bool:
    """A âncora é a interface do gadget DESTE aparelho, de pé agora?

    TODO-PAD-TEM-PORTA-PROPRIA-01 (14/10/2026), por ordem de produto: todo pad tem a
    porta USB virtual dele. O endpoint com o nome da Sony só nasce, e só se
    adota, na porta do próprio pad. A âncora emprestada (um hub,
    um dongle, de 18/09 a 14/10) dava ao jogo um áudio cujo ``ContainerId`` não
    casa com HID nenhum, e a biblioteca da Sony o varre sem parar: o engasgo
    de 12/10 e de 14/10, com 1 a 4 controles, em qualquer ordem e transporte.
    """
    return bool(ancora.declarado) and pad_usb.interface_do_aparelho(uniq) == ancora.declarado


ORDEM_PELO_ASSENTO = "assento"
ORDEM_PELO_ASSENTO_SEM_REFAZER = "assento-sem-refazer"
ORDEM_PELO_ENDERECO = "endereco"
ORDENS_DOS_NOS = (ORDEM_PELO_ASSENTO, ORDEM_PELO_ASSENTO_SEM_REFAZER, ORDEM_PELO_ENDERECO)
ORDEM_DOS_NOS = ORDEM_PELO_ASSENTO

INTERRUPTOR_DA_ORDEM_DOS_NOS = "HEFESTO_DUALSENSE4UNIX_ORDEM_DOS_NOS"


def ordem_dos_nos(ambiente: Mapping[str, str] | None = None) -> str:
    """A ordem que vale agora: a do interruptor, quando ele diz uma das três."""
    valor = (os.environ if ambiente is None else ambiente).get(INTERRUPTOR_DA_ORDEM_DOS_NOS, "")
    valor = str(valor).strip().lower()
    return valor if valor in ORDENS_DOS_NOS else ORDEM_DOS_NOS


def plano_da_ordem(
    marcas: Iterable[str],
    assento: Callable[[str], int | None],
    no_servidor: Mapping[str, int] | None = None,
    *,
    refazer: bool = True,
) -> tuple[list[str], list[str]]:
    """``(na_ordem, a_refazer)``: a ordem de nascimento e os nós de pé que renascem.

    ``assento(marca)`` é o número do jogador; ``no_servidor`` (marca → índice do
    módulo dele) são os nós que já existem, na ordem em que nasceram. Quem não
    tem assento vai para o fim; o empate fica na ordem da marca. Fica de pé o
    maior começo da lista do servidor que já é o começo de ``na_ordem``; o resto
    renasce atrás, e depois disso a lista do servidor É ``na_ordem`` (a volta
    seguinte não refaz nada). Função pura.
    """

    def chave(marca: str) -> tuple[int, int, str]:
        numero = assento(marca)
        if isinstance(numero, bool) or not isinstance(numero, int) or numero <= 0:
            return (1, 0, marca)
        return (0, numero, marca)

    na_ordem = sorted({str(m) for m in marcas}, key=chave)
    existentes = {m: i for m, i in (no_servidor or {}).items() if m in na_ordem}
    de_pe = sorted(existentes, key=lambda m: (existentes[m], m))
    fica = 0
    for marca, devida in zip(de_pe, na_ordem, strict=False):
        if marca != devida:
            break
        fica += 1
    return na_ordem, (de_pe[fica:] if refazer else [])


def nome_da_marca(marca: str) -> str:
    """O nome do nó do aparelho desta marca, ou "" quando a marca não tem essa forma."""
    if not isinstance(marca, str) or not marca.startswith(PREFIXO_DA_MARCA_DO_APARELHO):
        return ""
    letras = marca[len(PREFIXO_DA_MARCA_DO_APARELHO) :]
    if len(letras) != TAMANHO_DA_MARCA_DO_APARELHO or any(
        ch not in LETRAS_DA_MARCA_DO_APARELHO for ch in letras
    ):
        return ""
    nome = MOLDE_DO_NOME.format(marca=marca)
    return nome if len(nome) <= MAX_NOME else ""


def nome_sem_porta(marca: str) -> str:
    """O nome do nó do aparelho sem porta própria, ou "" quando a marca não tem a forma."""
    if not nome_da_marca(marca):
        return ""
    return MOLDE_DO_NOME_SEM_PORTA.format(marca=marca)


def nome_do_endpoint(uniq: str) -> str:
    """O nome do nó do controle ``uniq``, ou "" quando ele não dá identidade."""
    return nome_da_marca(marca_do_aparelho(uniq))


def rotulo_da_haptica(numero: int | None) -> str:
    """A FORMA A — «Háptica do Controle N (DualSense Wireless Controller)».

    **Decidido em 24/09/2026**, pelo padrão de produto fixado
    para o alto-falante e o microfone em 23/09 (A-FORJA-VALIDA-O-SOM-01, E6): o
    nome do controle na frente, o ``iProduct`` da Sony atrás, e nada de endereço. O
    rótulo de antes, «DualSense <hex6> (háptica)», punha o rabo do endereço do
    controle na lista de som da máquina — e fazia a máquina contar quatro placas
    DualSense onde há duas.

    ``None``, ``bool`` e número que não seja positivo valem como *"não sei o
    assento"*: sem número não se inventa número, e o rótulo sai sem ele.
    """
    base = NOME_DA_HAPTICA_DO_CONTROLE
    if isinstance(numero, int) and not isinstance(numero, bool) and numero > 0:
        base = f"{base} {numero}"
    return com_o_nome_da_sony(base)


def descricao_da_haptica(uniq: str) -> str:
    """O rótulo deste controle AGORA, com o assento perguntado ao DONO."""
    from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
        numero_do_assento,
    )

    return rotulo_da_haptica(numero_do_assento(str(uniq or "")))


def propriedades_do_endpoint(uniq: str, ancora: Ancora, rotulo: str | None = None) -> str:
    """O ``sink_properties=``, ENTRE ASPAS DUPLAS."""
    rotulo = descricao_da_haptica(uniq) if rotulo is None else rotulo
    campos = (
        *campos_da_identidade(ancora.declarado),
        *(() if e_sem_porta(ancora) else campos_do_nome()),
        f"device.description='{rotulo}'",
        f"priority.session={PRIORIDADE_DA_SESSAO}",
        f"priority.driver={PRIORIDADE_DO_RELOGIO}",
        "device.icon_name=audio-speakers",
        *campo_do_controle(uniq),
    )
    return 'sink_properties="' + " ".join(campos) + '"'


def endpoints_de_pe(
    runner: Callable[[list[str]], str | None] | None = None,
) -> dict[str, list[tuple[str, str]]]:
    """Os endpoints DESTA casa que estão de pé NO SERVIDOR, por nome de sink.

    Servidor mudo vira ``{}``; quem precisa distinguir «não há endpoint» de «não
    sei» usa :func:`endpoints_de_pe_ou_nada`.
    """
    return endpoints_de_pe_ou_nada(runner) or {}


def endpoints_de_pe_ou_nada(
    runner: Callable[[list[str]], str | None] | None = None,
) -> dict[str, list[tuple[str, str]]] | None:
    """Igual a :func:`endpoints_de_pe`, mas ``None`` quando o servidor não respondeu.

    **O servidor de som é a verdade, a memória é cache:** tirar um endpoint da
    memória porque ele não está na resposta só vale se houve resposta. ``{}`` é
    «o servidor disse que não há nenhum»; ``None``, «não sei».
    """
    chamar = runner or rodar_pactl
    saida = chamar(["pactl", "list", "short", "modules"])
    if saida is None or not any(
        linha.split("\t")[0].strip().isdigit() and "\t" in linha for linha in saida.splitlines()
    ):
        return None
    de_pe: dict[str, list[tuple[str, str]]] = {}
    for module_id, nome, caminho, _rotulo in _modulos_desta_casa(saida):
        de_pe.setdefault(nome, []).append((module_id, caminho))
    return de_pe


def _modulos_desta_casa(saida: str) -> list[tuple[str, str, str, str]]:
    """``(module_id, sink_name, sysfs.path, rótulo)`` de cada endpoint desta casa."""
    achados: list[tuple[str, str, str, str]] = []
    for linha in saida.splitlines():
        if _MODULO_NULL_SINK not in linha or MARCA_DO_NOME not in linha:
            continue
        if MARCA_DO_ENSAIO in linha:
            continue
        partes = linha.split("\t")
        if len(partes) < 3 or not partes[0].strip().isdigit():
            continue
        argv = partes[2]
        nome = ""
        caminho = ""
        for pedaco in argv.split():
            if pedaco.startswith("sink_name="):
                nome = pedaco[len("sink_name=") :]
            elif pedaco.startswith("sysfs.path="):
                caminho = pedaco[len("sysfs.path=") :]
        if not nome:
            continue
        rotulo = _ROTULO_NO_ARGUMENTO.search(argv)
        achados.append((partes[0].strip(), nome, caminho, rotulo.group(1) if rotulo else ""))
    return achados


def rotulo_no_ar(
    module_id: str, runner: Callable[[list[str]], str | None] | None = None
) -> str:
    """O rótulo com que o módulo ``module_id`` nasceu — ``""`` quando não se sabe."""
    chamar = runner or rodar_pactl
    saida = chamar(["pactl", "list", "short", "modules"]) or ""
    for achado_id, _nome, _caminho, rotulo in _modulos_desta_casa(saida):
        if achado_id == str(module_id):
            return rotulo
    return ""


def nasceu_com_o_relogio(
    module_id: str, runner: Callable[[list[str]], str | None] | None = None
) -> bool:
    """O módulo ``module_id`` nasceu com :data:`PRIORIDADE_DO_RELOGIO`? Sem resposta, True.

    O nó de antes desta cura (o daemon morto sem ``parar``) não se adota: ele
    deixaria o som do jogo no passo da placa até o servidor de som reiniciar.
    """
    chamar = runner or rodar_pactl
    for linha in (chamar(["pactl", "list", "short", "modules"]) or "").splitlines():
        partes = linha.split("\t")
        if len(partes) >= 3 and partes[0].strip() == str(module_id):
            return f"priority.driver={PRIORIDADE_DO_RELOGIO}" in partes[2]
    return True


def a_ancora_pode_ser_dele(uniq: str, caminho: str, outros: Iterable[str] = ()) -> bool:
    """A âncora declarada ``caminho`` é, ou ainda pode vir a ser, a porta do aparelho ``uniq``.

    É a porta registrada do aparelho; sem porta registrada, é um gadget
    (:func:`pad_usb.sob_o_vhci`) que não é a porta de nenhum dos ``outros``.
    """
    propria = pad_usb.interface_do_aparelho(uniq)
    if propria is not None:
        return propria == caminho
    return pad_usb.sob_o_vhci(caminho) and all(
        pad_usb.interface_do_aparelho(outro) != caminho for outro in outros
    )


def varrer_endpoints_orfaos(
    vivos: Iterable[str],
    runner: Callable[[list[str]], str | None] | None = None,
    *,
    de_pe: Mapping[str, Sequence[tuple[str, str]]] | None = None,
    sem_porta: Iterable[str] = (),
    na_mesa: Mapping[str, str] | None = None,
) -> list[str]:
    """Derruba todo endpoint desta casa (:data:`MARCA_DO_NOME`) que não é de aparelho vivo.

    Ficam o nó das marcas ``vivos`` (:func:`nome_da_marca`), o nó sem porta das ``sem_porta``
    e, dos aparelhos ``na_mesa`` (marca → ``uniq``), o nó cuja âncora pode ser a porta do
    aparelho (:func:`a_ancora_pode_ser_dele`), para o ``iniciar`` adotá-lo quando a porta
    montar. ``de_pe`` é a resposta de :func:`endpoints_de_pe` já lida na volta; sem a resposta,
    pergunta. Devolve os ``module_id`` derrubados.
    """
    chamar = runner or rodar_pactl
    esperados = (
        {nome_da_marca(marca) for marca in vivos} | {nome_sem_porta(m) for m in sem_porta}
    ) - {""}
    donos = {nome_da_marca(m): u for m, u in (na_mesa or {}).items()}
    caidos: list[str] = []
    servidor = endpoints_de_pe(chamar) if de_pe is None else de_pe
    for nome, instancias in servidor.items():
        if nome in esperados:
            continue
        for module_id, caminho in instancias:
            if nome in donos and a_ancora_pode_ser_dele(
                donos[nome], caminho, [u for u in donos.values() if u != donos[nome]]
            ):
                continue
            chamar(["pactl", "unload-module", module_id])
            caidos.append(module_id)
    if caidos:
        logger.info("haptica_endpoints_orfaos_derrubados", quantos=len(caidos))
    return caidos


class EndpointDeHaptica:
    """O nó de quatro canais que o JOGO enxerga como alto-falante do DualSense.

    **É DO APARELHO** (desde 02/10/2026, A-HAPTICA-E-POR-APARELHO-01; de 28/09
    a 02/10 era do lugar): ``uniq`` é o controle, e o nome, a âncora e o
    rótulo são dele. O controle chega pelo rádio (a ponte lê o monitor deste
    nó) ou pelo cabo (o laço leva o monitor à placa dele).

    **Não é o ``hefesto_som_<marca>``:** aquele é a saída da MÁQUINA para o
    controle — a pessoa o escolhe nas saídas de som, e o nome dele tem dono.
    Este aqui é o que o JOGO escolhe sozinho, pelo teste do GE, e o nome dele é
    ditado pelos patches. Só este casa com o teste, então o jogo não se
    confunde entre os dois.
    """

    marca: str = ""
    uniq: str = ""
    rotulo: str = ""

    def __init__(
        self,
        *,
        uniq: str,
        ancora: Ancora,
        runner: Callable[[list[str]], str | None] | None = None,
        canais: int = CANAIS_DA_HAPTICA,
        taxa_hz: int = TAXA_DO_ENDPOINT,
    ) -> None:
        self.uniq = str(uniq)
        self.marca = marca_do_aparelho(self.uniq)
        self.ancora = ancora
        self.nome = (
            nome_sem_porta(self.marca) if e_sem_porta(ancora) else nome_da_marca(self.marca)
        )
        self.canais = canais
        self.taxa_hz = taxa_hz
        self.runner = runner or rodar_pactl
        self._module_id: str | None = None
        self.rotulo = ""

    @property
    def module_id(self) -> str | None:
        return self._module_id

    @property
    def monitor(self) -> str:
        """O monitor de onde a ponte e o laço do cabo leem o PCM da háptica."""
        return f"{self.nome}.monitor" if self.nome else ""

    def no_ar(
        self, de_pe: Mapping[str, Sequence[tuple[str, str]]] | None = None
    ) -> bool | None:
        """O módulo deste endpoint existe no SERVIDOR? ``None`` = não sei.

        ``de_pe`` é a resposta de :func:`endpoints_de_pe_ou_nada` que quem chama
        já tem (a volta pergunta uma vez para todos).
        """
        if self._module_id is None:
            return False
        servidor = endpoints_de_pe_ou_nada(self.runner) if de_pe is None else de_pe
        if servidor is None:
            return None
        return any(m == self._module_id for m, _caminho in servidor.get(self.nome, ()))

    def iniciar(self) -> bool:
        """Publica o nó. Idempotente CONTRA O SERVIDOR; False quando não deu.

        **O servidor é a verdade, a memória é cache:** com o módulo na memória,
        só devolve ``True`` se o servidor ainda o tem (ou não soube dizer); módulo
        tirado por fora zera a memória e o nó é adotado ou sobe de novo.
        """
        if self._module_id is not None:
            if self.no_ar() is not False:
                return True
            logger.warning(
                "haptica_endpoint_sumiu_por_fora", controle=self.marca, module_id=self._module_id
            )
            self._module_id = None
            self.rotulo = ""
        if not self.nome:
            logger.info("haptica_endpoint_sem_identidade")
            return False
        if not e_sem_porta(self.ancora) and not a_porta_e_dele(self.uniq, self.ancora):
            logger.warning(
                "haptica_endpoint_recusa_porta_alheia",
                controle=self.marca,
                ancora=self.ancora.syspath,
            )
            return False
        instancias = endpoints_de_pe(self.runner).get(self.nome, [])
        iguais = [
            m
            for m, caminho in instancias
            if caminho == self.ancora.declarado and nasceu_com_o_relogio(m, self.runner)
        ]
        if iguais:
            self._module_id = iguais[0]
            for sobrando in [m for m, _ in instancias if m != iguais[0]]:
                self.runner(["pactl", "unload-module", sobrando])
            self.rotulo = rotulo_no_ar(iguais[0], self.runner)
            logger.info(
                "haptica_endpoint_adotado",
                controle=self.marca,
                sink=self.nome,
                derrubados=len(instancias) - 1,
            )
            return True
        for velho, _caminho in instancias:
            self.runner(["pactl", "unload-module", velho])
        if instancias:
            logger.info(
                "haptica_endpoint_de_ancora_velha_derrubado",
                controle=self.marca,
                quantos=len(instancias),
            )
        if not self._carregar(self.rotulo_de_agora()):
            logger.warning("haptica_endpoint_nao_subiu", controle=self.marca)
            return False
        logger.info(
            "haptica_endpoint_publicado",
            controle=self.marca,
            sink=self.nome,
            ancora=self.ancora.syspath,
        )
        return True

    def _carregar(self, rotulo: str) -> bool:
        """Um ``load-module`` com este rótulo. True = o servidor devolveu o id."""
        saida = self.runner(
            [
                "pactl",
                "load-module",
                _MODULO_NULL_SINK,
                f"sink_name={self.nome}",
                "format=float32le",
                f"rate={self.taxa_hz}",
                f"channels={self.canais}",
                "channel_map=front-left,front-right,rear-left,rear-right",
                propriedades_do_endpoint(self.uniq, self.ancora, rotulo),
            ]
        )
        linhas = [ln.strip() for ln in (saida or "").splitlines() if ln.strip()]
        if not linhas or not linhas[-1].isdigit():
            return False
        self._module_id = linhas[-1]
        self.rotulo = rotulo
        self._ligar_os_motores()
        return True


    def rotulo_de_agora(self) -> str:
        """O rótulo que este nó teria se nascesse AGORA; o sem porta sai sem o nome da Sony."""
        rotulo = descricao_da_haptica(self.uniq)
        return sem_o_nome_da_sony(rotulo) if e_sem_porta(self.ancora) else rotulo

    def rotulo_envelheceu(self) -> bool:
        """O rótulo no ar ficou para trás do número de agora? Nunca levanta."""
        return bool(self._rotulo_novo())

    def _rotulo_novo(self) -> str:
        """O rótulo de agora, se o do ar envelheceu; ``""`` se não há o que trocar."""
        if self._module_id is None or not self.rotulo:
            return ""
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            rotulo_envelheceu,
        )

        try:
            de_agora = self.rotulo_de_agora()
            return de_agora if rotulo_envelheceu(self.rotulo, de_agora) else ""
        except Exception:  # pragma: no cover
            logger.debug("haptica_rotulo_de_agora_ilegivel", controle=self.marca, exc_info=True)
            return ""

    def renovar_o_rotulo(self) -> bool:
        """O nó renasce com o rótulo de agora. True só quando renasceu com ele."""
        module_id = self._module_id
        de_agora = self._rotulo_novo()
        if module_id is None or not de_agora:
            return False
        velho = self.rotulo
        self.runner(["pactl", "unload-module", module_id])
        self._module_id = None
        if self._carregar(de_agora):
            logger.info(
                "haptica_rotulo_renovado", controle=self.marca, no_ar=velho, de_agora=de_agora
            )
            return True
        logger.warning("haptica_rotulo_novo_nao_subiu", controle=self.marca, de_agora=de_agora)
        if self._carregar(velho):
            logger.info("haptica_endpoint_voltou_com_o_rotulo_velho", controle=self.marca)
        else:
            self.rotulo = ""
            logger.warning("haptica_endpoint_sumiu_ao_renovar", controle=self.marca)
        return False

    def _ligar_os_motores(self) -> None:
        """Os quatro canais do nó em :data:`VOLUME_DOS_MOTORES` (a placa cheia).

        OS-QUATRO-EM-HARMONIA-01, item 1: o nó nasce com os 40 % do WirePlumber, e
        volume por canal no sink não é onde mora volume nenhum do Hefesto.
        """
        try:
            self.runner(["pactl", "set-sink-volume", self.nome, *[VOLUME_DOS_MOTORES] * 4])
        except Exception as exc:  # pragma: no cover
            logger.warning("haptica_motores_sem_volume", controle=self.marca, err=str(exc))
            return
        logger.info("haptica_motores_ligados", controle=self.marca, volume=VOLUME_DOS_MOTORES)

    def parar(self) -> None:
        """Derruba o nó. Silencioso quando ele já não está de pé."""
        if self._module_id is None:
            return
        self.runner(["pactl", "unload-module", self._module_id])
        logger.info("haptica_endpoint_derrubado", controle=self.marca, sink=self.nome)
        self._module_id = None

    def __enter__(self) -> EndpointDeHaptica:
        self.iniciar()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.parar()


FREQUENCIA_DO_FORTE_HZ = 60
FREQUENCIA_DO_FRACO_HZ = 160

QUADROS_POR_BLOCO = 480

QUADROS_DO_CICLO = 2400

FOLGA_DO_TOCADOR_S = 3.0

LATENCIA_DO_TOCADOR_MS = 20

RECUSA_DO_TOCADOR_S = 60.0

RECUO_INICIAL_DO_TOCADOR_S = 1.0

VIVO_QUE_ZERA_O_RECUO_S = 10.0

PRAZO_DO_NO_RENOVADO_S = 3.0

SAIDAS_SEM_RECUSA = frozenset({"silencio", "trocou_de_endpoint", "parado", "no_renovado"})

SAIDAS_QUE_ZERAM_O_RECUO = frozenset({"silencio", "trocou_de_endpoint"})

PRAZO_DA_ESCRITA_S = 1.0

CANO_DO_TOCADOR = 4096

ESPERAS_DA_CONFERENCIA_S: tuple[float, ...] = (0.3, 0.7, 1.0)

MARCA_DO_TOCADOR = "hefesto-haptica-do-rumble-"

_TAXA = TAXA_DO_ENDPOINT
_BYTES_POR_QUADRO = 4 * CANAIS_DA_HAPTICA


def _seno(frequencia: int) -> array[float]:
    return array(
        "f",
        (math.sin(2.0 * math.pi * frequencia * i / _TAXA) for i in range(QUADROS_DO_CICLO)),
    )


_SENO_DO_FORTE = np.array(_seno(FREQUENCIA_DO_FORTE_HZ), dtype=np.float64)
_SENO_DO_FRACO = np.array(_seno(FREQUENCIA_DO_FRACO_HZ), dtype=np.float64)
_BLOCO_MUDO = bytes(QUADROS_POR_BLOCO * _BYTES_POR_QUADRO)
_FLOAT32_LE = np.dtype("<f4")

TETO_DA_MISTURA = 0.9
JOELHO_DA_MISTURA = 0.85
ATAQUE_DO_LIMITADOR_QUADROS = 48
SOLTURA_DO_LIMITADOR_S = 0.08
LEITURA_DO_GANHO_S = 0.5


class LimitadorSuave:
    """O limitador da soma do bloco: um ganho por canal, com ataque e soltura, e um joelho.

    O teto de cada canal é dele (``tetos``). O ganho desce até o teto sobre o pico do bloco em
    :data:`ATAQUE_DO_LIMITADOR_QUADROS` quadros e sobe de volta em :data:`SOLTURA_DO_LIMITADOR_S`;
    o que ainda passa do teto no ataque entra no joelho (``tanh``), que acaba no teto sem quina.
    Sob o joelho e com o ganho em 1, o bloco sai o mesmo objeto, byte a byte. O estado é de
    UM tocador: quem chama é o fio de escrita dele, um bloco de cada vez.
    """

    def __init__(self, canais: int = CANAIS_DA_HAPTICA, taxa: int = _TAXA) -> None:
        self._ganho = np.ones(canais, dtype=np.float64)
        self._taxa = int(taxa)

    @property
    def ganho(self) -> np.ndarray:
        """O ganho de cada canal no fim do último bloco (1 = sem redução)."""
        return self._ganho.copy()

    def passar(self, quadros: np.ndarray, tetos: np.ndarray) -> np.ndarray:
        """``quadros`` (n, canais) em ``float64`` sob ``tetos`` (canais); nunca passa do teto."""
        n = len(quadros)
        joelho = tetos * JOELHO_DA_MISTURA
        pico = np.abs(quadros).max(axis=0) if n else np.zeros_like(tetos)
        if not n or (bool((self._ganho == 1.0).all()) and bool((pico <= joelho).all())):
            return quadros
        alvo = np.where(pico > tetos, tetos / np.maximum(pico, 1e-12), 1.0)
        antes = self._ganho
        descendo = alvo < antes
        subida = 1.0 - math.exp(-n / (self._taxa * SOLTURA_DO_LIMITADOR_S))
        fim = np.where(descendo, alvo, antes + (alvo - antes) * subida)
        fim = np.where(fim > 1.0 - 1e-4, 1.0, fim)
        passos = np.where(descendo, min(n, ATAQUE_DO_LIMITADOR_QUADROS), n)
        andado = np.minimum((np.arange(1, n + 1, dtype=np.float64)[:, None]) / passos, 1.0)
        z = quadros * (antes + (fim - antes) * andado)
        self._ganho = fim
        absoluto = np.abs(z)
        folga = tetos - joelho
        sobre = absoluto > joelho
        if not bool(sobre.any()):
            return z
        dobrado = joelho + folga * np.tanh((absoluto - joelho) / folga)
        return np.copysign(np.where(sobre, dobrado, absoluto), z)


def ganho_do_perfil(dono: str) -> float:
    """O fator linear da háptica do controle ``dono`` (o do perfil que vale); 1 sem dono."""
    from hefesto_dualsense4unix.daemon.ganho_da_haptica import GANHO

    return float(GANHO.fator(dono or None))


def rotulo_do_tocador(marca: str) -> str:
    """O ``node.name`` do tocador do aparelho desta marca. Sem endereço: a marca não é."""
    return f"{MARCA_DO_TOCADOR}{str(marca).lower()}"


def _amplitude(nivel: int) -> float:
    return max(0, min(255, int(nivel))) / 255.0


def bloco_da_haptica(
    fraco: int,
    forte: int,
    *,
    fase: int = 0,
    antes: tuple[int, int] | None = None,
) -> bytes:
    """Um bloco de :data:`QUADROS_POR_BLOCO` quadros, ``float32le``, FL FR RL RR."""
    fraco0, forte0 = antes if antes is not None else (fraco, forte)
    a0, a1 = _amplitude(forte0), _amplitude(forte)
    b0, b1 = _amplitude(fraco0), _amplitude(fraco)
    if not (a0 or a1 or b0 or b1):
        return _BLOCO_MUDO
    indices, rampa_a, rampa_b = _rampas(fase, a0, a1, b0, b1)
    return _quadros_de(rampa_a * _SENO_DO_FORTE[indices], rampa_b * _SENO_DO_FRACO[indices])


def _rampas(
    fase: int, a0: float, a1: float, b0: float, b1: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Os índices no ciclo e as duas rampas do bloco: de ``a0`` a ``a1`` e de ``b0`` a ``b1``."""
    n = QUADROS_POR_BLOCO
    passos = np.arange(n, dtype=np.float64)
    indices = (int(fase) % QUADROS_DO_CICLO + np.arange(n)) % QUADROS_DO_CICLO
    return indices, a0 + (a1 - a0) / n * passos, b0 + (b1 - b0) / n * passos


def _quadros_de(forte: np.ndarray, fraco: np.ndarray) -> bytes:
    """O bloco ``float32le`` com o forte no canal 2 e o fraco no 3."""
    quadros = np.zeros((len(forte), CANAIS_DA_HAPTICA), dtype=_FLOAT32_LE)
    quadros[:, 2] = forte
    quadros[:, 3] = fraco
    return quadros.tobytes()


def _rms(valores: np.ndarray) -> float:
    """O RMS pela soma do Python (compensada): a subida do timbre empata pela mesma conta."""
    if not len(valores):
        return 0.0
    return math.sqrt(sum((valores * valores).tolist()) / len(valores))


def _canal_que_nao_perde(timbre: np.ndarray, seno: np.ndarray) -> np.ndarray:
    """O canal com timbre, nunca com menos energia que o seno de hoje no mesmo bloco.

    Abaixo do seno, o timbre sobe (saturando em 1, o que só o engrossa) até a energia dele; se
    nem assim chega, o canal fica no seno. O jogo manda: o timbre só potencializa.
    """
    alvo, tem = _rms(seno), _rms(timbre)
    if tem >= alvo:
        return timbre
    if tem <= 0.0:
        return seno
    ganho = alvo / tem
    for _ in range(_SUBIDAS_DO_TIMBRE):
        subido = np.clip(timbre * ganho, -1.0, 1.0)
        if _rms(subido) >= alvo:
            return subido
        ganho *= 1.5
    return seno


_SUBIDAS_DO_TIMBRE = 8


def bloco_com_timbre(
    fraco: int,
    forte: int,
    timbre: str | None,
    *,
    fase: int = 0,
    antes: tuple[int, int] | None = None,
) -> bytes:
    """O :func:`bloco_da_haptica` no timbre pedido; ``timbre=None`` é ele, byte a byte."""
    if timbre is None:
        return bloco_da_haptica(fraco, forte, fase=fase, antes=antes)
    fraco0, forte0 = antes if antes is not None else (fraco, forte)
    a0, a1 = _amplitude(forte0), _amplitude(forte)
    b0, b1 = _amplitude(fraco0), _amplitude(fraco)
    if not (a0 or a1 or b0 or b1):
        return _BLOCO_MUDO
    indices, rampa_a, rampa_b = _rampas(fase, a0, a1, b0, b1)
    do_forte, do_fraco = (
        np.asarray(c, dtype=np.float64)[indices]
        for c in formas.ciclos_do_timbre(timbre, QUADROS_DO_CICLO, _TAXA)
    )
    return _quadros_de(
        _canal_que_nao_perde(rampa_a * do_forte, rampa_a * _SENO_DO_FORTE[indices]),
        _canal_que_nao_perde(rampa_b * do_fraco, rampa_b * _SENO_DO_FRACO[indices]),
    )


FREQUENCIA_DO_TOQUE_HZ = formas.FORMAS[formas.TOQUE].componentes[0][0]
ATAQUE_DO_TOQUE_MS = formas.FORMAS[formas.TOQUE].ataque_ms
QUADROS_DO_CORPO_NA_FILA = _TAXA // 10
TIQUES_DO_TATO_POR_S = 60
ALVO_DO_CORPO_NA_FILA = 2 * _TAXA // TIQUES_DO_TATO_POR_S
VALIDADE_DOS_LADOS_S = 1.0
CANAIS_DO_LADO: dict[str, tuple[int, ...]] = {
    "esquerdo": (2,),
    "direito": (3,),
    "centro": (2, 3),
}


def forma_do_toque(
    energia: float, duracao_ms: int, forma: str = formas.TOQUE
) -> array[float]:
    """As amostras de UM toque na forma pedida (o Toque seco, se nada se pede)."""
    return formas.amostras(forma, energia, duracao_ms, _TAXA)


def misturar_o_toque(
    bloco: bytes, toque: array[float] | np.ndarray, inicio: int, canais: tuple[int, ...]
) -> bytes:
    """Soma o trecho ``inicio`` do toque aos ``canais`` do bloco; o teto é do limitador."""
    quadros = np.frombuffer(bloco, dtype=_FLOAT32_LE).reshape(-1, CANAIS_DA_HAPTICA)
    k = max(0, min(len(quadros), len(toque) - inicio))
    if not k:
        return bloco
    trecho = np.asarray(toque[inicio:inicio + k], dtype=np.float64)
    soma = quadros.copy()
    for canal in canais:
        soma[:k, canal] = quadros[:k, canal].astype(np.float64) + trecho
    return soma.tobytes()


def somar_os_corpos(
    bloco: bytes, corpos: Sequence[tuple[array[float], tuple[int, ...]]]
) -> bytes:
    """Soma ao bloco o trecho de cada fila do corpo nos canais do próprio lado, sem cortar."""
    quadros = np.frombuffer(bloco, dtype=_FLOAT32_LE).reshape(-1, CANAIS_DA_HAPTICA)
    soma = quadros.astype(np.float64)
    for trecho, canais in corpos:
        k = min(len(quadros), len(trecho))
        valores = np.asarray(trecho[:k], dtype=np.float64)
        for canal in canais:
            soma[:k, canal] += valores
    return soma.astype(_FLOAT32_LE).tobytes()


def somar_os_lados(
    bloco: bytes, lados: tuple[int, int], antes: tuple[int, int], fase: int
) -> bytes:
    """Soma o nível de cada motor ao canal dele: o esquerdo no 2 e o direito no 3."""
    camada = np.frombuffer(
        bloco_da_haptica(lados[1], lados[0], fase=fase, antes=antes[::-1]), dtype=_FLOAT32_LE
    ).reshape(-1, CANAIS_DA_HAPTICA)
    for canal in (*CANAIS_DO_LADO["esquerdo"], *CANAIS_DO_LADO["direito"]):
        bloco = misturar_o_toque(bloco, camada[:, canal], 0, (canal,))
    return bloco


def argv_do_tocador(
    sink: str,
    rotulo: str,
    runner: Callable[[list[str]], str | None] | None = None,
) -> list[str]:
    """O comando que toca PCM cru no endpoint ``sink``. ``[]`` = não há como."""
    if not sink or not rotulo:
        return []
    recuo_proibido = (
        "node.dont-fallback=true",
        "node.dont-reconnect=true",
        "state.restore-target=false",
        "state.restore-props=false",
    )
    if shutil.which("pw-cat") is not None:
        serial = serial_do_no(sink) if o_servidor_e_o_pipewire(runner) else None
        if serial is not None:
            return [
                "pw-cat", "--playback", "--raw",
                f"--target={serial}",
                f"--rate={_TAXA}", f"--channels={CANAIS_DA_HAPTICA}", "--format=f32",
                "--channel-map=FL,FR,RL,RR", f"--latency={LATENCIA_DO_TOCADOR_MS}ms",
                "--volume=1.0",
                "-P", " ".join((f"node.name={rotulo}", f"media.name={rotulo}", *recuo_proibido)),
                "-",
            ]
    if shutil.which("pacat") is not None:
        return [
            "pacat", "--playback", "--raw", f"--device={sink}",
            f"--rate={_TAXA}", f"--channels={CANAIS_DA_HAPTICA}", "--format=float32le",
            "--channel-map=front-left,front-right,rear-left,rear-right",
            f"--latency-msec={LATENCIA_DO_TOCADOR_MS}", "--volume=65536",
            f"--client-name={rotulo}", f"--stream-name={rotulo}",
            f"--property=node.name={rotulo}",
            *(f"--property={p}" for p in recuo_proibido),
        ]
    return []


def conferir_o_destino_do_tocador(
    rotulo: str, ler_o_grafo: Callable[[], str | None] | None = None
) -> str | None:
    """O ``node.name`` do nó a que o tocador chamado ``rotulo`` se ligou. ``None`` = não sei.

    O grafo vem do dono dele (:func:`porta_do_som.ler_o_grafo`), com a guarda da suíte
    e o prazo dele; sem grafo, ou ilegível, «não sei».
    """
    if not rotulo:
        return None
    objetos = porta_do_som.lista_do_json((ler_o_grafo or porta_do_som.ler_o_grafo)())
    if objetos is None:
        return None
    nomes: dict[int, str] = {}
    meus: set[int] = set()
    for o in objetos:
        if not isinstance(o, dict) or o.get("type") != "PipeWire:Interface:Node":
            continue
        ident = o.get("id")
        props = (o.get("info") or {}).get("props") or {}
        if not isinstance(ident, int):
            continue
        nome = str(props.get("node.name") or "")
        nomes[ident] = nome
        if nome == rotulo:
            meus.add(ident)
    if not meus:
        return None
    for o in objetos:
        if not isinstance(o, dict) or o.get("type") != "PipeWire:Interface:Link":
            continue
        info = o.get("info") or {}
        if info.get("output-node-id") in meus:
            destino = info.get("input-node-id")
            if isinstance(destino, int):
                return nomes.get(destino) or None
    return None


def fluxos_nos_endpoints(
    nomes: Iterable[str],
    runner: Callable[[list[str]], str | None] | None = None,
) -> tuple[frozenset[str], frozenset[str]] | None:
    """``(clientes dos nossos tocadores, endpoints com fluxo de outro)``. ``None`` = não sei."""
    alvos = {n for n in nomes if n}
    if not alvos:
        return frozenset(), frozenset()
    chamar = runner or rodar_pactl
    sinks = chamar(["pactl", "list", "short", "sinks"])
    if sinks is None:
        return None
    por_indice: dict[str, str] = {}
    for linha in sinks.splitlines():
        campos = linha.split("\t")
        if len(campos) > 1 and campos[1] in alvos:
            por_indice[campos[0].strip()] = campos[1]
    if not por_indice:
        return frozenset(), frozenset()
    fluxos = porta_do_som.ler_fluxos("sink-inputs", chamar)
    if fluxos is None:
        return None
    nossos: set[str] = set()
    com_outro: set[str] = set()
    for fluxo in fluxos:
        cliente = fluxo.cliente
        nosso = any(
            MARCA_DO_TOCADOR in fluxo.propriedades.get(chave, "")
            for chave in ("node.name", "media.name")
        )
        alvo = por_indice.get(fluxo.alvo)
        if alvo is None:
            continue
        sem_cliente = cliente in ("", "n/a", "-")
        if nosso:
            if not sem_cliente:
                nossos.add(cliente)
        elif not sem_cliente:
            com_outro.add(alvo)
    return frozenset(nossos), frozenset(com_outro)


def escrever_o_bloco(
    fd: int,
    dados: bytes,
    fim: threading.Event,
    relogio: Callable[[], float],
    *,
    continuar_no_cheio: bool,
) -> str:
    """Escreve ``dados`` inteiro no cano ``fd`` e devolve ``""``; senão o motivo do fim.

    ``parado`` quando ``fim`` se armou no meio (o ``parar()``), ``parou_de_ler`` quando o cano
    fechou, deu erro ou ficou cheio por :data:`PRAZO_DA_ESCRITA_S`. ``continuar_no_cheio`` volta
    a esperar o cano no ``BlockingIOError``; sem ele, a volta escreve zero e segue.
    """
    vista = memoryview(dados)
    espera = select.poll()
    espera.register(fd, select.POLLOUT)
    parado_desde: float | None = None

    def falhou() -> str:
        return "parado" if fim.is_set() else "parou_de_ler"

    while vista and not fim.is_set():
        try:
            prontos = espera.poll(100)
        except (OSError, ValueError):
            return falhou()
        if any(ev & (select.POLLERR | select.POLLHUP | select.POLLNVAL) for _, ev in prontos):
            return falhou()
        if not prontos:
            agora = relogio()
            parado_desde = agora if parado_desde is None else parado_desde
            if agora - parado_desde >= PRAZO_DA_ESCRITA_S:
                return falhou()
            continue
        parado_desde = None
        try:
            escritos = os.write(fd, vista)
        except BlockingIOError:
            if continuar_no_cheio:
                continue
            escritos = 0
        except OSError:
            return falhou()
        vista = vista[escritos:]
    return "" if not vista else falhou()


class RecuoDoTocador:
    """Quanto um tocador espera antes de tentar de novo, e por quê.

    A falha que pode passar (o processo que morre, que não sobe, que para de ler) espera 1, 2,
    4 s, até :data:`RECUSA_DO_TOCADOR_S`; ``fixo`` (não há tocador instalado, o nó errado) espera
    o teto de uma vez. Quem usa segura a própria trava.
    """

    def __init__(self, relogio: Callable[[], float]) -> None:
        self._relogio = relogio
        self.ate = float("-inf")
        self.motivo = ""
        self._seguidas = 0

    @property
    def vale(self) -> bool:
        """A recusa vale agora."""
        return self._relogio() < self.ate

    def recusar(self, motivo: str, *, fixo: bool = False) -> float:
        """Arma a recusa e devolve a espera, em segundos."""
        if fixo:
            espera = RECUSA_DO_TOCADOR_S
        else:
            espera = min(RECUO_INICIAL_DO_TOCADOR_S * 2 ** self._seguidas, RECUSA_DO_TOCADOR_S)
            self._seguidas += 1
        self.ate = self._relogio() + espera
        self.motivo = str(motivo)
        return espera

    def zerar(self) -> None:
        """O tocador tocou de verdade: a próxima falha volta ao primeiro degrau."""
        self._seguidas = 0


def motivo_da_saida(
    motivo: str, *, parado: bool, renovado: bool, vivo_s: float | None, recuo: RecuoDoTocador
) -> str:
    """O motivo com que o tocador saiu, já lido: o fim pedido é ``parado``, a perda do nó que o
    próprio dono recriou é ``no_renovado``; o tocador que tocou o bastante zera o recuo."""
    if parado:
        return "parado"
    if renovado and motivo not in SAIDAS_SEM_RECUSA:
        motivo = "no_renovado"
    if motivo in SAIDAS_QUE_ZERAM_O_RECUO or (
        vivo_s is not None and vivo_s >= VIVO_QUE_ZERA_O_RECUO_S
    ):
        recuo.zerar()
    return motivo


class TocadorDoRumble:
    """O rumble do jogo tocado como háptica no endpoint de UM aparelho."""

    def __init__(
        self,
        marca: str,
        *,
        ao_mudar: Callable[[], object] | None = None,
        argv_de: Callable[[str, str], list[str]] | None = None,
        lancar: Callable[..., Any] | None = None,
        conferir: Callable[[str], str | None] | None = None,
        folga_s: float = FOLGA_DO_TOCADOR_S,
        relogio: Callable[[], float] = time.monotonic,
        ganho_da_via: Callable[[str], float] | None = None,
    ) -> None:
        self.marca = str(marca)
        self.rotulo = rotulo_do_tocador(self.marca)
        self._ao_mudar = ao_mudar
        self._argv_de = argv_de or argv_do_tocador
        self._lancar: Callable[..., Any] = lancar or lancar_filho
        self._conferir = conferir or conferir_o_destino_do_tocador
        self._folga_s = float(folga_s)
        self._relogio = relogio
        self._trava = threading.Lock()
        self._nivel: tuple[int, int] = (0, 0)
        self._sink = ""
        self._dono = ""
        self._proc: Any = None
        self._vivo = False
        self._vivo_desde: float | None = None
        self._recuo = RecuoDoTocador(relogio)
        self._renasce_ate = float("-inf")
        self._acordar = threading.Event()
        self._fim = threading.Event()
        self._fio: threading.Thread | None = None
        self._memoria: dict[tuple[int, int, int, str | None], bytes] = {}
        self._linha = classe_do_rumble.LinhaDoTempo()
        self._vestido: tuple[str | None, str | None] = (None, None)
        self._onda: str | None = None
        self._toque: tuple[array[float], tuple[int, ...]] | None = None
        self._toque_pos = 0
        self._toque_longo = False
        self._toque_em_laco = False
        self._corpos: dict[tuple[str, str], array[float]] = {}
        self._lados: tuple[int, int] = (0, 0)
        self._lados_antes: tuple[int, int] = (0, 0)
        self._lados_valem_ate = 0.0
        self._limitador = LimitadorSuave()
        self._ganho_da_via = ganho_da_via or ganho_do_perfil
        self._ganho_lido: tuple[float, str, float] = (-LEITURA_DO_GANHO_S, "", 1.0)


    @property
    def nivel(self) -> tuple[int, int]:
        """O par ``(fraco, forte)`` que o tocador está tocando agora."""
        return self._nivel

    @property
    def dono(self) -> str:
        """O ``uniq`` de quem pediu o nível de agora."""
        return self._dono

    @property
    def sink(self) -> str:
        return self._sink

    @property
    def vivo(self) -> bool:
        """De pé e escrevendo no endpoint — o processo, e não a lembrança."""
        proc = self._proc
        return bool(self._vivo and proc is not None and proc.poll() is None)

    @property
    def recusado(self) -> bool:
        """O tocador recusou e ainda não tenta de novo: o que se pede a ele não toca."""
        return self._recuo.vale

    @property
    def motivo_da_recusa(self) -> str:
        """Por que recusou, enquanto a recusa vale; vazio sem recusa."""
        return self._recuo.motivo if self._recuo.vale else ""

    def o_no_vai_renascer(self) -> None:
        """Quem é dono do nó vai derrubá-lo e recriá-lo: o tocador que perder o nó agora troca
        de endpoint, sem recusa, e volta no nó novo."""
        self._renasce_ate = self._relogio() + PRAZO_DO_NO_RENOVADO_S
        self._acordar.set()


    def levar(
        self,
        fraco: int,
        forte: int,
        *,
        sink: str,
        dono: str,
        estilo: str | None = None,
        forma: str | None = None,
        onda: str | None = None,
    ) -> None:
        """O nível de agora, com o estilo e a forma do timbre. Nunca espera, nunca levanta."""
        par = (max(0, min(255, int(fraco))), max(0, min(255, int(forte))))
        with self._trava:
            if str(dono or "") != self._dono:
                self._linha = classe_do_rumble.LinhaDoTempo()
            self._linha.anotar(self._relogio(), par[0], par[1], onda)
            self._vestido, self._onda = (estilo, forma), onda
            self._nivel = par
            self._sink = str(sink or "")
            self._dono = str(dono or "")
            if any(par) and not self._fim.is_set() and (
                self._fio is None or not self._fio.is_alive()
            ):
                self._fio = threading.Thread(
                    target=self._correr, name=f"hefesto-{self.rotulo}", daemon=True
                )
                self._fio.start()
        self._acordar.set()

    def calar(self) -> None:
        """Nível zero: o tocador fica a folga de pé e sai."""
        with self._trava:
            self._nivel = (0, 0)
            self._linha.anotar(self._relogio(), 0, 0)
        self._acordar.set()

    def tocar_o_toque(
        self,
        energia: float,
        lado: str,
        duracao_ms: int,
        *,
        sink: str,
        dono: str,
        forma: str = formas.TOQUE,
    ) -> None:
        """Um toque por cima do nível de agora. Nunca espera, nunca levanta.

        Uma forma longa (Guarda, Aparo) em curso não é cortada por toque nenhum: o novo pedido
        cai, e a fila do rádio não ganha um segundo toque por cima do primeiro. Ele cai antes da
        conta das amostras, que roda no fio de quem pede.
        """
        with self._trava:
            if self._toque is not None and self._toque_longo:
                return
        amostras = forma_do_toque(energia, duracao_ms, forma)
        canais = CANAIS_DO_LADO.get(lado, CANAIS_DO_LADO["centro"])
        with self._trava:
            if self._toque is not None and self._toque_longo:
                return
            self._toque = (amostras, canais)
            self._toque_pos = 0
            self._toque_longo = forma in formas.FORMAS_LONGAS
            self._sink = str(sink or "")
            self._dono = str(dono or self._dono)
            self._garantir_o_fio()
        self._acordar.set()

    def tocar_em_laco(
        self, amostras: array[float], lado: str, *, sink: str, dono: str, forma: str
    ) -> None:
        """As amostras voltam do começo até :meth:`soltar_o_laco`; nenhum toque as corta."""
        if not len(amostras):
            return
        canais = CANAIS_DO_LADO.get(lado, CANAIS_DO_LADO["centro"])
        with self._trava:
            self._toque = (amostras, canais)
            self._toque_pos = 0
            self._toque_longo = True
            self._toque_em_laco = True
            self._sink = str(sink or "")
            self._dono = str(dono or self._dono)
            self._garantir_o_fio()
        self._acordar.set()

    def soltar_o_laco(self) -> None:
        """O laço do teste cala na hora; um toque comum em curso segue."""
        with self._trava:
            if self._toque_em_laco:
                self._toque = None
                self._toque_longo = False
                self._toque_em_laco = False
        self._acordar.set()

    @property
    def tocando_em_laco(self) -> bool:
        return self._toque_em_laco

    def levar_o_corpo(
        self, amostras: array[float], lado: str, *, sink: str, dono: str, fonte: str = ""
    ) -> None:
        """O pedaço da ``fonte`` no ``lado``, atrás do que já espera na própria fila.

        Cada fonte e lado tem a fila dele, com o teto dele; o bloco soma todas. A fila que
        esvaziou (o bloco tocou zeros no lugar, ou ia tocar) volta com no máximo
        :data:`ALVO_DO_CORPO_NA_FILA`: o que passa sai do lado mais velho, e o atraso de um
        soluço não fica. Nunca espera, nunca levanta.
        """
        if not len(amostras):
            return
        chave = (str(fonte), lado if lado in CANAIS_DO_LADO else "centro")
        with self._trava:
            teto = QUADROS_DO_CORPO_NA_FILA if chave in self._corpos else ALVO_DO_CORPO_NA_FILA
            fila = self._corpos.setdefault(chave, array("f"))
            fila.extend(amostras)
            sobra = len(fila) - teto
            if sobra > 0:
                del fila[:sobra]
            self._sink = str(sink or "")
            self._dono = str(dono or self._dono)
            self._garantir_o_fio()
        self._acordar.set()

    def levar_os_lados(self, esquerdo: int, direito: int, *, sink: str, dono: str) -> None:
        """O padrão do gatilho: um nível por motor, somado ao rumble e ao corpo.

        Vale até o prazo: quem pediu pode sumir no meio, e o motor nunca fica preso.
        """
        par = (max(0, min(255, int(esquerdo))), max(0, min(255, int(direito))))
        with self._trava:
            self._lados = par
            self._lados_valem_ate = self._relogio() + VALIDADE_DOS_LADOS_S
            if any(par):
                self._sink = str(sink or "")
                self._dono = str(dono or self._dono)
                self._garantir_o_fio()
        self._acordar.set()

    def _garantir_o_fio(self) -> None:
        """Sobe o fio do tocador se ele não está de pé. Chamado com a trava."""
        if not self._fim.is_set() and (self._fio is None or not self._fio.is_alive()):
            self._fio = threading.Thread(
                target=self._correr, name=f"hefesto-{self.rotulo}", daemon=True
            )
            self._fio.start()

    @property
    def tocando_o_toque(self) -> bool:
        return self._toque is not None

    @property
    def tocando_o_corpo(self) -> bool:
        return any(self._corpos.values())

    @property
    def lados(self) -> tuple[int, int]:
        """O par ``(esquerdo, direito)`` do padrão do gatilho que vale agora."""
        return self._lados if self._relogio() < self._lados_valem_ate else (0, 0)

    def proximo_bloco(
        self, nivel: tuple[int, int], antes: tuple[int, int], fase: int
    ) -> bytes:
        """O bloco do nível, com o trecho do toque somado quando há toque em curso."""
        with self._trava:
            toque, inicio = self._toque, self._toque_pos
            if toque is not None:
                self._toque_pos = inicio + QUADROS_POR_BLOCO
                if self._toque_pos >= len(toque[0]):
                    if self._toque_em_laco:
                        self._toque_pos = 0
                    else:
                        self._toque = None
                        self._toque_longo = False
            corpos = []
            for (fonte, lado), fila in list(self._corpos.items()):
                corpos.append((fila[:QUADROS_POR_BLOCO], CANAIS_DO_LADO[lado]))
                del fila[:QUADROS_POR_BLOCO]
                if not fila:
                    del self._corpos[(fonte, lado)]
            lados, lados_antes = self.lados, self._lados_antes
            self._lados_antes = lados
        bloco = self._bloco(nivel, antes, fase)
        if any(lados) or any(lados_antes):
            bloco = somar_os_lados(bloco, lados, lados_antes, fase)
        if corpos:
            bloco = somar_os_corpos(bloco, corpos)
        if toque is not None:
            bloco = misturar_o_toque(bloco, toque[0], inicio, toque[1])
        return self._limitar(bloco)

    def _limitar(self, bloco: bytes) -> bytes:
        """A soma do bloco sob o teto de cada canal; sem nada a limitar, o mesmo ``bytes``."""
        quadros = np.frombuffer(bloco, dtype=_FLOAT32_LE).reshape(-1, CANAIS_DA_HAPTICA)
        em_64 = quadros.astype(np.float64)
        saida = self._limitador.passar(em_64, self.tetos_da_mistura())
        if saida is em_64:
            return bloco
        return saida.astype(_FLOAT32_LE).tobytes()

    def tetos_da_mistura(self) -> np.ndarray:
        """O teto de cada canal na saída do bloco: os dois motores descontam o ganho da via.

        O ganho da háptica do controle (``1.0 1.0 G G`` no laço do cabo, a amostra da ponte no
        rádio) multiplica o bloco DEPOIS daqui: o que passa de ``teto / G`` aqui passa do teto
        lá, e o corte volta no servidor de som. Ganho abaixo de 1 não sobe o teto. A leitura que
        falha guarda o último ganho lido do mesmo dono (1 se não houver).
        """
        agora, dono, fator = self._ganho_lido
        if self._dono != dono or self._relogio() - agora >= LEITURA_DO_GANHO_S:
            try:
                fator = float(self._ganho_da_via(self._dono))
            except Exception:
                fator = fator if dono == self._dono else 1.0
            if not math.isfinite(fator) or fator < 1.0:
                fator = 1.0
            self._ganho_lido = (self._relogio(), self._dono, fator)
        return np.array(
            [TETO_DA_MISTURA, TETO_DA_MISTURA, TETO_DA_MISTURA / fator, TETO_DA_MISTURA / fator]
        )

    def parar(self) -> None:
        """Derruba o processo e o fio. Idempotente."""
        self._fim.set()
        self._acordar.set()
        self._matar(self._proc)
        fio = self._fio
        if fio is not None and fio is not threading.current_thread():
            fio.join(timeout=2.0)

    def _avisar(self) -> None:
        aviso = self._ao_mudar
        if aviso is None:
            return
        try:
            aviso()
        except Exception as exc:
            logger.debug("haptica_fina_aviso_falhou", controle=self.marca, err=str(exc))

    def _recusar(self, motivo: str, *, fixo: bool = False) -> None:
        """Arma a recusa e solta o corpo que esperava: o pedaço velho nunca toca depois."""
        with self._trava:
            espera = self._recuo.recusar(motivo, fixo=fixo)
            self._corpos.clear()
        logger.info(
            "haptica_fina_recusada", controle=self.marca, motivo=motivo, espera_s=espera)

    def _correr(self) -> None:
        while not self._fim.is_set():
            self._acordar.wait(timeout=1.0)
            self._acordar.clear()
            if self._fim.is_set():
                return
            with self._trava:
                nivel, sink, toque = self._nivel, self._sink, self._toque
                corpo = any(self._corpos.values()) or any(self.lados)
            if (not any(nivel) and toque is None and not corpo) or not sink or self.recusado:
                continue
            self._tocar(sink)

    def _tocar(self, sink: str) -> None:
        argv = self._argv_de(sink, self.rotulo)
        if not argv:
            self._recusar("sem_tocador", fixo=True)
            return
        try:
            proc = self._lancar(
                argv, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.debug("haptica_fina_nao_subiu", controle=self.marca, err=str(exc))
            self._recusar("nao_subiu")
            return
        self._proc = proc
        motivo = "silencio"
        try:
            fd = proc.stdin.fileno()
            with contextlib.suppress(OSError):
                fcntl.fcntl(fd, getattr(fcntl, "F_SETPIPE_SZ", 1031), CANO_DO_TOCADOR)
            os.set_blocking(fd, False)
            motivo = self._escrever_enquanto_toca(proc, fd, sink, os.path.basename(argv[0]))
        except Exception as exc:
            logger.debug("haptica_fina_falhou", controle=self.marca, err=str(exc))
            motivo = "falhou"
        finally:
            estava_vivo = self._vivo
            desde, self._vivo_desde = self._vivo_desde, None
            self._vivo = False
            self._matar(proc)
            self._proc = None
            motivo = motivo_da_saida(
                motivo, parado=self._fim.is_set(),
                renovado=self._relogio() < self._renasce_ate,
                vivo_s=None if desde is None else self._relogio() - desde, recuo=self._recuo)
            if motivo not in SAIDAS_SEM_RECUSA:
                self._recusar(motivo)
            logger.info("haptica_fina_saiu", controle=self.marca, motivo=motivo)
            if estava_vivo:
                self._avisar()

    def _escrever_enquanto_toca(self, proc: Any, fd: int, sink: str, binario: str) -> str:
        fase = 0
        antes = (0, 0)
        silencio_desde: float | None = None
        while not self._fim.is_set():
            with self._trava:
                nivel, sink_agora = self._nivel, self._sink
            if sink_agora != sink:
                return "trocou_de_endpoint"
            if proc.poll() is not None:
                return "morreu"
            agora = self._relogio()
            if any(nivel) or self._toque is not None or self.tocando_o_corpo or any(self.lados):
                silencio_desde = None
            elif silencio_desde is None:
                silencio_desde = agora
            elif agora - silencio_desde >= self._folga_s:
                return "silencio"
            fim = self._escrever(fd, self.proximo_bloco(nivel, antes, fase))
            if fim:
                return fim
            if not self._vivo:
                self._vivo = True
                self._vivo_desde = self._relogio()
                logger.info("haptica_fina_de_pe", controle=self.marca, tocador=binario)
                threading.Thread(
                    target=self._conferir_o_destino, args=(proc, sink), daemon=True,
                    name=f"hefesto-{self.rotulo}-conferencia",
                ).start()
                self._avisar()
            antes = nivel
            fase = (fase + QUADROS_POR_BLOCO) % QUADROS_DO_CICLO
        return "parado"

    def timbre_de_agora(self, nivel: tuple[int, int] | None = None) -> str | None:
        """O timbre do bloco de agora: a classe viva do rumble no estilo e na forma do dono."""
        with self._trava:
            par = self._nivel if nivel is None else nivel
            classe = self._linha.classe(self._relogio(), par[0], par[1], self._onda)
            estilo, forma = self._vestido
            onda = self._onda
        return formas.timbre_do_rumble(estilo, forma, classe, onda)

    def _bloco(self, nivel: tuple[int, int], antes: tuple[int, int], fase: int) -> bytes:
        timbre = self.timbre_de_agora(nivel)
        if nivel != antes:
            self._memoria = {}
            return bloco_com_timbre(nivel[0], nivel[1], timbre, fase=fase, antes=antes)
        chave = (nivel[0], nivel[1], fase, timbre)
        bloco = self._memoria.get(chave)
        if bloco is None:
            bloco = bloco_com_timbre(nivel[0], nivel[1], timbre, fase=fase)
            self._memoria[chave] = bloco
        return bloco

    def _escrever(self, fd: int, dados: bytes) -> str:
        """Escreve o bloco inteiro e devolve ``""``; senão, o motivo do fim: ``parado`` quando
        o fim foi pedido, ``parou_de_ler`` quando o tocador parou de ler ou morreu."""
        return escrever_o_bloco(fd, dados, self._fim, self._relogio, continuar_no_cheio=True)

    def _conferir_o_destino(self, proc: Any, sink: str) -> None:
        """Ligado a outro nó que não o endpoint, o tocador morre — nunca na TV da máquina."""
        for espera in ESPERAS_DA_CONFERENCIA_S:
            if self._fim.wait(espera) or proc.poll() is not None:
                return
            try:
                destino = self._conferir(self.rotulo)
            except Exception as exc:
                logger.debug("haptica_fina_conferencia_falhou", controle=self.marca, err=str(exc))
                destino = None
            if destino is None:
                continue
            if destino == sink:
                return
            logger.warning("haptica_fina_ligada_a_outro_no", controle=self.marca)
            self._recusar("ligada_a_outro_no", fixo=True)
            self._matar(proc)
            return
        logger.debug("haptica_fina_nao_conferida", controle=self.marca)

    @staticmethod
    def _matar(proc: Any) -> None:
        if proc is None:
            return
        with contextlib.suppress(Exception):
            proc.stdin.close()
        with contextlib.suppress(Exception):
            proc.kill()
        with contextlib.suppress(Exception):
            proc.wait(timeout=2)


__all__ = [
    "AGULHAS",
    "CANAIS_DO_LADO",
    "FOLGA_DO_TOCADOR_S",
    "FREQUENCIA_DO_FORTE_HZ",
    "FREQUENCIA_DO_FRACO_HZ",
    "INTERRUPTOR_DA_ORDEM_DOS_NOS",
    "MARCA_DO_ENSAIO",
    "MARCA_DO_TOCADOR",
    "MOLDE_DO_NOME",
    "MOLDE_DO_NOME_SEM_PORTA",
    "NOME_DA_HAPTICA_DO_CONTROLE",
    "ORDEM_DOS_NOS",
    "ORDEM_PELO_ASSENTO",
    "ORDEM_PELO_ASSENTO_SEM_REFAZER",
    "ORDEM_PELO_ENDERECO",
    "ORDENS_DOS_NOS",
    "PID_DUALSENSE",
    "PRIORIDADE_DO_RELOGIO",
    "QUADROS_POR_BLOCO",
    "RECUSA_DO_TOCADOR_S",
    "SEM_PORTA",
    "VID_SONY",
    "Ancora",
    "EndpointDeHaptica",
    "LimitadorSuave",
    "RecuoDoTocador",
    "TocadorDoRumble",
    "a_porta_e_dele",
    "ancora_da_interface",
    "ancora_do_gadget",
    "argv_do_tocador",
    "bloco_com_timbre",
    "bloco_da_haptica",
    "conferir_o_destino_do_tocador",
    "descricao_da_haptica",
    "e_sem_porta",
    "endpoints_de_pe",
    "escrever_o_bloco",
    "fluxos_nos_endpoints",
    "forma_do_toque",
    "ganho_do_perfil",
    "marca_do_aparelho",
    "misturar_o_toque",
    "motivo_da_saida",
    "nasceu_com_o_relogio",
    "nome_da_marca",
    "nome_do_endpoint",
    "nome_sem_porta",
    "ordem_dos_nos",
    "plano_da_ordem",
    "propriedades_do_endpoint",
    "rotulo_da_haptica",
    "rotulo_do_tocador",
    "rotulo_no_ar",
    "somar_os_lados",
    "varrer_endpoints_orfaos",
]
