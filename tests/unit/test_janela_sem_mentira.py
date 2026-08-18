"""BOTÃO-QUE-NÃO-MENTE-01 (entrega 6) — a janela não pode prometer o que não faz.

A sprint mediu três classes de defeito. Estes testes travam **duas** delas, pela
regra e não pelos casos concretos que as revelaram — quem corrigir os casos deixa
o teste verde, e quem criar um caso novo o deixa vermelho.

1. **Widget fantasma** — controle que fica invisível na partida, sem ninguém no
   código capaz de acendê-lo, e que mesmo assim declara ``<signal>``. Foi o caso
   dos cinco ``player_led_*``: handler vivo, sinal ligado, e nenhum pixel na
   tela. Invisível que declara sinal é dívida — ou o widget volta a existir, ou
   o sinal sai junto com ele.

2. **Tooltip que mente** — texto de ajuda que usa o verbo "desfazer" para um
   clique que não tem desfazer nenhum na janela. Foi o caso do "Este jogo não
   funciona": o tooltip terminava com *"e dá para desfazer"* enquanto a função
   que desmarca (``remove_appid_from_steam_input_allowlist``) não tinha um único
   chamador do lado da interface.

**A terceira classe (adiamento silencioso) NÃO tem teste aqui, e a ausência é
medida, não preguiça.** A regra proposta era "handler cujo corpo só toca o
dicionário de rascunho, sem IPC nem marca de pendente". Rodada sobre o código de
hoje, na forma estrita, ela acusa **zero** handlers — inclusive os dois que a
sprint nomeia (``on_lightbar_color_set`` e ``on_lightbar_brightness_changed``),
porque ambos repintam a prévia e um deles ainda emite aviso em toast. Um teste
que fica verde com a doença inteira presente não testa nada. Afrouxada para
"toca o rascunho e não alcança IPC", ela passa a acusar 26 handlers, entre eles
``on_rumble_apply``, ``on_trigger_left_apply`` e ``on_mouse_speed_changed`` —
que aplicam na hora, alguns por caminho assíncrono a duas chamadas de distância.
Falso positivo em cima de trabalho correto.

O que separa "adiei e avisei" de "adiei calado" não está na forma da chamada:
está no CONTEÚDO da mensagem e no fato de a prévia repintada não ser um aviso de
pendência. Para o teste enxergar isso, ele teria de casar o texto das mensagens
de produção (a dívida de ~71 asserts que esta casa já paga e que proíbe
refatorar) ou fixar por decreto o nome de uma função de "marca de pendente" que a
entrega 1 ainda está escolhendo — o que reprovaria trabalho alheio por escolha de
nome. Fica registrado como o que é: classe conhecida, sem gate honesto disponível
ainda. O caminho que funcionaria é comportamental (dar o gesto e conferir que
alguma coisa fora do próprio widget mudou na tela), e depende de uma superfície
de pendência que ainda não existe.

Os dois testes são estáticos — XML do glade e AST do ``src/``. Mesmo motivo do
``test_glade_signal_handlers.py``: nada de GTK, nada de display, roda na CI sem
PyGObject. Medir layout precisa de ``GtkOffscreenWindow``; medir promessa não.
"""

from __future__ import annotations

import ast
import re
import xml.etree.ElementTree as ET
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]
_GLADE = _RAIZ / "src" / "hefesto_dualsense4unix" / "gui" / "main.glade"
_SRC = _RAIZ / "src" / "hefesto_dualsense4unix"
_APP = _SRC / "app"


# ---------------------------------------------------------------------------
# Leitura do glade
# ---------------------------------------------------------------------------


def _propriedades(obj: ET.Element) -> dict[str, str]:
    """Propriedades DIRETAS do objeto (não desce para os filhos)."""
    return {prop.get("name", ""): (prop.text or "").strip() for prop in obj.findall("property")}


def _pais(raiz: ET.Element) -> dict[ET.Element, ET.Element]:
    """ElementTree não guarda o pai; este mapa devolve a ligação."""
    return {filho: pai for pai in raiz.iter() for filho in pai}


