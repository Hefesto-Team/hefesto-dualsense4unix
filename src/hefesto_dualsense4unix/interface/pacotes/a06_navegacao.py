#!/usr/bin/env python3
"""O pacote da aba `06` Navegação.

O QUE TEM DONO: quem é o PRIMÁRIO (`is_primary`) — e é ele quem navega o PC.
O daemon marca um controle como primário, e a tela já dizia isso à mão: o
`NAVEGA` do gerador tirava o MENOR número da mesa, que acerta por coincidência
enquanto o P1 estiver na frente. Agora sai do daemon.

O QUE NÃO TEM: os cinco gestos (PS+Options, PS+↑…). Eles NÃO são configuráveis —
`daemon/subsystems/hotkey.py` monta um callback por combo, em código, e o único
pedaço ajustável é o `ps_button_action` da config, que método de IPC nenhum
escreve. A tabela da tela oferece trocar o que cada combo faz; o produto não tem
onde guardar essa troca.

FATO SUBSTITUÍDO (01/09/2026, segunda leva): esta linha dizia que os cinco
gestos "moram no PERFIL". Não moram — o perfil guarda `key_bindings`, que são
os BOTÕES (options, create, l1, r1, l3, r3 e as três regiões do touchpad), e
combo nenhum. A frase sobre as velocidades de cursor e rolagem, que estava na
mesma linha, já tinha caído na primeira leva (ver o `SEM_DONO` logo abaixo).

OS VINTE E OITO INDECIDÍVEIS DESTA ABA ESTÃO DECIDIDOS — 02/09/2026, à tarde.
A `--prova-de-mockup` classificava 28 dos 29 campos como INDECIDÍVEL: o valor que
o produto pinta COINCIDE com o que o desenho cravou, e ler a tela não separa
"pintou igual" de "não pintou". Era a maior concentração da casa. A cura foi
fazer o valor MUDAR — um DUBLÊ no lugar do daemon (três controles sintéticos,
`speed=11`, `scroll_speed=4`, teclado desligado, e um `button_actions` que troca
as 21 linhas) — e ver se a tela acompanha:

    mesa dela (2 controles)   produto  1 · mockup 0 · indecidível 28
    DUBLÊ                     produto 29 · mockup 0 · indecidível  0

**Os 29 endereços desta aba estão vivos.** Nenhum é endereço morto, e nenhum
campo depende do desenho. A régua que reproduz isso sem abrir janela é
`tests/unit/test_a_06_o_duble_decide_o_indecidivel.py`.

A PINTURA DESFAZIA A ESCOLHA DE QUEM CLICA — CURADO EM 02/09/2026, por decisão
dela. O defeito estava medido com dublê, escolhendo uma opção como uma pessoa
escolheria (evento `change`):

    ANTES  (o que a pintura pôs) : Botão direito
    CLIQUE (a escolha dela)      : F11
    +100 ms                      : F11
    +1500 ms (três tiques)       : Botão direito

Eram DUAS causas, e as duas eram desta aba: os 21 `<select>` não casavam com
nenhum endereço clicável do ouvinte (`hefesto_vivo.py:367`, o `closest` de
`manda_do_alvo`) — logo a escolha não chegava ao Python —, e o tique seguinte
reescrevia o valor do perfil por cima. Enquanto isso valeu, **o "Guardar" nunca
recebeu uma forma diferente do perfil**, e a recusa dele mandava trocar a linha
antes de clicar, um caminho que este mesmo arquivo declarava não existir.

A cura é a decisão dela: *"as 21 listas param de ser repintadas enquanto ela
está mexendo, até guardar ou sair"*. O gerador passou a marcar as 21 linhas com
`data-gesto` (`aba06.LINHA_DE_BOTAO`), o gesto `linha-de-botao` anota a escolha
em `_MEXENDO`, e a pintura passa a CONCORDAR com a tela em vez de reescrevê-la.
Ver `_o_que_a_tabela_mostra`.

O QUE SOBRA PARA O PILOTO, e continua relatado: a mesma forma de defeito vale
para TODA lista e TODO campo digitável das outras abas (o editor da Perfis, os
`<select>` da Conexões). A cura geral é o `escrever()` não sobrepor campo que a
pessoa está editando; a daqui resolve esta aba com o vocabulário que o piloto já
tem, sem tocar arquivo de fora.

E O SEGUNDO DEFEITO DO PILOTO, medido em 02/09/2026 e também relatado: **a frase
de recusa NÃO CHEGA À TELA DELA.** O `except` de `trabalhar()`
(`hefesto_vivo.py:758-771`) faz duas coisas e volta — grava `self.desfechos`,
que só a régua do aparelho lê, e imprime no `stderr`. Não chama `_js`, não chama
`window.__hef`, e `pintar()` não tem canal para mensagem: varre `fita`,
`blocos`, `mesa`, `vazios` e `colunas`, e nada mais. **Toda frase de recusa
deste arquivo é escrita para o dia em que o piloto ganhar onde mostrá-la** — o
que ela muda HOJE é o DESFECHO que a régua do aparelho lê, e essa é a diferença
entre "recusou dizendo" e "disse aplicado e nada mudou".

OS DOIS `return` MUDOS MORRERAM — 02/09/2026, corretivo. O "Guardar" e o "Voltar
ao padrão" saíam sem gravar, sem chamar e **sem uma palavra** quando não havia o
que fazer. No "Guardar" isso era cruel: a trava contra o apagador manda *"espere
a tabela se preencher e clique de novo"*, e o segundo clique caía exatamente
nesse `return`. Uma recusa que instrui a repetir o gesto e depois não responde
nada promete que a segunda tentativa funciona. Os dois passaram a RECUSAR
DIZENDO — ver `guardar_definicoes` e `padrao_definicoes`.

A "FUNÇÃO DO TECLADO" TEM TRÊS OPÇÕES — decisão dela, 02/09/2026: *"`Só dentro
do jogo` · `Só fora do jogo` · `Desativado`. O padrão de um perfil novo é `Só
fora do jogo` — no jogo o L3 é o clique do analógico e o teclado atrapalha; no
desktop é onde ele serve."* Duas têm dono e uma recusa dizendo; **qual é qual
está invertido em tudo o que esta casa escreveu até hoje**, e a medição está no
corpo de `teclado()`. O padrão de PERFIL NOVO não é desta aba — é do esquema, e
está no relato.

FATO SUBSTITUÍDO (02/09/2026): **"esta aba MENCIONA 7 campos e PINTA 3"** —
escrito a partir do `--passear`, que imprime `06-navegacao.html  1  3`. Ela
pinta os OITO elementos endereçados. O `3` é contagem de MUDANÇA: o `escrever()`
do piloto devolve `1` só quando o valor novo difere do que a tela já mostra, e
cinco dos oito já coincidiam com o daemon dela (`2 controles:`, `1 USB · 1 BT`,
`6`, `1`, `Ligada — atalhos e teclado na tela`). Ler "mudança" como "pintura" é
a mesma confusão entre a PALAVRA e o ATO que produziu o "77%" falso, com o sinal
trocado — e aqui ela escondia os defeitos REAIS da aba, que a medição achou:
metade da linha do cartão indo para a tela (`_linha_do_cartao`), 8 chaves de 14
emitidas para o vazio (`SEM_ENDERECO`) e um "Guardar" que apagava o perfil
(`guardar_definicoes`).
"""
from __future__ import annotations

import time
from typing import Any

from hefesto_dualsense4unix.core import acoes_de_botao as acoes

from . import Contexto, perfil, registrar

#: CORRIGIDO EM 01/09/2026. Aqui estava escrito que a velocidade do cursor e da
#: rolagem "mora no perfil, não no state_full". **O daemon publica as duas**, em
#: `mouse_emulation`, junto com se a emulação está ligada e por que está
#: bloqueada — medido no daemon dela: `{"enabled": false, "speed": 6,
#: "scroll_speed": 1, "bloqueio": "desligada"}`.
#:
#: Os atalhos de BOTÃO vêm do perfil (`key_bindings`), que também tem dono.
#: Sobra nada.
SEM_DONO: dict[str, str] = {}

#: O QUE O PACOTE SABE E A PÁGINA NÃO TEM ONDE PÔR — medido em 02/09/2026, com
#: `casamento.py 06-navegacao.html`. É o INVERSO do `SEM_DONO`: lá o produto não
#: sabe responder; aqui ele sabe, e o desenho não tem lugar para a resposta.
#:
#: POR QUE ISTO PRECISOU EXISTIR: `casamento.py` já imprimia os órfãos e
#: **reprovava só o zero**. Esta aba emitia oito chaves para o vazio com o
#: portão verde — e uma delas, `via`, não era falta de lugar: era o pacote
#: mandando METADE de uma linha cujo endereço cobre a linha inteira. Órfão
#: silencioso e defeito real ficavam na mesma pilha, sem ninguém para separá-los.
#: `test_a_06_nao_manda_para_o_vazio.py` passou a cobrar que toda chave órfã
#: esteja AQUI, com a razão.
#:
#: `via` SAIU: virou parte do `navega` (ver `_linha_do_cartao`).
#: `teclado-ligado` SAIU: era o mesmo bit de `teclado-estado`, que tem endereço.
SEM_ENDERECO: dict[str, str] = {
    # OS TRÊS DO MOUSE — o desenho TEM onde: o interruptor "Status do Modo". O
    # que falta é o piloto poder escrevê-lo. O widget é um
    # `<input type="checkbox" checked>` cujo estado a CSS lê (`.tog-in:checked
    # + .tog`), e a palavra "Ligado"/"Desligado" sai de um `content:` — não há
    # nó de texto para pintar, e `escrever()` não sabe marcar uma caixa nem pôr
    # uma classe. Medido em 02/09: o daemon dela tinha `mouse_emulation.enabled
    # = False` e a tela dizia **Ligado**. É a maior mentira desta aba, e a cura
    # é no piloto (um alvo que escreva atributo/classe), não aqui.
    "rato-ligado": "o 'Status do Modo' é um <input checkbox> e o piloto não sabe "
                   "marcar caixa nem trocar classe — hoje ele diz 'Ligado' com a "
                   "emulação desligada",
    "rato-bloqueio": "o motivo do bloqueio não tem linha no desenho; a frase do "
                     "produto é `app/actions/mouse_actions.frase_da_recusa_do_mouse`",
    "rato-despachando": "idem — quem despacha o cursor não aparece no desenho",
    # O TECLADO NA TELA: o produto TEM a frase pronta e humana em
    # `app/actions/input_actions.frase_do_teclado_na_tela(osk_disponivel)`, que a
    # GTK mostra. O desenho desta aba não tem onde pô-la.
    "teclado-osk": "o desenho não tem linha para 'há teclado na tela nesta "
                   "máquina'; a frase existe em "
                   "`app/actions/input_actions.frase_do_teclado_na_tela`",
    # OS ATALHOS DO PERFIL: a tabela da tela é a dos cinco COMBOS (PS+Options…),
    # que não são `key_bindings`. Não há onde mostrar a contagem, e mostrá-la na
    # tabela dos combos seria pôr um número ao lado de outra coisa.
    "gestos": "a tabela da tela é a dos cinco COMBOS, e `key_bindings` são os "
              "nove BOTÕES — não é o mesmo dado, e não há linha para ele",
    "gestos-lista": "idem; e a lista é estrutura, que o piloto pula",
}

