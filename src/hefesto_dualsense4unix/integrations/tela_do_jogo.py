"""A tela do jogo em cinco números: o dano, o clarão, o escuro, o tremor e a saturação.

Cada quadro da fonte (o portal de captura) vira uma grade de 32 por 18 cores médias, e da grade e
da anterior saem os cinco sinais de ``jogo.tela``, de 0 a 1; nenhum pixel sai daqui (uma região da
receita publica só a fração da cor declarada). Sem assinante a fonte não abre; sem fonte, ou com
a fonte caída, o tópico publica ``None`` (ausente), nunca zero, e tenta de novo. A escolha
cancelada ou esgotada só se pede com assinatura nova, e só o cancelamento apaga a ficha
(``escolher_a_tela``, no install). A fonte não acorda o portal antes da sessão gráfica nem reabre
com a tela escolhida desligada: o portal consome a ficha no ``SelectSources``.
"""
from __future__ import annotations

import contextlib
import math
import os
import re
import socket
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from operator import sub
from pathlib import Path
from typing import Any, Protocol

from hefesto_dualsense4unix.integrations.barramento_do_sistema import sessao_ainda_nao_subiu
from hefesto_dualsense4unix.utils.logging_config import get_logger

GRADE_X = 32
GRADE_Y = 18
HZ_DA_TELA = 5
TOPICO_DA_TELA = "jogo.tela"
LARGURA_DA_FONTE = 64
ALTURA_DA_FONTE = 36
PRAZO_DO_DBUS_S = 5.0
PRAZO_DA_ESCOLHA_S = 120.0
PRAZO_DO_QUADRO_S = 0.5
_PORTAL = "org.freedesktop.portal.Desktop"
_CAMINHO_DO_PORTAL = "/org/freedesktop/portal/desktop"
_SCREENCAST = "org.freedesktop.portal.ScreenCast"
_PEDIDO = "org.freedesktop.portal.Request"
_SEM_A_INTERFACE = frozenset({"org.freedesktop.DBus.Error.UnknownMethod",
                              "org.freedesktop.DBus.Error.UnknownInterface"})
_CONSERTO_DO_PORTAL = ("o portal subiu sem a captura da tela; o conserto é"
                       " systemctl --user restart xdg-desktop-portal")
_TELA_DESLIGADA = "a tela escolhida está desligada"
_ARMAZEM = "org.freedesktop.impl.portal.PermissionStore"
_CAMINHO_DO_ARMAZEM = "/org/freedesktop/impl/portal/PermissionStore"
_TABELA_DA_TELA = "screencast"
_FICHA_PERDIDA = "org.freedesktop.portal.Error.NotFound"
RAIZ_DRM = Path("/sys/class/drm")
_SEM_TELA = "Writeback-"
SINAIS = ("dano", "flash", "escuro", "tremor", "saturacao")
REGIOES_POR_RECEITA = 8
AMOSTRAS_DA_REGIAO = 64
ALCANCE_DO_TREMOR = 2
GANHO_DO_DANO = 3.0
GANHO_DO_FLASH = 2.0
NOME_DA_REGIAO = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
CANAIS: Mapping[str, tuple[int, int, int, int]] = {
    "BGRx": (2, 1, 0, 4),
    "BGRA": (2, 1, 0, 4),
    "RGBx": (0, 1, 2, 4),
    "RGBA": (0, 1, 2, 4),
    "RGB": (0, 1, 2, 3),
    "BGR": (2, 1, 0, 3),
}

Cor = tuple[float, float, float]
Grade = tuple[Cor, ...]

logger = get_logger(__name__)


class TelaRecusadaError(Exception):
    """A receita ou o quadro fora da forma; ``frase`` diz o porquê."""

    def __init__(self, frase: str) -> None:
        super().__init__(frase)
        self.frase = frase


class EscolhaCanceladaError(RuntimeError):
    """A pessoa cancelou a janela de escolha (o código 1 do ``Response``): é a única recusa que
    apaga a ficha guardada. Só assinatura nova pede de novo."""


class EscolhaSemRespostaError(EscolhaCanceladaError):
    """O prazo da escolha esgotou sem resposta: a pessoa não recusou nada, e a ficha guardada
    fica. Só assinatura nova pede de novo, para a espera não virar laço de janelas."""


