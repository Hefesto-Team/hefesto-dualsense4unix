"""Aba 05 · Vibração — o adaptador: o que a tela recebe e o que ela manda.

A página é ``src/hefesto_dualsense4unix/interface/paginas/05-vibracao.html``, aprovada por ela com
elogio literal
(``_ferramentas/CORRECOES-DELA.md:39``). Este módulo é o outro lado dela: pega o
``daemon.state_full`` e devolve **um pacote por tique** — nunca uma chamada por
valor. O gesto que a página manda é do pacote da aba
(``interface/pacotes/a05_vibracao``), que usa as duas traduções daqui
(:data:`LADO_PARA_MOTOR` e :data:`MOTOR_PARA_BARRA`).

Ele não abre janela, não importa ``gi`` e não fala IPC. Quem faz isso é quem
chama: o pacote da aba, dentro do piloto único (``interface/hefesto_vivo.py``).

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
* **OS OITO INTERRUPTORES DE LADO GANHARAM FONTE — 14/09/2026.** Eles estavam
  em :data:`SEM_FONTE` desde que esta tela nasceu, com a razão certa: *não há
  campo de habilitar motor por lado*. A cura de 14/09 não criou o campo — ela
  leu o que já existia. Ordem dela, com o controle na mão: *"ele deveria ligar se
  > 0 no slicer dele"*. Aceso passou a ser a LEITURA da barra daquele motor, e o
  clique, o par que a escreve (`interface/pacotes/a05_vibracao`, chave
  `lado-{lado}` e gesto `lado`). A `MIGRA-VIBRACAO-06`, que fecharia isto criando
  o campo, deixa de ser necessária por este caminho.

A tela mostra QUATRO colunas com quatro forças; o produto tem UMA. Pintar o
valor global nas quatro é a verdade de hoje, e a coluna que mostra o mesmo
número quatro vezes é a tela dizendo isso — a força com endereço é a
``MIGRA-VIBRACAO-04``, e ela muda o daemon, não esta conta.
"""
from __future__ import annotations

from typing import Any

LADO_PARA_MOTOR: dict[str, str] = {"e": "strong", "d": "weak"}

MOTOR_PARA_BARRA: dict[str, str] = {"strong": "forte_pct", "weak": "fraco_pct"}

#: para — a palavra é do comentário de ``rumble_actions._POLICY_MULT:67-69``.
#:
#: FICA ESCRITO porque ele é o degrau da escada que NÃO é botão da tela: o
#: ``Auto`` saiu da aba em 05/09/2026, pela palavra dela (*"segue os três modos
#: sempre"*), e :func:`degraus_da_forca` o deixa de fora por este nome. A
#: escada continua com ele — a mesa em ``Auto`` é estado que o produto ainda
#: sabe dizer (:func:`_pedido_da_politica`).
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
    ele é a única cópia autorizada em ``app/``. Há portão que vigia isso por varredura —
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
    """O 100% da barra "Personalizado", em pontos percentuais (hoje: 150)."""
    return round(_escada()["max"] * 100)


def degraus_da_forca() -> tuple[str, ...]:
    """As chaves dos degraus que a tela oferece, na ordem dela — do produto."""
    escada = _escada()
    return tuple(sorted(
        (k for k in escada if k != FORCA_SEM_MULTIPLICADOR),
        key=lambda k: escada[k],
    ))


# botão "Devolver ao jogo" que não existia (``rumble_actions.
# BTN_GIVE_BACK_TO_GAME``, RUM-01). **O que muda é só o DONO**, e a razão é

#: quando o teto já cortou, e por isso nunca ensinou que o teto existe.
DICA_DO_TETO_DA_MESA = (
    "O Perfil de Bateria pode impor um teto: a escolha continua valendo, "
    "só não passa dele."
)

DICA_DOS_VALORES_QUE_PASSAM = (
    "Esses valores ainda passam pelo degrau da coluna."
)


