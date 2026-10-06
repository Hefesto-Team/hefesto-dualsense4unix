"""radio_da_mesa.py — quanto do rádio de cada adaptador Bluetooth já está ocupado.

O PROBLEMA QUE ESTE MÓDULO RESOLVE
-----------------------------------

A janela sabe dizer QUANTOS controles estão no rádio, e sabe dizer quais
adaptadores existem no barramento. O que ela nunca soube dizer é a única coisa
que a pessoa precisa saber antes de plugar o quinto controle no mesmo dongle:
**quanto do rádio daquele adaptador já foi comprometido.** Sem essa conta, o
sintoma de rádio cheio chega como "o controle está estranho" e a pessoa procura
defeito no controle.

A conta tem duas metades, e elas têm procedências DIFERENTES — misturá-las é o
erro que este cabeçalho existe para impedir.

**A primeira metade é ESPECIFICAÇÃO, não medição desta máquina.** O Bluetooth
Classic divide o tempo em fatias de 625 µs, o que dá **1.600 fatias por
segundo** para tudo que aquele rádio carrega. Nenhum número deste parágrafo foi
medido aqui, e é por isso que a tela carrega o selo ``derivado da
especificação``: ele não é enfeite, é a procedência.

A metade de baixo — quantas fatias um relatório de 78 B consome — **foi MEDIDA
em 23/09/2026** (``integrations/ar_do_adaptador.py``, ``HCIGETDEVINFO``, sem
root): 87 B por pacote ACL recebido, que é o ``0x31`` de 83 B no ar mais 4 do
cabeçalho HCI — cabe num 3-DH1, uma fatia, e o controle só fala na fatia
seguinte a um POLL do mestre. **Cada relatório de entrada custa DUAS fatias**
(:data:`FATIAS_POR_RELATORIO_DE_ENTRADA`). 752,8 pacotes/s vezes 4 fatias
passaria de 1.600, o que é impossível — é o que fecha o 2. O 1 da conta
aditiva abaixo é o lado otimista; ver «O AR, DESDE 23/09/2026».

**A segunda metade é MEDIÇÃO, e é do projeto.** O A/B de 25/07/2026, mesmo
controle, três janelas de 3 s
(``integrations/dualsense_bt_audio.py:76-78``)::

    mic DESLIGADO  : input 260.4 Hz   audio   0.0 Hz   total 260.4 Hz
    mic LIGADO     : input 170.5 Hz   audio 106.2 Hz   total 276.7 Hz
    desligado again: input 274.3 Hz   audio   0.0 Hz   total 274.6 Hz

A terceira linha é a que fecha o argumento: ligar o microfone não abre canal
novo, ele **ocupa lugar na mesma fila**, e a recuperação ao desligar é total —
o efeito é de banda, não estado preso no firmware
(``dualsense_bt_audio.py:86-88``).

O QUE ELE NÃO É — e esta é a fronteira que a tela não atravessa
----------------------------------------------------------------

**Este módulo fala de OCUPAÇÃO. Ele não fala de culpa, e não tem como falar.**

Dois DualSense no MESMO adaptador, na MESMA janela de 20,000 s, entregaram
381,54 Hz e 191,40 Hz — quase o dobro um do outro, com a mesa FOLGADA
(``docs/data/ensaios-brutos/2026-08-15-E2-taxa-dos-oito-nos.csv:6`` e ``:8``). À
noite do mesmo dia, com os braços TROCADOS, a desigualdade atravessou a troca e
apareceu em unidades diferentes: 279,1 contra 157,8 Hz. O envelope do dia inteiro
no rádio foi de **157,8 a 402,9 Hz** (``docs/data/ensaios.csv:104``). O motivo
está **ABERTO** — não é da unidade, não é do braço, e ninguém sabe o que é.

    NOTA DATADA — 23/08/2026: há CANDIDATO, e ele aponta para o INSTRUMENTO.
    A medição de 22/08 (QUATRO-MICROFONES-01) leu o mesmo par de controles com
    duas réguas ao mesmo tempo:

    * a régua do **laço de leitura** deu 282,1 / 348,5 Hz numa passagem e
      357,0 / 353,9 na seguinte — instável, e desigual;
    * a régua do **relógio do próprio aparelho** (carimbo de tempo do sensor,
      derivado dos dados e não assumido: 3,000 MHz nos quatro) deu
      **398,3 / 400,2 Hz nas DUAS passagens** — estável, e IGUAL.

    Ou seja: a desigualdade pode estar no leitor, não no rádio. Reforça a
    leitura o fato de ler os quatro nós em paralelo no mesmo processo Python
    subcontar (638 Hz contra 780 Hz no mesmo nó) — o laço é o gargalo.

    **NÃO FECHA a pergunta**, e por uma razão só: ninguém refez o ensaio de
    15/08 com a régua nova. O que fecha é repetir aquele ensaio medindo pelo
    relógio do aparelho. Até lá o envelope acima continua sendo o que a casa
    tem, e as duas consequências de projeto abaixo continuam valendo.

    A mesma medição relê o denominador: ~800 relatórios/s é orçamento do
    **ADAPTADOR**, repartido entre os controles que ele hospeda — não uma taxa
    por controle. O modelo aditivo de ``HZ_INPUT_SEM_MIC`` abaixo assume o
    contrário. Trocar as constantes é decisão de produto (R1/R3 do PO) e exige o
    A/B refeito com o microfone ligado; ver ``docs/protocol/driver-hid-playstation.md``,
    a nota de 23/08 na seção do rádio.

Duas consequências de projeto saem daí, e as duas estão no código:

1. o medidor usa o **nominal do A/B**, nunca uma medição ao vivo. Uma barra
   alimentada pelo envelope de 157,8 a 402,9 Hz oscilaria 2,5 vezes sem ninguém
   ter mexido em nada, e ensinaria a desconfiar dela;
2. o rótulo é **uma de três palavras sobre ocupação** e não aceita frase de
   causa. A tela pode dizer *"a mesa está cheia"*, que é aritmética de
   especificação. Não pode dizer *"por isso seu controle está ruim"*, porque a
   taxa varia por motivo desconhecido mesmo com a mesa folgada. A constante
   :data:`PALAVRAS_DE_CULPA` existe para que um teste varra esse limite.

NOTA DATADA — 03/10/2026: a frase do MOVIMENTO de um controle (não a da ocupação do
adaptador) passou a dizer a causa, porque deixou de ser estimada. O sinal do enlace (RSSI,
lido sem root) segue quem se afasta e só ele, e o Hz cai contra o que o próprio controle dava
naquele adaptador: :func:`diagnosticar_o_movimento` junta os dois números e diz «longe»,
«interferência» ou «sinal desconhecido». A ocupação continua sem culpa.

Também não é um mapa de bonds: quem amarra controle a adaptador aqui é o
``HID_PHYS`` do uevent do nó hidraw, que o kernel publica e que abre como uid
1000 — nada de ``/var/lib/bluetooth`` e nada de sudo.
"""

