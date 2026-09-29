"""mapa_das_portas.py — o número que ELA escreveu no gabinete, e o que ele responde.

O PROBLEMA QUE ESTE MÓDULO RESOLVE
-----------------------------------

O produto sabe o **caminho de barramento** de cada aparelho (``3-1.1.4``) e não
sabe o **número da entrada** que ela enxerga no metal (``15a``). Toda frase de
diagnóstico da aba nasce em jargão por causa disso, e a pessoa não consegue
achar no gabinete o aparelho de que a tela está falando.

O mapa (``utils/maquina.MapaDaMesa``) é o que ela declarou; o censo
(``integrations/censo_do_barramento``) é o que o kernel leu. Este módulo é a
JUNÇÃO dos dois, e nada além disso: funções puras, sem GTK, sem IPC, sem
``/dev``, sem subprocesso, sem ler arquivo nenhum.

POR QUE O MAPA TEM DE SER DECLARADO — MEDIDO, 24 e 25/08/2026
--------------------------------------------------------------

As duas entradas da FRENTE do gabinete desta bancada são **indistinguíveis para
a máquina**: ``usb1-port3`` e ``usb1-port6`` respondem ``panel=right``,
``horizontal_position=left`` e ``vertical_position=lower`` — idênticos. A ACPI
desta placa nunca diz "front" nem "back", e some inteira na controladora
``0000:0c:00.3`` (0 de 8 entradas). Deduzir o mapa daria a mesma resposta para
dois buracos que ficam em faces diferentes do metal.

E o número do sysfs também não é a posição no metal: os dois receptores de 2,4
GHz da frente dela são ``1-3`` e ``1-6`` — três portas de distância na
numeração, um centímetro de distância no plástico. É por isso que
:func:`vizinhas_de_verdade` existe: ``mesa_de_radio.vizinhancas_apertadas``
responde pelo soquete, e o soquete não é o gabinete.

O QUE ELE NÃO FAZ
------------------

**Não escreve frase de tela.** Ele entrega o número; quem escreve a frase é a
aba (o texto desta aba tem dono único, e não é este módulo).

**Não vai buscar endereço de Bluetooth.** Quem fala com o barramento de
sistema é o ``bluez_dbus``, e só ele (o dono do BlueZ, BLUEZ-UM-DONO-01).

**Não guarda serial em lugar nenhum.** Serial identifica a unidade dela tão bem
quanto o MAC (``scripts/check_anonymity.sh``): :func:`serial_do_no` o lê para a
identidade do aparelho no mapa das conexões, que o resume com sal antes de
qualquer coisa. Nunca vai para a tela, nunca para o ``maquina.json``, nunca para
um PNG.

DUAS JUNÇÕES SAÍRAM EM 28/09/2026 (A-CONEXOES-DIZ-O-QUE-O-PRODUTO-JA-MEDE-01), as
duas sem chamador desde 25/08:

* ``porta_do_adaptador`` casava o adaptador com a entrada pelo serial USB — que
  É o endereço Bluetooth nos TP-Link desta bancada e não é regra universal (o
  Wi-Fi dela responde ``123456``). O produto responde a mesma pergunta pelo
  lugar do adaptador no sysfs (``bluez_dbus.lugares_dos_adaptadores`` →
  ``utils/lugar.lugar_de``), que vale para qualquer máquina, e a aba 08 diz a
  entrada de cada adaptador por ali;
* ``incoerencias`` acusava a entrada declarada numa face que não pende do hub
  da face. O desenho aprovado não tem onde dizer isso sem um recado, e recado
  não entra (as decisões de 23/09).
"""

from __future__ import annotations

import itertools
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

from hefesto_dualsense4unix.integrations import arranjo_da_mesa as motor
from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    Aparelho,
    Censo,
)
from hefesto_dualsense4unix.integrations.entradas_do_gabinete import (
    VELOCIDADE_SUPERSPEED_MBPS,
)
from hefesto_dualsense4unix.utils.maquina import (
    MapaDaMesa,
    caminho_da_porta,
    caminhos_da_porta,
)

#: Onde mora o serial de um nó USB, relativo ao caminho do nó.
_ARQUIVO_DO_SERIAL = "serial"

@dataclass(frozen=True)
class Resumo:
    """Os três números da linha-resumo de "Conexões" — nada de texto.

    ``colocados`` conta as entradas cujo caminho declarado EXISTE no censo de
    agora. Entrada declarada com o aparelho fora não conta: o resumo diz o que
    está na mesa, não o que já esteve.
    """

    faces: int = 0
    entradas: int = 0
    colocados: int = 0

    @property
    def vazio(self) -> bool:
        """Ninguém desenhou nada — e este é o estado legítimo mais comum."""
        return self.faces == 0 and self.entradas == 0


def controladores_do_censo(censo: Censo) -> dict[int, str]:
    """``{busnum: controlador PCI}`` pelos hubs-raiz do censo que já está na mão.

    A mesma resposta de ``mesa_de_radio.controladores_dos_barramentos``, sem
    uma segunda leitura do ``/sys``: é o que traduz o LUGAR que cada entrada
    guarda no caminho deste boot (``utils/maquina.caminho_da_porta``).
    """
    return {
        aparelho.busnum: aparelho.controlador_pci
        for aparelho in censo.aparelhos
        if aparelho.e_raiz and aparelho.controlador_pci
    }


def porta_de(
    mapa: MapaDaMesa, caminho: str, controladores: Mapping[int, str] | None = None
) -> str | None:
    """O número da entrada em que este caminho de barramento está.

    ``None`` quando nenhuma entrada dela está neste caminho — que é a resposta
    certa e a mais comum: quem nunca desenhou a mesa não tem número nenhum, e a
    tela volta a falar o caminho do sistema em vez de inventar um número.

    Pelo caminho do lado 2.0 de cada entrada primeiro, e depois pelos dois
    lados do buraco: o aparelho 3.0 enumera no nó SuperSpeed (``4-1.1.4``), e
    a entrada tem o lado 2.0 (``3-1.1.4``) — sem isto o Wi-Fi dela saía sem
    entrada na Sugestão (26/09/2026). Com os ``controladores`` deste boot, a
    entrada responde pelo LUGAR que guarda (A-ENTRADA-TEM-UM-REGISTRO-SO-01).

    Caminho vazio (o adaptador embutido, que não pendura em USB nenhum) nunca
    casa com nada: ele não está em entrada alguma.
    """
    if not caminho:
        return None
    for numero, porta in sorted(mapa.portas.items()):
        if caminho_da_porta(porta, controladores) == caminho:
            return numero
    for numero, porta in sorted(mapa.portas.items()):
        if caminho in caminhos_da_porta(porta, controladores):
            return numero
    return None