def _cadeia(obj: ET.Element, pais: dict[ET.Element, ET.Element]) -> list[ET.Element]:
    """O objeto e todos os ``<object>`` acima dele, de baixo para cima."""
    cadeia: list[ET.Element] = []
    no: ET.Element | None = obj
    while no is not None:
        if no.tag == "object":
            cadeia.append(no)
        no = pais.get(no)
    return cadeia


def _e_verdadeiro(valor: str) -> bool:
    return valor.strip().lower() in {"true", "yes", "1"}


def _e_falso(valor: str) -> bool:
    return valor.strip().lower() in {"false", "no", "0"}


# ---------------------------------------------------------------------------
# Leitura do código
# ---------------------------------------------------------------------------


def _fontes(diretorio: Path) -> dict[Path, list[str]]:
    return {
        arquivo: arquivo.read_text(encoding="utf-8").splitlines()
        for arquivo in sorted(diretorio.rglob("*.py"))
    }


def _funcoes(diretorio: Path) -> dict[str, list[ast.AST]]:
    """Todas as funções definidas na árvore, indexadas pelo nome."""
    por_nome: dict[str, list[ast.AST]] = {}
    for arquivo in sorted(diretorio.rglob("*.py")):
        try:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover — fonte quebrada tem gate próprio
            continue
        for no in ast.walk(arvore):
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                por_nome.setdefault(no.name, []).append(no)
    return por_nome


def _simbolos(no: ast.AST) -> set[str]:
    """Nomes que a função menciona: atributos, nomes livres e strings literais.

    As strings entram de propósito. O handler do "Este jogo não funciona" pega a
    função de escrita por ``getattr(slo, "add_appid_to_steam_input_allowlist")``
    — quem olhasse só para ``ast.Call`` não veria o nome que interessa.
    """
    achados: set[str] = set()
    for filho in ast.walk(no):
        if isinstance(filho, ast.Attribute):
            achados.add(filho.attr)
        elif isinstance(filho, ast.Name):
            achados.add(filho.id)
        elif isinstance(filho, ast.Constant) and isinstance(filho.value, str):
            achados.add(filho.value)
    return achados


# ---------------------------------------------------------------------------
# Defeito 1 — widget fantasma
# ---------------------------------------------------------------------------

#: Chamadas que fazem um widget oculto aparecer. São API do GTK, não nome de
#: função da casa: refatorar o nosso código não quebra esta lista.
_VERBOS_DE_VISIBILIDADE = (
    "set_visible",
    ".show(",
    "show_all",
    ".hide(",
    "set_reveal_child",
    "set_no_show_all",
)

#: Quantas linhas depois da menção ao id ainda contam como "o mesmo trecho".
#: O padrão da casa gasta duas linhas entre pegar o widget e mexer nele:
#:     btn = self._get("btn_migrate_to_systemd")
#:     if btn is not None:
#:         btn.set_visible(...)
_LINHAS_DE_CONTEXTO = 6


def _pode_ser_aceso(widget_id: str | None, fontes: dict[Path, list[str]]) -> bool:
    """Existe, em ``app/``, código capaz de tornar este widget visível?

    Sem id não há como: o ``Gtk.Builder`` só entrega objeto por nome, então um
    container anônimo com ``visible=False`` é definitivo. Era exatamente o caso
    da caixa dos cinco ``player_led_*``.
    """
    if not widget_id:
        return False
    alvos = (f'"{widget_id}"', f"'{widget_id}'")
    for linhas in fontes.values():
        for i, linha in enumerate(linhas):
            if not any(alvo in linha for alvo in alvos):
                continue
            trecho = linhas[max(0, i - 1) : i + _LINHAS_DE_CONTEXTO]
            if any(
                verbo in linha_vizinha
                for linha_vizinha in trecho
                for verbo in _VERBOS_DE_VISIBILIDADE
            ):
                return True
    return False


