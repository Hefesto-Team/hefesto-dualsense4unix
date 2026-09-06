#!/usr/bin/env python3
"""A RÉGUA DA LINHA 110: "Editar em Todos" escreve a seção GLOBAL do perfil.

O QUE ESTA RÉGUA MEDE, e a queixa é do CSV da paridade
(`docs/data/paridade-gtk-html.csv`, linha 110 — `FALTA_NO_HTML`):

    *"o perfil salvo pelo HTML fica com dois overrides por MAC em vez de uma
    seção global, o que muda o que acontece quando ela liga um TERCEIRO
    controle: ele herda a global (que o HTML nunca escreveu), não o efeito que
    ela configurou."*

O DEFEITO, MEDIDO ANTES DA CURA
--------------------------------
**Toda** escrita de gatilho desta tela era por MAC. Os quatro gestos que
gravavam — `modo`, `pronto`, `ajuste` e `guardar` — passam por
`_com_os_gatilhos`, que escreve em `controllers[uniq].triggers`. Não havia, na
interface nova, caminho nenhum para `profile.triggers`; e é essa seção que um
aparelho novo herda, porque `profiles/manager` a aplica em broadcast
(`manager.py:450`) e `_controllers_to_specs` só cobre quem tem override.

Consequência com dois controles na mesa: ela põe `Rígido` nos dois (dois
cliques, dois overrides), liga um terceiro — e o terceiro nasce com o gatilho de
ontem. **Ela não tem como saber por quê**: os dois primeiros estão certos.

O GÊMEO NA GTK, e é dele que a cura foi copiada campo a campo:
`app/actions/triggers_actions._persist_params_to_draft`, no ramo em que
`alvo_de_edicao(self).uniq is None` — o alvo em `TODOS`. Ele grava o lado
editado na seção global E chama
`draft.with_override_fields_cleared("triggers", {side})`.

AS SEIS COISAS QUE ESTA RÉGUA COBRA
------------------------------------
1. **A seção GLOBAL recebe o efeito.** É a metade que não existia.
2. **O lado editado SAI dos overrides por controle.** Sem esta segunda metade a
   global seria escrita e continuaria perdendo: o override por MAC vence o
   global no merge por campo do backend.
3. **O TERCEIRO CONTROLE HERDA** — a mordida que importa, medida pelos DOIS
   donos da resolução (o motor, `manager._controllers_to_specs`, e a escada que
   a tela pinta, `a03_gatilhos._modo_de_agora`).
4. **O lado que ela NÃO tocou continua sendo opinião de quem a tinha.** Clicar
   em "Em todos" com só o L2 escolhido não pode apagar o R2 próprio de um
   controle.
5. **O pedido vai em BROADCAST**, sem `uniq` — é o que a GTK faz no alvo
   `TODOS`, e é o que faz o efeito chegar aos quatro aparelhos de uma vez.
6. **Sem perfil ativo o gesto DIZ**, e diz a metade que dói: o efeito foi aos
   controles ligados, mas o controle novo não vai pegá-lo.

A MORDIDA
---------
São DUAS, e elas mordem metades diferentes — foi por medi-las que a §2 desta
lista ganhou a régua do MOTOR, que a primeira versão não tinha.

**Mordida A** — troque `_com_os_gatilhos_de_todos(prof, dos_lados)` por
`_com_os_gatilhos(prof, uniq, dos_lados)` em :func:`em_todos`. É o produto de
antes desta sprint, escrito de novo, e **seis** casos reprovam: a global fica
`Off`, os overrides ficam de pé e o terceiro controle continua com o gatilho de
ontem, pelas duas réguas do caso 3.

**Mordida B** — apague só o laço que limpa os overrides. Reprova o caso 2
INTEIRO e **nada mais** — e essa é a medição que vale registrar: o caso 3 fica
VERDE, porque o terceiro controle nunca teve override e herda a global de
qualquer jeito. Quem paga a mordida B são os aparelhos que JÁ estavam na mesa:
o botão diz "em todos" e dois deles ficam com o efeito velho. Se o caso 2 não
existisse separado do 3, a metade mais visível deste gesto — a que ela sente na
mão no mesmo segundo — não teria régua nenhuma.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: Faixa sintética da casa — há dois portões de anonimato nesta árvore, e as
#: chaves abaixo são as que o esquema canoniza (`_validate_controllers_keys`).
UNIQ_1 = "aa:bb:cc:00:00:01"
UNIQ_2 = "aa:bb:cc:00:00:02"
#: O TERCEIRO NUNCA APARECE NA MESA nem no perfil — é ele a mordida. Ele não
#: pode ter override nenhum, senão a régua mediria a herança olhando para uma
#: opinião própria, que é o oposto do que ela existe para provar.
UNIQ_3 = "e8:47:3a:00:00:07"
CHAVE_1, CHAVE_2 = "aabbcc000001", "aabbcc000002"

PERFIL = "Em todos"
#: O modo da prova e o lado dela. `Rigid` porque é o mais simples dos 19 e o que
#: as outras réguas desta aba já usam — trocar de modo aqui só trocaria o
#: assunto sem trocar o que se mede.
MODO = "Rigid"


class PonteDeMentira:
    """O daemon que aceita tudo e ANOTA o `uniq` de cada pedido.

    O `uniq` é o que esta régua mais precisa ver: é a diferença entre um efeito
    que chega aos quatro aparelhos e um que chega a um só. As outras pontes de
    mentira desta casa guardam lado/modo/params e jogam o `uniq` fora.
    """

    def __init__(self, aceita: bool = True) -> None:
        self.aceita = aceita
        self.enviados: list[tuple[str, str, list[int], str | None]] = []
        self.chamadas: list[str] = []

    def trigger_set_detalhado(self, lado: str, modo: str, params: list[int],
                              uniq: str | None = None) -> Any:
        self.enviados.append((lado, modo, list(params), uniq))
        return self.aceita if self.aceita else (False, "o daemon recusou", None)

    def trigger_reset_detalhado(self, lado: str, uniq: str | None = None) -> Any:
        self.enviados.append((lado, "Off", [], uniq))
        return self.aceita if self.aceita else (False, "o daemon recusou", None)

    def chamar(self, metodo: str, **_: Any) -> bool:
        self.chamadas.append(metodo)
        return True


@pytest.fixture
def pac():
    import pacotes

    return pacotes


@pytest.fixture(autouse=True)
def rascunho_limpo():
    """O `_RASCUNHO` é estado de MÓDULO e atravessa testes.

    Sem esta limpeza, o caso do "nada mudou" leria o que outro caso aplicou e
    sairia pela porta do "já está assim" — verde sobre uma gravação que nunca
    aconteceu. É a mesma cerca de `test_o_gatilho_aplicado_vai_para_o_perfil`.
    """
    from pacotes.a03_gatilhos import esquecer_o_rascunho

    esquecer_o_rascunho()
    yield
    esquecer_o_rascunho()


def _profile(**extra: Any) -> Any:
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile

    return Profile(name=PERFIL, match=MatchManual(), **extra)


def _overrides(*lados_por_controle: tuple[str, dict[str, Any]]) -> dict[str, Any]:
    """`{chave: ControllerOverrides(triggers=…)}` com SÓ os lados pedidos escritos.

    O `model_fields_set` é o significado, e não a igualdade dos valores: um lado
    ausente daqui é *"sem opinião"* e herda o global — é o contrato que
    `profiles/manager._controllers_to_specs` lê. Montar com `TriggersConfig()`
    cheio faria a régua medir um perfil que o produto nunca escreve.
    """
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        TriggerConfig,
        TriggersConfig,
    )

    fora: dict[str, Any] = {}
    for chave, lados in lados_por_controle:
        fora[chave] = ControllerOverrides(
            triggers=TriggersConfig(**{k: TriggerConfig(**v) for k, v in lados.items()}))
    return fora


@pytest.fixture
def disco(monkeypatch):
    """Um disco de mentira com um `Profile` DE VERDADE dentro.

    O esquema é o do produto porque é ele que esta régua mede — um dublê
    aceitaria um `ControllerOverrides` malformado e o teste ficaria verde sobre
    um perfil que o disco recusaria.
    """
    from hefesto_dualsense4unix.profiles import loader

    estado: dict[str, Any] = {}
    gravados: list[Any] = []

    def _grava(prof: Any, **_: Any) -> None:
        gravados.append(prof)
        estado[prof.name] = prof

    monkeypatch.setattr(loader, "load_profile", lambda n: estado[n], raising=False)
    monkeypatch.setattr(loader, "save_profile", _grava, raising=False)

    def _por(prof: Any) -> None:
        estado[prof.name] = prof

    return estado, gravados, _por


def _ctx(pac, ativo: str = PERFIL, quantos: int = 2):
    """A mesa da régua: DOIS controles ligados, e o terceiro fora dela."""
    mesa = [{"uniq": UNIQ_1, "transport": "usb", "connected": True, "player": 1},
            {"uniq": UNIQ_2, "transport": "bt", "connected": True, "player": 2}][:quantos]
    return pac.Contexto(state={"active_profile": ativo, "controllers": mesa},
                        mesa=[], conectados=mesa, estados={})


def _gesto(pac):
    from pacotes.a03_gatilhos import GESTO_DE_TODOS

    fn = pac.gesto_da_pagina("03-gatilhos.html", GESTO_DE_TODOS)
    assert fn is not None, f"03-gatilhos.html:{GESTO_DE_TODOS} perdeu o dono"
    return fn


def _clique(sigla: str = "e") -> dict[str, Any]:
    """O clique que o piloto manda: a coluna do P1, recolhida por `@controle`."""
    return {"uniq": UNIQ_1, "controle": "p1",
            "forma": {f"modo-chave-{sigla}": MODO}}


# ---------------------------------------------------------------------------
# 1. A SEÇÃO GLOBAL RECEBE — a metade que não existia
# ---------------------------------------------------------------------------


def test_o_em_todos_escreve_a_secao_global_do_perfil(pac, disco) -> None:
    """`profile.triggers.left` passa a ser o efeito dela. É a linha 110 inteira."""
    _, gravados, por = disco
    por(_profile())

    _gesto(pac)(_ctx(pac), _clique(), PonteDeMentira())

    assert len(gravados) == 1, (
        f"o clique gravou {len(gravados)} vez(es). Sem gravar, o efeito vale "
        f"até a próxima troca de perfil e o controle novo nunca o pega.")
    assert gravados[0].triggers.left.mode == MODO, (
        f"a seção GLOBAL ficou em {gravados[0].triggers.left.mode!r}. É ela que "
        f"`profiles/manager` aplica em broadcast (manager.py:450) e é ela que um "
        f"aparelho sem override herda.")


def test_o_lado_que_ela_nao_tocou_nao_entra_no_global(pac, disco) -> None:
    """Clicar com só o L2 escolhido não pode escrever opinião sobre o R2."""
    _, gravados, por = disco
    por(_profile())

    _gesto(pac)(_ctx(pac), _clique("e"), PonteDeMentira())

    assert gravados[0].triggers.right.mode == "Off", (
        "o clique no L2 escreveu um efeito no gatilho direito de TODO MUNDO — "
        "o alcance deste botão é a mesa, e por isso um lado a mais aqui custa "
        "quatro aparelhos.")


# ---------------------------------------------------------------------------
# 2. O LADO EDITADO SAI DOS OVERRIDES — a segunda metade, sem a qual a primeira
#    não vale nada
# ---------------------------------------------------------------------------


def test_o_lado_editado_sai_dos_overrides_por_controle(pac, disco) -> None:
    """A regra do backend, espelhada: uma edição em "Todos" vale para todo mundo.

    `app/draft_config.with_override_fields_cleared` a escreve do lado do
    rascunho da janela GTK, e a razão dela é a mesma aqui: com o override
    intacto, `_controllers_to_specs` continua mandando o gatilho de ontem para
    quem já tinha opinião — a global seria escrita e não valeria.
    """
    _, gravados, por = disco
    por(_profile(controllers=_overrides(
        (CHAVE_1, {"left": {"mode": "Vibration", "params": [3, 8, 20]}}),
        (CHAVE_2, {"left": {"mode": "Off", "params": []}}))))

    _gesto(pac)(_ctx(pac), _clique(), PonteDeMentira())

    restou = gravados[0].controllers or {}
    assert not restou, (
        f"sobrou override depois do 'Em todos': {sorted(restou)}. As duas "
        f"entradas só falavam do lado editado — esvaziadas, elas têm de SAIR do "
        f"mapa, senão o JSON salvo guarda um endereço apontando para nada e a "
        f"próxima leitura conclui que aquele aparelho tem opinião.")


def test_quem_ja_estava_na_mesa_passa_a_receber_o_efeito_novo(pac, disco) -> None:
    """A régua da mordida B, e ela pergunta ao MOTOR — não ao arquivo.

    Sem a limpeza dos overrides o perfil fica com a global certa e o aparelho
    continua com o gatilho velho: `_controllers_to_specs` monta o `OutputSpec`
    de quem tem opinião, e o `OutputSpec` vence o broadcast da seção global.
    Ou seja, o botão diz *"em todos"* e os dois controles que ela tem na mão
    ficam de fora — a metade mais visível deste gesto, e a que o caso 3 NÃO
    cobre, porque o terceiro controle não tem override para atrapalhar.
    """
    from hefesto_dualsense4unix.profiles.manager import _controllers_to_specs

    _, gravados, por = disco
    por(_profile(controllers=_overrides(
        (CHAVE_1, {"left": {"mode": "Vibration", "params": [3, 8, 20]}}),)))

    _gesto(pac)(_ctx(pac), _clique(), PonteDeMentira())
    novo = gravados[0]

    spec = _controllers_to_specs(novo.controllers, novo.leds).get(CHAVE_1)
    tem_opiniao = spec is not None and getattr(spec, "trigger_left", None) is not None
    assert not tem_opiniao, (
        "o controle que já estava na mesa continua com opinião própria no L2 — "
        "o `OutputSpec` dele vence o broadcast da seção global, e o efeito que "
        "ela acabou de pôr 'em todos' não chega justamente a quem ela tem na "
        "mão.")


def test_o_lado_que_ela_nao_tocou_fica_no_override(pac, disco) -> None:
    """A limpeza é POR CAMPO: o R2 próprio de um controle sobrevive ao L2 em todos."""
    _, gravados, por = disco
    por(_profile(controllers=_overrides(
        (CHAVE_1, {"left": {"mode": "Vibration", "params": [3, 8, 20]},
                   "right": {"mode": "Machine", "params": [1, 8, 3, 3, 5, 10]}}),)))

    _gesto(pac)(_ctx(pac), _clique("e"), PonteDeMentira())

    dele = (gravados[0].controllers or {}).get(CHAVE_1)
    assert dele is not None and dele.triggers is not None, (
        "o override sumiu inteiro — o gatilho direito próprio deste controle "
        "era escolha dela e o clique foi no esquerdo")
    lados = dele.triggers.model_fields_set
    assert lados == {"right"}, (
        f"o override ficou com {sorted(lados)}. O 'Em todos' tira do mapa SÓ o "
        f"lado editado; tirar os dois apagaria uma escolha que ela nunca "
        f"desfez.")
    assert dele.triggers.right.mode == "Machine"


# ---------------------------------------------------------------------------
# 3. A MORDIDA — o terceiro controle herda, medido pelos DOIS donos
# ---------------------------------------------------------------------------


def test_um_terceiro_controle_herda_o_efeito_no_motor(pac, disco) -> None:
    """O dono da resolução é `profiles/manager`, e é a ele que se pergunta.

    Um controle sem entrada em `_controllers_to_specs` não tem `OutputSpec`
    próprio: o que chega nele é o broadcast da seção global (`manager.py:450`).
    Então a pergunta certa tem DUAS metades, e as duas estão aqui — o terceiro
    não pode ter spec, e a global tem de ser o efeito dela.
    """
    from hefesto_dualsense4unix.profiles.manager import _controllers_to_specs

    _, gravados, por = disco
    por(_profile(controllers=_overrides(
        (CHAVE_1, {"left": {"mode": "Vibration", "params": [3, 8, 20]}}),
        (CHAVE_2, {"left": {"mode": "Off", "params": []}}))))

    _gesto(pac)(_ctx(pac), _clique(), PonteDeMentira())
    novo = gravados[0]

    specs = _controllers_to_specs(novo.controllers, novo.leds)
    assert UNIQ_3.replace(":", "") not in specs, (
        "o terceiro controle ganhou opinião própria sem nunca ter estado na "
        "mesa — a régua estaria medindo um override, não a herança")
    assert novo.triggers.left.mode == MODO, (
        f"o terceiro controle vai receber {novo.triggers.left.mode!r} no L2. "
        f"Com a escrita por MAC ele recebe o gatilho de ontem, e ela não tem "
        f"como saber por quê: os dois primeiros estão certos.")


def test_um_terceiro_controle_herda_o_efeito_na_tela(pac, disco, monkeypatch) -> None:
    """A segunda régua, e ela é a ESCADA QUE A TELA PINTA — não o motor.

    Duas réguas independentes sobre o mesmo fato é regra desta casa, e aqui a
    razão é concreta: o motor e a tela leem o perfil por caminhos diferentes
    (`_controllers_to_specs` pelo pydantic, `_modo_de_agora` pelo JSON cru), e
    já houve dia nesta casa em que os dois discordaram. Se a coluna do terceiro
    controle mostrasse `Desligado` sobre um gatilho que o motor aplica, ela
    veria o produto mentindo — que é o defeito de sempre por outra porta.
    """
    from pacotes.a03_gatilhos import _modo_de_agora

    _, gravados, por = disco
    por(_profile(controllers=_overrides(
        (CHAVE_1, {"left": {"mode": "Vibration", "params": [3, 8, 20]}}),)))

    ctx = _ctx(pac)
    _gesto(pac)(ctx, _clique(), PonteDeMentira())

    # A TELA LÊ O DISCO, e o disco é o que o gesto acabou de gravar. O `ativo`
    # do módulo `perfil` abre o JSON, então é ele que se desvia — desviar o
    # `_modo_de_agora` seria a régua medindo a si mesma.
    import pacotes.a03_gatilhos as a03

    cru = gravados[0].model_dump(mode="json")
    monkeypatch.setattr(a03.perfil, "ativo", lambda _n: cru, raising=False)

    assert _modo_de_agora(ctx, UNIQ_3, "left") == MODO, (
        "a coluna de um controle que chegar depois vai mostrar o gatilho de "
        "ontem. É a linha 110 do CSV pela ponta que ela enxerga.")


# ---------------------------------------------------------------------------
# 4. O PEDIDO VAI EM BROADCAST
# ---------------------------------------------------------------------------


def test_o_pedido_vai_sem_uniq(pac, disco) -> None:
    """Sem `uniq` o daemon escreve nos controles todos — é o que a GTK faz.

    `triggers_actions._apply_trigger` passa `uniq=None` quando o alvo é `TODOS`,
    e `ipc_bridge._payload_trigger_set` só põe a chave no pedido quando ela é
    verdadeira. Endereçar aqui faria o botão prometer a mesa e entregar um.
    """
    _, _, por = disco
    por(_profile())
    p = PonteDeMentira()

    _gesto(pac)(_ctx(pac), _clique(), p)

    assert len(p.enviados) == 1, f"foram {len(p.enviados)} pedidos ao daemon"
    lado, modo, _params, uniq = p.enviados[0]
    assert (lado, modo) == ("left", MODO)
    assert not uniq, (
        f"o pedido saiu endereçado a {uniq!r}. Com endereço, o efeito chega a "
        f"UM aparelho e o botão diz 'em todos' — a tela afirmando o que não é.")


def test_o_rascunho_lembra_para_cada_controle_da_mesa(pac, disco) -> None:
    """As quatro colunas não podem voltar ao valor do disco no tique seguinte.

    O `_RASCUNHO` é a memória entre o clique e o tique (500 ms). Guardado sob o
    `uniq` vazio do broadcast, ele seria podado pela varredura de mesa
    (`_o_rascunho_e_de_quem_esta_na_mesa`) e a coluna do P2 piscaria de volta ao
    gatilho velho — o defeito mais visível que este gesto poderia ter.
    """
    from pacotes.a03_gatilhos import _do_rascunho

    _, _, por = disco
    por(_profile())

    _gesto(pac)(_ctx(pac), _clique(), PonteDeMentira())

    for quem in (UNIQ_1, UNIQ_2):
        seu = _do_rascunho(quem, "left")
        assert seu is not None and seu.get("mode") == MODO, (
            f"o rascunho não lembrou o efeito de {quem[-5:]} — a coluna dele "
            f"volta ao valor do disco no tique seguinte")
    assert _do_rascunho("", "left") is None, (
        "o rascunho guardou uma entrada sob o `uniq` vazio do broadcast; ela "
        "não é de aparelho nenhum e a poda de mesa a apaga")


# ---------------------------------------------------------------------------
# 5. AS RECUSAS, E ELAS DIZEM O QUE FICOU PELO CAMINHO
# ---------------------------------------------------------------------------


def test_sem_perfil_ativo_o_gesto_diz_o_que_o_controle_novo_perde(pac, disco) -> None:
    """O efeito foi aos ligados; o que não foi é justamente o ponto do botão."""
    _, gravados, _por = disco
    p = PonteDeMentira()

    with pytest.raises(RuntimeError) as erro:
        _gesto(pac)(_ctx(pac, ativo=""), _clique(), p)

    assert p.enviados, "o gesto recusou ANTES de mandar — o aparelho ficou sem"
    assert not gravados, "gravou sem perfil ativo"
    frase = str(erro.value)
    assert "perfil" in frase and "controle novo" in frase, (
        f"a frase não conta a metade que dói: {frase!r}. Sem perfil não há "
        f"seção global, e é a seção global que o controle novo herda.")


def test_a_coluna_vazia_recusa_dizendo(pac, disco) -> None:
    """Um lugar sem aparelho não tem efeito a espalhar, e o gesto explica isso."""
    _, _, por = disco
    por(_profile())

    with pytest.raises(RuntimeError) as erro:
        _gesto(pac)(_ctx(pac), {"controle": "p3", "forma": {"modo-chave-e": MODO}},
                    PonteDeMentira())

    assert "p3" in str(erro.value).lower() or "P3" in str(erro.value)


def test_a_coluna_sem_modo_recusa_dizendo(pac, disco) -> None:
    """`—` é "não há controle neste lugar", nunca "desligue o gatilho de todos"."""
    from pacotes.a03_gatilhos import TRAVESSAO

    _, gravados, por = disco
    por(_profile())

    with pytest.raises(RuntimeError):
        _gesto(pac)(_ctx(pac),
                    {"uniq": UNIQ_1, "controle": "p1",
                     "forma": {"modo-chave-e": TRAVESSAO}},
                    PonteDeMentira())
    assert not gravados, (
        "o travessão virou uma escrita no perfil de TODO MUNDO — ele é a marca "
        "de lugar vazio, e gravá-lo silenciaria o gatilho que o perfil dava aos "
        "quatro")


def test_o_daemon_que_recusa_nao_deixa_o_disco_mentir(pac, disco) -> None:
    """Gravar na global um efeito que o aparelho recusou é prometer amanhã o que
    não se fez hoje — a guarda é a mesma do rascunho."""
    _, gravados, por = disco
    por(_profile())

    with pytest.raises(RuntimeError):
        _gesto(pac)(_ctx(pac), _clique(), PonteDeMentira(aceita=False))

    assert not gravados, "o perfil recebeu um efeito que o daemon recusou"


# ---------------------------------------------------------------------------
# 6. O BOTÃO E O DONO — o endereço não pode andar sozinho
# ---------------------------------------------------------------------------


def test_a_bancada_traz_o_botao_com_o_endereco_que_o_pacote_declara() -> None:
    """O `data-gesto` do desenho e o `@gesto` do pacote são o MESMO nome.

    O gerador já lê `GESTO_DE_TODOS` do pacote em vez de digitá-lo — esta régua
    mede o ARQUIVO, que é a outra ponta: um desenho publicado com o nome antigo,
    ou um pacote renomeado sem regerar, dá a ela um botão que morre calado (o
    piloto só imprime `[gesto sem dono]` no stderr de quem lançou a janela).

    E ELA COBRA UM POR COLUNA, e não "pelo menos um": um botão de escopo global
    que só existisse na primeira coluna faria as outras três perderem o único
    caminho para a seção global do perfil, e nada na tela diria isso. A conta é
    contra as colunas EMITIDAS — o desenho manda coluna para os quatro lugares,
    e a do lugar vazio nasce travada pelo CSS do `data-conectado="nao"`, que é a
    mesma trava dos dois `<select>` e do "Guardar".
    """
    from hefesto_dualsense4unix.interface import onde
    from pacotes.a03_gatilhos import GESTO_DE_TODOS

    html = onde.pagina("03-gatilhos.html").read_text(encoding="utf-8")
    quantos = html.count(f'data-gesto="{GESTO_DE_TODOS}"')
    colunas = html.count('<div class="ctrl"')
    assert quantos == colunas and quantos >= 2, (
        f"{quantos} botões `{GESTO_DE_TODOS}` para {colunas} colunas. É o único "
        f"caminho desta tela para a seção global do perfil, e a coluna que "
        f"ficar sem ele não tem outro.")
    assert f'data-gesto="{GESTO_DE_TODOS}" data-hef-forma="@controle"' in html, (
        "o botão perdeu o `data-hef-forma` — sem ele o piloto não recolhe a "
        "coluna, e o gesto recusa por não saber qual efeito espalhar")


# ---------------------------------------------------------------------------
# 7. NADA MUDOU, NADA GRAVA
# ---------------------------------------------------------------------------


def test_o_perfil_que_ja_esta_assim_nao_e_regravado(pac, disco) -> None:
    """Regravar um perfil idêntico troca a data do arquivo e faz o daemon
    reaplicá-lo — e um `profile.switch` no meio de uma partida não é de graça."""
    from hefesto_dualsense4unix.profiles.schema import TriggerConfig, TriggersConfig
    from pacotes.a03_gatilhos import _padroes

    _, gravados, por = disco
    por(_profile(triggers=TriggersConfig(
        left=TriggerConfig(mode=MODO, params=_padroes(MODO)))))

    _gesto(pac)(_ctx(pac), _clique(), PonteDeMentira())

    assert not gravados, (
        "o gesto regravou um perfil que já estava assim. O efeito ainda vai ao "
        "aparelho — reenviar é de graça —, mas o disco não se toca.")
