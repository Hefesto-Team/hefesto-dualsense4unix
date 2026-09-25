#!/usr/bin/env python3
"""byte_no_fio.py — o byte SAI no fio? A escrita de cor, vista no ar, por MAC.

A PERGUNTA QUE ELE RESPONDE
----------------------------
*Quando alguém escreve em `multi_intensity`, o output report `0x31` chega a
sair pelo rádio para AQUELE controle — e, saindo, ele é igual ao que sai para
um controle são no mesmo instante?*

Ela existe por causa de um defeito perecível: em 15/08/2026 a casa teve, ao
vivo e ao mesmo tempo, um DualSense de rádio com a barra APAGADA que ignora as
escritas do kernel, e outro DualSense de rádio, também por rádio, que OBEDECE
ao mesmo comando. O `docs/data/mapa-controles.csv` registra o sintoma
("330 mil escritas ignoradas ao vivo") e registra também que *o que faz uma
conexão de rádio nascer travada continua SEM CAUSA ISOLADA* — porque ninguém
jamais comparou os bytes de um doente contra os de um são no mesmo instante.

Há exatamente três lugares onde o comando pode morrer, e este instrumento
existe para dizer em qual:

1. o kernel não monta nem envia para o doente (defeito do host);
2. o kernel envia igual para os dois, byte a byte (defeito do APARELHO);
3. o kernel envia DIFERENTE — `seq`, CRC, flags, tamanho (defeito nosso).

POR QUE `btmon`, E NÃO O `hidraw`
----------------------------------
O `hidraw` **não serve** para esta pergunta, e é importante dizer por quê antes
de alguém tentar: um `read()` em `/dev/hidrawN` devolve os relatórios de
ENTRADA. Os de saída que o kernel manda não voltam por ali. Ler o hidraw e não
ver a cor sair não prova nada — é o nó errado.

O `btmon` lê o socket `HCI_CHANNEL_MONITOR`, que é uma cópia de tudo que passa
entre o host e o controlador Bluetooth. É o último ponto do host antes do ar.
Se o quadro aparece ali com o `handle` daquele controle, o host fez a parte
dele; se não aparece, o comando morreu ANTES do ar.

O `btmon` é passivo: ele não fala com o adaptador, não abre conexão, não toca
em nenhum controle. Precisa de `CAP_NET_RAW`, e por isso este instrumento — e
só este trecho dele — roda `sudo -n btmon -w`. A captura nasce 0600 e sai
depois de lida (`CapturaDoFio`): se um controle reconecta no meio, ela leva a
chave de pareamento em claro.

A RÉGUA, DECLARADA
-------------------
**Um "byte no fio" = um pacote ACL, capturado no monitor HCI, cujo payload
L2CAP começa em `0xA2`** (HID-over-BT: `DATA` no sentido host->device) **e cujo
byte seguinte é `0x31`** (o output report do DualSense por rádio).

O sentido NÃO é lido do opcode do btsnoop — é lido do CONTEÚDO, do byte `0xA2`,
que só existe no sentido host->device. Isso é de propósito: o opcode é memória
minha sobre um formato, e o `0xA2` é o protocolo. A casa já pagou por um parser
de `btmon` que, em 12/08/2026, não venceu o formato.

O `handle` do ACL vira MAC pela tabela do kernel: cada conexão ACL é um device
`hciN:<handle>` em `/sys/class/bluetooth`, com o `address` ao lado. Onde essa
leitura não responder, o `hcitool con` (DEPRECIADO pelo BlueZ) é o plano B. O
mapa handle->MAC sai IMPRESSO no relatório, com a RÉGUA de onde saiu: sem ele,
dizer "o branco não recebeu" seria uma afirmação sem sujeito.

A MORDIDA (é isto que autoriza acreditar no número)
----------------------------------------------------
Este instrumento **não** acredita em si mesmo. Ele escreve, em cada controle,
uma cor MÁGICA — três bytes escolhidos a dedo, que ninguém mais na mesa usa — e
depois EXIGE reencontrar esses três bytes exatos, nos offsets 47/48/49 do
report `0x31` (`lightbar_red/green/blue`, conferidos em
`docs/protocol/driver-hid-playstation.md` §"off. abs. BT"), no `handle` daquele
controle.

Se a cor mágica do controle SÃO não for reencontrada, o instrumento se declara
QUEBRADO e não emite veredito: um parser que não acha o que ele mesmo acabou de
escrever não tem autoridade para dizer que o outro controle não recebeu nada. A
ausência só é evidência depois que a presença foi demonstrada no mesmo arquivo.

ELE ESCREVE — E SÓ NO SYSFS
----------------------------
Ele escreve em `/sys/class/leds/<inputN>:rgb:indicator/multi_intensity`, que é
exatamente o que o produto já faz o tempo todo. **Nenhum output report cru é
montado ou enviado por este arquivo** — quem monta o `0x31` é o kernel, e é
justamente o kernel que está sob observação. No fim ele devolve a cor anterior
de cada controle, lida antes de começar.

Ele **NÃO** desliga, reinicia nem faz power-off de controle nenhum: o power-off
CURA o defeito e destrói a evidência. Ele também não mexe em unit nenhuma.

O SEGUNDO OBSERVADOR (`--kprobe`)
----------------------------------
Opcional e independente do ar: um kprobe em `dualsense_send_output_report` do
`hid_playstation`, que conta quantas vezes o driver montou um report, por
JANELA DE TEMPO. Ele não sabe dizer para QUAL controle (o kprobe não carrega a
identidade do `hid_device`), então só serve para uma coisa — e é uma coisa que
importa: se o btmon vir zero quadros para um controle mas o kprobe contar
chamadas na janela em que só ele foi escrito, o comando morreu ENTRE o driver e
o ar. Sem isso, "não saiu" e "não foi montado" ficariam indistinguíveis.

USO
    sudo -v && .venv/bin/python scripts/ensaios/byte_no_fio.py
    .venv/bin/python scripts/ensaios/byte_no_fio.py --kprobe
    .venv/bin/python scripts/ensaios/byte_no_fio.py --bruto docs/data/ensaios-brutos/
"""

