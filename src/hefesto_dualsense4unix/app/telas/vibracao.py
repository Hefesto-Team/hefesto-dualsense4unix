"""Aba 05 · Vibração — o adaptador: o que a tela recebe e o que ela manda.

A página é ``novo-layout/05-vibracao.html``, aprovada por ela com elogio literal
(``_ferramentas/CORRECOES-DELA.md:39``). Este módulo é o outro lado dela: pega o
``daemon.state_full`` e devolve **um pacote por tique** — nunca uma chamada por
valor —, e traduz de volta o gesto que a página mandar.

Ele não abre janela, não importa ``gi`` e não fala IPC. Quem faz isso é quem
chama (hoje o piloto ``novo-layout/_ferramentas/vibracao_viva.py``; amanhã o
enxerto da ``MIGRA-VIBRACAO-01``).

O QUE ESTA ABA TEM DE FONTE, E O QUE NÃO TEM
--------------------------------------------
Medido em 29/08/2026 contra o ``state_full`` e contra o ``src/``. A regra é
uma: **o que não tem fonte fica declarado, nunca inventado.** Um número
plausível e falso é pior que um traço honesto, porque ela confia nele.

* **tem fonte, e é da MESA (um valor para os quatro):** o degrau de força
  (``rumble_policy``), o multiplicador aplicado (``rumble_mult_applied``), a
  trava (``rumble_active``) e o passthrough (``rumble_passthrough``);
* **tem fonte, e é POR CONTROLE:** o par que chegou aos motores agora
  (``rumble_ff.per_vpad[].rumble_no_fisico``), lido pelo
  ``controller_card.motores_no_fisico`` — que é quem sabe quando o par está
  velho demais para ser dito;
* **NÃO TEM FONTE:** os oito interruptores de lado. Ver :data:`SEM_FONTE`.

A tela mostra QUATRO colunas com quatro forças; o produto tem UMA. Pintar o
valor global nas quatro é a verdade de hoje, e a coluna que mostra o mesmo
número quatro vezes é a tela dizendo isso — a força com endereço é a
``MIGRA-VIBRACAO-04``, e ela muda o daemon, não esta conta.
"""
from __future__ import annotations

from typing import Any

#: A tradução do lado da tela para o motor do código, e ela tem UM dono: este.
#:
#: ``e``/``d`` é a língua dela (esquerdo/direito) e é o que viaja no ``data-lado``
#: do HTML; ``weak``/``strong`` é contrato de código e nunca entra na página.
#:
#: **O par é medido, e é o contrário do que o nome sugere:** ``strong`` é o
#: motor ESQUERDO (``common[3]``) e ``weak`` é o DIREITO (``common[2]``) —
#: ``docs/protocol/dualsense-referencia-canonica.md:303-315``, com a medição em
#: que um ``EV_FF`` no esquerdo saiu no direito. Escrever isto em dois lugares é
#: como a inversão entra: aqui é um só.
LADO_PARA_MOTOR: dict[str, str] = {"e": "strong", "d": "weak"}

#: O degrau que NÃO tem multiplicador fixo, e por quê.
#:
#: ``RUMBLE_POLICY_MULT`` tem TRÊS entradas (economia, balanceado, max) e a tela
#: tem QUATRO degraus. O quarto é o ``auto``, e a ausência dele na tabela não é
#: esquecimento: ele escala pela BATERIA em ``core.rumble._effective_mult``
#: (>50% → 1,0 · 20-50% → 0,7 · <20% → 0,3) e **nunca amplifica**.
#:
#: FICA ESCRITO porque a ``MIGRA-VIBRACAO-02`` manda a régua exigir que os
#: quatro degraus sejam ``set(RUMBLE_POLICY_MULT)`` — e são três mais um.
FORCA_SEM_MULTIPLICADOR = "auto"

def teto_da_barra() -> int:
    """O 100% da barra "Personalizado", em pontos percentuais (hoje: 150).

    Ela para no Máximo, e o Máximo é do produto. Decisão dela, 27/08 — *"não
    passa dele"*.

    Era o literal ``150`` no gerador. Derivá-lo do ``RUMBLE_POLICY_MULT`` é o
    que impede a barra de prometer um teto que o daemon já não pratica: este
    número **já esteve errado pelo dobro** na dica desta aba (dizia 60% para o
    Economia) e nenhuma régua o via, porque estava digitado dos dois lados.
    """
    from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT

    return int(round(RUMBLE_POLICY_MULT["max"] * 100))