#: AS DUAS FRASES DA LISTA "Função do teclado" QUE O DAEMON SABE DIZER, e elas
#: são o outro lado do contrato que `src/hefesto_dualsense4unix/interface/aba06.py:OPCOES_TECLADO`
#: desenha. A repetição é declarada, e os dois lados falham de jeitos diferentes
#: de propósito:
#:
#: * o GESTO casa pela palavra que DISTINGUE (`_ESCOLHA`), então reescrever o
#:   resto da frase não desliga o botão;
#: * a PINTURA usa a frase inteira, porque `escrever()` do piloto faz
#:   `el.value = texto` e o `<select>` só aceita o texto exato de uma `<option>`
#:   (as opções não têm `value` — ver a nota no gerador sobre o portão do
#:   desenho).
#:
#: AS TRÊS PALAVRAS SÃO DECISÃO DELA, 02/09/2026: *"`Só dentro do jogo` · `Só
#: fora do jogo` · `Desativado`. O padrão de um perfil novo é `Só fora do jogo`
#: — no jogo o L3 é o clique do analógico e o teclado atrapalha; no desktop é
#: onde ele serve."*
#:
#: DUAS TÊM DONO E UMA NÃO, e qual é qual foi MEDIDO — ver o `fato_derrubado`
#: no corpo de `teclado()`. O que o teclado emulado faz hoje **já é** "só fora
#: do jogo": o daemon cala a emulação de desktop quando um jogo assume
#: (`_jogo_no_controle_do_desktop`, `daemon/lifecycle.py:2263`, e o
#: `gamepad_dispatched` do laço em `:4780`), e o `suppress_desktop_emulation`
#: do perfil é a versão explícita e por perfil da MESMA coisa. Quem não tem
#: dono é o INVERSO — "só dentro do jogo".
TECLADO_SO_FORA = "Só fora do jogo"
TECLADO_DESATIVADO = "Desativado"
TECLADO_SO_DENTRO = "Só dentro do jogo"

#: O SEPARADOR DO CARTÃO — o mesmo `•` que o desenho põe entre o transporte e o
#: papel (`aba06.controle`: `{via} <span class="pt">•</span> {papel}`). Ele é
#: texto porque o endereço `data-campo="navega"` cobre a LINHA INTEIRA: o piloto
#: escreve `textContent`, e o que não vier na string some da tela.
PONTO = " • "

#: O PREFIXO DAS VINTE E UMA LINHAS de *o que cada botão faz*. Um por botão de
#: `core/acoes_de_botao.BOTOES` — a lista é do produto, e não se digita aqui.
PREFIXO_DA_ACAO = "acao-"  # (noqa-acento) prefixo de endereço, não é prosa


def _nome_do_botao(botao: str) -> str:
    """`"l2"` → `"L2 (gatilho esquerdo)"`. O nome que ELA lê, e é do MOTOR.

    NÃO SE ESCREVE A TABELA AQUI. `app/actions/input_actions.humanize_button`
    (`:181`) é dona dos vinte nomes desde o KBD-01, e a GTK que ela usa mostra
    exatamente estes. As duas frases de recusa do "Guardar" mandavam o id cru
    para a tela — ela lia *"estas linhas ficaram sem quem as atenda:
    touchpad_left_press"*, que é jargão de kernel na cara de quem clicou.

    FATO SUBSTITUÍDO — 02/09/2026, corretivo. Este parágrafo citava TRÊS ids
    como curados: `l2`, `touchpad_left_press` e `r3_direcao`. **Os dois eixos
    continuam crus**, e a medição é de um comando:

        _nome_do_botao('l2')                  → 'L2 (gatilho esquerdo)'
        _nome_do_botao('touchpad_left_press') → 'Touchpad — lado esquerdo'
        _nome_do_botao('r3_direcao')          → 'r3_direcao'
        _nome_do_botao('l3_direcao')          → 'l3_direcao'

    São 21 botões em `acoes.BOTOES` e 20 nomes em `_BUTTON_LABELS`, e os dois
    que faltam são a DIREÇÃO dos analógicos. A cura mora no MOTOR
    (`app/actions/input_actions.py:129`), não aqui — copiar duas linhas para
    dentro deste arquivo criaria a segunda tabela que o
    `test_o_nome_do_botao_e_o_do_motor_e_nao_uma_segunda_tabela` existe para
    impedir, e a tela passaria a chamar o mesmo botão por dois nomes.

    O DANO HOJE É DE FORMA, e por isso não se força a cura: `acoes.resolver()`
    (`core/acoes_de_botao.py:285`) pula os eixos, então eles nunca chegam ao
    `sem_dono` — medido, trocando o `cross`: `sem_dono == ['l2']`. O único
    caminho que ainda os exporia é o `nao_reconhecidas` do "Guardar", que exige
    a tela oferecer um rótulo que o produto não conhece.

    O IMPORT É TARDIO, E É POR ISSO: `input_actions` puxa GTK no topo (e
    `mouse_actions` junto). Os pacotes são puros de propósito — importáveis sem
    janela, testáveis sem display —, e um import no topo deste arquivo faria a
    aba inteira depender da camada da janela ANTIGA para escrever um rótulo.
    Aqui ele custa uma vez, no caminho da recusa, que não é o do tique.

    E ELE CAI DE PÉ: sem GTK no ambiente, o id cru volta. Um rótulo bonito não
    vale derrubar a aba — o cru é feio e é honesto, que é a mesma escolha do
    `acoes.rotulo()` para um token sem nome.
    """
    try:
        from hefesto_dualsense4unix.app.actions.input_actions import humanize_button
    except Exception:
        return botao
    return humanize_button(botao)


def _linha_do_cartao(c: dict[str, Any], primario: bool) -> str:
    """A linha inteira do cartão: `"BT • Navega o PC"`.

    ELA ERA METADE, e a metade que faltava era o TRANSPORTE — medido em
    02/09/2026, com a foto ao lado. O desenho escreve
    `{via} <span class="pt">•</span> {papel}` e põe o `data-campo="navega"` na
    `<div>` que os contém; o pacote mandava só o papel. Como o piloto escreve
    `textContent`, o primeiro tique APAGAVA o "USB •" do cartão — a tela nascia
    dizendo por onde o controle está ligado e parava de dizer meio segundo
    depois, sem que nada acusasse.

    O `via` NÃO SE CALCULA AQUI. `mesa_viva` é o dono da regra
    (`"USB" if transporte == "usb" else "BT"`), e ela já vem mastigada na mesa
    que o piloto monta — repeti-la seria a segunda verdade que envelhece calada.
    O `ctx.conectados` é a resposta CRUA do daemon e traz `transport`; a mesa
    traz `via`. Quem entra na tela é o da mesa.
    """
    papel = "Navega o PC" if primario else "Só a janela"
    return PONTO.join(x for x in (str(c.get("via") or ""), papel) if x)


def _linhas_dos_botoes(p: dict[str, Any]) -> dict[str, str]:
    """As 21 linhas de *o que cada botão faz*, com o RÓTULO que o desenho mostra.

    O VOCABULÁRIO É O DO MOTOR, inteiro: `acoes.BOTOES` diz quais linhas
    existem, `acoes.padrao()` diz o que cada uma faz de fábrica e
    `acoes.rotulo()` traduz o token no texto da `<option>`. O gerador monta as
    mesmas listas do mesmo lugar (`aba06.ACOES_UNI = por_grupo()`), e é por isso
    que o valor emitido aqui SEMPRE existe como opção — condição do
    `escrever()` com `data-hef-alvo="valor"`, que se cala quando não casa.

    O PERFIL VENCE O DE FÁBRICA linha a linha, e não em bloco: `button_actions`
    guarda DIFERENÇA (`None` quer dizer "herda"), então uma linha ausente não é
    "nada" — é o de fábrica.
    """
    escolhas = (p.get("button_actions") or {}) if p else {}
    de_fabrica = acoes.padrao()
    return {
        f"{PREFIXO_DA_ACAO}{botao}": acoes.rotulo(
            str(escolhas.get(botao) or de_fabrica.get(botao) or ""))
        for botao in acoes.BOTOES
    }


#: O QUE ELA JÁ ESCOLHEU E AINDA NÃO GUARDOU: `acao-<botão>` → o rótulo que
#: está no `<select>`. Só entram as linhas que DIFEREM do que o perfil guarda —
#: escolher de volta o valor do perfil tira a linha daqui, e com o dicionário
#: vazio a aba volta a ser exatamente o que era antes desta trava.
#:
#: DECISÃO DELA, 02/09/2026: *"o Guardar FICA. As 21 listas param de ser
#: repintadas enquanto ela está mexendo, até guardar ou sair. **Não** vira
#: gravação automática: ela quer escolher várias, conferir e aplicar de uma
#: vez."*
#:
#: O QUE ISSO CURA, e estava medido no próprio arquivo: a pintura desfazia a
#: escolha de quem clica em ≤1,5 s (três tiques de `hefesto_vivo.TIQUE_MS`),
#: e por isso o "Guardar" NUNCA recebia uma forma diferente do perfil —
#: ele caía sempre no ramo de "não havia o que guardar". A recusa daquele ramo
#: ainda mandava *"troque a linha antes de clicar"*, um caminho que o mesmo
#: arquivo declarava não existir. Agora existe.
#:
#: ELE É DE MÓDULO, e é de propósito: o pacote é chamado uma vez por tique e não
#: tem onde guardar estado entre tiques. O piloto é um processo por janela e uma
#: janela por vez — não há duas telas desta aba no mesmo processo.
_MEXENDO: dict[str, str] = {}

