"""As mordidas do caminho POR PEÇA da aba Rumble (RUM-11, 25/08/2026).

Até esta leva, o caminho por peça DA ABA não tinha uma linha de teste. Os dois
métodos que o fazem (``_rumble_edit_uniq``, ``_gravar_intensidade_no_rascunho``)
apareciam em ``tests/unit/test_rumble_actions.py`` **só na lista de composição do
dublê**, e o censo era literal::

    $ grep -rn "_edit_target_uniq" tests/ | grep -ci rumble    # 0

Os dois testes de ``with_controller_rumble`` que existiam
(``test_por_unidade_01_todas_as_abas.py``) exercitam o **modelo**, não a aba.

Cinco mordidas, uma por defeito medido:

1. **RUM-1** — com um controle escolhido no seletor, a aba grava no override
   daquela peça e manda ``rumble.policy_set`` **sem endereço**, que é da máquina
   inteira. A frase que confessa isso estava escrita desde 10/08 na docstring de
   ``_gravar_intensidade_no_rascunho`` e nunca chegou à tela;
2. **RUM-2** — ``rumble.set`` com o alvo apontado e FORA da mesa respondia
   ``ok`` tendo escrito zero byte. A metade "não escreveu" já é provada por
   ``tests/unit/test_p4_alvo_ausente_nao_vira_broadcast.py``; o que falta lá, e
   é o que este arquivo acrescenta, é a metade "e DIZ" — **a RESPOSTA**. Separar
   *"não fez"* de *"fez e não contou"* é o ponto inteiro da tarefa, e um teste
   que só conta bytes não separa os dois;
3. **RUM-3** — com uma peça escolhida, clicar "Auto" apaga o override dela
   (``with_controller_rumble`` limpa, e a regra está certa: o esquema recusa
   ``auto`` por unidade porque ele escala pela bateria do controle PRINCIPAL).
   O toast dizia só *"Intensidade da vibração: Auto"* — indistinguível do caso
   "Todos", com o ajuste da peça apagado em silêncio;
4. **RUM-9** — a linha de pedidos somava os quatro jogadores. *"O jogo pediu
   vibração 40x"* com o Jogador 2 mudo é verdade sobre a mesa e mentira sobre
   quem reclamou;
5. **RUM-4** — *"conforme a bateria do controle"*, no singular e sem dizer
   qual, promete com quatro na mesa um comportamento por jogador que o produto
   não faz: quem escala é sempre o PRIMÁRIO.

**Por que num arquivo só, sendo que a 2 e a 5 não precisam de GTK.** A RUM-11
nomeia UM arquivo, e o motivo é que as mordidas descrevem UM gesto — o clique
com uma peça no seletor — da tela ao daemon. O preço é declarado: as duas
herdam a guarda de `gi` real e só rodam no job `gtk-real`. A prova de que o
`rumble.set` **não escreve** não paga esse preço, porque mora no `test_p4`, que
não importa `gi`.

**Endereços:** faixa sintética ``02:fe:00`` da casa, nunca a ``aabbcc`` — foi a
`aabbcc` que vazou para o ``controllers.json`` VIVO dela em 23/08.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# teste (`app.actions.rumble_actions`) importa `gi` na primeira linha, e sem
exigir_gi_real("aba Rumble: o caminho por peça, da tela ao daemon")

from typing import Any

import pytest


PECA = "02:fe:00:00:00:02"

OUTRA_PECA = "02:fe:00:00:00:03"


class _FakeToggle:
    def __init__(self, active: bool = False) -> None:
        self._active = bool(active)

    def get_active(self) -> bool:
        return self._active

    def set_active(self, v: bool) -> None:
        self._active = bool(v)


class _FakeScale:
    def __init__(self, value: float = 0.0) -> None:
        self._value = float(value)

    def get_value(self) -> float:
        return self._value

    def set_value(self, v: float) -> None:
        self._value = float(v)


class _FakeLabel:
    def __init__(self) -> None:
        self.texto = ""
        self.visivel = False

    def set_visible(self, v: bool) -> None:
        self.visivel = bool(v)

    def get_visible(self) -> bool:
        return self.visivel

    def set_text(self, t: str) -> None:
        self.texto = t

    def set_markup(self, t: str) -> None:
        self.texto = t


class _FakeBarra:
    def __init__(self) -> None:
        self.mensagens: list[str] = []

    def get_context_id(self, _key: str) -> int:
        return 1

    def pop(self, _ctx: int) -> None:
        if self.mensagens:
            self.mensagens.pop()

    def push(self, _ctx: int, msg: str) -> None:
        self.mensagens.append(msg)

    @property
    def ultima(self) -> str:
        return self.mensagens[-1] if self.mensagens else ""


@pytest.mark.asyncio
async def test_rumble_set_com_alvo_fora_da_mesa_responde_recusado() -> None:
    """A metade "e DIZ": a RESPOSTA, não a contagem de bytes."""
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
    from hefesto_dualsense4unix.daemon.subsystems.rumble import (
        MOTIVO_ALVO_FORA_DA_MESA,
        RUMBLE_RECUSADO_ALVO_AUSENTE,
    )

    escritas: list[tuple[int, int]] = []

    class _Controle:
        def alvo_de_output_ausente(self) -> str | None:
            return PECA

        def set_rumble(self, weak: int = 0, strong: int = 0) -> None:
            escritas.append((weak, strong))

    class _Config:
        rumble_active: tuple[int, int] | None = None
        rumble_active_uniq: str | None = None
        rumble_policy = "balanceado"

    class _Daemon:
        config = _Config()

        def is_native_mode(self) -> bool:
            return False

    class _Store:
        def __init__(self) -> None:
            self.travas: list[str] = []

        def mark_manual_trigger_active(self, categoria: str) -> None:
            self.travas.append(categoria)

    class _Servidor:
        controller = _Controle()
        daemon = _Daemon()
        store = _Store()

    servidor = _Servidor()
    handler = IpcHandlersMixin._handle_rumble_set.__get__(servidor, _Servidor)
    resposta = await handler({"weak": 160, "strong": 220})

    assert resposta["status"] == "recusado", (
        "o alvo está apontado e fora da mesa: o handler escreveu zero byte e "
        "respondeu que aplicou. A aba comemora o que não aconteceu — é o "
        "falso verde que a BROADCAST-PROIBIDO-01 mediu"
    )
    assert resposta["desfecho"] == RUMBLE_RECUSADO_ALVO_AUSENTE
    assert resposta["motivo"] == MOTIVO_ALVO_FORA_DA_MESA
    assert escritas == []
    assert servidor.daemon.config.rumble_active is None
    assert servidor.store.travas == []


def _estado(per_vpad: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    """Um ``state`` de ``daemon.state_full`` com só o que esta linha lê."""
    ff: dict[str, Any] = {
        "vpads": len(per_vpad),
        "plays": sum(int(i.get("ff_play_count", 0)) for i in per_vpad),
        "nao_nulos": sum(int(i.get("ff_nao_nulo_count", 0)) for i in per_vpad),
        "per_vpad": per_vpad,
    }
    ff.update(extra)
    return {"native_mode": False, "rumble_ff": ff}


