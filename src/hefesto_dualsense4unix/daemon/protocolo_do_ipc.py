"""As constantes do protocolo do socket — sem importar o servidor do daemon."""
from __future__ import annotations

PROTOCOL_VERSION = "2.0"

CODE_CONTROLLER_DISCONNECTED = -32001
CODE_PROFILE_NOT_FOUND = -32002
CODE_INVALID_PARAMS = -32003
CODE_CONTROLLER_LOST = -32004
CODE_INTERNAL = -32603
CODE_METHOD_NOT_FOUND = -32601
CODE_PARSE_ERROR = -32700
CODE_INVALID_REQUEST = -32600

MAX_PAYLOAD_BYTES = 32_768

#: quanto a IPC espera o P1 que nasce pelo fio: o broker (2 s) e a fila dos pads à frente
PRAZO_DO_P1_QUE_NASCE_S = 8.0
#: o teto da interface para o gesto que pede o P1 (`gamepad.emulation.set` e
#: `gamepad.mask.set`): o prazo do daemon e a folga do socket e do handler
TETO_DO_GESTO_QUE_PEDE_O_P1_S = PRAZO_DO_P1_QUE_NASCE_S + 2.0

__all__ = [
    "CODE_CONTROLLER_DISCONNECTED",
    "CODE_CONTROLLER_LOST",
    "CODE_INTERNAL",
    "CODE_INVALID_PARAMS",
    "CODE_INVALID_REQUEST",
    "CODE_METHOD_NOT_FOUND",
    "CODE_PARSE_ERROR",
    "CODE_PROFILE_NOT_FOUND",
    "MAX_PAYLOAD_BYTES",
    "PRAZO_DO_P1_QUE_NASCE_S",
    "PROTOCOL_VERSION",
    "TETO_DO_GESTO_QUE_PEDE_O_P1_S",
]
