"""A frase do produto não manda clicar num botão que não existe — VIBRACAO-O-QUE-SOBROU-01.

O DEFEITO, e ele tem nome desde 03/09/2026: **RUM-01**. Os toasts e o rótulo de
estado da vibração mandavam clicar em *"Devolver ao jogo"*; o botão real do
``gui/main.glade`` chamava-se *"Deixar o jogo controlar a vibração"*, e a cura
daquele dia foi um dono só — ``rumble_actions.BTN_GIVE_BACK_TO_GAME`` — para as
duas telas não divergirem no nome.

**O MESMO DEFEITO VOLTOU PELA OUTRA PORTA, e é o que esta régua fecha.** A
janela GTK saiu inteira em 06/09/2026 (``D-0609-GTK-LEVA-INTEIRA``: o
``main.glade`` não está mais no disco) e a interface nova **nunca teve** aquele
botão. O dono continuou apontando para um rótulo que ninguém pode clicar, e
cinco frases do produto mandavam procurá-lo:

===================================================== ==========================
onde                                                  o que mandava clicar
===================================================== ==========================
``rumble_actions.on_rumble_apply``                    "Deixar o jogo controlar a vibração"
``rumble_actions.on_rumble_stop``                     "Deixar o jogo controlar a vibração"
``rumble_actions._update_rumble_state_label`` (x2)    "Deixar o jogo controlar a vibração"
``status_actions._update_rumble_badge``               "aba Rumble → Deixar o jogo…"
===================================================== ==========================

E a varredura desta régua achou **mais três da mesma família**, no mesmo par de
arquivos, que a linha 177 do CSV da paridade não citava:

* ``rumble_actions.texto_do_alcance_da_intensidade`` — *"Ligue “Jogar pelo
  Hefesto” na aba Início"*. **Esta era a única que chega à tela dela HOJE**
  (``app/telas/vibracao.textos_do_estado`` → ``a05_vibracao.pacote``, o bloco
  ``#vib-estado`` da aba Vibração), e mandava procurar DUAS coisas
  inexistentes: uma aba "Início" e um rótulo "Jogar pelo Hefesto";
* ``status_actions._check_initial_poll_fallback`` e ``._render_offline`` —
  *"clique em "Ligar o Hefesto""*, botão que não existe em página nenhuma.

QUEM É O DONO DA RESPOSTA, e por isso esta régua não digita rótulo nenhum
=========================================================================

Os rótulos vêm das **dez páginas publicadas** (``interface/paginas/??-*.html``):
o texto visível de todo ``<button>``, ``<label>``, ``<option>`` e ``<a>``. É a
regra desta casa — *o que tem dono, a régua PERGUNTA ao dono* —, e é o que faz
esta régua envelhecer junto com a tela: renomear um botão no desenho reprova a
frase que o citava pelo nome velho, no mesmo dia.

DUAS LEITURAS INDEPENDENTES, e a segunda alcança o que a primeira não vê
========================================================================

1. **O PRODUTO** (:func:`test_o_produto_so_manda_clicar_em_botao_que_existe`) —
   as frases são obtidas CHAMANDO o produto: ``_update_rumble_state_label`` nos
   dois estados travados, ``_update_rumble_badge``, e as funções puras de
   frase. É o que a tela mostraria.
2. **O FONTE** (:func:`test_nenhuma_frase_do_fonte_manda_a_botao_inexistente`) —
   uma varredura AST dos dois arquivos, com as constantes de módulo resolvidas.
   Ela alcança as frases que hoje nenhuma superfície renderiza (os toasts dos
   `on_rumble_*`, que eram da janela aposentada) — e é por isso que ela existe:
   uma frase que ninguém renderiza **hoje** é exatamente a que apodrece até
   alguém religá-la. Foi assim que *"Alguns jogos derrubam o controle no meio
   da partida"* sobreviveu uma semana com as duas guardas de saída verdes.

**DOCSTRING NÃO É TELA**, e a varredura os pula. Este arquivo e os dois que ele
mede citam os rótulos MORTOS de propósito, como lápide do que custou; uma régua
que reprovasse a própria lápide obrigaria a apagar a história para ficar verde.

A SEGUNDA METADE DESTE ARQUIVO É OUTRA LINHA — e ela fechou por MEDIÇÃO
=======================================================================

A linha 182 do CSV da paridade dizia que, *"com ``rumble.weak/strong`` não-zero
no perfil em disco, o «Aplicar» do rodapé ainda re-manda os dois"* e re-trava a
vibração que o "Parar" soltou (o sintoma que a ABAS-04 curou na janela GTK).
**Medido em 06/09/2026, a premissa não se sustenta em nenhum dos três degraus**
— e :func:`test_o_aplicar_do_rodape_nao_retrava_a_vibracao` é a régua que
impede os três de se desfazerem em silêncio. O laudo está no docstring dela.
"""

from __future__ import annotations

