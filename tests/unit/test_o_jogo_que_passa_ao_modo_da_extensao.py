"""O perfil do Dungeons II passa ao Modo imersão uma vez, com cópia antes
(O-PERFIL-DO-DUNGEONS-II-PASSA-AO-MODO-IMERSAO-UMA-VEZ-01)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles import o_jogo_que_passa_ao_modo_da_extensao as passo
from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc
from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
from hefesto_dualsense4unix.profiles.schema import MODO_AUTOMATICO, Profile, perfil_no_modo
from hefesto_dualsense4unix.utils.xdg_paths import config_dir, profiles_dir

CABO_1 = "aa:bb:cc:00:00:01"
CABO_2 = "aa:bb:cc:00:00:02"
RADIO_1 = "aa:bb:cc:00:00:03"
RADIO_2 = "aa:bb:cc:00:00:04"
MODIFICADO = "2026-11-02T20:59:04"
GATILHO = {"mode": "Rigid", "params": [5, 200]}
IMERSAO = passo.MODO_DA_EXTENSAO
OUTRA = "extensao:outra"  # (noqa-acento)


def _dungeons(nome: str = "Minecraft Dungeons II", **trocas: Any) -> Profile:
    dados: dict[str, Any] = {
        "name": nome,
        "priority": 80,
        "match": {"type": "criteria", "window_class": ["steam_app_1912410"]},
        "triggers": {"left": GATILHO, "right": GATILHO, "modo": "personalizado"},
        "leds": {"lightbar": [10, 20, 200], "modo": "personalizado"},
        "rumble": {"policy": "max", "modo": "personalizado"},
        "controles_modo": "personalizado",
        "criado_em": "2026-10-01T10:00:00",
        "modificado_em": MODIFICADO,
        "controllers": {CABO_1: {}, CABO_2: {}, RADIO_1: {}, RADIO_2: {}},
    }
    dados.update(trocas)
    return Profile.model_validate(dados)


def _grava(perfil: Profile) -> Path:
    """O perfil no disco como o de quem usa: com as duas datas de um gesto antigo."""
    caminho = save_profile(perfil)
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    dados["criado_em"], dados["modificado_em"] = perfil.criado_em, perfil.modificado_em
    caminho.write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return caminho


def _md5(caminho: Path) -> str:
    return hashlib.md5(caminho.read_bytes()).hexdigest()


def _cru(caminho: Path) -> dict[str, Any]:
    return json.loads(caminho.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _marca() -> Path:
    return config_dir() / passo.MARCA


def test_as_tres_secoes_passam_com_a_copia_igual_e_a_marca() -> None:
    """Perfil do jogo com os quatro controles: três seções, cópia byte a byte, datas e marca."""
    caminho = _grava(_dungeons())
    antes = caminho.read_bytes()
    passou = passo.passar_uma_vez()
    assert passou == {caminho.stem: ["triggers", "leds", "rumble"]}
    cru = _cru(caminho)
    assert [cru[s]["modo"] for s in passo.SECOES] == [IMERSAO] * 3
    copia = caminho.with_name(caminho.name + passo.SUFIXO_DA_COPIA)
    assert copia.read_bytes() == antes
    assert hashlib.md5(copia.read_bytes()).hexdigest() == hashlib.md5(antes).hexdigest()
    assert cru["modificado_em"] == MODIFICADO
    assert _marca().exists()
    assert sorted(cru["controllers"]) == sorted(
        c.replace(":", "") for c in (CABO_1, CABO_2, RADIO_1, RADIO_2))
    assert cru["controles_modo"] == "personalizado"
    assert cru["triggers"]["left"] == GATILHO and cru["leds"]["lightbar"] == [10, 20, 200]
    assert cru["rumble"]["policy"] == "max"


def test_o_segundo_arranque_nao_muda_nada() -> None:
    caminho = _grava(_dungeons())
    assert passo.passar_uma_vez() is not None
    depois = _md5(caminho)
    assert passo.passar_uma_vez() is None
    assert _md5(caminho) == depois


def test_a_secao_em_automatico_e_o_modo_proprio_do_controle_ficam() -> None:
    """O modo de cada controle é dele: a entrada com `modo` próprio não é trocada."""
    perfil = _dungeons(
        leds={"lightbar": [10, 20, 200], "modo": MODO_AUTOMATICO},
        controllers={
            CABO_1: {"triggers": {"left": GATILHO, "modo": "personalizado"}},
            RADIO_1: {"leds": {"lightbar": [1, 2, 3], "modo": MODO_AUTOMATICO}},
            CABO_2: {}, RADIO_2: {},
        })
    caminho = _grava(perfil)
    passou = passo.passar_uma_vez()
    assert passou == {caminho.stem: ["triggers", "rumble"]}
    cru = _cru(caminho)
    assert cru["leds"]["modo"] == MODO_AUTOMATICO
    assert cru["controllers"][CABO_1.replace(":", "")]["triggers"]["modo"] == "personalizado", (
        "o modo de cada controle é dele")
    assert cru["controllers"][RADIO_1.replace(":", "")]["leds"]["modo"] == MODO_AUTOMATICO


def test_a_secao_em_outra_extensao_fica() -> None:
    caminho = _grava(_dungeons(rumble={"policy": "max", "modo": OUTRA}))
    assert passo.passar_uma_vez() == {caminho.stem: ["triggers", "leds"]}
    assert _cru(caminho)["rumble"]["modo"] == OUTRA


def test_a_secao_sem_modo_escrito_nao_passa() -> None:
    perfil = _dungeons(rumble={"policy": "max"})
    caminho = _grava(perfil)
    assert passo.passar_uma_vez() == {caminho.stem: ["triggers", "leds"]}
    assert "modo" not in _cru(caminho)["rumble"]


def test_outro_perfil_em_personalizado_sem_o_criterio_fica() -> None:
    outro = _grava(_dungeons(
        "Outro Jogo", match={"type": "criteria", "window_class": ["steam_app_1"]}))
    antes = _md5(outro)
    assert passo.passar_uma_vez() == {}
    assert _md5(outro) == antes
    assert not outro.with_name(outro.name + passo.SUFIXO_DA_COPIA).exists()
    assert _marca().exists()


def test_o_alvo_e_o_criterio_e_nao_o_nome_do_arquivo() -> None:
    """Quem renomeou o perfil continua com o jogo achado, e o critério vale sem caixa."""
    caminho = _grava(_dungeons(
        "Meu Dungeons", match={"type": "criteria", "window_class": ["Steam_App_1912410"]}))
    assert passo.passar_uma_vez() == {caminho.stem: ["triggers", "leds", "rumble"]}


def test_o_perfil_que_nasceu_depois_da_passada_nao_se_troca() -> None:
    """Pasta sem o perfil na primeira passada: a marca nasce, e o criado depois fica."""
    assert passo.passar_uma_vez() == {}
    assert _marca().exists()
    caminho = _grava(_dungeons())
    antes = _md5(caminho)
    assert passo.passar_uma_vez() is None
    assert _md5(caminho) == antes
    assert [_cru(caminho)[s]["modo"] for s in passo.SECOES] == ["personalizado"] * 3


def test_o_perfil_renomeado_e_voltado_a_personalizado_com_a_copia_apagada_fica() -> None:
    """A cópia não é a marca: o arquivo novo, sem cópia, não é trocado de novo."""
    caminho = _grava(_dungeons())
    assert passo.passar_uma_vez() is not None
    caminho.with_name(caminho.name + passo.SUFIXO_DA_COPIA).unlink()
    caminho.unlink()
    outro = _grava(_dungeons("Dungeons da Casa"))
    antes = _md5(outro)
    assert passo.passar_uma_vez() is None
    assert _md5(outro) == antes
    assert not outro.with_name(outro.name + passo.SUFIXO_DA_COPIA).exists()


def test_o_save_que_falha_nao_grava_a_marca_e_o_arranque_seguinte_passa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caminho = _grava(_dungeons())
    antes = _md5(caminho)
    original = loader.save_profile

    def falha(*_a: Any, **_k: Any) -> Path:
        raise OSError("disco cheio")

    monkeypatch.setattr(loader, "save_profile", falha)
    assert passo.passar_uma_vez() == {}
    assert not _marca().exists()
    assert _md5(caminho) == antes
    monkeypatch.setattr(loader, "save_profile", original)
    assert passo.passar_uma_vez() == {caminho.stem: ["triggers", "leds", "rumble"]}
    assert _marca().exists()


def test_a_falha_de_um_perfil_nao_segura_o_outro_e_nao_grava_a_marca(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primeiro = _grava(_dungeons("Dungeons A"))
    segundo = _grava(_dungeons("Dungeons B"))
    original = loader.save_profile

    def falha_no_primeiro(perfil: Profile, **k: Any) -> Path:
        if perfil.name == "Dungeons A":
            raise OSError("disco cheio")
        return original(perfil, **k)

    monkeypatch.setattr(loader, "save_profile", falha_no_primeiro)
    assert passo.passar_uma_vez() == {segundo.stem: ["triggers", "leds", "rumble"]}
    assert not _marca().exists()
    assert [_cru(primeiro)[s]["modo"] for s in passo.SECOES] == ["personalizado"] * 3


def test_o_gesto_de_quem_usa_nao_carimba_o_modificado_em() -> None:
    caminho = _grava(_dungeons())
    sinal = loader.gesto_de_agora.set("gesto-de-outra-hora")
    try:
        assert passo.passar_uma_vez() is not None
        assert loader.gesto_de_agora.get() == "gesto-de-outra-hora"
    finally:
        loader.gesto_de_agora.reset(sinal)
    assert _cru(caminho)["modificado_em"] == MODIFICADO


def test_a_copia_de_fabrica_e_o_json_torto_ficam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    torto = profiles_dir(ensure=True) / "torto.json"
    torto.write_text("{ isto não é json", encoding="utf-8")
    de_fabrica = _grava(_dungeons())
    monkeypatch.setattr(loader, "_e_copia_de_fabrica", lambda *_a: True)
    assert passo.passar_uma_vez() == {}
    assert torto.read_text(encoding="utf-8") == "{ isto não é json"
    assert [_cru(de_fabrica)[s]["modo"] for s in passo.SECOES] == ["personalizado"] * 3


def _sem_o_modo(dados: dict[str, Any]) -> dict[str, Any]:
    for secao in passo.SECOES:
        dados[secao].pop("modo", None)
    return dados


def test_com_a_extensao_desligada_o_aparelho_recebe_o_que_o_personalizado_dava() -> None:
    """Medida de 22/11: sem a extensão viva a vista é a do personalizado; com a extensão viva,
    o efeito fixo dos gatilhos e da luz cala (a vibração é da extensão, por cima)."""
    caminho = _grava(_dungeons())
    antes = perfil_no_modo(load_profile(caminho.stem), frozenset()).model_dump(mode="json")
    assert passo.passar_uma_vez() is not None
    passado = load_profile(caminho.stem)
    assert passado.triggers.modo == IMERSAO
    desligada = perfil_no_modo(passado, frozenset()).model_dump(mode="json")
    assert _sem_o_modo(desligada) == _sem_o_modo(antes)
    assert desligada["triggers"]["left"] == GATILHO
    assert desligada["leds"]["lightbar"] == [10, 20, 200]
    ligada = perfil_no_modo(passado, frozenset({"imersao"})).model_dump(mode="json")
    assert ligada["triggers"]["left"]["mode"] == "Off"
    assert ligada["leds"]["lightbar"] == [0, 0, 0]
    assert ligada["rumble"]["policy"] == "max"


def test_o_passo_do_computador_chama_a_passada_antes_de_tudo() -> None:
    caminho = _grava(_dungeons())
    opc.migrar_uma_vez()
    assert [_cru(caminho)[s]["modo"] for s in passo.SECOES] == [IMERSAO] * 3
    assert caminho.with_name(caminho.name + passo.SUFIXO_DA_COPIA).exists()
    assert opc.o_computador().migrado is True


def test_a_passada_ja_feita_nao_para_o_passo_do_computador_numa_maquina_migrada() -> None:
    """O `migrado` do computador já é verdade; a passada roda mesmo assim, uma vez."""
    assert opc.migrar_uma_vez() is not None
    assert opc.migrar_uma_vez() is None
    (config_dir() / passo.MARCA).unlink()
    caminho = _grava(_dungeons())
    assert opc.migrar_uma_vez() is None
    assert [_cru(caminho)[s]["modo"] for s in passo.SECOES] == [IMERSAO] * 3


def test_a_falha_da_passada_nao_segura_o_computador(monkeypatch: pytest.MonkeyPatch) -> None:
    def quebra() -> None:
        raise RuntimeError("falhou")

    monkeypatch.setattr(passo, "passar_uma_vez", quebra)
    _grava(_dungeons())
    assert opc.migrar_uma_vez() is not None
    assert opc.o_computador().migrado is True