def caminho_de(
    mapa: MapaDaMesa, porta: str, controladores: Mapping[int, str] | None = None
) -> str | None:
    """O caminho do lado 2.0 desta entrada, ou ``None`` — calculado, nunca guardado."""
    declarada = mapa.portas.get(porta)
    if declarada is None:
        return None
    return caminho_da_porta(declarada, controladores) or None


def filhas_de(mapa: MapaDaMesa, porta: str) -> tuple[str, ...]:
    """As entradas que nascem de uma extensão plugada NESTA entrada.

    Cabo de extensão passivo não tem descritor USB — o dongle na ponta enumera
    como se estivesse na entrada do hub, e nenhuma leitura de ``/sys``, hoje ou
    nunca, distingue os dois casos. Quem sabe é ela, porque ela disse.
    """
    return tuple(
        sorted(
            numero
            for numero, declarada in mapa.portas.items()
            if declarada.filha_de == porta and numero != porta
        )
    )


def irmas_de(mapa: MapaDaMesa) -> dict[str, str]:
    """A irmã FIXA de cada entrada — **inclusive da vazia**.

    É a fonte de ``arranjo_da_mesa.Entrada.par``. O motor lê aquele campo para
    disparar as penalidades de vizinho rádio (-30 no teclado, -45 no Bluetooth,
    -40 no mouse) e, até 25/08/2026, **ele não tinha de onde vir**: todo quadrado
    da tela dizia "aqui fica bem" onde deveria dizer "aqui não". Juízo otimista
    demais é pior que juízo nenhum.

    "Irmã" é a outra entrada do MESMO conjunto de metal — as duas tomadas
    empilhadas num plástico só da traseira. Não é "a próxima da fileira": na
    fileira de sete do hub, a 9 é irmã da 10 e vizinha da 11, e só a primeira
    relação é a que o motor pesa.

    :func:`vizinhas_de_verdade` continua respondendo outra pergunta: ela lista os
    pares OCUPADOS AGORA (precisa do censo), aqui está o par que existe no metal
    esteja ele vazio ou cheio (não precisa de censo nenhum). Duas perguntas, dois
    valores — a mesma lei que separou ``orcamento_em_vigor`` de
    ``orcamento_na_tela``.

    UMA FONTE SÓ, E ELA É O DESENHO DELA — DECISÃO DELA, 25/08/2026
    ---------------------------------------------------------------

    As entradas de cada face, tomadas de DUAS EM DUAS na ordem em que ela as
    numerou. Não precisa de leitura nenhuma, e por isso responde com o gabinete
    inteiro vazio. É **fato dela**, nunca inferência — não há selo de procedência
    a carregar aqui, porque não há segunda fonte de que desconfiar.

    **O ``peer`` do ``/sys`` foi tentado e SAIU**, e a medição é o motivo:
    ``readlink`` em cada ``*/peer`` dos 38 nós de entrada desta bancada, em
    25/08/2026, mostrou que **todo ``peer`` atravessa dois hubs-raiz** —
    ``usb1-port5`` ↔ ``usb2-port1``, ``usb3-port1`` ↔ ``usb4-port1``,
    ``3-1-port4`` ↔ ``4-1-port4``. Ele amarra os DOIS NÓS DE UM MESMO BURACO, o
    lado 2.0 e o lado 3.x — é para isso que o kernel o publica —, e **nunca** dois
    buracos vizinhos. ``Entrada.par`` é outra coisa: duas tomadas empilhadas num
    plástico só, cada uma com o SEU aparelho ao mesmo tempo. Na mesa dela o
    ``peer`` responderia por zero entradas e o desenho responde pelas catorze.

    A entrada por extensão (a ``15a``) não tem irmã: ela não está na fileira, e
    o cabo de um metro a põe longe de todo mundo.

    **Mapa vazio devolve ``{}``, e isso não é um detalhe de implementação:** é o
    estado de quem nunca desenhou, e nele o motor fica sem ``par`` e sem as três
    penalidades. Quem consome tem de DIZER que não sabe — calar é publicar juízo
    otimista, que é o defeito que esta função existe para fechar. A frase que diz
    isso mora em ``app/actions/config/secao_mesa._SEM_MAPA``.

    O número repetido conta UMA vez, pela primeira aparição — a mesma regra de
    :func:`_entradas_da_fileira`. Quem desenhou o mesmo número duas vezes
    desenhou errado, e deixar a repetição entrar faria uma entrada virar irmã de
    si mesma.
    """
    achadas: dict[str, str] = {}
    vistos: set[str] = set()
    for face in mapa.faces:
        numeros: list[str] = []
        for numero in face.portas:
            if numero in vistos:
                continue
            vistos.add(numero)
            numeros.append(numero)
        for primeira, segunda in zip(numeros[0::2], numeros[1::2], strict=False):
            achadas[primeira] = segunda
            achadas[segunda] = primeira
    return achadas


def resumo_do_mapa(mapa: MapaDaMesa, censo: Censo) -> Resumo:
    """Quantas faces, quantas entradas e quantos aparelhos colocados."""
    entradas = {numero for face in mapa.faces for numero in face.portas}
    presentes = _caminhos_do_censo(censo)
    controladores = controladores_do_censo(censo)
    colocados = sum(
        1
        for declarada in mapa.portas.values()
        if caminho_da_porta(declarada, controladores) in presentes
    )
    return Resumo(faces=len(mapa.faces), entradas=len(entradas), colocados=colocados)


def portas_livres(mapa: MapaDaMesa, censo: Censo) -> tuple[str, ...]:
    """As entradas da fileira que estão VAZIAS agora, na ordem do desenho.

    Vazia é a entrada sem caminho declarado, ou com um caminho declarado cujo
    aparelho não está mais plugado. **A entrada que hospeda uma extensão não
    está vazia**: o cabo ocupa o buraco, mesmo que o dongle esteja a três
    metros dali — dizer "a 15 está livre" mandaria a pessoa desplugar a
    extensão dela.
    """
    presentes = _caminhos_do_censo(censo)
    controladores = controladores_do_censo(censo)
    livres: list[str] = []
    for numero in _entradas_da_fileira(mapa):
        if filhas_de(mapa, numero):
            continue
        if _caminho_presente(mapa, numero, presentes, controladores):
            continue
        livres.append(numero)
    return tuple(livres)


