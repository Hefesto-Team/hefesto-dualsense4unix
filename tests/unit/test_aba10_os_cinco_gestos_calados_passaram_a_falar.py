"""Os CINCO gestos da aba Perfis que gravavam no disco dela e não diziam nada.

03/09/2026. O ``test_aba10_os_gestos_dizem_o_que_fizeram`` curou os três
primeiros — ``ativar``, ``recarregar``, ``remover``. **Sobravam cinco**, e a
conta é a do próprio CSV de paridade (``docs/data/paridade-gtk-html.csv``, aba
``10-perfis``, "O desfecho na tela: o que aconteceu depois do clique"):

    A metade que fala foi curada em 02/09 e é boa (…). A metade que falta é o
    SUCESSO: na GTK ela sabe que renomeou ("Salvo como X"); no HTML o campo só
    volta ao normal e a lista muda no tique seguinte. Para gestos que ESCREVEM
    NO DISCO, silêncio no sucesso é a mesma classe de defeito que o toast
    existe para curar.

MEDIDO ANTES DA CURA, lendo o retorno de cada handler com dublê de ponte e de
disco — o que a tela recebia depois do clique:

    editor.nome        → None      renomeia o `.json` e cria outro:  MUDO
    editor.jogo        → None      reescreve a regra INTEIRA:        MUDO
    detectar           → None      grava um appid que ela não digitou: MUDO
    voltar-a-de-ontem  → None      substitui o arquivo inteiro:      MUDO
    remover            → None      apaga o `.json`: falava, mas só no tique
                                   seguinte (`_anotar`, até 500 ms)

O ``remover`` é o caso mais fino e o mais caro: ele **anotava** a frase, então
uma régua que só olhasse ``_DESFECHO`` daria verde. O que faltava era o
``_dizer`` — o retorno que o ``_deu_certo`` do piloto pinta NO ATO
(``hefesto_vivo.py``). No gesto mais destrutivo da aba, meio segundo de silêncio
é o intervalo em que ela clica de novo achando que o primeiro não pegou — e o
segundo clique acerta a linha seguinte.

**O QUE ESTA RÉGUA NÃO MEDE**, e dizer isso é o contrato: ela não abre janela.
Que o endereço ``perfis.desfecho`` EXISTE na página e que a tira acende com ele
é trabalho do ``aba10.py`` (que o exige no gerador) e do
``test_aba10_os_gestos_dizem_o_que_fizeram`` (que confere o embrulho ``mesa``).
Aqui se mede uma coisa só: **os cinco gestos devolvem a notícia, no vocabulário
do produto.**

A MORDIDA, e ela é por gesto: troque qualquer um dos cinco ``return _dizer(…)``
por um ``return None`` (que é como eles eram) e o teste daquele gesto reprova
dizendo qual ficou mudo. Trocar o ``_dizer`` do ``remover`` de volta por
``_anotar`` reprova em ``test_o_remover_pinta_no_ato_e_nao_no_tique_seguinte``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import loader

#: A MESA — endereço MASCARADO (octetos 4 e 5 zerados).
MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1, "cor": "cosmic-red",
     "nome": "Cosmic Red", "via": "USB", "transporte": "usb", "alvo": True,
     "mascara": "DualSense"},
]

#: O endereço da tira. Ele é UM só nos dois lados — o pacote o emite e o
#: `aba10.py` o escreve na página —, e é o mesmo nome que a régua irmã usa.
DESFECHO = "perfis.desfecho"


class PonteDeMentira:
    """Anota o que foi pedido e nunca fala com o daemon vivo."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...]]] = []

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append(("profile_switch", (nome,)))
        return True

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
        self.chamadas.append((metodo, a))
        return True


