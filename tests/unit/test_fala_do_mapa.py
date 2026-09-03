"""Z6-03 — `Fala`, `Pendencia`, `NAO_MEDIDO`: a recusa mora no tipo.

A mordida da sprint: "Construir uma `Pendencia` com valor numérico ou
booleano → tem de levantar; trocar a recusa por `pass` → o teste reprova."
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.fala_do_mapa import (
    AFIRMA_NADA,
    AFIRMA_NAO_ACIONA,
    NAO_MEDIDO,
    Fala,
    Numero,
    Pendencia,
    formata_pt_br,
    frase_de_exibicao,
)


def _pendencia(**sobrescreve: object) -> Pendencia:
    base: dict[str, object] = {
        "aberta_em": "2026-08-24",
        "prazo_dias": 30,
        "quem_fecha": "a bancada, com o aparelho na mão",
        "o_que_falta": "o conteúdo do payload",
    }
    base.update(sobrescreve)
    return Pendencia(**base)  # type: ignore[arg-type]


def test_pendencia_valida_constroi() -> None:
    p = _pendencia()
    assert p.prazo_dias == 30


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("prazo_dias", 30.0),
        ("prazo_dias", True),
        ("prazo_dias", -5),
        ("prazo_dias", 0),
        ("aberta_em", 20260824),
        ("aberta_em", False),
        ("quem_fecha", 1),
        ("quem_fecha", ""),
        ("o_que_falta", 0),
    ],
)
def test_pendencia_recusa_valor_numerico_ou_booleano_ou_vazio(campo: str, valor: object) -> None:
    """MORDIDA de Z6-03 (Pendencia): número/booleano onde a casa exige prosa."""
    with pytest.raises((TypeError, ValueError)):
        _pendencia(**{campo: valor})


def test_pendencia_recusa_data_ilegivel() -> None:
    with pytest.raises(ValueError):
        _pendencia(aberta_em="24/08/2026")


def test_fala_recusa_texto_numerico_ou_booleano() -> None:
    with pytest.raises(TypeError):
        Fala(chave="a@b", lado="radio", aba="Status", texto=0, afirma=AFIRMA_NADA, porque="x")
    with pytest.raises(TypeError):
        Fala(chave="a@b", lado="radio", aba="Status", texto=False, afirma=AFIRMA_NADA, porque="x")


def test_fala_com_pendente_exige_texto_nao_medido() -> None:
    with pytest.raises(ValueError):
        Fala(
            chave="a@b",
            lado="radio",
            aba="Status",
            texto="uma frase qualquer",
            afirma=AFIRMA_NADA,
            porque="x",
            pendente=_pendencia(),
        )


def test_fala_nao_medido_exige_pendente() -> None:
    with pytest.raises(ValueError):
        Fala(
            chave="a@b",
            lado="radio",
            aba="Status",
            texto=NAO_MEDIDO,
            afirma=AFIRMA_NADA,
            porque="x",
        )


def test_fala_afirma_nada_exige_porque() -> None:
    with pytest.raises(ValueError):
        Fala(chave="a@b", lado="radio", aba="Status", texto="frase", afirma=AFIRMA_NADA, porque="")


def test_fala_texto_vazio_recusado() -> None:
    with pytest.raises(ValueError):
        Fala(chave="a@b", lado="radio", aba="Status", texto="   ", afirma=AFIRMA_NADA, porque="x")


def test_fala_valida_com_placeholder_constroi_e_exibe_frase_unica() -> None:
    fala = Fala(
        chave="audio.saida_dedicada@dualsense",
        lado="radio",
        aba="Status",
        texto=NAO_MEDIDO,
        afirma=AFIRMA_NADA,
        pendente=_pendencia(),
    )
    assert frase_de_exibicao(fala) == "Ainda não medimos isto no rádio."


def test_fala_valida_com_texto_escrito() -> None:
    fala = Fala(
        chave="identidade.cor_do_aparelho@dualsense",
        lado="radio",
        aba="Início",
        texto="No rádio o controle recusa o pedido da cor. Escolha na lista.",
        afirma=AFIRMA_NAO_ACIONA,
    )
    assert frase_de_exibicao(fala) == fala.texto


def test_numero_e_formata_pt_br() -> None:
    n = Numero(
        constante="HZ_INPUT_SEM_MIC",
        valor=260.4,
        chave="audio.microfone@dualsense",
        coluna="radio_ressalva",
    )
    assert formata_pt_br(n.valor) == "260,4"


def test_numero_recusa_valor_nao_numerico() -> None:
    with pytest.raises(TypeError):
        Numero(constante="X", valor="260,4", chave="a@b", coluna="c")  # type: ignore[arg-type]


# ===========================================================================
# A VÍRGULA TEM UM DONO SÓ (BG-03, 26/08/2026)
# ===========================================================================

_SRC = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"

#: O dono único da conversão `260.4` → `260,4`.
_DONO = "app/fala_do_mapa.py"

#: A ÚNICA cópia que sobrou, e ela está declarada porque não é minha de curar:
#: `app/widgets/calibrar_entradas.py::_virgula` está FORA da posse da frente
#: L3-F (regra R-A da leva de 26/08: precisou de arquivo alheio, relata e para),
#: e o relato está em `docs/process/agentes/2026-08-26/LEVA-3-F.md`.
#:
#: **No dia em que alguém a converter, este teste REPROVA** — e o conserto é
#: apagar a linha daqui, não silenciar. É a mesma disciplina da lápide de
#: `portao_a_casa_sabe_e_o_produto_nao_faz.py`: registro que sobrevive à cura
#: vira mentira.
_COPIAS_DECLARADAS: dict[str, str] = {
    "app/widgets/calibrar_entradas.py": (
        "`_virgula`, dono do texto OS_DOIS_RELOGIOS. Fora da posse da L3-F "
        "(26/08/2026); relatado em docs/process/agentes/2026-08-26/LEVA-3-F.md"
    ),
    "gui/aba_conexoes.py": (
        "03/09/2026 — NÃO É A MESMA CONTA. A linha monta a razão "
        "`balanceado/max` com TRÊS casas (`:.3f`) e dois `:g`, dentro da "
        "mensagem de um `ValueError` que explica por que a opção sem teto não "
        "tem tradução. `formata_pt_br` é de UMA casa e não sabe formatar a "
        "fração; chamá-lo aqui mudaria o texto do erro para dizer outro "
        "número. Fica declarada em vez de curada — e é a diferença entre "
        "cópia da regra e outra regra que só usa a mesma vírgula."
    ),
    "interface/aba02.py": (
        "03/09/2026 — a conta é a mesma, o CONTRATO não. Esta devolve "
        "`f\"{v:.1f}\".replace(\".\", \",\").removesuffix(\",0\")`: ela "
        "APAGA a casa decimal quando é zero, porque a aba Controles põe o "
        "número dentro de uma frase (\"2 controles\", e não \"2,0\"). "
        "`formata_pt_br` promete SEMPRE uma casa, e é essa promessa que o "
        "portão do mapa e a legenda compartilham. Envolvê-lo aqui daria a "
        "mesma saída hoje e quebraria no dia em que o dono mudar de casas — "
        "que é exatamente o dia para o qual o dono único existe."
    ),
}


def _e_a_troca_da_virgula(no: ast.AST) -> bool:
    """`<algo>.replace(".", ",")` — a forma exata das três cópias medidas."""
    if not isinstance(no, ast.Call) or not isinstance(no.func, ast.Attribute):
        return False
    if no.func.attr != "replace" or no.keywords or len(no.args) != 2:
        return False
    return [
        a.value for a in no.args if isinstance(a, ast.Constant)
    ] == [".", ","]


def _onde_a_virgula_e_reescrita() -> dict[str, list[int]]:
    """`{caminho relativo: [linhas]}` de toda troca de ponto por vírgula."""
    achados: dict[str, list[int]] = {}
    for arquivo in sorted(_SRC.rglob("*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))
        linhas = [
            no.lineno for no in ast.walk(arvore) if _e_a_troca_da_virgula(no)
        ]
        if linhas:
            achados[arquivo.relative_to(_SRC).as_posix()] = linhas
    return achados


def test_a_virgula_tem_um_dono_so() -> None:
    """A MORDIDA de BG-03: nenhuma cópia nova da conversão em `src/`.

    Eram TRÊS implementações independentes da mesma regra — `formata_pt_br`,
    o `_numero` de `app/actions/config/secao_controles.py` e o `_numero` de
    `integrations/plano_de_radio.py`, que ainda dizia em comentário *"mesma
    forma que…"* enquanto reescrevia a conta. A saída das três era idêntica,
    então **nenhum texto mudou na tela**; o que muda é que no dia em que uma
    delas mudar de arredondamento, duas células param de discordar.

    Devolvendo uma cópia a qualquer arquivo, este teste reprova nomeando
    `arquivo:linha`.

    **O que esta régua NÃO pega**, escrito para ninguém confiar demais nela:
    uma cópia escrita de outro jeito (`format()`, `locale`, `str.translate`)
    passa. Quem morde o FORMATO em si é
    `tests/unit/test_a_regua_e_a_legenda_sao_a_mesma_peca.py`, que reescreve
    `formata_pt_br` na árvore de mentira e exige que o portão do mapa mude de
    veredito junto.
    """
    achados = _onde_a_virgula_e_reescrita()

    assert _DONO in achados, (
        f"{_DONO} deixou de trocar o ponto pela vírgula — ou o dono único "
        "mudou de forma (e esta régua parou de medir o que promete), ou ele "
        "sumiu. Nos dois casos, conserte aqui antes de acreditar no verde"
    )

    intrusas = {
        caminho: linhas
        for caminho, linhas in achados.items()
        if caminho != _DONO and caminho not in _COPIAS_DECLARADAS
    }
    assert not intrusas, (
        "há cópia da conversão pt-BR fora do dono único "
        f"(`{_DONO}::formata_pt_br`):\n"
        + "\n".join(
            f"  - {caminho}:{','.join(str(n) for n in linhas)}"
            for caminho, linhas in sorted(intrusas.items())
        )
        + "\nChame `formata_pt_br` em vez de reescrever a conta. Se for uma "
        "cópia que você NÃO pode curar (arquivo fora da sua posse), declare-a "
        "em `_COPIAS_DECLARADAS` com o motivo e o relato — nunca em silêncio"
    )


def test_nenhuma_copia_declarada_sobreviveu_a_propria_cura() -> None:
    """O outro lado: registro que descreve uma árvore que não existe mais.

    Sem este caso, `_COPIAS_DECLARADAS` viraria o lugar onde se esconde o que
    incomoda — e a próxima pessoa perderia uma tarde procurando uma cópia que
    alguém já curou.
    """
    achados = _onde_a_virgula_e_reescrita()
    curadas = sorted(set(_COPIAS_DECLARADAS) - set(achados))
    assert not curadas, (
        "estas cópias estão declaradas em `_COPIAS_DECLARADAS` e já NÃO "
        f"existem: {curadas}. APAGUE a entrada — a cura chegou e o registro "
        "ficou"
    )


def test_as_duas_convertidas_devolvem_o_que_o_dono_devolve() -> None:
    """Saída idêntica: a prova de que nenhum texto da tela mudou em BG-03.

    Sem este caso, a régua acima passaria também numa "cura" que trocasse a
    conta por outra coisa qualquer.
    """
    from hefesto_dualsense4unix.app.actions.config import secao_controles
    from hefesto_dualsense4unix.integrations import plano_de_radio

    for valor in (0.0, 0.04, 3.4, 260.4, 260.45, 1234.56, -7.25):
        esperado = formata_pt_br(valor)
        assert secao_controles._numero(valor) == esperado, valor
        assert plano_de_radio._numero(valor) == esperado, valor