from __future__ import annotations

import os
import re
import threading
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.app.fala_do_mapa import Numero
from hefesto_dualsense4unix.core import o_dono_do_evento as _ode
from hefesto_dualsense4unix.core.physical_report_reader import MOTION_EMIT_MAX_HZ
from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.integrations.ar_do_adaptador import (
    NIVEL_ENGASGA,
    NIVEL_LISO,
    NIVEL_MEDIO,
)

#: Fatias de tempo por segundo do Bluetooth Classic — 625 µs cada. É
#: ESPECIFICAÇÃO, não medição desta máquina; ver o cabeçalho.
SLOTS_POR_SEGUNDO = 1600

#: Fatias por relatório NA VISTA ADITIVA VELHA (R1 do PO, 22/08). O medido é 2
#: e o 1 é o lado otimista; «O AR, DESDE 23/09/2026», no fim deste módulo, diz
#: por que ele fica (o mockup aprovado do arranjo o espelha) e quando sai.
SLOTS_POR_RELATORIO = 1

#: A chave da linha de ``docs/data/mapa-controles.csv`` de onde as três
#: constantes de Hz abaixo vieram — T5, CONFIGURAÇÕES-FECHA-01. A célula é a
#: coluna ``radio_ressalva``, e ``test_radio_da_mesa_bate_com_o_mapa.py`` reabre
#: o CSV e compara: remedir o A/B sem tocar aqui (ou vice-versa) reprova.
CHAVE_NO_MAPA_DE_CANAIS = "audio.microfone"

