"""O nome do lugar vem do maquina.json da conta que está na sessão, não da casa de quem instalou."""

from __future__ import annotations

import subprocess
from pathlib import Path

from tests.unit.test_o_que_era_do_zsh_mora_no_hefesto import _roda_a_cura

RAIZ = Path(__file__).resolve().parents[2]
MODO_ATIVO = RAIZ / "scripts" / "bt_active_mode.sh"
VIGIA = RAIZ / "scripts" / "bt_health_watchdog.sh"
UNIT = RAIZ / "assets" / "systemd" / "hefesto-bt-health-watchdog.service"
DROPIN_VELHO = "/etc/systemd/system/hefesto-bt-health-watchdog.service.d/10-hefesto-maquina.conf"
CONTAS = {"ana": 1001, "bia": 1002}


def _funcao(linhas: list[str], nome: str) -> list[str]:
    abertura = f"    {nome}() {{"
    if abertura not in linhas:
        return []
    ini = linhas.index(abertura)
    fim = next(i for i in range(ini, len(linhas)) if linhas[i] == "    }")
    return [linha[4:] for linha in linhas[ini : fim + 1]]


def _o_leitor_do_maquina_json() -> str:
    linhas = MODO_ATIVO.read_text(encoding="utf-8").splitlines()
    corpo = _funcao(linhas, "_uid_da_sessao_ativa") + _funcao(linhas, "_maquina_json")
    assert corpo, "o bt_active_mode.sh não tem mais o _maquina_json"
    return "\n".join(corpo)


def _executavel(caminho: Path, corpo: str) -> None:
    caminho.write_text("#!/bin/bash\n" + corpo, encoding="utf-8")
    caminho.chmod(0o755)


