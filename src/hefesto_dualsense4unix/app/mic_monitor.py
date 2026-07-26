"""mic_monitor.py — nível e mute do microfone do DualSense na aba Status (S2).

O selo ATIVO/MUDO e o medidor de nível saem da MESMA fonte: a source de
captura que o PipeWire/PulseAudio publica para o controle. Um fato, um dono
— a alternativa (selo vindo do daemon, nível vindo daqui) já é a receita da
qual este projeto se arrependeu quando três lugares escreviam o perfil.

Três invariantes, cada uma paga com um incidente conhecido:

* **Nada de subprocess na thread GTK.** `pactl` e `parec` só rodam na thread
  supervisora e nas threads de captura. A interface lê um dicionário.
* **Nada de busy-loop.** A captura fica BLOQUEADA num `read()` do pipe do
  `parec` (o áudio é o relógio) e a supervisora dorme num `Event.wait`. Um
  laço apertado aqui repetiria os 104% de CPU da v3.8.1.
* **Ausência é resposta, e a resposta é DITA.** Sem `pactl`, sem `parec`, sem
  source do controle ou com dois controles no cabo que não dá para
  distinguir, a leitura é `None` — e a faixa de microfone da aba Status
  continua na tela dizendo QUAL desses casos é (MIC-FAIXA-01,
  :func:`diagnosticar_mic`). Nunca um medidor parado em zero fingindo
  silêncio, e nunca mais um painel que some: "sumiu" é indistinguível de
  "não existe", e foi assim que três camadas de mudo ficaram invisíveis.

Por que `LC_ALL=C` em tudo: a saída do `pactl` é TRADUZIDA (nesta máquina o
mute sai como "Mudo: não"). Parsear texto localizado é bug esperando idioma.
"""
from __future__ import annotations

import array
import contextlib
import json
import math
import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Any, ClassVar

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Marcadores no NOME da source que identificam um DualSense. O PipeWire monta
#: o nome a partir das strings USB do device ("Sony Interactive Entertainment
#: Wireless Controller"), então o casamento é por substring normalizada.
_MARCADORES_DUALSENSE: tuple[str, ...] = (
    "wireless_controller",
    "wireless controller",
    "dualsense",
)

#: Prefixo do nome que a NOSSA ponte de áudio por Bluetooth publica no
#: PipeWire (`integrations/dualsense_bt_audio.py`, `module-pipe-source`). O
#: nome completo é este prefixo + os SEIS últimos dígitos hex do MAC — ver
#: `_sufixo_hex_da_ponte` para o porquê de casar o nome LITERAL.
PREFIXO_PONTE_BT: str = "hefesto_dualsense_bt_"

#: Quantos dígitos hex do MAC a ponte põe no nome da source (`nome_curto`).
_HEX_DA_PONTE = 6


#: Formato da captura. 16 kHz mono s16le é mais que suficiente para um
#: medidor de nível (não é gravação) e mantém o bloco pequeno: 100 ms = 3200
#: bytes, um `read()` a cada 100 ms por controle.
_TAXA_HZ = 16000
_BYTES_POR_AMOSTRA = 2
_BLOCO_MS = 100
_BLOCO_BYTES = int(_TAXA_HZ * _BYTES_POR_AMOSTRA * _BLOCO_MS / 1000)

#: Piso da escala em dBFS. Abaixo disso o medidor mostra vazio — 60 dB de
#: faixa é o que um medidor de voz precisa mostrar sem virar ruído visual.
_PISO_DBFS = -60.0

_TIMEOUT_SUBPROCESS_S = 2.0


@dataclass(frozen=True)
class LeituraMic:
    """O que o card mostra: quanto entra no mic e se ele está mudo.

    ``nivel`` é 0.0-1.0 já em escala de dB (ver `nivel_para_fracao`), pronto
    para virar altura de barra. ``muted`` None = a source existe mas o estado
    de mute ainda não foi lido — o selo espera em vez de chutar "ATIVO".
    """

    nivel: float = 0.0
    muted: bool | None = None
    fonte: str = ""


# ---------------------------------------------------------------------------
# Funções puras (testáveis sem áudio nenhum)
# ---------------------------------------------------------------------------


def fontes_dualsense(saida_pactl: str) -> list[str]:
    """Nomes das sources de CAPTURA de DualSense em `pactl list sources short`.

    O formato é ``índice\\tnome\\tdriver\\tformato\\testado`` (não traduzido).
    Monitores de saída (``.monitor``) são descartados: são o áudio que SAI
    pelo alto-falante do controle, não o microfone dele — medir aquilo faria
    o "nível do mic" subir com a trilha do jogo.
    """
    out: list[str] = []
    for linha in saida_pactl.splitlines():
        partes = linha.split("\t")
        if len(partes) < 2:
            continue
        nome = partes[1].strip()
        alvo = nome.lower()
        if alvo.endswith(".monitor"):
            continue
        if any(marca in alvo for marca in _MARCADORES_DUALSENSE):
            out.append(nome)
    return out


