#!/usr/bin/env python3
"""taxa_de_entrada.py — a taxa real de reports de entrada, cabo x rádio."""

from __future__ import annotations

import argparse
import contextlib
import os
import selectors
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comum import (
    GRAB_DE_TERCEIRO,
    Aparelho,
    cabecalho_do_instrumento,
    censo_da_mesa,
    descobrir_aparelhos,
    estado_do_grab,
    leitura_de_zero,
    ler_texto,
    resumo,
    tabela,
)

try:
    import evdev
    from evdev import ecodes
except ImportError:  # pragma: no cover - só quando falta a dep do projeto
    print("ERRO: python-evdev não encontrado. Rode com o interpretador do venv:")
    print("    .venv/bin/python scripts/ensaios/taxa_de_entrada.py")
    raise SystemExit(3) from None

EIXOS_DO_GIRO = {ecodes.ABS_RX, ecodes.ABS_RY, ecodes.ABS_RZ}
EIXOS_DO_ACELEROMETRO = {ecodes.ABS_X, ecodes.ABS_Y, ecodes.ABS_Z}


class Contagem:
    """Quantos eventos de cada canal saíram de um nó, e por quanto tempo."""

    def __init__(self, caminho: str, nome: str, dono: Aparelho) -> None:
        self.caminho = caminho
        self.nome = nome
        self.dono = dono
        self.e_motion = "Motion Sensors" in nome
        self.sincronismos = 0
        self.giro = 0
        self.acelerometro = 0
        self.botoes = 0
        self.segundos = 0.0

    def hz(self, quantos: int) -> float:
        return quantos / self.segundos if self.segundos > 0 else 0.0


def _nos_de_entrada(aparelho: Aparelho) -> list[tuple[str, str]]:
    """Os `/dev/input/eventN` que pertencem a este hidraw, achados por sysfs."""
    achados: list[tuple[str, str]] = []
    raiz = os.path.join(aparelho.dir_device, "input")
    if not os.path.isdir(raiz):
        return achados
    for entrada in sorted(os.listdir(raiz)):
        if not entrada.startswith("input"):
            continue
        dir_input = os.path.join(raiz, entrada)
        nome = ler_texto(os.path.join(dir_input, "name")).strip()
        for sub in sorted(os.listdir(dir_input)):
            if sub.startswith("event"):
                achados.append((f"/dev/input/{sub}", nome))
    return achados


def medir(contagens: list[Contagem], segundos: float) -> list[str]:
    """Conta eventos por canal durante `segundos`. Devolve as falhas de abertura."""
    seletor = selectors.DefaultSelector()
    falhas: list[str] = []
    abertos: dict[int, Contagem] = {}

    for contagem in contagens:
        try:
            dispositivo = evdev.InputDevice(contagem.caminho)
        except OSError as erro:
            falhas.append(f"{contagem.caminho} ({contagem.nome}): {erro.strerror or erro}")
            continue
        seletor.register(dispositivo, selectors.EVENT_READ)
        abertos[dispositivo.fd] = contagem

    if not abertos:
        return falhas

    inicio = time.monotonic()
    fim = inicio + segundos
    while True:
        restante = fim - time.monotonic()
        if restante <= 0:
            break
        for chave, _ in seletor.select(min(restante, 0.25)):
            contagem = abertos[chave.fileobj.fd]
            try:
                eventos = list(chave.fileobj.read())
            except BlockingIOError:
                continue
            except OSError:
                continue
            for evento in eventos:
                if evento.type == ecodes.EV_SYN and evento.code == ecodes.SYN_REPORT:
                    contagem.sincronismos += 1
                elif evento.type == ecodes.EV_ABS:
                    if evento.code in EIXOS_DO_GIRO and contagem.e_motion:
                        contagem.giro += 1
                    elif evento.code in EIXOS_DO_ACELEROMETRO and contagem.e_motion:
                        contagem.acelerometro += 1
                elif evento.type == ecodes.EV_KEY:
                    contagem.botoes += 1

    decorrido = time.monotonic() - inicio
    for contagem in abertos.values():
        contagem.segundos = decorrido

    for chave in list(seletor.get_map().values()):
        with contextlib.suppress(OSError):
            chave.fileobj.close()
    seletor.close()
    return falhas


def _valor(contagem: Contagem, quantos: int, grab: str) -> str:
    """O texto de uma célula — e o zero DEPENDE do grab, medido, não inferido."""
    if quantos == 0:
        return leitura_de_zero(grab)
    return f"{contagem.hz(quantos):.1f} Hz"