@pytest.fixture(autouse=True)
def _memoria_limpa(monkeypatch: pytest.MonkeyPatch) -> None:
    """Estado de MÓDULO herdado de outro teste não é prova de nada."""
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO", None, raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO_REBAIXAR", None, raising=False)
    monkeypatch.setattr(a10_perfis, "_DESFECHO", None, raising=False)
    monkeypatch.setattr(a10_perfis, "_PINTADO_PARA", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ULTIMO_TIQUE", 0.0, raising=False)


@pytest.fixture(autouse=True)
def _sem_a_biblioteca_dela(monkeypatch: pytest.MonkeyPatch) -> None:
    """O catálogo de jogos vem VAZIO — a régua não lê a Steam desta máquina.

    `_jogo_reconhecido` abre a biblioteca dela (os `.acf` e os `.desktop`) para
    traduzir o número em nome. Numa régua isso seria medir a máquina de quem
    roda: a mesma linha passaria aqui e reprovaria no CI, onde não há Steam.
    O teste que PRECISA do nome semeia o catálogo ele mesmo.
    """
    from hefesto_dualsense4unix.integrations import jogos_locais

    monkeypatch.setattr(jogos_locais, "catalogo_de_jogos", lambda *a, **k: [])


def _perfis(*nomes: str) -> list[Any]:
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    return [Profile(name=n, match=MatchAny(), priority=100 - i)
            for i, n in enumerate(nomes)]


def _o_disco_tem(monkeypatch: pytest.MonkeyPatch, *nomes: str) -> list[Any]:
    """A pasta de perfis, sem escrever no disco.

    SEM ISTO A PASTA É VAZIA: a ``conftest.py`` põe
    ``HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1`` em TODO teste.
    """
    todos = _perfis(*nomes)
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: todos)
    monkeypatch.setattr(
        loader, "load_profile",
        lambda nome, *a, **k: next(p for p in todos if p.name == nome))
    monkeypatch.setattr(loader, "save_profile", lambda *a, **k: None)
    monkeypatch.setattr(loader, "delete_profile", lambda *a, **k: None)
    return todos


def _ctx(ativo: str | None = None, classe: str = "") -> Contexto:
    return Contexto(
        state={"active_profile": ativo, "window_detect_last_class": classe},
        mesa=list(MESA), conectados=list(MESA), estados={})


def _o_marcador_diz(monkeypatch: pytest.MonkeyPatch, nome: str | None) -> None:
    from hefesto_dualsense4unix.app.actions import profiles_actions

    monkeypatch.setattr(profiles_actions, "perfil_que_ela_ativou", lambda: nome)


def _frase(fora: Any) -> str:
    """A frase que o gesto mandou para a tira, ou ``""`` se ele ficou mudo.

    Ela é lida do EMBRULHO que o gesto devolveu — ``{"mesa": {…}}`` —, e não do
    ``_DESFECHO`` do módulo, de propósito: o ``_anotar`` sozinho enche o
    ``_DESFECHO`` e a tela continua esperando o tique. O que o piloto pinta no
    ato é o RETORNO.
    """
    if not isinstance(fora, dict):
        return ""
    return str((fora.get("mesa") or {}).get(DESFECHO) or "")


# --------------------------------------------------------------------------
# 1. RENOMEAR — a frase é a do produto, `mensagem_do_salvar`
# --------------------------------------------------------------------------
def test_o_renomear_diz_de_onde_para_onde(monkeypatch: pytest.MonkeyPatch) -> None:
    """O gesto apaga um `.json` e cria outro, e dizia NADA.

    MORDIDA: apague o ``return _dizer(…)`` do fim de ``editor_nome`` e este
    teste reprova com a frase vazia.
    """
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        mensagem_do_salvar,
    )

    _o_disco_tem(monkeypatch, "Pragmata", "Sackboy")
    _o_marcador_diz(monkeypatch, "Sackboy")
    ctx, ponte = _ctx(), PonteDeMentira()
    a10_perfis.selecionar(ctx, {"texto": "Pragmata"}, ponte)

    fora = a10_perfis.editor_nome(
        ctx, {"valor": "Pragmata BR", "evento": "change"}, ponte)

    assert _frase(fora) == mensagem_do_salvar("Pragmata BR",
                                              renomeado_de="Pragmata"), (
        "o renomear não devolveu a frase do produto — e a frase tem de ser a "
        "DELE (`mensagem_do_salvar`), não uma segunda escrita à mão aqui")
    assert "Pragmata" in _frase(fora) and "Pragmata BR" in _frase(fora), (
        "a frase precisa nomear os DOIS lados: um renomear que só diz o nome "
        "novo não deixa ela desfazer pelo `profile restore <nome-antigo>`")


