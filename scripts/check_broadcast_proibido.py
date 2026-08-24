#!/usr/bin/env python3
"""BROADCAST-PROIBIDO-01 (Z3-8, 24/08/2026): reprova fan-out sem escopo.

A régua, numa frase: **toda função que escreve output em MAIS DE UM destino
consulta `_resolver_escopo`/`alvo_de_output_ausente`/`get_output_target_uniq`
ANTES, ou está na lista de exceções deliberadas com justificativa escrita.**

O defeito que este portão existe para impedir de voltar uma TERCEIRA vez: a
ABAS-06 (25/07) curou o broadcast na tela; o F4 (23/08) curou os três helpers
do backend (`_for_each`/`_for_each_com_key`/`_for_each_led`); e o MESMO
formato — "alvo escolhido, escrita em TODOS mesmo assim" — voltou por DUAS
portas diferentes, na MESMA árvore (ver
`docs/process/sprints/2026-08-24-ONDA0-Z3-BROADCAST-PROIBIDO-01-o-pulso-do-jogador-2-na-mao-dos-outros.md`,
§2.1): `daemon/ipc_handlers.py::_registrar_em_todos` (§2.1(b), a Regra 1
abaixo) e `daemon/subsystems/gamepad.py::apply_game_rumble` (§2.1(d), a
Regra 2). Sem portão, a quinta porta é só questão de tempo.

Como a varredura enxerga uma "escrita em mais de um destino" — DUAS regras
----------------------------------------------------------------------------
Puramente estrutural (AST, sem executar nada, sem hardware). As duas regras
olham só o CORPO DIRETO de cada função/método (não descem em `def`/`lambda`
aninhados — são escopos próprios, analisados como funções à parte quando o
`walk` do módulo chegar neles).

**Regra 1 — fan-out por `for` sem guardião** (`_achado_regra1_...`):

1. **FAN-OUT**: o corpo tem um `for` cujo iterável bate com um dos padrões de
   `_FONTES_DE_MUITOS` (uma fonte que enumera MAIS de um controle —
   `.items()`/`.values()` de algo com "handle(s)" no nome,
   `_uniqs_conectados()`, `describe_controllers()`, ou uma variável local
   atribuída a partir de uma dessas fontes na MESMA função) — **e** o corpo
   do `for` contém uma chamada cujo nome está em `_VERBOS_DE_ESCRITA`.
2. **CONSULTOU**: em QUALQUER linha ANTES do primeiro `for` de fan-out, uma
   chamada a um `_GUARDIOES` — direta OU pelo idioma defensivo desta casa,
   ``getattr(obj, "nome_do_guardiao", padrão)`` (é assim que praticamente
   todo chamador de produção pergunta: ver `_e_chamada_de_guardiao`).
3. FAN-OUT e NÃO CONSULTOU é reprovação.

**Regra 2 — degrada sem descartar** (`_achado_regra2_...`), a forma que a
Regra 1 não vê porque não há `for` nenhum — o fan-out mora DENTRO de uma
chamada só (`controller.set_rumble`, já corrigida pelo F4 para escrever
segundo o SELETOR global, não segundo o pedido desta função):

1. A função tem um parâmetro chamado exatamente `target_uniq`.
2. Existe um `if` cujo teste menciona `target_uniq` e `None`, com uma
   tentativa POR-UNIQ dentro (convenção desta casa: nome termina em `_for` —
   direto ou por `getattr`) recebendo `target_uniq` como argumento.
3. DEPOIS desse `if` (mesmo nível, linha maior), existe uma chamada cujo
   nome está em `_VERBOS_DE_QUEDA_PARA_BROADCAST` e que NÃO leva
   `target_uniq` entre os argumentos — ou seja, se a tentativa de (2) não
   `return`ou, a execução cai numa escrita que ignora o alvo que foi pedido.

4. Nas duas regras: **é reprovação** — a menos que `(arquivo, qualname)`
   esteja em `_EXCECOES_DELIBERADAS` com justificativa não-vazia.

O que esta régua NÃO pega, dito na cara
----------------------------------------
É estrutural, não semântica: uma função que chama uma OUTRA função que já é
FAN-OUT (por exemplo, `_handle_led_set` chamando `_registrar_em_todos`) não é
ela mesma marcada FAN-OUT — quem escreve o loop/a queda é quem o portão
cobra. Um fan-out por caminho que não é `for` NEM o padrão exato da Regra 2
(recursão, `map()`, `asyncio.gather`, um parâmetro com outro nome) não é
pego por esta versão — ver §2.4 da sprint, "NÃO VERIFICADO". Isto mede os
DOIS formatos que já apareceram nesta casa, não todo fan-out imaginável.
"""
from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path

