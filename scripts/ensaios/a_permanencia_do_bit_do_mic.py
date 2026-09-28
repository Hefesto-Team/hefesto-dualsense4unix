#!/usr/bin/env python3
"""a_permanencia_do_bit_do_mic.py — quanto tempo o `MicMuted` FICA em cada valor.

O NÚMERO QUE FALTA PARA CURAR O CORTE DE 1,1 s
-----------------------------------------------
Medido em 10/09/2026: o microfone por rádio capta ~1,1 s e para. A causa está
com endereço, e é nossa:

1. com o mic no ar, o firmware **oscila** o bit `MicMuted` a ~16,7 Hz — isso a
   casa já mediu e registrou em `integrations/dualsense_bt_audio.py`
   (``~100 transições em 6 s``; sem o `0x32`, ZERO em 1183 reports);
2. `daemon/subsystems/mic_da_mesa.py:143` engole as transições do primeiro
   segundo como repique (``MIC_SOSSEGO_S = 1.0``);
3. **a primeira depois de 1,0 s é ACEITA** e lida como o dedo dela no botão;
4. o daemon desliga o microfone — e sem o `0x32` o firmware para de oscilar,
   então nunca mais nasce borda e o mic não volta.

No journal dela, hoje às 09:42, a assinatura exata::

    mic_da_mesa_borda    mudo=True  repiques_engolidos=15  seq=1
    bt_mic_palavra_dela  ligado=False

A CURA é exigir SUSTENTAÇÃO da borda: o dedo dela TRAVA o valor (o kernel faz
latch), o gating do firmware não. **Mas a janela de sustentação precisa ficar
acima da permanência MÁXIMA do gating, e ninguém mediu a distribuição** — só a
média (~60 ms, derivada da taxa). Uma janela chutada abaixo do máximo deixa
passar a borda falsa de vez em quando, e o defeito volta intermitente, que é
pior do que agora.

**É esse máximo que este instrumento mede.**

O QUE ELE FAZ, E O QUE NÃO FAZ
-------------------------------
Ele **lê** o `hidrawN` do controle e cronometra cada permanência do bit 2 do
byte 55 (`STATUS_MIC_MUDO`). **Não escreve um byte** e não abre janela.

Ele **não liga o microfone** — quem liga é o daemon, quando ela aperta o botão
do plástico. Cada aperto dá ~1,1 s de gating antes de o defeito o derrubar, e
~17 permanências. Aperte umas cinco vezes durante a corrida.

QUEM VIRA O BIT SEM A MÃO (28/09/2026, O-BOTAO-DO-MIC-SO-OBEDECE-A-MAO-01)
-------------------------------------------------------------------------
A sustentação de 300 ms saiu do produto: o gesto passou a ser o BOTÃO
(`buttons[2]` bit 2), e o bit de mudo só diz o que o firmware segura. Mas na
sessão dela de 28/09 o bit do branco virou três vezes sem ela apertar, e quem
o escreveu ninguém mediu. Por isso a corrida também conta, pelo MESMO extrator
do produto (`core/physical_report_reader.extract_estado_do_mic`, com CRC e sem
o quadro de áudio), cada aperto e cada virada do bit de mudo que aconteceu com
o botão parado — com a hora do relógio, para casar com o diário do daemon.

USO
    a_permanencia_do_bit_do_mic.py --listar          # só diz o que leria
    a_permanencia_do_bit_do_mic.py --segundos 60     # mede, e ela aperta o mic
    a_permanencia_do_bit_do_mic.py --no hidraw5 --segundos 600
                                  # com mais de um DualSense no rádio, diga qual
"""

from __future__ import annotations

import argparse
import os
import select
import statistics
import sys
import time

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)
_SRC = os.path.join(os.path.dirname(os.path.dirname(_AQUI)), "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from comum import (
    RADIO,
    abrir_no_hidraw,
    cabecalho_do_instrumento,
    descobrir_aparelhos,
    fisicos,
    resumo,
)

#: O botão e o `status[1]` do MESMO report, pelo extrator do produto.
from hefesto_dualsense4unix.core.physical_report_reader import (
    extract_estado_do_mic,
)

#: O byte de status e o bit, do dono único da metade de ENTRADA.
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
    STATUS_MIC_MUDO,
)

#: Onde o `status1` mora no report `0x31` de ENTRADA por rádio. O número vem do
#: `hid-playstation` e do dono desta casa — não é digitado por adivinhação.
OFFSET_STATUS = 55

#: Um report de entrada por rádio cabe folgado nisto.
TAMANHO_DA_LEITURA = 600

#: Quanto tempo depois do dedo uma virada do bit de mudo ainda é do aperto. Um
#: aperto move o bit até duas vezes: o kernel escreve logo depois de ler o
#: report, e o ato do daemon pode escrever de novo até confirmar — o teto dele
#: é `hotkey.CONFIRMACAO_DO_MUDO_S`, três segundos. O que vira fora disso, com
#: o botão parado, foi escrito por outro.
JANELA_DO_DEDO_S = 3.0


