"""Aba Rumble: intensidade global (Economia/Balanceado/Máximo/Auto) + Testar motores.

FEAT-RUMBLE-POLICY-01: aba reestruturada em 2 cards:
  1. "Intensidade da vibração" — 4 GtkToggleButton agrupados + slider + label Auto.
  2. "Testar motores" — sliders de vibração leve/forte + botões Testar/Aplicar/Parar.

LEIGO-06: "política", "rumble", "weak"/"strong" e "throttle" saíram da TELA —
continuam sendo os nomes do IPC e do schema (`rumble.policy`, `policy="max"`),
que este módulo traduz na fronteira.

Política define multiplicador global aplicado pelo daemon sobre todo rumble,
inclusive passthrough de jogo (XInput virtual). Slider de intensidade ajusta
"custom" em 0-200% (mapeamento valor/100 nos dois sentidos).

HARM-19: o teto tem UM dono — ``profiles.schema.RUMBLE_CUSTOM_MULT_MAX``. Eram
três (2.0 no schema, 1.0 no handler ``rumble.policy_custom``, 200% no slider), e
de 101% em diante a usuária levava um erro de validação que esta aba nem
mostrava. Mexeu no teto? Mexa no schema — este slider é ``mult * 100``.

FEAT-RUMBLE-POLICY-PROFILE-01: cada escolha de política da usuária também é
gravada em ``self.draft.rumble`` — o "Salvar Perfil" do rodapé persiste no
perfil exatamente o que a aba mostra (aplicada de volta na ativação).
"""
# ruff: noqa: E402
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app.actions.jogar.painel import hefesto_ligado, modo_vivo
from hefesto_dualsense4unix.app.actions.mode_transition import (
    MODE_DESKTOP,
    MODE_GAMEPAD,
)
from hefesto_dualsense4unix.app.alvo_de_edicao import (
    AlvoDeEdicao,
    EstadoDoAlvo,
)
from hefesto_dualsense4unix.daemon.subsystems.rumble import (
    RUMBLE_POLICY_MULT,
    sem_dono_do_rumble,
)

_POLICY_MULT: dict[str, float] = {
    **RUMBLE_POLICY_MULT,
    "auto": 1.0,
}


_POLICY_LABEL: dict[str, str] = {
    "economia": "Economia",
    "balanceado": "Balanceado",
    "max": "Máximo",
    "auto": "Auto",
}

ROTULOS_DO_ORCAMENTO: dict[str, str] = dict(_POLICY_LABEL)


_ALCANCE_O_QUE_ACONTECE = "A intensidade não está chegando a jogo nenhum: "

_ALCANCE_O_QUE_SOBRA = " Aqui embaixo ela ainda vale."

_CAUSA_O_INTERRUPTOR_NAO_DIZ_LIGADO = (
    "falta o gamepad virtual, por onde ela passa. Ponha o Status em “Ligado” "
    "na aba Jogar."
)

_CAUSA_O_CAMINHO_E_A_NAVEGACAO = (
    "na Navegação o controle é teclado e mouse, não um gamepad. Troque o Modo "
    "na aba Jogar."
)

_CAUSA_O_GAMEPAD_VIRTUAL_NAO_SUBIU = (
    "o Status já está em “Ligado”, e o sistema não deixou o Hefesto criar o "
    "gamepad virtual."
)

_CAUSA_O_CAMINHO_E_DESCONHECIDO = (
    "o caminho de agora não tem gamepad virtual, e é por ele que ela passa."
)


