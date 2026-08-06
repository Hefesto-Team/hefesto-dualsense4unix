#!/usr/bin/env python3
"""Retrata os DIÁLOGOS de confirmação da leva de perfis — cinco estados.

Irmão do `retratar_abas.py`, para o que ele não alcança: o `retratar_abas.py`
fotografa a JANELA, e diálogo não é aba — nasce por cima, vive um segundo e
some. Três diálogos entraram na leva de perfis (COR-A, SALVAR-NÃO-REBAIXA-02 e
ATIVAR-NÃO-MENTE-01) e **nenhum deles jamais foi visto**, o que deixa o aceite
da PROVA-DE-TELA-01 em aberto: *"interface só fecha com o olho dela"*.

    scripts/gui-captura/retratar_dialogos.py             # atualiza as imagens
                                                         # da documentação
    scripts/gui-captura/retratar_dialogos.py /tmp/olhar  # só olhar, sem tocar
                                                         # no repositório

SÃO CINCO FOTOS, NÃO TRÊS
-------------------------

Dois dos diálogos têm DOIS textos, e a diferença entre eles é a razão de a leva
existir — fotografar só um lado esconderia justamente o defeito curado:

* `confirm_downgrade_match_to_any` sem `regra_atual` diz a frase da COR-A
  ("vale só em programas específicos"); COM `regra_atual` diz o que o perfil É
  hoje. O parâmetro nasceu porque a frase antiga MENTIRIA num perfil
  *"Só manual"*;
* `confirm_discard_pending_edits` sem `editando` mostra o travessão — o caso em
  que a janela não sabe o nome do rascunho e não pode inventar um.

A ROTA: FOTOGRAFAR NO LUGAR DO `run()`, SEM MEXER NA PRODUÇÃO
--------------------------------------------------------------

As três funções em `app/gui_dialogs.py` são monolíticas: montam o
`Gtk.MessageDialog` e chamam `dialog.run()` no fim, que BLOQUEIA até alguém
clicar. Um script que as chamasse simplesmente penduraria.

Havia duas saídas óbvias, e as duas custavam caro:

1. **extrair o corpo para `_montar_*`** e deixar as públicas só com
   `run()/destroy()`. É a refatoração que parece certa, e foi a primeira
   escolha — até a conferência. Quatro asserções desta casa leem o CÓDIGO-FONTE
   das funções públicas com `inspect.getsource` e cairiam todas, porque o
   `_apply_app_theme(` e o `set_default_response(` migrariam para as funções
   novas: `test_gui_dialogs_theme.py` (varredura por função),
   `test_salvar_nao_rebaixa_02_...py:600` e
   `test_ativar_nao_mente_01_...py:332,341`. Consertá-las seria mudar TRÊS
   arquivos de teste para tirar uma foto;
2. **replicar a montagem aqui**, que é o pior dos mundos: a foto vira uma cópia
   que envelhece calada, e o dia em que o texto do produto mudar a documentação
   passa a mentir sem que nada reprove.

A rota escolhida é uma terceira, e ela é MELHOR que a extração no próprio
critério que tornava a extração preferível — "a foto tem de ser do diálogo
REAL": este script troca `Gtk.MessageDialog.run` por uma função que, em vez de
bloquear, FOTOGRAFA o diálogo que está na mão e devolve `CANCEL`. Quem monta o
diálogo continua sendo a função de produção, inteira, sem uma linha de desvio —
nem sequer uma função `_montar_*` de onde a pública pudesse divergir. Produção
não muda; nenhum teste precisa mudar; e a foto é, por construção, o produto.

Nota: com o `run()` trocado o diálogo **nunca chega a ser mostrado** — quem
chama `gtk_widget_show` num `Gtk.Dialog` é o próprio `run()`. Por isso este
script não abre janela nenhuma, nem mesmo se rodar com a sessão dela na tela.

ARMADILHAS QUE ESTE ARQUIVO JÁ PAGOU (não as repita)
-----------------------------------------------------

1. **Sob Xvfb não há gerenciador de janelas.** Um `Gtk.Window` de verdade nunca
   é mapeado e o filho fica 1x1 para sempre — está medido em
   `docs/process/COMO-OLHAR-A-TELA.md`. E `Gtk.OffscreenWindow` não aceita
   `Gtk.Window` como filho. Por isso aqui se reparenta o MIOLO do diálogo
   (`get_child()`: área de conteúdo + área de ação) para uma offscreen.
2. **`Gtk.init_check()` antes de tudo.** Sem ele o `Gtk.MessageDialog` nasce com
   `get_child()` valendo `None`: `GtkDialog` monta o miolo por *template*, e
   template sem GTK inicializado não é construído. A foto saía vazia e o erro
   não dizia por quê.
3. **Fotografar DENTRO do `run()`, não depois.** A função de produção chama
   `dialog.destroy()` na linha seguinte ao `run()`, e `destroy()` leva os filhos
   junto — capturar o diálogo e olhar depois devolve um casco vazio.
4. **`set_size_request()` só vale ANTES do `show_all()`.** Depois de mostrada, a
   offscreen ignora o pedido e fica no tamanho MÍNIMO — o texto quebra em
   coluna estreita e a foto não é o diálogo que ela veria. Aqui se mede a
   largura NATURAL do miolo primeiro, que é o que um gerenciador de janelas
   daria, e só então se mostra.
5. **O nó CSS tem de ser `messagedialog`.** O tema do produto pinta estes
   diálogos em DOIS lugares: a classe `.hefesto-dualsense4unix-window` que o
   `_apply_app_theme` põe no diálogo, e um bloco TOP-LEVEL `messagedialog` no
   `theme.css` — que existe porque o nó `messagedialog` não herda o escopo da
   janela. Uma `Gtk.OffscreenWindow` crua tem nó `window` e perde o segundo
   bloco: os botões saíam sem a borda roxa. A subclasse abaixo declara
   `set_css_name("messagedialog")` e recebe os dois.
6. **Drene o laço mais de uma vez.** Widget sem alocação mede 1x1, e a foto sai
   vazia. O `_assentar()` faz oito passadas de propósito.

PRIVACIDADE — POR QUE ESTA FOTO É SEGURA
-----------------------------------------

Vale aqui a mesma regra do `retratar_abas.py`, pelo mesmo motivo: uma foto da
interface **já vazou o endereço Bluetooth real** dos controles desta máquina, e
a cura foi um borrão à mão — impossível agora que o PNG vai direto para
`docs/usage/assets/`, sem revisão a cada execução.

O risco destes diálogos não é o MAC: é o NOME DE PERFIL. Os três recebem nome
de perfil como argumento, e a tentação é ler os perfis dela do disco para
"deixar a foto real". Os nomes abaixo são os perfis que JÁ VIVEM no
repositório (`assets/profiles_default/`) — publicá-los não conta nada sobre
máquina nenhuma. Este script **nunca fala com o daemon e nunca lê perfil de
disco**, e `tests/unit/test_retrato_dos_dialogos_nao_vaza_dado_real.py` trava
as duas coisas por AST.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(os.environ.get("HEFESTO_RAIZ", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("GDK_BACKEND", "x11")

import gi

gi.require_version("Gtk", "3.0")
# O `Gdk` precisa de versão EXPLÍCITA: importado antes do `Gtk` (a ordem
# alfabética que o formatador impõe), ele cairia no 4.0 e o import quebraria.
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

CSS = RAIZ / "src/hefesto_dualsense4unix/gui/theme.css"

#: O destino padrão é dentro de `docs/usage/assets/`, ao lado das fotos das
#: abas, em pasta própria: diálogo não é aba e não entra no carrossel do README.
DESTINO_DOC = RAIZ / "docs/usage/assets/dialogos"

#: Os perfis que aparecem nas fotos. Os dois são perfis de FÁBRICA, versionados
#: em `assets/profiles_default/` — estão no repositório desde sempre e não
#: contam nada sobre a máquina de ninguém. Trocar um destes por um nome lido do
#: disco dela é exatamente o gesto que o portão irmão reprova.
PERFIL_EDITADO = "sackboy_nativo"
PERFIL_ATIVADO = "coop_local"


def _assentar(vezes: int = 8) -> None:
    """Drena o laço de eventos até o GTK parar de ter o que fazer.

    Mais de uma passada de propósito: a primeira monta, as seguintes deixam o
    tema e as elipses assentarem. Widget medido antes disso reporta 1x1.
    """
    for _ in range(vezes):
        while Gtk.events_pending():
            Gtk.main_iteration()


class _RetratoDeDialogo(Gtk.OffscreenWindow):
    """A offscreen que recebe o miolo do diálogo — com o nó CSS do produto.

    `set_css_name("messagedialog")` é o que faz o bloco top-level
    `messagedialog` do `theme.css` casar aqui. Sem ele o nó seria `window`, e a
    foto perderia metade do tema: fundo, cor de rótulo e a borda roxa dos
    botões vêm daquele bloco, não da classe da janela.
    """

    __gtype_name__ = "HefestoRetratoDeDialogo"


_RetratoDeDialogo.set_css_name("messagedialog")


def _carregar_o_tema() -> str:
    """Põe o `theme.css` do produto na tela, mais a nota sobre a sombra.

    A segunda folha não inventa estilo: ela DESLIGA a margem que o tema do
    sistema reserva para a sombra da janela (o nó `decoration`). Numa janela de
    verdade essa margem é onde o compositor desenha a sombra, e o GTK aloca o
    conteúdo já descontando-a; a `OffscreenWindow` põe o filho em (0,0) e
    ignora a margem, então o fundo saía deslocado 28 px e o título do diálogo
    era desenhado FORA dele. Sombra é justamente o que uma offscreen não
    reproduz — o `retratar_abas.py` diz o mesmo no cabeçalho dele.
    """
    tela = Gdk.Screen.get_default()
    if tela is None:
        return "tema não aplicado (sem tela)"
    try:
        produto = Gtk.CssProvider()
        produto.load_from_path(str(CSS))
        Gtk.StyleContext.add_provider_for_screen(
            tela, produto, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        sem_sombra = Gtk.CssProvider()
        sem_sombra.load_from_data(
            b"messagedialog decoration {"
            b" margin: 0; box-shadow: none; border-radius: 0; }"
        )
        Gtk.StyleContext.add_provider_for_screen(
            tela, sem_sombra, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1
        )
    except Exception as exc:  # tema indisponível não impede a foto
        return f"tema falhou ({exc})"
    return "tema do produto aplicado"


#: Preenchido antes de cada chamada; lido pela função que substitui o `run()`.
#: É a única maneira de o `run()` trocado saber para que arquivo gravar, já que
#: a assinatura dele é fixa (`run(self)`).
_EM_CURSO: dict[str, object] = {}


def _fotografar_em_vez_de_bloquear(dialogo) -> int:  # type: ignore[no-untyped-def]
    """Substitui `Gtk.MessageDialog.run`: fotografa e devolve `CANCEL`.

    Quando esta função roda, o diálogo já está INTEIRO — todas as chamadas de
    montagem (`format_secondary_text`, `add_button`, `set_default_response`)
    vêm antes do `run()` nas três funções de produção. É o instante exato em
    que ela veria o diálogo na tela.

    Devolve `CANCEL` porque é a resposta que não faz nada: as três funções
    traduzem qualquer coisa diferente de `OK` para "não confirmou".
    """
    miolo = dialogo.get_child()
    if miolo is None:
        _EM_CURSO["erro"] = (
            "o diálogo veio sem miolo — falta `Gtk.init_check()`?"
        )
        return int(Gtk.ResponseType.CANCEL)

    # As classes que o diálogo REAL carrega, incluindo a que o
    # `_apply_app_theme` acabou de pôr. Copiadas em vez de escritas à mão: uma
    # lista fixa aqui viraria um segundo dono do tema dos diálogos.
    classes = dialogo.get_style_context().list_classes()
    dialogo.remove(miolo)

    janela = _RetratoDeDialogo()
    for classe in classes:
        janela.get_style_context().add_class(classe)
    janela.add(miolo)

    # Mostrar o MIOLO (não a janela) para poder medi-lo: a largura natural é a
    # que um gerenciador de janelas daria ao diálogo. Medir depois de mostrar a
    # janela não adianta — a offscreen já teria congelado no tamanho mínimo.
    miolo.show_all()
    _assentar(2)
    largura_natural = miolo.get_preferred_width()[1]
    janela.set_size_request(largura_natural, -1)
    janela.show_all()
    _assentar()

    pixbuf = janela.get_pixbuf()
    arquivo = Path(str(_EM_CURSO["arquivo"]))
    pixbuf.savev(str(arquivo), "png", [], [])
    _EM_CURSO["largura"] = pixbuf.get_width()
    _EM_CURSO["altura"] = pixbuf.get_height()
    return int(Gtk.ResponseType.CANCEL)


def _retratos():  # type: ignore[no-untyped-def]
    """(arquivo, o que a foto prova, chamada) — os cinco estados.

    As chamadas são as de PRODUÇÃO, com os argumentos nomeados de propósito: o
    portão irmão confere que `name`, `ativado` e `editando` vêm das constantes
    forjadas deste módulo, e não de um literal solto ou de uma leitura de disco.
    """
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        LABEL_SO_MANUAL,
    )
    from hefesto_dualsense4unix.app.gui_dialogs import (
        confirm_discard_pending_edits,
        confirm_downgrade_match_to_any,
        confirm_downgrade_priority,
    )

    return (
        (
            "rebaixa_prioridade",
            "SALVAR-NÃO-REBAIXA-02: a prioridade que sumia calada",
            lambda: confirm_downgrade_priority(
                None, name=PERFIL_EDITADO, de=191, para=0
            ),
        ),
        (
            "vira_sempre_de_programa_especifico",
            "COR-A: o perfil de jogo que passaria a valer para tudo",
            lambda: confirm_downgrade_match_to_any(
                None, name=PERFIL_EDITADO, regra_atual=None
            ),
        ),
        (
            "vira_sempre_de_so_manual",
            "SALVAR-NÃO-REBAIXA-02: aqui a frase antiga MENTIRIA",
            lambda: confirm_downgrade_match_to_any(
                None, name=PERFIL_EDITADO, regra_atual=LABEL_SO_MANUAL
            ),
        ),
        (
            "descarta_edicao_pendente",
            "ATIVAR-NÃO-MENTE-01: ativar apaga o que ela não salvou",
            lambda: confirm_discard_pending_edits(
                None, ativado=PERFIL_ATIVADO, editando=PERFIL_EDITADO
            ),
        ),
        (
            "descarta_edicao_pendente_sem_nome",
            "ATIVAR-NÃO-MENTE-01: sem nome de rascunho, sai o travessão",
            lambda: confirm_discard_pending_edits(
                None, ativado=PERFIL_ATIVADO, editando=None
            ),
        ),
    )


def main(destino: str | None = None) -> int:
    saida = Path(destino) if destino else DESTINO_DOC
    saida.mkdir(parents=True, exist_ok=True)

    # Antes de qualquer widget: sem isto o `GtkDialog` nasce sem miolo, porque
    # o template dele não é construído (armadilha 2 do cabeçalho).
    if not Gtk.init_check(None)[0]:
        print(
            "ERRO: o GTK não inicializou. Este script precisa de um display; "
            "sem sessão gráfica, rode-o sob `xvfb-run -a`.",
            file=sys.stderr,
        )
        return 1

    print(f"  {_carregar_o_tema()}")
    Gtk.MessageDialog.run = _fotografar_em_vez_de_bloquear

    print(f"\n  {'arquivo':<42} tamanho     o que a foto prova")
    print("  " + "-" * 100)
    falhas = 0
    for nome, prova, chamada in _retratos():
        arquivo = saida / f"dialogo_{nome}.png"
        _EM_CURSO.clear()
        _EM_CURSO["arquivo"] = str(arquivo)
        chamada()

        erro = _EM_CURSO.get("erro")
        largura = int(_EM_CURSO.get("largura", 0) or 0)
        altura = int(_EM_CURSO.get("altura", 0) or 0)
        if erro or largura <= 1 or altura <= 1:
            falhas += 1
            print(
                f"  {arquivo.name:<42} FALHOU      "
                f"{erro or f'a foto saiu {largura}x{altura}'}",
                file=sys.stderr,
            )
            continue
        print(f"  {arquivo.name:<42} {largura:>4}x{altura:<4}  {prova}")

    if falhas:
        print(f"\n  {falhas} foto(s) saíram vazias ou 1x1.", file=sys.stderr)
        return 1

    print(f"\n  5 diálogo(s) em {saida}")
    if saida == DESTINO_DOC:
        print("  as fotos dos diálogos da leva de perfis estão em dia.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else None))
