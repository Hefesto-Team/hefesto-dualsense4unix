"""Está entrando som NESTE microfone agora? — o medidor da luz do mic.

LUZ-DO-MIC-01, PEÇA B (03/09/2026). Esta peça responde UMA pergunta, por
controle: *está entrando som neste microfone agora?* Quem decide a luz é a
PEÇA C (`daemon/subsystems/luz_do_mic.py`); quem diz se **alguém está ouvindo**
é a PEÇA A (`integrations/quem_ouve_o_microfone.py`). Aqui só se mede.

O CONTRATO DE SAÍDA são três valores, e a diferença entre dois deles é o
coração da peça:

* ``True``  — medi, e está entrando som.
* ``False`` — medi, e não está.
* ``None``  — **não sei**. Sem canal para este controle (o do rádio não publica
  nenhum), sem ``parec`` na máquina, fluxo recém-aberto que ainda não entregou
  amostra, ou fluxo vivo que parou de entregar. ``None`` NUNCA vira ``False``:
  ``False`` diz "medi e não há som", e a luz apagaria mentindo.

## O CAMINHO, e por que é este

O pico é calculado **pelo servidor**, não por nós. O PipeWire não publica nível
de sinal por propriedade nenhuma — medido 03/09 no ``pw-dump`` inteiro, as
únicas chaves que casam com ``peak|level|rms`` são ``resample.peaks`` (um
BOTÃO, não um valor), ``linking.role-based.duck-level``, ``log.level`` e
``nice.level``: nenhuma é nível de sinal. Mas esse botão existe, e é o caminho:
``resample.peaks=true`` troca a reamostragem por ``max|x|`` do bloco. A 25 Hz o
cliente recebe 25 float32 por segundo, ou seja **100 bytes/s por canal, já
mastigados**. Do nosso lado sobra um ``struct.unpack`` de quatro bytes.

**Zero dependência nova**, e isso é requisito da PEÇA E: o ``parec`` sai do
MESMO pacote que o ``pactl`` (``pulseaudio-utils``), que o ``install.sh:504``
já declara para as três famílias. Do lado Python é só a biblioteca padrão —
o ``numpy`` NÃO está no ``pyproject.toml`` (vive no ``~/.local`` dela), e
importá-lo aqui repetiria a dívida do ``playwright`` que o `CLAUDE.md` cobra.

**O modo de pico entrega o pico VERDADEIRO, e isto é medida, não confiança.**
20 s com DOIS fluxos abertos na MESMA fonte do DualSense ao mesmo tempo: o
nosso, a 25 Hz com ``resample.peaks``, deu ``max = 0,013535`` (-37,37 dBFS) em
500 amostras; uma captura CRUA de 48 kHz ao lado, verdade de campo, deu
``max = 0,013550`` (-37,36 dBFS) em 960.000 amostras. A razão entre os dois é
**0,9989** — os dois máximos distam 0,01 dB, meio passo de quantização do s16
que a captura crua usa. **Mesmo pico, com 1/960 do tráfego** (100 B/s contra
96.000 B/s).

Medido em 03/09/2026, e cada linha é uma decisão:

* ``--property=resample.peaks=true`` no argv LIGA o modo de pico — provado pela
  mordida, na MESMA fonte e no mesmo minuto: com a propriedade, ``max =
  0,013535``; sem ela, ``max = 0,000245`` (-72,2 dBFS), **55 vezes menor** e
  vinte e cinco vezes abaixo do limiar de entrada. Sem a propriedade a luz
  nunca piscaria, e o defeito seria silencioso: o fluxo abre, as amostras
  chegam, e todas dizem "silêncio".
* ``--latency-msec=100`` **não é opcional**. Com o fragmento padrão a primeira
  amostra do ``parec`` chega aos **2,006 s** (e ``stdbuf`` não resolve); com a
  flag, aos 96 ms (mediana de cinco corridas). Sem ela o medidor mede o passado
  e a luz pisca fora do tempo.

## O CUSTO, medido com ESTE módulo, por QUATRO réguas independentes

Régua: CPU por processo lida em ``/proc/<pid>/stat`` (utime+stime), janela de
30 a 40 s **descartando a partida** — o custo aparente de 18 % da primeira
corrida do levantamento era PARTIDA, não regime. Somam-se o Python deste
módulo, os ``parec`` filhos e os deltas de ``pipewire``, ``pipewire-pulse`` e
``wireplumber``. Percentuais são de **UM** núcleo; a máquina dela tem 16.

.. _custo-medido:

=================  ==========  ==========  ==========  ==========
canais medindo     corrida A   corrida B   corrida C   corrida D
=================  ==========  ==========  ==========  ==========
0 (piso)           0,000 %     0,000 %     0,000 %     0,000 %
1                  0,109 %     0,125 %     0,153 %     0,300 %
4                  0,325 %     0,350 %     0,357 %     0,400 %
=================  ==========  ==========  ==========  ==========

**QUATRO canais custam entre 0,33 % e 0,40 % de UM núcleo — no pior caso
0,025 % das 16 linhas dela.** É esse o número que decide, porque a mesa é de
quatro, e ele é estável: quatro medições feitas por réguas escritas
separadamente caem numa faixa de 0,08 pontos percentuais.

O de UM canal é ruidoso de propósito (0,11 a 0,30 %) e não deve ser citado
sozinho: ele mora no chão do instrumento. O ``/proc`` conta em tiques de 10 ms,
o que dá ±0,025 pontos percentuais numa janela de 40 s, e a máquina tinha
outros agentes trabalhando (``loadavg`` entre 1,2 e 2,4 durante as corridas).

O custo NÃO cresce quatro vezes — o marginal do 2º ao 4º canal é pequeno,
porque os quatro compartilham o mesmo servidor de som e o mesmo ``epoll``.

**O DEGRAU MENOR VEIO COMO DESENHO, não como recuo.** Este módulo só abre
fluxo para os ``uniq`` que :meth:`NivelDoMicrofone.seguir` receber — e o
chamador (PEÇA C) passa só os controles que a PEÇA A já disse ter ouvinte. É a
precedência da §1.1 da sprint escrita em código: o estado 2 (piscando) só pode
existir dentro do estado 1 (aceso). Na mesa dela, com ninguém ouvindo, o custo
desta peça é **zero processo e zero por cento** — nada é aberto.

Amostrar por JANELAS curtas foi medido e REJEITADO: a partida é barata (45 a
280 ms), mas abrir e fechar a 0,2 Hz faz o nó piscar entre ``RUNNING`` e
``SUSPENDED``, e é exatamente esse grafo que a PEÇA A lê — o medidor passaria a
tremer a leitura da outra peça, e a ligar e desligar o isócrono USB o dia
inteiro.

## A HISTERESE, e por que ela tem TRÊS degraus

Sem histerese o pisca vira estroboscópio a cada sílaba. Mas o defeito tem uma
segunda porta, e ela custou o número desta seção: **a luz também acende
sozinha, com a sala vazia.** É o mesmo estroboscópio pelo avesso.

**A MEDIÇÃO QUE MANDOU AQUI:** 605 s (15.120 amostras) do mic do DualSense pelo
cabo, sala como ela deixou, ninguém falando.

=======  ==========  ==========
quantil  linear      dBFS
=======  ==========  ==========
p50      0,008713    -41,20
p90      0,011978    -38,43
p99      0,017502    -35,14
p99,9    0,041824    -27,57
p100     0,225800    -12,93
=======  ==========  ==========

O p100 é o número que decide, e ele **não é piso**: só 19 das 15.120 amostras
passam de -30 dBFS (0,126 %). São IMPULSOS isolados — um clique, uma tecla, o
tique de uma ventoinha —, cada um durando uma amostra de 40 ms. O piso
propriamente dito está lá embaixo, no p90 de -38,4 dBFS.

**Por isso subir só a amplitude é a cura errada**, e a grade mede o porquê:
mesmo a -18 dBFS a luz ainda acende sozinha duas vezes em 605 s, e a essa
altura ela já perdeu a fala. O que separa impulso de fala não é altura, é
DURAÇÃO. Daí o terceiro degrau:

* **Amplitude para entrar** — :data:`LIMIAR_ENTRA` (-24,0 dBFS). Deixa 11 dB de
  folga sobre o p99 do piso.
* **Duração para entrar** — :data:`ENTRA_S` (120 ms). O pico tem de ficar acima
  do limiar de entrada por 120 ms CONTÍNUOS, ou seja quatro amostras seguidas a
  25 Hz. Um impulso de uma amostra não passa; uma sílaba passa.
* **Amplitude e tempo para sair** — abaixo de :data:`LIMIAR_SAI` (-30,0 dBFS)
  por :data:`SEGURA_S` (0,6 s) contínuos. A pausa entre duas sílabas é bem mais
  curta que isto: é o que separa "a luz acompanha a fala" de "a luz acompanha a
  forma de onda".

Acendimentos falsos nos MESMOS 605 s de sala real, por par (entrada, duração):

========  ======  ======  ======  ======  ======
entrada   0 ms    80 ms   120 ms  160 ms  200 ms
========  ======  ======  ======  ======  ======
-30 dBFS  9       2       1       1       0
-28 dBFS  9       1       1       1       0
-26 dBFS  7       1       0       0       0
-24 dBFS  5       0       0       0       0
-22 dBFS  3       0       0       0       0
========  ======  ======  ======  ======  ======

O par que este módulo usa é **-24 dBFS com 120 ms**.

O par escolhido não está na beirada do zero: os quatro vizinhos dele na grade
(-26/120 ms, -22/120 ms, -24/80 ms, -24/160 ms) também são zero. E **o par
anterior deste módulo, -30/-36 dBFS sem degrau de duração, acendia a luz nove
vezes** nesses mesmos 605 s, deixando-a acesa 7,2 s — 1,2 % do tempo, com
ninguém na sala. Aquele número não era piso medido: era o piso de uma janela de
31,7 s, curta demais para conter um impulso.

**Duas réguas independentes chegaram no mesmo -24 dBFS.** O levantamento da
peça mediu cinco janelas espalhadas por ~25 min e recomendou "por volta de -24
dBFS" pela contagem de cruzamentos; esta grade chegou lá pela contagem de
acendimentos com histerese completa. É o padrão desta casa: duas réguas, uma
resposta.

**O QUE CONTINUA NÃO MEDIDO, e é honesto dizer:** a âncora de CIMA. Ninguém
gerou fala na sala dela a esta hora. A escolha de 120 ms sobre 200 ms veio de
um MODELO de fala (sílabas de 160/200/240 ms com pausas de 120 ms, caindo ao
piso entre elas): a 200 ms de duração exigida, sílaba nenhuma de 160 ms acende
a luz em amplitude nenhuma; a 120 ms, uma sílaba de 160 ms acende. O modelo é o
pior caso — fala conectada não cai ao piso dentro de uma palavra —, mas modelo
não é medida. **A palavra final é a bancada com ela**, e é por isso que os
QUATRO valores são parâmetros do construtor, não constantes cravadas no laço.

## A TRAVA DE MORTE — um ``parec`` vazado prende o microfone DELA

Não é hipótese. Em 03/09, às 00h36, um ``parec`` deste medidor ficou órfão
(``ppid=1``) segurando a fonte do DualSense dela em ``RUNNING`` por **39
minutos**, num cgroup que não é unit do Hefesto — um ``systemctl --user stop``
do daemon não o recolheria. Ele foi morto à mão e a fonte voltou a ``IDLE``.

**O que segura o filho é o CANO, e isso foi isolado**, matando o pai com
SIGKILL em quatro desenhos:

===========================  ======================
desenho do ``stdout``        o filho…
===========================  ======================
``/dev/null``, mesma sessão  SOBREVIVE — ``ppid=1``
``/dev/null``, sessão nova   SOBREVIVE — ``ppid=1``
``PIPE``, mesma sessão       morre junto
``PIPE``, sessão nova        morre junto
===========================  ======================

A sessão é irrelevante; o cano é tudo. Com o pai morto, a ponta de leitura
fecha, o próximo write do ``parec`` toma ``SIGPIPE`` e ele cai — e em modo de
pico há write a cada 40 ms, então a janela é curta. **Por isso
:func:`abrir_fluxo` usa ``stdout=subprocess.PIPE`` e mais nada**: mandar essa
saída para arquivo, para ``DEVNULL`` ou para um fd herdado reabre exatamente o
vazamento de 00h36. Há teste que morde isso.

O cano cobre a morte do pai. Ele NÃO cobre um ``parec`` vivo que para de
entregar — esse ficaria de pé, mudo, com o microfone dela aberto. Quem cobre é
:data:`MUDEZ_S`: o fluxo que emudece por mais que isso é **fechado**, não só
respondido com ``None``. Soltar o microfone dela é obrigação, não zelo.

## A IDENTIDADE — o dono é ESTE arquivo, e a razão é uma junta

Se o nosso próprio medidor contar como ouvinte, a luz acende sozinha e a PEÇA A
mente. Esse defeito **não mora dentro de nenhuma das duas peças**: mora na
junta. Por isso o crivo é constante daqui e a PEÇA A o IMPORTA — o mesmo
movimento que :data:`~hefesto_dualsense4unix.integrations.fontes_de_captura.PREFIXO_SOURCE_PONTE_BT`
já fez nesta casa, pelo mesmo motivo. Quem precisa digitar um nome que já
existe noutro arquivo, LEIA de lá: use :func:`e_stream_do_medidor`.

Medido em ``pactl list source-outputs`` com o argv de :func:`argv_do_medidor`,
verbatim: ``application.name = "hefesto-medidor-de-nivel"``,
``node.name = "hefesto-medidor-de-nivel"``,
``application.id = "br.dev.hefesto.luz_do_mic"``,
``hefesto.papel = "medidor-de-nivel"``, ``hefesto.uniq = "143a9a0000ab"`` e
``resample.peaks = "true"``.

O crivo aceita TRÊS marcas, e a ordem não é preferência estética:

1. ``resample.peaks = "true"`` é o **intrínseco**. Um fluxo em modo de pico
   recebe envelope, não áudio — ele estruturalmente não consegue ouvir, seja
   nosso ou de quem for. Sobrevive a qualquer mudança de nome que façamos.
2. ``hefesto.papel = "medidor-de-nivel"`` é o **explícito**.
3. ``application.id`` é o terceiro.

**NÃO se põe ``media.role`` no fluxo.** Medido: com ``media.role=Production`` o
servidor grava ``module-stream-restore.id =
"source-output-by-media-role:production"`` — estado de restauração
COMPARTILHADO com todo fluxo de papel produção, e mexer no volume dele mexeria
no de estranhos. Sem ele o id vira
``source-output-by-application-id:br.dev.hefesto.luz_do_mic``, que é só nosso.

**O QUE ESTE CRIVO NÃO ALCANÇA, e é dívida declarada:** o outro ``parec`` desta
casa. `app/mic_monitor.py:635` (`_abrir_captura`) abre um ``parec`` CRU, que
aparece como ``application.name = "parec"`` — indistinguível do ``parec`` de
qualquer outro programa. Com a janela aberta na aba Status, a PEÇA A vê aquele
fluxo como ouvinte. A cura é de uma linha (acrescentar as mesmas propriedades
ao argv de lá) e o arquivo não é desta peça: fica escrito aqui para ter dono.
"""