# --- o vocabulário ---------------------------------------------------------

#: Quem já pergunta "que escopo é este" antes de escrever. Consultar QUALQUER
#: um destes antes do laço de fan-out livra a função da reprovação.
_GUARDIOES = frozenset(
    {
        "_resolver_escopo",
        "alvo_de_output_ausente",
        "get_output_target_uniq",
    }
)

#: Chamadas que, dentro de um `for` sobre muitos, são a ESCRITA em si —
#: física (o handle do pydualsense) ou de registro (o override por-uniq que
#: sobrevive ao reassert). Lista fechada de propósito: um verbo genérico
#: demais (`set`, `apply`) acusaria meio código-fonte à toa.
_VERBOS_DE_ESCRITA = frozenset(
    {
        "apply_output_for",
        "apply_for",
        "setLeftMotor",
        "setRightMotor",
        "setColorI",
        "set_rgb",
        "setMicrophoneLED",
        "setForce",
        "set_rumble_for",
    }
)

#: Padrões (substring do `ast.unparse` do iterável) que dizem "isto enumera
#: MAIS DE UM controle". `handle`/`handles` no nome cobre `self._handles`,
#: `handles.items()`, um parâmetro `handles: dict[str, Any]` etc.
_FONTES_DE_MUITOS = (
    "handles",
    "_uniqs_conectados(",
    "describe_controllers(",
)


@dataclass(frozen=True)
class _Excecao:
    justificativa: str


#: A SEGUNDA forma do mesmo defeito (Regra 2 — "degrada sem descartar"), do
#: §2.1(d) da sprint: uma função com parâmetro ``target_uniq`` tenta uma
#: chamada POR-UNIQ (convenção desta casa: nome termina em ``_for`` —
#: ``set_rumble_for``, ``set_game_trigger_for``...) guardada por
#: ``target_uniq is not None`` e, se a tentativa não devolver antes, CAI numa
#: chamada de escrita GENÉRICA — sem ``target_uniq`` entre os argumentos —
#: que replica em quem quer que o seletor global esteja mirando no momento.
#: É a forma exata de `apply_game_rumble` antes de Z3-1: o rumble do JOGO,
#: pedido para UM jogador, sacode a mesa que o seletor mirar.
_VERBOS_DE_QUEDA_PARA_BROADCAST = frozenset(
    {
        "set_rumble",
        "set_led",
        "set_trigger",
        "set_player_leds",
        "set_mic_led",
    }
)


def _mapa_getattr_local(corpo_direto: list[ast.AST]) -> dict[str, str]:
    """``var = getattr(obj, "nome", padrão)`` -> {"var": "nome"}.

    O idioma desta casa para chamada duck-typed defensiva: quase toda API
    opcional do backend é lida assim, nunca por atributo cru. Sem resolver
    isto, tanto `_GUARDIOES` quanto as duas regras de fan-out ficam cegas
    para o próprio código que elas precisam ler."""
    mapa: dict[str, str] = {}
    for node in corpo_direto:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        alvo = node.targets[0]
        if not isinstance(alvo, ast.Name):
            continue
        valor = node.value
        if (
            isinstance(valor, ast.Call)
            and isinstance(valor.func, ast.Name)
            and valor.func.id == "getattr"
            and len(valor.args) >= 2
            and isinstance(valor.args[1], ast.Constant)
            and isinstance(valor.args[1].value, str)
        ):
            mapa[alvo.id] = valor.args[1].value
    return mapa


