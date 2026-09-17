"""CANAL-SEM-VOZ-01 (17/09/2026) — a amputação para de cair calada.

A QUEIXA QUE ORIGINOU ESTE ARQUIVO, e ela é dela
------------------------------------------------
    *"joguei um jogo com controle por movimento e na hora do vamos ver o
    controle não deu resposta (pragmata)"*

O perfil do PRAGMATA não tem a chave ``caminho``. Ele herdou o
``config.gamepad_caminho`` que o jogo anterior deixou de pé, e o jogo anterior
era um em que ela escolheu Xbox — de propósito, e funcionou lá. Com o caminho
Xbox o vpad nasce em ``uinput``, e em ``uinput`` não há giroscópio: dez linhas
do ``docs/data/mapa-controles.csv`` saem do ar de uma vez.

NADA AQUI MUDA O CANAL. Este módulo não decide nem conserta nada — quem decide
o canal é `integrations/virtual_pad.quer_uhid`, e a herança do caminho é frente
de outra leva. O que ele faz é UMA coisa: dar VOZ ao que já acontecia em
silêncio.

POR QUE ISTO PRECISOU DE ARQUIVO, e a lição é cara
--------------------------------------------------
O preço já estava escrito, medido, e palavra por palavra, desde 19/08/2026 —
em `integrations/ponte_escada.py`, na justificativa do primeiro degrau:

    *"Errar aqui custa um aperto de botão; errar para Xbox custa as dez, e
    custa em silêncio."*

Estava num COMENTÁRIO. Aviso em comentário ninguém lê, e um mês depois ela
jogou um jogo de movimento e o controle não respondeu. Um canal que alguém lê
— o journal do launch e o ``daemon.state_full`` — é a diferença entre o produto
saber e o produto contar.

O QUE ESTE MÓDULO NÃO É, e as duas recusas são decisão DELA
-----------------------------------------------------------
1. **NÃO é degradação.** PS-L3-MASCARA-01 (14/09/2026): *o uinput do caminho
   Xbox é ESCOLHA dela, não degradação*. Por isso este campo tem dono NOVO e
   não reaproveita `gamepad.dedup_status` nem `gamepad.notify_vpad_degradado`
   — pendurar a voz naqueles dois reabriria uma decisão medida, e decisão
   medida não se apaga. Com o caminho Xbox de pé o ``dedup_ok`` continua
   ``True``, como ela decidiu, **e é exatamente esse "integra" que este campo
   existe para acompanhar**: o canal está íntegro para o que ele entrega, e
   entrega dez linhas a menos.

2. **NÃO é frase na tela.** Ordem dela de 07/09/2026, com portão
   (`scripts/check_a_tela_nao_confessa.py`): a tela nunca confessa dívida
   nossa. Aqui não é dívida nossa — é o PREÇO de uma escolha dela —, e por
   isso a redação de qualquer frase é DELA. Este módulo entrega o DADO; quem
   escreve a frase é ela.

NÃO EXISTE "XBOX COM GIROSCÓPIO", e ninguém deve gastar trabalho ali
--------------------------------------------------------------------
Publicar um segundo nó evdev de movimento no vpad ``uinput`` não devolve IMU a
jogo nenhum: sob Proton o evdev não atravessa o winebus (o único fio é o hidraw
com o descritor do DualSense), e mesmo em jogo nativo o SDL casa sensor com
gamepad por ``EVIOCGUNIQ`` — e o kernel **não tem** ``UI_SET_UNIQ`` (medido em
``/usr/include/linux/uinput.h``, 17/09/2026). Não há canal novo a inventar; há
um canal a não desligar sozinho.
"""

from __future__ import annotations

import csv
import pathlib

from hefesto_dualsense4unix.integrations.ponte_escada import ESCADA
from hefesto_dualsense4unix.integrations.virtual_pad import (
    CAMINHO_XBOX,
    caminho_resolvido,
)

#: O nome do evento no journal do launch. Literal em UM lugar só: a régua o
#: importa daqui em vez de redigitar a string, que é como duas grafias do mesmo
#: evento nascem e o `grep` dela passa a achar metade.
EVENTO = "canal_sem_imu"

#: A máscara que o produto promete quando o jogo vê um DualSense — o primeiro
#: degrau da `ESCADA`. Vem de lá porque a lista de pontes tem um dono só.
MASCARA_QUE_PROMETE = ESCADA[0].ponte.mascara

#: A ponte declarada, no mapa, pelas linhas que só chegam ao jogo por `uhid`.
#: É a chave do primeiro degrau — `"gamepad/dualsense"` — e ela também vem da
#: `ESCADA`, nunca redigitada.
PONTE_DAS_DEZ = ESCADA[0].ponte.chave

#: A raiz da árvore, a partir DESTE arquivo — nunca um caminho escrito à mão.
#: O mesmo cálculo de `interface/mesa_viva.RAIZ`, e pela mesma razão medida em
#: 30/08/2026: um literal apontaria para a árvore DELA, e um agente leria o
#: mapa dela em vez do seu.
_RAIZ = pathlib.Path(__file__).resolve().parents[3]
MAPA = _RAIZ / "docs" / "data" / "mapa-controles.csv"

