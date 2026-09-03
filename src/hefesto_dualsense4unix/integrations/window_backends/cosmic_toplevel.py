"""Backend de janela ativa para o COSMIC, falando `zcosmic_toplevel_info_v1`.

**POR QUE ESTE ARQUIVO EXISTE, e a frase que ele derruba.** O `doctor.sh` dizia,
desde que a seção nasceu:

    veredito: DEGRADADO — só XWayland: (…) apps Wayland nativos aparecem como
    'unknown'. Limitação do compositor (COSMIC exigiria zcosmic_toplevel_info_v1),
    não do hefesto.

A frase se desculpava nomeando o protocolo que resolveria — e **o compositor
dela EXPÕE esse protocolo**. Medido em 02/09/2026 na sessão COSMIC dela, com
`wayland-info`: entre os 58 globais publicados estão
``zcosmic_toplevel_info_v1`` (versão 3) e ``ext_foreign_toplevel_list_v1``
(versão 1). Não está lá o ``zwlr_foreign_toplevel_manager_v1``, que é o que o
`wlr_toplevel.py` procura. A limitação era do produto, não do compositor.

**POR QUE FALAR O PROTOCOLO NA MÃO, sem `pywayland`.** Não há binding de
Wayland na venv nem no `pyproject.toml`, e não há CLI de terceiro que fale o
protocolo do COSMIC (o `wlrctl`, que está instalado nesta máquina, fala o do
wlroots e por isso responde *"Foreign Toplevel Management interface not
found"*). O protocolo de fio do Wayland é pequeno o bastante para ser lido
direto: cabeçalho de 8 bytes (id do objeto, tamanho e opcode empacotados),
strings com prefixo de tamanho e enchimento para múltiplo de 4.

**ESTE CLIENTE NÃO CRIA SUPERFÍCIE NENHUMA.** Ele liga o `wl_registry` e o
``zcosmic_toplevel_info_v1``, e mais nada — não existe `wl_compositor`, não
existe `wl_surface`, logo **não há janela que possa nascer na tela dela**. Isso
é contrato, não descuido, e há teste que lê este arquivo procurando as
interfaces proibidas (`test_a_janela_ativa_do_cosmic.py`).

**POR QUE LIGAR NA VERSÃO 1 de uma interface que anuncia 3.** Na versão 1 o
``zcosmic_toplevel_info_v1`` emite os `toplevel` direto, e cada
``zcosmic_toplevel_handle_v1`` emite `title`, `app_id` e `state` por conta
própria: uma ligação, zero requisições depois dela, e é tudo o que a detecção
de janela precisa. Da versão 2 em diante o caminho passa a exigir o
``ext_foreign_toplevel_list_v1`` — outro global, outro objeto por janela e uma
requisição `get_cosmic_toplevel` para cada — em troca de nada que se use aqui.
Medido: ligado na versão 1, o cosmic-comp 0.1 desta máquina respondeu com as
cinco janelas abertas, uma delas com o estado `activated`.

**O QUE ELE VÊ E O QUE NÃO VÊ.** Vê `app_id` (que vira `wm_class`) e `title`.
**Não vê o PID**, logo não vê `exe_basename` — igual ao portal e ao wlrctl, e
declarado em `window_detect.BACKENDS_CEGOS_AO_PROCESSO`. Perfil que casa por
`process_name` continua sem casar por este caminho; quem cobre isso é o
`xlib`, e é por isso que o `_XlibComCosmicBackend` prefere o xlib sempre que
ele enxerga.

**A CONEXÃO É PERMANENTE, de propósito.** O `AutoSwitcher` lê a 2 Hz. Reabrir
o soquete e refazer o aperto de mão a cada tique custaria duas idas ao
compositor por leitura; em vez disso o soquete fica aberto e cada leitura só
esvazia o que chegou (o compositor **empurra** o `state` quando o foco muda).
Com nada para ler, uma leitura é um `recv` que devolve `EAGAIN`.
"""
from __future__ import annotations

import contextlib
import errno
import os
import socket
import struct
import time
from collections.abc import Callable, Iterator

