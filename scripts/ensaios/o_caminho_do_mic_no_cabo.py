#!/usr/bin/env python3
"""o_caminho_do_mic_no_cabo.py — MIC-CABO-LIMPO-01: o censo do caminho do cabo.

A QUEIXA, E ELA É DELA — 17/09/2026:

    *"sobre o mic do cabo ficar limpo igual o do mic no bt"*  # noqa-acento: citação literal dela

E o outro lado da mesma frase, do mesmo dia, sobre o RÁDIO: *"o som do mic ta
divino"*.  # noqa-acento: citação literal dela

POR QUE ESTE INSTRUMENTO EXISTE, E POR QUE ELE NÃO CURA NADA
=============================================================

Os dois transportes **não são o mesmo caminho degradado** — são cadeias
diferentes que se encontram só na metade final. Medido no código em 17/09/2026:

* **rádio:** aparelho → DSP de voz do firmware → Opus 48 kHz MONO → report 0x31
  → nosso decodificador → ``SourceVirtualPipeWire.escrever`` → fifo → nó.
  **Dois ganhos** (o ``common[6]`` do aparelho e o volume do nó), **zero
  conversão de formato**, e o ``common[7]`` com
  ``FORCE_INTERNAL_MIC | ECHO_CANCEL`` sai em TODO report 0x35 montado
  (``integrations/alto_falante_bt.py``, o ``COMMON_AUDIO_PATH``).
* **cabo:** aparelho → USB Audio Class → placa ALSA → perfil da placa →
  elemento de mixer de captura → nó PipeWire → ``parec`` → **remix e/ou
  reamostragem feitos pelo pipewire-pulse** → o MESMO ``escrever`` → o MESMO
  fifo → o MESMO nó. **Quatro ganhos e até duas conversões**, e o ``common[7]``
  só sai se alguém pedir uma ROTA de alto-falante — o que por omissão ninguém
  pede (``_byte_da_rota`` devolve ``None`` quando ``rota is None``, e
  ``set_speaker_volume`` nasce com ``rota=None``).

**Nenhum desses estágios a mais foi escolhido por ninguém desta casa.** Este
instrumento existe para pôr um NÚMERO em cada um deles, um fator por vez, antes
de qualquer cura — porque esta casa já pagou três vezes esta semana por escolher
um candidato sem medir.

**O QUE JÁ FOI CURADO SEM APARELHO, e não está mais nesta fila:** o pedaço que o
alimentador do cabo entregava ao fifo era de 4096 B = 42,7 ms, contra os 960 B =
10 ms do quadro do rádio, e o fifo descarta o pedaço INTEIRO quando não cabe
(4096 é exatamente o ``PIPE_BUF`` do Linux: ou entra tudo, ou não entra nada).
Ver ``integrations/canal_do_microfone.pedaco_do_bombeador`` e a régua
``test_um_descarte_no_cabo_nao_custa_mais_voz_que_um_no_radio``.

AS QUATRO HIPÓTESES, EM ORDEM DE FORÇA
=======================================

**H1 — o ganho de hardware que o produto não sabe que existe. A HIPÓTESE VIROU
DO AVESSO EM 20/09/2026, e a cura de uma ponta é o contrário da cura da outra.**
O elemento ALSA de captura do DualSense no cabo chama-se ``Headset`` (Feature
Unit 5 do descritor UAC, faixa 0…12288 = 0…+48 dB). A MIC-USB-01 o mediu a
**31%** em 25/07/2026; **esse número caiu**. Lido em repouso em 17/09 e de novo
em 20/09/2026, nesta bancada: ``Mono: Capture 101 [100%] [48.00dB] [on]`` — **no
topo da faixa**.

A H1 dizia *"um sinal que nasce a um terço e é amplificado depois"*; o que se
mede é o **oposto**: o sinal nasce com **+48 dB de ganho que ninguém escolheu**,
e o produto não alcança o botão.
``grep -rn "amixer|alsactl|snd_ctl|alsaaudio" src/ scripts/ install.sh``
continua **VAZIO**, e a ``mic.volume`` dela trava em 0–100% em
``integrations/audio_control.py`` — ela atenua, nunca amplifica, e não fala com
este elemento. A pergunta deixa de ser *"falta ganho?"* e passa a ser **"sobra
ganho, e ele não tem dono"**.

O que decide se esses +48 dB pioram o som é se o ganho é analógico (o pré-amp
traz ruído próprio) ou digital (o SNR não muda) — e **isso não se sabe**. Só o
par controlado do ``--ganho`` separa os dois, ele ESCREVE no mixer dela, e por
isso é janela própria, com ela presente. Ver ``--ganho-plano``.

**H2 — o remix que ninguém escolheu.** O ``parec`` do alimentador é lançado com
``--rate``/``--channels`` tirados do **DESTINO** (o ``module-pipe-source``, que é
mono 48 kHz), nunca da **ORIGEM**. Se o nó do cabo for estéreo, o pipewire-pulse
faz um remix 2→1 que ninguém pediu. E a casa já mediu, do lado da SAÍDA, que o
DualSense por USB põe coisas diferentes em canais diferentes: se a ENTRADA
repetir o padrão — o mono num canal só do par —, o remix custa 6 dB e traz o
ruído do canal morto junto. **Nenhuma régua desta casa lê o formato da ORIGEM**,
então isso hoje é invisível a todos os portões.

    **NOTA DE 20/09/2026 — a H2 sai da posição de candidata forte, e não é
    apagada.** O remix 2 → 1 **não é, por si, uma perda**: a média ``(L+R)/2``
    de dois microfones *melhora* o SNR em cerca de **3 dB**, porque o sinal é
    correlacionado e soma coerente enquanto o ruído, descorrelacionado, cai por
    raiz de 2. E as amostras já medidas confirmam o array de dois microfones —
    energia praticamente igual nos dois canais (RMS 86,56 × 87,43) com apenas
    **14,4%** de amostras idênticas (20.702 de 144.000), que é ruído
    descorrelacionado, não mono duplicado nem canal morto. O ``Capture Channel
    Map`` da placa fecha: ``chmap-fixed=FL,FR``, dois canais de verdade.
    O que **ainda poderia** degradar é *comb filtering* por diferença de fase
    entre os dois microfones — e isso **não foi medido**. A correlação cruzada
    só responde com FALA: sobre ruído de fundo ela é plana por construção, e
    *"não há atraso"* seria indistinguível de *"o instrumento não mede"*.
    **Essa medição precisa da orelha dela.**

**H3 — o ``common[7]`` que não sai no cabo.** Pelo rádio a base segura vai
incondicionalmente; pelo cabo, por omissão, o byte nunca é escrito e o firmware
fica no default DELE. ``ds_output_report`` afirma que esse default traz o
cancelamento ligado — e **ninguém mediu isso no cabo**.

**H4 — o ``NOISE_CANCEL``, que é gosto e é dela.**
``AUDIO_CONTROL_NOISE_CANCEL`` (bit3 do ``common[7]``) **não tem um único
escritor, em transporte nenhum**. Está fora da base por decisão escrita de
16/09/2026: *«mexe na qualidade da CAPTURA (…) O eco é defeito; o ruído é
gosto»*. A frase dela de 17/09 é o pedido que reabre essa decisão.

O ROTEIRO, UM FATOR POR VEZ
============================

**PASSO 0 — o controle no cabo. É DELA, e nada abaixo se mede sem ele.**

**PASSO 1 — o censo (este instrumento, ``--censo``).** Lê e não escreve: o
perfil ativo da placa, o formato e o mapa de canais do nó do cabo, o elemento de
captura do mixer ALSA e a sua porcentagem, e os parâmetros NATIVOS do endpoint
USB. Fecha sem a orelha dela.

**PASSO 2 — decide a H2 (este instrumento, ``--canais``).** Grava a origem em
DOIS canais e mede RMS e pico de CADA canal separado. Se um dos dois estiver
morto ou só com ruído, o remix está custando 6 dB e trazendo lixo junto. Fecha
sem a orelha dela.

A cura da H2, se ela se confirmar, **não é fixar «canal 0»** dentro do
``canal_do_microfone``: é o alimentador PERGUNTAR à origem o que ela é, e quem
responde tem de ser o dono único que já existe
(``integrations/fontes_de_captura``). Uma segunda régua escrita dentro do
``canal_do_microfone`` sobre o mesmo estado é RECEITA-ERRADA-01 de novo.

**PASSO 3 — decide a H1 (mede sozinho; o VALOR final é dela).** A mesma frase,
a mesma duração, com o ``Headset`` na porcentagem de hoje e depois mais alto:
RMS, pico e **piso de ruído entre as frases**. Se o piso subir junto com a voz,
o ganho não é a cura; se a voz subir e o piso ficar, é. Ganho demais satura, e
por isso o número final é dela.

O dono da cura, se ela se confirmar, é o ``scripts/doctor.sh``: ele JÁ é o dono
da camada 2 (o perfil da placa, ``_dualsense_perfil_status``) e já tem o
``--fix``. **Não** o daemon, e **não** um ``subprocess`` solto numa integração.
É capacidade nova — o produto não tem uma linha de ``amixer`` —, e por isso
precisa nascer com portão.

**PASSO 4 — decide a H3 (mede sozinho).** 10 s com o byte não escrito (o estado
de hoje) e 10 s com ``AUDIO_CONTROL_BASE_SEGURA`` escrito, pelo broker, como
fazem os instrumentos de 09/09. Se não mudar nada, a hipótese cai e fica
registrado que o default do firmware já traz o cancelamento no cabo.

**PASSO 5 — A ORELHA DELA, E SÓ ELA: o ``NOISE_CANCEL``.** Duas passadas iguais,
com e sem o bit3, pelo ``scripts/ensaios/a_folha_dos_ensaios.py``, como em
``folha-mic-volume-o-byte-age-cabo-0909``. **A palavra dela decide.**

**PASSO 6 — o descarte (barato).** Com alguém gravando pelo cabo por 60 s, ler
``descartes`` do ``SourceVirtualPipeWire``. Se não for zero, o defeito é o
alimentador que não segue o SUSPENDED/RUNNING da source — dívida já nomeada no
cabeçalho do ``canal_do_microfone``, devida à ONDA5-MIC-VIRTUAL-02.

O QUE VALE NOS DOIS TRANSPORTES, E É ORDEM DELA
================================================

**Cura por transporte é proibida** — ordem dela de 16/09/2026, o app é de
acessibilidade, trave a CLASSE. Qualquer opinião nova sobre o ``NOISE_CANCEL``
ou sobre o ganho de captura vale nos DOIS transportes, com a mesma justificativa
escrita. Ligar o bit3 só no cabo seria exatamente a cura por instância que ela
vetou.

E pela ordem dela de 17/09 — *"os jogos e perfis tem que iniciar com todas as
features ativadas por default"* — o que o passo 5 decidir deixa de ser um bit
sem opinião e passa a ter um **default escrito e justificado**.

AS ARMADILHAS DESTE CAMINHO, e as três já custaram
====================================================

1. **O fato velho da MIC-USB-01 já caiu.** A tabela daquela sprint diz que o
   ``iec958`` é *«S/PDIF — sem sinal»* e que o mic *«vive»* no analógico. Medido
   em 26/07 e registrado em ``scripts/doctor.sh``: **forçar o analógico
   SILENCIA o microfone** (327.680 B de silêncio, source sem porta de captura);
   o pico 0 de 25/07 era o mudo do FIRMWARE, camada 3. Quem medir sem ler o
   doctor primeiro reproduz a «cura» que emudecia quem a rodasse.
2. **Zero não é o lado neutro do ``common[7]``, e não escrever também não é.**
   As duas lições de 16/09, uma virada do avesso da outra. Não mande ``0x00``
   *"para limpar"* e não deixe de escrever *"para não mexer"*: cada bit é uma
   decisão, inclusive a de deixá-lo em zero.
3. **O par que a casa tem NÃO é um par controlado.** Cabo em 26/07 (pico 4606,
   RMS 374) contra rádio em 16/09 (pico 8627, RMS 303,2): dias, falas,
   durações e instrumentos diferentes. Serve para ordenar hipóteses, nunca para
   fechar uma. O par que decide é novo: mesma frase, mesma duração, mesmo
   comando, **um fator por vez**.

E A ARMADILHA DE NOME: a sprint ``SOM-CABO-QUALIDADE-01``, de hoje, tem quase
este nome e é do **ALTO-FALANTE** no cabo, não do microfone. A posse dela é
``integrations/alto_falante_bt.py``. São duas peças.

A PORTA, DECLARADA
===================
Este instrumento mede por **PulseAudio/ALSA** (``pactl``, ``amixer``,
``arecord``, ``parec``). **Não toca hidraw, não escreve no aparelho, não fala
com o daemon.** O passo 4 é o único que escreve, e ele NÃO está aqui: ele é do
``escrita_pelo_broker.py``, que é a porta desta casa para isso.

O QUE O DESCRITOR USB JÁ RESPONDEU, E FECHOU — MIC-CABO-SPDIF-01
=================================================================

A porta de captura que o PipeWire mostrava em 17/09 chamava-se
``iec958-stereo-input`` e dizia «Entrada digital S/PDIF». **O aparelho não tem
S/PDIF nenhum.** O ``--descritor`` prova isso sem servidor de som, sem daemon e
em qualquer máquina: ele LÊ ``/sys/bus/usb/devices/<X>/descriptors`` e traduz
cada ``wTerminalType`` por uma tabela do padrão UAC que mora dentro do
instrumento. A captura sai pelo terminal **0x0402, «Headset»**; os dois códigos
que significariam digital — ``0x0602`` («Digital audio interface») e ``0x0605``
(«S/PDIF interface») — **não aparecem em lugar nenhum do descritor**. A palavra
``iec958`` era invenção do lado do host: o DualSense falta na tabela
``cards.USB-Audio.pcm.iec958_device`` do ``alsa-lib``, então ``iec958:CARD=…``
cai no ``default 0`` e **é** ``hw:CARD,0`` — o mesmo e único PCM da placa.

**Nenhum número desta seção é digitado: o valor vem do aparelho, o nome vem da
tabela.** Se a Sony mudar o descritor num firmware novo, o instrumento acusa.

O QUE FOI MEDIDO EM 20/09/2026, E O QUE NÃO FOI
================================================

Com um DualSense no cabo, tudo por leitura pura (``/proc``, ``/sys``, ``dpkg``,
``amixer`` de consulta). **Nada tocou o servidor de som dela.**

**FECHADO — o ganho em repouso.** ``Headset: Mono: Capture 101 [100%]
[48.00dB] [on]``, lido duas vezes, com intervalo, e **idêntico** às duas. É
valor de repouso, não um terceiro dono mexendo.

**FECHADO — o ``ctlerr=1``, e a ambiguidade era do LEITOR.** O ``ctlerr`` de
``/proc/asound/cardN/usbmixer`` **não é contador de erro**: é o
``ignore_ctl_error`` do mixer. Nesta máquina ele vem do quirk **desta casa** —
``/etc/modprobe.d/hefesto-dualsense-storm.conf`` (SPRINT-GAME-RUMBLE-01) traz
``quirk_flags=054c:0ce6:ignore_ctl_error|ctl_msg_delay_1m`` — enquanto o
parâmetro global ``ignore_ctl_error`` continua em ``N``. E o log do kernel não
traz uma linha de erro de mixer para esta placa. Logo não há defeito de leitura
a suspeitar, e a porta analógica depende do fone, como a estrutura dizia.

**FECHADO — o comando que a sprint mandava rodar estava errado.**
``amixer -c N cget name='Headset Mic Jack'`` **falha** com «Cannot find the
given element»: os dois jacks vivem em ``iface=CARD``, e o ``cget`` procura em
``iface=MIXER``. Quem lê é ``amixer -c N contents``. Ler a falha como «o jack
não existe» seria concluir o contrário do que há.

**NÃO MEDIDO, com a razão** — os três, e nenhum é conclusão:

* **o par com fone / sem fone.** Lidos agora, ``Headphone Jack`` e
  ``Headset Mic Jack`` estão os dois em ``off`` — coerente com nada plugado no
  P2. O outro lado do par precisa da mão dela.
* **``hw:N,0`` direto contra a porta.** O nó de captura está **RUNNING**, então
  o ``arecord`` disputa o PCM e volta ocupado. **Ocupado não é «o caminho está
  quebrado»** — esta casa já concluiu isso sobre um caminho sadio. Só vale com
  o nó conferidamente suspenso, e suspender o nó é mexer no som dela.
* **o *comb filtering* entre L e R.** Precisa de FALA: sobre ruído de fundo a
  correlação cruzada é plana por construção, e *"não há atraso"* seria
  indistinguível de *"o instrumento não mede"*.

**E O MUNDO MUDOU ENTRE 17 E 20/09, o que muda o DONO do defeito.** Com o UCM
desta casa instalado (HAPTICA-NATIVA-01), o perfil da placa passou a ser
``HiFi`` e a porta de captura passou de ``iec958-stereo-input`` (do
``alsa-card-profile`` da distro) para ``[In] Mic``, do nosso
``assets/ucm/DualSense-HiFi.conf``. **O ganho continua fora de alcance pelo
mesmo motivo e por outro dono:** o ``SectionDevice."Mic"`` declara
``CapturePCM`` e ``CapturePriority``, e nenhum ``CaptureVolume`` ou
``CaptureMixerElem``.

A RECOMENDAÇÃO, EM UMA LINHA, PARA ELA
=======================================

**NÃO trocar o perfil da placa** — o perfil está certo e quem mentia era o nome;
trocar corta o áudio no meio da sessão e, sem headset no P2, devolve a source
sem porta de captura que já entregou 327.680 bytes de silêncio digital.
**O que há a decidir é outra coisa:** se o Hefesto passa a LIGAR o
``Headset Capture Volume`` no próprio UCM — o que põe o ganho ao alcance da tela
e dela — e, se sim, com que valor, porque hoje ele está no topo (+48 dB) e
ninguém escolheu isso. O preço de cada lado: **ligar** dá o botão a ela e deixa
o WirePlumber restaurar volume de captura por rota (que é uma camada a mais de
estado persistido, a mesma família do mudo da camada 1); **não ligar** mantém os
+48 dB fixos, fora do alcance de todos. A medição que separa as duas é o
``--ganho``, e ela é com a orelha dela.

USO
====
    scripts/ensaios/o_caminho_do_mic_no_cabo.py --censo
    scripts/ensaios/o_caminho_do_mic_no_cabo.py --descritor
    scripts/ensaios/o_caminho_do_mic_no_cabo.py --canais --segundos 10
    scripts/ensaios/o_caminho_do_mic_no_cabo.py --ganho-plano

Sem argumento, faz o censo. O ``--descritor`` é o único que roda com o servidor
de som caído. O ``--ganho-plano`` **imprime o protocolo e não mede nada**: o
passo que ele descreve escreve no mixer dela.
"""

