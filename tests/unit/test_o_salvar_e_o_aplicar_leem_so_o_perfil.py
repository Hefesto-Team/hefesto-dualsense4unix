"""O «Salvar» e o «Aplicar» leem o perfil do disco, e só ele — em toda aba."""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import Profile

NOME = "PRAGMATA"

P1, P2, P3, P4 = "02fe000000f0", "aabbcc0000d8", "aabbcc000003", "aabbcc0000ab"

PERFIL: dict[str, Any] = {
    "name": NOME, "version": 1,
    "match": {"type": "criteria", "window_class": ["steam_app_3357650"],
              "window_title_regex": None, "process_name": []},
    "priority": 80,
    "triggers": {"left": {"mode": "Off", "params": []},
                 "right": {"mode": "Off", "params": []}},
    "leds": {"lightbar": [0, 0, 0], "player_leds": [False] * 5,
             "lightbar_brightness": 1.0, "auto_player_colors": True,
             "lightbar_para_o_numero": None},
    "rumble": {"passthrough": True, "policy": "balanceado", "custom_mult": None},
    "mouse": {"enabled": False, "speed": 6, "scroll_speed": 1},
    "mode": {"kind": "gamepad", "gamepad_flavor": None, "caminho": "dualsense"},
    "suppress_desktop_emulation": False,
    "controllers": {
        P1: {"leds": {"lightbar": [0, 255, 0], "lightbar_brightness": 0.9},
             "speaker": {"volume": 102, "muted": False},
             "mic": {"muted": True, "volume": 98},
             "mascara": "dualsense"},
        P2: {"leds": {"lightbar": [128, 255, 0], "lightbar_brightness": 0.7},
             "rumble": {"policy": "custom", "custom_mult": 2.0},
             "speaker": {"volume": 102, "muted": False},
             "mic": {"muted": True, "volume": 54},
             "mascara": "dualsense"},
        P3: {"leds": {"lightbar": [255, 0, 0]},
             "triggers": {"left": {"mode": "SimpleRigid", "params": [6]},
                          "right": {"mode": "Machine",
                                    "params": [0, 9, 3, 3, 50, 8]}},
             "rumble": {"policy": "max"},
             "speaker": {"volume": 102, "muted": True, "rota": 2, "fonte": "sfx"},
             "mic": {"muted": True, "volume": 68, "gain": 40},
             "mascara": "dualsense"},
        P4: {"leds": {"lightbar": [255, 0, 128]},
             "speaker": {"volume": 102, "muted": False},
             "mic": {"muted": True, "volume": 98},
             "mascara": "xbox"},
    },
    "ponte": {"kind": "gamepad", "gamepad_flavor": "dualsense",
              "steam_input": False,
              "confirmada_em": "2026-09-17T01:42:11-03:00",
              "confirmada_por": "silencio"},
}


def _vivo(uniq: str, via: str, *, cor: list[int], barra: float,
          mic_mudo: bool, volume: int, giro: bool) -> dict[str, Any]:
    """Um controle como o `state_full` o publica, divergindo do disco."""
    return {
        "uniq": uniq, "connected": True, "transport": via,
        "lightbar_rgb": cor, "lightbar_on": True, "lightbar_source": "sysfs",
        "brilho_da_barra": barra, "brilho_das_luzes": "fraco",
        "speaker": {"volume": volume, "muted": not mic_mudo, "rota": 1},
        "audio": {"mic_mudo": mic_mudo, "mic_mudo_desejado": None,
                  "volume_captura": 30},
        "sensores": {"giroscopio_ligado": giro, "acelerometro_ligado": True},
    }


VIVOS: list[dict[str, Any]] = [
    _vivo(P1, "usb", cor=[0, 0, 255], barra=0.5, mic_mudo=True, volume=40, giro=True),
    _vivo(P2, "bt", cor=[38, 76, 0], barra=0.3, mic_mudo=True, volume=60, giro=False),
    _vivo(P3, "bt", cor=[0, 255, 255], barra=1.0, mic_mudo=False, volume=20, giro=True),
    _vivo(P4, "usb", cor=[255, 255, 0], barra=0.8, mic_mudo=False, volume=90, giro=False),
]

MESA_VIVA: dict[str, Any] = {
    "rumble_policy": "max",
    "rumble_passthrough": False,
    "rumble_policy_custom_mult": 0.7,
    "mouse_emulation": {"enabled": True, "speed": 11, "scroll_speed": 4},
}

