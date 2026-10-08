#!/usr/bin/env python3
"""contar_o_que_o_jogo_manda.py — o que um jogo de DualSense escreve no controle, por tiro.

O-QUE-O-JOGO-MANDA-POR-TIRO-SE-CONTA-NO-PC-01 (08/10/2026). Os emuladores de PS5 mostram o
que o jogo PODE pedir, não o que ele pede a cada tiro, e nenhuma fonte pública dá essa taxa.
O caminho legal é medir no PC, com um jogo que fala DualSense, o que ele escreve no hidraw
do controle. Duas decisões da leva do tato dependem do número: «o jogo manda o gatilho uma
vez por arma» e «rearmar por tiro só se um jogo fizer isso».

DUAS METADES, e só uma delas precisa do aparelho
------------------------------------------------
1. O CONTADOR (``contar``, ``tiros_do_audio``, ``ler_gravacao``): puro, lê uma GRAVAÇÃO e
   devolve a tabela. Roda em qualquer lugar, sem aparelho, sem daemon, sem ``/dev/uhid``.
   É o que os testes prendem. ``--ler ARQUIVO`` usa só ele.
2. O GRAVADOR (``--gravar``): roda o daemon do produto neste processo, em lar de mentira,
   com uma escuta no vpad que anota cada ``UHID_OUTPUT`` ANTES da deduplicação do produto (o
   produto descarta o bloco igual ao último entregue: contar na saída dele subconta). O jogo
   atira pelo físico que o daemon liga ao vpad; um vpad que só ouvisse não teria entrada. Nada
   do produto muda: a escuta só anota e repassa. NÃO foi rodado na árvore de desenvolvimento.

O QUE A GRAVAÇÃO É
------------------
Linhas JSON, uma por evento: ``{"t": s, "tipo": "saida", "corpo": "<hex>"}`` (o corpo é o
report 0x02 sem o byte do id, como o ``_replicate_from_output`` o recebe),
``{"t": s, "tipo": "abriu"}`` (o jogo abriu o controle), ``{"t": s, "tipo": "audio",
"energia": x}`` (energia do monitor dos canais 3 e 4, que a ponte já captura) e
``{"t": s, "tipo": "tiro"}`` (marca explícita). Os tiros são as marcas; sem elas, as rajadas
de energia do áudio (uma amostra curta por bala, no PS5); sem nenhum dos dois não há «por
tiro», só «por segundo», e a tabela diz isso.

O QUE ELE RECUSA (``--gravar``)
-------------------------------
Os mesmos motivos do ``latencia_do_tato.py``: ``HOME`` real e daemon no ar em qualquer socket.
Durante a sessão o ensaio é o daemon: com o serviço no ar, os dois disputariam o físico.
"""

from __future__ import annotations

import argparse
import json
import os
import pwd
import statistics
import struct
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

_AQUI = Path(__file__).resolve().parent
_RAIZ = _AQUI.parent.parent
_SRC = _RAIZ / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
if str(_AQUI) not in sys.path:
    sys.path.insert(0, str(_AQUI))

# --- onde as coisas moram no report 0x02 (espelho do vpad; um teste prende a igualdade) --------

OFFSET_FLAG0 = 0
OFFSET_FLAG1 = 1
OFFSET_GATILHO_DIREITO = 10
OFFSET_GATILHO_ESQUERDO = 21
TAMANHO_DO_BLOCO = 11
OFFSET_LEDS_DE_JOGADOR = 43
OFFSET_COR_DA_BARRA = 44
FLAG0_GATILHO_DIREITO = 0x04
FLAG0_GATILHO_ESQUERDO = 0x08
FLAG0_VIBRACAO = 0x03
FLAG0_AUDIO_DO_JOGO = 0xF0
FLAG1_BARRA = 0x04
FLAG1_LEDS_DE_JOGADOR = 0x10
OFFSET_FLAG2 = 38
FLAG2_VIBRACAO_V2 = 0x04
OFFSETS_DE_VOLUME = (4, 5, 6, 7)

#: Modos que desligam o gatilho: o cru (0x00) e o «desligado» oficial da Sony (0x05).
MODOS_DESLIGADO = frozenset({0x00, 0x05})

