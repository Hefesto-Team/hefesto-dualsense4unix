"""O teto da escala de prioridade tem UMA fonte, e três lugares a obedecem.

Decisão dela, 05/08/2026: *"preciso que as constantes apontem pros arquivos
reais do import"*. Medido no mesmo dia, o número 200 morava em três lugares
sem nenhum fio entre dois deles:

- `profiles/sanidade.py` — `PRIORIDADE_MAXIMA`, com comentário declarando a
  duplicação de propósito ("profiles/ não pode depender de app/");
- `app/actions/profiles_actions.py` — `PRIORIDADE_MAXIMA`, a "fonte" que os
  outros citavam;
- `gui/main.glade` — o `upper` do `profile_priority_adj`, XML que não importa
  nada de ninguém.

Só UM par tinha portão (`test_empate01_a_cor_volta_a_ser_dela.py`, glade
contra `profiles_actions`). O verificador semântico — que ACUSA prioridade
fora da faixa e manda a usuária "reabrir na aba Perfis" — podia divergir da
faixa que a aba Perfis realmente oferece, e o achado passaria a mentir sem
que nada reprovasse. Este arquivo fecha esse triângulo.

**Por que AST e não import de `profiles_actions`.** O módulo faz
``import gi``/``gi.require_version("Gtk", "3.0")`` no topo: importá-lo aqui
mataria o portão no CI headless. A casa tem duas saídas para isso — a guarda
`exigir_gi_real` (que PULA o módulo inteiro sem GTK) e a leitura por AST. Aqui
tem de ser a AST: um portão que confere se três números batem não pode ser um
portão que some justamente onde não há GTK, porque é lá que roda o CI. Ler o
literal pela AST não executa nada do módulo e vale em qualquer máquina.
"""
from __future__ import annotations

import ast
from pathlib import Path
from xml.etree import ElementTree

import pytest

from hefesto_dualsense4unix.profiles import sanidade, schema

_RAIZ = Path(__file__).resolve().parents[2]
_PACOTE = _RAIZ / "src" / "hefesto_dualsense4unix"
_GLADE = _PACOTE / "gui" / "main.glade"
_PROFILES_ACTIONS = _PACOTE / "app" / "actions" / "profiles_actions.py"


def _constante_por_ast(arquivo: Path, nome: str) -> int:
    """Lê um literal inteiro de módulo SEM importar o módulo.

    Aceita tanto a atribuição de um literal (``X = 200``) quanto a reexport de
    um atributo (``X = schema.PRIORIDADE_MAXIMA``) — neste segundo caso o valor
    devolvido é o do módulo citado, resolvido pelo import de `schema`, que só
    depende de stdlib + pydantic.
    """
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))
    for no in ast.walk(arvore):
        alvos: list[ast.expr] = []
        valor: ast.expr | None = None
        if isinstance(no, ast.Assign):
            alvos, valor = list(no.targets), no.value
        elif isinstance(no, ast.AnnAssign) and no.value is not None:
            alvos, valor = [no.target], no.value
        if not any(isinstance(a, ast.Name) and a.id == nome for a in alvos):
            continue
        assert valor is not None
        if isinstance(valor, ast.Constant) and isinstance(valor.value, int):
            return valor.value
        if isinstance(valor, ast.Attribute) and valor.attr == nome:
            return int(getattr(schema, nome))
        if isinstance(valor, ast.Name):
            return int(getattr(schema, valor.id))
        pytest.fail(
            f"{arquivo.name}: `{nome}` não é literal inteiro nem reexport de "
            f"`schema.{nome}` — este portão não sabe ler {ast.dump(valor)[:80]}"
        )
    pytest.fail(f"{arquivo.name}: `{nome}` sumiu do módulo")


def _upper_do_glade(adjustment: str) -> int:
    arvore = ElementTree.parse(_GLADE)
    ajuste = next(
        obj for obj in arvore.iter("object") if obj.get("id") == adjustment
    )
    upper = next(
        prop for prop in ajuste.iter("property") if prop.get("name") == "upper"
    )
    return int(str(upper.text).strip())


