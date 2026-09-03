"""A aba Perfis parou de perguntar só ao daemon qual perfil está valendo.

O DEFEITO, e ele desligava TRÊS guardas de uma vez. A aba lia
``ctx.state.get("active_profile")`` cru, em cinco lugares. A docstring do dono
da pergunta — ``profiles_actions.perfil_que_esta_valendo:574`` — diz, com estas
palavras, que o daemon responder ``active_profile: null`` é *"o estado da
máquina dela hoje"*. Com o ``null``:

    ativar     deixava de recusar o perfil que JÁ está valendo, e voltava a
               dizer "aplicado" sobre um não-evento
    remover    deixava de recusar apagar o perfil que está valendo — e o daemon
               segue aplicando um arquivo que não existe mais, sem uma palavra
               na tela (é o §P7 inteiro)
    a lista    perdia o realce da linha certa

O DONO EXISTE DESDE 25/08 e a interface nova nunca o chamou: ele está na fila do
reuso medida em 02/09 — 209 funções que a GTK usa e a HTML não chama. Ele
consulta o daemon primeiro e, só se ele calar, o marcador em disco, pelo MESMO
caminho do boot (``resolve_boot_profile``).

E A FRASE DA RECUSA DO REMOVER TAMBÉM É DO PRODUTO agora:
``frase_da_remocao_do_perfil_ativo`` (``profiles_actions:633``) é o aviso do
diálogo da janela estável — três parágrafos que dizem o quê, por quê e o que
fazer. A que estava aqui era uma segunda verdade escrita à mão, e dizia menos:
não contava que o controle segue com a cor, os gatilhos e a vibração aplicados
depois de o arquivo sumir.

**O ``nao_sei`` CALA, e é o que separa esta cura de um alarme falso.** "Não sei
qual está valendo" e "não há nenhum valendo" são fatos diferentes; transformar o
primeiro em recusa travaria o Remover por ignorância nossa.

FATO SUBSTITUÍDO — 02/09/2026. Esta última frase é verdadeira da FUNÇÃO e
**vazia nesta aba**: ``perfil_que_esta_valendo`` só devolve ``nao_sei`` quando o
``state`` não é dicionário, e ``Contexto.state`` é tipado ``dict[str, Any]`` e
nasce dicionário nos dois únicos lugares onde o piloto o constrói. O ramo que
esta aba alcança é o ``nenhum``. Quem cobre a distinção é
``test_p7_remover_diz_que_esta_apagando_o_que_vale.py``, contra a função.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import profiles_actions
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis


class PonteDeMentira:
    """Anota o que foi pedido e nunca fala com o daemon vivo."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...]]] = []

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append(("profile_switch", (nome,)))
        return True

    def chamar(self, metodo: str, *args: Any, **kw: Any) -> Any:
        self.chamadas.append((metodo, args))
        return True

    # `resultado` ENTROU EM 03/09/2026 com o ELO-MUDO-01: o `ativar` passou a
    # ler o CORPO da resposta do daemon (`secoes`) em vez do booleano, que é a
    # diferença entre "ativado" e "ativado, menos o que o lock manual
    # descartou". O dublê devolve `{}` — corpo sem relatório, que é o caso do
    # daemon antigo e faz `mensagem_de_ativacao` cair na frase de sempre.
    def resultado(self, metodo: str, *args: Any, **kw: Any) -> Any:
        self.chamadas.append((metodo, tuple(kw.values())))
        return {}


