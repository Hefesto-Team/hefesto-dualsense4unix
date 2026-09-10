#!/usr/bin/env python3
"""a_folha_do_microfone_por_controle.py — o microfone de cada controle, nos dois transportes, com o pico ao vivo.

A ENCOMENDA É DELA, 09/09/2026, com o produto instalado e os controles na mão:

    *"materializa o teste pensando em dois controles. um com cabo e o da  # (noqa-acento: citação dela)
     direita via bt. vou desconectar os demais. Faz eles estilo o que  # (noqa-acento: citação dela)
     fizemos hoje mais cedo. (…) com os controles pra eu poder ver e tal."*  # (noqa-acento: citação literal dela)
«Estilo o que fizemos hoje mais cedo» é a `a_folha_dos_ensaios.py`, e o que
esta herda dela é o desenho inteiro: uma TABELA declarativa que se monta em
tela, **um controle por pergunta**, o martelo a 10 Hz, e nenhuma conclusão —
as linhas do caderno saem PROPOSTAS no fim.

AS TRÊS PERGUNTAS QUE ESTA FOLHA DECIDE
----------------------------------------
1. **MIC-OS-QUATRO-01** — o mic virtual de cada controle sobe e CAPTA, nos dois
   transportes? Medido na mesa dela em 09/09: existe **UM** nó de quatro
   controles. A causa é conhecida e não é defeito: `BtMicSubsystem.alvos()`
   devolve `[]` enquanto ninguém PEDE o canal daquele controle — a ponte sobe
   **sob demanda**, e quem pede é o botão do microfone. Por isso a linha 2
   desta folha é esse pedido, num botão: ela aperta e vê o nó nascer na linha
   de cima; aperta de novo e vê sumir;
2. **MIC-VOLUME-02** (decisão dela, *"3-c"*) — o byte do aparelho
   (`common[6]`, teto `0x40`, autorizado por `valid_flag0` bit 6) muda a
   CAPTURA? Hoje ele é `decisao-tomada` no mapa: ninguém escreve, e ninguém
   mediu se faz algo. O campo que a tela oferece mexe no ganho da FONTE no
   PipeWire, que é **outra coisa** — e as duas estão lado a lado aqui, nas
   linhas 4 e 5, de propósito. *Byte que o aparelho não obedece não ganha
   campo*, e esta folha é quem decide;
3. **A TARJA QUE MENTE**, achada em 09/09/2026 — a aba Controles diz *"O
   sistema não publica um microfone para este controle"* sobre o controle do
   CABO, que **tem** o nó publicado E placa USB. A frase nasce quando o daemon
   responde `status: "sem_fonte"` ao `mic.volume.set`
   (`interface/pacotes/a02_controles.py`, o ramo `TEXTO_MIC_SEM_FONTE`). A
   linha 1 diz o que o SISTEMA publica; a linha 6 diz o que o DAEMON responde.
   Se os dois discordarem na frente dela, a causa está achada.

O QUE É DO PRODUTO E O QUE É DAQUI — e a lista importa
-------------------------------------------------------
Do PRODUTO, sem uma linha de cópia:

* quem é o nó de captura deste controle: `integrations/canal_do_microfone`
  (`nome_do_canal` = `hefesto_mic_<seis hex do MAC>`) e
  `integrations/audio_control.fonte_de_captura_do_uniq`, que é a MESMA função
  que o `mic.volume.set` do daemon chama;
* o pedido de canal: `mic.canal.set` por `app/ipc_bridge`, o mesmo ato do 🎙 da
  tela e da borda do botão do plástico (`hotkey.ligar_o_microfone`);
* o campo da tela: `mic.volume.set`, também por `app/ipc_bridge`;
* a placa ALSA de cada controle do cabo: `microfone_no_cabo.placas_de_dualsense`
  (casamento pelo dispositivo USB pai — a única identidade que o cabo tem);
* o report de saída de cada transporte: `escrita_pelo_broker`.

Daqui, e só isto: o desenho da folha, o martelo, o medidor de pico e a linha
do caderno.

**O NÓ SE CASA POR ENDEREÇO, NUNCA POR NÚMERO.** O `os_nos_de_som_por_controle`
casa o mic virtual pela DESCRIÇÃO («Microfone do Controle N»), e o N é o
assento — que muda quando um controle entra ou sai. Medido nesta mesa em
09/09/2026: o mesmo nó `hefesto_mic_<hex6>` foi atribuído ao controle do CABO
numa corrida e ao do RÁDIO na seguinte, sem nada ter mudado no áudio. Aqui a
pergunta *"de que controle é este nó"* tem UM dono, e é o do produto:
`fontes_de_captura.sufixo_do_canal_do_mic` / `canal_do_microfone.nome_do_canal`.

A MESA É DE DOIS, E O CABO É O CONTROLE POSITIVO
-------------------------------------------------
Um controle no CABO e um no RÁDIO. O som pelo cabo FUNCIONA (placa USB própria,
medido), então pôr os dois lado a lado na mesma folha é o que transforma *"não
ouvi nada"* em prova: ela aperta o do cabo e o pico sobe; aperta o do rádio, e
a diferença é o resultado. Sem o positivo ao lado, silêncio no rádio não
distingue *"o aparelho não aceita"* de *"o meu tom está mudo"*.

A folha **descobre a mesa sozinha** e funciona com dois, com quatro e com um —
e quando falta o par que ela precisa, DIZ, com todas as letras: *"preciso de um
no cabo e um no rádio; achei dois no cabo"*. Nenhum endereço se digita.

O MARTELO, e por que ele é obrigatório
---------------------------------------
O daemon reescreve o `common` a cada report dele. Esta folha bate a 10 Hz nos
campos que ela ASSUMIR. Se o pico PISCAR entre dois patamares, isso é um
**sim** — é o daemon e a folha disputando, e disputa só existe se o byte age.

**A posse é POR CONTROLE E POR ENSAIO**: o bit `0x40` do `valid_flag0` só liga
quando ela liga a chave «Assumir» daquela coluna. Assumir tudo de uma vez briga
com o daemon em todas as frentes e emborca a medição.

O PICO NÃO GRAVA NADA EM DISCO
-------------------------------
Ela está com o microfone aberto na própria sala. **A PORTA DE LEITURA é o
`parec`** — o mesmo leitor que o produto usa para alimentar o canal por
controle (`canal_do_microfone._ALIMENTADOR`) — lendo a fonte daquele controle
com `--latency-msec=40`, a saída em `stdout` por PIPE, s16 mono. Cada pedaço
que chega vira UM número (o pico daquele pedaço) e a amostra é **descartada na
mesma linha**: não há `open` de escrita, não há `wave`, não há arquivo. E o
ouvido só abre quando ela aperta «Ouvir o pico» — nenhum microfone nasce ligado
aqui.

Abrir o ouvido também é MEDIÇÃO, e não só instrumento: a ponte do rádio segue o
estado da source (`dualsense_bt_audio.ESTADO_COM_OUVINTE`), então um ouvinte é
o que a faz sair de `SUSPENDED` — o mesmo que o cabo faz de graça.

A MORDIDA
---------
* arranque o `c[0] |= VALID_FLAG0_MIC_VOLUME` de `common_do_byte` e o pico
  deixa de responder ao deslizante — a autorização é o que o firmware exige;
* troque o `6` de `COMMON_MIC_VOLUME` por `5` e a folha passa a mexer no
  **alto-falante** achando que mede o microfone;
* case o nó pela DESCRIÇÃO em vez do endereço e a coluna do rádio passa a
  exibir o nó do cabo — é o defeito medido acima, e `tests/unit/
  test_a_folha_do_microfone_casa_o_no_por_endereco.py` reprova nos três casos.

Porta: o broker (`comum.abrir_no_hidraw`) para o byte, com o daemon VIVO; o
socket do daemon (`app/ipc_bridge`) para os dois atos do produto; o `pactl`
(`LC_ALL=C`, senão o parser diz «NÃO EXISTE» a um nó que está lá) e o `parec`
para o som.

Escreve no aparelho? **SIM, por duas portas, e só quando ela manda:**

1. `common[6]` + o bit `0x40` do `valid_flag0` — apenas com «Assumir» ligado
   naquela coluna. **A porta do hidraw só ABRE nesse instante**: até ela ligar
   a chave, esta folha não escreve um byte sequer, e é por isso que `--listar`
   e `--oculta` provam o instrumento sem tocar em controle nenhum;
2. o botão «Pedir o canal», que é o ato do PRODUTO (`mic.canal.set`) — o mesmo
   do 🎙 da tela, e ele mexe no mudo do firmware por desenho dela.

USO
    a_folha_do_microfone_por_controle.py --listar      # só lê: a mesa, os nós, o que o produto responde
    a_folha_do_microfone_por_controle.py               # na tela dela
    a_folha_do_microfone_por_controle.py --so-ajustes  # só os controles, sem uma linha de prosa
    a_folha_do_microfone_por_controle.py --oculta      # sem tela, para régua
"""

