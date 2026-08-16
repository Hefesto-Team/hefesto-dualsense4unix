#!/usr/bin/env python3
"""tres_casos_de_som.py — os TRÊS casos do som, com dois timbres que não se confundem.

A PERGUNTA QUE ELE RESPONDE
----------------------------
*Para onde vai cada som, e quem manda nisso?* O DualSense tem uma saída de áudio
PRÓPRIA — o alto-falante interno, o canal que poucos jogos usam para SFX — e ela
convive com a saída normal do sistema (no caso desta bancada, o HDMI da TV).
Saber que "o som funciona" não diz nada: a pergunta é qual som sai por onde.

O DESENHO É DELA, de 15/08/2026, e a sacada está nos DOIS TIMBRES:

  som A  "hmmmmm"       180 Hz contínuo, com harmônicos em 360 e 540 — grave
  som B  "bep bep bep"  1300 Hz pulsado a 2 Hz                       — agudo

Um tom só, tocado duas vezes, produz o relato ambíguo "ouvi" — que não diz de
onde nem qual. Com dois timbres opostos, o relato dela JÁ carrega a resposta:
ela disse *"tuc hmmmmmm no controle"* e *"bep bep bep"*, e nenhuma das duas
frases cabe no outro caso. Nas palavras dela: *"som da tv tipo AAAAAA e no
controle apenas um BBêeee. Sons diferentes."*

OS TRÊS CASOS, e o terceiro é o que fecha
------------------------------------------
  1. **Só a TV.**  A -> HDMI. Tem de sair na TV, com o controle MUDO.
  2. **Só o controle.**  B -> sink do controle. Tem de sair no controle, TV MUDA.
  3. **Os dois juntos, no controle.**  A e B ao mesmo tempo, com o sink PADRÃO
     trocado para o controle. Os DOIS têm de sair pelo controle.

O caso 3 não é o caso 2 repetido: ele é o que a janela faz no botão "Todo o som
do PC", e é o único que exercita a troca do PADRÃO do sistema em vez de mirar um
sink. Rodar só o 2 e concluir o 3 é pular etapa — e foi o erro cometido na
primeira passada de 15/08, corrigido por ela na hora: *"não pula etapa, nem
chega em conclusão assim"*.

O QUE ESTE ENSAIO ISOLOU, e é a razão de ele existir
-----------------------------------------------------
**A POSSE DOS BYTES DE VOLUME É A CAUSA.** Medido por dose-resposta em 15/08,
com o azul no cabo:

  volume nunca escrito por nós ....... ela: "nenhum"          MUDO
  `speaker volume 85`  ............... ela: "bep bep bep"     SOA
  `speaker volume 0`   ............... ela: "mudo"            MUDO

Nada mais mudou entre as três passadas: mesma rota, mesmo sink, mesmo arquivo, e
o sink conferido antes sem mudo e a 100% nos quatro canais. O culpado é o
`_volumes_audio` (`common[4..7]`) do `core/backend_pydualsense.py`: **sem posse o
daemon escreve ZERO em todo report**, e o alto-falante fica mudo para todo mundo.
É a MESMA família do keepalive que cancelava o rumble alheio pelos BYTES e não
pelos bits — o comentário em `:560` já dizia *"idem, mandando volume ZERO em todo
report"*, e ninguém tinha ligado isso ao silêncio.

Por isso este instrumento toma a posse ANTES de tocar qualquer coisa, e oferece
`--controle-negativo` para reproduzir o silêncio de propósito.

A ROTA, e o que ainda falta dela
---------------------------------
`common[7]` bits 4-5, e a tabela é de `profiles/schema.py:437-441`:

  0  estéreo -> fone
  1  L -> fone, mono
  2  L -> fone, R -> ALTO-FALANTE     ("Sons do jogo" na tela; o caso Zelda)
  3  R -> alto-falante interno        ("Todo o som do PC" na tela)

Este ensaio roda na **rota 3**. A **rota 2 continua NÃO EXERCIDA** — e ela é
justamente o SFX que só alguns jogos mandam. As rotas 0 e 1 exigem fone plugado.

O QUE ELE NÃO PROVA
--------------------
Que o caminho da JANELA funcione. Ela relatou, na mesma sessão, que pela
interface o bipe não sai hoje nem no cabo, tendo saído antes. Este instrumento
prova o CAMINHO; a regressão da janela é outra frente e continua aberta.

E não prova nada sobre o rádio: a mesa desta medição tinha o azul no CABO.

CONTROLES, e nenhum é enfeite
------------------------------
POSITIVO ...... o caso 1 é o positivo do HDMI e, ao mesmo tempo, o negativo do
                controle; o caso 2 é o inverso. Um cobre o outro.
NEGATIVO ...... `--controle-negativo` põe o volume em 0 e repete: tem de sair
                MUDO. Sem ele, "ouvi" poderia ser qualquer escrita fazendo
                qualquer coisa.
DE VAZAMENTO .. os dois timbres tocando ao mesmo tempo em lugares diferentes é o
                que mostra que um não vaza para o outro.

O QUE ELE DEVOLVE
------------------
O sink padrão dela é guardado ANTES e devolvido no fim, inclusive se o ensaio
morrer no meio (`try/finally`). Trocar a saída de áudio de alguém e não devolver
é estragar a máquina de quem emprestou a bancada.

USO
    tres_casos_de_som.py --listar
    tres_casos_de_som.py --alvo <MAC>          # os três casos, na rota 3
    tres_casos_de_som.py --alvo <MAC> --caso 3
    tres_casos_de_som.py --alvo <MAC> --controle-negativo
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import socket
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

TAXA = 48000

#: Os dois timbres. A distância entre eles é o instrumento — ver o docstring.
SOM_A = ("hmmmmm (grave contínuo, 180 Hz + harmônicos)", 2)
SOM_B = ("bep bep bep (agudo pulsado, 1300 Hz a 2 Hz)", 4)


def _escrever_wav(caminho: Path, canais: int, gerar, segundos: float) -> None:
    """Um WAV com envelope nas pontas — clique de início vira 'ouvi' falso."""
    n = int(TAXA * segundos)
    quadros = bytearray()
    for i in range(n):
        env = min(1.0, i / (TAXA * 0.01), (n - i) / (TAXA * 0.01))
        v = gerar(i / TAXA)
        amostra = struct.pack("<h", int(max(-1.0, min(1.0, v * env)) * 32767))
        quadros += amostra * canais
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(canais)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(bytes(quadros))


def _onda_a(t: float) -> float:
    return (0.30 * math.sin(2 * math.pi * 180 * t)
            + 0.18 * math.sin(2 * math.pi * 360 * t)
            + 0.10 * math.sin(2 * math.pi * 540 * t))


def _onda_b(t: float) -> float:
    pulso = 1.0 if int(t * 4) % 2 == 0 else 0.0
    return 0.38 * math.sin(2 * math.pi * 1300 * t) * pulso


#: `LC_ALL=C` NÃO é zelo: o `pactl` TRADUZ os rótulos da saída longa, e nesta
#: máquina "Name:" sai como "Nome:". A primeira versão deste instrumento não
#: achava sink nenhum por isso, e dizia "nenhum controle com placa de áudio" —
#: uma afirmação sobre o APARELHO que na verdade era sobre o idioma do shell.
#: É a mesma família de "medir contra a biblioteca errada": o instrumento
#: mentindo com convicção.
_AMBIENTE_C = {**os.environ, "LC_ALL": "C", "LANG": "C"}


def _pactl(*args: str) -> str:
    return subprocess.run(["pactl", *args], capture_output=True, text=True,
                          timeout=15, env=_AMBIENTE_C).stdout.strip()


def sinks_de_controle() -> dict[str, str]:
    """MAC mascarado -> nome do sink, casados pelo dispositivo USB em comum.

    É o mesmo casamento que o `audio_por_transporte.py` faz, e ele é o que
    permite falar de UM controle quando há dois no cabo: o sink e o `hidraw`
    penduram no mesmo `usbN/X-Y`.
    """
    fora: dict[str, str] = {}
    for linha in _pactl("list", "sinks", "short").splitlines():
        campos = linha.split("\t")
        if len(campos) < 2 or "DualSense" not in campos[1]:
            continue
        nome = campos[1]
        # `analog-surround-40` e `...2.analog-surround-40` -> card 2 e 3
        detalhe = _pactl("list", "sinks")
        bloco = detalhe.split(f"Name: {nome}")
        if len(bloco) < 2:
            continue
        m = re.search(r'alsa\.card = "(\d+)"', bloco[1][:2000])
        if not m:
            continue
        card = m.group(1)
        alvo = os.path.realpath(f"/sys/class/sound/card{card}/device")
        alvo = re.sub(r":1\.\d+$", "", alvo)
        for h in Path("/sys/class/hidraw").glob("hidraw*"):
            dev = os.path.realpath(h / "device")
            m2 = re.search(r"(usb\d+/[\d.-]+)", dev)
            if not m2 or os.path.basename(m2.group(1)) != os.path.basename(alvo):
                continue
            try:
                uevent = (Path(dev) / "uevent").read_text(encoding="utf-8")
            except OSError:
                continue
            mu = re.search(r"HID_UNIQ=(\S+)", uevent)
            if mu:
                p = mu.group(1).split(":")
                fora[f"{p[0]}:{p[1]}:{p[2]}:00:00:{p[5]}"] = nome
    return fora


def rota(valor: int) -> dict:
    """`speaker.set {rota}` pelo IPC — o mesmo pedido que o botão da tela manda."""
    from hefesto_dualsense4unix.utils.xdg_paths import ipc_socket_path
    pedido = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "speaker.set",
                         "params": {"rota": valor}}) + "\n"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(8.0)
        s.connect(str(ipc_socket_path()))
        s.sendall(pedido.encode("utf-8"))
        return json.loads(s.recv(65536).decode("utf-8", "replace") or "{}")


def volume(pct: int) -> None:
    """Toma a posse dos bytes de volume. SEM ISTO O ALTO-FALANTE FICA MUDO."""
    subprocess.run(["hefesto-dualsense4unix", "speaker", "volume", str(pct)],
                   capture_output=True, text=True, timeout=30)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--listar", action="store_true")
    ap.add_argument("--alvo", help="MAC mascarado do controle (ver --listar)")
    ap.add_argument("--caso", type=int, choices=(1, 2, 3), action="append")
    ap.add_argument("--rota", type=int, default=3, choices=(0, 1, 2, 3))
    ap.add_argument("--volume", type=int, default=85)
    ap.add_argument("--controle-negativo", action="store_true",
                    help="volume 0: tem de sair MUDO")
    args = ap.parse_args()

    sinks = sinks_de_controle()
    if args.listar or not args.alvo:
        print("porta: pactl/pw-play (PipeWire) · IPC do daemon para a rota")
        print("escreve no aparelho? SIM — volume e rota. Bloco DELA.\n")
        for mac, nome in sinks.items():
            print(f"  {mac}  ->  {nome}")
        if not sinks:
            print("  nenhum controle com placa de áudio (só o CABO publica uma)")
        return 0

    if args.alvo not in sinks:
        print(f"alvo {args.alvo} não tem sink; conhecidos: {list(sinks)}")
        return 1
    sink = sinks[args.alvo]
    hdmi = next((linha.split("\t")[1]
                 for linha in _pactl("list", "sinks", "short").splitlines()
                 if "hdmi" in linha), "")
    anterior = _pactl("get-default-sink")
    casos = sorted(set(args.caso or (1, 2, 3)))

    print(f"alvo ....... {args.alvo}  ({sink})")
    print(f"HDMI ....... {hdmi or '(não achei)'}")
    print(f"padrão ..... {anterior}  (será DEVOLVIDO no fim)")
    print(f"rota ....... {args.rota}")
    print(f"volume ..... {0 if args.controle_negativo else args.volume}"
          f"{'  <- CONTROLE NEGATIVO: tem de sair MUDO' if args.controle_negativo else ''}")
    print("\nO RETORNO DESTE SCRIPT NÃO É A MEDIÇÃO. Quem mede é a orelha dela.\n")

    with tempfile.TemporaryDirectory(prefix="tres-casos-") as tmp:
        d = Path(tmp)
        _escrever_wav(d / "a.wav", 2, _onda_a, 2.5)
        _escrever_wav(d / "b.wav", 4, _onda_b, 2.5)
        try:
            volume(0 if args.controle_negativo else args.volume)
            rota(args.rota)
            if 1 in casos:
                input(f"CASO 1 — só a TV. Vou tocar o som A: {SOM_A[0]}\n"
                      "  esperado: sai na TV, controle MUDO.  [Enter]")
                subprocess.run(["pw-play", f"--target={hdmi}", str(d / "a.wav")],
                               timeout=20)
                print("  -> o que ela ouviu, e ONDE?\n")
            if 2 in casos:
                input(f"CASO 2 — só o controle. Som B: {SOM_B[0]}\n"
                      "  esperado: sai no controle, TV MUDA.  [Enter]")
                subprocess.run(["pw-play", f"--target={sink}", str(d / "b.wav")],
                               timeout=20)
                print("  -> o que ela ouviu, e ONDE?\n")
            if 3 in casos:
                input("CASO 3 — os DOIS juntos, no controle (o botão 'Todo o som "
                      "do PC').\n  esperado: A e B ao mesmo tempo, os dois pelo "
                      "controle.  [Enter]")
                _pactl("set-default-sink", sink)
                p1 = subprocess.Popen(["pw-play", str(d / "a.wav")])
                p2 = subprocess.Popen(["pw-play", str(d / "b.wav")])
                p1.wait(timeout=20)
                p2.wait(timeout=20)
                print("  -> ela ouviu os DOIS timbres? no controle?\n")
        finally:
            if anterior:
                _pactl("set-default-sink", anterior)
                print(f"padrão devolvido: {_pactl('get-default-sink')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
