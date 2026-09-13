"""O gravador da ponte de som MORRE, e morre ANTES de o nó sair.

SOM-TRAVA-NA-QUEDA-01, 13/09/2026. A queixa dela, no mesmo dia, pela segunda
vez: o som da máquina parou de sair e a Steam e os jogos ficaram sem janela.

O DEFEITO, MEDIDO NO ESTUDO DA SPRINT
-------------------------------------
Na queda do controle no rádio, o laço da `PonteDeSomPorRadio` para de ler o
`pw-record` do monitor do nó (a escrita no hidraw é recusada), o cano enche em
cerca de 0,34 s e a única thread do gravador fica parada no `write`. O SIGTERM
do `descer()` fica PENDENTE para sempre. O gravador sobrevivia à ponte e ao nó,
e todo cliente que mexia num parâmetro do nó dele ficava esperando por ele.

OS DUBLÊS, e por que são processos de verdade
---------------------------------------------
Nenhum servidor de som roda aqui. O gravador é um `python -c` que reproduz o
`pw-record` medido: SIGTERM BLOQUEADO (o `signalfd` dele), SIGPIPE no padrão, e
escrevendo no `stdout` até o cano encher — com espera por
`/proc/<pid>/wchan == anon_pipe_write`. O teimoso ignora também o SIGPIPE, e só
o KILL o derruba. Um dublê em Python puro, sem processo, passaria com a cura
arrancada: o que se mede é o KERNEL entregando SIGPIPE, não um método chamado.

A PONTE É A DE VERDADE, com o laço de verdade: só o codificador Opus e o hidraw
são dublês. O hidraw é um cano com a ponta de leitura fechada, e a escrita
recusada é o que faz o laço sair — a mesma porta da queda no diário dela.

AS RÉGUAS E AS MORDIDAS (cada uma medida na entrega da sprint)
--------------------------------------------------------------
* R1 — o gravador preso morre no `descer`, por SIGPIPE, em até 200 ms.
  MORDIDA: o `descer` de antes (só `terminate`) deixa o dublê vivo.
* R2 — o teimoso morre por KILL em até 1,5 s.
  MORDIDA: tirar o `kill` de `filho_de_som.derrubar_leitor_de_pipe` deixa vivo.
* R3 — na queda, o gravador já foi colhido quando o nó sai.
  MORDIDA: trocar a ordem de `_casar_as_pontes` e `gerenciador.reconciliar` em
  `AltoFalanteSubsystem._reconciliar`.
* R4 — no `stop`, o gravador é colhido antes de `gerenciador.parar()`.
  MORDIDA: o `stop` de antes (nós primeiro) reprova.
* R5 — o filho ocioso morre com o pai morto por SIGKILL.
  MORDIDA: tirar o `preexec_fn` de `filho_de_som.lancar_leitor` deixa o filho
  vivo, adotado por outro processo.
* R6 — o alimentador do cabo, com o bombeador morto, é colhido em < 100 ms.
  MORDIDA: a ordem de antes (`terminate` e `wait(2 s)`) leva 2 s.

E duas portas do órfão que o estudo nomeou: a ponte que não sobe e o gravador
sem `stdout`.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import canal_do_microfone as canal

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="SIGPIPE, PR_SET_PDEATHSIG e /proc são do Linux",
)

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: Faixa FORJADA da casa — nunca o endereço de um controle dela.
P1 = "aa:bb:cc:00:00:01"

#: A marca no argv de todo dublê. É por ela que a régua confere um PID antes de
#: matar um sobrevivente — nunca por nome de processo.
MARCA = "hefesto-regua-som-trava-na-queda"

#: O `pw-record` medido: TERM bloqueado (o signalfd), SIGPIPE no padrão, e o
#: `write` bloqueante até o cano encher.
DUBLE_PW_RECORD = r"""
import os, signal
signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
bloco = b"\0" * 1920
while True:
    os.write(1, bloco)
"""

#: O pior caso: TERM bloqueado E SIGPIPE ignorado. Só o KILL derruba.
DUBLE_TEIMOSO = r"""
import os, signal, time
signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
signal.signal(signal.SIGPIPE, signal.SIG_IGN)
bloco = b"\0" * 1920
while True:
    try:
        os.write(1, bloco)
    except BrokenPipeError:
        time.sleep(0.01)
