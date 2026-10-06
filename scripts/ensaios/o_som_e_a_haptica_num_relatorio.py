#!/usr/bin/env python3
"""o_som_e_a_haptica_num_relatorio.py — o 0x36 com o som e a háptica, num controle, pelo rádio.

O-SOM-E-A-HAPTICA-NUM-RELATORIO-SO-01 (03/10/2026), o primeiro tempo. Na
bancada de 03/10, pelo rádio, cada controle carregou som OU háptica: com os
dois pedidos, as pontes ficaram no ``0x35`` e a háptica não subiu, com dois ou
quatro controles por adaptador. A casa usa dois escritores por controle, o
``0x35`` do som e o ``0x32`` da háptica, cada um com o seu contador no
``0x11``. O fork loteran do DS5Dongle monta um ``0x36`` com os quatro blocos
num relatório só (``0x11`` + ``0x10`` + ``0x12`` + ``0x13``), lido no código e
nunca tentado aqui. Este ensaio é a prova do FORMATO, antes de a ponte mudar:
um controle, um escritor, um contador, o som e a háptica no mesmo quadro.

O que ele manda, a 93,75 relatórios por segundo (o ritmo do ``0x35`` que
tocou), por ``--segundos``: no ``0x13``, um tom contínuo (``--tom-hz``); no
``0x12``, uma onda senoidal (``--haptica-hz``) no lado escolhido (``--lado``:
``centro`` são os dois canais em fase, ``esquerdo`` o canal 3 e ``direito`` o
canal 4, o que a mão do usuário mediu em 03/10); no ``0x10``, o estado
(``--estado``: ``audio`` pede rota, volume e pré-amplificador do alto-falante,
como o ensaio do som; ``neutro`` vai com as validades zeradas; ``nenhum`` tira
o bloco, a variação que testa se o firmware exige o ``0x10``).

SEM ``--escrever``, monta três relatórios em seco e mostra os blocos e o CRC:
nada vai ao aparelho. COM ``--escrever``, ele RECUSA, nesta ordem:

1. o daemon no ar (ele escreve no mesmo hidraw, e o ``0x31`` dele no meio do
   ensaio mediria outra coisa: instrumento que briga com o produto recusa);
2. sem ``--exigir-mac`` conferido, ou com um endereço fora da lista;
3. o controle no cabo (o ``0x36`` é do rádio);
4. sem ``--eu-estou-ouvindo`` (rc=3): o ensaio é escrever com o ouvido e a
   mão do usuário do outro lado;
5. a bancada tomada por outra reserva (``scripts/bancada.sh exigir`` passa
   só com ela LIVRE: quem reservou mede, e o ensaio não escreve por cima).

O RETORNO DO ``os.write()`` NÃO É A MEDIÇÃO: o kernel aceita a entrega que o
firmware descarta calado. O veredito é dela (ouviu o tom contínuo? sentiu a
onda, sem alternar?), e vai ao ``docs/data/ensaios.csv`` com o relato dela.
"""

from __future__ import annotations

import argparse
import math
import os
import struct
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field