#: As perguntas da sprint: o mesmo efeito de volta depois de um Off em menos disto...
LIMITE_DO_REARME_S = 0.004
#: ...e o gatilho escrito nesta janela depois de abrir o controle (a graça do vpad é igual).
PRIMEIRA_JANELA_S = 0.5
#: Quanto dura o último tiro (não há outro depois que o feche).
JANELA_DO_ULTIMO_TIRO_S = 0.5
#: Energia acima disto é amostra de háptica; silêncio entre duas amostras separa dois tiros.
LIMIAR_DE_ENERGIA = 0.05
SILENCIO_ENTRE_TIROS_S = 0.08

CATEGORIAS = (
    "gatilho_direito", "gatilho_esquerdo", "luz", "luzes_de_jogador", "motores",
    "audio_do_jogo",
)
TIPOS = frozenset({"saida", "abriu", "audio", "tiro"})

RC_RECUSADO = 2
RC_SEM_DADO = 4


@dataclass(frozen=True)
class Evento:
    """Um evento da gravação: instante (s), tipo e, conforme o tipo, o corpo ou a energia."""

    t: float
    tipo: str
    corpo: bytes = b""
    energia: float = 0.0


# --- a gravação --------------------------------------------------------------------------------


def ler_gravacao(texto: str) -> list[Evento]:
    """Linhas JSON em eventos, em ordem de tempo. Linha torta levanta ``ValueError`` com o número."""
    eventos: list[Evento] = []
    for n, linha in enumerate(texto.splitlines(), 1):
        if not linha.strip():
            continue
        try:
            dado = json.loads(linha)
            tipo = str(dado["tipo"])
            if tipo not in TIPOS:
                raise ValueError(f"tipo {tipo!r} desconhecido")
            eventos.append(Evento(
                float(dado["t"]), tipo, bytes.fromhex(dado.get("corpo", "")),
                float(dado.get("energia", 0.0))))
        except (KeyError, TypeError, ValueError) as erro:
            raise ValueError(f"linha {n} da gravação: {erro}") from erro
    return sorted(eventos, key=lambda e: e.t)


def escrever_gravacao(eventos: Sequence[Evento]) -> str:
    linhas = []
    for e in eventos:
        dado: dict[str, Any] = {"t": round(e.t, 6), "tipo": e.tipo}
        if e.corpo:
            dado["corpo"] = e.corpo.hex()
        if e.tipo == "audio":
            dado["energia"] = e.energia
        linhas.append(json.dumps(dado, sort_keys=True))
    return "\n".join(linhas) + ("\n" if linhas else "")


# --- o que cada corpo carrega ------------------------------------------------------------------


def blocos_de_gatilho(corpo: bytes) -> dict[str, bytes]:
    """Os blocos de gatilho que o corpo ESCREVE (flag ligada e bloco inteiro), por lado."""
    achados: dict[str, bytes] = {}
    if len(corpo) <= OFFSET_FLAG0:
        return achados
    flag0 = corpo[OFFSET_FLAG0]
    for lado, bit, ini in (
        ("direito", FLAG0_GATILHO_DIREITO, OFFSET_GATILHO_DIREITO),
        ("esquerdo", FLAG0_GATILHO_ESQUERDO, OFFSET_GATILHO_ESQUERDO),
    ):
        if flag0 & bit and len(corpo) >= ini + TAMANHO_DO_BLOCO:
            achados[lado] = bytes(corpo[ini : ini + TAMANHO_DO_BLOCO])
    return achados


def categorias_do_corpo(corpo: bytes) -> list[str]:
    """As categorias que ESTE report escreve (um report pode escrever várias)."""
    if len(corpo) <= OFFSET_FLAG1:
        return []
    flag0, flag1 = corpo[OFFSET_FLAG0], corpo[OFFSET_FLAG1]
    categorias = [f"gatilho_{lado}" for lado in blocos_de_gatilho(corpo)]
    if flag1 & FLAG1_BARRA and len(corpo) >= OFFSET_COR_DA_BARRA + 3:
        categorias.append("luz")
    if flag1 & FLAG1_LEDS_DE_JOGADOR and len(corpo) > OFFSET_LEDS_DE_JOGADOR:
        categorias.append("luzes_de_jogador")
    v2 = len(corpo) > OFFSET_FLAG2 and corpo[OFFSET_FLAG2] & FLAG2_VIBRACAO_V2
    if flag0 & FLAG0_VIBRACAO or v2:
        categorias.append("motores")
    if (flag0 & FLAG0_AUDIO_DO_JOGO and len(corpo) > max(OFFSETS_DE_VOLUME)
            and any(corpo[i] for i in OFFSETS_DE_VOLUME)):
        categorias.append("audio_do_jogo")
    return categorias


