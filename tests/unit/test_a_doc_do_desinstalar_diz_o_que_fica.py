"""A seção «Desinstalar» do `instalacao.md` diz o que o uninstall deixa, e como tirar.

OS-TEXTOS-QUE-A-6E-1-DEIXOU-VELHOS-01 (25/09/2026), item 5, achado da
conferência da O-PURGE-LEVA-AS-COPIAS-DE-PAREAMENTO-01: todo uninstall sem
`--purge-config` guarda as chaves de pareamento numa pasta carimbada de root,
e o `--purge-config` as leva, inclusive as de uninstalls anteriores. A página
não dizia nenhuma das duas coisas, e ainda dava ao `--keep-bluez` um trabalho
que ele deixou de ter em 02/08 (preservar o BlueZ virou o padrão).

A régua não digita o que confere: o prefixo da pasta sai do `uninstall.sh`,
que é quem a escreve, e cada flag que a seção cita tem de existir no laço de
argumentos dele — uma flag inventada ou renomeada na página reprova aqui.

A MORDIDA, medida: com a seção de antes (sem o parágrafo das cópias e com a
frase do `--keep-bluez`), as três reprovam; md5 conferido na devolução.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
UNINSTALL = (RAIZ / "uninstall.sh").read_text(encoding="utf-8")
INSTALACAO = (RAIZ / "docs" / "usage" / "instalacao.md").read_text(encoding="utf-8")


def _secao_desinstalar() -> str:
    inicio = INSTALACAO.index("\n## Desinstalar\n")
    fim = INSTALACAO.index("\n## ", inicio + 1)
    return INSTALACAO[inicio:fim]


def _prefixo_das_copias() -> str:
    """O nome da pasta que o uninstall ESCREVE, lido do próprio uninstall."""
    achado = re.search(
        r'_bonds_destino="/var/lib/hefesto-dualsense4unix/([\w.-]+-)\$\{', UNINSTALL
    )
    assert achado is not None, "o uninstall deixou de nomear a pasta das cópias assim"
    return achado.group(1)


def _flags_do_uninstall() -> set[str]:
    laco = UNINSTALL[UNINSTALL.index('for arg in "$@"; do') :]
    laco = laco[: laco.index("esac")]
    return set(re.findall(r"^\s+(--[a-z-]+)[|)]", laco, re.MULTILINE))


def test_a_secao_diz_onde_ficam_as_copias_de_pareamento() -> None:
    secao = _secao_desinstalar()
    prefixo = _prefixo_das_copias()
    assert prefixo in secao, (
        f"a seção «Desinstalar» não diz onde ficam as cópias de pareamento ({prefixo}…)"
    )
    assert "cópias de pareamento" in secao and "--purge-config" in secao, secao


def test_a_secao_diz_que_o_purge_leva_as_de_uninstalls_anteriores() -> None:
    assert "inclusive as de uninstalls anteriores" in _secao_desinstalar()


def test_toda_flag_que_a_secao_cita_existe_e_faz_o_que_ela_diz() -> None:
    secao = _secao_desinstalar()
    vivas = _flags_do_uninstall()
    assert "--purge-config" in vivas, "a leitura do laço de argumentos mediu o vazio"
    citadas = set(re.findall(r"`(--[a-z-]+)`", secao))
    assert citadas, secao
    assert citadas <= vivas, f"a seção cita flag que o uninstall não tem: {citadas - vivas}"
    # O no-op não pode aparecer como se preservasse algo: preservar é o padrão.
    assert "--keep-bluez" not in citadas, (
        "o `--keep-bluez` é no-op desde 02/08 (preservar o BlueZ é o padrão); "
        "quem muda algo é o `--restore-bluez`"
    )
