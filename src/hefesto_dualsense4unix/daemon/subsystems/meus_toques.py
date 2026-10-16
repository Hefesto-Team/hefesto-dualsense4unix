"""Os meus toques: o controle vibra a cada entrada de quem joga, além do que o jogo manda.

O botão é um TOQUE por borda (teto de 12 por segundo por controle e 40 no total); o analógico,
o gatilho e o chacoalhar são um par contínuo ``(esquerdo, direito)``. O par se junta ao pedido do
jogo pela mistura do perfil (o maior dos dois, ou a soma limitada a 255), e só «so_meus_toques»
tira o jogo do controle. O Modo Nativo, a háptica por áudio do jogo e o gatilho com efeito do jogo
calam o toque que lhes toca. O relógio é injetado em cada chamada.
"""

from __future__ import annotations

import math
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import (
    TETO_POR_CONTROLE,
    TETO_TOTAL,
    Teto,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

MODO_SO_O_JOGO = "so_o_jogo"
MODO_JOGO_E_TOQUES = "jogo_e_meus_toques"
MODO_SO_TOQUES = "so_meus_toques"
MISTURA_MAIOR = "maior"
MISTURA_SOMAR = "somar"
ANALOGICO_DESLIGADO = "desligado"
ANALOGICO_MOVIMENTO = "movimento"
ANALOGICO_POSICAO = "posicao"

TOQUE_DO_BOTAO_S = 0.04
CALA_PARADO_S = 0.3
ZONA_MORTA_DO_ANALOGICO = 0.15
MOVIMENTO_MINIMO = 3
LIMIAR_DO_GATILHO = 20
LIMIAR_DO_GIRO = 150.0
GIRO_CHEIO = 600.0
ENTRE_ESCRITAS_S = 1.0 / 30.0

#: O motor esquerdo é o grosso (o ``forte`` do rumble); o direito é o fino (o ``fraco``).
ESQUERDO = "esquerdo"
DIREITO = "direito"
BOTOES_DO_LADO: dict[str, str] = {
    **dict.fromkeys(("cross", "circle", "square", "triangle", "r1", "r3"), DIREITO),
    **dict.fromkeys(
        ("dpad_up", "dpad_down", "dpad_left", "dpad_right", "l1", "l3"), ESQUERDO),
}

#: Um par como ``(esquerdo, direito)``: o esquerdo é o forte e o direito o fraco do rumble.
Par = tuple[int, int]
#: Um par como o rumble o escreve: ``(fraco, forte)``.
ParDoRumble = tuple[int, int]


@dataclass(frozen=True)
class Ajuste:
    """A escolha do perfil: quando os toques valem e como se juntam ao jogo."""

    modo: str = MODO_SO_O_JOGO
    mistura: str = MISTURA_MAIOR
    forca: int = 30
    analogicos: str = ANALOGICO_MOVIMENTO
    botoes: bool = True
    gatilhos: bool = True
    chacoalhar: bool = True

    @property
    def liga(self) -> bool:
        return self.modo in (MODO_JOGO_E_TOQUES, MODO_SO_TOQUES)


SEM_TOQUES = Ajuste()


def _ler(alvo: Any, nome: str, padrao: Any) -> Any:
    if isinstance(alvo, dict):
        return alvo.get(nome, padrao)
    return getattr(alvo, nome, padrao)


def _escolha(valor: Any, validos: tuple[str, ...], padrao: str) -> str:
    return valor if isinstance(valor, str) and valor in validos else padrao


def _booleano(valor: Any, padrao: bool) -> bool:
    return valor if isinstance(valor, bool) else padrao


def ajuste_do_perfil(perfil: Any) -> Ajuste:
    """O ajuste do bloco ``meus_toques`` do perfil; sem bloco ou ilegível, o de fábrica."""
    bloco = _ler(perfil, "meus_toques", None)
    if bloco is None:
        return SEM_TOQUES
    forca = _ler(bloco, "forca", SEM_TOQUES.forca)
    return Ajuste(
        modo=_escolha(
            _ler(bloco, "modo", None),
            (MODO_SO_O_JOGO, MODO_JOGO_E_TOQUES, MODO_SO_TOQUES), MODO_SO_O_JOGO),
        mistura=_escolha(
            _ler(bloco, "mistura", None), (MISTURA_MAIOR, MISTURA_SOMAR), MISTURA_MAIOR),
        forca=max(0, min(100, forca)) if isinstance(forca, int) and not isinstance(
            forca, bool) else SEM_TOQUES.forca,
        analogicos=_escolha(
            _ler(bloco, "analogicos", None),
            (ANALOGICO_DESLIGADO, ANALOGICO_MOVIMENTO, ANALOGICO_POSICAO), ANALOGICO_MOVIMENTO),
        botoes=_booleano(_ler(bloco, "botoes", None), True),
        gatilhos=_booleano(_ler(bloco, "gatilhos", None), True),
        chacoalhar=_booleano(_ler(bloco, "chacoalhar", None), True),
    )


@dataclass(frozen=True)
class Entrada:
    """O que o controle de um jogador está fazendo agora: botões, analógicos, gatilhos e giro."""

    uniq: str
    botoes: frozenset[str] = frozenset()
    lx: int = 128
    ly: int = 128
    rx: int = 128
    ry: int = 128
    l2: int = 0
    r2: int = 0
    #: a velocidade angular total, em graus por segundo
    giro: float = 0.0


@dataclass(frozen=True)
class Mistura:
    """O que o pedido do jogo vira ao se juntar aos toques: o par do rumble e os dois lados."""

    motores: ParDoRumble
    jogo: Par
    toques: Par


@dataclass
class Ligacoes:
    """As pontas de fora: o que escreve e o que pergunta. Em produção, o backend e o daemon."""

    #: ``motores(uniq, fraco, forte)``: já com a força de quem recebe, como o pedido do jogo
    motores: Callable[[str, int, int], object]
    #: o jogo está aberto neste controle e o modo dele deixa o Hefesto falar (o Nativo cala)
    pode_falar: Callable[[str], bool]
    #: o jogo fala por háptica de áudio neste controle (o rumble dos motores a calaria)
    haptica_do_jogo: Callable[[str], bool]
    #: o jogo escreve um efeito nos gatilhos deste controle
    gatilho_do_jogo: Callable[[str], bool]
    #: ``dizer(uniq, pedido, efetivo, jogo, toques)``: o ``jogo.vibracao`` dos acessórios
    dizer: Callable[[str, ParDoRumble, ParDoRumble, Par, Par], object]
    #: a força de cada motor, ``(mult_fraco, mult_forte)``, a mesma do pedido do jogo
    forca: Callable[[str], tuple[float, float]] = lambda uniq: (1.0, 1.0)


@dataclass
class _Estado:
    botoes: frozenset[str] = frozenset()
    ref: dict[str, tuple[int, int]] = field(default_factory=dict)
    mexeu: dict[str, float] = field(default_factory=dict)
    toques_de_botao: list[tuple[float, str]] = field(default_factory=list)
    jogo: ParDoRumble = (0, 0)
    toques: Par = (0, 0)
    escrito: ParDoRumble | None = None
    escrito_em: float = float("-inf")
    ativo: bool = False


class MeusToques:
    """O que o controle vibra por conta das entradas de quem joga."""

    def __init__(self, ligacoes: Ligacoes, *, teto: Teto | None = None) -> None:
        self._l = ligacoes
        self._teto = teto if teto is not None else Teto(TETO_POR_CONTROLE, TETO_TOTAL)
        self._trava = threading.RLock()
        self._ajuste = SEM_TOQUES
        self._por_uniq: dict[str, _Estado] = {}
        self.escritas = 0
        self.toques_dados = 0

    @property
    def ajuste(self) -> Ajuste:
        return self._ajuste

    def ajustar(self, ajuste: Ajuste) -> None:
        """A escolha do perfil de agora; a volta ao jogo sozinho sai no tique seguinte."""
        with self._trava:
            self._ajuste = ajuste

    def precisa_andar(self) -> bool:
        """Há toque a dar, ou um toque a desfazer: o laço só monta as entradas se for preciso."""
        with self._trava:
            return self._ajuste.liga or any(c.ativo for c in self._por_uniq.values())

    # -- o tique ------------------------------------------------------------------------

    def tique(self, entradas: Sequence[Entrada], agora: float) -> int:
        """Anda os toques de cada controle; devolve quantas escritas saíram."""
        antes = self.escritas
        with self._trava:
            for entrada in entradas:
                try:
                    self._andar(entrada, agora)
                except Exception:
                    logger.debug("meus_toques_tique_falhou", exc_info=True)
        return self.escritas - antes

    def _andar(self, entrada: Entrada, agora: float) -> None:
        uniq = entrada.uniq
        estado = self._por_uniq.setdefault(uniq, _Estado())
        if not self._l.pode_falar(uniq):
            self._esquecer(estado, entrada)
            return
        if not self._ajuste.liga:
            estado.botoes = entrada.botoes
            estado.toques = (0, 0)
            if estado.ativo:
                self._escrever(uniq, estado, agora)
            return
        if self._l.haptica_do_jogo(uniq):
            estado.botoes = entrada.botoes
            estado.toques_de_botao.clear()
            estado.toques, estado.ativo, estado.escrito = (0, 0), False, None
            return
        estado.toques = self._toques_de(entrada, estado, agora)
        self._escrever(uniq, estado, agora)

    @staticmethod
    def _esquecer(estado: _Estado, entrada: Entrada) -> None:
        """Sem jogo ou no Modo Nativo, nada se escreve: o que ficou marcado se esquece."""
        estado.botoes = entrada.botoes
        estado.toques_de_botao.clear()
        estado.toques, estado.jogo, estado.ativo, estado.escrito = (0, 0), (0, 0), False, None

    def _toques_de(self, entrada: Entrada, estado: _Estado, agora: float) -> Par:
        ajuste = self._ajuste
        nivel_esq = nivel_dir = 0.0
        if ajuste.analogicos != ANALOGICO_DESLIGADO:
            nivel_esq = self._analogico(estado, "l", entrada.lx, entrada.ly, agora)
            nivel_dir = self._analogico(estado, "r", entrada.rx, entrada.ry, agora)
        if ajuste.gatilhos and not self._l.gatilho_do_jogo(entrada.uniq):
            nivel_esq = max(nivel_esq, _nivel_do_gatilho(entrada.l2))
            nivel_dir = max(nivel_dir, _nivel_do_gatilho(entrada.r2))
        if ajuste.chacoalhar:
            giro = _nivel_do_giro(entrada.giro)
            nivel_esq, nivel_dir = max(nivel_esq, giro), max(nivel_dir, giro)
        base = round(255 * ajuste.forca / 100)
        esq, dir_ = round(base * nivel_esq), round(base * nivel_dir)
        for lado in self._toques_de_botao(entrada, estado, agora):
            esq, dir_ = (max(esq, base), dir_) if lado == ESQUERDO else (esq, max(dir_, base))
        if not (esq or dir_):
            return (0, 0)
        mult_fraco, mult_forte = self._l.forca(entrada.uniq)
        return (min(255, round(esq * mult_forte)), min(255, round(dir_ * mult_fraco)))

    def _toques_de_botao(self, entrada: Entrada, estado: _Estado, agora: float) -> list[str]:
        novos = entrada.botoes - estado.botoes
        estado.botoes = entrada.botoes
        if self._ajuste.botoes:
            for botao in sorted(novos):
                lado = BOTOES_DO_LADO.get(botao)
                if lado is None or not self._teto.cabe(entrada.uniq, agora):
                    continue
                self._teto.gastar(entrada.uniq, agora)
                estado.toques_de_botao.append((agora + TOQUE_DO_BOTAO_S, lado))
                self.toques_dados += 1
        estado.toques_de_botao = [t for t in estado.toques_de_botao if t[0] > agora]
        return [lado for _, lado in estado.toques_de_botao]

    def _analogico(self, estado: _Estado, lado: str, x: int, y: int, agora: float) -> float:
        desvio = min(1.0, math.hypot((x - 128) / 127.0, (y - 128) / 127.0))
        nivel = 0.0
        if desvio >= ZONA_MORTA_DO_ANALOGICO:
            nivel = (desvio - ZONA_MORTA_DO_ANALOGICO) / (1.0 - ZONA_MORTA_DO_ANALOGICO)
        if self._ajuste.analogicos == ANALOGICO_POSICAO:
            return nivel
        ref = estado.ref.get(lado)
        if ref is None:
            estado.ref[lado] = (x, y)
        elif max(abs(x - ref[0]), abs(y - ref[1])) >= MOVIMENTO_MINIMO:
            estado.ref[lado] = (x, y)
            estado.mexeu[lado] = agora
        parado_ha = agora - estado.mexeu.get(lado, float("-inf"))
        return nivel if parado_ha < CALA_PARADO_S else 0.0

    # -- o par que chega aos motores -----------------------------------------------------

    def _juntar(self, estado: _Estado) -> ParDoRumble:
        """O par do rumble (fraco, forte): o jogo e os toques, pela mistura do perfil."""
        forte_t, fraco_t = estado.toques
        jogo_fraco, jogo_forte = estado.jogo
        ajuste = self._ajuste
        if ajuste.modo == MODO_SO_TOQUES:
            return (fraco_t, forte_t)
        if ajuste.mistura == MISTURA_SOMAR:
            return (min(255, jogo_fraco + fraco_t), min(255, jogo_forte + forte_t))
        return (max(jogo_fraco, fraco_t), max(jogo_forte, forte_t))

    def _escrever(self, uniq: str, estado: _Estado, agora: float) -> None:
        alvo = self._juntar(estado)
        if alvo == (estado.escrito or (0, 0)):
            estado.ativo = estado.toques != (0, 0)
            return
        calando = estado.toques == (0, 0)
        if not calando and agora - estado.escrito_em < ENTRE_ESCRITAS_S:
            return
        self._l.motores(uniq, *alvo)
        estado.escrito, estado.escrito_em = alvo, agora
        estado.ativo = not calando
        self.escritas += 1
        self._l.dizer(uniq, estado.jogo, alvo, _lados(estado.jogo), estado.toques)

    def misturar_o_jogo(
        self, uniq: str, jogo: ParDoRumble, *, pelo_audio: bool = False
    ) -> Mistura | None:
        """O pedido do jogo, já com a força, junto aos toques de agora; ``None`` = não mexe.

        Chamada pelo ``apply_game_rumble``. A háptica por áudio fica como veio: os motores
        calados e os toques sem escrever no canal dela.
        """
        with self._trava:
            estado = self._por_uniq.setdefault(uniq, _Estado())
            if pelo_audio or not self._ajuste.liga or not self._l.pode_falar(uniq):
                estado.jogo = jogo if not pelo_audio else (0, 0)
                return None
            estado.jogo = jogo
            alvo = self._juntar(estado)
            estado.escrito, estado.escrito_em = alvo, float("-inf")
            estado.ativo = estado.toques != (0, 0)
            return Mistura(alvo, _lados(jogo), estado.toques)

    def soltar_tudo(self, agora: float) -> None:
        """O serviço parou: o que os toques seguravam nos motores volta a zero."""
        with self._trava:
            for uniq, estado in list(self._por_uniq.items()):
                if estado.ativo and self._l.pode_falar(uniq):
                    self._l.motores(uniq, 0, 0)
                    self.escritas += 1
            self._por_uniq.clear()


def _lados(par: ParDoRumble) -> Par:
    """O par do rumble ``(fraco, forte)`` como ``(esquerdo, direito)``."""
    return (par[1], par[0])


def _nivel_do_gatilho(valor: int) -> float:
    return max(0.0, min(1.0, (valor - LIMIAR_DO_GATILHO) / (255 - LIMIAR_DO_GATILHO)))


def _nivel_do_giro(giro: float) -> float:
    return max(0.0, min(1.0, (giro - LIMIAR_DO_GIRO) / (GIRO_CHEIO - LIMIAR_DO_GIRO)))


def _giro_de(leitor: Any) -> float:
    foto = getattr(leitor, "snapshot", None)
    if not callable(foto):
        return 0.0
    try:
        eixos = foto()
        return math.sqrt(sum(float(getattr(eixos, e, 0.0)) ** 2 for e in "xyz"))
    except Exception:
        return 0.0


def entradas_do_daemon(daemon: Any) -> list[Entrada]:
    """O que cada controle da mesa faz: o primário pelo último estado, os outros pelo leitor."""
    entradas: dict[str, Entrada] = {}
    primario = getattr(getattr(daemon, "controller", None), "primary_uniq", None)
    estado = getattr(daemon, "_last_state", None)
    if isinstance(primario, str) and primario and estado is not None:
        entradas[primario] = Entrada(
            primario,
            frozenset(getattr(estado, "buttons_pressed", ()) or ()),
            _byte(getattr(estado, "raw_lx", 128)), _byte(getattr(estado, "raw_ly", 128)),
            _byte(getattr(estado, "raw_rx", 128)), _byte(getattr(estado, "raw_ry", 128)),
            _byte(getattr(estado, "l2_raw", 0)), _byte(getattr(estado, "r2_raw", 0)),
            _giro_de(getattr(daemon, "_motion_reader", None)),
        )
    jogadores = getattr(getattr(daemon, "_coop_manager", None), "_players", None)
    if isinstance(jogadores, dict):
        for mac, jogador in list(jogadores.items()):
            if not isinstance(mac, str) or mac in entradas:
                continue
            try:
                foto = jogador.reader.snapshot()
            except Exception:
                continue
            entradas[mac] = Entrada(
                mac, frozenset(getattr(foto, "buttons_pressed", ()) or ()),
                _byte(getattr(foto, "lx", 128)), _byte(getattr(foto, "ly", 128)),
                _byte(getattr(foto, "rx", 128)), _byte(getattr(foto, "ry", 128)),
                _byte(getattr(foto, "l2_raw", 0)), _byte(getattr(foto, "r2_raw", 0)),
                _giro_de(getattr(jogador, "motion_reader", None)),
            )
    return list(entradas.values())


def _byte(valor: Any) -> int:
    try:
        return max(0, min(255, int(valor)))
    except (TypeError, ValueError):
        return 0


def meus_toques_de_producao(daemon: Any) -> MeusToques:
    """Os meus toques ligados ao serviço vivo: o backend escreve, o daemon responde às guardas."""
    from hefesto_dualsense4unix.daemon.lifecycle import o_hefesto_fala_no_modo
    from hefesto_dualsense4unix.daemon.subsystems import gamepad
    from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import (
        CANAL_GATILHO,
        JANELA_DO_JOGO_S,
        controles_do_daemon,
        decidir,
        estado_do_controle,
        ha_jogo,
    )
    from hefesto_dualsense4unix.daemon.subsystems.vibracao_do_jogo import dizer_a_vibracao

    controller = getattr(daemon, "controller", None)

    def estado_de(uniq: str) -> Any:
        for controle in controles_do_daemon(daemon):
            if controle.uniq == uniq:
                return estado_do_controle(controle, ha_jogo(daemon))
        return None

    def motores(uniq: str, fraco: int, forte: int) -> object:
        escrever = getattr(controller, "set_rumble_for", None)
        return escrever(uniq, fraco, forte) if callable(escrever) else False

    def pode_falar(uniq: str) -> bool:
        estado = estado_de(uniq)
        return estado is not None and estado.ha_jogo and o_hefesto_fala_no_modo(estado.modo)

    def haptica_do_jogo(uniq: str) -> bool:
        estado = estado_de(uniq)
        idade = None if estado is None else estado.visto_ha_s.get("audio_do_jogo")
        return idade is not None and idade < JANELA_DO_JOGO_S

    def gatilho_do_jogo(uniq: str) -> bool:
        estado = estado_de(uniq)
        return estado is not None and not decidir(CANAL_GATILHO, estado)

    def dizer(
        uniq: str, pedido: ParDoRumble, efetivo: ParDoRumble, jogo: Par, toques: Par
    ) -> object:
        dizer_a_vibracao(daemon, uniq, pedido, efetivo, jogo=jogo, toques=toques)
        return None

    def forca(uniq: str) -> tuple[float, float]:
        import time

        try:
            return gamepad._mults_por_motor(daemon, time.monotonic(), uniq)
        except Exception:
            return (1.0, 1.0)

    return MeusToques(Ligacoes(
        motores=motores,
        pode_falar=pode_falar,
        haptica_do_jogo=haptica_do_jogo,
        gatilho_do_jogo=gatilho_do_jogo,
        dizer=dizer,
        forca=forca,
    ))


__all__ = [
    "Ajuste",
    "Entrada",
    "Ligacoes",
    "MeusToques",
    "Mistura",
    "ajuste_do_perfil",
    "entradas_do_daemon",
    "meus_toques_de_producao",
]
