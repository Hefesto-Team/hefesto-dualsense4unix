"""BG-03: a janela aberta forkava um par de `pgrep` a cada 3,3 s.

O DEFEITO, medido em 25/08/2026 na máquina dela (DAEMON-ACORDADO-01, seção
"Quem forka, e por que a cada 3,3 s")
====================================================================
Com a janela do Hefesto ABERTA e um DualSense no cabo, numa janela cronometrada
de 30 s:

  =====================  =========  ==========
  \\                      read/s     rchar
  =====================  =========  ==========
  processo                2.572,9   537,8 KB/s
  threads VIVAS             997,2    83,9 KB/s
  **buraco (fork/exec)**  **1.575,6**  **453,9 KB/s**
  =====================  =========  ==========

**61 % das leituras e 84 % dos bytes do daemon não eram do controle.** Um
`pgrep` isolado custa 2.533 `read()` e 724 KB nesta máquina: ele lê `/proc`
INTEIRO, e cada leitura de `/proc/<pid>/cmdline` toma o `mmap_read_lock` do
processo alvo — inclusive o do jogo.

POR QUE A RÉGUA CONTA CHAMADAS, E NÃO SEGUNDOS
==============================================
Relógio não é asserção. Um teste que meça `time.monotonic()` antes e depois
mede a MÁQUINA (carga, escalonador, cache do `/proc`), não o produto — e esta
casa já pagou por instrumento assim. O que a cura promete é aritmético e
exato: **N tiques dentro da validade disparam UM fork; sem cache, N**. Os
dublês daqui contam invocação.

E cada dublê sabe RECUSAR: os testes `..._a_regua_sabe_recusar` zeram a
validade e exigem que o MESMO contador veja o mundo ruim. Régua que só sabe
passar não é régua.
"""

from __future__ import annotations

import subprocess
import sys
from types import SimpleNamespace

import pytest

from hefesto_dualsense4unix.core import escritor_cru
from hefesto_dualsense4unix.integrations import steam_launch_options as slo

# ---------------------------------------------------------------------------
# Metade 1 — o `pgrep` do `core/escritor_cru.py`
# ---------------------------------------------------------------------------

#: A saída de um `pgrep` que achou a Steam. Dois pids, como na mesa dela.
_SAIDA_PGREP = "4242\n4243\n"


class _SubprocessContado:
    """Dublê de `subprocess` que CONTA cada fork — e sabe recusar.

    Expõe `SubprocessError` porque o `except` do produto o nomeia: um dublê
    que não sabe ser exceção não consegue exercitar a degradação.
    """

    SubprocessError = subprocess.SubprocessError

    def __init__(self, *, saida: str = _SAIDA_PGREP, erro: BaseException | None = None):
        self.chamadas: list[list[str]] = []
        self._saida = saida
        self._erro = erro

    def run(self, args, **_kwargs):
        self.chamadas.append(list(args))
        if self._erro is not None:
            raise self._erro
        return SimpleNamespace(returncode=0, stdout=self._saida)

    @property
    def forks(self) -> int:
        return len(self.chamadas)


class _RelogioFalso:
    """`time` com `monotonic()` que só anda quando o teste manda."""

    def __init__(self, agora: float = 0.0) -> None:
        self.agora = agora

    def monotonic(self) -> float:
        return self.agora


@pytest.fixture(autouse=True)
def _sem_foto_herdada():
    """As duas curas guardam foto em módulo, e foto de módulo vaza entre testes."""
    escritor_cru.invalidar_pids_da_steam()
    slo.invalidar_varredura_de_proc()
    yield
    escritor_cru.invalidar_pids_da_steam()
    slo.invalidar_varredura_de_proc()


