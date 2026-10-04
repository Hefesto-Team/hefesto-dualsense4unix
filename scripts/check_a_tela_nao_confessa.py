#!/usr/bin/env python3
"""check_a_tela_nao_confessa.py — nenhum texto de tela confessa dívida NOSSA."""
from __future__ import annotations

import ast
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
BANCADA = RAIZ / "mockup"
PUBLICADO = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "paginas"  # noqa-acento: nome de PASTA, e caminho nao leva acento
FONTE = RAIZ / "src"
PACOTES = FONTE / "hefesto_dualsense4unix" / "interface" / "pacotes"

VALOR_DE_EXECUCAO = "‹…›"


FORMA = re.compile(
    r"(?:"
    r"ainda\s+(?:n[ãa]o|falta|estamos)"
    r"|n[ãa]o\s+(?:sabemos|conseguimos|conseguimos|temos\s+como)"
    r"|(?:Hefesto|produto|aplicativo|app)\s+(?:ainda\s+)?n[ãa]o\b"
    r")",
    re.IGNORECASE,
)


CONTEXTO = 55


def _forma(texto: str) -> list[str]:
    """Os trechos com FORMA de confissão, normalizados para casar com as tabelas."""
    fora = []
    for m in FORMA.finditer(texto):
        ini = max(0, m.start() - CONTEXTO)
        fim = min(len(texto), m.end() + CONTEXTO)
        pedaco = re.sub(r"<[^>]+>", " ", texto[ini:fim])
        fora.append(" ".join(pedaco.split()))
    return fora


FATOS: dict[str, str] = {
    "o jogo ainda não recebeu este controle":
        "o sujeito é O JOGO. Estado de agora, e o número fica reservado até ele "
        "entregar — 07/09/2026",
    "a leitura ainda não chegou":
        "o sujeito é A LEITURA do aparelho. Estado de agora: o traço diz que o "
        "dado não veio ainda, não que não venha — 07/09/2026",
    "a Steam ainda não mudou de lado para ele":
        "o sujeito é A STEAM. Estado de agora, e MEDIDO: depois de escrever, o "
        "gesto do chip «Steam Input» RELÊ o `localconfig.vdf` e diz o que "
        "ficou lá. A causa comum é aquele jogo não existir naquele arquivo — a "
        "Steam só o escreve depois de o jogo ter aberto uma vez por ela —, e "
        "por isso a frase termina no que ELA faz a seguir. Calar seria pior: "
        "cantar «ligado» sobre um arquivo que não mudou é o `excecao_inerte` "
        "que a PONTE-STEAM-INPUT-01 existiu para matar — STEAM-INPUT-01, "
        "20/09/2026",
    "o Hefesto não volta a perguntar":
        "COMPORTAMENTO, nomeado por ela como legal em 07/09/2026 — a frase diz "
        "o que o botão faz",
    "o Hefesto não consegue nomear o que o sistema não nomeia":
        "LIMITE DO SISTEMA, nomeado por ela como legal em 07/09/2026 — o Linux "
        "não nomeia, e a frase o diz na mesma linha",


    "o Hefesto não confirmou":
        "ESTADO DO ATO: o pedido saiu e a confirmação não voltou. A frase diz "
        "as duas causas na mesma oração (o serviço parou, ou o controle saiu "
        "da mesa) e o que fazer — 11/09/2026",
    "o Hefesto não aplicou":
        "ESTADO DO ATO: o aparelho recusou o que foi mandado, e a frase traz o "
        "que o controle respondeu. Não é capacidade por entregar — o gesto "
        "existe e funcionou antes — 11/09/2026",
    "o Hefesto não gravou esta barra":
        "ESTADO DO ATO, com o gesto que resolve na mesma frase (tentar de "
        "novo) — 11/09/2026",
    "este gatilho ainda não tem modo":
        "o sujeito é O GATILHO, e é estado do que a pessoa escolheu: sem modo "
        "não há ajuste a fazer. A frase diz o passo que falta — 11/09/2026",

    "o Hefesto não respondeu":
        "ESTADO DO ATO que acabou de acontecer: o daemon não devolveu resposta, "
        "e a frase diz na mesma linha o que ficou como estava. É a família de "
        "*o Hefesto não está entregando o controle ao jogo agora* — cinco "
        "gestos da Navegação e da Iluminação, inclusive o das lâmpadas com o "
        "co-op ligado, em que a frase ainda nomeia o dono — 11/09/2026",
    "o Hefesto não está rodando — ligue na aba Sistema":
        "ESTADO DE AGORA, e ela diz onde ligar. O serviço parado é fato "
        "presente, não capacidade por entregar — 11/09/2026",
    "o Hefesto não conseguiu mirar este":
        "ESTADO DO ATO, e diz AS DUAS METADES: para onde o volume foi e que o "
        "perfil deste controle não mudou — 11/09/2026",
    "o Hefesto ainda não disse se este sensor está ligado":
        "ESTADO DE AGORA: o dado do daemon não chegou, e a frase diz por que "
        "alternar sem ele seria chutar — 11/09/2026",
    "o Hefesto não precisa de ponte":
        "AFIRMAÇÃO POSITIVA: pelo cabo o PipeWire publica o canal sozinho. A "
        "peneira a pega pela forma, e ela diz o contrário de uma dívida — "
        "11/09/2026",
    "o Hefesto não tem como guardar a quem esta ponte pertence":
        "LIMITE DO APARELHO, e a frase nomeia a causa na mesma oração: este "
        "controle não tem endereço fixo, então não há chave por onde guardar — "
        "11/09/2026",
    "Esta instalação ainda não tem":
        "o sujeito é A INSTALAÇÃO dela — o Proton pinado, a aplicação em massa. "
        "Fato do que está no disco desta máquina — 11/09/2026",}


