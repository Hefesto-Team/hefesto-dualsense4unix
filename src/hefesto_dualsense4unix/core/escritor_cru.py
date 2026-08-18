"""ESCRITOR-CRU-01: enxergar o escritor que a classe LED não vê.

- **Medido na madrugada de 16/08/2026, e a hipótese é DELA** (*"não é pq a
  steam tá aberta?"*, levantada enquanto eu perseguia outra pista). Par de
  eliminação completo, nada mais tocado entre os dois lados:

  ===================  ==========================================
  COM a Steam aberta   a barra fica APAGADA depois de cada comando
  SEM a Steam          a barra volta ao verde sozinha
  ===================  ==========================================

O DEFEITO DE INSTRUMENTO, que é o que este módulo cura
======================================================
A casa tinha UM detector de escritor alheio — o ``verify=True`` do
:meth:`core.sysfs_leds.SysfsLedNode.set_rgb`, que re-lê ``multi_intensity`` e
compara com o que pedimos. Ele **não vê a Steam**, e a docstring daquele
arquivo já dizia por quê desde 12/08: *"escrita CRUA por hidraw que não passa
pela classe LED segue INVISÍVEL a esta re-leitura"*. A Steam escreve assim.

A medição fecha o círculo: ``lightbar_escritor_estrangeiro`` deu **ZERO em três
horas** com as barras apagadas na mesa. O detector estava ligado, funcionando, e
cego — que é pior do que não existir, porque o silêncio dele foi lido como
"ninguém está escrevendo".

POR QUE O CONTADOR É O ``fd``, E NÃO A COR
==========================================
Três caminhos foram considerados para responder *"quem escreveu preto?"* — a
pergunta que a canônica faz desde 12/08 (``dualsense-referencia-canonica.md``)
e que nunca teve ensaio:

1. **Reler a cor pelo próprio hidraw (feature report).** É o item 5.1 do estudo
   ``A-LIGHTBAR-TRAVADA``, e continua sendo a régua que falta — mas **nenhum
   dos dezessete feature reports lidos em 14-15/08 é conhecido por devolver
   estado de LED** (o ``0x22`` nunca foi lido por este projeto, o ``0xf6`` tem
   546 bytes e não é nomeado em documento nenhum). Além disso, ``GET_FEATURE``
   por Bluetooth exige retry contra o ``REPORT_REQ_TIMEOUT`` de 3 s do BlueZ.
   Isso é **ensaio de bancada**, não detector de regime;
2. **Comparar o pedido com o que o aparelho reporta.** O report de INPUT do
   DualSense não carrega a cor da barra. Não há o que comparar;
3. **Ver quem SEGURA o nó** — ``/proc/<pid>/fd``. Foi o que a madrugada
   observou (*"a Steam segurava os OITO hidraw"*), custa ~6 ms para ~4600 fds
   (medido no estudo do broker), funciona sem root para processos do mesmo
   usuário, e **não toca o aparelho**.

Este módulo é o (3). Ele responde ``quem segura``, e é honesto sobre a
diferença: **segurar não é escrever.** Um ``fd`` aberto pela Steam é estado
NORMAL — a casa já dizia isso em ``app/actions/external_controllers.py``. Por
isso o veredito daqui **nunca** licencia repintura em regime: ele licencia
UMA reafirmação no fim da sequência (``GATILHO-DA-COR-01``) e, na aba Status,
a frase honesta de que a cor mostrada é a PEDIDA.

O QUE ELE NÃO VÊ, dito antes que alguém descubra do jeito caro
==============================================================
- **Só reconhece a Steam.** A varredura é restrita aos PIDs dela (os mesmos
  padrões do ``steam_running`` canônico). Um segundo escritor cru — um jogo
  fora do Steam, outro daemon de controle — passa despercebido. Varrer
  ``/proc/*/fd`` inteiro seria caro e indiscreto, e a Steam é o escritor que
  a mesa dela mediu;
- **Não sabe QUANDO ela escreveu**, só que ela pode. Daí a rate-limit não vir
  daqui: quem decide a frequência é o gatilho;
- **Degrada em silêncio.** Sem ``pgrep``, sem permissão, orçamento estourado —
  devolve o que juntou. Ausência de veredito é "não sondado", **nunca**
  "ninguém segura".
"""
from __future__ import annotations

