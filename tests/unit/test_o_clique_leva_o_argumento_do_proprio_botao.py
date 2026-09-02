#!/usr/bin/env python3
"""O clique tem de levar ao Python o que o BOTÃO diz — não uma lista de nomes.

O DEFEITO, medido em 02/09/2026 com o dublê da casa: seis gestos da aba
Conexões recusavam dizendo *"o clique não disse qual aparelho"*, e o diagnóstico
que circulava era que o clique automático não dizia em qual CONTROLE agir.

**Não é o controle.** Os seis leem o argumento do PRÓPRIO BOTÃO:

    escolher-aparelho   o.get("caminho")    ← `data-caminho`, gerado em a08_conexoes.py:541
    escolher-entrada    o.get("entrada")    ← `data-entrada`, no HTML publicado
    tirar-daqui         o.get("entrada")
    nova-entrada        o.get("face")
    nova-extensao       o.get("entrada")
    nova-face           o.get("valor")

E o ouvinte do BOOTSTRAP encaminhava uma lista escrita à mão de catorze
atributos, em que NENHUM dos três aparecia. Logo os seis recusavam **para ela
também**, num clique de rato de verdade — não era defeito do instrumento.

A CURA É GENÉRICA de propósito: o ouvinte copia o `dataset` INTEIRO antes de
sobrescrever com a lista explícita. Uma lista escrita à mão de atributos que a
página pode ter só cresce quando alguém se lembra, e o esquecimento é silencioso
— é a mesma forma de defeito que esta casa já nomeou noutros lugares.

A MORDIDA: tire o `Object.assign({}, d)` do BOOTSTRAP e
``test_o_bootstrap_copia_o_dataset_inteiro`` reprova, nomeando os atributos que
a página tem e o clique deixaria de carregar.

O QUE ESTE TESTE **NÃO** PROVA: que o daemon dela aceitou. A prova no aparelho é
do orquestrador, serializada — há dois controles na mesa dela e treze frentes
rodando juntas, e um clique de régua muda o aparelho debaixo das outras.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PILOTO = RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"
PACOTES = RAIZ / "src/hefesto_dualsense4unix/interface/pacotes"
PAGINAS = RAIZ / "src/hefesto_dualsense4unix/interface/paginas"

#: Os atributos que o ouvinte nomeia UM A UM. Não é a lista boa — é a lista que
#: existia sozinha, e é contra ela que se mede o que faltava.
#:
#: ELA COLHE DE MAIS DE PROPÓSITO (qualquer `nome:` do JS, e não só os do objeto
#: do clique): colher demais só ENCOLHE a lista de órfãos, e um teste que erra
#: para o lado de acusar menos não inventa defeito. Cravar o começo da linha
#: perdia os que dividem linha com um vizinho — e a mensagem da mordida saía
#: nomeando `forca` e `player`, que estão lá.
_EXPLICITOS = re.compile(r"[\s,{]([a-zA-Z]+):")


def _bootstrap() -> str:
    fonte = PILOTO.read_text(encoding="utf-8")
    achou = re.search(r"BOOTSTRAP = r\"\"\"(.*?)\n\"\"\"", fonte, re.S)
    assert achou, "o piloto perdeu o BOOTSTRAP — a tela ficou sem ouvinte de clique"
    return achou.group(1)


def _chaves_que_os_gestos_leem() -> set[str]:
    """O que as funções de gesto pedem do clique, lido do código dos pacotes."""
    fora: set[str] = set()
    for arq in sorted(PACOTES.glob("a[0-9][0-9]_*.py")):
        fora |= set(re.findall(r'o\.get\("([a-z_]+)"', arq.read_text(encoding="utf-8")))
    return fora


def _data_das_paginas() -> set[str]:
    """Os `data-*` que as dez páginas publicadas trazem, em nome camelCase.

    É a forma com que o `dataset` do DOM os entrega — `data-mic-modo` chega como
    `micModo` —, que é a mesma com que eles chegam ao Python.
    """
    fora: set[str] = set()
    for arq in sorted(PAGINAS.glob("[01][0-9]-*.html")):
        for cru in re.findall(r'\bdata-([a-z][a-z0-9-]*)=', arq.read_text(encoding="utf-8")):
            partes = cru.split("-")
            fora.add(partes[0] + "".join(p.capitalize() for p in partes[1:]))
    return fora


def test_o_bootstrap_copia_o_dataset_inteiro():
    """A cura, e a mordida mora aqui: sem a cópia, estes atributos somem.

    O teste não se contenta em ver a linha: ele NOMEIA os atributos que a página
    tem, os gestos leem, e a lista explícita não carrega. Se a cópia sair, é
    essa lista que aparece na mensagem — não um "faltou uma linha".
    """
    js = _bootstrap()
    lidos = _chaves_que_os_gestos_leem()
    das_paginas = _data_das_paginas()
    explicitos = set(_EXPLICITOS.findall(js))
    orfaos = sorted((lidos & das_paginas) - explicitos)
    assert orfaos, (
        "este teste ficou sem caso: nenhum atributo que os gestos leem está "
        "fora da lista explícita do ouvinte. Se as páginas mudaram, escolha "
        "outro caso — um teste sem caso passa por qualquer motivo.")
    assert "Object.assign({}, d)" in js, (
        f"o ouvinte voltou a encaminhar só a lista escrita à mão, e estes "
        f"atributos que a página TEM e os gestos LEEM não chegam mais ao "
        f"Python: {orfaos}. Os gestos que dependem deles vão recusar dizendo "
        f"'o clique não disse qual...' — para ela, num clique de rato de "
        f"verdade, não só para a régua.")


def test_os_tres_argumentos_do_gabinete_estao_no_html_publicado():
    """A afirmação acima, conferida contra o arquivo e não contra a memória."""
    das_paginas = _data_das_paginas()
    assert "entrada" in das_paginas
    lidos = _chaves_que_os_gestos_leem()
    assert {"caminho", "entrada", "face"} <= lidos, (
        "os gestos do gabinete deixaram de ler `caminho`/`entrada`/`face`. Se "
        "isso foi de propósito, este teste tem de saber — ele existe porque "
        "esses três nomes não estavam na lista do ouvinte.")


# -- o alvo, com o dublê da casa ------------------------------------------
class PonteDeMentira:
    """O dublê da `pacotes/ponte.py`, igual ao das outras réguas desta casa.

    Ele responde a QUALQUER nome de propósito: virar uma segunda lista das
    funções da ponte a faria envelhecer em silêncio. Quem confere se o nome
    existe de verdade é `test_nenhum_gesto_chama_funcao_que_a_ponte_nao_tem`.
    """

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def __getattr__(self, nome: str):
        def registrar(*a, **k):
            self.chamadas.append(nome)
            return True
        return registrar


UNIQ_A = "aabbcc000011"
MESA = [{"pref": "p1", "uniq": UNIQ_A, "transport": "bt", "cor": "Cosmic Red"},
        {"pref": "p2", "uniq": "aabbcc000022", "transport": "usb",
         "cor": "Starlight Blue"}]
CONECTADOS = [{"uniq": UNIQ_A, "connected": True},
              {"uniq": "aabbcc000022", "connected": True}]


@pytest.fixture
def ctx():
    import pacotes

    return pacotes.Contexto(
        state={"active_profile": "regua", "controllers": CONECTADOS},
        mesa=MESA, conectados=CONECTADOS, estados={})


@pytest.mark.parametrize("nome", ["testar", "parar"])
def test_a_vibracao_recusa_sem_alvo_e_trabalha_com_ele(ctx, nome):
    """O caso que o alvo CURA — e é o único dos oito que ele cura.

    Sem controle, `testar` recusa dizendo *"sem alvo a mesa inteira treme"*, que
    é o comportamento CERTO: uma régua que engolisse isso faria a mesa dela
    inteira vibrar para provar que sabe clicar. Com o alvo, o gesto chega à
    ponte. Medido com dublê — nenhum comando saiu para o daemon dela.
    """
    import pacotes

    fn = pacotes.gesto_da_pagina("05-vibracao.html", nome)
    assert fn is not None

    sem = {"gesto": nome, "texto": "x", "valor": "", "controle": "", "uniq": ""}
    with pytest.raises(ValueError, match="não disse em qual controle"):
        fn(ctx, sem, PonteDeMentira())

    p = PonteDeMentira()
    fn(ctx, {**sem, "controle": "p1", "uniq": UNIQ_A}, p)
    assert p.chamadas, (
        f"{nome} com alvo não chamou a ponte. O alvo é a única coisa que "
        f"faltava a ele — se continua mudo, o conserto não é o alvo.")


def test_o_gabinete_nao_se_cura_com_alvo_de_controle(ctx):
    """A CORREÇÃO DE FATO: o que falta aos seis não é o controle.

    O plano do dia dizia que os seis gestos do gabinete recusavam por falta de
    alvo de CONTROLE. Medido: eles recusam com o controle passado do mesmo
    jeito, porque o que eles leem é o argumento do próprio botão. Este teste
    guarda a medição, para o diagnóstico errado não voltar.
    """
    import pacotes

    com_alvo = {"gesto": "", "texto": "x", "valor": "",
                "controle": "p1", "uniq": UNIQ_A}
    for nome, pedaco in (("escolher-aparelho", "qual aparelho"),
                         ("escolher-entrada", "qual entrada"),
                         ("tirar-daqui", "qual entrada tirar")):
        fn = pacotes.gesto_da_pagina("08-conexoes.html", nome)
        with pytest.raises(ValueError, match=pedaco):
            fn(ctx, {**com_alvo, "gesto": nome}, PonteDeMentira())


def test_o_gabinete_trabalha_quando_o_argumento_do_botao_chega(ctx):
    """E a prova do outro lado: com `caminho`, `escolher-aparelho` não recusa.

    É o que a cópia do `dataset` passa a entregar. O gesto de escolher não grava
    nada — é estado de tela — e por isso é o seguro de provar aqui.
    """
    import pacotes

    fn = pacotes.gesto_da_pagina("08-conexoes.html", "escolher-aparelho")
    fn(ctx, {"gesto": "escolher-aparelho", "texto": "x", "valor": "",
             "controle": "", "uniq": "", "caminho": "/sys/regua/hci9"},
       PonteDeMentira())