from __future__ import annotations

import array
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, ClassVar

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)
_SRC = os.path.join(os.path.dirname(os.path.dirname(_AQUI)), "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

#: As bandeiras que NÃO abrem janela na sessão viva.
BANDEIRAS_SEM_TELA = ("--oculta", "--listar")

# O ESCAPE É DECLARADO (TELA-DELA-02): sem `--oculta` nem `--listar` esta folha
# é DELA e nasce na tela dela — vê-la é o ponto inteiro.
#
# **E ele só vale quando este arquivo é o PROGRAMA.** Importá-lo para medir (o
# teste que morde faz isso) não pode assumir a tela dela de carona: `sys.argv`
# ali é o do pytest, e um `HEFESTO_NA_TELA=1` plantado no ambiente do processo
# valeria para todo módulo importado depois. A guarda da suíte já rodou; esta
# linha não tem o que dizer sobre ela.
_E_O_PROGRAMA = os.path.basename(sys.argv[0] or "") == os.path.basename(__file__)
if _E_O_PROGRAMA and not any(b in sys.argv for b in BANDEIRAS_SEM_TELA):
    os.environ["HEFESTO_NA_TELA"] = "1"

from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira

garantir_tela_de_mentira()

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import GLib, Gtk

import hefesto_dualsense4unix.core.ds_output_report as rep

# OS DONOS DA RESPOSTA, IMPORTADOS NO TOPO DE PROPÓSITO. O cabeçalho desta casa
# imprime o CAMINHO de cada biblioteca que o instrumento usa, e um import
# preguiçoso dentro da função sai como «NÃO IMPORTADO» — que é exatamente a
# declaração de procedência deixando de declarar.
from hefesto_dualsense4unix.integrations.audio_control import fonte_de_captura_do_uniq
from hefesto_dualsense4unix.integrations.canal_do_microfone import nome_do_canal
from comum import CABO, RADIO, cabecalho_do_instrumento, pintar_fundo_solido, resumo
from escrita_pelo_broker import (
    Escritor,
    alvos_da_mesa,
    common_vazio,
    linha_do_caderno,
    mascarar,
)
from microfone_no_cabo import placas_de_dualsense
from os_nos_de_som_por_controle import blocos_longos, pactl

#: O martelo. O daemon reescreve o `common` a cada report dele; ver o cabeçalho.
HZ = 10.0

#: De quanto em quanto tempo a lista viva de fontes é relida. Dois segundos é o
#: que faz o nó «nascer» na tela logo depois do botão sem transformar a folha
#: num laço de `pactl` — a leitura roda FORA da linha do GTK, num trabalhador.
RELER_A_LISTA_S = 2.0

#: O leitor do pico. É o MESMO do produto (`canal_do_microfone._ALIMENTADOR`):
#: ele fala nome de `pactl` e escreve cru no `stdout`, que é o que permite ler
#: o nível sem tocar em disco.
LEITOR_DO_PICO = "parec"

#: A latência que se pede ao leitor, e ela não é afinação — é conserto. Medida
#: pelo produto em 06/09/2026: sem ela o `parec` nasce com quase QUATRO segundos
#: de fragmento, e o primeiro byte só chega aos 1,98 s. Do lado dela, isso são
#: dois segundos de barra parada que se leem como *"não funcionou"*.
LATENCIA_DO_PICO_MS = 40

#: Taxa e pedaço da leitura do pico. 4 KiB a 48 kHz mono s16 é ~42 ms: a barra
#: acorda ~24 vezes por segundo, que é mais do que o olho precisa.
TAXA_DO_PICO = 48000
PEDACO_DO_PICO = 4096

#: Quanto a barra CAI por tique quando o som para. Sem queda ela ficaria presa
#: no último pedaço alto e diria «tem sinal» sobre silêncio; com queda ela conta
#: o que está acontecendo AGORA. O máximo da sessão fica guardado à parte — é
#: ele que decide o ensaio, porque o olho não guarda o patamar anterior.
QUEDA_DA_BARRA = 0.18

#: O que o campo da tela manda. É a escala da FONTE de captura no PipeWire
#: (0-100), e NÃO os 0-0x40 do byte do aparelho. Estarem juntos na folha e
#: separados na cabeça é o ponto inteiro do ensaio 3-c.
VOLUME_DA_FONTE_INICIAL = 100

#: Quanto se espera antes de mandar o `mic.volume.set` que o deslizante pediu.
#: Um pedido por pixel arrastado encheria o socket do daemon de gestos mortos.
COALESCE_DO_DESLIZANTE_MS = 250


def _agora_ddmm() -> str:
    return time.strftime("%d%m")


# ---------------------------------------------------------------------------
# O byte do aparelho — e SÓ ele
# ---------------------------------------------------------------------------
def common_do_byte(valor: int, *, com_bit: bool = True) -> bytearray:
    """Um `common` de 47 bytes com o volume do microfone, e nada mais.

    O `common` nasce VAZIO de propósito (a lição do `corpo_do_degrau.py`): um
    common cheio de estado do daemon faria de cada passo uma medição diferente.

    `com_bit=False` é o NEGATIVO do ensaio — o mesmo `--sem-bit` do
    `o_byte_do_microfone_muda_a_captura.py`. Se o pico subir sem o bit, a
    autorização não vale nada.
    """
    if not 0 <= valor <= rep.TETO_MIC_VOLUME:
        raise ValueError(f"volume do mic fora de 0..{rep.TETO_MIC_VOLUME:#x}: {valor:#x}")
    c = common_vazio()
    c[rep.COMMON_MIC_VOLUME] = valor
    if com_bit:
        c[0] |= rep.VALID_FLAG0_MIC_VOLUME
    return c


# ---------------------------------------------------------------------------
# De que controle é este nó — a pergunta tem UM dono, e ele é do produto
# ---------------------------------------------------------------------------
def no_do_canal(uniq: str) -> str:
    """`hefesto_mic_<hex6>` deste controle — "" se ele não tem identidade.

    Não há régua nova aqui: quem responde é `canal_do_microfone.nome_do_canal`,
    o dono do batismo. Ver o cabeçalho para o que custou casar por NÚMERO.
    """
    try:
        return nome_do_canal(uniq) or ""
    except Exception:
        return ""


def fonte_do_produto(uniq: str) -> str:
    """O que o PRODUTO responde a *"qual é o microfone deste controle"*.

    É a mesma função que o `mic.volume.set` do daemon chama
    (`audio_control.fonte_de_captura_do_uniq`), e por isso ela é a coluna que
    vale ao lado da resposta do daemon. **Com uma diferença declarada:** o
    daemon a chama com a MESA (`recado_do_microfone.mesa_de_agora`), que liga a
    regra 4 (um-para-um); daqui ela vai sem mesa, que é o comportamento de
    antes de 06/09. Quando as duas colunas discordarem, é aí que se olha.
    """
    try:
        return fonte_de_captura_do_uniq(uniq) or ""
    except Exception:
        return ""


@dataclass
class LeituraDoSistema:
    """O que a lista VIVA publica para um controle, num instante."""

    canal: str = ""  #: `hefesto_mic_<hex6>`, casado por ENDEREÇO
    descricao: str = ""  #: o que ela vê na lista de som
    estado: str = ""  #: SUSPENDED · IDLE · RUNNING
    placa_usb: str = ""  #: o `alsa_input...` da placa do cabo
    do_produto: str = ""  #: o que `fonte_de_captura_do_uniq` responde

    @property
    def publica(self) -> bool:
        """O sistema publica ALGUMA entrada para este controle?"""
        return bool(self.canal or self.placa_usb)

    @property
    def escolhida(self) -> str:
        """Onde o pico escuta: o que o produto resolve, e o endereço como rede."""
        return self.do_produto or self.canal or self.placa_usb

    def frase(self) -> str:
        if not self.publica:
            return "NÃO EXISTE — o sistema não publica entrada nenhuma para este controle"
        partes = []
        if self.canal:
            rotulo = self.descricao or "(sem descrição)"
            partes.append(f"canal «{rotulo}» ({self.canal}, {self.estado or 'estado ?'})")
        if self.placa_usb:
            partes.append("placa USB do cabo")
        partes.append(f"o produto responde: {self.do_produto or 'None'}")
        return " · ".join(partes)


def ler_o_sistema(alvos: list[Any]) -> dict[str, LeituraDoSistema]:
    """A lista viva, por `uniq`. Roda FORA da linha do GTK — ver `RELER_A_LISTA_S`."""
    fontes = blocos_longos(pactl("list", "sources"))
    por_nome = {f.get("Name", ""): f for f in fontes if f.get("Name")}
    placas = {p.dono.hidraw: p for p in placas_de_dualsense(alvos) if p.dono is not None}
    leituras: dict[str, LeituraDoSistema] = {}
    for a in alvos:
        leitura = LeituraDoSistema()
        canal = no_do_canal(a.mac)
        if canal and canal in por_nome:
            leitura.canal = canal
            leitura.descricao = por_nome[canal].get("Description", "")
            leitura.estado = por_nome[canal].get("State", "")
        placa = placas.get(a.hidraw)
        if placa is not None:
            for nome, bloco in por_nome.items():
                if nome.startswith("alsa_input") and bloco.get("alsa.card") == placa.numero:
                    leitura.placa_usb = nome
                    if not leitura.canal:
                        leitura.descricao = bloco.get("Description", "")
                        leitura.estado = bloco.get("State", "")
                    break
        leitura.do_produto = fonte_do_produto(a.mac)
        leituras[a.mac] = leitura
    return leituras


# ---------------------------------------------------------------------------
# O pico — leitura de nível que NÃO toca disco
# ---------------------------------------------------------------------------
def pico_do_pedaco(pedaco: bytes) -> float:
    """O pico de um pedaço de s16 little-endian, em 0..1 — e A AMOSTRA MORRE AQUI.

    É a única coisa que sobrevive de cada pedaço que o leitor entrega: um
    `float`. Não há caminho daqui para disco, e é isso que a régua guarda.

    O ímpar do fim é descartado (`len // 2 * 2`): meio quadro de s16 lido no
    corte de um pedaço não é uma amostra, e somá-lo produziria um pico
    inventado. Divide-se por 32768 e não por 32767 porque o mínimo de um s16 é
    `-32768` — um «aaaa» saturado sairia acima de 1,0 pela outra régua.
    """
    if not pedaco:
        return 0.0
    amostras = array.array("h")
    amostras.frombytes(pedaco[: len(pedaco) // 2 * 2])
    if not amostras:
        return 0.0
    return max(abs(min(amostras)), abs(max(amostras))) / 32768.0


class OuvidoDoPico:
    """Lê o nível de uma fonte e DESCARTA a amostra. Nada vai para disco.

    O `parec` escreve cru no `stdout`; cada pedaço vira um número e morre na
    mesma linha. Nenhuma porta de disco se abre aqui, e a régua
    `test_o_codigo_do_ouvido_nao_sabe_escrever_arquivo` percorre a ÁRVORE deste
    código para garantir que continue assim — ela está com o microfone aberto
    na própria sala.
    """

    def __init__(self, fonte: str) -> None:
        self.fonte = fonte
        self._proc: subprocess.Popen[bytes] | None = None
        self._thread: threading.Thread | None = None
        self._parar = threading.Event()
        self._trava = threading.Lock()
        self._ultimo = 0.0
        self.maximo = 0.0
        self.pedacos = 0
        self.erro = ""

    @staticmethod
    def argv(fonte: str) -> list[str]:
        """O comando do leitor. Sem caminho de saída: o destino é o `stdout`."""
        return [
            LEITOR_DO_PICO,
            f"--device={fonte}",
            f"--rate={TAXA_DO_PICO}",
            "--channels=1",
            "--format=s16le",
            f"--latency-msec={LATENCIA_DO_PICO_MS}",
        ]

    def abrir(self) -> str | None:
        """Liga o ouvido. Devolve o MOTIVO quando não dá — nunca fica mudo."""
        if self._proc is not None:
            return None
        if not self.fonte:
            return "este controle não publica entrada nenhuma — peça o canal primeiro"
        if not shutil.which(LEITOR_DO_PICO):
            return f"não há `{LEITOR_DO_PICO}` nesta máquina, e é ele que lê o nível"
        try:
            self._proc = subprocess.Popen(
                self.argv(self.fonte),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except OSError as erro:
            self._proc = None
            return str(erro)
        self._parar.clear()
        self._thread = threading.Thread(target=self._laco, name="pico", daemon=True)
        self._thread.start()
        return None

    def _laco(self) -> None:
        saida = self._proc.stdout if self._proc is not None else None
        if saida is None:
            return
        while not self._parar.is_set():
            pedaco = saida.read(PEDACO_DO_PICO)
            if not pedaco:
                break
            nivel = pico_do_pedaco(pedaco)
            with self._trava:
                self._ultimo = nivel
                self.maximo = max(self.maximo, nivel)
                self.pedacos += 1

    def tomar(self) -> float:
        """O nível do último pedaço, e ele se ZERA na leitura.

        Zerar é o que faz a barra CAIR quando ela para de falar: sem isso o
        último pedaço alto ficaria pendurado dizendo «tem sinal» sobre silêncio.
        """
        with self._trava:
            valor, self._ultimo = self._ultimo, 0.0
            return valor

    def zerar_o_maximo(self) -> None:
        with self._trava:
            self.maximo = 0.0

    @property
    def ligado(self) -> bool:
        return self._proc is not None

    def fechar(self) -> None:
        """Termina PELO OBJETO do processo — nunca por padrão de linha de comando."""
        self._parar.set()
        proc, self._proc = self._proc, None
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        if proc is not None and proc.stdout is not None:
            proc.stdout.close()
        self._thread = None


# ---------------------------------------------------------------------------
# A TABELA — linha nova, não painel novo
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Linha:
    """Uma linha da folha: o que ela pergunta e com que forma ela pergunta.

    A folha se MONTA daqui. Pergunta nova é LINHA nova — é isso que faz esta
    folha aguentar o resto da fila do microfone sem virar seis painéis.
    """

    id: str
    titulo: str
    forma: str  #: leitura | pedido | pico | byte | campo | resposta
    pergunta: str
    sprint: str
    linha_do_mapa: str
    olhar: str = ""


LINHAS: tuple[Linha, ...] = (
    Linha(
        id="o-no-existe",
        titulo="1 · O nó existe?",
        forma="leitura",
        pergunta="o que o SISTEMA publica para este controle, agora — relido a cada volta",
        olhar="O nome que ela vê na lista de som. «NÃO EXISTE» aqui é a metade "
        "de cima da pergunta 3.",
        sprint="MIC-OS-QUATRO-01",
        linha_do_mapa="audio.microfone@dualsense",
    ),
    Linha(
        id="pedir-o-canal",
        titulo="2 · Pedir o canal",
        forma="pedido",
        pergunta="a ponte sobe sob demanda: com o pedido, o nó nasce? sem ele, some?",
        olhar="Aperte e olhe a linha 1. É o mesmo ato do 🎙 da tela "
        "(`mic.canal.set`), e ele mexe no mudo do firmware.",
        sprint="MIC-OS-QUATRO-01",
        linha_do_mapa="audio.microfone@dualsense",
    ),
    Linha(
        id="o-pico-ao-vivo",
        titulo="3 · O pico da captura, ao vivo",
        forma="pico",
        pergunta="o nó CAPTA? — fale «aaaa» e a barra sobe, ou não sobe",
        olhar="A barra. E o «máx», que é quem decide: o ouvido não guarda o "
        "patamar anterior. Nada é gravado.",
        sprint="MIC-OS-QUATRO-01",
        linha_do_mapa="audio.microfone@dualsense",
    ),
    Linha(
        id="o-byte-do-aparelho",
        titulo="4 · O byte do aparelho (common[6], 0 a 0x40)",
        forma="byte",
        pergunta="o byte do aparelho muda a captura, ou quem manda é só a fonte do sistema?",
        olhar="Arraste ENQUANTO fala e olhe o «máx» de cada parada. Com a chave "
        "«Assumir» desligada, este é o negativo: sem o bit, nada deve mudar.",
        sprint="MIC-VOLUME-02",
        linha_do_mapa="audio.microfone.volume@dualsense",
    ),
    Linha(
        id="o-campo-da-tela",
        titulo="5 · O campo que a tela oferece (a FONTE, 0-100 %)",
        forma="campo",
        pergunta="o ganho da fonte no PipeWire — a outra coisa, e ela mexe mesmo",
        olhar="É o deslizante do card na aba Controles. Compare com a linha 4: "
        "se só este move o pico, o byte não ganha campo.",
        sprint="MIC-VOLUME-02",
        linha_do_mapa="audio.microfone.volume@dualsense",
    ),
    Linha(
        id="o-daemon-responde",
        titulo="6 · O que o daemon responde",
        forma="resposta",
        pergunta="o daemon diz `sem_fonte` sobre um controle que TEM nó publicado?",
        olhar="Compare com a linha 1. Discordância aqui é a tarja da aba "
        "Controles, com a causa à mostra.",
        sprint="MIC-OS-QUATRO-01",
        linha_do_mapa="audio.microfone@dualsense",
    ),
)


def linha_de(id_: str) -> Linha:
    """A linha pelo `id`. Indexar `LINHAS` por posição quebra ao inserir uma linha."""
    for linha in LINHAS:
        if linha.id == id_:
            return linha
    raise KeyError(f"não há linha {id_!r} nesta folha")


def veredito_da_tarja(
    leitura: LeituraDoSistema, corpo: dict[str, Any] | None, *, perguntou: bool
) -> str:
    """A frase que põe o SISTEMA e o DAEMON lado a lado. Ela não conclui a sprint.

    Três discordâncias possíveis, e as três já aconteceram nesta casa:

    * o sistema publica e o daemon responde `sem_fonte` — é a tarja que mente;
    * o daemon atende, mas na fonte de OUTRO controle — é o defeito que o
      `por_uniq` existe para confessar;
    * ninguém publica nada e o daemon diz `sem_fonte` — aqui os dois CONCORDAM,
      e a tarja está certa: o que falta é o canal, não a frase.

    **`perguntou` NÃO É DECORAÇÃO, e ele nasceu de um defeito desta folha**,
    pego ao dirigi-la em 09/09/2026 antes de entregá-la: sem ele, a linha 6
    dizia *"o daemon não respondeu"* nos primeiros dois segundos, com o daemon
    de pé e ninguém tendo perguntado nada. *Régua que afirma sobre o que não
    mediu é a família de defeito mais cara desta casa* — e ela apareceu dentro
    do instrumento escrito para pegá-la.
    """
    if not perguntou:
        return (
            "ninguém perguntou ainda — aperte «Perguntar ao daemon», ou mexa no "
            "deslizante da linha 5"
        )
    if corpo is None:
        return "o daemon não respondeu — ou o Hefesto está parado, ou o socket não abriu"
    status = str(corpo.get("status") or "")
    fonte = str(corpo.get("fonte") or "")
    if status == "sem_fonte" and leitura.publica:
        return (
            "OS DOIS DISCORDAM: o sistema publica entrada para este controle e o "
            "daemon respondeu «sem_fonte» — é a tarja da aba Controles, e a causa "
            "está aqui"
        )
    if status == "sem_fonte":
        return (
            "concordam: ninguém publica entrada para este controle e o daemon diz "
            "«sem_fonte» — falta o canal, não a frase"
        )
    if fonte and leitura.escolhida and fonte != leitura.escolhida:
        return (
            f"O DAEMON MEXEU EM OUTRO NÓ: ele atendeu em «{fonte}» e o nó deste "
            f"controle é «{leitura.escolhida}»"
        )
    if status == "ok":
        return f"concordam: o daemon atendeu em «{fonte or '?'}»"
    return f"o daemon respondeu «{status or '?'}» — nem ok nem sem_fonte"


def frase_da_resposta_do_daemon(
    leitura: LeituraDoSistema, corpo: dict[str, Any] | None, *, perguntou: bool
) -> str:
    """A linha 6 inteira: a resposta CRUA e, embaixo, o veredito da tarja.

    **CRUA de propósito.** O campo que desmascara a tarja é o `status`, e um
    resumo bem-intencionado é justamente o que apagaria o `por_uniq` e o
    `fonte` — os dois que dizem em QUAL microfone o daemon mexeu. Quem lê aqui
    é ela, com o controle na mão, e o que ela precisa ver é o que o produto
    respondeu, não o que eu achei da resposta.

    Uma função só porque a linha 6 tem DOIS escritores — o botão «Perguntar ao
    daemon» e a releitura de 2 s — e dois textos para o mesmo lugar é como
    esta casa fabrica divergência silenciosa.
    """
    veredito = veredito_da_tarja(leitura, corpo, perguntou=perguntou)
    if not perguntou:
        return veredito
    return f"CRU: {corpo}\n{veredito}"


# ---------------------------------------------------------------------------
# Um controle na folha
# ---------------------------------------------------------------------------
@dataclass
class ControleNaFolha:
    """Uma coluna: o aparelho, o `common` vivo, a porta, o ouvido e as respostas."""

    alvo: Any
    common: bytearray = field(default_factory=common_vazio)
    assumido: bool = False
    escritas: int = 0
    erro: str = ""
    escritor: Escritor | None = None
    ouvido: OuvidoDoPico | None = None
    barra: float = 0.0
    leitura: LeituraDoSistema = field(default_factory=LeituraDoSistema)
    #: A ÚLTIMA resposta crua de cada ato do produto. Cruas de propósito: é o
    #: que desmascara a tarja, e resumir apagaria justamente o campo que conta.
    resposta_do_canal: dict[str, Any] | None = None
    resposta_do_volume: dict[str, Any] | None = None
    #: Alguém já perguntou ao daemon por ESTE controle? `None` de resposta antes
    #: da pergunta é *"não perguntei"*, e dizer «o daemon não respondeu» ali é
    #: acusar o produto de um silêncio que ninguém mediu.
    perguntou_ao_daemon: bool = False
    canal_pedido: bool = False
    volume_da_fonte: int = VOLUME_DA_FONTE_INICIAL

    @property
    def nome(self) -> str:
        return ("CABO" if self.alvo.transporte == CABO else "RÁDIO") + " · " + mascarar(
            self.alvo.mac
        )

    @property
    def curto(self) -> str:
        return "cabo" if self.alvo.transporte == CABO else "radio"

    @property
    def papel(self) -> str:
        """O cabo é o CONTROLE POSITIVO, e a folha diz isso na coluna dele."""
        if self.alvo.transporte == CABO:
            return "CONTROLE POSITIVO — o som pelo cabo funciona (placa USB própria)"
        return "o que se mede CONTRA o positivo do lado"

    # -- a porta, que só abre quando ela assume ----------------------------
    def _garantir_porta(self) -> bool:
        """Abre o hidraw no primeiro «Assumir». Antes disso, nada é escrito.

        Abrir na construção custaria uma concessão do broker por controle
        SEMPRE — inclusive em `--listar` e `--oculta`, que existem para provar
        este instrumento sem tocar em aparelho nenhum.
        """
        if self.escritor is not None:
            return not self.erro
        self.escritor = Escritor(self.alvo)
        try:
            self.escritor.abrir()
        except Exception as erro:
            self.erro = str(erro)
            return False
        self.erro = ""
        return True

    def assumir(self, ligado: bool) -> None:
        """Liga o bit `0x40` do `valid_flag0` — a posse, por controle e por ensaio."""
        if ligado and not self._garantir_porta():
            self.assumido = False
            return
        self.assumido = ligado
        if ligado:
            self.common[0] |= rep.VALID_FLAG0_MIC_VOLUME
        else:
            self.common[0] &= ~rep.VALID_FLAG0_MIC_VOLUME & 0xFF

    def escrever_byte(self, valor: int) -> None:
        self.common[rep.COMMON_MIC_VOLUME] = valor & 0xFF

    @property
    def byte(self) -> int:
        return self.common[rep.COMMON_MIC_VOLUME]

    def bater(self) -> None:
        """O martelo. Só bate o que ela assumiu — e só se a porta abriu."""
        if not self.assumido or self.escritor is None or self.erro:
            return
        try:
            self.escritor.escrever(self.common)
            self.escritas += 1
        except Exception as erro:
            self.erro = str(erro)

    def devolver(self) -> None:
        """Devolve o byte ao daemon. Só escreve se a porta chegou a abrir."""
        self.common = common_vazio()
        self.assumido = False
        if self.escritor is not None and not self.erro:
            try:
                self.escritor.escrever(self.common)
            except Exception as erro:
                self.erro = str(erro)

    def fechar(self) -> None:
        if self.ouvido is not None:
            self.ouvido.fechar()
            self.ouvido = None
        self.devolver()
        if self.escritor is not None:
            self.escritor.fechar()
            self.escritor = None

    # -- os atos do PRODUTO -------------------------------------------------
    def pedir_o_canal(self, ligado: bool) -> dict[str, Any] | None:
        """`mic.canal.set` — o mesmo ato do 🎙 da tela. Bloqueia: chame no fundo."""
        from hefesto_dualsense4unix.app import ipc_bridge

        corpo = ipc_bridge.mic_canal_set_detalhado(ligado, uniq=self.alvo.mac)
        self.resposta_do_canal = corpo
        self.canal_pedido = ligado and bool(corpo) and corpo.get("status") in ("ok", "incompleto")
        return corpo

    def mandar_o_volume(self, por_cento: int) -> dict[str, Any] | None:
        """`mic.volume.set` — o campo da tela. Bloqueia: chame no fundo."""
        from hefesto_dualsense4unix.app import ipc_bridge

        self.volume_da_fonte = por_cento
        corpo = ipc_bridge.mic_volume_set_detalhado(por_cento, uniq=self.alvo.mac)
        self.resposta_do_volume = corpo
        self.perguntou_ao_daemon = True
        return corpo

    # -- o ouvido -----------------------------------------------------------
    def ouvir(self) -> str | None:
        if self.ouvido is not None and self.ouvido.ligado:
            self.ouvido.fechar()
            self.ouvido = None
            return None
        self.ouvido = OuvidoDoPico(self.leitura.escolhida)
        motivo = self.ouvido.abrir()
        if motivo:
            self.ouvido = None
        return motivo


# ---------------------------------------------------------------------------
# A mesa, e a frase quando falta o par
# ---------------------------------------------------------------------------
def frase_da_mesa(alvos: list[Any]) -> str:
    """A mesa que esta folha ENCONTROU — e o que falta, com todas as letras.

    O desenho pede UM no cabo e UM no rádio (o positivo ao lado do que se
    mede). A folha não recusa a mesa que veio: ela funciona com dois, com
    quatro e com um. O que ela não faz é deixar quem lê achar que comparou
    transportes quando comparou um só.
    """
    cabos = sum(1 for a in alvos if a.transporte == CABO)
    radios = sum(1 for a in alvos if a.transporte == RADIO)
    if cabos and radios:
        return f"a mesa tem o par: {cabos} no cabo e {radios} no rádio."

    def conta(n: int, onde: str) -> str:
        if n == 0:
            return f"nenhum no {onde}"
        return f"{'um' if n == 1 else n} no {onde}"

    achei = " e ".join(x for x in (conta(cabos, "cabo"), conta(radios, "rádio")) if x)
    return (
        "FALTA O PAR: preciso de um no cabo e um no rádio; achei "
        + achei
        + ". Sem o positivo do cabo ao lado, silêncio no rádio não distingue "
        "«o aparelho não aceita» de «o meu tom está mudo»."
    )


# ---------------------------------------------------------------------------
# A folha
# ---------------------------------------------------------------------------
class Folha:
    #: O rótulo de cada forma de linha que tem botão. A tabela existe para o
    #: botão novo nascer aqui, e não espalhado por dez `if`.
    _BOTOES: ClassVar[dict[str, tuple[str, str]]] = {
        "pedido": ("Pedir o canal", "Soltar o canal"),
        "pico": ("Ouvir o pico", "Parar de ouvir"),
    }

    def __init__(self, controles: list[ControleNaFolha], *, enxuta: bool = False) -> None:
        self.controles = controles
        self.enxuta = enxuta
        self._relendo = False
        #: UMA NOTA POR (linha, controle). É a lição da folha irmã: uma nota por
        #: linha fazia o que ela viu NO CABO sair escrito na linha do RÁDIO.
        self.notas: dict[tuple[str, str], Gtk.Entry] = {}
        self.recados: dict[tuple[str, str], Gtk.Label] = {}
        self.barras: list[tuple[Gtk.DrawingArea, ControleNaFolha]] = []
        self.contadores: list[tuple[ControleNaFolha, Gtk.Label]] = []
        self.chaves: dict[str, Gtk.Switch] = {}

        self.janela = Gtk.Window(
            title="Ajustes do microfone" if enxuta else "O microfone de cada controle"
        )
        self.janela.set_default_size(960, 720 if enxuta else 820)
        self.janela.connect("destroy", self._fechar)
        self._fundo_opaco()

        raiz = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.janela.add(raiz)
        raiz.pack_start(self._topo(), False, False, 0)

        rolagem = Gtk.ScrolledWindow()
        rolagem.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        corpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        corpo.set_margin_top(10)
        corpo.set_margin_bottom(16)
        corpo.set_margin_start(14)
        corpo.set_margin_end(14)
        for linha in LINHAS:
            corpo.pack_start(self._secao(linha), False, False, 0)
        rolagem.add(corpo)
        raiz.pack_start(rolagem, True, True, 0)

        GLib.timeout_add(int(1000 / HZ), self._tique)
        GLib.timeout_add(int(RELER_A_LISTA_S * 1000), self._reler_a_lista)

    # ------------------------------------------------------------------ css
    def _fundo_opaco(self) -> None:
        """Fundo SÓLIDO. A razão é dela: *"o fundo tá muito transparente"*.

        Uma `Gtk.Window` sem widget de fundo herda o do compositor, e sob o
        COSMIC isso vira uma folha translúcida com o desktop dela atravessando
        — o pior fundo possível para quem olha uma barra subir.
        """
        # O DONO É `comum.pintar_fundo_solido` DESDE 10/09/2026, e a razão está
        # lá: estas três folhas decidiam o tema por `prefer-dark`, que é False
        # na máquina dela sob um tema ESCURO — e o rótulo do botão sumia dentro
        # do próprio botão. *"nao deu pra ler nada nos botoes"*.  # (noqa-acento: citação literal dela)
        pintar_fundo_solido(self.janela)

    # ----------------------------------------------------------------- topo
    def _topo(self) -> Gtk.Widget:
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        caixa.set_margin_top(10)
        caixa.set_margin_start(14)
        caixa.set_margin_end(14)

        quem = Gtk.Label()
        quem.set_markup("<b>" + "</b>   ·   <b>".join(c.nome for c in self.controles) + "</b>")
        quem.set_xalign(0.0)
        caixa.pack_start(quem, False, False, 0)

        texto_da_mesa = frase_da_mesa([c.alvo for c in self.controles])
        mesa = Gtk.Label()
        mesa.set_xalign(0.0)
        mesa.set_line_wrap(True)
        if texto_da_mesa.startswith("FALTA O PAR"):
            mesa.set_markup(
                f"<span foreground='#e5a50a'>{GLib.markup_escape_text(texto_da_mesa)}</span>"
            )
        else:
            mesa.set_text(texto_da_mesa)
            mesa.get_style_context().add_class("dim-label")
        caixa.pack_start(mesa, False, False, 0)

        if not self.enxuta:
            dica = Gtk.Label(
                label="Ligue «Assumir» na coluna, arraste o byte e FALE. Se o pico "
                "piscar entre dois patamares, o byte age — é o daemon disputando. "
                "Nada do que o microfone capta é gravado."
            )
            dica.set_xalign(0.0)
            dica.set_line_wrap(True)
            dica.get_style_context().add_class("dim-label")
            caixa.pack_start(dica, False, False, 0)

        linha = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for controle in self.controles:
            conta = Gtk.Label()
            conta.get_style_context().add_class("dim-label")
            self.contadores.append((controle, conta))
            linha.pack_start(conta, False, False, 0)
        tudo = Gtk.Button(label="Devolver TUDO ao daemon")
        tudo.connect("clicked", self._devolver_tudo)
        linha.pack_end(tudo, False, False, 0)
        caixa.pack_start(linha, False, False, 0)
        caixa.pack_start(Gtk.Separator(), False, False, 6)
        return caixa

    def _devolver_tudo(self, *_: Any) -> None:
        for controle in self.controles:
            controle.devolver()
        for chave in self.chaves.values():
            chave.set_active(False)

    # ---------------------------------------------------------------- seção
    def _secao(self, linha: Linha) -> Gtk.Widget:
        moldura = Gtk.Frame()
        dentro = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        for lado in ("top", "bottom", "start", "end"):
            getattr(dentro, f"set_margin_{lado}")(10 if lado in ("top", "bottom") else 12)

        titulo = Gtk.Label()
        titulo.set_markup(
            f"<b>{GLib.markup_escape_text(linha.titulo)}</b>"
            + ("" if self.enxuta else f"   <span size='small'>{linha.sprint}</span>")
        )
        titulo.set_xalign(0.0)
        dentro.pack_start(titulo, False, False, 0)

        if not self.enxuta:
            for texto, classe in ((linha.pergunta, None), (f"OLHE: {linha.olhar}", "dim-label")):
                if not texto:
                    continue
                rot = Gtk.Label(label=texto)
                rot.set_xalign(0.0)
                rot.set_line_wrap(True)
                if classe:
                    rot.get_style_context().add_class(classe)
                dentro.pack_start(rot, False, False, 0)

        colunas = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        colunas.set_homogeneous(True)
        colunas.set_margin_top(6)
        for controle in self.controles:
            colunas.pack_start(self._coluna(linha, controle), True, True, 0)
        dentro.pack_start(colunas, False, False, 0)

        if not self.enxuta:
            gravar = Gtk.Button(label="Gravar o que eu vi")
            gravar.connect("clicked", lambda _b, ln=linha: self.propor(ln))
            gravar.set_margin_top(6)
            dentro.pack_start(gravar, False, False, 0)

        moldura.add(dentro)
        return moldura

    def _coluna(self, linha: Linha, controle: ControleNaFolha) -> Gtk.Widget:
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        nome = Gtk.Label()
        nome.set_markup(f"<small>{GLib.markup_escape_text(controle.nome)}</small>")
        nome.set_xalign(0.0)
        caixa.pack_start(nome, False, False, 0)

        recado = Gtk.Label()
        recado.set_xalign(0.0)
        recado.set_line_wrap(True)
        recado.set_selectable(True)
        recado.get_style_context().add_class("dim-label")
        self.recados[(linha.id, controle.alvo.mac)] = recado

        montar = {
            "leitura": self._corpo_leitura,
            "pedido": self._corpo_pedido,
            "pico": self._corpo_pico,
            "byte": self._corpo_byte,
            "campo": self._corpo_campo,
            "resposta": self._corpo_resposta,
        }[linha.forma]
        montar(caixa, linha, controle)
        caixa.pack_start(recado, False, False, 0)

        if not self.enxuta:
            nota = Gtk.Entry()
            nota.set_placeholder_text(f"O que eu vi no {controle.curto}")
            nota.set_hexpand(True)
            self.notas[(linha.id, controle.alvo.mac)] = nota
            caixa.pack_start(nota, False, False, 4)
        return caixa

    # ------------------------------------------------------------- as formas
    def _corpo_leitura(self, caixa: Gtk.Box, _linha: Linha, controle: ControleNaFolha) -> None:
        papel = Gtk.Label()
        papel.set_markup(f"<small>{GLib.markup_escape_text(controle.papel)}</small>")
        papel.set_xalign(0.0)
        papel.set_line_wrap(True)
        caixa.pack_start(papel, False, False, 0)

    def _corpo_pedido(self, caixa: Gtk.Box, linha: Linha, controle: ControleNaFolha) -> None:
        botao = Gtk.Button(label=self._BOTOES["pedido"][0])
        botao.connect("clicked", self._clicar_pedido, controle, linha)
        caixa.pack_start(botao, False, False, 0)

    def _corpo_pico(self, caixa: Gtk.Box, linha: Linha, controle: ControleNaFolha) -> None:
        botoes = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        ouvir = Gtk.Button(label=self._BOTOES["pico"][0])
        ouvir.connect("clicked", self._clicar_pico, controle, linha)
        botoes.pack_start(ouvir, True, True, 0)
        zerar = Gtk.Button(label="Zerar o máx")
        zerar.connect("clicked", self._zerar_o_maximo, controle)
        botoes.pack_start(zerar, False, False, 0)
        caixa.pack_start(botoes, False, False, 0)

        barra = Gtk.DrawingArea()
        barra.set_size_request(-1, 26)
        barra.connect("draw", self._pintar_barra, controle)
        barra.set_tooltip_text(
            "O nível AGORA (barra) e o máximo desde que ela zerou (o traço). "
            "A amostra é descartada: nada vai para disco."
        )
        self.barras.append((barra, controle))
        caixa.pack_start(barra, False, False, 0)

    def _corpo_byte(self, caixa: Gtk.Box, linha: Linha, controle: ControleNaFolha) -> None:
        cabeca = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        cabeca.pack_start(Gtk.Label(label="common[6]"), False, False, 0)
        chave = Gtk.Switch()
        chave.set_tooltip_text(
            "Assumir: liga o flag0 0x40 deste controle e começa a martelar a 10 Hz. "
            "Desligada, o deslizante é o NEGATIVO do ensaio."
        )
        chave.connect("notify::active", self._virar_a_chave, controle, linha)
        self.chaves[controle.alvo.mac] = chave
        cabeca.pack_end(chave, False, False, 0)
        cabeca.pack_end(Gtk.Label(label="Assumir"), False, False, 0)
        caixa.pack_start(cabeca, False, False, 0)

        ajuste = Gtk.Adjustment(
            value=rep.TETO_MIC_VOLUME,
            lower=0,
            upper=rep.TETO_MIC_VOLUME,
            step_increment=1,
            page_increment=8,
        )
        escala = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=ajuste)
        escala.set_digits(0)
        escala.set_round_digits(0)
        escala.set_value_pos(Gtk.PositionType.RIGHT)
        escala.set_hexpand(True)
        for valor, texto in ((0, "0"), (0x20, "meio"), (rep.TETO_MIC_VOLUME, "teto 0x40")):
            escala.add_mark(valor, Gtk.PositionType.BOTTOM, texto)
        controle.escrever_byte(rep.TETO_MIC_VOLUME)
        escala.connect(
            "value-changed", lambda s, c=controle: c.escrever_byte(round(s.get_value()))
        )
        caixa.pack_start(escala, False, False, 0)

    def _corpo_campo(self, caixa: Gtk.Box, linha: Linha, controle: ControleNaFolha) -> None:
        ajuste = Gtk.Adjustment(
            value=VOLUME_DA_FONTE_INICIAL, lower=0, upper=100, step_increment=1, page_increment=10
        )
        escala = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=ajuste)
        escala.set_digits(0)
        escala.set_round_digits(0)
        escala.set_value_pos(Gtk.PositionType.RIGHT)
        escala.set_hexpand(True)
        for valor, texto in ((0, "0 %"), (50, "50 %"), (100, "100 %")):
            escala.add_mark(valor, Gtk.PositionType.BOTTOM, texto)
        # UM PEDIDO POR PIXEL ARRASTADO encheria o socket do daemon de gestos
        # mortos: o valor final é o único que importa, e ele vai sozinho.
        pendente: dict[str, int] = {}

        def marcar(escala_: Gtk.Scale) -> None:
            novo = round(escala_.get_value())
            ja_havia = "v" in pendente
            pendente["v"] = novo
            if not ja_havia:
                GLib.timeout_add(COALESCE_DO_DESLIZANTE_MS, soltar)

        def soltar() -> bool:
            valor = pendente.pop("v", None)
            if valor is not None:
                self._dizer(linha, controle, f"mandando {valor} % ao daemon…")
                self._mandar_volume(controle, valor)
            return False

        escala.connect("value-changed", marcar)
        caixa.pack_start(escala, False, False, 0)

    def _corpo_resposta(self, caixa: Gtk.Box, _linha: Linha, controle: ControleNaFolha) -> None:
        botao = Gtk.Button(label="Perguntar ao daemon")
        botao.set_tooltip_text(
            "Manda o `mic.volume.set` com o valor que a linha 5 já está mostrando "
            "— não muda nada, e traz a resposta CRUA."
        )
        botao.connect(
            "clicked", lambda _b, c=controle: self._mandar_volume(c, c.volume_da_fonte)
        )
        caixa.pack_start(botao, False, False, 0)

    # ------------------------------------------------------------ os cliques
    def _virar_a_chave(
        self, chave: Gtk.Switch, _p: Any, controle: ControleNaFolha, linha: Linha
    ) -> None:
        controle.assumir(chave.get_active())
        if chave.get_active() and not controle.assumido:
            chave.set_active(False)
        self._dizer(linha, controle, controle.erro or "", erro=bool(controle.erro))

    def _clicar_pedido(self, botao: Gtk.Button, controle: ControleNaFolha, linha: Linha) -> None:
        quero = not controle.canal_pedido
        botao.set_sensitive(False)
        self._dizer(linha, controle, "pedindo ao daemon…")

        def no_fundo() -> None:
            try:
                corpo = controle.pedir_o_canal(quero)
                frase = self._frase_do_pedido(corpo, quero)
            except Exception as erro:  # o daemon não derruba a folha dela
                corpo, frase = None, f"o pedido falhou: {erro}"
            GLib.idle_add(terminar, frase, corpo is None)

        def terminar(frase: str, ruim: bool) -> bool:
            botao.set_sensitive(True)
            botao.set_label(self._BOTOES["pedido"][1 if controle.canal_pedido else 0])
            self._dizer(linha, controle, frase, erro=ruim)
            return False

        threading.Thread(target=no_fundo, name="pedir-canal", daemon=True).start()

    @staticmethod
    def _frase_do_pedido(corpo: dict[str, Any] | None, quero: bool) -> str:
        """As DUAS metades do ato viajam separadas — e é isso que ela precisa ver."""
        if corpo is None:
            return "o daemon não respondeu ao `mic.canal.set`"
        status = corpo.get("status")
        canal = corpo.get("canal_feito")
        firmware = corpo.get("firmware_pedido")
        motivo = corpo.get("motivo") or ""
        verbo = "ligar" if quero else "desligar"
        return (
            f"{verbo}: status={status} · canal_feito={canal} · firmware_pedido={firmware}"
            + (f" · {motivo}" if motivo else "")
            + " — olhe a linha 1"
        )

    def _clicar_pico(self, botao: Gtk.Button, controle: ControleNaFolha, linha: Linha) -> None:
        motivo = controle.ouvir()
        ligado = controle.ouvido is not None and controle.ouvido.ligado
        botao.set_label(self._BOTOES["pico"][1 if ligado else 0])
        if motivo:
            self._dizer(linha, controle, motivo, erro=True)
        elif ligado:
            self._dizer(
                linha, controle, f"ouvindo «{controle.leitura.escolhida}» — fale «aaaa»"
            )
        else:
            self._dizer(linha, controle, "ouvido fechado")

    def _zerar_o_maximo(self, _b: Gtk.Button, controle: ControleNaFolha) -> None:
        if controle.ouvido is not None:
            controle.ouvido.zerar_o_maximo()
        controle.barra = 0.0

    def _mandar_volume(self, controle: ControleNaFolha, valor: int) -> None:
        """O `mic.volume.set`, no FUNDO: ele tem teto de 6 s e travaria a folha.

        A RESPOSTA VAI PARA A LINHA 6, venha o pedido do deslizante da linha 5
        ou do botão da 6. A linha 6 é a que tem esse trabalho, e escrever a
        resposta em dois lugares diferentes conforme quem pediu deixaria ela
        procurando o `status` em dois lugares.
        """
        linha = linha_de("o-daemon-responde")

        def no_fundo() -> None:
            try:
                controle.mandar_o_volume(valor)
            except Exception as erro:
                controle.resposta_do_volume = None
                controle.perguntou_ao_daemon = True
                GLib.idle_add(self._dizer, linha, controle, f"o pedido falhou: {erro}", True)
                return
            GLib.idle_add(self._pintar_a_resposta, controle)

        threading.Thread(target=no_fundo, name="mic-volume", daemon=True).start()

    def _pintar_a_resposta(self, controle: ControleNaFolha) -> bool:
        """A linha 6, do jeito que ela é: o corpo CRU e o veredito da tarja."""
        frase = frase_da_resposta_do_daemon(
            controle.leitura,
            controle.resposta_do_volume,
            perguntou=controle.perguntou_ao_daemon,
        )
        self._dizer(
            linha_de("o-daemon-responde"),
            controle,
            frase,
            erro="DISCORDAM" in frase or "OUTRO NÓ" in frase,
        )
        return False

    def _dizer(
        self, linha: Linha, controle: ControleNaFolha, texto: str, erro: bool = False
    ) -> bool:
        recado = self.recados.get((linha.id, controle.alvo.mac))
        if recado is None:
            return False
        if erro:
            recado.set_markup(
                f"<span foreground='#c01c28'>{GLib.markup_escape_text(texto)}</span>"
            )
        else:
            recado.set_text(texto)
        return False

    # --------------------------------------------------------------- pintura
    def _pintar_barra(self, area: Gtk.DrawingArea, cr: Any, controle: ControleNaFolha) -> bool:
        largura, altura = area.get_allocated_width(), area.get_allocated_height()
        cr.set_source_rgb(0.16, 0.16, 0.16)
        cr.rectangle(0, 0, largura, altura)
        cr.fill()
        nivel = max(0.0, min(1.0, controle.barra))
        cr.set_source_rgb(0.18, 0.76, 0.49)
        cr.rectangle(0, 0, largura * nivel, altura)
        cr.fill()
        maximo = controle.ouvido.maximo if controle.ouvido is not None else 0.0
        if maximo > 0:
            x = largura * max(0.0, min(1.0, maximo))
            cr.set_source_rgb(1.0, 1.0, 1.0)
            cr.set_line_width(2.0)
            cr.move_to(x, 0)
            cr.line_to(x, altura)
            cr.stroke()
        cr.set_source_rgb(0.92, 0.92, 0.92)
        cr.move_to(6, altura - 8)
        cr.show_text(f"agora {nivel:.4f}   máx {maximo:.4f}")
        return False

    # ------------------------------------------------------------------ laço
    def _tique(self) -> bool:
        for controle in self.controles:
            controle.bater()
            if controle.ouvido is not None:
                controle.barra = max(controle.ouvido.tomar(), controle.barra - QUEDA_DA_BARRA)
            else:
                controle.barra = 0.0
        for barra, _ in self.barras:
            barra.queue_draw()
        for controle, conta in self.contadores:
            if controle.erro:
                conta.set_markup(
                    f"<span foreground='#c01c28'>{GLib.markup_escape_text(controle.nome)}: "
                    f"{GLib.markup_escape_text(controle.erro)}</span>"
                )
            else:
                conta.set_text(
                    f"{controle.nome}: byte {controle.byte:#04x}, "
                    f"{'assumido' if controle.assumido else 'do daemon'}, "
                    f"{controle.escritas} escritas"
                )
        return True

    def _reler_a_lista(self) -> bool:
        """A lista viva, num TRABALHADOR: o `pactl` tem teto de 8 s e travaria a folha."""
        if self._relendo:
            return True
        self._relendo = True

        def no_fundo() -> None:
            try:
                leituras = ler_o_sistema([c.alvo for c in self.controles])
            except Exception:
                leituras = {}
            GLib.idle_add(pintar, leituras)

        def pintar(leituras: dict[str, LeituraDoSistema]) -> bool:
            for controle in self.controles:
                nova = leituras.get(controle.alvo.mac)
                if nova is not None:
                    controle.leitura = nova
                self._dizer(linha_de("o-no-existe"), controle, controle.leitura.frase())
                self._pintar_a_resposta(controle)
                # O OUVIDO DIZ ONDE ESCUTARIA antes de ser aberto. Um botão que
                # só explica depois de apertado esconde o «não há o que ouvir».
                ouvindo = controle.ouvido is not None and controle.ouvido.ligado
                if not ouvindo:
                    onde = controle.leitura.escolhida
                    self._dizer(
                        linha_de("o-pico-ao-vivo"),
                        controle,
                        f"ouvido fechado — abriria em «{onde}»"
                        if onde
                        else "não há entrada para ouvir: peça o canal na linha 2",
                    )
            self._relendo = False
            return False

        threading.Thread(target=no_fundo, name="reler-a-lista", daemon=True).start()
        return True

    # -------------------------------------------------------------- o caderno
    def propor(self, linha: Linha) -> None:
        """A folha NÃO conclui: imprime as linhas, e quem coordena as escreve."""
        print(f"\nLINHAS PROPOSTAS — {linha.titulo} (docs/data/ensaios.csv):")
        for controle in self.controles:
            caixa = self.notas.get((linha.id, controle.alvo.mac))
            nota = caixa.get_text().strip() if caixa is not None else ""
            if not nota:
                print(f"  (o {controle.nome} ficou sem resposta — nada a propor por ele)")
                continue
            print(
                linha_do_caderno(
                    id=f"folha-mic-{linha.id}-{controle.curto}-{_agora_ddmm()}",
                    linha_id=linha.linha_do_mapa,
                    transporte=controle.curto,
                    suspeito=linha.pergunta,
                    presente="sim" if controle.leitura.publica else "não",
                    resultado="",
                    observado_por="olho-dela",
                    fonte="scripts/ensaios/a_folha_do_microfone_por_controle.py",
                    nota=self._nota_da_linha(linha, controle, nota),
                )
            )
        sys.stdout.flush()

    def _nota_da_linha(self, linha: Linha, controle: ControleNaFolha, dela: str) -> str:
        """O que a linha do caderno carrega de MEDIDO, além da frase dela."""
        maximo = controle.ouvido.maximo if controle.ouvido is not None else 0.0
        medido = [
            f"sistema: {controle.leitura.frase()}",
            f"byte common[6]={controle.byte:#04x}",
            f"flag0 0x40 {'ligado' if controle.assumido else 'apagado'}",
            f"martelo {HZ:g} Hz",
            f"pico máx {maximo:.4f}",
            f"fonte {controle.volume_da_fonte} %",
            "daemon: "
            + (
                str(controle.resposta_do_volume)
                if controle.perguntou_ao_daemon
                else "não perguntei"
            ),
        ]
        if linha.forma == "pedido":
            medido.append(f"mic.canal.set: {controle.resposta_do_canal}")
        return "; ".join(medido) + f"; ela: {dela}"

    # ---------------------------------------------------------------- ciclo
    def _fechar(self, *_: Any) -> None:
        for controle in self.controles:
            controle.fechar()
        if Gtk.main_level() > 0:
            Gtk.main_quit()

    def abrir(self) -> None:
        self.janela.show_all()
        Gtk.main()


# ---------------------------------------------------------------------------
# As bandeiras
# ---------------------------------------------------------------------------
def _cabecalho() -> str:
    return cabecalho_do_instrumento(
        "a_folha_do_microfone_por_controle",
        "o mic de cada controle sobe, capta, e o byte do aparelho muda a captura?",
        bibliotecas=[
            "hefesto_dualsense4unix.core.ds_output_report",
            "hefesto_dualsense4unix.integrations.canal_do_microfone",
            "hefesto_dualsense4unix.integrations.audio_control",
        ],
        escreve_no_aparelho=True,
    )


def listar(alvos: list[Any]) -> int:
    """`--listar`: SÓ LÊ. Nenhuma porta abre, nenhum byte sai, nenhum mic liga."""
    print(_cabecalho())
    print(
        "\nnesta corrida NADA foi escrito: a porta do hidraw só abre no primeiro\n"
        "«Assumir», e o ouvido do pico só no botão «Ouvir o pico».\n"
    )
    print(frase_da_mesa(alvos) + "\n")
    leituras = ler_o_sistema(alvos)
    largura = f"{'controle':<22} {'transp.':<7} o que o sistema publica"
    print(largura)
    print("-" * 100)
    for a in alvos:
        leitura = leituras.get(a.mac, LeituraDoSistema())
        print(f"{mascarar(a.mac):<22} {a.transporte:<7} {leitura.frase()}")
    print(f"\n{'linha':<22} {'sprint':<20} o que ela decide")
    print("-" * 100)
    for linha in LINHAS:
        print(f"{linha.id:<22} {linha.sprint:<20} {linha.pergunta}")
    faltando = [
        f"{mascarar(a.mac)} ({a.transporte})"
        for a in alvos
        if not leituras.get(a.mac, LeituraDoSistema()).publica
    ]
    if faltando:
        print(
            resumo(
                "sem entrada publicada: "
                + " · ".join(faltando)
                + " — é a linha 2 desta folha (o botão «Pedir o canal») que responde."
            )
        )
        return 0
    print(resumo(f"os {len(alvos)} controles têm entrada publicada na lista viva."))
    return 0


def main(argv: list[str] | None = None) -> int:
    argumentos = list(sys.argv[1:] if argv is None else argv)
    desconhecidas = [
        a for a in argumentos if a not in (*BANDEIRAS_SEM_TELA, "--so-ajustes")
    ]
    if desconhecidas:
        print(f"bandeira que esta folha não conhece: {desconhecidas} — veja o bloco USO.")
        return 2

    alvos = alvos_da_mesa()
    if not alvos:
        print("nenhum DualSense físico encontrado. Plugue ou pareie e rode de novo.")
        return 1

    if "--listar" in argumentos:
        return listar(alvos)

    print(_cabecalho())
    print("\n" + frase_da_mesa(alvos))
    controles = [ControleNaFolha(a) for a in alvos]
    try:
        for mac, leitura in ler_o_sistema(alvos).items():
            for controle in controles:
                if controle.alvo.mac == mac:
                    controle.leitura = leitura
    except Exception as erro:
        print(f"a lista viva não respondeu ({erro}) — as linhas dirão por quê")
    print(f"controles: {', '.join(c.nome for c in controles)}")
    print(f"linhas na folha: {len(LINHAS)}")

    folha = Folha(controles, enxuta="--so-ajustes" in argumentos)
    if "--oculta" in argumentos:
        # A RÉGUA: monta a folha, bate um tique e propõe. Nada é assumido, logo
        # `bater()` não escreve, a porta não abre e nenhum microfone liga.
        folha._tique()
        for linha in LINHAS:
            folha.propor(linha)
        folha._fechar()
        return 0
    folha.abrir()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
