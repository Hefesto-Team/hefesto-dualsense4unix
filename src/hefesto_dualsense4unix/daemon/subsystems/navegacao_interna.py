"""A Navegação Interna: um valor, um dono, e o foco decide.

A-NAVEGACAO-INTERNA-E-UM-MODO-QUE-SE-LIGA-EM-QUALQUER-ABA-01 (29/09/2026, com o
desenho dela de 03/10). Com a Interna ligada e a janela do Hefesto na frente,
cada controle anda as abas com R1 e L1, anda a seleção com o direcional, aciona
com X, sai com O e guarda com Start. Enquanto a janela está na frente esses
botões não chegam ao jogo (D-22) e o R1/L1 não saem como Alt+Tab (D-20); fora
dela, tudo volta a ser o de sempre.

O FOCO TEM PRAZO. A janela declara que está na frente pelo ``navegacao.foco``,
num pulso quando ganha ou perde o foco e numa renovação a cada tique dela. O
daemon larga o foco sozinho ``PRAZO_DO_FOCO_S`` depois da última renovação:
uma janela que morre sem se despedir não deixa botão roubado.

OS TOQUES SÃO CONTADORES QUE SÓ SOBEM. O leitor evdev de cada controle já conta
cada borda de aperto (``EvdevSnapshot.apertos``); aqui se soma só a diferença
entre duas leituras feitas com o foco vivo. A janela aplica a diferença com o
que leu antes, e um toque curto entre dois tiques dela não se perde, o que o
nível (``buttons``) perderia.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

TIPO_INTERNA = "interna"
TIPO_COMPUTADOR = "computador"
TIPOS = (TIPO_INTERNA, TIPO_COMPUTADOR)

#: Sem renovação por mais que isto, o foco cai e os botões voltam ao jogo.
PRAZO_DO_FOCO_S = 1.0

#: Os botões que navegam, no nome do leitor evdev, e o nome do toque na
#: resposta do ``navegacao.foco``. Os analógicos e os gatilhos nunca (D-22).
#: O Start (``options``) entra pelo desenho de 03/10: com a Interna ele
#: guarda as escolhas de todos no perfil, e não pausa o jogo atrás.
TOQUES: dict[str, str] = {
    "r1": "r1",
    "l1": "l1",
    "cross": "x",
    "circle": "o",
    "square": "quadrado",
    "triangle": "triangulo",
    "dpad_up": "cima",
    "dpad_down": "baixo",
    "dpad_left": "esquerda",
    "dpad_right": "direita",
    "options": "start",
}
BOTOES_QUE_NAVEGAM = frozenset(TOQUES)

#: O R1 e o L1 são o Alt+Tab do teclado emulado (D-20): com o foco vivo, calam.
#: Com o mouse desligado calam todos os ``BOTOES_QUE_NAVEGAM``.
BOTOES_DO_ALT_TAB = frozenset({"r1", "l1"})

#: O que a Interna guarda de quem navega o PC com o mouse ligado: o Alt+Tab e o Start
#: (22/10/2026: o Start sempre guarda; ele não sai como Super por cima da janela).
BOTOES_DE_QUEM_NAVEGA_O_PC = BOTOES_DO_ALT_TAB | frozenset({"options"})


class NavegacaoInterna:
    """O dono da Interna no daemon: ligada, tipo, o foco com prazo e os toques."""

    def __init__(
        self,
        *,
        ligada: bool = True,
        tipo: str = TIPO_INTERNA,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self.ligada = bool(ligada)
        self.tipo = tipo if tipo in TIPOS else TIPO_INTERNA
        self._relogio = relogio
        self._lock = threading.Lock()
        self._foco_ate = float("-inf")
        self._vistos: dict[str, dict[str, int]] = {}
        self._toques: dict[str, dict[str, int]] = {}

    @classmethod
    def da_sessao(cls) -> NavegacaoInterna:
        """A escolha guardada (``navegacao_interna.flag``); sem ela, ligada (19/10/2026)."""
        from hefesto_dualsense4unix.utils.session import load_navegacao_interna

        ligada, tipo = load_navegacao_interna()
        return cls(ligada=ligada, tipo=tipo)

    def definir(self, *, ligada: bool | None = None, tipo: str | None = None) -> None:
        """Muda o que veio e guarda os dois; o tipo inválido levanta."""
        if tipo is not None and tipo not in TIPOS:
            raise ValueError(f"tipo de navegação desconhecido: {tipo!r}")
        if ligada is not None:
            self.ligada = bool(ligada)
        if tipo is not None:
            self.tipo = tipo
        from hefesto_dualsense4unix.utils.session import save_navegacao_interna

        save_navegacao_interna(self.ligada, self.tipo)
        logger.info("navegacao_interna_definida", ligada=self.ligada, tipo=self.tipo)

    def declarar_foco(self, ativa: bool) -> None:
        """O pulso e a renovação da janela: na frente, o prazo recomeça."""
        with self._lock:
            self._foco_ate = (
                self._relogio() + PRAZO_DO_FOCO_S if ativa else float("-inf")
            )

    def foco_vivo(self) -> bool:
        """A janela está na frente, e a última renovação está dentro do prazo."""
        with self._lock:
            return self._relogio() <= self._foco_ate

    def age(self) -> bool:
        """A Interna ligada e a janela na frente: o roubo e os toques valem."""
        return self.ligada and self.foco_vivo()

    def roubar(self, botoes: frozenset[str]) -> frozenset[str]:
        """Os botões que vão ao pad virtual: sem os que navegam, quando ela age."""
        if not botoes or not self.age():
            return botoes
        return botoes - BOTOES_QUE_NAVEGAM

    def calar_o_alt_tab(
        self, botoes: frozenset[str], *, mouse_ligado: bool
    ) -> frozenset[str]:
        """Os botões que vão ao teclado emulado, quando a Interna age.

        Quem navega o PC (mouse ligado) perde o R1 e o L1, que são o Alt+Tab, e o
        Start, que guarda o perfil; o resto segue tecla. Quem não navega o PC
        (mouse desligado) navega a Interna: todo botão dela, e os que o perfil
        ligou a uma tecla, fica com a Interna e não sai como tecla.
        """
        if not botoes or not self.age():
            return botoes
        return botoes - (BOTOES_DE_QUEM_NAVEGA_O_PC if mouse_ligado else BOTOES_QUE_NAVEGAM)

    def contar(self, apertos_por_uniq: Mapping[str, Mapping[str, int] | None]) -> None:
        """Soma nos toques a diferença dos ``apertos`` de cada leitor.

        Só com a Interna agindo: fora dela a leitura só ressincroniza a base,
        e o R1 que saiu como Alt+Tab não vira aba depois. Um leitor reiniciado
        (o contador dele voltou para trás) conta a partir do zero novo.
        """
        agindo = self.age()
        with self._lock:
            for uniq, apertos in apertos_por_uniq.items():
                if not isinstance(apertos, Mapping):
                    continue
                vistos = self._vistos.get(uniq, {})
                toques = self._toques.setdefault(uniq, dict.fromkeys(TOQUES.values(), 0))
                novos: dict[str, int] = {}
                for botao, nome in TOQUES.items():
                    agora = int(apertos.get(botao, 0) or 0)
                    novos[botao] = agora
                    if not agindo or uniq not in self._vistos:
                        continue
                    antes = vistos.get(botao, 0)
                    toques[nome] += agora - antes if agora >= antes else agora
                self._vistos[uniq] = novos

    def toques(self, uniqs: Iterable[str] | None = None) -> dict[str, dict[str, int]]:
        """Os contadores de cada controle, que só sobem."""
        with self._lock:
            escolhidos = self._toques if uniqs is None else {
                u: self._toques[u] for u in uniqs if u in self._toques
            }
            return {u: dict(t) for u, t in escolhidos.items()}

    def bloco(self) -> dict[str, Any]:
        """O bloco ``navegacao`` do ``state_full``."""
        return {"interna_ligada": self.ligada, "tipo": self.tipo, "foco": self.foco_vivo()}


def da_navegacao(daemon: Any) -> NavegacaoInterna | None:
    """A Interna do daemon, ou ``None`` num dublê que não a tem."""
    nav = getattr(daemon, "_navegacao_interna", None)
    return nav if isinstance(nav, NavegacaoInterna) else None


def roubar_o_que_navega(
    daemon: Any, botoes: frozenset[str], soltos: frozenset[str]
) -> tuple[frozenset[str], frozenset[str]]:
    """O roubo da D-22 antes do ``forward_buttons``: o primário e os do co-op.

    Tirar o botão do conjunto gera a soltura no pad no tique seguinte, porque
    o ``forward_buttons`` faz diferença contra o estado inteiro: nada fica
    preso. Os ``soltos`` (o toque que coube num tique só) perdem os mesmos.
    """
    nav = da_navegacao(daemon)
    if nav is None:
        return botoes, soltos
    return nav.roubar(botoes), nav.roubar(soltos)
