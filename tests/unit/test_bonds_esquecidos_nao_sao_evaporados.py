"""CACHE NÃO É BOND — o doctor reprovava a máquina sem controle pareado.

MEDIDO em 30/09/2026, nesta máquina. Às 01h13 ela removeu três controles pelo
sistema; o install das 01h16 terminou com

    [FAIL] ZERO bonds em disco com cache de 159 devices — pareamentos vivendo
    só em memória (...) se houver snapshot: sudo .../bt_bonds_restore.sh --list

e a receita era restaurar o snapshot: desfazer o que ela tinha feito de
propósito. O cache guarda o nome de todo aparelho visto numa busca; o
RemoveDevice do BlueZ apaga o bond e o `[ServiceRecords]` do cache, e os três
caches ficaram com 46 bytes, só o nome. O que denuncia um bond que evaporou é o
registro de serviço sem o `info` — só esse órfão reprova.

Nenhum teste toca o `/var/lib/bluetooth` de verdade: o `sudo` é um dublê que
troca o caminho por uma árvore temporária.
"""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"

ADAPTADOR = "AC:A7:F1:00:00:CE"
CONTROLE = "A0:FA:9C:00:00:F0"
OUTRO = "D4:2F:4B:00:00:D8"

SO_O_NOME = "[General]\nName=DualSense Wireless Controller\n"
COM_SERVICO = SO_O_NOME + "\n[ServiceRecords]\n0x00010000=3601\n"


def _orfaos(entrada: str) -> str:
    script = (
        "set -uo pipefail; "
        f'HEFESTO_DOCTOR_LIB_ONLY=1 source "{DOCTOR}" >/dev/null 2>&1 || true; '
        "_bt_caches_orfaos"
    )
    r = subprocess.run(
        ["bash", "-c", script], input=entrada, capture_output=True, text=True, check=False
    )
    return r.stdout.strip()


class TestOrfaoPuro:
    def test_cache_so_com_o_nome_nao_entra_na_conta(self) -> None:
        # O chamador só passa caches COM registro de serviço: sem nenhum, zero.
        assert _orfaos("") == "0"

    def test_registro_de_servico_sem_info_e_orfao(self) -> None:
        assert _orfaos(f"/b/{ADAPTADOR}/cache/{CONTROLE}\n") == "1"

    def test_registro_de_servico_com_info_nao_e_orfao(self) -> None:
        entrada = f"/b/{ADAPTADOR}/{CONTROLE}/info\n/b/{ADAPTADOR}/cache/{CONTROLE}\n"
        assert _orfaos(entrada) == "0"

    def test_o_info_vale_so_no_mesmo_adaptador(self) -> None:
        entrada = f"/b/AC:A7:F1:00:00:41/{CONTROLE}/info\n/b/{ADAPTADOR}/cache/{CONTROLE}\n"
        assert _orfaos(entrada) == "1"


def _check(tmp_path: Path) -> str:
    """Roda `check_bt_bonds_persistidos` com um `sudo` que lê a árvore falsa."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    sudo = bin_dir / "sudo"
    sudo.write_text(
        "#!/usr/bin/env bash\n"
        '[[ "$1" == -n ]] && shift\n'
        "args=()\n"
        'for a in "$@"; do args+=("${a//\\/var\\/lib\\/bluetooth/$ARVORE_BT}"); done\n'
        'exec "${args[@]}"\n',
        encoding="utf-8",
    )
    sudo.chmod(sudo.stat().st_mode | stat.S_IEXEC)
    script = (
        "set -uo pipefail; "
        f'HEFESTO_DOCTOR_LIB_ONLY=1 source "{DOCTOR}" >/dev/null 2>&1 || true; '
        "check_bt_bonds_persistidos"
    )
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["ARVORE_BT"] = str(tmp_path / "bt")
    r = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, check=False, env=env
    )
    return r.stdout + r.stderr


def _arvore(tmp_path: Path, caches: dict[str, str], bonds: tuple[str, ...] = ()) -> None:
    cache = tmp_path / "bt" / ADAPTADOR / "cache"
    cache.mkdir(parents=True)
    for mac, texto in caches.items():
        (cache / mac).write_text(texto, encoding="utf-8")
    for mac in bonds:
        d = tmp_path / "bt" / ADAPTADOR / mac
        d.mkdir()
        (d / "info").write_text("[LinkKey]\n", encoding="utf-8")


class TestOCheck:
    def test_removidos_pelo_sistema_nao_reprovam(self, tmp_path: Path) -> None:
        # O retrato de 30/09: os removidos ficaram só com o nome.
        _arvore(tmp_path, {CONTROLE: SO_O_NOME, OUTRO: SO_O_NOME})
        saida = _check(tmp_path)
        assert "[FAIL]" not in saida
        assert "nenhum controle pareado agora" in saida
        assert "bt_bonds_restore" not in saida

    def test_bond_evaporado_reprova(self, tmp_path: Path) -> None:
        _arvore(tmp_path, {CONTROLE: COM_SERVICO, OUTRO: SO_O_NOME})
        saida = _check(tmp_path)
        assert "[FAIL]" in saida
        assert "1 aparelho(s) com registro de serviço" in saida

    def test_com_bond_passa(self, tmp_path: Path) -> None:
        _arvore(tmp_path, {CONTROLE: COM_SERVICO}, bonds=(CONTROLE,))
        saida = _check(tmp_path)
        assert "[FAIL]" not in saida
        assert "bonds BT persistidos em disco: 1" in saida
