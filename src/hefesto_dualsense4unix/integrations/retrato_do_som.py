"""O retrato do servidor de som, com um dono — O-SERVIDOR-DE-SOM-TEM-UM-LEITOR-SO-01.

**O DEFEITO, medido em 27/09/2026 no daemon dela (bpftrace e py-spy):** o
daemon executava `pactl` 22 a 23 vezes por segundo — 660 em 30 s —, cada um
um fork de um processo de 260 MB e um cliente novo no `pipewire-pulse`, o
mesmo servidor por onde passam o som do jogo e a háptica do rádio. Medido de
novo em 28/09, só lendo: 685 clientes novos em 30 s, e **nenhum** evento de
nó, de fluxo ou de padrão no mesmo intervalo. O servidor não mudou nada; o
daemon perguntou 685 vezes.

**A CAUSA:** o estado do servidor não tinha dono. O canal do microfone (5
perguntas por controle a cada 2 s), a luz do mic (3 a cada 1 s), o vigia do
alto-falante (2 a cada 0,4 s), as pontes (3 por endpoint a cada volta) e o
microfone do rádio (1 por controle a cada 1 s) perguntavam cada um por conta
própria, no próprio ritmo.

**A CURA, na origem:** este módulo guarda o que o servidor diz — nós de saída
e de entrada, fluxos, módulos e os padrões — e é o ÚNICO que pergunta a ele.
Quem o mantém em dia é o `pactl subscribe` do
`daemon/subsystems/ouvinte_do_som.py`: cada rajada de eventos relê só o tipo
que mudou, e sem evento não há `pactl` nenhum.

**TODO EXECUTOR DE `pactl` PERGUNTA AQUI PRIMEIRO** (:func:`responder`). As
perguntas de leitura continuam escritas por quem pergunta — ``["pactl",
"list", "sinks", "short"]`` —, e quem responde é o retrato. Com isso as
dezessete funções que liam o servidor passam a ler o retrato sem mudar uma
linha de parser, e o dublê que cada régua injeta continua alcançando o
produto: fora do daemon (a janela, o `hefesto doctor`, a suíte) não há dono, e
o executor roda como sempre rodou.

**AS ESCRITAS continuam pelo `pactl`** (``set-*``, ``load-module``…), e o
evento que elas geram atualiza o retrato. O executor avisa a escrita
(:func:`escreveu`) e o tipo que ela toca fica PENDENTE: a próxima leitura dele
relê o servidor antes de responder, para que o «escrevi, confiro» de quem
elege um microfone não leia a foto de antes da escrita. Não há segundo
caminho: a foto nunca é escrita com o valor pedido, só com o valor lido.

**SEM SERVIDOR, O RETRATO DIZ «NÃO SEI», E NÃO «NÃO HÁ»** (:data:`NAO_SEI`):
quando o `subscribe` cai, a foto velha para de responder, e quem pergunta
recebe a mesma falha de um `pactl` que não respondeu.

**VALE IGUAL PARA CABO E RÁDIO, QUALQUER MÁSCARA, P1 A P4:** o retrato é do
servidor, e não do controle.

**A LÍNGUA FICA PRESA EM C**, pela razão que esta casa já pagou duas vezes: o
`pactl` desta máquina traduz, e um leitor que dependa do idioma respondeu
*"não há"* sobre aparelho de pé.

**O FORMATO CURTO SAI DO LONGO**, e isso foi medido antes de ser escrito: os
`printf` do `pactl` 16.1 (lidos no binário) usam os mesmos campos nas duas
formas, e a síntese a partir do longo deu o curto byte a byte, nas saídas e
nas entradas da máquina dela, em 28/09/2026. Um tipo relido custa UM `pactl`.
"""

from __future__ import annotations

import asyncio
import contextlib
import itertools
import os
import shutil
import subprocess
import threading
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: O que o retrato guarda. `server` é o `pactl info` — de onde saem os dois
#: padrões e o nome do servidor.
TIPOS: Final[tuple[str, ...]] = (
    "sinks", "sources", "sink-inputs", "source-outputs", "modules", "server",
)

#: A palavra do `subscribe` (``Event 'change' on sink-input #12``) e o tipo
#: do retrato que ela manda reler. `client` fica de fora de propósito: cada
#: `pactl` — inclusive os deste módulo — é um cliente que nasce e morre, e
#: reler por eles faria o retrato perguntar por causa das próprias perguntas.
#: `card` também: a troca de perfil de uma placa chega como evento dos nós
#: dela, que já estão aqui.
TIPO_DO_EVENTO: Final[Mapping[str, str]] = {
    "sink": "sinks",
    "source": "sources",
    "sink-input": "sink-inputs",
    "source-output": "source-outputs",
    "module": "modules",
    "server": "server",
}

