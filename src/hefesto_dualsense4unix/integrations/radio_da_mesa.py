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

Falta a metade de baixo: **quantas fatias um relatório HID de 78 B consome não
está escrito em lugar nenhum desta árvore** — nem no protocolo, nem nos ensaios
(grep conferido em 22/08/2026 por ``625``, ``slot`` e "fatia de tempo" em
``src/``, ``scripts/``, ``docs/protocol/`` e ``docs/data/``). A decisão R1 do PO
fixou **um relatório = uma fatia**, que é a hipótese mais conservadora e a única
que a palavra "derivado da especificação" consegue defender sozinha. O número
real depende do tipo de pacote que o link negociou (2-DH1, 2-DH3), e o produto
não observa isso.

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

Também não é um mapa de bonds: quem amarra controle a adaptador aqui é o
``HID_PHYS`` do uevent do nó hidraw, que o kernel publica e que abre como uid
1000 — nada de ``/var/lib/bluetooth`` e nada de sudo.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

#: Fatias de tempo por segundo do Bluetooth Classic — 625 µs cada. É
#: ESPECIFICAÇÃO, não medição desta máquina; ver o cabeçalho.
SLOTS_POR_SEGUNDO = 1600

#: Quantas fatias um relatório consome. Decisão R1 do PO (22/08/2026): a
#: hipótese conservadora, porque a metade de baixo da conta não existe na
#: árvore. Mudar este número muda a tela inteira, e só com medição por trás.
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
#: CAI, porque o áudio divide a mesma fila (``dualsense_bt_audio.py:77``).
#: Mesma medição que :data:`CHAVE_NO_MAPA_DE_CANAIS` registra em
#: ``radio_ressalva``.
HZ_INPUT_COM_MIC = 170.5

#: Quadros de áudio por segundo com a ponte de pé (``dualsense_bt_audio.py:77``).
#: Mesma medição que :data:`CHAVE_NO_MAPA_DE_CANAIS` registra em
#: ``radio_ressalva``.
HZ_AUDIO_COM_MIC = 106.2

#: Z6-08 (24/08/2026) — o número medido ganha um dono só. As três constantes
#: acima e a célula ``radio_ressalva`` da linha 23 de
#: ``docs/data/mapa-controles.csv`` (``audio.microfone@dualsense``) eram a
#: MESMA medição escrita duas vezes, sem nada entre elas: trocar a constante
#: passava em 36 testes sem que a prosa do mapa se movesse (§0.1 do
#: SPRINT_ORDER, F9). Esta tupla é o que
#: ``scripts/validar-fala-de-tela.py`` lê POR AST (nunca importando este
#: módulo — ele puxa ``structlog`` por ``core.sysfs_leds``) para reprovar
#: quando a constante e a célula divergirem: cada item é
#: ``(nome_da_constante, valor, chave_do_mapa, coluna_do_mapa)``, e o
#: ``valor`` é a MESMA referência de nome acima — nunca um literal copiado —
#: para as duas nunca poderem divergir sem alguém precisar editar as duas
#: linhas.
NUMEROS_MEDIDOS_NO_MAPA: tuple[tuple[str, float, str, str], ...] = (
    ("HZ_INPUT_SEM_MIC", HZ_INPUT_SEM_MIC, "audio.microfone@dualsense", "radio_ressalva"),
    ("HZ_INPUT_COM_MIC", HZ_INPUT_COM_MIC, "audio.microfone@dualsense", "radio_ressalva"),
    ("HZ_AUDIO_COM_MIC", HZ_AUDIO_COM_MIC, "audio.microfone@dualsense", "radio_ressalva"),
)

#: Até aqui a mesa é "Folgada". Decisão R3 do PO.
CORTE_FOLGADA = 0.60

#: Daqui para cima a mesa é "Cheia"; entre os dois cortes, "Apertada". As três
#: palavras são só sobre OCUPAÇÃO — ver :data:`PALAVRAS_DE_CULPA`.
CORTE_APERTADA = 0.85

#: As três palavras, na ordem dos cortes. Duas cores só: a primeira é verde, as
#: outras duas são laranja (`@orange`). **Nunca vermelho** — rádio cheio é
#: reversível (basta tirar um controle do adaptador), e nesta casa o vermelho é
#: para o que destrói e não tem volta.
PALAVRA_FOLGADA = "Folgada"
PALAVRA_APERTADA = "Apertada"
PALAVRA_CHEIA = "Cheia"

