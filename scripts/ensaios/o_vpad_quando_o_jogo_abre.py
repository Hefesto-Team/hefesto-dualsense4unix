#!/usr/bin/env python3
"""o_vpad_quando_o_jogo_abre.py — o vpad MORRE, ou CONGELA? Segundo a segundo.

A PERGUNTA QUE ELE RESPONDE
----------------------------
*Quando o jogo abre, o que acontece com o controle virtual?* — e a resposta tem
de separar **duas coisas que os relatos de 16/08 misturaram**, porque elas têm
curas diferentes:

- **MORRE**  — o nó do vpad some (`gamepad_emulation_stopped`, `/dev/hidrawN`
  desaparece). O jogo, que já enumerou aquele nó, fica com um descritor órfão.
- **CONGELA** — o nó continua vivo e emitindo na cadência normal, e o CONTEÚDO
  para: os eixos ficam no valor de repouso. Foi o que o par de 17/08 00h20
  mediu (1573 reports, `LX` travado em 129) e o que o item 1 do
  O-QUE-FICOU-ABERTO-01 já tinha registrado no rádio (396 reports, `LX` em 128).

Contagem de reports **não** distingue as duas: um vpad que morreu e renasceu
emite tanto quanto um que nunca parou. Só a linha do tempo distingue — e é ela
que este instrumento imprime.

O QUE ELE MEDE
---------------
Uma linha por segundo, com quatro colunas que só fazem sentido juntas:

    t    vpad          reports  pares  perfil        o que o daemon fez
    12s  /dev/hidraw4      63     41   Dont Scream   -
    13s  /dev/hidraw4      61     38   Dont Scream   -
    14s  (nenhum)           0      0   Navegação     emulação PAROU
    15s  /dev/hidraw4      58      1   Dont Scream   vpad NASCEU

`pares` é a contagem de pares `(LX, LY)` **distintos** naquele segundo. É a
régua do movimento, e não a do tráfego: um vpad congelado dá `reports` alto e
`pares` = 1. Um vpad morto dá zero nos dois.

O QUE ELE NÃO MEDE
-------------------
**Não mede se o JOGO usa o que chega** — este é o andar do transporte, e o
prontuário por jogo é quem recusa dizer "funciona". Não mede latência.

A ARMADILHA QUE ELE EVITA
--------------------------
**Guardar o caminho do nó.** O vpad renasce com outro número, e um instrumento
que fixa `/dev/hidraw4` na primeira resolução mede "morreu" para sempre depois
do primeiro ciclo — exatamente o erro que o `descobrir_aparelhos()` do
`comum.py` existe para impedir. Aqui o nó é **redescoberto a cada segundo**, e
a coluna `vpad` imprime o nó de verdade daquele segundo.

E a de 16/08, que custou um diagnóstico errado: **um ensaio mede UM gesto**.
O gesto aqui é *um só* — mexer o analógico esquerdo, sem parar, do começo ao
fim. Quem parar de mexer para abrir o jogo produz `pares=1` por conta própria e
lê congelamento onde só houve mão parada. Por isso o instrumento **pede o gesto
antes de começar** e imprime, no resumo, quantos segundos tiveram movimento.

USO
    .venv/bin/python scripts/ensaios/o_vpad_quando_o_jogo_abre.py
    .venv/bin/python scripts/ensaios/o_vpad_quando_o_jogo_abre.py --segundos 120
"""

from __future__ import annotations

import argparse
import os
import re
import select
import subprocess
import sys
import threading
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comum import (  # noqa: E402
    abrir_no_hidraw,
    cabecalho_do_instrumento,
    descobrir_aparelhos,
    diagnostico_de_acesso,
    resumo,
    tabela,
    vpads,
)

#: Buffer folgado: um `read()` de hidraw devolve UM relatório, e o maior desta
#: família é o `0x31` do Bluetooth, com 78 bytes.
BUF = 128

#: Onde o primeiro eixo (`LX`) começa, por report ID. O vpad forja `BUS_USB` no
#: `UHID_CREATE2` (vira `0x01`), mas a máscara pode mudar — então os dois.
_BASE = {0x01: 1, 0x31: 2}

#: Os eventos do journal que mudam o veredito, e o rótulo curto de cada um.
#: Tudo o que não estiver aqui é ruído para ESTA pergunta e não entra na linha.
_EVENTOS = (
    ("uhid_device_created", "vpad NASCEU"),
    ("gamepad_emulation_stopped", "emulação PAROU"),
    ("gamepad_emulation_started", "emulação SUBIU"),
    ("gamepad_controller_grab", "grab"),
    ("backend_hotplug_reconcile", "reconcile"),
    ("motion_reader_started", "leitor de movimento SUBIU"),
    ("motion_reader_stopped", "leitor de movimento PAROU"),
    ("motion_reader_open_failed", "leitor de movimento FALHOU"),
    ("controller_disconnected", "controle DESCONECTOU"),
    ("state_stale_neutral_warning", "estado ESTAGNADO"),
)

