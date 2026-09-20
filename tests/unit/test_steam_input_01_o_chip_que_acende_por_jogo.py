#!/usr/bin/env python3
"""STEAM-INPUT-01 — o chip «Steam Input» passa a escrever, e **por jogo**.

A ORDEM DELA, 17/09/2026: *"Aqui no steam input é meio óbvio é basicamente setar
o jogo pra funcionar usando os controladores da própria steam. Fazer tal jogo
usar ela e funcionar."* E, sobre a gravidade: *"Achei que elas tivessem
configuradas. Isso é importantíssimo que resolvamos. Pois estão na aba principal
da interface"*.

O DEFEITO: o Steam Input era o único dos quatro chips da fileira cuja
implementação **já estava pronta e provada** — escrita atômica, backup, duas
réguas, gate de Steam, cura automática no prontuário — e o único que a TELA não
alcançava. Ele saía do gerador marcado e **sem `@gesto`**: o clique chegava, o
piloto recusava dizendo o nome, e nenhum byte era escrito.

O QUE ESTA RÉGUA MEDE, e é UMA pergunta: **clicar no chip mudou o estado da
Steam para AQUELE jogo?** Ela responde sem depender da máquina — lar de mentira,
`localconfig.vdf` sintético, appid que não é jogo de ninguém.

AS QUATRO MORDIDAS, e cada teste diz a sua no docstring:

1. arranque a chamada de `garantir_ponte` do gesto → a lista passa a ser escrita
   e o vdf fica em `"0"`. É o `excecao_inerte` voltando pela porta da régua:
   *"a lista só preserva o que já estava ligado — ela nunca liga"*;
2. arranque o gate da Steam → há escrita com a Steam viva, e a Steam regrava o
   arquivo ao sair: a edição some. **O gesto nunca fecha a Steam dela** — um
   `<span>` não tem como perguntar, e o guarda do vdf completa quando ela sai;
3. arranque o filtro por appid → um segundo jogo muda de valor e ninguém pediu.
   É a `CAMINHO-CONTAGIO-01` com outro campo;
4. arranque o terceiro estado → a tela acende no PENDENTE, afirmando uma ponte
   que não está de pé.

O FURO DESTA RÉGUA, DECLARADO porque é regra da casa: **ela mede o texto que nós
escrevemos, não a Steam lendo-o.** Um `vdf` perfeitamente escrito e uma Steam que
o ignora são indistinguíveis aqui. O outro lado do contrato só ela fecha, com o
jogo aberto (§8 da sprint).

O APPID NÃO É DE JOGO NENHUM, e é regra: *"receita por appid embarcada foi
recusada por ela em 14/08/2026, porque deixa todo jogo novo desprotegido"*
(`test_ponte_steam_input_01_…:44`). O construtor de vdf é o DAQUELE arquivo,
reusado — um terceiro construtor de `localconfig.vdf` nesta casa seria a terceira
versão a divergir.
"""
from __future__ import annotations

import ast
import collections
import inspect
import pathlib
import sys
import textwrap
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.integrations import steam_input_ponte as ponte
from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.interface.pacotes import a01_jogar as aba
from hefesto_dualsense4unix.interface.pacotes import confirmacao
from hefesto_dualsense4unix.interface.pacotes.a07_lancadores import METODO_DA_RECARGA

# O CONSTRUTOR DE VDF É REUSADO — §5.3 da sprint, com todas as letras:
# *"O `_vdf()` daquele arquivo já constrói um `localconfig.vdf` sintético com as
# duas árvores `apps` na ordem real medida. Reuse-o; não escreva um terceiro
# construtor de vdf nesta casa."*
from tests.unit.test_ponte_steam_input_01_a_lista_que_so_preservava import _vdf

#: OS DOIS APPIDS SÃO SINTÉTICOS, e o segundo existe só para a MORDIDA 3: ele é
#: o "outro jogo" que um gesto sem filtro por appid arrastaria junto.
APPID = "999000001"
OUTRO = "999000002"

#: A conta da Steam no lar de mentira. Um número qualquer: o que importa é o
#: LAYOUT (`<raiz>/userdata/<conta>/config/localconfig.vdf`), que é o que
#: `discover_vdfs` e `pasta_das_configs_por_jogo` sabem ler.
CONTA = "1000"


def _configset(*appids: str) -> str:
    """Um `configset_*.vdf` com `autosave` — o formato medido em 13/09/2026.

    É o que faz um appid contar como *"a Steam configurou este jogo POR JOGO"*
    para `ponte.configuracao_por_jogo`, que é o conjunto de onde o desligar tira
    os alvos. Sem ele o DESLIGAR não tem em que mexer, e o teste do segundo
    clique mediria o vazio.
    """
    corpo = "\n".join(
        f'\t"{a}"\n\t{{\n\t\t"autosave"\t\t"1"\n\t}}' for a in appids
    )
    return f'"controller_config"\n{{\n{corpo}\n}}\n'


@pytest.fixture
def lar(tmp_path, monkeypatch):
    """Um HOME de mentira com uma Steam inteira dentro. Nada toca a máquina.

    O `conftest` desta casa já desvia `HOME` e os quatro `XDG_*` para um lar
    falso; aqui o lar é desviado de novo, para um que esta régua CONSTRÓI — e
    assim `discover_vdfs`, `steam_input_allowlist_path` e
    `pasta_das_configs_por_jogo` resolvem sozinhos, sem um único dublê de
    caminho. Um dublê por função seria a régua medindo os próprios dublês.
    """
    casa = tmp_path / "lar"
    steam = casa / ".steam" / "steam"
    vdf = steam / "userdata" / CONTA / "config" / "localconfig.vdf"
    vdf.parent.mkdir(parents=True)
    vdf.write_text(
        _vdf(canonica={"424242": "%command%"}, viva={APPID: "0", OUTRO: "0"}),
        encoding="utf-8",
    )
    configs = (steam / "steamapps" / "common" / "Steam Controller Configs"
               / CONTA / "config")
    configs.mkdir(parents=True)
    (configs / "configset_controller_dualsense.vdf").write_text(
        _configset(APPID, OUTRO), encoding="utf-8")

    monkeypatch.setenv("HOME", str(casa))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(casa / ".config"))
    return vdf