#: Relatórios de entrada por segundo, mic desligado. A/B de 2026-07-25,
#: ``integrations/dualsense_bt_audio.py:76``. Mesma medição que
#: :data:`CHAVE_NO_MAPA_DE_CANAIS` registra em ``radio_ressalva``.
HZ_INPUT_SEM_MIC = 260.4

#: Relatórios de entrada por segundo com a ponte de microfone de pé — o input
HZ_INPUT_COM_MIC = 170.5

HZ_AUDIO_COM_MIC = 106.2

#: MESMA medição escrita duas vezes, sem nada entre elas: trocar a constante
NUMEROS_MEDIDOS_NO_MAPA: tuple[Numero, ...] = (
    Numero(constante="HZ_INPUT_SEM_MIC", valor=HZ_INPUT_SEM_MIC,
           chave="audio.microfone@dualsense", coluna="radio_ressalva"),
    Numero(constante="HZ_INPUT_COM_MIC", valor=HZ_INPUT_COM_MIC,
           chave="audio.microfone@dualsense", coluna="radio_ressalva"),
    Numero(constante="HZ_AUDIO_COM_MIC", valor=HZ_AUDIO_COM_MIC,
           chave="audio.microfone@dualsense", coluna="radio_ressalva"),
)

CORTE_FOLGADA = 0.60

CORTE_APERTADA = 0.85

PALAVRA_FOLGADA = "Folgada"
PALAVRA_APERTADA = "Apertada"
PALAVRA_CHEIA = "Cheia"

PALAVRAS_DE_CULPA = frozenset(
    {
        "culpa",
        "culpado",
        "defeito",
        "estragado",
        "falha",
        "falhando",
        "lento",
        "piora",
        "piorando",
        "problema",
        "ruim",
        "travando",
    }
)

SEM_ADAPTADOR = ""

_MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")

_MARCA_UNIQ = "HID_UNIQ="
_MARCA_PHYS = "HID_PHYS="

RAIZ_DO_HIDRAW = "/sys/class/hidraw"

_MAPA_DO_HIDRAW: tuple[str, tuple[int, ...], dict[str, str]] | None = None
_MAPA_TRAVA = threading.Lock()


def _esquecer_o_mapa() -> None:
    """O dono desarmou: o mapa guardado não tem mais quem o invalide."""
    global _MAPA_DO_HIDRAW
    with _MAPA_TRAVA:
        _MAPA_DO_HIDRAW = None


_ode.ao_desarmar(_esquecer_o_mapa)


def _mapa_do_hidraw(
    raiz: str, listar: Callable[[str], list[str]]
) -> tuple[dict[str, str], bool]:
    """``({uniq em hex: HID_PHYS ou ""}, completo?)`` dos nós de ``raiz``."""
    mapa: dict[str, str] = {}
    completo = True
    for no in sorted(listar(raiz)):
        texto = _ler_texto(os.path.join(raiz, no, "device", "uevent"))
        if not texto:
            completo = False
            continue
        hex_uniq = _hex(_valor_do_uevent(texto, _MARCA_UNIQ))
        if not hex_uniq or mapa.get(hex_uniq):
            continue
        phys = _valor_do_uevent(texto, _MARCA_PHYS).lower()
        mapa[hex_uniq] = phys if _MAC_RE.match(phys) else ""
    return mapa, completo


@dataclass(frozen=True)
class Ocupacao:
    """Quanto do rádio de UM adaptador está comprometido."""

    slots_input: float = 0.0
    slots_audio: float = 0.0
    slots_teto: int = SLOTS_POR_SEGUNDO
    controles: int = 0
    com_microfone: int = 0

    @property
    def slots_total(self) -> float:
        return self.slots_input + self.slots_audio

    @property
    def fracao_input(self) -> float:
        return self.slots_input / self.slots_teto if self.slots_teto else 0.0

    @property
    def fracao_audio(self) -> float:
        return self.slots_audio / self.slots_teto if self.slots_teto else 0.0

    @property
    def fracao_total(self) -> float:
        return self.fracao_input + self.fracao_audio

    @property
    def rotulo(self) -> str:
        """Uma das três palavras — e só sobre ocupação."""
        return palavra_da_ocupacao(self.fracao_total)


