"""O-SERVIDOR-DE-SOM-TEM-UM-LEITOR-SO-01 — o servidor de som tem um leitor só.

**O DEFEITO, medido em 27/09/2026 no daemon dela:** 22 a 23 `pactl` por
segundo, cada um um fork e um cliente novo no `pipewire-pulse`. Medido de novo
em 28/09, antes da cura, com o código de então contra o servidor de mentira
desta régua (quatro controles no rádio): o canal do microfone custava 20
`pactl` por volta de 2 s, a luz do mic 3 por segundo, o vigia do alto-falante
2 a cada 0,4 s, as pontes 12 por volta e o microfone do rádio 4 por segundo.

**AS TRÊS RÉGUAS DA SPRINT, e as três perguntam ao PROCESSO, não ao texto:**

1. **O servidor de mentira que conta os clientes.** Um `pactl` de mentira na
   frente do `PATH` anota cada pergunta que chega a ele. Cem tiques dos cinco
   leitores do daemon, com o retrato vivo e sem evento, fazem ZERO perguntas —
   e as respostas são as mesmas que o servidor daria. Um evento relê UM tipo.
2. **A exaustiva de dono.** Toda pergunta de leitura escrita em `src/` é
   achada pela árvore do código e entregue a um executor; cada executor é
   chamado de verdade com o retrato vivo, e o servidor de mentira diz se
   alguém além do retrato perguntou. A palavra só ACHA a pergunta; quem julga
   é o processo que chegou (ou não) ao servidor.
3. **Sem servidor, «não sei»:** o `subscribe` cai, e os leitores recebem a
   falha de sempre sem perguntar nada; o servidor volta, e o retrato se refaz.

**MORDIDA DA SPRINT:** devolva o `_ler_o_canal` ao `pactl` (o
`retrato_do_som.responder` devolvendo sempre `None`) e a régua 1 conta 5
perguntas por controle por volta.

**NENHUM TESTE DESTE ARQUIVO TOCA O SERVIDOR DE SOM DE QUEM O RODA:** o
servidor é um script num diretório temporário, na frente do `PATH`, e a
fixture recusa se o `pactl` que o produto acharia for outro.
"""

from __future__ import annotations

import ast
import asyncio
import contextlib
import errno
import os
import shutil
import stat
import time
from collections import Counter
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import retrato_do_som as rs

SRC = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"

# ---------------------------------------------------------------------------
# O servidor de mentira — quatro controles no rádio, faixa forjada
# ---------------------------------------------------------------------------

HEX = ("0000a1", "0000a2", "0000a3", "0000a4")
UNIQS = tuple(f"aa:bb:cc:00:00:{h[-2:]}" for h in HEX)
ENDPOINT = ("alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
            "Controller_HEFESTO{h}-00.HiFi__Speaker__sink")
HDMI = "alsa_output.pci-0000_0a_00.1.hdmi-stereo"


def _vol(canais: int, pct: int) -> str:
    bruto = int(65536 * pct / 100)
    nomes = {1: ["mono"], 2: ["front-left", "front-right"],
             4: ["front-left", "front-right", "rear-left", "rear-right"]}[canais]
    return ",   ".join(f"{c}: {bruto} / {pct}% / -23.88 dB" for c in nomes)


def _no(cabeca: str, indice: int, nome: str, desc: str, spec: str, estado: str,
        mudo: bool, vol: str, extra: str) -> str:
    """Um bloco de `pactl list sinks|sources` com o desenho que o `pactl` 16.1 imprime."""
    canais = ("front-left,front-right" if "2ch" in spec else
              "mono" if "1ch" in spec else
              "front-left,front-right,rear-left,rear-right")
    return "\n".join([
        f"{cabeca} #{indice}",
        f"\tState: {estado}",
        f"\tName: {nome}",
        f"\tDescription: {desc}",
        "\tDriver: PipeWire",
        f"\tSample Specification: {spec}",
        f"\tChannel Map: {canais}",
        "\tOwner Module: 4294967295",
        f"\tMute: {'yes' if mudo else 'no'}",
        f"\tVolume: {vol}",
        "\t        balance 0.00",
        "\tBase Volume: 65536 / 100% / 0.00 dB",
        extra,
        "\tLatency: 0 usec, configured 0 usec",
        "\tFlags: HARDWARE DECIBEL_VOLUME LATENCY ",
        "\tProperties:",
        f'\t\tnode.name = "{nome}"',
        f'\t\tdevice.description = "{desc}"',
        f'\t\tobject.serial = "{indice}"',
        "\tFormats:",
        "\t\tpcm",
    ]) + "\n"


def _textos(*, mic_mudo: str = "") -> dict[str, str]:
    """Os arquivos do servidor. O CURTO é escrito à parte, pelo `printf` do `pactl`
    — nunca pela síntese do retrato, que é o que ele mede."""
    sinks = [(101, HDMI, "Saida HDMI", "s16le 2ch 48000Hz", "SUSPENDED", _vol(2, 100))]
    sinks += [(201 + i, ENDPOINT.format(h=h), "DualSense wireless controller (PS5)",
               "float32le 4ch 48000Hz", "RUNNING" if i == 0 else "SUSPENDED", _vol(4, 40))
              for i, h in enumerate(HEX)]
    sinks += [(301 + i, f"hefesto_som_{h}", f"Alto-falante do Controle {i + 1}",
               "s16le 2ch 48000Hz", "SUSPENDED", _vol(2, 100)) for i, h in enumerate(HEX)]
    fontes = [(ix, f"{n}.monitor", f"Monitor of {d}", sp, e, v) for ix, n, d, sp, e, v in sinks]
    fontes.append((501, "alsa_input.pci-0000_0c_00.4.analog-stereo", "Microfone da placa",
                   "s32le 2ch 48000Hz", "SUSPENDED", _vol(2, 100)))
    fontes += [(401 + i, f"hefesto_mic_{h}", f"Microfone do Controle {i + 1}",
                "s16le 1ch 48000Hz", "RUNNING" if i == 2 else "SUSPENDED", _vol(1, 100))
               for i, h in enumerate(HEX)]
    longo_s = "\n".join(
        _no("Sink", ix, n, d, sp, e, False, v, f"\tMonitor Source: {n}.monitor")
        for ix, n, d, sp, e, v in sinks)
    longo_f = "\n".join(
        _no("Source", ix, n, d, sp, e, n == mic_mudo, v,
            f"\tMonitor of Sink: {n[:-8] if n.endswith('.monitor') else 'n/a'}")
        for ix, n, d, sp, e, v in fontes)
    fluxo = ("{cab} #{ix}\n\tDriver: PipeWire\n\tOwner Module: n/a\n\tClient: {cli}\n"
             "\t{alvo_cab}: {alvo}\n\tSample Specification: {spec}\n\tChannel Map: {mapa}\n"
             "\tFormat: pcm\n\tCorked: no\n\tMute: no\n\tVolume: {vol}\n"
             "\t        balance 0.00\n\tBuffer Latency: 0 usec\n\t{lat}: 0 usec\n"
             "\tResample method: PipeWire\n\tProperties:\n\t\tapplication.name = \"Jogo\"\n"
             "\t\tapplication.process.id = \"4242\"\n")
    return {
        "sinks.longo": longo_s,
        "sinks.curto": "".join(f"{ix}\t{n}\tPipeWire\t{sp}\t{e}\n"
                               for ix, n, _d, sp, e, _v in sinks),
        "sources.longo": longo_f,
        "sources.curto": "".join(f"{ix}\t{n}\tPipeWire\t{sp}\t{e}\n"
                                 for ix, n, _d, sp, e, _v in fontes),
        "sink-inputs.longo": fluxo.format(
            cab="Sink Input", ix=901, cli=77, alvo_cab="Sink", alvo=201,
            spec="float32le 4ch 48000Hz", mapa="front-left,front-right,rear-left,rear-right",
            vol=_vol(4, 100), lat="Sink Latency"),
        "sink-inputs.curto": "901\t201\t77\tPipeWire\tfloat32le 4ch 48000Hz\n",
        "source-outputs.longo": fluxo.format(
            cab="Source Output", ix=951, cli="n/a", alvo_cab="Source", alvo=403,
            spec="s16le 1ch 48000Hz", mapa="mono", vol=_vol(1, 100), lat="Source Latency"),
        "source-outputs.curto": "951\t403\t-\tPipeWire\ts16le 1ch 48000Hz\n",
        "modules.curto": ("1\tlibpipewire-module-rt\t{ }\t\n"
                          "2\tmodule-null-sink\tsink_name=hefesto_som_0000a1\t\n"),
        "info": ("Server String: /run/user/1000/pulse/native\nLibrary Protocol Version: 35\n"
                 "Server Protocol Version: 35\nIs Local: yes\nClient Index: 1\n"
                 "Tile Size: 65472\nServer Name: PulseAudio (on PipeWire 1.6.8)\n"
                 "Server Version: 15.0.0\n"
                 "Default Sample Specification: float32le 2ch 48000Hz\n"
                 "Default Channel Map: front-left,front-right\n"
                 f"Default Sink: {HDMI}\nDefault Source: hefesto_mic_0000a1\n"),
    }