import contextlib
import os
import subprocess
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Orçamentos da sonda. O ``pgrep`` tem timeout curto e a varredura de
#: ``/proc/<pid>/fd`` tem teto de tempo — o estudo do broker mediu ~6 ms para
#: ~4600 fds, então 0,5 s é folga patológica. Nunca roda no event loop.
PGREP_TIMEOUT_S: float = 1.0
ORCAMENTO_DA_VARREDURA_S: float = 0.5
MAX_PIDS_DA_STEAM: int = 8

#: Quanto um veredito vale antes de a sonda poder rodar de novo. Existe para
#: que uma rajada de escritas nossas (arrastar o seletor de cor da GUI) não
#: vire uma rajada de ``pgrep``: a rajada inteira lê o MESMO veredito.
VALIDADE_DO_VEREDITO_S: float = 5.0


def pids_da_steam() -> list[int]:
    """PIDs do processo Steam via ``pgrep`` — padrões do ``steam_running``.

    Mesmos matches de ``integrations/steam_launch_options.steam_running``
    (``-f steamrt64/steam`` pega o runtime pelo PATH; nunca ``-f steam``
    solto — o falso-positivo histórico do earlyoom), mais ``-x steam`` para
    instalações fora do runtime. Best-effort: qualquer falha devolve o que
    juntou.
    """
    pids: set[int] = set()
    for args in (["pgrep", "-f", "steamrt64/steam"], ["pgrep", "-x", "steam"]):
        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                timeout=PGREP_TIMEOUT_S,
                check=False,
                text=True,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if proc.returncode != 0:
            continue
        for token in proc.stdout.split():
            with contextlib.suppress(ValueError):
                pids.add(int(token))
    return sorted(pids)[:MAX_PIDS_DA_STEAM]


def holders_de_hidraw(
    nos: Iterable[str] | None = None,
) -> dict[str, list[int]]:
    """Mapa ``/dev/hidrawN`` -> PIDs do Steam que seguram o nó.

    Sonda OPCIONAL e degradável, restrita aos PIDs do Steam (nunca
    ``/proc/*/fd`` de todos os processos) — funciona sem sudo para processos
    do mesmo usuário. Estourou o orçamento/permissão, devolve o que tem; quem
    consome trata ausência como "não sondado", NUNCA como "ninguém segura".

    ``nos`` filtra o resultado aos nós que interessam (os DualSense da mesa);
    ``None`` devolve todos os hidraw que a Steam segura — é a forma que o
    inventário de externos (8BIT-01) usa.
    """
    interesse = {str(n) for n in nos} if nos is not None else None
    holders: dict[str, list[int]] = {}
    deadline = time.monotonic() + ORCAMENTO_DA_VARREDURA_S
    for pid in pids_da_steam():
        fd_dir = f"/proc/{pid}/fd"
        try:
            entries = os.listdir(fd_dir)
        except OSError:
            continue  # processo morreu / sem permissão: segue degradado
        for fd in entries:
            if time.monotonic() > deadline:
                return holders
            target = ""
            with contextlib.suppress(OSError):
                target = os.readlink(os.path.join(fd_dir, fd))
            if not target.startswith("/dev/hidraw"):
                continue
            if interesse is not None and target not in interesse:
                continue
            pids_do_no = holders.setdefault(target, [])
            if pid not in pids_do_no:
                pids_do_no.append(pid)
    return holders


@dataclass(frozen=True)
class Veredito:
    """O que a última sonda viu. Imutável de propósito: é uma FOTO, não estado.

    ``sondado_em`` a ``None`` é o terceiro estado que esta casa aprendeu a
    respeitar: **não sondado** não é "limpo". Quem lê tem de saber a diferença,
    porque rotular "ninguém segura" sem ter olhado é exatamente o erro que a
    leitura de ``multi_intensity`` cometia.
    """

    sondado_em: float | None = None
    por_no: Mapping[str, tuple[int, ...]] = field(default_factory=dict)

    @property
    def sondado(self) -> bool:
        """True se ALGUMA sonda já rodou (o veredito significa alguma coisa)."""
        return self.sondado_em is not None

    def segurado(self, no: str | None) -> bool:
        """True se ESTE nó hidraw tem um escritor cru em potencial."""
        return bool(no) and bool(self.por_no.get(str(no)))

    def pids(self, no: str | None) -> tuple[int, ...]:
        """PIDs que seguram este nó (vazio = nenhum, ou não sondado)."""
        return tuple(self.por_no.get(str(no), ())) if no else ()

    @property
    def nos_segurados(self) -> tuple[str, ...]:
        """Os nós com escritor cru em potencial, ordenados."""
        return tuple(sorted(n for n, pids in self.por_no.items() if pids))

    @property
    def algum(self) -> bool:
        """True se ao menos um nó da mesa está segurado."""
        return bool(self.nos_segurados)


