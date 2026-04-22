"""Utilitários de teste e runtime.

`FakeController` fornece implementação de `IController` sem hardware, usada
tanto em testes unitários quanto em smoke/debug do daemon via
`HEFESTO_FAKE=1`. Expor o módulo dentro do pacote canônico evita
manipulação de `PYTHONPATH` ao rodar `hefesto daemon start --foreground`
fora do wrapper `run.sh` (ver sprint CHORE-FAKEPATH-01).
"""

from __future__ import annotations

from hefesto.testing.fake_controller import FakeController, FakeControllerCommand, FakeLedState

__all__ = ["FakeController", "FakeControllerCommand", "FakeLedState"]