#: O `pactl` de mentira. Responde o que o real responde — inclusive a FALHA do
#: nó que não existe (rc=1), que um dublê mais frouxo esconderia.
_PACTL = r"""#!/bin/sh
F=__F__
printf '%s\n' "$*" >> "$F/chamadas"
[ -e "$F/caido" ] && exit 1
no() {  # $1 = arquivo longo, $2 = nó, $3 = campo
  awk -v alvo="$2" -v campo="$3" '
    /^(Sink|Source) #/ { dentro = 0 }
    index($0, "\tName: ") == 1 { dentro = (substr($0, 8) == alvo) }
    dentro && index($0, "\t" campo ": ") == 1 {
      print substr($0, 2); if (campo == "Volume") { getline; print substr($0, 2) }
      achou = 1; exit
    }
    END { exit achou ? 0 : 1 }' "$F/$1"
}
do_info() { awk -v c="$1" 'index($0, c ": ") == 1 { print substr($0, length(c) + 3) }' "$F/info"; }
alvo() {
  case "$1" in
    @DEFAULT_SINK@) do_info "Default Sink";;
    @DEFAULT_SOURCE@) do_info "Default Source";;
    *) printf '%s\n' "$1";;
  esac
}
case "$*" in
  "list sinks") cat "$F/sinks.longo";;
  "list sinks short"|"list short sinks") cat "$F/sinks.curto";;
  "list sources") cat "$F/sources.longo";;
  "list sources short"|"list short sources") cat "$F/sources.curto";;
  "list sink-inputs") cat "$F/sink-inputs.longo";;
  "list sink-inputs short"|"list short sink-inputs") cat "$F/sink-inputs.curto";;
  "list source-outputs") cat "$F/source-outputs.longo";;
  "list source-outputs short"|"list short source-outputs") cat "$F/source-outputs.curto";;
  "list modules short"|"list short modules") cat "$F/modules.curto";;
  "info") cat "$F/info";;
  "get-default-sink") do_info "Default Sink";;
  "get-default-source") do_info "Default Source";;
  "get-sink-mute "*) no sinks.longo "$(alvo "$2")" Mute;;
  "get-source-mute "*) no sources.longo "$(alvo "$2")" Mute;;
  "get-sink-volume "*) no sinks.longo "$(alvo "$2")" Volume;;
  "get-source-volume "*) no sources.longo "$(alvo "$2")" Volume;;
  "subscribe") exec cat "$F/eventos";;
  *) exit 1;;
esac
"""


class Servidor:
    """O servidor de som de mentira, com o caderno de quem perguntou."""

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self._escritor: int | None = None

    def montar(self, **kw: str) -> None:
        for nome, texto in _textos(**kw).items():
            (self.raiz / nome).write_text(texto, encoding="utf-8")

    def chamadas(self) -> list[str]:
        return (self.raiz / "chamadas").read_text(encoding="utf-8").splitlines()

    def zerar(self) -> None:
        (self.raiz / "chamadas").write_text("", encoding="utf-8")

    async def abrir_os_eventos(self, prazo: float = 5.0) -> None:
        """Abre o lado de escrita do canal de eventos, quando o `subscribe` o abrir para ler."""
        fim = time.monotonic() + prazo
        while True:
            try:
                self._escritor = os.open(self.raiz / "eventos", os.O_WRONLY | os.O_NONBLOCK)
                return
            except OSError as exc:
                if exc.errno != errno.ENXIO or time.monotonic() > fim:
                    raise
            await asyncio.sleep(0.01)

    def evento(self, *linhas: str) -> None:
        assert self._escritor is not None, "o subscribe não abriu o canal"
        os.write(self._escritor, "".join(f"{x}\n" for x in linhas).encode())

    def cair(self) -> None:
        """O servidor some: toda pergunta falha, e o `subscribe` fecha."""
        (self.raiz / "caido").write_text("", encoding="utf-8")
        self.fechar()

    def voltar(self) -> None:
        (self.raiz / "caido").unlink(missing_ok=True)

    def fechar(self) -> None:
        if self._escritor is not None:
            with contextlib.suppress(OSError):
                os.close(self._escritor)
            self._escritor = None