class TelaDesligadaError(RuntimeError):
    """A saída que a pessoa escolheu está desligada: a fonte espera e não pergunta ao portal, que
    consumiria a ficha guardada sem ter onde gravar outra."""


@dataclass(frozen=True)
class Quadro:
    """Um quadro cru: ``passo`` bytes por linha, no formato de ``CANAIS``."""

    largura: int
    altura: int
    passo: int
    formato: str
    dados: bytes

    def __post_init__(self) -> None:
        if self.formato not in CANAIS:
            raise TelaRecusadaError(f"O formato «{self.formato}» não é um dos conhecidos.")
        bpp = CANAIS[self.formato][3]
        if self.largura < 1 or self.altura < 1 or self.passo < self.largura * bpp:
            raise TelaRecusadaError("O quadro não tem a forma que declara.")
        if len(self.dados) < self.passo * (self.altura - 1) + self.largura * bpp:
            raise TelaRecusadaError("O quadro veio menor do que declara.")

    def cor(self, x: int, y: int) -> Cor:
        r, g, b, bpp = CANAIS[self.formato]
        i = y * self.passo + x * bpp
        d = self.dados
        return d[i + r] / 255.0, d[i + g] / 255.0, d[i + b] / 255.0


def reduzir(quadro: Quadro) -> Grade:
    """A grade 32 por 18, por linhas: em cada célula, a média de quatro amostras espalhadas."""
    r, g, b, bpp = CANAIS[quadro.formato]
    d = quadro.dados
    colunas = [[min(quadro.largura - 1, int((gx + f) * quadro.largura / GRADE_X)) * bpp
                for f in (0.25, 0.75)] for gx in range(GRADE_X)]
    celulas: list[Cor] = []
    for gy in range(GRADE_Y):
        linhas = [min(quadro.altura - 1, int((gy + f) * quadro.altura / GRADE_Y)) * quadro.passo
                  for f in (0.25, 0.75)]
        y0, y1 = linhas
        for x0, x1 in colunas:
            a, c, e, f = y0 + x0, y0 + x1, y1 + x0, y1 + x1
            celulas.append(((d[a + r] + d[c + r] + d[e + r] + d[f + r]) / 1020,
                            (d[a + g] + d[c + g] + d[e + g] + d[f + g]) / 1020,
                            (d[a + b] + d[c + b] + d[e + b] + d[f + b]) / 1020))
    return tuple(celulas)


def _luma(c: Cor) -> float:
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _vermelho(c: Cor) -> float:
    return max(0.0, c[0] - max(c[1], c[2]))


def _na_borda(i: int) -> bool:
    x, y = i % GRADE_X, i // GRADE_X
    return x < 3 or x >= GRADE_X - 3 or y < 2 or y >= GRADE_Y - 2


BORDA = tuple(i for i in range(GRADE_X * GRADE_Y) if _na_borda(i))


def _limitar(valor: float) -> float:
    return min(1.0, max(0.0, valor))


def deslocamento(antes: Sequence[float], agora: Sequence[float],
                 alcance: int = ALCANCE_DO_TREMOR) -> tuple[int, int]:
    """O deslocamento global (em células) que melhor leva ``antes`` a ``agora``; ``(0, 0)``
    quando nenhum outro é claramente melhor."""
    linhas = range(alcance, GRADE_Y - alcance)
    n = len(linhas) * (GRADE_X - 2 * alcance)
    trechos = [agora[y * GRADE_X + alcance:(y + 1) * GRADE_X - alcance] for y in linhas]

    def erro(dx: int, dy: int) -> float:
        soma = 0.0
        for y, trecho in zip(linhas, trechos, strict=True):
            inicio = (y - dy) * GRADE_X + alcance - dx
            soma += sum(map(abs, map(sub, trecho, antes[inicio:inicio + len(trecho)])))
        return soma / n

    parado = erro(0, 0)
    melhor, onde = parado, (0, 0)
    for dy in range(-alcance, alcance + 1):
        for dx in range(-alcance, alcance + 1):
            if (dx, dy) != (0, 0) and (e := erro(dx, dy)) < melhor:
                melhor, onde = e, (dx, dy)
    if parado < 0.02 or melhor > parado * 0.5:
        return 0, 0
    return onde


