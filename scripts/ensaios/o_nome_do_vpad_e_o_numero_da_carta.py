#!/usr/bin/env python3
"""A-MESMA-LINGUA-01 — a prova ao vivo, com os quatro DELA na mesa.

Lê o `state_full` do daemon VIVO (leitura pura, socket local) e responde três
perguntas, uma por espaço de numeração:

  1. o que a CARTA diz (a fila de chegada, `controllers[].player_slot`);
  2. o que o NOME do vpad diz hoje (`coop.mesa[].vpad_nome`);
  3. o que o SDL do CONTÊINER diz (a biblioteca que os jogos dela carregam).

E então roda a CURA contra a mesa viva: para cada aparelho, qual nome o vpad
levaria na PRÓXIMA subida. O daemon vivo é o de ANTES da cura — não se
reinicia daemon com quatro controles na mesa —, então a coluna "depois" é o
que a cura produz a partir dos MESMOS números que o daemon publica agora.

Nada aqui escreve: nem no daemon, nem no disco, nem na tela dela. Nenhuma
janela nasce (TELA-DELA-02) e nenhum endereço real sai impresso — a máscara da
casa (octetos 4 e 5 zerados) é aplicada em :func:`mascarar`.

Uso:

    PYTHONPATH=src .venv/bin/python scripts/ensaios/o_nome_do_vpad_e_o_numero_da_carta.py

`rc=0` quando os nomes que a próxima subida daria batem com as cartas; `rc=1`
quando sobra divergência.

A MORDIDA, medida em 07/09/2026 com os quatro dela na mesa: arrancada a cura
(`CoopManager.numero_para_o_nome` devolvendo o `fallback`), este mesmo ensaio
sai **4 de 4 divergentes**; com ela, **0 de 4**.

O QUE ELE NÃO PROVA, e está escrito para ninguém concluir demais: o daemon
VIVO é o de antes da cura, e não se reinicia daemon com quatro controles na
mesa. A coluna "depois" é a cura rodando contra os MESMOS números que o daemon
publica agora — o nome só troca de verdade na próxima subida de cada vpad.

E há um terceiro espaço de numeração que este ensaio NÃO alcança: dentro do
contêiner da Steam o SDL abre o vpad por HIDAPI e SOBRESCREVE o nome pelo
PID (`DualSense Edge Wireless Controller`, igual nos quatro). Ver o relatório
da A-MESMA-LINGUA-01.
"""
from __future__ import annotations

import json
import socket
import sys

SOCK = "/run/user/1000/hefesto-dualsense4unix/hefesto-dualsense4unix.sock"


def mascarar(mac: str) -> str:
    """A máscara da casa: octetos 4 e 5 zerados."""
    if not isinstance(mac, str):
        return "—"
    puro = mac.replace(":", "")
    if len(puro) != 12:
        return mac
    o = [puro[i : i + 2] for i in range(0, 12, 2)]
    return ":".join([*o[:3], "00", "00", o[5]])


def estado() -> dict:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect(SOCK)
    s.sendall(b'{"jsonrpc":"2.0","id":1,"method":"daemon.state_full","params":{}}\n')
    buf = b""
    while not buf.endswith(b"\n"):
        ch = s.recv(65536)
        if not ch:
            break
        buf += ch
    return json.loads(buf.decode())["result"]


def main() -> int:
    d = estado()
    mesa = {i["uniq"]: i for i in (d.get("coop") or {}).get("mesa") or [] if i.get("uniq")}
    cartas = {c["uniq"]: c for c in d.get("controllers") or []}

    # A CURA, alimentada pela mesa VIVA. `numeros_de_jogador` é a fonte única —
    # aqui ela é reconstruída a partir do que o daemon já publica (`player`), que
    # é a MESMA função (`CoopManager.numeros_de_jogador`) do outro lado do socket.
    from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager

    fila = {u: i["player"] for u, i in mesa.items()}

    class _Reg:
        def slot_for(self, uniq, assign=False, autoridade_de_presenca=True):
            return fila.get(uniq)

    primario = next((u for u, i in mesa.items() if i.get("is_primary")), None)

    class _Daemon:
        controller = type(
            "C", (), {"primary_uniq": primario, "_evdev": None}
        )()
        _gamepad_device = None
        config = type("Cfg", (), {"coop_enabled": True, "gamepad_flavor": "dualsense"})()
        identity_registry = _Reg()

    mgr = CoopManager(_Daemon())  # type: ignore[arg-type]
    # A MESA VIVA, sentada no manager: cada secundário com o `player_index` que
    # o daemon publica hoje DENTRO do nome (`vpad_indice`) — é ele o fallback,
    # e é contra ele que a cura tem de vencer.
    from types import SimpleNamespace

    from hefesto_dualsense4unix.daemon.subsystems.coop import _SecondaryPlayer

    for uniq, item in mesa.items():
        if item.get("is_primary"):
            continue
        mgr._players[uniq] = _SecondaryPlayer(
            identity=uniq,
            evdev_path="/dev/input/eventVIVO",
            reader=SimpleNamespace(grab_state="held"),  # type: ignore[arg-type]
            player_index=item.get("vpad_indice") or 2,
        )

    print("  aparelho             modelo            carta   nome de HOJE   depois")
    print("  " + "-" * 74)
    erra_antes = erra_depois = 0
    for uniq, item in mesa.items():
        carta = cartas.get(uniq, {})
        hoje = item.get("vpad_indice")
        if item.get("is_primary"):
            from hefesto_dualsense4unix.daemon.subsystems.coop import (
                numero_do_nome_do_primario,
            )

            mgr._daemon._coop_manager = mgr
            depois = numero_do_nome_do_primario(mgr._daemon)
        else:
            depois = mgr.numero_para_o_nome(uniq, hoje or 1)
        numero = item["player"]
        erra_antes += hoje != numero
        erra_depois += depois != numero
        print(
            f"  {mascarar(uniq):<20} {carta.get('modelo', '?')!s:<17} "
            f"{numero:^5}   Hefesto P{hoje}    Hefesto P{depois}"
            + ("   <-- mentia" if hoje != numero else "")
        )
    print()
    print(f"  divergentes ANTES: {erra_antes} de {len(mesa)}")
    print(f"  divergentes DEPOIS: {erra_depois} de {len(mesa)}")
    return 0 if erra_depois == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