#: O que o rótulo do medidor NÃO pode conter, em nenhuma das três palavras nem
#: em nada que a GUI componha a partir delas.
#:
#: Não é paranoia de redação: a desigualdade de quase o dobro entre dois
#: controles do mesmo adaptador (ver o cabeçalho) é ABERTA, e sobreviveu à troca
#: de unidades. Uma tela que ligue ocupação a qualidade estaria afirmando uma
#: causa que a bancada não sustenta — e ensinando a trocar de controle quando o
#: problema pode ser outro. O teste varre esta lista contra o texto que sai.
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

#: Chave do balde de "não sei a qual adaptador este controle pertence". É a
#: string vazia porque é exatamente o que :func:`adaptador_por_uniq` devolve
#: para ausência — um controle bt sem endereço legível NUNCA empresta o
#: adaptador do vizinho.
SEM_ADAPTADOR = ""

#: MAC bem-formado, minúsculo. É a MESMA regex de ``broker/hidraw_broker.py:123``,
#: recompilada aqui de propósito: lá ela é privada e mora no broker, e importar
#: um símbolo privado de outra camada é dívida pior que quatro linhas repetidas.
_MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")

_MARCA_UNIQ = "HID_UNIQ="
_MARCA_PHYS = "HID_PHYS="


@dataclass(frozen=True)
class Ocupacao:
    """Quanto do rádio de UM adaptador está comprometido.

    Os campos são fatias por segundo (não Hz, não porcentagem) porque é nessa
    unidade que a conta fecha contra o teto da especificação. As frações são
    derivadas e vêm CRUAS: passar de 1,0 é resultado legítimo, e é justamente o
    que a barra precisa saber dizer.
    """

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
    """A palavra da ocupação, pelos dois cortes da decisão R3.

    Fração é a do TOTAL (entrada mais áudio), e vem crua: acima de 1,0 continua
    "Cheia", que é o que a pessoa precisa ler.
    """
    if fracao <= CORTE_FOLGADA:
        return PALAVRA_FOLGADA
    if fracao <= CORTE_APERTADA:
        return PALAVRA_APERTADA
    return PALAVRA_CHEIA


def adaptador_por_uniq(
    uniqs: Iterable[str],
    *,
    raiz: str = "/sys/class/hidraw",
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
) -> dict[str, str]:
    """``{uniq: endereço do adaptador}`` — ``""`` para quem não está no rádio.

    Molde literal de ``integrations/usb_pai.py:161-201``, com uma troca só: lá
    o ``HID_UNIQ`` é a chave de busca e a resposta é o nó USB pai; aqui o
    ``HID_UNIQ`` segue sendo a chave e a resposta é o ``HID_PHYS``.

    Por que o ``HID_PHYS`` responde à pergunta "qual adaptador": o próprio
    broker decide por ele. ``broker/hidraw_broker.py:281`` recusa o nó cujo
    ``HID_PHYS`` não é MAC, com o comentário literal *"BT real tem HID_PHYS =
    MAC do adaptador"*, e o belt de ``:282-284`` só confirma quando o sysfs de
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
    """
    procurados = {_hex(u): u for u in uniqs if u and _hex(u)}
    saida: dict[str, str] = dict.fromkeys(procurados.values(), "")
    if not procurados:
        return saida
    try:
        nos = sorted(listar(raiz))
    except OSError:
        # Sysfs ilegível é "não sei", nunca um adaptador chutado. O sysfs de
        # Bluetooth é instável ao vivo — adaptador em down, rfkill, hci sem
        # `address` (`broker/hidraw_broker.py:166-172`).
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


