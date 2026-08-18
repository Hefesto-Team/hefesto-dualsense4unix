"""GUARDA-GI-FALSO-SEM-GUARDA-01 — portão contra o falso-verde de GTK de mentira.

O defeito medido (onda 2, 30/07): dezessete arquivos de `tests/unit` plantam um
`gi` FALSO direto em `sys.modules` e NÃO chamam `exigir_gi_real()`. A combinação
é o pior dos mundos:

- no job `lint-test` (sem PyGObject) eles NÃO pulam, porque o stub que eles
  mesmos plantam faz o `import gi` responder que sim — então rodam verdes contra
  widgets que são `object`;
- no job `gtk-real` eles NÃO entram na seleção, porque o critério de "teste de
  interface" do CI é justamente `grep -rlE 'exigir_gi_real|skip_sem_gi_real'`.

Resultado: centenas de testes de interface que nunca, em lugar nenhum, tocam um
GTK de verdade. Este arquivo não conserta os dezessete (são de outros donos e
valem centenas de testes) — ele CONGELA a dívida: o estado de hoje está na
allowlist abaixo, nome por nome, e qualquer arquivo NOVO que entre nesse estado
reprova aqui.

A allowlist é DÍVIDA A PAGAR, não permissão. Cada nome ali é um arquivo de
interface que precisa ganhar `exigir_gi_real()` no TOPO (antes do bloco de
imports, GUARDA-GI-REAL-01) e sair desta lista. Nunca acrescente um nome novo
para "fazer o portão passar": o portão está certo e o arquivo, errado.

Por que AST e não `grep`: `tests/unit/test_input_actions_gtk.py` cita
`sys.modules["gi.repository.Gtk"]` dentro de um COMENTÁRIO e não planta stub
nenhum — um grep de texto o acusaria injustamente. O detector aqui só conta
atribuição de verdade (`sys.modules[...] = ...`, `setdefault`), então comentário
e docstring não contaminam a medição.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

TESTS_UNIT = Path(__file__).resolve().parent
ESTE_ARQUIVO = Path(__file__).resolve().name

# ---------------------------------------------------------------------------
# DÍVIDA A PAGAR — NÃO É PERMISSÃO.
#
# Os dezessete arquivos que, em 30/07/2026, plantavam `gi` falso sem a guarda.
# Medido com o detector deste módulo (e conferido com o grep da sprint).
# Tirar um nome daqui = aquele arquivo ganhou `exigir_gi_real()` e passou a
# rodar também contra o GTK real. Acrescentar um nome aqui = o portão foi
# desligado; não faça.
# ---------------------------------------------------------------------------
DIVIDA_GI_FALSO: frozenset[str] = frozenset(
    {
        "test_auto01_um_clique_em_vez_de_dez.py",
        "test_compact_window.py",
        "test_daemon_autostart.py",
        "test_daemon_status_initial.py",
        "test_daemon_status_matrix.py",
        "test_emulation_actions_modo_jogo.py",
        "test_emulation_mic_quirk.py",
        "test_lightbar_persist.py",
        "test_mode_transition_um_dono.py",
        "test_modo01_o_modo_jogo_liga_sozinho.py",
        "test_profiles_editor_mode.py",
        "test_profiles_gui_sync.py",
        "test_proton_lock_button.py",
        "test_rumble_actions.py",
        "test_status_actions_reconnect.py",
        "test_triggers_actions.py",
        "test_vpad_degradation_banner.py",
    }
)

#: Nomes de guarda aceitos: a função do `tests/conftest.py` ou o marcador irmão.
GUARDAS_ACEITAS = ("exigir_gi_real", "skip_sem_gi_real")


def _e_sys_modules(no: ast.expr) -> bool:
    """`sys.modules` (ou `modules` importado solto) como alvo de indexação."""
    if isinstance(no, ast.Attribute) and no.attr == "modules":
        return isinstance(no.value, ast.Name) and no.value.id == "sys"
    return isinstance(no, ast.Name) and no.id == "modules"


def _chave_de_gi(no: ast.expr) -> bool:
    """A chave indexada é o pacote `gi` ou um submódulo dele."""
    if isinstance(no, ast.Constant) and isinstance(no.value, str):
        return no.value == "gi" or no.value.startswith("gi.")
    return False


def plantacoes_de_gi_falso(fonte: str) -> list[int]:
    """Linhas onde a fonte GRAVA um `gi` (ou `gi.*`) cru em `sys.modules`.

    Conta só escrita de verdade:
      - `sys.modules["gi"] = ...` (e submódulos);
      - `sys.modules.setdefault("gi", ...)`.

    NÃO conta `monkeypatch.setitem(sys.modules, "gi", ...)` — esse é o caminho
    sancionado pelo `tests/conftest.py` (`instalar_stubs_gi`), desfeito no
    teardown, que não vaza o stub para o arquivo seguinte.
    """
    try:
        arvore = ast.parse(fonte)
    except SyntaxError:  # pragma: no cover — arquivo quebrado é problema de outro portão
        return []
    linhas: list[int] = []
    for no in ast.walk(arvore):
        alvos: list[ast.expr] = []
        if isinstance(no, ast.Assign):
            alvos = list(no.targets)
        elif isinstance(no, ast.AnnAssign | ast.AugAssign):
            alvos = [no.target]
        for alvo in alvos:
            if (
                isinstance(alvo, ast.Subscript)
                and _e_sys_modules(alvo.value)
                and _chave_de_gi(alvo.slice)
            ):
                linhas.append(no.lineno)
        if (
            isinstance(no, ast.Call)
            and isinstance(no.func, ast.Attribute)
            and no.func.attr == "setdefault"
            and _e_sys_modules(no.func.value)
            and no.args
            and _chave_de_gi(no.args[0])
        ):
            linhas.append(no.lineno)
    return sorted(set(linhas))


def tem_guarda_de_gi_real(fonte: str) -> bool:
    """A fonte CHAMA `exigir_gi_real(...)` ou usa o marcador `skip_sem_gi_real`.

    Também por AST: menção em comentário ou docstring não vale como guarda
    (era assim que o arquivo passava a valer como "de interface" sem ser).
    """
    try:
        arvore = ast.parse(fonte)
    except SyntaxError:  # pragma: no cover
        return False
    for no in ast.walk(arvore):
        if isinstance(no, ast.Call):
            func = no.func
            nome = (
                func.id
                if isinstance(func, ast.Name)
                else func.attr
                if isinstance(func, ast.Attribute)
                else ""
            )
            if nome in GUARDAS_ACEITAS:
                return True
        if isinstance(no, ast.Name) and no.id in GUARDAS_ACEITAS:
            return True
        if isinstance(no, ast.Attribute) and no.attr in GUARDAS_ACEITAS:
            return True
    return False


def arquivos_em_falta() -> dict[str, list[int]]:
    """`{nome: linhas}` de todo arquivo de tests/unit que planta gi falso sem guarda."""
    achados: dict[str, list[int]] = {}
    for caminho in sorted(TESTS_UNIT.glob("test_*.py")):
        if caminho.name == ESTE_ARQUIVO:
            continue
        fonte = caminho.read_text(encoding="utf-8")
        linhas = plantacoes_de_gi_falso(fonte)
        if linhas and not tem_guarda_de_gi_real(fonte):
            achados[caminho.name] = linhas
    return achados


class TestPortaoDoGiFalso:
    def test_nenhum_arquivo_novo_planta_gi_falso_sem_a_guarda(self) -> None:
        novos = {
            nome: linhas
            for nome, linhas in arquivos_em_falta().items()
            if nome not in DIVIDA_GI_FALSO
        }
        detalhe = "\n".join(f"  - {n} (linhas {ls})" for n, ls in sorted(novos.items()))
        assert not novos, (
            "arquivo(s) de tests/unit plantando `gi` FALSO em sys.modules SEM "
            "chamar exigir_gi_real():\n"
            f"{detalhe}\n"
            "Assim eles rodam verdes contra widgets de mentira no lint-test e "
            "NUNCA entram no job gtk-real (que seleciona por "
            "grep exigir_gi_real|skip_sem_gi_real).\n"
            "Cura: chame exigir_gi_real() no TOPO do arquivo, antes do bloco de "
            "imports (GUARDA-GI-REAL-01) — ou troque o stub cru pelo "
            "instalar_stubs_gi(monkeypatch) do tests/conftest.py.\n"
            "NÃO acrescente o nome à allowlist DIVIDA_GI_FALSO: ela é dívida "
            "medida em 30/07, não permissão para dívida nova."
        )

    def test_allowlist_nao_tem_nome_fantasma(self) -> None:
        # Arquivo renomeado/apagado deixa a permissão pendurada em nome que não
        # existe mais — e um dia um arquivo NOVO nasce com esse nome já isento.
        fantasmas = sorted(n for n in DIVIDA_GI_FALSO if not (TESTS_UNIT / n).exists())
        assert not fantasmas, (
            f"nomes na allowlist que não existem mais em tests/unit: {fantasmas} "
            "— tire-os da lista (a dívida daquele arquivo morreu com ele)."
        )


class TestODetectorMorde:
    """O portão acima só vale se o detector realmente detecta — a prova aqui.

    Sem estes casos, um detector que devolvesse sempre `[]` passaria o portão
    inteiro para sempre (o falso-verde do falso-verde).
    """

    @pytest.mark.parametrize(
        "fonte",
        [
            'import sys\nsys.modules["gi"] = object()\n',
            'import sys\nsys.modules["gi.repository"] = object()\n',
            'from sys import modules\nmodules["gi"] = object()\n',
            'import sys\nsys.modules.setdefault("gi", object())\n',
        ],
        ids=["gi", "submodulo", "modules-solto", "setdefault"],
    )
    def test_pega_quem_planta(self, fonte: str) -> None:
        assert plantacoes_de_gi_falso(fonte), "plantação de gi falso passou batida"

    @pytest.mark.parametrize(
        "fonte",
        [
            '# sys.modules["gi"] = object()\n',
            '"""doc citando sys.modules["gi"] = object()."""\n',
            "CHAVE = 'sys.modules[\"gi\"]'\n",
            'import sys\nmonkeypatch.setitem(sys.modules, "gi", object())\n',
        ],
        ids=["comentario", "docstring", "string", "setitem-isolado"],
    )
    def test_nao_acusa_quem_so_menciona(self, fonte: str) -> None:
        assert not plantacoes_de_gi_falso(fonte)

    def test_arquivo_real_que_so_cita_em_comentario_nao_e_acusado(self) -> None:
        # Regressão viva: test_input_actions_gtk.py cita a expressão num
        # comentário e não tem guarda — o grep de texto da sprint o pegaria.
        alvo = TESTS_UNIT / "test_input_actions_gtk.py"
        if not alvo.exists():  # pragma: no cover — arquivo pode ser renomeado
            pytest.skip("test_input_actions_gtk.py não está mais aqui")
        assert alvo.name not in arquivos_em_falta()

    def test_guarda_por_chamada_conta_e_por_comentario_nao(self) -> None:
        assert tem_guarda_de_gi_real("exigir_gi_real()\n")
        assert tem_guarda_de_gi_real("import pytest\n@skip_sem_gi_real\ndef f(): ...\n")
        assert not tem_guarda_de_gi_real("# exigir_gi_real() — prometido, não feito\n")
        assert not tem_guarda_de_gi_real('"""fala de exigir_gi_real na docstring."""\n')
