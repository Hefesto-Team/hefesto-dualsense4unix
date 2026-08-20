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
(`02:fe:00:00:00:0N`, faixa localmente administrada, que por definição não
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

#: Onde o kernel lista os nós de entrada. Parametrizável só como COSTURA DE
#: TESTE — a suíte aponta para um diretório temporário, e nenhum teste desta
#: casa toca `/sys` ou `/dev` de verdade (TEMPESTADE-DE-TECLADOS-01).
RAIZ_CLASS_INPUT = "/sys/class/input"

#: Onde moram os nós de `/dev` correspondentes. Duas raízes separadas porque a
#: suíte precisa forjar as duas, e porque `os.stat` só faz sentido nesta.
RAIZ_DEV_INPUT = "/dev/input"
RAIZ_DEV = "/dev"

#: O que um bloco de nó devolve quando nada se resolveu. Quatro `None`, nunca
#: um dicionário vazio: quem lê o payload tem de encontrar as chaves sempre,
#: senão "o campo não existe" (daemon velho) e "o daemon não sabe" (nó não
#: resolvido) chegam iguais na tela — o modo de falha do `game_open`, que
#: existia no objeto desde sempre e nunca saía por IPC.
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
    """As linhas `CHAVE=valor` de um `uevent` como dicionário.

    Mesma forma do `scripts/identidade_do_vpad.py::campos_do_uevent`. A cópia
    é de três linhas e existe porque `src/` não importa de `scripts/`; o que
    NÃO se duplica é o critério — o `VPAD_HID_PHYS` usado abaixo é o mesmo
    objeto que o `_create2_event` carimba no kernel.
    """
    return dict(
        linha.split("=", 1) for linha in texto.splitlines() if "=" in linha
    )


def _numero_do_evento(entrada: str) -> int:
    """`event22` -> 22. Ordenar por texto poria `event9` depois de `event22`."""
    try:
        return int(entrada[len("event") :])
    except ValueError:
        return 1 << 30  # sem número: vai para o fim, nunca ganha o desempate


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
            # Caminho uinput: evdev puro, sem `uniq`. O nome é a única marca
            # que sobra, e é frágil por natureza (este já mudou uma vez) — por
            # isso ele só entra quando NÃO há `uniq`, nunca como reforço.
            nome_do_no = _texto_do_sysfs(os.path.join(base, "name"))
            if not nome or nome_do_no != nome:
                continue
        achados.append((_numero_do_evento(entrada), entrada, nome_do_no))
    return sorted(achados)


def _escolher(candidatos: list[tuple[int, str, str]], nome: str) -> str | None:
    """Qual dos nós do aparelho é o do JOGO — o gamepad, não o touchpad.

    O `hid_playstation` batiza o gamepad com o nome do `hdev` e os irmãos com
    sufixo (`ps_gamepad`/`ps_touchpad`/`ps_sensors`), então o nome EXATO é o
    critério. Sem nome conhecido, o desempate é o menor `eventN`: o gamepad é
    registrado primeiro, e é o palpite conservador — mas ele é palpite, e por
    isso perde para o nome sempre que há nome.
    """
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
    """O `hidrawN` do device HID dono deste nó de entrada, CONFIRMADO.

    `/sys/class/input/eventN/device` resolve em `<device HID>/input/inputM`;
    dois níveis acima está o device HID, que publica `hidraw/hidrawN` e o
    `uevent` com `HID_UNIQ`/`HID_PHYS`.

    A confirmação pelo `uevent` é a SEGUNDA RÉGUA, e ela pode reprovar: se o
    device HID a que este nó pertence não traz o nosso carimbo, a resposta é
    `None` — "não sei" —, nunca o `hidraw` que estava ali. O caminho uinput cai
    aqui também e sai `None` por construção: um vpad de uinput não tem hidraw,
    e é justamente por isso que o SDL não o faz vibrar.
    """
    dir_do_no = os.path.join(raiz_class_input, entrada, "device")
    try:
        alvo = os.path.realpath(dir_do_no)
    except OSError:
        return None
    pai = os.path.dirname(alvo)
    if os.path.basename(pai) != "input":
        return None  # uinput e afins: não há device HID acima
    dir_hid = os.path.dirname(pai)
    campos = _campos_do_uevent(_texto_do_sysfs(os.path.join(dir_hid, "uevent")))
    if not campos:
        return None  # uevent ilegível: não afirmar
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
    """`st_ino` do nó, ou `None`. `os.stat` NÃO abre o device.

    Isto não é detalhe de implementação, é a razão de a função existir: abrir o
    `/dev/hidraw` do vpad dispara `UHID_OPEN` e arma o modo jogo, e fechá-lo
    por último deixa o controle vibrando (o `_silence_rumble` não roda). O
    produto publica o inode para que nenhum instrumento precise abrir nada.
    """
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
    """`{evdev, hidraw, ino, hidraw_ino}` do vpad com este `uniq`/`nome`.

    `uniq` é o MAC forjado (`vpad.mac`, `02:fe:00:00:00:0N`) e é a régua forte;
    `nome` é o `vpad.name`, que serve para (a) escolher o gamepad entre os
    irmãos do mesmo aparelho e (b) achar o vpad de uinput, que não tem `uniq`.

    Sem `uniq` E sem `nome` não há o que casar, e a resposta é
    `NO_DESCONHECIDO` — quatro `None`. Esta função nunca devolve o "primeiro
    gamepad que achou": um chute aqui viraria uma afirmação sobre o controle
    FÍSICO dela no payload do produto.

    **E ela também não devolve "o primeiro dos HOMÔNIMOS"** (medido em
    20/08/2026, na prova de discriminação): sem `uniq`, o casamento é pelo
    nome, e no co-op de uinput os vpads são todos `XBOX360_NAME` — a mesma
    palavra, sem número de jogador. Dois candidatos com `uniq` vazio é
    ambiguidade REAL, não empate a desempatar, e a resposta é
    `NO_DESCONHECIDO`. Com `uniq` a pluralidade é normal e esperada (gamepad,
    touchpad e sensores dividem o `uniq` do aparelho), e quem desempata é o
    nome.

    As três raízes são `None` por default e se resolvem **na hora da chamada**,
    nunca no `def` — mesmo padrão (e mesma razão) do `dualsense_sem_driver`
    logo ali no `ipc_handlers`: assim as constantes deste módulo continuam
    sendo o único lugar onde os caminhos estão escritos, e a suíte as troca por
    um diretório temporário. Isso não é conforto de teste, é a disciplina da
    TEMPESTADE-DE-TECLADOS-01: nenhum teste desta casa varre o `/sys` vivo da
    máquina dela, onde os vpads de VERDADE estão.
    """
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
        # CO-OP NO BACKEND UINPUT, e é o caso vivo na máquina dela hoje.
        # `XBOX360_NAME` é UMA constante, sem número de jogador: os quatro
        # vpads de uinput publicam o nome IDÊNTICO, e o kernel não guarda
        # `uniq` nem device HID onde diferenciá-los. Sem esta recusa,
        # `_escolher` devolve o de menor `eventN` para TODOS eles, e o
        # `state_full` passa a publicar o inode de P1 dentro do bloco de P2 —
        # com confiança, sem `None`, sem aviso. A régua irmã de `scripts/`
        # já recusa este caso com todas as letras
        # (`o_jogo_segura_o_nosso_no::_rotulo_do_no`: "escolher um deles seria
        # inventar de qual jogador é o nó"); aqui a recusa faltava.
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
    """O bloco cacheado ainda descreve o MESMO nó? (`stat` de 1 syscall)

    O cache por TTL desta casa tem 2 s, e 2 s de caminho velho é exatamente a
    mentira que o inode existe para impedir. Esta conferência custa um `stat` e
    fecha a janela: se o `event22` de agora tem outro inode — porque o vpad
    morreu e voltou, ou porque o número foi reciclado para outro aparelho —, o
    bloco é descartado na hora.

    **Ela cobre um buraco só, e é de propósito.** Bloco sem `evdev` devolve
    `True`: um bloco que não afirma caminho nenhum não tem caminho a
    envelhecer, e nada a reconferir. Quem cobre o nó que APARECEU é o TTL —
    reprovar aqui faria a varredura inteira rodar a 10 Hz justamente no caso
    mais comum (vpad de uinput, vpad ainda nascendo, máquina sem controle), que
    é o oposto do motivo de o cache existir.

    Buraco declarado: um nó destruído e recriado com o MESMO inode passaria. O
    devtmpfs aloca inode crescente, então isso não acontece com `/dev` de
    verdade; não acontecer "na prática" é o limite honesto desta conferência, e
    por isso ela é uma re-checagem barata, nunca a régua principal.
    """
    evdev = no.get("evdev")
    if not isinstance(evdev, str) or not evdev:
        return True  # nada afirmado: só o TTL manda aqui
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
