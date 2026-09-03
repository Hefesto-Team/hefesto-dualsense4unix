"""JANELA-WAYLAND-CEGA-01: o COSMIC diz qual janela está na frente, e agora o produto pergunta.

**O QUE ESTA RÉGUA MEDE, e por que ela precisou de um compositor de mentira.**
O `doctor.sh` se desculpava: *"apps Wayland nativos aparecem como 'unknown'.
Limitação do compositor (COSMIC exigiria zcosmic_toplevel_info_v1), não do
hefesto."* A desculpa nomeava a cura, e o compositor dela **publica** esse
protocolo — medido com `wayland-info` em 02/09/2026: `zcosmic_toplevel_info_v1`
versão 3, entre 58 globais. A limitação era do produto.

Testar isso contra o compositor de verdade só funcionaria na máquina dela, e
uma régua que só passa numa máquina não é régua. Então estes testes sobem um
**compositor de mentira**: um soquete AF_UNIX que fala o protocolo de fio do
Wayland de verdade — cabeçalho de 8 bytes, strings com prefixo de tamanho — e
que obedece a um roteiro que o teste escreve. Com ele dá para mandar o foco
mudar e ver o backend seguir, que é a única prova de que a leitura vive no
TEMPO e não só no instante da chamada.

**ONDE ESTÁ A MORDIDA de cada teste:** cada um diz, no próprio docstring, o que
arrancar para vê-lo reprovar.
"""
from __future__ import annotations

import contextlib
import os
import socket
import struct
import threading
import time
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations.window_backends import cosmic_toplevel
from hefesto_dualsense4unix.integrations.window_backends.base import WindowInfo
from hefesto_dualsense4unix.integrations.window_backends.cosmic_toplevel import (
    MOTIVO_NENHUMA_ATIVA,
    MOTIVO_SEM_PROTOCOLO,
    MOTIVO_SEM_SOQUETE,
    CosmicToplevelBackend,
)

_FONTE = Path(cosmic_toplevel.__file__)

# Os mesmos números do módulo, escritos à mão de propósito: se alguém trocar um
# opcode lá, este arquivo tem de discordar em vez de acompanhar em silêncio.
_WL_DISPLAY = 1
_GET_REGISTRY = 1
_SYNC = 0
_BIND = 0
_EV_GLOBAL = 0
_EV_CALLBACK_DONE = 0
_EV_INFO_TOPLEVEL = 0
_EV_TOP_TITLE = 2
_EV_TOP_APP_ID = 3
_EV_TOP_STATE = 8
_EV_TOP_CLOSED = 0
_ATIVADO = 2

_PRIMEIRO_ID_DO_SERVIDOR = 0xFF000000


def _enche(b: bytes) -> bytes:
    return b + b"\x00" * ((-len(b)) % 4)


def _msg(objeto: int, opcode: int, corpo: bytes) -> bytes:
    return struct.pack("<II", objeto, ((8 + len(corpo)) << 16) | opcode) + corpo


def _texto(s: str) -> bytes:
    bruto = s.encode() + b"\x00"
    return struct.pack("<I", len(bruto)) + _enche(bruto)


def _vetor_de_estados(*estados: int) -> bytes:
    dados = struct.pack(f"<{len(estados)}I", *estados) if estados else b""
    return struct.pack("<I", len(dados)) + _enche(dados)