def _nome_resolvido(node: ast.Call, mapa_getattr: dict[str, str]) -> str | None:
    """`_nome_chamada`, mas resolvendo uma var local que veio de `getattr`."""
    direto = _nome_chamada(node)
    if direto is not None and direto in mapa_getattr:
        return mapa_getattr[direto]
    return direto


def _args_incluem_nome(node: ast.Call, nome: str) -> bool:
    fontes = list(node.args) + [kw.value for kw in node.keywords]
    return any(isinstance(a, ast.Name) and a.id == nome for a in fontes)


def _achado_regra2_degrada_sem_descartar(
    func: ast.FunctionDef | ast.AsyncFunctionDef, arquivo_rel: str
) -> Achado | None:
    parametros = {a.arg for a in func.args.args} | {a.arg for a in func.args.kwonlyargs}
    if "target_uniq" not in parametros:
        return None

    corpo_direto = list(_SoCorpoDireto(func))
    mapa_getattr = _mapa_getattr_local(corpo_direto)

    linha_da_tentativa: int | None = None
    for node in corpo_direto:
        if not isinstance(node, ast.If):
            continue
        teste_src = _unparse(node.test)
        if "target_uniq" not in teste_src or "None" not in teste_src:
            continue
        tem_tentativa_por_uniq = any(
            isinstance(n, ast.Call)
            and (nome := _nome_resolvido(n, mapa_getattr))
            and nome.endswith("_for")
            and _args_incluem_nome(n, "target_uniq")
            for n in ast.walk(node)
        )
        if not tem_tentativa_por_uniq:
            continue
        # Se este `if` SEMPRE termina em `return`/`raise` (última instrução
        # do corpo dele), a tentativa não pode cair para fora — é o formato
        # da cura (Z3-1): o `if target_uniq is not None:` inteiro devolve
        # antes de chegar ao broadcast. Só quando falta essa garantia é que
        # o que vem DEPOIS do `if` é alcançável mesmo com endereço pedido.
        termina_com_retorno = bool(node.body) and isinstance(
            node.body[-1], (ast.Return, ast.Raise)
        )
        if termina_com_retorno:
            continue
        fim = getattr(node, "end_lineno", node.lineno)
        linha_da_tentativa = fim if linha_da_tentativa is None else max(linha_da_tentativa, fim)

    if linha_da_tentativa is None:
        return None

    for node in corpo_direto:
        if not (isinstance(node, ast.Call) and node.lineno > linha_da_tentativa):
            continue
        nome = _nome_resolvido(node, mapa_getattr)
        if nome not in _VERBOS_DE_QUEDA_PARA_BROADCAST:
            continue
        if _args_incluem_nome(node, "target_uniq"):
            continue  # esta chamada respeita o alvo — não é a queda
        return Achado(arquivo=arquivo_rel, linha=node.lineno, qualname=_qualname(func))
    return None


#: (arquivo relativo a `src/`, qualname) -> justificativa. Cada entrada tem
#: de apontar para uma frase de VERDADE no docstring/comentário da própria
#: função — este dicionário não é a fonte da justificativa, é o ÍNDICE dela.
#: Nasce da batida de C (rodada 0 da Z3) — a varredura completa de fan-out
#: fora de `_resolver_escopo` que a sprint pede em §4.
_EXCECOES_DELIBERADAS: dict[tuple[str, str], _Excecao] = {
    (
        "hefesto_dualsense4unix/core/backend_pydualsense.py",
        "PyDualSenseController.force_rumble_stop",
    ): _Excecao(
        "Docstring do próprio método: 'Broadcast deliberado (ignora o "
        "seletor de alvo): sair de modo para TODO mundo.' — parar os motores "
        "na saída do Modo Nativo/gamepad tem de alcançar TODA a mesa, "
        "porque qualquer um deles pode ter sido deixado vibrando pelo jogo "
        "(HARM-16)."
    ),
}


