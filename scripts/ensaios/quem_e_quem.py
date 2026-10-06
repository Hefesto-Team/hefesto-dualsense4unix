#!/usr/bin/env python3
"""quem_e_quem.py — a correspondência MAC ↔ hidraw ↔ evdev ↔ vpad ↔ placa ALSA.

A PERGUNTA QUE ELE RESPONDE
----------------------------
*Qual controle físico é qual jogador?* Este instrumento nasceu em 15/08/2026
porque isso **não era observável pelo estado publicado**: o `state_full` trazia
`coop.players` como um NÚMERO (4), não como lista, e a pergunta "o vpad e o
físico correspondem?" só pôde ser respondida apertando botão em cada controle —
quatro vezes, à mão.

FATO SUBSTITUÍDO (15/08/2026, QUEM-ALIMENTA-QUEM-01): o produto passou a
publicar `coop.jogadores` — uma LISTA com, por jogador, o MAC do físico, o
`vpad_uniq` (o MAC forjado `02:fe:…` que o `HID_UNIQ` do vpad carrega) e o
backend. **Com um daemon novo, `hefesto coop status --json` responde a ligação
vpad↔MAC sem apertar nada.** Este instrumento continua valendo por outra razão:
ele mede o aparelho por FORA (sysfs, LED aceso), e é assim que se confere se o
que o daemon PUBLICA bate com o que o kernel MOSTRA.

Este instrumento resolve por sysfs **tudo o que sysfs resolve**, e diz com todas
as letras o que sobra — em vez de deixar o buraco calado, que é o defeito que
ele existe para não repetir.

O QUE ELE RESOLVE SOZINHO, E COMO
----------------------------------
  MAC ↔ hidraw ..... `HID_UNIQ` do `uevent` do device HID pai;
  hidraw ↔ evdev ... os `input*/event*` pendurados no mesmo device;
  hidraw ↔ placa ... o dispositivo USB em comum (interface `:1.0` é o áudio,
                     `:1.3` é o HID; as duas penduram no mesmo `usbN/X-Y`).
                     Só existe no cabo, por construção;
  hidraw ↔ bateria . o nome do `power_supply` carrega o MAC;
  vpad ↔ jogador ... o `HID_NAME`/`HID_UNIQ` que o produto carimba no vpad.

O QUE ELE MEDE E QUASE NINGUÉM PERCEBE QUE DÁ PARA MEDIR
---------------------------------------------------------
**O desenho do player LED sai do sysfs.** O `hid_playstation` publica cada um
dos cinco LEDs em `leds/<...>:white:player-N/brightness`, e o padrão aceso
decodifica direto para o número do jogador que o APARELHO está mostrando:

    00100 = P1     01010 = P2     10101 = P3     11011 = P4

Isso transforma "olhar o controle com o olho e contar as luzinhas" numa
**medição**, e é como este instrumento enxerga, sem pedir nada a ninguém, a
divergência entre o número que o daemon diz e o desenho que ele de fato
escreve — o defeito medido em 15/08/2026, que outra frente está curando em
`src/`. Aqui ele só é OBSERVADO; este instrumento não conserta nada.

O ENSAIO DO APERTO: FÍSICO ↔ PAD ↔ CARTÃO (`--apertar`)
--------------------------------------------------------
Nenhum arquivo de `/sys` liga o pad ao controle que o alimenta (o vpad nasce
por `/dev/uhid` ou `/dev/uinput` sem ponteiro para o físico; quem carrega a
ligação é o daemon, em `coop.jogadores`). O `--apertar` a mede por fora, e
mede junto a pergunta que a bancada de 29/09/2026 fez: *o botão apertado
naquele controle acende o cartão dele na aba Controles?*

Ele lê DUAS fontes, e quem diz «houve aperto» nunca sai do estado:

  a testemunha ... o nó que o JOGO lê, com a hora do kernel: o pad uhid (modo
                   DualSense, e o nó diz o jogador), o pad uinput (modo Xbox,
                   achado pelo dono, `identidade_do_vpad.e_pad_uinput_do_hefesto`;
                   o nó não diz o jogador) ou, sem pad nenhum (Nativo), o
                   físico, aberto pela porta da casa (`abrir_input_device`). O
                   nó que não falou sai pelo dono do zero (`leitura_de_zero`):
                   «o controle não emitiu» e «eu não posso ler» não saem iguais;
  a tela ......... o `state_full`, lido a cada `hefesto_vivo.TIQUE_MS`, com o
                   aceso de cada cartão pela conta da aba Controles
                   (`a02_controles.leitura_viva`). Nenhuma regra de «aceso»
                   mora aqui.

Cada aperto testemunhado dá uma linha: «acendeu só o cartão Pn» (e, onde o nó
diz o jogador, o Pn tem de ser o dele), ou FALHA («não acendeu cartão nenhum»,
«acendeu mais de um cartão», «o de outro jogador»), ou «curto demais para o
tique da tela», que não é FALHA e também não é medida; o botão que a grade não
desenha (o L3, o R3: quem diz é o `leitura_viva`) e não acendeu nada também
não é medida. A linha diz o nome que o jogo viu e o que a tela acendeu: com uma
troca de botão ligada, os dois diferem.

O LIMITE, dito também na saída: o ensaio prova o canal que a grade lê, não a
pintura. Ele não sabe se a aba 02 está na tela; quem prova a pintura são as
réguas da aba e o olho de quem confere.

O RC do `--apertar`: 2 com uma FALHA, 3 com nada medido (sem aperto
testemunhado, só apertos curtos, a tela que não respondeu, ou a tela que não
se lê aqui). Quando todo aperto medido acendeu o cartão dele, vale o rc da
tabela, com o aviso do LED de jogador. A interface é importada SÓ no
`--apertar`: a tabela e o `--json`, que o `o_basico.py` lê, não dependem do Gtk.

PRECISA DO DAEMON PARADO? Não. A tabela é sysfs, e o `--apertar` lê o daemon.

O ENDEREÇO NUNCA SAI CRU (O-BASICO-MEDIDO-01, 28/09/2026). A coluna «MAC»
imprimia o `HID_UNIQ` inteiro, e o MAC forjado do vpad é derivado do endereço
do controle. Toda linha passa pelo dono da máscara da casa
(`core/formas_do_endereco.mascarar`), com os endereços desta mesa como
conhecidos. O `--json` é a forma que o `o_basico.py` lê: o LED aceso, a cor
do sysfs e o transporte de cada físico, com o endereço mascarado.

USO
    quem_e_quem.py
    quem_e_quem.py --json
    quem_e_quem.py --apertar
"""

