"""PONTE-ESCADA-LACO-01 — quem SOBE a escada que `ponte_escada` desenhou.

19/08/2026. A escada estava construída e ninguém a subia: `proximo_degrau`,
`como_subir` e `confirmacao_por_silencio` eram três decisões corretas sem
nenhum chamador em produção — o defeito-mãe desta casa, *"a casa sabe e o
produto não faz"*, que o portão `portao_a_casa_sabe_e_o_produto_nao_faz.py`
acusava textualmente. Este módulo é o LAÇO, e só ele.

A divisão continua a mesma, e é ela que mantém as duas coisas separáveis:

- `ponte_escada` DECIDE (função pura: qual é o próximo degrau, quanto custa,
  quando o silêncio confirma);
- este módulo GUARDA A TENTATIVA EM CURSO e chama aquelas decisões nos três
  momentos em que o produto encosta nelas;
- quem AGE continua sendo `daemon/launch_env.py` (no lançamento) e
  `daemon/subsystems/hotkey.py` (no gesto dela). Nenhum dos dois ganhou
  decisão nova: os dois passaram a perguntar.

OS TRÊS MOMENTOS
----------------
1. **No lançamento** (`launch_env.arm_launch_profile` → `comecar`). Jogo COM
   carimbo: a escada não roda, e o carimbo arma como já armava. Jogo SEM
   carimbo e SEM `mode`: a escada começa — arma o primeiro degrau e abre a
   tentativa. Jogo SEM carimbo mas COM `mode`: o perfil manda, e a tentativa
   abre PARADA no degrau do perfil, sem armar nada.
2. **No gesto `PS + R3`** (`hotkey.build_next_bridge_callback` →
   `avancar_por_gesto`). O gesto é a vontade explícita dela e sempre obedece;
   para o laço, ele é o sinal de que o degrau de pé NÃO funcionou.
3. **No silêncio** (`launch_env.tique_da_escada` → `silencio_confirma`).
   Passado o silêncio com o jogo VIVO, o produto carimba com
   `POR_SILENCIO` — e nunca mais roda a escada naquele jogo.

ONDE A TENTATIVA MORA, E POR QUÊ NÃO É NO DISCO
-----------------------------------------------
Num atributo do daemon VIVO (`_ponte_tentativa`), como `_launch_armed_for` e
`_modo_anunciado` já moram. Estado vivo, que dura o que dura a sessão.

**O disco é só o carimbo.** Gravar a tentativa seria gravar "estou tentando
esta" — e a distância entre "estou tentando" e "esta funciona" é exatamente o
que a disciplina do balde `sem_impedimento_conhecido` do prontuário proíbe
apagar. Carimbar antes da confirmação é o defeito, não o atalho.

**Consequência declarada, com o preço na mesa:** se ela fechar o jogo no meio
da escada, NADA é carimbado (ninguém confirmou nada) e a tentativa morre. O
próximo lançamento recomeça do degrau que o PERFIL entrega — que, no jogo sem
`mode`, é o primeiro. Ela paga os mesmos gestos de novo. O preço é real e é o
barato: a alternativa é um arquivo dizendo "já tentei estas", que envelhece
sozinho e que ninguém sabe quando apagar.

O DEGRAU CARO NÃO PERTENCE AO GESTO — **avisa, GUARDA, e PULA**
----------------------------------------------------------------
Os dois últimos degraus da `ESCADA` não alcançam um processo já rodando —
`native` porque a env congelou no `exec` (o resultado ao vivo é ZERO
controles, `launch_env._nativos_fora_da_antecipacao`), `steam_input` porque o
`localconfig.vdf` só sobrevive com a Steam fechada. Quando a escada chega
neles com o jogo aberto, este laço **avisa, guarda e pula**; não finge, e não
come o aperto dela.

- **Não finge** porque subir ali ao vivo é o degrau que MENTE — é o que o
  cabeçalho de `ponte_escada` já dizia com todas as letras.
- **Avisa** no journal (`ponte_escada_pulou_o_degrau_caro`) e na lightbar, que
  é o único canal que ela enxerga sem sair do jogo: o `hotkey` pisca a cor do
  modo pulado (`CORES_DO_MODO`) antes de aplicar a troca. Um degrau que some
  em silêncio é o defeito com outro nome.
- **Pula** porque o gesto serve para uma coisa só, e ela disse qual:
  *"o PS+R3 altera a bridge, e isso permite que dentro do jogo eu possa testar
  a bridge sem fechar o jogo"*. Um degrau que exige REABRIR o jogo não testa
  nada dentro do jogo — ele pertence ao lançamento.

**FATO CORRIGIDO (29→30/08/2026).** Esta seção dizia *"não pula, porque pular
o `native` deixaria de fora a classe de jogos que escreve no hidraw direto
(Sackboy), e pular o `steam_input` deixaria de fora a classe 'só aceita Steam
Input' (DON'T SCREAM). Pular é perder de vez os dois jogos que motivaram a
escada existir; parar é só adiar."*

**A premissa era falsa, e a medição é curta:** o degrau caro já não era
alcançado por caminho nenhum, nem ao vivo nem no lançamento. `comecar` só arma
quando o perfil NÃO tem `mode`, e aí arma o PRIMEIRO degrau; com `mode` posto,
o ramo *"o perfil manda"* arma `None` — e depois do primeiro alinhamento todo
perfil tem `mode`.

    perfil SEM mode  -> motivo=primeiro_degrau  armar=gamepad/dualsense
    perfil mode=xbox -> motivo=perfil_manda     armar=None
    perfil mode=native -> motivo=perfil_manda   armar=None

Ou seja: **"parar" não adiava o degrau, só cobrava um aperto por ele.** É o
mesmo achado que `2b6bc5f9` registrou sem consertar — *"a escada nunca ARMA o
Nativo nem o Steam Input... fechá-lo mexe no ramo 'o perfil manda', que é
decisão dela"* — e ele continua aberto, e continua sendo dela.

O que o pulo GARANTE, e é o que `2b6bc5f9` acrescentou: a ponte de pé é
guardada (`_anotar_o_gesto(a_registrar=True)`) e o tique a grava no `mode` do
perfil sem carimbar, então o próximo lançamento abre a tentativa PARADA nela.
Ela não repaga os gestos que já gastou.

E o que "parar" custava foi MEDIDO, com os quatro jogos dela e quatro apertos
cada (`D-O-GESTO-DA-PONTE-E-UNIVERSAL-NAO-APRENDE-POR-JOGO`): o jogo SEM
carimbo perdia o 2º aperto (`xbox -> xbox`, nada), 3 trocas em 4 apertos,
enquanto os três carimbados faziam 4 em 4. **O gesto se comportava diferente
conforme o jogo tivesse ou não carimbo** — e o usuário novo, que não tem
carimbo em jogo nenhum, tinha o comportamento pior em TODOS eles.

DOIS APERTOS NÃO PODEM CUSTAR A PARTIDA (29/08/2026)
----------------------------------------------------
O parar acima custava DUAS coisas, e as duas foram medidas três vezes no
journal dela (Sackboy 26/08 03:40:45, Mullet 29/08 00:26:17, Touhou 29/08
03:19:14), sempre na mesma sequência de quatro linhas:

    ponte_escada_parou_no_degrau_caro  de=gamepad/xbox proximo=native/- ...
    ponte_escada_encerrada             degrau=gamepad/xbox gestos=2 ...
    ponte_troca_pedida_por_gesto       de=xbox escada=parou para=mouse_teclado

1. **o degrau em que ela estava EVAPORAVA.** `encerrar` não grava nada, e o
   `xbox` a que ela chegou com dois gestos sumia com a tentativa: o próximo
   lançamento armava o `mode` de antes e ela pagava os mesmos gestos. Agora o
   laço GUARDA a ponte de pé (`ponte_a_registrar`), e o tique a grava no `mode`
   do perfil — **sem carimbar**. Carimbar ali mataria o caminho para o Nativo
   (`proximo_degrau` recusa rodar havendo carimbo); alinhando só o `mode`, o
   próximo lançamento entrega `xbox`, a escada pergunta o degrau seguinte e,
   com o jogo ainda fora, `como_subir` responde `SUBIR_AGORA` — o Nativo é
   ARMADO no lançamento. É o que a escada já sabia fazer e ninguém chamava;
2. **o MESMO aperto caía no ciclo fixo** e levava a `mouse_teclado`: o gamepad
   sumia no meio da partida.

**O ponto 1 continua de pé, e é ele que sustenta tudo o que veio depois.** O
ponto 2 foi curado DUAS vezes no mesmo dia, e a segunda desfez a primeira de
propósito: a cura das 16:40 fez o aperto não trocar nada (`PASSO_PAROU`), e
isso comprou o silêncio ao preço de o gesto passar a se comportar diferente
conforme o jogo tivesse carimbo — ver § *O DEGRAU CARO NÃO PERTENCE AO GESTO*.
Hoje o aperto TROCA sempre; o que não acontece mais é a escada oferecer, ao
vivo, um degrau que só o lançamento alcança.

O LAÇO NÃO ANDA SOZINHO COM O JOGO ABERTO
------------------------------------------
Não há relógio que suba degrau. A escada avança em dois pontos só: o
lançamento (com o jogo ainda fora, onde recriar o vpad não custa nada a
ninguém) e o gesto DELA. Este é o desenho, não uma limitação temporária: cada
degrau ao vivo recria o vpad, e recriar o vpad com o jogo aberto arranca o
controle da mão dela (R-04, medido em 23/07/2026 e de novo em 19/08). Um laço
que subisse sozinho pagaria esse preço sem ela pedir.

É `como_subir` que sustenta isso mecanicamente, e por isso ele é chamado nos
DOIS pontos: com o jogo vivo ele nunca responde `SUBIR_AGORA`, e este módulo
só arma sozinho o que responde `SUBIR_AGORA`.

O QUE ESTE MÓDULO NÃO FAZ
-------------------------
**Não carimba.** Ele DIZ qual ponte carimbar; quem grava é
`profiles/manager.confirmar_ponte`, chamado de `launch_env`. Uma só gaveta, um
só escritor.

**Não confirma NO gesto.** Um `PS + R3` isolado continua sendo o contrário de
uma confirmação: é o sinal de que a ponte de pé NÃO pegou. O que confirma é o
gesto SEGUIDO DE SILÊNCIO com o jogo vivo — ela mexeu, parou de mexer, e
continuou jogando. Nesse caso o carimbo sai `POR_GESTO` (e não `POR_SILENCIO`),
porque foi a mão dela que pôs aquela ponte de pé; a distinção é a do esquema,
e `ponte_escada.por_que_confirmou` é a dona dela.

A MÁSCARA DO GESTO VOLTA PARA O PERFIL (29/08/2026)
---------------------------------------------------
O gesto tem um SEGUNDO registro vivo além da tentativa, e ele existe porque a
tentativa não cobre o caso que mais custa a ela: **o jogo com carimbo**. Ali a
escada não roda (e não deve rodar), `avancar_por_gesto` devolve `None`, e o
gesto dela trocava a ponte viva sem que nada no disco aprendesse. Medido no
journal: 24 apertos em 7 dias, porque os 23 perfis de jogo dela pedem
`dualsense` e ela joga em `xbox`.

`ponte_do_gesto` (a `GestoDela`) é esse registro: a ponte que o gesto deixou de
pé, o appid do jogo, e o relógio do silêncio. Ele vive no daemon como a
tentativa, morre com o jogo como ela, e o tique de 1 Hz é quem o colhe. Não é
uma segunda escada: é a mesma pergunta (*"que ponte ficou de pé, e ela parou de
reclamar?"*) para o caminho em que a escada, corretamente, não corre.
"""
from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.integrations import ponte_escada
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: O atributo do daemon VIVO onde a tentativa mora. Nome com underscore como
#: os vizinhos (`_launch_armed_for`, `_modo_anunciado`): é estado interno do
#: daemon, e o contrato público é este módulo.
ATRIBUTO_DA_TENTATIVA = "_ponte_tentativa"