def palavra_da_ocupacao(fracao: float) -> str:
    """A palavra da ocupação, pelos dois cortes da decisão R3."""
    if fracao <= CORTE_FOLGADA:
        return PALAVRA_FOLGADA
    if fracao <= CORTE_APERTADA:
        return PALAVRA_APERTADA
    return PALAVRA_CHEIA


def adaptador_por_uniq(
    uniqs: Iterable[str],
    *,
    raiz: str = RAIZ_DO_HIDRAW,
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
    dono: Any = None,
) -> dict[str, str]:
    """``{uniq: endereço do adaptador}`` — ``""`` para quem não está no rádio.

    Molde literal de ``integrations/usb_pai.py:157-197``, com uma troca só: lá
    o ``HID_UNIQ`` é a chave de busca e a resposta é o nó USB pai; aqui o
    ``HID_UNIQ`` segue sendo a chave e a resposta é o ``HID_PHYS``.

    Por que o ``HID_PHYS`` responde à pergunta "qual adaptador": o próprio
    broker decide por ele. ``broker/hidraw_broker.py:318`` recusa o nó cujo
    ``HID_PHYS`` não é MAC, com o comentário literal *"BT real tem HID_PHYS =
    MAC do adaptador"*, e o belt de ``:395-397`` só confirma quando o sysfs de
    Bluetooth está legível.

    **A regra de honestidade, e ela tem controle negativo medido nesta bancada
    em 22/08/2026:** controle no CABO traz ``HID_PHYS`` de barramento USB
    (``usb-0000:0c:00.3-1/input3``), não MAC. Ele devolve ``""``, porque
    controle no fio não ocupa fatia de rádio nenhuma. O mesmo vale para o nosso
    vpad, que anuncia ``hefesto-vpad``.

    A chave devolvida é o ``uniq`` COMO VEIO — quem chama procura pela string
    que já tem —, mas a comparação com o kernel é só pelos dígitos hex: o estado
    do daemon escreve 12 hex sem separador e o uevent escreve MAC com
    dois-pontos, e sem normalizar os dois lados nada casa.

    Uma varredura de ``/sys`` por chamada, sem subprocesso e sem abrir
    ``/dev``: nada aqui disputa o hidraw com o daemon.

    **Com o dono do evento armado** (O-REPOUSO-ESPERA-O-EVENTO-01, família 2),
    a varredura sai só quando a geração de nomes dos ``hidraw*`` de ``/dev``
    muda: o mapa inteiro dos nós fica guardado até lá, e cobre os quatro
    chamadores (o governador, a central do rádio, o plano e o ``state_full``).
    Vale só na raiz de produção e sem ``ler`` injetado; ``dono`` é costura de
    teste, e com ele injetado vale em qualquer raiz. O ``listar`` do governador
    (o que levanta em vez de devolver vazio) só roda quando o mapa perde. Sem o
    dono, a varredura de sempre, byte a byte.
    """
    global _MAPA_DO_HIDRAW
    procurados = {_hex(u): u for u in uniqs if u and _hex(u)}
    saida: dict[str, str] = dict.fromkeys(procurados.values(), "")
    if not procurados:
        return saida
    dono_efetivo = dono if dono is not None else _ode.dono_armado()
    ficha = (
        dono_efetivo.ficha((dono_efetivo.raiz_dos_nos, _ode.NOMES))
        if dono_efetivo is not None
        and ler is None
        and (dono is not None or raiz == RAIZ_DO_HIDRAW)
        else None
    )
    if ficha is not None:
        with _MAPA_TRAVA:
            guardado = _MAPA_DO_HIDRAW
        if guardado is not None and guardado[0] == raiz and guardado[1] == ficha:
            mapa = guardado[2]
        else:
            try:
                mapa, completo = _mapa_do_hidraw(raiz, listar)
            except OSError:
                return saida
            if completo:
                with _MAPA_TRAVA:
                    _MAPA_DO_HIDRAW = (raiz, ficha, mapa)
        for hex_procurado, como_veio in procurados.items():
            saida[como_veio] = mapa.get(hex_procurado, "")
        return saida
    try:
        nos = sorted(listar(raiz))
    except OSError:
        return saida
    leitor = ler if ler is not None else _ler_texto
    for no in nos:
        texto = leitor(os.path.join(raiz, no, "device", "uevent"))
        hex_uniq = _hex(_valor_do_uevent(texto, _MARCA_UNIQ))
        if not hex_uniq:
            continue
        original = procurados.get(hex_uniq)
        if original is None or saida[original]:
            continue
        phys = _valor_do_uevent(texto, _MARCA_PHYS).lower()
        saida[original] = phys if _MAC_RE.match(phys) else ""
    return saida


