#!/usr/bin/env python3
"""o_multiplicador_chega_ao_motor.py — a barra de cada motor, sentida na MÃO.

A PERGUNTA QUE ELE DECIDE
--------------------------
A `VIBRACAO-POR-MOTOR-01` (decisão dela, 04/09/2026) diz que cada motor tem um
multiplicador próprio que **compõe** com o degrau da coluna::

    efetivo(motor) = degrau(coluna) x barra(motor)

    degrau 150 %, fraca 100 %, forte 100 %  ->  150 % e 150 %
    degrau 150 %, fraca 100 %, forte  50 %  ->  150 % e  75 %

O teste de unidade prova a CONTA. Ele não prova nada sobre plástico. **O que
este ensaio decide é a premissa física da conta inteira:** os dois motores do
DualSense obedecem a um par ASSIMÉTRICO de verdade, ou o firmware os iguala
por baixo? Se os igualasse, a barra por motor seria um número bonito na tela
sobre um aparelho que não sabe cumpri-lo — e a régua verde não teria visto.

*"Quando o instrumento e o aparelho discordam, o aparelho ganha."*

O DESENHO — e a sacada é medir a RAZÃO, não o valor absoluto
-------------------------------------------------------------
O par sai da conta DO PRODUTO (`daemon.subsystems.gamepad._mults_por_motor`,
com um daemon sintético carregando os números dela), nunca de um `150` e um
`75` digitados aqui: um par digitado mediria o meu palpite.

O par é entregue pelo `rumble.set` do daemon VIVO, que é a porta de escrita
desta casa — nada de `os.write` cru disputando o hidraw com quem já o segura
(a armadilha número 3 do `CLAUDE.md`: *"o instrumento pode estar brigando com o
produto"*). O `rumble.set` aplica o degrau global POR CIMA do par, e isso não
atrapalha: **um fator comum aos dois motores não muda a razão entre eles**, e a
razão é a assinatura da barra. O degrau vigente sai impresso no cabeçalho, como
manda a casa.

Os passos, e cada um é uma pergunta para a mão dela::

    1  PAR SIMÉTRICO   (base, base)          controle POSITIVO — os dois tremem
    2  O PAR DA CONTA  (base * fraca, base * forte)  o fraco inteiro, o forte pela metade
    3  SÓ O FRACO      (base, 0)             o pequeno sozinho (o agudo)
    4  SÓ O FORTE      (0, base)              o grande sozinho (o grave)
    5  SILÊNCIO        (0, 0)                controle NEGATIVO — nada pode tremer

    Se 1 treme e 5 não   -> o instrumento está no caminho, e o resto significa
                            o que se pensa.
    Se 3 e 4 são iguais  -> o firmware IGUALA os motores, e a barra por motor
                            não tem como existir. É o achado que derruba a
                            sprint, e ele vale mais que um verde.
    Se 2 sai igual ao 1  -> a assimetria não sobreviveu ao caminho.

O QUE ELE **NÃO** PROVA, e está dito em vez de escondido
---------------------------------------------------------
**Ele não prova que o daemon INSTALADO faz a conta.** O daemon vivo é o da
árvore dela; o código desta sprint mora numa worktree e só chega ao aparelho
depois do merge e de um `install.sh` — que agente nenhum roda. O que ele prova é
o andar de baixo: que o par que a conta produz **chega ao motor como par**, com
os dois motores em intensidades diferentes. O andar de cima é o teste de
unidade, e os dois juntos fecham a afirmação.

A BANCADA É DELA
-----------------
Escrever no aparelho exige a bancada. O ensaio chama `scripts/bancada.sh exigir`
sozinho e PARA com `rc=2` se ela estiver tomada — nunca contorna por outro
caminho, que é como se inventa medição falsa.

Uso::

    scripts/ensaios/o_multiplicador_chega_ao_motor.py --sem-escrever   # só a conta
    scripts/ensaios/ONDA...py --base 200 --segundos 1.5                # na mão dela

Ele não abre janela nenhuma: sem GTK, sem navegador, sem `DISPLAY`. A tela dela
não recebe nada.
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import time
from types import SimpleNamespace
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

#: Os números DELA, verbatim da decisão de 04/09/2026 — o degrau "Máximo" e a
#: barra forte pela metade. São a ENTRADA da conta do produto, não a saída.
DEGRAU_DELA = "max"
BARRA_FORTE_DELA = 50
BARRA_FRACA_DELA = 100

#: O endereço da peça no perfil sintético. Faixa SINTÉTICA da casa — o MAC real
#: do aparelho na mesa nunca entra num arquivo versionado.
PECA = "aabbcc000001"


def _procedencia() -> list[str]:
    """De qual arquivo veio cada peça que este ensaio usa. Regra da casa."""
    from hefesto_dualsense4unix.app import ipc_bridge
    from hefesto_dualsense4unix.daemon.subsystems import gamepad, rumble
    from hefesto_dualsense4unix.profiles import schema

    return [
        f"conta ....... {gamepad.__file__}",
        f"escada ...... {rumble.__file__}",
        f"esquema ..... {schema.__file__}",
        f"porta ....... {ipc_bridge.__file__} (IPC do daemon VIVO)",
        f"python ...... {sys.executable}",
    ]


def _daemon_sintetico(degrau: str) -> Any:
    """Daemon de mentira só para a CONTA — não escreve em aparelho nenhum."""
    return SimpleNamespace(
        config=SimpleNamespace(
            rumble_active=None,
            rumble_policy=degrau,
            rumble_policy_custom_mult=0.7,
        ),
        controller=SimpleNamespace(),
        store=SimpleNamespace(
            active_profile=None,
            snapshot=lambda: SimpleNamespace(controller=SimpleNamespace(battery_pct=80)),
        ),
        _last_auto_mult=1.0,
        _last_auto_change_at=0.0,
        # O mapa por peça entregue pronto: o ensaio mede a CONTA, e ir ao disco
        # aqui mediria o `load_profile` junto.
        _rumble_motores_pct=(None, {PECA: (BARRA_FORTE_DELA, BARRA_FRACA_DELA)}),
    )


def _par_da_conta(degrau: str, base: int) -> tuple[int, int, float, float]:
    """`(weak, strong, mult_fraco, mult_forte)` — tudo do produto, nada digitado."""
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    mult_fraco, mult_forte = gp._mults_por_motor(_daemon_sintetico(degrau), 0.0, PECA)
    weak = max(0, min(255, round(base * mult_fraco)))
    strong = max(0, min(255, round(base * mult_forte)))
    return weak, strong, mult_fraco, mult_forte


def _exigir_bancada() -> bool:
    """`scripts/bancada.sh exigir` — rc≠0 é ESPERAR, nunca contornar."""
    proc = subprocess.run(
        ["bash", str(RAIZ / "scripts" / "bancada.sh"), "exigir"],
        capture_output=True,
        text=True,
    )
    saida = (proc.stdout + proc.stderr).strip()
    if saida:
        print(f"  bancada ..... {saida}")
    return proc.returncode == 0


def _estado_do_daemon() -> dict[str, Any] | None:
    from hefesto_dualsense4unix.app import ipc_bridge

    return ipc_bridge.daemon_state_full()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # 160 e não 200: com o degrau "Máximo" (1,5) o motor fraco sai em 240 e o
    # forte em 120 — a razão 2:1 INTEIRA, sem encostar no teto. Em 200 o fraco
    # pediria 300, o `min(255, …)` cortaria, e a razão medida viraria 1,7 por
    # SATURAÇÃO, não por conta errada. É a nota SATURA-01 mordendo o
    # instrumento em vez do produto.
    ap.add_argument("--base", type=int, default=160,
                    help="intensidade base a que a conta se aplica (0-255)")
    ap.add_argument("--segundos", type=float, default=1.5,
                    help="quanto tempo cada passo fica tremendo")
    ap.add_argument("--degrau", default=DEGRAU_DELA,
                    help="a política da coluna: economia|balanceado|max|custom")
    ap.add_argument("--sem-escrever", action="store_true",
                    help="só imprime a conta; não toca no aparelho nem na bancada")
    args = ap.parse_args()

    print("o multiplicador chega ao motor — procedência declarada:")
    for linha in _procedencia():
        print(f"  {linha}")

    weak, strong, mf, mF = _par_da_conta(args.degrau, args.base)
    print()
    print(f"A CONTA DO PRODUTO, com os números dela (degrau {args.degrau!r}, "
          f"barra fraca {BARRA_FRACA_DELA}%, barra forte {BARRA_FORTE_DELA}%):")
    print(f"  mult do motor FRACO ... {mf:.4f}")
    print(f"  mult do motor FORTE ... {mF:.4f}")
    print(f"  razão forte/fraco ..... {(mF / mf if mf else float('nan')):.4f}"
          f"   <- É ISTO que a mão tem de sentir")
    print(f"  par sobre a base {args.base:3d} .. weak={weak}  strong={strong}")
    if round(args.base * mf) > 255 or round(args.base * mF) > 255:
        print(f"  AVISO: a base {args.base} SATURA em 255 — a razão que a mão "
              f"vai sentir não é a da conta, é a do corte. Baixe a base.")

    if args.sem_escrever:
        print("\n--sem-escrever: nada foi mandado ao aparelho.")
        return 0

    print()
    estado = _estado_do_daemon()
    if estado is None:
        print("SEM DAEMON: o `rumble.set` não tem para onde ir. "
              "Ligue o Hefesto e rode de novo.", file=sys.stderr)
        return 3
    print(f"  daemon ...... vivo · degrau global {estado.get('rumble_policy')!r} "
          f"· perfil {estado.get('active_profile')!r}")
    print("  (o degrau global multiplica os DOIS motores por igual — ele muda a "
          "força, nunca a razão)")

    if not _exigir_bancada():
        print("BANCADA TOMADA — esperar, e dizer na entrega que se está "
              "esperando. Nada foi escrito.", file=sys.stderr)
        return 2

    from hefesto_dualsense4unix.app import ipc_bridge

    #: O QUE ESTAVA ANTES, para devolver no fim. `None` = passthrough (o jogo
    #: manda), e é o estado normal da máquina dela.
    antes = estado.get("rumble_active")
    print(f"  estado antes .. rumble_active={antes!r} "
          f"(será devolvido no fim, seja qual for)")

    passos: list[tuple[str, int, int, str]] = [
        ("PAR SIMÉTRICO  (controle POSITIVO)", args.base, args.base,
         "os DOIS têm de tremer — se não, o instrumento não está no caminho"),
        ("O PAR DA CONTA", weak, strong,
         "o fraco inteiro, o forte pela metade — a assimetria dela"),
        ("SÓ O FRACO", args.base, 0, "o motor pequeno sozinho (o agudo)"),
        ("SÓ O FORTE", 0, args.base, "o motor grande sozinho (o grave)"),
        ("SILÊNCIO       (controle NEGATIVO)", 0, 0,
         "NADA pode tremer — se tremer, alguém mais está escrevendo"),
    ]
    for titulo, w, s, pergunta in passos:
        print(f"\n  {titulo}: weak={w} strong={s}")
        print(f"      -> {pergunta}")
        ok = ipc_bridge.rumble_set(w, s)
        depois = _estado_do_daemon() or {}
        fixado = depois.get("rumble_active")
        print(f"      rumble.set aceito: {ok}   ·   o daemon guarda: {fixado}")
        if fixado is not None and tuple(fixado) != (w, s):
            print(f"      DIVERGÊNCIA: pedi {(w, s)} e o daemon guarda "
                  f"{tuple(fixado)} — alguém no caminho mexeu no par.")
        if (w, s) != (0, 0) and fixado is not None and fixado[0] == fixado[1] != 0 \
                and w != s:
            print("      O PAR FOI IGUALADO no caminho — é o achado que "
                  "derruba a barra por motor. Vale mais que um verde.")
        time.sleep(args.segundos)
        ipc_bridge.rumble_stop()
        time.sleep(0.4)

    # A DEVOLUÇÃO, e ela é obrigatória — MEDIDA em 04/09/2026, na primeira
    # execução deste ensaio: `rumble.stop` NÃO devolve o passthrough, deixa
    # `rumble_active=(0,0)`. E com o rumble FIXADO o `apply_game_rumble`
    # descarta o FF do jogo (primeira linha dele) — ou seja, o instrumento
    # saía deixando a máquina dela SEM vibração em jogo nenhum, em silêncio.
    # É a armadilha 3 do `CLAUDE.md` na forma mais cara: o instrumento
    # brigando com o produto e ninguém vendo.
    if antes is None:
        ipc_bridge.rumble_passthrough(True)
    else:
        ipc_bridge.rumble_set(int(antes[0]), int(antes[1]))
    final = _estado_do_daemon() or {}
    devolvido = final.get("rumble_active")
    print(f"\n  motores parados · rumble_active={devolvido} "
          f"· passthrough={final.get('rumble_passthrough')}")
    if (devolvido is None) != (antes is None):
        print("  ATENÇÃO: o estado de vibração NÃO voltou ao que era "
              f"({antes!r} antes, {devolvido!r} agora). Devolva à mão: "
              "`rumble_passthrough(True)`.", file=sys.stderr)
    print("  A LEITURA ACIMA É DO DAEMON, e ela prova que o par ASSIMÉTRICO "
          "atravessa como par.\n  O que ela NÃO prova é o plástico: o veredito "
          "de qual motor treme mais é da MÃO DELA.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
