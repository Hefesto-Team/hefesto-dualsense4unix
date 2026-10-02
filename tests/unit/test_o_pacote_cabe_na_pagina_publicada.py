"""O PORTÃO DOS DOIS MUNDOS — o pacote cabe na página que o produto renderiza?"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

_RAIZ = pathlib.Path(__file__).resolve().parents[2]
_PUBLICADO = _RAIZ / "src/hefesto_dualsense4unix/interface/paginas"
_PACOTES = _RAIZ / "src/hefesto_dualsense4unix/interface/pacotes"


def _opcoes_por_campo(html: str) -> dict[str, set[str]]:
    """Para cada `<select data-campo=...>`, o conjunto de textos que ele aceita."""
    achado: dict[str, set[str]] = {}
    for m in re.finditer(r"<select\b([^>]*)>(.*?)</select>", html, re.S):
        atributos, corpo = m.group(1), m.group(2)
        campo = re.search(r'data-campo="([^"]+)"', atributos)
        if not campo:
            continue
        textos = {
            t.strip()
            for t in re.findall(r"<option[^>]*>([^<]*)</option>", corpo)
            if t.strip()
        }
        achado.setdefault(campo.group(1), set()).update(textos)
    return achado


def _paginas() -> list[pathlib.Path]:
    return sorted(p for p in _PUBLICADO.glob("[01]*.html"))


def _pacote_da(pagina: pathlib.Path) -> pathlib.Path | None:
    return next(iter(_PACOTES.glob(f"a{pagina.name[:2]}_*.py")), None)


EXCECOES_DATADAS: dict[str, str] = {}


def _constantes(arvore: ast.Module) -> dict[str, str]:
    """`NOME = "texto"` no topo do módulo. É onde os rótulos moram."""
    achado: dict[str, str] = {}
    for no in arvore.body:
        if not isinstance(no, ast.Assign) or len(no.targets) != 1:
            continue
        alvo = no.targets[0]
        if (isinstance(alvo, ast.Name)
                and isinstance(no.value, ast.Constant)
                and isinstance(no.value.value, str)):
            achado[alvo.id] = no.value.value
    return achado


def _textos_de(valor: ast.expr, consts: dict[str, str]) -> set[str]:
    """Os textos que esta expressão pode virar. Só o que dá para saber lendo."""
    if isinstance(valor, ast.Constant) and isinstance(valor.value, str):
        return {valor.value}
    if isinstance(valor, ast.Name) and valor.id in consts:
        return {consts[valor.id]}
    if isinstance(valor, ast.IfExp):
        return _textos_de(valor.body, consts) | _textos_de(valor.orelse, consts)
    return set()


def _o_que_o_pacote_manda_para(campo: str, arvore: ast.Module,
                               consts: dict[str, str]) -> set[str]:
    """Os textos que o pacote ESCREVE neste campo — por AST, não por vizinhança."""
    achado: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Assign):
            for alvo in no.targets:
                if (isinstance(alvo, ast.Subscript)
                        and isinstance(alvo.slice, ast.Constant)
                        and alvo.slice.value == campo):
                    achado |= _textos_de(no.value, consts)
        elif isinstance(no, ast.Dict):
            for chave, valor in zip(no.keys, no.values, strict=False):
                if (isinstance(chave, ast.Constant) and chave.value == campo):
                    achado |= _textos_de(valor, consts)
    return achado


def test_nenhum_pacote_escreve_opcao_que_a_pagina_publicada_nao_tem() -> None:
    """MORDE o defeito das três frentes, e sem abrir uma janela."""
    queixas: list[str] = []
    for pagina in _paginas():
        pacote = _pacote_da(pagina)
        if pacote is None:
            continue
        opcoes = _opcoes_por_campo(pagina.read_text(encoding="utf-8"))
        if not opcoes:
            continue
        arvore = ast.parse(pacote.read_text(encoding="utf-8"))
        consts = _constantes(arvore)

        for campo, aceitos in sorted(opcoes.items()):
            for texto in sorted(_o_que_o_pacote_manda_para(campo, arvore, consts)):
                if texto in aceitos:
                    continue
                chave = f"{pacote.name}::{campo}::{texto}"
                if chave in EXCECOES_DATADAS:
                    continue
                queixas.append(
                    f"{pacote.name} manda {texto!r} para o campo {campo!r}, e "
                    f"{pagina.name} só aceita {sorted(aceitos)}"
                )

    assert not queixas, (
        "PACOTE E PÁGINA PUBLICADA NÃO SE FALAM — o produto vai emitir um "
        "texto que a tela descarta EM SILÊNCIO, e o que fica na tela é o que o "
        "desenho cravou:\n  - " + "\n  - ".join(queixas) + "\n\n"
        "Isto derrubou TRÊS frentes em 02/09/2026. A cura tem de valer nos "
        "DOIS mundos: aceite também o rótulo que a página publicada oferece, "
        "ou emita o rótulo que a página carregada tem. Se for dívida "
        "declarada, ponha em EXCECOES_DATADAS com a razão e a data."
    )


def test_a_lista_de_excecoes_nao_guarda_fantasma() -> None:
    """Exceção que já não existe é lista mentindo sobre o tamanho da dívida."""
    vivos: set[str] = set()
    for pagina in _paginas():
        pacote = _pacote_da(pagina)
        if pacote is None:
            continue
        arvore = ast.parse(pacote.read_text(encoding="utf-8"))
        consts = _constantes(arvore)
        for campo in _opcoes_por_campo(pagina.read_text(encoding="utf-8")):
            for texto in _o_que_o_pacote_manda_para(campo, arvore, consts):
                vivos.add(f"{pacote.name}::{campo}::{texto}")

    mortas = sorted(set(EXCECOES_DATADAS) - vivos)
    assert not mortas, (
        f"a lista guarda exceção que já morreu: {mortas}. Apague a linha — a "
        "dívida é menor do que ela diz."
    )


def _enderecos_da_pagina(html: str) -> set[str]:
    return set(re.findall(r'data-(?:campo|hef)="([^"]+)"', html))


@pytest.mark.parametrize(
    "pagina", _paginas(), ids=lambda p: p.name  # (noqa-acento) nome de parâmetro
)
def test_a_pagina_publicada_tem_endereco_para_o_que_a_aba_promete(
    pagina: pathlib.Path,
) -> None:
    """Um `<select>` com `data-campo` que ninguém escreve fica no desenho."""
    html = pagina.read_text(encoding="utf-8")
    selects = _opcoes_por_campo(html)
    if not selects:
        pytest.skip(f"{pagina.name} não tem select endereçado")

    pacote = _pacote_da(pagina)
    if pacote is None:
        pytest.skip(f"{pagina.name} não tem pacote")

    fonte = pacote.read_text(encoding="utf-8")
    orfaos = sorted(c for c in selects if f'"{c}"' not in fonte and f"'{c}'" not in fonte)

    assert len(orfaos) <= len(selects), (
        f"{pagina.name}: {len(orfaos)} de {len(selects)} campos de escolha não "
        f"têm ninguém que os escreva: {orfaos}. Cada um deles mostra a opção "
        "que o desenho cravou, e o segundo clique parece o primeiro."
    )


_PAGINA_DE_MENTIRA = """
<select data-campo="teclado-estado">
  <option>Ligada — atalhos e teclado na tela</option>
  <option>Só fora do jogo</option>
  <option>Desligada</option>