class Maquina:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.bin = tmp / "bin"
        self.bin.mkdir()
        self.assentos = tmp / "assentos"
        self.assentos.mkdir()
        passwd = "".join(
            f"{nome}:x:{uid}:{uid}::{tmp / 'home' / nome}:/bin/bash\n"
            for nome, uid in CONTAS.items()
        )
        passwd += f"root:x:0:0::{tmp / 'root'}:/bin/bash\n"
        (tmp / "passwd").write_text(passwd, encoding="utf-8")
        _executavel(self.bin / "getent", f'[ "$1" = passwd ] && cat "{tmp / "passwd"}"\n')
        _executavel(
            self.bin / "loginctl",
            f'A="{self.assentos}"\n'
            'case "$1" in\n'
            '  list-seats) for f in "$A"/*; do [ -e "$f" ] && echo "${f##*/}"; done ;;\n'
            '  show-seat) [ -f "$A/$2" ] && echo "sessao-$2" ;;\n'
            '  show-session) s="${2#sessao-}"; [ -f "$A/$s" ] && cat "$A/$s" ;;\n'
            "esac\n"
            "exit 0\n",
        )

    def guardar_lugares(self, conta: str) -> Path:
        arquivo = self.tmp / "home" / conta / ".config" / "hefesto-dualsense4unix" / "maquina.json"
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text('{"version": 1, "adaptadores": {}}', encoding="utf-8")
        return arquivo

    def entrar(self, conta: str, assento: str = "seat0") -> None:
        (self.assentos / assento).write_text(f"{CONTAS[conta]}\n", encoding="utf-8")

    def sair(self, assento: str = "seat0") -> None:
        (self.assentos / assento).unlink()

    def o_que_o_modo_ativo_le(self) -> str:
        roteiro = self.tmp / "leitor.sh"
        roteiro.write_text(
            "set -euo pipefail\n" + _o_leitor_do_maquina_json() + "\n_maquina_json\n",
            encoding="utf-8",
        )
        feito = subprocess.run(
            ["bash", str(roteiro)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env={"PATH": f"{self.bin}:/usr/bin:/bin", "HOME": str(self.tmp)},
        )
        assert feito.returncode == 0, feito.stderr[-800:]
        return feito.stdout.strip()


def test_duas_contas_com_lugares_vale_a_que_esta_na_sessao(tmp_path: Path) -> None:
    maquina = Maquina(tmp_path)
    da_ana = maquina.guardar_lugares("ana")
    da_bia = maquina.guardar_lugares("bia")
    maquina.entrar("bia")
    assert maquina.o_que_o_modo_ativo_le() == f"1002:{da_bia}"
    maquina.entrar("ana")
    assert maquina.o_que_o_modo_ativo_le() == f"1001:{da_ana}"


def test_sem_sessao_ativa_so_o_arquivo_unico_vale(tmp_path: Path) -> None:
    maquina = Maquina(tmp_path)
    da_ana = maquina.guardar_lugares("ana")
    da_bia = maquina.guardar_lugares("bia")
    assert maquina.o_que_o_modo_ativo_le() == ""
    da_bia.unlink()
    assert maquina.o_que_o_modo_ativo_le() == f"1001:{da_ana}"


def test_a_conta_da_sessao_sem_lugares_usa_o_unico_guardado(tmp_path: Path) -> None:
    maquina = Maquina(tmp_path)
    da_ana = maquina.guardar_lugares("ana")
    maquina.entrar("bia")
    assert maquina.o_que_o_modo_ativo_le() == f"1001:{da_ana}"


def test_dois_assentos_com_contas_diferentes_nao_escolhem_por_ninguem(tmp_path: Path) -> None:
    maquina = Maquina(tmp_path)
    maquina.guardar_lugares("ana")
    maquina.guardar_lugares("bia")
    maquina.entrar("ana", "seat0")
    maquina.entrar("bia", "seat1")
    assert maquina.o_que_o_modo_ativo_le() == ""
    maquina.sair("seat0")
    assert maquina.o_que_o_modo_ativo_le().startswith("1002:")


def _diretivas(texto: str) -> list[tuple[str, str]]:
    return [
        (chave.strip(), valor.strip())
        for chave, _, valor in (
            linha.partition("=")
            for linha in texto.splitlines()
            if linha.strip() and not linha.lstrip().startswith(("#", "["))
        )
    ]


def test_o_vigia_roda_o_modo_ativo_fora_do_sandbox_e_so_ele() -> None:
    diretivas = _diretivas(UNIT.read_text(encoding="utf-8"))
    execs = [valor for chave, valor in diretivas if chave == "ExecStart"]
    assert execs == [
        "-+/usr/local/lib/hefesto-dualsense4unix/bt_active_mode.sh --quiet",
        "/usr/local/lib/hefesto-dualsense4unix/bt_health_watchdog.sh",
    ], execs
    assert ("ProtectHome", "yes") in diretivas
    assert not [c for c, _ in diretivas if c.startswith("Bind")], "a unit voltou a abrir uma casa"


def test_o_tique_do_vigia_nao_chama_o_modo_ativo_de_dentro_do_sandbox() -> None:
    codigo = [
        linha
        for linha in VIGIA.read_text(encoding="utf-8").splitlines()
        if not linha.lstrip().startswith("#")
    ]
    assert not [linha for linha in codigo if "bt_active_mode" in linha]


def test_o_install_nao_prende_o_vigia_a_casa_de_quem_instalou(tmp_path: Path) -> None:
    _, sudo, captura = _roda_a_cura(tmp_path, "install_bt_resilience_host", {})
    linhas = sudo.splitlines()
    assert str(tmp_path / "casa") not in sudo, "o install gravou a casa de quem instalou"
    assert not [ln for ln in linhas if ln.startswith("install ") and ".service.d/" in ln
                and "hefesto-bt-health-watchdog" in ln]
    assert not (captura / "10-hefesto-maquina.conf").exists()
    tira = linhas.index(f"rm -f {DROPIN_VELHO}")
    assert tira < linhas.index("systemctl daemon-reload")

