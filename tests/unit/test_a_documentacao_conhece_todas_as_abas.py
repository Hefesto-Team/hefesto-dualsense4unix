"""A documentação tem de conhecer TODAS as abas do notebook — CONFIG-08.

O defeito que este arquivo existe para não deixar voltar é banal e caro: uma aba
nasce, entra na tira, é fotografada — e a documentação continua descrevendo as
outras. Em 22/08/2026, com a leva da aba Configurações inteira commitada, o
`docs/usage/interface.md` ainda abria com *"a janela principal tem dez abas"* e
o `README.md` ainda mostrava dez imagens. Nada reclamou, porque nada
media.  (noqa-acento: verbo medir, imperfeito) verbo medir

**ELE CONHECIA UM PRODUTO SÓ, E ERA O APOSENTADO — curado em 05/09/2026.** A
janela GTK tinha onze abas e o lançador abre DEZ páginas HTML; as dez podiam
nascer, mudar de nome ou sumir sem que este portão dissesse uma palavra. Agora
ele mede o produto de hoje contra os documentos que o publicam:

| tela | a lista vem de | o documento que a publica |
| --- | --- | --- |
| as DEZ de hoje | `interface/monta.py:ABAS` | `README.md` + `AS-DEZ-ABAS-o-que-cada-uma-faz.md` |

E a foto da janela velha deixou de ser cobrada no `README.md` no mesmo dia: a
vitrine passou a mostrar as dez do produto, e as `readme_*.png` continuam
publicadas no `interface.md`, onde viraram história.

**A LISTA DE ABAS É DERIVADA DO PRÓPRIO FONTE**, e essa é a decisão que faz o
portão valer alguma coisa. Uma lista escrita à mão aqui envelheceria junto com a
documentação que ela deveria vigiar — as duas erradas, concordando entre si, e o
teste verde. `monta.ABAS` é o único lugar onde a tira de abas existe de fato;
quem acrescentar a décima primeira lá ganha este portão de graça, sem tocar
neste arquivo.

A LISTA DE FOTOS MUDOU DE DONO — 08/09/2026
--------------------------------------------

**A CAUSA MEDIDA:** ela vinha de `scripts/gui-captura/retratar_abas.py`, de
`NOMES` e de `ABAS_ESTICADAS`, lidos por `ast`. **A janela GTK saiu inteira em
06/09/2026** (`D-0609-GTK-LEVA-INTEIRA`) e o retratista dela saiu junto — o
Passo 2 da `GTK-3` apagou o script, e o Passo 1 ("os 62 testes, um a um") não
alcançou este arquivo. `_tupla_de_texto` passou a morrer no
`RETRATO.read_text()`, e os dois testes que a chamavam ficaram vermelhos.

**O fato não caducou; ele agora é mais forte.** As duas réguas perguntavam
*"toda foto que o retratista grava está publicada?"* — uma pergunta que só
alcança as fotos de UM instrumento. A pergunta que este arquivo passa a fazer é
a inversa, e cobre o defeito real: *"toda imagem que a documentação publica
existe no disco?"* A lista sai dos PRÓPRIOS DOCUMENTOS, então nenhuma imagem
escapa por ter sido gravada por outro programa, à mão, ou por programa nenhum.

E ela pega exatamente o defeito de 05/09 que esta casa já pagou: o
`AS-DEZ-ABAS-o-que-cada-uma-faz.md` citava `assets/aba-01-jogar.png` nas dez
seções e **as dez imagens não existiam** — o documento publicava dez imagens
quebradas desde que foi escrito, e régua nenhuma via.

O QUE ESTE PORTÃO **NÃO** MEDE
------------------------------

Ele não lê o conteúdo da seção: não sabe dizer se a descrição está certa, nem se
está completa. Mede presença — que a aba tenha seção própria, e que a foto dela
seja referenciada nos dois documentos que a publicam. Conteúdo é
`PROVA-DE-TELA-01`, e a palavra final ali é dela.

AS MORDIDAS (aplicadas uma a uma em 22/08/2026, todas reprovaram)
------------------------------------------------------------------

1. **Trocar a leitura de `monta.ABAS` por uma lista de dez nomes escrita à mão:**
   `test_a_lista_das_dez_vem_do_monta_e_nao_de_uma_lista_a_mao` reprova — ele
   confere que o extrator devolve exatamente as abas que o fonte tem, contando
   de novo por outro caminho.
2. **Arrancar a seção de uma aba do `AS-DEZ-ABAS`:**
   `test_toda_aba_nova_tem_secao_na_pagina_das_dez` reprova nomeando a órfã.

AS MORDIDAS DE 08/09/2026, das duas réguas que trocaram de dono (aplicadas,
as duas reprovaram):

3. **Apagar `docs/usage/assets/readme_status.png` do disco, deixando o
   `interface.md` citando-a:** `test_toda_imagem_que_a_documentacao_publica_existe`
   reprova nomeando `interface.md -> assets/readme_status.png`. É o defeito de
   05/09 exatamente, medido do lado do documento.
4. **Trocar o recorte na moldura por uma foto do viewport** (`so_a_janela=para_a_doc`
   por `so_a_janela=False`): `test_a_foto_da_doc_mostra_a_aba_inteira` reprova.
   Sem o recorte na moldura, uma aba mais alta que a dobra volta a ser
   documentada só até onde cabe — que é o motivo de `ABAS_ESTICADAS` ter
   existido na janela, e o motivo de esta régua herdar dela.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "docs/usage/interface.md"
README = RAIZ / "README.md"
ASSETS = RAIZ / "docs/usage/assets"

#: QUEM FOTOGRAFA AS DEZ. Era `scripts/gui-captura/retratar_abas.py`, apagado
#: com a janela em 06/09/2026.
RETRATO = RAIZ / "src/hefesto_dualsense4unix/interface/olhar.py"

#: O DONO DA LISTA DAS DEZ. `monta.ABAS` é o que o piloto lê para montar a tira
#: da interface nova — o mesmo argumento do glade, uma tela adiante: lista
#: escrita à mão aqui envelheceria junto com a documentação que deveria vigiar.
MONTA = RAIZ / "src/hefesto_dualsense4unix/interface/monta.py"

#: A página que descreve as dez. O `interface.md` continua descrevendo as onze
#: da janela, com a nota datada que o declara registro.
AS_DEZ = RAIZ / "docs/usage/AS-DEZ-ABAS-o-que-cada-uma-faz.md"


#: OS DOCUMENTOS QUE PUBLICAM IMAGEM, e o que cada caminho é relativo A.
#: `README.md` mora na raiz e escreve `docs/usage/assets/...`; os dois de
#: `docs/usage/` escrevem `assets/...`. Resolver contra a pasta do próprio
#: documento é o que faz as duas formas caírem no mesmo lugar.
_DOCUMENTOS_COM_IMAGEM = (
    "README.md",
    "docs/usage/interface.md",
    "docs/usage/AS-DEZ-ABAS-o-que-cada-uma-faz.md",
)

#: `![alt](caminho)`, `[texto](caminho)` e `<img src="caminho">`. O link comum
#: entra de propósito: a foto da aba mais alta da janela é publicada como LINK
#: no `interface.md` (`readme_configuracoes_inteira.png`), não como imagem, e
#: um leitor que clica num link quebrado perde a mesma coisa que num `<img>`
#: quebrado.
_REFERENCIA = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)|<img[^>]+src=\"([^\"]+)\"")

#: Marcador de prosa, não referência — um NOME DE FORMA, do tipo
#: `assets/aba-NN-….png`, com que um documento explica o padrão dos arquivos
#: em vez de apontar para um deles. Cobrar a existência de um desses seria a
#: régua reprovando a própria explicação.
#:
#: É a armadilha de prosa desta casa, e ela mordeu AQUI em 08/09/2026: o
#: `AS-DEZ-ABAS` abria com uma nota dizendo *"as imagens ainda não estão no
#: disco"* e desenhava o padrão com `aba-NN-….png` — a nota estava velha (as
#: dez existem desde 05/09) e o desenho do padrão era, para uma régua ingênua,
#: a décima primeira imagem quebrada do documento. A nota foi corrigida na
#: mesma leva e o exemplo saiu com ela; **a guarda fica**, porque a próxima
#: pessoa que for explicar um padrão de nome vai escrevê-lo do mesmo jeito.
_E_MARCADOR = ("…", "NN-", "<", ">", "{")


def _imagens_publicadas() -> list[tuple[str, str, Path]]:
    """`(documento, referência, alvo no disco)` de cada imagem que a doc publica.

    A lista sai dos DOCUMENTOS, e é por isso que ela alcança o que nenhuma
    lista de instrumento alcança: uma imagem citada e nunca gravada, ou gravada
    por um programa que já não existe.
    """
    achados: list[tuple[str, str, Path]] = []
    for nome in _DOCUMENTOS_COM_IMAGEM:
        doc = RAIZ / nome
        texto = doc.read_text(encoding="utf-8")
        for m in _REFERENCIA.finditer(texto):
            ref = m.group(1) or m.group(2)
            if not ref or not ref.lower().endswith((".png", ".jpg", ".svg", ".gif")):
                continue
            if ref.startswith(("http://", "https://")):
                continue  # emblema de serviço externo; não é arquivo desta árvore
            if any(marca in ref for marca in _E_MARCADOR):
                continue
            achados.append((nome, ref, (doc.parent / ref).resolve()))
    return achados


def _abas_da_interface_nova() -> list[tuple[str, str]]:
    """`(rótulo, slug)` das dez, lidos de `monta.ABAS` por `ast`.

    Sem importar: `monta.py` puxa a árvore da interface inteira, e um
    `ImportError` viraria "zero abas encontradas" — o jeito silencioso de este
    portão se desligar.
    """
    arvore = ast.parse(MONTA.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Assign):
            continue
        if not any(isinstance(a, ast.Name) and a.id == "ABAS" for a in no.targets):
            continue
        if not isinstance(no.value, (ast.List, ast.Tuple)):
            continue
        pares: list[tuple[str, str]] = []
        for item in no.value.elts:
            if not isinstance(item, (ast.Tuple, ast.List)) or len(item.elts) < 2:
                continue
            rotulo, slug = item.elts[0], item.elts[1]
            if isinstance(rotulo, ast.Constant) and isinstance(slug, ast.Constant):
                pares.append((str(rotulo.value), str(slug.value)))
        if pares:
            return pares
    raise AssertionError(f"ABAS não encontrada em {MONTA}")


@pytest.fixture(scope="module")
def dez() -> list[tuple[str, str]]:
    return _abas_da_interface_nova()


def test_toda_imagem_que_a_documentacao_publica_existe() -> None:
    """Nenhum documento desta casa publica imagem quebrada.

    HERDEIRA de `test_toda_foto_do_retrato_aparece_no_readme` (08/09/2026), e a
    pergunta virou do avesso: em vez de *"toda foto do instrumento está
    publicada?"* — que só alcançava as fotos de um programa, e morreu com ele —
    ela pergunta *"toda imagem publicada existe?"*, que é o defeito medido.

    A lista sai dos documentos, então ela cobre as três famílias de uma vez: as
    dez `aba-*.png` que o `olhar.py` grava hoje, as `readme_*.png` da janela
    aposentada e os cinco diálogos — nenhuma delas depende de um instrumento
    vivo para ser cobrada.
    """
    achados = _imagens_publicadas()
    assert achados, (
        "nenhuma referência de imagem encontrada nos documentos. Se eles "
        "mudaram de nome, esta régua tem de aprender os nomes novos — sem "
        "isso ela fica verde sobre coisa nenhuma."
    )

    quebradas = [
        f"{doc} -> {ref}" for doc, ref, alvo in achados if not alvo.is_file()
    ]
    assert not quebradas, (
        "a documentação publica imagem que não existe no disco:\n  "
        + "\n  ".join(quebradas)
        + "\n\nÉ o defeito de 05/09/2026 de novo: o AS-DEZ-ABAS citava as dez "
        "`aba-*.png` e nenhuma existia. Rode: "
        "interface/olhar.py --todas --publicado --doc"
    )


def test_a_foto_da_doc_mostra_a_aba_inteira() -> None:
    """A foto da documentação recorta na MOLDURA, não no que coube na tela.

    HERDEIRA de `test_a_foto_esticada_e_publicada` (08/09/2026). Na janela GTK
    a aba mais alta que 1080 px saía cortada, e a cura era uma SEGUNDA foto
    (`ABAS_ESTICADAS`, `*_inteira.png`) — porque a janela tinha altura fixa e o
    retratista fotografava o viewport.

    A página HTML não precisa da segunda foto: `moldura.screenshot()` do
    Playwright captura o elemento INTEIRO, rolando se preciso. Mas essa
    propriedade depende de uma linha — `so_a_janela=para_a_doc` — e trocá-la por
    uma foto de viewport devolve o corte em silêncio, com a régua acima verde
    (o arquivo existiria; só estaria cortado). Por isso o fato tem régua
    própria, e ela mede o modo `--doc`.
    """
    fonte = RETRATO.read_text(encoding="utf-8")
    arvore = ast.parse(fonte)

    chamadas = [
        ast.unparse(no)
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call)
    ]

    recorte = [c for c in chamadas if "so_a_janela=para_a_doc" in c]
    assert recorte, (
        "o modo `--doc` deixou de recortar na moldura da aba. Sem "
        "`so_a_janela=para_a_doc` a foto vira retrato do viewport, e toda aba "
        "mais alta que ele passa a ser documentada só até onde coube — que é a "
        "situação que `ABAS_ESTICADAS` curava na janela, com uma segunda foto. "
        f"Chamadas encontradas em {RETRATO.name}: "
        + "; ".join(c for c in chamadas if "so_a_janela" in c)
    )

    assert "moldura.screenshot" in fonte, (
        "o recorte deixou de sair do elemento. `moldura.screenshot()` captura o "
        "elemento inteiro, rolando se preciso; um `pg.screenshot(clip=...)` "
        "cortaria de novo no que cabe na tela."
    )


# ---------------------------------------------------------------------------
# AS DEZ DE HOJE — 05/09/2026
#
# Tudo acima mede a janela GTK, que continua viva e continua documentada em
# `interface.md`. O que segue mede o produto que o lançador abre, e a lista vem
# do mesmo lugar que o piloto lê: `monta.ABAS`.
# ---------------------------------------------------------------------------


def test_a_lista_das_dez_vem_do_monta_e_nao_de_uma_lista_a_mao(
    dez: list[tuple[str, str]],
) -> None:
    """A régua é conferida contra o fonte por um caminho independente.

    O mesmo argumento do irmão que confere o glade: um extrator que devolvesse
    constante deixaria os outros verdes para sempre. A contagem independente é
    um `re.findall` sobre o texto cru — outra biblioteca, outro caminho.
    """
    assert len(dez) == 10, f"monta.ABAS tem {len(dez)} entradas, e as abas são dez: {dez}"

    bruto = MONTA.read_text(encoding="utf-8")
    trecho = bruto.split("ABAS", 1)[1]
    por_texto = re.findall(r'\("([^"]+)"\s*,\s*"(\d\d-[^"]+)"\)', trecho)
    assert dez == por_texto[: len(dez)], (
        "as duas leituras de monta.ABAS discordam — a régua não está lendo o "
        f"fonte: ast={dez} contra regex={por_texto[: len(dez)]}"
    )


def test_toda_aba_nova_tem_secao_na_pagina_das_dez(dez: list[tuple[str, str]]) -> None:
    """Cada uma das dez tem um `## N. <rótulo>` em `AS-DEZ-ABAS`.

    O título carrega o rótulo EXATO da tira, e não uma paráfrase: quem abre o
    produto procura na documentação a palavra que está vendo na tela.
    """
    texto = AS_DEZ.read_text(encoding="utf-8")
    titulos = set(re.findall(r"^## (.+)$", texto, re.M))
    orfas = [
        rotulo
        for i, (rotulo, _) in enumerate(dez, start=1)
        if f"{i}. {rotulo}" not in titulos
    ]
    assert not orfas, (
        f"abas da interface nova sem seção em {AS_DEZ.name}: {', '.join(orfas)}. "
        f"Títulos presentes: {sorted(titulos)}"
    )


def test_toda_foto_das_dez_existe_e_e_publicada(dez: list[tuple[str, str]]) -> None:
    """A foto de cada aba nova existe no disco e aparece nos dois documentos.

    O defeito que isto não deixa voltar estava vivo até 05/09/2026: o
    `AS-DEZ-ABAS` citava `assets/aba-01-jogar.png` nas dez seções e **as dez
    imagens não existiam** — o documento publicava dez imagens quebradas desde
    que foi escrito, e régua nenhuma via.

    Quem as grava é `interface/olhar.py --todas --publicado --doc`.
    """
    readme = README.read_text(encoding="utf-8")
    as_dez = AS_DEZ.read_text(encoding="utf-8")
    faltando: list[str] = []
    for _, slug in dez:
        arquivo = f"aba-{slug}.png"
        if not (ASSETS / arquivo).exists():
            faltando.append(f"{arquivo} (não existe em {ASSETS.name}/)")
            continue
        onde = [
            documento
            for documento, conteudo in (("README.md", readme), (AS_DEZ.name, as_dez))
            if arquivo not in conteudo
        ]
        if onde:
            faltando.append(f"{arquivo} (falta em {', '.join(onde)})")
    assert not faltando, (
        "fotos das dez abas que a documentação promete e não entrega: "
        + "; ".join(faltando)
        + ". Rode: interface/olhar.py --todas --publicado --doc"
    )