def _causa_do_alcance_perdido(state: dict[str, Any]) -> str:
    """A segunda metade do aviso, perguntada a QUEM PINTA O STATUS DA ABA JOGAR.

    RECADO-VPAD-01 (17/09/2026), e o defeito é a terceira aparição do mesmo
    padrão nesta casa: **duas leituras paralelas da mesma pergunta**. A primeira
    foi a borda do `launch_env` contra esta tela (11/08, curada pelo
    `sem_dono_do_rumble` logo abaixo); a segunda, a tela contra o journal. Esta
    é entre esta linha e o **interruptor da aba Jogar**:

    ===============  ==========================================  ==============
    quem             pergunta                                    onde
    ===============  ==========================================  ==============
    este aviso       ``native_mode`` + ``rumble_ff.vpads``       aqui
    o interruptor    ``mode_of_state`` → ``MODOS_LIGADOS``      `jogar/painel`
    ===============  ==========================================  ==============

    **O QUE ELA VIU, em 17/09/2026:** o rodapé da aba Vibração mandando *"Ponha
    o Status em «Ligado» na aba Jogar"* com o Status **já aceso**. No journal
    dela, 1 min 59 s de ``rumble_sem_dono backends=[] emulacao=False`` enquanto
    o modo vivo era ``mouse_teclado`` — o ``desktop`` do produto, o chip
    «Navegação», que mora DENTRO do lado Ligado do interruptor.

    **E A INSTRUÇÃO NUNCA PODIA ESTAR CERTA**, medido: o quadrante
    ``sem_dono_do_rumble`` exige ``native=False``, e com ``native`` falso
    ``mode_of_state`` só devolve ``gamepad`` ou ``desktop`` — os DOIS membros de
    ``MODOS_LIGADOS``. Logo ``hefesto_ligado`` é ``True`` em **100% dos estados
    em que este aviso aparece**, e o único estado em que ele seria ``False`` (o
    nativo) é exatamente aquele em que o aviso não sai. A ordem de ligar era
    inalcançável-correta desde que nasceu, e nenhuma régua viu porque as réguas
    mediam o TEXTO.

    A cura é a mesma das outras duas: **um dono só para a pergunta**. Quem
    responde "o Hefesto está no meio?" é ``jogar.painel.hefesto_ligado``, o
    mesmo leitor que acende o interruptor; quem responde "por qual caminho" é
    ``jogar.painel.modo_vivo``. Esta função não tem uma linha de regra própria.

    Os três casos, na ordem em que a função pergunta:

    1. **o painel NÃO diz Ligado** — a ordem de ligar é legítima, e é a única
       posição em que ela pode sair sem contradizer o que ela está vendo;
    2. **Navegação** (``desktop``): o controle é teclado e mouse por escolha
       dela, e nesse caminho jogo nenhum recebe um gamepad. Não é defeito — é o
       modo funcionando —, então a frase NOMEIA o modo e diz por onde se troca,
       no molde da frase do nativo logo abaixo;
    3. **Ligado no caminho de jogo, e o gamepad virtual não existe**
       (``enabled=True`` com ``vpads=0``): é a falha TOTAL do VPAD-09 —
       ``make_virtual_pad`` devolveu ``None`` porque ``/dev/uhid`` **e**
       ``/dev/uinput`` estavam sem a ACL do ``uaccess`` (o daemon de sessão sobe
       no login e o logind aplica a ACL instantes depois;
       `daemon/subsystems/gamepad.py`, "VPAD-09 (falha TOTAL)"). Aqui o Status
       já está exatamente onde a instrução velha mandava pôr, e segui-la **nunca
       resolve**: a causa é a permissão do sistema, e é ela que a frase nomeia.

    **POR QUE O CASO 3 NÃO CONFESSA DÍVIDA NOSSA** (a régua é
    `scripts/check_a_tela_nao_confessa.py`): o sujeito da frase é o SISTEMA, não
    o Hefesto. "o sistema não deixou" é limite da máquina, da mesma família das
    frases que ela aprovou em 07/09 — e é o que a pessoa precisa saber para
    parar de repetir um gesto que não muda nada.

    **POR QUE O CASO 3 NÃO TRAZ O GESTO DE ATUALIZAR.** Ele seria o ponteiro
    certo (`utils/repo_files.FRASE_DE_ATUALIZAR`, o mesmo que o ``sem_device``
    do mouse interpola), mas não cabe: a frase mais curta dos dois gestos tem 41
    caracteres e levaria esta linha a ~200, contra o teto medido de uma sublinha
    da `.vib-estado` — e uma segunda sublinha aqui faz o quadro rolar e CORTA o
    fim do aviso, que foi o defeito de 02/09 que fez ela mandar encurtar. O
    ponteiro da aba Sistema está fora por decisão medida: a BG-NAV-01 (26/08)
    tirou exatamente esse ponteiro do bloqueio irmão do mouse porque os botões
    de lá não escrevem a regra udev do ``uinput`` — *ponteiro que não leva ao
    conserto é ponteiro errado*.

    **AS DUAS FRASES FORAM MEDIDAS NO WEBKIT**, não contadas em caracteres, por
    ``tests/unit/test_o_aviso_da_vibracao_cabe_na_aba.py`` — que passou a rodar
    nos DOIS estados por causa desta mudança. Na caixa de 1119 px da
    ``.vib-estado``: Navegação **989 px** (163 caracteres) e vpad-não-subiu
    **961 px** (164). A primeira volta desta cura escrevia *"…, e jogo nenhum
    vê um gamepad"* e mediu **1067 px**: cabia, com 52 px de folga contra os
    162 px da frase que ela aprovou em 02/09. Encurtou — folga de uma sublinha
    não é asseio, é o que separa o aviso de ser CORTADO pela borda do miolo na
    máquina dela.
    """
    if hefesto_ligado(state) is not True:
        return _CAUSA_O_INTERRUPTOR_NAO_DIZ_LIGADO
    caminho = modo_vivo(state)
    if caminho == MODE_DESKTOP:
        return _CAUSA_O_CAMINHO_E_A_NAVEGACAO
    if caminho == MODE_GAMEPAD:
        return _CAUSA_O_GAMEPAD_VIRTUAL_NAO_SUBIU
    return _CAUSA_O_CAMINHO_E_DESCONHECIDO


