"""Nenhum perfil DE FÁBRICA pode casar com a janela do cliente Steam.

O DEFEITO QUE ESTE PORTÃO IMPEDE DE VOLTAR
-------------------------------------------

Uma janela invisível do ``steamwebhelper`` se anuncia com a ``wm_class``
``steam``. Um perfil de desktop que liste ``steam`` entre as suas
``window_class`` é ativado por ela **no meio da partida** — e leva junto os
gatilhos, a barra de luz e a vibração daquele perfil, no lugar dos do jogo.

Medido na máquina dela: **treze trocas de perfil em 54 minutos de partida.**
Ela levou os 54 minutos para descobrir de onde vinham, porque a troca
acontecia em silêncio.

A decisão é dela, ``D-STEAM-SAI-DA-NAVEGACAO``, tomada em 22/08/2026:

    *"tirar 'steam' e 'Steam' do perfil Navegação"*

Executada em 25/08/2026 — três dias depois, e o atraso é o motivo deste
arquivo existir. A correção é uma linha de JSON, e uma linha de JSON volta
sozinha na próxima vez que alguém editar o preset de fábrica achando que
``steam`` ali é um acerto. **Sem mordida, a cura tem prazo de validade.**

POR QUE A FÁBRICA, E NÃO O ARQUIVO VIVO DELA
---------------------------------------------

``assets/profiles_default/`` é o que toda instalação nova copia: é o único
lugar onde a correção alcança quem ainda não instalou o produto. O arquivo
vivo é **dela** e o produto não o edita — para esse, o que existe é o aviso
``perfil_casa_com_a_loja`` do ``loader``, que DIZ e não mexe.

Os dois se complementam de propósito, e é por isso que
``perfis_que_casam_com_o_cliente_steam`` continua no produto mesmo com a
fábrica curada: perfil escrito à mão, perfil de instalação antiga e perfil
copiado de outra máquina continuam alcançando o defeito.

A RÉGUA É A DO PRODUTO, DE PROPÓSITO
-------------------------------------

Este teste NÃO define uma segunda lista de nomes de janela da Steam. Ele
chama ``perfis_que_casam_com_o_cliente_steam``, que é a mesma função que o
``loader`` usa em produção, e que por sua vez usa o mesmo predicado
(``profiles/steam_app.e_janela_do_cliente_steam``) que o ``lifecycle`` usa
para proteger a partida.

Uma segunda lista divergiria da primeira — é o defeito que esta casa chama de
"duas verdades no mesmo repositório", e ele já custou uma leva.

A MORDIDA
---------

Devolva ``"steam", "Steam"`` a ``assets/profiles_default/navegacao.json`` e
``test_nenhum_preset_de_fabrica_casa_com_a_loja`` reprova, nomeando o arquivo.
"""
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


class TestAFabricaNaoCasaComALoja:
    def test_o_diretorio_de_fabrica_existe_e_tem_perfis(self) -> None:
        """Guarda do próprio instrumento: régua que não acha nada passa sempre."""
        assert FABRICA.is_dir(), f"o diretório de fábrica sumiu: {FABRICA}"
        presets = sorted(FABRICA.glob("*.json"))
        # PISO BAIXADO de 10 para 9 em 26/08/2026, e o motivo é a poda: `bow`,
        # `coop_local` e `sackboy_nativo` saíram da fábrica a pedido dela
        # (*"em termos de perfis de jogo vamos manter os que temos ativos
        # apenas"*), deixando 9. Não é o piso cedendo por conveniência — a
        # contagem exata dos 9 está travada em
        # `test_profiles_preset.py::TestOsPodadosNaoVoltam`, que reprova por
        # nome se a fábrica mudar de tamanho outra vez.
        assert len(presets) >= 9, (
            f"a fábrica tem só {len(presets)} presets — se ela encolheu, este "
            "teste passou a medir menos do que promete. Confira antes de "
            "baixar o piso."
        )

    def test_nenhum_preset_de_fabrica_casa_com_a_loja(self) -> None:
        """O portão. Roda a régua DO PRODUTO sobre o diretório de fábrica."""
        culpados = perfis_que_casam_com_o_cliente_steam(FABRICA)
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
        """A cura não pode ter esvaziado o perfil: ele ainda serve para navegar.

        Tirar ``steam`` sem esta guarda deixaria passar um conserto que
        apagasse a lista inteira — o perfil pararia de mentir e pararia
        também de funcionar.
        """
        dados = json.loads((FABRICA / "navegacao.json").read_text(encoding="utf-8"))
        classes = dados["match"]["window_class"]
        for esperada in ("firefox", "chromium", "google-chrome"):
            assert esperada in classes, (
                f"o preset Navegação perdeu {esperada!r}: a cura da loja não "
                "pode levar junto o que o perfil existe para casar."
            )

    @pytest.mark.parametrize("classe", ["steam", "Steam"])
    def test_a_regua_reconhece_as_duas_grafias(self, classe: str) -> None:
        """Guarda do instrumento: uma régua cega passaria verde para sempre.

        Se ``e_janela_do_cliente_steam`` parar de reconhecer estas grafias, o
        teste acima vira tautologia — verde porque não olha, não porque está
        curado.
        """
        assert e_janela_do_cliente_steam(classe), (
            f"a régua do produto não reconhece {classe!r} como janela do "
            "cliente Steam. Enquanto ela não reconhecer, o portão desta "
            "suíte está VERDE sem medir nada."
        )