from hefesto_dualsense4unix.integrations.window_backends.base import WindowInfo
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# --- o protocolo, em números ------------------------------------------------
# Opcodes nascem da ORDEM no XML (requisições e eventos numerados à parte).
# Fonte: pop-os/cosmic-protocols, `unstable/cosmic-toplevel-info-unstable-v1.xml`
# (interface versão 3) e o `wayland.xml` de `/usr/share/wayland`.

_WL_DISPLAY = 1
_WL_DISPLAY_SYNC = 0
_WL_DISPLAY_GET_REGISTRY = 1
_WL_DISPLAY_EV_ERROR = 0

_WL_REGISTRY = 2
_WL_REGISTRY_BIND = 0
_WL_REGISTRY_EV_GLOBAL = 0

_INTERFACE = "zcosmic_toplevel_info_v1"
#: A versão em que ligamos. Ver a explicação no cabeçalho — não é a maior.
_VERSAO_LIGADA = 1

#: `zcosmic_toplevel_info_v1`, eventos: toplevel=0, finished=1, done=2.
_INFO_EV_TOPLEVEL = 0
_INFO_EV_FINISHED = 1

#: `zcosmic_toplevel_handle_v1`, eventos na ordem do XML.
_TOP_EV_CLOSED = 0
_TOP_EV_TITLE = 2
_TOP_EV_APP_ID = 3
_TOP_EV_STATE = 8
#: e a única requisição dele.
_TOP_REQ_DESTROY = 0

#: `zcosmic_toplevel_handle_v1.state`: o valor que responde "esta é a de cima".
_ESTADO_ATIVADO = 2

# --- as folgas --------------------------------------------------------------
#: Segundos de paciência no aperto de mão (é a ÚNICA parte bloqueante).
_APERTO_DE_MAO_S = 2.0
#: Espera antes de tentar reconectar depois que o soquete morreu.
_ESPERA_PARA_RELIGAR_S = 5.0
#: Teto do que se lê num tique. O compositor empurra pouco; o teto existe para
#: que uma tempestade de eventos não segure o poll de 2 Hz.
_TETO_POR_TIQUE = 64 * 1024

# --- os motivos de leitura cega (JANELA-CEGA-01) ----------------------------
#: O compositor não publica o protocolo — desligado DE VEZ (não é COSMIC).
MOTIVO_SEM_PROTOCOLO = "cosmic_sem_protocolo"
#: Não há `WAYLAND_DISPLAY`/soquete para ligar.
MOTIVO_SEM_SOQUETE = "cosmic_sem_soquete"
#: O soquete caiu (compositor reiniciou, sessão trocada) e ainda estamos na
#: espera antes de religar.
MOTIVO_SEM_CONEXAO = "cosmic_sem_conexao"
#: Conectado, a lista chegou, e nenhuma janela se declara `activated`.
MOTIVO_NENHUMA_ATIVA = "cosmic_nenhuma_ativa"
#: O compositor devolveu `wl_display.error` — defeito nosso ou dele, e ele é
#: DITO em vez de virar um None mudo.
MOTIVO_ERRO_DO_PROTOCOLO = "cosmic_erro_do_protocolo"


def _enche(b: bytes) -> bytes:
    """Enche até o múltiplo de 4 que o fio exige."""
    return b + b"\x00" * ((-len(b)) % 4)


def _mensagem(objeto: int, opcode: int, corpo: bytes) -> bytes:
    """Monta o cabeçalho de 8 bytes na frente do corpo."""
    tamanho = 8 + len(corpo)
    return struct.pack("<II", objeto, (tamanho << 16) | opcode) + corpo


def _texto_no_fio(s: str) -> bytes:
    """Serializa uma string do jeito do Wayland: tamanho com o NUL, e enchimento."""
    bruto = s.encode("utf-8") + b"\x00"
    return struct.pack("<I", len(bruto)) + _enche(bruto)


def _le_texto(corpo: bytes, pos: int) -> tuple[str, int]:
    """Lê uma string a partir de `pos`; devolve o texto e a posição seguinte."""
    (n,) = struct.unpack_from("<I", corpo, pos)
    pos += 4
    texto = corpo[pos : pos + max(n - 1, 0)].decode("utf-8", "replace")
    return texto, pos + ((n + 3) & ~3)