def test_cinco_tiques_dentro_da_validade_forkam_um_par_so(monkeypatch) -> None:
    """A cura, em uma linha: cinco perguntas, um par de `pgrep`."""
    dubles = _SubprocessContado()
    monkeypatch.setattr(escritor_cru, "subprocess", dubles)

    for tique in range(5):  # 0, 1, 2, 3, 4 s — todos dentro dos 5 s de validade
        assert escritor_cru.pids_da_steam(agora=float(tique)) == [4242, 4243]

    assert dubles.forks == 2, (
        "a janela aberta continua forkando por tique: esperava UM par de "
        f"`pgrep` para cinco perguntas, contei {dubles.forks} forks "
        f"({dubles.chamadas})"
    )


def test_a_regua_sabe_recusar(monkeypatch) -> None:
    """O MESMO contador, com a validade zerada, tem de ver o mundo ruim.

    Sem este caso o teste acima passaria com um dublê cego (um que contasse
    sempre 2, ou nunca fosse chamado).
    """
    dubles = _SubprocessContado()
    monkeypatch.setattr(escritor_cru, "subprocess", dubles)
    monkeypatch.setattr(escritor_cru, "VALIDADE_DO_VEREDITO_S", 0.0)

    for tique in range(5):
        escritor_cru.pids_da_steam(agora=float(tique))

    assert dubles.forks == 10, (
        "a régua não enxerga fork: com a validade em zero os cinco tiques "
        f"tinham de custar dez `pgrep`, e contei {dubles.forks}"
    )


def test_a_foto_vence_a_validade_e_o_pgrep_volta(monkeypatch) -> None:
    """Cache não é congelamento: passados os 5 s, a próxima pergunta forka."""
    dubles = _SubprocessContado()
    monkeypatch.setattr(escritor_cru, "subprocess", dubles)

    escritor_cru.pids_da_steam(agora=0.0)
    escritor_cru.pids_da_steam(agora=4.999)
    assert dubles.forks == 2
    escritor_cru.pids_da_steam(agora=5.0)
    assert dubles.forks == 4, "a foto venceu e o produto não foi olhar de novo"


def test_forcar_ignora_a_foto(monkeypatch) -> None:
    """`forcar=True` é o contrato do vigia: pergunta de verdade, sempre."""
    dubles = _SubprocessContado()
    monkeypatch.setattr(escritor_cru, "subprocess", dubles)

    escritor_cru.pids_da_steam(agora=0.0)
    escritor_cru.pids_da_steam(agora=0.5, forcar=True)
    assert dubles.forks == 4


def test_o_caminho_da_janela_inteiro_paga_um_par_so(monkeypatch) -> None:
    """O caminho REAL: `controller.list` → `holders_de_hidraw` → `pids_da_steam`.

    É este que a medição de 25/08 pegou forkando a cada 3,3 s, e nenhum teste
    daqui podia afirmar a cura sem exercitá-lo de ponta a ponta.
    """
    dubles = _SubprocessContado()
    relogio = _RelogioFalso()
    monkeypatch.setattr(escritor_cru, "subprocess", dubles)
    monkeypatch.setattr(escritor_cru, "time", relogio)

    for tique in range(5):
        relogio.agora = tique * 1.0
        escritor_cru.holders_de_hidraw()

    assert dubles.forks == 2, (
        f"o caminho da janela ainda forka por tique: {dubles.forks} forks"
    )


def test_o_sentinela_forcado_joga_a_foto_fora(monkeypatch) -> None:
    """`sondar(forcar=True)` tem de valer para o cache NOVO também.

    Sem isto, "ignora a validade" passaria a ignorar só metade dela: a chegada
    de um controle (`connection.py`, `forcar=True`) veria pids de 5 s atrás.
    """
    dubles = _SubprocessContado()
    monkeypatch.setattr(escritor_cru, "subprocess", dubles)

    escritor_cru.pids_da_steam(agora=0.0)
    assert dubles.forks == 2

    sentinela = escritor_cru.SentinelaDeEscritorCru(sonda=lambda nos: {})
    sentinela.sondar(["/dev/hidraw0"], 0.1, forcar=True)

    assert escritor_cru._ultima_foto_de_pids is None, (
        "o `forcar=True` do sentinela deixou a foto de pids em pé — o cache "
        "novo transformou o contrato dele em mentira"
    )


