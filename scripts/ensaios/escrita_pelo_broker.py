#!/usr/bin/env python3
"""escrita_pelo_broker.py — a porta de ESCRITA dos instrumentos de bancada de 09/09.

Três instrumentos nasceram das decisões dela de 09/09/2026 (*"1-b;2b;3-c"*):
o do fone (`o_fone_tem_volume_proprio.py`), o do brilho de hardware
(`o_brilho_de_hardware_da_barra.py`) e o do byte do microfone
(`o_byte_do_microfone_muda_a_captura.py`). Os três fazem a mesma coisa —
escrevem UM byte do `common` de 47 e olham o aparelho — e dividem quatro
decisões, que moram aqui para não nascerem três vezes:

1. **O report certo para o transporte.** Cabo: `0x02` de 64 bytes
   (`build_usb_report`). Rádio: `0x31` de 78 bytes com tag `0x10` e CRC-32 de
   semente `0xA2` (`build_bt_report`), com o nibble de sequência rotacionado a
   cada escrita. Os dois construtores são OS DO PRODUTO — montar à mão aqui
   mediria a minha memória do formato, não o aparelho.
2. **O `common` VAZIO.** Nada do estado do daemon entra: só o byte do ensaio e
   o bit que o autoriza variam entre os passos. É a lição do
   `corpo_do_degrau.py`: um common cheio de estado torna cada passo uma
   medição diferente.
3. **A porta.** `comum.abrir_no_hidraw` — o broker — com o daemon VIVO. Não há
   `os.open` direto: na mesa com o co-op ligado ele mede `EACCES`, não o
   aparelho (armadilha 3 do `CLAUDE.md`).
4. **O martelo.** O daemon reescreve alguns desses bytes a cada report dele:
   `_build_common` manda `flag2` com o bit do brilho e `common[42] = 0` sempre
   que é dono das luzes, e manda fone e alto-falante juntos sempre que é dono
   do volume. Um byte escrito uma vez pode ser desfeito milissegundos depois —
   e a barra que escureceu por um instante e voltou é um SIM do firmware, não
   um não. Por isso `martelar()`: repete a escrita a N Hz durante a janela de
   observação, e o relatório diz que martelou.

O QUE ESTE MÓDULO NÃO FAZ
--------------------------
Não conclui nada. Quem conclui é o olho e a orelha dela (fone, brilho) ou o
pico da captura (microfone), e a linha do caderno sai PROPOSTA no fim de cada
instrumento — `docs/data/ensaios.csv` é de quem coordena a bancada.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)

from comum import (
    CABO,
    RADIO,
    Aparelho,
    abrir_no_hidraw,
    descobrir_aparelhos,
    fisicos,
)
from hefesto_dualsense4unix.core.ds_output_report import (
    BT_REPORT_LEN,
    COMMON_LEN,
    USB_REPORT_LEN,
    build_bt_report,
    build_usb_report,
)

#: A ordem das colunas de `docs/data/ensaios.csv`, lida do cabeçalho em 09/09/2026.
#: Quem propõe uma linha escreve nesta ordem — e o `validar-caducos` reprova se o
#: cabeçalho mudar sem que isto mude junto.
COLUNAS_DO_CADERNO = (
    "id",
    "linha_id",
    "transporte",
    "degrau",
    "ponte",
    "quando",
    "suspeito",
    "presente",
    "resultado",
    "resultado_da_feature",
    "observado_por",
    "fonte",
    "nota",
    "linha_id_v1",
)


def mascarar(mac: str) -> str:
    """A máscara da casa: octetos 4 e 5 zerados. Toda saída daqui é versionável."""
    partes = mac.split(":")
    if len(partes) != 6:
        return mac
    return ":".join([*partes[:3], "00", "00", partes[5]])


def alvos_da_mesa() -> list[Aparelho]:
    """Os DualSense FÍSICOS da mesa, nos dois transportes. O vpad fica de fora."""
    return fisicos(descobrir_aparelhos())


def escolher_alvo(aparelhos: list[Aparelho], chave: str) -> Aparelho | None:
    """O alvo pela MAC (inteira ou mascarada) ou pelo nome do hidraw."""
    chave = (chave or "").strip().lower()
    for a in aparelhos:
        if chave in (a.mac.lower(), mascarar(a.mac).lower(), a.hidraw.lower()):
            return a
    return None


def common_vazio() -> bytearray:
    """Os 47 bytes zerados. Nenhum flag, nenhum estado — só o que o passo puser."""
    return bytearray(COMMON_LEN)


def report_para(transporte: str, common: bytes | bytearray, seq: int = 0) -> bytes:
    """O report do transporte, montado pelo produto.

    Cabo -> `0x02` (64 B, sem CRC). Rádio -> `0x31` (78 B, CRC no rabo, `seq`
    no nibble alto de `[1]`). Qualquer outra coisa é erro, não palpite.
    """
    if transporte == CABO:
        return bytes(build_usb_report(common))
    if transporte == RADIO:
        return bytes(build_bt_report(common, seq=seq))
    raise ValueError(f"transporte sem report de saída conhecido: {transporte!r}")


def tamanho_esperado(transporte: str) -> int:
    return USB_REPORT_LEN if transporte == CABO else BT_REPORT_LEN


@dataclass
class Escritor:
    """Uma porta aberta para UM aparelho, que sabe montar e contar o que escreveu."""

    alvo: Aparelho
    escritas: int = 0
    bytes_no_fio: int = 0
    _seq: int = 0
    _no: object = field(default=None, repr=False)

    def abrir(self) -> str:
        """Abre pelo broker e devolve a linha de relatório da porta usada."""
        self._no = abrir_no_hidraw(self.alvo.caminho_hidraw, escrita=True)
        return getattr(self._no, "linha_de_relatorio", "porta: broker")

    def escrever(self, common: bytes | bytearray) -> int:
        """Uma escrita. Devolve os bytes que o `os.write` aceitou — que NÃO é a medição."""
        if self._no is None:
            raise RuntimeError("Escritor.abrir() antes de escrever")
        self._seq = (self._seq + 1) & 0x0F
        pacote = report_para(self.alvo.transporte, common, self._seq)
        escritos = os.write(self._no.fd, pacote)
        self.escritas += 1
        self.bytes_no_fio += escritos
        return escritos

    def martelar(self, common: bytes | bytearray, segundos: float, hz: float = 10.0) -> int:
        """Repete a escrita a `hz` durante `segundos`. Devolve quantas escritas fez."""
        intervalo = 1.0 / max(hz, 0.1)
        fim = time.monotonic() + max(segundos, 0.0)
        feitas = 0
        while True:
            self.escrever(common)
            feitas += 1
            if time.monotonic() >= fim:
                return feitas
            time.sleep(intervalo)

    def fechar(self) -> None:
        if self._no is not None:
            fechar = getattr(self._no, "fechar", None)
            if callable(fechar):
                fechar()
            self._no = None


def listar(aparelhos: list[Aparelho], *, so_transporte: str | None = None) -> str:
    """A mesa que este instrumento ENCONTROU, uma linha por controle físico."""
    linhas = []
    for a in aparelhos:
        if so_transporte and a.transporte != so_transporte:
            continue
        linhas.append(f"  {mascarar(a.mac):<20} {a.transporte:<6} {a.caminho_hidraw}")
    if not linhas:
        linhas.append("  nenhum DualSense físico na mesa")
    return "\n".join(linhas)


def linha_do_caderno(**campos: str) -> str:
    """UMA linha CSV na ordem do caderno, com aspas onde há vírgula. Só proposta."""
    campos.setdefault("quando", datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
    valores = []
    for coluna in COLUNAS_DO_CADERNO:
        v = str(campos.get(coluna, "")).replace('"', "'")
        valores.append(f'"{v}"' if ("," in v or "\n" in v) else v)
    return ",".join(valores)


def perguntar(texto: str) -> str:
    """A pergunta para ela, e a resposta dela — verbatim, sem limpar."""
    try:
        return input(texto).strip()
    except EOFError:
        return ""
