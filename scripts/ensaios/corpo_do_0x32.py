#!/usr/bin/env python3
"""corpo_do_0x32.py — o corpo do output `0x32` é um contêiner TLV ou o `common`?

A PERGUNTA (E-1 da A-PONTE-UNIVERSAL-01)
-----------------------------------------
O produto já monta, em regime, o pedido de microfone por rádio
(`integrations/dualsense_bt_audio.py:241-257`)::

    pkt[2] = BLOCO_AUDIO_CONTROL | BLOCO_PRESENTE   # 0x11 | 0x80 = 0x91
    pkt[3] = 1                                      # "comprimento do bloco"
    pkt[4] = 0b011 (LIGAR) | 0b010 (DESLIGAR)       # "valor do bloco"

Há duas leituras possíveis desses três bytes, e elas divergem:

* **TLV** — `[2]` é tag, `[3]` é comprimento, `[4]` é valor. O bit0 do valor é o
  liga/desliga do microfone. O pacote de DESLIGAR (`0b010`, bit0 = 0) **MUTA**.
* **`common` de 47 bytes** — o envelope de rádio é `[0]` id, `[1]` nibble de
  sequência, `[2]` tag, e o `common` começa em `[3]`. Então `[3]` é
  `valid_flag0` e `[4]` é `valid_flag1`. O pacote de DESLIGAR vira
  `valid_flag1 = 0x02` (`POWER_SAVE_CONTROL_ENABLE`) com `common[9] = 0x00`,
  que é literalmente **DESMUTAR**.

As duas leituras preveem o MESMO para o pacote de LIGAR — é por isso que o WAV
de 25/07 nunca decidiu nada. **Para o pacote de DESLIGAR elas preveem o
OPOSTO**, e o veredito é um bit do próprio aparelho: `report[55] & 0x04`
(`INPUT_OFFSET_AUDIO_STATUS = 55`, `STATUS_MIC_MUDO = 0x04`).

O QUE ESTE INSTRUMENTO ESCREVE NO APARELHO: **NADA**
-----------------------------------------------------
Nem um byte. Ele abre o hidraw **em leitura** pela porta do broker e conta bits.
Toda escrita é do PRODUTO, em regime, pela CLI que ele já entrega:

* ``hefesto-dualsense4unix mic mute|unmute|release --uniq <mac>`` — mexe no mudo
  do FIRMWARE pelo caminho do `0x31` (`common[9]`, `POWER_SAVE_MIC_MUTE`). É o
  **controle positivo**, e é ele que ARMA o aparelho no estado MUDO.
* ``hefesto-dualsense4unix mic bt`` — sobe a ponte, que escreve o `0x32` de
  LIGAR ao subir (`iniciar()`, `:898`) e o de DESLIGAR ao parar
  (`parar()`, `:917`). É o único caminho por onde o `0x32` sai nesta corrida.

POR QUE ARMAR MUDO ANTES (e este é o ponto que decide o ensaio)
----------------------------------------------------------------
Se o ensaio começasse com o microfone ATIVO, a previsão do `common` para o
pacote de DESLIGAR ("desmuta") seria indistinguível de "o pacote não fez nada" —
e "não fez nada" também é o que se vê quando o firmware descarta o report. O
ensaio não teria controle positivo do próprio `0x32`.

Armando MUDO, a corrida ganha dois degraus:

1. o `0x32` de **LIGAR** tem de LIMPAR o mudo. Se limpar, está provado que o
   `0x32` chega e é obedecido — **controle positivo do próprio report medido**;
2. só então o `0x32` de **DESLIGAR** decide: se o mudo VOLTAR, é TLV; se ficar
   limpo, é o `common`.

O `release` entre o armar e o medir não é detalhe: com posse do registrador o
daemon manda `POWER_SAVE_CONTROL_ENABLE` com `common[9]` a 60 Hz e escreveria
por cima do que o `0x32` fizesse (AUDIO-OWNER-01,
`core/backend_pydualsense.py:1038`, `:1082`). O `release` devolve a posse ao
kernel, o bit de autorização CAI, e o firmware conserva o mudo que recebeu — o
que este instrumento **verifica**, numa janela própria, antes de medir.

CONTROLE NEGATIVO — dois, na mesma corrida
-------------------------------------------
1. **o byte vizinho**: `report[54]` (o `status[0]`, bateria) não pode se mover
   nas mesmas janelas em que o `[55]` se move. Se os dois andarem juntos, o que
   mudou foi a leitura, não o microfone;
2. **a janela sem comando**: uma basal em que nenhum comando é dado e o bit tem
   de ficar parado. Um bit que oscila sozinho não decide nada.

CONFUNDIMENTO: **IMUNE**
-------------------------
O veredito é um bit do próprio aparelho mudando (ou não) em resposta ao próprio
produto. Não há comparação entre braços da mesa, então a troca de braços de
15/08 não entra na conta.

QUANTAS UNIDADES
-----------------
O `0x32` **só existe no rádio**: por cabo o descritor declara um único OUTPUT, o
`0x02` de 47 B (medido em 11/08/2026). Este ensaio, portanto, só pode falar das
unidades que estiverem no rádio AGORA — e ele diz quantas são, pelo
`hardware_version` de cada uma, em vez de fingir que mediu quatro.
"""

