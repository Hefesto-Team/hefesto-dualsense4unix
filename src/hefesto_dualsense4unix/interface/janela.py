"""janela — a janela, as duas pontes e a guarda de carga. UMA VEZ, para as dez abas."""
from __future__ import annotations

import contextlib
import json
import pathlib
import signal
import sys
import time
from collections.abc import Callable
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("WebKit2", "4.1")

from gi.repository import Gdk, Gio, GLib, Gtk, WebKit2  # noqa: E402

from hefesto_dualsense4unix.interface import tema_da_sessao as tema  # noqa: E402
from hefesto_dualsense4unix.interface.folha_da_casa import (  # noqa: E402
    CLASSE_DA_ESPERA,
    FOLHA_DA_CASA,
    caminho_do_tamanho,
    tamanho_guardado,
)
from hefesto_dualsense4unix.mods import tema as _tema_das_mods  # noqa: E402
from hefesto_dualsense4unix.utils import identidade as _identidade  # noqa: E402

_CASA = _identidade.atual()


class _TemaLigado(str):
    """O padrão de quem não diz o tema: o da modificação ligada, lido do registro."""


#: ``tema_de_cores=TEMA_LIGADO`` (o padrão) pede o tema da modificação ligada; ``None`` ou ``""``
#: abre sem tema; outra folha é usada como veio (quem a passa já a conferiu por
#: ``mods.tema.validar``).
TEMA_LIGADO = _TemaLigado("")


def folha_do_tema() -> str:
    """A folha do tema ligado, ou vazio. O tema reprovado não liga, e a frase vai para o
    diário: a interface não tem tela de modificações, e o tema que não ligou não muda a cor."""
    casa = _tema_das_mods.tema_da_casa()
    for frase in (casa.recusa, *casa.avisos):
        if frase:
            print(f"[tema] {frase}", file=sys.stderr)
    return casa.folha


def _a_folha_do_tema(pedido: str | None) -> str:
    if pedido is None:
        return ""
    return folha_do_tema() if isinstance(pedido, _TemaLigado) else pedido


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

#: No vídeo gravado na bancada a pintura chega em 1 a 2 quadros (33 a 66 ms) depois de a
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



def css_da_cor_da_barra(folha_do_tema: str) -> str:
    """A barra da janela nas cores do tema ligado: o fundo é o ``--panel`` e a letra o ``--fg``.

    Sem tema, vazio: a barra fica com a cor da sessão (no COSMIC, o ``gtk.css`` que ela gera).
    Decisão de 20/10/2026, a validar pelo usuário
    (O-TEMA-LIGA-SEM-REABRIR-A-JANELA-E-O-GTK-SEGUE-O-TEMA-01).
    """
    if not folha_do_tema:
        return ""
    tokens = _tema_das_mods.tokens_da_folha(folha_do_tema)
    casa = _tokens_da_casa_ou_nada()
    fundo = tokens.get("--panel") or casa.get("--panel")
    letra = tokens.get("--fg") or casa.get("--fg")
    if not (fundo and letra):
        return ""
    return (f"headerbar {{ background: {fundo}; color: {letra}; }}\n"
            f"button {{ color: {letra}; }}\n")


def _tokens_da_casa_ou_nada() -> dict[str, str]:
    try:
        return _tema_das_mods.tokens_da_casa()
    except (OSError, _tema_das_mods.TemaRecusadoError) as erro:
        print(f"[tema] as cores da casa não abriram: {erro}", file=sys.stderr)
        return {}


#: O par (escuro, claro) que o tema claro trocou, para a casa escura voltar ao escuro da sessão.
_O_ESCURO_TROCADO: list[tuple[str, str]] = []


def o_par_claro(nome: str) -> str:
    """O par claro de um tema GTK que só existe escuro (`adw-gtk3-dark` → `adw-gtk3`), ou vazio.

    O COSMIC grava na sessão o nome do tema escuro, e nele o pedido da variante clara não muda
    nada: medido em 21/10/2026, a lista do ``adw-gtk3-dark`` sai ``#1e1e1e`` com
    ``gtk-application-prefer-dark-theme`` em falso, e a do ``adw-gtk3`` sai ``#ffffff``.
    """
    if not nome.endswith("-dark"):
        return ""
    base = nome.removesuffix("-dark")
    pastas = [pathlib.Path(GLib.get_user_data_dir()) / "themes", pathlib.Path.home() / ".themes",
              *(pathlib.Path(d) / "themes" for d in GLib.get_system_data_dirs())]
    if base == "Adwaita" or any((p / base / "gtk-3.0" / "gtk.css").is_file() for p in pastas):
        return base
    return ""