from __future__ import annotations

import argparse
import atexit
import contextlib
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comum import (
    RADIO,
    Aparelho,
    cabecalho_do_instrumento,
    descobrir_aparelhos,
    ler_texto,
    resumo,
    tabela,
)

from o_formato_btsnoop import (
    HID_BT_ENTRADA,
    HID_BT_SAIDA,
    NOME_DO_OFFSET,
    OFF_B,
    OFF_CRC,
    OFF_G,
    OFF_R,
    Quadro,
    descreve,
    ler_btsnoop,
    reports_de_saida,
)

# O FORMATO DO ARQUIVO MORA NO ``o_formato_btsnoop.py`` desde 25/09/2026: a
# lightbar o lê como root, e ele não pode puxar o ``comum``.

#: As cores mágicas. Escolhidas para não colidir com nada que o produto use
#: (o Hefesto trabalha com cores de jogador, e nenhuma delas é um degradê de
#: nibble repetido) e para serem reconhecíveis a olho num despejo hexadecimal.
MAGICA_A = (0x11, 0x22, 0x33)
MAGICA_B = (0x44, 0x55, 0x66)
MAGICA_C = (0x77, 0x88, 0x99)
MAGICA_D = (0xAA, 0xBB, 0xCC)

_RE_MAC = re.compile(r"\b([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})\b")


def mascarar(texto: str) -> str:
    """A máscara da casa: octetos 4 e 5 zerados. Nada de MAC real em arquivo."""

    def _troca(m: re.Match[str]) -> str:
        p = m.group(1).split(":")
        return ":".join([p[0], p[1], p[2], "00", "00", p[5]])

    return _RE_MAC.sub(_troca, texto)


# ---------------------------------------------------------------------------
# A captura: nasce fechada, é lida e sai
# ---------------------------------------------------------------------------

#: O comando que o root roda. A umask vai DENTRO dele porque o `sudo` junta a
#: nossa com a do sudoers, e um sudoers com `umask_override` impõe a dele (022):
#: fora daqui, a captura nasceria 0644 em algumas máquinas.
_BTMON_FECHADO = 'umask 077 && exec btmon -w "$1"'

#: O que o root roda no fim: a captura passa a ser de quem mede, e continua 0600.
_ENTREGAR_FECHADO = 'chown "$1" "$2" && chmod 0600 "$2"'


