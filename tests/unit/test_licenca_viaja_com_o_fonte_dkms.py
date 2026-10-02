"""LICENÇA-QUE-VIAJA-01 — o texto da licença acompanha o fonte GPL que a"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

BASH = shutil.which("bash") or "/bin/bash"
REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_PATH = REPO_ROOT / "scripts" / "dkms_lib.sh"
LICENSES = REPO_ROOT / "LICENSES"


def _stub(diretorio: Path, nome: str, corpo: str) -> None:
    caminho = diretorio / nome
    caminho.write_text(f"#!/bin/sh\n{corpo}\n", encoding="utf-8")
    caminho.chmod(0o755)


def _cena(tmp_path: Path) -> dict[str, Path | str]:
    """Ambiente real da lib SEM root: raízes em `tmp` (a costura"""
    stubs = tmp_path / "bin"
    stubs.mkdir(exist_ok=True)
    log = tmp_path / "calls.log"
    estado = tmp_path / "estado"
    estado.mkdir(exist_ok=True)
    src_root = tmp_path / "usr-src"
    src_root.mkdir(exist_ok=True)
    kver = "0.0.0-hefesto-licenca"
    (tmp_path / "modules" / kver / "build").mkdir(parents=True, exist_ok=True)
    assets = tmp_path / "assets-dkms"
    (assets / "patch").mkdir(parents=True, exist_ok=True)
    (assets / "dkms.conf").write_text(
        'PACKAGE_NAME="hefesto-teste"\nPACKAGE_VERSION="9.9.9"\n', encoding="utf-8"
    )
    (assets / "mod-teste.c").write_text(
        "// SPDX-License-Identifier: GPL-2.0-or-later\n", encoding="utf-8"
    )
    (assets / "patch" / "0001-ref.patch").write_text("referência\n", encoding="utf-8")
    _stub(stubs, "uname", f'echo "{kver}"')
    _stub(stubs, "sudo", f'echo "sudo $@" >> "{log}"\nexec "$@"')
    _stub(stubs, "modinfo", 'echo "/lib/modules/x/updates/dkms/mod-teste.ko"')
    _stub(
        stubs,
        "dkms",
        f'echo "dkms $@" >> "{log}"\n'
        'case "$1" in\n'
        "  status)\n"
        f'    [ -f "{estado}/added" ] || exit 0\n'
        f'    if [ -f "{estado}/installed" ]; then echo "hefesto-teste/9.9.9: installed"\n'
        f'    elif [ -f "{estado}/built" ]; then echo "hefesto-teste/9.9.9: built"\n'
        '    else echo "hefesto-teste/9.9.9: added"; fi ;;\n'
        f'  add) touch "{estado}/added" ;;\n'
        f'  build) touch "{estado}/built" ;;\n'
        f'  install) touch "{estado}/installed" ;;\n'
        f'  remove) rm -f "{estado}/added" "{estado}/built" "{estado}/installed" ;;\n'
        "esac\nexit 0",
    )
    return {
        "path": f"{stubs}:/usr/bin:/bin",
        "log": log,
        "src_root": src_root,
        "assets": assets,
    }


MARCA = "---SEGUNDA-CHAMADA---"


def _roda(tmp_path: Path, chamadas: int) -> tuple[str, str, Path]:
    cena = _cena(tmp_path)
    chamada = (
        f"dkms_install_patched_module hefesto-teste 9.9.9 {cena['assets']} mod-teste\n"
        'printf "RC=%s\\n" "$?"\n'
    )
    corpo = chamada
    for _ in range(chamadas - 1):
        corpo += f"printf '%s\\n' '{MARCA}' >> '{cena['log']}'\n{chamada}"
    env = dict(os.environ)
    env["PATH"] = str(cena["path"])
    env["HEFESTO_DKMS_SRC_ROOT"] = str(cena["src_root"])
    env["HEFESTO_DKMS_MODULES_ROOT"] = str(tmp_path / "modules")
    env["HEFESTO_EFIVARS_ROOT"] = "/nao-existe/efivars-sem-secure-boot"
    resultado = subprocess.run(
        [BASH, "-c", f"source '{LIB_PATH}'\n{corpo}"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    log = Path(str(cena["log"]))
    return (
        resultado.stdout + resultado.stderr,
        log.read_text(encoding="utf-8") if log.exists() else "",
        Path(str(cena["src_root"])) / "hefesto-teste-9.9.9",
    )


def test_o_repositorio_tem_o_que_copiar() -> None:
    """Controle do teste: sem `LICENSES/` os dois abaixo passariam por"""
    assert (LICENSES / "GPL-2.0.txt").is_file(), (
        "LICENSES/GPL-2.0.txt sumiu — o teste desta entrega vira carimbo "
        "(quem cobra a existência do texto é test_cr05_licencas_de_terceiros_viajam)"
    )


def test_licenca_chega_ao_usr_src_na_execucao(tmp_path: Path) -> None:
    """Cura arrancada: apagar o bloco `1-bis` do `dkms_install_patched_module`"""
    saida, _registro, destino = _roda(tmp_path, chamadas=1)
    assert "RC=0" in saida, saida
    assert (destino / "mod-teste.c").is_file(), (
        f"o fonte nem chegou a {destino} — a cena do teste quebrou antes da entrega"
    )
    gpl = destino / "LICENSES" / "GPL-2.0.txt"
    assert gpl.is_file(), (
        f"o fonte GPL-2.0 foi posto em {destino} sem a cópia da licença ao lado. "
        "A GPL-2.0, seção 1, pede que o texto acompanhe o programa, e é o que os "
        "cinco alvos de empacotamento já fazem desde a CR-05."
    )
    assert gpl.read_text(encoding="utf-8") == (LICENSES / "GPL-2.0.txt").read_text(
        encoding="utf-8"
    ), "a licença chegou ao destino MODIFICADA — texto de licença não se edita"


def test_a_licenca_no_destino_nao_quebra_o_no_op_da_segunda_chamada(
    tmp_path: Path,
) -> None:
    """A armadilha da entrega, e ela é maior que a entrega."""
    saida, registro, _destino = _roda(tmp_path, chamadas=2)
    assert saida.count("RC=0") == 2, saida
    assert "já sincronizado" in saida, (
        "a segunda chamada não reconheceu o source como sincronizado — a cópia "
        "da licença quebrou a idempotência do passo 1 (falta `-x LICENSES` no diff)"
    )
    assert MARCA in registro, "a cena do teste não separou as duas chamadas"
    segunda = registro.split(MARCA, 1)[1]
    assert segunda.count("sudo cp -a") == 0, (
        "a segunda chamada recopiou a licença. O contrato desta biblioteca é "
        "que a reexecução não repita passo nenhum — e é `sudo cp -a` que "
        "test_dkms_lib.py::test_segunda_chamada_e_no_op_real conta para provar."
    )
    assert segunda.count("sudo dkms remove") == 0, (
        "a segunda chamada desregistrou o módulo para recopiar: o `diff -rq` "
        "passou a achar diferença por causa do LICENSES/ que só existe no "
        "destino. Cada install passaria a reconstruir os três módulos DKMS."
    )


def test_a_biblioteca_exclui_licenses_da_comparacao_de_sincronia() -> None:
    """Morde só TEXTO, e está declarado como tal — existe para a armadilha"""
    lib = LIB_PATH.read_text(encoding="utf-8")
    assert "-x patch -x LICENSES" in lib, (
        "o diff de sincronia do dkms_lib.sh precisa excluir LICENSES junto com "
        "patch — os dois existem em um lado só da comparação"
    )
