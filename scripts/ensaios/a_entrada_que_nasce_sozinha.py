#!/usr/bin/env python3
"""a_entrada_que_nasce_sozinha.py — quem mexe no cursor e no teclado dela.

PARA RODAR **NO MOMENTO EM QUE ACONTECER**, e é essa a razão de ele existir.

O RELATO É DELA, 10/09/2026, duas vezes na mesma madrugada:

    *"na REAL O TECLADO FICA SE MEXENDO QUANDO VC DA O COMANDO E SE FECHA
     SOZINHO. AI DESLIGO O BT DO CONTROLE E VOLTA AO NORMAL."*
    <!-- noqa-acento: citação literal dela -->

    *"DESLIGUEI ELE PQ O PROBLEMA DO TECLADO MALUCO E MOUSE MALUCO VOLTARAM."*
    <!-- noqa-acento: citação literal dela -->

O QUE JÁ FOI MEDIDO, E DEU ZERO NOS DOIS
-----------------------------------------
* **o controle PARADO na mesa, 30 s** — zero eventos no controle do rádio, no
  touchpad dele e no teclado virtual do Hefesto. Não é deriva de eixo nem botão
  preso;
* **durante 1000 reports de áudio escritos**, 16 s — zero eventos nos mesmos
  três nós. A escrita não provoca entrada.

**Logo a primeira causa que esta casa registrou estava errada** — eu atribuí a
entrada fantasma à disputa de contador da rajada de `0x35`, e ela voltou com
NENHUM som tocando.

A DIFERENÇA DE ESTADO QUE SOBRA, e é a hipótese viva: nas duas vezes em que ela
viu o defeito, o controle do rádio tinha **vpad** — era o `Hefesto P2` da mesa
de co-op. Nas duas medições que deram zero, ele não tinha: voltou como controle
físico depois de ela o reiniciar. Um vpad a mais é um caminho a mais entre o
aparelho e o cursor dela.

**Isto é hipótese, não conclusão.** Este instrumento existe para trocá-la por
medição na próxima vez.

E HOUVE UMA QUARTA MEDIÇÃO, que deu zero e **NÃO VALE** — 10/09/2026, 02h20.
O controle do rádio saiu da mesa entre a listagem e a corrida: ela desligou o
BT, que é o gesto com que ela cura o defeito. O instrumento mediu 90 s do
estado CURADO e imprimiu "NINGUÉM EMITIU NADA".

**A cura está no código, não neste texto:** ele relista os nós no fim, e se
algum alvo saiu, o veredito vira `MEDIÇÃO INVÁLIDA` com `rc=2`. Zero com o
alvo fora não é zero — é nada.

O QUE ELE MEDE
---------------
Todo nó de entrada com cara de controle ou de teclado/mouse virtual, ao mesmo
tempo, contando evento por evento e dizendo QUAL nó emitiu. Se o cursor dela
andar enquanto ele roda, o nome do culpado sai na tabela.

Ele **não escreve nada** e não abre janela: é leitura pura de `/dev/input`.

USO — rode QUANDO O DEFEITO ESTIVER ACONTECENDO
    a_entrada_que_nasce_sozinha.py                # 30 s
    a_entrada_que_nasce_sozinha.py --segundos 120 # mais tempo
    a_entrada_que_nasce_sozinha.py --listar       # só diz o que vigiaria
"""

from __future__ import annotations

