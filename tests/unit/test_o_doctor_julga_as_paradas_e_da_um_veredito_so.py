"""O doctor julga as paradas do serviço e fecha com um veredito só.

D-2511-O-DOCTOR-DA-UM-VEREDITO-SO: as paradas por minuto de vida do serviço acima do limiar viram
aviso, e o veredito é uma linha só, impressa por último, que soma o script e os blocos e diz o
código de saída.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli import cmd_doctor, ipc_client
from hefesto_dualsense4unix.cli.app import app

RAIZ = Path(__file__).resolve().parents[2]
MINUTO = 60.0


def test_seiscentas_paradas_em_dezesseis_minutos_avisam() -> None:
    linha = cmd_doctor._linha_do_atraso(
        {"poll.laco.lentas": 626, "poll.laco.pior_us": 690_100, "poll.laco.lenta.sleep": 690_100},
        vida_s=16 * MINUTO,
    )
    assert linha is not None
    assert linha[0] == "[WARN]", linha
    assert "626 paradas acima de 100 ms" in linha[1]
    assert "por minuto em 16,0 min de serviço" in linha[1]
    assert "janelas e bandejas abertas e as extensões" in linha[1]


def test_tres_paradas_em_uma_hora_ficam_ok() -> None:
    linha = cmd_doctor._linha_do_atraso({"poll.laco.lentas": 3}, vida_s=60 * MINUTO)
    assert linha is not None and linha[0] == "[ OK ]", linha


def _tag_do_atraso(paradas: int, vida_s: float | None) -> str:
    linha = cmd_doctor._linha_do_atraso({"poll.laco.lentas": paradas}, vida_s=vida_s)
    assert linha is not None
    return linha[0]


def test_as_paradas_da_subida_nao_acusam_e_sem_a_vida_so_informa() -> None:
    assert _tag_do_atraso(4, 2 * MINUTO) == "[ OK ]"
    assert _tag_do_atraso(626, None) == "[INFO]"
    assert _tag_do_atraso(0, None) == "[ OK ]"


def test_as_esperas_da_fila_contam_na_taxa() -> None:
    linha = cmd_doctor._linha_do_atraso(
        {"poll.laco.lentas": 0, "poll.pool.lentas": 300}, vida_s=20 * MINUTO
    )
    assert linha is not None and linha[0] == "[WARN]", linha


def test_o_tique_com_parte_pesada_acima_do_orcamento_avisa() -> None:
    def linha(medidos: int, estouros: int) -> tuple[str, str] | None:
        return cmd_doctor._linha_do_tique(
            {"poll.tique.medidos": medidos, "poll.tique.estouros": estouros}
        )

    pesado, leve, pouco_medido = linha(47687, 1786), linha(47687, 3), linha(100, 40)
    assert pesado is not None and pesado[0] == "[WARN]", pesado
    assert pesado[1].startswith("tique do laço: 1786 de 47687 acima de 16,7 ms")
    assert leve is not None and leve[0] == "[ OK ]", leve
    assert pouco_medido is not None and pouco_medido[0] == "[ OK ]", pouco_medido


class _Cliente:
    def __init__(self, contadores: dict[str, Any]) -> None:
        self._contadores = contadores

    async def __aenter__(self) -> _Cliente:
        return self

    async def __aexit__(self, *_a: Any) -> None:
        return None

    async def call(self, metodo: str, *_a: Any, **_k: Any) -> dict[str, Any]:
        if metodo == "daemon.state_full":
            return {"counters": self._contadores}
        return {"profiles": []} if metodo == "profile.list" else {"paused": False}


def _as_linhas_do_daemon(
    monkeypatch: pytest.MonkeyPatch, contadores: dict[str, Any], vida_s: float | None
) -> tuple[list[tuple[str, str]], list[int]]:
    chamadas: list[int] = []

    def vida() -> float | None:
        chamadas.append(1)
        return vida_s

    monkeypatch.setattr(ipc_client.IpcClient, "connect", lambda *_a, **_k: _Cliente(contadores))
    monkeypatch.setattr(cmd_doctor, "_vida_do_servico_s", vida)
    return asyncio.run(cmd_doctor._daemon_checks()), chamadas


def test_o_doctor_le_a_vida_da_unit_so_quando_ha_parada(monkeypatch: pytest.MonkeyPatch) -> None:
    linhas, chamadas = _as_linhas_do_daemon(
        monkeypatch, {"poll.laco.lentas": 626, "poll.pool.lentas": 0}, vida_s=16 * MINUTO
    )
    do_atraso = [(t, m) for t, m in linhas if m.startswith("atraso do serviço")]
    assert do_atraso and do_atraso[0][0] == "[WARN]", linhas
    assert chamadas == [1]
    linhas, chamadas = _as_linhas_do_daemon(monkeypatch, {"poll.laco.lentas": 0}, vida_s=None)
    assert chamadas == []
    assert [t for t, m in linhas if m.startswith("atraso do serviço")] == ["[ OK ]"]


def test_a_vida_ilegivel_diz_o_motivo_e_nao_acusa(monkeypatch: pytest.MonkeyPatch) -> None:
    def _sem_systemctl() -> float | None:
        raise FileNotFoundError("systemctl")

    monkeypatch.setattr(
        ipc_client.IpcClient, "connect", lambda *_a, **_k: _Cliente({"poll.laco.lentas": 626})
    )
    monkeypatch.setattr(cmd_doctor, "_vida_do_servico_s", _sem_systemctl)
    linhas = asyncio.run(cmd_doctor._daemon_checks())
    assert ("[INFO]", "vida do serviço ilegível (FileNotFoundError)") in linhas
    do_atraso = [(t, m) for t, m in linhas if m.startswith("atraso do serviço")]
    assert do_atraso == [("[INFO]", do_atraso[0][1])], linhas
    assert do_atraso[0][1].endswith("sem a vida do serviço, sem taxa")


def _o_sh_de_mentira(pasta: Path, falhas: int, avisos: int, rc: int) -> Path:
    """Um `doctor.sh` que, ao fechar, anota a contagem ou imprime o veredito, como o de verdade."""
    sh = pasta / "doctor.sh"
    sh.write_text(
        "printf '[WARN] um aviso do script\\n'\n"
        'if [ -n "${HEFESTO_DOCTOR_CONTAGEM:-}" ]; then\n'
        f'  echo "{falhas} {avisos}" > "$HEFESTO_DOCTOR_CONTAGEM"\n'
        "else\n"
        f"  echo ' Diagnóstico: tudo OK ({avisos} aviso(s))'\n"
        "fi\n"
        f"exit {rc}\n",
        encoding="utf-8",
    )
    return sh


def _o_doctor_com(
    monkeypatch: pytest.MonkeyPatch,
    pasta: Path,
    *,
    do_script: tuple[int, int, int],
    do_daemon: list[tuple[str, str]],
    args: tuple[str, ...] = (),
) -> Any:
    async def _checks() -> list[tuple[str, str]]:
        return do_daemon

    monkeypatch.setattr(cmd_doctor, "_find_doctor_sh", lambda: _o_sh_de_mentira(pasta, *do_script))
    for bloco in (
        "_print_storm_block",
        "_print_bloco_contratos",
        "_print_bloco_proton_fixado",
        "_print_bloco_entrada",
        "_print_bloco_registro",
        "_print_bloco_install",
    ):
        monkeypatch.setattr(cmd_doctor, bloco, lambda: 0)
    monkeypatch.setattr(cmd_doctor, "_print_bloco_perfis", lambda: False)
    monkeypatch.setattr(cmd_doctor, "_daemon_checks", _checks)
    return CliRunner().invoke(app, ["doctor", *args])


def _linhas(saida: str) -> list[str]:
    return [linha for linha in saida.splitlines() if linha.strip()]


def test_o_veredito_e_uma_linha_so_no_fim_e_soma_o_script_e_os_blocos(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """D-2511-O-DOCTOR-DA-UM-VEREDITO-SO: uma linha só, a última, com o total e o código."""
    r = _o_doctor_com(
        monkeypatch, tmp_path, do_script=(0, 12, 0), do_daemon=[("[WARN]", "um aviso do bloco")]
    )
    linhas = _linhas(r.output)
    assert r.exit_code == 1
    assert linhas[-1] == "Diagnóstico: 13 avisos, nenhuma falha. Código de saída 1: só avisos."
    assert not any("tudo OK" in linha for linha in linhas), r.output
    assert sum(linha.startswith("Diagnóstico:") for linha in linhas) == 1


def test_um_aviso_so_nos_blocos_diz_um_aviso(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    r = _o_doctor_com(
        monkeypatch, tmp_path, do_script=(0, 0, 0), do_daemon=[("[WARN]", "um aviso do bloco")]
    )
    ultima = _linhas(r.output)[-1]
    assert ultima == "Diagnóstico: 1 aviso, nenhuma falha. Código de saída 1: só avisos."


def test_aviso_so_do_script_entra_na_conta_e_nao_muda_o_codigo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    r = _o_doctor_com(monkeypatch, tmp_path, do_script=(0, 2, 0), do_daemon=[("[ OK ]", "x")])
    assert r.exit_code == 0
    ultima = _linhas(r.output)[-1]
    assert ultima.startswith("Diagnóstico: 2 avisos, nenhuma falha. Código de saída 0")


def test_aviso_so_dos_perfis_nao_e_dito_como_do_script(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    r = _o_doctor_com(monkeypatch, tmp_path, do_script=(0, 0, 0), do_daemon=[("[ OK ]", "x")])
    assert r.exit_code == 0

    def _perfis_com_aviso() -> bool:
        cmd_doctor._bloco("perfis", [("[WARN]", "perfil sem jogo")])
        return False

    monkeypatch.setattr(cmd_doctor, "_print_bloco_perfis", _perfis_com_aviso)
    r = CliRunner().invoke(app, ["doctor"])
    assert r.exit_code == 0
    assert _linhas(r.output)[-1] == (
        "Diagnóstico: 1 aviso, nenhuma falha. Código de saída 0: esses avisos não mudam o código."
    )


def test_falha_do_script_e_do_bloco_somam_e_o_codigo_e_dois(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    r = _o_doctor_com(
        monkeypatch, tmp_path, do_script=(1, 2, 1), do_daemon=[("[FAIL]", "serviço parado")]
    )
    assert r.exit_code == 2
    assert _linhas(r.output)[-1] == "Diagnóstico: 2 falhas e 2 avisos. Código de saída 2: há falha."


def test_sem_aviso_nem_falha_o_codigo_e_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    r = _o_doctor_com(monkeypatch, tmp_path, do_script=(0, 0, 0), do_daemon=[("[ OK ]", "x")])
    assert r.exit_code == 0
    assert _linhas(r.output)[-1] == "Diagnóstico: nenhum aviso e nenhuma falha. Código de saída 0."


def test_o_json_segue_so_a_lista_dos_blocos(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    r = _o_doctor_com(
        monkeypatch, tmp_path, do_script=(0, 0, 0), do_daemon=[("[WARN]", "x")], args=("--json",)
    )
    assert json.loads(r.output)[0]["mensagem"] == "x"


def test_o_script_so_imprime_o_veredito_dele_rodado_sozinho() -> None:
    """O fecho do `doctor.sh`: com a variável da contagem anota e cala; sozinho, imprime."""
    texto = (RAIZ / "scripts" / "doctor.sh").read_text(encoding="utf-8")
    fecho = texto[texto.rindex('if [[ -n "${HEFESTO_DOCTOR_CONTAGEM:-}" ]]; then') :]
    fecho = fecho[: fecho.index("\n}\n")]
    antes, _fi, depois = fecho.partition("else")
    assert "Diagnóstico:" not in antes
    assert re.search(r"Diagnóstico: tudo OK", depois)
    assert 'printf \'%d %d\\n\' "${FAILS}" "${WARNS}"' in antes