from __future__ import annotations

import argparse
import os
import select
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)

from comum import (  # noqa: E402
    RADIO,
    Aparelho,
    abrir_no_hidraw,
    cabecalho_do_instrumento,
    censo_da_mesa,
    descobrir_aparelhos,
    fisicos,
    resumo,
    tabela,
)

# ---------------------------------------------------------------------------
# O que se lê do report de INPUT por rádio. Os nomes e os números são os do
# produto (`integrations/dualsense_bt_audio.py`), importados quando dá — e
# repetidos aqui com a fonte declarada quando o pacote não está no caminho.
# ---------------------------------------------------------------------------

INPUT_REPORT_BT = 0x31
INPUT_REPORT_BT_SIZE = 78
INPUT_FLAG_HID = 0x01
INPUT_FLAG_AUDIO = 0x02
INPUT_OFFSET_AUDIO_STATUS = 55
INPUT_OFFSET_VIZINHO = 54  # `status[0]`, bateria — o controle negativo
STATUS_MIC_MUDO = 0x04

_FONTE_DAS_CONSTANTES = "repetidas neste arquivo"
try:  # pragma: no cover - depende do interpretador
    from hefesto_dualsense4unix.integrations import dualsense_bt_audio as _dsa

    INPUT_REPORT_BT = _dsa.INPUT_REPORT_BT
    INPUT_REPORT_BT_SIZE = _dsa.INPUT_REPORT_BT_SIZE
    INPUT_FLAG_HID = _dsa.INPUT_FLAG_HID
    INPUT_FLAG_AUDIO = _dsa.INPUT_FLAG_AUDIO
    INPUT_OFFSET_AUDIO_STATUS = _dsa.INPUT_OFFSET_AUDIO_STATUS
    STATUS_MIC_MUDO = _dsa.STATUS_MIC_MUDO
    _FONTE_DAS_CONSTANTES = _dsa.__file__
except Exception:  # pragma: no cover - fora do venv do projeto
    pass

#: O executável do produto. É ele quem escreve; este arquivo não.
_CLI = os.path.join(os.path.dirname(os.path.dirname(_AQUI)), ".venv", "bin",
                    "hefesto-dualsense4unix")


def mascarar_mac(mac: str) -> str:
    """A máscara da casa: octetos 4 e 5 zerados (`OUI:00:00:NN`).

    O OUI fica porque é público e é ele que explica o achado; o sufixo é o que
    identifica o aparelho dela, e esse sai. Há portão que reprova MAC real em
    arquivo versionado, e a saída bruta deste instrumento é versionada.
    """
    partes = mac.split(":")
    if len(partes) != 6:
        return mac
    return ":".join([*partes[:3], "00", "00", partes[5]])


def hardware_version(dir_device: str) -> str:
    """O `hardware_version` do sysfs — a identidade que ela pediu que eu use.

    Não é o MAC e não é o número do `hidraw`: os dois mudam entre sessões e o
    segundo mudou HOJE, na troca de braços. O `hardware_version` é da unidade.
    """
    for nome in ("hardware_version", "device/hardware_version"):
        caminho = os.path.join(dir_device, nome)
        try:
            with open(caminho, encoding="utf-8") as arquivo:
                return arquivo.read().strip()
        except OSError:
            continue
    return "?"


