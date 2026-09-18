"""O PCM da háptica vira bloco de rádio — HAPTICA-POR-RADIO-01, P2.

No CABO a vibração dos jogos da Sony viaja como áudio: o jogo abre o endpoint do
controle com quatro canais e toca os canais 3 e 4, que são os dois motores
voice-coil. Pelo rádio não há placa de áudio, e o mesmo sinal tem de ir dentro de
um report HID, num bloco de 64 bytes a cada 10,667 ms.

**MEDIDO EM 18/09/2026, com a mão dela** (`scripts/ensaios/a_haptica_pelo_radio.py`):
o motor vibra quando o report `0x32` (ou o `0x35`, o do alto-falante) leva o bloco
`0x91` de AudioControl e, depois dele, o bloco `0x92` com 64 bytes de PCM int8
estéreo a 3 kHz. Sem o `0x91` não vibra; com as amostras zeradas, cala.

ESTE MÓDULO É SÓ A CONTA, e por isso não importa nada de aparelho: entra PCM de
48 kHz com quatro canais, sai a lista de blocos prontos. Quem escreve no controle
é a ponte (P4), que já é dona do report `0x35` do alto-falante — um escritor por
controle, nunca dois (um segundo escritor desliga o microfone, a queixa de
10/09/2026).

A CONTA, e cada passo tem uma razão:

1. **só os canais 3 e 4** — os canais 1 e 2 são o alto-falante do controle, e
   mandá-los aos motores faria o controle tremer com a voz do jogo;
2. **passa-baixa antes de dizimar** — 48 kHz para 3 kHz é uma dizimação por 16, e
   sem filtro tudo o que passa de 1,5 kHz volta dobrado em cima do sinal
   (*aliasing*). O filtro é a média móvel de 16 amostras, que é o que a dizimação
   pede e custa uma soma por amostra;
3. **int8 com clamp** — o bloco é de 8 bits com sinal, e o `-128` é o valor que
   estoura para o outro lado quando alguém soma sem olhar; aqui o piso é `-127`.

**O QUE NÃO ESTÁ MEDIDO, e está escrito de propósito:** qual motor é o canal 3 e
qual é o 4 (a ordem dos dois no bloco), e a escala exata entre o PCM do jogo e a
força que ela sente. As duas saem na bancada do P4, com a mão dela.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: 32 amostras por canal por bloco, a 3 kHz: os 10,667 ms do quadro de áudio.
TAXA_DO_BLOCO = 3000
AMOSTRAS_POR_CANAL = 32
BYTES_DO_BLOCO = AMOSTRAS_POR_CANAL * 2

#: A entrada é a do endpoint do DualSense: 48 kHz, quatro canais, s16le.
TAXA_DE_ENTRADA = 48000
CANAIS_DE_ENTRADA = 4
#: Os canais dos motores dentro do quadro de quatro (FL, FR, RL, RR).
CANAIS_DOS_MOTORES = (2, 3)

#: 48000 / 3000. É também o tamanho da janela do passa-baixa — numa dizimação, o
#: filtro e o fator andam juntos.
FATOR = TAXA_DE_ENTRADA // TAXA_DO_BLOCO

_PICO_INT16 = 32768
_PICO_INT8 = 127


@dataclass
class ConversorDeHaptica:
    """Recebe PCM em pedaços de qualquer tamanho e devolve blocos inteiros.

    Guarda o resto entre as chamadas: o jogo entrega quadros que não caem em
    múltiplos de 512, e um conversor sem memória picotaria o sinal a cada
    entrega — que é ruído audível no motor, não arredondamento.
    """

    ganho: float = 1.0
    canais: int = CANAIS_DE_ENTRADA
    motores: tuple[int, int] = CANAIS_DOS_MOTORES
    _resto: bytearray = field(default_factory=bytearray, repr=False)
    _pendentes: bytearray = field(default_factory=bytearray, repr=False)

    def alimentar(self, pcm: bytes | bytearray | memoryview) -> list[bytes]:
        """PCM s16le entrelaçado → blocos de 64 B prontos para o report."""
        dados = bytes(self._resto) + bytes(pcm)
        largura = 2 * self.canais
        quadros = len(dados) // largura
        sobra = quadros % FATOR
        usaveis = quadros - sobra
        self._resto = bytearray(dados[usaveis * largura :])
        if usaveis:
            self._pendentes += self._dizimar(dados[: usaveis * largura], usaveis)

        blocos: list[bytes] = []
        while len(self._pendentes) >= BYTES_DO_BLOCO:
            blocos.append(bytes(self._pendentes[:BYTES_DO_BLOCO]))
            del self._pendentes[:BYTES_DO_BLOCO]
        return blocos

    def _dizimar(self, dados: bytes, quadros: int) -> bytes:
        """Média móvel de 16 e uma amostra a cada 16, nos dois motores."""
        largura = 2 * self.canais
        esq, dir_ = self.motores
        saida = bytearray()
        for inicio in range(0, quadros, FATOR):
            somas = [0, 0]
            for q in range(inicio, inicio + FATOR):
                base = q * largura
                for lado, canal in enumerate((esq, dir_)):
                    off = base + 2 * canal
                    somas[lado] += int.from_bytes(dados[off : off + 2], "little", signed=True)
            for soma in somas:
                saida.append(self._para_int8(soma / FATOR))
        return bytes(saida)

    def _para_int8(self, valor: float) -> int:
        escalado = round(valor * self.ganho * _PICO_INT8 / _PICO_INT16)
        if escalado > _PICO_INT8:
            escalado = _PICO_INT8
        elif escalado < -_PICO_INT8:
            escalado = -_PICO_INT8
        return escalado & 0xFF

    def limpar(self) -> None:
        """Esquece o resto — o jogo fechou, e o próximo não herda meia amostra."""
        self._resto.clear()
        self._pendentes.clear()


def bloco_de_silencio() -> bytes:
    """64 bytes zerados: o bloco que não mexe os motores."""
    return bytes(BYTES_DO_BLOCO)


__all__ = [
    "AMOSTRAS_POR_CANAL",
    "BYTES_DO_BLOCO",
    "CANAIS_DOS_MOTORES",
    "FATOR",
    "TAXA_DO_BLOCO",
    "ConversorDeHaptica",
    "bloco_de_silencio",
]
