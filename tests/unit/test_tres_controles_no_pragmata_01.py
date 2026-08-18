"""TRES-CONTROLES-01 — o jogo via três controles, e um deles era espelho de espelho.

O QUE ELA VIU, EM 10/08/2026
============================
*"ok inputs ainda tão duplicado na hora do pragmata mesmo clicando lá em
entregar o controle pra steam"* — com a caixinha marcada, com a exceção armada e
com o físico escondido, o controle continuava dobrado.

O QUE O `/dev/input` DELA TINHA, MEDIDO COM O JOGO ABERTO
=========================================================
Quatro aparelhos para UM controle físico::

    event2   Sony ... DualSense Wireless Controller       054c:0ce6   físico
    event6   DualSense Wireless Controller (Hefesto P1)   054c:0df2   nosso vpad
    event21  Microsoft X-Box 360 pad 0                    28de:11ff   Steam Input
    event23  Microsoft X-Box 360 pad 1                    28de:11ff   Steam Input

O `steam` (pid 3699757) era o único processo com `/dev/uinput` aberto além do
`input-remapper` do sistema, e o `pad 0` nasceu no MESMO segundo em que o daemon
logou ``steam_input_excecao_ativada appid=3357650`` (02:13:40). São **dois**
espelhos porque o Steam Input enxerga **dois** controles — o físico e o nosso
vpad — e faz um Xbox virtual para cada.

O env que o wrapper entregava ao Pragmata escondia só o `054c:0ce6`. Os espelhos
da Valve nunca estiveram em lista nenhuma deste projeto (`28de` não aparecia em
uma linha sequer do caminho de launch), então o jogo ficava com TRÊS: o nosso
vpad e os dois espelhos.

POR QUE ISTO EXPLICA O QUE JÁ FUNCIONAVA
========================================
A regra desta casa é que hipótese tem de explicar o que funcionava antes, senão
é contorno. Explica: até 09/08 a exceção do Steam Input **suspendia o nosso
vpad**. O Steam via um controle só, criava um espelho só, e o jogo via um. A
decisão dela de 09/08 (ESCONDER-EM-VEZ-DE-SAIR-01) manteve o vpad de pé para não
derrubar o jogador 2 do co-op junto — fechou aquela conta e reabriu esta pelo
outro lado. O invariante da JOGO-01 (25/07) é o mesmo dos dois lados: *"a
allowlist muda QUAL dispositivo o jogo vê, nunca QUANTOS"*.

O QUE **NÃO** SE FEZ, E POR QUÊ
===============================
A saída elegante seria ``SDL_GAMECONTROLLER_IGNORE_DEVICES_EXCEPT`` ("aceite só
o nosso vpad"). Ela está ERRADA aqui, e o motivo é uma exigência dela: *"deve
ser universal, caso eu tenha 4 novos dual sense ou novos pro controler ou
8bitdo"*. Os externos são read-only por decisão de produto — numeramos e
acendemos o LED, não os adotamos —, então eles chegam ao jogo POR SI, e um
`_EXCEPT` os apagaria todos. Ver `test_o_except_mataria_os_externos_dela`.
"""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.daemon.launch_env import (
    PAR_DUALSENSE_FISICO,
    PAR_STEAM_INPUT_VIRTUAL,
    compose_env,
)

_IGNORE = "SDL_GAMECONTROLLER_IGNORE_DEVICES"
_DISABLE = "PROTON_DISABLE_HIDRAW"

#: O espelho virtual da Valve, no formato que o SDL lê.
_ESPELHO = "0x28de/0x11ff"
#: O DualSense físico dela.
_FISICO = "0x054c/0x0ce6"
#: O nosso vpad. NUNCA pode ser escondido — é ele que entrega o controle.
_NOSSO_VPAD = "0x054c/0x0df2"


