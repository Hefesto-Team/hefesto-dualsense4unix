"""APLICAR-NAO-PERSISTE-01 — o botão que a documentação dizia que salvava.

`docs/usage/interface.md`, na seção **O rodapé**, dizia que *"**Aplicar**,
**Salvar Perfil**, **Importar** e **Restaurar Default** persistem o que está
editado para o perfil corrente"*. Para três dos quatro é verdade. Para o
**Aplicar** — o botão mais usado da janela — é falso: ele despacha
`profile.apply_draft` pelo IPC e **não abre arquivo nenhum**. O efeito é no
aparelho, e some no próximo perfil que entrar.

Era a linha que a documentação usava para dizer a ela **onde o trabalho fica
salvo**. O erro custa um perfil: ajustar, apertar Aplicar, ver o controle
obedecer e fechar a janela.

O que estes testes travam:

- **o `on_apply_draft` continua sem escrever em disco.** É o que sustenta a
  frase nova; sem esta asserção, um `save_profile` colado ali passa calado e a
  documentação vira mentira ao contrário;
- **e continua despachando pelo IPC** — se ele parar de fazer isso, o botão
  deixou de ser o que a tabela descreve;
- **os outros três continuam gravando**, e pelo funil único
  (`GRAVA-POR-UM-FUNIL-01`): a tabela promete "sim" para eles;
- **a tabela do documento não volta a prometer persistência no Aplicar.**

A mordida: colando uma gravação dentro do `on_apply_draft` — ou devolvendo a
frase antiga ao `interface.md` — os testes reprovam nomeando o que quebrou.

Nada aqui abre GTK, socket ou controle: é leitura do fonte com `ast` e do
documento.

E a leitura é do ARQUIVO, não do módulo importado. A distinção não é estilo:
`app/actions/footer_actions.py` puxa `app/gui_dialogs.py`, que faz `import gi`
sem guarda (`gui_dialogs.py:16`). No perfil do CI — `setup-python`, que não
enxerga o `dist-packages` onde moram `PyGObject` e `pycairo` — esse import
derrubava a COLETA deste módulo, e os quatro testes daqui sumiam sem reprovar
nada. Medido em 15/08/2026: era o `ERROS=1` do passo "Censo de coleta".

O teste que analisa texto não precisa executar o texto — e esta docstring
prometia isso desde o primeiro dia, enquanto a linha de import dizia o
contrário.
"""

from __future__ import annotations

import ast
import re
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INTERFACE_MD = REPO_ROOT / "docs" / "usage" / "interface.md"
FOOTER_ACTIONS_PY = (
    REPO_ROOT / "src" / "hefesto_dualsense4unix" / "app" / "actions" / "footer_actions.py"
)

#: Toda forma de deixar bytes no disco que este módulo tem à mão. Se o
#: `on_apply_draft` chamar qualquer uma, a linha "não persiste" caducou.
GRAVACOES = (
    r"\bsave_profile\s*\(",
    r"\b_gravar_perfil_async\s*\(",
    r"\b_persist_profile_async\s*\(",
    r"\.write_text\s*\(",
    r"\.write_bytes\s*\(",
    r"\bjson\.dump\s*\(",
    r"\bshutil\.(copy|move)",
    r"\bopen\s*\([^)]*[\"'][wax]",
)


#: O caminho INTEIRO do botão verde. O `on_apply_draft` virou despachante em
#: AGORA-E-DEPOIS-01: quem monta e envia o payload é o `_apply_draft_agora`, e
#: uma gravação escondida ali seria tão invisível quanto no handler.
CAMINHO_DO_APLICAR = ("on_apply_draft", "_aplicar_escolha_pendente", "_apply_draft_agora")


#: A classe onde os quatro botões do rodapé moram.
MIXIN = "FooterActionsMixin"