def test_sem_pgrep_no_sistema_degrada_e_nao_levanta(monkeypatch) -> None:
    """O dublê recusando de outro jeito: `pgrep` que nem existe."""
    dubles = _SubprocessContado(erro=OSError("sem pgrep"))
    monkeypatch.setattr(escritor_cru, "subprocess", dubles)

    assert escritor_cru.pids_da_steam(agora=0.0) == []
    assert dubles.forks == 2  # tentou os dois padrões antes de desistir


# ---------------------------------------------------------------------------
# Metade 2 — a varredura nativa de `/proc` do `steam_launch_options.py`
# ---------------------------------------------------------------------------

REAPER = (
    "/home/vitoriamaria/.steam/debian-installation/ubuntu12_32/reaper "
    "SteamLaunch AppId=1599660 -- /.../proton waitforexitandrun /.../Launcher.exe"
)


class _SemMarker:
    """`daemon.launch_env` sem marker: força o caminho de varredura.

    É o jogo lançado FORA do wrapper — e é justamente nele que a varredura
    completa lia a cmdline do jogo a cada 2 s, tomando o `mmap_read_lock` dele.
    """

    @staticmethod
    def read_last_run_marker():
        return None

    @staticmethod
    def read_last_run_pid():
        return None


class _ProcContado:
    """`/proc` sintético que conta varreduras COMPLETAS e leituras de cmdline."""

    def __init__(self, mapa: dict[str, str]) -> None:
        self.mapa = mapa
        self.varreduras = 0
        self.cmdlines: list[str] = []

    def listdir(self, path):
        if str(path) != "/proc":
            return _LISTDIR_REAL(path)
        self.varreduras += 1
        return [*self.mapa, "self", "cpuinfo"]

    def cmdline_of(self, pid) -> str:
        self.cmdlines.append(str(pid))
        return self.mapa.get(str(pid), "")


_LISTDIR_REAL = slo.os.listdir


@pytest.fixture
def proc_contado(monkeypatch):
    """Instala o `/proc` sintético contado. Devolve o contador."""

    def _instalar(mapa: dict[str, str]) -> _ProcContado:
        contador = _ProcContado(mapa)
        monkeypatch.setattr(slo, "_cmdline_of", contador.cmdline_of)
        monkeypatch.setattr(slo.os, "listdir", contador.listdir)
        monkeypatch.setitem(
            sys.modules, "hefesto_dualsense4unix.daemon.launch_env", _SemMarker()
        )
        return contador

    return _instalar


def test_cinco_tiques_sem_jogo_varrem_proc_uma_vez(proc_contado) -> None:
    """O estado permanente de um daemon 24/7: jogo fechado, e ninguém olhando.

    Era 400 `openat` a cada 2 s, para sempre — e DUAS varreduras por tique,
    porque o poll loop pergunta duas coisas (`running` e `appid`).
    """
    contador = proc_contado({"100": "cosmic-comp", "101": "pipewire"})

    for tique in range(5):
        assert slo._steam_launch_cmdline(agora=float(tique)) is None

    assert contador.varreduras == 1, (
        "o jogo fechado continua custando uma varredura de `/proc` por "
        f"pergunta: esperava 1 para cinco tiques, contei {contador.varreduras}"
    )


def test_a_regua_da_varredura_sabe_recusar(proc_contado, monkeypatch) -> None:
    """Com a validade zerada, o MESMO contador tem de ver as cinco varreduras."""
    contador = proc_contado({"100": "cosmic-comp"})
    monkeypatch.setattr(slo, "VALIDADE_DA_VARREDURA_S", 0.0)

    for tique in range(5):
        slo._steam_launch_cmdline(agora=float(tique))

    assert contador.varreduras == 5, (
        "a régua não enxerga varredura: com a validade em zero os cinco "
        f"tiques tinham de varrer cinco vezes, e contei {contador.varreduras}"
    )


