#!/usr/bin/env python3
"""espelho_fiel.py — o vpad repassa o que o físico manda? Campo a campo.

A PERGUNTA QUE ELE RESPONDE
----------------------------
*O controle virtual é um espelho FIEL do físico, ou perde alguma coisa pelo
caminho?* — e, quando perde, **qual campo**, em vez de "o giroscópio parece
ruim".

Ideia dela, 16/08/2026: *"conseguimos parear o que o controle físico manda e o
que o virtual manda?"*. É a Pedra de Roseta do projeto aplicada ao par
físico x virtual, em vez de cabo x rádio.

O QUE JÁ SE SABIA, E O QUE FALTAVA
-----------------------------------
O `taxa_no_hidraw.py` já mede QUANTOS relatórios cada nó entrega na mesma
janela. Em 16/08 isso foi medido com a mão dela e deu, em 10 s::

    canal        vpad     físico
    gamepad       286      0 (grab do daemon, correto)
    giroscópio  7 231     19 435
    touchpad    2 807      3 660

Os números levantam a pergunta e não a respondem: **~37% dos eventos do
giroscópio.** Pode ser decimação legítima (o vpad publica a 250 Hz, o físico
entrega mais), pode ser perda. Contagem não distingue as duas.

Este instrumento olha o CONTEÚDO: pega os dois fluxos na mesma janela e compara
campo a campo — eixos, gatilhos, botões, giroscópio, acelerômetro, touchpad.

O QUE ELE MEDE, E O QUE NÃO MEDE
---------------------------------
**Mede:** se cada campo VARIA nos dois lados; a amplitude de cada um; e se o
vpad reproduz os valores do físico ou os achata. Um campo que se mexe no físico
e fica parado no vpad é perda, e o instrumento o nomeia.

**Não mede:** latência entre os dois (exigiria carimbo comum, que não existe no
fio), nem se o JOGO usa o que chega. Este é o andar do transporte.

A ARMADILHA QUE ELE EVITA
--------------------------
Comparar amostras colhidas em janelas DIFERENTES. Se o físico for lido primeiro
e o vpad depois, o gesto humano no meio muda tudo e a diferença é do gesto, não
do repasse. Aqui os dois nós são lidos em threads simultâneas, na mesma janela,
e o instrumento **recusa** comparar se um dos lados não recebeu nada.

E a lição de 16/08, que custou um diagnóstico errado: **um ensaio mede UM
gesto**. Pedir "gire o controle E toque no touchpad" produziu `0/8 bytes
variam` no touchpad e quase virou acusação ao produto — com o gesto isolado,
os bytes variavam normalmente. Por isso este instrumento pede um gesto por vez
e diz qual.

USO
    espelho_fiel.py                      # descobre os nós sozinho
    espelho_fiel.py --segundos 8
    espelho_fiel.py --fisico /dev/hidraw5 --vpad /dev/hidraw4
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comum import (
    Aparelho,
    abrir_no_hidraw,
    cabecalho_do_instrumento,
    descobrir_aparelhos,
    fisicos,
    resumo,
    tabela,
    vpads,
)

#: Buffer folgado: um `read()` de hidraw devolve UM relatório, e o maior é o
#: `0x31` do rádio com 78 bytes.
_BUF = 256

#: Onde cada campo mora, por transporte. O deslocamento do `struct
#: dualsense_input_report` é 1 no USB (`0x01` + payload) e 2 no BT (`0x31` +
#: 1 byte de cabeçalho) — os mesmos números do
#: `core/physical_report_reader._USB_STRUCT_BASE`/`_BT_STRUCT_BASE`, e é de lá
#: que eles vêm. Duplicá-los aqui com outro valor seria criar uma segunda
#: verdade sobre o mesmo aparelho.
_BASE = {0x01: 1, 0x31: 2}

#: Os campos, em deslocamento DENTRO do payload. Batem com o
#: `struct dualsense_input_report` do `hid-playstation.c`.
_CAMPOS: tuple[tuple[str, int, int], ...] = (
    ("analógico esq. X", 0, 1),
    ("analógico esq. Y", 1, 1),
    ("analógico dir. X", 2, 1),
    ("analógico dir. Y", 3, 1),
    ("gatilho L2", 4, 1),
    ("gatilho R2", 5, 1),
    ("botões (face+d-pad)", 8, 1),
    ("botões (ombros+start)", 9, 1),
    ("botões (PS/touch/mic)", 10, 1),
    ("giroscópio", 15, 6),
    ("acelerômetro", 21, 6),
    ("touchpad", 32, 8),
)

#: O bit de ÁUDIO do byte 1 num `0x31`: o relatório carrega Opus, não estado de
#: entrada. Mesmo número do `physical_report_reader.INPUT_FLAG_AUDIO`, e pelo
#: mesmo motivo — em 16/08 ele prendeu o MIC e o PS por ser lido como botão.
_FLAG_AUDIO = 0x02


@dataclass
class Colheita:
    """O que um nó entregou na janela."""

    caminho: str
    relatorios: int = 0
    audio_descartado: int = 0
    tamanhos: set[int] = field(default_factory=set)
    ids: set[int] = field(default_factory=set)
    #: Por campo: o conjunto de valores distintos vistos (como bytes).
    valores: dict[str, set[bytes]] = field(default_factory=dict)
    erro: str | None = None


def _colher(caminho: str, segundos: float) -> Colheita:
    """Lê um nó por `segundos` e devolve o que passou. Nunca levanta."""
    c = Colheita(caminho=caminho)
    try:
        no = abrir_no_hidraw(caminho, escrita=False)
    except OSError as exc:
        c.erro = f"não abriu ({exc.errno})"
        return c
    fd = no.fd
    os.set_blocking(fd, False)
    fim = time.monotonic() + segundos
    try:
        while time.monotonic() < fim:
            try:
                dados = os.read(fd, _BUF)
            except BlockingIOError:
                time.sleep(0.001)
                continue
            except OSError as exc:
                c.erro = f"leitura parou ({exc.errno})"
                break
            if not dados:
                continue
            rid = dados[0]
            base = _BASE.get(rid)
            if base is None:
                continue
            # O relatório de áudio tem o MESMO id e o MESMO tamanho do de
            # entrada; só este bit os separa. Contá-lo como entrada foi o
            # defeito que prendeu MIC e PS em 16/08.
            if rid == 0x31 and len(dados) > 1 and (dados[1] & _FLAG_AUDIO):
                c.audio_descartado += 1
                continue
            c.relatorios += 1
            c.tamanhos.add(len(dados))
            c.ids.add(rid)
            for nome, desloc, tam in _CAMPOS:
                ini = base + desloc
                if ini + tam <= len(dados):
                    c.valores.setdefault(nome, set()).add(bytes(dados[ini : ini + tam]))
    finally:
        with_close = getattr(no, "fechar", None)
        if callable(with_close):
            with_close()
        else:
            os.close(fd)
    return c


def _hidraw_de(ap: Aparelho) -> str | None:
    """O `/dev/hidrawN` de um aparelho descoberto."""
    caminho = getattr(ap, "caminho_hidraw", None)
    return str(caminho) if caminho else None


def _veredito(nome: str, fis: int, vp: int) -> str:
    """O que a comparação de UM campo diz, sem inventar o que não mediu."""
    if fis <= 1 and vp <= 1:
        return "parado nos dois — o gesto não tocou este campo"
    if fis > 1 and vp <= 1:
        return "PERDIDO — mexe no físico e chega parado no vpad"
    if fis <= 1 and vp > 1:
        return "só no vpad — o daemon está inventando movimento?"
    razao = vp / fis
    if razao >= 0.80:
        return f"repassado ({razao:.0%} dos valores distintos)"
    if razao >= 0.30:
        return f"ACHATADO — só {razao:.0%} dos valores distintos chegam"
    return f"QUASE PERDIDO — {razao:.0%} dos valores distintos"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--segundos", type=float, default=8.0)
    ap.add_argument("--fisico", help="/dev/hidrawN do controle físico")
    ap.add_argument("--vpad", help="/dev/hidrawN do controle virtual")
    ap.add_argument(
        "--gesto",
        default="mexa UM analógico em círculos",
        help="o gesto que você vai fazer — ele entra no relatório",
    )
    args = ap.parse_args()

    print(
        cabecalho_do_instrumento(
            "espelho_fiel.py",
            "o vpad repassa, campo a campo, o que o físico manda?",
            bibliotecas=["os", "threading", "time"],
            escreve_no_aparelho=False,
            daemon_precisa_parar=False,
        )
    )

    caminho_fis, caminho_vp = args.fisico, args.vpad
    if not (caminho_fis and caminho_vp):
        aparelhos = descobrir_aparelhos()
        fs = [x for x in (_hidraw_de(a) for a in fisicos(aparelhos)) if x]
        vs = [x for x in (_hidraw_de(a) for a in vpads(aparelhos)) if x]
        caminho_fis = caminho_fis or (fs[0] if fs else None)
        caminho_vp = caminho_vp or (vs[0] if vs else None)
    if not caminho_fis or not caminho_vp:
        print("\n  não achei os dois nós. Passe --fisico e --vpad à mão.")
        print(f"    físico: {caminho_fis or '(não achado)'}")
        print(f"    vpad  : {caminho_vp or '(não achado)'}")
        return 2

    print(f"\n  físico: {caminho_fis}    vpad: {caminho_vp}")
    print(f"\n  >>> {args.gesto.upper()}, SEM PARAR, por {args.segundos:.0f} s <<<")
    print("      (UM gesto por vez — gesto composto já produziu ausência falsa)")
    time.sleep(1.0)

    saida: dict[str, Colheita] = {}
    fios = [
        threading.Thread(
            target=lambda c=c: saida.__setitem__(c, _colher(c, args.segundos)),
            daemon=True,
        )
        for c in (caminho_fis, caminho_vp)
    ]
    for f in fios:
        f.start()
    for f in fios:
        f.join()

    fis = saida.get(caminho_fis)
    vp = saida.get(caminho_vp)
    if fis is None or vp is None:
        print("\n  colheita incompleta.")
        return 1
    for rot, c in (("físico", fis), ("vpad", vp)):
        if c.erro:
            print(f"\n  {rot}: {c.erro}")
            if "13" in c.erro:
                print("    (o broker esconde o hidraw do físico — é esperado;")
                print("     rode como o daemon roda, ou meça só o vpad)")
    if not fis.relatorios or not vp.relatorios:
        print("\n  UM DOS LADOS NÃO ENTREGOU NADA — comparar seria inventar.")
        print(f"    físico: {fis.relatorios} relatórios | vpad: {vp.relatorios}")
        return 1

    print(
        "\n"
        + tabela(
            ["", "físico", "vpad"],
            [
                ["relatórios", str(fis.relatorios), str(vp.relatorios)],
                [
                    "ids",
                    ",".join(hex(i) for i in sorted(fis.ids)),
                    ",".join(hex(i) for i in sorted(vp.ids)),
                ],
                [
                    "tamanhos",
                    ",".join(str(t) for t in sorted(fis.tamanhos)),
                    ",".join(str(t) for t in sorted(vp.tamanhos)),
                ],
                [
                    "áudio descartado",
                    str(fis.audio_descartado),
                    str(vp.audio_descartado),
                ],
            ],
        )
    )

    linhas = []
    perdidos = []
    for nome, _d, _t in _CAMPOS:
        nf = len(fis.valores.get(nome, ()))
        nv = len(vp.valores.get(nome, ()))
        v = _veredito(nome, nf, nv)
        linhas.append([nome, str(nf), str(nv), v])
        if "PERDIDO" in v or "ACHATADO" in v:
            perdidos.append(nome)
    print("\n" + tabela(["campo", "físico", "vpad", "o que isso diz"], linhas))

    if perdidos:
        print(resumo("O vpad NÃO é fiel nestes campos: " + ", ".join(perdidos)))
    else:
        print(
            resumo(
                "Todo campo que se mexeu no físico chegou ao vpad. "
                "Isto NÃO diz que o jogo usa — só que o repasse entregou."
            )
        )
    print(
        "\n  Repita com um gesto por vez: analógico, gatilho, botões,\n"
        "  giroscópio (girar o controle), touchpad (deslizar o dedo).\n"
        "  Um campo 'parado nos dois' só quer dizer que o gesto não o tocou."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