#: O atributo do daemon VIVO onde mora a ponte que o GESTO dela deixou de pé.
#: Vizinho do de cima, e pelo mesmo motivo: estado do daemon, contrato público
#: neste módulo. Separado da tentativa porque ele existe justamente quando ela
#: NÃO existe — no jogo com carimbo, onde a escada não roda.
ATRIBUTO_DO_GESTO = "_ponte_do_gesto"

#: Por que a escada NÃO começou. Vocabulário de string, como os desfechos de
#: emulação em `daemon/subsystems/gamepad.py`.
COMECO_PRODUTO_JA_SABE = "produto_ja_sabe"
COMECO_FORA_DA_ESCADA = "fora_da_escada"
COMECO_ESCADA_ACABOU = "escada_acabou"
COMECO_DEGRAU_CARO = "degrau_caro"
COMECO_JOGO_VIVO = "jogo_vivo"
#: ...e por que ela começou.
COMECO_PRIMEIRO_DEGRAU = "primeiro_degrau"
COMECO_PERFIL_MANDA = "perfil_manda"

#: O que o gesto conseguiu fazer pela escada.
PASSO_SUBIU = "subiu"
#: O gesto PULOU um ou mais degraus que não se alcançam ao vivo e achou um que
#: se alcança. SUBSTITUI o `PASSO_PAROU` de 29/08/2026 (ver
#: `D-O-GESTO-DA-PONTE-E-UNIVERSAL-NAO-APRENDE-POR-JOGO`, o mesmo dia): o
#: `parou` existia para o gesto que não trocava nada, e é ele que não existe
#: mais.
PASSO_PULOU = "pulou"
PASSO_ESCADA_ACABOU = "escada_acabou"

