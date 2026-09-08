#!/usr/bin/env python3
"""a_captura_armada_do_som_no_radio.py — o instrumento que espera o som dela voltar.

A PERGUNTA QUE ELE EXISTE PARA RESPONDER, E ELA ESTÁ ABERTA HÁ VINTE DIAS
--------------------------------------------------------------------------
Em 16/08/2026, 00h10, ela ouviu **~6 segundos** de um pulsado saindo de um
DualSense que estava no RÁDIO, e reconheceu o timbre sem hesitar: *"era esse
som, esse mesmo som, o exato som"* — o pulsado de 1700 Hz a 6 Hz que ela tinha
ouvido minutos antes pelo cabo.

QUATRO réplicas negativas depois, o ensaio ``som-no-radio-observado-nao-replicado``
foi gravado no caderno com o resultado **inconclusivo**, e a nota dele diz, com
todas as letras, o que faltou capturar:

    ``btmon`` durante o evento, e o report que sai no fio para o ``hidraw8``
    naquele instante.

**Não se conclui que ela ouviu errado; conclui-se que não sabemos.** Este
instrumento é a única forma de sair do "não sabemos": ele não tenta REPRODUZIR
o evento — quatro tentativas já falharam nisso —, ele fica **ARMADO** para
quando ele acontecer de novo.

O DESENHO, E ELE INVERTE A PERGUNTA
------------------------------------
Um ensaio normal PROVOCA e mede. Este não pode: ninguém sabe o que provocou o
evento. Então ele grava tudo o tempo todo e deixa **ela** dizer quando:

    ela ouve  ->  ela aperta o botão de MUDO do plástico  ->  o instrumento
    carimba o instante e recorta uma janela de ±N segundos das DUAS metades.

**POR QUE O BOTÃO DE MUDO, e a escolha é sobre o risco, não sobre elegância.**
Ela tem UMA tela e quatro aparelhos na mesa; o marcador tem de ser algo que ela
alcance sem tirar os olhos da bancada e que **não mexa na máquina dela**:

* **o touchpad** seria o marcador óbvio (grande, fácil de acertar no escuro) e
  está DESCARTADO: clicar nele é um clique de mouse na tela dela, e um clique
  cego já desfez configuração dela nesta casa;
* **o botão PS** dispara ``ps_button_action_steam`` — o daemon tentaria abrir a
  Steam a cada marca;
* **o mudo do microfone** muda um bit do firmware, é reversível apertando de
  novo, não move cursor, não abre nada — e **já é marcador provado nesta casa**:
  o ensaio ``mic-radio-negativo-do-mudo-0907`` (07/09/2026) foi medido com ela
  apertando exatamente este botão.

O que se lê é a transição do bit ``STATUS_MIC_MUDO`` no report de entrada, pelo
mesmo extrator do produto (``core/physical_report_reader.extract_jack_status``),
que já traz a disciplina de CRC e a recusa do report de ÁUDIO — o bit ``0x02``
do byte 1, que em 16/08 fez os botões MIC e PS ficarem presos porque um parser
sem essa recusa lia Opus como estado de botão.

AS DUAS METADES, E POR QUE PRECISA DAS DUAS
--------------------------------------------
=========================  =================================================
metade                     o que ela decide
=========================  =================================================
o FIO (``btmon``)          se saiu ALGUMA COISA nossa para aquele controle
                           no instante. Se não saiu nada, o som — se houve —
                           não veio de report nosso, e isso é um fato novo.
o HIDRAW (entrada)         o que o aparelho estava dizendo: bit de áudio,
                           estado do jack, mudo, cadência dos reports.
=========================  =================================================

O ``hidraw`` **não serve** para a primeira metade, e é preciso dizer por quê
antes que alguém tente: um ``read()`` em ``/dev/hidrawN`` devolve os relatórios
de ENTRADA. Os de SAÍDA que o kernel manda não voltam por ali. O ``btmon`` lê o
``HCI_CHANNEL_MONITOR``, que é cópia de tudo que passa entre o host e o
controlador — o último ponto antes do ar.

O QUE ELE ESCREVE NO APARELHO: **NADA**
----------------------------------------
Nem um byte. Ele abre o hidraw **em leitura**, e o ``btmon`` é passivo. Não
reinicia o daemon, não toca no som dela, não abre janela. As únicas escritas
que a captura pode ver são as do PRODUTO, em regime.

O PRIVILÉGIO, E A DEGRADAÇÃO HONESTA
-------------------------------------
O ``btmon`` precisa de ``CAP_NET_RAW``, e nesta máquina ``sudo -n`` pede senha.
Sem ela **a metade do FIO não é capturada** — e o instrumento diz isso em
letras grandes em vez de entregar meio relatório com cara de inteiro. Para ter
as duas metades::

    sudo -v && .venv/bin/python scripts/ensaios/a_captura_armada_do_som_no_radio.py \\
        --exigir-mac <endereço> --segundos 300

A PROCEDÊNCIA, DECLARADA
-------------------------
Como todo instrumento desta pasta, ele imprime de qual ARQUIVO veio cada
biblioteca antes da primeira linha de medição. O parser de ``btsnoop`` **não é
novo**: é o do ``byte_no_fio.py``, importado, porque duas leituras do mesmo
formato é como esta casa fabrica divergência silenciosa.
"""

