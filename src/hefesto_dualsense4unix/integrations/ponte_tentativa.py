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

O DEGRAU QUE NÃO SE ALCANÇA AO VIVO: **avisa e para**
-----------------------------------------------------
Os dois últimos degraus da `ESCADA` não alcançam um processo já rodando —
`native` porque a env congelou no `exec` (o resultado ao vivo é ZERO
controles, `launch_env._nativos_fora_da_antecipacao`), `steam_input` porque o
`localconfig.vdf` só sobrevive com a Steam fechada. Quando a escada chega
neles com o jogo aberto, este laço **avisa e para**; não pula, e não finge.

- **Não finge** porque subir ali ao vivo é o degrau que MENTE — é o que o
  cabeçalho de `ponte_escada` já dizia com todas as letras.
- **Não pula** porque pular o `native` deixaria de fora a classe de jogos que
  escreve no hidraw direto (Sackboy, medido em 06/08), e pular o
  `steam_input` deixaria de fora a classe *"só aceita Steam Input"* (DON'T
  SCREAM, medido em 18→19/08). Pular é perder de vez os dois jogos que
  motivaram a escada existir; parar é só adiar.
- **Para** — e a tentativa é ENCERRADA. Ela acabou de dizer, pelo gesto, que
  o degrau de pé não serve; deixar a tentativa aberta faria o silêncio dos
  três minutos seguintes carimbar justamente o degrau que ela recusou.

E o GESTO não para junto: quando o laço não tem degrau ao vivo para oferecer,
o gesto volta a fazer o que sempre fez (o `CICLO_DE_PONTES` do `hotkey`). A
regra que nenhum dos dois quebra: **o gesto sempre troca alguma coisa.**

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

**Não confirma por gesto.** `POR_GESTO` existe no esquema para a porta em que
ela AFIRMA que uma ponte pegou (a aba de perfil). O `PS + R3` é o contrário
disso: é o sinal de que a ponte de pé NÃO pegou. Ler o mesmo gesto como
confirmação seria inventar uma promessa que o produto não faz.
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
PASSO_PAROU = "parou"
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


@dataclass(frozen=True)
class Tique:
    """O que o relógio de 1 Hz encontrou."""

    #: A ponte a CARIMBAR, ou None. Quem grava é `profiles/manager`.
    carimbar: ponte_escada.Ponte | None = None
    appid: int | None = None
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
    - **caro** (exige reabrir o jogo ou fechar a Steam): o laço AVISA e PARA,
      e a tentativa é encerrada. Ver o cabeçalho: parar adia, pular perde;
    - **inexistente** (a escada acabou): encerrada também. Nada mais a tentar
      e nada a confirmar — ela acabou de recusar o último degrau.

    Nos três casos em que `mascara` é `None`, o gesto volta ao `CICLO_DE_PONTES`
    de sempre. Ele nunca fica sem resposta.
    """
    tentativa = em_curso(daemon)
    if tentativa is None:
        return None
    momento = _agora(agora)
    tentativa.ultimo_gesto = momento
    tentativa.gestos += 1

    degrau = ponte_escada.proximo_degrau(
        ponte_atual=tentativa.ponte,
        # A tentativa só existe onde NÃO há carimbo — `comecar` não abre
        # nenhuma com `confirmada`. Passar `None` aqui é dizer isso, não
        # afrouxar a regra: quem tem carimbo nem chega neste caminho.
        confirmada=None,
    )
    if degrau is None:
        encerrar(daemon, motivo=FIM_ESCADA_ACABOU)
        logger.info(
            "ponte_escada_esgotada", appid=tentativa.appid, de=tentativa.ponte.chave
        )
        return Passo(
            degrau=None, mascara=None, preco=None, motivo=PASSO_ESCADA_ACABOU
        )

    preco = ponte_escada.como_subir(degrau, jogo_vivo=jogo_vivo)
    mascara = degrau.ponte.mascara
    alcancavel = (
        degrau.ao_vivo
        and degrau.ponte.kind == ponte_escada.KIND_GAMEPAD
        and mascara in MASCARAS_AO_VIVO
    )
    if not alcancavel:
        # AVISA E PARA. O journal diz o que falta acontecer, porque é ela quem
        # pode fazê-lo: reabrir o jogo, ou fechar a Steam e reabrir os dois.
        logger.warning(
            "ponte_escada_parou_no_degrau_caro",
            appid=tentativa.appid,
            de=tentativa.ponte.chave,
            proximo=degrau.ponte.chave,
            preco=preco,
            porque=degrau.porque,
        )
        encerrar(daemon, motivo=FIM_DEGRAU_CARO)
        return Passo(degrau=degrau, mascara=None, preco=preco, motivo=PASSO_PAROU)

    logger.info(
        "ponte_escada_degrau_pedido",
        appid=tentativa.appid,
        de=tentativa.ponte.chave,
        para=degrau.ponte.chave,
        preco=preco,
        gestos=tentativa.gestos,
    )
    return Passo(degrau=degrau, mascara=mascara, preco=preco, motivo=PASSO_SUBIU)


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
    tentativa = em_curso(daemon)
    if tentativa is None:
        return Tique()
    fim = ver_o_jogo(daemon, jogo_vivo=jogo_vivo, agora=agora)
    if fim is not None:
        return Tique(appid=tentativa.appid, fim=fim)
    ponte = silencio_confirma(daemon, jogo_vivo=jogo_vivo, agora=agora)
    if ponte is None:
        return Tique()
    encerrar(daemon, motivo=FIM_CONFIRMADA)
    logger.info(
        "ponte_escada_confirmada_por_silencio",
        appid=tentativa.appid,
        ponte=ponte.chave,
        gestos=tentativa.gestos,
        segundos=ponte_escada.SILENCIO_CONFIRMA_SEC,
    )
    return Tique(carimbar=ponte, appid=tentativa.appid, fim=FIM_CONFIRMADA)


__all__ = [
    "ATRIBUTO_DA_TENTATIVA",
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
    "PASSO_PAROU",
    "PASSO_SUBIU",
    "Comeco",
    "Passo",
    "Tentativa",
    "Tique",
    "avancar_por_gesto",
    "comecar",
    "degrau_subiu",
    "em_curso",
    "encerrar",
    "silencio_confirma",
    "tique",
    "ver_o_jogo",
]
