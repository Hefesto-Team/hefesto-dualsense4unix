"""A aba Perfis saía da foto como casca vazia — PERFIS-NA-FOTO-01, 13/08/2026.

`scripts/gui-captura/retratar_abas.py` existe para curar um defeito que o
próprio docstring dele nomeia no antecessor: o `retrato_offscreen.py` "mostra a
janela VAZIA: combos sem itens". Só que ele reproduzia esse mesmo defeito na
aba **mais editada da janela**.

O que a foto publicada em `docs/usage/assets/readme_perfis.png` mostrava até
aqui, medido na imagem:

* "Aplica a:" **sem um único botão** — o seletor segmentado é montado em
  código (`install_profiles_tab`), não no glade;
* o frame "Modo (o que este perfil liga ao ativar)" **vazio** — idem
  (`_install_mode_section`);
* a lista "Perfis salvos" **sem uma linha**.

Ou seja: três dos quatro blocos da aba estavam fora da documentação.

A MORDIDA
---------

Arrancando a chamada `_montar_aba_perfis(builder)` do `main` do script, o
`test_o_main_monta_a_aba_perfis` reprova nomeando a linha que sumiu.
Arrancando o corpo da função — a chamada a `install_profiles_tab()` —, os três
testes de contagem reprovam dizendo quantos botões a aba perdeu.

A SEGUNDA COISA QUE ESTE ARQUIVO TRAVA
--------------------------------------

`install_profiles_tab` é método de PRODUÇÃO, e produção lê o disco dela e
**fala com o daemon vivo** (`_sync_selection_with_active_profile` chama
`daemon.status`). Medido em 13/08/2026, na primeira rodada da função antes do
desvio: o log saiu com `perfis_selecao_automatica_recusada
pedido=<perfil real dela>`. Um script que grava DIRETO em `docs/` não pode ter
essa porta aberta — é a mesma regra que o
`test_retrato_das_abas_nao_vaza_dado_real.py` guarda, agora com o caminho novo
que a aba Perfis abriu.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`. Contra o stub
# (`Gtk.Box = object`) a contagem de botões deste arquivo passaria sem que
# botão nenhum existisse.
exigir_gi_real("a aba Perfis na foto da documentação")

import ast
import importlib.util
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions import profiles_actions as pa

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "gui-captura" / "retratar_abas.py"


def _script() -> Any:
    """Importa o script de retrato como módulo, sem rodar o `main`."""
    assert SCRIPT.is_file(), f"{SCRIPT} sumiu — o retrato das abas é rotina desta casa"
    spec = importlib.util.spec_from_file_location("_retratar_abas_sob_teste", SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _botoes(raiz: Any) -> list[Any]:
    """Todo `Gtk.Button` abaixo de `raiz`, em qualquer profundidade.

    Recursivo de propósito: o `SegmentedSelector` embrulha os botões em caixas
    e num `ScrolledWindow`, e uma contagem só dos filhos diretos devolveria
    zero mesmo com a aba montada.
    """
    achados: list[Any] = []
    if isinstance(raiz, Gtk.Button):
        achados.append(raiz)
    if isinstance(raiz, Gtk.Container):
        for filho in raiz.get_children():
            achados.extend(_botoes(filho))
    return achados


def _aba_perfis_montada() -> tuple[Any, str]:
    """Monta a janela como o `main` monta, e devolve o builder e o recado."""
    modulo = _script()
    builder = Gtk.Builder()
    builder.add_from_file(str(modulo.GLADE))
    notebook = builder.get_object("main_notebook")
    assert notebook is not None, "`main_notebook` sumiu do glade"

    janela = Gtk.OffscreenWindow()
    pai = notebook.get_parent()
    if pai is not None:
        pai.remove(notebook)
    janela.add(notebook)
    janela.set_size_request(modulo.LARGURA, modulo.ALTURA)
    janela.show_all()

    recado = modulo._montar_aba_perfis(builder)
    modulo._assentar()
    return builder, recado


def test_o_seletor_aplica_a_tem_botoes_na_foto() -> None:
    """"Aplica a:" sem botão é o retrato de uma pergunta sem resposta."""
    builder, recado = _aba_perfis_montada()
    slot = builder.get_object("profile_aplica_a_slot")
    assert slot is not None, "`profile_aplica_a_slot` sumiu do glade"

    achados = _botoes(slot)
    esperados = len(pa._APLICA_A_ITEMS)

    assert len(achados) >= esperados, (
        f"a foto da aba Perfis saiu com {len(achados)} botão(ões) em "
        f'"Aplica a:", e o produto tem {esperados}. Foi assim que a aba mais '
        "editada da janela chegou à documentação: com a pergunta na tela e "
        f"nenhuma resposta ao lado. O script disse: {recado!r}"
    )


def test_a_secao_modo_tem_botoes_na_foto() -> None:
    """O frame "Modo" vazio esconde a decisão que ativar um perfil toma."""
    builder, recado = _aba_perfis_montada()
    slot = builder.get_object("profile_mode_slot")
    assert slot is not None, "`profile_mode_slot` sumiu do glade"

    achados = _botoes(slot)
    esperados = len(pa._MODE_KIND_ITEMS)

    assert len(achados) >= esperados, (
        f"a foto da aba Perfis saiu com {len(achados)} botão(ões) na seção "
        f'"Modo (o que este perfil liga ao ativar)", e o produto tem '
        f"{esperados}. O script disse: {recado!r}"
    )


def test_a_lista_de_perfis_salvos_nao_sai_vazia() -> None:
    """Uma lista "Perfis salvos" vazia não ensina o que a aba faz."""
    modulo = _script()
    builder, recado = _aba_perfis_montada()
    tree = builder.get_object("profiles_tree")
    assert tree is not None, "`profiles_tree` sumiu do glade"

    store = tree.get_model()
    linhas = 0 if store is None else len(store)
    esperadas = len(modulo._PERFIS_DA_FOTO)

    assert linhas == esperadas, (
        f'a lista "Perfis salvos" da foto saiu com {linhas} linha(s), e o '
        f"script inventa {esperadas} perfis para ela. O script disse: "
        f"{recado!r}"
    )


def test_o_main_monta_a_aba_perfis() -> None:
    """A função pode existir e não ser chamada — foi assim que a aba ficou casca.

    Verificação sobre o AST do `main`, e não sobre o texto do arquivo: uma
    menção em comentário ou docstring não monta aba nenhuma.
    """
    arvore = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    main = next(
        (
            no
            for no in arvore.body
            if isinstance(no, ast.FunctionDef) and no.name == "main"
        ),
        None,
    )
    assert main is not None, "o `main` sumiu do `retratar_abas.py`"

    chamadas = {
        no.func.id
        for no in ast.walk(main)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
    }

    assert "_montar_aba_perfis" in chamadas, (
        "o `main` do retrato das abas parou de chamar `_montar_aba_perfis`. "
        'A foto volta a sair com "Aplica a:" sem um botão, o frame "Modo" '
        "vazio e a lista de perfis sem linha — e ninguém percebe, porque o "
        "script continua imprimindo dez abas e gravando dez PNGs."
    )


def test_a_aba_perfis_da_foto_nao_pergunta_ao_daemon() -> None:
    """O caminho novo abriu uma porta para o daemon vivo. Ela fica fechada.

    `install_profiles_tab` termina em `_sync_selection_with_active_profile`,
    que faz `call_async("daemon.status")`. Sem o desvio, o retrato passaria a
    consultar a máquina dela a cada execução — e o nome do perfil ativo dela
    fica a um passo da imagem versionada.
    """
    fonte = SCRIPT.read_text(encoding="utf-8")
    arvore = ast.parse(fonte)

    funcao = next(
        (
            no
            for no in arvore.body
            if isinstance(no, ast.FunctionDef) and no.name == "_montar_aba_perfis"
        ),
        None,
    )
    assert funcao is not None, "`_montar_aba_perfis` sumiu do `retratar_abas.py`"

    definidos = {
        no.name for no in ast.walk(funcao) if isinstance(no, ast.FunctionDef)
    }

    assert "_sync_selection_with_active_profile" in definidos, (
        "o host da aba Perfis parou de sobrescrever "
        "`_sync_selection_with_active_profile`. O de produção chama "
        '`call_async("daemon.status")`: o retrato passa a falar com o daemon '
        "vivo, que é exatamente o que o cabeçalho deste script promete nunca "
        "fazer."
    )

    # Só o CÓDIGO, pela mesma razão do
    # `test_retrato_das_abas_nao_vaza_dado_real.py`: os comentários deste
    # script citam `load_all_profiles()` de propósito, para explicar o que não
    # fazer, e uma busca no texto cru reprovaria a própria explicação.
    codigo = "\n".join(
        ast.unparse(no)
        for no in ast.walk(arvore)
        if isinstance(no, (ast.Call, ast.Attribute, ast.Import, ast.ImportFrom))
    )

    assert "load_all_profiles" not in codigo, (
        "o retrato das abas passou a carregar os perfis do DISCO. Os nomes de "
        "perfil dela — jogo, janela, processo — iriam direto para "
        "`docs/usage/assets/`, que ninguém revisa a cada execução."
    )