#: sai com: A-TELA-SEM-O-QUE-A-REGUA-ACEITA-01
A_DIVIDA: dict[str, str] = {
    "está desenhado na tela e o Hefesto não sabe montar essa máscara":
        "`interface/pacotes/a01_jogar.py` — a tela OFERECE uma máscara que o "
        "produto não constrói. O que falta é o construtor, e a frase é o "
        "recibo disso no cartão dela — medida em 11/09/2026",
    "ainda não tem dono, e é o INVERSO":
        "`interface/pacotes/a06_navegacao.py` — a primeira metade da mesma "
        "frase, e ela precisa de chave própria: a peneira acha duas vezes na "
        "mesma oração, e cada achado casa com a janela que o cerca — medida "
        "em 11/09/2026",
    "o portão com o sinal trocado —, e ele ainda não existe":
        "`interface/pacotes/a06_navegacao.py` — a lista oferece *Só dentro do "
        "jogo* e o perfil não tem o campo que o sustenta. A opção sai da lista "
        "ou o campo nasce; as duas curas tiram a frase — medida em 11/09/2026",
    # fica: a frase descreve a escolha dela, e não uma capacidade que devemos
    "como se o Hefesto não estivesse instalado":
        "o sujeito é o JOGO excluído por ela; a frase descreve a escolha, não "
        "uma capacidade que devemos — 21/09/2026",
}


def _limpo(html: str) -> str:
    """A página SEM comentário, `<style>` e `<script>` — nesta ordem, e antes de tudo."""
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    html = re.sub(r"<style\b.*?</style>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<script\b.*?</script>", " ", html, flags=re.S | re.I)
    return html


def _dentro_da_janela(html: str) -> str:
    corte = html.find('<div class="nota">')
    return html if corte < 0 else html[:corte]


def _paginas() -> list[tuple[str, str]]:
    fora = []
    for pasta in (BANCADA, PUBLICADO):
        if not pasta.is_dir():
            continue
        for p in sorted(pasta.glob("*.html")):
            texto = _dentro_da_janela(_limpo(p.read_text(encoding="utf-8")))
            fora.append((str(p.relative_to(RAIZ)), texto))
    return fora


def _falas() -> list[tuple[str, str]]:
    """Todo `texto=` de todo `Fala(...)` de `src/`, por AST — sem importar nada."""
    fora = []
    for p in sorted(FONTE.rglob("*.py")):
        try:
            arvore = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            nome = no.func.id if isinstance(no.func, ast.Name) else (
                no.func.attr if isinstance(no.func, ast.Attribute) else "")
            if nome != "Fala":
                continue
            for kw in no.keywords:
                if kw.arg == "texto" and isinstance(kw.value, ast.Constant) \
                        and isinstance(kw.value.value, str):
                    fora.append((f"{p.relative_to(RAIZ)}:{no.lineno}",
                                 kw.value.value))
    return fora


