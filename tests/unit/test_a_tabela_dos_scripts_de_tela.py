"""A tabela de `COMO-OLHAR-A-TELA.md` envelheceu calada — CINCO-SCRIPTS-01.

`docs/process/COMO-OLHAR-A-TELA.md` é o arquivo que o `CLAUDE.md` manda ler
**primeiro** quando o trabalho toca a tela. Ele trazia uma seção chamada
"Os três scripts desta pasta, e qual usar", com uma tabela de três linhas —
enquanto `ls scripts/gui-captura/` devolvia **cinco** arquivos.

E o que faltava não era detalhe: faltava o `retratar_dialogos.py`, cujas
imagens o `docs/usage/interface.md` **já publicava**. Quem chegasse pelo guia
não descobriria que existe maneira de fotografar diálogo, e a leva seguinte
pagaria de novo o preço que a `DIALOGO-QUE-MATA-A-JANELA-01` já pagou.

A PASTA MORREU E A RÉGUA NÃO — 06/09/2026, sprint `GTK-3`
----------------------------------------------------------

`scripts/gui-captura/` era o estúdio de fotografia da JANELA GTK, aposentada
por decisão dela (`D-0609-GTK-LEVA-INTEIRA`). Os cinco arquivos saíram, e com
eles a pasta que esta régua listava.

**O DEFEITO QUE ELA EXISTE PARA PEGAR NÃO SAIU JUNTO**, e ele é o mesmo: *o
primeiro arquivo que se manda ler nomeia uma ferramenta que não existe, ou
deixa de nomear a que existe.* Os dois lados agora se medem sem uma pasta:

* **caminho fantasma** — todo caminho de arquivo citado na tabela tem de EXISTIR
  nesta árvore. É a metade que continua idêntica, e é a que reprovaria hoje se
  a tabela tivesse ficado com o `retratar_abas.py` dentro;
* **o retratista nomeado** — a tabela tem de citar
  `src/hefesto_dualsense4unix/interface/olhar.py`. Ele é a "regra em uma linha"
  do guia, e uma tabela de instrumentos de tela sem o que tira a foto é
  exatamente a lacuna de 2026-08;
* **o número no título** — a seção tem de dizer, por extenso, quantas linhas a
  tabela tem. Foi um número errado no título que fez a versão anterior desta
  régua nascer.

**POR QUE NÃO HÁ MAIS UMA PASTA A LISTAR, e a ausência é decisão:** os
instrumentos de tela de hoje não moram juntos — o retratista e o piloto estão
em `src/…/interface/` (dependem do pacote), a ponte JS em `src/…/gui/`. Uma
lista escrita AQUI seria um terceiro dono do fato, que é a razão que a versão
anterior deste arquivo deu para olhar a pasta em vez de digitar nomes. Então a
régua deixou de perguntar "está tudo na tabela?" — pergunta que nenhuma pasta
responde hoje — e passa a cobrar o que tem dono: o caminho existe, o retratista
está lá, e o número bate.

A MORDIDA
---------

Apagar a linha do `olhar.py`, trocar um caminho por um que não existe, ou mexer
no número do título sem mexer na tabela: os três reprovam nomeando.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
GUIA = RAIZ / "docs" / "process" / "COMO-OLHAR-A-TELA.md"

#: O retratista das dez páginas — a "regra em uma linha" do guia. Se ele sair
#: da tabela, o guia deixa de responder à pergunta que mais se faz.
RETRATISTA = "src/hefesto_dualsense4unix/interface/olhar.py"

#: O que, numa célula, é um caminho de arquivo desta árvore.
_CAMINHO = re.compile(r"[\w./-]+\.(?:py|sh)")


#: O título da seção que carrega a tabela. O guia tem OUTRAS tabelas — as das
#: réguas que mentiram, a dos zeros da GPU —, e uma varredura de todas as linhas
#: que começam com `|` colheria 23 em vez de 4. Foi o primeiro defeito desta
#: reescrita, e ele é o mesmo de sempre: o instrumento medindo outra coisa.
_TITULO = "instrumentos de tela"


def _linhas_da_tabela() -> list[str]:
    """As linhas de instrumento — só as da tabela DESTA seção.

    O cabeçalho e o traço não são instrumentos, e a colheita para no próximo
    `##`: o que vem depois é outra seção, com outra tabela.
    """
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
        f"a tabela de `docs/process/COMO-OLHAR-A-TELA.md` cita {', '.join(fantasmas)}, "
        "que não existe nesta árvore. Este é o arquivo que o `CLAUDE.md` manda "
        "ler PRIMEIRO quando o trabalho toca a tela: um caminho morto ali manda "
        "a próxima pessoa rodar um comando que não roda, e ela conclui que a "
        "casa não tem a ferramenta."
    )


def test_a_tabela_nomeia_o_retratista() -> None:
    """Uma tabela de instrumentos de tela sem o que TIRA A FOTO é a lacuna de 2026-08."""
    tabela = "\n".join(_linhas_da_tabela())

    assert RETRATISTA in tabela, (
        f"a tabela de `docs/process/COMO-OLHAR-A-TELA.md` não cita {RETRATISTA}, "
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
        "`docs/process/COMO-OLHAR-A-TELA.md`."
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
