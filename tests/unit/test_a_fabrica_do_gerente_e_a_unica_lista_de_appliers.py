"""A-FÁBRICA-COM-UM-CLIENTE-01 — o portão da classe, e as rotas que passaram a
vir da fábrica.

O DEFEITO, EM UMA LINHA
-----------------------
**Applier ausente NÃO levanta: a seção é ignorada em silêncio.** Uma rota que
monta o ``ProfileManager`` com a própria lista nasce funcionando "quase", e o
"quase" só aparece no aparelho dela. É a família ``A-CASA-SABE-E-O-PRODUTO-NAO-FAZ``
(a cura escrita e nunca ligada) casada com a ``ELO-MUDO-01`` (o produto responde
pelo TRANSPORTE e nunca pelo EFEITO): o perfil "foi reaplicado", e uma seção
dele ficou como o jogo a deixou.

MEDIDO em 22/08/2026, por varredura de AST sobre ``src/``, ANTES desta leva:
``gerente_do_daemon`` tinha UM cliente (``daemon/launch_env.py``) e havia DOZE
construções diretas de ``ProfileManager`` à mão (treze com a que a própria
fábrica faz), SEIS delas declarando os sete appliers — cinco rotas de ativação,
migradas nesta leva, e o ``connection.py::restore_last_profile``, que declara os
sete e neutraliza dois de propósito. Uma já tinha derivado —
``daemon/lifecycle.py::_reapply_last_profile``, a rota que roda ao desligar o
Modo Nativo, passava SEIS. **FECHADA em 26/08/2026** (LEVA-1-B): a rota passou
a vir de ``gerente_do_daemon`` com o embrulho do ``mode`` como único desvio, e
a entrada dela em :data:`_A_MAO_COM_RAZAO` foi apagada no mesmo commit.

O QUE ESTE ARQUIVO VIGIA
------------------------
1. **o portão da classe (E3)** — toda construção direta de ``ProfileManager``
   que declare QUALQUER applier precisa de razão escrita em
   :data:`_A_MAO_COM_RAZAO`. Construção sem applier nenhum é legítima por
   construção: ela não ativa nada (listar perfis, carimbar ponte, a CLI);
2. **a tabela não envelhece calada** — cada entrada tem de continuar batendo,
   nome por nome, com o que a árvore diz. Rota consertada faz a entrada
   sobrar, e o portão cobra que ela seja APAGADA. É a mesma inversão do
   ``portao_a_casa_sabe_e_o_produto_nao_faz`` e do ``_SEM_ESCRITOR_HOJE``;
3. **as cinco rotas convertidas (E2)** entregam, de fato, os sete appliers —
   e a prova é pelo EFEITO: o teste dirige a rota de produção e olha o gerente
   que ela construiu, nunca a linha de código;
4. **o desvio da allowlist continua de pé** — a fábrica aceita um
   ``mode_applier`` explícito, e ele vence.

POR QUE A RÉGUA É AST, E NÃO UMA LISTA DE ROTAS
------------------------------------------------
Uma lista escrita à mão caduca na próxima rota — que é exatamente como esta
derivou. O conjunto de acusações é DERIVADO em runtime; o que é escrito à mão
é a CLASSIFICAÇÃO, e ela é exaustiva: rota nova sem classificação reprova por
estar SEM CLASSIFICAÇÃO, não por estar numa denylist.

E a régua conta o NOME do parâmetro, nunca a tupla ``APPLIERS_DO_DAEMON``:
``62d092a`` mostrou que a primeira versão daquele teste iterava
``APPLIERS_DO_DAEMON`` para conferir ``APPLIERS_DO_DAEMON`` e passava com um par
arrancado. Contagem que se confere sozinha não é contagem.

PREÇO DECLARADO DESTA RÉGUA, e ele é real: contar NOMES não vê um applier
passado como ``None`` de propósito. ``daemon/connection.py::restore_last_profile``
declara os sete e neutraliza dois (``mouse_applier=None`` e ``mode_applier=None``,
BUG-BOOT-RESTORE-FLIPS-EMULATION-01) — para a varredura ela é "completa". Está
classificada abaixo com essa nota, porque o portão que finge ver o que não vê é
pior que portão nenhum.

POR QUE REUSA ``modulos_alcancados`` E NÃO O RESTO DA MÁQUINA
--------------------------------------------------------------
O ``portao_a_casa_sabe_e_o_produto_nao_faz`` passou em 22/08/2026 a medir
alcance por GRAFO DE IMPORT a partir dos pontos de entrada declarados
(``61ba2ab``), e 33 acusados viraram 60. Essa máquina responde *"quem chama
este símbolo?"* — e aqui a pergunta é outra: *"que FORMA tem esta chamada?"*.
Todo sítio de construção é, por definição, um chamador; o grafo não muda
verdicto nenhum sobre a forma.

O que ela responde e este portão precisa é se a rota está VIVA: uma dívida
apontando para módulo morto é paisagem. Por isso ``modulos_alcancados`` entra
como asserção (``test_toda_rota_que_constroi_o_gerente_esta_viva``) e nada
mais. MEDIDO em 22/08/2026, DEPOIS desta leva: as oito construções de
``ProfileManager`` que restam moram em CINCO módulos, e os cinco estão nos 201
alcançados — nenhum é código morto.
"""
from __future__ import annotations

