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
exato: **N tiques dentro da validade disparam UMA varredura; sem cache, N**.
Os dublês daqui contam invocação.

E cada dublê sabe RECUSAR: os testes `..._a_regua_sabe_recusar` zeram a
validade e exigem que o MESMO contador veja o mundo ruim. Régua que só sabe
passar não é régua.

O QUE MUDOU EM 06/09/2026 — DAEMON-ACORDADO-01/E2
=================================================
**A metade 1 contava `fork`, e não há mais `fork` que contar.** O
`pids_da_steam` deixou de rodar o par de `pgrep` e passou a varrer `/proc`
nativamente, como a PERF-PROC-SCAN-01 já fazia do outro lado deste arquivo —
o custo medido caiu de 3.859 para 1.465 `read()` por chamada, e de 20,8 para
3,8 ms, nesta máquina com 430 processos.

Um dublê de `subprocess` sobre um produto que não chama `subprocess` conta
ZERO para sempre e passa em tudo: seria a régua que mede o mundo de ontem, o
defeito que esta casa nomeou em 05/09. Então a metade 1 conta agora o que a
metade 2 sempre contou — **varreduras de `/proc`** — e as duas metades passam
a falar a mesma língua.

E a régua ganhou uma asserção que o dublê de `subprocess` não podia fazer:
**quais arquivos o produto abre por pid**. É ela que prova que o `-x steam` do
`pgrep` continua sendo comparado com o `comm`, e não deduzido do `argv[0]`.
"""

from __future__ import annotations

import sys

import pytest

from hefesto_dualsense4unix.core import escritor_cru
from hefesto_dualsense4unix.integrations import steam_launch_options as slo

# ---------------------------------------------------------------------------
# Metade 1 — a varredura de `/proc` do `core/escritor_cru.py`
# ---------------------------------------------------------------------------

#: O `/proc` sintético da mesa dela: a Steam pelo runtime (o antigo
#: `pgrep -f steamrt64/steam`), a Steam fora do runtime (o antigo `pgrep -x
#: steam`, que compara o `comm`) e três vizinhos que não podem casar.
_PROC_COM_A_STEAM: dict[str, tuple[str, str]] = {
    # pid: (comm, cmdline)
    "100": ("cosmic-comp", "/usr/bin/cosmic-comp"),
    "4242": (
        "steam",
        "/home/vitoriamaria/.local/share/Steam/ubuntu12_32/steam",
    ),
    "4243": (
        "srt-bwrap",
        "/home/vitoriamaria/.steam/root/ubuntu12_64/steamrt64/steam-runtime "
        "-- /usr/bin/steam",
    ),
    "9000": ("pipewire", "/usr/bin/pipewire"),
    # A ISCA, e ela é real: um script que PROCURA a Steam carrega a agulha na
    # própria cmdline. O `pgrep` só se excluía a si mesmo, nunca ao vizinho —
    # então ele casava esta linha, e a varredura casa igual. Contrato idêntico
    # é o que esta sprint promete; virar o comportamento aqui em silêncio
    # seria trocar de contrato dizendo que só se trocou de mecanismo.
    "9100": ("bash", "/bin/bash -c pgrep -f steamrt64/steam"),
}

#: Quem o produto tem de achar no `/proc` acima — os dois da Steam e a isca.
_PIDS_ESPERADOS = [4242, 4243, 9100]


class _ProcDaSteamContado:
    """`/proc` sintético que CONTA varreduras e ARQUIVOS abertos — e recusa.

    Conta duas coisas diferentes de propósito:

    * `varreduras` — quantas vezes o produto chamou `os.listdir("/proc")`. É o
      que o cache promete zerar, e é o que o dublê de `subprocess` contava
      antes com o nome de `forks`;
    * `abertos` — a lista de `(pid, arquivo)` que o produto leu. É a asserção
      que o dublê velho não conseguia fazer: ela prova que o `comm` é LIDO, e
      não deduzido do `argv[0]`.

    `erro` faz o `listdir` levantar: é o `/proc` ilegível, e é como este dublê
    sabe RECUSAR.
    """

    def __init__(
        self,
        mapa: dict[str, tuple[str, str]] | None = None,
        *,
        erro: BaseException | None = None,
    ) -> None:
        self.mapa = dict(_PROC_COM_A_STEAM if mapa is None else mapa)
        self.varreduras = 0
        self.abertos: list[tuple[str, str]] = []
        self._erro = erro

    def listdir(self, path):
        if str(path) != "/proc":
            return _LISTDIR_REAL(path)
        self.varreduras += 1
        if self._erro is not None:
            raise self._erro
        return [*self.mapa, "self", "cpuinfo", "uptime"]

    def comm_de_pid(self, pid) -> str:
        self.abertos.append((str(pid), "comm"))
        return self.mapa.get(str(pid), ("", ""))[0]

    def cmdline_de_pid(self, pid) -> str:
        self.abertos.append((str(pid), "cmdline"))
        return self.mapa.get(str(pid), ("", ""))[1]


@pytest.fixture
def proc_da_steam(monkeypatch):
    """Instala o `/proc` sintético em `escritor_cru`. Devolve o contador."""

    def _instalar(
        mapa: dict[str, tuple[str, str]] | None = None,
        *,
        erro: BaseException | None = None,
    ) -> _ProcDaSteamContado:
        contador = _ProcDaSteamContado(mapa, erro=erro)
        monkeypatch.setattr(escritor_cru.os, "listdir", contador.listdir)
        monkeypatch.setattr(escritor_cru, "_comm_de_pid", contador.comm_de_pid)
        monkeypatch.setattr(escritor_cru, "cmdline_de_pid", contador.cmdline_de_pid)
        return contador

    return _instalar


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


def test_a_varredura_acha_a_steam_pelos_dois_criterios(proc_da_steam) -> None:
    """Antes de contar barato, provar que acha — nos DOIS critérios do `pgrep`.

    Uma varredura que devolvesse `[]` passaria em todos os testes de cache
    abaixo, e é o defeito que esta casa nomeou seis vezes: a régua que dá verde
    sobre nada.
    """
    proc_da_steam()

    assert escritor_cru.pids_da_steam(agora=0.0) == _PIDS_ESPERADOS


def test_o_comm_e_lido_e_nao_deduzido_do_argv(proc_da_steam) -> None:
    """`pgrep -x steam` compara o `comm`, e o produto tem de ler o `comm`.

    O pid 4242 tem `comm == "steam"` e uma cmdline que NÃO contém
    `steamrt64/steam`: só é achado por quem lê `/proc/<pid>/comm`. Deduzir o
    nome do `argv[0]` seria uma regra diferente com cara de igual — `comm` é
    definível por `prctl` e truncado em 15 bytes.
    """
    contador = proc_da_steam()
    escritor_cru.pids_da_steam(agora=0.0)

    assert ("4242", "comm") in contador.abertos, (
        "o produto não leu `/proc/4242/comm` — se ele achou a Steam sem isso, "
        f"achou por outra regra. Abriu: {contador.abertos}"
    )
    assert "steamrt64/steam" not in _PROC_COM_A_STEAM["4242"][1], (
        "o dublê deixou de morder: o pid 4242 só prova a regra do `comm` "
        "enquanto a cmdline dele NÃO casar a agulha da outra regra"
    )


def test_a_cmdline_so_e_lida_quando_o_comm_nao_resolveu(proc_da_steam) -> None:
    """Dois arquivos por pid é o teto, e o `comm` que casa dispensa o segundo.

    É metade da cura: o `pgrep` lia CINCO arquivos por processo.
    """
    contador = proc_da_steam()
    escritor_cru.pids_da_steam(agora=0.0)

    assert ("4242", "cmdline") not in contador.abertos, (
        "o `comm` casou e o produto foi ler a cmdline assim mesmo — é um "
        f"`open` a mais por processo da Steam. Abriu: {contador.abertos}"
    )
    por_pid = [p for p, _ in contador.abertos]
    assert max(por_pid.count(p) for p in set(por_pid)) <= 2, (
        f"algum pid custou mais de dois arquivos: {contador.abertos}"
    )


def test_cinco_tiques_dentro_da_validade_varrem_uma_vez(proc_da_steam) -> None:
    """A cura, em uma linha: cinco perguntas, uma varredura."""
    contador = proc_da_steam()

    for tique in range(5):  # 0, 1, 2, 3, 4 s — todos dentro dos 5 s de validade
        assert escritor_cru.pids_da_steam(agora=float(tique)) == _PIDS_ESPERADOS

    assert contador.varreduras == 1, (
        "a janela aberta continua varrendo `/proc` por tique: esperava UMA "
        f"varredura para cinco perguntas, contei {contador.varreduras}"
    )


def test_a_regua_sabe_recusar(proc_da_steam, monkeypatch) -> None:
    """O MESMO contador, com a validade zerada, tem de ver o mundo ruim.

    Sem este caso o teste acima passaria com um dublê cego (um que contasse
    sempre 1, ou nunca fosse chamado).
    """
    contador = proc_da_steam()
    monkeypatch.setattr(escritor_cru, "VALIDADE_DO_VEREDITO_S", 0.0)

    for tique in range(5):
        escritor_cru.pids_da_steam(agora=float(tique))

    assert contador.varreduras == 5, (
        "a régua não enxerga varredura: com a validade em zero os cinco "
        f"tiques tinham de custar cinco varreduras, e contei {contador.varreduras}"
    )


def test_a_foto_vence_a_validade_e_a_varredura_volta(proc_da_steam) -> None:
    """Cache não é congelamento: passados os 5 s, a próxima pergunta varre."""
    contador = proc_da_steam()

    escritor_cru.pids_da_steam(agora=0.0)
    escritor_cru.pids_da_steam(agora=4.999)
    assert contador.varreduras == 1
    escritor_cru.pids_da_steam(agora=5.0)
    assert contador.varreduras == 2, (
        "a foto venceu e o produto não foi olhar de novo"
    )


def test_forcar_ignora_a_foto(proc_da_steam) -> None:
    """`forcar=True` é o contrato do vigia: pergunta de verdade, sempre."""
    contador = proc_da_steam()

    escritor_cru.pids_da_steam(agora=0.0)
    escritor_cru.pids_da_steam(agora=0.5, forcar=True)
    assert contador.varreduras == 2


def test_o_caminho_da_janela_inteiro_paga_uma_varredura_so(
    proc_da_steam, monkeypatch
) -> None:
    """O caminho REAL: `controller.list` → `holders_de_hidraw` → `pids_da_steam`.

    É este que a medição de 25/08 pegou forkando a cada 3,3 s, e nenhum teste
    daqui podia afirmar a cura sem exercitá-lo de ponta a ponta.
    """
    contador = proc_da_steam()
    relogio = _RelogioFalso()
    monkeypatch.setattr(escritor_cru, "time", relogio)

    for tique in range(5):
        relogio.agora = tique * 1.0
        escritor_cru.holders_de_hidraw()

    assert contador.varreduras == 1, (
        f"o caminho da janela ainda varre por tique: {contador.varreduras}"
    )


def test_o_sentinela_forcado_joga_a_foto_fora(proc_da_steam) -> None:
    """`sondar(forcar=True)` tem de valer para o cache NOVO também.

    Sem isto, "ignora a validade" passaria a ignorar só metade dela: a chegada
    de um controle (`connection.py`, `forcar=True`) veria pids de 5 s atrás.
    """
    contador = proc_da_steam()

    escritor_cru.pids_da_steam(agora=0.0)
    assert contador.varreduras == 1

    sentinela = escritor_cru.SentinelaDeEscritorCru(sonda=lambda nos: {})
    sentinela.sondar(["/dev/hidraw0"], 0.1, forcar=True)

    assert escritor_cru._ultima_foto_de_pids is None, (
        "o `forcar=True` do sentinela deixou a foto de pids em pé — o cache "
        "novo transformou o contrato dele em mentira"
    )


def test_proc_ilegivel_degrada_e_nao_levanta(proc_da_steam) -> None:
    """O dublê recusando de outro jeito: `/proc` que não se lê."""
    contador = proc_da_steam(erro=OSError("sem /proc"))

    assert escritor_cru.pids_da_steam(agora=0.0) == []
    assert contador.varreduras == 1


def test_o_proc_ilegivel_do_escritor_cru_nao_vira_negativo_carimbado(
    proc_da_steam,
) -> None:
    """Ausência de leitura não é "a Steam não está aberta".

    O `pgrep` que estourava o `timeout` carimbava a foto assim mesmo, e cinco
    segundos de "ninguém segura o hidraw" licenciam repintura da barra por
    cima da Steam. A varredura que não terminou não carimba.

    **O NOME É LONGO DE PROPÓSITO.** A primeira versão deste teste se chamava
    `test_proc_ilegivel_nao_vira_cinco_segundos_de_negativo` — o nome EXATO de
    um teste da metade 2, sobre o outro produto. Python guarda a última
    definição, então este nunca rodou: a mordida (carimbar a foto no `except`)
    passou verde, e só apareceu porque a mordida foi conferida uma a uma. É a
    régua que não mede nada, achada dentro da régua que existe para achá-las.
    """
    contador = proc_da_steam(erro=OSError("sem /proc"))

    escritor_cru.pids_da_steam(agora=0.0)
    escritor_cru.pids_da_steam(agora=1.0)

    assert contador.varreduras == 2, (
        "um `/proc` ilegível virou negativo carimbado: o produto parou de "
        "tentar por cinco segundos com base numa leitura que nunca aconteceu"
    )


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