def sinais(antes: Grade | None, agora: Grade) -> dict[str, float]:
    """Os cinco sinais, de 0 a 1. Sem quadro anterior, o que depende de mudança é 0."""
    luma = [_luma(c) for c in agora]
    media = sum(luma) / len(luma)
    saturacao = sum((alto - min(c)) / alto if (alto := max(c)) > 0 else 0.0
                    for c in agora) / len(agora)
    borda = BORDA if len(agora) == GRADE_X * GRADE_Y else [
        i for i in range(len(agora)) if _na_borda(i)]
    vermelho = sum(_vermelho(agora[i]) for i in borda) / len(borda)
    dano = flash = tremor = 0.0
    if antes is not None:
        luma_antes = [_luma(c) for c in antes]
        flash = _limitar(GANHO_DO_FLASH * (media - sum(luma_antes) / len(luma_antes)))
        vermelho_antes = sum(_vermelho(antes[i]) for i in borda) / len(borda)
        dano = _limitar(GANHO_DO_DANO * (vermelho - vermelho_antes))
        dx, dy = deslocamento(luma_antes, luma)
        tremor = _limitar(math.hypot(dx, dy) / math.hypot(ALCANCE_DO_TREMOR, ALCANCE_DO_TREMOR))
    return {"dano": dano, "flash": flash, "escuro": _limitar(1.0 - media),
            "tremor": tremor, "saturacao": _limitar(saturacao)}


@dataclass(frozen=True)
class Regiao:
    """Uma região da tela que a receita declara (frações da tela) e a cor que a enche."""

    nome: str
    x: float
    y: float
    largura: float
    altura: float
    cor: tuple[int, int, int]
    tolerancia: int = 48


def regioes_da_receita(lista: Sequence[Mapping[str, Any]]) -> tuple[Regiao, ...]:
    """Valida as regiões declaradas; recusa com :class:`TelaRecusadaError`."""
    if len(lista) > REGIOES_POR_RECEITA:
        raise TelaRecusadaError(f"A receita declara até {REGIOES_POR_RECEITA} regiões.")
    regioes: list[Regiao] = []
    for linha in lista:
        try:
            nome = str(linha["nome"])
            x, y = float(linha["x"]), float(linha["y"])
            largura, altura = float(linha["largura"]), float(linha["altura"])
            cor = tuple(int(v) for v in linha["cor"])
            tolerancia = int(linha.get("tolerancia", 48))
        except (KeyError, TypeError, ValueError) as exc:
            raise TelaRecusadaError("Uma região da receita não tem a forma declarada.") from exc
        if not NOME_DA_REGIAO.match(nome):
            raise TelaRecusadaError(f"O nome «{nome}» não serve para uma região.")
        if (len(cor) != 3 or any(not 0 <= v <= 255 for v in cor)
                or not 0 <= tolerancia <= 255):
            raise TelaRecusadaError(f"A cor de «{nome}» precisa de três valores de 0 a 255.")
        if (not all(math.isfinite(v) for v in (x, y, largura, altura))
                or min(x, y) < 0 or largura <= 0 or altura <= 0
                or x + largura > 1 or y + altura > 1):
            raise TelaRecusadaError(f"«{nome}» sai da tela.")
        regioes.append(Regiao(nome, x, y, largura, altura, (cor[0], cor[1], cor[2]), tolerancia))
    if len({r.nome for r in regioes}) != len(regioes):
        raise TelaRecusadaError("A receita repete o nome de uma região.")
    return tuple(regioes)


def fracao(quadro: Quadro, regiao: Regiao, amostras: int = AMOSTRAS_DA_REGIAO) -> float:
    """A fração de 0 a 1 da linha do meio da região que tem a cor declarada."""
    y = min(quadro.altura - 1, int((regiao.y + regiao.altura / 2) * quadro.altura))
    alvo = [v / 255.0 for v in regiao.cor]
    limite = regiao.tolerancia / 255.0
    cheias = 0
    for i in range(amostras):
        x = min(quadro.largura - 1,
                int((regiao.x + regiao.largura * (i + 0.5) / amostras) * quadro.largura))
        if all(abs(a - b) <= limite for a, b in zip(quadro.cor(x, y), alvo, strict=True)):
            cheias += 1
    return cheias / amostras


