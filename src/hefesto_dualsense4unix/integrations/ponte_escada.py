"""PONTE-ESCADA-01 — tenta em ordem, para quando acerta, nunca mais pergunta.

A decisão dela, 19/08/2026: *"o produto tenta as pontes em ordem; ela confirma
UMA vez qual pegou; o produto grava para sempre"* — mais o atalho de escolher
direto na aba de perfil quando já souber.

Este módulo é a DECISÃO, e só ela: qual é a próxima ponte a tentar, quanto
custa subir esse degrau, e quando é honesto gravar que a ponte pegou. Ele não
cria vpad, não escreve `.env`, não mexe na Steam. Quem age é `launch_env` (no
lançamento) e o gesto dela (ao vivo).

NENHUMA PALAVRA NOVA
--------------------
Uma **ponte** não é um conceito novo: é a tupla que o disco JÁ guarda, e as
três peças já têm dono.

    Ponte(kind, mascara, steam_input)
      kind        = `mode.kind` do perfil        (profiles/schema.py)
      mascara     = `mode.gamepad_flavor`        (profiles/schema.py)
      steam_input = está no `steam_input_apps.txt`?  (a allowlist dela)

O que faltava não era vocabulário: era o registro de que **esta** tupla foi
CONFIRMADA para **aquele** jogo. É só isso que este módulo acrescenta.

A ORDEM, E O DADO QUE A SUSTENTA
--------------------------------
O censo de 19/08 propôs ``DualSense/uhid -> Xbox -> Nativo``. A ordem foi
conferida contra `docs/data/mapa-controles.csv`, e ela se sustenta — com uma
correção de forma, não de conteúdo (§ *OS DOIS TRAMOS*).

**A assimetria, contada no mapa (19/08/2026).** Das linhas do DualSense no
`mapa-controles.csv`, **dez** entregam ao JOGO por `uhid` — o canal que só
existe quando a máscara é a nossa DualSense (`054c:0df2`):

    audio.jack.deteccao            movimento.giroscopio.jogo
    energia.bateria.jogo           movimento.giroscopio.taxa
    luz.replica_output_jogo        toque.touchpad
    movimento.acelerometro.jogo    toque.touchpad.clique
    vibracao.rumble.ff             vibracao.rumble.passthrough

(A décima primeira linha `uhid`, `plataforma.vpad`, é o mecanismo, não uma
feature — fica fora da conta.)

A máscara Xbox é `uinput` (`045e:028e`, `integrations/uinput_gamepad.py`), e
`docs/protocol/pilha-steam-input-xpad-sdl.md` §1.5 explica POR QUE ela não tem
onde pôr nenhuma das dez: o pacote do Xbox 360 é fixo desde 2005, o `xpad`
declara sete eixos e um único nó de entrada, e o `hid-playstation` declara
quatro. *"Quem escolhe a máscara Xbox escolhe rumble por evdev que funciona em
tudo e paga com as cinco features."*

**Logo: errar para DualSense custa um aperto de botão; errar para Xbox custa
dez linhas do mapa, e custa em silêncio** — ninguém percebe que perdeu o
giroscópio até procurar por ele. Por isso a DualSense é o primeiro degrau. Isto
é a mesma conclusão do estudo de 16/08 (*A MÁSCARA QUE O DISCO NÃO SABE*, §3.1)
lida contra o mapa, e não uma opinião nova.

**O que NÃO sustenta pôr o Xbox primeiro, e parece sustentar:** o censo de
16/08 achou 14 jogos `indeciso` (XInput no binário e nada de SDL) contra 7
`entende_dualsense`. É tentador ler "a maioria quer Xbox". O mesmo estudo mediu
que essa leitura **erraria em 13 dos 14**: DON'T SCREAM, Big Walk e Sackboy são
`indeciso` e funcionaram com a máscara `dualsense`. `indeciso` é ausência de
evidência, não evidência de Xbox.

OS DOIS TRAMOS — e por que a escada não é uma escada só
-------------------------------------------------------
A correção de forma. Metade de cada ponte é **ambiente congelado no `exec`**:
`SDL_GAMECONTROLLER_IGNORE_DEVICES` e `PROTON_DISABLE_HIDRAW` são lidos UMA vez,
quando o jogo abre. Isso parte a escada em dois tramos, e o corte é medido, não
estético:

**Tramo AO VIVO — as duas máscaras.** Nenhuma das duas (`054c:0df2` e
`045e:028e`) está na lista de ignorados, então trocar entre elas alcança um
processo que já está rodando. Preço: recriar o vpad, que é o R-04.

**Tramo ENTRE LANÇAMENTOS — nativo e Steam Input.**

- *Nativo* não alcança processo vivo. `daemon/launch_env.py`
  (`_nativos_fora_da_antecipacao`) já tem a sequência escrita: *"a emulação cai
  → o vpad some e o físico continua escondido pelo IGNORE congelado na env do
  processo = ZERO controles"*. Subir para nativo com o jogo aberto não é um
  degrau ruim: é um degrau que MENTE.
- *Steam Input* é mais caro ainda, e o preço não é nosso. `UseSteamControllerConfig`
  só sobrevive com a **Steam fechada** (`integrations/steam_input_ponte.py`: a
  Steam regrava o `localconfig.vdf` ao sair e engole a edição feita por baixo).
  Ligar ou desligar exige fechar a Steam, reabrir a Steam e reabrir o jogo.

ONDE O STEAM INPUT CAI, E POR QUÊ
---------------------------------
No fim, e não por ser pior — por ser o mais caro de tentar.

Ele **não é uma máscara nossa**: é a Steam entregando a ENTRADA e o Hefesto
mantendo a SAÍDA. Medido em `CONTROLE-SONY-MEDIDO-01`, seção *A INVERSÃO*: com
o jogo na allowlist, os ajustes dela (lightbar, gatilhos, LED de jogador)
VENCEM o jogo; fora dela, o jogo vence. É a única ponte que inverte essa
disputa a favor dela — e é a única que funciona para a classe *"só aceita Steam
Input"*, medida na noite de 18→19/08 com DON'T SCREAM: sem Steam Input o jogo
não via controle nenhum.

A conta que o põe por último: os três primeiros degraus custam três gestos
dentro de uma sessão; este custa um ciclo Steam+jogo. Pagar três gestos antes
de um reinício é mais barato, para a biblioteca inteira, do que pagar um
reinício antes de três gestos.

A máscara que viaja debaixo dele é a `dualsense`, e isso tem medição: o
`virtualgamepadinfo.txt` dela (16/08) registra o nosso vpad no slot 0 como
`054c:0df2`, **type `ps5`** — é o que deixa os pedidos DualSense da própria
Steam (Steamworks) terem por onde chegar.

UMA CONTRADIÇÃO VIVA, REGISTRADA E NÃO ESCONDIDA
------------------------------------------------
DON'T SCREAM (2497900) aparece nas duas medições desta casa com desfechos
opostos: a tabela de 16/08 o lista como *"SIM (perfil dela, dualsense)"*, e a
bancada de 18→19/08 mediu que **sem Steam Input ele não via controle nenhum**.
As duas não podem estar certas ao mesmo tempo sobre o mesmo estado da máquina.

Não se resolve aqui, e não precisa: **é o argumento mais forte a favor de esta
escada existir.** Se duas medições da casa discordam sobre um jogo, nenhuma
leitura de disco vai decidir por ele. Só tentar decide.

O QUE ESTE MÓDULO NUNCA FAZ
---------------------------
**Gravar "funciona" sobre algo que ninguém confirmou.** É a disciplina do balde
`sem_impedimento_conhecido` do `prontuario_dos_jogos`: uma ponte só vira
CONFIRMADA por gesto dela, por silêncio dela com o jogo VIVO, ou por escolha
dela na aba de perfil. Jogo fechado no meio da escada não confirma nada.

**Guardar o que já tem dono.** A confirmação mora no PERFIL, no campo
`Profile.ponte` (`PonteConfirmada`, PONTE-CONFIRMADA-01, 19/08/2026) — é a
regra dela de 18/08, *"o perfil tem de guardar tudo"*, e quem grava é
`profiles/manager.confirmar_ponte`. Este módulo não abre uma segunda gaveta
para o mesmo fato: ele DECIDE, e devolve a ponte a carimbar. Os três nomes de
origem (`POR_GESTO`, `POR_SILENCIO`, `POR_ESCOLHA_DELA`) são byte a byte os
`CONFIRMADA_POR_*` do esquema, de propósito — dois vocabulários para a mesma
pergunta é como esta casa cria uma discordância que ninguém vê.

**Guardar posição.** A escada não tem memória própria: o degrau em que ela está
é a ponte que está DE PÉ agora (`ponte_atual`). Se ela fechar o jogo no meio da
escada, a ponte de pé continua sendo a última tentada, e o próximo lançamento
retoma dali em vez de reviver os degraus de baixo — sem nenhum arquivo novo
para isso ficar velho.

**Subir um degrau sozinho com o jogo aberto.** Cada degrau ao vivo recria o
vpad, e recriar o vpad com o jogo aberto arranca o controle da mão dela (R-04,
medido em 23/07/2026; medido DE NOVO em 19/08 no journal dela). O gate
`_recriacao_bloqueada_por_jogo` já implementa a metade defensiva disto: origem
automática é barrada, origem que é gesto dela nunca é. Este módulo declara a
outra metade — `como_subir` NUNCA responde "agora" com o jogo vivo.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# O vocabulário — todo ele emprestado de quem já o tinha
# ---------------------------------------------------------------------------

#: `mode.gamepad_flavor` (profiles/schema.py). Nomes idênticos, de propósito.
MASCARA_DUALSENSE = "dualsense"
MASCARA_XBOX = "xbox"

#: `mode.kind` (profiles/schema.py).
KIND_GAMEPAD = "gamepad"
KIND_NATIVE = "native"
KIND_DESKTOP = "desktop"

#: Como uma ponte foi confirmada. Só estes três confirmam; nada mais.
POR_GESTO = "gesto"
POR_SILENCIO = "silencio"
POR_ESCOLHA_DELA = "escolha_dela"
CONFIRMACOES = frozenset({POR_GESTO, POR_SILENCIO, POR_ESCOLHA_DELA})

#: O que custa subir um degrau, do ponto de vista dela. Vocabulário de string,
#: como os desfechos de emulação em `daemon/subsystems/gamepad.py`.
#:
#:   - ``"agora"``            — o jogo não está aberto: o degrau vale no
#:                              próximo lançamento e não custa nada a ninguém;
#:   - ``"so_com_gesto"``     — o jogo está aberto e o degrau recria o vpad
#:                              (R-04). Só o gesto DELA autoriza;
#:   - ``"reabrindo_o_jogo"`` — o degrau não alcança um processo já rodando: a
#:                              env dele congelou no `exec`;
#:   - ``"fechando_a_steam"`` — o degrau mexe no `localconfig.vdf`, que só
#:                              sobrevive com a Steam fechada.
SUBIR_AGORA = "agora"
SUBIR_SO_COM_GESTO = "so_com_gesto"
SUBIR_REABRINDO_O_JOGO = "reabrindo_o_jogo"
SUBIR_FECHANDO_A_STEAM = "fechando_a_steam"

#: Quanto silêncio dela conta como confirmação, em segundos.
#:
#: **O relógio começa no GESTO, nunca no lançamento** — e isto é o que o número
#: tem de medido. `launch_env.WRAPPER_MARKER_WINDOW_SEC` registra que a latência
#: launch→janela chega a 15 minutos (Proton na 1ª execução, compilação de
#: shaders, launcher de terceiro). Contar o silêncio a partir do lançamento
#: confirmaria o degrau de baixo enquanto o jogo ainda compila shaders e ela
#: nem viu o controle.
#:
#: **O valor em si NÃO é medido, e a honestidade é dizer isso.** Não existe nesta
#: casa uma medição de quanto tempo ela leva para perceber que o controle não
#: pegou. Três minutos é a estimativa, e o que a sustenta é o desenho, não o
#: cronômetro: um erro para MENOS custa um gesto (a confirmação prematura é
#: desfeita pelo próximo gesto, que recarimba o perfil), enquanto um erro para
#: MAIS deixa ela apertando um botão que não faz nada. Errar para o lado barato
#: é o critério.
SILENCIO_CONFIRMA_SEC = 180.0


@dataclass(frozen=True)
class Ponte:
    """A ponte que um jogo aceita — a tupla que o disco já guardava.

    `kind` e `mascara` são `mode.kind` e `mode.gamepad_flavor` do perfil;
    `steam_input` é "está no `steam_input_apps.txt`". Nenhum campo novo, e
    NENHUMA persistência aqui: esta é a forma de TRABALHO da escada; a forma
    de ARQUIVO é o `PonteConfirmada` do perfil, e ter uma só gaveta é o ponto.
    """

    kind: str
    mascara: str | None = None
    steam_input: bool = False

    @property
    def chave(self) -> str:
        """Identidade curta, estável, legível no journal."""
        alvo = self.mascara or "-"
        return f"{self.kind}/{alvo}{'+steam_input' if self.steam_input else ''}"


@dataclass(frozen=True)
class Degrau:
    """Um degrau da escada: a ponte, o porquê dela, e o preço de subir nele."""

    ponte: Ponte
    porque: str
    #: Subir aqui destrói e recria o vpad (R-04).
    recria_vpad: bool
    #: O degrau não alcança um processo já rodando (env congelada no `exec`).
    exige_reabrir_jogo: bool
    #: O degrau mexe no `localconfig.vdf` — só sobrevive com a Steam fechada.
    exige_fechar_steam: bool

    @property
    def ao_vivo(self) -> bool:
        """Este degrau alcança um jogo que já está aberto?"""
        return not self.exige_reabrir_jogo and not self.exige_fechar_steam


#: A ESCADA. Ordem justificada no cabeçalho, com o dado ao lado de cada linha.
ESCADA: tuple[Degrau, ...] = (
    Degrau(
        ponte=Ponte(KIND_GAMEPAD, MASCARA_DUALSENSE),
        porque=(
            "Dez linhas do mapa-controles.csv só chegam ao jogo por `uhid` — "
            "giroscópio, acelerômetro, os dois pontos do touchpad, o clique, o "
            "rumble por FF e o roteado, a réplica do output, o jack e a "
            "bateria. Errar aqui custa um aperto de botão; errar para Xbox "
            "custa as dez, e custa em silêncio."
        ),
        recria_vpad=True,
        exige_reabrir_jogo=False,
        exige_fechar_steam=False,
    ),
    Degrau(
        ponte=Ponte(KIND_GAMEPAD, MASCARA_XBOX),
        porque=(
            "A máscara `045e:028e` é o piso mais largo que existe: sete eixos, "
            "um nó de entrada, rumble por evdev que funciona em tudo "
            "(pilha-steam-input-xpad-sdl.md §1.5). Não carrega nenhuma das dez "
            "linhas `uhid`, e é por isso que ela é o segundo degrau e não o "
            "primeiro."
        ),
        recria_vpad=True,
        exige_reabrir_jogo=False,
        exige_fechar_steam=False,
    ),
    Degrau(
        ponte=Ponte(KIND_NATIVE),
        porque=(
            "Sem vpad: o jogo fala com o DualSense físico. É a ponte dos jogos "
            "que escrevem no hidraw direto (Sackboy, medido em 06/08) e "
            "recusam um intermediário. Só vale no próximo lançamento — com o "
            "jogo aberto, o IGNORE congelado na env esconde o físico e o "
            "resultado é ZERO controles (`launch_env._nativos_fora_da_"
            "antecipacao`)."
        ),
        recria_vpad=True,
        exige_reabrir_jogo=True,
        exige_fechar_steam=False,
    ),
    Degrau(
        ponte=Ponte(KIND_GAMEPAD, MASCARA_DUALSENSE, steam_input=True),
        porque=(
            "A Steam entrega a ENTRADA e o Hefesto fica inteiro na SAÍDA — os "
            "ajustes dela vencem o jogo (CONTROLE-SONY-MEDIDO-01, A INVERSÃO). "
            "É a única ponte da classe 'só aceita Steam Input', medida em "
            "18→19/08 com DON'T SCREAM. Fica por último por ser a mais cara de "
            "tentar: exige fechar a Steam, reabrir a Steam e reabrir o jogo."
        ),
        recria_vpad=False,
        exige_reabrir_jogo=True,
        exige_fechar_steam=True,
    ),
)

# ---------------------------------------------------------------------------
# As decisões — puras: sem disco, sem daemon, sem relógio próprio
# ---------------------------------------------------------------------------


def indice_do_degrau(ponte: Ponte) -> int:
    """Posição da ponte na `ESCADA`, ou -1 quando ela não é um degrau."""
    for indice, degrau in enumerate(ESCADA):
        if degrau.ponte == ponte:
            return indice
    return -1


def ponte_do_perfil(profile: Any, *, na_allowlist: bool) -> Ponte | None:
    """A ponte que ESTE perfil entrega HOJE, ou None quando ele não opina.

    Duck-typing sobre `mode` de propósito: este módulo não importa
    `profiles/schema.py` para não criar mais um nó no ciclo
    `profiles -> daemon -> profiles` que `daemon/protocols.py` existe para
    manter desfeito.
    """
    mode = getattr(profile, "mode", None)
    if mode is None:
        return None
    kind = getattr(mode, "kind", None)
    if kind not in (KIND_GAMEPAD, KIND_NATIVE, KIND_DESKTOP):
        return None
    mascara = getattr(mode, "gamepad_flavor", None) if kind == KIND_GAMEPAD else None
    if mascara is not None and mascara not in (MASCARA_DUALSENSE, MASCARA_XBOX):
        mascara = None
    return Ponte(kind=str(kind), mascara=mascara, steam_input=bool(na_allowlist))


def ponte_do_carimbo(carimbo: Any) -> Ponte | None:
    """A `Ponte` de um `PonteConfirmada` do perfil, ou None quando não há.

    O esquema chama a máscara de `gamepad_flavor` (para ficar campo a campo com
    o `mode` ao lado dela no arquivo) e a escada a chama de `mascara`. Esta é a
    ÚNICA tradução entre os dois vocabulários, e ela mora aqui de propósito —
    espalhá-la por cada chamador é como se fabrica a divergência que
    `PonteConfirmada.mesma_ponte` existe para não deixar acontecer.
    """
    if carimbo is None:
        return None
    kind = getattr(carimbo, "kind", None)
    if kind not in (KIND_GAMEPAD, KIND_NATIVE, KIND_DESKTOP):
        return None
    mascara = getattr(carimbo, "gamepad_flavor", None) if kind == KIND_GAMEPAD else None
    return Ponte(
        kind=str(kind),
        mascara=str(mascara) if mascara is not None else None,
        steam_input=bool(getattr(carimbo, "steam_input", False)),
    )


def proximo_degrau(
    *, ponte_atual: Ponte | None, confirmada: Ponte | None = None
) -> Degrau | None:
    """O próximo degrau a tentar, ou None quando a escada NÃO deve rodar.

    **Este é o ponto que transforma "achar rápido" em "nunca mais procurar", e
    um bug aqui é regressão pura** — a escada rodando em jogo que já
    funcionava. Por isso a primeira linha do corpo é a recusa, e não uma
    otimização depois de calcular o resto.

    `confirmada` é o carimbo do perfil daquele jogo
    (`profiles/manager.ponte_confirmada_do_appid`, traduzido por
    `ponte_do_carimbo`). Três motivos para não rodar, nesta ordem:

    1. **o produto SABE** — há ponte confirmada para este jogo. Vale mesmo que
       a ponte de pé hoje seja outra: divergir do carimbo é assunto do
       prontuário (`PONTE_DIVERGENTE`), e não licença para a escada recomeçar;
    2. **a ponte de pé não é um degrau** — ela escolheu na mão uma tupla que a
       escada não conhece. A escolha dela manda; a escada não a corrige;
    3. **a escada acabou** — o último degrau já está de pé e ninguém confirmou
       nada. Voltar ao primeiro faria um laço eterno, e um laço de escada é o
       laço destrói-e-recria com outro nome.

    A escada NÃO guarda posição própria: o degrau em que ela está é a ponte que
    está de pé. É isso que faz o jogo fechado no meio da escada retomar de onde
    parou sem nenhum arquivo de estado para ficar velho.
    """
    if confirmada is not None:
        return None
    if ponte_atual is None:
        # Ninguém opinou ainda: a escada começa no primeiro degrau.
        return ESCADA[0]
    posicao = indice_do_degrau(ponte_atual)
    if posicao < 0:
        return None
    proxima = posicao + 1
    if proxima >= len(ESCADA):
        return None
    return ESCADA[proxima]


def como_subir(degrau: Degrau, *, jogo_vivo: bool) -> str:
    """O preço de subir ESTE degrau agora. Um de `SUBIR_*`.

    A regra que este módulo não abre mão: **com o jogo vivo a resposta nunca é
    `SUBIR_AGORA`.** Cada degrau ao vivo recria o vpad, e recriar o vpad com o
    jogo aberto arranca o controle da mão dela (R-04). O produto pode subir
    sozinho entre lançamentos; com o jogo aberto, quem sobe é o gesto dela.
    """
    if degrau.exige_fechar_steam:
        return SUBIR_FECHANDO_A_STEAM
    if jogo_vivo and degrau.exige_reabrir_jogo:
        return SUBIR_REABRINDO_O_JOGO
    if jogo_vivo:
        return SUBIR_SO_COM_GESTO
    return SUBIR_AGORA


def confirmacao_por_silencio(
    *,
    ponte_atual: Ponte | None,
    ultimo_gesto: float,
    agora: float,
    jogo_vivo: bool,
    confirmada: Ponte | None = None,
) -> Ponte | None:
    """A ponte que o SILÊNCIO dela confirma, ou None quando nada é confirmado.

    *"Se ela para de apertar, a ponte atual é a que pegou."* Com quatro
    condições, e são elas que separam isto de inventar confirmação:

    1. **há ponte de pé** para confirmar;
    2. **ninguém já confirmou** — recarimbar a cada volta do laço apagaria a
       data, que é a única informação que o carimbo antigo carrega;
    3. **o jogo tem de estar VIVO.** Silêncio com o jogo fechado não é ela
       aprovando a ponte — é ela tendo ido embora. Se ela fechou o jogo no meio
       da escada, nada é confirmado: a ponte de pé continua sendo a última
       tentada, e o próximo lançamento retoma dali;
    4. **o relógio conta do último GESTO**, nunca do lançamento — ver
       `SILENCIO_CONFIRMA_SEC`.

    Devolve a `Ponte` a carimbar; quem grava é
    `profiles/manager.confirmar_ponte`, com `por=POR_SILENCIO`.
    """
    if ponte_atual is None or confirmada is not None:
        return None
    if not jogo_vivo:
        return None
    if (agora - ultimo_gesto) < SILENCIO_CONFIRMA_SEC:
        return None
    return ponte_atual


__all__ = [
    "CONFIRMACOES",
    "ESCADA",
    "KIND_DESKTOP",
    "KIND_GAMEPAD",
    "KIND_NATIVE",
    "MASCARA_DUALSENSE",
    "MASCARA_XBOX",
    "POR_ESCOLHA_DELA",
    "POR_GESTO",
    "POR_SILENCIO",
    "SILENCIO_CONFIRMA_SEC",
    "SUBIR_AGORA",
    "SUBIR_FECHANDO_A_STEAM",
    "SUBIR_REABRINDO_O_JOGO",
    "SUBIR_SO_COM_GESTO",
    "Degrau",
    "Ponte",
    "como_subir",
    "confirmacao_por_silencio",
    "indice_do_degrau",
    "ponte_do_carimbo",
    "ponte_do_perfil",
    "proximo_degrau",
]
