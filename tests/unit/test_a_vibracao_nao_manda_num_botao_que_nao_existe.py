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
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.rumble_actions import (
    BTN_GIVE_BACK_TO_GAME,
    COMO_DEVOLVER_AO_JOGO,
    RumbleActionsMixin,
    texto_do_alcance_da_intensidade,
)
from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin

RAIZ = Path(__file__).resolve().parents[2]
PAGINAS = (
    RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "paginas"  # (noqa-acento) nome de pasta
)
FONTES = (
    RAIZ / "src/hefesto_dualsense4unix/app/actions/rumble_actions.py",
    RAIZ / "src/hefesto_dualsense4unix/app/actions/status_actions.py",
)

#: O rótulo que a janela GTK tinha e a interface nova nunca teve. Ele fica aqui
#: NOMEADO porque é a agulha da mordida: quem devolver este valor ao dono tem de
#: ver esta régua reprovar.
ROTULO_QUE_SAIU_COM_A_JANELA = "Deixar o jogo controlar a vibração"

#: O que se apaga antes de ler a página: o que não é tela.
_MUDOS = re.compile(
    r"<!--.*?-->|<style\b[^>]*>.*?</style>|<script\b[^>]*>.*?</script>",
    re.S | re.I,
)
_TAG = re.compile(r"<[^>]*>", re.S)

#: O que uma pessoa pode clicar numa página desta casa. `<label>` está aqui
#: porque os interruptores da aba Jogar e os chips da fita são `<label>`, não
#: `<button>` — uma régua que só olhasse `<button>` reprovaria a frase que manda
#: pôr o Status em "Ligado", que é o gesto certo.
_CLICAVEL = re.compile(
    r"<(button|label|option|a)\b[^>]*>(.*?)</\1>", re.S | re.I
)

#: COMO SE RECONHECE UMA ORDEM DE CLIQUE. Duas formas, porque o produto escreve
#: as duas: aspas tipográficas (o padrão desta casa) e ``clique em "…"`` com
#: aspas retas, que é como o banner do serviço escreve.
_ENTRE_ASPAS_TIPOGRAFICAS = re.compile(r"[“”]([^“”]{1,80})[“”]")
_CLIQUE_COM_ASPAS_RETAS = re.compile(
    r"cliqu\w*(?:\s+em)?\s+\"([^\"]{1,80})\"", re.I
)


# ---------------------------------------------------------------------------
# O DONO DOS RÓTULOS — as dez páginas publicadas
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# LEITURA 1 — O PRODUTO: as frases obtidas chamando quem as escreve
# ---------------------------------------------------------------------------
class _RotuloEspiao:
    markup = ""

    def set_markup(self, texto: str) -> None:
        self.markup = texto


class _HostDaVibracao(RumbleActionsMixin):
    """O mínimo para o rótulo de estado pintar — o mesmo molde do
    ``test_tela_so_afirma_o_que_sabe_01``."""

    def __init__(self) -> None:
        self.rotulo = _RotuloEspiao()
        self._widgets: dict[str, Any] = {"rumble_state_label": self.rotulo}

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)


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


def frases_do_produto() -> list[tuple[str, str]]:
    """``[(onde, frase)]`` — o que a tela mostraria, obtido do produto."""
    saida: list[tuple[str, str]] = []

    host = _HostDaVibracao()
    for nome, ativo in (("silêncio", [0, 0]), ("fixa", [160, 220])):
        host._update_rumble_state_label(
            {"rumble_passthrough": False, "rumble_active": ativo}
        )
        saida.append((f"o rótulo de estado da vibração ({nome})", host.rotulo.markup))

    banner = _HostDoBanner()
    for nome, ativo in (("silêncio", [0, 0]), ("fixa", [160, 220])):
        banner._update_rumble_badge({"rumble_active": ativo})
        saida.append(
            (f"a dica do aviso de vibração travada ({nome})",
             banner._rumble_badge.tooltip)
        )

    alcance = texto_do_alcance_da_intensidade(
        {"rumble_ff": {"vpads": 0}, "native_mode": False}
    )
    assert alcance, (
        "sem gamepad virtual e sem Conexão Nativa o produto TEM o que dizer — "
        "uma frase vazia aqui significa que a régua deixou de medir a única "
        "destas que chega à aba Vibração hoje."
    )
    saida.append(("o aviso de alcance da intensidade (aba Vibração)", alcance))
    return saida