import ast
import re
from functools import lru_cache
from pathlib import Path

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.rumble_actions`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin

RAIZ = Path(__file__).resolve().parents[2]
PAGINAS = (
    RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "paginas"  # (noqa-acento) nome de pasta
)
FONTES = (
    RAIZ / "src/hefesto_dualsense4unix/app/actions/rumble_actions.py",
    RAIZ / "src/hefesto_dualsense4unix/app/actions/status_actions.py",
)

ROTULO_QUE_SAIU_COM_A_JANELA = "Deixar o jogo controlar a vibração"

_MUDOS = re.compile(
    r"<!--.*?-->|<style\b[^>]*>.*?</style>|<script\b[^>]*>.*?</script>",
    re.S | re.I,
)
_TAG = re.compile(r"<[^>]*>", re.S)

_CLICAVEL = re.compile(
    r"<(button|label|option|a)\b[^>]*>(.*?)</\1>", re.S | re.I
)

_ENTRE_ASPAS_TIPOGRAFICAS = re.compile(r"[“”]([^“”]{1,80})[“”]")
_CLIQUE_COM_ASPAS_RETAS = re.compile(
    r"cliqu\w*(?:\s+em)?\s+\"([^\"]{1,80})\"", re.I
)


@lru_cache(maxsize=1)
def rotulos_clicaveis() -> frozenset[str]:
    """O texto visível de tudo que se clica nas dez páginas publicadas."""
    achadas = sorted(PAGINAS.glob("??-*.html"))
    assert len(achadas) == 10, (
        f"achei {len(achadas)} páginas em {PAGINAS} e o produto tem dez — "
        "régua que não acha a tela não mede a tela."
    )
    fora: set[str] = set()
    for pagina in achadas:
        texto = _MUDOS.sub(" ", pagina.read_text(encoding="utf-8"))
        for m in _CLICAVEL.finditer(texto):
            rotulo = " ".join(_TAG.sub(" ", m.group(2)).split())
            if rotulo:
                fora.add(rotulo)
    return frozenset(fora)


def alvos_de_clique(frase: str) -> list[str]:
    """Os rótulos que uma frase manda procurar."""
    alvos = [m.group(1).strip() for m in _ENTRE_ASPAS_TIPOGRAFICAS.finditer(frase)]
    alvos += [m.group(1).strip() for m in _CLIQUE_COM_ASPAS_RETAS.finditer(frase)]
    return [a for a in alvos if a]


def _acusacao(onde: str, frase: str, alvo: str) -> str:
    return (
        f"{onde} manda procurar “{alvo}”, e nenhuma das dez páginas publicadas "
        f"tem esse rótulo clicável.\n"
        f"  a frase: {frase!r}\n"
        f"  o que fazer: nomeie um rótulo que exista (o dono é "
        f"`interface/paginas/`), ou tire a ordem de clique da frase."
    )


class _RotuloEspiao:
    markup = ""

    def set_markup(self, texto: str) -> None:
        self.markup = texto


class _BadgeEspiao:
    def __init__(self) -> None:
        self.markup = ""
        self.tooltip = ""
        self.visivel = False

    def set_markup(self, texto: str) -> None:
        self.markup = texto

    def set_tooltip_text(self, texto: str) -> None:
        self.tooltip = texto

    def show(self) -> None:
        self.visivel = True

    def hide(self) -> None:
        self.visivel = False


class _HostDoBanner(StatusActionsMixin):
    def __init__(self) -> None:
        self._rumble_badge = _BadgeEspiao()


def _ids_dos_docstrings(arvore: ast.Module) -> set[int]:
    """Os docstrings de módulo, classe e função — que NÃO são tela."""
    fora: set[int] = set()
    for no in ast.walk(arvore):
        corpo = getattr(no, "body", None)
        if not isinstance(
            no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        if (
            corpo
            and isinstance(corpo[0], ast.Expr)
            and isinstance(corpo[0].value, ast.Constant)
            and isinstance(corpo[0].value.value, str)
        ):
            fora.add(id(corpo[0].value))
    return fora


def _texto_da_fstring(no: ast.JoinedStr, constantes: dict[str, str]) -> str:
    """A f-string com o que se sabe resolvido; o resto vira ``«?»``."""
    pedacos: list[str] = []
    for parte in no.values:
        if isinstance(parte, ast.Constant) and isinstance(parte.value, str):
            pedacos.append(parte.value)
        elif isinstance(parte, ast.FormattedValue):
            alvo = parte.value
            pedacos.append(
                constantes[alvo.id]
                if isinstance(alvo, ast.Name) and alvo.id in constantes
                else "«?»"
            )
    return "".join(pedacos)


def frases_do_fonte(caminho: Path) -> list[tuple[str, str]]:
    """``[(arquivo:linha, texto)]`` de todo literal que não é docstring."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    docs = _ids_dos_docstrings(arvore)

    constantes: dict[str, str] = {}
    for no in arvore.body:
        if not (
            isinstance(no, ast.Assign)
            and len(no.targets) == 1
            and isinstance(no.targets[0], ast.Name)
        ):
            continue
        if isinstance(no.value, ast.Constant) and isinstance(no.value.value, str):
            constantes[no.targets[0].id] = no.value.value
        elif isinstance(no.value, ast.JoinedStr):
            constantes[no.targets[0].id] = _texto_da_fstring(no.value, constantes)

    saida: list[tuple[str, str]] = []
    nome = caminho.relative_to(RAIZ)
    for no in ast.walk(arvore):
        if isinstance(no, ast.Constant) and isinstance(no.value, str):
            if id(no) not in docs:
                saida.append((f"{nome}:{no.lineno}", no.value))
        elif isinstance(no, ast.JoinedStr):
            saida.append((f"{nome}:{no.lineno}", _texto_da_fstring(no, constantes)))
    return saida


@pytest.mark.parametrize("caminho", FONTES, ids=lambda c: c.name)
def test_nenhuma_frase_do_fonte_manda_a_botao_inexistente(caminho: Path) -> None:
    """MORDE: devolva o rótulo velho ao dono e esta reprova nomeando a linha."""
    rotulos = rotulos_clicaveis()
    culpas = [
        _acusacao(onde, frase, alvo)
        for onde, frase in frases_do_fonte(caminho)
        for alvo in alvos_de_clique(frase)
        if alvo not in rotulos
    ]
    assert not culpas, "\n\n".join(culpas)


