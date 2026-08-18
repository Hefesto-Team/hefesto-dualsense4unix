"""CR-02: o formato do efeito próprio RECUSA valor sem proveniência.

Portão da sprint
`docs/process/sprints/2026-07-25-CR-02-formato-e-proveniencia.md`, sob a regra
R3 do `docs/process/CLEAN-ROOM.md`: *"Todo valor entra no projeto com o registro
de como nasceu (...). Valor sem proveniência não entra."*

O que este arquivo cobra, e por que cada coisa é um portão e não um detalhe:

1. **A recusa é erro, não aviso.** Uma curva com `medido_por` vazio tem de
   levantar. Teste que aceita a tabela sem proveniência não testa nada — é a
   frase da própria sprint, e é o motivo de metade deste arquivo ser recusa.

2. **A recusa é insensível à caixa nos nomes do DSX.** `Hard` e `hard` são o
   mesmo problema. Vale especialmente para `Rigid`, que é ao mesmo tempo o
   sétimo modo "pronto" do DSX (recusado) e um dos 19 presets paramétricos que
   o Hefesto implementa (legítimo) — a colisão é real e está registrada em
   `docs/process/sprints/2026-07-31-CR-SEQUENCIA-01-*.md`.

3. **A lista de nomes recusados não é transcrita aqui.** Ela é lida do
   `DSX_CANNED_TRIGGER_MODES` do `daemon/udp_server.py`. Duas listas divergem;
   uma, não.

4. **A largura da curva é fato medido, não preferência.** Sete bytes porque o
   `TriggerEffect.forces` tem sete posições — este arquivo confere isso contra
   o `core.trigger_effects` de verdade, para que a constante não possa mentir.

O que este arquivo NÃO faz: escrever qualquer valor de curva de verdade. Os
bytes usados aqui são dado de teste sintético para exercitar o formato, e não
entram em `docs/protocol/curvas-proprias.md` — quem preenche aquela tabela é a
CR-04, com a mão da mantenedora no gatilho.
"""
from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.profiles.curva_propria import (
    CAMPOS_DE_PROVENIENCIA,
    CURVA_BYTES,
    DATA_MINIMA_DE_MEDICAO,
    NOTA_MINIMA_DE_CARACTERES,
    CatalogoCurvasProprias,
    CurvaPropria,
    gerar_tabela_markdown,
)

#: Curva sintética completa. Serve de base para as variações: cada teste de
#: recusa muda UM campo, para provar que é aquele campo que reprova.
CURVA_COMPLETA = {
    "nome": "Pesado",
    "curva": [2, 30, 200, 0, 0, 0, 0],
    "medido_por": "mantenedora",
    "medido_em": "2026-07-31",
    "controle": "DualSense CFI-ZCT1W, cabo USB-C",
    "nota": (
        "Dado de teste sintético, não é medição: existe só para exercitar o "
        "formato de proveniência."
    ),
}


def _sem(campo: str, valor: object) -> dict[str, object]:
    """A curva completa com um campo trocado."""
    dados = dict(CURVA_COMPLETA)
    dados[campo] = valor
    return dados


