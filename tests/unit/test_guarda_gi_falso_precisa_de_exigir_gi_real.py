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
GTK de verdade. Este arquivo não conserta os dezessete de uma vez (são de outros
donos e valem centenas de testes) — ele CONGELA a dívida: o estado de hoje está
na allowlist abaixo, nome por nome, e qualquer arquivo NOVO que entre nesse
estado reprova aqui.

AMORTIZAÇÃO — lote A pago em 13/08/2026 (TESTE-HONESTO-01/E1, `:227-232`). Seis
arquivos ganharam ``exigir_gi_real()`` no topo e saíram da allowlist:
``test_emulation_actions_modo_jogo``, ``test_daemon_status_initial``,
``test_lightbar_persist``, ``test_daemon_autostart``, ``test_compact_window`` e
``test_emulation_mic_quirk``. Restaram **onze**, pagos em 01/10/2026. A dívida tem
``TETO_DA_DIVIDA``, e ele **só desce** — é o que impede que alguém devolva um
nome à lista para calar o portão.

A allowlist é DÍVIDA A PAGAR, não permissão. Cada nome ali é um arquivo de
interface que precisa ganhar `exigir_gi_real()` no TOPO (antes do bloco de
imports, GUARDA-GI-REAL-01) e sair desta lista. Nunca acrescente um nome novo
para "fazer o portão passar": o portão está certo e o arquivo, errado.

Por que AST e não `grep`: `tests/unit/test_input_actions_gtk.py` cita
`sys.modules["gi.repository.Gtk"]` dentro de um COMENTÁRIO e não planta stub
nenhum — um grep de texto o acusaria injustamente. O detector aqui só conta
atribuição de verdade (`sys.modules[...] = ...`, `setdefault`), então comentário
e docstring não contaminam a medição.

A ORDEM (02/10/2026, O-GI-FALSO-SO-DEPOIS-DA-GUARDA-01). O portão aceitava como
guarda qualquer menção ao marcador `skip_sem_gi_real`, e o marcador pula o
TESTE, não a importação: o p3 e o p10 plantavam o `gi` falso no topo com ele, e
a coleta sem GTK deixava 16 módulos da janela no processo, construídos sobre a
mentira, para o arquivo seguinte importar. Num arquivo que planta, a guarda que
vale é a chamada de `exigir_gi_real(...)` no nível do módulo, ANTES da primeira
instrução que planta ao importar (direto, ou chamando uma função do arquivo que
planta).
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

TESTS_UNIT = Path(__file__).resolve().parent
ESTE_ARQUIVO = Path(__file__).resolve().name

# ---------------------------------------------------------------------------
# DÍVIDA A PAGAR — NÃO É PERMISSÃO.
#
# Eram dezessete em 30/07/2026 (medido com o detector deste módulo, conferido
# com o grep da sprint). O lote A saiu em 13/08/2026 e restaram onze.
# Tirar um nome daqui = aquele arquivo ganhou `exigir_gi_real()` e passou a
# rodar também contra o GTK real. Acrescentar um nome aqui = o portão foi
# desligado; não faça — e o `TETO_DA_DIVIDA` abaixo reprova quem tentar.
# ---------------------------------------------------------------------------
# A dívida zerou em 01/10/2026 (AS-ONZE-REGUAS-DO-GTK-DE-MENTIRA-01): os onze
# ganharam `exigir_gi_real()` no topo. A lista fica, vazia, porque é ela que
# o `TETO_DA_DIVIDA` vigia: um nome que volte a ela reprova pelo teto.
DIVIDA_GI_FALSO: frozenset[str] = frozenset()

#: TETO DA DÍVIDA — o número de nomes que a allowlist ainda pode ter. **Só
#: desce.** Sem ele, a allowlist é uma lista que só cresce por descuido: bastava
#: alguém acrescentar um nome para o portão calar, e a mensagem "NÃO acrescente"
#: era só um pedido educado. Cada lote pago baixa este número junto.
#:
#: 17 em 30/07/2026 (medição original) → 11 em 13/08/2026 (lote A da E1)
#: → 0 em 01/10/2026 (AS-ONZE-REGUAS-DO-GTK-DE-MENTIRA-01).
TETO_DA_DIVIDA = 0

#: Nomes de guarda aceitos: a função do `tests/conftest.py` ou o marcador irmão.
#: Os dois declaram o arquivo como de interface; num arquivo que PLANTA, só a
#: função guarda (ver `GUARDA_DA_IMPORTACAO`).
GUARDAS_ACEITAS = ("exigir_gi_real", "skip_sem_gi_real")

