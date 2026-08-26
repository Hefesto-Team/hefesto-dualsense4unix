"""censo_do_gabinete.py — o que o firmware e o kernel sabem do GABINETE dela.

O install roda como root **uma vez**; a janela nunca pede senha. Este módulo é o
que aproveita essa única passagem: ele lê a tabela SMBIOS **tipo 8** (*Port
Connector Information*), que é ``400 root`` e por isso inalcançável para a GUI,
junta o que o kernel dá de graça, e grava um ``gabinete.json`` que a aba Conexões
abre com o gabinete JÁ DESENHADO — em vez de pedir três números digitados.

Sprint ``MOTOR-DO-ARRANJO-01`` §7.4 e MOTOR-7. Pedido dela, 25/08/2026: *"manda
isso tudo pro nosso install viu. não podemos deixar isso passar. a ideia é que o
install faça o trampo sujo todo pro user sempre ter facilidade"*.

A BIOS DESTA PLACA MENTE, E ESSE É O DESENHO INTEIRO
-----------------------------------------------------

Medido em 25/08/2026 na Gigabyte B450M S2H, com ``pkexec dmidecode -t 8``: a
tabela tem **18 entradas**, cinco delas USB (``J1500``..``J1504``), e **não
descreve esta máquina**. Declara **5** conectores USB onde a traseira entrega
**8**, e declara um ``USB-C`` que esta placa **não tem** — gabarito genérico do
fabricante, copiado sem ajustar.

Três contagens da mesma coisa, e as três divergem (as duas de kernel remedidas
nesta árvore em 25/08/2026, 21h18, com o hub externo de volta ao barramento):

===========================  =======  =====
fonte                        conta    root?
===========================  =======  =====
BIOS, DMI tipo 8             5 USB    sim
ela, na foto numerada        8 externos  —
kernel, nós de raiz          22       não
kernel, buracos de raiz      15       não
===========================  =======  =====

**Nenhuma é autoritativa, e por isso este módulo NUNCA elege uma.** Ele grava
todas, marca ``divergem``, e deixa a pergunta pronta para a aba fazer. Foi assim
que a §7.4 da sprint pediu, e é a regra desta casa: *divergência declarada é
informação; divergência escondida é o defeito de forma F6*.

**Firmware é FONTE, nunca premissa.** Com o censo vazio a aba continua inteira —
ela cai nos três números da §7.1 e pergunta. O que este módulo não pode fazer é
**inventar**: um gabinete de mentira é pior que nenhum, porque ela confia nele.

O QUE ESTE MÓDULO NÃO FAZ
--------------------------

**Não chama ``dmidecode``.** O texto entra por argumento — quem tem o root é o
roteiro de shell, e quem decide é o módulo puro. É a mesma política de
``kernel_cmdline.py`` (``install.sh``:1592), e é o que torna o parser testável
sem root, sem bancada e sem placa nenhuma.

**Não desenha faces.** ``faces`` sai **sempre** ``[]``, e não é preguiça: medido
em 25/08/2026, ``usb1-port3`` (teclado) e ``usb1-port6`` (mouse) são byte a byte
iguais nos três campos de ``physical_location`` — ``panel=right``,
``horizontal_position=left``, ``vertical_position=lower`` — e a tabela ACPI desta
placa nunca diz ``front`` nem ``back``. O DMI tipo 8 dá o **inventário**, não a
face. Quem sabe qual buraco é da frente é **ela**, e a aba pergunta.

**Não conta hub externo.** O gabinete é o chassi. ``listar_entradas`` devolve os
nós de TODOS os hubs (38 nesta bancada às 21h18, com o hub de volta); aqui só
entram os nós de **hub-raiz**, que são 22 — exatamente a soma dos ``maxchild``
dos quatro barramentos, medida por uma régua independente e conferida no próprio
censo (:func:`censo_do_kernel`).

100% STDLIB, E ISSO É CONTRATO
-------------------------------

O ``install.sh`` carrega este arquivo pelo ``python3`` do SISTEMA, de dentro de
um heredoc, com ``sys.path`` apontando para ``src/`` — sem venv e sem pacote
instalado. Uma dependência de terceiros aqui viraria um passo mudo do instalador.
A única importação de produto é ``entradas_do_gabinete``, que também é stdlib
pura, e é de propósito: contar soquete de outro jeito seria a **segunda verdade**
que esta leva inteira existe para matar.

Nenhuma constante de módulo lê o disco (``CANARIO-FS-01``, ``tests/conftest.py``):
``caminho_padrao()`` resolve o ``HOME`` **na hora da chamada**.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from .entradas_do_gabinete import NoDeEntrada, furos, listar_entradas

# ══ 1. OS QUATRO SELOS ═══════════════════════════════════════════════════
#
# Vocabulário PRÓPRIO, e não os três de `ordens_da_mesa.py`, porque a pergunta é
# outra. Lá é *"como sei que este conselho vale"*; aqui é *"por que rota este
# número chegou até mim"* — e a rota é o que decide se ele pode ser refeito sem
# senha. A chave é ASCII com hífen, a convenção do `de_onde_sei` do mapa de
# canais; o texto de tela é da frente do léxico, não deste arquivo.

#: Veio da tabela SMBIOS. O tipo 8 exige root (``/sys/firmware/dmi/tables/DMI``
#: é ``400 root``); os campos de identificação da placa não, porque o kernel os
#: republica em ``/sys/class/dmi/id/`` legíveis por todo mundo. A rota muda, a
#: procedência do dado não — e é a procedência que este selo nomeia.
LIDO_DO_FIRMWARE = "lido-do-firmware"

#: Veio do ``/sys`` do kernel, sem root e sem subprocesso: os nós de entrada e o
#: ``maxchild`` de cada hub-raiz.
LIDO_DO_KERNEL = "lido-do-kernel"

#: **Ela** disse, na aba. Este módulo NUNCA grava este selo — ele existe porque a
#: aba escreve no mesmo arquivo, e um vocabulário partido em dois arquivos é como
#: se perde o significado de um campo.
DECLARADO_POR_ELA = "declarado-por-ela"

#: A fonte foi consultada e não respondeu nada de aproveitável. **Não é a mesma
#: coisa que o valor ser zero**: zero com selo de firmware afirma que a placa não
#: tem conector nenhum, e é justamente a mentira que este selo existe para não
#: deixar acontecer.
NAO_RESPONDEU = "nao-respondeu"

#: Os quatro, e é contra esta tupla que o portão do selo confere.
SELOS = (LIDO_DO_FIRMWARE, LIDO_DO_KERNEL, DECLARADO_POR_ELA, NAO_RESPONDEU)

#: Sobe quando a FORMA do arquivo mudar de um jeito que a aba precise notar.
VERSAO_DO_CENSO = 1

#: O nome do arquivo dentro de ``~/.local/state/hefesto-dualsense4unix/`` — a
#: mesma pasta em que o ``install.sh`` já escreve (``:972``, ``:2943``).
NOME_DO_ARQUIVO = "gabinete.json"

#: Onde o kernel publica a tabela SMBIOS decomposta. O ``raw`` de cada entrada é
#: ``400 root``, mas **o diretório é listável por qualquer um** — e é por isso
#: que dá para saber que a tabela 8 EXISTE mesmo sem poder lê-la. Default de
#: argumento, nunca constante usada direto (CANARIO-FS-01).
RAIZ_DMI_PADRAO = "/sys/firmware/dmi/entries"

#: Onde o kernel republica a identificação da placa, sem root.
RAIZ_DMI_ID_PADRAO = "/sys/class/dmi/id"

#: Onde o kernel publica o barramento USB.
RAIZ_USB_PADRAO = "/sys/bus/usb/devices"


# ══ 2. O LIXO QUE O FIRMWARE ESCREVE ═════════════════════════════════════
#
# Isto NÃO é desconfiança genérica do fabricante: é medido nesta placa, hoje.
# `/sys/class/dmi/id/board_version` responde literalmente `Default string` — o
# gabarito do fabricante que ninguém preencheu. Uma tabela 8 inteira preenchida
# assim tem 18 blocos e ZERO informação, e tratá-la como resposta é como se
# desenha um gabinete que não é o dela.

#: As frases com que o firmware diz "não preenchi", em minúsculas. A lista é
#: fechada de propósito: adivinhar por heurística ("parece genérico") descartaria
#: designação de verdade, e designação de verdade é rara e cara.
_LIXO_DE_FIRMWARE = frozenset(
    {
        "",
        "-",
        "default string",
        "n/a",
        "no connection",
        "none",
        "not applicable",
        "not available",
        "not specified",
        "other",
        "system manufacturer",
        "system product name",
        "to be filled by o.e.m.",
        "to be filled by o.e.m",
        "unknown",
    }
)

#: Um bloco do ``dmidecode -t 8`` começa aqui.
_CABECALHO_DA_TABELA_8 = re.compile(r"^\s*Handle\s+0x[0-9A-Fa-f]+,\s*DMI type 8\b")

#: Qualquer cabeçalho de bloco — serve para saber onde o bloco anterior termina.
_CABECALHO_DE_BLOCO = re.compile(r"^\s*Handle\s+0x[0-9A-Fa-f]+,\s*DMI type\b")

#: ``\tExternal Reference Designator: J1500`` -> (rótulo, valor).
_CAMPO = re.compile(r"^\s+([A-Z][A-Za-z0-9 /()\.-]*?):\s*(.*)$")

#: ``usb1``, ``usb2``… — o hub-RAIZ, e o único cujo nome não é ``bus-devpath``.
#: É a mesma régua de ``mesa_de_radio.py``, e é o que separa o CHASSI do hub que
#: ela pendurou na mesa.
_HUB_RAIZ = re.compile(r"^usb[0-9]+$")

#: Os tipos de chassi do SMBIOS que significam "não tem rack, não tem traseira
#: com oito buracos" — o caso do notebook, que a §5 da sprint chama de boa parte
#: do público. Fonte: SMBIOS 3.x, tabela 7.4.1 (*Chassis Types*).
_CHASSI_MOVEL = frozenset({8, 9, 10, 11, 12, 14, 30, 31, 32})

#: Os que significam "tem gabinete de verdade". Fora dos dois conjuntos a
#: resposta honesta é ``None`` — e não "desktop por padrão".
_CHASSI_FIXO = frozenset({3, 4, 5, 6, 7, 13, 15, 16, 17, 23, 24, 28})


# ══ 3. UM CONECTOR DA TABELA 8 ═══════════════════════════════════════════


@dataclass(frozen=True)
class Conector:
    """Uma entrada de *Port Connector Information* que sobreviveu ao filtro.

    Os cinco campos saem verbatim do ``dmidecode``, sem normalizar: a palavra do
    fabricante é o dado, e reescrevê-la seria apagar a única evidência de que ele
    respondeu. Quem traduz para tela é a aba.
    """

    designacao_externa: str = ""
    tipo_externo: str = ""
    designacao_interna: str = ""
    tipo_interno: str = ""
    tipo_de_porta: str = ""

    @property
    def externo(self) -> bool:
        """Este conector aparece na CARCAÇA? — o único que a pessoa alcança.

        Cabeçote interno (``F_USB1`` e parentes) é fato e fica gravado, mas não
        conta como buraco do gabinete: mandar alguém procurar um cabeçote de
        placa-mãe atrás do gabinete é pior que não dizer nada.
        """
        return not _lixo(self.designacao_externa) or not _lixo(self.tipo_externo)

    @property
    def e_usb(self) -> bool:
        """USB? — decidido pelos campos de TIPO, nunca pela designação.

        A designação é serigrafia (``J1500``) e não diz nada sobre o protocolo;
        já os tipos vêm de tabela do SMBIOS e falam. A régua é substring porque o
        vocabulário varia com a versão do ``dmidecode`` e do firmware —
        ``USB``, ``USB 3.0``, ``Access Bus (USB)``, ``USB Type-C Receptacle`` e
        ``USB-C`` são todos o mesmo assunto, e todos contêm ``usb``.
        """
        return any(
            "usb" in campo.casefold()
            for campo in (self.tipo_de_porta, self.tipo_externo, self.tipo_interno)
        )

    def como_dicionario(self) -> dict[str, object]:
        return {
            "designacao_externa": self.designacao_externa,
            "tipo_externo": self.tipo_externo,
            "designacao_interna": self.designacao_interna,
            "tipo_interno": self.tipo_interno,
            "tipo_de_porta": self.tipo_de_porta,
            "externo": self.externo,
            "usb": self.e_usb,
            "de_onde_sei": LIDO_DO_FIRMWARE,
        }


def _lixo(valor: str) -> bool:
    """O firmware escreveu alguma coisa aqui, ou repetiu o gabarito?"""
    return valor.strip().casefold() in _LIXO_DE_FIRMWARE


def conector_de_verdade(conector: Conector) -> bool:
    """**A CURA.** Um bloco só é conector quando ALGUM campo foi preenchido.

    Medido em 25/08/2026: esta placa tem 18 blocos na tabela 8 e cinco deles com
    conteúdo. Sem este filtro, uma placa cuja tabela é gabarito puro — que é o
    caso comum, e o que a §7.4 da sprint avisou — produziria 18 conectores com
    selo ``lido-do-firmware``, o censo diria ``respondeu``, e a aba desenharia um
    gabinete que ninguém tem. É o defeito exato que a mordida
    ``test_placa_sem_tabela_8_nao_inventa_gabinete`` arranca e devolve.
    """
    return not all(
        _lixo(campo)
        for campo in (
            conector.designacao_externa,
            conector.tipo_externo,
            conector.designacao_interna,
            conector.tipo_interno,
            conector.tipo_de_porta,
        )
    )


# ══ 4. O PARSER — texto do dmidecode, sem root e sem subprocesso ═════════


def blocos_da_tabela_8(texto: str) -> int:
    """Quantos blocos ``DMI type 8`` o texto traz — **lixo incluído**.

    É a contagem BRUTA, e ela vale por si: 18 blocos com zero conteúdo é uma
    afirmação sobre o fabricante, não sobre a máquina, e some se contarmos só os
    que sobreviveram ao filtro.
    """
    return sum(1 for linha in texto.splitlines() if _CABECALHO_DA_TABELA_8.match(linha))


def conectores_do_dmidecode(texto: str) -> tuple[Conector, ...]:
    """Os conectores REAIS da tabela 8 — os de gabarito ficam de fora.

    Texto vazio devolve tupla vazia, e é o caminho normal em três casos: placa
    sem tabela 8, ``dmidecode`` ausente, e install rodado sem poder de root. Os
    três são *"não respondeu"*, e nenhum deles é *"a placa não tem conector"*.
    """
    achados: list[Conector] = []
    for bloco in _blocos(texto):
        conector = Conector(
            designacao_externa=bloco.get("External Reference Designator", ""),
            tipo_externo=bloco.get("External Connector Type", ""),
            designacao_interna=bloco.get("Internal Reference Designator", ""),
            tipo_interno=bloco.get("Internal Connector Type", ""),
            tipo_de_porta=bloco.get("Port Type", ""),
        )
        if conector_de_verdade(conector):
            achados.append(conector)
    return tuple(achados)


def _blocos(texto: str) -> list[dict[str, str]]:
    """Os blocos de tipo 8, cada um como ``rótulo -> valor``.

    O ``dmidecode -t 8`` já filtra por tipo, mas o parser não conta com isso: um
    dia alguém passa a saída de ``dmidecode`` inteira e o resultado tem de ser o
    mesmo. Por isso ele abre em ``DMI type 8`` e fecha em QUALQUER cabeçalho.
    """
    saida: list[dict[str, str]] = []
    dentro: dict[str, str] | None = None
    for linha in texto.splitlines():
        if _CABECALHO_DE_BLOCO.match(linha):
            if dentro is not None:
                saida.append(dentro)
            dentro = {} if _CABECALHO_DA_TABELA_8.match(linha) else None
            continue
        if dentro is None:
            continue
        campo = _CAMPO.match(linha)
        if campo is not None:
            dentro[campo.group(1).strip()] = campo.group(2).strip()
    if dentro is not None:
        saida.append(dentro)
    return saida


def entradas_no_sysfs(
    *,
    raiz_dmi: str = RAIZ_DMI_PADRAO,
    listar: Callable[[str], list[str]] = os.listdir,
) -> int | None:
    """Quantas entradas de tipo 8 o kernel publica — **sem root**, e é o pulo.

    O conteúdo de cada entrada é ``400 root``, mas o DIRETÓRIO é listável: nesta
    bancada, ``ls /sys/firmware/dmi/entries | grep -c '^8-'`` responde **18** com
    o usuário comum. Isso separa duas coisas que a aba precisa não confundir:

    * *"a sua placa não tem tabela de conectores"* — ``0``;
    * *"a sua placa TEM 18 e eu não tive root para lê-las"* — ``18`` com
      ``tabela_8_respondeu`` falso, e aí a frase honesta é pedir o install de
      novo, não pedir os três números.

    ``None`` quando o ``/sys`` não respondeu: contêiner, sandbox, kernel sem DMI.
    """
    try:
        nomes = listar(raiz_dmi)
    except OSError:
        return None
    return sum(1 for nome in nomes if nome.startswith("8-"))


# ══ 5. A PLACA — identificação sem root ══════════════════════════════════


def ler_a_placa(
    *,
    raiz_dmi_id: str = RAIZ_DMI_ID_PADRAO,
    ler: Callable[[str], str] | None = None,
) -> dict[str, object]:
    """Quem é esta placa — e serve para saber que o censo é DESTA máquina.

    Todos os campos saem de ``/sys/class/dmi/id/``, legível por qualquer usuário.
    Medido em 25/08/2026: ``Gigabyte Technology Co., Ltd.`` / ``B450M S2H`` /
    BIOS ``F68a`` / ``chassis_type = 3`` (desktop). O ``board_version`` responde
    ``Default string``, que é o gabarito do fabricante e o motivo de
    :data:`_LIXO_DE_FIRMWARE` existir.

    ``movel`` é três estados de propósito: ``True`` notebook e parentes, ``False``
    gabinete de verdade, ``None`` quando o tipo não está em nenhuma das duas
    listas — porque *"não sei"* é resposta, e "desktop por padrão" mandaria quem
    tem um notebook procurar um rack.
    """
    leitor = _ler_texto if ler is None else ler
    bruto = {
        campo: leitor(os.path.join(raiz_dmi_id, campo)).strip()
        for campo in ("board_vendor", "board_name", "bios_version", "chassis_type")
    }
    tipo = _talvez_inteiro(bruto["chassis_type"])
    movel: bool | None = None
    if tipo in _CHASSI_MOVEL:
        movel = True
    elif tipo in _CHASSI_FIXO:
        movel = False
    return {
        "fabricante": _talvez(_ou_nada(bruto["board_vendor"]), LIDO_DO_FIRMWARE),
        "modelo": _talvez(_ou_nada(bruto["board_name"]), LIDO_DO_FIRMWARE),
        "bios": _talvez(_ou_nada(bruto["bios_version"]), LIDO_DO_FIRMWARE),
        "tipo_de_chassi": _talvez(tipo, LIDO_DO_FIRMWARE),
        "movel": _talvez(movel, LIDO_DO_FIRMWARE),
    }


def serve_para_esta_placa(censo: dict[str, object], placa: dict[str, object]) -> bool:
    """**A CURA.** Este ``gabinete.json`` é DESTA máquina?

    Um censo copiado junto com o ``~/.local/state`` — restauro de backup, HOME em
    disco externo, a mesma pasta em dois PCs — desenharia o gabinete de OUTRA
    placa com selo de firmware. Pior que gabinete nenhum, pela mesma razão de
    sempre: ela confia no que o produto desenha.

    Compara fabricante **e** modelo. Quando qualquer um dos dois lados não sabe
    quem é, a resposta é ``False`` — não dá para afirmar que serve, e afirmar é
    justamente o erro. Mordida: ``test_censo_de_outra_placa_nao_serve``.
    """
    gravada = censo.get("placa")
    if not isinstance(gravada, dict):
        return False
    for campo in ("fabricante", "modelo"):
        antes = _valor(gravada.get(campo))
        agora = _valor(placa.get(campo))
        if antes is None or agora is None or antes != agora:
            return False
    return True


# ══ 6. O KERNEL — os soquetes do CHASSI, sem root ════════════════════════


def soquetes_de_raiz(entradas: Sequence[NoDeEntrada]) -> tuple[NoDeEntrada, ...]:
    """Só os nós pendurados num hub-RAIZ — o chassi, sem o hub da mesa.

    Medido nesta árvore em 25/08/2026 às 21h18, com o hub externo de volta ao
    barramento: ``listar_entradas`` devolve **38** nós, distribuídos por oito
    hubs (``usb1``..``usb4`` e quatro internos do hub dela). Filtrando pelos
    quatro de raiz sobram **22** — que é exatamente a soma dos ``maxchild``. Sem
    este filtro, o gabinete dela cresceria e encolheria conforme ela plugasse e
    desplugasse o hub, que é o oposto do que um mapa de gabinete deve fazer.
    """
    return tuple(entrada for entrada in entradas if _HUB_RAIZ.match(entrada.hub))


def ler_maxchild(
    *,
    raiz_usb: str = RAIZ_USB_PADRAO,
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
) -> dict[str, int]:
    """Quantos soquetes cada hub-raiz declara — a SEGUNDA régua da contagem.

    Contar nós de entrada e ler ``maxchild`` são dois caminhos independentes para
    o mesmo número, e é regra desta casa ter dois: *"duas réguas independentes é
    o que revela"*. Medido em 25/08/2026: ``usb1``=10, ``usb2``=4, ``usb3``=4,
    ``usb4``=4, soma **22** — e a contagem de nós deu 22 também. Quando as duas
    discordarem, :func:`censo_do_kernel` grava as duas e diz que discordam, em
    vez de escolher.
    """
    leitor = _ler_texto if ler is None else ler
    try:
        nomes = sorted(listar(raiz_usb))
    except OSError:
        return {}
    saida: dict[str, int] = {}
    for nome in nomes:
        if not _HUB_RAIZ.match(nome):
            continue
        quantos = _talvez_inteiro(leitor(os.path.join(raiz_usb, nome, "maxchild")))
        if quantos is not None:
            saida[nome] = quantos
    return saida


def censo_do_kernel(
    entradas: Sequence[NoDeEntrada], maxchild: dict[str, int]
) -> dict[str, object]:
    """As contagens que o kernel dá de graça, cada uma com o que ela significa.

    * ``soquetes`` — nós de entrada de raiz. **22** aqui;
    * ``buracos`` — os mesmos nós agrupados pelo symlink ``peer``. **15** aqui: um
      buraco USB 3.x aparece como DOIS nós (o lado 2.0 e o lado 3.x) e é UM
      buraco. Contar nó mandaria ela procurar 22 furos num gabinete que tem 15;
    * ``buracos_de_encaixe`` — os buracos cujo ``connect_type`` é ``hotplug``.
      **11** aqui, contra ``unknown`` em 4. O ``unknown`` NÃO vira ``hardwired``:
      nesta placa é o que separa as internas das de gabinete, e apagá-lo seria
      jogar medição fora;
    * ``maxchild`` — a segunda régua, e ``reguas_concordam`` diz se bateu.

    Nenhum destes é *"quantos buracos a traseira dela tem"*. Ela tem **8**
    externos, e nenhuma das contagens de kernel chega a esse número: o barramento
    conta cabeçote interno e a duplicação 2.0/3.0 do mesmo furo. É por isso que a
    aba pergunta, e é por isso que este módulo não elege.
    """
    raiz = soquetes_de_raiz(entradas)
    buracos = furos(raiz) if raiz else ()
    de_encaixe = sum(1 for buraco in buracos if buraco.tipo_de_encaixe == "hotplug")
    soma = sum(maxchild.values()) if maxchild else None
    return {
        "soquetes": _talvez(len(raiz) if raiz else None, LIDO_DO_KERNEL),
        "buracos": _talvez(len(buracos) if buracos else None, LIDO_DO_KERNEL),
        "buracos_de_encaixe": _talvez(de_encaixe if buracos else None, LIDO_DO_KERNEL),
        "maxchild": _talvez(soma, LIDO_DO_KERNEL),
        "por_barramento": dict(sorted(maxchild.items())),
        "reguas_concordam": None if (soma is None or not raiz) else soma == len(raiz),
    }


# ══ 7. A DIVERGÊNCIA — declarada, nunca resolvida ════════════════════════


def declarar_divergencia(
    *, firmware: int | None, soquetes: int | None, buracos: int | None
) -> dict[str, object]:
    """As contagens lado a lado, e a pergunta pronta para a aba fazer.

    **A CURA, e é a segunda mordida.** Com a saída real desta placa (5 USB) e o
    kernel real (22 soquetes / 15 buracos), o resultado é ``divergem = True`` e as
    três contagens gravadas. Arrancada — fazendo o firmware vencer — o censo
    grava **5** e a aba desenha cinco entradas para quem tem oito; a pessoa
    procura no gabinete três buracos que o mapa não mostra, e desiste achando que
    entendeu errado.

    ``divergem`` só é ``True`` quando há **duas** fontes para comparar: uma fonte
    sozinha não diverge de nada, e marcar divergência ali seria ruído. Já
    ``precisa_da_palavra_dela`` é **sempre** ``True``, e não é redundância — é o
    §7.4 inteiro: *nenhuma das três é autoritativa*. Mesmo se as três batessem,
    quem sabe quantos buracos a traseira dela tem continua sendo ela.
    """
    vistos = [n for n in (soquetes, buracos) if n is not None]
    divergem = firmware is not None and bool(vistos) and firmware not in vistos
    return {
        "firmware": _talvez(firmware, LIDO_DO_FIRMWARE),
        "kernel_soquetes": _talvez(soquetes, LIDO_DO_KERNEL),
        "kernel_buracos": _talvez(buracos, LIDO_DO_KERNEL),
        "declarado_por_ela": _fato(None, NAO_RESPONDEU),
        "divergem": divergem,
        "precisa_da_palavra_dela": True,
        "pergunta": _pergunta(firmware=firmware, buracos=buracos, divergem=divergem),
    }


def _pergunta(*, firmware: int | None, buracos: int | None, divergem: bool) -> str:
    """A frase que a aba mostra. **Provisória, e o dono dela é o léxico.**

    Ela nasce aqui porque precisa dos números, e porque um censo que grava a
    divergência sem saber dizê-la em voz alta deixa a aba livre para escondê-la —
    que é o F6. A frente do léxico pode substituir o texto; o que não pode é
    apagar os números que o sustentam.
    """
    if divergem and firmware is not None and buracos is not None:
        return (
            f"A BIOS desta placa diz {firmware} conectores USB, e no barramento "
            f"eu vejo {buracos} buracos. As duas contas discordam, e nenhuma "
            "delas viu o seu gabinete. Quantos buracos a sua traseira tem?"
        )
    if firmware is None and buracos is None:
        return (
            "Não consegui contar as entradas USB desta máquina — nem a BIOS "
            "respondeu, nem o barramento. Quantos buracos a sua traseira tem?"
        )
    return (
        "Contei as entradas USB por uma fonte só, e ela não viu o seu gabinete "
        "por fora. Quantos buracos a sua traseira tem?"
    )


# ══ 8. O CENSO INTEIRO ═══════════════════════════════════════════════════


def montar_censo(
    *,
    dmidecode: str = "",
    entradas: Sequence[NoDeEntrada] = (),
    maxchild: dict[str, int] | None = None,
    placa: dict[str, object] | None = None,
    entradas_da_tabela_8: int | None = None,
    agora: str = "",
) -> dict[str, object]:
    """O ``gabinete.json`` inteiro, e **cada fato com o seu selo**.

    ``faces`` sai vazio SEMPRE — ver o cabeçalho do módulo. O firmware dá o
    inventário; a face é dela.

    Quando a tabela 8 não responde, o campo de contagem sai ``None`` com selo
    ``nao-respondeu`` — nunca ``0`` com selo de firmware. A diferença é a
    diferença entre *"não sei"* e *"a sua placa não tem conector nenhum"*, e a
    segunda é uma afirmação que este módulo não tem como fazer.
    """
    conectores = conectores_do_dmidecode(dmidecode)
    respondeu = bool(conectores)
    usb_externos = sum(1 for c in conectores if c.e_usb and c.externo)
    brutos = blocos_da_tabela_8(dmidecode)
    kernel = censo_do_kernel(entradas, maxchild or {})
    return {
        "versao_do_censo": VERSAO_DO_CENSO,
        "gravado_em": agora or _agora(),
        "de_onde_sei": LIDO_DO_FIRMWARE if respondeu else NAO_RESPONDEU,
        "faces": [],
        "por_que_faces_vazias": (
            "O firmware dá o inventário de conectores, não a face em que cada um "
            "está — e o kernel também não: medido em 25/08/2026, o teclado e o "
            "mouse desta bancada têm physical_location idêntico. Quem sabe qual "
            "buraco é da frente é você."
        ),
        "placa": placa if placa is not None else {},
        "firmware": {
            "tabela_8_respondeu": respondeu,
            "blocos_lidos": _talvez(brutos if dmidecode.strip() else None, LIDO_DO_FIRMWARE),
            "entradas_no_sysfs": _talvez(entradas_da_tabela_8, LIDO_DO_KERNEL),
            "conectores": [c.como_dicionario() for c in conectores],
            "conectores_usb": _talvez(usb_externos if respondeu else None, LIDO_DO_FIRMWARE),
        },
        "kernel": kernel,
        "contagens": declarar_divergencia(
            firmware=usb_externos if respondeu else None,
            soquetes=_numero(kernel["soquetes"]),
            buracos=_numero(kernel["buracos"]),
        ),
    }


def ler_o_gabinete(
    *,
    dmidecode: str = "",
    raiz_usb: str = RAIZ_USB_PADRAO,
    raiz_dmi: str = RAIZ_DMI_PADRAO,
    raiz_dmi_id: str = RAIZ_DMI_ID_PADRAO,
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
) -> dict[str, object]:
    """O censo desta máquina — a única função aqui que toca o ``/sys``.

    O texto do ``dmidecode`` entra por argumento: quem tem root é o roteiro do
    install. Tudo o mais é leitura sem privilégio, e continua funcionando quando
    o root faltou — só que dizendo que faltou.
    """
    return montar_censo(
        dmidecode=dmidecode,
        entradas=listar_entradas(raiz_usb=raiz_usb, listar=listar, ler=ler),
        maxchild=ler_maxchild(raiz_usb=raiz_usb, listar=listar, ler=ler),
        placa=ler_a_placa(raiz_dmi_id=raiz_dmi_id, ler=ler),
        entradas_da_tabela_8=entradas_no_sysfs(raiz_dmi=raiz_dmi, listar=listar),
    )


# ══ 9. GRAVAR ════════════════════════════════════════════════════════════


def caminho_padrao(*, home: str = "") -> str:
    """``~/.local/state/hefesto-dualsense4unix/gabinete.json``.

    O ``HOME`` é lido **na chamada**, nunca na importação: constante de módulo é
    avaliada antes de qualquer isolamento e aponta para a pasta real dela, que é
    a cicatriz que o ``CANARIO-FS-01`` guarda.
    """
    raiz = home or os.path.expanduser("~")
    return os.path.join(raiz, ".local", "state", "hefesto-dualsense4unix", NOME_DO_ARQUIVO)


def ler_do_disco(caminho: str = "") -> dict[str, object]:
    """O ``gabinete.json`` que já está lá — ``{}`` quando não há ou não abre.

    Nenhuma falha aqui é excepcional: primeira instalação, arquivo truncado por
    um desligamento, formato de uma versão futura. Nos três a resposta é a mesma
    — *"não tinha nada"* — e o install segue.
    """
    try:
        with open(caminho or caminho_padrao(), encoding="utf-8") as arquivo:
            lido = json.load(arquivo)
    except (OSError, ValueError):
        return {}
    return lido if isinstance(lido, dict) else {}


def preservar_o_que_ela_disse(
    novo: dict[str, object], antigo: dict[str, object], placa: dict[str, object]
) -> dict[str, object]:
    """**A CURA.** Reinstalar não pode apagar o que ela ensinou ao produto.

    O censo é escrito pelo install, mas ele NÃO é o único que escreve neste
    arquivo: quem responde *"a minha traseira tem 8"* é ela, na aba, e a resposta
    mora aqui — é o único lugar onde ela mora. Um ``install.sh`` que grava por
    cima sem olhar apaga o trabalho dela **em silêncio**, e o sintoma é o pior
    possível: a aba volta a perguntar o que ela já respondeu, e ela conclui que o
    produto não guarda nada.

    Arrancada esta função (gravando o censo novo direto), a segunda instalação
    zera ``faces`` e ``declarado_por_ela``. Mordida:
    ``test_o_install_nao_apaga_o_que_ela_ensinou``.

    **A carona tem limite, e é a placa.** Um censo de outra máquina não empresta
    declaração nenhuma — as faces dele descreveriam um gabinete que não é este.
    Nesse caso o novo passa inteiro e o campo ``substituiu_outra_placa`` diz por
    quê, para a aba poder avisar em vez de a troca acontecer no escuro.

    A FORMA de ``faces`` é da aba, não deste módulo: aqui ela é opaca e viaja
    inteira. Inventar um esquema para o que outra frente escreve seria a segunda
    verdade de sempre.
    """
    if not antigo:
        return novo
    if not serve_para_esta_placa(antigo, placa):
        return {**novo, "substituiu_outra_placa": True}
    herdado = dict(novo)
    faces = antigo.get("faces")
    if isinstance(faces, list) and faces:
        herdado["faces"] = faces
    dela = _dela(antigo)
    contagens = herdado.get("contagens")
    if dela is not None and isinstance(contagens, dict):
        novas = dict(contagens)
        novas["declarado_por_ela"] = _fato(dela, DECLARADO_POR_ELA)
        novas["precisa_da_palavra_dela"] = False
        herdado["contagens"] = novas
    return herdado


def _dela(censo: dict[str, object]) -> object:
    contagens = censo.get("contagens")
    if not isinstance(contagens, dict):
        return None
    return _valor(contagens.get("declarado_por_ela"))


def gravar(censo: dict[str, object], caminho: str = "") -> str:
    """Grava o censo e devolve o caminho. Escrita ATÔMICA, por troca de nome.

    Um ``gabinete.json`` truncado no meio da escrita — desligar no tempo errado,
    disco cheio — é um JSON quebrado que a aba não sabe abrir, e o produto abriria
    sem gabinete sem saber por quê. Grava-se ao lado e renomeia-se por cima:
    ``os.replace`` é atômico no mesmo sistema de arquivos.
    """
    alvo = caminho or caminho_padrao()
    os.makedirs(os.path.dirname(alvo), exist_ok=True)
    provisorio = f"{alvo}.novo"
    with open(provisorio, "w", encoding="utf-8") as arquivo:
        json.dump(censo, arquivo, ensure_ascii=False, indent=2, sort_keys=True)
        arquivo.write("\n")
    os.replace(provisorio, alvo)
    return alvo


def resumo(censo: dict[str, object]) -> str:
    """Uma linha para o install imprimir — o que ficou sabido, e o que não."""
    firmware = censo.get("firmware")
    contagens = censo.get("contagens")
    if not isinstance(firmware, dict) or not isinstance(contagens, dict):
        return "censo do gabinete vazio"
    usb = _valor(firmware.get("conectores_usb"))
    buracos = _valor(contagens.get("kernel_buracos"))
    partes = [
        f"BIOS: {usb} conectores USB" if usb is not None else "BIOS: não respondeu",
        f"barramento: {buracos} buracos" if buracos is not None else "barramento: mudo",
    ]
    if contagens.get("divergem"):
        partes.append("DIVERGEM — a aba vai perguntar")
    return " · ".join(partes)


# ══ 10. Interno ══════════════════════════════════════════════════════════


def _fato(valor: object, selo: str) -> dict[str, object]:
    """Todo número deste arquivo é um par ``{valor, de_onde_sei}``, sem exceção.

    Um número solto num JSON perde a rota por onde chegou no primeiro ``get`` que
    alguém escrever, e aí a aba não tem como distinguir o que a BIOS afirmou do
    que o kernel contou. Há teste que varre a árvore inteira e reprova ``valor``
    sem ``de_onde_sei`` ao lado.
    """
    return {"valor": valor, "de_onde_sei": selo}


def _talvez(valor: object, selo: str) -> dict[str, object]:
    """Um fato que pode não existir — e a AUSÊNCIA troca o selo, não só o valor.

    ``None`` com selo de fonte afirmaria que a fonte respondeu ``nada``; o que
    aconteceu foi ela não responder. É a mesma distinção do :data:`NAO_RESPONDEU`,
    aplicada em todo campo opcional de uma vez para ninguém esquecer num deles.
    """
    return _fato(valor, selo if valor is not None else NAO_RESPONDEU)


def _valor(fato: object) -> object:
    return fato.get("valor") if isinstance(fato, dict) else None


def _numero(fato: object) -> int | None:
    """O ``valor`` de um fato quando ele é contagem — ``None`` em todo o resto.

    O JSON gravado é ``dict[str, object]`` por natureza, e tirar um ``int`` dele
    exige afirmar o tipo em algum lugar. Este é o lugar, e ele AFIRMA olhando —
    ``isinstance`` — em vez de calar o verificador com um ``ignore``. Um censo
    lido de um disco antigo pode trazer texto onde havia número, e aí a resposta
    certa é *"não sei"*, não um estouro no meio do install.
    """
    valor = _valor(fato)
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def _ou_nada(texto: str) -> str | None:
    """Gabarito de fabricante vira ``None`` — ``Default string`` não é o modelo."""
    return None if _lixo(texto) else texto


def _talvez_inteiro(valor: str) -> int | None:
    try:
        return int(valor.strip())
    except (AttributeError, TypeError, ValueError):
        return None


def _agora() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _ler_texto(caminho: str) -> str:
    try:
        with open(caminho, encoding="utf-8", errors="ignore") as arquivo:
            return arquivo.read()
    except OSError:
        return ""