from __future__ import annotations

import argparse
import array
import math
import os
import re
import shutil
import subprocess
import sys

#: O nó do cabo é reconhecido por PROPRIEDADE, nunca pelo texto do
#: ``Description`` — decisão dela: *"o produto é pra outra pessoa também"*. O
#: que identifica é ser uma source ALSA de um dispositivo Sony/DualSense, e quem
#: é dono dessa resposta é ``integrations/fontes_de_captura``. Aqui, fora do
#: pacote, se usa o mesmo critério que ELE usa: o prefixo ``alsa_input.`` mais o
#: nome do produto no ``node.name`` — que vem do USB, não de rótulo editável.
_PREFIXO_ALSA_INPUT = "alsa_input."
_MARCA_NO_NOME = "dualsense"

#: s16le. É o formato que o ``parec`` pede e o que este instrumento decodifica.
_BYTES_POR_AMOSTRA = 2

#: Os aparelhos cujo descritor este instrumento sabe ler, por ``idVendor:idProduct``.
#: O DualSense e o DualSense Edge — os mesmos dois do quirk de áudio desta casa
#: (``/etc/modprobe.d/hefesto-dualsense-storm.conf``).
_APARELHOS_UAC = {
    ("054c", "0ce6"): "DualSense",
    ("054c", "0df2"): "DualSense Edge",
}

