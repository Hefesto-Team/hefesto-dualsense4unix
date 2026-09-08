"""O retratista das abas não pode fotografar dado REAL dela.

O `README.md` carrega este aviso, e ele é a razão deste arquivo existir:

    "Na aba Sistema, o bloco 'Detalhes técnicos' está borrado de propósito: o
     log mostra o endereço Bluetooth real dos controles desta máquina, e os
     gates de anonimato do projeto não varrem imagens."

Ou seja: uma foto da interface **já vazou endereço Bluetooth real** uma vez, e
a cura foi um borrão feito à mão. Quem grava direto em `docs/usage/assets/` —
as imagens do README — não pode contar com borrão: ninguém revisa PNG a cada
execução, e os portões de anonimato desta casa **não leem imagem** (o `-I` do
`check_anonymity.sh` existe justamente porque eles nunca souberam).

A segurança vem da CONSTRUÇÃO, e a construção mudou de dono — 08/09/2026
------------------------------------------------------------------------

**A CAUSA MEDIDA:** até hoje este arquivo apontava para
`scripts/gui-captura/retratar_abas.py`, que montava a JANELA GTK do `.glade` e
alimentava o card com os dublês da suíte. **A janela saiu inteira em 06/09/2026
por decisão dela** (`D-0609-GTK-LEVA-INTEIRA`) e o retratista saiu com ela — o
Passo 2 da `GTK-3` removeu o script, e o Passo 1 ("os 62 testes, um a um") não
alcançou este arquivo. O resultado foi uma régua de ANONIMATO apontada para um
caminho que não existe: `_fonte()` morria no `assert SCRIPT.is_file()` e os
três testes ficavam vermelhos — que é o pior estado possível para um portão de
vazamento, porque vermelho constante se lê como ruído e se desliga.

**O fato não caducou; o dono mudou.** Quem grava em `docs/usage/assets/` hoje é
`src/hefesto_dualsense4unix/interface/olhar.py --todas --publicado --doc`, e o
`CLAUDE.md` já manda rodá-lo antes de commitar. Ele fotografa PÁGINA HTML num
Chrome headless, e é por isso que a garantia continua valendo — e continua
podendo ser quebrada pelo mesmo gesto tentador de sempre: ligar o retratista ao
daemon vivo para "deixar a foto mais real", e publicar o MAC dela junto.

O QUE MUDOU NA FORMA DA GARANTIA, e é o que faz esta régua morder hoje
----------------------------------------------------------------------

A janela lia estado por IPC no instante da foto. A página HTML não lê nada: ela
é um arquivo do repositório, e o retratista abre `file://`. Então a régua tem
duas metades, e a segunda é nova:

1. **nenhuma porta do daemon no código** — a lista abaixo é a mesma de sempre,
   e cada nome dela traz no payload MAC, nome de máquina ou caminho de arquivo
   de quem rodar;
2. **a foto só nasce de página do repositório** — e isso se mede em DUAS
   metades, sobre o argumento do `goto` e não sobre o texto do arquivo: a
   FORMA (`f"file://{nome}"`, e nada além disso) e a PROCEDÊNCIA (esse nome
   nasce numa pergunta ao `onde`, o dono único das duas pastas de página). É o
   outro lado da moeda: barrada a conversa com o daemon, o atalho que sobra é
   abrir qualquer outra coisa e fotografar.

   **AS DUAS METADES SÃO ALLOWLIST, e isso é o ponto** — corrigido em
   08/09/2026, no mesmo dia em que nasceram como denylist. Ver a docstring de
   `test_a_foto_so_nasce_de_pagina_do_repositorio` para o preço medido: duas
   mordidas do conferente passaram VERDE contra a denylist.

E o que a página CONTÉM não se mede aqui de propósito: ela é arquivo versionado
e passa pelos DOIS portões de anonimato desta casa — o `test_docs_mac_anonimato`
(por OUI) e o `check_endereco_de_radio.py` (por FORMA), que varrem todo arquivo
que o `git ls-files` lista. Uma terceira régua sobre o mesmo texto seria
verbosidade; o buraco que só ESTE arquivo pode tapar é o do instrumento.

O QUE SAIU JUNTO COM A JANELA, e quem herdou
---------------------------------------------

* `test_a_unica_fonte_de_estado_e_o_fixture_versionado` cobrava que todo `.json`
  lido morasse em `tests/fixtures/`. O retratista de hoje não lê `.json`
  nenhum — o modo `--mesa-cheia` era da janela. **Herdeiro:**
  `test_a_foto_so_nasce_de_pagina_do_repositorio`, que é a mesma pergunta
  ("de onde vem o dado da foto?") sobre o instrumento que existe.
* `test_o_card_e_alimentado_pelos_dubles_da_suite` e
  `test_o_duble_usado_tem_mac_falso` ancoravam o dublê que alimentava o
  `controller_card` do GTK. Não há card montado em widget nesta foto.
  **Herdeiro:** os dois portões de anonimato do parágrafo acima, que medem a
  página — o que de fato é fotografado hoje.

A MORDIDA
---------

Aplicada em 08/09/2026, e as QUATRO reprovaram. As duas primeiras são as de
sempre; as duas últimas são as do CONFERENTE, que contra a denylist passavam
verdes — cada uma com `count() == 1` conferido antes de escrever:

* acrescente `from hefesto_dualsense4unix.cli.ipc_client import IpcClient` ao
  `olhar.py` — `test_o_script_nao_fala_com_o_daemon` reprova nomeando
  `ipc_client, IpcClient`;
* troque o `pg.goto(f"file://{alvo}")` por `pg.goto("http://localhost:8080")` —
  reprova na FORMA: o argumento deixou de ser f-string de um nome;
* troque-o por um `goto` de um despejo em `/tmp` digitado à mão — **VERDE
  antes, reprova agora**, e sem que a régua precise conhecer `/tmp`, que é
  legítimo como DESTINO do PNG no modo rascunho;
* troque-o por `goto("file://" + expanduser("~") + "/.config/…")` — **VERDE
  antes**, porque o `$HOME` nunca aparecia como literal; reprova agora por ser
  concatenação, não a forma.

E a quinta, que nenhuma das duas metades pega sozinha: mantenha a forma e
plante `alvo = pathlib.Path("/tmp/despejo.html")` antes dela — a FORMA passa e
a PROCEDÊNCIA reprova, nomeando o `alvo` e a função em que ele foi ligado.
"""