AS_DEZ = ("01-jogar.html", "02-controles.html", "03-gatilhos.html",
          "04-iluminacao.html", "05-vibracao.html", "06-navegacao.html",
          "07-lancadores.html", "08-conexoes.html", "09-sistema.html",
          "10-perfis.html")


class PonteDoRodape:
    """O que o «Aplicar» chama, com a resposta que o daemon real devolve."""

    def __init__(self) -> None:
        self.reaplicados: list[str] = []

    def profile_reaplicar(self, nome: str) -> dict[str, Any]:
        """O-APLICAR-E-A-ATIVACAO-SAO-UMA-SO-01: o «Aplicar» manda só o nome."""
        self.reaplicados.append(nome)
        return {"active_profile": nome, "mode_aplicado": True, "secoes": {}}

    def profile_switch(self, nome: str) -> bool:
        return True

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
        return True

    def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
        return {}


@pytest.fixture(autouse=True)
def _o_disco(monkeypatch: pytest.MonkeyPatch) -> None:
    """O perfil no disco hermético da suíte, gravado pelo próprio produto."""
    from hefesto_dualsense4unix.profiles.schema import declaracao_da_economia
    from hefesto_dualsense4unix.utils.maquina import gravar_maquina

    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", NOME, raising=False)
    loader.save_profile(Profile.model_validate(PERFIL), origem="teste")
    assert gravar_maquina(declaracao_da_economia(P2, True))


def _ctx() -> Contexto:
    vivos = copy.deepcopy(VIVOS)
    return Contexto(state={"active_profile": NOME, "controllers": vivos,
                           **copy.deepcopy(MESA_VIVA)},
                    mesa=vivos, conectados=vivos)


def _clique(aba: str, gesto: str) -> dict[str, str]:
    """O clique como o piloto o manda: com a aba de onde veio."""
    return {"gesto": gesto, "pagina": aba}  # (noqa-acento: chave do clique)


def _o_arquivo() -> bytes:
    arquivo = loader.arquivo_do_perfil(NOME)
    assert arquivo is not None, f"o perfil {NOME!r} não está no disco"
    return arquivo.read_bytes()


def _o_perfil() -> dict[str, Any]:
    """O perfil no disco: a parte global pelo esquema, os overrides crus."""
    cru = json.loads(_o_arquivo())
    perfil = Profile.model_validate(cru).model_dump(mode="json")
    perfil["controllers"] = cru.get("controllers")
    return perfil


def _o_que_mudou(antes: Any, depois: Any, pre: str = "") -> list[str]:
    if isinstance(antes, dict) and isinstance(depois, dict):
        fora: list[str] = []
        for k in sorted(set(antes) | set(depois)):
            fora += _o_que_mudou(antes.get(k), depois.get(k), f"{pre}.{k}" if pre else k)
        return fora
    return [] if antes == depois else [f"{pre}: {antes!r} -> {depois!r}"]


def _salvar(aba: str) -> None:
    gesto = pacotes.gesto_da_pagina(aba, "salvar")
    assert gesto is not None, f"a {aba} não tem quem atenda o «Salvar»"
    gesto(_ctx(), _clique(aba, "salvar"), PonteDoRodape())


@pytest.mark.parametrize("aba", AS_DEZ)
def test_o_salvar_de_qualquer_aba_grava_o_disco_como_estava(aba: str) -> None:
    """Com o aparelho divergindo em tudo, o perfil gravado é o que estava lá."""
    antes = _o_perfil()
    _salvar(aba)
    mudou = _o_que_mudou(antes, _o_perfil())
    assert not mudou, (
        f"o «Salvar» da {aba} gravou o que o aparelho diz, e não o disco:\n  "
        + "\n  ".join(mudou))


@pytest.mark.parametrize("aba", AS_DEZ)
def test_as_tres_fontes_que_nao_sao_dela_ficam_fora_do_disco(aba: str) -> None:
    """O botão do microfone, o teto da economia e a política viva, nomeados."""
    _salvar(aba)
    depois = json.loads(_o_arquivo())
    dele = depois["controllers"]
    assert dele[P3]["mic"]["muted"] is True and dele[P4]["mic"]["muted"] is True, (
        f"o «Salvar» da {aba} gravou o microfone aberto do aparelho como escolha "
        "dela (P3 e P4)")
    assert dele[P2]["leds"]["lightbar_brightness"] == pytest.approx(0.7), (
        f"o «Salvar» da {aba} gravou o teto da economia do P2 como o brilho dela")
    assert depois["rumble"]["policy"] == "balanceado", (
        f"o «Salvar» da {aba} gravou a política viva `max` no perfil")
    assert dele[P3]["speaker"].get("fonte") == "sfx", (
        f"o «Salvar» da {aba} apagou a fonte do alto-falante do P3")