def _e_fonte_de_cabo(fonte: str) -> bool:
    """True se a source vem de uma placa ALSA — logo, de um controle no CABO.

    Por rádio o DualSense não expõe placa de áudio nenhuma (medido: o SDP
    traz só HID e PnP, e o áudio dele anda em quadros Opus dentro dos reports
    HID). Então uma source `alsa_*` só pode pertencer a um controle no cabo —
    e é esse fato que deixa a regra do um para um funcionar com a mesa mista
    que é o caso normal desta casa: um no cabo e três por rádio.
    """
    return fonte.startswith("alsa_")


def escolher_fonte(
    fontes: list[str],
    uniq: str,
    uniqs_com_audio: list[str],
    transportes: dict[str, str] | None = None,
) -> str | None:
    """Source atribuível ao controle `uniq` — ou None quando não dá para saber.

    ``transportes`` (uniq -> "usb"/"bt") é opcional e só refina a regra 3:
    sem ele, a atribuição se comporta como sempre.

    Três regras, nesta ordem:

    1. **O nome carrega o MAC.** Sources de Bluetooth nascem como
       ``bluez_input.XX_XX_XX_XX_XX_XX``; ali o MAC está no nome e a
       atribuição é certa mesmo com vários controles. A busca por MAC é
       restrita a esses nomes DE PROPÓSITO: em nomes ALSA o "hex" que sobra
       ao filtrar letras é lixo de palavra ("Interactive" vira "eac"), e um
       casamento por acaso ali apontaria o mic do controle errado.
    2. **O nome é o da NOSSA ponte** (MIC-BT-01). A ponte de áudio por
       Bluetooth publica ``hefesto_dualsense_bt_<6 hex>``, e esses seis hex
       são os últimos do MAC do controle. Esta regra vem ANTES do um para um
       porque é justamente o cenário-alvo da casa — quatro controles por
       rádio, onde o um para um nunca dispara.
    3. **Um para um, DENTRO do transporte.** Uma única source compatível com
       o transporte deste controle e um único controle candidato naquele
       transporte: só pode ser ele. O recorte por transporte é o que salva a
       mesa mista (um no cabo, três por rádio): sem ele, a única source ALSA
       da mesa tinha quatro candidatos e a regra nunca disparava — a aba
       dizia "não dá para saber de quem é" para o controle que estava
       justamente no cabo, com o microfone funcionando.

    Fora disso devolve None. Dois DualSense no cabo publicam sources cujo
    nome não distingue um do outro (a string USB é a mesma), e exibir o mic
    do controle errado é pior que não exibir nenhum — é a regra do "não
    invente dado na interface".
    """
    alvo = _so_hex(uniq)
    if alvo:
        for fonte in fontes:
            if fonte.lower().startswith("bluez") and alvo in _so_hex(fonte):
                return fonte
    ponte = _fonte_da_ponte(fontes, uniq, uniqs_com_audio)
    if ponte is not None:
        return ponte
    candidatas, candidatos = _compativeis(uniq, uniqs_com_audio, fontes, transportes)
    if len(candidatas) == 1 and candidatos == [uniq]:
        return candidatas[0]
    return None


def _compativeis(
    uniq: str,
    uniqs_com_audio: list[str],
    fontes: list[str],
    transportes: dict[str, str] | None,
) -> tuple[list[str], list[str]]:
    """``(sources, controles)`` que podem casar com o transporte de `uniq`.

    Sem ``transportes`` (ou sem o transporte deste controle) devolve tudo: a
    regra volta a ser a de antes, e "não sei o transporte" nunca vira uma
    atribuição a mais.
    """
    via = (transportes or {}).get(uniq, "").lower()
    if via not in ("usb", "bt"):
        return (list(fontes), list(uniqs_com_audio))
    no_cabo = via == "usb"
    candidatas = [f for f in fontes if _e_fonte_de_cabo(f) is no_cabo]
    candidatos = [
        outro
        for outro in uniqs_com_audio
        if (transportes or {}).get(outro, "").lower() == via
    ]
    return (candidatas, candidatos)


def _sufixo_hex_da_ponte(fonte: str) -> str | None:
    """Os SEIS hex do nome da nossa ponte — None se o nome não é de ponte.

    Casamento pelo nome LITERAL, e nunca por ``_so_hex()`` da fonte inteira,
    por uma armadilha medida na MIC-BT-01: o próprio prefixo produz oito
    dígitos hex de lixo (``_so_hex("hefesto_dualsense_bt_") == "efedaeeb"``),
    então um "os 6 hex do controle aparecem no hex da fonte" casaria por acaso
    com um MAC terminado em ``efedae``. É a mesma armadilha do "Interactive"
    virando ``eac`` que a regra do bluez já evita.

    Sufixo que não é hex de seis dígitos devolve None de propósito: um
    controle sem ``HID_UNIQ`` faz a ponte publicar ``..._hidraw9``, e desse
    nome não sai atribuição nenhuma.
    """
    if not fonte.startswith(PREFIXO_PONTE_BT):
        return None
    sufixo = fonte[len(PREFIXO_PONTE_BT) :].lower()
    if len(sufixo) != _HEX_DA_PONTE:
        return None
    if any(ch not in "0123456789abcdef" for ch in sufixo):
        return None
    return sufixo