def _env(**kw: object) -> dict[str, str]:
    base: dict[str, object] = {
        "native_mode": False,
        "emulation_enabled": True,
        "flavor": "dualsense",
        "backends": ["uhid"],
    }
    base.update(kw)
    return compose_env(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# A cura
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("flavor", ["dualsense", "xbox"])
def test_o_espelho_do_steam_input_e_escondido_do_jogo(flavor: str) -> None:
    """O caso dela, nas DUAS máscaras. Morde em `PAR_STEAM_INPUT_VIRTUAL`.

    Arranque para ver reprovar: tirar o par da lista do `_IGNORE_VALUE`. É
    exatamente o estado do produto até 10/08/2026 — e o resultado é o que ela
    relatou, com o jogo vendo três controles.

    Nas duas máscaras porque o Steam Input cria o espelho igual: ele enxerga o
    nosso vpad, não a nossa máscara.
    """
    backends = ["uhid"] if flavor == "dualsense" else ["uinput"]
    env = _env(flavor=flavor, backends=backends)
    assert _ESPELHO in env[_IGNORE].split(",")


def test_o_fisico_continua_escondido_junto() -> None:
    """A cura ACRESCENTA, não substitui — a razão do par original não mudou."""
    assert _FISICO in _env()[_IGNORE].split(",")


def test_o_nosso_vpad_nunca_entra_em_lista_nenhuma() -> None:
    """O contraponto que impede a cura de virar o defeito oposto.

    Esconder o `0df2` deixaria o jogo com ZERO controles — e a assimetria desta
    casa manda errar para o lado do duplicado, jamais para o do controle sumido.
    Vale para as duas variáveis: o `PROTON_DISABLE_HIDRAW` nega hidraw, e sem
    hidraw o vpad Edge perde rumble, gatilhos e lightbar do jogo.
    """
    env = _env()
    assert _NOSSO_VPAD not in env[_IGNORE].lower()
    assert _NOSSO_VPAD not in env[_DISABLE].lower()


def test_o_disable_hidraw_nao_ganhou_o_espelho() -> None:
    """Só o IGNORE cresceu, e a diferença é de mecanismo, não de descuido.

    O `PROTON_DISABLE_HIDRAW` faz o winebus NEGAR hidraw; o espelho da Valve não
    é um aparelho HID que o Proton entregue, é um evdev virtual. Pôr o par lá
    seria ruído numa variável cujo comentário no código diz, com todas as
    letras, que só o físico entra.

    Morde: acrescentar o par ao `_DISABLE_HIDRAW_VALUE` faz este teste reprovar.
    """
    env = _env()
    assert env[_DISABLE].lower() == _FISICO
    assert "0x28de" not in env[_DISABLE].lower()


# ---------------------------------------------------------------------------
# Os portões que a cura NÃO pode furar
# ---------------------------------------------------------------------------


def test_sem_cobertura_o_espelho_tambem_nao_e_escondido() -> None:
    """Duplicado > zero controles, e o espelho obedece ao MESMO invariante.

    Com dois DualSense físicos e um vpad vivo (o que o `EBUSY` de 02/08 produzia
    o tempo todo) o IGNORE inteiro é omitido — e tem de ser, senão um dos dois
    controles dela some do jogo. O espelho da Valve sai junto: é melhor ela ver
    um controle a mais do que jogar com um a menos.

    Morde: dar ao espelho um ramo PRÓPRIO, fora do `cobertura_total`, faz este
    teste reprovar. Foi por isso que o par entrou no valor, e não num `if` novo.
    """
    env = _env(fisicos=2, backends=["uhid"])
    assert _IGNORE not in env


def test_no_modo_nativo_nao_se_esconde_nada() -> None:
    """A Conexão Nativa expõe o físico de propósito — nada de IGNORE ali."""
    assert _IGNORE not in _env(native_mode=True)


def test_com_a_emulacao_desligada_nao_se_esconde_nada() -> None:
    """Sem vpad para devolver o controle, esconder é ficar sem controle."""
    assert _IGNORE not in _env(emulation_enabled=False)
    assert _IGNORE not in _env(backends=[])


# ---------------------------------------------------------------------------
# A saída que foi RECUSADA, e o motivo dela por escrito
# ---------------------------------------------------------------------------


def test_o_except_mataria_os_externos_dela() -> None:
    """Por que não `SDL_GAMECONTROLLER_IGNORE_DEVICES_EXCEPT`.

    A variável existe e resolveria em uma linha ("aceite só o nosso vpad"). Este
    teste TRAVA a decisão de não usá-la, porque ela reaparece como ideia boa
    toda vez que alguém reencontra o problema.

    O motivo é a exigência dela: *"deve ser universal, caso eu tenha 4 novos
    dual sense ou novos pro controler ou 8bitdo"*. Um Pro Controller ou um
    8BitDo chegam ao jogo POR SI — o Hefesto os numera e acende o LED, mas não
    os adota —, então um `_EXCEPT` com o nosso VID/PID os apagaria da mesa.

    Se um dia o produto ADOTAR os externos com vpad próprio (a `E4` da
    LUGAR-À-MESA-01), esta decisão caduca e este teste ganha uma nota datada.
    """
    env = _env()
    assert "SDL_GAMECONTROLLER_IGNORE_DEVICES_EXCEPT" not in env


def test_o_par_da_valve_nao_e_o_steam_controller_fisico_dela() -> None:
    """`28de:11ff` é o espelho virtual; o aparelho físico da Valve é outro PID.

    Sem esta separação a cura esconderia um controle de verdade — o erro exato
    que o `test_par_fora_da_faixa` da bateria irmã existe para evitar. O
    `28de:1142` já está nomeado como "Steam Controller" em
    `app/actions/external_controllers.py`, e nenhum dos dois pares físicos entra
    aqui.
    """
    from hefesto_dualsense4unix.app.actions.external_controllers import (
        _TYPE_BY_VIDPID,
    )

    assert PAR_STEAM_INPUT_VIRTUAL == (0x28DE, 0x11FF)
    assert PAR_STEAM_INPUT_VIRTUAL != PAR_DUALSENSE_FISICO
    valor = _env()[_IGNORE].lower()
    for chave in _TYPE_BY_VIDPID:
        if not chave.startswith("28de:"):
            continue
        vid, _, pid = chave.partition(":")
        assert f"0x{vid}/0x{pid}" not in valor, (
            f"{chave} é um controle FÍSICO da Valve e não pode ser escondido"
        )
