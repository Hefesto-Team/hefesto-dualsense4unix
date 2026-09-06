"""O quadro "Modo" da aba Perfis GRAVA — PERFIL-MODO-01, Passo 1 (06/09/2026).

Era a linha 384 do CSV da paridade, com o veredito mais duro da aba:

    `FALTA_NO_HTML` · *"NÃO EXISTE — nem na página, nem no pacote. Grep de
    `ProfileModeConfig`, `with_mode`, `mode_kind` em `interface/` dá zero"*

E a consequência, medida por quem escreveu a linha: *"um perfil criado ou
editado pelo HTML não pode dizer «quando eu entrar, ligue o modo jogo» — o campo
simplesmente não é alcançável, e o valor do disco sobrevive só por herança
(ninguém escreve nele)"*.

O QUE ESTA RÉGUA MEDE
---------------------
O PYTHON: que os quatro modos gravam o que prometem no `.json`, que "Não mexer
no modo" REMOVE a seção (e não grava um `kind` de mentira), e que a máscara do
disco atravessa a troca — a cicatriz de ESCOLHA-DELA-VENCE-01/E1, em que um
`or "xbox"` fazia salvar um perfil passar a EXIGIR Xbox.

NÃO MEDE o clique chegando. Quem prova isso é
`scripts/ensaios/o_quadro_do_modo_grava_pelo_webkit.py`, que abre a página da
BANCADA no `WebKit2.WebView`, clica os quatro botões como o navegador clica e lê
o `.json` do outro lado — porque um botão que o ouvinte do piloto não alcançasse
daria verde em toda régua de Python e silêncio na tela.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import perfis_web
from hefesto_dualsense4unix.app.actions.profiles_actions import _MODE_KIND_ITEMS
from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    Profile,
    ProfileModeConfig,
)

PAGINA = "10-perfis.html"  # (noqa-acento) nome de arquivo

#: A MESA — endereços MASCARADOS (octetos 4 e 5 zerados), a máscara da casa.
MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1, "cor": "cosmic-red",
     "nome": "Cosmic Red", "via": "USB", "transporte": "usb", "alvo": True},
]


class PonteDeMentira:
    """Anota, e não fala com o daemon dela. Sabe RECUSAR (ver `falha`)."""

    def __init__(self, falha: bool = False) -> None:
        self.chamadas: list[str] = []
        self.falha = falha

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append(f"profile_switch:{nome}")
        return not self.falha

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
        self.chamadas.append(f"chamar:{metodo}")
        return not self.falha

    def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
        self.chamadas.append(f"resultado:{metodo}")
        if self.falha:
            raise RuntimeError("o dublê recusou")
        return {}


@pytest.fixture(autouse=True)
def _memoria_limpa(monkeypatch: pytest.MonkeyPatch) -> None:
    """Estado de MÓDULO herdado de outro teste não é prova de nada."""
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_PINTADO_PARA", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ULTIMO_TIQUE", 0.0, raising=False)
    monkeypatch.setattr(a10_perfis, "_DESFECHO", None, raising=False)
    monkeypatch.setattr(a10_perfis, "_CARONA_PENDENTE", "", raising=False)


@pytest.fixture
def disco(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Um perfil na "pasta". O que o gesto gravar fica AQUI, não em `~/.config`."""
    guardado: dict[str, Any] = {
        "perfil": Profile(name="Pragmata", match=MatchAny(), priority=40),
        "salvos": [],
    }

    def _load_all(*a: Any, **kw: Any) -> list[Profile]:
        return [guardado["perfil"]]

    def _load(nome: str, *a: Any, **kw: Any) -> Profile:
        if nome != guardado["perfil"].name:
            raise FileNotFoundError(nome)
        return guardado["perfil"].model_copy(deep=True)

    def _save(prof: Profile, *a: Any, **kw: Any) -> None:
        guardado["perfil"] = prof
        guardado["salvos"].append(prof)

    monkeypatch.setattr(loader, "load_all_profiles", _load_all)
    monkeypatch.setattr(loader, "load_profile", _load)
    monkeypatch.setattr(loader, "save_profile", _save)
    a10_perfis._ESCOLHIDO = "Pragmata"
    return guardado


def _ctx() -> Contexto:
    return Contexto(state={"active_profile": None}, mesa=list(MESA),
                    conectados=list(MESA), estados={})


# --------------------------------------------------------------------------
# 1. OS QUATRO RÓTULOS SÃO DELA, E SAEM DO DONO
# --------------------------------------------------------------------------