def test_o_renomear_que_nao_mudou_nada_continua_mudo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clicar dentro do campo manda o valor que já estava lá — e não é notícia.

    O ``_so_mudou`` já barrava o `click`; o que esta linha guarda é que a tira
    não passe a acender por um clique que não gravou nada. Um desfecho que
    aparece sem gesto é a tela afirmando um trabalho que ninguém fez.
    """
    _o_disco_tem(monkeypatch, "Pragmata")
    _o_marcador_diz(monkeypatch, "Pragmata")
    ctx, ponte = _ctx(), PonteDeMentira()

    assert a10_perfis.editor_nome(
        ctx, {"valor": "Pragmata", "evento": "click"}, ponte) is None
    assert a10_perfis.editor_nome(
        ctx, {"valor": "Pragmata", "evento": "change"}, ponte) is None, (
        "o mesmo nome de novo não é um renomear, e não pode virar notícia")


# --------------------------------------------------------------------------
# 2. O CAMPO DO JOGO — diz a REGRA nova, no vocabulário da coluna "Quando usar"
# --------------------------------------------------------------------------
def test_o_campo_do_jogo_diz_em_que_o_perfil_passou_a_valer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ele reescreve o `match` INTEIRO e movia o seletor junto, calado.

    MORDIDA: apague o ``return _dizer(_agora_vale_em(…))`` de ``editor_jogo`` e
    este teste reprova com a frase vazia.
    """
    from hefesto_dualsense4unix.app.actions.profiles_actions import _match_label

    todos = _o_disco_tem(monkeypatch, "Pragmata")
    _o_marcador_diz(monkeypatch, "Pragmata")
    ctx, ponte = _ctx(), PonteDeMentira()

    fora = a10_perfis.editor_jogo(
        ctx, {"valor": "1599660", "evento": "change"}, ponte)

    assert _frase(fora), "o campo do jogo gravou a regra e ficou mudo"
    # O RÓTULO É LIDO DO DONO, e não digitado: `_match_label` é a mesma função
    # pura que alimenta a coluna "Quando usar". Cravar "Só neste programa" aqui
    # faria esta régua reprovar no dia em que a coluna mudasse de palavra.
    assert _match_label(todos[0].match) in _frase(fora), (
        f"o desfecho não fala o mesmo idioma da coluna 'Quando usar' — ela diz "
        f"{_match_label(todos[0].match)!r} e a tira diz {_frase(fora)!r}")


def test_o_campo_do_jogo_traduz_o_numero_no_nome_do_jogo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`1599660` sozinho não diz a ela que aquele é o Mortal Kombat 1.

    JOGO-QUE-SE-DIZ-01. A janela estável põe o nome ao lado do campo
    (``profile_jogo_reconhecido``); esta aba não tem esse rótulo no desenho, e
    até ter, o nome chega pelo desfecho — que é o instante em que a pergunta
    "é esse jogo mesmo?" existe.

    MORDIDA: troque o ``_jogo_reconhecido`` por ``""`` e este teste reprova.
    """
    from hefesto_dualsense4unix.integrations import jogos_locais

    _o_disco_tem(monkeypatch, "Pragmata")
    _o_marcador_diz(monkeypatch, "Pragmata")
    monkeypatch.setattr(
        jogos_locais, "catalogo_de_jogos",
        lambda *a, **k: [jogos_locais.JogoLocal(appid="1599660",
                                                nome="Mortal Kombat 1",
                                                fonte="steam")])
    ctx, ponte = _ctx(), PonteDeMentira()

    fora = a10_perfis.editor_jogo(
        ctx, {"valor": "1599660", "evento": "change"}, ponte)

    assert "Mortal Kombat 1" in _frase(fora), (
        f"o número entrou e o nome não voltou: {_frase(fora)!r}. O desfecho é "
        f"o único lugar desta aba onde ela confere o que digitou")


def test_a_biblioteca_ilegivel_nao_vira_recusa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O perfil JÁ ESTÁ NO DISCO quando o nome do jogo é buscado.

    Uma exceção lendo a biblioteca dela transformaria uma gravação
    bem-sucedida em tarja de recusa — o mesmo contrato de ``_com_a_carona``.

    MORDIDA: tire o ``try/except`` de ``_jogo_reconhecido`` e este teste
    reprova com o ``OSError`` subindo pelo gesto.
    """
    from hefesto_dualsense4unix.integrations import jogos_locais

    def _explode(*a: Any, **k: Any) -> Any:
        raise OSError("a biblioteca dela não abriu")

    _o_disco_tem(monkeypatch, "Pragmata")
    _o_marcador_diz(monkeypatch, "Pragmata")
    monkeypatch.setattr(jogos_locais, "catalogo_de_jogos", _explode)
    ctx, ponte = _ctx(), PonteDeMentira()

    fora = a10_perfis.editor_jogo(
        ctx, {"valor": "1599660", "evento": "change"}, ponte)

    assert _frase(fora), "a leitura da biblioteca derrubou o desfecho inteiro"