"""

#: O gravador SÃO: escreve sem parar e morre no SIGTERM, como o `pw-record`
#: que não está preso (medido no estudo: 1 ms).
DUBLE_SAO = r"""
import os
bloco = b"\0" * 1920
while True:
    os.write(1, bloco)
"""

#: O gravador OCIOSO: não escreve nada, logo nunca toma SIGPIPE. É o caso que
#: só o `PR_SET_PDEATHSIG` cobre quando o daemon morre por SIGKILL.
DUBLE_OCIOSO = "import time\ntime.sleep(300)\n"


def _argv(codigo: str) -> list[str]:
    return [sys.executable, "-c", codigo, MARCA]


@pytest.fixture
def dubles() -> Iterator[list[subprocess.Popen[bytes]]]:
    """Todo dublê que a régua abre, a régua COLHE — inclusive com a cura arrancada."""
    abertos: list[subprocess.Popen[bytes]] = []
    yield abertos
    for proc in abertos:
        if proc.poll() is None:
            with contextlib.suppress(OSError):
                proc.kill()
        with contextlib.suppress(Exception):
            proc.wait(timeout=5)
        if proc.stdout is not None:
            with contextlib.suppress(Exception):
                proc.stdout.close()


def _lancador(
    codigo: str, abertos: list[subprocess.Popen[bytes]], *, sem_saida: bool = False
) -> Callable[[list[str]], subprocess.Popen[bytes]]:
    """O `abrir` injetado: lança o DUBLÊ no lugar do `pw-record` ou do `parec`."""

    def _abrir(_argv_do_produto: list[str]) -> subprocess.Popen[bytes]:
        proc = subprocess.Popen(
            _argv(codigo),
            stdout=subprocess.DEVNULL if sem_saida else subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        abertos.append(proc)
        return proc

    return _abrir


def _wchan(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/wchan", encoding="ascii") as arquivo:
            return arquivo.read().strip()
    except OSError:
        return ""


def _esperar_o_cano_encher(pid: int) -> None:
    """Até o dublê parar no `write` do cano cheio — o estado do órfão da queda.

    Onde o kernel não mostra o `wchan`, espera o bastante para o cano encher: o
    dublê escreve mais de 1 MB por segundo e o cano tem 64 KiB.
    """
    prazo = time.monotonic() + 5.0
    while time.monotonic() < prazo:
        wchan = _wchan(pid)
        if wchan == "anon_pipe_write":
            return
        if wchan in ("", "0") and time.monotonic() > prazo - 4.5:
            return
        time.sleep(0.01)
    pytest.fail(f"o dublê {pid} não parou no write do cano cheio (wchan={_wchan(pid)!r})")


class _CodificadorDeMentira:
    """Um quadro Opus de tamanho certo, sem a libopus. O laço é o de verdade."""

    def __init__(self, **_kw: Any) -> None:
        pass

    def codificar(self, _pcm: bytes) -> bytes:
        return b"\x01" * af.BYTES_POR_QUADRO_OPUS


def _hidraw_que_caiu() -> int:
    """Um fd cuja escrita é recusada: o controle saiu do rádio."""
    leitura, escrita = os.pipe()
    os.close(leitura)
    return escrita


def _hidraw_que_aceita() -> int:
    """Um fd que aceita tudo: o controle está no ar."""
    return os.open(os.devnull, os.O_WRONLY)


@pytest.fixture
def ponte_real(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ponte sobe sem libopus e sem `pw-record` na máquina — só por dublê."""
    monkeypatch.setattr(af, "a_ponte_do_radio_pode_subir", lambda: (True, ""))
    monkeypatch.setattr(af, "CodificadorOpus", _CodificadorDeMentira)
    monkeypatch.setattr(
        af, "argv_do_gravador", lambda fonte, **_kw: ["pw-record", f"--target={fonte}", "-"]
    )