def main() -> int:
    analisador = argparse.ArgumentParser(
        description="Taxa de entrada, giro e acelerômetro por transporte.",
    )
    analisador.add_argument("--segundos", type=float, default=5.0, help="janela (padrão 5 s)")
    analisador.add_argument("--so-fisicos", action="store_true", help="ignorar os vpads")
    analisador.add_argument("--so-vpads", action="store_true", help="ignorar os físicos")
    argumentos = analisador.parse_args()

    aparelhos = descobrir_aparelhos()
    escolhidos = [
        a
        for a in aparelhos
        if not (argumentos.so_fisicos and a.e_vpad) and not (argumentos.so_vpads and not a.e_vpad)
    ]
    contagens: list[Contagem] = []
    for aparelho in escolhidos:
        for caminho, nome in _nos_de_entrada(aparelho):
            if "Touchpad" in nome or "Headset" in nome:
                continue
            contagens.append(Contagem(caminho, nome, aparelho))

    print(
        cabecalho_do_instrumento(
            "taxa_de_entrada.py",
            "o rádio entrega entrada, giro e acelerômetro na mesma taxa que o cabo?",
            bibliotecas=["evdev", "selectors"],
            escreve_no_aparelho=False,
            daemon_precisa_parar=False,
            nos_evdev=[c.caminho for c in contagens],
        )
    )

    print(f"\n  {censo_da_mesa(aparelhos)}")

    if not escolhidos:
        print(resumo("nenhum aparelho selecionado — nada medido."))
        return 1

    if not contagens:
        print(resumo("nenhum nó de entrada encontrado sob os aparelhos — nada medido."))
        return 1

    print(f"\n  medindo {len(contagens)} nó(s) por {argumentos.segundos:.0f} s.")
    print("  >> MEXA E GIRE os controles agora: botão parado não gera evento,")
    print("  >> e zero num controle imóvel não é falha do transporte.")
    print()
    falhas = medir(contagens, argumentos.segundos)

    cabecalho = ["aparelho", "transporte", "nó", "entrada", "giro", "acelerômetro", "botões"]
    linhas: list[list[str]] = []
    mudos: list[str] = []
    for contagem in contagens:
        grab = estado_do_grab(contagem.caminho)
        preso = grab == GRAB_DE_TERCEIRO
        if preso:
            mudos.append(contagem.dono.apelido)
        linhas.append(
            [
                contagem.dono.apelido,
                contagem.dono.transporte,
                "movimento" if contagem.e_motion else "principal",
                _valor(contagem, contagem.sincronismos, grab),
                _valor(contagem, contagem.giro, grab) if contagem.e_motion else "-",
                _valor(contagem, contagem.acelerometro, grab) if contagem.e_motion else "-",
                str(contagem.botoes) if not preso else "-",
            ]
        )
    print(tabela(cabecalho, linhas))

    if falhas:
        print("\n  NÓS QUE NÃO ABRIRAM (falha barulhenta, de propósito):")
        for falha in falhas:
            print(f"    - {falha}")

    if mudos:
        print()
        print("  Os nós físicos acima estão MUDOS, e isso é o produto funcionando:")
        print("  o co-op faz EVIOCGRAB neles, que é exclusivo, e é assim que o")
        print("  Hefesto esconde o controle do jogo. Para medir o APARELHO em vez")
        print("  do que o jogo vê, pare o daemon primeiro.")

    por_transporte: dict[str, list[float]] = {}
    for contagem in contagens:
        if contagem.e_motion and contagem.giro and not contagem.dono.e_vpad:
            por_transporte.setdefault(contagem.dono.transporte, []).append(
                contagem.hz(contagem.giro)
            )

    if len(por_transporte) >= 2:
        pedacos = [
            f"{t}: {sum(v) / len(v):.0f} Hz de giro" for t, v in sorted(por_transporte.items())
        ]
        veredito = "giro medido nos dois transportes — " + "; ".join(pedacos)
    elif por_transporte:
        transporte, valores = next(iter(por_transporte.items()))
        veredito = (
            f"giro medido SÓ no {transporte} ({sum(valores) / len(valores):.0f} Hz). "
            "Nada foi comparado entre transportes."
        )
    else:
        veredito = (
            "nenhum evento de movimento capturado. Se os controles ficaram parados, "
            "repita mexendo; se os físicos aparecem MUDO, é o EVIOCGRAB do co-op."
        )
    print(resumo(veredito))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