def degraus_da_forca() -> tuple[str, ...]:
    """As chaves dos quatro degraus, na ordem da tela — do produto, não daqui.

    As três primeiras saem de ``RUMBLE_POLICY_MULT``; a quarta é o
    :data:`FORCA_SEM_MULTIPLICADOR`. A ordem é a do desenho (do mais fraco ao
    mais forte, e o ``auto`` por último), e ela é fixada aqui porque um
    ``dict`` do produto não promete ordem de tela.
    """
    from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT

    por_forca = sorted(RUMBLE_POLICY_MULT, key=lambda k: RUMBLE_POLICY_MULT[k])
    return (*por_forca, FORCA_SEM_MULTIPLICADOR)


#: O QUE A TELA MOSTRA E O PRODUTO NÃO SABE RESPONDER. Cada linha diz onde o
#: caminho se perde e o que o fecha — é dívida com endereço, não lápide calada.
SEM_FONTE: dict[str, str] = {
    "lado:ligado": "NÃO EXISTE EM LINHA NENHUMA. Não há campo de habilitar motor "
    "por lado em `profiles/schema.py`, nem método de IPC, nem chave no "
    "`state_full`: o produto liga e desliga a vibração INTEIRA de um controle, "
    "nunca um punho. Os oito interruptores desta tela são desenho. "
    "Fecha: MIGRA-VIBRACAO-06.",
    "forca:por-controle": "O degrau é da MESA. `daemon.config.rumble_policy` é um "
    "campo só, lido por três rotas (`ipc_rumble_policy.apply_rumble_policy`, "
    "`subsystems/rumble.reassert_rumble` e `subsystems/gamepad._game_rumble_mult`). "
    "As quatro colunas mostram o MESMO valor porque é o que existe. "
    "Fecha: MIGRA-VIBRACAO-04.",
    "trava:por-controle": "A trava é UMA para a mesa — `daemon_cfg.rumble_active` "
    "mais `rumble_active_uniq` (`daemon/ipc_handlers.py:4214-4215`). Quatro "
    "'Parar' sobre uma trava só: parar o P2 apaga a vibração do P1. "
    "Fecha: MIGRA-VIBRACAO-05.",
    "estado:da-vibracao": "O produto de hoje tem uma LINHA DE ESTADO da vibração e "
    "um aviso de teto do orçamento (`rumble_state_label`, `rumble_policy_aviso` "
    "no `gui/main.glade`); o desenho aprovado não tem onde pô-los. "
    "Fecha: MIGRA-VIBRACAO-08.",
}

#: O DONO REAL DE CADA GESTO, num lugar só. Enquanto a aba está sendo avaliada
#: por ela, nenhum é chamado: o clique chega, é registrado e ECOA. Um gesto que
#: grave sem ela mandar é dano, e um que mande byte ao aparelho é pior.
DONOS_DOS_GESTOS: dict[str, str] = {
    "forca": "rumble.policy_set {policy} pela ponte `app/ipc_bridge."
    "rumble_policy_set_checked` — a ÚNICA porta desde 26/08/2026. É GLOBAL: o "
    "handler não aceita `uniq` (`daemon/ipc_handlers.py:4452`). E `auto` por "
    "unidade é RECUSADO pelo esquema, com validador e mensagem dedicados "
    "(`profiles/schema.py:798-811`): ele escala pela bateria do controle "
    "PRIMÁRIO, então guardá-lo por peça faria duas escalarem pela bateria da "
    "mesma.",
    "barra:forca": "rumble.policy_custom {mult} pela ponte `app/ipc_bridge."
    "rumble_policy_custom`. Global, e o teto do esquema é "
    "`RUMBLE_CUSTOM_MULT_MAX` = 2,0 (`profiles/schema.py:76`) — maior que os "
    "150% que esta barra desenha, e baixá-lo para 1,5 é decisão dela.",
    "barra:motor": "rumble.set {weak, strong} pela ponte `app/ipc_bridge."
    "rumble_set_checked`. O par é da MESA, e os dois valores viajam JUNTOS: não "
    "há como mandar um lado só.",
    "lado": "SEM DONO — ver SEM_FONTE['lado:ligado'].",
    "testar": "rumble.set {weak, strong} e, meio segundo depois, rumble.stop — é "
    "o que o `rumble_test_500ms` do produto faz hoje. Global.",
    "parar": "rumble.stop pela ponte `app/ipc_bridge.rumble_stop_checked`. "
    "Global, e sem antídoto nesta tela: o botão 'Deixar o jogo controlar a "
    "vibração' (`rumble_actions.py:1092`) não existe em nenhum dos dez mockups, "
    "e o banner do cabeçalho manda clicar nele PELO NOME "
    "(`status_actions.py:2262`).",
}

