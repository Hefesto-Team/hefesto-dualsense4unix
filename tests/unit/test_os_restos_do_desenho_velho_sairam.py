#!/usr/bin/env python3
"""Os restos do desenho velho saem das abas 03, 05 e 08.

Sprint: OS-RESTOS-DO-DESENHO-VELHO-SAEM-DAS-ABAS-03-05-08-01.

Medido em 23/10/2026: a cena de exemplo dos geradores levava o nome da dona da bancada
(`monta.MESA`, `"dono"`, e o `DONO_DA_CENA` da 08), e o HTML publicado, a primeira pintura e o
campo sem dono o mostravam a qualquer usuário; a cena do rádio da 08 lia do desenho congelado
(`mockup/mapa-do-radio.html`) quatro nomes de pessoa. A 03 importava o glifo da 05, e a `LEGENDA`
da 08 era código morto.

As réguas leem o fonte e o desenho (o que o `--publicar` copia), nunca o que um gerador devolveu.

MORDIDAS (24/10/2026): devolver o `"dono": "Vitória"` à `monta.MESA`; devolver o
`from aba05 import GLIFO_DO_CONTROLE` à 03; devolver a `LEGENDA` à 08; devolver o
`"nome": linha["nome"]` ao controle da cena do rádio. Cada uma reprova uma régua daqui.
"""
from __future__ import annotations

import ast
import io
import pathlib
import re
import tokenize

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src/hefesto_dualsense4unix/interface"
DESENHOS_COM_A_CENA = ("04-iluminacao.html", "05-vibracao.html", "08-conexoes.html")
NOME_DA_CENA_VELHA = "Vitória"


def _fonte(nome: str) -> str:
    return (INTERFACE / nome).read_text(encoding="utf-8")


def _textos_do_codigo(fonte: str) -> list[str]:
    """As constantes de texto do módulo, fora de comentário e de docstring."""
    arvore = ast.parse(fonte)
    docstrings = set()
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            primeiro = no.body[0] if no.body else None
            if isinstance(primeiro, ast.Expr) and isinstance(primeiro.value, ast.Constant):
                docstrings.add(id(primeiro.value))
    return [no.value for no in ast.walk(arvore)
            if isinstance(no, ast.Constant) and isinstance(no.value, str)
            and id(no) not in docstrings]


def _sem_comentarios_de_html(doc: str) -> str:
    return re.sub(r"/\*.*?\*/", "", re.sub(r"<!--.*?-->", "", doc, flags=re.S), flags=re.S)


def _desenho(nome: str) -> str:
    return (RAIZ / "mockup" / nome).read_text(encoding="utf-8")


def test_o_codigo_da_cena_nao_tem_nome_de_pessoa() -> None:
    for modulo in ("monta.py", "aba08.py"):
        fonte = _fonte(modulo)
        achados = [t for t in _textos_do_codigo(fonte) if NOME_DA_CENA_VELHA in t]
        assert not achados, f"{modulo} publica um nome de pessoa: {achados[:3]}"
        # os comentários ficam de fora; o resto do código também não o diz
        sem_comentarios = "".join(
            tok.string for tok in tokenize.generate_tokens(io.StringIO(fonte).readline)
            if tok.type != tokenize.COMMENT and tok.type != tokenize.STRING)
        assert NOME_DA_CENA_VELHA not in sem_comentarios, modulo


def test_a_cena_do_gerador_nao_tem_dono() -> None:
    import sys

    sys.path.insert(0, str(INTERFACE))
    sys.path.insert(0, str(RAIZ / "src"))
    from hefesto_dualsense4unix.interface import monta

    com_dono = [c["pref"] for c in monta.MESA if c.get("dono")]
    assert com_dono == [], f"a cena dá nome de quem joga a {com_dono}: a tela mostraria esse nome"


def test_os_desenhos_da_04_da_05_e_da_08_nao_tem_nome_de_pessoa() -> None:
    for nome in DESENHOS_COM_A_CENA:
        doc = _sem_comentarios_de_html(_desenho(nome))
        assert doc.count(NOME_DA_CENA_VELHA) == 0, f"{nome}: {doc.count(NOME_DA_CENA_VELHA)}"


def test_a_cena_do_radio_da_08_nao_le_os_nomes_do_desenho_congelado() -> None:
    """O desenho congelado tem um nome por controle; nenhum deles chega à 08."""
    radio = _desenho("mapa-do-radio.html")
    csv = re.search(r'<script type="text/csv" id="dados">(.*?)</script>', radio, re.S)
    assert csv, "o desenho do rádio perdeu a tabela `dados`"
    nomes = [linha.split(",")[2].strip() for linha in csv.group(1).splitlines()
             if linha.startswith("aparelho,") and ",controle," in linha]
    assert len(nomes) == 4, nomes
    doc = _sem_comentarios_de_html(_desenho("08-conexoes.html"))
    vazados = {n: len(re.findall(rf"\b{re.escape(n)}\b", doc)) for n in nomes}
    assert not any(vazados.values()), f"os nomes do desenho congelado chegaram à 08: {vazados}"
    # o campo do nome de quem joga nasce vazio, e a tela diz o número
    campos = re.findall(r'<input class="gc-dono"[^>]*>', doc)
    assert campos and all('value=""' in c for c in campos), campos[:1]


def test_a_03_nao_importa_o_desenho_da_05() -> None:
    arvore = ast.parse(_fonte("aba03.py"))
    de_fora = [ast.unparse(no) for no in ast.walk(arvore)
               if (isinstance(no, ast.ImportFrom) and (no.module or "").split(".")[-1] == "aba05")
               or (isinstance(no, ast.Import) and any(a.name.split(".")[-1] == "aba05"
                                                      for a in no.names))]
    assert de_fora == [], f"a 03 importa o desenho da 05: {de_fora}"


def test_o_glifo_do_controle_tem_um_dono_comum() -> None:
    """A 03 e a 05 o tiram de `mapa.glifo_do_controle`, pelo caminho do pacote; nenhuma o refaz.

    Mora com a silhueta, no `mapa.py`, que está fora do produto: no `monta.py`, que o pacote
    importa, ele abria ao produto um caminho até o gerador do mapa
    (`test_o_codigo_de_src_tem_quem_o_chame`)."""
    for modulo in ("aba03.py", "aba05.py"):
        fonte = _fonte(modulo)
        assert ("from hefesto_dualsense4unix.interface.mapa import glifo_do_controle"
                in fonte), f"{modulo} não importa o glifo do dono comum"
        assert "silhueta_do_dualsense(22" not in fonte, f"{modulo} refaz o glifo do controle"


def test_a_08_nao_define_a_legenda() -> None:
    arvore = ast.parse(_fonte("aba08.py"))
    nomes = {alvo.id for no in arvore.body if isinstance(no, ast.Assign)
             for alvo in no.targets if isinstance(alvo, ast.Name)}
    assert "LEGENDA" not in nomes, "a LEGENDA da 08 voltou, e nada a lê"
