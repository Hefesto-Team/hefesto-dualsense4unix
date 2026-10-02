"""O-DUBLE-NAO-EMPOBRECE-SOZINHO-01 — o dublê que roda o laço de produção"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
LIFECYCLE = RAIZ / "src" / "hefesto_dualsense4unix" / "daemon" / "lifecycle.py"
TESTES = RAIZ / "tests"


def _poll_loop_de(arvore: ast.Module) -> ast.AsyncFunctionDef:
    for no in ast.walk(arvore):
        if isinstance(no, ast.AsyncFunctionDef) and no.name == "_poll_loop":
            return no
    raise AssertionError("não achei o `_poll_loop`")


def _o_while_do_laco(fn: ast.AsyncFunctionDef) -> ast.While:
    """O único `while` do corpo do `_poll_loop`."""
    whiles = [s for s in fn.body if isinstance(s, ast.While)]
    if len(whiles) != 1:
        raise AssertionError(
            f"esperava UM `while` no corpo do `_poll_loop`, achei {len(whiles)}. "
            "Esta régua reparte o laço no gate de conexão e precisa saber qual é "
            "o laço. Reescreva-a antes de seguir."
        )
    return whiles[0]


def _indice_do_gate(laco: ast.While) -> int:
    """A posição, no corpo do `while`, do `if not self.controller.is_connected():`."""
    for i, sentenca in enumerate(laco.body):
        if not isinstance(sentenca, ast.If):
            continue
        if not isinstance(sentenca.test, ast.UnaryOp) or not isinstance(sentenca.test.op, ast.Not):
            continue
        if "is_connected" not in ast.dump(sentenca.test):
            continue
        if sentenca.body and isinstance(sentenca.body[-1], ast.Continue):
            return i
    raise AssertionError(
        "não achei no `_poll_loop` um `if not self.controller.is_connected():` "
        "terminado em `continue`. Ou o gate mudou de forma, ou saiu — e nos dois "
        "casos esta régua precisa ser reescrita antes de voltar a valer."
    )


def _usos_de_self(nos: Iterable[ast.AST]) -> tuple[dict[str, int], set[str]]:
    """`(nome -> primeira linha, quais deles aparecem CHAMADOS)`."""
    usos: dict[str, int] = {}
    chamados: set[str] = set()
    for raiz in nos:
        for no in ast.walk(raiz):
            if (
                isinstance(no, ast.Call)
                and isinstance(no.func, ast.Attribute)
                and isinstance(no.func.value, ast.Name)
                and no.func.value.id == "self"
            ):
                chamados.add(no.func.attr)
            if (
                isinstance(no, ast.Attribute)
                and isinstance(no.value, ast.Name)
                and no.value.id == "self"
                and isinstance(no.ctx, ast.Load)
            ):
                usos.setdefault(no.attr, no.lineno)
    return usos, chamados


def _reparte_no_gate(
    fn: ast.AsyncFunctionDef,
) -> tuple[tuple[dict[str, int], set[str]], tuple[dict[str, int], set[str]]]:
    """Devolve (o que o dublê executa, o que só roda com o controle na mesa)."""
    laco = _o_while_do_laco(fn)
    corte = _indice_do_gate(laco)
    posicao = fn.body.index(laco)
    executado: list[ast.AST] = [
        *fn.body[:posicao],
        laco.test,
        *laco.body[: corte + 1],
        *laco.orelse,
        *fn.body[posicao + 1 :],
    ]
    so_conectado: list[ast.AST] = [*laco.body[corte + 1 :]]
    return _usos_de_self(executado), _usos_de_self(so_conectado)


def _producao() -> ast.AsyncFunctionDef:
    fonte = LIFECYCLE.read_text(encoding="utf-8")
    return _poll_loop_de(ast.parse(fonte, filename=str(LIFECYCLE)))


def _amarra_o_laco_de_producao(classe: ast.ClassDef) -> bool:
    """A assinatura de um dublê que roda o laço de verdade: `X._poll_loop.__get__`."""
    for no in ast.walk(classe):
        if not isinstance(no, ast.Attribute) or no.attr != "__get__":
            continue
        dono = no.value
        if (
            isinstance(dono, ast.Attribute)
            and dono.attr == "_poll_loop"
            and isinstance(dono.value, ast.Name)
            and dono.value.id != "self"
        ):
            return True
    return False


def _dubles_do_laco() -> list[tuple[Path, ast.Module, ast.ClassDef]]:
    """Varre `tests/` atrás de toda classe que amarra o `_poll_loop` de produção."""
    achados: list[tuple[Path, ast.Module, ast.ClassDef]] = []
    for caminho in sorted(TESTES.rglob("*.py")):
        texto = caminho.read_text(encoding="utf-8", errors="replace")
        if "_poll_loop" not in texto:
            continue
        try:
            modulo = ast.parse(texto, filename=str(caminho))
        except SyntaxError:
            continue
        for no in ast.walk(modulo):
            if isinstance(no, ast.ClassDef) and _amarra_o_laco_de_producao(no):
                achados.append((caminho, modulo, no))
    return achados


def _classe_do_modulo(modulo: ast.Module, nome: str) -> ast.ClassDef | None:
    for no in ast.walk(modulo):
        if isinstance(no, ast.ClassDef) and no.name == nome:
            return no
    return None


def _vocabulario(classe: ast.ClassDef, modulo: ast.Module, caminho: Path) -> dict[str, int]:
    """Tudo o que o dublê DECLARA: método próprio, atributo de instância, e as"""
    nomes: dict[str, int] = {}
    for sentenca in classe.body:
        if isinstance(sentenca, ast.FunctionDef | ast.AsyncFunctionDef):
            nomes.setdefault(sentenca.name, sentenca.lineno)
    for no in ast.walk(classe):
        if isinstance(no, ast.Assign):
            alvos: list[ast.expr] = list(no.targets)
        elif isinstance(no, ast.AnnAssign | ast.AugAssign):
            alvos = [no.target]
        else:
            continue
        for alvo in alvos:
            if (
                isinstance(alvo, ast.Attribute)
                and isinstance(alvo.value, ast.Name)
                and alvo.value.id == "self"
            ):
                nomes.setdefault(alvo.attr, alvo.lineno)
    for base in classe.bases:
        if not isinstance(base, ast.Name):
            raise AssertionError(
                f"{caminho.name}: o dublê `{classe.name}` herda de uma expressão "
                "que esta régua não sabe ler. Ela mede o que está ESCRITO no "
                "arquivo do dublê; se a base vier de outro lugar, a régua "
                "precisa ser reescrita em vez de ficar verde sobre nada."
            )
        pai = _classe_do_modulo(modulo, base.id)
        if pai is None:
            raise AssertionError(
                f"{caminho.name}: o dublê `{classe.name}` herda de `{base.id}`, "
                "que não é declarado neste módulo. Se ele passou a herdar do "
                "`Daemon` de produção, esta régua deixa de medir — todo método "
                "existiria por herança e ela ficaria verde sobre nada. "
                "Reescreva-a antes de seguir."
            )
        for nome, linha in _vocabulario(pai, modulo, caminho).items():
            nomes.setdefault(nome, linha)
    return nomes


def test_o_laco_de_producao_tem_um_gate_que_corta() -> None:
    """A fundação da régua abaixo: existe o gate, e há vida dos dois lados.

    Se o gate cortasse o laço inteiro (nada depois) ou nada (nada antes), a
    repartição seria decorativa e a régua estaria exigindo do dublê a lista
    errada — demais num caso, de menos no outro.

    O QUE A MORDIDA ARRANCA: tire o `continue` do fim do
    `if not self.controller.is_connected():` em `daemon/lifecycle.py`. O
    `_indice_do_gate` deixa de reconhecer o gate e este teste reprova dizendo
    que a régua precisa ser reescrita — em vez de medir a metade errada calado.
    """
    (executado, _), (so_conectado, _) = _reparte_no_gate(_producao())

    assert executado, "o gate de conexão é a primeira coisa do laço: nada roda desconectado?"
    assert so_conectado, (
        "o gate de conexão não corta nada — todo o laço rodaria desconectado. "
        "Ou o `continue` saiu, ou o laço foi reescrito; nos dois casos esta "
        "régua mede a lista errada."
    )
    assert "_is_stopping" in executado, (
        "o `_is_stopping` da condição do `while` sumiu da conta — sinal de que a "
        "régua parou de ler `laco.test` e passou a ignorar a única chamada que "
        "roda ANTES de qualquer tique."
    )


def test_ha_pelo_menos_um_duble_rodando_o_poll_loop_de_producao() -> None:
    """Conjunto vazio não é verde."""
    dubles = _dubles_do_laco()

    assert dubles, (
        "nenhuma classe em `tests/` amarra `X._poll_loop.__get__(self)`. Ou o "
        "dublê do laço sumiu, ou mudou de forma — e esta régua não mede mais "
        "nada. Ela existe porque `test_aba_no_jogo_so_com_jogo_aberto.py` roda "
        "o `_poll_loop` de PRODUÇÃO."
    )
    nomes = {classe.name for _, _, classe in dubles}
    assert "_DaemonDeLaco" in nomes, (
        f"o dublê conhecido `_DaemonDeLaco` não está entre os achados: {sorted(nomes)}"
    )


def test_o_duble_tem_um_irmao_para_todo_uso_que_ele_executa() -> None:
    """A entrega desta sprint, e a mensagem É a entrega."""
    (executado, chamados), _ = _reparte_no_gate(_producao())
    faltando: list[str] = []

    for caminho, modulo, classe in _dubles_do_laco():
        tem = _vocabulario(classe, modulo, caminho)
        relativo = caminho.relative_to(RAIZ)
        for nome, linha in sorted(executado.items()):
            if nome in tem:
                continue
            if nome in chamados:
                receita = f"def {nome}(self, **_k: object) -> None: ..."
                onde = "no corpo da classe"
            else:
                receita = f"self.{nome} = None   # o laço LÊ isto, nunca chama"
                onde = "no `__init__`"
            faltando.append(
                f"  - `{nome}`  (usado em daemon/lifecycle.py:{linha})\n"
                f"    falta em `{classe.name}`, {relativo}:{classe.lineno}\n"
                f"    escreva {onde}:  {receita}"
            )

    assert not faltando, (
        "O `_poll_loop` de produção usa, no caminho que o dublê percorre, nomes "
        "de `self` que o dublê não tem. O dublê roda o laço de VERDADE — é essa "
        "a virtude dele —, então ele precisa de um irmão para cada uso, senão a "
        "próxima pessoa colhe um `AttributeError` três arquivos longe da "
        "causa:\n\n" + "\n".join(faltando)
    )


_LACO_DE_MENTIRA = """
class Falso:
    async def _poll_loop(self) -> None:
        self._antes_do_while()
        while not self._is_stopping():
            self._antes_do_gate()
            self.store.nao_e_chamada_de_self()
            self._escrito_antes = 1
            if self._lido_antes is not None:
                pass
            with contextlib.suppress(Exception):
                self._antes_mas_suprimido()
            if not self.controller.is_connected():
                self._dentro_do_gate()
                continue
            self._depois_do_gate()
            if self._lido_depois:
                self._depois_aninhado()
        else:
            self._no_else_do_while()
        self._no_rabo_do_laco()
        tarefa = self._lido_no_rabo
