"""O contrato MARCAR e APLICAR, escrito no disco — I12 da INÍCIO NÃO MENTE-01.

**O defeito:** hoje a aba Início **marca** a máscara e o rodapé aplica; a aba
Emulação **aplica na hora**; e o rodapé, no gesto seguinte, desfaz o clique da
Emulação em silêncio. O contrato existia na cabeça de quem escreveu e em
nenhum lugar do disco — e três abas o copiam por import de nome privado
(``app/widgets/painel_no_jogo.py`` importa ``_MODE_ITEMS``, ``_FLAVOR_ITEMS`` e
``RECONCILIAR_LABEL`` da aba Início).

Este módulo é o contrato virado dado. Ele **não tem função nenhuma**, e isso é
deliberado: um contrato que executa é um segundo caminho de execução, e o que
falta aqui não é comportamento — é uma declaração que o portão possa ler e que
quem chegar depois encontre antes de inventar um terceiro dono.

O QUE FICA DECIDIDO, E O QUE NÃO
---------------------------------

Decidido (é o que o código de hoje já faz, e o que a
`AGORA-E-DEPOIS-01` construiu em 08/08/2026 a pedido dela — *"talvez fosse
interessante isso aparecer somente quando clicarmos no botão final em aplicar,
o botão verde"*):

* **quem MARCA** são os seletores das abas: o clique guarda a escolha em
  ``_escolha_pendente`` e **não sai IPC nenhum**;
* **quem APLICA** é o rodapé, e só ele — é lá que a pergunta do relançamento
  acontece UMA vez, com a decisão dela completa, em vez de a cada clique de
  seletor.

**NÃO** decidido aqui, e é palavra dela (D-B do ``SPRINT_ORDER.md`` §0.9): a
redação de tela que acompanha a mudança, e o que fazer com a aba Emulação, que
hoje é a exceção declarada abaixo. Enquanto ela não decidir, a exceção fica
registrada com data — não apagada, e não normalizada.

O PREÇO DA EXCEÇÃO, MEDIDO
---------------------------

``app/actions/emulation_actions.py`` chama ``apply_mode`` direto (``:1337``),
ou seja **aplica na hora**. Não é descuido — foi a cura da HARM-01, que tirou
dali um ``gamepad.emulation.set`` CRU e o fez passar pela sequência completa da
transição. O que sobrou é que as duas abas mandam no mesmo valor por caminhos
diferentes, e a última a falar vence sem dizer que venceu.
"""
from __future__ import annotations

from typing import Final

# O vocabulário atravessa a fronteira de módulo POR AQUI, e não mais por nome
# privado. A lista-dona continua sendo a da aba Início — copiar qualquer uma
# delas criaria o segundo dono que o `test_vocabulario_das_quatro_superficies`
# existe para reprovar. O que este módulo acrescenta é o NOME PÚBLICO: quem
# importa daqui não precisa mais furar o `_` de outro módulo.
from hefesto_dualsense4unix.app.actions.home_actions import (
    _FLAVOR_ITEMS,
    _MODE_ITEMS,
    RECONCILIAR_LABEL,
)

#: Os dois gestos, nomeados. "Marcar" guarda a escolha; "aplicar" a leva à
#: máquina. Um seletor que faz os dois é o defeito 2 da OITO-DEFEITOS-01 (a
#: máscara perguntando a cada clique) de volta.
GESTO_MARCAR: Final[str] = "marcar"
GESTO_APLICAR: Final[str] = "aplicar"

#: A ÚNICA superfície da janela autorizada a APLICAR modo e máscara. Caminho
#: relativo a ``src/hefesto_dualsense4unix/``, porque é assim que o portão o lê.
SUPERFICIE_QUE_APLICA: Final[str] = "app/actions/footer_actions.py"

#: O mecanismo — não é superfície, é o caminho por onde a aplicação passa. Ele
#: monta o plano e dispara os IPCs; quem decide APLICAR é quem o chama.
MECANISMO_DA_TRANSICAO: Final[str] = "app/actions/mode_transition.py"

#: As superfícies que MARCAM: guardam a escolha dela e não disparam IPC.
SUPERFICIES_QUE_MARCAM: Final[tuple[str, ...]] = (
    "app/actions/home_actions.py",
)

#: As superfícies que aplicam HOJE e não deveriam, com a data e a razão.
#:
#: Este registro é o "antes" da onda, e ele existe para não ser esquecido: uma
#: exceção sem data envelhece calada, e uma exceção apagada vira norma. O
#: portão `test_home_contrato_marcar_e_aplicar.py` cobra as duas coisas — que
#: nenhuma superfície NOVA entre aqui, e que a que está aqui ainda aplique de
#: fato (se a Emulação parar de aplicar, a linha SAI, e o portão reprova
#: enquanto ela ficar).
EXCECOES_QUE_APLICAM_HOJE: Final[dict[str, str]] = {
    "app/actions/emulation_actions.py": (
        "MEDIDO em 24/08/2026 (§4/I12 da INÍCIO NÃO MENTE-01): a aba Emulação "
        "chama `apply_mode` no clique (`_apply_mode`, :1311-1337) — aplica na "
        "hora. Não é descuido: foi a cura da HARM-01, que tirou dali um "
        "`gamepad.emulation.set` CRU e o fez passar pela sequência completa da "
        "transição. O que sobrou é que duas abas mandam no MESMO valor por "
        "caminhos diferentes, e o rodapé desfaz o clique da Emulação em "
        "silêncio no gesto seguinte. "
        "O QUE A FECHA: a onda da aba Emulação, que a faz MARCAR como a "
        "Início. Não se fecha daqui: são duas abas, dois donos, e escolher por "
        "ela é o fato consumado que esta casa recusa."
    ),
}

#: Os três nomes que a aba "No jogo" (e quem mais precisar) importa. Aliases
#: públicos, mesmo objeto — nunca cópia.
ITENS_DE_MODO: Final = _MODE_ITEMS
ITENS_DE_MASCARA: Final = _FLAVOR_ITEMS
ROTULO_RECONCILIAR: Final[str] = RECONCILIAR_LABEL

__all__ = [
    "EXCECOES_QUE_APLICAM_HOJE",
    "GESTO_APLICAR",
    "GESTO_MARCAR",
    "ITENS_DE_MASCARA",
    "ITENS_DE_MODO",
    "MECANISMO_DA_TRANSICAO",
    "ROTULO_RECONCILIAR",
    "SUPERFICIES_QUE_MARCAM",
    "SUPERFICIE_QUE_APLICA",
]