def test_os_quatro_rotulos_vem_do_dono_e_nao_estao_digitados() -> None:
    """`_MODE_KIND_ITEMS` é a fonte, nos TRÊS lugares desta entrega.

    MORDIDA: troque uma palavra em `perfis_web.MODO_DO_PERFIL` e isto reprova —
    porque o dicionário PASSOU a ser digitado em vez de derivado.
    """
    assert dict(_MODE_KIND_ITEMS) == perfis_web.MODO_DO_PERFIL, (
        "os rótulos do Modo deixaram de sair de "
        "`profiles_actions._MODE_KIND_ITEMS` — a quinta superfície com as "
        "palavras dela digitadas é a quinta a envelhecer sozinha")
    primeiro = next(iter(perfis_web.MODO_DO_PERFIL))
    assert primeiro == perfis_web.MODO_SEM_OPINIAO, (
        "«Não mexer no modo» deixou de ser o primeiro — é o que a MAIORIA dos "
        "perfis é, e a ordem é a do dono")


def test_o_desenho_mostra_os_quatro_com_a_palavra_do_dono() -> None:
    """E a BANCADA carrega os quatro `data-hef-quando`, um por id.

    MORDIDA: apague um `<button>` de `aba10.botoes_do_modo` e isto reprova
    nomeando o id que sumiu.
    """
    html = onde.pagina(PAGINA, publicado=False).read_text(encoding="utf-8")
    for ident, rotulo in _MODE_KIND_ITEMS:
        assert f'data-hef-quando="{ident}"' in html, (
            f"o botão do modo `{ident}` não está na bancada — os quatro são "
            f"dela, e o conjunto é fechado")
        assert f">{rotulo}</button>" in html, (
            f"o botão `{ident}` não diz {rotulo!r} — o desenho passou a "
            f"digitar a palavra dela em vez de perguntá-la ao dono")


# --------------------------------------------------------------------------
# 2. OS QUATRO GRAVAM — e o "none" REMOVE a seção
# --------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["desktop", "gamepad", "native"])
def test_cada_modo_grava_o_kind_no_perfil(disco: dict[str, Any], kind: str) -> None:
    """MORDIDA: troque `prof.mode = ProfileModeConfig(**campos)` por `pass` em
    `a10_perfis.editor_modo` e os três casos reprovam — o gesto responde
    "aplicado" e o `.json` continua sem a seção."""
    p = PonteDeMentira()
    resposta = a10_perfis.editor_modo(_ctx(), {"modo": kind}, p)
    gravado = disco["perfil"]
    assert gravado.mode is not None, (
        f"o modo `{kind}` não gravou a seção `mode` — o perfil continua sem "
        f"dizer o que ativar ele liga")
    assert gravado.mode.kind == kind
    assert resposta is not None and "perfis.desfecho" in resposta["mesa"]
    assert resposta["mesa"]["editor.modo"] == kind, (
        "o gesto não devolve o modo novo para a tela na hora — ela vê o botão "
        "antigo aceso por até meio segundo depois do clique")


def test_o_nao_mexer_no_modo_remove_a_secao(disco: dict[str, Any]) -> None:
    """"none" → `mode = None`, como `_mode_section_from_editor` já fazia.

    MORDIDA: troque o `prof.mode = None` por `ProfileModeConfig(kind="desktop")`
    e isto reprova — o perfil passaria a MEXER no modo justamente na opção que
    promete não mexer.
    """
    disco["perfil"] = disco["perfil"].model_copy(
        update={"mode": ProfileModeConfig(kind="gamepad")})
    a10_perfis.editor_modo(_ctx(), {"modo": "none"}, PonteDeMentira())
    assert disco["perfil"].mode is None, (
        "«Não mexer no modo» deixou uma seção `mode` no perfil — o rótulo "
        "promete que ativar não mexe, e o arquivo diria o contrário")