from __future__ import annotations

import contextlib
import math
import os
import selectors
import shutil
import struct
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# --------------------------------------------------------------------------
# A IDENTIDADE — dono único, e a PEÇA A lê daqui
# --------------------------------------------------------------------------

#: Como o servidor de som nos chama (``application.name`` e ``node.name``).
#: É o único crivo que sobrevive às DUAS formas de cliente (pulse e PipeWire
#: nativo): a forma nativa não publica ``application.process.id`` nenhum, então
#: excluir por PID deixaria a luz acesa sozinha.
NOME_DO_MEDIDOR = "hefesto-medidor-de-nivel"

#: ``media.name`` do fluxo. Aparece na lista como o nome do que estamos ouvindo.
NOME_DO_FLUXO = "luz-do-mic"

#: ``application.id``. Reverso desta casa, específico da luz.
APLICACAO_ID = "br.dev.hefesto.luz_do_mic"

#: A chave e o valor do papel — o crivo EXPLÍCITO.
CHAVE_DO_PAPEL = "hefesto.papel"
PAPEL_DO_MEDIDOR = "medidor-de-nivel"

#: A chave que carrega DE QUE controle é este medidor. Não serve só para
#: excluir: deixa a PEÇA A dizer *qual* controle estamos medindo, sem ter de
#: casar índice de fonte com ``uniq`` uma segunda vez.
CHAVE_DO_UNIQ = "hefesto.uniq"

