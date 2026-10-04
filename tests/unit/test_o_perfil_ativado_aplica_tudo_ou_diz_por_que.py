"""O-PERFIL-ATIVADO-APLICA-TUDO-OU-DIZ-POR-QUE-01 (03/10/2026).

O log da janela dela: «Perfil ativado: Avatar Legends — Aplicado, menos:
mascara:<id>, mascara:<id>, alto-falante de um…». No diário do serviço, no mesmo
instante, a máscara de um controle FOI aplicada (`profile_mascara_por_peca`
mascara=xbox) e a do outro VOLTOU AO PADRÃO (`profile_mascara_devolvida_ao_padrao`).
A causa era do LEITOR (`relato_da_ativacao`): ele chamava de «não entrou» tudo o
que não vinha escrito «aplicado», e a seção por controle `mascara:<id>` não
responde com um estado, responde com o DADO aplicado (o nome da máscara).
"""
from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.profiles_actions`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions import profiles_actions as pa
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import Profile
from hefesto_dualsense4unix.testing.fake_controller import FakeController

#: A forma que o perfil e o daemon usam por dentro (o esquema tira os `:`).
P1 = "aabbcc000001"
P2 = "aabbcc000002"
P3 = "aabbcc000003"


@pytest.fixture
def registro_de_mentira(monkeypatch: pytest.MonkeyPatch):
    """Um registro de máscaras que não toca o disco."""
    from hefesto_dualsense4unix.daemon.subsystems import external_mask as em

    monkeypatch.setattr(em.ExternalMaskRegistry, "_load_locked", lambda self: None)
    monkeypatch.setattr(em.ExternalMaskRegistry, "_save_locked", lambda self: None)
    em._zerar_registro_de_mascaras()
    yield em.registro_de_mascaras()
    em._zerar_registro_de_mascaras()


def _ativacao_do_avatar(registro: Any, estado_do_speaker_de_p3: str) -> dict[str, str]:
    """O que o `profile.switch` relata: máscara em P1, P2 devolvido ao padrão, 3 alto-falantes."""
    registro.set_mask(P2, "xbox")  # tinha máscara própria; o perfil não a declara
    estados = {P1: "aplicado", P2: "aplicado", P3: estado_do_speaker_de_p3}
    gerente = ProfileManager(
        controller=FakeController(),
        store=StateStore(),
        speaker_applier=lambda _v, _m, *, uniq=None, **_k: estados[str(uniq)],
    )
    perfil = Profile.model_validate({
        "name": "Avatar Legends",
        "version": 1,
        "match": {"type": "any"},
        "priority": 10,
        "controllers": {
            P1: {"mascara": "xbox", "speaker": {"volume": 60}},
            P2: {"speaker": {"volume": 60}},
            P3: {"speaker": {"volume": 60}},
        },
    })
    relatorio: dict[str, str] = {"leds": "aplicado"}
    gerente.apply_controller_mascaras(perfil, relatorio=relatorio)
    gerente.apply_controller_speakers(perfil, relatorio=relatorio)
    return relatorio


def test_mascara_aplicada_e_devolvida_ao_padrao_nao_e_falta(registro_de_mentira) -> None:
    relatorio = _ativacao_do_avatar(registro_de_mentira, "aplicado")
    # o que o produto de fato escreve: o DADO, nunca a palavra «aplicado»
    assert relatorio[f"mascara:{P1}"] == "xbox"
    assert relatorio[f"mascara:{P2}"] == "padrão"

    assert pa.mensagem_de_ativacao("Avatar Legends", {"secoes": relatorio}) == (
        "Perfil ativado: Avatar Legends"
    )


def test_o_alto_falante_de_um_controle_que_nao_esta_ligado_nao_e_falta(
    registro_de_mentira,
) -> None:
    """Sem o controle não há o que escrever; ele recebe quando reconecta."""
    relatorio = _ativacao_do_avatar(registro_de_mentira, "ignorado_sem_controle")
    assert relatorio[f"speaker:{P3}"] == "ignorado_sem_controle"

    assert pa.mensagem_de_ativacao("Avatar Legends", {"secoes": relatorio}) == (
        "Perfil ativado: Avatar Legends"
    )


def test_o_que_falhou_de_verdade_segue_dito_e_sem_chave_crua(registro_de_mentira) -> None:
    relatorio = _ativacao_do_avatar(registro_de_mentira, "falhou")
    relatorio[f"mascara:{P1}"] = "recusado"

    frase = pa.mensagem_de_ativacao("Avatar Legends", {"secoes": relatorio})

    assert frase.startswith("Perfil ativado: Avatar Legends — Aplicado, menos: ")
    assert "máscara de um controle" in frase and "alto-falante de um controle" in frase
    assert "mascara:" not in frase and "speaker:" not in frase


@pytest.mark.parametrize(("chave", "estado", "nome"), [
    (f"mic:{P1}", "falhou", "microfone"),
    (f"mic:ganho:{P1}", "falhou", "microfone"),
    (f"movimento:{P1}", "falhou", "mira"),
])
def test_toda_peca_por_controle_que_falha_sai_com_palavra_de_tela(
    chave: str, estado: str, nome: str
) -> None:
    frase = pa.mensagem_de_ativacao("X", {"secoes": {"leds": "aplicado", chave: estado}})
    assert nome in frase and chave.split(":")[0] + ":" not in frase, frase


def test_sensores_e_dado_nao_e_estado() -> None:
    secoes = {"leds": "aplicado", f"sensores:{P1}": "giro=on accel=off"}
    assert pa.mensagem_de_ativacao("X", {"secoes": secoes}) == "Perfil ativado: X"


def test_o_global_sem_controle_segue_dito() -> None:
    """Só a PEÇA de um controle ausente deixa de ser falta; o global segue dito."""
    secoes = {"leds": "aplicado", "speaker": "ignorado_sem_controle"}
    assert "alto-falante" in pa.mensagem_de_ativacao("X", {"secoes": secoes})


def test_o_gesto_ativar_da_aba_perfis_diz_so_o_nome_quando_tudo_entrou(
    monkeypatch: pytest.MonkeyPatch, registro_de_mentira
) -> None:
    """A PONTA: o `ativar` da aba 10 com o corpo que o produto de fato produz.

    Antes, a frase do rodapé saía «Perfil ativado: Avatar Legends — Aplicado, menos:
    mascara:…, mascara:…».
    """
    from hefesto_dualsense4unix.interface.pacotes import a10_perfis
    from tests.unit.test_aba10_os_gestos_dizem_o_que_fizeram import (
        PonteDeMentira,
        _ctx,
        _o_disco_tem,
        _o_marcador_diz,
    )

    _o_disco_tem(monkeypatch, "Avatar Legends", "Sackboy")
    _o_marcador_diz(monkeypatch, None)
    a10_perfis._ESCOLHIDO = "Avatar Legends"
    corpo = {"secoes": _ativacao_do_avatar(registro_de_mentira, "ignorado_sem_controle")}

    carga = a10_perfis.ativar(_ctx(ativo="Sackboy"), {"texto": "Ativar"},
                              PonteDeMentira(corpo=corpo))

    assert carga["relato"] == "Perfil ativado: Avatar Legends"
