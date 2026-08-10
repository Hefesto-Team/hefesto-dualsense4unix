"""Aba "No jogo": o que está atravessando para o jogo, recurso por recurso.

O PEDIDO DELA (09/08/2026), literal, quando perguntou como validar giroscópio
e touchpad:

    *"eu sei que a aba status é uma coisa, mas isso converter em input seja
    via xbox ou dualsense ou nativo é outra"*

Ela está certa, e o produto não sabia responder. A aba Status mostra o controle
**FÍSICO** — os sticks tremem, o giroscópio pinta barras, o touchpad acende um
ponto. Nada disso diz o que o JOGO recebe: entre o controle e o jogo há um
gamepad virtual (nas duas máscaras) ou não há nada (na Conexão Nativa, em que o
jogo abre o controle físico direto). Para saber, ela tinha de abrir o testador
da Steam.

Esta aba é a resposta, e o trabalho aqui é quase todo de TELA: os números já
subiam no ``daemon.state_full`` (``rumble_ff.per_vpad``) e a REGRA que os lê já
existia — ela mora em :func:`controller_card.estado_do_recurso`, entregue pela
PAINEL-DA-VERDADE-01 e ampliada pela ORFAOS-QUE-VOLTAM-01 e pela
MOTOR-QUE-NAO-SE-VE-01. Este módulo **chama** aquela função; não reimplementa
nem uma linha dela.

POR QUE NÃO É UMA CÓPIA DA LINHA DO CARD
----------------------------------------

O card já mostra ``resumo_do_que_chega_ao_jogo`` — uma frase corrida, ótima
para o relance ("está tudo bem?") e ruim para o gesto que ela descreveu: trocar
a máscara na aba Início, aplicar, e conferir se **movimento** e **toque**
continuam atravessando. Numa frase corrida os recursos mudam de posição
conforme mudam de situação, e comparar antes/depois vira leitura de texto.

Aqui cada recurso tem LINHA FIXA, na mesma ordem, sempre — o que muda é só a
coluna da direita. Trocar a máscara e olhar duas vezes para o mesmo lugar é o
que fecha a pergunta dela em três minutos, sem terminal e sem a Steam.

A HONESTIDADE QUE ESTE MÓDULO TEM DE MANTER
-------------------------------------------

É a mesma da PAINEL-DA-VERDADE-01, e está herdada por construção, porque as
frases nascem da função de lá: nenhuma linha afirma que o JOGO consumiu o dado
— isso depende de qual biblioteca o jogo carregou (medido em 01/08: a
``libSDL2`` do Ubuntu não enumerava o gamepad virtual; a SDL3 que a Steam
distribui enumerava). O que se afirma é o que o daemon PODE saber: o dado saiu
daqui, e alguém escreveu de volta.

E onde não há dado, a tela **cala** em vez de escrever zero. Campo ausente
vira ``None`` lá dentro e some daqui.
"""
from __future__ import annotations

from typing import Any, Final, NamedTuple

# Três nomes "privados" atravessam a fronteira de módulo aqui — `_MODE_ITEMS`,
# `_FLAVOR_ITEMS` e `_NOME_NA_FRASE` —, e é deliberado: a alternativa é pior.
#
# `_NOME_NA_FRASE` é a lista-dona dos recursos e da ORDEM deles; `_MODE_ITEMS` e
# `_FLAVOR_ITEMS` são as listas-donas dos rótulos de modo e de máscara (o
# `test_vocabulario_das_quatro_superficies` chama a primeira de "frase-dona" com
# todas as letras). Copiar qualquer uma das três para cá criaria um SEGUNDO
# dono: no dia em que um rótulo mudasse na aba Início, esta aba continuaria
# dizendo o nome velho — em silêncio, que é como esta casa já perdeu um dia.
#
# Um `_` no começo do nome é convenção de módulo; um segundo dono de vocabulário
# é defeito medido. Entre os dois, escolhe-se o `_`.
from hefesto_dualsense4unix.app.actions.home_actions import (
    _FLAVOR_ITEMS,
    _MODE_ITEMS,
    RECONCILIAR_LABEL,
)
from hefesto_dualsense4unix.app.actions.mode_transition import (
    MODE_DESKTOP,
    MODE_GAMEPAD,
    MODE_NATIVE,
    mode_of_state,
)
from hefesto_dualsense4unix.app.widgets.controller_card import (
    _NOME_NA_FRASE,
    SITUACAO_CHEGANDO,
    SITUACAO_IMPOSSIVEL,
    SITUACAO_NATIVO,
    SITUACAO_NUNCA,
    SITUACAO_PARADO,
    estado_do_recurso,
    titulo_do_card,
)