# ---------------------------------------------------------------------------
# A leitura: uma thread, um `select` sobre todos os nós, nenhuma escrita
# ---------------------------------------------------------------------------


@dataclass
class Evento:
    """Um report de input já reduzido ao que este ensaio pergunta."""

    t: float
    byte54: int
    byte55: int
    audio: bool


@dataclass
class Unidade:
    """Uma unidade da mesa, no rádio, com a sua trilha de eventos."""

    aparelho: Aparelho
    hw: str
    eventos: list[Evento] = field(default_factory=list)

    @property
    def rotulo(self) -> str:
        return f"{mascarar_mac(self.aparelho.mac)} (hw {self.hw})"


class Leitor:
    """Lê os nós em uma thread e carimba cada report com o relógio da corrida.

    Uma thread só, e um `select` sobre todos os fds: dois leitores com dois
    relógios já produziram, nesta casa, uma tabela em que a mesma janela tinha
    duas durações.
    """

    def __init__(self, unidades: list[Unidade]) -> None:
        self._unidades = unidades
        self._nos = {u.aparelho.caminho_hidraw: abrir_no_hidraw(
            u.aparelho.caminho_hidraw, escrita=False) for u in unidades}
        self._por_fd = {
            self._nos[u.aparelho.caminho_hidraw].fd: u for u in unidades
        }
        self._parar = threading.Event()
        self._thread = threading.Thread(target=self._laco, name="e1-leitor",
                                        daemon=True)
        self.t0 = 0.0
        self.curtos = 0

    @property
    def linhas_da_porta(self) -> list[str]:
        return [
            f"{caminho}: {no.linha_de_relatorio}"
            for caminho, no in self._nos.items()
        ]

    def iniciar(self) -> None:
        self.t0 = time.monotonic()
        self._thread.start()

    def parar(self) -> None:
        self._parar.set()
        self._thread.join(timeout=3.0)
        for no in self._nos.values():
            no.fechar()

    def _laco(self) -> None:
        fds = list(self._por_fd)
        while not self._parar.is_set():
            prontos, _, _ = select.select(fds, [], [], 0.2)
            agora = time.monotonic() - self.t0
            for fd in prontos:
                try:
                    dados = os.read(fd, 128)
                except OSError:
                    continue
                if len(dados) < INPUT_REPORT_BT_SIZE or dados[0] != INPUT_REPORT_BT:
                    self.curtos += 1
                    continue
                unidade = self._por_fd[fd]
                unidade.eventos.append(
                    Evento(
                        t=agora,
                        byte54=dados[INPUT_OFFSET_VIZINHO],
                        byte55=dados[INPUT_OFFSET_AUDIO_STATUS],
                        audio=bool(dados[1] & INPUT_FLAG_AUDIO),
                    )
                )


# ---------------------------------------------------------------------------
# As fases: cada uma é uma janela de tempo com um nome e, talvez, um comando
# ---------------------------------------------------------------------------


@dataclass
class Fase:
    nome: str
    comando: str  # o que o PRODUTO escreveu nesta fase (vazio = nada)
    inicio: float
    fim: float = 0.0
    saida: str = ""


@dataclass
class Recorte:
    """O que uma fase viu num nó."""

    reports: int
    audio: int
    primeiro55: int | None
    ultimo55: int | None
    valores55: dict[int, int]
    valores54: dict[int, int]

    @property
    def mudo_no_fim(self) -> bool | None:
        if self.ultimo55 is None:
            return None
        return bool(self.ultimo55 & STATUS_MIC_MUDO)

    @property
    def mudo_no_inicio(self) -> bool | None:
        if self.primeiro55 is None:
            return None
        return bool(self.primeiro55 & STATUS_MIC_MUDO)

    @property
    def bit_estavel(self) -> bool:
        bits = {v & STATUS_MIC_MUDO for v in self.valores55}
        return len(bits) <= 1

    @property
    def vizinho_estavel(self) -> bool:
        return len(self.valores54) <= 1


