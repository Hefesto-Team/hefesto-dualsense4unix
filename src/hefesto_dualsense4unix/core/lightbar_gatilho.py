"""GATILHO-DA-COR-01: repintar a lightbar DEPOIS que a rajada da Steam passa.

- **Medido em:** bancada de 11-12/08/2026, com o olho dela, quatro DualSense na
  mesa. As linhas estão em ``docs/data/ensaios.csv`` (``linha_id =
  luz.lightbar.cor@dualsense``), e as três que sustentam este arquivo são
  ``btmon-a-rajada-tem-hora``, ``gatilho-1500ms-por-controle`` e
  ``gatilho-escrever-no-silencio``.
- **A formulação é dela:** *"não podemos colocar um gatilho pra sempre que a
  steam aloprar em sequência algo ativa a sobrescrição automática?"*

O DEFEITO
=========
A lightbar do DualSense por Bluetooth nasce apagada. Dezesseis dias de caça
eliminaram, com ensaio, o ``0x08``, o keepalive, o cache do nó sysfs, a adoção,
a instância de conexão, a revisão de hardware e a personalização por controle.

A CAUSA, contada no fio com ``btmon``
=====================================
A Steam mantém ``/dev/hidraw*`` de cada DualSense aberto em LEITURA+ESCRITA e
**repinta a lightbar em rajada a cada conexão nova**: 98 reports de saída numa
probe com ela viva, contra 6 sem ela (e os 6 são o próprio kernel). A rajada
dura ~4 s, e **não é por controle** — cada conexão nova faz a Steam repintar
TODOS os controles que ela enxerga.

O produto perde porque pinta a cor no *priming*, na descoberta do controle —
ou seja, dentro da rajada. Chega junto, e a última palavra é da Steam.

SÃO DUAS LUZES, NÃO UMA
=======================
Pergunta dela, 12/08: *"isso vai servir pro player e pro lightbar, certo?"* —
e a resposta tem de ser sim, porque **a Steam repinta as duas**. Medido no
mesmo dia: ao abrir a Steam com as barras acesas, elas migraram para as cores
de jogador dela, e o número de jogador acompanhou. Um gatilho que reescrevesse
só a cor deixaria o produto dizendo uma coisa na luz e outra na tela.

As duas cabem no MESMO report — ``valid_flag1`` liga os dois bits
(``LIGHTBAR_CONTROL_ENABLE`` 0x04 e ``PLAYER_INDICATOR_CONTROL_ENABLE`` 0x10),
o número mora em ``common[43]`` e a cor em ``common[44..46]``. Uma escrita, as
duas luzes: fazer duas seria dobrar a chance de cair no meio de uma rajada
nova.

O ERRO QUE ENSINOU O DESENHO
============================
A primeira versão do gatilho esperava 1,5 s **depois de cada controle** e
escrevia só naquele. Falhou: três conexões em três segundos, e só o ÚLTIMO
ficou magenta (ensaio ``gatilho-1500ms-por-controle``; literal dela: *"só o
player 4 que é o controle azul o resto tá no padrão da steam"*). O último
sobreviveu apenas porque ninguém conectou depois dele.

Por isso o disparo é no **fim da sequência**, nunca por controle: cada evento
RE-ADIA, e quando o rádio sossega escreve-se em TODOS.

ONDE MORA O QUÊ
===============
Este módulo tem só o **conteúdo** da lightbar: o report que se escreve e o
número medido de espera. O **mecanismo** — armar, re-adiar, disparar no
silêncio — mora em `core/gatilho_fim_de_sequencia.py`, genérico por decisão
dela (*"reafirmar o que o produto quer no fim da sequência, seja cor, número
ou o IGNORE do ambiente"*), porque já são três os defeitos da mesma família. A
fiação dos dois é `daemon/connection.py`.
"""
from __future__ import annotations

from hefesto_dualsense4unix.core.ds_output_report import (
    COMMON_LEN,
    VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE,
    VALID_FLAG1_PLAYER_INDICATOR_CONTROL_ENABLE,
    build_bt_report,
)

#: Offsets dentro do payload ``common`` de 47 bytes (espelho do
#: ``dualsense_output_report_common`` do ``hid-playstation``): o padrão de LED
#: de jogador e os três bytes de cor da lightbar.
COMMON_PLAYER_LEDS = 43
COMMON_LIGHTBAR_R = 44
COMMON_LIGHTBAR_G = 45
COMMON_LIGHTBAR_B = 46

#: Quanto se espera DEPOIS DA ÚLTIMA conexão nova antes de repintar.
#:
#: **1,5 s é número medido, não estimativa.** Foi ela quem o fixou em 12/08
#: (*"muito tempo. desce pra um segundo e meio"*), e o ensaio
#: ``gatilho-1500ms-por-controle`` mostrou que 1,5 s bastam: o controle que
#: ninguém seguiu ficou magenta e ficou. Os dois que falharam naquele ensaio
#: não falharam pelo número — falharam porque o relógio era por controle, e uma
#: conexão posterior trouxe uma rajada nova por cima deles.
ATRASO_APOS_A_ULTIMA_CONEXAO_S: float = 1.5

