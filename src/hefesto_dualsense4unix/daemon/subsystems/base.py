"""Protocol Subsystem — interface mínima para subsystems do daemon.

Cada subsystem deve implementar start(), stop() e is_enabled().
O atributo `name` identifica o subsystem nos logs.

E O «CONTROLE N» DOS NÓS DE SOM, que é a outra coisa que mora aqui
------------------------------------------------------------------
TRES-CONTAS-PARA-UM-NUMERO-01 (12/09/2026). Os dois nós que ela lê na lista de
som do sistema — «Alto-falante do Controle N» e «Microfone do Controle N» —
eram batizados por DUAS cópias da mesma regra (uma em `alto_falante.py`, outra
em `bt_mic.py`), e essa regra era uma TERCEIRA conta de «Controle N», diferente
da que a tela imprime no cartão. Agora as duas chamam
:func:`numero_do_assento_na_mesa`, que **não tem conta nenhuma**: ela pergunta
ao dono.
"""
from __future__ import annotations

import contextlib
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.context import DaemonContext
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig


#: Doze hex minúsculos sem separador — a chave de `norm_mac`. Um `uniq` que não
#: chega a este tamanho não é endereço, e sem endereço não há de quem seja o nó.
UNIQ_HEX = 12


@runtime_checkable
class Subsystem(Protocol):
    """Interface mínima que todo subsystem do daemon deve satisfazer."""

    name: str

    async def start(self, ctx: DaemonContext) -> None:
        """Inicia o subsystem com o contexto fornecido."""
        ...

    async def stop(self) -> None:
        """Para o subsystem de forma limpa e idempotente."""
        ...

    def is_enabled(self, config: DaemonConfig) -> bool:
        """Retorna True se o subsystem deve ser ativado com a config atual."""
        ...


def slot_de_sessao(daemon: Any, chave: str) -> int | None:
    """O ``player_slot`` deste controle, PERGUNTADO ao dono dele.

    O dono é o ``identity_registry`` (``daemon/subsystems/identity.py``), e a
    pergunta é a MESMA que a interface faz pelo IPC —
    ``ipc_handlers._player_slot_for``: ``slot_for(uniq, assign=False)``, leitura
    pura. ``assign=False`` não é detalhe: expor estado nunca pode ALOCAR lugar
    na fila, senão nomear um nó de som mudaria a numeração da mesa dela.

    **É o DAEMON que entra, não o registro**, e a razão é de ordem medida em
    12/09/2026: ``Daemon.run()`` chama ``_safe_start("bt_mic", …)`` e
    ``_safe_start("alto_falante", …)`` **antes** de ``_wire_identity_registry()``.
    Guardar o registro por VALOR no ``start`` congelaria ``None`` para a sessão
    inteira — o subsystem responderia para sempre pelo mundo de antes da fiação.
    Pelo daemon a leitura é tardia, e é o mesmo caminho que
    ``external_identity`` usa (``getattr(self._daemon, "identity_registry",
    None)``).

    ``None`` é *"o dono não tem opinião"* — daemon ausente (dublê de teste),
    backend Fake (o registro fica deliberadamente sem fiação), ``uniq`` de vpad
    (D9: o vpad jamais é "Controle N") ou controle que ainda não estreou na
    fila. Nunca um número inventado.
    """
    registro = getattr(daemon, "identity_registry", None) if daemon is not None else None
    slot_for = getattr(registro, "slot_for", None) if registro is not None else None
    if not callable(slot_for):
        return None
    bruto: Any = None
    with contextlib.suppress(Exception):
        bruto = slot_for(chave, assign=False)
    if isinstance(bruto, int) and not isinstance(bruto, bool):
        return bruto
    return None