def pedir_a_variante(folha_do_tema: str) -> bool:
    """Pede ao GTK a variante do tema do sistema que combina com o tema de cores.

    O popup do ``<select>`` e o resto que o CSS da página não alcança seguem a variante: escura
    com a casa (BUG-GUI-COSMIC-WIDGET-CONTRAST-01), clara com um tema claro, trocando o tema da
    sessão que só existe escuro pelo par claro dele. Devolve se é escura.
    """
    escura = _tema_das_mods.e_escuro(_tema_das_mods.tokens_da_folha(folha_do_tema),
                                     _tokens_da_casa_ou_nada())
    ajustes = Gtk.Settings.get_default()
    if escura:
        if _O_ESCURO_TROCADO and ajustes is not None:
            escuro, claro = _O_ESCURO_TROCADO.pop()
            if ajustes.get_property("gtk-theme-name") == claro:
                ajustes.set_property("gtk-theme-name", escuro)
        tema.pedir_a_variante_escura()
        return True
    if ajustes is not None:
        nome = str(ajustes.get_property("gtk-theme-name") or "")
        claro = o_par_claro(nome)
        if claro:
            _O_ESCURO_TROCADO[:] = [(nome, claro)]
            ajustes.set_property("gtk-theme-name", claro)
        ajustes.set_property("gtk-application-prefer-dark-theme", False)
    return False


APARENCIA_DO_MAXIMIZAR: dict[bool, tuple[str, str]] = {
    False: ("window-maximize-symbolic", "Maximizar"),
    True: ("window-restore-symbolic", "Restaurar"),
}

#: Na ORDEM DA TELA, da esquerda para a direita, e à esquerda do título (20/10/2026,
#: OS-BOTOES-DA-JANELA-VAO-PARA-A-ESQUERDA-01: fechar, maximizar, minimizar). O
#: `montar_a_barra` os põe com `pack_start`; os botões são desta casa, e o
#: `gtk-decoration-layout` da sessão não os alcança.
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

#: No máximo uma linha `[janela] tamanho:` por intervalo desta duração; o que cair no meio
#: de uma rajada (arrastar a borda dispara dezenas de `configure-event` por segundo) vira UMA
#: linha no fim do intervalo, com o último valor, para a rajada não esconder onde ela parou.
SEGUNDOS_ENTRE_LINHAS_DE_TAMANHO = 1.0

#: Os sinais que encerram a janela por fora, e que antes a matavam sem uma linha.
SINAIS_DE_FIM = (signal.SIGTERM, signal.SIGHUP)


def nome_do_estado(estado: int) -> str:
    """O estado do `Gdk.WindowState`, em uma palavra do diário."""
    marcas = (
        (Gdk.WindowState.FULLSCREEN, "tela cheia"),
        (Gdk.WindowState.MAXIMIZED, "maximizada"),
        (Gdk.WindowState.ICONIFIED, "minimizada"),
        (Gdk.WindowState.TILED, "ladrilhada"),
    )
    for marca, nome in marcas:
        if estado & int(marca):
            return nome
    return "normal"


def janela_proibida_na_tela() -> bool:
    """O ambiente proíbe abrir janela visível nesta máquina?"""
    import os

    return bool(os.environ.get(SEM_JANELA_NA_TELA, "").strip())


def literal_js(valor: object) -> str:
    """Um valor Python virando literal JavaScript, por JSON e só por JSON."""
    return json.dumps(valor)


def por_na_area_de_transferencia(texto: str) -> bool:
    """O texto na área de transferência, pelo laço do GTK desta moldura. `False` = não deu."""

    def _agora() -> bool:
        with contextlib.suppress(Exception):
            area = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            area.set_text(texto, -1)
            area.store()
        return False

    GLib.idle_add(_agora)
    return True


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