N_MAX_PONTES = 2

HZ_DA_PONTE = 93.75

FATIAS_DA_PONTE = 3

FATIAS_POR_RELATORIO_DE_ENTRADA = 2

MODOS_DA_PONTE = frozenset({"som", "haptica"})


# numeros com fontes mudando de cores do vermelho <!-- noqa-acento: citação literal -->
# distancia tá daquele conector.»* <!-- noqa-acento: citação literal -->

HZ_QUE_ENGASGA = 1000.0 / 8
HZ_DO_JOGO = MOTION_EMIT_MAX_HZ
SEGURA_O_NIVEL_S = 3.0


def nivel_do_movimento(hz: object) -> str:
    """O nível do Hz de movimento de um controle: ``liso`` a partir de"""
    if isinstance(hz, bool) or not isinstance(hz, int | float) or hz != hz:
        return ""
    if hz >= HZ_DO_JOGO:
        return NIVEL_LISO
    if hz >= HZ_QUE_ENGASGA:
        return NIVEL_MEDIO
    return NIVEL_ENGASGA


#: O sinal (RSSI do enlace, dBm) que o rádio mede de cada controle. Os dois números são da
#: bancada de 03/10/2026 (dados em `bancada-0310/x-sinal.txt`, um adaptador, a casa do usuário):
#: abaixo
#: de ~-48 o controle ainda funciona e já atrasa; abaixo de ~-52 perde aperto. São o ponto de
#: partida, e a sprint mede de novo noutro adaptador antes de fixá-los.
SINAL_QUE_ATRASA_DBM = -48
SINAL_QUE_PERDE_APERTO_DBM = -52

#: O Hz de um controle é relativo ao que ELE dava naquele adaptador com aquela gente dividindo
#: (a referência abaixo): 250 Hz é normal para dois no mesmo adaptador e é queda para um sozinho
#: que dava 650. Acima de `FRACAO_QUE_AINDA_E_NORMAL` da referência é liso; abaixo de
#: `FRACAO_QUE_ENGASGA`, engasga.
FRACAO_QUE_AINDA_E_NORMAL = 0.6
FRACAO_QUE_ENGASGA = 0.3
MEIA_VIDA_DA_REFERENCIA_S = 120.0

CAUSA_LONGE = "longe"
CAUSA_INTERFERENCIA = "interferencia"
CAUSA_ADAPTADOR_CHEIO = "adaptador_cheio"
CAUSA_SEM_SINAL = "sem_sinal"

_ORDEM_DO_NIVEL = {"": 0, NIVEL_LISO: 1, NIVEL_MEDIO: 2, NIVEL_ENGASGA: 3}


@dataclass(frozen=True)
class Diagnostico:
    """O nível (a cor) e a causa (a frase) do movimento de um controle."""

    nivel: str
    causa: str = ""


def atualizar_a_referencia(
    anterior: tuple[int, float, float] | None, dividem: int, hz: object, agora: float
) -> tuple[int, float, float]:
    """`(dividem, pico, instante)`: o maior Hz que ESTE controle deu com esta gente dividindo.

    O pico recomeça quando muda quem divide o adaptador, e esquece devagar (meia-vida de
    :data:`MEIA_VIDA_DA_REFERENCIA_S`) para a referência acompanhar um rádio que mudou de vez.
    """
    valor = float(hz) if isinstance(hz, int | float) and not isinstance(hz, bool) else 0.0
    if anterior is None or anterior[0] != dividem:
        return dividem, valor, agora
    _, pico, quando = anterior
    pico *= 0.5 ** (max(0.0, agora - quando) / MEIA_VIDA_DA_REFERENCIA_S)
    return dividem, max(pico, valor), agora