from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

#: QUEM GRAVA EM `docs/usage/assets/` HOJE. O caminho está no `CLAUDE.md` e no
#: `test_as_fotos_acompanham_a_versao`, que cobra o gesto de rodá-lo.
SCRIPT = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "olhar.py"

#: O que denuncia conversa com o daemon vivo. Não é lista de proibição
#: cosmética: cada um destes traz, no payload, MAC, nome de máquina ou caminho
#: de arquivo do computador de quem rodar.
#:
#: `ipc_client`/`IpcClient` não estão aqui por simetria com `IPCClient`: a
#: classe real chama-se `IpcClient` (`cli/ipc_client.py`), e enquanto a lista
#: só tinha a caixa `IPCClient` um `from ... .ipc_client import IpcClient`
#: passava VERDE — a porta mais direta de todas estava aberta.
_PORTAS_DO_DAEMON = (
    "daemon.state_full",
    "ipc_bridge",
    "ipc_client",
    "IpcClient",
    "_safe_call",
    "call_async",
    "daemon.status",
    "IPCClient",
    "ipc_socket_path",
)

#: O DONO ÚNICO das duas pastas de página (a bancada e o publicado). Toda foto
#: tem de nascer de uma pergunta a ELE — é o que torna a origem uma página do
#: repositório *por construção*, em vez de por lista de proibições.
_DONO_DA_PAGINA = "onde"
#: Os dois nomes são os das FUNÇÕES de `interface/onde.py`, não prosa: acentuar
#: faria a régua procurar um método que não existe. Daí a isenção na linha.
_PERGUNTAS_AO_DONO = ("pagina", "paginas")  # noqa-acento: nome de função do `onde`

#: O ÚNICO esquema que o retratista pode abrir. `file://` é o disco desta
#: árvore; qualquer outro (`http`, `https`) é a rede, e a rede serve a página
#: VIVA do piloto — com o estado real dela dentro.
_ESQUEMA_PERMITIDO = "file://"


def _fonte() -> str:
    assert SCRIPT.is_file(), (
        f"{SCRIPT} sumiu. Se o retratista mudou de casa de novo, este portão "
        "muda com ele — apagá-lo é deixar a próxima foto publicar o MAC dela."
    )
    return SCRIPT.read_text(encoding="utf-8")


