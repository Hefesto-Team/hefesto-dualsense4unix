"""O portão do contrato MARCAR e APLICAR — I12 da INÍCIO NÃO MENTE-01."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_home_contrato_marcar_e_aplicar: importa código da janela GTK")

import ast
from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.actions import contrato_da_mascara as contrato

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"
APP = SRC / "app"


def _superficies_que_aplicam() -> dict[str, list[int]]:
    """`{caminho relativo: [linhas]}` de quem chama `apply_mode` dentro de `app/`."""
    achados: dict[str, list[int]] = {}
    for arquivo in sorted(APP.rglob("*.py")):
        relativo = str(arquivo.relative_to(SRC)).replace("\\", "/")
        if relativo == contrato.MECANISMO_DA_TRANSICAO:
            continue
        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover
            continue
        linhas = [
            no.lineno
            for no in ast.walk(arvore)
            if isinstance(no, ast.Call)
            and (
                (isinstance(no.func, ast.Name) and no.func.id == "apply_mode")
                or (
                    isinstance(no.func, ast.Attribute)
                    and no.func.attr == "apply_mode"
                )
            )
        ]
        if linhas:
            achados[relativo] = linhas
    return achados


def test_o_contrato_esta_no_disco_e_nomeia_os_dois_gestos() -> None:
    """Antes desta sprint ele existia só na cabeça de quem escreveu."""
    assert contrato.GESTO_MARCAR == "marcar"
    assert contrato.GESTO_APLICAR == "aplicar"
    assert contrato.SUPERFICIE_QUE_APLICA == "app/actions/footer_actions.py"
    assert "app/actions/home_actions.py" in contrato.SUPERFICIES_QUE_MARCAM


def test_a_regua_enxerga_quem_aplica() -> None:
    """Valide o instrumento contra o que você já sabe (A5, 23/08/2026)."""
    quem = _superficies_que_aplicam()
    assert contrato.SUPERFICIE_QUE_APLICA in quem, (
        "a varredura não acha nem o rodapé, que é o dono declarado do gesto de "
        "aplicar. O instrumento está cego, e o verde do portão não vale nada."
    )
    assert "app/actions/emulation_actions.py" in quem, (
        "a varredura não acha a aba Emulação, que a sprint MEDIU aplicando no "
        "clique (`_apply_mode`). Ou a onda dela fechou — e aí o registro de "
        "exceção tem de sair —, ou o instrumento está cego."
    )


def test_nenhuma_superficie_nova_entrou_no_gesto_de_aplicar() -> None:
    """O portão de verdade: quem aplica é o rodapé, mais o que está registrado."""
    permitidas = {contrato.SUPERFICIE_QUE_APLICA, *contrato.EXCECOES_QUE_APLICAM_HOJE}
    intrusas = sorted(set(_superficies_que_aplicam()) - permitidas)
    assert not intrusas, (
        f"estas superfícies aplicam modo/máscara sem serem o rodapé: "
        f"{intrusas}. O contrato é MARCAR nos seletores e APLICAR no rodapé "
        "(`app/actions/contrato_da_mascara.py`). Se a mudança é deliberada, "
        "ela precisa da palavra dela e de uma linha datada em "
        "`EXCECOES_QUE_APLICAM_HOJE` — não de um portão mais frouxo."
    )


def test_a_excecao_registrada_ainda_e_uma_excecao() -> None:
    """Exceção que sobreviveu à própria cura vira norma. Esta não vai."""
    quem = _superficies_que_aplicam()
    curadas = [alvo for alvo in contrato.EXCECOES_QUE_APLICAM_HOJE if alvo not in quem]
    assert not curadas, (
        f"{curadas} não aplica(m) mais nada, e continua(m) registrada(s) como "
        "exceção. Apague a linha de `EXCECOES_QUE_APLICAM_HOJE`: um registro "
        "que sobrevive à cura ensina a próxima pessoa a não acreditar nele."
    )


def test_toda_excecao_tem_data_e_razao() -> None:
    """Razão sem data envelhece calada — a régua do registro de lacunas."""
    import re

    for alvo, razao in contrato.EXCECOES_QUE_APLICAM_HOJE.items():
        assert re.search(r"\b\d{2}/\d{2}/\d{4}\b", razao), (
            f"a exceção de {alvo} não diz QUANDO foi medida"
        )
        assert "O QUE A FECHA" in razao, (
            f"a exceção de {alvo} não diz o que a fecha — sem isso ela é uma "
            "desculpa, não um registro"
        )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "a aba Emulação aplica no clique (MEDIDO em 24/08/2026). Fechá-la é a "
        "onda dela, e a redação de tela do contrato é palavra dela (D-B do "
        "SPRINT_ORDER §0.9). Quando ela fechar, este teste PASSA e o strict "
        "reprova — que é o gatilho para apagar este xfail e a linha de "
        "`EXCECOES_QUE_APLICAM_HOJE` no mesmo gesto."
    ),
)
def test_nenhuma_superficie_alem_do_rodape_aplica() -> None:
    """O contrato inteiro, sem exceção. É o alvo, e ainda não é o estado."""
    quem = sorted(set(_superficies_que_aplicam()) - {contrato.SUPERFICIE_QUE_APLICA})
    assert not quem, quem


def test_o_vocabulario_atravessa_a_fronteira_por_nome_publico() -> None:
    """A aba "No jogo" deixou de importar nome privado da aba Início."""
    from hefesto_dualsense4unix.app.actions import home_actions
    from hefesto_dualsense4unix.app.widgets import painel_no_jogo

    assert contrato.ITENS_DE_MODO is home_actions._MODE_ITEMS
    assert contrato.ITENS_DE_MASCARA is home_actions._FLAVOR_ITEMS
    assert contrato.ROTULO_RECONCILIAR == home_actions.RECONCILIAR_LABEL
    assert painel_no_jogo._MODE_ITEMS is home_actions._MODE_ITEMS
    assert painel_no_jogo._FLAVOR_ITEMS is home_actions._FLAVOR_ITEMS

    fonte = (
        RAIZ / "src/hefesto_dualsense4unix/app/widgets/painel_no_jogo.py"
    ).read_text(encoding="utf-8")
    assert "from hefesto_dualsense4unix.app.actions.home_actions import (" not in fonte, (
        "a aba No jogo voltou a importar direto da aba Início. O contrato "
        "declara o dono do vocabulário; furar o `_` de outro módulo é o hábito "
        "que ele existe para tirar."
    )
