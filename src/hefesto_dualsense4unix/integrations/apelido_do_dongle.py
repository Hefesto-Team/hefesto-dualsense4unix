"""apelido_do_dongle.py — dar nome a cada dongle sem derrubar o Pro Controller.

O PROBLEMA QUE ESTE MÓDULO RESOLVE
-----------------------------------

Ela tem TRÊS adaptadores Bluetooth ``2357:0604``, todos atrás do mesmo hub.
Idênticos no barramento e no ``lsusb``. A única coisa que os separa é o BD
Address, e endereço não é nome: ninguém olha para ``AC:A7:F1:...`` e sabe qual
é o do sofá.

E **o modelo deles não é uma pergunta que o barramento responda** — MEDIDO em
22/08/2026, e é por isso que a frase acima não diz "UB500"::

    3-3.1.1   2357:0604  bcdDevice=0200  product="TP-Link UB500 Adapter"
    3-3.1.4   2357:0604  bcdDevice=0200  product="TP-Link Bluetooth USB Adapter"
    3-3.2     2357:0604  bcdDevice=0200  product="TP-Link UB500 Adapter"

O ``vid:pid`` NÃO distingue: UB500, UB5A e UB500 Plus são os três
``2357:0604``, com o mesmo chip RTL8761BUV, e aqui nem o ``bcdDevice`` os
separa. O único campo que varia é o ``product``, e ele é frágil: três unidades
da mesma bancada devolvem DUAS strings diferentes, e há na natureza uma
terceira com erro de digitação de fábrica (``TP-Lifk UB5A Adapter``).

**Consequência que precisa estar escrita:** nenhuma regra de udev, linha do
mapa de canais ou caminho de decisão deste produto pode depender de distinguir
modelo de dongle TP-Link. Não dá. O que identifica um adaptador aqui é o BD
Address; o que ela lê na tela é o apelido que ela mesma escreveu. É a mesma
recusa do ``censo_do_barramento`` a heurística por ``product`` — adivinhar por
texto é como se erra com confiança.

O BlueZ já guarda um nome por adaptador — ``org.bluez.Adapter1.Alias`` — e o
grava em ``/var/lib/bluetooth/<endereço>/settings``, então ele sobrevive a
reboot. Faltava o produto deixá-la escrever ali.

A ARMADILHA, E ELA É O CORAÇÃO DESTE MÓDULO
--------------------------------------------

O prefixo ``Nintendo`` nesse nome **não é enfeite**. O Pro Controller LÊ o nome
Bluetooth do host e, se ele não começar com ``Nintendo``, cai num modo de sniff
frágil que não manda keepalive — sob rumble e IMU os relatórios enfileiram e o
controle DESCONECTA. É a metade (1) do ``BT-NINTENDO-ACTIVE-01``, pesquisa de
22/07/2026, com três fontes independentes, e é o que
``scripts/bt_active_mode.sh:137-149`` aplica.

Renomear um adaptador que hospeda um Pro sem manter o prefixo derruba o Pro. Por
isso a decisão dela (22/08/2026) é: *"você escreve, o produto protege o
prefixo"*. O nome que a TELA mostra é o dela, limpo; o que vai ao BlueZ é o
costurado. Ela nunca precisa saber que a costura existe.

POR QUE PREFIXO, E NÃO SUFIXO — três razões, nenhuma delas de gosto
--------------------------------------------------------------------

1. **O firmware do Pro casa o COMEÇO do nome.** A verificação é ``Nintendo*``,
   literalmente o glob de ``bt_active_mode.sh:141``. Sufixo não satisfaz.
2. **O BlueZ corta pela CAUDA.** Medido nesta bancada em 22/08/2026, BlueZ 5.86:
   um alias de 300 caracteres ASCII volta com 247 — ele trunca, e o que
   desaparece é o fim. Um sufixo protetor sumiria calado justamente nos nomes
   longos; um prefixo sobrevive ao corte.
3. **Já existe outro escritor.** O ``bt_active_mode.sh`` escreve
   ``"Nintendo ${alias}"``. Qualquer outra forma faria os dois brigarem: o
   script re-prefixaria o que este módulo tivesse sufixado, e o nome cresceria
   a cada boot.

O TETO DO ALIAS, MEDIDO — e por que o produto trunca antes do BlueZ
--------------------------------------------------------------------

Nesta bancada, em 22/08/2026, BlueZ 5.86, como uid 1000::

    300 x "N"  (300 bytes)  -> aceito, volta com 247 caracteres
    123 x "á"  (246 bytes)  -> aceito inteiro
    124 x "á"  (248 bytes)  -> RECUSADO: "Invalid arguments in method call"

Uma regra só explica os três: **o teto é de 247 BYTES, o BlueZ trunca sozinho
e, quando o corte cai no meio de um caractere multibyte, a chamada inteira é
recusada.** Nome dela tem acento — "Sofá", "Salão" —, então deixar o BlueZ
truncar é deixar o salvamento falhar sem motivo visível. :func:`costurar_o_nome`
corta antes, sempre em fronteira de caractere, e sempre pela cauda: o prefixo
nunca é o sacrificado.

A ESCRITA NÃO PRECISA DE PRIVILÉGIO — medido, não suposto
----------------------------------------------------------

22/08/2026, nesta máquina: ``busctl set-property`` do ``Alias`` devolve ``0``
como uid 1000 **e também como ``nobody``**, um usuário sem sessão e sem assento.
A política do BlueZ em ``/usr/share/dbus-1/system.d/bluetooth.conf`` tem
``<policy context="default"><allow send_destination="org.bluez"/>``, e o
``Alias`` não passa por polkit. **Não há helper privilegiado a pedir aqui.**

O ponto de injeção ``executar`` existe assim mesmo, por duas razões que não são
privilégio: a suíte precisa de um D-Bus dublado, e dentro do Flatpak o barramento
de sistema **não está montado** (``flatpak/br.andrefarias.Hefesto.yml`` não tem
``--socket=system-bus`` nem ``--system-talk-name=org.bluez``) — lá a leitura e a
escrita simplesmente não chegam ao BlueZ, e quem resolver isso pluga aqui.

**A escrita é ASSÍNCRONA.** Medido: ler a propriedade imediatamente depois de
escrever devolve o valor ANTIGO; um segundo depois, o novo. Quem quiser conferir
o que gravou tem de esperar — este módulo não confere, ele reporta o que o
``set-property`` respondeu.

O QUE ELE NÃO É
----------------

Não desenha tela: quem monta a seção da aba é outra camada, e este módulo é
puro o bastante para rodar sem GTK.

Não mexe em link policy. A metade (2) do ``BT-NINTENDO-ACTIVE-01`` — o no-sniff
por dispositivo — é do ``bt_active_mode.sh``, precisa de root e de ``hcitool``,
e é POR CONTROLE, não por adaptador. Aqui só a metade (1), a do nome, que é a
que sai sem privilégio nenhum.

Não usa ``hciN`` como identidade em lugar nenhum. O índice inverte entre boots
(``GUIA-RADIO-DA-SALA.md`` §6.1, e a cicatriz do ``bt_health_watchdog.sh``), e
por isso o caminho ``/org/bluez/hciN`` é resolvido a cada leitura a partir do
BD Address, nunca guardado.

Nunca SUBTRAI. Se um adaptador carrega o prefixo e não hospeda Nintendo nenhum,
o prefixo fica: tirar uma palavra que ela escreveu é pior que deixar uma palavra
que não faz nada. Ver :func:`limpar_o_nome`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from hefesto_dualsense4unix.core.linhagem_nintendo import (
    NOMES_LINHAGEM,
    OUIS_LINHAGEM_COM_DOIS_PONTOS,
    _e_da_linhagem_nintendo,
)

#: O prefixo que tira o Pro Controller do sniff frágil. Caixa canônica, igual à
#: de ``scripts/bt_active_mode.sh:142`` — os dois escritores têm de produzir a
#: MESMA string, ou cada um desfaz o outro.
PREFIXO_NINTENDO = "Nintendo"

#: Teto do alias em BYTES UTF-8. MEDIDO em 22/08/2026, BlueZ 5.86 — ver o
#: cabeçalho. Não é o 248 do ``MGMT_MAX_NAME_LENGTH``: o que esta bancada
#: devolveu foi 247, e o número que vale é o medido.
TETO_DE_BYTES = 247

#: Teto de espera de cada `busctl`, em segundos. Mesmo número de
#: ``integrations/exame_da_mesa.py:72`` — um `busctl` pendurado seguraria o
#: worker e a janela pareceria travada.
ESPERA_DO_BUSCTL_S = 5.0

#: OUIs da linhagem Nintendo, minúsculas com ``:`` — a faixa do Pro desta
#: bancada e a do 8BitDo em modo Switch, que mente VID/PID como ``057E:2009``
#: mas nunca mente a OUI.
#:
#: O 8BitDo entra na lista de propósito, e o A/B de 23/07/2026 é quem autoriza:
#: *"o alias 'Nintendo' seguiu aplicado — ou seja, o NOME não atrapalha o
#: clone"* (``bt_active_mode.sh:170-174``). O que atrapalha o clone é o
#: no-sniff, que não é deste módulo.
#:
#: **UMA-FAIXA-NÃO-É-UM-FABRICANTE-01 (22/08/2026):** as faixas deixaram de ser
#: literais aqui e vêm de ``core/linhagem_nintendo``, que é a casa única delas
#: no ``src/``. A frase que este comentário trazia antes — *"mesma fonte da
#: verdade de ``NINTENDO_REAL_OUI``"* — descrevia quatro cópias que se citavam
#: mutuamente, que é a assinatura de uma fonte da verdade que não existe.
#: Agora existe.
OUIS_NINTENDO = OUIS_LINHAGEM_COM_DOIS_PONTOS

#: Pedaços de ``HID_NAME`` que denunciam a linhagem, em minúsculas. Existem
#: além das OUIs porque OUI é lista fechada e nome é o que o kernel deduziu do
#: driver: um aparelho novo do mesmo firmware entra por aqui sem ninguém
#: precisar descobrir a OUI dele primeiro.
#:
#: ``"pro controller"`` é o nome que o ``hid-nintendo`` dá ao Pro e ao clone.
#: NÃO casa ``"DualSense Wireless Controller"``, e não casa ``"8BitDo Pro 2"``
#: em modo X-input — que é um gamepad comum e não tem nada a ver com o sniff.
NOMES_NINTENDO = NOMES_LINHAGEM

#: MAC bem-formado, minúsculo. Mesma forma de
#: ``integrations/radio_da_mesa.py:152``. É o que separa um ``HID_PHYS`` de
#: rádio (``ac:a7:f1:...``) de um de cabo
#: (``usb-0000:0c:00.3-1/input3``) — sem esta guarda, o caminho USB vira um
#: endereço de adaptador inventado.
_MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")

#: O caminho de UM adaptador na árvore do BlueZ, e nada mais fundo. A âncora de
#: fim é o que deixa de fora ``/org/bluez/hci0/dev_XX``, que é dispositivo.
_CAMINHO_DE_ADAPTADOR = re.compile(r"/org/bluez/hci[0-9]+")

_MARCA_NOME = "HID_NAME="
_MARCA_PHYS = "HID_PHYS="
_MARCA_UNIQ = "HID_UNIQ="

_INTERFACE_ADAPTADOR = "org.bluez.Adapter1"


@dataclass(frozen=True)
class Dongle:
    """Um adaptador Bluetooth pela ótica de quem quer dar nome a ele.

    ``endereco`` é o BD Address em MAIÚSCULAS com ``:`` — a identidade, a mesma
    forma que o ``bluetoothctl list`` imprime e que o ``GUIA-RADIO-DA-SALA.md``
    §6.2 manda anotar no papel colado no rack.

    ``objeto`` é o ``/org/bluez/hciN`` de AGORA. Ele existe para que a escrita
    da mesma leitura não precise varrer a árvore de novo, e é a única coisa
    aqui que caduca: o índice inverte entre boots. Nunca guarde em disco.

    ``alias`` é o que está no BlueZ, costurado. ``nome`` é o dela, limpo — é o
    que a tela mostra.
    """

    endereco: str
    alias: str = ""
    nome_do_sistema: str = ""
    hospeda_nintendo: bool = False
    ligado: bool = False
    objeto: str = ""

    @property
    def nome(self) -> str:
        """O nome DELA — o alias sem a costura do produto."""
        return limpar_o_nome(self.alias, hospeda_nintendo=self.hospeda_nintendo)

    @property
    def protegido(self) -> bool:
        """O alias de hoje já tira o Pro do sniff frágil?

        ``True`` também quando não há Nintendo nenhum ali: não há o que
        proteger, e a resposta honesta para "este adaptador está em risco?" é
        "não". Quem quer saber se a costura FOI aplicada olha
        :attr:`Renomeacao.costurado`.
        """
        return not self.hospeda_nintendo or self.alias.startswith(PREFIXO_NINTENDO)


@dataclass(frozen=True)
class Renomeacao:
    """O que aconteceu (ou aconteceria) ao renomear um dongle.

    Existe para que a tela possa mostrar o resultado sem reler o BlueZ — e para
    que ela POSSA mostrar: a escrita é assíncrona, e reler logo depois devolve o
    valor antigo (medido, ver o cabeçalho).
    """

    endereco: str
    nome: str = ""
    alias: str = ""
    costurado: bool = False
    truncado: bool = False
    aplicado: bool = False
    porque: str = ""


# ---------------------------------------------------------------------------
# A costura — funções puras, sem D-Bus, sem sysfs, sem subprocesso.
# ---------------------------------------------------------------------------


def costurar_o_nome(nome: str, *, hospeda_nintendo: bool) -> str:
    """O nome dela vira o alias que vai ao BlueZ.

    Três regras, nesta ordem:

    1. **sem Nintendo no adaptador, o nome vai como ela escreveu.** O produto
       não acrescenta palavra que não protege nada;
    2. **com Nintendo, o alias começa com** :data:`PREFIXO_NINTENDO`. Se o nome
       dela já começa assim, nada é acrescentado — a costura é idempotente, e
       tem de ser: ``bt_active_mode.sh`` roda a cada tique da vigia e o nome
       cresceria a cada passagem;
    3. **o resultado cabe em** :data:`TETO_DE_BYTES` **bytes**, cortado em
       fronteira de caractere e sempre pela cauda.

    O caso do nome VAZIO é o que menos parece e mais morde. No BlueZ, alias
    ``""`` significa *"esqueça o apelido e volte ao nome do sistema"* — medido
    em 22/08/2026: escrever ``""`` devolveu o adaptador ao ``Name``. Num
    adaptador com Pro isso apagaria a proteção junto. Por isso, com Nintendo
    presente e nome vazio, o alias é o prefixo sozinho: protege, e ainda é um
    nome legível.
    """
    bruto = _alias_sem_tesoura(nome, hospeda_nintendo=hospeda_nintendo)
    intocavel = len(PREFIXO_NINTENDO) if hospeda_nintendo else 0
    return _caber(bruto, intocavel=intocavel)


def _alias_sem_tesoura(nome: str, *, hospeda_nintendo: bool) -> str:
    """A costura ANTES do teto — separada para que se possa dizer se cortou.

    Sem esta separação, "o produto acrescentou o prefixo" e "o produto cortou o
    fim" viram a mesma comparação contra o nome dela, e as duas saem erradas
    quando acontecem juntas.
    """
    limpo = nome.strip()
    if not hospeda_nintendo:
        return limpo
    if limpo.startswith(PREFIXO_NINTENDO):
        return limpo
    if not limpo:
        return PREFIXO_NINTENDO
    return f"{PREFIXO_NINTENDO} {limpo}"


def limpar_o_nome(alias: str, *, hospeda_nintendo: bool) -> str:
    """O alias do BlueZ vira o nome dela — o que a tela mostra.

    **A limpeza é condicional, e a condição é o que impede o produto de comer
    uma palavra dela.** Só se tira o prefixo de um adaptador que hospeda
    Nintendo, porque só ali o produto poderia tê-lo posto.

    O defeito que isso evita, se a limpeza fosse incondicional: ela batiza um
    dongle SEM Nintendo de ``"Nintendo do sofá"``. A tela mostraria
    ``"do sofá"``; ela salva de novo; sem Nintendo o produto não recosturaria
    nada, e o alias viraria ``"do sofá"``. A palavra dela desapareceria no
    segundo salvamento, sem ninguém ter pedido.

    Com a condição, os dois sentidos fecham em ida e volta:

    * **com Nintendo:** ``"Nintendo do sofá"`` -> ``"do sofá"`` -> costura ->
      ``"Nintendo do sofá"``;
    * **sem Nintendo:** ``"Nintendo do sofá"`` -> ``"Nintendo do sofá"`` ->
      costura -> ``"Nintendo do sofá"``.

    A comparação é sem caixa porque o objetivo aqui é ESCONDER a costura, e um
    ``"nintendo casa"`` vindo de um BlueZ antigo é costura tanto quanto o
    canônico. Já a ESCRITA usa sempre a caixa de :data:`PREFIXO_NINTENDO` —
    ``costurar_o_nome`` não confia na caixa para proteger o Pro.

    Consequência conhecida e aceita: mover o Pro para outro dongle muda o nome
    que a tela mostra para os dois, porque muda quem hospeda Nintendo. O alias
    no BlueZ não muda em nenhum dos dois — o que ela vê fica diferente, o que
    protege o controle fica igual.
    """
    texto = alias.strip()
    if not hospeda_nintendo:
        return texto
    if texto.lower() == PREFIXO_NINTENDO.lower():
        return ""
    if not texto.lower().startswith(PREFIXO_NINTENDO.lower()):
        return texto
    resto = texto[len(PREFIXO_NINTENDO) :]
    if not resto[:1].isspace():
        # `NintendoCasa` não é costura deste produto — o script e este módulo
        # sempre põem um espaço. Devolver `Casa` aqui inventaria uma separação
        # que ninguém escreveu.
        return texto
    return resto.strip()


def _caber(texto: str, *, intocavel: int = 0) -> str:
    """Corta ``texto`` para :data:`TETO_DE_BYTES` bytes, sem partir caractere.

    ``intocavel`` é quantos caracteres do começo não podem sumir de jeito
    nenhum — o prefixo. Se nem ele couber (o que exigiria um teto absurdo de
    pequeno), volta o prefixo cortado: um nome truncado é ruim, um nome que o
    BlueZ recusa é pior.
    """
    bruto = texto.encode("utf-8")
    if len(bruto) <= TETO_DE_BYTES:
        return texto
    cortado = bruto[:TETO_DE_BYTES].decode("utf-8", errors="ignore").rstrip()
    return cortado if cortado else texto[:intocavel]


# ---------------------------------------------------------------------------
# Quem hospeda Nintendo — pelo sysfs, sem root e sem subprocesso.
# ---------------------------------------------------------------------------


def adaptadores_com_nintendo(
    *,
    raiz: str = "/sys/class/hidraw",
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
) -> frozenset[str]:
    """Endereços (minúsculos, com ``:``) dos adaptadores que hospedam Nintendo.

    A fonte é o ``uevent`` de cada nó ``/sys/class/hidraw/*/device/``, que o
    kernel publica e que abre como uid 1000 — medido nesta bancada em
    22/08/2026, sem sudo. ``HID_PHYS`` traz o MAC do ADAPTADOR, ``HID_UNIQ`` o
    do controle e ``HID_NAME`` o nome que o driver deu. É a mesma leitura de
    ``integrations/radio_da_mesa.py:adaptador_por_uniq``, com a pergunta
    invertida: lá se procura o adaptador de um controle, aqui se procura a
    linhagem dos controles de cada adaptador.

    **A regra é permissiva de propósito, e o motivo é custo assimétrico.**
    Prefixo sobrando num adaptador que não precisa: nada acontece — o A/B de
    23/07/2026 mediu o clone 8BitDo funcionando com o alias aplicado. Prefixo
    faltando num que precisa: o Pro cai sob carga. Diante da dúvida, a resposta
    que custa menos é ``True``.

    Controle no CABO não entra: ``HID_PHYS`` dele é caminho de barramento
    (``usb-0000:0c:00.3-1/input3``), não MAC, e ele não está no rádio de
    adaptador nenhum. O nosso vpad também não, pela mesma porta: ele anuncia
    ``hefesto-vpad``.

    Conjunto VAZIO é resposta legítima e é a mais comum: mesa sem Nintendo
    nenhum, ou máquina sem controle no rádio.
    """
    leitor = _ler_texto if ler is None else ler
    try:
        nos = sorted(listar(raiz))
    except OSError:
        # Sysfs ilegível é "não sei". Devolver vazio aqui faz o produto NÃO
        # costurar, e é a falha para o lado errado — mas inventar adaptador é
        # pior, e quem chama vê a mesa vazia e não escreve nada em ninguém.
        return frozenset()

    achados: set[str] = set()
    for no in nos:
        texto = leitor(os.path.join(raiz, no, "device", "uevent"))
        if not texto:
            continue
        phys = _valor_do_uevent(texto, _MARCA_PHYS).lower()
        if not _MAC_RE.match(phys):
            continue
        if not _e_da_linhagem_nintendo(
            nome=_valor_do_uevent(texto, _MARCA_NOME),
            uniq=_valor_do_uevent(texto, _MARCA_UNIQ),
        ):
            continue
        achados.add(phys)
    return frozenset(achados)


# ---------------------------------------------------------------------------
# Ler e escrever o alias — por BD Address, nunca por hciN.
# ---------------------------------------------------------------------------


def ler_os_dongles(
    *,
    executar: Callable[[Sequence[str]], str | None] | None = None,
    raiz_hidraw: str = "/sys/class/hidraw",
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
) -> tuple[Dongle, ...]:
    """Todos os adaptadores, com nome, endereço e quem eles hospedam.

    Ordenados por endereço, que é a única ordem estável que existe aqui: a da
    árvore do BlueZ segue o ``hciN``, e o ``hciN`` inverte entre boots — uma
    tabela que troca de ordem sozinha depois de reiniciar é uma tabela em que
    ninguém confia.

    Tupla VAZIA é resposta legítima: sem ``busctl``, com o ``bluetoothd``
    parado, dentro do Flatpak (que não monta o barramento de sistema) ou numa
    máquina sem adaptador nenhum. Quem chama diz isso na tela — nunca uma
    tabela em branco.
    """
    rodar = _busctl if executar is None else executar
    arvore = rodar(["tree", "org.bluez", "--list"])
    if arvore is None:
        return ()
    com_nintendo = adaptadores_com_nintendo(
        raiz=raiz_hidraw, listar=listar, ler=ler
    )
    achados: list[Dongle] = []
    for linha in arvore.splitlines():
        caminho = linha.strip()
        if not _CAMINHO_DE_ADAPTADOR.fullmatch(caminho):
            continue
        endereco = _propriedade(rodar, caminho, "Address")
        if not endereco:
            # Adaptador sem endereço legível não tem identidade, e sem
            # identidade não há o que renomear: `hciN` não serve, e é
            # exatamente a troca que este módulo existe para não fazer.
            continue
        achados.append(
            Dongle(
                endereco=endereco.upper(),
                alias=_propriedade(rodar, caminho, "Alias") or "",
                nome_do_sistema=_propriedade(rodar, caminho, "Name") or "",
                hospeda_nintendo=endereco.lower() in com_nintendo,
                ligado=_propriedade(rodar, caminho, "Powered") == "true",
                objeto=caminho,
            )
        )
    return tuple(sorted(achados, key=lambda d: d.endereco))


def renomear_o_dongle(
    endereco: str,
    nome: str,
    *,
    dongles: Iterable[Dongle] | None = None,
    executar: Callable[[Sequence[str]], str | None] | None = None,
    raiz_hidraw: str = "/sys/class/hidraw",
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
) -> Renomeacao:
    """Grava o nome dela num dongle, com a costura do prefixo por cima.

    ``endereco`` é o BD Address, em qualquer caixa. O ``/org/bluez/hciN`` é
    resolvido AGORA, a partir dele — nunca recebido de fora e nunca guardado.

    ``dongles`` é a leitura que a tela já tem em mãos; sem ela, uma leitura
    nova. Passar a de mão poupa uma varredura, mas tem um preço declarado: se o
    Pro mudou de adaptador desde aquela leitura, a costura sai pela informação
    velha. Em tela isso é uma janela de segundos; para o passe de reparo, use
    :func:`costurar_a_mesa`, que sempre relê.

    Não confere o que gravou, e é de propósito: a escrita é assíncrona (medido
    — ler logo depois devolve o valor antigo), e uma conferência com espera
    dentro travaria a interface por um segundo a cada salvamento.
    """
    rodar = _busctl if executar is None else executar
    tabela = (
        tuple(dongles)
        if dongles is not None
        else ler_os_dongles(
            executar=rodar, raiz_hidraw=raiz_hidraw, listar=listar, ler=ler
        )
    )
    alvo = next(
        (d for d in tabela if d.endereco.lower() == endereco.strip().lower()),
        None,
    )
    if alvo is None:
        return Renomeacao(
            endereco=endereco.upper(),
            nome=nome,
            porque="Este adaptador não está mais na mesa.",
        )

    bruto = _alias_sem_tesoura(nome, hospeda_nintendo=alvo.hospeda_nintendo)
    alias = costurar_o_nome(nome, hospeda_nintendo=alvo.hospeda_nintendo)
    costurado = bruto != nome.strip()
    truncado = alias != bruto
    if not alvo.objeto:
        return Renomeacao(
            endereco=alvo.endereco,
            nome=nome,
            alias=alias,
            costurado=costurado,
            truncado=truncado,
            porque="Não achei este adaptador no Bluetooth do sistema.",
        )
    resposta = rodar(
        [
            "set-property",
            "org.bluez",
            alvo.objeto,
            _INTERFACE_ADAPTADOR,
            "Alias",
            "s",
            alias,
        ]
    )
    if resposta is None:
        return Renomeacao(
            endereco=alvo.endereco,
            nome=nome,
            alias=alias,
            costurado=costurado,
            truncado=truncado,
            porque="O Bluetooth do sistema recusou o nome novo.",
        )
    return Renomeacao(
        endereco=alvo.endereco,
        nome=nome,
        alias=alias,
        costurado=costurado,
        truncado=truncado,
        aplicado=True,
    )


def costurar_a_mesa(
    *,
    executar: Callable[[Sequence[str]], str | None] | None = None,
    raiz_hidraw: str = "/sys/class/hidraw",
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
) -> tuple[Renomeacao, ...]:
    """O passe de reparo: põe o prefixo em TODO adaptador que hospeda Nintendo.

    Devolve só o que MUDOU. Mesa já protegida devolve tupla vazia, e é o que se
    espera na esmagadora maioria das chamadas.

    Por que este passe precisa existir, medido nesta bancada em 22/08/2026 com
    três adaptadores e um Pro Controller no rádio:

    * ``bt_active_mode.sh`` costura **um** adaptador, o primeiro que o
      ``/sys/class/bluetooth`` lista (``_adaptador()``, linha 75). Com um
      dongle só isso sempre acertou;
    * nesta mesa o Pro está no SEGUNDO, e o prefixo estava no primeiro. O
      script protegeu um adaptador que não hospeda Nintendo nenhum e deixou o
      Pro sem proteção;
    * ninguém percebeu porque o sintoma do Pro sem prefixo é queda **sob
      carga** — rumble e IMU juntos —, que parece defeito do controle.

    Este passe é por adaptador e por linhagem, não pela ordem de enumeração, e
    por isso a mesa de três acerta pelo mesmo caminho que a de um.

    O passe **nunca subtrai**: adaptador que carrega o prefixo e não hospeda
    Nintendo fica como está. Ver :func:`limpar_o_nome`.
    """
    rodar = _busctl if executar is None else executar
    tabela = ler_os_dongles(
        executar=rodar, raiz_hidraw=raiz_hidraw, listar=listar, ler=ler
    )
    feitos: list[Renomeacao] = []
    for dongle in tabela:
        if dongle.protegido:
            continue
        feitos.append(
            renomear_o_dongle(
                dongle.endereco,
                dongle.nome,
                dongles=tabela,
                executar=rodar,
            )
        )
    return tuple(feitos)


# ---------------------------------------------------------------------------
# Encanamento.
# ---------------------------------------------------------------------------


def _propriedade(
    executar: Callable[[Sequence[str]], str | None], caminho: str, nome: str
) -> str:
    """Uma propriedade de ``org.bluez.Adapter1``, já desembrulhada."""
    bruto = executar(
        ["get-property", "org.bluez", caminho, _INTERFACE_ADAPTADOR, nome]
    )
    return "" if bruto is None else _desembrulhar(bruto)


def _desembrulhar(bruto: str) -> str:
    """O valor de uma resposta do ``busctl``, com JSON na frente e texto atrás.

    **Por que JSON, e por que não o desembrulho de
    ``exame_da_mesa.py:_propriedade_do_dispositivo``:** aquele faz
    ``texto.split()[-1]``, que serve para ``b true`` e ``s "yes"`` e MUTILA
    qualquer nome com espaço — ``s "Nintendo MeowSystem"`` voltaria como
    ``MeowSystem``. Nomes com espaço e acento são o assunto deste módulo
    inteiro, então aqui o desembrulho tem de ser o certo.

    O texto continua atendido como plano B, para o caso de um ``busctl`` que
    não conheça ``--json`` (anterior ao systemd 239, de 2018) ou de um dublê de
    teste que responda no formato humano.
    """
    texto = bruto.strip()
    if not texto:
        return ""
    try:
        dado = json.loads(texto)
    except ValueError:
        pass
    else:
        if isinstance(dado, dict) and "data" in dado:
            valor = dado["data"]
            return valor if isinstance(valor, str) else str(valor).lower()
        return str(dado)
    tipo, _, resto = texto.partition(" ")
    if tipo == "s" and resto.startswith('"') and resto.endswith('"'):
        return resto[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return resto.strip('"') if resto else texto


def _busctl(argumentos: Sequence[str]) -> str | None:
    """Roda um ``busctl`` e devolve a saída, ou ``None`` se não deu.

    Ausência da ferramenta, erro e teto de tempo colapsam em ``None``: para
    quem chama os três significam "não deu para falar com o BlueZ". Molde de
    ``integrations/exame_da_mesa.py:289``, com uma diferença: as leituras
    pedem ``--json=short``, porque o valor que interessa aqui é um nome com
    espaço e acento (ver :func:`_desembrulhar`).

    Saída vazia com código ``0`` é SUCESSO, não falha — é o que o
    ``set-property`` devolve. Por isso o contrato é ``None`` contra ``str``, e
    nunca "string vazia é erro".
    """
    if shutil.which("busctl") is None:
        return None
    modo = ["--json=short"] if argumentos and argumentos[0] == "get-property" else []
    try:
        saida = subprocess.run(
            ["busctl", *modo, *argumentos],
            capture_output=True,
            text=True,
            timeout=ESPERA_DO_BUSCTL_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return saida.stdout if saida.returncode == 0 else None


def _valor_do_uevent(texto: str, marca: str) -> str:
    """O valor de uma chave do uevent — "" quando o nó não a declara."""
    for linha in texto.splitlines():
        if linha.startswith(marca):
            return linha[len(marca) :].strip()
    return ""


def _ler_texto(caminho: str) -> str:
    """Lê um arquivo de ``/sys``; "" em qualquer erro — sysfs some sob a mão."""
    try:
        with open(caminho, encoding="utf-8", errors="replace") as arquivo:
            return arquivo.read()
    except OSError:
        return ""


__all__ = [
    "ESPERA_DO_BUSCTL_S",
    "NOMES_NINTENDO",
    "OUIS_NINTENDO",
    "PREFIXO_NINTENDO",
    "TETO_DE_BYTES",
    "Dongle",
    "Renomeacao",
    "adaptadores_com_nintendo",
    "costurar_a_mesa",
    "costurar_o_nome",
    "ler_os_dongles",
    "limpar_o_nome",
    "renomear_o_dongle",
]
