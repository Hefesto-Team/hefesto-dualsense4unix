"""ONDA0-Z5/T4 — `connected` não se escreve à mão fora dos três handlers.

O defeito que este portão fecha: F6 nasceu de QUATRO lugares escrevendo
"tem controle conectado?" com respostas diferentes (§2.2 da ONDA0-Z5). T1
fechou a causa (a escrita zumbi no laço de poll); este portão fecha a
RECORRÊNCIA — se um quinto handler nascer publicando `"connected":` direto,
sem passar pelas duas fontes já auditadas (`snap.controller`/`_last_state`,
que T1 mantém honestas; ou `describe_controllers`/`is_connected()`, que já
acertava), a próxima pessoa reintroduz a mesma doença sem perceber.

A régua é AST, não grep: varre `ast.Dict` e reprova toda ESCRITA (chave de
dict literal) do nome `"connected"` fora da lista de funções conhecidas.
LEITURA (`.get("connected")`, subscrição) nunca é escrita — é o que separa
os `:540`/`:995`/`:2381`/`:3784` (leem) dos `:1908`/`:2244`/`:3768`
(publicam), medidos na sprint.
"""
from __future__ import annotations

import ast
from pathlib import Path

# Os três handlers que já foram auditados nesta sprint — cada um com a
# derivação certa para a fonte que usa (ver notas ONDA0-Z5/T1 e T2 em
# `daemon/ipc_handlers.py`, junto de cada ocorrência).
_HANDLERS_QUE_PODEM_ESCREVER_CONNECTED = frozenset(
    {
        "_handle_daemon_status",
        "_handle_daemon_state_full",
        "_handle_controller_list",
    }
)

_IPC_HANDLERS_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "hefesto_dualsense4unix"
    / "daemon"
    / "ipc_handlers.py"
)


class _VisitanteDeEscritasDeConnected(ast.NodeVisitor):
    """Acumula (função, linha) para toda chave de dict literal `"connected"`.

    Só entra em `Dict` — `params.get("connected")` e `entry["connected"]`
    fora de um literal não passam por `visit_Dict`, então são LEITURA e
    nunca aparecem aqui.
    """

    def __init__(self) -> None:
        self.violacoes: list[tuple[str, int]] = []
        self._pilha_de_funcoes: list[str] = []

    def _visitar_funcao(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._pilha_de_funcoes.append(node.name)
        self.generic_visit(node)
        self._pilha_de_funcoes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visitar_funcao(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visitar_funcao(node)

    def visit_Dict(self, node: ast.Dict) -> None:
        nome_atual = self._pilha_de_funcoes[-1] if self._pilha_de_funcoes else "<módulo>"
        for chave in node.keys:
            if (
                isinstance(chave, ast.Constant)
                and chave.value == "connected"
                and nome_atual not in _HANDLERS_QUE_PODEM_ESCREVER_CONNECTED
            ):
                self.violacoes.append((nome_atual, chave.lineno))
        self.generic_visit(node)


def escritas_de_connected_fora_da_lista(source: str) -> list[tuple[str, int]]:
    """A régua do portão — devolve `[(função, linha), ...]` das violações."""
    arvore = ast.parse(source)
    visitante = _VisitanteDeEscritasDeConnected()
    visitante.visit(arvore)
    return visitante.violacoes


# --- o aceite, contra a árvore de verdade --------------------------------


def test_hoje_so_os_tres_handlers_conhecidos_escrevem_connected() -> None:
    fonte = _IPC_HANDLERS_PATH.read_text(encoding="utf-8")
    violacoes = escritas_de_connected_fora_da_lista(fonte)
    assert violacoes == [], (
        f"'connected' publicado fora dos três handlers auditados: {violacoes} "
        "— nova rota de F6 nascendo sem a derivação certa"
    )


# --- a mordida: régua tem de RECUSAR e tem de ACEITAR --------------------


def test_mordida_um_quarto_handler_publicando_connected_reprova_nomeando() -> None:
    fonte = (
        "async def _handle_um_quinto_qualquer(self, params):\n"
        '    return {"connected": True}\n'
    )
    violacoes = escritas_de_connected_fora_da_lista(fonte)
    assert violacoes == [("_handle_um_quinto_qualquer", 2)], (
        "o portão tem de nomear a FUNÇÃO e a LINHA de quem escreveu à mão"
    )


def test_mordida_uma_leitura_de_connected_nao_reprova() -> None:
    fonte = (
        "async def _handle_um_quinto_qualquer(self, params):\n"
        '    if params.get("connected"):\n'
        '        pass\n'
        "    entry: dict = {}\n"
        '    if entry.get("connected"):\n'
        "        pass\n"
        '    return {"status": "ok"}\n'
    )
    violacoes = escritas_de_connected_fora_da_lista(fonte)
    assert violacoes == [], (
        "leitura (.get) não é escrita — o portão que reprova as duas coisas "
        "não separa nada (ver COMO-EXECUTAR-UMA-SPRINT.md §4)"
    )
