"""O repositório pesa só o que serve (O-REPOSITORIO-PESA-SO-O-QUE-SERVE-01, 21/10/2026).

Medido em 21/10/2026: o versionado somava 118 MB, e `docs/research/` levava 40,5 MB, dois deles em
duas fotos da página inteira (5,7 e 5,0 MB) que nenhum documento citava. A cura saiu da árvore
(a história só encolhe na reescrita do degrau 10): as fotos foram recomprimidas SEM perda
(`optipng`, pixel a pixel iguais), as duas páginas inteiras sem citação saíram, e
`mockup/variantes/` esvaziou, porque toda variante que havia já foi escolhida e a escolha está no
CSV de decisões.

A régua mede os arquivos VERSIONADOS (`git ls-files`) e reprova:

* o arquivo acima do teto (`TETO_BYTES`; `TETO_DE_IMAGEM` para imagem) que não esteja em `GRANDES`,
  cada um com o motivo;
* a entrada de `GRANDES` que já cabe no teto (a lista só encolhe);
* o arquivo em `mockup/variantes/` que não esteja em `ESPERAM_A_ESCOLHA` (o desenho escolhido mora
  em `mockup/`; só a variante que ainda espera a escolha do usuário fica).

MORDIDAS (executadas em 21/10/2026, em série, e devolvidas; o md5 do teste bateu):

* a página inteira de 5,7 MB de volta ao git reprova `test_nada_versionado_passa_do_teto`;
* uma variante em `mockup/variantes/` reprova `test_a_variante_escolhida_nao_fica_no_repositorio`;
* uma entrada de `GRANDES` que cabe no teto reprova `test_a_lista_de_grandes_so_encolhe`;
* um PNG de teste acima do teto reprova `test_a_regua_morde_o_png_acima_do_teto` (sobre `tmp_path`).
"""
from __future__ import annotations

import subprocess
from pathlib import Path, PurePosixPath

RAIZ = Path(__file__).resolve().parents[2]

#: o teto de qualquer arquivo versionado. Medido em 21/10/2026: o maior fora de `GRANDES` tem
#: 858 KB; passar de 1 MB é dado ou imagem que pede decisão, não acidente.
TETO_BYTES = 1_000_000
#: o teto de imagem. Medido: a maior fotografia versionada tem 229 KB depois da recompressão.
TETO_DE_IMAGEM = 400_000
IMAGENS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"})

# arquivo (relativo à raiz) -> por que ele passa do teto e fica. Só dado gerado ou lastro citado.
GRANDES: dict[str, str] = {
    "docs/specs.html": "gerado do mapa-controles.csv; é a página que o mapa publica",
    "docs/data/mapa-controles.csv": "o mapa de canais; é portão (check_paridade_transporte)",
    "docs/data/decisoes-de-produto.csv": "o registro das decisões; uma linha por decisão",
    "docs/data/ensaios-brutos/2026-08-15-PAREADO-hci-decodificado.txt":
        "a captura do btmon em texto que o estudo PAREADO cita por «Handle» e por pacote",
}

# variante de desenho que ainda ESPERA a escolha do usuário (nome do arquivo -> o que ela decide).
# Vazia de propósito: em 21/10/2026 toda variante tinha escolha gravada e saiu.
ESPERAM_A_ESCOLHA: dict[str, str] = {}


def _versionados(raiz: Path = RAIZ) -> list[str]:
    saida = subprocess.run(
        ["git", "ls-files", "-z"], cwd=raiz, check=True, capture_output=True
    ).stdout
    return [c for c in saida.decode().split("\0") if c]


def _teto(caminho: str) -> int:
    ext = PurePosixPath(caminho).suffix.lower()
    return TETO_DE_IMAGEM if ext in IMAGENS else TETO_BYTES


def acima_do_teto(raiz: Path, arquivos: list[str]) -> list[str]:
    """Os arquivos que passam do teto e não estão em `GRANDES`, com o tamanho e o teto."""
    achados = []
    for caminho in arquivos:
        arquivo = raiz / caminho
        if caminho in GRANDES or not arquivo.is_file():
            continue
        tamanho = arquivo.stat().st_size
        if tamanho > _teto(caminho):
            achados.append(f"{caminho}: {tamanho} B, teto {_teto(caminho)} B")
    return achados


def variantes_paradas(arquivos: list[str]) -> list[str]:
    """Os arquivos de `mockup/variantes/` que não esperam a escolha do usuário."""
    return [
        c for c in arquivos
        if c.startswith("mockup/variantes/") and PurePosixPath(c).name not in ESPERAM_A_ESCOLHA
    ]


def test_nada_versionado_passa_do_teto() -> None:
    # D-2110-O-REPOSITORIO-PESA-SO-O-QUE-SERVE
    achados = acima_do_teto(RAIZ, _versionados())
    assert not achados, (
        "arquivo versionado acima do teto: comprima sem perda (optipng), corte no que o documento "
        "cita, ou declare em GRANDES com o motivo:\n" + "\n".join(achados)
    )


def test_a_lista_de_grandes_so_encolhe() -> None:
    versionados = set(_versionados())
    for caminho in GRANDES:
        assert caminho in versionados, f"{caminho} saiu do git: tire da lista"
        tamanho = (RAIZ / caminho).stat().st_size
        assert tamanho > _teto(caminho), f"{caminho} cabe no teto ({tamanho} B): tire da lista"


def test_a_variante_escolhida_nao_fica_no_repositorio() -> None:
    sobra = variantes_paradas(_versionados())
    assert not sobra, (
        "o desenho escolhido mora em mockup/ e a escolha no CSV; só a variante que espera a "
        "escolha dela fica, declarada em ESPERAM_A_ESCOLHA:\n" + "\n".join(sobra)
    )


def test_a_regua_morde_o_png_acima_do_teto(tmp_path: Path) -> None:
    pequeno = tmp_path / "pequeno.png"
    grande = tmp_path / "grande.png"
    pequeno.write_bytes(b"\0" * (TETO_DE_IMAGEM - 1))
    grande.write_bytes(b"\0" * (TETO_DE_IMAGEM + 1))
    assert acima_do_teto(tmp_path, ["pequeno.png"]) == []
    achado = acima_do_teto(tmp_path, ["grande.png"])
    assert len(achado) == 1 and achado[0].startswith("grande.png")


def test_o_teto_de_texto_e_mais_largo_que_o_de_imagem(tmp_path: Path) -> None:
    meio = tmp_path / "dados.csv"
    meio.write_bytes(b"x" * (TETO_DE_IMAGEM + 1))
    assert acima_do_teto(tmp_path, ["dados.csv"]) == []
    meio.write_bytes(b"x" * (TETO_BYTES + 1))
    assert len(acima_do_teto(tmp_path, ["dados.csv"])) == 1


def test_a_grande_declarada_nao_reprova(tmp_path: Path) -> None:
    caminho = next(iter(GRANDES))
    alvo = tmp_path / caminho
    alvo.parent.mkdir(parents=True)
    alvo.write_bytes(b"x" * (TETO_BYTES + 1))
    assert acima_do_teto(tmp_path, [caminho]) == []


def test_a_regua_morde_a_variante_que_sobra() -> None:
    assert variantes_paradas(["mockup/variantes/2110-extensoes-A-duas-colunas.html"])
    assert not variantes_paradas(["mockup/05-vibracao.html"])
