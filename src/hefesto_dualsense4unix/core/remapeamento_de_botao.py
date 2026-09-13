"""O remapeamento botão a botão — o motor puro. F1-REMAPEAR, 13/09/2026.

**Decisão dela, 29/08/2026** (`D-O-REMAPEAMENTO-BOTAO-A-BOTAO-ENTRA`,
`docs/data/decisoes-dela.csv`): *"ENTRA, E VIRA SPRINT PRÓPRIA. É feature real:
trocar botão por botão é o que salva jogo que não deixa remapear."* E ele é
GLOBAL no perfil (`D-0809-A-NAVEGACAO-E-GLOBAL-NO-PERFIL`, mesma planilha): um
mapa só por perfil, não um por controle.

O QUE ESTE ARQUIVO É: a regra inteira, sem GTK, sem daemon e sem disco. Ele
recebe o mapa declarado (`Profile.remapeamento`, *botão → botão*) e devolve o
mapa resolvido ou a recusa com motivo (:func:`resolver`), e traduz UM tique do
que o controle apertou para o que o jogo vai ver (:func:`traduzir`).

ONDE A TROCA ENTRA — logo antes dos dois `forward_buttons`, e só ali:

    primário     `daemon/subsystems/gamepad.dispatch_gamepad`
    secundários  `daemon/subsystems/coop.CoopManager.forward_all`

Quem escolheu o ponto foi quem coordena, por delegação (a palavra dela de
13/09 no índice `2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md`, §0 item 5), e a
razão é MEDIDA: os dois são o único caminho de botão até o gamepad virtual, e
tudo o que não é o jogo — o PS, os cinco gestos, o atalho de teclado, o
teclado e o mouse emulados — lê o `buttons_pressed` ORIGINAL no laço do daemon
(`daemon/lifecycle.py`, o tique do primário). Logo a troca muda só o que o jogo
vê, nos quatro controles, e o PS continua sendo a saída de emergência.

FATO SUBSTITUÍDO, e ele estava escrito na sprint e na tela: *"o primário não
passa por `forward_buttons`"*. Passa — `lifecycle` chama
`_dispatch_gamepad_emulation`, que chama `gamepad.dispatch_gamepad`, que chama
`device.forward_buttons(buttons_pressed)`, desde `da9b4921` (27/06/2026).

O ESTADO ATIVO MORA NO `StateStore` DO DAEMON, e não num canal novo da fábrica
do gerente. Medido em 13/09: das rotas que ativam perfil, a do boot
(`daemon/connection.py::restore_last_profile`) monta o `ProfileManager` à mão e
não recebe canal nenhum da fábrica — mas TODAS passam `store=daemon.store`, e o
poll loop já lê o `store` por tique (`udp_trigger_thresholds`). Um canal só na
fábrica deixaria a troca muda no boot até a primeira troca de perfil, que é a
forma exata do defeito *applier ausente é seção ignorada em silêncio*.
"""
from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, cast

#: O BOTÃO PS, travado nos dois lados. Se ele pudesse ser trocado, a pessoa
#: perderia as duas saídas de emergência com um clique: os cinco gestos da aba
#: Navegação começam nele (`daemon/subsystems/hotkey.py`). É o mesmo id de
#: `core/acoes_de_botao.BOTAO_PS` — a régua confere.
BOTAO_PS: Final = "ps"

#: Os dois gatilhos: o id da tela → o nome do bit digital no vocabulário do
#: gamepad virtual (`core/evdev_reader.EvdevReader.BUTTON_MAP`). O gatilho é
#: DUAS entradas — o bit e o eixo 0-255 —, e a troca leva as duas juntas.
GATILHOS: Final[Mapping[str, str]] = MappingProxyType({"l2": "l2_btn", "r2": "r2_btn"})

#: O CONTRÁRIO: o nome no vocabulário do jogo → o id da tela.
_ID_DO_NOME: Final[Mapping[str, str]] = MappingProxyType(
    {nome: botao for botao, nome in GATILHOS.items()})

#: O QUE A TROCA ALCANÇA, na ordem de `core/acoes_de_botao.BOTOES`: os botões
#: que chegam ao jogo como BOTÃO pelo `forward_buttons`, mais os dois gatilhos.
#: A lista é conferida contra o vocabulário do leitor evdev e contra `BOTOES`
#: pela régua `test_migra_navegacao_13_o_remapeamento_botao_a_botao.py` — ela
#: não é importada daqui porque `acoes_de_botao` arrasta
#: `integrations/uinput_mouse`, e este módulo roda no caminho quente.
REMAPEAVEIS: Final[tuple[str, ...]] = (
    "cross", "circle", "square", "triangle",
    "l1", "r1", "l2", "r2",
    "l3", "r3",
    "dpad_up", "dpad_down", "dpad_left", "dpad_right",
    "options", "create",
)

