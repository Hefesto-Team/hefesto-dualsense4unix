#!/usr/bin/env python3
"""microfone_no_cabo.py — o microfone do cabo capta? E a companhia custa? (E-5 e E-6)

AS DUAS PERGUNTAS, E POR QUE ELAS MORAM NO MESMO INSTRUMENTO
-------------------------------------------------------------
**E-5:** *o microfone do controle NO CABO capta de verdade?* A célula
`audio.microfone@dualsense`, coluna `cabo_confianca`, está em
`inferido-do-codigo`, e a evidência de hoje é **o arquivo do WirePlumber** — o
que é medir a configuração, não o aparelho. O braço do rádio já é `medido` de
verdade desde 25/07 (protocolo byte a byte, Opus decodificado).

**E-6:** *quando o controlador USB é carregado pelos controles do cabo, a
entrada dos do rádio cai?* Nesta máquina os dois DualSense do cabo e o
adaptador de Bluetooth dividem o **mesmo controlador xHCI** (`0000:0c:00.3`),
que é a pré-condição física da suspeita de 10/08 — *"um controle NO CABO matava
a saída do controle NO BT"*.

E-6 está aqui porque **a carga do E-6 É a medição do E-5**: capturar o
microfone USB é tráfego isócrono no controlador compartilhado, e é a única
carga que este ensaio pode gerar sem escrever um byte no aparelho. A versão
óbvia — martelar com rumble — escreveria, e escrita está fora desta janela.

O DESENHO DO E-6 É DOSE-RESPOSTA, E É POR ISSO QUE ELE VALE
-------------------------------------------------------------
Três patamares de carga (0, 1 e 2 microfones capturando), medindo o MESMO
aparelho consigo mesmo. É o `D2` do método, e é o único desenho do plano da
mesa 2+2 **imune ao confundimento braço/unidade** da Lei 4: não se compara
controle com controle, compara-se um controle com ele mesmo sob três cargas.

A escada é percorrida **para cima e para baixo, em rodadas** (0-1-2 numa
rodada, 2-1-0 na seguinte). Sem isso, uma queda que fosse só deriva de tempo —
um controle esquentando, o rádio ficando mais cheio, qualquer coisa que anda
para um lado só — sairia com cara de dose-resposta. A ordem alternada faz a
deriva se cancelar e a dose, se existir, sobreviver.

A RÉGUA DO E-5, E O NEGATIVO QUE QUASE ME ENGANOU
--------------------------------------------------
A régua é de máquina, não de ouvido: **zeros exatos em todas as amostras = não
captou; qualquer piso de ruído = captou.**

O negativo dessa régua tinha de ser uma fonte que se sabe muda. A primeira
tentativa foi o dispositivo `null` do ALSA — e ele devolveu **1880 amostras
diferentes de zero, com pico 31868** em um segundo. O `null` do ALSA não zera o
buffer: ele entrega memória não inicializada. Usá-lo de negativo teria
"provado" que uma fonte muda produz piso de ruído, e com isso qualquer lixo
teria virado captação.

O negativo que este instrumento usa é o **monitor de um sink SUSPENSO que não é
DualSense**, gravado pelo MESMO `arecord` e analisado pelo MESMO código —
`arecord -D pulse` com `PULSE_SOURCE` apontado para ele. Medido: zeros exatos,
pico 0. Só depois disso "piso de ruído" é medida, e não adjetivo.

Sink de DualSense fica de fora do negativo de propósito: monitorar o sink dele
acorda a saída do controle, e acordar a saída é mexer no aparelho.

A PORTA, DECLARADA — e são DUAS, porque são duas camadas
---------------------------------------------------------
- **E-5** mede por **ALSA** (`arecord`, `alsa-lib`), sem tocar em hidraw.
- **E-6** mede a taxa de entrada por **hidraw pelo broker**
  (`comum.abrir_no_hidraw`): com o co-op ligado os físicos estão `0600` e um
  `open()` direto ali mede `EACCES`, não o aparelho.

O QUE ELE NUNCA FAZ
--------------------
**Não escreve no aparelho.** Capturar microfone é leitura; o alto-falante não é
tocado, nem a cor, nem o rumble, nem nenhum gatilho. Nenhum `SET_FEATURE`.

PRECISA DO DAEMON PARADO? **Não**, e não pode pedir: parar o daemon derruba os
quatro vpads e o co-op.

USO
    microfone_no_cabo.py                         # só o E-5
    microfone_no_cabo.py --dose-resposta         # E-5 e depois o E-6
    microfone_no_cabo.py --dose-resposta --rodadas 3 --janela 12 --csv /tmp/mic.csv
"""

