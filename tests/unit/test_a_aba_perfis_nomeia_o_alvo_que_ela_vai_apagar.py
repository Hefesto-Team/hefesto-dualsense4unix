"""A aba Perfis parou de anunciar um perfil e agir sobre outro.

TRÊS DEFEITOS DE COMPORTAMENTO, reproduzidos em 02/09/2026 com **33 perfis** no
disco (o número dela) e dublê de ponte — nada foi ao daemon.

1. **O Remover anunciava um alvo e apagava outro.** O armamento sempre foi por
   perfil (``remover`` exige ``_ARMADO[0] == nome``), mas o RÓTULO olhava só o
   relógio. Medido, sem ninguém valendo:

       clique em Remover (Pragmata escolhido) -> rótulo: Remover “Pragmata”?
       ela clica na linha do Sackboy          -> rótulo: Remover “Pragmata”?
       clique em Remover                      -> arma o SACKBOY, calado
       clique em Remover                      -> some do disco: ["Sackboy"]

   Três cliques num botão que nunca deixou de dizer "Pragmata" apagam o
   Sackboy, e a recusa que armaria o segundo sai em ``stderr``
   (``hefesto_vivo.py``), onde ela não está olhando.

2. **O marcador ÓRFÃO virava nome na tela.** ``resolve_boot_profile`` declara na
   própria docstring que *"só resolve NOMES — não valida se o perfil carrega"*,
   e o que ele devolvia ia cru para o chip "Perfil ativo" e para o alvo dos
   gestos. Com o marcador em "Perfil Que Ela Apagou": o chip nomeava um perfil
   sem linha entre as 33 e sem arquivo no disco.

3. **Duas comparações para a mesma pergunta, na mesma tela.** O realce da lista
   é ``p.name == ativo`` (``perfis_web._linhas_da_lista``) e as guardas dos
   gestos são ``mesmo_slug`` (R-10). Com o marcador em ``sackboy`` e o perfil
   chamado ``Sackboy``: nenhuma das 33 linhas se acendia **e** o Ativar recusava
   dizendo que ele já valia.

A CURA DOS TRÊS ÚLTIMOS É UMA SÓ e tem UM dono: ``a10_perfis._valendo`` resolve
o nome contra os perfis do disco (``find_by_slug``) antes de entregá-lo a
qualquer um. O que sai de lá já É o ``p.name`` de uma linha — o ``==`` não pode
mais discordar do ``mesmo_slug``.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import loader

#: A MESA — endereço MASCARADO (octetos 4 e 5 zerados). Nenhum endereço real de
#: rádio entra em arquivo versionado.
MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1, "cor": "cosmic-red",
     "nome": "Cosmic Red", "via": "USB", "transporte": "usb", "alvo": True,
     "mascara": "DualSense"},
]


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
    """``_ESCOLHIDO`` e ``_ARMADO`` são estado de MÓDULO. O segundo decide se o
    clique APAGA — herdá-lo de outro teste seria pior que não ter prova."""
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO", None, raising=False)
    monkeypatch.setattr(a10_perfis, "_PINTADO_PARA", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ULTIMO_TIQUE", 0.0, raising=False)


def _perfis(*nomes: str) -> list[Any]:
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    return [Profile(name=n, match=MatchAny(), priority=100 - i)
            for i, n in enumerate(nomes)]


def _o_disco_tem(monkeypatch: pytest.MonkeyPatch, *nomes: str) -> list[Any]:
    """A pasta de perfis, sem escrever no disco.

    SEM ISTO A PASTA É VAZIA, e isso não é detalhe: a ``conftest.py:2114`` põe
    ``HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1`` em TODO teste, então
    ``load_all_profiles()`` devolve ``[]`` na suíte inteira. Uma régua desta aba
    que não semeie mede o ramo da lista vazia.
    """
    todos = _perfis(*nomes)
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: todos)
    return todos


def _o_marcador_diz(monkeypatch: pytest.MonkeyPatch, nome: str | None) -> None:
    """O marcador em disco, pela costura que ``perfil_que_esta_valendo`` usa
    quando o daemon cala (``profiles_actions:601``)."""
    from hefesto_dualsense4unix.app.actions import profiles_actions

    monkeypatch.setattr(profiles_actions, "perfil_que_ela_ativou", lambda: nome)


def _ctx() -> Contexto:
    """O daemon CALADO — ``active_profile: null`` é o estado da máquina dela."""
    return Contexto(state={"active_profile": None}, mesa=list(MESA),
                    conectados=list(MESA), estados={})


def _realcadas(fora: dict[str, Any]) -> list[str]:
    html = (fora.get("blocos") or {}).get(a10_perfis.SELETOR_DA_LISTA, "")
    return [x.split('data-hef-perfil="')[1].split('"')[0]
            for x in html.splitlines() if 'class="ativo"' in x]


# --------------------------------------------------------------------------
# 1. O RÓTULO DO REMOVER NOMEIA O ALVO DE AGORA
# --------------------------------------------------------------------------
def test_o_rotulo_para_de_perguntar_quando_ela_troca_de_linha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Armado o Pragmata, ela clica no Sackboy: o botão volta a dizer "Remover".

    É a verdade do estado — o próximo clique naquele botão ARMA o Sackboy, não
    apaga o Pragmata. Deixá-lo perguntando pelo Pragmata é o botão anunciar um
    alvo e agir sobre outro, com a recusa intermediária indo para o ``stderr``.

    MORDIDA: tire o ``_ARMADO[0] == alvo`` de ``_rotulo_do_remover`` (que é como
    ele era até 02/09) e este teste reprova mostrando a pergunta pelo Pragmata.
    """
    _o_disco_tem(monkeypatch, "Pragmata", "Sackboy")
    _o_marcador_diz(monkeypatch, None)
    ctx, ponte = _ctx(), PonteDeMentira()

    a10_perfis.pacote(ctx)
    a10_perfis.selecionar(ctx, {"texto": "Pragmata"}, ponte)
    with pytest.raises(RuntimeError, match="Apagar “Pragmata”"):
        a10_perfis.remover(ctx, {}, ponte)
    assert a10_perfis.pacote(ctx)["perfis.remover"] == (
        "Remover “Pragmata”? Clique de novo"), "a pergunta não chegou ao rótulo"

    a10_perfis.selecionar(ctx, {"texto": "Sackboy"}, ponte)
    assert a10_perfis.pacote(ctx)["perfis.remover"] == "Remover", (
        "o botão continua perguntando pelo perfil ARMADO enquanto o alvo já é "
        "outro — anuncia um e age sobre o outro")