def _fonte_da_ponte(
    fontes: list[str], uniq: str, uniqs_com_audio: list[str]
) -> str | None:
    """Regra 2 de :func:`escolher_fonte` — a source publicada pela nossa ponte.

    A recusa honesta continua valendo quando DOIS controles terminam nos
    mesmos seis hex: a ambiguidade nasce na própria ponte, que publicaria o
    mesmo nome para os dois, e aqui a resposta é None em vez de escolher um.
    """
    cauda = _so_hex(uniq)[-_HEX_DA_PONTE:]
    if len(cauda) < _HEX_DA_PONTE:
        return None
    homonimos = sum(
        1 for outro in uniqs_com_audio if _so_hex(outro)[-_HEX_DA_PONTE:] == cauda
    )
    if homonimos > 1:
        return None
    for fonte in fontes:
        if _sufixo_hex_da_ponte(fonte) == cauda:
            return fonte
    return None


def _so_hex(valor: str) -> str:
    """Só os dígitos hex minúsculos — mesma normalização de MAC do projeto."""
    return "".join(ch for ch in valor.lower() if ch in "0123456789abcdef")


def _e_fonte_de_placa(entrada: dict[str, Any]) -> bool:
    """True se esta source vem de uma PLACA (ALSA) e portanto tem portas.

    A distinção existe por causa da nossa própria ponte de Bluetooth: um
    `module-pipe-source` não tem porta nenhuma por construção, e aplicar nele
    a regra de "sem porta ativa" acusaria de quebrada justamente a ponte que
    está funcionando.
    """
    props = entrada.get("properties")
    if isinstance(props, dict) and props.get("alsa.card") is not None:
        return True
    return str(entrada.get("name") or "").startswith("alsa_")


def portas_de_captura(saida_json: str) -> dict[str, bool]:
    """``{nome_da_source: tem porta de captura ATIVA}`` do `pactl -f json`.

    **Este é o teste honesto de "dá para captar", e ele custou uma premissa.**
    A MIC-USB-01 dizia que o perfil `input:iec958-stereo` é "S/PDIF, sem
    sinal", e que a cura era trocar para `input:analog-stereo`. Medido ao vivo
    em 26/07, com um DualSense no cabo, o contrário: no perfil analógico a
    source abre, desmutada e a 100%, e entrega 327.680 bytes com **pico 0** —
    e o `pactl -f json` mostra ali `active_port: null` com lista de portas
    VAZIA. No perfil `iec958`, que a sprint chamava de errado, a mesma
    gravação dá pico 4606 com envelope de voz. Nó sem porta de captura entrega
    zeros, seja qual for o nome do perfil.

    Por isso o que se olha aqui é a PORTA, e não o nome do perfil: o nome é
    uma convenção que já mentiu neste hardware; a porta é a existência do
    caminho de áudio.

    Saída ilegível, `pactl` sem `-f json` ou source virtual devolvem ausência
    (a chave não entra no dicionário) — e ausência aqui significa "não sei",
    nunca "sem porta".
    """
    try:
        dados = json.loads(saida_json)
    except (ValueError, TypeError):
        return {}
    if not isinstance(dados, list):
        return {}
    portas: dict[str, bool] = {}
    for entrada in dados:
        if not isinstance(entrada, dict):
            continue
        nome = entrada.get("name")
        if not isinstance(nome, str) or not nome:
            continue
        if not _e_fonte_de_placa(entrada):
            continue
        lista = entrada.get("ports")
        ativa = entrada.get("active_port")
        portas[nome] = bool(lista) and isinstance(ativa, str) and bool(ativa)
    return portas


def muted_de_saida(saida: str) -> bool | None:
    """Lê ``Mute: yes|no`` do `pactl get-source-mute`; None se ilegível.

    Só funciona com `LC_ALL=C` (ver o cabeçalho do módulo). Saída inesperada
    vira None — o selo prefere esperar a mentir.
    """
    texto = saida.strip().lower()
    if texto.endswith("yes"):
        return True
    if texto.endswith("no"):
        return False
    return None


def rms_de_pcm_s16le(bloco: bytes) -> float:
    """RMS normalizado (0.0-1.0) de um bloco PCM 16 bits little-endian.

    Bloco vazio/ímpar → 0.0: um `read()` truncado no encerramento do `parec`
    não pode virar pico no medidor.
    """
    if len(bloco) < 2:
        return 0.0
    amostras = array.array("h")
    amostras.frombytes(bloco[: len(bloco) - (len(bloco) % 2)])
    if not amostras:
        return 0.0
    if sys.byteorder == "big":
        # `parec` entrega s16LE; em máquina big-endian o `array` leria os
        # bytes trocados e o medidor viraria ruído.
        amostras.byteswap()
    soma = sum(float(a) * float(a) for a in amostras)
    return math.sqrt(soma / len(amostras)) / 32768.0