#: A propriedade que LIGA o modo de pico do reamostrador — e que é, ao mesmo
#: tempo, o crivo INTRÍNSECO: quem recebe envelope não consegue ouvir.
CHAVE_DO_PICO = "resample.peaks"
VALOR_DO_PICO = "true"


def propriedades_do_medidor(uniq: str = "") -> dict[str, str]:
    """As propriedades que o nosso fluxo publica no servidor de som.

    Medidas chegando verbatim ao ``pactl list source-outputs`` em 03/09/2026.
    `uniq` vazio quer dizer "não sei de quem é este medidor" e a chave sai da
    lista — melhor faltar do que publicar um endereço inventado.
    """
    props = {
        CHAVE_DO_PICO: VALOR_DO_PICO,
        "application.id": APLICACAO_ID,
        CHAVE_DO_PAPEL: PAPEL_DO_MEDIDOR,
    }
    if uniq:
        props[CHAVE_DO_UNIQ] = uniq
    return props


def e_stream_do_medidor(propriedades: Mapping[str, str]) -> bool:
    """Este fluxo de captura é o NOSSO medidor? — o crivo que a PEÇA A usa.

    Recebe o bloco ``Properties:`` de um ``Source Output`` já em dicionário e
    responde se ele deve ser DESCONTADO da conta de quem ouve. Três marcas
    independentes, em OU: basta uma. Ver o cabeçalho do módulo para a ordem e
    a razão de cada uma.

    Aceitar ``resample.peaks`` de QUALQUER aplicativo é deliberado: um fluxo em
    modo de pico recebe ``max|x|`` por bloco, não áudio — ele não consegue
    ouvir ninguém, seja nosso ou de estranho. Contar um medidor alheio como
    ouvinte acenderia a luz por um aplicativo que também só está medindo.
    """
    if propriedades.get(CHAVE_DO_PICO, "").strip().lower() == VALOR_DO_PICO:
        return True
    if propriedades.get(CHAVE_DO_PAPEL, "").strip() == PAPEL_DO_MEDIDOR:
        return True
    return propriedades.get("application.id", "").strip() == APLICACAO_ID