#: Quando a tabela foi pintada pela última vez (`time.monotonic`). É o que
#: distingue "ela continua na aba" de "ela saiu e voltou".
_ULTIMA_PINTURA = 0.0

#: A PAUSA QUE SIGNIFICA OUTRA ABA. O tique do piloto é de 500 ms
#: (`hefesto_vivo.TIQUE_MS`), e enquanto ela estiver nesta página o `pacote()`
#: é chamado a cada tique. Dez tiques sem uma chamada só acontecem se a página
#: SAIU de cena — e voltar a ela é um documento NOVO, com os 21 `<select>` de
#: volta no que o gerador cravou. Aí a trava tem de estar solta, senão a tabela
#: ficaria mostrando o desenho com o perfil dizendo outra coisa.
#:
#: NÃO SE IMPORTA `TIQUE_MS` DAQUI: `hefesto_vivo` puxa GTK no topo, e os
#: pacotes são puros de propósito — importáveis sem janela, testáveis sem
#: display. O número está escrito com a conta ao lado, que é o que permite
#: conferir a divergência se o tique mudar.
#:
#: O CUSTO ESTÁ DECLARADO: um daemon mudo por mais de cinco segundos também
#: interrompe a pintura (o `_tique` do piloto volta antes de chamar o pacote), e
#: nesse caso as escolhas pendentes são largadas como se ela tivesse saído. É o
#: preço de não haver, hoje, um sinal de "a página recarregou" que chegue ao
#: pacote — e ele erra para o lado seguro: a tela volta a mostrar o perfil, que
#: é a verdade do disco, em vez de fingir uma escolha que ninguém mais está
#: fazendo.
PAUSA_DE_OUTRA_ABA = 5.0


def _largar_o_que_ela_mexeu() -> None:
    """Solta a trava. Chamado pelo "Guardar", pelo "Voltar ao padrão" e pelo sair."""
    _MEXENDO.clear()


def _o_que_a_tabela_mostra(p: dict[str, Any]) -> dict[str, str]:
    """As 21 linhas: o perfil, com as que ela está mexendo por cima.

    A PINTURA NÃO PARA — ela passa a CONCORDAR com a tela, que é a única forma
    estável de "não repintar". Um pacote que simplesmente OMITISSE as 21 chaves
    deixaria a tabela sem dono: a página recarregada mostraria o desenho para
    sempre, e o contador de pinturas do piloto perderia 21 endereços vivos. Aqui
    o valor emitido é o que o `<select>` já tem, então `escrever()` devolve 0 e
    nada pisca — e o que ela escolheu continua na tela até guardar ou sair.

    A JANELA DE SAÍDA é medida pelo relógio, e não por um sinal do piloto: ver
    `PAUSA_DE_OUTRA_ABA`.
    """
    global _ULTIMA_PINTURA

    agora = time.monotonic()
    if _MEXENDO and _ULTIMA_PINTURA and agora - _ULTIMA_PINTURA > PAUSA_DE_OUTRA_ABA:
        # ELA SAIU DA ABA. O documento que ela vê agora é outro, e nele os 21
        # `<select>` voltaram ao que o gerador cravou — segurar as escolhas
        # velhas por cima disso seria pintar uma decisão que ela abandonou.
        _largar_o_que_ela_mexeu()
    _ULTIMA_PINTURA = agora
    linhas = _linhas_dos_botoes(p)
    # SÓ AS QUE AINDA DIFEREM. Se o perfil já passou a dizer o que ela escolheu
    # (o "Guardar" gravou, ou outro caminho mudou o perfil), a linha sai da
    # trava sozinha — e a trava se esvazia sem ninguém precisar lembrar.
    for campo in list(_MEXENDO):
        if campo not in linhas or linhas[campo] == _MEXENDO[campo]:
            del _MEXENDO[campo]
    linhas.update(_MEXENDO)
    return linhas