def nivel_para_fracao(rms: float) -> float:
    """RMS linear → 0.0-1.0 em escala de dB (o que o olho lê como "volume").

    Escala linear é inútil num medidor de voz: fala normal fica com 3% de
    barra e só um grito enche. Mapeia `_PISO_DBFS`..0 dBFS em 0..1.
    """
    if rms <= 0.0:
        return 0.0
    dbfs = 20.0 * math.log10(min(1.0, rms))
    if dbfs <= _PISO_DBFS:
        return 0.0
    return min(1.0, (dbfs - _PISO_DBFS) / (-_PISO_DBFS))


# ---------------------------------------------------------------------------
# Diagnóstico da faixa de microfone (MIC-FAIXA-01) — puro, sem toolkit
# ---------------------------------------------------------------------------
#
# A faixa do rodapé da aba Status é PERMANENTE: o espaço do microfone existe
# para todo controle da mesa, em qualquer transporte, medindo ou não. Quando
# não há medição ela DIZ POR QUÊ, porque "sumiu" é indistinguível de "não
# existe" — foi exatamente esse sumiço que fez a mantenedora abrir a queixa
# ("o medidor não aparece em cartão nenhum"), com o microfone mudo de verdade
# nas três camadas da MIC-USB-01 e a tela sem uma palavra sobre isso.
#
# Cada motivo abaixo tem uma cura DIFERENTE, e é essa a razão de eles serem
# estados separados em vez de um "sem microfone" só.

#: Há captura viva: o medidor desenha o que está entrando.
MOTIVO_MEDINDO = "medindo"
#: O monitor ainda não terminou a primeira descoberta de sources.
MOTIVO_AGUARDANDO = "aguardando"
#: Transporte por rádio e a ponte de áudio desligada (ela nasce opt-in).
MOTIVO_PONTE_DESLIGADA = "ponte_desligada"
#: O PipeWire não publica source de DualSense nenhuma.
MOTIVO_SEM_FONTE = "sem_fonte"
#: Há source, mas o nome não diz de qual controle ela é (`escolher_fonte`).
MOTIVO_AMBIGUA = "ambigua"
#: Source atribuída; o `parec` ainda não entregou o primeiro bloco.
MOTIVO_SEM_CAPTURA = "sem_captura"
#: Camada 1 — mudo no PipeWire, guardado por rota pelo WirePlumber.
MOTIVO_MUDO_ROTA = "mudo_rota"
#: Camada 2 — a source existe mas o perfil da placa não expõe porta de
#: captura. Ver :func:`portas_de_captura` para o porquê de o critério ser a
#: PORTA e não o nome do perfil (a premissa da MIC-USB-01 caiu na medição).
MOTIVO_SEM_PORTA = "sem_porta"
#: Camada 3 — o firmware do controle declara o microfone mudo.
MOTIVO_MUDO_FIRMWARE = "mudo_firmware"

#: O gesto que liga a ponte de áudio por Bluetooth (opt-in por medição
#: pendente: ela disputa o contador de sequência do report 0x32).
CURA_PONTE_BT = "Ligue a ponte no terminal: hefesto mic bt"
#: O gesto da camada 2. NÃO nomeia perfil de destino de propósito: o perfil
#: que funciona varia com o hardware, e nesta máquina o que a MIC-USB-01
#: mandava usar é justamente o que entrega silêncio.
CURA_PERFIL_DA_PLACA = (
    "Troque o perfil de entrada da placa (pactl set-card-profile) para um que "
    "o ALSA marque como disponível — o atual não expõe porta de captura."
)
#: O gesto da camada 1. Só o desmute, sem tocar no perfil: mexer no perfil
#: aqui é o que a medição de 26/07 desaconselha.
CURA_MUDO_ROTA = (
    "Desmute com: pactl set-source-mute {fonte} 0 — e para não voltar no "
    "próximo replug: scripts/fix_wireplumber_default_source.sh --unmute-routes"
)
#: Nem toda ausência tem cura conhecida. Aqui o gesto é MEDIR, não consertar.
CURA_SEM_FONTE = "Confira a placa do controle: pactl list cards | grep -i dualsense"


@dataclass(frozen=True)
class DiagnosticoMic:
    """O que a faixa de microfone mostra para UM controle.

    ``nivel`` None é o nulo honesto da casa: sem medição a faixa fica no
    lugar e VAZIA, nunca com barra parada fingindo silêncio. ``texto`` diz o
    que está acontecendo e ``cura`` diz o gesto — vazio quando o projeto não
    sabe curar aquilo (e aí dizer "faça X" seria inventar solução).
    """

    motivo: str
    texto: str
    cura: str = ""
    nivel: float | None = None
    muted: bool | None = None
    fonte: str = ""

    @property
    def medindo(self) -> bool:
        """True só quando há nível de verdade para desenhar."""
        return self.motivo == MOTIVO_MEDINDO


