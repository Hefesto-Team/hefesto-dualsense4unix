"""O-DUBLE-NAO-EMPOBRECE-SOZINHO-01 — o dublê que roda o laço de produção
não pode ficar para trás dele.

O DEFEITO, MEDIDO EM 20/09/2026
===============================
A suíte de 24 partes reprovou dois testes::

    FAILED tests/unit/test_aba_no_jogo_so_com_jogo_aberto.py::test_o_poll_loop_agenda_a_sonda
    FAILED tests/unit/test_aba_no_jogo_so_com_jogo_aberto.py::test_a_sonda_nao_empilha_a_cada_tique
    E  AttributeError: '_DaemonDeLaco' object has no attribute
                       '_reconciliar_exposicao_do_modo_nativo'

A causa estava noutro arquivo e noutra sprint: `cacd786cb`
(O-NO-NASCE-FECHADO-01) acrescentou uma chamada ao `_poll_loop` de
`daemon/lifecycle.py`. O dublê `_DaemonDeLaco` roda o `_poll_loop` **de
produção** — de propósito, e é essa a virtude dele —, então todo uso novo de
`self` precisa de um irmão no dublê. Ele já tinha cinco stubs exatamente por
isso. Faltou o sexto, e quem quebrou não era dono do arquivo que reprovou.

A METADE FÁCIL foi acrescentar o stub. Ela cura os dois vermelhos e não cura o
problema. Esta é a outra metade: a régua que **lê o laço de produção** e exige
do dublê um irmão para cada uso, nomeando o que falta em vez de deixar um
`AttributeError` aparecer três arquivos adiante.

O QUE A CONFERÊNCIA ADVERSARIAL DE 20/09/2026 ARRANCOU DESTA RÉGUA
==================================================================
A primeira versão desta régua media **dois terços do que o dublê executa**, e
as duas mordidas abaixo a passaram VERDE enquanto reproduziam, palavra por
palavra, o `AttributeError` de cima:

1. **O RABO DO LAÇO.** Ela repartia `while.body` no gate e parava ali — mas o
   `_poll_loop` tem quatro sentenças **depois** do `while`, e o dublê roda até
   o fim (`_is_stopping` devolve `True` e o laço sai normalmente). Uma chamada
   posta ali reprovava a bancada do dublê com a régua em `5 passed`.
2. **A LEITURA DE ATRIBUTO.** Ela olhava só para `Call`. Mas
   `if self._lease_do_modo_nativo is not None:` antes do gate quebra o dublê
   do mesmo jeito — e **quatro dos atributos que o dublê já carrega hoje**
   (`_stop_event`, `_input_ready_at`, `_external_tick_task`,
   `_steam_jogo_task`) existem no `__init__` dele exatamente porque o laço os
   LÊ, nunca porque os chama. O defeito histórico é `self.<qualquer coisa>`,
   não `self.<chamada>`.

Por isso a régua de hoje mede **todo `self.<nome>` em contexto de leitura**,
em **tudo o que o dublê executa**: a preparação antes do `while`, a CONDIÇÃO
do `while`, o corpo até o gate, o corpo do gate, o `else` do `while` e o rabo
depois dele. Escrita (`self.x = ...`) fica de fora: ela não exige nada de
ninguém.

POR QUE AST, E NÃO `hasattr` NUMA INSTÂNCIA
===========================================
Três razões, e as três custaram alguma coisa nesta casa:

1. **`hasattr` passa por herança em método que o dublê não pretende ter.** A
   pergunta é *"o laço de produção usa isto?"*, e quem responde é o código do
   laço — não o MRO do dublê.
2. **O módulo do dublê SÓ COLETA com PyGObject real** (`exigir_gi_real`, no topo
   dele). Uma régua que o importasse seria PULADA num runner headless — verde
   sobre nada, que é a família de defeito que esta casa mais persegue. Lendo por
   AST, esta régua roda em qualquer lugar.
3. **Lista digitada é a terceira cópia do mesmo dado.** Se o gate de conexão
   mudar de lugar, a régua muda junto porque ela LÊ o laço.

OS NÚMEROS QUE DESENHAM A RÉGUA — medidos por AST, 20/09/2026
=============================================================
O `_poll_loop` usa **16** nomes de `self` no que o dublê executa (nove deles
chamados, sete só lidos) e **26** no que só roda com o controle na mesa. O
dublê roda com `is_connected()` devolvendo `False`, e por isso nunca precisou
desses 26.

**Uma régua ingênua — a que exigisse tudo — reprovaria sem defeito nenhum**,
medido arrancando o corte desta régua em 20/09/2026. Por isso ela reparte o
laço no gate e exige só o lado que o dublê executa.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
LIFECYCLE = RAIZ / "src" / "hefesto_dualsense4unix" / "daemon" / "lifecycle.py"
TESTES = RAIZ / "tests"


# ---------------------------------------------------------------------------
# A leitura do laço de produção
# ---------------------------------------------------------------------------


def _poll_loop_de(arvore: ast.Module) -> ast.AsyncFunctionDef:
    for no in ast.walk(arvore):
        if isinstance(no, ast.AsyncFunctionDef) and no.name == "_poll_loop":
            return no
    raise AssertionError("não achei o `_poll_loop`")


def _o_while_do_laco(fn: ast.AsyncFunctionDef) -> ast.While:
    """O único `while` do corpo do `_poll_loop`.

    Se um dia forem dois, esta régua para de saber repartir o laço — e dizer
    isso é melhor do que escolher o primeiro e medir metade.
    """
    whiles = [s for s in fn.body if isinstance(s, ast.While)]
    if len(whiles) != 1:
        raise AssertionError(
            f"esperava UM `while` no corpo do `_poll_loop`, achei {len(whiles)}. "
            "Esta régua reparte o laço no gate de conexão e precisa saber qual é "
            "o laço. Reescreva-a antes de seguir."
        )
    return whiles[0]


def _indice_do_gate(laco: ast.While) -> int:
    """A posição, no corpo do `while`, do `if not self.controller.is_connected():`.

    O gate tem de TERMINAR em `continue`: é isso que faz "antes do gate" ser um
    modelo correto do que o dublê executa. Sem o `continue`, o laço seguiria
    adiante desconectado e a régua estaria medindo a metade errada.
    """
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
    """`(nome -> primeira linha, quais deles aparecem CHAMADOS)`.

    Conta todo `self.<nome>` em contexto de LEITURA, chamado ou não: quatro dos
    atributos que o `_DaemonDeLaco` carrega hoje existem porque o laço os lê,
    nunca porque os chama, e um `if self._algo:` novo quebra o dublê igualzinho
    a uma chamada nova (medido na conferência de 20/09/2026).

    Fica de fora, de propósito:

    * **ESCRITA** (`self._last_state = None`) — não exige nada de ninguém.
    * **O SEGUNDO SALTO** (`self.store.clear_controller_state()`) — quem tem de
      ter o `clear_controller_state` é o `store`; do dublê se cobra o `store`,
      e é o que este colhedor devolve.
    """
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
    """Devolve (o que o dublê executa, o que só roda com o controle na mesa).

    O primeiro conjunto é TUDO por onde o dublê passa:

    * a preparação antes do `while`;
    * a CONDIÇÃO do `while` (é ali que mora o `_is_stopping`);
    * o corpo do laço até o gate, e o corpo do próprio gate — que o dublê
      executa, porque ele nasce desconectado;
    * o `else` do `while` e **o rabo depois do `while`**, porque o dublê roda o
      laço até o fim: o `_is_stopping` dele devolve `True` depois de N tiques e
      a função continua. Esquecer o rabo foi o furo nº 1 de 20/09/2026 — e é
      dali que vêm o `_external_tick_task` e o `_steam_jogo_task` do dublê.
    """
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


# ---------------------------------------------------------------------------
# A leitura do dublê
# ---------------------------------------------------------------------------


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
    """Varre `tests/` atrás de toda classe que amarra o `_poll_loop` de produção.

    Hoje é uma só (`_DaemonDeLaco`). A varredura é para a PRÓXIMA — uma lista
    digitada aqui envelheceria calada, que é o defeito que esta sprint cura.
    """
    achados: list[tuple[Path, ast.Module, ast.ClassDef]] = []
    for caminho in sorted(TESTES.rglob("*.py")):
        texto = caminho.read_text(encoding="utf-8", errors="replace")
        if "_poll_loop" not in texto:  # peneira barata; a autoridade é o AST
            continue
        try:
            modulo = ast.parse(texto, filename=str(caminho))
        except SyntaxError:  # fixture de código quebrado de propósito
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
    """Tudo o que o dublê DECLARA: método próprio, atributo de instância, e as
    bases escritas no mesmo arquivo.

    O `self._schedule_steam_jogo_tick = Daemon....__get__(self)` do `__init__` é
    a razão de os atributos de instância entrarem: ele é método sem ser `def`.
    """
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


# ---------------------------------------------------------------------------
# 1. O modelo: o laço tem mesmo um gate, e ele corta alguma coisa
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 2. A trava contra o conjunto vazio: sem dublê, a régua não mede nada
# ---------------------------------------------------------------------------


def test_ha_pelo_menos_um_duble_rodando_o_poll_loop_de_producao() -> None:
    """Conjunto vazio não é verde.

    A régua de baixo percorre os dublês achados. Se a varredura devolvesse zero
    — arquivo renomeado, dublê reescrito com outra amarração —, ela passaria sem
    olhar para nada, que é exatamente o instrumento falso que esta casa mais
    achou em 2026.

    O QUE A MORDIDA ARRANCA: em `test_aba_no_jogo_so_com_jogo_aberto.py`, troque
    `Daemon._poll_loop.__get__(self)` por `self._poll_loop = None`. A varredura
    devolve lista vazia e este teste reprova — enquanto o de baixo ficaria verde
    sozinho.
    """
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


# ---------------------------------------------------------------------------
# 3. A régua: todo uso de `self` que o dublê executa tem irmão no dublê
# ---------------------------------------------------------------------------


def test_o_duble_tem_um_irmao_para_todo_uso_que_ele_executa() -> None:
    """A entrega desta sprint, e a mensagem É a entrega.

    Quem lê esta reprovação é quem acabou de mexer no `_poll_loop` — e ele não
    faz ideia de que existe um dublê. Então a mensagem diz o nome, a linha do
    laço, o dublê, o arquivo dele, e a linha a escrever.

    Vale para os usos dentro de `with contextlib.suppress(Exception):` também, e
    ali vale ainda mais: lá um `AttributeError` não estoura, vira no-op
    silencioso — o dublê exercitaria um laço com um bloco a menos e ninguém
    saberia.

    O QUE A MORDIDA ARRANCA, e são quatro — as duas primeiras são o defeito
    original, as duas últimas são o que a conferência adversarial de 20/09/2026
    achou passando VERDE:

    1. Apague do `_DaemonDeLaco` o stub `_reconciliar_exposicao_do_modo_nativo`.
       Este teste reprova NOMEANDO o método — que é o vermelho de 20/09/2026,
       agora com endereço.
    2. Devolva o stub e acrescente ao `_poll_loop`, antes do gate, um
       `self._um_metodo_que_nao_existe()`. Reprova de novo, nomeando o método.
    3. Acrescente uma chamada de `self` **depois do `while`**, no rabo do
       `_poll_loop` (junto do `tick_task = self._external_tick_task`). O dublê
       roda até lá; a régua antiga parava no `while` e dava `5 passed` com a
       bancada do dublê em dois `AttributeError`.
    4. Acrescente, antes do gate, uma LEITURA sem chamada —
       `if self._lease_do_modo_nativo is not None:`. Mesmo estrago, e a régua
       antiga só olhava para `Call`.
    """
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


# ---------------------------------------------------------------------------
# 4. A régua da régua: o gate é o que separa, e a separação é medida
# ---------------------------------------------------------------------------


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
    """O arranjo DIFÍCIL, num laço de mentira feito só para isto.

    Um laço sintético é o único jeito de perguntar à régua se ela acerta os
    casos que o laço real tem hoje mas pode perder amanhã: a chamada na
    CONDIÇÃO do `while`, a chamada dentro de um `with suppress`, a chamada
    dentro do corpo do gate, a chamada ANINHADA depois do gate, a chamada no
    `else` do `while`, a chamada e a leitura no RABO depois do `while`, a
    LEITURA sem chamada dos dois lados do gate, a ESCRITA (que não exige nada) e
    a chamada que não é em `self` (`self.store.x()` — quem precisa do método é o
    store, e do dublê se cobra o `store`).

    Montar o esperado com a mesma função que extrai seria tautologia; aqui o
    esperado está escrito à mão, contra um texto escrito à mão.

    O QUE A MORDIDA ARRANCA, e são quatro:

    * em `_reparte_no_gate`, troque `laco.body[: corte + 1]` por `laco.body`: a
      régua volta a ser a ingênua e este teste reprova nomeando
      `_depois_do_gate`, `_lido_depois` e `_depois_aninhado`;
    * troque por `laco.body[:corte]` e ele reprova por `_dentro_do_gate`, que o
      dublê EXECUTA porque nasce desconectado;
    * tire o `*fn.body[posicao + 1 :]` e ele reprova por `_no_rabo_do_laco` e
      `_lido_no_rabo` — o furo nº 1 da conferência de 20/09/2026;
    * volte `_usos_de_self` a olhar só para `ast.Call` e ele reprova por
      `_lido_antes` e `_lido_no_rabo` — o furo nº 2.
    """
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


# ---------------------------------------------------------------------------
# 5. As duas metades que a conferência adversarial achou faltando
# ---------------------------------------------------------------------------


def test_a_regua_alcanca_o_rabo_do_laco_e_a_leitura_sem_chamada() -> None:
    """Os dois furos de 20/09/2026, ancorados no laço DE VERDADE.

    O teste acima prova as duas metades num laço sintético. Este prova que elas
    valem contra `daemon/lifecycle.py` como ele está: o `_poll_loop` real tem
    sentenças depois do `while`, e elas usam `self` — sem chamar. As duas
    afirmações são estruturais de propósito (linha e conjunto, não nome
    digitado): renomear `_external_tick_task` não derruba este teste, e tirar o
    rabo da conta derruba.

    O QUE A MORDIDA ARRANCA: tire `*fn.body[posicao + 1 :]` de
    `_reparte_no_gate` — a primeira afirmação cai. Volte `_usos_de_self` a olhar
    só para `ast.Call` — as duas caem.
    """
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


# ---------------------------------------------------------------------------
# 6. A recusa: um dublê que herda o produto não é mensurável por esta régua
# ---------------------------------------------------------------------------


_DUBLE_QUE_HERDA_O_PRODUTO = """
from hefesto_dualsense4unix.daemon.lifecycle import Daemon


class _DubleQueHerda(Daemon):
    def __init__(self) -> None:
        self._poll_loop = Daemon._poll_loop.__get__(self)
"""


def test_a_regua_recusa_um_duble_que_herda_o_daemon_de_producao() -> None:
    """A razão de esta régua ler AST e não chamar `hasattr`, escrita como teste.

    Se o dublê herdar do `Daemon` de produção, TODO método existe por herança:
    um `hasattr` passaria sempre, e a régua ficaria verde sobre nada — sem nunca
    dizer que parou de medir. O `_vocabulario` só sabe ler o que está escrito no
    arquivo do dublê, e quando a base não está lá ele RECUSA em voz alta.

    Isto é a regra de 04/09 aplicada à própria régua: *instrumento que sabe do
    próprio risco RESOLVE, não avisa*.

    O QUE A MORDIDA ARRANCA: troque o `raise AssertionError` de `_vocabulario`
    (o do `pai is None`) por `continue`. Este teste reprova porque nenhuma
    exceção sobe — e é o momento exato em que a régua principal passaria a dar
    verde sobre um dublê que ela não consegue medir.
    """
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