SEM_FONTE: dict[str, str] = {
    "forca:por-controle": "O degrau é da MESA. `daemon.config.rumble_policy` é um "
    "campo só, lido por três rotas (`ipc_rumble_policy.apply_rumble_policy`, "
    "`subsystems/rumble.reassert_rumble` e `subsystems/gamepad._game_rumble_mult`). "
    "As quatro colunas mostram o MESMO valor porque é o que existe. "
    "Fecha: MIGRA-VIBRACAO-04.",
    "trava:por-controle": "A trava é UMA para a mesa — `daemon_cfg.rumble_active` "
    "mais `rumble_active_uniq` (`daemon/ipc_handlers.py:3709-3715`). Quatro "
    "'Parar' sobre uma trava só: parar o P2 apaga a vibração do P1. "
    "Fecha: MIGRA-VIBRACAO-05.",
    "estado:da-vibracao": "O produto de hoje tem uma LINHA DE ESTADO da vibração e "
    "um aviso de teto do orçamento (`rumble_state_label`, `rumble_policy_aviso` "
    "no `gui/main.glade`); o desenho aprovado não tem onde pô-los. "
    "Fecha: MIGRA-VIBRACAO-08.",
}

# própria recusa), e a tabela ficou descrevendo um estado que a cura desfez.

NAO_SEI = "—"

_ZERO = "0%"


def _inteiro(valor: Any) -> int | None:
    """Um inteiro do payload, ou ``None``. ``bool`` NÃO é inteiro aqui."""
    if isinstance(valor, bool) or not isinstance(valor, int):
        return None
    return valor


def motores_do_controle(entrada: dict[str, Any], state: dict[str, Any]) -> dict[str, int | None]:
    """``{"e": esquerdo, "d": direito}`` do que chegou aos motores AGORA."""
    from hefesto_dualsense4unix.interface.cartao_do_controle import (
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
        "identidade": (
            f'P{controle["jogador"]} <span class="pt">•</span> {controle["nome"]}'
            f' <span class="pt">•</span> {controle["via"]}'
        ),
        "plastico": controle.get("plastico") or "",
        "forca": politica,
        "pct": _barra(pct, teto_da_barra(), sufixo="%"),
        "motores": {lado: _barra(motores[lado], 255) for lado in LADO_PARA_MOTOR},
        "treme": {lado: bool(motores[lado]) for lado in LADO_PARA_MOTOR},
    }


def pacote_da_mesa(
    state: dict[str, Any],
    mesa: list[dict[str, Any]],
    conectados: list[dict[str, Any]],
    *,
    contagem: tuple[str, str] = ("", ""),
) -> dict[str, Any]:
    """UMA chamada por tique, com tudo o que mudou. Nunca uma por valor."""
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


#: mesma promessa sem caminho, e o ``portao_a_casa_sabe_e_o_produto_nao_faz``
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
    que acontece com eles. As frases já existiam, prontas, e ninguém as
    chamava:

    ==================================== =========================================
    o que a linha diz                    de quem é a frase
    ==================================== =========================================
    a intensidade não alcança o jogo     ``rumble_actions.texto_do_alcance_da_intensidade``
    o orçamento limitou o multiplicador  ``rumble_actions.texto_do_teto_do_orcamento``
    grava num lugar e manda em outro     ``rumble_actions.texto_de_onde_grava_e_onde_manda``
    ==================================== =========================================

    **ERAM QUATRO ATÉ 07/09/2026**, e a que saiu era a primeira — a contagem de
    pedidos do jogo.

    **NENHUMA FRASE NASCE AQUI.** Este módulo escolhe QUANDO perguntar e traduz
    a resposta para a forma que a tela consome; o texto tem dono, e o dono é o
    mesmo das duas telas. Duas cópias de um texto de tela divergem na primeira
    edição — esta casa já pagou por isso.

    **``None`` DE CADA UMA É "NÃO APARECE", nunca travessão.** O pintor troca
    vazio por ``—`` (``hefesto_vivo.py:61``), e um travessão numa linha de
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


# linha (`app/actions/rumble_actions.py`), com as suas próprias
# promessa pública sem caminho — é o que o `portao_a_casa_sabe_e_o_produto_
# ESTADO`: os dois gestos da aba terminam em `rumble_passthrough(True)`, de


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
    ``tom`` só vale :data:`ALERTA`/:data:`INFO`, duas constantes
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
    (``hefesto_vivo.py:789``). Com ``&quot;`` no conteúdo a comparação seria
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


# junto (ver a nota acima de `NAO_SEI`).
