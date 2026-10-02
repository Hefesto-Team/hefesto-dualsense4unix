"""no_do_vpad.py — qual nó do kernel é o gamepad virtual deste produto.

POR QUE ESTE MÓDULO EXISTE (QUEM-SEGURA-O-NOSSO-NO-01, 20/08/2026)
------------------------------------------------------------------
O `daemon.state_full` publica ~20 contadores por vpad e **não diz qual nó do
kernel aquele vpad é**. Consequência medida: todo instrumento de bancada que
precisa da resposta a reimplementa — `scripts/ensaios/quem_o_jogo_abre.py`
casa por *regex de caminho*, o `emulation_actions` da janela casa por prefixo
de nome, e o `identidade_do_vpad.py` de `scripts/` casa pelo `uevent` do pai.
São três réguas para o mesmo fato, e a lição desta casa é que uma delas
envelhece calada.

Aqui a resposta sai **do produto**, que é o único que sabe sem adivinhar: ele
carimbou o `phys` e o `uniq` no `UHID_CREATE2` e conhece o nome que pediu ao
kernel. O que este módulo faz é traduzir esse carimbo em `(/dev/input/eventN,
/dev/hidrawM)` e nos **inodes** dos dois.

POR QUE O INODE, E NÃO O CAMINHO
---------------------------------
`/dev/input/eventN` é um número de fila, não uma identidade: basta um controle
cair e voltar para o `event22` de agora ser o `event19` de daqui a pouco — e
para o `event22` passar a ser de OUTRO aparelho. Quem casa por caminho afirma
com confiança sobre o device errado.

O inode é a identidade que o `/proc/<pid>/fd/<n>` de um jogo carrega: o
`os.stat` do link resolve no MESMO inode do nó, e `os.stat` **não abre nada** —
não dispara `UHID_OPEN`, não arma o modo jogo, não entra na conta de quem
fecha por último. É por isso que o inode viaja no payload junto com o caminho:
publicar só o caminho obrigaria quem lê a fazer o `stat` por conta própria, e
entre o caminho publicado e o `stat` de quem lê cabe exatamente a renumeração
que este módulo existe para não sofrer.

O QUE ESTE MÓDULO NÃO OLHA
---------------------------
**VID/PID e barramento.** O vpad forja `054c:0df2` (DualSense Edge) no
barramento `0003` de propósito, e forja bem. Quem casa por vid/pid está a um
DualSense Edge de verdade de distância de medir o aparelho errado.

**"mora sob `/devices/virtual/`".** Armadilha paga em 11/08/2026: com BlueZ
>= 5.73 o `bluetoothd` cria o HID dos DualSense FÍSICOS de rádio também por
`/dev/uhid`, no mesmíssimo lugar. Topologia de sysfs não separa nada aqui.

A régua é a do `scripts/identidade_do_vpad.py`, e é a mesma: o `uniq`
(`02:fe:…`, faixa localmente administrada, que por definição não
colide com endereço de fábrica) e o `phys` (`hefesto-vpad`, uma palavra que só
este produto escreve). Aqui o `uniq` vem do PRÓPRIO objeto vpad, não de uma
heurística: o produto pergunta a si mesmo.

DE ONDE SAI CADA NÚMERO (a procedência, declarada)
---------------------------------------------------
- `evdev`: varredura de `/sys/class/input/event*/device/uniq` (o
  `hid_playstation` copia `hdev->uniq` para o `input_dev` —
  `assets/dkms/hid-playstation/hid-playstation.c:704`). Sem `uniq` (caminho
  uinput, que é evdev puro e não tem `uniq`), a varredura casa pelo `name`
  exato — e, se mais de um nó carregar esse mesmo nome, ela RECUSA em vez de
  escolher: no co-op de uinput os vpads são homônimos, e apontar um deles
  seria publicar o nó de P1 dentro do bloco de P2.
- `hidraw`: do nó de entrada escolhido, sobe dois níveis de sysfs
  (`.../<device HID>/input/inputM`) e lê `<device HID>/hidraw/`. **Confirmado**
  contra o `uevent` daquele device HID (`HID_UNIQ`/`HID_PHYS`) antes de ser
  afirmado — segunda régua, e discordância vira `None`, nunca um palpite.
- `ino` e `hidraw_ino`: `os.stat` dos dois nós de `/dev`, no mesmo instante em
  que os caminhos foram resolvidos.

Tudo o que não se resolve sai `None`. Este módulo nunca chuta: um campo `None`
diz "não sei", e "não sei" vale mais do que um caminho plausível e errado.
"""