def _fantasmas(glade: Path, fontes: dict[Path, list[str]]) -> list[str]:
    """Widgets que declaram sinal dentro de um trecho apagado e insalvável.

    "Apagado" é ``visible=False`` **junto com** ``no-show-all=True``, no próprio
    widget ou em qualquer ancestral. Os dois juntos, e não só o primeiro, porque
    ``app.py`` chama ``show_all()`` na janela: sem ``no-show-all``, o
    ``visible=False`` do glade é desfeito na abertura e o widget aparece.
    """
    raiz = ET.parse(str(glade)).getroot()
    pais = _pais(raiz)
    achados: list[str] = []
    for obj in raiz.iter("object"):
        sinais = [s.get("handler", "?") for s in obj.findall("signal")]
        if not sinais:
            continue
        for ancestral in _cadeia(obj, pais):
            props = _propriedades(ancestral)
            apagado = _e_falso(props.get("visible", "")) and _e_verdadeiro(
                props.get("no-show-all", "")
            )
            if not apagado:
                continue
            if _pode_ser_aceso(ancestral.get("id"), fontes):
                break  # oculto na partida, mas o código sabe acender: legítimo
            quem = obj.get("id") or f"<sem id, {obj.get('class')}>"
            esconde = ancestral.get("id") or f"<sem id, {ancestral.get('class')}>"
            achados.append(f"{quem} (sinais: {', '.join(sinais)}) apagado por {esconde}")
            break
    return achados


def test_widget_invisivel_nao_declara_sinal() -> None:
    """Sinal ligado a widget que ninguém consegue ver é promessa sem tela.

    O custo não é só a linha morta: o handler continua no dict de sinais, o
    inventário continua contando o controle, e o tooltip do botão vizinho chega a
    explicar o widget oculto para quem nunca vai vê-lo — foi o que aconteceu com
    os ``player_led_*``.

    A saída legítima existe e está aferida junto: um widget que nasce oculto e é
    aceso pelo código (``btn_migrate_to_systemd``, que aparece só no estado
    ``online_avulso``) passa, porque tem id e há ``set_visible`` sobre ele.
    """
    achados = _fantasmas(_GLADE, _fontes(_APP))

    assert not achados, (
        "widgets do glade que declaram <signal> dentro de um trecho que nasce "
        "apagado e que nenhum código de app/ consegue acender:\n  - "
        + "\n  - ".join(achados)
        + "\nOu o widget volta para a tela, ou o <signal> sai junto com ele. "
        "Se o trecho precisa mesmo nascer oculto, dê um id ao container e "
        "acenda-o no código (set_visible/show) — é assim que o "
        "btn_migrate_to_systemd passa por aqui."
    )


# ---------------------------------------------------------------------------
# Defeito 2 — tooltip que mente
# ---------------------------------------------------------------------------

#: A palavra que a sprint isolou. O portão é DELIBERADAMENTE cego a negação:
#: tentar distinguir "dá para desfazer" de "não dá para desfazer" por vizinhança
#: não funciona em português. O texto real que motivou a sprint era *"Não fecha a
#: Steam e dá para desfazer"* — uma promessa cujo "Não" está a seis palavras de
#: distância e nega outra coisa. Qualquer janela de negação larga o bastante para
#: pegar "não dá para desfazer" engoliria essa frase também. Logo, a regra é
#: simples: só use o verbo quando ele for verdade. Para avisar que NÃO dá, diga
#: sem ele ("ainda não existe um botão para desmarcar").
_PALAVRA_DE_PROMESSA = "desfazer"

_PROPRIEDADES_DE_AJUDA = (
    "tooltip-text",
    "tooltip-markup",
    "AtkObject::accessible-description",
)

#: Classes cujo texto de ajuda descreve o efeito de um CLIQUE.
_CLICAVEIS = (
    "Button",
    "ToggleButton",
    "CheckButton",
    "RadioButton",
    "MenuItem",
    "Switch",
)

_VERBOS_DE_REMOCAO = (
    "remove",
    "remover",
    "desfaz",
    "undo",
    "delet",
    "apagar",
    "retirar",
    "desmarcar",
    "excluir",
    "limpar",
    "reverter",
)

#: Escritas cujo inverso é um conceito real do produto (tem contraparte).
_VERBOS_DE_ESCRITA = ("add_", "adicionar_", "marcar_", "incluir_")