def numero_do_assento_na_mesa(
    conectados: Sequence[dict[str, Any]],
    uniq: str,
    *,
    daemon: Any = None,
) -> int | None:
    """O «Controle N» deste controle — a conta DA CASA, alcançada pelo daemon.

    ESTA FUNÇÃO NÃO TEM CONTA PRÓPRIA, e é isso que ela entrega. Havia TRÊS
    números para o mesmo «Controle N» (TRES-CONTAS-PARA-UM-NUMERO-01):

    ======================================== ==================================
    ``app/actions/base.numero_do_controle``  ``player_slot``, senão ``index+1``
    ``daemon/ipc_handlers._numero_de_exibicao`` a MESMA regra, copiada porque
                                             ``base.py`` importa ``gi`` e o
                                             daemon não pode
    ``*.numero_do_assento`` (09/09)          a posição entre os CONECTADOS
    ======================================== ==================================

    A terceira MORREU aqui. O que sobra é a conta da casa, com um dono só do
    lado do daemon (``_numero_de_exibicao``), e as duas primeiras continuam
    amarradas pelo portão que já existia
    (``tests/unit/test_mesa_cheia_11_a_janela_conta_quatro.py``). **A cura não
    mexeu na conta da casa — ela a ALCANÇOU**, que é o que a sprint pedia.

    A DIVERGÊNCIA QUE ISTO MATA, medida na mesa dela em 09/09/2026 às 22h::

        pactl list sources → Description: Microfone do Controle 2   ← o daemon
        a tela             → P1 • White • cabo                      ← o cartão

    Dois números para o mesmo aparelho em duas janelas ao mesmo tempo, que é
    exatamente o defeito que o ``numero_do_controle`` foi criado para matar. A
    causa não era a desconexão de ninguém: com os quatro na mesa, o
    ``player_slot`` é a ordem da FILA (``[4,1,3,2]`` no payload real que a
    MESA-CHEIA-11 mede) e a posição entre os conectados é a ordem dos HANDLES.
    Listas diferentes sobre a mesma mesa.

    POR QUE O ``player_slot`` NÃO VEM DE GRAÇA: ``describe_controllers()`` não
    o devolve — ele é do ``identity_registry``, e é o IPC que o carimba na
    entrada antes de publicá-la
    (``ipc_handlers.IpcHandlersMixin._enrich_controllers_per_controller``). Aqui ele é
    carimbado do mesmo jeito, na MESMA entrada, pelo mesmo caminho de leitura
    pura (:func:`slot_de_sessao`), e só então a regra da casa decide.

    **A INVARIANTE CONTINUA:** número só para quem está NA MESA. ``conectados``
    já vem filtrado por ``connected``, e a busca é dentro dele — então um
    controle desligado não ganha nome, mesmo que o registro guarde um lugar na
    fila para ele (``slot_for`` com ``assign=False`` responde a COLOCAÇÃO que
    um ausente teria se voltasse; publicar um nó por essa resposta poria na
    lista de som dela um «Microfone do Controle 3» de um controle que não está
    lá).

    Sem daemon, sem registro, ou controle sem lugar na fila, cai no
    ``index + 1`` da regra da casa — que é o número que a tela imprime no
    cartão nessa mesma situação, pela mesma razão. ``None`` é *"não sei"*, e o
    rótulo nasce sem número; nunca com um inventado.
    """
    # O DONO DA REGRA É O DO IPC, e o import é tardio de propósito: importar um
    # subsystem não pode arrastar o servidor IPC inteiro. Ele é privado ao
    # módulo dele, e copiá-lo aqui seria a QUARTA conta — o que esta sprint
    # existe para não fazer. Há régua que reprova se ele sair de lá:
    # `test_o_som_por_controle_cai_em_cada_um.py`.
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
    from hefesto_dualsense4unix.daemon.ipc_handlers import _numero_de_exibicao

    chave = norm_mac(str(uniq)) or ""
    if len(chave) != UNIQ_HEX:
        return None
    for item in conectados:
        if (norm_mac(str(item.get("uniq") or "")) or "") != chave:
            continue
        entrada = dict(item)
        if not isinstance(entrada.get("player_slot"), int) or isinstance(
            entrada.get("player_slot"), bool
        ):
            entrada["player_slot"] = slot_de_sessao(daemon, chave)
        return _numero_de_exibicao(entrada)
    return None


__all__ = [
    "UNIQ_HEX",
    "Subsystem",
    "numero_do_assento_na_mesa",
    "slot_de_sessao",
]