@registrar("06-navegacao.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    st = ctx.state
    rato = st.get("mouse_emulation") or {}
    tecla = st.get("keyboard_emulation") or {}
    p = perfil.ativo(st.get("active_profile"))
    atalhos = (p.get("key_bindings") or {}) if p else {}

    cards = {}
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        # A MESA É QUEM TEM O `via`. `ctx.conectados` é a resposta crua do
        # daemon (`transport`), e a tradução para "USB"/"BT" tem dono em
        # `mesa_viva.mesa_do_estado`. Sem casa na mesa (um controle que entrou
        # entre a montagem da mesa e este tique), a linha sai só com o papel —
        # meia verdade, nunca um transporte inventado.
        na_mesa = next((m for m in ctx.mesa if str(m.get("uniq") or "") == uniq), {})
        cards[uniq] = {"navega": _linha_do_cartao(na_mesa, bool(c.get("is_primary")))}
    mesa = {
        # AS DUAS VELOCIDADES, do daemon — não do perfil. O perfil guarda o
        # que ela SALVOU; o daemon diz o que está VALENDO agora, e é o
        # segundo que a tela mostra.
        "vel-cursor": rato.get("speed"),
        "vel-rolagem": rato.get("scroll_speed"),
        "rato-ligado": bool(rato.get("enabled")),
        "rato-bloqueio": rato.get("bloqueio") or "",
        "rato-despachando": bool(rato.get("despachando")),
        "teclado-osk": bool(tecla.get("osk_disponivel")),
        "gestos": len(atalhos),
        "gestos-lista": {k: v for k, v in list(atalhos.items())[:12]},
    }
    # AS VINTE E UMA LINHAS DE *O QUE CADA BOTÃO FAZ*, do perfil dela — e elas
    # não existiam aqui até 02/09/2026. O botão "Guardar" LIA essas linhas
    # (`data-hef-forma`) e nada as ESCREVIA, então a tela mostrava para sempre o
    # que o desenho escolheu. Ver `guardar_definicoes` para o que isso custava.
    #
    # E ELAS PARAM DE SER REPINTADAS ENQUANTO ELA ESTÁ MEXENDO — decisão dela,
    # 02/09/2026. Ver `_o_que_a_tabela_mostra`.
    mesa.update(_o_que_a_tabela_mostra(p))
    # A LISTA "Função do teclado" SÓ É REESCRITA QUANDO O DAEMON FALOU, e a
    # ausência da chave é o que impede a mentira: sem o bloco
    # `keyboard_emulation` (daemon mudo, ou config inacessível — o `state_full`
    # OMITE o bloco nesse caso) escrever "Desligada" afirmaria um estado que
    # ninguém mediu. Chave ausente = a pintura não toca no `<select>`.
    #
    # E ela é o ÚNICO canal de recusa VISÍVEL desta aba: um gesto que levanta só
    # grava o desfecho e imprime no **stderr** do piloto
    # (`hefesto_vivo.py:768-771`) — o `except` de `trabalhar()` não chama `_js`
    # nem `window.__hef`, e `pintar()` não tem campo para mensagem. Escolher
    # "Só dentro do jogo", que não tem dono, deixa a lista parada na opção
    # errada até o tique seguinte reescrevê-la com o que o daemon diz.
    if "keyboard_emulation" in st:
        mesa["teclado-estado"] = (
            TECLADO_SO_FORA if tecla.get("enabled") else TECLADO_DESATIVADO)
    return {
        "colunas": cards,
        "mesa": mesa,
        "sem_dono": {},
        # O NÚMERO SAI DOS DICIONÁRIOS, e não de uma constante escrita à mão:
        # foi uma soma digitada (`len(cards) * 2 + 9`) que deixou a curva da aba
        # Gatilhos fora da cobertura, e aqui ela erraria no tique em que a lista
        # do teclado entra — o valor é condicional.
        #
        # E ELE DESCONTA O QUE NÃO TEM ONDE CAIR — 02/09/2026. Contar chave
        # EMITIDA como "pintado" é a mesma confusão entre a PALAVRA e o ATO que
        # produziu o "77%" falso desta casa: medido no mesmo dia, esta aba
        # emitia 14 chaves e a página tinha endereço para 6. O instrumento dizia
        # 14. Um contador que mente é pior que um campo parado.
        "cobertura": {"pintados": (sum(len(v) for v in cards.values())
                                   + len(set(mesa) - set(SEM_ENDERECO))),
                      "sem_dono": len(SEM_DONO)},
    }


# ---------------------------------------------------------------------------
# OS GESTOS — ver o exemplo comentado em `a04_iluminacao.py`
#
# ESTA ABA NÃO ENDEREÇA POR CONTROLE, e é decisão do desenho: o `title` da fita
# diz, com todas as letras, *"Não se aplica: mouse, teclado e gestos saem de um
# controle só"* — o primário. Nenhum gesto daqui pede `uniq`, e nenhum dos três
# métodos do daemon aceita um: `mouse.emulation.set`, `mouse.emulation.restore`
# e `keyboard.emulation.set` valem para a MÁQUINA.
#
# DE ONDE VEM O NÚMERO QUE O GESTO SOMA: do `ctx`, que é o estado do ÚLTIMO
# TIQUE (500 ms, `hefesto_vivo.TIQUE_MS`). Dois cliques dentro do mesmo tique
# leem o mesmo `atual` e mandam o mesmo alvo — o segundo não anda. Ler o daemon
# a cada clique custaria um `daemon.state_full` por clique (57 ms medidos, e
# HARM-15 já registra que ele passa dos 0,25 s sob carga), e ainda assim a tela
# só repinta no tique. Fica declarado aqui porque é o que alguém vai medir.
# ---------------------------------------------------------------------------
from hefesto_dualsense4unix.app.actions.mode_transition import (  # noqa: E402
    MODE_DESKTOP,
    mode_of_state,
)
from hefesto_dualsense4unix.integrations.uinput_mouse import (  # noqa: E402
    DEFAULT_MOUSE_SPEED,
    DEFAULT_SCROLL_SPEED,
)

from . import gesto  # noqa: E402

#: A ORIGEM É `manual` PORQUE É A MÃO DELA. `origem_do_pedido`
#: (`daemon/ipc_handlers.py:46`) lê a AUSÊNCIA como `"profile"`, e a assimetria é
#: de propósito — foi um cliente que só reconciliava estado, promovido a gesto
#: humano, que devolveu o gamepad virtual com o grab pulado e pôs um "Jogador 3"
#: fantasma na tela dela (JOGADOR-3-FANTASMA-01). Aqui é clique, logo é manual.
MANUAL = "manual"


def _rato(ctx: Contexto) -> dict[str, Any]:
    """O bloco `mouse_emulation` do último tique — o que está VALENDO agora.

    Ele é o do DAEMON, e não o do perfil: o perfil guarda o que ela salvou, e a
    tela mexe no que está ligado. É a mesma escolha que a função de pintura
    acima já fazia.
    """
    return ctx.state.get("mouse_emulation") or {}


def _passo(o: dict[str, Any]) -> int:
    """`+1` ou `-1`, lido do NOME do gesto que chegou.

    O piloto manda `o["gesto"]` com o `data-gesto` do botão clicado
    (`hefesto_vivo.py:202`), e os dois botões de um `bignum` são
    `<nome>-menos` e `<nome>-mais`. Assim a direção não precisa de um atributo
    novo — e `data-v`, que seria o candidato, é o único da lista do piloto que
    o portão do desenho NÃO ignora (`check_o_desenho_aprovado.INVISIVEIS`), o
    que faria toda marcação virar divergência de desenho.
    """
    nome = str(o.get("gesto") or "")
    if nome.endswith("-mais"):
        return 1
    if nome.endswith("-menos"):
        return -1
    raise ValueError(f"velocidade: o clique não disse a direção (veio {nome!r})")


def _mandar(p: Any, **params: Any) -> None:
    """`mouse.emulation.set`, e RECLAMA quando ninguém respondeu.

    `p.chamar` devolve `False` só em falha de TRANSPORTE — o `_safe_call`
    (`app/ipc_bridge.py:103`) não olha o corpo. Um `{"status": "failed",
    "bloqueio": "sem_device"}` volta como `True` daqui, e o gesto **não tem como
    saber**: a ponte não expõe o `_call_checked_detalhado`, que é o único que
    entrega o corpo. Está no relato como achado; enquanto isso, o que dá para
    dizer com verdade é "ninguém respondeu", e é o que se diz.
    """
    if not p.chamar("mouse.emulation.set", **params):
        raise RuntimeError("o Hefesto não respondeu — a velocidade não mudou")


@gesto("06-navegacao.html", "modo")
def modo(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Status do Modo": o interruptor que liga mouse E teclado.

    POR QUE OS DOIS, e não só o mouse: este interruptor é o que ela pediu em
    27/08 no lugar de dois botões — *"Suspender Mouse e Teclado, Sair do Modo
    Jogo, deixam de existir devido ao botão status na parte superior"* —, e a
    dica dele diz o alcance: *"nada desta aba chega ao PC"*. Teclado é desta
    aba. São duas chamadas porque o daemon tem dois interruptores separados
    (`mouse.emulation.set` e `keyboard.emulation.set`), e o segundo nasceu
    justamente porque desligar o mouse deixava o teclado emitindo Alt+Tab dentro
    da partida (`daemon/ipc_handlers.py:5032`).

    O MOUSE VAI PRIMEIRO de propósito: é ele que tem exclusão mútua com o
    gamepad virtual (`daemon/lifecycle.py:1359` — ligar o mouse PARA o vpad). Se
    a primeira falhar, a segunda não chega a rodar e o teclado não fica ligado
    sozinho num modo que não é dele.

    O LADO PARA ONDE IR SAI DO DAEMON, nunca da caixinha: o piloto não sabe
    escrever `checked` (o `escrever()` dele cobre texto, largura, fundo e
    `value`), então o desenho nasce `checked` e o daemon dela nasce
    `enabled=false` — ler a tela inverteria o gesto no primeiro clique.

    O PORTÃO DO MODO É DO PRODUTO, e está copiado dele: `_sync_mouse_mode_gate`
    (`app/actions/mouse_actions.py:299`) faz `blocked = mode != MODE_DESKTOP` e
    desliga o interruptor nos DOIS sentidos, inclusive com o modo desconhecido.
    A razão está escrita lá e é o que este gesto herda: *"Ligar o switch durante
    'Jogar pelo Hefesto' derrubava o vpad e os jogadores do co-op SEM AVISO (a
    exclusão mútua do daemon é silenciosa)"*.

    A FRASE É OUTRA, e tem de ser: a do produto (`MODE_GATE_HINT`) manda ir à
    **aba Início**, que não existe no desenho das dez abas — o modo mudou para a
    aba **Jogar**. Reusá-la mandaria ela a uma aba que não está lá. Reusar o
    módulo também não dá: `mouse_actions.py` importa GTK no topo, e os pacotes
    são puros de propósito.
    """
    if not ctx.state:
        raise RuntimeError(
            "não consegui falar com o Hefesto agora, então não sei se ligar o "
            "mouse derrubaria um jogo em andamento. Tente de novo em instantes.")
    atual = mode_of_state(ctx.state)
    if atual != MODE_DESKTOP:
        raise RuntimeError(
            "só dá para mexer no mouse e no teclado fora do jogo: jogando, o "
            "controle é do jogo, e ligar o mouse aqui derrubaria o controle "
            "virtual e os jogadores do co-op no meio da partida. O degrau se "
            "troca na aba Jogar.")

    novo = not bool(_rato(ctx).get("enabled"))
    if not p.chamar("mouse.emulation.set", enabled=novo, origin=MANUAL):
        raise RuntimeError("o Hefesto não respondeu — o mouse ficou como estava")
    if not p.chamar("keyboard.emulation.set", enabled=novo):
        raise RuntimeError("o mouse mudou e o teclado não — o Hefesto não respondeu")


#: O QUE CADA OPÇÃO DA LISTA MANDA FAZER. A chave é a palavra que DISTINGUE uma
#: das outras duas, e não mais a primeira: com as três palavras dela, duas
#: começam por "só" — casar pela primeira faria "Só dentro do jogo" e "Só fora
#: do jogo" virarem a mesma escolha, e viraria CALADO.
#:
#: A busca é por palavra INTEIRA no texto da opção, em minúsculas, o que deixa o
#: gesto sobreviver a uma reescrita do resto da frase. Casar a frase toda
#: quebraria no dia em que alguém melhorasse o texto da tela — e um `<select>`
#: cujo valor não casa com nada simplesmente não faz nada.
#:
#: `None` é a opção que a tela oferece e o produto NÃO tem. Ela não vira `False`
#: nem `True` por conveniência: ver `teclado()`.
_ESCOLHA: dict[str, bool | None] = {"fora": True, "desativado": False, "dentro": None}


@gesto("06-navegacao.html", "teclado")
def teclado(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """A lista "Função do teclado". `keyboard.emulation.set`.

    O VALOR VEM EM `valor`, E ISSO É O QUE MUDOU DESDE A PRIMEIRA LEVA: o
    ouvinte do piloto passou a escutar `change` além de `click` e a mandar o
    `value` do alvo (`hefesto_vivo.py:196` e `:230`). Antes só chegava `texto`,
    que num `<select>` é a lista INTEIRA de opções concatenada — foi por isso
    que esta lista ficou sem dono na primeira leva, e não por falta de método.

    O `rotulo` É O SEGUNDO CAMINHO, não um enfeite: as `<option>` desta lista
    não têm atributo `value` (`value` não está entre os que o portão do desenho
    ignora), então `select.value` **é** o texto — mas um `<option value=…>` que
    nasça amanhã mandaria a chave em `valor` e a frase em `rotulo`, e é o
    `rotulo` que continuaria casando com o desenho.

    DUAS DAS TRÊS OPÇÕES TÊM DONO, e a terceira RECUSA DIZENDO — que é a regra
    da casa, não uma falha desta ligação:

    * "Só fora do jogo" → `enabled=True`; "Desativado" → `enabled=False`. O
      handler (`daemon/ipc_handlers.py:5038`) só lê `enabled`, e ele é bool.
    * "Só dentro do jogo" **não existe do outro lado**, e nem poderia: ele é o
      INVERSO de tudo o que o produto faz hoje.

    FATO DERRUBADO — 02/09/2026, e ele estava escrito NESTE arquivo e no
    enunciado do trabalho: *"'Só fora do jogo' não existe do outro lado"* e
    *"'Só dentro do jogo' já existe, e é o `suppress_desktop_emulation`"*. **Os
    dois estão invertidos**, e a medição é de três leituras:

    1. `Profile.suppress_desktop_emulation` (`profiles/schema.py:1036`) diz, no
       próprio comentário: *"True = ativar o perfil suprime a emulação de
       mouse/teclado no desktop (jogos de GAMEPAD que leem o controle cru)"*.
       O perfil é ativado quando o jogo casa; logo a supressão vale **durante o
       jogo** — o teclado funciona FORA dele.
    2. `apply_profile_suppression` (`daemon/lifecycle.py:1951`) recebe esse
       campo a cada ativação de perfil e liga a supressão com `desired=True`.
    3. Sem perfil nenhum a dizer o contrário, o daemon **já** cala a emulação de
       desktop quando um jogo assume: `_jogo_no_controle_do_desktop`
       (`:2263`, a cura da queixa dela de 29/07 — *"aperto r1 e ele muda de app
       ao invés de funcionar no jogo"*) e o `gamepad_dispatched` do laço
       (`:4780`).

    Logo o teclado emulado ligado **é** "só fora do jogo", e a etiqueta velha
    ("Ligada — atalhos e teclado na tela") é que afirmava um alcance maior do
    que o produto tem. O que falta é o INVERSO: um teclado que só valha DENTRO
    do jogo. Ele exigiria um portão por perfil com o sinal trocado — campo novo
    no esquema, e ele **não existe**. Enquanto não existir, esta opção recusa
    dizendo, que é o contrário de um botão que aceita o clique e não faz nada.

    SEM PORTÃO DE MODO, ao contrário do gesto `modo` logo acima, e é medido: o
    portão de lá existe porque ligar o MOUSE derruba o gamepad virtual — o
    `set_mouse_emulation` (`daemon/lifecycle.py:1336`).

    Do outro lado, o teclado não mexe no gamepad virtual em momento nenhum.
    Quem o liga e desliga é o
    `set_keyboard_emulation` (`daemon/lifecycle.py:1469`): ele cria ou destrói o
    teclado virtual e nada mais.

    E COM O GAMEPAD DESPACHANDO, o teclado nem chega a ser consultado — a
    guarda está em `lifecycle.py:2240`, no `if not gamepad_dispatched`. Copiar o
    portão daqui bloquearia, dentro do jogo, o único interruptor que existe
    para calar o Alt+Tab do R1 — que é o defeito que este método nasceu para
    curar (queixa dela, 29/07).

    O QUE ESTE BOTÃO AINDA NÃO DIZ, e está no relato: desligar tira também o
    teclado na tela do L3/R3 e as três regiões do touchpad (o handler manda a
    interface repassar isso). O piloto não tem canal de aviso — um gesto só
    imprime no terminal —, então o recado não tem onde aparecer.
    """
    escolhido = str(o.get("valor") or o.get("rotulo") or "").strip()
    palavras = {x.strip(".,;:—-").lower() for x in escolhido.split()}
    chaves = palavras & set(_ESCOLHA)
    if len(chaves) != 1:
        raise ValueError(
            f"teclado: não reconheci a opção escolhida ({escolhido!r}). As três "
            f"do desenho estão em `src/hefesto_dualsense4unix/interface/aba06.py:OPCOES_TECLADO`, "
            f"e cada uma tem de trazer exatamente uma destas palavras: "
            f"{', '.join(sorted(_ESCOLHA))}.")
    ligar = _ESCOLHA[chaves.pop()]
    if ligar is None:
        raise RuntimeError(
            f"“{TECLADO_SO_DENTRO}” ainda não tem dono, e é o INVERSO do que o "
            "Hefesto faz: ele cala o teclado emulado quando um jogo assume o "
            "controle, e o que sobra é justamente o “"
            f"{TECLADO_SO_FORA}”. Um teclado que valha SÓ dentro do jogo pede um "
            "campo novo no perfil — o portão com o sinal trocado —, e ele ainda "
            "não existe. A lista volta sozinha para o que está valendo.")
    if not p.chamar("keyboard.emulation.set", enabled=ligar):
        raise RuntimeError("o Hefesto não respondeu — o teclado ficou como estava")


@gesto("06-navegacao.html", "vel-cursor-mais")
@gesto("06-navegacao.html", "vel-cursor-menos")
def vel_cursor(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O menos e o mais do "Analógico" da Velocidade de cursor. `mouse_emulation.speed`.

    SEM `enabled` DE PROPÓSITO, e é a rota que o produto criou para isto: o
    handler manda o pedido sem `enabled` para `set_mouse_speed`
    (`daemon/ipc_handlers.py:4970`), que atualiza a config e o device vivo **sem
    start/stop e sem gravar o flag**. É o que impede um passo de velocidade de
    RELIGAR a emulação e matar o gamepad virtual — a regressão que o
    BUG-MOUSE-GUI-SYNC-01 (A4) fechou. O `_send_mouse_param_async` da GUI
    estável (`app/actions/mouse_actions.py:559`) manda exatamente este payload.

    NÃO SE APARA O NÚMERO AQUI. O teto e o piso têm dono e é o daemon:
    A faixa tem dono desde 01/09/2026 —
    `MOUSE_SPEED_MIN`/`MAX` em `integrations/uinput_mouse.py:78`, lidos
    pelo `set_speed` (`integrations/uinput_mouse.py:279`). Repetir
    `1..12` neste arquivo seria a segunda verdade que esta casa persegue — e ela
    envelheceria calada no dia em que a faixa mudasse. Um `13` chega, vira 12, e
    o tique seguinte repinta 12 na tela.

    O CHÃO É O DO PRODUTO: sem `speed` no estado (daemon sem responder ainda), o
    passo parte de `DEFAULT_MOUSE_SPEED`, que é o mesmo 6 que o desenho mostra.
    """
    atual = _rato(ctx).get("speed")
    atual = DEFAULT_MOUSE_SPEED if atual is None else int(atual)
    _mandar(p, speed=atual + _passo(o), origin=MANUAL)


@gesto("06-navegacao.html", "rolagem-mais")
@gesto("06-navegacao.html", "rolagem-menos")
def vel_rolagem(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O menos e o mais do "Analógico" da Velocidade da rolagem. `scroll_speed`.

    Mesma rota speed-only do vizinho, e o mesmo motivo. O que muda é o alcance:
    `scroll_speed` multiplica o passo do analógico DIREITO em `_emit_scroll`
    (`integrations/uinput_mouse.py:466`) e nada mais — o touchpad não rola.

    A FAIXA DELE É OUTRA, e o daemon é quem a impõe: `max(1, min(5, …))`
    (`daemon/lifecycle.py:1449` e `:1452`), contra os 12 do cursor. A dica da tela
    1 a 10" nas duas linhas, e nas duas está errada — está no relato.
    """
    atual = _rato(ctx).get("scroll_speed")
    atual = DEFAULT_SCROLL_SPEED if atual is None else int(atual)
    _mandar(p, scroll_speed=atual + _passo(o), origin=MANUAL)


@gesto("06-navegacao.html", "linha-de-botao")
def linha_de_botao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Ela trocou UMA das 21 linhas de *o que cada botão faz*. NÃO grava nada.

    ELE EXISTE PARA A TELA PARAR DE DESFAZER A ESCOLHA DELA — decisão de
    02/09/2026: *"as 21 listas param de ser repintadas enquanto ela está
    mexendo, até guardar ou sair. Não vira gravação automática: ela quer
    escolher várias, conferir e aplicar de uma vez."*

    Por isso ele **não chama o daemon e não escreve em disco**. O ponto de
    gravação continua sendo o "Guardar" ao lado; o que este gesto faz é anotar
    a escolha em `_MEXENDO`, e é a anotação que faz a pintura do tique seguinte
    concordar com a tela em vez de reescrevê-la.

    SEM ELE A ESCOLHA NÃO CHEGAVA AQUI, e a medição é do mesmo dia: o ouvinte do
    piloto só olha um alvo que case com o `closest` de `manda_do_alvo`
    (`hefesto_vivo.py:367`), e os 21 `<select>` tinham só `data-campo`,
    `data-linha` e `data-hef-alvo`. O `change` morria no navegador:

        ANTES  (o que a pintura pôs) : Botão direito
        CLIQUE (a escolha dela)      : F11
        +1500 ms (três tiques)       : Botão direito

    O `data-gesto` que o gerador passou a pôr (`aba06.LINHA_DE_BOTAO`) é o que
    abre este caminho.

    A RECUSA É DE CLIQUE INVÁLIDO (`ValueError`), e não do produto: um rótulo
    que o produto não conhece só chega aqui se o desenho andou sem o gerador —
    a lista da tela e a do produto saem do mesmo `core/acoes_de_botao`.

    O QUE ELE DEVOLVE é a própria linha, pelo endereço da pintura. Na tela isso
    é um no-op (o `<select>` já está nela), e é de propósito: um gesto que volta
    com `None` não toca o DOM (`hefesto_vivo._deu_certo`) e sai do relato como
    "aplicado" sem nada a mostrar. Devolvendo o endereço, o desfecho do gesto
    passa a ser verificável — e a linha volta ao lugar certo se a página tiver
    sido repintada entre o clique e a volta da thread.
    """
    botao = str(o.get("linha") or o.get("campo") or "").removeprefix(PREFIXO_DA_ACAO)
    if botao not in acoes.BOTOES:
        raise ValueError(
            f"linha-de-botao: o clique não disse qual botão (veio {botao!r}). O "
            "`data-linha` de cada `<select>` é o id do botão, e ele vem do "
            "gerador — sem ele não há o que anotar.")
    rotulo = str(o.get("valor") or o.get("rotulo") or "").strip()
    if acoes.token_do_rotulo(rotulo) is None:
        raise ValueError(
            f"{_nome_do_botao(botao)}: a opção {rotulo!r} não é do produto. A "
            "lista da tela e a do produto saem do mesmo lugar "
            "(`core/acoes_de_botao.ACOES`) — se divergiram, foi o desenho que "
            "andou sem o gerador.")
    campo = f"{PREFIXO_DA_ACAO}{botao}"
    do_perfil = _linhas_dos_botoes(perfil.ativo((ctx.state or {}).get("active_profile")))
    if do_perfil.get(campo) == rotulo:
        # ELA VOLTOU AO QUE O PERFIL JÁ GUARDA. Não há nada a segurar, e segurar
        # assim mesmo deixaria a trava presa por uma escolha que não é escolha.
        _MEXENDO.pop(campo, None)
    else:
        _MEXENDO[campo] = rotulo
    return {"mesa": {campo: rotulo}}


@gesto("06-navegacao.html", "fechar-definicoes")
def fechar_definicoes(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """O fechar e o "Cancelar" da tela de definições: LARGAM o que ela não guardou.

    Este é o "sair" da decisão dela — *"até guardar ou sair"*. Os dois botões
    fecham a pop-up sozinhos, pelo `:target` do CSS; o que faltava era o Python
    saber que ela desistiu. Sem isso a trava das 21 linhas ficaria presa depois
    do "Cancelar", e a tela continuaria mostrando escolhas que ninguém vai
    guardar.

    ELE DEVOLVE A TABELA DO PERFIL na hora, e não espera o tique: um "Cancelar"
    que só desfaz meio segundo depois deixa a pessoa vendo a própria escolha
    fantasma na reabertura da tela.

    SEM PERFIL ATIVO ele ainda solta a trava — largar não depende de haver o que
    ler — e devolve o de fábrica, que é o que `_linhas_dos_botoes({})` dá.
    """
    _largar_o_que_ela_mexeu()
    return {"mesa": _linhas_dos_botoes(
        perfil.ativo((ctx.state or {}).get("active_profile")))}


def _perfil_ativo_ou_recusa(ctx: Contexto) -> str:
    """O nome do perfil ativo, ou a recusa com o motivo.

    OS ATALHOS SÃO DO PERFIL, não da máquina (`profiles/schema.py`), e essa é a
    frase que a recusa precisa carregar: sem ela, "não deu" vira mistério.
    """
    nome = str((ctx.state or {}).get("active_profile") or "").strip()
    if not nome:
        raise RuntimeError(
            "não há perfil ativo agora, e o que cada botão faz é do perfil — não "
            "da máquina. Escolha um perfil na aba Perfis e tente de novo.")
    return nome


@gesto("06-navegacao.html", "guardar-definicoes")
def guardar_definicoes(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Guardar" das 21 linhas de *o que cada botão faz*. `Profile.button_actions`.

    ELE PASSOU A TER DONO EM 01/09/2026, por decisão dela: *"ganha campo. essa é
    a parte das features que precisam ou serem ajustadas ou desenvolvidas."* O
    que o segurava era medido e verdadeiro — a tela deixava escolher 21 linhas e
    o perfil alcançava 9 —, e a cura foi o campo nascer, não o botão fingir.

    DE ONDE VEM O QUE ELE GRAVA: da `forma`, que o piloto recolhe quando o botão
    traz `data-hef-forma`. O ouvinte manda o valor do elemento CLICADO, e o
    Guardar é outro elemento — sem a forma, ele não teria como saber o que está
    escolhido em cada linha, e era por isso que só podia recusar.

    SÓ O QUE MUDOU VAI PARA O DISCO. Gravar as 21 sempre encheria o perfil de
    linhas iguais ao padrão, e no dia em que o padrão do produto mudasse o perfil
    congelaria o padrão VELHO sem ninguém ter escolhido isso. `button_actions`
    guarda diferença, e é o que o `None` do campo quer dizer: herda.

    O CAMPO ZERADO É `None`, e nunca `{}`: `None` é o mesmo estado de um perfil
    que nunca foi editado, e `{}` seria "nenhum botão faz nada". Depois das duas
    recusas abaixo, o único caminho que ainda grava `None` é o perfil que já
    tinha `{}` — a normalização de um estado que o esquema não pretende.

    FATO SUBSTITUÍDO (02/09/2026, corretivo): esta linha dizia *"e quando nada
    mudou, ele grava `None` — que apaga o campo"*. **Nada mudou deixou de gravar
    coisa alguma.** Com o perfil guardando escolhas, a trava recusa; com o perfil
    já igual à tela, a recusa nova diz que já está guardado. Nenhum dos dois
    chega ao disco.

    ELE ERA UM APAGADOR COM RÓTULO DE "GUARDAR", e isso foi medido em
    02/09/2026: as 21 opções que a tela mostrava eram **exatamente**
    `acoes.padrao()`, logo `diferentes` saía `{}` e o gesto gravava
    `button_actions = None` — apagando, em silêncio, qualquer escolha que o
    perfil dela guardasse. O botão dizia "Guardar" e fazia o contrário.

    FATO SUBSTITUÍDO, e ele estava escrito AQUI: *"as 21 `<select>` têm
    `data-linha` e nenhum `data-campo`, então nada nunca as pintou"*. Isso valia
    contra a página publicada da manhã. **Ela mandou publicar** no mesmo dia
    (commit `70b58116`), e a página publicada de agora traz `data-campo` e
    `data-hef-alvo="valor"` nas 21 — medido com dublê: os 21 campos saem
    PRODUTO, e o valor que a tela mostra é o do perfil.

    O QUE SOBRA DA TRAVA, e por que ela FICA: a forma toda no de fábrica com o
    perfil guardando escolhas deixou de ser o estado permanente e virou uma
    JANELA — os 500 ms entre a página carregar e o primeiro tique pintar
    (`hefesto_vivo.TIQUE_MS`). Um clique ali dentro ainda leria o desenho como
    se fosse a escolha dela, e ainda apagaria. Enquanto o piloto não marcar o
    que já foi pintado, esta trava é o que separa "ela zerou" de "a tela ainda
    não falou".

    O QUE A TELA OFERECE E O PRODUTO NÃO ATENDE **é dito, não engolido**: os
    comandos "Abrir a Steam", "Sair do modo jogo" e "Escolher um programa…", os
    dois papéis de eixo pedidos a um botão, e os gatilhos L2/R2, que são espelho
    do cross e do triangle (`uinput_mouse._resolve_emulated_set`). O gesto GRAVA
    o resto e LEVANTA nomeando o que não pousou — quem clicou fica sabendo, em
    vez de descobrir pelo botão que não responde.
    """
    nome = _perfil_ativo_ou_recusa(ctx)
    forma = o.get("forma")
    if not isinstance(forma, dict) or not forma:
        raise RuntimeError(
            "não consegui ler as linhas da tela. O botão precisa do "
            "`data-hef-forma` para o piloto recolher os campos — se ele sumiu do "
            "desenho, o Guardar não tem o que gravar.")

    escolhas: dict[str, str] = {}
    nao_reconhecidas: list[str] = []
    for botao, rotulo in forma.items():
        if botao not in acoes.BOTOES:
            continue
        token = acoes.token_do_rotulo(str(rotulo))
        if token is None:
            nao_reconhecidas.append(f"{_nome_do_botao(botao)}={rotulo!r}")
            continue
        escolhas[botao] = token
    if nao_reconhecidas:
        raise ValueError(
            "estas linhas trazem uma opção que o produto não conhece: "
            + ", ".join(nao_reconhecidas)
            + ". A lista da tela e a do produto saem do mesmo lugar "
              "(`core/acoes_de_botao.ACOES`) — se divergiram, foi o desenho que "
              "andou sem o gerador.")

    de_fabrica = acoes.padrao()
    diferentes = {b: a for b, a in escolhas.items() if de_fabrica.get(b) != a}

    loader = perfil._com_o_src()
    prof = loader.load_profile(nome)
    novo = diferentes or None
    # NADA A GRAVAR **É UM DESFECHO, E ELE FALA** — 02/09/2026, corretivo. Aqui
    # havia um `return` seco, e ele era o outro lado da recusa logo abaixo: a
    # trava manda "espere a tabela se preencher e clique de novo", e o segundo
    # clique caía exatamente NESTE `return` — sem gravar, sem chamar e sem uma
    # palavra. Encenado com dublê de disco e ponte muda:
    #
    #     1º clique (tabela ainda no desenho)  → RuntimeError, com a frase
    #     2º clique (tabela cheia, = ao perfil) → voltou SEM levantar, gravou 0
    #
    # Uma recusa que INSTRUI a repetir o gesto e depois não responde nada é pior
    # que uma recusa seca: ela promete que a segunda tentativa funciona. E um
    # gesto que devolve `None` não toca o DOM (`hefesto_vivo._deu_certo`), logo
    # o segundo clique era o botão que responde calado — o defeito que esta casa
    # mais persegue.
    if prof.button_actions == novo:
        guardadas = ("nenhuma escolha sua: as 21 linhas estão no de fábrica"
                     if not novo else
                     f"{len(novo)} escolha(s) sua(s)")
        # NADA PENDENTE: a tela e o disco dizem a mesma coisa, logo não há
        # escolha em curso a segurar. Soltar aqui é o que impede a trava de
        # ficar presa por uma linha que ela desfez à mão.
        _largar_o_que_ela_mexeu()
        raise RuntimeError(
            f"não havia o que guardar — o perfil “{nome}” já tem exatamente o "
            f"que a tabela mostra ({guardadas}). Está guardado. Para mudar "
            "alguma coisa, troque a linha e clique aqui de novo; para voltar "
            "tudo ao de fábrica, use o “Voltar ao padrão” ao lado.")
    # A TRAVA CONTRA O APAGADOR — 02/09/2026. "Nada diferente do de fábrica" só
    # quer dizer "ela zerou as 21 linhas" DEPOIS que as 21 linhas mostraram o
    # que o perfil guarda. Elas mostram desde que a página foi publicada, mas
    # não no primeiro instante: entre a carga e o primeiro tique há 500 ms
    # (`hefesto_vivo.TIQUE_MS`) em que a tela ainda é o desenho, e nessa janela
    # esta forma quer dizer outra coisa — *o piloto releu o desenho*.
    #
    # E ZERAR TEM BOTÃO PRÓPRIO, a dois centímetros: "Voltar ao padrão"
    # (`padrao-definicoes`), que zera dizendo e ainda pede confirmação. Um
    # "Guardar" que apaga em silêncio é o botão que responde calado — o defeito
    # que esta casa mais persegue.
    #
    # E ELA DEIXOU DE SER CEGA — 02/09/2026, segunda correção. A trava não tinha
    # como distinguir *"ela zerou as 21 linhas"* de *"o piloto releu o desenho"*,
    # e por isso recusava as duas. Com a decisão dela sobre o repinte, a
    # diferença passou a estar ESCRITA: `_MEXENDO` só tem linha que ELA trocou,
    # pelo gesto `linha-de-botao`. Vazio, a forma é o que a pintura pôs — e a
    # trava vale. Cheio, a forma é escolha dela — e zerar de propósito é um
    # pedido legítimo, que o "Guardar" atende.
    #
    # ISSO CURA A FRASE QUE ENSINAVA UM CAMINHO INEXISTENTE. A recusa mandava
    # *"espere a tabela se preencher e clique de novo"*, e trocar a linha nunca
    # chegava ao Guardar: o tique reescrevia a escolha em ≤1,5 s. Agora chega.
    if novo is None and prof.button_actions and not _MEXENDO:
        raise RuntimeError(
            "não guardei: as 21 linhas da tela estão todas no de fábrica, e o "
            f"perfil “{nome}” guarda "
            f"{len(prof.button_actions)} escolha(s) sua(s). Gravar isto as "
            "apagaria. A tela leva meio segundo para mostrar o que o perfil "
            "guarda; se você clicou antes disso, o que estava na tela era o "
            "desenho, e não a sua escolha. Espere a tabela se preencher — para "
            "voltar tudo ao de fábrica de propósito, use o “Voltar ao padrão” "
            "ao lado.")
    perfil.gravar_e_reaplicar(prof.model_copy(update={"button_actions": novo}), ctx, p)
    # GUARDADO É O FIM DA EDIÇÃO. A partir daqui o perfil diz o que a tela diz,
    # e o tique volta a mandar na tabela — que é a outra metade de *"até guardar
    # ou sair"*.
    _largar_o_que_ela_mexeu()

    _, _, sem_dono = acoes.resolver(novo)
    if sem_dono:
        raise RuntimeError(
            "guardei o que o produto sabe fazer, e estas linhas ficaram sem "
            "quem as atenda: " + ", ".join(_nome_do_botao(b) for b in sem_dono)
            + ". Elas estão no perfil e não acendem nada hoje — é feature que "
              "falta, não erro seu.")


@gesto("06-navegacao.html", "padrao-definicoes")
def padrao_definicoes(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Voltar ao padrão" das 21 linhas de *o que cada botão faz*.

    O QUE ELE FAZ: grava `key_bindings = None` no perfil ATIVO e manda o daemon
    reaplicá-lo. `None` não é "vazio" — o esquema o define como *"herda
    `DEFAULT_BUTTON_BINDINGS` do core"* (`profiles/schema.py:985`), e `{}` é
    outra coisa (teclado silencioso). Escrever `{}` aqui devolveria um controle
    MUDO com o botão dizendo "de fábrica".

    E ELE DEVOLVE AS VINTE E UMA, ao contrário do que parece. Contadas na tela e
    no fonte, em 01/09/2026:

        9 linhas   `key_bindings` as alcança — l1, r1, l3, r3, options, create
                   e as três regiões do touchpad (`core/keyboard_mappings.py:41`)
        12 linhas  mapas FIXOS do produto — `BUTTON_TO_UINPUT`, `DPAD_TO_KEY` e
                   `EDGE_KEY_MAP` (`integrations/uinput_mouse.py:93,99,105`),
                   mais o L2/R2 e a DIREÇÃO dos analógicos, que binding nenhum
                   alcança

    As 12 não têm onde ser mudadas — logo estão **sempre** de fábrica, e zerar as
    9 devolve a tabela inteira ao de fábrica. É por isso que este botão fecha
    inteiro, enquanto o "Guardar" ao lado dele não fecha: guardar 9 de 21
    escolhas e perder 12 caladas é o botão que responde calado.

    ELE ZERA OS DOIS CAMPOS desde 01/09/2026: o `key_bindings` (as nove teclas)
    e o `button_actions` (as vinte e uma linhas da tela, que nasceu no mesmo
    dia). Zerar só um deixaria a tabela metade de fábrica, com o botão dizendo
    o contrário.

    O ALVO É O PERFIL ATIVO, e ele é dito: os dois são campo de perfil
    (`profiles/schema.py`), não da máquina. Sem perfil ativo o botão RECUSA —
    devolver ao padrão "o perfil nenhum" não quer dizer nada.

    A GRAVAÇÃO É A DA CASA: `perfil.gravar_e_reaplicar`, a mesma que a aba
    Perfis usa. O `save_profile` grava em disco e o `profile.switch` reaplica se
    for o ativo.

    FATO SUBSTITUÍDO, e é o que destravou este botão: o `SEM_GESTO` abaixo dizia
    que "gravar perfil não tem método". Tem — `profiles/loader.save_profile`, e
    o `a10_perfis` já o usava desde a mesma leva que escreveu a frase.
    """
    nome = _perfil_ativo_ou_recusa(ctx)
    loader = perfil._com_o_src()
    prof = loader.load_profile(nome)
    # OS DOIS CAMPOS, e não só um — 01/09/2026, quando o `button_actions`
    # nasceu. O perfil passou a guardar o que cada botão faz em DOIS lugares:
    # o `key_bindings` (as nove teclas, da FEAT-KEYBOARD-PERSISTENCE-01) e o
    # `button_actions` (as vinte e uma linhas da tela). Um "Voltar ao padrão"
    # que zerasse só o primeiro deixaria a tabela metade de fábrica e metade
    # não — e o botão diria "de fábrica" sobre isso.
    if prof.key_bindings is None and prof.button_actions is None:
        # JÁ ESTÁ DE FÁBRICA. Gravar de novo trocaria a data do arquivo e faria
        # o daemon reaplicar um perfil idêntico — barulho sem efeito, e um
        # `profile.switch` no meio de uma partida não é de graça. **Mas não
        # fazer nada não é não dizer nada:** até 02/09/2026 este ramo era um
        # `return` seco, e a régua do aparelho o lia como "disse aplicado e
        # nada mudou" — indistinguível de um botão que mentiu. Agora ele
        # RECUSA DIZENDO, que é o desfecho verdadeiro: não havia o que voltar.
        # Nada é gravado e o daemon continua sem ser incomodado.
        _largar_o_que_ela_mexeu()
        raise RuntimeError(
            f"não havia o que voltar — o perfil “{nome}” já está no de fábrica "
            "nas 21 linhas de o que cada botão faz. Não gravei nada e não "
            "incomodei o daemon.")
    perfil.gravar_e_reaplicar(
        prof.model_copy(update={"key_bindings": None, "button_actions": None}), ctx, p)
    # "VOLTAR AO PADRÃO" TAMBÉM É FIM DE EDIÇÃO: o perfil foi zerado, e segurar
    # escolhas pendentes por cima disso faria a tabela mostrar o contrário do
    # que o botão acabou de fazer.
    _largar_o_que_ela_mexeu()


#: OS OITO QUE CONTINUAM SEM DONO, com o motivo MEDIDO de cada um — o
#: inventário honesto do que falta, no lugar de um botão que responde calado. O
#: piloto os recusa PELO NOME (`[gesto sem dono] 06-navegacao.html · <nome>`), e
#: por isso as chaves aqui são os nomes que ele vai imprimir, um por um: os dois
#: `bignum` sem dono viram quatro linhas (`-menos` e `-mais`), porque são quatro
#: botões.
#:
#: ERAM QUATORZE, depois TREZE. O `teclado` saiu na segunda leva — o que o
#: segurava não era falta de método, era o piloto não mandar o valor de um
#: `<select>`. O `padrao-definicoes` saiu na TERCEIRA, e o que o segurava era
#: um FATO ERRADO escrito aqui: que gravar perfil não tinha método. Tinha, e o
#: `a10_perfis` já o usava. As duas saídas têm a mesma forma — o que prendia o
#: botão não era o produto, era o que estava escrito sobre ele.
#:
#: -------------------------------------------------------------------------
#: `mouse.emulation.restore` NÃO virou botão, e a segunda leva reconfirmou a
#: recusa com uma razão MAIOR que a da primeira. Três coisas, e a terceira é a
#: que fecha a porta:
#:
#: 1. o handler diz o lugar dele com todas as letras — *"entra na transição de
#:    modo (`app/actions/mode_transition.py`), **nunca em um botão solto**"*
#:    (`daemon/ipc_handlers.py:5011`);
#: 2. ele devolve a preferência PERSISTIDA — não "o de fábrica" nem "o que a
#:    tela mostra" —, então pendurá-lo num "Voltar ao padrão" faria o botão
#:    prometer uma coisa e fazer outra;
#: 3. **ele LIGA o mouse.** `restore_mouse_preference`
#:    (`daemon/lifecycle.py:1402`) chama `set_mouse_emulation(pref, …)` e, com a
#:    preferência nunca gravada, `pref` vira `True` por default (`:1403`) — o
#:    cursor DELA passa a andar pelo controle, e o gamepad virtual cai junto
#:    (`:1359`). Isso o põe na mesma prateleira do gesto `modo`, que já está em
#:    `hefesto_vivo.PERIGOSOS` justamente para a prova botão a botão não o
#:    clicar. Ligá-lo aqui criaria um gesto perigoso NOVO **fora** daquela
#:    lista, e a lista mora num arquivo que esta aba não pode tocar.
SEM_GESTO = {
    "navegacao-interna": "navegar a janela do Hefesto com o controle não tem "
                         "método no daemon — nenhum dos 39, e o "
                         "`core/disputa_de_botao.py` que as sprints citam não "
                         "existe no disco",
    "modo-steam": "não há método de Modo Steam no daemon — nenhum dos 39",
    # OS QUATRO DE VELOCIDADE SAÍRAM DAQUI porque saíram da TELA — 01/09/2026,
    # decisão dela ao ler a medição: *"só ajustar o texto e deixar rolagem,
    # ajustar ali pra deixar um só se for o caso pra ambos"*.
    #
    # O que estava escrito aqui era: o cursor do touchpad sai do MESMO
    # `mouse_speed` (`uinput_mouse.py:446`), e rolagem por dois dedos não existe
    # (`_emit_scroll` lê só o analógico direito). As duas linhas do desenho
    # ofereciam DOIS números onde o produto tem UM — e a cura foi no desenho, não
    # num gesto que fingisse o segundo. As dicas passaram a ler a faixa do
    # produto, que também estava errada nas duas ("De 1 a 10", quando o cursor
    # vai a 12 e a rolagem a 5).
    # FATO SUBSTITUÍDO (segunda leva): dizia "os cinco combos moram em
    # `key_bindings` do perfil". Não moram — `key_bindings` são os nove BOTÕES
    # do `DEFAULT_BUTTON_BINDINGS`, e combo nenhum aparece lá.
    # FATO AFINADO (terceira leva, 01/09/2026): esta entrada dizia que "método
    # de IPC nenhum escreve" o `ps_button_action`. Escreve — `daemon.reload`
    # aceita `config_overrides` com qualquer campo do `DaemonConfig`
    # (`ipc_handlers.py:4556`). O que ele NÃO faz é gravar: o handler roda
    # `replace(config, **overrides)` e `reload_config(...)` e para aí (`:4567`),
    # então a escolha morre no próximo start do daemon. E o `ps_button_action` é
    # do PS SOLO, não dos combos — a tabela desta tela é dos cinco COMBOS.
    "acao-do-gesto": "os cinco combos são callbacks montados em código "
                     "(`daemon/subsystems/hotkey.py:86,414`), não dado. O "
                     "vizinho deles, o `config.ps_button_action` do PS solo, "
                     "tem escritor VIVO (`daemon.reload` com `config_overrides`) "
                     "e nenhum que grave em disco — e ele nem é o que esta "
                     "tabela oferece trocar",
    "padrao-da-aba": "a frase do botão promete a aba INTEIRA — as opções de "
                     "ativação, os 5 gestos e as 21 linhas das duas telas. Só as "
                     "duas velocidades têm rota (`mouse.emulation.set` "
                     "speed-only); as outras três promessas não têm nenhuma, e "
                     "um 'Voltar ao padrão' que devolve dois números de cinco "
                     "coisas é um botão que responde calado sobre as outras três",
    # `guardar-definicoes` SAIU DAQUI em 01/09/2026, e não porque a medição
    # estivesse errada: ela estava certa. A tela deixava escolher 21 linhas e o
    # perfil alcançava 9, e guardar 9 de 21 caladas seria o botão que responde
    # calado. O que mudou foi o PRODUTO — decisão dela ao ler a medição:
    # *"ganha campo. essa é a parte das features que precisam ou serem ajustadas
    # ou desenvolvidas."* `Profile.button_actions` nasceu, o
    # `core/acoes_de_botao` virou o dono do vocabulário e do padrão, e o device
    # de mouse passou a obedecer.
    #
    # O QUE AINDA NÃO PousA está DITO, não engolido: os três comandos
    # ("Abrir a Steam", "Sair do modo jogo", "Escolher um programa…"), os dois
    # papéis de eixo pedidos a um botão, e os gatilhos L2/R2, que são espelho do
    # cross e do triangle. O gesto grava o resto e LEVANTA nomeando esses.
    "guardar-remapeamento": "o remapeamento botão-por-botão não tem sequer campo "
                            "no perfil, quanto mais método de IPC",
    "padrao-remapeamento": "idem, ao contrário",
    "guardar-ponto": "'Estilo de Jogo' não existe em campo, widget ou preset "
                     "nenhum do produto — está escrito em "
                     "`app/actions/perfis_web.py`, que já mediu isto para a aba "
                     "Perfis. O `point_and_click` que existe é um PERFIL em "
                     "disco, não um estilo, e gravar perfil não tem método",
}


#: OS DOIS QUE GRAVAM PERFIL E NÃO TÊM ECO — 02/09/2026, à tarde, medido com
#: dublê da ponte e dublê do disco (`--prova-no-aparelho` NÃO foi usado: há
#: controles na mesa dela e a leva inteira está proibida de tocar o aparelho).
#:
#: O `state_full` do daemon publica `active_profile` — o NOME — e mais nada do
#: conteúdo do perfil. Nem `button_actions` nem `key_bindings` aparecem entre as
#: chaves do payload (`daemon/ipc_handlers.py:2493`). Logo a régua que compara o
#: estado do daemon antes e depois do clique não tem como ver o efeito destes
#: dois, por mais que eles funcionem — e eles funcionam:
#:
#:     gesto                               desfecho          chamou      gravou
#:     guardar-definicoes (linha trocada)  ACEITOU           switch      1 perfil
#:     guardar-definicoes (forma de fábr.) RECUSA dizendo    NADA        0
#:     guardar-definicoes (= ao perfil)    RECUSA dizendo    NADA        0
#:     padrao-definicoes                   ACEITOU           switch      1 perfil
#:     padrao-definicoes (já de fábrica)   RECUSA dizendo    NADA        0
#:
#: A PROVA DELES É O ARQUIVO — mesma forma do `teto-da-vibracao` da aba Conexões
#: (`a08_conexoes.SEM_ECO`), que também grava no perfil: efeito vivo pelo
#: `profile.switch` do `gravar_e_reaplicar`, e nenhum eco. Quem cobra são
#: `test_a_06_nao_manda_para_o_vazio.py` e
#: `test_o_padrao_dos_atalhos_volta_de_fabrica.py`, contra o disco.
#:
#: FATO SUBSTITUÍDO — 02/09/2026, corretivo. Aqui estava escrito que *"a última
#: linha da tabela é o que os pôs aqui"*: `padrao-definicoes` com o perfil já de
#: fábrica saindo pelo `return` de "nada a fazer", sem gravar, sem chamar e sem
#: levantar. **Isso caducou porque o `return` mudo morreu** — os dois ramos de
#: "nada a fazer" (aqui e no `guardar-definicoes`) passaram a RECUSAR DIZENDO, e
#: `recusou dizendo` vem ANTES de `aceito sem eco` na ordem de `classe()`
#: (`hefesto_vivo.py:1492`). Logo esta declaração NÃO cobre mais o caso do
#: não-fazer-nada calado: ele voltou a ser visível para a régua do aparelho, com
#: nome próprio. O que `SEM_ECO` cobre é só o que está escrito acima — o daemon
#: não publica conteúdo de perfil, e o efeito das linhas "ACEITOU" mora no disco.
#:
#: O `teclado` NÃO ENTRA, e a diferença é medida: ele chama
#: `keyboard.emulation.set`, e `keyboard_emulation.enabled` VOLTA no
#: `state_full` — é o que pinta o `teclado-estado`. Declará-lo aqui calaria a
#: régua sobre um caminho que ela consegue medir.
#:
#: OS DOIS QUE NÃO TÊM ASSUNTO NENHUM NO DAEMON — 02/09/2026, e eles são de
#: outra espécie que os dois acima. `linha-de-botao` e `fechar-definicoes` não
#: chamam a ponte, não escrevem em disco e não pretendem: os dois mexem no que a
#: PINTURA vai fazer no tique seguinte, e nada mais. Não é "o daemon não publica
#: este assunto" — é "não há assunto do daemon", que é mais forte.
#:
#: SEM ESTA LINHA a régua do aparelho os leria como *"disse aplicado e nada
#: mudou"* (`hefesto_vivo.py:1637`), que é o rótulo dos botões que mentem — e
#: aqui seria a régua acusando o comportamento CERTO. Declará-los sem prova
#: seria o inverso: lápide escondendo defeito. A prova deles não é o estado do
#: daemon, é o efeito na pintura, e ela roda no CI, sem janela:
#: `test_a_06_a_escolha_dela_sobrevive_ao_tique.py`, que arranca a trava e vê a
#: tabela voltar a desfazer a escolha em um tique.
#:
#: TUPLA, e não dicionário: o piloto faz `set(getattr(mod, "SEM_ECO", ()))` e as
#: seis abas que declaram usam tupla. O motivo mora no comentário, que é onde
#: ele cabe inteiro — `SEM_ECO` sem razão escrita é lápide para esconder defeito.
SEM_ECO = ("guardar-definicoes", "padrao-definicoes",
           "linha-de-botao", "fechar-definicoes")


PONTE = {"chamar"}
METODOS = {"mouse.emulation.set", "keyboard.emulation.set"}


PAGINA = "06-navegacao.html"
PISO_DA_ABA = 8


def _prova(nome: str, clique: dict[str, Any], chama: list[Any]) -> dict[str, Any]:
    """Uma linha do `PROVAS`, para a chave da régua ser escrita UMA vez.

    Cinco dicionários escritos por extenso repetiam a chave da página cinco
    vezes — e cada repetição custava um marcador `# (noqa-acento)` (a chave é do
    contrato da régua, não texto em português) e um aviso do ruff sobre ele. Um
    construtor paga o preço uma vez só.
    """
    # A primeira chave é o NOME do contrato da régua, não texto em português —
    # por isso a linha leva o marcador de isenção, e uma vez só. (Escrever a
    # palavra AQUI, no comentário, também acusava: a régua de acentuação não
    # distingue prosa de identificador nem quando o identificador é o assunto.)
    return {"pagina": PAGINA, "gesto": nome,  # (noqa-acento) chave do contrato
            "clique": clique, "chama": chama}


#: O `ctx` da régua não tem `mouse_emulation`, então cada gesto parte do padrão
#: do produto: 6 no cursor e 1 na rolagem. É de propósito — é o mesmo chão que a
#: tela mostra enquanto o daemon ainda não falou.
#:
#: O `rolagem-menos` manda `0`, e não `1`: a faixa tem UM dono e é o daemon
#: (`max(1, min(5, …))`, `daemon/lifecycle.py:1431`). Apará-la aqui seria a
#: segunda verdade, e é ela que envelhece calada no dia em que a faixa mudar.
_MOUSE = "mouse.emulation.set"
PROVAS = [
    _prova("modo", {},
           [("chamar", [_MOUSE], {"enabled": True, "origin": "manual"}),
            ("chamar", ["keyboard.emulation.set"], {"enabled": True})]),
    _prova("vel-cursor-mais", {"gesto": "vel-cursor-mais"},
           [("chamar", [_MOUSE], {"speed": 7, "origin": "manual"})]),
    _prova("vel-cursor-menos", {"gesto": "vel-cursor-menos"},
           [("chamar", [_MOUSE], {"speed": 5, "origin": "manual"})]),
    _prova("rolagem-mais", {"gesto": "rolagem-mais"},
           [("chamar", [_MOUSE], {"scroll_speed": 2, "origin": "manual"})]),
    _prova("rolagem-menos", {"gesto": "rolagem-menos"},
           [("chamar", [_MOUSE], {"scroll_speed": 0, "origin": "manual"})]),
    # AS DUAS PONTAS DA LISTA DO TECLADO, e as duas provam a mesma coisa por
    # lados opostos: que o `valor` do `<select>` decide o bool. O `clique` traz
    # `valor` porque é ele que o piloto manda desde 01/09 — `texto`, num
    # `<select>`, é a lista inteira concatenada, e foi essa confusão que deixou
    # esta lista sem dono na primeira leva.
    #
    # A OPÇÃO SEM DONO NÃO TEM PROVA AQUI de propósito: `PROVAS` só sabe cobrar
    # chamada, e o certo para "Só dentro do jogo" é NÃO chamar nada. Ela é
    # provada pela mordida, no relato, e pelo teste da recusa.
    _prova("teclado", {"valor": TECLADO_SO_FORA},
           [("chamar", ["keyboard.emulation.set"], {"enabled": True})]),
    _prova("teclado", {"valor": TECLADO_DESATIVADO},
           [("chamar", ["keyboard.emulation.set"], {"enabled": False})]),
]
