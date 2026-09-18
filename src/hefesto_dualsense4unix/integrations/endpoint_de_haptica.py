"""O endpoint que o rádio não tem — HAPTICA-POR-RADIO-01, P3.

Pelo CABO a vibração dos jogos da Sony viaja como áudio: o jogo abre o endpoint
de quatro canais do controle e toca os canais 3 e 4, que são os dois motores.
Pelo RÁDIO o DualSense não tem placa de som nenhuma, e sem endpoint o jogo não
tem onde tocar — ele desiste antes de olhar o HID.

Este módulo publica o endpoint que falta: um ``module-null-sink`` do PipeWire
vestido de DualSense, um por controle no rádio.

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
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    CANAIS_DA_HAPTICA,
    HEX_DO_SUFIXO,
    rodar_pactl,
    so_hex,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: O VID/PID que o GE exige NO PROPLIST — não no aparelho.
VID_SONY = "054c"
PID_DUALSENSE = "0ce6"

TAXA_DO_ENDPOINT = 48000

#: As três agulhas que os patches do GE procuram no nome, e um discriminador
#: por controle: dois endpoints de nome IGUAL viram um só (patch 0186,
#: `is_shared_sony_mono_backend_name`), e aí a háptica de dois controles iria
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


def distribuir_ancoras(uniqs: Sequence[str], disponiveis: Iterable[Ancora]) -> dict[str, Ancora]:
    """Uma âncora por controle, sempre a mesma para o mesmo ``uniq``.

    **Duas âncoras iguais são dois endpoints com o mesmo ``ContainerId``**, e
    aí o jogo não distingue os controles — a háptica do jogador 2 iria para o
    device KS do jogador 1. A distribuição é por ordem dos dois lados, que é
    determinística e não depende de quando cada controle conectou.
    """
    lista = list(disponiveis)
    return {uniq: lista[i] for i, uniq in enumerate(sorted(set(uniqs))) if i < len(lista)}


def marca_do_controle(uniq: str) -> str:
    """Os seis hex do rabo do ``uniq`` — a identidade que sobrevive a hotplug.

    A mesma de :func:`alto_falante_bt.nome_do_sink`, e pelo mesmo motivo: o
    ``hidrawN`` muda a cada reconexão, o endereço do controle não.
    """
    rabo = so_hex(str(uniq))
    return rabo[-HEX_DO_SUFIXO:] if len(rabo) >= HEX_DO_SUFIXO else ""


def nome_do_endpoint(uniq: str) -> str:
    """O nome do nó, ou "" quando o ``uniq`` não dá identidade.

    "" é recusa, não um nome vazio: publicar um nó anônimo faria dois controles
    disputarem o mesmo endpoint.
    """
    marca = marca_do_controle(uniq)
    if not marca:
        return ""
    nome = MOLDE_DO_NOME.format(marca=marca)
    return nome if len(nome) <= MAX_NOME else ""


def propriedades_do_endpoint(uniq: str, ancora: Ancora) -> str:
    """O ``sink_properties=``, ENTRE ASPAS DUPLAS.

    **As aspas são a cura conhecida desta casa**, paga em 06/09/2026: o parser
    do ``pipewire-pulse`` corta o valor no primeiro ESPAÇO quando ele não vem
    entre aspas, e só a primeira propriedade chega — com a régua dando verde
    por ler o argv em vez do nó.
    """
    marca = marca_do_controle(uniq)
    campos = (
        "device.bus=usb",
        f"device.vendor.id={VID_SONY}",
        f"device.product.id={PID_DUALSENSE}",
        f"sysfs.path={ancora.declarado}",
        "device.vendor.name='Sony Interactive Entertainment'",
        f"device.description='DualSense {marca} (háptica)'",
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
    for linha in saida.splitlines():
        if _MODULO_NULL_SINK not in linha or MARCA_DO_NOME not in linha:
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
        if nome:
            de_pe.setdefault(nome, []).append((partes[0].strip(), caminho))
    return de_pe


def varrer_endpoints_orfaos(
    vivos: Iterable[str],
    runner: Callable[[list[str]], str | None] | None = None,
) -> list[str]:
    """Derruba todo endpoint desta casa que não pertence a um controle vivo.

    ``vivos`` são os ``uniq`` que estão na mesa AGORA. O que sobra é resto de
    sessão anterior — e resto de sessão anterior não é inofensivo: ele entra na
    lista de saídas de som da pessoa com o mesmo nome do endpoint bom, e o jogo
    que procura o alto-falante do DualSense pode achar o morto.

    Devolve os ``module_id`` derrubados, para o log e para a régua.
    """
    chamar = runner or rodar_pactl
    esperados = {nome_do_endpoint(u) for u in vivos} - {""}
    caidos: list[str] = []
    for nome, instancias in endpoints_de_pe(chamar).items():
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

    **São DOIS nós por controle no rádio, e a diferença é de identidade:** o
    ``hefesto_som_<hex6>`` é a saída da MÁQUINA para o controle — a pessoa o
    escolhe nas saídas de som, e o nome dele tem dono. Este aqui é o que o JOGO
    escolhe sozinho, pelo teste do GE, e o nome dele é ditado pelos patches.
    Só este casa com o teste, então o jogo não se confunde entre os dois.
    """

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
        self.ancora = ancora
        self.nome = nome_do_endpoint(uniq)
        self.canais = canais
        self.taxa_hz = taxa_hz
        self.runner = runner or rodar_pactl
        self._module_id: str | None = None

    @property
    def module_id(self) -> str | None:
        return self._module_id

    @property
    def monitor(self) -> str:
        """O monitor de onde a ponte lê o PCM da háptica."""
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
          restart do daemon com o controle no lugar, e recarregar trocaria um
          nó vivo (com o jogo talvez já ligado nele) por outro idêntico;
        * um ou mais de pé com âncora DIFERENTE → derruba todos e carrega um.
          A âncora é o que o jogo lê para calcular o ``ContainerId``; um nó com
          a âncora velha responde a pergunta errada.
        """
        if self._module_id is not None:
            return True
        if not self.nome:
            logger.info("haptica_endpoint_sem_identidade", uniq=self.uniq)
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
                uniq=self.uniq,
                sink=self.nome,
                derrubados=len(instancias) - 1,
            )
            return True
        for velho, _caminho in instancias:
            self.runner(["pactl", "unload-module", velho])
        if instancias:
            logger.info(
                "haptica_endpoint_de_ancora_velha_derrubado",
                uniq=self.uniq,
                quantos=len(instancias),
            )
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
                propriedades_do_endpoint(self.uniq, self.ancora),
            ]
        )
        linhas = [ln.strip() for ln in (saida or "").splitlines() if ln.strip()]
        if not linhas or not linhas[-1].isdigit():
            logger.warning("haptica_endpoint_nao_subiu", uniq=self.uniq)
            return False
        self._module_id = linhas[-1]
        logger.info(
            "haptica_endpoint_publicado",
            uniq=self.uniq,
            sink=self.nome,
            ancora=self.ancora.syspath,
        )
        return True

    def parar(self) -> None:
        """Derruba o nó. Silencioso quando ele já não está de pé."""
        if self._module_id is None:
            return
        self.runner(["pactl", "unload-module", self._module_id])
        logger.info("haptica_endpoint_derrubado", uniq=self.uniq, sink=self.nome)
        self._module_id = None

    def __enter__(self) -> EndpointDeHaptica:
        self.iniciar()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.parar()


__all__ = [
    "AGULHAS",
    "MOLDE_DO_NOME",
    "PID_DUALSENSE",
    "VID_SONY",
    "Ancora",
    "EndpointDeHaptica",
    "ancoras",
    "distribuir_ancoras",
    "endpoints_de_pe",
    "marca_do_controle",
    "nome_do_endpoint",
    "propriedades_do_endpoint",
    "varrer_endpoints_orfaos",
]