@pytest.fixture(autouse=True)
def _memoria_limpa(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_ESCOLHIDO` e `_ARMADO` são estado de MÓDULO — nenhum teste herda o do
    anterior. O `_ARMADO` importa em especial: é ele que decide se o segundo
    clique do Remover APAGA."""
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO", None, raising=False)


def _o_disco_diz(monkeypatch: pytest.MonkeyPatch, nome: str | None) -> None:
    """O marcador em disco, sem escrever no disco.

    ``perfil_que_esta_valendo`` engole exceções desta chamada e devolve
    ``nao_sei``; então ``None`` aqui é "o disco não sabe", e não "não há".
    """
    monkeypatch.setattr(profiles_actions, "perfil_que_ela_ativou", lambda: nome)


# --------------------------------------------------------------------------
# 1. O ATIVAR
# --------------------------------------------------------------------------
def test_ativar_recusa_o_mesmo_perfil_mesmo_com_o_daemon_calado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Daemon com ``active_profile: null`` e o marcador em disco valendo.

    ANTES desta cura o gesto passava direto: ``ativo`` saía vazio, a terceira
    guarda não disparava, e o botão respondia "aplicado" sobre uma troca que não
    trocou nada — exatamente o defeito que a guarda existe para matar, de volta
    pela porta dos fundos.

    MORDIDA: troque ``_valendo(ctx)`` por ``ctx.state.get("active_profile")`` em
    ``ativar`` e este teste reprova — a ponte registra o ``profile_switch``.
    """
    _o_disco_diz(monkeypatch, "meu_perfil")
    a10_perfis._ESCOLHIDO = "meu_perfil"
    ponte = PonteDeMentira()
    with pytest.raises(RuntimeError, match="já é o perfil que está valendo"):
        a10_perfis.ativar(Contexto(state={"active_profile": None}),
                          {"texto": "Ativar"}, ponte)
    assert ponte.chamadas == [], (
        f"o gesto falou com a ponte sobre um não-evento: {ponte.chamadas}")


def test_o_daemon_vence_o_disco_quando_os_dois_falam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ordem do dono é deliberada: o daemon é quem APLICOU as seções.

    Com o daemon dizendo "Ação" e o disco dizendo "meu_perfil", ativar
    "meu_perfil" tem de PASSAR — o marcador em disco está velho.
    """
    _o_disco_diz(monkeypatch, "meu_perfil")
    a10_perfis._ESCOLHIDO = "meu_perfil"
    ponte = PonteDeMentira()
    a10_perfis.ativar(Contexto(state={"active_profile": "Ação"}),  # noqa-acento: id
                      {"texto": "Ativar"}, ponte)
    assert ponte.chamadas == [("profile.switch", ("meu_perfil",))]


# --------------------------------------------------------------------------
# 2. O REMOVER — o §P7, que é o mais caro
# --------------------------------------------------------------------------
def _remover(nome: str, state: dict[str, Any]) -> tuple[PonteDeMentira, Exception | None]:
    a10_perfis._ESCOLHIDO = nome
    ponte = PonteDeMentira()
    try:
        a10_perfis.remover(Contexto(state=state), {}, ponte)
    except Exception as erro:
        return ponte, erro
    return ponte, None


def test_remover_recusa_o_perfil_que_vale_pelo_disco(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Daemon calado, marcador em disco valendo: o Remover RECUSA.

    Este é o §P7 chegando à interface nova. Antes, com o daemon em ``null``, o
    primeiro clique ARMAVA e o segundo apagava o perfil que estava valendo — e
    depois disso o daemon segue com as seções daquele perfil no controle, o
    marcador em disco aponta para um arquivo que não existe, e nada na tela diz.

    MORDIDA: troque a chamada a ``frase_da_remocao_do_perfil_ativo`` por um
    ``mesmo_slug`` contra ``ctx.state`` e este teste reprova: o gesto arma em
    vez de recusar.
    """
    _o_disco_diz(monkeypatch, "meu_perfil")
    ponte, erro = _remover("meu_perfil", {"active_profile": None})
    assert isinstance(erro, RuntimeError), "o Remover armou sobre o perfil que vale"
    assert str(erro) == profiles_actions._AVISO_DA_REMOCAO_DO_ATIVO, (
        "a recusa não é a frase do produto — há uma segunda verdade escrita à mão")
    assert ponte.chamadas == []


def test_a_recusa_do_remover_e_a_frase_inteira_do_produto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """As TRÊS partes da frase chegam: o quê, o que não se desfaz, e o que fazer.

    A frase escrita à mão que estava aqui só tinha a primeira e a terceira.
    """
    _o_disco_diz(monkeypatch, "meu_perfil")
    _, erro = _remover("meu_perfil", {})
    texto = str(erro)
    assert "está valendo agora" in texto
    assert "seguem aplicados" in texto, "sumiu o que a remoção NÃO desfaz"
    assert "ative outro perfil em seguida" in texto


def test_com_ninguem_valendo_o_remover_nao_trava(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem daemon e sem marcador em disco, o Remover SEGUE para a pergunta.

    A tela não pode AFIRMAR que este é o perfil que está valendo. A guarda que
    sobra é a pergunta no rótulo do botão, que continua de pé: o primeiro clique
    arma e levanta.

    TÍTULO CORRIGIDO — 02/09/2026, achado de auditoria. Ele dizia
    ``…quando_ninguem_sabe_quem_vale…`` e a docstring prometia cobrir o ramo
    ``nao_sei``. **Ele nunca chega lá, e não é bug deste teste — é inalcançável
    por esta aba:** ``perfil_que_esta_valendo`` só devolve ``nao_sei`` quando o
    ``state`` NÃO é dicionário (``houve_resposta = isinstance(state, dict)``), e
    ``Contexto.state`` é tipado ``dict[str, Any]`` e nasce dicionário nos dois
    únicos lugares onde o piloto o constrói. O que esta régua exercita é o ramo
    ``nenhum`` — daemon calado E disco calado —, que é um estado real da máquina
    dela. A distinção ``nao_sei``/``nenhum`` continua sendo do produto, e quem a
    cobre é ``test_p7_remover_diz_que_esta_apagando_o_que_vale.py``.

    MORDIDA: faça a recusa disparar quando ``perfil_que_esta_valendo`` não sabe
    de ninguém (``if aviso or not _vale.nome:``) e este teste reprova — o
    Remover ficaria travado numa máquina com o daemon parado e sem marcador.
    """
    def _explode() -> str:
        raise OSError("o disco não respondeu")

    monkeypatch.setattr(profiles_actions, "perfil_que_ela_ativou", _explode)
    # O ramo medido, escrito no próprio teste para não voltar a ser suposto.
    assert profiles_actions.perfil_que_esta_valendo({}).fonte == "nenhum"
    _, erro = _remover("meu_perfil", {})
    assert isinstance(erro, RuntimeError), (
        f"esperava a pergunta do rótulo, veio {type(erro).__name__}: {erro}")
    assert "Clique em Remover de novo" in str(erro)


def test_remover_outro_perfil_continua_perguntando_e_apagando(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A guarda não pode fechar o gesto: apagar um perfil é o trabalho dele.

    O primeiro clique ARMA (``RuntimeError`` com a pergunta) e o segundo apaga.
    """
    _o_disco_diz(monkeypatch, "meu_perfil")
    apagados: list[str] = []
    from hefesto_dualsense4unix.profiles import loader

    monkeypatch.setattr(loader, "delete_profile", lambda n: apagados.append(n))

    _, primeiro = _remover("Ação", {})  # noqa-acento: id
    assert isinstance(primeiro, RuntimeError)
    assert "Apagar “Ação”" in str(primeiro)
    assert apagados == [], "o primeiro clique apagou sem perguntar"

    ponte, segundo = _remover("Ação", {})  # noqa-acento: id
    assert segundo is None, f"o segundo clique foi recusado: {segundo}"
    assert apagados == ["Ação"]
    assert ("launch_env.refresh", ()) in ponte.chamadas


# --------------------------------------------------------------------------
# 3. NENHUM LUGAR DA ABA VOLTA A LER O `state` CRU
# --------------------------------------------------------------------------
def test_a_aba_nao_le_mais_o_active_profile_cru() -> None:
    """A régua mecânica, e ela é o que impede a volta pela porta dos fundos.

    Cinco lugares liam ``ctx.state.get("active_profile")`` e todos passaram a
    chamar ``_valendo``. Uma cura em quatro dos cinco deixaria a aba respondendo
    diferente conforme o botão — que é pior que o defeito original.

    **ELA MEDE TEXTO, E TEXTO SE REESCREVE** — achado de auditoria, 02/09/2026.
    A reversão dos quatro sítios que não tinham régua de ATO, escrita por
    concatenação (``state.get("act" "ive_profile")``), deixou 1080 testes
    verdes: qualquer f-string, ``.format()`` ou constante de módulo produz o
    mesmo efeito. Ela FICA — pega o descuido, que é o caso comum — mas quem
    segura o defeito é a régua de comportamento, e agora existe para os cinco:

        ativar               este arquivo, ``test_ativar_recusa_o_mesmo_perfil…``
        remover              este arquivo, ``test_remover_recusa_o_perfil_que_vale…``
        pacote               ``test_a_aba_perfis_nomeia_o_alvo_que_ela_vai_apagar``
                             — ``…_o_marcador_que_existe_continua_valendo``
        _perfil_do_editor    idem — ``…_o_editor_abre_no_perfil_que_o_disco_diz…``
        voltar_a_de_ontem    idem — ``…_acha_o_perfil_e_manda_reaplicar`` (os dois
                             sítios no mesmo clique)

    MORDIDA: escreva ``ctx.state.get("active_profile")`` em qualquer gesto desta
    aba e este teste reprova nomeando a linha.
    """
    import inspect

    fonte = inspect.getsource(a10_perfis)
    linhas = [(i, x) for i, x in enumerate(fonte.splitlines(), 1)
              if 'ctx.state.get("active_profile")' in x
              # A docstring do `_valendo` CITA a leitura crua para explicar o
              # defeito. Citar não é ler.
              and not x.lstrip().startswith(("#", "`", "*"))
              and "_valendo" not in x]
    assert not linhas, (
        "a aba voltou a perguntar só ao daemon: "
        + "; ".join(f"linha {i}: {x.strip()}" for i, x in linhas))