#: O destino "Touchpad (clique)" da tela não é um id de `BOTOES`: as três
#: regiões são invenção do modo mouse, e o DualSense só reporta um clique.
DESTINO_TOUCHPAD: Final = "touchpad"

#: O QUE A TELA MOSTRA E A TROCA NÃO ALCANÇA, com a razão medida de cada um.
#: Não é lista de exceção: é o que o caminho do jogo NÃO carrega como botão.
FORA_DO_ALCANCE: Final[Mapping[str, str]] = MappingProxyType({
    "l3_direcao": "a direção do analógico é eixo, não botão",
    "r3_direcao": "a direção do analógico é eixo, não botão",
    "touchpad_left_press": "o clique do touchpad chega ao jogo por outro caminho",
    "touchpad_middle_press": "o clique do touchpad chega ao jogo por outro caminho",
    "touchpad_right_press": "o clique do touchpad chega ao jogo por outro caminho",
    DESTINO_TOUCHPAD: "o clique do touchpad chega ao jogo por outro caminho",
})

MOTIVO_DESCONHECIDO: Final = "desconhecido"
MOTIVO_PS: Final = "ps"
MOTIVO_FORA: Final = "fora"
MOTIVO_COLISAO: Final = "colisao"  # (noqa-acento) código de motivo, não é prosa

#: A força do eixo que um gatilho apertado até o fim manda.
FORCA_CHEIA: Final = 255

#: O atributo do `StateStore` onde o mapa ativo mora — ver o topo do arquivo.
_ATRIBUTO_DO_ATIVO: Final = "_remapeamento_de_botao_ativo"


class RemapeamentoRecusadoError(ValueError):
    """A recusa, com o motivo e os botões que ela nomeia.

    É `ValueError` para o esquema do perfil a devolver como erro de validação
    sem embrulho, e carrega os ids crus: quem escreve a frase para gente ler é
    a tela, que sabe o nome de cada linha.
    """

    def __init__(self, motivo: str, botoes: tuple[str, ...]) -> None:
        self.motivo = motivo
        self.botoes = botoes
        super().__init__(f"remapeamento recusado ({motivo}): {', '.join(botoes)}")


def _ordem(botao: str) -> int:
    """A posição da linha na tela, para a recusa nomear na ordem que ela lê."""
    try:
        return REMAPEAVEIS.index(botao)
    except ValueError:
        return len(REMAPEAVEIS)


def resolver(declarado: Mapping[str, str] | None) -> dict[str, str]:
    """O mapa declarado, limpo — ou `RemapeamentoRecusadoError` com o motivo.

    AS QUATRO RECUSAS, nesta ordem, e cada uma nomeia os botões:

    1. botão que o produto não conhece (nem `BOTOES`, nem o destino touchpad);
    2. o PS em qualquer lado — travado nos dois;
    3. linha fora do alcance (`FORA_DO_ALCANCE`), em qualquer lado;
    4. dois botões apontando para o MESMO destino — nomeia os dois e o destino.

    A TROCA DE UM BOTÃO POR ELE MESMO SOME antes de tudo: é o "— Sem troca —"
    dito de outro jeito, e guardá-la seria encher o perfil de linha que não faz
    nada.

    CICLO NÃO É RECUSA, e isto derruba uma linha do contrato da
    MIGRA-NAVEGACAO-13: a troca dupla `{l1: r1, r1: l1}` É um ciclo, e é o caso
    que o mesmo contrato manda funcionar. :func:`traduzir` lê sempre o que o
    controle APERTOU, nunca o resultado de outra troca, então `A→B, B→C` também
    tem um sentido só: apertar A o jogo vê B, apertar B o jogo vê C.
    """
    if not declarado:
        return {}
    from hefesto_dualsense4unix.core.acoes_de_botao import BOTOES

    conhecidos = set(BOTOES) | {DESTINO_TOUCHPAD}
    limpo = {str(o): str(d) for o, d in declarado.items() if o != d}
    desconhecidos = sorted({x for par in limpo.items() for x in par
                            if x not in conhecidos})
    if desconhecidos or any(o == DESTINO_TOUCHPAD for o in limpo):
        raise RemapeamentoRecusadoError(
            MOTIVO_DESCONHECIDO,
            tuple(desconhecidos) or (DESTINO_TOUCHPAD,))
    com_ps = sorted({o for o, d in limpo.items() if BOTAO_PS in (o, d)}, key=_ordem)
    if com_ps:
        raise RemapeamentoRecusadoError(MOTIVO_PS, tuple(com_ps))
    fora = [o for o, d in limpo.items() if o in FORA_DO_ALCANCE or d in FORA_DO_ALCANCE]
    if fora:
        raise RemapeamentoRecusadoError(MOTIVO_FORA, tuple(sorted(fora, key=_ordem)))
    por_destino: dict[str, list[str]] = {}
    for origem, destino in limpo.items():
        por_destino.setdefault(destino, []).append(origem)
    for destino in sorted(por_destino, key=_ordem):
        origens = por_destino[destino]
        if len(origens) > 1:
            raise RemapeamentoRecusadoError(
                MOTIVO_COLISAO, (*sorted(origens, key=_ordem), destino))
    return limpo