def tiros_do_audio(
    eventos: Sequence[Evento], limiar: float = LIMIAR_DE_ENERGIA,
    silencio_s: float = SILENCIO_ENTRE_TIROS_S,
) -> list[float]:
    """O instante de cada rajada de energia dos canais 3 e 4: uma amostra de háptica, um tiro."""
    tiros: list[float] = []
    ultimo_acima: float | None = None
    for e in sorted((x for x in eventos if x.tipo == "audio"), key=lambda x: x.t):
        if e.energia <= limiar:
            continue
        if ultimo_acima is None or e.t - ultimo_acima >= silencio_s:
            tiros.append(e.t)
        ultimo_acima = e.t
    return tiros


# --- a contagem --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Categoria:
    total: int
    por_segundo: float
    pico_por_segundo: int


@dataclass(frozen=True)
class Contagem:
    duracao_s: float
    categorias: dict[str, Categoria]
    tiros: int
    origem_dos_tiros: str
    blocos_de_gatilho_por_tiro_mediana: float | None
    blocos_de_gatilho_por_tiro_maximo: int | None
    off_e_o_mesmo_em_menos_de_4ms: int | None
    gatilho_nos_primeiros_meio_segundo: bool | None


def _tempos_de_gatilho(eventos: Sequence[Evento]) -> list[tuple[float, str, bytes]]:
    achados = []
    for e in eventos:
        if e.tipo == "saida":
            for lado, bloco in blocos_de_gatilho(e.corpo).items():
                achados.append((e.t, lado, bloco))
    return achados


def _reescritas_depois_do_off(gatilhos: Sequence[tuple[float, str, bytes]]) -> int | None:
    """Quantas vezes o MESMO efeito voltou em menos de 4 ms depois de um Off, por lado.

    Sem nenhum bloco de gatilho na gravação, ``None``: o jogo não escreveu gatilho, e «não»
    seria uma resposta que a gravação não tem.
    """
    if not gatilhos:
        return None
    achados = 0
    for lado in ("direito", "esquerdo"):
        ultimo_ativo: bytes | None = None
        off_em: float | None = None
        for t, l, bloco in gatilhos:
            if l != lado:
                continue
            if bloco[0] in MODOS_DESLIGADO:
                off_em = t
                continue
            if off_em is not None and bloco == ultimo_ativo and t - off_em < LIMITE_DO_REARME_S:
                achados += 1
            ultimo_ativo, off_em = bloco, None
    return achados


def _gatilho_logo_depois_de_abrir(
    eventos: Sequence[Evento], gatilhos: Sequence[tuple[float, str, bytes]]
) -> bool | None:
    aberturas = sorted(e.t for e in eventos if e.tipo == "abriu")
    if not aberturas or not gatilhos:
        return None
    for i, aberto in enumerate(aberturas):
        proxima = aberturas[i + 1] if i + 1 < len(aberturas) else float("inf")
        primeiro = next((t for t, _l, _b in gatilhos if aberto <= t < proxima), None)
        if primeiro is not None and primeiro - aberto <= PRIMEIRA_JANELA_S:
            return True
    return False


def contar(eventos: Sequence[Evento]) -> Contagem:
    """Por categoria (total, média e pico por segundo) e as três perguntas da sprint."""
    if not eventos:
        raise ValueError("gravação vazia: nada a contar")
    inicio = min(e.t for e in eventos)
    duracao = max(e.t for e in eventos) - inicio
    base = max(duracao, 1.0)
    por_categoria: dict[str, list[float]] = {c: [] for c in CATEGORIAS}
    for e in eventos:
        if e.tipo == "saida":
            for c in categorias_do_corpo(e.corpo):
                por_categoria[c].append(e.t)
    categorias = {}
    for nome, tempos in por_categoria.items():
        baldes: dict[int, int] = {}
        for t in tempos:
            baldes[int(t - inicio)] = baldes.get(int(t - inicio), 0) + 1
        categorias[nome] = Categoria(
            len(tempos), len(tempos) / base, max(baldes.values(), default=0))

    marcados = sorted(e.t for e in eventos if e.tipo == "tiro")
    do_audio = tiros_do_audio(eventos)
    tiros, origem = (marcados, "marcas") if marcados else (
        (do_audio, "áudio dos canais 3 e 4") if do_audio else ([], "nenhuma"))

    gatilhos = _tempos_de_gatilho(eventos)
    por_tiro: list[int] = []
    for i, t in enumerate(tiros):
        fim = tiros[i + 1] if i + 1 < len(tiros) else t + JANELA_DO_ULTIMO_TIRO_S
        por_tiro.append(sum(1 for tg, _l, _b in gatilhos if t <= tg < fim))
    return Contagem(
        duracao_s=duracao,
        categorias=categorias,
        tiros=len(tiros),
        origem_dos_tiros=origem,
        blocos_de_gatilho_por_tiro_mediana=statistics.median(por_tiro) if por_tiro else None,
        blocos_de_gatilho_por_tiro_maximo=max(por_tiro) if por_tiro else None,
        off_e_o_mesmo_em_menos_de_4ms=_reescritas_depois_do_off(gatilhos),
        gatilho_nos_primeiros_meio_segundo=_gatilho_logo_depois_de_abrir(eventos, gatilhos),
    )


