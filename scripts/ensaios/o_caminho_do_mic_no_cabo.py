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

**H1 — o ganho de hardware que o produto não sabe que existe.** O elemento ALSA
de captura do DualSense no cabo chama-se literalmente ``Headset`` e foi medido a
**31%** em 25/07/2026 (MIC-USB-01). E
``grep -rn "amixer|alsactl|snd_ctl|alsaaudio" src/ scripts/ install.sh``
devolve **VAZIO**: o produto nunca tocou o mixer ALSA. Um sinal que nasce a um
terço e é amplificado depois é exatamente um sinal *"não limpo"* — e a
``mic.volume`` dela não pode compensar, porque ``definir_volume_da_captura``
trava em 0–100% (``integrations/audio_control.py``) e não amplifica.

**H2 — o remix que ninguém escolheu.** O ``parec`` do alimentador é lançado com
``--rate``/``--channels`` tirados do **DESTINO** (o ``module-pipe-source``, que é
mono 48 kHz), nunca da **ORIGEM**. Se o nó do cabo for estéreo, o pipewire-pulse
faz um remix 2→1 que ninguém pediu. E a casa já mediu, do lado da SAÍDA, que o
DualSense por USB põe coisas diferentes em canais diferentes: se a ENTRADA
repetir o padrão — o mono num canal só do par —, o remix custa 6 dB e traz o
ruído do canal morto junto. **Nenhuma régua desta casa lê o formato da ORIGEM**,
então isso hoje é invisível a todos os portões.

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

USO
====
    scripts/ensaios/o_caminho_do_mic_no_cabo.py --censo
    scripts/ensaios/o_caminho_do_mic_no_cabo.py --canais --segundos 10

Sem argumento, faz o censo.
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
    print("   trava em 0–100%: o deslizante da tela não recupera o que se perdeu")
    print("   antes dele.")

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
    partidor.add_argument("--segundos", type=int, default=10)
    args = partidor.parse_args()
    if args.canais:
        return _canais(max(1, args.segundos))
    return _censo()


if __name__ == "__main__":
    raise SystemExit(main())
