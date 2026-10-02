"""O exame da mesa — as conferências que respondem "está tudo certo?".

O `scripts/doctor.sh` sabe responder isso desde sempre, em milhares de linhas
de diagnóstico (o número medido está no documento da sprint, que envelhece
sozinho e não obriga esta página a envelhecer junto). O
problema nunca foi a medição: é que ela só existe para quem abre terminal, que
é a minoria de quem usa o produto. Esta é a mesma leitura, num formato que a
aba Conexões mostra na seção Check-up — uma linha por achado, sem teto.

POR QUE UM MÓDULO PYTHON, E NÃO UM `doctor.sh --json`. O doctor NÃO viaja nos
pacotes: o `install.sh:3778-3780` só copia o `storm_watch.sh`, a spec do Fedora
instala `install-host-udev.sh` e `dkms_lib.sh`, e o manifesto Flatpak não o
menciona. Uma aba que dependesse dele nasceria VAZIA para quem instalou por
pacote — que é a maioria futura. O padrão que a casa já usa três vezes é o
inverso: o módulo viaja dentro do wheel e o doctor é que o consome
(`sentinela_do_wrapper.py` ← `scripts/doctor.sh:1673`).

A DISCIPLINA, herdada de `storm_doctor.py:1-9` e válida linha a linha aqui:

- **Somente leitura.** Nenhuma função deste arquivo escreve em lugar nenhum.
- **Sem root, nunca.** Checagem que precisaria de `sudo` devolve
  ``ESTADO_NAO_SEI`` — jamais falha. O `/var/lib/bluetooth` é proibido por
  isso: `check_bt_bonds_persistidos` (`scripts/doctor.sh:3111-3114`) começa
  com `sudo -n true` e desiste sem ele.
- **Cada caminho entra por argumento**, com default igual ao sistema real. É o
  que permite testar com fixture e é o que permite ao retrato das abas montar
  a tela sem fotografar a máquina de quem mantém o projeto.
- **100% stdlib.** O doctor chama este arquivo pelo `python3` do sistema
  (`check_sentinela_wrapper` não usa o `_python_do_produto`), então uma
  dependência de terceiros aqui viraria uma linha muda na conferência.

O QUE ESTE MÓDULO NÃO FAZ, e é deliberado: ele não devolve frase de tela
pronta nem cor. Devolve chave, estado e um "porquê" curto em português —
escrito AQUI, nunca copiado da mensagem do doctor. As mensagens de lá carregam
`sudo` e carregam endereço de rádio (`scripts/doctor.sh:3288` imprime o MAC),
e as duas coisas acabariam num PNG versionado pelo caminho do retrato das abas.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - só para o verificador de tipos
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import Leitura, Ordem
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

ESTADO_CERTO = "certo"
ESTADO_ATENCAO = "atencao"  # (noqa-acento): chave de máquina, ASCII por contrato
ESTADO_PROBLEMA = "problema"
ESTADO_NAO_SEI = "nao_sei"

ROTULO_ENERGIA_DO_RADIO = "Economia de energia desligada"
ROTULO_ENERGIA_DAS_PORTAS = "Energia das portas"
ROTULO_PAREAMENTOS = "Pareamentos salvos"
ROTULO_SUPORTE_AO_CONTROLE = "Suporte ao controle"
ROTULO_VIZINHANCA = "Vizinhança das portas"

ROTULO_DA_ORDEM = "Mudança recomendada"

ROTULO_DAS_ORDENS = "Mudanças recomendadas"

CHAVE_DAS_ORDENS = "ordens_da_mesa"

_CAMINHO_DE_DISPOSITIVO = re.compile(r"/org/bluez/hci[0-9]+/dev_[0-9A-Fa-f_]+")


@dataclass(frozen=True)
class Item:
    """Uma linha do exame: o que foi conferido e o que se achou.

    ``porque`` é a MEDIÇÃO em uma frase, não a mensagem do doctor. ``cura`` é o
    que a pessoa pode fazer sem terminal e sem senha — ``None`` quando não há
    nada a fazer, que é o caso normal do estado ``certo``.

    ``ordem`` é a ORDEM DE SERVIÇO desta linha, quando ela tem uma
    (`integrations/ordens_da_mesa.Ordem`): o imperativo, as três linhas de
    porquê e o selo de procedência de cada uma. É por este campo que a cura
    deixa de morar só no ``set_tooltip_text`` — a tela desenha um card com o
    que está aqui, e quem não passa o mouse por cima da palavra certa passa a
    descobrir o que fazer.

    O campo é ``None`` nas cinco conferências, e é assim que ele fica: uma
    conferência responde "está certo?" e uma ordem responde "faça isto". Item
    com ordem é card; item sem ordem continua sendo uma linha da tira.
    """

    chave: str
    rotulo: str
    estado: str
    porque: str
    cura: str | None = None
    ordem: Ordem | None = None

    def como_dicionario(self) -> dict[str, object]:
        """Forma JSON — é o que o `doctor.sh` consome (`--censo`)."""
        forma: dict[str, object] = {
            "chave": self.chave,
            "rotulo": self.rotulo,
            "estado": self.estado,
            "porque": self.porque,
            "cura": self.cura,
        }
        if self.ordem is not None:
            forma["ordem"] = self.ordem.como_dicionario()
        return forma


def _texto_de(caminho: Path) -> str | None:
    """Conteúdo de um arquivo do sistema, ou ``None`` se não deu para ler."""
    try:
        return caminho.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def energia_do_radio(
    *,
    parametro: Path = Path("/sys/module/btusb/parameters/enable_autosuspend"),
    conf: Path = Path("/etc/modprobe.d/hefesto-btusb-no-autosuspend.conf"),
) -> Item:
    """O rádio dos controles está proibido de dormir? (`doctor.sh:2401-2417`)

    O `btusb` liga o autosuspend do adaptador no probe, por default do módulo;
    o conf do Hefesto corta na raiz e o esperado pós-boot é ``N``.

    O ramo do meio é o que engana: com o conf JÁ instalado e o módulo ainda com
    o valor antigo, a cura está no disco e não está valendo — só vale no
    próximo probe. Verde ali seria dizer que o rádio não dorme enquanto ele
    ainda dorme.
    """
    valor = _texto_de(parametro)
    if valor in ("N", "0"):
        return Item(
            chave="energia_do_radio",
            rotulo=ROTULO_ENERGIA_DO_RADIO,
            estado=ESTADO_CERTO,
            porque="O sistema não desliga o rádio dos controles.",
        )
    if conf.is_file():
        if not valor:
            return Item(
                chave="energia_do_radio",
                rotulo=ROTULO_ENERGIA_DO_RADIO,
                estado=ESTADO_NAO_SEI,
                porque=(
                    "A regra está no lugar; nenhum adaptador BT ligado agora."
                ),
            )
        return Item(
            chave="energia_do_radio",
            rotulo=ROTULO_ENERGIA_DO_RADIO,
            estado=ESTADO_ATENCAO,
            porque=(
                "A regra está no lugar; vale no próximo encaixe do adaptador."
            ),
            cura=(
                "Desencaixe e encaixe o adaptador Bluetooth de novo, ou "
                "reinicie o computador."
            ),
        )
    return Item(
        chave="energia_do_radio",
        rotulo=ROTULO_ENERGIA_DO_RADIO,
        estado=ESTADO_ATENCAO,
        porque=(
            "O sistema pode desligar o adaptador, e o controle cai."
        ),
        cura="Rode a instalação do Hefesto de novo: a regra entra por padrão.",
    )


def energia_das_portas(
    *, raiz: Path = Path("/sys/bus/usb/devices")
) -> Item:
    """Nenhuma porta USB em economia de energia? (`doctor.sh:2301-2321`)"""
    total = 0
    dormindo = 0
    try:
        portas = sorted(raiz.iterdir())
    except OSError:
        portas = []
    for porta in portas:
        controle = _texto_de(porta / "power" / "control")
        if controle is None or not (porta / "idVendor").exists():
            continue
        total += 1
        if controle == "auto":
            dormindo += 1
    if total == 0:
        return Item(
            chave="energia_das_portas",
            rotulo=ROTULO_ENERGIA_DAS_PORTAS,
            estado=ESTADO_NAO_SEI,
            porque="Este sistema não deixa ler o estado das portas USB.",
        )
    if dormindo == 0:
        return Item(
            chave="energia_das_portas",
            rotulo=ROTULO_ENERGIA_DAS_PORTAS,
            estado=ESTADO_CERTO,
            porque=(
                f"As {total} portas USB ficam sempre ligadas."
            ),
        )
    return Item(
        chave="energia_das_portas",
        rotulo=ROTULO_ENERGIA_DAS_PORTAS,
        estado=ESTADO_ATENCAO,
        porque=(
            f"{dormindo} de {total} portas USB podem dormir e derrubar aparelhos."
        ),
        cura="Rode a instalação do Hefesto de novo: a regra entra por padrão.",
    )


def suporte_ao_controle(
    *,
    modulos: Path = Path("/proc/modules"),
    diretorio_do_modulo: Path = Path("/sys/module/hid_playstation"),
) -> Item:
    """O `hid_playstation` está de pé? (`doctor.sh:393-401`)"""
    texto = _texto_de(modulos)
    if texto is not None:
        for linha in texto.splitlines():
            if linha.startswith("hid_playstation "):
                return Item(
                    chave="suporte_ao_controle",
                    rotulo=ROTULO_SUPORTE_AO_CONTROLE,
                    estado=ESTADO_CERTO,
                    porque="O sistema já sabe falar com o DualSense.",
                )
    if diretorio_do_modulo.is_dir():
        return Item(
            chave="suporte_ao_controle",
            rotulo=ROTULO_SUPORTE_AO_CONTROLE,
            estado=ESTADO_CERTO,
            porque="O suporte ao DualSense vem embutido no sistema.",
        )
    return Item(
        chave="suporte_ao_controle",
        rotulo=ROTULO_SUPORTE_AO_CONTROLE,
        estado=ESTADO_ATENCAO,
        porque=(
            "O sistema ainda não sabe falar com o DualSense."
        ),
        cura="Reinicie o computador; se continuar, o kernel pode ser antigo demais.",
    )


def pareamentos(
    *, executar: Callable[[Sequence[str]], str | None] | None = None
) -> Item:
    """Algum controle com pareamento pela metade? (`doctor.sh:3274-3292`)"""
    from hefesto_dualsense4unix.integrations import bluez_dbus

    leitor = bluez_dbus.dono() if executar is None else bluez_dbus.pelo_executor(executar)
    arvore = leitor.caminhos()
    if arvore is None:
        return Item(
            chave="pareamentos",
            rotulo=ROTULO_PAREAMENTOS,
            estado=ESTADO_NAO_SEI,
            porque="Não deu para perguntar ao Bluetooth do sistema.",
        )
    caminhos = [c for c in arvore if _CAMINHO_DE_DISPOSITIVO.fullmatch(c)]
    if not caminhos:
        return Item(
            chave="pareamentos",
            rotulo=ROTULO_PAREAMENTOS,
            estado=ESTADO_CERTO,
            porque=(
                "Nenhum controle pareado por BT ainda."
            ),
        )
    pela_metade = 0
    sem_resposta = 0
    for caminho in caminhos:
        pareado = bluez_dbus.como_booleano(
            leitor.propriedade(caminho, bluez_dbus.APARELHO, "Paired")
        )
        vinculado = bluez_dbus.como_booleano(
            leitor.propriedade(caminho, bluez_dbus.APARELHO, "Bonded")
        )
        if pareado is None or vinculado is None:
            sem_resposta += 1
            continue
        if pareado and not vinculado:
            pela_metade += 1
    if pela_metade:
        return Item(
            chave="pareamentos",
            rotulo=ROTULO_PAREAMENTOS,
            estado=ESTADO_PROBLEMA,
            porque=(
                f"{pela_metade} pareamento(s) pela metade: o controle cai."
            ),
            cura=(
                "No Bluetooth do sistema, remova esse controle e pareie de "
                "novo segurando o botão PS."
            ),
        )
    if sem_resposta == len(caminhos):
        return Item(
            chave="pareamentos",
            rotulo=ROTULO_PAREAMENTOS,
            estado=ESTADO_NAO_SEI,
            porque="O BT não diz se o pareamento está inteiro.",
        )
    return Item(
        chave="pareamentos",
        rotulo=ROTULO_PAREAMENTOS,
        estado=ESTADO_CERTO,
        porque=(
            f"Nenhum dos {len(caminhos)} pareamentos está "
            "pela metade."
        ),
    )


def _vizinhancas_do_sistema() -> Sequence[object]:
    """Os pares de portas coladas, lidos pela seção "A mesa" da mesma aba."""
    from hefesto_dualsense4unix.integrations import mesa_de_radio

    return mesa_de_radio.ler_a_mesa().apertadas


def vizinhanca_das_portas(
    *,
    leitura: Callable[[], Sequence[object]] | None = None,
    altura_da_antena: str | None = None,
    linha_de_visada: str | None = None,
) -> Item:
    """Há aparelho encaixado na porta colada à de outro rádio?"""
    ler = leitura if leitura is not None else _vizinhancas_do_sistema
    try:
        apertadas = list(ler())
    except Exception:
        return Item(
            chave="vizinhanca_das_portas",
            rotulo=ROTULO_VIZINHANCA,
            estado=ESTADO_NAO_SEI,
            porque="Não deu para ler onde cada aparelho está encaixado.",
        )
    if not apertadas:
        return Item(
            chave="vizinhanca_das_portas",
            rotulo=ROTULO_VIZINHANCA,
            estado=ESTADO_CERTO,
            porque="Nenhum aparelho colado a um adaptador BT.",
        )
    nada_declarado = altura_da_antena is None and linha_de_visada is None
    if nada_declarado:
        cura = (
            "Abra “Rádio e Adaptadores”, logo abaixo: declare a altura da antena e "
            "a linha de visada para o exame explicar o alcance em vez de só "
            "medi-lo, ou mude um dos dois aparelhos para uma porta mais "
            "longe."
        )
    else:
        cura = (
            "Mude um dos dois para uma porta mais longe."
        )
    return Item(
        chave="vizinhanca_das_portas",
        rotulo=ROTULO_VIZINHANCA,
        estado=ESTADO_ATENCAO,
        porque=(
            f"{len(apertadas)} par(es) de rádios em portas coladas."
        ),
        cura=cura,
    )


def leitura_do_sistema() -> Leitura:
    """O que o catálogo de ordens precisa ler, direto do ``/sys``."""
    from hefesto_dualsense4unix.integrations import ordens_da_mesa
    from hefesto_dualsense4unix.integrations.censo_do_barramento import (
        ler_o_barramento,
    )
    from hefesto_dualsense4unix.integrations.entradas_do_gabinete import (
        listar_entradas,
    )

    return ordens_da_mesa.Leitura(
        censo=ler_o_barramento(), entradas=listar_entradas()
    )


def _itens_das_ordens(leitura: Callable[[], Leitura]) -> list[Item]:
    """Uma linha por ordem de serviço achada — e uma linha se não deu para ver."""
    from hefesto_dualsense4unix.integrations import ordens_da_mesa

    try:
        catalogo = ordens_da_mesa.catalogo(leitura())
    except Exception:
        return [
            Item(
                chave=CHAVE_DAS_ORDENS,
                rotulo=ROTULO_DAS_ORDENS,
                estado=ESTADO_NAO_SEI,
                porque=(
                    "Não deu para conferir os encaixes agora."
                ),
            )
        ]
    return [
        Item(
            chave=ordem.chave,
            rotulo=ROTULO_DA_ORDEM,
            estado=ESTADO_ATENCAO,
            porque=ordem.o_que_eu_vi.texto,
            cura=ordem.acao or None,
            ordem=ordem,
        )
        for ordem in catalogo
    ]


def exame(
    *,
    parametro_do_radio: Path | None = None,
    conf_do_radio: Path | None = None,
    raiz_usb: Path | None = None,
    modulos: Path | None = None,
    diretorio_do_modulo: Path | None = None,
    executar_busctl: Callable[[Sequence[str]], str | None] | None = None,
    leitura_da_vizinhanca: Callable[[], Sequence[object]] | None = None,
    altura_da_antena: str | None = None,
    linha_de_visada: str | None = None,
    leitura_das_ordens: Callable[[], Leitura] | None = None,
) -> list[Item]:
    """As cinco linhas, na ORDEM DA TELA.

    A ordem é a do desenho aprovado e não a ordem em que as checagens foram
    escritas: quem lê a tela lê de cima para baixo, e trocar a ordem aqui troca
    a tela.

    Todo caminho é ``None`` por default e cai no default da checagem — assim
    esta assinatura não repete cinco caminhos do sistema real, e o retrato das
    abas continua conseguindo injetar uma bancada falsa em UMA chamada.

    `altura_da_antena` e `linha_de_visada` só alimentam
    :func:`vizinhanca_das_portas` — ver o parágrafo sobre CONFIG-09 lá.

    `leitura_das_ordens` É O ÚNICO ARGUMENTO CUJO DEFAULT NÃO É O SISTEMA REAL,
    e a exceção é a proteção da foto. Os cinco caminhos acima apontam para
    arquivos fixos, e uma bancada os substitui um a um; o catálogo de ordens
    varre o barramento INTEIRO, e quem monta uma bancada para os cinco não tem
    como adivinhar que precisa de um sexto substituto. Pior: o
    `test_com_as_raizes_injetadas_nada_do_sistema_real_e_lido` vigia
    ``pathlib``, e as duas varreduras do catálogo usam ``os.listdir`` e
    ``open`` — o portão passaria verde sobre um exame lendo a máquina dela.
    Com o default desligado, quem quer ordens pede: `main()` pede e
    `app/actions/config/secao_exame.py` pede.

    O terceiro nome desta lista era `scripts/gui-captura/retratar_abas.py`,
    citado como quem NÃO pedia — o retratista da JANELA GTK, apagado com ela em
    06/09/2026 (`D-0609-GTK-LEVA-INTEIRA`). O retratista de hoje
    (`interface/olhar.py`) não pede porque não chega aqui: ele fotografa página
    HTML já gravada, sem executar este módulo.
    """
    argumentos_do_radio: dict[str, Path] = {}
    if parametro_do_radio is not None:
        argumentos_do_radio["parametro"] = parametro_do_radio
    if conf_do_radio is not None:
        argumentos_do_radio["conf"] = conf_do_radio
    argumentos_do_suporte: dict[str, Path] = {}
    if modulos is not None:
        argumentos_do_suporte["modulos"] = modulos  # (noqa-acento): nome de argumento
    if diretorio_do_modulo is not None:
        argumentos_do_suporte["diretorio_do_modulo"] = diretorio_do_modulo

    itens = [
        energia_do_radio(**argumentos_do_radio),
        energia_das_portas(**({"raiz": raiz_usb} if raiz_usb is not None else {})),
        pareamentos(executar=executar_busctl),
        suporte_ao_controle(**argumentos_do_suporte),
        vizinhanca_das_portas(
            leitura=leitura_da_vizinhanca,
            altura_da_antena=altura_da_antena,
            linha_de_visada=linha_de_visada,
        ),
    ]
    if leitura_das_ordens is not None:
        itens.extend(_itens_das_ordens(leitura_das_ordens))
    return itens


def veredito(itens: Sequence[Item]) -> str:
    """O selo do topo, derivado — e derivado em UM lugar só."""
    estados = {item.estado for item in itens}
    for grave in (ESTADO_PROBLEMA, ESTADO_ATENCAO, ESTADO_NAO_SEI):
        if grave in estados:
            return grave
    return ESTADO_CERTO if estados else ESTADO_NAO_SEI


def censo(itens: Sequence[Item] | None = None) -> dict[str, object]:
    """O exame inteiro em forma JSON — é o que o `doctor.sh` consome."""
    linhas = (
        list(exame(leitura_das_ordens=leitura_do_sistema))
        if itens is None
        else list(itens)
    )
    return {
        "itens": [item.como_dicionario() for item in linhas],
        "veredito": veredito(linhas),
    }


# porta é a única coisa que separa "o cabo daquele controle" de "aquele hub".
#    laço de reinícios, e não um DualSense. :attr:`Aparelho.papel` diz qual dos

TAG_DO_STORM = "[USB-71]"

RAIZ_USB = Path("/sys/bus/usb/devices")

CLASSE_DE_HUB = "09"

VID_DA_SONY = "054c"

VIDS_DE_CONTROLE = frozenset({"054c", "057e", "045e", "2dc8", "0f0d", "20d6", "28de"})

TRIPLA_DO_ADAPTADOR = ("e0", "01", "01")

#: A classe de interface HID. O DualSense no cabo tem as de áudio (`01`) e a
CLASSE_HID = "03"

DESFECHO_ENTRADA_LARGADA = "entrada_largada"
DESFECHO_SEM_HID = "sem_hid"

_ENTRADA_LARGADA = re.compile(r"unable to enumerate usb device", re.IGNORECASE)

_PROBE_DO_HID = re.compile(
    r"can.t add hid device|probe with driver usbhid failed", re.IGNORECASE
)

_MENSAGEM_DO_KERNEL = re.compile(r"^\s*(?P<driver>\S+)\s+(?P<alvo>\S+?):\s")

_PORTA_DE_HUB_RAIZ = re.compile(r"^usb(?P<bus>\d+)-port(?P<degrau>\d+)$")

_PORTA_DE_HUB = re.compile(r"^(?P<hub>\d+-\d+(?:\.\d+)*)-port(?P<degrau>\d+)$")

_INTERFACE_USB = re.compile(r"^(?P<no>\d+-\d+(?:\.\d+)*):\d+\.\d+$")

_NO_USB = re.compile(r"^\d+-\d+(?:\.\d+)*$")

_LUGAR_NA_LINHA = re.compile(r"\s·\slugar\s(?P<lugar>pci-\S+)\s*$")


def porta_do_evento(mensagem: str) -> str:
    """A porta USB de uma mensagem do kernel — ``""`` quando não dá para dizer."""
    achado = _MENSAGEM_DO_KERNEL.match(mensagem)
    if achado is None:
        return ""
    alvo = achado.group("alvo")
    de_raiz = _PORTA_DE_HUB_RAIZ.match(alvo)
    if de_raiz is not None:
        return f"{de_raiz.group('bus')}-{de_raiz.group('degrau')}"
    de_hub = _PORTA_DE_HUB.match(alvo)
    if de_hub is not None:
        return f"{de_hub.group('hub')}.{de_hub.group('degrau')}"
    interface = _INTERFACE_USB.match(alvo)
    if interface is not None:
        return interface.group("no")
    if _NO_USB.match(alvo) is not None:
        return alvo
    return ""


def cadeia_da_porta(porta: str) -> tuple[str, ...]:
    """Os nós do caminho até a porta, do mais raso ao mais fundo."""
    if _NO_USB.match(porta) is None:
        return ()
    bus, _, resto = porta.partition("-")
    degraus = resto.split(".")
    caminho: list[str] = [f"{bus}-{degraus[0]}"]
    for degrau in degraus[1:]:
        caminho.append(f"{caminho[-1]}.{degrau}")
    return tuple(caminho)


@dataclass(frozen=True)
class Aparelho:
    """Quem está numa porta USB AGORA — ou a confissão de que não está ninguém."""

    porta: str
    presente: bool = False
    vid: str = ""
    pid: str = ""
    nome: str = ""
    e_hub: bool = False
    e_adaptador: bool = False
    hid_sem_driver: bool = False
    nome_da_entrada: str = ""

    @property
    def onde(self) -> str:
        """«Entrada 3 (3-4.1.3)»: o nome da seção do rádio e o caminho do kernel."""
        if self.nome_da_entrada and self.nome_da_entrada != self.porta:
            if self.porta in self.nome_da_entrada.split():
                return self.nome_da_entrada
            return f"{self.nome_da_entrada} ({self.porta})"
        return self.porta

    @property
    def e_controle(self) -> bool:
        """Um aparelho de fabricante de controle, encaixado agora."""
        return self.presente and self.vid.lower() in VIDS_DE_CONTROLE

    @property
    def papel(self) -> str:
        """O que ele é para quem joga — o controle ou o adaptador. ``""`` no resto."""
        if self.e_controle:
            return "um controle, pelo USB"
        if self.presente and self.e_adaptador:
            return "um adaptador BT: quando ele cai, caem todos os controles dele"
        return ""

    @property
    def identidade(self) -> str:
        """Como o aparelho se chama numa frase — no tempo verbal do PRESENTE."""
        if not self.presente:
            return "nada encaixado — e o /sys não guarda quem já esteve aqui"
        nome = self.nome or "aparelho que não publica nome"
        if self.vid and self.pid:
            return f"{nome} ({self.vid}:{self.pid})"
        return nome

    def como_dicionario(self) -> dict[str, object]:
        return {
            "porta": self.porta,
            "presente": self.presente,
            "vid": self.vid,
            "pid": self.pid,
            "nome": self.nome,
            "e_hub": self.e_hub,
            "e_adaptador": self.e_adaptador,
            "hid_sem_driver": self.hid_sem_driver,
            "nome_da_entrada": self.nome_da_entrada,
            "onde": self.onde,
            "papel": self.papel,
            "identidade": self.identidade,
        }


def _interfaces_da_porta(porta: str, raiz_usb: Path) -> list[Path]:
    """As interfaces do nó (``3-4.4:1.0``, ``3-4.4:1.3``…), em ordem. Somente leitura."""
    try:
        return sorted(raiz_usb.glob(f"{porta}:*"))
    except OSError:
        return []


def _tripla(no: Path, prefixo: str) -> tuple[str, str, str]:
    """``(classe, subclasse, protocolo)`` de um nó ou interface, em minúsculas."""
    classe, subclasse, protocolo = (
        (_texto_de(no / f"{prefixo}{campo}") or "").lower()
        for campo in ("Class", "SubClass", "Protocol")
    )
    return classe, subclasse, protocolo


def _e_adaptador(no: Path, interfaces: Sequence[Path]) -> bool:
    """A tripla do adaptador BT no descritor do aparelho OU na interface 0."""
    if _tripla(no, "bDevice") == TRIPLA_DO_ADAPTADOR:
        return True
    zero = [i for i in interfaces if i.name.endswith(".0")]
    return bool(zero) and _tripla(zero[0], "bInterface") == TRIPLA_DO_ADAPTADOR


def _hid_sem_driver(interfaces: Sequence[Path]) -> bool:
    """Alguma interface HID sem driver, e que ninguém desligou de propósito?

    ``authorized`` em ``0`` é escolha de alguém (a regra 75 faz isso com o áudio
    do DualSense), e não é o -71: essa interface não entra na conta.
    """
    for interface in interfaces:
        if (_texto_de(interface / "bInterfaceClass") or "").lower() != CLASSE_HID:
            continue
        if (_texto_de(interface / "authorized") or "1") == "0":
            continue
        try:
            if not (interface / "driver").exists():
                return True
        except OSError:
            continue
    return False


def aparelho_da_porta(porta: str, *, raiz_usb: Path = RAIZ_USB) -> Aparelho:
    """Lê no ``/sys`` quem está encaixado nesta porta. Somente leitura."""
    no = raiz_usb / porta
    try:
        presente = no.is_dir()
    except OSError:
        presente = False
    if not presente:
        return Aparelho(porta=porta)
    vid = _texto_de(no / "idVendor") or ""
    interfaces = _interfaces_da_porta(porta, raiz_usb)
    return Aparelho(
        porta=porta,
        presente=True,
        vid=vid,
        pid=(_texto_de(no / "idProduct") or ""),
        nome=(_texto_de(no / "product") or ""),
        e_hub=(_texto_de(no / "bDeviceClass") or "") == CLASSE_DE_HUB,
        e_adaptador=_e_adaptador(no, interfaces),
        hid_sem_driver=(
            vid.lower() == VID_DA_SONY and _hid_sem_driver(interfaces)
        ),
    )


@dataclass(frozen=True)
class PortaDoStorm:
    """Uma entrada que deu -71 na janela: quantos, quando, o que há nela e o que parou."""

    porta: str
    quantos: int
    ultimo: str
    aparelho: Aparelho
    hubs: tuple[Aparelho, ...] = ()
    desfecho: str = ""

    @property
    def parada(self) -> str:
        """O que ficou parado NESTA entrada, lido AGORA — ``""`` quando nada ficou."""
        if self.aparelho.hid_sem_driver:
            return "o controle está nela sem o HID, e o jogo não o vê"
        if self.desfecho == DESFECHO_ENTRADA_LARGADA and not self.aparelho.presente:
            return "o kernel desistiu dela no -71, e ela segue vazia"
        return ""

    @property
    def porque(self) -> str:
        """A MEDIÇÃO em uma frase — o mesmo contrato do ``porque`` de `Item`."""
        quando = f"{self.ultimo[8:10]}/{self.ultimo[5:7]}" if self.ultimo else "?"
        eventos = "1 evento" if self.quantos == 1 else f"{self.quantos} eventos"
        if self.hubs:
            caminho = ", depois ".join(
                f"{hub.onde}: {hub.identidade}" for hub in self.hubs
            )
            quantos_hubs = "1 hub" if len(self.hubs) == 1 else f"{len(self.hubs)} hubs"
            onde = f"atrás de {quantos_hubs} — {caminho}"
        else:
            onde = "direto numa entrada do próprio computador, sem hub no caminho"
        papel = f" — {self.aparelho.papel}" if self.aparelho.papel else ""
        return (
            f"{self.aparelho.onde} — {eventos}, o último em {quando}; nela "
            f"AGORA: {self.aparelho.identidade}{papel}; {onde}"
        )

    def como_dicionario(self) -> dict[str, object]:
        return {
            "porta": self.porta,
            "entrada": self.aparelho.onde,
            "quantos": self.quantos,
            "ultimo": self.ultimo,  # (noqa-acento): chave de máquina, ASCII por contrato
            "desfecho": self.desfecho,
            "parada": self.parada,
            "aparelho": self.aparelho.como_dicionario(),
            "hubs": [hub.como_dicionario() for hub in self.hubs],
            "porque": self.porque,
        }


@dataclass(frozen=True)
class HubEmComum:
    """Um hub no caminho de DUAS OU MAIS entradas que deram -71 na janela."""

    hub: Aparelho
    portas: tuple[str, ...]
    entradas: tuple[str, ...] = ()

    @property
    def porque(self) -> str:
        abaixo = self.entradas or self.portas
        return (
            f"o hub em {self.hub.onde} está no caminho de "
            f"{len(self.portas)} entradas que deram -71 "
            f"({', '.join(abaixo)}) — é o fator comum que a topologia "
            f"aponta; nela AGORA: {self.hub.identidade}"
        )

    def como_dicionario(self) -> dict[str, object]:
        return {
            "hub": self.hub.como_dicionario(),
            "portas": list(self.portas),
            "entradas": list(self.entradas),
            "porque": self.porque,
        }


@dataclass(frozen=True)
class LaudoDoStorm:
    """O -71 da janela com endereço — o que o doctor passa a dizer."""

    dias: int = 7
    portas: tuple[PortaDoStorm, ...] = ()
    hubs_em_comum: tuple[HubEmComum, ...] = ()
    sem_endereco: int = 0
    porque_nao: str = ""

    @property
    def total(self) -> int:
        return sum(p.quantos for p in self.portas) + self.sem_endereco

    def como_dicionario(self) -> dict[str, object]:
        return {
            "dias": self.dias,
            "total": self.total,
            "sem_endereco": self.sem_endereco,
            "porque_nao": self.porque_nao,
            "portas": [p.como_dicionario() for p in self.portas],
            "hubs_em_comum": [h.como_dicionario() for h in self.hubs_em_comum],
        }


def _sem_nome(_porta: str) -> str | None:
    """O nomeador de quando o dono do nome não está ao alcance."""
    return None


def _nomeador(
    raiz_usb: Path, *, maquina: MaquinaConfig | None = None
) -> Callable[[str], str | None]:
    """Quem dá o nome a uma entrada — o DONO, `entrada_a_entrada.nome_da_porta`."""
    try:
        from hefesto_dualsense4unix.integrations.entrada_a_entrada import nome_da_porta
        from hefesto_dualsense4unix.integrations.mesa_de_radio import (
            controladores_dos_barramentos,
        )
        from hefesto_dualsense4unix.utils.maquina import (
            MaquinaConfig as _Maquina,
        )
        from hefesto_dualsense4unix.utils.maquina import carregar_maquina
    except Exception:
        return _sem_nome
    try:
        barramentos = controladores_dos_barramentos(raiz_usb=str(raiz_usb))
        if maquina is None:
            maquina = carregar_maquina() if raiz_usb == RAIZ_USB else _Maquina()
    except Exception:
        return _sem_nome

    def nomear(porta: str) -> str | None:
        try:
            return nome_da_porta(porta, maquina=maquina, controladores=barramentos)
        except Exception:
            return None

    return nomear


def _barramentos_da_raiz(raiz_usb: Path) -> dict[int, str]:
    """``{busnum: controlador PCI}`` da raiz lida — ``{}`` quando não se sabe."""
    try:
        from hefesto_dualsense4unix.integrations.mesa_de_radio import (
            controladores_dos_barramentos,
        )

        return dict(controladores_dos_barramentos(raiz_usb=str(raiz_usb)))
    except Exception:
        return {}


def _porta_de_hoje(
    porta: str, lugar: str, barramentos: dict[int, str], raiz_usb: Path
) -> str:
    """O caminho de HOJE da entrada em que o -71 aconteceu — STORM-USB-02.

    O caminho do kernel (``3-4.4``) carrega o número do barramento, e o número
    é a ORDEM em que os controladores xHCI subiram naquele boot. Nos 12 boots
    medidos na mesa dela a ordem não mudou; num computador em que mude, o
    caminho de um -71 de ontem nomeia OUTRA entrada hoje. O ``lugar`` que o
    kernel-watch grava na linha (o controlador PCI e a cadeia de portas) é o
    que diz qual é a certa, e esta função o traduz pelos barramentos da raiz.

    Vale o caminho do log quando a linha não tem lugar (o log de antes de
    24/09), quando não há barramentos lidos, quando a ordem não mudou (o caso
    comum: o mesmo resultado de antes) e quando o controlador daquele boot não
    está mais na máquina — aí não há entrada de hoje para apontar. Dos dois
    lados de uma entrada USB 3 (o 2.0 e o 3.x têm o mesmo lugar), fica o que
    tem aparelho agora; sem nenhum, o 2.0, onde o DualSense e os adaptadores
    enumeram.
    """
    if not lugar or not barramentos:
        return porta
    try:
        from hefesto_dualsense4unix.utils.lugar import (
            caminhos_do_lugar,
            lugar_do_caminho,
        )
    except Exception:
        return porta
    if lugar_do_caminho(porta, barramentos) == lugar:
        return porta
    candidatos = caminhos_do_lugar(lugar, barramentos)
    if not candidatos:
        return porta
    presentes = []
    for candidato in candidatos:
        try:
            if (raiz_usb / candidato).is_dir():
                presentes.append(candidato)
        except OSError:
            continue
    return (presentes or list(candidatos))[0]


def _desfecho(mensagem: str) -> str:
    """O kernel desistiu nesta linha? Um dos ``DESFECHO_*``, ou ``""``."""
    if _ENTRADA_LARGADA.search(mensagem):
        return DESFECHO_ENTRADA_LARGADA
    if _PROBE_DO_HID.search(mensagem):
        return DESFECHO_SEM_HID
    return ""


def storm_por_porta(
    *,
    linhas: Sequence[str] | None = None,
    log: Path | None = None,
    dias: int = 7,
    hoje: datetime.date | None = None,
    raiz_usb: Path = RAIZ_USB,
    nomear: Callable[[str], str | None] | None = None,
) -> LaudoDoStorm:
    """Cada -71 da janela com a ENTRADA e o CONTROLE — a entrega da STORM-USB-01."""
    if linhas is None:
        if log is None:
            return LaudoDoStorm(dias=dias, porque_nao="nenhum log do kernel-watch informado")
        try:
            linhas = log.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return LaudoDoStorm(
                dias=dias,
                porque_nao=f"não deu para ler {log}",
            )
    corte = ((hoje or datetime.date.today()) - datetime.timedelta(days=dias)).isoformat()

    quantos: dict[str, int] = {}
    ultimo: dict[str, str] = {}
    carimbo: dict[str, str] = {}
    desfecho: dict[str, str] = {}
    sem_endereco = 0
    barramentos: dict[int, str] | None = None
    for linha in linhas:
        if TAG_DO_STORM not in linha:
            continue
        data = linha[:10]
        if len(data) < 10 or data < corte:
            continue
        _, _, mensagem = linha.partition(TAG_DO_STORM)
        lugar = ""
        casou = _LUGAR_NA_LINHA.search(mensagem)
        if casou is not None:
            lugar = casou.group("lugar")
            mensagem = mensagem[: casou.start()]
        porta = porta_do_evento(mensagem.strip())
        if not porta:
            sem_endereco += 1
            continue
        if lugar:
            if barramentos is None:
                barramentos = _barramentos_da_raiz(raiz_usb)
            porta = _porta_de_hoje(porta, lugar, barramentos, raiz_usb)
        quantos[porta] = quantos.get(porta, 0) + 1
        if data > ultimo.get(porta, ""):
            ultimo[porta] = data
        instante = linha[:19]
        if instante >= carimbo.get(porta, ""):
            carimbo[porta] = instante
            desfecho[porta] = _desfecho(mensagem)

    if nomear is None:
        nomear = _nomeador(raiz_usb) if quantos else _sem_nome
    conhecidos: dict[str, Aparelho] = {}

    def _aparelho(porta: str) -> Aparelho:
        if porta not in conhecidos:
            conhecidos[porta] = replace(
                aparelho_da_porta(porta, raiz_usb=raiz_usb),
                nome_da_entrada=nomear(porta) or "",
            )
        return conhecidos[porta]

    portas: list[PortaDoStorm] = []
    for porta in quantos:
        caminho = cadeia_da_porta(porta)
        portas.append(
            PortaDoStorm(
                porta=porta,
                quantos=quantos[porta],
                ultimo=ultimo[porta],
                aparelho=_aparelho(porta),
                hubs=tuple(_aparelho(degrau) for degrau in caminho[:-1]),
                desfecho=desfecho.get(porta, ""),
            )
        )
    portas.sort(key=lambda p: (-p.quantos, p.porta))

    sob_o_hub: dict[str, list[str]] = {}
    for p in portas:
        for degrau in cadeia_da_porta(p.porta)[:-1]:
            sob_o_hub.setdefault(degrau, []).append(p.porta)
    hubs_em_comum = tuple(
        HubEmComum(
            hub=_aparelho(degrau),
            portas=tuple(sorted(abaixo)),
            entradas=tuple(_aparelho(porta).onde for porta in sorted(abaixo)),
        )
        for degrau, abaixo in sorted(sob_o_hub.items())
        if len(abaixo) >= 2
    )
    return LaudoDoStorm(
        dias=dias,
        portas=tuple(portas),
        hubs_em_comum=hubs_em_comum,
        sem_endereco=sem_endereco,
    )


def log_do_kernel_watch(lar: Path | None = None) -> Path | None:
    """O `kernel.log`, ou o `storm.log` antigo, ou ``None`` se não há nenhum."""
    raiz = (lar or Path.home()) / ".local/state/hefesto-dualsense4unix"
    for nome in ("kernel.log", "storm.log"):
        caminho = raiz / nome
        try:
            if caminho.is_file():
                return caminho
        except OSError:
            continue
    return None


_MARCA = {
    ESTADO_CERTO: "[ OK ]",
    ESTADO_ATENCAO: "[WARN]",
    ESTADO_PROBLEMA: "[FAIL]",
    ESTADO_NAO_SEI: "[INFO]",
}


ROTULOS_DA_ORDEM = ("O que eu vi aqui", "Por que importa", "Ganho esperado")


def _imprimir_relatorio(itens: Sequence[Item]) -> int:
    """Uma linha por conferência, mais o veredito. Devolve o código de saída."""
    for item in itens:
        print(f"{_MARCA.get(item.estado, '[INFO]')} {item.rotulo}: {item.porque}")
        if item.cura:
            print(f"        o que fazer: {item.cura}")
        if item.ordem is not None:
            for rotulo, linha in zip(
                ROTULOS_DA_ORDEM, item.ordem.linhas, strict=True
            ):
                fonte = f" ({linha.fonte})" if linha.fonte else ""
                print(f"        {rotulo}: {linha.texto} [{linha.selo}]{fonte}")
    final = veredito(itens)
    print(f"{_MARCA.get(final, '[INFO]')} exame da mesa: {final}")
    return 1 if final == ESTADO_PROBLEMA else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="exame_da_mesa",
        description=(
            "Confere, sem root e sem escrever nada, o que atrapalha um "
            "controle na mesa: energia do rádio, energia das portas, "
            "pareamento pela metade, suporte ao DualSense e a vizinhança das "
            "portas — e manda as mudanças que valem a pena, com de onde sai "
            "cada afirmação. Sem argumentos, --relatorio."
        ),
    )
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument(
        "--relatorio", action="store_true", help="relatório legível (default)"
    )
    grupo.add_argument("--censo", action="store_true", help="o exame em JSON")
    grupo.add_argument(
        "--storm-usb",
        action="store_true",
        help="o -71 dos últimos dias com a porta, o aparelho e o hub, em JSON",
    )
    parser.add_argument(
        "--log", help="o kernel.log a ler (default: o do kernel-watch desta conta)"
    )
    parser.add_argument(
        "--dias", type=int, default=7, help="a janela do --storm-usb, em dias (7)"
    )
    parser.add_argument(
        "--raiz-usb",
        default=str(RAIZ_USB),
        help=(
            "onde o /sys lista os nós USB. Trocá-lo permite endereçar o -71 "
            "contra um retrato de /sys de OUTRA máquina — é por aqui que a "
            "régua injeta uma bancada e o suporte lê a topologia de quem pediu "
            "ajuda, sem ter a máquina na mão"
        ),
    )
    args = parser.parse_args(argv)

    if args.storm_usb:
        caminho = Path(args.log) if args.log else log_do_kernel_watch()
        laudo = storm_por_porta(
            log=caminho, dias=args.dias, raiz_usb=Path(args.raiz_usb)
        )
        print(json.dumps(laudo.como_dicionario(), ensure_ascii=False))
        return 0
    if args.censo:
        print(json.dumps(censo(), ensure_ascii=False))
        return 0
    return _imprimir_relatorio(exame(leitura_das_ordens=leitura_do_sistema))


if __name__ == "__main__":  # pragma: no cover - entrypoint do doctor
    sys.exit(main())
