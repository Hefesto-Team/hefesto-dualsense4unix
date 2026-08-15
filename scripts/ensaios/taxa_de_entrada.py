#!/usr/bin/env python3
"""taxa_de_entrada.py — a taxa real de reports de entrada, cabo x rádio.

A PERGUNTA QUE ELE RESPONDE
----------------------------
*O rádio entrega a entrada na mesma taxa que o cabo?* E, separadamente, porque
são canais distintos que a casa vinha tratando como um só: *qual a taxa do
giroscópio, e qual a do acelerômetro?*

O acelerômetro **não aparece em célula medida nenhuma do mapa de canais**. Esta
é a dívida que este instrumento paga: ele mede giro e acelerômetro em colunas
separadas, porque `movimento.giro` estar verde nunca foi promessa de que o
acelerômetro chega.

COMO ELE MEDE, E POR QUE ASSIM
-------------------------------
Por **evdev**, o mesmo caminho que os jogos usam. O `hid_playstation` recebe o
report no transporte (0x01 no cabo, 0x31 com CRC-32 no rádio), o decodifica e
emite os eventos; contar aqui é contar o que o jogo receberia. Não se abre
hidraw, não se disputa nada com o daemon.

A conta é feita por CANAL, não por evento solto:

  entrada  ..... `SYN_REPORT` do nó principal — botões e analógicos. Só sai
                 quando algo MUDA, então parado ele fica perto de zero, e isso
                 é o correto, não uma falha;
  giro ......... `ABS_RX`/`ABS_RY`/`ABS_RZ` do nó *Motion Sensors*;
  acelerômetro . `ABS_X`/`ABS_Y`/`ABS_Z` do MESMO nó.

Giro e acelerômetro chegam no mesmo report do aparelho, mas em eixos separados,
e o kernel só emite o eixo que mudou. É por isso que as duas colunas podem
divergir — e é justamente essa divergência que o mapa nunca mediu.

O BURACO QUE ELE SABE NOMEAR (medido em 15/08/2026)
----------------------------------------------------
**Os nós evdev FÍSICOS ficam mudos para leitores externos** quando o co-op está
ativo: o daemon faz `EVIOCGRAB` neles, e o grab é exclusivo. Em dois ensaios,
evento nenhum saiu dos MACs físicos — só dos vpads. Isso é comportamento
CORRETO (é assim que o Hefesto esconde o controle do jogo), mas nunca tinha sido
medido, e explica por que um instrumento ingênuo mede zero e conclui besteira.

Por isso este instrumento, ao ver zero, **PERGUNTA ao nó se o grab está livre**
(`estado_do_grab`, a única prova que o kernel oferece: tentar, e devolver na
hora) antes de escrever a célula. Grab de terceiro sai `MUDO (EVIOCGRAB de
terceiro)`; grab livre sai `0 (o controle não emitiu)`. A diferença entre as
duas frases é a diferença entre uma medição e uma calúnia contra o aparelho.

Até 15/08/2026 ele decidia isso por INFERÊNCIA — zero, nó físico, daemon vivo —
e os três indícios andam juntos com o grab sem serem o grab: com o co-op
desligado, um controle parado saía como `MUDO (EVIOCGRAB)` sem ninguém ter
grabado nada.

Com o daemon vivo, portanto, o que se mede de verdade é o **vpad** — que é o que
o jogo vê, e é medida legítima, só que de outra coisa. As duas leituras estão na
tabela, rotuladas.

PRECISA DO DAEMON PARADO?
--------------------------
Depende do que se quer:
  - medir o que O JOGO recebe .......... daemon RODANDO, meça os vpads;
  - medir o que O APARELHO entrega ..... daemon PARADO, meça os físicos.
O instrumento detecta em qual dos dois mundos está e diz na tabela.

USO
    taxa_de_entrada.py                    # 5 s, tudo que achar
    taxa_de_entrada.py --segundos 15      # janela maior, medida mais firme
    taxa_de_entrada.py --so-fisicos
"""

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
    """Os `/dev/input/eventN` que pertencem a este hidraw, achados por sysfs.

    Resolve pelo device HID pai a cada chamada. Os números NÃO são estáveis:
    em 15/08/2026, entre duas leituras com segundos de diferença, um controle
    reapareceu com outro `eventN`. Quem guarda caminho mede o aparelho errado.
    """
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
    """O texto de uma célula — e o zero DEPENDE do grab, medido, não inferido.

    Até 15/08/2026 este instrumento decidia "MUDO" por INFERÊNCIA: zero, nó
    físico, daemon rodando. Três indícios que costumam andar juntos com o
    `EVIOCGRAB`, mas nenhum deles É o grab — com o daemon rodando e o co-op
    desligado, um controle parado saía como "MUDO (EVIOCGRAB)" sem que
    ninguém tivesse grabado coisa alguma, que é a calúnia ao contrário.
    Agora o grab é PERGUNTADO ao nó (`estado_do_grab`), e a frase vem de
    `leitura_de_zero`, uma só, compartilhada por todo instrumento da casa.
    """
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

    # A descoberta vem ANTES do cabeçalho de propósito: ela é silenciosa, e o
    # cabeçalho precisa saber quais nós vai ler para poder declarar o grab de
    # cada um — que é a metade do E3 sem a qual "zero eventos" é ambíguo.
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

    # O grab é PERGUNTADO a cada nó, depois de medir. Antes, e não depois,
    # seria pior: a tentativa de grab (a única prova que o kernel oferece) tira
    # o nó de quem o segura por microssegundos, e fazer isso no meio da janela
    # de contagem contaminaria a própria medida.
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

    # SÓ os físicos entram na comparação de transporte. O vpad forja BUS_USB e
    # entraria na média do cabo — o que já falseou esta tabela em 15/08/2026.
    # Ele não fala com aparelho nenhum: mede a saída do produto, não o canal.
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