from __future__ import annotations

import argparse
import contextlib
import os
import selectors
import sys
import time
from dataclasses import dataclass, field
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comum import (
    CABO,
    Aparelho,
    cabecalho_do_instrumento,
    censo_da_mesa,
    descobrir_aparelhos,
    fisicos,
    ler_texto,
    resumo,
    tabela,
    vpads,
)
from identidade_do_vpad import e_pad_uinput_do_hefesto

from hefesto_dualsense4unix.core.formas_do_endereco import mascarar

CONHECIDOS: list[str] = []


def dizer(texto: str = "") -> None:
    """Toda linha que sai daqui passa pelo dono da máscara."""
    print(mascarar(texto, CONHECIDOS))

try:
    import evdev
    from evdev import ecodes
except ImportError:  # pragma: no cover - só quando falta a dep do projeto
    evdev = None  # type: ignore[assignment]
    ecodes = None  # type: ignore[assignment]

# Os padrões de player LED do DualSense: cinco luzes, e só quatro desenhos
DESENHOS_DO_LED = {
    (0, 0, 1, 0, 0): 1,
    (0, 1, 0, 1, 0): 2,
    (1, 0, 1, 0, 1): 3,
    (1, 1, 0, 1, 1): 4,
}


def _placa_alsa_do_usb(usb: str) -> str:
    if not usb:
        return "-"
    for entrada in sorted(os.listdir("/sys/class/sound")):
        if not entrada.startswith("card"):
            continue
        alvo = os.path.realpath(f"/sys/class/sound/{entrada}/device")
        if alvo.startswith(usb + "/") or alvo == usb:
            nome = ler_texto(f"/proc/asound/{entrada}/id").strip()
            return f"{entrada} ({nome})" if nome else entrada
    return "-"


def _dispositivo_usb_pai(caminho: str) -> str:
    atual = os.path.realpath(caminho)
    while atual and atual != "/":
        if os.path.exists(os.path.join(atual, "busnum")):
            return atual
        atual = os.path.dirname(atual)
    return ""


