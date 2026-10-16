"""O editor da aba Perfis só grava no perfil que mostra — 09/10/2026.

Com o Modo Freestyle ligado, o perfil que vale é o Freestyle, e ele não está na lista
de escolher (decisão de 02/10: a tela dele é o botão). Quem PINTA o editor lia a lista
de escolher e abria no primeiro dela; quem GRAVA lia a lista inteira e mirava o
Freestyle. Medido antes da cura, com «Freestyle» e «Corrida» no disco:

    pacote(ctx)["editor.nome"]        -> "Corrida"
    editor_nome(valor="Corrida 2")    -> "Perfil renomeado: Freestyle → Corrida 2",
                                         e o freestyle.json some do disco

Desde 15/10 o `pacote()` não manda mais o `editor.nome` (a tela nova não tem o campo Nome): o perfil
que o editor mostra é a linha MARCADA da lista (`aria-selected`), e a régua lê dali.

A régua junta o que nenhuma outra juntava: `freestyle_ligado` com os gestos do
editor. Para cada gesto, o perfil que ele LÊ do disco é o que o `pacote()` pinta, e o
`freestyle.json` sai byte a byte igual.

MORDIDA: volte `_perfil_do_editor` para `_ESCOLHIDO or _valendo(ctx)` e o renomear
apaga o `freestyle.json`.
"""
from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import estilos_de_jogo, loader
from hefesto_dualsense4unix.profiles.schema import MatchAny, MatchCriteria, Profile
from hefesto_dualsense4unix.utils import session

FREESTYLE = loader.NOME_DO_PADRAO
CORRIDA = "Corrida"
AVATAR = "Avatar Legends"


class PonteDeMentira:
    """O daemon calado que confirma: nada do aparelho entra na régua."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append(f"profile_switch:{nome}")
        return True

    def profile_reaplicar(self, nome: str, *, prender: bool = False) -> bool:
        self.chamadas.append(f"profile_reaplicar:{nome}")
        return True

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
        self.chamadas.append(f"chamar:{metodo}")
        return True

    def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
        self.chamadas.append(f"resultado:{metodo}")
        return {}


@pytest.fixture(autouse=True)
def _memoria_limpa(monkeypatch: pytest.MonkeyPatch) -> None:
    """Estado de MÓDULO herdado de outro teste não é prova de nada."""
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO", None, raising=False)
    monkeypatch.setattr(a10_perfis, "_PROCURA", "", raising=False)
    # o «pinta uma vez» (`_uma_vez_so`) omite os campos digitados do mesmo alvo por 2 s
    monkeypatch.setattr(a10_perfis, "_PINTADO_PARA", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ULTIMO_TIQUE", 0.0, raising=False)


def _o_disco(*, so_o_freestyle: bool = False) -> Path:
    """O Freestyle e a Corrida; a Corrida gravada duas vezes, diferente, e há «ontem».

    A gravação byte a byte igual não arquiva a anterior (`save_profile`), então a
    primeira da Corrida tem outra prioridade.
    """
    loader.save_profile(Profile(name=FREESTYLE, match=MatchAny()), origem="régua")
    if not so_o_freestyle:
        for prioridade in (59, 60):
            loader.save_profile(
                Profile(name=CORRIDA, match=MatchCriteria(window_class=["corrida"]),
                        priority=prioridade), origem="régua")
    session.save_freestyle_ligado(True)
    return loader.profiles_dir() / f"{loader.SLUG_DO_PADRAO}.json"


def _ctx() -> Contexto:
    state = {"active_profile": FREESTYLE, "freestyle_ligado": True,
             "window_detect_last_class": "corrida_jogo"}
    return Contexto(state=state, mesa=[], conectados=[], estados={})


def _estilo_que_grava() -> str:
    return next(e.rotulo for e in estilos_de_jogo.ESTILOS if e.chave not in estilos_de_jogo.SEM_COR)


def _aberto_no_editor() -> str:
    """O perfil que o editor mostra: a linha marcada da lista que o `pacote()` pinta."""
    html = a10_perfis.pacote(_ctx())["blocos"].get(a10_perfis.SELETOR_DA_LISTA, "")
    marcadas = [x.split('data-hef-perfil="')[1].split('"')[0]
                for x in html.splitlines() if 'aria-selected="true"' in x]
    assert len(marcadas) == 1, f"o editor deve abrir numa linha só: {marcadas!r}"
    return marcadas[0]


#: Os gestos do editor e o que cada um recebe da tela. O `remover` fica fora: a
#: guarda do perfil que vale o recusaria antes de gravar, e ele tem régua própria.
GESTOS: dict[str, tuple[Any, dict[str, Any]]] = {
    "editor.nome": (a10_perfis.editor_nome, {"valor": "Corrida 2"}),
    "editor.prioridade": (a10_perfis.editor_prioridade, {"valor": "77"}),
    "editor.ambiente": (a10_perfis.editor_ambiente, {"valor": "Instalado aqui"}),
    "editor.estilo": (a10_perfis.editor_estilo, {"valor": _estilo_que_grava()}),
    "editor.jogo": (a10_perfis.editor_jogo, {"valor": "corrida.exe"}),
    "detectar": (a10_perfis.detectar, {}),
    "duplicar": (a10_perfis.duplicar, {}),
    "voltar-a-de-ontem": (a10_perfis.voltar_a_de_ontem, {}),
}


@pytest.fixture
def alvos(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Os nomes que os gestos LEEM ou RESTAURAM no disco, na ordem em que leem."""
    lidos: list[str] = []
    ler, restaurar = loader.load_profile, loader.restaurar_do_historico

    def _ler(nome: str, *a: Any, **kw: Any) -> Any:
        lidos.append(nome)
        return ler(nome, *a, **kw)

    def _restaurar(nome: str, *a: Any, **kw: Any) -> Any:
        lidos.append(nome)
        return restaurar(nome, *a, **kw)

    monkeypatch.setattr(loader, "load_profile", _ler)
    monkeypatch.setattr(loader, "restaurar_do_historico", _restaurar)
    return lidos