def ocupante_de(mapa: MapaDaMesa, numero: str, censo: Censo) -> str:
    """O caminho do aparelho que está NESTA entrada agora, ou o declarado.

    O aparelho USB 3 enumera no lado SuperSpeed do buraco (``4-1.1.4``), e a
    entrada declara o lado 2.0 (``3-1.1.4``): perguntar só pelo declarado dava
    a entrada do Wi-Fi como vazia, e a Sugestão mandava o adaptador para ela.
    """
    controladores = controladores_do_censo(censo)
    return (_caminho_presente(mapa, numero, _caminhos_do_censo(censo), controladores)
            or caminho_de(mapa, numero, controladores) or "")


def _caminho_presente(
    mapa: MapaDaMesa,
    numero: str,
    presentes: frozenset[str],
    controladores: Mapping[int, str] | None = None,
) -> str:
    """O caminho, dos dois lados do buraco, em que há aparelho agora — ``""`` se nenhum."""
    porta = mapa.portas.get(numero)
    if porta is None:
        return ""
    for caminho in caminhos_da_porta(porta, controladores):
        if caminho in presentes:
            return caminho
    return ""


def vizinhas_de_verdade(
    mapa: MapaDaMesa, censo: Censo
) -> tuple[tuple[str, str], ...]:
    """Os pares de entradas OCUPADAS que estão coladas no metal.

    Duas coisas mudam em relação a ``mesa_de_radio.vizinhancas_apertadas``, e
    as duas são o ponto deste módulo:

    * **quem manda é o desenho dela, não o número do sysfs.** Os dois
      receptores de 2,4 GHz da frente desta bancada são ``1-3`` e ``1-6``:
      três portas de distância na numeração do kernel, um centímetro no
      plástico. A vizinhança pelo sysfs não vê esse par; a pelo mapa vê;
    * **a entrada por extensão sai da fileira.** Uma entrada declarada como
      filha deixa de ser vizinha de quem está na fileira e passa a ser vizinha
      de quem estiver na MESMA extensão. Sem isso o produto pinta de laranja
      um par que está do outro lado da sala.

    Cada par aparece uma vez, na ordem do desenho. Entrada vazia não entra:
    aparelho que não existe não atrapalha ninguém.
    """
    presentes = _caminhos_do_censo(censo)
    controladores = controladores_do_censo(censo)

    def ocupada(numero: str) -> bool:
        return bool(_caminho_presente(mapa, numero, presentes, controladores))

    pares: list[tuple[str, str]] = []
    vistos: set[tuple[str, str]] = set()
    for face in mapa.faces:
        for primeira, segunda in itertools.pairwise(face.portas):
            if not (ocupada(primeira) and ocupada(segunda)):
                continue
            if (primeira, segunda) in vistos:
                continue
            vistos.add((primeira, segunda))
            pares.append((primeira, segunda))
    for numero in _entradas_da_fileira(mapa):
        irmas = [filha for filha in filhas_de(mapa, numero) if ocupada(filha)]
        for primeira, segunda in itertools.pairwise(irmas):
            if (primeira, segunda) in vistos:
                continue
            vistos.add((primeira, segunda))
            pares.append((primeira, segunda))
    return tuple(pares)


# ---------------------------------------------------------------------------
# A MESA DO MOTOR — a junção que faltava
# ---------------------------------------------------------------------------
#
# O motor do arranjo (``integrations/arranjo_da_mesa``) recebe a mesa como
# ARGUMENTO e não lê nada — é isso que o torna testável sem aparelho. Faltava
# quem montasse esse argumento a partir do que o produto de fato tem na mão: o
# desenho DELA (``MapaDaMesa``) e a leitura de AGORA (``Censo``). É a mesma
# junção que este módulo já faz para o número da entrada, e por isso mora aqui.

#: As chaves do que o desenho NÃO diz. São CONTRATO, nunca texto de tela: este
#: módulo não escreve frase (ver o cabeçalho), e quem as traduz para a palavra
#: dela é a janela do mapa.
#:
#: Elas existem porque a alternativa é pior: um campo que ninguém preencheu
#: cai no valor por omissão da dataclass do motor, e o motor não tem como
#: distinguir "é assim" de "ninguém disse". O juízo sai otimista e CALADO, que
#: é o defeito que a ``D-O-PAR-DE-ENTRADAS-VEM-DO-SYSFS`` fechou com todas as
#: letras: *"a linha do mapa DIZ isso em vez de calar"*.
LACUNA_PAR = "par"
LACUNA_POSICAO = "posicao"  # noqa-acento: chave de contrato ASCII, não texto de tela
LACUNA_VELOCIDADE = "velocidade"
LACUNA_REGIAO = "regiao"  # noqa-acento: chave de contrato ASCII, não texto de tela
LACUNA_ESPECIE = "especie"  # noqa-acento: chave de contrato ASCII, não texto de tela

#: ``(classe, subclasse, protocolo)`` do kernel -> a classe que o motor julga.
#:
#: É a MESMA régua de ``censo_do_barramento._especie`` e de
#: ``ordens_da_mesa._e_bluetooth``, e é a única fonte honesta que existe: o
#: ``product`` de dois dongles idênticos desta bancada diverge ("UB500 Adapter"
#: e "Bluetooth USB Adapter"), e adivinhar por texto é como se erra com
#: confiança.
_CLASSE_DO_MOTOR_POR_TRIPLA: dict[tuple[str, str, str], str] = {
    ("e0", "01", "01"): "bt",
    ("03", "01", "01"): "teclado",
    ("03", "01", "02"): "mouse",
}

#: Classe de vídeo (UVC). A webcam é a única espécie do motor que a classe
#: sozinha resolve.
_CLASSE_DE_VIDEO = "0e"

#: O sufixo que separa o hub que hospeda do número da entrada nele:
#: ``usb1-port5`` -> ``usb1``, ``3-1-port4`` -> ``3-1``. Não é uma terceira
#: cópia da forma do nó (ela já está em ``utils/maquina`` e em
#: ``entradas_do_gabinete``, declarada nos dois): ``MapaDaMesa`` valida a forma
#: ao carregar, e aqui só se corta o que já passou pelo validador.
_SUFIXO_DO_NO = "-port"


