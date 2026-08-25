"""mesa_do_mockup.py — a mesa dela, do jeito que o mockup a declara.

Transcrição das constantes de
``docs/process/sprints/2026-08-24-ABA-CONEXOES/mockup/mapa-das-portas.html``:
os oito aparelhos, as três faces, o mapa de 8 entradas de 16 e as duas leituras
reais de 24/08/2026 (20h15 e 22h50).

**Isto é cópia, e cópia envelhece — de propósito, com barulho.** O
``test_arranjo_da_mesa_bate_com_o_mockup.py`` compara a saída do Python com a do
mockup rodado em ``node``: no dia em que uma destas constantes divergir do
arquivo, o oráculo muda e o teste reprova nomeando o cenário. É o barulho que se
quer, não a sobrevivência silenciosa de duas verdades.

**Nada aqui é endereço de rádio.** O motor trabalha com caminho de barramento
(``3-1.2``), que é topologia do USB e não identifica aparelho nenhum. Serial e
MAC não entram neste módulo, nem nos testes que o usam.
"""

from __future__ import annotations

from hefesto_dualsense4unix.integrations.arranjo_da_mesa import (
    Aparelho,
    Controle,
    Entrada,
    Face,
    Leitura,
    Mapa,
    Mesa,
)

APARELHOS: tuple[Aparelho, ...] = (
    Aparelho("bt-a", "Bluetooth", "TP-Link UB500", "bt"),
    Aparelho("bt-b", "Bluetooth", "TP-Link UB500", "bt"),
    Aparelho("bt-c", "Bluetooth", "TP-Link UB500", "bt"),
    Aparelho("wifi", "Wi-Fi", "Archer T3U", "wifi"),
    Aparelho("webcam", "Webcam", "Logitech C920", "webcam"),
    Aparelho("teclado", "Teclado", "Receptor 2,4 GHz", "teclado"),
    Aparelho("mouse", "Mouse", "Receptor 2,4 GHz", "mouse"),
    Aparelho("hub", "Hub", "TP-Link UH700", "hub"),
)

FACES: tuple[Face, ...] = (
    Face(
        nome="Frente do gabinete", regiao="pc", perto=True,
        entradas=(
            Entrada("1", usb=2, onde="pc", par="2"),
            Entrada("2", usb=2, onde="pc", par="1"),
        ),
    ),
    Face(
        nome="Traseira", regiao="pc",
        entradas=(
            Entrada("3", usb=3, onde="pc", par="4"),
            Entrada("4", usb=3, onde="pc", par="3"),
            Entrada("5", usb=3, onde="pc", par="6"),
            Entrada("6", usb=3, onde="pc", par="5"),
            Entrada("7", usb=2, onde="pc", par="8"),
            Entrada("8", usb=2, onde="pc", par="7"),
        ),
    ),
    Face(
        nome="Hub, no alto do rack", regiao="hub", alto=True,
        entradas=(
            Entrada("9", usb=3, onde="hub", pos=1, par="10"),
            Entrada("10", usb=3, onde="hub", pos=2, par="9"),
            Entrada("11", usb=3, onde="hub", pos=3, par="12"),
            Entrada("12", usb=3, onde="hub", pos=4, par="11"),
            Entrada("13", usb=3, onde="hub", pos=5, par="14"),
            Entrada("14", usb=3, onde="hub", pos=6, par="13"),
            Entrada("15", usb=3, onde="hub", pos=7,
                    filho=Entrada("15a", usb=3, onde="hub", pos=9, esticada=True)),
        ),
    ),
)

#: ela declarou 8 das 16 entradas — só as que tinham algo no dia
MAPA: Mapa = {
    "1": "1-3", "4": "3-1", "5": "3-3", "6": "3-4",
    "9": "3-1.2", "11": "4-1.1.2", "13": "3-1.4", "15a": "3-1.1.4",
}

#: 20h15 de 24/08/2026 — antes de ela mexer nos cabos
LEITURA_ANTES: Leitura = {
    "mouse": "1-3", "hub": "3-1", "bt-c": "3-3", "webcam": "3-4",
    "bt-a": "3-1.2", "wifi": "4-1.1.2", "teclado": "3-1.4", "bt-b": "3-1.1.4",
}

#: 22h50 de 24/08/2026 — depois dos movimentos dela
LEITURA_AGORA: Leitura = {
    "teclado": "1-3", "webcam": "1-4", "mouse": "1-6", "hub": "3-1",
    "bt-c": "3-1.1.1", "bt-b": "3-1.1.4", "bt-a": "3-1.2", "wifi": "4-2",
}

CONTROLES: tuple[Controle, ...] = (
    Controle("Jogador 1", mic=True, onde="bt-a"),
    Controle("Jogador 2", mic=True, onde="bt-a"),
    Controle("Jogador 3", mic=True, onde="bt-b"),
    Controle("Jogador 4", mic=True, onde="bt-b"),
)

# ── A MESA DELA ÀS 02h36 DE 25/08/2026 ──────────────────────────────────
#
# O hub saiu do barramento e levou os três adaptadores Bluetooth com ele. Sobrou
# teclado em `1-3`, DualSense por cabo em `1-4`, mouse em `1-6` e Wi-Fi em `4-4`.
# É estado de primeira classe do motor, não borda: sem hub não há topologia de
# hub para deduzir, e sem adaptador não cabe controle nenhum.

SEM_HUB_APARELHOS: tuple[Aparelho, ...] = (
    Aparelho("wifi", "Wi-Fi", "Archer T3U", "wifi"),
    Aparelho("teclado", "Teclado", "Receptor 2,4 GHz", "teclado"),
    Aparelho("mouse", "Mouse", "Receptor 2,4 GHz", "mouse"),
)

SEM_HUB_LEITURA: Leitura = {"teclado": "1-3", "mouse": "1-6", "wifi": "4-4"}


def mesa(
    mapa: Mapa | None = None,
    leitura: Leitura | None = None,
    aparelhos: tuple[Aparelho, ...] | None = None,
) -> Mesa:
    """A mesa do mockup, com o que você quiser trocar."""
    return Mesa(
        aparelhos=APARELHOS if aparelhos is None else aparelhos,
        faces=FACES,
        mapa=MAPA if mapa is None else mapa,
        leitura=LEITURA_AGORA if leitura is None else leitura,
    )


def mesa_sem_hub() -> Mesa:
    """A mesa de agora: o hub fora do barramento, os três dongles com ele."""
    return mesa(aparelhos=SEM_HUB_APARELHOS, leitura=SEM_HUB_LEITURA)