CABECALHO_DA_TABELA = (
    "| jogo | transporte | controle | categoria | total | por segundo | pico em 1 s |\n"
    "| --- | --- | --- | --- | --- | --- | --- |"
)


def _sim_nao(valor: bool | None) -> str:
    return "sem dado" if valor is None else ("sim" if valor else "não")


def linhas_da_tabela(jogo: str, transporte: str, controle: str, c: Contagem) -> list[str]:
    return [
        f"| {jogo} | {transporte} | {controle} | {nome} | {cat.total} | "
        f"{cat.por_segundo:.1f} | {cat.pico_por_segundo} |"
        for nome, cat in c.categorias.items()
    ]


def respostas(c: Contagem) -> list[str]:
    """As três perguntas da sprint, cada uma com a resposta e o que a sustenta."""
    if c.blocos_de_gatilho_por_tiro_mediana is None:
        por_tiro = ("blocos de gatilho por tiro: sem dado (a gravação não tem tiros marcados "
                    "nem rajadas de áudio nos canais 3 e 4)")
    else:
        por_tiro = (
            f"blocos de gatilho por tiro: mediana {c.blocos_de_gatilho_por_tiro_mediana:g}, "
            f"máximo {c.blocos_de_gatilho_por_tiro_maximo} em {c.tiros} tiro(s) "
            f"(tiros pelas {c.origem_dos_tiros})")
    return [
        por_tiro,
        "o jogo escreve Off e o mesmo efeito em menos de 4 ms: "
        + ("sem dado (a gravação não tem bloco de gatilho)"
           if c.off_e_o_mesmo_em_menos_de_4ms is None
           else f"sim ({c.off_e_o_mesmo_em_menos_de_4ms} vez(es))"
           if c.off_e_o_mesmo_em_menos_de_4ms else "não"),
        "o jogo escreve o gatilho nos primeiros 0,5 s depois de abrir o controle: "
        + _sim_nao(c.gatilho_nos_primeiros_meio_segundo),
    ]


# --- o gravador (bancada) ----------------------------------------------------------------------


def corpo_do_uhid_output(data: bytes) -> bytes | None:
    """O corpo do report 0x02 (sem o id) de um ``UHID_OUTPUT`` cru; ``None`` se não for o 0x02."""
    from hefesto_dualsense4unix.core import ds_output_report as rep
    from hefesto_dualsense4unix.integrations import uhid_gamepad as ug

    fim = 4 + ug.HID_MAX_DESCRIPTOR_SIZE
    if len(data) < fim + 2:
        return None
    tamanho = struct.unpack("<H", data[fim : fim + 2])[0]
    report = data[4 : 4 + min(tamanho, ug.HID_MAX_DESCRIPTOR_SIZE)]
    if len(report) < 2 or report[0] != rep.USB_REPORT_ID:
        return None
    return bytes(report[1:])


