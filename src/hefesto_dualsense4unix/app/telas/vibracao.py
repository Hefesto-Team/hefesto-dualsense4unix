"""Aba 05 · Vibração — o adaptador: o que a tela recebe e o que ela manda.

A página é ``src/hefesto_dualsense4unix/interface/paginas/05-vibracao.html``, aprovada por ela com
elogio literal
(``_ferramentas/CORRECOES-DELA.md:39``). Este módulo é o outro lado dela: pega o
``daemon.state_full`` e devolve **um pacote por tique** — nunca uma chamada por
valor —, e traduz de volta o gesto que a página mandar.

Ele não abre janela, não importa ``gi`` e não fala IPC. Quem faz isso é quem
chama (hoje o piloto ``src/hefesto_dualsense4unix/interface/vibracao_viva.py``; amanhã o
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

#: O degrau que NÃO tem multiplicador MEDIDO, e por quê.
#:
#: Ele escala pela BATERIA em ``core.rumble._effective_mult`` (>50% → 1,0 ·
#: 20-50% → 0,7 · <20% → 0,3) e **nunca amplifica**. O 1,0 que ele tem em
#: :func:`_escada` não é um degrau medido: é o TETO dele, onde o deslizador
#: para — a palavra é do comentário de ``rumble_actions._POLICY_MULT:67-69``.
#:
#: FICA ESCRITO porque a ordem dos quatro na tela não sai de um ``dict``: ele é
#: o último, e é o único cuja posição não vem do valor.
FORCA_SEM_MULTIPLICADOR = "auto"


def _escada() -> dict[str, float]:
    """A ESCADA DOS QUATRO DEGRAUS, lida da única cópia autorizada em ``app/``.

    **CORRIGIDO EM 02/09/2026, e o defeito era o `auto`.** Estas três funções
    liam ``daemon.subsystems.rumble.RUMBLE_POLICY_MULT``, que tem TRÊS chaves;
    a tela tem QUATRO botões. Com o degrau em ``Auto`` e o orçamento da mesa em
    ``Economia``, a janela estável escreve *"100% · limitado a 30% pelo
    orçamento"* e esta aba **não dizia nada** — medido lado a lado, uma
    divergência em dez combinações de degrau e orçamento.

    ``rumble_actions._POLICY_MULT`` é ``{**RUMBLE_POLICY_MULT, "auto": 1.0}`` e
    o comentário de ``rumble_actions.py:402`` o chama, por escrito, de *"a única
    cópia autorizada em ``app/``"*. Há portão que vigia isso por varredura —
    ``test_orcamento_dono_unico_do_valor_efetivo.
    test_nenhum_modulo_de_app_recalcula_a_escada`` reprova a escada do daemon
    INDEXADA em qualquer arquivo de ``app/``, e este módulo o deixava
    **VERMELHO** em duas linhas desde que nasceu (:74 e :87 no ``dev``
    ``64644c5e``; nenhum dos 30 portões o via, porque ele é teste de suíte).

    O import é tardio porque ``rumble_actions`` puxa ``gi``/``Gtk`` no topo: uma
    régua que só pergunte o teto da barra não carrega a janela inteira.
    """
    from hefesto_dualsense4unix.app.actions.rumble_actions import _POLICY_MULT

    return _POLICY_MULT


def teto_da_barra() -> int:
    """O 100% da barra "Personalizado", em pontos percentuais (hoje: 150).

    Ela para no Máximo, e o Máximo é do produto. Decisão dela, 27/08 — *"não
    passa dele"*.

    Era o literal ``150`` no gerador. Derivá-lo da :func:`_escada` é o que
    impede a barra de prometer um teto que o daemon já não
    pratica  (noqa-acento: verbo praticar, correto sem acento). Este número
    **já esteve errado pelo dobro** na dica desta aba (dizia 60% para o
    Economia) e nenhuma régua o via, porque estava digitado dos dois lados.
    """
    return round(_escada()["max"] * 100)


def degraus_da_forca() -> tuple[str, ...]:
    """As chaves dos quatro degraus, na ordem da tela — do produto, não daqui.

    A ordem é a do desenho: do mais fraco ao mais forte, e o
    :data:`FORCA_SEM_MULTIPLICADOR` por último. O ``auto`` **não** entra pelo
    valor — o 1,0 dele empataria com o ``balanceado`` e a ordem dos botões
    passaria a depender de qual chave o ``dict`` devolvesse primeiro.
    """
    escada = _escada()
    return tuple(sorted(
        escada, key=lambda k: (k == FORCA_SEM_MULTIPLICADOR, escada[k])
    ))


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
    "mais `rumble_active_uniq` (`daemon/ipc_handlers.py:4561-4562`). Quatro "
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
    # FATO SUBSTITUÍDO EM 03/09/2026, e quem o derrubou foi ELA, em uma linha:
    # *"O parar é sobre o teste."* Esta célula dizia "sem antídoto nesta tela",
    # e a frase mandou-me concluir que o Parar deixava o controle mudo no jogo
    # sem caminho de volta — cheguei a apresentar isso a ela como armadilha de
    # mão única. NÃO É, e não é desde a cura que juntou os dois passos:
    # `a05_vibracao.parar` chama `rumble_stop_checked()` E `rumble_passthrough
    # (True)` na mesma função. O que na janela estável são DOIS botões, aqui é
    # um só — e a dica publicada já dizia isso com todas as letras: *"Parar
    # corta a vibração dele agora e devolve a mão ao jogo"*.
    #
    # A NOTA VELHA CUSTOU CARO justamente por descrever um estado que a cura já
    # tinha desfeito: eu li a prosa, não o ato. É a forma que esta casa
    # persegue, aparecendo do lado de dentro de uma tabela de donos.
    "parar": "rumble.stop pela ponte `app/ipc_bridge.rumble_stop_checked` E "
    "`rumble_passthrough(True)` na sequência — os DOIS passos que a janela "
    "estável separa em dois botões. Corta a vibração daquele controle agora e "
    "devolve a mão ao jogo, que é o que a dica publicada promete. Global no "
    "primeiro passo; o alvo é mirado antes por `_mirar`.",
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

    **E O ``pedido_de_vibracao_fresco`` NÃO ENTRA AQUI — a razão certa, 02/09.**
    A razão que circulou era falsa: *"ele é consultado por dentro do
    ``motores_no_fisico``"*. Não é — li o corpo (``controller_card.py:1511-1541``):
    o freio dele é próprio (``rumble_no_fisico_ha_s > ATIVIDADE_FRESCA_S``), e
    quem põe os dois em série é o CHAMADOR, ``estado_do_recurso`` (``:1719``
    pergunta *"o jogo PEDIU?"*, e só então ``:1721`` pergunta *"chegou aos
    motores?"*).

    A razão que sobra é de assunto, e é esta: lá a pergunta é uma SITUAÇÃO
    ("chegando" contra "parou") e o pedido do jogo é o que a separa; aqui a pergunta
    é um NÚMERO — *"quanto foi ao motor agora?"* —, e a fonte dele é o par
    físico. Um controle em que o jogo parou de pedir já responde ``None`` pelo
    freio de ``motores_no_fisico``; acrescentar o segundo juiz não mudaria uma
    coluna e criaria duas verdades sobre o mesmo pixel.
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
    pct = None if not isinstance(aplicado, (int, float)) else round(float(aplicado) * 100)
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


#: OS TRÊS TONS DA LINHA DE ESTADO, um por token de cor da janela estável.
#:
#: **CORRIGIDO EM 02/09/2026: eram DOIS, e a janela GTK usa TRÊS neste card.**
#: O comentário anterior dizia *"os dois tons ... são os mesmos da janela GTK"*,
#: e a quarta frase saía como ``diz`` — cinza. Lá ela é ciano, e o comentário
#: que a pinta explica por quê: *"a frase explica, não alarma"*.
#:
#: ==========  ===========================  ==================================
#: tom         cor na estável               qual frase
#: ==========  ===========================  ==================================
#: ``diz``     a cor normal do rótulo       ``texto_dos_pedidos_de_vibracao``
#: ``alerta``  ``#ffb86c`` (:1259, :545)    ``…do_alcance_da_intensidade`` e
#:                                          ``…do_teto_do_orcamento``
#: ``info``    ``#8be9fd`` (:608)           ``texto_de_onde_grava_e_onde_manda``
#: ==========  ===========================  ==================================
#:
#: Viaja o NOME, e a cor mora no CSS da aba — a mesma disciplina do
#: ``conta_cor``, que manda ``var(--green)`` em vez de um hexadecimal. Os três
#: tokens já existem no mockup (``--orange``, ``--cyan``, ``--texto-suave``).
DIZ = "diz"
ALERTA = "alerta"
INFO = "info"


def _pedido_da_politica(state: dict[str, Any]) -> float | None:
    """O multiplicador que esta aba está PEDINDO, ou ``None``.

    É a MESMA conta da janela estável, e agora é verdade: a linha de
    ``rumble_actions._pintar_a_linha_do_teto:537`` é
    ``custom_mult if policy == "custom" else _POLICY_MULT.get(policy)``, e esta
    é ela com o ``custom_mult`` vindo do ``state``. A escada sai da
    :func:`_escada`, que é a cópia autorizada — não uma segunda tabela.

    **O ``auto`` DIZ 100%, e o número é fixo.** O docstring anterior afirmava
    que ele *"responde ``None`` de propósito — o teto dele é móvel"*, e o
    ``None`` fazia esta aba calar onde a estável avisa. O móvel é o que o
    ``auto`` ENTREGA (escala pela bateria); o 1,0 é o TETO dele, que nunca
    amplifica — e a frase resultante fala do teto, não da entrega. Quem decide
    quando calar é ``texto_do_teto_do_orcamento``, e ele já cala nos quatro
    silêncios que documenta.

    ``None`` aqui é só *"degrau que não existe"*: política fora dos quatro
    (daemon velho, chave nova) ou ``custom`` sem multiplicador lido.
    """
    politica = str(state.get("rumble_policy") or "")
    if politica == "custom":
        aplicado = state.get("rumble_mult_applied")
        if isinstance(aplicado, bool) or not isinstance(aplicado, (int, float)):
            return None
        return float(aplicado)
    return _escada().get(politica)


def _orcamento_da_maquina() -> str | None:
    """A chave do orçamento GRAVADO, pelo dono dela; ``None`` = não sei.

    ``secao_orcamento.orcamento_em_vigor`` aceita ``host=None`` e cai no
    ``carregar_maquina()`` — é função de módulo, atravessa sem ``Gtk.Window``, e
    é a mesma que a janela estável consulta. **Não se reescreve a leitura do
    disco aqui**: quem sabe o que é "em vigor" (e por que o pendente do
    "Aplicar" NÃO conta) é aquele módulo, por escrito.

    O ``suppress`` é a diferença entre "não sei" e "quebrou a tela": esta linha
    é um AVISO, e um orçamento ilegível não pode derrubar o tique que pinta os
    dois motores.
    """
    import contextlib

    from hefesto_dualsense4unix.app.actions.config.secao_orcamento import (
        orcamento_em_vigor,
    )

    with contextlib.suppress(Exception):
        return orcamento_em_vigor()
    return None


def textos_do_estado(
    state: dict[str, Any], *, alvo: Any = None
) -> list[tuple[str, str]]:
    """A LINHA DE ESTADO da vibração: ``[(tom, frase), …]``, só o que tem a dizer.

    **O buraco que ela fecha, medido em 02/09/2026.** A janela estável mostra
    quatro avisos nesta aba e a interface nova mostrava ZERO — a tela nova tinha
    os dois motores, os quatro degraus e o "Testar", e nenhuma palavra sobre o
    que acontece com eles. As quatro frases já existiam, prontas, e ninguém as
    chamava:

    ==================================== =========================================
    o que a linha diz                    de quem é a frase
    ==================================== =========================================
    quantas vezes o jogo pediu vibração  ``rumble_actions.texto_dos_pedidos_de_vibracao``
    a intensidade não alcança o jogo     ``rumble_actions.texto_do_alcance_da_intensidade``
    o orçamento limitou o multiplicador  ``rumble_actions.texto_do_teto_do_orcamento``
    grava num lugar e manda em outro     ``rumble_actions.texto_de_onde_grava_e_onde_manda``
    ==================================== =========================================

    **NENHUMA FRASE NASCE AQUI.** Este módulo escolhe QUANDO perguntar e traduz
    a resposta para a forma que a tela consome; o texto tem dono, e o dono é o
    mesmo das duas telas. Duas cópias de um texto de tela divergem na primeira
    edição — esta casa já pagou por isso.

    **``None`` DE CADA UMA É "NÃO APARECE", nunca travessão.** O pintor troca
    vazio por ``—`` (``hefesto_vivo.py:118``), e um travessão numa linha de
    alerta afirmaria "não sei" onde a resposta é "não há o que avisar". Por isso
    esta função devolve uma LISTA do que existe, e não um dicionário de campos
    fixos: a linha que não se aplica não é apagada — ela **não é montada**.

    :param alvo: o :class:`~app.alvo_de_edicao.AlvoDeEdicao` desta tela. O padrão
        é ``TODOS``, e **é medição, não conveniência**: nesta aba a fita do topo
        nasce inerte (decisão dela, 28/08), não há controle escolhido, e o único
        clique que grava — o degrau de força — manda ``rumble.policy_set``, que
        **não leva endereço**. Não há override de peça sendo escrito, logo não há
        a divergência que aquela frase confessa, e um aviso permanente viraria
        ruído crônico — é o próprio contrato da função, na letra.

        A CHAMADA FICA MESMO ASSIM, e não é enfeite: no dia em que esta aba
        ganhar alvo por controle (``MIGRA-VIBRACAO-04``), quem passar o alvo
        certo aqui recebe a confissão pronta, sem ninguém redigir a frase de
        novo. Uma linha de tela que a aba deveria ter e não tem é exatamente o
        buraco que esta função fecha do outro lado.

    **O QUE ELA NÃO COBRE**, e fica dito: a tela nova afirma QUATRO forças, uma
    por coluna, e o produto tem UMA. Essa mentira é de outra natureza e já está
    declarada em :data:`SEM_FONTE` (``forca:por-controle``); nenhuma das quatro
    frases fala dela.
    """
    from hefesto_dualsense4unix.app.actions import rumble_actions as _ra
    from hefesto_dualsense4unix.app.alvo_de_edicao import AlvoDeEdicao, EstadoDoAlvo

    linhas: list[tuple[str, str]] = []
    pedidos = _ra.texto_dos_pedidos_de_vibracao(state)
    if pedidos:
        linhas.append((DIZ, pedidos))
    alcance = _ra.texto_do_alcance_da_intensidade(state)
    if alcance:
        linhas.append((ALERTA, alcance))
    teto = _ra.texto_do_teto_do_orcamento(
        _pedido_da_politica(state), _orcamento_da_maquina()
    )
    if teto:
        linhas.append((ALERTA, teto))
    onde = _ra.texto_de_onde_grava_e_onde_manda(
        alvo if alvo is not None else AlvoDeEdicao(estado=EstadoDoAlvo.TODOS)
    )
    if onde:
        linhas.append((INFO, onde))
    return linhas


def html_do_estado(linhas: list[tuple[str, str]]) -> str:
    """O miolo da linha de estado, em HTML. Lista vazia → string vazia.

    **UM SÓ EMISSOR PARA OS DOIS LADOS**, e é por isso que ele mora aqui e não
    no gerador nem no pacote: o desenho da bancada (``interface/aba05.py``) e a
    tela viva (``pacotes/a05_vibracao.py``) montam estas linhas do MESMO lugar.
    Dois emissores divergem no primeiro ajuste de classe, e aí o produto deixa
    de parecer o desenho — que é o defeito que a pasta ``novo-layout/`` custou.

    A STRING VAZIA É O PONTO: o CSS tem ``.vib-estado:empty{display:none}``, de
    modo que "não há o que avisar" some da tela em vez de virar travessão.

    O ``escape`` não é cerimônia: as frases vêm de ``rumble_actions`` e hoje
    nenhuma leva ``<`` ou ``&``, mas elas são texto de tela e mudam sem passar
    por aqui — o dia em que uma ganhar um ``&`` é o dia em que a linha some da
    tela sem uma palavra de erro.

    **AS DUAS FATIAS ESCAPAM DIFERENTE, e a diferença é o ponto — 02/09/2026.**

    ========================  =============  ==================================
    fatia                     ``quote``      por quê
    ========================  =============  ==================================
    ``tom``, em ``class="…"``  ``True``      é ATRIBUTO. Uma ``"`` ali FECHA o
                                             atributo e o resto do valor vira
                                             markup: é assim que um apóstrofo
                                             quebra a tela.
    ``frase``, entre spans     ``False``     é conteúdo de TEXTO. A entidade é
                                             desnecessária **e o navegador
                                             nunca a devolve**.
    ========================  =============  ==================================

    O ``quote=False`` no ``tom`` era o defeito: ele desligava o escape justo na
    fatia que precisa dele, e o argumento vinha com o comentário dizendo o
    contrário — *"isto aqui é conteúdo de TEXTO, nunca atributo"*. Hoje o
    ``tom`` só vale :data:`DIZ`/:data:`ALERTA`/:data:`INFO`, três constantes
    deste módulo; o escape é o que impede que a próxima classe de tom, vinda de
    um dado, saia do atributo.

    **E NO ``frase`` O ``quote=False`` É MEDIDO**, não gosto. Escrevendo em
    ``el.innerHTML`` e lendo de volta no WebKit::

        as frases de HOJE ......... volta igual: True   (aspas tipográficas “ ”)
        uma frase com & e < ....... volta igual: True
        uma frase com ASPA RETA ... volta igual: False
            emitido:   <span>clique &quot;Testar&quot;</span>
            devolvido: <span>clique "Testar"</span>

    O guarda do pintor é ``if (alvo && alvo.innerHTML !== html)``
    (``hefesto_vivo.py:213``). Com ``&quot;`` no conteúdo a comparação seria
    VERDADEIRA sempre: o bloco repintaria e contaria ``+1`` a cada tique, a
    2 Hz, para sempre — o defeito que o ramo ``SELECT`` do ``escrever()`` foi
    escrito para impedir, e o mesmo instrumento com que esta casa prova que um
    endereço existe. No ATRIBUTO isso não acontece: o navegador devolve a
    ``class`` já normalizada e o ``&quot;`` nunca chega ao ``innerHTML`` lido.
    """
    import html as _html

    return "".join(
        f'<div class="est {_html.escape(tom)}">'
        f'<span class="sinal">{"▲" if tom == ALERTA else "●"}</span>'
        f"<span>{_html.escape(frase, quote=False)}</span></div>"
        for tom, frase in linhas
    )


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
    pct = 0 if not isinstance(aplicado, (int, float)) else round(float(aplicado) * 100)
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
    chave = f'barra:{gesto.get("papel") or "?"}' if nome == "barra" else nome
    return chave, DONOS_DOS_GESTOS.get(chave, SEM_DONO)