import ast
import asyncio
import inspect
import re
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import (
    APPLIERS_DO_DAEMON,
    HERDA_DO_DAEMON,
    ProfileManager,
    gerente_do_daemon,
)
from tests.unit.portao_a_casa_sabe_e_o_produto_nao_faz import modulos_alcancados

_RAIZ = Path(__file__).resolve().parents[2]
_SRC = _RAIZ / "src" / "hefesto_dualsense4unix"
_PACOTE = "hefesto_dualsense4unix"

#: Os nomes de parâmetro que injetam um applier de seção. Derivado do CONTRATO
#: (`APPLIERS_DO_DAEMON`) e conferido contra o dataclass logo abaixo, porque a
#: tupla sozinha não é régua — ver o docstring.
_NOMES_DE_APPLIER = frozenset(parametro for parametro, _ in APPLIERS_DO_DAEMON)

#: Quantos caracteres uma razão precisa ter para ser razão, e não isenção
#: fingindo ser decisão. Mesmo número do `portao_a_casa_sabe_e_o_produto_nao_faz`.
_RAZAO_MINIMA = 80

_DATA = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")


@dataclass(frozen=True)
class Construcao:
    """Uma chamada a ``ProfileManager(...)`` achada em ``src/``."""

    modulo: str
    funcao: str
    linha: int
    appliers: frozenset[str]

    @property
    def chave(self) -> tuple[str, str]:
        return (self.modulo, self.funcao)

    @property
    def endereco(self) -> str:
        return f"{self.modulo}::{self.funcao} (linha {self.linha})"


@dataclass(frozen=True)
class Razao:
    """A classificação escrita à mão de uma construção direta."""

    appliers: frozenset[str]
    motivo: str


#: A CLASSIFICAÇÃO EXAUSTIVA das construções diretas que declaram applier.
#: Rota nova que não esteja aqui reprova — e a saída é escrever a razão, ou
#: passar a usar `gerente_do_daemon`.
_A_MAO_COM_RAZAO: dict[tuple[str, str], Razao] = {
    (
        "daemon.connection",
        "reapply_speaker_after_connect",
    ): Razao(
        appliers=frozenset({"speaker_applier"}),
        motivo=(
            "22/08/2026 — NÃO é rota de ativação: não chama `activate`, chama "
            "`ProfileManager.reapply_speaker_on_connect`, que só reescreve o "
            "volume do alto-falante quando o cabo volta. Um gerente completo "
            "aqui não acrescentaria seção nenhuma (nenhuma outra é consultada) "
            "e daria ao replug o poder de reaplicar o perfil inteiro, que é o "
            "oposto do que a rota existe para fazer. Ver "
            "src/hefesto_dualsense4unix/daemon/connection.py, docstring da "
            "própria função."
        ),
    ),
    (
        "daemon.connection",
        "restore_last_profile",
    ): Razao(
        appliers=frozenset(_NOMES_DE_APPLIER),
        motivo=(
            "22/08/2026 — declara os SETE nomes e neutraliza DOIS com `None` de "
            "propósito: `mouse_applier=None` (BUG-BOOT-RESTORE-FLIPS-EMULATION-01 "
            "— no boot a emulação vem dos flags persistidos, e o perfil ligando "
            "o mouse por cima matava o gamepad restaurado) e `mode_applier=None` "
            "(FEAT-PROFILE-MODE-01, mesma razão). A fábrica hoje só nomeia o "
            "desvio de `mode`; migrar esta rota pede um `mouse_applier` nomeado "
            "em `gerente_do_daemon` com o porquê no docstring. Território de "
            "outra frente nesta leva — ver o relatório da "
            "A-FÁBRICA-COM-UM-CLIENTE-01."
        ),
    ),
}