def traduzir(
    apertados: frozenset[str], l2: int, r2: int, mapa: Mapping[str, str]
) -> tuple[frozenset[str], int, int]:
    """Um tique: o que o controle apertou → o que o jogo vai ver.

    O MAPA É APLICADO SOBRE O RETRATO, nunca em cadeia: cada origem lê o que o
    controle apertou, e o resultado de uma troca não entra em outra. É o que
    faz a troca dupla funcionar — aplicada em ordem, a segunda troca leria a
    primeira e o botão voltaria a si mesmo.

    O QUE NÃO ESTÁ NO MAPA PASSA INTACTO, inclusive nome que a tela não conhece
    (`mic_btn`, o clique do touchpad): a troca só mexe no que declarou.

    OS GATILHOS LEVAM O EIXO JUNTO. Um gatilho de origem manda a força dele ao
    destino gatilho, e o bit digital ao destino botão; um botão de origem manda
    `FORCA_CHEIA` a um destino gatilho. Dois apertos no mesmo gatilho ficam com
    a força maior.

    QUEM CHAMA CONFERE O MAPA VAZIO ANTES (`if mapa:`), e é de propósito: sem
    troca, o jogo recebe o MESMO objeto que o controle mandou, e o tique não
    aloca nada — é a régua de custo da MIGRA-NAVEGACAO-13.
    """
    saida = {n for n in apertados if _ID_DO_NOME.get(n, n) not in mapa}
    forca = {"l2": 0 if "l2" in mapa else l2, "r2": 0 if "r2" in mapa else r2}
    lida = {"l2": l2, "r2": r2}
    for origem, destino in mapa.items():
        apertado = GATILHOS.get(origem, origem) in apertados
        if destino in GATILHOS:
            valor = lida[origem] if origem in GATILHOS else (
                FORCA_CHEIA if apertado else 0)
            if valor > forca[destino]:
                forca[destino] = valor
            if apertado:
                saida.add(GATILHOS[destino])
        elif apertado:
            saida.add(destino)
    return frozenset(saida), forca["l2"], forca["r2"]


def definir_ativo(dono: object, mapa: Mapping[str, str] | None) -> None:
    """Guarda o mapa ATIVO no dono (o `StateStore` do daemon). Vazio = sem troca.

    O mapa vai CONGELADO (`MappingProxyType` de uma cópia): o poll loop o lê
    por tique noutra thread, e a troca de referência é atômica — ninguém muda
    o mapa por baixo de um tique em curso. `None` é metade do contrato: o perfil
    sem troca apaga a do perfil anterior.
    """
    if dono is None:
        return
    setattr(dono, _ATRIBUTO_DO_ATIVO,
            MappingProxyType(dict(mapa)) if mapa else None)


def ativo(dono: object) -> Mapping[str, str] | None:
    """O mapa ativo, ou `None`. Leitura de memória, custo de um `getattr`.

    SÓ UM MAPA CONGELADO VALE: um dublê de teste feito de `MagicMock` responde
    qualquer atributo com outro mock, e um mock verdadeiro no caminho do jogo
    trocaria botão nenhum e derrubaria o tique.
    """
    valor = getattr(dono, _ATRIBUTO_DO_ATIVO, None)
    if type(valor) is not MappingProxyType:
        return None
    return cast("Mapping[str, str]", valor)


__all__ = [
    "BOTAO_PS",
    "DESTINO_TOUCHPAD",
    "FORA_DO_ALCANCE",
    "FORCA_CHEIA",
    "GATILHOS",
    "MOTIVO_COLISAO",
    "MOTIVO_DESCONHECIDO",
    "MOTIVO_FORA",
    "MOTIVO_PS",
    "REMAPEAVEIS",
    "RemapeamentoRecusadoError",
    "ativo",
    "definir_ativo",
    "resolver",
    "traduzir",
]