#: O que se diz de um gesto sem linha na tabela. Era um `KeyError` no piloto da
#: Controles e derrubava a janela inteira — derrubar a tela dela para relatar um
#: dono desconhecido é o pior dos dois males.
SEM_DONO = ("SEM LINHA na tabela de donos — este gesto chegou de um endereço que "
            "o gerador não escreve. Nada foi aplicado.")

#: O traço do valor que não se sabe. Nunca um zero: zero é um valor que ela pode
#: ter escolhido, e confundir os dois é o defeito que a `MIGRA-VIBRACAO-01`
#: nomeia (`_read_scales` devolvendo `else 0` e o "Aplicar" mandando (0, 0)).
NAO_SEI = "—"

#: O fundo do trilho quando o lado está desligado ou o valor é desconhecido.
_ZERO = "0%"


def _inteiro(valor: Any) -> int | None:
    """Um inteiro do payload, ou ``None``. ``bool`` NÃO é inteiro aqui."""
    if isinstance(valor, bool) or not isinstance(valor, int):
        return None
    return valor


def motores_do_controle(entrada: dict[str, Any], state: dict[str, Any]) -> dict[str, int | None]:
    """``{"e": esquerdo, "d": direito}`` do que chegou aos motores AGORA.

    ``None`` num lado é *"nada a dizer"*, e são três respostas diferentes com a
    mesma cara — daemon antigo, nunca escreveu, ou escreveu há mais de
    ``ATIVIDADE_FRESCA_S``. Quem decide isso é o
    ``controller_card.motores_no_fisico``, e ele é o dono: um segundo juiz de
    "este número ainda vale" divergiria na primeira mudança do teto.

    O casamento controle → vpad também não se refaz aqui — ``_item_do_vpad``
    diz de si mesmo, por escrito, que é *"o dono único do casamento"*.
    """
    from hefesto_dualsense4unix.app.widgets.controller_card import (
        _item_do_vpad,
        motores_no_fisico,
    )

    item = _item_do_vpad(entrada, state)
    par = motores_no_fisico(item) if isinstance(item, dict) else None
    if par is None:
        return {"e": None, "d": None}
    weak, strong = par
    por_motor = {"weak": weak, "strong": strong}
    return {lado: por_motor[motor] for lado, motor in LADO_PARA_MOTOR.items()}


def _barra(valor: int | None, teto: int, sufixo: str = "") -> dict[str, str]:
    """Uma barra da tela: a largura do cheio e o número escrito ao lado."""
    if valor is None:
        return {"w": _ZERO, "n": NAO_SEI, "sabe": ""}
    largura = max(0.0, min(100.0, 100.0 * valor / teto))
    return {"w": f"{round(largura, 1)}%", "n": f"{valor}{sufixo}", "sabe": "1"}