#: Os recursos, na ordem em que a aba os lista. Vem da lista-dona do card.
RECURSOS: Final[tuple[str, ...]] = tuple(nome for nome, _rot in _NOME_NA_FRASE)

#: Recurso -> o nome dele na tela. Mesma fonte, mesmo texto que a linha do card.
NOME_DO_RECURSO: Final[dict[str, str]] = dict(_NOME_NA_FRASE)

#: Teto de largura de um painel, em px.
#:
#: Ele existe porque o conteúdo é uma tabela de duas colunas curtas: com a
#: janela maximizada dela (1920) e o teto elástico da página em 1400px, um
#: painel esticado desenharia uma moldura de 1400px em volta de ~430px de
#: tinta — a mesma "sobra que vira buraco" que a SOM-01 tirou do card.
#:
#: `width-request` é MÍNIMO no GTK3, nunca máximo; sozinho ele não segura nada.
#: Quem o transforma em teto de fato é o `halign=START` que vai junto — é o
#: idioma que esta casa já usa nas barras de gatilho e no giroscópio do card.
#: 700px é o número medido: a linha mais larga da tabela ("clique do touchpad"
#: + "no jogo agora (motores: 30/120)") pede ~430px, e o recado sem vpad — que
#: é a linha longa desta tela — quebra em duas antes disso.
LARGURA_PAINEL: Final[int] = 700

#: Situação -> a palavra que a coluna da direita usa.
#:
#: As três derivam do que a linha do card já escreve, no singular: ela agrupa
#: ("No jogo agora: ...", "pararam: ...", "sem pedido ainda: ...") porque diz
#: vários recursos de uma vez; aqui cada linha fala de um só. Nenhuma palavra
#: nova entrou — a regra da casa é que nome que não deriva do que já está na
#: tela é sinal de conceito errado.
PALAVRA_DA_SITUACAO: Final[dict[str, str]] = {
    SITUACAO_CHEGANDO: "no jogo agora",
    SITUACAO_PARADO: "parou",
    SITUACAO_NUNCA: "sem pedido ainda",
}

#: Situação -> cor do texto. Só DUAS situações ganham cor, e a escolha é de
#: significado, não de gosto:
#:
#: * **chegando** é a única que afirma alguma coisa boa -> verde;
#: * **parou** pede atenção (era para estar chegando e não está) -> amarelo;
#: * o resto é EXPLICAÇÃO, não defeito, e fica apagado: "sem pedido ainda" é o
#:   jogo não ter pedido, e "a máscara Xbox 360 não tem giroscópio" é a API do
#:   controle de Xbox, não avaria nossa. Pintar qualquer um dos dois de
#:   vermelho ensinaria ela a ver problema onde não há.
#:
#: **Por que markup e não classe de CSS**, que seria o desenho preferido desta
#: casa: medido nesta leva, a regra `.hefesto-dualsense4unix-window label` do
#: `theme.css` tem especificidade MAIOR que a de
#: `.hefesto-dualsense4unix-status-ok` — a classe existe, é aplicada e não pinta
#: nada (a primeira foto saiu com "no jogo agora" em branco). O `set_markup` com
#: `foreground` é o mesmo caminho que o `header_connection` já usa para o verde,
#: o laranja e o vermelho do estado do daemon. Os dois hex são os do `theme.css`
#: (`@green` e `@yellow`); mudou lá, muda aqui.
COR_DA_SITUACAO: Final[dict[str, str]] = {
    SITUACAO_CHEGANDO: "#50fa7b",
    SITUACAO_PARADO: "#f1fa8c",
}

#: PERFIL-MUDO-01: a cor do aviso do perfil que não entrou. É o MESMO amarelo do
#: "parou", e pela mesma razão: era para estar valendo e não está. Vermelho seria
#: exagero — o Hefesto continua funcionando, com o perfil errado.
COR_DO_AVISO_DE_PERFIL: Final[str] = "#f1fa8c"