class TestUmTetoSo:
    def test_o_verificador_semantico_usa_a_faixa_da_janela(self) -> None:
        """`sanidade` e a aba Perfis têm de dizer o MESMO teto.

        Este é o par que NÃO tinha portão. Divergir aqui faz o doctor acusar
        "fora da faixa que a janela oferece" com uma faixa que a janela não
        oferece — e a cura que ele imprime ("reabra na aba Perfis") não cura.
        """
        da_aba = _constante_por_ast(_PROFILES_ACTIONS, "PRIORIDADE_MAXIMA")
        assert da_aba == sanidade.PRIORIDADE_MAXIMA

    def test_o_glade_acompanha_o_verificador(self) -> None:
        """O terceiro lado do triângulo, fechado pelo XML."""
        assert _upper_do_glade("profile_priority_adj") == sanidade.PRIORIDADE_MAXIMA

    def test_os_tres_lugares_dizem_o_mesmo_numero(self) -> None:
        """A asserção da dona, escrita como ela pediu, numa linha só."""
        assert (
            sanidade.PRIORIDADE_MAXIMA
            == _constante_por_ast(_PROFILES_ACTIONS, "PRIORIDADE_MAXIMA")
            == _upper_do_glade("profile_priority_adj")
        )

    def test_o_piso_da_escala_tambem_bate_com_o_glade(self) -> None:
        """`PRIORIDADE_MINIMA` é o `lower` do mesmo adjustment."""
        arvore = ElementTree.parse(_GLADE)
        ajuste = next(
            obj
            for obj in arvore.iter("object")
            if obj.get("id") == "profile_priority_adj"
        )
        lower = next(
            prop for prop in ajuste.iter("property") if prop.get("name") == "lower"
        )
        assert int(str(lower.text).strip()) == sanidade.PRIORIDADE_MINIMA


class TestAFonteEDaCamadaMaisBaixa:
    """Depois da unificação de 05/08: quem manda mora em `profiles/schema.py`.

    O critério da eleição é o import: `schema.py` depende só de stdlib +
    pydantic, é de onde `draft_config` já lê o DEFAULT de `priority`, e é
    importável por `profiles/`, por `app/` e pelo CLI sem puxar GTK. Os testes
    acima seguiriam verdes com três cópias sincronizadas na mão; estes exigem
    que não haja cópia nenhuma.
    """

    def test_o_schema_declara_a_faixa(self) -> None:
        assert schema.PRIORIDADE_MINIMA == 0
        assert schema.PRIORIDADE_MAXIMA == 200
        assert "PRIORIDADE_MAXIMA" in schema.__all__
        assert "PRIORIDADE_MINIMA" in schema.__all__

    def test_sanidade_nao_tem_copia_propria(self) -> None:
        """`sanidade.PRIORIDADE_MAXIMA` É o objeto do schema, não um gêmeo."""
        assert sanidade.PRIORIDADE_MAXIMA is schema.PRIORIDADE_MAXIMA
        assert sanidade.PRIORIDADE_MINIMA is schema.PRIORIDADE_MINIMA

    def test_a_aba_perfis_reexporta_em_vez_de_repetir(self) -> None:
        """Sem importar `profiles_actions`: o literal 200 não pode voltar lá.

        A leitura é textual de propósito — `_constante_por_ast` resolveria uma
        reexport E um literal para o mesmo 200, e é justamente o literal que
        esta asserção proíbe.
        """
        arvore = ast.parse(
            _PROFILES_ACTIONS.read_text(encoding="utf-8"),
            filename=str(_PROFILES_ACTIONS),
        )
        atribuicoes = [
            no
            for no in ast.walk(arvore)
            if isinstance(no, ast.Assign)
            and any(
                isinstance(a, ast.Name) and a.id == "PRIORIDADE_MAXIMA"
                for a in no.targets
            )
        ]
        assert atribuicoes, "profiles_actions perdeu o nome `PRIORIDADE_MAXIMA`"
        for no in atribuicoes:
            assert not isinstance(no.value, ast.Constant), (
                "profiles_actions voltou a escrever o teto na mão — ele tem de "
                "reexportar `profiles.schema.PRIORIDADE_MAXIMA`"
            )

    def test_o_nome_continua_no_modulo_da_aba(self) -> None:
        """Seis asserções vivas importam `pa.PRIORIDADE_MAXIMA`.

        Unificar não pode virar churn: o nome fica onde estava, só muda de
        dono. Conferido pelo texto, para não puxar GTK.
        """
        fonte = _PROFILES_ACTIONS.read_text(encoding="utf-8")
        assert "PRIORIDADE_MAXIMA" in fonte
