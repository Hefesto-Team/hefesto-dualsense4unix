"""janela — a janela, as duas pontes e a guarda de carga. UMA VEZ, para as dez abas."""
from __future__ import annotations

import json
import pathlib
import sys
import time
from collections.abc import Callable
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("WebKit2", "4.1")

from gi.repository import Gdk, GLib, Gtk, WebKit2  # noqa: E402

from hefesto_dualsense4unix.app import theme as tema  # noqa: E402
from hefesto_dualsense4unix.interface.folha_da_casa import (  # noqa: E402
    CLASSE_DA_ESPERA,
    FOLHA_DA_CASA,
)
from hefesto_dualsense4unix.utils import identidade as _identidade  # noqa: E402

_CASA = _identidade.atual()

AS_QUATRO_ARMADILHAS: tuple[str, ...] = (
    "FINISHED dispara DEPOIS de um load-failed, com o URI ORIGINAL: arquivo "
    "inexistente dá DOIS FINISHED e o segundo é indistinguível de sucesso. E "
    "host recusando conexão não dispara load-failed nenhum — só troca o URI "
    "para about:blank, calado. Quem confirma a carga é a PÁGINA, perguntada "
    "por JS, e custa 0,04 ms",
    "get_title() dentro do handler de FINISHED devolve vazio — o título chega "
    "depois. Este módulo não chama get_title() em lugar nenhum",
    "evaluate_javascript não devolve Promise (Unsupported result type 601): "
    "toda resposta assíncrona da tela volta pelo postMessage, nunca pelo "
    "retorno da avaliação",
    "na série 4.1 o handler de script-message-received leva UM argumento; na "
    "6.0 leva dois. Escrever a forma da 6.0 aqui faz o gesto sumir calado",
)


MS_ANTES_DE_RECARREGAR = 250

RECARGAS_SEGUIDAS = 3

SEGUNDOS_PARA_ESQUECER_O_CRASH = 60.0

CANAL_PADRAO = "hefesto"

#: No vídeo dela a pintura chega em 1 a 2 quadros (33 a 66 ms) depois de a
#: página aparecer. O prazo é a rede de segurança do caso em que o piloto NÃO
#: pinta — travado, ou sem o bootstrap: aí a tela mostra o arquivo como está
#: (o desenho), que é o comportamento de antes, em vez de ficar sem miolo.
PRAZO_DA_ESPERA_MS = 1500

ROTEIRO_DA_ESPERA = (
    "(function(){var h=document.documentElement;if(!h)return;"
    f"h.classList.add('{CLASSE_DA_ESPERA}');"
    f"setTimeout(function(){{h.classList.remove('{CLASSE_DA_ESPERA}');}},"
    f"{PRAZO_DA_ESPERA_MS});}})();"
)

LARGURA_DO_DESENHO = 1212

PISO_DA_VISTA = 809

ALTURA_DO_DESENHO = PISO_DA_VISTA

ALTURA_DA_BARRA = 39

CSS_DA_BARRA = """
headerbar {
  min-height: 39px;
  padding-top: 0;
  padding-bottom: 0;
}
button {
  min-height: 24px;
  min-width: 24px;
  padding: 4px;
  margin: 0;
  border: none;
  border-radius: 6px;
  box-shadow: none;
  background: none;
}
button:hover {
  background-color: alpha(currentColor, 0.12);
}
button:active {
  background-color: alpha(currentColor, 0.2);
}
"""

APARENCIA_DO_MAXIMIZAR: dict[bool, tuple[str, str]] = {
    False: ("window-maximize-symbolic", "Maximizar"),
    True: ("window-restore-symbolic", "Restaurar"),
}

BOTOES_DA_BARRA = (
    ("window-close-symbolic", "fechar", "Fechar"),
    (APARENCIA_DO_MAXIMIZAR[False][0], "maximizar", APARENCIA_DO_MAXIMIZAR[False][1]),
    ("window-minimize-symbolic", "minimizar", "Minimizar"),
)

TAMANHO_NA_TELA = (LARGURA_DO_DESENHO, PISO_DA_VISTA + ALTURA_DA_BARRA)
TAMANHO_OCULTA = (LARGURA_DO_DESENHO, PISO_DA_VISTA)

RECUO_DO_CORPO = 16

CROMO_DA_JANELA = 143

MIOLO_NO_PISO = PISO_DA_VISTA - 2 * RECUO_DO_CORPO - CROMO_DA_JANELA