#: As situações que ficam apagadas — as três que EXPLICAM em vez de acusar.
SITUACOES_APAGADAS: Final[frozenset[str]] = frozenset(
    {SITUACAO_NUNCA, SITUACAO_IMPOSSIVEL, SITUACAO_NATIVO}
)

#: As situações que só existem quando há um controle virtual DESTE controle
#: para medir. `IMPOSSIVEL` e `NATIVO` ficam de fora de propósito: as duas são
#: respostas que a função dá ANTES de olhar o vpad (a máscara Xbox apaga o
#: recurso; o Modo Nativo dispensa o vpad inteiro), e tomá-las como prova de
#: que há vpad faria a aba mostrar seis linhas medidas num controle que o jogo
#: não vê.
_SITUACOES_MEDIDAS: Final[frozenset[str]] = frozenset(
    {SITUACAO_CHEGANDO, SITUACAO_PARADO, SITUACAO_NUNCA}
)

#: O que a aba diz quando o Hefesto está desligado. Texto da aba Início
#: (`_render_home`, o caminho offline), pelo mesmo motivo dos rótulos: a mesma
#: situação não pode ter duas frases em duas abas.
TEXTO_OFFLINE: Final[str] = "O Hefesto está desligado."

#: E quando ele está ligado e não há controle nenhum na mesa. Idem — é a frase
#: que a aba Início já usa em `_render_home_controllers`.
TEXTO_SEM_CONTROLE: Final[str] = "Nenhum controle conectado."

#: Conexão Nativa (Sony): não há gamepad virtual, e a tela tem de DIZER isso.
#:
#: Ficar vazia seria pior que mentir — ela olharia uma aba morta e concluiria
#: que quebrou. E dizer "não chega nada" seria falso: no Nativo chega TUDO,
#: justamente porque não há intermediário. O que esta frase afirma é o único
#: fato que o daemon conhece com certeza: não existe controle virtual para
#: medir, porque o jogo abriu o aparelho de verdade.
#:
#: **A primeira redação desta frase foi reprovada por um portão desta casa**, e
#: a lição vale registrar: ela começava com "O Hefesto saiu da frente", que é a
#: construção que a medição DELA derrubou em 06/08/2026
#: (`test_a_frase_refutada_da_allowlist`). O portão está certo mesmo aqui, onde
#: o assunto é outro: a frase ensina que o produto inteiro se afasta, e quem lê
#: conclui que perde cor e gatilho. O que se diz agora é o mecanismo — não há
#: controle virtual —, que é verificável e não ensina nada errado.
TEXTO_NATIVO: Final[str] = (
    "Não há controle virtual nenhum neste modo: o jogo abre o controle físico "
    "e fala direto com ele. Movimento, toque, vibração e som saem do próprio "
    "DualSense, e por isso não há aqui o que medir."
)

#: "Controlar o PC": também não há gamepad virtual, e por outro motivo.
#:
#: A frase afirma o que sabemos (o que NÓS entregamos) e não o que não sabemos
#: (o que o jogo faz). "Nenhum jogo recebe nada" seria uma afirmação sobre o
#: mundo inteiro a partir de um campo do nosso payload.
TEXTO_DESKTOP: Final[str] = (
    "O controle está movendo o mouse e o teclado. Enquanto estiver assim, o "
    'Hefesto não entrega controle nenhum ao jogo — troque para "Jogar pelo '
    'Hefesto" na aba Início.'
)

#: E o terceiro caso sem vpad: o modo é "Jogar pelo Hefesto", mas ESTE controle
#: não tem um gamepad virtual casado com ele no `state_full`.
#:
#: Repare no que a frase NÃO diz: ela não culpa o co-op, não afirma que houve
#: erro e não promete que vai entrar. Diz o que se observa (o jogo não vê este
#: controle), diz o que costuma resolver sozinho (acabou de conectar) e aponta
#: o gesto que já existe na aba Início para o caso de não resolver.
TEXTO_SEM_VPAD: Final[str] = (
    "O jogo ainda não vê este controle. Se você acabou de conectá-lo, ele entra "
    f'sozinho em alguns segundos; se demorar, use "{RECONCILIAR_LABEL}" na aba '
    "Início."
)


