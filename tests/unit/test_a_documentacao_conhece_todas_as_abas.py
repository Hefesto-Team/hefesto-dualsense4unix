"""A documentação tem de conhecer TODAS as abas do notebook — CONFIG-08.

O defeito que este arquivo existe para não deixar voltar é banal e caro: uma aba
nasce, entra na tira, é fotografada — e a documentação continua descrevendo as
outras. Em 22/08/2026, com a leva da aba Configurações inteira commitada, o
`docs/usage/interface.md` ainda abria com *"a janela principal tem dez abas"* e
o `README.md` ainda mostrava dez imagens. Nada reclamou, porque nada
media.  (noqa-acento: verbo medir, imperfeito)

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
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

GLADE = RAIZ / "src/hefesto_dualsense4unix/gui/main.glade"
INTERFACE = RAIZ / "docs/usage/interface.md"
README = RAIZ / "README.md"
RETRATO = RAIZ / "scripts/gui-captura/retratar_abas.py"
ASSETS = RAIZ / "docs/usage/assets"

#: O id do `GtkNotebook` da janela principal. É o mesmo que o `app.py` usa; a
#: janela tem outros notebooks em potencial, e mirar pelo id evita que um deles
#: entre na conta um dia.
NOTEBOOK = "main_notebook"


def _abas_do_glade() -> list[str]:
    """Os rótulos das abas, na ordem da tira, lidos do XML.

    Um `<child type="tab">` do notebook é exatamente uma aba — é o contrato do
    `GtkNotebook`, não uma convenção deste projeto. O rótulo sai da propriedade
    `label` do `GtkLabel` filho, que é o texto que a pessoa lê na tira.
    """
    raiz = ET.parse(GLADE).getroot()
    for objeto in raiz.iter("object"):
        if objeto.get("class") != "GtkNotebook" or objeto.get("id") != NOTEBOOK:
            continue
        rotulos: list[str] = []
        for filho in objeto.findall("child"):
            if filho.get("type") != "tab":
                continue
            alvo = filho.find("object")
            if alvo is None:
                continue
            for propriedade in alvo.findall("property"):
                if propriedade.get("name") == "label" and propriedade.text:
                    rotulos.append(propriedade.text.strip())
        return rotulos
    raise AssertionError(f"notebook {NOTEBOOK} não encontrado em {GLADE}")


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


@pytest.fixture(scope="module")
def abas() -> list[str]:
    return _abas_do_glade()


def test_a_lista_de_abas_vem_do_glade_e_nao_de_uma_lista_a_mao(
    abas: list[str],
) -> None:
    """A régua é conferida contra o XML por um caminho independente.

    Este teste não olha documentação nenhuma: ele existe porque o valor dos
    outros três depende inteiramente de o extrator estar lendo o glade de
    verdade. Um extrator que devolvesse uma constante deixaria os três verdes
    para sempre, e é a forma mais fácil de este portão morrer sem ninguém ver.

    A contagem independente é um `re.findall` sobre o texto cru — outra
    biblioteca, outro caminho, mesmo arquivo.
    """
    assert abas, "nenhuma aba lida do glade"

    bruto = GLADE.read_text(encoding="utf-8")
    trecho = bruto.split(f'id="{NOTEBOOK}"', 1)[1]
    por_texto = [
        rotulo
        for bloco in re.findall(r'<child type="tab">(.*?)</child>', trecho, re.S)
        for rotulo in re.findall(r'<property name="label"[^>]*>(.*?)</property>', bloco)
    ]
    assert abas == por_texto, (
        "as duas leituras do glade discordam — a régua deste portão não está "
        f"lendo o XML: ElementTree={abas} contra regex={por_texto}"
    )


def test_toda_aba_do_glade_tem_secao_no_interface(abas: list[str]) -> None:
    """Cada aba da tira tem um `## <rótulo>` no `interface.md`.

    O título da seção é o rótulo EXATO da tira, e não uma paráfrase: quem abre a
    janela procura na documentação a palavra que está vendo na tela.
    """
    texto = INTERFACE.read_text(encoding="utf-8")
    titulos = set(re.findall(r"^## (.+)$", texto, re.M))
    orfas = [aba for aba in abas if aba not in titulos]
    assert not orfas, (
        f"abas sem seção no interface.md: {', '.join(orfas)}. "
        "Uma aba na tira sem seção na documentação é aba invisível para quem "
        f"não a descobriu sozinho. Títulos presentes: {sorted(titulos)}"
    )


def test_toda_foto_do_retrato_aparece_no_readme() -> None:
    """Toda foto que o retrato grava é publicada nos dois documentos.

    O `README.md` é a vitrine e o `interface.md` é o manual. Uma foto que existe
    no disco e não aparece em nenhum dos dois é trabalho feito e não entregue —
    e foi exatamente o estado da aba nova entre `c6b8daa` e esta leva.
    """
    readme = README.read_text(encoding="utf-8")
    interface = INTERFACE.read_text(encoding="utf-8")
    faltando: list[str] = []
    for nome in _tupla_de_texto("NOMES"):
        arquivo = f"{nome}.png"
        assert (ASSETS / arquivo).exists(), f"{arquivo} não existe em {ASSETS}"
        onde = [
            documento
            for documento, conteudo in (("README.md", readme), ("interface.md", interface))
            if arquivo not in conteudo
        ]
        if onde:
            faltando.append(f"{arquivo} (falta em {', '.join(onde)})")
    assert not faltando, (
        "fotos que o retratar_abas.py grava e a documentação não publica: "
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