# --- a varredura -------------------------------------------------------------


def _unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _nome_chamada(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _e_chamada_de_guardiao(node: ast.Call) -> bool:
    """True quando `node` nomeia um `_GUARDIOES`, direto OU pelo idioma
    defensivo desta casa: ``getattr(obj, "nome_do_guardiao", padrão)``. O
    censo (§2.1) mostrou que TODO chamador de produção usa `getattr`
    defensivo, nunca o atributo cru — uma régua que só reconhecesse a
    chamada direta reprovaria o próprio `_registrar_em_todos` já curado."""
    if _nome_chamada(node) in _GUARDIOES:
        return True
    if isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) >= 2:
        segundo = node.args[1]
        if isinstance(segundo, ast.Constant) and segundo.value in _GUARDIOES:
            return True
    return False


def _e_fonte_de_muitos(iteravel_src: str, variaveis_de_muitos: set[str]) -> bool:
    if any(padrao in iteravel_src for padrao in _FONTES_DE_MUITOS):
        return True
    # variável local: `alvos = self._uniqs_conectados()` ... `for alvo in alvos:`
    return iteravel_src in variaveis_de_muitos


def _rastreia_variaveis_de_muitos(corpo: list[ast.stmt]) -> set[str]:
    """Nomes simples atribuídos a partir de uma fonte de `_FONTES_DE_MUITOS`."""
    variaveis: set[str] = set()
    for stmt in corpo:
        if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
            continue
        alvo = stmt.targets[0]
        if not isinstance(alvo, ast.Name):
            continue
        valor_src = _unparse(stmt.value)
        if any(padrao in valor_src for padrao in _FONTES_DE_MUITOS):
            variaveis.add(alvo.id)
    return variaveis


@dataclass(frozen=True)
class Achado:
    arquivo: str
    linha: int
    qualname: str

    def __str__(self) -> str:
        return f"{self.arquivo}:{self.linha}  {self.qualname}"


def _achado_regra1_fanout_sem_guardiao(
    func: ast.FunctionDef | ast.AsyncFunctionDef, arquivo_rel: str
) -> Achado | None:
    """Regra 1: `for` sobre muitos, escreve, e nunca perguntou antes."""
    corpo = func.body
    variaveis_de_muitos = _rastreia_variaveis_de_muitos(corpo)

    primeiro_for_fanout: ast.For | None = None
    corpo_direto = list(_SoCorpoDireto(func))
    for stmt in corpo_direto:
        if isinstance(stmt, ast.For):
            iteravel_src = _unparse(stmt.iter)
            if not _e_fonte_de_muitos(iteravel_src, variaveis_de_muitos):
                continue
            escreve = any(
                isinstance(n, ast.Call) and _nome_chamada(n) in _VERBOS_DE_ESCRITA
                for n in ast.walk(stmt)
            )
            if escreve:
                primeiro_for_fanout = stmt
                break

    if primeiro_for_fanout is None:
        return None

    # CONSULTOU: chamada a um guardião em QUALQUER ponto do corpo direto
    # ANTES da linha do for de fan-out.
    for node in corpo_direto:
        if (
            isinstance(node, ast.Call)
            and node.lineno < primeiro_for_fanout.lineno
            and _e_chamada_de_guardiao(node)
        ):
            return None

    qualname = _qualname(func)
    return Achado(arquivo=arquivo_rel, linha=func.lineno, qualname=qualname)


def _analisa_funcao(
    func: ast.FunctionDef | ast.AsyncFunctionDef, arquivo_rel: str
) -> Achado | None:
    return _achado_regra1_fanout_sem_guardiao(
        func, arquivo_rel
    ) or _achado_regra2_degrada_sem_descartar(func, arquivo_rel)