class CapturaDoFio:
    """Uma captura do ``btmon -w``, do nascimento à remoção. **Nasce fechada.**

    Se um controle reconecta durante a captura, o ``btmon`` grava a chave de
    pareamento em claro (o ``Link Key Request Reply``). Até 24/09/2026 a captura
    nascia 0644, do root, no ``/tmp``, e ficava lá
    (AS-CAPTURAS-DE-RADIO-NASCEM-FECHADAS-01). Agora ela:

    * nasce 0600 num diretório 0700 de quem mede — duas trancas, e nenhuma
      depende do sudoers da máquina;
    * no fim passa a ser de quem mede (``chown``), ainda 0600, e é lida sem root;
    * sai logo depois de lida, e :meth:`apagar` devolve a linha com o caminho,
      para a saída dizer onde ela esteve. Se o instrumento cair antes, o
      ``atexit`` apaga — e um ``SIGTERM`` ou um ``SIGHUP`` (o terminal que
      fecha) saem pelo mesmo caminho, em vez de matar o Python com o ``btmon``
      do root ainda gravando.

    O que deu errado no caminho (o ``sudo -n`` que não pôs o ``btmon`` de pé, a
    entrega que falhou) fica em :attr:`queixas`, para o relatório dizer «não
    medi» em vez de «não houve».

    Os dois instrumentos que capturam o fio (este e a captura armada) passam
    por aqui: duas cópias deste ciclo é como uma delas volta a nascer aberta.
    """

    def __init__(self, prefixo: str) -> None:
        self.diretorio = tempfile.mkdtemp(prefix=f"{prefixo}-")
        self.caminho = os.path.join(self.diretorio, f"{prefixo}.btsnoop")
        self.queixas: list[str] = []
        self._processo: subprocess.Popen[bytes] | None = None
        self._sinais: dict[int, Any] = {}
        self._linha = ""
        atexit.register(self.apagar)

    def comecar(self) -> None:
        """Põe o ``btmon -w`` de pé, como root, com a umask fechada."""
        self._sair_pelo_atexit_nos_sinais()
        self._processo = subprocess.Popen(
            ["sudo", "-n", "sh", "-c", _BTMON_FECHADO, "btmon", self.caminho],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _sair_pelo_atexit_nos_sinais(self) -> None:
        """``SIGTERM``/``SIGHUP`` viram ``SystemExit`` enquanto a captura vive.

        Só troca o sinal que está no padrão, e só no fio principal (o único
        onde o Python deixa trocar); o :meth:`apagar` devolve o que havia.
        """
        if threading.current_thread() is not threading.main_thread():
            return
        for sinal in (signal.SIGTERM, signal.SIGHUP):
            if signal.getsignal(sinal) is signal.SIG_DFL:
                self._sinais[sinal] = signal.signal(sinal, _sair_pelo_caminho_normal)

    def encerrar(self) -> None:
        """Para o ``btmon`` e entrega o arquivo a quem mede, ainda 0600."""
        processo, self._processo = self._processo, None
        if processo is None:
            return
        saiu_sozinho = processo.poll()
        if saiu_sozinho is not None:
            self.queixas.append(
                f"o `sudo -n btmon -w` saiu sozinho (rc={saiu_sozinho}) antes do fim "
                "da janela: o fio NÃO foi capturado. Sem credencial do sudo em cache? "
                "Rode `sudo -v` antes."
            )
        processo.terminate()
        try:
            processo.wait(timeout=5)
        except subprocess.TimeoutExpired:
            processo.kill()
            processo.wait()
        entrega = subprocess.run(
            ["sudo", "-n", "sh", "-c", _ENTREGAR_FECHADO, "sh",
             f"{os.getuid()}:{os.getgid()}", self.caminho],
            capture_output=True,
            check=False,
            timeout=20,
        )
        if entrega.returncode != 0 and os.path.lexists(self.caminho):
            self.queixas.append(
                f"a captura não foi entregue a quem mede (rc={entrega.returncode}): "
                "ela continua do root, 0600, e não se lê sem root."
            )

    def apagar(self) -> str:
        """Apaga a captura e o diretório dela; devolve a linha para a saída."""
        atexit.unregister(self.apagar)
        if self._linha:
            return self._linha
        self.encerrar()
        existia = os.path.lexists(self.caminho)
        try:
            os.unlink(self.caminho)
        except FileNotFoundError:
            pass
        except OSError:
            subprocess.run(["sudo", "-n", "rm", "-f", self.caminho],
                           capture_output=True, check=False, timeout=20)
        with contextlib.suppress(OSError):
            os.rmdir(self.diretorio)
        if threading.current_thread() is threading.main_thread():
            for sinal, antes in self._sinais.items():
                signal.signal(sinal, antes)
            self._sinais.clear()
        if os.path.lexists(self.caminho):
            self._linha = f"captura: {self.caminho}  NÃO SAIU — apague à mão (tem MAC real)"
        elif existia:
            self._linha = f"captura: {self.caminho}  (lida e apagada)"
        else:
            self._linha = f"captura: {self.caminho}  (o btmon não gravou nada ali)"
        return self._linha


def _sair_pelo_caminho_normal(numero: int, _quadro: Any) -> None:
    """O sinal vira ``SystemExit``: os ``finally`` e o ``atexit`` rodam.

    O segundo sinal não interrompe a limpeza que o primeiro disparou: os dois
    passam a ser ignorados até o :meth:`CapturaDoFio.apagar` devolver os de antes.
    """
    for sinal in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sinal, signal.SIG_IGN)
    raise SystemExit(128 + numero)


