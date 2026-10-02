"""A `--prova-gesto` não pode clicar num botão que não existe mais."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
FONTE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "controles_vivos.py"
PAGINAS = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "paginas"  # (noqa-acento) pasta
PUBLICADO = PAGINAS / "02-controles.html"
BANCADA = RAIZ / "mockup" / "02-controles.html"


def _roteiro() -> tuple[tuple[int, str], ...]:
    """O roteiro lido do fonte por AST — sem importar `gi`, sem abrir janela."""
    arvore = ast.parse(FONTE.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if (
            isinstance(no, ast.AnnAssign)
            and isinstance(no.target, ast.Name)
            and no.target.id == "ROTEIRO_DA_PROVA_DE_GESTO"
            and no.value is not None
        ):
            passos = ast.literal_eval(no.value)
            return tuple((p[0], p[1]) for p in passos)
    raise AssertionError(
        "o `ROTEIRO_DA_PROVA_DE_GESTO` sumiu do fonte — se ele voltou a ser uma "
        "lista embutida no meio do método, esta régua deixou de alcançá-lo, e "
        "com ela o portão que impede a prova de clicar no vazio"
    )


def _alvos_do_seletor(seletor: str) -> list[str]:
    """Os pedaços do seletor que TÊM de aparecer na página, um a um."""
    partes: list[str] = []
    for atributo, valor in re.findall(r'\[([\w-]+)="([^"]*)"\]', seletor):
        partes.append(f'{atributo}="{valor}"')
    for classe in re.findall(r"\.([\w-]+)", seletor):
        partes.append(f"{classe}")
    return partes


@pytest.mark.parametrize("alvo", [PUBLICADO, BANCADA], ids=["publicado", "mockup"])
def test_todo_passo_do_roteiro_acha_alvo_na_tela(alvo: Path) -> None:
    """MORDIDA 1: cada seletor do roteiro existe na página. Nos DOIS lugares."""
    html = alvo.read_text(encoding="utf-8")
    mortos: list[str] = []
    for _ms, seletor in _roteiro():
        for pedaco in _alvos_do_seletor(seletor):
            if pedaco not in html:
                mortos.append(f"{seletor}  (falta {pedaco!r})")
    assert not mortos, (
        f"a `--prova-gesto` clica em alvo que não existe em {alvo.name}:\n  "
        + "\n  ".join(mortos)
        + "\n\nUm passo que bate em `null` levanta dentro do WebKit e o `_js` "
        "não lê o erro: a prova dá VERDE sobre um botão morto."
    )


def test_o_roteiro_cobre_o_microfone_e_o_alto_falante() -> None:
    """MORDIDA 2: os DOIS botões da coluna do som continuam no roteiro."""
    seletores = [s for _ms, s in _roteiro()]
    for botao in ('[data-gesto="mic-retorno"]', '[data-mudo="alto-falante"]'):
        assert any(botao in s for s in seletores), (
            f"o roteiro deixou de clicar {botao} — é o defeito de 29/08 "
            f"voltando: {seletores}"
        )


def test_todo_botao_de_rota_tem_dono_na_tabela() -> None:
    """MORDIDA 4: a tabela de donos não pode ficar para trás da fileira."""
    fonte = FONTE.read_text(encoding="utf-8")
    inicio = fonte.index("DONOS_DOS_GESTOS = {")
    tabela = fonte[inicio : fonte.index("\n}\n", inicio)]
    declarados = set(re.findall(r'"rota:([a-z]+)"', tabela))
    for alvo in (PUBLICADO, BANCADA):
        if not alvo.is_file():
            continue
        na_pagina = set(re.findall(r'data-rota="([a-z]+)"', alvo.read_text(encoding="utf-8")))
        assert na_pagina, f"{alvo.name} não tem botão de rota nenhum — a fileira sumiu?"
        sem_dono = sorted(na_pagina - declarados)
        assert not sem_dono, (
            f"{alvo.name} tem botão de rota sem linha em `DONOS_DOS_GESTOS`: "
            f"{sem_dono}. A `--prova-gesto` vai dizer «nada foi aplicado» sobre "
            f"um botão que tem dono em `pacotes/a02_controles.rota`, e quem ler "
            f"o relatório vai concluir que o produto está quebrado."
        )


def test_o_passo_confessa_quando_nao_acha_o_alvo() -> None:
    """MORDIDA 3: o clique sintético reporta `achou`, em vez de estourar calado."""
    fonte = FONTE.read_text(encoding="utf-8")
    assert "def _clique_que_confessa(" in fonte
    arvore = ast.parse(fonte)
    corpo = next(
        (n for n in ast.walk(arvore)
         if isinstance(n, ast.FunctionDef) and n.name == "_clique_que_confessa"),
        None,
    )
    assert corpo is not None
    texto = ast.get_source_segment(fonte, corpo) or ""
    assert "postMessage" in texto, (
        "o clique sintético não manda nada de volta — um alvo ausente volta a "
        "sumir sem uma linha vermelha"
    )
    assert "achou" in texto, "o recado não diz SE o alvo foi achado"
    assert "if(e){e.click();}" in texto, (
        "o clique deixou de ser condicional: com o alvo ausente ele volta a "
        "levantar `TypeError` dentro do WebKit, calado"
    )


def test_o_relato_final_mostra_os_alvos_mortos() -> None:
    """MORDIDA 4: o número aparece no relato, senão ninguém o lê."""
    fonte = FONTE.read_text(encoding="utf-8")
    assert "alvos_mortos_do_roteiro" in fonte
    assert "ALVOS MORTOS" in fonte, (
        "o relato final não nomeia os alvos mortos — o contador existe e "
        "ninguém o vê"
    )