_RE_PERFIL = re.compile(r"profile_activated\s+name=('([^']*)'|(\S+))")


def _perfil_agora() -> str:
    """O perfil ativo AGORA, para a primeira linha não sair em branco.

    Uma chamada ao IPC, no começo e só no começo: dali em diante quem manda é o
    `profile_activated` do log, que é a fonte de verdade sobre a TROCA. Ler o
    IPC a cada segundo seria o instrumento perguntando ao produto o que ele já
    está gritando no log — e mais uma coisa disputando o socket durante a
    medição.
    """
    try:
        saida = subprocess.run(
            [sys.executable, "-m", "hefesto_dualsense4unix", "status"],
            capture_output=True, text=True, timeout=8,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return "(não sei)"
    for linha in saida.splitlines():
        if "active_profile" in linha:
            partes = [p.strip() for p in linha.strip("│ ").split("│")]
            if len(partes) >= 2:
                return partes[1]
    return "(não sei)"


class Janela:
    """O que aconteceu em cada segundo. Um lock, porque três threads escrevem."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.reports: dict[int, int] = defaultdict(int)
        self.pares: dict[int, set[tuple[int, int]]] = defaultdict(set)
        self.no: dict[int, str] = {}
        self.eventos: dict[int, list[str]] = defaultdict(list)
        self.perfil = _perfil_agora()
        self.perfil_por_seg: dict[int, str] = {}

    def report(self, seg: int, no: str, lx: int, ly: int) -> None:
        with self.lock:
            self.reports[seg] += 1
            self.pares[seg].add((lx, ly))
            self.no[seg] = no

    def evento(self, seg: int, rotulo: str) -> None:
        with self.lock:
            if rotulo not in self.eventos[seg]:
                self.eventos[seg].append(rotulo)

    def trocou_perfil(self, nome: str) -> None:
        with self.lock:
            self.perfil = nome

    def fecha(self, seg: int) -> tuple[str, int, int, str, str]:
        with self.lock:
            self.perfil_por_seg[seg] = self.perfil
            return (
                self.no.get(seg, "(nenhum)"),
                self.reports.get(seg, 0),
                len(self.pares.get(seg, ())),
                self.perfil,
                ", ".join(self.eventos.get(seg, ())) or "-",
            )


def _le_o_vpad(janela: Janela, t0: float, ate: float, parar: threading.Event) -> None:
    """Lê o vpad e redescobre o nó a cada segundo. Nunca guarda o caminho."""
    aberto: tuple[str, object] | None = None
    proxima_busca = 0.0
    while not parar.is_set() and time.monotonic() < ate:
        agora = time.monotonic()
        if aberto is None and agora >= proxima_busca:
            proxima_busca = agora + 1.0
            achados = vpads(descobrir_aparelhos())
            if achados:
                caminho = achados[0].caminho_hidraw
                try:
                    aberto = (caminho, abrir_no_hidraw(caminho, escrita=False))
                except OSError:
                    aberto = None
        if aberto is None:
            time.sleep(0.05)
            continue
        caminho, no = aberto
        try:
            pronto, _, _ = select.select([no.fd], [], [], 0.2)
            if not pronto:
                # Nó sumiu debaixo de nós? `stat` é barato e é a única checagem
                # que separa "nada a ler" de "o vpad morreu".
                if not os.path.exists(caminho):
                    raise OSError(2, "o nó sumiu")
                continue
            dados = os.read(no.fd, BUF)
        except OSError:
            try:
                no.close()
            except Exception:  # noqa: BLE001 — fechar não pode derrubar a medição
                pass
            aberto = None
            continue
        base = _BASE.get(dados[0] if dados else -1)
        if base is None or len(dados) < base + 2:
            continue
        janela.report(int(time.monotonic() - t0), caminho, dados[base], dados[base + 1])


def _segue_o_journal(janela: Janela, t0: float, parar: threading.Event) -> None:
    """Segue o log do daemon ao vivo. Só LÊ — não pede nada ao daemon."""
    proc = subprocess.Popen(
        [
            "journalctl", "--user", "-u", "hefesto-dualsense4unix",
            "-f", "-n", "0", "-o", "cat",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        assert proc.stdout is not None
        for linha in proc.stdout:
            if parar.is_set():
                break
            seg = int(time.monotonic() - t0)
            casou = _RE_PERFIL.search(linha)
            if casou:
                janela.trocou_perfil(casou.group(2) or casou.group(3))
                janela.evento(seg, f"perfil → {casou.group(2) or casou.group(3)}")
            for chave, rotulo in _EVENTOS:
                if chave in linha:
                    if chave == "gamepad_controller_grab":
                        rotulo = "grab " + ("PEGOU" if "grab=True" in linha else "SOLTOU")
                    janela.evento(seg, rotulo)
    finally:
        proc.terminate()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--segundos", type=int, default=90, help="duração (padrão: 90)")
    args = ap.parse_args()

    print(
        cabecalho_do_instrumento(
            "o_vpad_quando_o_jogo_abre.py",
            "quando o jogo abre, o vpad MORRE ou CONGELA?",
            bibliotecas=[],
            escreve_no_aparelho=False,
            daemon_precisa_parar=False,
        )
    )

    achados = vpads(descobrir_aparelhos())
    if achados:
        print(f"\n  vpad agora: {achados[0].caminho_hidraw}")
        print(f"  acesso ...: {diagnostico_de_acesso(achados[0].caminho_hidraw)}")
    else:
        print("\n  vpad agora: NENHUM — a emulação está desligada neste instante.")
        print("  (não é impedimento: o instrumento espera ele nascer e registra a hora)")

    print(
        "\n  O GESTO, e é UM SÓ: mexa o analógico ESQUERDO em círculos, sem parar,\n"
        "  do primeiro segundo ao último. Não pare para abrir o jogo — abra com a\n"
        "  outra mão. Mão parada produz `pares=1` sozinha, e isso se lê como\n"
        "  congelamento que não houve.\n"
    )
    print(f"  Medindo por {args.segundos}s. Comece a mexer AGORA.\n")

    janela = Janela()
    t0 = time.monotonic()
    parar = threading.Event()
    ate = t0 + args.segundos
    threads = [
        threading.Thread(target=_le_o_vpad, args=(janela, t0, ate, parar), daemon=True),
        threading.Thread(target=_segue_o_journal, args=(janela, t0, parar), daemon=True),
    ]
    for t in threads:
        t.start()

    linhas: list[list[str]] = []
    print(f"  {'t':>4}  {'vpad':<14} {'reports':>7} {'pares':>6}  {'perfil':<14} o que o daemon fez")
    print("  " + "-" * 92)
    try:
        for seg in range(args.segundos):
            time.sleep(max(0.0, (t0 + seg + 1) - time.monotonic()))
            no, reports, pares, perfil, eventos = janela.fecha(seg)
            curto = no.replace("/dev/", "")
            print(f"  {seg:>3}s  {curto:<14} {reports:>7} {pares:>6}  {perfil:<14} {eventos}")
            linhas.append([f"{seg}s", curto, str(reports), str(pares), perfil, eventos])
    except KeyboardInterrupt:
        print("\n  (interrompido)")
    parar.set()

    # ---- o veredito, e ele recusa sair de contagem sozinha -------------------
    com_movimento = sum(1 for ln in linhas if int(ln[3]) > 2)
    com_report = sum(1 for ln in linhas if int(ln[2]) > 0)
    sem_vpad = sum(1 for ln in linhas if ln[1] == "(nenhum)")
    congelados = sum(1 for ln in linhas if int(ln[2]) > 10 and int(ln[3]) <= 1)
    mortes = sum(1 for ln in linhas if "emulação PAROU" in ln[5])
    nascimentos = sum(1 for ln in linhas if "vpad NASCEU" in ln[5])
    reconciles = sum(1 for ln in linhas if "reconcile" in ln[5])

    print(
        "\n"
        + tabela(
            ["o que se contou", "segundos"],
            [
                ["com movimento real (pares > 2)", str(com_movimento)],
                ["com report chegando", str(com_report)],
                ["SEM vpad nenhum", str(sem_vpad)],
                ["CONGELADO (reports > 10 e pares ≤ 1)", str(congelados)],
                ["--- eventos ---", ""],
                ["a emulação PAROU", str(mortes)],
                ["o vpad NASCEU", str(nascimentos)],
                ["backend_hotplug_reconcile", str(reconciles)],
            ],
        )
    )

    if com_movimento == 0:
        print(
            resumo(
                "NÃO CONCLUSIVO: nenhum segundo teve movimento real. Ou a mão "
                "ficou parada, ou nunca houve entrada — e este instrumento não "
                "separa as duas. Refaça com o gesto contínuo do começo ao fim."
            )
        )
        return 2
    if sem_vpad and congelados:
        print(
            resumo(
                f"OS DOIS: o vpad MORREU em {sem_vpad}s e CONGELOU em "
                f"{congelados}s. A linha do tempo acima diz qual veio primeiro — "
                "e é ela que decide a ordem da cura."
            )
        )
    elif sem_vpad:
        print(
            resumo(
                f"MORRE: {sem_vpad}s sem vpad nenhum, com {mortes} parada(s) da "
                f"emulação e {nascimentos} nascimento(s). O jogo que enumerou o "
                "nó anterior ficou com um descritor órfão. A cura é impedir a "
                "destruição, não reabrir o leitor."
            )
        )
    elif congelados:
        print(
            resumo(
                f"CONGELA: {congelados}s com report chegando e eixo parado, sem "
                "o vpad morrer. É o item 1 do O-QUE-FICOU-ABERTO-01, agora com "
                "gatilho na linha do tempo acima."
            )
        )
    else:
        print(
            resumo(
                f"NEM UM NEM OUTRO: {com_movimento}s de movimento real e nenhum "
                "segundo congelado ou sem vpad. Neste ensaio o vpad se comportou."
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
