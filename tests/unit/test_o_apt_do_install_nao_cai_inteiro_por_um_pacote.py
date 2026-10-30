"""O apt do install não cai inteiro por um pacote que falta.

O-APT-DO-INSTALL-NAO-CAI-INTEIRO-POR-UM-PACOTE-01.

Num kernel sem o pacote de cabeçalhos no repositório (kernel próprio, contêiner), o pedido único
`dkms build-essential linux-headers-$(uname -r)` caía inteiro. O `apt-get` e o `sudo` aqui são de
mentira, no `PATH` de um `tmp_path`.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from tests.unit.test_install_garante_deps_em_qualquer_familia import (
    INSTALL,
    _extrai_funcao,
)
from tests.unit.test_o_install_nao_tropeca_no_pacote_quebrado import PRELUDO, _roda

PRELUDO_DKMS = "\n".join([PRELUDO, _extrai_funcao("_pedir_o_que_o_dkms_compila")])


def _apt_que_recusa_os_cabecalhos(tmp_path: Path) -> dict[str, str]:
    binario = tmp_path / "bin"
    binario.mkdir()
    for nome, corpo in (
        ("sudo", 'exec "$@"\n'),
        ("dpkg-query", "printf 'ii  bash\\n'\n"),
        ("apt-get", 'printf "%s\\n" "$*" >> "${LOG_PKG}"\n'
                    'case " $* " in *" linux-headers-"*) exit 100 ;; esac\n'),
    ):
        alvo = binario / nome
        alvo.write_text("#!/usr/bin/env bash\n" + corpo, encoding="utf-8")
        alvo.chmod(0o755)
    return {"HEFESTO_FAMILIA_PACOTES": "apt", "LOG_PKG": str(tmp_path / "pkg.log"),
            "PATH": f"{binario}:{os.environ['PATH']}"}


def test_sem_os_cabecalhos_o_dkms_e_o_compilador_entram(tmp_path: Path) -> None:
    """Mordida: com o pedido único de volta, o apt recusa tudo e o dkms não entra."""
    env = _apt_que_recusa_os_cabecalhos(tmp_path)
    proc = _roda("_pedir_o_que_o_dkms_compila dkms compilador kernel-headers || echo RC=$?",
                 preludo=PRELUDO_DKMS, env=env)
    pedidos = (tmp_path / "pkg.log").read_text(encoding="utf-8").splitlines()

    assert len(pedidos) == 2, pedidos
    assert pedidos[0].endswith(" dkms build-essential"), pedidos
    assert re.search(r" linux-headers-\S+$", pedidos[1]), pedidos
    assert "RC=" in proc.stdout, proc.stdout + proc.stderr
    saida = proc.stdout
    assert "cabeçalhos do kernel" in saida and "O dkms e o compilador ficam instalados" in saida
    assert "microfone do DualSense pelo rádio fica desligado" in saida
    assert "sudo apt install linux-headers-" in saida
    assert "pronto para compilar" not in saida


def test_com_tudo_no_repositorio_os_dois_pedidos_passam(tmp_path: Path) -> None:
    env = _apt_que_recusa_os_cabecalhos(tmp_path)
    proc = _roda("_pedir_o_que_o_dkms_compila dkms compilador", preludo=PRELUDO_DKMS, env=env)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "pronto para compilar os módulos" in proc.stdout


def test_o_passo_do_dkms_pede_pela_funcao_e_nao_numa_linha_so() -> None:
    trecho = INSTALL[INSTALL.index('_dkms_faltando=()'):INSTALL.index('unset _dkms_faltando')]
    assert '_pedir_o_que_o_dkms_compila "${_dkms_faltando[@]}"' in trecho
    assert 'run_pkg "${_dkms_faltando[@]}"' not in trecho
