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
  `daemon/subsystems/hotkey.py` (no gesto do usuário). Nenhum dos dois ganhou
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
- **Pula** porque o gesto serve para uma coisa só, e o usuário disse qual. Um degrau que exige
  REABRIR o jogo não testa
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
decisão de produto"* — e ele continua aberto, e continua sendo dela.

O que o pulo GARANTE, e é o que `2b6bc5f9` acrescentou: a ponte de pé é
guardada (`_anotar_o_gesto(a_registrar=True)`) e o tique a grava no `mode` do
perfil sem carimbar, então o próximo lançamento abre a tentativa PARADA nela.
Ela não repaga os gestos que já gastou.

E o que "parar" custava foi MEDIDO, com os quatro jogos do usuário e quatro apertos
cada (`D-O-GESTO-DA-PONTE-E-UNIVERSAL-NAO-APRENDE-POR-JOGO`): o jogo SEM
carimbo perdia o 2º aperto (`xbox -> xbox`, nada), 3 trocas em 4 apertos,
enquanto os três carimbados faziam 4 em 4. **O gesto se comportava diferente
conforme o jogo tivesse ou não carimbo** — e o usuário novo, que não tem
carimbo em jogo nenhum, tinha o comportamento pior em TODOS eles.

DOIS APERTOS NÃO PODEM CUSTAR A PARTIDA (29/08/2026)
----------------------------------------------------
O parar acima custava DUAS coisas, e as duas foram medidas três vezes no
journal da bancada (Sackboy 26/08 03:40:45, Mullet 29/08 00:26:17, Touhou 29/08
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
ninguém) e o gesto do usuário. Este é o desenho, não uma limitação temporária: cada
degrau ao vivo recria o vpad, e recriar o vpad com o jogo aberto arranca o
controle da mão do usuário (R-04, medido em 23/07/2026 e de novo em 19/08). Um laço
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
gesto SEGUIDO DE SILÊNCIO com o jogo vivo — o usuário mexeu, parou de mexer, e
continuou jogando. Nesse caso o carimbo sai `POR_GESTO` (e não `POR_SILENCIO`),
porque foi a mão do usuário que pôs aquela ponte de pé; a distinção é a do esquema,
e `ponte_escada.por_que_confirmou` é a dona dela.