#: Por que a tentativa terminou. NENHUM deles carimba, exceto `FIM_CONFIRMADA`.
FIM_CONFIRMADA = "confirmada_por_silencio"
FIM_JOGO_FECHOU = "jogo_fechou"
FIM_ESCADA_ACABOU = "escada_acabou"
FIM_DEGRAU_CARO = "degrau_caro"
FIM_OUTRA_TENTATIVA = "outra_tentativa"

#: As máscaras que o GESTO consegue aplicar ao vivo. É a interseção honesta
#: entre a `ESCADA` e o que `hotkey._aplicar_ponte` sabe construir — e a
#: ausência de `native` aqui não é esquecimento: entrar em Modo Nativo pelo
#: gesto mataria o próprio gesto (não há porta de volta pelo controle), e isso
#: já estava escrito em `build_next_bridge_callback`.
MASCARAS_AO_VIVO = frozenset({ponte_escada.MASCARA_DUALSENSE, ponte_escada.MASCARA_XBOX})


@dataclass
class Tentativa:
    """A subida em curso. VIVA: morre com o jogo, com o daemon, ou confirmada.

    `degrau` é o que está DE PÉ agora — não o que se pretende subir. Ele só
    avança depois que o aparelho confirma a máscara (`degrau_subiu`), pela
    mesma razão da MASCARA-01: o retorno do applier não prova nada, e a única
    prova é olhar o vpad depois.
    """

    appid: int
    epoch: int
    degrau: ponte_escada.Degrau
    #: Relógio da confirmação por silêncio. Nasce no instante em que o jogo é
    #: VISTO vivo (ver `ver_o_jogo`) e reinicia a cada gesto dela.
    ultimo_gesto: float
    #: O jogo já apareceu alguma vez? Antes disso, "não está vivo" significa
    #: "ainda não abriu" (Proton na 1ª execução leva até 15 minutos —
    #: `launch_env.WRAPPER_MARKER_WINDOW_SEC`), nunca "fechou".
    viu_o_jogo: bool = False
    gestos: int = 0

    @property
    def ponte(self) -> ponte_escada.Ponte:
        """A ponte de pé agora."""
        return self.degrau.ponte


@dataclass(frozen=True)
class Comeco:
    """O que o lançamento decidiu: a tentativa aberta e o degrau a armar."""

    tentativa: Tentativa | None
    #: O degrau que o LANÇAMENTO deve armar. `None` = não arme nada.
    armar: ponte_escada.Degrau | None
    motivo: str


@dataclass(frozen=True)
class Passo:
    """O que o gesto dela pode fazer pela escada AGORA."""

    #: O degrau que o gesto deve aplicar, ou None quando o laço não tem
    #: nenhum ao vivo para oferecer — e aí o gesto faz o que sempre fez.
    degrau: ponte_escada.Degrau | None
    #: A máscara a aplicar, quando há uma. Vocabulário de `hotkey`.
    mascara: str | None
    #: O preço do próximo degrau, de `ponte_escada.como_subir`.
    preco: str | None
    motivo: str
    #: Os degraus que este gesto PULOU por não se alcançarem ao vivo, na ordem
    #: da `ESCADA`. Existe para o `hotkey` avisar pela lightbar: um degrau
    #: pulado em silêncio é o defeito de 29/08 com outro nome.
    pulados: tuple[ponte_escada.Degrau, ...] = ()


@dataclass
class GestoDela:
    """A ponte que o GESTO dela deixou de pé, esperando o silêncio.

    VIVA, como a `Tentativa`: morre com o jogo, com o daemon, ou gravada. O que
    ela guarda a mais é o `appid`, porque este caminho não nasce do lançamento
    — nasce do gesto, e o gesto sozinho não sabe em que jogo está (quem sabe é
    `launch_env.launch_session_appid`, o mesmo sinal do resto da casa).
    """

    appid: int
    ponte: ponte_escada.Ponte
    #: Relógio do silêncio, reiniciado a cada gesto dela.
    ultimo_gesto: float
    gestos: int = 1
    #: Há um `mode` a alinhar AGORA, sem esperar silêncio nenhum. É o degrau
    #: caro: a tentativa foi encerrada e a ponte de pé evaporaria com ela.
    a_registrar: bool = False