class QuemVirou:
    """Os apertos e as viradas do bit de mudo SEM a mão, com a hora de cada um.

    Lê só reports de ESTADO íntegros (`extract_estado_do_mic`): o quadro de
    áudio do rádio e o report com CRC ruim não dizem nada sobre o dedo.
    """

    def __init__(self) -> None:
        self.apertos: list[str] = []
        self.sem_mao: list[str] = []
        self._botao: bool | None = None
        self._mudo: bool | None = None
        self._dedo_em = float("-inf")

    def ler(self, dados: bytes, agora: float) -> None:
        lido = extract_estado_do_mic(dados)
        if lido is None:
            return
        status, botao = lido
        mudo = bool(status & STATUS_MIC_MUDO)
        if botao:
            if self._botao is False:
                self.apertos.append(f"{_hora()}  aperto (o bit segurava mudo={mudo})")
            self._dedo_em = agora
        self._botao = botao
        if self._mudo is not None and mudo != self._mudo and (
            agora - self._dedo_em
        ) > JANELA_DO_DEDO_S:
            self.sem_mao.append(f"{_hora()}  o bit virou para mudo={mudo} SEM A MÃO")
        self._mudo = mudo


def _hora() -> str:
    """A hora do relógio, no formato do diário do daemon."""
    agora = time.time()
    return time.strftime("%H:%M:%S", time.localtime(agora)) + f".{int(agora * 1000) % 1000:03d}"


def permanencias(
    fd: int, segundos: float, quem: QuemVirou | None = None
) -> tuple[list[float], list[float], int]:
    """`(permanências de MUDO, de NÃO-MUDO, reports lidos)`, em segundos."""
    mudo_agora: bool | None = None
    desde = 0.0
    em_mudo: list[float] = []
    em_claro: list[float] = []
    lidos = 0
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        prontos, _, _ = select.select([fd], [], [], 0.5)
        if not prontos:
            continue
        try:
            dados = os.read(fd, TAMANHO_DA_LEITURA)
        except OSError:
            break
        if len(dados) <= OFFSET_STATUS:
            continue
        lidos += 1
        mudo = bool(dados[OFFSET_STATUS] & STATUS_MIC_MUDO)
        agora = time.monotonic()
        if quem is not None:
            quem.ler(dados, agora)
        if mudo_agora is None:
            mudo_agora, desde = mudo, agora
            continue
        if mudo != mudo_agora:
            (em_mudo if mudo_agora else em_claro).append(agora - desde)
            mudo_agora, desde = mudo, agora
    return em_mudo, em_claro, lidos


def descrever(nome: str, amostras: list[float]) -> list[str]:
    """As linhas de uma distribuição — e o MÁXIMO em destaque, que é o alvo."""
    if not amostras:
        return [f"  {nome}: nenhuma transição — o gating não aconteceu"]
    ms = sorted(v * 1000.0 for v in amostras)
    p95 = ms[min(len(ms) - 1, int(len(ms) * 0.95))]
    return [
        f"  {nome}: {len(ms)} permanência(s)",
        f"    mediana {statistics.median(ms):7.1f} ms",
        f"    média   {statistics.fmean(ms):7.1f} ms",
        f"    p95     {p95:7.1f} ms",
        f"    MÁXIMO  {ms[-1]:7.1f} ms   <- a janela tem de ficar ACIMA disto",
    ]