#: A ÚNICA pergunta de leitura que o daemon faz ao servidor, por tipo. Os
#: módulos ficam na forma curta porque é a única que alguém lê.
_LEITURA_DO_TIPO: Final[Mapping[str, tuple[str, ...]]] = {
    "sinks": ("pactl", "list", "sinks"),
    "sources": ("pactl", "list", "sources"),
    "sink-inputs": ("pactl", "list", "sink-inputs"),
    "source-outputs": ("pactl", "list", "source-outputs"),
    "modules": ("pactl", "list", "modules", "short"),
    "server": ("pactl", "info"),
}

#: Os verbos do `pactl` que só leem. O resto é escrita — menos o `subscribe`,
#: que é o canal de eventos e tem dono próprio (`ouvinte_do_som`).
LEITURAS: Final[frozenset[str]] = frozenset({
    "list", "info", "stat",
    "get-default-sink", "get-default-source",
    "get-sink-volume", "get-source-volume",
    "get-sink-mute", "get-source-mute",
})

#: O teto de uma leitura. Curto de propósito, pela razão do `ouvinte_do_som`:
#: uma leitura pendurada segura quem esperava a resposta.
TETO_DA_LEITURA_S: Final[float] = 4.0

#: Um tipo cuja releitura FALHOU não responde, e só se tenta de novo depois
#: deste intervalo. Sem ele, um servidor que recusa depressa (rc≠0 sem estouro,
#: que o recuo não pega) voltaria a levar uma pergunta por leitor por tique —
#: o defeito inteiro, pela porta dos fundos.
INTERVALO_DA_DUVIDA_S: Final[float] = 1.0


class _NaoSei:
    """A resposta de quem não sabe. Ver :data:`NAO_SEI`."""

    _instancia: _NaoSei | None = None

    def __new__(cls) -> _NaoSei:
        if cls._instancia is None:
            cls._instancia = super().__new__(cls)
        return cls._instancia

    def __repr__(self) -> str:
        return "NAO_SEI"

    def __bool__(self) -> bool:
        return False


#: **O retrato tem dono e não sabe responder**: o servidor caiu, a releitura
#: falhou, ou o nó perguntado não existe. O executor devolve a MESMA falha que
#: devolveria para um `pactl` que saiu com erro — `None`, `""`, `(127, "")` —,
#: e não pergunta ao servidor por conta própria.
NAO_SEI: Final[_NaoSei] = _NaoSei()


# ---------------------------------------------------------------------------
# O formato do `pactl`, lido uma vez por releitura
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NoDeSom:
    """Um nó de saída (`Sink`) ou de entrada (`Source`), como o `pactl list` o diz."""

    indice: int
    nome: str
    descricao: str = ""
    driver: str = ""
    formato: str = ""
    estado: str = ""
    mudo: bool | None = None
    volume: str = ""
    balanco: str = ""
    propriedades: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Fluxo:
    """Um fluxo de um programa: `Sink Input` (tocando) ou `Source Output` (gravando).

    ``alvo`` é o índice do nó onde ele toca ou de onde grava, como o `pactl` o
    imprime; ``cliente`` é ``"n/a"`` quando o fluxo não tem cliente.
    """

    indice: int
    alvo: str
    cliente: str = ""
    driver: str = ""
    formato: str = ""
    corked: bool | None = None
    mudo: bool | None = None
    propriedades: Mapping[str, str] = field(default_factory=dict)


_CABECAS_DE_NO: Final[tuple[str, ...]] = ("Sink", "Source")
_CABECAS_DE_FLUXO: Final[tuple[str, ...]] = ("Sink Input", "Source Output")


def _sim_ou_nao(valor: str) -> bool | None:
    if valor == "yes":
        return True
    if valor == "no":
        return False
    return None


@dataclass
class _Bloco:
    indice: int
    campos: dict[str, str] = field(default_factory=dict)
    props: dict[str, str] = field(default_factory=dict)
    balanco: str = ""