SEM_JANELA_NA_TELA = "HEFESTO_SEM_JANELA"


def janela_proibida_na_tela() -> bool:
    """O ambiente proíbe abrir janela visível nesta máquina?"""
    import os

    return bool(os.environ.get(SEM_JANELA_NA_TELA, "").strip())


def literal_js(valor: object) -> str:
    """Um valor Python virando literal JavaScript, por JSON e só por JSON."""
    return json.dumps(valor)


def vestir_o_nome_acessivel(botao: Any, dica: str) -> None:
    """Prende ao PORTUGUÊS o nome que o leitor de tela anuncia.

    Um `Gtk.Button` que só carrega uma imagem não tem rótulo, e o ATK cai no
    nome do ÍCONE. **MEDIDO NESTA ÁRVORE, na sessão do usuário (`LANG=pt_BR.UTF-8`),
    com a barra montada exatamente como o construtor a montava:**

    ============================  =============  ==========
    ícone                         em ``pt_BR``   em ``C``
    ============================  =============  ==========
    ``window-close-symbolic``     ``Fechar``     ``Close``
    ``window-maximize-symbolic``  ``Maximize``   ``Maximize``
    ``window-minimize-symbolic``  ``Minimize``   ``Minimize``
    ``window-restore-symbolic``   ``Restore``    ``Restore``
    ============================  =============  ==========

    **SÓ O FECHAR ESTAVA TRADUZIDO.** Na tela do usuário, dois dos três botões se
    anunciavam em inglês — «Maximize» e «Minimize» — com a dica ao lado dizendo
    «Maximizar» e «Minimizar». Quem lê recebia uma palavra; quem ouve, outra. E
    o estado novo desta volta entra pela mesma porta: sem esta função, a janela
    maximizada passaria a anunciar «Restore».

    CORREÇÃO DE FATO, de um erro de medição: a primeira versão desta docstring dizia
    que **os três** respondiam em inglês, inclusive ``'Close'``. Aquela medição
    rodou com ``LC_ALL=C`` no próprio arquivo de ambiente da régua — herdado da
    regra de LER o servidor de som sem tradução — e respondeu sobre o locale do
    instrumento, não sobre o produto. A tabela acima é a medição refeita nos
    dois locales, e é a que vale.

    ``set_tooltip_text`` não faz este trabalho: a dica é um balão do GTK e não
    entra no ATK — está na tabela, com a dica certa do lado do nome errado.

    Duas réguas, em ``tests/unit/test_a_barra_diz_o_estado_da_janela.py``: a de
    dentro do processo amarra o nome à dica (e morde na sessão do usuário, pelos dois
    botões em inglês); ``test_o_nome_acessivel_nao_segue_o_locale`` mede **num
    processo filho com ``LC_ALL=C``**, para a garantia não depender do locale
    de quem roda a suíte.
    """
    acessivel = botao.get_accessible()
    if acessivel is not None:
        acessivel.set_name(dica)