def pacote_da_coluna(
    controle: dict[str, Any],
    entrada: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    """O que uma coluna recebe por tique.

    ``controle`` é o item de mesa (o que o gerador desenha); ``entrada`` é o
    controle cru do ``state_full``. Os dois porque a coluna diz duas coisas: a
    identidade, que é da mesa, e a vibração, que é do estado.

    ``controle["plastico"]`` é a cor JÁ RESOLVIDA (``monta.cor_da_zona`` sobre o
    colorway que o aparelho respondeu). Ela vem pronta, e não se resolve aqui,
    porque quem sabe traduzir colorway em cor é o gerador do desenho — este
    módulo é ``src/`` e não importa ``novo-layout/``, que é ``.gitignore:108``.
    """
    politica = str(state.get("rumble_policy") or "")
    aplicado = state.get("rumble_mult_applied")
    pct = None if not isinstance(aplicado, (int, float)) else int(round(float(aplicado) * 100))
    motores = motores_do_controle(entrada, state)
    return {
        # A identidade é a MESMA gramática das dez abas (26/08): P# • plástico •
        # transporte. Ela é assada no HTML pela remontagem e repintada aqui
        # porque a cor chega DEPOIS — é uma pergunta ao aparelho, em thread.
        "identidade": (
            f'P{controle["jogador"]} <span class="pt">•</span> {controle["nome"]}'
            f' <span class="pt">•</span> {controle["via"]}'
        ),
        "plastico": controle.get("plastico") or "",
        "forca": politica,
        "pct": _barra(pct, teto_da_barra(), sufixo="%"),
        "motores": {lado: _barra(motores[lado], 255) for lado in LADO_PARA_MOTOR},
        # O DESENHO TREME POR LADO: um lado acende quando o motor daquele punho
        # recebeu força AGORA. `None` (nada a dizer) apaga — nunca acende, que
        # seria a tela afirmando um tremor que ninguém mediu.
        "treme": {lado: bool(motores[lado]) for lado in LADO_PARA_MOTOR},
    }


def pacote_da_mesa(
    state: dict[str, Any],
    mesa: list[dict[str, Any]],
    conectados: list[dict[str, Any]],
    *,
    contagem: tuple[str, str] = ("", ""),
) -> dict[str, Any]:
    """UMA chamada por tique, com tudo o que mudou. Nunca uma por valor.

    Com 14 valores por coluna e quatro colunas na mesa, uma chamada por valor
    seriam 560 travessias de fronteira por segundo.
    """
    por_uniq = {str(e.get("uniq") or ""): e for e in conectados}
    colunas = {
        c["uniq"]: pacote_da_coluna(c, por_uniq.get(c["uniq"], {}), state)
        for c in mesa
        if c["uniq"] in por_uniq
    }
    conta, conta_b = contagem
    return {
        "conta": conta,
        "conta_b": conta_b,
        "conta_cor": "var(--green)",
        "bolinha": "●",
        "perfil": str(state.get("active_profile") or NAO_SEI),
        "colunas": colunas,
    }


def estado_da_coluna(entrada: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    """O estado no formato que ``aba05._coluna`` desenha, para a REMONTAGEM.

    A remontagem monta o HTML da coluna pelo gerador do mockup — nunca por HTML
    escrito aqui. O gerador fala ``{"forca", "pct", "esq", "dir"}``, e esta é a
    tradução; sem ela a coluna viva nasceria da cena estática do mockup e a
    primeira pintura teria de corrigir tudo.

    Os interruptores nascem LIGADOS porque não há o que os desligue: o produto
    não tem lado desligável (:data:`SEM_FONTE`), e desenhá-los apagados seria
    afirmar um estado que ninguém mediu.
    """
    politica = str(state.get("rumble_policy") or "")
    aplicado = state.get("rumble_mult_applied")
    pct = 0 if not isinstance(aplicado, (int, float)) else int(round(float(aplicado) * 100))
    motores = motores_do_controle(entrada, state)
    return {
        "forca": politica,
        "pct": pct,
        "esq": (True, motores["e"] or 0),
        "dir": (True, motores["d"] or 0),
    }


def gesto_do_clique(gesto: dict[str, Any]) -> tuple[str, str]:
    """``(chave, dono)`` de um gesto que a página mandou.

    A chave é o que a tabela :data:`DONOS_DOS_GESTOS` indexa; o dono é a frase
    que diz o que aconteceria se este gesto fosse aplicado — e enquanto ele não
    é, é a frase que impede alguém de achar que já é.
    """
    nome = str(gesto.get("gesto") or "")
    if nome == "barra":
        chave = f'barra:{gesto.get("papel") or "?"}'
    else:
        chave = nome
    return chave, DONOS_DOS_GESTOS.get(chave, SEM_DONO)