@dataclass(frozen=True)
class Bancada:
    """A mesa do motor **e** o que o desenho não disse para montá-la.

    Os dois juntos, num valor só, de propósito: quem recebe a mesa sem receber
    as lacunas não tem como saber que o juízo que ela produz está apoiado em
    campo que ninguém preencheu — e publicaria "aqui fica bem" com a mesma cara
    de quem mediu.
    """

    mesa: motor.Mesa
    lacunas: tuple[str, ...] = ()
    #: ``número -> de onde veio a velocidade`` (:data:`USB_PELO_APARELHO`,
    #: :data:`USB_DECLARADA`, :data:`USB_PELA_PLACA` ou ``""``) — da MESMA
    #: chamada da precedência que deu a ``usb`` de cada entrada
    #: (O-MAPA-QUE-ELA-CORRIGE-01, D-2609-A-VELOCIDADE-DELA-VENCE-A-PLACA). Fora
    #: do ``motor.Entrada`` de propósito: aquele é contrato do ouro.
    usb_de: Mapping[str, str] = field(default_factory=dict)


def mesa_do_motor(mapa: MapaDaMesa, censo: Censo) -> Bancada:
    """O desenho dela mais a leitura de agora, na forma que o motor entende.

    O que cada campo do motor recebe, e de onde:

    ==========================  ==================================================
    campo                       fonte
    ==========================  ==================================================
    ``Aparelho.classe``         a tripla do kernel (ver ``_CLASSE_DO_MOTOR_POR_TRIPLA``)
    ``Face.perto`` / ``.alto``  ``FaceDeclarada.perto`` / ``.alto`` — fato dela
    ``Entrada.par``             :func:`irmas_de` — o desenho dela, de duas em duas
    ``Entrada.filho``           :func:`filhas_de` — a extensão que ela declarou
    ``Entrada.onde``            ``arranjo_da_mesa.regiao_do_caminho``, do barramento
    ``Entrada.usb``             :func:`velocidade_da_entrada` — aparelho, ela, placa
    ``Entrada.pos``             **NINGUÉM** — ver ``LACUNA_POSICAO``
    ==========================  ==================================================

    ``leitura`` mapeia cada aparelho para o próprio caminho de barramento
    porque é ele que serve de ``id`` aqui: o motor foi portado de um mockup em
    que os aparelhos tinham apelido (``"bt-a"``), e o produto não tem apelido
    nenhum — tem o nome do kernel, que é único e é o que o mapa dela declara.

    **O Wi-Fi não tem classe, e isso é MEDIDO, não descuido:** o Archer T3U
    desta bancada declina de se classificar (``ff/ff/ff``). Nenhuma leitura o
    separa de um adaptador de rede com fio, e as regras de Wi-Fi do motor
    (o SuperSpeed no mesmo hub) valem só para rádio. Ele entra com classe
    vazia e a lacuna ``LACUNA_ESPECIE`` diz isso.

    **O BURACO TEM DOIS NÓS, E A LEITURA VALE PELOS DOIS** — 26/09/2026, foto
    dela: *«dentro do hub identificou errado são 4 dispositivos
    conectados»*. A entrada declara o caminho do lado USB 2.0 (``3-1.1.4``) e
    os nós dos DOIS lados (``3-1.1-port4``, ``4-1.1-port4``); o Wi-Fi que
    enumera no lado 3.0 (``4-1.1.4``) não casava com caminho nenhum e caía em
    «sem entrada». Agora o aparelho encaixado em qualquer nó de uma entrada é
    lido no caminho DELA (:func:`_leitura_pelas_entradas`), e o chip de dentro
    do hub e o gêmeo 3.0 do hub saem da lista de aparelhos — não são coisa que
    ela plugou.
    """
    controladores = controladores_do_censo(censo)
    leitura, fora = _leitura_pelas_entradas(mapa, censo.conectados(), controladores)
    aparelhos = tuple(
        _aparelho_do_motor(a) for a in censo.conectados() if a.nome_do_kernel not in fora
    )
    leitura = {aparelho.id: leitura[aparelho.id] for aparelho in aparelhos}
    declarado = {
        numero: caminho
        for numero, porta in sorted(mapa.portas.items())
        if (caminho := caminho_da_porta(porta, controladores))
    }

    # O esboço existe para uma pergunta só: qual é o caminho do hub externo.
    # `caminho_do_hub` só olha aparelhos e leitura, e é ele quem decide a
    # região de cada entrada — que é o que as faces ainda não têm.
    esboco = motor.Mesa(
        aparelhos=aparelhos, faces=(), mapa=declarado, leitura=leitura
    )
    caminho_hub = motor.caminho_do_hub(esboco)

    pares = irmas_de(mapa)
    velocidades = _velocidade_por_hub(censo)
    aparelhos_medidos = velocidades_dos_aparelhos(censo)
    lacunas: set[str] = set()
    origens: dict[str, str] = {}
    if any(not aparelho.classe for aparelho in aparelhos):
        lacunas.add(LACUNA_ESPECIE)
    if mapa.faces:
        # NÃO é condicional, e por isso não olha entrada nenhuma: `Entrada.pos`
        # é a posição do buraco na fileira do metal, e ela não existe em fonte
        # alguma — nem no `MapaDaMesa`, nem no censo, nem no `/sys`. Sem ela o
        # `_bonus_separacao` (+6 por posição de folga, teto 6) nunca dispara, e
        # dois adaptadores de rádio nas pontas opostas da fileira do hub
        # recebem o mesmo juízo de dois colados.
        lacunas.add(LACUNA_POSICAO)

    faces: list[motor.Face] = []
    for face in mapa.faces:
        numeros = _entradas_da_fileira_da_face(mapa, face.portas)
        regioes: dict[str, str | None] = {}
        for numero in _entradas_da_face(mapa, numeros):
            regioes[numero] = motor.regiao_do_caminho(
                declarado.get(numero), caminho_hub
            )
        conhecidas = [regiao for regiao in regioes.values() if regiao]
        if not conhecidas:
            lacunas.add(LACUNA_REGIAO)
        regiao_da_face = (
            "hub" if conhecidas.count("hub") > conhecidas.count("pc") else "pc"
        )
        entradas: list[motor.Entrada] = []
        for numero in numeros:
            entrada = _entrada_do_motor(
                mapa,
                numero,
                pares=pares,
                regiao=regioes.get(numero) or regiao_da_face,
                velocidades=velocidades,
                aparelhos=aparelhos_medidos,
                lacunas=lacunas,
                origens=origens,
            )
            filhas = filhas_de(mapa, numero)
            if filhas:
                # A PONTA É DA VELOCIDADE DE QUEM A HOSPEDA quando nada dela diz
                # outra coisa (O-MAPA-DAS-CONEXOES-NO-PRODUTO-02, 26/09/2026):
                # o extensor passivo não tem descritor, e a ponta que o editor
                # grava não tem nós. Sem isto, declarar algo na ponta a pintava
                # de USB 2.0 ao reler, com a mãe azul ao lado.
                filho = _entrada_do_motor(
                    mapa,
                    filhas[0],
                    pares=pares,
                    regiao=regioes.get(filhas[0]) or regiao_da_face,
                    velocidades=velocidades,
                    aparelhos=aparelhos_medidos,
                    lacunas=lacunas,
                    esticada=True,
                    usb_de_quem_hospeda=entrada.usb,
                    origens=origens,
                    origem_de_quem_hospeda=origens.get(numero, ""),
                )
                entrada = replace(entrada, filho=filho)
            entradas.append(entrada)
        faces.append(
            motor.Face(
                nome=face.nome,
                regiao=regiao_da_face,
                entradas=tuple(entradas),
                perto=face.perto,
                alto=face.alto,
            )
        )

    return Bancada(
        mesa=motor.Mesa(
            aparelhos=aparelhos,
            faces=tuple(faces),
            mapa=declarado,
            leitura=leitura,
        ),
        lacunas=tuple(sorted(lacunas)),
        usb_de=origens,
    )