_AQUI = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.dirname(_AQUI)
_RAIZ = os.path.dirname(_SCRIPTS)
_SRC = os.path.join(_RAIZ, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import haptica_bt

SEGUNDOS_PADRAO = 10.0
TETO_DE_SEGUNDOS = 60.0
TOM_HZ_PADRAO = 440.0
HAPTICA_HZ_PADRAO = 120.0
AMPLITUDE_DO_SOM = 9000
FRACAO_DA_HAPTICA = 0.6
LADOS = ("centro", "esquerdo", "direito")
ESTADOS = ("audio", "neutro", "nenhum")


def tom_por_quadro(tom_hz: float) -> Callable[[], bytes]:
    """PCM ``s16le`` estéreo de um quadro Opus, contínuo de um quadro ao outro.

    A fase anda na taxa em que o quadro é TOCADO (``taxa_da_fonte("som")``,
    480 amostras a cada 10,667 ms), para o tom sair na altura pedida.
    """
    taxa = af.taxa_da_fonte("som")
    fase = [0]

    def _quadro() -> bytes:
        amostras: list[int] = []
        for _ in range(af.AMOSTRAS_POR_QUADRO):
            valor = int(AMPLITUDE_DO_SOM * math.sin(2 * math.pi * tom_hz * fase[0] / taxa))
            amostras.extend((valor, valor))
            fase[0] += 1
        return struct.pack(f"<{len(amostras)}h", *amostras)

    return _quadro


def onda_por_bloco(haptica_hz: float, lado: str) -> Callable[[], bytes]:
    """Um bloco ``0x12`` de 64 B: 32 pares (canal 3, canal 4) em ``int8`` a 3 kHz."""
    if lado not in LADOS:
        raise ValueError(f"lado {lado!r} fora de {LADOS}")
    pico = int(FRACAO_DA_HAPTICA * 127)
    fase = [0]

    def _bloco() -> bytes:
        saida = bytearray()
        for _ in range(haptica_bt.AMOSTRAS_POR_CANAL):
            valor = round(
                pico * math.sin(2 * math.pi * haptica_hz * fase[0] / haptica_bt.TAXA_DO_BLOCO)
            )
            fase[0] += 1
            esquerdo = valor if lado in ("centro", "esquerdo") else 0
            direito = valor if lado in ("centro", "direito") else 0
            saida += bytes((esquerdo & 0xFF, direito & 0xFF))
        return bytes(saida)

    return _bloco


def estado_do_ensaio(estado: str) -> bytes | None:
    """O ``common`` de 47 B do bloco ``0x10``, ou None quando o bloco não vai."""
    if estado == "audio":
        return af.common_de_audio()
    if estado == "neutro":
        return bytes(rep.COMMON_LEN)
    if estado == "nenhum":
        return None
    raise ValueError(f"estado {estado!r} fora de {ESTADOS}")


def descrever(relatorio: bytes) -> list[str]:
    """Os blocos do relatório, na ordem da cadeia, e o CRC conferido."""
    linhas = [
        f"  id 0x{relatorio[0]:02x}  {len(relatorio)} B  seq {relatorio[1] >> 4}"
        f"  contador do 0x11 {relatorio[10]}"
    ]
    pos = 2
    while pos + 1 < len(relatorio) - af.CRC_BYTES and relatorio[pos]:
        tag, tamanho = relatorio[pos], relatorio[pos + 1]
        linhas.append(f"  [{pos:3d}] bloco 0x{tag & 0x3F:02x} (tag 0x{tag:02x}) com {tamanho} B")
        pos += 2 + tamanho
    crc = rep.bt_crc32(relatorio[: -af.CRC_BYTES], seed=rep.BT_CRC_SEED)
    certo = crc.to_bytes(4, "little") == relatorio[-af.CRC_BYTES :]
    linhas.append(f"  CRC {'certo' if certo else 'ERRADO'}")
    return linhas


def daemon_no_ar() -> bool:
    """O daemon pode estar no ar? Na dúvida, SIM: «não sei» nunca é «parado».

    Primeiro a pergunta do ``test trigger --raw`` (``daemon.status``). Sem
    resposta, o socket decide: nenhum socket, ou um socket que recusa a
    conexão (o que sobrou de um daemon morto), é o daemon parado; alguém que
    aceita a conexão (o daemon ocupado demais para responder em 0,25 s) ou
    qualquer outro erro é «pode estar no ar», e o ensaio recusa.
    """
    import socket

    from hefesto_dualsense4unix.app.ipc_bridge import daemon_status_basic
    from hefesto_dualsense4unix.utils.xdg_paths import ipc_socket_path

    try:
        if daemon_status_basic() is not None:
            return True
        caminho = ipc_socket_path()
        if not caminho.exists():
            return False
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conexao:
            conexao.settimeout(1.0)
            conexao.connect(str(caminho))
    except (ConnectionRefusedError, FileNotFoundError):
        return False
    except Exception:
        return True
    return True


def _exigir_bancada() -> tuple[bool, str]:
    """``scripts/bancada.sh exigir`` — rc≠0 é ESPERAR, nunca contornar."""
    proc = subprocess.run(
        ["bash", os.path.join(_RAIZ, "scripts", "bancada.sh"), "exigir"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


@dataclass
class Contagem:
    """O que o laço contou. Nada disto é a medição."""

    montados: int = 0
    entregues: int = 0
    recusados_pelo_kernel: int = 0
    bytes_entregues: int = 0
    segundos: float = 0.0
    erros: list[str] = field(default_factory=list)

    def linhas(self) -> list[str]:
        ritmo = self.entregues / self.segundos if self.segundos > 0 else 0.0
        return [
            f"  relatórios montados ........ {self.montados}",
            f"  entregues ao kernel ........ {self.entregues} ({ritmo:.2f}/s)",
            f"  recusados pelo kernel ...... {self.recusados_pelo_kernel}",
            f"  bytes entregues ............ {self.bytes_entregues}",
            f"  duração .................... {self.segundos:.2f} s",
            *(f"  erro: {e}" for e in self.erros[:5]),
        ]


def montador(argumentos: argparse.Namespace) -> Callable[[], bytes]:
    """O escritor único do ensaio: um relatório por quadro, um contador só."""
    escritor = af.RelatorioCombinado()
    common = estado_do_ensaio(argumentos.estado)
    onda = None if argumentos.sem_haptica else onda_por_bloco(argumentos.haptica_hz, argumentos.lado)
    tom = None if argumentos.sem_som else tom_por_quadro(argumentos.tom_hz)
    codificador = af.CodificadorOpus() if tom is not None else None

    def _proximo() -> bytes:
        quadro = codificador.codificar(tom()) if (tom and codificador) else None
        return escritor.relatorio_do_quadro(
            quadro_de_som=quadro,
            haptico=onda() if onda is not None else None,
            common=common,
        )

    return _proximo


def laco(
    proximo: Callable[[], bytes],
    escrever: Callable[[bytes], int],
    *,
    segundos: float,
    relogio: Callable[[], float] = time.monotonic,
    dormir: Callable[[float], None] = time.sleep,
) -> Contagem:
    """Escreve no ritmo do ``0x35`` (512/48000 s por relatório) por ``segundos``."""
    contagem = Contagem()
    intervalo = af.INTERVALO_DE_ENVIO_035
    comeco = relogio()
    alvo = comeco
    while relogio() - comeco < segundos:
        relatorio = proximo()
        contagem.montados += 1
        try:
            escritos = escrever(relatorio)
            contagem.entregues += 1
            contagem.bytes_entregues += int(escritos or 0)
        except BlockingIOError:
            contagem.recusados_pelo_kernel += 1
        except OSError as erro:
            contagem.erros.append(str(erro))
            break
        alvo += intervalo
        espera = alvo - relogio()
        if espera > 0:
            dormir(espera)
    contagem.segundos = relogio() - comeco
    return contagem


def resumo(argumentos: argparse.Namespace, alvo: str) -> str:
    som = "nenhum" if argumentos.sem_som else f"tom de {argumentos.tom_hz:.0f} Hz contínuo"
    haptica = (
        "nenhuma" if argumentos.sem_haptica
        else f"onda de {argumentos.haptica_hz:.0f} Hz, lado {argumentos.lado}"
    )
    return (
        f"  alvo        {alvo}\n"
        f"  relatório   0x{af.DEGRAU_COMBINADO:02x} "
        f"({af.TAMANHO_DO_DEGRAU[af.DEGRAU_COMBINADO]} B), "
        f"{1 / af.INTERVALO_DE_ENVIO_035:.2f} por segundo\n"
        f"  som (0x13)  {som}\n"
        f"  háptica     {haptica}\n"
        f"  estado      {argumentos.estado}\n"
        f"  duração     {min(argumentos.segundos, TETO_DE_SEGUNDOS):.1f} s\n"
    )


def em_seco(argumentos: argparse.Namespace) -> int:
    """Três relatórios montados e descritos. Nada vai ao aparelho."""
    print("EM SECO: nada é escrito. Os três primeiros relatórios do ensaio:\n")
    print(resumo(argumentos, "(nenhum, em seco)"))
    proximo = montador(argumentos)
    for _ in range(3):
        for linha in descrever(proximo()):
            print(linha)
        print()
    return 0


def escrever_no_aparelho(argumentos: argparse.Namespace) -> int:
    """A porta do ensaio de bancada: recusa muito mais do que aceita."""
    if daemon_no_ar():
        print(
            "RECUSADO: o daemon está no ar. Ele escreve no mesmo hidraw, e o 0x31\n"
            "  dele no meio do ensaio mediria outra coisa. Peça a ela que pare o\n"
            "  serviço pela mão dela, e rode de novo."
        )
        return 2
    from hefesto_dualsense4unix.daemon.subsystems.alto_falante import controles_na_lista

    if not argumentos.exigir_mac:
        print("RECUSADO: --escrever exige --exigir-mac com o endereço conferido.")
        return 2
    alvo = af.so_hex(argumentos.exigir_mac)
    achados = [c for c in controles_na_lista() if af.so_hex(c.uniq) == alvo]
    if not achados:
        print("RECUSADO: nenhum controle com esse endereço na lista.")
        return 2
    controle = achados[0]
    if controle.transporte != "rádio":
        print(f"RECUSADO: {controle.caminho} está no CABO. O 0x36 é do rádio.")
        return 2
    if not argumentos.eu_estou_ouvindo:
        print("PARADO ANTES DE ESCREVER, e de propósito.\n" + resumo(argumentos, controle.caminho))
        print("  Acrescente --eu-estou-ouvindo com o ouvido e a mão dela do outro lado.")
        return 3
    livre, recado = _exigir_bancada()
    if recado:
        print(f"  bancada ..... {recado}")
    if not livre:
        print("RECUSADO: a bancada está tomada por outra reserva. Esperar é a resposta.")
        return 2

    print("\nO QUE VAI SAIR, E POR QUANTO TEMPO\n" + resumo(argumentos, controle.caminho))
    from hefesto_dualsense4unix.integrations.dualsense_bt_audio import abrir_hidraw_rw

    try:
        fd = abrir_hidraw_rw(controle.caminho)
    except OSError as erro:
        print(f"RECUSADO: não deu para abrir {controle.caminho} — {erro}")
        return 2
    try:
        contagem = laco(
            montador(argumentos),
            af.escritor_de_hidraw(fd),
            segundos=min(max(0.0, float(argumentos.segundos)), TETO_DE_SEGUNDOS),
        )
    finally:
        os.close(fd)
    print("\nO QUE O LAÇO CONTOU (não é a medição)")
    for linha in contagem.linhas():
        print(linha)
    print(
        "\nO VEREDITO É DELA: o tom saiu contínuo pelo alto-falante? A onda foi\n"
        "  sentida no lado pedido, sem alternar com o som? A frase dela vai ao\n"
        "  docs/data/ensaios.csv; estes números não."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    analisador.add_argument("--escrever", action="store_true", help="a porta do ensaio de bancada")
    analisador.add_argument("--exigir-mac", default="", help="endereço conferido do alvo")
    analisador.add_argument("--eu-estou-ouvindo", action="store_true",
                            help="o ouvido e a mão dela do outro lado; sem isto, rc=3")
    analisador.add_argument("--segundos", type=float, default=SEGUNDOS_PADRAO,
                            help=f"duração (teto {TETO_DE_SEGUNDOS:.0f} s)")
    analisador.add_argument("--tom-hz", type=float, default=TOM_HZ_PADRAO)
    analisador.add_argument("--haptica-hz", type=float, default=HAPTICA_HZ_PADRAO)
    analisador.add_argument("--lado", choices=LADOS, default="centro")
    analisador.add_argument("--estado", choices=ESTADOS, default="audio")
    analisador.add_argument("--sem-som", action="store_true", help="só a háptica")
    analisador.add_argument("--sem-haptica", action="store_true", help="só o som")
    argumentos = analisador.parse_args(argv)
    if argumentos.escrever:
        return escrever_no_aparelho(argumentos)
    return em_seco(argumentos)


if __name__ == "__main__":
    raise SystemExit(main())