# --------------------------------------------------------------------------
# A RÉGUA
# --------------------------------------------------------------------------

#: Amostras por segundo que o servidor entrega. 25 Hz = 100 bytes/s por canal,
#: e é o passo de 40 ms com que a luz pode reagir.
TAXA_HZ = 25

#: Pico que ACENDE, se sustentado por :data:`ENTRA_S` (-24,0 dBFS). Onze dB
#: acima do p99 do piso medido em 605 s de sala real (-35,14 dBFS).
LIMIAR_ENTRA = 0.0631

#: Por quanto tempo CONTÍNUO o pico tem de ficar acima de :data:`LIMIAR_ENTRA`
#: para acender — quatro amostras seguidas a 25 Hz. É o degrau que separa
#: IMPULSO de FALA, e sem ele a luz acende sozinha nove vezes em 605 s de sala
#: vazia: os 19 estouros que o piso dela tem são de uma amostra cada.
ENTRA_S = 0.12

#: Pico abaixo do qual começa a contar o apagamento (-30,0 dBFS), 6 dB abaixo
#: da entrada.
LIMIAR_SAI = 0.0316

#: Quanto tempo CONTÍNUO abaixo de :data:`LIMIAR_SAI` para apagar. A pausa
#: entre duas sílabas é bem mais curta que isto — é o que separa "a luz
#: acompanha a fala" de "a luz acompanha a forma de onda".
SEGURA_S = 0.6

#: Fluxo vivo que para de entregar amostra por este tempo volta a ser ``None``
#: **e é fechado**. Um ``parec`` pendurado (vivo, mudo) responderia ``False``
#: para sempre, com toda a confiança do mundo — e ``False`` é uma afirmação,
#: não uma ausência. Pior: ele seguraria o microfone DELA aberto, que é o
#: vazamento medido de 00h36 entrando por outra porta. Ver a §TRAVA DE MORTE.
MUDEZ_S = 3.0