def _construcoes() -> list[Construcao]:
    """Toda chamada a ``ProfileManager(...)`` em ``src/``, derivada por AST.

    A função que hospeda a chamada é o ``def`` mais próximo acima dela — é ele
    que dá endereço estável à entrada da tabela. Número de linha apodrece a
    cada edição; nome de função, não.
    """
    achados: list[Construcao] = []
    for arquivo in sorted(_SRC.rglob("*.py")):
        if "__pycache__" in arquivo.parts:
            continue
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))
        partes = arquivo.relative_to(_SRC).with_suffix("").parts
        if partes[-1] == "__init__":
            partes = partes[:-1]
        modulo = ".".join(partes)
        dono: dict[int, str] = {}
        for no in ast.walk(arvore):
            if isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef):
                for filho in ast.walk(no):
                    dono.setdefault(id(filho), no.name)
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            alvo = no.func
            nome = (
                alvo.id
                if isinstance(alvo, ast.Name)
                else alvo.attr
                if isinstance(alvo, ast.Attribute)
                else None
            )
            if nome != "ProfileManager":
                continue
            kwargs = {k.arg for k in no.keywords if k.arg}
            achados.append(
                Construcao(
                    modulo=modulo,
                    funcao=dono.get(id(no), "<módulo>"),
                    linha=no.lineno,
                    appliers=frozenset(kwargs & _NOMES_DE_APPLIER),
                )
            )
    return achados


# ===========================================================================
# E3 — o portão da classe
# ===========================================================================


def test_a_lista_de_appliers_bate_com_o_dataclass() -> None:
    """A régua é o CONSTRUTOR, nunca a tupla que ela mesma confere.

    `62d092a`: a primeira versão do teste iterava `APPLIERS_DO_DAEMON` para
    conferir `APPLIERS_DO_DAEMON` e passava com um par arrancado. A contagem
    independente é o dataclass — quem declara os parâmetros de verdade.

    Mordida: apagar um par de `APPLIERS_DO_DAEMON`.
    """
    do_dataclass = {
        nome
        for nome in inspect.signature(ProfileManager).parameters
        if nome.endswith("_applier")
    }
    assert do_dataclass == set(_NOMES_DE_APPLIER), (
        "o contrato e o construtor discordam. Só no construtor: "
        f"{sorted(do_dataclass - _NOMES_DE_APPLIER)}; só no contrato: "
        f"{sorted(_NOMES_DE_APPLIER - do_dataclass)}.\n"
        "Applier ausente NÃO levanta — a seção é ignorada em silêncio, e é por "
        "isso que a lista precisa ser UMA."
    )