#: A guarda que pula a IMPORTAÇÃO. O marcador age na hora de rodar o teste,
#: depois de o arquivo inteiro ter sido importado, plantio incluído.
GUARDA_DA_IMPORTACAO = "exigir_gi_real"


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
    arvore = _arvore(fonte)
    return _linhas_que_plantam(ast.walk(arvore)) if arvore is not None else []


def _arvore(fonte: str) -> ast.Module | None:
    try:
        return ast.parse(fonte)
    except SyntaxError:  # pragma: no cover — arquivo quebrado é problema de outro portão
        return None


def _linhas_que_plantam(nos: Iterable[ast.AST]) -> list[int]:
    linhas: list[int] = []
    for no in nos:
        if isinstance(no, ast.Assign | ast.AnnAssign | ast.AugAssign):
            alvos = list(no.targets) if isinstance(no, ast.Assign) else [no.target]
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


def _nome_da_chamada(chamada: ast.Call) -> str:
    func = chamada.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _roda_na_importacao(no: ast.AST) -> Iterator[ast.AST]:
    """Os nós que rodam quando o módulo é importado.

    O corpo de uma função (ou de um lambda) só roda quando alguém a chama, e
    fica de fora; o de uma classe, o de um `if` e o de um `try` rodam ali.
    """
    if isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
        return
    yield no
    for filho in ast.iter_child_nodes(no):
        yield from _roda_na_importacao(filho)


def _chama_alguma(nos: Iterable[ast.AST], nomes: set[str]) -> bool:
    return any(
        isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id in nomes
        for no in nos
    )