#: Folga numérica dos degraus de TEMPO, e ela tem razão de ser: os instantes
#: das amostras são RECONSTRUÍDOS por divisão (ver :meth:`NivelDoMicrofone._comer`)
#: e o relógio chega em ponto flutuante. "Exatamente :data:`ENTRA_S` decorrido"
#: erra na 13ª casa decimal e vira cara ou coroa — a quarta amostra de uma
#: rajada acenderia ou não conforme o arredondamento. Um microssegundo é
#: quarenta mil vezes menor que o passo de 40 ms: não muda comportamento
#: nenhum, só tira a moeda do ar.
_FOLGA_S = 1e-6

_TAM_AMOSTRA = 4  # float32
_LOTE_BYTES = 4096
_ESPERA_DO_SELETOR_S = 0.2
_ESPERA_APOS_MORTE_S = 2.0

#: Espera depois de recolher um fluxo que emudeceu. É mais longa que a de
#: morte de propósito: abrir e fechar em rajada faz o nó da fonte piscar entre
#: ``RUNNING`` e ``SUSPENDED``, e é esse grafo que a PEÇA A lê para contar
#: ouvintes — o medidor passaria a tremer a leitura da outra peça.
_ESPERA_APOS_MUDEZ_S = 10.0


@dataclass
class Histerese:
    """A régua de TRÊS degraus: amplitude, duração para entrar, tempo para sair.

    Pura, sem relógio próprio. O instante entra por parâmetro de propósito — é
    o que deixa o teste provar o comportamento no tempo sem dormir, e o que
    deixa a régua ser exercitada com um relógio falso.

    O degrau do meio, :attr:`entra_s`, é o que a medição de 605 s exigiu: sem
    ele, os 19 impulsos de uma amostra que a sala dela tem acendem a luz nove
    vezes com ninguém falando. Ver a §HISTERESE do módulo.
    """

    limiar_entra: float = LIMIAR_ENTRA
    limiar_sai: float = LIMIAR_SAI
    segura_s: float = SEGURA_S
    entra_s: float = ENTRA_S
    _captando: bool = field(default=False, init=False)
    _ultimo_alto: float = field(default=0.0, init=False)
    _acima_desde: float | None = field(default=None, init=False)
    _viu: bool = field(default=False, init=False)

    def aplicar(self, pico: float, agora: float) -> bool | None:
        """Come uma amostra e devolve o estado. Amostra suja é ignorada."""
        if not math.isfinite(pico):
            return self.estado(agora)
        valor = abs(pico)
        self._viu = True
        if valor >= self.limiar_sai:
            self._ultimo_alto = agora
        if not self._captando:
            if valor < self.limiar_entra:
                # Caiu abaixo: a contagem de duração RECOMEÇA. É isto que faz
                # um impulso de 40 ms não acender — ele não tem sucessor.
                self._acima_desde = None
            else:
                if self._acima_desde is None:
                    self._acima_desde = agora
                if (agora - self._acima_desde) >= self.entra_s - _FOLGA_S:
                    self._captando = True
                    self._ultimo_alto = agora
        return self.estado(agora)

    def estado(self, agora: float) -> bool | None:
        """O estado AGORA — e é aqui que o tempo apaga, não só a amostra.

        Sem esta reavaliação, um fluxo que emudece de vez ficaria aceso para
        sempre: o apagamento depende de tempo decorrido, e tempo passa mesmo
        quando não chega amostra nenhuma.
        """
        if not self._viu:
            return None
        if self._captando and (agora - self._ultimo_alto) >= self.segura_s - _FOLGA_S:
            self._captando = False
            self._acima_desde = None
        return self._captando


# --------------------------------------------------------------------------
# O FLUXO — o que se abre por canal
# --------------------------------------------------------------------------


class Fluxo(Protocol):
    """O mínimo que o medidor precisa de uma captura aberta."""

    @property
    def fd(self) -> int:
        """Descritor de onde saem os float32 do pico."""

    def vivo(self) -> bool:
        """Ainda está de pé?"""

    def parar(self) -> None:
        """Fecha, sem levantar."""


def argv_do_medidor(fonte: str, uniq: str = "") -> list[str]:
    """O argv do ``parec`` que mede o pico desta fonte.

    Sem ``shell=True`` (invariante do projeto): a fonte entra como argumento e
    nunca como texto de comando.

    As duas flags que a medição de 03/09 tornou obrigatórias:

    * ``--property=resample.peaks=true`` — sem ela vêm 25 amostras por segundo
      da onda DECIMADA (57 de 58 negativas, amplitude cem vezes menor), e o
      limiar nunca dispara: a luz nunca piscaria.
    * ``--latency-msec=100`` — sem ela a primeira amostra chega aos 2,006 s.
    """
    argv = [
        "parec",
        f"--device={fonte}",
        "--format=float32le",
        f"--rate={TAXA_HZ}",
        "--channels=1",
        "--latency-msec=100",
        "--client-name=" + NOME_DO_MEDIDOR,
        "--stream-name=" + NOME_DO_FLUXO,
    ]
    argv += [f"--property={k}={v}" for k, v in propriedades_do_medidor(uniq).items()]
    return argv