class CompositorDeMentira:
    """Um compositor Wayland só o bastante para responder a este backend.

    Fala o protocolo de fio de verdade. O teste manda `abrir_janela`,
    `focar` e `fechar_janela`, e o compositor empurra os eventos pelo soquete
    como o cosmic-comp empurra.
    """

    def __init__(self, tmp: Path, *, publica_o_protocolo: bool = True) -> None:
        self.caminho = str(tmp / "compositor-de-mentira")
        self._publica = publica_o_protocolo
        self._servidor = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._servidor.bind(self.caminho)
        self._servidor.listen(1)
        self._cliente: socket.socket | None = None
        self._info = 0
        self._registro = 0
        self._proximo_do_servidor = _PRIMEIRO_ID_DO_SERVIDOR
        self._janelas: dict[str, int] = {}
        self._titulos: dict[int, str] = {}
        self._apelidos: dict[int, str] = {}
        self._estados: dict[int, tuple[int, ...]] = {}
        self._trava = threading.Lock()
        self._parar = threading.Event()
        self.destruicoes_recebidas: list[int] = []
        self._fio = threading.Thread(target=self._servir, daemon=True)
        self._fio.start()

    # -- o que o teste manda -------------------------------------------------

    def abrir_janela(self, app_id: str, titulo: str, *, ativa: bool = False) -> int:
        """Cria um toplevel.

        Janela aberta ANTES de o cliente ligar espera pela ligação, e sai toda
        de uma vez no `bind` — que é o que o cosmic-comp faz de verdade: a
        lista inicial chega inteira logo depois do aperto de mão. Sem isso, os
        testes só conseguiriam medir janela criada depois da conexão, que é o
        caso mais fácil.
        """
        with self._trava:
            identidade = self._proximo_do_servidor
            self._proximo_do_servidor += 1
            self._janelas[app_id] = identidade
            self._titulos[identidade] = titulo
            self._apelidos[identidade] = app_id
            self._estados[identidade] = (_ATIVADO,) if ativa else ()
            if self._info:
                self._despejar(identidade)
            return identidade

    def focar(self, app_id: str) -> None:
        """Move o `activated` para esta janela — é a troca de foco de verdade."""
        with self._trava:
            for nome, identidade in self._janelas.items():
                self._estados[identidade] = (_ATIVADO,) if nome == app_id else ()
                if self._info:
                    self._enviar(
                        _msg(
                            identidade,
                            _EV_TOP_STATE,
                            _vetor_de_estados(*self._estados[identidade]),
                        )
                    )

    def fechar_janela(self, app_id: str) -> None:
        with self._trava:
            identidade = self._janelas.pop(app_id)
            self._enviar(_msg(identidade, _EV_TOP_CLOSED, b""))

    def _despejar(self, identidade: int) -> None:
        """Os quatro eventos que descrevem uma janela, na ordem do compositor."""
        self._enviar(_msg(self._info, _EV_INFO_TOPLEVEL, struct.pack("<I", identidade)))
        self._enviar(_msg(identidade, _EV_TOP_TITLE, _texto(self._titulos[identidade])))
        self._enviar(_msg(identidade, _EV_TOP_APP_ID, _texto(self._apelidos[identidade])))
        self._enviar(
            _msg(identidade, _EV_TOP_STATE, _vetor_de_estados(*self._estados[identidade]))
        )

    def parar(self) -> None:
        self._parar.set()
        with contextlib.suppress(OSError):
            self._servidor.close()
        if self._cliente is not None:
            with contextlib.suppress(OSError):
                self._cliente.close()
        with contextlib.suppress(OSError):
            os.unlink(self.caminho)

    # -- o fio que atende ----------------------------------------------------

    def _enviar(self, dados: bytes) -> None:
        if self._cliente is None:
            return
        with contextlib.suppress(OSError):
            self._cliente.sendall(dados)

    def _servir(self) -> None:
        try:
            cliente, _ = self._servidor.accept()
        except OSError:
            return
        self._cliente = cliente
        cliente.settimeout(0.2)
        sobra = b""
        while not self._parar.is_set():
            try:
                dado = cliente.recv(65536)
            except TimeoutError:
                continue
            except OSError:
                return
            if not dado:
                return
            sobra += dado
            while len(sobra) >= 8:
                objeto, palavra = struct.unpack_from("<II", sobra, 0)
                tamanho, opcode = palavra >> 16, palavra & 0xFFFF
                if tamanho < 8 or len(sobra) < tamanho:
                    break
                corpo, sobra = sobra[8:tamanho], sobra[tamanho:]
                with self._trava:
                    self._atender(objeto, opcode, corpo)

    def _atender(self, objeto: int, opcode: int, corpo: bytes) -> None:
        if objeto == _WL_DISPLAY and opcode == _GET_REGISTRY:
            (self._registro,) = struct.unpack_from("<I", corpo, 0)
            self._anunciar_globais()
            return
        if objeto == _WL_DISPLAY and opcode == _SYNC:
            (eco,) = struct.unpack_from("<I", corpo, 0)
            self._enviar(_msg(eco, _EV_CALLBACK_DONE, struct.pack("<I", 1)))
            return
        if objeto == self._registro and opcode == _BIND:
            (n,) = struct.unpack_from("<I", corpo, 4)
            pos = 8 + ((n + 3) & ~3)
            _versao, novo = struct.unpack_from("<II", corpo, pos)
            self._info = novo
            for identidade in self._janelas.values():
                self._despejar(identidade)
            return
        # `_apelidos` guarda TODA janela que já existiu — a que acabou de
        # fechar já saiu de `_janelas`, e é justamente o `destroy` dela que
        # este compositor precisa registrar.
        if objeto in self._apelidos:
            self.destruicoes_recebidas.append(objeto)

    def _anunciar_globais(self) -> None:
        publicados = [("wl_compositor", 5)]
        if self._publica:
            publicados.append(("zcosmic_toplevel_info_v1", 3))
        for nome, (interface, versao) in enumerate(publicados, start=1):
            corpo = struct.pack("<I", nome) + _texto(interface) + struct.pack("<I", versao)
            self._enviar(_msg(self._registro, _EV_GLOBAL, corpo))