from __future__ import annotations

import argparse
import array
import contextlib
import csv
import os
import selectors
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from dataclasses import dataclass, field
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# O `_dispositivo_usb_pai` é IMPORTADO, não recopiado: é a régua que amarra
# placa de som a controle, e esta casa já pagou o preço de três instrumentos
# respondendo à mesma pergunta de três jeitos (um deles errado). Com dois
# controles no cabo, adivinhar a placa por ordem erraria metade das vezes.
from audio_por_transporte import _dispositivo_usb_pai
from comum import (
    CABO,
    RADIO,
    Aparelho,
    NoAberto,
    PortaFechadaError,
    abrir_no_hidraw,
    cabecalho_do_instrumento,
    censo_da_mesa,
    descobrir_aparelhos,
    fisicos,
    ler_texto,
    resumo,
    tabela,
)
from imu_no_cabo import PERFIL_DO_TRANSPORTE, mascarar

USBID_DUALSENSE = "054c:0ce6"

#: O byte `status[1]` do report de entrada. Offset 53 dentro do
#: `struct dualsense_input_report`; o transporte decide o endereço absoluto,
#: como no `imu_no_cabo.py`.
#:
#: **`DS_STATUS1_MIC_DETECT` (BIT 1) é do JACK, não do microfone embutido.** O
#: driver o define ao lado de `HP_DETECT` e os soma em `DS_STATUS1_JACK_DETECT`
#: (`hid-playstation.c:179`), que é como o kernel avisa que plugaram um fone com
#: microfone na entrada de 3,5 mm. Medido em 15/08/2026 nesta mesa: os dois
#: controles do cabo saem com o bit **limpo** e mesmo assim o microfone
#: embutido entrega piso de ruído pelo ALSA. Ler este bit como "tem microfone"
#: teria produzido a conclusão exatamente oposta à medição.
OFFSET_STATUS1_NO_CORPO = 53
BIT_JACK_MIC_DETECT = 0x02
BIT_MIC_MUTE = 0x04

_BYTES_POR_LEITURA = 256

#: Quantos segundos de folga antes de medir, para a captura se estabilizar. O
#: `arecord` gasta os primeiros instantes negociando altset e enchendo o
#: primeiro período — medir dentro dessa janela mediria o `arecord` subindo, e
#: não a carga no controlador.
_ASSENTAR_S = 2.0


@dataclass
class Placa:
    """Uma placa ALSA de DualSense, já amarrada ao controle que a expõe."""

    numero: str
    identificador: str
    usb: str
    dono: Aparelho | None = None
    canais: int = 2

    @property
    def dispositivo(self) -> str:
        return f"hw:{self.numero},0"


@dataclass
class Captura:
    """O que N segundos de microfone produziram — em números, não em adjetivos."""

    rotulo: str
    dispositivo: str
    amostras: int = 0
    nao_zero: int = 0
    pico: int = 0
    rms: float = 0.0
    erro: str = ""

    @property
    def captou(self) -> bool:
        return self.amostras > 0 and self.nao_zero > 0

    @property
    def veredito(self) -> str:
        if self.erro:
            return "NÃO GRAVOU"
        if not self.amostras:
            return "SEM AMOSTRA"
        if self.nao_zero == 0:
            return "ZEROS EXATOS"
        return "PISO DE RUÍDO"