def test_o_produto_so_manda_clicar_em_botao_que_existe() -> None:
    """MORDE: devolva ``ROTULO_QUE_SAIU_COM_A_JANELA`` ao dono e este reprova."""
    rotulos = rotulos_clicaveis()
    culpas = [
        _acusacao(onde, frase, alvo)
        for onde, frase in frases_do_produto()
        for alvo in alvos_de_clique(frase)
        if alvo not in rotulos
    ]
    assert not culpas, "\n\n".join(culpas)


def test_o_rotulo_da_janela_aposentada_nao_volta() -> None:
    """A agulha, dita pelo nome: o rótulo do botão que saiu com a janela GTK
    não é o rótulo de nada que se clique, e nenhuma frase do produto o cita.

    Ela é redundante com a régua acima **de propósito**: aquela reprova por
    ausência na lista, esta reprova pelo NOME do defeito, e uma acusação que
    nomeia o caso poupa a próxima pessoa de reconstruir a história.
    """
    assert ROTULO_QUE_SAIU_COM_A_JANELA not in rotulos_clicaveis(), (
        "o botão voltou às páginas — se ele existe de novo, esta régua e o "
        "valor de `BTN_GIVE_BACK_TO_GAME` mudam juntos."
    )
    for onde, frase in frases_do_produto():
        assert ROTULO_QUE_SAIU_COM_A_JANELA not in frase, (
            f"{onde} voltou a citar o botão da janela aposentada: {frase!r}"
        )


def test_o_dono_do_rotulo_aponta_para_um_botao_que_existe() -> None:
    """A fiação: a frase pronta do dono cita o rótulo, e o rótulo está na tela."""
    assert BTN_GIVE_BACK_TO_GAME in rotulos_clicaveis()
    assert f"“{BTN_GIVE_BACK_TO_GAME}”" in COMO_DEVOLVER_AO_JOGO
    assert "aba Vibração" in COMO_DEVOLVER_AO_JOGO


# ---------------------------------------------------------------------------
# LEITURA 2 — O FONTE: a varredura AST com as constantes resolvidas
# ---------------------------------------------------------------------------
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
    """A f-string com o que se sabe resolvido; o resto vira ``«?»``.

    Resolver as constantes de módulo é o que dá MORDIDA a esta leitura: sem
    isso o fonte só mostraria ``{COMO_DEVOLVER_AO_JOGO}`` e trocar o valor do
    dono passaria despercebido.
    """
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


def test_a_varredura_do_fonte_realmente_ve_alguma_ordem_de_clique() -> None:
    """Régua da régua: uma varredura que não acha NADA passa por engano.

    É a armadilha do *instrumento de terceiro sem validar* — em 23/08/2026 um
    grafo de 24.684 nós não achou nenhuma das três funções que já se sabia sem
    chamador. Se o dia em que alguém mudar a forma de escrever a instrução
    fizer esta varredura ficar cega, é aqui que se descobre.
    """
    vistos = [
        (onde, alvo)
        for caminho in FONTES
        for onde, frase in frases_do_fonte(caminho)
        for alvo in alvos_de_clique(frase)
    ]
    assert len(vistos) >= 5, (
        f"a varredura só achou {len(vistos)} ordens de clique nos dois "
        "arquivos, e em 06/09/2026 eram oito. Uma régua que parou de ver o "
        "que media dá verde sobre qualquer coisa."  # (noqa-acento: verbo medir, imperfeito)
    )


def test_o_docstring_nao_e_tela_e_a_lapide_pode_citar_o_rotulo_morto() -> None:
    """Guarda (não morde): a história fica escrita sem reprovar.

    Os dois arquivos citam ``ROTULO_QUE_SAIU_COM_A_JANELA`` e *"Ligar o
    Hefesto"* nos docstrings, como lápide do que custou. Se a varredura
    passasse a ler docstring, a única saída verde seria apagar a história — e
    esta casa não apaga decisão medida.
    """
    fonte = FONTES[0].read_text(encoding="utf-8")
    assert ROTULO_QUE_SAIU_COM_A_JANELA in fonte, (
        "a lápide do RUM-01 sumiu do dono; sem ela a próxima pessoa refaz a "
        "medição de 06/09/2026 do zero."
    )
    achados = [
        alvo
        for onde, frase in frases_do_fonte(FONTES[0])
        for alvo in alvos_de_clique(frase)
    ]
    assert ROTULO_QUE_SAIU_COM_A_JANELA not in achados