def _morrer_com_o_pai() -> None:
    """Pede ao kernel um SIGKILL neste filho quando o processo pai morrer.

    O `parec` VAZOU ÓRFÃO, e foi medido na máquina dela em 03/09/2026: três
    gerações diferentes de `parec` sobreviveram aos processos que as lançaram —
    a última com `PPID=1`, 42 s de vida e o `hefesto.uniq` no `cmdline`. Cada
    uma segurava a fonte de captura do controle em `RUNNING`, ou seja: **o
    microfone dela ficava aberto por um processo que ninguém estava lendo.**

    Sem isto, matar o daemon (ou o agente, ou a sessão) não mata o medidor: o
    `parec` é reparentado ao `init` e continua gravando para um cano que não
    tem leitor. O `terminate()` do `_FluxoParec` só alcança o caso em que o pai
    teve chance de rodar o `finally` — morte por `SIGKILL`, `OOM` ou queda da
    sessão não dá essa chance, e é justamente quando o vazamento acontece.

    `PR_SET_PDEATHSIG` é a única garantia que não depende de o pai colaborar. O
    `start_new_session=True` seria o OPOSTO do que se quer aqui: ele DESLIGA o
    filho do grupo do pai, que é como o processo sobrevive ao terminal.

    O `preexec_fn` roda entre o `fork` e o `exec`, no filho. O aviso do ruff
    (PLW1509) é sobre segurança em programa com threads — aqui a chamada é um
    único `prctl` sem alocação, que é exatamente o uso que a documentação do
    CPython admite.

    Em plataforma sem `PR_SET_PDEATHSIG` a função não faz nada e o processo
    nasce igual: degradar em silêncio é melhor que recusar a medição inteira
    num sistema que não é Linux.
    """
    with contextlib.suppress(Exception):
        import ctypes

        PR_SET_PDEATHSIG = 1  # noqa: N806 - o nome é do kernel
        ctypes.CDLL("libc.so.6", use_errno=True).prctl(
            PR_SET_PDEATHSIG, signal.SIGKILL, 0, 0, 0
        )


def _ambiente_c() -> dict[str, str]:
    """`LC_ALL=C`: a saída das ferramentas de som é TRADUZIDA nesta máquina."""
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    return env


@dataclass
class _FluxoParec:
    """Um ``parec`` em modo de pico, visto como :class:`Fluxo`."""

    proc: Any

    @property
    def fd(self) -> int:
        return int(self.proc.stdout.fileno())

    def vivo(self) -> bool:
        return self.proc.poll() is None

    def parar(self) -> None:
        with contextlib.suppress(OSError):  # pragma: no cover - defensivo
            self.proc.terminate()
        try:
            self.proc.wait(timeout=2.0)
        except Exception:  # pragma: no cover - defensivo
            with contextlib.suppress(OSError):
                self.proc.kill()
        with contextlib.suppress(OSError):  # pragma: no cover - defensivo
            if self.proc.stdout is not None:
                self.proc.stdout.close()


def abrir_fluxo(fonte: str, uniq: str = "") -> Fluxo | None:
    """Abre a captura de pico desta fonte — ``None`` quando não dá.

    ``None`` é resposta: sem ``parec`` na máquina, ou o processo não subiu. Não
    se inventa um zero nem um falso: quem recebe ``None`` responde "não sei".

    ``bufsize=0`` não é detalhe: o medidor lê o descritor CRU com ``os.read``
    através de um seletor, e um leitor com buffer esconderia bytes já entregues
    atrás do próprio buffer — o seletor diria "nada a ler" com dado na mão.

    **``stdout=subprocess.PIPE`` é a TRAVA DE MORTE, e não é escolha de
    estilo.** Medido em 03/09 matando o pai com SIGKILL: com o cano o ``parec``
    morre junto (a ponta de leitura fecha, o próximo write toma ``SIGPIPE``, e
    em modo de pico há write a cada 40 ms); com ``stdout`` para ``/dev/null``
    ele SOBREVIVE órfão, segurando o microfone dela aberto — foi assim que um
    ``parec`` deste medidor ficou 39 minutos de pé em 03/09 às 00h36. A sessão
    não muda nada: os dois desenhos de ``/dev/null`` vazam, os dois de cano
    morrem. Quem mandar esta saída para outro lugar reabre o vazamento; há
    teste que morde.
    """
    if shutil.which("parec") is None:
        logger.debug("nivel_do_mic_sem_parec", fonte=fonte)
        return None
    try:
        proc = subprocess.Popen(  # argv fixo, sem shell
            argv_do_medidor(fonte, uniq),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=_ambiente_c(),
            bufsize=0,
            preexec_fn=_morrer_com_o_pai,  # noqa: PLW1509 - ver a nota abaixo
        )
    except (OSError, ValueError) as exc:
        logger.warning("nivel_do_mic_nao_abriu", fonte=fonte, err=str(exc))
        return None
    if proc.stdout is None:  # pragma: no cover - defensivo
        with contextlib.suppress(OSError):
            proc.kill()
        return None
    return _FluxoParec(proc=proc)


@dataclass
class _Canal:
    """Um controle sendo medido: o fluxo aberto, a régua e o que sobrou."""

    uniq: str
    fonte: str
    fluxo: Fluxo
    hist: Histerese
    resto: bytearray = field(default_factory=bytearray)
    ultimo_dado: float = 0.0


# --------------------------------------------------------------------------
# O MEDIDOR
# --------------------------------------------------------------------------