def _nos_de_entrada(aparelho: Aparelho) -> dict[str, str]:
    """{"principal": "/dev/input/eventN", "movimento": ..., ...} deste aparelho."""
    achados: dict[str, str] = {}
    raiz = os.path.join(aparelho.dir_device, "input")
    if not os.path.isdir(raiz):
        return achados
    for entrada in sorted(os.listdir(raiz)):
        dir_input = os.path.join(raiz, entrada)
        if not os.path.isdir(dir_input):
            continue
        nome = ler_texto(os.path.join(dir_input, "name")).strip()
        if "Motion" in nome:
            papel = "movimento"
        elif "Touchpad" in nome:
            papel = "touchpad"
        elif "Headset" in nome:
            papel = "fone"
        else:
            papel = "principal"
        for sub in sorted(os.listdir(dir_input)):
            if sub.startswith("event"):
                achados.setdefault(papel, f"/dev/input/{sub}")
    return achados


def _player_led(aparelho: Aparelho) -> tuple[str, str]:
    """(desenho aceso, jogador que o desenho significa) lido do sysfs."""
    dir_leds = os.path.join(aparelho.dir_device, "leds")
    if not os.path.isdir(dir_leds):
        return "-", "-"
    acesos: list[int] = []
    for numero in range(1, 6):
        achado = [d for d in os.listdir(dir_leds) if d.endswith(f":player-{numero}")]
        if not achado:
            return "-", "-"
        bruto = ler_texto(os.path.join(dir_leds, achado[0], "brightness")).strip()
        acesos.append(1 if bruto not in ("", "0") else 0)
    desenho = "".join(str(x) for x in acesos)
    jogador = DESENHOS_DO_LED.get(tuple(acesos))
    return desenho, (f"P{jogador}" if jogador else "padrão inválido")


def _luz_do_sysfs(aparelho: Aparelho) -> tuple[list[int] | None, int | None]:
    """A cor que o kernel publica na barra (``multi_intensity``) e o brilho."""
    dir_leds = os.path.join(aparelho.dir_device, "leds")
    if not os.path.isdir(dir_leds):
        return None, None
    for entrada in sorted(os.listdir(dir_leds)):
        if not entrada.endswith(":rgb:indicator"):
            continue
        cor = ler_texto(os.path.join(dir_leds, entrada, "multi_intensity")).split()
        brilho = ler_texto(os.path.join(dir_leds, entrada, "brightness")).strip()
        rgb = [int(x) for x in cor] if len(cor) == 3 and all(x.isdigit() for x in cor) else None
        return rgb, int(brilho) if brilho.isdigit() else None
    return None, None


def retrato_json(alvos: list[Aparelho], saidas: list[Aparelho]) -> dict[str, object]:
    """A forma que o `o_basico.py` lê: um físico por linha, o endereço mascarado."""
    fisicos_json = []
    for aparelho in alvos:
        desenho, jogador = _player_led(aparelho)
        rgb, brilho = _luz_do_sysfs(aparelho)
        fisicos_json.append({
            "uniq": mascarar(aparelho.mac, CONHECIDOS) if aparelho.mac else None,
            "transporte": aparelho.transporte,
            "hidraw": aparelho.hidraw,
            "led_desenho": desenho,
            "led_jogador": int(jogador[1:]) if jogador.startswith("P") and jogador[1:].isdigit() else None,
            "luz_rgb": rgb,
            "luz_brilho": brilho,
            "bateria": _bateria(aparelho),
        })
    numeros = [f["led_jogador"] for f in fisicos_json if f["led_jogador"] is not None]
    repetidos = sorted({n for n in numeros if numeros.count(n) > 1})
    return {
        "veredito": (f"o mesmo número aceso em dois controles: {repetidos}" if repetidos
                     else f"{len(numeros)} de {len(fisicos_json)} físico(s) com o LED legível"),
        "alvos_inicio": [f["uniq"] for f in fisicos_json],
        "alvos_fim": [f["uniq"] for f in fisicos_json],
        "mexeu": [],
        "medidas": {"fisicos": len(fisicos_json), "vpads": len(saidas), "repetidos": repetidos},
        "fisicos": fisicos_json,
        "vpads": [{"rotulo": v.rotulo, "hidraw": v.hidraw} for v in saidas],
    }


def _bateria(aparelho: Aparelho) -> str:
    dir_ps = os.path.join(aparelho.dir_device, "power_supply")
    if not os.path.isdir(dir_ps):
        return "-"
    for entrada in sorted(os.listdir(dir_ps)):
        capacidade = ler_texto(os.path.join(dir_ps, entrada, "capacity")).strip()
        estado = ler_texto(os.path.join(dir_ps, entrada, "status")).strip()
        if capacidade:
            return f"{capacidade}% {estado}".strip()
    return "-"


