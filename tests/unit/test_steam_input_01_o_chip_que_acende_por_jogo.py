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
   arquivo ao sair: a edição some. **O primeiro clique nunca fecha a Steam
   dela**: ele avisa (o rótulo vira «Fechar a Steam?»), e só o segundo fecha
   — escolha dela de 23/09/2026 (`D-2309-STEAM-INPUT-A-FRASE-E-O-CLIQUE`);
3. arranque o filtro por appid → um segundo jogo muda de valor e ninguém pediu.
   É a `CAMINHO-CONTAGIO-01` com outro campo;
4. volte a acender só com a ponte de pé (`dado.ligados`) → o PENDENTE apaga, e
   o clique dela com a Steam aberta volta sem acender nada. FATO SUBSTITUÍDO
   em 23/09/2026 (O-MODO-QUE-NAO-SAI-DO-STEAM-INPUT-01, pela regra dela): a
   mordida era a inversa — acender no PENDENTE era *"afirmar uma ponte que
   não está de pé"*. Na fileira que é grupo de rádio o aceso é a ESCOLHA
   dela, e o que falta aplicar vai à faixa de pendência com a frase do dono.

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

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.integrations import steam_input_ponte as ponte
from hefesto_dualsense4unix.integrations import steam_launch_options as slo
from hefesto_dualsense4unix.interface.pacotes import Contexto, confirmacao
from hefesto_dualsense4unix.interface.pacotes import a01_jogar as aba
from hefesto_dualsense4unix.interface.pacotes.a07_lancadores import METODO_DA_RECARGA

# O CONSTRUTOR DE VDF É REUSADO — §5.3 da sprint, com todas as letras:
# *"O `_vdf()` daquele arquivo já constrói um `localconfig.vdf` sintético com as
# duas árvores `apps` na ordem real medida. Reuse-o; não escreva um terceiro
# construtor de vdf nesta casa."*
from tests.unit.test_ponte_steam_input_01_a_lista_que_so_preservava import _vdf

#: O `with_steam_closed` DE VERDADE, guardado antes de qualquer dublê: é ele que
#: :class:`SteamDeMentira` roda, com os portões dele — o dublê troca só o
#: processo (`stop_steam`, `reopen_steam`), e por isso não é mais frouxo que o
#: produto.
_WITH_STEAM_CLOSED_DE_VERDADE = slo.with_steam_closed

#: OS DOIS APPIDS SÃO SINTÉTICOS, e o segundo existe só para a MORDIDA 3: ele é
#: o "outro jogo" que um gesto sem filtro por appid arrastaria junto.
APPID = "999000001"
OUTRO = "999000002"

#: A MESA DA MATRIZ — regra dela de 23/09/2026: *"nunca é pensada só em um
#: modo, rota, forma de conexão se cabo ou se bt, ou só pro player 1."* Quatro
#: controles, dois no USB e dois no BT. Uniq em faixa FORJADA (`aa:bb:cc`).
MESA_DE_QUATRO = [
    {"pref": f"p{n}", "jogador": n, "uniq": f"aa:bb:cc:00:00:0{n}",
     "transporte": transporte, "via": via, "cor": "", "nome": ""}
    for n, (transporte, via) in enumerate(
        [("usb", "USB"), ("bt", "BT"), ("usb", "USB"), ("bt", "BT")], start=1)
]
UM_CONTROLE = MESA_DE_QUATRO[0]

#: A RESPOSTA DO PRIMEIRO CLIQUE com a Steam aberta: o chip ARMADO, na forma do
#: `blocos:` que o piloto pinta. O rótulo e o gesto vêm dos donos.
_ARMADO_NA_TELA = {"blocos": {
    f'[data-gesto="{aba.GESTO_DO_STEAM_INPUT}"]': aba.STEAM_INPUT_ARMADO}}

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


def instalar_o_vigia(casa: pathlib.Path, *, manter_steam_input: bool = False,
                     habilitado: bool = True) -> pathlib.Path:
    """O vigia do vdf como o `install.sh` o deixa no lar — O-MODO-FREESTYLE-02.

    O MESMO ASSET e as MESMAS trocas do passo 11 do `install.sh`: os
    marcadores viram caminho, e o `--keep-steam-input` apaga SÓ a linha do
    `__SCRIPT__`. O `enable` deixa um atalho em `default.target.wants` (o
    `.path`) e em `timers.target.wants` (o `.timer`). Escrever uma unidade à mão
    seria a régua medindo o próprio dublê.
    """
    import re

    pasta = casa / ".config" / "systemd" / "user"
    pasta.mkdir(parents=True, exist_ok=True)
    texto = (RAIZ / "assets" / "hefesto-steam-input-guard.service").read_text(
        encoding="utf-8")
    if manter_steam_input:
        texto = re.sub(r"(?m)^ExecStart=.*__SCRIPT__.*\n", "", texto)
    for marcador, caminho in (("__SCRIPT__", "scripts/disable_steam_input.sh"),
                              ("__SENTINELA__", "sentinela_do_wrapper.py"),
                              ("__PROTON_PIN__", "proton_pin.py"),
                              ("__OPCOES_POR_JOGO__", "opcoes_por_jogo.py")):
        texto = texto.replace(marcador, str(RAIZ / caminho))
    (pasta / "hefesto-steam-input-guard.service").write_text(texto, encoding="utf-8")
    for tipo, quer in (("path", "default.target.wants"), ("timer", "timers.target.wants")):
        unidade = pasta / f"hefesto-steam-input-guard.{tipo}"
        unidade.write_bytes(
            (RAIZ / "assets" / f"hefesto-steam-input-guard.{tipo}").read_bytes())
        if habilitado:
            (pasta / quer).mkdir(exist_ok=True)
            (pasta / quer / unidade.name).symlink_to(unidade)
    return pasta


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
    # A MÁQUINA INSTALADA SEM OPT-OUT, que é o padrão do `install.sh`: o vigia
    # que liga quando a Steam fecha está lá (O-MODO-FREESTYLE-02, item 6).
    instalar_o_vigia(casa)
    return vdf