from __future__ import annotations

import os
from typing import Any

from hefesto_dualsense4unix.integrations.uhid_gamepad import VPAD_HID_PHYS

RAIZ_CLASS_INPUT = "/sys/class/input"

RAIZ_DEV_INPUT = "/dev/input"
RAIZ_DEV = "/dev"

NO_DESCONHECIDO: dict[str, Any] = {
    "evdev": None,
    "hidraw": None,
    "ino": None,
    "hidraw_ino": None,
}


def _texto_do_sysfs(caminho: str) -> str:
    """Conteúdo de um atributo de sysfs, sem espaços nas pontas ("" se ilegível).

    Nó que sumiu entre o `listdir` e a leitura é o caso NORMAL aqui, não a
    exceção: o co-op cria e destrói vpads, e a varredura roda a partir do
    `state_full`. Ilegível vira "", que não casa com nada.
    """
    try:
        with open(caminho, encoding="utf-8", errors="replace") as arquivo:
            return arquivo.read().strip()
    except OSError:
        return ""


def _campos_do_uevent(texto: str) -> dict[str, str]:
    """As linhas `CHAVE=valor` de um `uevent` como dicionário."""
    return dict(
        linha.split("=", 1) for linha in texto.splitlines() if "=" in linha
    )


def _numero_do_evento(entrada: str) -> int:
    """`event22` -> 22. Ordenar por texto poria `event9` depois de `event22`."""
    try:
        return int(entrada[len("event") :])
    except ValueError:
        return 1 << 30


def _candidatos(
    *, uniq: str, nome: str, raiz_class_input: str
) -> list[tuple[int, str, str]]:
    """Os nós de entrada que são ESTE vpad: `(número, eventN, nome do nó)`.

    Um DualSense — e portanto o nosso vpad, que se apresenta como um — publica
    TRÊS nós de entrada com o MESMO `uniq`: o gamepad, o `… Touchpad` e o
    `… Motion Sensors` (`ps_allocate_input_dev`). Casar por `uniq` e parar no
    primeiro daria o nó do touchpad em metade das vezes; por isso a lista
    inteira volta e o desempate é de quem chama.
    """
    achados: list[tuple[int, str, str]] = []
    try:
        entradas = os.listdir(raiz_class_input)
    except OSError:
        return achados
    for entrada in entradas:
        if not entrada.startswith("event"):
            continue
        base = os.path.join(raiz_class_input, entrada, "device")
        if uniq:
            if _texto_do_sysfs(os.path.join(base, "uniq")).casefold() != uniq:
                continue
            nome_do_no = _texto_do_sysfs(os.path.join(base, "name"))
        else:
            nome_do_no = _texto_do_sysfs(os.path.join(base, "name"))
            if not nome or nome_do_no != nome:
                continue
        achados.append((_numero_do_evento(entrada), entrada, nome_do_no))
    return sorted(achados)


def _escolher(candidatos: list[tuple[int, str, str]], nome: str) -> str | None:
    """Qual dos nós do aparelho é o do JOGO — o gamepad, não o touchpad."""
    if not candidatos:
        return None
    if nome:
        for _numero, entrada, nome_do_no in candidatos:
            if nome_do_no == nome:
                return entrada
    return candidatos[0][1]


