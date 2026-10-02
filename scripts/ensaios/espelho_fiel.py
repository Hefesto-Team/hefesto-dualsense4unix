#!/usr/bin/env python3
"""espelho_fiel.py — o vpad repassa o que o físico manda? Campo a campo."""
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
from hefesto_dualsense4unix.core.formas_do_endereco import mascarar

_BUF = 256

_BASE = {0x01: 1, 0x31: 2}

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

_FLAG_AUDIO = 0x02


@dataclass
class Colheita:
    """O que um nó entregou na janela."""

    caminho: str
    relatorios: int = 0
    audio_descartado: int = 0
    tamanhos: set[int] = field(default_factory=set)
    ids: set[int] = field(default_factory=set)
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
        conhecidos = [a.mac for a in aparelhos if a.mac]
        print("\n  RECUSADO: o par não foi dito. Com mais de um controle na mesa, o")
        print("  primeiro físico e o primeiro vpad da enumeração não são o mesmo")
        print("  jogador. Passe --fisico e --vpad (o quem_e_quem.py diz quem é quem).")
        for a in fisicos(aparelhos):
            print(mascarar(f"    físico: {_hidraw_de(a) or '?'}  {a.mac or a.hidraw}  {a.transporte}", conhecidos))
        for a in vpads(aparelhos):
            print(f"    vpad  : {_hidraw_de(a) or '?'}  {a.rotulo}")
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
    return 1 if perdidos else 0


if __name__ == "__main__":
    raise SystemExit(main())