#: A CÓPIA CONGELADA das dez, e ela existe por um motivo estrutural: o
#: `docs/data/mapa-controles.csv` **não entra no wheel**
#: (`pyproject.toml`, `[tool.hatch.build.targets.wheel].include`), então no
#: produto instalado não há mapa no disco para ler. Sem esta cópia o evento
#: nasceria mudo justamente na máquina dela, que é a única que importa.
#:
#: ELA NÃO É UMA SEGUNDA VERDADE: quem manda é o mapa, e há portão que compara
#: as duas e reprova a divergência
#: (`tests/unit/test_o_canal_sem_imu_tem_voz.py`). Quem mexer nas linhas `uhid`
#: do mapa vê esta tupla reprovar no mesmo `git add`.
DEZ_LINHAS_CONGELADAS: tuple[str, ...] = (
    "audio.jack.deteccao",
    "energia.bateria.jogo",
    "luz.replica_output_jogo",
    "movimento.acelerometro.jogo",
    "movimento.giroscopio.jogo",
    "movimento.giroscopio.taxa",
    "toque.touchpad",
    "toque.touchpad.clique",
    "vibracao.rumble.ff",
    "vibracao.rumble.passthrough",
)


def linhas_do_mapa() -> tuple[str, ...]:
    """As linhas do DualSense que declaram chegar ao jogo pela ponte DualSense.

    LÊ a coluna `ponte_alcanca`, que nasceu em 20/08/2026 exatamente para
    guardar esta afirmação no dado em vez de na prosa (PONTE-NO-MAPA-01). Não
    há lista digitada aqui: no dia em que uma feature nova nascer `uhid` no
    DualSense e declarar a ponte, ela entra nesta conta sozinha.

    Tupla VAZIA quando o mapa não está no disco — é o caso do produto
    instalado, e quem trata é :func:`chaves_fora_do_ar`.
    """
    try:
        with MAPA.open(encoding="utf-8", newline="") as arq:
            return tuple(
                sorted(
                    (linha.get("chave") or "").strip()
                    for linha in csv.DictReader(arq)
                    if (linha.get("controle") or "").strip() == "dualsense"
                    and (linha.get("ponte_alcanca") or "").strip() == PONTE_DAS_DEZ
                )
            )
    except (OSError, csv.Error, UnicodeDecodeError):
        return ()


def chaves_fora_do_ar() -> tuple[str, ...]:
    """As linhas que o caminho Xbox tira do ar — do mapa, ou da cópia congelada.

    Ordem estável (alfabética pela chave) porque ela vai para o journal e para
    o `state_full`: uma lista que muda de ordem a cada leitura faz duas linhas
    iguais parecerem diferentes para quem estiver comparando.
    """
    return _DO_DISCO or DEZ_LINHAS_CONGELADAS


#: Lido UMA vez, no import. O `state_full` roda a 20 Hz e o launch materializa
#: a cada transição: abrir um CSV de 312 linhas em qualquer um dos dois seria
#: I/O em caminho quente. É o mesmo molde do `mesa_viva.MAPA`.
_DO_DISCO: tuple[str, ...] = linhas_do_mapa()


def canal_sem_imu(*, mascara: object, caminho: object, backend: object) -> bool:
    """O jogo vê um DualSense por um canal que não carrega as dez linhas?

    AS TRÊS METADES, e cada uma exclui um caso que NÃO é este:

    - **`mascara == "dualsense"`** — o jogo está vendo o par VID/PID da Sony,
      ou seja, o produto prometeu um DualSense. Com a máscara Xbox o jogo vê um
      controle de Xbox, a tela diz «Xbox», e o preço daquele degrau já está
      declarado na `ESCADA` (segundo degrau: *"Não carrega nenhuma das dez
      linhas `uhid`"*) — é escolha coerente, não silêncio, e não é este evento;
    - **caminho resolvido `== "xbox"`** — o canal escolhido é o comum. É a
      metade que a herança de `config.gamepad_caminho` liga sem ninguém pedir
      NAQUELE jogo, e é por ela que o PRAGMATA caiu;
    - **`backend == "uinput"`** — o vpad de pé é mesmo o evdev. Sem esta, um
      vpad `uhid` que ainda não sabe dizer o caminho responderia "sem IMU" com
      a IMU no ar, que é a mentira cara num painel de diagnóstico.

    `caminho_resolvido` é chamada e não reimplementada: a regra de *"sem
    escolha, o caminho sai da máscara"* tem um dono, e é ele.
    """
    if str(mascara or "") != MASCARA_QUE_PROMETE:
        return False
    if str(backend or "") != "uinput":
        return False
    return caminho_resolvido(caminho, mascara) == CAMINHO_XBOX


def canal_sem_imu_do_vpad(vpad: object) -> bool:
    """A mesma pergunta, feita ao vpad que está DE PÉ. Nunca levanta.

    Pergunta ao APARELHO, nunca ao perfil: *a escolha dela morre antes do
    aparelho* já custou três defeitos num dia (16/09/2026). O caminho vem de
    `virtual_pad.caminho_do_vpad`, que é quem sabe em que caminho aquele pad
    nasceu; `None` dali é *"não sei dizer"*, e aí `canal_sem_imu` resolve pela
    máscara, que é o produto de antes de 13/09.
    """
    from hefesto_dualsense4unix.integrations.virtual_pad import caminho_do_vpad

    if vpad is None:
        return False
    try:
        return canal_sem_imu(
            mascara=getattr(vpad, "flavor", None),
            caminho=caminho_do_vpad(vpad),
            backend=getattr(vpad, "backend", None),
        )
    except Exception:
        # Diagnóstico nunca derruba quem pergunta: este ramo é chamado de
        # dentro do `state_full` e da materialização do launch, e os dois são
        # best-effort por contrato.
        return False


__all__ = [
    "DEZ_LINHAS_CONGELADAS",
    "EVENTO",
    "MAPA",
    "MASCARA_QUE_PROMETE",
    "PONTE_DAS_DEZ",
    "canal_sem_imu",
    "canal_sem_imu_do_vpad",
    "chaves_fora_do_ar",
    "linhas_do_mapa",
]