"""


def test_a_regua_sabe_exatamente_onde_o_gate_corta() -> None:
    """O arranjo DIFÍCIL, num laço de mentira feito só para isto."""
    fn = _poll_loop_de(ast.parse(_LACO_DE_MENTIRA))
    (executado, chamados), (so_conectado, _) = _reparte_no_gate(fn)

    assert set(executado) == {
        "_is_stopping",
        "_antes_do_while",
        "_antes_do_gate",
        "_lido_antes",
        "_antes_mas_suprimido",
        "_dentro_do_gate",
        "_no_else_do_while",
        "_no_rabo_do_laco",
        "_lido_no_rabo",
        "store",
        "controller",
    }
    assert set(so_conectado) == {
        "_depois_do_gate",
        "_lido_depois",
        "_depois_aninhado",
    }
    assert "_escrito_antes" not in executado | so_conectado, (
        "escrita de atributo não exige nada do dublê — `self.x = 1` funciona em "
        "qualquer objeto. Cobrá-la só faria a régua pedir stub à toa."
    )
    assert "nao_e_chamada_de_self" not in executado | so_conectado
    assert chamados == {
        "_is_stopping",
        "_antes_do_while",
        "_antes_do_gate",
        "_antes_mas_suprimido",
        "_dentro_do_gate",
        "_no_else_do_while",
        "_no_rabo_do_laco",
    }, "o conjunto dos CHAMADOS é o que escolhe a receita da mensagem de recusa"


def test_a_regua_alcanca_o_rabo_do_laco_e_a_leitura_sem_chamada() -> None:
    """Os dois furos de 20/09/2026, ancorados no laço DE VERDADE."""
    fn = _producao()
    laco = _o_while_do_laco(fn)
    (executado, chamados), _ = _reparte_no_gate(fn)

    fim_do_while = laco.end_lineno
    assert fim_do_while is not None, "AST sem `end_lineno`: esta régua precisa dele"
    depois_do_while = {nome: linha for nome, linha in executado.items() if linha > fim_do_while}
    assert depois_do_while, (
        "nenhum uso de `self` depois do `while` entrou na conta, e o "
        f"`_poll_loop` vai até a linha {fn.end_lineno} enquanto o `while` "
        f"termina na {fim_do_while}. O dublê roda o laço ATÉ O FIM "
        "(`_is_stopping` devolve `True` e a função continua), então o rabo é "
        "território dele. Foi este o furo nº 1 da conferência de 20/09/2026: a "
        "régua dava verde com a bancada do dublê em dois `AttributeError`."
    )
    so_lidos = set(executado) - chamados
    assert so_lidos, (
        "todo uso de `self` que o dublê executa apareceu CHAMADO, o que não "
        "bate com o laço: o `_stop_event`, o `_input_ready_at` e as duas tasks "
        "do rabo são lidos e nunca chamados — e é por isso que eles estão no "
        "`__init__` do `_DaemonDeLaco`. Se este conjunto esvaziou, a régua "
        "voltou a olhar só para `ast.Call` (furo nº 2 de 20/09/2026) e uma "
        "leitura nova passa a quebrar o dublê em silêncio."
    )


_DUBLE_QUE_HERDA_O_PRODUTO = """
from hefesto_dualsense4unix.daemon.lifecycle import Daemon


class _DubleQueHerda(Daemon):
    def __init__(self) -> None:
        self._poll_loop = Daemon._poll_loop.__get__(self)
"""


def test_a_regua_recusa_um_duble_que_herda_o_daemon_de_producao() -> None:
    """A razão de esta régua ler AST e não chamar `hasattr`, escrita como teste."""
    modulo = ast.parse(_DUBLE_QUE_HERDA_O_PRODUTO)
    classe = _classe_do_modulo(modulo, "_DubleQueHerda")
    assert classe is not None

    try:
        _vocabulario(classe, modulo, Path("duble_de_mentira.py"))
    except AssertionError as recusa:
        assert "Daemon" in str(recusa)
        assert "verde sobre nada" in str(recusa)
    else:
        raise AssertionError(
            "`_vocabulario` aceitou um dublê que herda do `Daemon` de produção. "
            "Nesse arranjo ela não mede nada — todo método existe por herança — "
            "e a régua principal passa a dar verde sobre um dublê cego."
        )