@dataclass(frozen=True)
class Tique:
    """O que o relógio de 1 Hz encontrou."""

    #: A ponte a CARIMBAR, ou None. Quem grava é `profiles/manager`.
    carimbar: ponte_escada.Ponte | None = None
    #: A ponte a gravar no `mode` do perfil SEM carimbar, ou None. Ver
    #: `manager.alinhar_o_modo_do_appid` para por que as duas não são a mesma
    #: coisa: carimbar aqui mataria o caminho para o degrau seguinte.
    alinhar: ponte_escada.Ponte | None = None
    appid: int | None = None
    #: `POR_GESTO` ou `POR_SILENCIO`, quando há o que carimbar
    #: (`ponte_escada.por_que_confirmou`).
    por: str | None = None
    #: Por que a tentativa terminou, ou None quando ela segue em pé.
    fim: str | None = None


def _agora(agora: float | None) -> float:
    """Relógio MONOTÔNICO, e ele é próprio.

    O `arm_launch_profile` conta em `time.time()` porque o marker do wrapper é
    um epoch de parede gravado por outro processo. Aqui o que se mede é a
    distância entre dois eventos NOSSOS (o gesto e o tique), e para isso a
    parede é o relógio errado: um ajuste de NTP no meio de uma partida
    carimbaria uma ponte que ninguém confirmou, ou adiaria para sempre a que
    já estava confirmada.
    """
    return time.monotonic() if agora is None else agora


def em_curso(daemon: Any) -> Tentativa | None:
    """A tentativa aberta neste daemon, ou None."""
    valor = getattr(daemon, ATRIBUTO_DA_TENTATIVA, None)
    return valor if isinstance(valor, Tentativa) else None


def gesto_em_curso(daemon: Any) -> GestoDela | None:
    """A ponte que o gesto dela deixou de pé neste daemon, ou None."""
    valor = getattr(daemon, ATRIBUTO_DO_GESTO, None)
    return valor if isinstance(valor, GestoDela) else None


def _guardar_o_gesto(daemon: Any, gesto: GestoDela | None) -> None:
    """Grava (ou apaga) a ponte do gesto. Best-effort, como a tentativa."""
    with contextlib.suppress(Exception):
        setattr(daemon, ATRIBUTO_DO_GESTO, gesto)


def esquecer_o_gesto(daemon: Any) -> GestoDela | None:
    """Apaga o registro do gesto. Devolve o que estava lá."""
    gesto = gesto_em_curso(daemon)
    _guardar_o_gesto(daemon, None)
    return gesto


def _anotar_o_gesto(
    daemon: Any,
    *,
    appid: int,
    ponte: ponte_escada.Ponte,
    momento: float,
    gestos: int | None = None,
    a_registrar: bool = False,
) -> GestoDela:
    """Abre ou refresca o registro do gesto. Um por jogo, e o relógio reinicia.

    Jogo diferente do anotado: o registro velho morre sem gravar nada. Dois
    registros ao mesmo tempo seriam duas respostas para *"que ponte ficou de
    pé"*, que é o defeito que este módulo inteiro existe para não ter.
    """
    anterior = gesto_em_curso(daemon)
    if anterior is not None and anterior.appid == appid:
        anterior.ponte = ponte
        anterior.ultimo_gesto = momento
        anterior.gestos = anterior.gestos + 1 if gestos is None else gestos
        anterior.a_registrar = anterior.a_registrar or a_registrar
        return anterior
    novo = GestoDela(
        appid=appid,
        ponte=ponte,
        ultimo_gesto=momento,
        gestos=1 if gestos is None else gestos,
        a_registrar=a_registrar,
    )
    _guardar_o_gesto(daemon, novo)
    return novo


def gesto_deixou_de_pe(
    daemon: Any,
    *,
    appid: int | None,
    mascara: str | None,
    jogo_vivo: bool,
    agora: float | None = None,
) -> GestoDela | None:
    """Momento 2b: a ponte que o gesto dela deixou de pé. None = nada anotado.

    Chamado pelo `hotkey` DEPOIS de conferir a máscara viva — a disciplina da
    MASCARA-01: o retorno do applier vale `True` para três desfechos, e anotar
    pelo retorno anotaria uma ponte que não subiu.

    Quatro recusas, e cada uma tem um porquê que não é conveniência:

    - **sem jogo vivo**: fora de uma partida o gesto é ela mexendo na mesa, e o
      perfil de jogo nenhum tem o que aprender com isso;
    - **sem appid**: o jogo não veio pelo wrapper, então não há perfil de jogo
      para receber a máscara. Escrever no perfil errado é pior que não escrever;
    - **máscara fora das duas** (`mouse_teclado`, e o que mais o ciclo ganhar):
      não é degrau da `ESCADA` e não é ponte de gamepad. Gravar
      `mode.kind="desktop"` no perfil de um jogo porque ela passou por ali
      seria uma decisão de produto que ninguém pediu;
    - **há tentativa em curso**: aquele caminho já tem dono
      (`avancar_por_gesto` + `tique`), e dois donos para a mesma pergunta é
      como esta casa fabrica duas verdades.
    """
    if not jogo_vivo or appid is None or mascara not in MASCARAS_AO_VIVO:
        return None
    if em_curso(daemon) is not None:
        return None
    gesto = _anotar_o_gesto(
        daemon,
        appid=appid,
        ponte=ponte_escada.Ponte(ponte_escada.KIND_GAMEPAD, mascara),
        momento=_agora(agora),
    )
    logger.info(
        "ponte_do_gesto_anotada",
        appid=gesto.appid,
        ponte=gesto.ponte.chave,
        gestos=gesto.gestos,
        segundos=ponte_escada.SILENCIO_CONFIRMA_SEC,
    )
    return gesto


def _guardar(daemon: Any, tentativa: Tentativa | None) -> None:
    """Grava (ou apaga) a tentativa. Best-effort, como todo estado vivo daqui.

    `contextlib.suppress`: um daemon dublado com `__slots__` — ou qualquer
    objeto que recuse o atributo — não pode derrubar o lançamento nem o gesto
    dela por causa de um extra. Sem a tentativa, o produto volta a ser o de
    ontem; com uma exceção aqui, ele para.
    """
    with contextlib.suppress(Exception):
        setattr(daemon, ATRIBUTO_DA_TENTATIVA, tentativa)