class LinhaDoJogo(NamedTuple):
    """Uma linha da tabela: o recurso, o que dizer dele e como pintar.

    ``detalhe`` é o que a função-dona acrescentou ao nome do recurso — o
    ``(~158 Hz)`` do giroscópio e o ``(motores: 30/120)`` da vibração. Ele
    viaja separado do nome porque a coluna da esquerda é FIXA (é o que permite
    comparar antes e depois de trocar a máscara olhando o mesmo lugar) e o
    número é o que muda.
    """

    recurso: str
    nome: str
    situacao: str
    texto: str


def _detalhe(frase: str, nome: str) -> str:
    """O que sobra da frase da função-dona depois do nome do recurso.

    ``estado_do_recurso`` devolve ``"giroscópio (~158 Hz)"`` e
    ``"vibração (motores: 30/120)"`` — o nome mais um parêntese com o número
    medido. A coluna da esquerda mostra o nome; este resto vai para a direita.

    Se a frase deixar de começar pelo nome (mudança futura da função-dona),
    ela vai INTEIRA para a direita em vez de sumir: uma tela que perde
    informação em silêncio é o defeito que este projeto mais paga.
    """
    if frase == nome:
        return ""
    if frase.startswith(nome):
        return frase[len(nome) :].strip()
    return frase


def linhas_do_controle(
    entry: dict[str, Any], state_global: dict[str, Any]
) -> list[LinhaDoJogo]:
    """As linhas de UM controle; ``[]`` = não há o que afirmar sobre ele.

    Uma linha por recurso, na ordem de :data:`RECURSOS`, e nenhuma regra nova:
    quem decide entre chegando/parou/sem pedido/impossível/nativo é
    ``estado_do_recurso``, que é a dona única dessa decisão desde a
    PAINEL-DA-VERDADE-01. Recurso que devolve ``None`` (não há o que afirmar)
    não vira linha — a tela cala em vez de escrever zero.
    """
    linhas: list[LinhaDoJogo] = []
    for recurso in RECURSOS:
        estado = estado_do_recurso(recurso, entry, state_global)
        if estado is None:
            continue
        nome = NOME_DO_RECURSO[recurso]
        palavra = PALAVRA_DA_SITUACAO.get(estado.situacao)
        if palavra is None:
            # IMPOSSIVEL e NATIVO: a `frase` já É a explicação inteira ("a
            # máscara Xbox 360 não tem giroscópio"), e não o nome do recurso.
            texto = estado.frase
        else:
            detalhe = _detalhe(estado.frase, nome)
            texto = f"{palavra} {detalhe}" if detalhe else palavra
        linhas.append(LinhaDoJogo(recurso, nome, estado.situacao, texto))
    return linhas


def tem_controle_no_jogo(
    entry: dict[str, Any], state_global: dict[str, Any]
) -> bool:
    """True quando existe um gamepad virtual DESTE controle para medir.

    Derivado, e não um segundo dono: se ao menos um recurso chegou a uma
    situação MEDIDA (chegando/parou/sem pedido), é porque o casamento
    controle -> vpad de ``_item_do_vpad`` encontrou alguém. Perguntar
    diretamente ao ``per_vpad`` daqui seria repetir aquele casamento — e ele
    tem regra sutil (jogador 1 sem ``is_primary`` nunca casa) que já divergiu
    uma vez nesta casa quando teve duas implementações.
    """
    return any(
        linha.situacao in _SITUACOES_MEDIDAS
        for linha in linhas_do_controle(entry, state_global)
    )


def recado_do_controle(
    entry: dict[str, Any], state_global: dict[str, Any]
) -> str | None:
    """A frase que substitui as linhas; ``None`` = há linhas a mostrar.

    Os três casos sem gamepad virtual, e cada um com a sua frase — porque as
    três situações mandam agir em lugares diferentes:

    * **Conexão Nativa (Sony)** — não há nada nosso no meio, e está tudo certo;
    * **Controlar o PC** — o controle é mouse e teclado, e o gesto que muda
      isso está na aba Início;
    * **"Jogar pelo Hefesto" e mesmo assim sem vpad** — o único dos três que
      pode ser transitório.
    """
    if tem_controle_no_jogo(entry, state_global):
        return None
    modo = mode_of_state(state_global)
    if modo == MODE_NATIVE:
        return TEXTO_NATIVO
    if modo == MODE_DESKTOP:
        return TEXTO_DESKTOP
    return TEXTO_SEM_VPAD