def audio_do_entry(entry: dict[str, Any]) -> tuple[bool | None, bool | None]:
    """``(mic_mudo, mic_mudo_desejado)`` do bloco ``audio`` de um controle.

    As duas chaves são OPCIONAIS no ``state_full`` (daemon antigo, dublê de
    teste, controle do qual nenhum report foi lido ainda) e as duas admitem
    None com significado próprio: ``mic_mudo`` None = não sabemos;
    ``mic_mudo_desejado`` None = a posse do registrador é do `hid-playstation`
    (quem manda no mudo é o botão físico), e não que ninguém tenha opinião.
    """
    audio = entry.get("audio")
    if not isinstance(audio, dict):
        return (None, None)
    mudo = audio.get("mic_mudo")
    desejado = audio.get("mic_mudo_desejado")
    return (
        mudo if isinstance(mudo, bool) else None,
        desejado if isinstance(desejado, bool) else None,
    )


def _cura_do_firmware(desejado: bool | None) -> str:
    """Qual gesto desmuta a camada 3 — depende de QUEM está segurando.

    É para isso que o `state_full` publica ``mic_mudo_desejado``: "aperte o
    botão do controle" e "mande desmutar pelo Hefesto" descrevem o mesmo
    ``mic_mudo: true``, e só uma das duas resolve cada caso.

    A pegadinha da posse, medida ao vivo em 26/07, entra no texto porque sem
    ela a cura vira um segundo defeito: enquanto o Hefesto segura o
    registrador do mudo, **o botão físico do controle para de responder** (ela
    apertou e o LED não apagou). `hefesto mic release` devolve a posse ao
    kernel — e é por isso que a frase o cita junto, e não depois.
    """
    if desejado is True:
        return (
            "O Hefesto está segurando o mudo: hefesto mic unmute — e "
            "hefesto mic release para o botão do controle voltar a valer."
        )
    return (
        "Aperte o botão de microfone do controle. Pela linha de comando, "
        "hefesto mic unmute — mas ele toma a posse do botão físico até "
        "hefesto mic release."
    )


def diagnosticar_mic(
    *,
    fontes: list[str] | None,
    uniq: str,
    uniqs_com_audio: list[str],
    transporte: str = "",
    leitura: LeituraMic | None = None,
    mic_mudo: bool | None = None,
    mic_mudo_desejado: bool | None = None,
    ponte_bt_ligada: bool = False,
    portas: dict[str, bool] | None = None,
    transportes: dict[str, str] | None = None,
) -> DiagnosticoMic:
    """Por que este controle está (ou não está) medindo — e o que cura.

    A ordem das perguntas é a das TRÊS CAMADAS da MIC-USB-01, de fora para
    dentro, porque cada cura revela a de baixo:

    1. O firmware do controle (camada 3) vem primeiro. Ele é um fato lido do
       report de input, vale em qualquer transporte, e enquanto ele estiver
       mudo o resto da cadeia entrega silêncio — apontar a placa de áudio
       ali seria mandar a usuária consertar a peça que está funcionando.
    2. Depois a existência e a atribuição da source: sem ela não há o que
       medir, e o motivo muda a cura (ponte desligada x nome ambíguo).
    3. Por último as camadas 1 e 2, que só se enxergam com a source na mão —
       e a 2 pela PORTA de captura, não pelo nome do perfil (ver
       :func:`portas_de_captura`).

    ``fontes`` None significa "o monitor ainda não descobriu" (aba recém
    aberta, monitor que nem nasceu) — e isso é diferente de "não há source":
    afirmar "não há microfone" antes da primeira descoberta seria um
    falso-negativo piscando na tela a cada troca de aba.
    """
    if mic_mudo is True:
        return DiagnosticoMic(
            motivo=MOTIVO_MUDO_FIRMWARE,
            texto="Mudo no firmware do controle (camada 3).",
            cura=_cura_do_firmware(mic_mudo_desejado),
            muted=True,
        )
    if fontes is None:
        return DiagnosticoMic(
            motivo=MOTIVO_AGUARDANDO,
            texto="Procurando o microfone deste controle...",
        )

    # A MESMA atribuição que o monitor usa para abrir a captura. Se a faixa
    # decidisse por conta própria, ela e o `parec` divergiriam — dois donos do
    # mesmo fato, que é a classe de bug que este projeto mais paga.
    fonte = escolher_fonte(fontes, uniq, uniqs_com_audio, transportes)
    if fonte is None:
        if transporte.lower() == "bt" and not ponte_bt_ligada:
            return DiagnosticoMic(
                motivo=MOTIVO_PONTE_DESLIGADA,
                texto=(
                    "Por rádio o DualSense não publica placa de áudio: o som "
                    "dele vem em quadros Opus dentro dos reports HID, e só "
                    "chega ao sistema com a ponte ligada."
                ),
                cura=CURA_PONTE_BT,
            )
        if not fontes:
            return DiagnosticoMic(
                motivo=MOTIVO_SEM_FONTE,
                texto="O PipeWire não publica microfone para este controle.",
                cura=CURA_SEM_FONTE,
            )
        return DiagnosticoMic(
            motivo=MOTIVO_AMBIGUA,
            texto=(
                "Há microfone publicado, mas o nome não diz de qual controle "
                "ele é — mostrar o mic do controle errado seria pior."
            ),
        )

    if portas is not None and portas.get(fonte) is False:
        return DiagnosticoMic(
            motivo=MOTIVO_SEM_PORTA,
            texto=(
                "A fonte existe, mas o perfil da placa não expõe porta de "
                "captura — nenhum áudio pode entrar por ela (camada 2)."
            ),
            cura=CURA_PERFIL_DA_PLACA,
            fonte=fonte,
        )
    if leitura is None:
        return DiagnosticoMic(
            motivo=MOTIVO_SEM_CAPTURA,
            texto="Microfone encontrado; abrindo a captura...",
            fonte=fonte,
        )
    if leitura.muted is True:
        return DiagnosticoMic(
            motivo=MOTIVO_MUDO_ROTA,
            texto=(
                "Mudo no PipeWire — o WirePlumber guarda esse mudo por rota e "
                "o restaura a cada conexão (camada 1)."
            ),
            cura=CURA_MUDO_ROTA.format(fonte=fonte),
            muted=True,
            fonte=fonte,
        )
    return DiagnosticoMic(
        motivo=MOTIVO_MEDINDO,
        texto="",
        nivel=leitura.nivel,
        muted=leitura.muted,
        fonte=fonte,
    )