def test_toda_construcao_com_applier_tem_razao_escrita() -> None:
    """A SEXTA ROTA à mão reprova aqui, nomeando arquivo, função e appliers.

    Zero applier é legítimo por construção (a rota não ativa nada). Qualquer
    applier declarado é uma lista à mão, e uma lista à mão é como esta casa
    fabricou a divergência que a sprint mede: `gerente_do_daemon` existe
    justamente para não haver uma segunda.

    Mordida: trocar `gerente_do_daemon(...)` por `ProfileManager(...)` com os
    sete appliers em qualquer rota convertida — ver a saída colada no relatório.
    """
    sem_classificacao = [
        c
        for c in _construcoes()
        if c.appliers and c.chave not in _A_MAO_COM_RAZAO
    ]
    assert not sem_classificacao, (
        "rota montando o `ProfileManager` à mão, SEM razão escrita:\n"
        + "\n".join(
            f"  - {c.endereco}: {sorted(c.appliers)}" for c in sem_classificacao
        )
        + "\n\nUse `hefesto_dualsense4unix.profiles.manager.gerente_do_daemon` — "
        "ela traz os sete appliers de uma fonte só. Se esta rota tem razão "
        "MEDIDA para divergir, a razão vira parâmetro nomeado da fábrica (com o "
        "porquê no docstring) e a rota entra em `_A_MAO_COM_RAZAO` com data e "
        "endereço.\n"
        "Applier ausente NÃO levanta: a seção é ignorada em silêncio."
    )


def test_a_tabela_nao_envelhece_calada() -> None:
    """Rota consertada faz a entrada SOBRAR, e o portão cobra que ela saia.

    É a inversão do `portao_a_casa_sabe_e_o_produto_nao_faz`: a classificação
    é escrita à mão, mas ela é conferida contra a árvore a cada rodada. Sem
    isto a dívida da E1 vira paisagem no dia em que alguém a consertar.

    Mordida: apagar um applier da entrada de
    `daemon.connection::restore_last_profile` sem tocar no produto — a tabela
    passa a dizer seis onde a árvore diz sete, e o portão nomeia a divergência.
    Foi assim que a entrada da `daemon.lifecycle::_reapply_last_profile` foi
    cobrada e apagada em 26/08/2026, quando a E1 fechou.
    """
    por_chave = {c.chave: c for c in _construcoes() if c.appliers}
    problemas: list[str] = []
    for chave, razao in _A_MAO_COM_RAZAO.items():
        viva = por_chave.get(chave)
        if viva is None:
            problemas.append(
                f"  - {chave[0]}::{chave[1]} não existe mais (ou deixou de "
                "declarar applier): APAGUE a entrada."
            )
            continue
        if viva.appliers != razao.appliers:
            problemas.append(
                f"  - {viva.endereco} mudou de forma. A tabela diz "
                f"{sorted(razao.appliers)}; a árvore diz {sorted(viva.appliers)}. "
                "Se a rota foi consertada, APAGUE a entrada; se mudou de razão, "
                "reescreva a razão."
            )
    assert not problemas, (
        "a classificação de `_A_MAO_COM_RAZAO` não bate mais com `src/`:\n"
        + "\n".join(problemas)
    )


def test_toda_rota_que_constroi_o_gerente_esta_viva() -> None:
    """Dívida apontando para módulo morto é paisagem, não dívida.

    Reusa a régua de alcance por grafo de import do
    `portao_a_casa_sabe_e_o_produto_nao_faz` (`61ba2ab`, 22/08/2026) — a única
    peça daquela máquina que responde a uma pergunta deste portão.

    Mordida: apontar uma entrada da tabela para um módulo fora do alcance.
    """
    alcancados = modulos_alcancados()
    mortos = [
        c.endereco
        for c in _construcoes()
        if f"{_PACOTE}.{c.modulo}" not in alcancados
    ]
    assert not mortos, (
        "há construção de `ProfileManager` em módulo que os pontos de entrada "
        "declarados NÃO alcançam:\n  " + "\n  ".join(mortos)
    )


def test_a_razao_e_uma_razao() -> None:
    """Razão curta e sem data é isenção fingindo ser decisão.

    Mordida: encurtar qualquer `motivo` de `_A_MAO_COM_RAZAO`.
    """
    for chave, razao in _A_MAO_COM_RAZAO.items():
        rotulo = f"{chave[0]}::{chave[1]}"
        assert len(razao.motivo) > _RAZAO_MINIMA, (
            f"a razão de {rotulo} tem {len(razao.motivo)} caracteres e não diz "
            "por que esta rota não vem da fábrica."
        )
        assert _DATA.search(razao.motivo), (
            f"a razão de {rotulo} não tem data (DD/MM/AAAA). Sem data ninguém "
            "sabe se ela envelheceu."
        )


