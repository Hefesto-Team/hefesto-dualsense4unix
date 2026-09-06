"""ordens_da_mesa.py — o que eu vi, por que importa, e o que dá para fazer.

O PROBLEMA QUE ESTE MÓDULO RESOLVE
-----------------------------------

O produto já sabia achar cinco problemas e já tinha escrito a cura de quatro
deles — e a cura só chegava à tela dentro de um ``set_tooltip_text``. Quem não
passasse o mouse por cima da palavra certa nunca descobria o que fazer. É a
``A-CASA-SABE-E-O-PRODUTO-NAO-FAZ`` na forma mais barata de consertar: o dado
está pronto, falta a tela pronunciá-lo.

Uma **ordem de serviço** é o formato que pronuncia. Ela tem quatro partes, e
nenhuma é opcional:

* o **imperativo** — "Mova o aparelho de 5 Gbps para uma entrada do computador";
* **o que eu vi aqui** — a medição, nesta máquina, agora;
* **por que importa** — a consequência;
* **o ganho esperado** — e, quando ele não foi medido, a linha DIZ que não foi.

A TERCEIRA LINHA É SEMPRE VISÍVEL — ``D-LINHA-DO-GANHO-NAO-MEDIDO``
--------------------------------------------------------------------

A linha que confessa que o ganho não foi medido **nunca** mora só no tooltip.
Ela é o que impede raciocínio de se vestir de medição: uma ordem que manda mover
um aparelho sem dizer quanto se ganha é uma ordem honesta; a mesma ordem com o
ganho escondido é um palpite com cara de laudo.

"NÃO MEDI" E "VOCÊ NÃO DECLAROU" SÃO PALAVRAS DIFERENTES
---------------------------------------------------------

``D-O-QUE-O-PRODUTO-DIZ-SEM-SABER``: confundir as duas é o defeito de forma F7
desta casa — o estado vazio se disfarçando de resposta. :data:`NAO_MEDI` é
"olhei e não sei quanto"; :data:`NAO_DECLARADO` é "só você sabe, e você ainda
não me disse". As duas constantes existem para que a diferença seja testável, e
há teste que reprova se elas colapsarem numa frase só.

O SELO DE PROCEDÊNCIA
----------------------

Toda :class:`Linha` carrega de onde ela veio, e o selo é DADO, nunca string de
tela: ``medido-aqui``, ``derivado-da-conta``, ``especificacao-de-terceiro``. O
terceiro **exige nomear o terceiro** — autoridade anônima é exatamente como
raciocínio se veste de medição, e é o motivo de o selo existir. Há portão que
varre este arquivo por AST e reprova ``Linha`` sem selo válido, ou selo de
terceiro sem ``fonte``.

Por que vocabulário novo em vez de reusar o ``de_onde_sei`` do mapa de canais:
as duas respondem perguntas diferentes. O CSV responde *"como sei que este canal
funciona"*; a ordem responde *"como sei que este conselho vale"*. Onde há
correspondência ela existe (``medido-aqui`` ↔ ``medido``,
``especificacao-de-terceiro`` ↔ ``afirmado-no-doc``); ``derivado-da-conta`` não
tem par lá, porque o CSV não faz aritmética.

A DISCIPLINA — a mesma de ``exame_da_mesa.py`` e ``censo_do_barramento.py``
----------------------------------------------------------------------------

* **100% stdlib.** O ``doctor.sh`` carrega o exame pelo ``python3`` do sistema,
  e o exame passa a carregar este arquivo: uma dependência de terceiros aqui
  viraria uma linha muda na conferência. É por isso que este módulo **não**
  importa ``mapa_das_portas`` nem ``utils/maquina`` — os dois trazem pydantic
  junto. A vizinhança pelo desenho dela entra por ARGUMENTO, já calculada por
  quem chama (``mapa_das_portas.vizinhas_de_verdade``).
* **Funções puras.** Nada aqui abre ``/dev``, fala com o daemon, escreve em
  disco ou toca no rádio. O catálogo inteiro sai do censo do barramento e da
  leitura das entradas, os dois já feitos por quem chama.
* **Nenhum serial, nenhum endereço, em lugar nenhum.** :class:`Identidade`
  guarda ``vid``, ``pid`` e o caminho de barramento — e um booleano dizendo se a
  tripla ficou AMBÍGUA. O serial é lido dentro de :func:`identidades`, usado
  para comparar, e descartado. A tela desta aba vira PNG versionado
  (``scripts/gui-captura/retratar_abas.py``), e ``scripts/check_anonymity.sh``
  diz por escrito que o serial identifica a unidade dela tão bem quanto o MAC.

O QUE NENHUMA ORDEM PODE DIZER
-------------------------------

1. que o aparelho de 5 Gbps está derrubando o Bluetooth dela — é hipótese, e a
   medição que a fecharia não foi feita;
2. **"Wi-Fi"**, enquanto a classe do aparelho for ``ff`` e ela não tiver
   declarado o que é. O kernel não classifica, e o ``product`` dizer
   "802.11ac NIC" não o torna Wi-Fi para o produto — adivinhar por texto é como
   se erra com confiança (``censo_do_barramento.py``, cabeçalho);
3. que um dongle atrapalha OUTRO dongle. Três adaptadores no mesmo hub é o
   arranjo que o próprio ``GUIA-RADIO-DA-SALA.md`` manda comprar;
4. qualquer número de milímetros, altura ou linha de visada — o guia é
   raciocínio, e ela já disse que não sabe o que essas palavras querem dizer;
5. o serial ou o endereço de aparelho nenhum.
"""
from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    Aparelho,
    Censo,
    cadeia_de_hubs,
)
from hefesto_dualsense4unix.integrations.entradas_do_gabinete import (
    Furo,
    NoDeEntrada,
    furos,
)
from hefesto_dualsense4unix.integrations.portas_do_barramento import (
    hubs_do_mesmo_plastico,
)

# ---------------------------------------------------------------------------
# Os três selos.
# ---------------------------------------------------------------------------

#: Medi nesta máquina, agora. É o selo mais forte e o mais barato de perder:
#: basta a frase falar de outra máquina que ele deixa de valer.
MEDIDO_AQUI = "medido-aqui"

#: Sai de uma conta sobre o que foi medido — contagem, soma, consequência
#: lógica. Não existe no ``de_onde_sei`` do mapa de canais porque o CSV não faz
#: aritmética.
DERIVADO_DA_CONTA = "derivado-da-conta"

#: Alguém de fora afirmou, e este selo **exige nomear quem**. Sem ``fonte`` a
#: linha não existe — há portão.
ESPECIFICACAO_DE_TERCEIRO = "especificacao-de-terceiro"

#: Os três, na ordem de força. É contra esta tupla que o portão de AST confere.
SELOS = (MEDIDO_AQUI, DERIVADO_DA_CONTA, ESPECIFICACAO_DE_TERCEIRO)