A MÁSCARA DO GESTO VOLTA PARA O PERFIL (29/08/2026)
---------------------------------------------------
O gesto tem um SEGUNDO registro vivo além da tentativa, e ele existe porque a
tentativa não cobre o caso que mais custa a ela: **o jogo com carimbo**. Ali a
escada não roda (e não deve rodar), `avancar_por_gesto` devolve `None`, e o
gesto do usuário trocava a ponte viva sem que nada no disco aprendesse. Medido no
journal: 24 apertos em 7 dias, porque os 23 perfis de jogo do usuário pedem
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
from hefesto_dualsense4unix.integrations.virtual_pad import (
    CAMINHO_DUALSENSE,
    CAMINHO_XBOX,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

ATRIBUTO_DA_TENTATIVA = "_ponte_tentativa"

ATRIBUTO_DO_GESTO = "_ponte_do_gesto"

COMECO_PRODUTO_JA_SABE = "produto_ja_sabe"
COMECO_FORA_DA_ESCADA = "fora_da_escada"
COMECO_ESCADA_ACABOU = "escada_acabou"
COMECO_DEGRAU_CARO = "degrau_caro"
COMECO_JOGO_VIVO = "jogo_vivo"
COMECO_PRIMEIRO_DEGRAU = "primeiro_degrau"
COMECO_PERFIL_MANDA = "perfil_manda"

PASSO_SUBIU = "subiu"
PASSO_PULOU = "pulou"
PASSO_ESCADA_ACABOU = "escada_acabou"

FIM_CONFIRMADA = "confirmada_por_silencio"
FIM_JOGO_FECHOU = "jogo_fechou"
FIM_ESCADA_ACABOU = "escada_acabou"
FIM_DEGRAU_CARO = "degrau_caro"
FIM_OUTRA_TENTATIVA = "outra_tentativa"

#: entre a `ESCADA` e o que `hotkey._aplicar_ponte` sabe construir — e a
#: caminhos da tela («Sony DualSense» e «Xbox»), e é caminho que o gesto aplica.
CAMINHOS_AO_VIVO = frozenset({CAMINHO_DUALSENSE, CAMINHO_XBOX})


@dataclass
class Tentativa:
    """A subida em curso. VIVA: morre com o jogo, com o daemon, ou confirmada."""

    appid: int
    epoch: int
    degrau: ponte_escada.Degrau
    ultimo_gesto: float
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
    armar: ponte_escada.Degrau | None
    motivo: str


@dataclass(frozen=True)
class Passo:
    """O que o gesto do usuário pode fazer pela escada AGORA."""

    degrau: ponte_escada.Degrau | None
    caminho: str | None
    preco: str | None
    motivo: str
    pulados: tuple[ponte_escada.Degrau, ...] = ()


@dataclass
class GestoDela:
    """A ponte que o GESTO do usuário deixou de pé, esperando o silêncio."""

    appid: int
    ponte: ponte_escada.Ponte
    ultimo_gesto: float
    gestos: int = 1
    a_registrar: bool = False


@dataclass(frozen=True)
class Tique:
    """O que o relógio de 1 Hz encontrou."""

    carimbar: ponte_escada.Ponte | None = None
    alinhar: ponte_escada.Ponte | None = None
    appid: int | None = None
    por: str | None = None
    fim: str | None = None


def _agora(agora: float | None) -> float:
    """Relógio MONOTÔNICO, e ele é próprio."""
    return time.monotonic() if agora is None else agora


def em_curso(daemon: Any) -> Tentativa | None:
    """A tentativa aberta neste daemon, ou None."""
    valor = getattr(daemon, ATRIBUTO_DA_TENTATIVA, None)
    return valor if isinstance(valor, Tentativa) else None


def gesto_em_curso(daemon: Any) -> GestoDela | None:
    """A ponte que o gesto do usuário deixou de pé neste daemon, ou None."""
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
    """Abre ou refresca o registro do gesto. Um por jogo, e o relógio reinicia."""
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
    caminho: str | None,
    jogo_vivo: bool,
    agora: float | None = None,
) -> GestoDela | None:
    """Momento 2b: a ponte que o gesto do usuário deixou de pé. None = nada anotado.

    NOTA DATADA — MODO-DE-CONEXAO-01, 13/09/2026. O registro guardava a MÁSCARA
    que o gesto pôs de pé, e o tique a alinhava em ``mode.gamepad_flavor`` do
    perfil do jogo. O gesto passou a andar por CAMINHOS, grava o caminho no
    perfil ATIVO na hora (`Daemon.gravar_o_modo_escolhido`, pelo setter do
    modo, desde a O-MODO-SE-GRAVA-ONDE-ELE-MUDA-01), e o que este
    registro leva ao perfil do jogo depois do silêncio é o caminho também
    (`manager.alinhar_o_modo_com_a_ponte`). A máscara não passa mais por aqui.

    Chamado pelo `hotkey` DEPOIS de conferir a máscara viva — a disciplina da
    MASCARA-01: o retorno do applier vale `True` para três desfechos, e anotar
    pelo retorno anotaria uma ponte que não subiu.

    Quatro recusas, e cada uma tem um porquê que não é conveniência:

    - **sem jogo vivo**: fora de uma partida o gesto é ela mexendo na mesa, e o
      perfil de jogo nenhum tem o que aprender com isso;
    - **sem appid**: o jogo não veio pelo wrapper, então não há perfil de jogo
      para receber a máscara. Escrever no perfil errado é pior que não escrever;
    - **caminho fora dos dois** (`mouse_teclado`, e o que mais o ciclo ganhar):
      não é degrau da `ESCADA` e não é ponte de gamepad. Gravar
      `mode.kind="desktop"` no perfil de um jogo porque ela passou por ali
      seria uma decisão de produto que ninguém pediu;
    - **há tentativa em curso**: aquele caminho já tem dono
      (`avancar_por_gesto` + `tique`), e dois donos para a mesma pergunta é
      como esta casa fabrica duas verdades.
    """
    if not jogo_vivo or appid is None or caminho not in CAMINHOS_AO_VIVO:
        return None
    if em_curso(daemon) is not None:
        return None
    gesto = _anotar_o_gesto(
        daemon,
        appid=appid,
        ponte=ponte_escada.Ponte(ponte_escada.KIND_GAMEPAD, caminho),
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
    """Grava (ou apaga) a tentativa. Best-effort, como todo estado vivo daqui."""
    with contextlib.suppress(Exception):
        setattr(daemon, ATRIBUTO_DA_TENTATIVA, tentativa)


def encerrar(daemon: Any, *, motivo: str) -> Tentativa | None:
    """Fecha a tentativa SEM carimbar nada. Devolve a que estava aberta."""
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
    """Momento 1: o lançamento. Abre a tentativa e diz o que armar."""
    momento = _agora(agora)
    anterior = em_curso(daemon)
    if anterior is not None and (anterior.appid, anterior.epoch) != (appid, epoch):
        encerrar(daemon, motivo=FIM_OUTRA_TENTATIVA)

    degrau = ponte_escada.proximo_degrau(
        ponte_atual=ponte_do_perfil, confirmada=confirmada
    )
    if degrau is None:
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
    """Momento 2: o usuário apertou `PS + R3`. Devolve o degrau a aplicar, ou None."""
    tentativa = em_curso(daemon)
    if tentativa is None:
        return None
    momento = _agora(agora)
    tentativa.ultimo_gesto = momento
    tentativa.gestos += 1

    de_onde = tentativa.ponte
    pulados: list[ponte_escada.Degrau] = []
    while True:
        degrau = ponte_escada.proximo_degrau(
            ponte_atual=de_onde,
            confirmada=None,
        )
        if degrau is None:
            break
        preco = ponte_escada.como_subir(degrau, jogo_vivo=jogo_vivo)
        caminho = degrau.ponte.mascara
        alcancavel = (
            degrau.ao_vivo
            and degrau.ponte.kind == ponte_escada.KIND_GAMEPAD
            and caminho in CAMINHOS_AO_VIVO
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
                caminho=caminho,
                preco=preco,
                motivo=PASSO_PULOU if pulados else PASSO_SUBIU,
                pulados=tuple(pulados),
            )
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
        caminho=None,
        preco=None,
        motivo=PASSO_ESCADA_ACABOU,
        pulados=tuple(pulados),
    )


