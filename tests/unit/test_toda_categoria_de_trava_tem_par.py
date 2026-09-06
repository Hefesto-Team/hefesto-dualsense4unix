"""Toda categoria da trava manual tem quem a ARME e quem a SOLTE.

A-TRAVA-DO-LED-NÃO-SOLTA-01 (06/09/2026). O defeito que originou esta régua,
numa frase: mudar a cor da barra de luz **armava** a trava que cala a troca
automática de perfil, e **nenhum gesto do produto a soltava** — nem o
"Automático", que é exatamente o gesto que significa *"pode voltar a mandar"*.

O CENSO, medido contra o disco em 29/08/2026 e o motivo de esta régua existir:

    | categoria | armava em                    | soltava em          |
    |-----------|------------------------------|---------------------|
    | `trigger` | `trigger.set`                | `trigger.reset`     |
    | `rumble`  | `rumble.set` / `rumble.stop` | `rumble.passthrough`|
    | `led`     | `led.set`, `led.player_set`  | **nada**            |
    | `audio`   | `speaker.set`                | **nada**            |

Enquanto QUALQUER categoria está armada, o `AutoSwitcher` não reaplica o perfil
por mudança de janela. Duas das quatro entravam e não saíam.

O QUE ESTA RÉGUA AFIRMA, e são três coisas diferentes:

1. **o par existe**, e ela o descobre percorrendo `MANUAL_OVERRIDE_CATEGORIES`
   — a constante, nunca uma lista à mão — e varrendo `src/` por AST. Categoria
   nova sem par nasce vermelha aqui, e não na mão de quem clica;
2. **solta só a sua** — o gesto da luz deixa `trigger` e `rumble` de pé. Um
   `clear` sem argumento é a regressão que a assinatura por categoria existe
   para impedir;
3. **e o autoswitch volta a agir** — a prova que importa, com o
   `AutoSwitcher._activate` de verdade. Medir só o `StateStore` seria medir o
   artefato e nunca o encontro dele com o resto do sistema.

A LÁPIDE VIVA. `audio` continua sem par (é a E1 da ÁUDIO-QUE-TRANCA-01) e entra
como `xfail(strict=True)` com o endereço. No dia em que aquela E1 fechar, o
marcador vira XPASS, esta suíte reprova, e alguém vem aqui apagar a linha — que
é o jeito desta casa de uma dívida não envelhecer calada.

AS MORDIDAS, e as duas foram executadas — os números estão no relatório da
sprint (`docs/process/agentes/2026-09-06/`):

- apague `self.store.clear_manual_trigger_active("led")` de
  `_handle_led_auto_release` e veja `test_toda_categoria_tem_quem_a_solte[led]`
  reprovar **dizendo "led"**, com `test_o_autoswitch_volta_a_agir_depois_do_gesto`
  junto;
- escreva as quatro categorias à mão dentro deste arquivo e veja
  `test_esta_regua_le_as_categorias_em_vez_de_digitar` reprovar — *régua que
  digita o que devia LER é a forma exata das onze de 26/08*.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import (
    MANUAL_OVERRIDE_CATEGORIES,
    StateStore,
)
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing import FakeController

RAIZ = Path(__file__).resolve().parents[2]
FONTE = RAIZ / "src"
HANDLERS = FONTE / "hefesto_dualsense4unix/daemon/ipc_handlers.py"
DISPATCHER = FONTE / "hefesto_dualsense4unix/daemon/ipc_server.py"

#: O ENDEREÇO DA DÍVIDA que ainda não tem par, e a razão de ela não ter.
#: Ele é UM nome, e não uma coleção: uma lista aqui seria a lista à mão que a
#: meta-régua abaixo proíbe — e, pior, congelaria o censo do dia em que foi
#: escrita. Quem responde "quais têm par" é o `src/`, lido por AST.
SEM_PAR_AINDA = "audio"
SEM_PAR_PORQUE = (
    "é a E1 da ÁUDIO-QUE-TRANCA-01 "
    "(docs/process/sprints/2026-08-03-AUDIO-QUE-TRANCA-01-"
    "um-toque-no-volume-congela-a-troca-de-perfil.md): o `speaker.set` arma "
    "por dois caminhos, e devolver a posse do alto-falante é o escopo de lá. "
    "Quando ela fechar, este xfail vira XPASS e esta linha deve sair."
)


def _censo_do_src() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Quem ARMA e quem SOLTA cada categoria, lido de `src/` por AST.

    Devolve `({categoria: {endereços}}, {categoria: {endereços}})`. O endereço
    viaja junto de propósito: uma régua que só diz "não achei" manda a próxima
    pessoa procurar de novo o que esta já percorreu.

    POR AST, E NÃO POR `grep`: um `grep` acha a palavra dentro de um comentário
    ou de um docstring — e é exatamente aí que ela mais aparece neste código,
    que documenta a própria trava em três blocos longos. A menção seria contada
    como chamada, e a régua ficaria verde sobre um par que não existe.
    """
    marcam: dict[str, set[str]] = {}
    soltam: dict[str, set[str]] = {}
    for arquivo in sorted(FONTE.rglob("*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call) or not isinstance(no.func, ast.Attribute):
                continue
            if no.func.attr == "mark_manual_trigger_active":
                destino = marcam
            elif no.func.attr == "clear_manual_trigger_active":
                destino = soltam
            else:
                continue
            valores = list(no.args) + [k.value for k in no.keywords]
            for arg in valores:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    onde = f"{arquivo.relative_to(RAIZ)}:{no.lineno}"
                    destino.setdefault(arg.value, set()).add(onde)
    return marcam, soltam


def _categorias_para_a_regua() -> list[Any]:
    """As categorias do produto, com a lápide viva marcada — LIDAS, não digitadas.

    A ORDEM É ESTÁVEL (`sorted`) para o id do teste não dançar entre execuções,
    e a fonte é `MANUAL_OVERRIDE_CATEGORIES`: uma quinta categoria entra nesta
    régua sozinha, no commit em que nascer.
    """
    saida: list[Any] = []
    for categoria in sorted(MANUAL_OVERRIDE_CATEGORIES):
        if categoria == SEM_PAR_AINDA:
            saida.append(
                pytest.param(
                    categoria,
                    marks=pytest.mark.xfail(strict=True, reason=SEM_PAR_PORQUE),
                )
            )
        else:
            saida.append(categoria)
    return saida


# --- 1. o par existe para todas -------------------------------------------


@pytest.mark.parametrize("categoria", sorted(MANUAL_OVERRIDE_CATEGORIES))
def test_toda_categoria_tem_quem_a_arme(categoria: str) -> None:
    """Categoria que ninguém arma é constante morta — some do produto, não daqui."""
    marcam, _ = _censo_do_src()
    assert categoria in marcam, (
        f"nenhuma linha de `src/` chama "
        f"`mark_manual_trigger_active({categoria!r})`. Se a categoria deixou "
        f"de existir no produto, tire-a de `MANUAL_OVERRIDE_CATEGORIES`; "
        f"enquanto ela estiver lá, o `AutoSwitcher` a consulta. "
        f"Armadas hoje: {sorted(marcam)}"
    )


@pytest.mark.parametrize("categoria", _categorias_para_a_regua())
def test_toda_categoria_tem_quem_a_solte(categoria: str) -> None:
    """O par. Sem ele, a trava só sai pelo teto de ociosidade ou por acaso.

    O `clear` SEM ARGUMENTO não conta, e essa é a parte que morde: as três
    saídas globais (`profile.switch`, a hotkey de ciclo, a cessão ao perfil de
    jogo) sempre existiram e limpavam tudo — foi com elas de pé que `led` e
    `audio` passaram semanas armando sem soltar. O que se cobra aqui é o gesto
    que solta AQUELA categoria, que é o único que a pessoa pode acionar
    sabendo o que faz.
    """
    _, soltam = _censo_do_src()
    assert categoria in soltam, (
        f"a categoria {categoria!r} ARMA e nada em `src/` a solta: nenhuma "
        f"chamada de `clear_manual_trigger_active({categoria!r})`. Enquanto "
        f"ela estiver armada o `AutoSwitcher` não reaplica perfil por troca de "
        f"janela, e a única saída é a pessoa trocar de perfil na mão — um "
        f"gesto que ela não tem como saber que precisa fazer. "
        f"Soltas hoje: {sorted(soltam)}"
    )


def test_o_par_da_luz_esta_no_handler_certo() -> None:
    """E o par de `led` é o gesto CERTO — não o rascunho, não o instrumento.

    Um `clear("led")` pendurado em qualquer lugar deixaria a régua acima verde.
    O endereço importa, e a exclusão mais dura é o próprio `led.set`: ele ARMA
    a trava, e um clear dentro dele seria o clear que se desfaz sozinho.
    """
    _, soltam = _censo_do_src()
    onde = sorted(soltam.get("led", ()))
    assert any("daemon/ipc_handlers.py" in x for x in onde), (
        f"o `clear('led')` não está no `ipc_handlers.py`, e sim em {onde}. "
        f"Fora do daemon ele não alcança a trava que o `led.set` armou."
    )

    arvore = ast.parse(HANDLERS.read_text(encoding="utf-8"))
    donos = [
        no.name
        for no in ast.walk(arvore)
        if isinstance(no, ast.AsyncFunctionDef | ast.FunctionDef)
        for filho in ast.walk(no)
        if isinstance(filho, ast.Call)
        and isinstance(filho.func, ast.Attribute)
        and filho.func.attr == "clear_manual_trigger_active"
        and any(isinstance(a, ast.Constant) and a.value == "led" for a in filho.args)
    ]
    assert donos, "nenhuma função do `ipc_handlers` solta `led`"
    assert "_handle_led_set" not in donos, (
        "o `led.set` não pode soltar a trava que ele mesmo arma logo abaixo — "
        "seria o clear que se desfaz sozinho."
    )


def test_a_rota_do_par_esta_no_dispatcher() -> None:
    """Handler sem rota é código morto — e o botão chamaria um nome inexistente.

    A ponte da interface chama pelo NOME (`p.chamar("led.auto_release")`), e um
    nome que o `ipc_server` não registra volta como erro na mão de quem clica.
    """
    achado = re.search(
        r'"led\.auto_release"\s*:\s*self\._handle_led_auto_release',
        DISPATCHER.read_text(encoding="utf-8"),
    )
    assert achado, (
        "`led.auto_release` não está no dicionário de rotas do `ipc_server.py`. "
        "O handler existe e ninguém o alcança."
    )


# --- 2. solta só a sua ----------------------------------------------------


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


def _perfil(name: str) -> Profile:
    return Profile(
        name=name,
        match=MatchCriteria(window_class=[f"{name}_class"]),
        priority=10,
        leds=LedsConfig(lightbar=(10, 20, 30)),
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Off"), right=TriggerConfig(mode="Off")
        ),
    )


@pytest.fixture
def servidor(isolated_profiles_dir: Path, tmp_path: Path) -> IpcServer:
    """`IpcServer` de verdade, sem socket no ar — molde de `test_aplicar_verdade`.

    O SERVIDOR É O REAL de propósito. Um dublê de handler seria mais frouxo que
    o daemon vivo, que é a assinatura dos três instrumentos falsos de 04/09: o
    caminho de erro nunca era exercido porque quem respondia não sabia recusar.
    """
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    return IpcServer(
        controller=fc,
        store=store,
        profile_manager=ProfileManager(controller=fc, store=store),
        socket_path=tmp_path / "hefesto-dualsense4unix.sock",
    )


async def test_o_gesto_da_luz_solta_so_a_luz(servidor: IpcServer) -> None:
    """Arma as três com gesto; o `led.auto_release` deixa duas de pé.

    A MORDIDA: troque a chamada por `clear_manual_trigger_active()` sem
    argumento e veja este teste reprovar. É a regressão do ABAS-05 — desligar
    UMA coisa apagava a opinião deliberada das outras abas.

    ARMA TODAS AS OUTRAS, e não duas escolhidas a dedo: a lista sai da
    constante, então a quinta categoria que nascer já entra aqui defendida.
    """
    for categoria in sorted(MANUAL_OVERRIDE_CATEGORIES):
        servidor.store.mark_manual_trigger_active(categoria)

    corpo = await servidor._handle_led_auto_release({})

    assert corpo["status"] == "ok"
    assert corpo["categoria"] == "led"
    assert servidor.store.manual_override_categories == (
        MANUAL_OVERRIDE_CATEGORIES - {"led"}
    ), (
        "o gesto da luz levou junto o gatilho, a vibração ou o volume que ela "
        "deixou deliberadamente em outra aba."
    )
    assert servidor.store.manual_trigger_active is True, (
        "com `trigger` e `rumble` ainda armadas a trava continua de pé — quem "
        "soltou tudo foi um `clear` sem categoria."
    )


async def test_o_gesto_nao_levanta_com_nada_armado(servidor: IpcServer) -> None:
    """Clicar duas vezes, ou com nada armado, não levanta e não arma nada.

    O botão está sempre na tela e não sabe se a trava está de pé. Um handler
    que recusasse por "não havia nada a soltar" transformaria um clique inócuo
    num recado vermelho — e o gesto ainda tem os dois passos que o precedem,
    que fizeram o que prometiam.
    """
    assert servidor.store.manual_trigger_active is False
    await servidor._handle_led_auto_release({})
    await servidor._handle_led_auto_release({})
    assert servidor.store.manual_override_categories == frozenset()


async def test_a_resposta_nao_promete_alcance_por_controle(
    servidor: IpcServer,
) -> None:
    """A trava não tem dono por controle, e a resposta diz isso em vez de calar.

    `_manual_override_categories` é um dicionário categoria → carimbo, um por
    daemon. Um `uniq` aceito e ignorado seria o "sucesso mentiroso" que a
    APLICAR-VERDADE-01 nomeia: a coluna de UM controle pediria, as quatro
    soltariam, e nada na resposta contaria isso.
    """
    servidor.store.mark_manual_trigger_active("led")
    corpo = await servidor._handle_led_auto_release({})
    assert "uniq" not in corpo
    assert corpo["escopo"], "a resposta não diz até onde o pedido alcançou"
    assert servidor.store.manual_override_categories == frozenset()


# --- 3. e o autoswitch volta a agir ---------------------------------------


async def test_o_autoswitch_volta_a_agir_depois_do_gesto(
    servidor: IpcServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A prova que importa: o perfil que estava calado ENTRA, e sem esperar horas.

    Quem responde é o `AutoSwitcher._activate` de verdade. Com só `led` armada
    ele cala a boca, como tem de calar; depois do gesto, a troca de janela
    seguinte reaplica o perfil.

    E ELE NÃO ESPERA O RELÓGIO. O teto de ociosidade
    (`MANUAL_OVERRIDE_STALE_AFTER_SEC`, seis horas) já devolvia isto sozinho —
    esta régua roda em milissegundos de propósito, para provar que quem soltou
    foi o GESTO. Um teste que andasse o relógio ficaria verde com o gesto
    arrancado, medindo a rede em vez da cura.

    A MORDIDA: apague o `clear_manual_trigger_active("led")` do handler e o
    `ativacoes` volta a `[]` — o autoswitch continua calado depois do clique.
    """
    save_profile(_perfil("shooter"))
    store = servidor.store
    manager = servidor.profile_manager

    ativacoes: list[str] = []
    monkeypatch.setattr(
        manager,
        "activate",
        # `**_` porque o `AutoSwitcher` passa `origin=` — um dublê de assinatura
        # estreita transformaria "a trava soltou" em `autoswitch_activate_failed`
        # e a régua leria a própria falha como se fosse o defeito.
        lambda name, **_: ativacoes.append(name) or MagicMock(),
    )
    switcher = AutoSwitcher(manager=manager, window_reader=lambda: {}, store=store)

    # Ela pinta a barra de roxo: a trava da luz arma (é o `led.set`).
    store.mark_manual_trigger_active("led")
    switcher._activate("shooter", {"wm_class": "Doom"})
    assert ativacoes == [], "o autoswitch pisou na cor que ela acabou de aplicar"

    # Ela clica em "Automático". O gesto larga o claim, pinta a cor do slot e
    # SOLTA A TRAVA — é o terceiro passo que este teste mede.
    await servidor._handle_led_auto_release({})

    switcher._activate("shooter", {"wm_class": "Doom"})
    assert ativacoes == ["shooter"], (
        "depois do 'Automático' a troca de janela seguinte tem de reaplicar o "
        "perfil. Enquanto a trava fica armada, o botão promete devolver a luz "
        "ao automático e não devolve."
    )


async def test_o_autoswitch_continua_calado_se_outra_categoria_esta_armada(
    servidor: IpcServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O outro lado, e ele é o que impede a cura de virar o defeito de volta.

    Soltar a luz não pode reabrir o autoswitch enquanto ela tem um gatilho
    deliberado aplicado — seria o ABAS-05 pela porta nova.
    """
    save_profile(_perfil("shooter"))
    store = servidor.store
    manager = servidor.profile_manager

    ativacoes: list[str] = []
    monkeypatch.setattr(
        manager, "activate", lambda name, **_: ativacoes.append(name) or MagicMock()
    )
    switcher = AutoSwitcher(manager=manager, window_reader=lambda: {}, store=store)

    store.mark_manual_trigger_active("led")
    store.mark_manual_trigger_active("trigger")
    await servidor._handle_led_auto_release({})

    switcher._activate("shooter", {"wm_class": "Doom"})
    assert ativacoes == [], (
        "o gatilho dela ainda está aplicado e o autoswitch voltou a pisar nele"
    )


# --- a meta-régua: esta régua LÊ, nunca digita ----------------------------


def test_esta_regua_le_as_categorias_em_vez_de_digitar() -> None:
    """Nenhuma coleção literal de categorias mora neste arquivo.

    ONZE RÉGUAS DE 26/08 reprovaram a melhora em vez do defeito pela mesma
    forma: *digitavam o que deviam LER*. Uma lista à mão aqui congelaria o
    censo do dia em que foi escrita — a quinta categoria nasceria sem par e
    esta suíte ficaria verde.

    O QUE ELA PROÍBE, e não é toda menção: um LITERAL DE COLEÇÃO (lista, tupla,
    conjunto) com DUAS OU MAIS categorias dentro. Um nome sozinho continua
    permitido, e tem de continuar — a lápide viva (`SEM_PAR_AINDA`) é um deles,
    e os textos de erro citam a categoria pelo nome. É a diferença entre nomear
    um caso e reconstruir a lista.
    """
    arvore = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    culpados: list[tuple[int, list[str]]] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.List | ast.Tuple | ast.Set):
            continue
        textos = [
            e.value
            for e in no.elts
            if isinstance(e, ast.Constant) and isinstance(e.value, str)
        ]
        categorias = [t for t in textos if t in MANUAL_OVERRIDE_CATEGORIES]
        if len(categorias) >= 2:
            culpados.append((no.lineno, categorias))
    assert culpados == [], (
        f"esta régua digitou a lista das categorias em vez de ler "
        f"`MANUAL_OVERRIDE_CATEGORIES`: {culpados}. Uma lista à mão aqui "
        f"envelhece calada — a quinta categoria nasceria sem par e o teste "
        f"continuaria verde."
    )


def test_a_lapide_viva_ainda_e_uma_categoria_do_produto() -> None:
    """A dívida declarada tem de ser real — nome errado desligaria o xfail.

    Se `audio` sair de `MANUAL_OVERRIDE_CATEGORIES`, o `pytest.param` marcado
    deixa de existir e ninguém percebe que a lápide ficou órfã. Aqui ela grita.
    """
    assert SEM_PAR_AINDA in MANUAL_OVERRIDE_CATEGORIES, (
        f"{SEM_PAR_AINDA!r} não é mais uma categoria da trava. Se a dívida "
        f"morreu com ela, apague `SEM_PAR_AINDA` e o `xfail` desta régua."
    )
    assert SEM_PAR_PORQUE.strip(), "lápide sem razão escrita é só um teste desligado"


def test_o_gesto_solta_na_hora_e_nao_depende_do_relogio() -> None:
    """O teto continua existindo, e continua sendo outra coisa.

    Esta régua mede o GESTO. A rede que devolve a trava sozinha depois de horas
    de silêncio é a A-TRAVA-QUE-NINGUÉM-SOLTA-01, medida em
    `tests/unit/test_a_trava_que_ninguem_solta_01.py`. As duas camadas se
    somam: o gesto é para quem clica, o teto é para todo caminho que arma sem
    passar pelo botão — e para `audio`, que ainda não tem botão nenhum.
    """
    from hefesto_dualsense4unix.daemon.state_store import (
        MANUAL_OVERRIDE_STALE_AFTER_SEC,
    )

    store = StateStore()
    store.mark_manual_trigger_active("led")
    assert store.manual_trigger_active is True
    store.clear_manual_trigger_active("led")
    assert store.manual_trigger_active is False, (
        "o gesto não pode depender de relógio nenhum — ele solta na hora"
    )
    assert MANUAL_OVERRIDE_STALE_AFTER_SEC > 0, "o teto some e a rede vai junto"
