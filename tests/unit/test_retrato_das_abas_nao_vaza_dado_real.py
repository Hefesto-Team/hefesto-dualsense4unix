"""O retratista das abas não pode fotografar dado REAL dela."""

from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

SCRIPT = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "olhar.py"

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

_DONO_DA_PAGINA = "onde"
_PERGUNTAS_AO_DONO = ("pagina", "paginas")  # noqa-acento: nome de função do `onde`

_ESQUEMA_PERMITIDO = "file://"


def _fonte() -> str:
    assert SCRIPT.is_file(), (
        f"{SCRIPT} sumiu. Se o retratista mudou de casa de novo, este portão "
        "muda com ele — apagá-lo é deixar a próxima foto publicar o MAC dela."
    )
    return SCRIPT.read_text(encoding="utf-8")


def _arvore() -> ast.Module:
    return ast.parse(_fonte())


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
    if isinstance(exp, ast.Subscript):
        return _nasce_no_dono(exp.value, escopo, arvore, visto)
    if isinstance(exp, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
        return all(
            _nasce_no_dono(g.iter, escopo, arvore, visto) for g in exp.generators
        )
    if isinstance(exp, ast.Name):
        return _nome_nasce_no_dono(exp.id, escopo, arvore, visto)
    return False


def _nome_nasce_no_dono(nome: str, escopo: ast.FunctionDef, arvore: ast.Module,
                        visto: frozenset[tuple[str, int]]) -> bool:
    """Todo caminho que liga `nome` dentro de `escopo` nasce no dono?"""
    chave = (nome, id(escopo))
    if chave in visto:
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
    if not chamadas:
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
    """Toda navegação do retratista abre `file://` de um nome, e nada mais."""
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
    """A única interpolação de `f"file://{...}"` — ou `None` se a forma não bate."""
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
    """O nome que o `goto` abre nasce numa pergunta ao `onde`, e só nela."""
    arvore = _arvore()
    sem_procedencia: list[str] = []
    conferidas = 0
    for no in _navegacoes(arvore):
        alvo = no.args[0] if no.args else _argumento_em(no, 0, "url")
        if alvo is None:
            continue
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


_FONTES_PROIBIDAS = ("/home/", "~/", "http://", "https://", "/proc/", "/sys/", "/run/")


def test_nenhum_literal_do_retratista_aponta_para_fora() -> None:
    """A TERCEIRA METADE, e ela é a rede que as outras duas não alcançam."""
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