class TestAProveniencaEObrigatoria:
    """A mordida principal: sem os quatro campos, nada entra."""

    def test_curva_completa_entra(self) -> None:
        curva = CurvaPropria(**CURVA_COMPLETA)  # type: ignore[arg-type]
        assert curva.nome == "Pesado"
        assert curva.medido_em_data == __import__("datetime").date(2026, 7, 31)

    @pytest.mark.parametrize("campo", ["medido_por", "controle", "nota"])
    def test_campo_de_proveniencia_vazio_reprova(self, campo: str) -> None:
        with pytest.raises(ValidationError) as erro:
            CurvaPropria(**_sem(campo, ""))  # type: ignore[arg-type]
        assert campo in str(erro.value)

    @pytest.mark.parametrize("campo", ["medido_por", "controle", "nota"])
    def test_campo_de_proveniencia_so_com_espaco_reprova(self, campo: str) -> None:
        """Espaço em branco é a forma mais fácil de burlar 'não vazio'."""
        with pytest.raises(ValidationError):
            CurvaPropria(**_sem(campo, "   \t  "))  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "campo", ["nome", "medido_por", "medido_em", "controle", "nota"]
    )
    def test_campo_ausente_reprova(self, campo: str) -> None:
        """Omitir o campo é diferente de mandar vazio — os dois têm de reprovar."""
        dados = dict(CURVA_COMPLETA)
        del dados[campo]
        with pytest.raises(ValidationError):
            CurvaPropria(**dados)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "campo", ["nome", "medido_por", "medido_em", "controle", "nota"]
    )
    def test_campo_none_reprova_falando_da_regra(self, campo: str) -> None:
        with pytest.raises(ValidationError) as erro:
            CurvaPropria(**_sem(campo, None))  # type: ignore[arg-type]
        assert "R3" in str(erro.value)

    def test_nota_cerimonial_reprova(self) -> None:
        """'ok' preenche o campo sem cumprir a regra — e a regra é o que vale."""
        with pytest.raises(ValidationError) as erro:
            CurvaPropria(**_sem("nota", "ok"))  # type: ignore[arg-type]
        assert str(NOTA_MINIMA_DE_CARACTERES) in str(erro.value)

    def test_nenhum_campo_de_proveniencia_tem_default(self) -> None:
        """Default transformaria 'não informado' em 'informado como vazio'."""
        assert set(CAMPOS_DE_PROVENIENCIA) == {
            "medido_por",
            "medido_em",
            "controle",
            "nota",
        }, "a lista de campos de proveniência mudou sem passar por aqui"
        for campo in CAMPOS_DE_PROVENIENCIA:
            assert CurvaPropria.model_fields[campo].is_required(), (
                f"{campo} ganhou default — é o buraco que a R3 fecha"
            )


class TestADataEDatada:
    """A R3 pede proveniência DATADA, e a data tem de ser data."""

    def test_data_fora_do_iso_reprova(self) -> None:
        with pytest.raises(ValidationError):
            CurvaPropria(**_sem("medido_em", "31/07/2026"))  # type: ignore[arg-type]

    def test_data_anterior_ao_processo_reprova(self) -> None:
        with pytest.raises(ValidationError) as erro:
            CurvaPropria(**_sem("medido_em", "2026-07-24"))  # type: ignore[arg-type]
        assert "sala limpa" in str(erro.value)

    def test_o_primeiro_dia_do_processo_entra(self) -> None:
        """A borda é inclusiva: 25/07 é o dia em que o processo passou a valer."""
        curva = CurvaPropria(
            **_sem("medido_em", DATA_MINIMA_DE_MEDICAO.isoformat())  # type: ignore[arg-type]
        )
        assert curva.medido_em == "2026-07-25"

    def test_o_limite_nao_depende_do_relogio(self) -> None:
        """Data FIXA, não `date.today()`.

        A cicatriz desta casa é portão que reprova sozinho quando o relógio da
        máquina muda. Se alguém trocar a constante por uma leitura do relógio,
        este teste é quem avisa.
        """
        assert DATA_MINIMA_DE_MEDICAO.isoformat() == "2026-07-25"