@pytest.fixture(autouse=True)
def _steam_fechada(monkeypatch):
    """A STEAM DA MÁQUINA NÃO ENTRA NA RÉGUA, e o dublê vai nos DOIS donos.

    `steam_input_ponte` faz `from .steam_launch_options import steam_running`:
    ele guarda a PRÓPRIA referência, e um dublê só em `steam_launch_options`
    deixaria `garantir_ponte` perguntando ao `/proc` de verdade. É a armadilha
    que esta casa já pagou — *"from-import copia a referência"*.

    E o `with_steam_closed` é dublado por segurança em todo teste: o de verdade
    escala para `pkill -TERM`/`-KILL` na Steam DELA. `stop_steam` e
    `reopen_steam` também: a régua que usa o `with_steam_closed` DE VERDADE
    (:class:`SteamDeMentira`) troca só esses dois, e um que escapasse cairia
    aqui em vez de na Steam dela.
    """
    for dono in (slo, ponte):
        monkeypatch.setattr(dono, "steam_running", lambda: False)
        monkeypatch.setattr(dono, "steam_game_running", lambda: False)

    def _nunca(*a: Any, **kw: Any) -> Any:
        raise AssertionError("o gesto tentou FECHAR a Steam sem a régua mandar")

    for mata_steam in ("with_steam_closed", "stop_steam", "reopen_steam"):
        monkeypatch.setattr(slo, mata_steam, _nunca)