# ---------------------------------------------------------------------------
# Monitor (threads)
# ---------------------------------------------------------------------------


class MicMonitor:
    """Captura o nível do mic dos controles enquanto a aba Status está visível.

    Uso (a mixin de status é a dona)::

        monitor.set_ativo(True)              # entrou na aba Status
        monitor.set_controles(("aabb...",))  # tick de 10 Hz, barato
        leitura = monitor.leitura("aabb...") # None = sem mic atribuível
        monitor.set_ativo(False)             # saiu da aba: mata tudo

    ``set_ativo(False)`` não é otimização: sem ele, um `parec` por controle
    ficaria capturando o microfone da usuária a sessão inteira com a janela
    minimizada.
    """

    #: Intervalo da supervisora. Descobrir sources é subprocess; 3 s é rápido
    #: o bastante para plugar um controle e ver o medidor aparecer.
    _SUPERVISAO_S: ClassVar[float] = 3.0
    #: Frequência de releitura do mute. O nível é contínuo; o mute muda por
    #: gesto humano — 1 Hz é imperceptível e evita um subprocess por bloco.
    _MUTE_S: ClassVar[float] = 1.0

    def __init__(
        self,
        *,
        runner: Any = None,
        capturador: Any = None,
        auto_supervisao: bool = True,
    ) -> None:
        """`runner` e `capturador` são injetáveis para teste (sem áudio real).

        `auto_supervisao=False` deixa a thread supervisora de fora e o teste
        chama `reconciliar()` na mão — do contrário a thread rodaria a mesma
        reconciliação em paralelo e o teste viraria uma corrida.
        """
        self._runner = runner or _rodar
        self._capturador = capturador or _abrir_captura
        self._auto_supervisao = auto_supervisao
        self._lock = threading.RLock()
        self._ativo = False
        self._controles: tuple[str, ...] = ()
        #: uniq -> transporte, para a regra 3 de `escolher_fonte`.
        self._transportes: dict[str, str] = {}
        self._leituras: dict[str, LeituraMic] = {}
        self._capturas: dict[str, _Captura] = {}
        # MIC-FAIXA-01: as sources da ÚLTIMA descoberta. None = nenhuma
        # descoberta aconteceu ainda, e a faixa precisa dessa distinção para
        # não afirmar "não há microfone" no instante em que a aba abre.
        self._fontes: list[str] | None = None
        # Porta de captura ativa por source (ver `portas_de_captura`). Chave
        # ausente = não sei; o diagnóstico não acusa nada nesse caso.
        self._portas: dict[str, bool] = {}
        self._acordar = threading.Event()
        self._parar = threading.Event()
        self._supervisora: threading.Thread | None = None

    # -- API da thread GTK (tudo barato: só dict/tuple sob lock) ----------

    def set_ativo(self, ativo: bool) -> None:
        """Liga/desliga a captura. Chamado pelo gancho de troca de aba."""
        with self._lock:
            if ativo == self._ativo:
                return
            self._ativo = ativo
        if ativo:
            self._garantir_supervisora()
        self._acordar.set()

    def set_controles(
        self, uniqs: tuple[str, ...], transportes: dict[str, str] | None = None
    ) -> None:
        """Identidades dos controles que PODEM ter mic (chamado a 10 Hz).

        ``transportes`` (uniq -> "usb"/"bt") entra na atribuição pela regra 3
        de :func:`escolher_fonte`. É opcional para o monitor seguir usável sem
        ele — mas a GUI o manda, porque é ele que resolve a mesa mista.
        """
        vias = dict(transportes or {})
        with self._lock:
            if uniqs == self._controles and vias == self._transportes:
                return
            self._controles = uniqs
            self._transportes = vias
        self._acordar.set()

    def leitura(self, uniq: str) -> LeituraMic | None:
        """Última leitura do mic deste controle; None = sem mic atribuível."""
        with self._lock:
            return self._leituras.get(uniq)

    def fontes(self) -> list[str] | None:
        """Sources da última descoberta; None = ainda não descobriu nenhuma vez.

        A faixa de microfone (MIC-FAIXA-01) precisa das sources CRUAS, e não
        só da leitura: é o que separa "não há source publicada" de "há source
        e não dá para saber de quem é" — dois estados com curas diferentes,
        que a ausência de `leitura()` funde num "sem microfone" mudo.
        """
        with self._lock:
            return None if self._fontes is None else list(self._fontes)

    def portas(self) -> dict[str, bool]:
        """``{source: tem porta de captura ativa}`` da última descoberta.

        Dicionário vazio (ou chave ausente) = não sei — e "não sei" nunca
        vira acusação na faixa.
        """
        with self._lock:
            return dict(self._portas)

    def stop(self) -> None:
        """Encerra tudo. Idempotente (fechamento da janela)."""
        self._parar.set()
        self._acordar.set()
        thread = self._supervisora
        self._supervisora = None
        if thread is not None:
            thread.join(timeout=2.0)
        self._derrubar_capturas(set())

    # -- Supervisora ------------------------------------------------------

    def _garantir_supervisora(self) -> None:
        if self._parar.is_set() or not self._auto_supervisao:
            return
        with self._lock:
            atual = self._supervisora
            if atual is not None and atual.is_alive():
                return
            self._supervisora = threading.Thread(
                target=self._loop_supervisao, name="hefesto-mic-monitor", daemon=True
            )
            self._supervisora.start()

    def _loop_supervisao(self) -> None:
        while not self._parar.is_set():
            try:
                self.reconciliar()
            except Exception as exc:  # nunca derruba a thread
                logger.debug("mic_monitor_reconciliacao_falhou", err=str(exc))
            self._acordar.wait(self._SUPERVISAO_S)
            self._acordar.clear()

    def reconciliar(self) -> None:
        """Casa as capturas vivas com aba visível, controles e sources.

        Público para o teste exercitar o ciclo sem depender de temporização.
        """
        with self._lock:
            ativo = self._ativo
            controles = self._controles
            transportes = dict(self._transportes)
        if not ativo or not controles:
            self._derrubar_capturas(set())
            with self._lock:
                self._leituras = {}
            return

        fontes = self._descobrir_fontes()
        alvos: dict[str, str] = {}
        for uniq in controles:
            fonte = escolher_fonte(fontes, uniq, list(controles), transportes)
            if fonte is not None:
                alvos[uniq] = fonte
        self._derrubar_capturas(set(alvos))
        with self._lock:
            self._leituras = {
                u: leitura for u, leitura in self._leituras.items() if u in alvos
            }
        for uniq, fonte in alvos.items():
            self._garantir_captura(uniq, fonte)

    def _descobrir_fontes(self) -> list[str]:
        saida = self._runner(["pactl", "list", "sources", "short"])
        fontes = fontes_dualsense(saida or "")
        # A porta de captura vem numa segunda chamada, em JSON, e é
        # ENRIQUECIMENTO: `pactl` sem `-f json` devolve "" e o dicionário sai
        # vazio, o que significa "não sei" e não muda nada do que a faixa
        # afirma. A descoberta por nome curto continua sendo a fonte da
        # verdade sobre QUAIS sources existem — ela é a que está testada e
        # funciona em qualquer versão.
        bruto = self._runner(["pactl", "-f", "json", "list", "sources"])
        portas = portas_de_captura(bruto or "")
        with self._lock:
            self._fontes = list(fontes)
            self._portas = portas
        return fontes

    def _derrubar_capturas(self, manter: set[str]) -> None:
        with self._lock:
            mortas = [u for u in self._capturas if u not in manter]
            capturas = [self._capturas.pop(u) for u in mortas]
        for captura in capturas:
            captura.parar()

    def _garantir_captura(self, uniq: str, fonte: str) -> None:
        with self._lock:
            atual = self._capturas.get(uniq)
            if atual is not None and atual.fonte == fonte and atual.viva():
                return
            if atual is not None:
                self._capturas.pop(uniq, None)
        if atual is not None:
            atual.parar()
        captura = _Captura(
            uniq=uniq,
            fonte=fonte,
            publicar=self._publicar,
            runner=self._runner,
            capturador=self._capturador,
            parar_global=self._parar,
            mute_intervalo_s=self._MUTE_S,
        )
        with self._lock:
            self._capturas[uniq] = captura
        captura.iniciar()

    def _publicar(self, uniq: str, leitura: LeituraMic) -> None:
        with self._lock:
            self._leituras[uniq] = leitura