def test_o_segundo_clique_so_apaga_o_perfil_que_o_rotulo_nomeou(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A guarda de comportamento por trás do rótulo: trocar de linha DESARMA.

    O armamento já era por perfil; esta régua existe para que a cura do rótulo
    não seja "afrouxar o remover" no dia em que alguém quiser simplificar.
    """
    _o_disco_tem(monkeypatch, "Pragmata", "Sackboy")
    _o_marcador_diz(monkeypatch, None)
    apagados: list[str] = []
    monkeypatch.setattr(loader, "delete_profile", lambda n: apagados.append(n))
    ctx, ponte = _ctx(), PonteDeMentira()

    a10_perfis.selecionar(ctx, {"texto": "Pragmata"}, ponte)
    with pytest.raises(RuntimeError):
        a10_perfis.remover(ctx, {}, ponte)
    a10_perfis.selecionar(ctx, {"texto": "Sackboy"}, ponte)
    with pytest.raises(RuntimeError, match="Apagar “Sackboy”"):
        a10_perfis.remover(ctx, {}, ponte)
    assert apagados == [], "o clique na outra linha aproveitou a confirmação"

    a10_perfis.remover(ctx, {}, ponte)
    assert apagados == ["Sackboy"]


# --------------------------------------------------------------------------
# 2. O MARCADOR ÓRFÃO
# --------------------------------------------------------------------------
def test_o_marcador_orfao_nao_vira_nome_no_chip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Perfil renomeado ou apagado por fora: o chip volta ao travessão.

    Antes, o chip do topo nomeava um perfil que não tem linha entre as 33 nem
    arquivo no disco — e ela iria procurá-lo na lista. É o defeito que esta casa
    nomeou em 31/08 ("nomear um controle que não está"), do outro lado da tela.

    MORDIDA: tire o ``find_by_slug`` de ``_valendo`` e este teste reprova com o
    nome fantasma no chip.
    """
    _o_disco_tem(monkeypatch, "Pragmata", "Sackboy")
    _o_marcador_diz(monkeypatch, "Perfil Que Ela Apagou")
    fora = a10_perfis.pacote(_ctx())
    assert fora["ativo"] == "—"
    assert _realcadas(fora) == []


def test_o_marcador_orfao_nao_vira_alvo_de_gesto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A outra metade, e é a que a tentativa anterior deixou aberta: a TELA
    parou de nomear o perfil inexistente e o GESTO continuava mirando nele.

    Sem esta régua, "Voltar à de ontem" e "Remover" agiriam sobre um nome que
    não está na lista — e a frase de erro falaria de um perfil que ela não vê.
    """
    _o_disco_tem(monkeypatch, "Pragmata", "Sackboy")
    _o_marcador_diz(monkeypatch, "Perfil Que Ela Apagou")
    ctx = _ctx()
    with pytest.raises(ValueError, match="escolha um perfil na lista primeiro"):
        a10_perfis._perfil_do_editor(ctx)
    with pytest.raises(ValueError, match="escolha um perfil na lista primeiro"):
        a10_perfis.voltar_a_de_ontem(ctx, {}, PonteDeMentira())


def test_o_marcador_que_existe_continua_valendo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O contrapeso: derrubar o órfão não pode derrubar o marcador BOM.

    Sem esta régua, ``_valendo`` devolvendo ``""`` sempre passaria nas duas de
    cima — e o realce, o chip e as três guardas do §P1 morreriam calados.
    """
    _o_disco_tem(monkeypatch, "Pragmata", "Sackboy")
    _o_marcador_diz(monkeypatch, "Sackboy")
    fora = a10_perfis.pacote(_ctx())
    assert fora["ativo"] == "Sackboy"
    assert _realcadas(fora) == ["Sackboy"]


# --------------------------------------------------------------------------
# 3. UM DONO SÓ: o realce e as guardas param de discordar
# --------------------------------------------------------------------------
@pytest.mark.parametrize("marcador", ["Sackboy", "sackboy", "SACKBOY"])
def test_o_realce_e_a_guarda_do_ativar_dao_o_mesmo_veredito(
    monkeypatch: pytest.MonkeyPatch, marcador: str,
) -> None:
    """O marcador em disco pode guardar ``sackboy`` e a lista mostrar
    ``Sackboy`` — é o caso que ``find_by_slug`` existe para cobrir, e a docstring
    dele cita "Navegação"/"Navegacao".

    ANTES: com ``sackboy``, a lista de 33 não realçava ninguém **e** o Ativar
    recusava dizendo que o Sackboy já valia. Duas guardas, dois vereditos, uma
    tela.

    MORDIDA: devolva o nome CRU em ``_valendo`` (sem ``find_by_slug``) e as duas
    variações de caixa reprovam aqui — o realce sai vazio enquanto o Ativar
    continua recusando.
    """
    _o_disco_tem(monkeypatch, "Pragmata", "Sackboy")
    _o_marcador_diz(monkeypatch, marcador)
    ctx, ponte = _ctx(), PonteDeMentira()

    fora = a10_perfis.pacote(ctx)
    assert _realcadas(fora) == ["Sackboy"], (
        f"marcador {marcador!r}: a lista não acendeu a linha do perfil que vale")
    assert fora["ativo"] == "Sackboy", "o chip mostra o nome DIGITADO, não o da lista"

    a10_perfis.selecionar(ctx, {"texto": "Sackboy"}, ponte)
    with pytest.raises(ValueError, match="já é o perfil que está valendo"):
        a10_perfis.ativar(ctx, {}, ponte)
    assert ponte.chamadas == []


def test_lista_vazia_nao_desarma_a_guarda_do_perfil_que_vale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lista vazia é AUSÊNCIA DE PROVA, não prova de órfão.

    Se ``_valendo`` rebaixasse o nome a ``""`` sempre que não achasse par, uma
    pasta ilegível — ou a suíte inteira, onde a ``conftest`` desliga a semeadura
    e ``load_all_profiles()`` devolve ``[]`` — desligaria o §P7: o Remover
    voltaria a apagar o perfil que está valendo.

    MORDIDA: tire o ``if not todos: return nome`` e este teste reprova com o
    Remover ARMANDO em vez de recusar.
    """
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: [])
    _o_marcador_diz(monkeypatch, "meu_perfil")
    a10_perfis._ESCOLHIDO = "meu_perfil"
    with pytest.raises(ValueError, match="está valendo agora"):
        a10_perfis.remover(_ctx(), {}, PonteDeMentira())


# --------------------------------------------------------------------------
# 4. OS TRÊS SÍTIOS DE `_valendo` QUE SÓ TINHAM RÉGUA DE TEXTO
# --------------------------------------------------------------------------
# ACHADO DE AUDITORIA, 02/09/2026: `test_a_aba_nao_le_mais_o_active_profile_cru`
# procura a SUBSTRING `ctx.state.get("active_profile")` no fonte. Ela mede
# TEXTO, e cede a uma mudança de grafia — a auditoria reverteu quatro dos cinco
# sítios escrevendo a leitura por concatenação e 1080 testes ficaram verdes.
# Só `ativar` e `remover` tinham régua de ATO. As três de baixo cobrem o resto:
# `_perfil_do_editor` e os DOIS sítios de `voltar_a_de_ontem`.
def test_o_editor_abre_no_perfil_que_o_disco_diz_estar_valendo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Daemon calado, marcador no disco, nenhuma linha clicada.

    MORDIDA: troque o ``_valendo(ctx)`` de ``_perfil_do_editor`` pela leitura
    crua do ``state`` e este teste reprova — o alvo dos oito gestos que agem
    sobre o perfil aberto some, e a aba passa a recusar tudo com "escolha um
    perfil na lista primeiro".
    """
    _o_disco_tem(monkeypatch, "Pragmata", "Sackboy")
    _o_marcador_diz(monkeypatch, "Sackboy")
    assert a10_perfis._perfil_do_editor(_ctx()) == "Sackboy"


def test_voltar_a_de_ontem_acha_o_perfil_e_manda_reaplicar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Os DOIS sítios de ``_valendo`` deste gesto, no mesmo clique.

    O primeiro escolhe o perfil (sem ele o gesto recusa por falta de alvo); o
    segundo decide se o daemon precisa reaplicar — e sem essa reaplicação o
    arquivo volta ao que era com o controle no que estava, que é o sintoma que
    ela leu como "não está salvando".

    MORDIDA: troque qualquer um dos dois pela leitura crua do ``state`` e este
    teste reprova — o primeiro com ``ValueError``, o segundo sem o
    ``profile_switch`` na ponte.
    """
    restaurados: list[str] = []
    _o_disco_tem(monkeypatch, "Pragmata", "Sackboy")
    _o_marcador_diz(monkeypatch, "Sackboy")
    monkeypatch.setattr(loader, "restaurar_do_historico",
                        lambda n: restaurados.append(n))
    ponte = PonteDeMentira()
    a10_perfis.voltar_a_de_ontem(_ctx(), {}, ponte)
    assert restaurados == ["Sackboy"]
    assert ("profile_switch", ("Sackboy",)) in ponte.chamadas, (
        "o perfil restaurado é o que está valendo e o daemon não foi avisado")
    assert ("launch_env.refresh", ()) in ponte.chamadas


# --------------------------------------------------------------------------
# 5. O "ESTILO DE JOGO" ABRE NO TRAVESSÃO — decisão dela, 02/09/2026
# --------------------------------------------------------------------------
def test_o_pacote_nao_escreve_no_estilo_de_jogo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O perfil não tem campo de Estilo, então a tela não afirma nenhum.

    E não basta mandar vazio: o ``escrever()`` do piloto troca vazio por ``'—'``
    ANTES do ramo ``valor``, e num ``<select>`` cuja opção vazia tem
    ``value=""`` isso deixa ``selectedIndex = -1`` — o campo renderiza em branco
    e o contador de pinturas soma +1 a cada visita. Quem diz o ``—`` é o
    desenho; o pacote só precisa não estragá-lo.

    MORDIDA: tire ``editor.estilo`` de ``NAO_PINTAVEIS`` e este teste reprova.
    """
    _o_disco_tem(monkeypatch, "Pragmata")
    _o_marcador_diz(monkeypatch, "Pragmata")
    fora = a10_perfis.pacote(_ctx())
    assert "editor.estilo" not in fora
    assert "editor.estilo" in a10_perfis.NAO_PINTAVEIS


def test_a_bancada_abre_o_estilo_de_jogo_no_travessao() -> None:
    """A primeira opção do ``<select>``: ``value=""``, texto ``—``, marcada.

    Palavra dela em 02/09/2026. Antes, o desenho trazia
    ``<option selected>Luta</option>`` e por isso os **33 perfis** dela
    apareciam como "Luta" — um valor que ninguém escreveu.

    A BANCADA, e não a página publicada: publicar é ato dela, e a divergência
    está declarada em ``mockup/DIVERGENCIAS.md``.

    MORDIDA: rode ``aba10.py`` com ``opts(ESTILOS, "Luta")`` de volta e este
    teste reprova nas duas asserções.
    """
    html = onde.pagina("10-perfis.html").read_text(encoding="utf-8")
    trecho = html.split('data-hef="editor.estilo"', 1)[1].split("</select>", 1)[0]
    opcoes = [x.strip() for x in trecho.splitlines() if "<option" in x]
    assert opcoes[0] == '<option value="" selected>—</option>', (
        f"a primeira opção do Estilo de Jogo é {opcoes[0]!r}")
    assert not [o for o in opcoes[1:] if "selected" in o], (
        "outra opção nasce marcada — o campo voltaria a afirmar um estilo")