def encerrar(daemon: Any, *, motivo: str) -> Tentativa | None:
    """Fecha a tentativa SEM carimbar nada. Devolve a que estava aberta.

    Todo caminho que passa por aqui é um caminho em que ninguém confirmou
    nada — inclusive (e principalmente) o jogo fechado no meio da escada. O
    carimbo tem uma porta só, e ela não é esta.
    """
    tentativa = em_curso(daemon)
    _guardar(daemon, None)
    if tentativa is not None:
        logger.info(
            "ponte_escada_encerrada",
            appid=tentativa.appid,
            degrau=tentativa.ponte.chave,
            gestos=tentativa.gestos,
            motivo=motivo,
        )
    return tentativa


def comecar(
    daemon: Any,
    *,
    appid: int,
    epoch: int,
    ponte_do_perfil: ponte_escada.Ponte | None,
    confirmada: ponte_escada.Ponte | None,
    jogo_vivo: bool,
    agora: float | None = None,
) -> Comeco:
    """Momento 1: o lançamento. Abre a tentativa e diz o que armar.

    `ponte_do_perfil` é a ponte que o perfil entrega HOJE (o `mode` dele), e
    `confirmada` é o carimbo — os dois já calculados pelo `arm_launch_profile`,
    que os passa em vez de recalcular: duas leituras do mesmo disco é como
    esta casa fabrica duas verdades (o achado do vdf de 16/08).

    Três desfechos, e o primeiro é o que protege o que já funciona:

    - **o produto SABE** (`confirmada`): `proximo_degrau` devolve `None` e a
      escada não roda. Nenhuma tentativa é aberta, e o gesto dela naquele jogo
      segue fazendo o que sempre fez;
    - **o perfil manda** (`ponte_do_perfil` é um degrau): a tentativa abre
      PARADA nesse degrau. Nada é armado pela escada — trocar o modo de um
      jogo dela sem ela pedir é a regra mais velha desta casa ao contrário. O
      que a tentativa acrescenta é o de onde CONTINUAR quando ela apertar;
    - **ninguém opinou**: a escada começa, e arma o primeiro degrau.

    E há a recusa que `como_subir` sustenta: com um jogo VIVO na autoridade, o
    lançamento não arma nada sozinho. Recriar o vpad ali arrancaria o controle
    da mão dela (R-04) por conta de um jogo que nem abriu ainda.
    """
    momento = _agora(agora)
    anterior = em_curso(daemon)
    if anterior is not None and (anterior.appid, anterior.epoch) != (appid, epoch):
        # Outro lançamento chegou: a tentativa velha morre sem carimbar. Duas
        # tentativas ao mesmo tempo seriam duas escadas confirmando uma na
        # frente da outra.
        encerrar(daemon, motivo=FIM_OUTRA_TENTATIVA)

    degrau = ponte_escada.proximo_degrau(
        ponte_atual=ponte_do_perfil, confirmada=confirmada
    )
    if degrau is None:
        # As três recusas de `proximo_degrau`, distinguidas aqui só para o
        # journal — a decisão é lá, e continua sendo uma só.
        if confirmada is not None:
            motivo = COMECO_PRODUTO_JA_SABE
        elif ponte_do_perfil is not None and ponte_escada.indice_do_degrau(
            ponte_do_perfil
        ) < 0:
            motivo = COMECO_FORA_DA_ESCADA
        else:
            motivo = COMECO_ESCADA_ACABOU
        _guardar(daemon, None)
        logger.info("ponte_escada_nao_roda", appid=appid, motivo=motivo)
        return Comeco(tentativa=None, armar=None, motivo=motivo)

    if ponte_do_perfil is not None:
        # O perfil manda: a tentativa abre no degrau DELE, e o `degrau` que
        # `proximo_degrau` devolveu fica para o primeiro gesto dela.
        posicao = ponte_escada.indice_do_degrau(ponte_do_perfil)
        tentativa = Tentativa(
            appid=appid,
            epoch=epoch,
            degrau=ponte_escada.ESCADA[posicao],
            ultimo_gesto=momento,
        )
        _guardar(daemon, tentativa)
        logger.info(
            "ponte_escada_aberta",
            appid=appid,
            degrau=tentativa.ponte.chave,
            motivo=COMECO_PERFIL_MANDA,
        )
        return Comeco(tentativa=tentativa, armar=None, motivo=COMECO_PERFIL_MANDA)

    preco = ponte_escada.como_subir(degrau, jogo_vivo=jogo_vivo)
    if preco != ponte_escada.SUBIR_AGORA:
        # Com jogo vivo o preço nunca é `SUBIR_AGORA` — e o degrau que exige
        # fechar a Steam não é `SUBIR_AGORA` nem com a mesa vazia. Nos dois
        # casos o lançamento não arma: a escada não paga o R-04 sozinha, e não
        # fecha a Steam de ninguém.
        motivo = COMECO_JOGO_VIVO if jogo_vivo else COMECO_DEGRAU_CARO
        _guardar(daemon, None)
        logger.info(
            "ponte_escada_nao_arma",
            appid=appid,
            degrau=degrau.ponte.chave,
            preco=preco,
            motivo=motivo,
        )
        return Comeco(tentativa=None, armar=None, motivo=motivo)

    tentativa = Tentativa(
        appid=appid, epoch=epoch, degrau=degrau, ultimo_gesto=momento
    )
    _guardar(daemon, tentativa)
    logger.info(
        "ponte_escada_aberta",
        appid=appid,
        degrau=degrau.ponte.chave,
        porque=degrau.porque,
        motivo=COMECO_PRIMEIRO_DEGRAU,
    )
    return Comeco(
        tentativa=tentativa, armar=degrau, motivo=COMECO_PRIMEIRO_DEGRAU
    )