@pytest.fixture(autouse=True)
def _steam_fechada(monkeypatch):
    """A STEAM DA MÁQUINA NÃO ENTRA NA RÉGUA, e o dublê vai nos DOIS donos.

    `steam_input_ponte` faz `from .steam_launch_options import steam_running`:
    ele guarda a PRÓPRIA referência, e um dublê só em `steam_launch_options`
    deixaria `garantir_ponte` perguntando ao `/proc` de verdade. É a armadilha
    que esta casa já pagou — *"from-import copia a referência"*.

    E o `with_steam_closed` é dublado por segurança em todo teste: o de verdade
    escala para `pkill -TERM`/`-KILL` na Steam DELA.
    """
    for dono in (slo, ponte):
        monkeypatch.setattr(dono, "steam_running", lambda: False)
        monkeypatch.setattr(dono, "steam_game_running", lambda: False)

    def _nunca(*a: Any, **kw: Any) -> Any:
        raise AssertionError("o gesto tentou FECHAR a Steam sem a régua mandar")

    monkeypatch.setattr(slo, "with_steam_closed", _nunca)


@pytest.fixture(autouse=True)
def _vigia_limpa():
    """A vigia e o consentimento são de MÓDULO — dois testes se contaminam.

    Sem isto, o cache de um teste responde pelo lar de outro, e um gesto armado
    num teste confirma no seguinte.
    """
    aba.VIGIA_DO_STEAM_INPUT._dado = None
    aba.VIGIA_DO_STEAM_INPUT._quando = 0.0
    confirmacao.desarmar()
    yield
    aba.VIGIA_DO_STEAM_INPUT._dado = None
    aba.VIGIA_DO_STEAM_INPUT._quando = 0.0
    confirmacao.desarmar()