class TelaDoJogo:
    """Guarda a grade anterior e transforma cada quadro na carga de ``jogo.tela``."""

    def __init__(self, regioes: Sequence[Regiao] = (),
                 relogio: Callable[[], float] = time.monotonic) -> None:
        self.regioes = tuple(regioes)
        self._relogio = relogio
        self._antes: Grade | None = None

    def medir(self, quadro: Quadro) -> dict[str, Any]:
        grade = reduzir(quadro)
        carga: dict[str, Any] = {"t": self._relogio(), **sinais(self._antes, grade)}
        self._antes = grade
        if self.regioes:
            carga["regioes"] = {r.nome: fracao(quadro, r) for r in self.regioes}
        return carga

    def ausente(self) -> dict[str, Any]:
        self._antes = None
        carga: dict[str, Any] = {"t": self._relogio(), **dict.fromkeys(SINAIS)}
        if self.regioes:
            carga["regioes"] = {r.nome: None for r in self.regioes}
        return carga


class FonteDaTela(Protocol):
    """A fonte dos quadros (o portal de captura). ``abrir`` devolve se abriu; ``quadro``
    devolve ``None`` quando a fonte caiu; ``interromper``, de outro fio, solta a espera em voo."""

    def abrir(self) -> bool: ...

    def quadro(self) -> Quadro | None: ...

    def fechar(self) -> None: ...

    def interromper(self) -> None: ...


class FonteAusente:
    """A fonte do modo de mentira: nunca abre, e o tópico fica ausente."""

    def abrir(self) -> bool:
        return False

    def quadro(self) -> Quadro | None:
        return None

    def interromper(self) -> None:
        return None

    def fechar(self) -> None:
        return None


def _caminho_do_pedido(nome_unico: str, ficha: str) -> str:
    return f"{_CAMINHO_DO_PORTAL}/request/{nome_unico.lstrip(':').replace('.', '_')}/{ficha}"


def _aceita(resposta: Any, pedido: str) -> Any:
    """A resposta do barramento, ou :class:`RuntimeError` diante de um erro: o portal sem a
    interface ``ScreenCast`` recusa na hora, e nenhum ``Response`` sai depois de uma recusa. O
    motivo do portal sem a interface diz o conserto; reiniciar o portal é de quem usa, porque
    cortaria o compartilhamento de tela em curso de outro programa."""
    from jeepney import HeaderFields, MessageType

    if resposta.header.message_type == MessageType.error:
        motivo = resposta.body[0] if resposta.body else ""
        if resposta.header.fields.get(HeaderFields.error_name) in _SEM_A_INTERFACE:
            motivo = f"{motivo}; {_CONSERTO_DO_PORTAL}"
        raise RuntimeError(f"o portal recusou {pedido}: {motivo}")
    return resposta


def conectores() -> dict[str, bool]:
    """As saídas de vídeo da máquina (``HDMI-A-1``, ``DP-2``…) e se cada uma está ligada, lidas de
    ``RAIZ_DRM/card*-<saída>/status``. Só ``disconnected`` é desligada: ``unknown`` é um conector
    sem detecção de plugue, e a dúvida não pode travar a captura. O ``Writeback`` não é tela (a
    placa grava nele, ninguém o vê) e fica de fora. Vazio quando o sistema não diz (sem DRM, ou
    nada legível)."""
    saidas: dict[str, bool] = {}
    try:
        pastas = sorted(RAIZ_DRM.glob("card*-*"))
    except OSError:
        return saidas
    for pasta in pastas:
        estado = ""
        with contextlib.suppress(OSError):
            estado = (pasta / "status").read_text(encoding="utf-8").strip()
        if not estado:
            continue
        nome = pasta.name.split("-", 1)[1]
        if nome.startswith(_SEM_TELA):
            continue
        saidas[nome] = saidas.get(nome, False) or estado != "disconnected"
    return saidas


