"""O doctor confere a última partida do vigia da Steam.

O-DOCTOR-CONFERE-A-ULTIMA-PARTIDA-DO-VIGIA-DA-STEAM-01 (21/11/2026). O ``--censo`` da sentinela só
lê e nunca passa pelo caminho que caía, então o doctor prometia «repõe sozinho» sem saber se o vigia
chegou ao reparo. Agora ele lê o ``Result`` da unidade e, com a última partida falhada, diz a falha
e o comando do diário. O ``systemctl`` é de mentira no ``PATH`` (só responde ao ``show`` da unidade)
e o ``HOME`` é um lar de mentira com um ``localconfig.vdf`` de jogo sem o atalho.
"""

from __future__ import annotations

import shutil
import stat
import subprocess
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"
UNIDADE = "hefesto-steam-input-guard.service"
DIARIO = f"journalctl --user -u {UNIDADE} -n 50"
T = "\t"

pytestmark = pytest.mark.skipif(shutil.which("python3") is None, reason="sem python3 para o censo")


def _vdf(apps: dict[str, str]) -> str:
    blocos = "".join(
        f'{T * 5}"{a}"\n{T * 5}{{\n{T * 6}"LaunchOptions"{T * 2}"{v}"\n{T * 5}}}\n'
        for a, v in apps.items()
    )
    return (
        '"UserLocalConfigStore"\n{\n'
        f'{T}"Software"\n{T}{{\n{T * 2}"Valve"\n{T * 2}{{\n{T * 3}"Steam"\n{T * 3}{{\n'
        f'{T * 4}"apps"\n{T * 4}{{\n{blocos}{T * 4}}}\n{T * 3}}}\n{T * 2}}}\n{T}}}\n}}\n'
    )


def _rodar(
    tmp_path: Path,
    *,
    carga: str = "loaded",
    ativo: str = "inactive",
    resultado: str = "success",
    sem_systemctl: bool = False,
) -> str:
    lar = tmp_path / "lar"
    conf = lar / ".steam" / "steam" / "userdata" / "1" / "config" / "localconfig.vdf"
    conf.parent.mkdir(parents=True)
    conf.write_text(_vdf({"9900620": "%command%"}), encoding="utf-8")
    fakes = tmp_path / "fakes"
    fakes.mkdir()
    chamadas = tmp_path / "chamadas.log"
    sistemctl = fakes / "systemctl"
    sistemctl.write_text(
        "#!/bin/bash\n"
        f'printf "%s\\n" "$*" >> "{chamadas}"\n'
        + ("exit 1\n" if sem_systemctl else
           'if [[ "$1 $2" != "--user show" ]]; then exit 1; fi\n'
           f'[[ "${{*: -1}}" == "{UNIDADE}" ]] || exit 1\n'
           "shift 2\n"
           'while [[ $# -gt 1 ]]; do\n'
           '  if [[ "$1" == "-p" ]]; then\n'
           '    case "$2" in\n'
           f'      LoadState) echo "LoadState={carga}" ;;\n'
           f'      ActiveState) echo "ActiveState={ativo}" ;;\n'
           f'      Result) echo "Result={resultado}" ;;\n'
           "    esac\n"
           "    shift\n"
           "  fi\n"
           "  shift\n"
           "done\n"),
        encoding="utf-8",
    )
    sistemctl.chmod(sistemctl.stat().st_mode | stat.S_IEXEC)
    env = {
        "PATH": f"{fakes}:/usr/bin:/bin",
        "HOME": str(lar),
        "XDG_CONFIG_HOME": str(lar / ".config"),
        "XDG_STATE_HOME": str(lar / ".local" / "state"),
    }
    script = (f'source "{DOCTOR}"\nQUIET=0\nWARNS=0\nFAILS=0\n'
              "check_sentinela_wrapper\n"
              'echo "WARNS=${WARNS} FAILS=${FAILS}"\n')
    r = subprocess.run([BASH, "-c", script], env=env, capture_output=True, text=True,
                       timeout=90, check=False)
    return r.stdout + r.stderr


def _linha_do_vigia(saida: str) -> str:
    achadas = [ln for ln in saida.splitlines() if "vigia da Steam" in ln]
    return achadas[0] if achadas else ""


def _linha_dos_jogos(saida: str) -> str:
    achadas = [ln for ln in saida.splitlines() if "sem as Opções de Inicialização" in ln]
    return achadas[0] if achadas else ""


def test_a_ultima_partida_falhada_diz_a_falha_e_o_comando_do_diario(tmp_path: Path) -> None:
    """MORDIDA: sem a leitura do Result, o doctor fica calado sobre o vigia que caiu."""
    saida = _rodar(tmp_path, ativo="failed", resultado="exit-code")
    linha = _linha_do_vigia(saida)
    assert linha.startswith("[WARN]"), saida
    assert "falhou na última partida" in linha, saida
    assert DIARIO in linha, saida


def test_com_a_partida_falhada_a_promessa_de_repor_sozinho_nao_sai(tmp_path: Path) -> None:
    """MORDIDA: sem a troca da promessa, o doctor segue dizendo que o Hefesto repõe sozinho."""
    saida = _rodar(tmp_path, ativo="failed", resultado="exit-code")
    jogos = _linha_dos_jogos(saida)
    assert jogos, saida
    assert "repõe" not in jogos and "fica para quando" not in jogos, jogos
    assert "falhou na última partida" in jogos, jogos
    assert "--reparar" in jogos, jogos


@pytest.mark.parametrize("resultado", ["signal", "core-dump", "timeout", "start-limit-hit"])
def test_todo_resultado_que_nao_e_success_conta_como_falha(tmp_path: Path, resultado: str) -> None:
    saida = _rodar(tmp_path, ativo="failed", resultado=resultado)
    assert "falhou na última partida" in _linha_do_vigia(saida), saida


def test_com_a_partida_boa_nada_muda_em_relacao_a_hoje(tmp_path: Path) -> None:
    saida = _rodar(tmp_path, resultado="success")
    assert "falhou" not in saida, saida
    assert DIARIO not in saida, saida
    jogos = _linha_dos_jogos(saida)
    assert "o Hefesto repõe" in jogos or "o reparo fica para quando" in jogos or (
        "repõe assim que a Steam fechar" in jogos), jogos


def test_sem_a_unidade_instalada_nada_se_acusa(tmp_path: Path) -> None:
    saida = _rodar(tmp_path, carga="not-found", ativo="inactive", resultado="success")
    assert "falhou" not in saida and DIARIO not in saida, saida
    saida = _rodar(tmp_path / "outra", carga="not-found", ativo="inactive", resultado="exit-code")
    assert "falhou" not in saida and DIARIO not in saida, saida


def test_a_partida_em_andamento_nao_se_acusa(tmp_path: Path) -> None:
    saida = _rodar(tmp_path, ativo="activating", resultado="exit-code")
    assert "falhou" not in saida, saida


def test_sem_o_systemd_do_usuario_o_doctor_fica_calado_sobre_o_vigia(tmp_path: Path) -> None:
    saida = _rodar(tmp_path, sem_systemctl=True)
    assert _linha_do_vigia(saida) == "" and "falhou" not in saida, saida


def test_o_doctor_so_pergunta_a_unidade_e_nunca_a_muda(tmp_path: Path) -> None:
    _rodar(tmp_path, ativo="failed", resultado="exit-code")
    verbos = (tmp_path / "chamadas.log").read_text(encoding="utf-8").splitlines()
    assert verbos, "o doctor nem perguntou ao systemd pela unidade do vigia"
    assert all(v.startswith("--user show ") for v in verbos), verbos
