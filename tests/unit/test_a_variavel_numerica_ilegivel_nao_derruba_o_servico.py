"""A variável numérica ilegível do ambiente não derruba o serviço: vale o padrão, e o aviso sai.

Um leitor só (``utils/numero_do_ambiente.py``) para toda variável numérica: o backend importa, a
configuração do serviço se monta e cada guarda antiga (o teto do toque curto, a porta das
métricas) cai no padrão com o ``warning`` da chave.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from structlog.testing import capture_logs

from hefesto_dualsense4unix.utils.numero_do_ambiente import numero_do_ambiente

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src"
ILEGIVEIS = ("", "abc", "5s", "nan", "inf")


def _avisos(diario: list[dict[str, object]], chave: str) -> list[dict[str, object]]:
    return [e for e in diario if e.get("log_level") == "warning" and e.get("chave") == chave]


@pytest.mark.parametrize("bruto", ILEGIVEIS)
def test_o_leitor_cai_no_padrao_e_avisa(bruto: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HEFESTO_X", bruto)
    with capture_logs() as diario:
        assert numero_do_ambiente("HEFESTO_X", 7) == 7
        assert numero_do_ambiente("HEFESTO_X", 0.5) == 0.5
    assert len(_avisos(diario, "HEFESTO_X")) == 2


def test_o_leitor_le_o_legivel_e_recusa_o_fora_da_faixa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HEFESTO_X", raising=False)
    assert numero_do_ambiente("HEFESTO_X", 7) == 7
    monkeypatch.setenv("HEFESTO_X", " 12 ")
    assert numero_do_ambiente("HEFESTO_X", 7) == 12
    assert numero_do_ambiente("HEFESTO_X", 0.5) == 12.0
    with capture_logs() as diario:
        assert numero_do_ambiente("HEFESTO_X", 7, piso=0, teto=10) == 7
    assert [e["event"] for e in _avisos(diario, "HEFESTO_X")] == [
        "variavel_numerica_fora_da_faixa"]


@pytest.mark.parametrize("chave", [
    "HEFESTO_DUALSENSE4UNIX_INIT_TIMEOUT_SEC", "HEFESTO_DUALSENSE4UNIX_REPORT_THROTTLE_SEC"])
@pytest.mark.parametrize("bruto", ["", "abc", "5s"])
def test_o_backend_importa_com_a_variavel_ilegivel(chave: str, bruto: str, tmp_path: Path) -> None:
    """O backend importa num processo novo, com o padrão no lugar do número torto."""
    ambiente = {**os.environ, chave: bruto, "PYTHONPATH": str(SRC), "HOME": str(tmp_path)}
    programa = (
        "import json\n"
        "import hefesto_dualsense4unix.core.backend_pydualsense as b\n"
        "print(json.dumps([b.INIT_TIMEOUT_SEC, b.REPORT_THREAD_THROTTLE_SEC]))\n"
    )
    feito = subprocess.run(
        [sys.executable, "-c", programa], env=ambiente, capture_output=True, text=True,
        timeout=60, check=False)
    assert feito.returncode == 0, feito.stderr[-2000:]
    assert json.loads(feito.stdout.strip().splitlines()[-1]) == [5.0, 0.008]
    assert "variavel_numerica_ilegivel" in feito.stdout + feito.stderr


@pytest.mark.parametrize("bruto", ["", "abc", "5s"])
def test_a_configuracao_do_servico_se_monta_com_o_padrao(
    bruto: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hefesto_dualsense4unix.daemon.main import montar_a_configuracao

    for chave in ("HEFESTO_DUALSENSE4UNIX_POLL_HZ", "HEFESTO_DUALSENSE4UNIX_PS_LONG_PRESS_MS"):
        monkeypatch.setenv(chave, bruto)
    with capture_logs() as diario:
        config = montar_a_configuracao()
    assert (config.poll_hz, config.ps_long_press_ms) == (60, 0)
    assert _avisos(diario, "HEFESTO_DUALSENSE4UNIX_POLL_HZ")
    assert _avisos(diario, "HEFESTO_DUALSENSE4UNIX_PS_LONG_PRESS_MS")


def test_as_guardas_antigas_passam_pelo_leitor(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems.metrics import ENV_METRICS_PORT, _porta_efetiva
    from hefesto_dualsense4unix.integrations.hotkey_daemon import (
        DEFAULT_PS_TOQUE_CURTO_TETO_MS,
        ENV_PS_TOQUE_CURTO_TETO_MS,
        _teto_do_toque_curto_do_ambiente,
    )

    monkeypatch.setenv(ENV_METRICS_PORT, "5s")
    monkeypatch.setenv(ENV_PS_TOQUE_CURTO_TETO_MS, "5s")
    with capture_logs() as diario:
        assert _porta_efetiva(9090) == 9090
        assert _teto_do_toque_curto_do_ambiente() == DEFAULT_PS_TOQUE_CURTO_TETO_MS
    assert _avisos(diario, ENV_METRICS_PORT) and _avisos(diario, ENV_PS_TOQUE_CURTO_TETO_MS)


ARQUIVOS_COM_NUMERO_DO_AMBIENTE = (
    "core/backend_pydualsense.py",
    "daemon/main.py",
    "integrations/hotkey_daemon.py",
    "daemon/subsystems/metrics.py",
)


@pytest.mark.parametrize("arquivo", ARQUIVOS_COM_NUMERO_DO_AMBIENTE)
def test_nenhum_numero_cru_do_ambiente_nos_leitores(arquivo: str) -> None:
    """``int(os.getenv(...))`` ou ``float(os.environ.get(...))`` cru reprova: o leitor é um só."""
    arvore = ast.parse((SRC / "hefesto_dualsense4unix" / arquivo).read_text(encoding="utf-8"))
    crus = [
        no.lineno for no in ast.walk(arvore)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
        and no.func.id in {"int", "float"}
        and any("getenv" in ast.dump(a) or "environ" in ast.dump(a) for a in no.args)
    ]
    assert not crus, f"{arquivo}: número cru do ambiente nas linhas {crus}"