def recortar(unidade: Unidade, fase: Fase) -> Recorte:
    """Os eventos de `unidade` dentro da janela de `fase`, resumidos."""
    dentro = [e for e in unidade.eventos if fase.inicio <= e.t <= fase.fim]
    estado = [e for e in dentro if not e.audio]
    valores55: dict[int, int] = {}
    valores54: dict[int, int] = {}
    for e in estado:
        valores55[e.byte55] = valores55.get(e.byte55, 0) + 1
        valores54[e.byte54] = valores54.get(e.byte54, 0) + 1
    return Recorte(
        reports=len(estado),
        audio=sum(1 for e in dentro if e.audio),
        primeiro55=estado[0].byte55 if estado else None,
        ultimo55=estado[-1].byte55 if estado else None,
        valores55=valores55,
        valores54=valores54,
    )


def _selo(valor: bool | None) -> str:
    if valor is None:
        return "sem report"
    return "MUDO" if valor else "ativo"


def _hex_contado(valores: dict[int, int]) -> str:
    if not valores:
        return "—"
    return " ".join(
        f"0x{v:02x}x{n}" for v, n in sorted(valores.items(), key=lambda p: -p[1])
    )


# ---------------------------------------------------------------------------
# A corrida
# ---------------------------------------------------------------------------


class Corrida:
    def __init__(self, leitor: Leitor, unidades: list[Unidade], *,
                 verboso: bool) -> None:
        self.leitor = leitor
        self.unidades = unidades
        self.fases: list[Fase] = []
        self.verboso = verboso

    def _agora(self) -> float:
        return time.monotonic() - self.leitor.t0

    def dormir(self, segundos: float) -> None:
        time.sleep(segundos)

    def fase(self, nome: str, duracao: float, *, comando: list[str] | None = None,
             ) -> Fase:
        """Abre uma janela, roda o comando do PRODUTO (se houver), espera, fecha.

        A janela começa DEPOIS do comando de propósito: o que interessa é o
        estado que o aparelho passou a declarar, e incluir o instante da
        escrita na janela misturaria o antes com o depois.
        """
        saida = ""
        rotulo = " ".join(comando) if comando else ""
        if comando:
            proc = subprocess.run(comando, capture_output=True, text=True,
                                  timeout=60, check=False)
            saida = "\n".join(
                linha for linha in (proc.stdout + proc.stderr).splitlines()
                if not linha.startswith("2026-")
            ).strip()
        f = Fase(nome=nome, comando=rotulo, inicio=self._agora(), saida=saida)
        if self.verboso:
            print(f"  ... {nome}  ({duracao:.0f}s)"
                  + (f"   <- {rotulo}" if rotulo else ""), flush=True)
        self.dormir(duracao)
        f.fim = self._agora()
        self.fases.append(f)
        return f


def ciclo_da_ponte(corrida: Corrida, braco: str, janela: float, *,
                   silencioso: bool) -> tuple[Fase, Fase, str]:
    """Sobe a ponte do produto, observa, manda SIGTERM, observa de novo.

    Quem escreve o `0x32` é a ponte, não este arquivo: `iniciar()` manda o
    LIGAR (`dualsense_bt_audio.py:898`) e `parar()` manda o DESLIGAR (`:917`).
    O SIGTERM é o MESMO caminho do Ctrl-C que a CLI documenta.
    """
    ponte = subprocess.Popen(
        [_CLI, "mic", "bt"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True,
    )
    f_ligar = Fase(nome=f"{braco}: 0x32 de LIGAR (a ponte subiu)",
                   comando=f"{_CLI} mic bt", inicio=corrida._agora())
    if not silencioso:
        print(f"  ... {f_ligar.nome}  ({janela + 4:.0f}s)", flush=True)
    time.sleep(janela + 4.0)
    f_ligar.fim = corrida._agora()
    corrida.fases.append(f_ligar)

    ponte.send_signal(signal.SIGTERM)
    try:
        saida = ponte.communicate(timeout=30)[0] or ""
    except subprocess.TimeoutExpired:  # pragma: no cover
        ponte.kill()
        saida = ponte.communicate()[0] or ""
    f_desligar = Fase(nome=f"{braco}: 0x32 de DESLIGAR (a ponte parou)",
                      comando="SIGTERM na ponte -> parar() -> 0x32 DESLIGAR",
                      inicio=corrida._agora())
    if not silencioso:
        print(f"  ... {f_desligar.nome}  ({janela + 6:.0f}s)", flush=True)
    time.sleep(janela + 6.0)
    f_desligar.fim = corrida._agora()
    corrida.fases.append(f_desligar)
    return f_ligar, f_desligar, saida


def montar_argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="E-1: o corpo do 0x32 é TLV ou é o `common` de 47 bytes?",
    )
    p.add_argument("--basal", type=float, default=20.0,
                   help="segundos da janela sem comando nenhum (controle "
                        "negativo). Padrão: 20.")
    p.add_argument("--janela", type=float, default=6.0,
                   help="segundos de observação após cada comando. Padrão: 6.")
    p.add_argument("--saida", default="",
                   help="arquivo onde gravar o relatório inteiro (além da tela).")
    p.add_argument("--silencioso", action="store_true",
                   help="não imprime o andamento fase a fase.")
    return p.parse_args()