#: O tamanho da interface que a 09 grava (100, 125 ou 150) vale por padrão quando o arquivo não diz.
TAMANHO_PADRAO = 100


def tamanho_da_interface() -> int:
    """O percentual guardado em `interface_escala` (100, 125 ou 150), lido de quem o grava.

    A aba Sistema grava o arquivo; quem o lê é a folha da casa (`folha_da_casa.tamanho_guardado`),
    que não traz as dez abas para dentro da abertura. Se a pergunta falhar, a janela abre no
    tamanho de hoje e o diário diz por quê; zoom que não aplicou nunca derruba a tela.
    """
    try:
        return int(tamanho_guardado())
    except Exception as erro:  # a janela segue aberta no tamanho de hoje, e o diário conta
        print(
            f"[janela] tamanho da interface: não li o arquivo ({erro!r}); fico em "
            f"{TAMANHO_PADRAO} %",
            file=sys.stderr,
        )
        return TAMANHO_PADRAO


def arquivo_do_tamanho() -> pathlib.Path | None:
    """O caminho do `interface_escala`, ou `None` se quem o conhece não respondeu."""
    try:
        return pathlib.Path(caminho_do_tamanho())
    except Exception as erro:
        print(f"[janela] tamanho da interface: sem arquivo para vigiar ({erro!r})", file=sys.stderr)
        return None