#: Preposições e artigos não ajudam a parear ``add_x_to_y`` com ``remove_x_from_y``.
_LIGACAO = {
    "to",
    "from",
    "in",
    "on",
    "of",
    "the",
    "a",
    "o",
    "e",
    "de",
    "do",
    "da",
    "no",
    "na",
    "por",
    "para",
    "um",
    "uma",
}

_MENCAO_DE_HANDLER = re.compile(r"self\.(on_[A-Za-z0-9_]+)")


def _textos_de_ajuda(obj: ET.Element) -> list[str]:
    """Tooltip do widget mais a descrição acessível do ``AtkObject`` filho.

    As duas superfícies dizem a mesma coisa para pessoas diferentes; uma mentira
    lida pelo leitor de tela é tão mentira quanto a que aparece no balão.

    Só o que é DO widget: ``iter`` desceria a árvore inteira e faria a
    ``main_window`` responder pelo tooltip de todos os 85 widgets de dentro dela
    — o primeiro falso positivo que este arquivo produziu.
    """
    textos = [
        prop.text or ""
        for prop in obj.findall("property")
        if prop.get("name") in _PROPRIEDADES_DE_AJUDA
    ]
    for filho in obj.findall("child"):
        for acessivel in filho.findall("object"):
            if acessivel.get("class") != "AtkObject":
                continue
            textos += [
                prop.text or ""
                for prop in acessivel.findall("property")
                if prop.get("name") in _PROPRIEDADES_DE_AJUDA
            ]
    return textos


def _trecho_com_a_promessa(texto: str, margem: int = 45) -> str:
    """A vizinhança do verbo, para a falha mostrar a FRASE e não só o id."""
    onde = texto.lower().find(_PALAVRA_DE_PROMESSA)
    if onde < 0:  # pragma: no cover — só chegam aqui textos que contêm o verbo
        return texto.strip()
    inicio = max(0, onde - margem)
    fim = onde + len(_PALAVRA_DE_PROMESSA) + margem
    return " ".join(texto[inicio:fim].split())


def _promessas_de_desfazer(glade: Path) -> list[tuple[str, str, str]]:
    """(id, classe, texto) de cada widget cujo texto de ajuda usa o verbo."""
    raiz = ET.parse(str(glade)).getroot()
    achados: list[tuple[str, str, str]] = []
    for obj in raiz.iter("object"):
        if not obj.get("id"):
            continue
        for texto in _textos_de_ajuda(obj):
            if _PALAVRA_DE_PROMESSA in texto.lower():
                achados.append((obj.get("id", ""), obj.get("class", ""), texto))
                break
    return achados


def _handlers_do_widget(glade: Path, widget_id: str, fontes: dict[Path, list[str]]) -> set[str]:
    """Handlers do widget, pelos DOIS caminhos de fiação que a casa usa.

    Pelo glade (``<signal handler="...">``) e por código — o mixin da aba Sistema
    liga os botões do modo simples em ``_wire_steam_simple_buttons`` justamente
    porque o app conecta sinais por dict literal. Quem olhasse só o glade acharia
    que "Este jogo não funciona" não tem handler nenhum.
    """
    raiz = ET.parse(str(glade)).getroot()
    nomes: set[str] = set()
    for obj in raiz.iter("object"):
        if obj.get("id") != widget_id:
            continue
        nomes.update(s.get("handler", "") for s in obj.findall("signal"))
    alvos = (f'"{widget_id}"', f"'{widget_id}'")
    for linhas in fontes.values():
        for i, linha in enumerate(linhas):
            if not any(alvo in linha for alvo in alvos):
                continue
            # A própria linha primeiro: a fiação por tupla põe id e handler lado
            # a lado, e a janela larga arrastaria junto o handler do BOTÃO
            # VIZINHO da mesma tupla — sobra que só torna o teste mais frouxo.
            na_linha = _MENCAO_DE_HANDLER.findall(linha)
            if na_linha:
                nomes.update(na_linha)
                continue
            # Sem isso, o padrão de duas linhas (pegar o widget, depois
            # `connect`) ficaria invisível.
            nomes.update(_MENCAO_DE_HANDLER.findall("\n".join(linhas[i : i + 4])))
    return {nome for nome in nomes if nome}