def recado_global(state_global: dict[str, Any] | None) -> str | None:
    """A frase que responde pela JANELA inteira; ``None`` = é por controle.

    Dois dos três casos sem gamepad virtual não são fatos DE UM CONTROLE: na
    Conexão Nativa e no "Controlar o PC" não existe controle virtual para
    ninguém — o modo vale para a mesa inteira, e a explicação é uma só. Não
    confundir com a allowlist do Steam Input, em que a medição dela derrubou
    essa leitura pela metade (`test_a_frase_refutada_da_allowlist`): lá o
    produto entrega a entrada e MANTÉM a saída, e aqui o assunto é outro.
    Repetir a mesma explicação dentro de um painel por controle
    (medido na foto de 10/08: a frase do Nativo saiu duas vezes, palavra por
    palavra, com dois controles na mesa) não acrescenta informação nenhuma —
    acrescenta leitura.

    O terceiro caso — modo "Jogar pelo Hefesto" e mesmo assim sem vpad — fica
    de fora daqui de propósito: ele é fato de UM controle, e pode valer para um
    e não para o outro na mesma mesa.

    Sem daemon devolve ``None``: quem diz "O Hefesto está desligado." é a linha
    de contexto, e repetir a frase logo abaixo dela seria eco.
    """
    if not isinstance(state_global, dict):
        return None
    modo = mode_of_state(state_global)
    if modo == MODE_NATIVE:
        return TEXTO_NATIVO
    if modo == MODE_DESKTOP:
        return TEXTO_DESKTOP
    return None


def aviso_do_perfil(state_global: dict[str, Any] | None) -> str | None:
    """O perfil que ela escreveu PARA este jogo e que não entrou. ``None`` = nada a dizer.

    PERFIL-MUDO-01 (10/08/2026). O daemon manda as frases prontas (ele é quem
    tem os perfis do disco e a janela em foco); aqui só se decide se há o que
    mostrar e como juntar mais de uma. As frases vêm de
    `profiles.porque_nao_entrou`, e são factuais de propósito — dizem o que o
    perfil exigiu e o que o Hefesto viu, sem mandar apagar nada: quem escreveu o
    critério foi ela.

    O fecho ("Enquanto isso, vale o perfil ...") é o que transforma o aviso em
    resposta completa: sem ele a aba diria que um perfil não entrou e deixaria a
    pergunta óbvia — *então qual entrou?* — sem resposta na mesma tela. E o
    ``active_profile`` já viajava no estado desde sempre.

    Duas regras para o mesmo jogo são raras e possíveis (ela teve ``Pragmata`` e
    ``Pragmata2`` no disco em 01/08). Aparecem as duas, uma por linha: escolher
    uma para mostrar seria o produto decidindo qual das configurações dela
    importa.
    """
    if not isinstance(state_global, dict):
        return None
    achados = state_global.get("perfil_do_jogo_que_nao_entrou")
    if not isinstance(achados, list):
        return None
    frases = [
        str(a.get("frase") or "")
        for a in achados
        if isinstance(a, dict) and a.get("frase")
    ]
    if not frases:
        return None
    ativo = state_global.get("active_profile")
    if isinstance(ativo, str) and ativo:
        frases.append(f'Enquanto isso, vale o perfil "{ativo}".')
    return "\n".join(frases)


def texto_do_contexto(state_global: dict[str, Any] | None) -> str:
    """A linha de cabeçalho da aba: em que modo e com que máscara ela está.

    É a linha que amarra esta aba à aba Início — e ela usa os rótulos DE LÁ,
    importados, para as duas abas nunca chamarem a mesma coisa por dois nomes.
    A pergunta que a aba fecha é *"funciona nos três modos?"*, então o modo tem
    de estar escrito na tela junto com a resposta.

    Sem daemon, devolve a frase de desligado: afirmar máscara nenhuma a partir
    de um payload que não existe é a família de erro que esta casa já removeu
    do `texto_do_custo_da_mascara`.
    """
    if not isinstance(state_global, dict):
        return TEXTO_OFFLINE
    modo = mode_of_state(state_global)
    rotulo_do_modo = dict(_MODE_ITEMS).get(modo or "", "")
    if modo != MODE_GAMEPAD:
        return rotulo_do_modo
    gamepad = state_global.get("gamepad_emulation")
    flavor = gamepad.get("flavor") if isinstance(gamepad, dict) else None
    rotulo_da_mascara = dict(_FLAVOR_ITEMS).get(str(flavor), "")
    if not rotulo_da_mascara:
        # Máscara ausente ou desconhecida: diz o modo e cala sobre o resto.
        return rotulo_do_modo
    return f"{rotulo_do_modo} · O jogo vê o controle como: {rotulo_da_mascara}"