def texto_do_alcance_da_intensidade(state: dict[str, Any]) -> str | None:
    """O aviso de que a intensidade escolhida NÃO chega à vibração dos jogos.

    ``None`` = ela chega, ou não se sabe — e nos dois casos a linha não aparece.

    **O defeito**, medido no journal da máquina dela em 11/08/2026:
    ``launch_env_materializado ... backends=[] emulacao=False
    mascara=dualsense native=False``. Sem gamepad virtual **e** sem Conexão
    Nativa (Sony) ao mesmo tempo. Nesse estado o multiplicador dos quatro
    botões não age sobre a vibração do jogo, porque ele mora no caminho de
    saída do gamepad virtual — ``daemon.subsystems.gamepad.apply_game_rumble``,
    alcançado só pelo sink de ``make_primary_rumble_sink``. Sem gamepad
    virtual, esse sink nunca é criado. E a aba seguia mostrando
    Economia/Balanceado/Máximo como se valessem, sem uma palavra.

    **QUEM DECIDE O QUADRANTE NÃO É ESTA FUNÇÃO** — é
    ``daemon.subsystems.rumble.sem_dono_do_rumble``, o mesmo predicado que faz o
    daemon gritar ``rumble_sem_dono`` no journal, com a medição RUMBLE-SEM-DONO-01
    atrás dele. Por algumas horas em 11/08 houve dois critérios paralelos para o
    mesmo buraco (a borda olhava ``backends``, esta tela olhava ``vpads``), e
    dois critérios divergem na primeira mudança. O ``state_full`` não manda os
    NOMES dos backends, manda a CONTAGEM de gamepads virtuais; como o predicado
    só olha a verdade/falsidade da sequência, a contagem responde a mesma
    pergunta e a tradução acontece aqui, na fronteira.

    A ordem das perguntas é a mesma de ``texto_dos_pedidos_de_vibracao``, e
    pelo mesmo motivo:

    1. **O dado veio?** ``rumble_ff`` ausente, ou ``vpads`` que não é inteiro
       (daemon mais velho, resposta que não chegou): silêncio. Afirmar "não
       alcança" com o campo ausente seria inventar um defeito — "não sei" e
       "não chega" mandam caçar em lugares opostos;
    2. **É o quadrante sem dono?** Pergunta feita ao predicado. Se for, é a
       frase do defeito, com o gesto que o resolve;
    3. **Conexão Nativa (Sony) sem gamepad virtual?** A intensidade também não
       alcança, mas isso é o modo funcionando como deve — não é defeito, e por
       isso não é o quadrante. A frase é a que as outras telas já usam (*"o jogo
       fala direto com o controle"*), e não manda consertar nada;
    4. **Sobrou.** Há gamepad virtual e a intensidade alcança: nada a dizer.

    As duas frases terminam dizendo o que a intensidade AINDA faz — ela vale
    para a vibração fixada em "Testar motores", pelo caminho do
    ``reassert_rumble`` e do ``apply_rumble_policy``, que não dependem de
    gamepad virtual nenhum. Sem essa metade, o aviso viraria "esta parte da
    tela não serve para nada", que é falso.

    **A PRIMEIRA FRASE ENCURTOU — 02/09/2026, decisão dela, ciente do custo.**
    Ela tinha 211 caracteres, e na aba HTML ocupava 1072 px de 1072
    disponíveis: quebrava em DUAS sublinhas, o quadro passava a rolar 40 px e a
    segunda metade — *"que você fixar aqui embaixo."* — ficava CORTADA pela
    borda de baixo do miolo. Medido no WebKit da janela do produto (1180x757,
    ``interface/janela.TAMANHO_NA_TELA``), com a mesa dela e ``vpads == 0``.

    A frase de hoje tem 162 caracteres, ocupa 942 px e cabe em UMA sublinha. As
    quatro informações continuam lá: o que não está acontecendo, por quê, o que
    fazer, e o que a intensidade ainda faz. Ela escolheu encurtar em vez de
    deixar a aba rolar — *"uma frase, um dono"*: **esta função é a única cópia,
    e encurtar aqui muda a janela GTK junto**, de propósito. Escrever uma
    segunda versão para a tela nova é o defeito que esta casa passou o dia
    matando.
    """
    ff = state.get("rumble_ff")
    if not isinstance(ff, dict):
        return None
    vpads = ff.get("vpads")
    if not isinstance(vpads, int) or isinstance(vpads, bool):
        return None
    native = bool(state.get("native_mode"))
    backends = ("vpad",) * max(0, vpads)
    if sem_dono_do_rumble(native=native, backends=backends):
        # O QUE ADIOU A CURA CADUCOU. O comentário de 03/09 dizia que a frase
        # (`data-gesto="hefesto"`, `data-modo="gamepad"` no `Ligado`) — e é
        return (
            _ALCANCE_O_QUE_ACONTECE
            + _causa_do_alcance_perdido(state)
            + _ALCANCE_O_QUE_SOBRA
        )
    if vpads == 0 and native:
        return (
            "Conexão Nativa (Sony): o jogo fala direto com o controle, e a "
            "intensidade acima não passa por ele. Enquanto o modo estiver "
            "ligado, fixar vibração aqui embaixo também não chega ao motor — "
            "quem manda nele é o jogo."
        )
    return None