def test_jogo_fora_do_wrapper_custa_um_open_por_tique(proc_contado) -> None:
    """A camada 2, e é a que morde o engasgo: o jogo aberto SEM o marker.

    Antes: `/proc` inteiro a cada tique, lendo a cmdline do próprio jogo junto
    com a de todo mundo. Depois: uma varredura na vida, e um `open` por tique
    — o do jogo. E a resposta continua sendo de AGORA, não de cinco segundos
    atrás: o pid é reconfirmado contra a agulha toda vez.
    """
    contador = proc_contado({"100": "cosmic-comp", "200": REAPER})

    for tique in range(5):
        assert slo._steam_launch_cmdline(agora=float(tique)) == REAPER

    assert contador.varreduras == 1, (
        f"varreu `/proc` {contador.varreduras} vezes com o jogo aberto — a "
        "reconfirmação por pid não está segurando"
    )
    assert contador.cmdlines[-4:] == ["200"] * 4, (
        "os quatro tiques depois da varredura tinham de ler UM cmdline (o do "
        f"jogo) e leram {contador.cmdlines[-4:]}"
    )


def test_o_jogo_que_fechou_e_notado_no_tique_seguinte(proc_contado) -> None:
    """Cache de positivo seria mentira: "há jogo" tem de morrer com o jogo.

    O tique seguinte ao fim do jogo está DENTRO da validade — e mesmo assim a
    resposta muda, porque a camada 2 reconfirma o pid em vez de acreditar nele.
    """
    contador = proc_contado({"200": REAPER})
    assert slo._steam_launch_cmdline(agora=0.0) == REAPER

    contador.mapa.clear()  # o jogo fechou
    assert slo._steam_launch_cmdline(agora=1.0) is None, (
        "o produto continuou dizendo que há jogo aberto depois de o jogo "
        "fechar — é a mentira que guarda gesto destrutivo"
    )


def test_proc_ilegivel_nao_vira_cinco_segundos_de_negativo(monkeypatch) -> None:
    """Ausência de leitura não é "não há jogo" — e não pode carimbar a foto."""
    tentativas: list[str] = []

    def _boom(path):
        if str(path) != "/proc":
            return _LISTDIR_REAL(path)
        tentativas.append(str(path))
        raise OSError("sem /proc")

    monkeypatch.setattr(slo.os, "listdir", _boom)
    monkeypatch.setitem(
        sys.modules, "hefesto_dualsense4unix.daemon.launch_env", _SemMarker()
    )

    assert slo._steam_launch_cmdline(agora=0.0) is None
    assert slo._steam_launch_cmdline(agora=1.0) is None
    assert len(tentativas) == 2, (
        "um `/proc` ilegível virou negativo carimbado: o produto parou de "
        "tentar por cinco segundos com base numa leitura que nunca aconteceu"
    )


def test_gesto_destrutivo_varre_de_verdade(proc_contado) -> None:
    """Fechar a Steam com jogo aberto MATA o jogo: ali não se aceita foto.

    O jogo nasce DEPOIS da varredura que não o viu, e dentro da validade — o
    caminho destrutivo tem de enxergá-lo assim mesmo.
    """
    contador = proc_contado({"100": "cosmic-comp"})
    assert slo._steam_launch_cmdline(agora=0.0) is None

    contador.mapa["200"] = REAPER  # ela abriu um jogo fora do wrapper
    assert slo._steam_launch_cmdline(agora=1.0) is None  # a foto ainda vale

    slo.invalidar_varredura_de_proc()  # o que todo gesto destrutivo faz antes
    assert slo.steam_game_running() is True, (
        "o caminho que vai FECHAR a Steam aceitou um negativo velho — com um "
        "jogo aberto, esse é o caminho que mata progresso não salvo dela"
    )