@dataclass
class Janela:
    """Uma janela de contagem de reports, num patamar de carga."""

    patamar: int
    rodada: int
    quando: str
    segundos: float = 0.0
    reports: dict[str, int] = field(default_factory=dict)

    def hz(self, chave: str) -> float:
        if self.segundos <= 0:
            return 0.0
        return self.reports.get(chave, 0) / self.segundos


def _canais_de_captura(numero: str) -> int:
    """Quantos canais a interface de CAPTURA da placa declara, lido do `/proc`.

    Não é detalhe: `arecord -c 1` na placa do DualSense falha com *"Contagem de
    canais não disponível"*, porque a captura dele é estéreo. Um instrumento
    que chutasse 1 canal reportaria "não gravou" e a próxima pessoa iria
    procurar defeito no aparelho.
    """
    texto = ler_texto(f"/proc/asound/card{numero}/stream0")
    dentro = False
    for linha in texto.splitlines():
        despido = linha.strip()
        if despido.startswith("Capture:"):
            dentro = True
            continue
        if despido.startswith("Playback:"):
            dentro = False
            continue
        if dentro and despido.startswith("Channels:"):
            with contextlib.suppress(ValueError):
                return int(despido.split(":", 1)[1].strip())
    return 2


def placas_de_dualsense(alvos: list[Aparelho]) -> list[Placa]:
    """As placas ALSA de DualSense, cada uma amarrada ao seu controle."""
    achadas: list[Placa] = []
    base = "/proc/asound"
    if not os.path.isdir(base):
        return achadas
    usb_por_aparelho = {a.hidraw: _dispositivo_usb_pai(a.dir_device) for a in alvos}
    for entrada in sorted(os.listdir(base)):
        if not entrada.startswith("card") or not entrada[4:].isdigit():
            continue
        numero = entrada[4:]
        usbid = ler_texto(os.path.join(base, entrada, "usbid")).strip().lower()
        if usbid != USBID_DUALSENSE:
            continue
        usb = _dispositivo_usb_pai(f"/sys/class/sound/{entrada}/device")
        dono = next((a for a in alvos if usb and usb_por_aparelho.get(a.hidraw) == usb), None)
        achadas.append(
            Placa(
                numero=numero,
                identificador=ler_texto(os.path.join(base, entrada, "id")).strip(),
                usb=usb,
                dono=dono,
                canais=_canais_de_captura(numero),
            )
        )
    return achadas