def diagnosticar_o_movimento(
    hz: object,
    *,
    sinal_dbm: object = None,
    referencia_hz: float | None = None,
    via_radio: bool = True,
    adaptador_cheio: bool = False,
) -> Diagnostico:
    """A cor e a frase, dos dois números JUNTOS: o Hz que chega e o sinal do enlace.

    * Hz caindo e sinal fraco: ``longe``. Hz caindo e sinal bom: ``interferencia`` (ou
      ``adaptador_cheio``, quando a conta de quem divide diz). Hz normal e sinal bom: liso.
    * O Hz cai contra a REFERÊNCIA do controle naquele adaptador, não contra um número fixo;
      sem referência, vale o absoluto (:func:`nivel_do_movimento`).
    * Pelo rádio sem o sinal, a linha não é verde: ``sem_sinal`` e cor neutra.
    """
    absoluto = nivel_do_movimento(hz)
    if not absoluto:
        return Diagnostico("")
    nivel = absoluto
    if referencia_hz is not None and referencia_hz > 0:
        razao = float(hz) / referencia_hz  # type: ignore[arg-type]
        relativo = (NIVEL_LISO if razao >= FRACAO_QUE_AINDA_E_NORMAL
                    else NIVEL_MEDIO if razao >= FRACAO_QUE_ENGASGA else NIVEL_ENGASGA)
        piso = NIVEL_ENGASGA if absoluto == NIVEL_ENGASGA else NIVEL_LISO
        nivel = max(piso, relativo, key=_ORDEM_DO_NIVEL.__getitem__)
    caindo = nivel != NIVEL_LISO
    if not via_radio:
        return Diagnostico(nivel)
    if isinstance(sinal_dbm, bool) or not isinstance(sinal_dbm, int | float):
        return Diagnostico(nivel if caindo else "", CAUSA_SEM_SINAL)
    if not caindo:
        return Diagnostico(nivel)
    if sinal_dbm <= SINAL_QUE_ATRASA_DBM:
        return Diagnostico(nivel, CAUSA_LONGE)
    return Diagnostico(nivel, CAUSA_ADAPTADOR_CHEIO if adaptador_cheio else CAUSA_INTERFERENCIA)


def sinais_dos_enlaces(
    ar: Mapping[str, Any], *, ler: Callable[[int, int], int | None] | None = None
) -> dict[str, int | None]:
    """`{uniq (12 hex): RSSI | None}` de cada enlace ACL de cada adaptador, lido SEM root.

    ``ar`` é o que o medidor de ar entrega (:class:`ArDoAdaptador`, com as conexões e o
    handle de cada uma). Quem pergunta ao rádio é o dono do HCI cru (``ler_rssi``).
    """
    from hefesto_dualsense4unix.integrations import ar_do_adaptador as _ar

    leitor = ler if ler is not None else _ar.ler_rssi
    saida: dict[str, int | None] = {}
    for leitura in ar.values():
        for conexao in leitura.conexoes or ():
            if conexao.tipo == _ar.TIPO_ACL:
                saida[_hex(conexao.endereco)] = leitor(leitura.hci, conexao.handle)
    return saida


def palavra_das_pontes(pontes: int, n_max: int = N_MAX_PONTES) -> str:
    """As três palavras de sempre, agora lendo PONTES contra ``n_max``."""
    if pontes < n_max:
        return PALAVRA_FOLGADA
    if pontes == n_max:
        return PALAVRA_APERTADA
    return PALAVRA_CHEIA


@dataclass(frozen=True)
class ControleNoAr:
    """Um controle no rádio, com os Hz MEDIDOS. ``None`` = não sei."""

    uniq: str
    hz_movimento: float | None = None
    hz_voz: float | None = None
    ponte: str | None = None