def test_a_fabrica_nao_tem_saco_generico() -> None:
    """`**sobrescritas` é a lista à mão de volta, com outro nome.

    Um saco genérico deixa qualquer rota injetar o que quiser sem escrever o
    porquê em lugar nenhum — e o portão acima não veria, porque a construção
    passaria a ser da fábrica. Divergência vira PARÂMETRO NOMEADO.

    Mordida: devolver `**sobrescritas: Any` à assinatura de `gerente_do_daemon`.
    """
    parametros = inspect.signature(gerente_do_daemon).parameters
    genericos = [
        nome
        for nome, p in parametros.items()
        if p.kind is inspect.Parameter.VAR_KEYWORD
    ]
    assert not genericos, (
        f"`gerente_do_daemon` voltou a aceitar {genericos} — um saco genérico "
        "ao lado da lista é a lista à mão de volta. Divergência medida vira "
        "parâmetro NOMEADO, com o porquê no docstring."
    )
    desvios = sorted(set(parametros) - {"daemon", "controller", "store"})
    assert desvios == ["mode_applier"], (
        f"os desvios declarados da fábrica mudaram: {desvios}. Cada um precisa "
        "do porquê MEDIDO no docstring de `gerente_do_daemon` — senão o "
        "parâmetro vira o saco genérico com um nome."
    )


# ===========================================================================
# A fábrica: o que ela injeta, e o único desvio que ela aceita
# ===========================================================================


class _DaemonEspiao:
    """Daemon de bancada com os sete appliers e nada mais.

    O ``store`` é um ``StateStore`` de verdade porque duas das rotas dirigidas
    aqui gravam diagnóstico nele (``_build_diag_window_reader``) — um dublê
    magro derrubaria a rota antes de o gerente nascer, e o teste passaria a
    medir o dublê.
    """

    def __init__(self) -> None:
        self.controller = SimpleNamespace()
        self.store = StateStore()
        self._keyboard_device = None
        for _parametro, atributo in APPLIERS_DO_DAEMON:
            setattr(self, atributo, lambda *a, **k: None)

    def esperado(self) -> dict[str, Any]:
        return {
            parametro: getattr(self, atributo)
            for parametro, atributo in APPLIERS_DO_DAEMON
        }


def test_a_fabrica_entrega_os_sete() -> None:
    """Sem desvio, os sete vêm do daemon — nenhum fica `None` por descuido.

    Mordida: trocar o laço de injeção da fábrica por um `pass`.
    """
    daemon = _DaemonEspiao()
    gerente = gerente_do_daemon(daemon)
    faltando = [
        parametro
        for parametro, esperado in daemon.esperado().items()
        if getattr(gerente, parametro) is not esperado
    ]
    assert not faltando, f"a fábrica não injetou: {faltando}"


def test_mode_applier_explicito_vence_o_daemon() -> None:
    """O desvio da allowlist: a fábrica aceita o embrulho, e ele vence.

    `62d092a` mediu que existe um caso em que o gerente nasce DE PROPÓSITO sem
    o `apply_profile_mode` do daemon — o ramo da allowlist do Steam Input, para
    o Hefesto não disputar o gamepad. Se a fábrica ignorasse o par explícito, a
    cura viraria defeito.

    Mordida: apagar o `if mode_applier is not HERDA_DO_DAEMON` da fábrica.
    """
    daemon = _DaemonEspiao()
    embrulho = lambda *a, **k: "so_a_mascara"  # noqa: E731

    assert gerente_do_daemon(daemon, mode_applier=embrulho).mode_applier is embrulho
    # `None` é pedido EXPLÍCITO ("esta rota não aplica a seção mode"), e a
    # sentinela existe para que ele não seja confundido com "não opinei".
    assert gerente_do_daemon(daemon, mode_applier=None).mode_applier is None
    assert (
        gerente_do_daemon(daemon, mode_applier=HERDA_DO_DAEMON).mode_applier
        is daemon.apply_profile_mode
    )