def main() -> int:
    args = montar_argumentos()
    partes: list[str] = []

    def diga(texto: str = "") -> None:
        partes.append(texto)
        print(texto, flush=True)

    aparelhos = descobrir_aparelhos()
    diga(cabecalho_do_instrumento(
        "corpo_do_0x32.py",
        "o corpo do output 0x32 é um contêiner TLV ou o `common` de 47 bytes?",
        bibliotecas=["os", "select", "subprocess",
                     "hefesto_dualsense4unix.integrations.dualsense_bt_audio"],
        escreve_no_aparelho=False,
        daemon_precisa_parar=False,
    ))
    diga()
    diga("  QUEM ESCREVE, e este instrumento NÃO é um deles:")
    diga(f"    {_CLI} mic mute|unmute|release --uniq <mac>   (caminho 0x31, "
         "common[9] — o controle positivo e o ARMAR)")
    diga(f"    {_CLI} mic bt                                  (a ponte: 0x32 "
         "LIGAR ao subir, 0x32 DESLIGAR ao parar)")
    diga(f"  constantes do report .... de {_FONTE_DAS_CONSTANTES}")
    diga(f"  bit do veredito ......... report[{INPUT_OFFSET_AUDIO_STATUS}] & "
         f"0x{STATUS_MIC_MUDO:02x}   (controle negativo: "
         f"report[{INPUT_OFFSET_VIZINHO}], que não pode se mover junto)")
    diga("  confundimento ........... IMUNE — o veredito é um bit do próprio "
         "aparelho; não há comparação entre braços")
    diga()
    diga(censo_da_mesa(aparelhos))
    diga()

    no_radio = [a for a in fisicos(aparelhos) if a.transporte == RADIO]
    if not no_radio:
        diga("SEM MEDIÇÃO: nenhum DualSense no rádio. O 0x32 não existe no "
             "cabo — por cabo o descritor declara um único OUTPUT, o 0x02 de "
             "47 B (medido em 11/08/2026). Ponha ao menos um controle no "
             "rádio e rode de novo.")
        return 2

    unidades = [Unidade(aparelho=a, hw=hardware_version(a.dir_device))
                for a in no_radio]
    total_fisicos = len(fisicos(aparelhos))
    diga(f"  unidades que este ensaio PODE medir: {len(unidades)} de "
         f"{total_fisicos} — só as que estão no rádio, porque o 0x32 não "
         "existe no cabo:")
    for u in unidades:
        diga(f"    {u.aparelho.hidraw:<9} {u.rotulo}")
    diga()

    leitor = Leitor(unidades)
    for linha in leitor.linhas_da_porta:
        diga(f"  {linha}")
    diga()
    leitor.iniciar()

    corrida = Corrida(leitor, unidades, verboso=not args.silencioso)
    macs = [u.aparelho.mac for u in unidades]

    # --- 1. basal: nenhum comando. O bit tem de ficar parado. --------------
    f_basal = corrida.fase("basal (nenhum comando)", args.basal)

    # --- 2. controle positivo, unidade a unidade ---------------------------
    positivos: dict[str, tuple[Fase, Fase]] = {}
    for mac in macs:
        f_mute = corrida.fase(
            f"controle positivo: mute em {mascarar_mac(mac)}", args.janela,
            comando=[_CLI, "mic", "mute", "--uniq", mac])
        f_unmute = corrida.fase(
            f"controle positivo: unmute em {mascarar_mac(mac)}", args.janela,
            comando=[_CLI, "mic", "unmute", "--uniq", mac])
        corrida.fase(
            f"devolve a posse: release em {mascarar_mac(mac)}", 2.0,
            comando=[_CLI, "mic", "release", "--uniq", mac])
        positivos[mac] = (f_mute, f_unmute)

    # --- 3. BRAÇO A: armado MUDO -------------------------------------------
    # Armar MUDO e SOLTAR o registrador. O `release` não é detalhe: com posse,
    # o daemon manda `POWER_SAVE_CONTROL_ENABLE` a 60 Hz e escreveria por cima
    # do que o 0x32 fizesse. Sem posse, o firmware conserva o mudo — e é isso
    # que a janela seguinte VERIFICA antes de qualquer medição.
    for mac in macs:
        corrida.fase(f"armar MUDO em {mascarar_mac(mac)}", 2.0,
                     comando=[_CLI, "mic", "mute", "--uniq", mac])
    for mac in macs:
        corrida.fase(f"soltar o registrador de {mascarar_mac(mac)}", 2.0,
                     comando=[_CLI, "mic", "release", "--uniq", mac])
    f_armado = corrida.fase(
        "BRAÇO A: ARMADO MUDO — o mudo sobrevive sem o daemon segurando?",
        args.janela)
    f_ligar_a, f_desligar_a, saida_ponte_a = ciclo_da_ponte(
        corrida, "BRAÇO A (armado MUDO)", args.janela, silencioso=args.silencioso)

    # --- 4. BRAÇO B: armado ATIVO ------------------------------------------
    # O mesmo ciclo com o microfone DESMUTADO na largada. É aqui que a previsão
    # POSITIVA do TLV é falsificável: sob TLV o pacote de DESLIGAR (bit0 = 0)
    # tem de MUTAR; sob o `common` ele desmuta, e desmutar quem já está ativo é
    # não fazer nada.
    for mac in macs:
        corrida.fase(f"armar ATIVO em {mascarar_mac(mac)}", 2.0,
                     comando=[_CLI, "mic", "unmute", "--uniq", mac])
    for mac in macs:
        corrida.fase(f"soltar o registrador de {mascarar_mac(mac)}", 2.0,
                     comando=[_CLI, "mic", "release", "--uniq", mac])
    f_ativo = corrida.fase(
        "BRAÇO B: ARMADO ATIVO — o microfone está desmutado e sem dono?",
        args.janela)
    f_ligar_b, f_desligar_b, saida_ponte_b = ciclo_da_ponte(
        corrida, "BRAÇO B (armado ATIVO)", args.janela, silencioso=args.silencioso)
    saida_ponte = ("--- BRAÇO A ---\n" + saida_ponte_a
                   + "\n--- BRAÇO B ---\n" + saida_ponte_b)

    # --- 5. deixar a mesa como estava --------------------------------------
    for mac in macs:
        corrida.fase(f"restaurar: unmute em {mascarar_mac(mac)}", 1.5,
                     comando=[_CLI, "mic", "unmute", "--uniq", mac])
    for mac in macs:
        corrida.fase(f"restaurar: release em {mascarar_mac(mac)}", 1.5,
                     comando=[_CLI, "mic", "release", "--uniq", mac])

    leitor.parar()

    # --- 6. o que a corrida viu --------------------------------------------
    diga()
    diga("A LINHA DO TEMPO — cada fase, o que o produto escreveu, e o que o "
         "aparelho passou a declarar")
    linhas: list[list[str]] = []
    for f in corrida.fases:
        for u in unidades:
            r = recortar(u, f)
            linhas.append([
                f"{f.inicio:6.1f}-{f.fim:6.1f}",
                f.nome,
                mascarar_mac(u.aparelho.mac),
                str(r.reports),
                _selo(r.mudo_no_inicio),
                _selo(r.mudo_no_fim),
                _hex_contado(r.valores55),
                _hex_contado(r.valores54),
                str(r.audio),
            ])
    diga(tabela(["janela (s)", "fase", "unidade", "reports", "[55] no início",
                 "[55] no fim", "[55] observados", "[54] observados",
                 "reports de áudio"], linhas))

    diga()
    diga("A SAÍDA DO PRODUTO, comando a comando (é ele quem escreve)")
    for f in corrida.fases:
        if f.comando:
            diga(f"  $ {f.comando}")
            for linha in (f.saida or "(sem saída)").splitlines():
                diga(f"      {linha}")
    diga("  $ (a ponte, do subir ao SIGTERM)")
    for linha in (saida_ponte or "").splitlines():
        if not linha.startswith("2026-") or "bt_mic_pedido" in linha:
            diga(f"      {linha}")

    # --- 7. o veredito, unidade a unidade ----------------------------------
    diga()
    diga("O VEREDITO, UNIDADE A UNIDADE")
    veredito_linhas: list[list[str]] = []
    vereditos: dict[str, str] = {}
    for u in unidades:
        mac = u.aparelho.mac
        f_mute, f_unmute = positivos[mac]
        r_basal = recortar(u, f_basal)
        r_mute = recortar(u, f_mute)
        r_unmute = recortar(u, f_unmute)
        r_armado = recortar(u, f_armado)
        r_ativo = recortar(u, f_ativo)
        r_ligar_a = recortar(u, f_ligar_a)
        r_desligar_a = recortar(u, f_desligar_a)
        r_ligar_b = recortar(u, f_ligar_b)
        r_desligar_b = recortar(u, f_desligar_b)

        positivo_ok = r_mute.mudo_no_fim is True and r_unmute.mudo_no_fim is False
        basal_ok = r_basal.bit_estavel and r_basal.reports > 0
        vizinho_ok = all(
            r.vizinho_estavel for r in (r_basal, r_mute, r_unmute, r_armado,
                                        r_ativo, r_ligar_a, r_desligar_a,
                                        r_ligar_b, r_desligar_b))
        armado_ok = r_armado.mudo_no_inicio is True and r_armado.mudo_no_fim is True
        ativo_ok = r_ativo.mudo_no_fim is False

        # O CONTROLE POSITIVO DO PRÓPRIO 0x32, e é ele que separa "o firmware
        # não obedeceu" de "o report nem chegou": a basal não tem UM report de
        # áudio, e a janela do LIGAR tem centenas. O aparelho só começa a
        # mandar áudio porque recebeu e obedeceu ao 0x32.
        audio_na_basal = r_basal.audio
        audio_chegou = (r_ligar_a.audio > 0 or r_ligar_b.audio > 0)
        audio_parou = (r_desligar_a.audio == 0 and r_desligar_b.audio == 0)

        # BRAÇO A (armado MUDO): o `common` prevê DESMUTAR nos DOIS pacotes
        # (valid_flag1 0x03 e 0x02, ambos com common[9] = 0x00).
        a_desmutou = (r_ligar_a.mudo_no_fim is False
                      or r_desligar_a.mudo_no_fim is False)
        # BRAÇO B (armado ATIVO): o TLV prevê MUTAR no pacote de DESLIGAR.
        b_mutou = r_desligar_b.mudo_no_fim is True

        if not basal_ok:
            v = ("SEM VEREDITO — o bit oscilou na basal, sem comando nenhum. "
                 "Um bit que se mexe sozinho não decide nada.")
        elif not vizinho_ok:
            v = ("SEM VEREDITO — o byte vizinho [54] se moveu junto. O que "
                 "mudou foi a leitura, não o microfone.")
        elif not positivo_ok:
            v = ("SEM VEREDITO — o controle positivo falhou: o caminho do 0x31 "
                 "não moveu o bit nos dois sentidos. O réu é o instrumento ou "
                 "o daemon, não o 0x32.")
        elif not armado_ok or not ativo_ok:
            v = ("SEM VEREDITO — o estado armado não sobreviveu ao `release`. "
                 "Sem largada conhecida não há previsão a falsificar.")
        elif not audio_chegou:
            v = ("SEM VEREDITO — o 0x32 não teve EFEITO OBSERVÁVEL nenhum: nem "
                 "moveu o mudo, nem fez o aparelho mandar áudio. Sem prova de "
                 "que o report chegou, o silêncio não decide entre as leituras.")
        elif a_desmutou:
            v = ("O `common` DE 47 BYTES — armado MUDO, o 0x32 DESMUTOU o "
                 "microfone, que é exatamente o que valid_flag1 com "
                 "common[9]=0x00 faz. [3] é valid_flag0 e [4] é valid_flag1.")
        elif b_mutou:
            v = ("TLV — armado ATIVO, o 0x32 de DESLIGAR (0b010, bit0=0) MUTOU "
                 "o microfone, e armado MUDO ele NÃO desmutou. O `common` está "
                 "refutado nos dois braços. [2] é tag, [3] é comprimento, [4] "
                 "é valor.")
        else:
            v = ("TLV, e o bit0 é o FLUXO, não o registrador de mudo — o 0x32 "
                 "chegou e foi obedecido (o áudio começou a sair com LIGAR e "
                 "parou com DESLIGAR), e mesmo assim NÃO mexeu no "
                 "STATUS_MIC_MUDO em braço nenhum. O `common` está REFUTADO: "
                 "com valid_flag1=0x03 e common[9]=0x00 ele teria desmutado o "
                 "aparelho armado MUDO, e não desmutou.")
        vereditos[mac] = v
        veredito_linhas.append([
            u.rotulo,
            "ok" if basal_ok else "OSCILOU",
            "ok" if vizinho_ok else "MOVEU JUNTO",
            "ok" if positivo_ok else "FALHOU",
            f"{audio_na_basal} -> {r_ligar_a.audio}/{r_ligar_b.audio}"
            + ("" if audio_parou else "  (o áudio NÃO parou)"),
            "ok" if armado_ok else "NÃO",
            "DESMUTOU" if a_desmutou else "não desmutou",
            "ok" if ativo_ok else "NÃO",
            "MUTOU" if b_mutou else "não mutou",
        ])
    diga(tabela(["unidade", "basal parada", "[54] parado",
                 "controle positivo (0x31)",
                 "reports de áudio: basal -> LIGAR A/B",
                 "braço A armado MUDO", "A: o 0x32 desmutou?",
                 "braço B armado ATIVO", "B: o DESLIGAR mutou?"],
                veredito_linhas))
    diga()
    diga("  Como ler a coluna do áudio: a basal não tem comando nenhum e o "
         "aparelho não manda áudio; nas janelas de LIGAR ele manda centenas de "
         "reports com o bit de áudio. Esse é o CONTROLE POSITIVO DO PRÓPRIO "
         "0x32 — a prova de que o report chegou e foi obedecido, sem a qual "
         "'o mudo não mexeu' seria indistinguível de 'o pacote foi descartado'.")
    diga("  A previsão que o `common` faz, e que o braço A falsifica: sob essa "
         "leitura [4]=0b011 é valid_flag1=0x03 (MIC_MUTE_LED_CONTROL_ENABLE | "
         "POWER_SAVE_CONTROL_ENABLE) e [4]=0b010 é 0x02, os dois com "
         "common[9]=0x00 — que é o MESMO mecanismo pelo qual o `mic unmute` "
         "desmuta pelo 0x31, e que funcionou nesta mesma corrida.")
    diga()
    for u in unidades:
        diga(f"  {u.rotulo}")
        diga(f"      {vereditos[u.aparelho.mac]}")

    distintos = set(vereditos.values())
    if len(distintos) == 1 and len(unidades) > 1:
        concordancia = (f"as {len(unidades)} unidades no rádio concordam")
    elif len(unidades) == 1:
        concordancia = "uma única unidade no rádio — n=1, e o relatório diz isso"
    else:
        concordancia = "AS UNIDADES DISCORDAM — e a que discorda está nomeada acima"
    diga()
    diga(f"  em quantas unidades: {len(unidades)} de {total_fisicos} na mesa "
         f"({concordancia}). As outras estão no CABO, onde o 0x32 não existe.")
    diga(f"  reports curtos/ignorados na corrida: {leitor.curtos}")

    primeiro = vereditos[unidades[0].aparelho.mac].split(" — ")[0]
    diga(resumo(f"{primeiro}  ·  {len(unidades)}/{total_fisicos} unidades, "
                f"{concordancia}."))

    if args.saida:
        with open(args.saida, "w", encoding="utf-8") as arquivo:
            arquivo.write("\n".join(partes) + "\n")
        print(f"\n(relatório gravado em {args.saida})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