from __future__ import annotations

import argparse
import os
import select
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime

_AQUI = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_AQUI)
_RAIZ = os.path.dirname(_SCRIPTS)
_SRC = os.path.join(_RAIZ, "src")
for _p in (_AQUI, _SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from byte_no_fio import (
    HID_BT_ENTRADA,
    HID_BT_SAIDA,
    Quadro,
    handles_por_mac,
    ler_btsnoop,
    mascarar,
)
from comum import (
    RADIO,
    Aparelho,
    abrir_no_hidraw,
    cabecalho_do_instrumento,
    censo_da_mesa,
    descobrir_aparelhos,
    fisicos,
    resumo,
    tabela,
)

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.core.physical_report_reader import (
    INPUT_FLAG_AUDIO,
    INPUT_REPORT_BT,
    extract_jack_status,
)
from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    OFFSET_DO_COMMON,
    TAMANHO_DO_DEGRAU,
)
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
    STATUS_MIC_MUDO,
)

#: O `[2]` do envelope de rádio que diz *"o que vem aqui é o `common` de 47
#: bytes"*. Vem do dono (`core/ds_output_report.BT_TAG`) e não é redigitado: o
#: mapa registra, na `plataforma.escada_de_output@dualsense`, que **todo** degrau
#: da escada leva o `common` a partir de `[3]` quando `[2]` é este valor.
TAG_DO_COMMON = rep.BT_TAG

#: Quanto tempo, para cada lado da marca, a janela recorta. Seis segundos é o
#: comprimento que ELA relatou; a janela é maior de propósito, porque o que
#: interessa é o que veio ANTES do som tanto quanto o que veio durante.
JANELA_PADRAO_S = 8.0

#: Quanto tempo o instrumento fica armado, por omissão. Cinco minutos: longo o
#: bastante para ela trabalhar na bancada sem pensar nele, curto o bastante
#: para o arquivo do `btmon` não crescer sem limite.
SEGUNDOS_PADRAO = 300.0

#: Ritmo do `select` na leitura do hidraw. O mesmo do produto.
_SELECT_TIMEOUT_S = 0.25
_READ_LEN = 128


# ---------------------------------------------------------------------------
# As marcas — o instante em que ELA disse "foi agora"
# ---------------------------------------------------------------------------


@dataclass
class Marca:
    """Um instante que ela carimbou apertando o mudo do plástico."""

    monotonico: float
    relogio: str
    mudo_virou: bool
    numero: int


