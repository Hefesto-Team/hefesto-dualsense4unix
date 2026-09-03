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

from . import Contexto, perfil, registrar

#: Nada. E a lista vazia é uma AFIRMAÇÃO, não um esquecimento: cada valor desta
#: aba tem dono medido, e a régua de cobertura conta este zero junto com os
#: `pintados` — um pacote que pinta 0 e declara 0 é reprovado por
#: `test_o_despachante_serve_as_dez.py`, de propósito.
SEM_DONO: dict[str, str] = {}

#: O LADO NA TELA E O LADO NO DISCO. A tela usa `e`/`d` (o L2 e o R2 do
#: desenho); o perfil usa `left`/`right`. Dois vocabulários, uma tradução, num
#: lugar só — a regra da casa é que o que tem dono não se digita.
LADOS = {"e": "left", "d": "right"}

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
    "—")` (`hefesto_vivo.py:1006-1016`), e `escrever()` **recusa** escrever um
    valor que o `<select>` não oferece (`hefesto_vivo.py:145-151`) — a recusa é
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


#: O MODO QUE UMA CURVA PRONTA É. Uma curva de dez posições só existe como
#: `MultiPositionFeedback` — é o único modo cujos ajustes são `pos_0..pos_9`
#: (`app/actions/trigger_specs.py`), e é o que a GUI estável exige para sequer
#: MOSTRAR a linha de preset (`triggers_actions._update_preset_row_visibility`,
#: que a esconde nos outros 17 modos).
MODO_DA_CURVA = "MultiPositionFeedback"


def _pronto_da_curva(nome: str, curva: list[int]) -> str:
    """Qual efeito pronto é aquela curva salva, ou `custom` se não for nenhum.

    O DISCO NÃO GUARDA QUAL PRESET FOI ESCOLHIDO — guarda as dez intensidades.
    Então a chave se RECONHECE, comparando com a tabela do produto; ela não se
    adivinha e não se digita. Sem isto a tela mostraria "— Nenhum —" para uma
    curva que é exatamente a "Stop hard" que ela escolheu.

    `custom` é o token do próprio produto para "nenhuma pronta"
    (`FEEDBACK_POSITION_LABELS["custom"]`), e é o `value` que a opção
    "— Nenhum —" carrega no desenho — a tela e o disco falam a mesma palavra.
    """
    tp = _prontos()
    if tp is None or nome != MODO_DA_CURVA or len(curva) != 10:
        return "custom"
    for chave, valores in tp.FEEDBACK_POSITION_PRESETS.items():
        if list(valores) == list(curva):
            return str(chave)
    return "custom"


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
                     cabem: int | None = None) -> str:
    """A caixa de ajustes daquele lado, em HTML — a lista do MODO.

    Uma linha por parâmetro do modo, com o rótulo, a barra na porcentagem da
    FAIXA daquele parâmetro e o número. Zero parâmetros devolvem a frase, que é
    o que as colunas vazias do desenho já diziam.

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
    linhas = [_html_de_uma_barra(sigla, i, a, escondida=i >= a_vista)
              for i, a in enumerate(ajustes)]
    return "\n".join(linhas)


def _html_de_uma_barra(sigla: str, i: int, a: dict[str, Any],
                       escondida: bool = False) -> str:
    """Uma linha da caixa de ajustes. `escondida` guarda o valor sem mostrá-lo."""
    #: INLINE, e não a classe: `.barra{display:flex}` é regra de autor e ganha do
    #: `[hidden]{display:none}` da folha do navegador. O atributo sozinho não
    #: esconderia nada.
    oculta = ' style="display:none"' if escondida else ""
    return (
        f'            <div class="barra" data-ajuste="{sigla}-{i}"{oculta}>\n'
        f'              <span class="nome" data-campo="aj-nome-{sigla}-{i}">'
        f'{_escapar(str(a["nome"]))}</span>\n'
        f'              <span class="trilho"><span class="cheio" '
        f'data-campo="aj-pct-{sigla}-{i}" data-hef-alvo="largura" '
        f'style="width:{a["pct"]}%"></span></span>\n'
        f'              <span class="num" data-campo="aj-val-{sigla}-{i}">'
        f'{_escapar(str(a["valor"]))}</span>\n'
        f'            </div>')


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


def html_das_opcoes_de_pronto() -> str:
    """As opções do campo "Efeito pronto": o desenho + os efeitos DELA.

    É AQUI QUE OS "MEUS EFEITOS" DEIXAM DE SER EXEMPLO. O desenho traz dois
    nomes de exemplo debaixo do separador; o produto traz os que ela salvou —
    e, quando ela não salvou nenhum, **não traz separador nenhum**. É o
    princípio geral dela de hoje: *"se não tá mostrando agora, não tem info pra
    mostrar no produto"*. Um separador com nada embaixo é uma promessa vazia.
    """
    fora = _opcoes_cravadas_do_pronto()
    meus = meus_efeitos()
    if not meus:
        return fora
    linhas = [fora, '                <option disabled>──── Meus efeitos ────</option>']
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
# A FITA NEM SEMPRE LÊ, e isso é fato medido em 03/09/2026, não ressalva:
# `hefesto_vivo._fita` devolve `""` — deixando a fita INTEIRA no desenho —
# quando QUALQUER controle da mesa está sem cor lida (`hefesto_vivo.py:598`).
# Com um controle no rádio, que é a mesa dela agora, a fita fica no mockup. Esta
# aba não depende disso: ela lê a MESA, controle a controle, e cala sobre quem
# não disse a cor em vez de calar sobre todos.
#
# UM DONO, DOIS CHAMADORES — é a forma que a `fileira_de_players` da aba
# Iluminação já usa. `aba03.py` chama estas funções para desenhar a bancada e o
# `pacote()` as chama a cada tique para pintar o produto. Enquanto eram duas
# escritas, o desenho e o produto podiam divergir sem ninguém ver.
# ---------------------------------------------------------------------------

#: A CLASSE DO EMBRULHO DO CHIP. Ela é o alvo do `blocos` (um seletor CSS) para
#: as colunas SEM aparelho, e o lugar do `data-campo` para as que têm.
CLASSE_DO_CHIP = "cabeca"

#: O ENDEREÇO DO CHIP — e ele mora no EMBRULHO, não no `<span>`.
#:
#: POR QUE O EMBRULHO E NÃO O CHIP: o piloto **não sabe reescrever o estilo de
#: um elemento**. Os alvos são texto·largura·fundo·valor·html·classe·cor, e
#: nenhum deles escreve uma propriedade CSS de autor — e a cor do plástico é
#: `--plastico` no `style` do próprio `<span>`. Trocando o MIOLO do embrulho, o
#: `<span>` inteiro é refeito: borda, dica e texto de uma vez.
#:
#: E POR QUE ELE NÃO PODE MORAR NO `<span>`, que era onde ele estava até a
#: medição de 03/09/2026 desfazer a escolha: `escrever()` carimba
#: `data-hef-visto="1"` no elemento que visita, e um selo posto DENTRO do HTML
#: comparado faz a comparação nunca mais bater. Medido com o piloto e os dois
#: controles dela, 17 tiques:
#:
#:     selo dentro do miolo comparado ... 17 tiques pintaram
#:     selo no embrulho (agora) .........  2 tiques pintaram
#:
#: Repintar o mesmo HTML a cada tique não muda um pixel, mas **infla o contador
#: de pinturas** — que é O instrumento com que esta casa prova que um endereço
#: existe. `hefesto_vivo.escrever` diz a mesma frase sobre o `<select>` que
#: recusa um valor: *um contador que mente é pior que um campo parado*.
CAMPO_DO_CHIP = "chip-do-controle"

#: O ENDEREÇO NO PRÓPRIO `<span>`, e ele existe por UMA razão: a régua
#: `check_identidade_vem_de_cima.py` julga o `--plastico` pelo endereço do
#: ELEMENTO QUE O CARREGA — um pai endereçado não dá ao filho o direito de
#: trazer cor congelada, e está certa nisso. Sem ele, os chips com cor
#: continuariam acusados com o produto já os reescrevendo.
#:
#: ELE É `data-hef`, E O NOME NÃO CASA COM CHAVE NENHUMA, de propósito. O
#: `achar()` do piloto varre os três vocabulários pela MESMA chave: dar ao
#: `<span>` o nome do embrulho faria a pintura escrever um chip DENTRO do chip.
#: Quem reescreve este elemento é o pai, pelo alvo `html` — o `<span>` é
#: refeito inteiro a cada tique, e por isso não precisa (nem pode) receber
#: escrita própria.
#:
#: **O ENDEREÇO ACOMPANHA A COR — 03/09/2026, e a razão é medida.** Ele sai
#: onde não há `--plastico` no `style`, e o motivo é que ali ele é LASTRO: não
#: há cor congelada para o produto reescrever, e a régua da identidade não olha
#: um elemento que não carrega cor (ela julga o `style` do PRÓPRIO elemento; o
#: texto e a dica já ficam cobertos pelo embrulho endereçado).
#:
#: O QUE O LASTRO CUSTAVA, e é a dívida desta frente: um `<span>` DENTRO de um
#: pai que se troca inteiro **nunca pode receber o selo da visita** — carimbá-lo
#: poria `data-hef-visto="1"` dentro do `innerHTML` que o pai compara, e a
#: coluna repintaria a cada tique, para sempre (é o mesmo defeito que o
#: `CAMPO_DO_CHIP` acima já mediu: 17 tiques, 17 pinturas). Sem selo, um campo
#: só é PRODUTO quando o seu valor MUDA — e o do lugar vazio nunca muda:
#: `P3 • Desconectado` é o mesmo no desenho e no produto, por construção. O
#: desfecho eram DOIS campos eternamente contados como mockup, sem que houvesse
#: o que consertar. Endereço que ninguém pode pintar não é cobertura: é dívida
#: que não se paga.
HEF_DO_CHIP = "chip.plastico"

#: O separador dos pedaços do rótulo. É o mesmo `monta.SEPARADOR`, e está aqui
#: como literal pela razão que o `NOME_SEM_LEITURA` do `pacotes/__init__` já
#: documenta: importar `monta` num pacote puxa a árvore inteira do desenho só
#: para ler uma string. A régua nova confere que as duas são a MESMA.
PONTO = ' <span class="pt">•</span> '


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


def chip_do_controle(jogador: int, nome: str, via: str, plastico: str,
                     conectado: bool = True) -> str:
    """O `<span>` do cabeçalho da coluna, com endereço e sem cor inventada.

    `plastico` é o HEX JÁ RESOLVIDO, e não o *slug*, de propósito: o gerador
    resolve por `monta.cor_da_zona`, que **levanta** num colorway que o desenho
    não tem (é portão, e está certo em levantar); o pacote resolve por
    `_cor_do_plastico`, que devolve `""` — derrubar a pintura da aba por causa
    de um modelo novo seria trocar uma borda que falta por uma tela congelada.
    A política de resolução é de quem chama; a MARCAÇÃO é daqui, e é ela que não
    pode divergir.

    SEM HEX, SEM `style`. A borda não some: `topo.html` declara
    `.chip.plastico{border-color:var(--plastico, var(--border-forte))}`, com a
    queda já escrita. Cravar um hex de mockup aqui seria dizer que se sabe a cor
    do plástico de um controle que ainda não a disse.

    E SEM HEX, SEM ENDEREÇO NO `<span>` — ver :data:`HEF_DO_CHIP`. Os dois
    andam juntos porque o endereço existe para defender a cor: onde não há cor
    congelada não há o que defender, e o endereço vira lastro que a régua do
    mockup cobra sem que ninguém possa pagar.
    """
    classe = "chip plastico" if conectado else "chip vazio"
    if not conectado:
        dica = "Nenhum controle neste lugar."
    elif nome:
        dica = f"{nome} — a borda é a cor do plástico"
    else:
        dica = "A borda é a cor do plástico deste controle."
    estilo = f' style="--plastico:{plastico}"' if conectado and plastico else ""
    endereco = f' data-hef="{HEF_DO_CHIP}"' if estilo else ""
    return (f'<span class="{classe}"{endereco}{estilo}'
            f' title="{dica}">'
            f"{miolo_do_chip(jogador, nome, via, conectado)}</span>")


def _cor_do_plastico(slug: str) -> str:
    """O hex da casca daquele modelo, ou `""` quando ninguém sabe ainda.

    `monta.cor_da_zona` é o dono — ele LÊ a folha que pinta o desenho, em vez de
    digitar hex. O `""` não é desistência: a cor chega pelo broker, uma vez por
    endereço e em thread, então o primeiro tique de uma sessão sempre tem a mesa
    sem cor. **E pelo rádio ela pode não chegar nunca**, hoje: sem hex o chip
    sai com a borda neutra em vez de vestir o plástico de outro controle.
    """
    if not slug:
        return ""
    try:
        import monta  # o `pacotes/__init__` põe `interface/` no `sys.path`

        return str(monta.cor_da_zona(slug))
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
    """
    return f'[data-controle="{pref}"] .{CLASSE_DO_CHIP}'


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


def _chip_vivo(ctx: Contexto, c: dict[str, Any]) -> str:
    """O `<span>` inteiro de um controle que está na mesa AGORA."""
    return chip_do_controle(*_identidade_viva(ctx, c))


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
    opcoes = html_das_opcoes_de_pronto()

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
        meu = overrides.get(uniq) or {}
        seus = (meu.get("triggers") or {}) if isinstance(meu, dict) else {}
        deste = {sig: (_do_lado(seus[disco], specs) if seus.get(disco) else lados[sig])
                 for sig, disco in LADOS.items()}
        cfgs = {sig: (seus.get(disco) or trig.get(disco) or {})
                for sig, disco in LADOS.items()}

        col: dict[str, object] = {
            # O CABEÇALHO DA COLUNA, e ele é IDENTIDADE — vem da mesa, que é a
            # MESMA lista que a fita do topo desenha. Ver `chip_do_controle`.
            #
            # O CHIP INTEIRO, e não só o texto: borda, dica e nome saem juntos
            # pelo alvo `html` do embrulho. E ele sai por CAMPO — não por bloco
            # — porque só o campo carimba o selo `data-hef-visto`: sem o selo,
            # um controle que por acaso SEJA o Cosmic Red do desenho ficaria
            # classificado como mockup para sempre pela régua do mockup.
            CAMPO_DO_CHIP: _chip_vivo(ctx, c),
            "l2-raw": l2, "r2-raw": r2,
            "l2-pct": round((l2 or 0) / 255 * 100),
            "r2-pct": round((r2 or 0) / 255 * 100),
        }
        for sig, d in deste.items():
            col[f"modo-{sig}"] = d["modo"]
            col[f"modo-chave-{sig}"] = d["modo-chave"]
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
        blocos.update(_blocos_da_coluna(pref_de.get(uniq) or uniq, deste, opcoes))

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
            pref, dict.fromkeys(LADOS, sem_ninguem), opcoes))
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
                      opcoes: str) -> dict[str, str]:
    """Os quatro blocos de uma coluna: as duas caixas de ajuste e as duas listas.

    O SELETOR É CSS, e ele tem de achar UM elemento só: o piloto usa
    `document.querySelector` (o primeiro que casar). `[data-controle="p1"]
    .ajustes.e` é único na página; `.ajustes.e` sozinho acharia o do P1 e
    escreveria a caixa do P3 nele.

    A LISTA DO "EFEITO PRONTO" VAI PARA AS QUATRO COLUNAS com o mesmo conteúdo —
    a biblioteca de efeitos é dela, não do controle. Emitir por coluna é o que
    permite ao piloto trocar cada `<select>` sem inventar um endereço novo.
    """
    fora: dict[str, str] = {}
    if not pref:
        return fora
    for sig, d in deste.items():
        # O TETO VEM DA PÁGINA QUE O PRODUTO RENDERIZA, e é `None` no dia em que
        # ela publicar a bancada. Ver `_a_caixa_cresce`.
        fora[f'[data-controle="{pref}"] .ajustes.{sig}'] = html_dos_ajustes(
            sig, list(d.get("ajustes") or []), _cabem_no_desenho(sig))
        fora[f'[data-controle="{pref}"] select.pronto[data-lado="{sig}"]'] = opcoes
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


def _desfecho(resposta: Any) -> tuple[bool, str]:
    """`(ok, motivo)` de uma resposta da ponte, que tem TRÊS formas.

    `trigger_set` devolve `bool`, `trigger_set_checked` devolve `(ok, motivo)` e
    `trigger_set_detalhado` devolve `(ok, motivo, corpo)`. Normalizar aqui é o
    que permite o gesto RECUSAR DIZENDO sem depender de qual das três a ponte
    entregou — e um `ok, motivo = ...` rígido rebentaria com um `TypeError` na
    primeira troca de porta, que é erro sobre erro.
    """
    if isinstance(resposta, tuple):
        motivo = resposta[1] if len(resposta) > 1 else ""
        return bool(resposta[0]), str(motivo or "")
    return bool(resposta), ""


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


def _curva(chave: str) -> list[int]:
    """As dez intensidades daquele efeito pronto, lidas do produto."""
    tp = _prontos()
    if tp is None:
        raise RuntimeError(
            "efeito pronto: não consegui abrir `profiles/trigger_presets.py`.")
    valores = tp.resolve_feedback_preset(chave)
    if not valores:
        raise ValueError(
            f"efeito pronto: {chave!r} não é uma curva do produto "
            f"(`profiles/trigger_presets.FEEDBACK_POSITION_PRESETS`).")
    return list(valores)


def _aplicar(p: Any, lado: str, modo_: str, params: list[int],
             uniq: str) -> tuple[bool, str]:
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
    """
    if modo_ == "Off":
        return _desfecho(p.trigger_reset_detalhado(lado, uniq=uniq))
    return _desfecho(p.trigger_set_detalhado(lado, modo_, params, uniq=uniq))


@gesto("03-gatilhos.html", "modo")
def modo(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
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
    ok, motivo = _aplicar(p, lado, chave, _padroes(chave), uniq)
    if not ok:
        raise RuntimeError(_na_lingua_da_tela(motivo, chave)
                           or f"o daemon não aplicou o modo {chave!r}")


@gesto("03-gatilhos.html", "pronto")
def pronto(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Escolher um efeito pronto põe aquela CURVA no gatilho, na hora.

    O EFEITO PRONTO TEM DONO, e o dono é `profiles/trigger_presets.py`: os cinco
    nomes que o desenho oferece são cinco dos seis `FEEDBACK_POSITION_LABELS`, e
    cada um resolve para dez intensidades de 0 a 8.

    E ELE TROCA O MODO — está dito aqui porque é a única coisa deste gesto que
    não é dedução direta do produto. Uma curva de dez posições SÓ existe como
    `MultiPositionFeedback`; na GUI estável a linha de preset nem aparece nos
    outros 17 modos (`_update_preset_row_visibility`). No desenho ela aparece
    sempre, para os 19 — então escolher "Stop hard" com o modo em "Metralhadora"
    só pode querer dizer *"põe este gatilho na curva Stop hard"*. **Isto é
    escolha de produto e é dela**; está no relato para ela decidir. O que não
    faço é a alternativa calada: aplicar dez intensidades num modo que não tem
    posições, que o `build_from_name` recusaria e a tela não explicaria.

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
        ok, motivo = _aplicar(p, lado, modo_salvo, params, uniq)
        if not ok:
            raise RuntimeError(_na_lingua_da_tela(motivo, modo_salvo)
                               or f"o daemon não aplicou o seu efeito {nome!r}")
        return
    if chave in ("", "custom", TRAVESSAO):
        raise ValueError(
            "efeito pronto: não há curva a aplicar. '— Nenhum —' é a ausência "
            "de escolha, e `—` é como esta tela diz que o lugar está vazio. "
            "Para guardar um efeito seu, dê um nome a ele e use "
            "'Guardar esse efeito'.")
    ok, motivo = _desfecho(
        p.trigger_set_detalhado(lado, MODO_DA_CURVA, _curva(chave), uniq=uniq))
    if not ok:
        # O SPEC DA TRADUÇÃO É O DA CURVA, e não o do preset: quem recusa é o
        # `MultiPositionFeedback`, e é dele que saem os rótulos `Posição 0..9`
        # que a recusa vai nomear.
        raise RuntimeError(_na_lingua_da_tela(motivo, MODO_DA_CURVA)
                           or f"o daemon não aplicou a curva {chave!r}")


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
        perfil.gravar_e_reaplicar(novo, ctx, p)
    # O RECIBO É A LISTA NOVA. O tique seguinte a traria de qualquer jeito, mas
    # meio segundo entre salvar e ver o nome aparecer é meio segundo em que ela
    # não sabe se o botão fez algo.
    return {"blocos": _blocos_do_pronto(ctx)} if apelido else None


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
    """As listas de "Efeito pronto" das quatro colunas, com a biblioteca de agora."""
    opcoes = html_das_opcoes_de_pronto()
    fora: dict[str, str] = {}
    for m in ctx.mesa:
        pref = str(m.get("pref") or "")
        if not pref:
            continue
        for sig in LADOS:
            fora[f'[data-controle="{pref}"] select.pronto[data-lado="{sig}"]'] = opcoes
    return fora


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
PISO_DA_ABA = 3
#: O `uniq` da prova é a faixa sintética da casa: há dois portões de anonimato
#: nesta árvore e eles não perdoam.
_UNIQ = "aa:bb:cc:00:00:01"
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
    # o único em que dez posições existem.
    {"pagina": PAGINA,  # (noqa-acento) chave do contrato
     "gesto": "pronto", "clique": {"lado": "d", "v": "stop_hard"},
     "chama": [("trigger_set_detalhado",
                ["right", MODO_DA_CURVA, _curva("stop_hard")], {"uniq": _UNIQ})]},
]

#: OS GESTOS QUE O DAEMON ACEITA E NÃO PUBLICA. O `state_full` não traz
#: `triggers`: o DualSense não devolve o modo em que está — gatilho adaptativo é
#: comando de IDA, e o `docs/data/mapa-controles.csv` diz o mesmo pela outra
#: ponta. A prova destes é a porta `_detalhado`, que levanta quando o daemon
#: recusa; chegar a "aplicado" já é ele ter aceitado.
SEM_ECO = ("modo", "pronto", "ajuste")
