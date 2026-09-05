"""arranjo_da_mesa.py — o motor que decide o arranjo da mesa.

Porte para Python do motor que existia só em JavaScript, dentro de
``docs/process/sprints/2026-08-24-ABA-CONEXOES/mockup/mapa-das-portas.html`` —
1058 linhas de lógica, testadas em 29 estados pela ``fumaca.js`` e em nenhuma
linha do produto. Sprint ``MOTOR-DO-ARRANJO-01``.

O MODELO, E ELE É A VIRADA
---------------------------

O mapa **não** guarda *"a entrada 9 tem um Bluetooth"*. Guarda *"a entrada 9 **é**
o caminho ``3-1.2``"*::

    mapa     : entrada -> caminho de barramento   (declarado UMA vez)
    leitura  : aparelho -> caminho                (medido AGORA, do sysfs)
    alocação : entrada -> aparelho                (DERIVADO: junta os dois)

Quando alguém troca um aparelho de lugar, o **caminho** muda e o **serial** não.
Com o modelo antigo o mapa passava a mentir; com este, o produto reconhece
sozinho quem foi para onde, sem a pessoa declarar nada de novo.

O QUE ESTE MÓDULO NÃO FAZ
--------------------------

**Não lê nada.** Sem GTK, sem IPC, sem ``/dev``, sem ``/sys``, sem
``subprocess``, sem rede. Quem lê o barramento é ``integrations/mesa_de_radio.py``
e ``integrations/censo_do_barramento.py``; este módulo recebe a leitura e o mapa
como argumento e devolve estrutura. É isso que o torna testável sem hardware —
e é a única razão de a equivalência com o mockup ser demonstrável.

A única coisa que ele importa do produto são as **constantes medidas do rádio**,
de ``integrations/radio_da_mesa.py`` (§10). Elas moravam aqui copiadas e
arredondadas, e essa cópia era a segunda verdade que a casa mais paga para
matar; ver a nota da D-OS-NUMEROS-DO-RADIO-TEM-UM-DONO-SO no §10.

AS DUAS REGRAS QUE SALVAM A CREDIBILIDADE
------------------------------------------

1. **Ficar parado vale bônus** (``Opcoes.bonus_parado``, ``+1`` por omissão): só
   desempata, nunca vence uma escolha melhor.
2. **Intercambiável não troca com o irmão**: dois aparelhos de mesma classe e
   mesmo modelo não trocam de lugar entre si — o conjunto de entradas é o mesmo
   e cada troca evitada é um movimento a menos.

Sem as duas, o plano mandava movimentos inúteis. A mordida delas está em
``tests/unit/test_arranjo_invariantes.py``, que arranca uma de cada vez e conta.

O QUE SE PERDE SAI EM PALAVRA, NUNCA EM PONTOS
-----------------------------------------------

``consequencias()`` devolve frases. *"437 pontos pior"* não diz nada a ninguém;
*"os dongles ficam na altura da escrivaninha, não no alto do rack"* diz.
``qualidade()`` existe só para ordenar variantes entre si e **não vai para a
tela**.

DIVERGÊNCIAS DECLARADAS ENTRE ESTE PORTE E O MOCKUP
-----------------------------------------------------

Todas são generalizações que dão a MESMA saída em todos os cenários medidos:

* o mockup acha o Wi-Fi e o hub pelo ``id`` literal ``"wifi"``/``"hub"``; aqui
  eles saem pela **classe**, que é o que o censo do barramento entrega;
* ``julgar()`` e ``planejar()`` recebem o estado por argumento em vez de lê-lo
  de variável de módulo;
* onde o mockup estouraria (entrada do mapa que não existe em face nenhuma), o
  porte trata como *"não tem entrada de hoje"*.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from hefesto_dualsense4unix.integrations.radio_da_mesa import (
    HZ_AUDIO_COM_MIC,
    HZ_INPUT_COM_MIC,
    HZ_INPUT_SEM_MIC,
    SLOTS_POR_RELATORIO,
    SLOTS_POR_SEGUNDO,
)

# ══ 1. O VOCABULÁRIO ═════════════════════════════════════════════════════

#: entrada -> caminho de barramento. Declarado uma vez, envelhece devagar.
Mapa = Mapping[str, str]
#: id do aparelho -> caminho de barramento. Medido agora, envelhece num cabo.
Leitura = Mapping[str, str]

SELO_MEDIDO = "medido"
SELO_DERIVADO = "derivado"
SELO_ESPEC = "espec"

CLASSES_DE_RADIO = frozenset({"bt", "wifi", "teclado", "mouse"})

#: a ordem de decisão: quem tem exigência dura escolhe antes.
ORDEM_DE_DECISAO = ("hub", "teclado", "wifi", "bt", "mouse", "webcam")


@dataclass(frozen=True)
class Aparelho:
    """Um aparelho da mesa, como o censo do barramento o entrega."""

    id: str
    tipo: str
    nome: str
    classe: str


@dataclass(frozen=True)
class Entrada:
    """Uma entrada USB do gabinete ou do hub, como ela a numerou na foto."""

    n: str
    usb: int
    onde: str
    par: str | None = None
    pos: int | None = None
    esticada: bool = False
    filho: Entrada | None = None


@dataclass(frozen=True)
class Face:
    """Uma face do gabinete (frente, traseira) ou o hub."""

    nome: str
    regiao: str
    entradas: tuple[Entrada, ...]
    perto: bool = False
    alto: bool = False


@dataclass(frozen=True)
class Mesa:
    """Tudo que o motor precisa saber, e nada que ele precise ir buscar."""

    aparelhos: tuple[Aparelho, ...]
    faces: tuple[Face, ...]
    mapa: Mapa
    leitura: Leitura


@dataclass(frozen=True)
class Opcoes:
    """A restrição de uma variante. ``proibir`` recusa uma entrada inteira."""

    bonus_parado: int = 1
    proibir: Callable[[Entrada], bool] | None = None


@dataclass(frozen=True)
class Razao:
    """Um porquê, com o grau de quem o afirma."""

    selo: str
    texto: str


@dataclass(frozen=True)
class Contexto:
    """O que a entrada não sabe sozinha: a face, o vizinho e o hub."""

    perto: bool
    vizinho_radio: bool
    superspeed_no_hub: bool


@dataclass(frozen=True)
class Regra:
    """Uma linha da tabela de notas."""

    n: int
    quando: Callable[[Entrada, Contexto], bool]
    selo: str
    texto: str
    essencial: bool = False


@dataclass(frozen=True)
class Nota:
    n: int
    razoes: tuple[Razao, ...]
    peso: str


@dataclass(frozen=True)
class Motivo:
    """Por que este aparelho vai para esta entrada, e quanto isso vale."""

    razoes: tuple[Razao, ...]
    peso: str
    ganho: float
    forcado: bool
    essencial: bool


@dataclass(frozen=True)
class Plano:
    """entrada -> aparelho, e o motivo de cada um."""

    plano: Mapping[str, str]
    motivo: Mapping[str, Motivo]


@dataclass(frozen=True)
class Linha:
    selo: str
    texto: str


@dataclass(frozen=True)
class Movimento:
    """Uma ordem de serviço: o que fazer, e de onde eu sei."""

    titulo: str
    linhas: tuple[Linha, ...]
    essencial: bool = False
    ganho: float = 0.0
    sem_numero: bool = False


@dataclass(frozen=True)
class Veredito:
    """O julgamento de uma entrada para o aparelho que está na mão."""

    v: str
    texto: str
    porque: str


@dataclass(frozen=True)
class Mudanca:
    """Um aparelho que mudou de caminho entre duas leituras."""

    aparelho: Aparelho
    antes: str | None
    agora: str | None
    entrada_antes: str | None
    entrada_agora: str | None


@dataclass(frozen=True)
class SemEntrada:
    """Um aparelho que a leitura vê e o mapa não sabe onde está."""

    aparelho: Aparelho
    caminho: str
    regiao: str | None


@dataclass(frozen=True)
class Adaptador:
    id: str
    entrada: str | None
    rotulo: str


@dataclass(frozen=True)
class Controle:
    """Um controle e o adaptador em que ele JÁ está — o bond nasce preso."""

    nome: str
    mic: bool
    onde: str


@dataclass(frozen=True)
class PlanoDosControles:
    adaptadores: tuple[Adaptador, ...]
    #: fatias por segundo já comprometidas em cada adaptador. É FLOAT porque o
    #: número medido é 260,4 / 276,7 — arredondar aqui recriaria a cópia que a
    #: D-OS-NUMEROS-DO-RADIO-TEM-UM-DONO-SO acabou de matar.
    carga: Mapping[str, float]
    destino: Mapping[str, str]
    cabe: bool
    sobra: int


@dataclass(frozen=True)
class Variante:
    id: str
    rotulo: str
    descricao: str
    opcoes: Opcoes = field(default_factory=Opcoes)


# ══ 2. AS PEÇAS QUE TODO O RESTO USA ═════════════════════════════════════

_SO_DIGITOS = re.compile(r"^(0|[1-9][0-9]*)$")
_CAMINHO = re.compile(r"^(\d+)-(.+)$")


def _chaves_em_ordem_js(d: Mapping[str, object]) -> list[str]:
    """As chaves na ordem em que o JavaScript as percorre.

    ``Object.keys`` põe as chaves que parecem índice em ordem numérica
    crescente e só depois as demais, em ordem de inserção. Um dicionário Python
    devolve tudo em ordem de inserção. A diferença só aparece quando dois
    caminhos iguais disputam a mesma entrada — e é exatamente o tipo de
    divergência silenciosa que este porte existe para não ter.
    """
    inteiras = sorted((k for k in d if _SO_DIGITOS.match(k)), key=int)
    vistas = set(inteiras)
    return inteiras + [k for k in d if k not in vistas]


def todas_as_entradas(faces: Iterable[Face]) -> list[Entrada]:
    """Todas as entradas de todas as faces, incluindo as da ponta do extensor."""
    fora: list[Entrada] = []
    for face in faces:
        for entrada in face.entradas:
            fora.append(entrada)
            if entrada.filho is not None:
                fora.append(entrada.filho)
    return fora


def por_num(faces: Iterable[Face], n: str | None) -> Entrada | None:
    """A entrada de número ``n``, ou ``None`` se ela não existe em face nenhuma."""
    if n is None:
        return None
    for entrada in todas_as_entradas(faces):
        if entrada.n == str(n):
            return entrada
    return None


def _mae_de(faces: Iterable[Face], n: str) -> Entrada | None:
    for entrada in todas_as_entradas(faces):
        if entrada.filho is not None and entrada.filho.n == str(n):
            return entrada
    return None


def _face_da_entrada(faces: Iterable[Face], n: str) -> Face | None:
    for face in faces:
        for entrada in face.entradas:
            if entrada.n == n or (entrada.filho is not None and entrada.filho.n == n):
                return face
    return None


def _acha(mesa: Mesa, ident: str | None) -> Aparelho | None:
    if ident is None:
        return None
    for aparelho in mesa.aparelhos:
        if aparelho.id == ident:
            return aparelho
    return None


def _classe_de(mesa: Mesa, ident: str | None) -> str | None:
    aparelho = _acha(mesa, ident)
    return aparelho.classe if aparelho else None


def eh_radio(classe: str | None) -> bool:
    """Emite em 2,4 GHz e, portanto, atrapalha e é atrapalhado por vizinho."""
    return classe in CLASSES_DE_RADIO


def entrada_de_em(plano: Mapping[str, str], ident: str) -> str | None:
    """A entrada que este aparelho ocupa dentro de um plano (ou da alocação)."""
    for entrada, quem in plano.items():
        if quem == ident:
            return entrada
    return None


def ocupada(faces: Iterable[Face], plano: Mapping[str, str], entrada: Entrada) -> bool:
    """Um dongle na entrada-filha ocupa também a entrada-mãe: o extensor está nela."""
    if entrada.n in plano:
        return True
    if entrada.filho is not None and entrada.filho.n in plano:
        return True
    mae = _mae_de(faces, entrada.n)
    return bool(mae is not None and mae.n in plano)


# ══ 3. O QUE SE DERIVA DA LEITURA ════════════════════════════════════════


def alocacao(mapa: Mapa, leitura: Leitura) -> dict[str, str]:
    """entrada -> id do aparelho. **Derivado**, nunca guardado.

    A versão que lia uma alocação em cache dava resposta VELHA depois de um
    reexame: o dongle que ela moveu ainda era relatado na entrada antiga.
    """
    fora: dict[str, str] = {}
    for entrada in _chaves_em_ordem_js(mapa):
        caminho = mapa[entrada]
        for ident, medido in leitura.items():
            if medido == caminho:
                fora[entrada] = ident
                break
    return fora


def caminho_do_hub(mesa: Mesa) -> str | None:
    """O caminho do hub externo AGORA — ``None`` quando ele não está na mesa.

    Às 02h36 de 25/08/2026 o hub dela saiu do barramento e levou os três
    adaptadores Bluetooth junto. Sem hub não há topologia de hub para deduzir,
    e a resposta honesta de ``regiao_do_caminho`` passa a ser ``None``.
    """
    for aparelho in mesa.aparelhos:
        if aparelho.classe == "hub":
            return mesa.leitura.get(aparelho.id)
    return None


def regiao_do_caminho(caminho: str | None, caminho_hub: str | None) -> str | None:
    """``"hub"``, ``"pc"`` ou ``None`` — deduzido do barramento, não chutado.

    ``3-1.1.1`` pende de ``3-1``, que é o hub. Esconder o aparelho por não saber
    a entrada exata é jogar fora metade da informação que existe.

    O lado USB 3.0 do mesmo hub físico aparece noutro barramento (``4-1.x``
    contra ``3-1.x``) porque hub 3.0 é dual-bus — mesmo metal, dois números; daí
    a segunda comparação.
    """
    if not caminho_hub or not caminho:
        return None
    if caminho.startswith(caminho_hub + "."):
        return "hub"
    mh = _CAMINHO.match(caminho_hub)
    mc = _CAMINHO.match(caminho)
    if mh and mc and mc.group(1) != mh.group(1) and mc.group(2).startswith(mh.group(2) + "."):
        return "hub"
    return "pc"


def sem_entrada(mesa: Mesa) -> list[SemEntrada]:
    """Os aparelhos que a leitura vê e o mapa não sabe onde estão.

    Medido na mesa dela em 24/08, com 8 de 16 entradas declaradas: quatro dos
    cinco aparelhos que ela moveu caíram aqui. É o argumento medido para
    declarar as entradas vazias também.
    """
    conhecidos = {mesa.mapa[k] for k in _chaves_em_ordem_js(mesa.mapa)}
    hub = caminho_do_hub(mesa)
    fora: list[SemEntrada] = []
    for aparelho in mesa.aparelhos:
        caminho = mesa.leitura.get(aparelho.id)
        if not caminho or caminho in conhecidos:
            continue
        fora.append(SemEntrada(aparelho, caminho, regiao_do_caminho(caminho, hub)))
    return fora


def candidatas(mesa: Mesa, regiao: str) -> list[Entrada]:
    """As entradas daquela região que ainda não foram declaradas.

    De 16 candidatas para 4, sem ela declarar nada. Isso é dedução, não chute.
    """
    declaradas = set(mesa.mapa)
    alvo = "hub" if regiao == "hub" else "pc"
    return [e for e in todas_as_entradas(mesa.faces) if e.n not in declaradas and e.onde == alvo]


# ══ 4. A TABELA DE NOTAS ═════════════════════════════════════════════════
#
# Cada entrada ganha uma nota por aparelho; ele vai para a de maior nota. Não é
# otimizador global: é nota explicável, porque conselho que a pessoa não entende
# ela não segue.
#
# O selo não é enfeite — é a coluna `de_onde_sei` do mapa de canais, e é o que
# impede raciocínio de se vestir de medição (decisão dela, `D-ORDEM-DE-SERVICO`).

REGRAS: Mapping[str, tuple[Regra, ...]] = {
    "teclado": (
        Regra(100, lambda p, c: p.onde == "pc", SELO_ESPEC, essencial=True,
              texto="entrada direta do PC: hub externo nem sempre é ligado pelo firmware,"
                    " e sem teclado você não entra na BIOS"),
        Regra(20, lambda p, c: c.perto, SELO_DERIVADO,
              texto="na frente, que é a mais perto de você"),
        Regra(-30, lambda p, c: c.vizinho_radio, SELO_ESPEC, essencial=True,
              texto="longe de outro rádio de 2,4 GHz — dois receptores encostados se atrapalham"),
        Regra(-6, lambda p, c: p.usb == 3, SELO_DERIVADO,
              texto="sem gastar uma entrada azul, que ele não usa"),
    ),
    "wifi": (
        Regra(100, lambda p, c: p.onde == "pc", SELO_ESPEC, essencial=True,
              texto="fora do hub: o tráfego dele em 5 Gbps é o que vira ruído em 2,4 GHz"
                    " para os dongles do mesmo hub"),
        Regra(40, lambda p, c: p.usb == 3, SELO_DERIVADO,
              texto="entrada azul, para ele manter a velocidade"),
        Regra(-30, lambda p, c: c.vizinho_radio, SELO_ESPEC, essencial=True,
              texto="sem outro rádio colado"),
    ),
    "bt": (
        Regra(60, lambda p, c: p.onde == "hub", SELO_DERIVADO,
              texto="no alto do rack, com a antena acima da linha das cabeças"),
        Regra(25, lambda p, c: p.esticada, SELO_DERIVADO,
              texto="na ponta do extensor: a antena que fica mais longe das outras"),
        Regra(-120, lambda p, c: p.onde == "hub" and c.superspeed_no_hub, SELO_ESPEC,
              essencial=True,
              texto="sem o Wi-Fi usando o SuperSpeed do mesmo hub"),
        Regra(-45, lambda p, c: c.vizinho_radio, SELO_ESPEC, essencial=True,
              texto="sem outro rádio de 2,4 GHz na entrada colada"),
    ),
    "mouse": (
        Regra(40, lambda p, c: p.onde == "pc", SELO_DERIVADO,
              texto="entrada direta do PC"),
        Regra(-40, lambda p, c: c.vizinho_radio, SELO_ESPEC, essencial=True,
              texto="longe do receptor do teclado — dois rádios de 2,4 GHz encostados"
                    " se atrapalham"),
        Regra(10, lambda p, c: p.usb == 2, SELO_DERIVADO,
              texto="entrada preta, sem gastar a azul que ele não usa"),
    ),
    "webcam": (
        Regra(12, lambda p, c: p.usb == 2, SELO_DERIVADO,
              texto="entrada preta: ela não usa a velocidade da azul,"
                    " e a azul faz falta a quem usa"),
        Regra(6, lambda p, c: p.onde == "pc", SELO_DERIVADO,
              texto="direta do PC, sem gastar entrada do hub"),
    ),
    "hub": (
        Regra(40, lambda p, c: p.onde == "pc", SELO_DERIVADO, essencial=True,
              texto="entrada direta do PC — o hub não pode pendurar em si mesmo"),
        Regra(20, lambda p, c: p.usb == 3, SELO_DERIVADO,
              texto="entrada azul, para o hub entregar o que ele oferece"),
    ),
}


def _bonus_separacao(entrada: Entrada, ja_postos: Sequence[Entrada]) -> tuple[int, Razao | None]:
    """Quanto mais longe do irmão mais próximo, melhor: +6 por posição, teto 6."""
    if not ja_postos or entrada.pos is None:
        return 0, None
    d = min(abs((q.pos or 0) - entrada.pos) for q in ja_postos)
    plural = "ão" if d == 1 else "ões"
    return min(d, 6) * 6, Razao(
        SELO_ESPEC,
        f"com {d} posiç{plural} de folga até o dongle mais próximo"
        " — dois rádios colados se atrapalham",
    )


def _superspeed_no_hub(mesa: Mesa, plano: Mapping[str, str], aloc: Mapping[str, str]) -> bool:
    """O Wi-Fi está (ou vai ficar) numa entrada do hub?"""
    for aparelho in mesa.aparelhos:
        if aparelho.classe != "wifi":
            continue
        onde = entrada_de_em(plano, aparelho.id) or entrada_de_em(aloc, aparelho.id)
        entrada = por_num(mesa.faces, onde)
        return bool(entrada is not None and entrada.onde == "hub")
    return False


def nota_de(
    mesa: Mesa,
    aparelho: Aparelho,
    entrada: Entrada,
    plano: Mapping[str, str],
    ja_postos: Sequence[Entrada],
    aloc: Mapping[str, str],
) -> Nota:
    """A nota deste aparelho nesta entrada, com os porquês que a explicam."""
    face = _face_da_entrada(mesa.faces, entrada.n)
    vizinho: str | None = None
    if entrada.par:
        vizinho = _classe_de(mesa, plano.get(entrada.par) or aloc.get(entrada.par))
    ctx = Contexto(
        perto=bool(face is not None and face.perto),
        vizinho_radio=eh_radio(vizinho),
        superspeed_no_hub=_superspeed_no_hub(mesa, plano, aloc),
    )

    regras = REGRAS.get(aparelho.classe, ())
    n = 0
    razoes: list[Razao] = []
    peso = "melhora"
    for regra in regras:
        if not regra.quando(entrada, ctx):
            continue
        n += regra.n
        if regra.n > 0:
            razoes.append(Razao(regra.selo, regra.texto))
            if regra.essencial:
                peso = "essencial"
    # penalidade que NÃO casou é uma exigência satisfeita: também explica
    for regra in regras:
        if regra.n >= 0 or regra.quando(entrada, ctx):
            continue
        razoes.append(Razao(regra.selo, regra.texto))
        if regra.essencial:
            peso = "essencial"

    if aparelho.classe == "bt":
        bonus, razao = _bonus_separacao(entrada, ja_postos)
        n += bonus
        if bonus > 0 and razao is not None:
            razoes.append(razao)

    return Nota(n=n, razoes=tuple(razoes), peso=peso)


# ══ 5. O PLANEJADOR ══════════════════════════════════════════════════════


def _sem_proibicao(_entrada: Entrada) -> bool:
    return False


def _receita_manda_mover(de: str | None, para: str | None, motivo: Motivo | None) -> bool:
    """A ÚNICA regra de *"isto vira ordem de serviço"* — e ela tem um dono só.

    Ela morava dentro de :func:`receita`, e o mapa (que sai de :func:`planejar`)
    não a consultava. Daí o defeito que a
    ``D-MAPA-SEM-RECEITA`` fechou: nas variantes que PROÍBEM a entrada de hoje o
    desenho mostrava o aparelho no lugar novo e a receita não mandava mexer, e
    quem olhava a tela via o aparelho noutro lugar **sem instrução nenhuma**.

    Agora as duas beiras perguntam a mesma coisa a esta função, e por isso não
    há como discordarem. Arrancá-la (devolver sempre ``True``) faz o mapa E a
    receita voltarem a mandar mexer à toa — é a mordida do §5 de
    ``test_arranjo_invariantes.py``.
    """
    if not para or de == para:
        return False
    # aparelho que ainda não tem lugar no mapa entra sempre: não há "ficar onde
    # está" para comparar. Quem já tem lugar só entra se o movimento MELHORA —
    # ganho infinito é o movimento forçado por terceiro, que também melhora.
    return not de or (motivo is not None and motivo.ganho > 0)


def planejar(mesa: Mesa, op: Opcoes | None = None) -> Plano:
    """O melhor arranjo, e por quê — entrada por entrada."""
    op = op or Opcoes()
    proibida = op.proibir or _sem_proibicao
    aloc = alocacao(mesa.mapa, mesa.leitura)  # nunca planejar sobre leitura velha

    plano: dict[str, str] = {}
    motivo: dict[str, Motivo] = {}
    entradas = [e for e in todas_as_entradas(mesa.faces) if not proibida(e)]
    ja_postos: list[Entrada] = []

    for classe in ORDEM_DE_DECISAO:
        for aparelho in [a for a in mesa.aparelhos if a.classe == classe]:
            livres = [e for e in entradas if not ocupada(mesa.faces, plano, e)]
            if not livres:
                continue
            atual = entrada_de_em(aloc, aparelho.id)

            melhor: Entrada | None = None
            melhor_nota: Nota | None = None
            melhor_efetiva = 0
            for candidata in livres:
                nota = nota_de(mesa, aparelho, candidata, plano, ja_postos, aloc)
                # o bônus de ficar parado só DESEMPATA: nunca troca uma escolha melhor
                efetiva = nota.n + (op.bonus_parado if candidata.n == atual else 0)
                if melhor is None or efetiva > melhor_efetiva:
                    melhor, melhor_nota, melhor_efetiva = candidata, nota, efetiva
            if melhor is None or melhor_nota is None:
                continue

            plano[melhor.n] = aparelho.id
            motivo[aparelho.id] = _motivo_de(
                mesa, aparelho, atual, plano, ja_postos, aloc, melhor_nota
            )
            if aparelho.classe == "bt":
                ja_postos.append(melhor)

    _intercambiaveis_ficam(mesa, plano, motivo, ja_postos, aloc)
    _o_mapa_so_move_o_que_a_receita_manda(mesa, plano, motivo, ja_postos, aloc, proibida)
    return Plano(plano=plano, motivo=motivo)


#: A frase que a receita diz quando a variante tirou do tabuleiro a entrada em
#: que o aparelho está hoje. É o único caso em que ele SAI de um lugar bom sem
#: ganho nenhum, e sem esta linha a ordem de serviço não teria porquê.
_PORQUE_A_VARIANTE_TIROU = "esta opção não usa a entrada {de}, onde ele está hoje"


def _o_mapa_so_move_o_que_a_receita_manda(
    mesa: Mesa,
    plano: dict[str, str],
    motivo: dict[str, Motivo],
    ja_postos: Sequence[Entrada],
    aloc: Mapping[str, str],
    proibida: Callable[[Entrada], bool],
) -> None:
    """``D-MAPA-SEM-RECEITA`` (25/08/2026): se não há ordem, o mapa não move nada.

    **O defeito, medido em 25/08 sobre a mesa dela de 24/08.** Em ``Sem o
    extensor`` e ``Sem usar o hub`` a variante PROÍBE a entrada em que o dongle
    está hoje. O planejador então o realoja — e o mapa desenha isso —, mas a
    nota da entrada nova é PIOR que a da atual (``-25``, ``-60``, ``-130`` nos
    três casos medidos), e a receita, que só manda o que melhora, cala. Quem
    olha a tela vê o aparelho noutro lugar e não recebe instrução nenhuma.

    **A decisão dela**, entre três caminhos — mover e dizer que o ganho é zero,
    baixar o corte para o ganho zero contar, ou este: *"se não há ordem, o mapa
    não move nada. Uma verdade só na tela: o desenho mostra o que a receita
    manda fazer."* O preço, que ela aceitou por escrito: **o mapa passa a
    mostrar MENOS do que o motor calculou** — o aparelho fica desenhado onde
    está, e a melhoria que ele perde não aparece na tela.

    **A ordem importa:** roda DEPOIS de :func:`_intercambiaveis_ficam`, porque
    aquele passe ainda troca destinos entre irmãos e recalcula motivos.

    DUAS ENTRADAS DE HOJE NÃO ACEITAM O APARELHO DE VOLTA, e nas duas o
    movimento vira ORDEM em vez de sumir do mapa — que é a mesma invariante
    vista do outro lado:

    * **a variante proibiu aquela entrada.** ``Sem o extensor`` com o dongle na
      ponta do extensor não pode devolvê-lo para lá: o desenho passaria a
      mostrar, numa opção chamada *sem o extensor*, um dongle no extensor. Aqui
      não existe *"ficar onde está"* para comparar — a entrada saiu do
      tabuleiro —, então o movimento é forçado, e a receita diz por quê com
      :data:`_PORQUE_A_VARIANTE_TIROU`;
    * **outro aparelho ficou com ela** (direto, ou pela mãe do extensor). É o
      mesmo *"forçado por terceiro"* que :func:`_motivo_de` já sabe nomear.
    """
    for aparelho in mesa.aparelhos:
        de = entrada_de_em(aloc, aparelho.id)
        para = entrada_de_em(plano, aparelho.id)
        if not de or not para or de == para:
            continue
        if _receita_manda_mover(de, para, motivo.get(aparelho.id)):
            continue

        entrada_de_hoje = por_num(mesa.faces, de)
        if entrada_de_hoje is None:
            continue  # entrada declarada que não existe em face nenhuma: nada a desenhar

        del plano[para]
        tirada = proibida(entrada_de_hoje)
        volta = not tirada and not ocupada(mesa.faces, plano, entrada_de_hoje)
        destino = de if volta else para
        entrada = entrada_de_hoje if volta else por_num(mesa.faces, para)
        plano[destino] = aparelho.id
        if entrada is None:
            continue
        vizinhos = [q for q in ja_postos if q.n != destino]
        nota = nota_de(mesa, aparelho, entrada, plano, vizinhos, aloc)
        novo = _motivo_de(mesa, aparelho, de, plano, (), aloc, nota)
        if not volta and not novo.forcado:
            novo = Motivo(
                razoes=(Razao(SELO_DERIVADO, _PORQUE_A_VARIANTE_TIROU.format(de=de)),
                        *novo.razoes),
                peso=novo.peso, ganho=math.inf, forcado=True, essencial=True,
            )
        motivo[aparelho.id] = novo


def _motivo_de(
    mesa: Mesa,
    aparelho: Aparelho,
    atual: str | None,
    plano: Mapping[str, str],
    ja_postos: Sequence[Entrada],
    aloc: Mapping[str, str],
    nota: Nota,
) -> Motivo:
    """Quanto este destino melhora — e se o movimento foi forçado por terceiro.

    Se a entrada de hoje foi tomada por outro aparelho no plano, o movimento é
    FORÇADO: não há "ficar onde está" para comparar, e escondê-lo faria o mapa e
    a receita discordarem na tela.
    """
    tomada = bool(atual and plano.get(atual) and plano.get(atual) != aparelho.id)
    entrada_atual = por_num(mesa.faces, atual) if (atual and not tomada) else None
    nota_atual = (
        nota_de(mesa, aparelho, entrada_atual, plano, ja_postos, aloc).n
        if entrada_atual is not None
        else -math.inf
    )
    razoes = list(nota.razoes)
    if tomada and atual is not None:
        outro = _acha(mesa, plano.get(atual))
        razoes.insert(0, Razao(
            SELO_DERIVADO,
            f"a entrada {atual} passou a ser do {outro.tipo if outro else ''},"
            " entao este precisa de outro lugar",
        ))
    ganho = math.inf if tomada else (nota.n - nota_atual)
    return Motivo(
        razoes=tuple(razoes),
        peso=nota.peso,
        ganho=ganho,
        forcado=tomada,
        essencial=tomada or (nota.peso == "essencial" and (nota.n - nota_atual) >= 30),
    )


def _intercambiaveis_ficam(
    mesa: Mesa,
    plano: dict[str, str],
    motivo: dict[str, Motivo],
    ja_postos: Sequence[Entrada],
    aloc: Mapping[str, str],
) -> None:
    """A segunda regra que salva a credibilidade: irmão não troca com irmão.

    Aparelhos de mesma classe E mesmo modelo não têm por que trocar de lugar
    entre si. Se um deles já está numa das entradas de destino, ele fica nela —
    o conjunto de entradas é o mesmo, e cada troca evitada é um movimento a
    menos que ela precisa fazer. Sem isto o plano mandava mover dois UB500
    idênticos entre a 9 e a 15a.
    """
    por_modelo: dict[str, list[Aparelho]] = {}
    for aparelho in mesa.aparelhos:
        por_modelo.setdefault(f"{aparelho.classe}|{aparelho.nome}", []).append(aparelho)

    for grupo in por_modelo.values():
        if len(grupo) < 2:
            continue
        destinos = [d for d in (entrada_de_em(plano, a.id) for a in grupo) if d]
        if len(destinos) < 2:
            continue

        novo: dict[str, str] = {}
        sobram = list(destinos)
        pendentes: list[Aparelho] = []
        for aparelho in grupo:
            hoje = entrada_de_em(aloc, aparelho.id)
            if hoje and hoje in sobram:
                novo[aparelho.id] = hoje
                sobram.remove(hoje)
            else:
                pendentes.append(aparelho)
        for aparelho in pendentes:
            if sobram:
                novo[aparelho.id] = sobram.pop(0)

        for destino in destinos:
            plano.pop(destino, None)
        for aparelho in grupo:
            if aparelho.id in novo:
                plano[novo[aparelho.id]] = aparelho.id

        # o motivo acompanha a ENTRADA, não o aparelho: recalcula para quem mudou
        for aparelho in grupo:
            onde = novo.get(aparelho.id)
            if not onde:
                continue
            entrada = por_num(mesa.faces, onde)
            if entrada is None:
                continue
            vizinhos = [q for q in ja_postos if q.n != onde]
            nota = nota_de(mesa, aparelho, entrada, plano, vizinhos, aloc)
            motivo[aparelho.id] = _motivo_de(
                mesa, aparelho, entrada_de_em(aloc, aparelho.id), plano, (), aloc, nota
            )


# ══ 6. A RECEITA: a diferença entre o que está e o que devia ═════════════


def _rotulo(aparelho: Aparelho) -> tuple[str, str]:
    if aparelho.classe == "bt":
        return "o", "dongle Bluetooth"
    if aparelho.classe == "hub":
        return "o", "cabo do hub"
    if aparelho.classe == "webcam":
        return "a", "webcam"
    return "o", aparelho.tipo.lower()


_FECHO = Movimento(
    titulo="O que muda quando você terminar",
    sem_numero=True,
    linhas=(
        Linha(SELO_DERIVADO,
              "Os dongles ficam no alto e separados, com o Wi-Fi fora do hub deles."),
        Linha(SELO_DERIVADO,
              "<b>Quanto isso melhora o seu Bluetooth não foi medido nesta máquina.</b>"
              " O ensaio que responde conta os quadros que chegam e confere se vieram"
              " inteiros — antes e depois da mudança."),
    ),
)


def receita(mesa: Mesa, op: Opcoes | None = None) -> list[Movimento]:
    """Só entra aqui o que MELHORA.

    Aparelho que já está numa entrada tão boa quanto a melhor candidata fica
    onde está e não vira movimento. Sem esta linha o plano mandava mexer no cabo
    do hub e no mouse à toa.

    Quem decide é :func:`_receita_manda_mover`, e o mapa pergunta à MESMA
    função: desde a ``D-MAPA-SEM-RECEITA`` o desenho não pode mostrar um
    movimento que esta lista não mande.
    """
    resultado = planejar(mesa, op)
    aloc = alocacao(mesa.mapa, mesa.leitura)
    movimentos: list[Movimento] = []

    for aparelho in mesa.aparelhos:
        de = entrada_de_em(aloc, aparelho.id)
        para = entrada_de_em(resultado.plano, aparelho.id)
        motivo = resultado.motivo.get(
            aparelho.id, Motivo((), "melhora", 0.0, forcado=False, essencial=False)
        )
        if not _receita_manda_mover(de, para, motivo):
            continue

        linhas = [_linha_de_hoje(mesa, aparelho, de)]
        for razao in motivo.razoes[:3]:
            linhas.append(Linha(razao.selo, razao.texto[:1].upper() + razao.texto[1:] + "."))

        genero, nome = _rotulo(aparelho)
        titulo = (
            f"Mova {genero} {nome} da entrada {de} para a {para}"
            if de
            else f"Ponha {genero} {nome} na entrada {para}"
        )
        if not motivo.essencial:
            titulo += "  ·  melhora, não é urgente"
        movimentos.append(Movimento(
            titulo=titulo, linhas=tuple(linhas),
            essencial=motivo.essencial, ganho=motivo.ganho,
        ))

    # os essenciais primeiro, e dentro deles o de maior ganho
    movimentos.sort(key=lambda m: (0 if m.essencial else 1, -m.ganho))
    if movimentos:
        movimentos.append(_FECHO)
    return movimentos


def _linha_de_hoje(mesa: Mesa, aparelho: Aparelho, de: str | None) -> Linha:
    if not de:
        return Linha(SELO_MEDIDO, "Ele apareceu no sistema e ainda não tem lugar no mapa.")
    caminho = mesa.leitura.get(aparelho.id) or ""
    entrada = por_num(mesa.faces, de)
    no_hub = entrada is not None and entrada.onde == "hub"
    if no_hub and aparelho.classe == "wifi":
        return Linha(SELO_MEDIDO,
                     "Hoje ele está no hub, e os dois chips do hub enumeram a <b>5000M</b>"
                     " (<code>4-1</code>, <code>4-1.1</code>): o enlace SuperSpeed fica"
                     " treinado, e é o <b>tráfego</b> dele que irradia.")
    if no_hub and aparelho.classe == "teclado":
        return Linha(SELO_MEDIDO, f"Hoje ele está pendurado no hub (<code>{caminho}</code>).")
    return Linha(SELO_MEDIDO, f"Hoje ele está na entrada <b>{de}</b> (<code>{caminho}</code>).")


# ══ 7. O JULGAMENTO POR ENTRADA, no modo "estou segurando" ═══════════════


def julgar(
    entrada: Entrada,
    na_mao: str | None,
    mesa: Mesa,
    segurando: str | None = None,
) -> Veredito | None:
    """O que dizer desta entrada para o aparelho que está na mão dela."""
    aloc = alocacao(mesa.mapa, mesa.leitura)

    quem = aloc.get(entrada.n)
    if quem:
        aparelho = _acha(mesa, quem)
        tipo = aparelho.tipo if aparelho else ""
        return Veredito("cheia", "ocupada", f"{tipo} — clique para tirar")
    if ocupada(mesa.faces, aloc, entrada):
        return Veredito("cheia", "indisponível",
                        "o extensor está nela" if entrada.filho else "a entrada-mãe está em uso")

    if segurando:
        regiao = regiao_do_caminho(mesa.leitura.get(segurando), caminho_do_hub(mesa))
        mesma = regiao is None or (
            entrada.onde == "hub" if regiao == "hub" else entrada.onde == "pc"
        )
        if not mesma:
            return Veredito("fora", "outra região",
                            "este está no hub" if regiao == "hub" else "este está direto no PC")

    if not na_mao:
        return None

    no_hub = entrada.onde == "hub"
    vizinho = _acha(mesa, aloc.get(entrada.par)) if entrada.par else None
    vz_radio = vizinho is not None and eh_radio(vizinho.classe)
    colada = (
        f"colada no {vizinho.tipo}, na entrada {entrada.par}" if vizinho else ""
    )
    superspeed = _superspeed_no_hub(mesa, {}, aloc)

    if na_mao == "bt":
        if no_hub and superspeed:
            return Veredito("ruim", "evite", "o Wi-Fi usa o SuperSpeed deste mesmo hub,"
                                             " e esse tráfego vira ruído em 2,4 GHz")
        if vz_radio:
            return Veredito("evite", "vale evitar", colada)
        if entrada.esticada:
            return Veredito("melhor", "melhor lugar",
                            "na ponta do extensor: a antena mais longe das outras")
        if no_hub:
            return Veredito("melhor", "melhor lugar",
                            "no alto do rack, com a antena acima das cabeças")
        # A PALAVRA "mesa" SAIU DA TELA — 05/09/2026, ordem dela: *"muda o termo
        # pra objeto e sinônimos nesses casos"*. Aqui o sentido é ALTURA FÍSICA,
        # e o contraste com "no alto do rack" (duas linhas acima) é o que a frase
        # vende: "escrivaninha" o diz inteiro, sem a palavra.
        return Veredito("serve", "serve", "entrada direta, mas na altura da escrivaninha")

    if na_mao == "wifi":
        if no_hub:
            return Veredito("ruim", "evite",
                            "aqui o tráfego dele em 5 Gbps fica ao lado dos dongles do controle")
        if entrada.usb != 3:
            return Veredito("evite", "vale evitar", "entrada preta — o Wi-Fi perde velocidade")
        if vz_radio:
            return Veredito("evite", "vale evitar", colada)
        return Veredito("melhor", "melhor lugar",
                        "azul, direta do PC e longe das antenas de rádio")

    if na_mao == "teclado":
        if no_hub:
            return Veredito("ruim", "evite", "no hub você pode ficar sem teclado na BIOS")
        if vz_radio:
            return Veredito("evite", "vale evitar", colada)
        return Veredito("melhor", "melhor lugar",
                        "direta do PC — funciona na BIOS e na recuperação")

    if na_mao == "mouse":
        if vz_radio:
            return Veredito("evite", "vale evitar", colada)
        if no_hub and superspeed:
            return Veredito("evite", "vale evitar", "hub com o tráfego do Wi-Fi ao lado")
        if entrada.usb == 3:
            return Veredito("serve", "serve", "gasta uma entrada azul que ele não usa")
        return Veredito("melhor", "melhor lugar", "entrada preta, longe de outro rádio")

    if na_mao == "webcam":
        if entrada.usb == 3:
            return Veredito("serve", "serve", "gasta uma entrada azul que ela não precisa")
        return Veredito("melhor", "melhor lugar", "entrada preta, que é o que ela pede")

    return None


# ══ 8. AS VARIANTES, com o preço em PALAVRA ══════════════════════════════
#
# Um arranjo só não serve: o melhor no papel pode ser impossível na mesa — o cabo
# não alcança, o hub está longe, a entrada de trás é inacessível. Cada variante é
# a MESMA regra com uma restrição declarada.

VARIANTES: tuple[Variante, ...] = (
    Variante("melhor", "O melhor no papel",
             "Sem restrição: o arranjo que a regra escolhe quando tudo é possível.",
             Opcoes()),
    Variante("poucos", "Mexendo o mínimo",
             "Aceita um lugar pior para você mexer em menos coisas."
             " Bom quando desmontar a mesa custa caro.",
             Opcoes(bonus_parado=45)),
    Variante("sem-ext", "Sem o extensor",
             "Para quando o cabo de extensão não alcança onde você queria,"
             " ou você não quer usá-lo.",
             Opcoes(proibir=lambda p: p.esticada)),
    Variante("so-pc", "Sem usar o hub",
             "Só as entradas do gabinete. É o caso de quem não tem hub — e de notebook.",
             Opcoes(proibir=lambda p: p.onde == "hub")),
)


def variante_por_id(ident: str) -> Variante:
    for variante in VARIANTES:
        if variante.id == ident:
            return variante
    return VARIANTES[0]


def consequencias(mesa: Mesa, op: Opcoes | None = None) -> list[str]:
    """O que se perde nesta variante, **em palavra**.

    *"437 pontos pior"* não diz nada a ninguém; a pessoa precisa saber O QUÊ
    fica pior, para decidir se aceita.
    """
    plano = planejar(mesa, op).plano
    fora: list[str] = []

    bts = [
        e for e in (
            por_num(mesa.faces, entrada_de_em(plano, a.id))
            for a in mesa.aparelhos if a.classe == "bt"
        ) if e is not None
    ]
    no_alto = sum(1 for e in bts if e.onde == "hub")
    if bts and no_alto == 0:
        fora.append("os dongles ficam na altura da escrivaninha, não no alto do rack")
    elif no_alto < len(bts):
        fora.append(f"{len(bts) - no_alto} dongle(s) fora do alto")
    if not any(e.esticada for e in bts):
        fora.append("o extensor não é usado")

    poss = sorted(e.pos for e in bts if e.pos is not None)
    if len(poss) > 1 and min(poss[i + 1] - poss[i] for i in range(len(poss) - 1)) <= 1:
        fora.append("dois dongles ficam em entradas coladas")

    colados = 0
    for aparelho in mesa.aparelhos:
        if not eh_radio(aparelho.classe):
            continue
        entrada = por_num(mesa.faces, entrada_de_em(plano, aparelho.id))
        if entrada is None or not entrada.par:
            continue
        if eh_radio(_classe_de(mesa, plano.get(entrada.par))):
            colados += 1
    if colados:
        fora.append(f"{-(-colados // 2)} par(es) de rádio ficam colados")
    return fora


def qualidade(mesa: Mesa, op: Opcoes | None = None) -> int:
    """A nota total de um plano. **Só** para ordenar variantes entre si.

    Nunca vai para a tela: quem vai é ``consequencias()``.
    """
    resultado = planejar(mesa, op)
    aloc = alocacao(mesa.mapa, mesa.leitura)
    total = 0
    ja_postos: list[Entrada] = []
    for aparelho in mesa.aparelhos:
        onde = entrada_de_em(resultado.plano, aparelho.id)
        if not onde:
            total -= 60
            continue
        entrada = por_num(mesa.faces, onde)
        if entrada is None:
            continue
        total += nota_de(mesa, aparelho, entrada, resultado.plano, ja_postos, aloc).n
        if aparelho.classe == "bt":
            ja_postos.append(entrada)
    return total


# ══ 9. A RE-IDENTIFICAÇÃO POR SERIAL ═════════════════════════════════════


def reexame(mesa: Mesa, antes: Leitura, agora: Leitura) -> list[Mudanca]:
    """Quem mudou de lugar entre duas leituras — e para onde, quando dá para saber.

    O caminho de barramento de quem foi movido é outro; o **serial** não. É por
    ele que o produto sabe quem foi para onde, sem ela declarar nada.

    Medido em 24/08, duas leituras com 1h50 de intervalo: cinco aparelhos
    mudaram e só o teclado caiu numa entrada declarada. O não-reconhecido também
    ensina — é o argumento para declarar as entradas vazias também.
    """
    por_caminho: dict[str, str] = {}
    for entrada in _chaves_em_ordem_js(mesa.mapa):
        por_caminho[mesa.mapa[entrada]] = entrada

    mudou: list[Mudanca] = []
    for aparelho in mesa.aparelhos:
        de = antes.get(aparelho.id)
        para = agora.get(aparelho.id)
        if de == para:
            continue
        mudou.append(Mudanca(
            aparelho=aparelho, antes=de, agora=para,
            entrada_antes=por_caminho.get(de) if de else None,
            entrada_agora=por_caminho.get(para) if para else None,
        ))
    return mudou


# ══ 10. OS CONTROLES ═════════════════════════════════════════════════════
#
# A CONTA, medida (A/B de 25/07/2026, `integrations/dualsense_bt_audio.py:76-78`):
#   sem microfone .. 260,4 relatórios por segundo
#   com microfone .. 276,7  (o áudio NÃO abre canal novo: divide a fila:
#                            170,5 de entrada + 106,2 de áudio)
# Gatilho, vibração, barra de luz, giroscópio e touch andam no MESMO canal HID —
# eles não somam pacote. **Só o microfone muda a conta.**
#
# O NÚMERO TEM UM DONO SÓ, e não é este módulo. Até 25/08/2026 estas três linhas
# guardavam `260`, `277` e `1600` — literais copiados do mockup, ARREDONDADOS.
# O dono é `integrations/radio_da_mesa.py`, que tem portão contra a linha 23 de
# `docs/data/mapa-controles.csv` (`test_radio_da_mesa_bate_com_o_mapa.py`); este
# módulo estava FORA desse portão, então remedir o A/B corrigia o dono e deixava
# o motor mentindo com tudo verde. Agora as três saem de lá por IMPORTAÇÃO —
# nunca por cópia —, e por isso não há como divergirem.
# D-OS-NUMEROS-DO-RADIO-TEM-UM-DONO-SO (25/08/2026): corrigir nos DOIS, Python E
# mockup, que é a regra da casa aplicada inteira — fato errado sai de todos os
# lugares onde aparece. O mockup que ela abre mudou de número, e é o preço aceito.

#: Fatias por segundo de um controle **sem** microfone.
CUSTO_SEM_MIC = HZ_INPUT_SEM_MIC * SLOTS_POR_RELATORIO
#: Fatias por segundo de um controle **com** o microfone de pé — as duas metades
#: da mesma fila somadas, porque o áudio não abre canal novo.
CUSTO_COM_MIC = (HZ_INPUT_COM_MIC + HZ_AUDIO_COM_MIC) * SLOTS_POR_RELATORIO
#: O teto do rádio, por adaptador. Especificação do Bluetooth Classic.
SLOTS = SLOTS_POR_SEGUNDO


def adaptadores_da_mesa(mesa: Mesa) -> tuple[Adaptador, ...]:
    """Os adaptadores Bluetooth e a entrada de cada um, quando ela é sabida."""
    aloc = alocacao(mesa.mapa, mesa.leitura)
    fora: list[Adaptador] = []
    for aparelho in mesa.aparelhos:
        if aparelho.classe != "bt":
            continue
        entrada = entrada_de_em(aloc, aparelho.id)
        fora.append(Adaptador(
            id=aparelho.id, entrada=entrada,
            rotulo=f"entrada {entrada}" if entrada else "entrada por confirmar",
        ))
    return tuple(fora)


def _custo(controle: Controle) -> float:
    return CUSTO_COM_MIC if controle.mic else CUSTO_SEM_MIC


def plano_dos_controles(
    controles: Sequence[Controle],
    adaptadores: Sequence[Adaptador],
) -> PlanoDosControles:
    """Em qual adaptador cada controle deve ficar.

    A regra que salva o conselho: parte-se de onde cada um JÁ está, e só se move
    alguém quando isso **baixa a carga do adaptador mais cheio**. Trocar custa
    caro de verdade — desfazer o pareamento, apagar o cache SDP e parear de
    novo, com o controle na mão. Sem esta regra o plano mandava trocar três
    controles entre dongles idênticos, sem ganho.

    **Sem adaptador nenhum, nada cabe** — e esse é o estado real dela às 02h36
    de 25/08/2026, quando o hub saiu do barramento levando os três dongles.
    """
    if not adaptadores:
        return PlanoDosControles((), {}, {}, cabe=False, sobra=0)

    carga: dict[str, float] = {a.id: 0.0 for a in adaptadores}
    destino: dict[str, str] = {}

    # 1. cada um fica onde está — se o adaptador dele ainda existe
    orfaos: list[Controle] = []
    for controle in controles:
        if controle.onde in carga:
            destino[controle.nome] = controle.onde
            carga[controle.onde] += _custo(controle)
        else:
            orfaos.append(controle)

    # 2. quem perdeu o adaptador vai para o menos carregado
    for controle in orfaos:
        alvo = _menos_carregado(adaptadores, carga)
        destino[controle.nome] = alvo
        carga[alvo] += _custo(controle)

    # 3. rebalanceia SÓ enquanto isso baixar o pico
    for _ in range(len(controles) * 2):
        cheio = _mais_carregado(adaptadores, carga)
        vazio = _menos_carregado(adaptadores, carga)
        if cheio == vazio:
            break
        candidatos = [c for c in controles if destino.get(c.nome) == cheio]
        if not candidatos:
            break
        controle = candidatos[-1]
        pico_antes = carga[cheio]
        pico_depois = max(carga[cheio] - _custo(controle), carga[vazio] + _custo(controle))
        if pico_depois >= pico_antes:
            break
        carga[cheio] -= _custo(controle)
        carga[vazio] += _custo(controle)
        destino[controle.nome] = vazio

    pico = max(carga[a.id] for a in adaptadores)

    # quantos MAIS cabem: simula acrescentar até um adaptador estourar. Dividir a
    # folga total daria número maior e falso — controle não se parte em dois.
    teste = dict(carga)
    sobra = 0
    while sobra < 32:
        alvo = _menos_carregado(adaptadores, teste)
        if teste[alvo] + CUSTO_COM_MIC > SLOTS:
            break
        teste[alvo] += CUSTO_COM_MIC
        sobra += 1

    return PlanoDosControles(
        adaptadores=tuple(adaptadores), carga=carga, destino=destino,
        cabe=pico <= SLOTS, sobra=sobra,
    )


def _menos_carregado(adaptadores: Sequence[Adaptador], carga: Mapping[str, float]) -> str:
    alvo = adaptadores[0].id
    for adaptador in adaptadores:
        if carga[adaptador.id] < carga[alvo]:
            alvo = adaptador.id
    return alvo


def _mais_carregado(adaptadores: Sequence[Adaptador], carga: Mapping[str, float]) -> str:
    alvo = adaptadores[0].id
    for adaptador in adaptadores:
        if carga[adaptador.id] > carga[alvo]:
            alvo = adaptador.id
    return alvo
