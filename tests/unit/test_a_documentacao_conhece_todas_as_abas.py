"""A documentação tem de conhecer TODAS as abas do notebook — CONFIG-08."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
README = RAIZ / "README.md"
ASSETS = RAIZ / "docs/usage/assets"

RETRATO = RAIZ / "src/hefesto_dualsense4unix/interface/olhar.py"

MONTA = RAIZ / "src/hefesto_dualsense4unix/interface/monta.py"

AS_DEZ = RAIZ / "docs/usage/AS-DEZ-ABAS-o-que-cada-uma-faz.md"


_DOCUMENTOS_COM_IMAGEM = (
    "README.md",
    "docs/usage/AS-DEZ-ABAS-o-que-cada-uma-faz.md",
)

_REFERENCIA = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)|<img[^>]+src=\"([^\"]+)\"")

_E_MARCADOR = ("…", "NN-", "<", ">", "{")


def _imagens_publicadas() -> list[tuple[str, str, Path]]:
    """`(documento, referência, alvo no disco)` de cada imagem que a doc publica."""
    achados: list[tuple[str, str, Path]] = []
    for nome in _DOCUMENTOS_COM_IMAGEM:
        doc = RAIZ / nome
        texto = doc.read_text(encoding="utf-8")
        for m in _REFERENCIA.finditer(texto):
            ref = m.group(1) or m.group(2)
            if not ref or not ref.lower().endswith((".png", ".jpg", ".svg", ".gif")):
                continue
            if ref.startswith(("http://", "https://")):
                continue
            if any(marca in ref for marca in _E_MARCADOR):
                continue
            achados.append((nome, ref, (doc.parent / ref).resolve()))
    return achados


def _abas_da_interface_nova() -> list[tuple[str, str]]:
    """`(rótulo, slug)` das dez, lidos de `monta.ABAS` por `ast`."""
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
    """Nenhum documento desta casa publica imagem quebrada."""
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
    """A foto da documentação recorta na MOLDURA, não no que coube na tela."""
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


def test_a_lista_das_dez_vem_do_monta_e_nao_de_uma_lista_a_mao(
    dez: list[tuple[str, str]],
) -> None:
    """A régua é conferida contra o fonte por um caminho independente."""
    assert len(dez) == 10, f"monta.ABAS tem {len(dez)} entradas, e as abas são dez: {dez}"

    bruto = MONTA.read_text(encoding="utf-8")
    trecho = bruto.split("ABAS", 1)[1]
    por_texto = re.findall(r'\("([^"]+)"\s*,\s*"(\d\d-[^"]+)"\)', trecho)
    assert dez == por_texto[: len(dez)], (
        "as duas leituras de monta.ABAS discordam — a régua não está lendo o "
        f"fonte: ast={dez} contra regex={por_texto[: len(dez)]}"
    )


def test_toda_aba_nova_tem_secao_na_pagina_das_dez(dez: list[tuple[str, str]]) -> None:
    """Cada uma das dez tem um `## N. <rótulo>` em `AS-DEZ-ABAS`."""
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
    """A foto de cada aba nova existe no disco e aparece nos dois documentos."""
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