# ---------------------------------------------------------------------------
# A mesa: quem é quem, e qual handle é de quem
# ---------------------------------------------------------------------------


def _handles_do_sysfs(raiz: str = "/sys/class/bluetooth") -> dict[str, int]:
    """MAC -> handle ACL lido do sysfs: cada conexão vira `hciN:<handle>`.

    MIGRACAO-BLUEZ-DEPRECIADOS-01 (19/08/2026). O `hcitool` foi DEPRECIADO pela
    upstream do BlueZ e cada família de distro o mudou de pacote
    (`bluez-deprecated`, `bluez-deprecated-tools`). Onde ele não existe, este
    instrumento voltava um mapa VAZIO e o relatório saía com "SEM HANDLE" em
    todo mundo — sem dizer por quê.

    A fonte viva é o próprio kernel: o `hci_conn` registra um device
    `hciN:<handle>` (handle em decimal) sob /sys/class/bluetooth, com os
    atributos `address` e `type`. Nada de root, nada de pacote.

    NÃO CONFERIDO AO VIVO: em 19/08/2026 esta bancada não tinha adaptador BT
    ligado (`/sys/class/bluetooth` vazio), então a forma exata dos nomes e
    atributos veio do fonte do kernel, não de medição aqui. Por isso o
    `hcitool` continua como plano B e o relatório DECLARA de qual régua o mapa
    saiu — se a leitura do sysfs estiver errada, isso aparece impresso em vez
    de contaminar o veredito em silêncio.
    """
    mapa: dict[str, int] = {}
    try:
        nomes = os.listdir(raiz)
    except OSError:
        return mapa
    for nome in nomes:
        m = re.fullmatch(r"hci\d+:(\d+)", nome)
        if not m:
            continue
        try:
            with open(os.path.join(raiz, nome, "address"), encoding="utf-8") as fh:
                mac = fh.read().strip().lower()
        except OSError:
            continue
        if re.fullmatch(r"([0-9a-f]{2}:){5}[0-9a-f]{2}", mac):
            mapa[mac] = int(m.group(1))
    return mapa