def _le_vetor(corpo: bytes, pos: int) -> tuple[bytes, int]:
    """Lê um `array` a partir de `pos`; devolve os bytes e a posição seguinte."""
    (n,) = struct.unpack_from("<I", corpo, pos)
    pos += 4
    return corpo[pos : pos + n], pos + ((n + 3) & ~3)


def caminho_do_soquete() -> str | None:
    """Onde mora o soquete do compositor, ou ``None`` se não há sessão Wayland.

    `WAYLAND_DISPLAY` absoluto é usado como está (o protocolo permite); relativo
    pende de `XDG_RUNTIME_DIR`, e sem ele não há o que tentar.
    """
    tela = os.environ.get("WAYLAND_DISPLAY")
    if not tela:
        return None
    if tela.startswith("/"):
        return tela
    lar = os.environ.get("XDG_RUNTIME_DIR")
    if not lar:
        return None
    return os.path.join(lar, tela)


class _Janela:
    """Uma janela como o compositor a descreve. Sem PID — ele não manda."""

    __slots__ = ("app_id", "ativada", "titulo")

    def __init__(self) -> None:
        self.app_id: str = ""
        self.titulo: str = ""
        self.ativada: bool = False


class CosmicToplevelBackend:
    """Janela ativa via `zcosmic_toplevel_info_v1`, sem binário de terceiro.

    Ligar é preguiçoso: nada acontece no `__init__`, para que construir o
    backend num ambiente sem Wayland (CI, teste, sessão X11 pura) não custe
    soquete nenhum. A primeira leitura é a que abre a conexão.
    """

    backend_name: str = "cosmic"

    def __init__(self) -> None:
        self._soquete: socket.socket | None = None
        self._sobra: bytes = b""
        self._proximo_id: int = _WL_REGISTRY
        self._info: int = 0
        self._janelas: dict[int, _Janela] = {}
        self._desligado_de_vez: bool = False
        self._proxima_tentativa: float = 0.0
        self._anunciado: bool = False
        self.last_failure_reason: str | None = None

    # -- o que a cascata pergunta -------------------------------------------

    @property
    def available(self) -> bool:
        """Este backend ainda pode produzir leitura?

        ``False`` só depois de o compositor ter DITO que não publica o
        protocolo. Soquete caído não desliga o backend: o compositor volta e
        ele volta junto.
        """
        return not self._desligado_de_vez

    @property
    def protocol_unsupported(self) -> bool:
        """O compositor não publica ``zcosmic_toplevel_info_v1``?

        Distingue, no diagnóstico, *"não é COSMIC"* de *"é, e o soquete caiu"*.
        """
        return self._desligado_de_vez

    def get_active_window_info(self) -> WindowInfo | None:
        """A janela `activated` de agora, ou ``None`` com o motivo dito."""
        if self._desligado_de_vez:
            self.last_failure_reason = MOTIVO_SEM_PROTOCOLO
            return None

        if self._soquete is None and not self._ligar():
            return None

        if not self._esvaziar():
            return None

        for janela in self._janelas.values():
            if janela.ativada:
                self.last_failure_reason = None
                return WindowInfo(
                    wm_class=janela.app_id or "unknown",
                    pid=0,
                    app_id=janela.app_id,
                    title=janela.titulo,
                    exe_basename="",
                )

        self.last_failure_reason = MOTIVO_NENHUMA_ATIVA
        return None

    def fechar(self) -> None:
        """Larga o soquete. Existe para o teste e para quem quiser ser limpo."""
        self._largar_conexao()

    # -- a conexão ----------------------------------------------------------

    def _ligar(self) -> bool:
        """Aperto de mão completo: registry, ligação e a primeira lista.

        Esta é a única parte bloqueante, e ela tem teto (`_APERTO_DE_MAO_S`).
        Ela é bloqueante de propósito: a alternativa seria a primeira leitura
        devolver ``None`` mesmo com o compositor respondendo — um "não sei"
        falso, que é o defeito que esta casa mais persegue.
        """
        agora = time.monotonic()
        if agora < self._proxima_tentativa:
            self.last_failure_reason = MOTIVO_SEM_CONEXAO
            return False

        caminho = caminho_do_soquete()
        if not caminho:
            self.last_failure_reason = MOTIVO_SEM_SOQUETE
            self._proxima_tentativa = agora + _ESPERA_PARA_RELIGAR_S
            return False

        try:
            soquete = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            soquete.settimeout(_APERTO_DE_MAO_S)
            soquete.connect(caminho)
        except OSError as exc:
            logger.debug("cosmic_toplevel_conexao_recusada", err=str(exc))
            self.last_failure_reason = MOTIVO_SEM_CONEXAO
            self._proxima_tentativa = agora + _ESPERA_PARA_RELIGAR_S
            return False

        self._soquete = soquete
        self._sobra = b""
        self._proximo_id = _WL_REGISTRY
        self._info = 0
        self._janelas = {}

        try:
            globais = self._pedir_o_registro()
        except OSError as exc:
            logger.debug("cosmic_toplevel_registro_falhou", err=str(exc))
            self._largar_conexao()
            self.last_failure_reason = MOTIVO_SEM_CONEXAO
            return False

        if _INTERFACE not in globais:
            self._largar_conexao()
            self._desligado_de_vez = True
            self.last_failure_reason = MOTIVO_SEM_PROTOCOLO
            logger.info(
                "cosmic_toplevel_protocolo_ausente",
                hint=(
                    "o compositor não publica zcosmic_toplevel_info_v1 — "
                    "não é COSMIC, ou é uma versão sem o protocolo. Este "
                    "backend fica de fora; os outros da cascata seguem."
                ),
            )
            return False

        nome, versao_anunciada = globais[_INTERFACE]
        try:
            self._ligar_na_interface(nome)
        except OSError as exc:
            logger.debug("cosmic_toplevel_bind_falhou", err=str(exc))
            self._largar_conexao()
            self.last_failure_reason = MOTIVO_SEM_CONEXAO
            return False

        soquete.setblocking(False)
        if not self._anunciado:
            logger.info(
                "cosmic_toplevel_ligado",
                versao_anunciada=versao_anunciada,
                versao_ligada=_VERSAO_LIGADA,
                janelas=len(self._janelas),
                hint=(
                    "apps Wayland nativos passam a ser vistos pelo nome; o "
                    "PID continua invisível por este caminho (o xlib é quem "
                    "o resolve)."
                ),
            )
            self._anunciado = True
        return True

    def _pedir_o_registro(self) -> dict[str, tuple[int, int]]:
        """`get_registry` + `sync`, e lê até a volta do `sync`."""
        soquete = self._exigir_soquete()
        registro = self._novo_id()  # sempre 2, o primeiro que o cliente aloca
        soquete.sendall(
            _mensagem(_WL_DISPLAY, _WL_DISPLAY_GET_REGISTRY, struct.pack("<I", registro))
        )
        eco = self._novo_id()
        soquete.sendall(_mensagem(_WL_DISPLAY, _WL_DISPLAY_SYNC, struct.pack("<I", eco)))

        globais: dict[str, tuple[int, int]] = {}

        def anota(objeto: int, opcode: int, corpo: bytes) -> None:
            if objeto == registro and opcode == _WL_REGISTRY_EV_GLOBAL:
                (nome,) = struct.unpack_from("<I", corpo, 0)
                interface, pos = _le_texto(corpo, 4)
                (versao,) = struct.unpack_from("<I", corpo, pos)
                globais[interface] = (nome, versao)

        self._ler_ate(eco, anota)
        return globais

    def _ligar_na_interface(self, nome: int) -> None:
        """`bind` na versão 1 + `sync`, e lê a lista inicial de janelas."""
        soquete = self._exigir_soquete()
        self._info = self._novo_id()
        corpo = (
            struct.pack("<I", nome)
            + _texto_no_fio(_INTERFACE)
            + struct.pack("<II", _VERSAO_LIGADA, self._info)
        )
        soquete.sendall(_mensagem(_WL_REGISTRY, _WL_REGISTRY_BIND, corpo))
        eco = self._novo_id()
        soquete.sendall(_mensagem(_WL_DISPLAY, _WL_DISPLAY_SYNC, struct.pack("<I", eco)))
        self._ler_ate(eco, self._digerir)

    def _novo_id(self) -> int:
        """O próximo id do espaço do CLIENTE. O primeiro é 2, o `wl_registry`."""
        identidade = self._proximo_id
        self._proximo_id += 1
        return identidade

    def _exigir_soquete(self) -> socket.socket:
        """O soquete, ou um `OSError` que o chamador já sabe tratar."""
        if self._soquete is None:
            raise OSError(errno.ENOTCONN, "sem conexão com o compositor")
        return self._soquete

    # -- ler do fio ---------------------------------------------------------

    def _ler_ate(self, eco: int, trata: Callable[[int, int, bytes], None]) -> None:
        """Lê mensagens até o `wl_callback.done` de `eco`, ou até o teto de tempo.

        `wl_display.error` interrompe: o compositor não vai mandar o `done`
        depois de reclamar, e esperar por ele seria segurar o aperto de mão
        pelos dois segundos inteiros.
        """
        soquete = self._exigir_soquete()
        fim = time.monotonic() + _APERTO_DE_MAO_S
        while time.monotonic() < fim:
            dado = soquete.recv(_TETO_POR_TIQUE)
            if not dado:
                raise OSError(errno.EPIPE, "o compositor fechou o soquete")
            self._sobra += dado
            for objeto, opcode, corpo in self._destrinchar():
                if objeto == _WL_DISPLAY and opcode == _WL_DISPLAY_EV_ERROR:
                    self._reclamar(corpo)
                    return
                if objeto == eco:
                    return
                trata(objeto, opcode, corpo)
        raise OSError(errno.ETIMEDOUT, "o compositor não respondeu ao sync")

    def _esvaziar(self) -> bool:
        """Lê tudo o que já chegou, sem bloquear. ``False`` = a conexão morreu."""
        soquete = self._soquete
        if soquete is None:
            self.last_failure_reason = MOTIVO_SEM_CONEXAO
            return False
        lido = 0
        while lido < _TETO_POR_TIQUE:
            try:
                dado = soquete.recv(_TETO_POR_TIQUE - lido)
            except BlockingIOError:
                break
            except OSError as exc:
                logger.debug("cosmic_toplevel_leitura_falhou", err=str(exc))
                self._largar_conexao()
                self.last_failure_reason = MOTIVO_SEM_CONEXAO
                return False
            if not dado:
                logger.info(
                    "cosmic_toplevel_soquete_fechado",
                    hint="o compositor encerrou a conexão; religamos na próxima leitura.",
                )
                self._largar_conexao()
                self.last_failure_reason = MOTIVO_SEM_CONEXAO
                return False
            self._sobra += dado
            lido += len(dado)

        for objeto, opcode, corpo in self._destrinchar():
            if objeto == _WL_DISPLAY and opcode == _WL_DISPLAY_EV_ERROR:
                self._reclamar(corpo)
                self._largar_conexao()
                self.last_failure_reason = MOTIVO_ERRO_DO_PROTOCOLO
                return False
            self._digerir(objeto, opcode, corpo)
        return True

    def _destrinchar(self) -> Iterator[tuple[int, int, bytes]]:
        """Fatia `self._sobra` em mensagens inteiras; o resto fica para depois."""
        while len(self._sobra) >= 8:
            objeto, palavra = struct.unpack_from("<II", self._sobra, 0)
            tamanho = palavra >> 16
            if tamanho < 8 or len(self._sobra) < tamanho:
                return
            corpo = self._sobra[8:tamanho]
            self._sobra = self._sobra[tamanho:]
            yield objeto, palavra & 0xFFFF, corpo

    def _digerir(self, objeto: int, opcode: int, corpo: bytes) -> None:
        """Aplica um evento ao estado. Ignora o que não é nosso, de propósito.

        O que se ignora aqui não é descuido: `wl_display.delete_id`, os
        `wl_registry.global` que continuam chegando e os eventos de geometria e
        de área de trabalho da janela não mudam a resposta de "quem está em
        cima" — e cada `if` a mais é uma chance a mais de errar o opcode.
        """
        if objeto == self._info and self._info:
            if opcode == _INFO_EV_TOPLEVEL:
                (identidade,) = struct.unpack_from("<I", corpo, 0)
                self._janelas[identidade] = _Janela()
            elif opcode == _INFO_EV_FINISHED:
                # O compositor aposentou a interface; a lista que temos morreu
                # com ela e não haverá outra nesta conexão.
                self._janelas.clear()
                self._info = 0
            return

        janela = self._janelas.get(objeto)
        if janela is None:
            return
        if opcode == _TOP_EV_TITLE:
            janela.titulo, _ = _le_texto(corpo, 0)
        elif opcode == _TOP_EV_APP_ID:
            janela.app_id, _ = _le_texto(corpo, 0)
        elif opcode == _TOP_EV_STATE:
            vetor, _ = _le_vetor(corpo, 0)
            quantos = len(vetor) // 4
            estados = struct.unpack_from(f"<{quantos}I", vetor, 0) if quantos else ()
            janela.ativada = _ESTADO_ATIVADO in estados
        elif opcode == _TOP_EV_CLOSED:
            self._janelas.pop(objeto, None)
            self._destruir_janela(objeto)

    def _destruir_janela(self, objeto: int) -> None:
        """Devolve ao compositor o objeto da janela que fechou.

        Sem isto, cada janela que ela abre e fecha deixa um objeto vivo do
        lado do compositor — uma sessão longa é justamente onde o vazamento
        apareceria, e uma sessão longa é o caso normal deste daemon.
        """
        soquete = self._soquete
        if soquete is None:
            return
        try:
            soquete.sendall(_mensagem(objeto, _TOP_REQ_DESTROY, b""))
        except OSError as exc:
            logger.debug("cosmic_toplevel_destroy_falhou", err=str(exc))

    def _reclamar(self, corpo: bytes) -> None:
        """Escreve o `wl_display.error` no log, com o texto do compositor."""
        try:
            alvo, codigo = struct.unpack_from("<II", corpo, 0)
            texto, _ = _le_texto(corpo, 8)
        except struct.error:
            alvo, codigo, texto = 0, 0, "(ilegível)"
        logger.warning(
            "cosmic_toplevel_erro_do_protocolo",
            objeto=alvo,
            codigo=codigo,
            texto=texto,
        )

    def _largar_conexao(self) -> None:
        if self._soquete is not None:
            with contextlib.suppress(OSError):
                self._soquete.close()
        self._soquete = None
        self._sobra = b""
        self._info = 0
        self._janelas = {}
        self._proxima_tentativa = time.monotonic() + _ESPERA_PARA_RELIGAR_S