#: Nome deste gatilho no `RegistroDeGatilhos` do daemon. Existe para que quem
#: arma (o tick de hotplug, a transição do sinal de jogo) e quem registra a
#: ação não precisem repetir a string — e para que um nome errado dê no
#: silêncio de um só gatilho, nunca em dois disparos concorrentes.
NOME_DO_GATILHO = "lightbar"


def mascara_de_player_leds(padrao: tuple[bool, bool, bool, bool, bool]) -> int:
    """Converte o padrão de cinco lâmpadas no byte ``common[43]``.

    Bit ``i`` = a ``i``-ésima lâmpada, da esquerda para a direita — a MESMA
    conta do ``_write_partial_output`` do backend (``sum(1 << i ...)``), e é
    ela que faz os padrões baterem com a tabela do driver desta máquina
    (``assets/dkms/hid-playstation/hid-playstation.c:1836-1842``:
    ``BIT(2)``, ``BIT(3)|BIT(1)``, ``BIT(4)|BIT(2)|BIT(0)``,
    ``BIT(4)|BIT(3)|BIT(1)|BIT(0)``, todos) — os palíndromos ``--x--``,
    ``-x-x-``, ``x-x-x``, ``xx-xx``, ``xxxxx``.
    """
    return sum(1 << i for i, aceso in enumerate(padrao) if aceso)


def build_bt_lightbar_report(
    rgb: tuple[int, int, int] | None,
    player_leds: tuple[bool, bool, bool, bool, bool] | None = None,
    *,
    seq: int = 0,
) -> bytes:
    """Report ``0x31`` MÍNIMO que pinta a lightbar e o número do jogador.

    É o report exato que venceu a Steam na mesa dela (ensaio
    ``cor-rota-hidraw-com-steam``, 12/08), acrescido do bit do número — que a
    Steam também repinta.

    Cada eixo entra SÓ quando há valor: ``rgb=None`` não liga o bit da
    lightbar, ``player_leds=None`` não liga o do número. É a disciplina do
    ``AUDIO-OWNER-01`` aplicada aqui — autorizar um campo que sai zerado é
    mandar "apaga" com cara de keepalive, e apagar a barra é exatamente o
    defeito que este módulo existe para curar.

    O que fica ZERADO importa tanto quanto o que é escrito:

    - ``valid_flag0`` zerado — não pede vibração, gatilho nem áudio;
    - ``valid_flag2`` zerado — em particular o
      ``LIGHTBAR_SETUP_CONTROL_ENABLE`` (0x02), que o
      ``LIGHTBAR-BT-KEEPALIVE-01`` (22/07) mediu: reengatá-lo fora da UMA vez
      por conexão que o kernel faz **trava a exibição no firmware** (o
      registrador aceita a cor, o sysfs mostra, e a barra fica apagada);
    - ``valid_flag1`` sem o ``RELEASE_LEDS`` (0x08), que o
      ``LIGHTBAR-BT-CULPADO-01`` (03/08) provou travar a barra 7 de 7 dentro da
      janela pós-conexão.

    ``seq`` fica em 0 aqui de propósito: quem carimba o contador por handle (e
    recalcula o CRC) é o ``writeReport`` do handle, e essa ordem é a lição do
    ``LIGHTBAR-BT-RESET-03`` — um 0x31 com ``seq`` fora do fluxo do handle é
    descartado pelo firmware, e o sintoma é o pior de todos: o log diz
    "escrito" e a barra não muda.
    """
    common = bytearray(COMMON_LEN)
    flag1 = 0
    if rgb is not None:
        flag1 |= VALID_FLAG1_LIGHTBAR_CONTROL_ENABLE
        common[COMMON_LIGHTBAR_R] = int(rgb[0]) & 0xFF
        common[COMMON_LIGHTBAR_G] = int(rgb[1]) & 0xFF
        common[COMMON_LIGHTBAR_B] = int(rgb[2]) & 0xFF
    if player_leds is not None:
        flag1 |= VALID_FLAG1_PLAYER_INDICATOR_CONTROL_ENABLE
        common[COMMON_PLAYER_LEDS] = mascara_de_player_leds(player_leds) & 0xFF
    common[1] = flag1  # common[1] é o valid_flag1 ([0] é o flag0)
    return bytes(build_bt_report(common, seq=seq))


__all__ = [
    "ATRASO_APOS_A_ULTIMA_CONEXAO_S",
    "COMMON_LIGHTBAR_B",
    "COMMON_LIGHTBAR_G",
    "COMMON_LIGHTBAR_R",
    "COMMON_PLAYER_LEDS",
    "NOME_DO_GATILHO",
    "build_bt_lightbar_report",
    "mascara_de_player_leds",
]