#: A palavra de tela de cada selo. Chave de máquina em ASCII com hífen (a
#: convenção do ``de_onde_sei``), texto de gente à parte — pelo mesmo motivo de
#: sempre: a chave é contrato e o texto é da frente do léxico.
TEXTO_DO_SELO = {
    MEDIDO_AQUI: "medido aqui",
    DERIVADO_DA_CONTA: "derivado da conta",
    ESPECIFICACAO_DE_TERCEIRO: "especificação de terceiro",
}

# ---------------------------------------------------------------------------
# As duas ausências, e elas NÃO são a mesma — ``D-O-QUE-O-PRODUTO-DIZ-SEM-SABER``.
# ---------------------------------------------------------------------------

#: "Olhei e não sei quanto." O aparelho está aqui, a medição é possível, e ela
#: não foi feita nesta máquina.
NAO_MEDI = "Não medi o ganho nesta máquina."

#: "Só você sabe, e você ainda não me disse." Nenhuma medição fecha isto: o
#: desenho do gabinete não está em lugar nenhum do sistema.
NAO_DECLARADO = "Você ainda não desenhou suas entradas na seção Conexões."

#: A frase que fecha uma ordem sem destino — e ela diz por que não há destino,
#: em vez de calar. Calar é o F7.
SEM_DESTINO = "Não achei entrada livre para onde mandar."

# ---------------------------------------------------------------------------
# Os números que o catálogo compara.
# ---------------------------------------------------------------------------

#: A partir daqui o aparelho negocia em SuperSpeed, que é a velocidade cujo
#: sinal emite ruído de banda larga em cima de 2,4 GHz. Mesmo valor de
#: ``entradas_do_gabinete.VELOCIDADE_SUPERSPEED_MBPS`` — repetido e não
#: importado de lá porque ali ele responde "este buraco é azul?" e aqui ele
#: responde "este sinal faz ruído?": duas perguntas que podem divergir.
VELOCIDADE_LARGA_MBPS = 5000.0

#: A classe de interface de um adaptador Bluetooth, na tripla do kernel.
#: ``e0/01/01`` — a mesma régua de ``censo_do_barramento._especie``, e ela é o
#: ÚNICO jeito de o produto saber que um aparelho é Bluetooth sem adivinhar por
#: nome de produto.
_CLASSE_BLUETOOTH = ("e0", "01", "01")

#: A classe de interface de um teclado: ``03/01/01``.
_CLASSE_TECLADO = ("03", "01", "01")

#: O ``connect_type`` de uma entrada que uma pessoa alcança com a mão. As
#: internas respondem ``hard-wired`` ou ``unknown``, e mandar alguém encaixar um
#: cabo numa entrada soldada dentro do gabinete é pior que não mandar nada.
ENCAIXE_DE_GENTE = "hotplug"

#: Doze hex é a forma em que um serial USB carrega endereço. Aqui ele nunca é
#: guardado: só entra na comparação que decide se a tripla ficou ambígua.
_TAMANHO_DO_SERIAL_DE_ENDERECO = 12

#: Onde mora o serial de um nó USB, relativo ao caminho do nó.
_ARQUIVO_DO_SERIAL = "serial"

# ---------------------------------------------------------------------------
# As chaves das regras. São a chave de DISPENSA e a chave de teste, e por isso
# são ASCII com sublinhado — nunca o texto de tela, que muda de dono.
# ---------------------------------------------------------------------------

R1_RADIO_LARGO_NO_MESMO_HUB = "radio_largo_no_mesmo_hub"
R2_DOIS_RADIOS_COLADOS = "dois_radios_colados"
R3_DONGLE_ATRAS_DE_HUB = "dongle_atras_de_hub"
R4_TECLADO_SO_NO_HUB = "teclado_so_no_hub"
R5_DONGLE_DORME = "dongle_dorme"
R6_ENTRADA_RECLAMOU_DE_CORRENTE = "entrada_reclamou_de_corrente"


@dataclass(frozen=True)
class Linha:
    """Uma das três frases de uma ordem, com de onde ela veio.

    ``fonte`` é OBRIGATÓRIA quando ``selo == ESPECIFICACAO_DE_TERCEIRO``, e é um
    caminho de arquivo desta árvore — não um nome de empresa solto. Há dois
    portões: um confere o selo e a presença da fonte por AST, o outro confere
    que o arquivo apontado existe em disco.
    """

    texto: str
    selo: str
    fonte: str = ""

    def como_dicionario(self) -> dict[str, object]:
        """Forma JSON — é o que o ``doctor.sh --censo`` consome."""
        return {"texto": self.texto, "selo": self.selo, "fonte": self.fonte}


@dataclass(frozen=True)
class Identidade:
    """Quem é o aparelho que a ordem manda mover — **sem o serial dele**.

    ``ambigua`` é o que impede o produto de dizer "Confirmei" quando não pode:
    dois aparelhos com a MESMA tripla ``(vid, pid, serial)`` na mesa são
    indistinguíveis, e a resposta honesta é "não consegui confirmar", nunca um
    chute. O serial que decidiu isso foi lido em :func:`identidades`, comparado
    e descartado — ele não está aqui, e não pode estar.
    """

    vid: str = ""
    pid: str = ""
    caminho: str = ""
    ambigua: bool = False


@dataclass(frozen=True)
class Ordem:
    """Uma ordem de serviço: o imperativo, as três linhas, e o alvo.

    ``chave`` é o slug da regra, e é a chave de dispensa: uma regra produz no
    máximo UMA ordem por leitura. Duas ordens da mesma regra na mesma tela
    dariam duas linhas para o mesmo fato e duas dispensas para a mesma decisão.

    ``arranjo`` é a assinatura do que a regra viu — os caminhos de barramento do
    alvo e de quem o acusou, na ordem em que a regra os viu. É ele, e não o
    serial, que responde "você moveu?" e "isto é fato novo?". Não carrega
    serial, não carrega endereço.

    ``destino`` vazio é uma ordem **sem ação**: ela conta o que viu e não manda
    nada, porque não há para onde mandar. ``acao`` acompanha, e fica vazia  # (noqa-acento)
    junto — uma ordem que manda mover para lugar nenhum é pior que silêncio.
    """

    chave: str
    acao: str
    o_que_eu_vi: Linha
    por_que_importa: Linha
    ganho_esperado: Linha
    alvo: Identidade = field(default_factory=Identidade)
    arranjo: str = ""
    destino: str = ""

    @property
    def tem_acao(self) -> bool:
        """A ordem manda fazer alguma coisa, ou só conta o que viu?"""
        return bool(self.acao)

    @property
    def linhas(self) -> tuple[Linha, Linha, Linha]:
        """As três, na ordem da tela. Nenhuma é opcional, nem a terceira."""
        return (self.o_que_eu_vi, self.por_que_importa, self.ganho_esperado)

    def como_dicionario(self) -> dict[str, object]:
        """Forma JSON — é o que o ``doctor.sh --censo`` consome."""
        return {
            "chave": self.chave,
            "acao": self.acao,  # (noqa-acento): chave de máquina, ASCII por contrato
            "o_que_eu_vi": self.o_que_eu_vi.como_dicionario(),
            "por_que_importa": self.por_que_importa.como_dicionario(),
            "ganho_esperado": self.ganho_esperado.como_dicionario(),
            "arranjo": self.arranjo,
            "destino": self.destino,
        }