def montar_a_barra(
    titulo: str,
    subtitulo: str,
    ao_gesto: Callable[..., None],
    cor: Any = None,
) -> tuple[Any, dict[str, Any]]:
    """A ``Gtk.HeaderBar`` da janela, com os três botões DESTA CASA.

    ``cor`` é o ``Gtk.CssProvider`` das cores do tema (:func:`css_da_cor_da_barra`): quem o passa
    troca o texto dele, e a barra e os botões repintam.
    """
    barra = Gtk.HeaderBar()
    barra.set_show_close_button(False)
    estilo = Gtk.CssProvider()
    estilo.load_from_data(CSS_DA_BARRA.encode("utf-8"))
    provedores = [(estilo, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)]
    if cor is not None:
        provedores.append((cor, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1))
    for provedor, prioridade in provedores:
        barra.get_style_context().add_provider(provedor, prioridade)
    botoes: dict[str, Any] = {}
    for nome_do_icone, gesto, dica in BOTOES_DA_BARRA:
        botao = Gtk.Button()
        for provedor, prioridade in provedores:
            botao.get_style_context().add_provider(provedor, prioridade)
        botao.set_valign(Gtk.Align.CENTER)
        botao.set_image(Gtk.Image.new_from_icon_name(nome_do_icone, Gtk.IconSize.MENU))
        botao.set_relief(Gtk.ReliefStyle.NONE)
        botao.set_tooltip_text(dica)
        botao.get_style_context().add_class("titlebutton")
        vestir_o_nome_acessivel(botao, dica)
        botao.connect("clicked", ao_gesto, gesto)
        barra.pack_start(botao)
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
        tema_de_cores: str | None = TEMA_LIGADO,
    ) -> None:
        self.canal = canal
        self._ao_receber = ao_receber
        self._ao_recusar = ao_recusar
        self.recusas: list[tuple[str, str]] = []
        self.chamadas = 0

        ucm = WebKit2.UserContentManager()
        ucm.register_script_message_handler(canal)
        ucm.connect(f"script-message-received::{canal}", self._da_tela)
        # O tema de cores (O-TEMA-DE-CORES-ENTRA-PELA-FOLHA-DE-USUARIO-01) é a SEGUNDA folha de
        # usuário, depois da da casa: só redefine tokens do `:root`, com `!important`, que no nível
        # USER vence o `:root` da página sem mudar um byte dela.
        self.folha_da_casa = folha or ""
        self.tema_de_cores = _a_folha_do_tema(tema_de_cores)
        self.ucm = ucm
        self._por_as_folhas()
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
        self.view = WebKit2.WebView.new_with_user_content_manager(ucm)
        # O botão direito é da casa: o menu do WebKit não abre, e quem responde é o
        # menu HTML da base comum, que aciona gestos.
        self.view.connect("context-menu", self._calar_o_menu_do_webkit)

    def _por_as_folhas(self) -> None:
        for estilo in (self.folha_da_casa, self.tema_de_cores):
            if not estilo:
                continue
            self.ucm.add_style_sheet(
                WebKit2.UserStyleSheet(
                    estilo,
                    WebKit2.UserContentInjectedFrames.TOP_FRAME,
                    WebKit2.UserStyleLevel.USER,
                    None,
                    None,
                )
            )

    def trocar_o_tema(self, folha_do_tema: str) -> None:
        """Troca o tema de cores sem recarregar a página: tira as folhas de usuário e põe de novo
        a da casa e a do tema (vazio desliga). O WebKit repinta na hora."""
        self.ucm.remove_all_style_sheets()
        self.tema_de_cores = folha_do_tema
        self._por_as_folhas()

    @staticmethod
    def _calar_o_menu_do_webkit(_view: Any, _menu: Any, _evento: Any, _resultado: Any) -> bool:
        """`True` diz ao WebKit que o menu já foi tratado, e ele não abre o seu."""
        return True

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
        tema_de_cores: str | None = TEMA_LIGADO,
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
        self._nasceu = time.monotonic()
        self._fim_dito = False
        self._motivo_pedido: str | None = None
        #: Quantas vezes o tamanho, o monitor, a escala ou o estado mudou. Vai ao `[tique lento]`.
        self.mudancas_de_tamanho = 0
        self._tamanho_visto: tuple[int, int, str, int, str] | None = None
        self._tamanho_por_dizer: tuple[int, int, str, int, str] | None = None
        self._tamanho_dito_em = float("-inf")
        self._tamanho_agendado = False

        self.ponte = PonteDaTela(
            canal=canal, ao_receber=ao_receber, ao_recusar=ao_recusar, folha=folha,
            esperar_a_pintura=esperar_a_pintura, tema_de_cores=tema_de_cores,
        )
        self.view = self.ponte.view
        #: O tema ligado se relê quando o registro das extensões muda (só no padrão: a folha
        #: passada por quem abre a janela fica como veio).
        self._vigia_do_tema = (self._vigiar_o_tema()
                               if isinstance(tema_de_cores, _TemaLigado) else None)
        self._cor_da_barra = Gtk.CssProvider()
        self._cor_da_barra.load_from_data(
            css_da_cor_da_barra(self.ponte.tema_de_cores).encode("utf-8"))
        #: O percentual de zoom que a página está usando AGORA (`None` até o primeiro aplicar).
        self.tamanho_aplicado: int | None = None
        self.aplicar_o_tamanho_guardado()
        self._vigia_do_tamanho = self._vigiar_o_tamanho()
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
        pedir_a_variante(self.ponte.tema_de_cores)
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
                titulo, subtitulo or "", self._gesto_da_barra, cor=self._cor_da_barra
            )
            self.janela.set_titlebar(barra)
            self.janela.connect("window-state-event", self._a_barra_se_refaz)
            self.janela.connect("window-state-event", self._o_tamanho_mudou)
            self.janela.connect("configure-event", self._o_tamanho_mudou)
            self.janela.connect("destroy", self._ao_destruir)
        self.janela.add(self.view)
        self.janela.show_all()
        self.view.load_uri(arquivo.as_uri())

    def aplicar_o_tamanho_guardado(self) -> bool:
        """Põe no WebView o zoom que a aba Sistema guardou. Devolve se mudou o zoom."""
        percentual = tamanho_da_interface()
        if percentual == self.tamanho_aplicado:
            return False
        self.view.set_zoom_level(percentual / 100)
        antes, self.tamanho_aplicado = self.tamanho_aplicado, percentual
        if antes is not None:
            print(f"[janela] tamanho da interface: {antes} % -> {percentual} %", file=sys.stderr)
        return True

    def _vigiar_o_tamanho(self) -> Any:
        """Vigia o `interface_escala`: quando a 09 grava, o zoom muda na hora, sem reabrir.

        O gesto da 09 só guarda a escolha (`tamanho_da_interface_gesto`), e a janela é outro
        processo que não recebe aviso dele. O monitor do GIO acorda no `rename` do arquivo
        novo (a gravação é atômica), sem laço e sem tique: não custa nada ao tique de 100 ms.
        """
        arquivo = arquivo_do_tamanho()
        if arquivo is None:
            return None
        try:
            monitor = Gio.File.new_for_path(str(arquivo)).monitor_file(
                Gio.FileMonitorFlags.WATCH_MOVES, None
            )
        except GLib.Error as erro:
            print(f"[janela] tamanho da interface: não consegui vigiar {arquivo} ({erro})",
                  file=sys.stderr)
            return None
        monitor.connect("changed", self._o_arquivo_do_tamanho_mudou)
        return monitor

    def _o_arquivo_do_tamanho_mudou(self, *_args: Any) -> None:
        self.aplicar_o_tamanho_guardado()

    def _vigiar_o_tema(self) -> Any:
        """Vigia o registro das extensões: a chave da Experimental (ou o terminal) grava, e o tema
        troca na hora. A gravação é atômica, e o monitor acorda no `rename`, como no tamanho."""
        from hefesto_dualsense4unix.mods.instalador import Lugares

        registro = Lugares.do_xdg().registro
        try:
            monitor = Gio.File.new_for_path(str(registro)).monitor_file(
                Gio.FileMonitorFlags.WATCH_MOVES, None
            )
        except GLib.Error as erro:
            print(f"[janela] tema: não consegui vigiar {registro} ({erro})", file=sys.stderr)
            return None
        monitor.connect("changed", self._o_registro_das_extensoes_mudou)
        return monitor

    def _o_registro_das_extensoes_mudou(self, *_args: Any) -> None:
        folha = folha_do_tema()
        if folha != self.ponte.tema_de_cores:
            self.trocar_o_tema(folha)

    def trocar_o_tema(self, folha_do_tema: str) -> None:
        """O tema novo na página, na barra e na variante do GTK, sem reabrir a janela."""
        self.ponte.trocar_o_tema(folha_do_tema)
        self._cor_da_barra.load_from_data(css_da_cor_da_barra(folha_do_tema).encode("utf-8"))
        escura = pedir_a_variante(folha_do_tema)
        print(f"[janela] tema: {'ligado' if folha_do_tema else 'desligado'}, variante "
              f"{'escura' if escura else 'clara'}", file=sys.stderr)

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

    def anotar_o_fim(self, motivo: str) -> bool:
        """A linha de fim, UMA vez por vida: o motivo e há quantos segundos a janela estava aberta.

        Todo caminho que encerra o laço passa por aqui antes de `Gtk.main_quit`; quem chega
        depois (o `destroy` que segue o `close`, o fim do laço) não repete. Devolve se escreveu.
        """
        if self._fim_dito:
            return False
        self._fim_dito = True
        aberta = time.monotonic() - self._nasceu
        print(f"[janela] fechou: {motivo} · aberta há {aberta:.0f} s", file=sys.stderr)
        return True

    def _ao_destruir(self, _janela: Any) -> None:
        """A janela foi destruída: o `fechar` já deixou o motivo; sem ele, o pedido veio de fora."""
        self.anotar_o_fim(
            self._motivo_pedido
            or "destroy sem pedido da própria janela (Alt+F4, compositor ou sistema)"
        )
        Gtk.main_quit()

    def fechar_por_sinal(self, sinais: tuple[signal.Signals, ...] = SINAIS_DE_FIM) -> list[int]:
        """Liga ao laço do GLib os sinais que encerram a janela: escreve a linha e sai pelo caminho
        normal (o `finally` do processo devolve o que as abas seguravam). Devolve as fontes.

        O sinal que o processo já recebeu IGNORADO fica ignorado: o lançador nasce com
        `nohup`, que pede a janela de pé quando o terminal fecha, e ligar o SIGHUP ao fim
        desfaria esse pedido."""
        return [
            GLib.unix_signal_add(GLib.PRIORITY_HIGH, int(sinal), self._chegou_o_sinal, int(sinal))
            for sinal in sinais
            if signal.getsignal(sinal) is not signal.SIG_IGN
        ]

    def _chegou_o_sinal(self, numero: int) -> bool:
        """O sinal fecha pelo `fechar`, que destrói a janela (e o GL do WebView) dentro do laço."""
        self.fechar(f"sinal {signal.Signals(numero).name}")
        return False  # GLib.SOURCE_REMOVE: a fonte sai depois do primeiro sinal

    def _o_tamanho_mudou(self, *_args: Any) -> bool:
        """`configure-event` e `window-state-event`: lê a janela como ela está agora."""
        largura, altura = self.janela.get_size()
        self.anotar_o_tamanho(largura, altura)
        return False

    def _o_monitor(self) -> str:
        """O número do monitor em que a janela está, na ordem do `Gdk.Display`, ou `?`."""
        gdk = self.janela.get_window()
        tela = Gdk.Display.get_default()
        if gdk is None or tela is None:
            return "?"
        atual = tela.get_monitor_at_window(gdk)
        for n in range(tela.get_n_monitors()):
            if tela.get_monitor(n) == atual:
                return str(n)
        return "?"

    def anotar_o_tamanho(self, largura: int, altura: int) -> bool:
        """Registra o tamanho, o monitor, a escala e o estado quando algum deles MUDA.

        O deslocamento sem mudança de tamanho (`configure-event` de mover) não escreve nada.
        No máximo uma linha por `SEGUNDOS_ENTRE_LINHAS_DE_TAMANHO`; o resto da rajada sai numa
        linha só, no fim do intervalo. Devolve se algo mudou.
        """
        gdk = self.janela.get_window()
        estado = nome_do_estado(int(gdk.get_state())) if gdk is not None else "normal"
        visto = (largura, altura, self._o_monitor(), int(self.janela.get_scale_factor()), estado)
        if visto == self._tamanho_visto:
            return False
        self._tamanho_visto = visto
        self._tamanho_por_dizer = visto
        self.mudancas_de_tamanho += 1
        espera = self._tamanho_dito_em + SEGUNDOS_ENTRE_LINHAS_DE_TAMANHO - time.monotonic()
        if espera <= 0:
            self._dizer_o_tamanho()
        elif not self._tamanho_agendado:
            self._tamanho_agendado = True
            GLib.timeout_add(int(espera * 1000) + 1, self._dizer_o_tamanho_adiado)
        return True

    def _dizer_o_tamanho_adiado(self) -> bool:
        self._tamanho_agendado = False
        self._dizer_o_tamanho()
        return False

    def _dizer_o_tamanho(self) -> None:
        visto = self._tamanho_por_dizer
        if visto is None:
            return
        self._tamanho_por_dizer = None
        self._tamanho_dito_em = time.monotonic()
        largura, altura, monitor, escala, estado = visto
        print(
            f"[janela] tamanho: {largura}x{altura} · monitor {monitor} · escala {escala}"
            f" · estado {estado}",
            file=sys.stderr,
        )

    def fechar(self, motivo: str = "Fechar da barra ou do menu do botão direito") -> None:
        """Fecha a janela e encerra o laço. É o «Fechar» do menu do botão direito e o da barra."""
        if self.oculta:
            self.anotar_o_fim(motivo)
            Gtk.main_quit()
        else:
            self._motivo_pedido = motivo
            self.janela.close()

    def _gesto_da_barra(self, _botao: Any, gesto: str) -> None:
        """Minimizar, maximizar/restaurar ou fechar, pelos botões desta casa."""
        if gesto == "fechar":
            self.fechar()
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
            # A janela segue aberta, sem página: não é um fim, e a linha diz isso com a idade.
            print(
                f"[janela] sem recarga: o processo web terminou ({nome}) · aberta há "
                f"{time.monotonic() - self._nasceu:.0f} s",
                file=sys.stderr,
            )
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
        self.anotar_o_fim(f"a carga falhou ({motivo})")
        Gtk.main_quit()

    def agendar_saida(self, segundos: float, antes: Callable[[], None] | None = None) -> None:
        """Fecha a janela daqui a N segundos. ``0`` (ou menos) não agenda nada."""
        if segundos <= 0:
            return

        def sair() -> bool:
            if antes is not None:
                antes()
            self.anotar_o_fim(f"o prazo de {segundos:g} s acabou")
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