def avancar_por_gesto(
    daemon: Any, *, jogo_vivo: bool, agora: float | None = None
) -> Passo | None:
    """Momento 2: ela apertou `PS + R3`. Devolve o degrau a aplicar, ou None.

    **O gesto é a vontade explícita dela e sempre obedece** — não é este
    módulo que decide se troca. O que ele lê no gesto é outra coisa: *o degrau
    de pé NÃO funcionou.* É daí, e só daí, que a escada aprende.

    Duas coisas acontecem sempre que há tentativa: o relógio do silêncio
    reinicia (ela reclamou; os três minutos recomeçam) e o contador de gestos
    sobe. Depois disso, o próximo degrau:

    - **alcançável ao vivo** (uma das duas máscaras): devolvido para o gesto
      aplicar. Quem CONFIRMA que ele subiu é `degrau_subiu`, depois de olhar o
      aparelho — o retorno do applier não prova nada (MASCARA-01);
    - **caro** (exige reabrir o jogo ou fechar a Steam): AVISA, GUARDA e
      **PULA** — a caminhada segue para o degrau seguinte. Ver o cabeçalho,
      § *O DEGRAU CARO NÃO PERTENCE AO GESTO*;
    - **inexistente** (a escada acabou, ou só sobraram caros): a tentativa é
      encerrada e o gesto volta ao `CICLO_DE_PONTES`.

    Quando `mascara` é `None`, o gesto volta ao `CICLO_DE_PONTES` de sempre.
    Ele nunca fica sem resposta — e desde 29/08/2026 ele nunca fica sem
    TROCA, que é o que o fazia divergir entre um jogo carimbado e um sem.
    """
    tentativa = em_curso(daemon)
    if tentativa is None:
        return None
    momento = _agora(agora)
    tentativa.ultimo_gesto = momento
    tentativa.gestos += 1

    # A CAMINHADA. Cada volta pergunta o degrau seguinte e olha se ele se
    # alcança COM O JOGO ABERTO. O que não se alcança é PULADO — anotado em
    # `pulados` para o aviso, e deixado para o lançamento, onde ele é de graça.
    # `de_onde` anda junto porque `proximo_degrau` não guarda posição: quem diz
    # onde a escada está é a ponte que se passa a ela.
    de_onde = tentativa.ponte
    pulados: list[ponte_escada.Degrau] = []
    while True:
        degrau = ponte_escada.proximo_degrau(
            ponte_atual=de_onde,
            # A tentativa só existe onde NÃO há carimbo — `comecar` não abre
            # nenhuma com `confirmada`. Passar `None` aqui é dizer isso, não
            # afrouxar a regra: quem tem carimbo nem chega neste caminho.
            confirmada=None,
        )
        if degrau is None:
            break
        preco = ponte_escada.como_subir(degrau, jogo_vivo=jogo_vivo)
        mascara = degrau.ponte.mascara
        alcancavel = (
            degrau.ao_vivo
            and degrau.ponte.kind == ponte_escada.KIND_GAMEPAD
            and mascara in MASCARAS_AO_VIVO
        )
        if alcancavel:
            logger.info(
                "ponte_escada_degrau_pedido",
                appid=tentativa.appid,
                de=tentativa.ponte.chave,
                para=degrau.ponte.chave,
                preco=preco,
                pulados=[d.ponte.chave for d in pulados],
                gestos=tentativa.gestos,
            )
            return Passo(
                degrau=degrau,
                mascara=mascara,
                preco=preco,
                motivo=PASSO_PULOU if pulados else PASSO_SUBIU,
                pulados=tuple(pulados),
            )
        # PULA, e NÃO EM SILÊNCIO. O journal diz qual degrau ficou de fora e o
        # que ele custaria, porque é ela quem pode pagá-lo: reabrir o jogo, ou
        # fechar a Steam e reabrir os dois. O `hotkey` pisca a cor DESTE modo
        # antes de aplicar a troca.
        logger.warning(
            "ponte_escada_pulou_o_degrau_caro",
            appid=tentativa.appid,
            de=tentativa.ponte.chave,
            pulado=degrau.ponte.chave,
            preco=preco,
            porque=degrau.porque,
            fica_para_o_lancamento=True,
        )
        pulados.append(degrau)
        de_onde = degrau.ponte

    # A escada acabou — ou porque não havia degrau seguinte, ou porque todos os
    # que sobravam eram caros. Nos DOIS casos a tentativa morre aqui, e o gesto
    # volta ao `CICLO_DE_PONTES` do `hotkey`: ele nunca fica sem resposta.
    #
    # E o degrau em que ela ESTÁ é guardado ANTES de a tentativa morrer — esta
    # é a metade de `2b6bc5f9` (29/08/2026) que continua de pé: o tique grava a
    # ponte no `mode` do perfil SEM carimbar, e o próximo lançamento abre a
    # tentativa PARADA nela em vez de recomeçar do `mode` de antes. Ela ganha
    # os gestos que já gastou.
    #
    # NÃO SE AFIRMA AQUI QUE O NATIVO SERÁ ARMADO NO LANÇAMENTO — foi MEDIDO
    # em 30/08/2026 que ele não é, por caminho nenhum:
    #
    #     perfil SEM mode  -> motivo=primeiro_degrau  armar=gamepad/dualsense
    #     perfil mode=xbox -> motivo=perfil_manda     armar=None
    #
    # O ramo `perfil manda` de `comecar` arma `None` por decisão, e depois do
    # primeiro alinhamento TODO perfil tem `mode`. É o mesmo achado que
    # `2b6bc5f9` registrou sem consertar (*"a escada nunca ARMA o Nativo nem o
    # Steam Input... fechá-lo mexe no ramo 'o perfil manda', que é decisão
    # dela"*), e continua aberto e dela. O pulo não o perde porque não havia o
    # que perder: o degrau já não era alcançado por lugar nenhum.
    _anotar_o_gesto(
        daemon,
        appid=tentativa.appid,
        ponte=tentativa.ponte,
        momento=momento,
        gestos=tentativa.gestos,
        a_registrar=bool(pulados),
    )
    encerrar(daemon, motivo=FIM_DEGRAU_CARO if pulados else FIM_ESCADA_ACABOU)
    logger.info(
        "ponte_escada_esgotada",
        appid=tentativa.appid,
        de=tentativa.ponte.chave,
        pulados=[d.ponte.chave for d in pulados],
    )
    return Passo(
        degrau=pulados[-1] if pulados else None,
        mascara=None,
        preco=None,
        motivo=PASSO_ESCADA_ACABOU,
        pulados=tuple(pulados),
    )