# ---------------------------------------------------------------------------
# A LINHA 182 — "o Aplicar que retrava", e o que a medição fez com ela
# ---------------------------------------------------------------------------
def test_o_aplicar_do_rodape_nao_retrava_a_vibracao() -> None:
    """A linha 182 do CSV da paridade CAIU por medição — esta é a régua dela.

    O enunciado: *"se o perfil no disco tiver ``rumble.weak/strong`` não-zero,
    um «Aplicar» do rodapé re-manda esses valores e re-trava a vibração que o
    «Parar» da coluna acabou de soltar"*. Medido em 06/09/2026, os TRÊS
    degraus do caminho recusam o sintoma, e esta régua guarda os três:

    1. **o perfil no disco não pode ter esses campos.** ``RumbleConfig`` tem
       ``extra="forbid"`` e três campos (``passthrough``, ``policy``,
       ``custom_mult``); ``{"weak": 160}`` sai com *Extra inputs are not
       permitted*;
    2. **o draft do «Aplicar» nasce zerado, e não do disco.**
       ``DraftConfig.from_profile`` constrói ``RumbleDraft()`` sem tocar em
       ``weak``/``strong`` — o comentário dele já dizia *"weak/strong não
       persistem no perfil (teste de motores)"*. O ``rodape.aplicar`` da
       interface nova chama ``_draft_do_ativo(nome)`` **sem** o ``ctx``, então
       nem o estado vivo entra: a seção que viaja é sempre ``{0, 0}``;
    3. **e ``{0, 0}`` no «Aplicar» é o oposto de travar.** É a
       ``BUG-RUMBLE-APPLY-KILLS-GAME-01``, escrita no próprio
       ``ipc_draft_applier._apply_rumble``: com o par zerado ele faz
       ``rumble_active = None`` (passthrough) e manda ``set_rumble(0, 0)`` uma
       vez, para SOLTAR um rumble contínuo anterior.

    Medido com ``rumble_active = (160, 220)`` — a vibração travada em valor
    não-zero, o pior caso do enunciado: depois da seção o daemon fica em
    ``rumble_active = None``. Ele solta; não re-trava.

    **A quarta perna, que o enunciado nem cita**, é a mesma resposta:
    ``passthrough=False`` no disco também não re-trava, porque
    ``Daemon.apply_profile_rumble_passthrough`` abre com ``if not passthrough:
    return``.
    """
    from hefesto_dualsense4unix.app.draft_config import DraftConfig
    from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier
    from hefesto_dualsense4unix.profiles.schema import (
        MatchAny,
        Profile,
        RumbleConfig,
    )

    # 1 — o disco não guarda o par
    with pytest.raises(Exception, match=r"[Ee]xtra"):
        RumbleConfig.model_validate({"weak": 160, "strong": 220})

    # 2 — o draft do "Aplicar" nasce zerado
    perfil = Profile(
        name="ensaio-da-regua",
        match=MatchAny(type="any"),
        rumble=RumbleConfig(passthrough=False, policy="max"),
    )
    secao = DraftConfig.from_profile(perfil).to_ipc_dict()["rumble"]
    assert secao == {"weak": 0, "strong": 0}, (
        f"o «Aplicar» passou a mandar {secao} — se o par voltar a vir do "
        "disco, o sintoma da ABAS-04 volta com ele."
    )

    # 3 — e o par zerado SOLTA a vibração travada, em vez de re-travá-la
    class _Config:
        rumble_active: Any = (160, 220)
        rumble_active_uniq: Any = "aa:bb:cc:00:00:01"
        rumble_policy = None
        rumble_policy_custom_mult = None
        native_mode = False

    class _Daemon:
        config = _Config()
        native_mode = False

    class _Controle:
        def __init__(self) -> None:
            self.escritas: list[tuple[int, int]] = []

        def set_rumble(self, weak: int, strong: int) -> None:
            self.escritas.append((weak, strong))

    daemon, controle = _Daemon(), _Controle()
    DraftApplier(controller=controle, store=None, daemon=daemon)._apply_rumble(secao)

    assert daemon.config.rumble_active is None, (
        "o «Aplicar» re-travou a vibração — é o sintoma que a linha 182 "
        "descrevia, e ele voltou."
    )
    assert controle.escritas == [(0, 0)]