def titulo_do_painel(entry: dict[str, Any]) -> str:
    """O título de um painel — o MESMO do card do controle na aba Status.

    "Controle 1 — USB · Jogador 1". Reusar o título é o que faz as duas abas
    lerem como o mesmo aparelho: ela olha a aba Status, olha esta, e o nome
    bate sem ela ter de traduzir nada.
    """
    return titulo_do_card(entry)


# ---------------------------------------------------------------------------
# Resolução condicional de GTK (padrão da casa: real + stub)
# ---------------------------------------------------------------------------

try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib, Gtk

    _GTK_DISPONIVEL = all(
        hasattr(Gtk, attr)
        for attr in ("Frame", "Box", "Grid", "Label", "Align", "Orientation")
    ) and hasattr(GLib, "markup_escape_text")
except (ImportError, ValueError):
    _GTK_DISPONIVEL = False


if _GTK_DISPONIVEL:

    class PainelNoJogo(Gtk.Frame):  # type: ignore[misc]
        """O painel de UM controle na aba "No jogo".

        Uso (a mixin de status monta e distribui, no molde do ControllerCard)::

            painel = PainelNoJogo()
            painel.atualizar(entry, state_full)

        Sem timer próprio: quem chama é o tique de 2 Hz que a mixin já tinha, e
        só com esta aba à vista. O gate de timers da `status_actions` conta as
        ocorrências de `GLib.timeout_add` no fonte — este widget não acrescenta
        nenhuma, de propósito.
        """

        def __init__(self) -> None:
            super().__init__()
            self.set_label(" ")
            self._titulo = ""
            self._ultimo: tuple[Any, ...] | None = None
            self._linhas: dict[str, Any] = {}
            # O par que vira teto de largura: pedido MÍNIMO + `halign=START`.
            # Ver :data:`LARGURA_PAINEL` para o porquê de não ser só o pedido.
            self.set_size_request(LARGURA_PAINEL, -1)
            self.set_halign(Gtk.Align.START)

            corpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            corpo.set_margin_top(8)
            corpo.set_margin_bottom(8)
            corpo.set_margin_start(10)
            corpo.set_margin_end(10)
            self.add(corpo)

            self._grade = Gtk.Grid()
            self._grade.set_column_spacing(18)
            self._grade.set_row_spacing(4)
            corpo.pack_start(self._grade, False, False, 0)

            # O recado ocupa o LUGAR das linhas (nunca os dois ao mesmo tempo):
            # sem gamepad virtual não há o que tabelar, e uma tabela de seis
            # traços ao lado de uma explicação seria ruído em cima de ruído.
            self._recado = Gtk.Label()
            self._recado.set_xalign(0.0)
            self._recado.set_line_wrap(True)
            # `max_width_chars` NÃO basta sozinho — ele limita a largura NATURAL
            # e o pai continua livre para alocar mais (medido em 01/08: um
            # parágrafo de 1869px ficou intacto). Precisa de `halign=start`.
            self._recado.set_max_width_chars(72)
            self._recado.set_halign(Gtk.Align.START)
            self._recado.get_style_context().add_class("dim-label")
            # `no_show_all` porque quem manda na visibilidade deste rótulo é o
            # `atualizar`, e um `show_all()` de fora (a janela inteira nasce com
            # um, e o retrato das abas roda outro) o traria de volta VAZIO —
            # medido: um label vazio e visível some da tela mas cobra a altura
            # de uma linha, e o painel ganhava um vão sem causa aparente.
            self._recado.set_no_show_all(True)
            corpo.pack_start(self._recado, False, False, 0)

            self._montar_linhas()

        def _montar_linhas(self) -> None:
            """Cria as seis linhas UMA vez; o tique só troca texto e classe.

            As linhas são fixas de propósito — é o que permite comparar a tela
            antes e depois de trocar a máscara olhando o mesmo lugar. Recriar
            widget a cada tique também faria a aba piscar a 2 Hz.
            """
            for indice, recurso in enumerate(RECURSOS):
                nome = Gtk.Label(label=NOME_DO_RECURSO[recurso])
                nome.set_xalign(0.0)
                nome.get_style_context().add_class("hefesto-rotulo")
                valor = Gtk.Label(label="")
                valor.set_xalign(0.0)
                valor.set_line_wrap(True)
                valor.set_max_width_chars(56)
                valor.set_halign(Gtk.Align.START)
                # Mesma razão do recado: a linha de um recurso que não tem o
                # que afirmar fica ESCONDIDA, e um `show_all()` de fora a
                # traria de volta com o texto do ciclo anterior.
                nome.set_no_show_all(True)
                valor.set_no_show_all(True)
                self._grade.attach(nome, 0, indice, 1, 1)
                self._grade.attach(valor, 1, indice, 1, 1)
                self._linhas[recurso] = (nome, valor)

        def atualizar(
            self, entry: dict[str, Any], state_global: dict[str, Any]
        ) -> None:
            """Repinta o painel a partir do ``state_full``.

            Diff no começo, como o card: repetir o mesmo estado não toca em
            widget nenhum. O que muda de fato a 2 Hz é o número do giroscópio
            e o dos motores, e mesmo assim só enquanto ela está jogando.
            """
            titulo = titulo_do_painel(entry)
            recado = recado_do_controle(entry, state_global)
            linhas = [] if recado else linhas_do_controle(entry, state_global)
            assinatura = (titulo, recado, tuple(linhas))
            if assinatura == self._ultimo:
                return
            self._ultimo = assinatura

            if titulo != self._titulo:
                self._titulo = titulo
                self.set_label(titulo)

            self._recado.set_text(recado or "")
            self._recado.set_visible(recado is not None)
            self._grade.set_visible(recado is None)
            por_recurso = {linha.recurso: linha for linha in linhas}
            for recurso, (rotulo, valor) in self._linhas.items():
                linha = por_recurso.get(recurso)
                visivel = linha is not None
                rotulo.set_visible(visivel)
                valor.set_visible(visivel)
                if linha is None:
                    continue
                cor = COR_DA_SITUACAO.get(linha.situacao)
                contexto = valor.get_style_context()
                if cor is None:
                    valor.set_text(linha.texto)
                    contexto.add_class("dim-label")
                else:
                    contexto.remove_class("dim-label")
                    valor.set_markup(
                        f'<span foreground="{cor}">'
                        f"{GLib.markup_escape_text(linha.texto)}</span>"
                    )