def o_controle_no_radio(no: str | None = None):  # o tipo é o `Aparelho` de `comum`
    """O DualSense do rádio. Um só, ou o `no` que ela disse: o bit é de um."""
    reais = [a for a in fisicos(descobrir_aparelhos()) if a.transporte == RADIO]
    if no:
        nome = os.path.basename(no)
        escolhido = [a for a in reais if a.hidraw == nome]
        return escolhido[0] if escolhido else None
    return reais[0] if len(reais) == 1 else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--segundos", type=float, default=60.0)
    ap.add_argument("--listar", action="store_true", help="só diz o que leria")
    ap.add_argument(
        "--no",
        default=None,
        help="o hidrawN do DualSense do rádio a ler, quando há mais de um",
    )
    args = ap.parse_args()

    print(
        cabecalho_do_instrumento(
            "a_permanencia_do_bit_do_mic",
            "quanto tempo o `MicMuted` fica em cada valor com o mic no ar?",
            bibliotecas=["nenhuma — leitura pura de hidraw"],
            escreve_no_aparelho=False,
        )
    )

    alvo = o_controle_no_radio(args.no)
    if alvo is None:
        print(resumo(
            "preciso de EXATAMENTE UM DualSense no rádio, ou do `--no hidrawN` "
            "de um deles. Com dois e sem o nó, não se sabe de qual controle é o "
            "bit que oscila."))
        return 1
    print(f"O CONTROLE: {alvo.hidraw}  ({alvo.transporte})")

    if args.listar:
        print(resumo("leitura pura — nenhum nó aberto nesta corrida."))
        return 0

    # O CAMINHO, não o `Aparelho` — `abrir_no_hidraw` recebe `str` e devolve um
    # `NoAberto` que carrega o fd E a porta usada.
    no = abrir_no_hidraw(f"/dev/{alvo.hidraw}", escrita=False)
    if no.fd is None:
        print(resumo(f"não abri o nó: {no.linha_de_relatorio}"))
        return 1
    print(f"  {no.linha_de_relatorio}")
    fd = no.fd

    print(
        f"\n>>> MEDINDO {args.segundos:g} s.\n"
        ">>> APERTE O BOTÃO DO MICROFONE do controle umas cinco vezes durante\n"
        ">>> a corrida. Cada aperto dá ~1,1 s de gating antes de o defeito o\n"
        ">>> derrubar — e é nesse trecho que o bit oscila.",
        flush=True,
    )
    quem = QuemVirou()
    try:
        em_mudo, em_claro, lidos = permanencias(fd, args.segundos, quem)
    finally:
        os.close(fd)

    print(f"\n{lidos} report(s) de entrada lidos em {args.segundos:g} s")
    print(f"\nO DEDO E O BIT ({len(quem.apertos)} aperto(s), "
          f"{len(quem.sem_mao)} virada(s) do bit sem a mão):")
    for linha in sorted(quem.apertos + quem.sem_mao):
        print(f"  {linha}")
    print("\nPERMANÊNCIA DO BIT `MicMuted`:")
    for linha in descrever("MUDO=True ", em_mudo):
        print(linha)
    for linha in descrever("MUDO=False", em_claro):
        print(linha)

    todas = em_mudo + em_claro
    if not todas:
        print(resumo(
            "ZERO transições. Ou o microfone não subiu durante a corrida (ela "
            "apertou o botão?), ou o gating não acontece nesta configuração — "
            "e a segunda resposta valeria tanto quanto a primeira."))
        return 2

    # O MÁXIMO NÃO É O ALVO — CURA DE 10/09/2026, na primeira corrida de
    # verdade. Este resumo dizia "a janela tem de ficar acima do MÁXIMO" e
    # sugeriu **23,4 segundos**, um número absurdo. A causa: o máximo mede o
    # bit PARADO (o microfone desligado, o valor estável por 11,7 s) e não o
    # gating. Misturar repouso com oscilação num percentil só é medir duas
    # populações como se fossem uma.
    #
    # O que decide é: **com a janela X, quantas permanências do GATING
    # sobreviveriam e virariam borda falsa?** É essa a pergunta, e o número
    # abaixo a responde diretamente para cada candidata.
    ms = sorted(v * 1000.0 for v in todas)
    print("\nQUANTAS PERMANÊNCIAS SOBREVIVEM A CADA JANELA:")
    print("  (cada sobrevivente é uma BORDA FALSA em potencial)")
    # O produto não usa janela nenhuma desde 28/09/2026: conta o botão. A
    # tabela fica pela pergunta de 10/09, que ainda mede o gating do driver.
    for janela_ms in (50, 100, 150, 200, 250, 300, 400, 500):
        passam = sum(1 for v in ms if v >= janela_ms)
        print(f"    {janela_ms:>4} ms: {passam:>5} de {len(ms)} "
              f"({100.0 * passam / len(ms):5.2f}%)")

    # O CASO FELIZ QUEBRAVA ESTE RESUMO — cura de 10/09/2026, na corrida que
    # PROVOU a cura do driver. Sem gating não há permanência curta, e
    # `statistics.median([])` levanta. O instrumento morria exatamente na
    # corrida que ele existe para celebrar: um `Traceback` no lugar do número.
    curtas = [v for v in ms if v < 1000.0]
    if not curtas:
        print(resumo(
            f"NENHUMA permanência abaixo de 1 s em {len(todas)} transição(ões): "
            "**o gating não está acontecendo**. Com o microfone no ar, isto é o "
            "resultado que a cura do driver (MIC-NAO-E-BOTAO-01) produz — antes "
            "dela esta mesma corrida colhia mais de mil, com mediana de 6 ms. "
            "Se o microfone NÃO estava no ar, o resultado não diz nada."))
        return 0

    print(resumo(
        f"{len(todas)} permanências, {len(curtas)} delas abaixo de 1 s — estas "
        f"são o GATING (mediana {statistics.median(curtas):.0f} ms). As demais "
        "são o bit PARADO, e não entram na conta. "
        "A janela certa é a menor que zere a coluna acima sem atrasar o gesto "
        "dela — e se nenhuma zerar, a resposta não é aumentar a janela: é que "
        "a sustentação é PALIATIVO, e a cura está no driver "
        "(MIC-NAO-E-BOTAO-01)."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