@dataclass(frozen=True)
class Leitura:
    """Tudo que o catálogo lê, num objeto só — um ponto de injeção, não seis.

    Nenhum campo é buscado por este módulo: quem chama já leu o barramento
    (``censo_do_barramento.ler_o_barramento``), já leu as entradas
    (``entradas_do_gabinete.listar_entradas``) e, se ela desenhou a mesa, já
    calculou a vizinhança pelo desenho
    (``mapa_das_portas.vizinhas_de_verdade``). É o contrato que mantém este
    arquivo 100% stdlib e testável sem tocar em ``/sys``.

    ``vizinhas`` são pares de NÚMEROS de entrada, do desenho dela — tupla vazia
    quando ela não desenhou, que é o caso mais comum e é uma resposta.
    ``ocupante_da_entrada`` diz qual caminho de barramento está em cada número.

    ``nomes_declarados`` é ``{"vid:pid": "o nome que ela deu"}``: é o que
    autoriza a ordem a chamar o aparelho de 5 Gbps pelo nome. Sem declaração, a
    ordem diz "um aparelho que você ainda não identificou" — e nunca "Wi-Fi".

    ``entradas_livres_declaradas`` são os NÚMEROS que ela escreveu no gabinete e
    que estão vazios agora (``mapa_das_portas.portas_livres``). Elas são a única
    fonte de um DESTINO: o ``/sys`` sabe contar buracos livres e não sabe onde
    eles ficam no metal, e ``usb1-port5`` não é um lugar que uma pessoa ache.
    """

    censo: Censo = field(default_factory=Censo)
    entradas: tuple[NoDeEntrada, ...] = ()
    vizinhas: tuple[tuple[str, str], ...] = ()
    ocupante_da_entrada: Mapping[str, str] = field(default_factory=dict)
    entradas_livres_declaradas: tuple[str, ...] = ()
    nomes_declarados: Mapping[str, str] = field(default_factory=dict)
    tipos_declarados: Mapping[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# A topologia que o `busnum` esconde.
# ---------------------------------------------------------------------------


def mesmo_hub_fisico(
    leitura: Leitura, primeiro: Aparelho, segundo: Aparelho
) -> bool:
    """Os dois aparelhos penduram no MESMO plástico de hub?

    **É a função que faz R1 enxergar.** ``mesa_de_radio.vizinhancas_apertadas``
    recusa qualquer par cujos ``busnum`` diferem, e o arranjo suspeito desta
    bancada é exatamente esse: um aparelho de 5 Gbps em ``4-1.1.2`` e um
    adaptador Bluetooth em ``3-1.1.4`` — dois buracos do MESMO chip de hub, em
    barramentos diferentes porque o hub tem um lado 2.0 e um lado 3.0.

    QUEM DIZ QUE DOIS HUBS SÃO O MESMO PLÁSTICO É O KERNEL, E NÃO UMA CONTA
    ----------------------------------------------------------------------

    A resposta sai de ``portas_do_barramento.hubs_do_mesmo_plastico``, que
    agrupa os hubs pelo symlink ``peer`` das entradas deles. **Não** de uma
    comparação de ``devpath``, e a diferença foi medida nesta máquina em
    25/08/2026::

        usb1-port5  peer -> usb2-port1
        usb1-port6  peer -> usb2-port2
        usb1-port7  peer -> usb2-port3

    **Os números dos dois lados divergem.** Um hub encaixado no buraco que é
    ``usb1-port5`` do lado 2.0 enumera como ``1-5`` (``devpath`` ``"5"``) e como
    ``2-1`` (``devpath`` ``"1"``) do lado 3.0 — e uma régua que compara
    ``devpath`` declara que os dois lados do MESMO hub são plásticos diferentes.
    R1 ficaria cega exatamente no buraco que ela recomenda como destino, porque
    ``usb1-port5``, ``-port6`` e ``-port7`` são ``hotplug``: são as entradas que
    uma pessoa alcança com a mão. Há teste que reprova se a conta voltar.

    O ``peer`` não tem esse ponto cego: ele é o que o kernel costurou a partir
    do firmware, buraco a buraco, e não depende de os números baterem.
    """
    classes = hubs_do_mesmo_plastico(leitura.entradas)
    de_um = _plastico_dos_hubs(leitura.censo, primeiro, classes)
    de_outro = _plastico_dos_hubs(leitura.censo, segundo, classes)
    return bool(de_um & de_outro)


def _plastico_dos_hubs(
    censo: Censo, aparelho: Aparelho, classes: Mapping[str, frozenset[str]]
) -> set[str]:
    """Os hubs acima deste aparelho, cada um expandido no plástico dele.

    ``cadeia_de_hubs`` já deixa os hubs-raiz de fora: eles não são aparelho de
    bancada, e incluí-los faria dois aparelhos quaisquer do mesmo controlador
    parecerem "no mesmo hub".

    Um hub que o ``peer`` não costurou a ninguém responde por si mesmo — não
    saber que ele tem outro lado não é o mesmo que saber que ele não tem.
    """
    por_no = {a.no: a for a in censo.aparelhos}
    saida: set[str] = set()
    for no in cadeia_de_hubs(censo, aparelho.no):
        hub = por_no.get(no)
        if hub is None:
            continue
        nome = hub.nome_do_kernel
        saida |= classes.get(nome, frozenset({nome}))
    return saida


# ---------------------------------------------------------------------------
# A identidade, e as duas armadilhas medidas.
# ---------------------------------------------------------------------------


def identidades(
    censo: Censo, *, ler_serial: Callable[[str], str] | None = None
) -> dict[str, Identidade]:
    """``{nome do kernel: Identidade}`` — e o serial morre aqui dentro.

    Duas armadilhas, as duas medidas em 24/08/2026 nesta bancada:

    1. **``vid:pid`` não identifica.** Os três adaptadores Bluetooth desta casa
       são ``2357:0604``. Quem separa é o ``serial``, e ele vem de graça no
       sysfs — sem BlueZ, sem D-Bus, sem endereço;
    2. **``serial`` também mente.** O aparelho de 5 Gbps declara ``123456``, e
       o ``product`` diverge entre dois dongles idênticos. Quando a tripla
       ``(vid, pid, serial)`` aparece DUAS vezes na mesa, ela deixa de
       identificar — e a ordem que dependia dela desiste de confirmar em vez de
       chutar.

    O serial lido não sai desta função: ele entra na contagem que decide
    ``ambigua`` e é descartado. Nenhum atributo de :class:`Identidade` o
    carrega, e é assim que ele não chega ao PNG que o retrato das abas versiona.
    """
    leitor = _serial_do_no if ler_serial is None else ler_serial
    triplas: dict[str, tuple[str, str, str]] = {}
    for aparelho in censo.conectados():
        triplas[aparelho.nome_do_kernel] = (
            aparelho.vid,
            aparelho.pid,
            _serial_normalizado(leitor(aparelho.no)),
        )
    quantas: dict[tuple[str, str, str], int] = {}
    for tripla in triplas.values():
        quantas[tripla] = quantas.get(tripla, 0) + 1
    return {
        nome: Identidade(
            vid=tripla[0],
            pid=tripla[1],
            caminho=nome,
            ambigua=quantas[tripla] > 1,
        )
        for nome, tripla in triplas.items()
    }


def _serial_normalizado(serial: str) -> str:
    """O serial em minúsculas e sem separador — ``""`` quando não há serial.

    Não é validação de forma: um serial de fábrica pode ser qualquer coisa, e
    aqui ele só precisa comparar consigo mesmo. O que importa é que dois
    aparelhos SEM serial colapsem na mesma tripla, porque é o que eles são: dois
    aparelhos que o sysfs não sabe separar.
    """
    limpo = serial.strip().replace(":", "").replace("-", "").lower()
    return limpo[:_TAMANHO_DO_SERIAL_DE_ENDERECO] if limpo else ""


def _serial_do_no(no: str) -> str:
    """O ``serial`` de um nó USB; ``""`` em qualquer erro.

    É o único leitor de arquivo deste módulo, e ele existe para ser trocado por
    um dublê em teste. O valor que ele devolve **não sai** de
    :func:`identidades`.
    """
    try:
        with open(
            os.path.join(no, _ARQUIVO_DO_SERIAL), encoding="utf-8", errors="replace"
        ) as arquivo:
            return arquivo.read()
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# As seis regras de topologia. Uma função pura por regra, no molde de uma
# função por linha de `exame_da_mesa.py`.
# ---------------------------------------------------------------------------


def radio_largo_no_mesmo_hub(leitura: Leitura) -> Ordem | None:
    """R1 — um aparelho de banda larga no mesmo hub que um adaptador Bluetooth.

    O gatilho é ``velocidade_mbps >= 5000`` num aparelho que divide o plástico
    de hub com um adaptador Bluetooth. É a regra que **só existe** porque
    :func:`mesmo_hub_fisico` atravessa o ``busnum``.

    A ordem nomeia o aparelho pelo que ELA declarou, e nunca pelo ``product``:
    com classe ``ff`` e sem declaração, ele é "um aparelho que você ainda não
    identificou". Ler o ``product`` para escrever "Wi-Fi" é adivinhar por texto.
    """
    largos = [
        aparelho
        for aparelho in leitura.censo.conectados()
        if aparelho.velocidade_mbps >= VELOCIDADE_LARGA_MBPS
        and not aparelho.e_hub
        and not _e_bluetooth(aparelho)
    ]
    adaptadores = _bluetooth_do_censo(leitura.censo)
    pares = [
        (largo, dongle)
        for largo in largos
        for dongle in adaptadores
        if mesmo_hub_fisico(leitura, largo, dongle)
    ]
    if not pares:
        return None
    alvo, _acusador = pares[0]
    livres = _livres_fora_da_controladora(leitura, alvo.controlador_pci)
    destino = _destino_declarado(leitura)
    nome = _nome_do_aparelho(leitura, alvo)
    return Ordem(
        chave=R1_RADIO_LARGO_NO_MESMO_HUB,
        acao=_acao(f"Mova {nome}", len(livres), destino),
        o_que_eu_vi=Linha(
            texto=(
                f"{_com_maiuscula(nome)} negocia "
                f"{_velocidade(alvo.velocidade_mbps)} no mesmo hub que "
                + _plural(
                    len(pares),
                    "um adaptador Bluetooth",
                    f"{len(pares)} adaptadores Bluetooth",
                )
                + "."
            ),
            selo=MEDIDO_AQUI,
        ),
        por_que_importa=Linha(
            texto=(
                "USB 3.0 emite ruído bem em cima da faixa de 2,4 GHz, que é a "
                "faixa dos controles."
            ),
            selo=ESPECIFICACAO_DE_TERCEIRO,
            fonte="docs/protocol/por-que-usb3-atrapalha-24ghz.md",
        ),
        ganho_esperado=Linha(
            texto=NAO_MEDI if livres else f"{NAO_MEDI} {SEM_DESTINO}",
            selo=DERIVADO_DA_CONTA,
        ),
        alvo=_identidade_de(leitura, alvo),
        arranjo=_assinatura(pares),
        destino=destino if livres else "",
    )


def dois_radios_colados(leitura: Leitura) -> Ordem | None:
    """R2 — duas entradas coladas NO DESENHO DELA, as duas irradiando.

    Consome ``mapa_das_portas.vizinhas_de_verdade``, que já veio calculada em
    :attr:`Leitura.vizinhas` — a vizinhança ficou com a frente do mapa 2D de
    propósito, porque a entrada por extensão muda o cálculo e só o desenho dela
    sabe onde a extensão está.

    **O filtro é o ponto da regra.** Só conta como irradiando o que o kernel
    classificou como Bluetooth (``e0/01/01``) ou o que ELA declarou como rádio.
    Sem ele, a webcam de cabo colada a um dongle vira acusação — foi o que a
    tela publicou nesta bancada, e webcam de cabo não irradia 2,4 GHz.

    Sem desenho, a regra cala. Isso **não** é "está tudo certo": é
    :data:`NAO_DECLARADO`, e quem escreve o cabeçalho sabe a diferença.
    """
    acusados = [
        (primeira, segunda)
        for primeira, segunda in leitura.vizinhas
        if _irradia(leitura, primeira) and _irradia(leitura, segunda)
    ]
    if not acusados:
        return None
    primeira, segunda = acusados[0]
    ocupante = leitura.ocupante_da_entrada
    caminhos = [
        (ocupante.get(um, ""), ocupante.get(outro, ""))
        for um, outro in acusados
    ]
    return Ordem(
        chave=R2_DOIS_RADIOS_COLADOS,
        acao="Mude um dos dois para uma entrada mais longe",
        o_que_eu_vi=Linha(
            texto=(
                f"As entradas {primeira} e {segunda} estão coladas no seu "
                "desenho, e as duas têm um aparelho que usa 2,4 GHz."
            ),
            selo=MEDIDO_AQUI,
        ),
        por_que_importa=Linha(
            texto=(
                "Rádio ao lado de rádio é a vizinhança que mais atrapalha o "
                "controle."
            ),
            selo=DERIVADO_DA_CONTA,
        ),
        ganho_esperado=Linha(texto=NAO_MEDI, selo=DERIVADO_DA_CONTA),
        alvo=_identidade_do_caminho(
            leitura, leitura.ocupante_da_entrada.get(primeira, "")
        ),
        arranjo=_assinatura_de_caminhos(caminhos),
        destino=_destino_declarado(leitura),
    )


def dongle_atras_de_hub(leitura: Leitura) -> Ordem | None:
    """R3 — o adaptador Bluetooth chega ao computador por dentro do hub.

    **A contra-regra é obrigatória, e é metade da regra:** três adaptadores no
    mesmo hub é o arranjo que o próprio ``GUIA-RADIO-DA-SALA.md`` manda comprar.
    R3 **nunca** acusa um dongle de atrapalhar outro; o que ela conta é que o
    caminho até o computador passa por um hub, e o hub tem uma velocidade só
    para tudo que estiver nele.

    O destino só nasce quando há entrada de gente (``hotplug``) livre numa
    controladora PCI **diferente** — mandar mover para outra entrada do mesmo
    hub não mudaria nada. Sem destino, a ordem nasce **sem ação**: ela conta o
    que viu, e cala sobre o que fazer, porque não há o que fazer.
    """
    atras = [
        aparelho
        for aparelho in _bluetooth_do_censo(leitura.censo)
        if aparelho.atras_de_hub
    ]
    if not atras:
        return None
    total = len(_bluetooth_do_censo(leitura.censo))
    alvo = atras[0]
    livres = _livres_fora_da_controladora(leitura, alvo.controlador_pci)
    destino = _destino_declarado(leitura)
    velocidade = _velocidade_do_hub(leitura.censo, alvo)
    return Ordem(
        chave=R3_DONGLE_ATRAS_DE_HUB,
        acao=_acao("Leve um dos adaptadores Bluetooth", len(livres), destino),
        o_que_eu_vi=Linha(
            texto=(
                f"{len(atras)} de {total} "
                + _plural(
                    total,
                    "adaptador Bluetooth chega",
                    "adaptadores Bluetooth chegam",
                )
                + " ao computador por dentro de um hub, e há "
                f"{len(livres)} "
                f"{_plural(len(livres), 'entrada livre', 'entradas livres')} "
                "no próprio computador."
            ),
            selo=MEDIDO_AQUI,
        ),
        por_que_importa=Linha(
            texto=(
                "Tudo que passa pelo hub divide o mesmo caminho de "
                f"{_velocidade(velocidade)} com o que mais estiver lá."
                if velocidade
                else (
                    "Tudo que passa pelo hub divide o mesmo caminho com o que "
                    "mais estiver lá."
                )
            ),
            selo=MEDIDO_AQUI,
        ),
        ganho_esperado=Linha(
            texto=NAO_MEDI if livres else f"{NAO_MEDI} {SEM_DESTINO}",
            selo=DERIVADO_DA_CONTA,
        ),
        alvo=_identidade_de(leitura, alvo),
        arranjo=_assinatura_de_caminhos(
            [(aparelho.nome_do_kernel, "") for aparelho in atras]
        ),
        destino=destino if livres else "",
    )


def teclado_so_no_hub(leitura: Leitura) -> Ordem | None:
    """R4 — o único teclado da casa depende do hub.

    É a única regra do catálogo que **não fala de rádio**, e a terceira linha
    dela diz isso com todas as letras. Uma ordem que promete ganho de rádio onde
    não há é exatamente o raciocínio se vestindo de medição que o selo existe
    para impedir.
    """
    teclados = [
        aparelho
        for aparelho in leitura.censo.conectados()
        if _classe_de(aparelho) == _CLASSE_TECLADO
    ]
    if not teclados or any(not teclado.atras_de_hub for teclado in teclados):
        return None
    alvo = teclados[0]
    livres = _livres_fora_da_controladora(leitura, alvo.controlador_pci)
    destino = _destino_declarado(leitura)
    return Ordem(
        chave=R4_TECLADO_SO_NO_HUB,
        acao=_acao("Leve um teclado", len(livres), destino),
        o_que_eu_vi=Linha(
            texto=(
                _plural(
                    len(teclados),
                    "O único teclado da casa depende",
                    "Todos os teclados da casa dependem",
                )
                + " do hub."
            ),
            selo=MEDIDO_AQUI,
        ),
        por_que_importa=Linha(
            texto=(
                "Se o hub sair da tomada, você fica sem teclado antes de o "
                "Linux abrir."
            ),
            selo=DERIVADO_DA_CONTA,
        ),
        ganho_esperado=Linha(
            texto=(
                "Isto não muda o rádio; é sobre você conseguir ligar o "
                "computador."
            ),
            selo=DERIVADO_DA_CONTA,
        ),
        alvo=_identidade_de(leitura, alvo),
        arranjo=_assinatura_de_caminhos(
            [(teclado.nome_do_kernel, "") for teclado in teclados]
        ),
        destino=destino if livres else "",
    )


def dongle_dorme(leitura: Leitura) -> Ordem | None:
    """R5 — o adaptador Bluetooth está autorizado a dormir.

    ``power/control == "auto"`` num aparelho sem fio: o sistema pode desligá-lo
    para poupar energia, e o controle cai sozinho no meio do jogo. É o mesmo
    fato que ``exame_da_mesa.energia_das_portas`` já conta em número; o que a
    ordem acrescenta é o imperativo e o selo.

    **Nesta bancada ela CALA**, e isso é resultado, não ausência: em 24/08/2026
    os dez aparelhos responderam ``on``. Um catálogo cujas regras todas disparam
    é um catálogo que não distingue nada.
    """
    dormindo = [
        aparelho
        for aparelho in leitura.censo.conectados()
        if _e_bluetooth(aparelho) and aparelho.energia.controle == "auto"
    ]
    if not dormindo:
        return None
    alvo = dormindo[0]
    return Ordem(
        chave=R5_DONGLE_DORME,
        acao="Rode a instalação do Hefesto de novo: a regra entra por padrão",
        o_que_eu_vi=Linha(
            texto=(
                _plural(
                    len(dormindo),
                    "Um adaptador Bluetooth está",
                    f"{len(dormindo)} adaptadores Bluetooth estão",
                )
                + " com a economia de energia ligada."
            ),
            selo=MEDIDO_AQUI,
        ),
        por_que_importa=Linha(
            texto=(
                "O sistema pode desligar o adaptador para poupar energia, e aí "
                "o controle cai sozinho no meio do jogo."
            ),
            selo=DERIVADO_DA_CONTA,
        ),
        ganho_esperado=Linha(texto=NAO_MEDI, selo=DERIVADO_DA_CONTA),
        alvo=_identidade_de(leitura, alvo),
        arranjo=_assinatura_de_caminhos(
            [(aparelho.nome_do_kernel, "") for aparelho in dormindo]
        ),
        destino="",
    )


def entrada_reclamou_de_corrente(leitura: Leitura) -> Ordem | None:
    """R6 — a entrada de um adaptador já acusou excesso de corrente.

    ``port/over_current_count > 0`` é o único número que o sysfs dá sem root e
    que registra um EVENTO real, e não uma declaração de descritor. Zero em toda
    a mesa é uma resposta; maior que zero é um aparelho que já foi cortado.
    """
    reclamaram = [
        aparelho
        for aparelho in leitura.censo.conectados()
        if _e_bluetooth(aparelho) and (aparelho.energia.excesso_de_corrente or 0) > 0
    ]
    if not reclamaram:
        return None
    alvo = reclamaram[0]
    livres = _livres_fora_da_controladora(leitura, alvo.controlador_pci)
    destino = _destino_declarado(leitura)
    return Ordem(
        chave=R6_ENTRADA_RECLAMOU_DE_CORRENTE,
        acao=_acao("Leve esse adaptador", len(livres), destino),
        o_que_eu_vi=Linha(
            texto=(
                "A entrada de "
                + _plural(
                    len(reclamaram),
                    "um adaptador Bluetooth",
                    f"{len(reclamaram)} adaptadores Bluetooth",
                )
                + " já acusou excesso de corrente."
            ),
            selo=MEDIDO_AQUI,
        ),
        por_que_importa=Linha(
            texto="Entrada que corta a corrente derruba o aparelho sem aviso.",
            selo=DERIVADO_DA_CONTA,
        ),
        ganho_esperado=Linha(
            texto=NAO_MEDI if livres else f"{NAO_MEDI} {SEM_DESTINO}",
            selo=DERIVADO_DA_CONTA,
        ),
        alvo=_identidade_de(leitura, alvo),
        arranjo=_assinatura_de_caminhos(
            [(aparelho.nome_do_kernel, "") for aparelho in reclamaram]
        ),
        destino=destino if livres else "",
    )


#: As seis regras, na ordem em que elas aparecem na tela. A ordem é a de
#: gravidade percebida, não a de escrita: R1 e R2 falam de rádio ruim agora, R3
#: fala de caminho, R4 não fala de rádio nenhum.
REGRAS: tuple[Callable[[Leitura], Ordem | None], ...] = (
    radio_largo_no_mesmo_hub,
    dois_radios_colados,
    dongle_atras_de_hub,
    dongle_dorme,
    entrada_reclamou_de_corrente,
    teclado_so_no_hub,
)


def catalogo(leitura: Leitura) -> tuple[Ordem, ...]:
    """Todas as ordens que as seis regras acharam, na ordem da tela.

    Uma regra que não dispara devolve ``None`` e some daqui. Catálogo vazio é
    resposta: quer dizer que as seis regras rodaram e nenhuma achou nada — o que
    é diferente de nenhuma regra ter rodado, e é o cabeçalho que separa os dois.
    """
    achadas = [regra(leitura) for regra in REGRAS]
    return tuple(ordem for ordem in achadas if ordem is not None)


# ---------------------------------------------------------------------------
# A dispensa — ``D-ORDEM-IGNORADA-VOLTA``.
# ---------------------------------------------------------------------------


def ordens_novas(
    ordens: Sequence[Ordem], dispensadas: Mapping[str, str]
) -> tuple[Ordem, ...]:
    """As ordens que ela ainda não dispensou **neste arranjo**.

    ``dispensadas`` é ``{chave da regra: arranjo dispensado}``. A chave do
    dispensado é o ARRANJO, e não a recomendação: a dispensa vale para o que ela
    viu, e se ela mudar os cabos e a mesma regra disparar com um arranjo novo, é
    fato novo e a ordem volta. Chavear só pelo slug faria a decisão de ontem
    calar uma medição de hoje.

    **ARRANJO VAZIO NÃO É ASSINATURA — medido em 06/09/2026, e o defeito é do
    lado que CALA.** `Ordem.arranjo` tem `""` por padrão, e a `ONDA5-08-01`
    ensinou o desfazer a gravar `arranjo=""` na dispensa. As duas pontas vazias
    casavam: uma ordem VIVA que chegasse sem arranjo — o padrão do campo — batia
    com o vazio guardado e nascia CALADA para os dois consumidores deste módulo,
    a janela GTK inclusive. Uma ordem que ninguém dispensou sumia da tela, e ela
    deixaria de saber que existe uma medição ali.

    Relatado por TRÊS frentes seguidas (08-01, 08-02 e CONEXOES-LIGAR-TUDO-01)
    sem uma linha de mudança, porque o arquivo estava fora da posse das três. A
    aba nova tinha guarda local (`a08_conexoes._ordem_calada`) e por isso não
    sofria — o que é a definição de cura pela metade.
    """
    return tuple(
        ordem
        for ordem in ordens
        if not ordem.arranjo or dispensadas.get(ordem.chave) != ordem.arranjo
    )


def ordens_caladas(
    ordens: Sequence[Ordem], dispensadas: Mapping[str, str]
) -> tuple[Ordem, ...]:
    """As ordens que a dispensa dela está segurando — e que a tela CONTA.

    Dispensa que some sem deixar marca é a mesma classe de defeito do card que
    some: ela deixaria de saber que existe uma decisão dela ali.

    O `ordem.arranjo and` é a outra metade da cura de 06/09/2026 — ver
    :func:`ordens_novas`. Sem ele esta contagem incluiria as ordens vivas de
    arranjo vazio, e a tela diria que há uma decisão dela onde não há nenhuma.
    """
    return tuple(
        ordem
        for ordem in ordens
        if ordem.arranjo and dispensadas.get(ordem.chave) == ordem.arranjo
    )


# ---------------------------------------------------------------------------
# "Já movi — reexaminar": as quatro respostas, e nenhuma é repetir a ordem.
# ---------------------------------------------------------------------------

#: A regra parou de disparar. Verde, e **fica na tela** até ela sair da aba: um
#: card que simplesmente some é indistinguível de um card que nunca foi
#: desenhado, e ela apertou um botão e precisa ver o que ele fez.
CONFIRMEI = "confirmei"

#: A regra ainda dispara, com outro arranjo. Ela moveu, e continua apertado.
MOVEU_E_CONTINUA = "moveu_e_continua"

#: A regra dispara com o MESMO arranjo. O card fica, com essa linha somada.
SEM_MUDANCA = "sem_mudanca"

#: A tripla do alvo ficou ambígua — dois aparelhos iguais na mesa. **Nunca**
#: "Confirmei": o produto não sabe qual dos dois ela moveu.
NAO_CONSEGUI_CONFIRMAR = "nao_consegui_confirmar"

#: A frase de cada resposta. Texto provisório da frente do léxico; o que é
#: contrato é a chave, e é ela que o teste afirma.
FRASE_DA_RESPOSTA = {
    CONFIRMEI: "Confirmei: o aparelho saiu de perto do adaptador.",
    MOVEU_E_CONTINUA: "Você moveu, e continua apertado:",
    SEM_MUDANCA: "Não vi mudança: o aparelho continua na mesma entrada.",
    NAO_CONSEGUI_CONFIRMAR: (
        "Não consegui confirmar: há dois aparelhos iguais na mesa."
    ),
}


def resposta_ao_ja_movi(anterior: Ordem, agora: Ordem | None) -> str:
    """O que a tela diz depois do "Já movi — reexaminar".

    ``anterior`` é a ordem que estava na tela quando ela apertou o botão;
    ``agora`` é o que a MESMA regra devolveu na leitura nova — ``None`` quando
    ela parou de disparar.

    A ambiguidade vence tudo, e vence antes: com dois aparelhos de tripla igual
    na mesa, o produto não sabe qual deles ela moveu, e "Confirmei" ali seria
    uma afirmação sem base. Só depois vêm as três respostas do arranjo.
    """
    if anterior.alvo.ambigua or (agora is not None and agora.alvo.ambigua):
        return NAO_CONSEGUI_CONFIRMAR
    if agora is None:
        return CONFIRMEI
    if agora.arranjo != anterior.arranjo:
        return MOVEU_E_CONTINUA
    return SEM_MUDANCA


# ---------------------------------------------------------------------------
# O cabeçalho — o estado bom sabe se dizer (F7).
# ---------------------------------------------------------------------------

#: Há ordens: a tela conta quantas.
TOPO_HA_ORDENS = "ha_ordens"

#: Zero ordens e tudo respondeu. É o único verde, e ele diz QUANTA coisa foi
#: conferida — a queixa dela era que "está tudo certo" não fala nada.
TOPO_NADA_A_MUDAR = "nada_a_mudar"

#: Zero ordens e alguma checagem não soube. **Cinza, nunca verde.** É o F7: o
#: estado em que o produto não sabe se disfarçando do estado em que está tudo
#: bem.
TOPO_ALGUMA_NAO_SOUBE = "alguma_nao_soube"

#: Zero ordens novas, e há dispensa dela. Verde, e conta a decisão dela.
TOPO_NADA_NOVO = "nada_novo"


@dataclass(frozen=True)
class Cabecalho:
    """O selo do topo da seção — a frase, a chave de estado e o botão.

    A chave de estado é a de ``exame_da_mesa`` (``certo``/``atencao``/  # (noqa-acento)
    ``nao_sei``) e vem CALCULADA AQUI, num lugar só: um segundo lugar decidindo
    a cor do topo é exatamente como o verde volta a conviver com o vermelho
    (cicatriz de ``6c86e295``, 16/08/2026).
    """

    chave: str
    texto: str
    estado: str
    botao: str = ""


def cabecalho(
    *,
    ordens: Sequence[Ordem],
    conferidas: int,
    sem_resposta: int,
    dispensadas: int,
) -> Cabecalho:
    """Os quatro cabeçalhos da seção, derivados **numa função só**.

    ``conferidas`` é quantas checagens responderam alguma coisa;
    ``sem_resposta`` é quantas rodaram e não souberam. As duas contagens são
    diferentes de propósito: "conferi 5 coisas" e "5 coisas não deram resposta"
    são afirmações opostas, e a tela que as colapsa é a tela que mente de verde.

    A precedência é de honestidade, não de gravidade: ordem primeiro (há o que
    fazer), depois o que **não soube** (nunca verde), depois a decisão dela, e
    só então o verde. O ``sem_resposta`` passar à frente da dispensa é o que
    impede o terceiro caso de se disfarçar do quarto.
    """
    if ordens:
        return Cabecalho(
            chave=TOPO_HA_ORDENS,
            texto=f"{len(ordens)} "
            + _plural(
                len(ordens), "mudança recomendada", "mudanças recomendadas"
            ),
            estado="atencao",  # (noqa-acento): chave de máquina, ASCII por contrato
        )
    if sem_resposta:
        return Cabecalho(
            chave=TOPO_ALGUMA_NAO_SOUBE,
            texto=(
                f"Conferi {conferidas} "
                + _plural(conferidas, "coisa", "coisas")
                + f"; {sem_resposta} não "
                + _plural(sem_resposta, "deu", "deram")
                + " resposta."
            ),
            estado="nao_sei",
            botao="Ver quais",
        )
    if dispensadas:
        return Cabecalho(
            chave=TOPO_NADA_NOVO,
            texto=(
                f"Nada novo. {dispensadas} "
                + _plural(dispensadas, "recomendação", "recomendações")
                + " você dispensou."
            ),
            estado="certo",
            botao="Ver",
        )
    return Cabecalho(
        chave=TOPO_NADA_A_MUDAR,
        texto=(
            f"Nada a mudar. Conferi {conferidas} "
            + _plural(conferidas, "coisa", "coisas")
            + " agora."
        ),
        estado="certo",
        botao="Ver o que conferi",
    )


# ---------------------------------------------------------------------------
# Interno
# ---------------------------------------------------------------------------


def _classe_de(aparelho: Aparelho) -> tuple[str, str, str]:
    return (aparelho.classe, aparelho.subclasse, aparelho.protocolo)


def _e_bluetooth(aparelho: Aparelho) -> bool:
    """A tripla do kernel diz Bluetooth — e nada mais diz.

    Não há caminho por nome de produto, e é de propósito: o ``product`` de dois
    dongles idênticos desta bancada diverge ("UB500 Adapter" e "Bluetooth USB
    Adapter"), e adivinhar por texto é como se erra com confiança.
    """
    return _classe_de(aparelho) == _CLASSE_BLUETOOTH


def _bluetooth_do_censo(censo: Censo) -> tuple[Aparelho, ...]:
    return tuple(a for a in censo.conectados() if _e_bluetooth(a))


def _irradia(leitura: Leitura, numero: str) -> bool:
    """O que está NESTA entrada usa 2,4 GHz?

    Duas fontes, e as duas são afirmação de alguém: o kernel, que classificou o
    aparelho como Bluetooth; e ela, que declarou o que o aparelho é. Nada de
    heurística — a webcam de cabo desta bancada estava sendo acusada por uma
    régua que só olhava a distância.
    """
    caminho = leitura.ocupante_da_entrada.get(numero, "")
    if not caminho:
        return False
    for aparelho in leitura.censo.conectados():
        if aparelho.nome_do_kernel != caminho:
            continue
        if _e_bluetooth(aparelho):
            return True
        tipo = leitura.tipos_declarados.get(f"{aparelho.vid}:{aparelho.pid}", "")
        return bool(tipo) and tipo != "webcam"
    return False


def _nome_do_aparelho(leitura: Leitura, aparelho: Aparelho) -> str:
    """Como a ordem chama o aparelho — pelo que ELA declarou, ou pela ausência.

    Com declaração, o nome dela. Sem declaração, "um aparelho que você ainda não
    identificou" — e **nunca** o ``product``. É a diferença entre a tela repetir
    o que o fabricante escreveu e a tela afirmar o que a máquina sabe.
    """
    nome = leitura.nomes_declarados.get(f"{aparelho.vid}:{aparelho.pid}", "").strip()
    return nome or "um aparelho que você ainda não identificou"


def _com_maiuscula(texto: str) -> str:
    return texto[:1].upper() + texto[1:] if texto else texto


def _identidade_de(leitura: Leitura, aparelho: Aparelho) -> Identidade:
    return _identidade_do_caminho(leitura, aparelho.nome_do_kernel)


def _identidade_do_caminho(leitura: Leitura, caminho: str) -> Identidade:
    """A identidade do aparelho que está neste caminho — sem ler serial nenhum.

    A ambiguidade que importa aqui é a que :func:`identidades` calcula com o
    serial; quem quiser essa resposta chama aquela função e a costura. O que
    esta devolve é a identidade CRUA, e a ambiguidade dela é a que se enxerga
    sem abrir arquivo: dois aparelhos de mesmo ``vid:pid`` na mesa.
    """
    for aparelho in leitura.censo.conectados():
        if aparelho.nome_do_kernel != caminho:
            continue
        iguais = sum(
            1
            for outro in leitura.censo.conectados()
            if (outro.vid, outro.pid) == (aparelho.vid, aparelho.pid)
        )
        return Identidade(
            vid=aparelho.vid,
            pid=aparelho.pid,
            caminho=caminho,
            ambigua=iguais > 1,
        )
    return Identidade(caminho=caminho)


def _velocidade_do_hub(censo: Censo, aparelho: Aparelho) -> float:
    """A velocidade do hub imediatamente acima — ``0.0`` quando não dá para ler."""
    por_no = {a.no: a for a in censo.aparelhos}
    pai = por_no.get(aparelho.pai)
    return pai.velocidade_mbps if pai is not None else 0.0


def _furos_livres(leitura: Leitura) -> tuple[Furo, ...]:
    """Os BURACOS vazios que uma pessoa alcança com a mão.

    Buraco, e nunca nó: um buraco USB 3.x aparece no ``/sys`` como dois nós
    amarrados pelo ``peer``, e o lado 3.0 do buraco onde o mouse dela está
    responde ``not attached``. Mandar encaixar ali seria mandá-la ao buraco que
    já tem aparelho. Quem agrupa é ``entradas_do_gabinete.furos`` — a régua é
    uma só, e não se reimplementa aqui.
    """
    return tuple(
        furo
        for furo in furos(leitura.entradas)
        if furo.vazio and furo.tipo_de_encaixe == ENCAIXE_DE_GENTE
    )


def _livres_fora_da_controladora(
    leitura: Leitura, controlador_pci: str
) -> tuple[Furo, ...]:
    """Os buracos livres que NÃO pendem da mesma controladora do aparelho.

    É a contra-regra em forma de filtro: mover o dongle para outro buraco do
    mesmo hub não muda o caminho que ele divide, e mover um dongle para perto de
    outro dongle é o que R3 nunca faz. Sem ``controlador_pci`` legível (o campo
    pode faltar), nenhum buraco é oferecido — silêncio é melhor que um destino
    que não ajuda.
    """
    if not controlador_pci:
        return ()
    controlador_por_hub = {
        aparelho.nome_do_kernel: aparelho.controlador_pci
        for aparelho in leitura.censo.aparelhos
    }
    achados: list[Furo] = []
    for furo in _furos_livres(leitura):
        controladores = {
            controlador_por_hub.get(no.hub, "") for no in furo.entradas
        }
        if controlador_pci in controladores:
            continue
        achados.append(furo)
    return tuple(achados)


def _destino_declarado(leitura: Leitura) -> str:
    """A primeira entrada livre pelo NÚMERO dela — ``""`` quando não há desenho.

    Vem de ``mapa_das_portas.portas_livres``, já calculada por quem chama. É a
    ÚNICA fonte possível de um destino: o desenho é declarado, nunca deduzido —
    as duas entradas da frente do gabinete desta bancada são byte a byte iguais
    nos três campos que o kernel decodifica.
    """
    declaradas = leitura.entradas_livres_declaradas
    return declaradas[0] if declaradas else ""


def _acao(verbo: str, quantos_livres: int, destino: str) -> str:
    """O imperativo da ordem — e ele diz o que falta para virar um endereço.

    Três formas, e a diferença entre a segunda e a terceira é
    ``D-O-QUE-O-PRODUTO-DIZ-SEM-SABER``:

    * **com destino**: "… para a entrada 4". Ela desenhou, e o produto aponta;
    * **sem destino e com buraco livre**: "… para uma entrada do próprio
      computador — há 9 livres." mais :data:`NAO_DECLARADO`. O produto CONTA o
      que mediu e diz exatamente o que falta para ele conseguir apontar. Isso
      não é "não sei": é "só você sabe";
    * **sem buraco livre**: string vazia. A ordem nasce **sem ação** — ela conta
      o que viu, e cala sobre o que fazer, porque não há o que fazer. Um
      imperativo que manda mover para lugar nenhum é pior que silêncio.

    O ``/sys`` sabe CONTAR buracos livres e não sabe onde eles ficam no metal:
    ``usb1-port5`` não é um lugar que uma pessoa ache atrás do gabinete, e
    publicá-lo seria trocar uma ausência honesta por jargão.
    """
    if not quantos_livres:
        return ""
    if destino:
        return f"{verbo} para a entrada {destino}"
    return (
        f"{verbo} para uma entrada do próprio computador — há "
        f"{quantos_livres} "
        + _plural(quantos_livres, "livre", "livres")
        + f". {NAO_DECLARADO}"
    )


def _assinatura(pares: Sequence[tuple[Aparelho, Aparelho]]) -> str:
    return _assinatura_de_caminhos(
        [(alvo.nome_do_kernel, acusador.nome_do_kernel) for alvo, acusador in pares]
    )


def _assinatura_de_caminhos(pares: Iterable[tuple[str, str]]) -> str:
    """A assinatura do arranjo: os caminhos de barramento, e nada mais.

    Não carrega serial, não carrega endereço, não carrega o número da entrada —
    ela precisa mudar quando os CABOS mudam, e o número da entrada é o desenho
    dela, que pode mudar sem nenhum cabo sair do lugar.
    """
    partes = sorted(
        "|".join(parte for parte in par if parte) for par in pares
    )
    return " ".join(parte for parte in partes if parte)


def _velocidade(mbps: float) -> str:
    """A velocidade do kernel na palavra que a pessoa lê no cabo.

    O sysfs responde em Mb/s (``5000``); o que está escrito na embalagem e no
    conector é ``5 Gbps``. Traduzir é a tela falando a língua do metal — não é
    arredondar medição, porque o número é exatamente o mesmo.
    """
    if mbps >= 1000:
        gbps = mbps / 1000
        inteiro = int(gbps)
        return f"{inteiro} Gbps" if gbps == inteiro else f"{gbps:.1f} Gbps"
    return f"{int(mbps)} Mb/s"


def _plural(quantos: int, singular: str, plural: str) -> str:
    """Uma das duas palavras, pela contagem. ``0`` usa o plural, como em
    português: "0 entradas livres"."""
    return singular if quantos == 1 else plural


__all__ = [
    "DERIVADO_DA_CONTA",
    "ESPECIFICACAO_DE_TERCEIRO",
    "MEDIDO_AQUI",
    "NAO_DECLARADO",
    "NAO_MEDI",
    "SELOS",
    "TEXTO_DO_SELO",
    "Cabecalho",
    "Identidade",
    "Leitura",
    "Linha",
    "Ordem",
    "cabecalho",
    "catalogo",
    "identidades",
    "mesmo_hub_fisico",
    "ordens_caladas",
    "ordens_novas",
    "resposta_ao_ja_movi",
]
