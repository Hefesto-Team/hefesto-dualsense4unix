#!/usr/bin/env python3
"""O pacote da aba `03` Gatilhos — e ele nasceu ERRADO, corrigido em 01/09/2026.

O QUE ESTAVA ESCRITO AQUI, e era meu, e estava errado:

    "o modo escolhido      NÃO EXISTE no state    ← sem dono
     o efeito pronto       NÃO EXISTE no state    ← sem dono
     os ajustes do modo    NÃO EXISTEM no state   ← sem dono"

A parte factual continua verdadeira: o `state_full` do daemon **não** publica
`triggers`, e o DualSense não devolve o modo em que está — gatilho adaptativo é
comando de ida. O que estava errado era a CONCLUSÃO: dali eu tirei "não tem
dono" e pintei quatro travessões.

ELA PEGOU COM UMA PERGUNTA SÓ: *"vc tá corrigindo na origem esses problemas que
tá relatando né?"* Não estava. O dado tem dono, e são dois, os dois já no
produto que ela usa:

    profiles/schema.py       `triggers.left/right` → `mode` e `params`
    app/actions/trigger_specs.py   `PRESETS`: `name` (disco) → `label` (tela)
                                   e cada `param` com nome, faixa e padrão

MEDIDO NO DISCO DELA, perfil "Ação", em 01/09/2026::

    triggers.left  = {"mode": "Rigid",     "params": [0, 180]}
    triggers.right = {"mode": "Vibration", "params": [3, 8, 20]}

Cinco dos 33 perfis dela têm gatilho configurado. Mostrar `—` ali era apagar da
tela uma escolha que ela salvou.

O QUE AINDA NÃO TEM DONO, e agora a lista é honesta: nada desta aba. O que muda
é a NATUREZA do valor — ele é o que está **salvo no perfil**, não o que está
**aceso no plástico**, e essas são coisas diferentes. Como o aparelho não
devolve a segunda, a primeira é a melhor verdade disponível, e a tela diz de
qual está falando.
"""
from __future__ import annotations

import re
from typing import Any

from . import Contexto, jogador_de, perfil, registrar

#: Nada. E a lista vazia é uma AFIRMAÇÃO, não um esquecimento: cada valor desta
#: aba tem dono medido, e a régua de cobertura conta este zero junto com os
#: `pintados` — um pacote que pinta 0 e declara 0 é reprovado por
#: `test_o_despachante_serve_as_dez.py`, de propósito.
SEM_DONO: dict[str, str] = {}

#: O LADO NA TELA E O LADO NO DISCO. A tela usa `e`/`d` (o L2 e o R2 do
#: desenho); o perfil usa `left`/`right`. Dois vocabulários, uma tradução, num
#: lugar só — a regra da casa é que o que tem dono não se digita.
LADOS = {"e": "left", "d": "right"}

#: COMO A GTK CHAMA CADA GATILHO NUMA FRASE PARA ELA, copiado letra por letra de
#: `triggers_actions._toast_trigger`. Ele existe lá por uma cura com nome — a
#: TRG-01: a barra de status dizia `"LEFT -> Off"`, trocando a fala dela (o
#: gatilho que ela clicou) por id interno mais o lado em inglês. Escrever `"L2"`
#: aqui seria a segunda verdade sobre a mesma peça, e a tela nova
#: reintroduziria o defeito por outro atalho.
NOME_DO_LADO = {"left": "Gatilho esquerdo (L2)", "right": "Gatilho direito (R2)"}

#: O TRAVESSÃO É DO PILOTO, e está aqui só para a régua poder cobrá-lo sem
#: repetir a string: `hefesto_vivo.escrever()` troca `''` por `—` antes de
#: escrever. Emitir `''` é dizer "esta casa não tem valor"; emitir `'—'` seria
#: esta aba inventando a marca de vazio de outra camada.
VAZIO = ""


# ---------------------------------------------------------------------------
# O QUE A PÁGINA TEM, LIDO DA PÁGINA — e é a cura do defeito D3.
#
# O DEFEITO, medido em 02/09/2026 com o perfil `meu_perfil` (`L2: mode='Off'
# params=[]`, `R2: idem`) e a foto da aba aberta: a tela mostrava, na coluna do
# P1, `Força 7 · Frequência 4 · Início do curso 25 · Fim do curso 230` — e, três
# linhas acima, `Modo: Desligado`. Os quatro números eram do MOCKUP.
#
# A PRIMEIRA CURA ENDEREÇOU A CASA VAZIA: o pacote passou a escrever `''` nas
# quatro barras que o modo não usa, e a tela deixou de mostrar `Força 7` debaixo
# de `Desligado`. Ela funcionava, e **saiu hoje** — porque tratava o sintoma.
#
# A CURA DE AGORA É A DECISÃO DELA DE 02/09/2026: *"os ajustes viram lista e a
# caixa acompanha o modo"*. Quem decide quantas barras existem deixa de ser a
# PÁGINA e passa a ser o MODO — que é o único que sabe. `Off` tem zero,
# `Machine` tem seis, `MultiPositionVibration` tem onze; a página reservava
# quatro e duas, e por isso *escondia* sete das onze. A caixa inteira passa a
# ser um BLOCO trocado pelo produto (`blocos:`), que é o mecanismo que esta casa
# já tem para o que muda de TAMANHO com o dado.
#
# A PÁGINA CONTINUA SENDO LIDA, e por outra pergunta: quantas casas ela ainda
# CRAVA. É o que diz se o desenho novo já foi publicado, e é a mesma forma do
# `False` que o `barra_por_largura` tinha antes — trabalho de gerador esperando
# a palavra dela, nunca pacote incompleto. Digitar `4` e `2` aqui criaria a
# segunda cópia de um número que o gerador decide.
# ---------------------------------------------------------------------------
PAGINA = "03-gatilhos.html"

_CASA = re.compile(r'data-campo="aj-nome-(?P<lado>[ed])-(?P<i>\d+)"')

#: O LUGAR QUE O DESENHO JÁ DÁ POR VAZIO. `data-controle` e `data-conectado`
#: saem no MESMO elemento, nesta ordem, e o `[^>]*` atravessa a quebra de linha
#: que o gerador põe entre os dois atributos.
_LUGAR_VAZIO = re.compile(r'data-controle="(p\d+)"[^>]*data-conectado="nao"')

#: TODOS os lugares que a página desenha, cheios ou vazios. É diferente do de
#: cima e a diferença é o defeito: a página nasce com dois lugares CONECTADOS
#: (o P1 e o P2 do desenho) e, com um controle só na mesa, o P2 fica sem dono —
#: a coluna dele continua com os ajustes que o mockup escreveu.
_QUALQUER_LUGAR = re.compile(r'data-controle="(p\d+)"')

#: UM `<select>` DA PÁGINA, pela CLASSE. É por ele que o pacote pergunta o que a
#: página OFERECE — e nunca supõe: `escrever()` do piloto recusa pôr num
#: `<select>` um valor que ele não tem, e a recusa é calada.
_SELECT = re.compile(
    r'<select[^>]*class="(?P<classe>modo|pronto)"[^>]*>(?P<dentro>.*?)</select>', re.S)

#: O ATRIBUTO BOOLEANO NA FORMA EM QUE O NAVEGADOR O DEVOLVE. Um HTML escrito
#: `disabled` volta do `innerHTML` como `disabled=""` — medido no Chrome em
#: 02/09/2026 —, e essa diferença de um caractere é o que separa um bloco
#: trocado UMA vez de um bloco trocado a cada tique. Ver
#: `_opcoes_cravadas_do_pronto`.
_COMO_O_DOM_ESCREVE = re.compile(r"\s(disabled|hidden|readonly|required)(?=[\s>])")

#: UM COMENTÁRIO DE CSS, e ele é o que separa uma régua que MEDE de uma que
#: lê a própria prosa. O `<style>` da página carrega os comentários do gerador,
#: e neles a declaração aparece escrita por extenso, para explicar a cura —
#: procurar a declaração no documento inteiro acha o comentário e dá verde
#: sobre uma página que não a tem. Medido em 02/09/2026, ver `_a_caixa_cresce`.
_COMENTARIO_CSS = re.compile(r"/\*.*?\*/", re.S)

_LIDO: dict[str, int] | None = None
_ENDERECOS: frozenset[str] | None = None
_VAZIOS: frozenset[str] | None = None
_OFERECE: dict[str, frozenset[str]] | None = None
_OPCOES_DO_PRONTO: str | None = None
_CRESCE: dict[str, bool] | None = None


def _pagina_publicada() -> str:
    """O HTML que o produto renderiza AGORA, ou `''` se não der para ler.

    `publicado=True` É DELIBERADO, e é a exceção que o `onde.pagina` prevê: o
    padrão daquele módulo é a BANCADA, porque todo instrumento desta casa mede o
    desenho de hoje. Aqui não — quem pinta pinta no que está no `WebView`, e
    contar as casas da bancada faria o pacote endereçar barras que a página
    publicada ainda não tem.
    """
    from hefesto_dualsense4unix.interface import onde

    try:
        return onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
    except OSError:
        return ""


def _casas_cravadas() -> dict[str, int]:
    """`{"e": N, "d": M}` — quantas barras de ajuste a página publicada CRAVA.

    NÃO É MAIS UMA INSTRUÇÃO, É UM DIAGNÓSTICO. Até 02/09/2026 este número
    mandava no pacote: ele escrevia exatamente `N` casas, enchendo de vazio as
    que o modo não usava. Era a cura do D3 pelo sintoma, e ela tinha um teto —
    `Machine` pede 6 barras, `MultiPositionVibration` pede 11, e a página crava
    4 e 2. *Os sete que sobram não cabiam, e a tela calava sobre eles.*

    Com a decisão dela (a caixa acompanha o modo), quem manda é o MODO e a caixa
    inteira vem em `blocos:`. O que este número diz agora é UMA coisa: quantas
    barras o produto ainda tem de SOBRESCREVER porque a página publicada as
    trouxe do desenho velho. Ele vai a zero no dia em que ela publicar a bancada
    — e ali o bloco passa a pousar num lugar que já nasceu vazio.

    Ele continua LIDO e nunca digitado: `4` e `2` escritos aqui seriam a segunda
    cópia de um número que o gerador decide, e envelheceriam calados.
    """
    global _LIDO
    if _LIDO is None:
        casas = {"e": 0, "d": 0}
        for m in _CASA.finditer(_pagina_publicada()):
            lado, i = m.group("lado"), int(m.group("i"))
            casas[lado] = max(casas[lado], i + 1)
        _LIDO = casas
    return _LIDO


def sem_comentarios_de_css(doc: str) -> str:
    """O documento sem os `/* … */` — e sem espaço, para casar declaração.

    É PÚBLICA PORQUE TEM DOIS DONOS: este pacote pergunta à página publicada se
    a caixa já cresce, e a régua do gerador (`aba03.py`) pergunta o mesmo à
    bancada que acabou de escrever. As duas procuram a MESMA declaração, e uma
    delas escrita à mão divergiria da outra no dia em que o CSS mudasse.

    POR QUE ELA EXISTE, e é um defeito medido em 02/09/2026: a régua do gerador
    fazia `exigir("grid-template-rows:subgrid" in doc, …)` sobre o documento
    inteiro. Arrancada a declaração de `.duas-colunas > div`, o gerador
    continuou dizendo `OK` — porque o comentário que EXPLICA a cura escreve a
    declaração por extenso, e comentário de CSS é emitido para dentro do
    `<style>`. A régua lia a própria prosa. Sem os comentários ela mede a
    página.
    """
    return _COMENTARIO_CSS.sub(" ", doc).replace(" ", "").replace("\n", "")


def _a_caixa_cresce() -> dict[str, bool]:
    """`{"e": bool, "d": bool}` — a página publicada deixa a caixa crescer?

    É A PERGUNTA QUE MANTÉM A CURA VÁLIDA NOS DOIS MUNDOS, e ela nasceu de um
    estrago medido: a decisão dela (a caixa acompanha o modo) tem DUAS metades,
    e elas moram em lados diferentes da fronteira da publicação. A metade que
    ENCHE a caixa é este pacote e vale hoje — um `blocos:` pousa na página
    publicada como pousa na bancada. A metade que a faz CRESCER é o desenho, e
    desenho só entra na tela dela quando ELA publica.

    A METADE SOZINHA É PIOR QUE NENHUMA. Medido em 02/09/2026 no Chrome, sobre
    o arquivo publicado, injetando o HTML que `html_dos_ajustes` emite e
    exatamente a operação do piloto (`alvo.innerHTML = html`), com os perfis do
    disco dela::

        aventura  L2 `Curva de força`  10 barras em caixa de  92px → vaza  58px
                  R2 `Curva de força`  10 barras em caixa de  46px → vaza 104px
        corrida   R2 `Vibração por posição` 11 barras em 46px → vaza 119px

    E o que vaza cai POR CIMA do `<select>` de Modo do R2 e do "Guardar esse
    efeito" (foto: `/tmp/gat-pub-aventura.png`).

    A RESPOSTA VEM DA PÁGINA, nunca de uma data ou de um interruptor: a trilha
    de ajustes cresce quando ela é `minmax(var(--r-aj-<lado>),auto)`. Enquanto
    a publicada trouxer a trilha FIXA, o pacote se limita ao que cabe lá; no dia
    em que ela publicar, a mesma leitura devolve `True` e a caixa passa a ter o
    tamanho do modo, sem ninguém lembrar de mexer aqui.

    POR LADO, e não uma resposta só: as duas trilhas são declaradas separadas
    (`--r-aj-e` e `--r-aj-d`), e um desenho que crescesse só a de cima é uma
    página que este pacote tem de saber ler.
    """
    global _CRESCE
    if _CRESCE is None:
        css = sem_comentarios_de_css(_pagina_publicada())
        _CRESCE = {lado: f"minmax(var(--r-aj-{lado}),auto)" in css
                   for lado in ("e", "d")}
    return _CRESCE


def _cabem_no_desenho(sigla: str) -> int | None:
    """Quantas barras a página publicada comporta naquele lado — ou `None`.

    `None` quer dizer *"não há teto"*: ou a trilha já cresce (ela publicou), ou
    a página não trouxe barra nenhuma cravada e não há teto a respeitar.
    """
    if _a_caixa_cresce().get(sigla):
        return None
    cabem = _casas_cravadas().get(sigla, 0)
    return cabem or None


def _o_que_o_select_oferece() -> dict[str, frozenset[str]]:
    """Os `value` que cada campo de escolha da página publicada aceita.

    POR QUE O PACOTE PRECISA PERGUNTAR ISTO, e é o mecanismo inteiro da decisão
    13 dela: `escrever()` do piloto **recusa em silêncio** pôr num `<select>` um
    valor que ele não oferece (`hefesto_vivo.py`, o alvo `valor`) — e a recusa é
    CERTA, porque escrever qualquer outra coisa deixaria o campo em branco
    somando uma pintura por tique para sempre.

    Então o pacote emite o travessão **só quando a página já o tem**. Enquanto a
    bancada espera a palavra dela, o lugar vazio continua dizendo `Desligado` —
    que é o que o produto de hoje sabe mostrar — e passa a dizer `—` no dia da
    publicação, sem ninguém precisar lembrar de mexer aqui.
    """
    global _OFERECE
    if _OFERECE is None:
        fora: dict[str, set[str]] = {"modo": set(), "pronto": set()}
        for m in _SELECT.finditer(_pagina_publicada()):
            fora[m.group("classe")].update(
                re.findall(r'<option[^>]*value="([^"]*)"', m.group("dentro")))
        _OFERECE = {k: frozenset(v) for k, v in fora.items()}
    return _OFERECE


def _enderecos_da_pagina() -> frozenset[str]:
    """Todo `data-campo` que a página publicada tem. Vazio se ela não abrir.

    É com ele que a `cobertura` para de contar pintura no vazio. Um conjunto
    VAZIO faz a contagem cair a zero, e a régua do despachante reprova um
    pacote que pinta 0 — o que é o desfecho certo se a página sumir do wheel.
    """
    global _ENDERECOS
    if _ENDERECOS is None:
        _ENDERECOS = frozenset(re.findall(r'data-campo="([^"]+)"', _pagina_publicada()))
    return _ENDERECOS


def _lugares_que_o_desenho_da_por_vazios() -> frozenset[str]:
    """Os `pref` que a página publicada já marca `data-conectado="nao"`.

    POR QUE O PACOTE PRECISA SABER DISSO, e é o defeito D4, medido em
    02/09/2026: os quatro `<select>` das colunas P3 e P4 são **endereço morto**.
    O piloto preenche todo lugar que a mesa não tem com `dict.fromkeys(chaves,
    "—")` (`pacotes/__init__.py:323`), e `escrever()` **recusa** escrever um
    valor que o `<select>` não oferece (`hefesto_vivo.py:348-352`) — a recusa é
    CERTA, porque escrever qualquer outra coisa deixaria o campo em branco
    somando +1 por tique para sempre. O desfecho é que o travessão nunca pousa e
    a coluna vazia continua mostrando o que o gerador escreveu.

    Enquanto o valor cravado é `Off`/`custom`, isso passa por inofensivo. **Ele
    não é**: o dia em que um controle sai do P3 com `Rígido` aplicado, o
    `Rígido` FICA na tela — a coluna de um lugar sem aparelho afirmando um
    efeito. É a nona aparição do defeito que esta casa nomeia, *a tela afirmando
    o que não é*, e a única cura é o pacote escrever ali um valor que o
    `<select>` aceite.

    POR QUE SÓ OS LUGARES QUE O DESENHO JÁ DÁ POR VAZIOS, e não todo lugar
    vazio: quem emite uma coluna SAI da conta `TODOS_OS_LUGARES - vivos` do
    piloto, e com ela perde o `data-conectado="nao"` que o piloto escreveria —
    que é o que segura o `pointer-events:none` do lugar vazio. Nas colunas que a
    página já dá por vazias isso não custa nada (a marca está no arquivo); numa
    que a página dá por conectada — o P2 com um controle só na mesa — custaria a
    trava. O acoplamento é do piloto (ele deduz "vazio" de "quem não emitiu", em
    vez de perguntar à mesa) e a cura é lá; aqui fica a metade que não regride.
    """
    global _VAZIOS
    if _VAZIOS is None:
        _VAZIOS = frozenset(_LUGAR_VAZIO.findall(_pagina_publicada()))
    return _VAZIOS


def _todos_os_lugares_da_pagina() -> frozenset[str]:
    """Os `pref` de TODAS as colunas da página publicada, cheias ou vazias.

    POR QUE ELE EXISTE SEPARADO DO DE CIMA, e é um defeito que a mudança de hoje
    abriria sem ele: os `colunas` só podem ser emitidos para os lugares que a
    página já dá por vazios (ver acima), mas a caixa de ajustes é um BLOCO, e um
    bloco não passa pela conta `TODOS_OS_LUGARES - colunas` do despachante — ele
    pousa por seletor CSS. Logo ele pode alcançar o P2 sem tirar o P2 daquela
    conta, e é justamente o P2 que ficava mostrando o desenho com um controle só
    na mesa.

    Até 02/09 quem cuidava disso era o molde do despachante: ele escrevia
    travessão em `aj-nome-e-0`, `aj-val-e-0`… um por um. Com a caixa virando
    bloco, esses endereços saem do molde — e a cura tem de vir por onde a caixa
    agora vem.
    """
    return frozenset(_QUALQUER_LUGAR.findall(_pagina_publicada()))


#: O QUE O DESENHO OFERECE PARA DIZER "NÃO HÁ NADA AQUI" — decisão 13 dela,
#: 02/09/2026: *"o lugar vazio mostra travessão"*. A razão é dela e é a de
#: sempre nesta casa: `Desligado` **é uma escolha legítima de um controle
#: conectado**, e usar a mesma palavra para as duas coisas confunde as duas.
#:
#: O `value` É O TRAVESSÃO, e não `""`, e isso não é enfeite: `escrever()` do
#: piloto troca o vazio por `—` ANTES de escolher a opção, e depois faz
#: `select.value = '—'`. Uma opção com `value=""` e texto `—` não seria
#: selecionada — o campo nasceria em branco somando uma pintura por tique.
TRAVESSAO = "—"


def _sem_nada(campo: str, cravado: str) -> str:
    """O que este campo mostra num lugar SEM APARELHO, hoje.

    `campo` é `modo` ou `pronto`; `cravado` é o que o produto sabia dizer antes
    da decisão 13 (`Off` e `custom`). Devolve `""` — que o piloto pinta como
    `—` — assim que a página publicada oferecer o travessão, e o valor antigo
    enquanto ela não oferecer.

    É O PRINCÍPIO GERAL DELA, aplicado a um campo só: *"se não tá mostrando
    agora, não tem info pra mostrar no produto. Mas quando tiver, aparece a
    info correta. Isso pra todo tipo de questão similar."* O pacote não fica
    esperando alguém lembrar de trocar uma constante no dia da publicação: ele
    PERGUNTA à página, e a resposta muda sozinha.
    """
    return VAZIO if TRAVESSAO in _o_que_o_select_oferece().get(campo, ()) else cravado