# A TELA"* — `hefesto_vivo._recusou_dizendo` faz `str(erro)` e deposita o texto
def _arvore(p: pathlib.Path) -> ast.Module | None:
    if p not in _ARVORES:
        try:
            texto = p.read_text(encoding="utf-8")
            _ARVORES[p] = ast.parse(texto)
            _TEXTOS[p] = texto
        except (SyntaxError, UnicodeDecodeError, OSError):
            _ARVORES[p] = None
    return _ARVORES[p]


def _trecho(p: pathlib.Path, no: ast.AST) -> str:
    """A expressão como está ESCRITA no fonte, numa linha só."""
    trecho = ast.get_source_segment(_TEXTOS.get(p, ""), no) or ""
    return " ".join(trecho.split())


_ARVORES: dict[pathlib.Path, ast.Module | None] = {}
_TEXTOS: dict[pathlib.Path, str] = {}
_ESCOPOS: dict[pathlib.Path, tuple[dict, dict, dict]] = {}


def _modulo(nome: str, base: pathlib.Path, nivel: int) -> pathlib.Path | None:
    """O arquivo de um `import`, se ele morar DENTRO de `src/`."""
    if nivel:
        pasta = base.parent
        for _ in range(nivel - 1):
            pasta = pasta.parent
        rel = (nome or "").replace(".", "/")
        candidatos = ([pasta / f"{rel}.py", pasta / rel / "__init__.py"]
                      if rel else [pasta / "__init__.py"])
    else:
        if not nome:
            return None
        rel = nome.replace(".", "/")
        candidatos = [FONTE / f"{rel}.py", FONTE / rel / "__init__.py"]
    return next((c for c in candidatos if c.is_file()), None)


def _colher(corpo: list[ast.stmt], p: pathlib.Path) -> tuple[dict, dict, dict]:
    """O que um corpo declara: constantes, apelidos de import e funções."""
    constantes: dict[str, ast.expr] = {}
    apelidos: dict[str, tuple[str, pathlib.Path, str]] = {}
    funcoes: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for no in corpo:
        if isinstance(no, ast.ImportFrom):
            de = _modulo(no.module or "", p, no.level)
            for n in no.names:
                if n.name == "*":
                    continue
                inteiro = (f"{no.module}.{n.name}" if no.module else n.name)
                sub = _modulo(inteiro, p, no.level)
                if sub is not None:
                    apelidos[n.asname or n.name] = ("módulo", sub, "")
                elif de is not None:
                    apelidos[n.asname or n.name] = ("nome", de, n.name)
        elif isinstance(no, ast.Import):
            for n in no.names:
                achado = _modulo(n.name, p, 0)
                if achado is not None:
                    apelidos[n.asname or n.name.split(".")[0]] = (
                        "módulo", achado, "")
        elif isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcoes[no.name] = no
        elif isinstance(no, ast.Assign):
            for alvo in no.targets:
                if isinstance(alvo, ast.Name):
                    constantes.setdefault(alvo.id, no.value)
        elif isinstance(no, ast.AnnAssign):
            if isinstance(no.target, ast.Name) and no.value is not None:
                constantes.setdefault(no.target.id, no.value)
    return constantes, apelidos, funcoes


def _escopo(p: pathlib.Path) -> tuple[dict, dict, dict]:
    if p not in _ESCOPOS:
        arvore = _arvore(p)
        _ESCOPOS[p] = _colher(arvore.body, p) if arvore else ({}, {}, {})
    return _ESCOPOS[p]


def _dentro(fn: ast.FunctionDef | ast.AsyncFunctionDef,
            p: pathlib.Path) -> tuple[dict, dict, dict]:
    """O corpo da função INTEIRO, e não só o primeiro nível."""
    partes = [_colher([n], p) for n in ast.walk(fn) if isinstance(n, ast.stmt)]
    constantes: dict = {}
    apelidos: dict = {}
    funcoes: dict = {}
    for c, a, f in partes:
        for d, nova in ((constantes, c), (apelidos, a), (funcoes, f)):
            for k, v in nova.items():
                d.setdefault(k, v)
    return constantes, apelidos, funcoes