def sondar_o_compositor() -> dict[str, object]:
    """Uma leitura, do zero, para quem só quer o veredito (o `doctor.sh`).

    Existe para que o diagnóstico pergunte ao MESMO código que o daemon roda,
    em vez de reescrever o protocolo num `python3 -c` embutido no bash — que é
    como uma régua desta casa passa a medir outra coisa que não o produto.
    """
    backend = CosmicToplevelBackend()
    try:
        info = backend.get_active_window_info()
        return {
            "protocolo": backend.available,
            "motivo": backend.last_failure_reason,
            "janelas": len(backend._janelas),
            "wm_class": None if info is None else info.wm_class,
            "titulo": None if info is None else info.title,
        }
    finally:
        backend.fechar()


def _linha_para_o_doctor() -> str:
    """Uma linha, campos separados por `|`, para o bash consumir sem parser."""
    r = sondar_o_compositor()
    return "|".join(
        [
            "protocolo=sim" if r["protocolo"] else "protocolo=nao",
            f"janelas={r['janelas']}",
            f"wm_class={r['wm_class'] or ''}",
            f"motivo={r['motivo'] or ''}",
        ]
    )


if __name__ == "__main__":  # pragma: no cover - caminho de diagnóstico
    print(_linha_para_o_doctor())


__all__ = [
    "MOTIVO_ERRO_DO_PROTOCOLO",
    "MOTIVO_NENHUMA_ATIVA",
    "MOTIVO_SEM_CONEXAO",
    "MOTIVO_SEM_PROTOCOLO",
    "MOTIVO_SEM_SOQUETE",
    "CosmicToplevelBackend",
    "caminho_do_soquete",
    "sondar_o_compositor",
]
