"""A documentação tem de conhecer TODAS as abas do notebook — CONFIG-08.

O defeito que este arquivo existe para não deixar voltar é banal e caro: uma aba
nasce, entra na tira, é fotografada — e a documentação continua descrevendo as
outras. Em 22/08/2026, com a leva da aba Configurações inteira commitada, o
`docs/usage/interface.md` ainda abria com *"a janela principal tem dez abas"* e
o `README.md` ainda mostrava dez imagens. Nada reclamou, porque nada
media.  (noqa-acento: verbo medir, imperfeito) verbo medir

**ELE CONHECIA UM PRODUTO SÓ, E ERA O APOSENTADO — curado em 05/09/2026.** A
janela GTK tem onze abas e o lançador abre DEZ páginas HTML; as dez podiam
nascer, mudar de nome ou sumir sem que este portão dissesse uma palavra. Agora
ele mede as duas telas, cada uma contra o documento que a publica:

| tela | a lista vem de | o documento que a publica |
| --- | --- | --- |
| as DEZ de hoje | `interface/monta.py:ABAS` | `README.md` + `AS-DEZ-ABAS-o-que-cada-uma-faz.md` |
| as ONZE da janela | `gui/main.glade` | `docs/usage/interface.md`, que é registro datado |

E a foto da janela velha deixou de ser cobrada no `README.md` no mesmo dia: a
vitrine passou a mostrar as dez do produto, e as `readme_*.png` continuam
publicadas onde viraram história.

**A LISTA DE ABAS É DERIVADA DO PRÓPRIO GLADE**, e essa é a decisão que faz o
portão valer alguma coisa. Uma lista escrita à mão aqui envelheceria junto com a
documentação que ela deveria vigiar — as duas erradas, concordando entre si, e o
teste verde. O `main.glade` é o único lugar onde a tira de abas existe de fato;
quem acrescentar a décima segunda aba lá ganha este portão de graça, sem tocar
neste arquivo.

Pelo mesmo argumento, a lista de FOTOS vem do
`scripts/gui-captura/retratar_abas.py` — de `NOMES` e de `ABAS_ESTICADAS`, lidos
por `ast` sem executar o módulo (importá-lo puxaria GTK e montaria a janela).

O QUE ESTE PORTÃO **NÃO** MEDE
------------------------------

Ele não lê o conteúdo da seção: não sabe dizer se a descrição está certa, nem se
está completa. Mede presença — que a aba tenha seção própria, e que a foto dela
seja referenciada nos dois documentos que a publicam. Conteúdo é
`PROVA-DE-TELA-01`, e a palavra final ali é dela.

AS MORDIDAS (aplicadas uma a uma em 22/08/2026, todas reprovaram)
------------------------------------------------------------------

1. **Arrancar a seção "## Configurações" do `interface.md`:**
   `test_toda_aba_do_glade_tem_secao_no_interface` reprova nomeando a aba órfã —
   ``abas sem seção no interface.md: Configurações``.
2. **Arrancar a linha da imagem nova do `README.md`:**
   `test_toda_foto_do_retrato_aparece_no_readme` reprova nomeando o arquivo
   (``readme_configuracoes.png``).
3. **Trocar a leitura do glade por uma lista de dez nomes escrita à mão:**
   `test_a_lista_de_abas_vem_do_glade_e_nao_de_uma_lista_a_mao` reprova — ele
   confere que o extrator devolve exatamente as abas que o XML tem, contando de
   novo por outro caminho.
4. **Apagar a menção à foto esticada no `interface.md`:**
   `test_a_foto_esticada_e_publicada` reprova. Sem ela a aba mais alta da janela
   ficaria documentada pela metade, que é o motivo de a segunda foto existir.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "docs/usage/interface.md"
README = RAIZ / "README.md"
RETRATO = RAIZ / "scripts/gui-captura/retratar_abas.py"
ASSETS = RAIZ / "docs/usage/assets"

#: O DONO DA LISTA DAS DEZ. `monta.ABAS` é o que o piloto lê para montar a tira
#: da interface nova — o mesmo argumento do glade, uma tela adiante: lista
#: escrita à mão aqui envelheceria junto com a documentação que deveria vigiar.
MONTA = RAIZ / "src/hefesto_dualsense4unix/interface/monta.py"

#: A página que descreve as dez. O `interface.md` continua descrevendo as onze
#: da janela, com a nota datada que o declara registro.
AS_DEZ = RAIZ / "docs/usage/AS-DEZ-ABAS-o-que-cada-uma-faz.md"


def _tupla_de_texto(nome: str) -> tuple[str, ...]:
    """Uma tupla de literais do `retratar_abas.py`, lida SEM executar o módulo.

    Importar o script puxaria `gi`, montaria a janela e faria deste teste um
    teste de GTK. `ast` responde a pergunta que interessa — *o que está escrito
    lá* — sem nada disso.
    """
    arvore = ast.parse(RETRATO.read_text(encoding="utf-8"))
    for no in arvore.body:
        if not isinstance(no, ast.Assign):
            continue
        alvos = [a.id for a in no.targets if isinstance(a, ast.Name)]
        if nome not in alvos or not isinstance(no.value, ast.Tuple):
            continue
        return tuple(
            item.value
            for item in no.value.elts
            if isinstance(item, ast.Constant) and isinstance(item.value, str)
        )
    raise AssertionError(f"{nome} não encontrada em {RETRATO}")


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


def test_toda_foto_do_retrato_aparece_no_readme() -> None:
    """Toda foto da JANELA é publicada no `interface.md`.

    Ela era cobrada nos DOIS documentos, e o `README.md` saiu da conta em
    05/09/2026: a vitrine passou a mostrar as dez abas do produto, e as
    `readme_*.png` viraram o registro datado que o `interface.md` guarda. Cobrar
    a vitrine pela foto da janela aposentada obrigaria o README a publicar as
    duas telas para sempre — que é a contradição que esta casa apaga, não
    documenta.
    """
    interface = INTERFACE.read_text(encoding="utf-8")
    faltando: list[str] = []
    for nome in _tupla_de_texto("NOMES"):
        arquivo = f"{nome}.png"
        assert (ASSETS / arquivo).exists(), f"{arquivo} não existe em {ASSETS}"
        if arquivo not in interface:
            faltando.append(arquivo)
    assert not faltando, (
        "fotos que o retratar_abas.py grava e o interface.md não publica: "
        + "; ".join(faltando)
    )


def test_a_foto_esticada_e_publicada() -> None:
    """A aba que não cabe na janela tem a segunda foto, e ela é citada.

    `ABAS_ESTICADAS` existe porque uma aba mais alta que 1080px sai cortada, e
    uma foto cortada é pior que nenhuma: quem lê conclui que o que ficou abaixo
    da dobra não existe. Gravar a esticada e não publicá-la desfaz a cura.
    """
    interface = INTERFACE.read_text(encoding="utf-8")
    for nome in _tupla_de_texto("ABAS_ESTICADAS"):
        arquivo = f"{nome}_inteira.png"
        assert (ASSETS / arquivo).exists(), (
            f"{arquivo} não existe: o retrato lista {nome} em ABAS_ESTICADAS e "
            "a foto da página inteira não foi commitada"
        )
        assert arquivo in interface, (
            f"{arquivo} não é citada no interface.md — a aba mais alta da "
            "janela ficaria documentada só até a dobra"
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
