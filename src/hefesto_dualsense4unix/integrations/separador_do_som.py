"""O separador da caixa: o alto-falante do controle toca só o efeito do jogo, nunca a música.

A-CAIXA-DO-CONTROLE-TOCA-SO-O-SFX-01, método (3) da medida de 14/11/2026: STFT causal
(janela de 720, salto de 240: 10 ms a 48 kHz, 10,7 ms a 45 kHz) e a máscara do HPSS rápido
vezes a da porta de transiente. Fica entre o nó de som e a caixa, no cabo e no rádio; o corpo
não passa por aqui. Abaixo de 250 Hz a caixa cala; amostra de até 1 LSB sai zero, porque o
rádio só cala com bytes zero. Limite medido: com batida forte a caixa só abaixa, e a voz e o
efeito tonal perdem de 12 a 20 dB.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from typing import Any

AMOSTRAS_DA_JANELA = 720
AMOSTRAS_DO_SALTO = 240
PISO_DA_CAIXA_HZ = 250.0
TETO_DA_PORTA_HZ = 12_000.0
SOBE_DO_HARMONICO_MS = 60.0
DESCE_DO_HARMONICO_MS = 30.0
LARGURA_DO_PERCUSSIVO_HZ = 1200.0
PESO_DO_HARMONICO = 1.5
LIMIAR_SOBRE_OS_PICOS = 1.6
JANELA_DOS_PICOS_S = 4.0
LIMIAR_SEM_HISTORIA_DB = 6.0
LIMIAR_MINIMO_DB = 2.0
FUNDO_ANTES_DO_GOLPE_MS = 50.0
PESO_DO_FUNDO = 2.0
PORTA_ABERTA_MS = 350.0
PORTA_ABERTA_NO_MAXIMO_S = 1.5
CAUDA_DO_GOLPE = 0.05
SOLTURA_DA_PORTA_MS = 60.0
TROCA_DA_CHAVE_MS = 20.0
FUNDO_SILENCIOSO_DBFS = -60.0
SILENCIO_LSB = 2


def o_separador_cabe_aqui() -> bool:
    """Esta máquina tem o numpy de que o separador precisa? Nunca levanta."""
    if "numpy" in sys.modules:
        return True
    try:
        return importlib.util.find_spec("numpy") is not None
    except (ImportError, ValueError):
        return False


def _np() -> Any:
    import numpy

    return numpy


class _Harmonico:
    """O HPSS rápido: a máscara do que é ataque contra o que sustenta tom."""

    def __init__(self, taxa_hz: int, janela: int, salto: int) -> None:
        np = _np()
        quadros_por_s = taxa_hz / salto
        self._sobe = 1.0 - float(np.exp(-1.0 / (SOBE_DO_HARMONICO_MS / 1000.0 * quadros_por_s)))
        self._desce = 1.0 - float(
            np.exp(-1.0 / (DESCE_DO_HARMONICO_MS / 1000.0 * quadros_por_s))
        )
        self._largura = max(3, round(LARGURA_DO_PERCUSSIVO_HZ / (taxa_hz / janela)) | 1)
        self._meia = self._largura // 2
        self._estendido = np.zeros(janela // 2 + 1 + self._largura)
        self._envoltoria: Any = None

    def mascara(self, modulo: Any) -> Any:
        np = _np()
        if self._envoltoria is None:
            self._envoltoria = modulo.copy()
        diferenca = modulo - self._envoltoria
        self._envoltoria += (self._desce + (self._sobe - self._desce) * (diferenca > 0)) * diferenca
        meia = self._meia
        estendido = self._estendido
        estendido[: meia + 1] = modulo[0]
        estendido[meia + 1 : meia + 1 + len(modulo)] = modulo
        estendido[meia + 1 + len(modulo) :] = modulo[-1]
        acumulado = np.cumsum(estendido)
        percussivo = (acumulado[self._largura:] - acumulado[:-self._largura]) / self._largura
        harmonico = (PESO_DO_HARMONICO * self._envoltoria) ** 2
        quadrado = percussivo * percussivo
        return quadrado / (harmonico + quadrado + 1e-12)


class _Porta:
    """A porta de transiente: abre no golpe, guarda o fundo de antes, solta devagar.

    O limiar segue os picos da MÚSICA: o pico que nasce do silêncio (abaixo de -60 dBFS
    nos 50 ms de antes) não entra na conta. Sem isso, o efeito depois do silêncio (o jogo
    sem trilha, o menu) virava a régua de si mesmo, e de três golpes iguais só um passava.
    """

    _PICOS = 64

    def __init__(self, taxa_hz: int, janela: int, salto: int, soma_da_janela: float) -> None:
        np = _np()
        frequencias = np.fft.rfftfreq(janela, 1.0 / taxa_hz)
        self._bins = janela // 2 + 1
        self._banda = np.flatnonzero(
            (frequencias >= PISO_DA_CAIXA_HZ) & (frequencias <= TETO_DA_PORTA_HZ)
        )
        quadros_por_s = taxa_hz / salto
        self._anel = np.full((3, len(self._banda)), -140.0)
        self._quantos_antes = max(4, int(FUNDO_ANTES_DO_GOLPE_MS / 1000.0 * quadros_por_s))
        self._antes = np.zeros((self._quantos_antes, self._bins))
        self._alturas = np.zeros(self._PICOS)
        self._quando = np.full(self._PICOS, -(10**9))
        self._proximo_pico = 0
        self._fluxo_1 = 0.0
        self._fluxo_2 = 0.0
        self._t = 0
        self._aberta_ate = -1
        self._abriu_em = -(10**9)
        self._maximo = int(PORTA_ABERTA_NO_MAXIMO_S * quadros_por_s)
        self._segura = int(PORTA_ABERTA_MS / 1000.0 * quadros_por_s)
        self._janela_dos_picos = int(JANELA_DOS_PICOS_S * quadros_por_s)
        self._soltura = float(np.exp(-1.0 / (SOLTURA_DA_PORTA_MS / 1000.0 * quadros_por_s)))
        self._envelope = 0.0
        self._fundo = np.zeros(self._bins)
        self._pico_do_golpe = 0.0
        self._zeros = np.zeros(self._bins)
        amplitude = 10.0 ** (FUNDO_SILENCIOSO_DBFS / 20.0)
        self._silencio = (amplitude * soma_da_janela / 2.0) ** 2
        self._banda_antes = np.zeros(self._quantos_antes)
        self._silencio_antes = True

    def _limiar(self, t: int) -> float:
        np = _np()
        validos = self._quando > t - self._janela_dos_picos
        if int(validos.sum()) < 3:
            return LIMIAR_SEM_HISTORIA_DB
        return LIMIAR_SOBRE_OS_PICOS * float(np.median(self._alturas[validos]))

    def mascara(self, modulo: Any) -> Any:
        np = _np()
        t = self._t
        self._t += 1
        nivel = 20.0 * np.log10(modulo[self._banda] + 1e-7)
        referencia = self._anel.max(0)
        referencia[1:-1] = np.maximum(
            referencia[1:-1], np.maximum(referencia[:-2], referencia[2:])
        )
        fluxo = float(np.maximum(nivel - referencia, 0.0).sum()) / len(nivel)
        self._anel[t % 3] = nivel
        silencio_agora = float(self._banda_antes.sum()) < self._silencio * self._quantos_antes
        pico = self._fluxo_1 > self._fluxo_2 and self._fluxo_1 >= fluxo and self._fluxo_1 > 0.5
        if pico and not self._silencio_antes:
            self._alturas[self._proximo_pico % self._PICOS] = self._fluxo_1
            self._quando[self._proximo_pico % self._PICOS] = t - 1
            self._proximo_pico += 1
        self._silencio_antes = silencio_agora
        self._fluxo_2, self._fluxo_1 = self._fluxo_1, fluxo
        potencia = modulo * modulo
        if fluxo > LIMIAR_MINIMO_DB and t > self._aberta_ate and fluxo > self._limiar(t):
            self._fundo = self._antes.mean(0)
            self._aberta_ate = t + self._segura
            self._abriu_em = t
            self._pico_do_golpe = 0.0
        self._antes[t % self._quantos_antes] = potencia
        self._banda_antes[t % self._quantos_antes] = float(potencia[self._banda].sum())
        if t <= self._aberta_ate and t - self._abriu_em < self._maximo:
            excesso = float(
                np.maximum(
                    potencia[self._banda] - PESO_DO_FUNDO * self._fundo[self._banda], 0.0
                ).sum()
            )
            self._pico_do_golpe = max(self._pico_do_golpe, excesso)
            if excesso > CAUDA_DO_GOLPE * self._pico_do_golpe:
                self._aberta_ate = max(self._aberta_ate, t + 2)
            self._envelope = 1.0
        else:
            self._envelope *= self._soltura
        if self._envelope < 1e-4:
            return self._zeros
        return (
            np.clip(1.0 - PESO_DO_FUNDO * self._fundo / (potencia + 1e-12), 0.0, 1.0)
            * self._envelope
        )


class SeparadorDoSom:
    """Do PCM do nó de som ao PCM da caixa: só o efeito, atrasado 480 amostras.

    Um por caminho (uma ponte do rádio, uma caixa do cabo), com estado entre as
    chamadas. ``so_efeitos`` é a chave «Só efeitos» daquele controle (um booleano ou
    quem o diz, lido a cada salto); desligada, a máscara vai a 1 em 20 ms, sem estalo.
    A máscara sai da potência média dos canais e vale igual em cada um: o estéreo fica
    estéreo, e o som em oposição de fase não se cancela.
    """

    def __init__(
        self,
        taxa_hz: int,
        *,
        canais: int = 2,
        so_efeitos: bool | Callable[[], bool] = True,
        janela: int = AMOSTRAS_DA_JANELA,
        salto: int = AMOSTRAS_DO_SALTO,
    ) -> None:
        np = _np()
        self.taxa_hz = int(taxa_hz)
        self.canais = max(1, int(canais))
        self.so_efeitos = so_efeitos
        self._janela_n = int(janela)
        self._salto = int(salto)
        janela_raiz = np.sqrt(0.5 - 0.5 * np.cos(2 * np.pi * np.arange(janela) / janela))
        soma = np.zeros(janela)
        for deslocamento in range(0, janela, salto):
            soma += np.roll(janela_raiz**2, deslocamento)
        self._janela = janela_raiz
        self._sintese = janela_raiz / soma.mean()
        frequencias = np.fft.rfftfreq(janela, 1.0 / self.taxa_hz)
        self._grave = frequencias < PISO_DA_CAIXA_HZ
        self._harmonico = _Harmonico(self.taxa_hz, janela, salto)
        self._porta = _Porta(self.taxa_hz, janela, salto, float(janela_raiz.sum()))
        self._passo_da_chave = min(1.0, (salto / self.taxa_hz) / (TROCA_DA_CHAVE_MS / 1000.0))
        self._ligada = self._a_chave()
        self._mistura = 1.0 if self._ligada else 0.0
        self._sinais = 0
        self._da_mascara = 1
        self._entrada: Any = None
        self._janelas: Any = None
        self._somas: Any = None
        self._saida: Any = None

    @property
    def latencia_amostras(self) -> int:
        """O atraso da caixa, em amostras por canal (o salto inteiro, sem sobra)."""
        return self._janela_n - self._salto

    def _a_chave(self) -> bool:
        chave = self.so_efeitos
        if not callable(chave):
            return bool(chave)
        try:
            return bool(chave())
        except Exception:
            return bool(getattr(self, "_ligada", True))

    def _preparar(self, quantos: int) -> None:
        np = _np()
        self._sinais = quantos
        self._entrada = np.zeros((quantos, 0))
        self._janelas = np.zeros((quantos, self._janela_n))
        self._somas = np.zeros((quantos, self._janela_n))
        self._saida = np.zeros((quantos, 0))

    def _mascara(self, modulo: Any) -> Any:
        separacao = self._porta.mascara(modulo) * self._harmonico.mascara(modulo)
        separacao[self._grave] = 0.0
        self._ligada = self._a_chave()
        alvo = 1.0 if self._ligada else 0.0
        if self._mistura < alvo:
            self._mistura = min(alvo, self._mistura + self._passo_da_chave)
        elif self._mistura > alvo:
            self._mistura = max(alvo, self._mistura - self._passo_da_chave)
        if self._mistura >= 1.0:
            return separacao
        return self._mistura * separacao + (1.0 - self._mistura)

    def _um_salto(self, bloco: Any) -> Any:
        np = _np()
        salto = self._salto
        janelas = self._janelas
        janelas[:, :-salto] = janelas[:, salto:]
        janelas[:, -salto:] = bloco
        espectros = np.fft.rfft(janelas * self._janela, axis=1)
        if self._da_mascara == 1:
            modulo = np.abs(espectros[0])
        else:
            canais = espectros[: self._da_mascara]
            potencia = canais.real**2 + canais.imag**2
            modulo = np.sqrt(potencia.sum(0) / self._da_mascara)
        mascara = self._mascara(modulo)
        somas = self._somas
        somas[:, :-salto] = somas[:, salto:]
        somas[:, -salto:] = 0.0
        somas += np.fft.irfft(espectros * mascara, self._janela_n, axis=1) * self._sintese
        return somas[:, :salto].copy()

    def separar(self, *sinais: Any, canais_da_mascara: int = 1) -> list[Any]:
        """A máscara dos primeiros sinais aplicada a todos, em ``float`` do mesmo tamanho.

        Os sinais além de ``canais_da_mascara`` são testemunhas: como a máscara é linear,
        passar a música e o efeito separados pela máscara da mistura mostra o que sai de
        cada um.
        """
        np = _np()
        if not sinais:
            return []
        if len(sinais) != self._sinais:
            self._preparar(len(sinais))
        self._da_mascara = max(1, min(int(canais_da_mascara), len(sinais)))
        tamanho = len(sinais[0])
        entrada = np.concatenate((self._entrada, np.vstack(sinais).astype(float)), axis=1)
        salto = self._salto
        saltos = entrada.shape[1] // salto
        prontos = [self._saida]
        for indice in range(saltos):
            prontos.append(self._um_salto(entrada[:, indice * salto:(indice + 1) * salto]))
        self._entrada = entrada[:, saltos * salto:]
        pronto = np.concatenate(prontos, axis=1)
        if pronto.shape[1] < tamanho:
            falta = np.zeros((len(sinais), tamanho - pronto.shape[1]))
            pronto = np.concatenate((falta, pronto), axis=1)
        self._saida = pronto[:, tamanho:]
        return list(pronto[:, :tamanho])

    def processar(self, pcm: bytes) -> bytes:
        """PCM s16 little-endian intercalado → o mesmo tamanho, só o efeito."""
        np = _np()
        quadro = 2 * self.canais
        util = len(pcm) - len(pcm) % quadro
        if util <= 0:
            return bytes(len(pcm))
        amostras = np.frombuffer(pcm[:util], dtype="<i2").reshape(-1, self.canais) / 32768.0
        saidas = self.separar(*amostras.T, canais_da_mascara=self.canais)
        inteiros = np.clip(np.rint(np.stack(saidas, axis=1) * 32768.0), -32768, 32767)
        inteiros[np.abs(inteiros) < SILENCIO_LSB] = 0
        return bytes(inteiros.astype("<i2").tobytes()) + bytes(len(pcm) - util)


__all__ = [
    "AMOSTRAS_DA_JANELA",
    "AMOSTRAS_DO_SALTO",
    "PISO_DA_CAIXA_HZ",
    "SeparadorDoSom",
    "o_separador_cabe_aqui",
]