def tabela_dos_fisicos(alvos: list[Aparelho]) -> list[str]:
    """Imprime a tabela dos controles físicos. Devolve os avisos que achou."""
    cabecalho = [
        "MAC",
        "transporte",
        "hidraw",
        "evdev principal",
        "placa ALSA",
        "LED aceso",
        "LED diz",
        "hardware",
        "bateria",
    ]
    linhas: list[list[str]] = []
    avisos: list[str] = []
    vistos: dict[str, list[str]] = {}

    for aparelho in alvos:
        nos = _nos_de_entrada(aparelho)
        desenho, jogador = _player_led(aparelho)
        if jogador.startswith("P"):
            vistos.setdefault(jogador, []).append(mascarar(aparelho.mac, CONHECIDOS))
        elif desenho != "-":
            avisos.append(
                f"{mascarar(aparelho.mac, CONHECIDOS)}: LED em {desenho}, que não é desenho de jogador nenhum"
            )
        linhas.append(
            [
                mascarar(aparelho.mac, CONHECIDOS) if aparelho.mac else "?",
                aparelho.transporte,
                aparelho.hidraw,
                nos.get("principal", "-"),
                _placa_alsa_do_usb(_dispositivo_usb_pai(aparelho.dir_device))
                if aparelho.transporte == CABO
                else "- (só no cabo)",
                desenho,
                jogador,
                ler_texto(os.path.join(aparelho.dir_device, "hardware_version")).strip() or "-",
                _bateria(aparelho),
            ]
        )
    dizer()
    dizer("  OS CONTROLES FÍSICOS")
    dizer()
    dizer(tabela(cabecalho, linhas))

    for jogador, macs in sorted(vistos.items()):
        if len(macs) > 1:
            avisos.append(f"{jogador} está aceso em {len(macs)} controles: {', '.join(macs)}")
    return avisos


def tabela_dos_vpads(saidas: list[Aparelho]) -> None:
    cabecalho = ["vpad", "jogador", "hidraw", "evdev principal", "MAC forjado"]
    linhas = [
        [
            v.rotulo,
            v.rotulo,
            v.hidraw,
            _nos_de_entrada(v).get("principal", "-"),
            mascarar(v.mac, CONHECIDOS) if v.mac else "?",
        ]
        for v in saidas
    ]
    dizer()
    dizer("  OS VPADS — a saída do produto, o que o jogo enxerga")
    dizer()
    dizer(tabela(cabecalho, linhas))


# Em 29/09/2026 um laço de 0,1 s leu 1.767 vezes o `state_full` com os botões

ACENDEU = "acendeu"
FALHA = "falha"
CURTO = "curto"
SEM_TELA = "sem_tela"
SEM_GLIFO = "sem_glifo"

RC_FALHA = 2
RC_NADA_MEDIDO = 3

PAD_UHID = "pad uhid"
PAD_UINPUT = "pad uinput"
FISICO = "físico"


@dataclass(frozen=True)
class Testemunha:
    """Um nó evdev que diz, com a hora do kernel, que um botão desceu."""

    caminho: str
    tipo: str
    jogador: str = ""
    uniq: str = ""

    @property
    def marca(self) -> str:
        if self.jogador:
            return f"{self.tipo} {self.jogador}"
        if self.uniq:
            return f"{self.tipo} {self.uniq}"
        return f"{self.tipo} {self.caminho}"


@dataclass
class Aperto:
    testemunha: Testemunha
    codigo: int
    nome: str
    descida: float
    subida: float | None = None


