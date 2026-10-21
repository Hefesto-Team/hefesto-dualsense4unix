"""O-PROCEDIMENTO-DO-HID-NINTENDO-NAO-CONHECE-A-PASTA-DE-NINGUEM-01 (20/10/2026).

O que chega a quem usa (o produto, os scripts, o install e as páginas de uso e de
protocolo) não traz caminho da bancada: um `cd` para uma pasta que só existe num
computador quebra o procedimento em todos os outros. Os registros de medida
(`docs/process`, `docs/research`, `docs/data`) e os testes ficam fora: lá o caminho
é história.

A MORDIDA: devolva `cd ~/Desenvolvimento/hefesto-dualsense4unix` ao
`assets/dkms/hid-nintendo/README.md` e o caso reprova, com o arquivo e a linha.
"""
from __future__ import annotations

import os
import pathlib
import pwd
import re
import subprocess

RAIZ = pathlib.Path(__file__).resolve().parents[2]

O_QUE_VAI_A_QUEM_USA = (
    "README.md", "docs/usage", "docs/protocol", "docs/method", "assets", "packaging",
    "src", "scripts", "install.sh", "uninstall.sh",
)

#: O HOME de quem roda (pela tabela de usuários) e as pastas da bancada, montados sem o caminho
#: literal, que a régua `test_nenhum_caminho_desta_maquina_no_codigo` proíbe em `tests/`. O ponto
#: de montagem seguido de reticências é citação de medida, não caminho: só a barra conta.
CAMINHO_DA_BANCADA = re.compile("|".join([
    re.escape(f"/home/{pwd.getpwuid(os.getuid()).pw_name}") + r"\b",
    re.escape("~/Desenvolvimento/"),
    re.escape("/mnt/" + "Apate/"),
]))


def _versionados() -> list[pathlib.Path]:
    saida = subprocess.run(
        ["git", "ls-files", "-z", "--", *O_QUE_VAI_A_QUEM_USA],
        cwd=RAIZ, check=True, capture_output=True,
    ).stdout.decode("utf-8")
    return [RAIZ / nome for nome in saida.split("\0") if nome]


def test_nada_que_vai_a_quem_usa_aponta_a_pasta_da_bancada() -> None:
    achados: list[str] = []
    arquivos = _versionados()
    assert len(arquivos) > 100, "a lista do git veio curta: a régua não está olhando a árvore"
    for arquivo in arquivos:
        try:
            texto = arquivo.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        for numero, linha in enumerate(texto.splitlines(), 1):
            if CAMINHO_DA_BANCADA.search(linha):
                achados.append(f"{arquivo.relative_to(RAIZ)}:{numero}: {linha.strip()[:120]}")
    assert not achados, "caminho da bancada no que vai a quem usa:\n" + "\n".join(achados)
