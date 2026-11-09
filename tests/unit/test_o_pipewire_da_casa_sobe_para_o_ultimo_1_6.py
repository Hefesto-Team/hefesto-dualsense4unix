"""O PipeWire da casa sobe para a última 1.6 publicada, com o WirePlumber junto.

O-PIPEWIRE-DA-CASA-SOBE-PARA-O-ULTIMO-1-6-01 (09/11/2026). O ``BASELINE`` diz a versão, a tag e
o hash juntos, e o hash é o medido para aquela versão (dois downloads iguais do arquivo da tag
no GitLab, em 09/11/2026). A revisão fica acima da 1.6.9 que a casa tinha instalada, e o
``_pw_veredito`` do install a pede.

AS MORDIDAS (feitas na sprint, com a cura devolvida): o hash da 1.6.9 com a versão 1.6.11
reprova o caso do hash; o ``PW_REVISAO`` de volta à 1.6.9 reprova o «precisa» da máquina de
hoje; o rótulo do 3f-bis escrito à mão reprova o caso do rótulo.
"""
from __future__ import annotations

import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
BASELINE = RAIZ / "assets" / "pipewire-backport" / "BASELINE"
INSTALL = (RAIZ / "install.sh").read_text(encoding="utf-8")
BASH = shutil.which("bash") or "/bin/bash"

MEDIDOS_POR_VERSAO = {
    ("PW", "1.6.9"): ("8fa27cabdc6c0c1350c69c026af5850ef0af1e26",
                      "0cde58c124825bad462b32ab79f9aa286ee7b113cc73a5cda923a4365e752657"),
    ("PW", "1.6.11"): ("4287f31510771fc999f8a58a024c81ca10b8d55f",
                       "0b32fbbece4591376b45dde5a818bfa5b3517e70913a2f7414e33c47c20b07ee"),
    ("WP", "0.5.18"): ("81606cbb32d29df20147d1b68b662c1082654d81",
                       "0c2ea30a7b3bb4ecad456bb27e2c283defda59bb53d97df6917a495f12887e33"),
    ("WP", "0.5.19"): ("4ab992fa2931ae2b17ef73508b1370030b7878c3",
                       "e743070200e3788b8a46b5cd35438170dea4458302cfa3bb04ab4a9495ad14a4"),
}
INSTALADA_EM_0911 = {"PW": "1.6.9-0~hefesto24.04.1", "WP": "0.5.18-0~hefesto24.04.1"}


def _baseline() -> dict[str, str]:
    valores = {}
    for linha in BASELINE.read_text(encoding="utf-8").splitlines():
        if linha and not linha.startswith("#") and "=" in linha:
            chave, valor = linha.split("=", 1)
            valores[chave] = valor
    return valores


def _ordem(versao: str) -> tuple[int, ...]:
    return tuple(int(x) for x in versao.split("."))


@pytest.mark.parametrize("prefixo", ["PW", "WP"])
def test_versao_tag_e_hash_andam_juntos(prefixo: str) -> None:
    v = _baseline()
    versao = v[f"{prefixo}_VERSAO_UPSTREAM"]
    assert (prefixo, versao) in MEDIDOS_POR_VERSAO, f"{versao} sem medida na tabela"
    tag, sha = MEDIDOS_POR_VERSAO[(prefixo, versao)]
    assert v[f"{prefixo}_TAG_COMMIT"] == tag
    assert v[f"{prefixo}_FONTE_SHA256"] == sha
    assert f"/{versao}/" in v[f"{prefixo}_FONTE_URL"]
    assert v[f"{prefixo}_REVISAO"] == f"{versao}-0~hefesto24.04.1"


def test_a_versao_e_a_ultima_1_6_de_09_11() -> None:
    v = _baseline()
    assert _ordem(v["PW_VERSAO_UPSTREAM"]) >= (1, 6, 11)
    assert _ordem(v["PW_VERSAO_UPSTREAM"])[:2] == (1, 6)
    assert _ordem(v["WP_VERSAO_UPSTREAM"]) >= (0, 5, 19)


def _exe(pasta: Path, nome: str, corpo: str) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / nome
    alvo.write_text("#!/bin/bash\n" + corpo, encoding="utf-8")
    alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC)


def _funcao(nome: str) -> str:
    inicio = INSTALL.index(f"{nome}() {{\n")
    return INSTALL[inicio:INSTALL.index("\n}\n", inicio) + 3]


@pytest.mark.skipif(shutil.which("dpkg") is None, reason="sem dpkg para comparar versões")
def test_a_maquina_de_hoje_pede_a_revisao_nova(tmp_path: Path) -> None:
    """Prova da D-0911-O-PIPEWIRE-DA-CASA-SOBE-PARA-O-ULTIMO-1-6: a 1.6.9 de hoje fica abaixo."""
    v = _baseline()
    falsos = tmp_path / "falsos"
    _exe(falsos, "dpkg-query",
         'case "$*" in\n'
         f'  *libpipewire-0.3-modules*) printf "ii |{INSTALADA_EM_0911["PW"]}\\n" ;;\n'
         f'  *wireplumber*) printf "ii |{INSTALADA_EM_0911["WP"]}\\n" ;;\n'
         "esac\n")
    script = _funcao("_pw_versao_ii") + _funcao("_pw_veredito") + (
        f'_pw_veredito "{v["PW_REVISAO"]}" "{v["WP_REVISAO"]}"\n')
    feito = subprocess.run([BASH, "-c", script], capture_output=True, text=True, timeout=30,
                           env={"PATH": f"{falsos}:/usr/bin:/bin", "LC_ALL": "C"})
    assert feito.stdout.strip() == "precisa", feito.stdout + feito.stderr


def test_o_rotulo_do_3f_bis_le_o_baseline() -> None:
    linha = next(x for x in INSTALL.splitlines() if 'step "3f-bis"' in x)
    feito = subprocess.run(
        [BASH, "-c", "step() { printf '%s\\n' \"$2\"; }\n" + linha.strip() + "\n"],
        capture_output=True, text=True, timeout=30, env={"ROOT_DIR": str(RAIZ),
                                                         "PATH": "/usr/bin:/bin"})
    v = _baseline()
    assert f"{v['PW_VERSAO_UPSTREAM']} com o WirePlumber {v['WP_VERSAO_UPSTREAM']}" in feito.stdout
    assert not re.search(r"\b1\.6\.9\b", linha)


@pytest.mark.parametrize(("prefixo", "nome"), [("PW", "pipewire"), ("WP", "wireplumber")])
def test_o_changelog_abre_na_revisao_nova_com_a_tag(prefixo: str, nome: str) -> None:
    v = _baseline()
    texto = (RAIZ / "assets" / "pipewire-backport" / "debian"
             / f"changelog.{nome}.hefesto").read_text(encoding="utf-8")
    entrada = texto.split("\n -- ", 1)[0]
    assert entrada.startswith(f"{nome} ({v[f'{prefixo}_REVISAO']}) noble;")
    assert f"Upstream: {v[f'{prefixo}_VERSAO_UPSTREAM']} {v[f'{prefixo}_TAG_COMMIT']}" in entrada