@dataclass(frozen=True)
class OrcamentoDoAdaptador:
    """O ar de UM adaptador: quem está nele, quantas pontes, e o que se mediu."""

    adaptador: str
    controles: tuple[ControleNoAr, ...] = ()
    n_max: int = N_MAX_PONTES
    entrada_por_s: float | None = None
    saida_por_s: float | None = None
    canais_evitados: tuple[int, ...] | None = None
    motivo_do_ar: str = ""
    #: ``{aparelho (12 hex): {le, canais_evitados, qualidade_do_enlace,
    #: rssi}}`` de TODO enlace lido do
    #: adaptador, o aparelho que for (celular, relógio, fone, controle): a faixa de cada
    #: linha da seção «Dispositivos Conectados». ``None`` em campo = não sei.
    enlaces: Mapping[str, Mapping[str, Any]] | None = None

    @property
    def pontes(self) -> tuple[tuple[str, str], ...]:
        """``(uniq, modo)`` de cada controle com ponte de pé neste adaptador."""
        return tuple(
            (c.uniq, c.ponte) for c in self.controles if c.ponte in MODOS_DA_PONTE
        )

    @property
    def rotulo(self) -> str:
        return palavra_das_pontes(len(self.pontes), self.n_max)

    def publicar(self) -> dict[str, Any]:
        """O dicionário que viaja no ``state_full`` — só tipos de JSON."""
        return {
            "controles": [
                {
                    "uniq": c.uniq,
                    "hz_movimento": c.hz_movimento,
                    "hz_voz": c.hz_voz,
                    "ponte": c.ponte,
                }
                for c in self.controles
            ],
            "pontes": [{"uniq": u, "modo": m} for u, m in self.pontes],
            "n_max": self.n_max,
            "rotulo": self.rotulo,
            "entrada_por_s": self.entrada_por_s,
            "saida_por_s": self.saida_por_s,
            "canais_evitados": (
                list(self.canais_evitados) if self.canais_evitados is not None else None
            ),
            "motivo_do_ar": self.motivo_do_ar,
            "enlaces": {k: dict(v) for k, v in (self.enlaces or {}).items()},
        }


def _numero_ou_none(valor: Any) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    return float(valor)


def orcamento_por_adaptador(
    controles: Iterable[Mapping[str, Any]],
    *,
    ar: Mapping[str, Any] | None = None,
    canais_evitados: Mapping[str, tuple[int, ...] | None] | None = None,
    enlaces: Mapping[str, Mapping[str, Any]] | None = None,
    sinais: Mapping[str, int | None] | None = None,
    n_max: int = N_MAX_PONTES,
    raiz: str = "/sys/class/hidraw",
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
) -> dict[str, OrcamentoDoAdaptador]:
    """``{endereço do adaptador: OrcamentoDoAdaptador}`` — o P3 da R10."""
    no_radio = [
        c for c in controles
        if c.get("transport") == "bt" and c.get("connected", True)
    ]
    sem_endereco = [
        _hex(str(c.get("uniq") or ""))
        for c in no_radio
        if not _MAC_RE.match(str(c.get("adaptador") or "").lower())
    ]
    resolvidos = adaptador_por_uniq(
        [u for u in sem_endereco if u], raiz=raiz, listar=listar, ler=ler
    )
    por_adaptador: dict[str, list[ControleNoAr]] = {}
    for c in no_radio:
        uniq = _hex(str(c.get("uniq") or ""))
        publicado = str(c.get("adaptador") or "").lower()
        endereco = publicado if _MAC_RE.match(publicado) else resolvidos.get(uniq, "")
        ponte = c.get("ponte_do_radio")
        por_adaptador.setdefault(endereco if uniq else SEM_ADAPTADOR, []).append(
            ControleNoAr(
                uniq=uniq,
                hz_movimento=_numero_ou_none(c.get("hz_movimento")),
                hz_voz=_numero_ou_none(c.get("hz_voz")),
                ponte=ponte if ponte in MODOS_DA_PONTE else None,
            )
        )
    medidos = dict(ar or {})
    evitados = dict(canais_evitados or {})
    lidos = dict(enlaces or {})
    sinais_lidos = dict(sinais or {})
    enderecos = (set(por_adaptador) | {e for e in medidos if e} | {e for e in evitados if e}
                 | {e for e in lidos if e})
    saida: dict[str, OrcamentoDoAdaptador] = {}
    for endereco in sorted(enderecos):
        leitura = medidos.get(endereco)
        saida[endereco] = OrcamentoDoAdaptador(
            adaptador=endereco,
            controles=tuple(por_adaptador.get(endereco, ())),
            n_max=n_max,
            entrada_por_s=_numero_ou_none(getattr(leitura, "entrada_por_s", None)),
            saida_por_s=_numero_ou_none(getattr(leitura, "saida_por_s", None)),
            canais_evitados=evitados.get(endereco),
            enlaces=_enlaces_publicaveis(lidos.get(endereco), sinais_lidos),
            motivo_do_ar=(
                str(getattr(leitura, "motivo", "") or "")
                if leitura is not None
                else ("" if endereco == SEM_ADAPTADOR else "o medidor não leu este adaptador")
            ),
        )
    return saida