class TestAGuardaDeNomes:
    """R2: nome nosso, em português. Nunca um dos doze do DSX."""

    def _nomes_do_dsx(self) -> list[str]:
        from hefesto_dualsense4unix.daemon.udp_server import DSX_CANNED_TRIGGER_MODES

        return list(DSX_CANNED_TRIGGER_MODES.values())

    def test_os_doze_nomes_do_dsx_reprovam(self) -> None:
        recusados = self._nomes_do_dsx()
        assert len(recusados) == 12, "a lista do DSX mudou de tamanho"
        for nome in recusados:
            with pytest.raises(ValidationError):
                CurvaPropria(**_sem("nome", nome))  # type: ignore[arg-type]

    @pytest.mark.parametrize("variante", ["hard", "HARD", "hArD", "  Hard  "])
    def test_a_recusa_ignora_caixa_e_espaco(self, variante: str) -> None:
        with pytest.raises(ValidationError):
            CurvaPropria(**_sem("nome", variante))  # type: ignore[arg-type]

    def test_rigid_reprova_apesar_de_ser_preset_nosso(self) -> None:
        """A colisão que prova que o risco da R2 não é teórico.

        `Rigid` é o modo enlatado nº 7 do DSX (recusado) E um dos 19 presets
        paramétricos do Hefesto (legítimo, anterior ao processo). Como nome de
        efeito NOVO, ele reprova — é justamente o caso em que a comparação byte
        a byte seria convidada.
        """
        from hefesto_dualsense4unix.core.trigger_effects import PRESET_FACTORIES

        assert "Rigid" in PRESET_FACTORIES, "o preset paramétrico sumiu"
        with pytest.raises(ValidationError):
            CurvaPropria(**_sem("nome", "Rigid"))  # type: ignore[arg-type]

    def test_a_mensagem_explica_a_regra_em_vez_de_so_negar(self) -> None:
        """A sprint pede explicação, não recusa muda."""
        with pytest.raises(ValidationError) as erro:
            CurvaPropria(**_sem("nome", "Choppy"))  # type: ignore[arg-type]
        texto = str(erro.value)
        assert "R2" in texto
        assert "comparação" in texto

    def test_nome_proprio_em_portugues_entra(self) -> None:
        for nome in ("Pesado", "Macio", "Trepidante"):
            assert CurvaPropria(**_sem("nome", nome)).nome == nome  # type: ignore[arg-type]


class TestACurvaTemALarguraDoHardware:
    """Fronteira R4, lado do fato do protocolo."""

    def test_a_constante_bate_com_o_hardware_de_verdade(self) -> None:
        """Se `forces` mudar de largura, a constante não pode continuar mentindo."""
        from hefesto_dualsense4unix.core.trigger_effects import PRESET_FACTORIES

        efeito = PRESET_FACTORIES["Rigid"](5, 200)
        assert len(efeito.forces) == CURVA_BYTES

    @pytest.mark.parametrize("tamanho", [0, 1, 6, 8, 12])
    def test_curva_com_tamanho_errado_reprova(self, tamanho: int) -> None:
        with pytest.raises(ValidationError):
            CurvaPropria(**_sem("curva", [0] * tamanho))  # type: ignore[arg-type]

    @pytest.mark.parametrize("byte", [-1, 256, 1000])
    def test_byte_fora_da_faixa_reprova(self, byte: int) -> None:
        with pytest.raises(ValidationError):
            CurvaPropria(**_sem("curva", [byte] + [0] * 6))  # type: ignore[arg-type]

    def test_booleano_nao_passa_por_byte(self) -> None:
        """`True` é `int` em Python; num campo de byte isso é lixo, não dado."""
        with pytest.raises(ValidationError):
            CurvaPropria(**_sem("curva", [True] + [0] * 6))  # type: ignore[arg-type]


class TestOCatalogoNaoAceitaDoisDonosParaOMesmoNome:
    """A decisão de projeto da CR-02, cobrada por teste."""

    def test_nome_repetido_reprova(self) -> None:
        outra = dict(CURVA_COMPLETA)
        outra["medido_por"] = "outra pessoa"
        with pytest.raises(ValidationError) as erro:
            CatalogoCurvasProprias(
                curvas=[
                    CurvaPropria(**CURVA_COMPLETA),  # type: ignore[arg-type]
                    CurvaPropria(**outra),  # type: ignore[arg-type]
                ]
            )
        assert "duplicado" in str(erro.value)

    def test_nome_repetido_com_caixa_diferente_tambem_reprova(self) -> None:
        with pytest.raises(ValidationError):
            CatalogoCurvasProprias(
                curvas=[
                    CurvaPropria(**CURVA_COMPLETA),  # type: ignore[arg-type]
                    CurvaPropria(**_sem("nome", "PESADO")),  # type: ignore[arg-type]
                ]
            )

    def test_catalogo_vazio_e_valido(self) -> None:
        """Antes da CR-04 não há curva nenhuma, e isso não é erro."""
        assert CatalogoCurvasProprias().curvas == []

    def test_campo_desconhecido_reprova(self) -> None:
        with pytest.raises(ValidationError):
            CatalogoCurvasProprias(curvas=[], apelido="x")  # type: ignore[call-arg]