@dataclass
class LeituraDoHidraw:
    """O que a metade de ENTRADA viu enquanto esperava."""

    reports: int = 0
    reports_de_audio: int = 0
    reports_de_estado: int = 0
    marcas: list[Marca] = field(default_factory=list)
    erro: str = ""

    def linhas(self) -> list[str]:
        return [
            f"  reports de entrada lidos ... {self.reports}",
            f"  com o bit de ÁUDIO ligado .. {self.reports_de_audio}",
            f"  de estado (CRC ok, sem áudio) {self.reports_de_estado}",
            f"  marcas dela ................ {len(self.marcas)}",
        ]


#: O que um report de entrada é, para este instrumento. Três respostas, e a
#: do meio é a que existe por causa de um estrago medido.
E_AUDIO = "audio"
E_ESTADO = "estado"
E_NADA = "nada"


def classificar_report(bruto: bytes) -> tuple[str, bool]:
    """``(classe, mudo)`` de um report de entrada. **A função pura da marca.**

    Ela existe separada do laço por uma razão só: é ela que a régua morde. O
    laço abre hidraw e olha o relógio; a decisão *"isto é uma marca dela?"* não
    precisa de nenhum dos dois, e uma decisão que só é exercível com aparelho
    na mesa é uma decisão que ninguém testa.

    **A recusa do report de ÁUDIO vem antes de tudo, e o preço dela está pago
    por escrito.** Com o microfone ligado o DualSense manda Opus no MESMO
    report ``0x31``, com os MESMOS 78 bytes e CRC válido — a única diferença é
    o bit ``0x02`` do byte 1. Em 16/08/2026 um caminho sem essa recusa leu Opus
    como estado de botão, MIC e PS ficaram presos e o daemon tentou abrir a
    Steam dezenas de vezes por segundo; ela descreveu como *"o teclado e o
    mouse com vida própria"*. Aqui o estrago seria mais barato e mais
    traiçoeiro: marcas que ela nunca fez, com a hora certa.

    O resto é do ``extract_jack_status``, que é o dono — ele já recusa CRC
    ruim, tamanho errado e report que não é de estado, e devolve ``None``.
    """
    if not bruto:
        return E_NADA, False
    if bruto[0] == INPUT_REPORT_BT and len(bruto) > 1 and (bruto[1] & INPUT_FLAG_AUDIO):
        return E_AUDIO, False
    status = extract_jack_status(bruto)
    if status is None:
        return E_NADA, False
    return E_ESTADO, bool(status & STATUS_MIC_MUDO)


def escutar_o_hidraw(
    caminho: str, *, segundos: float, parar: threading.Event
) -> LeituraDoHidraw:
    """Lê o hidraw EM LEITURA e carimba toda transição do mudo. Não escreve.

    **A recusa do report de ÁUDIO não é nossa** — ela vem de graça no
    ``extract_jack_status``, que devolve ``None`` para report com o bit
    ``0x02`` ligado ou CRC ruim. Sem ela, um quadro de Opus seria lido como
    estado de jack e o instrumento carimbaria marcas que ela nunca fez.
    """
    saida = LeituraDoHidraw()
    limite = time.monotonic() + max(0.0, float(segundos))
    mudo_antes: bool | None = None
    try:
        no = abrir_no_hidraw(caminho, escrita=False)
    except OSError as erro:
        saida.erro = f"não deu para abrir {caminho} em leitura — {erro}"
        return saida
    with no:
        while time.monotonic() < limite and not parar.is_set():
            prontos, _, _ = select.select([no.fd], [], [], _SELECT_TIMEOUT_S)
            if not prontos:
                continue
            try:
                bruto = os.read(no.fd, _READ_LEN)
            except OSError as erro:
                saida.erro = f"leitura interrompida — {erro}"
                break
            if not bruto:
                continue
            saida.reports += 1
            classe, mudo = classificar_report(bruto)
            if classe == E_AUDIO:
                saida.reports_de_audio += 1
                continue
            if classe != E_ESTADO:
                continue
            saida.reports_de_estado += 1
            if mudo_antes is not None and mudo != mudo_antes:
                saida.marcas.append(
                    Marca(
                        monotonico=time.monotonic(),
                        relogio=datetime.now().strftime("%H:%M:%S.%f")[:-3],
                        mudo_virou=mudo,
                        numero=len(saida.marcas) + 1,
                    )
                )
                print(
                    f"    MARCA {len(saida.marcas)} — {saida.marcas[-1].relogio}"
                    f" (mudo {'LIGOU' if mudo else 'DESLIGOU'})",
                    flush=True,
                )
            mudo_antes = mudo
    return saida