def ocupacao_por_adaptador(
    controles: Iterable[Mapping[str, Any]],
    *,
    com_ponte_de_mic: Iterable[str] = (),
    raiz: str = "/sys/class/hidraw",
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
) -> dict[str, Ocupacao]:
    """``{endereço do adaptador: Ocupacao}`` a partir do estado do daemon.

    ``controles`` é a lista ``state["controllers"]`` como ela já chega
    (``core/backend_pydualsense.py:5413``): cada item traz ``transport``,
    ``connected`` e ``uniq`` — este último com 12 hex sem separador, **ou
    ``None``** quando a chave do backend era um caminho e não um MAC
    (``:4664-4679``, a guarda que impediu o pseudo-MAC ``deda4``).

    ``com_ponte_de_mic`` é o conjunto de ``uniq`` com a ponte agente por HID de
    pé. É só ela que custa rádio: por rádio o DualSense **não publica placa ALSA
    nenhuma** (medido 15/08/2026, ``integrations/usb_pai.py:38-42``), então
    ``controllers[].audio`` não diz nada sobre ocupação, e as duas primeiras
    chaves do ``bt_mic`` do ``daemon.state_full`` são do PROCESSO — com quatro
    controles e uma ponte elas dizem ``running: true`` e pintariam áudio nos
    quatro. Decisão R4.

    A FONTE, desde 22/08/2026 (``QUATRO-MICROFONES-01``): a terceira chave
    daquele bloco, ``bt_mic.uniqs``, que o daemon publica com os ``uniq`` cuja
    ponte SUBIU — não os que ela pediu. Uma ponte pedida que não subiu (libopus
    ausente, hidraw recusado) não ocupa fatia de rádio nenhuma, e contá-la aqui
    seria o produto respondendo pelo pedido em vez de pelo efeito.

    Três regras, e as três são de honestidade:

    * controle que não está em ``bt`` é DESCARTADO. No cabo o rádio não é
      tocado, e um vpad não tem rádio nenhum;
    * controle bt sem endereço legível vai para :data:`SEM_ADAPTADOR`, e a tela
      diz que não sabe — nunca empresta o adaptador do vizinho;
    * a fração passa de 1,0 quando passa. Saturar aqui esconderia justamente o
      caso que a barra existe para mostrar.
    """
    conectados = [
        controle
        for controle in controles
        if controle.get("transport") == "bt" and controle.get("connected", True)
    ]
    if not conectados:
        return {}

    uniqs = [_hex(str(c.get("uniq") or "")) for c in conectados]
    enderecos = adaptador_por_uniq(
        [u for u in uniqs if u], raiz=raiz, listar=listar, ler=ler
    )
    com_mic = {_hex(u) for u in com_ponte_de_mic if _hex(u)}

    acumulado: dict[str, list[float]] = {}
    for uniq in uniqs:
        endereco = enderecos.get(uniq, SEM_ADAPTADOR)
        alvo = acumulado.setdefault(endereco, [0.0, 0.0, 0.0, 0.0])
        if uniq and uniq in com_mic:
            alvo[0] += HZ_INPUT_COM_MIC * SLOTS_POR_RELATORIO
            alvo[1] += HZ_AUDIO_COM_MIC * SLOTS_POR_RELATORIO
            alvo[3] += 1
        else:
            alvo[0] += HZ_INPUT_SEM_MIC * SLOTS_POR_RELATORIO
        alvo[2] += 1

    return {
        endereco: Ocupacao(
            slots_input=entrada,
            slots_audio=audio,
            slots_teto=SLOTS_POR_SEGUNDO,
            controles=int(quantos),
            com_microfone=int(com_microfone),
        )
        for endereco, (entrada, audio, quantos, com_microfone) in acumulado.items()
    }


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
    """Só os dígitos hex minúsculos, "" quando não há nenhum.

    ``core.sysfs_leds.norm_mac`` é o normalizador público do projeto e é o MESMO
    que produz o ``uniq`` do estado (``core/backend_pydualsense.py:6346-6351``,
    o corpo de ``_key_to_uniq``; o endereço anterior, ``4674-4679``, apontava
    para o ``set_coop_outputs`` desde alguma mudança não datada),
    então os dois lados casam por construção. Aqui só a ausência muda de forma:
    ``None`` vira ``""``, que é a resposta que o resto deste módulo espera.
    """
    return norm_mac(valor) or ""


__all__ = [
    "CORTE_APERTADA",
    "CORTE_FOLGADA",
    "HZ_AUDIO_COM_MIC",
    "HZ_INPUT_COM_MIC",
    "HZ_INPUT_SEM_MIC",
    "PALAVRAS_DE_CULPA",
    "PALAVRA_APERTADA",
    "PALAVRA_CHEIA",
    "PALAVRA_FOLGADA",
    "SEM_ADAPTADOR",
    "SLOTS_POR_RELATORIO",
    "SLOTS_POR_SEGUNDO",
    "Ocupacao",
    "adaptador_por_uniq",
    "ocupacao_por_adaptador",
    "palavra_da_ocupacao",
]
