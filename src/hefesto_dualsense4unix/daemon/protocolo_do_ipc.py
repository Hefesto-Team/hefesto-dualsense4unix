"""As constantes do protocolo do socket — sem importar o servidor do daemon.

O-APP-RESPONDE-NA-HORA-01 (02/10/2026). Os dois clientes (a CLI, pelo
`cli/ipc_client.py`, e a janela e a bandeja, pelo `app/ipc_bridge.py`) liam
estas constantes de `daemon/ipc_server.py`, que importa o `ipc_handlers`
inteiro: medido com `-X importtime`, o `cli.ipc_client` custava 245 a 267 ms e
caiu para 67 ms com elas num módulo à parte; a janela, de 431 a 464 ms para
386 a 410 ms. Este módulo não importa nada do produto, e o servidor as
reexporta: quem as importa de lá segue funcionando.

O contrato do protocolo está em `docs/protocol/ipc-unix-socket.md`.
"""
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

# Limite explícito de bytes por request JSON-RPC no dispatch. Cobre handler
# atuais (payloads tipicamente ~1-2 KiB) com folga generosa e protege contra
# payload gigante de cliente local malicioso (socket Unix restrito ao user).
# Ajuste defensivo — HARDEN-IPC-PAYLOAD-LIMIT-01.
MAX_PAYLOAD_BYTES = 32_768

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
    "PROTOCOL_VERSION",
]