# ---------------------------------------------------------------------------
# Interno
# ---------------------------------------------------------------------------


def _leitura_pelas_entradas(
    mapa: MapaDaMesa,
    conectados: Sequence[Aparelho],
    controladores: Mapping[int, str] | None = None,
) -> tuple[dict[str, str], frozenset[str]]:
    """``(aparelho -> caminho em que o mapa o lê, os hubs que não são aparelho)``.

    O caminho é o da entrada cujo buraco o aparelho ocupa, dos dois lados, ou o
    dele mesmo quando nenhuma entrada o declara. Um hub sai da lista em dois
    casos, e os dois são o mesmo plástico:

    * o CHIP DE DENTRO — ele hospeda entradas declaradas e não está em entrada
      nenhuma (``3-1.1`` e ``4-1.1``, no hub de dois chips desta bancada);
    * o GÊMEO 3.0 — ele cai no caminho de outro hub já lido (``4-1`` é o lado
      SuperSpeed do ``3-1``, na mesma entrada).

    Os caminhos de cada entrada são os deste boot
    (``utils/maquina.caminhos_da_porta``): pelo lugar que ela guarda, traduzido
    com os ``controladores`` de agora.
    """
    da_entrada: dict[str, str] = {}
    anfitrioes: set[str] = set()
    for _numero, porta in sorted(mapa.portas.items()):
        principal = caminho_da_porta(porta, controladores)
        for no in porta.nos:
            anfitrioes.add(no.rpartition(_SUFIXO_DO_NO)[0])
        for caminho in caminhos_da_porta(porta, controladores):
            if principal:
                da_entrada.setdefault(caminho, principal)
    leitura: dict[str, str] = {}
    fora: set[str] = set()
    lidos_de_hub: set[str] = set()
    # O lado 2.0 primeiro: é o caminho que a entrada declara, e o gêmeo que
    # sobra é o do outro barramento.
    for aparelho in sorted(conectados, key=lambda a: a.nome_do_kernel not in da_entrada.values()):
        nome = aparelho.nome_do_kernel
        caminho = da_entrada.get(nome, nome)
        leitura[nome] = caminho
        if not aparelho.e_hub:
            continue
        if (nome not in da_entrada and nome in anfitrioes) or caminho in lidos_de_hub:
            fora.add(nome)
        else:
            lidos_de_hub.add(caminho)
    return leitura, frozenset(fora)


def _aparelho_do_motor(aparelho: Aparelho) -> motor.Aparelho:
    """Um aparelho do censo na forma do motor — sem inventar o que falta.

    ``nome`` cai na espécie quando o descritor não traz produto: os TP-Link
    desta bancada publicam ``manufacturer`` com um espaço dentro, e espaço em
    branco é ausência.
    """
    return motor.Aparelho(
        id=aparelho.nome_do_kernel,
        tipo=aparelho.especie,
        nome=aparelho.produto.strip() or aparelho.especie,
        classe=_classe_do_motor(aparelho),
    )


def _classe_do_motor(aparelho: Aparelho) -> str:
    """A classe que o motor julga, ou ``""`` quando o kernel não disse.

    ``""`` é resposta, e é a resposta certa para o Archer T3U (``ff/ff/ff``) e
    para o DualSense por cabo (``03/00/00``, HID sem protocolo de arranque):
    nenhuma regra do motor fala deles, e forçá-los numa classe faria o quadrado
    julgar pelo aparelho errado.
    """
    if aparelho.e_hub:
        return "hub"
    achada = _CLASSE_DO_MOTOR_POR_TRIPLA.get(
        (aparelho.classe, aparelho.subclasse, aparelho.protocolo)
    )
    if achada:
        return achada
    return "webcam" if aparelho.classe == _CLASSE_DE_VIDEO else ""


def _entrada_do_motor(
    mapa: MapaDaMesa,
    numero: str,
    *,
    pares: Mapping[str, str],
    regiao: str,
    velocidades: Mapping[str, float],
    lacunas: set[str],
    aparelhos: Mapping[str, float] | None = None,
    esticada: bool = False,
    filho: motor.Entrada | None = None,
    usb_de_quem_hospeda: int | None = None,
    origens: dict[str, str] | None = None,
    origem_de_quem_hospeda: str = "",
) -> motor.Entrada:
    """Uma entrada do desenho na forma do motor, anotando o que faltou.

    ``usb_de_quem_hospeda`` é a velocidade da entrada em que o extensor está:
    a ponta dele a herda quando nem os nós nem ela dizem outra coisa — e a
    origem junto (``origem_de_quem_hospeda``). ``origens`` recebe de onde veio
    a velocidade desta entrada (:attr:`Bancada.usb_de`).
    """
    par = pares.get(numero)
    if par is None and not esticada:
        # A entrada por extensão NÃO tem irmã por desenho (o cabo de um metro a
        # põe longe de todo mundo), e essa ausência não é lacuna.
        lacunas.add(LACUNA_PAR)
    declarada = mapa.portas.get(numero)
    rapido, origem = _velocidade_do_no(
        () if declarada is None else declarada.nos,
        velocidades,
        None if declarada is None else declarada.usb,
        aparelhos,
    )
    if rapido is None and usb_de_quem_hospeda is not None:
        rapido, origem = usb_de_quem_hospeda == 3, origem_de_quem_hospeda
    if rapido is None:
        lacunas.add(LACUNA_VELOCIDADE)
    if origens is not None:
        origens[numero] = origem
    return motor.Entrada(
        n=numero,
        usb=3 if rapido else 2,
        onde="hub" if regiao == "hub" else "pc",
        par=par,
        pos=None,
        esticada=esticada,
        filho=filho,
    )


