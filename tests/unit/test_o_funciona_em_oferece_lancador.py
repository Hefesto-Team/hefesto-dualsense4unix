"""«Funciona em:» diz DE ONDE O JOGO VEM, e o produto casa sozinho.

C4-FUNCIONA-EM, 11/09/2026. O desenho é DELA, confirmado com todas as letras
(*"isso mesmo."*), e a ordem original foi esta:

    "seria legal nome do programa launcher aqui: A gente adicionaria  # noqa-acento: citação dela
     Navegação, remopve jogo da steam, jogo, jogo pela janela, estilo de jogo,
     e colocariamos os launchers. Isso deveria ajudar a identificar mais rápido
     o nome do jogo depois"

O QUE ESTE ARQUIVO MEDE, e cada bloco tem a sua mordida escrita:

1. **o campo oferece procedências**, e a lista sai do CENSO — nunca digitada;
2. **a máquina sem lançador nenhum** sai com «Navegação» e «Qualquer jogo» e
   nada mais. É a ordem dela do mesmo dia: *"a ideia é que todas as
   features mesmo do app funcionem nao so pra mim mas pra qualquer  (noqa-acento)
   outro user"*;
3. **o caminho de volta** — um perfil que já existe continua sendo mostrado, e
   isso inclui os dois do disco dela que nenhum catálogo conhece;
4. **o clique**, pelo gesto que o dedo dela aciona, com o `MatchCriteria`
   LIDO DE VOLTA DO DISCO;
5. **o jargão saiu** das duas telas — o desenho e a página publicada.

**NENHUMA RÉGUA AQUI TOCA A BIBLIOTECA DELA.** O lar de mentira da suíte é um
espelho por symlink, então `Path.home()` num teste alcançaria o Heroic de
verdade: ou se passa `lar=tmp_path`, ou se substitui a fonte.
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
if str(RAIZ / "src") not in sys.path:  # pragma: no cover - trava de caminho
    sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.integrations import jogos_locais as jl
from hefesto_dualsense4unix.integrations.censo_dos_lancadores import (
    sabe_ler,
)
from hefesto_dualsense4unix.interface.pacotes import (
    Contexto,
    a10_perfis as a10,
)
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles import simple_match as sm
from hefesto_dualsense4unix.profiles.slug import slugify
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    Profile,
)

HEROIC_ID = "com.heroicgameslauncher.hgl"

#: O jogo baixado dela, com os campos EXATOS que o disco trouxe em 10/09/2026.
BAIXADO: dict[str, Any] = {
    "app_name": "63a665088eb1480298f1e57943b225d8",
    "title": "Marvel's Guardians of the Galaxy",
    "is_installed": True,
    "install": {"executable": "retail/gotg.exe",
                "install_path": "/casa/Games/Heroic/MarvelGOTG",
                "is_dlc": False},
}

#: A MESA — endereço MASCARADO (octetos 4 e 5 zerados).
MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1, "cor": "cosmic-red",
     "nome": "Cosmic Red", "via": "USB", "transporte": "usb", "alvo": True,
     "mascara": "DualSense"},
]


class PonteDeMentira:
    """Daemon calado: o gesto grava no disco e nada é reaplicado."""

    def profile_switch(self, nome: str) -> bool:
        return True

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
        return True

    def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
        return {}


def _ctx() -> Contexto:
    return Contexto(state={"active_profile": None}, mesa=list(MESA),
                    conectados=list(MESA), estados={})


def _heroic(lar: pathlib.Path, itens: list[dict[str, Any]]) -> None:
    """A biblioteca do Heroic num lar de mentira."""
    alvo = (lar / ".var/app" / HEROIC_ID / "config/heroic/store_cache"
            / "legendary_library.json")
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(json.dumps({"library": itens}), encoding="utf-8")


@pytest.fixture(autouse=True)
def _caderno_limpo(monkeypatch: pytest.MonkeyPatch) -> None:
    """O caderno das janelas é memoizado no DONO — zerá-lo é obrigatório.

    Sem isto, a primeira régua que ler o catálogo congela a resposta para as
    seguintes, e uma máquina "sem lançador nenhum" herdaria o Heroic da régua
    anterior. É a mesma trava que as réguas da sprint dos lançadores já usam.
    """
    monkeypatch.setattr(jl, "_NOMES_DAS_JANELAS", None, raising=False)
    monkeypatch.setattr(a10, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10, "_ARMADO", None, raising=False)
    monkeypatch.setattr(a10, "_ARMADO_REBAIXAR", None, raising=False)
    monkeypatch.setattr(a10, "_DESFECHO", None, raising=False)


@pytest.fixture
def maquina_pelada(monkeypatch: pytest.MonkeyPatch,
                   tmp_path: pathlib.Path) -> pathlib.Path:
    """UMA MÁQUINA SEM NADA: sem Steam, sem Heroic, sem Lutris, sem `.desktop`.

    É o computador de quem instalou o Hefesto hoje, e é o caso que a ordem dela
    de 11/09/2026 exige que funcione. As duas origens são apontadas para um
    `tmp_path` vazio — e a da Steam some pelo dublê, porque ela não passa por
    `lar` nenhum na chamada da aba.
    """
    vazio = tmp_path / "lar-pelado"
    vazio.mkdir()
    de_verdade, assinar = jl.jogos_com_janela, jl.assinatura_das_janelas
    monkeypatch.setattr(jl, "jogos_com_janela",
                        lambda *_a, **_k: de_verdade(lar=vazio, pastas=[vazio]))
    monkeypatch.setattr(jl, "assinatura_das_janelas",
                        lambda *_a, **_k: assinar(lar=vazio, pastas=[vazio]))
    monkeypatch.setattr(a10, "_nomes_dos_jogos", lambda: {})
    return vazio


@pytest.fixture
def maquina_dela(monkeypatch: pytest.MonkeyPatch,
                 tmp_path: pathlib.Path) -> pathlib.Path:
    """A MÁQUINA COM DUAS ORIGENS: o Heroic com o jogo baixado, e a Steam.

    O lado da Steam é dublê porque ele já tem régua própria — o que se mede
    aqui é o campo que passou a somar as duas.
    """
    lar = tmp_path / "lar-dela"
    lar.mkdir()
    _heroic(lar, [BAIXADO])
    de_verdade, assinar = jl.jogos_com_janela, jl.assinatura_das_janelas
    monkeypatch.setattr(jl, "jogos_com_janela",
                        lambda *_a, **_k: de_verdade(lar=lar, pastas=[lar]))
    monkeypatch.setattr(jl, "assinatura_das_janelas",
                        lambda *_a, **_k: assinar(lar=lar, pastas=[lar]))
    monkeypatch.setattr(a10, "_nomes_dos_jogos",
                        lambda: {"1245620": "ELDEN RING"})
    return lar


def _o_disco_tem(monkeypatch: pytest.MonkeyPatch, *perfis: Any) -> list[Any]:
    todos = list(perfis)
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: todos)
    monkeypatch.setattr(
        loader, "load_profile",
        lambda nome, *a, **k: next(p for p in todos if p.name == nome))
    return todos


def _aberto_no_editor(monkeypatch: pytest.MonkeyPatch, prof: Any) -> None:
    """O perfil que o editor abriu — o que o clique na linha da lista deixa.

    Sem ele os gestos recusam dizendo *"escolha um perfil na lista primeiro"*,
    que é a guarda certa e não é o que estas réguas medem.
    """
    monkeypatch.setattr(a10, "_ESCOLHIDO", prof.name, raising=False)


def _do_disco(prof: Any) -> dict[str, Any]:
    """O ARQUIVO, lido de volta — e é o de verdade, no lar de mentira da suíte.

    O nome sai de `slugify`, que é o mesmo que `loader._profile_path` usa:
    digitar `elden-ring.json` aqui faria a régua medir um arquivo que o produto
    nunca escreve, e o `FileNotFoundError` se leria como "não gravou".
    """
    caminho = loader.profiles_dir() / f"{slugify(prof.name)}.json"
    return json.loads(caminho.read_text(encoding="utf-8"))


def _escolher(rotulo: str) -> dict[str, Any]:
    """O clique que o piloto manda: o `value` do `<select>` e o evento."""
    return {"valor": rotulo, "rotulo": rotulo, "evento": "change",
            "tipo": "select"}


def _opcoes(html: str) -> list[str]:
    """Os textos das `<option>` de um bloco, na ordem — sem o `—` desabilitado."""
    import re

    return [t for t in re.findall(r"<option[^>]*>([^<]*)</option>", html)
            if t != a10.TRAVESSAO]


# ---------------------------------------------------------------------------
# 1. O CAMPO OFERECE PROCEDÊNCIAS, e a lista sai do censo
# ---------------------------------------------------------------------------
def test_o_campo_oferece_de_onde_o_jogo_vem(
    maquina_dela: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """«Navegação» · os lançadores que a máquina tem · «Qualquer jogo».

    MORDIDA: tire o `SELETOR_DO_AMBIENTE` do `fora["blocos"]` de `pacote()` e
    o campo volta a mostrar os lançadores do DESENHO — a tela afirmando que
    esta máquina tem Lutris e RetroArch, que ela não tem.
    """
    _o_disco_tem(monkeypatch,
                 Profile(name="GOTG", priority=80,
                         match=MatchCriteria(window_class=["gotg.exe"])))

    blocos = a10.pacote(_ctx())["blocos"]

    assert _opcoes(blocos[a10.SELETOR_DO_AMBIENTE]) == [
        "Navegação", "Steam", "Heroic", "Qualquer jogo"]
    # E O LUTRIS NÃO ESTÁ LÁ, que é a metade que importa: a lista não é
    # digitada, e um lançador que a máquina não tem não aparece.
    assert "Lutris" not in blocos[a10.SELETOR_DO_AMBIENTE]


def test_a_maquina_sem_lancador_nenhum_sai_com_as_duas_fixas(
    maquina_pelada: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """**A ORDEM DELA:** o produto é para qualquer pessoa, não para esta bancada.

    Sem Steam, sem Heroic e sem Lutris o campo sai com «Navegação» e «Qualquer
    jogo» — sem linha vazia, sem erro, e sem uma palavra que pressuponha Steam.

    MORDIDA: cave `PROCEDENCIA_DA_STEAM` dentro de `oferta_do_funciona_em` (ou
    troque `_procedencias_da_maquina` por uma lista escrita à mão) e a régua
    reprova: quem acabou de instalar ganha uma opção que não leva a lugar
    nenhum.
    """
    _o_disco_tem(monkeypatch, Profile(name="Universal", priority=0,
                                      match=MatchAny()))

    blocos = a10.pacote(_ctx())["blocos"]

    assert _opcoes(blocos[a10.SELETOR_DO_AMBIENTE]) == [
        "Navegação", "Qualquer jogo"]
    assert _opcoes(blocos[a10.SELETOR_DO_AMBIENTE]) == sm.oferta_do_funciona_em([])
    # E A LISTA DE BAIXO SAI VAZIA, sem uma `<option>` em branco: um campo que
    # oferece uma linha vazia é pior que um campo que não oferece nada.
    assert blocos[a10.SELETOR_DOS_JOGOS] == ""
    # O TRAVESSÃO CONTINUA LÁ, e ele não é uma procedência: é onde o piloto
    # pousa o `—` de um perfil cuja regra a tela não sabe mostrar.
    assert (f'<option value="{a10.TRAVESSAO}" disabled>'
            in blocos[a10.SELETOR_DO_AMBIENTE])


def test_a_procedencia_do_perfil_entra_mesmo_desinstalado(
    maquina_pelada: pathlib.Path,
) -> None:
    """Ela desinstalou o Heroic; o perfil do jogo dele continua no disco.

    Um ``<select>`` só mostra o que oferece. Sem esta linha o campo cairia para
    a primeira opção — a tela AFIRMANDO uma regra que o arquivo não tem, que é
    o mesmo defeito que o travessão veio curar em 04/09/2026.

    MORDIDA: tire o `atual` de `oferta_do_funciona_em` e a lista volta sem ele.
    """
    assert sm.oferta_do_funciona_em([], "Heroic") == [
        "Navegação", "Heroic", "Qualquer jogo"]
    # E ELE NÃO ENTRA DUAS VEZES quando já está na lista da máquina.
    assert sm.oferta_do_funciona_em(["Steam"], "Steam") == [
        "Navegação", "Steam", "Qualquer jogo"]


def test_os_lancadores_que_a_tela_ordena_o_censo_sabe_ler() -> None:
    """A ordem declarada não pode citar um lançador que não existe.

    `ORDEM_DOS_LANCADORES` é digitada (e tem de ser — ver a docstring dela), e
    uma lista digitada envelhece. A régua não compara texto com texto: ela
    PERGUNTA ao censo se aquele nome é um lançador que ele sabe ler.

    MORDIDA: acrescente `"GOG"` à ordem e isto reprova — a GOG é uma LOJA
    dentro do Heroic, não um lançador com biblioteca própria.
    """
    for nome in a10.ORDEM_DOS_LANCADORES:
        assert nome == sm.PROCEDENCIA_DA_STEAM or sabe_ler(nome), (
            f"“{nome}” está na ordem do campo «Funciona em:» e o censo não "
            f"sabe ler a biblioteca dele — ou ele mudou de nome, ou ele nunca "
            f"foi um lançador")


# ---------------------------------------------------------------------------
# 2. O CAMINHO DE VOLTA — o perfil que já existe continua sendo mostrado
# ---------------------------------------------------------------------------
def test_o_perfil_que_ja_existe_diz_de_onde_ele_vem(
    maquina_dela: pathlib.Path,
) -> None:
    """As cinco leituras, e as duas últimas são o disco DELA de 11/09/2026.

    Medido nos 27 perfis dela: 25 são `steam_game`, um é `game` (``guard``) e
    um é `janela` (``Hefesto-Dualsense4Unix``). Os dois últimos são exatamente
    os que dependem do residual para não abrirem travados — e a §5 manda o
    perfil de forma escolhida à mão continuar válido e mostrado.

    MORDIDA: devolva `None` no ramo `("game", "janela")` de
    `procedencia_do_match` e os dois perfis dela abrem com o cadeado aceso,
    sem gesto nenhum, sobre regras que funcionam.
    """
    def vem_de(match: Any) -> str | None:
        return sm.procedencia_do_match(match, a10._lancador_da_chave)

    assert vem_de(MatchCriteria(window_class=["steam_app_1245620"])) == "Steam"
    assert vem_de(MatchCriteria(process_name=["steam"])) == "Steam"
    assert vem_de(MatchAny()) == "Qualquer jogo"
    assert vem_de(sm.SIMPLE_MATCH_PRESETS["browser"]) == "Navegação"
    # O jogo do Heroic, pela chave que a janela dele anuncia.
    assert vem_de(MatchCriteria(window_class=["gotg.exe"])) == "Heroic"
    # E OS DOIS DO DISCO DELA que catálogo nenhum conhece.
    assert vem_de(MatchCriteria(process_name=["guard"])) == jl.LANCADOR_DIRETO
    assert vem_de(
        MatchCriteria(window_class=["Hefesto-Dualsense4Unix"])
    ) == jl.LANCADOR_DIRETO


def test_a_regra_que_a_tela_nao_sabe_mostrar_continua_travando(
    maquina_dela: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A válvula do R-12 não morreu — ela só passou a falar a língua nova.

    Sete dos nove perfis de fábrica casam por título de janela ou por lista de
    classes, e nenhuma procedência descreve isso. O campo vai travado com a
    frase do que a regra É, e o `match` do disco fica intacto.

    MORDIDA: faça `_procedencia_e_recado` devolver «Instalado aqui» quando
    `procedencia_do_match` diz `None` e o cadeado apaga sobre uma regra que o
    campo não sabe mostrar — o gesto seguinte a rebaixaria.
    """
    fino = MatchCriteria(window_title_regex="Elden Ring.*",
                         process_name=["eldenring.exe"])
    _o_disco_tem(monkeypatch, Profile(name="Fino", priority=90, match=fino))

    fora = a10.pacote(_ctx())

    assert fora["editor.ambiente"] == ""
    assert fora["editor.ambiente.travado"] is True
    assert "título de janela" in fora["editor.ambiente.recado"]