def _blocos(texto: str, cabecas: tuple[str, ...]) -> list[_Bloco]:
    """Os blocos de um `pactl list` longo, com os campos de nível um e as propriedades.

    O formato, pelo binário: o bloco abre em ``<Cabeça> #<índice>``; os campos
    têm UM tab (``\\tName: …``); a continuação do volume tem um tab e espaços
    (``\\t        balance 0.00``); as propriedades têm DOIS tabs e a forma
    ``chave = "valor"``. Portas e formatos também têm dois tabs, e ficam de
    fora porque ninguém os lê.
    """
    blocos: list[_Bloco] = []
    atual: _Bloco | None = None
    nas_propriedades = False
    ultima = ""
    for linha in texto.splitlines():
        cabeca = next((c for c in cabecas if linha.startswith(c + " #")), None)
        if cabeca is not None:
            try:
                atual = _Bloco(indice=int(linha[len(cabeca) + 2:].strip()))
            except ValueError:
                atual = None
                continue
            blocos.append(atual)
            nas_propriedades = False
            ultima = ""
            continue
        if atual is None:
            continue
        if linha.startswith("\t\t"):
            if nas_propriedades:
                chave, sep, valor = linha.strip().partition(" = ")
                if sep:
                    valor = valor.strip()
                    if len(valor) >= 2 and valor[0] == valor[-1] == '"':
                        valor = valor[1:-1]
                    atual.props[chave.strip()] = valor
            continue
        if not linha.startswith("\t"):
            continue
        corpo = linha[1:]
        if corpo.startswith(" "):
            if ultima == "Volume" and "balance" in corpo:
                atual.balanco = corpo.strip()
            continue
        chave, sep, valor = corpo.partition(":")
        if not sep:
            continue
        chave = chave.strip()
        nas_propriedades = chave == "Properties"
        atual.campos.setdefault(chave, valor.strip())
        ultima = chave
    return blocos


def nos_do_texto(texto: str) -> tuple[NoDeSom, ...]:
    """Os nós de um `pactl list sinks` ou `pactl list sources` longo. Função pura."""
    return tuple(
        NoDeSom(
            indice=b.indice,
            nome=b.campos.get("Name", ""),
            descricao=b.campos.get("Description", ""),
            driver=b.campos.get("Driver", ""),
            formato=b.campos.get("Sample Specification", ""),
            estado=b.campos.get("State", ""),
            mudo=_sim_ou_nao(b.campos.get("Mute", "")),
            volume=b.campos.get("Volume", ""),
            balanco=b.balanco,
            propriedades=dict(b.props),
        )
        for b in _blocos(texto, _CABECAS_DE_NO)
    )


def fluxos_do_texto(texto: str) -> tuple[Fluxo, ...]:
    """Os fluxos de um `pactl list sink-inputs|source-outputs` longo. Função pura."""
    return tuple(
        Fluxo(
            indice=b.indice,
            alvo=b.campos.get("Sink", b.campos.get("Source", "")),
            cliente=b.campos.get("Client", ""),
            driver=b.campos.get("Driver", ""),
            formato=b.campos.get("Sample Specification", ""),
            corked=_sim_ou_nao(b.campos.get("Corked", "")),
            mudo=_sim_ou_nao(b.campos.get("Mute", "")),
            propriedades=dict(b.props),
        )
        for b in _blocos(texto, _CABECAS_DE_FLUXO)
    )


def curto_dos_nos(nos: Iterable[NoDeSom]) -> str:
    """O `pactl list sinks|sources short` a partir do longo.

    ``%u\\t%s\\t%s\\t%s\\t%s`` — índice, nome, driver, formato, estado —, o
    `printf` do `pactl` 16.1. Conferido byte a byte contra a saída curta da
    máquina dela em 28/09/2026.
    """
    return "".join(
        f"{n.indice}\t{n.nome}\t{n.driver}\t{n.formato}\t{n.estado}\n" for n in nos)


def curto_dos_fluxos(fluxos: Iterable[Fluxo]) -> str:
    """O `pactl list sink-inputs|source-outputs short` a partir do longo.

    ``%u\\t%u\\t%s\\t%s\\t%s`` — índice, nó, cliente, driver, formato. O cliente
    que o longo diz ``n/a`` o curto diz ``-``: é o mesmo `PA_INVALID_INDEX`
    nas duas formas do `printf`.
    """
    return "".join(
        f"{f.indice}\t{f.alvo}\t{'-' if f.cliente in ('', 'n/a') else f.cliente}"
        f"\t{f.driver}\t{f.formato}\n"
        for f in fluxos)