@pytest.fixture(autouse=True)
def _vigia_limpa():
    """A vigia e o relógio são de MÓDULO — dois testes se contaminam.

    Sem isto, o cache de um teste responde pelo lar de outro, e o chip armado
    por um teste vira o consentimento do seguinte.
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
# 2. SAIR DO STEAM INPUT DESLIGA — e só aquele jogo
# ---------------------------------------------------------------------------
def test_sair_do_steam_input_desliga_o_jogo_e_so_ele(lar) -> None:
    """Clique no «Steam Input», clique no «Sony DualSense»: o appid sai e o vdf volta a `"0"`.

    FATO SUBSTITUÍDO — O-MODO-QUE-NAO-SAI-DO-STEAM-INPUT-01, 23/09/2026, pela
    regra dela (*"a idea é eu poder escolher qualquer que seja o modo
    independnete da ordem"*). Esta régua tratava o chip como INTERRUPTOR: o segundo
    clique nele desligava. Na fileira que é grupo de rádio o segundo clique
    REAPLICA, e quem tira o jogo da lista é clicar em qualquer um dos outros
    três (`a01_jogar.o_que_o_chip_faz`). A primeira metade abaixo mede isso; o
    filtro por appid, que é o que esta régua existe para morder, continua.

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

    # O SEGUNDO CLIQUE NO «STEAM INPUT» REAPLICA — não é mais interruptor.
    aba.VIGIA_DO_STEAM_INPUT.esquecer()
    aba.modo_steam(_ctx(), {}, PonteDeMentira())
    assert APPID in _lista() and _valor(lar, APPID) == ponte.LIGADO, (
        "o segundo clique no «Steam Input» desligou — o chip voltou a ser "
        "interruptor, e clicar no aceso apagava o que ela escolheu")

    aba.modo_dualsense(_ctx(), {"texto": "Sony DualSense"}, PonteDeMentira())

    assert APPID not in _lista(), (
        f"o «Sony DualSense» não tirou o jogo da lista: {_lista()}")
    assert _valor(lar, APPID) == ponte.DESLIGADO, (
        f"sair do Steam Input não desfez a ponte: o vdf diz "
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

    O ADIAMENTO NÃO É RECUSA — O-MODO-QUE-NAO-SAI-DO-STEAM-INPUT-01, 23/09/2026.
    Até aqui o gesto levantava com a frase do dono, e a tela piscava recusa
    sobre um clique que valeu. Agora ele volta com a piscada verde, o chip
    acende pela escolha dela, e a frase vai à faixa de pendência.

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

    **E O PRIMEIRO CLIQUE NÃO FECHA A STEAM DELA: ele AVISA** — escolha dela,
    23/09/2026 (`D-2309-STEAM-INPUT-A-FRASE-E-O-CLIQUE`): *"o primeiro clique
    avisa, o segundo fecha"*. A resposta é o rótulo armado do chip, e o dublê
    de `with_steam_closed` desta régua levanta se o primeiro clique o alcançar.
    """
    monkeypatch.setattr(slo, "steam_running", lambda: True)
    monkeypatch.setattr(ponte, "steam_running", lambda: True)
    ctx = _ctx()

    assert aba.modo_steam(ctx, {}, PonteDeMentira()) == _ARMADO_NA_TELA, (
        "o primeiro clique com a Steam aberta não avisou que o segundo a fecha")

    assert APPID in _lista(), (
        f"a vontade dela se perdeu no clique em que ela a fez: {_lista()}. O "
        f"guarda do vdf completa quando a Steam sair, mas só se a lista disser")
    assert _valor(lar, APPID) == "0", (
        f"houve escrita no vdf com a Steam VIVA: o valor virou "
        f"{_valor(lar, APPID)!r}, e a Steam regrava o arquivo ao sair")
    # O CHIP ACENDE PELA ESCOLHA DELA. Na TELA vai a frase curta dela; no
    # DIÁRIO, a do dono — `Estado.frase()`, que NOMEIA o jogo e já diz quando.
    assert aba._estado_da_tela(ctx.state)["steam-input-aceso"] == "steam", (
        "o clique com a Steam aberta voltou e o chip não acendeu — é o "
        "«cliquei e nada acendeu» da queixa dela")
    esperada = ponte.estado_da_ponte(allowlist=[APPID]).frase()
    diario = aba._faixa_do_pendente(ctx.state)[0]
    assert esperada in diario, (
        f"o diário não leva a frase do dono:\n"
        f"  diário   {diario!r}\n  esperava {esperada!r}")
    assert "Ligo assim que a Steam fechar" in diario
    ctx.mesa.append(dict(UM_CONTROLE))
    tela = aba.pacote(ctx)
    assert (tela["pendente"], tela["pendente-ha"]) == (f"● {aba.STEAM_INPUT_ESPERA}", "1"), (
        f"a faixa não disse a frase dela: {tela['pendente']!r} "
        f"(ha={tela['pendente-ha']!r})")


def test_desligar_com_a_steam_aberta_tira_da_lista_e_diz_quando(
        lar, monkeypatch) -> None:
    """O avesso, e ele tem frase própria porque o dono não tem uma.

    A SAÍDA DO STEAM INPUT É CLICAR NUM DOS OUTROS TRÊS — O-MODO-QUE-NAO-SAI-
    DO-STEAM-INPUT-01, 23/09/2026. E o recado VOLTA em vez de levantar: a lista
    mudou, o caminho mudou, o chip clicado acende — o que falta é da Steam.

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

    resposta = aba.modo_dualsense(_ctx(), {"texto": "Sony DualSense"}, PonteDeMentira())

    assert APPID not in _lista(), f"a vontade não foi desfeita: {_lista()}"
    assert _valor(lar, APPID) == ponte.LIGADO, (
        "houve escrita no vdf com a Steam VIVA — a edição some na saída dela")
    assert resposta == {"recado": aba.STEAM_INPUT_SAIU_E_A_STEAM_ESTA_ABERTA}, (
        f"a tela piscou verde ou digitou outra coisa: {resposta!r}")


# ---------------------------------------------------------------------------
# 3b. OS DOIS CLIQUES — «Fechar a Steam?», escolha dela de 23/09/2026
# ---------------------------------------------------------------------------
class SteamDeMentira:
    """A Steam aberta, e o `with_steam_closed` DE VERDADE por cima dela.

    O DUBLÊ É SÓ O PROCESSO: `stop_steam` vira a bandeira e conta, e
    `reopen_steam` a devolve. A ORDEM DOS PORTÕES (jogo aberto antes de tudo, a
    Steam que resiste não é editada, a reabertura no `finally`) é a do produto,
    porque a função que roda é a do produto. Com `resiste=True` o `stop_steam`
    devolve `False`, como a Steam que não fecha em 30 s.
    """

    def __init__(self, monkeypatch: Any, *, jogo_aberto: bool = False,
                 resiste: bool = False) -> None:
        self.aberta = True
        self.jogo_aberto = jogo_aberto
        self.resiste = resiste
        self.fechou = 0
        self.reabriu = 0
        for dono in (slo, ponte):
            monkeypatch.setattr(dono, "steam_running", lambda: self.aberta)
            monkeypatch.setattr(dono, "steam_game_running",
                                lambda: self.jogo_aberto)
        monkeypatch.setattr(slo, "with_steam_closed", _WITH_STEAM_CLOSED_DE_VERDADE)
        monkeypatch.setattr(slo, "stop_steam", self._parar)
        monkeypatch.setattr(slo, "reopen_steam", self._reabrir)

    def _parar(self, *a: Any, **kw: Any) -> bool:
        if self.resiste:
            return False
        self.fechou += 1
        self.aberta = False
        return True

    def _reabrir(self, *a: Any, **kw: Any) -> None:
        self.reabriu += 1
        self.aberta = True


def _o_segundo_clique() -> dict[str, str]:
    """O `o` do clique no chip ARMADO — o `texto` é o que o piloto manda."""
    return {"texto": aba.STEAM_INPUT_ARMADO}


def test_o_primeiro_clique_avisa_e_o_segundo_fecha_liga_e_reabre(
        lar, monkeypatch) -> None:
    """A escolha dela, inteira: *"o primeiro clique avisa, o segundo fecha"*.

    `D-2309-STEAM-INPUT-A-FRASE-E-O-CLIQUE`, 23/09/2026. Com a Steam aberta e
    nenhum jogo:

    1. o primeiro clique grava a vontade, NÃO fecha a Steam, e ARMA: o rótulo do
       chip vira «Fechar a Steam?», e a faixa diz «Liga quando a Steam fechar»;
    2. o tique mantém o rótulo armado enquanto o relógio corre;
    3. o segundo clique traz o rótulo armado, fecha a Steam UMA vez, liga o
       jogo no vdf e a reabre — e o rótulo volta a «Steam Input», a faixa cala.

    A MORDIDA: faça `_armar_se_a_steam_segura` devolver `None` sem armar e a
    primeira asserção reprova — o primeiro clique voltaria calado, e o segundo
    não teria o que confirmar.
    """
    steam = SteamDeMentira(monkeypatch)
    ctx = _ctx()
    ctx.mesa.extend(dict(c) for c in MESA_DE_QUATRO)

    assert aba.modo_steam(ctx, {"texto": "Steam Input"}, PonteDeMentira()) == _ARMADO_NA_TELA
    assert (steam.fechou, _valor(lar, APPID)) == (0, "0"), (
        "o PRIMEIRO clique fechou a Steam ou escreveu no vdf — ele só avisa")
    tela = aba.pacote(ctx)
    assert tela["blocos"] == _ARMADO_NA_TELA["blocos"], (
        f"o tique não manteve o chip armado: {tela['blocos']!r}")
    assert tela["pendente"] == f"● {aba.STEAM_INPUT_ESPERA}"

    resposta = aba.modo_steam(ctx, _o_segundo_clique(), PonteDeMentira())

    assert (steam.fechou, steam.reabriu, steam.aberta) == (1, 1, True), (
        f"o segundo clique não fechou e reabriu a Steam uma vez: fechou="
        f"{steam.fechou} reabriu={steam.reabriu} aberta={steam.aberta}")
    assert _valor(lar, APPID) == ponte.LIGADO, (
        f"a Steam fechou e o vdf continua {_valor(lar, APPID)!r}")
    assert APPID in _lista()
    em_repouso = {f'[data-gesto="{aba.GESTO_DO_STEAM_INPUT}"]': "Steam Input"}
    assert resposta == {"blocos": em_repouso}, f"o chip não voltou ao repouso: {resposta!r}"
    depois = aba.pacote(ctx)
    assert (depois["blocos"], depois["pendente"], depois["steam-input-aceso"]) == (
        em_repouso, "", "steam"), (
        f"depois do segundo clique: blocos={depois['blocos']!r} "
        f"faixa={depois['pendente']!r} aceso={depois['steam-input-aceso']!r}")


def test_o_clique_sem_o_rotulo_armado_nao_fecha_a_steam(lar, monkeypatch) -> None:
    """O relógio armado SEM o rótulo não é consentimento — rearma e não fecha.

    É o primeiro guarda da aba 09 (`a09_sistema._confirmado`): o rótulo que
    **só existe no chip armado**. Um clique que chega com «Steam Input» — a
    prova automática, um tique que ainda não repintou — é um primeiro clique.

    A MORDIDA: em `a01_jogar._o_clique_que_confirma`, confirme só pelo relógio
    (tire a comparação com `STEAM_INPUT_ARMADO`) e a Steam fecha aqui.
    """
    steam = SteamDeMentira(monkeypatch)
    aba.modo_steam(_ctx(), {"texto": "Steam Input"}, PonteDeMentira())
    assert aba.modo_steam(_ctx(), {"texto": "Steam Input"}, PonteDeMentira()) == _ARMADO_NA_TELA
    assert (steam.fechou, _valor(lar, APPID)) == (0, "0"), (
        "o clique sem o rótulo armado fechou a Steam dela")


def test_o_rotulo_armado_fora_do_prazo_recusa_e_nao_fecha(lar, monkeypatch) -> None:
    """A pergunta venceu: o rótulo sozinho não fecha a Steam, e o clique recusa.

    É o segundo guarda, o relógio de `pacotes/confirmacao`.

    A MORDIDA: em `a01_jogar._o_clique_que_confirma`, confirme só pelo rótulo
    (tire a comparação com `confirmacao.armado_agora()`) e a Steam fecha aqui.
    """
    steam = SteamDeMentira(monkeypatch)
    aba.modo_steam(_ctx(), {"texto": "Steam Input"}, PonteDeMentira())
    confirmacao.ARMADO["ate"] -= confirmacao.SEGUNDOS_PARA_CONFIRMAR + 1

    with pytest.raises(RuntimeError) as erro:
        aba.modo_steam(_ctx(), _o_segundo_clique(), PonteDeMentira())

    assert str(erro.value) == aba.STEAM_INPUT_A_PERGUNTA_VENCEU
    assert (steam.fechou, _valor(lar, APPID)) == (0, "0")
    assert aba._o_rotulo_do_chip(_ctx().state)[
        f'[data-gesto="{aba.GESTO_DO_STEAM_INPUT}"]'] == "Steam Input", (
        "a pergunta venceu e o chip continua dizendo «Fechar a Steam?»")


@pytest.mark.parametrize(("jogo_aberto", "resiste", "janela"), [
    (True, False, "jogo_aberto"),
    (False, True, "nao_fechou"),
], ids=["jogo-abriu-entre-os-cliques", "a-steam-nao-fechou"])
def test_o_segundo_clique_que_nao_pode_recusa_com_a_frase_do_dono(
        lar, monkeypatch, jogo_aberto, resiste, janela) -> None:
    """Jogo aberto entre os dois cliques, ou a Steam que resiste: nada muda.

    Os portões são os de `with_steam_closed`, e a frase é a do dono
    (`daemon_actions.format_steam_janela_recusa`). O vdf sai idêntico: com um
    jogo aberto fechar a Steam o mataria, e com ela viva a edição some.
    """
    from hefesto_dualsense4unix.app.actions.daemon_actions import (
        format_steam_janela_recusa,
    )

    steam = SteamDeMentira(monkeypatch)
    aba.modo_steam(_ctx(), {"texto": "Steam Input"}, PonteDeMentira())
    steam.jogo_aberto = jogo_aberto
    steam.resiste = resiste
    antes = lar.read_text(encoding="utf-8")

    with pytest.raises(RuntimeError) as erro:
        aba.modo_steam(_ctx(), _o_segundo_clique(), PonteDeMentira())

    assert str(erro.value) == format_steam_janela_recusa(janela)
    assert lar.read_text(encoding="utf-8") == antes, "o vdf mudou num clique recusado"
    assert steam.aberta, "a Steam ficou fechada depois da recusa"


def test_com_a_ponte_de_pe_o_segundo_clique_nao_fecha_a_steam_por_nada(
        lar, monkeypatch) -> None:
    """A ponte subiu entre os dois cliques: o segundo não fecha a Steam.

    O caso é real: ela fecha a Steam sozinha depois do primeiro clique, o
    guarda do vdf liga o jogo na saída, e ela reabre a Steam dentro dos 20 s.
    O rótulo ainda diz «Fechar a Steam?», e fechá-la de novo seria por nada.

    A MORDIDA: tire o `if _o_que_o_vdf_diz(alvo) == ponte.LIGADO` de
    `a01_jogar._fechar_a_steam_e_ligar` e a Steam fecha aqui.
    """
    steam = SteamDeMentira(monkeypatch)
    aba.modo_steam(_ctx(), {"texto": "Steam Input"}, PonteDeMentira())
    steam.aberta = False
    ponte.garantir_ponte(allowlist=[APPID])       # o guarda, na saída da Steam
    steam.aberta = True
    assert _valor(lar, APPID) == ponte.LIGADO

    resposta = aba.modo_steam(_ctx(), _o_segundo_clique(), PonteDeMentira())

    assert steam.fechou == 0, "a ponte já estava de pé e a Steam fechou assim mesmo"
    assert resposta == {"blocos": {
        f'[data-gesto="{aba.GESTO_DO_STEAM_INPUT}"]': "Steam Input"}}


def test_outro_chip_desarma_o_steam_input(lar, monkeypatch) -> None:
    """Armado o «Steam Input», clicar em outro chip desarma — e o rótulo volta.

    Sem isto o chip seguiria dizendo «Fechar a Steam?» com o «Sony DualSense»
    aceso, e o clique nele fecharia a Steam por um jogo que acabou de sair da
    lista.

    A MORDIDA: tire o `_desarmar_o_chip()` de `a01_jogar._o_clique_da_fileira`
    e o relógio continua armado — esta linha reprova.
    """
    SteamDeMentira(monkeypatch)
    aba.modo_steam(_ctx(), {"texto": "Steam Input"}, PonteDeMentira())
    assert confirmacao.armado_agora()

    aba.modo_dualsense(_ctx(), {"texto": "Sony DualSense"}, PonteDeMentira())

    assert confirmacao.armado_agora() == "", (
        "o «Sony DualSense» não desarmou o «Fechar a Steam?» do chip vizinho")


def test_o_consentimento_e_para_aquele_jogo(lar, monkeypatch) -> None:
    """Armado para um jogo, o segundo clique não fecha a Steam por OUTRO.

    Conferência de 24/09/2026. A chave do relógio leva o appid
    (`_chave_do_chip`) porque o consentimento dela é para o jogo da pergunta:
    se o jogo da vez muda entre os dois cliques (outra janela em foco, outro
    jogo no marcador), o rótulo «Fechar a Steam?» ainda pode estar na tela, e
    o clique nele não pode valer pelo jogo novo.

    A MORDIDA: faça `_chave_do_chip` ignorar o appid e a Steam fecha aqui pelo
    `OUTRO` — um jogo sobre o qual ela nunca foi perguntada.
    """
    steam = SteamDeMentira(monkeypatch)
    assert aba.modo_steam(_ctx(), {"texto": "Steam Input"}, PonteDeMentira()) == _ARMADO_NA_TELA

    outro = _ctx()
    outro.state["window_detect_last_class"] = f"steam_app_{OUTRO}"
    assert aba._o_rotulo_do_chip(outro.state) == {
        f'[data-gesto="{aba.GESTO_DO_STEAM_INPUT}"]': "Steam Input"}, (
        "o tique pintou «Fechar a Steam?» para um jogo que não foi perguntado")
    antes = lar.read_text(encoding="utf-8")

    with pytest.raises(RuntimeError) as erro:
        aba.modo_steam(outro, _o_segundo_clique(), PonteDeMentira())

    assert str(erro.value) == aba.STEAM_INPUT_A_PERGUNTA_VENCEU
    assert steam.fechou == 0, "o consentimento de um jogo fechou a Steam por outro"
    assert lar.read_text(encoding="utf-8") == antes


def test_com_a_ponte_de_pe_o_clique_no_chip_nao_pergunta(lar, monkeypatch) -> None:
    """Com o jogo já ligado no vdf, o clique no «Steam Input» não arma.

    Conferência de 24/09/2026. O primeiro clique só pergunta quando fechar a
    Steam MUDA alguma coisa — o vdf em `"0"` para o jogo. Com a ponte de pé
    (`"2"`), a pergunta pediria um consentimento para nada, e o segundo clique
    fecharia a Steam dela à toa.

    A MORDIDA: tire de `_armar_se_a_steam_segura` a pergunta ao vdf e o chip
    arma aqui.
    """
    ponte.garantir_ponte(allowlist=[APPID])          # a Steam ainda fechada
    assert _valor(lar, APPID) == ponte.LIGADO
    slo.add_appid_to_steam_input_allowlist(APPID)
    steam = SteamDeMentira(monkeypatch)

    resposta = aba.modo_steam(_ctx(), {"texto": "Steam Input"}, PonteDeMentira())

    assert resposta is None, f"o chip perguntou com a ponte já de pé: {resposta!r}"
    assert confirmacao.armado_agora() == "", "o relógio armou sem nada a fechar"
    assert steam.fechou == 0


def _texto_visivel_das_abas() -> str:
    """O texto que as dez abas PUBLICADAS mostram, sem a nota do rodapé.

    Sai o que não é tela: comentários, `<script>`, `<style>`, as tags (e com
    elas os atributos) e a `<div class="nota">` do fim, que é a história da aba
    — ela cita botões que saíram, de propósito, e contaria como tela.
    """
    import html as _html
    import re

    from hefesto_dualsense4unix.interface import onde

    pedacos = []
    for pagina in sorted(onde.PUBLICADO.glob("[01][0-9]-*.html")):
        texto = pagina.read_text(encoding="utf-8")
        texto = re.sub(r"<!--.*?-->", " ", texto, flags=re.S)
        texto = re.sub(r"<(script|style)\b.*?</\1>", " ", texto, flags=re.S)
        nota = texto.find('<div class="nota">')
        if nota >= 0:
            texto = texto[:nota]
        pedacos.append(_html.unescape(re.sub(r"<[^>]+>", " ", texto)))
    assert len(pedacos) == 10, f"esperava as dez abas publicadas, achei {len(pedacos)}"
    return re.sub(r"\s+", " ", " ".join(pedacos))


def test_as_frases_do_chip_e_do_detectar_so_nomeiam_o_que_a_tela_tem() -> None:
    """Toda «coisa» que uma frase da 01 ou da 07 nomeia existe na tela publicada.

    Conferência de 24/09/2026. O acréscimo da sprint achou o «Consertar» na
    frase do «Detectar»; a mesma forma morava no chip: a frase do desligar que
    não pegou mandava usar «Desligar o Steam Input», na aba Lançadores — botão
    que saiu em 21/09 junto com o «Consertar». Curar só o que foi apontado
    deixaria a segunda cópia viva.

    A régua lê a ÁRVORE (as strings do código, sem as docstrings) e não uma
    lista de frases: a que nascer amanhã entra sozinha.

    A MORDIDA: devolva «Desligar o Steam Input» a `STEAM_INPUT_SAIU_MAS_CONTINUA`
    e esta régua reprova nomeando o arquivo e a linha.
    """
    import re

    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores

    tela = _texto_visivel_das_abas()
    orfaos = []
    for modulo in (aba, a07_lancadores):
        arvore = ast.parse(inspect.getsource(modulo))
        docstrings = {
            id(no.body[0].value) for no in ast.walk(arvore)
            if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef,
                               ast.AsyncFunctionDef))
            and no.body and isinstance(no.body[0], ast.Expr)
            and isinstance(no.body[0].value, ast.Constant)
        }
        for no in ast.walk(arvore):
            if (isinstance(no, ast.Constant) and isinstance(no.value, str)
                    and id(no) not in docstrings):
                for nome in re.findall(r"«([^»]+)»", no.value):
                    if nome not in tela:
                        orfaos.append(f"{pathlib.Path(modulo.__file__).name}:"
                                      f"{no.lineno} «{nome}»")
    assert not orfaos, (
        f"frases que nomeiam o que a tela publicada não tem: {orfaos}. Botão "
        f"que saiu da tela sai da frase junto")