def degrau_subiu(daemon: Any, degrau: ponte_escada.Degrau) -> bool:
    """Carimba na tentativa que o degrau está DE PÉ. True = anotado."""
    tentativa = em_curso(daemon)
    if tentativa is None:
        return False
    tentativa.degrau = degrau
    return True


def ver_o_jogo(
    daemon: Any, *, jogo_vivo: bool, agora: float | None = None
) -> str | None:
    """Acompanha o jogo. Devolve o motivo do FIM quando a tentativa morre."""
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
    """Momento 3: a ponte que o silêncio dela confirma, ou None."""
    tentativa = em_curso(daemon)
    if tentativa is None:
        return None
    return ponte_escada.confirmacao_por_silencio(
        ponte_atual=tentativa.ponte,
        ultimo_gesto=tentativa.ultimo_gesto,
        agora=_agora(agora),
        jogo_vivo=jogo_vivo,
        confirmada=None,
        gestos=tentativa.gestos,
    )


def tique(daemon: Any, *, jogo_vivo: bool, agora: float | None = None) -> Tique:
    """O relógio de 1 Hz da escada: acompanha o jogo e colhe a confirmação."""
    momento = _agora(agora)
    tentativa = em_curso(daemon)
    if tentativa is None:
        return _tique_do_gesto(daemon, jogo_vivo=jogo_vivo, momento=momento)
    fim = ver_o_jogo(daemon, jogo_vivo=jogo_vivo, agora=momento)
    if fim is not None:
        return Tique(appid=tentativa.appid, fim=fim)
    ponte = silencio_confirma(daemon, jogo_vivo=jogo_vivo, agora=momento)
    if ponte is None:
        return Tique()
    encerrar(daemon, motivo=FIM_CONFIRMADA)
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
        alinhar=ponte if por == ponte_escada.POR_GESTO else None,
        appid=tentativa.appid,
        por=por,
        fim=FIM_CONFIRMADA,
    )


def _tique_do_gesto(daemon: Any, *, jogo_vivo: bool, momento: float) -> Tique:
    """O tique do registro de GESTO — o caminho sem tentativa aberta."""
    gesto = gesto_em_curso(daemon)
    if gesto is None:
        return Tique()
    if gesto.a_registrar:
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
        confirmada=None,
        gestos=gesto.gestos,
    )
    if ponte is None:
        return Tique()
    esquecer_o_gesto(daemon)
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
    "CAMINHOS_AO_VIVO",
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