# --------------------------------------------------------------------------
# 3. DETECTAR — grava um appid que ela não digitou, e agora diz qual
# --------------------------------------------------------------------------
def test_o_detectar_diz_o_jogo_que_achou(monkeypatch: pytest.MonkeyPatch) -> None:
    """O botão grava a regra a partir de uma janela que ela não está olhando.

    A recusa já nomeava a classe que o detector viu; o SUCESSO não dizia nada —
    e é o caso em que dizer vale mais.

    MORDIDA: apague o ``return _dizer(_agora_vale_em(…))`` de ``detectar``.
    """
    _o_disco_tem(monkeypatch, "Pragmata")
    _o_marcador_diz(monkeypatch, "Pragmata")
    ctx, ponte = _ctx(classe="steam_app_1599660"), PonteDeMentira()

    fora = a10_perfis.detectar(ctx, {}, ponte)

    assert _frase(fora), "o Detectar gravou o appid e ficou mudo"
    assert "Pragmata" in _frase(fora), (
        "o desfecho não nomeia o perfil que mudou — com a lista ao lado, uma "
        "frase sem nome não diz em qual linha o trabalho caiu")


def test_o_detectar_que_recusa_continua_recusando_dizendo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A metade que já falava não pode ter sido trocada pela nova.

    Sem jogo da Steam em foco o gesto levanta ``RuntimeError`` — que o piloto
    vira TARJA. Um desfecho no lugar da recusa seria a tela dizendo que gravou.
    """
    _o_disco_tem(monkeypatch, "Pragmata")
    _o_marcador_diz(monkeypatch, "Pragmata")
    ctx, ponte = _ctx(classe="firefox"), PonteDeMentira()

    with pytest.raises(RuntimeError, match="não achei jogo da Steam"):
        a10_perfis.detectar(ctx, {}, ponte)


# --------------------------------------------------------------------------
# 4. VOLTAR À DE ONTEM — o desfazer mudo era indistinguível do que não pegou
# --------------------------------------------------------------------------
def test_o_voltar_a_de_ontem_diz_qual_versao_voltou(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ele substitui o arquivo INTEIRO e a tela não mudava nada visível.

    O editor mostra nome e regra; o que volta é gatilho, luz, vibração e
    máscara — nada disso está na tela desta aba. Um desfazer mudo é
    indistinguível de um desfazer que não pegou.

    O CARIMBO VAI SEM O `.json`: é a forma que o ``--em`` do ``profile
    restore`` aceita (``loader.py`` casa as duas), então a frase é copiável
    para o comando que volta a OUTRA versão.

    MORDIDA: apague o ``return _dizer(…)`` de ``voltar_a_de_ontem``.
    """
    _o_disco_tem(monkeypatch, "Pragmata", "Sackboy")
    _o_marcador_diz(monkeypatch, "Sackboy")
    monkeypatch.setattr(
        loader, "restaurar_do_historico",
        lambda n, *a, **k: (Path(f"/perfis/{n}.json"),
                            Path("2026-09-03T04-00-00.json")))
    ctx, ponte = _ctx(), PonteDeMentira()

    fora = a10_perfis.voltar_a_de_ontem(ctx, {}, ponte)

    assert "Sackboy" in _frase(fora), (
        f"o desfazer não nomeia o perfil restaurado: {_frase(fora)!r}")
    assert "2026-09-03T04-00-00" in _frase(fora), (
        "o carimbo da versão não chegou à tira — sem ele a frase não diz de "
        "onde veio, e ela não tem como pedir outra pelo `profile restore --em`")
    assert ".json" not in _frase(fora), (
        "o carimbo saiu com a extensão; a forma copiável para o `--em` é o "
        "nome sem `.json`")