def _entradas_da_fileira_da_face(
    mapa: MapaDaMesa, numeros: Sequence[str]
) -> tuple[str, ...]:
    """Os números da fileira desta face, sem repetir — a regra de ``irmas_de``.

    A entrada repetida conta UMA vez, pela primeira aparição. É a mesma regra
    do pareamento, e as duas precisam concordar: se a fileira contasse a
    repetição e o pareamento não, uma entrada ficaria sem irmã só por estar
    desenhada duas vezes.
    """
    achados: list[str] = []
    vistos: set[str] = set()
    for numero in numeros:
        if numero in vistos:
            continue
        vistos.add(numero)
        achados.append(numero)
    return tuple(achados)


def _velocidade_por_hub(censo: Censo) -> dict[str, float]:
    """``hub -> Mbps``, para os hubs-raiz e para os hubs da mesa.

    É o que responde se um buraco é azul: o nome do nó declarado carrega o hub
    em que ele mora (``usb3-port1``, ``4-1-port2``), e o lado SuperSpeed de um
    hub de dois chips enumera num barramento próprio.
    """
    achadas = {
        barramento.nome_do_kernel: barramento.velocidade_mbps
        for barramento in censo.barramentos
    }
    for aparelho in censo.aparelhos:
        if aparelho.e_hub:
            achadas[aparelho.nome_do_kernel] = aparelho.velocidade_mbps
    return achadas


def _rapido_do_no(
    nos: Sequence[str],
    velocidades: Mapping[str, float],
    declarada: int | None = None,
    aparelhos: Mapping[str, float] | None = None,
) -> bool | None:
    """O buraco declarado alcança SuperSpeed? ``None`` = não deu para saber.

    O que a PLACA diz é a mesma régua de ``entradas_do_gabinete.Furo.rapido``,
    e de propósito: a velocidade mora no HUB que hospeda, nunca no nó. ``None``
    é a resposta de quem nunca abriu a janela de calibração. Mas a placa não
    tem a última palavra — ver :func:`velocidade_da_entrada`: a velocidade que
    ela ``declarada`` vence o firmware, e um aparelho USB 3 enumerado num dos
    ``nos`` (``aparelhos``: nome do kernel -> Mbps) vence os dois.
    """
    return _velocidade_do_no(nos, velocidades, declarada, aparelhos)[0]


def _velocidade_do_no(
    nos: Sequence[str],
    velocidades: Mapping[str, float],
    declarada: int | None = None,
    aparelhos: Mapping[str, float] | None = None,
) -> tuple[bool | None, str]:
    """:func:`_rapido_do_no` com a origem: ``(é USB 3?, de onde veio)``."""
    lidas = [
        velocidades[hub]
        for hub in (no.rpartition(_SUFIXO_DO_NO)[0] for no in nos)
        if hub in velocidades
    ]
    placa: bool | None
    if not lidas or all(valor <= 0 for valor in lidas):
        placa = None
    else:
        placa = any(valor >= VELOCIDADE_SUPERSPEED_MBPS for valor in lidas)
    return velocidade_da_entrada(
        placa, declarada, _aparelho_usb3_nos_nos(nos, aparelhos or {})
    )


#: DE ONDE VEIO A VELOCIDADE DE UMA ENTRADA — O-MAPA-DAS-CONEXOES-NO-PRODUTO-01,
#: 26/09/2026. Chaves de máquina, na ordem da certeza: o aparelho USB 3 que
#: enumerou nela, o que ela disse, o par que a placa publica.
USB_PELO_APARELHO = "aparelho"
USB_DECLARADA = "declarada"
USB_PELA_PLACA = "placa"


def velocidade_da_entrada(
    placa: bool | None, declarada: int | None, aparelho_usb3: bool = False
) -> tuple[bool | None, str]:
    """``(é USB 3?, de onde veio)`` — o dono ÚNICO da precedência.

    O ``peer`` do ``/sys`` diz o que o FIRMWARE anuncia, e não o conector.
    MEDIDO na mesa em que isto nasceu (26/09/2026, com ela olhando o gabinete):
    as duas USB 2.0 pretas de trás têm ``peer`` — o controlador tem as vias
    SuperSpeed, e a placa só ligou o conector 2.0 —, e a frente, que o gabinete
    chama de 3.0, está num conector 2.0 da placa (sem ``peer``: ali o firmware
    acerta). Quem erra é o par que o firmware publica, e por isso:

    1. ``aparelho_usb3`` — um aparelho enumerado a 5000M+ na entrada é
       medição, e nada o contradiz;
    2. ``declarada`` (2 ou 3) — o que ela disse no editor vence o firmware;
    3. ``placa`` — o que sobra, e ``None`` é "não sei".

    O motor pergunta por :func:`_rapido_do_no`; o Mapear
    (``entrada_a_entrada.ler_o_mapa``) pergunta aqui com o que ele mediu.
    """
    if aparelho_usb3:
        return True, USB_PELO_APARELHO
    if declarada in (2, 3):
        return declarada == 3, USB_DECLARADA
    return placa, (USB_PELA_PLACA if placa is not None else "")


def velocidades_dos_aparelhos(censo: Censo) -> dict[str, float]:
    """``nome do kernel -> Mbps`` de tudo que enumerou — o lado de :func:`velocidade_da_entrada`
    que é medição."""
    return {a.nome_do_kernel: a.velocidade_mbps for a in censo.conectados()}


def _aparelho_usb3_nos_nos(nos: Sequence[str], aparelhos: Mapping[str, float]) -> bool:
    """Algum aparelho encaixado num destes nós enumerou a 5000M ou mais?"""
    from hefesto_dualsense4unix.utils.lugar import caminho_do_no

    return any(
        aparelhos.get(caminho_do_no(no), 0.0) >= VELOCIDADE_SUPERSPEED_MBPS for no in nos
    )


def aparelho_usb3_na_entrada(nos: Sequence[str], censo: Censo) -> bool:
    """O lado «aparelho» de :func:`velocidade_da_entrada`, pelos NÓS da entrada.

    O Mapear perguntava pelo primeiro aparelho que achava nos nós — no hub de
    dois chips, o lado 2.0 (480M) — e o arranjo, por todos: a mesma entrada
    saía «É o que a placa-mãe diz.» num e «Um aparelho está nela» no outro
    (O-MAPA-QUE-ELA-CORRIGE-01, D4: uma régua só).
    """
    return _aparelho_usb3_nos_nos(nos, velocidades_dos_aparelhos(censo))