def campos_do_servidor(texto: str) -> dict[str, str]:
    """``{campo: valor}`` do `pactl info`. Função pura."""
    fora: dict[str, str] = {}
    for linha in texto.splitlines():
        chave, sep, valor = linha.partition(":")
        if sep:
            fora[chave.strip()] = valor.strip()
    return fora


def _servidor_sem_o_cliente(texto: str) -> str:
    """O `info` sem a linha que muda a cada pergunta.

    ``Client Index`` é o número do PRÓPRIO `pactl` que perguntou — muda toda
    vez, e compará-lo faria cada releitura parecer mudança.
    """
    return "\n".join(
        linha for linha in texto.splitlines() if not linha.startswith("Client Index:"))


# ---------------------------------------------------------------------------
# A pergunta
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Pergunta:
    """Uma leitura que o retrato sabe responder: de qual tipo, e em que forma."""

    tipo: str
    forma: str  # "longa" | "curta" | "padrao" | "volume" | "mudo" | "info"
    alvo: str = ""


_TIPOS_DE_LISTA: Final[frozenset[str]] = frozenset(
    {"sinks", "sources", "sink-inputs", "source-outputs", "modules"})


def verbo_do_pactl(argv: Sequence[object]) -> str | None:
    """O verbo de um argv de `pactl`, ou `None` se o argv não é de `pactl`."""
    if not argv:
        return None
    if os.path.basename(str(argv[0])) != "pactl":
        return None
    if len(argv) < 2:
        return ""
    return str(argv[1])


def entender(argv: Sequence[object]) -> Pergunta | None:
    """A leitura que este argv faz, se o retrato souber respondê-la."""
    verbo = verbo_do_pactl(argv)
    if not verbo:
        return None
    resto = [str(a) for a in argv[2:]]
    if verbo == "list":
        palavras = [p for p in resto if p != "short"]
        curta = len(palavras) < len(resto)
        if len(palavras) != 1 or palavras[0] not in _TIPOS_DE_LISTA:
            return None
        tipo = palavras[0]
        if tipo == "modules":
            return Pergunta("modules", "curta") if curta else None
        return Pergunta(tipo, "curta" if curta else "longa")
    if verbo == "info" and not resto:
        return Pergunta("server", "info")
    if verbo in ("get-default-sink", "get-default-source") and not resto:
        return Pergunta("server", "padrao", verbo.rsplit("-", 1)[-1])
    for de, tipo in (("sink", "sinks"), ("source", "sources")):
        if len(resto) == 1 and verbo == f"get-{de}-volume":
            return Pergunta(tipo, "volume", resto[0])
        if len(resto) == 1 and verbo == f"get-{de}-mute":
            return Pergunta(tipo, "mudo", resto[0])
    return None


def e_leitura(argv: Sequence[object]) -> bool:
    return verbo_do_pactl(argv) in LEITURAS


def tipos_da_escrita(argv: Sequence[object]) -> frozenset[str]:
    """Os tipos que uma escrita pode ter mudado. Na dúvida, todos."""
    verbo = verbo_do_pactl(argv)
    if verbo is None or verbo in LEITURAS or verbo == "subscribe":
        return frozenset()
    if verbo in ("set-default-sink", "set-default-source"):
        return frozenset({"server"})
    for prefixo, tipos in (
        ("set-sink-input-", {"sink-inputs"}),
        ("set-source-output-", {"source-outputs"}),
        ("move-sink-input", {"sink-inputs"}),
        ("move-source-output", {"source-outputs"}),
        ("kill-sink-input", {"sink-inputs"}),
        ("kill-source-output", {"source-outputs"}),
        ("set-sink-", {"sinks", "sources"}),
        ("suspend-sink", {"sinks", "sources"}),
        ("set-source-", {"sources"}),
        ("suspend-source", {"sources"}),
    ):
        if verbo.startswith(prefixo):
            return frozenset(tipos)
    return frozenset(TIPOS)


# ---------------------------------------------------------------------------
# Quem pergunta ao servidor
# ---------------------------------------------------------------------------


def _ambiente() -> dict[str, str]:
    return {**os.environ, "LC_ALL": "C", "LANG": "C"}


