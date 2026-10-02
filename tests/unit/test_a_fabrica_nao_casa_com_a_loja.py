"""Nenhum perfil DE FÁBRICA pode casar com a janela do cliente Steam."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hefesto_dualsense4unix.profiles.loader import (
    perfis_que_casam_com_o_cliente_steam,
)
from hefesto_dualsense4unix.profiles.steam_app import e_janela_do_cliente_steam

RAIZ = Path(__file__).resolve().parents[2]
FABRICA = RAIZ / "assets" / "profiles_default"
ESTILOS = RAIZ / "assets" / "estilos_de_jogo"
CASAS_DE_FABRICA = (FABRICA, ESTILOS)


class TestAFabricaNaoCasaComALoja:
    def test_o_diretorio_de_fabrica_existe_e_tem_perfis(self) -> None:
        """Guarda do próprio instrumento: régua que não acha nada passa sempre."""
        for casa in CASAS_DE_FABRICA:
            assert casa.is_dir(), f"uma casa da fábrica sumiu: {casa}"
        presets = sorted(p for casa in CASAS_DE_FABRICA for p in casa.glob("*.json"))
        assert len(presets) >= 9, (
            f"a fábrica tem só {len(presets)} presets — se ela encolheu, este "
            "teste passou a medir menos do que promete. Confira antes de "
            "baixar o piso."
        )

    def test_nenhum_preset_de_fabrica_casa_com_a_loja(self) -> None:
        """O portão. Roda a régua DO PRODUTO sobre o diretório de fábrica."""
        culpados = [
            achado
            for casa in CASAS_DE_FABRICA
            for achado in perfis_que_casam_com_o_cliente_steam(casa)
        ]
        assert culpados == [], (
            "preset de FÁBRICA casando com a janela do cliente Steam:\n"
            + "\n".join(
                f"  {arquivo} (perfil {nome!r}) por causa de {list(classes)}"
                for arquivo, nome, classes in culpados
            )
            + "\n\nUma janela invisível do steamwebhelper ativa este perfil no "
            "meio da partida — foram treze trocas em 54 minutos na máquina "
            "dela. Decisão D-STEAM-SAI-DA-NAVEGACAO, 22/08/2026: as classes da "
            "loja saem do preset de desktop.\n"
            "Se um preset PRECISA mesmo casar com a loja, ele não é preset de "
            "desktop — e a exceção é decisão dela, não do código."
        )

    def test_navegacao_continua_casando_com_os_navegadores(self) -> None:
        """A cura não pode ter esvaziado o perfil: ele ainda serve para navegar."""
        dados = json.loads((ESTILOS / "navegacao.json").read_text(encoding="utf-8"))
        classes = dados["match"]["window_class"]
        for esperada in ("firefox", "chromium", "google-chrome"):
            assert esperada in classes, (
                f"o preset Navegação perdeu {esperada!r}: a cura da loja não "
                "pode levar junto o que o perfil existe para casar."
            )

    @pytest.mark.parametrize("classe", ["steam", "Steam"])
    def test_a_regua_reconhece_as_duas_grafias(self, classe: str) -> None:
        """Guarda do instrumento: uma régua cega passaria verde para sempre."""
        assert e_janela_do_cliente_steam(classe), (
            f"a régua do produto não reconhece {classe!r} como janela do "
            "cliente Steam. Enquanto ela não reconhecer, o portão desta "
            "suíte está VERDE sem medir nada."
        )