def _do_dono(fn: ast.FunctionDef | ast.AsyncFunctionDef, p: pathlib.Path,
             prof: int, vistos: frozenset) -> tuple[str, bool]:
    """O que uma função DEVOLVE, para a régua perguntar ao dono da frase."""
    dentro = _dentro(fn, p)
    pedacos, inteiro, achou = [], True, False
    for no in ast.walk(fn):
        if isinstance(no, ast.Return) and no.value is not None:
            achou = True
            t, c = _montar(no.value, p, dentro, prof + 1, vistos)
            pedacos.append(t)
            inteiro = inteiro and c
    if not achou:
        return VALOR_DE_EXECUCAO, False
    return f" {VALOR_DE_EXECUCAO} ".join(pedacos), inteiro


_TETO = 12


def _montar(no: ast.expr, p: pathlib.Path, local: tuple[dict, dict, dict],
            prof: int = 0, vistos: frozenset = frozenset()) -> tuple[str, bool]:
    """A frase como ela CHEGA ao cartão — e se a régua a montou inteira."""
    if prof > _TETO:
        return VALOR_DE_EXECUCAO, False
    consts, apelidos, funcoes = _escopo(p)
    l_consts, l_apelidos, l_funcoes = local
    consts = {**consts, **l_consts}
    apelidos = {**apelidos, **l_apelidos}
    funcoes = {**funcoes, **l_funcoes}

    if isinstance(no, ast.Constant):
        return ((no.value, True) if isinstance(no.value, str)
                else (VALOR_DE_EXECUCAO, False))

    if isinstance(no, ast.Name):
        chave = (p, no.id)
        if chave in vistos:
            return VALOR_DE_EXECUCAO, False
        adiante = vistos | {chave}
        if no.id in consts:
            return _montar(consts[no.id], p, local, prof + 1, adiante)
        if no.id in funcoes:
            return _do_dono(funcoes[no.id], p, prof, adiante)
        if no.id in apelidos:
            tipo, onde, orig = apelidos[no.id]
            c2, _a2, f2 = _escopo(onde)
            if tipo == "nome" and orig in c2:
                return _montar(c2[orig], onde, ({}, {}, {}), prof + 1, adiante)
            if tipo == "nome" and orig in f2:
                return _do_dono(f2[orig], onde, prof, adiante)
        return VALOR_DE_EXECUCAO, False

    if isinstance(no, ast.Attribute):
        base = no.value
        if isinstance(base, ast.Name) and apelidos.get(base.id, ("", None, ""))[0] == "módulo":
            onde = apelidos[base.id][1]
            chave = (onde, no.attr)
            if chave in vistos:
                return VALOR_DE_EXECUCAO, False
            adiante = vistos | {chave}
            c2, _a2, f2 = _escopo(onde)
            if no.attr in c2:
                return _montar(c2[no.attr], onde, ({}, {}, {}), prof + 1, adiante)
            if no.attr in f2:
                return _do_dono(f2[no.attr], onde, prof, adiante)
        return VALOR_DE_EXECUCAO, False

    if isinstance(no, ast.Call):
        if isinstance(no.func, ast.Name) and no.func.id == "str" and len(no.args) == 1:
            return _montar(no.args[0], p, local, prof + 1, vistos)
        if isinstance(no.func, (ast.Name, ast.Attribute)):
            return _montar(no.func, p, local, prof, vistos)
        return VALOR_DE_EXECUCAO, False

    if isinstance(no, ast.JoinedStr):
        pedacos, inteiro = [], True
        for parte in no.values:
            t, c = _montar(parte, p, local, prof + 1, vistos)
            pedacos.append(t)
            inteiro = inteiro and c
        return "".join(pedacos), inteiro

    if isinstance(no, ast.FormattedValue):
        t, c = _montar(no.value, p, local, prof + 1, vistos)
        return (t, c) if c else (VALOR_DE_EXECUCAO, False)

    if isinstance(no, ast.BinOp) and isinstance(no.op, ast.Add):
        a, ca = _montar(no.left, p, local, prof + 1, vistos)
        b, cb = _montar(no.right, p, local, prof + 1, vistos)
        return a + b, ca and cb

    if isinstance(no, ast.BoolOp):
        pedacos, inteiro = [], True
        for parte in no.values:
            t, c = _montar(parte, p, local, prof + 1, vistos)
            pedacos.append(t)
            inteiro = inteiro and c
        return f" {VALOR_DE_EXECUCAO} ".join(pedacos), inteiro

    if isinstance(no, ast.IfExp):
        a, ca = _montar(no.body, p, local, prof + 1, vistos)
        b, cb = _montar(no.orelse, p, local, prof + 1, vistos)
        return f"{a} {VALOR_DE_EXECUCAO} {b}", ca and cb

    return VALOR_DE_EXECUCAO, False