def _ponte(
    abertos: list[subprocess.Popen[bytes]],
    *,
    codigo: str = DUBLE_PW_RECORD,
    abrir_hidraw: Callable[[], int] = _hidraw_que_caiu,
) -> tuple[af.PonteDeSomPorRadio, subprocess.Popen[bytes]]:
    """Uma ponte de verdade, com o gravador vindo pela porta REAL de lançamento."""
    fonte, proc, motivo = af.fonte_do_monitor_do_no(
        af.nome_do_sink(P1), abrir=_lancador(codigo, abertos)
    )
    assert fonte is not None and proc is not None, motivo
    ponte = af.PonteDeSomPorRadio(
        uniq=P1, abrir_hidraw=abrir_hidraw, fonte_de_pcm=fonte, gravador=proc
    )
    assert ponte.subir() is True, ponte.motivo
    return ponte, proc


def _ponte_na_queda(
    abertos: list[subprocess.Popen[bytes]], *, codigo: str = DUBLE_PW_RECORD
) -> tuple[af.PonteDeSomPorRadio, subprocess.Popen[bytes]]:
    """A ponte no instante da queda: o laço já saiu e o gravador está preso."""
    ponte, proc = _ponte(abertos, codigo=codigo)
    prazo = time.monotonic() + 5.0
    while ponte._corrida_viva() and time.monotonic() < prazo:
        time.sleep(0.01)
    assert not ponte._corrida_viva(), (
        "o laço não saiu com a escrita recusada — a régua não reproduziu a queda"
    )
    _esperar_o_cano_encher(proc.pid)
    assert proc.poll() is None, "o dublê morreu sozinho — a régua não mede nada"
    return ponte, proc


def _ponte_tocando(
    abertos: list[subprocess.Popen[bytes]],
) -> tuple[af.PonteDeSomPorRadio, subprocess.Popen[bytes]]:
    """A ponte tocando: o laço lê, o hidraw aceita, o gravador está são."""
    ponte, proc = _ponte(abertos, codigo=DUBLE_SAO, abrir_hidraw=_hidraw_que_aceita)
    prazo = time.monotonic() + 5.0
    while time.monotonic() < prazo:
        contagem = ponte.contagem
        if contagem is not None and contagem.reports_montados > 3:
            break
        time.sleep(0.01)
    assert ponte.esta_de_pe(), "a ponte não ficou tocando — a régua não mede o caso"
    assert proc.poll() is None
    return ponte, proc


class _No:
    """O nó do PipeWire, dublê: anota se o gravador ainda vivia quando ele saiu."""

    def __init__(self, gravador: subprocess.Popen[bytes], saidas: list[int | None]) -> None:
        self._gravador = gravador
        self._saidas = saidas

    def iniciar(self) -> bool:
        return True

    def parar(self) -> None:
        self._saidas.append(self._gravador.poll())


def _gerenciador_com_o_no_de_pe(
    gravador: subprocess.Popen[bytes], saidas: list[int | None]
) -> mod.GerenciadorDeNosDeSom:
    ger = mod.GerenciadorDeNosDeSom(fabrica=lambda _uniq: _No(gravador, saidas))
    ger.reconciliar([P1])
    assert P1 in ger.nos, "o nó não subiu — a régua não mediria a saída dele"
    return ger


# ---------------------------------------------------------------------------
# R1 e R2 — o `descer` colhe o gravador
# ---------------------------------------------------------------------------


def test_r1_o_gravador_preso_morre_no_descer_por_sigpipe(
    ponte_real: None, dubles: list[subprocess.Popen[bytes]]
) -> None:
    """A queda: laço fora, cano cheio, TERM pendente. O `descer` o derruba.

    MORDIDA: com o `descer` de antes (só `terminate`) o dublê fica vivo, no
    `write`, com o SIGTERM pendente — exatamente o órfão da máquina dela.
    """
    ponte, proc = _ponte_na_queda(dubles)

    comeco = time.monotonic()
    assert ponte.descer() is True
    ms = (time.monotonic() - comeco) * 1000.0

    assert proc.poll() is not None, (
        f"o gravador (pid {proc.pid}) continua vivo depois do `descer`, com "
        f"wchan={_wchan(proc.pid)!r} — é o órfão que segurou a sessão de som dela"
    )
    assert proc.returncode == -signal.SIGPIPE, (
        f"morreu com {proc.returncode}, e não por SIGPIPE: o cano não foi fechado "
        "com o laço já parado"
    )
    assert ms <= 200.0, f"o `descer` levou {ms:.1f} ms para colher o gravador preso"
    assert ponte.como_morreu_o_gravador is not None
    assert ponte.como_morreu_o_gravador.por == "SIGPIPE"