def _analisar_wav(caminho: str, captura: Captura) -> None:
    """Abre o WAV e enche a `Captura` — a régua inteira mora aqui, e é só esta."""
    try:
        with wave.open(caminho, "rb") as arquivo:
            if arquivo.getsampwidth() != 2:
                captura.erro = f"largura de amostra {arquivo.getsampwidth()} B (esperava 2)"
                return
            bruto = arquivo.readframes(arquivo.getnframes())
    except (OSError, wave.Error) as erro:
        captura.erro = f"não pude ler o WAV: {erro}"
        return
    amostras = array.array("h")
    amostras.frombytes(bruto[: len(bruto) // 2 * 2])
    captura.amostras = len(amostras)
    if not amostras:
        return
    captura.nao_zero = sum(1 for x in amostras if x)
    captura.pico = max(abs(x) for x in amostras)
    captura.rms = (sum(float(x) * x for x in amostras) / len(amostras)) ** 0.5


def gravar(
    dispositivo: str, segundos: float, canais: int, rotulo: str, *, fonte_pulse: str = ""
) -> Captura:
    """Grava `segundos` de `dispositivo` com `arecord` e devolve os números.

    O MESMO binário e o MESMO analisador servem à medição e ao negativo — se a
    régua fosse outra no negativo, ele não seria negativo de coisa nenhuma.
    """
    captura = Captura(rotulo=rotulo, dispositivo=dispositivo)
    if not shutil.which("arecord"):
        captura.erro = "arecord não encontrado"
        return captura
    ambiente = dict(os.environ)
    if fonte_pulse:
        ambiente["PULSE_SOURCE"] = fonte_pulse
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temporario:
        caminho = temporario.name
    try:
        resultado = subprocess.run(
            [
                "arecord",
                "-D",
                dispositivo,
                "-f",
                "S16_LE",
                "-r",
                "48000",
                "-c",
                str(canais),
                "-d",
                str(int(segundos)),
                caminho,
            ],
            capture_output=True,
            text=True,
            timeout=segundos + 20,
            check=False,
            env=ambiente,
        )
        if resultado.returncode != 0:
            captura.erro = (resultado.stderr or "").strip().splitlines()[-1:] or ["falhou"]
            captura.erro = captura.erro[0] if isinstance(captura.erro, list) else captura.erro
            return captura
        _analisar_wav(caminho, captura)
    except (OSError, subprocess.SubprocessError) as erro:
        captura.erro = str(erro)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(caminho)
    return captura


def _sink_suspenso_sem_dualsense() -> str:
    """O monitor de um sink SUSPENSO que não é DualSense — o negativo da régua.

    Suspenso quer dizer que ninguém está tocando nada nele, e o monitor de um
    sink parado entrega zeros exatos. DualSense fica de fora: monitorar o sink
    dele acorda a saída do controle, e acordar a saída é mexer no aparelho.
    """
    if not shutil.which("pactl"):
        return ""
    try:
        saida = subprocess.run(
            ["pactl", "list", "short", "sources"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    for linha in saida.stdout.splitlines():
        campos = linha.split("\t")
        if len(campos) < 5 or not campos[1].endswith(".monitor"):
            continue
        if "DualSense" in campos[1] or "Sony" in campos[1]:
            continue
        if campos[-1].strip() == "SUSPENDED":
            return campos[1]
    return ""


# ---------------------------------------------------------------------------
# O estado do microfone SEGUNDO O APARELHO — a desambiguação de um "zeros"
# ---------------------------------------------------------------------------


def estado_do_microfone(aparelho: Aparelho) -> str:
    """`status[1]` do report de entrada, cru — para desambiguar um silêncio.

    Existe porque microfone mudo por hardware e rota de áudio quebrada produzem
    o mesmo `ZEROS EXATOS`, e chamá-los pelo mesmo nome seria a calúnia de
    sempre.

    **Ressalva declarada, e ela é dupla.** `DS_STATUS1_MIC_MUTE` é definido no
    driver e nunca lido por ele (`hid-playstation.c:179`), então a semântica
    não tem confirmação de terceiro. E o bit vizinho, `MIC_DETECT`, é do **jack
    de 3,5 mm**, não do microfone embutido — medido aqui em 15/08/2026, com o
    bit limpo nos dois do cabo e o microfone embutido captando. O que sai daqui
    é o BYTE; a leitura ao lado é sugestão do fonte, não veredito.
    """
    perfil = PERFIL_DO_TRANSPORTE.get(aparelho.transporte)
    if perfil is None:
        return "transporte desconhecido"
    try:
        no = abrir_no_hidraw(aparelho.caminho_hidraw, escrita=False)
    except (PortaFechadaError, OSError) as erro:
        return f"não abriu: {erro}"
    posicao = perfil["corpo"] + OFFSET_STATUS1_NO_CORPO
    try:
        os.set_blocking(no.fd, False)
        prazo = time.monotonic() + 2.0
        while time.monotonic() < prazo:
            try:
                bruto = os.read(no.fd, _BYTES_POR_LEITURA)
            except BlockingIOError:
                time.sleep(0.005)
                continue
            if not bruto or bruto[0] != perfil["report_id"] or len(bruto) <= posicao:
                continue
            byte = bruto[posicao]
            jack = "com fone" if byte & BIT_JACK_MIC_DETECT else "sem fone"
            mudo = "bit de MUDO ligado" if byte & BIT_MIC_MUTE else "bit de mudo limpo"
            return f"status[1]=0x{byte:02x} — jack {jack}, {mudo}"
        return "nenhum report no prazo"
    finally:
        no.fechar()


# ---------------------------------------------------------------------------
# O E-6: a dose-resposta
# ---------------------------------------------------------------------------


def _abrir_fisicos(alvos: list[Aparelho]) -> tuple[dict[int, Aparelho], list[NoAberto], list[str]]:
    """Abre os quatro físicos pelo broker, uma vez para a fase inteira."""
    abertos: dict[int, Aparelho] = {}
    nos: list[NoAberto] = []
    falhas: list[str] = []
    for aparelho in alvos:
        try:
            no = abrir_no_hidraw(aparelho.caminho_hidraw, escrita=False)
        except (PortaFechadaError, OSError) as erro:
            falhas.append(f"{mascarar(aparelho.mac)} ({aparelho.hidraw}): {erro}")
            continue
        os.set_blocking(no.fd, False)
        abertos[no.fd] = aparelho
        nos.append(no)
    return abertos, nos, falhas


def _drenar(fds: list[int]) -> None:
    """Esvazia a fila de cada fd antes de contar.

    Sem isto, a primeira janela contaria o que o kernel guardou ENQUANTO o
    patamar anterior era desmontado — e a contagem do patamar 1 apareceria
    inflada pelo que sobrou do patamar 0.
    """
    for fd in fds:
        while True:
            try:
                if not os.read(fd, _BYTES_POR_LEITURA):
                    break
            except BlockingIOError:
                break
            except OSError:
                break


def _contar_janela(
    abertos: dict[int, Aparelho], seletor: selectors.BaseSelector, janela: Janela, segundos: float
) -> None:
    """Conta reports VÁLIDOS de cada nó por `segundos`, todos na mesma janela."""
    _drenar(list(abertos))
    inicio = time.monotonic()
    fim = inicio + segundos
    while True:
        restante = fim - time.monotonic()
        if restante <= 0:
            break
        for chave, _ in seletor.select(min(restante, 0.25)):
            aparelho = abertos[chave.fd]
            perfil = PERFIL_DO_TRANSPORTE.get(aparelho.transporte)
            try:
                bruto = os.read(chave.fd, _BYTES_POR_LEITURA)
            except BlockingIOError:
                continue
            except OSError:
                continue
            if not bruto or perfil is None or bruto[0] != perfil["report_id"]:
                continue
            chave_do_no = aparelho.hidraw
            janela.reports[chave_do_no] = janela.reports.get(chave_do_no, 0) + 1
    janela.segundos = time.monotonic() - inicio


def _carga(placas: list[Placa], quantas: int, duracao: float) -> list[subprocess.Popen[bytes]]:
    """Sobe `quantas` capturas de microfone — a carga isócrona no controlador."""
    processos: list[subprocess.Popen[bytes]] = []
    for placa in placas[:quantas]:
        processos.append(
            subprocess.Popen(
                [
                    "arecord",
                    "-D",
                    placa.dispositivo,
                    "-f",
                    "S16_LE",
                    "-r",
                    "48000",
                    "-c",
                    str(placa.canais),
                    "-d",
                    str(int(duracao)),
                    "/dev/null",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        )
    return processos


def _derrubar(processos: list[subprocess.Popen[bytes]]) -> None:
    for processo in processos:
        with contextlib.suppress(OSError):
            processo.terminate()
    for processo in processos:
        with contextlib.suppress(subprocess.TimeoutExpired, OSError):
            processo.wait(timeout=5)


def dose_resposta(
    alvos: list[Aparelho], placas: list[Placa], janela_s: float, rodadas: int
) -> tuple[list[Janela], list[str]]:
    """A escada de três patamares, subindo e descendo, por `rodadas` vezes."""
    abertos, nos, falhas = _abrir_fisicos(alvos)
    janelas: list[Janela] = []
    if not abertos:
        return janelas, falhas
    seletor = selectors.DefaultSelector()
    for fd in abertos:
        seletor.register(fd, selectors.EVENT_READ)
    try:
        for rodada in range(1, rodadas + 1):
            ordem = [0, 1, 2] if rodada % 2 else [2, 1, 0]
            for patamar in ordem:
                processos = _carga(placas, patamar, janela_s + _ASSENTAR_S + 5)
                time.sleep(_ASSENTAR_S)
                janela = Janela(
                    patamar=patamar,
                    rodada=rodada,
                    quando=datetime.now().isoformat(timespec="milliseconds"),
                )
                _contar_janela(abertos, seletor, janela, janela_s)
                janelas.append(janela)
                _derrubar(processos)
                print(
                    f"    rodada {rodada}, patamar {patamar}: "
                    + ", ".join(
                        f"{a.hidraw}={janela.hz(a.hidraw):.1f} Hz" for a in abertos.values()
                    )
                )
    finally:
        seletor.close()
        for no in nos:
            no.fechar()
    return janelas, falhas


def _resumo_por_patamar(
    janelas: list[Janela], aparelho: Aparelho
) -> dict[int, tuple[float, float, float]]:
    """Por patamar: (média, mínimo, máximo) das taxas daquele aparelho."""
    por_patamar: dict[int, list[float]] = {}
    for janela in janelas:
        por_patamar.setdefault(janela.patamar, []).append(janela.hz(aparelho.hidraw))
    return {
        patamar: (sum(v) / len(v), min(v), max(v)) for patamar, v in sorted(por_patamar.items())
    }


def _veredito_da_dose(resumo_do_aparelho: dict[int, tuple[float, float, float]]) -> str:
    """A conclusão de UM aparelho — conservadora de propósito.

    "Não mexeu" é resultado, não falha do ensaio (`A-20`). E queda que não
    supera a própria dispersão das rodadas não é queda: é ruído com sorte.
    """
    if len(resumo_do_aparelho) < 3:
        return "patamares de menos"
    medias = [resumo_do_aparelho[p][0] for p in (0, 1, 2)]
    dispersao = max(alto - baixo for _, baixo, alto in resumo_do_aparelho.values())
    queda = medias[0] - medias[2]
    monotonica = medias[0] >= medias[1] >= medias[2]
    if abs(queda) <= dispersao:
        return f"sem efeito separável (variação {queda:+.1f} Hz, dispersão {dispersao:.1f} Hz)"
    if monotonica and queda > 0:
        percentual = queda / medias[0] * 100 if medias[0] else 0.0
        return f"QUEDA dose-dependente: {queda:.1f} Hz ({percentual:.1f}%), monotônica"
    return f"mudou {queda:+.1f} Hz, mas NÃO monotônica — não é dose-resposta"


def _escrever_csv(
    caminho: str, capturas: list[Captura], janelas: list[Janela], quando: str
) -> None:
    # `lineterminator="\n"` porque o padrão do módulo `csv` é CRLF, e o
    # `.gitattributes` desta casa é `eol=lf` em tudo.
    with open(caminho, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo, lineterminator="\n")
        escritor.writerow(["bloco", "quando", "chave", "campo", "valor"])
        for captura in capturas:
            for campo, valor in (
                ("dispositivo", captura.dispositivo),
                ("amostras", captura.amostras),
                ("nao_zero", captura.nao_zero),
                ("pico", captura.pico),
                ("rms", f"{captura.rms:.2f}"),
                ("veredito", captura.veredito),
                ("erro", captura.erro),
            ):
                escritor.writerow(["E-5", quando, captura.rotulo, campo, valor])
        for janela in janelas:
            for no, quantos in sorted(janela.reports.items()):
                escritor.writerow(
                    [
                        "E-6",
                        janela.quando,
                        f"patamar{janela.patamar}/rodada{janela.rodada}/{no}",
                        "hz",
                        f"{janela.hz(no):.2f}",
                    ]
                )
                escritor.writerow(
                    [
                        "E-6",
                        janela.quando,
                        f"patamar{janela.patamar}/rodada{janela.rodada}/{no}",
                        "reports",
                        quantos,
                    ]
                )


def main() -> int:
    analisador = argparse.ArgumentParser(
        description="E-5 (o microfone do cabo capta?) e E-6 (a companhia custa taxa?).",
    )
    analisador.add_argument("--segundos", type=float, default=5.0, help="captura do E-5 (5 s)")
    analisador.add_argument("--dose-resposta", action="store_true", help="rodar também o E-6")
    analisador.add_argument("--janela", type=float, default=12.0, help="janela do E-6 (12 s)")
    analisador.add_argument("--rodadas", type=int, default=3, help="rodadas da escada (3)")
    analisador.add_argument("--csv", default="", help="onde escrever a tabela")
    argumentos = analisador.parse_args()

    print(
        cabecalho_do_instrumento(
            "microfone_no_cabo.py",
            "o microfone do CABO capta, e a companhia no controlador custa taxa?",
            bibliotecas=["subprocess", "wave", "array", "selectors"],
            escreve_no_aparelho=False,
            daemon_precisa_parar=False,
        )
    )
    quando = datetime.now().isoformat(timespec="milliseconds")
    print(f"  T0 (hora de parede) ... {quando}")
    print("  ferramenta externa .... arecord (" + (shutil.which("arecord") or "AUSENTE") + ")")
    print("  régua do E-5 .......... zeros exatos = não captou; qualquer não-zero = captou")
    print("  régua do E-6 .......... reports de entrada por segundo, por nó hidraw")

    aparelhos = descobrir_aparelhos()
    alvos = fisicos(aparelhos)
    print(f"\n  {censo_da_mesa(aparelhos)}")
    if not alvos:
        print(resumo("nenhum DualSense físico na mesa — nada a medir."))
        return 1

    placas = placas_de_dualsense(alvos)
    print("\n  AS PLACAS ALSA, AMARRADAS AO CONTROLE PELO DISPOSITIVO USB EM COMUM")
    print()
    print(
        tabela(
            ["placa", "id", "canais de captura", "controle", "transporte"],
            [
                [
                    f"card{p.numero}",
                    p.identificador,
                    str(p.canais),
                    mascarar(p.dono.mac) if p.dono else "NÃO CASOU",
                    p.dono.transporte if p.dono else "-",
                ]
                for p in placas
            ],
        )
    )
    do_radio = [a for a in alvos if a.transporte == RADIO]
    print()
    print(f"    {len(do_radio)} controle(s) no rádio, e NENHUM tem placa ALSA. Isso prova que a")
    print("    ROTA ALSA não existe no rádio — NÃO prova que o aparelho não capta por")
    print("    rádio: já está medido que capta, por HID e Opus, desde 25/07.")

    capturas: list[Captura] = []

    print("\n  O NEGATIVO DA RÉGUA — uma fonte que se SABE muda, pelo mesmo arecord")
    print()
    fonte_muda = _sink_suspenso_sem_dualsense()
    if not fonte_muda:
        print("    não achei sink suspenso não-DualSense: NEGATIVO NÃO FEITO.")
        print("    Sem ele, 'piso de ruído' fica sem contraprova nesta rodada.")
    else:
        negativo = gravar(
            "pulse", min(argumentos.segundos, 3.0), 2, "negativo", fonte_pulse=fonte_muda
        )
        capturas.append(negativo)
        print(f"    fonte ....... {fonte_muda}")
        print(
            f"    resultado ... {negativo.veredito}: {negativo.amostras} amostras, "
            f"{negativo.nao_zero} não-zero, pico {negativo.pico}"
        )
        if negativo.captou:
            print("    >> A RÉGUA ESTÁ QUEBRADA: a fonte muda produziu não-zero. Todo")
            print("    >> veredito 'PISO DE RUÍDO' abaixo é suspeito, e nada disto vira célula.")

    print("\n  E-5 — O MICROFONE DE CADA PLACA DO CABO")
    print()
    for placa in placas:
        rotulo = mascarar(placa.dono.mac) if placa.dono else f"card{placa.numero}"
        captura = gravar(placa.dispositivo, argumentos.segundos, placa.canais, rotulo)
        capturas.append(captura)
    do_cabo_com_placa = [c for c in capturas if c.rotulo != "negativo"]
    print(
        tabela(
            ["controle", "dispositivo", "amostras", "não-zero", "pico", "RMS", "veredito"],
            [
                [
                    c.rotulo,
                    c.dispositivo,
                    str(c.amostras),
                    str(c.nao_zero),
                    str(c.pico),
                    f"{c.rms:.1f}",
                    c.veredito if not c.erro else f"NÃO GRAVOU: {c.erro}",
                ]
                for c in do_cabo_com_placa
            ],
        )
    )

    print()
    print("  O QUE O APARELHO DIZ DO PRÓPRIO MICROFONE (status[1] do report de entrada)")
    print()
    print(
        tabela(
            ["controle", "transporte", "o aparelho diz"],
            [[mascarar(a.mac), a.transporte, estado_do_microfone(a)] for a in alvos],
        )
    )
    print()
    print("    Ressalva: `DS_STATUS1_MIC_MUTE` é DEFINIDO no driver e nunca LIDO por ele, e")
    print("    o bit vizinho `MIC_DETECT` é do JACK de 3,5 mm, não do microfone embutido.")
    print("    O que está acima é o byte com a leitura que o fonte sugere, não um veredito.")

    janelas: list[Janela] = []
    if argumentos.dose_resposta:
        do_cabo = [p for p in placas if p.dono and p.dono.transporte == CABO]
        print("\n  E-6 — A DOSE-RESPOSTA DA COMPANHIA (0, 1 e 2 microfones capturando)")
        print()
        print(f"    carga ....... {[p.dispositivo for p in do_cabo]}")
        print(f"    janela ...... {argumentos.janela:.0f} s por patamar")
        print(f"    rodadas ..... {argumentos.rodadas} (a escada sobe e desce, alternando)")
        print()
        janelas, falhas = dose_resposta(alvos, do_cabo, argumentos.janela, argumentos.rodadas)
        if falhas:
            print("\n    NÓS QUE NÃO ABRIRAM:")
            for falha in falhas:
                print(f"      - {falha}")

        print()
        linhas = []
        for aparelho in alvos:
            porp = _resumo_por_patamar(janelas, aparelho)
            linhas.append(
                [
                    mascarar(aparelho.mac),
                    aparelho.transporte,
                    *[
                        f"{porp[p][0]:.1f} ({porp[p][1]:.0f}-{porp[p][2]:.0f})"
                        if p in porp
                        else "-"
                        for p in (0, 1, 2)
                    ],
                    _veredito_da_dose(porp),
                ]
            )
        print(
            tabela(
                ["controle", "transporte", "patamar 0", "patamar 1", "patamar 2", "veredito"],
                linhas,
            )
        )
        print()
        print("    Cada célula é a MÉDIA das rodadas, e entre parênteses o mínimo e o")
        print("    máximo observados naquele patamar. Queda menor que a própria dispersão")
        print("    NÃO é dose-resposta — é ruído com sorte.")

    print(f"\n  T1 (hora de parede) ... {datetime.now().isoformat(timespec='milliseconds')}")
    if argumentos.csv:
        _escrever_csv(argumentos.csv, capturas, janelas, quando)
        print(f"  CSV ................... {argumentos.csv}")

    captaram = [c for c in do_cabo_com_placa if c.captou]
    mudos = [c for c in do_cabo_com_placa if not c.captou and not c.erro]
    partes = [
        f"E-5: {len(captaram)}/{len(do_cabo_com_placa)} microfone(s) do cabo com piso de ruído"
    ]
    if mudos:
        partes.append(f"{len(mudos)} com ZEROS EXATOS")
    if janelas:
        radio_vereditos = [
            _veredito_da_dose(_resumo_por_patamar(janelas, a))
            for a in alvos
            if a.transporte == RADIO
        ]
        houve = [v for v in radio_vereditos if v.startswith("QUEDA")]
        if houve:
            partes.append(f"E-6: dose-resposta em {len(houve)}/{len(radio_vereditos)} do rádio")
        else:
            partes.append(
                f"E-6: NENHUM dos {len(radio_vereditos)} do rádio caiu além da dispersão — "
                "a topologia compartilhada não bastou para produzir dano"
            )
    print(resumo(". ".join(partes)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