#: A sonda, em forma de tipo — é o que torna o sentinela exercitável sem
#: ``/proc``, sem Steam e sem hardware.
Sonda = Callable[[Iterable[str] | None], Mapping[str, list[int]]]


class SentinelaDeEscritorCru:
    """Guarda o último veredito e diz **quando um nó GANHOU** um escritor cru.

    Duas responsabilidades, e nenhuma delas é escrever no aparelho:

    - **cachear** — a sonda faz ``pgrep`` + ``readlink``; sem cache, cada
      escrita de cor da GUI pagaria um subprocesso. ``VALIDADE_DO_VEREDITO_S``
      é o teto: dentro dela, ``sondar`` devolve a foto que já tem;
    - **achar a BORDA** — o que interessa não é "a Steam está aberta" (estado
      normal, o dia inteiro), é *"este nó, que estava livre, acabou de ser
      segurado"*. É a borda que corresponde à rajada de repintura medida em
      12/08, e é ela que licencia UMA reafirmação.

    Não lê relógio: recebe ``agora`` de fora, como o
    ``GatilhoDeFimDeSequencia``. É o que permite exercitar cinco segundos de
    validade em microssegundos de teste.
    """

    def __init__(
        self,
        *,
        sonda: Sonda | None = None,
        validade_s: float = VALIDADE_DO_VEREDITO_S,
    ) -> None:
        self._sonda: Sonda = sonda if sonda is not None else holders_de_hidraw
        self._validade_s = float(validade_s)
        self._veredito = Veredito()
        #: A PRIMEIRA sonda não tem foto anterior contra a qual haver borda.
        self._ja_sondou = False

    @property
    def veredito(self) -> Veredito:
        """A última foto, sem tocar em ``/proc``. É o que a aba Status lê."""
        return self._veredito

    def fresco(self, agora: float) -> bool:
        """True se o veredito ainda vale (uma sonda nova seria desperdício)."""
        em = self._veredito.sondado_em
        return em is not None and (float(agora) - em) < self._validade_s

    def sondar(
        self, nos: Iterable[str], agora: float, *, forcar: bool = False
    ) -> tuple[Veredito, tuple[str, ...]]:
        """Sonda (respeitando a validade) e devolve ``(veredito, nós NOVOS)``.

        ``nós NOVOS`` são os que **ganharam** um escritor cru desde a foto
        anterior — a borda. Um nó que já estava segurado na foto passada não
        volta na lista: a Steam aberta o dia inteiro arma o gatilho UMA vez,
        não o dia inteiro.

        ``forcar`` ignora a validade (o tique de 30 s do ``reconnect_loop``,
        que é quem tem orçamento para o ``pgrep``). Sem ele, uma sonda dentro
        da validade é no-op e devolve a foto que já existe, com borda vazia —
        e isso é resposta, não falha.

        Falha da sonda **preserva a foto anterior**: um ``pgrep`` que morreu
        não é prova de que a Steam fechou, e apagar o veredito por causa dele
        faria a aba Status mentir para o outro lado.
        """
        alvos = [str(n) for n in nos if n]
        if not alvos:
            return self._veredito, ()
        if not forcar and self.fresco(agora):
            return self._veredito, ()
        try:
            bruto = self._sonda(alvos)
        except Exception as exc:  # sonda é best-effort por contrato
            logger.debug("escritor_cru_sonda_falhou", err=str(exc))
            return self._veredito, ()
        por_no = {
            str(no): tuple(int(p) for p in pids)
            for no, pids in dict(bruto).items()
            if pids
        }
        antes = set(self._veredito.nos_segurados)
        primeira = not self._ja_sondou
        novo = Veredito(sondado_em=float(agora), por_no=por_no)
        self._veredito = novo
        self._ja_sondou = True
        # A borda só existe contra uma foto anterior. Na PRIMEIRA sonda tudo
        # seria "novo", e o daemon repintaria no boot por nada — o priming do
        # `_refresh_sysfs_leds` já cuidou daquele instante.
        if primeira:
            return novo, ()
        return novo, tuple(n for n in novo.nos_segurados if n not in antes)


__all__ = [
    "MAX_PIDS_DA_STEAM",
    "ORCAMENTO_DA_VARREDURA_S",
    "PGREP_TIMEOUT_S",
    "VALIDADE_DO_VEREDITO_S",
    "SentinelaDeEscritorCru",
    "Sonda",
    "Veredito",
    "holders_de_hidraw",
    "pids_da_steam",
]
