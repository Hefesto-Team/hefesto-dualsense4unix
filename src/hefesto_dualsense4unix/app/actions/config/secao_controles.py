"""Seção 1 da aba Configurações — um card por controle da mesa.

Aqui entra o que o aparelho não anuncia e o produto não deduz: o modo em que um
controle não-Sony foi ligado, o rótulo dos botões, e a cor do plástico quando a
leitura falha. Todo campo nasce em "não sei", e "não sei" é resposta válida.

TERRITÓRIO DE CONFIG-06. Quem trabalha nesta seção escreve AQUI — o título, a
dica e todo widget dela. O montador da aba (`mixin.py`) só cria a moldura e
chama `montar`; ele não sabe o que há dentro, e é assim que cinco seções
crescem sem se pisarem.

DE ONDE VEM CADA COISA NA TELA
-------------------------------

* **os controles adotados** — `daemon.state_full`, que é o único lugar onde o
  `player_slot` de um DualSense existe (`ipc_handlers.py:1842`); o
  `controller.list` devolve a lista sem ele;
* **os que o Hefesto só vê** — `controller.list {external: true}`, que já traz o
  `player_slot` deles resolvido pelo registro do daemon;
* **a cor do plástico** — lida DO APARELHO, pelos DOIS transportes, por
  `integrations/cor_do_plastico` (decisão T6). Antes desta leva a leitura vivia
  fora do aplicativo, em `scripts/ensaios/`, e toda linha "Cor:" nasceria em
  "Não sei" — inclusive nos controles no cabo, que o desenho mostra com a cor
  lida. **Quem decide se um nó pode responder é `cor_do_plastico`**, dono único
  do envelope de cada transporte — aqui não há `if` de barramento nenhum, e a
  razão está em :meth:`_PainelDosControles._perguntar_as_cores`;
* **o resto** — declaração dela, acumulada em `_maquina_pendente` e gravada
  pelo "Aplicar" do rodapé (`D-A4`: a aba é diferida, o clique só marca).

DUAS CHAMADAS, E NUNCA NUM TIQUE
---------------------------------

Os tiques desta casa são de 100 ms, 500 ms e 2 s. Enumerar o `/dev/input`
inteiro e sondar quem segura cada `hidraw` custa de 10 a 40 ms mais um
subprocesso (`ipc_handlers.py:449`), e nada disso muda entre dois quadros. A
leitura roda ao ENTRAR na aba, e só.
"""
from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.app.actions.config import secao_mesa
from hefesto_dualsense4unix.app.fala_do_mapa import formata_pt_br
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

TITULO = "Os controles"

DICA: str | None = (
    "A borda de cada card é a cor do plástico daquele controle. O anel roxo "
    "por dentro marca qual está selecionado no cabeçalho da janela."
)


COLUNAS = 3


DICA_MIC_SEM_ENDERECO = (
    "Este controle não tem endereço fixo, então o Hefesto não tem como guardar "
    "a quem esta ponte pertence."
)


def _numero(valor: float) -> str:
    """Uma casa decimal, com vírgula — é assim que ela lê número nesta casa.

    Delega ao DONO ÚNICO (`app/fala_do_mapa.formata_pt_br`) desde 26/08/2026.
    Até então era uma segunda implementação da mesma regra, e a saída idêntica
    é o que fazia ninguém notar: no dia em que uma delas mudasse de
    arredondamento, esta seção e a célula do mapa passariam a dizer números
    diferentes sobre o mesmo fato. O nome local fica porque as quatro chamadas
    abaixo o usam e ele diz o que faz nesta seção.
    """
    return formata_pt_br(valor)


def frase_da_capacidade_do_mic() -> str:
    """Quanto do rádio um microfone ocupa. DERIVADA, nunca digitada."""
    from hefesto_dualsense4unix.integrations.radio_da_mesa import (
        HZ_AUDIO_COM_MIC,
        HZ_INPUT_COM_MIC,
        HZ_INPUT_SEM_MIC,
        SLOTS_POR_SEGUNDO,
    )

    total = HZ_INPUT_COM_MIC + HZ_AUDIO_COM_MIC
    return (
        f"Com o microfone ligado, um controle no BT troca {_numero(HZ_INPUT_SEM_MIC)} "
        f"relatórios de entrada por segundo por {_numero(HZ_INPUT_COM_MIC)} mais "
        f"{_numero(HZ_AUDIO_COM_MIC)} quadros de áudio: {_numero(total)} das "
        f"{SLOTS_POR_SEGUNDO} fatias daquele adaptador. Quanto já está em uso "
        f'está na seção "{secao_mesa.TITULO}".'
    )


def _lista(valor: Any) -> list[dict[str, Any]]:
    if not isinstance(valor, list):
        return []
    return [item for item in valor if isinstance(item, dict)]


def _inteiro(valor: Any) -> int | None:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


