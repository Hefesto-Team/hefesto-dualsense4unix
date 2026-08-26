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

**Não vai buscar endereço de Bluetooth.** :func:`porta_do_adaptador` RECEBE os
endereços que o BlueZ já reportou, em vez de abrir D-Bus: ``integrations/`` não
pode passar a depender do barramento de sistema, que o manifesto Flatpak não
permite.

**Não guarda serial em lugar nenhum.** O serial USB dos adaptadores TP-Link
desta bancada É o endereço Bluetooth deles (medido em 24/08/2026, três
aparelhos), e é essa coincidência que casa as duas leituras. Mas serial
identifica a unidade dela tão bem quanto o MAC (``scripts/check_anonymity.sh``):
ele é lido dentro de :func:`porta_do_adaptador`, usado para casar, e some. Nunca
vai para a tela, nunca para o ``maquina.json``, nunca para um PNG.

**NÃO VERIFICADO:** que serial-é-endereço valha fora destes TP-Link. O Wi-Fi
desta mesma bancada responde ``123456``, o que já prova que não é regra
universal. Por isso a regra é casar **quando o serial tem doze hex E bate com um
endereço que o BlueZ já reportou**; nos outros casos a resposta é a ausência —
"não sei em qual entrada" —, nunca um palpite.
"""

from __future__ import annotations

import itertools
import os
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    Aparelho,
    Censo,
    cadeia_de_hubs,
)
from hefesto_dualsense4unix.integrations.mesa_de_radio import Adaptador
from hefesto_dualsense4unix.utils.maquina import MapaDaMesa

#: Doze hex, que é a forma em que o serial USB de um TP-Link UB500 carrega o
#: endereço Bluetooth do aparelho. Qualquer outra forma — o ``123456`` do
#: Archer T3U desta bancada, por exemplo — não casa com endereço nenhum, e a
#: resposta é a ausência.
_DOZE_HEX = re.compile(r"^[0-9a-f]{12}$")

#: Onde mora o serial de um nó USB, relativo ao caminho do nó.
_ARQUIVO_DO_SERIAL = "serial"

@dataclass(frozen=True)
class Incoerencia:
    """Uma entrada declarada numa face que não pendura onde a face pendura.

    É o cálculo, e só ele: a FRASE que a tela mostra é de quem escreve a ordem
    de serviço. Aqui ficam os quatro fatos de que aquela frase precisa.

    ``ancora`` é o hub de que a maioria das entradas daquela face pendura — o
    que o desenho chama de "o cabo da face". Ele não é declarado: sai da
    leitura, contando de que hub as entradas da face penduram.
    """

    face: str
    porta: str
    caminho: str
    ancora: str


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


def porta_de(mapa: MapaDaMesa, caminho: str) -> str | None:
    """O número da entrada em que este caminho de barramento está declarado.

    ``None`` quando ela não declarou este caminho — que é a resposta certa e a
    mais comum: quem nunca desenhou a mesa não tem número nenhum, e a tela
    volta a falar o caminho do sistema em vez de inventar um número.

    Caminho vazio (o adaptador embutido, que não pendura em USB nenhum) nunca
    casa com nada: ele não está em entrada alguma.
    """
    if not caminho:
        return None
    for numero, porta in sorted(mapa.portas.items()):
        if porta.caminho == caminho:
            return numero
    return None


def caminho_de(mapa: MapaDaMesa, porta: str) -> str | None:
    """O caminho de barramento declarado para esta entrada, ou ``None``."""
    declarada = mapa.portas.get(porta)
    return None if declarada is None else declarada.caminho


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
    colocados = sum(
        1
        for declarada in mapa.portas.values()
        if declarada.caminho and declarada.caminho in presentes
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
    livres: list[str] = []
    for numero in _entradas_da_fileira(mapa):
        if filhas_de(mapa, numero):
            continue
        caminho = caminho_de(mapa, numero)
        if caminho and caminho in presentes:
            continue
        livres.append(numero)
    return tuple(livres)


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

    def ocupada(numero: str) -> bool:
        caminho = caminho_de(mapa, numero)
        return bool(caminho) and caminho in presentes

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


def incoerencias(mapa: MapaDaMesa, censo: Censo) -> tuple[Incoerencia, ...]:
    """As entradas que a face diz hospedar e o barramento diz que não.

    A âncora de uma face é o hub de que a MAIORIA das entradas dela pendura —
    o cabo daquela face, deduzido em vez de declarado. Uma face cujas entradas
    penduram direto na placa (a frente e a traseira de um gabinete) não tem
    âncora, e uma face sem âncora nunca acusa ninguém.

    **A EXCEÇÃO DO HUB DE DOIS BARRAMENTOS, e ela é o motivo desta função ter
    tarefa própria.** O hub desta bancada é UM plástico com DOIS chips: o lado
    USB 2.0 enumera em ``3-1``/``3-1.1`` e o lado USB 3.0 em ``4-1``/``4-1.1``.
    Um aparelho no buraco azul pendura em ``4-1.1`` enquanto os vizinhos dele
    penduram em ``3-1`` — e a comparação de prefixo crua acusaria a mesa dela
    de estar errada, que é uma acusação FALSA contra quem declarou certo. Dois
    caminhos que diferem apenas no barramento, cujos barramentos pendem do
    mesmo controlador PCI, são o mesmo plástico.
    """
    por_caminho = {a.no: a for a in censo.aparelhos}
    caminho_por_nome = {a.nome_do_kernel: a.no for a in censo.aparelhos}
    achadas: list[Incoerencia] = []
    for face in mapa.faces:
        numeros = _entradas_da_face(mapa, face.portas)
        cadeias = {
            numero: _cadeia(censo, caminho_por_nome, caminho_de(mapa, numero))
            for numero in numeros
        }
        ancora = _ancora_da_face(cadeias.values())
        if not ancora:
            continue
        for numero in numeros:
            cadeia = cadeias[numero]
            if not cadeia:
                caminho = caminho_de(mapa, numero)
                if not caminho or caminho not in caminho_por_nome:
                    # Entrada vazia, ou aparelho que saiu da mesa: não há o que
                    # acusar. O mapa continua valendo para quando ele voltar.
                    continue
            if ancora in cadeia:
                continue
            if _mesmo_plastico_em_dois_barramentos(ancora, cadeia, por_caminho):
                continue
            achadas.append(
                Incoerencia(
                    face=face.nome,
                    porta=numero,
                    caminho=caminho_de(mapa, numero) or "",
                    ancora=_nome_do_kernel(por_caminho, ancora),
                )
            )
    return tuple(achadas)


def porta_do_adaptador(
    mapa: MapaDaMesa,
    adaptadores: Sequence[Adaptador],
    enderecos_do_bluez: Iterable[str],
    *,
    ler_serial: Callable[[str], str] | None = None,
) -> dict[str, str]:
    """``{endereço do adaptador: número da entrada}`` — o casamento do serial.

    É a ponte que faltava entre ``radio_da_mesa``, que chaveia por **endereço
    do adaptador**, e ``mesa_de_radio``, que sabe **onde o adaptador está** e
    não sabe o endereço (medido: ``/sys/class/bluetooth/hci0/`` não tem arquivo
    ``address``). Com ela, e sem root, sem ``busctl``, sem D-Bus de sistema e
    sem o Flatpak reclamar, o produto passa a poder dizer em qual entrada o
    Jogador 2 está.

    O casamento é conservador de propósito: só entra no resultado o adaptador
    cujo serial tem doze hex **E** bate com um endereço que o BlueZ já
    reportou **E** cujo caminho ela declarou no mapa. Falhou qualquer um dos
    três, a resposta é a ausência — "não sei em qual entrada" —, que é o que a
    tela tem de dizer em vez de chutar.

    O serial não sobrevive a esta função: é lido, comparado e descartado.
    """
    leitor = _serial_do_no if ler_serial is None else ler_serial
    conhecidos = {
        _endereco_normalizado(endereco)
        for endereco in enderecos_do_bluez
        if _endereco_normalizado(endereco)
    }
    achados: dict[str, str] = {}
    for adaptador in adaptadores:
        if not adaptador.no or not adaptador.caminho:
            continue
        endereco = _endereco_do_serial(leitor(adaptador.no))
        if not endereco or endereco not in conhecidos:
            continue
        numero = porta_de(mapa, adaptador.caminho)
        if numero is None:
            continue
        achados[endereco] = numero
    return achados


# ---------------------------------------------------------------------------
# Interno
# ---------------------------------------------------------------------------


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


def _cadeia(
    censo: Censo, caminho_por_nome: dict[str, str], caminho: str | None
) -> tuple[str, ...]:
    """Os hubs acima do caminho declarado, do mais perto ao mais longe."""
    if not caminho:
        return ()
    no = caminho_por_nome.get(caminho)
    if no is None:
        return ()
    return cadeia_de_hubs(censo, no)


def _ancora_da_face(cadeias: Iterable[tuple[str, ...]]) -> str:
    """O hub de que a MAIORIA das entradas da face pendura — ``""`` se nenhum.

    O empate se resolve pelo hub mais EXTERNO, o que está mais longe dos
    aparelhos: uma face é um plástico inteiro, não um dos chips dele. Sem esse
    critério, o hub de dois chips desta bancada faria a âncora oscilar entre
    ``3-1`` e ``3-1.1`` conforme quantos aparelhos estivessem em cada chip.
    """
    contagem: dict[str, int] = {}
    profundidade: dict[str, int] = {}
    for cadeia in cadeias:
        for altura, hub in enumerate(cadeia):
            contagem[hub] = contagem.get(hub, 0) + 1
            profundidade[hub] = max(profundidade.get(hub, 0), altura)
    if not contagem:
        return ""
    return max(contagem, key=lambda hub: (contagem[hub], profundidade[hub], hub))


def _mesmo_plastico_em_dois_barramentos(
    ancora: str,
    cadeia: Sequence[str],
    por_caminho: dict[str, Aparelho],
) -> bool:
    """A âncora e algum hub desta cadeia são os dois lados do MESMO hub?

    A assinatura, medida nesta bancada: mesmo ``devpath``, ``busnum``
    diferente, e o mesmo controlador PCI nos dois. O hub USB 2.1/3.1 dela
    enumera ``3-1`` no lado 2.0 e ``4-1`` no lado 3.0, e os dois barramentos
    pendem de ``0000:0c:00.3``.
    """
    de_la = por_caminho.get(ancora)
    if de_la is None:
        return False
    for hub in cadeia:
        deste = por_caminho.get(hub)
        if deste is None:
            continue
        if deste.devpath != de_la.devpath:
            continue
        if deste.busnum == de_la.busnum:
            continue
        if deste.controlador_pci and deste.controlador_pci == de_la.controlador_pci:
            return True
    return False


def _nome_do_kernel(por_caminho: dict[str, Aparelho], no: str) -> str:
    aparelho = por_caminho.get(no)
    return "" if aparelho is None else aparelho.nome_do_kernel


def _endereco_do_serial(serial: str) -> str:
    """Os doze hex do serial USB virando endereço — ``""`` quando não é um.

    MEDIDO em 24/08/2026 nos três TP-Link desta bancada: os doze hex do serial
    USB são os seis octetos do endereço Bluetooth do adaptador. E medido o
    contraexemplo no mesmo barramento: o Archer T3U responde ``123456``, que
    não é endereço de nada.
    """
    limpo = serial.strip().replace(":", "").replace("-", "").lower()
    if not _DOZE_HEX.match(limpo):
        return ""
    return ":".join(limpo[posicao : posicao + 2] for posicao in range(0, 12, 2))


def _endereco_normalizado(endereco: str) -> str:
    """O endereço do BlueZ em minúsculas com dois-pontos — ``""`` se não for um."""
    return _endereco_do_serial(endereco)


def _serial_do_no(no: str) -> str:
    """O ``serial`` de um nó USB; ``""`` em qualquer erro — sysfs some sob a mão.

    É o único leitor de arquivo deste módulo, e ele existe para ser trocado por
    um dublê em teste. O valor que ele devolve **não sai** de
    :func:`porta_do_adaptador`.
    """
    try:
        with open(
            os.path.join(no, _ARQUIVO_DO_SERIAL), encoding="utf-8", errors="replace"
        ) as arquivo:
            return arquivo.read()
    except OSError:
        return ""


__all__ = [
    "Incoerencia",
    "Resumo",
    "caminho_de",
    "filhas_de",
    "incoerencias",
    "irmas_de",
    "porta_de",
    "porta_do_adaptador",
    "portas_livres",
    "resumo_do_mapa",
    "vizinhas_de_verdade",
]
