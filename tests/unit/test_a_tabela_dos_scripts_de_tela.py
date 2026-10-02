"""A tabela de `COMO-OLHAR-A-TELA.md` envelheceu calada — CINCO-SCRIPTS-01."""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
GUIA = RAIZ / "docs" / "method" / "COMO-OLHAR-A-TELA.md"

RETRATISTA = "src/hefesto_dualsense4unix/interface/olhar.py"

_CAMINHO = re.compile(r"[\w./-]+\.(?:py|sh)")


_TITULO = "instrumentos de tela"


def _linhas_da_tabela() -> list[str]:
    """As linhas de instrumento — só as da tabela DESTA seção."""
    assert GUIA.is_file(), f"{GUIA} sumiu — é o primeiro arquivo a ler nesta casa"
    texto = GUIA.read_text(encoding="utf-8")
    dentro = False
    colhidas: list[str] = []
    for linha in texto.splitlines():
        if linha.startswith("## "):
            dentro = _TITULO in linha
            continue
        if not dentro:
            continue
        crua = linha.strip()
        if not crua.startswith("|"):
            continue
        if set(crua) <= set("|-: ") or crua.startswith("| instrumento"):
            continue
        colhidas.append(crua)
    return colhidas


def test_a_tabela_nao_nomeia_caminho_que_nao_existe() -> None:
    """Linha sobrevivente de ferramenta apagada manda a pessoa ao vazio."""
    fantasmas = sorted(
        {
            caminho
            for linha in _linhas_da_tabela()
            for caminho in _CAMINHO.findall(linha)
            if not (RAIZ / caminho).is_file()
        }
    )

    assert not fantasmas, (
        f"a tabela de `docs/method/COMO-OLHAR-A-TELA.md` cita {', '.join(fantasmas)}, "
        "que não existe nesta árvore. Este é o arquivo que se lê PRIMEIRO "
        "quando o trabalho toca a tela: um caminho morto ali manda "
        "a próxima pessoa rodar um comando que não roda, e ela conclui que a "
        "casa não tem a ferramenta."
    )


def test_a_tabela_nomeia_o_retratista() -> None:
    """Uma tabela de instrumentos de tela sem o que TIRA A FOTO é a lacuna de 2026-08."""
    tabela = "\n".join(_linhas_da_tabela())

    assert RETRATISTA in tabela, (
        f"a tabela de `docs/method/COMO-OLHAR-A-TELA.md` não cita {RETRATISTA}, "
        "que é o retratista das dez páginas e a 'regra em uma linha' do próprio "
        "guia. Sem ele na tabela, quem chega não descobre como fotografar a "
        "tela — e refaz à mão o trabalho que uma execução resolve."
    )


def test_o_titulo_da_secao_diz_o_numero_certo() -> None:
    """"Os três scripts desta pasta" com cinco no disco foi como isto começou."""
    texto = GUIA.read_text(encoding="utf-8")
    quantos = len(_linhas_da_tabela())
    por_extenso = {
        2: "dois",
        3: "três",
        4: "quatro",
        5: "cinco",
        6: "seis",
        7: "sete",
        8: "oito",
    }.get(quantos)

    titulos = [
        linha
        for linha in texto.splitlines()
        if linha.startswith("## ") and _TITULO in linha
    ]
    assert titulos, (
        "a seção que apresenta os instrumentos de tela sumiu de "
        "`docs/method/COMO-OLHAR-A-TELA.md`."
    )
    assert por_extenso is not None, (
        f"a tabela passou a ter {quantos} linhas e este teste não sabe escrever "
        "esse número por extenso — acrescente-o ao mapa acima."
    )

    titulo = titulos[0]
    assert por_extenso in titulo, (
        f"o título diz {titulo.strip('# ').strip()!r}, e a tabela tem {quantos} "
        f"linhas ({por_extenso}). Um número errado no primeiro arquivo que se "
        "manda ler é pior que número nenhum: ele faz quem chega parar de "
        "procurar depois do terceiro."
    )
