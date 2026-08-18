"""Documento que afirma um NÚMERO do código tem de contar do código.

Sprint DOC-VERDADE-02, entregas E3 e E7. As duas mentiras que estes testes
travam nasceram do mesmo jeito, e vale escrever por quê:

  - **E7**, `DaemonConfig`: três páginas afirmavam "o daemon o constrói com três
    parâmetros só (`poll_hz`, `auto_reconnect`, `ps_long_press_ms`)". Era
    verdade quando foi escrito. Em 29/07 a EMULACAO-NO-JOGO-01 acrescentou
    `keyboard_emulation_enabled` — o campo que desliga o teclado emulado dentro
    da partida — e as três frases ficaram falsas no mesmo instante, sem que
    ninguém tocasse nelas. A ironia é que são as páginas mais HONESTAS do
    projeto: elas erram por serem específicas, que é o oposto do defeito das
    outras.

  - **E3**, o socket: o mesmo caminho tinha três grafias na documentação, e a
    do documento canônico era uma das erradas. A cura não é digitar o caminho
    certo — um caminho digitado à mão volta a divergir na próxima mudança de
    `utils/xdg_paths.py`, que foi exatamente como ele divergiu da primeira vez.

Por isso nenhum destes testes compara documento com documento. Todos derivam o
fato do CÓDIGO — por AST, sem importar o pacote onde dá — e cobram que o
documento diga o mesmo. A mordida é essa: acrescentar um quinto parâmetro ao
`DaemonConfig`, ou trocar `IPC_SOCKET_DEFAULT_NAME`, deixa estes testes
VERMELHOS enquanto os documentos não acompanharem.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
DAEMON_MAIN = RAIZ / "src" / "hefesto_dualsense4unix" / "daemon" / "main.py"
XDG_PATHS = RAIZ / "src" / "hefesto_dualsense4unix" / "utils" / "xdg_paths.py"

#: Numeral por extenso, que é como a prosa desta casa escreve contagem pequena.
POR_EXTENSO = {
    1: "um",
    2: "dois",
    3: "três",
    4: "quatro",
    5: "cinco",
    6: "seis",
    7: "sete",
    8: "oito",
    9: "nove",
    10: "dez",
}

#: As páginas que afirmam a contagem de parâmetros do `DaemonConfig`.
#:
#: O `README.md` entrou em 01/08, fechando a isenção de processo que o deixara
#: de fora: ele afirmava a MESMA frase e continuava dizendo "três parâmetros"
#: porque pertencia a outro agente na leva daquele dia. Ele é a página de
#: entrada do projeto — deixá-lo fora era guardar as três páginas internas e
#: soltar a única que quase todo mundo lê.
PAGINAS_DA_CONTAGEM = (
    "README.md",
    "docs/usage/metrics.md",
    "docs/adr/016-prometheus-metrics.md",
)

#: A página que afirma quais variáveis de ambiente o daemon lê na subida.
PAGINA_DAS_ENVS = "docs/usage/hotkeys.md"

#: O documento canônico do protocolo, que precisa carregar o caminho real.
PROTOCOLO_IPC = "docs/protocol/ipc-unix-socket.md"

#: A grafia legada do socket: layout curto, de antes do projeto ser renomeado.
#: Ela não pode sobreviver em documento que ENSINA. Em ADR ela sobrevive de
#: propósito — não se reescreve decisão tomada — desde que o arquivo tenha a
#: nota de verificação datada dizendo o que caducou.
GRAFIA_LEGADA = "XDG_RUNTIME_DIR/hefesto/"

_NOTA_DE_VERIFICACAO = re.compile(r"^#{1,6}\s*Nota de verifica", re.IGNORECASE)


def _chamada_do_daemon_config() -> ast.Call:
    """A chamada `DaemonConfig(...)` de `daemon/main.py`, lida por AST.

    Ler o código-fonte em vez de importar o módulo é deliberado: importar
    `daemon.main` arrasta o daemon inteiro, e um `ImportError` de dependência
    de sistema transformaria este teste num `error` de coleta — o modo de falha
    que esta casa já pagou caro (um módulo que some da coleta some calado).
    """
    arvore = ast.parse(DAEMON_MAIN.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if (
            isinstance(no, ast.Call)
            and isinstance(no.func, ast.Name)
            and no.func.id == "DaemonConfig"
        ):
            return no
    pytest.fail(
        "não achei a chamada `DaemonConfig(...)` em daemon/main.py — "
        "a premissa destes testes mudou e eles precisam ser reescritos"
    )


def _campos_do_daemon_config() -> list[str]:
    """Os nomes dos argumentos nomeados passados ao `DaemonConfig`."""
    return [kw.arg for kw in _chamada_do_daemon_config().keywords if kw.arg]


def _envs_lidas_na_subida() -> set[str]:
    """Todo literal `HEFESTO_*` passado a `os.getenv` em `daemon/main.py`."""
    arvore = ast.parse(DAEMON_MAIN.read_text(encoding="utf-8"))
    nomes: set[str] = set()
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        e_getenv = isinstance(alvo, ast.Attribute) and alvo.attr == "getenv"
        if not e_getenv or not no.args:
            continue
        primeiro = no.args[0]
        e_literal = isinstance(primeiro, ast.Constant) and isinstance(
            primeiro.value, str
        )
        if e_literal and primeiro.value.startswith("HEFESTO_"):
            nomes.add(primeiro.value)
    return nomes


def _constante_de_texto(fonte: Path, nome: str) -> str:
    """Lê uma constante de módulo cujo valor é um literal de texto."""
    arvore = ast.parse(fonte.read_text(encoding="utf-8"))
    for no in arvore.body:
        if not isinstance(no, ast.Assign):
            continue
        for alvo in no.targets:
            if (
                isinstance(alvo, ast.Name)
                and alvo.id == nome
                and isinstance(no.value, ast.Constant)
                and isinstance(no.value.value, str)
            ):
                return no.value.value
    pytest.fail(f"constante {nome} não encontrada em {fonte.name}")


def _texto(relativo: str) -> str:
    return (RAIZ / relativo).read_text(encoding="utf-8")


def _linhas_antes_da_nota(relativo: str) -> list[tuple[int, str]]:
    """As linhas do documento ANTES do primeiro cabeçalho de nota datada.

    O que vem depois da nota é registro de correção: ali o valor caducado é
    citado de propósito, e é a informação inteira da nota.
    """
    linhas = _texto(relativo).splitlines()
    fim = len(linhas)
    for indice, linha in enumerate(linhas):
        if _NOTA_DE_VERIFICACAO.match(linha):
            fim = indice
            break
    return list(enumerate(linhas[:fim], start=1))


# ---------------------------------------------------------------------------
# E7 -- a contagem de parâmetros do DaemonConfig.
# ---------------------------------------------------------------------------


def test_o_daemon_config_e_construido_com_quatro_parametros() -> None:
    """Ancora a premissa: se o número mudar, mudou de propósito.

    Este teste não guarda documento nenhum. Ele existe para que a mudança de
    contagem apareça AQUI, com nome e sobrenome, em vez de aparecer como três
    falhas confusas nos testes de documento abaixo.
    """
    campos = _campos_do_daemon_config()

    assert campos == [
        "poll_hz",
        "auto_reconnect",
        "ps_long_press_ms",
        "keyboard_emulation_enabled",
    ], (
        "a construção do DaemonConfig em daemon/main.py mudou. Isso é legítimo "
        "— mas as páginas que afirmam a contagem precisam mudar junto: "
        f"{', '.join(PAGINAS_DA_CONTAGEM)}."
    )


@pytest.mark.parametrize("documento", PAGINAS_DA_CONTAGEM)
def test_a_pagina_afirma_a_contagem_certa_de_parametros(documento: str) -> None:
    """A frase "com N parâmetros" tem de bater com o código de hoje.

    A busca é no documento INTEIRO, nota inclusive: numa ADR a correção mora
    justamente na nota datada, e exigi-la no corpo seria exigir que a decisão
    original fosse reescrita — o oposto do que esta casa faz.
    """
    campos = _campos_do_daemon_config()
    esperado = f"{POR_EXTENSO[len(campos)]} parâmetros"

    assert esperado in _texto(documento), (
        f"{documento} não afirma '{esperado}'. O `DaemonConfig` é construído com "
        f"{len(campos)} argumentos em daemon/main.py ({', '.join(campos)}); "
        "a página precisa dizer o mesmo número."
    )


@pytest.mark.parametrize("documento", PAGINAS_DA_CONTAGEM)
def test_a_pagina_nomeia_todos_os_parametros(documento: str) -> None:
    """Contar certo e listar errado seria a mesma mentira com outra roupa.

    É por isto que um teste que só procurasse a palavra "quatro" não morderia:
    passaria com a lista antiga de três nomes ao lado do número novo.
    """
    campos = _campos_do_daemon_config()
    texto = _texto(documento)
    faltando = [campo for campo in campos if f"`{campo}`" not in texto]

    assert not faltando, (
        f"{documento} afirma a contagem mas não nomeia: {', '.join(faltando)}. "
        "O campo existe na construção do DaemonConfig em daemon/main.py."
    )


def test_nenhuma_pagina_viva_repete_a_lista_antiga_de_tres() -> None:
    """A enumeração de 26/07 não pode voltar fora de nota datada.

    `três parâmetros` era verdade até 29/07. Depois disso, encontrar essa frase
    fora de uma nota de verificação significa que alguém reescreveu para trás.
    """
    for documento in PAGINAS_DA_CONTAGEM:
        for numero, linha in _linhas_antes_da_nota(documento):
            assert "três parâmetros" not in linha, (
                f"{documento}:{numero} voltou a dizer 'três parâmetros' fora de "
                "nota de verificação datada."
            )


# ---------------------------------------------------------------------------
# E7 -- as variáveis de ambiente lidas na subida do daemon.
# ---------------------------------------------------------------------------


def test_hotkeys_lista_todas_as_variaveis_lidas_na_subida() -> None:
    """`hotkeys.md` omitia a quarta variável, e a quarta é a que dói.

    `HEFESTO_DUALSENSE4UNIX_KEYBOARD_EMULATION` nasceu porque o R1 do mapa
    default emitia Alt+Tab DENTRO da partida dela. A página que ensina hotkeys
    era justamente onde essa variável precisava estar.
    """
    envs = _envs_lidas_na_subida()
    texto = _texto(PAGINA_DAS_ENVS)
    faltando = sorted(nome for nome in envs if f"`{nome}`" not in texto)

    assert not faltando, (
        f"{PAGINA_DAS_ENVS} não cita: {', '.join(faltando)}. São lidas por "
        "`os.getenv` em daemon/main.py, na subida do daemon."
    )


def test_hotkeys_afirma_a_contagem_certa_de_variaveis() -> None:
    """A mordida escrita na sprint: uma env nova sem tocar o documento reprova."""
    envs = _envs_lidas_na_subida()
    esperado = f"hoje são {POR_EXTENSO[len(envs)]}"

    assert esperado in _texto(PAGINA_DAS_ENVS), (
        f"{PAGINA_DAS_ENVS} não afirma '{esperado}'. `daemon/main.py` lê "
        f"{len(envs)} variáveis na subida: {', '.join(sorted(envs))}."
    )


# ---------------------------------------------------------------------------
# E3 -- o caminho do socket, derivado de utils/xdg_paths.py.
# ---------------------------------------------------------------------------


def test_o_protocolo_carrega_o_caminho_canonico_do_socket() -> None:
    """O documento canônico tem de conter o caminho que o código monta.

    Montado aqui do mesmo jeito que `ipc_socket_path()` monta: o diretório de
    `runtime_dir()` (que é `$XDG_RUNTIME_DIR` + o nome do projeto) mais o
    nome-base de `IPC_SOCKET_DEFAULT_NAME`. Trocar a constante no código deixa
    este teste VERMELHO enquanto o documento não acompanhar — que é exatamente
    a regressão que a casa quer que doa.
    """
    nome_base = _constante_de_texto(XDG_PATHS, "IPC_SOCKET_DEFAULT_NAME")
    canonico = f"$XDG_RUNTIME_DIR/hefesto-dualsense4unix/{nome_base}"

    assert canonico in _texto(PROTOCOLO_IPC), (
        f"{PROTOCOLO_IPC} não traz o caminho canônico `{canonico}`, derivado de "
        "utils/xdg_paths.py (`runtime_dir()` + `IPC_SOCKET_DEFAULT_NAME`)."
    )


def test_o_protocolo_nomeia_a_variavel_de_isolamento_certa() -> None:
    """A variável real é a longa; o ADR-010 anunciava a curta, que não existe."""
    env = _constante_de_texto(XDG_PATHS, "IPC_SOCKET_ENV_VAR")

    assert f"`{env}`" in _texto(PROTOCOLO_IPC), (
        f"{PROTOCOLO_IPC} não cita `{env}` (constante `IPC_SOCKET_ENV_VAR` em "
        "utils/xdg_paths.py), que é a única variável que troca o nome-base."
    )


def test_o_protocolo_nomeia_o_socket_do_modo_fake() -> None:
    """O modo fake é a armadilha declarada da E3.

    `ipc_socket_name()` troca o nome-base quando `HEFESTO_DUALSENSE4UNIX_FAKE=1`,
    e um documento que só mostrasse o caminho de produção esconderia o socket
    que o daemon falso realmente abre — o mesmo descompasso que já produziu um
    "Conectado Via USB" fantasma na janela (BUG-FAKE-SOCKET-SYNC-01).
    """
    fake = _constante_de_texto(XDG_PATHS, "IPC_SOCKET_FAKE_NAME")

    assert fake in _texto(PROTOCOLO_IPC), (
        f"{PROTOCOLO_IPC} não cita `{fake}` (`IPC_SOCKET_FAKE_NAME`), o "
        "nome-base que o modo fake usa."
    )


def test_nenhum_documento_que_ensina_cita_a_grafia_legada_do_socket() -> None:
    """`$XDG_RUNTIME_DIR/hefesto/` não cola em terminal nenhum desde a renomeação.

    Em ADR a grafia sobrevive de propósito, na decisão original — não se
    reescreve história. O que ela não pode é sobreviver ANTES da nota de
    verificação num documento sem nota nenhuma, nem em `docs/usage/` ou
    `docs/protocol/`, que são receita para copiar.
    """
    alvos = sorted(
        p.relative_to(RAIZ).as_posix()
        for p in list((RAIZ / "docs" / "usage").rglob("*.md"))
        + list((RAIZ / "docs" / "protocol").rglob("*.md"))
    )
    culpados = [
        f"{alvo}:{numero}"
        for alvo in alvos
        for numero, linha in enumerate(_texto(alvo).splitlines(), start=1)
        if GRAFIA_LEGADA in linha
    ]

    assert not culpados, (
        "grafia legada do socket em documento que ensina: "
        f"{', '.join(culpados)}. O caminho real vem de `ipc_socket_path()`."
    )


def test_o_adr_do_socket_tem_nota_datada_corrigindo_a_grafia_legada() -> None:
    """Onde a grafia legada fica, a nota que a desmente tem de estar junto."""
    adr = "docs/adr/010-ipc-socket-liveness-probe.md"
    texto = _texto(adr)
    nome_base = _constante_de_texto(XDG_PATHS, "IPC_SOCKET_DEFAULT_NAME")
    env = _constante_de_texto(XDG_PATHS, "IPC_SOCKET_ENV_VAR")

    assert GRAFIA_LEGADA in texto, (
        f"{adr} não cita mais a grafia legada — se a decisão original foi "
        "reescrita, este teste perdeu o objeto e a história, junto."
    )
    linhas = texto.splitlines()
    tem_nota = any(_NOTA_DE_VERIFICACAO.match(linha) for linha in linhas)
    assert tem_nota, f"{adr} cita a grafia legada e não tem nota de verificação."

    inicio = next(
        i for i, linha in enumerate(linhas) if _NOTA_DE_VERIFICACAO.match(linha)
    )
    depois_da_nota = "\n".join(linhas[inicio:])
    for esperado in (nome_base, env, "hefesto-dualsense4unix/"):
        assert esperado in depois_da_nota, (
            f"a nota de verificação de {adr} não nomeia `{esperado}` — sem isso "
            "ela não diz o que o leitor deve usar no lugar."
        )