def instalar_escuta(eventos: list[Evento]) -> Callable[[], None]:
    """Põe no vpad do PRODUTO uma escuta que anota o que o jogo escreve; devolve quem a tira.

    A escuta embrulha ``UhidDualSense._handle_event`` na CLASSE, então vale para todo vpad que o
    daemon criar neste processo, pelo uhid ou pelo gadget USB (que entrega o output do jogo pelo
    mesmo ``_handle_event``). Anota o ``UHID_OPEN`` e cada ``UHID_OUTPUT`` que o vpad conta como
    saída do jogo (o eco puro do driver fica de fora), no instante em que o evento CHEGA e com o
    corpo cru, antes de qualquer deduplicação. O evento segue inteiro para o vpad: o que o
    produto faz com ele não muda.
    """
    from hefesto_dualsense4unix.integrations import uhid_gamepad as ug

    original = ug.UhidDualSense.__dict__["_handle_event"]

    def _handle_event(self: Any, data: bytes) -> None:
        t = self.time_fn()
        tipo = struct.unpack("<I", data[:4])[0]
        antes = self._output_count
        original(self, data)
        if tipo == ug.UHID_OPEN:
            eventos.append(Evento(t, "abriu"))
        elif tipo == ug.UHID_OUTPUT and self._output_count > antes:
            corpo = corpo_do_uhid_output(data)
            if corpo is not None:
                eventos.append(Evento(t, "saida", corpo))

    ug.UhidDualSense._handle_event = _handle_event

    def tirar() -> None:
        ug.UhidDualSense._handle_event = original

    return tirar


def gravar_no_aparelho(
    segundos: float, rodar_o_daemon: Callable[[], int] | None = None
) -> list[Evento]:
    """O daemon do produto NESTE processo, com a escuta no vpad, por ``segundos``.

    BANCADA. O jogo só atira com um controle que responde, e quem liga o físico ao vpad é o
    daemon: um vpad que só ouvisse não teria entrada, e o jogo escreveria no controle que a
    tem. Então, durante a sessão, o ensaio É o daemon (com o serviço parado antes, o que a
    recusa do daemon no ar garante) e a escuta anota o que o jogo escreve no vpad. No fim do
    prazo o processo manda SIGTERM a si mesmo, e o daemon para pelo caminho normal dele. A
    escuta sai por qualquer caminho.
    """
    import signal
    import threading

    if rodar_o_daemon is None:
        from hefesto_dualsense4unix.daemon.main import run_daemon

        rodar_o_daemon = run_daemon
    eventos: list[Evento] = []
    tirar = instalar_escuta(eventos)
    prazo = threading.Timer(segundos, os.kill, (os.getpid(), signal.SIGTERM))
    prazo.daemon = True
    try:
        prazo.start()
        rodar_o_daemon()
    finally:
        prazo.cancel()
        tirar()
    return list(eventos)


# --- a linha de comando ------------------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Conta o que um jogo escreve no controle, por tiro.")
    grupo = p.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--ler", type=Path, help="conta uma gravação (só leitura, em qualquer lugar)")
    grupo.add_argument("--gravar", type=float, metavar="SEGUNDOS",
                       help="bancada: sobe o vpad que só ouve por estes segundos")
    p.add_argument("--saida", type=Path, help="com --gravar: onde guardar a gravação")
    p.add_argument("--jogo", default="PRAGMATA")
    p.add_argument("--transporte", choices=("cabo", "radio"), default="cabo")
    p.add_argument("--controle", default="P1", help="rótulo na tabela: P1 a P4")
    return p


def _imprimir(args: argparse.Namespace, eventos: Sequence[Evento]) -> int:
    contagem = contar(eventos)
    print(f"o que o jogo manda — {date.today():%d/%m/%Y} — {args.jogo}, {args.transporte}, "
          f"{args.controle} — {contagem.duracao_s:.1f} s de gravação")
    print(CABECALHO_DA_TABELA)
    print("\n".join(linhas_da_tabela(args.jogo, args.transporte, args.controle, contagem)))
    print()
    print("\n".join(f"- {linha}" for linha in respostas(contagem)))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.ler is not None:
        try:
            return _imprimir(args, ler_gravacao(args.ler.read_text(encoding="utf-8")))
        except (OSError, ValueError) as erro:
            print(f"SEM DADO: {erro}")
            return RC_SEM_DADO
    import latencia_do_tato as lat

    motivos = lat.recusas(dict(os.environ), os.getuid(), pwd.getpwuid(os.getuid()).pw_dir)
    if args.saida is None:
        motivos.append("--gravar pede --saida: a gravação é o recibo e não pode se perder")
    if motivos:
        for m in motivos:
            print(f"RECUSADO: {m}")
        return RC_RECUSADO
    try:
        eventos = gravar_no_aparelho(args.gravar)
        args.saida.write_text(escrever_gravacao(eventos), encoding="utf-8")
        return _imprimir(args, eventos)
    except (OSError, ValueError) as erro:
        print(f"SEM DADO: {erro}")
        return RC_SEM_DADO


if __name__ == "__main__":
    raise SystemExit(main())
