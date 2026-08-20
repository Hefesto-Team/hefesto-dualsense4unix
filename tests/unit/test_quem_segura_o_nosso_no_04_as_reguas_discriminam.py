"""QUEM-SEGURA-O-NOSSO-NO-01/PROVA — as três réguas DISCRIMINAM, ou não medem nada.

O QUE ESTE ARQUIVO É
---------------------
As PEÇAS 1, 2 e 3 construíram três réguas para o degrau `O JOGO RECEBEU`, que
até 20/08/2026 tinha ZERO células no `docs/data/mapa-controles.csv` por falta
de instrumento. Um instrumento nessa posição não se prova rodando: prova-se
mostrando que ele responde DIFERENTE para aparelhos diferentes. Um script que
diz "achei o nosso vpad" sobre qualquer coisa que apareça na mesa não é régua,
é carimbo.

Este arquivo é a MATRIZ: três réguas contra as três perguntas que separam
instrumento de script, na MESMA mesa forjada.

                          | régua 1        | régua 2        | régua 3
                          | no_do_vpad     | o_jogo_segura  | o_log_do_proton
    ----------------------+----------------+----------------+----------------
    separa do FÍSICO?     | sim            | sim            | sim
    separa do ESPELHO?    | sim (1)        | sim, mas (2)   | sim (3)
    recusa quando não sabe| sim (4)        | sim            | sim

A MESA DE TRÊS, e por que ela tem TRÊS aparelhos e não dois
------------------------------------------------------------
A mesa real desta casa nunca teve dois aparelhos. Está MEDIDO na
TRES-CONTROLES-01 (10/08/2026), com o jogo aberto e um controle na mão:

    event2   Sony ... DualSense Wireless Controller   054c:0ce6   o FÍSICO
    event6   DualSense Wireless Controller (Hefesto P1) 054c:0df2 o NOSSO vpad
    event21  Microsoft X-Box 360 pad 0                28de:11ff   Steam Input
    event23  Microsoft X-Box 360 pad 1                28de:11ff   Steam Input

**O Steam Input faz um espelho Xbox de CADA controle que enxerga — inclusive
do nosso vpad** (`docs/protocol/pilha-steam-input-xpad-sdl.md` §2.1-2.2, com o
mecanismo fechado por `strings(1)` no `steamclient.so` dela: `Microsoft X-Box
360 pad %u` escrito em `/dev/uinput`, com VID/PID da **Valve**). Dois controles
vistos, dois espelhos criados. Uma régua testada só contra o físico passa e
continua cega para metade da mesa.

AS DUAS FALHAS DE DISCRIMINAÇÃO QUE ESTA PROVA ACHOU — e que foram curadas
--------------------------------------------------------------------------
Elas não são hipóteses: as duas foram medidas com árvore forjada, e as duas
faziam a régua AFIRMAR sobre o aparelho errado, sem `None` e sem aviso.

**(a) A régua 1 dava a P2 o nó de P1, no backend uinput.** `XBOX360_NAME` é
UMA constante — `"Microsoft X-Box 360 pad (Hefesto - Dualsense4Unix virtual)"`,
sem número de jogador —, e o vpad de uinput não tem `uniq` nem device HID onde
diferenciar um do outro. Com dois vpads na mesa, `_escolher` devolvia o de
menor `eventN` para os DOIS, e o `state_full` publicava o inode de P1 dentro do
bloco de P2. O backend uinput é o que está VIVO na máquina dela hoje. Cura: sem
`uniq`, mais de um homônimo é ambiguidade REAL, e a resposta é os quatro
`None`. Guardado por `test_r1_coop_de_uinput_e_ambiguo_e_a_regua_recusa`.

**(b) A régua 3 deixava o espelho HERDAR o nosso carimbo.** O parser tinha UM
slot de "nó aberto" e atribuía as linhas de `uevent` a quem abrira por último,
sem olhar de qual thread do Wine elas vinham — embora já extraísse a thread. Um
espelho abrindo na thread vizinha ficava com `HID_PHYS=hefesto-vpad` e entrava
como nosso vpad, com reports e tudo. Cura: o slot passou a ser por thread.
Guardado por `test_r3_o_espelho_nao_herda_o_nosso_carimbo_da_thread_vizinha`.

RESSALVA HONESTA sobre (b), porque ela muda o tamanho do achado: no único log
real desta casa (`steam-2497900.log`, 72956 linhas) as 67 linhas de
`udev_add_device` e as 524 de `get_device_subsystem_info` saem TODAS da thread
`00b4` — a contaminação era latente, não manifesta. E aquele log **não tinha
espelho nenhum** (zero ocorrências de `28de`), então ele não prova que a
enumeração segue com uma thread só quando há espelho na mesa. O veredicto do
log real é o MESMO antes e depois da cura: `RECEBEU DO NOSSO NÓ`, 9914 reports.

O LIMITE QUE **NÃO** FOI CURADO, e que é decisão dela — (2) na matriz
---------------------------------------------------------------------
A régua 2 não CONFUNDE o espelho com o nosso vpad: ela o deixa de fora, e há
teste que morde. Mas ela também não tem NOME para ele. Um jogo que segure só o
espelho do nosso vpad — que é o caminho normal quando o Steam Input está
ligado, e a entrada DELE somos nós, lavada pela Steam — cai no veredito
`NENHUM`, cujo texto é *"o censo FECHOU (...) e nenhum deles segura o nosso nó
nem o do físico. Isto é uma afirmação, não uma ausência de dado."*

**É uma afirmação, e ela lê como "a nossa entrada não chegou ao jogo" quando a
entrada chegou, um andar acima.** Curar isso é acrescentar uma classe de alvo e
um sexto veredito ao léxico de cinco — e léxico de veredito é dela. Fica
DECLARADO aqui e no relato, com teste que prende o comportamento de hoje para
que a próxima pessoa não descubra sozinha:
`test_r2_o_jogo_que_so_segura_o_espelho_cai_em_nenhum_e_esse_e_o_limite`.

NENHUM TESTE DAQUI TOCA O `/sys`, O `/proc` OU O `/dev` VIVOS
--------------------------------------------------------------
Todas as árvores são forjadas em `tmp_path` e os "nós de /dev" são arquivos
comuns. Nada é aberto, nada é criado em `/dev/input`, nenhum aparelho é
tocado — disciplina da TEMPESTADE-DE-TECLADOS-01 aplicada ao lado dos scripts.
E nenhum teste daqui escreve em `docs/data/`: esta prova constrói a régua, e
quem preenche o mapa é ela, com o controle na mão.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations.no_do_vpad import (
    NO_DESCONHECIDO,
    resolver_no_do_vpad,
)
from hefesto_dualsense4unix.integrations.uhid_gamepad import VPAD_HID_PHYS
from hefesto_dualsense4unix.integrations.uinput_gamepad import XBOX360_NAME

_RAIZ = Path(__file__).resolve().parents[2]


def _carregar(nome_do_arquivo: str, apelido: str) -> Any:
    """Carrega um instrumento de `scripts/ensaios/` pelo caminho.

    `scripts/ensaios/` não é pacote, e o apelido em `sys.modules` é OUTRO de
    propósito: assim este arquivo nunca rouba o módulo de quem o importe pelo
    nome real. Mesmo precedente do `test_giro_e_buraco`.
    """
    alvo = _RAIZ / "scripts" / "ensaios" / nome_do_arquivo
    pasta = str(alvo.parent)
    if pasta not in sys.path:
        sys.path.insert(0, pasta)
    especificacao = importlib.util.spec_from_file_location(apelido, alvo)
    if especificacao is None or especificacao.loader is None:
        raise AssertionError(f"não consegui carregar {alvo}")
    modulo = importlib.util.module_from_spec(especificacao)
    sys.modules[apelido] = modulo
    especificacao.loader.exec_module(modulo)
    return modulo


APARELHO = _carregar(
    "o_jogo_segura_o_nosso_no.py", "o_jogo_segura_o_nosso_no_na_matriz"
)
LOG = _carregar("o_jogo_no_log_do_proton.py", "o_jogo_no_log_do_proton_na_matriz")


#: O `uniq` que o produto forja por jogador (faixa localmente administrada:
#: por definição não colide com endereço de fábrica).
UNIQ_P1 = "02:fe:00:00:00:01"

#: O placeholder canônico de fixture desta casa para um controle FÍSICO.
UNIQ_FISICO = "aa:bb:cc:00:00:11"

#: O nome que o Steam Input dá a cada espelho. A forma é LITERAL: a string do
#: `steamclient.so` dela é `Microsoft X-Box 360 pad %u`, lida por `strings(1)`
#: em 11/08/2026. O índice é o slot do controle espelhado — e o espelho do
#: NOSSO vpad é um destes, porque a Steam espelha tudo o que enxerga.
def _nome_do_espelho(indice: int) -> str:
    return f"Microsoft X-Box 360 pad {indice}"

NOME_DO_FISICO = "Sony Interactive Entertainment DualSense Wireless Controller"


def _nome_do_vpad(jogador: int) -> str:
    return f"DualSense Wireless Controller (Hefesto P{jogador})"


# ---------------------------------------------------------------------------
# A MESA DE TRÊS — uma árvore de sysfs forjada, servindo às duas réguas de
# aparelho. Nada aqui existe fora do `tmp_path`.
# ---------------------------------------------------------------------------


class Mesa:
    """`/sys/class/input` + `/dev` de mentira, na topologia exata do kernel.

    `/sys/class/input/eventN/device` é um symlink para `<device HID>/input/
    inputM`, e é subindo por ele que as duas réguas acham o device HID, o
    `uevent` e o `hidraw`. A topologia é reproduzida em vez de simplificada
    porque é ELA que as réguas navegam — uma mesa "equivalente porém mais
    simples" testaria outra coisa.
    """

    def __init__(self, raiz: Path) -> None:
        self.raiz = raiz
        self.class_input = raiz / "sys" / "class" / "input"
        self.devices = raiz / "sys" / "devices"
        self.dev_input = raiz / "dev" / "input"
        self.dev = raiz / "dev"
        for pasta in (self.class_input, self.devices, self.dev_input, self.dev):
            pasta.mkdir(parents=True, exist_ok=True)

    # -- os aparelhos com device HID (uhid: o nosso vpad e os físicos) -----

    def _no_hid(
        self,
        *,
        marca_do_dir: str,
        evento: str,
        nome: str,
        uniq: str,
        uevent: str,
        hidraw: str | None,
        bustype: str,
    ) -> Path:
        dir_hid = self.devices / marca_do_dir
        dir_input = dir_hid / "input" / f"input{evento[len('event'):]}"
        dir_input.mkdir(parents=True, exist_ok=True)
        (dir_hid / "uevent").write_text(uevent, encoding="utf-8")
        (dir_input / "name").write_text(nome + "\n", encoding="utf-8")
        (dir_input / "uniq").write_text(uniq + "\n", encoding="utf-8")
        (dir_input / "id").mkdir(parents=True, exist_ok=True)
        (dir_input / "id" / "bustype").write_text(bustype + "\n", encoding="utf-8")
        if hidraw:
            (dir_hid / "hidraw" / hidraw).mkdir(parents=True, exist_ok=True)
            (self.dev / hidraw).write_text("", encoding="utf-8")
        classe = self.class_input / evento
        classe.mkdir(parents=True, exist_ok=True)
        (classe / "device").symlink_to(dir_input, target_is_directory=True)
        (self.dev_input / evento).write_text("", encoding="utf-8")
        return dir_input

    def vpad_uhid(
        self, jogador: int, *, gamepad: str, hidraw: str, uniq: str | None = None
    ) -> None:
        """O nosso vpad no backend uhid: os TRÊS nós que um DualSense publica.

        A ordem é a que o kernel produz: o touchpad fica com o menor `eventN`.
        É ela que dá a mordida do desempate — quem escolhe "o primeiro que
        achou" leva o touchpad e mede o aparelho certo pelo nó errado.
        """
        uniq = uniq or f"02:fe:00:00:00:0{jogador}"
        base = int(gamepad[len("event") :])
        marca = f"virtual/misc/uhid/0003:054C:0DF2.000{jogador}"
        uevent = (
            "DRIVER=playstation\n"
            "HID_ID=0003:0000054C:00000DF2\n"
            f"HID_NAME={_nome_do_vpad(jogador)}\n"
            f"HID_PHYS={VPAD_HID_PHYS}\n"
            f"HID_UNIQ={uniq}\n"
        )
        nome = _nome_do_vpad(jogador)
        for evento, sufixo, hidraw_aqui in (
            (f"event{base - 2}", " Touchpad", None),
            (f"event{base - 1}", " Motion Sensors", None),
            (gamepad, "", hidraw),
        ):
            self._no_hid(
                marca_do_dir=marca,
                evento=evento,
                nome=nome + sufixo,
                uniq=uniq,
                uevent=uevent,
                hidraw=hidraw_aqui,
                bustype="0003",
            )

    def fisico(
        self,
        *,
        gamepad: str,
        hidraw: str,
        uniq: str = UNIQ_FISICO,
        nome: str = NOME_DO_FISICO,
        bustype: str = "0003",
        marca_do_dir: str = "pci0000:00/0003:054C:0CE6.0002",
    ) -> None:
        """Um DualSense FÍSICO: carimbo de fábrica no `HID_PHYS` e no `HID_UNIQ`."""
        uevent = (
            "DRIVER=playstation\n"
            f"HID_ID={bustype}:0000054C:00000CE6\n"
            f"HID_NAME={nome}\n"
            "HID_PHYS=usb-0000:0c:00.3-3/input3\n"
            f"HID_UNIQ={uniq}\n"
        )
        base = int(gamepad[len("event") :])
        for evento, sufixo, hidraw_aqui in (
            (f"event{base - 2}", " Touchpad", None),
            (f"event{base - 1}", " Motion Sensors", None),
            (gamepad, "", hidraw),
        ):
            self._no_hid(
                marca_do_dir=marca_do_dir,
                evento=evento,
                nome=nome + sufixo,
                uniq=uniq,
                uevent=uevent,
                hidraw=hidraw_aqui,
                bustype=bustype,
            )

    def edge_de_verdade(self, *, gamepad: str, hidraw: str) -> None:
        """Um DualSense **Edge** físico — o MESMO `054c:0df2` que o vpad forja.

        Existe para que "casar por vid/pid" tenha em quem tropeçar. Nada aqui
        é nosso: `HID_PHYS` é caminho USB e o `HID_UNIQ` é endereço forjado de
        fábrica.
        """
        self.fisico(
            gamepad=gamepad,
            hidraw=hidraw,
            uniq="aa:bb:cc:00:00:22",
            nome="Sony Interactive Entertainment DualSense Edge Wireless Controller",
            marca_do_dir="pci0000:00/0003:054C:0DF2.0009",
        )

    # -- os nós de uinput (o espelho do Steam e o nosso vpad degradado) -----

    def uinput(self, *, evento: str, nome: str) -> None:
        """Um nó de uinput: evdev PURO — sem `uniq`, sem device HID acima.

        É assim que o Steam Input publica cada espelho (`/dev/uinput`, §2.2 da
        pilha) e é assim que o nosso próprio vpad nasce no backend degradado.
        Os dois moram em `/sys/devices/virtual/input/inputN`, cujo PAI também
        se chama `input` — a armadilha que a exigência de `HID_ID` desarma.
        """
        dir_input = self.devices / "virtual" / "input" / f"input{evento[5:]}"
        dir_input.mkdir(parents=True, exist_ok=True)
        (dir_input / "name").write_text(nome + "\n", encoding="utf-8")
        (dir_input / "uniq").write_text("\n", encoding="utf-8")
        (dir_input / "id").mkdir(parents=True, exist_ok=True)
        (dir_input / "id" / "bustype").write_text("0003\n", encoding="utf-8")
        classe = self.class_input / evento
        classe.mkdir(parents=True, exist_ok=True)
        (classe / "device").symlink_to(dir_input, target_is_directory=True)
        (self.dev_input / evento).write_text("", encoding="utf-8")

    def espelho_do_steam(self, *, evento: str, indice: int = 0) -> None:
        """O espelho Xbox que o Steam Input faz de UM controle que enxergou."""
        self.uinput(evento=evento, nome=_nome_do_espelho(indice))

    # -- consultas -----------------------------------------------------------

    def resolver(self, uniq: str | None, nome: str | None) -> dict[str, Any]:
        """A régua 1 apontada para ESTA árvore, nunca para o `/sys` vivo."""
        return resolver_no_do_vpad(
            uniq=uniq,
            nome=nome,
            raiz_class_input=str(self.class_input),
            raiz_dev_input=str(self.dev_input),
            raiz_dev=str(self.dev),
        )

    def varrer(self) -> list[Any]:
        """A régua 2 (`vpads_do_sysfs`) apontada para ESTA árvore."""
        return APARELHO.vpads_do_sysfs(str(self.class_input))

    def ino(self, evento: str) -> int:
        return os.stat(self.dev_input / evento).st_ino


@pytest.fixture()
def mesa(tmp_path: Path) -> Mesa:
    return Mesa(tmp_path)


@pytest.fixture()
def mesa_de_tres(mesa: Mesa) -> Mesa:
    """A mesa MEDIDA na TRES-CONTROLES-01: físico, nosso vpad, e dois espelhos.

    Os números de `eventN` são escolhidos para que o FÍSICO fique com os
    menores: uma régua que caia em "o primeiro gamepad que achei" mede o
    aparelho dela, e é bom que isso apareça como reprovação e não como acaso.
    """
    mesa.fisico(gamepad="event4", hidraw="hidraw1")
    mesa.vpad_uhid(1, gamepad="event8", hidraw="hidraw5")
    mesa.espelho_do_steam(evento="event21", indice=0)
    mesa.espelho_do_steam(evento="event23", indice=1)
    return mesa


# ===========================================================================
# RÉGUA 1 — `integrations/no_do_vpad`: o produto declarando o próprio nó
# ===========================================================================


def test_r1_o_fisico_na_mesa_nao_vira_o_nosso_no(mesa_de_tres: Mesa) -> None:
    """Pergunta 1 da matriz: a régua 1 separa o nosso vpad do controle FÍSICO?

    MORDIDA: arrancar o filtro de `uniq` em `_candidatos` (ou casar por
    vid/pid, que é o que uma pessoa de boa-fé faria, já que o vpad forja
    `054c:0df2`). O físico tem o menor `eventN` desta mesa, então a régua
    passa a devolver `event4` — o nó DELA — dentro do bloco do nosso vpad.
    """
    no = mesa_de_tres.resolver(UNIQ_P1, _nome_do_vpad(1))

    assert no["evdev"] == str(mesa_de_tres.dev_input / "event8")
    assert no["ino"] == mesa_de_tres.ino("event8")
    assert no["hidraw"] == str(mesa_de_tres.dev / "hidraw5")

    # e o físico não encostou em nenhum dos quatro campos
    assert no["ino"] != mesa_de_tres.ino("event4")
    assert "hidraw1" not in str(no["hidraw"])


def test_r1_o_edge_de_verdade_tem_o_nosso_vidpid_e_nao_e_nosso(mesa: Mesa) -> None:
    """O par `054c:0df2` é do DualSense **Edge**, que existe de verdade.

    O vpad o forja de propósito e forja bem. Se a única coisa na mesa for um
    Edge físico, a resposta certa é NÃO SEI — e não "achei, é este".
    """
    mesa.edge_de_verdade(gamepad="event8", hidraw="hidraw3")

    assert mesa.resolver(UNIQ_P1, _nome_do_vpad(1)) == NO_DESCONHECIDO


def test_r1_o_espelho_xbox_do_nosso_vpad_nao_e_o_nosso_vpad(mesa: Mesa) -> None:
    """Pergunta 2 da matriz, no backend UINPUT — o caso vivo na máquina dela.

    O Steam Input espelha CADA controle que enxerga, o nosso vpad inclusive, e
    os espelhos se chamam `Microsoft X-Box 360 pad 0`/`1`. O nosso vpad de
    uinput se chama `Microsoft X-Box 360 pad (Hefesto - Dualsense4Unix
    virtual)`: os três começam com a MESMA palavra.

    MORDIDA: trocar o `!=` exato de `_candidatos` por `startswith("Microsoft
    X-Box 360 pad")`. Os dois espelhos entram como candidatos, viram três
    homônimos, e a régua devolve o espelho de menor `eventN` — ou, com a
    recusa por ambiguidade, para de responder sobre um vpad que existe.
    """
    mesa.espelho_do_steam(evento="event21", indice=0)
    mesa.espelho_do_steam(evento="event23", indice=1)
    mesa.uinput(evento="event30", nome=XBOX360_NAME)

    no = mesa.resolver(None, XBOX360_NAME)

    assert no["evdev"] == str(mesa.dev_input / "event30")
    assert no["ino"] == mesa.ino("event30")
    assert no["ino"] not in (mesa.ino("event21"), mesa.ino("event23"))
    # uinput é evdev puro: dizer um hidraw seria inventar
    assert no["hidraw"] is None


def test_r1_o_espelho_do_nosso_vpad_uhid_nao_rouba_o_lugar(
    mesa_de_tres: Mesa,
) -> None:
    """O mesmo, no backend UHID: o espelho existe na mesa e é ignorado.

    Aqui a régua tem `uniq` para casar, e o espelho — evdev puro — não tem
    `uniq` nenhum. O teste existe porque a mesa REAL é esta: o espelho não
    desaparece quando o vpad é uhid, ele fica na mesa ao lado.
    """
    no = mesa_de_tres.resolver(UNIQ_P1, _nome_do_vpad(1))

    assert no["ino"] not in (
        mesa_de_tres.ino("event21"),
        mesa_de_tres.ino("event23"),
    )


def test_r1_coop_de_uinput_e_ambiguo_e_a_regua_recusa(mesa: Mesa) -> None:
    """FALHA (a) — achada por esta prova em 20/08/2026, e curada.

    `XBOX360_NAME` é UMA constante, sem número de jogador. No co-op do backend
    uinput os vpads são HOMÔNIMOS, e o kernel não guarda `uniq` nem device HID
    onde diferenciá-los: não existe, no sistema, o dado que responderia "qual
    destes é o de P2".

    Antes da cura a régua devolvia o de menor `eventN` para TODOS os
    jogadores — medido: P1 e P2 recebiam `event10`, com confiança, sem `None`
    e sem aviso —, e o `state_full` publicava o inode de P1 dentro do bloco de
    P2. Quem lesse o payload para preencher o mapa afirmaria sobre o jogador
    errado.

    MORDIDA: arrancar a guarda `if not uniq_norm and len(candidatos) > 1` de
    `resolver_no_do_vpad`. Os dois blocos voltam a apontar para o mesmo nó.
    """
    mesa.uinput(evento="event10", nome=XBOX360_NAME)
    mesa.uinput(evento="event12", nome=XBOX360_NAME)

    p1 = mesa.resolver(None, XBOX360_NAME)
    p2 = mesa.resolver(None, XBOX360_NAME)

    assert p1 == NO_DESCONHECIDO
    assert p2 == NO_DESCONHECIDO
    # o defeito curado, dito na forma em que ele aparecia:
    assert not (p1["ino"] is not None and p1["ino"] == p2["ino"])


def test_r1_um_vpad_de_uinput_sozinho_continua_resolvendo(mesa: Mesa) -> None:
    """A cura de (a) recusa a AMBIGUIDADE, não o backend uinput.

    Irmão obrigatório do teste acima: uma guarda que recusasse sempre passaria
    nele e mataria o campo justamente na configuração viva da máquina dela.
    Um vpad de uinput sozinho é caso NÃO ambíguo, e tem de resolver.
    """
    mesa.espelho_do_steam(evento="event21", indice=0)
    mesa.uinput(evento="event30", nome=XBOX360_NAME)

    no = mesa.resolver(None, XBOX360_NAME)

    assert no["evdev"] == str(mesa.dev_input / "event30")


def test_r1_com_uniq_os_tres_nos_do_aparelho_nao_sao_ambiguidade(
    mesa_de_tres: Mesa,
) -> None:
    """A outra metade da cura: com `uniq`, ser plural é NORMAL.

    Um DualSense publica três nós com o MESMO `uniq` (gamepad, touchpad e
    sensores). Se a guarda de ambiguidade valesse também para o caminho do
    `uniq`, o vpad uhid — que é o backend bom — pararia de resolver. Aqui a
    pluralidade se desempata pelo nome exato, e o que sai é o gamepad.
    """
    no = mesa_de_tres.resolver(UNIQ_P1, _nome_do_vpad(1))

    assert no["evdev"] == str(mesa_de_tres.dev_input / "event8")
    assert no["ino"] != mesa_de_tres.ino("event6")  # o "Touchpad"
    assert no["ino"] != mesa_de_tres.ino("event7")  # o "Motion Sensors"


def test_r1_sem_o_nosso_vpad_na_mesa_a_resposta_e_nao_sei(mesa: Mesa) -> None:
    """Pergunta 3 da matriz: a régua 1 recusa quando não sabe?

    Mesa cheia — um físico e dois espelhos —, e o nosso vpad ausente. É o
    estado da máquina com o daemon parado.

    MORDIDA: qualquer fallback do tipo "devolve o primeiro gamepad que achou".
    Ele passaria a afirmar o nó do controle FÍSICO dela dentro do payload do
    produto, que é a pior forma deste defeito: plausível, confiante e errada.
    """
    mesa.fisico(gamepad="event4", hidraw="hidraw1")
    mesa.espelho_do_steam(evento="event21", indice=0)
    mesa.espelho_do_steam(evento="event23", indice=1)

    assert mesa.resolver(UNIQ_P1, _nome_do_vpad(1)) == NO_DESCONHECIDO


def test_r1_o_hidraw_do_vizinho_nao_e_afirmado(mesa: Mesa) -> None:
    """Recusa parcial: o nó é nosso, o `hidraw` do pai NÃO confirma.

    A confirmação pelo `uevent` do device HID pai é a segunda régua da régua
    1, e ela pode reprovar sozinha: nó nosso com pai de outro aparelho devolve
    `evdev` preenchido e `hidraw` `None`. "Não sei uma parte" é uma resposta
    melhor do que um `hidraw` plausível e alheio — e é no `hidraw` que a
    escrita acontece.
    """
    mesa.vpad_uhid(1, gamepad="event8", hidraw="hidraw5")
    alheio = (
        "DRIVER=playstation\n"
        "HID_ID=0003:0000054C:00000CE6\n"
        "HID_NAME=Sony Interactive Entertainment DualSense Wireless Controller\n"
        "HID_PHYS=usb-0000:0c:00.3-3/input3\n"
        f"HID_UNIQ={UNIQ_FISICO}\n"
    )
    pai = mesa.devices / "virtual" / "misc" / "uhid" / "0003:054C:0DF2.0001"
    (pai / "uevent").write_text(alheio, encoding="utf-8")

    no = mesa.resolver(UNIQ_P1, _nome_do_vpad(1))

    assert no["evdev"] == str(mesa.dev_input / "event8")
    assert no["hidraw"] is None
    assert no["hidraw_ino"] is None


# ===========================================================================
# RÉGUA 2 — `o_jogo_segura_o_nosso_no.py`: quem tem o inode na mão
# ===========================================================================


def test_r2_na_mesa_de_tres_so_o_nosso_vpad_e_nosso(mesa_de_tres: Mesa) -> None:
    """Perguntas 1 e 2 da matriz, de uma vez: quatro aparelhos, um alvo.

    A varredura independente (régua B: sysfs, sem perguntar nada ao daemon)
    tem de sair da mesa de TRÊS com os nós do nosso vpad e nada mais — nem o
    físico, nem os dois espelhos.

    MORDIDA (a do físico): trocar `e_vpad_do_hefesto` por um teste de vid/pid.
    MORDIDA (a do espelho): trocar o `==` exato do nome por `startswith`.
    """
    achados = mesa_de_tres.varrer()
    eventos = sorted(no.evento for no in achados)

    assert eventos == ["event6", "event7", "event8"]
    for no in achados:
        assert no.uniq.lower() == UNIQ_P1
        assert "X-Box" not in no.nome
        assert no.nome != NOME_DO_FISICO


def test_r2_o_espelho_de_uinput_nao_entra_nem_quando_o_vpad_tambem_e_uinput(
    mesa: Mesa,
) -> None:
    """O caso mais apertado do espelho: os dois lados são uinput.

    Sem `uniq`, sem device HID, sem carimbo nenhum no kernel — a única marca
    que sobra é o nome, lido do FONTE do produto. Três nós, prefixo idêntico,
    e só um é nosso.

    MORDIDA: `startswith("Microsoft X-Box 360 pad")` no lugar do `==`. Os dois
    espelhos entram como alvos NOSSOS, e um jogo que segure o espelho passa a
    sair como `SEGURA O NOSSO NÓ` — uma célula de mapa preenchida com o
    aparelho errado.
    """
    mesa.espelho_do_steam(evento="event21", indice=0)
    mesa.espelho_do_steam(evento="event23", indice=1)
    mesa.uinput(evento="event30", nome=XBOX360_NAME)

    achados = mesa.varrer()

    assert [no.evento for no in achados] == ["event30"]
    assert achados[0].nome == XBOX360_NAME


def test_r2_o_coop_de_uinput_da_dois_alvos_e_nao_inventa_o_jogador(
    mesa: Mesa,
) -> None:
    """O contraste com a falha (a): a régua 2 já tratava o co-op certo.

    Para o degrau `O JOGO RECEBEU` a pergunta é "o jogo segurou um nó NOSSO?",
    e os dois vpads de uinput são nossos — os dois entram. O que a régua 2 se
    recusa a fazer é dizer DE QUEM é cada um: `_rotulo_do_no` só usa o nome
    quando ele é único, e com homônimos cai para o `eventN`.

    Este teste é o espelho do `test_r1_coop_de_uinput_e_ambiguo_e_a_regua_
    recusa`: as duas réguas param no mesmo lugar, por caminhos diferentes.
    """
    mesa.uinput(evento="event10", nome=XBOX360_NAME)
    mesa.uinput(evento="event12", nome=XBOX360_NAME)

    achados = mesa.varrer()
    assert sorted(no.evento for no in achados) == ["event10", "event12"]

    do_produto = [_vpad_de_uinput(1), _vpad_de_uinput(2)]
    rotulos = {
        APARELHO._rotulo_do_no(no, None, do_produto) for no in achados
    }
    assert rotulos == {"event10", "event12"}
    assert not any(r.startswith("P") for r in rotulos)


def test_r2_o_censo_separa_quem_segura_o_nosso_de_quem_segura_o_fisico(
    tmp_path: Path,
) -> None:
    """Pergunta 1 da matriz no CENSO: dois vereditos, e não um.

    Dois jogos forjados, um com o inode do nosso nó na mão e outro com o do
    físico. Um censo que não discriminasse daria o mesmo veredito aos dois.

    MORDIDA: casar por `os.readlink` (o caminho) em vez do inode; ou colapsar
    as classes `nosso`/`físico` numa só.
    """
    nosso = tmp_path / "dev" / "input" / "event8"
    fisico = tmp_path / "dev" / "input" / "event4"
    for caminho in (nosso, fisico):
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text("", encoding="utf-8")

    alvos = [
        _alvo(nosso, classe="nosso"),
        _alvo(fisico, classe="físico"),
    ]
    proc = tmp_path / "proc"
    _processo(proc, 100, fds={"3": nosso})
    _processo(proc, 200, fds={"3": fisico})

    censo = APARELHO.censo_de_posse(alvos, str(proc))

    so_do_nosso, _ = APARELHO.decidir(alvos, censo, [100], [])
    so_do_fisico, _ = APARELHO.decidir(alvos, censo, [200], [])
    dos_dois, _ = APARELHO.decidir(alvos, censo, [100, 200], [])

    assert so_do_nosso == APARELHO.V_NOSSO
    assert so_do_fisico == APARELHO.V_FISICO
    assert dos_dois == APARELHO.V_DOIS
    assert len({so_do_nosso, so_do_fisico, dos_dois}) == 3


def test_r2_o_jogo_que_so_segura_o_espelho_cai_em_nenhum_e_esse_e_o_limite(
    tmp_path: Path,
) -> None:
    """O LIMITE DECLARADO — não é defeito curado, é decisão dela.

    A régua 2 não CONFUNDE o espelho com o nosso vpad: o espelho nunca vira
    alvo, e os testes acima mordem por isso. Mas ela também não tem NOME para
    ele. Um jogo que segure SÓ o espelho do nosso vpad — o caminho normal com
    o Steam Input ligado, em que a entrada que chega ao jogo é a NOSSA, lavada
    pela Steam — cai no veredito `NENHUM`, cujo texto afirma que *"nenhum
    deles segura o nosso nó nem o do físico. Isto é uma afirmação, não uma
    ausência de dado."*

    É afirmação verdadeira sobre fds e enganosa sobre a pergunta do mapa: a
    nossa entrada CHEGOU ao jogo, um andar acima. Curar isso é acrescentar uma
    classe de alvo e um sexto veredito ao léxico de cinco, e léxico de
    veredito é dela — a regra desta casa é partir do que já existe, não
    inventar nome novo por conta própria.

    Este teste prende o comportamento de HOJE para que a próxima pessoa
    encontre o limite escrito em vez de descobri-lo com uma célula errada no
    mapa. Se ela decidir o sexto veredito, é este teste que muda — e é para
    isso que ele existe.
    """
    nosso = tmp_path / "dev" / "input" / "event8"
    espelho = tmp_path / "dev" / "input" / "event21"
    for caminho in (nosso, espelho):
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text("", encoding="utf-8")

    alvos = [_alvo(nosso, classe="nosso")]
    proc = tmp_path / "proc"
    _processo(proc, 100, fds={"3": espelho})

    censo = APARELHO.censo_de_posse(alvos, str(proc))
    veredito, motivo = APARELHO.decidir(alvos, censo, [100], [])

    assert veredito == APARELHO.V_NENHUM
    assert "afirmação" in motivo
    # e o espelho não aparece em lugar nenhum do censo: ele não é alvo
    assert censo.posses == []


def test_r2_sem_alvo_nosso_a_resposta_e_nao_sondado_e_nunca_nenhum(
    tmp_path: Path,
) -> None:
    """Pergunta 3 da matriz: a régua 2 recusa quando não sabe?

    Mesa com o físico e o espelho, sem nenhum nó nosso resolvido — o estado da
    máquina com o daemon parado. `NENHUM` aqui responderia uma pergunta que
    não foi feita.

    MORDIDA: aceitar o alvo FÍSICO como suficiente para abrir a pergunta. O
    instrumento passa a dizer `NENHUM` — afirmação positiva — sobre um vpad
    que nem existia.
    """
    fisico = tmp_path / "dev" / "input" / "event4"
    fisico.parent.mkdir(parents=True, exist_ok=True)
    fisico.write_text("", encoding="utf-8")

    alvos = [_alvo(fisico, classe="físico")]
    proc = tmp_path / "proc"
    _processo(proc, 100, fds={})

    censo = APARELHO.censo_de_posse(alvos, str(proc))
    veredito, _ = APARELHO.decidir(alvos, censo, [100], [])

    assert veredito == APARELHO.V_NAO_SONDADO


def test_r2_alvo_nao_sondado_nao_conta_como_alvo(tmp_path: Path) -> None:
    """A recusa também vale para alvo cujo inode não se resolveu.

    Um `Alvo` com `chave=None` é um nó que a régua não conseguiu medir. Ele
    não pode abrir a pergunta: sem inode não há o que procurar em `/proc`, e
    contá-lo faria o instrumento afirmar `NENHUM` sobre um alvo cego.
    """
    fantasma = APARELHO.Alvo(
        classe="nosso",
        rotulo="P1",
        papel="gamepad",
        caminho="/dev/input/event8",
        chave=None,
        reguas="A (produto)",
        nota="NÃO SONDADO — o nó publicado não existe mais",
    )
    proc = tmp_path / "proc"
    _processo(proc, 100, fds={})

    censo = APARELHO.censo_de_posse([fantasma], str(proc))
    veredito, _ = APARELHO.decidir([fantasma], censo, [100], [])

    assert not fantasma.sondado
    assert veredito == APARELHO.V_NAO_SONDADO


# ===========================================================================
# RÉGUA 3 — `o_jogo_no_log_do_proton.py`: a fronteira do Wine
# ===========================================================================

WINEDEBUG = "+hid,+xinput,+plugplay"


def _cabecalho() -> list[str]:
    return [
        "======================",
        "Proton: 1774238111 GE-Proton10-34",
        "SteamGameId: 123456",
        "Command: ['/jogo/Jogo.exe']",
        f"Effective WINEDEBUG: {WINEDEBUG}",
        "======================",
        "00b4:trace:hid:build_initial_deviceset_direct Initial enumeration of /dev/hidraw*",
    ]


def _bloco_hid(
    no: str,
    *,
    phys: str,
    uniq: str,
    hid_id: str = "0003:0000054C:00000DF2",
    destino: str,
    thread: str = "00b4",
) -> list[str]:
    """Um nó COM device HID pai, do lado unix do winebus."""
    syspath = f"/sys/devices/virtual/misc/uhid/0003:054C:0DF2.000D/{Path(no).name}"
    linhas = [f'{thread}:trace:hid:udev_add_device udev "{no}" syspath {syspath}']
    for chave, valor in (
        ("DRIVER", "playstation"),
        ("HID_ID", hid_id),
        ("HID_NAME", "DualSense Wireless Controller"),
        ("HID_PHYS", phys),
        ("HID_UNIQ", uniq),
    ):
        linhas.append(
            f'{thread}:trace:hid:get_device_subsystem_info hid uevent "{chave}={valor}"'
        )
    linhas.append(f'{thread}:trace:hid:udev_add_device evdev "{no}": {destino}')
    return linhas


def _bloco_do_espelho(no: str, *, indice: int = 0, thread: str = "00b4") -> list[str]:
    """O espelho do Steam do lado unix: uinput PURO, sem `uevent` de HID.

    Um device de `/dev/uinput` não tem device HID pai, então o winebus não
    publica `HID_PHYS` nem `HID_UNIQ` nenhum para ele — só o `uevent` do
    subsistema `input`. É por essa AUSÊNCIA que ele não pode ser nosso, e é
    por isso que herdar o carimbo de outro nó era tão grave.
    """
    syspath = f"/sys/devices/virtual/input/input{indice + 21}"
    return [
        f'{thread}:trace:hid:udev_add_device udev "{no}" syspath {syspath}',
        f'{thread}:trace:hid:get_device_subsystem_info input uevent '
        f'"NAME=\\"Microsoft X-Box 360 pad {indice}\\""',
        f'{thread}:trace:hid:get_device_subsystem_info input uevent '
        f'"PRODUCT=3/28de/11ff/0110"',
        f'{thread}:trace:hid:udev_add_device evdev "{no}": '
        "{vid 28de, pid 11ff, version 0110, input 0, uid 00000000, "
        "is_gamepad 1, is_hidraw 0, bus_type 3}.",
    ]


def _pdo(handle: str, *, vidpid: str, uniq: str = "") -> list[str]:
    """O device do lado Windows. O `\\\\` é literal no log — não é escape meu."""
    instancia = f"0&{uniq}&0&0&0" if uniq else "0&0000&0&0&0"
    return [
        f"00b4:trace:hid:bus_create_hid_device created device {handle}/0x77e51800ade0",
        f"00b4:trace:hid:driver_add_device Adding device to PDO {handle}, "
        rf'id L"USB\\{vidpid}"\L"{instancia}".',
    ]


def _reports(handle: str, quantos: int) -> list[str]:
    linhas: list[str] = []
    for _ in range(quantos):
        linhas.append(
            f"00b4:trace:hid:process_hid_report device {handle} "
            "report_buf 0000000000C2CEF2 (0x1), report_len 0x40"
        )
        linhas.append(
            f"00b4:trace:hid:deliver_next_report device {handle}/0x77e51800ade0 "
            "input report length 64:"
        )
    return linhas


def _log(tmp_path: Path, linhas: list[str]) -> str:
    alvo = tmp_path / "steam-123456.log"
    alvo.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return str(alvo)


ADIADO = (
    "deferring {vid 054c, pid 0df2, version 8100, input -1, uid 00000000, "
    "is_gamepad 0, is_hidraw 0, bus_type 1} to a different backend"
)
IGNORADO = (
    "ignoring {vid 054c, pid 0ce6, version 0100, input 3, uid 00000000, "
    "is_gamepad 0, is_hidraw 0, bus_type 1}, in SDL ignore list"
)


def test_r3_o_fisico_entregando_report_nao_vira_o_nosso_no(tmp_path: Path) -> None:
    """Pergunta 1 da matriz na régua 3: separa o nosso nó do FÍSICO?

    O nosso nó foi enumerado e não entregou nada; o físico entregou 900
    reports. A resposta certa é `VIU O NOSSO NÓ, NÃO RECEBEU` — que é
    exatamente o sintoma de o jogo estar lendo o controle dela por cima do
    produto.

    MORDIDA: somar `reports_totais` em vez de `reports_nossos`. O veredito
    vira `RECEBEU DO NOSSO NÓ` com 900 reports de "prova" que nunca passaram
    pelo nosso nó.
    """
    linhas = _cabecalho()
    linhas += _bloco_hid(
        "/dev/input/event30", phys="hefesto-vpad", uniq=UNIQ_P1, destino=ADIADO
    )
    linhas += _bloco_hid(
        "/dev/input/event24",
        phys="usb-0000:0c:00.3-3/input3",
        uniq=UNIQ_FISICO,
        hid_id="0003:0000054C:00000CE6",
        destino=IGNORADO,
    )
    linhas += _pdo("00000000000C51210", vidpid="VID_054C&PID_0DF2", uniq=UNIQ_P1)
    linhas += _pdo("00000000000C5DAB0", vidpid="VID_054C&PID_0CE6", uniq=UNIQ_FISICO)
    linhas += _reports("00000000000C5DAB0", 900)

    log = LOG.ler_log(_log(tmp_path, linhas))
    decisao, razoes = LOG.veredicto(log)

    assert decisao == LOG.V_SO_VIU
    assert [no.no for no in LOG.nossos_nos(log)] == ["/dev/input/event30"]
    assert [d.handle for d in LOG.nossos_devices(log)] == ["00000000000C51210"]
    assert sum(d.processou for d in LOG.nossos_devices(log)) == 0
    assert any("NENHUM report atravessou" in r for r in razoes)


def test_r3_o_espelho_do_steam_nao_e_lido_como_nosso_no(tmp_path: Path) -> None:
    """Pergunta 2 da matriz na régua 3: separa o nosso nó do ESPELHO?

    O espelho aparece no log como um nó de uinput SEM `uevent` de HID, e do
    lado Windows como um PDO da Valve (`28de:11ff`) sem MAC na instância. Ele
    entrega 500 reports; o nosso nó, nenhum.

    MORDIDA: casar por vid/pid, ou aceitar qualquer device que entregue
    report. O espelho vira "o nosso nó" e o degrau `O JOGO RECEBEU` fecha com
    a entrada da Steam no lugar da nossa.
    """
    linhas = _cabecalho()
    linhas += _bloco_hid(
        "/dev/input/event30", phys="hefesto-vpad", uniq=UNIQ_P1, destino=ADIADO
    )
    linhas += _bloco_do_espelho("/dev/input/event21", indice=0)
    linhas += _pdo("00000000000C51210", vidpid="VID_054C&PID_0DF2", uniq=UNIQ_P1)
    linhas += _pdo("00000000000C99999", vidpid="VID_28DE&PID_11FF")
    linhas += _reports("00000000000C99999", 500)

    log = LOG.ler_log(_log(tmp_path, linhas))
    decisao, _ = LOG.veredicto(log)

    espelho = next(no for no in log.nos if no.no == "/dev/input/event21")
    assert espelho.e_nosso is False
    assert espelho.hid_phys == ""
    assert espelho.hid_uniq == ""
    assert [d.handle for d in LOG.nossos_devices(log)] == ["00000000000C51210"]
    assert decisao == LOG.V_SO_VIU


def test_r3_o_espelho_nao_herda_o_nosso_carimbo_da_thread_vizinha(
    tmp_path: Path,
) -> None:
    """FALHA (b) — achada por esta prova em 20/08/2026, e curada.

    O parser tinha UM slot de "nó aberto" e atribuía cada linha de `uevent` a
    quem abrira por último, sem olhar de qual thread do Wine ela vinha — mesmo
    já extraindo a thread no regex da linha. Bastava o espelho abrir na thread
    `00cc` enquanto o nosso vpad publicava o `uevent` dele na `00b4` para o
    espelho ficar com `HID_PHYS=hefesto-vpad` e ser contado como nosso.

    MEDIDO: antes da cura, `e_nosso` do `/dev/input/event21` saía `True`, com
    o nosso `phys` e o nosso `uniq` colados nele.

    RESSALVA, também medida e dita na tela: no único log real desta casa a
    enumeração inteira sai de UMA thread (`00b4`), então isto era latente. E
    aquele log não tinha espelho nenhum, o que o impede de ser prova de que a
    enumeração continua com uma thread só quando há espelho na mesa.

    MORDIDA: voltar o slot único (`abertos[thread]` para uma variável só).
    """
    linhas = _cabecalho()
    linhas += [
        # o espelho ABRE na thread vizinha...
        '00cc:trace:hid:udev_add_device udev "/dev/input/event21" '
        "syspath /sys/devices/virtual/input/input21",
        # ...e o nosso vpad publica o `uevent` DELE na thread da enumeração
        '00b4:trace:hid:get_device_subsystem_info hid uevent "HID_PHYS=hefesto-vpad"',
        f'00b4:trace:hid:get_device_subsystem_info hid uevent "HID_UNIQ={UNIQ_P1}"',
        '00cc:trace:hid:udev_add_device evdev "/dev/input/event21": '
        "{vid 28de, pid 11ff, version 0110, input 0, uid 00000000, "
        "is_gamepad 1, is_hidraw 0, bus_type 3}.",
    ]

    log = LOG.ler_log(_log(tmp_path, linhas))
    espelho = next(no for no in log.nos if no.no == "/dev/input/event21")

    assert espelho.e_nosso is False
    assert espelho.hid_phys == ""
    assert espelho.hid_uniq == ""
    assert LOG.nossos_nos(log) == []


def test_r3_o_uevent_continua_grudando_no_no_certo_da_mesma_thread(
    tmp_path: Path,
) -> None:
    """Irmão obrigatório da cura (b): ela separa threads, não desliga o parser.

    Um slot por thread que nunca casasse nada passaria no teste acima e
    tornaria a régua 3 cega para tudo. Aqui a enumeração é single-thread, como
    no log REAL, e o carimbo tem de continuar grudando.
    """
    linhas = _cabecalho()
    linhas += _bloco_hid(
        "/dev/input/event30", phys="hefesto-vpad", uniq=UNIQ_P1, destino=ADIADO
    )
    linhas += _pdo("00000000000C51210", vidpid="VID_054C&PID_0DF2", uniq=UNIQ_P1)
    linhas += _reports("00000000000C51210", 12)

    log = LOG.ler_log(_log(tmp_path, linhas))
    decisao, _ = LOG.veredicto(log)

    nosso = next(no for no in log.nos if no.no == "/dev/input/event30")
    assert nosso.e_nosso is True
    assert nosso.hid_phys == "hefesto-vpad"
    assert decisao == LOG.V_RECEBEU


def test_r3_duas_threads_enumerando_nao_se_misturam(tmp_path: Path) -> None:
    """A cura (b) sob a forma geral: dois nós, duas threads, intercalados.

    O caso do teste anterior é o do log real; este é o que o parser tem de
    aguentar se a enumeração um dia sair de duas threads. Cada carimbo fica
    com o seu nó.
    """
    linhas = _cabecalho()
    linhas += [
        '00b4:trace:hid:udev_add_device udev "/dev/input/event30" '
        "syspath /sys/devices/virtual/misc/uhid/0003:054C:0DF2.000D/event30",
        '00cc:trace:hid:udev_add_device udev "/dev/input/event24" '
        "syspath /sys/devices/pci0000:00/0003:054C:0CE6.0002/event24",
        '00b4:trace:hid:get_device_subsystem_info hid uevent "HID_PHYS=hefesto-vpad"',
        '00cc:trace:hid:get_device_subsystem_info hid uevent '
        '"HID_PHYS=usb-0000:0c:00.3-3/input3"',
        f'00cc:trace:hid:get_device_subsystem_info hid uevent "HID_UNIQ={UNIQ_FISICO}"',
        f'00b4:trace:hid:get_device_subsystem_info hid uevent "HID_UNIQ={UNIQ_P1}"',
    ]

    log = LOG.ler_log(_log(tmp_path, linhas))
    por_no = {no.no: no for no in log.nos}

    assert por_no["/dev/input/event30"].hid_phys == "hefesto-vpad"
    assert por_no["/dev/input/event30"].hid_uniq == UNIQ_P1
    assert por_no["/dev/input/event24"].hid_phys == "usb-0000:0c:00.3-3/input3"
    assert por_no["/dev/input/event24"].hid_uniq == UNIQ_FISICO
    assert [no.no for no in LOG.nossos_nos(log)] == ["/dev/input/event30"]


def test_r3_so_o_espelho_no_log_e_recebeu_de_outro_no(tmp_path: Path) -> None:
    """O nosso nó ausente e o espelho entregando: `RECEBEU DE OUTRO NÓ`.

    É o veredito que separa "o jogo não recebeu nada" de "o jogo recebeu, mas
    não de nós" — e é a única coisa que a régua 3 vê e a régua 2 não, porque
    posse de fd não distingue enumerar de ler.
    """
    linhas = _cabecalho()
    linhas += _bloco_do_espelho("/dev/input/event21", indice=0)
    linhas += _pdo("00000000000C99999", vidpid="VID_28DE&PID_11FF")
    linhas += _reports("00000000000C99999", 500)

    log = LOG.ler_log(_log(tmp_path, linhas))
    decisao, razoes = LOG.veredicto(log)

    assert decisao == LOG.V_OUTRO
    assert LOG.nossos_nos(log) == []
    assert LOG.nossos_devices(log) == []
    assert any("nenhum traço do nosso carimbo" in r for r in razoes)


def test_r3_espelho_sem_report_nenhum_e_nenhum_e_nao_nao_sondado(
    tmp_path: Path,
) -> None:
    """Pergunta 3 da matriz: a régua 3 recusa quando não sabe — e afirma quando sabe.

    Aqui o censo FECHOU (o canal estava ligado, a enumeração rodou, os nós
    foram considerados) e nada entregou report. `NENHUM` é a afirmação certa,
    e transformá-la em `NÃO SONDADO` seria prudência decorativa — o erro
    simétrico, que faz o veredito nunca sair.
    """
    linhas = _cabecalho()
    linhas += _bloco_do_espelho("/dev/input/event21", indice=0)
    linhas += _bloco_hid(
        "/dev/input/event24",
        phys="usb-0000:0c:00.3-3/input3",
        uniq=UNIQ_FISICO,
        hid_id="0003:0000054C:00000CE6",
        destino=IGNORADO,
    )

    log = LOG.ler_log(_log(tmp_path, linhas))
    decisao, _ = LOG.veredicto(log)

    assert decisao == LOG.V_NENHUM


def test_r3_sem_o_canal_de_hid_nao_ha_veredito(tmp_path: Path) -> None:
    """A recusa que vem ANTES de qualquer contagem.

    Um log gravado sem `+hid` não tem como responder, e a ausência de linha
    ali é cegueira do instrumento, não silêncio do jogo. Contar primeiro e
    conferir a procedência depois é como se imprime `NENHUM` sobre um log que
    nunca olhou para aparelho nenhum.
    """
    linhas = [
        "======================",
        "Proton: 1774238111 GE-Proton10-34",
        "SteamGameId: 123456",
        "Effective WINEDEBUG: +plugplay",
        "======================",
    ]

    log = LOG.ler_log(_log(tmp_path, linhas))
    decisao, razoes = LOG.veredicto(log)

    assert decisao == LOG.V_NAO_SONDADO
    assert any("WINEDEBUG" in r for r in razoes)


# ===========================================================================
# A MATRIZ FECHA — as três réguas, a MESMA mesa, respostas coerentes
# ===========================================================================


def test_a_matriz_fecha_as_tres_reguas_recusam_o_espelho_e_o_fisico(
    mesa_de_tres: Mesa, tmp_path: Path
) -> None:
    """O fecho: as três réguas, a mesma mesa de quatro aparelhos, um só nosso.

    Este teste não acrescenta critério nenhum — ele impede que as três réguas
    se afastem. Uma matriz em que cada linha é testada num arquivo diferente
    permite que duas delas passem a discordar sobre quem é o nosso vpad sem
    que teste nenhum reprove.
    """
    # régua 1: o produto declara o nó
    r1 = mesa_de_tres.resolver(UNIQ_P1, _nome_do_vpad(1))
    assert r1["evdev"] == str(mesa_de_tres.dev_input / "event8")

    # régua 2: a varredura independente do sysfs
    r2 = mesa_de_tres.varrer()
    assert sorted(no.evento for no in r2) == ["event6", "event7", "event8"]

    # as duas concordam sobre o gamepad, e é por INODE que elas concordam
    gamepad = next(no for no in r2 if no.papel == "gamepad")
    assert gamepad.caminho.endswith("event8")
    assert r1["ino"] == mesa_de_tres.ino("event8")

    # régua 3: o mesmo vpad atravessando a fronteira do Wine, com o espelho e
    # o físico na mesa junto
    linhas = _cabecalho()
    linhas += _bloco_hid(
        "/dev/input/event8", phys="hefesto-vpad", uniq=UNIQ_P1, destino=ADIADO
    )
    linhas += _bloco_hid(
        "/dev/input/event4",
        phys="usb-0000:0c:00.3-3/input3",
        uniq=UNIQ_FISICO,
        hid_id="0003:0000054C:00000CE6",
        destino=IGNORADO,
    )
    linhas += _bloco_do_espelho("/dev/input/event21", indice=0)
    linhas += _pdo("00000000000C51210", vidpid="VID_054C&PID_0DF2", uniq=UNIQ_P1)
    linhas += _reports("00000000000C51210", 42)

    log = LOG.ler_log(_log(tmp_path, linhas))
    decisao, _ = LOG.veredicto(log)

    assert [no.no for no in LOG.nossos_nos(log)] == ["/dev/input/event8"]
    assert decisao == LOG.V_RECEBEU


def test_nenhuma_regua_desta_prova_escreve_no_mapa() -> None:
    """A regra absoluta do pedido, prendida por teste: zero células.

    Esta prova constrói a régua; quem preenche o caderno é ela, com o controle
    na mão e o jogo aberto. Um teste que escrevesse em `docs/data/` fabricaria
    justamente o defeito que o portão `ensaio-nao-diz-o-degrau` existe para
    impedir — e este arquivo é longo o bastante para esconder uma linha dessas.

    ELE LÊ A ÁRVORE SINTÁTICA, e não o texto. A primeira versão procurava a
    palavra `mapa-controles.csv` no fonte e reprovou na própria docstring do
    arquivo, que cita o caminho para explicar por que o degrau estava vazio —
    o mesmo tropeço que o `test_o_instrumento_nao_escreve_em_lugar_nenhum` da
    régua 3 já tinha registrado. Docstring é prosa; o que interessa é literal
    de código.
    """
    import ast

    arvore = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    # Sem esta linha o teste se acha a si mesmo: os literais da PENEIRA
    # (`"docs/"`, `".csv"`) são literais de código deste arquivo. Aconteceu na
    # primeira execução, e fica registrado porque é o modo de falha clássico de
    # um instrumento que se mede.
    arvore.body = [
        no
        for no in arvore.body
        if not (
            isinstance(no, ast.FunctionDef)
            and no.name == "test_nenhuma_regua_desta_prova_escreve_no_mapa"
        )
    ]
    docstrings = {
        id(no.body[0].value)
        for no in ast.walk(arvore)
        if isinstance(
            no, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        )
        and no.body
        and isinstance(no.body[0], ast.Expr)
        and isinstance(no.body[0].value, ast.Constant)
        and isinstance(no.body[0].value.value, str)
    }
    literais = [
        no.value
        for no in ast.walk(arvore)
        if isinstance(no, ast.Constant)
        and isinstance(no.value, str)
        and id(no) not in docstrings
    ]

    suspeitos = [t for t in literais if "docs/" in t or t.endswith(".csv")]
    assert suspeitos == [], f"literal de código apontando para o caderno: {suspeitos}"


# ---------------------------------------------------------------------------
# Forja de `/proc` e de alvos — usada pelos testes da régua 2
# ---------------------------------------------------------------------------


def _vpad_de_uinput(jogador: int) -> Any:
    """Um bloco `per_vpad` de vpad uinput, como o produto o publica hoje.

    Com a cura da falha (a), o nó sai `None` no co-op — que é o "não sei"
    honesto. Os campos existem (o daemon é novo), e é por isso que
    `campos_ausentes` é vazio: campo AUSENTE e campo `None` não são a mesma
    coisa, e confundir os dois é como o daemon velho vira "o daemon não sabe".
    """
    return APARELHO.VpadDoProduto(
        player=jogador,
        uniq=None,
        nome=XBOX360_NAME,
        backend="uinput",
        evdev=None,
        hidraw=None,
        ino=None,
        hidraw_ino=None,
        game_open=False,
        campos_ausentes=(),
    )


def _alvo(arquivo: Path, *, classe: str, papel: str = "gamepad") -> Any:
    st = arquivo.stat()
    return APARELHO.Alvo(
        classe=classe,
        rotulo="P1" if classe == "nosso" else UNIQ_FISICO,
        papel=papel,
        caminho=str(arquivo),
        chave=(st.st_dev, st.st_ino),
        reguas="B (sysfs)",
    )


def _processo(
    raiz: Path, pid: int, *, fds: dict[str, Path], cmdline: str = "Jogo.exe"
) -> None:
    """Um `/proc/<pid>` de mentira, com `fd/` de links para arquivos comuns."""
    dir_pid = raiz / str(pid)
    (dir_pid / "fd").mkdir(parents=True, exist_ok=True)
    (dir_pid / "cmdline").write_bytes(cmdline.encode("utf-8") + b"\0")
    (dir_pid / "environ").write_bytes(b"SteamAppId=123456\0")
    for numero, alvo in fds.items():
        (dir_pid / "fd" / numero).symlink_to(alvo)