def _arvore() -> ast.Module:
    return ast.parse(_fonte())


# ---------------------------------------------------------------------------
# A PROCEDÊNCIA DO ARGUMENTO, e é o que separa uma allowlist de uma denylist
# ---------------------------------------------------------------------------
#
# Estas funções respondem UMA pergunta: *a expressão que o retratista entrega
# ao `goto` nasce numa pergunta ao `onde`?* Elas não conhecem caminho nenhum —
# não há `/tmp`, não há `$HOME`, não há lista de esquema proibido a manter. Por
# isso o `/tmp` legítimo do modo rascunho (o DESTINO do PNG, `saida`) não é
# assunto delas: só o que entra no `goto` é medido.


def _funcao_que_contem(arvore: ast.Module, alvo: ast.AST) -> ast.FunctionDef | None:
    """A função MAIS INTERNA que contém `alvo` — o escopo em que ele se resolve."""
    dentro = [
        f
        for f in ast.walk(arvore)
        if isinstance(f, ast.FunctionDef) and any(n is alvo for n in ast.walk(f))
    ]
    return max(dentro, key=lambda f: f.lineno) if dentro else None


def _nasce_no_dono(exp: ast.expr, escopo: ast.FunctionDef, arvore: ast.Module,
                   visto: frozenset[tuple[str, int]] = frozenset()) -> bool:
    """A expressão `exp`, avaliada em `escopo`, vem de `onde.pagina*`?"""
    if isinstance(exp, ast.Call):
        f = exp.func
        return (
            isinstance(f, ast.Attribute)
            and isinstance(f.value, ast.Name)
            and f.value.id == _DONO_DA_PAGINA
            and f.attr in _PERGUNTAS_AO_DONO
        )
    if isinstance(exp, ast.Subscript):  # uma fatia do que o dono devolveu é dele
        return _nasce_no_dono(exp.value, escopo, arvore, visto)
    if isinstance(exp, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
        # `[p for p in onde.paginas(...) if ...]` — a origem é o `iter`.
        return all(
            _nasce_no_dono(g.iter, escopo, arvore, visto) for g in exp.generators
        )
    if isinstance(exp, ast.Name):
        return _nome_nasce_no_dono(exp.id, escopo, arvore, visto)
    return False


def _nome_nasce_no_dono(nome: str, escopo: ast.FunctionDef, arvore: ast.Module,
                        visto: frozenset[tuple[str, int]]) -> bool:
    """Todo caminho que liga `nome` dentro de `escopo` nasce no dono?

    Três formas de ligação, e são as três que o retratista usa:
    atribuição (`alvo = onde.pagina(...)`), laço sobre a lista que o dono
    devolveu, e PARÂMETRO — que é o que a régua velha não sabia perseguir. Um
    parâmetro só é do dono se TODA chamada da função o alimentar com algo do
    dono; basta um chamador entregar outra coisa para a resposta ser não.
    """
    chave = (nome, id(escopo))
    if chave in visto:  # recursão (`x = x`): não prova nada, e não trava
        return False
    visto = visto | {chave}

    ligacoes: list[ast.expr] = []
    for no in ast.walk(escopo):
        if isinstance(no, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == nome for t in no.targets):
                ligacoes.append(no.value)
        elif isinstance(no, ast.AnnAssign):
            if isinstance(no.target, ast.Name) and no.target.id == nome and no.value:
                ligacoes.append(no.value)
        elif (
            isinstance(no, ast.For)
            and isinstance(no.target, ast.Name)
            and no.target.id == nome
        ):
            ligacoes.append(no.iter)
    if ligacoes:
        return all(_nasce_no_dono(v, escopo, arvore, visto) for v in ligacoes)

    posicao = _posicao_do_parametro(escopo, nome)
    if posicao is None:
        return False
    chamadas = _chamadas_de(escopo.name, arvore)
    if not chamadas:  # função sem chamador não prova procedência nenhuma
        return False
    for chamada in chamadas:
        arg = _argumento_em(chamada, posicao, nome)
        if arg is None:
            return False
        de_quem = _funcao_que_contem(arvore, chamada)
        if de_quem is None or not _nasce_no_dono(arg, de_quem, arvore, visto):
            return False
    return True


def _posicao_do_parametro(f: ast.FunctionDef, nome: str) -> int | None:
    todos = [*f.args.posonlyargs, *f.args.args]
    for i, a in enumerate(todos):
        if a.arg == nome:
            return i
    return None


def _chamadas_de(nome: str, arvore: ast.Module) -> list[ast.Call]:
    return [
        n
        for n in ast.walk(arvore)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == nome
    ]


def _argumento_em(chamada: ast.Call, posicao: int, nome: str) -> ast.expr | None:
    for kw in chamada.keywords:
        if kw.arg == nome:
            return kw.value
    if posicao < len(chamada.args):
        return chamada.args[posicao]
    return None


def _navegacoes(arvore: ast.Module) -> list[ast.Call]:
    """Toda chamada `.goto(...)` do retratista — o único ponto que abre página."""
    return [
        n
        for n in ast.walk(arvore)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "goto"
    ]


def test_o_script_nao_fala_com_o_daemon() -> None:
    """A foto não pode nascer de estado real: ela vai direto para `docs/`.

    A verificação é sobre o CÓDIGO, não sobre os comentários — a nota de
    privacidade do cabeçalho cita `daemon.state_full` de propósito, para
    explicar o que não fazer. (E é a mesma armadilha de prosa que já mordeu
    esta casa três vezes: um comentário que CITA o padrão proibido vira a
    primeira ocorrência dele. Aqui o `ast` a desarma por construção.)
    """
    # Só o código: docstrings e comentários ficam de fora por construção do AST.
    codigo = "\n".join(
        ast.unparse(no)
        for no in ast.walk(_arvore())
        if isinstance(no, (ast.Call, ast.Attribute, ast.Import, ast.ImportFrom))
    )

    achados = [porta for porta in _PORTAS_DO_DAEMON if porta in codigo]

    assert not achados, (
        f"o retratista das abas passou a falar com o daemon ({', '.join(achados)}). "
        "O estado real carrega o MAC dos controles dela, e estas fotos vão "
        "DIRETO para docs/usage/assets/, que é o README — sem revisão humana e "
        "sem portão que varra imagens. Se a foto precisa de dado real, ela "
        "precisa de revisão antes de ser publicada, e o script não pode mais "
        "gravar em docs/."
    )


def test_a_foto_so_nasce_de_pagina_do_repositorio() -> None:
    """Toda navegação do retratista abre `file://` de um nome, e nada mais.

    A METADE DA FORMA. Ela mede **o argumento do `goto`**, e cobra uma FORMA
    ÚNICA: uma f-string cujo texto literal é exatamente `file://` e que tem UMA
    interpolação só. É allowlist — o que não tem essa forma reprova, sem que
    ninguém precise ter previsto o atalho. (*O que* essa interpolação pode ser
    é assunto da régua da PROCEDÊNCIA, logo abaixo.)

    A FORMA PIOROU E O LAUDO NÃO DIZIA — CURADO EM 08/09/2026
    ---------------------------------------------------------

    Esta régua nasceu hoje mesmo como DENYLIST de prefixos proibidos
    (o lar de quem roda, `~/`, os dois esquemas de rede, `/proc/`, `/sys/`,
    `/run/`), herdando o lugar de
    `test_a_unica_fonte_de_estado_e_o_fixture_versionado`,
    que era ALLOWLIST de prefixo (*"todo caminho tem de começar em
    `tests/fixtures/`"*). **Numa régua de ANONIMATO a denylist é a forma
    errada**, e quem escrevia isso era a própria casa, no texto do teste que
    saiu. O conferente mediu o preço com duas mordidas, `count() == 1`
    conferido nas duas, e as DUAS passaram VERDE:

    * `goto` para um despejo em `/tmp` — um caminho que a lista não previu;
    * `goto` para o `$HOME` montado em tempo de execução — que passava porque
      **o `$HOME` nunca aparece como literal**.

    A allowlist mata as duas de uma vez, e sem precisar conhecê-las: nenhuma
    das duas tem a forma. E ela resolve o problema que a denylist não podia
    resolver — `/tmp` **não pode** entrar em lista de proibição, porque é onde
    o `olhar.py` grava legitimamente no modo rascunho. Aqui isso nem se
    pergunta: só o argumento do `goto` é medido, e o `/tmp` do rascunho é o
    DESTINO do PNG, nunca a origem.
    """
    navegacoes = _navegacoes(_arvore())
    assert navegacoes, (
        "não achei nenhuma chamada `.goto(...)` no retratista. Régua que não "
        "encontra o que vigiar não é régua verde — é régua cega. Se a "
        "navegação mudou de nome, esta régua muda com ela."
    )

    fora_de_forma: list[str] = []
    for no in navegacoes:
        alvo = no.args[0] if no.args else _argumento_em(no, 0, "url")
        if alvo is None or _interpolacao_unica(alvo) is None:
            desenho = ast.unparse(alvo) if alvo is not None else "<sem argumento>"
            fora_de_forma.append(f"linha {no.lineno}: goto({desenho})")

    assert not fora_de_forma, (
        "o retratista abriu algo que não tem a forma `file://` de UM valor:"
        "\n  "
        + "\n  ".join(fora_de_forma)
        + "\n\nA foto vai direto para docs/usage/assets/ sem revisão humana. "
        "A forma cobrada é uma só — `pg.goto(f\"file://{alvo}\")` — e ela "
        "existe para que a régua não dependa de alguém ter previsto o atalho: "
        "concatenação, caminho digitado e endereço de rede reprovam por não "
        "TEREM a forma, não por estarem numa lista."
    )


def _interpolacao_unica(alvo: ast.expr) -> ast.expr | None:
    """A única interpolação de `f"file://{...}"` — ou `None` se a forma não bate.

    A forma é fechada de propósito: o texto literal tem de ser exatamente
    `file://` e a interpolação tem de ser UMA. Duas interpolações, texto
    sobrando depois do esquema, concatenação ou string crua não passam — e não
    passam por FALTAR A FORMA, não por estarem numa lista de proibições.

    O que a interpolação pode ser fica para a régua da PROCEDÊNCIA: um nome
    (o caso do retratista hoje) ou a pergunta ao dono escrita ali mesmo
    (`f"file://{onde.pagina(x)}"`), que é igualmente legítima e seria arbitrário
    recusar.
    """
    if not isinstance(alvo, ast.JoinedStr):
        return None
    literal = "".join(
        p.value
        for p in alvo.values
        if isinstance(p, ast.Constant) and isinstance(p.value, str)
    )
    pedacos = [p for p in alvo.values if isinstance(p, ast.FormattedValue)]
    if literal != _ESQUEMA_PERMITIDO or len(pedacos) != 1:
        return None
    return pedacos[0].value


def test_a_pagina_fotografada_tem_um_dono_so() -> None:
    """O nome que o `goto` abre nasce numa pergunta ao `onde`, e só nela.

    A METADE DA PROCEDÊNCIA, e ela é o que faz a de cima valer: a forma sozinha
    aceitaria `alvo = pathlib.Path("/tmp/despejo.html")` seguido de
    `goto(f"file://{alvo}")`. Aqui o nome é PERSEGUIDO até onde foi ligado —
    atribuição, laço ou parâmetro —, e um parâmetro só passa se TODOS os seus
    chamadores o alimentarem com algo do dono.

    ERA PRESENÇA, VIROU EXCLUSIVIDADE — 08/09/2026
    -----------------------------------------------

    A régua anterior cobrava que a string `onde.pagina` aparecesse em ALGUM
    ponto do arquivo. O conferente mordeu as duas fontes da régua acima
    mantendo a chamada ao `onde` noutro lugar, e **as duas passaram** — a
    presença estava lá, e a foto nascia de outro sítio. Presença não é
    exclusividade, e num portão de vazamento a diferença é o portão inteiro.
    """
    arvore = _arvore()
    sem_procedencia: list[str] = []
    conferidas = 0
    for no in _navegacoes(arvore):
        alvo = no.args[0] if no.args else _argumento_em(no, 0, "url")
        if alvo is None:
            continue  # a régua da FORMA já reprovou este; não somar ruído
        interpolado = _interpolacao_unica(alvo)
        if interpolado is None:
            continue
        conferidas += 1
        escopo = _funcao_que_contem(arvore, no)
        if escopo is None or not _nasce_no_dono(interpolado, escopo, arvore):
            onde_esta = escopo.name if escopo else "<nível do módulo>"
            sem_procedencia.append(
                f"linha {no.lineno}: `{ast.unparse(interpolado)}`, em `{onde_esta}`"
            )

    # RÉGUA QUE NÃO CONFERIU NADA NÃO É RÉGUA VERDE. Sem esta linha, apagar a
    # régua da FORMA acima deixaria esta passando sobre ZERO navegações — o
    # laço inteiro cairia no `continue` e o `assert` final acharia a lista
    # vazia. É a forma exata do defeito que esta leva fecha.
    assert conferidas, (
        "nenhuma navegação com a forma esperada foi conferida. Ou o retratista "
        "não abre mais nada, ou a régua da FORMA "
        "(`test_a_foto_so_nasce_de_pagina_do_repositorio`) parou de valer e "
        "esta aqui virou verde sobre nada."
    )

    assert not sem_procedencia, (
        "o retratista fotografa um caminho cuja procedência não chega ao "
        "`onde`:\n  "
        + "\n  ".join(sem_procedencia)
        + "\n\n`onde.py` é o dono único das duas pastas de página (a bancada e "
        "o publicado), e é ele que torna a origem da foto uma página do "
        "repositório POR CONSTRUÇÃO. Só a página versionada passa pelos "
        "portões de anonimato desta casa (test_docs_mac_anonimato, por OUI; "
        "check_endereco_de_radio.py, por forma); o que for montado à mão não "
        "passa por nenhum, e a foto vai para o README sem revisão humana."
    )


#: OS DESTINOS QUE NENHUM LITERAL DO RETRATISTA PODE NOMEAR. Voltou em
#: 08/09/2026 — ver :func:`test_nenhum_literal_do_retratista_aponta_para_fora`.
#: `/tmp` NÃO está aqui de propósito: o retratista grava o PNG lá no modo
#: rascunho, e proibi-lo cobraria o legítimo. Quem barra `/tmp` como FONTE é a
#: metade da FORMA, que só aceita `file://` de um nome vindo do dono.
_FONTES_PROIBIDAS = ("/home/", "~/", "http://", "https://", "/proc/", "/sys/", "/run/")


def test_nenhum_literal_do_retratista_aponta_para_fora() -> None:
    """A TERCEIRA METADE, e ela é a rede que as outras duas não alcançam.

    **POR QUE ELA VOLTOU — 08/09/2026, e a medição é do conferente.** As duas
    metades acima (FORMA e PROCEDÊNCIA) nasceram hoje no lugar de uma varredura
    de literais, e a troca foi melhor em duas mordidas e **PIOR em duas outras**,
    porque as duas só olham o argumento do ``goto``:

    * ``pg.evaluate("u => location.assign(u)", "http://localhost:8080/vivo")``
      ao lado de um ``goto`` legítimo — navegação por FORA do ``goto``, e o
      arquivo já chama ``pg.evaluate`` com string de JS. **Verde nas duas
      metades**, vermelho na varredura de literais que tinha saído;
    * um ``onde`` local (``types.SimpleNamespace``) cuja pergunta ao dono devolve
      ``/proc/self/environ`` — que é **literalmente o "segundo dono do caminho"
      que a docstring da PROCEDÊNCIA diz impedir**: ela confia no NOME ``onde``
      sem conferir de onde ele vem.

    *Trocar uma rede por outra deixa passar o que só a primeira pegava.* As três
    metades são ADITIVAS: a FORMA diz que forma o argumento tem, a PROCEDÊNCIA
    diz de onde o nome vem, e esta diz que **nenhum literal do arquivo inteiro**
    nomeia um destino de fora — esteja ele num ``goto``, num ``evaluate``, num
    ``SimpleNamespace`` de mentira ou numa constante de módulo.

    A MORDIDA: ponha ``"http://localhost:8080/vivo"`` em qualquer lugar do
    retratista e esta régua reprova nomeando o literal e a linha.
    """
    achados: list[str] = []
    for no in ast.walk(_arvore()):
        if not isinstance(no, ast.Constant) or not isinstance(no.value, str):
            continue
        texto = no.value
        if texto.startswith(_FONTES_PROIBIDAS) or any(
            f" {p}" in texto or f'"{p}' in texto or f"'{p}" in texto
            for p in _FONTES_PROIBIDAS
        ):
            achados.append(f"{SCRIPT.name}:{no.lineno}: {texto[:70]!r}")

    assert not achados, (
        "o retratista tem literal apontando para fora do repositório — o lar de "
        "quem roda, a rede, ou o `/proc`:\n  " + "\n  ".join(achados) + "\n"
        "Uma foto que nasce de qualquer uma dessas fontes pode carregar dado "
        "dela para dentro de `docs/usage/assets/`, que é versionado. Se o "
        "literal é legítimo (uma mensagem que CITA um caminho, por exemplo), "
        "declare-o com a razão — nunca afrouxe a lista.")