def test_r2_o_teimoso_morre_por_kill(
    ponte_real: None, dubles: list[subprocess.Popen[bytes]]
) -> None:
    """TERM bloqueado e SIGPIPE ignorado: só o KILL, e dentro do prazo.

    MORDIDA: tire o `kill` de `filho_de_som.derrubar_leitor_de_pipe` e o
    teimoso sobrevive ao `descer`.
    """
    ponte, proc = _ponte_na_queda(dubles, codigo=DUBLE_TEIMOSO)

    comeco = time.monotonic()
    ponte.descer()
    segundos = time.monotonic() - comeco

    assert proc.poll() is not None, (
        f"o teimoso (pid {proc.pid}) sobreviveu ao `descer` — sem o KILL não há "
        "o que o derrube"
    )
    assert proc.returncode == -signal.SIGKILL, f"morreu com {proc.returncode}"
    assert segundos <= 1.5, f"o KILL chegou em {segundos:.2f} s"
    assert ponte.como_morreu_o_gravador is not None
    assert ponte.como_morreu_o_gravador.insistiu is True


# ---------------------------------------------------------------------------
# R3 e R4 — a ORDEM: o gravador morre antes de o nó sair
# ---------------------------------------------------------------------------


def test_r3_na_queda_o_gravador_ja_foi_colhido_quando_o_no_sai(
    ponte_real: None, dubles: list[subprocess.Popen[bytes]]
) -> None:
    """O controle sumiu da lista: a ponte desce e o nó sai, NESTA ordem.

    MORDIDA: em `AltoFalanteSubsystem._reconciliar`, chame
    `gerenciador.reconciliar(alvos)` antes de `self._casar_as_pontes(alvos)` —
    o nó sai com o gravador ainda preso.
    """
    ponte, proc = _ponte_na_queda(dubles)
    saidas: list[int | None] = []
    ger = _gerenciador_com_o_no_de_pe(proc, saidas)
    sub = mod.AltoFalanteSubsystem(gerenciador=ger, fonte_de_controles=lambda: [])
    sub._pontes[P1] = ponte

    sub._reconciliar(ger)

    assert saidas, "o nó não saiu na queda — a régua não mediu a ordem"
    assert saidas[0] is not None, (
        "o nó saiu com o gravador da ponte ainda vivo — a ponte tem de descer "
        "(e colher o gravador) antes de `gerenciador.reconciliar`"
    )
    assert P1 not in sub._pontes


@pytest.mark.parametrize("cena", ["na_queda", "tocando"])
def test_r4_no_stop_o_gravador_e_colhido_antes_de_os_nos_sairem(
    ponte_real: None, dubles: list[subprocess.Popen[bytes]], cena: str
) -> None:
    """O desligamento do daemon: pontes primeiro, nós depois — nas duas cenas.

    MORDIDA: com o `stop` de antes, `gerenciador.parar()` vinha primeiro e os
    nós saíam com o gravador vivo.
    """
    if cena == "na_queda":
        ponte, proc = _ponte_na_queda(dubles)
    else:
        ponte, proc = _ponte_tocando(dubles)
    saidas: list[int | None] = []
    ger = _gerenciador_com_o_no_de_pe(proc, saidas)
    sub = mod.AltoFalanteSubsystem(gerenciador=ger, fonte_de_controles=lambda: [])
    sub._gerenciador = ger
    sub._pontes[P1] = ponte

    asyncio.run(sub.stop())

    assert saidas, "o nó não saiu no stop — a régua não mediu a ordem"
    assert saidas[0] is not None, (
        f"[{cena}] os nós saíram no `stop` com o gravador ainda vivo — as pontes "
        "têm de descer antes de `gerenciador.parar()`"
    )
    assert proc.poll() is not None
    assert sub._pontes == {}