def test_o_salvar_regrava_o_arquivo_na_forma_de_hoje() -> None:
    """O Salvar ESCREVE: o arquivo na forma de ontem sai na de hoje, igual."""
    arquivo = loader.arquivo_do_perfil(NOME)
    assert arquivo is not None
    velho = {**json.loads(arquivo.read_bytes()),
             "key_bindings": None, "speaker": None, "mic": None}
    arquivo.write_text(json.dumps(velho, ensure_ascii=False), encoding="utf-8")
    antes = _o_perfil()
    _salvar("07-lancadores.html")
    depois = json.loads(_o_arquivo())
    assert not {"key_bindings", "speaker", "mic"} & set(depois), (
        "o «Salvar» não regravou o arquivo na forma de hoje: as seções sem "
        f"opinião continuam com `null` ({sorted(set(velho) & set(depois))})")
    assert _o_arquivo().count(b"\n") > 1, "o «Salvar» deixou o arquivo numa linha"
    mudou = _o_que_mudou(antes, _o_perfil())
    assert not mudou, (
        "o «Salvar» mudou o perfil ao normalizar:\n  " + "\n  ".join(mudou))


def test_salvar_duas_vezes_grava_o_mesmo_arquivo_nas_dez_abas() -> None:
    """Idempotente: depois do primeiro Salvar (que só normaliza), byte a byte."""
    _salvar(AS_DEZ[0])
    marca = hashlib.sha256(_o_arquivo()).hexdigest()
    for aba in AS_DEZ + AS_DEZ:
        _salvar(aba)
        assert hashlib.sha256(_o_arquivo()).hexdigest() == marca, (
            f"o «Salvar» da {aba} mudou o arquivo que o anterior já tinha gravado")


@pytest.mark.parametrize("aba", AS_DEZ)
def test_o_aplicar_de_qualquer_aba_manda_o_perfil_do_disco(aba: str) -> None:
    """O «Aplicar» pede ao daemon o perfil do disco, pelo nome, e não grava nada."""
    antes = _o_arquivo()
    gesto = pacotes.gesto_da_pagina(aba, "aplicar")
    assert gesto is not None, f"a {aba} não tem quem atenda o «Aplicar»"
    ponte = PonteDoRodape()
    gesto(_ctx(), _clique(aba, "aplicar"), ponte)
    gesto(_ctx(), _clique(aba, "aplicar"), ponte)
    assert ponte.reaplicados == [NOME, NOME], (
        f"o «Aplicar» da {aba} pediu {ponte.reaplicados}, e o perfil é {NOME!r}")
    assert _o_arquivo() == antes, f"o «Aplicar» da {aba} gravou no disco"


def test_o_aplicar_e_o_salvar_miram_o_mesmo_perfil() -> None:
    """O perfil que o Aplicar pede é o arquivo que o Salvar grava."""
    ponte = PonteDoRodape()
    pacotes.gesto_da_pagina("05-vibracao.html", "aplicar")(
        _ctx(), _clique("05-vibracao.html", "aplicar"), ponte)
    _salvar("02-controles.html")
    gravado = Profile.model_validate(json.loads(_o_arquivo()))
    assert ponte.reaplicados == [gravado.name], (
        f"o «Aplicar» pediu {ponte.reaplicados} e o «Salvar» gravou {gravado.name!r}")


def test_o_editor_da_10_grava_so_o_campo_dele_com_o_aparelho_divergindo() -> None:
    """Mudar a prioridade grava a prioridade, e o microfone e a cor ficam."""
    antes = _o_perfil()
    a10_perfis.editor_prioridade(_ctx(), {"valor": "81", "evento": "change"},
                                 PonteDoRodape())
    mudou = _o_que_mudou(antes, _o_perfil())
    assert mudou == ["priority: 80 -> 81"], (
        "o editor da aba Perfis gravou mais que a prioridade:\n  " + "\n  ".join(mudou))
