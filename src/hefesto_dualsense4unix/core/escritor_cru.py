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

**NOTA DATADA — 23/09/2026, e a regra acima mudou por decisão dela.** *"Hefesto
manda e controla sempre, steam sequestrou hefesto corrigiu ao no segundo após"*
(STEAM-NO-FISICO-01). O SENTINELA continua licenciando uma reafirmação só; a
:class:`VigiaDoSequestro`, no fim deste módulo, licencia a reescrita da barra e
do número a cada segundo ENQUANTO um processo alheio segurar o nó — e só a barra
e o número, nunca vibração, gatilho ou áudio (o que zerou motor alheio no
RUMBLE-SEM-DONO-01 era um report que levava os motores).

O QUE ELE NÃO VÊ, dito antes que alguém descubra do jeito caro
==============================================================
- **Só reconhece a Steam.** A varredura é restrita aos PIDs dela (os mesmos
  padrões do ``steam_running`` canônico). Um segundo escritor cru — um jogo
  fora do Steam, outro daemon de controle — passa despercebido. Varrer
  ``/proc/*/fd`` inteiro seria caro e indiscreto, e a Steam é o escritor que
  a mesa dela mediu;
- **Não sabe QUANDO ela escreveu**, só que ela pode. Daí a rate-limit não vir
  daqui: quem decide a frequência é o gatilho;
- **Degrada em silêncio.** Sem ``/proc``, sem permissão, orçamento estourado —
  devolve o que juntou. Ausência de veredito é "não sondado", **nunca**
  "ninguém segura".
"""
from __future__ import annotations

import contextlib
import os
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field

from hefesto_dualsense4unix.integrations.steam_launch_options import cmdline_de_pid
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Orçamentos da sonda. A varredura de ``/proc`` que acha os PIDs da Steam e a
#: varredura de ``/proc/<pid>/fd`` têm, cada uma, teto de tempo — o estudo do
#: broker mediu ~6 ms para ~4600 fds, então 0,5 s é folga patológica. Nunca
#: rodam no event loop.
ORCAMENTO_DA_VARREDURA_DE_PIDS_S: float = 1.0
ORCAMENTO_DA_VARREDURA_S: float = 0.5
MAX_PIDS_DA_STEAM: int = 8

#: **NOME VELHO, e ele mente desde 06/09/2026: não há mais ``pgrep`` aqui.**
#: DAEMON-ACORDADO-01/E2 trocou o par de ``pgrep`` de :func:`pids_da_steam` por
#: uma varredura nativa de ``/proc``, e o número (1,0 s) sobreviveu inteiro —
#: virou o teto da varredura. O alias fica porque
#: ``daemon/ipc_handlers.py:664`` (``_HOLDERS_PGREP_TIMEOUT_SEC``) o importa, e
#: aquele arquivo **não é posse desta sprint**: R1 desta casa manda RELATAR em
#: vez de editar arquivo alheio. Quem tiver o ``ipc_handlers`` na posse aposenta
#: os dois nomes de uma vez — está escrito na entrega desta sprint.
PGREP_TIMEOUT_S: float = ORCAMENTO_DA_VARREDURA_DE_PIDS_S

#: Agulha do ``pgrep -f steamrt64/steam`` que a varredura substituiu: casa o
#: runtime da Steam pelo PATH. **Nunca ``steam`` solto** — é o falso-positivo
#: histórico do earlyoom, e a razão de o ``steam_running`` canônico nunca ter
#: usado ``-f steam``.
_AGULHA_DA_STEAM_NA_CMDLINE = "steamrt64/steam"

#: Nome EXATO de processo do ``pgrep -x steam``, para instalações fora do
#: runtime. ``-x`` compara com o ``comm`` do processo, não com a cmdline — daí
#: a varredura ler ``/proc/<pid>/comm``, e não deduzir o nome do ``argv[0]``:
#: ``comm`` é definível por ``prctl`` e truncado em 15 bytes, então deduzir
#: seria uma regra DIFERENTE com cara de igual.
_COMM_EXATO_DA_STEAM = "steam"

#: Quanto um veredito vale antes de a sonda poder rodar de novo. Existe para
#: que uma rajada de escritas nossas (arrastar o seletor de cor da GUI) não
#: vire uma rajada de varreduras: a rajada inteira lê o MESMO veredito.
#:
#: **DAEMON-ACORDADO-01/BG-03 (25/08/2026): agora ela cobre também a
#: VARREDURA, e não só o veredito.** O número existia desde a ESCRITOR-CRU-01
#: com este comentário, e mesmo assim o ``pgrep`` continuava forkando a cada
#: chamada — porque a validade morava no :class:`SentinelaDeEscritorCru` e o
#: caminho da JANELA (``controller.list`` → ``ipc_handlers._steam_hidraw_holders``
#: → :func:`holders_de_hidraw` → :func:`pids_da_steam`) **não passa pelo
#: sentinela**. Era a cura escrita e nunca ligada.
VALIDADE_DO_VEREDITO_S: float = 5.0

#: A última lista de PIDs e QUANDO ela foi colhida — ``None`` = nunca.
#: Escrita numa tupla só de propósito: a atribuição é atômica sob a GIL, e a
#: sonda roda em thread (``asyncio.to_thread`` do inventário) enquanto o vigia
#: da lightbar pode ler. Duas gravações concorrentes custam uma varredura a
#: mais, nunca uma foto meio velha e meio nova.
_ultima_foto_de_pids: tuple[float, tuple[int, ...]] | None = None


def invalidar_pids_da_steam() -> None:
    """Joga fora a foto de PIDs: a próxima chamada varre `/proc` de verdade.

    Existe para o ``forcar=True`` de :meth:`SentinelaDeEscritorCru.sondar`
    continuar valendo o que a docstring dele promete — sem isto, um cache
    novo por baixo transformaria "ignora a validade" em mentira.
    """
    global _ultima_foto_de_pids
    _ultima_foto_de_pids = None


def processo_vivo(pid: int) -> bool:
    """Ainda existe processo com este PID?

    ESCRITOR-CRU-03 (19/09/2026) — é o que separa a foto do presente, e é
    barato de propósito: UM `stat` em ``/proc/<pid>``, sem `pgrep`, sem
    subprocesso e sem varrer diretório. É o que torna pagável conferir a foto
    no tique de 1 s da GUI, que é onde `_lightbar_disputada` é lido.

    Não conseguir olhar devolve ``True``: falha de leitura não é prova de
    morte, e a disciplina desta casa é não mudar a resposta por falta de dado.
    """
    try:
        return os.path.exists(f"/proc/{int(pid)}")
    except Exception:  # pragma: no cover - `int()` de lixo, `/proc` ausente
        return True


def _comm_de_pid(pid: str | int) -> str:
    """``comm`` de um pid — o nome de processo que o ``pgrep -x`` compara.

    Nunca levanta, pela mesma razão de :func:`cmdline_de_pid`: pid que morreu
    entre o ``listdir`` e o ``open`` é o caso comum, não a exceção.
    """
    try:
        with open(f"/proc/{pid}/comm", "rb") as fh:
            return fh.read().decode("utf-8", "replace").strip()
    except OSError:
        return ""


def pids_da_steam(*, agora: float | None = None, forcar: bool = False) -> list[int]:
    """PIDs do processo Steam por varredura de ``/proc`` — sem forkar nada.

    Mesmos matches de ``integrations/steam_launch_options.steam_running``, e o
    contrato é **idêntico** ao do par de ``pgrep`` que estava aqui até
    06/09/2026: ``steamrt64/steam`` na cmdline (o runtime pelo PATH; nunca
    ``steam`` solto — o falso-positivo histórico do earlyoom) e ``comm``
    exatamente ``steam`` (instalações fora do runtime). Best-effort: qualquer
    falha devolve o que juntou.

    A LEITURA DA CMDLINE É A DA PERF-PROC-SCAN-01
    =============================================
    DAEMON-ACORDADO-01/E2 (06/09/2026). A PERF-PROC-SCAN-01 já tinha trocado um
    ``pgrep -f`` por varredura nativa em ``integrations/steam_launch_options``
    (12/08/2026), medindo este mesmo defeito e escrevendo esta mesma conta —
    **e esta função era a cópia que ficou de fora daquela troca.** Por isso ela
    não ganha varredura própria: importa :func:`cmdline_de_pid` de lá. Duas
    varreduras de ``/proc`` no mesmo daemon seriam duas verdades sobre o mesmo
    ``/proc``, que é a família de defeito que a casa acabou de pagar.

    O QUE O FORK CUSTAVA, medido em 25/08/2026 na máquina dela
    ==========================================================
    Janela do Hefesto ABERTA e um DualSense no cabo: o par de ``pgrep`` daqui
    saía a cada 3,3 s (o ritmo do ``controller.list``), e **um** ``pgrep``
    custa 2.533 ``read()`` e 724 KB de ``rchar`` nesta máquina — 61 % das
    leituras e 84 % dos bytes do daemon não eram do controle. O ``pgrep`` lê
    CINCO arquivos por processo (``status``, ``stat``, ``cmdline``, ``cgroup``,
    ``ctty``) e paga ``fork`` + ``execve``, com o ``PATH`` errando cinco vezes
    antes de achar o binário.

    A varredura lê **no máximo DOIS** arquivos por pid (``comm``, e ``cmdline``
    só quando o ``comm`` não resolveu), sem ``fork`` e sem ``execve``. O
    ``comm`` vem primeiro porque é o que pode dispensar o segundo ``open``.

    **O NÚMERO É MEDIDO, e ele NÃO é "custo zero".** Nesta máquina, 430
    processos vivos, as duas formas rodadas cinco vezes cada e contadas pelo
    delta de ``syscr`` de ``/proc/self/io`` — a régua do "buraco" que a
    DAEMON-ACORDADO-01 inventou porque ``ptrace_scope=1`` proíbe ``strace``, e
    que serve aqui porque ``/proc/<pid>/io`` **soma o que o filho colhido
    gastou**, que é justamente o custo do ``pgrep``:

      ==================  ================  ==============
      forma               ``read()``/chamada  tempo/chamada
      ==================  ================  ==============
      varredura nativa            1.465          3,8 ms
      par de ``pgrep``            3.859         20,8 ms
      ==================  ================  ==============

    **2,6x menos ``read()`` e 5,5x menos tempo de parede**, mais os dois
    ``fork``/``execve`` que deixam de existir. Uma versão anterior desta
    docstring anunciava "~5x menos", por analogia com a PERF-PROC-SCAN-01 e
    sem medir: nos ``read()`` são 2,6x, e o 5x só aparece no relógio. Quem
    quiser o custo em zero depende do cache abaixo, não desta varredura.

    **A equivalência também é medida**, e com uma agulha que ACHA processos —
    uma régua que só sabe devolver lista vazia (a Steam fechada) não mede nada.
    Três agulhas, cada uma comparada contra o ``pgrep`` de verdade: a da Steam,
    ``/usr/lib/systemd``/``systemd`` (7 pids) e ``zsh``/``zsh`` (6 pids). Os
    três conjuntos saíram IGUAIS, inclusive sobre a isca — o processo que casa
    porque a agulha está na cmdline DELE, que o ``_STEAM_LAUNCH_RE`` já
    documenta como risco residual e que as duas formas enxergam igual.

    O CACHE, e o que ele paga
    =========================
    **O resultado vale ``VALIDADE_DO_VEREDITO_S`` (BG-03, 25/08/2026).**
    ``agora`` é injetável pelo mesmo motivo do ``GatilhoDeFimDeSequencia``:
    exercitar cinco segundos de validade em microssegundos de teste.
    ``forcar`` ignora a foto.

    **O preço, dito antes que alguém descubra do jeito caro:** a lista de PIDs
    pode estar até ``VALIDADE_DO_VEREDITO_S`` atrasada. A Steam que ABRIU há
    três segundos ainda não aparece, e quem lê isso responde "não vi ninguém
    segurando". É o mesmo atraso que o veredito do sentinela já tinha; a
    varredura de ``/proc/<pid>/fd`` continua fresca a cada chamada — só a lista
    de pids é que envelhece.

    **A VARREDURA QUE NÃO TERMINOU NÃO CARIMBA A FOTO**, e isto é uma correção
    de comportamento, não um efeito colateral: o ``pgrep`` que estourava o
    ``timeout`` carimbava mesmo assim, transformando uma leitura que não
    aconteceu em cinco segundos de "a Steam não está aberta". É a mentira que
    a casa proíbe (ausência ≠ negativo) e que o ``_steam_launch_cmdline`` já
    recusava na camada 4. O preço da correção: numa máquina onde varrer
    ``/proc`` passe de ``ORCAMENTO_DA_VARREDURA_DE_PIDS_S``, cada chamada paga
    o orçamento inteiro. O teto é 1,0 s contra os 4,2 ms que a varredura de
    ``/proc`` mediu — ~200x de folga —, então chegar lá já é patológico.
    """
    global _ultima_foto_de_pids
    agora = time.monotonic() if agora is None else float(agora)
    if not forcar:
        foto = _ultima_foto_de_pids
        if foto is not None and (agora - foto[0]) < VALIDADE_DO_VEREDITO_S:
            return list(foto[1])
    try:
        entradas = os.listdir("/proc")
    except OSError:
        # Sem `/proc` não houve varredura: NÃO carimba a foto (ver docstring).
        return []
    deadline = time.monotonic() + ORCAMENTO_DA_VARREDURA_DE_PIDS_S
    pids: set[int] = set()
    for entrada in entradas:
        if not entrada.isdigit():
            continue
        if time.monotonic() > deadline:
            # Varredura truncada: devolve o que juntou e não carimba.
            return sorted(pids)[:MAX_PIDS_DA_STEAM]
        if _comm_de_pid(entrada) == _COMM_EXATO_DA_STEAM:
            with contextlib.suppress(ValueError):
                pids.add(int(entrada))
            continue
        if _AGULHA_DA_STEAM_NA_CMDLINE in cmdline_de_pid(entrada):
            with contextlib.suppress(ValueError):
                pids.add(int(entrada))
    achados = sorted(pids)[:MAX_PIDS_DA_STEAM]
    _ultima_foto_de_pids = (agora, tuple(achados))
    return achados


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

    O relógio é lido **uma vez** e serve às duas contas — o orçamento da
    varredura e a validade da foto de PIDs. É o que faz o caminho da janela
    inteiro (``controller.list`` → aqui → :func:`pids_da_steam`) obedecer a um
    relógio só, inclusive o falso dos testes.
    """
    interesse = {str(n) for n in nos} if nos is not None else None
    holders: dict[str, list[int]] = {}
    agora = time.monotonic()
    deadline = agora + ORCAMENTO_DA_VARREDURA_S
    for pid in pids_da_steam(agora=agora):
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


#: ESCRITOR-CRU-02 (16/09/2026) — o teto da varredura AMPLA.
#:
#: O número é medido nesta máquina, não estimado: três voltas sobre **122
#: processos legíveis e 4.139 fds** deram 12,8 · 10,8 · 9,5 ms. O teto de 0,5 s
#: é a mesma folga patológica do irmão restrito, e pelo mesmo motivo — o que
#: importa é nunca travar, não ser rápido.
ORCAMENTO_DA_VARREDURA_AMPLA_S: float = 0.5


def holders_de_hidraw_de_qualquer_um(
    nos: Iterable[str] | None = None,
) -> dict[str, list[int]]:
    """Mapa ``/dev/hidrawN`` -> PIDs de QUALQUER processo que segure o nó.

    ESCRITOR-CRU-02, 16/09/2026 — e ele existe por uma ORDEM DELA:

        *"O app deveria construir tudo independente de qual jogo ou launcher.
        (…) é um app que será focado pra acessibilidade. Isso não pode se
        repetir."*

    **O PONTO CEGO, e este módulo o declarava desde que nasceu:** *"Só reconhece
    a Steam. (…) Um segundo escritor cru — um jogo fora do Steam, outro daemon
    de controle — passa despercebido. Varrer ``/proc/*/fd`` inteiro seria caro e
    indiscreto, e a Steam é o escritor que a mesa dela mediu."*

    As três razões foram medidas em 16/09/2026, e **duas caíram**:

    1. **"seria caro" — FALSO nesta máquina.** Varrer TODOS os processos custa
       9,5 a 12,8 ms (122 legíveis, 4.139 fds), contra os ~6 ms do irmão
       restrito. A diferença é de milissegundos, e a sonda já é rate-limitada
       por :data:`VALIDADE_DO_VEREDITO_S` e nunca roda no event loop.
    2. **"a Steam é o escritor que a mesa dela mediu" — VERDADEIRO E
       INSUFICIENTE.** A mesa dela é uma; o produto é de outras pessoas. Quem
       joga por Lutris, Heroic, Flatpak ou execução direta tem um escritor cru
       que este módulo não enxergava — e "não enxergo" saía como "ninguém
       segura", que é o erro que a leitura de ``multi_intensity`` já cometia.
    3. **"indiscreto" — DE PÉ, e por isso a disciplina:** lemos o alvo do
       symlink e **descartamos na hora** tudo que não começa com
       ``/dev/hidraw``. Nenhum outro caminho é guardado, logado ou devolvido.
       O que sai daqui é só *"o PID N segura o hidraw M"*.

    **O QUE ELE CONTINUA NÃO VENDO**, dito aqui antes que custe caro: segurar
    não é escrever (a mesma honestidade do irmão), e processo de OUTRO usuário
    fica fora — ``/proc/<pid>/fd`` alheio precisa de root, e subir privilégio
    para pintar uma barra não é troca que esta casa faça.

    Degrada igual ao irmão: sem ``/proc``, sem permissão ou orçamento estourado,
    devolve o que juntou. Ausência é "não sondado", **nunca** "ninguém segura".
    """
    interesse = {str(n) for n in nos} if nos is not None else None
    holders: dict[str, list[int]] = {}
    deadline = time.monotonic() + ORCAMENTO_DA_VARREDURA_AMPLA_S
    try:
        pids = os.listdir("/proc")
    except OSError:
        return holders
    for entrada in pids:
        if not entrada.isdigit():
            continue
        fd_dir = f"/proc/{entrada}/fd"
        try:
            entries = os.listdir(fd_dir)
        except OSError:
            continue  # morreu, ou é de outro usuário: segue degradado
        for fd in entries:
            if time.monotonic() > deadline:
                return holders
            target = ""
            with contextlib.suppress(OSError):
                target = os.readlink(os.path.join(fd_dir, fd))
            # O DESCARTE É AQUI, e é o que mantém a sonda discreta: tudo que
            # não é hidraw morre nesta linha, sem ser guardado nem logado.
            if not target.startswith("/dev/hidraw"):
                continue
            if interesse is not None and target not in interesse:
                continue
            pids_do_no = holders.setdefault(target, [])
            pid = int(entrada)
            if pid not in pids_do_no:
                pids_do_no.append(pid)
    return holders


def escritores_crus_alheios(
    nos: Iterable[str] | None = None,
    *,
    meu_pid: int | None = None,
) -> dict[str, list[int]]:
    """Os nós de :func:`holders_de_hidraw_de_qualquer_um` TIRANDO nós mesmos.

    É a forma que um gatilho de defesa quer: *"além de mim, quem mais segura o
    hidraw deste controle?"*. O daemon segura o próprio nó — e vê-lo na lista
    faria toda sonda acusar escritor alheio a cada volta.

    O filtro é por PID, e inclui o processo ATUAL e o pai: o daemon abre o
    hidraw em mais de um fd (medido: quatro no mesmo PID), e o broker roda em
    processo próprio. Nada aqui supõe quantos — só que o nosso não conta.
    """
    eu = os.getpid() if meu_pid is None else int(meu_pid)
    try:
        pai = os.getppid()
    except OSError:  # pragma: no cover - não acontece em Linux
        pai = -1
    nossos = {eu, pai}
    bruto = holders_de_hidraw_de_qualquer_um(nos)
    return {
        no: alheios
        for no, pids in bruto.items()
        if (alheios := [p for p in pids if p not in nossos])
    }


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

    # --- a foto conferida contra o presente (ESCRITOR-CRU-03) -------------

    def pids_vivos(
        self, no: str | None, *, vivo: Callable[[int], bool] | None = None
    ) -> tuple[int, ...]:
        """Dos PIDs que a foto guarda para este nó, os que AINDA EXISTEM."""
        olhar = processo_vivo if vivo is None else vivo
        return tuple(p for p in self.pids(no) if olhar(p))

    def segurado_de_fato(
        self, no: str | None, *, vivo: Callable[[int], bool] | None = None
    ) -> bool:
        """True se alguém **que ainda existe** segura este nó.

        ESCRITOR-CRU-03 (19/09/2026) — a diferença entre LEMBRAR e MEDIR.

        `segurado` acima responde sobre a FOTO, e a foto é tirada no tique de
        30 s do `reconnect_loop`. Entre dois tiques ela é a única coisa que a
        aba Status tem — e ela conta o passado no presente. Medido em 19/09: a
        Steam levou SIGTERM, `pgrep` devolveu zero, e sete segundos depois o
        `daemon.state_full` ainda publicava ``lightbar_disputada: True``. O
        aviso na tela dela nomeia um processo que não existe mais.

        E há um caminho em que a foto **nunca** é corrigida: o
        `vigiar_escritor_cru` é no-op TOTAL em Modo Nativo (nem sonda) e
        desiste quando nenhum nó está mapeado. Nesses estados ninguém zera o
        que a última foto disse — ela vale para sempre.

        A cura não é sondar mais: um `pgrep` por segundo é justamente o preço
        que o `_lightbar_disputada` se recusa a pagar. É conferir o que a foto
        já guarda — **os PIDs**. Um `os.path.exists('/proc/<pid>')` por PID
        lembrado custa um `stat`, e a foto tem um punhado deles.

        **Só pode ir de True para False, nunca o contrário**: um nó que a sonda
        viu livre continua livre, e nenhum aviso novo nasce daqui.

        Ressalva honesta, porque a régua não pode prometer o que não entrega:
        um PID reciclado por outro processo lê-se como vivo, e um processo vivo
        que já fechou o `fd` também. Nos dois casos a resposta é a de hoje — o
        erro fica do lado seguro, que é o de não mudar nada — e o tique de 30 s
        corrige. O que some é a mentira barata: o processo MORTO.
        """
        return bool(self.pids_vivos(no, vivo=vivo))

    def nos_segurados_de_fato(
        self, *, vivo: Callable[[int], bool] | None = None
    ) -> tuple[str, ...]:
        """Os nós segurados por quem ainda existe — o `nos_segurados` medido."""
        return tuple(
            sorted(n for n in self.por_no if self.segurado_de_fato(n, vivo=vivo))
        )


#: A sonda, em forma de tipo — é o que torna o sentinela exercitável sem
#: ``/proc``, sem Steam e sem hardware.
Sonda = Callable[[Iterable[str] | None], Mapping[str, list[int]]]


class SentinelaDeEscritorCru:
    """Guarda o último veredito e diz **quando um nó GANHOU** um escritor cru.

    Duas responsabilidades, e nenhuma delas é escrever no aparelho:

    - **cachear** — a sonda varre ``/proc`` + ``readlink``; sem cache, cada
      escrita de cor da GUI pagaria a varredura. ``VALIDADE_DO_VEREDITO_S``
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
        #: **ESCRITOR-CRU-02 (16/09/2026): o default deixou de ser só a Steam.**
        #:
        #: Era :func:`holders_de_hidraw`, que varre apenas os PIDs do cliente
        #: Steam. Quem joga por Lutris, Heroic, Flatpak ou execução direta tinha
        #: um escritor cru INVISÍVEL a esta sentinela — e invisível saía como
        #: "ninguém segura", que é o verde sobre nada. Ordem dela de 16/09: o
        #: app independe do lançador.
        #:
        #: É :func:`escritores_crus_alheios`, e não a varredura ampla nua, por
        #: uma razão que a régua trava: **o daemon segura o próprio hidraw**
        #: (medido: quatro fds no mesmo PID). A varredura nua nos devolveria a
        #: nós mesmos, a borda dispararia na primeira volta e a sentinela
        #: passaria a acusar escritor alheio para sempre.
        #:
        #: O caminho da JANELA (`ipc_handlers._steam_hidraw_holders`) segue com
        #: a sonda restrita DE PROPÓSITO: ali a frase da aba Status nomeia a
        #: Steam, e trocar a sonda trocaria o texto sem ninguém pedir.
        self._sonda: Sonda = (
            sonda if sonda is not None else escritores_crus_alheios
        )
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
        que é quem tem orçamento para a varredura). Sem ele, uma sonda dentro
        da validade é no-op e devolve a foto que já existe, com borda vazia —
        e isso é resposta, não falha.

        **BG-03 (25/08/2026): ``forcar`` também joga fora a foto de PIDs.** O
        cache novo de :func:`pids_da_steam` fica DEBAIXO desta classe, e sem
        esta linha "ignora a validade" passaria a ignorar só metade dela — o
        ``forcar=True`` da chegada de um controle (``connection.py``) veria
        pids de até cinco segundos atrás.

        Falha da sonda **preserva a foto anterior**: uma varredura que morreu
        não é prova de que a Steam fechou, e apagar o veredito por causa dele
        faria a aba Status mentir para o outro lado.
        """
        alvos = [str(n) for n in nos if n]
        if not alvos:
            return self._veredito, ()
        if not forcar and self.fresco(agora):
            return self._veredito, ()
        if forcar:
            invalidar_pids_da_steam()
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


# ---------------------------------------------------------------------------
# STEAM-NO-FISICO-01 — a vigia do sequestro: corrigir em até um segundo
# ---------------------------------------------------------------------------

#: A fatia do laço de reconexão enquanto a vigia está de guarda. É o que torna
#: «em até um segundo» uma conta que fecha: reafirmação a cada
#: `INTERVALO_DA_REAFIRMACAO_S`, avaliada a cada meia fatia.
PASSO_DA_VIGIA_S: float = 0.5

#: De quanto em quanto a barra e o número são reescritos num nó sequestrado.
#: 0,9 s com a fatia de 0,5 s dá uma reescrita a cada segundo cravado — o teto
#: que ela deu (*"corrigiu ao no segundo após"*) — e não duas: meio segundo
#: pagaria o dobro de reports sem que o olho dela visse diferença.
INTERVALO_DA_REAFIRMACAO_S: float = 0.9

#: A sonda de `/proc` (≈11 ms nesta máquina, medido em 23/09/2026: 453 pids,
#: 146 legíveis, 4.385 fds) roda a cada fatia só enquanto há nó ABERTO sem
#: sequestrador conhecido — é o único estado em que um processo novo pode
#: chegar sem aviso, e a borda dele tem de ser vista em meio segundo.
INTERVALO_DA_SONDA_S: float = 0.5

#: Com o sequestro já visto, a sonda só precisa dizer quando ele acabou; a
#: reescrita continua a cada segundo, e reafirmar um nó que já foi solto é
#: inofensivo (é a cor do próprio Hefesto). Dois segundos cortam três quartos
#: da varredura numa sessão longa de Modo Nativo, que é onde o jogo segura o nó
#: o tempo inteiro.
INTERVALO_DA_SONDA_COM_SEQUESTRO_S: float = 2.0


def no_alcancavel(no: str) -> bool:
    """Um processo DESTE usuário consegue abrir este nó agora?

    É a pergunta que decide se vale varrer `/proc`: com a regra udev da cura
    (O-NO-NASCE-FECHADO-01) o nó do físico é `0600 root`, e nenhum processo da
    sessão consegue abri-lo — logo ninguém NOVO pode sequestrá-lo, e a sonda
    seria gasto sem pergunta. Ele fica alcançável no Modo Nativo (o broker
    expõe de propósito), numa máquina sem a cura, ou na janela de milissegundos
    em que o `_open_one` expõe o nó para o `hidapi`.

    `os.access` respeita a ACL (é o `access(2)` do kernel), custa ~0,4 µs
    (medido em 23/09/2026) e não abre nada. Falha de leitura devolve ``True``:
    na dúvida, a vigia olha.
    """
    try:
        return os.access(no, os.R_OK | os.W_OK)
    except Exception:  # pragma: no cover - caminho malformado
        return True


@dataclass(frozen=True)
class PassoDaVigia:
    """O que um passo da vigia viu — uma FOTO, como o `Veredito`."""

    sondou: bool = False
    novos: tuple[str, ...] = ()
    soltos: tuple[str, ...] = ()
    a_reafirmar: tuple[str, ...] = ()
    pids: Mapping[str, tuple[int, ...]] = field(default_factory=dict)


class VigiaDoSequestro:
    """Diz, a cada fatia, QUAIS nós do físico reescrever — e só isso.

    STEAM-NO-FISICO-01, a segunda obrigação da decisão dela de 23/09/2026:

        *"steam sequestrou hefesto corrigiu ao no segundo após"* — e,
        na sprint: *"o Hefesto reescreve a barra e o número em até 1 s,
        quantas vezes for preciso"*.

    **POR QUE NÃO É O `SentinelaDeEscritorCru`.** O sentinela licencia UMA
    reafirmação no fim da sequência, e a foto dele é a verdade que a aba Status
    lê. A vigia muda as duas coisas: ela reafirma enquanto o sequestro durar, e
    olha também no Modo Nativo, onde o sentinela não olha por regra antiga
    (*"no modo nativo devolvemos o controle pra steam"*). Pendurar isto nele
    trocaria o texto da aba Status sem ninguém pedir. A SONDA é a mesma
    (:func:`escritores_crus_alheios`) — uma varredura só de `/proc` no produto,
    chamada por dois donos.

    **SEGURAR NÃO É ESCREVER, e a vigia sabe.** Não há como ler a cor que a
    barra mostra (ver o cabeçalho deste módulo). Então enquanto um processo
    alheio segura o nó, a barra e o número são reescritos a cada segundo — o
    preço é um report mínimo por segundo por controle sequestrado (duas fatias
    de rádio, contra ~800 reports/s de uma mesa cheia), e ele só existe
    enquanto houver sequestrador.

    **QUANDO ELA VARRE.** Nó fechado e nenhum sequestrador conhecido: nunca —
    ninguém da sessão consegue abrir um nó `0600 root`. Nó alcançável: a cada
    `INTERVALO_DA_SONDA_S`. Sequestro conhecido: a cada
    `INTERVALO_DA_SONDA_COM_SEQUESTRO_S`, só para saber quando acabou; entre
    duas varreduras, o PID que morreu solta o nó na hora (um `stat`).

    Não lê relógio nem `/proc` por conta própria: tudo entra por injeção
    (`sonda`, `alcancavel`, `vivo`), como no sentinela. É o que deixa exercitar
    minutos de vigia em microssegundos de teste.
    """

    def __init__(
        self,
        *,
        sonda: Sonda | None = None,
        alcancavel: Callable[[str], bool] | None = None,
        vivo: Callable[[int], bool] | None = None,
        intervalo_da_sonda_s: float = INTERVALO_DA_SONDA_S,
        intervalo_com_sequestro_s: float = INTERVALO_DA_SONDA_COM_SEQUESTRO_S,
        intervalo_da_reafirmacao_s: float = INTERVALO_DA_REAFIRMACAO_S,
    ) -> None:
        self._sonda: Sonda = sonda if sonda is not None else escritores_crus_alheios
        self._alcancavel = alcancavel if alcancavel is not None else no_alcancavel
        self._vivo = vivo if vivo is not None else processo_vivo
        self._intervalo_da_sonda_s = float(intervalo_da_sonda_s)
        self._intervalo_com_sequestro_s = float(intervalo_com_sequestro_s)
        self._intervalo_da_reafirmacao_s = float(intervalo_da_reafirmacao_s)
        #: nó -> PIDs alheios que o seguram, pela última sonda (só vivos).
        self._por_no: dict[str, tuple[int, ...]] = {}
        self._sondado_em: float | None = None
        #: nó -> quando a barra e o número dele foram reescritos pela última vez.
        self._reafirmado_em: dict[str, float] = {}
        #: nó -> quantas reescritas desde que o sequestro começou (para o diário).
        self._reescritas: dict[str, int] = {}
        #: Os sequestros já DITOS (nó -> PIDs): é contra eles que as bordas se
        #: medem. Separado de `_por_no` porque o PID morto sai de lá entre duas
        #: varreduras, e a borda de saída não pode sumir junto.
        self._anunciados: dict[str, tuple[int, ...]] = {}
        self._vigilante = False

    @property
    def vigilante(self) -> bool:
        """True quando a próxima fatia tem de ser curta (há o que vigiar)."""
        return self._vigilante

    @property
    def sequestrados(self) -> Mapping[str, tuple[int, ...]]:
        """Os nós sequestrados na última foto, com os PIDs. Só leitura."""
        return dict(self._por_no)

    def reescritas(self, no: str) -> int:
        """Quantas vezes a barra deste nó foi reescrita neste sequestro."""
        return self._reescritas.get(str(no), 0)

    def quer_sondar(self, nos: Iterable[str], agora: float) -> bool:
        """Este passo precisa varrer `/proc`? Barato: `access` e `stat`.

        Atualiza `vigilante` como efeito — quem pergunta é a fatia, e a
        resposta decide o tamanho da próxima.
        """
        alvos = {str(n) for n in nos if n}
        self._esquecer_fora(alvos)
        self._soltar_os_mortos()
        abertos_sem_dono = [
            n for n in alvos if n not in self._por_no and self._alcancavel(n)
        ]
        self._vigilante = bool(abertos_sem_dono or self._por_no)
        if not self._vigilante:
            return False
        if self._sondado_em is None:
            return True
        intervalo = (
            self._intervalo_da_sonda_s
            if abertos_sem_dono
            else self._intervalo_com_sequestro_s
        )
        return (float(agora) - self._sondado_em) >= intervalo

    def passo(
        self, nos: Iterable[str], agora: float, *, sondar: bool
    ) -> PassoDaVigia:
        """Um passo da vigia: (talvez) varre, e diz o que reescrever AGORA.

        ``sondar`` vem de :meth:`quer_sondar`; separar as duas é o que deixa o
        chamador mandar SÓ a varredura para o executor — o resto é memória.
        Falha da sonda preserva a foto anterior (ausência não é "ninguém
        segura", a mesma disciplina do sentinela).
        """
        agora = float(agora)
        alvos = sorted({str(n) for n in nos if n})
        sondou = False
        if sondar and alvos:
            try:
                bruto = self._sonda(alvos)
            except Exception as exc:  # sonda é best-effort por contrato
                logger.debug("vigia_do_sequestro_sonda_falhou", err=str(exc))
            else:
                sondou = True
                self._sondado_em = agora
                self._por_no = {
                    str(no): tuple(p for p in (int(x) for x in pids) if self._vivo(p))
                    for no, pids in dict(bruto).items()
                    if str(no) in alvos and pids
                }
                self._por_no = {no: pids for no, pids in self._por_no.items() if pids}
        antes = self._anunciados
        novos = tuple(n for n in sorted(self._por_no) if n not in antes)
        soltos = tuple(n for n in sorted(antes) if n not in self._por_no)
        pids = {n: self._por_no[n] for n in novos}
        pids.update({n: antes[n] for n in soltos})
        self._anunciados = dict(self._por_no)
        for no in soltos:
            self._reafirmado_em.pop(no, None)
        a_reafirmar = tuple(
            n
            for n in sorted(self._por_no)
            if n in novos
            or (agora - self._reafirmado_em.get(n, float("-inf")))
            >= self._intervalo_da_reafirmacao_s
        )
        self._vigilante = self._vigilante or bool(self._por_no)
        return PassoDaVigia(
            sondou=sondou,
            novos=novos,
            soltos=soltos,
            a_reafirmar=a_reafirmar,
            pids=pids,
        )

    def reafirmado(self, nos: Iterable[str], agora: float) -> None:
        """Marca que a barra e o número destes nós acabaram de ser reescritos."""
        for no in nos:
            self._reafirmado_em[str(no)] = float(agora)
            self._reescritas[str(no)] = self._reescritas.get(str(no), 0) + 1

    def encerrar(self, no: str) -> int:
        """Zera a conta de um sequestro que acabou; devolve quantas reescritas."""
        return self._reescritas.pop(str(no), 0)

    def _soltar_os_mortos(self) -> None:
        """O PID que morreu solta o nó sem esperar a próxima varredura."""
        vivos = {
            no: tuple(p for p in pids if self._vivo(p)) for no, pids in self._por_no.items()
        }
        self._por_no = {no: pids for no, pids in vivos.items() if pids}

    def _esquecer_fora(self, alvos: set[str]) -> None:
        """Nó que saiu da mesa (desconexão, replug com outro número) sai da foto."""
        for no in [n for n in self._por_no if n not in alvos]:
            del self._por_no[no]
        for no in [n for n in self._reafirmado_em if n not in alvos]:
            del self._reafirmado_em[no]


__all__ = [
    "INTERVALO_DA_REAFIRMACAO_S",
    "INTERVALO_DA_SONDA_COM_SEQUESTRO_S",
    "INTERVALO_DA_SONDA_S",
    "MAX_PIDS_DA_STEAM",
    "ORCAMENTO_DA_VARREDURA_AMPLA_S",
    "ORCAMENTO_DA_VARREDURA_DE_PIDS_S",
    "ORCAMENTO_DA_VARREDURA_S",
    "PASSO_DA_VIGIA_S",
    "PGREP_TIMEOUT_S",
    "VALIDADE_DO_VEREDITO_S",
    "PassoDaVigia",
    "SentinelaDeEscritorCru",
    "Sonda",
    "Veredito",
    "VigiaDoSequestro",
    "escritores_crus_alheios",
    "holders_de_hidraw",
    "holders_de_hidraw_de_qualquer_um",
    "invalidar_pids_da_steam",
    "no_alcancavel",
    "pids_da_steam",
    "processo_vivo",
]