def _tokens(nome: str) -> set[str]:
    return {parte for parte in nome.lower().split("_") if parte} - _LIGACAO


def _contraparte_na_janela(
    escrita: str, funcoes: dict[str, list[ast.AST]], fontes_da_app: dict[Path, list[str]]
) -> bool:
    """A função que DESFAZ ``escrita`` existe e a janela alcança ela?

    O pareamento é por vocabulário, não por prefixo: ``add_appid_to_..._allowlist``
    e ``remove_appid_from_..._allowlist`` trocam o verbo E a preposição, então
    trocar ``add_`` por ``remove_`` não acharia nada. Compartilhar três palavras
    de conteúdo acha, e continua achando se alguém renomear o par.
    """
    palavras = _tokens(escrita) - {v.strip("_") for v in _VERBOS_DE_ESCRITA}
    for nome in funcoes:
        if not any(nome.lower().startswith(v) for v in _VERBOS_DE_REMOCAO):
            continue
        if len(_tokens(nome) & palavras) < 3:
            continue
        if any(nome in linha for linhas in fontes_da_app.values() for linha in linhas):
            return True
    return False


def test_tooltip_que_promete_desfazer_tem_de_desfazer() -> None:
    """Quem promete desfazer na tela tem de ter o desfazer NA TELA.

    Três saídas deixam este teste verde, e as três são correções de verdade:
    o próprio handler passa a chamar a remoção; a remoção ganha botão em algum
    lugar de ``app/`` (o inverso é achado por vocabulário, então serve qualquer
    nome sensato); ou o texto para de usar o verbo. A quarta saída — deixar a
    promessa e não entregar — é a única que ele fecha.

    O custo do erro está escrito no próprio código do caso que originou a regra:
    um jogo marcado por engano fica sem cor, gatilhos e co-op do Hefesto até ser
    desmarcado. Prometer que dá para voltar atrás, sem ter como, é pior do que
    admitir que ainda não dá.
    """
    fontes_da_app = _fontes(_APP)
    funcoes_do_projeto = _funcoes(_SRC)
    mentiras: list[str] = []

    for widget_id, classe, texto in _promessas_de_desfazer(_GLADE):
        handlers = _handlers_do_widget(_GLADE, widget_id, fontes_da_app)
        if not handlers:
            if any(c in classe for c in _CLICAVEIS):
                mentiras.append(
                    f"{widget_id} ({classe}) fala em desfazer e não tem handler "
                    "nenhum — nem no glade, nem ligado em código"
                )
            continue

        simbolos: set[str] = set()
        for handler in handlers:
            for corpo in funcoes_do_projeto.get(handler, []):
                simbolos |= _simbolos(corpo)

        if any(simbolo.lower().startswith(v) for simbolo in simbolos for v in _VERBOS_DE_REMOCAO):
            continue  # o próprio clique desfaz

        escritas = sorted(s for s in simbolos if any(s.startswith(v) for v in _VERBOS_DE_ESCRITA))
        if any(_contraparte_na_janela(e, funcoes_do_projeto, fontes_da_app) for e in escritas):
            continue  # o desfazer existe e a janela chega nele

        detalhe = (
            f"escreve {escritas} e o inverso não aparece em app/"
            if escritas
            else "não chama nada que remova nem que escreva algo reversível"
        )
        mentiras.append(
            f"{widget_id} -> {sorted(handlers)}: {detalhe}\n"
            f"      texto: ...{_trecho_com_a_promessa(texto)}..."
        )

    assert not mentiras, (
        "textos de ajuda que usam o verbo 'desfazer' sem desfazer disponível na "
        "janela:\n  - "
        + "\n  - ".join(mentiras)
        + "\nCorrija de um destes três jeitos: chame a remoção no próprio "
        "handler; dê um botão a ela em app/ (o par é achado por vocabulário, "
        "qualquer nome sensato serve); ou tire o verbo do texto e diga o custo "
        "de não ter volta. Mentira na tela é pior que falta."
    )
