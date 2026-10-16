"""O teto da escala de prioridade tem UMA fonte, e três lugares a obedecem."""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.profiles import sanidade, schema

_RAIZ = Path(__file__).resolve().parents[2]
_PACOTE = _RAIZ / "src" / "hefesto_dualsense4unix"
_PAGINA_PERFIS = (
    _PACOTE / "interface" / "paginas" / "10-perfis.html"  # noqa-acento (pasta)
)
_PROFILES_ACTIONS = _PACOTE / "app" / "actions" / "profiles_actions.py"


def _constante_por_ast(arquivo: Path, nome: str) -> int:
    """Lê um literal inteiro de módulo SEM importar o módulo."""
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


_A_ABA_PERFIS = _PACOTE / "interface" / "pacotes" / "a10_perfis.py"


class TestUmTetoSo:
    """Desde 15/10/2026 a página não tem o trilho da Prioridade (a ordem é arrastada na lista).

    O terceiro lugar que repetia o teto era o `max` do trilho; hoje é a ordem do editor, que recebe
    o teto de `schema.PRIORIDADE_MAXIMA`.
    """

    def test_o_verificador_semantico_usa_a_faixa_da_janela(self) -> None:
        """`sanidade` e a aba Perfis têm de dizer o MESMO teto."""
        da_aba = _constante_por_ast(_PROFILES_ACTIONS, "PRIORIDADE_MAXIMA")
        assert da_aba == sanidade.PRIORIDADE_MAXIMA

    def test_a_tela_nao_cravou_o_teto_de_volta(self) -> None:
        """MORDIDA: devolva um `<input type="range" max="200">` ao gerador e isto reprova."""
        pagina = _PAGINA_PERFIS.read_text(encoding="utf-8")
        assert 'type="range"' not in pagina and "editor.prioridade" not in pagina, (
            "a página voltou a ter um trilho de Prioridade com o teto escrito nela")

    def test_a_ordem_do_editor_usa_o_teto_do_schema(self) -> None:
        """O teto vem de `schema`, por nome, e o empate no topo não passa dele.

        MORDIDA: troque o `teto` do `editor_ordem` por 100 e a ordem de baixo deixa de caber em 200.
        """
        from hefesto_dualsense4unix.interface.pacotes import a10_perfis

        fonte = _A_ABA_PERFIS.read_text(encoding="utf-8")
        assert "from hefesto_dualsense4unix.profiles.schema import PRIORIDADE_MAXIMA" in fonte
        assert not re.search(r"^\s*PRIORIDADE_MAXIMA\s*=\s*\d+", fonte, re.M), (
            "a aba Perfis escreveu o teto na mão")
        teto = sanidade.PRIORIDADE_MAXIMA
        assert a10_perfis._valores_da_nova_ordem([teto, teto, teto], teto) == [
            teto, teto - 1, teto - 2]

    def test_o_piso_da_ordem_e_o_da_escala(self) -> None:
        """`PRIORIDADE_MINIMA` é o chão: uma ordem comprida não vai abaixo dele."""
        from hefesto_dualsense4unix.interface.pacotes import a10_perfis

        piso = sanidade.PRIORIDADE_MINIMA
        valores = a10_perfis._valores_da_nova_ordem([piso] * 3, sanidade.PRIORIDADE_MAXIMA)
        assert min(valores) >= piso


class TestAFonteEDaCamadaMaisBaixa:
    """Depois da unificação de 05/08: quem manda mora em `profiles/schema.py`."""

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
        """Sem importar `profiles_actions`: o literal 200 não pode voltar lá."""
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
        """Seis asserções vivas importam `pa.PRIORIDADE_MAXIMA`."""
        fonte = _PROFILES_ACTIONS.read_text(encoding="utf-8")
        assert "PRIORIDADE_MAXIMA" in fonte