def ler_do_servidor(argv: Sequence[str]) -> str | None:
    """A leitura do retrato: o stdout do `pactl`, ou `None` em qualquer falha.

    Pelo recuo do servidor, que é um só (`dualsense_bt_audio.PACTL`): em recuo
    não pergunta; prazo estourado entra no recuo; rc=0 o zera. Nunca levanta.
    """
    from hefesto_dualsense4unix.integrations.dualsense_bt_audio import PACTL

    if shutil.which("pactl") is None or PACTL.mudo():
        return None
    try:
        proc = subprocess.run(
            list(argv), capture_output=True, text=True,
            timeout=TETO_DA_LEITURA_S, check=False, env=_ambiente(),
        )
    except subprocess.TimeoutExpired:
        PACTL.estourou()
        return None
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    PACTL.respondeu()
    return proc.stdout or ""


def _servidor_sob_suspeita() -> bool:
    """O recuo do servidor está de pé (em curso, ou vencido sem resposta desde então)."""
    from hefesto_dualsense4unix.integrations.dualsense_bt_audio import PACTL

    return PACTL.espera_s > 0


class RetratoDoSom:
    """O que o servidor de som disse por último, com um dono por processo.

    Três estados, e são três coisas diferentes:

    * **solto** — ninguém neste processo mantém o retrato (a janela, o
      `doctor`, a suíte). :meth:`responder` devolve `None`, e o executor
      pergunta ao servidor como sempre;
    * **vivo** — o `ouvinte_do_som` leu tudo e está escutando. Toda leitura
      sai da foto;
    * **sem servidor** — o dono existe e o `subscribe` caiu. Toda leitura
      recebe :data:`NAO_SEI`.
    """

    def __init__(self, ler: Callable[[Sequence[str]], str | None] | None = None) -> None:
        self._ler_injetado = ler
        self._trava = threading.RLock()
        self._mudou = threading.Condition(self._trava)
        self._contador = itertools.count(1)
        self._dono = False
        self._conectado = False
        self._laco: asyncio.AbstractEventLoop | None = None
        self._textos: dict[str, str] = {}
        self._seq: dict[str, int] = {}
        self._pendente_desde: dict[str, int] = {}
        self._duvida: dict[str, float] = {}
        self._analisado: dict[str, tuple[int, object]] = {}
        self._geracao = 0
        self._geracao_do_tipo: dict[str, int] = dict.fromkeys(TIPOS, 0)
        self._esperas: set[tuple[asyncio.AbstractEventLoop, asyncio.Event]] = set()

    # -- quem lê -------------------------------------------------------------

    def _ler(self, argv: Sequence[str]) -> str | None:
        ler = self._ler_injetado or ler_do_servidor
        try:
            return ler(list(argv))
        except Exception as exc:  # a leitura nunca derruba quem pergunta
            logger.debug("retrato_do_som_leitura_falhou", err=str(exc))
            return None

    def _reler_um(self, tipo: str) -> bool:
        """Relê UM tipo. True = o texto mudou."""
        with self._trava:
            seq = next(self._contador)
        texto = self._ler(_LEITURA_DO_TIPO[tipo])
        with self._trava:
            if texto is None:
                if self._seq.get(tipo, 0) < seq:
                    self._duvida[tipo] = time.monotonic()
                    if self._pendente_desde.get(tipo, 0) < seq:
                        self._pendente_desde.pop(tipo, None)
                return False
            if self._seq.get(tipo, 0) > seq:
                return False  # uma leitura mais nova já chegou
            antes = self._textos.get(tipo)
            if tipo == "server":
                mudou = antes is None or (
                    _servidor_sem_o_cliente(antes) != _servidor_sem_o_cliente(texto))
            else:
                mudou = antes != texto
            self._textos[tipo] = texto
            self._seq[tipo] = seq
            self._duvida.pop(tipo, None)
            if self._pendente_desde.get(tipo, 0) < seq:
                self._pendente_desde.pop(tipo, None)
            if mudou:
                self._analisado.pop(tipo, None)
            return mudou

    def reler(self, tipos: Iterable[str]) -> frozenset[str]:
        """Relê os tipos dados — um `pactl` por tipo — e avisa quem espera."""
        mudaram = frozenset(t for t in dict.fromkeys(tipos) if t in _LEITURA_DO_TIPO
                            and self._reler_um(t))
        if mudaram:
            self._avisar(mudaram)
        return mudaram

    def carregar(self) -> bool:
        """A leitura inteira, a de quando o ouvinte sobe. True = tudo lido."""
        self.reler(TIPOS)
        return self.completo()

    def completo(self) -> bool:
        with self._trava:
            return all(t in self._textos for t in TIPOS) and not self._duvida

    # -- o dono --------------------------------------------------------------

    def assumir(self, laco: asyncio.AbstractEventLoop | None = None) -> None:
        """O ouvinte leu e está escutando: daqui em diante as leituras saem da foto."""
        with self._trava:
            self._dono = True
            self._conectado = True
            self._laco = laco
        self._avisar()

    def perdeu_o_servidor(self) -> None:
        """O `subscribe` caiu: a foto para de responder até ele voltar."""
        with self._trava:
            if not self._conectado:
                return
            self._conectado = False
        self._avisar()

    def soltar(self) -> None:
        """Ninguém mantém mais o retrato neste processo (o daemon parou)."""
        with self._trava:
            self._dono = False
            self._conectado = False
            self._laco = None
            self._textos.clear()
            self._seq.clear()
            self._pendente_desde.clear()
            self._duvida.clear()
            self._analisado.clear()
        self._avisar()

    @property
    def dono(self) -> bool:
        with self._trava:
            if self._dono and self._laco is not None and self._laco.is_closed():
                # O laço que assumiu morreu sem soltar (um teste que não parou o
                # daemon, um processo que saiu pelo meio). Dono morto é solto.
                self._dono = False
                self._conectado = False
                self._laco = None
            return self._dono

    @property
    def vivo(self) -> bool:
        with self._trava:
            return self.dono and self._conectado

    @property
    def geracao(self) -> int:
        """Quantas vezes o retrato mudou. Quem espera compara com a que viu."""
        with self._trava:
            return self._geracao

    def marca(self, tipos: Iterable[str] | None = None) -> int:
        """A geração dos tipos dados (todos, sem `tipos`). Só cresce.

        Quem espera por UM assunto — o canal do microfone lê fontes e padrão;
        o vigia do alto-falante, saídas e fluxos — não acorda pela mudança dos
        outros: um jogo tocando muda os fluxos de saída e não tem por que
        fazer o selo do microfone reler quatro controles.
        """
        with self._trava:
            if tipos is None:
                return self._geracao
            return sum(self._geracao_do_tipo.get(t, 0) for t in tipos)

    # -- quem espera ---------------------------------------------------------

    def _avisar(self, tipos: Iterable[str] = TIPOS) -> None:
        with self._trava:
            self._geracao += 1
            for tipo in tipos:
                if tipo in self._geracao_do_tipo:
                    self._geracao_do_tipo[tipo] += 1
            self._mudou.notify_all()
            esperas = list(self._esperas)
        for laco, evento in esperas:
            with contextlib.suppress(RuntimeError):
                laco.call_soon_threadsafe(evento.set)

    def acordar(self) -> None:
        """Acorda quem espera sem que nada tenha mudado (quem espera vai parar)."""
        with self._trava:
            self._mudou.notify_all()

    def esperar(
        self, desde: int, prazo: float, tipos: Iterable[str] | None = None
    ) -> int:
        """Bloqueia até a :meth:`marca` dos `tipos` sair de `desde`, ou até o prazo.

        Devolve a marca de agora, que pode ser a mesma: :meth:`acordar` e a
        mudança de outro assunto também soltam quem espera — é assim que quem
        vai parar não espera o prazo inteiro. Quem recebe a mesma marca só
        olha de novo, e a olhada sai da foto.
        """
        assunto = None if tipos is None else tuple(tipos)
        with self._mudou:
            if self.marca(assunto) == desde:
                self._mudou.wait(timeout=max(0.0, prazo))
            return self.marca(assunto)

    async def esperar_async(
        self, desde: int, prazo: float, tipos: Iterable[str] | None = None
    ) -> int:
        """Como :meth:`esperar`, sem segurar o laço de eventos."""
        assunto = None if tipos is None else tuple(tipos)
        laco = asyncio.get_running_loop()
        limite = laco.time() + max(0.0, prazo)
        while True:
            evento = asyncio.Event()
            chave = (laco, evento)
            with self._trava:
                agora = self.marca(assunto)
                if agora != desde:
                    return agora
                self._esperas.add(chave)
            falta = limite - laco.time()
            try:
                if falta <= 0:
                    return agora
                with contextlib.suppress(TimeoutError, asyncio.TimeoutError):
                    await asyncio.wait_for(evento.wait(), timeout=falta)
            finally:
                with self._trava:
                    self._esperas.discard(chave)
            if laco.time() >= limite:
                return self.marca(assunto)

    # -- quem pergunta -------------------------------------------------------

    def _texto_em_dia(self, tipo: str) -> str | None:
        """O texto do tipo, relido antes se uma escrita o deixou pendente.

        Só com o retrato VIVO: sem dono não há evento que o mantenha em dia, e
        uma foto que ninguém atualiza responderia sobre o passado para sempre.

        **SERVIDOR SOB SUSPEITA NÃO RESPONDE PELA FOTO.** Um `pipewire-pulse`
        TRAVADO não derruba o `subscribe` — ele só para de falar —, e a foto
        continuaria respondendo como se nada houvesse. Quem percebe o
        travamento é o recuo do servidor (`dualsense_bt_audio.PACTL`), pelo
        prazo estourado de uma escrita ou de uma releitura. Com o recuo de pé,
        toda resposta passa a exigir leitura nova: em recuo ela nem sai («não
        sei»); com o recuo vencido, a primeira que responder o zera — é a
        mesma sondagem de `alto_falante_bt._o_servidor_atende`, pela porta do
        retrato.
        """
        if not self.vivo:
            return None
        with self._trava:
            falhou = self._duvida.get(tipo)
            precisa = (tipo in self._pendente_desde or tipo not in self._textos
                       or falhou is not None)
        precisa = precisa or _servidor_sob_suspeita()
        if precisa:
            if falhou is not None and time.monotonic() - falhou < INTERVALO_DA_DUVIDA_S:
                return None
            if self._reler_um(tipo):
                self._avisar({tipo})
        with self._trava:
            # Uma escrita que chegou DURANTE a releitura deixa o tipo pendente
            # de novo; a resposta é a desta releitura, que já é posterior à
            # escrita que a pediu, e a próxima pergunta relê outra vez.
            if tipo in self._duvida:
                return None
            return self._textos.get(tipo)

    def _analisar(self, tipo: str, texto: str) -> object:
        with self._trava:
            seq = self._seq.get(tipo, 0)
            guardado = self._analisado.get(tipo)
            if guardado is not None and guardado[0] == seq:
                return guardado[1]
        if tipo in ("sinks", "sources"):
            valor: object = nos_do_texto(texto)
        elif tipo in ("sink-inputs", "source-outputs"):
            valor = fluxos_do_texto(texto)
        elif tipo == "server":
            valor = campos_do_servidor(texto)
        else:
            valor = texto
        with self._trava:
            self._analisado[tipo] = (seq, valor)
        return valor

    def _nos(self, tipo: str) -> tuple[NoDeSom, ...] | None:
        texto = self._texto_em_dia(tipo)
        if texto is None:
            return None
        valor = self._analisar(tipo, texto)
        return valor if isinstance(valor, tuple) else None

    def _servidor(self) -> dict[str, str] | None:
        texto = self._texto_em_dia("server")
        if texto is None:
            return None
        valor = self._analisar("server", texto)
        return dict(valor) if isinstance(valor, dict) else None

    def responder(self, argv: Sequence[object]) -> str | _NaoSei | None:
        """A resposta a uma leitura de `pactl`, pelo retrato.

        * ``None`` — o retrato não responde por este argv: não há dono neste
          processo, o argv não é de `pactl`, ou é uma escrita. O executor roda.
        * :data:`NAO_SEI` — há dono e não há resposta. O executor devolve a
          falha dele, sem perguntar ao servidor.
        * ``str`` — a saída que o `pactl` daria, byte a byte.

        Uma leitura que o retrato não fotografa (`list cards`, `stat`) com dono
        vivo é feita AQUI, pelo leitor do retrato, e não guardada: quem pergunta
        ao servidor continua sendo um só.
        """
        if verbo_do_pactl(argv) is None or not self.dono:
            return None
        if not e_leitura(argv):
            return None
        if not self.vivo:
            return NAO_SEI
        pergunta = entender(argv)
        if pergunta is None:
            texto = self._ler([str(a) for a in argv])
            return texto if texto is not None else NAO_SEI
        resposta = self._responder(pergunta)
        return NAO_SEI if resposta is None else resposta

    def _responder(self, p: Pergunta) -> str | None:
        if p.forma == "info":
            return self._texto_em_dia("server")
        if p.forma == "padrao":
            campos = self._servidor()
            if campos is None:
                return None
            chave = "Default Sink" if p.alvo == "sink" else "Default Source"
            valor = campos.get(chave)
            return None if valor is None else f"{valor}\n"
        if p.forma in ("longa", "curta") and p.tipo == "modules":
            return self._texto_em_dia("modules")
        if p.forma == "longa":
            return self._texto_em_dia(p.tipo)
        if p.tipo in ("sink-inputs", "source-outputs"):
            texto = self._texto_em_dia(p.tipo)
            if texto is None:
                return None
            fluxos = self._analisar(p.tipo, texto)
            return curto_dos_fluxos(fluxos) if isinstance(fluxos, tuple) else None
        nos = self._nos(p.tipo)
        if nos is None:
            return None
        if p.forma == "curta":
            return curto_dos_nos(nos)
        no = self._no_por_alvo(p.tipo, nos, p.alvo)
        if no is None:
            return None
        if p.forma == "mudo":
            return None if no.mudo is None else f"Mute: {'yes' if no.mudo else 'no'}\n"
        if not no.volume:
            return None
        return f"Volume: {no.volume}\n" + (f"        {no.balanco}\n" if no.balanco else "")

    def _no_por_alvo(
        self, tipo: str, nos: tuple[NoDeSom, ...], alvo: str
    ) -> NoDeSom | None:
        nome = alvo
        if alvo in ("@DEFAULT_SINK@", "@DEFAULT_SOURCE@", "@DEFAULT_MONITOR@"):
            campos = self._servidor()
            if campos is None:
                return None
            if alvo == "@DEFAULT_SOURCE@":
                nome = campos.get("Default Source", "")
            else:
                nome = campos.get("Default Sink", "")
                if alvo == "@DEFAULT_MONITOR@":
                    nome = f"{nome}.monitor"
        for no in nos:
            if no.nome == nome or (nome.isdigit() and no.indice == int(nome)):
                return no
        return None

    def escreveu(self, argv: Sequence[object]) -> None:
        """Uma escrita saiu: o que ela tocou é relido antes da próxima resposta."""
        tipos = tipos_da_escrita(argv)
        if not tipos or not self.dono:
            return
        with self._trava:
            seq = next(self._contador)
            for tipo in tipos:
                self._pendente_desde[tipo] = seq

    # -- as consultas de quem mora no daemon ---------------------------------

    def nos(self, tipo: str) -> tuple[NoDeSom, ...] | None:
        """Os nós de `sinks` ou `sources`, ou `None` (não sei)."""
        if tipo not in ("sinks", "sources"):
            raise ValueError(tipo)
        return self._nos(tipo)

    def fluxos(self, tipo: str) -> tuple[Fluxo, ...] | None:
        """Os fluxos de `sink-inputs` ou `source-outputs`, ou `None` (não sei)."""
        if tipo not in ("sink-inputs", "source-outputs"):
            raise ValueError(tipo)
        texto = self._texto_em_dia(tipo)
        if texto is None:
            return None
        valor = self._analisar(tipo, texto)
        return valor if isinstance(valor, tuple) else None

    def padrao(self, de: str) -> str | None:
        """O nome do nó padrão (`sink` ou `source`), ou `None` (não sei)."""
        campos = self._servidor()
        if campos is None:
            return None
        return campos.get("Default Sink" if de == "sink" else "Default Source")

    def descricoes(self) -> dict[str, str]:
        """``{nome cru: Description}`` de todas as saídas e entradas que o retrato tem."""
        fora: dict[str, str] = {}
        for tipo in ("sinks", "sources"):
            for no in self._nos(tipo) or ():
                if no.descricao:
                    fora[no.nome] = no.descricao
        return fora


#: O retrato deste processo. Nasce SOLTO: só o `ouvinte_do_som` do daemon o assume.
RETRATO: Final[RetratoDoSom] = RetratoDoSom()


def responder(argv: Sequence[object]) -> str | _NaoSei | None:
    """:meth:`RetratoDoSom.responder` do retrato deste processo."""
    return RETRATO.responder(argv)


def escreveu(argv: Sequence[object]) -> None:
    """:meth:`RetratoDoSom.escreveu` do retrato deste processo."""
    RETRATO.escreveu(argv)


__all__ = [
    "INTERVALO_DA_DUVIDA_S",
    "LEITURAS",
    "NAO_SEI",
    "RETRATO",
    "TETO_DA_LEITURA_S",
    "TIPOS",
    "TIPO_DO_EVENTO",
    "Fluxo",
    "NoDeSom",
    "Pergunta",
    "RetratoDoSom",
    "campos_do_servidor",
    "curto_dos_fluxos",
    "curto_dos_nos",
    "e_leitura",
    "entender",
    "escreveu",
    "fluxos_do_texto",
    "ler_do_servidor",
    "nos_do_texto",
    "responder",
    "tipos_da_escrita",
    "verbo_do_pactl",
]