# ---------------------------------------------------------------------------
# R5 — o filho ocioso morre com o pai morto por SIGKILL
# ---------------------------------------------------------------------------

_PAI_DO_GRAVADOR = """
import sys, time
sys.path.insert(0, {raiz!r} + "/src")
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
af.argv_do_gravador = lambda fonte, **kw: {argv!r}
fonte, proc, motivo = af.fonte_do_monitor_do_no("hefesto_som_000001")
print(proc.pid if proc is not None else 0, flush=True)
time.sleep(300)
"""

_PAI_DO_ALIMENTADOR = """
import sys, time
sys.path.insert(0, {raiz!r} + "/src")
from hefesto_dualsense4unix.integrations import canal_do_microfone as canal
canal.argv_do_alimentador = lambda *a, **kw: {argv!r}
class Source:
    taxa_hz = 48000
    canais = 1
    def escrever(self, pcm):
        return True
alimentador = canal._Alimentador("aabbcc000001", "fonte-de-mentira", Source())
print(alimentador._proc.pid if alimentador.iniciar() else 0, flush=True)
time.sleep(300)
"""


def _cmdline(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as arquivo:
            return arquivo.read().replace(b"\0", b" ").decode(errors="replace")
    except OSError:
        return ""


def _pai_de(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/stat", encoding="ascii") as arquivo:
            return arquivo.read().rsplit(")", 1)[1].split()[1]
    except (OSError, IndexError):
        return "?"


@pytest.mark.parametrize(
    "roteiro", [_PAI_DO_GRAVADOR, _PAI_DO_ALIMENTADOR], ids=["gravador", "alimentador"]
)
def test_r5_o_filho_ocioso_morre_com_o_pai(roteiro: str) -> None:
    """O daemon morto por SIGKILL não roda `finally`: quem mata o filho é o kernel.

    O pai é um processo SEPARADO, que lança o filho pela porta do PRODUTO
    (`fonte_do_monitor_do_no` sem `abrir`, e `_Alimentador` sem `lancar`) — só o
    argv vira o dublê ocioso. O filho ocioso não escreve, então não há SIGPIPE
    que o salve.

    MORDIDA: tire o `preexec_fn` de `filho_de_som.lancar_leitor` e o filho
    sobrevive ao pai, adotado por outro processo.
    """
    pai = subprocess.Popen(
        [sys.executable, "-c", roteiro.format(raiz=RAIZ, argv=_argv(DUBLE_OCIOSO))],
        stdout=subprocess.PIPE,
        text=True,
    )
    neto = 0
    try:
        assert pai.stdout is not None
        neto = int(pai.stdout.readline().strip() or 0)
        assert neto, "o produto não lançou o filho — a régua não mediu nada"
        prazo = time.monotonic() + 5.0
        while MARCA not in _cmdline(neto) and time.monotonic() < prazo:
            time.sleep(0.01)
        assert MARCA in _cmdline(neto), "o filho nem chegou a ser o dublê"

        pai.kill()
        pai.wait(timeout=5)

        prazo = time.monotonic() + 1.0
        while MARCA in _cmdline(neto) and time.monotonic() < prazo:
            time.sleep(0.02)

        assert MARCA not in _cmdline(neto), (
            f"o filho (pid {neto}) SOBREVIVEU ao SIGKILL do pai, agora com ppid "
            f"{_pai_de(neto)} — o `preexec_fn=morrer_com_o_pai` caiu do lançamento"
        )
    finally:
        with contextlib.suppress(Exception):
            pai.kill()
            pai.wait(timeout=5)
        if pai.stdout is not None:
            pai.stdout.close()
        # O sobrevivente da mordida é colhido pela régua, por PID conferido pela
        # MARCA no argv — nunca por nome de processo.
        if neto and MARCA in _cmdline(neto):
            with contextlib.suppress(OSError):
                os.kill(neto, signal.SIGKILL)


# ---------------------------------------------------------------------------
# R6 — o alimentador do cabo não segura o fechamento por 2 s
# ---------------------------------------------------------------------------


class _SourceQueSumiu:
    """O nó do canal que sumiu: o `escrever` levanta, e o bombeador morre."""

    taxa_hz = 48000
    canais = 1

    def escrever(self, _pcm: bytes) -> bool:
        raise OSError("o fifo do canal sumiu")


def test_r6_o_alimentador_com_o_bombeador_morto_e_colhido_depressa(
    dubles: list[subprocess.Popen[bytes]],
) -> None:
    """Ninguém lê o cano do `parec`: fechar o canal não pode esperar o prazo.

    MORDIDA: a ordem de antes (`terminate` → `wait(2 s)` → `kill`) leva os 2 s
    inteiros, porque o TERM não alcança quem está parado no `write`.
    """
    alimentador = canal._Alimentador(
        "aabbcc000001", "fonte-de-mentira", _SourceQueSumiu(),
        lancar=_lancador(DUBLE_PW_RECORD, dubles),
    )
    assert alimentador.iniciar() is True
    proc = alimentador._proc
    bomba = alimentador._bomba
    assert proc is not None and bomba is not None
    bomba.join(timeout=5)
    assert not bomba.is_alive(), "o bombeador não morreu — a régua não mede o caso"
    _esperar_o_cano_encher(proc.pid)

    comeco = time.monotonic()
    alimentador.parar()
    ms = (time.monotonic() - comeco) * 1000.0

    assert proc.poll() is not None, f"o alimentador (pid {proc.pid}) ficou vivo"
    assert ms < 100.0, f"fechar o canal levou {ms:.0f} ms com o bombeador já morto"
    assert proc.returncode == -signal.SIGPIPE, f"morreu com {proc.returncode}"


# ---------------------------------------------------------------------------
# As outras duas portas do órfão
# ---------------------------------------------------------------------------


def test_a_ponte_que_nao_sobe_colhe_o_gravador(
    ponte_real: None,
    dubles: list[subprocess.Popen[bytes]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O gravador já nasceu e a ponte não subiu: ninguém lê aquele cano, nunca.

    MORDIDA: com o `descer` de antes o gravador fica vivo, preso no cano.
    """
    real = af.fonte_do_monitor_do_no

    def _com_o_duble(id_do_no: str, **_kw: Any) -> tuple[Any, Any, str]:
        resposta = real(id_do_no, abrir=_lancador(DUBLE_PW_RECORD, dubles))
        # Preso ANTES de a ponte recusar: um dublê ainda nascendo morreria no
        # TERM de qualquer `descer`, e a régua passaria com a cura arrancada.
        _esperar_o_cano_encher(resposta[1].pid)
        return resposta

    monkeypatch.setattr(af, "fonte_do_monitor_do_no", _com_o_duble)
    monkeypatch.setattr(af, "a_ponte_do_radio_pode_subir", lambda: (False, "sem libopus"))

    class _Controle:
        uniq = P1
        caminho = "/dev/hidraw-de-mentira"
        transporte = "bluetooth"

    sub = mod.AltoFalanteSubsystem(fonte_de_controles=lambda: [])
    sub._casar_as_pontes([_Controle()])

    assert sub._pontes == {}
    assert len(dubles) == 1, "o gravador nem foi lançado — a régua não mede nada"
    assert dubles[0].poll() is not None, (
        "a ponte não subiu e o gravador dela ficou vivo, sem ninguém para lê-lo"
    )
    assert dubles[0].returncode == -signal.SIGPIPE, f"morreu com {dubles[0].returncode}"


def test_o_gravador_sem_stdout_e_colhido_antes_de_voltar(
    ponte_real: None, dubles: list[subprocess.Popen[bytes]]
) -> None:
    """Sem `stdout` não há fonte, nem ponte, nem quem derrube o processo.

    MORDIDA: devolva `(None, proc, …)` sem `derrubar_leitor_de_pipe` e o
    processo fica vivo.
    """
    fonte, proc, motivo = af.fonte_do_monitor_do_no(
        af.nome_do_sink(P1), abrir=_lancador(DUBLE_OCIOSO, dubles, sem_saida=True)
    )

    assert len(dubles) == 1, "o gravador nem foi lançado — a régua não mede nada"
    assert dubles[0].poll() is not None, "o gravador sem `stdout` ficou vivo"
    assert fonte is None and motivo
    assert proc is None, "o processo derrubado não pode voltar como se estivesse de pé"
