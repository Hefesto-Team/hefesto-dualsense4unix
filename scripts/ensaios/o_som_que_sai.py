#!/usr/bin/env python3
"""o_som_que_sai.py — o MESMO PCM pelos DOIS arranjos, e o nó que nasce.

O QUE ELE É, E O QUE ELE NÃO É
-------------------------------
Ele é o instrumento da SOM-QUE-SAI-01: monta, mede e mostra. **Ele não conclui
nada sobre som ter saído de aparelho nenhum**, e o mapa proíbe que qualquer
coisa nesta árvore conclua isso antes do ensaio de bancada
(``audio.saida_dedicada.payload_do_degrau@dualsense``.radio_ressalva):

    *"NÃO ESCREVER, EM LUGAR NENHUM, que 'descobrimos o áudio por Bluetooth'
    ou que a ponte funciona. Não funciona, e não há ponte: há um canal que
    responde. FALÁCIA DO CANAL QUE RESPONDE."*

O honesto, até a orelha dela decidir: **o canal responde, e o conteúdo vai
pelos DOIS arranjos candidatos.**

AS TRÊS PERGUNTAS QUE ELE RESPONDE
-----------------------------------
``--motor``   (padrão)  a escada pela TABELA, o encoder fechando o quadro de
                        200 bytes, e os dois arranjos montados do MESMO PCM.
                        Não toca no servidor de som nem no aparelho.
``--sink``              carrega o ``module-null-sink`` de um controle
                        SINTÉTICO, LÊ do servidor o que chegou ao nó
                        (``priority.session``, estado), confere que a saída
                        PADRÃO do sistema não mudou, e descarrega. É a medição
                        que o mapa listava como NÃO MEDIDA: *"module-null-sink
                        carrega nesta máquina"*.
``--escrever``          escreve no aparelho. **É o ensaio 1 da
                        MESA-DE-QUATRO-01**, não deste script sozinho: exige
                        bancada reservada, ``--exigir-mac`` conferido, o
                        aparelho no RÁDIO, e a orelha dela do outro lado.

A ARMADILHA QUE ESTE ENSAIO TEM DE RESPEITAR
---------------------------------------------
``os.write()`` num hidraw devolve sucesso quando o **KERNEL** aceita a entrega;
ele NÃO espera veredito do firmware. Em 15/08 o kernel aceitou até um pacote de
tamanho errado que era o controle negativo. **O retorno desta chamada não é a
medição.** Quem mede é a orelha dela.

E A SEGUNDA, que é do outro lado: um report com o tamanho errado põe o CRC-32
no lugar errado e o firmware **descarta calado**. O sintoma de *"errei o
degrau"* é indistinguível do sintoma de *"o protocolo está errado"*. Por isso o
tamanho vem da TABELA (:data:`TAMANHO_DO_DEGRAU`) e nunca de aritmética.

O QUE ELE RECUSA POR CONSTRUÇÃO
--------------------------------
* escrever sem ``--exigir-mac`` conferido — para não escrever no controle
  errado;
* escrever em aparelho no CABO: a escada só existe no rádio, e escrever ali
  seria medir outra coisa;
* qualquer report fora de ``0x31``-``0x39``: a família ``0xF0``-``0xF7`` é o
  canal de atualização de firmware, e ela está BLOQUEADA por decisão dela de
  15/08;
* abrir janela. Ele não tem tela; a tela dela é uma só.

A PROCEDÊNCIA, DECLARADA
-------------------------
Como todo instrumento desta pasta, ele imprime de qual ARQUIVO veio cada
biblioteca antes da primeira linha de medição. *"Medir contra a biblioteca
errada produz alarme convincente e falso"* já aconteceu três vezes aqui.
"""

from __future__ import annotations

import argparse
import itertools
import math
import os
import struct
import subprocess
import sys
from collections.abc import Callable

