"""O endpoint que o rádio não tem — HAPTICA-POR-RADIO-01, P3.

Pelo CABO a vibração dos jogos da Sony viaja como áudio: o jogo abre o endpoint
de quatro canais do controle e toca os canais 3 e 4, que são os dois motores.
Pelo RÁDIO o DualSense não tem placa de som nenhuma, e sem endpoint o jogo não
tem onde tocar — ele desiste antes de olhar o HID.

Este módulo publica o endpoint que falta: um ``module-null-sink`` do PipeWire
vestido de DualSense, um por APARELHO — ver «UM ENDPOINT POR APARELHO», abaixo.

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
Controller)», com o número do jogador, que se renova quando o número anda
(:meth:`EndpointDeHaptica.renovar_o_rotulo`, nunca com jogo aberto).

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

UM ENDPOINT POR APARELHO — 02/10/2026
-------------------------------------
A-HAPTICA-E-POR-APARELHO-01, pela palavra dela de 29/09, à pergunta da háptica
de P1 a P4: *«todas as features são um por aparelho. sempre.»* Ela REVOGA a
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

**O preço, que ela aceitou na pergunta:** o registro que o jogo lê (o device
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
import re
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
from hefesto_dualsense4unix.integrations.vestido_de_dualsense import (
    PID_DUALSENSE,
    VID_SONY,
    campos_da_identidade,
    campos_do_nome,
    com_o_nome_da_sony,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


TAXA_DO_ENDPOINT = 48000

MOLDE_DO_NOME = (
    "alsa_output.usb-Sony_Interactive_Entertainment_"
    "DualSense_Wireless_Controller_HEFESTO{marca}-00.HiFi__Speaker__sink"
)
#: A MARCA que separa os nós DESTA casa dos de um DualSense por cabo de
MARCA_DO_NOME = "HEFESTO"

#: conta das âncoras do ``doctor.sh`` (uma por DualSense, até quatro).
LUGARES: tuple[int, ...] = (1, 2, 3, 4)

MARCA_DO_ENSAIO = "hefesto.origem=ensaio"

AGULHAS = (
    "alsa_output.usb-Sony_Interactive_Entertainment_",
    "Wireless_Controller",
    "Speaker__sink",
)
MAX_NOME = 127

PRIORIDADE_DA_SESSAO = 0

#: era pra tá assim eu acho"*.  <!-- noqa-acento: citação literal dela -->
#: a vibração (a háptica do DualSense viaja como áudio nos traseiros); em zero,
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


def _ler(caminho: Path) -> str:
    try:
        return caminho.read_text(encoding="ascii", errors="replace").strip()
    except OSError:
        return ""


RAIZ_DO_SYSFS = Path("/sys")


def ancoras(sysfs: Path | None = None) -> list[Ancora]:
    """Os ``usb_device`` que servem de âncora, na ordem do barramento."""
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
    aparelhos: Iterable[str],
    disponiveis: Iterable[Ancora],
    de_pe: Mapping[str, Sequence[tuple[str, str]]] | None = None,
    *,
    ja_postas: Mapping[str, Ancora] | None = None,
    ocupados: Iterable[str] = (),
) -> dict[str, Ancora]:
    """Uma âncora por APARELHO, e NUNCA a mesma para dois. Função pura."""
    lista = list(disponiveis)
    por_aparelho = {a.syspath: a for a in lista}
    por_declarado = {a.declarado: a for a in lista}
    ordem = sorted({str(m) for m in aparelhos if nome_da_marca(str(m))})
    postas: dict[str, Ancora] = {}
    tomadas: set[str] = set()

    def tomar(marca: str, ancora: Ancora | None) -> bool:
        if ancora is None or ancora.syspath in tomadas:
            return False
        postas[marca] = ancora
        tomadas.add(ancora.syspath)
        return True

    lembradas = ja_postas or {}
    for marca in ordem:
        lembrada = lembradas.get(marca)
        if lembrada is not None and lembrada.syspath in por_aparelho:
            tomar(marca, lembrada)
    servidor = de_pe or {}
    for marca in ordem:
        if marca in postas:
            continue
        for _module_id, caminho in servidor.get(nome_da_marca(marca), ()):
            if tomar(marca, por_declarado.get(caminho)):
                break
    livres = (a for a in lista if a.syspath not in tomadas)
    na_mesa = {str(m) for m in ocupados}
    for marca in [m for m in ordem if m in na_mesa] + [m for m in ordem if m not in na_mesa]:
        if marca in postas:
            continue
        for ancora in livres:
            if tomar(marca, ancora):
                break
    return postas


def nome_da_marca(marca: str) -> str:
    """O nome do nó do aparelho desta marca, ou "" quando ela não tem a forma de uma."""
    if not isinstance(marca, str) or not marca.startswith(PREFIXO_DA_MARCA_DO_APARELHO):
        return ""
    letras = marca[len(PREFIXO_DA_MARCA_DO_APARELHO) :]
    if len(letras) != TAMANHO_DA_MARCA_DO_APARELHO or any(
        ch not in LETRAS_DA_MARCA_DO_APARELHO for ch in letras
    ):
        return ""
    nome = MOLDE_DO_NOME.format(marca=marca)
    return nome if len(nome) <= MAX_NOME else ""


def nome_do_endpoint(uniq: str) -> str:
    """O nome do nó do controle ``uniq``, ou "" quando ele não dá identidade."""
    return nome_da_marca(marca_do_aparelho(uniq))


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
        *campos_do_nome(),
        f"device.description='{rotulo}'",
        f"priority.session={PRIORIDADE_DA_SESSAO}",
        "device.icon_name=audio-speakers",
        *campo_do_controle(uniq),
    )
    return 'sink_properties="' + " ".join(campos) + '"'


def endpoints_de_pe(
    runner: Callable[[list[str]], str | None] | None = None,
) -> dict[str, list[tuple[str, str]]]:
    """Os endpoints DESTA casa que estão de pé NO SERVIDOR, por nome de sink."""
    chamar = runner or rodar_pactl
    saida = chamar(["pactl", "list", "short", "modules"]) or ""
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


def _volume_da_frente(saida_do_pactl: str, nome_do_sink: str) -> tuple[str, str]:
    """Os dois volumes da FRENTE deste sink, na forma que o `pactl` aceita."""
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
    vivos: Iterable[str],
    runner: Callable[[list[str]], str | None] | None = None,
    *,
    de_pe: Mapping[str, Sequence[tuple[str, str]]] | None = None,
) -> list[str]:
    """Derruba todo endpoint desta casa que não é de um aparelho vivo.

    ``vivos`` são as MARCAS dos aparelhos cujo nó fica de pé AGORA
    (:func:`nome_da_marca`). O que sobra é resto de sessão anterior — e resto
    de sessão anterior não é inofensivo: ele entra na lista de saídas de som da
    pessoa com o mesmo nome do endpoint bom, e o jogo que procura o
    alto-falante do DualSense pode achar o morto.

    **OS NOMES DE ANTES CAEM NA PRIMEIRA VOLTA DEPOIS DO INSTALL.** O endpoint
    por lugar (``LUGAR<n>``, de 28/09 a 02/10) e o por rabo de endereço
    (``HEFESTO<6 hex>``, até 28/09) não são de aparelho nenhum, e saem por esta
    mesma conta: a varredura lê TODO nó desta casa (:data:`MARCA_DO_NOME`), e
    não só os de nome novo.

    ``de_pe`` é a resposta de :func:`endpoints_de_pe` que quem chama já tem: a
    mesma pergunta semeia :func:`distribuir_ancoras`, e fazê-la duas vezes por
    volta seria um ``pactl`` a mais a cada reconciliação. Sem ela, pergunta.

    Devolve os ``module_id`` derrubados, para o log e para a régua.
    """
    chamar = runner or rodar_pactl
    esperados = {nome_da_marca(marca) for marca in vivos} - {""}
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
        self.nome = nome_da_marca(self.marca)
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

    def iniciar(self) -> bool:
        """Publica o nó. Idempotente CONTRA O SERVIDOR; False quando não deu."""
        if self._module_id is not None:
            return True
        if not self.nome:
            logger.info("haptica_endpoint_sem_identidade")
            return False
        instancias = endpoints_de_pe(self.runner).get(self.nome, [])
        iguais = [m for m, caminho in instancias if caminho == self.ancora.declarado]
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
        """O rótulo que este nó teria se nascesse AGORA."""
        return descricao_da_haptica(self.uniq)

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
        except Exception:  # pragma: no cover - defensivo: numerador explodindo
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
        """Põe os canais traseiros em :data:`VOLUME_DOS_MOTORES`, preservando a frente."""
        atual = self.runner(["pactl", "list", "sinks"]) or ""
        frente = _volume_da_frente(atual, self.nome)
        try:
            self.runner([
                "pactl", "set-sink-volume", self.nome,
                frente[0], frente[1], VOLUME_DOS_MOTORES, VOLUME_DOS_MOTORES,
            ])
        except Exception as exc:  # pragma: no cover — pactl é o mundo de fora
            logger.warning("haptica_motores_sem_volume", controle=self.marca, err=str(exc))
            return
        logger.info(
            "haptica_motores_ligados",
            controle=self.marca,
            frente=list(frente),
            motores=VOLUME_DOS_MOTORES,
        )

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


_SENO_DO_FORTE = _seno(FREQUENCIA_DO_FORTE_HZ)
_SENO_DO_FRACO = _seno(FREQUENCIA_DO_FRACO_HZ)
_BLOCO_MUDO = bytes(QUADROS_POR_BLOCO * _BYTES_POR_QUADRO)


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


def conferir_o_destino_do_tocador(rotulo: str) -> str | None:
    """O ``node.name`` do nó a que o tocador chamado ``rotulo`` se ligou. ``None`` = não sei."""
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
    ) -> None:
        self.marca = str(marca)
        self.rotulo = rotulo_do_tocador(self.marca)
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
        self._memoria: dict[tuple[int, int, int], bytes] = {}


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


    def _avisar(self) -> None:
        aviso = self._ao_mudar
        if aviso is None:
            return
        try:
            aviso()
        except Exception as exc:
            logger.debug("haptica_fina_aviso_falhou", controle=self.marca, err=str(exc))

    def _recusar(self, motivo: str) -> None:
        self._recusado_ate = self._relogio() + RECUSA_DO_TOCADOR_S
        logger.info("haptica_fina_recusada", controle=self.marca, motivo=motivo)

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
            self._vivo = False
            self._matar(proc)
            self._proc = None
            if motivo not in ("silencio", "trocou_de_endpoint", "parado"):
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
                logger.info("haptica_fina_de_pe", controle=self.marca, tocador=binario)
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
                logger.debug("haptica_fina_conferencia_falhou", controle=self.marca, err=str(exc))
                destino = None
            if destino is None:
                continue
            if destino == sink:
                return
            logger.warning("haptica_fina_ligada_a_outro_no", controle=self.marca)
            self._recusado_ate = self._relogio() + RECUSA_DO_TOCADOR_S
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
    "FOLGA_DO_TOCADOR_S",
    "FREQUENCIA_DO_FORTE_HZ",
    "FREQUENCIA_DO_FRACO_HZ",
    "LUGARES",
    "MARCA_DO_ENSAIO",
    "MARCA_DO_TOCADOR",
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
    "descricao_da_haptica",
    "distribuir_ancoras",
    "endpoints_de_pe",
    "fluxos_nos_endpoints",
    "marca_do_aparelho",
    "nome_da_marca",
    "nome_do_endpoint",
    "propriedades_do_endpoint",
    "rotulo_da_haptica",
    "rotulo_do_tocador",
    "rotulo_no_ar",
    "varrer_endpoints_orfaos",
]