def _caminhos_do_censo(censo: Censo) -> frozenset[str]:
    """Os ``nome_do_kernel`` de tudo que está plugado agora, sem os hubs-raiz."""
    return frozenset(a.nome_do_kernel for a in censo.conectados())


def _entradas_da_fileira(mapa: MapaDaMesa) -> tuple[str, ...]:
    """Os números das faces, na ordem do desenho e sem repetir."""
    achados: list[str] = []
    vistos: set[str] = set()
    for face in mapa.faces:
        for numero in face.portas:
            if numero in vistos:
                continue
            vistos.add(numero)
            achados.append(numero)
    return tuple(achados)


def _entradas_da_face(mapa: MapaDaMesa, numeros: Sequence[str]) -> tuple[str, ...]:
    """As entradas de uma face MAIS as que nascem de extensão nelas.

    A entrada por extensão não está na fileira — ela desenha dentro do quadrado
    da entrada que a hospeda —, mas pertence à face do mesmo jeito: o cabo sai
    dali. Deixá-la de fora da coerência esconderia justamente o aparelho que
    mais confunde o barramento.
    """
    achadas: list[str] = []
    for numero in numeros:
        achadas.append(numero)
        achadas.extend(filhas_de(mapa, numero))
    return tuple(achadas)


# ---------------------------------------------------------------------------
# O QUE O METAL DE UMA PORTA É — A-08-UM-MAPEAR-SO-01 (25/09/2026)
# ---------------------------------------------------------------------------
#
# O pedido dela: *«carrega a informação que medimos»* — cada porta do mapa diz
# se é USB 2.0 ou 3.0, de que controlador e de que hub ela pende, quantos -71
# ela deu, e se o que está nela é o adaptador Bluetooth da placa ou um dongle.
# Tudo isso é LEITURA do buraco, e por isso não vai para o ``maquina.json``: o
# disco guarda o que só ela sabe (o número, o nome, o lugar no gabinete) e a
# identidade do buraco (o lugar e os nós); o resto se lê de novo a cada pedido,
# e um hub trocado de lugar nunca deixa no disco um «3.0» que já não é verdade.
# A junção mora aqui porque é junção pura: quem lê o ``/sys`` é quem chama
# (``entrada_a_entrada.ler_o_mapa``), com a raiz desviável.

#: A resposta de «esta porta alcança SuperSpeed?», em chave de máquina.
USB_3 = "3.0"
USB_2 = "2.0"

#: O adaptador Bluetooth encaixado na porta: o da PLACA (módulo interno num
#: conector que ninguém alcança de fora — ``connect_type`` ``hardwired``) ou
#: um DONGLE (a entrada é ``hotplug``, ou ele pende de um hub que não está
#: num conector interno). Chaves de máquina. O rádio direto numa porta-raiz
#: ``unknown`` NÃO é nenhum dos dois: numa máquina sem a tabela ACPI das
#: portas toda entrada diz ``unknown``, a de gabinete e a interna — e ali o
#: produto responde "não sei" (``bluetooth == ""`` com ``e_bluetooth``).
BLUETOOTH_DA_PLACA = "placa"
BLUETOOTH_DONGLE = "dongle"

#: A tripla de classe do rádio Bluetooth — a mesma de
#: ``_CLASSE_DO_MOTOR_POR_TRIPLA`` e de ``censo_do_barramento._especie``.
_TRIPLA_DO_BLUETOOTH = ("e0", "01", "01")

#: O ``connect_type`` do conector interno da placa, e o da entrada que se
#: alcança de fora (o mesmo ``_ENCAIXE_DE_FORA`` do ``entrada_a_entrada``).
_ENCAIXE_INTERNO = "hardwired"
_ENCAIXE_DE_FORA = "hotplug"


@dataclass(frozen=True)
class FatosDoBuraco:
    """O que o ``/sys`` diz de UM buraco, cheio ou vazio — nada declarado.

    ``usb`` é :data:`USB_3`, :data:`USB_2` ou ``""`` (não deu para saber).
    ``hub`` é o nome do kernel do hub de que o buraco pende (``3-4``), ``""``
    quando ele é do próprio computador. ``storm`` é ``None`` quando o -71 não
    foi medido — que é diferente de zero. ``e_bluetooth`` diz que o aparelho é
    um rádio Bluetooth; ``bluetooth`` diz de onde ele é (placa ou dongle), e
    ``""`` com ``e_bluetooth`` é "não sei de onde".
    """

    usb: str = ""
    controlador: str = ""
    hub: str = ""
    hub_produto: str = ""
    encaixe: str = ""
    ocupada: bool | None = None
    aparelho: str = ""
    especie: str = ""
    produto: str = ""
    e_dualsense: bool = False
    e_bluetooth: bool = False
    bluetooth: str = ""
    storm: int | None = None