# --------------------------------------------------------------------------
# 5. REMOVER — falava, mas só no tique seguinte
# --------------------------------------------------------------------------
def test_o_remover_pinta_no_ato_e_nao_no_tique_seguinte(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_anotar` guarda; só `_dizer` DEVOLVE para o piloto pintar no ato.

    É o gesto mais destrutivo da aba, e meio segundo de silêncio é o intervalo
    em que ela clica de novo achando que o primeiro não pegou — com a diferença
    de que aqui o segundo clique acerta a linha SEGUINTE.

    MORDIDA: troque o ``return _dizer(…)`` do fim de ``remover`` de volta pelo
    ``_anotar(…)`` (que é como ele era) e este teste reprova: o ``_DESFECHO``
    do módulo continua cheio e o RETORNO volta a ser ``None``.
    """
    _o_disco_tem(monkeypatch, "Pragmata", "Sackboy")
    _o_marcador_diz(monkeypatch, "Sackboy")
    ctx, ponte = _ctx(), PonteDeMentira()
    a10_perfis.selecionar(ctx, {"texto": "Pragmata"}, ponte)

    with pytest.raises(RuntimeError, match="Clique em Remover de novo"):
        a10_perfis.remover(ctx, {}, ponte)
    fora = a10_perfis.remover(ctx, {}, ponte)

    assert _frase(fora) == "Perfil removido: Pragmata", (
        f"o Remover não devolveu a frase da janela estável: {_frase(fora)!r}")
    # E A ORDEM CONTINUA: o `launch_env.refresh` é o que impede o
    # `steam_app_<id>.env` do perfil morto de ficar rançoso (DEDUP-04).
    assert ("launch_env.refresh", ()) in ponte.chamadas


# --------------------------------------------------------------------------
# 6. O INVENTÁRIO — nenhum gesto que grava no disco pode voltar a ficar mudo
# --------------------------------------------------------------------------
#: OS GESTOS DESTA ABA QUE ESCREVEM NO DISCO DELA, e por isso devem notícia.
#:
#: A LISTA É CURTA E DECLARADA de propósito: ela é o inventário que a próxima
#: pessoa lê antes de acrescentar um gesto. Quem escrever o sexto escritor e não
#: lhe der desfecho tem de vir aqui apagar o nome — e apagar um nome é um ato
#: que se vê no diff, ao contrário de esquecer um `return`.
#:
#: `selecionar` NÃO ESTÁ AQUI e não é esquecimento: ele grava um nome num
#: módulo, não no disco, e a janela estável também não dá toast por seleção.
#: `editor.estilo` também não: ele SEMPRE levanta — o desfecho dele é a recusa.
ESCRITORES = ("editor.nome", "editor.jogo", "detectar", "voltar-a-de-ontem",
              "novo", "duplicar", "remover", "ativar", "recarregar")


def test_todo_gesto_que_grava_devolve_o_embrulho_que_a_pintura_le() -> None:
    """Nenhum dos nove pode ficar sem o caminho de volta.

    Esta régua lê a ANOTAÇÃO DE RETORNO do handler, e não o corpo: um gesto que
    volte a devolver só ``None`` não tem por onde a tira acender no ato — e é
    exatamente a forma do defeito que os cinco tinham.

    MORDIDA: troque a anotação de qualquer um dos nove para ``-> None`` e este
    teste reprova nomeando o gesto.
    """
    import inspect

    from hefesto_dualsense4unix.interface.pacotes import GESTOS

    mudos: list[str] = []
    for nome in ESCRITORES:
        fn = GESTOS.get(("10-perfis.html", nome))
        assert fn is not None, f"o gesto {nome!r} sumiu da aba 10"
        retorno = str(inspect.signature(fn).return_annotation)
        if "dict" not in retorno:
            mudos.append(f"{nome} → {retorno}")
    assert not mudos, (
        "estes gestos gravam no disco dela e não têm caminho de volta para a "
        f"tira: {', '.join(mudos)}")