def test_o_desvio_nao_contamina_as_outras_seis() -> None:
    """Pedir um `mode_applier` próprio não pode custar as outras seções.

    Foi assim que o `mode_applier=None` da allowlist virou defeito por algumas
    horas em 22/08: barrar a seção `mode` inteira levava junto o
    `gamepad_flavor`. Aqui a garantia é mais estreita e mecânica — o desvio de
    UMA seção não apaga as outras.

    Mordida: fazer a fábrica devolver cedo quando `mode_applier` é informado.
    """
    daemon = _DaemonEspiao()
    gerente = gerente_do_daemon(daemon, mode_applier=None)
    for parametro, esperado in daemon.esperado().items():
        if parametro == "mode_applier":
            continue
        assert getattr(gerente, parametro) is esperado, (
            f"{parametro} se perdeu quando a rota pediu um `mode_applier` próprio"
        )


# ===========================================================================
# E2 — as rotas de ativação, dirigidas de verdade
# ===========================================================================


def _sem_ambiente_grafico(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_ensure_display_env` chama `systemctl` — fora daqui."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.autoswitch._ensure_display_env",
        lambda: None,
    )


def _confere(gerente: Any, daemon: _DaemonEspiao, rota: str) -> None:
    faltando = [
        parametro
        for parametro, esperado in daemon.esperado().items()
        if getattr(gerente, parametro) is not esperado
    ]
    assert not faltando, (
        f"a rota {rota} construiu um gerente sem {faltando}.\n"
        "Applier ausente NÃO levanta: a seção é ignorada em silêncio, e o "
        "defeito só aparece no aparelho dela."
    )
    assert gerente.keyboard_device_provider is not None, (
        f"a rota {rota} perdeu o provider lazy do teclado — o gerente nasce "
        "antes de o teclado subir, e capturar a referência congelaria `None`"
    )


def test_rota_ipc_subsystem_recebe_os_sete(monkeypatch: pytest.MonkeyPatch) -> None:
    """`IpcSubsystem.start` — a rota do `profile.switch` pela janela.

    PREÇO DESTE CASO, MEDIDO em 22/08/2026 e declarado aqui porque instrumento
    que finge ver o que não vê é pior que instrumento nenhum: o `ctx` daqui tem
    um atributo `daemon`, e o `DaemonContext` de produção NÃO tem (os campos
    são `controller`, `bus`, `store`, `config`, `executor`). Com um
    `DaemonContext` de verdade, esta rota nasce com os SETE em `None` — antes e
    depois desta leva, porque a lista à mão também fazia `getattr` sobre `None`.
    Isto não é o caminho de boot: `Daemon.run` sobe o IPC por `start_ipc(self)`,
    e é lá que os appliers chegam. O que este caso guarda é a fábrica dentro
    desta rota, para o dia em que ela ganhar um daemon.

    Mordida: trocar a chamada à fábrica por `ProfileManager(...)` sem um
    applier — ver a saída colada no relatório.
    """
    from hefesto_dualsense4unix.daemon import ipc_server as ipc_server_mod
    from hefesto_dualsense4unix.daemon.subsystems.ipc import IpcSubsystem

    capturado: list[Any] = []

    class _ServidorFalso:
        def __init__(self, **kw: Any) -> None:
            capturado.append(kw["profile_manager"])

        async def start(self) -> None:
            return None

    monkeypatch.setattr(ipc_server_mod, "IpcServer", _ServidorFalso)
    daemon = _DaemonEspiao()
    ctx = SimpleNamespace(
        controller=daemon.controller, store=daemon.store, daemon=daemon
    )
    asyncio.run(IpcSubsystem().start(ctx))  # type: ignore[arg-type]

    assert capturado, "a rota não construiu gerente nenhum"
    _confere(capturado[0], daemon, "IpcSubsystem.start")


def test_rota_start_ipc_recebe_os_sete(monkeypatch: pytest.MonkeyPatch) -> None:
    """`start_ipc` — a irmã utilitária, a que o `Daemon` usa direto.

    As DUAS rotas de subida do IPC existem, e é entre irmãs assim que a
    divergência nasce.
    """
    from hefesto_dualsense4unix.daemon import ipc_server as ipc_server_mod
    from hefesto_dualsense4unix.daemon.subsystems.ipc import start_ipc

    capturado: list[Any] = []

    class _ServidorFalso:
        def __init__(self, **kw: Any) -> None:
            capturado.append(kw["profile_manager"])

        async def start(self) -> None:
            return None

    monkeypatch.setattr(ipc_server_mod, "IpcServer", _ServidorFalso)
    daemon = _DaemonEspiao()
    asyncio.run(start_ipc(daemon))  # type: ignore[arg-type]

    assert capturado, "a rota não construiu gerente nenhum"
    _confere(capturado[0], daemon, "start_ipc")


def test_rota_autoswitch_subsystem_recebe_os_sete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AutoswitchSubsystem.start` — a troca de perfil pela janela em foco.

    Mesmo preço declarado em `test_rota_ipc_subsystem_recebe_os_sete`: o `ctx`
    de produção não tem `daemon`, e o boot sobe esta rota por
    `start_autoswitch(self)`.
    """
    from hefesto_dualsense4unix.daemon.subsystems.autoswitch import AutoswitchSubsystem
    from hefesto_dualsense4unix.profiles import autoswitch as autoswitch_mod

    _sem_ambiente_grafico(monkeypatch)
    capturado: list[Any] = []

    class _TrocadorFalso:
        def __init__(self, **kw: Any) -> None:
            capturado.append(kw["manager"])

        def disabled(self) -> bool:
            return True

    monkeypatch.setattr(autoswitch_mod, "AutoSwitcher", _TrocadorFalso)
    daemon = _DaemonEspiao()
    ctx = SimpleNamespace(
        controller=daemon.controller, store=daemon.store, daemon=daemon
    )
    asyncio.run(AutoswitchSubsystem().start(ctx))  # type: ignore[arg-type]

    assert capturado, "a rota não construiu gerente nenhum"
    _confere(capturado[0], daemon, "AutoswitchSubsystem.start")


def test_rota_start_autoswitch_recebe_os_sete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`start_autoswitch` — a irmã utilitária do autoswitch."""
    from hefesto_dualsense4unix.daemon.subsystems.autoswitch import start_autoswitch
    from hefesto_dualsense4unix.profiles import autoswitch as autoswitch_mod

    _sem_ambiente_grafico(monkeypatch)
    capturado: list[Any] = []

    class _TrocadorFalso:
        def __init__(self, **kw: Any) -> None:
            capturado.append(kw["manager"])

        def disabled(self) -> bool:
            return True

    monkeypatch.setattr(autoswitch_mod, "AutoSwitcher", _TrocadorFalso)
    daemon = _DaemonEspiao()
    asyncio.run(start_autoswitch(daemon))  # type: ignore[arg-type]

    assert capturado, "a rota não construiu gerente nenhum"
    _confere(capturado[0], daemon, "start_autoswitch")


def test_rota_do_ciclo_por_hotkey_recebe_os_sete() -> None:
    """PS+D-pad — o gesto que ela usa DENTRO do jogo, com o controle na mão.

    O gerente desta rota é local ao `_cycle`; quem o entrega é o
    `_run_blocking(manager.list_profiles)`, e é pelo `__self__` do método
    ligado que o teste o alcança — sem tocar na linha de construção.
    """
    from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
        build_profile_cycle_callback,
    )

    capturado: list[Any] = []

    class _DaemonComCiclo(_DaemonEspiao):
        def __init__(self) -> None:
            super().__init__()
            self.store.set_native_mode_active(False)

        async def _run_blocking(self, fn: Any, *args: Any) -> Any:
            dono = getattr(fn, "__self__", None)
            if dono is not None:
                capturado.append(dono)
            # Uma lista com menos de dois perfis encerra o ciclo logo em
            # seguida — o que interessa aqui já foi construído.
            return []

    daemon = _DaemonComCiclo()
    asyncio.run(build_profile_cycle_callback(daemon, 1)())  # type: ignore[arg-type]

    assert capturado, "a rota não construiu gerente nenhum"
    _confere(capturado[0], daemon, "build_profile_cycle_callback")