#: ``wTerminalType`` → nome do PADRÃO, da «USB Device Class Definition for
#: Terminal Types» 1.0. **Esta tabela é o único texto digitado do
#: ``--descritor``; o valor que se traduz vem do aparelho.** Os dois códigos que
#: significam digital são o ``0x0602`` e o ``0x0605``, e é por eles que a
#: pergunta «é S/PDIF?» se responde LENDO em vez de acreditar no rótulo do host.
_TIPOS_DE_TERMINAL = {
    0x0100: "USB Undefined", 0x0101: "USB Streaming", 0x01FF: "USB vendor specific",
    0x0200: "Input Undefined", 0x0201: "Microphone", 0x0202: "Desktop microphone",
    0x0203: "Personal microphone", 0x0204: "Omni-directional microphone",
    0x0205: "Microphone array", 0x0206: "Processing microphone array",
    0x0300: "Output Undefined", 0x0301: "Speaker", 0x0302: "Headphones",
    0x0303: "Head Mounted Display Audio", 0x0304: "Desktop speaker",
    0x0305: "Room speaker", 0x0306: "Communication speaker",
    0x0307: "Low frequency effects speaker",
    0x0400: "Bi-directional Undefined", 0x0401: "Handset", 0x0402: "Headset",
    0x0403: "Speakerphone, no echo reduction",
    0x0404: "Echo-suppressing speakerphone", 0x0405: "Echo-canceling speakerphone",
    0x0500: "Telephony Undefined", 0x0501: "Phone line", 0x0502: "Telephone",
    0x0503: "Down Line Phone",
    0x0600: "External Undefined", 0x0601: "Analog connector",
    0x0602: "Digital audio interface", 0x0603: "Line connector",
    0x0604: "Legacy audio connector", 0x0605: "S/PDIF interface",
    0x0606: "1394 DA stream", 0x0607: "1394 DV stream soundtrack",
    0x0700: "Embedded Undefined", 0x0703: "CD player", 0x0710: "Radio Receiver",
}