def fatos_do_buraco(
    nos: Sequence[str],
    entradas: Sequence[object],
    censo: Censo,
    controladores: Mapping[int, str],
    *,
    storm: Mapping[str, int] | None = None,
) -> FatosDoBuraco:
    """Os fatos medidos de um buraco — pelos NÓS dele, que existem vazios.

    ``entradas`` são os ``entradas_do_gabinete.NoDeEntrada`` da leitura de
    agora (tipados como ``object`` para este módulo não depender de quem lê
    o ``/sys``); só os deste buraco contam. ``storm`` é ``{caminho do kernel:
    quantos -71}`` do ``exame_da_mesa.storm_por_porta`` — a porta que o log
    nomeia é o aparelho que estava no buraco, e o caminho do aparelho é o
    ``caminho_do_no`` do nó.
    """
    # Import no corpo, e não no topo: a linha a mais no topo deslocaria as
    # citações `mapa_das_portas.py:N` que a aba 08 faz deste arquivo.
    from hefesto_dualsense4unix.utils.lugar import caminho_do_no

    meus = [e for e in entradas if getattr(e, "no", "") in set(nos)]
    velocidades = [float(getattr(e, "velocidade_mbps", 0.0) or 0.0) for e in meus]
    if any(v >= VELOCIDADE_SUPERSPEED_MBPS for v in velocidades):
        usb = USB_3
    elif velocidades and not all(v <= 0 for v in velocidades):
        usb = USB_2
    else:
        usb = ""

    # O lado 2.0 primeiro: é onde o DualSense e os dongles enumeram.
    ordenados = sorted(
        (no for no in nos if caminho_do_no(no)),
        key=lambda no: int(caminho_do_no(no).partition("-")[0]),
    )
    controlador = ""
    hub = ""
    for no in ordenados:
        busnum = int(caminho_do_no(no).partition("-")[0])
        controlador = controlador or controladores.get(busnum, "")
        dono = no.rpartition(_SUFIXO_DO_NO)[0]
        if dono and not dono.startswith("usb") and not hub:
            hub = dono
    por_nome = {a.nome_do_kernel: a for a in censo.aparelhos}
    hub_produto = por_nome[hub].produto.strip() if hub in por_nome else ""

    estados = [str(getattr(e, "estado", "") or "") for e in meus]
    dentro = next((str(getattr(e, "aparelho", "")) for e in meus if getattr(e, "aparelho", "")), "")
    if dentro:
        ocupada: bool | None = True
    elif meus and all(estado == "not attached" for estado in estados):
        ocupada = False
    else:
        ocupada = None
    encaixe = next((str(getattr(e, "tipo_de_encaixe", "")) for e in meus
                    if getattr(e, "tipo_de_encaixe", "")), "")

    aparelho = por_nome.get(dentro)
    e_bluetooth = aparelho is not None and (
        aparelho.classe, aparelho.subclasse, aparelho.protocolo
    ) == _TRIPLA_DO_BLUETOOTH
    bluetooth = _origem_do_bluetooth(nos, entradas) if e_bluetooth else ""

    medido: int | None = None
    caminhos = {caminho_do_no(no) for no in nos} | ({dentro} if dentro else set())
    caminhos.discard("")
    if storm is not None and caminhos:
        # Sem caminho nenhum (a porta de um hub desligado, sem nós lidos), o
        # log não tem a quem ser atribuído: é "não sei", e não zero.
        medido = sum(storm.get(caminho, 0) for caminho in caminhos)

    return FatosDoBuraco(
        usb=usb,
        controlador=controlador,
        hub=hub,
        hub_produto=hub_produto,
        encaixe=encaixe,
        ocupada=ocupada,
        aparelho=dentro,
        especie="" if aparelho is None else aparelho.especie,
        produto="" if aparelho is None else aparelho.produto.strip(),
        e_dualsense=aparelho is not None and aparelho.vid.lower() == "054c",
        e_bluetooth=e_bluetooth,
        bluetooth=bluetooth,
        storm=medido,
    )


def _origem_do_bluetooth(nos: Sequence[str], entradas: Sequence[object]) -> str:
    """Placa, dongle ou ``""`` — pelo ``connect_type`` do buraco e de quem o hospeda.

    1. o buraco diz ``hardwired``: o conector interno da placa;
    2. o buraco, ou o de um hub acima dele, diz ``hotplug``: alguém encaixou
       aquilo de fora — é dongle, mesmo que o hub não publique o encaixe das
       entradas dele (hub externo não tem tabela ACPI);
    3. atrás de hub, sem nenhum ``hardwired`` na corrente: dongle. O rádio da
       placa (a placa M.2 de Wi-Fi e Bluetooth, o módulo soldado) vai nos
       pinos de uma porta-raiz, não atrás de um hub que o firmware nem
       descreve. Medido na mesa dela em 25/09/2026: toda entrada diz
       ``unknown``, e os três rádios estão atrás do hub da mesa — são dongles;
    4. o resto é "não sei": o rádio direto numa porta-raiz ``unknown`` (numa
       máquina sem a tabela ACPI toda entrada diz isso, a de gabinete e a
       interna), e o que pende de um hub INTERNO (num conector ``hardwired``),
       que hospeda tanto o rádio da placa quanto o painel da frente.
    """
    por_no = {str(getattr(e, "no", "")): e for e in entradas}
    alvo = set(nos)
    vistos: set[str] = set()
    degraus = 0
    interno = False
    while alvo and not alvo <= vistos:
        vistos |= alvo
        tipos = {
            str(getattr(por_no[no], "tipo_de_encaixe", "") or "")
            for no in alvo
            if no in por_no
        }
        if _ENCAIXE_INTERNO in tipos:
            if not degraus:
                return BLUETOOTH_DA_PLACA
            interno = True
        if _ENCAIXE_DE_FORA in tipos:
            return BLUETOOTH_DONGLE
        hubs = {
            dono
            for no in alvo
            if (dono := no.rpartition(_SUFIXO_DO_NO)[0]) and not dono.startswith("usb")
        }
        if not hubs:
            break
        degraus += 1
        alvo = {
            no
            for no, e in por_no.items()
            if str(getattr(e, "aparelho", "") or "") in hubs
        }
        if not alvo:
            return ""  # o buraco do hub não foi lido: não sei o que há acima
    return BLUETOOTH_DONGLE if degraus and not interno else ""


def _serial_do_no(no: str) -> str:
    """O ``serial`` de um nó USB; ``""`` em qualquer erro — sysfs some sob a mão.

    É o único leitor de arquivo deste módulo, e ele existe para ser trocado por
    um dublê em teste.
    """
    try:
        with open(
            os.path.join(no, _ARQUIVO_DO_SERIAL), encoding="utf-8", errors="replace"
        ) as arquivo:
            return arquivo.read()
    except OSError:
        return ""


def serial_do_no(no: str) -> str:
    """O ``serial`` de um nó USB, para a identidade do aparelho no mapa das conexões.

    O-MAPA-DAS-CONEXOES-NO-PRODUTO-02. Quem o lê para a página
    (``interface/arranjo_desta_maquina.identidades``) o resume com sal antes
    de qualquer coisa: ele não vai à tela nem ao disco. Lê o ``/sys``, então
    nunca no fio da janela.
    """
    return _serial_do_no(no)


__all__ = [
    "BLUETOOTH_DA_PLACA",
    "BLUETOOTH_DONGLE",
    "LACUNA_ESPECIE",
    "LACUNA_PAR",
    "LACUNA_POSICAO",
    "LACUNA_REGIAO",
    "LACUNA_VELOCIDADE",
    "USB_2",
    "USB_3",
    "USB_DECLARADA",
    "USB_PELA_PLACA",
    "USB_PELO_APARELHO",
    "Bancada",
    "FatosDoBuraco",
    "Resumo",
    "aparelho_usb3_na_entrada",
    "caminho_de",
    "fatos_do_buraco",
    "filhas_de",
    "irmas_de",
    "mesa_do_motor",
    "porta_de",
    "portas_livres",
    "resumo_do_mapa",
    "serial_do_no",
    "velocidade_da_entrada",
    "velocidades_dos_aparelhos",
    "vizinhas_de_verdade",
]
