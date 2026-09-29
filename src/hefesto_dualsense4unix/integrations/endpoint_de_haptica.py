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
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    CANAIS_DA_HAPTICA,
    HEX_DO_SUFIXO,
    rodar_pactl,
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
) -> dict[int, Ancora]:
    """Uma âncora por LUGAR, e NUNCA a mesma para dois. Função pura.

    **Duas âncoras iguais são dois endpoints com o mesmo ``ContainerId``**, e
    aí o jogo não distingue os lugares — a háptica do jogador 2 iria para o
    device KS do jogador 1.

    **POR LUGAR DESDE 28/09/2026** (A-HAPTICA-CHEGA-A-QUEM-ENTRA-DEPOIS-01): as
    chaves eram os ``uniq`` dos controles no rádio, e passaram a ser os lugares
    (:data:`LUGARES`). A posse é a mesma, nos mesmos três passos; faltando
    âncora, fica de fora o lugar de número MAIOR.

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
    3. os que sobram, em ordem, recebem as âncoras ainda LIVRES.

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
    for lugar in ordem:
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


__all__ = [
    "AGULHAS",
    "LUGARES",
    "MARCA_DO_ENSAIO",
    "MOLDE_DA_MARCA_DO_LUGAR",
    "MOLDE_DO_NOME",
    "NOME_DA_HAPTICA_DO_CONTROLE",
    "PID_DUALSENSE",
    "VID_SONY",
    "Ancora",
    "EndpointDeHaptica",
    "ancoras",
    "distribuir_ancoras",
    "endpoints_de_pe",
    "marca_do_controle",
    "marca_do_lugar",
    "nome_do_endpoint",
    "propriedades_do_endpoint",
    "rotulo_da_haptica",
    "varrer_endpoints_orfaos",
]