</select>
"""


def _acusacoes(fonte: str, html: str = _PAGINA_DE_MENTIRA) -> set[str]:
    arvore = ast.parse(fonte)
    consts = _constantes(arvore)
    fora: set[str] = set()
    for campo, aceitos in _opcoes_por_campo(html).items():
        for texto in _o_que_o_pacote_manda_para(campo, arvore, consts):
            if texto not in aceitos:
                fora.add(texto)
    return fora


def test_a_regua_pega_o_defeito_que_derrubou_a_navegacao() -> None:
    """O caso REAL de 02/09: o pacote emite um rótulo que a página não tem."""
    defeito = (
        'TECLADO_DESATIVADO = "Desativado"\n'
        "def pacote():\n"
        '    mesa = {}\n'
        '    mesa["teclado-estado"] = TECLADO_DESATIVADO\n'
        "    return mesa\n"
    )
    assert "Desativado" in _acusacoes(defeito), (
        "a régua NÃO pegou o defeito que devolveu a Navegação — ela passaria "
        "verde sobre o clique morto e sobre a tela afirmando o contrário"
    )

    defeito_dict = (
        "def pacote():\n"
        '    return {"campos": {"teclado-estado": "Só dentro do jogo"}}\n'
    )
    assert "Só dentro do jogo" in _acusacoes(defeito_dict), (
        "a régua só enxerga a atribuição por índice, e metade dos pacotes "
        "emite por dicionário literal"
    )


def test_a_regua_poupa_o_decorador_e_a_docstring() -> None:
    """As DUAS versões anteriores desta régua acusaram inocentes."""
    inocente = (
        'def outra():\n'
        '    """A lista teclado-estado oferece Ligada — atalhos e teclado na tela,\n'
        '    Só fora do jogo e Desligada. Esta prosa NÃO é uma emissão."""\n'
        '\n'
        '@gesto("06-navegacao.html", "teclado-estado")\n'
        "def teclado(ctx, o, ponte):\n"
        '    """Escolher aqui liga ou desliga; ver `Só dentro do jogo`."""\n'
        "    return None\n"
    )
    assert not _acusacoes(inocente), (
        "a régua voltou a acusar prosa e decorador: "
        f"{sorted(_acusacoes(inocente))}"
    )


def test_a_regua_resolve_os_dois_ramos_de_uma_escolha() -> None:
    """`A if cond else B` é como um pacote escolhe entre dois rótulos."""
    fonte = (
        "def pacote(ligado):\n"
        '    return {"teclado-estado": "Só fora do jogo" if ligado else "Desativado"}\n'
    )
    fora = _acusacoes(fonte)
    assert fora == {"Desativado"}, (
        f"a régua devia acusar só o ramo errado, e devolveu {sorted(fora)}"
    )