class _Captura:
    """Uma captura `parec` + a releitura periódica do mute, numa thread só."""

    def __init__(
        self,
        *,
        uniq: str,
        fonte: str,
        publicar: Any,
        runner: Any,
        capturador: Any,
        parar_global: threading.Event,
        mute_intervalo_s: float,
    ) -> None:
        self.uniq = uniq
        self.fonte = fonte
        self._publicar = publicar
        self._runner = runner
        self._capturador = capturador
        self._parar_global = parar_global
        self._mute_intervalo_s = mute_intervalo_s
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None
        self._proc: Any = None

    def viva(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def iniciar(self) -> None:
        if self.viva():
            return
        self._thread = threading.Thread(
            target=self._loop, name=f"hefesto-mic-{self.uniq[:8]}", daemon=True
        )
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()
        proc = self._proc
        if proc is not None:
            with contextlib.suppress(Exception):
                proc.terminate()
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=2.0)

    def _loop(self) -> None:
        proc = None
        try:
            proc = self._capturador(self.fonte)
        except Exception as exc:
            logger.debug("mic_captura_nao_abriu", fonte=self.fonte, err=str(exc))
        if proc is None or proc.stdout is None:
            # Degradação silenciosa: sem `parec` (ou sem permissão) o card
            # simplesmente não mostra o módulo de microfone.
            return
        self._proc = proc
        muted: bool | None = None
        blocos_por_leitura_de_mute = max(
            1, int(self._mute_intervalo_s * 1000 / _BLOCO_MS)
        )
        contador = 0
        try:
            while not self._parar.is_set() and not self._parar_global.is_set():
                bloco = proc.stdout.read(_BLOCO_BYTES)
                if not bloco:
                    break  # `parec` morreu: a supervisora respawna no próximo ciclo
                if contador % blocos_por_leitura_de_mute == 0:
                    muted = self._ler_mute()
                contador += 1
                self._publicar(
                    self.uniq,
                    LeituraMic(
                        nivel=nivel_para_fracao(rms_de_pcm_s16le(bloco)),
                        muted=muted,
                        fonte=self.fonte,
                    ),
                )
        except Exception as exc:
            logger.debug("mic_captura_interrompida", fonte=self.fonte, err=str(exc))
        finally:
            self._proc = None
            with contextlib.suppress(Exception):
                proc.terminate()
            with contextlib.suppress(Exception):
                proc.wait(timeout=1.0)

    def _ler_mute(self) -> bool | None:
        saida = self._runner(["pactl", "get-source-mute", self.fonte])
        return muted_de_saida(saida or "")