def montar_a_barra(
    titulo: str,
    subtitulo: str,
    ao_gesto: Callable[..., None],
) -> tuple[Any, dict[str, Any]]:
    """A ``Gtk.HeaderBar`` da janela, com os três botões DESTA CASA."""
    barra = Gtk.HeaderBar()
    barra.set_show_close_button(False)
    estilo = Gtk.CssProvider()
    estilo.load_from_data(CSS_DA_BARRA.encode("utf-8"))
    barra.get_style_context().add_provider(estilo, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    botoes: dict[str, Any] = {}
    for nome_do_icone, gesto, dica in BOTOES_DA_BARRA:
        botao = Gtk.Button()
        botao.get_style_context().add_provider(estilo, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        botao.set_valign(Gtk.Align.CENTER)
        botao.set_image(Gtk.Image.new_from_icon_name(nome_do_icone, Gtk.IconSize.MENU))
        botao.set_relief(Gtk.ReliefStyle.NONE)
        botao.set_tooltip_text(dica)
        botao.get_style_context().add_class("titlebutton")
        vestir_o_nome_acessivel(botao, dica)
        botao.connect("clicked", ao_gesto, gesto)
        barra.pack_end(botao)
        botoes[gesto] = botao
    barra.set_title(titulo)
    if subtitulo:
        barra.set_subtitle(subtitulo)
    return barra, botoes


def vestir_a_cara_do_maximizar(botoes: dict[str, Any], maximizada: bool) -> bool:
    """Põe no botão do meio a cara do estado em que a janela ESTÁ."""
    botao = botoes.get("maximizar")
    if botao is None:
        return False
    nome_do_icone, dica = APARENCIA_DO_MAXIMIZAR[bool(maximizada)]
    imagem = botao.get_image()
    if imagem is None:
        return False
    imagem.set_from_icon_name(nome_do_icone, Gtk.IconSize.MENU)
    botao.set_tooltip_text(dica)
    vestir_o_nome_acessivel(botao, dica)
    return True


class PonteDaTela:
    """As duas pontes, e nada mais: Python → página e página → Python."""

    def __init__(
        self,
        *,
        canal: str = CANAL_PADRAO,
        ao_receber: Callable[[dict[str, Any]], None] | None = None,
        ao_recusar: Callable[[str, str], None] | None = None,
        folha: str | None = FOLHA_DA_CASA,
        esperar_a_pintura: bool = False,
    ) -> None:
        self.canal = canal
        self._ao_receber = ao_receber
        self._ao_recusar = ao_recusar
        self.recusas: list[tuple[str, str]] = []
        self.chamadas = 0

        ucm = WebKit2.UserContentManager()
        ucm.register_script_message_handler(canal)
        ucm.connect(f"script-message-received::{canal}", self._da_tela)
        if folha:
            ucm.add_style_sheet(
                WebKit2.UserStyleSheet(
                    folha,
                    WebKit2.UserContentInjectedFrames.TOP_FRAME,
                    WebKit2.UserStyleLevel.USER,
                    None,
                    None,
                )
            )
        if esperar_a_pintura:
            ucm.add_script(
                WebKit2.UserScript(
                    ROTEIRO_DA_ESPERA,
                    WebKit2.UserContentInjectedFrames.TOP_FRAME,
                    WebKit2.UserScriptInjectionTime.START,
                    None,
                    None,
                )
            )
        self.ucm = ucm
        self.view = WebKit2.WebView.new_with_user_content_manager(ucm)

    def dizer(self, funcao: str, *argumentos: object) -> None:
        """Chama uma função da página com os argumentos serializados em JSON."""
        crus = ", ".join(literal_js(a) for a in argumentos)
        self.rodar(f"{funcao}({crus})")

    def rodar(self, script: str) -> None:
        """JavaScript solto, sem esperar resposta — instalar o bootstrap, mexer"""
        self.chamadas += 1
        self.view.evaluate_javascript(script, -1, None, None, None, None, None)

    def perguntar(
        self,
        js: str,
        resposta: Callable[[str | None, Exception | None], None],
    ) -> None:
        """Avalia o ``js`` e devolve o resultado como texto ao callback."""
        self.chamadas += 1

        def terminou(view: Any, res: Any, _u: Any = None) -> None:
            try:
                valor = view.evaluate_javascript_finish(res)
            except Exception as erro:
                resposta(None, erro)
                return
            resposta(None if valor is None else valor.to_string(), None)

        self.view.evaluate_javascript(js, -1, None, None, None, terminou, None)

    def _da_tela(self, _ucm: Any, resultado: Any) -> None:
        """ARMADILHA 4: na 4.1 este handler leva UM argumento além do ``ucm``."""
        valor = resultado.get_js_value() if hasattr(resultado, "get_js_value") else resultado
        try:
            bruto = valor.to_string()
        except Exception as erro:
            self._recusar("a mensagem não virou texto", repr(erro))
            return
        self.receber_texto(bruto)

    def receber_texto(self, bruto: str) -> None:
        """A metade da ponte que NÃO precisa de WebView: o texto vira gesto."""
        try:
            objeto = json.loads(bruto)
        except (TypeError, ValueError) as erro:
            self._recusar(f"não é JSON ({erro})", str(bruto))
            return
        if not isinstance(objeto, dict):
            self._recusar(f"JSON válido, mas não é objeto (veio {type(objeto).__name__})", bruto)
            return
        if self._ao_receber is not None:
            self._ao_receber(objeto)

    def _recusar(self, motivo: str, bruto: str) -> None:
        self.recusas.append((motivo, bruto[:200]))
        if self._ao_recusar is not None:
            self._ao_recusar(motivo, bruto)
        else:
            print(f"ponte: gesto RECUSADO — {motivo}: {bruto[:200]!r}", file=sys.stderr)


class JanelaDaAba:
    """A janela que hospeda uma aba do mockup, com a guarda de carga que não mata."""

    def __init__(
        self,
        *,
        arquivo: pathlib.Path,
        titulo_esperado: str,
        ao_carregar: Callable[[], None],
        ao_receber: Callable[[dict[str, Any]], None] | None = None,
        ao_recusar: Callable[[str, str], None] | None = None,
        ao_sair_da_aba: Callable[[str], None] | None = None,
        ao_falhar: Callable[[str], None] | None = None,
        ao_morrer_a_pagina: Callable[[str], None] | None = None,
        oculta: bool = False,
        titulo: str = _CASA.nome_longo,
        subtitulo: str = "",
        canal: str = CANAL_PADRAO,
        folha: str | None = FOLHA_DA_CASA,
        tamanho: tuple[int, int] | None = None,
        esperar_a_pintura: bool = False,
    ) -> None:
        self.arquivo = arquivo
        self.titulo_esperado = titulo_esperado
        self._ao_carregar = ao_carregar
        self._ao_sair_da_aba = ao_sair_da_aba
        self._ao_falhar = ao_falhar
        self._ao_morrer_a_pagina = ao_morrer_a_pagina
        self.morreu: str | None = None
        self.oculta = oculta
        self.primeira_carga = True
        self.na_aba = False
        self.mortes: list[str] = []
        self.recargas = 0
        self._viva_desde = time.monotonic()

        self.ponte = PonteDaTela(
            canal=canal, ao_receber=ao_receber, ao_recusar=ao_recusar, folha=folha,
            esperar_a_pintura=esperar_a_pintura,
        )
        self.view = self.ponte.view
        self.view.connect("load-changed", self._carregou)
        self.view.connect("web-process-terminated", self._morreu_a_pagina)

        if not oculta and janela_proibida_na_tela():
            print(
                f"[janela] {SEM_JANELA_NA_TELA} está no ambiente: abrindo "
                f"OCULTA em vez de na tela dela ({titulo}).",
                file=sys.stderr,
            )
            oculta = True
            self.oculta = True

        tema.adotar_o_tema_da_sessao()
        tema.pedir_a_variante_escura()
        tema.adotar_a_barra_da_sessao()

        self._botoes_da_barra: dict[str, Any] = {}

        if oculta:
            self.janela: Any = Gtk.OffscreenWindow()
            self.janela.set_default_size(*(tamanho or TAMANHO_OCULTA))
        else:
            self.janela = Gtk.Window(title=f"{titulo} — {subtitulo}" if subtitulo else titulo)
            self.janela.set_default_size(*(tamanho or TAMANHO_NA_TELA))
            self.janela.set_size_request(LARGURA_DO_DESENHO, PISO_DA_VISTA + ALTURA_DA_BARRA)
            barra, self._botoes_da_barra = montar_a_barra(
                titulo, subtitulo or "", self._gesto_da_barra
            )
            self.janela.set_titlebar(barra)
            # do print arruma automaticamente"*  <!-- noqa-acento: dela -->
            self.janela.connect("window-state-event", self._a_barra_se_refaz)
            self.janela.connect("destroy", Gtk.main_quit)
        self.janela.add(self.view)
        self.janela.show_all()
        self.view.load_uri(arquivo.as_uri())

    ATRASOS_DO_REDESENHO_MS = (60, 300)

    def _a_barra_se_refaz(self, _janela: Any, evento: Any) -> bool:
        """Veste o botão do meio com o estado novo e agenda o redesenho."""
        mudou = int(getattr(evento, "changed_mask", 0) or 0)
        estado = int(getattr(evento, "new_window_state", 0) or 0)

        vestir_a_cara_do_maximizar(
            self._botoes_da_barra, bool(estado & int(Gdk.WindowState.MAXIMIZED))
        )

        if not (mudou & ~int(Gdk.WindowState.FOCUSED)):
            return False

        for atraso in self.ATRASOS_DO_REDESENHO_MS:
            GLib.timeout_add(atraso, self._repintar_a_decoracao)
        return False

    def _gesto_da_barra(self, _botao: Any, gesto: str) -> None:
        """Minimizar, maximizar/restaurar ou fechar, pelos botões desta casa."""
        if gesto == "fechar":
            self.janela.close()
        elif gesto == "minimizar":
            self.janela.iconify()
        elif gesto == "maximizar":
            if self.janela.is_maximized():
                self.janela.unmaximize()
            else:
                self.janela.maximize()

    def _repintar_a_decoracao(self) -> bool:
        """O gesto que o screenshot dela fazia de graça."""
        self.janela.queue_resize()
        barra = self.janela.get_titlebar()
        if barra is not None:
            barra.hide()
            barra.show_all()
            barra.queue_resize()
        gdk = self.janela.get_window()
        if gdk is not None:
            gdk.invalidate_rect(None, True)
        self.janela.queue_draw()
        return False

    def _carregou(self, _view: Any, evento: Any) -> None:
        if evento != WebKit2.LoadEvent.FINISHED:
            return
        self._confirmar_a_pagina()

    def _confirmar_a_pagina(self) -> None:
        """Quem diz que a carga deu certo é a PÁGINA, não o evento nem o URI."""

        def respondeu(titulo: str | None, erro: Exception | None) -> None:
            if erro is not None:
                self._morrer(f"a página não respondeu: {erro}")
                return
            if self.titulo_esperado not in (titulo or ""):
                if self.primeira_carga:
                    self._morrer(f"carregou OUTRA página: título {titulo!r}")
                else:
                    self._saiu_da_aba(titulo or "(sem título)")
                return
            self.primeira_carga = False
            self.na_aba = True
            self._viva_desde = time.monotonic()
            self._ao_carregar()

        self.ponte.perguntar("document.title", respondeu)

    def _morreu_a_pagina(self, _view: Any, motivo: Any) -> None:
        """O processo web do WebKit terminou. A janela RECARREGA — e diz."""
        nome = getattr(motivo, "value_nick", None) or str(motivo)
        self.mortes.append(str(nome))
        self.na_aba = False
        print(f"[página morreu] o processo web do WebKit terminou ({nome})",
              file=sys.stderr)
        if self._ao_morrer_a_pagina is not None:
            self._ao_morrer_a_pagina(str(nome))
        if time.monotonic() - self._viva_desde >= SEGUNDOS_PARA_ESQUECER_O_CRASH:
            self.recargas = 0
        if self.recargas >= RECARGAS_SEGUIDAS:
            print(f"[página morreu] {self.recargas} recargas seguidas sem a "
                  f"página parar de pé — não recarrego de novo.", file=sys.stderr)
            return
        self.recargas += 1
        self._viva_desde = time.monotonic()
        GLib.timeout_add(MS_ANTES_DE_RECARREGAR, self._recarregar)

    def _recarregar(self) -> bool:
        """Traz a página de volta. ``load_uri`` quando nunca houve carga boa."""
        print(f"[página morreu] recarregando ({self.recargas}/{RECARGAS_SEGUIDAS})",
              file=sys.stderr)
        if self.primeira_carga:
            self.view.load_uri(self.arquivo.as_uri())
        else:
            self.view.reload()
        return False

    def _saiu_da_aba(self, titulo: str) -> None:
        """O usuário clicou na tira. Isso é LEGÍTIMO, e matar a janela por isso é bug."""
        if not self.na_aba:
            return
        self.na_aba = False
        if self._ao_sair_da_aba is not None:
            self._ao_sair_da_aba(titulo)
        else:
            print(f"[fora da aba] {titulo} — o mockup estático; a pintura pausou.")

    def _morrer(self, motivo: str) -> None:
        self.morreu = motivo
        if self._ao_falhar is not None:
            self._ao_falhar(motivo)
            return
        print(f"ERRO DE CARGA: {motivo}", file=sys.stderr)
        Gtk.main_quit()

    def agendar_saida(self, segundos: float, antes: Callable[[], None] | None = None) -> None:
        """Fecha a janela daqui a N segundos. ``0`` (ou menos) não agenda nada."""
        if segundos <= 0:
            return

        def sair() -> bool:
            if antes is not None:
                antes()
            Gtk.main_quit()
            return False

        GLib.timeout_add(int(segundos * 1000), sair)

    def fotografar(self, destino: str) -> bool:
        """O PNG da janela oculta. Devolve se a foto saiu."""
        if not isinstance(self.janela, Gtk.OffscreenWindow):
            print("foto: só a janela OCULTA se fotografa (use --oculta)", file=sys.stderr)
            return False
        pix = self.janela.get_pixbuf()
        if pix is None:
            print("foto: a janela oculta ainda não tem pixbuf", file=sys.stderr)
            return False
        pix.savev(destino, "png", [], [])
        print(f"foto: {destino}")
        return True
