#!/usr/bin/env python3
"""o_jogo_segura_o_nosso_no.py — o jogo abriu o NOSSO nó, ou passou por fora?

A PERGUNTA QUE ELE RESPONDE
----------------------------
*Algum processo da árvore do jogo está com o nó do NOSSO vpad aberto, agora?*

E a pergunta gêmea, que é a que dói: *ou ele foi abrir o controle FÍSICO, por
fora de tudo o que o produto montou?*

O DEGRAU QUE ELE SUSTENTA
--------------------------
`O JOGO RECEBEU`, o primeiro degrau da direção de ENTRADA
(`scripts/check_paridade_transporte.py::ESCADA`). O critério está escrito lá, e
este arquivo obedece a ele literalmente:

    o INODE do nó do vpad (`stat -c %i`) aparece em `/proc/<pid>/fd` de um
    processo da árvore do jogo. (...) NUNCA case por caminho (o minor é
    reciclado: `event22` foi vpad DualSense às 01:40 e vpad Xbox às 01:50) e
    NUNCA pelo carimbo de tempo do fd (ele marca quando alguém OLHOU, e fica
    cacheado).

Até 20/08/2026 a direção de ENTRADA tinha **zero células** no mapa de canais,
porque não existia instrumento. Este é metade do instrumento; a outra metade é
`o_jogo_no_log_do_proton.py`, que responde a MESMA pergunta por régua
independente — portão em série engana, e duas réguas é o que revela quando uma
olha para o lugar errado.

**Ele não preenche célula nenhuma.** Ele MEDE; quem escreve no mapa é quem
olhou o resultado. Um instrumento que preenchesse sozinho seria o instrumento
confirmando a si mesmo, que é a armadilha nº 1 desta casa.

O QUE MUDA EM RELAÇÃO AO `quem_o_jogo_abre.py`, ITEM A ITEM
------------------------------------------------------------
Metade deste instrumento é aquele, e o que se aproveita se aproveita por
importação, não por cópia:

- **a árvore do jogo sai da MESMA função** (`quem_o_jogo_abre.arvore_do_jogo`),
  e não de uma segunda implementação — mas ela passa por uma ÂNCORA aqui, e a
  âncora nasceu de um falso positivo MEDIDO em 20/08/2026. Com nenhum jogo
  aberto, `arvore_do_jogo(r"\\.exe|Shipping")` devolveu DOIS processos nesta
  máquina: o `earlyoom`, cuja lista de `--avoid` cita a palavra, e um binário
  de outro programa cujo nome termina em `.exe`. Um deles bastaria para o
  instrumento imprimir "a árvore do jogo existe e não segura nada" — um
  `NENHUM` sobre um jogo que não está aberto. A âncora é a MESMA que o `processo_do_jogo` já
  usa e defende: `SteamAppId` no `environ`. Um processo que só MENCIONA `.exe`
  não a carrega; o `winedevice` de um jogo sob Proton carrega, porque herda o
  ambiente do lançamento;
- **o casamento do nó é por INODE, nunca por caminho.** O
  `quem_o_jogo_abre.py` faz `re.search(r"(event\\d+|hidraw\\d+)", os.readlink(fd))`
  — o caminho, que é um número de fila. O critério do degrau proíbe isso com
  todas as letras, e aqui o casamento é `os.stat` do fd contra `(st_dev,
  st_ino)` do nosso nó. `os.stat` **não abre nada**;
- **o par `(st_dev, st_ino)`, não o inode sozinho.** Número de inode só é único
  DENTRO de um sistema de arquivos: um fd para um arquivo comum de outro
  sistema de arquivos com o mesmo número casaria. O degrau fala em inode
  porque é o que `stat -c %i` mostra; o par é o mesmo critério, sem a colisão;
- **identidade pelo carimbo do produto, nunca por vid/pid.** O vpad forja
  `054c:0df2` (DualSense Edge) de propósito e forja bem — quem casa por vid/pid
  está a um Edge de verdade de distância de medir o aparelho errado. A régua é
  `identidade_do_vpad.e_vpad_do_hefesto`: `HID_PHYS = hefesto-vpad` e
  `HID_UNIQ` no prefixo `02:fe:`;
- **transporte pelo BARRAMENTO da perna FÍSICA**, com segunda rota. O vpad NÃO
  TEM transporte: ele forja `BUS_USB` no `UHID_CREATE2` e a leitura ingênua o
  classifica como cabo. Quem tem transporte é o controle que alimenta aquele
  vpad, e o barramento dele sai de `HID_ID` (rota 1) e do
  `/sys/class/input/eventN/device/id/bustype` (rota 2). **Topologia de sysfs
  NÃO serve**: com BlueZ >= 5.73 o físico de rádio mora sob
  `/devices/virtual/misc/uhid/`, no mesmo lugar do vpad — armadilha paga em
  11/08/2026;
- **ele diz `NÃO SONDADO`**, e diz sem constrangimento. O
  `quem_o_jogo_abre.py` imprime `1` e "o jogo está aberto?"; aqui a falta de
  sujeito é um veredito com nome, porque é isso que o mapa tem de receber.

AS DUAS RÉGUAS DO ALVO, E POR QUE SÃO DUAS
-------------------------------------------
- **Régua A — o produto DECLARA.** `daemon.state_full` publica, por vpad,
  `evdev`, `hidraw`, `ino`, `hidraw_ino` e `game_open` (QUEM-SEGURA-O-NOSSO-NO-01,
  20/08/2026). É o único que sabe sem adivinhar: ele carimbou o `phys` e o
  `uniq` no `UHID_CREATE2`.
- **Régua B — o kernel MOSTRA.** Varredura de `/sys/class/input/event*` por
  conta própria, com a régua compartilhada dos scripts
  (`identidade_do_vpad.e_vpad_do_hefesto`). É outra implementação da mesma
  pergunta, e é isso que a torna régua.

Discordância entre as duas — inode diferente, caminho que a outra não vê —
**não vira palpite**: aquele alvo sai `NÃO SONDADO`.

ONDE A RÉGUA B É FRACA, E ISSO SAI IMPRESSO
--------------------------------------------
No backend **uinput** o vpad não tem `uniq` nem device HID pai: não há carimbo
nenhum no kernel, e a única marca que sobra é o NOME — `XBOX360_NAME`, lido do
fonte do produto. Duas consequências, e as duas viajam no relatório:

1. a régua compartilhada `e_vpad_do_hefesto` **não reconhece** o vpad de
   uinput: ela procura `(Hefesto P` no nome, e o nome do uinput é
   `Microsoft X-Box 360 pad (Hefesto - Dualsense4Unix virtual)`. Por isso o
   ramo do nome existe aqui, à parte e declarado;
2. o casamento é por nome **EXATO**. O Steam Input publica um espelho Xbox de
   CADA controle que vê, o nosso vpad inclusive, e esses espelhos se chamam
   `Microsoft X-Box 360 pad 0`, `... 1`. Um casamento por prefixo abraçaria o
   espelho do Steam e mediria o aparelho errado.

O QUE ELE NÃO FAZ
------------------
**Não abre nó nenhum.** Nem para conferir. Abrir o `/dev/hidraw` do vpad
dispara `UHID_OPEN` e arma o modo jogo; fechá-lo por último deixa o controle
vibrando, porque o `_silence_rumble()` não roda. Ele lê `/proc` e `/sys` e faz
`os.stat`, que resolve caminho e não abre descritor.

Não escreve em aparelho, não abre nem fecha jogo, não toca na Steam, não mexe
em configuração, não cria dispositivo de entrada. O pior desfecho de um erro
aqui é um relatório errado.

E não fecha o degrau sozinho: `O JOGO REAGIU` é dela, e só dela.

OS CINCO VEREDITOS
-------------------
    SEGURA O NOSSO NÓ ............ um processo da árvore do jogo tem o inode
                                   de um nó nosso aberto. É o degrau.
    SEGURA O FÍSICO, NÃO O NOSSO . a árvore do jogo foi ao controle de
                                   verdade. O produto está fora do caminho.
    SEGURA OS DOIS ............... nosso E físico. É o sintoma do controle em
                                   dobro, e não é bom presságio.
    NENHUM ....................... a árvore do jogo existe, o censo DELA
                                   fechou, e ela não segura nem um nem outro.
                                   AFIRMAÇÃO POSITIVA — só se imprime com o
                                   censo fechado.
    NÃO SONDADO .................. não há árvore de jogo; ou o alvo não se
                                   resolveu; ou as duas réguas discordaram; ou
                                   o censo da árvore não fechou.

O CENSO QUE TEM DE FECHAR É O DA ÁRVORE, E NÃO O DO MUNDO
----------------------------------------------------------
A varredura de `/proc` é global — é ela que responde *"e quem está segurando,
então?"* —, mas o `NENHUM` é sobre o JOGO, e é o censo da ÁRVORE DELE que
precisa ter fechado. A diferença não é sutileza: nesta máquina há três
processos do próprio usuário que **nunca** se deixam ler
(`(sd-pam)` e dois `ssh-agent` zeram o `PR_SET_DUMPABLE` de propósito).
Exigir o mundo inteiro faria `NENHUM` ser inalcançável para sempre, e um
veredito inalcançável vira `NÃO SONDADO` decorativo — que é pior que não ter
veredito, porque parece prudência.

COMO USAR
----------
    .venv/bin/python scripts/ensaios/o_jogo_segura_o_nosso_no.py
    .venv/bin/python scripts/ensaios/o_jogo_segura_o_nosso_no.py --padrao Duskfade
    .venv/bin/python scripts/ensaios/o_jogo_segura_o_nosso_no.py --json

Rode com o jogo NA TELA, não no menu da Steam: o jogo só enumera controle
depois de subir. Sem jogo aberto ele roda igual e responde `NÃO SONDADO` — a
tabela de posse continua valendo, e é ela que mostra quem mais está com o
nosso nó na mão (o cliente Steam abre, e sessão aberta NÃO é evidência de
jogo: é o veto da NUMA-02).
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comum import (
    BUS_BLUETOOTH,
    BUS_USB,
    CABO,
    RADIO,
    Aparelho,
    cabecalho_do_instrumento,
    descobrir_aparelhos,
    fisicos,
    ler_texto,
    resumo,
    tabela,
)
from identidade_do_vpad import (
    VPAD_HID_PHYS,
    campos_do_uevent,
    e_vpad_do_hefesto,
)
from quem_o_jogo_abre import arvore_do_jogo

#: O produto é a fonte dos carimbos, e sem ele este instrumento não tem régua
#: nenhuma — só chute com cara de medição. A falta é BARULHENTA de propósito,
#: com o comando exato: o `python3` do sistema não enxerga o pacote, e um
#: instrumento que degradasse em silêncio aqui mediria o aparelho de outra
#: pessoa.
try:
    from hefesto_dualsense4unix.integrations.no_do_vpad import no_ainda_vale
    from hefesto_dualsense4unix.integrations.uhid_gamepad import (
        VPAD_HID_PHYS as PHYS_DO_PRODUTO,
    )
    from hefesto_dualsense4unix.integrations.uinput_gamepad import XBOX360_NAME
    from hefesto_dualsense4unix.utils.xdg_paths import ipc_socket_path

    PRODUTO_IMPORTAVEL = ""
except ImportError as _erro:  # pragma: no cover - só fora do venv do projeto
    PRODUTO_IMPORTAVEL = str(_erro)

VERSAO = "2026-08-20"

#: As duas raízes que este instrumento lê. Parametrizáveis só como COSTURA DE
#: TESTE, no mesmo molde do `integrations/no_do_vpad`: a suíte aponta para um
#: diretório temporário, e **nenhum teste desta casa varre o `/sys` ou o
#: `/proc` vivos da máquina dela** — nem para ler. É a disciplina da
#: TEMPESTADE-DE-TECLADOS-01, e ela não se aplica só a criar dispositivo: um
#: teste que lesse o `/sys` de verdade passaria ou reprovaria conforme o que
#: estivesse plugado na hora, que é o oposto de teste.
RAIZ_CLASS_INPUT = "/sys/class/input"
RAIZ_PROC = "/proc"

#: Os cinco vereditos. Ver o bloco OS CINCO VEREDITOS na docstring.
V_NOSSO = "SEGURA O NOSSO NÓ"
V_FISICO = "SEGURA O FÍSICO, NÃO O NOSSO"
V_DOIS = "SEGURA OS DOIS"
V_NENHUM = "NENHUM"
V_NAO_SONDADO = "NÃO SONDADO"

#: As cinco chaves que a QUEM-SEGURA-O-NOSSO-NO-01 acrescentou ao `per_vpad`.
#: A lista existe para separar dois silêncios que chegam iguais na tela:
#: chave AUSENTE é daemon MAIS VELHO que o código (install editable — a cura só
#: vale no próximo start); chave presente com `None` é o daemon dizendo "não
#: resolvi". O segundo é uma medição; o primeiro é a falta dela.
CAMPOS_DO_NO = ("evdev", "hidraw", "ino", "hidraw_ino", "game_open")

#: O papel de cada nó de entrada de um DualSense, pelo sufixo do nome. Um
#: aparelho publica três (ou quatro, com fone), e o jogo pode segurar
#: QUALQUER um deles — segurar o `Motion Sensors` é receber o nosso vpad tanto
#: quanto segurar o gamepad.
SUFIXOS_DE_PAPEL = (
    ("Motion Sensors", "movimento"),
    ("Touchpad", "touchpad"),
    ("Headset Jack", "fone"),
)

#: O padrão de cmdline que acha o jogo, o mesmo default do `quem_o_jogo_abre`.
PADRAO_DO_JOGO = r"\.exe|Shipping"

#: A ÂNCORA. Um processo só entra na árvore do jogo se carregar isto no
#: `environ`. É a mesma variável em que o `quem_o_jogo_abre.processo_do_jogo`
#: se apoia, e pelo mesmo motivo estrutural: ela existe no ambiente que a Steam
#: monta e é herdada por tudo o que o jogo gera, inclusive o `winedevice` que é
#: quem costuma segurar o dispositivo.
#:
#: MEDIDO em 20/08/2026, sem jogo nenhum aberto: o padrão default casou com o
#: `earlyoom` (a palavra `.exe` mora na lista de `--avoid` dele) e com um
#: binário de outro programa cujo nome termina em `.exe`. Sem a âncora, o
#: instrumento teria afirmado "a árvore do jogo existe e não segura nada"
#: sobre um jogo que não estava aberto — a classe de erro mais cara que um
#: instrumento comete aqui.
ANCORA_DO_JOGO = b"SteamAppId="


def _mascara(mac: str) -> str:
    """MAC com os octetos 4 e 5 zerados — a máscara desta casa.

    Isto é APRESENTAÇÃO, não medição: o casamento acontece por inode, e o MAC
    só aparece para quem lê saber de qual controle se fala. Mascarar aqui é o
    que impede um endereço real de escorregar para dentro de um relatório
    colado num arquivo versionado.
    """
    partes = mac.split(":")
    if len(partes) != 6:
        return mac
    return ":".join([*partes[:3], "00", "00", partes[5]])


def _chave(caminho: str) -> tuple[int, int] | None:
    """`(st_dev, st_ino)` de um caminho, ou `None`. **Não abre nada.**

    `os.stat` resolve o caminho e lê o inode; não há `open()`, então não há
    `UHID_OPEN`, não há modo jogo armado e não há contagem de quem fecha por
    último. É a razão de este instrumento poder rodar com o jogo aberto sem
    estragar a medição que está tentando fazer.

    O par, e não o `st_ino` sozinho: número de inode só é único dentro de um
    sistema de arquivos. Um fd para um arquivo comum de outro `st_dev` com o
    mesmo número casaria, e o falso positivo sairia convincente.
    """
    try:
        st = os.stat(caminho)
    except OSError:
        return None
    return (st.st_dev, st.st_ino)


# ---------------------------------------------------------------------------
# O ALVO — régua A: o produto declara
# ---------------------------------------------------------------------------


def estado_do_produto(timeout: float = 5.0) -> tuple[dict, str]:
    """`daemon.state_full` pelo socket do daemon: `({}, motivo)` se não deu.

    Uma chamada, no começo e só uma. Não é o instrumento perguntando ao
    produto o que ele deveria medir sozinho: é a régua A, e ela existe porque o
    produto é o único que sabe qual nó é dele sem adivinhar.

    O laço de `recv` até o `\\n` não é firula: o `state_full` desta casa passa
    de 64 KiB com a mesa cheia, e um `recv` só devolveria JSON cortado — que
    viraria "o daemon não respondeu" no relatório.
    """
    if PRODUTO_IMPORTAVEL:
        return {}, f"o pacote não é importável ({PRODUTO_IMPORTAVEL})"
    caminho = str(ipc_socket_path())
    if not os.path.exists(caminho):
        return {}, f"não há socket do daemon em {caminho}"
    pedido = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "daemon.state_full", "params": {}}
    )
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(caminho)
            sock.sendall(pedido.encode("utf-8") + b"\n")
            bruto = b""
            while not bruto.endswith(b"\n"):
                pedaco = sock.recv(65536)
                if not pedaco:
                    break
                bruto += pedaco
    except OSError as erro:
        return {}, f"o socket {caminho} não respondeu ({erro})"
    try:
        resposta = json.loads(bruto.decode("utf-8", "replace") or "{}")
    except ValueError as erro:
        return {}, f"resposta ilegível do daemon ({erro})"
    resultado = resposta.get("result")
    if not isinstance(resultado, dict):
        return {}, f"o daemon respondeu sem `result` ({resposta.get('error')})"
    return resultado, ""


@dataclass
class VpadDoProduto:
    """O que a régua A diz de UM vpad, e o que falta nela."""

    player: int
    uniq: str | None
    nome: str | None
    backend: str | None
    evdev: str | None
    hidraw: str | None
    ino: int | None
    hidraw_ino: int | None
    game_open: bool | None
    campos_ausentes: tuple[str, ...]

    @property
    def declara_o_no(self) -> bool:
        return not self.campos_ausentes and bool(self.evdev)


def vpads_do_produto(estado: dict) -> list[VpadDoProduto]:
    """Os blocos `rumble_ff.per_vpad` traduzidos, com o que falta neles.

    `per_vpad` não é chave de topo do payload — ela mora dentro de
    `rumble_ff`, ao lado dos contadores de força-feedback. Isso já custou
    tempo; fica escrito.
    """
    per_vpad = (estado.get("rumble_ff") or {}).get("per_vpad") or []
    achados: list[VpadDoProduto] = []
    for bloco in per_vpad:
        if not isinstance(bloco, dict):
            continue
        ausentes = tuple(c for c in CAMPOS_DO_NO if c not in bloco)
        achados.append(
            VpadDoProduto(
                player=int(bloco.get("player") or 0),
                uniq=bloco.get("vpad_uniq"),
                nome=bloco.get("vpad_nome"),
                backend=bloco.get("backend"),
                evdev=bloco.get("evdev"),
                hidraw=bloco.get("hidraw"),
                ino=bloco.get("ino"),
                hidraw_ino=bloco.get("hidraw_ino"),
                game_open=bloco.get("game_open"),
                campos_ausentes=ausentes,
            )
        )
    return achados


def fisico_por_jogador(estado: dict) -> dict[int, str]:
    """`player` -> MAC do controle FÍSICO que alimenta aquele vpad.

    Sai de `coop.mesa`, que é onde o produto publica a ligação vpad ↔ físico
    (QUEM-É-QUEM-01). Nenhum arquivo de `/sys` carrega essa ligação: o vpad
    nasce por `/dev/uhid` e não guarda ponteiro para o controle que o alimenta.
    Sem o daemon vivo, esta ponte simplesmente não existe — e o transporte sai
    `NÃO SONDADO`, que é a resposta honesta.
    """
    mesa = (estado.get("coop") or {}).get("mesa") or []
    fora: dict[int, str] = {}
    for item in mesa:
        if not isinstance(item, dict):
            continue
        uniq = item.get("uniq")
        numero = int(item.get("player") or 0)
        if isinstance(uniq, str) and uniq:
            fora[numero] = uniq
    return fora


# ---------------------------------------------------------------------------
# O ALVO — régua B: o kernel mostra
# ---------------------------------------------------------------------------


@dataclass
class NoDeEntrada:
    """Um `/dev/input/eventN` visto pelo sysfs: quem é, e como se soube."""

    evento: str
    caminho: str
    nome: str
    uniq: str
    papel: str
    marca: str
    dir_hid: str
    hidraw: str | None


def _papel_do_nome(nome: str) -> str:
    for sufixo, papel in SUFIXOS_DE_PAPEL:
        if nome.endswith(sufixo):
            return papel
    return "gamepad"


def _hid_pai(dir_device: str) -> tuple[str, dict[str, str]]:
    """`(diretório do device HID dono deste nó, campos do uevent dele)`.

    `/sys/class/input/eventN/device` resolve em `<device HID>/input/inputM`;
    dois níveis acima está o device HID.

    **A subida de dois níveis não basta como prova, e isto é medido.** O vpad
    de uinput resolve em `/sys/devices/virtual/input/input1499`: o pai
    TAMBÉM se chama `input`, então a regra "subiu dois e o pai era input, logo
    achei um device HID" entrega `/sys/devices/virtual` — um diretório que não
    é device nenhum. Aqui o candidato só passa se o `uevent` dele trouxer
    `HID_ID`, que é o que todo device HID publica e nenhum outro publica.
    Confirmar pelo que o diretório DIZ, e não pelo nome do avô, é a diferença
    entre régua e coincidência de caminho.

    Devolve `("", {})` quando não há device HID acima — o caminho uinput —, e
    é assim que quem chama sabe que não há hidraw a procurar.
    """
    try:
        alvo = os.path.realpath(dir_device)
    except OSError:
        return "", {}
    pai = os.path.dirname(alvo)
    if os.path.basename(pai) != "input":
        return "", {}
    candidato = os.path.dirname(pai)
    campos = campos_do_uevent(ler_texto(os.path.join(candidato, "uevent")))
    if "HID_ID" not in campos:
        return "", {}
    return candidato, campos


def _hidraw_do_hid(dir_hid: str) -> str | None:
    if not dir_hid:
        return None
    try:
        nos = sorted(os.listdir(os.path.join(dir_hid, "hidraw")))
    except OSError:
        return None
    for no in nos:
        if no.startswith("hidraw"):
            return f"/dev/{no}"
    return None


def vpads_do_sysfs(raiz: str | None = None) -> list[NoDeEntrada]:
    """Os nós de entrada que são vpad DESTE produto — varredura independente.

    Esta é a régua B. Ela não pergunta nada ao daemon: lê o `uniq` do nó, o
    `uevent` do device HID pai, e decide com
    `identidade_do_vpad.e_vpad_do_hefesto` — a régua que os scripts desta casa
    já compartilham, e que é outra IMPLEMENTAÇÃO da mesma pergunta que o
    `integrations/no_do_vpad` do produto responde. Duas implementações, uma
    pergunta: é isso que faz delas duas réguas, e não duas cópias.

    O ramo do NOME é o buraco declarado, e ele fica à parte de propósito. No
    backend uinput não há `uniq`, não há device HID pai e não há carimbo
    nenhum: o `e_vpad_do_hefesto` responde `False`, com razão, porque procura
    `(Hefesto P` e o nome do uinput não tem essa marca. O que sobra é o
    `XBOX360_NAME` lido do FONTE do produto — o que torna esta metade da régua
    independente do daemon VIVO, mas não do código. Casamento **exato**: o
    espelho Xbox que o Steam Input publica de cada controle se chama
    `Microsoft X-Box 360 pad 0`, e um prefixo o abraçaria.
    """
    raiz = RAIZ_CLASS_INPUT if raiz is None else raiz
    achados: list[NoDeEntrada] = []
    try:
        entradas = sorted(os.listdir(raiz))
    except OSError:
        return achados
    for entrada in entradas:
        if not entrada.startswith("event"):
            continue
        dir_device = os.path.join(raiz, entrada, "device")
        nome = ler_texto(os.path.join(dir_device, "name")).strip()
        uniq = ler_texto(os.path.join(dir_device, "uniq")).strip()
        dir_hid, campos = _hid_pai(dir_device)
        if e_vpad_do_hefesto(campos, uniq_do_no=uniq, nome=nome):
            marca = (
                f"HID_PHYS={VPAD_HID_PHYS}"
                if campos.get("HID_PHYS", "").strip().lower().startswith(
                    VPAD_HID_PHYS
                )
                else "carimbo do produto (uniq/nome)"
            )
        elif not PRODUTO_IMPORTAVEL and nome == XBOX360_NAME:
            marca = "nome EXATO do uinput (régua fraca — ver docstring)"
        else:
            continue
        achados.append(
            NoDeEntrada(
                evento=entrada,
                caminho=f"/dev/input/{entrada}",
                nome=nome,
                uniq=uniq,
                papel=_papel_do_nome(nome),
                marca=marca,
                dir_hid=dir_hid,
                hidraw=_hidraw_do_hid(dir_hid),
            )
        )
    return achados


def nos_de_entrada_do_hid(dir_device: str) -> list[tuple[str, str]]:
    """`[(nome, /dev/input/eventN)]` de um device HID, pelo sysfs.

    Variante de `quem_e_quem._nos_de_entrada`, e a diferença é deliberada: lá
    a saída é um mapa `papel -> caminho`, que guarda UM nó por papel; aqui
    interessam TODOS os nós, porque a pergunta é "o jogo segurou algum deles?"
    e a resposta não pode perder o quarto nó por ele não ter papel próprio.
    """
    fora: list[tuple[str, str]] = []
    raiz = os.path.join(dir_device, "input")
    if not os.path.isdir(raiz):
        return fora
    try:
        entradas = sorted(os.listdir(raiz))
    except OSError:
        return fora
    for entrada in entradas:
        dir_input = os.path.join(raiz, entrada)
        if not os.path.isdir(dir_input):
            continue
        nome = ler_texto(os.path.join(dir_input, "name")).strip()
        try:
            filhos = sorted(os.listdir(dir_input))
        except OSError:
            continue
        for sub in filhos:
            if sub.startswith("event"):
                fora.append((nome, f"/dev/input/{sub}"))
    return fora


# ---------------------------------------------------------------------------
# O transporte da perna FÍSICA — duas rotas, e discordância vira NÃO SONDADO
# ---------------------------------------------------------------------------


def _transporte_do_bustype(bruto: str) -> str:
    try:
        barramento = int(bruto.strip(), 16)
    except ValueError:
        return "?"
    if barramento == BUS_BLUETOOTH:
        return RADIO
    if barramento == BUS_USB:
        return CABO
    return f"bus 0x{barramento:04x}"


def transporte_por_duas_rotas(
    aparelho: Aparelho,
    nos: list[tuple[str, str]],
    raiz_class_input: str | None = None,
) -> tuple[str, str, str]:
    """`(veredito, rota 1, rota 2)` do transporte deste controle FÍSICO.

    - **rota 1**: o barramento do `HID_ID` do `uevent` do device HID pai. É a
      que `comum._transporte_do_hid_id` já lê, e vem pronta no `Aparelho`.
    - **rota 2**: o `id/bustype` do NÓ DE ENTRADA. O `ps_allocate_input_dev`
      copia `bustype` do `hdev` para o `input_dev`, então as duas TÊM de
      concordar — e quando não concordam, alguma delas está olhando para outro
      aparelho, que é exatamente o que se quer descobrir antes de escrever
      "cabo" numa célula.

    **Topologia de sysfs não é rota nenhuma** e não aparece aqui: com BlueZ
    >= 5.73 o `bluetoothd` cria o HID dos DualSense físicos de rádio também por
    `/dev/uhid`, sob `/devices/virtual/misc/uhid/`, no mesmíssimo lugar do
    nosso vpad. Armadilha paga em 11/08/2026.

    Discordância — ou rota que não se resolve — devolve `NÃO SONDADO`. Um
    transporte plausível e errado é pior que um buraco declarado: o mapa mede
    cabo CONTRA rádio, e uma linha trocada inverte a conclusão.
    """
    raiz = RAIZ_CLASS_INPUT if raiz_class_input is None else raiz_class_input
    rota1 = aparelho.transporte
    lidos = set()
    for _nome, caminho in nos:
        evento = os.path.basename(caminho)
        bruto = ler_texto(os.path.join(raiz, evento, "device", "id", "bustype"))
        if bruto.strip():
            lidos.add(_transporte_do_bustype(bruto))
    if len(lidos) == 1:
        rota2 = next(iter(lidos))
    elif not lidos:
        rota2 = "(não sei)"
    else:
        rota2 = "DISCORDAM ENTRE SI: " + ", ".join(sorted(lidos))
    if rota1 == rota2 and rota1 in (CABO, RADIO):
        return rota1, rota1, rota2
    return V_NAO_SONDADO, rota1, rota2


# ---------------------------------------------------------------------------
# Os alvos, montados das duas réguas
# ---------------------------------------------------------------------------


@dataclass
class Alvo:
    """Um nó de `/dev` que interessa à pergunta, e de onde a certeza dele veio."""

    classe: str  # "nosso" | "físico"
    rotulo: str  # "P1" / "44:46:48:00:00:03"
    papel: str  # "gamepad" | "touchpad" | "hidraw" | ...
    caminho: str
    chave: tuple[int, int] | None
    reguas: str
    nota: str = ""

    @property
    def sondado(self) -> bool:
        return self.chave is not None and not self.nota.startswith("NÃO SONDADO")


def _rotulo_do_no(
    no: NoDeEntrada, vpad: VpadDoProduto | None, do_produto: list[VpadDoProduto]
) -> str:
    """Como este nó aparece na tabela: `P1`, o `uniq` forjado, ou o `eventN`.

    **Isto é rótulo, não medição.** O casamento acontece por inode, sempre; o
    que se decide aqui é só como chamar a linha na tela.

    A queda para o NOME existe porque, com o daemon mais velho que o código,
    a régua A não publica caminho nenhum e todo nó nosso sairia chamado
    `event10` — verdadeiro e inútil. E ela só vale quando o nome é ÚNICO nas
    duas listas: no co-op com quatro vpads de uinput os quatro têm o mesmo
    nome, e escolher um deles seria inventar de qual jogador é o nó.
    """
    if vpad is not None:
        return f"P{vpad.player}"
    homonimos = [v for v in do_produto if v.nome and v.nome == no.nome]
    if len(homonimos) == 1:
        return f"P{homonimos[0].player} (pelo nome)"
    if no.uniq:
        return no.uniq
    return no.evento


def montar_alvos(
    do_produto: list[VpadDoProduto], do_sysfs: list[NoDeEntrada]
) -> tuple[list[Alvo], list[str]]:
    """Os nós NOSSOS, com as duas réguas confrontadas nó a nó.

    A ordem importa: começa pelo que a régua B viu no kernel — ela existe com
    ou sem daemon — e só então pergunta se a régua A concorda. O contrário
    faria a régua A definir o universo, e uma segunda régua que só confere o
    que a primeira apontou não é segunda régua nenhuma.
    """
    alvos: list[Alvo] = []
    avisos: list[str] = []

    #: `caminho publicado -> o vpad que o publicou`, para o confronto abaixo.
    publicados: dict[str, VpadDoProduto] = {}
    for vpad in do_produto:
        if isinstance(vpad.evdev, str) and vpad.evdev:
            publicados[vpad.evdev] = vpad

    for no in do_sysfs:
        chave = _chave(no.caminho)
        vpad = publicados.get(no.caminho)
        reguas = "B (sysfs)"
        nota = ""
        if vpad is not None:
            if chave is not None and vpad.ino == chave[1]:
                reguas = "A (produto) + B (sysfs)"
            else:
                reguas = "A e B DISCORDAM"
                nota = (
                    f"NÃO SONDADO: o produto publicou ino={vpad.ino} para "
                    f"{no.caminho} e o `stat` de agora lê "
                    f"ino={chave[1] if chave else None}"
                )
        rotulo = _rotulo_do_no(no, vpad, do_produto)
        alvos.append(
            Alvo(
                classe="nosso",
                rotulo=rotulo,
                papel=no.papel,
                caminho=no.caminho,
                chave=chave,
                reguas=reguas,
                nota=nota,
            )
        )
        if no.hidraw:
            alvos.append(
                Alvo(
                    classe="nosso",
                    rotulo=rotulo,
                    papel="hidraw",
                    caminho=no.hidraw,
                    chave=_chave(no.hidraw),
                    reguas=reguas,
                )
            )

    vistos = {alvo.caminho for alvo in alvos}
    for vpad in do_produto:
        if not vpad.campos_ausentes and not vpad.evdev:
            avisos.append(
                f"P{vpad.player}: o daemon publicou o bloco e NÃO resolveu o "
                "nó (`evdev` = None). Isso é o produto dizendo `não sei`, e "
                "não a falta do campo."
            )
        if vpad.evdev and vpad.evdev not in vistos:
            avisos.append(
                f"P{vpad.player}: o produto publica {vpad.evdev} e a varredura "
                "de /sys NÃO o reconhece como nosso. As duas réguas discordam "
                "sobre a EXISTÊNCIA do nó — nada se afirma sobre ele."
            )
            alvos.append(
                Alvo(
                    classe="nosso",
                    rotulo=f"P{vpad.player}",
                    papel="gamepad",
                    caminho=vpad.evdev,
                    chave=_chave(vpad.evdev),
                    reguas="A e B DISCORDAM",
                    nota="NÃO SONDADO: só a régua A vê este nó",
                )
            )
        if vpad.declara_o_no:
            bloco = {
                "evdev": vpad.evdev,
                "hidraw": vpad.hidraw,
                "ino": vpad.ino,
                "hidraw_ino": vpad.hidraw_ino,
            }
            if not no_ainda_vale(bloco):
                avisos.append(
                    f"P{vpad.player}: o bloco publicado JÁ NÃO VALE — o nó foi "
                    "renumerado entre a leitura do daemon e a minha. É a "
                    "renumeração que o inode existe para pegar, e ela "
                    "aconteceu agora."
                )
    return alvos, avisos


def alvos_fisicos(mapa_do_produto: dict[int, str]) -> tuple[list[Alvo], list[list[str]]]:
    """Os nós dos controles FÍSICOS, e a tabela de transporte de cada um.

    Eles entram como alvo porque o veredito `SEGURA O FÍSICO` é uma resposta
    de verdade, e das caras: quer dizer que o jogo passou por fora de tudo o
    que o produto montou. Sem eles o instrumento só saberia dizer "não segura
    o nosso", que é a mesma frase para dois mundos opostos.
    """
    alvos: list[Alvo] = []
    linhas: list[list[str]] = []
    por_mac = {mac.replace(":", "").lower(): num for num, mac in mapa_do_produto.items()}
    for aparelho in fisicos(descobrir_aparelhos()):
        nos = nos_de_entrada_do_hid(aparelho.dir_device)
        veredito, rota1, rota2 = transporte_por_duas_rotas(aparelho, nos)
        mac = _mascara(aparelho.mac)
        numero = por_mac.get(aparelho.mac.replace(":", "").lower())
        linhas.append(
            [
                f"P{numero}" if numero else "-",
                mac,
                aparelho.hidraw,
                rota1,
                rota2,
                veredito,
            ]
        )
        for nome, caminho in nos:
            alvos.append(
                Alvo(
                    classe="físico",
                    rotulo=mac,
                    papel=_papel_do_nome(nome),
                    caminho=caminho,
                    chave=_chave(caminho),
                    reguas="B (sysfs)",
                )
            )
        alvos.append(
            Alvo(
                classe="físico",
                rotulo=mac,
                papel="hidraw",
                caminho=aparelho.caminho_hidraw,
                chave=_chave(aparelho.caminho_hidraw),
                reguas="B (sysfs)",
            )
        )
    return alvos, linhas


# ---------------------------------------------------------------------------
# O CENSO — quem segura o quê, por inode
# ---------------------------------------------------------------------------


@dataclass
class Posse:
    """Um processo com um dos nossos alvos aberto, agora."""

    pid: int
    cmdline: str
    alvo: Alvo


@dataclass
class Censo:
    """O que a varredura de `/proc` conseguiu ver — e o que não viu."""

    processos: int = 0
    meus: int = 0
    de_outro_usuario: int = 0
    ilegiveis: set[int] = field(default_factory=set)
    posses: list[Posse] = field(default_factory=list)

    def fechou_sobre(self, pids: list[int]) -> bool:
        """Li o `fd/` de TODOS estes processos? `NENHUM` depende disto.

        A pergunta é sobre a ÁRVORE DO JOGO, e é o censo dela que precisa
        fechar. Exigir o mundo inteiro seria exigir o impossível: `(sd-pam)` e
        `ssh-agent` zeram o `PR_SET_DUMPABLE` e nunca se deixam ler, então o
        censo global desta máquina não fecha nunca — e `NENHUM` viraria um
        veredito decorativo, que nunca sai.
        """
        return not (set(pids) & self.ilegiveis)


def _cmdline(pid: int, raiz_proc: str | None = None) -> str:
    raiz = RAIZ_PROC if raiz_proc is None else raiz_proc
    try:
        with open(os.path.join(raiz, str(pid), "cmdline"), "rb") as arquivo:
            bruto = arquivo.read()
    except OSError:
        return ""
    return bruto.replace(b"\0", b" ").decode("utf-8", "replace").strip()


def censo_de_posse(alvos: list[Alvo], raiz_proc: str | None = None) -> Censo:
    """Quem, entre TODOS os processos legíveis, segura um dos alvos.

    A varredura é global de propósito, e não só da árvore do jogo. A pergunta
    do degrau é sobre o jogo, mas a pergunta que salva a investigação é *"e
    quem está segurando, então?"* — o cliente Steam abre o nó, e sessão aberta
    NÃO é evidência de jogo (veto da NUMA-02, mecanismo do incidente das
    14:42). Sem a lista global, um `NENHUM` no jogo e um `NENHUM` no mundo
    sairiam com a mesma cara.

    O casamento é `os.stat` do `/proc/<pid>/fd/<n>` contra o `(st_dev, st_ino)`
    do alvo. **Nada é aberto.** E não se lê o `os.readlink`: o caminho é um
    número de fila, e o critério do degrau proíbe casar por ele.
    """
    raiz = RAIZ_PROC if raiz_proc is None else raiz_proc
    censo = Censo()
    por_chave: dict[tuple[int, int], Alvo] = {
        alvo.chave: alvo for alvo in alvos if alvo.chave is not None
    }
    meu_uid = os.getuid()
    try:
        entradas = os.listdir(raiz)
    except OSError:
        return censo
    for entrada in entradas:
        if not entrada.isdigit():
            continue
        pid = int(entrada)
        censo.processos += 1
        try:
            dono = os.stat(os.path.join(raiz, entrada)).st_uid
        except OSError:
            continue  # morreu entre o listdir e o stat: não é buraco, é vida
        if dono != meu_uid:
            censo.de_outro_usuario += 1
            continue
        censo.meus += 1
        try:
            fds = os.listdir(os.path.join(raiz, entrada, "fd"))
        except FileNotFoundError:
            continue  # morreu agora
        except OSError:
            censo.ilegiveis.add(pid)
            continue
        # Um mesmo nó aberto duas vezes pelo mesmo processo é UM fato, não
        # dois: o `dup()` de um fd não é uma segunda posse, e contá-lo duas
        # vezes engorda a tabela sem acrescentar nada.
        ja_vistos: set[str] = set()
        for fd in fds:
            chave = _chave(os.path.join(raiz, entrada, "fd", fd))
            alvo = por_chave.get(chave) if chave else None
            if alvo is not None and alvo.caminho not in ja_vistos:
                ja_vistos.add(alvo.caminho)
                censo.posses.append(
                    Posse(pid=pid, cmdline=_cmdline(pid, raiz), alvo=alvo)
                )
    return censo


def arvore_ancorada(
    padrao: str, *, ancora: bool = True, raiz_proc: str | None = None
) -> tuple[list[int], list[int]]:
    """`(árvore ancorada, o que casou pelo cmdline e NÃO é jogo)`.

    A expansão da árvore é a do `quem_o_jogo_abre.arvore_do_jogo` — processos
    cujo cmdline case, mais os descendentes. O que se acrescenta aqui é a
    peneira: só fica quem carrega `SteamAppId` no `environ`.

    O resto volta separado de propósito, para ser IMPRESSO. Quem roda isto sem
    jogo aberto precisa ver que o `earlyoom` casou com a palavra `.exe` — e não
    ficar com a impressão de que o instrumento não achou nada por acaso.
    """
    raiz = RAIZ_PROC if raiz_proc is None else raiz_proc
    candidatos = arvore_do_jogo(padrao)
    if not ancora:
        return candidatos, []
    dentro: list[int] = []
    fora: list[int] = []
    for pid in candidatos:
        try:
            with open(os.path.join(raiz, str(pid), "environ"), "rb") as arquivo:
                bruto = arquivo.read()
        except OSError:
            fora.append(pid)
            continue
        (dentro if ANCORA_DO_JOGO in bruto else fora).append(pid)
    return dentro, fora


# ---------------------------------------------------------------------------
# A decisão
# ---------------------------------------------------------------------------


def decidir(
    alvos: list[Alvo], censo: Censo, arvore: list[int], recusados: list[int]
) -> tuple[str, str]:
    """`(veredito, motivo)` sobre a ÁRVORE DO JOGO. Um dos cinco, sempre.

    A assimetria entre achar e não achar é o coração disto: **achar é uma
    observação positiva** e vale mesmo com o censo aberto — um processo com o
    fd na mão é um processo com o fd na mão. **Não achar não é observação
    nenhuma** enquanto sobrar processo que não se pôde ler: aí a frase honesta
    é `NÃO SONDADO`, e não `NENHUM`.
    """
    nossos = [a for a in alvos if a.classe == "nosso" and a.sondado]
    if not nossos:
        return (
            V_NAO_SONDADO,
            "nenhum nó NOSSO se resolveu: sem alvo não há o que procurar em "
            "`/proc`. Com o daemon parado isto é o esperado — o vpad só existe "
            "enquanto ele roda.",
        )
    if not arvore:
        if recusados:
            return (
                V_NAO_SONDADO,
                f"{len(recusados)} processo(s) casaram com o padrão pelo "
                "cmdline e NENHUM deles carrega `SteamAppId` no ambiente — "
                "eles mencionam a palavra, não são o jogo. Se o jogo está "
                "aberto e não veio da Steam, aponte `--padrao` para o "
                "executável dele.",
            )
        return (
            V_NAO_SONDADO,
            "nenhum processo casou com o padrão do jogo: não há árvore em que "
            "procurar. `NENHUM` aqui responderia uma pergunta que não foi "
            "feita — é sobre o JOGO que este veredito fala.",
        )
    da_arvore = [p for p in censo.posses if p.pid in set(arvore)]
    tem_nosso = any(p.alvo.classe == "nosso" for p in da_arvore)
    tem_fisico = any(p.alvo.classe == "físico" for p in da_arvore)
    if tem_nosso and tem_fisico:
        return (
            V_DOIS,
            "a árvore do jogo segura o nosso nó E o do controle físico. É o "
            "sintoma do controle em dobro: o jogo enxerga dois aparelhos onde "
            "deveria haver um.",
        )
    if tem_nosso:
        return (
            V_NOSSO,
            "um processo da árvore do jogo tem o inode de um nó NOSSO aberto. "
            "É o que o degrau `O JOGO RECEBEU` pede, e nada além disso: que o "
            "jogo REAJA ao que chega é o degrau seguinte, e o sensor dele é "
            "ela.",
        )
    if tem_fisico:
        return (
            V_FISICO,
            "a árvore do jogo foi ao controle FÍSICO e não ao nosso vpad. O "
            "produto está fora do caminho — e se o broker estiver escondendo o "
            "hidraw, o que sobrou aberto é o evdev.",
        )
    if not censo.fechou_sobre(arvore):
        cegos = sorted(set(arvore) & censo.ilegiveis)
        return (
            V_NAO_SONDADO,
            f"{len(cegos)} processo(s) DA ÁRVORE DO JOGO não se deixaram ler "
            f"em `/proc/<pid>/fd` ({cegos}). Não achar nada entre os que "
            "sobraram não é o mesmo que não haver nada.",
        )
    return (
        V_NENHUM,
        f"o censo FECHOU (os {len(arvore)} processos da árvore do jogo foram "
        "lidos, um a um) e nenhum deles segura o nosso nó nem o do físico. "
        "Isto é uma afirmação, não uma ausência de dado.",
    )


# ---------------------------------------------------------------------------
# Saída
# ---------------------------------------------------------------------------


def _linha_do_vpad(vpad: VpadDoProduto) -> list[str]:
    if vpad.campos_ausentes:
        estado = "campos AUSENTES: " + ", ".join(vpad.campos_ausentes)
    elif vpad.evdev:
        estado = f"{vpad.evdev} ino={vpad.ino}"
    else:
        estado = "o daemon publicou `None` — ele não resolveu o nó"
    return [
        f"P{vpad.player}",
        vpad.backend or "?",
        (vpad.nome or "?")[:46],
        estado,
        "-" if vpad.game_open is None else ("SIM" if vpad.game_open else "não"),
    ]


def imprimir(
    motivo_do_estado: str,
    do_produto: list[VpadDoProduto],
    do_sysfs: list[NoDeEntrada],
    alvos: list[Alvo],
    avisos: list[str],
    linhas_de_transporte: list[list[str]],
    censo: Censo,
    arvore: list[int],
    recusados: list[int],
    padrao: str,
    ancora: bool,
) -> None:
    print("\n--- 1. O ALVO: quais nós são NOSSOS -----------------------------")
    if motivo_do_estado:
        print(f"  régua A (o produto declara) .. INDISPONÍVEL — {motivo_do_estado}")
    else:
        print(f"  régua A (o produto declara) .. {len(do_produto)} vpad(s) no "
              "`rumble_ff.per_vpad` do `daemon.state_full`")
        print(tabela(
            ["jogador", "backend", "nome", "o que o produto diz do nó", "game_open"],
            [_linha_do_vpad(v) for v in do_produto],
        ))
        if do_produto and all(v.campos_ausentes for v in do_produto):
            print()
            print("  >> O DAEMON VIVO É MAIS VELHO QUE O CÓDIGO. Os campos do nó")
            print("  >> não existem no payload dele — install editable: a cura só")
            print("  >> vale no próximo start. Isto NÃO é o daemon dizendo `não")
            print("  >> sei`; é o campo não existir. Sigo com a régua B sozinha,")
            print("  >> e digo isso em vez de fingir duas réguas.")
    print()
    print(f"  régua B (o kernel mostra) .... {len(do_sysfs)} nó(s) de entrada "
          "nossos em /sys/class/input")
    if do_sysfs:
        print(tabela(
            ["nó", "papel", "nome", "como sei que é nosso"],
            [[n.caminho, n.papel, n.nome[:44], n.marca] for n in do_sysfs],
        ))
    else:
        print("      NENHUM — nenhum nó de entrada carrega o carimbo do produto")
    print()
    print("  os alvos, com a chave por que se casa (st_dev, st_ino):")
    print(tabela(
        ["classe", "quem", "papel", "nó", "inode", "réguas"],
        [
            [
                a.classe,
                a.rotulo,
                a.papel,
                a.caminho,
                str(a.chave[1]) if a.chave else "(não resolveu)",
                a.reguas,
            ]
            for a in alvos
        ],
    ))
    for aviso in avisos:
        print(f"  >> {aviso}")

    print("\n--- 2. A PERNA FÍSICA e o transporte ----------------------------")
    print("  O vpad NÃO tem transporte — ele forja BUS_USB no UHID_CREATE2. Quem")
    print("  tem é o controle que o alimenta, e é o barramento DELE que vale.")
    if linhas_de_transporte:
        print(tabela(
            ["jogador", "MAC (mascarado)", "hidraw", "rota 1 (HID_ID)",
             "rota 2 (bustype)", "veredito"],
            linhas_de_transporte,
        ))
    else:
        print("      NENHUM DualSense físico na mesa.")

    print("\n--- 3. O CENSO: quem segura esses inodes ------------------------")
    print(f"  processos em /proc ........... {censo.processos}")
    print(f"  do seu usuário, lidos ........ {censo.meus}")
    print(f"  de outro usuário, PULADOS .... {censo.de_outro_usuario}  "
          "(um jogo sob Proton roda com o seu uid)")
    print(f"  do seu usuário, ILEGÍVEIS .... {len(censo.ilegiveis)}  "
          "(`(sd-pam)` e `ssh-agent` zeram o PR_SET_DUMPABLE: nunca abrem)")
    fechou = censo.fechou_sobre(arvore)
    print(f"  o censo DA ÁRVORE fechou? .... "
          f"{'SIM' if fechou else 'NÃO — `NENHUM` não pode ser afirmado'}")
    if censo.posses:
        print(tabela(
            ["pid", "na árvore do jogo?", "classe", "quem", "nó", "processo"],
            [
                [
                    str(p.pid),
                    "SIM" if p.pid in set(arvore) else "não",
                    p.alvo.classe,
                    p.alvo.rotulo,
                    p.alvo.caminho,
                    p.cmdline[:58] or "(sem cmdline)",
                ]
                for p in sorted(censo.posses, key=lambda p: (p.pid, p.alvo.caminho))
            ],
        ))
    else:
        print("      ninguém, entre os processos lidos, segura um destes nós")

    print("\n--- 4. A ÁRVORE DO JOGO -----------------------------------------")
    print(f"  padrão do cmdline ............ {padrao}")
    print(
        "  âncora ....................... "
        + (
            f"{ANCORA_DO_JOGO.decode().rstrip('=')} no `environ`"
            if ancora
            else "DESLIGADA por `--sem-ancora` — a lista abaixo é o que casou "
            "pela PALAVRA"
        )
    )
    print(f"  na árvore, ANCORADOS ......... {len(arvore)}")
    print(f"  casaram e foram RECUSADOS .... {len(recusados)}")
    for pid in recusados:
        print(f"      {pid:<9} {_cmdline(pid)[:62] or '(sem cmdline)'}")
    if recusados:
        print("      (casaram com a palavra do padrão e não carregam a âncora —")
        print("      não são o jogo, e sem esta peneira entrariam na conta)")
    if not arvore:
        print("      NENHUM ancorado. Sem jogo aberto não há sujeito para a")
        print("      pergunta — e este instrumento diz isso em vez de inventar")
        print("      um zero.")


def registro(
    veredito: str,
    motivo: str,
    alvos: list[Alvo],
    linhas_de_transporte: list[list[str]],
    censo: Censo,
    arvore: list[int],
    recusados: list[int],
) -> dict:
    """O mesmo relatório em JSON, para quem for CONFERIR — nunca para preencher.

    Ele não grava nada em disco e não conhece o formato do caderno de ensaios.
    Escrever a célula é ato de quem olhou; um instrumento que preenchesse
    sozinho fabricaria exatamente o defeito que o degrau existe para impedir.
    """
    da_arvore = set(arvore)
    return {
        "veredito": veredito,
        "motivo": motivo,
        "degrau": "O JOGO RECEBEU",
        "alvos": [
            {
                "classe": a.classe,
                "quem": a.rotulo,
                "papel": a.papel,
                "no": a.caminho,
                "st_dev": a.chave[0] if a.chave else None,
                "ino": a.chave[1] if a.chave else None,
                "reguas": a.reguas,
                "nota": a.nota,
            }
            for a in alvos
        ],
        "transporte": [
            dict(
                zip(
                    ("jogador", "mac", "hidraw", "rota1", "rota2", "veredito"),
                    linha,
                    strict=True,
                )
            )
            for linha in linhas_de_transporte
        ],
        "censo": {
            "processos": censo.processos,
            "meus": censo.meus,
            "de_outro_usuario": censo.de_outro_usuario,
            "ilegiveis": sorted(censo.ilegiveis),
            "fechou_sobre_a_arvore": censo.fechou_sobre(arvore),
        },
        "posse": [
            {
                "pid": p.pid,
                "na_arvore_do_jogo": p.pid in da_arvore,
                "classe": p.alvo.classe,
                "quem": p.alvo.rotulo,
                "no": p.alvo.caminho,
            }
            for p in censo.posses
        ],
        "arvore_do_jogo": arvore,
        "recusados_pela_ancora": recusados,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--padrao",
        default=PADRAO_DO_JOGO,
        help="regex do cmdline do jogo (padrão pega .exe sob Proton)",
    )
    ap.add_argument(
        "--json", action="store_true", help="imprime o registro em JSON e sai"
    )
    ap.add_argument(
        "--sem-ancora",
        action="store_true",
        help="aceita a árvore sem exigir `SteamAppId` no ambiente (jogo que "
        "não veio da Steam). SAI AVISADO no relatório: sem a âncora, um "
        "processo que só menciona `.exe` entra na conta",
    )
    args = ap.parse_args(argv)

    if PRODUTO_IMPORTAVEL:
        print(
            "ERRO: o pacote do produto não é importável neste interpretador "
            f"({PRODUTO_IMPORTAVEL}).\n"
            "Sem ele eu não tenho o carimbo que separa o nosso vpad de um "
            "DualSense de verdade, e mediria por vid/pid — que é justamente o "
            "que o vpad forja.\n"
            "Rode com o interpretador do projeto:\n"
            "    .venv/bin/python scripts/ensaios/o_jogo_segura_o_nosso_no.py",
            file=sys.stderr,
        )
        return 2

    estado, motivo_do_estado = estado_do_produto()
    do_produto = vpads_do_produto(estado)
    do_sysfs = vpads_do_sysfs()
    alvos, avisos = montar_alvos(do_produto, do_sysfs)
    fisicos_alvos, linhas_de_transporte = alvos_fisicos(fisico_por_jogador(estado))
    alvos.extend(fisicos_alvos)
    censo = censo_de_posse(alvos)
    arvore, recusados = arvore_ancorada(args.padrao, ancora=not args.sem_ancora)
    veredito, motivo = decidir(alvos, censo, arvore, recusados)

    if args.json:
        print(json.dumps(
            registro(
                veredito, motivo, alvos, linhas_de_transporte, censo, arvore,
                recusados,
            ),
            ensure_ascii=False,
            indent=1,
        ))
        return 0

    print(cabecalho_do_instrumento(
        f"o_jogo_segura_o_nosso_no.py (versão {VERSAO})",
        "a árvore do jogo segura o NOSSO nó, ou o do controle físico?",
        bibliotecas=[
            "os",
            "socket",
            "identidade_do_vpad",
            "hefesto_dualsense4unix.integrations.no_do_vpad",
            "hefesto_dualsense4unix.integrations.uhid_gamepad",
            "hefesto_dualsense4unix.integrations.uinput_gamepad",
        ],
        escreve_no_aparelho=False,
        daemon_precisa_parar=False,
    ))
    print("  ABRE algum nó? ........ NÃO. `os.stat` resolve caminho e não abre")
    print("                          descritor: nada de UHID_OPEN, nada de modo")
    print("                          jogo armado, ninguém fecha por último.")
    print("  a linha `porta` acima . este instrumento não abre hidraw; ela vale")
    print("                          por OUTRO motivo — com o broker vivo o")
    print("                          hidraw do FÍSICO está escondido do jogo, e")
    print("                          isso muda como se lê `não segura o físico`.")
    if args.sem_ancora:
        print()
        print("  >> ÂNCORA DESLIGADA por `--sem-ancora`. Todo processo cujo")
        print("  >> cmdline casar entra na árvore, inclusive quem só MENCIONA a")
        print("  >> palavra. Confira a lista da seção 4 antes de acreditar.")
    if VPAD_HID_PHYS != PHYS_DO_PRODUTO:
        print()
        print("  >> AS DUAS CÓPIAS DO CARIMBO DIVERGIRAM. O `scripts/"
              f"identidade_do_vpad.py` diz `{VPAD_HID_PHYS}` e o produto "
              f"carimba `{PHYS_DO_PRODUTO}`.")
        print("  >> A régua deste instrumento está velha; NÃO acredite no que "
              "vem abaixo.")

    imprimir(
        motivo_do_estado,
        do_produto,
        do_sysfs,
        alvos,
        avisos,
        linhas_de_transporte,
        censo,
        arvore,
        recusados,
        args.padrao,
        not args.sem_ancora,
    )
    print(resumo(f"{veredito} — {motivo}"))
    print("Este instrumento NÃO preenche célula do mapa. Ele mede; quem escreve")
    print("no caderno é quem olhou — e `O JOGO REAGIU` é dela, e só dela.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
