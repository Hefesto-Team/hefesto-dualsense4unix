#!/usr/bin/env python3
"""o_som_que_sai.py — o MESMO PCM pelos DOIS arranjos, e o nó que nasce."""

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

from collections.abc import Sequence

from hefesto_dualsense4unix.integrations import alto_falante_bt as af


def degrau_para_payload(bytes_de_payload: int) -> int | None:
    """O MENOR degrau cujo orçamento comporta este payload. None se não cabe."""
    if bytes_de_payload < 0:
        return None
    for degrau in sorted(af.TAMANHO_DO_DEGRAU):
        if degrau == af.DEGRAU_DO_KERNEL:
            continue
        if af.ORCAMENTO_DO_DEGRAU[degrau] >= bytes_de_payload:
            return degrau
    return None


def montar_pelos_dois_arranjos(
    quadros: Sequence[bytes],
    *,
    seq: int = 0,
    tag_audio: int = af.BLOCO_SPEAKER,
) -> dict[str, bytes]:
    """O MESMO PCM já codificado, montado pelos DOIS arranjos candidatos."""
    return {a.nome: a.montar(quadros, seq=seq, tag_audio=tag_audio) for a in af.ARRANJOS}


MAC_SINTETICO = "aa:bb:cc:00:00:01"

TOM_HZ = 440.0
AMPLITUDE = 12000


def pcm_de_referencia(quadros: int = 2) -> list[bytes]:
    """Quadros de PCM ``s16le`` estéreo de 10 ms — o MESMO para os dois arranjos."""
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


BANCADA_HZ = 1300.0
BANCADA_PULSOS_HZ = 2.0


def pcm_pulsado(taxa: int = af.TAXA_DO_ENCODER) -> Callable[[int], bytes]:
    """Uma fonte de PCM infinita com o timbre da bancada. `s16le` estéreo, à `taxa`."""
    fase = itertools.count()

    def _ler(quantos: int) -> bytes:
        amostras: list[int] = []
        for _ in range(quantos // 4):
            f = next(fase)
            t = f / taxa
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
        degrau = degrau_para_payload(n)
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
        pacotes = montar_pelos_dois_arranjos([q or b"" for q in opus])
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
    """Carrega o nó, LÊ do servidor o que chegou nele, e descarrega."""
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


TETO_DE_SEGUNDOS = 15.0

SEGUNDOS_PADRAO = 4.0


def _linha_do_common(common: bytes | None) -> str:
    """A linha que DIZ o que vai em [3..49] — ou que ali não vai nada."""
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


def intervalo_do_arranjo(arranjo: af.Arranjo) -> float:
    """O intervalo entre reports do arranjo: o medido quando existe, o nominal quando não."""
    if arranjo.intervalo_de_envio_s is not None:
        return float(arranjo.intervalo_de_envio_s)
    return float(af.MS_POR_QUADRO * max(1, arranjo.quadros_de_audio) / 1000.0)


def rodar_o_arranjo(
    arranjo: af.Arranjo,
    *,
    fonte: Callable[[int], bytes],
    escritor: Callable[[bytes], int],
    tag_audio: int,
    common: bytes | None,
    segundos: float,
) -> af.ContagemDaBomba:
    """O laço do ensaio: lê o PCM de um report, codifica, monta pelo ARRANJO e escreve.

    A ponte do produto escreve só o ``0x36`` combinado
    (:class:`alto_falante_bt.BombaDeSomPeloRadio`); este laço é o do ensaio dos
    arranjos de fora, e mora aqui. O relógio é o do módulo do motor, o mesmo do
    :func:`alto_falante_bt.fonte_com_ritmo` que dá o ritmo à fonte.
    """
    relogio = af.time.monotonic
    contagem = af.ContagemDaBomba()
    pedido = af.BYTES_DE_PCM_POR_QUADRO * arranjo.quadros_de_audio
    comeco = relogio()
    limite = comeco + max(0.0, float(segundos))
    seq = 0
    quadros_mandados = 0
    codificador = af.CodificadorOpus()
    try:
        while relogio() < limite:
            pcm = fonte(pedido)
            if not pcm:
                break
            contagem.pcm_lido += len(pcm)
            pcm = pcm.ljust(pedido, b"\x00")
            quadros = []
            for i in range(arranjo.quadros_de_audio):
                quadro = codificador.codificar(
                    pcm[i * af.BYTES_DE_PCM_POR_QUADRO : (i + 1) * af.BYTES_DE_PCM_POR_QUADRO]
                )
                if quadro is None:
                    contagem.quadros_recusados += 1
                    break
                contagem.quadros_opus += 1
                quadros.append(bytes(quadro))
            if len(quadros) != arranjo.quadros_de_audio:
                continue
            controle = (
                af.controle_de_audio_035(contador_de_quadros=quadros_mandados)
                if arranjo.controle_conta_quadros
                else b""
            )
            report = arranjo.montar(
                quadros, seq=seq, tag_audio=tag_audio, common=common, controle=controle
            )
            seq = (seq + 1) % af.VOLTA_DA_SEQUENCIA
            quadros_mandados += max(1, arranjo.quadros_de_audio)
            contagem.reports_montados += 1
            try:
                contagem.bytes_escritos += int(escritor(report))
                contagem.escritas_aceitas_pelo_kernel += 1
            except OSError:
                contagem.escritas_recusadas += 1
                break
    finally:
        fechar = getattr(codificador, "close", None)
        if callable(fechar):
            fechar()
    contagem.segundos = relogio() - comeco
    return contagem


def escrever_no_aparelho(argumentos: argparse.Namespace) -> int:
    """A porta do ensaio de bancada — e ela recusa muito mais do que aceita.

    **Este caminho é o ensaio 1 da MESA-DE-QUATRO-01**, não deste script
    sozinho. Até 07/09/2026 ele parava ANTES de escrever, com rc=3, e a razão
    estava escrita: *"ele existe aqui para que o instrumento esteja pronto
    quando a bancada e a orelha dela estiverem"*. As duas chegaram — ela está
    na bancada com os quatro DualSense —, e o que faltava do nosso lado era o
    laço entre o encoder e o fio, que agora existe (:func:`rodar_o_arranjo`).

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
        intervalo = intervalo_do_arranjo(arranjo)
        taxa = round(af.AMOSTRAS_POR_QUADRO * max(1, arranjo.quadros_de_audio) / intervalo)
        print(
            f"  PCM por report {af.BYTES_DE_PCM_POR_QUADRO * arranjo.quadros_de_audio} B, "
            f"tocados em {1000 * intervalo:.3f} ms (timbre a {taxa} Hz)"
        )
        print(f"  cadência       {1 / intervalo:.2f} reports/s")
        contagem = rodar_o_arranjo(
            arranjo,
            fonte=af.fonte_com_ritmo(pcm_pulsado(taxa=taxa), ms_por_report=1000 * intervalo),
            escritor=af.escritor_de_hidraw(fd),
            tag_audio=argumentos.tag,
            common=common,
            segundos=segundos,
        )
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