class TestATabelaEGeradaDoDado:
    """A CR-02 é explícita: a tabela sai dos dados, não da mão de ninguém."""

    def test_catalogo_vazio_devolve_a_linha_que_o_documento_ja_tem(self) -> None:
        assert gerar_tabela_markdown(CatalogoCurvasProprias()) == (
            "_(nenhum ainda — ver CR-04)_"
        )

    def test_a_tabela_carrega_os_quatro_campos_de_proveniencia(self) -> None:
        catalogo = CatalogoCurvasProprias(
            curvas=[CurvaPropria(**CURVA_COMPLETA)]  # type: ignore[arg-type]
        )
        tabela = gerar_tabela_markdown(catalogo)
        assert "mantenedora" in tabela
        assert "2026-07-31" in tabela
        assert "DualSense CFI-ZCT1W" in tabela
        assert "sintético" in tabela
        assert "2, 30, 200" in tabela

    def test_a_ordem_e_estavel_por_nome(self) -> None:
        """Tabela que muda de ordem sozinha vira ruído de diff a cada geração."""
        catalogo = CatalogoCurvasProprias(
            curvas=[
                CurvaPropria(**_sem("nome", "Trepidante")),  # type: ignore[arg-type]
                CurvaPropria(**_sem("nome", "Macio")),  # type: ignore[arg-type]
                CurvaPropria(**_sem("nome", "Pesado")),  # type: ignore[arg-type]
            ]
        )
        linhas = gerar_tabela_markdown(catalogo).splitlines()[2:]
        assert [linha.split("|")[1].strip() for linha in linhas] == [
            "Macio",
            "Pesado",
            "Trepidante",
        ]

    def test_pipe_na_nota_nao_quebra_a_tabela(self) -> None:
        """Nota com `|` tem de sair escapada, senão vira coluna nova no render."""
        nota = "Travou firme | e não doeu no dedo depois de dez minutos seguidos."
        catalogo = CatalogoCurvasProprias(
            curvas=[CurvaPropria(**_sem("nota", nota))]  # type: ignore[arg-type]
        )
        linha = gerar_tabela_markdown(catalogo).splitlines()[2]
        assert r"\|" in linha, "o pipe da nota não foi escapado"
        # Só os separadores de coluna contam: os escapados não abrem coluna.
        separadores = len(re.findall(r"(?<!\\)\|", linha))
        assert separadores == 7, f"a linha ganhou coluna: {linha}"


class TestODocumentoDeProvenienciaSegueVazio:
    """R3 na direção contrária: nenhum valor pode ter entrado sem a mão dela."""

    def test_curvas_proprias_md_nao_tem_tabela_de_valores(self) -> None:
        """Se alguém colar uma curva no documento, este portão avisa.

        Nenhum valor entra antes da CR-04, e a CR-04 é a sprint que exige a
        medição no hardware. Uma tabela preenchida aqui significa valor sem
        mão — exatamente o que a R3 recusa.
        """
        import pathlib

        raiz = pathlib.Path(__file__).resolve().parents[2]
        doc = raiz / "docs" / "protocol" / "curvas-proprias.md"
        assert doc.is_file(), "o documento de proveniência sumiu"
        assert "_(nenhum ainda — ver CR-04)_" in doc.read_text(encoding="utf-8")