@pytest.fixture
def servidor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Servidor]:
    raiz = tmp_path / "som"
    binario = raiz / "bin"
    binario.mkdir(parents=True)
    s = Servidor(raiz)
    s.montar()
    s.zerar()
    os.mkfifo(raiz / "eventos")
    pactl = binario / "pactl"
    pactl.write_text(_PACTL.replace("__F__", str(raiz)), encoding="utf-8")
    pactl.chmod(pactl.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{binario}{os.pathsep}{os.environ.get('PATH', '')}")
    # A GUARDA QUE SAI: o produto tem de achar ESTE pactl, ou a régua mediria
    # o servidor de quem a roda.
    if shutil.which("pactl") != str(pactl):
        pytest.fail(f"o pactl achado não é o de mentira: {shutil.which('pactl')}")
    rs.RETRATO.soltar()
    try:
        yield s
    finally:
        s.fechar()
        rs.RETRATO.soltar()


class _Daemon:
    """O que o ouvinte usa do daemon: o barramento e a lista de tarefas."""

    def __init__(self) -> None:
        self.publicados: list[Any] = []
        self._tasks: list[Any] = []
        self.bus = self

    def publish(self, _topico: str, carga: Any) -> None:
        self.publicados.append(carga)


class _Espiao:
    """Conta as leituras que o PRÓPRIO retrato faz — as legítimas."""

    def __init__(self) -> None:
        self.lidas: list[str] = []

    def __call__(self, argv: list[str]) -> str | None:
        self.lidas.append(" ".join(argv[1:]))
        return rs.ler_do_servidor(argv)


async def _ate(condicao: Callable[[], bool], motivo: str, prazo: float = 8.0) -> None:
    fim = time.monotonic() + prazo
    while not condicao():
        if time.monotonic() > fim:
            raise AssertionError(f"não chegou no prazo: {motivo}")
        await asyncio.sleep(0.01)


async def _o_ouvinte_subiu(
    daemon: _Daemon, desde: int = 0, motivo: str = "o ouvinte subiu", prazo: float = 8.0
) -> None:
    """A barreira de toda volta do ouvinte: o retrato vivo E o padrão dele publicado.

    O retrato fica vivo no `assumir` do `_carregar_o_retrato`, e a leitura do padrão
    (numa thread) e a publicação vêm DEPOIS. Esperar só o `RETRATO.vivo` mediria um
    instante antes do fato cobrado: no runner do CI a thread passa da volta do laço
    (a corrida 36503520655, no 3.12). A publicação sai em toda volta, com o servidor
    de pé ou não, por isso a barreira pede o VALOR que o retrato diz, e não só a
    contagem; e `desde` separa uma volta da anterior (a do servidor que voltou).
    """

    def subiu() -> bool:
        if not rs.RETRATO.vivo:
            return False
        publicadas = {p.get("saida") for p in daemon.publicados[desde:]} - {None, ""}
        return bool(publicadas) and rs.RETRATO.padrao("sink") in publicadas

    await _ate(subiu, motivo, prazo=prazo)


def _de_quem_mais(servidor: Servidor, espiao: _Espiao) -> Counter[str]:
    """As perguntas que chegaram ao servidor SEM ser do retrato nem do `subscribe`."""
    fora = Counter(servidor.chamadas())
    fora.subtract(Counter(espiao.lidas))
    fora.subtract({"subscribe": fora["subscribe"]})
    return +fora


# ---------------------------------------------------------------------------
# Os cinco leitores do daemon que a auditoria de 27/09 achou, numa volta
# ---------------------------------------------------------------------------


def _uma_volta_dos_leitores() -> dict[str, Any]:
    """O que o daemon pergunta ao servidor numa volta dos laços — pelas funções REAIS."""
    from hefesto_dualsense4unix.daemon.subsystems import bt_mic, hotkey, luz_do_mic
    from hefesto_dualsense4unix.integrations import alto_falante_bt as afb
    from hefesto_dualsense4unix.integrations import dualsense_bt_audio as dba

    endpoints = [ENDPOINT.format(h=h) for h in HEX]
    return {
        # hotkey._ler_o_canal, a cada CANAL_TTL_S por controle
        "canal": [hotkey._ler_o_canal(u) for u in UNIQS],
        # luz_do_mic._quem_ouve, a cada INTERVALO_DE_QUEM_OUVE_S
        "quem_ouve": luz_do_mic._quem_ouve(list(UNIQS), {}),
        # alto_falante._a_mesa_do_som_mudou, quando o retrato avisa (o vigia de
        # 0,4 s saiu em 28/09, A-HAPTICA-DO-RADIO-OBEDECE-AO-SINAL-DO-JOGO-01)
        "vigia": afb.sinks_que_tocam([*endpoints, *(afb.nome_do_sink(u) for u in UNIQS)]),
        # alto_falante._casar_as_pontes, por endpoint
        "pontes": [(afb.sink_esta_tocando(e, na_duvida=True), afb.volumes_do_sink(e))
                   for e in endpoints],
        # dualsense_bt_audio._talvez_seguir_a_source, por controle no rádio
        "radio": [dba._rodar(["pactl", "list", "sources", "short"]) for _ in UNIQS],
        # bt_mic, a fonte padrão crua
        "padrão": bt_mic.fonte_padrao_crua(),
    }


def _correr(cenario: Callable[[], Any]) -> None:
    """Um laço próprio que FECHA mesmo se o ouvinte não parar — ver :func:`_parar`."""
    laco = asyncio.new_event_loop()
    try:
        laco.run_until_complete(cenario())
        laco.run_until_complete(laco.shutdown_default_executor())
    finally:
        laco.close()


async def _parar(tarefa: asyncio.Task[Any]) -> None:
    """Cancela o ouvinte como o `connection.shutdown` do daemon: UMA vez.

    Um ouvinte que engole o cancelamento prende o desligamento do daemon — e
    prenderia esta régua para sempre, em vez de reprovar. Medido: a mordida do
    «sem servidor» achou exatamente isso, um `suppress(CancelledError)` em
    volta do `await` das tarefas da rajada.
    """
    tarefa.cancel()
    feitas, _ = await asyncio.wait({tarefa}, timeout=5.0)
    assert feitas, "o ouvinte engoliu o cancelamento: o daemon não conseguiria parar"


# ---------------------------------------------------------------------------
# 1 — O SERVIDOR QUE CONTA OS CLIENTES
# ---------------------------------------------------------------------------


def test_cem_tiques_sem_evento_nao_perguntam_nada_e_respondem_igual(
    servidor: Servidor, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A régua da sprint: 100 tiques do daemon sem evento = 0 `pactl`.

    E a resposta do retrato é a MESMA que o servidor daria: a volta é medida
    primeiro com o retrato SOLTO (cada leitor perguntando ao servidor, o
    mundo de antes da cura) e depois com ele vivo. Um retrato que zerasse as
    perguntas respondendo outra coisa passaria na conta e mentiria na tela.

    MORDIDA: `retrato_do_som.responder` devolvendo sempre `None` — a conta
    volta, e o canal do microfone sozinho pergunta 5 vezes por controle.
    """
    from hefesto_dualsense4unix.daemon.subsystems import hotkey
    from hefesto_dualsense4unix.daemon.subsystems import ouvinte_do_som as ods

    espiao = _Espiao()
    monkeypatch.setattr(rs.RETRATO, "_ler_injetado", espiao)
    antes = _uma_volta_dos_leitores()
    por_volta_antes = len(servidor.chamadas())
    assert por_volta_antes >= 40, (
        f"o mundo de antes da cura custava ~43 perguntas por volta; mediu {por_volta_antes} — "
        "o servidor de mentira deixou de responder a algum leitor")
    servidor.zerar()

    async def cenario() -> None:
        daemon = _Daemon()
        tarefa = asyncio.create_task(ods.ouvinte_do_som_loop(daemon))
        try:
            await _o_ouvinte_subiu(daemon)
            await servidor.abrir_os_eventos()
            assert sorted(espiao.lidas) == sorted(
                " ".join(a[1:]) for a in rs._LEITURA_DO_TIPO.values()), (
                "a leitura inteira de quando o ouvinte sobe é uma por tipo")
            servidor.zerar()
            espiao.lidas.clear()
            depois = await asyncio.to_thread(_uma_volta_dos_leitores)
            for _ in range(99):
                await asyncio.to_thread(_uma_volta_dos_leitores)
            perguntas = servidor.chamadas()
            servidor.zerar()
            # O CANAL DO MICROFONE SOZINHO, que é a mordida escrita na sprint:
            # devolvido ao `pactl`, ele conta 5 perguntas por controle por volta.
            for _ in range(100):
                await asyncio.to_thread(lambda: [hotkey._ler_o_canal(u) for u in UNIQS])
            do_canal = len(servidor.chamadas())
            assert do_canal == 0, (
                f"o canal do microfone perguntou {do_canal} vezes em 100 voltas — "
                f"{do_canal / (100 * len(UNIQS)):.0f} por controle por volta")
            assert perguntas == [], (
                f"100 tiques sem evento perguntaram {len(perguntas)} vezes ao servidor: "
                f"{Counter(perguntas).most_common(6)}")
            assert depois == antes, "o retrato respondeu diferente do servidor"
        finally:
            await _parar(tarefa)

    _correr(cenario)


def test_um_evento_rele_so_o_tipo_que_mudou(
    servidor: Servidor, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Um evento = UMA releitura, do tipo que mudou — e a tela vê a mudança.

    O servidor cala o microfone do controle 3 e avisa `change on source`. O
    retrato relê `list sources` (uma vez) e o selo do canal daquele controle
    passa a dizer mudo, sem nenhum leitor perguntar nada.

    E `client` não relê nada: cada `pactl` é um cliente, inclusive os do
    próprio retrato — reler por eles seria perguntar por causa das perguntas.
    """
    from hefesto_dualsense4unix.daemon.subsystems import hotkey
    from hefesto_dualsense4unix.daemon.subsystems import ouvinte_do_som as ods

    espiao = _Espiao()
    monkeypatch.setattr(rs.RETRATO, "_ler_injetado", espiao)

    async def cenario() -> None:
        daemon = _Daemon()
        tarefa = asyncio.create_task(ods.ouvinte_do_som_loop(daemon))
        try:
            await _o_ouvinte_subiu(daemon)
            await servidor.abrir_os_eventos()
            antes = await asyncio.to_thread(hotkey._ler_o_canal, UNIQS[2])
            assert antes["canal_mudo"] is False
            servidor.zerar()
            espiao.lidas.clear()

            servidor.evento("Event 'new' on client #7", "Event 'remove' on client #7")
            await asyncio.sleep(ods.RAJADA_S * 4)
            assert servidor.chamadas() == [], "evento de cliente fez o retrato reler"

            marca = rs.RETRATO.marca(("sources",))
            servidor.montar(mic_mudo=f"hefesto_mic_{HEX[2]}")
            servidor.evento("Event 'change' on source #403")
            await _ate(lambda: rs.RETRATO.marca(("sources",)) != marca, "o retrato reler as fontes")
            depois = await asyncio.to_thread(hotkey._ler_o_canal, UNIQS[2])
            assert depois["canal_mudo"] is True, "o retrato não acompanhou o evento"
            assert servidor.chamadas() == ["list sources"], (
                f"um evento de fonte devia reler UMA vez: {servidor.chamadas()}")
        finally:
            await _parar(tarefa)

    _correr(cenario)


def test_a_rajada_de_eventos_rele_uma_vez(
    servidor: Servidor, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Um jogo que abre emite uma rajada; reler a cada linha seria a chuva de volta.

    MORDIDA: `RAJADA_S = 0` com uma releitura por linha — a conta vira cinco.
    """
    from hefesto_dualsense4unix.daemon.subsystems import ouvinte_do_som as ods

    espiao = _Espiao()
    monkeypatch.setattr(rs.RETRATO, "_ler_injetado", espiao)

    async def cenario() -> None:
        daemon = _Daemon()
        tarefa = asyncio.create_task(ods.ouvinte_do_som_loop(daemon))
        try:
            await _o_ouvinte_subiu(daemon)
            await servidor.abrir_os_eventos()
            servidor.zerar()
            marca = rs.RETRATO.geracao
            servidor.evento(*["Event 'change' on sink-input #901"] * 5)
            await asyncio.sleep(ods.RAJADA_S * 6)
            assert servidor.chamadas() == ["list sink-inputs"], servidor.chamadas()
            assert rs.RETRATO.geracao == marca, "nada mudou e o retrato acordou quem espera"
        finally:
            await _parar(tarefa)

    _correr(cenario)


# ---------------------------------------------------------------------------
# 3 — SEM SERVIDOR, «NÃO SEI»; ELE VOLTA, E O RETRATO SE REFAZ
# ---------------------------------------------------------------------------


def test_sem_servidor_o_retrato_diz_nao_sei_e_se_refaz(
    servidor: Servidor, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O `systemctl --user restart pipewire…` da prova 4, sem o servidor dela.

    Caído: cada leitor recebe a falha de sempre — `None`, e não o conjunto
    vazio que diria «ninguém toca» — e NENHUM pergunta ao servidor por conta
    própria (quem tenta religar é só o ouvinte). Voltou: o retrato se relê
    inteiro e os leitores respondem de novo, sem ninguém mandar.
    """
    from hefesto_dualsense4unix.daemon.subsystems import ouvinte_do_som as ods
    from hefesto_dualsense4unix.integrations import alto_falante_bt as afb

    espiao = _Espiao()
    monkeypatch.setattr(rs.RETRATO, "_ler_injetado", espiao)
    monkeypatch.setattr(ods, "ESPERA_PARA_RELIGAR_S", 0.05)

    async def cenario() -> None:
        daemon = _Daemon()
        tarefa = asyncio.create_task(ods.ouvinte_do_som_loop(daemon))
        try:
            await _o_ouvinte_subiu(daemon)
            await servidor.abrir_os_eventos()
            servidor.cair()
            await _ate(lambda: not rs.RETRATO.vivo,
                       "o retrato dizer «não sei» com o servidor caído")
            assert rs.RETRATO.dono, "o dono soltou o retrato só porque o servidor caiu"
            servidor.zerar()
            espiao.lidas.clear()
            volta = await asyncio.to_thread(_uma_volta_dos_leitores)
            assert volta["vigia"] is None, "servidor caído virou «ninguém toca»"
            assert volta["padrão"] is None
            assert all(c["fonte"] is None for c in volta["canal"])
            assert all(r is None for r in volta["radio"])
            assert rs.RETRATO.responder(["pactl", "list", "sinks"]) is rs.NAO_SEI
            fora = _de_quem_mais(servidor, espiao)
            assert not fora, f"com o servidor caído, leitores perguntaram por conta própria: {fora}"

            desde = len(daemon.publicados)
            servidor.voltar()
            await _o_ouvinte_subiu(daemon, desde, "o ouvinte subiu de novo com o servidor")
            await servidor.abrir_os_eventos()
            assert afb.sinks_que_tocam([ENDPOINT.format(h=HEX[0])]) == {ENDPOINT.format(h=HEX[0])}
        finally:
            await _parar(tarefa)
        assert not rs.RETRATO.dono, "o ouvinte parou e o retrato ficou com dono"

    _correr(cenario)


# ---------------------------------------------------------------------------
# 2 — A EXAUSTIVA DE DONO: quem pergunta ao servidor, e não a palavra
# ---------------------------------------------------------------------------

#: Onde cada pergunta de leitura escrita em `src/` é entregue, e ao executor de
#: quem. A chave é `(arquivo, porta)`: a porta é a chamada que recebe o argv
#: (``self.runner``, ``correr``…) ou, quando o argv é guardado num nome antes,
#: a função que o guarda. Um injetável (``runner``, ``correr``) aponta para o
#: executor PADRÃO do módulo — é ele que roda quando ninguém injeta.
PORTAS: dict[tuple[str, str], str] = {
    ("app/audio_saida.py", "rodar"): "audio_saida.rodar_leitura",
    ("app/audio_saida.py", "rodar_leitura"): "audio_saida.rodar_leitura",
    ("app/audio_saida.py", "ler"): "audio_saida.rodar_leitura",
    ("app/audio_saida.py", "self._runner"): "audio_saida.rodar_leitura",
    ("app/mic_monitor.py", "self._runner"): "mic_monitor._rodar",
    ("daemon/subsystems/hotkey.py", "subprocess.run"): "hotkey._fonte_esta_muda",
    ("daemon/subsystems/hotkey.py", "_mudo_pelo_retrato"): "hotkey._fonte_esta_muda",
    ("daemon/subsystems/bt_mic.py", "subprocess.run"): "bt_mic.fonte_padrao_crua",
    ("integrations/alto_falante_bt.py", "correr"): "alto_falante_bt._rodar",
    ("integrations/alto_falante_bt.py", "self.runner"): "alto_falante_bt._rodar",
    ("integrations/alto_falante_bt.py", "ler"): "alto_falante_bt._rodar",
    ("integrations/alto_falante_bt.py", "_rodar"): "alto_falante_bt._rodar",
    ("integrations/alto_falante_bt.py", "<módulo>"): "alto_falante_bt._rodar",
    ("integrations/audio_control.py", "_texto_do_pactl"): "audio_control._rodar_pelo_recuo",
    ("integrations/audio_control.py", "_rodar_pelo_recuo"): "audio_control._rodar_pelo_recuo",
    ("integrations/audio_control.py", "self._run"): "audio_control._rodar_pelo_recuo",
    ("integrations/audio_ks_dualsense.py", "runner"): "audio_ks_dualsense._pactl",
    ("integrations/dualsense_bt_audio.py", "self.runner"): "dualsense_bt_audio._rodar",
    ("integrations/dualsense_bt_audio.py", "_com_recuo(runner or _rodar)"):
        "dualsense_bt_audio._rodar",
    ("integrations/eleicao_de_microfone.py", "_rodar"): "eleicao_de_microfone._rodar",
    ("integrations/eleicao_de_microfone.py", "_ler"): "eleicao_de_microfone._rodar",
    ("integrations/endpoint_de_haptica.py", "chamar"): "alto_falante_bt._rodar",
    ("integrations/endpoint_de_haptica.py", "self.runner"): "alto_falante_bt._rodar",
    ("integrations/ganho_do_microfone.py", "audio_saida.rodar_leitura"):
        "audio_saida.rodar_leitura",
    ("integrations/quem_ouve_o_microfone.py", "_rodar"): "eleicao_de_microfone._rodar",
    ("integrations/teste_do_microfone.py", "fonte_do_controle"):
        "teste_do_microfone.fonte_do_controle",
    # A janela (nao_toca desta sprint) lê pelo dono da aba 02, que embrulha o
    # `audio_saida.rodar_leitura`: é ele quem pergunta, e ele pergunta ao retrato.
    ("interface/pacotes/a02_controles.py", "_ler_pelo_dono"): "audio_saida.rodar_leitura",
}


#: A porta que É o retrato: quem pergunta a ele não pergunta ao servidor.
PORTA_DO_RETRATO = "retrato_do_som.responder"


def _texto_de(valor: Any) -> Any:
    return valor.stdout if hasattr(valor, "stdout") else valor


def _executores() -> dict[str, Callable[[list[str]], Any]]:
    """Cada executor, chamado como o produto o chama. Nada é dublado aqui."""
    from hefesto_dualsense4unix.app import audio_saida, mic_monitor
    from hefesto_dualsense4unix.daemon.subsystems import bt_mic, hotkey
    from hefesto_dualsense4unix.integrations import alto_falante_bt as afb
    from hefesto_dualsense4unix.integrations import audio_control as ac
    from hefesto_dualsense4unix.integrations import audio_ks_dualsense as aks
    from hefesto_dualsense4unix.integrations import dualsense_bt_audio as dba
    from hefesto_dualsense4unix.integrations import eleicao_de_microfone as em
    from hefesto_dualsense4unix.integrations import teste_do_microfone as tdm

    def pelo_recuo(argv: list[str]) -> Any:
        try:
            return ac._rodar_pelo_recuo(argv, timeout=2.0, env=dict(os.environ)).stdout
        except ac.PactlEmRecuoError:
            return None

    return {
        "audio_saida.rodar_leitura": audio_saida.rodar_leitura,
        "mic_monitor._rodar": mic_monitor._rodar,
        "hotkey._fonte_esta_muda": lambda _a: hotkey._fonte_esta_muda(f"hefesto_mic_{HEX[2]}"),
        "bt_mic.fonte_padrao_crua": lambda _a: bt_mic.fonte_padrao_crua(),
        "alto_falante_bt._rodar": afb._rodar,
        "audio_control._rodar_pelo_recuo": pelo_recuo,
        "audio_ks_dualsense._pactl": aks._pactl,
        "dualsense_bt_audio._rodar": dba._rodar,
        "eleicao_de_microfone._rodar": lambda a: em._rodar(a)[1],
        "teste_do_microfone.fonte_do_controle": lambda _a: tdm.fonte_do_controle(UNIQS[0]),
    }


def _e_leitura(elementos: list[str | None]) -> bool:
    """`["pactl", verbo, ...]` ou `[<variável>, verbo, ...]` com verbo de leitura."""
    if len(elementos) < 2 or elementos[1] not in rs.LEITURAS:
        return False
    return elementos[0] in ("pactl", None)


def _censo() -> list[tuple[str, int, str, list[str | None]]]:
    """Toda pergunta de leitura ao servidor escrita em `src/`: (arquivo, linha, porta, argv).

    Pela árvore, e não pelo texto: prosa pode dizer `pactl list`, e só conta a
    lista que o interpretador monta. O primeiro elemento pode ser uma variável
    (`[exe, "get-default-source"]`) — o nome do binário resolvido não esconde a
    pergunta.
    """
    achados: list[tuple[str, int, str, list[str | None]]] = []
    for arquivo in sorted(SRC.rglob("*.py")):
        relativo = arquivo.relative_to(SRC).as_posix()
        if relativo == "integrations/retrato_do_som.py":
            continue
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        pais: dict[int, ast.AST] = {}
        funcao: dict[int, str] = {}
        for no in ast.walk(arvore):
            for filho in ast.iter_child_nodes(no):
                pais[id(filho)] = no
        for no in ast.walk(arvore):
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dentro in ast.walk(no):
                    funcao.setdefault(id(dentro), no.name)
        for no in ast.walk(arvore):
            if isinstance(no, (ast.List, ast.Tuple)):
                elementos = [e.value if isinstance(e, ast.Constant) and isinstance(e.value, str)
                             else None for e in no.elts]
                if not _e_leitura(elementos):
                    continue
                pai = pais.get(id(no))
                if isinstance(pai, ast.Call) and no in pai.args:
                    porta = ast.unparse(pai.func)
                else:
                    porta = funcao.get(id(no), "<módulo>")
                achados.append((relativo, no.lineno, porta, elementos))
            elif isinstance(no, ast.Call):
                elementos = [a.value if isinstance(a, ast.Constant) and isinstance(a.value, str)
                             else "?" for a in no.args]
                if elementos[:1] == ["pactl"] and len(elementos) > 1 and _e_leitura(
                        [*elementos[:1], *elementos[1:]]):
                    achados.append((relativo, no.lineno, ast.unparse(no.func), [*elementos]))
    return achados


def test_toda_pergunta_de_leitura_tem_um_executor_que_passa_pelo_retrato() -> None:
    """A metade que ACHA: cada pergunta de leitura de `src/` cai numa porta conhecida.

    Um leitor novo que monte a própria pergunta e a entregue a um
    `subprocess.run` — ou a um executor novo — aparece aqui com arquivo e linha,
    antes de virar a 24ª pergunta por segundo.

    MORDIDA: ponha um `subprocess.run(["pactl", "list", "sinks"])` em qualquer
    módulo de `src/` e esta régua reprova apontando a linha.
    """
    sem_dono = [f"{a}:{linha} ({porta}) pergunta {' '.join(str(e) for e in argv[1:3])}"
                for a, linha, porta, argv in _censo()
                if porta != PORTA_DO_RETRATO and (a, porta) not in PORTAS]
    assert not sem_dono, (
        "pergunta ao servidor de som que não passa pelo retrato:\n  " + "\n  ".join(sem_dono))


def test_o_censo_acha_as_perguntas_que_existem() -> None:
    """Uma régua exaustiva que não acha nada é a trava medida contra a própria saída."""
    achados = _censo()
    portas = {(a, p) for a, _l, p, _e in achados if p != PORTA_DO_RETRATO}
    assert len(achados) >= 40, f"o censo achou só {len(achados)} perguntas"
    usadas = set(PORTAS)
    assert portas == usadas, (
        f"portas da tabela que o censo não acha mais: {sorted(usadas - portas)}; "
        f"portas novas: {sorted(portas - usadas)}")


def test_todo_executor_com_o_retrato_vivo_nao_pergunta_nada(
    servidor: Servidor, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A metade que JULGA: cada executor, chamado de verdade, com cada pergunta que
    o censo achou entregue a ele — e o servidor diz se alguém além do retrato
    perguntou.

    A resposta com o retrato vivo tem de ser a MESMA que o executor dá
    perguntando ao servidor: a primeira volta roda com o retrato solto e serve
    de gabarito.

    MORDIDA: tire a consulta ao retrato de qualquer executor (o
    `mic_monitor._rodar`, por exemplo) e esta régua reprova nomeando-o.
    """
    executores = _executores()
    formas: dict[str, set[tuple[str, ...]]] = {}
    for a, _l, porta, argv in _censo():
        if porta == PORTA_DO_RETRATO:
            continue
        chave = PORTAS[(a, porta)]
        partes = ["pactl" if i == 0 else "?" if e is None else str(e)
                  for i, e in enumerate(argv)]
        if partes[1:2] == ["list"] and len(partes) == 3 and partes[2] == "?":
            for tipo in ("sinks", "sources"):
                formas.setdefault(chave, set()).add(("pactl", "list", tipo))
            continue
        alvo = HDMI if "sink" in partes[1] else f"hefesto_mic_{HEX[2]}"
        formas.setdefault(chave, set()).add(
            tuple(alvo if p == "?" else p for p in partes))
    assert set(formas) == set(executores), (
        f"executor sem pergunta ou pergunta sem executor: {set(formas) ^ set(executores)}")

    espiao = _Espiao()
    quem_perguntou: dict[str, dict[str, int]] = {}

    def uma_volta() -> dict[tuple[str, tuple[str, ...]], Any]:
        respostas = {}
        for k, fs in sorted(formas.items()):
            servidor.zerar()
            espiao.lidas.clear()
            for f in sorted(fs):
                respostas[(k, f)] = _texto_de(executores[k](list(f)))
            fora = _de_quem_mais(servidor, espiao)
            if fora:
                quem_perguntou[k] = dict(fora)
        return respostas

    gabarito = uma_volta()
    assert len(quem_perguntou) == len(executores), (
        "com o retrato solto, algum executor não perguntou — o gabarito é oco: "
        f"{set(executores) - set(quem_perguntou)}")
    quem_perguntou.clear()
    monkeypatch.setattr(rs.RETRATO, "_ler_injetado", espiao)
    assert rs.RETRATO.carregar()
    rs.RETRATO.assumir()
    agora = uma_volta()
    assert not quem_perguntou, (
        f"executores perguntaram ao servidor com o retrato vivo: {quem_perguntou}")
    diferentes = [k for k in gabarito if agora[k] != gabarito[k]]
    assert not diferentes, f"o retrato respondeu diferente do servidor em: {diferentes}"


# ---------------------------------------------------------------------------
# O retrato por dentro
# ---------------------------------------------------------------------------


def test_o_curto_sai_do_longo_como_o_pactl_o_imprime() -> None:
    """O oráculo é o `printf` do `pactl` 16.1, escrito à parte do retrato.

    Conferido também contra a saída curta da máquina dela em 28/09/2026 (os
    arquivos ficaram fora do repositório: têm endereço de controle).

    MORDIDA: troque a ordem de duas colunas em `curto_dos_nos`.
    """
    t = _textos()
    for tipo in ("sinks", "sources"):
        assert rs.curto_dos_nos(rs.nos_do_texto(t[f"{tipo}.longo"])) == t[f"{tipo}.curto"]
    for tipo in ("sink-inputs", "source-outputs"):
        assert rs.curto_dos_fluxos(rs.fluxos_do_texto(t[f"{tipo}.longo"])) == t[f"{tipo}.curto"]


def test_o_fluxo_diz_de_quem_e_para_quem_o_pedir() -> None:
    """A partida pelo dono do fluxo (A-HAPTICA-DO-RADIO) lê isto do retrato."""
    (fluxo,) = rs.fluxos_do_texto(_textos()["sink-inputs.longo"])
    assert fluxo.alvo == "201"
    assert fluxo.propriedades["application.process.id"] == "4242"
    assert fluxo.corked is False


@pytest.mark.parametrize(("argv", "esperado"), [
    (["pactl", "list", "sinks", "short"], rs.Pergunta("sinks", "curta")),
    (["pactl", "list", "short", "sink-inputs"], rs.Pergunta("sink-inputs", "curta")),
    (["pactl", "list", "sources"], rs.Pergunta("sources", "longa")),
    (["pactl", "list", "modules", "short"], rs.Pergunta("modules", "curta")),
    (["/usr/bin/pactl", "get-default-source"], rs.Pergunta("server", "padrão", "source")),
    (["pactl", "get-sink-mute", "x"], rs.Pergunta("sinks", "mudo", "x")),
    (["pactl", "get-source-volume", "@DEFAULT_SOURCE@"],
     rs.Pergunta("sources", "volume", "@DEFAULT_SOURCE@")),
    (["pactl", "info"], rs.Pergunta("server", "info")),
    (["pactl", "list", "cards"], None),
    (["pactl", "list", "modules"], None),
    (["pactl", "set-default-sink", "x"], None),
    (["wpctl", "status"], None),
])
def test_as_perguntas_que_o_retrato_entende(argv: list[str], esperado: Any) -> None:
    assert rs.entender(argv) == esperado


@pytest.mark.parametrize(("argv", "tipos"), [
    (["pactl", "set-default-source", "x"], {"server"}),
    (["pactl", "set-source-mute", "x", "0"], {"sources"}),
    (["pactl", "set-sink-volume", "x", "40%"], {"sinks", "sources"}),
    (["pactl", "set-sink-input-mute", "9", "1"], {"sink-inputs"}),
    (["pactl", "load-module", "module-null-sink"], set(rs.TIPOS)),
    (["pactl", "list", "sinks"], set()),
    (["pactl", "subscribe"], set()),
])
def test_cada_escrita_deixa_pendente_o_que_ela_toca(argv: list[str], tipos: set[str]) -> None:
    assert rs.tipos_da_escrita(argv) == tipos


def _retrato_de_mentira(respostas: dict[tuple[str, ...], str | None]) -> tuple[
        rs.RetratoDoSom, list[tuple[str, ...]]]:
    lidas: list[tuple[str, ...]] = []

    def ler(argv: Any) -> str | None:
        lidas.append(tuple(argv))
        return respostas.get(tuple(argv))

    return rs.RetratoDoSom(ler=ler), lidas


def _respostas() -> dict[tuple[str, ...], str | None]:
    t = _textos()
    return {
        ("pactl", "list", "sinks"): t["sinks.longo"],
        ("pactl", "list", "sources"): t["sources.longo"],
        ("pactl", "list", "sink-inputs"): t["sink-inputs.longo"],
        ("pactl", "list", "source-outputs"): t["source-outputs.longo"],
        ("pactl", "list", "modules", "short"): t["modules.curto"],
        ("pactl", "info"): t["info"],
    }


def test_escrever_e_conferir_le_o_servidor_e_nao_a_foto() -> None:
    """O «escrevi, confiro» de quem elege um microfone.

    Sem a pendência, a conferência que vem logo depois da escrita leria a foto
    de antes dela — e a eleição concluiria que o servidor recusou.

    MORDIDA: esvazie `escreveu` e a conferência responde o padrão velho.
    """
    respostas = _respostas()
    r, lidas = _retrato_de_mentira(respostas)
    assert r.carregar()
    r.assumir()
    assert r.responder(["pactl", "get-default-source"]) == "hefesto_mic_0000a1\n"
    respostas[("pactl", "info")] = respostas[("pactl", "info")].replace(  # type: ignore[union-attr]
        "Default Source: hefesto_mic_0000a1", "Default Source: hefesto_mic_0000a3")
    lidas.clear()
    r.escreveu(["pactl", "set-default-source", "hefesto_mic_0000a3"])
    assert r.responder(["pactl", "get-default-source"]) == "hefesto_mic_0000a3\n"
    assert lidas == [("pactl", "info")], "a escrita não fez o retrato reler o tipo dela"
    assert r.responder(["pactl", "get-default-source"]) == "hefesto_mic_0000a3\n"
    assert lidas == [("pactl", "info")], "releu de novo sem escrita nova"


def test_o_tipo_que_nao_releu_diz_nao_sei_e_nao_pergunta_a_cada_tique() -> None:
    """Releitura que falhou: «não sei», e a próxima tentativa só depois do intervalo.

    Sem o intervalo, um servidor que recusa depressa levaria uma pergunta por
    leitor por tique — o defeito inteiro, pela porta dos fundos.
    """
    respostas = _respostas()
    r, lidas = _retrato_de_mentira(respostas)
    assert r.carregar()
    r.assumir()
    respostas[("pactl", "list", "sinks")] = None
    r.escreveu(["pactl", "set-sink-mute", HDMI, "1"])
    lidas.clear()
    for _ in range(20):
        assert r.responder(["pactl", "list", "sinks", "short"]) is rs.NAO_SEI
    assert lidas.count(("pactl", "list", "sinks")) == 1


def test_solto_nao_responde_e_dono_morto_e_solto() -> None:
    """Fora do daemon o executor pergunta como sempre; um laço que morreu solta o retrato."""
    r, _lidas = _retrato_de_mentira(_respostas())
    assert r.responder(["pactl", "list", "sinks"]) is None
    laco = asyncio.new_event_loop()
    assert r.carregar()
    r.assumir(laco)
    assert isinstance(r.responder(["pactl", "list", "sinks"]), str)
    laco.close()
    assert r.responder(["pactl", "list", "sinks"]) is None
    assert not r.dono


def test_a_escrita_nunca_e_respondida_pelo_retrato() -> None:
    """As escritas continuam pelo `pactl`: o retrato não tem segundo caminho."""
    r, _lidas = _retrato_de_mentira(_respostas())
    assert r.carregar()
    r.assumir()
    assert r.responder(["pactl", "set-default-sink", HDMI]) is None
    assert r.responder(["pactl", "load-module", "module-null-sink"]) is None
    assert r.responder(["pactl", "subscribe"]) is None


def test_servidor_sob_suspeita_nao_responde_pela_foto(monkeypatch: pytest.MonkeyPatch) -> None:
    """Um servidor TRAVADO não derruba o `subscribe`: quem o percebe é o recuo.

    Em recuo, «não sei» sem perguntar; recuo vencido sem resposta, a leitura
    vai ao servidor e a primeira que responde zera o recuo.
    """
    from hefesto_dualsense4unix.integrations import dualsense_bt_audio as dba

    respostas = _respostas()
    r, lidas = _retrato_de_mentira(respostas)
    assert r.carregar()
    r.assumir()
    agora = [1000.0]
    recuo = dba.RecuoDoPactl(relogio=lambda: agora[0])
    monkeypatch.setattr(dba, "PACTL", recuo)
    recuo.estourou()
    lidas.clear()
    assert r.responder(["pactl", "get-default-sink"]) == f"{HDMI}\n"
    assert lidas == [("pactl", "info")], "sob suspeita, a foto respondeu sem ler"

    # E EM RECUO o leitor do retrato nem pergunta: «não sei», sem processo.
    def nenhum_processo(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("em recuo, o retrato perguntou ao servidor")

    monkeypatch.setattr(rs.subprocess, "run", nenhum_processo)
    monkeypatch.setattr(r, "_ler_injetado", rs.ler_do_servidor)
    assert r.responder(["pactl", "get-default-source"]) is rs.NAO_SEI


def test_quem_espera_acorda_so_pelo_assunto_dele() -> None:
    """O selo do microfone não relê quatro controles porque um fluxo de saída mudou."""
    respostas = _respostas()
    r, _lidas = _retrato_de_mentira(respostas)
    assert r.carregar()
    r.assumir()
    fontes = r.marca(("sources", "server"))
    saidas = r.marca(("sink-inputs",))
    respostas[("pactl", "list", "sink-inputs")] = ""
    assert r.reler({"sink-inputs"}) == {"sink-inputs"}
    assert r.marca(("sources", "server")) == fontes
    assert r.marca(("sink-inputs",)) != saidas
    inicio = time.monotonic()
    assert r.esperar(fontes, 0.05, ("sources", "server")) == fontes
    assert time.monotonic() - inicio >= 0.04


# ---------------------------------------------------------------------------
# «Os laços deixam de perguntar: eles acordam pelo evento»
# ---------------------------------------------------------------------------


def test_o_canal_do_microfone_acorda_pelo_evento_das_fontes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A prova 2 da sprint, na metade que cabe numa régua: o selo do canal
    acompanha o gesto em menos de 1 s porque o laço acorda pelo evento — e não
    na volta de 2 s. Um fluxo de SAÍDA que muda no meio do jogo não o acorda.

    MORDIDA: devolva o `asyncio.sleep(CANAL_TTL_S)` ao laço.
    """
    from hefesto_dualsense4unix.daemon.subsystems import hotkey

    voltas: list[str] = []

    async def ler(_daemon: Any, uniq: str) -> dict[str, Any]:
        voltas.append(uniq)
        return {"fonte": None}

    async def conferir(_daemon: Any, _uniqs: list[str]) -> list[str]:
        return []

    monkeypatch.setattr(hotkey, "_uniqs_conectados", lambda _d: [UNIQS[0]])
    monkeypatch.setattr(hotkey, "_ler_o_canal_deste", ler)
    monkeypatch.setattr(hotkey, "_conferir_quem_saiu_do_ar", conferir)
    monkeypatch.setattr(hotkey, "_CANAL_POR_UNIQ", {})
    monkeypatch.setattr(hotkey, "CANAL_TTL_S", 30.0)
    monkeypatch.setattr(hotkey, "_MARCA_DO_CANAL", [None])

    class _D:
        parar = False

        def _is_stopping(self) -> bool:
            return self.parar

    async def cenario() -> None:
        daemon = _D()
        tarefa = asyncio.create_task(hotkey.canal_do_microfone_loop(daemon))  # type: ignore[arg-type]
        try:
            await asyncio.sleep(0.05)
            assert voltas == []
            rs.RETRATO._avisar({"sink-inputs"})
            await asyncio.sleep(0.2)
            assert voltas == [], "um fluxo de saída acordou o canal do microfone"
            rs.RETRATO._avisar({"sources"})
            await _ate(lambda: voltas == [UNIQS[0]], "o canal acordar pelo evento das fontes",
                       prazo=1.0)
        finally:
            daemon.parar = True
            rs.RETRATO._avisar({"sources"})
            await asyncio.wait_for(tarefa, 2.0)

    _correr(cenario)


def test_o_vigia_do_alto_falante_acorda_pelo_fluxo_que_nasce(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O jogo abre um fluxo no endpoint: a volta do alto-falante acorda na hora.

    Desde 28/09 (A-HAPTICA-DO-RADIO-OBEDECE-AO-SINAL-DO-JOGO-01) não há vigia
    de 0,4 s: o OUVINTE do alto-falante dorme no retrato e arma o aviso da
    volta, que olha se o que ela leu mudou. A parada solta os dois sem esperar
    o relógio — o ouvinte pelo `RETRATO.acordar`, a espera pelo aviso.

    MORDIDA: tire o `self._acordar.set()` de `_ouvir_o_retrato` — o fluxo que
    nasce espera a volta inteira.
    """
    import threading

    from hefesto_dualsense4unix.daemon.subsystems import alto_falante as af

    monkeypatch.setattr(af, "RECONCILIA_S", 10.0)
    quem = object.__new__(af.AltoFalanteSubsystem)
    quem._parar = threading.Event()  # type: ignore[attr-defined]
    quem._acordar = threading.Event()  # type: ignore[attr-defined]
    mudou = [False]
    quem._a_mesa_do_som_mudou = lambda: mudou[0]  # type: ignore[method-assign]

    class _Gerenciador:
        def dormir(self, _s: float) -> bool:
            return False

    ouvinte = threading.Thread(target=quem._ouvir_o_retrato, daemon=True)
    ouvinte.start()
    fim: list[tuple[bool, float]] = []

    def esperar() -> None:
        inicio = time.monotonic()
        fim.append((quem._esperar_a_mesa_do_som(_Gerenciador()), time.monotonic() - inicio))

    try:
        fio = threading.Thread(target=esperar)
        fio.start()
        time.sleep(0.1)
        mudou[0] = True
        rs.RETRATO._avisar({"sink-inputs"})
        fio.join(2.0)
        assert fim and fim[0][0] is False and fim[0][1] < 1.0, (
            f"o fluxo que nasceu não acordou a volta: {fim}")

        fim.clear()
        mudou[0] = False
        fio = threading.Thread(target=esperar)
        fio.start()
        time.sleep(0.1)
        quem._parar.set()
        quem._acordar.set()
        fio.join(2.0)
        assert fim and fim[0][0] is True and fim[0][1] < 1.0, (
            f"a parada esperou o relógio inteiro: {fim}")
    finally:
        quem._parar.set()
        rs.RETRATO.acordar()
        ouvinte.join(2.0)
    assert not ouvinte.is_alive(), "o ouvinte não parou com o `RETRATO.acordar`"


def test_o_ouvinte_para_quando_mandam_mesmo_com_o_servidor_caido(
    servidor: Servidor, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O desligamento do daemon cancela o ouvinte UMA vez, em qualquer ponto da volta.

    Com o servidor caído o ouvinte religa sem parar, e o cancelamento pode cair
    em qualquer `await` da volta — inclusive no que recolhe as tarefas da
    rajada. Achado pela mordida do «sem servidor» em 28/09/2026: um
    `suppress(CancelledError)` ali engolia o cancelamento, e o ouvinte (e a
    régua) ficavam presos para sempre. Quarenta cancelamentos em pontos
    diferentes da volta.

    MORDIDA: devolva o `await` por tarefa dentro de `suppress(CancelledError)`.
    """
    from hefesto_dualsense4unix.daemon.subsystems import ouvinte_do_som as ods

    monkeypatch.setattr(ods, "ESPERA_PARA_RELIGAR_S", 0.0)
    servidor.cair()

    async def cenario() -> None:
        for i in range(40):
            tarefa = asyncio.create_task(ods.ouvinte_do_som_loop(_Daemon()))
            await asyncio.sleep(0.002 * i)
            await _parar(tarefa)

    _correr(cenario)


# ---------------------------------------------------------------------------
# A conferência de 28/09/2026 — o que as réguas de cima não mordiam
# ---------------------------------------------------------------------------


def test_o_padrao_nao_segura_o_laco_do_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    """A consulta ao retrato que RELÊ o servidor roda fora do laço do daemon.

    Uma escrita deixou o `server` pendente: o padrão publicado relê o
    servidor antes de responder, com `subprocess.run`. No laço, esse `pactl`
    pararia o daemon inteiro pelo tempo dele — a leitura de antes da cura era
    assíncrona justamente por isso.

    MORDIDA: devolva o corpo de `ler_o_padrao` ao laço (sem o `to_thread`) e o
    laço fica parado enquanto o retrato relê.
    """
    from hefesto_dualsense4unix.daemon.subsystems import ouvinte_do_som as ods

    r, _lidas = _retrato_de_mentira(_respostas())
    assert r.carregar()
    r.assumir()
    rapido = r._ler_injetado
    assert rapido is not None

    def devagar(argv: Any) -> str | None:
        time.sleep(0.3)
        return rapido(argv)

    r._ler_injetado = devagar
    r.escreveu(["pactl", "set-default-sink", HDMI])
    monkeypatch.setattr(rs, "RETRATO", r)

    async def cenario() -> None:
        voltas = [0]

        async def girar() -> None:
            while True:
                voltas[0] += 1
                await asyncio.sleep(0.01)

        giro = asyncio.create_task(girar())
        try:
            await asyncio.sleep(0.03)
            antes = voltas[0]
            som = await ods.ler_o_padrao()
            durante = voltas[0] - antes
        finally:
            giro.cancel()
            await asyncio.gather(giro, return_exceptions=True)
        assert som.saida == HDMI
        assert durante >= 10, (
            f"o laço do daemon deu {durante} voltas enquanto o retrato relia o servidor")

    _correr(cenario)


def test_a_rajada_que_acabou_nao_fica_guardada(servidor: Servidor) -> None:
    """Cada rajada é uma tarefa; a que acabou sai da lista da volta.

    Sem a poda, toda rajada ficava guardada até o `subscribe` cair — e ele não
    cai numa sessão boa. Um jogo que mexe nos fluxos dá uma rajada por
    segundo: dezenas de milhares por noite, no processo que fica de pé o dia
    inteiro.

    MORDIDA: tire a poda e a conta vira trinta.
    """
    import gc

    from hefesto_dualsense4unix.daemon.subsystems import ouvinte_do_som as ods

    def rajadas_guardadas() -> int:
        gc.collect()
        return sum(1 for o in gc.get_objects()
                   if isinstance(o, asyncio.Task) and o.done()
                   and getattr(o.get_coro(), "__name__", "") == "descarregar")

    async def cenario() -> None:
        daemon = _Daemon()
        tarefa = asyncio.create_task(ods.ouvinte_do_som_loop(daemon))
        try:
            await _o_ouvinte_subiu(daemon)
            await servidor.abrir_os_eventos()
            servidor.zerar()
            for i in range(30):
                servidor.evento("Event 'change' on sink-input #901")
                await _ate(lambda i=i: servidor.chamadas().count("list sink-inputs") == i + 1,
                           "a rajada reler os fluxos")
                await asyncio.sleep(ods.RAJADA_S * 2)
            guardadas = rajadas_guardadas()
            assert guardadas <= 1, f"{guardadas} rajadas que acabaram continuam guardadas"
        finally:
            await _parar(tarefa)

    _correr(cenario)


def test_o_evento_nao_encurta_o_prazo_de_quem_sai_do_ar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O selo acompanha o evento; o «saiu do ar» segue o relógio de sempre.

    `MicrofonesNoAr.LEITURAS_SEM_CANAL_ATE_SAIR` conta LEITURAS, e o tempo
    delas vinha do laço, que dormia `CANAL_TTL_S`: duas faltas eram dois a
    quatro segundos. Acordado pelo evento, o laço dá voltas em milissegundos —
    a ponte do rádio que refaz o nó (a fonte sai, o monitor do alto-falante
    sai, a fonte volta) contaria as duas faltas num piscar e tiraria do ar um
    microfone que ela ligou, sem gesto nenhum.

    E a volta pelo evento que pulou a conferência não a empurra um prazo
    inteiro para a frente: a seguinte sai na hora devida.

    MORDIDAS: devolva o `_conferir_quem_saiu_do_ar` direto ao laço e as cinco
    voltas pelo evento conferem cinco vezes; tire o teto do prazo em
    `_esperar_o_som_mudar` e a segunda conferência atrasa o que o último
    evento atrasou.
    """
    from hefesto_dualsense4unix.daemon.subsystems import hotkey

    voltas: list[str] = []
    conferencias: list[float] = []

    async def ler(_daemon: Any, uniq: str) -> dict[str, Any]:
        voltas.append(uniq)
        return {"fonte": None}

    async def conferir(_daemon: Any, _uniqs: list[str]) -> list[str]:
        conferencias.append(asyncio.get_running_loop().time())
        return []

    monkeypatch.setattr(hotkey, "_uniqs_conectados", lambda _d: [UNIQS[0]])
    monkeypatch.setattr(hotkey, "_ler_o_canal_deste", ler)
    monkeypatch.setattr(hotkey, "_conferir_quem_saiu_do_ar", conferir)
    monkeypatch.setattr(hotkey, "_CANAL_POR_UNIQ", {})
    monkeypatch.setattr(hotkey, "CANAL_TTL_S", 0.6)
    monkeypatch.setattr(hotkey, "_MARCA_DO_CANAL", [None])

    class _D:
        parar = False

        def _is_stopping(self) -> bool:
            return self.parar

    async def cenario() -> None:
        daemon = _D()
        tarefa = asyncio.create_task(hotkey.canal_do_microfone_loop(daemon))  # type: ignore[arg-type]
        try:
            await asyncio.sleep(0.02)
            for n in range(1, 6):
                rs.RETRATO._avisar({"sources"})
                await _ate(lambda n=n: len(voltas) >= n, "a volta pelo evento", prazo=1.0)
            assert len(voltas) == 5
            assert len(conferencias) == 1, (
                f"cinco voltas pelo evento conferiram {len(conferencias)} vezes quem saiu do ar")
            # Um evento perto da hora devida: a volta dele pula a conferência,
            # e a seguinte não pode esperar um prazo inteiro a partir dele.
            laco = asyncio.get_running_loop()
            await asyncio.sleep(max(0.0, conferencias[0] + 0.45 - laco.time()))
            rs.RETRATO._avisar({"sources"})
            await _ate(lambda: len(voltas) >= 6, "a volta pelo evento", prazo=1.0)
            await _ate(lambda: len(conferencias) >= 2, "a conferência no prazo", prazo=2.0)
            intervalo = conferencias[1] - conferencias[0]
            assert 0.6 - 0.02 <= intervalo < 0.9, (
                f"a segunda conferência saiu {intervalo:.2f} s depois da primeira, "
                "e o prazo é 0,6 s")
        finally:
            daemon.parar = True
            rs.RETRATO._avisar({"sources"})
            await asyncio.wait_for(tarefa, 2.0)

    _correr(cenario)


def test_o_numero_do_cliente_no_info_nao_e_mudanca(monkeypatch: pytest.MonkeyPatch) -> None:
    """O `Client Index` do `pactl info` é o do PRÓPRIO `pactl` que perguntou.

    Ele muda a cada pergunta, e contá-lo como mudança faria toda releitura do
    servidor acordar o canal do microfone dos quatro controles — o servidor
    de mentira de cima não o muda, e por isso não via.

    MORDIDA: compare o `info` inteiro em `_reler_um`.
    """
    respostas = _respostas()
    contador = [1]
    base = respostas[("pactl", "info")]
    assert base is not None and "Client Index: 1" in base

    def ler(argv: Any) -> str | None:
        if tuple(argv) == ("pactl", "info"):
            contador[0] += 1
            return base.replace("Client Index: 1", f"Client Index: {contador[0]}")
        return respostas.get(tuple(argv))

    r = rs.RetratoDoSom(ler=ler)
    assert r.carregar()
    r.assumir()
    marca = r.marca(("server",))
    assert r.reler({"server"}) == frozenset()
    assert r.marca(("server",)) == marca, "o número do cliente acordou quem espera"


@pytest.mark.parametrize("thread_lenta", [False, True], ids=["no-ritmo-da-casa", "thread-lenta"])
def test_um_tipo_que_nao_le_nao_cala_os_outros(
    servidor: Servidor, monkeypatch: pytest.MonkeyPatch, thread_lenta: bool
) -> None:
    """Um tipo que o servidor não responde não segura o retrato inteiro.

    Numa máquina em que UMA pergunta falha sempre (um servidor que não lista
    os módulos, por exemplo), o retrato que exigia as seis respostas para
    assumir ficava solto para sempre: todo leitor voltava a perguntar ao
    servidor — o defeito inteiro — e o padrão publicado ficava vazio, embora o
    servidor respondesse o resto. E a insistência relê só o que falta.

    MORDIDAS: exija a leitura inteira para o primeiro dono assumir (o retrato
    nunca fica vivo); releia todos os tipos na insistência (as saídas voltam a
    ser perguntadas sem evento).

    A THREAD LENTA (O-CI-DA-DEV-VOLTA-A-VERDE-02): o `_o_padrao_do_retrato` com 50 ms
    de atraso é o runner do CI, em que a leitura do padrão (depois de o retrato ficar
    vivo e antes da publicação) passa da volta do laço. MORDIDA: volte a barreira
    para o `RETRATO.vivo` e este caso reprova com «o padrão não foi publicado».
    """
    from hefesto_dualsense4unix.daemon.subsystems import ouvinte_do_som as ods

    if thread_lenta:
        original = ods._o_padrao_do_retrato

        def _lento() -> Any:
            time.sleep(0.05)
            return original()

        monkeypatch.setattr(ods, "_o_padrao_do_retrato", _lento)
    espiao = _Espiao()
    monkeypatch.setattr(rs.RETRATO, "_ler_injetado", espiao)
    monkeypatch.setattr(ods, "ESPERA_PARA_RELIGAR_S", 0.1)
    (servidor.raiz / "modules.curto").unlink()
    daemon = _Daemon()

    async def cenario() -> None:
        tarefa = asyncio.create_task(ods.ouvinte_do_som_loop(daemon))
        try:
            await _o_ouvinte_subiu(
                daemon, motivo="o retrato vivo sem os módulos, e o padrão publicado", prazo=3.0)
            await servidor.abrir_os_eventos()
            assert rs.RETRATO.padrao("sink") == HDMI
            assert any(p.get("saida") == HDMI for p in daemon.publicados), (
                "o padrão não foi publicado")
            assert rs.RETRATO.responder(["pactl", "list", "modules", "short"]) is rs.NAO_SEI
            servidor.zerar()
            await asyncio.sleep(0.6)
            chamadas = servidor.chamadas()
            assert "list modules short" in chamadas, "a insistência parou de tentar"
            outras = sorted({c for c in chamadas if c != "list modules short"})
            assert not outras, f"a insistência releu o que já sabia: {outras}"
        finally:
            await _parar(tarefa)

    _correr(cenario)