def _hidraw_do_no(
    *, entrada: str, uniq: str, raiz_class_input: str
) -> str | None:
    """O `hidrawN` do device HID dono deste nó de entrada, CONFIRMADO."""
    dir_do_no = os.path.join(raiz_class_input, entrada, "device")
    try:
        alvo = os.path.realpath(dir_do_no)
    except OSError:
        return None
    pai = os.path.dirname(alvo)
    if os.path.basename(pai) != "input":
        return None
    dir_hid = os.path.dirname(pai)
    campos = _campos_do_uevent(_texto_do_sysfs(os.path.join(dir_hid, "uevent")))
    if not campos:
        return None
    hid_uniq = campos.get("HID_UNIQ", "").strip().casefold()
    hid_phys = campos.get("HID_PHYS", "").strip().casefold()
    confirmado = hid_phys.startswith(VPAD_HID_PHYS) or (
        bool(uniq) and hid_uniq == uniq
    )
    if not confirmado:
        return None
    try:
        nos = sorted(os.listdir(os.path.join(dir_hid, "hidraw")))
    except OSError:
        return None
    for no in nos:
        if no.startswith("hidraw"):
            return no
    return None


def _inode(caminho: str) -> int | None:
    """`st_ino` do nó, ou `None`. `os.stat` NÃO abre o device."""
    try:
        return os.stat(caminho).st_ino
    except OSError:
        return None


def resolver_no_do_vpad(
    *,
    uniq: str | None,
    nome: str | None,
    raiz_class_input: str | None = None,
    raiz_dev_input: str | None = None,
    raiz_dev: str | None = None,
) -> dict[str, Any]:
    """`{evdev, hidraw, ino, hidraw_ino}` do vpad com este `uniq`/`nome`."""
    raiz_class_input = (
        RAIZ_CLASS_INPUT if raiz_class_input is None else raiz_class_input
    )
    raiz_dev_input = RAIZ_DEV_INPUT if raiz_dev_input is None else raiz_dev_input
    raiz_dev = RAIZ_DEV if raiz_dev is None else raiz_dev
    uniq_norm = (uniq or "").strip().casefold()
    nome_norm = (nome or "").strip()
    if not uniq_norm and not nome_norm:
        return dict(NO_DESCONHECIDO)
    candidatos = _candidatos(
        uniq=uniq_norm, nome=nome_norm, raiz_class_input=raiz_class_input
    )
    if not uniq_norm and len(candidatos) > 1:
        # `state_full` passa a publicar o inode de P1 dentro do bloco de P2 —
        return dict(NO_DESCONHECIDO)
    entrada = _escolher(candidatos, nome_norm)
    if entrada is None:
        return dict(NO_DESCONHECIDO)
    evdev = os.path.join(raiz_dev_input, entrada)
    hidraw_no = _hidraw_do_no(
        entrada=entrada, uniq=uniq_norm, raiz_class_input=raiz_class_input
    )
    hidraw = os.path.join(raiz_dev, hidraw_no) if hidraw_no else None
    return {
        "evdev": evdev,
        "hidraw": hidraw,
        "ino": _inode(evdev),
        "hidraw_ino": _inode(hidraw) if hidraw else None,
    }


def no_ainda_vale(no: dict[str, Any]) -> bool:
    """O bloco cacheado ainda descreve o MESMO nó? (`stat` de 1 syscall)"""
    evdev = no.get("evdev")
    if not isinstance(evdev, str) or not evdev:
        return True
    if _inode(evdev) != no.get("ino"):
        return False
    hidraw = no.get("hidraw")
    if isinstance(hidraw, str) and hidraw:
        return _inode(hidraw) == no.get("hidraw_ino")
    return True


__all__ = [
    "NO_DESCONHECIDO",
    "RAIZ_CLASS_INPUT",
    "RAIZ_DEV",
    "RAIZ_DEV_INPUT",
    "no_ainda_vale",
    "resolver_no_do_vpad",
]