else:

    class PainelNoJogo:  # type: ignore[no-redef]
        """Stub sem GTK3 — guarda o resultado das funções puras.

        Mesmo desenho do stub do `ControllerCard`: o suficiente para asserção
        de contrato num ambiente sem toolkit (o job `lint-test` do CI roda sem
        PyGObject por decisão registrada no `ci.yml`).
        """

        def __init__(self) -> None:
            self.titulo: str | None = None
            self.recado: str | None = None
            self.linhas: list[LinhaDoJogo] = []

        def atualizar(
            self, entry: dict[str, Any], state_global: dict[str, Any]
        ) -> None:
            self.titulo = titulo_do_painel(entry)
            self.recado = recado_do_controle(entry, state_global)
            self.linhas = (
                [] if self.recado else linhas_do_controle(entry, state_global)
            )


__all__ = [
    "COR_DA_SITUACAO",
    "COR_DO_AVISO_DE_PERFIL",
    "LARGURA_PAINEL",
    "NOME_DO_RECURSO",
    "PALAVRA_DA_SITUACAO",
    "RECURSOS",
    "SITUACOES_APAGADAS",
    "TEXTO_DESKTOP",
    "TEXTO_NATIVO",
    "TEXTO_OFFLINE",
    "TEXTO_SEM_CONTROLE",
    "TEXTO_SEM_VPAD",
    "LinhaDoJogo",
    "PainelNoJogo",
    "aviso_do_perfil",
    "linhas_do_controle",
    "recado_do_controle",
    "recado_global",
    "tem_controle_no_jogo",
    "texto_do_contexto",
    "titulo_do_painel",
]
