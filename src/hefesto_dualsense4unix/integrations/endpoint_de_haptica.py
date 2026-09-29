"""O endpoint que o rádio não tem — HAPTICA-POR-RADIO-01, P3.

Pelo CABO a vibração dos jogos da Sony viaja como áudio: o jogo abre o endpoint
de quatro canais do controle e toca os canais 3 e 4, que são os dois motores.
Pelo RÁDIO o DualSense não tem placa de som nenhuma, e sem endpoint o jogo não
tem onde tocar — ele desiste antes de olhar o HID.

Este módulo publica o endpoint que falta: um ``module-null-sink`` do PipeWire
vestido de DualSense, um por LUGAR da mesa (P1 a P4) — ver «UM ENDPOINT POR
LUGAR», abaixo.

O QUE O GE-PROTON LÊ, E POR QUE UM NÓ BASTA
--------------------------------------------
Lido no fonte em 18/09/2026 e medido no PRAGMATA no mesmo dia:

* ``fill_device_info`` (``winepulse.drv/pulse.c:668``) lê ``device.bus``,
  ``device.vendor.id`` e ``device.product.id`` **do proplist do sink** — não
  pergunta ao aparelho;
* ``is_dualsense_audio_device`` (patch 0063) exige ``usb`` + ``054c`` +
  ``0ce6``/``0df2``, tudo do proplist;
* o NOME tem de conter ``alsa_output.usb-Sony_Interactive_Entertainment_``,
  ``Wireless_Controller`` e ``Speaker__sink`` (patch 0060);
* o formato é ``FLOAT32LE``, 48 kHz, **quatro canais** (patch 0063).

**Nada disso pergunta como o CONTROLE está ligado.** É por isso que o gadget
USB (``usbip-vudc``) deixou de ser necessário: ele existia para produzir estes
mesmos campos, e exigia raiz, módulos de kernel e ``linux-tools`` da versão
exata — o que fere *"o produto é para qualquer usuário"*.

A ÂNCORA, E O ERRO DE UM NÍVEL QUE CUSTOU UM LANÇAMENTO
--------------------------------------------------------
O ``ContainerId`` do endpoint é o que casa o nó com o device KS do prefixo. Ele
sai de ``get_container_id`` (``pulse.c:608``), que só roda quando o proplist
traz ``sysfs.path`` e que sobe ao **pai** ``usb_device`` desse caminho.

* **sem ``sysfs.path``** o GUID sai ZERADO — e zerado é o valor de toda saída
  que não é USB, então o jogo poderia abrir a háptica na caixa de som da
  pessoa;
* **com o caminho de um ``usb_device``** o GUID sai do PAI dele. Medido no
  PRAGMATA às 03h40 de 18/09: declarando o hub âncora, o jogo gravou o GUID do
  **hub raiz**, e o device KS nunca casou.

Por isso o nó declara a INTERFACE da âncora (``<bus>-<porta>:1.0``), que é a
forma de uma placa de som de verdade — o caminho dela é o do ``sound/card``,
cujo pai é o aparelho. Com isso, às 03h54, os dois lados deram o mesmo GUID e o
jogo abriu o stream de quatro canais.

**Nada é escrito na âncora.** Ela é só um endereço de onde o Wine tira quatro
números.

O RÓTULO DIZ O CONTROLE, E NÃO O ENDEREÇO — 24/09/2026
------------------------------------------------------
A-HAPTICA-TEM-NOME-DE-CONTROLE-01. O nó aparecia na lista de saídas de som da
pessoa como «DualSense <os seis hex do endereço> (háptica)». Passou à FORMA A
dos outros dois nós do controle: «Háptica do Controle N (DualSense Wireless
Controller)», com o número do jogador. Desde 28/09 o N é o do LUGAR, e o
rótulo é fixo: quem anda é o controle, não o nó (abaixo).

**O que o jogo lê não mudou, e isso foi medido no código** — o GE-Proton11-7
com os 182 patches ``proton-ds5-haptic`` aplicados em ordem. A descrição vira
o ``drv_id`` do endpoint no ``mmdevapi`` (``get_device_name``), e é só ali que
ela pesa: os casamentos sobre ele dão o MESMO resultado para o rótulo velho e
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

UM ENDPOINT POR LUGAR — 28/09/2026
----------------------------------
A-HAPTICA-CHEGA-A-QUEM-ENTRA-DEPOIS-01. O endpoint era um por CONTROLE no
rádio, com o nome pelo rabo do endereço, e nascia e morria com o controle. O
registro que o jogo lê (o device KS, ``audio_ks_dualsense``) só se grava no
lançamento, com o ``wineserver`` ainda fora do ar: o controle que chegava com
o jogo aberto caía num endpoint que o jogo não conhecia, e o que caía e voltava
podia voltar noutra âncora.

Agora são QUATRO nós, um por lugar, com o nome pelo lugar
(:func:`nome_do_endpoint`) e a âncora própria, e eles sobem com o primeiro
DualSense da mesa, em qualquer transporte. O jogo casa o LUGAR, e não o
aparelho: quem entra depois, em qualquer ordem, cai num endpoint que o
lançamento já registrou. No rádio a ponte lê o endpoint do lugar do controle;
no cabo um laço leva o endpoint do lugar à placa do controle
(``integrations/haptica_do_cabo.py``). O número que anda troca o laço ou a
ponte, e nunca o endpoint.

A MARCA DO LUGAR NÃO TEM A FORMA DE SEIS HEX (:data:`MOLDE_DA_MARCA_DO_LUGAR`):
as réguas de forma leem ``HEFESTO<6 hex>`` como o rabo de um endereço
(``scripts/check_endereco_de_radio.py``, ``core/formas_do_endereco.py``).

O RUMBLE DO PAD SEM HÁPTICA TOCA NO LUGAR — 29/09/2026
------------------------------------------------------
NO-MODO-XBOX-TUDO-FUNCIONA-01, parte 4. No modo Xbox o jogo vê um pad de
Xbox 360 no ``uinput`` e só manda rumble (dois motores, 0 a 255); o áudio de
háptica que ele toca num DualSense não existe ali. :class:`TocadorDoRumble`
toca esse rumble como háptica nos canais traseiros do endpoint do lugar, e o
laço do cabo e a ponte do rádio o levam ao controle como levam o do jogo.

**O ALVO É O ``object.serial``, COM O RECUO PROIBIDO** (:func:`argv_do_tocador`):
um fluxo de reprodução cujo alvo não resolve cai na saída PADRÃO sem erro — a
TV ou a caixa de som dela, tocando um zumbido de 60 Hz. O fluxo pede
``node.dont-fallback`` e ``node.dont-reconnect``, e o destino é conferido no
grafo (:func:`conferir_o_destino_do_tocador`): ligado a outro nó, morre.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import math
import os
import select
import shutil
import subprocess
import sys
import threading
import time
from array import array
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    CANAIS_DA_HAPTICA,
    HEX_DO_SUFIXO,
    o_servidor_e_o_pipewire,
    rodar_pactl,
    serial_do_no,
    so_hex,
)
from hefesto_dualsense4unix.integrations.vestido_de_dualsense import (
    PID_DUALSENSE,
    VID_SONY,
    campos_da_identidade,
    campos_do_nome,
    com_o_nome_da_sony,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# O VID/PID que o GE exige NO PROPLIST — não no aparelho — e o fabricante têm
# DONO em `vestido_de_dualsense` desde 24/09/2026 (A-FORJA-VALIDA-O-SOM-01): o
# nó do alto-falante veste as mesmas strings do fabricante e do produto, e a
# identidade inteira que este endpoint declara (barramento, VID, PID, âncora)
# sai de `campos_da_identidade`. `VID_SONY` e `PID_DUALSENSE` seguem no
# `__all__` daqui para quem já os importava deste módulo.

TAXA_DO_ENDPOINT = 48000

#: As três agulhas que os patches do GE procuram no nome, e um discriminador
#: por LUGAR: dois endpoints de nome IGUAL viram um só (patch 0186,
#: `is_shared_sony_mono_backend_name`), e aí a háptica de dois lugares iria
#: para o mesmo aparelho.
MOLDE_DO_NOME = (
    "alsa_output.usb-Sony_Interactive_Entertainment_"
    "DualSense_Wireless_Controller_HEFESTO{marca}-00.HiFi__Speaker__sink"
)
#: A MARCA que separa os nós DESTA casa dos de um DualSense por cabo de
#: verdade — o `HEFESTO` no meio do nome. A varredura de órfãos a exige: sem
#: ela, um `unload-module` nosso poderia derrubar o sink que o `pipewire`
#: publicou para um controle plugado, que não é nosso para derrubar.
MARCA_DO_NOME = "HEFESTO"

#: OS LUGARES DA MESA — A-HAPTICA-CHEGA-A-QUEM-ENTRA-DEPOIS-01, 28/09/2026. Um
#: endpoint por lugar, os quatro de pé desde o primeiro DualSense. O número é o
#: «Controle N» que a tela imprime no cartão.
LUGARES: tuple[int, ...] = (1, 2, 3, 4)

#: A marca do lugar no nome. **Sem a forma de seis hex**: ``HEFESTO<6 hex>`` é
#: o que as réguas de forma leem como o rabo de um endereço, e o nome do lugar
#: não tem endereço nenhum.
MOLDE_DA_MARCA_DO_LUGAR = "LUGAR{lugar}"

#: A marca que só o endpoint montado pelo ENSAIO carrega
#: (``scripts/ensaios/os_endpoints_de_haptica.py --montar``). A varredura de
#: órfãos não o derruba: o instrumento que a bancada montou não é resto de
#: processo nenhum, e derrubá-lo seria o produto brigando com o instrumento.
MARCA_DO_ENSAIO = "hefesto.origem=ensaio"

AGULHAS = (
    "alsa_output.usb-Sony_Interactive_Entertainment_",
    "Wireless_Controller",
    "Speaker__sink",
)
#: `PA_NAME_MAX` é 128 com o `\0`; um nome maior o servidor recusa.
MAX_NOME = 127

#: O nó NÃO pode virar a saída padrão da máquina — ele é para o jogo achar, não
#: para a pessoa escolher. Mesma razão e mesmo valor do nó do alto-falante.
PRIORIDADE_DA_SESSAO = 0

#: OS CANAIS TRASEIROS SÃO OS MOTORES, e eles precisam ser LIGADOS de propósito
#: — medido na máquina dela em 19/09/2026, e o achado foi dela: *"é defeito não
#: era pra tá assim eu acho"*.  <!-- noqa-acento: citação literal dela -->
#:
#: O `load-module` abaixo não dizia NADA sobre volume, e o endpoint nascia com
#: os canais 3-4 em **0%, menos infinito dB** enquanto os 1-2 ficavam em 100%. Os 3-4 são
#: a vibração (a háptica do DualSense viaja como áudio nos traseiros); em zero,
#: o jogo escreve no nada.
#:
#: É A MESMA CLASSE DE DEFEITO QUE ESTA CASA JÁ PAGOU: *não escrever não é o
#: lado neutro*. Omitir um byte do report calou o alto-falante por um mês; aqui
#: omitir o volume calou os motores — e em QUALQUER computador, porque o valor
#: vem do servidor de som, não do nosso código.
#:
#: SÓ OS TRASEIROS, e os da frente ficam como estão: os 1-2 são o alto-falante
#: do controle, que tem volume próprio no produto (`speaker.volume`, por HID).
#: Cravar 100% neles aqui atropelaria a escolha dela do outro lado.
VOLUME_DOS_MOTORES = "100%"

#: A metade do rótulo SEM o número e sem o sufixo da Sony, que
#: :func:`rotulo_da_haptica` acrescenta. Irmã de
#: ``alto_falante_bt.NOME_DO_ALTO_FALANTE_DO_CONTROLE`` e de
#: ``dualsense_bt_audio.NOME_DO_MICROFONE_DO_CONTROLE``: os três nós de um
#: controle no BT se leem lado a lado na lista de som da pessoa.
NOME_DA_HAPTICA_DO_CONTROLE = "Háptica do Controle"

_MODULO_NULL_SINK = "module-null-sink"


@dataclass(frozen=True)
class Ancora:
    """Um ``usb_device`` de onde o Wine tira o ``ContainerId`` do endpoint."""

    #: O `usb_device` — é dele que saem vid, pid, busnum, devnum e USEC.
    syspath: str
    #: O que vai no ``sysfs.path`` do nó: uma INTERFACE dele, porque o Wine
    #: sobe ao PAI do caminho declarado.
    declarado: str
    nome: str = ""


def _ler(caminho: Path) -> str:
    try:
        return caminho.read_text(encoding="ascii", errors="replace").strip()
    except OSError:
        return ""


#: A raiz do sysfs, resolvida NA CHAMADA e não no default do parâmetro.
#: **A diferença é a suíte**: um default avaliado no import congela `/sys` no
#: módulo, e nenhuma fixture o alcança depois — a suíte passaria a ler o
#: barramento USB DELA e a publicar nós de verdade. É a cicatriz de
#: 16/09/2026 (memória "subsystem novo faz a suíte tocar o aparelho dela").
RAIZ_DO_SYSFS = Path("/sys")


def ancoras(sysfs: Path | None = None) -> list[Ancora]:
    """Os ``usb_device`` que servem de âncora, na ordem do barramento.

    **Fora ficam os que têm placa de som:** o ``ContainerId`` de um deles já é
    o de um endpoint de verdade, e reusá-lo faria dois endpoints dizerem ser o
    mesmo aparelho. Fora ficam também os que não têm interface configurada —
    sem um filho para declarar, o GUID subiria ao hub raiz.
    """
    sysfs = RAIZ_DO_SYSFS if sysfs is None else sysfs
    raiz = sysfs / "bus" / "usb" / "devices"
    achadas: list[Ancora] = []
    try:
        entradas = sorted(raiz.iterdir())
    except OSError:
        return achadas
    try:
        raiz_txt = str(sysfs.resolve())
    except OSError:
        return achadas
    for dev in entradas:
        if not (_ler(dev / "busnum").isdigit() and _ler(dev / "devnum").isdigit()):
            continue
        if any(dev.glob("*/sound/card*")):
            continue
        interface = next(
            (i for i in sorted(dev.glob(f"{dev.name}:*")) if (i / "uevent").is_file()), None
        )
        if interface is None:
            continue
        try:
            achadas.append(
                Ancora(
                    syspath=str(dev.resolve()).replace(raiz_txt, "", 1),
                    declarado=str(interface.resolve()).replace(raiz_txt, "", 1),
                    nome=_ler(dev / "product"),
                )
            )
        except OSError:
            continue
    return achadas


def distribuir_ancoras(
    lugares: Iterable[int],
    disponiveis: Iterable[Ancora],
    de_pe: Mapping[str, Sequence[tuple[str, str]]] | None = None,
    *,
    ja_postas: Mapping[int, Ancora] | None = None,
    ocupados: Iterable[int] = (),
) -> dict[int, Ancora]:
    """Uma âncora por LUGAR, e NUNCA a mesma para dois. Função pura.

    **Duas âncoras iguais são dois endpoints com o mesmo ``ContainerId``**, e
    aí o jogo não distingue os lugares — a háptica do jogador 2 iria para o
    device KS do jogador 1.

    **POR LUGAR DESDE 28/09/2026** (A-HAPTICA-CHEGA-A-QUEM-ENTRA-DEPOIS-01): as
    chaves eram os ``uniq`` dos controles no rádio, e passaram a ser os lugares
    (:data:`LUGARES`). A posse é a mesma, nos mesmos três passos; faltando
    âncora, fica de fora o lugar VAZIO de número maior.

    **QUEM ESTÁ SENTADO VEM PRIMEIRO NAS LIVRES** (``ocupados``, conferência de
    28/09/2026). Pela ordem pura, com menos âncoras que lugares, o lugar 1
    vazio levava a âncora e o controle sozinho no lugar 2 ficava sem vibração
    pelo rádio — num notebook com uma âncora, bastava ele não ser o «Controle
    1». A posse não muda: só o passo 3 serve os lugares ocupados antes.

    **A DISTRIBUIÇÃO ERA POR ORDEM, E A ORDEM REPETIA ÂNCORA — 18/09/2026.** Ela
    ordenava TODOS os controles vivos e dava a i-ésima âncora ao i-ésimo; quem
    já tinha endpoint era só pulado depois. B conecta sozinho e fica com a
    âncora 0; A chega, com A < B, e a ordenação dá a âncora 0 a A também. O
    mesmo com o adaptador que cai e devolve os controles em outra ordem, e com
    um aparelho USB novo que muda a lista. Nada disso depende da máquina dela.

    Agora a posse é respeitada, em três passos e nesta ordem:

    1. ``ja_postas`` — a memória do processo: quem já tem endpoint fica com a
       âncora dele, enquanto o aparelho existir em ``disponiveis``;
    2. ``de_pe`` — o SERVIDOR, no formato de :func:`endpoints_de_pe`: quem não
       tem endpoint neste processo, mas tem o nó de pé (o restart do daemon),
       adota o ``sysfs.path`` que o nó já declara. Sem isso a ordenação voltava
       a mandar depois de cada restart e :meth:`EndpointDeHaptica.iniciar`
       derrubava e recarregava um nó vivo — com o jogo talvez aberto nele;
    3. os que sobram recebem as âncoras ainda LIVRES: primeiro os
       ``ocupados``, depois os vazios, cada grupo em ordem de lugar.

    A identidade de uma âncora é o ``syspath`` do aparelho, não a interface
    declarada: o Wine sobe ao pai do caminho, então duas interfaces do mesmo
    aparelho dariam o mesmo ``ContainerId``. Faltando âncora, o controle fica
    de fora — repetir seria pior que faltar.
    """
    lista = list(disponiveis)
    por_aparelho = {a.syspath: a for a in lista}
    por_declarado = {a.declarado: a for a in lista}
    ordem = sorted({int(n) for n in lugares if int(n) in LUGARES})
    postas: dict[int, Ancora] = {}
    tomadas: set[str] = set()

    def tomar(lugar: int, ancora: Ancora | None) -> bool:
        if ancora is None or ancora.syspath in tomadas:
            return False
        postas[lugar] = ancora
        tomadas.add(ancora.syspath)
        return True

    lembradas = ja_postas or {}
    for lugar in ordem:
        lembrada = lembradas.get(lugar)
        if lembrada is not None and lembrada.syspath in por_aparelho:
            tomar(lugar, lembrada)
    servidor = de_pe or {}
    for lugar in ordem:
        if lugar in postas:
            continue
        for _module_id, caminho in servidor.get(nome_do_endpoint(lugar), ()):
            if tomar(lugar, por_declarado.get(caminho)):
                break
    livres = (a for a in lista if a.syspath not in tomadas)
    sentados = {int(n) for n in ocupados}
    for lugar in [n for n in ordem if n in sentados] + [n for n in ordem if n not in sentados]:
        if lugar in postas:
            continue
        for ancora in livres:
            if tomar(lugar, ancora):
                break
    return postas


def marca_do_controle(uniq: str) -> str:
    """Os seis hex do rabo do ``uniq`` — a identidade que sobrevive a hotplug.

    A mesma de :func:`alto_falante_bt.nome_do_sink`, e pelo mesmo motivo: o
    ``hidrawN`` muda a cada reconexão, o endereço do controle não. Desde
    28/09/2026 ela não entra no nome do endpoint (:func:`nome_do_endpoint` é
    pelo lugar); segue como a marca do gravador da ponte
    (``alto_falante_bt.rotulo_do_gravador``).
    """
    rabo = so_hex(str(uniq))
    return rabo[-HEX_DO_SUFIXO:] if len(rabo) >= HEX_DO_SUFIXO else ""


def marca_do_lugar(lugar: int) -> str:
    """``LUGAR<n>`` para um dos :data:`LUGARES`, e "" para qualquer outro valor.

    ``bool`` não é lugar, embora seja ``int``: ``True`` viraria o lugar 1.
    """
    if isinstance(lugar, bool) or not isinstance(lugar, int) or lugar not in LUGARES:
        return ""
    return MOLDE_DA_MARCA_DO_LUGAR.format(lugar=lugar)


def nome_do_endpoint(lugar: int) -> str:
    """O nome do nó do lugar, ou "" quando o valor não é um dos :data:`LUGARES`.

    "" é recusa, não um nome vazio: publicar um nó anônimo faria dois lugares
    disputarem o mesmo endpoint. **O nome é do LUGAR desde 28/09/2026** — era
    pelo rabo do endereço do controle, e o controle que chegava com o jogo
    aberto caía num endpoint que o registro do lançamento não tinha.
    """
    marca = marca_do_lugar(lugar)
    if not marca:
        return ""
    nome = MOLDE_DO_NOME.format(marca=marca)
    return nome if len(nome) <= MAX_NOME else ""


def rotulo_da_haptica(numero: int | None) -> str:
    """A FORMA A — «Háptica do Controle N (DualSense Wireless Controller)».

    **Decidido por delegação dela em 24/09/2026**, pelo padrão que ela fixou
    para o alto-falante e o microfone em 23/09 (A-FORJA-VALIDA-O-SOM-01, E6): o
    nome dela na frente, o ``iProduct`` da Sony atrás, e nada de endereço. O
    rótulo de antes, «DualSense <hex6> (háptica)», punha o rabo do endereço do
    controle na lista de som da máquina — e fazia a bancada contar quatro placas
    DualSense onde há duas.

    ``None``, ``bool`` e número que não seja positivo valem como *"não sei o
    assento"*: sem número não se inventa número, e o rótulo sai sem ele.
    """
    base = NOME_DA_HAPTICA_DO_CONTROLE
    if isinstance(numero, int) and not isinstance(numero, bool) and numero > 0:
        base = f"{base} {numero}"
    return com_o_nome_da_sony(base)


def propriedades_do_endpoint(lugar: int, ancora: Ancora) -> str:
    """O ``sink_properties=``, ENTRE ASPAS DUPLAS.

    **As aspas são a cura conhecida desta casa**, paga em 06/09/2026: o parser
    do ``pipewire-pulse`` corta o valor no primeiro ESPAÇO quando ele não vem
    entre aspas, e só a primeira propriedade chega — com a régua dando verde
    por ler o argv em vez do nó.

    O rótulo é o do LUGAR, e fixo (28/09/2026): o nó não renasce quando o
    assento de um controle anda, porque quem anda é o controle.
    """
    rotulo = rotulo_da_haptica(lugar if marca_do_lugar(lugar) else None)
    campos = (
        # A IDENTIDADE tem um dono, e a âncora é a dele: sem `sysfs.path` o
        # Wine zera o `ContainerId` e o jogo não casa o endpoint com o device
        # KS — a razão inteira deste módulo.
        *campos_da_identidade(ancora.declarado),
        # O NOME da Sony, do mesmo dono do nó do alto-falante. O que pesa aqui
        # é o `device.product.name`: o monitor deste nó se chama «Monitor of
        # Háptica do Controle N (…)», 64 caracteres, e acima dos 62 do Wine é
        # dele que o `get_device_name` monta o `drv_id` do monitor — sem ele, o
        # comprido fica inteiro ali. O nome que o jogo LÊ não sai daqui: o USB
        # `054c:0ce6` acima faz o `mmdevapi` trocá-lo pelo do produto.
        *campos_do_nome(),
        f"device.description='{rotulo}'",
        f"priority.session={PRIORIDADE_DA_SESSAO}",
        "device.icon_name=audio-speakers",
    )
    return 'sink_properties="' + " ".join(campos) + '"'


def endpoints_de_pe(
    runner: Callable[[list[str]], str | None] | None = None,
) -> dict[str, list[tuple[str, str]]]:
    """Os endpoints DESTA casa que estão de pé NO SERVIDOR, por nome de sink.

    **O DEFEITO QUE ISTO CURA, medido na mesa dela em 18/09/2026:** vinte e dois
    ``module-null-sink`` carregados onde deviam existir QUATRO — cinco para um
    mesmo controle. A idempotência do :meth:`EndpointDeHaptica.iniciar` era
    contra a MEMÓRIA DO PROCESSO (``self._module_id``), e o servidor de som é
    outro processo: um restart do daemon deixa todos os módulos de pé, e o
    daemon novo nasce sem saber deles. A troca de âncora fazia o resto — dois
    endpoints do mesmo controle com ``sysfs.path`` diferentes
    (``3-4.1:1.0`` e ``3-4:1.0``), porque a âncora escolhida muda entre
    reconciliações e o nome do sink não.

    É a mesma classe do canal ÓRFÃO que o ``bt_mic`` já cura
    (``VarredorDeCanaisOrfaos``, MIC-O-CANAL-DO-OUTRO-01), e a cura é a mesma:
    **perguntar ao servidor, nunca à lembrança**.

    Devolve ``{sink_name: [(module_id, sysfs_path), …]}``. A lista é lista de
    propósito: quando há mais de um, o vazamento já aconteceu, e quem chama
    precisa ver todos para derrubar os que sobram.
    """
    chamar = runner or rodar_pactl
    saida = chamar(["pactl", "list", "short", "modules"]) or ""
    de_pe: dict[str, list[tuple[str, str]]] = {}
    for module_id, nome, caminho in _modulos_desta_casa(saida):
        de_pe.setdefault(nome, []).append((module_id, caminho))
    return de_pe


def _modulos_desta_casa(saida: str) -> list[tuple[str, str, str]]:
    """``(module_id, sink_name, sysfs.path)`` de cada endpoint desta casa.

    O leitor ÚNICO do ``pactl list short modules`` deste módulo. **O do ensaio
    fica de fora** (:data:`MARCA_DO_ENSAIO`): ele não é do produto, e o que não
    é do produto o produto não adota nem derruba.
    """
    achados: list[tuple[str, str, str]] = []
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
        achados.append((partes[0].strip(), nome, caminho))
    return achados


def _volume_da_frente(saida_do_pactl: str, nome_do_sink: str) -> tuple[str, str]:
    """Os dois volumes da FRENTE deste sink, na forma que o `pactl` aceita.

    Devolve ``("100%", "100%")`` quando não dá para saber — é o valor com que o
    null-sink nasce, então não muda nada em quem já estava certo.
    """
    dentro = False
    for linha in saida_do_pactl.splitlines():
        crua = linha.strip()
        if crua.startswith("Name:"):
            dentro = crua.split(":", 1)[1].strip() == nome_do_sink
            continue
        if dentro and crua.startswith("Volume:"):
            partes = [p.strip() for p in crua.split(":", 1)[1].split(",")]
            lidos = []
            for p in partes[:2]:
                achado = [t for t in p.split("/") if t.strip().endswith("%")]
                if achado:
                    lidos.append(achado[0].strip())
            if len(lidos) == 2:
                return (lidos[0], lidos[1])
            return ("100%", "100%")
    return ("100%", "100%")


def varrer_endpoints_orfaos(
    vivos: Iterable[int],
    runner: Callable[[list[str]], str | None] | None = None,
    *,
    de_pe: Mapping[str, Sequence[tuple[str, str]]] | None = None,
) -> list[str]:
    """Derruba todo endpoint desta casa que não é de um lugar vivo.

    ``vivos`` são os LUGARES que ficam de pé AGORA (desde 28/09/2026; eram os
    ``uniq`` da mesa). O que sobra é resto de sessão anterior — e resto de
    sessão anterior não é inofensivo: ele entra na lista de saídas de som da
    pessoa com o mesmo nome do endpoint bom, e o jogo que procura o
    alto-falante do DualSense pode achar o morto.

    **O NOME DE ANTES CAI NA PRIMEIRA VOLTA DEPOIS DO INSTALL.** O endpoint por
    controle (``HEFESTO<6 hex>``) não é de lugar nenhum, e sai por esta mesma
    conta: a varredura lê TODO nó desta casa (:data:`MARCA_DO_NOME`), e não só
    os de nome novo.

    ``de_pe`` é a resposta de :func:`endpoints_de_pe` que quem chama já tem: a
    mesma pergunta semeia :func:`distribuir_ancoras`, e fazê-la duas vezes por
    volta seria um ``pactl`` a mais a cada reconciliação. Sem ela, pergunta.

    Devolve os ``module_id`` derrubados, para o log e para a régua.
    """
    chamar = runner or rodar_pactl
    esperados = {nome_do_endpoint(lugar) for lugar in vivos} - {""}
    caidos: list[str] = []
    servidor = endpoints_de_pe(chamar) if de_pe is None else de_pe
    for nome, instancias in servidor.items():
        if nome in esperados:
            continue
        for module_id, _caminho in instancias:
            chamar(["pactl", "unload-module", module_id])
            caidos.append(module_id)
    if caidos:
        logger.info("haptica_endpoints_orfaos_derrubados", quantos=len(caidos))
    return caidos


class EndpointDeHaptica:
    """O nó de quatro canais que o JOGO enxerga como alto-falante do DualSense.

    **É DO LUGAR, E NÃO DO CONTROLE** (28/09/2026): ``lugar`` é um dos
    :data:`LUGARES`, e o nome, a âncora e o rótulo são dele. O controle que
    está sentado ali chega pelo rádio (a ponte lê o monitor deste nó) ou pelo
    cabo (o laço leva o monitor à placa dele).

    **Não é o ``hefesto_som_<hex6>``:** aquele é a saída da MÁQUINA para o
    controle — a pessoa o escolhe nas saídas de som, e o nome dele tem dono.
    Este aqui é o que o JOGO escolhe sozinho, pelo teste do GE, e o nome dele é
    ditado pelos patches. Só este casa com o teste, então o jogo não se
    confunde entre os dois.
    """

    #: O lugar deste nó. **No corpo da classe**, e não só no ``__init__``: o
    #: dublê montado por ``object.__new__`` não roda o ``__init__``, e estado
    #: que só nasce lá deixa o dublê mais pobre que o produto. ``0`` não é
    #: lugar, e o rótulo sai sem número.
    lugar: int = 0

    def __init__(
        self,
        *,
        lugar: int,
        ancora: Ancora,
        runner: Callable[[list[str]], str | None] | None = None,
        canais: int = CANAIS_DA_HAPTICA,
        taxa_hz: int = TAXA_DO_ENDPOINT,
    ) -> None:
        self.lugar = lugar
        self.ancora = ancora
        self.nome = nome_do_endpoint(lugar)
        self.canais = canais
        self.taxa_hz = taxa_hz
        self.runner = runner or rodar_pactl
        self._module_id: str | None = None

    @property
    def module_id(self) -> str | None:
        return self._module_id

    @property
    def monitor(self) -> str:
        """O monitor de onde a ponte e o laço do cabo leem o PCM da háptica."""
        return f"{self.nome}.monitor" if self.nome else ""

    def iniciar(self) -> bool:
        """Publica o nó. Idempotente CONTRA O SERVIDOR; False quando não deu.

        **A idempotência mudou de alvo em 18/09/2026**, e a razão está em
        :func:`endpoints_de_pe`: guardar só ``self._module_id`` fazia cada
        restart do daemon somar um módulo novo ao servidor. Na mesa dela eram
        vinte e dois.

        Três casos, e o terceiro é o que o vazamento pedia:

        * nenhum de pé com este nome → carrega, como sempre;
        * um de pé com a MESMA âncora → **adota o id** e não carrega nada. É o
          restart do daemon com a mesa no lugar, e recarregar trocaria um nó
          vivo (com o jogo talvez já ligado nele) por outro idêntico;
        * um ou mais de pé com âncora DIFERENTE → derruba todos e carrega um.
          A âncora é o que o jogo lê para calcular o ``ContainerId``; um nó com
          a âncora velha responde a pergunta errada.
        """
        if self._module_id is not None:
            return True
        if not self.nome:
            logger.info("haptica_endpoint_sem_lugar", lugar=self.lugar)
            return False
        instancias = endpoints_de_pe(self.runner).get(self.nome, [])
        iguais = [m for m, caminho in instancias if caminho == self.ancora.declarado]
        if iguais:
            # Adota o primeiro e derruba o resto: mais de um com a mesma âncora
            # já é o vazamento, e deixá-lo de pé o perpetuaria.
            self._module_id = iguais[0]
            for sobrando in [m for m, _ in instancias if m != iguais[0]]:
                self.runner(["pactl", "unload-module", sobrando])
            logger.info(
                "haptica_endpoint_adotado",
                lugar=self.lugar,
                sink=self.nome,
                derrubados=len(instancias) - 1,
            )
            return True
        for velho, _caminho in instancias:
            self.runner(["pactl", "unload-module", velho])
        if instancias:
            logger.info(
                "haptica_endpoint_de_ancora_velha_derrubado",
                lugar=self.lugar,
                quantos=len(instancias),
            )
        if not self._carregar():
            logger.warning("haptica_endpoint_nao_subiu", lugar=self.lugar)
            return False
        logger.info(
            "haptica_endpoint_publicado",
            lugar=self.lugar,
            sink=self.nome,
            ancora=self.ancora.syspath,
        )
        return True

    def _carregar(self) -> bool:
        """Um ``load-module`` do nó do lugar. True = o servidor devolveu o id."""
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
                propriedades_do_endpoint(self.lugar, self.ancora),
            ]
        )
        linhas = [ln.strip() for ln in (saida or "").splitlines() if ln.strip()]
        if not linhas or not linhas[-1].isdigit():
            return False
        self._module_id = linhas[-1]
        self._ligar_os_motores()
        return True

    # O RÓTULO NÃO SE RENOVA MAIS — 28/09/2026. Aqui moravam o
    # `renovar_o_rotulo`, o `rotulo_envelheceu` e o `rotulo_de_agora`
    # (A-HAPTICA-TEM-NOME-DE-CONTROLE-01, 24/09): o nó era do CONTROLE, e o
    # «Háptica do Controle N» renascia quando o assento andava. O nó passou a
    # ser do LUGAR, e o rótulo do lugar não envelhece — quem anda é o controle,
    # e o que troca é o laço ou a ponte, nunca o endpoint.

    def _ligar_os_motores(self) -> None:
        """Põe os canais traseiros em :data:`VOLUME_DOS_MOTORES`, preservando a frente.

        **LÊ ANTES DE ESCREVER.** `pactl set-sink-volume` com quatro valores
        define os QUATRO, e os dois da frente são o alto-falante do controle —
        cravá-los aqui atropelaria o volume que ela escolheu por HID. Então a
        frente volta com o valor que estava, e só os traseiros mudam.

        **NUNCA LEVANTA.** O endpoint já está de pé quando esta função roda; um
        `pactl` que falhou não pode desfazer a publicação. O pior caso é o que
        já acontecia antes desta cura — motores em zero — e ele fica no log.
        """
        atual = self.runner(["pactl", "list", "sinks"]) or ""
        frente = _volume_da_frente(atual, self.nome)
        try:
            self.runner([
                "pactl", "set-sink-volume", self.nome,
                frente[0], frente[1], VOLUME_DOS_MOTORES, VOLUME_DOS_MOTORES,
            ])
        except Exception as exc:  # pragma: no cover — pactl é o mundo de fora
            logger.warning("haptica_motores_sem_volume", lugar=self.lugar, err=str(exc))
            return
        logger.info(
            "haptica_motores_ligados",
            lugar=self.lugar,
            frente=list(frente),
            motores=VOLUME_DOS_MOTORES,
        )

    def parar(self) -> None:
        """Derruba o nó. Silencioso quando ele já não está de pé."""
        if self._module_id is None:
            return
        self.runner(["pactl", "unload-module", self._module_id])
        logger.info("haptica_endpoint_derrubado", lugar=self.lugar, sink=self.nome)
        self._module_id = None

    def __enter__(self) -> EndpointDeHaptica:
        self.iniciar()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.parar()


# ---------------------------------------------------------------------------
# O rumble do pad sem háptica, tocado no lugar — NO-MODO-XBOX-TUDO-FUNCIONA-01
# ---------------------------------------------------------------------------

#: O motor GRANDE e lento do pad de Xbox (o ``strong``) vira um seno de 60 Hz no
#: atuador da ESQUERDA (o canal traseiro esquerdo, o ``motor_left`` do report);
#: o PEQUENO e rápido (o ``weak``), um de 160 Hz no da direita. É o arranjo dos
#: dois motores de um pad de Xbox, e é escolha, não medida: a frequência que o
#: firmware usa na própria emulação ninguém publicou
#: (``docs/protocol/dualsense-energia-e-vibracao.md``, §5). Os dois fecham um
#: número inteiro de voltas em :data:`QUADROS_DO_CICLO`, e o bloco não estala.
FREQUENCIA_DO_FORTE_HZ = 60
FREQUENCIA_DO_FRACO_HZ = 160

#: 10 ms a 48 kHz: o nível do rumble é relido a cada bloco.
QUADROS_POR_BLOCO = 480

#: 50 ms: 3 voltas de 60 Hz e 8 de 160 Hz. O seno vem de uma tabela deste
#: tamanho, e a fase anda em múltiplos do bloco.
QUADROS_DO_CICLO = 2400

#: Quanto silêncio o tocador aguenta de pé antes de sair do endpoint. De pé, o
#: endpoint «toca» e a ponte do rádio fica no modo háptica (que só escreve o
#: bloco com sinal); fora dele, o próximo rumble custa subir o tocador de novo,
#: e até lá quem leva é o HID. Três segundos cobrem a pausa entre dois tiros.
FOLGA_DO_TOCADOR_S = 3.0

#: A latência que se pede ao tocador — explícita, pela regra da casa: sem ela
#: o servidor escolhe um buffer generoso e a vibração chega atrasada.
LATENCIA_DO_TOCADOR_MS = 20

#: Um tocador que falhou (sem binário, morreu, parou de ler, ligou-se ao nó
#: errado) não é relançado a cada rumble: o HID leva, e ele tenta de novo depois.
RECUSA_DO_TOCADOR_S = 60.0

#: Quanto tempo a escrita espera o tocador ler antes de o dar por parado. Um
#: fluxo sem destino (o recuo proibido) não consome nada, e a escrita ficaria
#: presa para sempre.
PRAZO_DA_ESCRITA_S = 1.0

#: O cano entre o daemon e o tocador, em bytes: 4 KiB são 5 ms de áudio de
#: quatro canais. O padrão do kernel (64 KiB, 85 ms) seria atraso puro.
CANO_DO_TOCADOR = 4096

#: Quando conferir o destino no grafo, contados da primeira escrita.
ESPERAS_DA_CONFERENCIA_S: tuple[float, ...] = (0.3, 0.7, 1.0)

#: O começo do nome do NOSSO fluxo no endpoint. É por ele que a partida sabe
#: que o fluxo não é de jogo nenhum (``fluxos_nos_lugares``).
MARCA_DO_TOCADOR = "hefesto-haptica-do-rumble-"

_TAXA = TAXA_DO_ENDPOINT
_BYTES_POR_QUADRO = 4 * CANAIS_DA_HAPTICA


def _seno(frequencia: int) -> array[float]:
    return array(
        "f",
        (math.sin(2.0 * math.pi * frequencia * i / _TAXA) for i in range(QUADROS_DO_CICLO)),
    )


_SENO_DO_FORTE = _seno(FREQUENCIA_DO_FORTE_HZ)
_SENO_DO_FRACO = _seno(FREQUENCIA_DO_FRACO_HZ)
_BLOCO_MUDO = bytes(QUADROS_POR_BLOCO * _BYTES_POR_QUADRO)


def rotulo_do_tocador(lugar: int) -> str:
    """O ``node.name`` do tocador do lugar. Sem endereço: o lugar é o dono."""
    return f"{MARCA_DO_TOCADOR}lugar{int(lugar)}"


def _amplitude(nivel: int) -> float:
    return max(0, min(255, int(nivel))) / 255.0


def bloco_da_haptica(
    fraco: int,
    forte: int,
    *,
    fase: int = 0,
    antes: tuple[int, int] | None = None,
) -> bytes:
    """Um bloco de :data:`QUADROS_POR_BLOCO` quadros, ``float32le``, FL FR RL RR.

    A frente (o alto-falante) sai em silêncio; o traseiro esquerdo leva o
    ``forte`` a :data:`FREQUENCIA_DO_FORTE_HZ` e o direito o ``fraco`` a
    :data:`FREQUENCIA_DO_FRACO_HZ`, com amplitude ``nível / 255``. ``antes`` é o
    par do bloco anterior: a amplitude anda em rampa de um ao outro dentro do
    bloco, e a mudança de nível não vira um estalo no atuador. ``fase`` é o
    quadro do ciclo em que o bloco começa.
    """
    fraco0, forte0 = antes if antes is not None else (fraco, forte)
    a0, a1 = _amplitude(forte0), _amplitude(forte)
    b0, b1 = _amplitude(fraco0), _amplitude(fraco)
    if not (a0 or a1 or b0 or b1):
        return _BLOCO_MUDO
    n = QUADROS_POR_BLOCO
    inicio = int(fase) % QUADROS_DO_CICLO
    indices = [(inicio + i) % QUADROS_DO_CICLO for i in range(n)]
    passo_a, passo_b = (a1 - a0) / n, (b1 - b0) / n
    quadros = array("f", _BLOCO_MUDO)
    forte_ = _SENO_DO_FORTE
    fraco_ = _SENO_DO_FRACO
    quadros[2::4] = array("f", [(a0 + passo_a * i) * forte_[k] for i, k in enumerate(indices)])
    quadros[3::4] = array("f", [(b0 + passo_b * i) * fraco_[k] for i, k in enumerate(indices)])
    if sys.byteorder != "little":  # pragma: no cover — o formato é little-endian
        quadros.byteswap()
    return quadros.tobytes()


def argv_do_tocador(
    sink: str,
    rotulo: str,
    runner: Callable[[list[str]], str | None] | None = None,
) -> list[str]:
    """O comando que toca PCM cru no endpoint ``sink``. ``[]`` = não há como.

    O ``pw-cat`` vai SÓ pelo ``object.serial`` (o índice do ``pactl`` no
    ``pipewire-pulse``, :func:`alto_falante_bt.o_servidor_e_o_pipewire`): pelo
    nome, um nó que não resolve manda o fluxo à saída padrão. Sem serial, o
    ``pacat`` acerta pelo nome. Os dois pedem as mesmas três coisas: não
    recuar para a saída padrão, não se religar a outro nó quando o endpoint
    sai, e não herdar um alvo nem um volume guardados para o programa.
    """
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


def conferir_o_destino_do_tocador(rotulo: str) -> str | None:
    """O ``node.name`` do nó a que o tocador chamado ``rotulo`` se ligou. ``None`` = não sei.

    É o espelho, do lado da reprodução, de
    ``alto_falante_bt.conferir_o_alvo_do_gravador``: lá o nosso nó é a ENTRADA
    do ``Link`` e a resposta é a origem; aqui ele é a SAÍDA e a resposta é o
    destino. ``None`` nunca quer dizer «está certo» (sem ``pw-dump``, com a
    saída ilegível, ou ainda sem ``Link``).
    """
    if not rotulo or shutil.which("pw-dump") is None:
        return None
    try:
        proc = subprocess.run(
            ["pw-dump"], capture_output=True, text=True, timeout=3.0, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    try:
        objetos = json.loads(proc.stdout or "[]")
    except (ValueError, TypeError):
        return None
    nomes: dict[int, str] = {}
    meus: set[int] = set()
    for o in objetos if isinstance(objetos, list) else ():
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


def fluxos_nos_lugares(
    nomes: Iterable[str],
    runner: Callable[[list[str]], str | None] | None = None,
) -> tuple[frozenset[str], frozenset[str]] | None:
    """``(clientes dos nossos tocadores, endpoints com fluxo de outro)``. ``None`` = não sei.

    Uma passada pela listagem LONGA dos fluxos (a curta não diz o nome do
    fluxo): o nosso se reconhece pelo ``node.name`` ou pelo ``media.name`` que
    :func:`argv_do_tocador` lhe dá (:data:`MARCA_DO_TOCADOR`). O fluxo sem
    cliente (um módulo do próprio servidor) não é de jogo.
    """
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
    texto = chamar(["pactl", "list", "sink-inputs"])
    if texto is None:
        return None
    nossos: set[str] = set()
    com_outro: set[str] = set()
    for bloco in texto.split("Sink Input #")[1:]:
        cliente = sink = ""
        nosso = False
        for linha in bloco.splitlines():
            chave, _, valor = linha.strip().partition(":")
            if chave == "Client" and not cliente:
                cliente = valor.strip()
            elif chave == "Sink" and not sink:
                sink = valor.strip()
            elif linha.strip().startswith(("node.name", "media.name")):
                nosso = nosso or MARCA_DO_TOCADOR in linha
        alvo = por_indice.get(sink)
        if alvo is None:
            continue
        sem_cliente = cliente in ("", "n/a", "-")
        if nosso:
            if not sem_cliente:
                nossos.add(cliente)
        elif not sem_cliente:
            com_outro.add(alvo)
    return frozenset(nossos), frozenset(com_outro)


class TocadorDoRumble:
    """O rumble do jogo tocado como háptica no endpoint de UM lugar.

    :meth:`levar` só guarda o nível e acorda o fio — quem chama é o fio da
    vibração do pad, que não pode esperar um processo subir. O fio do tocador
    sobe o processo no primeiro nível não nulo, escreve um bloco a cada 10 ms
    com o nível de agora e sai depois de :data:`FOLGA_DO_TOCADOR_S` de
    silêncio. ``ao_mudar`` é avisado quando o tocador fica de pé e quando sai:
    é a volta do alto-falante, que abre ou fecha o caminho até o controle.
    """

    def __init__(
        self,
        lugar: int,
        *,
        ao_mudar: Callable[[], object] | None = None,
        argv_de: Callable[[str, str], list[str]] | None = None,
        lancar: Callable[..., Any] | None = None,
        conferir: Callable[[str], str | None] | None = None,
        folga_s: float = FOLGA_DO_TOCADOR_S,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self.lugar = int(lugar)
        self.rotulo = rotulo_do_tocador(lugar)
        self._ao_mudar = ao_mudar
        self._argv_de = argv_de or argv_do_tocador
        self._lancar: Callable[..., Any] = lancar or subprocess.Popen
        self._conferir = conferir or conferir_o_destino_do_tocador
        self._folga_s = float(folga_s)
        self._relogio = relogio
        self._trava = threading.Lock()
        self._nivel: tuple[int, int] = (0, 0)
        self._sink = ""
        self._dono = ""
        self._proc: Any = None
        self._vivo = False
        self._recusado_ate = 0.0
        self._acordar = threading.Event()
        self._fim = threading.Event()
        self._fio: threading.Thread | None = None
        #: ``((fraco, forte, fase), bloco)`` do nível parado: o rumble fica
        #: constante por muitos blocos, e o seno não se recalcula à toa.
        self._memoria: dict[tuple[int, int, int], bytes] = {}

    # -- o que se lê de fora ----------------------------------------------

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

    # -- o que se pede ------------------------------------------------------

    def levar(self, fraco: int, forte: int, *, sink: str, dono: str) -> None:
        """O nível de agora. Nunca espera, nunca levanta."""
        par = (max(0, min(255, int(fraco))), max(0, min(255, int(forte))))
        with self._trava:
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
        self._acordar.set()

    def parar(self) -> None:
        """Derruba o processo e o fio. Idempotente."""
        self._fim.set()
        self._acordar.set()
        self._matar(self._proc)
        fio = self._fio
        if fio is not None and fio is not threading.current_thread():
            fio.join(timeout=2.0)

    # -- o fio ---------------------------------------------------------------

    def _avisar(self) -> None:
        aviso = self._ao_mudar
        if aviso is None:
            return
        try:
            aviso()
        except Exception as exc:  # o tocador não cai por um aviso
            logger.debug("haptica_fina_aviso_falhou", lugar=self.lugar, err=str(exc))

    def _recusar(self, motivo: str) -> None:
        self._recusado_ate = self._relogio() + RECUSA_DO_TOCADOR_S
        logger.info("haptica_fina_recusada", lugar=self.lugar, motivo=motivo)

    def _correr(self) -> None:
        while not self._fim.is_set():
            self._acordar.wait(timeout=1.0)
            self._acordar.clear()
            if self._fim.is_set():
                return
            with self._trava:
                nivel, sink = self._nivel, self._sink
            if not any(nivel) or not sink or self._relogio() < self._recusado_ate:
                continue
            self._tocar(sink)

    def _tocar(self, sink: str) -> None:
        argv = self._argv_de(sink, self.rotulo)
        if not argv:
            self._recusar("sem_tocador")
            return
        try:
            proc = self._lancar(
                argv, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.debug("haptica_fina_nao_subiu", lugar=self.lugar, err=str(exc))
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
        except Exception as exc:  # o fio nunca cai por um processo de fora
            logger.debug("haptica_fina_falhou", lugar=self.lugar, err=str(exc))
            motivo = "falhou"
        finally:
            estava_vivo = self._vivo
            self._vivo = False
            self._matar(proc)
            self._proc = None
            if motivo not in ("silencio", "trocou_de_endpoint", "parado"):
                self._recusar(motivo)
            logger.info("haptica_fina_saiu", lugar=self.lugar, motivo=motivo)
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
            if any(nivel):
                silencio_desde = None
            elif silencio_desde is None:
                silencio_desde = agora
            elif agora - silencio_desde >= self._folga_s:
                return "silencio"
            if not self._escrever(fd, self._bloco(nivel, antes, fase)):
                return "parou_de_ler"
            if not self._vivo:
                self._vivo = True
                logger.info("haptica_fina_de_pe", lugar=self.lugar, tocador=binario)
                threading.Thread(
                    target=self._conferir_o_destino, args=(proc, sink), daemon=True,
                    name=f"hefesto-{self.rotulo}-conferencia",
                ).start()
                self._avisar()
            antes = nivel
            fase = (fase + QUADROS_POR_BLOCO) % QUADROS_DO_CICLO
        return "parado"

    def _bloco(self, nivel: tuple[int, int], antes: tuple[int, int], fase: int) -> bytes:
        if nivel != antes:
            self._memoria = {}
            return bloco_da_haptica(nivel[0], nivel[1], fase=fase, antes=antes)
        chave = (nivel[0], nivel[1], fase)
        bloco = self._memoria.get(chave)
        if bloco is None:
            bloco = bloco_da_haptica(nivel[0], nivel[1], fase=fase)
            self._memoria[chave] = bloco
        return bloco

    def _escrever(self, fd: int, dados: bytes) -> bool:
        """Escreve o bloco inteiro; ``False`` = o tocador parou de ler ou morreu."""
        # `poll`, e não `select`: acima do descritor 1023 o `select` levanta
        # (`tests/unit/test_a_espera_passa_do_descritor_1023.py`).
        vista = memoryview(dados)
        espera = select.poll()
        espera.register(fd, select.POLLOUT)
        parado_desde: float | None = None
        while vista and not self._fim.is_set():
            try:
                prontos = espera.poll(100)
            except (OSError, ValueError):
                return False
            if any(ev & (select.POLLERR | select.POLLHUP | select.POLLNVAL) for _, ev in prontos):
                return False
            if not prontos:
                agora = self._relogio()
                parado_desde = agora if parado_desde is None else parado_desde
                if agora - parado_desde >= PRAZO_DA_ESCRITA_S:
                    return False
                continue
            parado_desde = None
            try:
                escritos = os.write(fd, vista)
            except BlockingIOError:
                continue
            except OSError:
                return False
            vista = vista[escritos:]
        return not vista

    def _conferir_o_destino(self, proc: Any, sink: str) -> None:
        """Ligado a outro nó que não o endpoint, o tocador morre — nunca na TV dela."""
        for espera in ESPERAS_DA_CONFERENCIA_S:
            if self._fim.wait(espera) or proc.poll() is not None:
                return
            try:
                destino = self._conferir(self.rotulo)
            except Exception as exc:
                logger.debug("haptica_fina_conferencia_falhou", lugar=self.lugar, err=str(exc))
                destino = None
            if destino is None:
                continue
            if destino == sink:
                return
            # O nome do nó errado não vai ao diário: pode ser a saída dela.
            logger.warning("haptica_fina_ligada_a_outro_no", lugar=self.lugar)
            self._recusado_ate = self._relogio() + RECUSA_DO_TOCADOR_S
            self._matar(proc)
            return
        logger.debug("haptica_fina_nao_conferida", lugar=self.lugar)

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
    "FOLGA_DO_TOCADOR_S",
    "FREQUENCIA_DO_FORTE_HZ",
    "FREQUENCIA_DO_FRACO_HZ",
    "LUGARES",
    "MARCA_DO_ENSAIO",
    "MARCA_DO_TOCADOR",
    "MOLDE_DA_MARCA_DO_LUGAR",
    "MOLDE_DO_NOME",
    "NOME_DA_HAPTICA_DO_CONTROLE",
    "PID_DUALSENSE",
    "QUADROS_POR_BLOCO",
    "VID_SONY",
    "Ancora",
    "EndpointDeHaptica",
    "TocadorDoRumble",
    "ancoras",
    "argv_do_tocador",
    "bloco_da_haptica",
    "conferir_o_destino_do_tocador",
    "distribuir_ancoras",
    "endpoints_de_pe",
    "fluxos_nos_lugares",
    "marca_do_controle",
    "marca_do_lugar",
    "nome_do_endpoint",
    "propriedades_do_endpoint",
    "rotulo_da_haptica",
    "rotulo_do_tocador",
    "varrer_endpoints_orfaos",
]
