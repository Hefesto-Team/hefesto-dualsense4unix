"""A FAMÍLIA DO `getattr` SEM DONO — o método que achou o R-08, virado régua.

O DEFEITO QUE ESTA RÉGUA PEGA, e ele já custou duas vezes: um
``getattr(self, "_alguma_coisa", None)`` sobre um nome que **módulo nenhum de
``src/`` define**. A chamada nunca estoura — devolve o default e o ramo desce
pelo caminho de recuo, calado. Enquanto a janela GTK existia, ela é que
fornecia esses nomes; a janela saiu do disco em ``f5311616`` (06/09/2026,
``D-0609-GTK-LEVA-INTEIRA``) e os ramos ficaram apontando para fora.

AS DUAS OCORRÊNCIAS QUE ORIGINARAM A RÉGUA, e a diferença entre elas importa:

* ``_tem_edicao_pendente`` (08/09) — o recuo era *"não há nada a proteger"*:
  a guarda R-08 passava a mentir e uma edição não salva dela podia ser
  repintada por cima. **Voltou**, como ``profile_writer.tem_edicao_pendente``.
* ``_bootstrap_draft_async`` (08/09, irmão) — o recuo é ``_refresh_all_tabs``,
  documentado, que repinta a memória sem reler o disco. **Não volta**, e a
  medição de por que está na lápide A FAMÍLIA DO R-08, no fim de
  ``app/actions/profiles_actions.py``.

O QUE MEDIU AS DUAS não foi ler código com atenção — foi cruzar duas listas: os
nomes consultados por ``getattr``/``hasattr`` sobre ``self`` contra os nomes que
``src/`` define. É uma pergunta mecânica, e por isso vira régua: a próxima
pessoa não precisa ter a mesma atenção que o conferente teve.

POR QUE TESTE E NÃO PORTÃO: a lista dos portões tem um dono só
(``scripts/portoes.sh``) e ``test_portao_a_lista_de_portoes_e_uma_so.py`` exige
que ela e a do CI batam — um portão a mais é decisão de duas listas. E esta
pergunta é da CAUDA: a leva de 08/09 mediu que os 50 portões ficaram verdes com
a guarda R-08 já sem dono. Quem alcança a cauda é a suíte.

A DECLARAÇÃO NÃO É ISENÇÃO, e as três provas abaixo é que garantem isso: um
órfão declarado tem de continuar órfão (senão a declaração está velha) **e** tem
de continuar sendo consultado (senão a declaração é peso morto). Declarar sem
razão escrita não passa — a razão é campo obrigatório do dicionário.
"""

from __future__ import annotations

import ast
import collections
import pathlib
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"

#: Nome consultado por `getattr`/`hasattr` que NINGUÉM em `src/` define, com a
#: razão medida. Entrar aqui é decisão registrada, não conveniência: as três
#: provas deste arquivo cobram que a declaração continue verdadeira nos dois
#: sentidos.
ORFAOS_DECLARADOS: dict[str, str] = {
    "_bootstrap_draft_async": (
        "A peça 2 da máquina do R-08 — o carregador que RELIA o perfil ativo "
        "(IPC `state_full` + `load_all_profiles`) e refazia `draft`, "
        "`_active_profile_name` e `_draft_baseline` antes de repintar. Saiu com "
        "a janela GTK (`D-0609-GTK-LEVA-INTEIRA`, `f5311616`; o original está "
        "em `f5311616^:app/app.py:960`). O ramo que o procura degrada para "
        "`_refresh_all_tabs`, que repinta o `self.draft` que já estava em "
        "memória — o perfil ANTERIOR. Não volta porque a premissa dele (um "
        "`self.draft` guardado e atualizado a cada widget) foi decidida contra "
        "em 01/09: a interface nova é de ação imediata e lê o perfil ativo por "
        "`interface/pacotes/rodape.py:91`. A medição inteira, e o que fazer no "
        "dia em que um compositor chegar, estão na lápide A FAMÍLIA DO R-08, no "
        "fim de `app/actions/profiles_actions.py`."
    ),
}


