"""Os dois campos da aba Perfis que passaram a ESCREVER — 03/09/2026."""
from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions import trigger_specs
from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import estilos_de_jogo, loader
from hefesto_dualsense4unix.profiles.schema import (
    PRIORIDADE_MAXIMA,
    PRIORIDADE_MINIMA,
    MatchAny,
    Profile,
)

PAGINA = "10-perfis.html"

MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1, "cor": "cosmic-red",
     "nome": "Cosmic Red", "via": "USB", "transporte": "usb", "alvo": True},
    {"pref": "p2", "uniq": "aabbcc000002", "jogador": 2, "cor": "white",
     "nome": "White", "via": "BT", "transporte": "bt", "alvo": False},
]


class PonteDeMentira:
    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append(f"profile_switch:{nome}")
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
    monkeypatch.setattr(a10_perfis, "_ARMADO_REBAIXAR", None, raising=False)
    monkeypatch.setattr(a10_perfis, "_PINTADO_PARA", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ULTIMO_TIQUE", 0.0, raising=False)


@pytest.fixture
def disco(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Um perfil na "pasta", e o que o gesto GRAVAR fica aqui — não no disco."""
    guardado: dict[str, Any] = {
        "perfil": Profile(name="Pragmata", match=MatchAny(), priority=40),
        "salvos": [],
    }

    def _load_all(*a: Any, **kw: Any) -> list[Profile]:
        return [guardado["perfil"]]

    def _load(nome: str, *a: Any, **kw: Any) -> Profile:
        if nome != guardado["perfil"].name:
            raise FileNotFoundError(nome)
        return guardado["perfil"]

    def _save(prof: Profile, *a: Any, **kw: Any) -> None:
        guardado["perfil"] = prof
        guardado["salvos"].append(prof)

    monkeypatch.setattr(loader, "load_all_profiles", _load_all)
    monkeypatch.setattr(loader, "load_profile", _load)
    monkeypatch.setattr(loader, "save_profile", _save)
    a10_perfis._ESCOLHIDO = "Pragmata"
    return guardado


def _ctx(mesa: list[dict[str, Any]] | None = None) -> Contexto:
    tem = MESA if mesa is None else mesa
    return Contexto(state={"active_profile": None}, mesa=list(tem),
                    conectados=list(tem), estados={})


def _bancada() -> str:
    return onde.pagina(PAGINA, publicado=False).read_text(encoding="utf-8")


def test_a_prioridade_tem_gesto() -> None:
    """MORDIDA: tire o ``@gesto`` de ``editor_prioridade`` e isto reprova."""
    from hefesto_dualsense4unix.interface import pacotes

    assert pacotes.gesto_da_pagina(PAGINA, "editor.prioridade") is not None


def test_a_faixa_do_slider_e_a_do_esquema() -> None:
    """A régua PERGUNTA ao dono do teto, e não digita ``0..200``."""
    html = _bancada()
    assert f'min="{PRIORIDADE_MINIMA}"' in html and f'max="{PRIORIDADE_MAXIMA}"' in html, (
        "a faixa do `<input type=range>` da Prioridade não é a do esquema")
    assert '<input type="range" class="desliza"' in html, (
        "a Prioridade voltou a ser uma barra que não se arrasta")


def test_arrastar_grava_a_prioridade(disco: dict[str, Any]) -> None:
    """O caminho principal: o ``change`` do punho vira ``priority`` no perfil."""
    ponte = PonteDeMentira()
    resposta = a10_perfis.editor_prioridade(_ctx(), {"valor": "137"}, ponte)

    assert disco["perfil"].priority == 137, (
        f"o arrasto não chegou ao perfil: {disco['perfil'].priority}")
    assert len(disco["salvos"]) == 1
    assert resposta is not None
    mesa = resposta["mesa"]
    assert mesa["editor.prioridade.n"] == "137"
    esperada = str(round(137 * 100 / PRIORIDADE_MAXIMA))
    assert mesa["editor.prioridade"] == esperada, (
        f"a largura saiu {mesa['editor.prioridade']!r} e devia ser {esperada!r}, "
        f"sem `%` e sem travessão")


@pytest.mark.parametrize("valor", ["-1", str(PRIORIDADE_MAXIMA + 1), "9999"])
def test_fora_da_faixa_recusa_dizendo(disco: dict[str, Any], valor: str) -> None:
    """Um número fora da faixa iria direto para o ``.json`` dela.

    O ``<input>`` já traz ``min``/``max``, mas o clique pode chegar de qualquer
    lugar — inclusive de uma régua. ``RuntimeError`` porque é a única classe que
    ``_recusou_dizendo`` leva ao DOM.

    MORDIDA: tire a guarda de faixa do gesto e isto reprova.
    """
    with pytest.raises(RuntimeError, match="fora da faixa"):
        a10_perfis.editor_prioridade(_ctx(), {"valor": valor}, PonteDeMentira())
    assert not disco["salvos"], "gravou um número fora da faixa do esquema"


def test_o_que_nao_e_numero_recusa(disco: dict[str, Any]) -> None:
    """MORDIDA: tire o ``try/except ValueError`` e isto vira ``ValueError`` cru —"""
    with pytest.raises(RuntimeError, match="tem de ser um número"):
        a10_perfis.editor_prioridade(_ctx(), {"valor": "meio"}, PonteDeMentira())
    assert not disco["salvos"]


def test_o_clique_solto_nao_grava(disco: dict[str, Any]) -> None:
    """Um ``<input type=range>`` dispara ``click`` E ``change`` no mesmo toque."""
    assert a10_perfis.editor_prioridade(
        _ctx(), {"valor": "137", "evento": "click"}, PonteDeMentira()) is None
    assert not disco["salvos"], "um clique que não mudou nada gravou no disco"


def test_o_mesmo_numero_nao_regrava(disco: dict[str, Any]) -> None:
    """Regravar um perfil idêntico troca a data do arquivo e faz o daemon
    reaplicar — um ``profile.switch`` no meio de uma partida não é de graça."""
    assert a10_perfis.editor_prioridade(
        _ctx(), {"valor": "40"}, PonteDeMentira()) is None
    assert not disco["salvos"]


def test_o_punho_se_pinta_uma_vez_por_perfil() -> None:
    """``editor.prioridade.escolha`` tem de estar em ``CAMPOS_QUE_ELA_DIGITA``.

    A MEDIÇÃO: com ``data-hef-alvo="valor"`` a pintura faz ``el.value = t`` a
    cada 500 ms. Num ``<input type=range>``, isso devolve o punho ao número do
    disco NO MEIO do arrasto — o slider ficaria intocável, do mesmo jeito que os
    dois ``<input>`` de texto ficariam.

    E O NÚMERO AO LADO NÃO PODE ENTRAR: ele é leitura, e congelá-lo faria a
    legenda mostrar o valor velho depois de a gravação acontecer.

    MORDIDA: tire o nome de ``CAMPOS_QUE_ELA_DIGITA`` e isto reprova.
    """
    assert "editor.prioridade.escolha" in a10_perfis.CAMPOS_QUE_ELA_DIGITA
    assert "editor.prioridade.n" not in a10_perfis.CAMPOS_QUE_ELA_DIGITA


def test_o_select_oferece_o_que_o_motor_sabe_aplicar() -> None:
    """O CONJUNTO, e não uma contagem: uma receita nova não pode ficar fora."""
    html = _bancada()
    fora = [e.rotulo for e in estilos_de_jogo.ESTILOS
            if f">{e.rotulo}</option>" not in html]
    assert not fora, f"o motor conhece e o `<select>` não oferece: {fora}"


def test_o_estilo_grava_gatilho_vibracao_e_uma_cor_por_unidade(
    disco: dict[str, Any],
) -> None:
    """A entrega inteira num gesto: os três ajustes, e a cor POR UNIDADE."""
    ponte = PonteDeMentira()
    resposta = a10_perfis.editor_estilo(_ctx(), {"valor": "FPS"}, ponte)

    prof = disco["perfil"]
    receita = estilos_de_jogo.POR_ROTULO["FPS"]
    assert prof.triggers.left.mode == receita.gatilho
    assert prof.triggers.right.mode == receita.gatilho
    assert prof.rumble.policy == receita.vibracao
    assert set(prof.controllers or {}) == {c["uniq"] for c in MESA}
    assert prof.leds.lightbar == (0, 0, 0), (
        "o estilo escreveu uma cor na seção GLOBAL — é a cor que os quatro "
        "herdariam, e a regra dela é que nenhum controle repete a cor de outro")
    assert resposta is not None and "FPS" in resposta["relato"]
    assert resposta["mesa"]["perfis.desfecho"] == "", "a tira voltou a falar"


def test_nenhuma_unidade_recebe_a_cor_de_outra(disco: dict[str, Any]) -> None:
    """A LEI DE PRODUTO, medida no que foi GRAVADO — e não no motor."""
    for rotulo in [e.rotulo for e in estilos_de_jogo.ESTILOS
                   if e.chave != "personalizado"]:
        disco["perfil"] = Profile(name="Pragmata", match=MatchAny(), priority=40)
        a10_perfis.editor_estilo(_ctx(), {"valor": rotulo}, PonteDeMentira())
        cores = [tuple(o.leds.lightbar)
                 for o in (disco["perfil"].controllers or {}).values()]
        assert len(set(cores)) == len(cores), (
            f"“{rotulo}” deu a mesma cor a duas unidades: {cores}")


def test_o_gatilho_sai_do_dono_dos_parametros(disco: dict[str, Any]) -> None:
    """Os números do gatilho são PERGUNTADOS, nunca digitados."""
    sem_params = []
    for estilo in estilos_de_jogo.ESTILOS:
        if estilo.chave == "personalizado":
            continue
        disco["perfil"] = Profile(name="Pragmata", match=MatchAny(), priority=40)
        a10_perfis.editor_estilo(_ctx(), {"valor": estilo.rotulo},
                                 PonteDeMentira())
        spec = trigger_specs.get_spec(estilo.gatilho or "")
        assert spec is not None, f"{estilo.rotulo}: gatilho fora do produto"
        esperado = list(trigger_specs.preset_to_positional_params(spec, {}))
        for lado in ("left", "right"):
            tem = list(getattr(disco["perfil"].triggers, lado).params)
            assert tem == esperado, (
                f"{estilo.rotulo}/{lado}: params {tem} != {esperado} do dono")
        if spec.params and not esperado:  # pragma: no cover — defesa da régua
            sem_params.append(estilo.rotulo)
    assert not sem_params


def test_o_gatilho_gravado_e_construivel(disco: dict[str, Any]) -> None:
    """O que foi gravado tem de ABRIR no produto — senão o estrago é no `apply()`."""
    from hefesto_dualsense4unix.core.trigger_effects import build_from_name

    for estilo in estilos_de_jogo.ESTILOS:
        if estilo.chave == "personalizado":
            continue
        disco["perfil"] = Profile(name="Pragmata", match=MatchAny(), priority=40)
        a10_perfis.editor_estilo(_ctx(), {"valor": estilo.rotulo},
                                 PonteDeMentira())
        cfg = disco["perfil"].triggers.left
        efeito = build_from_name(cfg.mode, cfg.params)
        assert efeito is not None, f"{estilo.rotulo}: o gatilho não monta"


def test_personalizado_nao_mexe_em_nada(disco: dict[str, Any]) -> None:
    """"Personalizado" é o estilo que diz *"eu ajusto na mão"*."""
    era = disco["perfil"]
    resposta = a10_perfis.editor_estilo(
        _ctx(), {"valor": "Personalizado"}, PonteDeMentira())
    assert not disco["salvos"], "o `Personalizado` gravou alguma coisa"
    assert disco["perfil"] is era
    assert resposta is not None
    assert "não mexe em nada" in resposta["relato"]


def test_um_estilo_que_o_produto_nao_conhece_recusa(disco: dict[str, Any]) -> None:
    """MORDIDA: tire o ``if estilo is None`` e isto vira ``AttributeError``."""
    with pytest.raises(RuntimeError, match="não é um dos Estilos de Jogo"):
        a10_perfis.editor_estilo(_ctx(), {"valor": "Boliche"}, PonteDeMentira())
    assert not disco["salvos"]


def test_dois_controles_no_mesmo_lugar_recusam(disco: dict[str, Any]) -> None:
    """O único caminho pelo qual a lei de produto cairia com o motor inocente."""
    mesa = [dict(MESA[0]), {**MESA[1], "jogador": 1}]
    with pytest.raises(RuntimeError, match="MESMA cor"):
        a10_perfis.editor_estilo(_ctx(mesa), {"valor": "FPS"}, PonteDeMentira())
    assert not disco["salvos"]


def test_mesa_vazia_ainda_ajusta_gatilho_e_vibracao(disco: dict[str, Any]) -> None:
    """Sem controle na mesa, os dois que não dependem de peça entram do mesmo"""
    resposta = a10_perfis.editor_estilo(_ctx([]), {"valor": "Corrida"},
                                        PonteDeMentira())
    prof = disco["perfil"]
    assert prof.triggers.left.mode == estilos_de_jogo.POR_ROTULO["Corrida"].gatilho
    assert prof.rumble.policy == estilos_de_jogo.POR_ROTULO["Corrida"].vibracao
    assert not (prof.controllers or {})
    assert resposta is not None
    assert "nenhum controle ligado" in resposta["relato"]


def test_o_estilo_saiu_da_lista_de_travados() -> None:
    """``perfis_web`` não pode mais mostrar TRAVADO um campo que grava."""
    from hefesto_dualsense4unix.app.actions import perfis_web

    assert "editor.estilo" not in perfis_web.GESTOS_SEM_MOTOR
    editor = perfis_web.pacote_da_aba(
        [Profile(name="Pragmata", match=MatchAny())],
        editado=Profile(name="Pragmata", match=MatchAny()))["editor"]
    assert editor["estilo_travado"] is False
    assert editor["estilo"] is None
    assert "editor.estilo" in a10_perfis.NAO_PINTAVEIS


def test_o_pacote_manda_o_numero_cru_para_o_punho(
    monkeypatch: pytest.MonkeyPatch, disco: dict[str, Any],
) -> None:
    """``editor.prioridade.escolha`` é o número CRU — nunca a porcentagem."""
    disco["perfil"] = Profile(name="Pragmata", match=MatchAny(), priority=137)
    fora = a10_perfis.pacote(_ctx())
    assert fora["editor.prioridade.escolha"] == "137"
    assert fora["editor.prioridade"] == str(round(137 * 100 / PRIORIDADE_MAXIMA))


def test_sem_perfil_o_punho_nao_recebe_travessao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A guarda que impede o contador de mentir para sempre."""
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: [])
    fora = a10_perfis.pacote(_ctx())
    assert "editor.prioridade.escolha" not in fora, (
        "o punho recebeu um valor sem perfil aberto — o `'—'` do pintor faz o "
        "contador somar uma pintura por tique, para sempre")