_AQUI = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_AQUI)
_RAIZ = os.path.dirname(_SCRIPTS)
_SRC = os.path.join(_RAIZ, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from hefesto_dualsense4unix.integrations import alto_falante_bt as af

#: MAC SINTÉTICO da casa, e ele nunca sai deste arquivo. Faixas permitidas:
#: ``02:fe:00``, ``aa:bb:cc``, ``e8:47:3a``, sem sequência simples. Nada de MAC
#: real em arquivo versionado — há DOIS portões, e um deles pega por FORMA.
MAC_SINTETICO = "aa:bb:cc:00:00:01"

#: O tom do PCM de referência: 440 Hz, meia escala. Um seno de verdade, e não
#: silêncio — silêncio em CBR também fecha 200 bytes, e mediria o bitrate sem
#: medir o codificador trabalhando.
TOM_HZ = 440.0
AMPLITUDE = 12000


def pcm_de_referencia(quadros: int = 2) -> list[bytes]:
    """Quadros de PCM ``s16le`` estéreo de 10 ms — o MESMO para os dois arranjos.

    Estéreo porque a rota do firmware é POR CANAL (``OUTPUT_PATH_SEL`` = 2:
    L → fone, R → alto-falante). Com um nó mono esse caso é inexprimível.
    """
    saida: list[bytes] = []
    fase = 0
    for _ in range(quadros):
        amostras: list[int] = []
        for _i in range(af.AMOSTRAS_POR_QUADRO):
            valor = int(AMPLITUDE * math.sin(2 * math.pi * TOM_HZ * fase / af.TAXA_DO_ENCODER))
            amostras.extend((valor, valor))
            fase += 1
        saida.append(struct.pack(f"<{len(amostras)}h", *amostras))
    return saida


#: O TIMBRE do ensaio de bancada, e ele é escolhido para o RELATO DELA, não
#: para o osciloscópio: 1300 Hz PULSADO a 2 Hz — o *"bep bep bep"* que ela já
#: descreveu por três vezes em ensaio cego (`sfx-cabo-com-posse`,
#: `sfx-canal1-e-o-alto-falante`, `som-no-radio-observado-não-replicado`).
#:
#: **POR QUE PULSADO, E NÃO O TOM CONTÍNUO DE 440 Hz** que este arquivo já
#: gera para medir o encoder: um tom contínuo tem UM relato possível ("ouvi") e
#: nenhuma forma de distinguir *o nosso som* de *qualquer outra coisa que a
#: máquina esteja tocando*. O pulsado carrega a resposta dentro do relato dela
#: — e é exatamente o timbre da observação em aberto, o que faz deste ensaio,
#: se ele um dia soar, a réplica daquela noite.
BANCADA_HZ = 1300.0
BANCADA_PULSOS_HZ = 2.0


def pcm_pulsado() -> Callable[[int], bytes]:
    """Uma fonte de PCM infinita com o timbre da bancada. `s16le` estéreo 48k.

    Fonte SINTÉTICA de propósito: ela não passa pelo servidor de som, não
    depende de nó publicado e não pode ser confundida com som que já estava
    tocando na máquina dela. O caminho pelo monitor do nó
    (:func:`alto_falante_bt.argv_do_gravador`) é o de REGIME; para decidir o
    arranjo, o que se quer é o menor número de coisas entre o timbre e o fio.
    """
    fase = itertools.count()

    def _ler(quantos: int) -> bytes:
        amostras: list[int] = []
        for _ in range(quantos // 4):
            f = next(fase)
            t = f / af.TAXA_DO_ENCODER
            porta = 1.0 if math.sin(2 * math.pi * BANCADA_PULSOS_HZ * t) >= 0 else 0.0
            valor = int(AMPLITUDE * porta * math.sin(2 * math.pi * BANCADA_HZ * t))
            amostras.extend((valor, valor))
        return struct.pack(f"<{len(amostras)}h", *amostras)

    return _ler


def _exigir_bancada() -> tuple[bool, str]:
    """`scripts/bancada.sh exigir` — rc≠0 é ESPERAR, nunca contornar."""
    proc = subprocess.run(
        ["bash", os.path.join(_RAIZ, "scripts", "bancada.sh"), "exigir"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def cabecalho() -> None:
    """De onde veio cada biblioteca — o CAMINHO, não o nome."""
    import ctypes.util

    print("o_som_que_sai — a procedência primeiro")
    print(f"  python        {sys.executable}")
    print(f"  hefesto       {af.__file__}")
    print(f"  libopus       {ctypes.util.find_library('opus')} ({af.versao_libopus()})")
    print(f"  árvore        {_RAIZ}")
    print()


def medir_motor() -> int:
    """A escada, o encoder e os dois arranjos. Não toca em nada de fora."""
    print("A ESCADA — pela TABELA, e a aritmética ao lado para se ver o buraco")
    print("  degrau  tabela  orçamento  78+64*(id-0x31)")
    ruim = 0
    for degrau in sorted(af.TAMANHO_DO_DEGRAU):
        tabela = af.TAMANHO_DO_DEGRAU[degrau]
        aritmetica = 78 + 64 * (degrau - 0x31)
        marca = "  <-- DIVERGE" if aritmetica != tabela else ""
        if aritmetica != tabela:
            ruim += 1
        print(
            f"  0x{degrau:02x}    {tabela:4d}    {af.ORCAMENTO_DO_DEGRAU[degrau]:4d}"
            f"       {aritmetica:4d}{marca}"
        )
    print(
        f"  a escada tem {ruim} passo(s) que a aritmética erra — é por isso que a"
        " regra é uma tabela\n"
    )

    print("A ESCOLHA DO DEGRAU — o MENOR cujo orçamento comporta o payload")
    for n in (24, 88, 89, 152, 493, 494):
        degrau = af.degrau_para_payload(n)
        print(f"  {n:4d} B -> {('0x%02x' % degrau) if degrau else 'NÃO CABE em degrau nenhum'}")
    print()

    print("O ENCODER — CBR 160 kbps, 10 ms, estéreo")
    try:
        codificador = af.CodificadorOpus()
    except Exception as exc:
        print(f"  SEM ENCODER: {exc}")
        return 1
    with codificador:
        quadros_pcm = pcm_de_referencia(2)
        opus = [codificador.codificar(p) for p in quadros_pcm]
        if any(q is None for q in opus):
            print("  a libopus recusou o quadro — nada a montar")
            return 1
        tamanhos = [len(q or b"") for q in opus]
        print(f"  PCM por quadro     {len(quadros_pcm[0])} B (480 amostras x 2 canais x 2 B)")
        print(f"  Opus por quadro    {tamanhos}")
        print(f"  o bloco quer       {af.BYTES_POR_QUADRO_OPUS} B — as duas fontes declaram len 200")
        fecha = all(t == af.BYTES_POR_QUADRO_OPUS for t in tamanhos)
        print(f"  fecha?             {'SIM' if fecha else 'NÃO'}")
        curto = codificador.codificar(b"\x00" * 10)
        print(f"  PCM de tamanho errado é RECUSADO: {curto!r}")
        print()

        print("OS DOIS ARRANJOS — o MESMO PCM, dois corpos, e nenhum é escolhido")
        pacotes = af.montar_pelos_dois_arranjos([q or b"" for q in opus])
        for nome, pkt in pacotes.items():
            arranjo = af.ARRANJO_POR_NOME[nome]
            print(f"  [{nome}] {arranjo.fonte}")
            print(f"    procedência   {arranjo.de_onde_sei}")
            print(f"    tamanho       {len(pkt)} B (id 0x{pkt[0]:02x})")
            print(
                f"    AudioControl  tag 0x{pkt[arranjo.pos_tag_controle]:02x} em "
                f"[{arranjo.pos_tag_controle}], len {pkt[arranjo.pos_tag_controle + 1]}"
            )
            print(
                f"    áudio         tag 0x{pkt[arranjo.pos_tag_audio]:02x} em "
                f"[{arranjo.pos_tag_audio}], {arranjo.quadros_de_audio} x "
                f"{arranjo.len_audio} B em [{arranjo.pos_audio}.."
                f"{arranjo.pos_audio + arranjo.bytes_de_audio - 1}]"
            )
            print(
                f"    háptico       tag 0x{pkt[arranjo.pos_tag_haptico]:02x} em "
                f"[{arranjo.pos_tag_haptico}]"
            )
            print(f"    CRC-32        {pkt[-4:].hex()} em [{len(pkt) - 4}..{len(pkt) - 1}]")
        iguais = len(set(pacotes.values())) == 1
        print(f"  os dois corpos são iguais? {'SIM' if iguais else 'NÃO — e é o ponto'}")
        print(
            "  quem escolhe é a orelha dela no ensaio 1 da MESA-DE-QUATRO-01."
            " Este script não escolhe.\n"
        )
    return 0 if fecha and not iguais else 1


def medir_sink() -> int:
    """Carrega o nó, LÊ do servidor o que chegou nele, e descarrega.

    **A régua lê o NÓ, não o argv.** A lição é da metade de entrada, paga em
    06/09/2026: a régua que vigiava a prioridade da source afirmava
    ``"priority.session=1500" in props[0]`` — a string ESTÁ no argv, dentro do
    pedaço que o servidor descarta, e o número nunca chegava ao nó. Aqui se
    pergunta ao servidor.
    """
    diagnostico = af.diagnosticar(uniqs=[MAC_SINTETICO])
    print("O DIAGNÓSTICO — o que impede o nó de subir")
    print(f"  pactl          {diagnostico.pactl}")
    print(f"  null-sink      {diagnostico.null_sink}")
    print(f"  loopback       {diagnostico.loopback}")
    print(f"  libopus        {diagnostico.libopus}")
    for falta in diagnostico.impedimentos:
        print(f"  IMPEDIMENTO: {falta}")
    if not diagnostico.pactl or not diagnostico.null_sink:
        print("  sem servidor de som não há o que medir")
        return 1
    print()

    padrao_antes = (af.rodar_pactl(["pactl", "get-default-sink"]) or "").strip()
    no = af.SinkVirtualPipeWire(uniq=MAC_SINTETICO)
    print(f"O NÓ — nome derivado do controle, nunca do transporte: {no.nome}")
    if not no.iniciar():
        print("  não subiu")
        return 1
    try:
        bruto = af.rodar_pactl(["pactl", "list", "sinks"]) or ""
        bloco = _bloco_do_sink(bruto, no.nome)
        prioridade = _propriedade(bloco, "priority.session")
        descricao = _propriedade(bloco, "device.description")
        print(f"  module id            {no.module_id}")
        print(f"  estado (do servidor) {no.estado()}")
        print(f"  monitor              {no.monitor()}")
        print(f"  priority.session     {prioridade}  (pedimos {af.PRIORIDADE_SESSAO_DO_SOM})")
        print(f"  device.description   {descricao}")
        padrao_agora = (af.rodar_pactl(["pactl", "get-default-sink"]) or "").strip()
        print(f"  saída padrão antes   {padrao_antes}")
        print(f"  saída padrão agora   {padrao_agora}")
        virou_padrao = padrao_agora == no.nome
        print(f"  virou a saída padrão? {'SIM — DEFEITO' if virou_padrao else 'não'}")
        chegou = str(prioridade) == str(af.PRIORIDADE_SESSAO_DO_SOM)
        print(f"  a prioridade CHEGOU ao nó? {'sim' if chegou else 'NÃO — DEFEITO'}")
    finally:
        no.parar()
    depois = af.rodar_pactl(["pactl", "list", "sinks", "short"]) or ""
    sumiu = no.nome not in depois
    padrao_final = (af.rodar_pactl(["pactl", "get-default-sink"]) or "").strip()
    print(f"  o nó saiu ao descarregar? {'sim' if sumiu else 'NÃO — sobrou lixo'}")
    print(f"  saída padrão no fim   {padrao_final}")
    ok = chegou and not virou_padrao and sumiu and padrao_final == padrao_antes
    print(f"\n  {'MEDIDO' if ok else 'REPROVOU'}")
    return 0 if ok else 1


def _bloco_do_sink(saida: str, nome: str) -> str:
    """O trecho de ``pactl list sinks`` que descreve ESTE nó."""
    blocos = saida.split("Sink #")
    for bloco in blocos:
        for linha in bloco.splitlines():
            if linha.strip().startswith("Name:") and linha.split(":", 1)[1].strip() == nome:
                return bloco
    return ""


def _propriedade(bloco: str, chave: str) -> str:
    for linha in bloco.splitlines():
        crua = linha.strip()
        if crua.startswith(f"{chave} ="):
            return crua.split("=", 1)[1].strip().strip('"')
    return "(não veio)"


#: Teto do ensaio, em segundos. **É uma trava, não um padrão**: ela está na
#: bancada com quatro aparelhos e um som que não para é um som que atrapalha o
#: ensaio seguinte. Quinze segundos é mais que o dobro dos ~6 s que ela ouviu
#: na observação em aberto, que é o comprimento que este ensaio quer replicar.
TETO_DE_SEGUNDOS = 15.0

#: Quanto o ensaio toca por omissão. Curto de propósito: o relato dela sobre
#: 4 s de um pulsado é tão bom quanto sobre 40, e o preço de errar é menor.
SEGUNDOS_PADRAO = 4.0


def _linha_do_common(common: bytes | None) -> str:
    """A linha que DIZ o que vai em [3..49] — ou que ali não vai nada.

    Ela existe porque o defeito de 08/09/2026 era invisível na saída: o corpo
    saía com 47 zeros e o ensaio imprimia exatamente o mesmo texto que
    imprimiria com o envelope cheio. Um instrumento que não mostra a variável
    que ele está variando não é instrumento.
    """
    from hefesto_dualsense4unix.core import ds_output_report as rep

    if common is None:
        return (
            "  common      NENHUM — este arranjo põe a tag do AudioControl no "
            "byte [2]\n"
        )
    rota = (common[rep.COMMON_AUDIO_PATH] & rep.OUTPUT_PATH_SEL_MASK) >> (
        rep.OUTPUT_PATH_SEL_SHIFT
    )
    return (
        f"  common      47 B em [3..49] — rota {rota}, volume "
        f"{common[rep.COMMON_SPEAKER_VOLUME]}, pré-amp "
        f"{common[rep.COMMON_AUDIO_CONTROL2] & rep.SP_PREAMP_GAIN_MASK}\n"
    )


def escrever_no_aparelho(argumentos: argparse.Namespace) -> int:
    """A porta do ensaio de bancada — e ela recusa muito mais do que aceita.

    **Este caminho é o ensaio 1 da MESA-DE-QUATRO-01**, não deste script
    sozinho. Até 07/09/2026 ele parava ANTES de escrever, com rc=3, e a razão
    estava escrita: *"ele existe aqui para que o instrumento esteja pronto
    quando a bancada e a orelha dela estiverem"*. As duas chegaram — ela está
    na bancada com os quatro DualSense —, e o que faltava do nosso lado era o
    laço entre o encoder e o fio, que agora existe
    (:class:`alto_falante_bt.BombaDeSomPeloRadio`).

    **O QUE NÃO MUDOU, E É O PONTO:** ele continua parando em rc=3 sem
    ``--eu-estou-ouvindo``. O ensaio não é *escrever*; o ensaio é *escrever com
    a orelha dela do outro lado*, e um instrumento que escreve sem isso mede o
    kernel aceitando uma entrega — que não é medição nenhuma. As seis recusas,
    na ordem em que caem:

    1. sem ``--exigir-mac`` conferido — para não escrever no controle errado;
    2. endereço que não está na lista;
    3. aparelho no CABO (a escada só existe no rádio);
    4. arranjo não escolhido (as duas fontes divergem, e a escolha é dela);
    5. degrau fora da escada ``0x31``-``0x39``;
    6. **sem a declaração de que ela está ouvindo**, e sem a bancada reservada.

    E O RETORNO DO ``os.write()`` CONTINUA NÃO SENDO A MEDIÇÃO. O kernel aceita
    a entrega; o firmware descarta calado. Quem mede é a orelha dela, e o
    veredito vai para ``docs/data/ensaios.csv`` com o relato dela, nunca com o
    número deste script.
    """
    from hefesto_dualsense4unix.daemon.subsystems.alto_falante import controles_na_lista

    if not argumentos.exigir_mac:
        print("RECUSADO: --escrever exige --exigir-mac com o endereço conferido.")
        return 2
    alvo = af.so_hex(argumentos.exigir_mac)
    achados = [c for c in controles_na_lista() if af.so_hex(c.uniq) == alvo]
    if not achados:
        print(f"RECUSADO: nenhum controle com esse endereço na lista ({argumentos.exigir_mac}).")
        return 2
    controle = achados[0]
    if controle.transporte != "rádio":
        print(
            f"RECUSADO: {controle.caminho} está no CABO. A escada de output só existe "
            "no rádio; escrever aqui mediria outra coisa."
        )
        return 2
    arranjo = af.ARRANJO_POR_NOME.get(argumentos.arranjo or "")
    if arranjo is None:
        print(f"RECUSADO: escolha o arranjo entre {sorted(af.ARRANJO_POR_NOME)}.")
        return 2
    if arranjo.degrau not in af.TAMANHO_DO_DEGRAU:
        print("RECUSADO: degrau fora da escada 0x31-0x39.")
        return 2
    segundos = min(max(0.0, float(argumentos.segundos)), TETO_DE_SEGUNDOS)
    # O ENVELOPE DE [3..49], e ele só existe para o corpo que o PRESERVA.
    #
    # DEFEITO MEDIDO EM 08/09/2026: o `--arranjo common-preservado` ia ao fio
    # com 47 ZEROS em [3..49] — a bomba chamava `arranjo.montar` sem `common`.
    # Um `common` zerado tem os bits de validação apagados, então ele não pede
    # rota, não pede volume e não pede pré-amp; e o mapa diz que por rádio o
    # kernel NUNCA escreve os três. A passada teria custado a orelha dela para
    # medir um corpo que não pedia nada.
    #
    # Os dois arranjos externos põem a tag do AudioControl no byte [2] e não
    # têm onde guardar um `common` — passá-lo a eles seria inventar campo.
    common = af.common_de_audio() if arranjo.common_preservado else None
    linha_do_common = _linha_do_common(common)
    if not argumentos.eu_estou_ouvindo:
        print(
            "PARADO ANTES DE ESCREVER, e de propósito.\n"
            f"  alvo        {controle.caminho} ({controle.transporte})\n"
            f"  arranjo     {arranjo.nome} — {arranjo.fonte}\n"
            f"  degrau      0x{arranjo.degrau:02x} ({arranjo.tamanho} B)\n"
            f"{linha_do_common}"
            "  A escrita é o ensaio 1 da MESA-DE-QUATRO-01: ela precisa da bancada\n"
            "  reservada (scripts/bancada.sh exigir) e da orelha dela do outro lado.\n"
            "  Acrescente --eu-estou-ouvindo quando as duas coisas forem verdade.\n"
            "  O retorno do os.write() NÃO é a medição — o kernel aceita entrega que\n"
            "  o firmware descarta calado."
        )
        return 3
    reservada, recado = _exigir_bancada()
    if recado:
        print(f"  bancada ..... {recado}")
    if not reservada:
        print("RECUSADO: a bancada não está reservada. Esperar é a resposta.")
        return 2

    # O QUE VAI SAIR, DITO ANTES — regra da casa para qualquer som no aparelho
    # dela. Ela está na bancada; um timbre que aparece sem aviso estraga o
    # ensaio dela tanto quanto estragaria o nosso.
    print(
        "\nO QUE VAI SAIR, E POR QUANTO TEMPO (leia antes de confirmar)\n"
        f"  alvo        {controle.caminho} ({controle.transporte})\n"
        f"  timbre      {BANCADA_HZ:.0f} Hz PULSADO a {BANCADA_PULSOS_HZ:.0f} Hz "
        '— o "bep bep bep"\n'
        f"  duração     {segundos:.1f} s\n"
        f"  arranjo     {arranjo.nome} — {arranjo.fonte}\n"
        f"  degrau      0x{arranjo.degrau:02x} ({arranjo.tamanho} B)\n"
        f"{linha_do_common}"
        f"  tag do bloco 0x{argumentos.tag:02x}"
        f"  ({'alto-falante interno' if argumentos.tag == af.BLOCO_SPEAKER else 'fone'})\n"
    )

    from hefesto_dualsense4unix.integrations.dualsense_bt_audio import abrir_hidraw_rw

    try:
        fd = abrir_hidraw_rw(controle.caminho)
    except OSError as erro:
        print(f"RECUSADO: não deu para abrir {controle.caminho} — {erro}")
        return 2
    try:
        # O RITMO É OBRIGATÓRIO AQUI, e a razão está em `af.fonte_com_ritmo`:
        # o timbre é sintético e não bloqueia, então sem ele a bomba escreveria
        # 2.660 reports/s num degrau que pede 50/s — 53 vezes o necessário, num
        # rádio que carrega os outros três controles dela. Isso não é ensaio, é
        # inundação, e ela mediria a fila do kernel.
        molde = af.BombaDeSomPeloRadio(
            arranjo=arranjo, fonte=pcm_pulsado(), common=common
        )
        bomba = af.BombaDeSomPeloRadio(
            arranjo=arranjo,
            fonte=af.fonte_com_ritmo(
                pcm_pulsado(), ms_por_report=molde.ms_por_report
            ),
            escritor=af.escritor_de_hidraw(fd),
            tag_audio=argumentos.tag,
            seco=False,
            common=common,
        )
        print(f"  PCM por report {bomba.bytes_de_pcm_por_report} B / {bomba.ms_por_report} ms")
        print(f"  cadência       {1000 / bomba.ms_por_report:.0f} reports/s")
        contagem = bomba.rodar(segundos=segundos)
    finally:
        os.close(fd)

    print("\nO QUE A BOMBA CONTOU")
    for linha in contagem.linhas():
        print(linha)
    print(
        "\nO VEREDITO NÃO ESTÁ AQUI.\n"
        "  Nada acima é medição de som. O que este ensaio produziu foi um canal\n"
        "  exercitado com um conteúdo candidato — e o mapa proíbe, com todas as\n"
        "  letras, concluir daí que a ponte funciona (FALÁCIA DO CANAL QUE\n"
        "  RESPONDE). O veredito é UMA frase dela, e ela vai para\n"
        "  docs/data/ensaios.csv com o relato dela, não com estes números.\n"
        "  Se ela não ouviu nada: rode de novo com o OUTRO arranjo antes de\n"
        "  concluir qualquer coisa — os dois são candidatos, e medir um e\n"
        "  concluir sobre o outro é o erro que montar os dois existe para matar."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--motor", action="store_true", help="a escada, o encoder, os arranjos")
    analisador.add_argument("--sink", action="store_true", help="carrega e LÊ o nó no PipeWire")
    analisador.add_argument("--escrever", action="store_true", help="a porta do ensaio de bancada")
    analisador.add_argument("--exigir-mac", default="", help="endereço conferido do alvo")
    analisador.add_argument(
        "--arranjo", default="",
        # O TERCEIRO É A METADE *COM* DO PAR COM/SEM: `common-preservado`
        # mantém o `[2] = 0x10` e o `common` em [3..49], que é o único
        # envelope que esta bancada mediu o firmware aceitar por rádio. As
        # seis passadas de 07/09 variaram a TAG e o ARRANJO e NÃO variaram
        # este byte — os dois candidatos externos escrevem 0x91 nele.
        help="ds5dongle | senshi | common-preservado")
    analisador.add_argument("--eu-estou-ouvindo", action="store_true",
                            help="a orelha dela está do outro lado — sem isto, rc=3")
    analisador.add_argument("--segundos", type=float, default=SEGUNDOS_PADRAO,
                            help=f"duração do timbre (teto {TETO_DE_SEGUNDOS:.0f}s)")
    analisador.add_argument("--tag", type=lambda s: int(s, 0), default=af.BLOCO_SPEAKER,
                            help="tag do bloco de áudio: 0x13 alto-falante, 0x16 fone")
    argumentos = analisador.parse_args(argv)
    cabecalho()
    if argumentos.escrever:
        return escrever_no_aparelho(argumentos)
    codigo = 0
    if argumentos.sink:
        codigo |= medir_sink()
    if argumentos.motor or not argumentos.sink:
        codigo |= medir_motor()
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