def _enlaces_publicaveis(
    lidos: Mapping[str, Any] | None, sinais: Mapping[str, int | None]
) -> dict[str, dict[str, Any]]:
    """Cada enlace lido do adaptador, só com tipos de JSON, e com o RSSI que o sinal mediu."""
    saida: dict[str, dict[str, Any]] = {}
    for aparelho, lido in (lidos or {}).items():
        evitados = getattr(lido, "canais_evitados", None)
        ligacao = getattr(lido, "qualidade_do_enlace", None)
        rssi = sinais.get(_hex(aparelho))
        saida[_hex(aparelho)] = {
            "le": bool(getattr(lido, "le", False)),
            "canais_evitados": list(evitados) if evitados is not None else None,
            "qualidade_do_enlace": ligacao if isinstance(ligacao, int) else None,
            "rssi": rssi if isinstance(rssi, int) and not isinstance(rssi, bool) else None,
        }
    return saida


def _valor_do_uevent(texto: str, marca: str) -> str:
    """O valor de uma chave do uevent — "" quando o nó não declara aquela chave."""
    for linha in texto.splitlines():
        if linha.startswith(marca):
            return linha[len(marca) :].strip()
    return ""


def _ler_texto(caminho: str) -> str:
    """Lê um arquivo de ``/sys``; "" em qualquer erro — sysfs some sob a mão."""
    try:
        with open(caminho, encoding="utf-8", errors="replace") as arquivo:
            return arquivo.read()
    except OSError:
        return ""


def _hex(valor: str) -> str:
    """Só os dígitos hex minúsculos, "" quando não há nenhum."""
    return norm_mac(valor) or ""


__all__ = [
    "CAUSA_ADAPTADOR_CHEIO",
    "CAUSA_INTERFERENCIA",
    "CAUSA_LONGE",
    "CAUSA_SEM_SINAL",
    "CORTE_APERTADA",
    "CORTE_FOLGADA",
    "FATIAS_DA_PONTE",
    "FATIAS_POR_RELATORIO_DE_ENTRADA",
    "FRACAO_QUE_AINDA_E_NORMAL",
    "FRACAO_QUE_ENGASGA",
    "HZ_AUDIO_COM_MIC",
    "HZ_DA_PONTE",
    "HZ_DO_JOGO",
    "HZ_INPUT_COM_MIC",
    "HZ_INPUT_SEM_MIC",
    "HZ_QUE_ENGASGA",
    "MODOS_DA_PONTE",
    "NIVEL_ENGASGA",
    "NIVEL_LISO",
    "NIVEL_MEDIO",
    "N_MAX_PONTES",
    "PALAVRAS_DE_CULPA",
    "PALAVRA_APERTADA",
    "PALAVRA_CHEIA",
    "PALAVRA_FOLGADA",
    "SEGURA_O_NIVEL_S",
    "SEM_ADAPTADOR",
    "SINAL_QUE_ATRASA_DBM",
    "SINAL_QUE_PERDE_APERTO_DBM",
    "SLOTS_POR_RELATORIO",
    "SLOTS_POR_SEGUNDO",
    "ControleNoAr",
    "Diagnostico",
    "Ocupacao",
    "OrcamentoDoAdaptador",
    "adaptador_por_uniq",
    "atualizar_a_referencia",
    "diagnosticar_o_movimento",
    "nivel_do_movimento",
    "orcamento_por_adaptador",
    "palavra_da_ocupacao",
    "palavra_das_pontes",
    "sinais_dos_enlaces",
]