#: OS AJUDANTES QUE O GESTO PRECISA ALCANÇAR, no MÍNIMO. É a trava da trava:
#: a varredura de :func:`_alcance_do_gesto` é DERIVADA, e uma derivação que
#: quebra devolve só o gesto e deixa a régua verde sobre tudo. Esta lista não é
#: a varredura — é o piso dela.
_AJUDANTES_DO_CHIP = {
    "modo_steam", "_reconciliar_o_vdf", "_os_que_ficam", "_o_que_o_vdf_diz",
    "_qual_jogo", "_o_clique_que_confirma", "_armar_se_a_steam_segura",
    "_fechar_a_steam_e_ligar",
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


def test_so_o_segundo_clique_alcanca_o_fechar_a_steam() -> None:
    """UMA função do alcance do gesto fecha a Steam, e é a do segundo clique.

    A escolha dela, 23/09/2026 (`D-2309-STEAM-INPUT-A-FRASE-E-O-CLIQUE`): *"o
    primeiro clique avisa, o segundo fecha"*. O gesto alcança
    `with_steam_closed` — e só por :func:`a01_jogar._fechar_a_steam_e_ligar`,
    que `modo_steam` só chama depois de `_o_clique_que_confirma`.

    FATO SUBSTITUÍDO — esta régua se chamava «o gesto nunca fecha a Steam dela»
    e reprovava qualquer `with_steam_closed` no alcance: um `<span>` não tinha
    como perguntar. O `blocos:` troca o rótulo do chip, e a pergunta é ele.

    ELA LÊ A ÁRVORE, e não o texto: um `grep` casaria a docstring que EXPLICA
    quando o gesto fecha a Steam — *o aviso vira a primeira ocorrência do que
    ele descreve*. E O ALCANCE É DERIVADO (conferência de 20/09/2026): com a
    lista digitada, um `with_steam_closed` dentro de `_o_que_o_vdf_diz` passava.

    A MORDIDA: devolva um `slo.with_steam_closed(...)` a qualquer outro
    ajudante — `_o_que_o_vdf_diz`, `_reconciliar_o_vdf`, `_armar_se_a_steam_segura`
    — e esta régua reprova nomeando a função.
    """
    alcance = _alcance_do_gesto(aba.modo_steam)
    faltam = sorted(_AJUDANTES_DO_CHIP - set(alcance))
    assert not faltam, (
        f"a varredura derivada deixou de alcançar {faltam} — e uma varredura "
        f"que encolhe deixa esta régua verde sobre o que ela não vê. O piso "
        f"está em `_AJUDANTES_DO_CHIP`")

    fecham = []
    for nome, fn in alcance.items():
        arvore = ast.parse(textwrap.dedent(inspect.getsource(fn)))
        chamadas = {
            no.func.attr if isinstance(no.func, ast.Attribute) else
            getattr(no.func, "id", "")
            for no in ast.walk(arvore) if isinstance(no, ast.Call)
        }
        if chamadas & {"with_steam_closed", "stop_steam", "reopen_steam"}:
            fecham.append(nome)
    assert fecham == ["_fechar_a_steam_e_ligar"], (
        f"quem fecha a Steam DELA no alcance do chip: {sorted(fecham)}. Só o "
        f"segundo clique pode — ele escala para `pkill -TERM`/`-KILL`")


def test_com_o_jogo_aberto_a_lista_e_gravada_e_o_vdf_espera(lar, monkeypatch) -> None:
    """Jogo da Steam aberto: o clique grava a lista, o vdf espera, e nada recusa.

    FATO SUBSTITUÍDO — O-MODO-QUE-NAO-SAI-DO-STEAM-INPUT-01, 23/09/2026, §3
    item 5. Esta régua cobrava a RECUSA (*"Feche o jogo e clique de novo"*) e
    dizia que gravar a lista com o jogo aberto *"mudaria o que o daemon entrega
    ao jogo EM CURSO"*. Isso nunca foi medido, e o git diz de onde o portão
    veio: o desenho da STEAM-INPUT-01 (§4.2) o punha só na PONTE, com a razão
    *"fechar a Steam mataria o jogo"*; o commit `c417498e0` recuou de fechar a
    Steam e deixou o portão na frente da lista também. O que a lista decide com
    o jogo aberto é a exceção do daemon (`gamepad.esconder_o_fisico_para_o_jogo`,
    que só reafirma o estado canônico, sem criar nem destruir device) e o
    arming do PRÓXIMO lançamento.

    O VDF CONTINUA ESPERANDO, e quem espera é o dono: `garantir_ponte` adia com
    o jogo aberto antes de olhar a Steam. A frase dele vai à faixa.

    A MORDIDA: devolva o portão (`if slo.steam_game_running(): raise ...`) a
    `a01_jogar._o_clique_da_fileira` e o clique volta a recusar.
    """
    for dono in (slo, ponte):
        monkeypatch.setattr(dono, "steam_running", lambda: True)
        monkeypatch.setattr(dono, "steam_game_running", lambda: True)
    antes = lar.read_text(encoding="utf-8")
    ctx = _ctx()

    assert aba.modo_steam(ctx, {}, PonteDeMentira()) is None

    assert APPID in _lista(), "a escolha dela não foi gravada com o jogo aberto"
    assert lar.read_text(encoding="utf-8") == antes, (
        "houve escrita no vdf com o jogo aberto")
    assert aba._estado_da_tela(ctx.state)["steam-input-aceso"] == "steam"
    assert "Ligo assim que o jogo e a Steam fecharem" in (
        aba._faixa_do_pendente(ctx.state)[0])
    # COM JOGO ABERTO NADA ARMA: o segundo clique fecharia a Steam com o jogo
    # dentro. A faixa diz a mesma frase curta.
    assert confirmacao.armado_agora() == "", "o chip armou com um jogo aberto"
    ctx.mesa.append(dict(UM_CONTROLE))
    assert aba.pacote(ctx)["pendente"] == f"● {aba.STEAM_INPUT_ESPERA}"


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
def test_a_tela_acende_pela_escolha_dela(lar) -> None:
    """**A MORDIDA 4** — o PENDENTE acende, e o que falta vai à faixa.

    | o que se sabe | a tela |
    | --- | --- |
    | na lista **e** o vdf diz `"2"` | chip **aceso**, faixa sem a ponte |
    | na lista e o vdf ainda diz `"0"` (PENDENTE) | chip **aceso**, e a frase do dono na faixa |
    | fora da lista | chip apagado |

    FATO SUBSTITUÍDO — O-MODO-QUE-NAO-SAI-DO-STEAM-INPUT-01, 23/09/2026, §3
    item 3. Esta régua cobrava o PENDENTE APAGADO, e o custo disso foi a queixa
    dela: com a Steam aberta o clique no «Steam Input» voltava e nada acendia.
    Na fileira que é grupo de rádio o chip aceso é o que ela ESCOLHEU; a ponte
    que ainda não subiu não some da tela, vai à faixa de pendência com a frase
    do dono (`ponte.Estado.frase`).

    A MORDIDA: faça `_o_jogo_na_lista` responder por `dado.ligados` em vez de
    `dado.lista` e o caso do meio apaga — a segunda asserção reprova.
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
    assert aba._estado_da_tela(ctx.state)["steam-input-aceso"] == "steam", (
        "o chip apagou no PENDENTE — a escolha dela sumiu da tela porque a "
        "Steam ainda não reescreveu o arquivo")
    dono = ponte.estado_da_ponte(allowlist=[APPID]).frase()
    assert dono in aba._faixa_do_pendente(ctx.state)[0], (
        "o PENDENTE acendeu sem dizer, na faixa, o que falta aplicar")

    # (a) LIGADO — a ponte de pé
    ponte.garantir_ponte(allowlist=[APPID])
    assert _valor(lar, APPID) == ponte.LIGADO
    aba.VIGIA_DO_STEAM_INPUT.esquecer()
    aba.VIGIA_DO_STEAM_INPUT.ler()
    assert aba._estado_da_tela(ctx.state)["steam-input-aceso"] == "steam", (
        "a ponte está de pé para este jogo e o chip continua apagado")
    assert aba._a_ponte_que_falta(ctx.state) == "", (
        "a ponte está de pé e a faixa ainda diz que falta")


def _com_o_caminho(caminho: str | None, *, modo_desktop: bool = False) -> Contexto:
    """O `_ctx()` com outro caminho vivo — ou na Navegação."""
    ctx = _ctx()
    ctx.state["gamepad_emulation"] = {"enabled": not modo_desktop,
                                      "flavor": caminho or "", "caminho": caminho}
    return ctx


def _ponte_de_pe() -> None:
    slo.add_appid_to_steam_input_allowlist(APPID)
    ponte.garantir_ponte(allowlist=[APPID])
    aba.VIGIA_DO_STEAM_INPUT.esquecer()
    aba.VIGIA_DO_STEAM_INPUT.ler()


def test_com_a_ponte_de_pe_so_o_steam_input_acende(lar) -> None:
    """UM ACESO SÓ — a D-2 da sprint, decidida por ela em 21/09/2026.

    A régua daqui cobrava os DOIS acesos («Sony DualSense» + «Steam Input»), o
    padrão que a sprint propôs enquanto a D-2 esperava a palavra dela. A
    palavra veio com a aba aberta: *"dois botões ligados no modo"*. O Steam
    Input é o DEGRAU 4 da escada (`ponte_escada.ESCADA[3]`, que senta sobre o
    caminho DualSense), e o degrau em que se está é um.

    A MORDIDA: apague o `if steam: aceso = ""` de `a01_jogar._estado_da_tela`
    e a primeira asserção reprova — os dois voltam a acender juntos.
    """
    _ponte_de_pe()

    fora = aba._estado_da_tela(_ctx().state)
    assert fora["modo-aceso"] == "", (
        f"o «Sony DualSense» acendeu junto com o Steam Input: {fora['modo-aceso']!r}")
    assert fora["steam-input-aceso"] == "steam", (
        f"a ponte está de pé e o Steam Input não acendeu: {fora['steam-input-aceso']!r}")
    assert "steam-input-aceso" in aba.DA_PAGINA, (
        "o endereço não está na promessa da aba — o `cobertura` passaria a "
        "contar um campo que a régua não confere")


@pytest.mark.parametrize(("caminho", "desktop", "quem"), [
    ("xbox", False, "xbox"),
    ("dualsense", True, "navegacao"),
])
def test_fora_do_degrau_4_acende_o_chip_de_verdade(lar, caminho, desktop, quem) -> None:
    """Sobre o Xbox, ou na Navegação, o degrau 4 não está de pé.

    A lista dela e o vdf dizem Steam Input para o jogo, e o chip dele NÃO
    acende: a ponte da escada é gamepad + DualSense + Steam Input, e a tela
    mostra o degrau em que se está. A MORDIDA: em `a01_jogar._estado_da_tela`,
    pergunte `_steam_input_da_tela` sem a guarda do caminho (a comparação com
    a linha do «Steam Input» em `o_que_o_chip_faz`) e o Steam Input volta a
    acender aqui, apagando o chip que está de verdade no comando.
    """
    _ponte_de_pe()

    fora = aba._estado_da_tela(_com_o_caminho(caminho, modo_desktop=desktop).state)
    assert fora["steam-input-aceso"] == "", (
        f"o Steam Input acendeu fora do degrau 4 ({caminho}, desktop={desktop})")
    assert fora["modo-aceso"] == quem, (
        f"esperava {quem!r} aceso e saiu {fora['modo-aceso']!r}")


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
        f"chips). Partilhando o `{aba01.CAMPO_DO_MODO}`, o Steam Input perde o "
        f"endereço por onde `_estado_da_tela` o acende — e nunca mais acende")

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


def test_toda_aba_que_fecha_a_steam_usa_o_relogio_de_confirmacao() -> None:
    """Dois relógios sobre a MESMA Steam deixam dois consentimentos pendurados.

    **A HISTÓRIA, e ela é curta.** Em 20/09/2026 a conferência mediu que armar
    a aba 07 e a aba 09 deixava os DOIS consentimentos de pé ao mesmo tempo —
    cada uma com o seu `_ARMADO`, as duas chamando `with_steam_closed`. Em 21/09
    os botões da 07 saíram e sobrou um relógio, o da 09. Em 24/09 o chip
    «Steam Input» da aba Jogar passou a fechar a Steam em dois cliques
    (`D-2309-STEAM-INPUT-A-FRASE-E-O-CLIQUE`), e o relógio voltou a morar num
    dono só: `pacotes/confirmacao.ARMADO`, que a 09 usa pelo mesmo objeto.

    O QUE ELA COBRA: toda aba que alcança `with_steam_closed` arma no relógio
    de `confirmacao` — ou não tem `_ARMADO` próprio, ou o `_ARMADO` dela É o
    `confirmacao.ARMADO`. A varredura é sobre os arquivos, não sobre uma
    lista: a aba que nascer amanhã entra sozinha.

    **O RECORTE É "QUEM FECHA A STEAM", e não "quem tem `_ARMADO`."**
    `a10_perfis` tem o dela e está CERTO: ela arma o «Remover perfil», que não
    toca a Steam de ninguém.

    A MORDIDA: dê à 09 um `_ARMADO: dict = {}` próprio (ou à 01 um relógio
    dela) e esta régua reprova nomeando a aba.
    """
    import importlib
    import pathlib as _pathlib

    pasta = _pathlib.Path(aba.__file__).parent
    fecham: list[str] = []
    com_relogio_proprio: list[str] = []
    for arquivo in sorted(pasta.glob("a[0-9][0-9]_*.py")):
        mod = importlib.import_module(
            f"hefesto_dualsense4unix.interface.pacotes.{arquivo.stem}")
        fecha = any(
            isinstance(no, ast.Call) and (
                (isinstance(no.func, ast.Attribute)
                 and no.func.attr == "with_steam_closed")
                or (isinstance(no.func, ast.Name)
                    and no.func.id == "with_steam_closed"))
            for no in ast.walk(ast.parse(inspect.getsource(mod)))
        )
        if not fecha:
            continue
        fecham.append(arquivo.name)
        if getattr(mod, "_ARMADO", confirmacao.ARMADO) is not confirmacao.ARMADO:
            com_relogio_proprio.append(arquivo.name)

    assert not com_relogio_proprio, (
        f"abas que fecham a Steam DELA com relógio PRÓPRIO: {com_relogio_proprio}. "
        f"Dois relógios sobre a MESMA Steam deixam dois consentimentos "
        f"pendurados ao mesmo tempo — o relógio é `pacotes/confirmacao.ARMADO`")
    assert {"a01_jogar.py", "a09_sistema.py"} <= set(fecham), (
        f"as abas que fecham a Steam mudaram ({fecham}) — esta régua conta com "
        f"a 01 e a 09; se uma saiu, reescreva-a no mesmo commit")


def test_o_chip_e_a_aba_09_dividem_um_relogio(lar, monkeypatch) -> None:
    """Armar o chip desarma o botão armado da 09, e vice-versa.

    A MORDIDA: dê à 09 um `_ARMADO` próprio e a segunda metade reprova — o
    chip armado deixa de desarmar o «Aplicar aos jogos da Steam».
    """
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

    monkeypatch.setattr(slo, "steam_running", lambda: True)
    monkeypatch.setattr(ponte, "steam_running", lambda: True)
    a09._ARMADO.update(gesto="aplicar-aos-jogos", ate=float("inf"))
    assert a09._armado_agora() == "aplicar-aos-jogos"

    assert aba.modo_steam(_ctx(), {}, PonteDeMentira()) == _ARMADO_NA_TELA
    assert a09._armado_agora() != "aplicar-aos-jogos", (
        "o chip armou e o «Aplicar aos jogos da Steam» continuou armado — dois "
        "consentimentos pendurados sobre a mesma Steam")

    a09._ARMADO.clear()
    a09._ARMADO.update(gesto="aplicar-aos-jogos", ate=float("inf"))
    assert aba._o_rotulo_do_chip(_ctx().state) == {
        f'[data-gesto="{aba.GESTO_DO_STEAM_INPUT}"]': "Steam Input"}, (
        "a 09 armou e o chip continuou dizendo «Fechar a Steam?»")


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


def test_sem_controle_na_mesa_nenhum_botao_do_modo_acende(lar) -> None:
    """O Modo apaga com a mesa vazia — pedido dela, 22/09/2026.

    *"ligado mesmo sem controle"*: a aba sem controle nenhum mostrava o «Steam
    Input» aceso, porque o daemon e a lista dela ainda diziam o degrau 4. A
    mesma ponte, com UM controle na mesa, volta a acender o Steam Input — é o
    que separa a cura de um Modo que nunca acende.

    A MORDIDA: faça `a01_jogar._a_fileira_com_a_mesa` devolver `tela` sempre e
    a primeira metade reprova com o «Steam Input» aceso sobre mesa nenhuma.
    """
    _ponte_de_pe()

    vazio = aba.pacote(_ctx())
    assert vazio["steam-input-aceso"] == "" and vazio["modo-aceso"] == "", (
        f"sem controle na mesa o Modo acendeu: steam={vazio['steam-input-aceso']!r} "
        f"modo={vazio['modo-aceso']!r}")
    assert vazio["pendente"] == "", "a faixa falou de um chip que a tela não acende"

    # A MATRIZ (regra dela, 23/09/2026): um no USB, um no BT, e os quatro.
    for mesa in (MESA_DE_QUATRO[:1], MESA_DE_QUATRO[1:2], MESA_DE_QUATRO):
        ctx = _ctx()
        ctx.mesa.extend(dict(c) for c in mesa)
        com = aba.pacote(ctx)
        vias = [c["via"] for c in mesa]
        assert com["steam-input-aceso"] == "steam", (
            f"com {vias} na mesa o Steam Input não acendeu: {com['steam-input-aceso']!r}")


@pytest.mark.parametrize(("mesa", "caminho", "desktop"), [
    ([], "dualsense", False),
    (MESA_DE_QUATRO, "xbox", False),
    (MESA_DE_QUATRO, "dualsense", True),
], ids=["mesa-vazia", "sobre-o-xbox", "na-navegacao"])
def test_a_faixa_so_fala_com_o_chip_aceso(lar, mesa, caminho, desktop) -> None:
    """«Liga quando a Steam fechar» diz o que FALTA ao chip aceso — e só a ele.

    O ARRANJO É O DIFÍCIL DE PROPÓSITO: o jogo está PENDENTE (na lista, o vdf
    em `"0"`), que é o único caso em que a frase existe. Com a ponte de pé a
    faixa calaria por outro motivo, e a régua passaria com a guarda arrancada
    — foi o que a primeira mordida mediu, com a mesa vazia e a ponte de pé.

    A MORDIDA: tire a guarda `steam-input-aceso` de `a01_jogar._o_que_o_chip_diz`
    e os três casos reprovam — a faixa fala de um botão que a tela não acende.
    """
    slo.add_appid_to_steam_input_allowlist(APPID)
    aba.VIGIA_DO_STEAM_INPUT.esquecer()
    aba.VIGIA_DO_STEAM_INPUT.ler()
    assert aba._a_ponte_que_falta(_ctx().state), "o arranjo não ficou PENDENTE"

    ctx = _com_o_caminho(caminho, modo_desktop=desktop)
    ctx.mesa.extend(dict(c) for c in mesa)
    fora = aba.pacote(ctx)
    assert fora["steam-input-aceso"] == ""
    assert (fora["pendente"], fora["pendente-ha"]) == ("", ""), (
        f"a faixa falou sem o chip aceso: {fora['pendente']!r}")

    # O CONTROLE DA RÉGUA: o mesmo PENDENTE, com o chip aceso, fala.
    aceso = _ctx()
    aceso.mesa.extend(dict(c) for c in MESA_DE_QUATRO)
    assert aba.pacote(aceso)["pendente"] == f"● {aba.STEAM_INPUT_ESPERA}"
