"""Os dois campos da aba Perfis que passaram a ESCREVER — 03/09/2026."""
from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions import trigger_specs
from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import efeitos_de_imersao, estilos_de_jogo, loader
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


def test_a_prioridade_saiu_da_pagina_e_a_faixa_segue_do_esquema() -> None:
    """A página não tem mais o trilho da Prioridade (a ordem é a da lista), e o teto é do esquema.

    MORDIDA: devolva o `<input type="range">` ao gerador e isto reprova.
    """
    html = _bancada()
    assert 'type="range"' not in html and "editor.prioridade" not in html, (
        "a Prioridade voltou à página: quem manda é a ordem arrastada (`editor.ordem`)")
    assert (PRIORIDADE_MINIMA, PRIORIDADE_MAXIMA) == (0, 200)


def test_so_os_campos_de_texto_ficam_fora_do_tique() -> None:
    """O que ela DIGITA não se repinta a cada 500 ms (apagaria a frase no meio da escrita).

    Com o trilho da Prioridade fora da página restam os dois campos de texto e o select do estilo,
    que se pinta só quando outro perfil abre (pintar a cada tique reaplicaria a receita).
    MORDIDA: tire ``editor.jogo`` de ``CAMPOS_QUE_ELA_DIGITA`` e isto reprova.
    """
    assert set(a10_perfis.CAMPOS_QUE_ELA_DIGITA) == {
        "editor.jogo", "editor.evento.comando", "editor.estilo"}


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
    assert prof.triggers.left.mode == receita.l2.modo  # o L2 e o R2 são receitas separadas
    assert prof.triggers.right.mode == receita.r2.modo == receita.gatilho
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
        if estilo.chave in estilos_de_jogo.SEM_COR:
            continue
        disco["perfil"] = Profile(name="Pragmata", match=MatchAny(), priority=40)
        a10_perfis.editor_estilo(_ctx(), {"valor": estilo.rotulo},
                                 PonteDeMentira())
        for disco_do_lado, dele in (("left", estilo.l2), ("right", estilo.r2)):
            spec = trigger_specs.get_spec(dele.modo)
            assert spec is not None, f"{estilo.rotulo}: gatilho fora do produto"
            # os números do dono: a imersão do lado, ou os de partida do acionamento
            numeros = (
                efeitos_de_imersao.ajustes_da_imersao(
                    efeitos_de_imersao.POR_CHAVE[dele.imersao], dele.modo, estilo.chave)
                if dele.imersao else {})
            esperado = list(trigger_specs.preset_to_positional_params(spec, numeros or {}))
            tem = list(getattr(disco["perfil"].triggers, disco_do_lado).params)
            assert tem == esperado, (
                f"{estilo.rotulo}/{disco_do_lado}: params {tem} != {esperado} do dono")
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


def test_personalizado_nao_mexe_nas_abas_e_desliga_a_receita(
        disco: dict[str, Any]) -> None:
    """"Personalizado" é o estilo que diz *"eu ajusto na mão"*: grava só a chave dele.

    Até 09/10/2026 ele não gravava nada, e o ``estilo`` anterior seguia no disco com a
    receita invisível tocando (O-PERSONALIZADO-DESLIGA-A-RECEITA-DO-ESTILO-ANTERIOR-01).
    """
    era = disco["perfil"].model_copy(update={"estilo": "fps"})
    disco["perfil"] = era
    resposta = a10_perfis.editor_estilo(
        _ctx(), {"valor": "Personalizado"}, PonteDeMentira())
    assert len(disco["salvos"]) == 1, "o `Personalizado` não gravou a chave dele"
    novo = disco["perfil"]
    assert novo.estilo == "personalizado"
    for campo in ("triggers", "rumble", "leds", "controllers"):
        assert getattr(novo, campo) == getattr(era, campo), (
            f"o `Personalizado` mexeu em `{campo}`, que é das abas")
    assert resposta is not None
    assert "desligada" in resposta["relato"]


def test_um_estilo_que_o_produto_nao_conhece_recusa(disco: dict[str, Any]) -> None:
    """MORDIDA: tire o ``if estilo is None`` e isto vira ``AttributeError``."""
    with pytest.raises(RuntimeError, match="não é um dos estilos de jogo"):
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
    assert prof.triggers.right.mode == estilos_de_jogo.POR_ROTULO["Corrida"].gatilho
    assert prof.triggers.left.mode == estilos_de_jogo.POR_ROTULO["Corrida"].l2.modo
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
    assert "editor.estilo" not in a10_perfis.NAO_PINTAVEIS


def test_o_pacote_nao_manda_mais_a_prioridade_para_a_pagina(
    monkeypatch: pytest.MonkeyPatch, disco: dict[str, Any],
) -> None:
    """A página não tem o trilho; mandar o número seria endereço sem lugar.

    MORDIDA: faça o pacote emitir ``editor.prioridade.escolha`` de novo e isto reprova.
    """
    disco["perfil"] = Profile(name="Pragmata", match=MatchAny(), priority=137)
    fora = a10_perfis.pacote(_ctx())
    assert not [k for k in fora if k.startswith("editor.prioridade")], (
        "o pacote voltou a mandar a Prioridade, que a página nova não desenha")


def test_sem_perfil_o_punho_nao_recebe_travessao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A guarda que impede o contador de mentir para sempre."""
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: [])
    fora = a10_perfis.pacote(_ctx())
    assert "editor.prioridade.escolha" not in fora, (
        "o punho recebeu um valor sem perfil aberto — o `'—'` do pintor faz o "
        "contador somar uma pintura por tique, para sempre")