def _handles_do_hcitool() -> dict[str, int]:
    """Plano B: o `hcitool con` depreciado, para não perder leitura em quem o tem."""
    try:
        saida = subprocess.run(
            ["sudo", "-n", "hcitool", "con"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    mapa: dict[str, int] = {}
    for linha in saida.splitlines():
        m = re.search(r"([0-9A-Fa-f:]{17})\s+handle\s+(\d+)", linha)
        if m:
            mapa[m.group(1).lower()] = int(m.group(2))
    return mapa


def handles_por_mac() -> tuple[dict[str, int], str]:
    """O mapa MAC -> handle ACL, e a RÉGUA de onde ele saiu.

    Ferramenta viva primeiro (sysfs do kernel), depreciada como plano B. A régua
    volta junto porque este instrumento declara a régua — regra desta casa
    desde que uma medição contra a biblioteca errada produziu alarme
    convincente e falso.
    """
    mapa = _handles_do_sysfs()
    if mapa:
        return mapa, "sysfs /sys/class/bluetooth"
    mapa = _handles_do_hcitool()
    if mapa:
        return mapa, "hcitool con (depreciado)"
    return {}, "NENHUMA — nem sysfs nem hcitool responderam"


def led_do_aparelho(ap: Aparelho) -> str:
    """O diretório `<inputN>:rgb:indicator` deste hidraw, ou "" se não houver.

    Vai pelo `dir_device` do hid, que é o pai comum do `hidraw` e do `leds/` —
    e não por adivinhação de número de input, que já trocou de controle nesta
    casa quando um deles reconectou.
    """
    dir_leds = os.path.join(ap.dir_device, "leds")
    if not os.path.isdir(dir_leds):
        return ""
    for nome in sorted(os.listdir(dir_leds)):
        if nome.endswith(":rgb:indicator"):
            return os.path.join(dir_leds, nome)
    return ""


def cor_atual(dir_led: str) -> str:
    return ler_texto(os.path.join(dir_led, "multi_intensity")).strip()


def escrever_cor(dir_led: str, rgb: tuple[int, int, int]) -> str:
    """Escreve no sysfs. Devolve "" se deu certo, ou a queixa do sistema.

    Isto é uma escrita no SYSFS, não no aparelho: quem monta o `0x31` é o
    kernel. É a única forma de provocar a escrita para observá-la, e é
    literalmente o que o produto faz o tempo todo.
    """
    alvo = os.path.join(dir_led, "multi_intensity")
    texto = f"{rgb[0]} {rgb[1]} {rgb[2]}"
    try:
        with open(alvo, "w", encoding="ascii") as arq:
            arq.write(texto)
        return ""
    except OSError as erro:
        return str(erro)


# ---------------------------------------------------------------------------
# O segundo observador: o kprobe
# ---------------------------------------------------------------------------

TRACEFS = "/sys/kernel/tracing"
SIMBOLO_KPROBE = "dualsense_send_output_report.isra.0"


def _sudo_sh(comando: str, *, checar: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sudo", "-n", "sh", "-c", comando],
        capture_output=True,
        text=True,
        check=checar,
        timeout=20,
    )


def kprobe_armar() -> str:
    """Arma o kprobe. Devolve "" se armou, ou a razão de não ter armado."""
    simbolo = SIMBOLO_KPROBE
    if simbolo not in ler_kallsyms():
        simbolo = "dualsense_send_output_report"
    r = _sudo_sh(
        f"echo 'p:hefesto_dsout {simbolo}' > {TRACEFS}/kprobe_events && "
        f"echo 1 > {TRACEFS}/events/kprobes/hefesto_dsout/enable"
    )
    if r.returncode != 0:
        return (r.stderr or r.stdout).strip() or f"falha ao armar em `{simbolo}`"
    return ""


def ler_kallsyms() -> str:
    return _sudo_sh("cat /proc/kallsyms").stdout


def kprobe_contador() -> int:
    """Quantas linhas do kprobe estão no buffer AGORA.

    É contagem de buffer, não contador de hardware: se o buffer der a volta, o
    número mente para MENOS. Por isso ele é zerado a cada janela e as janelas
    são curtas — e por isso ele é o SEGUNDO observador, não o primeiro.
    """
    texto = _sudo_sh(f"grep -c hefesto_dsout {TRACEFS}/trace").stdout.strip()
    return int(texto) if texto.isdigit() else 0


def kprobe_zerar() -> None:
    _sudo_sh(f"echo > {TRACEFS}/trace")


def kprobe_desarmar() -> None:
    _sudo_sh(
        f"echo 0 > {TRACEFS}/events/kprobes/hefesto_dsout/enable; "
        f"echo '-:hefesto_dsout' >> {TRACEFS}/kprobe_events; "
        f"echo > {TRACEFS}/trace"
    )


# ---------------------------------------------------------------------------
# O ensaio
# ---------------------------------------------------------------------------


class Alvo:
    def __init__(self, ap: Aparelho, dir_led: str) -> None:
        self.ap = ap
        self.dir_led = dir_led
        self.cor_antes = cor_atual(dir_led)
        self.handle = -1
        self.magicas: list[tuple[int, int, int]] = []


def fatia(quadros: list[Quadro], t0: float, t1: float) -> list[Quadro]:
    return [q for q in quadros if t0 <= q.ts <= t1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--segundos", type=float, default=1.2,
                    help="quanto tempo cada janela de escrita dura (padrão 1,2 s)")
    ap.add_argument("--kprobe", action="store_true",
                    help="arma o segundo observador, no kernel (precisa de sudo)")
    ap.add_argument("--bruto", default="",
                    help="diretório onde gravar o relatório bruto, com MAC mascarado")
    ap.add_argument("--mesma-cor", action="store_true",
                    help="o teste GÊMEO: a MESMA cor mágica nos dois, ao mesmo tempo. "
                         "É o que permite dizer 'os bytes são iguais' sem ressalva — "
                         "com cores diferentes, R/G/B diferem por desenho e a frase "
                         "ficaria mais fraca do que a medida permite.")
    args = ap.parse_args()

    print(
        cabecalho_do_instrumento(
            "byte_no_fio.py",
            "o output report 0x31 da cor SAI no ar para cada controle de rádio?",
            bibliotecas=["struct", "zlib"],
            escreve_no_aparelho=False,
        )
    )
    print("  ESCRITA ......... só no sysfs (`multi_intensity`), como o produto faz.")
    print("  NÃO faz .......... power-off, reconexão, restart de unit, report cru.")
    print("  privilégio ....... `sudo -n btmon -w` (passivo, CAP_NET_RAW)")
    print("=" * 78)

    aparelhos = [a for a in descobrir_aparelhos() if a.transporte == RADIO and not a.e_vpad]
    if len(aparelhos) < 1:
        print("\nNão há DualSense por rádio nesta mesa. Nada a medir.")
        return 2

    mapa, regua_do_mapa = handles_por_mac()
    alvos: list[Alvo] = []
    for a in aparelhos:
        dir_led = led_do_aparelho(a)
        if not dir_led:
            print(f"  !! {mascarar(a.apelido)} não tem `:rgb:indicator` no sysfs — fora")
            continue
        alvo = Alvo(a, dir_led)
        alvo.handle = mapa.get(a.mac.lower(), -1)
        alvos.append(alvo)

    print(f"\nA MESA DE RÁDIO, E O MAPA handle -> MAC (régua: {regua_do_mapa})")
    print(tabela(
        ["MAC", "hidraw", "handle ACL", "LED do sysfs", "cor agora"],
        [[mascarar(a.ap.mac), a.ap.hidraw, str(a.handle) if a.handle >= 0 else "SEM HANDLE",
          os.path.basename(a.dir_led), a.cor_antes] for a in alvos],
    ))
    if any(a.handle < 0 for a in alvos):
        print("\n  !! Sem handle não dá para atribuir quadro a controle. Veredito parcial.")

    # ---- captura ----------------------------------------------------------
    # Tem MAC real e pode ter a chave de pareamento: nasce 0600 e sai depois de
    # lida (`CapturaDoFio`). NÃO se versiona.
    captura = CapturaDoFio("byte-no-fio")
    kprobe_erro = "não pedido"
    if args.kprobe:
        kprobe_erro = kprobe_armar()
        if not kprobe_erro:
            kprobe_zerar()

    captura.comecar()
    time.sleep(1.0)  # o btmon precisa abrir o socket antes de a gente escrever

    janelas: list[tuple[str, Alvo, tuple[int, int, int], float, float, int]] = []
    magicas = [MAGICA_A, MAGICA_B, MAGICA_C, MAGICA_D]
    print("\nESCREVENDO (só sysfs), uma janela por controle, uma cor mágica por janela")
    for rodada in (0, 1):
        for i, alvo in enumerate(alvos):
            if args.mesma_cor:
                # No teste gêmeo a cor varia por RODADA, nunca por controle: os
                # dois recebem exatamente o mesmo valor na mesma janela.
                cor = magicas[rodada % len(magicas)]
            else:
                cor = magicas[(rodada * len(alvos) + i) % len(magicas)]
            if args.kprobe and not kprobe_erro:
                kprobe_zerar()
            k0 = 0
            t0 = time.time()
            # A escrita INSISTE durante a janela inteira. Não é redundância: o
            # daemon do Hefesto escreve cor nestes mesmos LEDs o tempo todo, e
            # uma escrita única pode ser sobrescrita antes de o `output_worker`
            # do driver rodar. Insistir garante que a cor mágica teve chance
            # real de sair — e se mesmo assim não sair, o silêncio é do rádio,
            # não da corrida com o daemon.
            erro = ""
            while time.time() - t0 < args.segundos:
                erro = escrever_cor(alvo.dir_led, cor) or erro
                time.sleep(0.05)
            t1 = time.time()
            k1 = kprobe_contador() if args.kprobe and not kprobe_erro else 0
            alvo.magicas.append(cor)
            janelas.append((
                f"r{rodada + 1}", alvo, cor, t0, t1, k1 - k0,
            ))
            print(f"  {mascarar(alvo.ap.mac)}  <- {cor[0]:3d} {cor[1]:3d} {cor[2]:3d}"
                  f"   ({'ok' if not erro else 'ERRO: ' + erro})")

    time.sleep(0.4)
    captura.encerrar()

    # ---- devolver a cor de antes -----------------------------------------
    print("\nDEVOLVENDO a cor que cada um tinha antes")
    for alvo in alvos:
        partes = alvo.cor_antes.split()
        if len(partes) == 3 and all(p.isdigit() for p in partes):
            escrever_cor(alvo.dir_led, (int(partes[0]), int(partes[1]), int(partes[2])))
            print(f"  {mascarar(alvo.ap.mac)}  <- {alvo.cor_antes}")

    if args.kprobe and not kprobe_erro:
        kprobe_desarmar()

    # ---- leitura ----------------------------------------------------------
    quadros, queixas = ler_btsnoop(captura.caminho)
    linha_da_captura = captura.apagar()
    queixas = [*captura.queixas, *queixas]
    saidas = reports_de_saida(quadros)
    entradas = [q for q in quadros if q.sentido == HID_BT_ENTRADA]

    linhas_saida: list[str] = []
    linhas_saida.append("\nO QUE A CAPTURA VIU (arquivo do `btmon -w`, lido por parser próprio)")
    linhas_saida.append(f"  quadros ACL com payload L2CAP ...... {len(quadros)}")
    linhas_saida.append(f"  DATA host->device (0xA2) ........... "
                        f"{sum(1 for q in quadros if q.sentido == HID_BT_SAIDA)}")
    linhas_saida.append(f"  ... destes, output report 0x31 ..... {len(saidas)}")
    linhas_saida.append(f"  DATA device->host (0xA1) ........... {len(entradas)}")
    for q in queixas:
        linhas_saida.append(f"  queixa do parser ................... {q}")
    if args.kprobe:
        linhas_saida.append(f"  kprobe ............................. "
                            f"{kprobe_erro or 'armado em ' + SIMBOLO_KPROBE}")

    por_handle: dict[int, list[Quadro]] = {}
    for q in saidas:
        por_handle.setdefault(q.handle, []).append(q)
    linhas_saida.append("\nOUTPUT REPORTS 0x31 POR HANDLE, NA CAPTURA INTEIRA")
    linhas_saida.append(tabela(
        ["handle", "de quem", "quadros 0x31"],
        [[str(h),
          mascarar(next((mascarar(a.ap.mac) for a in alvos if a.handle == h), f"handle {h}")),
          str(len(v))]
         for h, v in sorted(por_handle.items())]
        + [[str(a.handle), mascarar(a.ap.mac), "0"] for a in alvos
           if a.handle not in por_handle],
    ))

    # ---- a mordida: reencontrar a cor mágica ------------------------------
    linhas_saida.append("\nA MORDIDA — a cor mágica que EU escrevi aparece no ar, "
                        "nos offsets 47/48/49?")
    achados: list[list[str]] = []
    mordeu: dict[str, bool] = {}
    exemplares: dict[str, bytes] = {}
    for rot, alvo, cor, _t0, _t1, dk in janelas:
        # De propósito, a busca é na CAPTURA INTEIRA e não na janela de tempo:
        # a cor mágica é única por janela, então ela mesma é o marcador. Assim
        # o veredito não depende de eu ter acertado a época do btsnoop.
        na_janela = [q for q in saidas if q.handle == alvo.handle]
        casados = [q for q in na_janela
                   if len(q.corpo) > OFF_B + 1
                   and (q.corpo[1 + OFF_R], q.corpo[1 + OFF_G], q.corpo[1 + OFF_B]) == cor]
        chave = alvo.ap.mac
        mordeu[chave] = mordeu.get(chave, False) or bool(casados)
        if casados and chave not in exemplares:
            exemplares[chave] = casados[0].corpo[1:]
        achados.append([
            rot, mascarar(alvo.ap.mac), str(alvo.handle),
            f"{cor[0]:02x} {cor[1]:02x} {cor[2]:02x}",
            str(len(na_janela)), str(len(casados)),
            str(dk) if args.kprobe and not kprobe_erro else "-",
        ])
    linhas_saida.append(tabela(
        ["rodada", "MAC", "handle", "cor mágica (hex)", "0x31 no handle",
         "com a cor mágica", "kprobe"],
        achados,
    ))

    # ---- os bytes, lado a lado -------------------------------------------
    if exemplares:
        linhas_saida.append("\nOS BYTES — um exemplar do 0x31 de cada controle "
                            "que a cor mágica identificou")
        linhas_saida.append(tabela(
            ["MAC", "seq_tag", "tag", "vflag0", "vflag1", "vflag2",
             "lb_setup", "brilho", "R G B", "tam", "CRC"],
            [[mascarar(mac), *descreve(rep)] for mac, rep in sorted(exemplares.items())],
        ))
        for mac, rep in sorted(exemplares.items()):
            linhas_saida.append(f"\n  {mascarar(mac)}  0x31 inteiro, {len(rep)} bytes:")
            for i in range(0, len(rep), 16):
                linhas_saida.append(f"    {i:3d}: " + " ".join(f"{c:02x}" for c in rep[i:i + 16]))

    # ---- o diff byte a byte ----------------------------------------------
    if len(exemplares) == 2:
        (mac_a, rep_a), (mac_b, rep_b) = sorted(exemplares.items())
        difs = [i for i in range(min(len(rep_a), len(rep_b))) if rep_a[i] != rep_b[i]]
        linhas_saida.append(
            f"\nO DIFF BYTE A BYTE — {mascarar(mac_a)} contra {mascarar(mac_b)}")
        linhas_saida.append(f"  tamanhos: {len(rep_a)} e {len(rep_b)}")
        if not difs:
            linhas_saida.append("  os 78 bytes são IDÊNTICOS. Nenhuma diferença.")
        else:
            linhas_saida.append(tabela(
                ["offset", "campo", mascarar(mac_a), mascarar(mac_b)],
                [[str(i),
                  NOME_DO_OFFSET.get(i, "crc32" if i >= OFF_CRC else "reservado"),
                  f"0x{rep_a[i]:02x}", f"0x{rep_b[i]:02x}"] for i in difs],
            ))

    # ---- veredito ---------------------------------------------------------
    sao = [a for a in alvos if mordeu.get(a.ap.mac)]
    mudo = [a for a in alvos if not mordeu.get(a.ap.mac)]
    if not sao:
        veredito = (
            "INSTRUMENTO QUEBRADO — não reencontrei a cor mágica de NENHUM controle. "
            "Sem demonstrar a presença, a ausência não é evidência. Sem veredito."
        )
    elif not mudo:
        veredito = (
            f"O BYTE SAI NO FIO PARA TODOS OS {len(alvos)}. Nenhum comando morreu no host: "
            "compare os bytes acima — se forem iguais, o réu é o aparelho."
        )
    else:
        quem = ", ".join(mascarar(a.ap.mac) for a in mudo)
        veredito = (
            f"O BYTE NÃO SAI NO FIO para {quem}, e SAI para "
            f"{', '.join(mascarar(a.ap.mac) for a in sao)} na mesma captura. "
            "O comando morre NO HOST, antes do ar."
        )

    texto = "\n".join(linhas_saida)
    print(texto)
    print(resumo(veredito))

    if args.bruto:
        os.makedirs(args.bruto, exist_ok=True)
        carimbo = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        destino = os.path.join(args.bruto, f"{carimbo}-byte-no-fio.txt")
        with open(destino, "w", encoding="utf-8") as arq:
            arq.write(mascarar(texto) + "\n\nRESUMO: " + mascarar(veredito) + "\n")
        print(f"bruto: {destino}")
    print(linha_da_captura)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