def _arquivos() -> list[pathlib.Path]:
    arquivos = sorted(RAIZ.rglob("*.py"))
    assert arquivos, f"nenhum fonte sob {RAIZ} — a régua estaria medindo o vazio"
    return arquivos


class _Consultas(ast.NodeVisitor):
    """`getattr(self, "_x")` e `hasattr(self, "_x")` com nome literal."""

    def __init__(self, arq: pathlib.Path, saco: dict[str, list[Any]]) -> None:
        self.arq = arq
        self.saco = saco

    def visit_Call(self, node: ast.Call) -> None:
        alvo = getattr(node.func, "id", None)
        if alvo in {"getattr", "hasattr"} and len(node.args) > 1:
            quem, nome = node.args[0], node.args[1]
            if (
                isinstance(quem, ast.Name)
                and quem.id == "self"
                and isinstance(nome, ast.Constant)
                and isinstance(nome.value, str)
                and nome.value.startswith("_")
            ):
                self.saco[nome.value].append((self.arq, node.lineno))
        self.generic_visit(node)


class _Definicoes(ast.NodeVisitor):
    """Todo jeito de um nome `_x` PASSAR A EXISTIR num objeto desta casa.

    Larga de propósito: a pergunta é *"alguém em `src/` define este nome?"*, e
    uma varredura estreita transformaria um dono legítimo em falso vermelho.
    Errar para o lado do "tem dono" é o lado barato — o caro é acusar quem
    escreveu certo, que é a forma de instrumento falso que esta casa mais pagou.
    """

    def __init__(self, arq: pathlib.Path, saco: dict[str, list[Any]]) -> None:
        self.arq = arq
        self.saco = saco

    def _reg(self, nome: Any, no: ast.AST) -> None:
        if isinstance(nome, str) and nome.startswith("_"):
            self.saco[nome].append((self.arq, getattr(no, "lineno", 0)))

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._reg(node.name, node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._reg(node.name, node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for corpo in node.body:
            if isinstance(corpo, ast.AnnAssign) and isinstance(corpo.target, ast.Name):
                self._reg(corpo.target.id, corpo)
            elif isinstance(corpo, ast.Assign):
                for alvo in corpo.targets:
                    if isinstance(alvo, ast.Name):
                        self._reg(alvo.id, corpo)
        self.generic_visit(node)

    def _atributo_de_self(self, alvo: ast.AST, no: ast.AST) -> None:
        if (
            isinstance(alvo, ast.Attribute)
            and isinstance(alvo.value, ast.Name)
            and alvo.value.id == "self"
        ):
            self._reg(alvo.attr, no)
        elif isinstance(alvo, (ast.Tuple, ast.List)):
            for item in alvo.elts:
                self._atributo_de_self(item, no)

    def visit_Assign(self, node: ast.Assign) -> None:
        for alvo in node.targets:
            self._atributo_de_self(alvo, node)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._atributo_de_self(node.target, node)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._atributo_de_self(node.target, node)
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self._atributo_de_self(node.target, node)
        self.generic_visit(node)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self._atributo_de_self(node.target, node)
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            if item.optional_vars is not None:
                self._atributo_de_self(item.optional_vars, node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if getattr(node.func, "id", None) == "setattr" and len(node.args) > 1:
            quem, nome = node.args[0], node.args[1]
            if (
                isinstance(quem, ast.Name)
                and quem.id == "self"
                and isinstance(nome, ast.Constant)
            ):
                self._reg(nome.value, node)
        self.generic_visit(node)


@pytest.fixture(scope="module")
def censo() -> tuple[dict[str, list[Any]], dict[str, list[Any]]]:
    """(consultas, definições) de `src/` inteiro, lidas por `ast` uma vez só."""
    consultas: dict[str, list[Any]] = collections.defaultdict(list)
    definicoes: dict[str, list[Any]] = collections.defaultdict(list)
    for arq in _arquivos():
        arvore = ast.parse(arq.read_text(encoding="utf-8"), filename=str(arq))
        _Consultas(arq, consultas).visit(arvore)
        _Definicoes(arq, definicoes).visit(arvore)
    return consultas, definicoes


def _relativo(arq: pathlib.Path) -> str:
    return str(arq.relative_to(RAIZ.parents[1]))


def test_nenhum_getattr_de_src_aponta_para_nome_que_ninguem_define(
    censo: tuple[dict[str, list[Any]], dict[str, list[Any]]],
) -> None:
    """A varredura que achou as duas peças do R-08, agora permanente.

    MORDIDA (08/09/2026): tirado `_bootstrap_draft_async` de
    `ORFAOS_DECLARADOS`, esta prova reprova nomeando
    `app/actions/profiles_actions.py:3361`. Devolvido, verde.
    """
    consultas, definicoes = censo
    sem_dono = {
        nome: onde
        for nome, onde in consultas.items()
        if nome not in definicoes and nome not in ORFAOS_DECLARADOS
    }
    if sem_dono:
        linhas = [
            f"  {nome} — {', '.join(f'{_relativo(a)}:{n}' for a, n in onde)}"
            for nome, onde in sorted(sem_dono.items())
        ]
        pytest.fail(
            "`getattr`/`hasattr` sobre nome que módulo nenhum de `src/` define:\n"
            + "\n".join(linhas)
            + "\n\nO ramo não estoura — ele desce calado pelo caminho de recuo. "
            "Antes de declarar o nome em `ORFAOS_DECLARADOS`, meça as duas "
            "coisas que a lápide A FAMÍLIA DO R-08 mediu: o que o ramo FAZIA "
            "quando o nome tinha dono, e se o recuo entrega menos. Se entrega "
            "menos e algum caminho vivo passa ali, a cura é repor a regra — não "
            "declarar o órfão."
        )


def test_orfao_declarado_que_ganhou_dono_perde_a_declaracao(
    censo: tuple[dict[str, list[Any]], dict[str, list[Any]]],
) -> None:
    """Declaração velha é pior que nenhuma: ela silencia a régua sobre um fato
    que mudou.

    MORDIDA (08/09/2026): posto um `def _bootstrap_draft_async(self): ...` em
    `app/actions/profiles_actions.py`, esta prova reprova nomeando o arquivo e
    a linha do dono novo. Arrancado, verde.
    """
    _, definicoes = censo
    voltaram = {
        nome: definicoes[nome] for nome in ORFAOS_DECLARADOS if nome in definicoes
    }
    if voltaram:
        linhas = [
            f"  {nome} — agora definido em "
            f"{', '.join(f'{_relativo(a)}:{n}' for a, n in onde)}"
            for nome, onde in sorted(voltaram.items())
        ]
        pytest.fail(
            "órfão DECLARADO que ganhou dono em `src/`:\n"
            + "\n".join(linhas)
            + "\n\nA declaração descreve um mundo que acabou. Tire o nome de "
            "`ORFAOS_DECLARADOS` e leve junto a lápide que o explica — quem "
            "repõe a peça é quem apaga a nota que dizia por que ela faltava."
        )


def test_orfao_declarado_que_ninguem_mais_consulta_perde_a_declaracao(
    censo: tuple[dict[str, list[Any]], dict[str, list[Any]]],
) -> None:
    """O outro sentido: sem o ramo, a declaração é peso morto.

    MORDIDA (08/09/2026): trocado o `getattr` de `profiles_actions.py:3361` por
    uma chamada direta a `_refresh_all_tabs`, esta prova reprova nomeando
    `_bootstrap_draft_async`. Devolvido, verde.
    """
    consultas, _ = censo
    esquecidos = [nome for nome in ORFAOS_DECLARADOS if nome not in consultas]
    if esquecidos:
        pytest.fail(
            "órfão DECLARADO que `src/` não consulta mais: "
            + ", ".join(sorted(esquecidos))
            + "\n\nO ramo que justificava a declaração saiu. Tire o nome de "
            "`ORFAOS_DECLARADOS` — uma isenção sem ramo vivo é uma porta aberta "
            "para o próximo nome entrar sem medição."
        )


def test_o_recuo_do_carregador_deixa_a_guarda_do_r08_de_pe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O recuo repinta a memória — e NÃO pode declarar a edição dela salva.

    Esta é a metade que a declaração do órfão não cobre. Sem o carregador,
    `_recarregar_as_abas_do_perfil_ativo` cai em `_refresh_all_tabs`, que
    repinta `self.draft`. O perigo não é repintar: é alguém "consertar" o recuo
    fazendo `self._draft_baseline = self.draft` para o estado parecer coerente
    — com isso `tem_edicao_pendente` responde `False`, a guarda R-08 desliga e a
    edição não salva dela deixa de ser protegida, que é exatamente o estrago que
    a peça 1 voltou para impedir.

    MORDIDA (08/09/2026): acrescentado `self._draft_baseline = self.draft` ao
    fim de `_recarregar_as_abas_do_perfil_ativo`, esta prova reprova com
    *"o recuo apagou a edição pendente dela"*. Arrancado, verde.

    NO DIA EM QUE O CARREGADOR VOLTAR esta prova reprova junto — e é para
    reprovar. O carregador legítimo refaz a linha de base a partir do DISCO, e
    então a bancada tem de ganhar um disco em vez de perder a régua. A lápide A
    FAMÍLIA DO R-08 diz o que ele fazia, com o endereço do original.
    """
    from hefesto_dualsense4unix.app.actions import footer_actions as fa
    from hefesto_dualsense4unix.app.actions import profiles_actions as pa
    from hefesto_dualsense4unix.app.actions.profile_writer import tem_edicao_pendente

    # AS TRÊS PROVAS ACIMA LEEM O DISCO A PARTIR DO `__file__`; esta IMPORTA, e
    # o import obedece ao `PYTHONPATH`. Se os dois divergirem, este arquivo
    # estaria medindo duas árvores e chamando o resultado de uma — que é o
    # instrumento falso de 04/09, quando a suíte inteira LIA o `src/` de outra
    # árvore. Declarar qual das duas está em uso é regra desta casa.
    assert pathlib.Path(pa.__file__).resolve().is_relative_to(RAIZ), (
        f"a suíte importou `{pa.__file__}`, e a varredura leu `{RAIZ}` — duas "
        "árvores. Rode com o `PYTHONPATH` desta árvore antes de acreditar em "
        "qualquer verde deste arquivo."
    )

    repintadas: list[Any] = []
    monkeypatch.setattr(fa, "_refresh_all_tabs", repintadas.append)

    class _SoOMixin(pa.ProfilesActionsMixin):  # type: ignore[misc]
        """Nem janela nem aba: o mixin sozinho, que é o estado de `src/` hoje."""

        def __init__(self) -> None:
            # Dois `DraftConfig` diferentes = edição por salvar (R-08). Objetos
            # crus bastam: `tem_edicao_pendente` só faz `draft != baseline`.
            self._draft_baseline = object()
            self.draft = object()

    mixin = _SoOMixin()
    assert not hasattr(mixin, "_bootstrap_draft_async"), (
        "esta prova só vale enquanto o carregador não tem dono — se ele voltou, "
        "leia a lápide A FAMÍLIA DO R-08 antes de mexer aqui"
    )
    assert tem_edicao_pendente(mixin), "a bancada nasceu sem edição pendente"

    mixin._recarregar_as_abas_do_perfil_ativo()

    assert repintadas == [mixin], "o recuo não repintou as abas"
    assert tem_edicao_pendente(mixin), (
        "o recuo apagou a edição pendente dela: `_recarregar_as_abas_do_perfil_"
        "ativo` mexeu em `_draft_baseline` sem ter relido o disco. Repintar a "
        "memória não é ter salvado nada — e desligar a guarda R-08 aqui devolve "
        "o defeito que ela existe para impedir."
    )