def _textos(valor: Any) -> Iterator[str]:
    """Todo texto de um valor do barramento, em qualquer fundura: a ficha do portal guarda os dados
    do compositor num formato que é dele, e o nome da saída é achado pelo que ele é."""
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, Mapping):
        for chave, item in valor.items():
            yield from _textos(chave)
            yield from _textos(item)
    elif isinstance(valor, tuple | list):
        for item in valor:
            yield from _textos(item)


class FonteDoPortal:
    """O portal ``ScreenCast`` pelo PipeWire: a primeira abertura pede a escolha da tela ao
    sistema, e a ficha de volta guardada em ``guarda`` reabre sem pedir de novo. O quadro chega
    reduzido a ``LARGURA_DA_FONTE`` por ``ALTURA_DA_FONTE`` pelo GStreamer, sem ``pipewiresrc``
    a fonte não abre."""

    def __init__(self, guarda: Path) -> None:
        self.guarda = guarda
        self._conexao: Any = None
        self._sessao = ""
        self._tubo: Any = None
        self._ralo: Any = None
        self._serie = 0
        self._interrompida = False

    def _ficha(self) -> str:
        self._serie += 1
        return f"hefesto{os.getpid()}_{self._serie}"

    def _pedir(self, metodo: str, assinatura: str, corpo: tuple[Any, ...],
               opcoes: dict[str, tuple[str, Any]]) -> dict[str, Any]:
        from jeepney import DBusAddress, MatchRule, new_method_call
        from jeepney.bus_messages import message_bus

        ficha = self._ficha()
        regra = MatchRule(type="signal", interface=_PEDIDO, member="Response",
                          path=_caminho_do_pedido(self._conexao.unique_name, ficha))
        _aceita(self._conexao.send_and_get_reply(message_bus.AddMatch(regra),
                                                 timeout=PRAZO_DO_DBUS_S), "AddMatch")
        endereco = DBusAddress(_CAMINHO_DO_PORTAL, bus_name=_PORTAL, interface=_SCREENCAST)
        opcoes = {**opcoes, "handle_token": ("s", ficha)}
        with self._conexao.filter(regra) as fila:
            _aceita(self._conexao.send_and_get_reply(
                new_method_call(endereco, metodo, assinatura, (*corpo, opcoes)),
                timeout=PRAZO_DO_DBUS_S), metodo)
            try:
                sinal = self._conexao.recv_until_filtered(fila, timeout=PRAZO_DA_ESCOLHA_S)
            except TimeoutError as erro:
                raise EscolhaSemRespostaError(
                    f"o portal não respondeu à escolha da tela em {PRAZO_DA_ESCOLHA_S:.0f} s"
                    f" ({metodo}); a ficha guardada fica"
                ) from erro
        codigo, resultados = sinal.body
        if codigo == 1:
            raise EscolhaCanceladaError(f"a pessoa cancelou {metodo}")
        if codigo != 0:
            raise RuntimeError(f"o portal respondeu {codigo} a {metodo}")
        return {nome: valor for nome, (_tipo, valor) in resultados.items()}

    def _ficha_guardada(self) -> str | None:
        try:
            return self.guarda.read_text(encoding="utf-8").strip() or None
        except OSError:
            return None

    def _guardar(self, ficha: object) -> None:
        if isinstance(ficha, str) and ficha:
            with contextlib.suppress(OSError):
                self.guarda.parent.mkdir(parents=True, exist_ok=True)
                self.guarda.write_text(ficha, encoding="utf-8")

    def _esquecer(self) -> None:
        with contextlib.suppress(OSError):
            self.guarda.unlink(missing_ok=True)

    def _ler_a_ficha(self, ficha: str) -> tuple[bool, Any]:
        """O ``Lookup`` da ficha no ``PermissionStore``, que não consome nada. Devolve se o portal
        ainda guarda a ficha e os dados da entrada; ``(True, None)`` quando a pergunta não teve
        resposta legível (o armazém fora do ar, o prazo): a ficha vale até o portal dizer o fim."""
        from jeepney import DBusAddress, HeaderFields, MessageType, new_method_call

        endereco = DBusAddress(_CAMINHO_DO_ARMAZEM, bus_name=_ARMAZEM, interface=_ARMAZEM)
        try:
            resposta = self._conexao.send_and_get_reply(
                new_method_call(endereco, "Lookup", "ss", (_TABELA_DA_TELA, ficha)),
                timeout=PRAZO_DO_DBUS_S)
        except (OSError, TimeoutError):
            return True, None
        if resposta.header.message_type == MessageType.error:
            texto = str(resposta.body[0]) if resposta.body else ""
            perdida = (resposta.header.fields.get(HeaderFields.error_name) == _FICHA_PERDIDA
                       or texto.startswith("No entry"))
            return (not perdida), None
        corpo = resposta.body
        return True, corpo[1] if len(corpo) > 1 else None

    def _conferir_a_tela(self, ficha: str | None, saidas: Mapping[str, bool]) -> str | None:
        """Devolve a ficha a levar ao portal, ou levanta :class:`TelaDesligadaError` se a saída
        escolhida está desligada. A ficha que o portal já não tem sai do disco, e a escolha volta a
        ser pedida, uma vez. A saída vem dos dados da ficha; sem dado legível, vale qualquer saída
        ligada."""
        saida = None
        if ficha is not None:
            existe, dados = self._ler_a_ficha(ficha)
            if not existe:
                logger.info("tela_do_jogo_escolha_perdida",
                            motivo="a escolha da tela se perdeu no portal")
                self._esquecer()
                ficha = None
            else:
                saida = next((t for t in _textos(dados) if t in saidas), None)
        if saidas and not (saidas[saida] if saida is not None else any(saidas.values())):
            raise TelaDesligadaError(_TELA_DESLIGADA)
        return ficha

    def abrir(self) -> bool:
        try:
            import gi

            gi.require_version("Gst", "1.0")
            from gi.repository import Gst
            from jeepney import DBusAddress, new_method_call
            from jeepney.io.blocking import open_dbus_connection
        except (ImportError, ValueError):
            return False
        Gst.init(None)
        if Gst.ElementFactory.find("pipewiresrc") is None:
            return False
        if (saidas := conectores()) and not any(saidas.values()):
            raise TelaDesligadaError(_TELA_DESLIGADA)
        self._conexao = open_dbus_connection(bus="SESSION", enable_fds=True)
        try:
            if self._interrompida:
                raise InterruptedError("a fonte foi interrompida antes de abrir")
            if sessao_ainda_nao_subiu(self._conexao, _PORTAL, PRAZO_DO_DBUS_S):
                raise RuntimeError(
                    "a sessão gráfica ainda não subiu; o portal não se acorda antes da sessão")
            guardada = self._conferir_a_tela(self._ficha_guardada(), saidas)
            criada = self._pedir("CreateSession", "a{sv}", (),
                                 {"session_handle_token": ("s", self._ficha())})
            self._sessao = str(criada["session_handle"])
            escolha: dict[str, tuple[str, Any]] = {
                "types": ("u", 3), "multiple": ("b", False), "persist_mode": ("u", 2)}
            if guardada is not None:
                escolha["restore_token"] = ("s", guardada)
            try:
                self._pedir("SelectSources", "oa{sv}", (self._sessao,), escolha)
                comecou = self._pedir("Start", "osa{sv}", (self._sessao, ""), {})
                fluxos = comecou.get("streams") or []
                if not fluxos:
                    raise RuntimeError("o portal não entregou fluxo")
            except EscolhaSemRespostaError:
                raise
            except EscolhaCanceladaError:
                if guardada is not None and not self._interrompida:
                    self._esquecer()
                raise
            self._guardar(comecou.get("restore_token"))
            endereco = DBusAddress(_CAMINHO_DO_PORTAL, bus_name=_PORTAL, interface=_SCREENCAST)
            resposta = _aceita(self._conexao.send_and_get_reply(
                new_method_call(endereco, "OpenPipeWireRemote", "oa{sv}", (self._sessao, {})),
                timeout=PRAZO_DO_DBUS_S), "OpenPipeWireRemote")
            descritor = resposta.body[0].to_raw_fd()
            self._tubo = Gst.parse_launch(
                f"pipewiresrc fd={descritor} path={int(fluxos[0][0])} do-timestamp=true"
                f" ! videorate drop-only=true max-rate={HZ_DA_TELA}"
                " ! videoscale method=nearest-neighbour ! videoconvert"
                f" ! video/x-raw,format=BGRx,width={LARGURA_DA_FONTE},height={ALTURA_DA_FONTE}"
                " ! appsink name=ralo max-buffers=1 drop=true sync=false")
            self._ralo = self._tubo.get_by_name("ralo")
            self._tubo.set_state(Gst.State.PLAYING)
        except Exception:
            self.fechar()
            raise
        return True

    def quadro(self) -> Quadro | None:
        if self._ralo is None:
            return None
        from gi.repository import Gst

        if self._tubo.get_bus().pop_filtered(Gst.MessageType.ERROR) is not None:
            return None
        amostra = self._ralo.emit("try-pull-sample", int(PRAZO_DO_QUADRO_S * Gst.SECOND))
        if amostra is None:
            return None
        estrutura = amostra.get_caps().get_structure(0)
        largura, altura = estrutura.get_value("width"), estrutura.get_value("height")
        buffer = amostra.get_buffer()
        ok, mapa = buffer.map(Gst.MapFlags.READ)
        if not ok:
            return None
        try:
            dados = bytes(mapa.data)
        finally:
            buffer.unmap(mapa)
        return Quadro(largura, altura, len(dados) // altura, "BGRx", dados)

    def interromper(self) -> None:
        """Solta a espera do portal: o soquete desliga, e o pedido em voo cai em ``OSError``."""
        self._interrompida = True
        conexao = self._conexao
        if conexao is not None:
            with contextlib.suppress(OSError):
                conexao.sock.shutdown(socket.SHUT_RDWR)

    def fechar(self) -> None:
        tubo, self._tubo, self._ralo = self._tubo, None, None
        if tubo is not None:
            from gi.repository import Gst

            tubo.set_state(Gst.State.NULL)
        conexao, self._conexao = self._conexao, None
        if conexao is None:
            return
        from jeepney import DBusAddress, DBusErrorResponse, new_method_call

        with contextlib.suppress(OSError, TimeoutError, DBusErrorResponse):
            if self._sessao:
                sessao = DBusAddress(self._sessao, bus_name=_PORTAL,
                                     interface="org.freedesktop.portal.Session")
                conexao.send_and_get_reply(new_method_call(sessao, "Close"),
                                           timeout=PRAZO_DO_DBUS_S)
        self._sessao = ""
        with contextlib.suppress(OSError):
            conexao.close()


def fonte_do_sistema() -> FonteDaTela:
    """O portal, ou a fonte ausente no modo de mentira."""
    from hefesto_dualsense4unix.utils.xdg_paths import fake_mode_enabled, state_dir

    if fake_mode_enabled():
        return FonteAusente()
    return FonteDoPortal(state_dir() / "tela-do-portal.ficha")


def escolher_a_tela(fonte: FonteDaTela | None = None, *, tentativas: int = 3,
                    pausa_s: float = 3.0, dormir: Callable[[float], None] = time.sleep) -> int:
    """O passo do install: abre a escolha da tela uma vez, com a pessoa diante da tela, e fecha. A
    ficha de volta fica guardada, e com ficha que o portal aceita a fonte abre sem janela. Sai com
    0 (a escolha está guardada), 2 (sem portal ou sem sessão: fica para o primeiro jogo) ou 3
    (a janela foi cancelada ou ficou sem resposta). O portal que acaba de reiniciar tem
    ``tentativas`` chances, ``pausa_s`` uma da outra."""
    fonte = fonte if fonte is not None else fonte_do_sistema()
    motivo = "a fonte não abriu"
    for tentativa in range(max(1, tentativas)):
        try:
            if fonte.abrir():
                fonte.fechar()
                print("a escolha da tela está guardada")
                return 0
            break
        except EscolhaCanceladaError as erro:
            fonte.fechar()
            print(f"a escolha da tela não ficou: {erro}")
            return 3
        except (OSError, RuntimeError) as erro:
            fonte.fechar()
            motivo = str(erro) or motivo
            if tentativa + 1 < tentativas:
                dormir(pausa_s)
    print(f"a escolha da tela fica para o primeiro jogo ({motivo})")
    return 2


class Captura:
    """Abre a fonte só com assinante e publica um quadro por passo; a fonte que falta ou cai
    vira ``jogo.tela`` ausente uma vez, e a próxima tentativa sai depois de ``espera``. A escolha
    que não veio (cancelada ou esgotada) não volta sozinha: só com assinatura
    nova depois da recusa, ou depois de todos saírem. ``assinantes`` diz quantos existem agora
    (zero fecha a fonte) e ``nascidas`` quantas assinaturas já nasceram desde sempre: sair e
    entrar no mesmo passo não muda a primeira conta, e a segunda sobe."""

    def __init__(self, fonte: FonteDaTela, tela: TelaDoJogo, *,
                 publicar: Callable[[dict[str, Any]], None],
                 assinantes: Callable[[], int], nascidas: Callable[[], int],
                 espera: float = 2.0,
                 relogio: Callable[[], float] = time.monotonic) -> None:
        self.fonte = fonte
        self.tela = tela
        self._publicar = publicar
        self._assinantes = assinantes
        self._nascidas = nascidas
        self._espera = espera
        self._relogio = relogio
        self.aberta = False
        self._proxima = 0.0
        self._ausente_dito = False
        self._desligada_dita = False
        self._recusada_com: int | None = None
        self._parada = threading.Event()

    def parar(self) -> None:
        """A parada, de qualquer fio: o passo em voo cai e nenhum outro abre a fonte."""
        self._parada.set()
        self.fonte.interromper()

    def _cair(self, motivo: str, *, desligada: bool = False) -> None:
        if self.aberta:
            self.fonte.fechar()
        self.aberta = False
        self._proxima = self._relogio() + self._espera
        if self._parada.is_set():
            return
        if not self._ausente_dito:
            self._ausente_dito = True
            self._desligada_dita = desligada
            logger.info("tela_do_jogo_ausente", motivo=motivo)
            self._publicar(self.tela.ausente())
        elif desligada and not self._desligada_dita:
            self._desligada_dita = True
            logger.info("tela_do_jogo_ausente", motivo=motivo)

    def passo(self) -> None:
        assinantes = self._assinantes()
        if self._parada.is_set() or assinantes <= 0:
            if self.aberta:
                self.fonte.fechar()
                self.aberta = False
            self._ausente_dito = False
            self._desligada_dita = False
            self._recusada_com = None
            return
        if not self.aberta:
            if self._recusada_com is not None:
                if self._nascidas() <= self._recusada_com:
                    return
                self._recusada_com = None
            if self._relogio() < self._proxima:
                return
            motivo = "a fonte não abriu"
            desligada = False
            try:
                self.aberta = self.fonte.abrir()
            except EscolhaCanceladaError as erro:
                self.aberta = False
                self._recusada_com = self._nascidas()
                motivo = str(erro)
            except TelaDesligadaError as erro:
                self.aberta = False
                desligada = True
                motivo = str(erro)
            except (OSError, RuntimeError) as erro:
                self.aberta = False
                motivo = str(erro) or motivo
            if not self.aberta:
                self._cair(motivo, desligada=desligada)
                return
        motivo = "a fonte parou de entregar quadro"
        try:
            quadro = self.fonte.quadro()
        except (OSError, RuntimeError, TelaRecusadaError) as erro:
            quadro = None
            motivo = str(erro) or motivo
        if quadro is None:
            self._cair(motivo)
            return
        self._ausente_dito = False
        self._desligada_dita = False
        self._publicar(self.tela.medir(quadro))


__all__ = [
    "GRADE_X",
    "GRADE_Y",
    "HZ_DA_TELA",
    "RAIZ_DRM",
    "SINAIS",
    "TOPICO_DA_TELA",
    "Captura",
    "EscolhaCanceladaError",
    "EscolhaSemRespostaError",
    "FonteAusente",
    "FonteDaTela",
    "FonteDoPortal",
    "Quadro",
    "Regiao",
    "TelaDesligadaError",
    "TelaDoJogo",
    "TelaRecusadaError",
    "conectores",
    "deslocamento",
    "escolher_a_tela",
    "fonte_do_sistema",
    "fracao",
    "reduzir",
    "regioes_da_receita",
    "sinais",
]