@pytest.mark.parametrize("gesto", list(GESTOS))
def test_o_gesto_mira_o_perfil_que_o_editor_pinta(gesto: str, alvos: list[str]) -> None:
    """O alvo de cada gesto é o perfil que o editor mostra, e o Freestyle não muda."""
    arquivo = _o_disco()
    antes = arquivo.read_bytes()
    pintado = _aberto_no_editor()
    assert pintado == CORRIDA, f"o editor abriu em {pintado!r}, e a lista só tem a Corrida"

    funcao, o = GESTOS[gesto]
    alvos.clear()
    # a recusa por outro motivo vale, desde que o alvo seja o pintado
    with contextlib.suppress(RuntimeError):
        funcao(_ctx(), dict(o), PonteDeMentira())

    assert alvos, f"{gesto}: o gesto não leu perfil nenhum do disco"
    assert set(alvos) == {pintado}, (
        f"{gesto}: o editor mostra {pintado!r} e o gesto leu {alvos!r} do disco")
    assert arquivo.is_file(), f"{gesto}: o freestyle.json sumiu do disco"
    assert arquivo.read_bytes() == antes, f"{gesto}: o freestyle.json mudou"


def test_renomear_renomeia_a_corrida_e_o_freestyle_fica() -> None:
    """O caso medido: «Corrida 2» é a Corrida renomeada, e o Freestyle segue no disco."""
    arquivo = _o_disco()
    antes = arquivo.read_bytes()

    resposta = a10_perfis.editor_nome(_ctx(), {"valor": "Corrida 2"}, PonteDeMentira())

    nomes = {p.name for p in loader.load_all_profiles()}
    assert nomes == {FREESTYLE, "Corrida 2"}, f"o disco ficou com {sorted(nomes)}"
    assert arquivo.read_bytes() == antes
    assert resposta is not None
    assert FREESTYLE not in str(resposta), f"a frase fala do Freestyle: {resposta!r}"


def test_a_linha_clicada_continua_sendo_o_alvo(alvos: list[str]) -> None:
    """Com a linha escolhida, editor e gesto miram ela, e não o primeiro da lista."""
    _o_disco()
    loader.save_profile(Profile(name=AVATAR, match=MatchCriteria(window_class=["avatar"])),
                        origem="régua")
    a10_perfis.selecionar(_ctx(), {"hefPerfil": AVATAR}, PonteDeMentira())

    assert _aberto_no_editor() == AVATAR
    alvos.clear()
    a10_perfis.editor_prioridade(_ctx(), {"valor": "91"}, PonteDeMentira())
    assert alvos == [AVATAR]
    assert loader.load_profile(AVATAR).priority == 91


def test_so_o_freestyle_no_disco_e_recusa(alvos: list[str]) -> None:
    """Lista de escolher vazia: o editor não abre, e o gesto recusa sem tocar o Freestyle."""
    arquivo = _o_disco(so_o_freestyle=True)
    antes = arquivo.read_bytes()

    with pytest.raises(RuntimeError, match="escolha um perfil"):
        a10_perfis.editor_nome(_ctx(), {"valor": "Outro"}, PonteDeMentira())
    with pytest.raises(RuntimeError, match="escolha um perfil"):
        a10_perfis.voltar_a_de_ontem(_ctx(), {}, PonteDeMentira())

    assert alvos == []
    assert arquivo.read_bytes() == antes