# ---------------------------------------------------------------------------
# A metade do FIO — o `btmon`, e o que se lê dele
# ---------------------------------------------------------------------------


def _sudo_serve() -> bool:
    """`sudo -n true` passa? Se não, a metade do fio não vai existir."""
    try:
        proc = subprocess.run(
            ["sudo", "-n", "true"], capture_output=True, text=True, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def _audio_do_report(corpo: bytes) -> str:
    """Os quatro bytes de áudio de um report de saída, ou "" se não houver.

    ``corpo`` é o quadro L2CAP inteiro (o ``0xA2`` do HID em ``[0]``), então o
    report começa em ``[1]``. Os offsets do ``common`` vêm do dono
    (``core/ds_output_report``), somados ao começo do ``common`` dentro do
    envelope de rádio (``OFFSET_DO_COMMON``) — nenhum número digitado aqui.
    """
    if len(corpo) < 2:
        return ""
    report = corpo[1:]
    if report[0] not in TAMANHO_DO_DEGRAU or len(report) < 3:
        return ""
    if report[2] != TAG_DO_COMMON:
        return ""
    base = 1 + OFFSET_DO_COMMON
    campos = (
        ("fone", rep.COMMON_HEADPHONE_VOLUME),
        ("alto", rep.COMMON_SPEAKER_VOLUME),
        ("mic", rep.COMMON_MIC_VOLUME),
        ("rota", rep.COMMON_AUDIO_PATH),
    )
    pedacos: list[str] = []
    for nome, offset in campos:
        i = base + offset
        pedacos.append(f"{nome}={corpo[i]:#04x}" if i < len(corpo) else f"{nome}=--")
    flag0 = corpo[base + 0] if base < len(corpo) else 0
    autorizados = flag0 & rep.VALID_FLAG0_AUDIO_MASK
    pedacos.append(f"flag0_audio={autorizados:#04x}")
    return " ".join(pedacos)


def _tabela_da_janela(quadros: list[Quadro], handle: int) -> str:
    """O que passou no fio para ESTE handle, agregado por id e sentido."""
    contas: dict[tuple[str, int], int] = {}
    exemplo: dict[tuple[str, int], str] = {}
    for q in quadros:
        if q.handle != handle or not q.corpo:
            continue
        sentido = {HID_BT_SAIDA: "host->controle", HID_BT_ENTRADA: "controle->host"}.get(
            q.corpo[0], f"0x{q.corpo[0]:02x}"
        )
        ident = q.corpo[1] if len(q.corpo) > 1 else -1
        chave = (sentido, ident)
        contas[chave] = contas.get(chave, 0) + 1
        if sentido == "host->controle" and chave not in exemplo:
            exemplo[chave] = _audio_do_report(q.corpo)
    if not contas:
        return "  (nenhum quadro para este controle nesta janela)"
    linhas = [
        [
            sentido,
            f"0x{ident:02x}" if ident >= 0 else "--",
            str(n),
            exemplo.get((sentido, ident), "") or "-",
        ]
        for (sentido, ident), n in sorted(contas.items())
    ]
    return tabela(["sentido", "report", "quadros", "bytes de áudio (1º exemplar)"], linhas)


# ---------------------------------------------------------------------------
# O alvo
# ---------------------------------------------------------------------------


def _escolher_alvo(
    aparelhos: list[Aparelho], mac: str, no: str
) -> tuple[Aparelho | None, str]:
    """O controle desta captura. Recusa em vez de adivinhar."""
    candidatos = [a for a in fisicos(aparelhos) if a.transporte == RADIO]
    if not candidatos:
        return None, "não há nenhum DualSense no RÁDIO na mesa — nada a armar."
    if no:
        achados = [a for a in candidatos if a.caminho_hidraw == no]
        if not achados:
            return None, f"{no} não é um DualSense de rádio na mesa."
        return achados[0], ""
    if mac:
        alvo = mac.lower().replace(":", "")
        achados = [a for a in candidatos if a.mac.lower().replace(":", "") == alvo]
        if not achados:
            return None, f"nenhum DualSense de rádio com esse endereço ({mascarar(mac)})."
        return achados[0], ""
    if len(candidatos) > 1:
        return None, (
            f"há {len(candidatos)} DualSense no rádio — diga qual com --exigir-mac "
            "ou --no. Armar no controle errado é gastar a janela dela."
        )
    return candidatos[0], ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exigir-mac", default="", help="endereço do controle a armar")
    ap.add_argument("--no", default="", help="/dev/hidrawN do controle a armar")
    ap.add_argument("--segundos", type=float, default=SEGUNDOS_PADRAO,
                    help="quanto tempo fica armado")
    ap.add_argument("--janela", type=float, default=JANELA_PADRAO_S,
                    help="quantos segundos recortar para cada lado da marca")
    ap.add_argument("--sem-fio", action="store_true",
                    help="nem tenta o btmon (só a metade do hidraw)")
    argumentos = ap.parse_args(argv)

    print(cabecalho_do_instrumento(
        "a_captura_armada_do_som_no_radio",
        "quando ela ouvir o som do rádio de novo, o que estava no fio naquele "
        "instante — e o que o aparelho estava dizendo?",
        bibliotecas=["os", "select", "subprocess", "threading"],
        nos_evdev=[],
    ))
    aparelhos = descobrir_aparelhos()
    print(censo_da_mesa(aparelhos))

    alvo, recusa = _escolher_alvo(aparelhos, argumentos.exigir_mac, argumentos.no)
    if alvo is None:
        print(f"\nRECUSADO: {recusa}")
        return 2

    handles, fonte_dos_handles = handles_por_mac()
    handle = handles.get(alvo.mac.lower(), -1)
    print(
        f"\nARMADO EM {alvo.caminho_hidraw} ({mascarar(alvo.mac)}, {alvo.transporte})\n"
        f"  handle ACL .. {handle if handle >= 0 else 'DESCONHECIDO'}"
        f"  (fonte: {fonte_dos_handles})\n"
        f"  janela ...... ±{argumentos.janela:.0f} s em volta de cada marca\n"
        f"  duração ..... {argumentos.segundos:.0f} s"
    )

    captura = None
    caminho_captura = ""
    t_fio_zero = time.monotonic()
    if argumentos.sem_fio:
        print("\n  metade do FIO: DESLIGADA por --sem-fio.")
    elif not _sudo_serve():
        print(
            "\n  metade do FIO: **NÃO CAPTURADA** — `sudo -n` pede senha nesta\n"
            "  máquina, e o `btmon` precisa de CAP_NET_RAW. O relatório que sai\n"
            "  daqui tem METADE do que a nota do ensaio pede. Rode `sudo -v`\n"
            "  antes e chame de novo para ter as duas."
        )
    else:
        # O DESTINO SAI DO AMBIENTE, e não de um caminho digitado. O `btmon`
        # roda como root e recria o arquivo; escrever um diretório fixo aqui
        # prenderia a captura à máquina de quem escreveu — e o portão de
        # anonimato pega isso por FORMA, sem consultar nada.
        caminho_captura = os.path.join(
            tempfile.gettempdir(), f"captura-armada-{int(time.time())}.btsnoop"
        )
        subprocess.run(["sudo", "-n", "rm", "-f", caminho_captura], check=False)
        captura = subprocess.Popen(
            ["sudo", "-n", "btmon", "-w", caminho_captura],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.0)  # o btmon precisa abrir o socket antes de a gente contar
        t_fio_zero = time.monotonic()
        print(f"\n  metade do FIO: `btmon -w {caminho_captura}` de pé.")

    print(
        "\nO GESTO DELA, e é UM só:\n"
        "  quando ouvir som saindo deste controle, aperte o botão de MUDO do\n"
        "  plástico (o do microfone). Aperte de novo para desfazer o mudo — as\n"
        "  DUAS transições viram marca, então não há gesto errado.\n"
        f"\nEsperando {argumentos.segundos:.0f} s...\n"
    )

    parar = threading.Event()
    try:
        leitura = escutar_o_hidraw(
            alvo.caminho_hidraw, segundos=argumentos.segundos, parar=parar
        )
    except KeyboardInterrupt:
        parar.set()
        leitura = LeituraDoHidraw(erro="interrompido por Ctrl-C")
    finally:
        if captura is not None:
            captura.terminate()
            try:
                captura.wait(timeout=5)
            except subprocess.TimeoutExpired:
                captura.kill()
            subprocess.run(["sudo", "-n", "chmod", "0644", caminho_captura], check=False)

    print("\nO QUE A METADE DO HIDRAW VIU")
    for linha in leitura.linhas():
        print(linha)
    if leitura.erro:
        print(f"  QUEIXA: {leitura.erro}")

    if not leitura.marcas:
        print(
            "\nNENHUMA MARCA. Isto NÃO é 'o som não aconteceu' — é 'ela não\n"
            "carimbou nada nesta janela'. O ensaio segue inconclusivo, que é\n"
            "exatamente onde ele estava; nada aqui muda uma célula do mapa."
        )

    if captura is None:
        print(
            "\nA METADE DO FIO NÃO EXISTE NESTE RELATÓRIO.\n"
            "  Sem ela não se responde 'saiu report nosso naquele instante?', que\n"
            "  é a pergunta que o ensaio `som-no-radio-observado-nao-replicado`\n"
            "  deixou escrita. Não conclua nada sobre o fio a partir daqui."
        )
        return 0 if not leitura.erro else 1

    quadros, queixas = ler_btsnoop(caminho_captura)
    print(f"\nO QUE A CAPTURA VIU — {len(quadros)} quadro(s) ACL em {caminho_captura}")
    for q in queixas:
        print(f"  QUEIXA DO ARQUIVO: {q}")
    if handle < 0:
        print(
            "  SEM HANDLE para este controle: o sysfs não devolveu o `hciN:<handle>`.\n"
            "  Sem ele não dá para separar os quadros DESTE controle dos dos outros,\n"
            "  e um relatório que some tudo responderia sobre a mesa, não sobre ele."
        )
        return 1

    # O `ts` do btsnoop é de outra época; a marca é monotônica. O que amarra os
    # dois é a POSIÇÃO relativa: normaliza-se pelo primeiro quadro e pela hora
    # em que a captura começou. É aproximado, e a aproximação está declarada.
    if not quadros:
        print("  o arquivo não tem quadro ACL nenhum — nada a recortar.")
        return 1
    t0_fio = quadros[0].ts
    print(
        "\n  AS JANELAS SÃO APROXIMADAS, e a aproximação está declarada: o carimbo\n"
        "  do `btsnoop` é de uma época que não é a do Unix, então as janelas saem\n"
        "  da POSIÇÃO relativa (primeiro quadro = t=0), não de um relógio comum."
    )
    for marca in leitura.marcas:
        centro = t0_fio + (marca.monotonico - t_fio_zero)
        janela = [
            q
            for q in quadros
            if centro - argumentos.janela <= q.ts <= centro + argumentos.janela
        ]
        print(
            f"\n  MARCA {marca.numero} — {marca.relogio}"
            f" (mudo {'LIGOU' if marca.mudo_virou else 'DESLIGOU'}),"
            f" ±{argumentos.janela:.0f} s"
        )
        print(_tabela_da_janela(janela, handle))

    print(resumo(
        "NADA AQUI PROVA SOM, e nada aqui vira célula do mapa. O que este\n"
        "instrumento entrega é o par que faltava — o fio e a entrada, no mesmo\n"
        "instante que ELA carimbou. O veredito continua sendo a orelha dela, e o\n"
        "ensaio `som-no-radio-observado-nao-replicado` continua `inconclusivo`\n"
        "até que uma marca dela venha com report nosso do lado."
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