def _escapar(texto: str) -> str:
    """O mínimo para um texto de dado caber num atributo e num nó de texto.

    O NOME DO EFEITO É DELA, e ela pode escrever o que quiser nele — inclusive
    `<` e `"`. Sem isto, um nome com aspas partiria o `value` da opção ao meio e
    o clique mandaria ao daemon um pedaço de nome.
    """
    return (texto.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _specs() -> Any:
    """A tabela de presets do produto, ou `None` se o `src/` não abrir.

    `None` NÃO vira travessão silencioso: sem a tabela, o pacote não sabe
    traduzir `Rigid` para `Rígido` nem nomear os ajustes, e devolver rótulos
    crus seria pior que devolver nada. Quem chama trata.
    """
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions import trigger_specs

        return trigger_specs
    except Exception:
        return None


def _prontos() -> Any:
    """As curvas prontas do produto (`profiles/trigger_presets.py`), ou `None`.

    São as MESMAS cinco que o desenho oferece em "Efeito pronto" — a tela não as
    inventou: `FEEDBACK_POSITION_LABELS` traz "Rampa crescente", "Rampa
    decrescente", "Plateau central", "Stop hard" e "Stop macio", letra por letra,
    e cada uma resolve para dez intensidades de 0 a 8.
    """
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.profiles import trigger_presets

        return trigger_presets
    except Exception:
        return None


#: O MODO QUE UMA CURVA DE FEEDBACK É. Uma curva de dez posições existe em DOIS
#: modos, e este é o de força: `pos_0..pos_9` (`app/actions/trigger_specs.py`).
#: O outro é o `MODO_DA_VIBRACAO`, logo abaixo — a GUI estável repovoa o mesmo
#: campo com uma tabela ou com a outra conforme o modo em que o gatilho está
#: (`triggers_actions._populate_preset_combo`).
MODO_DA_CURVA = "MultiPositionFeedback"

#: O SEGUNDO MODO POR POSIÇÃO, e ele estava fora do alcance desta tela até
#: 03/09/2026. `VIBRATION_POSITION_PRESETS` tem CINCO curvas — pulso crescente,
#: machine gun, galope, senoide, vibração final — que a GUI estável oferece e o
#: HTML não alcançava de jeito nenhum: o campo só carregava as de feedback e o
#: gesto mandava sempre `MultiPositionFeedback`.
MODO_DA_VIBRACAO = "MultiPositionVibration"

#: OS DOIS MODOS QUE TÊM CURVA PRONTA, na ordem em que o produto os nomeia.
#: É o `_MODES_COM_PRESET` da GUI estável, com o mesmo conteúdo e o mesmo dono
#: de tabela — quem decide qual das duas listas o campo mostra é o MODO.
MODOS_COM_CURVA = (MODO_DA_CURVA, MODO_DA_VIBRACAO)


# ---------------------------------------------------------------------------
# A DESCRIÇÃO DO MODO — decisão [01] do PO, 04/09/2026: *"Dica do campo, com o
# texto desta tela. A dica do campo deixa de ser fixa e passa a ser a explicação
# do modo ESCOLHIDO, reescrita a cada tique."*
#
# ELA MORA AQUI, E NÃO NO GERADOR, e a razão é a mesma da caixa de ajustes e do
# chip da coluna: **quem reescreve a cada tique é o produto**. Enquanto o
# dicionário vivia em `interface/aba03.py`, o texto só existia na BANCADA — o
# gerador o cravava no `title` de cada `<option>` e ninguém, do lado vivo, tinha
# como pôr a frase do modo ESCOLHIDO no campo. Agora `aba03.py` importa daqui, e
# a cena e o tique dizem a mesma frase por construção.
#
# O TEXTO É O DESTA TELA, e a escolha é do PO com a razão medida: o produto tem
# a sua própria descrição (`PRESETS[i].description`, *"Barreira rígida numa
# posição fixa."*) e esta é a concreta — fala de freio de carro e de espingarda.
# As duas continuam existindo, cada uma no seu lugar: a do produto é a da GTK, e
# a linha `Dica (tooltip) por modo` do CSV declara a divergência de propósito.
#
# A GUARDA DE CONJUNTO CONTINUA NO GERADOR (`interface/aba03.py`), e é onde ela
# morde: lá o `PRESETS` é importado no topo e um modo novo REPROVA a geração
# alto. Aqui `_specs()` é preguiçoso e devolve `None` numa árvore sem `src/` —
# uma guarda de import neste arquivo derrubaria a interface inteira por causa
# de uma frase de dica, que é trocar um buraco por um apagão.
DICA_DO_MODO = {
 "Off": "Sem resistência nenhuma — o gatilho fica solto, como num controle comum.",
 "Rigid": "Trava dura do começo ao fim do curso. Serve para freio de carro e para arma travada.",
 "SimpleRigid": "A mesma trava dura, com um só ponto de ajuste em vez de dez.",
 "Pulse": "Um solavanco num ponto do curso e depois solta — o coice de um tiro único.",
 "PulseA": "Pulso com a subida mais suave: a força cresce antes do estalo.",
 "PulseB": "Pulso com a descida mais suave: o estalo vem e a força cai devagar.",
 "Resistance": "Peso constante do começo ao fim, sem trava — remada, alavanca, arco sendo puxado.",
 "Bow": "Fica cada vez mais pesado até o fim do curso, e então solta de uma vez.",
 "Galloping": "Batidas ritmadas enquanto o gatilho está apertado — cavalo correndo, motor pegando.",
 "SemiAutoGun": "Uma trava, um estalo, e o gatilho volta. Um tiro por aperto.",
 "AutoGun": "Vibra continuamente enquanto está apertado — rajada.",
 "Machine": "Batidas rápidas e fortes enquanto apertado. É o padrão do Estilo FPS.",
 "Feedback": "Solto até certo ponto do curso, e daí em diante duro. O ponto é ajustável.",
 "Weapon": "Trava, solta no estalo e fica leve até o fim — espingarda.",
 "Vibration": "Treme o gatilho na frequência escolhida, sem opor força.",
 "SlopeFeedback": "A força sobe em linha reta do início ao fim do curso.",
 "MultiPositionFeedback": "Você desenha a força em dez posições do curso, uma por uma.",
 "MultiPositionVibration": "Treme só na faixa do curso que você marcar.",
 "Custom": "As dez posições em branco, para desenhar a curva do jeito que a sua mão pedir.",
}

#: O QUE A DICA DIZ NUM LUGAR SEM APARELHO. É a MESMA frase que o chip da coluna
#: já usa (:func:`chip_do_controle`), e ela mora numa constante por isso: duas
#: cópias divergiriam no primeiro dia em que alguém mexesse numa só, e a coluna
#: vazia passaria a dizer duas coisas diferentes sobre o mesmo nada.
SEM_APARELHO_AQUI = "Nenhum controle neste lugar."

#: OS DOIS ENDEREÇOS DA DICA, um por campo de escolha, com o lado no fim
#: (`dica-modo-e`, `dica-pronto-d`). Eles ficam no EMBRULHO do `<select>`, e não
#: no próprio: um elemento tem UM `data-hef-alvo`, e o do campo de escolha já é
#: `valor` — sem ele a primeira pintura faria `select.textContent = "Rígido"` e
#: apagaria as 19 opções. O `title` de um ancestral é o que o navegador mostra
#: quando o elemento sob o rato não tem o seu, e esta casa já depende disso na
#: `08-conexoes` (o `mic-dica` embrulha o `<b>` do estado).
PREFIXO_DA_DICA_DO_MODO = "dica-modo-"
PREFIXO_DA_DICA_DO_PRONTO = "dica-pronto-"


def descricao_do_modo(chave: str) -> str:
    """A explicação do modo, na frase desta tela — vazio nunca.

    A QUEDA É A DESCRIÇÃO DO PRODUTO, e não o silêncio: um modo que o produto
    ganhe e que esta tela ainda não tenha frase para continua tendo o
    `spec.description`, que é a frase da GTK. Entre a frase concreta, a genérica
    e nenhuma, a ordem é essa — e o gerador reprova alto no dia em que a
    primeira faltar, para que a segunda não vire o padrão calado.
    """
    daqui = DICA_DO_MODO.get(chave)
    if daqui:
        return daqui
    specs = _specs()
    spec = specs.get_spec(chave) if specs else None
    return str(getattr(spec, "description", "") or "")


def _rotulo_do_modo(chave: str) -> str:
    """O rótulo de tela de um modo (`Rigid` → `Rígido`), ou a chave crua.

    A CHAVE CRUA É O CONTRATO DE DISCO e não é texto de tela — é a separação que
    o `GATILHO-PALAVRA-01` escreveu neste projeto. Ela só sai daqui quando o
    `src/` não abre, que é o caso em que não há tradução a oferecer.
    """
    specs = _specs()
    spec = specs.get_spec(chave) if specs else None
    return str(getattr(spec, "label", "") or chave)


def destinos_do_campo_de_pronto(modo_chave: str) -> list[str]:
    """Os modos a que as curvas OFERECIDAS neste campo levam, naquele modo.

    ELE É DERIVADO, NUNCA DIGITADO — e essa é a razão de ele existir em vez de
    duas frases escritas à mão. Quem decide o que o campo oferece é
    :func:`_tabela_que_o_campo_mostra`; quem decide para que modo cada curva
    leva é :func:`_curva`, pela TABELA em que ela mora. Perguntar aos dois é o
    único jeito de a dica não prometer um caminho que a lista não abre.
    """
    presets, _ = _tabela_que_o_campo_mostra(modo_chave)
    fora: list[str] = []
    for chave in presets:
        try:
            destino = _curva(chave)[1]
        except (ValueError, RuntimeError):
            continue
        if destino not in fora:
            fora.append(destino)
    return fora


def dica_do_pronto(modo_chave: str) -> str:
    """O aviso do campo "Efeito pronto" — ANTES do clique, com o modo de AGORA.

    DECISÃO [02] do PO, 04/09/2026: *"Fica como está, e a dica avisa ANTES do
    clique. O desenho é dela, o atalho de um clique é real, e a única dívida
    medida é a tela não avisar que o modo vai mudar."*

    A DIVERGÊNCIA COM A GTK É REAL E CONHECIDA (linha `Quando o campo "Efeito
    pronto" aparece, e o que escolhê-lo faz`): lá a linha só existe nos DOIS
    modos por posição e escolher um preset preenche os sliders **sem mexer no
    modo**; aqui o campo aparece nos 19 e o clique já aplica — logo, fora dos
    dois modos por posição, escolher uma curva TROCA o modo. Quem decidiu manter
    foi o PO; o que faltava era a tela dizer isso antes.

    **A PRIMEIRA VERSÃO DESTA FRASE PROMETIA DEMAIS, e quem a derrubou foi a
    mordida.** Ela dizia *"as curvas de força vão para «Curva de força» e as de
    vibração para «Vibração por posição»"* nos dezessete modos comuns — e é
    FALSO: com o gatilho em `Rigid`, o campo oferece SÓ as seis curvas de
    feedback (`_tabela_que_o_campo_mostra`, medido no DOM em 03/09), então
    `Vibração por posição` não é alcançável dali. A tela estaria descrevendo um
    caminho que a lista não abre — que é o alarme sem medição que esta casa bane.

    **A CURA É PERGUNTAR À LISTA**, e não escolher melhor as palavras: o destino
    sai de :func:`destinos_do_campo_de_pronto`, que lê o que o campo oferece
    naquele modo e resolve cada curva pela tabela em que ela mora. Se um dia o
    campo passar a oferecer as onze, a dica nomeia as duas sozinha.
    """
    agora = _rotulo_do_modo(modo_chave)
    fim = "Um efeito seu põe o modo com que ele foi guardado."
    destinos = destinos_do_campo_de_pronto(modo_chave)
    if not destinos:
        # SEM CURVA A OFERECER NÃO HÁ TROCA A ANUNCIAR. É o caminho que só se
        # alcança sem o `src/` (as tabelas do produto não abriram), e ali a
        # honestidade é dizer o que se sabe: o modo de agora, e mais nada.
        return f"Este gatilho está em «{agora}». {fim}"
    para = " ou ".join(f"«{_rotulo_do_modo(d)}»" for d in destinos)
    if destinos == [modo_chave]:
        return (f"Este gatilho está em «{agora}», e o campo mostra as curvas "
                f"deste modo: escolher uma aplica as dez posições dela na hora, "
                f"sem trocar o modo. {fim}")
    return (f"Este gatilho está em «{agora}». Escolher uma curva pronta TROCA o "
            f"modo dele para {para} na hora — é um clique, e já vai ao "
            f"controle. {fim}")


def _tabela_da_curva(modo: str) -> tuple[dict[str, list[int]], dict[str, str]]:
    """`(presets, rótulos)` do modo por posição, ou dois vazios nos outros 17.

    ESTA É A REGRA DA GUI ESTÁVEL, palavra por palavra
    (`triggers_actions._populate_preset_combo`): `MultiPositionFeedback` lê
    `FEEDBACK_POSITION_*`, `MultiPositionVibration` lê `VIBRATION_POSITION_*`,
    e nenhum outro modo tem curva. Escrever a escolha em dois lugares — na
    lista que a tela mostra e no gesto que aplica — era como a tela passaria a
    oferecer uma curva que o gesto não sabe resolver.
    """
    tp = _prontos()
    if tp is None:
        return {}, {}
    if modo == MODO_DA_VIBRACAO:
        return dict(tp.VIBRATION_POSITION_PRESETS), dict(tp.VIBRATION_POSITION_LABELS)
    if modo == MODO_DA_CURVA:
        return dict(tp.FEEDBACK_POSITION_PRESETS), dict(tp.FEEDBACK_POSITION_LABELS)
    return {}, {}


def _pronto_da_curva(nome: str, curva: list[int]) -> str:
    """Qual efeito pronto é aquela curva salva, ou `custom` se não for nenhum.

    O DISCO NÃO GUARDA QUAL PRESET FOI ESCOLHIDO — guarda as dez intensidades.
    Então a chave se RECONHECE, comparando com a tabela do produto; ela não se
    adivinha e não se digita. Sem isto a tela mostraria "— Nenhum —" para uma
    curva que é exatamente a "Stop hard" que ela escolheu.

    A TABELA É A DO MODO — 03/09/2026. Esta função só olhava a de feedback, e
    por isso um `MultiPositionVibration` gravado com a `galope` do produto
    aparecia como "— Nenhum —": a tela desistia de nomear uma curva que ela
    mesma tem. As duas tabelas não compartilham chave nenhuma, mas quem escolhe
    é o modo, e não a coincidência.

    `custom` é o token do próprio produto para "nenhuma pronta"
    (`FEEDBACK_POSITION_LABELS["custom"]`), e é o `value` que a opção
    "— Nenhum —" carrega no desenho — a tela e o disco falam a mesma palavra.
    """
    presets, _ = _tabela_da_curva(nome)
    if not presets or len(curva) != 10:
        return "custom"
    for chave, valores in presets.items():
        if list(valores) == list(curva):
            return str(chave)
    return "custom"


# ---------------------------------------------------------------------------
# O RASCUNHO DESTA ABA — a escolha dela FICA na tela até o disco alcançá-la.
#
# O DEFEITO, e ele é o que mais se parece com a frase dela (*"o produto via html
# não funcionou igual o gtk"*): clicar `Rígido` aplicava no aparelho — ela sente
# na mão — e, em no máximo meio segundo, o campo voltava para o modo SALVO. O
# tique repinta `modo-chave-<lado>` com o perfil DO DISCO, e aplicar não grava
# (a docstring do `guardar` já dizia: *"o efeito vale até a próxima troca de
# perfil, e o disco continua com o que estava lá"*).
#
# ISSO NÃO É TELA VAZIA — É TELA QUE MENTE, e ela contaminava o botão: o
# "Guardar esse efeito" lê a COLUNA, e passado meio segundo a coluna já não
# tinha a escolha dela. Um clique em `Rígido` seguido de `Guardar` gravava o que
# já estava no disco.
#
# A CURA É A DA GTK, e ela tem nome lá: `_persist_params_to_draft`
# (`app/actions/triggers_actions.py:342-391`), chamado antes de todo envio, e
# `_refresh_triggers_from_draft` (:168-203), que repinta do RASCUNHO e não do
# perfil. Aqui o rascunho é este dicionário, com a MESMA forma que o disco usa
# (`{"mode": ..., "params": [...]}`) — logo `_do_lado` o traduz para a tela sem
# uma linha nova, e o `guardar` continua lendo a tela.
#
# ELE VIVE SÓ ENQUANTO O PERFIL VIVE, e as duas podas são medidas, não zelo:
#
# * TROCA DE PERFIL — o daemon REAPLICA o perfil no `profile.switch`, então o
#   que estava aplicado deixou de estar. Guardar o rascunho por perfil e
#   ressuscitá-lo na volta faria a tela afirmar um efeito que o daemon já
#   desfez. A GTK paga o mesmo preço: o draft é remontado do perfil.
# * O CONTROLE SAI DA MESA — no replug o daemon aplica o perfil de novo. Um
#   rascunho sobrevivente diria, sobre um aparelho que acabou de chegar, o
#   efeito de antes de ele sair.
#
# QUEM ESCREVE É A THREAD DO GESTO e quem lê é o laço do GTK. Não há trava:
# cada entrada é SUBSTITUÍDA inteira (nunca mutada por dentro), e uma leitura
# concorrente devolve a de antes ou a de depois — nunca meia. O tique seguinte
# corrige em 500 ms.
# ---------------------------------------------------------------------------
_PERFIL_DO_RASCUNHO: str = ""
_RASCUNHO: dict[tuple[str, str], dict[str, Any]] = {}


def _chave_do_rascunho(uniq: str, disco: str) -> tuple[str, str]:
    """O endereço de uma metade do rascunho: `uniq` NORMALIZADO e o lado.

    O `uniq` do clique vem da mesa (`d4:2f:…`) e o do perfil vem do disco
    (`d42f…`). Normalizar aqui é o que impede o mesmo controle de ter duas
    entradas — a mesma razão que `_com_os_gatilhos` já escreve.
    """
    return (uniq.replace(":", "").lower(), disco)


def esquecer_o_rascunho() -> None:
    """Joga fora o que esta sessão lembrava de ter aplicado.

    PÚBLICA de propósito: é por ela que a régua arranca a cura e vê a tela
    voltar a mentir, e é ela que a troca de perfil chama.
    """
    _RASCUNHO.clear()


def _o_rascunho_e_deste_perfil(perfil: str) -> None:
    """Poda o rascunho quando o perfil ativo mudou. Ver a nota da seção."""
    global _PERFIL_DO_RASCUNHO
    if perfil != _PERFIL_DO_RASCUNHO:
        _PERFIL_DO_RASCUNHO = perfil
        esquecer_o_rascunho()


def _o_rascunho_e_de_quem_esta_na_mesa(uniqs: set[str]) -> None:
    """Poda o rascunho dos controles que saíram. Ver a nota da seção."""
    for chave in [k for k in _RASCUNHO if k[0] not in uniqs]:
        _RASCUNHO.pop(chave, None)


def _lembrar_o_aplicado(perfil: str, uniq: str, disco: str,
                        cfg: dict[str, Any]) -> None:
    """Grava no rascunho o que acabou de ir para o aparelho."""
    _o_rascunho_e_deste_perfil(perfil)
    _RASCUNHO[_chave_do_rascunho(uniq, disco)] = {
        "mode": str(cfg.get("mode") or "Off"),
        "params": [int(v) for v in (cfg.get("params") or [])],
    }


def _do_rascunho(uniq: str, disco: str) -> dict[str, Any] | None:
    """O que esta sessão aplicou naquele gatilho, ou `None` se não aplicou nada."""
    return _RASCUNHO.get(_chave_do_rascunho(uniq, disco))


# ---------------------------------------------------------------------------
# "MEUS EFEITOS" — a decisão 17 dela, 02/09/2026, com as palavras dela:
#
#     "Isso é pra quando o user salva algum efeito. É assim que tem que
#      aparecer. O nome que o user deixar lá. Ali é só exemplo."
#
# `Recuo do MK` e `Freio do carro` são EXEMPLOS do desenho — não features
# falsas. O que faltava era o DONO, e é o que nasce aqui.
#
# ONDE ELES MORAM, e a escolha é minha com a razão escrita: em
# `app/gui_prefs.py`, a mesma caixa de preferências da interface que já existe,
# é XDG-correta (`~/.config/hefesto-dualsense4unix/gui_preferences.json`),
# resolve o caminho NA CHAMADA (a cura do CANARIO-FS-01, para a suíte não
# vazar no `$HOME` de quem roda) e tem três funções públicas de módulo —
# `load_gui_prefs`, `save_gui_prefs`, `set_pref`. **É reuso, e a LEI 0 desta
# leva manda procurar antes de escrever.**
#
# POR QUE NÃO NO PERFIL, que era o lugar "óbvio": um efeito salvo é uma peça da
# BIBLIOTECA dela, não uma propriedade daquele jogo. Guardado no perfil, o
# "Recuo do MK" existiria no perfil em que foi salvo e sumiria em todos os
# outros 32 — que é o oposto de "Meus efeitos". E há o preço estrutural: seção
# nova no `Profile` obriga classificação em três portões de perfil e reescreve
# `schema.py` + `loader.py`, dois arquivos que outras frentes desta leva também
# tocam. A biblioteca não paga nada disso.
#
# O QUE UM EFEITO É: o PAR L2+R2. A legenda do próprio desenho dizia
# *"Guarda o par L2+R2 em Meus efeitos"* (a frase morreu num redesenho; o
# comentário do CSS que a explica sobreviveu, em `aba03.py`). Escolhê-lo no
# campo do L2 aplica a metade esquerda; no do R2, a direita — o campo é de um
# gatilho, e aplicar os dois de um clique num campo de um seria surpresa.
# ---------------------------------------------------------------------------

#: A CHAVE NA CAIXA DE PREFERÊNCIAS. Ela não está nos `_DEFAULTS` do
#: `gui_prefs` de propósito: ausente quer dizer "ela ainda não salvou nenhum",
#: que é diferente de "salvou e apagou todos" — e `load_gui_prefs` devolve o
#: dicionário sem a chave, que é o `{}` honesto.
CHAVE_DOS_MEUS = "gatilhos_meus_efeitos"

#: O PREFIXO QUE SEPARA UM EFEITO DELA DE UMA CURVA DO PRODUTO no `value` da
#: opção. Sem ele, um efeito chamado `stop_hard` sequestraria a curva do
#: produto — e o clique aplicaria outra coisa sem nada na tela dizendo.
PREFIXO_DO_MEU = "meu:"


def meus_efeitos() -> dict[str, Any]:
    """Os efeitos que ELA salvou, do disco. `{}` quando não há nenhum.

    NUNCA LEVANTA: `load_gui_prefs` já engole `JSONDecodeError` e `OSError` com
    aviso no log e devolve os padrões. Um arquivo corrompido não pode derrubar a
    pintura da aba inteira — a tela ficaria congelada sem dizer por quê.
    """
    try:
        from hefesto_dualsense4unix.app.gui_prefs import load_gui_prefs

        guardado = load_gui_prefs().get(CHAVE_DOS_MEUS)
    except Exception:
        return {}
    if not isinstance(guardado, dict):
        return {}
    return {str(nome): valor for nome, valor in guardado.items()
            if isinstance(valor, dict) and nome.strip()}


def _guardar_meus_efeitos(todos: dict[str, Any]) -> None:
    """Escreve a biblioteca de volta, PRESERVANDO o resto das preferências.

    O `load` antes do `save` não é cerimônia: `save_gui_prefs` grava o
    dicionário INTEIRO, e escrever só a nossa chave apagaria o
    `advanced_editor` e o `ambiente_corrigido` dela.
    """
    from hefesto_dualsense4unix.app.gui_prefs import load_gui_prefs, save_gui_prefs

    prefs = load_gui_prefs()
    prefs[CHAVE_DOS_MEUS] = todos
    save_gui_prefs(prefs)


def _meia_do_efeito(efeito: Any, disco: str) -> dict[str, Any] | None:
    """A metade `left`/`right` de um efeito salvo, ou `None` se ele não a tem.

    `None` é uma resposta legítima: quem salvou um par em que só o L2 tinha modo
    guardou só o L2, e escolher esse efeito no R2 não tem o que aplicar.
    """
    if not isinstance(efeito, dict):
        return None
    meia = efeito.get(disco)
    if not isinstance(meia, dict) or not meia.get("mode"):
        return None
    return meia


def _meu_efeito_que_casa(disco: str, cfg: dict[str, Any]) -> str:
    """O nome do efeito salvo que É esta configuração, ou `""`.

    MESMA IDEIA DO `_pronto_da_curva`, e pela mesma razão: o disco não guarda
    QUAL efeito foi escolhido — guarda o modo e os ajustes. O nome se
    RECONHECE. Sem isto, ela salvaria "Recuo do MK", o campo continuaria em
    "— Nenhum —" e ela não teria como saber que o que está no gatilho é
    exatamente o que ela guardou.
    """
    modo_agora = str((cfg or {}).get("mode") or "Off")
    params_agora = list((cfg or {}).get("params") or [])
    for nome, efeito in meus_efeitos().items():
        meia = _meia_do_efeito(efeito, disco)
        if meia is None:
            continue
        if str(meia.get("mode")) == modo_agora and list(meia.get("params") or []) == params_agora:
            return nome
    return ""


def _do_lado(cfg: dict[str, Any], specs: Any) -> dict[str, Any]:
    """Um lado do gatilho, do perfil para a tela.

    `cfg` é o `{"mode": "Rigid", "params": [0, 180]}` do disco. Sai o rótulo em
    português, o nome de cada ajuste e o valor que ela salvou — que é o que as
    três linhas da aba mostram: Modo, Efeito pronto e Ajustes.

    OS AJUSTES SÃO OS DO MODO, E SÓ ELES — decisão dela, 02/09/2026. Este
    parâmetro tinha um terceiro argumento, `casas`, com o número que a PÁGINA
    reservava, e o laço enchia de vazio o que sobrava. Aquilo curava o D3 pelo
    sintoma e tinha teto: `Machine` pede seis barras e a página crava quatro —
    duas ficavam **escondidas**, e a tela calava sobre elas. Agora a caixa é um
    bloco que o produto troca inteiro, e o tamanho dela é o do modo.
    """
    nome = str((cfg or {}).get("mode") or "Off")
    valores = list((cfg or {}).get("params") or [])
    spec = specs.get_spec(nome) if specs else None

    fora: dict[str, object] = {
        "modo": spec.label if spec else nome,
        # O `name` cru viaja junto: é o contrato de disco, e é por ele que a
        # tela sabe qual botão acender sem depender do texto traduzido.
        "modo-chave": nome,
        # O `pronto` É A CHAVE, e não o rótulo — 01/09/2026. Ele é pintado no
        # `<select class="pronto">` por `data-hef-alvo="valor"`, e `select.value`
        # casa com o `value` da opção, que carrega a chave do produto
        # (`rampa_crescente`, `stop_hard`…). Um rótulo aqui não casaria com opção
        # nenhuma e o campo nasceria em branco.
        "pronto": "custom",
        "ajustes": [],
    }
    # O NOME PRÓPRIO PELA MESMA RAZÃO DA CURVA ABAIXO: reler `fora["ajustes"]`
    # devolve `object`, que não tem `.append`. A lista tem um nome e um tipo, e
    # o dicionário guarda ELA — as duas apontam para o mesmo objeto, então o
    # que se acrescenta aqui sai lá.
    ajustes: list[dict[str, Any]] = []
    fora["ajustes"] = ajustes

    if spec is None:
        return fora

    #: A CURVA, e ela é a segunda forma que o disco guarda. Medido nos 33
    #: perfis dela em 01/09/2026: `Rigid` grava `[0, 180]` — um escalar por
    #: ajuste — mas `MultiPositionFeedback` e `MultiPositionVibration` gravam
    #: `[[1], [2], ..., [8]]`, dez posições do curso, cada uma numa lista de um.
    #:
    #: São DOIS controles de tela diferentes: o primeiro é um punhado de
    #: sliders com nome, o segundo é o desenho de dez barrinhas que a aba chama
    #: de "Curva de força" e "Vibração por posição". Tratar os dois pela mesma
    #: conta foi o que quebrou este pacote na primeira execução — `[1] - 0`
    #: não é uma subtração que exista.
    por_indice: dict[int, int] = {}
    if any(isinstance(v, list) for v in valores):
        # O NOME PRÓPRIO, e não `fora["curva"]` relido três vezes: o `fora` é
        # um `dict[str, Any]`, e cada releitura devolvia `object` — o que o
        # `mypy` recusava iterar, indexar e passar adiante. A lista tem um
        # nome e um tipo, e as três linhas seguintes falam com ela.
        curva_da_tela: list[int] = [
            int(v[0]) if isinstance(v, list) and v else int(v or 0)
            for v in valores]
        fora["curva"] = curva_da_tela
        # A escala da curva é 0..8, a mesma dos `_RAMPA_PADRAO` do produto.
        fora["curva-pct"] = [round(max(0, min(100, x / 8 * 100)))
                             for x in curva_da_tela]
        fora["pronto"] = _pronto_da_curva(nome, curva_da_tela)
        # A CURVA É UMA LISTA DE POSIÇÕES, E ELAS SÃO AJUSTES — 02/09/2026, e é
        # a decisão dela: *"a tela nunca esconde o que está gravado no disco"*.
        # Até hoje este ramo devolvia a caixa VAZIA, com a razão de que a curva
        # teria desenho próprio (`curva-<lado>`) — que nunca existiu.
        #
        # O DESFECHO, MEDIDO — e a primeira versão desta nota errava nas duas
        # metades. Ela dizia *"os TRÊS perfis mostravam 'Este modo não tem o
        # que ajustar'"*. São DOIS perfis (a conta antiga somava LADOS: o
        # `aventura` tem `MultiPositionFeedback` nos dois gatilhos e o `corrida`
        # tem `MultiPositionVibration` no R2), e a frase NÃO aparecia: com
        # `casas_cravadas = {'e': 4, 'd': 2}` o `encher()` sempre devolvia
        # barras, e o que a tela mostrava eram QUATRO BARRAS MUDAS — travessão
        # no nome e no valor, largura zero — sobre dez intensidades gravadas.
        # Grave do mesmo jeito, e por um motivo pior: uma caixa vazia se lê como
        # "não há o que ajustar"; quatro barras em branco se leem como "os
        # ajustes estão em zero".
        #
        # O ALINHAMENTO NÃO É POR ÍNDICE, e a medição é de hoje, nos 33 perfis
        # dela: `MultiPositionVibration` guarda **10** valores e o spec tem
        # **11** parâmetros (`frequency` + `pos_0..pos_9`). Alinhar pelo índice
        # poria a posição 0 debaixo do rótulo "Frequência" — a tela nomeando
        # errado um número certo. As posições vão para os parâmetros `pos_*`,
        # que é o que elas SÃO, e a frequência fica no padrão do modo.
        posicoes = [i for i, q in enumerate(spec.params) if q.name.startswith("pos_")]
        alvos = posicoes if len(posicoes) == len(curva_da_tela) else list(
            range(len(curva_da_tela)))
        por_indice = dict(zip(alvos, curva_da_tela, strict=False))
    elif nome in MODOS_COM_CURVA:
        # A CURVA TAMBÉM CHEGA DEITADA, e é assim que ela chega do RASCUNHO —
        # 03/09/2026, medido CLICANDO no controle vivo.
        #
        # O DISCO guarda dez listas de um (`[[0], [1], …]`); o RASCUNHO guarda o
        # que foi ao daemon, que é a lista POSICIONAL do modo, plana
        # (`preset_to_positional_params`). O ramo de cima só reconhecia a
        # primeira forma — então, no instante seguinte a ela escolher uma curva,
        # o campo "Efeito pronto" voltava a `— Nenhum —` sobre um gatilho que
        # ESTAVA com a curva aplicada.
        #
        # MEDIDO, e vale para as ONZE: apliquei `linear_medio` no L2 do
        # controle na mesa e li o DOM — modo `MultiPositionFeedback`, dez barras
        # em 4 (a curva certa, no aparelho), e o campo de baixo dizendo
        # "— Nenhum —". Fora da tela, `_do_lado` devolvia `custom` para
        # `rampa_crescente`, `stop_hard`, `linear_medio`, `galope` e
        # `machine_gun` — as cinco que provei, das onze do produto.
        #
        # É A MESMA FAMÍLIA DA TELA QUE MENTE que o rascunho veio curar: ali era
        # o MODO que voltava para o disco, aqui é o NOME DA CURVA que some. E
        # tem o mesmo efeito colateral, porque o "Guardar esse efeito" lê a
        # coluna: guardar logo depois de escolher uma curva gravava um efeito
        # que a tela dizia não ter curva nenhuma.
        #
        # A LEITURA É PELO NOME DO PARÂMETRO (`pos_*`), nunca pelo índice — a
        # mesma regra de `_params_da_curva`: em `MultiPositionVibration` o spec
        # tem ONZE parâmetros e a curva tem DEZ, e alinhar por índice leria a
        # frequência como a posição 0.
        posicoes = [i for i, q in enumerate(spec.params) if q.name.startswith("pos_")]
        deitada = [int(valores[i] or 0) for i in posicoes if i < len(valores)]
        if posicoes and len(deitada) == len(posicoes):
            fora["curva"] = deitada
            fora["curva-pct"] = [round(max(0, min(100, x / 8 * 100)))
                                 for x in deitada]
            fora["pronto"] = _pronto_da_curva(nome, deitada)

    #: O EFEITO PRONTO NÃO É O MODO — corrigido em 01/09/2026. Estava escrito
    #: aqui que *"até existir um segundo eixo, o pronto É o modo"*, e o campo
    #: recebia `spec.label`. O segundo eixo EXISTE, e existia antes desta aba:
    #: `profiles/trigger_presets.py` guarda as cinco curvas que o desenho
    #: oferece, com os mesmos cinco nomes. O que elas preenchem são as dez
    #: posições do `MultiPositionFeedback` — logo, nos outros 18 modos não há
    #: pronto nenhum, e o honesto é `custom` ("— Nenhum —"), que já é o padrão
    #: lá em cima. Repetir o nome do modo aqui era dizer duas vezes a mesma
    #: escolha em duas linhas que a tela apresenta como diferentes.

    for i, p in enumerate(spec.params):
        if por_indice:
            valor = por_indice.get(i, p.default)
        else:
            valor = valores[i] if i < len(valores) else p.default
        largura = max(1, p.max_value - p.min_value)
        ajustes.append({
            "nome": p.label,
            "valor": valor,
            # A PORCENTAGEM É DA FAIXA DAQUELE AJUSTE, não de 0..255. Um
            # `force` vai de 0 a 255 e uma `position` de 0 a 9; dividir os dois
            # pela mesma escala pintaria a barra da posição sempre no chão.
            "pct": round(max(0, min(100, (valor - p.min_value) / largura * 100))),
            "min": p.min_value, "max": p.max_value,
        })
    return fora


# ---------------------------------------------------------------------------
# A CAIXA DE AJUSTES, EM HTML — e este módulo é o DONO da marcação dela.
#
# DECISÃO DELA, 02/09/2026: *"os ajustes viram lista e a caixa acompanha o
# modo. A aba passa a rolar nos modos grandes, e isso é aceito. A tela nunca
# esconde o que está gravado no disco."*
#
# POR QUE UM BLOCO, E NÃO CAMPO A CAMPO: o próprio piloto escreve a razão —
# *"um bloco cujo NÚMERO DE FILHOS muda com o dado não tem como ser pintado
# campo a campo: não há endereço para um filho que ainda não existe"*. Aqui o
# número vai de ZERO (`Off`) a ONZE (`MultiPositionVibration`), e a página
# reservava quatro e duas.
#
# NADA PINTA DENTRO DESTE BLOCO, e isso é deliberado: o `escrever()` do piloto
# carimba `data-hef-visto="1"` em todo elemento que visita, e um carimbo dentro
# do bloco faria o `innerHTML` divergir do HTML emitido a cada tique — o bloco
# seria trocado quatro vezes por segundo para sempre. Um contador que sobe sem
# nada mudar é o instrumento com que esta casa prova que um endereço existe;
# gastá-lo aqui custaria caro. O precedente é `a08_conexoes._html_do_mapa`.
# ---------------------------------------------------------------------------

#: A FRASE DO MODO QUE NÃO TEM O QUE AJUSTAR, e ela já era do desenho que ela
#: aprovou — está no HTML publicado desde 26/08. O dono passa a ser este
#: módulo, e o gerador a lê daqui: escrita nos dois, ela divergiria no dia em
#: que alguém mexesse num só.
SEM_AJUSTE = "Este modo não tem o que ajustar."


#: O AVISO DO QUE NÃO COUBE SAIU — decisão dela, 02/09/2026, e ela publicou a
#: 03 no mesmo minuto.
#:
#: Ele dizia `+N não cabem nesta caixa ainda` na última casa reservada. Era
#: texto de tela que ela não tinha visto, e texto de tela é dela: perguntei, e a
#: resposta foi tirar.
#:
#: TIRAR CUSTOU ZERO E RENDEU UMA BARRA: o aviso ocupava uma casa, então o teto
#: mostrava `cabem - 1` ajustes para caber a frase. Sem ele, cabem `cabem`.
#:
#: E COM A 03 PUBLICADA O TETO NEM AGE: `_a_caixa_cresce` acha a trilha
#: `minmax(var(--r-aj-<lado>),auto)` na página e devolve `None`, então nada é
#: cortado. O teto fica de pé para o caso de uma página futura voltar a ter
#: trilha fixa — e nesse dia o corte é CALADO. Quem reintroduzir trilha fixa
#: tem de dizer o custo na seção da aba em `mockup/DIVERGENCIAS.md`, que é o
#: que o portão do desenho passou a cobrar em 02/09.


def html_dos_ajustes(sigla: str, ajustes: list[dict[str, Any]],
                     cabem: int | None = None, editavel: bool = False) -> str:
    """A caixa de ajustes daquele lado, em HTML — a lista do MODO.

    Uma linha por parâmetro do modo, com o rótulo, a barra na porcentagem da
    FAIXA daquele parâmetro e o número. Zero parâmetros devolvem a frase, que é
    o que as colunas vazias do desenho já diziam.

    `editavel` É QUEM PODE ARRASTAR — 03/09/2026, e ele tem DOIS donos de razão,
    não um:

    * o PRODUTO passa `True` só nas colunas que têm aparelho. Um ajuste é de um
      gatilho; arrastar num lugar vazio só pode terminar em recusa, e o botão
      que convida para uma recusa é pior que o botão que não existe — é a mesma
      regra que o `pointer-events:none` do CSS já aplica aos `<select>`;
    * o DESENHO fica no padrão `False`, e isto está esperando a palavra dela.
      A alavanca é invisível — o desenho não muda um pixel —, mas o que ela
      aprovou em 27/08 foi uma barra de LEITURA, e transformar leitura em
      controle é decisão de produto. O gerador escreve a bancada e a bancada é
      o que ela olha; enquanto ela não disser, o desenho segue mostrando o que
      ela aprovou e o produto segue tendo a paridade com a GTK que a Lei 0
      manda ter.

    `cabem` É O TETO DA PÁGINA QUE O PRODUTO RENDERIZA HOJE, e `None` quer dizer
    "não há teto". Ele é a metade que faltava da decisão dela: a caixa acompanha
    o modo, mas a trilha que a deixa CRESCER está na bancada e a bancada só
    chega à tela quando ela publica. Sem o teto, uma caixa de 92px recebe onze
    barras e as sete que sobram caem por cima do `<select>` de Modo do R2 e do
    "Guardar esse efeito" — medido no Chrome sobre o arquivo PUBLICADO, com dois
    perfis do disco dela (`aventura` vaza 58px à esquerda e 104 à direita;
    `corrida` vaza 119). Ver `_a_caixa_cresce`.

    COM TETO, A ÚLTIMA CASA VIRA O AVISO. Ela perde uma barra e ganha o número
    do que não está vendo — que é a única coisa que a caixa cheia não lhe diz.
    Calar seria repetir o defeito que esta aba existe para matar: hoje, na
    página publicada, um `Curva de força` mostra QUATRO barras em branco sobre
    dez intensidades gravadas, e nada na tela conta que há dez.

    E O QUE NÃO COUBE CONTINUA NO DOM, invisível — `style="display:none"`, que
    ganha da classe `.barra` por ser inline. Não é enfeite: o "Guardar esse
    efeito" lê os `aj-val-*` DA TELA (o daemon não devolve o modo do gatilho), e
    `_ajustes_da_coluna` cai no PADRÃO do modo para o índice que não achar.
    Emitir só as barras visíveis faria o botão gravar os padrões por cima das
    sete posições que ela salvou — destruir dado dela em silêncio, no clique de
    um botão que diz "guardar".

    A MARCAÇÃO É A MESMA QUE O GERADOR ESCREVIA — `data-campo` inclusive, e o
    `data-hef-alvo="largura"` da barra. Ela não é enfeite:

    * o `data-campo` é o que o "Guardar esse efeito" lê. O piloto recolhe a
      coluna por `[data-linha],[data-campo]`, e sem endereço nenhum ali o
      Guardar leria zero ajustes e gravaria os PADRÕES do modo por cima do que
      ela salvou;
    * o `data-hef-alvo="largura"` é como a régua do mockup sabe LER a barra: sem
      ele, o valor cravado de `aj-pct-*` passa a ser o texto (vazio) em vez da
      largura, e a régua deixa de enxergar a barra.

    E NADA PINTA AQUI DENTRO: o pacote não emite `aj-*` em `colunas`, então o
    `escrever()` do piloto nunca visita estes elementos — logo nenhum
    `data-hef-visto` é carimbado, o `innerHTML` não diverge do emitido, e o
    bloco é trocado UMA vez em vez de quatro por segundo. Medido: 17 tiques,
    1 pintura.
    """
    if not ajustes:
        return f'            <div class="ajustes-vazio">{SEM_AJUSTE}</div>'

    #: QUANTAS APARECEM. Sem teto, todas — e é o caso de hoje, com a 03
    #: publicada. Com teto, exatamente as que cabem: o aviso saiu por decisão
    #: dela e a casa que ele ocupava voltou a ser uma barra.
    a_vista = len(ajustes) if cabem is None else min(len(ajustes), cabem)
    linhas = [_html_de_uma_barra(sigla, i, a, escondida=i >= a_vista,
                                 editavel=editavel)
              for i, a in enumerate(ajustes)]
    return "\n".join(linhas)


#: O ESTILO DA ALAVANCA INVISÍVEL, e ele é INLINE porque tem de valer na página
#: que o produto renderiza HOJE. A folha de estilo mora no cabeçalho do arquivo
#: publicado, e publicar é ato dela (`--publicar 03`); uma classe nova ficaria
#: sem regra até lá, e a alavanca nasceria do tamanho do texto, por cima da
#: barra vizinha.
#:
#: A CONTA DA CAIXA DE TOQUE: a linha da barra mede `--h-barra` = 23px e o
#: trilho tem 5px, centrado — sobram 9px acima. `top:-9px;height:23px` devolve à
#: alavanca a linha INTEIRA, que é a área que o `Gtk.Scale` da GTK também tem.
#: Menos que isso e ela pega só o fio de 5px, que ninguém acerta arrastando.
_ALAVANCA = ("position:absolute;left:0;top:-9px;width:100%;height:23px;"
             "margin:0;padding:0;opacity:0;cursor:ew-resize;"
             "-webkit-appearance:none;background:transparent")


def _html_de_uma_barra(sigla: str, i: int, a: dict[str, Any],
                       escondida: bool = False, editavel: bool = False) -> str:
    """Uma linha da caixa de ajustes. `escondida` guarda o valor sem mostrá-lo.

    `editavel` PÕE A ALAVANCA — 03/09/2026, e é a maior dívida desta aba.
    Medido: 17 dos 19 modos têm ajuste, somando 73 parâmetros (Rigid 2,
    Machine 6, MultiPositionFeedback 10, MultiPositionVibration 11). Na GTK
    cada um é um `Gtk.Scale` que ela arrasta, com faixa e padrão vindos do
    `trigger_specs`; no HTML **nenhum** era tocável, e escolher um modo
    aplicava os PADRÕES dele e acabava.

    O DESENHO NÃO MUDA UM PIXEL: a alavanca é um `<input type="range">`
    transparente POR CIMA do trilho que ela aprovou. Quem desenha continua
    sendo o `.cheio` que o pacote pinta; o `<input>` só recebe o arrasto. Uma
    barra visível nova seria desenho, e desenho é dela.

    A FAIXA É A DO PARÂMETRO, e sai do produto: `spec.params[i].min_value` e
    `.max_value`, os mesmos números que o `Gtk.Scale` usa. Digitar `0..255`
    aqui poria a posição do curso (0..9) numa régua trinta vezes maior.

    ELE PEDE A FORMA E NÃO ENTRA NELA. `data-hef-forma="@controle"` é o que faz
    o arrasto chegar ao Python com a coluna inteira — o modo e os outros
    ajustes —, porque o daemon lê a lista posicional INTEIRA e um número solto
    trocaria os vizinhos pelos padrões. Mas a alavanca não tem `data-linha` nem
    `data-campo`, e a varredura do piloto recolhe só esses dois: quem carrega o
    valor daquela casa continua sendo o `.num`. Dois endereços para o mesmo
    número seriam duas verdades no mesmo clique.

    E ELE NÃO FAZ O BLOCO PISCAR: o `value` viaja no ATRIBUTO, e arrastar muda
    a *propriedade*. O `innerHTML` continua igual ao emitido enquanto ela
    arrasta, então o piloto não troca a caixa debaixo da mão dela.
    """
    #: INLINE, e não a classe: `.barra{display:flex}` é regra de autor e ganha do
    #: `[hidden]{display:none}` da folha do navegador. O atributo sozinho não
    #: esconderia nada.
    oculta = ' style="display:none"' if escondida else ""
    alavanca = ""
    if editavel and not escondida:
        alavanca = (
            f'<input type="range" min="{int(a.get("min", 0))}" '
            f'max="{int(a.get("max", 255))}" step="1" '
            f'value="{int(a["valor"])}" data-gesto="ajuste" '
            f'data-lado="{sigla}" data-i="{i}" data-hef-forma="@controle" '
            # O NOME PARA QUEM NÃO VÊ. A alavanca é transparente de propósito, e
            # sem isto um leitor de tela anunciaria uma barra sem nome. O texto
            # é o rótulo do próprio parâmetro — nada inventado.
            f'aria-label="{_escapar(str(a["nome"]))}" '
            f'style="{_ALAVANCA}">')
    return (
        f'            <div class="barra" data-ajuste="{sigla}-{i}"{oculta}>\n'
        f'              <span class="nome" data-campo="aj-nome-{sigla}-{i}">'
        f'{_escapar(str(a["nome"]))}</span>\n'
        f'              <span class="trilho"><span class="cheio" '
        f'data-campo="aj-pct-{sigla}-{i}" data-hef-alvo="largura" '
        f'style="width:{a["pct"]}%"></span>{alavanca}</span>\n'
        f'              <span class="num" data-campo="aj-val-{sigla}-{i}">'
        f'{_escapar(str(a["valor"]))}</span>\n'
        f'            </div>')


#: UMA OPÇÃO DE `<select>`, partida na CABEÇA e no TEXTO. O `value` é o
#: contrato (o `name` do preset, que está serializado no perfil dela); o texto
#: é o rótulo, e é só ele que `html_das_opcoes_de_modo` troca. Tudo o mais da
#: cabeça — o `title` com a frase que ELA aprovou, a ordem, o `disabled` do
#: travessão — atravessa intacto.
_OPCAO = re.compile(
    r'(?P<cabeca><option value="(?P<valor>[^"]*)"[^>]*>)(?P<texto>[^<]*)</option>')

_OPCOES_DO_MODO: str | None = None


def _opcoes_cravadas_do_modo() -> str:
    """As opções do campo "Modo" que a página publicada traz, como o DOM as escreve.

    A MESMA COZINHA DE `_opcoes_cravadas_do_pronto`, e pelas mesmas duas razões:
    o `selected` sai (quem escolhe é a pintura do `modo-chave-<lado>`, e um
    `selected` no bloco emitido carregaria a escolha da coluna do desenho para as
    quatro colunas da mesa dela), e o `disabled` vira `disabled=""`, que é como o
    navegador serializa o atributo booleano de volta no `innerHTML`. Sem essa
    segunda troca o piloto reescreveria os oito `<select>` a cada tique, para
    sempre — ver a medição no docstring do irmão.
    """
    global _OPCOES_DO_MODO
    if _OPCOES_DO_MODO is None:
        dentro = ""
        for m in _SELECT.finditer(_pagina_publicada()):
            if m.group("classe") == "modo":
                dentro = m.group("dentro")
                break
        _OPCOES_DO_MODO = _COMO_O_DOM_ESCREVE.sub(
            r' \1=""', dentro.replace(" selected", "")).rstrip()
    return _OPCOES_DO_MODO


def html_das_opcoes_de_modo() -> str:
    """As opções do campo "Modo", com o RÓTULO perguntado ao dono.

    O DONO DO RÓTULO É `app/actions/trigger_specs.PRESETS`, e está escrito lá
    com todas as letras (GATILHO-PALAVRA-01): o `name` é contrato — está
    serializado no perfil dela (`triggers.left.mode`), no IPC (`trigger.set`) e
    no protocolo DSX —, e o `label` é texto de tela. A página carregava uma
    SEGUNDA CÓPIA dos 19 rótulos, digitada à mão no gerador, e duas cópias de um
    texto divergem: MEDIDO no DOM vivo em 03/09/2026, com um controle na mesa,
    **dois rótulos em cada um dos oito `<select>` — 16 divergências**.

    Os dois são decisão DELA, de 07/08/2026, para desambiguar: o produto diz
    ``Arco de flecha (Bow)`` e ``Disparo (Weapon)``; a tela nova dizia ``Arco de
    flecha`` e ``Disparo``. Não é opinião nova sobre o desenho — é a palavra
    dela que esta página não acompanhou.

    O QUE ESTA FUNÇÃO **NÃO** TOCA, e é de propósito: a ordem, o travessão da
    decisão 13 e o `title` de cada modo. A frase da dica é a que ELA aprovou
    nesta tela ("Trava dura do começo ao fim do curso…"), mais concreta que a do
    motor ("Barreira rígida numa posição fixa."), e trocá-la seria pagar a
    dívida do rótulo criando outra. O que se troca é o nó de texto, e só.

    A TROCA É PELO `value`, NUNCA PELA ORDEM. O gerador casava as duas listas
    por posição — e casar por posição é o que faz um `PRESETS` reordenado pôr o
    rótulo de um modo em cima de outro sem nada acusar. Aqui a chave é o
    contrato: a opção `value="Bow"` recebe o rótulo de `Bow`, e uma opção cujo
    `value` o produto não conhece atravessa intacta, porque não é o rótulo dela
    que esta função sabe corrigir (é o caso do `—`).
    """
    specs = _specs()
    if specs is None:
        return _opcoes_cravadas_do_modo()
    do_produto = {p.name: p.label for p in specs.PRESETS}

    def rotular(m: re.Match[str]) -> str:
        rot = do_produto.get(m.group("valor"))
        return m.group(0) if rot is None else f'{m.group("cabeca")}{_escapar(rot)}</option>'

    return _OPCAO.sub(rotular, _opcoes_cravadas_do_modo())


def _opcoes_cravadas_do_pronto() -> str:
    """As opções de "Efeito pronto" que O DESENHO oferece, lidas da página.

    POR QUE LIDAS, e não montadas do produto: o desenho escolheu CINCO das seis
    curvas de `FEEDBACK_POSITION_LABELS` e batizou o `custom` de "— Nenhum —"
    (o produto o chama de "Personalizar"). Os rótulos desta lista são decisão
    DELA, não do motor — montá-los aqui criaria a segunda verdade e trocaria as
    palavras que ela aprovou.

    O CORTE É NO SEPARADOR "Meus efeitos": o que vem antes dele é o desenho; o
    que vem depois são os dois EXEMPLOS que ela mandou manter no desenho e que o
    produto substitui pelo que ela de fato salvou.

    O `selected` SAI de todas. Quem escolhe é a pintura do `pronto-<lado>`, logo
    depois — e um `selected` no HTML emitido faria o bloco carregar a escolha da
    coluna do desenho para as quatro colunas da mesa dela.

    E O `disabled` VIRA `disabled=""`, que não é firula — é a diferença entre um
    bloco trocado UMA vez e um bloco trocado a cada tique, para sempre. O piloto
    só reescreve quando `alvo.innerHTML !== html`, e o `innerHTML` é o que o
    NAVEGADOR serializa, não o que está no arquivo.

    MEDIDO em 02/09/2026, no mesmo Chrome que a régua do desenho usa, escrevendo
    a string emitida e lendo o `innerHTML` de volta::

        emitido:  <option value="—" disabled>—</option>
        de volta: <option value="—" disabled="">—</option>

    Um caractere de diferença, no atributo 43. Com ele, `25 tiques · 25
    pinturas`; sem ele, `21 tiques · 1 pintura`. Um contador que sobe sem nada
    mudar é O instrumento com que esta casa prova que um endereço existe —
    gastá-lo aqui custaria caro, e o DOM ainda seria reescrito quatro vezes por
    segundo.
    """
    global _OPCOES_DO_PRONTO
    if _OPCOES_DO_PRONTO is None:
        dentro = ""
        for m in _SELECT.finditer(_pagina_publicada()):
            if m.group("classe") == "pronto":
                dentro = m.group("dentro")
                break
        antes = dentro.split("<option disabled>", 1)[0].replace(" selected", "")
        _OPCOES_DO_PRONTO = _COMO_O_DOM_ESCREVE.sub(r' \1=""', antes).rstrip()
    return _OPCOES_DO_PRONTO


def _valores_cravados_do_pronto() -> frozenset[str]:
    """Os `value` que o DESENHO já oferece no campo "Efeito pronto"."""
    return frozenset(re.findall(r'<option value="([^"]*)"',
                                _opcoes_cravadas_do_pronto()))


def _tabela_que_o_campo_mostra(modo: str) -> tuple[dict[str, list[int]], dict[str, str]]:
    """A tabela que o campo "Efeito pronto" OFERECE naquele modo.

    NÃO É `_tabela_da_curva`, e a diferença é uma decisão dela. A GUI estável
    ESCONDE a linha de preset fora dos dois modos por posição
    (`_update_preset_row_visibility`); o desenho dela a mostra nos DEZENOVE. Nos
    outros 17 a página crava as curvas de FEEDBACK — logo é a tabela de feedback
    que o campo mostra ali, e o gesto `pronto` já sabe aplicá-las: ele tira o
    modo da TABELA em que a curva mora (ver `_curva`), não do modo de agora.

    O BURACO QUE ISTO TAPA, medido no DOM VIVO em 03/09/2026 com o gatilho em
    `Desligado` e um controle na mesa: os oito campos ofereciam CINCO curvas de
    feedback e não a sexta — `linear_medio`, a firmeza constante. As cinco vêm
    cravadas da página; a sexta só era acrescentada quando `_tabela_da_curva`
    devolvia a tabela de feedback, isto é, **só com o gatilho já em "Curva de
    força"**. Oferecer cinco das seis irmãs é um buraco arbitrário: para
    alcançar a sexta ela teria de trocar o modo antes, e nada na tela dizia.

    `_tabela_da_curva` CONTINUA COMO ESTÁ, e tem de continuar: quem a chama para
    RECONHECER uma curva salva (`_pronto_da_curva`) precisa da tabela do modo
    gravado, e cair no feedback ali nomearia uma curva de vibração com o nome de
    outra tabela.
    """
    presets, rotulos = _tabela_da_curva(modo)
    if rotulos:
        return presets, rotulos
    return _tabela_da_curva(MODO_DA_CURVA)


def _curvas_que_a_pagina_esqueceu(modo: str) -> list[str]:
    """As curvas que o PRODUTO tem naquele modo e a página não oferece.

    A DÍVIDA QUE ISTO PAGA, medida em 03/09/2026 lendo os dois lados:

    * `linear_medio` ("Linear médio", `[4]` dez vezes, a firmeza constante) existe em
      `FEEDBACK_POSITION_PRESETS` desde antes desta aba, a GUI estável a
      oferece, e a lista `PRONTOS` do gerador — digitada à mão — a esqueceu;
    * as CINCO de `VIBRATION_POSITION_PRESETS` (pulso crescente, machine gun,
      galope, senoide, vibração final) nunca chegaram à tela nova: o campo só
      carregava as de feedback.

    Seis curvas do produto fora do alcance de quem clica, e nenhuma régua
    acusava — o gerador reprova um rótulo que o produto NÃO tem, e nunca um que
    o produto tem e a tela esqueceu.

    O RÓTULO É O DO PRODUTO, letra por letra (`FEEDBACK_POSITION_LABELS` /
    `VIBRATION_POSITION_LABELS`). Não invento texto de tela: estas palavras já
    são as que a aba Gatilhos da GUI estável mostra a ela.

    `custom` FICA DE FORA porque a página já o tem, com o nome que ELA aprovou
    ("— Nenhum —", contra o "Personalizar" do motor). Acrescentá-lo daria duas
    opções para a mesma chave, com dois nomes.

    A TABELA É A QUE O CAMPO MOSTRA, e não a do modo — 03/09/2026. Ver
    `_tabela_que_o_campo_mostra`: com o gatilho em `Desligado` esta função
    devolvia lista vazia, e a sexta curva de feedback ficava fora dos oito
    campos até alguém trocar o modo primeiro.
    """
    _, rotulos = _tabela_que_o_campo_mostra(modo)
    if not rotulos:
        return []
    ja_tem = _valores_cravados_do_pronto()
    return [chave for chave in rotulos
            if chave != "custom" and chave not in ja_tem]


def html_das_opcoes_de_pronto(modo: str = MODO_DA_CURVA) -> str:
    """As opções do campo "Efeito pronto": o desenho + o produto + os efeitos DELA.

    A LISTA É DO MODO — 03/09/2026, e é a regra da GUI estável
    (`_populate_preset_combo`): com o gatilho em `MultiPositionVibration` o
    campo mostra as CINCO curvas de vibração; nos outros, as de feedback.
    Escolher uma curva de vibração num campo que só oferece feedback era
    impossível, e é o que fazia as cinco não existirem na tela nova.

    O QUE NÃO MUDOU, e é decisão dela: o campo continua VISÍVEL nos 19 modos. A
    GTK esconde a linha nos outros 17; o desenho dela a mostra sempre, e a
    escolha de produto que isso abre — uma curva escolhida fora dos dois modos
    por posição TROCA o modo — continua na tela como estava, esperando a
    palavra dela.

    É AQUI QUE OS "MEUS EFEITOS" DEIXAM DE SER EXEMPLO. O desenho traz dois
    nomes de exemplo debaixo do separador; o produto traz os que ela salvou —
    e, quando ela não salvou nenhum, **não traz separador nenhum**. É o
    princípio geral dela de hoje: *"se não tá mostrando agora, não tem info pra
    mostrar no produto"*. Um separador com nada embaixo é uma promessa vazia.
    """
    _, rotulos = _tabela_que_o_campo_mostra(modo)
    linhas = [_opcoes_cravadas_do_pronto()]
    # AS DE VIBRAÇÃO SUBSTITUEM, AS DE FEEDBACK COMPLETAM. No modo de vibração
    # as cinco cravadas do desenho são de OUTRA tabela — deixá-las na lista
    # ofereceria a "Stop hard" a um gatilho que não a sabe aplicar. Mas o corte
    # tem de preservar o que a página cravou e não é curva: o travessão e o
    # "— Nenhum —", que são as duas formas de "não há efeito" desta tela.
    if modo == MODO_DA_VIBRACAO:
        cravadas = _opcoes_cravadas_do_pronto().split("\n")
        de_feedback, _ = _tabela_da_curva(MODO_DA_CURVA)
        linhas = [uma for uma in cravadas
                  if not any(f'value="{c}"' in uma for c in de_feedback)]
    for chave in _curvas_que_a_pagina_esqueceu(modo):
        linhas.append(f'                <option value="{chave}">'
                      f'{_escapar(str(rotulos[chave]))}</option>')
    meus = meus_efeitos()
    if meus:
        linhas.append('                <option disabled>──── Meus efeitos ────</option>')
        for nome in sorted(meus):
            linhas.append(
                f'                <option value="{PREFIXO_DO_MEU}{_escapar(nome)}">'
                f'{_escapar(nome)}</option>')
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# O CHIP DA COLUNA — a identidade do controle, e ela VEM DE CIMA.
#
# A LEI, e ela é dela (03/09/2026): *"se no topo tá mostrando controle white
# player 1, então cada aba vai usar os controles lá de cima. Não mistura com a
# info dos mockups."*
#
# O QUE ELA VIU, com os dois controles na mesa e três centímetros entre uma
# coisa e outra: a fita dizendo `P1 · White · USB` e o cabeçalho da coluna logo
# abaixo dizendo `Cosmic Red · USB`. A cor do card não era de controle nenhum
# dela — a fita lia do aparelho e as dez abas abaixo continuavam mostrando o
# controle do desenho.
#
# FATO SUBSTITUÍDO — 04/09/2026, na integração, e não é renumeração: aqui
# estava escrito que *"a fita nem sempre lê: `hefesto_vivo._fita` devolve `""`
# quando QUALQUER controle da mesa está sem cor lida"*, e que por isso, com um
# controle no rádio, a fita ficava no mockup. **Essa guarda não existe mais.**
# Ela dizia `any(not c.get("cor") for c in mesa)` e outra frente a retirou no
# mesmo 03/09 exatamente por mentir: pelo rádio a cor NUNCA chega, então a fita
# ficava eternamente no desenho. Hoje `_fita` só devolve `""` com a MESA VAZIA
# (`hefesto_vivo.py:1161`); quem trata a cor ausente é o `monta.fita`, que
# emite o chip sem `--plastico`. Esta aba continua não dependendo disso: ela lê
# a MESA, controle a controle, e cala sobre quem não disse a cor em vez de
# calar sobre todos.
#
# UM DONO, DOIS CHAMADORES — é a forma que a `fileira_de_players` da aba
# Iluminação já usa. `aba03.py` chama estas funções para desenhar a bancada e o
# `pacote()` as chama a cada tique para pintar o produto. Enquanto eram duas
# escritas, o desenho e o produto podiam divergir sem ninguém ver.
# ---------------------------------------------------------------------------

#: A CLASSE DO EMBRULHO DO CHIP. Ela é a célula da grade, e agora é ela quem
#: CARREGA a cor do aparelho — ver :data:`CAMPO_DO_PLASTICO`.
CLASSE_DO_CHIP = "cabeca"

#: O ENDEREÇO DO MIOLO DO CHIP, e ele mora num `<span>` DENTRO do embrulho.
#:
#: O QUE ELE ESCREVE: o `<span class="chip …">` inteiro — classe, dica e texto
#: de uma vez, pelo alvo `html`. Um bloco cujo conteúdo muda de forma (o chip do
#: lugar vazio não é o do controle na mesa) não se pinta campo a campo.
#:
#: ELE DESCEU UM NÍVEL — 03/09/2026, e a razão é a lei dela. Enquanto ele morava
#: no `.cabeca`, a cor do plástico morava no `style` do `<span>` de dentro, isto
#: é, DENTRO do HTML que o produto compara. Aquilo tinha duas consequências, e a
#: segunda é a que esta frente veio pagar:
#:
#: * o `<span>` nunca podia receber o selo da visita — carimbá-lo poria
#:   `data-hef-visto="1"` dentro do `innerHTML` comparado e a coluna repintaria
#:   a cada tique, para sempre (medido: 17 tiques, 17 pinturas);
#: * logo o `--plastico` ficava num elemento cujo alvo era `texto`, e
#:   `check_a_cor_vem_do_aparelho.py` o contava como cor CRAVADA — com razão:
#:   *"o `escrever()` escreve no elemento que ACHOU"*.
#:
#: Descendo o alvo `html` para um `<span>` de embrulho, a cor sobe para o
#: `.cabeca`, que fica FORA do HTML comparado e pode ter alvo próprio. As duas
#: escritas convivem: cada uma no seu elemento, cada uma com o seu selo.
#:
#: A PÁGINA PUBLICADA CONTINUA FUNCIONANDO com o mesmo pacote, e isso não é
#: acaso: lá o `data-campo` ainda está no `.cabeca`, e o valor que chega é o
#: mesmo HTML do chip. O que ela não tem é o endereço da COR — e é por isso que
#: a cura espera o `--publicar 03`.
CAMPO_DO_CHIP = "chip-do-controle"

#: O ENDEREÇO DA COR DO PLÁSTICO — no EMBRULHO, com o alvo que a alcança.
#:
#: A LEI DELA, 03/09/2026: *"imagina que cada pessoa tenha um dualsense
#: diferente. (…) eu quero que cada um, ao usar seu controle, se toque disso —
#: que o app se adaptou ao controle dele"*. Ela catalogou 28 modelos em
#: `docs/data/cores-do-dualsense.csv`; a aba mostrava o do desenho.
#:
#: O ALVO É `plastico`, e ele é o único que escreve `--plastico`: os outros
#: escrevem texto, largura, fundo, valor, html, classe, cor ou atributo. Vazio e
#: travessão APAGAM a variável, e é assim que a regra dela vale nos dois
#: sentidos — *sem cor lida, sem cor na tela*: o `topo.html` declara
#: `.chip.plastico{border-color:var(--plastico, var(--border-forte))}` e a queda
#: assume sozinha.
#:
#: A VARIÁVEL DESCE POR HERANÇA, que é o que torna o embrulho um lugar legítimo:
#: uma propriedade customizada de CSS vale para toda a subárvore. É o mesmo
#: arranjo da `.moldura` da `05-vibracao`, e pela mesma razão.
#:
#: ELE É `data-campo` E NÃO `data-hef` por uma razão medida: a `cobertura` desta
#: aba conta pintura contra `_enderecos_da_pagina()`, que varre a página
#: publicada por `data-campo=` — um `data-hef` nunca entraria na conta, e a aba
#: pintaria quatro valores que ninguém somaria.
CAMPO_DO_PLASTICO = "plastico"

#: O ALVO que alcança a cor. Escrito uma vez, lido pelo desenho e pelo pacote.
ALVO_DO_PLASTICO = "plastico"

#: O separador dos pedaços do rótulo. É o mesmo `monta.SEPARADOR`, e está aqui
#: como literal pela razão que o `NOME_SEM_LEITURA` do `pacotes/__init__` já
#: documenta: importar `monta` num pacote puxa a árvore inteira do desenho só
#: para ler uma string. A régua nova confere que as duas são a MESMA.
PONTO = ' <span class="pt">•</span> '


def cor_de_borda(tinta: str) -> str:
    """A tinta da zona quando ela É cor, e `""` quando o mapa não tem hex.

    O QUE O MAPA DELA RESPONDE, e são TRÊS formas — `gerar_cores_do_dualsense.
    _tinta` é quem as escreve, a partir de `docs/data/cores-do-dualsense.csv`:

        `#rrggbb`                 o hexadecimal daquela zona
        `url(#casca-<modelo>)`    a casca partida em duas, num gradiente
        `url(#hachura-sem-hex)`   a AUSÊNCIA DECLARADA — *"o acabamento não cabe
                                  num hexadecimal (iridescente, metálico,
                                  camuflado, arte)"*

    Só a primeira é uma cor. E a terceira não é caso raro: **OITO dos vinte e
    oito modelos** respondem hachura na `casca-solida`, que é justamente a zona
    do chip — Grey Camouflage, Chroma Teal, Chroma Indigo, Chroma Pearl, Ghost
    of Yōtei, Marathon, Genshin Impact e 007 First Light.

    MEDIDO NO WEBKIT DESTA MÁQUINA, 03/09/2026, com a regra que o `topo.html`
    declara (`.chip.plastico{border-color:var(--plastico, var(--border-forte))}`)::

        --plastico:#ae335a                → rgb(174, 51, 90)   a cor do plástico
        --plastico ausente                → rgb(98, 114, 164)  a QUEDA declarada
        --plastico:url(#hachura-sem-hex)  → rgb(139, 233, 253) a cor do TEXTO

    A terceira linha é o defeito, e ele é do CSS e não do desenho: uma `var()`
    que resolve para algo que a propriedade não aceita fica **inválida no tempo
    de valor computado**, e nesse caso o navegador NÃO usa a queda escrita ao
    lado — ele volta ao valor herdado, que numa `border-color` é o
    `currentColor`. O chip vestia a cor da LETRA e a dica ao lado dizia, com
    todas as letras, que aquela era a cor do plástico daquele aparelho.

    A REGRA É A DELA: *sem cor lida, sem cor na tela.* Sem `--plastico` a queda
    do `topo.html` vale, a borda fica neutra, e a dica diz por quê.

    O TESTE DO `#` NÃO É NOVO: é o mesmo que `gerar_cores_do_dualsense.legivel`
    já usa, pela mesma razão — *"gradiente, hachura: não são cor"*. Não há
    tabela de cor aqui; quem sabe a cor continua sendo o CSV dela.
    """
    tinta = (tinta or "").strip()
    return tinta if tinta.startswith("#") else ""


def miolo_do_chip(jogador: int, nome: str, via: str,
                  conectado: bool = True) -> str:
    """O texto do chip: `P1 • White • USB`, e cada pedaço só entra se existir.

    O NÚMERO DO JOGADOR É ESTRUTURA, e por isso ele entra sempre: `P1`…`P4` são
    a posição na mesa, não a identidade do aparelho. Ela: *"O p1 ou p2 reflete
    o player do jogador."*

    O NOME E O TRANSPORTE SÃO IDENTIDADE, e por isso eles só entram quando
    foram LIDOS. É a regra dela — *"se não tá mostrando agora, não tem info pra
    mostrar no produto"* —, e ela morde aqui de verdade: a cor por rádio ainda
    não chega, e o chip do controle no rádio sai `P2 • BT` em vez de inventar um
    plástico. Um nome de cor escrito sem leitura é exatamente o defeito que ela
    viu na tela.
    """
    if not conectado:
        return f"P{jogador}{PONTO}Desconectado"
    pedacos = [f"P{jogador}"]
    if nome:
        pedacos.append(nome)
    if via:
        pedacos.append(via)
    return PONTO.join(pedacos)


def a_pagina_recebe_a_cor_por_endereco() -> bool:
    """A página PUBLICADA já tem onde receber a cor por endereço?

    ELA EXISTE PARA NÃO APAGAR A BORDA NA TELA DELA. O desenho de hoje pôs o
    `--plastico` no embrulho, com `data-campo="plastico"`; a página que o
    `WebView` renderiza AGORA não o tem — ela só recebe o chip inteiro pelo alvo
    `html`. Um pacote que escrevesse só no endereço novo deixaria as duas
    colunas dela com a borda neutra até o `--publicar 03`, que é ato dela.

    Medido em 03/09/2026, com a página publicada e um Nova Pink na mesa: a
    borda saía `rgb(68, 71, 90)` — a queda do tema — em vez de
    `rgb(227, 91, 140)`.

    ELA SE APOSENTA SOZINHA. No dia em que a bancada virar produto, o endereço
    passa a existir e este ramo deixa de correr. É a mesma forma de
    `_lugares_que_o_desenho_da_por_vazios` e `_casas_cravadas`: o pacote
    pergunta à PÁGINA o que ela sabe receber, em vez de presumir.
    """
    return CAMPO_DO_PLASTICO in _enderecos_da_pagina()


def chip_do_controle(jogador: int, nome: str, via: str, plastico: str,
                     conectado: bool = True, cor_no_chip: bool = False) -> str:
    """O `<span>` do cabeçalho da coluna, com endereço e sem cor inventada.

    `plastico` é o HEX JÁ RESOLVIDO, e não o *slug*, de propósito: o gerador
    resolve por `monta.cor_da_zona`, que **levanta** num colorway que o desenho
    não tem (é portão, e está certo em levantar); o pacote resolve por
    `_cor_do_plastico`, que devolve `""` — derrubar a pintura da aba por causa
    de um modelo novo seria trocar uma borda que falta por uma tela congelada.
    A política de resolução é de quem chama; a MARCAÇÃO é daqui, e é ela que não
    pode divergir.

    A COR NÃO SAI DAQUI NO DESENHO — 03/09/2026, e é a mudança desta frente. O
    `--plastico` subiu para o EMBRULHO (:func:`_cabeca_do_controle`), que tem
    endereço e alvo próprios; este `<span>` é o miolo que o alvo `html` refaz.
    O parâmetro `plastico` fica porque é ele que decide A DICA, e a dica tem de
    saber separar as duas ausências. Quem julga o que é hex é
    :func:`cor_de_borda`, que recusa o que o mapa dela responde quando não há
    hex. A borda não some: `topo.html` declara
    `.chip.plastico{border-color:var(--plastico, var(--border-forte))}`, com a
    queda já escrita.

    `cor_no_chip` É A PONTE ATÉ O `--publicar 03`, e só o PACOTE a levanta —
    ver :func:`a_pagina_recebe_a_cor_por_endereco`. A página que ela vê hoje não
    tem o endereço da cor; enquanto não tiver, o produto continua mandando a cor
    dentro do chip, como sempre mandou. O DESENHO nunca a levanta: ali a cor tem
    de estar no embrulho, ou a régua a acusa — e com razão, porque num arquivo
    estático ninguém a reescreve.

    **E A DICA ACOMPANHA A COR — 03/09/2026.** Ela dizia *"a borda é a cor do
    plástico"* nos TRÊS casos, e nos dois últimos era mentira: sem hex a borda é
    a neutra do tema, não o plástico de ninguém. São duas ausências diferentes, e
    a tela tem de saber dizer qual é qual — porque uma se conserta lendo o
    aparelho e a outra não se conserta:

        o mapa RESPONDEU e não é cor  o acabamento não cabe num hexadecimal
                                      (:func:`cor_de_borda`, oito dos 28 modelos)
        ninguém leu a cor             pelo rádio ela pode não chegar nunca, hoje

    É a metade que faltava da regra dela: *sem cor lida, sem cor na tela* — e,
    quando não há, dizer POR QUE não há.
    """
    cor = cor_de_borda(plastico)
    classe = "chip plastico" if conectado else "chip vazio"
    if not conectado:
        dica = SEM_APARELHO_AQUI
    elif cor:
        dica = (f"{nome} — a borda é a cor do plástico" if nome
                else "A borda é a cor do plástico deste controle.")
    elif plastico:
        dica = (f"{nome} — o acabamento deste modelo não cabe num hexadecimal, "
                f"e a borda fica neutra" if nome else
                "O acabamento deste modelo não cabe num hexadecimal, e a borda "
                "fica neutra.")
    else:
        dica = (f"{nome} — a cor do plástico deste controle ainda não foi lida"
                if nome else
                "A cor do plástico deste controle ainda não foi lida.")
    estilo = f' style="--plastico:{cor}"' if cor_no_chip and cor else ""
    return (f'<span class="{classe}"{estilo} title="{dica}">'
            f"{miolo_do_chip(jogador, nome, via, conectado)}</span>")


def _cabeca_do_controle(jogador: int, nome: str, via: str, plastico: str,
                        conectado: bool = True) -> str:
    """O cabeçalho INTEIRO da coluna: o embrulho que veste a cor e o miolo.

    ELE É PRIVADO, e o nome diz um fato: **só o gerador monta este elemento**. O
    produto escreve nos dois endereços que ele deixa; nunca refaz a `.cabeca`.
    Público, ele seria uma promessa ao produto sem chamador em produção — e o
    `portao_a_casa_sabe_e_o_produto_nao_faz` acusa isso, com razão: os dez
    `interface/abaNN.py` são BANCADA e saem da conta pela poda dele.

    MORA AQUI E NÃO NO GERADOR porque a MARCAÇÃO tem um dono só. Se o desenho a
    escrevesse por conta própria, a estrutura que ele emite e a que
    :func:`seletor_do_chip` procura divergiriam no primeiro dia em que alguém
    mexesse numa só — e o produto passaria a escrever no lugar errado, calado.

    DOIS ELEMENTOS, DOIS ENDEREÇOS, e a divisão é o ponto:

        .cabeca   `data-campo="plastico"`  alvo `plastico`  → a COR do aparelho
          span    `data-campo="chip-do-controle"` alvo `html` → o CHIP inteiro

    Só o gerador emite esta função — o produto escreve nos dois endereços que
    ela deixa. Aninhá-los é o que permite as duas escritas conviverem: o selo do
    embrulho fica FORA do `innerHTML` que o miolo compara, e o selo do miolo fica
    no elemento que o escreve. Com a cor dentro do miolo (como era até hoje) uma
    das duas tinha de ser sacrificada, e a sacrificada era a cor.

    O EMBRULHO TEM ENDEREÇO NAS QUATRO COLUNAS, inclusive nas vazias, e isso é
    deliberado: a página é estática e o piloto não cria endereço. Sem ele, o dia
    em que um controle entra no P3 a coluna mostra o nome do plástico e uma borda
    neutra — a cor não teria por onde chegar. Onde não há leitura o produto
    escreve o vazio, que APAGA a variável.
    """
    cor = cor_de_borda(plastico) if conectado else ""
    estilo = f' style="--plastico:{cor}"' if cor else ""
    return (f'<div class="{CLASSE_DO_CHIP}" data-campo="{CAMPO_DO_PLASTICO}"'
            f' data-hef-alvo="{ALVO_DO_PLASTICO}"{estilo}>'
            f'<span data-campo="{CAMPO_DO_CHIP}" data-hef-alvo="html">'
            f"{chip_do_controle(jogador, nome, via, plastico, conectado)}"
            f"</span></div>")


def _cor_do_plastico(slug: str) -> str:
    """A TINTA da casca daquele modelo, como o mapa dela a escreve — ou `""`.

    `monta.cor_da_zona` é o dono — ele LÊ a folha que pinta o desenho, em vez de
    digitar hex. O `""` não é desistência: a cor chega pelo broker, uma vez por
    endereço e em thread, então o primeiro tique de uma sessão sempre tem a mesa
    sem cor. **E pelo rádio ela pode não chegar nunca**, hoje: sem hex o chip
    sai com a borda neutra em vez de vestir o plástico de outro controle.

    ELA DEVOLVE A TINTA CRUA, E NÃO SÓ O HEX, de propósito — 03/09/2026. Em oito
    dos 28 modelos a resposta do mapa é a hachura do SEM-HEX, e essas duas
    ausências são diferentes na tela: *"o mapa respondeu, e não é cor"* se
    conserta medindo o plástico; *"ninguém leu"* se conserta lendo o aparelho.
    Quem separa as duas é :func:`chip_do_controle`, com :func:`cor_de_borda` —
    peneirar aqui apagaria a diferença antes de alguém poder dizê-la.
    """
    if not slug:
        return ""
    try:
        import monta  # o `pacotes/__init__` põe `interface/` no `sys.path`

        # `cor_de_css` E NÃO `cor_da_zona` — 03/09/2026. Oito dos 28 modelos
        # dela não têm hexa amostrado e devolvem `url(#hachura-sem-hex)`, que
        # o CSSOM RECUSA EM SILÊNCIO num campo de cor — e o que ficava na
        # tela era o Cosmic Red do MOCKUP, sob um desenho que dizia outro
        # modelo. Ver a razão inteira em `monta.cor_de_css`.
        return str(monta.cor_de_css(slug))
    except (Exception, SystemExit):
        # `cor_da_zona` levanta `SystemExit` para colorway que o SVG não tem, e
        # `SystemExit` não é `Exception` — herda de `BaseException`. Um
        # `except Exception` sozinho passaria ao lado e derrubaria a janela.
        return ""


def _casa_na_mesa(ctx: Contexto, uniq: str) -> dict[str, Any]:
    """A entrada da MESA daquele controle — a mesma que a FITA DO TOPO desenha.

    É esta função que faz a lei valer: a fita sai de `monta.fita(mesa=ctx.mesa)`
    e o chip da coluna sai da MESMA lista. Ler o daemon por outra porta daria
    duas verdades sobre o mesmo controle, que é o defeito de origem.
    """
    for m in ctx.mesa:
        if str(m.get("uniq") or "") == uniq:
            return m
    return {}


def seletor_do_chip(pref: str) -> str:
    """O endereço de bloco do cabeçalho daquela coluna.

    O SELETOR TEM DE ACHAR UM ELEMENTO SÓ — o piloto usa `querySelector`, o
    primeiro que casar. `.cabeca` sozinho acharia o do P1 e escreveria o chip do
    P3 nele; é a mesma armadilha que `_blocos_da_coluna` já documenta.

    ELE MIRA O `data-campo`, E NÃO A CLASSE — 03/09/2026. As duas páginas têm o
    `chip-do-controle` num lugar diferente (na bancada ele desceu para o `<span>`
    de dentro, para o `.cabeca` poder vestir a cor), e um seletor pela CLASSE
    escreveria por cima do embrulho endereçado da bancada — matando, na primeira
    pintura, o endereço da cor que esta frente veio criar. Perguntar pelo
    endereço acha o elemento certo nas duas.
    """
    return f'[data-controle="{pref}"] [data-campo="{CAMPO_DO_CHIP}"]'


def _numero_da_posicao(pref: str) -> int:
    """`p3` → 3. O número do lugar VAZIO, que é posição e não identidade."""
    digitos = "".join(ch for ch in pref if ch.isdigit())
    return int(digitos) if digitos else 0


def _identidade_viva(ctx: Contexto, c: dict[str, Any]) -> tuple[int, str, str, str]:
    """`(jogador, nome, via, plástico)` de um controle que está na mesa AGORA.

    UMA LEITURA SÓ, dois usos: o chip inteiro (`blocos`) e o texto dele
    (`colunas`) saem daqui. Lida duas vezes, ela podia dar duas respostas no
    mesmo tique — e a tela mostraria uma borda de um controle com o nome de
    outro, que é a família de defeito desta frente.
    """
    from . import VIA_DO_TRANSPORTE, identidade_de

    casa = _casa_na_mesa(ctx, str(c.get("uniq") or ""))
    via = str(casa.get("via")
              or VIA_DO_TRANSPORTE.get(str(c.get("transport") or "").lower(), ""))
    # `identidade_de` É O DONO DO NOME NA TELA, e ele já sabe que `"Não sei"`
    # não é nome. O que ele faz e este chip não quer é a ÚLTIMA queda: sem nome
    # nenhum ele devolve o transporte, e o chip escreveria `P2 • BT • BT`. Aqui
    # o transporte já tem lugar próprio, então a queda vira ausência.
    nome = identidade_de(c, ctx.mesa)
    if nome in ("—", via):
        nome = ""
    jogador = casa.get("jogador")
    if not isinstance(jogador, int) or isinstance(jogador, bool):
        jogador = _numero_da_posicao(str(casa.get("pref") or ""))
    return jogador, nome, via, _cor_do_plastico(str(casa.get("cor") or ""))


def _cabecalho_vivo(ctx: Contexto, c: dict[str, Any]) -> tuple[str, str]:
    """`(chip, cor)` de um controle que está na mesa AGORA — de UMA leitura.

    Os dois valores vão para endereços diferentes (o miolo pelo alvo `html`, a
    cor pelo alvo `plastico`) e por isso saem juntos daqui: lidos em duas
    chamadas, `_identidade_viva` podia responder duas mesas no mesmo tique — e a
    coluna vestiria a borda de um controle com o nome de outro, que é a família
    de defeito desta frente.

    A COR VAI PENEIRADA por :func:`cor_de_borda`, e não crua: em oito dos 28
    modelos o mapa dela responde a hachura do SEM-HEX, que não é cor. Escrevê-la
    em `--plastico` deixa a `var()` inválida no tempo de valor computado, e a
    borda vira o `currentColor` — o chip vestindo a cor da LETRA com a dica ao
    lado dizendo que aquela é a cor do plástico. Vazio APAGA a variável, e a
    queda do `topo.html` assume.
    """
    identidade = _identidade_viva(ctx, c)
    chip = chip_do_controle(
        *identidade, cor_no_chip=not a_pagina_recebe_a_cor_por_endereco())
    return chip, cor_de_borda(identidade[3])


def _chip_do_lugar_vazio(pref: str) -> str:
    """O chip de um lugar sem aparelho: a posição e o estado, e mais nada.

    Decisão dela, 31/08/2026: *"na parte do nome do P3 e do P4 colocar algo como
    Desconectado e não os controles mockados."*
    """
    return chip_do_controle(_numero_da_posicao(pref), "", "", "", conectado=False)


@registrar("03-gatilhos.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """Endereço → valor, por controle da mesa. E a caixa de ajustes, em bloco.

    O gatilho é do PERFIL, e o perfil é um só para a mesa inteira — logo as
    colunas recebem o mesmo modo, a menos que o `ControllerOverrides.triggers`
    daquele controle diga outra coisa.

    DUAS COISAS SAEM DAQUI, e elas são de naturezas diferentes:

    * `colunas` — os quatro campos que a página tem endereço para receber
      (`modo-chave-<lado>` e `pronto-<lado>`), pintados campo a campo;
    * `blocos` — a caixa de ajustes e a lista do "Efeito pronto", trocadas
      INTEIRAS, porque o número de filhos delas muda com o dado: a caixa vai de
      zero a onze linhas conforme o modo, e a lista cresce a cada efeito que
      ela salva.

    A COBERTURA CONTA O QUE A PÁGINA RECEBE, e não o que este dicionário tem —
    mudado em 02/09/2026. As chaves que sobram (`l2-raw`, `l2-pct`, `r2-raw`,
    `r2-pct` e o rótulo `modo-e`/`modo-d`) não têm endereço na página publicada;
    contá-las era esta aba dando-se nota por escrever no vazio, que é a mesma
    forma do "77%" que a medição de 02/09 derrubou. Elas continuam saindo — o
    rótulo tem régua que o cobra — e agora estão DITAS em `sem_endereco`.
    """
    specs = _specs()
    p = perfil.ativo(ctx.state.get("active_profile"))
    trig = (p.get("triggers") or {}) if p else {}
    overrides = (p.get("controllers") or {}) if p else {}
    tem_endereco = _enderecos_da_pagina()

    # AS DUAS PODAS DO RASCUNHO, e elas rodam ANTES de qualquer leitura dele:
    # trocar de perfil e sair da mesa desfazem o que foi aplicado, porque o
    # daemon reaplica o perfil nos dois casos. Ver a seção do rascunho.
    _o_rascunho_e_deste_perfil(str(ctx.state.get("active_profile") or ""))
    _o_rascunho_e_de_quem_esta_na_mesa(
        {_chave_do_rascunho(str(c.get("uniq") or ""), "")[0] for c in ctx.conectados})

    lados = {sig: _do_lado(trig.get(disco) or {}, specs) for sig, disco in LADOS.items()}
    #: O `pref` DE CADA CONTROLE, e ele é obrigatório para o `blocos`: a chave
    #: de `colunas` é traduzida por `pacotes.normalizar`, mas um SELETOR CSS vai
    #: cru para o `document.querySelector` do piloto — e a página endereça as
    #: colunas por `p1..p4`, nunca por `uniq`.
    pref_de = {str(m.get("uniq") or ""): str(m.get("pref") or "") for m in ctx.mesa}

    colunas: dict[str, dict[str, Any]] = {}
    blocos: dict[str, str] = {}
    pintados = 0
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        entradas = c.get("inputs") or {}
        l2, r2 = entradas.get("l2_raw"), entradas.get("r2_raw")

        #: O OVERRIDE POR CONTROLE VENCE O PERFIL, e é o que o produto faz —
        #: `ControllerOverrides.triggers` existe no schema desde antes desta aba.
        #:
        #: E O RASCUNHO VENCE OS DOIS, que é a cura de 03/09/2026: o que ela
        #: acabou de aplicar é mais novo do que o que está gravado, e a tela tem
        #: de mostrar o gatilho de AGORA. É a ordem da GTK —
        #: `_refresh_triggers_from_draft` repinta do draft, não do perfil.
        meu = overrides.get(uniq) or {}
        seus = (meu.get("triggers") or {}) if isinstance(meu, dict) else {}
        cfgs = {sig: (_do_rascunho(uniq, disco)
                      or seus.get(disco) or trig.get(disco) or {})
                for sig, disco in LADOS.items()}
        deste = {sig: (_do_lado(cfgs[sig], specs) if cfgs[sig] else lados[sig])
                 for sig in LADOS}

        chip, plastico = _cabecalho_vivo(ctx, c)
        col: dict[str, object] = {
            # O CABEÇALHO DA COLUNA, e ele é IDENTIDADE — vem da mesa, que é a
            # MESMA lista que a fita do topo desenha. Ver `chip_do_controle`.
            #
            # O CHIP INTEIRO, e não só o texto: classe, dica e nome saem juntos
            # pelo alvo `html`. E ele sai por CAMPO — não por bloco — porque só
            # o campo carimba o selo `data-hef-visto`: sem o selo, um controle
            # que por acaso SEJA o Cosmic Red do desenho ficaria classificado
            # como mockup para sempre pela régua do mockup.
            CAMPO_DO_CHIP: chip,
            # A COR DO PLÁSTICO, no embrulho e por endereço próprio — a lei
            # dela, 03/09/2026. Ela vem do MAPA (`monta.cor_da_zona` lê a folha
            # dos 28 modelos), e não de uma tabela deste arquivo: quem tem um
            # Nova Pink recebe o Nova Pink, e o dia em que ela acrescentar um
            # modelo ao CSV a aba o veste sem uma linha de Python a mais.
            CAMPO_DO_PLASTICO: plastico,
            "l2-raw": l2, "r2-raw": r2,
            "l2-pct": round((l2 or 0) / 255 * 100),
            "r2-pct": round((r2 or 0) / 255 * 100),
        }
        for sig, d in deste.items():
            col[f"modo-{sig}"] = d["modo"]
            col[f"modo-chave-{sig}"] = d["modo-chave"]
            # AS DUAS DICAS DO LADO, reescritas a cada tique — decisões [01] e
            # [02] do PO. Elas pousam no `title` do EMBRULHO de cada `<select>`,
            # pelo alvo `atributo`: o campo de escolha já gasta o seu alvo com
            # `valor`, e um `title` cravado no desenho congelaria a explicação
            # do modo que a CENA tinha — que é o defeito de forma que esta aba
            # já pagou quatro vezes (a tela afirmando o que não é).
            col[f"{PREFIXO_DA_DICA_DO_MODO}{sig}"] = descricao_do_modo(
                str(d["modo-chave"]))
            col[f"{PREFIXO_DA_DICA_DO_PRONTO}{sig}"] = dica_do_pronto(
                str(d["modo-chave"]))
            # O EFEITO DELA VENCE A CURVA DO PRODUTO, e a ordem é a única
            # honesta: se a configuração de agora É o "Recuo do MK" que ela
            # salvou, dizer "Stop hard" seria trocar o nome dela pelo do motor.
            meu_nome = _meu_efeito_que_casa(LADOS[sig], cfgs[sig])
            col[f"pronto-{sig}"] = (f"{PREFIXO_DO_MEU}{meu_nome}" if meu_nome
                                    else d["pronto"])
            # A CURVA VAI JUNTO, e ela precisa entrar na CONTAGEM: sem estas
            # duas linhas o perfil "Aventura" — que é curva nos dois lados —
            # pintava 10 valores enquanto o "Ação" pintava 25, e a cobertura
            # diria que a aba está meio ligada quando ela está inteira.
            if d.get("curva"):
                col[f"curva-{sig}"] = d["curva"]
                col[f"curva-pct-{sig}"] = d["curva-pct"]
        colunas[uniq] = col
        pintados += sum(1 for k in col if k in tem_endereco)
        blocos.update(_blocos_da_coluna(pref_de.get(uniq) or uniq, deste,
                                        editavel=True))

    # O LUGAR VAZIO TAMBÉM É ESCRITO — a cura do D4, ver
    # `_lugares_que_o_desenho_da_por_vazios`. A chave é o `pref` cru: o
    # `pacotes.normalizar` traduz `uniq → pref` quando conhece a tradução e
    # deixa passar o que já é `pref`.
    #
    # O VALOR NÃO SE DIGITA: um lugar sem aparelho é um lugar sem configuração
    # de gatilho, e `_do_lado({}, …)` é exatamente isso — a mesma função que
    # traduz o perfil, com o perfil vazio. O que muda é a PALAVRA: pela decisão
    # 13 dela o vazio mostra `—`, e `_sem_nada` a escolhe perguntando à página
    # se ela já oferece o travessão (ver lá).
    ocupados = {str(m.get("pref") or "") for m in ctx.mesa}
    sem_ninguem = _do_lado({}, specs)
    for pref in sorted(_lugares_que_o_desenho_da_por_vazios() - ocupados):
        vazia = {f"modo-chave-{sig}": _sem_nada("modo", str(sem_ninguem["modo-chave"]))
                 for sig in LADOS}
        vazia.update({f"pronto-{sig}": _sem_nada("pronto", str(sem_ninguem["pronto"]))
                      for sig in LADOS})
        # A DICA DO LUGAR VAZIO NÃO EXPLICA MODO NENHUM. Deixar a frase do
        # `Desligado` ali seria a tela explicando o efeito de um aparelho que
        # não está aqui; deixar VAZIO seria pior, porque o `escrever()` do
        # piloto troca vazio por travessão e o `title` viraria um `—` solto.
        vazia.update({f"{pref_}{sig}": SEM_APARELHO_AQUI
                      for pref_ in (PREFIXO_DA_DICA_DO_MODO,
                                    PREFIXO_DA_DICA_DO_PRONTO)
                      for sig in LADOS})
        # O CABEÇALHO DO LUGAR VAZIO É CAMPO, E NÃO BLOCO — 03/09/2026, e é a
        # dívida que esta frente veio pagar. Ele SEMPRE foi escrito (pelo
        # `blocos` mais abaixo), mas bloco pousa por seletor CSS e **não carimba
        # o selo da visita**. Sem selo, a régua do mockup só consegue dar por
        # PRODUTO um campo cujo valor MUDE — e o do lugar vazio não muda nunca:
        # `P3 • Desconectado` é o mesmo no desenho e no produto, por construção.
        # Eram dois campos acusados com o produto já os escrevendo, e o comentário
        # que dizia "o que se perde é o selo, e não faz falta" estava errado: era
        # exatamente o selo que faltava.
        #
        # AQUI PODE E NO P2 NÃO PODE, e a diferença é a de sempre nesta função:
        # emitir uma coluna tira aquele lugar da conta `TODOS_OS_LUGARES -
        # colunas` do piloto, e com ela some o `data-conectado="nao"` que segura
        # o `pointer-events:none`. Nos lugares que a PÁGINA já dá por vazios a
        # marca está no arquivo e isso não custa nada; num que ela dá por
        # conectado, custaria a trava. Por isso o bloco continua existindo, para
        # os lugares que este laço não alcança.
        vazia[CAMPO_DO_CHIP] = _chip_do_lugar_vazio(pref)
        # E A COR SAI, no mesmo tique — 03/09/2026. O vazio APAGA o
        # `--plastico` do embrulho (`escrever` chama `removeProperty`), que é o
        # que a decisão dela pede: *"os demais 3 e o 4 ficam lá com os espaços
        # mas tudo com Desligado e Nenhum, fora a borda do P1 e P2"*. Sem esta
        # linha, um controle que SAI do P1 deixaria a borda dele acesa num lugar
        # sem aparelho — a nona aparição de *a tela afirmando o que não é*.
        vazia[CAMPO_DO_PLASTICO] = ""
        colunas[pref] = vazia
        pintados += sum(1 for k in vazia if k in tem_endereco)

    # A CAIXA DE AJUSTES DE TODO LUGAR SEM APARELHO, e aqui a conta é a LARGA —
    # `_todos_os_lugares_da_pagina`, não só os que o desenho já dá por vazios.
    # Um bloco pousa por seletor CSS, então ele alcança o P2 (que a página dá
    # por conectado) sem tirá-lo da conta `TODOS_OS_LUGARES - colunas` de que
    # depende o `data-conectado="nao"` do piloto. Com um controle só na mesa,
    # sem esta linha, a coluna do P2 ficaria com as três barras do mockup —
    # que é o defeito D3 numa coluna que ninguém olha.
    for pref in sorted(_todos_os_lugares_da_pagina() - ocupados):
        blocos.update(_blocos_da_coluna(
            pref, dict.fromkeys(LADOS, sem_ninguem)))
        # E O CABEÇALHO DELE, pela mesma razão e com o mesmo alcance LARGO: com
        # um controle só na mesa, o P2 é um lugar que a PÁGINA dá por conectado.
        # Sem esta linha ele continuaria com o `Starlight Blue` do desenho — um
        # cabeçalho nomeando um controle que não está aqui, que é o defeito de
        # forma que esta casa já nomeou quatro vezes.
        #
        # AQUI É BLOCO PORQUE NÃO DÁ PARA SER CAMPO, e não porque bloco baste:
        # o campo é melhor — ele carimba o selo da visita, e sem selo a régua do
        # mockup não consegue dar por PRODUTO um valor que coincide com o
        # desenho. Quem PODE ser campo já foi, no laço acima; aqui sobra o lugar
        # que a PÁGINA dá por conectado (o P2 com um controle só na mesa), onde
        # emitir uma coluna custaria o `data-conectado="nao"` que segura o
        # `pointer-events:none`.
        #
        # A FRASE QUE ESTAVA AQUI CAIU — 03/09/2026. Ela dizia: *"o que se perde
        # é o selo, e não faz falta: um lugar sem aparelho não tem valor que
        # possa COINCIDIR com o do desenho"*. Faz falta, e coincide: o desenho
        # crava `P3 • Desconectado` nas duas colunas vazias — é o mesmo texto
        # que o produto escreve, palavra por palavra, porque as duas saem desta
        # mesma função. Sem selo, a régua contava as duas como mockup.
        #
        # A GUARDA PERGUNTA PELO CHIP, e não pela COLUNA. Medido na mordida
        # desta frente: com `pref not in colunas`, arrancar o campo do laço de
        # cima fazia o P3 ficar com cabeçalho NENHUM — a coluna existia (as
        # quatro escolhas), o bloco era pulado, e o desenho ficava na tela sem
        # que nada acusasse. Perguntar pelo que se quer escrever é o que impede
        # uma cura de virar buraco quando a outra sai.
        if CAMPO_DO_CHIP not in (colunas.get(pref) or {}):
            blocos[seletor_do_chip(pref)] = _chip_do_lugar_vazio(pref)

    return {
        "colunas": colunas,
        "blocos": blocos,
        "perfil": ctx.state.get("active_profile") or "",
        "sem_dono": {},
        "cobertura": {"pintados": pintados, "sem_dono": len(SEM_DONO),
                      # O QUE SAI E NÃO TEM ONDE POUSAR, dito em voz alta. Não é
                      # erro — `modo-e` tem régua que o cobra — mas contá-lo como
                      # pintura era a aba dando-se nota por escrever no vazio.
                      "sem_endereco": sum(1 for col in colunas.values()
                                          for k in col if k not in tem_endereco),
                      # OS BLOCOS SÃO PINTURA TAMBÉM, e de um tipo que a conta
                      # acima não alcança: eles não pousam num `data-campo`,
                      # pousam num seletor. Contá-los junto com os campos
                      # inflaria a nota; calá-los faria a aba parecer pintar
                      # quatro coisas quando pinta a caixa inteira.
                      "blocos": len(blocos),
                      # QUANTAS BARRAS A PÁGINA PUBLICADA AINDA CRAVA. Zero é o
                      # dia em que ela publicar a bancada; até lá o bloco pousa
                      # por cima do desenho velho e o sobrescreve. Ver
                      # `_casas_cravadas`.
                      "casas_cravadas": sum(_casas_cravadas().values()),
                      # E SE A CAIXA JÁ PODE CRESCER NELA. Enquanto for `0`, o
                      # bloco se limita ao que a página comporta e diz na tela
                      # quantos ajustes ficaram de fora — ver `_a_caixa_cresce`.
                      "caixa_cresce": sum(_a_caixa_cresce().values())},
    }


def _blocos_da_coluna(pref: str, deste: dict[str, dict[str, Any]],
                      editavel: bool = False) -> dict[str, str]:
    """Os quatro blocos de uma coluna: as duas caixas de ajuste e as duas listas.

    O SELETOR É CSS, e ele tem de achar UM elemento só: o piloto usa
    `document.querySelector` (o primeiro que casar). `[data-controle="p1"]
    .ajustes.e` é único na página; `.ajustes.e` sozinho acharia o do P1 e
    escreveria a caixa do P3 nele.

    A LISTA DO "EFEITO PRONTO" É DO LADO, e não da coluna — 03/09/2026. Ela era
    uma só para os oito campos; agora ela depende do MODO daquele gatilho,
    porque as curvas de vibração só existem em `MultiPositionVibration` (ver
    `html_das_opcoes_de_pronto`). A biblioteca dela continua igual nos oito: o
    que muda é a metade que vem do motor.

    E A LISTA DE "MODO" ENTROU — 03/09/2026, e ela é IGUAL nos oito: os 19
    rótulos não dependem de coluna nem de lado. Ela vem em bloco pela mesma
    razão que a de cima: o rótulo tem dono no produto, e enquanto a página
    publicada carregar a cópia digitada, é o bloco que põe a palavra dela na
    tela sem esperar publicação. Ver `html_das_opcoes_de_modo`.

    O BLOCO NÃO DESFAZ A ESCOLHA, e a ordem é o que garante: o piloto pinta os
    BLOCOS antes dos CAMPOS (`hefesto_vivo`, passo 0 contra passo 2), então o
    `modo-chave-<lado>` reescolhe a opção depois de a lista ser trocada. É o
    mesmo caminho que o `select.pronto` já percorre desde 02/09.
    """
    fora: dict[str, str] = {}
    if not pref:
        return fora
    for sig, d in deste.items():
        fora[f'[data-controle="{pref}"] select.modo[data-lado="{sig}"]'] = (
            html_das_opcoes_de_modo())
        # O TETO VEM DA PÁGINA QUE O PRODUTO RENDERIZA, e é `None` no dia em que
        # ela publicar a bancada. Ver `_a_caixa_cresce`.
        fora[f'[data-controle="{pref}"] .ajustes.{sig}'] = html_dos_ajustes(
            sig, list(d.get("ajustes") or []), _cabem_no_desenho(sig),
            editavel=editavel)
        fora[f'[data-controle="{pref}"] select.pronto[data-lado="{sig}"]'] = (
            html_das_opcoes_de_pronto(str(d.get("modo-chave") or MODO_DA_CURVA)))
    return fora


# ---------------------------------------------------------------------------
# OS GESTOS — o clique dela chegando ao gatilho. Ver o exemplo comentado em
# `a04_iluminacao.py`; o que é PRÓPRIO desta aba está escrito aqui.
#
# NADA SE REESCREVE: o `p` é a `pacotes/ponte.py`, que expõe o
# `app/ipc_bridge.py` — a mesma camada que a aba Gatilhos da GUI estável usa
# (`app/actions/triggers_actions.py:622` e `:701`). O payload, o timeout e a
# tradução da recusa já estão lá.
# ---------------------------------------------------------------------------
from . import gesto  # noqa: E402


def _uniq(o: dict[str, Any]) -> str:
    """O `uniq` da coluna onde ela clicou. Vazio = recusa, nunca "todos".

    ESTA ABA TEM UMA COLUNA POR CONTROLE, e o alcance é a diferença entre um
    ajuste e um estrago: o `trigger.reset` sem `uniq` vai em BROADCAST e zera o
    gatilho dos quatro. Foi o defeito ABAS-06 (25/07), descrito no próprio
    `ipc_bridge.trigger_reset_detalhado`: *"com 'Controle 2' selecionado,
    'Desligar' zerava o gatilho dos QUATRO"*. Aqui ele não pode voltar.
    """
    return str(o.get("uniq") or "")


def _exigir_controle(o: dict[str, Any], gesto_: str) -> str:
    """O `uniq` da coluna, ou uma recusa que DIZ QUAL é o caso. Nunca inventa.

    SÃO DOIS CASOS, e tratá-los pela mesma frase foi um defeito medido em
    02/09/2026. O `hefesto_vivo._gesto` resolve `uniq` percorrendo a mesa por
    `pref`; um clique numa coluna VAZIA não acha nada e chega aqui igualzinho a
    um clique que não trouxe controle nenhum. A frase única — *"o clique não
    disse em qual controle"* — culpa o instrumento quando quem está errado é a
    tela: a página publicada deixa os quatro `<select>` e o "Guardar esse
    efeito" das colunas P3 e P4 CLICÁVEIS, com `data-conectado="nao"` ao lado.

    Fotografado no mesmo dia: as colunas P3 e P4 dizem `Desconectado` no
    cabeçalho e mostram `Desligado` · `— Nenhum —` em campos que abrem. A cura
    de forma é o `disabled` no gerador (`aba03.py`), e publicá-la é ato dela;
    a cura de FUNDO é esta — o gesto recusa, e a frase vai para a tela.
    """
    uniq = _uniq(o)
    if uniq:
        return uniq
    lugar = str(o.get("controle") or "").strip()
    if lugar:
        raise RuntimeError(
            f"{gesto_}: não há controle no lugar {lugar.upper()} — esta coluna "
            f"está vazia. Um gatilho é de um aparelho; sem aparelho não há onde "
            f"aplicar. Ligue um controle neste lugar e ele pega o efeito.")
    raise ValueError(f"{gesto_}: o clique não disse em qual controle")


def _lado(o: dict[str, Any]) -> str:
    """`e`/`d` da tela → `left`/`right` do daemon, pela tradução que já existe.

    O `LADOS` lá em cima é o dono dessa tradução e serve a pintura desde que
    esta aba nasceu — o gesto usa o mesmo, e não uma segunda cópia.
    """
    sigla = str(o.get("lado") or "").strip()
    if sigla not in LADOS:
        raise ValueError(
            f"o clique não disse qual gatilho (veio {sigla!r}; espero 'e' ou 'd'). "
            f"É o `data-lado` do campo de escolha.")
    return LADOS[sigla]


def _escolhido(o: dict[str, Any]) -> str:
    """O que ela escolheu no campo, sem inventar nada quando não veio.

    TRÊS CHAVES, E AS TRÊS SÃO REAIS. `modo` e `v` são o `data-modo` e o
    `data-v` que o ouvinte do piloto manda a partir do dataset do elemento
    clicado; `valor` é `alvo.value`, e é por ele que um `<select>` entrega a
    escolha.

    FATO SUBSTITUÍDO — esta docstring dizia que *"o piloto único não trouxe esse
    ramo, e é por isso que os campos de escolha desta aba ainda não entregam a
    escolha"*. Deixou de ser verdade: o ouvinte manda `valor` (e `rotulo`) desde
    que ganhou o `change`, com a razão escrita lá — *"num `<input>` o texto é
    vazio, e num `<select>` é a lista INTEIRA de opções"*. Guardar a frase velha
    ao lado do código que a desmente obrigaria a próxima pessoa a escolher entre
    duas afirmações.

    A ORDEM IMPORTA e é a de especificidade: um `data-modo` no elemento é uma
    escolha DECLARADA no botão; o `value` do campo é o que sobrou de mais geral.
    """
    return str(o.get("modo") or o.get("v") or o.get("valor") or "").strip()


def _desfecho(resposta: Any) -> tuple[bool, str, dict[str, Any] | None]:
    """`(ok, motivo, corpo)` de uma resposta da ponte, que tem TRÊS formas.

    `trigger_set` devolve `bool`, `trigger_set_checked` devolve `(ok, motivo)` e
    `trigger_set_detalhado` devolve `(ok, motivo, corpo)`. Normalizar aqui é o
    que permite o gesto RECUSAR DIZENDO sem depender de qual das três a ponte
    entregou — e um `ok, motivo = ...` rígido rebentaria com um `TypeError` na
    primeira troca de porta, que é erro sobre erro.

    O CORPO DEIXOU DE SER JOGADO FORA — 03/09/2026, e era a terceira mentira
    desta aba. Esta função reduzia a resposta a `(ok, motivo)`, e com isso três
    desfechos diferentes chegavam à tela como o mesmo silêncio de sucesso:

    * `{status: ok, aplicado_em: [], guardado_em: []}` — **nada aconteceu**, e é
      a rota que a bancada mediu em 23/08 com a aba dizendo "aplicado";
    * `guardado_em` com alguém — a intenção ficou guardada e o gatilho dela
      **não mudou**;
    * `status: ok` COM `motivo` — a recusa que vem dentro de uma resposta
      bem-sucedida (`ipc_bridge._recusa_no_corpo`), que `trigger_set_detalhado`
      entrega com `ok=True`.

    `None` quer dizer *"não há corpo a ler"* — a ponte antiga, ou o dublê da
    régua. Nesse caso quem decide continua sendo o `ok`, exatamente como antes.
    """
    if isinstance(resposta, tuple):
        motivo = resposta[1] if len(resposta) > 1 else ""
        corpo = resposta[2] if len(resposta) > 2 else None
        return (bool(resposta[0]), str(motivo or ""),
                corpo if isinstance(corpo, dict) else None)
    return bool(resposta), "", None


def _na_lingua_da_tela(motivo: str, modo: str) -> str:
    """A recusa do daemon na língua dos rótulos desta aba. Sem dono novo.

    O TRADUTOR JÁ EXISTIA E NINGUÉM O CHAMAVA. `triggers_actions.
    humanizar_erro_gatilho` (`app/actions/triggers_actions.py:53`) é a HARM-19,
    escrita e testada para a aba Gatilhos da GUI estável: o daemon fala a língua
    do `core/trigger_effects` — *"end (3) deve ser > start (5)"* — e ela devolve
    *"Fim (3) precisa ser maior que Início (5)"*, com os MESMOS rótulos que o
    `<select>` desta tela mostra, porque tira os dois do mesmo `spec.params`.
    Conferido em 02/09/2026: zero pacotes da interface nova a chamavam, e a
    recusa chegava CRUA à tela dela.

    O `_rotulo_do_param` (`:45`) FICA PRIVADO, e é decisão escrita: quem precisa
    dele é esta função, que já o usa por dentro. Torná-lo público criaria uma
    segunda porta para a mesma tradução — e a próxima pessoa teria de escolher
    entre duas, que é o defeito que a regra do dono único existe para matar.

    O MOTIVO CRU VOLTA INTEIRO quando não há tradução, e é deliberado: o
    `humanizar_erro_gatilho` devolve `None` para todo formato que não conhece
    (*"aí o chamador mostra o texto cru do daemon, que ainda diz mais que
    'daemon offline?'"*, palavras do próprio docstring dele). Calar aqui seria
    trocar uma frase feia por nenhuma.

    E ELE NÃO PODE DERRUBAR O GESTO. O módulo do tradutor importa `Gtk` no topo;
    numa árvore sem PyGObject o import levanta, e um `except` que virasse erro
    faria a interface recusar um clique VÁLIDO por causa da tradução da recusa.
    """
    if not motivo:
        return motivo
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.actions.triggers_actions import (
            humanizar_erro_gatilho,
        )
    except Exception:
        return motivo
    specs = _specs()
    spec = specs.get_spec(modo) if specs else None
    return humanizar_erro_gatilho(motivo, spec) or motivo


def _padroes(nome: str) -> list[int]:
    """Os ajustes PADRÃO daquele modo, na ordem em que o daemon os lê.

    NÃO SE DIGITA NENHUM NÚMERO. `preset_to_positional_params(spec, {})` devolve
    `[p.default for p in spec.params]`, que é a mesma lista que a GUI estável
    monta nos sliders ao trocar de modo (`triggers_actions._rebuild_params` →
    `_apply_trigger`), e a mesma ordem que `_persist_params_to_draft` grava —
    *"usa SEMPRE a lista posicional plana na ordem do spec"*.

    E ELA JÁ É O FORMATO DO FIO PARA OS TRÊS MODOS "ESPECIAIS", conferido contra
    `triggers_actions._send_trigger_named`: `MultiPositionFeedback` tem
    `pos_0..pos_9` (= `strengths`), `MultiPositionVibration` tem
    `frequency, pos_0..pos_9` (= `[freq, *strengths]`) e `Custom` tem
    `mode, force_0..force_6` (= `[mode, *forces]`). Os três casos que aquela
    função trata à mão saem prontos daqui — não há caso especial a reescrever.
    """
    specs = _specs()
    if specs is None:
        raise RuntimeError(
            "modo: não consegui abrir `app/actions/trigger_specs.py`, e sem ele "
            "não sei quais ajustes este modo tem. Mandar `params` vazio faria o "
            "daemon aplicar um efeito sem zona ativa — o gatilho ficaria solto e "
            "a tela diria que aplicou.")
    spec = specs.get_spec(nome)
    if spec is None:
        raise ValueError(
            f"modo: {nome!r} não é um dos 19 modos do produto "
            f"(`app/actions/trigger_specs.PRESETS`).")
    return list(specs.preset_to_positional_params(spec, {}))


def _curva(chave: str) -> tuple[list[int], str]:
    """`(as dez intensidades, o modo em que elas existem)` daquele efeito pronto.

    O MODO SAI DA TABELA EM QUE A CURVA MORA, e não de uma constante: as duas
    tabelas do produto não compartilham chave nenhuma
    (`rampa_crescente`… contra `pulso_crescente`…), então saber DE ONDE a curva veio
    é saber em que modo ela existe. Antes desta linha o gesto mandava sempre
    `MultiPositionFeedback`, e as cinco curvas de vibração não tinham como ser
    aplicadas nem que a lista as oferecesse.
    """
    tp = _prontos()
    if tp is None:
        raise RuntimeError(
            "efeito pronto: não consegui abrir `profiles/trigger_presets.py`.")
    for modo_, resolver in ((MODO_DA_CURVA, tp.resolve_feedback_preset),
                            (MODO_DA_VIBRACAO, tp.resolve_vibration_preset)):
        valores = resolver(chave)
        if valores:
            return list(valores), modo_
    raise ValueError(
        f"efeito pronto: {chave!r} não é uma curva do produto "
        f"(`profiles/trigger_presets.FEEDBACK_POSITION_PRESETS` nem "
        f"`VIBRATION_POSITION_PRESETS`).")


def _params_da_curva(modo_: str, curva: list[int]) -> list[int]:
    """As dez posições postas nos parâmetros `pos_*` do modo, o resto no padrão.

    É O QUE A GTK FAZ, e por que ela precisa fazer: em
    `MultiPositionVibration` o spec tem ONZE parâmetros — `frequency` mais
    `pos_0..pos_9` — e a curva tem DEZ. `_on_preset_changed` pula o slider de
    frequência por nome (`if nome == "frequency": continue`) e escreve só os
    `pos_N`. Alinhar por índice poria a posição 0 debaixo da frequência: um
    número certo com o nome errado, e o efeito errado no fio.

    A frequência (e qualquer outro parâmetro que não seja posição) fica no
    PADRÃO do modo, que é o que o `preset_to_positional_params` devolve.
    """
    specs = _specs()
    fora = _padroes(modo_)
    if specs is None:
        return fora
    spec = specs.get_spec(modo_)
    posicoes = [i for i, q in enumerate(spec.params) if q.name.startswith("pos_")]
    for i, valor in zip(posicoes, curva, strict=False):
        fora[i] = int(valor)
    return fora


def _aplicar(p: Any, lado: str, modo_: str, params: list[int],
             uniq: str, ctx: Contexto | None = None) -> tuple[bool, str, str]:
    """Manda o efeito ao daemon pela porta CERTA, e a certa depende do modo.

    "DESLIGADO" É `trigger.reset`, E NÃO `trigger.set` COM `Off` — a R-19. O
    `_handle_trigger_set` do daemon termina em `mark_manual_trigger_active`:
    mandar `Off` por ali ARMA a trava que pausa a troca automática de perfil,
    e o `trigger.reset` faz o oposto. Está escrito com todas as letras em
    `triggers_actions._reset_trigger`: *"o botão que a usuária usa para 'voltar
    ao normal' era mais um jeito de PAUSAR a troca automática de perfil, sem
    nada na tela dizendo isso"*.

    A FUNÇÃO EXISTE PORQUE HÁ TRÊS CHAMADORES — o `modo`, o `pronto` quando
    aplica um efeito dela, e a régua. Escrito três vezes, o `if chave == "Off"`
    some num deles no dia em que alguém mexer, e a trava volta calada.

    E ELA É O CHOKE POINT DO RASCUNHO — 03/09/2026. Toda escrita no gatilho
    passa por aqui, então é aqui que a tela aprende o que foi aplicado. É o
    lugar da GTK: `_persist_params_to_draft` é chamado ANTES de todo envio
    (`triggers_actions.py:597`), pela mesma razão — quatro chamadores gravando
    o draft por conta própria seria o quarto que esquece.

    O RASCUNHO SÓ RECEBE O QUE O DAEMON ACEITOU. Guardar antes faria a tela
    afirmar um efeito que o aparelho recusou — trocaria a mentira de hoje (a
    escolha some) por uma pior (a escolha fica, e é falsa).

    E ELE DEVOLVE O RECIBO — 04/09/2026, a D-01. A terceira casa é a frase de
    SUCESSO daquele envio, e ela sai daqui porque é aqui que o CORPO do daemon
    existe: montá-la nos quatro chamadores seria o quarto que esquece, que é o
    mesmo argumento pelo qual o rascunho já mora nesta função.
    """
    if modo_ == "Off":
        ok, motivo, corpo = _desfecho(p.trigger_reset_detalhado(lado, uniq=uniq))
        params = []
    else:
        ok, motivo, corpo = _desfecho(
            p.trigger_set_detalhado(lado, modo_, params, uniq=uniq))
    if ok and _chegou_ao_aparelho(corpo):
        _lembrar_o_aplicado(str((ctx.state if ctx else {}).get("active_profile") or ""),
                            uniq, lado, {"mode": modo_, "params": params})
    ok, motivo = _conferir_o_desfecho(lado, modo_, ok, motivo, corpo, ctx, uniq)
    return ok, motivo, _recibo(lado, modo_, corpo, ctx, uniq)


#: OS DOIS CAMPOS EM QUE O DAEMON DIZ ONDE A ESCRITA FOI PARAR. O vocabulário é
#: dele (`_destinos_por_uniq`, MESA-CHEIA-09) e quem os LÊ é
#: `ipc_bridge.destinos_da_aplicacao`; aqui eles servem só para uma pergunta
#: anterior, que aquela função não pode responder — ver `_fala_de_destino`.
_CAMPOS_DE_DESTINO = ("aplicado_em", "guardado_em")


def _fala_de_destino(corpo: dict[str, Any] | None) -> bool:
    """O corpo diz alguma coisa sobre ONDE a escrita foi parar?

    ESTA PERGUNTA VEM ANTES DE `destinos_da_aplicacao`, e a distinção não é
    firula: aquela função devolve `([], [])` tanto para *"o daemon disse que
    nenhum controle recebeu"* quanto para *"este corpo não fala disso"*. As
    duas coisas são diferentes, e tratá-las igual faria a tela afirmar um
    diagnóstico que ninguém mediu — que é exatamente o defeito que a própria
    `NADA_ACONTECEU` documenta do outro lado (*"olhei e não sei por quê" é uma
    resposta, e disfarçá-la de diagnóstico é o defeito de forma*).

    É A MESMA DISTINÇÃO QUE `_corpo_do_daemon` já faz um nível acima, entre
    `None` ("não houve resposta utilizável") e `dict` ("o daemon falou"): aqui
    ela desce um degrau e pergunta se ele falou DISTO.

    MEDIDO: o dublê da régua devolve `(True, "", {})`. Sem esta guarda, todo
    gesto provado por dublê passava a levantar *"nenhum controle recebeu"* —
    a régua reprovando a cura em vez do defeito, que é a forma de erro mais
    repetida desta casa.
    """
    return isinstance(corpo, dict) and any(c in corpo for c in _CAMPOS_DE_DESTINO)


def _chegou_ao_aparelho(corpo: dict[str, Any] | None) -> bool:
    """O byte SAIU no fio para alguém — a pergunta que decide o rascunho.

    Sem corpo — ou com um corpo que não fala de destino — a resposta é SIM, e é
    a de sempre: a ponte antiga e o dublê da régua não dizem onde a escrita
    parou, e o `ok` é tudo o que existe para ler. Com corpo que fala, quem
    responde é `ipc_bridge.destinos_da_aplicacao` — dono único da leitura de
    `aplicado_em`/`guardado_em`, para nenhuma aba ler esses dois campos por
    conta própria.

    GUARDADO NÃO CONTA. Um efeito que ficou registrado sem sair do fio não é o
    que está no gatilho dela agora; pintá-lo na tela seria a tela afirmando um
    estado que o aparelho não tem — o defeito que o rascunho veio matar, do
    outro lado.
    """
    if not _fala_de_destino(corpo):
        return True
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.ipc_bridge import destinos_da_aplicacao
    except Exception:
        return True
    aplicado, _ = destinos_da_aplicacao(corpo)
    return bool(aplicado)


def _como_a_janela_pergunta(ctx: Contexto | None, uniq: str) -> Any:
    """O `host` que `frase_do_desfecho` interroga, com o que ESTA aba sabe.

    A GTK lê três coisas do objeto da janela para explicar um "guardado": o
    alvo de edição, o mapa de conectados e o Modo Nativo. Esta aba SABE as três,
    e melhor do que a GTK — ela não tem alvo de edição, tem uma COLUNA POR
    CONTROLE, e a coluna clicada é o alvo sem ambiguidade nenhuma.

    POR QUE UM DUBLÊ E NÃO UMA SEGUNDA FRASE: `app/textos_de_aplicacao.py` é o
    dono único do vocabulário de aplicado/guardado/nada-aconteceu, e a D-9 diz
    com todas as letras por que ele é um só — *"para que trocá-lo seja uma
    linha, e não uma caçada por strings"*. Escrever aqui "guardado, vai valer
    quando…" seria a sexta cópia.

    OS TRÊS ATRIBUTOS SÃO OS DO CONTRATO, e não inventados:
    `_alvo_de_edicao` (o canônico de `app/alvo_de_edicao.py`),
    `_target_uniq_by_index` (o mapa que a aba Status recalcula do `state_full`)
    e `_modo_nativo_ligado` (o `native_mode` do mesmo `state_full`).
    """
    from hefesto_dualsense4unix.app.alvo_de_edicao import AlvoDeEdicao, EstadoDoAlvo

    conectados = list((ctx.conectados if ctx else []) or [])
    rotulo = ""
    for c in conectados:
        if str(c.get("uniq") or "") == uniq:
            # `jogador_de` E NÃO `c.get("player")`: o daemon publica DUAS
            # chaves, e quem NÃO é jogador do co-op tem `player: None` com
            # `player_slot` preenchido. Lendo cru, o secundário do co-op vinha
            # à tela como "Controle ?" — o mesmo defeito que a `jogador_de`
            # nasceu para matar, aqui de novo pelo caminho do rótulo.
            rotulo = f"Controle {jogador_de(c) or '?'}"
            break

    class _Janela:
        def __init__(self) -> None:
            self._alvo_de_edicao = AlvoDeEdicao(EstadoDoAlvo.CONTROLE, uniq=uniq,
                                                label=rotulo or None)
            self._target_uniq_by_index = {i: str(c.get("uniq") or "")
                                          for i, c in enumerate(conectados)}
            self._modo_nativo_ligado = bool(
                (ctx.state if ctx else {}).get("native_mode"))

    return _Janela()


def _assunto(lado: str, modo_: str) -> str:
    """`"Gatilho esquerdo (L2): Rigid"` — o assunto de toda frase desta aba.

    UM SÓ, e é o ponto: a recusa e o recibo falam do mesmo gatilho, e escrever a
    mesma construção duas vezes é como se acaba com duas frases para o mesmo
    fato. É a MESMA que `triggers_actions._toast_trigger` monta na barra da GTK
    — inclusive no `preset_id` cru, que é uma dívida conhecida desta casa e não
    uma escolha desta função (ver o relatório desta frente).

    O NOME DO LADO É A CURA TRG-01: a barra dizia `"LEFT -> Off"`, trocando a
    fala dela pelo id interno mais o lado em inglês.
    """
    return f"{NOME_DO_LADO.get(lado, lado)}: {modo_}"


def _recibo(lado: str, modo_: str, corpo: dict[str, Any] | None,
            ctx: Contexto | None, uniq: str) -> str:
    """A frase de SUCESSO que vai ao CARTÃO daquele controle — a D-01 em ato.

    **O DEFEITO QUE ELA FECHA**, e ele é a queixa de origem desta casa: quando
    dava certo, a tela não dizia nada. O piloto imprimia `[gesto] … → aplicado`
    no terminal de quem lançou a janela, e quem clica não lê terminal. A decisão
    dela, 04/09/2026: *"No próprio cartão, como a recusa."*

    **NÃO HÁ CANAL NOVO AQUI, e é o ponto inteiro do conflito C-3.** A lista
    desta aba propunha *o campo que pisca*; ela escolheu o cartão, que é a mesma
    peça das outras quatro abas. Esta função só ESCREVE a frase — quem a leva ao
    cartão é o `hefesto_vivo._deu_certo_dizendo`, lendo o `recado` que o gesto
    devolve.

    A FRASE É DO DONO DO ASSUNTO: `app/textos_de_aplicacao.frase_do_desfecho`,
    a mesma que a barra da GTK usa, com o CORPO do daemon como autoridade — é
    ela que sabe dizer *"aplicado em 2 controles"* em vez de um "aplicado" que
    não conta.

    **O CORPO QUE NÃO FALA DE DESTINO NÃO PASSA POR ELA**, e essa guarda é a
    lição de 04/09: o dublê da régua devolve `{}`, e `frase_do_desfecho` leria
    as duas listas vazias como *"nenhum controle recebeu"* — um recibo de
    SUCESSO afirmando que nada aconteceu. É a mesma armadilha que
    `_fala_de_destino` já documenta do outro lado, e a resposta é a mesma
    pergunta.
    """
    assunto = _assunto(lado, modo_)
    if not _fala_de_destino(corpo):
        return f"{assunto} aplicado"
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.textos_de_aplicacao import frase_do_desfecho

        return frase_do_desfecho(assunto, corpo, _como_a_janela_pergunta(ctx, uniq))
    except Exception:
        # O TRADUTOR NÃO PODE CALAR O RECIBO, pela mesma razão que ele não pode
        # derrubar o gesto em `_conferir_o_desfecho`: sem ele a frase é a curta,
        # e a curta ainda diz mais que o silêncio que esta peça veio curar.
        return f"{assunto} aplicado"


def _conferir_o_desfecho(lado: str, modo_: str, ok: bool, motivo: str,
                         corpo: dict[str, Any] | None,
                         ctx: Contexto | None, uniq: str) -> tuple[bool, str]:
    """Levanta quando o gatilho dela NÃO mudou, com a frase do dono do assunto.

    A DÍVIDA QUE ISTO PAGA, e ela é a feature 19 da medição de 03/09: *"dizer
    na tela o desfecho — aplicado, guardado para depois, nada aconteceu"*. A
    GTK escreve na barra de status a cada Aplicar, lendo o CORPO do daemon
    (`_toast_trigger` → `frase_do_desfecho`, ELO-MUDO-01/T3). O HTML jogava o
    corpo fora, e três desfechos diferentes viravam o mesmo nada.

    O CANAL É O `RuntimeError`, e é o único que esta tela tem: o piloto leva a
    frase de um `RuntimeError` ao CARTÃO daquele controle
    (`hefesto_vivo._recusou_dizendo`) e não tem por onde levar a de um sucesso.
    Então a regra é a honesta: **cala quando o byte saiu, fala quando não
    saiu.** O "aplicado" na tela — a outra metade da feature 19 — precisa de um
    lugar na página, e lugar na página é dela.

    SÃO DOIS OS CASOS QUE FALAM, e o segundo é o mais fino:

    * nada saiu no fio (as duas listas vazias, ou só `guardado_em`);
    * o corpo traz `motivo` COM `status: ok` — sucesso PARCIAL
      (`ipc_bridge._recusa_no_corpo`). O `ok` continua `True` e o byte pode até
      ter saído, mas o daemon disse alguma coisa e essa coisa é dela.

    A RECUSA SECA (`ok=False`) NÃO PASSA POR AQUI: quem a trata é o chamador,
    que sabe nomear o que tentou aplicar ("o seu efeito 'Recuo do MK'", "a curva
    'stop_hard'"). Repetir a decisão aqui daria duas frases para a mesma recusa.

    SEM CORPO NÃO HÁ O QUE CONFERIR: a ponte antiga e o dublê da régua não
    devolvem corpo, e nesse caso o `ok` decide, palavra por palavra como antes.

    O ASSUNTO É A FRASE DA GTK, e não uma escrita aqui: `_toast_trigger` monta
    `"Gatilho esquerdo (L2): <modo>"` — a cura TRG-01, que existe porque a barra
    dizia `"LEFT -> Off"`, trocando a fala dela por id interno mais o lado em
    inglês. A tela nova não vai reintroduzir o defeito com outro atalho.
    """
    assunto = _assunto(lado, modo_)
    if not ok or corpo is None:
        return ok, motivo
    calado = ((not _fala_de_destino(corpo) or _chegou_ao_aparelho(corpo))
              and not str(corpo.get("motivo") or ""))
    if calado:
        return ok, motivo
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.app.textos_de_aplicacao import frase_do_desfecho

        frase = frase_do_desfecho(assunto, corpo, _como_a_janela_pergunta(ctx, uniq))
    except Exception:
        # O TRADUTOR NÃO PODE DERRUBAR O GESTO nem calar o defeito. Sem ele a
        # frase é crua, e crua ainda diz mais que silêncio — é a mesma escolha
        # que `_na_lingua_da_tela` já faz com o motivo do daemon.
        frase = f"{assunto} — o daemon respondeu, e nenhum controle recebeu."
    raise RuntimeError(frase)


@gesto("03-gatilhos.html", "modo")
def modo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Escolher um modo APLICA o efeito naquele gatilho, naquele controle.

    É O QUE O PRÓPRIO DESENHO PROMETE, na dica do quadro: *"Escolher um modo já
    manda o efeito para aquele controle, e quem está com ele na mão sente na
    hora"* — e *"soltar já manda"*. É também a decisão dela de 01/09 para a
    interface inteira: o gesto age na hora, e não junta rascunho.

    E É O QUE A GUI ESTÁVEL FAZ. `triggers_actions._on_mode_changed` remonta os
    ajustes nos padrões do modo (`_rebuild_params`) e agenda o live-preview de
    300 ms, que chama `_apply_trigger` com esses mesmos padrões. Aqui não há
    debounce a fazer: o clique é um, não um arrastar de slider.

    "DESLIGADO" É `trigger.reset`, E NÃO `trigger.set` COM `Off` — e esta é a
    parte que não se adivinha pelo nome. O `_handle_trigger_set` do daemon
    termina em `mark_manual_trigger_active("trigger")`: mandar `Off` por ali
    ARMA a trava que pausa a troca automática de perfil. O `_handle_trigger_reset`
    faz o oposto, `clear_manual_trigger_active("trigger")`. É a R-19, escrita com
    todas as letras em `triggers_actions._reset_trigger`: *"o botão que a usuária
    usa para 'voltar ao normal' era mais um jeito de PAUSAR a troca automática de
    perfil, sem nada na tela dizendo isso"*.

    A PORTA É A `_detalhado`, e não a `_checked`, pela mesma razão que a GUI
    estável migrou (ELO-MUDO-01/T3): só ela junta as DUAS formas de o daemon
    dizer não — o erro JSON-RPC de parâmetro inválido e a recusa que vem DENTRO
    de uma resposta bem-sucedida (`_recusa_no_corpo`). Com a `_checked`, a
    segunda chegaria como sucesso.
    """
    uniq, lado = _exigir_controle(o, "modo"), _lado(o)
    chave = _escolhido(o)
    if not chave:
        raise ValueError(
            "modo: o clique não trouxe qual modo foi escolhido. O `<select>` "
            "carrega a chave no `value` de cada opção; quem tem de mandá-la é a "
            "ponte do piloto, no `change` — ver `_escolhido`.")
    if chave == TRAVESSAO:
        # O TRAVESSÃO É O VAZIO, NÃO UMA ESCOLHA — decisão 13 dela. Ele nasce
        # desabilitado no desenho, então este caminho só se alcança por JS; e
        # aplicar "nada" como se fosse um modo seria o botão que responde calado.
        raise ValueError(
            "modo: `—` é como esta tela diz que não há controle neste lugar, e "
            "não um efeito a aplicar. Escolha `Desligado` para soltar o gatilho.")
    ok, motivo, recibo = _aplicar(p, lado, chave, _padroes(chave), uniq, ctx)
    if not ok:
        raise RuntimeError(_na_lingua_da_tela(motivo, chave)
                           or f"o daemon não aplicou o modo {chave!r}")
    return {"recado": recibo}


@gesto("03-gatilhos.html", "pronto")
def pronto(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Escolher um efeito pronto põe aquela CURVA no gatilho, na hora.

    O EFEITO PRONTO TEM DONO, e o dono é `profiles/trigger_presets.py`. São
    ONZE curvas em DUAS tabelas: seis em `FEEDBACK_POSITION_PRESETS` (as cinco
    do desenho mais `linear_medio`) e cinco em `VIBRATION_POSITION_PRESETS`.
    Cada uma resolve para dez intensidades de 0 a 8.

    FATO SUBSTITUÍDO — 03/09/2026. Esta docstring dizia, e a nota do
    `MODO_DA_CURVA` repetia: *"Uma curva de dez posições SÓ existe como
    `MultiPositionFeedback`"*. **É falso**, e o produto o desmente em duas
    linhas: `MultiPositionVibration` tem `frequency, pos_0..pos_9` no
    `trigger_specs`, e o `_MODES_COM_PRESET` da GUI estável lista os DOIS. Foi
    essa afirmação que manteve as cinco curvas de vibração fora do alcance
    desta tela — o gesto mandava sempre o modo de força. Agora o modo sai da
    TABELA em que a curva mora (ver `_curva`).

    E ELE TROCA O MODO NOS OUTROS 17 — está dito aqui porque é a única coisa
    deste gesto que não é dedução direta do produto. Na GUI estável a linha de
    preset nem aparece fora dos dois modos por posição
    (`_update_preset_row_visibility`). No desenho ela aparece sempre, para os
    19 — então escolher "Stop hard" com o modo em "Metralhadora" só pode querer
    dizer *"põe este gatilho na curva Stop hard"*. **Isto é escolha de produto
    e é dela**; está no relato para ela decidir. O que não faço é a alternativa
    calada: aplicar dez intensidades num modo que não tem posições, que o
    `build_from_name` recusaria e a tela não explicaria.

    "— Nenhum —" NÃO APLICA NADA, e recusa dizendo. O `value` dele é `custom`,
    que é o token do próprio produto para "os valores são os que estão aí" —
    não há curva a mandar, e mandar o modo "de volta ao normal" seria confundir
    este campo com o "Desligado" do campo de cima.

    E OS "MEUS EFEITOS" PASSARAM A EXISTIR — decisão 17 dela, 02/09/2026. Uma
    opção `meu:<nome>` é um efeito que ELA salvou (ver `meus_efeitos`), e o que
    se aplica é a metade DESTE gatilho do par que ela guardou. Até hoje esta
    função recusava dizendo *"não há onde guardar nem de onde ler um efeito com
    nome"*; agora há, e a frase saiu junto com o defeito.
    """
    uniq, lado = _exigir_controle(o, "efeito pronto"), _lado(o)
    chave = _escolhido(o)
    if chave.startswith(PREFIXO_DO_MEU):
        nome = chave[len(PREFIXO_DO_MEU):]
        meia = _meia_do_efeito(meus_efeitos().get(nome), lado)
        if meia is None:
            raise RuntimeError(
                f"'{nome}' não guardou nada para este gatilho. Um efeito seu é o "
                f"par L2+R2, e o lado que estava sem modo na hora de guardar não "
                f"entrou — escolha-o no outro gatilho, ou guarde de novo com os "
                f"dois ajustados.")
        modo_salvo = str(meia.get("mode") or "Off")
        params = [int(v) for v in (meia.get("params") or [])]
        ok, motivo, recibo = _aplicar(p, lado, modo_salvo, params, uniq, ctx)
        if not ok:
            raise RuntimeError(_na_lingua_da_tela(motivo, modo_salvo)
                               or f"o daemon não aplicou o seu efeito {nome!r}")
        return {"recado": recibo}
    if chave in ("", "custom", TRAVESSAO):
        raise ValueError(
            "efeito pronto: não há curva a aplicar. '— Nenhum —' é a ausência "
            "de escolha, e `—` é como esta tela diz que o lugar está vazio. "
            "Para guardar um efeito seu, dê um nome a ele e use "
            "'Guardar esse efeito'.")
    # O MODO É O DA TABELA EM QUE A CURVA MORA — 03/09/2026. Era `MODO_DA_CURVA`
    # cravado, e por isso as cinco curvas de VIBRAÇÃO do produto não podiam ser
    # aplicadas: mandá-las como `MultiPositionFeedback` poria uma curva de
    # vibração num modo de força — o número certo no efeito errado.
    curva, modo_da_curva = _curva(chave)
    ok, motivo, recibo = _aplicar(p, lado, modo_da_curva,
                                  _params_da_curva(modo_da_curva, curva), uniq, ctx)
    if not ok:
        # O SPEC DA TRADUÇÃO É O DO MODO POR POSIÇÃO, e não o do preset: quem
        # recusa é ele, e é dele que saem os rótulos `Posição 0..9` que a recusa
        # vai nomear.
        raise RuntimeError(_na_lingua_da_tela(motivo, modo_da_curva)
                           or f"o daemon não aplicou a curva {chave!r}")
    return {"recado": recibo}


@gesto("03-gatilhos.html", "ajuste")
def ajuste(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Arrastar uma barra muda AQUELE parâmetro e reaplica o efeito na hora.

    A MAIOR DÍVIDA DESTA ABA, e o nome dela já estava reservado: o `SEM_ECO`
    listava um gesto `ajuste` que não existia. São **73 parâmetros em 17 dos 19
    modos** que a GTK deixa mexer e o HTML só mostrava — Rigid 2, Machine 6,
    MultiPositionFeedback 10, MultiPositionVibration 11. Sem eles, escolher um
    modo aplicava os PADRÕES dele e não havia como sair de lá; e "Montar do
    zero" (`Custom`), cujos oito padrões são ZERO, era um modo que não faz nada
    — um item de menu que responde "aplicado" com o gatilho intacto.

    NADA DE LÓGICA NOVA. A ordem dos parâmetros é a do produto
    (`preset_to_positional_params`, ver `_padroes`), quem lê a coluna é o
    `_ajustes_da_coluna` que o "Guardar esse efeito" já usava, e quem manda ao
    daemon é o `_aplicar`. Este gesto só troca UM número no meio da lista.

    O MODO VEM DA COLUNA, e não do servidor: é a mesma `forma` que o Guardar
    recolhe (`data-hef-forma`), e ela traz o `modo-chave-<lado>` que está na
    tela. Perguntar ao perfil daria o modo do DISCO, e o rascunho existe
    justamente porque os dois podem divergir.

    O `click` NÃO REPETE O `change`, e a guarda é a IGUALDADE, não o nome do
    evento. Uma alavanca dispara os dois no mesmo gesto — `change` ao soltar,
    `click` logo depois, com o mesmo valor —, e sem guarda cada arrasto viraria
    dois pedidos idênticos ao daemon. É o que o debounce de 300 ms da GTK
    (`_schedule_live_preview`) resolve do outro lado; aqui não há arrasto
    contínuo a conter, só a repetição do próprio evento.

    POR QUE PELA IGUALDADE E NÃO POR `evento == "click"`, e a diferença foi
    medida: o clique sintético desta casa (`--prova-clique`, `CLIQUE_COM_ALVO`)
    chama `el.click()` — se o gesto recusasse todo `click`, a régua da tela
    nunca alcançaria a alavanca e daria verde sobre um controle que ela nunca
    tocou. É o defeito do `--prova-gesto` que dava verde sobre dois botões
    mortos, com o sinal trocado. Comparar com o RASCUNHO cala a repetição sem
    calar a prova: o primeiro pedido passa, o segundo é o mesmo pedido.
    """
    uniq, lado = _exigir_controle(o, "ajuste"), _lado(o)
    sigla = str(o.get("lado") or "").strip()
    forma = o.get("forma")
    if not isinstance(forma, dict) or not forma:
        raise RuntimeError(
            "não consegui ler a coluna deste controle. A barra precisa do "
            "`data-hef-forma` para o piloto recolher os campos — sem ele não sei "
            "em que modo o gatilho está, e o daemon lê a lista de ajustes "
            "INTEIRA: mandar um número solto trocaria os outros pelos padrões.")
    modo_ = str(forma.get(f"modo-chave-{sigla}") or "").strip()
    if not modo_ or modo_ == TRAVESSAO:
        raise RuntimeError(
            "este gatilho não tem modo escolhido, e um ajuste é de um modo — é "
            "ele que diz quantos parâmetros existem e o que cada um significa. "
            "Escolha um modo primeiro.")
    params = _ajustes_da_coluna(forma, sigla, modo_)
    try:
        i = int(str(o.get("i") or "").strip())
    except ValueError:
        raise ValueError(
            "ajuste: o clique não disse QUAL barra. É o `data-i` da alavanca, "
            "e ele é o índice do parâmetro na ordem do spec.") from None
    if not 0 <= i < len(params):
        raise ValueError(
            f"ajuste: a barra {i} não existe no modo {modo_!r}, que tem "
            f"{len(params)} ajuste(s). O índice é posicional — se a caixa e o "
            f"modo saíram de sincronia, aplicar aqui escreveria no parâmetro "
            f"errado.")
    try:
        params[i] = int(float(str(o.get("valor") or "").strip()))
    except ValueError:
        raise ValueError(
            f"ajuste: a barra devolveu {o.get('valor')!r}, que não é número. "
            f"Zero é uma medida; o que a tela não soube dizer não vira zero.") from None
    ja = _do_rascunho(uniq, lado)
    if ja and ja.get("mode") == modo_ and list(ja.get("params") or []) == params:
        return None
    ok, motivo, recibo = _aplicar(p, lado, modo_, params, uniq, ctx)
    if not ok:
        raise RuntimeError(_na_lingua_da_tela(motivo, modo_)
                           or f"o daemon não aplicou o ajuste no modo {modo_!r}")
    return {"recado": recibo}


#: O SEPARADOR DAS DUAS METADES DO RECIBO DO REENVIO. Ele é uma constante
#: porque é `PONTO` sem a marcação — o recado do cartão é texto, não HTML
#: (`hefesto_vivo.pintar_recados` escreve `textContent`), e um `<span>` ali
#: apareceria escrito na tela dela.
_E_TAMBEM = " · "


@gesto("03-gatilhos.html", "reenviar")
def reenviar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Manda de novo ao controle os DOIS gatilhos que estão NA TELA desta coluna.

    DECISÃO [03] do PO, 04/09/2026: *"Um botão na faixa que JÁ EXISTE
    (`--r-acao`, 34 px, já desenhada e aprovada), mandando os DOIS gatilhos
    daquela coluna. Zero trilha nova."*

    **O QUE ELE PAGA, e a dívida é medida** (linha `Aplicar o efeito no
    aparelho`): a GTK tem *"Aplicar em L2"* e *"Aplicar em R2"*, dois botões que
    reenviam o que está na tela sem mexer em nada; a interface nova não tinha
    nenhum. E o "Aplicar" do rodapé **não é substituto** — ele manda o rascunho
    montado a partir do PERFIL NO DISCO, não o que ela acabou de escolher.

    **POR QUE ISSO NÃO É LUXO, e é a natureza do aparelho:** o DualSense não
    devolve o modo em que está. Gatilho adaptativo é comando de IDA, e o
    `state_full` não publica `triggers` — está escrito no topo deste arquivo e
    o `docs/data/mapa-controles.csv` diz o mesmo pela outra ponta. Quando o
    efeito se perde (o jogo escreveu por cima pelo hidraw, o controle voltou do
    rádio, o daemon reaplicou um perfil), **não há como a tela saber**: o único
    caminho de volta é reenviar.

    **A FONTE É A TELA, e não o disco** — é a diferença inteira em relação ao
    rodapé. O piloto recolhe a coluna pelo `data-hef-forma="@controle"`, do
    mesmo jeito que o "Guardar esse efeito" já recolhe, e por isso este gesto
    reusa o `_ajustes_da_coluna` em vez de escrever uma segunda leitura.

    **ELE NÃO GRAVA NADA NO DISCO DELA**, e é o que o distingue do vizinho: o
    `guardar` escreve em `meu_perfil.json` (e por isso está em
    `hefesto_vivo.PERIGOSOS`); este só reenvia ao APARELHO valores que já estão
    na tela. Reenviar o que já está lá é idempotente — nenhum valor novo, nenhum
    byte a mais do que o `modo` e o `pronto` já mandam a cada clique dela.

    **UM LADO QUE RECUSA NÃO CALA O OUTRO.** Os dois gatilhos são independentes,
    e parar no primeiro deixaria a coluna pela metade sem dizer. Aqui os dois
    vão, e o desfecho de cada um entra na frase: se algum recusou, a frase
    inteira sai como recusa (que é o canal que pousa no cartão em laranja); se
    os dois foram, sai como recibo verde. **Um recibo que some a recusa de um
    lado com o sucesso do outro seria a tela afirmando o que não é.**
    """
    uniq = _exigir_controle(o, "reenviar")
    forma = o.get("forma")
    if not isinstance(forma, dict) or not forma:
        raise RuntimeError(
            "não consegui ler a coluna deste controle. O botão precisa do "
            "`data-hef-forma` para o piloto recolher os campos — e sem eles não "
            "há o que reenviar, porque o daemon não devolve o modo do gatilho.")

    recibos: list[str] = []
    recusas: list[str] = []
    for sigla, disco in LADOS.items():
        modo_ = str(forma.get(f"modo-chave-{sigla}") or "").strip()
        if not modo_ or modo_ == TRAVESSAO:
            continue
        params = _ajustes_da_coluna(forma, sigla, modo_)
        try:
            ok, motivo, recibo = _aplicar(p, disco, modo_, params, uniq, ctx)
        except RuntimeError as erro:
            # O `_conferir_o_desfecho` LEVANTA quando o byte não saiu, e a
            # frase dele já nomeia o lado. Deixá-la subir aqui mataria o outro
            # gatilho antes de ele ser tentado.
            recusas.append(str(erro))
            continue
        if ok:
            recibos.append(recibo)
        else:
            # O ASSUNTO VAI NA FRENTE, e aqui ele NÃO é opcional — medido na
            # mordida desta frente. `_na_lingua_da_tela` devolve a recusa
            # traduzida do daemon (*"Fim (3) precisa ser maior que Início (5)"*)
            # e ela não nomeia gatilho nenhum: num clique que manda os DOIS, a
            # frase sozinha deixa ela sem saber qual dos dois recusou.
            recusas.append(
                f"{_assunto(disco, modo_)} — "
                f"{_na_lingua_da_tela(motivo, modo_) or 'o daemon não aplicou'}")
    if not recibos and not recusas:
        raise RuntimeError(
            "esta coluna não tem gatilho nenhum para reenviar. Escolha um modo "
            "em L2 ou em R2 — `—` é como esta tela diz que o lugar está vazio.")
    if recusas:
        raise RuntimeError(_E_TAMBEM.join(recusas + recibos))
    return {"recado": _E_TAMBEM.join(recibos)}


@gesto("03-gatilhos.html", "guardar")
def guardar(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Guardar esse efeito": a coluna vai para o PERFIL — e, com nome, para ELA.

    POR QUE ELE PRECISA EXISTIR, e é a diferença entre esta aba e as outras: os
    dois gestos vizinhos (`modo` e `pronto`) APLICAM na hora — é a decisão dela
    de 01/09, *"clicar já aplica"*. Mas aplicar não guarda: o efeito vale até a
    próxima troca de perfil, e o disco continua com o que estava lá. Este botão
    é o ponto de gravação, e é a única coisa nesta tela que sobrevive a um
    `profile.switch`.

    DE ONDE VEM O QUE ELE GRAVA — e a resposta não é o daemon. O DualSense **não
    devolve** o modo em que está: gatilho é comando de ida, e o `state_full` não
    o publica (é por isso que `modo` e `pronto` estão no `SEM_ECO` desta aba).
    Logo o único lugar onde a escolha viva existe é a TELA, e é dela que a
    `forma` vem — o piloto recolhe a coluna inteira quando o botão traz
    `data-hef-forma="@controle"`.

    O ALVO É O OVERRIDE DO CONTROLE, e não a seção global: `ControllerOverrides`
    tem `triggers` desde a PERFIL-02, e a aba mostra uma coluna POR CONTROLE.
    Gravar no global faria o "Guardar" do P2 mudar o gatilho do P1 — a mesma
    contradição que mantém o `mic-escopo` da aba Conexões recusando.

    A FUSÃO É POR CAMPO, e o esquema a escreve: *"`None` = sem opinião — o
    controle herda a seção GLOBAL do perfil (merge POR CAMPO na aplicação,
    PERFIL-01: override parcial nunca apaga a cor global no replug)"*. Por isso
    este gesto só toca `triggers` do controle clicado e devolve o resto intacto.

    E O NOME É O QUE FALTAVA — decisão 17 dela, 02/09/2026: *"Isso é pra quando
    o user salva algum efeito. É assim que tem que aparecer. O nome que o user
    deixar lá."* O campo ao lado do botão é opcional; preenchido, o par L2+R2
    entra em "Meus efeitos" com aquele nome e passa a aparecer nas quatro
    colunas. Vazio, este botão continua exatamente o que era.

    A LEGENDA DO DESENHO JÁ DIZIA ISSO, e é de onde veio a forma do dado:
    *"Guarda o par L2+R2 em Meus efeitos"*. A frase morreu num redesenho de
    30/08; o comentário do CSS que a explica sobreviveu em `aba03.py`.
    """
    uniq = _exigir_controle(o, "guardar")
    forma = o.get("forma")
    if not isinstance(forma, dict) or not forma:
        raise RuntimeError(
            "não consegui ler a coluna deste controle. O botão precisa do "
            "`data-hef-forma` para o piloto recolher os campos — sem ele não há "
            "o que guardar, porque o daemon não devolve o modo do gatilho.")

    dos_lados: dict[str, dict[str, Any]] = {}
    for lado, sigla in (("left", "e"), ("right", "d")):
        modo_ = str(forma.get(f"modo-chave-{sigla}") or "").strip()
        if not modo_ or modo_ == TRAVESSAO:
            continue
        dos_lados[lado] = {"mode": modo_,
                           "params": _ajustes_da_coluna(forma, sigla, modo_)}
    if not dos_lados:
        raise RuntimeError(
            "a coluna não trouxe modo nenhum. Os dois `<select>` de modo são "
            "`modo-chave-e` e `modo-chave-d` — se eles mudaram de endereço, o "
            "Guardar deixou de achar o que guardar.")

    # O NOME É OPCIONAL, E É ELE QUE FAZ O EFEITO VIRAR DELA — decisão 17.
    # Vazio, o botão faz o que sempre fez: grava a coluna no perfil deste
    # controle. Com nome, o par L2+R2 entra também na biblioteca — e a
    # biblioteca é a que aparece em "Meus efeitos", nas quatro colunas.
    apelido = str(forma.get("nome-do-efeito") or "").strip()
    if len(apelido) > 60:
        raise ValueError(
            "o nome do efeito passou de 60 letras. O campo de escolha em que "
            "ele aparece tem 220px de coluna — um nome que não cabe some "
            "cortado, e um efeito que ela não consegue ler é um efeito perdido.")
    if apelido:
        _salvar_o_meu(apelido, dos_lados)

    nome = str((ctx.state or {}).get("active_profile") or "").strip()
    if not nome:
        if apelido:
            # SALVOU O EFEITO E NÃO HAVIA PERFIL. Não é erro: a biblioteca dela
            # não depende de jogo nenhum. Levantar aqui diria "não deu" sobre um
            # efeito que ESTÁ no disco — a pior forma de recibo.
            return {"blocos": _blocos_do_pronto(ctx)}
        raise RuntimeError(
            "não há perfil ativo agora, e o efeito do gatilho é do perfil — não "
            "da máquina. Escolha um perfil na aba Perfis, ou dê um nome ao "
            "efeito para guardá-lo em 'Meus efeitos'.")

    loader = perfil._com_o_src()
    prof = loader.load_profile(nome)
    novo = _com_os_gatilhos(prof, uniq, dos_lados)
    if novo is not None:
        _gravar_so_o_gatilho(novo, p)
    # O RECIBO É A LISTA NOVA. O tique seguinte a traria de qualquer jeito, mas
    # meio segundo entre salvar e ver o nome aparecer é meio segundo em que ela
    # não sabe se o botão fez algo.
    return {"blocos": _blocos_do_pronto(ctx)} if apelido else None


def _gravar_so_o_gatilho(novo: Any, p: Any) -> None:
    """Grava o perfil no disco — e NÃO reaplica o perfil inteiro no aparelho.

    ELE NÃO PODE SER O `perfil.gravar_e_reaplicar`, e o motivo foi MEDIDO em
    03/09/2026, clicando este botão no produto instalado com um DualSense no
    cabo. `gravar_e_reaplicar` termina em `p.profile_switch(...)`, que manda o
    daemon aplicar o perfil INTEIRO — barra de luz, LEDs de jogador, tudo. A
    prova, com um gesto só (`--prova-clique guardar`) e a barra apagada antes:

        antes   lightbar_on: false · lightbar_rgb: [0, 0, 0]
        depois  lightbar_on: true  · lightbar_rgb: [0, 0, 255]

    Ou seja: ela desliga a barra na aba Iluminação, vai aos Gatilhos, clica
    "Guardar esse efeito" — e a barra ACENDE de novo, sem nada na tela dizendo
    que isso ia acontecer. É *a tela afirmando o que não é*, na forma mais cara:
    um botão de escopo estreito ("esse efeito") desfazendo escolha viva dela em
    OUTRA aba.

    E A REAPLICAÇÃO NÃO ERA NECESSÁRIA PARA NADA. Esta aba aplica NA HORA — é a
    decisão dela de 01/09, *"clicar já aplica"*: quando ela chega a este botão,
    `modo` e `pronto` já mandaram o efeito ao aparelho por `_aplicar`. O
    `profile_switch` reaplicava por cima um gatilho que já estava lá, e levava
    junto nove seções que ninguém pediu.

    O `launch_env.refresh` FICA, e é a metade que tem de sobreviver: sem ele o
    perfil novo só chega ao jogo no próximo start do daemon. Ele relê o que os
    jogos vão receber e não escreve no aparelho.
    """
    loader = perfil._com_o_src()
    loader.save_profile(novo, origem="interface-nova")
    p.chamar("launch_env.refresh")


def _salvar_o_meu(apelido: str, dos_lados: dict[str, dict[str, Any]]) -> None:
    """Guarda o par L2+R2 na biblioteca dela, com o nome que ela deixou.

    O MODO É CONFERIDO CONTRA O PRODUTO antes de entrar no disco — `_padroes`
    levanta com o nome do arquivo quando o modo não é um dos 19. Um efeito
    salvo com um modo que o `build_from_name` não conhece só falharia no dia em
    que ela o escolhesse, longe da origem; aqui ele falha no clique que o criou.

    O MESMO NOME SOBRESCREVE, e é o que "salvar" quer dizer em toda parte:
    guardar de novo com um nome que já existe atualiza aquele efeito. Um segundo
    "Recuo do MK" na lista seria pior que a sobrescrita — ela não teria como
    dizer qual é qual.
    """
    guardado: dict[str, Any] = {}
    for disco, cfg in dos_lados.items():
        _padroes(str(cfg["mode"]))
        guardado[disco] = {"mode": str(cfg["mode"]),
                           "params": [int(v) for v in cfg["params"]]}
    todos = meus_efeitos()
    todos[apelido] = guardado
    _guardar_meus_efeitos(todos)


def _blocos_do_pronto(ctx: Contexto) -> dict[str, str]:
    """As listas de "Efeito pronto" das quatro colunas, com a biblioteca de agora.

    O MODO DE CADA LADO ENTRA NA CONTA — 03/09/2026: a lista depende dele desde
    que as curvas de vibração passaram a existir na tela. Ler o modo do
    RASCUNHO e, na falta dele, do perfil é a mesma ordem que a pintura usa —
    montar aqui uma lista de feedback por cima de um gatilho que está em
    `MultiPositionVibration` faria o recibo do "Guardar" desfazer a lista certa
    até o tique seguinte.
    """
    fora: dict[str, str] = {}
    for m in ctx.mesa:
        pref = str(m.get("pref") or "")
        if not pref:
            continue
        uniq = str(m.get("uniq") or "")
        for sig, disco in LADOS.items():
            fora[f'[data-controle="{pref}"] select.pronto[data-lado="{sig}"]'] = (
                html_das_opcoes_de_pronto(_modo_de_agora(ctx, uniq, disco)))
    return fora


def _modo_de_agora(ctx: Contexto, uniq: str, disco: str) -> str:
    """O modo em que aquele gatilho está, na MESMA ordem que a tela pinta.

    Rascunho (o que esta sessão aplicou) → override do controle → seção global
    do perfil → `Off`. Uma quinta cópia dessa ordem seria a quinta chance de ela
    divergir da pintura; esta é a única que os gestos consultam.
    """
    seu = _do_rascunho(uniq, disco)
    if seu:
        return str(seu.get("mode") or "Off")
    p = perfil.ativo(ctx.state.get("active_profile")) or {}
    meu = (p.get("controllers") or {}).get(uniq) or {}
    seus = (meu.get("triggers") or {}) if isinstance(meu, dict) else {}
    cfg = seus.get(disco) or (p.get("triggers") or {}).get(disco) or {}
    return str(cfg.get("mode") or "Off")


def _ajustes_da_coluna(forma: dict[str, Any], sigla: str, modo: str) -> list[int]:
    """Os ajustes daquele lado, na ORDEM do spec — nunca na ordem da tela.

    A ordem é a que o daemon lê, e ela tem dono: `preset_to_positional_params`
    (ver `_padroes`). A tela desenha uma barra por parâmetro, na mesma ordem,
    endereçadas `aj-val-<lado>-<i>` — então o índice da barra É o índice do
    parâmetro. Ler por índice, e não por NOME, é o que faz isto sobreviver a uma
    tradução de rótulo.

    O QUE NÃO VEIO NA TELA CAI NO PADRÃO DO MODO. Um modo de quatro parâmetros
    desenhado numa coluna que só mostra dois não pode gravar dois — o daemon lê
    a lista posicional inteira, e uma curta muda o que ela não escolheu.
    """
    padrao = _padroes(modo)
    fora = list(padrao)
    for i in range(len(padrao)):
        cru = str(forma.get(f"aj-val-{sigla}-{i}") or "").strip()
        if not cru:
            continue
        try:
            fora[i] = int(float(cru))
        except ValueError:
            # UM VALOR QUE NÃO É NÚMERO NÃO VIRA ZERO. Zero é uma medida; o que
            # a tela não soube dizer tem de cair no padrão do modo, que é o que
            # o daemon aplicaria de qualquer jeito.
            continue
    return fora


def _com_os_gatilhos(prof: Any, uniq: str, dos_lados: dict[str, Any]) -> Any:
    """O perfil com o gatilho DESTE controle trocado, ou `None` se nada mudou.

    `None` evita o barulho: regravar um perfil idêntico troca a data do arquivo
    e faz o daemon reaplicar — e um `profile.switch` no meio de uma partida não
    é de graça.

    A CHAVE DO OVERRIDE É O `uniq` NORMALIZADO, e é o que o esquema espera
    (`_validate_controllers_keys`). Escrever `d4:2f:…` onde o disco guarda
    `d42f…` criaria um segundo dono para o mesmo controle.
    """
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        TriggerConfig,
        TriggersConfig,
    )

    chave = uniq.replace(":", "").lower()
    atuais = dict(prof.controllers or {})
    dele = atuais.get(chave) or ControllerOverrides()
    antes = dele.triggers
    novos = TriggersConfig(
        left=TriggerConfig(**dos_lados["left"]) if "left" in dos_lados
        else (antes.left if antes else TriggerConfig(mode="Off")),
        right=TriggerConfig(**dos_lados["right"]) if "right" in dos_lados
        else (antes.right if antes else TriggerConfig(mode="Off")),
    )
    if antes is not None and antes == novos:
        return None
    atuais[chave] = dele.model_copy(update={"triggers": novos})
    return prof.model_copy(update={"controllers": atuais})


#: AS FUNÇÕES DA PONTE QUE ESTA ABA USA. A régua confere que existem — um nome
#: inventado aparece aqui, e não na mão de quem clica.
PONTE = {"trigger_set_detalhado", "trigger_reset_detalhado"}
#: Vazio: os dois métodos que esta aba usa (`trigger.set` e `trigger.reset`) têm
#: função no `ipc_bridge`, então nenhum passa pelo degrau cru `p.chamar`.
METODOS: set[str] = set()


#: O PISO E AS PROVAS MORAM AQUI, e não no teste — território exclusivo.
#: O `PAGINA` é declarado lá em cima, junto de quem lê a página publicada.
#: 3 → 4 EM 03/09/2026: o `ajuste` nasceu, e com ele os 73 parâmetros dos 17
#: modos que a GTK deixa mexer. O piso SÓ SOBE, e uma queda não aparece na tela
#: — o clique simplesmente deixa de fazer alguma coisa.
#: 4 → 5 EM 04/09/2026: nasceu o `reenviar`, a decisão [03] do PO — o botão que
#: a GTK tem por lado ("Aplicar em L2"/"Aplicar em R2") e a interface nova não
#: tinha por nenhum.
PISO_DA_ABA = 5
#: O `uniq` da prova é a faixa sintética da casa: há dois portões de anonimato
#: nesta árvore e eles não perdoam.
_UNIQ = "aa:bb:cc:00:00:01"
#: A CURVA E O MODO DELA, resolvidos uma vez para as provas abaixo lerem os dois
#: sem repetir a chamada. `stop_hard` é de feedback; `galope`, de vibração.
_STOP_HARD, _MODO_STOP_HARD = _curva("stop_hard")
_GALOPE, _MODO_GALOPE = _curva("galope")


def _forma_de_prova(sigla: str, modo_: str) -> dict[str, str]:
    """A coluna que o piloto recolheria, montada pelo endereço que a pintura usa.

    Escrever `{"modo-chave-e": "Rigid"}` à mão aqui digitaria duas coisas que
    já têm dono — o endereço, que sai do `pacote()`, e o contrato de disco do
    modo, que sai do `trigger_specs` — e ainda faria o portão dos dois mundos
    (`test_o_pacote_cabe_na_pagina_publicada`) ler um `value` como se fosse
    rótulo de tela: ele compara texto de `<option>`, e `Rigid` é o `value` da
    opção cujo texto é `Rígido`.
    """
    return {f"modo-chave-{sigla}": modo_}
PROVAS = [
    # Um modo comum: os ajustes saem do produto, e é por isso que a prova os
    # BUSCA em vez de digitar `[5, 200]`. Digitados, eles ficariam errados
    # calados no dia em que ela mudasse um padrão — e a régua daria verde sobre
    # um gatilho aplicado com a força de ontem.
    {"pagina": PAGINA, "gesto": "modo", "clique": {"lado": "e",  # (noqa-acento) id
     "modo": "Rigid"},
     "chama": [("trigger_set_detalhado", ["left", "Rigid", _padroes("Rigid")],
                {"uniq": _UNIQ})]},
    # "Desligado" é `trigger.reset` — a R-19. Se alguém trocar por um
    # `trigger.set` com `Off`, esta linha reprova: o nome da função muda.
    {"pagina": PAGINA, "gesto": "modo", "clique": {"lado": "d", "modo": "Off"},  # (noqa-acento) id
     "chama": [("trigger_reset_detalhado", ["right"], {"uniq": _UNIQ})]},
    # A MESMA ESCOLHA PELA OUTRA CHAVE: `valor` é o que um `<select>` manda no
    # `change`. As duas portas do `_escolhido` têm de levar ao mesmo lugar.
    {"pagina": PAGINA,  # (noqa-acento) chave do contrato
     "gesto": "modo", "clique": {"lado": "e", "valor": "Vibration"},
     "chama": [("trigger_set_detalhado", ["left", "Vibration", _padroes("Vibration")],
                {"uniq": _UNIQ})]},
    # O efeito pronto: a curva sai de `profiles/trigger_presets.py`, e o modo é
    # o da TABELA em que ela mora — aqui, o de força.
    {"pagina": PAGINA,  # (noqa-acento) chave do contrato
     "gesto": "pronto", "clique": {"lado": "d", "v": "stop_hard"},
     "chama": [("trigger_set_detalhado",
                ["right", _MODO_STOP_HARD,
                 _params_da_curva(_MODO_STOP_HARD, _STOP_HARD)],
                {"uniq": _UNIQ})]},
    # E A CURVA DE VIBRAÇÃO, que até 03/09/2026 não tinha como ser aplicada por
    # esta tela. Ela prova as DUAS metades da cura: o modo tem de ser
    # `MultiPositionVibration` (e não o de força, que era o cravado) e as dez
    # posições têm de cair nos `pos_*`, com a frequência no padrão do modo — se
    # alguém alinhar por índice, o primeiro número vai para a frequência e esta
    # linha reprova.
    {"pagina": PAGINA,  # (noqa-acento) chave do contrato
     "gesto": "pronto", "clique": {"lado": "e", "v": "galope"},
     "chama": [("trigger_set_detalhado",
                ["left", _MODO_GALOPE, _params_da_curva(_MODO_GALOPE, _GALOPE)],
                {"uniq": _UNIQ})]},
    # O AJUSTE: uma barra arrastada troca UM parâmetro e reaplica o modo com a
    # lista inteira. A prova manda `Rigid` com a força em 200 e espera os
    # padrões do modo com o índice 1 trocado — se alguém passar a mandar só o
    # número mexido, os outros viram padrão calados e esta linha reprova.
    {"pagina": PAGINA,  # (noqa-acento) chave do contrato
     "gesto": "ajuste", "clique": {"lado": "e", "i": "1", "valor": "200",
                                   "forma": _forma_de_prova("e", "Rigid")},
     "chama": [("trigger_set_detalhado",
                ["left", "Rigid", [_padroes("Rigid")[0], 200]], {"uniq": _UNIQ})]},
    # O REENVIO: UM clique, DOIS envios, na ordem L2 → R2. A prova mistura os
    # dois modos de propósito — `Rigid` de um lado e `Desligado` do outro —
    # porque as PORTAS são diferentes e a R-19 mora nessa diferença: `Off` é
    # `trigger.reset` (que LIMPA a trava manual) e nunca `trigger.set` com
    # `Off` (que a ARMA). Se alguém fizer o reenvio mandar tudo pela mesma
    # porta, esta linha reprova pelo NOME da função.
    {"pagina": PAGINA,  # (noqa-acento) chave do contrato
     "gesto": "reenviar",
     "clique": {"forma": {**_forma_de_prova("e", "Rigid"),
                          **_forma_de_prova("d", "Off")}},
     "chama": [("trigger_set_detalhado", ["left", "Rigid", _padroes("Rigid")],
                {"uniq": _UNIQ}),
               ("trigger_reset_detalhado", ["right"], {"uniq": _UNIQ})]},
]

#: OS GESTOS QUE O DAEMON ACEITA E NÃO PUBLICA. O `state_full` não traz
#: `triggers`: o DualSense não devolve o modo em que está — gatilho adaptativo é
#: comando de IDA, e o `docs/data/mapa-controles.csv` diz o mesmo pela outra
#: ponta. A prova destes é a porta `_detalhado`, que levanta quando o daemon
#: recusa; chegar a "aplicado" já é ele ter aceitado.
SEM_ECO = ("modo", "pronto", "ajuste")