def _funcoes_que_plantam(arvore: ast.Module) -> set[str]:
    """As funções do arquivo que plantam, direto ou chamando outra que planta."""
    funcoes = {
        no.name: no
        for no in arvore.body
        if isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    plantam = {nome for nome, no in funcoes.items() if _linhas_que_plantam(ast.walk(no))}
    while True:
        novas = {
            nome
            for nome, no in funcoes.items()
            if nome not in plantam and _chama_alguma(ast.walk(no), plantam)
        }
        if not novas:
            return plantam
        plantam |= novas


def plantio_na_importacao(fonte: str) -> int | None:
    """A linha da primeira instrução de nível de módulo que planta `gi` ao importar.

    Planta direto (fora de função) ou chama uma função do arquivo que planta.
    `None` quando o plantio mora só em função que a importação não chama.
    """
    arvore = _arvore(fonte)
    if arvore is None:
        return None
    plantadoras = _funcoes_que_plantam(arvore)
    for instrucao in arvore.body:
        nos = list(_roda_na_importacao(instrucao))
        if _linhas_que_plantam(nos) or _chama_alguma(nos, plantadoras):
            return instrucao.lineno
    return None


def guarda_na_importacao(fonte: str) -> int | None:
    """A linha da primeira chamada de `exigir_gi_real(...)` no nível do módulo.

    Só a instrução solta conta (expressão ou atribuição): é ela que pula o
    módulo antes da linha seguinte. Dentro de função, ela só roda se alguém
    chamar; o marcador nem é chamada.
    """
    arvore = _arvore(fonte)
    if arvore is None:
        return None
    for instrucao in arvore.body:
        if isinstance(instrucao, ast.Expr | ast.Assign | ast.AnnAssign):
            valor = instrucao.value
            if isinstance(valor, ast.Call) and _nome_da_chamada(valor) == GUARDA_DA_IMPORTACAO:
                return instrucao.lineno
    return None


@dataclass(frozen=True)
class Falta:
    """Um arquivo que planta `gi` falso sem a guarda antes."""

    #: Toda linha que planta, dentro ou fora de função.
    plantio: tuple[int, ...]
    #: A primeira instrução de nível de módulo que planta ao importar, se há.
    na_importacao: int | None
    #: A linha do `exigir_gi_real(...)` de nível de módulo, se há.
    guarda: int | None
    #: O arquivo se declara de interface só pelo marcador (ou pela chamada
    #: dentro de função): a palavra está lá, o ato não.
    so_a_palavra: bool

    def descrever(self) -> str:
        guarda = f"linha {self.guarda}" if self.guarda is not None else "nenhuma"
        if self.guarda is None and self.so_a_palavra:
            guarda += " (só o marcador, que pula o teste e não a importação)"
        topo = (
            f"linha {self.na_importacao}"
            if self.na_importacao is not None
            else "nenhum (só dentro de função)"
        )
        return (
            f"planta nas linhas {list(self.plantio)}; plantio ao importar: {topo}; "
            f"guarda exigir_gi_real(): {guarda}"
        )


def falta_de_guarda(fonte: str) -> Falta | None:
    """`None` se a fonte não planta, ou planta com a guarda antes; senão, a falta."""
    linhas = plantacoes_de_gi_falso(fonte)
    if not linhas:
        return None
    guarda = guarda_na_importacao(fonte)
    topo = plantio_na_importacao(fonte)
    if guarda is not None and (topo is None or guarda < topo):
        return None
    return Falta(
        plantio=tuple(linhas),
        na_importacao=topo,
        guarda=guarda,
        so_a_palavra=tem_guarda_de_gi_real(fonte),
    )


def arquivos_em_falta(pasta: Path = TESTS_UNIT) -> dict[str, Falta]:
    """`{nome: falta}` de todo `test_*.py` da pasta que planta gi falso sem guarda antes."""
    achados: dict[str, Falta] = {}
    for caminho in sorted(pasta.glob("test_*.py")):
        if caminho.name == ESTE_ARQUIVO:
            continue
        falta = falta_de_guarda(caminho.read_text(encoding="utf-8"))
        if falta is not None:
            achados[caminho.name] = falta
    return achados


class TestPortaoDoGiFalso:
    def test_nenhum_arquivo_novo_planta_gi_falso_sem_a_guarda(self) -> None:
        novos = {
            nome: falta
            for nome, falta in arquivos_em_falta().items()
            if nome not in DIVIDA_GI_FALSO
        }
        detalhe = "\n".join(f"  - {n}: {f.descrever()}" for n, f in sorted(novos.items()))
        assert not novos, (
            "arquivo(s) de tests/unit plantando `gi` FALSO em sys.modules SEM "
            "chamar exigir_gi_real() no nível do módulo ANTES do plantio:\n"
            f"{detalhe}\n"
            "Sem GTK, a importação planta a mentira, e os módulos da janela "
            "construídos sobre ela ficam no processo para o arquivo seguinte. "
            "O marcador skip_sem_gi_real pula o teste, depois da importação.\n"
            "Cura: chame exigir_gi_real() no TOPO do arquivo, antes do bloco de "
            "imports (GUARDA-GI-REAL-01) — ou troque o stub cru pelo "
            "instalar_stubs_gi(monkeypatch) do tests/conftest.py.\n"
            "NÃO acrescente o nome à allowlist DIVIDA_GI_FALSO: ela é dívida "
            "medida em 30/07, não permissão para dívida nova."
        )

    def test_a_divida_so_encolhe(self) -> None:
        # A allowlist sozinha não é portão: ela cala qualquer arquivo cujo nome
        # esteja nela. O teto é o que a torna dívida — quem quiser silenciar um
        # arquivo novo acrescentando o nome tem de MEXER neste número, à vista.
        assert len(DIVIDA_GI_FALSO) <= TETO_DA_DIVIDA, (
            f"a dívida do GTK de mentira CRESCEU: {len(DIVIDA_GI_FALSO)} nomes "
            f"na DIVIDA_GI_FALSO, teto {TETO_DA_DIVIDA}.\n"
            "Nome novo na allowlist é o portão sendo desligado, não dívida "
            "nova legítima. Cure o arquivo com exigir_gi_real() (ou troque o "
            "stub cru pelo instalar_stubs_gi do tests/conftest.py) em vez de "
            "subir o teto — ele só desce (17 em 30/07, 11 em 13/08, 0 em 01/10)."
        )

    def test_allowlist_nao_guarda_arquivo_ja_pago(self) -> None:
        # Nome que já ganhou a guarda e ficou na lista é permissão pendurada:
        # se alguém arrancar o `exigir_gi_real()` daquele arquivo depois, ele
        # volta a plantar `gi` falso em silêncio, coberto pela própria isenção.
        pagos = sorted(DIVIDA_GI_FALSO - set(arquivos_em_falta()))
        assert not pagos, (
            f"nomes na allowlist que JÁ têm a guarda: {pagos} — tire-os da "
            "DIVIDA_GI_FALSO e baixe o TETO_DA_DIVIDA no mesmo commit. "
            "Isenção que sobrevive à cura vira permissão para a recaída."
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


# ---------------------------------------------------------------------------
# A ORDEM (02/10/2026, O-GI-FALSO-SO-DEPOIS-DA-GUARDA-01)
# ---------------------------------------------------------------------------
_CABECA = '''import sys
import types

from tests.conftest import exigir_gi_real, skip_sem_gi_real


def _plantar():
    sys.modules["gi"] = types.ModuleType("gi")
    sys.modules["gi.repository"] = types.ModuleType("gi.repository")

'''
#: O p3 e o p10 até 02/10: o marcador, e o plantio no topo.
_O_MARCADOR_SOZINHO = _CABECA + "pytestmark = skip_sem_gi_real\n\n_plantar()\n"
_A_GUARDA_DEPOIS = _CABECA + "_plantar()\n\nexigir_gi_real('depois')\n"
_A_GUARDA_ANTES = _CABECA + "exigir_gi_real('antes')\n\n_plantar()\n"
_A_GUARDA_ATRIBUIDA = _CABECA + "_GI = exigir_gi_real('antes')\n\n_plantar()\n"
_A_GUARDA_DENTRO_DE_FUNCAO = (
    _CABECA + "def _guardar():\n    exigir_gi_real()\n\n_plantar()\n_guardar()\n"
)
_O_PLANTIO_DIRETO_ANTES = (
    'import sys\nimport types\nfrom tests.conftest import exigir_gi_real\n\n'
    'try:\n    import gi\nexcept ImportError:\n'
    '    sys.modules["gi"] = types.ModuleType("gi")\n\nexigir_gi_real()\n'
)
_O_PLANTIO_NA_CLASSE = (
    'import sys\nimport types\nfrom tests.conftest import exigir_gi_real\n\n'
    'class _Gi:\n    sys.modules["gi"] = types.ModuleType("gi")\n\nexigir_gi_real()\n'
)
#: Uma função que chama outra que planta, chamada no topo antes da guarda.
_POR_DUAS_FUNCOES = (
    _CABECA + "def _preparar():\n    _plantar()\n\n_preparar()\n\nexigir_gi_real()\n"
)
#: O `test_o_botao_que_tira_o_que_faz_engasgar.py`: define, guarda e não chama.
_SO_DEFINE = _CABECA + "_GI_REAL = exigir_gi_real('so define')\n"


def _linha(fonte: str, texto: str) -> int:
    return fonte.splitlines().index(texto) + 1


class TestAGuardaVemAntesDoPlantio:
    """Mordidas: a regra de antes (o marcador como guarda) deixa o primeiro caso
    limpo; contar a guarda em qualquer linha deixa o segundo; ignorar a chamada
    de função que planta deixa o terceiro."""

    def test_o_marcador_sozinho_nao_guarda_o_plantio_do_topo(self, tmp_path: Path) -> None:
        nome = "test_o_marcador_sozinho.py"
        (tmp_path / nome).write_text(_O_MARCADOR_SOZINHO, encoding="utf-8")
        faltas = arquivos_em_falta(tmp_path)
        assert nome in faltas, (
            "o marcador skip_sem_gi_real passou como guarda de um arquivo que planta "
            "no topo: ele pula o TESTE, e a importação planta o gi falso antes"
        )
        falta = faltas[nome]
        assert falta.guarda is None and falta.so_a_palavra
        assert falta.na_importacao == _linha(_O_MARCADOR_SOZINHO, "_plantar()")
        assert "só o marcador" in falta.descrever()

    def test_a_guarda_depois_do_plantio_nao_vale(self) -> None:
        falta = falta_de_guarda(_A_GUARDA_DEPOIS)
        assert falta is not None, "a guarda DEPOIS do plantio foi aceita"
        assert falta.na_importacao == _linha(_A_GUARDA_DEPOIS, "_plantar()")
        assert falta.guarda == _linha(_A_GUARDA_DEPOIS, "exigir_gi_real('depois')")
        assert falta_de_guarda(_A_GUARDA_DENTRO_DE_FUNCAO) is not None, (
            "a guarda dentro de função só roda se alguém a chamar; não guarda a importação"
        )

    @pytest.mark.parametrize(
        "fonte", [_A_GUARDA_ANTES, _A_GUARDA_ATRIBUIDA, _SO_DEFINE],
        ids=["chamada-solta", "guardada-num-nome", "nada-chama-o-plantio"],
    )
    def test_a_guarda_antes_do_plantio_vale(self, fonte: str) -> None:
        assert falta_de_guarda(fonte) is None

    @pytest.mark.parametrize(
        ("fonte", "texto"),
        [
            (_POR_DUAS_FUNCOES, "_preparar()"),
            (_O_PLANTIO_DIRETO_ANTES, "try:"),
            (_O_PLANTIO_NA_CLASSE, "class _Gi:"),
        ],
        ids=["por-duas-funcoes", "direto-no-try", "no-corpo-da-classe"],
    )
    def test_o_plantio_ao_importar_conta_por_onde_vier(self, fonte: str, texto: str) -> None:
        falta = falta_de_guarda(fonte)
        assert falta is not None, "o plantio ao importar, antes da guarda, passou"
        assert falta.na_importacao == _linha(fonte, texto)

    def test_a_funcao_que_so_e_definida_nao_planta_ao_importar(self) -> None:
        assert plantio_na_importacao(_SO_DEFINE) is None
        alvo = TESTS_UNIT / "test_o_botao_que_tira_o_que_faz_engasgar.py"
        if alvo.exists():
            assert plantacoes_de_gi_falso(alvo.read_text(encoding="utf-8"))
            assert alvo.name not in arquivos_em_falta()


# ---------------------------------------------------------------------------
# A COLETA SEM GTK (o `lint-test`) NÃO DEIXA A JANELA NO PROCESSO
# ---------------------------------------------------------------------------
RAIZ = TESTS_UNIT.parents[1]

#: Os dois que plantavam com o marcador só, até 02/10.
OS_DOIS_DO_MARCADOR = (
    "tests/unit/test_p10_os_quatro_caminhos_da_aba_perfis_sem_mordida.py",
    "tests/unit/test_p3_o_salvar_solta_a_thread_e_para_de_prometer.py",
)

_ESCONDE_O_GI = '''
import sys
class _EscondeOGi:
    def find_spec(self, nome, caminho=None, alvo=None):
        if nome.split(".")[0] in ("gi", "cairo"):
            raise ModuleNotFoundError(f"No module named {nome!r}", name=nome)
        return None
sys.meta_path.insert(0, _EscondeOGi())
'''

_ESPIA_DA_JANELA = '''
import json, os, sys
_VISTOS = []
def pytest_collectreport(report):
    if report.nodeid.endswith(".py"):
        _VISTOS.append(report.nodeid)
def pytest_collection_finish(session):
    janela = sorted(m for m in sys.modules
                    if m == "hefesto_dualsense4unix.app"
                    or m.startswith("hefesto_dualsense4unix.app."))
    escondido = any(type(f).__name__ == "_EscondeOGi" for f in sys.meta_path)
    with open(os.environ["ESPIA_DA_JANELA"], "w", encoding="utf-8") as saida:
        json.dump({"gi_escondido": escondido, "vistos": _VISTOS, "janela": janela}, saida)
'''


def test_a_coleta_sem_gtk_nao_deixa_a_janela_no_processo(tmp_path: Path) -> None:
    """O p10 e o p3 coletados sem `gi`, num pytest filho: nenhum módulo da janela fica.

    Mordida: tire o `exigir_gi_real()` do topo do p10 e devolva o marcador com
    o plantio; a régua lista os 16 módulos da janela que a coleta deixou.
    """
    lar = tmp_path / "sem_gi"
    lar.mkdir()
    (lar / "sitecustomize.py").write_text(_ESCONDE_O_GI, encoding="utf-8")
    (lar / "espia_da_janela.py").write_text(_ESPIA_DA_JANELA, encoding="utf-8")
    saida = tmp_path / "espia.json"
    ambiente = dict(os.environ)
    ambiente["PYTHONPATH"] = os.pathsep.join([str(lar), str(RAIZ / "src"), str(RAIZ)])
    ambiente["ESPIA_DA_JANELA"] = str(saida)
    ambiente["PYTHONDONTWRITEBYTECODE"] = "1"
    ambiente.pop("HEFESTO_EXIGE_GTK_REAL", None)
    ambiente.pop("PYTEST_ADDOPTS", None)
    r = subprocess.run(
        [
            sys.executable, "-m", "pytest", "--collect-only", "-q",
            "-p", "no:cacheprovider", "-p", "espia_da_janela", *OS_DOIS_DO_MARCADOR,
        ],
        capture_output=True,
        text=True,
        cwd=RAIZ,
        env=ambiente,
        timeout=180,
    )
    assert saida.exists(), (
        f"o pytest filho não chegou ao fim da coleta:\n{(r.stdout + r.stderr)[-1500:]}"
    )
    dados = json.loads(saida.read_text(encoding="utf-8"))
    assert dados["gi_escondido"], "o gi não foi escondido: a régua mediria o mundo com GTK"
    faltaram = [a for a in OS_DOIS_DO_MARCADOR if a not in dados["vistos"]]
    assert not faltaram, f"a coleta não passou por {faltaram}: zero com o alvo fora não é zero"
    assert not dados["janela"], (
        f"a coleta sem GTK deixou {len(dados['janela'])} módulos da janela no processo, "
        "construídos sobre o gi falso, para o arquivo seguinte importar:\n  "
        + "\n  ".join(dados["janela"])
    )
