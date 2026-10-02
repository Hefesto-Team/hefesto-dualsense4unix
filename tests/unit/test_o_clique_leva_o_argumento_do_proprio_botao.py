#!/usr/bin/env python3
"""O clique tem de levar ao Python o que o BOTÃO diz — não uma lista de nomes."""
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
    """Os `data-*` que as dez páginas publicadas trazem, em nome camelCase."""
    fora: set[str] = set()
    for arq in sorted(PAGINAS.glob("[01][0-9]-*.html")):
        for cru in re.findall(r'\bdata-([a-z][a-z0-9-]*)=', arq.read_text(encoding="utf-8")):
            partes = cru.split("-")
            fora.add(partes[0] + "".join(p.capitalize() for p in partes[1:]))
    return fora


def test_o_bootstrap_copia_o_dataset_inteiro():
    """A cura, e a mordida mora aqui: sem a cópia, estes atributos somem."""
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


class PonteDeMentira:
    """O dublê da `pacotes/ponte.py`, igual ao das outras réguas desta casa."""

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

    **A RECUSA PASSOU DE `ValueError` A `RuntimeError` — 04/09/2026**, e o tipo
    é o contrato: `hefesto_vivo._recusou_dizendo` leva `RuntimeError` ao CARTÃO
    daquele controle e deixa `ValueError` no `stderr` de quem lançou a janela.
    A frase estava certa desde 02/09 e **nunca chegou aos olhos dela** — clicar
    "Testar" numa coluna sem controle não fazia nada e não explicava nada, que é
    a queixa *"vibração nem funciona"* na forma mais barata de produzir.

    A MORDIDA: devolva o `raise ValueError` a `a05_vibracao._mirar` — este caso
    reprova, porque `RuntimeError` deixa de ser levantado.
    """
    import pacotes

    fn = pacotes.gesto_da_pagina("05-vibracao.html", nome)
    assert fn is not None

    sem = {"gesto": nome, "texto": "x", "valor": "", "controle": "", "uniq": ""}
    with pytest.raises(RuntimeError, match="dentro da coluna"):
        fn(ctx, sem, PonteDeMentira())

    p = PonteDeMentira()
    fn(ctx, {**sem, "controle": "p1", "uniq": UNIQ_A}, p)
    assert p.chamadas, (
        f"{nome} com alvo não chamou a ponte. O alvo é a única coisa que "
        f"faltava a ele — se continua mudo, o conserto não é o alvo.")


def test_o_gabinete_nao_se_cura_com_alvo_de_controle(ctx):
    """A CORREÇÃO DE FATO: o que falta aos seis não é o controle."""
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
    """E a prova do outro lado: com `caminho`, `escolher-aparelho` não recusa."""
    import pacotes

    fn = pacotes.gesto_da_pagina("08-conexoes.html", "escolher-aparelho")
    fn(ctx, {"gesto": "escolher-aparelho", "texto": "x", "valor": "",
             "controle": "", "uniq": "", "caminho": "/sys/regua/hci9"},
       PonteDeMentira())