@pytest.fixture
def compositor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Um compositor de mentira, já apontado pelo `WAYLAND_DISPLAY`."""
    c = CompositorDeMentira(tmp_path)
    monkeypatch.setenv("WAYLAND_DISPLAY", c.caminho)
    yield c
    c.parar()


class TestOCompositorResponde:
    """O caminho feliz, que é o da máquina dela."""

    def test_le_a_janela_ativa(self, compositor: CompositorDeMentira) -> None:
        """MORDIDA: troque `_ESTADO_ATIVADO` para 3 no módulo e reprova."""
        compositor.abrir_janela("com.system76.CosmicTerm", "Terminal")
        compositor.abrir_janela("spotify", "Spotify Premium", ativa=True)
        backend = CosmicToplevelBackend()
        try:
            info = backend.get_active_window_info()
        finally:
            backend.fechar()
        assert isinstance(info, WindowInfo)
        assert info.wm_class == "spotify"
        assert info.app_id == "spotify"
        assert info.title == "Spotify Premium"
        assert backend.last_failure_reason is None

    def test_o_pid_nao_vem_e_isso_e_dito(self, compositor: CompositorDeMentira) -> None:
        """O protocolo não manda PID. Prometer `exe_basename` seria a mentira.

        MORDIDA: fazer o backend inventar um `exe_basename` (o do próprio
        processo, por exemplo) e este teste reprova.
        """
        compositor.abrir_janela("spotify", "Spotify", ativa=True)
        backend = CosmicToplevelBackend()
        try:
            info = backend.get_active_window_info()
        finally:
            backend.fechar()
        assert info is not None
        assert info.pid == 0
        assert info.exe_basename == ""

    def test_nenhuma_ativa_diz_o_motivo(self, compositor: CompositorDeMentira) -> None:
        """Lista cheia e ninguém em foco NÃO é a mesma coisa que lista vazia.

        MORDIDA: devolver a primeira janela da lista quando não há `activated`.
        """
        compositor.abrir_janela("spotify", "Spotify")
        backend = CosmicToplevelBackend()
        try:
            assert backend.get_active_window_info() is None
            assert backend.last_failure_reason == MOTIVO_NENHUMA_ATIVA
        finally:
            backend.fechar()


class TestALeituraViveNoTempo:
    """Uma leitura mede um INSTANTE; o foco é um comportamento."""

    def test_segue_a_troca_de_foco(self, compositor: CompositorDeMentira) -> None:
        """Três trocas, uma conexão só, e a resposta acompanha as três.

        Este é o teste que a régua de 29/08 pediu quando uma regressão só
        apareceu aos 181 segundos: rodar o tique UMA vez não mede nada.

        MORDIDA: guardar a primeira resposta em cache (não reprocessar o
        `state` que chega depois) e as trocas param de aparecer.
        """
        compositor.abrir_janela("google-chrome", "Chrome", ativa=True)
        compositor.abrir_janela("com.system76.CosmicTerm", "Terminal")
        compositor.abrir_janela("spotify", "Spotify")
        backend = CosmicToplevelBackend()
        try:
            vistos = [self._ler(backend)]
            for alvo in ("com.system76.CosmicTerm", "spotify", "google-chrome"):
                compositor.focar(alvo)
                vistos.append(self._ler(backend, esperado=alvo))
        finally:
            backend.fechar()
        assert vistos == [
            "google-chrome",
            "com.system76.CosmicTerm",
            "spotify",
            "google-chrome",
        ]

    def test_janela_fechada_sai_da_lista(self, compositor: CompositorDeMentira) -> None:
        """E o produto devolve o objeto ao compositor, em vez de vazá-lo.

        MORDIDA: apagar a chamada a `_destruir_janela` e a última asserção
        reprova; apagar o `self._janelas.pop` e a primeira reprova.
        """
        compositor.abrir_janela("spotify", "Spotify", ativa=True)
        identidade = compositor._janelas["spotify"]
        backend = CosmicToplevelBackend()
        try:
            assert self._ler(backend) == "spotify"
            compositor.fechar_janela("spotify")
            prazo = time.monotonic() + 3.0
            while time.monotonic() < prazo:
                if backend.get_active_window_info() is None:
                    break
                time.sleep(0.05)
            assert backend.get_active_window_info() is None
            time.sleep(0.2)
            assert identidade in compositor.destruicoes_recebidas
        finally:
            backend.fechar()

    @staticmethod
    def _ler(backend: CosmicToplevelBackend, esperado: str | None = None) -> str:
        """Lê até o compositor ter empurrado o que mandou (com prazo)."""
        prazo = time.monotonic() + 3.0
        visto = None
        while time.monotonic() < prazo:
            info = backend.get_active_window_info()
            visto = None if info is None else info.wm_class
            if visto is not None and (esperado is None or visto == esperado):
                return visto
            time.sleep(0.05)
        return visto or "<nada>"


class TestQuandoNaoDaParaLer:
    """Cada jeito de não conseguir tem nome próprio (JANELA-CEGA-01)."""

    def test_compositor_sem_o_protocolo_desliga_de_vez(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Não é COSMIC: uma ida ao soquete e o backend se aposenta.

        Sem isto, a cascata bateria no compositor a 2 Hz para sempre.

        MORDIDA: tirar o `self._desligado_de_vez = True` de `_ligar` e
        `available` continua True.
        """
        c = CompositorDeMentira(tmp_path, publica_o_protocolo=False)
        monkeypatch.setenv("WAYLAND_DISPLAY", c.caminho)
        backend = CosmicToplevelBackend()
        try:
            assert backend.get_active_window_info() is None
            assert backend.last_failure_reason == MOTIVO_SEM_PROTOCOLO
            assert backend.available is False
            assert backend.protocol_unsupported is True
            assert backend.get_active_window_info() is None
        finally:
            backend.fechar()
            c.parar()

    def test_sem_wayland_display_nao_tenta(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MORDIDA: fazer `caminho_do_soquete` chutar um caminho padrão."""
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        backend = CosmicToplevelBackend()
        assert backend.get_active_window_info() is None
        assert backend.last_failure_reason == MOTIVO_SEM_SOQUETE
        assert backend.available is True  # não é culpa do compositor

    def test_soquete_que_nao_existe_nao_desliga_o_backend(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Compositor fora do ar não é compositor sem o protocolo.

        MORDIDA: marcar `_desligado_de_vez` no ramo de conexão recusada.
        """
        monkeypatch.setenv("WAYLAND_DISPLAY", str(tmp_path / "nao-existe"))
        backend = CosmicToplevelBackend()
        assert backend.get_active_window_info() is None
        assert backend.available is True
        assert backend.protocol_unsupported is False


def _codigo_sem_prosa(caminho: Path) -> str:
    """O fonte sem COMENTÁRIO e sem DOCSTRING — o resto fica, textos inclusive.

    **Esta função nasceu falsa e foi consertada pela mordida, em 02/09/2026.**
    A primeira versão jogava fora todo token `STRING`, e não só as docstrings.
    Parecia razoável — "prosa fora" — e era cega justamente ao que ela promete
    pegar: num cliente Wayland, **o nome de uma interface é sempre um literal
    de texto**. `_DESENHO = "wl_surface"` acrescentado ao módulo passava
    VERDE. A mordida do passo 4 pegou.

    O que se corta agora é o que não pode virar comportamento: comentário, e a
    string solta que abre módulo, classe ou função. Um literal usado como
    VALOR fica, porque é ele que liga a interface.
    """
    import ast
    import io
    import tokenize

    fonte = caminho.read_bytes()
    arvore = ast.parse(fonte)
    linhas_de_docstring: set[int] = set()
    for no in ast.walk(arvore):
        if not isinstance(
            no, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        ):
            continue
        corpo = getattr(no, "body", None)
        if not corpo:
            continue
        primeiro = corpo[0]
        if (
            isinstance(primeiro, ast.Expr)
            and isinstance(primeiro.value, ast.Constant)
            and isinstance(primeiro.value.value, str)
            and primeiro.end_lineno is not None
        ):
            linhas_de_docstring.update(range(primeiro.lineno, primeiro.end_lineno + 1))

    pedacos: list[str] = []
    for tok in tokenize.tokenize(io.BytesIO(fonte).readline):
        if tok.type == tokenize.COMMENT:
            continue
        if tok.type == tokenize.STRING and tok.start[0] in linhas_de_docstring:
            continue
        pedacos.append(tok.string)
    return " ".join(pedacos)


class TestNenhumaJanelaPodeNascerDaqui:
    """A trava da tela dela, conferida no FONTE (a regra de 02/09/2026)."""

    def test_o_backend_nao_liga_interface_de_desenhar(self) -> None:
        """Este cliente lê o compositor; ele não desenha nada.

        A régua lê o CÓDIGO porque o defeito que ela previne é de escrita: no
        dia em que alguém acrescentar um `wl_compositor` aqui para "só pegar a
        escala da tela", nasce o caminho para uma janela aparecer na frente
        dela. Ela tem de conviver com o cabeçalho, que cita essas mesmas
        interfaces para dizer que NÃO as usa — por isso comentário e texto
        saem antes da busca.

        MORDIDA: acrescentar `_WL_SURFACE = "wl_surface"` ao módulo (uma linha
        de CÓDIGO, não de prosa) e este teste reprova. **Foi exatamente essa
        mordida que pegou a régua mentindo** — ver `_codigo_sem_prosa`.
        """
        codigo = _codigo_sem_prosa(_FONTE)
        proibidas = (
            "wl_compositor",
            "wl_surface",
            "xdg_wm_base",
            "zwlr_layer_shell",
            "wl_shell",
        )
        achadas = [p for p in proibidas if p in codigo]
        assert not achadas, f"o backend passou a poder desenhar: {achadas}"

    def test_a_unica_interface_que_ele_liga_e_a_do_cosmic(self) -> None:
        """Uma ligação, e ela está declarada numa constante só.

        MORDIDA: trocar `_INTERFACE` por outra coisa, ou ligar uma segunda.
        """
        assert cosmic_toplevel._INTERFACE == "zcosmic_toplevel_info_v1"
        codigo = _codigo_sem_prosa(_FONTE)
        assert codigo.count("_WL_REGISTRY_BIND") == 2  # a constante e o uso


class _XlibDeMentira:
    """Um `xlib` que responde o que o teste mandar, com o motivo junto."""

    backend_name = "xlib"

    def __init__(self, info: WindowInfo | None, motivo: str | None) -> None:
        self._info = info
        self.last_failure_reason = motivo
        self.chamadas = 0

    def get_active_window_info(self) -> WindowInfo | None:
        self.chamadas += 1
        return self._info

    def conexao_provada(self) -> bool | None:
        return self._info is not None


class _WaylandDeMentira:
    """Uma cascata Wayland que responde o que o teste mandar."""

    backend_name = "cosmic"

    def __init__(self, info: WindowInfo | None, motivo: str | None = None) -> None:
        self._info = info
        self.last_failure_reason = motivo
        self.chamadas = 0

    def get_active_window_info(self) -> WindowInfo | None:
        self.chamadas += 1
        return self._info


class TestOCompostoDoXWayland:
    """JANELA-WAYLAND-CEGA-01: o xlib na frente, o compositor atrás dele.

    A pergunta que estes testes respondem não é "o composto funciona?", é
    **"ele estraga o que já funcionava?"**. O jogo Proton lido pelo xlib traz
    `pid` e `exe_basename`, e é com eles que os perfis dela casam por
    `process_name`. Se o composto perguntasse ao compositor primeiro, cinco
    perfis dela voltariam a não casar (PERFIL-MUDO-01).
    """

    def test_com_o_x_enxergando_o_wayland_nem_e_perguntado(self) -> None:
        """MORDIDA: inverter a ordem no `get_active_window_info` do composto."""
        from hefesto_dualsense4unix.integrations import window_detect

        xlib = _XlibDeMentira(
            WindowInfo(wm_class="steam_app_3357650", pid=42, exe_basename="PRAGMATA.exe"),
            None,
        )
        wayland = _WaylandDeMentira(WindowInfo(wm_class="nao-devia-ser-perguntado"))
        composto = window_detect._XlibComCosmicBackend(xlib, wayland)  # type: ignore[arg-type]

        info = composto.get_active_window_info()
        assert info is not None
        assert info.wm_class == "steam_app_3357650"
        assert info.exe_basename == "PRAGMATA.exe"
        assert wayland.chamadas == 0
        assert composto.backend_name == "xlib"

    def test_com_o_x_cego_a_leitura_vem_do_compositor(self) -> None:
        """O caso medido na sessão dela às 23h02 de 02/09.

        Antes: `wm_class="unknown"`, motivo `sem_foco_x`, perfil nenhum casa.
        Depois: o nome do app, vindo do compositor.

        MORDIDA: fazer o composto devolver `None` quando o xlib devolve `None`.
        """
        from hefesto_dualsense4unix.integrations import window_detect

        xlib = _XlibDeMentira(None, "sem_foco_x")
        wayland = _WaylandDeMentira(
            WindowInfo(wm_class="google-chrome", app_id="google-chrome", title="DOLLSSIÊ")
        )
        composto = window_detect._XlibComCosmicBackend(xlib, wayland)  # type: ignore[arg-type]

        info = composto.get_active_window_info()
        assert info is not None
        assert info.wm_class == "google-chrome"
        assert composto.backend_name == "cosmic"
        assert composto.last_failure_reason is None

    def test_os_dois_calados_preservam_o_motivo_do_x(self) -> None:
        """`sem_foco_x` e "o XWayland caiu" mandam caçar em lugares opostos.

        MORDIDA: trocar o motivo por um genérico quando os dois falham.
        """
        from hefesto_dualsense4unix.integrations import window_detect

        xlib = _XlibDeMentira(None, "sem_conexao_x")
        wayland = _WaylandDeMentira(None, "cosmic_sem_protocolo")
        composto = window_detect._XlibComCosmicBackend(xlib, wayland)  # type: ignore[arg-type]

        assert composto.get_active_window_info() is None
        assert composto.last_failure_reason == "sem_conexao_x"

    def test_o_backend_cosmic_esta_declarado_como_cego_ao_processo(self) -> None:
        """PROCESSO-CEGO-01: a tabela tem de saber do backend novo.

        Sem esta linha, `backend_ve_nome_do_processo("cosmic")` responderia
        `None` — "não sei" — e a aba Sistema deixaria de avisar que perfil por
        `process_name` não casa por este caminho.

        MORDIDA: tirar ``"cosmic"`` de `BACKENDS_CEGOS_AO_PROCESSO`.
        """
        from hefesto_dualsense4unix.integrations.window_detect import (
            BACKENDS_CEGOS_AO_PROCESSO,
            backend_ve_nome_do_processo,
        )

        assert CosmicToplevelBackend.backend_name in BACKENDS_CEGOS_AO_PROCESSO
        assert backend_ve_nome_do_processo("cosmic") is False


class TestADesculpaDoDoctorCaiu:
    """A frase que motivou esta frente não pode voltar por copiar-e-colar."""

    def test_o_doctor_nao_diz_mais_que_e_limitacao_do_compositor(self) -> None:
        """A frase nomeava a cura e chamava de limitação alheia.

        O `zcosmic_toplevel_info_v1` está publicado no compositor dela — medido
        com `wayland-info`, versão 3 entre 58 globais. Enquanto o produto não o
        usava, a desculpa era o produto falando de si na terceira pessoa.

        MORDIDA: escrever de volta "Limitação do compositor" no veredito.
        """
        doctor = _FONTE.parents[4] / "scripts" / "doctor.sh"
        texto = doctor.read_text(encoding="utf-8")
        assert "Limitação do compositor (COSMIC exigiria" not in texto

    def test_o_doctor_pergunta_pelo_protocolo_do_cosmic(self) -> None:
        """Não basta tirar a desculpa: tem de haver a MEDIÇÃO no lugar dela.

        MORDIDA: apagar o bloco que roda o `-m ...cosmic_toplevel` no doctor.
        """
        doctor = _FONTE.parents[4] / "scripts" / "doctor.sh"
        texto = doctor.read_text(encoding="utf-8")
        assert "window_backends.cosmic_toplevel" in texto
        assert "protocolo=sim" in texto

    def test_a_linha_que_o_doctor_le_tem_o_formato_que_ele_espera(
        self, compositor: CompositorDeMentira
    ) -> None:
        """O bash casa com `protocolo=sim*` — o Python tem de começar por aí.

        Este par (bash e Python) é exatamente o tipo de acordo que apodrece
        calado: o doctor cairia no ramo do `wayland-info` e diria "o hefesto
        instalado não sabe usá-lo" com o backend funcionando.

        O compositor de mentira entra aqui porque a `sondar_o_compositor`
        constrói o backend por dentro: sem ele, este teste ligaria no
        compositor da máquina onde roda.

        MORDIDA: trocar a ordem dos campos em `_linha_para_o_doctor`.
        """
        compositor.abrir_janela("spotify", "Spotify", ativa=True)
        linha = cosmic_toplevel._linha_para_o_doctor()
        campos = linha.split("|")
        assert campos[0] == "protocolo=sim"
        assert campos[1].startswith("janelas=")
        assert campos[2] == "wm_class=spotify"

    def test_a_linha_diz_nao_quando_o_compositor_nao_publica(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDIDA: fazer a sonda devolver `protocolo=sim` sem ligação."""
        c = CompositorDeMentira(tmp_path, publica_o_protocolo=False)
        monkeypatch.setenv("WAYLAND_DISPLAY", c.caminho)
        try:
            assert cosmic_toplevel._linha_para_o_doctor().startswith("protocolo=nao")
        finally:
            c.parar()
