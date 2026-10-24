"""O-AGREGADO-DO-DIARIO-NAO-ESCREVE-NO-STDOUT-JA-FECHADO-01 (24/10/2026).

Medido no fim do pytest de `test_o_led_de_quem_espera_nao_enche_o_diario.py` e
`test_o_lugar_guardado_do_p2_ao_p4_espera_no_vpad_dele.py`: o `atexit` do
`AgregadoDoDiario` escrevia a conta aberta num stdout que o pytest já fechou, e saía
`ValueError: I/O operation on closed file` no stderr. Destino fechado: a conta se perde
calada. Destino aberto: a linha agregada sai como antes. Outro erro sobe.

MORDIDA: tirar o `try` do `AgregadoDoDiario._escrever` reprova as duas primeiras réguas
com o `ValueError`.
"""

from __future__ import annotations

import errno
import io
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.utils import logging_config


def _agregado_com_conta_aberta(destino: Any) -> logging_config.AgregadoDoDiario:
    agora = [100.0]
    agregado = logging_config.AgregadoDoDiario(
        eventos={"gatilho_armado": ("nome",)}, relogio=lambda: agora[0]
    )
    agregado._agendar = lambda *_a: None  # type: ignore[method-assign]
    agregado.diario = structlog.wrap_logger(
        structlog.PrintLogger(file=destino),
        processors=[agregado, structlog.processors.KeyValueRenderer(sort_keys=True)],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
    )
    for _ in range(3):
        agregado.diario.info("gatilho_armado", nome="cor")
        agora[0] += 1.0
    return agregado


def test_destino_fechado_a_conta_se_perde_calada(tmp_path: Path) -> None:
    # D-2410-O-DIARIO-NAO-ESCREVE-NO-DESTINO-FECHADO
    destino = (tmp_path / "diario.txt").open("w", encoding="utf-8")
    agregado = _agregado_com_conta_aberta(destino)
    destino.close()
    agregado.fechar_tudo()
    assert agregado._janelas == {}


def test_o_atexit_do_processo_sai_sem_traceback_com_o_stdout_fechado() -> None:
    programa = (
        "import sys\n"
        "from hefesto_dualsense4unix.utils import logging_config as lc\n"
        "lc.configure_logging(stream=sys.stdout)\n"
        "log = lc.get_logger('prova')\n"
        "log.info('gatilho_armado', nome='cor')\n"
        "log.info('gatilho_armado', nome='cor')\n"
        "sys.stdout.close()\n"
    )
    ambiente = dict(os.environ)
    ambiente["PYTHONPATH"] = os.pathsep.join(
        [str(Path(logging_config.__file__).parents[2]), ambiente.get("PYTHONPATH", "")]
    )
    ambiente.pop("HEFESTO_DUALSENSE4UNIX_LOG_LEVEL", None)
    feito = subprocess.run(
        [sys.executable, "-c", programa],
        capture_output=True, text=True, timeout=60, env=ambiente, check=False,
    )
    assert feito.returncode == 0, feito.stderr
    assert "gatilho_armado" in feito.stdout
    assert "ValueError" not in feito.stderr, feito.stderr
    assert "Traceback" not in feito.stderr, feito.stderr


def test_destino_aberto_a_linha_agregada_sai_com_vezes_e_janela() -> None:
    destino = io.StringIO()
    agregado = _agregado_com_conta_aberta(destino)
    agregado.fechar_tudo()
    linhas = destino.getvalue().splitlines()
    assert len(linhas) == 2, linhas
    assert "vezes" not in linhas[0]
    assert "vezes=2" in linhas[1]
    assert f"janela_s={logging_config.JANELA_DO_AGREGADO_S}" in linhas[1]


class _DestinoQueFalha(io.StringIO):
    def __init__(self, erro: BaseException) -> None:
        super().__init__()
        self.erro = erro
        self.armado = False

    def write(self, texto: str) -> int:
        if self.armado:
            raise self.erro
        return super().write(texto)


@pytest.mark.parametrize(
    "erro",
    [OSError(errno.EPIPE, "Broken pipe"), OSError(errno.EBADF, "Bad file descriptor")],
)
def test_cano_sem_leitor_tambem_se_perde_calado(erro: OSError) -> None:
    destino = _DestinoQueFalha(erro)
    agregado = _agregado_com_conta_aberta(destino)
    destino.armado = True
    agregado.fechar_tudo()


@pytest.mark.parametrize(
    "erro",
    [ValueError("valor ruim do diário"), OSError(errno.ENOSPC, "No space left on device")],
)
def test_outro_erro_de_escrita_sobe(erro: BaseException) -> None:
    destino = _DestinoQueFalha(erro)
    agregado = _agregado_com_conta_aberta(destino)
    destino.armado = True
    with pytest.raises(type(erro)):
        agregado.fechar_tudo()