def texto_do_teto_do_orcamento(
    pedido: float | None, orcamento: str | None
) -> str | None:
    """A linha *"150% · limitado a 30% pelo orçamento"*, ou ``None``.

    CONFIG-05 (22/08/2026), e ela é a metade visível da invariante **teto, não
    troca**: o orçamento CALCULA, a aba de origem só EXIBE. Nada aqui reescreve
    a escolha dela — os quatro botões seguem afundando onde ela os pôs, o
    deslizador segue mostrando o número que ela escolheu, e voltar o orçamento
    para Balanceado devolve tudo sem um clique a mais. Espelhar estado entre
    abas é a classe de defeito que a `ABAS-01` curou, e esta linha é o formato
    que não a repete.

    ``None`` = **a linha não aparece**, e são quatro os silêncios, na ordem em
    que a função pergunta. A disciplina é a do
    :func:`texto_do_alcance_da_intensidade` acima, palavra por palavra: *"não
    sei" e "não chega" mandam caçar em lugares opostos*.

    1. **Ninguém declarou orçamento** (``orcamento is None``). Afirmar um teto
       aqui seria inventar um limite que o daemon não impõe.
    2. **O orçamento não impõe teto** — ``balanceado``, ``max``, e também o
       ``auto``, cujo teto é MÓVEL: ele muda a cada tique com a bateria, e a
       casa já decidiu não prometer número móvel na tela
       (`profiles/manager.py:1818-1820`). Um "limitado a 70%" que vira 30% no
       minuto seguinte ensina a desconfiar da tela inteira.
    3. **Não se sabe o que a aba está pedindo** (``pedido is None``): política
       fora dos degraus conhecidos, deslizador ainda não lido.
    4. **O teto não morde** (``pedido <= teto``): o número que a aba mostra é
       exatamente o que chega ao controle, e dizer "limitado" seria falso.

    O percentual do teto sai de :func:`core.rumble.teto_do_orcamento`, que o
    deriva de ``RUMBLE_POLICY_MULT``. Esta aba não recalcula degrau nenhum: a
    única cópia autorizada em ``app/`` é o ``_POLICY_MULT`` do topo deste
    arquivo, e há teste que vigia isso por grep.
    """
    from hefesto_dualsense4unix.core.rumble import teto_do_orcamento

    if pedido is None:
        return None
    teto = teto_do_orcamento(orcamento)
    if teto is None or pedido <= teto:
        return None
    return (
        f"{round(pedido * 100)}% · limitado a {round(teto * 100)}% pelo orçamento"
    )


TEXTO_ONDE_GRAVA_E_ONDE_MANDA = (
    "Com um controle escolhido: a intensidade acima vale agora para todos os "
    "controles ligados — só o que você salvar no perfil fica deste controle."
)


def texto_de_onde_grava_e_onde_manda(alvo: AlvoDeEdicao) -> str | None:
    """O aviso de alcance do GESTO; ``None`` = não há divergência a confessar."""
    if alvo.estado is EstadoDoAlvo.CONTROLE:
        return TEXTO_ONDE_GRAVA_E_ONDE_MANDA
    return None


def _inteiro(valor: Any) -> int | None:
    """O inteiro do payload, ou ``None`` quando o campo não veio (daemon velho)."""
    if isinstance(valor, int) and not isinstance(valor, bool):
        return valor
    return None