@lru_cache(maxsize=1)
def _classe_do_rodape() -> tuple[str, ast.ClassDef]:
    """O texto do arquivo e o nó da classe — parseados uma vez só."""
    texto = FOOTER_ACTIONS_PY.read_text(encoding="utf-8")
    for no in ast.parse(texto).body:
        if isinstance(no, ast.ClassDef) and no.name == MIXIN:
            return texto, no
    raise AssertionError(
        f"`{MIXIN}` sumiu de {FOOTER_ACTIONS_PY.name} — se o rodapé mudou de casa, "
        "estes testes precisam saber para onde, senão passam a não vigiar nada"
    )


def _fonte(nome: str) -> str:
    """Fonte do método SEM a docstring — senão a prosa satisfaz a asserção sozinha."""
    texto, classe = _classe_do_rodape()
    for no in classe.body:
        if isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef) and no.name == nome:
            fonte = ast.get_source_segment(texto, no) or ""
            doc = ast.get_docstring(no)
            return fonte.replace(doc, "", 1) if doc else fonte
    raise AssertionError(
        f"`{MIXIN}.{nome}` não existe mais — o caminho do botão mudou e ninguém "
        "atualizou este teste, que a partir daqui vigiaria um método fantasma"
    )


def test_aplicar_nao_escreve_em_disco() -> None:
    for nome in CAMINHO_DO_APLICAR:
        fonte = _fonte(nome)
        for padrao in GRAVACOES:
            assert not re.search(padrao, fonte), (
                f"`{nome}` passou a gravar ({padrao!r}) — a seção 'O rodapé' de "
                "docs/usage/interface.md afirma que o Aplicar NÃO persiste, e é por "
                "essa linha que ela decide se pode fechar a janela"
            )


def test_aplicar_despacha_pelo_ipc() -> None:
    fonte = _fonte("_apply_draft_agora")
    assert '"profile.apply_draft"' in fonte, (
        "o Aplicar é definido por despachar `profile.apply_draft` ao daemon (e a "
        "asserção lê o CÓDIGO, não a docstring); sem isso a tabela do documento "
        "descreve outro botão"
    )


#: O funil único por onde TODA gravação de perfil passa (GRAVA-POR-UM-FUNIL-01,
#: `actions/profile_writer.py`).
FUNIL = "_gravar_perfil_async"

#: Os três botões que gravam e o degrau deste módulo por onde cada um chega ao
#: funil. Nenhum deles chama `save_profile` na mão — daí a indireção.
QUEM_GRAVA_E_POR_ONDE = {
    "on_save_profile": "_persist_profile_async",
    "on_import_profile": "_import_save_async",
    "on_restore_default": FUNIL,
}


def test_os_outros_tres_gravam_pelo_funil() -> None:
    """A outra metade da frase: os três REALMENTE persistem (e pelo funil único)."""
    for nome, degrau in QUEM_GRAVA_E_POR_ONDE.items():
        assert re.search(rf"\b{degrau}\s*\(", _fonte(nome)), (
            f"`{nome}` deixou de chamar `{degrau}` — a tabela de "
            "docs/usage/interface.md promete 'sim' para ele"
        )
        if degrau == FUNIL:
            continue  # este já É o funil
        assert re.search(rf"\b{FUNIL}\s*\(", _fonte(degrau)), (
            f"`{degrau}` deixou de passar pelo funil `{FUNIL}` — GRAVA-POR-UM-FUNIL-01"
        )


def test_o_documento_nao_promete_persistencia_no_aplicar() -> None:
    texto = INTERFACE_MD.read_text(encoding="utf-8")
    assert not re.search(
        r"\*\*Aplicar\*\*.{0,120}persistem o que está editado",
        texto,
        re.DOTALL,
    ), (
        "a seção 'O rodapé' voltou a dizer que o Aplicar persiste — ele despacha "
        "`profile.apply_draft` pelo IPC e não abre arquivo nenhum"
    )
    assert "**Salvar Perfil**" in texto, (
        "o documento tem de nomear quem realmente salva; dizer só o que o Aplicar "
        "NÃO faz deixa a pergunta dela sem resposta"
    )