import argparse
import collections
import os
import re
import select
import sys
import time

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)
_SRC = os.path.join(os.path.dirname(os.path.dirname(_AQUI)), "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from comum import cabecalho_do_instrumento, resumo

#: O QUE ENTRA NA VIGIA. Nomes, e não caminhos: `eventNN` muda a cada
#: reconexão, e um caminho cravado aqui mediria o nó errado amanhã.
INTERESSA = ("hefesto", "dualsense", "virtual", "wireless controller")


def mascarar(uniq: str) -> str:
    """A máscara da casa: octetos 4 e 5 zerados."""
    return re.sub(r"^(..):(..):(..):..:..:(..)$", r"\1:\2:\3:00:00:\4", uniq)


def nos_de_entrada() -> list[tuple[str, str, str]]:
    """`(caminho, nome, uniq mascarado)` de todo nó que interessa."""
    fora = []
    try:
        with open("/proc/bus/input/devices", encoding="utf-8") as arq:
            blocos = arq.read().split("\n\n")
    except OSError:
        return fora
    for b in blocos:
        n = re.search(r'N: Name="([^"]+)"', b)
        e = re.search(r"(event\d+)", b)
        if not (n and e):
            continue
        nome = n.group(1)
        if not any(k in nome.lower() for k in INTERESSA):
            continue
        u = re.search(r"U: Uniq=(\S*)", b)
        uniq = (u.group(1) if u else "") or ""
        fora.append((f"/dev/input/{e.group(1)}", nome, mascarar(uniq) if uniq else "—"))
    return fora


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--segundos", type=float, default=30.0)
    ap.add_argument("--listar", action="store_true", help="só diz o que vigiaria")
    args = ap.parse_args()

    print(cabecalho_do_instrumento(
        "a_entrada_que_nasce_sozinha",
        "qual nó mexe no cursor e no teclado dela quando ninguém encosta no controle?",
        bibliotecas=["evdev"],
        escreve_no_aparelho=False))

    alvos = nos_de_entrada()
    if not alvos:
        print(resumo("nenhum nó de controle na mesa — nada a vigiar."))
        return 1
    print("O QUE ELE VIGIA:")
    for caminho, nome, uniq in alvos:
        print(f"  {caminho:20s} {nome[:48]:50s} uniq={uniq}")

    if args.listar:
        print(resumo("leitura pura — nenhum nó aberto nesta corrida."))
        return 0

    try:
        import evdev
    except ImportError:
        print(resumo("o `evdev` não está nesta venv — `pip install evdev`."))
        return 1

    abertos: dict[int, tuple[object, str]] = {}
    for caminho, nome, _ in alvos:
        try:
            d = evdev.InputDevice(caminho)
            abertos[d.fd] = (d, nome)
        except OSError as erro:
            print(f"  (não abri {caminho}: {erro.strerror})")
    if not abertos:
        print(resumo("não consegui abrir nenhum nó — falta permissão em /dev/input?"))
        return 1

    print(f"\n>>> MEDINDO {args.segundos:g} s. Se o cursor andar sozinho agora, "
          f"o culpado sai nomeado abaixo.", flush=True)
    conta: collections.Counter[str] = collections.Counter()
    detalhe: collections.Counter[tuple[str, str]] = collections.Counter()
    fim = time.monotonic() + args.segundos
    while time.monotonic() < fim:
        prontos, _, _ = select.select(list(abertos), [], [], 1.0)
        for fd in prontos:
            dispositivo, nome = abertos[fd]
            try:
                eventos = list(dispositivo.read())  # type: ignore[attr-defined]
            except OSError:
                continue
            for ev in eventos:
                if ev.type == evdev.ecodes.EV_SYN:
                    continue
                conta[nome] += 1
                rotulo = evdev.ecodes.bytype.get(ev.type, {}).get(ev.code, str(ev.code))
                if isinstance(rotulo, list):
                    rotulo = rotulo[0]
                detalhe[(nome, str(rotulo))] += 1

    # A MESA MUDOU NO MEIO? — CURA DE 10/09/2026, e ela nasceu de um zero FALSO.
    #
    # A corrida das 02h20 mediu 90 s e imprimiu "NINGUÉM EMITIU NADA". Só que o
    # controle do rádio tinha saído da mesa entre a listagem e a medição: ela
    # desligou o BT, que é exatamente o gesto com que ela CURA o defeito. O
    # instrumento mediu o estado curado e devolveu o veredito do estado doente.
    #
    # É a família que esta casa já nomeia: *o instrumento respondeu sobre outra
    # coisa que não o alvo*. Zero com o alvo fora não é zero — é NADA.
    depois = {c for c, _n, _u in nos_de_entrada()}
    sumiram = [n for c, n, _u in alvos if c not in depois]
    nasceram = sorted(depois - {c for c, _n, _u in alvos})

    print(f"\nEVENTOS EM {args.segundos:g} s:")
    for _, nome, _uniq in alvos:
        print(f"  {conta.get(nome, 0):>7}  {nome[:60]}")
    if detalhe:
        print("\nos que mais apareceram:")
        for (nome, rotulo), quantos in detalhe.most_common(12):
            print(f"  {quantos:>7}  {rotulo:24s} em {nome[:40]}")

    total = sum(conta.values())

    if sumiram:
        for nome in sumiram:
            print(f"\n  !! SAIU DA MESA NO MEIO: {nome}")
        print(resumo(
            f"MEDIÇÃO INVÁLIDA — {len(sumiram)} nó(s) saíram durante a corrida. "
            "Desligar o BT do controle é o gesto com que ela CURA o defeito, "
            "então o que sobrou aqui é o estado curado. "
            f"{total} evento(s) medido(s), e eles NÃO respondem à pergunta. "
            "Refaça com o aparelho na mesa do começo ao fim."))
        return 2

    if nasceram:
        print(f"\n  (nasceram no meio: {', '.join(nasceram)})")

    # A IMU NÃO É CANDIDATA — CURA DE 10/09/2026, na mesma corrida da anterior.
    #
    # Os nós `Motion Sensors` publicam giroscópio e acelerômetro a ~250 Hz sem
    # parar, com o controle imóvel na mesa: 21.884 eventos em 5 s nos dois
    # controles. Eles NÃO chegam ao cursor nem ao teclado — quem faz isso é
    # EV_KEY, EV_REL e o touchpad. Contar a IMU no mesmo balde faz o resumo
    # apontar "o nó que mais emitiu" para o ruído de fundo, e o candidato de
    # verdade (o teclado virtual, que deu ZERO) desaparece embaixo dele.
    imu = sum(q for n, q in conta.items() if "Motion Sensors" in n)
    move_a_tela = total - imu
    if imu:
        print(f"\n  (dos {total}, {imu} são IMU a ~250 Hz — ruído esperado, "
              f"não chega ao cursor)")

    print(resumo(
        f"{move_a_tela} evento(s) NO QUE MEXE NA TELA — teclas, botões, "
        "mouse e touchpad. O nó que mais emitiu é o candidato."
        if move_a_tela else
        f"ZERO no que mexe na tela (a IMU emitiu {imu}, e é ruído esperado). "
        "Se o defeito estava acontecendo agora, ele não nasce em nó de "
        "entrada — olhe o compositor, o teclado na tela ou o aplicativo em "
        "foco."
        if imu else
        "NINGUÉM EMITIU NADA, com a mesa INTEIRA do começo ao fim. Se o defeito "
        "estava acontecendo agora, ele não nasce em nó de entrada — olhe o "
        "compositor, o teclado na tela ou o aplicativo em foco."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