def test_rota_do_lancamento_mantem_o_desvio_da_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O jogo na allowlist do Steam Input não pode ter a seção `mode` disputada.

    É a divergência LEGÍTIMA que a E2 tinha de preservar: fora da allowlist o
    `mode_applier` é o do daemon; dentro, é o embrulho que barra o `kind` e
    deixa a máscara passar. As outras seis seções entram nos dois casos.

    Mordida: apagar o ramo `if na_allowlist` do `_ativar_o_perfil_do_lancamento`.
    """
    from hefesto_dualsense4unix.daemon import launch_env as le

    capturados: list[dict[str, Any]] = []

    class _GerenteFalso:
        def activate(self, *a: Any, **k: Any) -> None:
            return None

    daemon = _DaemonEspiao()

    def _fabrica_espia(_daemon: Any, **kw: Any) -> Any:
        capturados.append(kw)
        return _GerenteFalso()

    monkeypatch.setattr(
        "hefesto_dualsense4unix.profiles.manager.gerente_do_daemon", _fabrica_espia
    )
    perfil = SimpleNamespace(name="sackboy")

    le._ativar_o_perfil_do_lancamento(daemon, perfil, appid=1, na_allowlist=False)  # type: ignore[arg-type]
    le._ativar_o_perfil_do_lancamento(daemon, perfil, appid=1, na_allowlist=True)  # type: ignore[arg-type]

    fora, dentro = capturados
    assert "mode_applier" not in fora, (
        "fora da allowlist a rota não tem opinião sobre a seção `mode` — quem "
        f"a resolve é a fábrica. Veio {fora.get('mode_applier')!r}"
    )
    assert callable(dentro.get("mode_applier")), (
        "na allowlist o `mode_applier` tem de ser o EMBRULHO. `None` está "
        "refutado desde 22/08/2026: barrava junto o `gamepad_flavor`, que não é "
        f"disputa nenhuma. Veio {dentro.get('mode_applier')!r}"
    )


# ===========================================================================
# E1 — a saída do Modo Nativo, e a lápide que não pode envelhecer calada
# ===========================================================================


def test_sair_do_modo_nativo_devolve_a_vibracao_ao_jogo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A prova pelo EFEITO, não pela construção.

    O caso é o dela: em Modo Nativo o controle está solto para o jogo; ela testa
    os motores pela aba Rumble (o "Aplicar" FIXA a vibração em
    `config.rumble_active`) e desliga o Modo Nativo. O perfil é reaplicado, e
    `rumble.passthrough=True` — o default de TODO perfil — manda soltar a
    vibração de volta para o jogo.

    Sem o applier a fixação continua de pé e `apply_game_rumble` ignora o FF do
    jogo: é a segunda metade do *"testei os motores e o jogo não vibra"*.
    """
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.profiles import loader as loader_module
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import (
        LedsConfig,
        MatchCriteria,
        Profile,
        TriggerConfig,
        TriggersConfig,
    )
    from hefesto_dualsense4unix.testing import FakeController

    alvo = tmp_path / "profiles"
    alvo.mkdir()
    monkeypatch.setattr(
        loader_module,
        "profiles_dir",
        lambda ensure=False: alvo,
    )

    daemon = Daemon(controller=FakeController(), config=DaemonConfig())
    save_profile(
        Profile(
            name="sackboy_nativo",
            match=MatchCriteria(window_class=["steam_app_1599660"]),
            priority=10,
            triggers=TriggersConfig(
                left=TriggerConfig(mode="Off"), right=TriggerConfig(mode="Off")
            ),
            leds=LedsConfig(lightbar=(10, 20, 30)),
        )
    )
    daemon.store.set_active_profile("sackboy_nativo")
    # O "Aplicar" da aba Rumble, com o Modo Nativo ligado.
    daemon.config.rumble_active = (128, 200)
    daemon.config.rumble_active_uniq = None

    daemon._reapply_last_profile()

    assert daemon.config.rumble_active is None, (
        "a vibração continuou FIXADA depois de sair do Modo Nativo — o perfil "
        "pede `rumble.passthrough=True` e a seção foi ignorada em silêncio, "
        "porque a rota nasceu sem o `rumble_passthrough_applier`."
    )