def degrau_subiu(daemon: Any, degrau: ponte_escada.Degrau) -> bool:
    """Carimba na tentativa que o degrau está DE PÉ. True = anotado.

    Chamado pelo gesto DEPOIS de conferir a máscara viva, nunca antes. A
    disciplina é a da MASCARA-01: `set_gamepad_emulation` devolve `True` para
    três desfechos diferentes (aplicou, já-estava, foi bloqueado), então
    avançar a tentativa pelo retorno faria o laço acreditar estar num degrau
    que nunca subiu — e o gesto seguinte pularia o degrau que faltava tentar.
    """
    tentativa = em_curso(daemon)
    if tentativa is None:
        return False
    tentativa.degrau = degrau
    return True


def ver_o_jogo(
    daemon: Any, *, jogo_vivo: bool, agora: float | None = None
) -> str | None:
    """Acompanha o jogo. Devolve o motivo do FIM quando a tentativa morre.

    Duas bordas, e a diferença entre elas é o que impede o laço de confirmar
    ou de desistir na hora errada:

    - **o jogo apareceu**: o relógio do silêncio começa AQUI, e não no
      lançamento. `SILENCIO_CONFIRMA_SEC` registra o porquê com número:
      launch→janela chega a 15 minutos (Proton na 1ª execução, shaders,
      launcher de terceiro), e contar dali confirmaria o degrau enquanto ela
      ainda olha uma tela preta;
    - **o jogo sumiu depois de ter aparecido**: a tentativa morre sem
      carimbar. Silêncio com o jogo fechado não é ela aprovando a ponte — é
      ela tendo ido embora, e `confirmacao_por_silencio` já recusa esse caso.
      Encerrar aqui é o que impede a tentativa de sobreviver ao jogo e
      confirmar na sessão seguinte.

    Enquanto o jogo NUNCA apareceu, "não está vivo" não decide nada: é o
    estado normal dos primeiros minutos.
    """
    tentativa = em_curso(daemon)
    if tentativa is None:
        return None
    if jogo_vivo:
        if not tentativa.viu_o_jogo:
            tentativa.viu_o_jogo = True
            tentativa.ultimo_gesto = _agora(agora)
            logger.info(
                "ponte_escada_jogo_apareceu",
                appid=tentativa.appid,
                degrau=tentativa.ponte.chave,
            )
        return None
    if tentativa.viu_o_jogo:
        encerrar(daemon, motivo=FIM_JOGO_FECHOU)
        return FIM_JOGO_FECHOU
    return None


def silencio_confirma(
    daemon: Any, *, jogo_vivo: bool, agora: float | None = None
) -> ponte_escada.Ponte | None:
    """Momento 3: a ponte que o silêncio dela confirma, ou None.

    Fachada fina sobre `ponte_escada.confirmacao_por_silencio` — a regra é
    dela, e ela não é reescrita aqui. O que este laço acrescenta é o
    `ponte_atual` (o degrau de pé da tentativa) e o `ultimo_gesto` (o relógio
    que a tentativa mantém).

    Devolve a `Ponte` a carimbar. **Não grava**: quem grava é
    `profiles/manager.confirmar_ponte`, chamado por `launch_env`. Uma gaveta,
    um escritor.
    """
    tentativa = em_curso(daemon)
    if tentativa is None:
        return None
    return ponte_escada.confirmacao_por_silencio(
        ponte_atual=tentativa.ponte,
        ultimo_gesto=tentativa.ultimo_gesto,
        agora=_agora(agora),
        jogo_vivo=jogo_vivo,
        # A tentativa só existe sem carimbo (`comecar` recusa abrir com um).
        confirmada=None,
        # E `gestos` decide o `por=` do carimbo, não SE ele sai: aqui não há
        # carimbo para recusar. Ver `ponte_escada.por_que_confirmou`.
        gestos=tentativa.gestos,
    )


def tique(daemon: Any, *, jogo_vivo: bool, agora: float | None = None) -> Tique:
    """O relógio de 1 Hz da escada: acompanha o jogo e colhe a confirmação.

    Ordem deliberada: **ver o jogo ANTES de perguntar pelo silêncio.** É a
    primeira passada com o jogo vivo que ARMA o relógio; perguntar antes disso
    mediria o silêncio a partir do lançamento, que é exatamente o erro que
    `SILENCIO_CONFIRMA_SEC` documenta. E é ela também que encerra a tentativa
    quando o jogo fecha — antes que o silêncio de um jogo fechado seja lido
    como aprovação.
    """
    momento = _agora(agora)
    tentativa = em_curso(daemon)
    if tentativa is None:
        # Sem escada correndo, sobra o caminho que a escada não cobre: a ponte
        # que o GESTO dela deixou de pé num jogo que o produto já "sabia".
        return _tique_do_gesto(daemon, jogo_vivo=jogo_vivo, momento=momento)
    fim = ver_o_jogo(daemon, jogo_vivo=jogo_vivo, agora=momento)
    if fim is not None:
        return Tique(appid=tentativa.appid, fim=fim)
    ponte = silencio_confirma(daemon, jogo_vivo=jogo_vivo, agora=momento)
    if ponte is None:
        return Tique()
    encerrar(daemon, motivo=FIM_CONFIRMADA)
    # A mesma pergunta, respondida: um registro de gesto deste jogo não pode
    # sobreviver ao carimbo e mandar gravar de novo no tique seguinte.
    esquecer_o_gesto(daemon)
    por = ponte_escada.por_que_confirmou(tentativa.gestos)
    logger.info(
        "ponte_escada_confirmada_por_silencio",
        appid=tentativa.appid,
        ponte=ponte.chave,
        gestos=tentativa.gestos,
        por=por,
        segundos=ponte_escada.SILENCIO_CONFIRMA_SEC,
    )
    return Tique(
        carimbar=ponte,
        # Carimbo por GESTO alinha o `mode` junto: num perfil que opina, o
        # carimbo sozinho não muda o próximo lançamento — `arm_launch_profile`
        # só lê o carimbo quando `mode is None`, porque *"o perfil manda"*. Por
        # SILÊNCIO não alinha: ninguém pediu troca nenhuma, e o carimbo já
        # preenche o silêncio de um perfil sem `mode`.
        alinhar=ponte if por == ponte_escada.POR_GESTO else None,
        appid=tentativa.appid,
        por=por,
        fim=FIM_CONFIRMADA,
    )