class NivelDoMicrofone:
    """Mede o pico de cada canal pedido e responde com histerese.

    Uso, do lado da PEÇA C (uma chamada por volta do laço)::

        medidor.seguir({uniq: fonte_ou_None, ...})   # quem TEM ouvinte
        captando = medidor.captando()                # {uniq: True|False|None}

    :meth:`seguir` é o degrau menor da sprint feito desenho: só o que entra
    nele é aberto, e o que sai é fechado no mesmo instante. Passe apenas os
    controles que a PEÇA A já disse ter ouvinte — a §1.1 diz que o estado 2 só
    existe dentro do estado 1, e assim o custo com ninguém ouvindo é zero.

    Um ``uniq`` cujo valor seja ``None`` (o controle do RÁDIO, que não publica
    canal) é aceito e respondido com ``None``. Isso é deliberado: deixa o
    chamador passar a tabela inteira de `escolher_fonte` sem filtrar, e o
    "não há o que medir" não vira um "medi e não há som".

    Todo o trabalho acontece numa thread só, com um seletor: quatro canais são
    quatro descritores no MESMO ``epoll``, não quatro threads. Quem preferir
    dirigir o relógio (os testes, ou um chamador que já tem laço próprio)
    constrói com ``automatico=False`` e chama :meth:`bombear`.
    """

    def __init__(
        self,
        *,
        abrir: Callable[[str, str], Fluxo | None] = abrir_fluxo,
        agora: Callable[[], float] = time.monotonic,
        limiar_entra: float = LIMIAR_ENTRA,
        limiar_sai: float = LIMIAR_SAI,
        segura_s: float = SEGURA_S,
        entra_s: float = ENTRA_S,
        mudez_s: float = MUDEZ_S,
        automatico: bool = True,
    ) -> None:
        self._abrir = abrir
        self._agora = agora
        self._limiar_entra = limiar_entra
        self._limiar_sai = limiar_sai
        self._segura_s = segura_s
        self._entra_s = entra_s
        self._mudez_s = mudez_s
        self._automatico = automatico
        self._lock = threading.RLock()
        self._desejado: dict[str, str | None] = {}
        self._canais: dict[str, _Canal] = {}
        self._proxima_tentativa: dict[str, float] = {}
        self._seletor = selectors.DefaultSelector()
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None

    # -- o que o chamador usa -------------------------------------------

    def seguir(self, alvos: Mapping[str, str | None]) -> None:
        """Passa a medir exatamente estes controles — nem mais, nem menos.

        Idempotente: o que já estava aberto na MESMA fonte continua aberto (e
        a régua dele não é zerada, senão a luz recomeçaria do escuro a cada
        volta do laço). O que saiu da lista é fechado agora.
        """
        with self._lock:
            self._desejado = dict(alvos)
        if self._automatico:
            self._garantir_thread()

    def captando(self) -> dict[str, bool | None]:
        """``{uniq: True|False|None}`` para tudo que :meth:`seguir` recebeu."""
        agora = self._agora()
        with self._lock:
            return {u: self._resposta(u, agora) for u in self._desejado}

    def captando_em(self, uniq: str) -> bool | None:
        """A resposta de UM controle. ``None`` também para quem nem é seguido."""
        agora = self._agora()
        with self._lock:
            if uniq not in self._desejado:
                return None
            return self._resposta(uniq, agora)

    def parar(self) -> None:
        """Fecha tudo. Idempotente, e não levanta."""
        self._parar.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=3.0)
        self._thread = None
        with self._lock:
            self._desejado = {}
            for uniq in list(self._canais):
                self._fechar(uniq)
        with contextlib.suppress(OSError):  # pragma: no cover - defensivo
            self._seletor.close()

    def __enter__(self) -> NivelDoMicrofone:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.parar()

    # -- o laço ----------------------------------------------------------

    def bombear(self, timeout_s: float = _ESPERA_DO_SELETOR_S) -> None:
        """Uma volta: reconcilia os fluxos e come o que chegou.

        Público de propósito. Um chamador que já tem laço (ou um teste que
        dirige o relógio) usa isto e dispensa a thread inteira.
        """
        self._reconciliar()
        eventos = self._seletor.select(timeout=timeout_s)
        agora = self._agora()
        for chave, _mascara in eventos:
            self._comer(str(chave.data), agora)

    def _rodar(self) -> None:  # pragma: no cover - exercitado só com thread
        while not self._parar.is_set():
            try:
                self.bombear()
            except Exception as exc:  # defensivo: a thread não pode morrer
                logger.warning("nivel_do_mic_volta_falhou", err=str(exc))
                time.sleep(_ESPERA_DO_SELETOR_S)

    def _garantir_thread(self) -> None:
        with self._lock:
            if self._thread is not None or self._parar.is_set():
                return
            self._thread = threading.Thread(
                target=self._rodar, name="nivel_do_microfone", daemon=True
            )
        self._thread.start()

    # -- as tripas -------------------------------------------------------

    def _resposta(self, uniq: str, agora: float) -> bool | None:
        """Chamado SEMPRE com o lock tomado."""
        canal = self._canais.get(uniq)
        if canal is None:
            return None
        if (agora - canal.ultimo_dado) >= self._mudez_s:
            return None
        return canal.hist.estado(agora)

    def _reconciliar(self) -> None:
        agora = self._agora()
        with self._lock:
            desejado = dict(self._desejado)
            for uniq, canal in list(self._canais.items()):
                if desejado.get(uniq) != canal.fonte or not canal.fluxo.vivo():
                    self._fechar(uniq)
                elif (agora - canal.ultimo_dado) >= self._mudez_s:
                    # Vivo e mudo: já respondemos `None` por ele, mas ele
                    # continua com o microfone DELA aberto e o nó em RUNNING.
                    # Soltar é obrigação — e a espera é longa para não fazer o
                    # nó piscar na leitura da PEÇA A.
                    self._fechar(uniq)
                    self._proxima_tentativa[uniq] = agora + _ESPERA_APOS_MUDEZ_S
                    logger.warning(
                        "nivel_do_mic_fluxo_emudeceu",
                        uniq=uniq,
                        mudo_ha_s=round(agora - canal.ultimo_dado, 2),
                    )
            faltam = [
                (u, f)
                for u, f in desejado.items()
                if f and u not in self._canais
            ]
        for uniq, fonte in faltam:
            if agora < self._proxima_tentativa.get(uniq, 0.0):
                continue
            self._abrir_canal(uniq, str(fonte), agora)

    def _abrir_canal(self, uniq: str, fonte: str, agora: float) -> None:
        fluxo = self._abrir(fonte, uniq)
        if fluxo is None:
            # Ausência é resposta, e não se tenta de novo em rajada: um
            # `parec` que não existe não passa a existir em 40 ms.
            self._proxima_tentativa[uniq] = agora + _ESPERA_APOS_MORTE_S
            return
        canal = _Canal(
            uniq=uniq,
            fonte=fonte,
            fluxo=fluxo,
            hist=Histerese(
                limiar_entra=self._limiar_entra,
                limiar_sai=self._limiar_sai,
                segura_s=self._segura_s,
                entra_s=self._entra_s,
            ),
            ultimo_dado=agora,
        )
        try:
            self._seletor.register(fluxo.fd, selectors.EVENT_READ, uniq)
        except (KeyError, ValueError, OSError) as exc:  # pragma: no cover
            logger.warning("nivel_do_mic_seletor_recusou", uniq=uniq, err=str(exc))
            fluxo.parar()
            self._proxima_tentativa[uniq] = agora + _ESPERA_APOS_MORTE_S
            return
        with self._lock:
            self._canais[uniq] = canal
        self._proxima_tentativa.pop(uniq, None)
        logger.info("nivel_do_mic_abriu", uniq=uniq, fonte=fonte)

    def _fechar(self, uniq: str) -> None:
        """Chamado SEMPRE com o lock tomado."""
        canal = self._canais.pop(uniq, None)
        if canal is None:
            return
        with contextlib.suppress(  # pragma: no cover - defensivo
            KeyError, ValueError, OSError
        ):
            self._seletor.unregister(canal.fluxo.fd)
        canal.fluxo.parar()
        logger.info("nivel_do_mic_fechou", uniq=uniq, fonte=canal.fonte)

    def _comer(self, uniq: str, agora: float) -> None:
        with self._lock:
            canal = self._canais.get(uniq)
        if canal is None:
            return
        try:
            dados = os.read(canal.fluxo.fd, _LOTE_BYTES)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            dados = b""
        if not dados:
            # Fim de arquivo: o `parec` morreu. Fechar e deixar a resposta
            # voltar a `None` — nunca a `False`, que seria afirmar silêncio.
            with self._lock:
                self._fechar(uniq)
            self._proxima_tentativa[uniq] = agora + _ESPERA_APOS_MORTE_S
            logger.info("nivel_do_mic_fluxo_morreu", uniq=uniq)
            return
        canal.resto += dados
        inteiras = len(canal.resto) // _TAM_AMOSTRA
        if not inteiras:
            return
        with self._lock:
            # CADA AMOSTRA GANHA O SEU INSTANTE, e isso não é preciosismo: a
            # régua tem um degrau de DURAÇÃO, e carimbar o lote inteiro com um
            # instante só faria a duração medir a cadência de quem LÊ, não a do
            # sinal. Um lote de quatro amostras chegado de uma vez pareceria
            # 0 s de som contínuo; a 25 Hz ele é 160 ms. As amostras deste lote
            # chegaram entre a leitura anterior e agora, espalhadas em passo
            # igual — que é como o servidor as emite.
            inicio = canal.ultimo_dado
            passo = (agora - inicio) / inteiras
            for i in range(inteiras):
                pico = struct.unpack_from("<f", canal.resto, i * _TAM_AMOSTRA)[0]
                canal.hist.aplicar(pico, inicio + passo * (i + 1))
            del canal.resto[: inteiras * _TAM_AMOSTRA]
            canal.ultimo_dado = agora


__all__ = [
    "APLICACAO_ID",
    "CHAVE_DO_PAPEL",
    "CHAVE_DO_PICO",
    "CHAVE_DO_UNIQ",
    "ENTRA_S",
    "LIMIAR_ENTRA",
    "LIMIAR_SAI",
    "MUDEZ_S",
    "NOME_DO_FLUXO",
    "NOME_DO_MEDIDOR",
    "PAPEL_DO_MEDIDOR",
    "SEGURA_S",
    "TAXA_HZ",
    "VALOR_DO_PICO",
    "Fluxo",
    "Histerese",
    "NivelDoMicrofone",
    "abrir_fluxo",
    "argv_do_medidor",
    "e_stream_do_medidor",
    "propriedades_do_medidor",
]