@dataclass(frozen=True)
class Leitura:
    """Uma pergunta ao `state_full`, com a hora em que a resposta chegou."""

    hora: float
    acesos: dict[int, frozenset[str]] | None
    enderecos: dict[int, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Veredito:
    tipo: str
    texto: str


def _nome_do_botao(codigo: int) -> str:
    """O nome que o jogo vê, pelo dono (o mesmo mapa do leitor do daemon)."""
    from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

    for nome_evdev, nome in EvdevReader.BUTTON_MAP.items():
        if ecodes.ecodes.get(nome_evdev) == codigo:
            return str(nome)
    cru: object = ecodes.BTN.get(codigo) or ecodes.KEY.get(codigo) or str(codigo)
    return str(cru[0]) if isinstance(cru, (list, tuple)) else str(cru)


def testemunhas_da_mesa(aparelhos: list[Aparelho], raiz_sys: str = "/sys") -> list[Testemunha]:
    """Os nós que o JOGO lê, em todo modo; o físico só quando não há pad.

    - uhid (DualSense): o nó principal de cada vpad, e o vpad diz o jogador;
    - uinput (Xbox): os nós que o dono já reconhece
      (`identidade_do_vpad.e_pad_uinput_do_hefesto`), achados em
      `/sys/class/input`. O nó não diz o jogador;
    - Nativo (sem pad): o nó principal de cada físico, e o endereço dele
      diz de quem é o cartão.
    """
    achadas: list[Testemunha] = []
    for vpad in vpads(aparelhos):
        caminho = _nos_de_entrada(vpad).get("principal")
        if caminho:
            jogador = vpad.rotulo if vpad.rotulo.startswith("P") else ""
            achadas.append(Testemunha(caminho, PAD_UHID, jogador=jogador))
    raiz = os.path.join(raiz_sys, "class", "input")
    try:
        entradas = sorted(os.listdir(raiz), key=lambda n: int(n.removeprefix("event") or 0)
                          if n.removeprefix("event").isdigit() else -1)
    except OSError:
        entradas = []
    for entrada in entradas:
        if not entrada.startswith("event"):
            continue
        dir_device = os.path.join(raiz, entrada, "device")
        nome = ler_texto(os.path.join(dir_device, "name")).strip()
        if e_pad_uinput_do_hefesto(nome, dir_device):
            achadas.append(Testemunha(f"/dev/input/{entrada}", PAD_UINPUT))
    if achadas:
        return achadas
    for fisico in fisicos(aparelhos):
        caminho = _nos_de_entrada(fisico).get("principal")
        if caminho:
            achadas.append(Testemunha(caminho, FISICO, uniq=fisico.mac))
    return achadas


def _a_tela() -> tuple[Any, Any, Any, int]:
    """Os donos da leitura da tela, importados SÓ no `--apertar`.

    O `hefesto_vivo` sobe o Gtk e o WebKit no import, e este ensaio vai no
    pacote e roda com `--json` pelo `o_basico.py`: a tabela e o `--json` não
    podem depender da interface. Devolve (`mesa_viva`, `leitura_viva`,
    `mesa_do_estado`, `TIQUE_MS`), ou levanta `ImportError`.
    """
    import hefesto_dualsense4unix

    interface = os.path.join(os.path.dirname(hefesto_dualsense4unix.__file__), "interface")
    if os.path.isdir(interface) and interface not in sys.path:
        sys.path.insert(0, interface)
    from hefesto_dualsense4unix.interface import hefesto_vivo, mesa_viva
    from hefesto_dualsense4unix.interface.pacotes import a02_controles

    return mesa_viva, a02_controles.leitura_viva, mesa_viva.mesa_do_estado, int(hefesto_vivo.TIQUE_MS)


def ler_a_tela(estado: dict[str, Any], leitura_viva: Any, mesa_do_estado: Any,
               hora: float) -> Leitura:
    """Os glifos acesos de cada cartão, pela conta que a aba Controles faz.

    O cartão é o item da mesa (`mesa_viva.mesa_do_estado`, o número que o
    cabeçalho do cartão imprime), e o aceso é o `leitura_viva` da aba 02 sobre
    a entrada do controle com o mesmo endereço. Nenhuma regra de «aceso» mora
    aqui: seria uma segunda régua, que envelhece calada.
    """
    numero_do_uniq = {
        str(item.get("uniq") or ""): int(item.get("jogador") or 0)
        for item in mesa_do_estado(estado, {})
    }
    acesos: dict[int, frozenset[str]] = {}
    enderecos: dict[int, str] = {}
    for entrada in estado.get("controllers") or []:
        if not isinstance(entrada, dict):
            continue
        uniq = str(entrada.get("uniq") or "")
        numero = numero_do_uniq.get(uniq)
        if not numero:
            continue
        campos = leitura_viva(entrada)
        acesos[numero] = frozenset(
            chave.removeprefix("glifo-") for chave, valor in campos.items()
            if chave.startswith("glifo-") and valor
        )
        enderecos[numero] = uniq.lower()
    return Leitura(hora, acesos, enderecos)


def acende_algum_glifo(leitura_viva: Any, nome: str) -> bool:
    """A grade tem glifo para este nome? Perguntado ao dono do aceso.

    A grade tem dezesseis glifos, e o L3, o R3 e o botão do microfone não estão
    entre eles; o L2 e o R2 acendem pelo gatilho, não pelo botão. Em vez de uma
    lista escrita aqui, o `leitura_viva` recebe o nome apertado e diz se algum
    glifo acende (o `create` acende o `share`, por exemplo).
    """
    campos = leitura_viva({"inputs": {"buttons": [nome]}})
    return any(valor for chave, valor in campos.items() if chave.startswith("glifo-"))


def julgar(
    aperto: Aperto,
    leituras: list[Leitura],
    tique_s: float,
    fim: float,
    tem_glifo: Any = None,
) -> Veredito:
    """O veredito de UM aperto testemunhado."""
    subida = aperto.subida if aperto.subida is not None else fim
    duracao = subida - aperto.descida
    janela = [x for x in leituras if aperto.descida <= x.hora <= subida + 2 * tique_s]
    respondidas = [x for x in janela if x.acesos is not None]
    curto = duracao <= tique_s
    if not respondidas:
        if curto:
            return Veredito(CURTO, "curto demais para o tique da tela")
        return Veredito(SEM_TELA, "a tela não respondeu durante o aperto — nada medido")
    cartoes: dict[int, set[str]] = {}
    enderecos: dict[int, str] = {}
    for leitura in respondidas:
        enderecos.update(leitura.enderecos)
        for numero, glifos in (leitura.acesos or {}).items():
            if glifos:
                cartoes.setdefault(numero, set()).update(glifos)
    if not cartoes:
        if curto:
            return Veredito(CURTO, "curto demais para o tique da tela")
        if tem_glifo is not None and not tem_glifo(aperto.nome):
            return Veredito(SEM_GLIFO, f"a grade não tem glifo para {aperto.nome} — nada medido")
        return Veredito(FALHA, "não acendeu cartão nenhum")
    acesos = ", ".join(f"P{n} ({', '.join(sorted(g))})" for n, g in sorted(cartoes.items()))
    if len(cartoes) > 1:
        return Veredito(FALHA, f"acendeu mais de um cartão: {acesos}")
    ((numero, acesos_do_cartao),) = cartoes.items()
    esperado = aperto.testemunha.jogador
    if not esperado and aperto.testemunha.uniq:
        dono = [n for n, u in enderecos.items() if u and u == aperto.testemunha.uniq.lower()]
        esperado = f"P{dono[0]}" if len(dono) == 1 else ""
    tela = ", ".join(sorted(acesos_do_cartao))
    if esperado and esperado != f"P{numero}":
        return Veredito(FALHA, f"acendeu o cartão P{numero}, que é de outro jogador "
                               f"(o nó é do {esperado}); a tela acendeu {tela}")
    return Veredito(ACENDEU, f"acendeu só o cartão P{numero}; a tela acendeu {tela}")


def _colher(
    abertos: list[tuple[Any, Testemunha]],
    segundos: float,
    tique_s: float,
    ler: Any,
    mudo: type[Exception],
    ler_a_tela_de: Any,
    relogio: Any,
    novo_seletor: Any,
) -> tuple[list[Aperto], list[Leitura], set[Testemunha], float]:
    """O laço: o pad pela hora do kernel, a tela a cada tique."""
    seletor = novo_seletor()
    dono_do_no: dict[int, Testemunha] = {}
    for dispositivo, testemunha in abertos:
        seletor.register(dispositivo, selectors.EVENT_READ)
        dono_do_no[id(dispositivo)] = testemunha
    apertos: list[Aperto] = []
    leituras: list[Leitura] = []
    descidas: dict[tuple[int, int], Aperto] = {}
    falaram: set[Testemunha] = set()
    inicio = relogio()
    fim = inicio + segundos
    proxima = inicio
    try:
        while True:
            agora = relogio()
            if agora >= fim:
                break
            if agora >= proxima:
                try:
                    estado = ler()
                except mudo:
                    leituras.append(Leitura(relogio(), None))
                else:
                    leituras.append(ler_a_tela_de(estado, relogio()))
                proxima = max(proxima + tique_s, relogio() + tique_s / 2)
                continue
            for chave, _ in seletor.select(max(0.0, min(proxima, fim) - agora)):
                dispositivo = chave.fileobj
                try:
                    lidos = list(dispositivo.read())
                except OSError:
                    continue
                for evento in lidos:
                    if evento.type != ecodes.EV_KEY or evento.value not in (0, 1):
                        continue
                    chave_do_botao = (id(dispositivo), evento.code)
                    if evento.value == 1:
                        testemunha = dono_do_no[id(dispositivo)]
                        falaram.add(testemunha)
                        aperto = Aperto(testemunha, evento.code,
                                        _nome_do_botao(evento.code), evento.timestamp())
                        apertos.append(aperto)
                        descidas[chave_do_botao] = aperto
                    elif chave_do_botao in descidas:
                        descidas.pop(chave_do_botao).subida = evento.timestamp()
    finally:
        for chave in list(seletor.get_map().values()):
            with contextlib.suppress(OSError):
                chave.fileobj.close()
        seletor.close()
    return apertos, leituras, falaram, fim


def ensaio_de_aperto(
    aparelhos: list[Aparelho],
    segundos: float,
    *,
    raiz_sys: str = "/sys",
    relogio: Any = time.time,
    novo_seletor: Any = selectors.DefaultSelector,
) -> int | None:
    """Físico ↔ pad ↔ cartão: cada aperto testemunhado pelo pad, e o cartão"""
    dizer()
    dizer("  ENSAIO DO APERTO — físico ↔ pad ↔ cartão")
    dizer()
    if evdev is None:
        dizer("  python-evdev ausente — rode com .venv/bin/python. Nada medido.")
        return RC_NADA_MEDIDO
    try:
        mesa_viva, leitura_viva, mesa_do_estado, tique_ms = _a_tela()
    except Exception as erro:
        dizer(f"  A tela não se lê aqui ({type(erro).__name__}: {erro}) — nada medido.")
        return RC_NADA_MEDIDO
    from hefesto_dualsense4unix.core import evdev_reader
    from hefesto_dualsense4unix.integrations import hidraw_broker_client

    tique_s = tique_ms / 1000.0
    testemunhas = testemunhas_da_mesa(aparelhos, raiz_sys)
    tipos = sorted({t.tipo for t in testemunhas})
    dizer("  A testemunha é o nó que o jogo lê, com a hora do kernel: "
          + (", ".join(tipos) if tipos else "nenhum nó achado") + ".")
    dizer(f"  A tela é o `state_full`, lido a cada {tique_ms} ms e aceso pela conta da")
    dizer("  aba Controles. O ensaio prova o canal que a grade lê, não a pintura:")
    dizer("  ele não sabe se a aba está na tela.")
    dizer()

    abertos: list[tuple[Any, Testemunha]] = []
    for testemunha in testemunhas:
        try:
            dispositivo = evdev_reader.abrir_input_device(testemunha.caminho)
        except OSError as erro:
            dizer(f"    {testemunha.marca} ({testemunha.caminho}) não abriu: {erro}")
            continue
        abertos.append((dispositivo, testemunha))

    apertos: list[Aperto] = []
    leituras: list[Leitura] = []
    falaram: set[Testemunha] = set()
    fim = relogio()
    if abertos:
        dizer(f"  >> APERTE um botão em cada controle, um de cada vez. Esperando {segundos:.0f} s…")
        dizer()
        apertos, leituras, falaram, fim = _colher(
            abertos, segundos, tique_s, mesa_viva.estado_do_daemon, mesa_viva.DaemonMudo,
            lambda estado, hora: ler_a_tela(estado, leitura_viva, mesa_do_estado, hora),
            relogio, novo_seletor)

    calados = [t for t in testemunhas if t not in falaram]
    for testemunha in calados:
        estado_grab = hidraw_broker_client.estado_do_grab(testemunha.caminho)
        dizer(f"    {testemunha.marca} ({testemunha.caminho}): "
              f"{hidraw_broker_client.leitura_de_zero(estado_grab)}")

    def tem_glifo(nome: str) -> bool:
        return acende_algum_glifo(leitura_viva, nome)

    vereditos = [(a, julgar(a, leituras, tique_s, fim, tem_glifo)) for a in apertos]
    for aperto, veredito in vereditos:
        marca = "FALHA — " if veredito.tipo == FALHA else ""
        dizer(f"    {aperto.nome} no {aperto.testemunha.marca}: {marca}{veredito.texto}")

    dizer()
    falhas = [v for _, v in vereditos if v.tipo == FALHA]
    medidos = [v for _, v in vereditos if v.tipo in (ACENDEU, FALHA)]
    if falhas:
        dizer(f"  {len(falhas)} de {len(medidos)} aperto(s) medido(s) sem o cartão dele.")
        return RC_FALHA
    if leituras and all(x.acesos is None for x in leituras):
        dizer("  A tela não respondeu — nada medido.")
        return RC_NADA_MEDIDO
    if not abertos:
        dizer("  Nenhum nó de testemunha abriu — nada medido.")
        return RC_NADA_MEDIDO
    if not medidos:
        dizer("  Nenhum aperto medido na janela — nada medido. Aperte durante a janela,")
        dizer("  e segure o botão mais que um tique da tela.")
        return RC_NADA_MEDIDO
    dizer(f"  {len(medidos)} aperto(s) medido(s), cada um com o cartão dele.")
    return None


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(
        description="Quem é quem: MAC, hidraw, evdev, vpad e placa ALSA na mesma tabela.",
    )
    analisador.add_argument(
        "--apertar",
        action="store_true",
        help="ensaio interativo: físico ↔ pad ↔ cartão, com o pad como testemunha "
             "(rc 2 com uma falha, 3 com nada medido)",
    )
    analisador.add_argument("--segundos", type=float, default=15.0, help="janela do --apertar")
    analisador.add_argument("--json", action="store_true", help="a forma que o o_basico.py lê")
    argumentos = analisador.parse_args(argv)

    aparelhos = descobrir_aparelhos()
    CONHECIDOS.extend(a.mac for a in aparelhos if a.mac)
    if argumentos.json:
        import json

        dado = retrato_json(fisicos(aparelhos), vpads(aparelhos))
        dizer(json.dumps(dado, ensure_ascii=False, indent=1))
        medidas = dado.get("medidas")
        repetidos = medidas.get("repetidos") if isinstance(medidas, dict) else None
        return 1 if (not aparelhos or repetidos) else 0

    dizer(
        cabecalho_do_instrumento(
            "quem_e_quem.py",
            "qual controle físico é qual jogador, e o que só se resolve apertando botão?",
            bibliotecas=["evdev", "os"],
            escreve_no_aparelho=False,
            daemon_precisa_parar=False,
        )
    )

    alvos = fisicos(aparelhos)
    saidas = vpads(aparelhos)
    dizer(f"\n  {censo_da_mesa(aparelhos)}")
    if not aparelhos:
        dizer(resumo("nenhum DualSense na mesa — nada a resolver."))
        return 1

    avisos = tabela_dos_fisicos(alvos) if alvos else []
    if saidas:
        tabela_dos_vpads(saidas)

    dizer()
    dizer("  O QUE ESTA TABELA NÃO RESOLVE POR SYSFS, e é honesto dizer:")
    dizer("    - qual vpad é alimentado por qual MAC. Nenhum arquivo de /sys carrega")
    dizer("      essa ligação. Quem a carrega é o daemon, desde 15/08/2026:")
    dizer("      `hefesto coop status --json` traz `coop.jogadores` (MAC do físico +")
    dizer("      `vpad_uniq`). Aqui, use --apertar (físico ↔ pad ↔ cartão), ou compare")
    dizer("      com aquela lista.")

    if avisos:
        dizer()
        dizer("  DIVERGÊNCIAS VISTAS NO DESENHO DO PLAYER LED:")
        for aviso in avisos:
            dizer(f"    - {aviso}")
        dizer("    (defeito ABERTO, sob cura de outro agente em src/. Aqui só se observa.)")

    rc_do_aperto = ensaio_de_aperto(aparelhos, argumentos.segundos) if argumentos.apertar else None

    leds = [_player_led(a)[1] for a in alvos]
    validos = [x for x in leds if x.startswith("P")]
    numeros_dos_vpads = sorted(v.rotulo for v in saidas)
    veredito = (
        f"{len(alvos)} físico(s) e {len(saidas)} vpad(s) resolvidos por sysfs; "
        f"LED lido em {len(validos)}/{len(alvos)} ({', '.join(sorted(validos)) or '-'}) "
        f"contra vpads {', '.join(numeros_dos_vpads) or '-'}. "
        "A ligação vpad↔MAC não sai do sysfs: use --apertar (físico ↔ pad ↔ cartão), ou "
        "`hefesto coop status --json` (`coop.jogadores`, desde 15/08/2026)."
    )
    dizer(resumo(veredito))
    if rc_do_aperto is not None:
        return rc_do_aperto
    return 1 if avisos else 0


if __name__ == "__main__":
    raise SystemExit(main())