def _recados() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Os recados dos gestos: os que a régua LEU, e os que ela não alcançou."""
    lidos: list[tuple[str, str]] = []
    mudos: list[tuple[str, str]] = []
    for p in sorted(PACOTES.glob("*.py")):
        arvore = _arvore(p)
        if arvore is None:
            continue
        nome_do_arquivo = p.name
        for fn in ast.walk(arvore):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            local = _dentro(fn, p)
            for no in ast.walk(fn):
                if not (isinstance(no, ast.Raise) and isinstance(no.exc, ast.Call)):
                    continue
                alvo = no.exc.func
                qual = (alvo.id if isinstance(alvo, ast.Name)
                        else getattr(alvo, "attr", ""))
                if qual != "RuntimeError" or not no.exc.args:
                    continue
                texto, inteiro = _montar(no.exc.args[0], p, local)
                onde = f"{p.relative_to(RAIZ)}:{no.lineno}"
                if not inteiro and not texto.replace(VALOR_DE_EXECUCAO, "").strip():
                    mudos.append((
                        f"{nome_do_arquivo}:{fn.name} ← "
                        f"{_trecho(p, no.exc.args[0])}", onde))
                lidos.append((onde, texto))
    return lidos, mudos


SEM_LETRA: dict[str, str] = {
    "a10_perfis.py:editor_ambiente ← MSG_ESCOLHA_O_JOGO.format(procedencia=rotulo)":
        "a frase de `profiles/simple_match`, com o nome do lançador no buraco",
    "a10_perfis.py:editor_ambiente ← recado":
        "o `ambiente_recado` que `app/actions/perfis_web` monta, repassado "
        "inteiro",
    "a10_perfis.py:editor_jogo ← recado":
        "idem, no campo do jogo",
    "a01_jogar.py:mascara_do_controle ← motivo":
        "a recusa do `gamepad.mask.set`, palavra por palavra do daemon",
    "a02_controles.py:mudo ← frase":
        "a recusa do `mic.set`, montada pelo motor do microfone",
    "a02_controles.py:rota ← desfecho.motivo":
        "o campo `motivo` do desfecho de `app/actions` da rota do som",
    "a04_iluminacao.py:_cobrar_a_frase_do_desenho ← frase":
        "a frase do DONO do desenho das lâmpadas (`app/actions`), devolvida "
        "inteira quando ela difere do desfecho feliz",
    "a05_vibracao.py:parar ← motivo":
        "a recusa do `rumble.stop`, palavra do daemon",
    "a08_conexoes.py:luz_nao_acende ← resultado.porque":
        "o campo `porque` do resultado de `app/actions` da barra de luz",
    "a09_sistema.py:reiniciar ← motivo":
        "a recusa do `systemctl restart`, como o systemd a devolve",
    "a09_sistema.py:retomar ← motivo":
        "a recusa de retomar o serviço, idem",
    "a09_sistema.py:_systemctl ← f\"{recusa}{f': {detalhe}' if detalhe else '.'}\"":
        "a recusa do systemd mais o detalhe que ele mesmo dá — as duas metades "
        "vêm de fora, e o `f''` só as costura",
    'a06_navegacao.py:guardar_definicoes ← " ".join(recados)':
        "os recados juntados de várias gravações; cada um nasce no seu dono",
    'a06_navegacao.py:guardar_ponto ← " ".join(recados)':
        "idem, pelo Guardar do Estilo Point-and-click — os dois costuram as "
        "mesmas três frases (o atalho que para de valer, a linha sem "
        "atendente, o desenho congelado), e cada uma tem o seu dono",
    "a02_controles.py:mudo ← acao.dica":
        "a dica da ação de microfone, que mora no dono da ação",

    "a01_jogar.py:_plano ← painel.porque_nao_aplica(chave)":
        "`app/actions/jogar/painel.py:porque_nao_aplica` — a razão do cinza, "
        "montada por chave",
    "a01_jogar.py:reconectar ← _painel().RECONECTAR_SEM_SERVICO":
        "`app/actions/jogar/painel.py:RECONECTAR_SEM_SERVICO` — o import é "
        "tardio e vem por uma função, então a régua perde o rastro",
    "a09_sistema.py:restaurar_de_fabrica ← _rodape.frase_do_preset_ausente()":
        "`app/actions/footer_actions.py:frase_do_preset_ausente`",

    'a01_jogar.py:_plano_do_chip ← BOTOES_SEM_DONO.get(f"modo-{chave}", "sem dono no produto")':
        "o valor sai de um dicionário pela chave do clique; as frases estão no "
        "próprio `a01_jogar.py`, e ler qual delas sai pediria saber a chave",
}


def main() -> int:
    achados: list[str] = []
    vistas: set[str] = set()

    lidos, mudos = _recados()
    for onde, texto in _paginas() + _falas() + lidos:
        for trecho in _forma(texto):
            casou = next((k for k in {**FATOS, **A_DIVIDA} if k.lower() in trecho.lower()),
                         None)
            if casou is None:
                achados.append(f"{onde}\n      …{trecho}…")
            else:
                vistas.add(casou)

    orfas = [k for k in sorted(set(FATOS) | set(A_DIVIDA)) if k not in vistas]

    chaves_mudas = {chave for chave, _ in mudos}
    nao_declarados = sorted(
        (chave, onde) for chave, onde in mudos if chave not in SEM_LETRA)
    sem_dono = [k for k in sorted(SEM_LETRA) if k not in chaves_mudas]

    if achados:
        print(f"FALHA: {len(achados)} frase(s) de tela com forma de confissão "
              f"que ninguém declarou.\n")
        for a in achados[:30]:
            print("  " + a)
        if len(achados) > 30:
            print(f"  … e mais {len(achados) - 30}.")
        print("\nA ordem dela, 07/09/2026: *\"o layout não informa os nossos")
        print("defeitos\"*. Pergunte de quem é o sujeito da frase:")
        print("  • do mundo, do aparelho, do sistema, ou estado de agora")
        print("       -> declare em FATOS, com a razão e a data.")
        print("  • NOSSO, uma capacidade que ainda devemos")
        print("       -> TIRE DA TELA. A dívida fica no mapa e na sprint,")
        print("          que são de quem desenvolve.")
        print("  • sem tempo de tirar agora -> A_DIVIDA, com o endereço e a")
        print("    data. Essa lista só encolhe.")

    if orfas:
        print(f"\nFALHA: {len(orfas)} frase(s) declarada(s) que a tela não tem mais.")
        for k in orfas:
            print(f"  {k!r}")
        print("\nTire-as da tabela: uma declaração que sobrevive à frase")
        print("envelhece calada, e a próxima pessoa a lê como se a confissão")
        print("continuasse na tela.")

    if nao_declarados:
        print(f"\nFALHA: {len(nao_declarados)} recado(s) de gesto que a régua "
              f"NÃO CONSEGUIU LER.\n")
        for chave, onde in nao_declarados:
            print(f"  {onde}\n      {chave}")
        print("\nA frase chega ao cartão dela por `str(erro)`, e aqui ela não")
        print("tem uma letra de prosa que a régua alcance. Diga de quem ela é")
        print("em SEM_LETRA — o dono costuma ser o daemon ou `app/actions/*`.")
        print("Se o dono for ESTE arquivo, escreva a frase no `raise` e a")
        print("régua passa a lê-la sozinha.")

    if sem_dono:
        print(f"\nFALHA: {len(sem_dono)} recado(s) declarado(s) em SEM_LETRA "
              f"que o fonte não tem mais.")
        for k in sem_dono:
            print(f"  {k!r}")
        print("\nTire-os da tabela, pela razão das outras duas: declaração que")
        print("sobrevive ao código vira ponto cego com aparência de cuidado.")

    if achados or orfas or nao_declarados or sem_dono:
        return 1
    print(f"OK: a tela não confessa dívida nossa — {len(FATOS)} frase(s) "
          f"legítima(s) declarada(s), {len(A_DIVIDA)} dívida(s) ainda na tela, "
          f"{len(lidos)} recado(s) de gesto lidos ({len(SEM_LETRA)} com o dono "
          f"declarado fora do alcance).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