def test_a_mascara_nunca_e_inventada_pelo_gesto(disco: dict[str, Any]) -> None:
    """ESCOLHA-DELA-VENCE-01/E1, pelo avesso: nada de `or "xbox"`.

    A cicatriz é da janela estável: havia um `or "xbox"` no Salvar, e **bastava
    salvar um perfil para ele passar a EXIGIR Xbox**. Este quadro não tem a
    linha da máscara, então ele nunca escolhe uma — e a única coisa que faz com
    o campo é ZERÁ-LO fora do modo jogo, que é o que
    `_mode_section_from_editor` já faz (*"JSON limpo, sem sobras"*) e o que
    `manager.alinhar_o_modo_com_a_ponte` aplica pela mesma regra.

    MORDIDA (colhida em 06/09/2026): troque
    `campos["gamepad_flavor"] = None` por `campos["gamepad_flavor"] = "xbox"`
    e a primeira asserção reprova; troque o `if kind != "gamepad"` por
    `if False` e a segunda reprova, com o `dualsense` sobrando num perfil que
    já não usa o gamepad virtual.
    """
    disco["perfil"] = disco["perfil"].model_copy(update={
        "mode": ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense")})
    a10_perfis.editor_modo(_ctx(), {"modo": "native"}, PonteDeMentira())
    guardado = disco["perfil"]
    assert guardado.mode is not None and guardado.mode.kind == "native"
    assert guardado.mode.gamepad_flavor is None, (
        "o `gamepad_flavor` sobreviveu fora do modo jogo — é sobra no `.json`, "
        "e é justamente a sobra que fez a janela estável exigir Xbox")

    # E do zero: um perfil SEM seção nenhuma que vira gamepad não pode nascer
    # com máscara. `None` quer dizer «mantém a atual», que é o que estava lá.
    disco["perfil"] = Profile(name="Pragmata", match=MatchAny(), priority=40)
    a10_perfis.editor_modo(_ctx(), {"modo": "gamepad"}, PonteDeMentira())
    assert disco["perfil"].mode is not None
    assert disco["perfil"].mode.kind == "gamepad"
    assert disco["perfil"].mode.gamepad_flavor is None, (
        "o gesto inventou uma máscara — `None` é «mantém a atual», e é o que a "
        "janela estável grava quando não há botão marcado")


# --------------------------------------------------------------------------
# 3. O GESTO SABE RECUSAR — régua que só sabe passar não é régua
# --------------------------------------------------------------------------

def test_o_modo_desconhecido_e_recusado_dizendo(disco: dict[str, Any]) -> None:
    """Um `data-modo` que o esquema não conhece não pode virar arquivo.

    É a mesma disciplina de `editor_ambiente` com "Estilo de Jogo": cair fora da
    tabela do dono é o que faz o gesto RECUSAR em vez de gravar calado.
    """
    with pytest.raises(RuntimeError, match="não é um modo"):
        a10_perfis.editor_modo(_ctx(), {"modo": "turbo"}, PonteDeMentira())
    assert not disco["salvos"], "recusou e gravou assim mesmo"


def test_reclicar_o_modo_que_ja_vale_recusa_dizendo(disco: dict[str, Any]) -> None:
    """A guarda do `ativar`, aplicada aqui: não se diz "aplicado" sobre nada.

    MORDIDA: apague o `if getattr(atual, "kind", None) == kind` e isto reprova —
    o gesto passaria a gravar o MESMO arquivo e a anunciar mudança.
    """
    disco["perfil"] = disco["perfil"].model_copy(
        update={"mode": ProfileModeConfig(kind="desktop")})
    with pytest.raises(RuntimeError, match="já liga"):
        a10_perfis.editor_modo(_ctx(), {"modo": "desktop"}, PonteDeMentira())
    assert not disco["salvos"]


def test_sem_perfil_escolhido_o_gesto_recusa(disco: dict[str, Any]) -> None:
    """Sem alvo não há o que gravar — e o gesto diz o que fazer."""
    a10_perfis._ESCOLHIDO = ""
    ctx = Contexto(state={}, mesa=list(MESA), conectados=list(MESA))
    with pytest.raises(RuntimeError, match="escolha um perfil"):
        a10_perfis.editor_modo(ctx, {"modo": "gamepad"}, PonteDeMentira())


# --------------------------------------------------------------------------
# 4. O VALOR CHEGA À TELA COMO **ID**, e é o que acende o botão certo
# --------------------------------------------------------------------------

def test_o_pacote_manda_o_id_do_modo_e_nao_o_rotulo(disco: dict[str, Any]) -> None:
    """O alvo `classe` compara com `data-hef-quando`, que é o ID.

    MORDIDA: troque `"modo": ...kind` por `MODO_DO_PERFIL[kind]` em
    `perfis_web._pacote_do_editor` e isto reprova — a tela compararia a palavra
    dela com um id, e nenhum dos quatro botões acenderia nunca.
    """
    disco["perfil"] = disco["perfil"].model_copy(
        update={"mode": ProfileModeConfig(kind="gamepad")})
    editor = perfis_web._pacote_do_editor(disco["perfil"])
    assert editor["modo"] == "gamepad"
    sem_secao = Profile(name="x", match=MatchAny())
    assert perfis_web._pacote_do_editor(sem_secao)["modo"] == "none", (
        "perfil SEM a seção `mode` deixou de sair como «Não mexer no modo» — "
        "a tela passaria a não acender nenhum dos quatro no caso mais comum")
