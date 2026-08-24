"""O recibo do ensaio passa a dizer DE QUE BANCADA cada foto saiu — Z0-5.

O DEFEITO, medido em 24/08/2026 (§2.2/M5 da sprint Z0-01). O
`PROVA-DA-FOTO.txt` já registrava `ensaio` e a soma sha256 de cada PNG, mas
nenhuma linha dizia qual dos modos rodou nem qual arquivo alimentou os
dublês — e as fotos SÃO dublê desde sempre, por decisão de privacidade. Quem
lê a imagem sem ler o recibo (ou o próprio `interface.md`) não tem como
separar o que foi medido do que foi encenado. Foi exatamente esse buraco que
custou dez briefings errados em 23/08.

O QUE ESTE PORTÃO COBRA: `_gravar_prova_da_foto` grava um bloco de
proveniência — `modo:` e `fixture:` — e o `main` do retrato repassa os dois
para ela em CADA um dos três destinos canônicos (README, mesa cheia, mesa de
cinco).

A MORDIDA
---------

`test_o_recibo_da_mesa_cheia_nomeia_o_fixture_versionado` é a mordida
literal do aceite: rode com `--mesa-cheia` (aqui, chamando a função como o
`main` chama) e o recibo tem de nomear `state_full_quatro_controles.json`.
Arranque o parâmetro `fixture` (chame com `fixture=None`) e o teste reprova
dizendo que o nome do arquivo sumiu do recibo — o dublê do teste sabe
recusar, não só aprovar.

`test_o_main_repassa_modo_e_fixture_ao_recibo` fecha o outro lado: garante
que o `main` de verdade passa os dois argumentos, e não só a função isolada —
sem ela, a régua de cima poderia ficar sempre verde enquanto o `main`
continuasse chamando a função sem proveniência nenhuma.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: o módulo importado abaixo faz `gi.require_version` e
# `from gi.repository import Gtk` no escopo do módulo — mesmo as funções
# puras deste arquivo (que não tocam widget nenhum) forçam esse import.
exigir_gi_real("a proveniência do recibo da foto")

import ast
import importlib.util
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "gui-captura" / "retratar_abas.py"


def _retrato() -> Any:
    """Importa o script como módulo, sem rodar o `main`."""
    assert SCRIPT.is_file(), "retratar_abas.py sumiu"
    spec = importlib.util.spec_from_file_location("_retrato_do_recibo", SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _bancada_com_dois_pngs(tmp_path: Path) -> Path:
    """Uma pasta com dois PNGs de mentira — o suficiente para gravar recibo."""
    saida = tmp_path / "bancada"
    saida.mkdir()
    (saida / "readme_inicio.png").write_bytes(b"\x89PNG-de-mentira-1")
    (saida / "readme_status.png").write_bytes(b"\x89PNG-de-mentira-2")
    return saida


def test_o_recibo_do_modo_padrao_nao_tem_fixture_e_avisa_que_e_duble(
    tmp_path: Path,
) -> None:
    """O modo do README não lê arquivo nenhum — os dublês são fixos no script."""
    retrato = _retrato()
    saida = _bancada_com_dois_pngs(tmp_path)

    retrato._gravar_prova_da_foto(saida, modo="padrão", fixture=None)

    texto = (saida / retrato.NOME_DA_PROVA).read_text(encoding="utf-8")
    assert "modo:    padrão" in texto, texto
    assert "fixture: nenhum" in texto, texto
    assert "dublê" in texto, (
        "o recibo não repete, com todas as letras, que a imagem é dublê — a "
        "frase que o aceite da Z0-01 pede para matar a confusão entre foto e "
        "medição"
    )


def test_o_recibo_da_mesa_cheia_nomeia_o_fixture_versionado(tmp_path: Path) -> None:
    """A MORDIDA do Z0-5 (§8 da sprint Z0-01): rodar com `--mesa-cheia` tem de
    nomear `state_full_quatro_controles.json` no recibo.

    Arranque a cura: troque `fixture=retrato.FIXTURE_MESA_CHEIA` por
    `fixture=None` na chamada abaixo e rode este teste — ele reprova porque o
    nome do fixture sumiu do texto.
    """
    retrato = _retrato()
    saida = _bancada_com_dois_pngs(tmp_path)

    retrato._gravar_prova_da_foto(
        saida, modo="--mesa-cheia", fixture=retrato.FIXTURE_MESA_CHEIA
    )

    texto = (saida / retrato.NOME_DA_PROVA).read_text(encoding="utf-8")
    assert "modo:    --mesa-cheia" in texto, texto
    assert "state_full_quatro_controles.json" in texto, (
        "o recibo da mesa cheia não nomeia o fixture que alimentou os "
        f"dublês. Texto gravado:\n{texto}"
    )


def test_o_main_repassa_modo_e_fixture_ao_recibo() -> None:
    """Sem isto, a função de cima poderia estar certa e o `main` nunca a usar
    com proveniência — a régua de cima mediria uma função que ninguém chama
    dessa forma.

    Verificação por AST: toda chamada de `_gravar_prova_da_foto` dentro do
    `main` tem de trazer as keywords `modo=` e `fixture=`.
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

    chamadas = [
        no
        for no in ast.walk(main)
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Name)
        and no.func.id == "_gravar_prova_da_foto"
    ]
    assert chamadas, (
        "o `main` parou de chamar `_gravar_prova_da_foto` — nenhum destino "
        "canônico ganharia recibo"
    )
    for chamada in chamadas:
        nomes_das_keywords = {kw.arg for kw in chamada.keywords}
        faltando = {"modo", "fixture"} - nomes_das_keywords
        assert not faltando, (
            f"a chamada de `_gravar_prova_da_foto` na linha {chamada.lineno} "
            f"não passa {sorted(faltando)} — o recibo voltaria a nascer sem "
            "proveniência"
        )