#: Os DOIS códigos que declarariam uma interface digital. Se nenhum aparecer no
#: descritor, a palavra «S/PDIF» que a tela do sistema mostra é do host.
_TIPOS_DIGITAIS = (0x0602, 0x0605)

#: Subtipos de descritor de classe (``bDescriptorType`` 0x24) que interessam
#: numa interface AudioControl de UAC1.
_AC_HEADER, _AC_INPUT, _AC_OUTPUT, _AC_FEATURE = 0x01, 0x02, 0x03, 0x06


def _rodar(argv: list[str], *, entrada: bytes | None = None) -> str:
    """Um comando curto, sem shell, com timeout. Devolve stdout (vazio se falhar)."""
    if shutil.which(argv[0]) is None:
        return ""
    try:
        saida = subprocess.run(  # argv fixo, sem shell
            argv,
            input=entrada,
            capture_output=True,
            timeout=15,
            env={**os.environ, "LC_ALL": "C"},
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return saida.stdout.decode("utf-8", "replace")


def _no_do_cabo() -> str:
    """O nome do nó ALSA de captura do DualSense, ou vazio.

    Só ``alsa_input.*``: o ``.monitor`` do sink também casa a marca no nome, mas
    é o loopback da SAÍDA, não o microfone.
    """
    for linha in _rodar(["pactl", "list", "sources", "short"]).splitlines():
        campos = linha.split("\t")
        if len(campos) < 2:
            continue
        nome = campos[1].strip()
        if nome.startswith(_PREFIXO_ALSA_INPUT) and _MARCA_NO_NOME in nome.lower():
            return nome
    return ""


def _bloco_da_source(nome: str) -> list[str]:
    """As linhas do ``pactl list sources`` que descrevem ESTE nó."""
    bloco: list[str] = []
    dentro = False
    for linha in _rodar(["pactl", "list", "sources"]).splitlines():
        if re.match(r"^\s*Name:\s", linha):
            dentro = linha.split(":", 1)[1].strip() == nome
        if linha.startswith("Source #"):
            dentro = False
        if dentro:
            bloco.append(linha.rstrip())
    return bloco


def _cartao_do_dualsense() -> tuple[str, str]:
    """(nome do card, perfil ATIVO) do DualSense em ``pactl list cards``."""
    card = ativo = ""
    alvo = False
    for linha in _rodar(["pactl", "list", "cards"]).splitlines():
        if re.match(r"^\s*Name:\s", linha):
            nome = linha.split(":", 1)[1].strip()
            alvo = _MARCA_NO_NOME in nome.lower()
            if alvo:
                card = nome
            continue
        if alvo and re.match(r"^\s*Active Profile:\s", linha):
            ativo = linha.split(":", 1)[1].strip()
    return card, ativo


def _indice_alsa() -> str:
    """O índice de placa ALSA do DualSense em ``/proc/asound/cards``, ou vazio."""
    try:
        with open("/proc/asound/cards", encoding="utf-8", errors="replace") as fonte:
            texto = fonte.read()
    except OSError:
        return ""
    for linha in texto.splitlines():
        if _MARCA_NO_NOME in linha.lower():
            achado = re.match(r"\s*(\d+)\s", linha)
            if achado:
                return achado.group(1)
    return ""


def _mixer_de_captura(indice: str) -> list[str]:
    """Os controles de CAPTURA do mixer ALSA daquela placa, com a porcentagem.

    **Este é o estágio de ganho que o produto não sabe que existe.** Lê, nunca
    escreve — mexer no mixer dela sem ela pedir está fora desta janela.
    """
    if not indice:
        return []
    texto = _rodar(["amixer", "-c", indice, "scontents"])
    achados: list[str] = []
    nome = ""
    for linha in texto.splitlines():
        achado = re.match(r"Simple mixer control '([^']+)'", linha)
        if achado:
            nome = achado.group(1)
            continue
        if nome and "Capture" in linha and "%" in linha:
            achados.append(f"{nome}: {linha.strip()}")
    return achados


def _parametros_nativos(indice: str) -> list[str]:
    """Taxa, canais e formato NATIVOS do endpoint USB, pelo ``--dump-hw-params``.

    É a ORIGEM de verdade: o que o aparelho entrega antes de qualquer perfil,
    remix ou reamostragem. O ``arecord`` escreve isso no stderr e sai com erro —
    é o comportamento normal do ``--dump-hw-params``, não uma falha.
    """
    if not indice or shutil.which("arecord") is None:
        return []
    try:
        saida = subprocess.run(  # argv fixo, sem shell
            ["arecord", "-D", f"hw:{indice},0", "--dump-hw-params", "-d", "1"],
            capture_output=True,
            timeout=15,
            env={**os.environ, "LC_ALL": "C"},
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    texto = saida.stderr.decode("utf-8", "replace")
    guardar = ("FORMAT:", "CHANNELS:", "RATE:", "PERIOD_SIZE:", "ACCESS:")
    return [ln.strip() for ln in texto.splitlines() if ln.strip().startswith(guardar)]


def _rms_e_pico(pcm: bytes, canais: int) -> list[tuple[float, int]]:
    """(RMS, pico) de CADA canal, a partir de PCM s16le intercalado."""
    amostras = array.array("h")
    amostras.frombytes(pcm[: len(pcm) - len(pcm) % (_BYTES_POR_AMOSTRA * canais)])
    if sys.byteorder == "big":
        amostras.byteswap()
    saida: list[tuple[float, int]] = []
    for canal in range(canais):
        fatia = amostras[canal::canais]
        if not fatia:
            saida.append((0.0, 0))
            continue
        soma = sum(float(v) * v for v in fatia)
        saida.append((math.sqrt(soma / len(fatia)), max(abs(v) for v in fatia)))
    return saida


# --- O DESCRITOR USB, que responde «é S/PDIF?» sem servidor de som ----------


def _aparelho_uac() -> tuple[str, str, str]:
    """``(pasta em /sys, rótulo, "vid:pid")`` do primeiro DualSense no cabo.

    Percorre ``/sys/bus/usb/devices`` e casa por ``idVendor``/``idProduct``.
    **Não abre o aparelho, não fala com o daemon, não precisa de PipeWire.**
    """
    raiz = "/sys/bus/usb/devices"
    try:
        nomes = sorted(os.listdir(raiz))
    except OSError:
        return "", "", ""
    for nome in nomes:
        pasta = os.path.join(raiz, nome)
        try:
            with open(os.path.join(pasta, "idVendor"), encoding="ascii") as fonte:
                vid = fonte.read().strip().lower()
            with open(os.path.join(pasta, "idProduct"), encoding="ascii") as fonte:
                pid = fonte.read().strip().lower()
        except OSError:
            continue
        rotulo = _APARELHOS_UAC.get((vid, pid))
        if rotulo:
            return pasta, rotulo, f"{vid}:{pid}"
    return "", "", ""


def _descritores_crus(pasta: str) -> bytes:
    """Os bytes de ``<pasta>/descriptors``, ou vazio."""
    try:
        with open(os.path.join(pasta, "descriptors"), "rb") as fonte:
            return fonte.read()
    except OSError:
        return b""


def _ler_uac(bruto: bytes) -> tuple[dict[int, dict], list[str]]:
    """Percorre os descritores e devolve ``(unidades por id, linhas de fluxo)``.

    Caminha a lista TLV (``bLength``, ``bDescriptorType``, …) e só interpreta o
    que está DENTRO de uma interface de classe 0x01 (Audio): ``0x24`` é
    CS_INTERFACE, e o significado do subtipo depende da subclasse da interface
    corrente — AudioControl (0x01) tem terminais e unidades; AudioStreaming
    (0x02) tem o formato e o terminal a que se liga.

    Função PURA: recebe bytes, devolve estrutura. É ela que os testes medem.
    """
    unidades: dict[int, dict] = {}
    fluxo: list[str] = []
    subclasse = 0
    ligado_a = 0
    pos = 0
    while pos + 1 < len(bruto):
        tamanho = bruto[pos]
        tipo = bruto[pos + 1]
        if tamanho < 2 or pos + tamanho > len(bruto):
            break
        corpo = bruto[pos : pos + tamanho]
        if tipo == 0x04 and tamanho >= 9:  # INTERFACE
            subclasse = corpo[6] if corpo[5] == 0x01 else 0
            ligado_a = 0
        elif tipo == 0x24 and tamanho >= 3 and subclasse == 0x01:  # AudioControl
            sub = corpo[2]
            if sub == _AC_INPUT and tamanho >= 12:
                unidades[corpo[3]] = {
                    "tipo": "entrada",
                    "terminal": corpo[4] | (corpo[5] << 8),
                    "fonte": None,
                    "canais": corpo[7],
                    "mapa": corpo[8] | (corpo[9] << 8),
                }
            elif sub == _AC_OUTPUT and tamanho >= 9:
                unidades[corpo[3]] = {
                    "tipo": "saida",
                    "terminal": corpo[4] | (corpo[5] << 8),
                    "fonte": corpo[7],
                    "canais": 0,
                    "mapa": 0,
                }
            elif sub == _AC_FEATURE and tamanho >= 7:
                unidades[corpo[3]] = {
                    "tipo": "ganho",
                    "terminal": None,
                    "fonte": corpo[4],
                    "canais": 0,
                    "mapa": 0,
                    "controles": bytes(corpo[6 : tamanho - 1]),
                }
        elif tipo == 0x24 and tamanho >= 3 and subclasse == 0x02:  # AudioStreaming
            sub = corpo[2]
            if sub == 0x01 and tamanho >= 4:  # AS_GENERAL
                ligado_a = corpo[3]
            elif sub == 0x02 and tamanho >= 11:  # FORMAT_TYPE I
                taxa = corpo[8] | (corpo[9] << 8) | (corpo[10] << 16)
                fluxo.append(
                    f"terminal {ligado_a}: {corpo[4]} canal(is) × "
                    f"{corpo[6]} bits × {taxa} Hz"
                )
        pos += tamanho
    return unidades, fluxo


def _terminal_da_captura(unidades: dict[int, dict]) -> int | None:
    """O ``wTerminalType`` da ENTRADA que alimenta o fluxo que sobe para o host.

    Anda a corrente ao contrário a partir do ``OUTPUT TERMINAL`` de tipo «USB
    Streaming» (0x0101) — que é por onde o host recebe —, seguindo ``bSourceID``
    até chegar a um terminal de entrada. **Não adivinha pelo nome nem pelo
    índice: segue o que o descritor liga.**
    """
    origem: int | None = None
    for unidade in unidades.values():
        if unidade["tipo"] == "saida" and unidade["terminal"] == 0x0101:
            origem = unidade["fonte"]
            break
    vistos: set[int] = set()
    while origem is not None and origem in unidades and origem not in vistos:
        vistos.add(origem)
        unidade = unidades[origem]
        if unidade["tipo"] == "entrada":
            terminal = unidade["terminal"]
            return terminal if isinstance(terminal, int) else None
        origem = unidade["fonte"]
    return None


def _nome_do_terminal(codigo: int) -> str:
    return _TIPOS_DE_TERMINAL.get(codigo, "(fora da tabela do padrão)")


def _descritor() -> int:
    """Responde «o microfone entra por uma porta digital?» LENDO o aparelho."""
    pasta, rotulo, ids = _aparelho_uac()

    print("=" * 78)
    print("  o_caminho_do_mic_no_cabo — o DESCRITOR USB (leitura de /sys)")
    print("=" * 78)
    print(f"  interpretador ..... {sys.executable}")
    print("  porta ............. /sys/bus/usb/devices (nem pactl, nem ALSA)")
    print("  precisa de som? ... NÃO — roda com o PipeWire caído")
    print("=" * 78)

    if not pasta:
        print()
        print("  NÃO HÁ DUALSENSE NO CABO NESTA MÁQUINA.")
        print("  O descritor só existe enquanto o aparelho está plugado.")
        print("-" * 78)
        print("RESUMO: mesa vazia — nada a afirmar sobre o descritor.")
        print("-" * 78)
        return 2

    bruto = _descritores_crus(pasta)
    if not bruto:
        print()
        print(f"  achei {rotulo} em {pasta}, mas não consegui ler `descriptors`.")
        print("-" * 78)
        print("RESUMO: leitura falhou — NÃO é o mesmo que «não é S/PDIF».")
        print("-" * 78)
        return 2

    unidades, fluxo = _ler_uac(bruto)
    print()
    print(f"  aparelho .......... {rotulo}  ({ids})")
    print(f"  em ................ {pasta}")
    print(f"  descritores ....... {len(bruto)} bytes")

    print()
    print("  -- OS TERMINAIS, com o tipo TRADUZIDO pela tabela do padrão UAC ------")
    if not unidades:
        print("   (nenhuma unidade de AudioControl — o aparelho não declara áudio?)")
    for uid in sorted(unidades):
        unidade = unidades[uid]
        if unidade["tipo"] == "ganho":
            controles = unidade.get("controles", b"").hex(" ") or "(vazio)"
            print(
                f"   unidade {uid:2d}  GANHO (Feature Unit)  fonte={unidade['fonte']}"
                f"  bmaControls={controles}"
            )
            continue
        codigo = unidade["terminal"] or 0
        lado = "ENTRADA" if unidade["tipo"] == "entrada" else "SAÍDA  "
        extra = ""
        if unidade["tipo"] == "entrada":
            extra = f"  canais={unidade['canais']}  mapa=0x{unidade['mapa']:04x}"
        else:
            extra = f"  fonte={unidade['fonte']}"
        print(
            f"   unidade {uid:2d}  {lado}  0x{codigo:04x}"
            f"  «{_nome_do_terminal(codigo)}»{extra}"
        )

    if fluxo:
        print()
        print("  -- O QUE CADA FLUXO CARREGA ------------------------------------------")
        for linha in fluxo:
            print(f"   {linha}")

    digitais = sorted(
        {
            unidade["terminal"]
            for unidade in unidades.values()
            if unidade["terminal"] in _TIPOS_DIGITAIS
        }
    )
    captura = _terminal_da_captura(unidades)

    print()
    print("-" * 78)
    if captura is None:
        print("VEREDITO: não achei a corrente de captura no descritor. NÃO conclua")
        print("          nada sobre o microfone a partir desta corrida.")
        print("-" * 78)
        return 2
    print(
        f"captura: terminal 0x{captura:04x} ({_nome_do_terminal(captura)})"
        f" · S/PDIF declarado: {'SIM' if digitais else 'NÃO'}"
    )
    if not digitais:
        print()
        print("Os dois códigos que declarariam digital — 0x0602 («Digital audio")
        print("interface») e 0x0605 («S/PDIF interface») — NÃO aparecem no descritor.")
        print("Toda palavra «S/PDIF» ou «iec958» que a tela do sistema mostrar é")
        print("rótulo do HOST, não do aparelho, e não custa um byte de áudio.")
    print("-" * 78)
    return 0


def _ganho_plano() -> int:
    """IMPRIME o protocolo do par controlado do ganho. **Não mede nada.**

    O passo que este texto descreve ESCREVE no mixer dela, e por isso ele não
    roda aqui: a execução é janela própria, com ela presente, e com um
    ``--restaura`` que devolve o valor **lido** antes de qualquer escrita — o
    valor lido, nunca um valor digitado, que é a armadilha de medir contra a
    própria saída.
    """
    print("=" * 78)
    print("  o_caminho_do_mic_no_cabo — o PLANO do ganho (não mede, não escreve)")
    print("=" * 78)
    print()
    print("  O par controlado: a MESMA frase, a MESMA duração, o MESMO comando,")
    print("  um fator por vez, em três degraus do `Headset Capture Volume`:")
    print()
    print("      +48 dB (o de hoje)   ·   +24 dB   ·   0 dB")
    print()
    print("  Em cada degrau, TRÊS números: RMS da voz · pico · piso ENTRE as frases.")
    print()
    print("  -- A CONTA QUE DECIDE, escrita ANTES de medir ------------------------")
    print("   piso e voz caem os MESMOS dB → o ganho é digital, aplicado depois do")
    print("       conversor. O SNR não muda. A H1 morre inteira, e fica registrado")
    print("       para ninguém remedir.")
    print("   o piso cai MAIS que a voz  → o ganho é analógico e o pré-amp traz")
    print("       ruído próprio. Há cura, e o número é dela.")
    print("   a voz satura em +48 e não em +24 → há recorte hoje, e é audível.")
    print("       Há cura, e é urgente.")
    print()
    print("  -- POR QUE ESTE COMANDO NÃO O EXECUTA --------------------------------")
    print("   Escrever no `Headset Capture Volume` é escrever no SISTEMA dela, não")
    print("   no Hefesto. O produto não tem hoje uma linha de amixer/alsactl em")
    print("   src/, scripts/ nem install.sh. Se esse ganho ganhar dono, o dono é o")
    print("   scripts/doctor.sh — que já é dono da camada 2 e já tem --fix — e ele")
    print("   nasce com DEFAULT escrito e justificado, nunca «deixa como está».")
    print()
    print("  -- A RECOMENDAÇÃO, EM UMA LINHA, PARA ELA ---------------------------")
    print("   NÃO trocar o perfil da placa: o perfil está certo e quem mentia era")
    print("   o nome. O que há a decidir é se o Hefesto passa a LIGAR o")
    print("   `Headset Capture Volume` no próprio UCM — ligar dá o botão a ela e")
    print("   traz uma camada a mais de estado persistido; não ligar mantém os")
    print("   +48 dB fixos, fora do alcance de todos.")
    print("-" * 78)
    print("RESUMO: plano impresso. Nada foi medido e nada foi escrito.")
    print("-" * 78)
    return 0


def _censo() -> int:
    no = _no_do_cabo()
    card, perfil = _cartao_do_dualsense()
    indice = _indice_alsa()

    print("=" * 78)
    print("  o_caminho_do_mic_no_cabo — PASSO 1, o censo (leitura pura)")
    print("=" * 78)
    print(f"  interpretador ..... {sys.executable}")
    print("  porta ............. PulseAudio/ALSA (pactl, amixer, arecord)")
    print("  escreve? .......... NÃO — nem no aparelho, nem no mixer, nem no perfil")
    print("=" * 78)

    if not (no or card or indice):
        print()
        print("  NÃO HÁ DUALSENSE NO CABO NESTA MÁQUINA.")
        print("  O passo 0 é dela, e nada abaixo se mede sem ele.")
        print("-" * 78)
        print("RESUMO: mesa vazia — nenhuma afirmação sobre o caminho do cabo é")
        print("        possível a partir desta corrida.")
        print("-" * 78)
        return 2

    print()
    print(f"  placa ............. {card or '(não achei em pactl list cards)'}")
    print(f"  perfil ATIVO ...... {perfil or '(não sei)'}")
    print(f"  índice ALSA ....... {indice or '(não achei em /proc/asound/cards)'}")
    print(f"  nó de captura ..... {no or '(não achei em pactl list sources short)'}")

    print()
    print("  -- H2: O FORMATO DA ORIGEM (o que o `parec` recebe) ------------------")
    interessa = ("Sample Specification:", "Channel Map:", "Base Volume:",
                 "Volume:", "Latency:", "Active Port:", "Mute:")
    linhas = [ln for ln in _bloco_da_source(no) if ln.strip().startswith(interessa)]
    for linha in linhas or ["    (nó sem bloco no `pactl list sources`)"]:
        print(f"   {linha.strip()}")
    print()
    print("   O DESTINO é s16le 1ch 48000Hz — o `module-pipe-source` do canal.")
    print("   Toda diferença acima vira remix ou reamostragem no pipewire-pulse,")
    print("   e HOJE nenhuma régua desta casa a enxerga.")

    print()
    print("  -- H1: O GANHO DE HARDWARE (o estágio que o produto não conhece) -----")
    controles = _mixer_de_captura(indice)
    for linha in controles or ["    (nenhum controle de captura no mixer desta placa)"]:
        print(f"   {linha}")
    print()
    print("   O produto NUNCA escreve aqui: `amixer`/`alsactl`/`snd_ctl` não")
    print("   aparecem em src/, scripts/ nem install.sh. E a `mic.volume` dela")
    print("   trava em 0–100% — ela ATENUA, nunca amplifica, e não fala com este")
    print("   elemento.")
    print()
    print("   O 31% de 25/07/2026 (MIC-USB-01) CAIU. Lido em repouso em 17/09 e")
    print("   de novo em 20/09/2026: 100% / +48,00 dB — o TOPO da faixa. A H1 não")
    print("   morreu, virou do avesso: não é que falte ganho, é que SOBRA ganho e")
    print("   ele não tem dono. Se é analógico ou digital, só o par controlado do")
    print("   `--ganho-plano` separa, e esse passo é com ela.")

    print()
    print("  -- A ORIGEM NATIVA (antes do perfil) ---------------------------------")
    nativos = _parametros_nativos(indice)
    for linha in nativos or ["    (não deu para ler os parâmetros nativos)"]:
        print(f"   {linha}")

    print()
    print("-" * 78)
    print("RESUMO: censo feito. O passo 2 (`--canais`) decide a H2 sozinho; o")
    print("        passo 3 mede a H1 mas o VALOR final é dela; o passo 5 é")
    print("        inteiramente dela, por decisão escrita desta casa.")
    print("-" * 78)
    return 0


def _canais(segundos: int) -> int:
    """PASSO 2 — o remix, decidido por número: RMS e pico de CADA canal."""
    no = _no_do_cabo()
    if not no:
        print("NÃO HÁ nó de captura de DualSense. O passo 0 é dela.")
        return 2
    if shutil.which("parec") is None:
        print("`parec` não está nesta máquina — sem ele não há como ler a origem.")
        return 2

    canais = 2
    print(f"gravando {segundos} s de {no} em {canais} canais, sem converter nada…")
    argv = [
        "parec", f"--device={no}", "--raw", "--format=s16le",
        f"--channels={canais}", "--rate=48000", "--latency-msec=40",
        "--client-name=hefesto-ensaio-mic-no-cabo",
    ]
    try:
        proc = subprocess.run(  # argv fixo, sem shell
            argv, capture_output=True, timeout=segundos + 5, check=False,
            env={**os.environ, "LC_ALL": "C"},
        )
        pcm = proc.stdout
    except subprocess.TimeoutExpired as expirou:
        pcm = expirou.stdout or b""
    except (OSError, subprocess.SubprocessError):
        pcm = b""

    if not pcm:
        print("nada saiu do nó. Confira o mudo do firmware (camada 3) e o mute da rota.")
        return 2

    medidas = _rms_e_pico(pcm, canais)
    print()
    for i, (rms, pico) in enumerate(medidas):
        print(f"  canal {i}: RMS {rms:9.1f}   pico {pico:6d}")
    print()
    vivos = [i for i, (rms, _) in enumerate(medidas) if rms > 0]
    if len(vivos) < canais:
        mortos = [i for i in range(canais) if i not in vivos]
        print("-" * 78)
        print(f"RESUMO: H2 CONFIRMADA — o(s) canal(is) {mortos} não traz(em) sinal, e o")
        print("        remix 2→1 que o pipewire-pulse faz hoje custa ~6 dB de voz.")
        print("-" * 78)
        return 0
    razao = max(r for r, _ in medidas) / max(1e-9, min(r for r, _ in medidas))
    print("-" * 78)
    if razao > 2.0:
        print(f"RESUMO: H2 PROVÁVEL — os dois canais diferem por {razao:.1f}x; um deles")
        print("        é muito mais fraco, e o remix mistura os dois em partes iguais.")
    else:
        print(f"RESUMO: H2 FRACA — os dois canais estão a {razao:.2f}x um do outro; o")
        print("        remix 2→1 é aproximadamente uma média de sinais equivalentes.")
    print("-" * 78)
    return 0


def main() -> int:
    partidor = argparse.ArgumentParser(description=__doc__ and __doc__.splitlines()[0])
    partidor.add_argument("--censo", action="store_true", help="PASSO 1 (padrão)")
    partidor.add_argument("--canais", action="store_true", help="PASSO 2 — decide a H2")
    partidor.add_argument(
        "--descritor",
        action="store_true",
        help="o descritor USB: responde «é S/PDIF?» sem servidor de som",
    )
    partidor.add_argument(
        "--ganho-plano",
        action="store_true",
        help="imprime o protocolo do par controlado do ganho — NÃO mede, NÃO escreve",
    )
    partidor.add_argument("--segundos", type=int, default=10)
    args = partidor.parse_args()
    if args.descritor:
        return _descritor()
    if args.ganho_plano:
        return _ganho_plano()
    if args.canais:
        return _canais(max(1, args.segundos))
    return _censo()


if __name__ == "__main__":
    raise SystemExit(main())