def _ambiente_c() -> dict[str, str]:
    """Cópia do ambiente com locale neutro (a saída do pactl é traduzida)."""
    env = dict(os.environ)
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    return env


def _rodar(argv: list[str]) -> str:
    """Roda um comando curto e devolve o stdout ("" em qualquer falha).

    Nunca `shell=True` (invariante do projeto) e sempre com timeout: um
    `pactl` pendurado num PipeWire morto não pode segurar a supervisora.

    A checagem de disponibilidade da ferramenta mora AQUI, no runner, e não
    em quem o chama: assim um runner dublado no teste não depende do que
    está instalado na máquina que roda a suíte.
    """
    if shutil.which(argv[0]) is None:
        return ""
    try:
        proc = subprocess.run(
            argv,
            timeout=_TIMEOUT_SUBPROCESS_S,
            check=False,
            capture_output=True,
            text=True,
            env=_ambiente_c(),
        )
    except Exception as exc:
        logger.debug("mic_comando_falhou", argv=argv[0], err=str(exc))
        return ""
    return proc.stdout or ""


def _abrir_captura(fonte: str) -> Any:
    """Abre o `parec` da source e devolve o processo (None se indisponível)."""
    if shutil.which("parec") is None:
        return None
    # Sem `shell=True` (invariante do projeto): argv fixo, a source entra como
    # argumento e não como texto de comando.
    return subprocess.Popen(
        [
            "parec",
            f"--device={fonte}",
            "--format=s16le",
            f"--rate={_TAXA_HZ}",
            "--channels=1",
            f"--latency-msec={_BLOCO_MS}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=_ambiente_c(),
    )


__all__ = [
    "CURA_MUDO_ROTA",
    "CURA_PERFIL_DA_PLACA",
    "CURA_PONTE_BT",
    "CURA_SEM_FONTE",
    "MOTIVO_AGUARDANDO",
    "MOTIVO_AMBIGUA",
    "MOTIVO_MEDINDO",
    "MOTIVO_MUDO_FIRMWARE",
    "MOTIVO_MUDO_ROTA",
    "MOTIVO_PONTE_DESLIGADA",
    "MOTIVO_SEM_CAPTURA",
    "MOTIVO_SEM_FONTE",
    "MOTIVO_SEM_PORTA",
    "PREFIXO_PONTE_BT",
    "DiagnosticoMic",
    "LeituraMic",
    "MicMonitor",
    "audio_do_entry",
    "diagnosticar_mic",
    "escolher_fonte",
    "fontes_dualsense",
    "muted_de_saida",
    "nivel_para_fracao",
    "portas_de_captura",
    "rms_de_pcm_s16le",
]