class PonteDeMentira:
    """O `p` do gesto: anota o que foi chamado e não fala com daemon nenhum."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def chamar(self, metodo: str, **params: Any) -> bool:
        self.chamadas.append(metodo)
        return True


def _ctx(com_jogo: bool = True) -> Contexto:
    """O contexto do clique — o jogo chega pela SEGUNDA evidência da escada.

    `a_escada_do_jogo` tem três degraus; os outros dois leem marker em disco, e
    no lar de mentira não há marker nenhum. O degrau do meio
    (`window_detect_last_class`) é puro e vem no `state`, que é o que a pintura
    recebe de verdade.
    """
    state: dict[str, Any] = {
        "connected": True,
        "native_mode": False,
        "gamepad_emulation": {"enabled": True, "flavor": "dualsense",
                              "caminho": "dualsense"},
    }
    if com_jogo:
        state["window_detect_last_class"] = f"steam_app_{APPID}"
    return Contexto(state=state, mesa=[], conectados=[], estados={})


def _valor(vdf: pathlib.Path, appid: str) -> str | None:
    """O `UseSteamControllerConfig` do appid na árvore VIVA, relido do disco.

    **RELIDO, e não guardado:** a régua tem de olhar o arquivo que ficou em
    disco, nunca o texto que ela mesma mandou escrever. É o defeito de 07/09 —
    a trava que se comparava com a própria saída e passava enquanto o CSV perdia
    cinquenta colunas.
    """
    texto = vdf.read_text(encoding="utf-8")
    viva = ponte.arvore_viva(ponte.ler_arvores(texto))
    if viva is None:
        return None
    achado = viva.chaves.get(appid)
    return achado[0] if achado is not None else None


def _canonica(vdf: pathlib.Path) -> str:
    """O texto CRU da árvore canônica das `LaunchOptions` — a que não se toca.

    A ARVORE-ERRADA-01 mediu o preço de confundir as duas: o `localconfig.vdf`
    dela tem TRÊS blocos chamados `apps`, e escrever no errado é reescrever a
    linha de lançamento dos jogos dela sem ninguém pedir.
    """
    texto = vdf.read_text(encoding="utf-8")
    linhas = texto.splitlines()
    canonica = next(a for a in ponte.ler_arvores(texto)
                    if a.caminho.endswith("Software/Valve/Steam/apps"))
    inicio = min(i for i, _f in canonica.blocos.values())
    return "\n".join(linhas[inicio - 1:canonica.fim + 1])


def _lista() -> list[str]:
    """A lista de exceções dela, relida do disco."""
    return ponte.ler_allowlist()


# ---------------------------------------------------------------------------
# 1. O CLIQUE LIGA — a vontade E a ponte
# ---------------------------------------------------------------------------
def test_o_clique_escreve_a_vontade_e_constroi_a_ponte(lar) -> None:
    """Um clique: o jogo entra na lista dela E o vdf passa a dizer `"2"`.

    **A MORDIDA 1** — troque `_ligar_a_ponte` por um `lambda *_: ""` (ou arranque
    a chamada de `ponte.garantir_ponte` de dentro dele). A lista continua sendo
    escrita, o `steam_input_apps.txt` nasce, e o `UseSteamControllerConfig`
    **fica em `"0"`**: esta linha reprova dizendo o valor que sobrou.

    Sem ela, a régua estaria medindo a LISTA e chamando isso de ponte — que é
    textualmente o estorvo `excecao_inerte` que a PONTE-STEAM-INPUT-01 existiu
    para matar: *"a lista só preserva o que já estava ligado — ela nunca liga."*
    """
    assert _valor(lar, APPID) == "0"

    p = PonteDeMentira()
    recado = aba.modo_steam(_ctx(), {}, p)

    assert APPID in _lista(), (
        f"a vontade dela não foi gravada: a lista de exceções tem {_lista()}")
    assert _valor(lar, APPID) == ponte.LIGADO, (
        f"a ponte não subiu: o vdf diz {_valor(lar, APPID)!r} para o jogo "
        f"clicado. A lista sem a ponte é a `excecao_inerte`")
    assert recado is None, (
        f"o clique que deu certo mandou uma caixa de recado: {recado!r}. A "
        f"piscada verde do botão é como esta casa diz «deu certo»")
    # O NOME DO MÉTODO VEM DO DONO — `a07_lancadores.METODO_DA_RECARGA`, que é
    # o mesmo que o gesto importa. Aqui se digitava `"launch_env.refresh"` num
    # `else`, atrás de um `hasattr(aba, "METODO_DA_RECARGA")` que é SEMPRE
    # falso: o gesto importa o nome DENTRO da função, então o módulo nunca o
    # expõe. O primeiro ramo era código morto e a régua mediu a string à mão —
    # *quando um valor tem dono, pergunte ao dono* (conferência, 20/09/2026).
    assert METODO_DA_RECARGA in p.chamadas, (
        f"a marca não foi feita valer AGORA: {p.chamadas}. Sem a recarga ela "
        f"só vale no próximo arranque do serviço, e ela clicaria de novo")


def test_o_clique_nao_toca_a_arvore_das_opcoes_de_lancamento(lar) -> None:
    """A árvore canônica sai byte a byte idêntica.

    ARVORE-ERRADA-01: o `localconfig.vdf` dela tem TRÊS blocos `apps`, e o da
    chave NÃO é o das `LaunchOptions`. Escrever no errado reescreveria a linha
    de lançamento dos jogos dela.
    """
    antes = _canonica(lar)
    aba.modo_steam(_ctx(), {}, PonteDeMentira())
    assert _canonica(lar) == antes, (
        "a árvore canônica das `LaunchOptions` mudou — e ela não é desta chave")


def test_o_clique_nao_arrasta_o_outro_jogo(lar) -> None:
    """**A MORDIDA 3** — o filtro por appid, e ela é a mais cara.

    Arranque o `allowlist=[alvo]` de `_ligar_a_ponte` (deixe `garantir_ponte()`
    ler a lista do disco, ou passe a lista inteira) e ligue com DOIS jogos na
    lista: o segundo appid muda de valor sem ninguém ter pedido, e esta linha
    reprova nomeando.

    É a `CAMINHO-CONTAGIO-01` repetida com outro campo — a sprint que nasceu
    porque o `mode.caminho` de UM jogo virava lei sobre os outros 29.
    """
    slo.add_appid_to_steam_input_allowlist(OUTRO, nota="posto aqui pela régua")
    assert OUTRO in _lista()
    assert _valor(lar, OUTRO) == "0"

    aba.modo_steam(_ctx(), {}, PonteDeMentira())

    assert _valor(lar, APPID) == ponte.LIGADO
    assert _valor(lar, OUTRO) == "0", (
        f"o clique num jogo ligou OUTRO: {OUTRO} saiu de \"0\" para "
        f"{_valor(lar, OUTRO)!r}. A escolha é POR JOGO — ordem dela: «setar o "
        f"jogo pra funcionar usando os controladores da própria steam»")


# ---------------------------------------------------------------------------
# 2. O SEGUNDO CLIQUE DESLIGA — e só aquele jogo
# ---------------------------------------------------------------------------
def test_o_segundo_clique_desliga_o_jogo_e_so_ele(lar) -> None:
    """Clique, clique: o appid sai da lista e o vdf volta a `"0"`.

    O CHIP É UM INTERRUPTOR, e quem decide o sentido é o DISCO (a vigia), não o
    que a tela mostra: a página pode ter até vinte segundos.

    **A MORDIDA DO FILTRO VALE AQUI, E O ARRANJO É O DIFÍCIL DE PROPÓSITO.**
    `garantir_fora_da_lista_desligado` escolhe os alvos por SUBTRAÇÃO: desliga
    todo jogo que a Steam configurou por jogo e que **não** está na lista que
    ela recebe. Então o outro jogo tem de estar LIGADO no vdf e **fora** da
    lista dela — que é o estado de quem ligou o Steam Input pela própria Steam.

    Arranque o `allowlist=_os_que_ficam(alvo)` (chame
    `garantir_fora_da_lista_desligado()` sem argumento, que lê a lista do disco)
    e o outro jogo cai para `"0"` no mesmo clique. A última linha reprova.

    **A PRIMEIRA VERSÃO DESTA RÉGUA MEDIU O ARRANJO FÁCIL** — ela punha o outro
    jogo NA lista dela, e aí as duas versões davam o mesmo resultado por
    coincidência: a mordida passou verde. Foi exatamente a forma de defeito que
    esta casa mediu no rótulo do gravador em 20/09 — *a régua conferia o par que
    não colidia*.
    """
    aba.modo_steam(_ctx(), {}, PonteDeMentira())      # liga só o alvo
    # O OUTRO, ligado POR FORA e fora da lista dela — o arranjo difícil.
    ponte.garantir_ponte(allowlist=[OUTRO])
    assert OUTRO not in _lista()
    assert _valor(lar, APPID) == ponte.LIGADO
    assert _valor(lar, OUTRO) == ponte.LIGADO

    aba.VIGIA_DO_STEAM_INPUT.esquecer()
    aba.modo_steam(_ctx(), {}, PonteDeMentira())

    assert APPID not in _lista(), (
        f"o segundo clique não tirou o jogo da lista: {_lista()}")
    assert _valor(lar, APPID) == ponte.DESLIGADO, (
        f"o segundo clique não desfez a ponte: o vdf diz "
        f"{_valor(lar, APPID)!r}. Um chip que liga e não desliga é pior que um "
        f"chip que não faz nada")
    assert _valor(lar, OUTRO) == ponte.LIGADO, (
        f"desligar um jogo desligou OUTRO: {OUTRO} caiu para "
        f"{_valor(lar, OUTRO)!r} e ninguém pediu")


# ---------------------------------------------------------------------------
# 3. O GATE DA STEAM — a vontade fica, o arquivo espera, e a frase é do dono
# ---------------------------------------------------------------------------
def test_com_a_steam_aberta_o_gesto_grava_a_vontade_e_nao_toca_no_vdf(
        lar, monkeypatch) -> None:
    """**A MORDIDA 2** — o gate da Steam, e ele é do DONO, não deste gesto.

    Arranque o gate (faça `garantir_ponte` escrever com a Steam viva, ou
    dublê `ponte.steam_running` para `False` dentro do `garantir_ponte`) e a
    segunda asserção reprova: **com ela viva a edição é engolida na saída
    dela** — a Steam regrava o `localconfig.vdf` ao sair.

    **A VONTADE FICA, e é a metade que faz o clique valer.** Ela clicou; o
    produto anota. Quem completa é o `hefesto-steam-input-guard.path`, medido
    **active** e **enabled** na máquina dela em 20/09/2026, com
    `PathChanged=%h/.steam/steam/userdata` — ele acorda quando a Steam acaba de
    sair e roda `disable_steam_input.sh --apply-quiet`, que liga os jogos da
    lista e desliga os de fora.

    **E O GESTO NÃO FECHA A STEAM DELA.** A sprint pedia o consentimento de dois
    tempos da aba 07; ele não alcança um chip. O botão da 07 é redesenhado a
    cada tique e TROCA de rótulo para «Fechar e continuar»; o chip é um `<span>`
    estático, e o segundo guarda de `confirmacao.este_clique_confirma` exige um
    `data-v` que **só existe no cartão já armado**. Um consentimento que ela não
    LÊ não é consentimento. O dublê de `with_steam_closed` desta régua levanta
    se alguém tentar.
    """
    monkeypatch.setattr(slo, "steam_running", lambda: True)
    monkeypatch.setattr(ponte, "steam_running", lambda: True)

    with pytest.raises(RuntimeError) as erro:
        aba.modo_steam(_ctx(), {}, PonteDeMentira())

    assert APPID in _lista(), (
        f"a vontade dela se perdeu no clique em que ela a fez: {_lista()}. O "
        f"guarda do vdf completa quando a Steam sair, mas só se a lista disser")
    assert _valor(lar, APPID) == "0", (
        f"houve escrita no vdf com a Steam VIVA: o valor virou "
        f"{_valor(lar, APPID)!r}, e a Steam regrava o arquivo ao sair")
    # A FRASE É A DO DONO — `Estado.frase()`, que NOMEIA o jogo e já diz quando.
    esperada = ponte.estado_da_ponte(allowlist=[APPID]).frase()
    assert str(erro.value) == esperada, (
        f"a tela digitou uma frase própria em vez de ler a do dono:\n"
        f"  saiu    {str(erro.value)!r}\n  esperava {esperada!r}")
    assert "Ligo assim que a Steam fechar" in str(erro.value)


def test_desligar_com_a_steam_aberta_tira_da_lista_e_diz_quando(
        lar, monkeypatch) -> None:
    """O avesso, e ele tem frase própria porque o dono não tem uma.

    Ligar adiado usa `Estado.frase()`, que nomeia o jogo e termina em *"Ligo
    assim que a Steam fechar"*. `garantir_fora_da_lista_desligado` devolve só
    `(status, detalhe)` — não há `Estado`, logo não há frase do dono a ler. Esta
    é nossa, e está marcada PROVISÓRIO: texto de tela é palavra dela.

    A MORDIDA: devolva `""` no ramo do desligar adiado e o clique pisca VERDE
    sobre um jogo que a Steam ainda comanda — quem clicou abriria o jogo
    esperando o controle de volta e não teria.

    E A PROMESSA TEM QUEM A CUMPRA: o `--apply-quiet` do guarda zera o
    `UseSteamControllerConfig` de todo jogo FORA da lista, e o jogo saiu dela na
    linha de cima.
    """
    aba.modo_steam(_ctx(), {}, PonteDeMentira())      # liga, com a Steam fechada
    assert _valor(lar, APPID) == ponte.LIGADO
    monkeypatch.setattr(slo, "steam_running", lambda: True)
    monkeypatch.setattr(ponte, "steam_running", lambda: True)
    aba.VIGIA_DO_STEAM_INPUT.esquecer()

    with pytest.raises(RuntimeError) as erro:
        aba.modo_steam(_ctx(), {}, PonteDeMentira())

    assert APPID not in _lista(), f"a vontade não foi desfeita: {_lista()}"
    assert _valor(lar, APPID) == ponte.LIGADO, (
        "houve escrita no vdf com a Steam VIVA — a edição some na saída dela")
    assert str(erro.value) == aba.STEAM_INPUT_SAIU_E_A_STEAM_ESTA_ABERTA, (
        f"a tela piscou verde ou digitou outra coisa: {str(erro.value)!r}")


#: OS AJUDANTES QUE O GESTO PRECISA ALCANÇAR, no MÍNIMO. É a trava da trava:
#: a varredura de :func:`_alcance_do_gesto` é DERIVADA, e uma derivação que
#: quebra devolve só o gesto e deixa a régua verde sobre tudo. Esta lista não é
#: a varredura — é o piso dela.
_AJUDANTES_DO_CHIP = {
    "modo_steam", "_reconciliar_o_vdf", "_os_que_ficam", "_o_que_o_vdf_diz",
    "_qual_jogo",
}


def _alcance_do_gesto(fn: Any, _visto: frozenset[str] = frozenset(),
                      _fundo: int = 3) -> dict[str, Any]:
    """O gesto e TODO ajudante do PRÓPRIO módulo que ele alcança, por árvore.

    **ERA UMA LISTA DIGITADA DE TRÊS NOMES, e a conferência mediu o furo em
    20/09/2026:** um `slo.with_steam_closed(...)` vivo dentro de
    :func:`a01_jogar._o_que_o_vdf_diz` — o quarto ajudante, chamado a CADA
    clique nos dois sentidos — passava VERDE, porque o quarto nome não estava
    na lista. *A régua mediu o arranjo fácil*, que é a assinatura desta casa.

    A conta é a mesma de `test_todo_gesto_que_grava_esta_protegido._portas`:
    desce pelos ajudantes do próprio módulo, com teto, para não virar um
    interpretador. Três níveis cobrem o gesto inteiro e sobra um.
    """
    achados: dict[str, Any] = {getattr(fn, "__name__", "?"): fn}
    modulo = inspect.getmodule(fn)
    if _fundo <= 0 or modulo is None:
        return achados
    try:
        arvore = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    except (OSError, SyntaxError, TypeError):  # pragma: no cover - defesa
        return achados
    visto = _visto | set(achados)
    a_descer = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call) or not isinstance(no.func, ast.Name):
            continue
        nome = no.func.id
        alvo = getattr(modulo, nome, None)
        if (nome not in visto and callable(alvo)
                and inspect.getmodule(alvo) is modulo):
            a_descer.append(nome)
    visto = visto | set(a_descer)
    for nome in a_descer:
        achados.update(
            _alcance_do_gesto(getattr(modulo, nome), visto, _fundo - 1))
    return achados


def test_o_gesto_nunca_fecha_a_steam_dela(lar, monkeypatch) -> None:
    """Nem ligando, nem desligando, nem com a Steam aberta. **Por árvore.**

    A MORDIDA: devolva um `slo.with_steam_closed(...)` ao gesto **ou a qualquer
    ajudante dele** e esta régua reprova nomeando a função — sem depender de um
    clique chegar até lá.

    ELA LÊ A ÁRVORE, e não o texto: um `grep` casaria a docstring que EXPLICA
    por que o gesto não fecha a Steam, e essa é a forma de defeito que esta casa
    mais paga — *o aviso vira a primeira ocorrência do que ele descreve*.

    **E O ALCANCE É DERIVADO — conferência de 20/09/2026.** A primeira versão
    digitava TRÊS funções (`modo_steam`, `_reconciliar_o_vdf`, `_os_que_ficam`),
    e com um `with_steam_closed` dentro de `_o_que_o_vdf_diz` — o ajudante que
    RELÊ o vdf a cada clique, nos dois sentidos, e o lugar mais natural para
    alguém pensar *"a Steam está aberta, deixa eu fechá-la e ler de novo"* — a
    régua passava com **14 verdes**. Ver :func:`_alcance_do_gesto`.
    """
    alcance = _alcance_do_gesto(aba.modo_steam)
    faltam = sorted(_AJUDANTES_DO_CHIP - set(alcance))
    assert not faltam, (
        f"a varredura derivada deixou de alcançar {faltam} — e uma varredura "
        f"que encolhe deixa esta régua verde sobre o que ela não vê. O piso "
        f"está em `_AJUDANTES_DO_CHIP`")

    fonte = "".join(
        textwrap.dedent(inspect.getsource(fn)) for fn in alcance.values())
    chamadas = {
        no.func.attr if isinstance(no.func, ast.Attribute) else
        getattr(no.func, "id", "")
        for no in ast.walk(ast.parse(fonte)) if isinstance(no, ast.Call)
    }
    for mata_steam in ("with_steam_closed", "stop_steam", "reopen_steam"):
        assert mata_steam not in chamadas, (
            f"o chip da aba Jogar passou a chamar `{mata_steam}` — ele fecha a "
            f"Steam DELA (escala para `pkill -TERM`/`-KILL`) e um `<span>` não "
            f"tem como perguntar antes. A varredura alcançou "
            f"{sorted(alcance)}")


def test_com_o_jogo_aberto_nada_e_escrito(lar, monkeypatch) -> None:
    """Jogo aberto: recusa com a frase do dono, e nem a lista nem o vdf mudam.

    A MORDIDA: tire o portão de jogo aberto e a lista passa a ser escrita no
    instante em que ela está jogando — com o vdf adiado de qualquer forma, o
    clique mudaria o que o daemon entrega ao jogo EM CURSO.
    """
    from hefesto_dualsense4unix.app.actions.daemon_actions import (
        format_steam_janela_recusa,
    )

    monkeypatch.setattr(slo, "steam_game_running", lambda: True)
    monkeypatch.setattr(ponte, "steam_game_running", lambda: True)
    antes = lar.read_text(encoding="utf-8")

    with pytest.raises(RuntimeError) as erro:
        aba.modo_steam(_ctx(), {}, PonteDeMentira())

    assert str(erro.value) == format_steam_janela_recusa("jogo_aberto")
    assert not slo.steam_input_allowlist_path().exists(), (
        "a lista foi escrita com um jogo aberto")
    assert lar.read_text(encoding="utf-8") == antes


# ---------------------------------------------------------------------------
# 4. SEM JOGO, NADA ACONTECE
# ---------------------------------------------------------------------------
def test_sem_jogo_o_gesto_recusa_dizendo_e_nada_e_escrito(lar) -> None:
    """Nenhuma das três evidências responde: recusa nomeada, zero escrita.

    A MORDIDA: tire a guarda `if appid is None` e o gesto passa a escrever sobre
    o `None` — `add_appid_to_steam_input_allowlist("None")` devolve
    `appid_invalido`, e a tela diria que anotou algo. Estas três linhas
    reprovam.

    A FRASE É DO DONO (`format_game_broken_result`), e não digitada aqui: duas
    telas recusando a mesma coisa com palavras diferentes é como a pessoa
    aprende que uma delas não é a sério.
    """
    from hefesto_dualsense4unix.app.actions.daemon_actions import (
        format_game_broken_result,
    )

    antes = lar.read_text(encoding="utf-8")
    with pytest.raises(RuntimeError) as erro:
        aba.modo_steam(_ctx(com_jogo=False), {}, PonteDeMentira())

    assert str(erro.value) == format_game_broken_result(status="sem_jogo")
    assert not slo.steam_input_allowlist_path().exists(), (
        "a lista de exceções nasceu sobre um jogo que ninguém identificou")
    assert lar.read_text(encoding="utf-8") == antes, (
        "o vdf mudou num clique que o produto recusou")


# ---------------------------------------------------------------------------
# 5. A TELA LÊ OS TRÊS ESTADOS
# ---------------------------------------------------------------------------
def test_a_tela_acende_so_com_a_ponte_de_pe(lar) -> None:
    """**A MORDIDA 4** — o terceiro estado, e sem ele o chip volta a mentir.

    | o que se sabe | a tela |
    | --- | --- |
    | na lista **e** o vdf diz `"2"` | chip **aceso** |
    | na lista e o vdf ainda diz `"0"` (PENDENTE) | chip **apagado** |
    | fora da lista | chip apagado |

    Arranque o terceiro estado — faça `_steam_input_da_tela` responder
    `dado.lista` em vez de `dado.ligados` — e o caso do meio acende. A segunda
    asserção reprova.

    Acender no PENDENTE é a tela afirmando uma ponte que não está de pé: quem
    clicou veria o chip aceso, abriria o jogo e não teria Steam Input nenhum.
    """
    ctx = _ctx()

    # (c) fora da lista
    assert aba._estado_da_tela(ctx.state)["steam-input-aceso"] == "", (
        "o chip acendeu sobre um jogo que não está na lista dela")

    # (b) PENDENTE — na lista, e o vdf ainda em "0"
    slo.add_appid_to_steam_input_allowlist(APPID)
    aba.VIGIA_DO_STEAM_INPUT.esquecer()
    aba.VIGIA_DO_STEAM_INPUT.ler()
    assert _valor(lar, APPID) == "0"
    assert aba._estado_da_tela(ctx.state)["steam-input-aceso"] == "", (
        "o chip acendeu no PENDENTE — a tela afirmando uma ponte que não está "
        "de pé, que é o `excecao_inerte` com outra roupa")

    # (a) LIGADO — a ponte de pé
    ponte.garantir_ponte(allowlist=[APPID])
    assert _valor(lar, APPID) == ponte.LIGADO
    aba.VIGIA_DO_STEAM_INPUT.esquecer()
    aba.VIGIA_DO_STEAM_INPUT.ler()
    assert aba._estado_da_tela(ctx.state)["steam-input-aceso"] == "steam", (
        "a ponte está de pé para este jogo e o chip continua apagado")


def test_o_chip_do_steam_input_nao_apaga_o_do_caminho(lar) -> None:
    """Os DOIS acesos ao mesmo tempo — e é a verdade do degrau 4.

    `ponte_escada.ESCADA[3]` é `Ponte(gamepad, dualsense, steam_input=True)` e
    tem `recria_vpad=False`: o Steam Input senta EM CIMA do caminho DualSense em
    vez de substituí-lo. «Sony DualSense» e «Steam Input» são verdade juntos.

    A MORDIDA: devolva o chip do Steam Input ao campo `modo-aceso`
    (`aba01._campo_do_chip`) e os dois passam a disputar UM endereço — o piloto
    escreve o mesmo valor em todo elemento daquele `data-campo`, e acender um
    apaga o outro. Esta linha reprova.
    """
    slo.add_appid_to_steam_input_allowlist(APPID)
    ponte.garantir_ponte(allowlist=[APPID])
    aba.VIGIA_DO_STEAM_INPUT.esquecer()
    aba.VIGIA_DO_STEAM_INPUT.ler()

    fora = aba._estado_da_tela(_ctx().state)
    assert fora["modo-aceso"] == "dualsense", (
        f"o caminho vivo deixou de acender: {fora['modo-aceso']!r}")
    assert fora["steam-input-aceso"] == "steam", (
        f"o Steam Input não acendeu junto: {fora['steam-input-aceso']!r}")
    assert "steam-input-aceso" in aba.DA_PAGINA, (
        "o endereço não está na promessa da aba — o `cobertura` passaria a "
        "contar um campo que a régua não confere")


def test_o_chip_do_steam_input_tem_UM_endereco_proprio_e_cravado() -> None:  # noqa: N802
    """O número que NÃO sai da função medida — e ele só vivia no `__main__`.

    **A RÉGUA QUE ISTO CONSERTA ERA TAUTOLÓGICA, e a conferência de 20/09/2026
    mediu.** `test_a_aba01_le_o_estado_em_vez_de_cravar` passou a derivar quantos
    elementos cada campo tem de ter com `collections.Counter(aba01._campo_do_chip
    (m) for m in aba01.MODOS)` — a MESMA função que escreve a página. O commit
    declarou a tautologia e apontou o antídoto: *"está fechada do outro lado, no
    `conferir()` do próprio `aba01.py`, que CRAVA o único número que não sai
    dela"*.

    **O antídoto não roda.** `aba01._conferir` só é chamado no `if __name__ ==
    "__main__"`, e o `scripts/portoes.sh` desta casa já escreveu isso duas vezes,
    nestas palavras: *"A auto-checagem da própria `aba01.py` NÃO substitui esta:
    ela só roda com `python aba01.py`, e uma régua que espera alguém a chamar não
    protege ninguém — foi o que a conferência de 07/09 derrubou na aba 04."*

    MEDIDO: com `_campo_do_chip` devolvendo sempre `CAMPO_DO_MODO` (os quatro
    chips de volta ao campo partilhado) e a página regerada, a régua derivada
    passa VERDE — esperado `{modo-aceso: 4, steam-input-aceso: 0}`, página com 4
    e 0. A cura arrancada, e nenhum vermelho.

    A MORDIDA DESTA: troque `_campo_do_chip` por `CAMPO_DO_MODO` **ou** por
    `CAMPO_DO_STEAM_INPUT` para todos, e as duas direções reprovam — a primeira
    linha por 0, a segunda por 4. É o único número que não sai da função medida.

    **E A SEGUNDA LINHA MEDE A PÁGINA, não a tabela:** gerador e HTML podem
    divergir (a bancada é escrita por um comando que alguém precisa rodar), e a
    tabela certa sobre uma página velha é a cura que não chegou à tela.

    A CONTA É SOBRE A BANCADA (`mockup/`), e não sobre o produto: o endereço
    novo espera o `--publicar 01`, que é ato dela, e a divergência está
    declarada em `mockup/DIVERGENCIAS.md`.
    """
    from hefesto_dualsense4unix.interface import aba01, onde

    por_campo = collections.Counter(
        aba01._campo_do_chip(m) for m in aba01.MODOS)
    assert por_campo[aba01.CAMPO_DO_STEAM_INPUT] == 1, (
        f"esperava UM chip em `{aba01.CAMPO_DO_STEAM_INPUT}` e a tabela dá "
        f"{por_campo[aba01.CAMPO_DO_STEAM_INPUT]} (de {len(aba01.MODOS)} "
        f"chips). Partilhando o `{aba01.CAMPO_DO_MODO}`, acender o Steam Input "
        f"APAGA o «Sony DualSense» — e os dois são verdade ao mesmo tempo")

    corpo = onde.pagina("01-jogar.html").read_text(encoding="utf-8")
    quantos = corpo.count(f'data-campo="{aba01.CAMPO_DO_STEAM_INPUT}"')
    assert quantos == 1, (
        f"a bancada tem {quantos} elemento(s) em "
        f"`{aba01.CAMPO_DO_STEAM_INPUT}` e a tabela do gerador diz 1 — a "
        f"página não foi regerada, e a cura certa numa tabela que a tela não "
        f"recebeu é cura que não chegou")


# ---------------------------------------------------------------------------
# 6. A RÉGUA DA CLASSE — §6.4 da sprint
# ---------------------------------------------------------------------------
def _arvore(modulo: Any) -> Any:
    """A árvore do fonte do módulo. Por `ast`, e nunca por `grep`.

    Um `grep` casaria a docstring de quem apenas EXPLICA o padrão — e é a forma
    de defeito que esta casa mais paga: *o aviso vira a primeira ocorrência do
    que ele descreve*, três vezes em três dias.
    """
    import ast
    import inspect

    return ast.parse(inspect.getsource(modulo))


def _de_onde_importa(modulo: Any, nome: str) -> set[str]:
    """De quais módulos este módulo importa `nome`, lendo a ÁRVORE do fonte."""
    import ast

    de = set()
    for no in ast.walk(_arvore(modulo)):
        if isinstance(no, ast.ImportFrom):
            for alvo in no.names:
                if alvo.name == nome:
                    de.add(no.module or "")
    return de


def _define(modulo: Any, nome: str) -> bool:
    """Este módulo DEFINE uma função com este nome?"""
    import ast

    return any(
        isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and no.name == nome
        for no in ast.walk(_arvore(modulo))
    )


def test_o_consentimento_que_fecha_a_steam_tem_UM_dono() -> None:  # noqa: N802
    """`este_clique_confirma` mora em `pacotes/confirmacao`, e em mais lugar nenhum.

    **POR QUE ELA EXISTE:** o consentimento que fecha a Steam dela nasceu
    PRIVADO na aba 07 (`_este_clique_confirma`, `_ARMADO`, `_confirmo`), e
    bastava enquanto UMA aba fechava a Steam. Assim que uma segunda precisar do
    mesmo, as duas saídas erradas estão nomeadas: importar o símbolo privado da
    outra aba, ou reescrever a conta. *A terceira cópia é sempre a mais frouxa*
    — é o que o próprio docstring dizia quando ele era da 07: *"Três cópias do
    consentimento que fecha a Steam dela é exatamente onde uma delas ficaria
    mais frouxa que as outras."*

    A MORDIDA: devolva o corpo de `_este_clique_confirma` para dentro de
    `a07_lancadores` (ou escreva uma cópia em qualquer `pacotes/a*.py`) e esta
    régua reprova nomeando o arquivo.

    E ELA ALCANÇA O ESTADO, que é a metade que um import igual não garante: a
    aba 07 lê o MESMO `_ARMADO` de `confirmacao`.

    **FATO CORRIGIDO PELA CONFERÊNCIA — 20/09/2026.** Aqui se dizia *"o relógio
    (`_ARMADO`) é UM só"*, e a medição derrubou: `a09_sistema` tem `_ARMADO`
    PRÓPRIO e o gesto `aplicar-aos-jogos` chama `with_steam_closed`. Armar a 07
    e a 09 deixa OS DOIS pendurados ao mesmo tempo. O que ESTA régua prova é o
    alcance dela — a 07 e a ausência de cópias; quem cobra o resto, e NOMEIA a
    dívida da 09, é
    :func:`test_quem_fecha_a_steam_dela_nao_inventa_um_segundo_relogio`.
    """
    import importlib
    import pathlib as _pathlib

    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

    esperado = {"hefesto_dualsense4unix.interface.pacotes.confirmacao",
                ".confirmacao", "confirmacao"}
    de = _de_onde_importa(a07, "este_clique_confirma")
    assert de & esperado, (
        f"a07_lancadores não importa `este_clique_confirma` de "
        f"`pacotes/confirmacao` — importa de {de or 'lugar nenhum'}")
    assert a07._este_clique_confirma is confirmacao.este_clique_confirma

    # E NENHUM PACOTE DE ABA DEFINE O SEU. A varredura é sobre os arquivos, e
    # não sobre uma lista digitada: a aba que nascer amanhã entra sozinha.
    pasta = _pathlib.Path(confirmacao.__file__).parent
    copias = []
    for arquivo in sorted(pasta.glob("a[0-9][0-9]_*.py")):
        mod = importlib.import_module(
            f"hefesto_dualsense4unix.interface.pacotes.{arquivo.stem}")
        for nome in ("este_clique_confirma", "_este_clique_confirma"):
            if _define(mod, nome):
                copias.append(f"{arquivo.name}::{nome}")
    assert not copias, (
        f"cópia(s) do consentimento que fecha a Steam dela fora do dono: "
        f"{copias}. Quem precisa dele importa de `pacotes/confirmacao`")

    # O RELÓGIO É UM SÓ, e é o que um import repetido não prova.
    assert not hasattr(a07, "_ARMADO") or a07._ARMADO is confirmacao._ARMADO
    confirmacao.armar("um-ato")
    assert a07._armado_agora() == "um-ato", (
        "a aba 07 lê um relógio diferente do de `confirmacao` — dois "
        "consentimentos pendurados sobre a mesma Steam")
    confirmacao.desarmar()


#: QUEM FECHA A STEAM DELA COM RELÓGIO PRÓPRIO — dívida NOMEADA, medida, e
#: anterior a esta leva. A isenção é do ARQUIVO, com a razão do lado; é o mesmo
#: contrato de `test_todo_gesto_que_grava_esta_protegido.ISENTOS`.
RELOGIO_PROPRIO_DECLARADO: dict[str, str] = {
    "a09_sistema.py":
        "o gesto `aplicar-aos-jogos` chama `with_steam_closed` e arma pelo "
        "`_ARMADO` PRÓPRIO do módulo. A conta de lá é mais rica — `_confirmado"
        "(…, antes_de_armar=…)` recusa o clique 1 (SISTEMA-BOTOES-01, 13/09) — "
        "e não cabe na de `confirmacao` sem reescrever a aba, que é de outra "
        "posse. MEDIDO em 20/09/2026: armar a 07 e a 09 deixa OS DOIS "
        "pendurados ao mesmo tempo. Fica nomeada para não ser invisível",
}


def test_quem_fecha_a_steam_dela_nao_inventa_um_segundo_relogio() -> None:
    """Toda aba que fecha a Steam DELA arma pelo relógio de `confirmacao`.

    **POR QUE ELA EXISTE, e é a conferência de 20/09/2026.** A régua irmã
    (`…_tem_UM_dono`) mediu só a aba 07 — a que acabara de ser refatorada — e
    concluía, no docstring, que *"o relógio é UM só"*. A casa já tinha o
    contra-exemplo VIVO: `a09_sistema._ARMADO`, com `aplicar-aos-jogos`
    chamando `with_steam_closed`. *A régua mediu o arranjo fácil*, que é a
    assinatura desta casa desde 20/09.

    O QUE ELA COBRA: um pacote de aba que alcance `with_steam_closed` não pode
    ter um `_ARMADO` de módulo que não seja o de `confirmacao` — a não ser que
    esteja em :data:`RELOGIO_PROPRIO_DECLARADO`, com a medição do lado.

    **O RECORTE É "QUEM FECHA A STEAM", e não "quem tem `_ARMADO`."**
    `a10_perfis` tem o dela e está CERTO: ela arma o «Remover perfil», que não
    toca a Steam de ninguém. Cobrar relógio único ali seria a régua reprovando
    o que não é o defeito.

    AS DUAS MORDIDAS:

    1. tire `a09_sistema.py` de :data:`RELOGIO_PROPRIO_DECLARADO` e ela reprova
       nomeando o arquivo — a dívida de hoje;
    2. dê a uma aba qualquer um `_ARMADO` próprio **e** uma chamada a
       `with_steam_closed`, e ela reprova sem ninguém acrescentar um nome: a
       varredura é sobre os arquivos, não sobre uma lista.

    E A DECLARAÇÃO TAMBÉM MORDE, no outro sentido: um arquivo declarado que
    deixar de ter relógio próprio reprova, para a isenção não envelhecer calada.
    """
    import importlib
    import pathlib as _pathlib

    pasta = _pathlib.Path(confirmacao.__file__).parent
    culpados: list[str] = []
    declarados_ociosos: list[str] = []
    for arquivo in sorted(pasta.glob("a[0-9][0-9]_*.py")):
        mod = importlib.import_module(
            f"hefesto_dualsense4unix.interface.pacotes.{arquivo.stem}")
        proprio = (getattr(mod, "_ARMADO", confirmacao._ARMADO)
                   is not confirmacao._ARMADO)
        fecha = any(
            isinstance(no, ast.Call) and (
                (isinstance(no.func, ast.Attribute)
                 and no.func.attr == "with_steam_closed")
                or (isinstance(no.func, ast.Name)
                    and no.func.id == "with_steam_closed"))
            for no in ast.walk(ast.parse(inspect.getsource(mod)))
        )
        if fecha and proprio and arquivo.name not in RELOGIO_PROPRIO_DECLARADO:
            culpados.append(arquivo.name)
        if arquivo.name in RELOGIO_PROPRIO_DECLARADO and not (fecha and proprio):
            declarados_ociosos.append(arquivo.name)

    assert not culpados, (
        f"aba(s) que fecham a Steam DELA com relógio de consentimento próprio, "
        f"sem declaração: {culpados}. Dois relógios sobre a MESMA Steam deixam "
        f"dois consentimentos pendurados ao mesmo tempo — quem precisa do "
        f"mecanismo importa de `pacotes/confirmacao`")
    assert not declarados_ociosos, (
        f"declaração(ões) em RELOGIO_PROPRIO_DECLARADO que já não descrevem o "
        f"arquivo: {declarados_ociosos}. Uma isenção que sobrevive ao defeito "
        f"envelhece calada — tire a linha no mesmo commit que curou")


def test_a_divida_do_segundo_relogio_e_real_e_esta_medida() -> None:
    """A dívida declarada acima não é teórica: os DOIS ficam armados juntos.

    Ela existe para que :data:`RELOGIO_PROPRIO_DECLARADO` não vire uma linha de
    prosa. O dia em que a 09 passar a usar `confirmacao`, ESTA régua reprova —
    e é o sinal de tirar a declaração, não de reescrever a régua.

    A MORDIDA: faça `a09_sistema._ARMADO` ser o de `confirmacao` e a última
    linha reprova, dizendo que a dívida acabou.
    """
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

    confirmacao.desarmar()
    a09._ARMADO.clear()
    try:
        confirmacao.armar("fechar-a-steam")
        a09._ARMADO.update(
            gesto="aplicar-aos-jogos",
            ate=__import__("time").monotonic() + confirmacao.SEGUNDOS_PARA_CONFIRMAR)
        assert confirmacao.armado_agora() == "fechar-a-steam"
        assert a09._armado_agora() == "aplicar-aos-jogos", (
            "a dívida do segundo relógio ACABOU — a aba 09 passou a ler o "
            "relógio de `confirmacao`. Tire `a09_sistema.py` de "
            "RELOGIO_PROPRIO_DECLARADO no mesmo commit")
    finally:
        confirmacao.desarmar()
        a09._ARMADO.clear()


def test_a_aba_jogar_nao_pede_consentimento_porque_nao_tem_onde(lar) -> None:
    """**O CHIP NÃO USA O CONSENTIMENTO, e isso é medido — não esquecimento.**

    A sprint (§4.2) pedia o consentimento de dois tempos também na aba Jogar.
    Ele não alcança um chip, e o motivo está no desenho:

    1. o chip é um `<span>` ESTÁTICO da fileira. O botão da aba 07 é redesenhado
       a cada tique (`_botao_armavel`) e TROCA de rótulo para «Fechar e
       continuar»; um chip não troca, e um consentimento que ela não LÊ não é
       consentimento;
    2. o segundo guarda exige o `data-v` que **só existe no cartão já armado**.
       O piloto manda `v: d.v || ''`, lido do ATRIBUTO — um `data-v` cravado no
       chip valeria já para o primeiro clique, que é o contrário do que o guarda
       existe para fazer.

    **E NÃO PRECISA:** quem completa o vdf é o `hefesto-steam-input-guard.path`,
    medido **active** e **enabled** na máquina dela em 20/09/2026.

    A régua trava as DUAS pontas — o chip não pede consentimento, e o botão que
    fecha a Steam de verdade continua existindo na aba 07.
    """
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

    assert not _de_onde_importa(aba, "este_clique_confirma"), (
        "a aba Jogar voltou a pedir consentimento — e ela não tem onde mostrar "
        "a pergunta nem como carregar o `data-v` que o guarda exige")
    assert a07.PERGUNTA_DA_STEAM and a07.CONFIRMA_A_STEAM, (
        "o botão que fecha a Steam DE VERDADE sumiu da aba 07 — o chip da 01 "
        "manda para ele quando o desligar não alcança")


def test_o_gesto_esta_registrado_e_declara_o_que_grava() -> None:
    """O chip deixou de ser um botão sem dono — e declarou a porta.

    A MORDIDA: tire o `grava=` do decorador e
    `test_todo_gesto_que_grava_esta_protegido` (direção A) reprova — a régua de
    clique passaria a marcar um jogo DELA para provar que sabe clicar.
    """
    from hefesto_dualsense4unix.interface import pacotes

    chave = ("01-jogar.html", aba.GESTO_DO_STEAM_INPUT)
    assert chave in pacotes.GESTOS, (
        "o `modo-steam` continua sem `@gesto`: o clique chega e o piloto recusa")
    assert pacotes.GESTOS_QUE_MEXEM.get(chave) == (
        "add_appid_to_steam_input_allowlist")
    assert aba.GESTO_DO_STEAM_INPUT not in aba.BOTOES_SEM_DONO, (
        "o chip está listado como sem dono E tem gesto — a lista manda a "
        "próxima pessoa construir o que já está construído")
