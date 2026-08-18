"""Os botões e o D-pad do Nintendo Pro chegam ao vpad do jogador secundário.

O QUE ESTE ARQUIVO GUARDA
-------------------------
O caminho que o Hefesto usa para o Pro: o `EvdevReader` — o MESMO que o co-op
instancia para o jogador secundário (`daemon/subsystems/coop.py`, o
`_SecondaryPlayer` com `evdev_path`) — traduzindo o nó evdev do controle em
nomes canônicos da casa. Duas peças, e as duas são cura:

- `EvdevReader.BUTTON_MAP`: o keycode do kernel vira `cross`/`circle`/… Sem a
  entrada, `_keycode_name` devolve `None` e o botão **some** — sem erro, sem
  log, sem nada;
- `EvdevReader._refresh_dpad_buttons`: no Pro o D-pad NÃO é botão, é o par de
  eixos `ABS_HAT0X`/`ABS_HAT0Y` (o driver publica `JC_BTN_UP/DOWN/LEFT/RIGHT`
  como hat, e o mapa de canais registra isso na coluna `evdev` da linha
  `entrada.botoes@pro`). Sem a conversão, o D-pad inteiro fica mudo para o
  produto enquanto o nó evdev continua respondendo — a AUSÊNCIA de dado, que é
  a armadilha da casa.

POR QUE ELE EXISTE, e o que ele NÃO prova
-----------------------------------------
A linha `entrada.botoes@pro` do mapa de canais afirma `radio_aciona = sim` com
`radio_de_onde_sei = medido`: 536 relatórios em 6,0 s, TODOS `0x30`, TODOS de 49
bytes (`docs/protocol/externos-referencia-canonica.md` §3.3, 07/08/2026). A
mesma linha registra que **por rádio o envelope é IDÊNTICO ao do cabo** — o
Bluetooth não muda o report do Pro, ao contrário do DualSense.

Este arquivo NÃO mede o fio: ele não sabe se o report chega por rádio. Ele
guarda a metade que é NOSSA — se o report chega e a tradução some, o dedo dela
não vira nada no jogo, e a suíte inteira continua verde. Medir o fio é bancada.

MORDE? Apague uma linha do `BUTTON_MAP` (ou o corpo do `_refresh_dpad_buttons`)
e estes testes reprovam nomeando o botão que sumiu.

MORDIDA PROVADA (15/08/2026, com o `src/` COPIADO para fora da árvore e o
`PYTHONPATH` apontado para a cópia — a árvore de trabalho nunca foi mutada):
ver o bloco `MORDIDA` de cada teste e a coluna `mordida_provada_em` da linha
`entrada.botoes@pro` do mapa de canais.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evdev import AbsInfo, ecodes

from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

#: A faixa do hat, como o `hid-nintendo` a publica para o Pro (-1, 0, +1).
FAIXA_HAT = AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)
#: Os analógicos do Pro têm sinal (medido em 06/08/2026 na mesa dela).
FAIXA_PRO = AbsInfo(value=0, min=-32767, max=32767, fuzz=250, flat=500, resolution=0)

#: Os treze botões DIGITAIS do Pro, na ordem em que a linha `entrada.botoes@pro`
#: os lista, e o nome canônico que a casa dá a cada um. O par vem do
#: `BUTTON_MAP`; a lista existe para que APAGAR uma entrada do mapa reprove aqui
#: com o nome do botão, em vez de passar por comparação de conjunto vazio.
BOTOES_DO_PRO: tuple[tuple[str, str], ...] = (
    ("BTN_SOUTH", "cross"),  # B do Pro
    ("BTN_EAST", "circle"),  # A
    ("BTN_NORTH", "triangle"),  # X
    ("BTN_WEST", "square"),  # Y
    ("BTN_TL", "l1"),  # L
    ("BTN_TR", "r1"),  # R
    ("BTN_TL2", "l2_btn"),  # ZL — digital no Pro
    ("BTN_TR2", "r2_btn"),  # ZR — digital no Pro
    ("BTN_SELECT", "create"),  # o botão de "menos" do Pro
    ("BTN_START", "options"),  # o botão de "mais" do Pro
    ("BTN_MODE", "ps"),  # Home
    ("BTN_THUMBL", "l3"),
    ("BTN_THUMBR", "r3"),
)


def _caps_pro() -> dict[int, Any]:
    """Caps do Pro: os treze botões, os quatro eixos com sinal e o hat.

    Sem `ABS_Z`/`ABS_RZ` — o ZL/ZR do Pro é botão, não eixo (a linha
    `gatilho.analogico@pro` do mapa é sobre exatamente isso).
    """
    return {
        ecodes.EV_KEY: [getattr(ecodes, nome) for nome, _ in BOTOES_DO_PRO],
        ecodes.EV_ABS: [
            (ecodes.ABS_X, FAIXA_PRO),
            (ecodes.ABS_Y, FAIXA_PRO),
            (ecodes.ABS_RX, FAIXA_PRO),
            (ecodes.ABS_RY, FAIXA_PRO),
            (ecodes.ABS_HAT0X, FAIXA_HAT),
            (ecodes.ABS_HAT0Y, FAIXA_HAT),
        ],
    }


class _DevFalso:
    """Só o que `_on_device_opened` toca: o `capabilities()` do node aberto."""

    def __init__(self, caps: Any) -> None:
        self._caps = caps

    def capabilities(self) -> Any:
        return self._caps


def _reader_do_pro() -> EvdevReader:
    reader = EvdevReader(device_path=Path("/dev/input/event999"))
    reader._on_device_opened(_DevFalso(_caps_pro()))
    return reader


def test_cada_botao_digital_do_pro_vira_o_nome_canonico_da_casa() -> None:
    """Apertar e soltar os treze, um a um, pelo caminho real do reader.

    MORDIDA: apague qualquer linha de `EvdevReader.BUTTON_MAP` e este teste
    reprova nomeando o botão — `_keycode_name` passa a devolver `None` e o
    aperto vira silêncio (o nó evdev continua respondendo; quem some é o dado).
    """
    reader = _reader_do_pro()
    for evdev_nome, nome_da_casa in BOTOES_DO_PRO:
        code = getattr(ecodes, evdev_nome)
        reader._handle_key(code, 1, ecodes)
        assert nome_da_casa in reader.snapshot().buttons_pressed, (
            f"{evdev_nome} do Pro não virou `{nome_da_casa}`: sem a entrada no "
            "BUTTON_MAP o botão SOME sem erro nenhum, e o jogador secundário "
            "fica com um botão morto"
        )
        reader._handle_key(code, 0, ecodes)
        assert nome_da_casa not in reader.snapshot().buttons_pressed, (
            f"`{nome_da_casa}` ficou preso depois de soltar {evdev_nome}"
        )


def test_o_dpad_do_pro_vem_do_hat_e_nao_de_botao() -> None:
    """As quatro direções chegam por `ABS_HAT0X`/`ABS_HAT0Y`, os dois sentidos.

    MORDIDA: apague o corpo de `_refresh_dpad_buttons` (ou o ramo `ABS_HAT0*` de
    `_handle_abs`) e este teste reprova nas quatro direções. No Pro o D-pad
    inteiro depende disto: ele não publica `BTN_DPAD_*`.
    """
    reader = _reader_do_pro()
    casos = (
        (ecodes.ABS_HAT0Y, -1, "dpad_up"),
        (ecodes.ABS_HAT0Y, 1, "dpad_down"),
        (ecodes.ABS_HAT0X, -1, "dpad_left"),
        (ecodes.ABS_HAT0X, 1, "dpad_right"),
    )
    for eixo, valor, direcao in casos:
        reader._handle_abs(eixo, valor, ecodes)
        assert direcao in reader.snapshot().buttons_pressed, (
            f"o hat em {valor} não virou `{direcao}`: o D-pad do Pro é hat, e "
            "sem a conversão ele fica MUDO para o produto"
        )
        reader._handle_abs(eixo, 0, ecodes)
        assert direcao not in reader.snapshot().buttons_pressed, (
            f"`{direcao}` ficou preso depois do hat voltar ao centro"
        )


def test_o_hat_solta_a_direcao_oposta_em_vez_de_somar() -> None:
    """Ir de esquerda para direita sem passar pelo centro não pode deixar as
    DUAS pressionadas — no hat isso é um evento só, não dois botões."""
    reader = _reader_do_pro()
    reader._handle_abs(ecodes.ABS_HAT0X, -1, ecodes)
    reader._handle_abs(ecodes.ABS_HAT0X, 1, ecodes)
    pressionados = reader.snapshot().buttons_pressed
    assert "dpad_right" in pressionados
    assert "dpad_left" not in pressionados, (
        "o D-pad ficou com as duas direções do mesmo eixo pressionadas"
    )
