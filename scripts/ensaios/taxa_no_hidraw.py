#!/usr/bin/env python3
"""taxa_no_hidraw.py — a taxa de relatórios dos oito nós, na MESMA janela.

A PERGUNTA QUE ELE RESPONDE
----------------------------
*Quantos relatórios por segundo cada DualSense entrega no fio, e cada vpad
repassa, medidos todos ao mesmo tempo?* É o instrumento I-1 do
`docs/process/estudos/2026-08-15-PLANO-DA-MESA-2-2-o-que-so-se-mede-com-quatro.md`,
e dele saem os ensaios E-2 (taxa), E-3 (CRC de entrada) e E-6 (dose-resposta).

POR QUE HIDRAW, E NÃO EVDEV
----------------------------
O irmão mais próximo deste instrumento, `taxa_de_entrada.py`, mede por
**evdev** — o caminho que o jogo usa. Com o co-op ligado esse caminho fica
**mudo nos nós físicos**: o daemon faz `EVIOCGRAB` neles, que é exclusivo, e um
leitor externo conta zero. Isso é o produto funcionando, e não uma medida do
aparelho.

Aqui se mede um andar abaixo: o **hidraw**, que é o quadro do transporte antes
de o `hid_playstation` decodificar. Três consequências, e as três são o motivo
de este arquivo existir:

1. **O `EVIOCGRAB` do evdev não alcança o hidraw.** Cada `open()` de hidraw tem
   fila de entrada própria no kernel, e este instrumento não escreve nada — não
   disputa com o daemon, não tira nada de ninguém. O estado do grab dos evdev
   sai no cabeçalho assim mesmo, porque a pergunta *"então por que aqui não é
   zero?"* merece resposta escrita, e não uma nota de rodapé em algum lugar.
2. **O CRC de entrada é visível.** O `hidraw` recebe o quadro **antes** de o
   driver validar o CRC-32 e descartá-lo. Um leitor de hidraw enxerga o que o
   kernel depois joga fora, que é exatamente a corrupção que o E-3 quer contar.
3. **A porta é o broker.** Os quatro físicos estão `0600` sem ACL — o Hefesto os
   esconde do jogo de propósito. Quem bate por `open()` colhe `EACCES` e escreve
   um zero convincente e falso.

A RÉGUA, DECLARADA (`A-3`, na versão mais barata)
--------------------------------------------------
**Um relatório = um `read()` que retornou no hidraw** = um quadro do
transporte. **Não** é `SYN_REPORT` do evdev, que só sai quando um eixo muda e
que num controle parado fica perto de zero. Os dois números são legítimos e
medem coisas diferentes; confundi-los já produziu tabela errada nesta casa.

A régua independente do braço do cabo, para conferir este instrumento sem
acreditar nele: o `bInterval` do endpoint de interrupção do DualSense no USB é
de **4 ms**, ou seja **250 Hz** cravados, e sai de
`/sys/bus/usb/devices/3-N/3-N:1.3/ep_84/interval`. Se o cabo não der 250 Hz
aqui, o réu é o instrumento.

AS DUAS PORTAS, NO MESMO RELATÓRIO
-----------------------------------
Os quatro físicos entram pelo **broker** (`SCM_RIGHTS`); os quatro vpads, por
**`open()` direto** — o broker recusa vpad de propósito
(`reject_not_physical_dualsense`), porque é por ele que o jogo fala com o
controle e escondê-lo seria o defeito. As duas portas aparecem na coluna
`porta`, nó a nó: sem isso não dá para dizer se os dois braços do ensaio 2+2
mediram pelo mesmo caminho.

A MORDIDA DESTE INSTRUMENTO
----------------------------
Rode com os nós trocados de ordem na linha de comando (`--no`). Se o relatório
não trocar de endereço junto, ele está lendo a ordem de enumeração e não o
aparelho:

    taxa_no_hidraw.py --segundos 5 --no /dev/hidraw4 --no /dev/hidraw9
    taxa_no_hidraw.py --segundos 5 --no /dev/hidraw9 --no /dev/hidraw4

ELE NÃO ESCREVE NADA NO APARELHO
---------------------------------
Abre em `O_RDONLY` quando pode, lê, conta e fecha. Nenhum output report,
nenhum `SET_FEATURE`, nenhuma mudança de cor, rumble ou gatilho.

USO
    taxa_no_hidraw.py                                  # 20 s, os oito nós
    taxa_no_hidraw.py --segundos 60 --verificar-crc    # o E-3
    taxa_no_hidraw.py --csv /tmp/taxa-2-2.csv          # o E-2
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import fcntl
import os
import selectors
import sys
import time
import zlib
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comum import (
    CABO,
    RADIO,
    VPAD,
    Aparelho,
    PortaFechadaError,
    abrir_no_hidraw,
    cabecalho_do_instrumento,
    censo_da_mesa,
    descobrir_aparelhos,
    ler_texto,
    resumo,
    tabela,
)

try:
    from hefesto_dualsense4unix.core.ds_output_report import (
        BT_INPUT_CRC_SEED,
        BT_REPORT_ID,
    )

    _CRC_IMPORTAVEL = ""
except ImportError as _erro:  # pragma: no cover - só fora do venv do projeto
    BT_INPUT_CRC_SEED = 0xA1
    BT_REPORT_ID = 0x31
    _CRC_IMPORTAVEL = str(_erro)

#: Maior relatório de entrada que este aparelho emite é o `0x31` do rádio, com
#: 78 bytes. O buffer é folgado de propósito: `read()` em hidraw devolve UM
#: relatório inteiro por chamada, e um buffer curto truncaria o quadro sem
#: avisar — o que estragaria justamente a conferência de CRC.
TAMANHO_DO_BUFFER = 1024

#: As frases da coluna de CRC nos braços em que ele NÃO existe. Escritas assim,
#: e nunca como `0 falhas`: no cabo os quatro últimos bytes são payload comum, e
#: dizer "zero falhas" ali seria afirmar que se conferiu algo que não há. É a
#: mesma lição que o `censo_features.py` já pagou.
SEM_TRAILER_CABO = "sem trailer (no cabo os 4 últimos bytes são payload)"
SEM_TRAILER_VPAD = "sem trailer (o vpad não é transporte)"


def mascarar_mac(mac: str) -> str:
    """A máscara da casa: octetos 4 e 5 zerados (`OUI:00:00:NN`).

    O OUI fica porque é público e é ele que explica o achado; o que identifica
    o aparelho dela é o sufixo, e esse sai. Há portão que reprova MAC real em
    arquivo versionado, e a saída bruta deste instrumento é versionada.
    """
    partes = mac.split(":")
    if len(partes) != 6:
        return mac
    return ":".join([*partes[:3], "00", "00", partes[5]])


def apelido_mascarado(aparelho: Aparelho) -> str:
    """Como o aparelho aparece na tabela — e nunca com o MAC inteiro."""
    if aparelho.e_vpad:
        return f"vpad {aparelho.rotulo}"
    if aparelho.mac:
        return mascarar_mac(aparelho.mac)
    return aparelho.hidraw


def evdev_principal(aparelho: Aparelho) -> str:
    """O `/dev/input/eventN` principal deste hidraw, resolvido por sysfs AGORA.

    Serve só ao cabeçalho, para declarar o estado do `EVIOCGRAB`. Resolve a
    cada chamada porque os números não são estáveis: em 15/08/2026, entre duas
    leituras com segundos de diferença, um controle reapareceu com outro
    `eventN`.
    """
    raiz = os.path.join(aparelho.dir_device, "input")
    if not os.path.isdir(raiz):
        return ""
    for entrada in sorted(os.listdir(raiz)):
        if not entrada.startswith("input"):
            continue
        dir_input = os.path.join(raiz, entrada)
        nome = ler_texto(os.path.join(dir_input, "name")).strip()
        if "Motion" in nome or "Touchpad" in nome or "Headset" in nome:
            continue
        for sub in sorted(os.listdir(dir_input)):
            if sub.startswith("event"):
                return f"/dev/input/{sub}"
    return ""


class Medida:
    """Quantos relatórios saíram de UM nó, por qual porta, e com que CRC."""

    def __init__(self, aparelho: Aparelho) -> None:
        self.aparelho = aparelho
        self.fd = -1
        self.porta = ""
        self.motivo = ""
        self.erro = ""
        self.relatorios = 0
        self.bytes_min = 0
        self.bytes_max = 0
        self.ids: dict[int, int] = {}
        self.crc_confere = 0
        self.crc_difere = 0
        self.crc_sem_trailer = 0
        self.segundos = 0.0

    @property
    def hz(self) -> float:
        return self.relatorios / self.segundos if self.segundos > 0 else 0.0

    @property
    def e_radio(self) -> bool:
        return self.aparelho.transporte == RADIO

    def registrar(self, dados: bytes, *, conferir_crc: bool) -> None:
        self.relatorios += 1
        tamanho = len(dados)
        if self.bytes_min == 0 or tamanho < self.bytes_min:
            self.bytes_min = tamanho
        if tamanho > self.bytes_max:
            self.bytes_max = tamanho
        if dados:
            self.ids[dados[0]] = self.ids.get(dados[0], 0) + 1
        if conferir_crc and self.e_radio:
            self._conferir_crc(dados)

    def _conferir_crc(self, dados: bytes) -> None:
        """O CRC-32 de entrada do rádio, semente `0xA1`, conforme o driver.

        A conta é a do `hid-playstation`: CRC-32 padrão sobre o byte de semente
        seguido do relatório inteiro menos os quatro últimos bytes, comparado
        com esses quatro bytes lidos em little-endian. Só o `0x31` carrega o
        trailer; o `0x01` curto que o rádio às vezes emite não carrega, e
        contá-lo como falha seria inventar corrupção.
        """
        if len(dados) < 5 or dados[0] != BT_REPORT_ID:
            self.crc_sem_trailer += 1
            return
        esperado = int.from_bytes(dados[-4:], "little")
        semente = zlib.crc32(bytes([BT_INPUT_CRC_SEED]))
        calculado = zlib.crc32(dados[:-4], semente) & 0xFFFFFFFF
        if esperado == calculado:
            self.crc_confere += 1
        else:
            self.crc_difere += 1

    def veredito_crc(self, conferir: bool) -> str:
        if not conferir:
            return "-"
        if self.aparelho.e_vpad:
            return SEM_TRAILER_VPAD
        if not self.e_radio:
            return SEM_TRAILER_CABO
        if self.crc_confere == 0 and self.crc_difere == 0:
            return "nenhum quadro com trailer"
        texto = f"{self.crc_confere} conferem / {self.crc_difere} DIFEREM"
        if self.crc_sem_trailer:
            texto += f" (+{self.crc_sem_trailer} sem trailer)"
        return texto

    def texto_dos_ids(self) -> str:
        if not self.ids:
            return "-"
        return " ".join(f"0x{i:02x}x{n}" for i, n in sorted(self.ids.items()))


def escolher_nos(argumentos: argparse.Namespace) -> tuple[list[Aparelho], list[str]]:
    """Os aparelhos a medir, na ORDEM pedida, e as recusas explicadas.

    Quando `--no` é dado, a ordem da linha de comando é a ordem da tabela — é o
    que torna a mordida verificável: trocar a ordem tem de trocar as linhas de
    lugar SEM trocar o endereço de cada uma. Um nó pedido que o sysfs não
    reconheça como DualSense (físico ou vpad) é RECUSADO, e não medido às
    cegas: ler um hidraw de identidade desconhecida produz um número sem dono.
    """
    aparelhos = descobrir_aparelhos()
    if not argumentos.no:
        escolhidos = [
            a
            for a in aparelhos
            if not (argumentos.so_fisicos and a.e_vpad)
            and not (argumentos.so_vpads and not a.e_vpad)
        ]
        return escolhidos, []

    por_caminho = {a.caminho_hidraw: a for a in aparelhos}
    escolhidos = []
    recusas = []
    for pedido in argumentos.no:
        caminho = os.path.realpath(pedido) if os.path.exists(pedido) else pedido
        alvo = por_caminho.get(caminho) or por_caminho.get(pedido)
        if alvo is None:
            recusas.append(f"{pedido}: não é um DualSense nem um vpad do Hefesto no sysfs de agora")
            continue
        escolhidos.append(alvo)
    return escolhidos, recusas


def abrir(medidas: list[Medida]) -> None:
    """Abre cada nó pela porta que servir, e guarda QUAL serviu.

    `escrita=False` de propósito: este instrumento não escreve no aparelho, e
    pedir `O_RDWR` seria pedir mais poder do que a medição precisa. Pelo broker
    o fd vem `O_RDWR` de qualquer jeito (é o contrato dele), e por isso a porta
    fica registrada em vez de inferida.
    """
    for medida in medidas:
        try:
            no = abrir_no_hidraw(medida.aparelho.caminho_hidraw, escrita=False)
        except PortaFechadaError as erro:
            medida.erro = str(erro)
            medida.porta = "FECHADA"
            medida.motivo = str(erro)
            continue
        medida.fd = no.fd
        medida.porta = no.porta
        medida.motivo = no.motivo


def _drenar(
    seletor: selectors.BaseSelector, medida: Medida, *, contar: bool, conferir_crc: bool
) -> None:
    """Lê tudo o que está na fila deste fd, até `EAGAIN`.

    Drenar até o fim importa: a fila de hidraw do kernel guarda um número
    limitado de relatórios por `open()`, e um leitor que tirasse um por vez
    perderia quadros a 250-400 Hz e reportaria uma taxa menor que a real —
    exatamente o alarme falso que este ensaio existe para não produzir.
    """
    while True:
        try:
            dados = os.read(medida.fd, TAMANHO_DO_BUFFER)
        except BlockingIOError:
            return
        except OSError as erro:
            medida.erro = f"leitura falhou: {erro.strerror or erro}"
            with contextlib.suppress(KeyError, ValueError):
                seletor.unregister(medida.fd)
            return
        if not dados:
            return
        if contar:
            medida.registrar(dados, conferir_crc=conferir_crc)


def medir(
    medidas: list[Medida], segundos: float, *, conferir_crc: bool
) -> tuple[str, str, float]:
    """Conta relatórios dos nós abertos numa janela só. Devolve T0, T1 e o vão.

    Um laço, um `select`, todos os nós. Duas janelas em fila não são um ensaio
    de coexistência — é a exigência 4 do I-1 no plano da mesa 2+2.
    """
    seletor = selectors.DefaultSelector()
    abertos = [m for m in medidas if m.fd >= 0]
    for medida in abertos:
        # O fd é EXCLUSIVAMENTE nosso (o broker fecha a cópia dele logo após o
        # `sendmsg`), então mexer no `O_NONBLOCK` não altera o estado de
        # ninguém. Sem ele, drenar a fila travaria o laço no primeiro nó
        # silencioso e as oito medidas deixariam de ser da mesma janela.
        flags = fcntl.fcntl(medida.fd, fcntl.F_GETFL)
        fcntl.fcntl(medida.fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        seletor.register(medida.fd, selectors.EVENT_READ, medida)

    # O que se acumulou entre o `open` e o relógio não é desta janela: sai
    # fora, sem ser contado. Sem isso o primeiro nó aberto largaria na frente.
    for medida in abertos:
        _drenar(seletor, medida, contar=False, conferir_crc=False)

    t0 = datetime.now()
    inicio = time.monotonic()
    fim = inicio + segundos
    while True:
        restante = fim - time.monotonic()
        if restante <= 0:
            break
        for chave, _ in seletor.select(min(restante, 0.2)):
            _drenar(seletor, chave.data, contar=True, conferir_crc=conferir_crc)
    decorrido = time.monotonic() - inicio
    t1 = datetime.now()

    for medida in abertos:
        medida.segundos = decorrido
    seletor.close()
    return (
        t0.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        t1.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        decorrido,
    )


def linhas_da_tabela(medidas: list[Medida], conferir_crc: bool) -> list[list[str]]:
    linhas = []
    for medida in medidas:
        if medida.erro and medida.fd < 0:
            valor = "NÃO ABRIU"
            hz = "-"
        else:
            valor = str(medida.relatorios)
            hz = f"{medida.hz:.1f}"
        linhas.append(
            [
                apelido_mascarado(medida.aparelho),
                medida.aparelho.transporte,
                medida.aparelho.hidraw,
                medida.porta or "-",
                valor,
                hz,
                f"{medida.bytes_min}..{medida.bytes_max}" if medida.bytes_max else "-",
                medida.texto_dos_ids(),
                medida.veredito_crc(conferir_crc),
            ]
        )
    return linhas


def escrever_csv(
    caminho: str, medidas: list[Medida], t0: str, t1: str, conferir_crc: bool
) -> None:
    """Ensaio que não vira linha de tabela vira lembrança (exigência 8 do I-1)."""
    with open(caminho, "w", encoding="utf-8", newline="") as arquivo:
        # `lineterminator="\n"`: o padrão do módulo é `\r\n`, e um CSV com CRLF
        # entra no repositório brigando com o `core.autocrlf` do git — que o
        # normaliza na próxima vez que tocar no arquivo, fazendo a saída bruta
        # deixar de ser byte a byte o que o instrumento escreveu.
        escritor = csv.writer(arquivo, lineterminator="\n")
        escritor.writerow(
            [
                "no",
                "aparelho",
                "transporte",
                "porta",
                "motivo_da_porta",
                "relatorios",
                "segundos",
                "hz",
                "bytes_min",
                "bytes_max",
                "report_ids",
                "crc_confere",
                "crc_difere",
                "crc_sem_trailer",
                "crc_veredito",
                "t0_parede",
                "t1_parede",
                "erro",
            ]
        )
        for medida in medidas:
            escritor.writerow(
                [
                    medida.aparelho.hidraw,
                    apelido_mascarado(medida.aparelho),
                    medida.aparelho.transporte,
                    medida.porta,
                    medida.motivo,
                    medida.relatorios,
                    f"{medida.segundos:.3f}",
                    f"{medida.hz:.2f}",
                    medida.bytes_min,
                    medida.bytes_max,
                    medida.texto_dos_ids(),
                    medida.crc_confere,
                    medida.crc_difere,
                    medida.crc_sem_trailer,
                    medida.veredito_crc(conferir_crc),
                    t0,
                    t1,
                    medida.erro,
                ]
            )


def _avisar_taxa_identica(medidas: list[Medida]) -> list[str]:
    """O controle negativo embutido do E-2, e ele é de graça.

    Se dois nós contarem EXATAMENTE o mesmo número de relatórios, desconfie do
    instrumento antes de comemorar: pode estar lendo o mesmo nó duas vezes. O
    plano pede isto para o par vpad-x-físico; aqui vale para QUALQUER par,
    porque a pergunta ("é o mesmo nó?") é a mesma e o par vpad-x-vpad é tão
    capaz de denunciar o defeito quanto o outro.

    Contagem igual **não é prova de defeito** — dois vpads alimentados pelo
    mesmo laço do daemon empatam de verdade. O aviso pede conferência: se os
    apelidos e os MACs são distintos, o empate é do produto, não do
    instrumento. É a armadilha `A-10`: controle negativo não prova obediência
    por si só.
    """
    avisos = []
    vivas = [m for m in medidas if m.relatorios]
    for i, uma in enumerate(vivas):
        for outra in vivas[i + 1 :]:
            if uma.relatorios != outra.relatorios:
                continue
            avisos.append(
                f"{apelido_mascarado(uma.aparelho)} ({uma.aparelho.hidraw}) e "
                f"{apelido_mascarado(outra.aparelho)} ({outra.aparelho.hidraw}) contaram "
                f"o MESMO número de relatórios ({uma.relatorios}) — confira se não é o "
                "mesmo nó lido duas vezes. Apelidos e nós distintos acima = o empate é "
                "do produto, não do instrumento."
            )
    return avisos


def main() -> int:
    analisador = argparse.ArgumentParser(
        description="Taxa de relatórios no hidraw dos físicos e dos vpads, na mesma janela.",
    )
    analisador.add_argument("--segundos", type=float, default=20.0, help="janela (padrão 20 s)")
    analisador.add_argument("--csv", default="", help="arquivo CSV de saída")
    analisador.add_argument(
        "--verificar-crc",
        action="store_true",
        help="confere o CRC-32 de entrada (semente 0xA1) nos nós de rádio",
    )
    analisador.add_argument(
        "--no",
        action="append",
        default=[],
        metavar="CAMINHO",
        help="mede SÓ estes nós, na ordem dada (a mordida do instrumento)",
    )
    analisador.add_argument("--so-fisicos", action="store_true", help="ignorar os vpads")
    analisador.add_argument("--so-vpads", action="store_true", help="ignorar os físicos")
    argumentos = analisador.parse_args()

    aparelhos = descobrir_aparelhos()
    escolhidos, recusas = escolher_nos(argumentos)

    print(
        cabecalho_do_instrumento(
            "taxa_no_hidraw.py",
            "quantos relatórios por segundo cada nó entrega, todos na mesma janela?",
            bibliotecas=["os", "selectors", "time", "zlib", "fcntl"],
            escreve_no_aparelho=False,
            daemon_precisa_parar=False,
            nos_evdev=[e for e in (evdev_principal(a) for a in escolhidos) if e],
        )
    )
    print(
        "  régua ............ 1 relatório = 1 read() que retornou no hidraw "
        "(o quadro do TRANSPORTE),\n"
        "                     NÃO um SYN_REPORT do evdev — as duas contas medem "
        "coisas diferentes."
    )
    print(
        "  o grab acima ..... é do EVDEV, e NÃO alcança o hidraw: cada open() de "
        "hidraw tem\n"
        "                     fila própria no kernel. Por isso aqui não sai zero "
        "onde o\n"
        "                     taxa_de_entrada.py sai MUDO."
    )
    if argumentos.verificar_crc:
        origem = (
            "hefesto_dualsense4unix.core.ds_output_report"
            if not _CRC_IMPORTAVEL
            else f"embutido (o pacote não importou: {_CRC_IMPORTAVEL})"
        )
        print(
            f"  CRC .............. semente 0x{BT_INPUT_CRC_SEED:02X} sobre o "
            f"relatório 0x{BT_REPORT_ID:02X}, de {origem}.\n"
            "                     Só o RÁDIO carrega trailer; no cabo os quatro "
            "últimos bytes são\n"
            "                     payload, e a coluna diz `sem trailer`, nunca "
            "`0 falhas`."
        )
    print("=" * 78)

    print(f"\n  {censo_da_mesa(aparelhos)}")

    for recusa in recusas:
        print(f"  RECUSADO: {recusa}")

    if not escolhidos:
        print(resumo("nenhum nó selecionado — nada medido."))
        return 1

    medidas = [Medida(a) for a in escolhidos]
    abrir(medidas)

    abertos = [m for m in medidas if m.fd >= 0]
    if not abertos:
        print(resumo("nenhum nó abriu — nem pelo broker, nem por open(). Nada medido."))
        for medida in medidas:
            print(f"    - {medida.aparelho.hidraw}: {medida.erro}")
        return 2

    print(f"\n  medindo {len(abertos)} nó(s) por {argumentos.segundos:.0f} s, numa janela só.")
    print("  >> NÃO é preciso mexer em nada: o DualSense parado na mesa já transmite.")

    t0, t1, decorrido = medir(medidas, argumentos.segundos, conferir_crc=argumentos.verificar_crc)

    print(f"\n  T0 (hora de parede) .. {t0}")
    print(f"  T1 (hora de parede) .. {t1}")
    print(f"  janela ............... {decorrido:.3f} s de relógio monotônico\n")

    cabecalho = [
        "aparelho",
        "transporte",
        "nó",
        "porta",
        "relatórios",
        "Hz",
        "bytes",
        "report ids",
        "CRC de entrada",
    ]
    fisicas = [m for m in medidas if not m.aparelho.e_vpad]
    virtuais = [m for m in medidas if m.aparelho.e_vpad]

    if fisicas:
        print("  OS CONTROLES FÍSICOS — o que o APARELHO entrega no fio\n")
        print(tabela(cabecalho, linhas_da_tabela(fisicas, argumentos.verificar_crc)))
    if virtuais:
        print("\n  OS VPADS — a saída do produto, e o controle negativo desta janela\n")
        print(tabela(cabecalho, linhas_da_tabela(virtuais, argumentos.verificar_crc)))

    falhas = [m for m in medidas if m.erro]
    if falhas:
        print("\n  NÓS COM FALHA (barulhenta de propósito):")
        for medida in falhas:
            print(f"    - {medida.aparelho.hidraw}: {medida.erro}")

    for aviso in _avisar_taxa_identica(medidas):
        print(f"\n  ATENÇÃO (controle negativo): {aviso}")

    # A identidade é RESOLVIDA DE NOVO no fim: se um nó trocou de dono no meio
    # da janela, a linha acima fala de um aparelho que já não estava lá.
    depois = {a.hidraw: a.mac for a in descobrir_aparelhos()}
    mudou = [
        m.aparelho.hidraw
        for m in medidas
        if depois.get(m.aparelho.hidraw, m.aparelho.mac) != m.aparelho.mac
    ]
    if mudou:
        print(
            "\n  ATENÇÃO: a ligação hidraw->aparelho MUDOU durante a janela em "
            + ", ".join(mudou)
            + ". Não conclua nada sobre esses nós; rode o quem_e_quem.py de novo."
        )

    if argumentos.verificar_crc:
        conferidos = sum(m.crc_confere for m in medidas)
        divergentes = sum(m.crc_difere for m in medidas)
        if conferidos == 0:
            print(
                "\n  CONTROLE POSITIVO REPROVADO: nenhum quadro teve CRC conferido "
                "em lugar nenhum.\n"
                "  CRC que nunca confere é instrumento quebrado, não aparelho "
                "corrompido — NÃO\n"
                "  escreva nada sobre corrupção a partir desta rodada."
            )
        else:
            print(
                f"\n  CONTROLE POSITIVO: {conferidos} quadros com CRC conferido — "
                "o instrumento sabe conferir.\n"
                f"  Falhas de CRC no rádio: {divergentes}."
            )

    if argumentos.csv:
        escrever_csv(argumentos.csv, medidas, t0, t1, argumentos.verificar_crc)
        print(f"\n  CSV escrito em {argumentos.csv}")

    for medida in medidas:
        if medida.fd >= 0:
            with contextlib.suppress(OSError):
                os.close(medida.fd)

    por_transporte: dict[str, list[float]] = {}
    for medida in medidas:
        if medida.relatorios and medida.aparelho.transporte in (CABO, RADIO):
            por_transporte.setdefault(medida.aparelho.transporte, []).append(medida.hz)
    virtuais_vivas = [m.hz for m in medidas if m.aparelho.transporte == VPAD and m.relatorios]

    if len(por_transporte) >= 2:
        pedacos = [
            f"{t}: {sum(v) / len(v):.1f} Hz (n={len(v)})" for t, v in sorted(por_transporte.items())
        ]
        veredito = "cada braço entregou — " + "; ".join(pedacos)
        if virtuais_vivas:
            veredito += f"; vpads: {sum(virtuais_vivas) / len(virtuais_vivas):.1f} Hz"
        veredito += ". Régua: relatório de hidraw, não SYN_REPORT."
    elif por_transporte:
        transporte, valores = next(iter(por_transporte.items()))
        veredito = (
            f"relatórios medidos SÓ no {transporte} ({sum(valores) / len(valores):.1f} Hz). "
            "Nada foi comparado entre transportes."
        )
    else:
        veredito = (
            "nenhum relatório contado em nó nenhum — o réu provável é a porta, não o aparelho."
        )
    print(resumo(veredito))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