# ---------------------------------------------------------------------------
# 3. O CAMPO DE BAIXO — os jogos DAQUELE lançador, pelo nome
# ---------------------------------------------------------------------------
def test_a_lista_de_baixo_segue_o_campo_de_cima(
    maquina_dela: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Escolhido «Heroic», o campo «Nome do Jogo» oferece os jogos do Heroic.

    É o efeito que ela pediu com todas as letras: *"Isso deveria ajudar a
    identificar mais rápido o nome do jogo depois"*.

    MORDIDA: tire o filtro por procedência de `_html_dos_jogos` e a lista volta
    a oferecer o `ELDEN RING` da Steam com «Heroic» escolhido no campo de cima
    — duas afirmações contraditórias na mesma tela.
    """
    do_heroic = a10._html_dos_jogos("Heroic")
    da_steam = a10._html_dos_jogos("Steam")

    assert "gotg.exe" in do_heroic and "1245620" not in do_heroic
    assert "1245620" in da_steam and "gotg.exe" not in da_steam
    # AS DUAS FIXAS NÃO FILTRAM, e é a saída que `editor_jogo` documenta:
    # digitar um jogo com o perfil em «Qualquer jogo» é como ela DIZ que aquele
    # perfil é daquele jogo. Esvaziar a lista prenderia o perfil onde está.
    inteira = a10._html_dos_jogos("Qualquer jogo")
    assert "gotg.exe" in inteira and "1245620" in inteira


def test_a_linha_da_lista_diz_nome_e_codigo_e_nunca_o_executavel(
    maquina_dela: pathlib.Path,
) -> None:
    """``ELDEN RING · 1245620``, e nunca ``eldenring.exe`` — item 12 da lista dela.

    A queixa é da foto 9: a linha trazia o número sozinho, que não diz nada a
    ninguém, nem a ela daqui a um mês.

    O jogo de lançador sai só com o NOME: o "código" dele é o basename do
    executável, que é exatamente o que a foto manda nunca mostrar.

    MORDIDA: devolva `jogo.rotulo` em `_linha_do_jogo` e a linha volta a
    `ELDEN RING (appid 1245620)` — o número com a palavra `appid` colada, que
    é jargão, e o parêntese que ela não pediu.
    """
    html = a10._html_dos_jogos("Steam")
    assert 'label="ELDEN RING · 1245620"' in html
    assert ".exe" not in html

    do_heroic = a10._html_dos_jogos("Heroic")
    assert 'label="Marvel&#x27;s Guardians of the Galaxy"' in do_heroic or (
        "label=\"Marvel's Guardians of the Galaxy\"" in do_heroic)
    # O `value` CONTINUA SENDO O ENDEREÇO, e isso não é descuido: é o que o
    # campo grava, e trocá-lo pelo nome faria nascer um `steam_app_Sea of
    # Stars`, que nunca casa com janela nenhuma. O que ela LÊ é o `label`.
    assert 'value="gotg.exe"' in do_heroic


# ---------------------------------------------------------------------------
# 4. O CLIQUE — e o `MatchCriteria` lido de volta do disco
# ---------------------------------------------------------------------------
def test_escolher_o_lancador_grava_a_forma_que_ele_entrega(
    maquina_dela: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O gesto que o dedo dela aciona, e o arquivo LIDO DE VOLTA.

    Ela escolhe «Heroic» num perfil que estava em «Qualquer jogo» com o jogo
    já no campo de baixo; o produto decide sozinho que a forma daquele lançador
    é a `wm_class`, e o disco recebe `window_class: ["gotg.exe"]` — **nunca um
    tipo novo de casamento**, que é a regra do §4.

    MORDIDA: faça `forma_da_procedencia` devolver `"game"` para um lançador e
    o disco passa a guardar `process_name`, que é outro dado e casa por acaso —
    a família do R-12 que esta casa já pagou.
    """
    prof = Profile(name="Guardioes", priority=80,
                   match=MatchCriteria(window_class=["gotg.exe"]))
    _o_disco_tem(monkeypatch, prof)
    _aberto_no_editor(monkeypatch, prof)
    # A REGRA VAI PARA «Qualquer jogo» primeiro, para o clique ter o que mudar.
    prof.match = MatchAny()
    monkeypatch.setattr(a10, "_editor_de",
                        lambda _p: {"jogo": "gotg.exe", "ambiente_recado": ""})

    resposta = a10.editor_ambiente(_ctx(), _escolher("Heroic"), PonteDeMentira())

    assert resposta is not None
    assert "Heroic" in resposta["mesa"]["perfis.desfecho"]
    # O DISCO, LIDO DE VOLTA — e é o arquivo de verdade, no lar de mentira da
    # suíte. Nada aqui inspeciona o objeto em memória.
    do_disco = _do_disco(prof)
    assert do_disco["match"] == {"type": "criteria",
                                 "window_class": ["gotg.exe"],
                                 "window_title_regex": None,
                                 "process_name": []}


def test_escolher_a_steam_com_o_numero_no_campo_grava_o_steam_app(
    maquina_dela: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """«Steam» + «ELDEN RING · 1245620» → ``steam_app_1245620``. É o §4, literal.

    MORDIDA: mande `forma_da_procedencia` devolver sempre `"janela"` e o disco
    guarda `window_class: ["1245620"]` — uma regra que nunca casa.
    """
    prof = Profile(name="Elden Ring", priority=85, match=MatchAny())
    _o_disco_tem(monkeypatch, prof)
    _aberto_no_editor(monkeypatch, prof)
    monkeypatch.setattr(a10, "_editor_de",
                        lambda _p: {"jogo": "1245620", "ambiente_recado": ""})

    a10.editor_ambiente(_ctx(), _escolher("Steam"), PonteDeMentira())

    do_disco = _do_disco(prof)
    assert do_disco["match"]["window_class"] == ["steam_app_1245620"]


def test_a_mesma_procedencia_nao_reescreve_a_forma_do_perfil(
    maquina_dela: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clicar na opção que JÁ está lá não pode trocar `process_name` por `wm_class`.

    O perfil ``guard`` dela casa por nome de programa e aparece como «Instalado
    aqui». «Instalado aqui» escreve `wm_class` quando ela escolhe um jogo da
    lista — então, sem esta guarda, um gesto que não mudou nada na tela
    trocaria o dado no disco por outro que *"casa por acaso"*.

    MORDIDA: tire o `if rotulo == agora: return None` de `editor_ambiente` e a
    régua reprova com `window_class: ["guard"]` no arquivo.
    """
    gravados: list[Any] = []
    monkeypatch.setattr(loader, "save_profile",
                        lambda prof, **kw: gravados.append(prof))
    prof = Profile(name="Guard", priority=50,
                   match=MatchCriteria(process_name=["guard"]))
    _o_disco_tem(monkeypatch, prof)
    _aberto_no_editor(monkeypatch, prof)
    monkeypatch.setattr(a10, "_editor_de",
                        lambda _p: {"jogo": "guard", "ambiente_recado": ""})

    assert a10.editor_ambiente(
        _ctx(), _escolher(jl.LANCADOR_DIRETO), PonteDeMentira()) is None
    assert gravados == []
    assert prof.match.process_name == ["guard"]


def test_trocar_para_um_lancador_sem_o_jogo_manda_ela_para_a_lista(
    maquina_dela: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uma frase pela metade não vira regra — e a recusa diz onde terminar.

    Escolher «Heroic» com o campo de baixo em branco (ou com um jogo de outro
    lugar) é dizer meia coisa: o endereço que está lá não vale naquele
    lançador. Gravar assim mesmo faria nascer uma regra que nunca casa.

    MORDIDA: tire o `raise` e o perfil passa a guardar
    `window_class: ["1245620"]` — o número da Steam gravado como classe de
    janela, calado.
    """
    gravados: list[Any] = []
    monkeypatch.setattr(loader, "save_profile",
                        lambda prof, **kw: gravados.append(prof))
    prof = Profile(name="Elden Ring", priority=85,
                   match=MatchCriteria(window_class=["steam_app_1245620"]))
    _o_disco_tem(monkeypatch, prof)
    _aberto_no_editor(monkeypatch, prof)
    monkeypatch.setattr(a10, "_editor_de",
                        lambda _p: {"jogo": "1245620", "ambiente_recado": ""})

    with pytest.raises(RuntimeError) as erro:
        a10.editor_ambiente(_ctx(), _escolher("Heroic"), PonteDeMentira())

    assert "Escolha o jogo na lista de baixo" in str(erro.value)
    assert "Heroic" in str(erro.value)
    assert gravados == []


def test_a_navegacao_grava_o_preset_dos_navegadores(
    maquina_dela: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """«Navegação» é o perfil do desktop, sem jogo — e ele já existia no produto.

    O preset `browser` estava em `perfis_web.FORA_DO_DESENHO` desde que a
    interface nova nasceu: *"existe no produto e não no desenho dela"*. Esta
    sprint o traz para a tela com a palavra DELA.

    MORDIDA: tire a linha `«Navegação» → "browser"` de `_FORMA_FIXA` e o gesto
    grava `janela` com o texto do campo de baixo — um perfil de navegador
    viraria um perfil de um jogo.
    """
    prof = Profile(name="Navegar", priority=40, match=MatchAny())
    _o_disco_tem(monkeypatch, prof)
    _aberto_no_editor(monkeypatch, prof)
    monkeypatch.setattr(a10, "_editor_de",
                        lambda _p: {"jogo": "1245620", "ambiente_recado": ""})

    a10.editor_ambiente(_ctx(), _escolher("Navegação"), PonteDeMentira())

    do_disco = _do_disco(prof)
    # O TEXTO DO CAMPO DE BAIXO NÃO ENTRA: «Navegação» não tem jogo.
    assert "1245620" not in json.dumps(do_disco)
    assert do_disco["match"]["window_class"] == list(
        sm.SIMPLE_MATCH_PRESETS["browser"].window_class)


# ---------------------------------------------------------------------------
# 5. O JARGÃO SAIU — das duas telas, e «Estilo de Jogo» continua vivo
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("caminho", ["mockup/10-perfis.html",
                                    "src/hefesto_dualsense4unix/interface/"
                                    "paginas/10-perfis.html"])
def test_o_jargao_saiu_das_duas_telas(caminho: str) -> None:
    """O desenho e a página publicada dizem a MESMA coisa — ou nenhuma das duas.

    Curar o mockup não cura o produto: os geradores escrevem em `mockup/`, e
    sem o `--publicar` a tela dela não muda. Esta régua mede as duas.

    MORDIDA: publique só uma e ela reprova nomeando qual ficou para trás.
    """
    html = (RAIZ / caminho).read_text(encoding="utf-8")
    campo = html.split('data-hef="editor.ambiente"', 1)[1].split("</select>", 1)[0]

    for jargao in ("Jogo da Steam", "Jogo (pela janela)", ">Jogo<"):
        assert jargao not in campo, (
            f"“{jargao}” voltou ao «Funciona em:» de `{caminho}` — é o jargão "
            f"de implementação que ela mandou tirar em 11/09/2026")
    for fixa in (sm.PROCEDENCIA_DA_NAVEGACAO, sm.PROCEDENCIA_DE_QUALQUER_JOGO):
        assert f">{fixa}<" in campo, (
            f"“{fixa}” saiu do «Funciona em:» de `{caminho}` — as duas fixas "
            f"são o que sobra numa máquina sem lançador nenhum")

    # **«Estilo de Jogo» NÃO MORREU — mudou de lugar.** Ele não é uma
    # procedência, é um corte transversal, e continua no campo próprio uma
    # linha abaixo. Cobrar a ausência dele na PÁGINA seria a régua matando o
    # campo que a ordem dela preservou.
    assert 'data-hef="editor.estilo"' in html
    assert ">Estilo de Jogo:</span>" in html