def _tique_do_gesto(daemon: Any, *, jogo_vivo: bool, momento: float) -> Tique:
    """O tique do registro de GESTO — o caminho sem tentativa aberta.

    Três desfechos, nesta ordem, e a ordem é a entrega:

    1. **há `mode` a registrar AGORA** (o degrau caro): sai antes de qualquer
       pergunta sobre o jogo estar vivo, de propósito. Alinhar o `mode` NÃO é
       confirmar — é anotar onde ela estava —, e é justamente o jogo fechando
       que fazia esse dado evaporar;
    2. **o jogo sumiu**: o registro morre sem carimbar nada, pela mesma regra da
       tentativa. Silêncio com o jogo fechado é ela tendo ido embora;
    3. **passou o silêncio**: carimba `POR_GESTO` e alinha o `mode` na mesma
       gravação — o carimbo sozinho não muda o próximo lançamento de um perfil
       que opina (ver `manager.alinhar_o_modo_com_a_ponte`).
    """
    gesto = gesto_em_curso(daemon)
    if gesto is None:
        return Tique()
    if gesto.a_registrar:
        # O GESTO É ESQUECIDO AQUI, E NÃO SÓ MARCADO COMO REGISTRADO.
        #
        # MEDIDO em 29/08/2026, e era regressão: pôr `a_registrar = False` e
        # deixar o `GestoDela` VIVO fazia os 180 s seguintes caírem em
        # `confirmacao_por_silencio(confirmada=None, gestos=N)` — que carimba
        # `POR_GESTO` **o degrau que ela acabou de recusar**. No lançamento
        # seguinte a escada via `produto_ja_sabe`, `proximo_degrau` devolvia
        # `None`, e **o caminho para o Modo Nativo morria**.
        #
        # A régua que cobria este ramo rodava o tique UMA VEZ e parava. A vida
        # não para: t+181 s carimbava. Os 67 testes daquela leva passavam com
        # esta linha aqui — prova de que a régua nunca alcançou o caso.
        #
        # ALINHAR NÃO É CONFIRMAR, e é essa a distinção que o esquecimento
        # protege: o `mode` do perfil recebe a máscara que o gesto dela pôs de
        # pé (para o próximo lançamento não armar o errado), e o CARIMBO não
        # nasce — a escada continua aberta e o degrau caro continua alcançável
        # no lançamento seguinte, que é onde ele cabe.
        esquecer_o_gesto(daemon)
        logger.info(
            "ponte_de_pe_a_registrar",
            appid=gesto.appid,
            ponte=gesto.ponte.chave,
            gestos=gesto.gestos,
        )
        return Tique(alinhar=gesto.ponte, appid=gesto.appid)
    if not jogo_vivo:
        esquecer_o_gesto(daemon)
        logger.info(
            "ponte_do_gesto_esquecida",
            appid=gesto.appid,
            ponte=gesto.ponte.chave,
            motivo=FIM_JOGO_FECHOU,
        )
        return Tique(appid=gesto.appid, fim=FIM_JOGO_FECHOU)
    ponte = ponte_escada.confirmacao_por_silencio(
        ponte_atual=gesto.ponte,
        ultimo_gesto=gesto.ultimo_gesto,
        agora=momento,
        jogo_vivo=jogo_vivo,
        # Sem carimbo a comparar: este módulo não lê disco, e o registro só
        # existe porque a mão DELA moveu a ponte viva. Quem confere o que já
        # está gravado é o escritor, que já tem o perfil aberto.
        confirmada=None,
        gestos=gesto.gestos,
    )
    if ponte is None:
        return Tique()
    esquecer_o_gesto(daemon)
    # `por_que_confirmou` também aqui, e não um `POR_GESTO` digitado: a escolha
    # entre os dois nomes tem UM dono, e é `ponte_escada`. (Este registro só
    # nasce de um gesto, então ele responde sempre `POR_GESTO` — o ponto é não
    # haver um segundo lugar onde alguém possa responder outra coisa.)
    por = ponte_escada.por_que_confirmou(gesto.gestos)
    logger.info(
        "ponte_do_gesto_confirmada",
        appid=gesto.appid,
        ponte=ponte.chave,
        gestos=gesto.gestos,
        por=por,
        segundos=ponte_escada.SILENCIO_CONFIRMA_SEC,
    )
    return Tique(
        carimbar=ponte,
        alinhar=ponte,
        appid=gesto.appid,
        por=por,
        fim=FIM_CONFIRMADA,
    )


__all__ = [
    "ATRIBUTO_DA_TENTATIVA",
    "ATRIBUTO_DO_GESTO",
    "COMECO_DEGRAU_CARO",
    "COMECO_ESCADA_ACABOU",
    "COMECO_FORA_DA_ESCADA",
    "COMECO_JOGO_VIVO",
    "COMECO_PERFIL_MANDA",
    "COMECO_PRIMEIRO_DEGRAU",
    "COMECO_PRODUTO_JA_SABE",
    "FIM_CONFIRMADA",
    "FIM_DEGRAU_CARO",
    "FIM_ESCADA_ACABOU",
    "FIM_JOGO_FECHOU",
    "FIM_OUTRA_TENTATIVA",
    "MASCARAS_AO_VIVO",
    "PASSO_ESCADA_ACABOU",
    "PASSO_PULOU",
    "PASSO_SUBIU",
    "Comeco",
    "GestoDela",
    "Passo",
    "Tentativa",
    "Tique",
    "avancar_por_gesto",
    "comecar",
    "degrau_subiu",
    "em_curso",
    "encerrar",
    "esquecer_o_gesto",
    "gesto_deixou_de_pe",
    "gesto_em_curso",
    "silencio_confirma",
    "tique",
    "ver_o_jogo",
]