class _SoCorpoDireto:
    """Iterável de nós do CORPO de `func`, SEM descer em `def`/`lambda`
    aninhados — são escopos próprios, analisados como funções à parte quando
    o `walk` do módulo chegar neles (ver `_funcoes_do_arquivo`)."""

    def __init__(self, func: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._vistos: list[ast.AST] = []
        for stmt in func.body:
            self._vistos.append(stmt)
            self._coleta(stmt)

    def _coleta(self, node: ast.AST) -> None:
        for filho in ast.iter_child_nodes(node):
            if isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue  # escopo próprio — não desce
            self._vistos.append(filho)
            self._coleta(filho)

    def __iter__(self):
        return iter(self._vistos)


def _qualname(func: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    nome = getattr(func, "_broadcast_proibido_qualname", None)
    return nome if isinstance(nome, str) else func.name


def _marca_qualnames(tree: ast.Module) -> None:
    """Prefixa cada função com `Classe.` quando ela é método — um só passo,
    de fora para dentro, sem alterar a AST em outra coisa."""

    def visita(node: ast.AST, prefixo: str) -> None:
        for filho in ast.iter_child_nodes(node):
            if isinstance(filho, ast.ClassDef):
                visita(filho, f"{prefixo}{filho.name}.")
            elif isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef)):
                filho._broadcast_proibido_qualname = f"{prefixo}{filho.name}"  # type: ignore[attr-defined]
                visita(filho, f"{prefixo}{filho.name}.")
            else:
                visita(filho, prefixo)

    visita(tree, "")


def _funcoes_do_arquivo(
    caminho: Path,
) -> list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, str]]:
    try:
        fonte = caminho.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        tree = ast.parse(fonte, filename=str(caminho))
    except SyntaxError:
        return []
    _marca_qualnames(tree)
    achadas: list[tuple[ast.FunctionDef | ast.AsyncFunctionDef, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            achadas.append((node, _qualname(node)))
    return achadas


def varre(raiz_src: Path) -> list[Achado]:
    achados: list[Achado] = []
    for caminho in sorted(raiz_src.rglob("*.py")):
        arquivo_rel = "hefesto_dualsense4unix/" + str(
            caminho.relative_to(raiz_src / "hefesto_dualsense4unix")
        )
        for func, qualname in _funcoes_do_arquivo(caminho):
            achado = _analisa_funcao(func, arquivo_rel)
            if achado is None:
                continue
            if (arquivo_rel, qualname) in _EXCECOES_DELIBERADAS:
                continue
            achados.append(achado)
    return achados


# --- CLI ---------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--raiz",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="raiz do repositório (default: dois níveis acima deste script)",
    )
    args = parser.parse_args(argv)

    raiz_src = (args.raiz / "src").resolve()
    if not raiz_src.is_dir():
        print(f"ERRO: raiz de src inexistente: {raiz_src}")
        return 2

    achados = varre(raiz_src)

    if achados:
        print(f"FALHA: {len(achados)} rota(s) de saída com fan-out sem escopo:")
        for achado in achados:
            print(f"  {achado}")
        print("")
        print(
            "Cada função acima escreve em MAIS DE UM controle (um `for` sobre "
            "handles/uniqs conectados, com uma chamada de escrita dentro) sem "
            "antes perguntar `_resolver_escopo`/`alvo_de_output_ausente`/"
            "`get_output_target_uniq` — é o formato exato do BROADCAST-"
            "PROIBIDO-01 (o pulso do jogador ausente na mão dos outros)."
        )
        print(
            "Resolva o escopo antes de escrever, ou — se o broadcast for "
            "DELIBERADO (sair de um modo para todo mundo, por exemplo) — "
            "acrescente a função a `_EXCECOES_DELIBERADAS` neste script, com "
            "a justificativa escrita."
        )
        return 1

    print(f"OK: nenhuma rota de saída com fan-out sem escopo em {raiz_src}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
