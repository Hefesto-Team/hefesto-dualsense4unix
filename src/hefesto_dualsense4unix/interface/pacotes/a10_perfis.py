#!/usr/bin/env python3
"""O pacote da aba `10` Perfis.

ESTA ABA JÁ ESTAVA MARCADA, e não por mim: o outro agente pôs **77 endereços**
(`data-hef`) e 11 gestos nela em 31/08, com um esquema de nomes próprio. Os dois
convivem — o nome do atributo não é o contrato; o contrato é este despachante.

O QUE TEM DONO: o perfil em vigor (`active_profile`) e o travamento do
autoswitch (`autoswitch_locked`), que é o que diz se a troca automática está
segurada.

OS DOZE GESTOS MARCADOS, E OS DEZ COM DONO — 01/09/2026, em duas levas:

    selecionar          a célula do nome, na lista. Abre o perfil no editor.
    ativar              `profile.switch`
    voltar-a-de-ontem   `restaurar_do_historico` + reaplicar + `launch_env.refresh`
    ---- a segunda leva ----------------------------------------------------
    editor.nome         renomeia: `save_profile` do nome novo + `delete_profile`
    editor.ambiente     troca a REGRA: `from_simple_choice` + `save_profile`
    editor.jogo         o programa (ou o appid) dentro da regra
    detectar            o jogo da Steam em foco, de `window_detect_last_class`
    novo                um perfil em branco, com a regra do jogo em foco
    duplicar            `model_copy` com "(cópia)" no nome, e o editor abre nela
    remover             `delete_profile`, com a pergunta NO RÓTULO do botão

A SEGUNDA LEVA SÓ FOI POSSÍVEL POR TRÊS CORREÇÕES, e nenhuma é do daemon:

1. o clique passou a trazer `valor` — o `value` do `<input>`/`<select>`. A
   primeira leva parou exatamente aqui: *"o ouvinte manda `texto:
   alvo.textContent`, que num `<input>` é vazio"*;
2. os quatro campos ganharam `data-hef-alvo="valor"` no gerador. Sem isso a
   pintura APAGAVA as opções dos dois `<select>` (medido: 5 → 0 e 15 → 0) e
   deixava os dois `<input>` com o texto do MOCKUP para sempre;
3. `pacote()` passou a mandar `editado=` para o produto. Sem isso o editor
   pintava o perfil ATIVO enquanto os botões agiam sobre o ESCOLHIDO — e ligar
   o campo Nome seria ela renomear um perfil olhando o nome de outro.

OS DOIS QUE CONTINUAM SEM DONO — `recarregar` e `editor.estilo` — estão com o
motivo medido logo acima do `PONTE`, no fim deste arquivo.

A LISTA PASSOU A CABER INTEIRA — 02/09/2026. O `<tbody>` publicado tem catorze
linhas porque catorze cabiam na figura, e a pasta dela tem **33 perfis**: os
outros dezenove não existiam na tela, e com eles nove dos dez botões desta aba,
que agem sobre o perfil ESCOLHIDO. A lista virou um `blocos` — ver
`_html_da_lista`, que também explica por que a régua do mockup não conta esta
entrega.

E A ABA PAROU DE PERGUNTAR SÓ AO DAEMON quem está valendo — ver `_valendo`. Com
`active_profile: null`, que é o estado da máquina dela hoje, três guardas se
desligavam ao mesmo tempo.

O QUE ESTA ABA NÃO SABE FAZER, e é o teto de tudo o que está acima: **o daemon
não tem `profile.save` nem `profile.delete`.** Os 39 métodos que ele atende
trazem só `profile.switch`, `profile.list` e `profile.apply_draft` — gravar e
apagar perfil roda no processo da janela, direto no disco, e por isso todo gesto
que escreve tem de avisar o daemon depois (`profile.switch` para reaplicar,
`launch_env.refresh` para a antecipação por appid).
"""
from __future__ import annotations

import re
import time
from typing import Any

# O IMPORT É DE MÓDULO, e não de dentro da função — 01/09/2026. O
# `portao_a_casa_sabe_e_o_produto_nao_faz` segue o fecho de IMPORT a partir do
# piloto que o lançador abre, e um `from … import` escondido dentro de uma
# função não entra nesse fecho: a camada do produto continuava aparecendo como
# "promessa sem caminho" mesmo depois de eu a ligar.
#
# O `sys.path` já tem o `src/` quando esta linha roda: `pacotes/__init__.py` o
# insere no import do pacote.
from hefesto_dualsense4unix.app.actions import perfis_web as _tela

from . import Contexto, perfil, registrar

#: CORRIGIDO EM 01/09/2026. Estava escrito que a lista "vem de `profiles.*`, não
#: do state_full" — e daí eu concluí que não tinha dono. `profile.list` é um
#: método vivo do daemon e responde agora; os 33 perfis dela estão em disco, em
#: `profiles_dir()`. Ter outro dono que não o `state_full` não é não ter dono.
SEM_DONO: dict[str, str] = {}


#: COMO A TELA CHAMA O QUE O PERFIL GUARDA — `match.type` no disco, uma frase
#: na coluna "Quando usar". A tradução mora aqui e não no JS: é vocabulário do
#: produto, e o desenho dela já fixou as palavras.
QUANDO = {"criteria": "Jogo", "any": "Todos — quando nenhum casa",
          "manual": "Só quando eu escolher"}


#: O PERFIL ESCOLHIDO NA LISTA — o que ela clicou por último, e o alvo dos
#: botões da aba. Vive AQUI, no pacote, e não na tela: o clique chega ao Python
#: e a pintura sai dele, então guardar no JS obrigaria o gesto a perguntar de
#: volta ao navegador o que ele acabou de mandar.
#:
#: NÃO É "O PERFIL ATIVO". São duas coisas, e a janela estável já as separa: o
#: ativo é o que está valendo agora no daemon; o escolhido é a linha em que o
#: editor está aberto. Confundi-los faria "Voltar à de ontem" agir sempre sobre
#: o que está valendo, mesmo com outra linha aberta no editor.
_ESCOLHIDO: str = ""


def _escolhido(todos: list[dict[str, Any]], ativo: str) -> str:
    """A linha aberta no editor: a última clicada, ou o perfil ativo.

    ELE DEIXA DE VALER SOZINHO quando o perfil sai do disco — apagado por fora,
    renomeado, o `HEFESTO_VARIANTE` trocado. Sem esta queda, "Voltar à de
    ontem" continuaria mirando um arquivo que não existe mais e a mensagem de
    erro falaria de um perfil que ela não vê na lista.

    A SINCRONIZAÇÃO INICIAL É ESCRITA AQUI DE PROPÓSITO, e a guarda é o que a
    torna segura de repetir: só grava quando a lista tem aquele nome. Na régua
    dos botões o `active_profile` é "regua" e nenhum perfil se chama assim,
    então nada é gravado e o estado do módulo continua limpo.

    FATO SUBSTITUÍDO — 02/09/2026, e é a segunda correção desta mesma linha.
    Estava escrito que, *"no mesmo lar de mentira do `conftest.py`"*,
    `load_all_profiles()` devolve **9 perfis** (os de fábrica, que ela semeia).
    **Sob o `pytest` ele devolve `[]`**: a `conftest.py:2114` põe
    `HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1` em TODO teste, e é justamente
    esse env que desliga o `_maybe_seed_presets`. Os nove eram reais — mas num
    processo SEM o pytest, que é onde a medição de 01/09 rodou. Conferido em
    02/09 com uma sonda dentro da suíte: `sorted(nomes) == []`.

    O QUE ISSO NÃO MUDA: a guarda continua segura de repetir. Com a lista vazia
    o `ativo` nunca está em `nomes`, então nada é gravado — que é o mesmo
    desfecho que a razão original previa por outro caminho.
    """
    global _ESCOLHIDO
    nomes = {p["nome"] for p in todos}
    if _ESCOLHIDO and _ESCOLHIDO not in nomes:
        _ESCOLHIDO = ""
    if not _ESCOLHIDO and ativo in nomes:
        _ESCOLHIDO = ativo
    return _ESCOLHIDO or ativo


#: A JANELA DA CONFIRMAÇÃO do "Remover", em segundos. Não é gosto: um armamento
#: sem prazo é uma armadilha — ela clica, se distrai, volta meia hora depois,
#: clica de novo e o perfil some sem que nada na tela tenha dito por quê.
SEGUNDOS_PARA_CONFIRMAR = 8.0

#: OS ENDEREÇOS QUE A PÁGINA PUBLICADA **NÃO SABE RECEBER** — e emiti-los não é
#: um valor que não aparece: é a página se DESMONTANDO a cada meio segundo.
#:
#: A CAUSA, e ela é do pintor, não desta aba: `escrever()` termina em
#: `el.textContent = t` (`hefesto_vivo.py:170`), e `textContent` num elemento que
#: tem FILHOS-ELEMENTO apaga todos eles. O desvio existe — `data-hef-alvo` —, mas
#: quem o escreve é o GERADOR, no HTML, e o HTML publicado só muda por ato dela.
#:
#: MEDIDO em 02/09/2026 sobre `interface/paginas/10-perfis.html`, contando os
#: filhos-elemento de cada alvo (a régua está em
#: `tests/unit/test_a_guarda_do_perfil_nao_apaga_a_tabela.py`):
#:
#:     endereço                 tag      elementos  filhos  o que some
#:     guarda.linhas            tbody            1       4  as 4 linhas, com 24 endereços
#:     editor.prioridade.dica   span             1       2  o TRILHO e o número ao lado
#:
#: **É ISTO QUE ELA FOTOGRAFOU.** A tabela `Controle / Ajuste próprio / ID da
#: peça` mostrando um `2` sozinho é o `guarda.linhas` escrevendo `"2"` no
#: `<tbody>`; e o *"Prioridade 1 de 200. O maior vence a disputa…"* que ela leu
#: no lugar do trilho é o `editor.prioridade.dica` comendo o trilho e o número —
#: a frase dela, *"esse texto em perfis nem faz sentido mais"*, é sobre uma
#: FRASE QUE ENGOLIU UM CONTROLE DESLIZANTE, não sobre o texto em si.
#:
#: FATO DERRUBADO — 02/09/2026, e o enunciado desta frente o repetia. Aqui
#: estava escrito que `editor.prioridade` também não sai, porque o
#: `data-hef-alvo="largura"` estaria *"já escrito na BANCADA (`aba10.py`),
#: esperando o ato de publicar DELA"*. **Ela já publicou.** O commit `70b58116`
#: levou a aba inteira ao produto, e o atributo está nas DUAS páginas — na
#: linha 1162 da publicada e na 1165 da bancada. Enquanto este nome ficou
#: na lista, a barra da prioridade continuou nos 90% do desenho para um perfil
#: em 1 de 200 — a tela afirmando o que não mediu, com o conserto no disco há
#: um commit. Ele SAI da lista, e o `escrever()` do piloto escreve a largura.
#:
#: SEGUNDO FATO DERRUBADO — 02/09/2026. Aqui estava escrito que `guarda.secao`
#: fica *"porque o pintor precisa de um alvo que ligue/desligue CLASSE, e nenhum
#: dos cinco alvos de hoje (texto·largura·fundo·valor·html) alcança uma
#: classe"*. **O alvo `classe` nasceu no mesmo dia** (`hefesto_vivo.py`, o ramo
#: `if(alvo === 'classe')`), e a nota dele já cita esta coluna pelo nome.
#: `aba10.linha_do_controle` passou a escrever `data-hef-alvo="classe"` nos
#: dezesseis `<span class="gr">`, e o nome **saiu desta lista** — mas não para
#: sair sempre: ele passou a ser decidido por MEDIÇÃO, em
#: `_a_pagina_acende_a_secao_por_classe()`, que pergunta à página PUBLICADA se
#: ela já traz o atributo. É o mesmo padrão do `a02_controles`/`a03_gatilhos`, e
#: a razão de ele existir aqui está medida logo abaixo.
#:
#: **POR QUE NÃO BASTOU TIRAR DA LISTA:** `--publicar-enderecos 10` RECUSOU.
#: A ferramenta é por PÁGINA, não por atributo, e esta página já carregava uma
#: mudança de DESENHO pendente — a primeira opção `—` do Estilo de Jogo, decisão
#: dela deste dia. Medido:
#:
#:     endereços: 0 levada(s) · 1 recusada(s) · 0 já igual(is)
#:       RECUSADA 10-perfis.html  (o DESENHO mudou — isto é decisão dela)
#:
#: Emitir mesmo assim seria escrever TEXTO nos dezesseis `<span>` da página que
#: o produto renderiza hoje, apagando o glifo SVG de cada um duas vezes por
#: segundo. Por isso a emissão pergunta à página: hoje ela cala, e no tique
#: seguinte ao `--publicar 10` dela as dezesseis células acendem sem ninguém
#: tocar em código.
#:
#: **E O QUE SAÍA DAQUI ESTAVA ERRADO, o que só se viu ao destravar.** A
#: emissão era `[s for g in guarda for s in (g.get("secoes") or [])]` —
#: iterar um `dict` dá as CHAVES. Com dois controles na mesa ela devolvia
#: `["leds","triggers","rumble","speaker"] * 2`, sempre, para qualquer perfil.
#: Como `ligado("leds")` é verdadeiro, publicar isso teria ACENDIDO AS QUATRO
#: SEÇÕES NOS QUATRO CONTROLES — exatamente o que a docstring de
#: `perfis_web._secoes_do_controle` diz que a tela não pode ensinar (*"apagado é
#: a resposta certa para a maioria dos controles na maioria dos perfis"*). A
#: lista agora manda os VALORES (`bool`), que é o que o alvo `classe` lê.
#:
#: **PARA DESTRAVAR OS QUE FICAM**, e cada um tem um dono diferente:
#:
#:   guarda.linhas       não tem conserto e não precisa: é o `<tbody>`, um
#:                       CONTINENTE. Nunca houve valor para escrever nele.
#:                       (A lista de perfis tinha o mesmo formato e ganhou
#:                       conserto por OUTRA porta — ver `_html_da_lista`.)
#:   editor.prioridade.dica  **a frase JÁ FOI APROVADA e não chega à tela** —
#:                       correção de fato, 02/09/2026. Aqui estava escrito que
#:                       *"o texto novo é decisão DELA"*; ela decidiu (decisão
#:                       nº11, *"Quando dois perfis servem ao mesmo tempo, o de
#:                       número maior entra."*) e o texto está em
#:                       `perfis_web._pacote_do_editor`. O que segura é ESTA
#:                       lista, e por uma razão que continua de pé: o alvo é um
#:                       `<span>` com DOIS filhos-elemento (o trilho e o
#:                       número), e `textContent` os apagaria. A tela mostra
#:                       hoje o `title=` estático do desenho, que não é nem a
#:                       frase velha nem a nova. **Para destravar, o pintor
#:                       precisa de um `data-hef-alvo` que escreva ATRIBUTO
#:                       (`title=`)** — `hefesto_vivo.py`, fora do território
#:                       desta frente; está no relatório.
#:   editor.estilo       **não há valor a escrever, e escrever apaga o `—` que
#:                       ela pediu** — 02/09/2026. O perfil não tem campo de
#:                       Estilo (`perfis_web` devolve `estilo: None`), então o
#:                       que sairia daqui é o vazio. E o `escrever()` do piloto
#:                       troca vazio por `'—'` ANTES do ramo `valor`
#:                       (`hefesto_vivo.py`, `const t = vazio ? '—' : …`): num
#:                       `<select>` cuja opção vazia tem `value=""`, escrever
#:                       `'—'` passa a guarda pelo TEXTO da opção e depois
#:                       deixa `selectedIndex = -1` — o campo renderiza EM
#:                       BRANCO, e `el.value` nunca volta igual ao escrito, o
#:                       que faz o contador somar +1 a cada visita.
#:                       **PRECISÃO DA AUDITORIA, 02/09/2026:** aqui estava
#:                       escrito que *"o desenho já nasce com a opção certa
#:                       marcada"*, e isso vale só na BANCADA. No PUBLICADO —
#:                       o que ela abre hoje — a linha 1194 ainda é
#:                       `<option selected>Luta</option>`, e a foto de hoje
#:                       mostra `Estilo de Jogo: Luta` nos 33 perfis dela. Não
#:                       pintar continua sendo o certo (pintar deixaria o campo
#:                       EM BRANCO), mas o `—` da decisão nº3 só chega quando
#:                       ela publicar. Quem lhe dá valor de verdade é a
#:                       ONDA-PERFIS-04, e nesse dia o piloto precisa de um
#:                       caminho para MARCAR uma opção de `value` vazio.
NAO_PINTAVEIS = ("guarda.linhas", "editor.prioridade.dica", "editor.estilo")

#: A resposta de `_a_pagina_acende_a_secao_por_classe()`, lida UMA vez.
_SECAO_POR_CLASSE: bool | None = None

#: O `guarda.secao` da página com o alvo `classe` declarado, nas DUAS ordens de
#: atributo — quem gera o HTML não deve a ninguém a ordem em que os escreve.
_ALVO_DA_SECAO = re.compile(
    r'data-hef="guarda\.secao"[^>]*data-hef-alvo="classe"'
    r'|data-hef-alvo="classe"[^>]*data-hef="guarda\.secao"'
)


def _a_pagina_acende_a_secao_por_classe() -> bool:
    """A página **PUBLICADA** já sabe receber o `guarda.secao` como CLASSE?

    ESTA PERGUNTA É A CURA QUE VALE NOS DOIS MUNDOS, e ela existe porque a
    coluna "Ajuste próprio" ficou entre um desenho pronto e um ato dela.

    O que a tela mostra é uma CLASSE (`.gr.on` aceso, `.gr` apagado), e o único
    alvo do pintor que alcança classe nasceu em 02/09/2026. O atributo que o
    liga — `data-hef-alvo="classe"` — está escrito no gerador e já saiu na
    bancada; **só que `--publicar-enderecos 10` recusou**, porque a mesma página
    carrega uma mudança de DESENHO pendente (a opção `—` do Estilo de Jogo, que
    é decisão dela). A ferramenta publica por PÁGINA, não por atributo.

    ENTÃO O PACOTE PERGUNTA À PÁGINA, uma vez, em vez de um nome cravado numa
    lista. Sem esta guarda, o produto que ela usa HOJE receberia TEXTO nos
    dezesseis `<span class="gr">` e o `el.textContent` do ramo padrão apagaria o
    glifo SVG de dentro de cada um, duas vezes por segundo — o mesmo estrago que
    ela fotografou na tabela desta aba. Com ela, o tique seguinte ao
    `--publicar 10` acende as dezesseis células sem ninguém tocar em código.

    É o padrão que `a02_controles._enderecos_da_pagina` e
    `a03_gatilhos._pagina_publicada` já usam, pela mesma razão e com a mesma
    escolha deliberada de `publicado=True`: **o piloto abre SEMPRE o
    publicado**, e medir a bancada daria verde sobre uma página que o `WebView`
    não carrega.

    Página ilegível responde `False`: o erro seguro é não escrever.
    """
    global _SECAO_POR_CLASSE
    if _SECAO_POR_CLASSE is None:
        from hefesto_dualsense4unix.interface import onde

        try:
            doc = onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
        except OSError:
            doc = ""
        _SECAO_POR_CLASSE = bool(_ALVO_DA_SECAO.search(doc))
    return _SECAO_POR_CLASSE


#: AS CHAVES QUE SAEM DAQUI E A PÁGINA NÃO TEM ONDE PÔR — o inventário, com a
#: razão medida de cada uma. É a lista irmã do `SEM_ENDERECO` da aba 06, e ela
#: existe pela mesma razão: **órfão calado é defeito; órfão declarado é
#: inventário.** A régua que a cobra é
#: `tests/unit/test_a_aba_perfis_manda_para_um_endereco_que_existe.py`.
#:
#: A DIFERENÇA PARA `NAO_PINTAVEIS`, e as duas listas não se confundem:
#: ali estão os endereços que a página TEM e que escrever DESTRÓI; aqui estão
#: os valores que a página NÃO TEM — eles caem no vazio, sem estrago e sem
#: notícia. Um valor desta lista nunca aparece na tela nem no contador.
#:
#: MEDIDO em 02/09/2026 contra AS DUAS PÁGINAS, uma de cada vez — e elas
#: **NÃO** são byte-idênticas, ao contrário do que esta linha e o parágrafo do
#: `editor.prioridade` acima diziam até a auditoria de 02/09. `diff
#: mockup/10-perfis.html src/…/interface/paginas/10-perfis.html` acusa **16
#: linhas** — a aba 10 é uma das SEIS em que o produto está atrás da bancada,
#: e o portão `desenho-aprovado` fica verde justamente por isso estar
#: declarado. A divergência é a decisão nº3 DELA: o `<select>` do Estilo nasce
#: com `<option value="" selected>—</option>` na BANCADA e continua em
#: `<option selected>Luta</option>` no PUBLICADO, que é o que o produto
#: renderiza hoje. Está declarada em `mockup/DIVERGENCIAS.md`, seção
#: `## 10-perfis.html`, esperando o ato de publicar dela.
#:
#: **É POR ISSO QUE A RÉGUA COBRA AS DUAS.** Escrever aqui que elas são iguais
#: é a frase que faz a próxima pessoa conferir só uma — e a armadilha desta
#: leva é exatamente essa: curar na bancada e o produto seguir lendo o
#: publicado. Ver `test_a_aba_perfis_manda_para_um_endereco_que_existe.py`,
#: que roda `[bancada]` e `[publicada]` como dois casos separados.
SEM_ENDERECO = {
    # Os quatro do editor vêm inteiros de `perfis_web._pacote_do_editor` pelo
    # laço de achatamento — a camada do produto os monta e o desenho ainda não
    # tem lugar para eles. `*.travado` é o seletor que a tela não pode editar
    # sem rebaixar a regra do disco; `*.recado` é a frase que explica por quê.
    # São trabalho de DESENHO, não de código: quando o mockup ganhar o lugar,
    # o valor já está saindo.
    "editor.ambiente.travado": "o seletor travado não tem marca no desenho",
    "editor.ambiente.recado": "a frase da válvula não tem lugar no desenho",
    "editor.estilo.travado": "idem, para o Estilo de Jogo",
    "editor.estilo.recado": "idem — a frase de `GESTOS_SEM_MOTOR`",
    # `quantos` é a SEGUNDA forma da mesma pergunta: `perfis.conta` tem
    # endereço (a página o mostra) e sai deste mesmo pacote. Medido: ninguém o
    # lê hoje — nem produto, nem régua. Fica declarado, e não apagado, porque
    # tirar emissão é decisão de quem tem a aba inteira na mão; declarado, ele
    # aparece nesta lista para quem for tomá-la.
    "quantos": "a contagem que a tela mostra é `perfis.conta`, e essa tem endereço",
    # `autoswitch_locked` é estado do daemon, e o desenho desta aba não o
    # mostra em lugar nenhum. Quem tem endereço para a troca automática é a aba
    # Sistema (`data-campo="hefesto-troca-de-perfil"`, em `09-sistema.html`).
    "travado": "a trava da troca automática não é desenhada nesta aba",
}

#: OS ENDEREÇOS QUE JÁ ESTÃO NA BANCADA E ESPERAM O ATO DELA — 03/09/2026.
#:
#: NÃO É UM `SEM_ENDERECO` MAIS FROUXO, e a diferença é o que cada lista afirma:
#: ali estão os valores que a PÁGINA NÃO TEM onde pôr — nem hoje, nem depois de
#: publicar; aqui estão os que o gerador JÁ marcou em `mockup/` e que só chegam a
#: `interface/paginas/` quando ela mandar. **Publicar é ato dela**
#: (`check_o_desenho_aprovado.py --publicar NN`), e nenhuma frente o faz.
#:
#: ELA PRECISOU EXISTIR, e o buraco era estrutural: a régua cobrava endereço nas
#: DUAS páginas, então marcar um campo novo no gerador reprovava sempre — a única
#: forma de ficar verde era publicar, que é justamente o que uma frente não pode
#: fazer. Sem esta lista, "dar endereço" e "publicar" viravam o mesmo ato.
#:
#: A RÉGUA CONTINUA MORDENDO NOS DOIS SENTIDOS
#: (`test_a_aba_perfis_manda_para_um_endereco_que_existe.py`): um nome daqui tem
#: de EXISTIR na bancada — senão não está esperando, está faltando — e tem de NÃO
#: existir ainda na publicada, senão a declaração envelheceu e é a régua se
#: desligando sozinha no dia em que ela publicar.
ESPERANDO_A_PUBLICACAO = {
    "guarda.plastico": (
        "a barra da cor do plástico ganhou endereço em 03/09/2026 "
        "(IDENTIDADE-VEM-DE-CIMA); a página publicada é de 02/09"
    ),
}

#: O que o "Remover" está esperando: `(perfil, instante)`, ou `None`.
_ARMADO: tuple[str, float] | None = None

#: O perfil cujos campos de TEXTO já foram pintados, e o instante do último
#: tique desta aba. Ver `_uma_vez_so`.
_PINTADO_PARA: str = ""
_ULTIMO_TIQUE: float = 0.0

#: OS DOIS CAMPOS QUE NÃO SE REPINTAM, porque ela DIGITA neles.
#:
#: ERAM TRÊS até 02/09/2026: o `editor.estilo` estava aqui por outro motivo —
#: *"o valor é sempre o mesmo e repintá-lo custava uma escrita por tique"*. Ele
#: saiu porque a razão dele não é "não repintar", é **não pintar**: foi para
#: `NAO_PINTAVEIS`, onde está a medição. Deixá-lo nos dois lugares faria duas
#: listas decidirem o mesmo campo.
CAMPOS_QUE_ELA_DIGITA = ("editor.nome", "editor.jogo")


def _uma_vez_so(alvo: str) -> tuple[str, ...]:
    """Os endereços a OMITIR deste tique. Vazio = pinte tudo.

    O PROBLEMA, medido em 01/09/2026 lendo o `escrever()` do piloto
    (`hefesto_vivo.py:114`): com `data-hef-alvo="valor"` a pintura faz
    `el.value = t` sempre que o valor difere. O tique é de 500 ms
    (`hefesto_vivo.py:63`). Na segunda tecla que ela digita, o campo já difere
    do que está no disco — e meio segundo depois a pintura o devolve ao valor
    do perfil. **O campo ficaria intocável.**

    A CURA É PINTAR UMA VEZ POR ESCOLHA: quando o perfil aberto no editor muda,
    os três campos vão uma vez; enquanto ela fica no mesmo perfil, ninguém
    escreve neles. Foi assim que o campo pôde ganhar gesto — sem isto, ligar o
    Nome seria ligar um campo que se apaga sozinho.

    E ELE VOLTA A PINTAR QUANDO ELA SAI DA ABA E VOLTA. Sem esta segunda
    guarda, a página recarregada mostraria de novo o "Mortal Kombat" do
    MOCKUP — o `<input>` nasce com o valor do desenho, e a memória deste módulo
    diria "já pintei". O sinal é o BURACO no tique: as dez abas dividem o mesmo
    piloto, e `pacote()` só é chamado enquanto esta página está aberta, a cada
    500 ms. Um intervalo maior que 2 s significa que a página foi embora e
    voltou.
    """
    global _PINTADO_PARA, _ULTIMO_TIQUE
    agora = time.monotonic()
    voltou = (agora - _ULTIMO_TIQUE) > 2.0
    _ULTIMO_TIQUE = agora
    if voltou or alvo != _PINTADO_PARA:
        _PINTADO_PARA = alvo
        return ()
    return CAMPOS_QUE_ELA_DIGITA


#: O separador do rótulo, EM TEXTO PURO. O dono da forma continua sendo
#: `interface/monta.SEPARADOR` — `' <span class="pt">•</span> '` —, que é
#: MARCAÇÃO e não pode entrar num `textContent`: a célula mostraria os
#: marcadores como letras. Aqui vai o mesmo caractere, sem a casca.
#:
#: NÃO IMPORTO O `monta`: ele é o GERADOR do desenho e faz leitura de disco no
#: import (`topo.html`, `fim.html`, o SVG, a logo, dois CSV). Um gerador no
#: caminho do produto é uma janela que não abre onde não há repositório. Quem
#: impede a segunda gramática é a régua
#: `test_o_rotulo_da_guarda_e_o_mesmo_do_monta`, que compara este rótulo com o
#: do `monta.rotulo(c, "curta")` sem a marcação — se ela mudar a ordem
#: (**marca • player • plástico • transporte**, decisão dela de 26/08), a régua
#: reprova AQUI antes de a tela discordar de si mesma.
SEPARADOR_EM_TEXTO = " • "


def _rotulo_curto(controle: dict[str, Any]) -> str:
    """`P1 • Cosmic Red • USB` — a forma `curta` do `monta.rotulo`, sem marcação.

    `jogador`, `nome` e `via` são os três campos que `mesa_viva.mesa_do_estado`
    devolve, e são exatamente os três que a forma `curta` junta.
    """
    return SEPARADOR_EM_TEXTO.join([
        f"P{controle.get('jogador') or '—'}",
        str(controle.get("nome") or "—"),
        str(controle.get("via") or "—"),
    ])


def _plastico(controle: dict[str, Any]) -> str:
    """O hexadecimal da casca daquele controle, **pelo dono da cor**.

    A LEI É DELA, 03/09/2026: *"se no topo tá mostrando controle white player 1,
    então cada aba vai usar os controles lá de cima. Não mistura com a info dos
    mockups."* A barra de 3px da linha era `--plastico` cravado no `<tr>` pelo
    gerador — a cor do controle do DESENHO —, e ficava lá enquanto o
    `guarda.nome` ao lado já vinha do aparelho: a linha dizia `P1 • White • USB`
    com a barra vermelha do mockup.

    `monta.cor_da_zona` lê o `<style>` que `scripts/gerar_cores_do_dualsense.py`
    escreveu no `ds_limpo.svg` — o MESMO lugar de onde a fita do topo tira a cor
    do chip. Reescrever a leitura aqui criaria a segunda verdade sobre a cor, que
    é o que o portão `check_cores_do_dualsense.py` existe para matar.

    O IMPORT É TARDIO E GUARDADO, e não uma exceção que eu abri: é exatamente o
    que `hefesto_vivo._fita` faz para esta mesma leitura, pela mesma razão. O
    `monta` lê disco no import (o esqueleto, o SVG e dois CSV de `docs/`), então
    um `import` no topo derrubaria a janela onde não há repositório. E não é um
    caminho novo: sem repositório a fita do topo também não repinta.

    `SystemExit` NO `except`, e ele não é `Exception`: `cor_da_zona` ergue
    justamente essa para um colorway que o SVG não tem, e um `except Exception`
    passaria ao lado — foi como o piloto morreu na primeira execução da fita viva.

    SEM COR LIDA, DEVOLVE VAZIO. Pelo rádio a cor não vem (o mapa de canais diz
    `identidade.cor_do_aparelho = não`) e `mesa_do_estado` entrega `cor: ""`.
    Inventar um cinza, ou cair na cor do mockup, seria a tela afirmando um modelo
    que ninguém pode conferir — o defeito que esta frente veio desfazer. Com o
    vazio o piloto escreve `''` no alvo `cor`, o `style` de linha cai, o
    `color:transparent` da classe volta e a barra SOME: campo sem informação não
    mostra nada, regra dela.
    """
    slug = str(controle.get("cor") or "")
    if not slug:
        return ""
    try:
        from hefesto_dualsense4unix.interface import monta

        return str(monta.cor_da_zona(slug))
    except (Exception, SystemExit):
        return ""


def _mesa_com_rotulo(mesa: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A mesa no formato que `perfis_web.pacote_da_aba` DIZ esperar.

    FATO ERRADO, SUBSTITUÍDO — 02/09/2026. A docstring de
    `perfis_web.pacote_da_aba` afirma que a mesa vem *"no formato que
    ``mesa_viva.mesa_do_estado`` devolve mais ``rotulo`` e ``plastico``"*, e o
    `_linhas_da_guarda` lê `controle.get("rotulo")` (`perfis_web.py:397`).
    **`mesa_do_estado` não devolve nenhum dos dois** — os campos dela são
    `pref`, `uniq`, `jogador`, `cor`, `nome`, `via`, `transporte`, `alvo`,
    `mascara` (`mesa_viva.py:320-332`). Medido: `guarda.nome` saía `["", ""]`
    para os DOIS controles da mesa dela, e a tabela ficava sem nome nenhum.

    QUEM JÁ FAZIA ISTO CERTO: `interface/perfis_vivos.mesa_de_agora:318` — o
    visor da aba, que o piloto **não carrega**. É o padrão que a ONDA B1 mediu:
    *o reuso aconteceu, no arquivo que o piloto não abre*. Aqui ele entra no
    caminho do produto.

    O `plastico` ENTROU EM 03/09/2026, e o fato acima valia para ele também:
    `_linhas_da_guarda` lê `controle.get("plastico")` (`perfis_web.py:404`) e
    recebia `""` para todo controle, porque ninguém o punha aqui. Ver `_plastico`.
    """
    return [{**c, "rotulo": _rotulo_curto(c), "plastico": _plastico(c)}
            for c in mesa]


#: O SELETOR DO CORPO DA LISTA — CSS, e não `data-campo`: o `blocos` do piloto
#: endereça por `document.querySelector` (`hefesto_vivo.py`, o laço
#: `for(const [seletor, html] of Object.entries(p.blocos || {}))`).
SELETOR_DA_LISTA = 'tbody[data-hef="perfis.lista"]'

#: A INDENTAÇÃO DA LINHA no desenho: dezesseis espaços, os mesmos que
#: `aba10.linha_do_perfil` emite. Ela não muda nada na tela — HTML come espaço
#: em branco entre linhas de tabela —, e existe para que a régua de forma possa
#: comparar as duas emissões CARACTERE A CARACTERE.
_RECUO = " " * 16


def _texto(v: Any) -> str:
    """Um valor pronto para virar TEXTO dentro de uma célula.

    ESCAPAR É OBRIGATÓRIO AQUI E NÃO ERA NO GERADOR, e a diferença é a fonte: o
    gerador escreve os catorze nomes que ESTA CASA digitou no `PERFIS` do
    desenho; esta função escreve os 33 que estão no disco DELA. Um perfil
    chamado `Bail < Jail` viraria marcação no meio da linha.
    """
    s = str(v if v is not None else "")
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace("\xa0", "&nbsp;"))


def _atr(v: Any) -> str:
    """Um valor pronto para virar VALOR DE ATRIBUTO — `title=`, `data-…=`.

    **ESCAPA MENOS QUE O `html.escape` DO PYTHON, e isso é a cura de um defeito
    medido, não um relaxamento.** O `blocos` do piloto só reescreve o miolo
    quando `alvo.innerHTML !== html` — ou seja, ele compara a MINHA string com a
    **serialização que o navegador devolve**. Escapar o que o serializador não
    escapa faz as duas nunca baterem, e o bloco é reescrito a cada 500 ms para
    sempre.

    MEDIDO em 02/09/2026, com o piloto aberto na aba por dez segundos e com o
    mesmo HTML injetado num Chrome de bancada (`_ferramentas` do desenho, sem
    janela) para ler o `innerHTML` de volta:

        `html.escape(quote=True)`  →  21 tiques, 17 escritas em CADA um
        escapando como o serializador →  1 escrita, e silêncio depois

    As duas divergências, e as duas são de escapar DEMAIS:

        `'`   o Python manda `&#x27;`, o navegador devolve `'`   (`DON'T SCREAM`)
        `\\n`  o Python (na minha primeira tentativa) mandava `&#10;`, o navegador
              devolve a quebra CRUA — e a dica da disputa tem dois parágrafos

    E NÃO É INSEGURO: dentro de aspas duplas, um `'` e um `<` não fecham nada —
    quem fecha o atributo é a aspa dupla, e ela continua virando `&quot;`. É
    exatamente o conjunto que o serializador de HTML escapa em atributo.

    O CUSTO DE NÃO CURAR ISTO NÃO É SÓ O CONTADOR: reescrever o `<tbody>` a cada
    meio segundo apaga o `:hover` da linha sob o mouse dela e desfaz qualquer
    seleção de texto na lista — três vezes por segundo, enquanto ela procura um
    perfil entre 33.
    """
    s = str(v if v is not None else "")
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("\xa0", "&nbsp;")


def _linha_da_lista(nome: str, prioridade: str, quando: str,
                    ativo: bool, dica: str = "") -> str:
    """Uma linha da lista de perfis — a MESMA forma que o desenho crava.

    O DONO DA FORMA CONTINUA SENDO O GERADOR, `aba10.linha_do_perfil`, cuja
    docstring já dizia a que veio: *"a MESMA para o mockup e para a viva … a aba
    viva precisa do desenho, não de uma cópia dele"*. Só que ele **não atravessa
    para o produto**: `aba10.py` faz `sys.path.insert` e `from monta import …`,
    e o `monta` lê seis arquivos do repositório no import — um gerador no
    caminho do produto é uma janela que não abre onde não há repositório. É a
    mesma razão pela qual o `SEPARADOR_EM_TEXTO` acima é uma constante e não um
    import.

    ENTÃO O QUE IMPEDE A SEGUNDA GRAMÁTICA É UMA RÉGUA, e não a boa vontade:
    `test_a_lista_de_perfis_cabe_inteira.py::test_a_linha_viva_e_a_linha_do_desenho`
    importa o gerador (no teste ele pode) e compara as duas saídas caractere a
    caractere. Mexer no desenho da linha sem mexer aqui reprova ANTES de a tela
    discordar de si mesma.

    A ÚNICA DIVERGÊNCIA DECLARADA É O ESCAPE — ver `_texto` e `_atr`.
    """
    return (f'{_RECUO}<tr class="{"ativo" if ativo else ""}" '
            f'data-hef-perfil="{_atr(nome)}" title="{_atr(dica)}">'
            f'<td data-hef="perfis.linha.nome" data-hef-gesto="selecionar">'
            f'{_texto(nome)}</td>'
            f'<td class="pri" data-hef="perfis.linha.prioridade">'
            f'{_texto(prioridade)}</td>'
            f'<td class="quando" data-hef="perfis.linha.quando">'
            f'{_texto(quando)}</td></tr>')


def _html_da_lista(lista: list[dict[str, Any]], vazia: str) -> str:
    """As linhas da lista de perfis, TODAS — e é a maior mentira que esta aba
    contava.

    MEDIDO em 02/09/2026, na máquina dela: `load_all_profiles()` devolve **33**
    perfis e o `<tbody>` publicado tem **14 linhas**. O contador ao lado do
    título dizia "33 perfis" — e dizia a verdade — enquanto a tabela logo abaixo
    mostrava catorze. **Dezenove perfis dela não tinham como ser clicados**, e
    com eles nove dos dez botões desta aba: `ativar`, `remover`, `duplicar`,
    `editor.nome`… todos agem sobre o perfil ESCOLHIDO, e escolher é clicar numa
    linha que existe.

    POR QUE NÃO SE PINTA CAMPO A CAMPO: é a mesma razão da fita de chips e do
    mapa do gabinete — **um bloco cujo número de filhos muda com o dado não tem
    endereço para o filho que ainda não existe**. A lista de perfis é o caso
    mais puro: o desenho cravou catorze porque catorze cabiam na figura.

    TRÊS COISAS CHEGAM À TELA POR AQUI E NÃO CHEGAVAM POR NENHUMA OUTRA PORTA:

    1. **as linhas que faltavam** — as 19;
    2. **a classe `ativo` na linha certa.** O desenho a crava na PRIMEIRA linha,
       e até hoje ela ficava lá. Acertava por acidente — `ordem_de_exibicao`
       põe o ativo em primeiro —, e mentia inteiro quando não há perfil ativo
       nenhum: a tela realçava um perfil que não está valendo. Nenhum dos cinco
       alvos do pintor liga uma CLASSE; o `blocos` traz a linha pronta, com a
       classe dentro dela, e não precisa dele;
    3. **o `title` da disputa.** `explicacao_da_disputa` existe em
       `profiles_actions:403`, `perfis_web._linhas_da_lista` já a chamava a cada
       tique, e o valor morria no dicionário: o `title=""` do desenho nasce
       vazio *"porque a dica é a DISPUTA, e disputa é dado — o mockup não tem
       nenhum"* (palavras do gerador). O dado existe desde então; faltava a
       porta.

    A LISTA VAZIA TAMBÉM É UM ESTADO, e a frase dela já estava escrita e nunca
    tinha aparecido: `perfis_web.LISTA_VAZIA` diz o que fazer para ter o
    primeiro perfil. Sem esta linha o `<tbody>` ficaria em branco — a tela
    calada sobre um estado que ela sabe explicar.

    **ESTE `<tbody>` AINDA É REESCRITO A CADA TIQUE, e a causa NÃO é o escape** —
    medido em 02/09/2026 no WebKit da janela dela, com o daemon vivo e uma sonda
    no laço do `blocos` do piloto. Em 20 tiques: `BLOCOS 20`, contra 1 de cada
    um dos outros endereços da aba (eles assentam no primeiro tique). O primeiro
    caractere divergente é o 594:

        na TELA     …data-hef-gesto="selecionar" data-hef-visto="1">meu_perfil…
        no PRODUTO  …data-hef-gesto="selecionar">meu_perfil…

    O `escrever()` do piloto carimba `el.dataset.hefVisto = '1'` em TODO
    elemento que visita — inclusive quando escreve zero, que é o ponto do selo.
    O laço do `blocos` roda ANTES da distribuição por endereço e compara
    `alvo.innerHTML !== html`: do segundo tique em diante a tela tem 99 selos
    que o produto não tem (12.222 caracteres contra 10.341), e as duas strings
    nunca mais batem. O custo é o que a nota do `_atr` já descreve — o `:hover`
    da linha sob o mouse dela apagado duas vezes por segundo, enquanto ela
    procura um perfil entre 33.

    **A CURA MORA NO PILOTO, e não aqui** — carimbar o selo fora da serialização
    (um `WeakSet` em JS) ou comparar sem ele. Emitir o selo daqui faria esta aba
    conhecer um detalhe interno do pintor. Está relatado ao orquestrador.

    HOJE SÓ ESTA LISTA PAGA, e conferi antes de acusar as irmãs: o defeito só
    morde um `blocos` cujos FILHOS tenham endereço, e os dois da `08-conexoes`
    (`.mm-faces` e `.mm-lista`) não emitem `data-campo` nenhum dentro. Quando
    emitirem, entram no mesmo buraco.
    """
    if not lista:
        return (f'{_RECUO}<tr class="vazia"><td colspan="3">'
                f'{_texto(vazia)}</td></tr>')
    return "\n".join(
        _linha_da_lista(str(x.get("nome") or ""), str(x.get("prioridade") or ""),
                        str(x.get("quando") or ""), bool(x.get("ativo")),
                        str(x.get("dica") or ""))
        for x in lista)


def _valendo(ctx: Contexto, todos: list[Any] | None = None) -> str:
    """Qual perfil está valendo AGORA, **com o nome que a LISTA mostra**.

    `profiles_actions.perfil_que_esta_valendo` é o §P1 desta casa, e esta aba
    era o lugar mais caro para não o chamar: ela lia
    `ctx.state.get("active_profile")` cru, e a própria docstring de lá diz que o
    daemon responder `active_profile: null` é *"o estado da máquina dela hoje"*.
    Com o `null`, as três guardas desta aba se desligavam ao mesmo tempo:

        ativar     deixava de recusar o perfil que JÁ está valendo
        remover    deixava de recusar apagar o perfil que está valendo —
                   e o daemon segue aplicando um arquivo que não existe mais
        voltar…    deixava de reaplicar depois de restaurar, e o arquivo voltava
                   ao que era com o controle no que estava

    E a lista perdia o realce da linha certa. O dono consulta o daemon primeiro
    e, só se ele calar, o marcador em disco — pelo mesmo caminho do boot
    (`resolve_boot_profile`). Ele nunca levanta: qualquer falha de I/O vira
    `nao_sei`, que aqui é o `""`.

    **O `find_by_slug` NO FIM É A SEGUNDA METADE, e sem ele a mesma tela dava
    DOIS vereditos** — 02/09/2026. O que vem do daemon ou do marcador é um NOME
    DIGITADO, e daqui ele seguia cru para dois comparadores diferentes:

        o realce da lista   `perfis_web._linhas_da_lista:358` faz `p.name == ativo`
        as guardas dos gestos  `mesmo_slug` (R-10), em `ativar` e `voltar…`

    MEDIDO com 33 perfis no disco e o daemon calado, marcador em `sackboy` e o
    perfil chamado `Sackboy`:

        realce -> []                     (nenhuma das 33 linhas se acende)
        Ativar -> "já é o perfil que está valendo"   (a guarda por slug pega)

    Duas guardas, dois vereditos, uma tela — e o marcador em caixa diferente é
    exatamente o caso que `find_by_slug` existe para cobrir (a docstring dele
    cita "Navegação"/"Navegacao"). **O dono passa a ser UM SÓ:** o nome é
    resolvido aqui, contra os perfis do disco, e sai já sendo o `p.name` de uma
    linha da lista. O `==` de lá não pode mais discordar do `mesmo_slug` daqui.

    **E O MARCADOR ÓRFÃO CAI JUNTO** — perfil renomeado ou apagado por fora. O
    `resolve_boot_profile` declara na própria docstring que *"só resolve NOMES —
    não valida se o perfil carrega"*; o que ele devolve ia CRU para o REALCE DA
    LISTA e para o alvo dos gestos. Sem casar com ninguém, o nome vira `""` —
    que aqui é "não há", e a lista não acende linha nenhuma.

    **FATO ERRADO, SUBSTITUÍDO — 02/09/2026.** Aqui estava escrito que o nome
    cru ia também *"para o chip 'Perfil ativo'"*, e que a cura o levava ao
    travessão. **O chip não passa por aqui, e continua nomeando o órfão.** Ele
    é `<span class="pa-nome" data-campo="perfil">` (`10-perfis.html:1035`, nas
    duas páginas), do `topo.html`, que é das dez abas — e quem o pinta é
    `pacotes.topo()`, com `ctx.state.get("active_profile")` CRU. Medido pelo
    caminho do piloto (`pacote_da_pagina` → `normalizar` → `topo` com
    `setdefault`), dois perfis no disco e dublê de ponte:

        daemon diz              chip na tela            linhas realçadas
        "Perfil Que Ela Apagou" "Perfil Que Ela Apagou"  []
        "sackboy"               "sackboy"                ["Sackboy"]

    A segunda linha é a pior: a MESMA tela passa a dar dois nomes para a mesma
    pergunta. A cura mora no dono compartilhado (`pacotes/__init__.py`, `topo`),
    que tem de resolver o nome do mesmo jeito — **não aqui**: um pacote de aba
    que emitisse `perfil` seria o segundo dono do cabeçalho, que é o defeito
    fotografado às 04:23 de 02/09 na aba Sistema e está escrito em
    `a09_sistema.pacote`. A dívida tem régua própria, em
    `tests/unit/test_a_aba_perfis_manda_para_um_endereco_que_existe.py`.

    **LISTA VAZIA NÃO É PROVA DE ÓRFÃO — é a AUSÊNCIA de prova**, e essa
    distinção é a que impede a cura de desarmar o §P7. Só se rebaixa o nome a
    `""` quando há uma lista contra a qual conferi-lo; sem lista, o nome cru
    segue, e `ativar`/`remover` continuam recusando. Medido em 02/09/2026: sob
    o `pytest` a `conftest.py:2114` põe
    `HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1` em TODO teste, e
    `load_all_profiles()` devolve **[]** — sem esta guarda, todas as réguas
    desta aba passariam a medir o ramo vazio e a guarda de apagar o perfil que
    vale ficaria verde sem existir.

    `todos` é para quem já leu o disco neste tique: `pacote()` roda a cada
    500 ms e chama `load_all_profiles()` uma vez; ler 33 arquivos duas vezes por
    tique seria pagar de novo o que já está na mão. Os gestos chamam sem ele —
    são um clique, não um laço.
    """
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        perfil_que_esta_valendo,
    )
    from hefesto_dualsense4unix.profiles.slug import find_by_slug

    nome = str(perfil_que_esta_valendo(ctx.state).nome or "")
    if not nome:
        return ""
    if todos is None:
        from hefesto_dualsense4unix.profiles.loader import load_all_profiles

        try:
            todos = list(load_all_profiles())
        except Exception:
            # DISCO ILEGÍVEL NÃO PODE DESARMAR AS GUARDAS. Sem a lista não dá
            # para saber se o nome é órfão — e o erro seguro é o nome cru: ele
            # mantém `ativar` e `remover` recusando. Devolver `""` aqui faria a
            # falha de leitura ABRIR a porta de apagar o perfil que vale.
            return nome
    if not todos:
        return nome
    achado = find_by_slug(nome, todos)
    return str(getattr(achado, "name", "") or "") if achado is not None else ""


def _rotulo_do_remover(alvo: str) -> str:
    """"Remover", ou a PERGUNTA que a dica dela promete — sobre o alvo de AGORA.

    A dica no desenho diz *"Apaga do disco. Pergunta antes."* — e esta janela
    não tem diálogo. O `on_profile_remove` da janela estável abre um
    `gui_dialogs.confirm_delete_profile` (`profiles_actions.py:3167`), que é
    GTK e MODAL; daqui não dá para abri-lo, porque **os gestos rodam em
    thread** (`hefesto_vivo.py:520`) e GTK só aceita diálogo no laço principal.

    **FATO CADUCO, SUBSTITUÍDO — 02/09/2026.** Aqui estava escrito que *"a
    recusa do piloto não serve de pergunta: ela sai em `stderr`, no terminal,
    onde a dona não está olhando"*. **Não sai mais.** O piloto ganhou
    `_recusou_dizendo` (`hefesto_vivo.py:1074`): todo `RuntimeError` de gesto
    vira TARJA na tela — no cartão do controle quando a página tem um, e no
    `document.body` quando não tem, que é o caso desta aba. Ela some sozinha em
    `SEGUNDOS_DO_RECADO = 30.0`.

    **O RÓTULO CONTINUA SENDO A PERGUNTA, e agora por outra razão:** a tarja é
    AVISO e o rótulo é ESTADO. A tarja conta o que acabou de acontecer e vai
    embora em trinta segundos; o rótulo diz, enquanto o armamento vive, qual
    perfil o próximo clique apaga. Com só a tarja, ela leria "Apagar
    “Pragmata”?" e teria oito segundos para decidir olhando um botão que diz
    "Remover".

    O rótulo é o pedaço de tela que
    já existe, que ela está olhando no instante do clique, e que o piloto sabe
    pintar. O desenho não muda: o mockup continua escrevendo "Remover".

    **O `alvo` É A CURA DE 02/09/2026, e sem ele o botão ANUNCIAVA UM PERFIL E
    APAGAVA OUTRO.** O armamento sempre foi por perfil — `remover` exige
    `_ARMADO[0] == nome` — mas este rótulo olhava só o RELÓGIO, e por isso
    continuava perguntando pelo perfil armado depois de ela clicar noutra linha.
    **A SEQUÊNCIA, MEDIDA PASSO A PASSO** — dois perfis no disco, dublê de
    ponte, ninguém valendo. A coluna ANTES é este rótulo sem o `== alvo` (a
    mordida); a coluna DEPOIS é o de hoje:

        passo                          ANTES                      DEPOIS
        1 clicou na linha do Pragmata  "Remover"                  "Remover"
        2 CLIQUE em Remover            arma o Pragmata, levanta   igual
        3 o rótulo, no tique seguinte  "Remover “Pragmata”? …"    igual
        4 clicou na linha do Sackboy   "Remover “Pragmata”? …"    "Remover"
        5 CLIQUE em Remover            arma o SACKBOY, levanta    igual
        6 o rótulo, no tique seguinte  "Remover “Sackboy”? …"     igual
        7 CLIQUE em Remover            APAGA o Sackboy            igual

    **UM ÚNICO PASSO DIFERE, e é o 4 — o defeito inteiro está ali:** o botão
    anuncia que o próximo clique apaga o Pragmata, e o próximo clique arma o
    Sackboy.

    **FATO ERRADO, SUBSTITUÍDO — 02/09/2026.** Aqui estava escrito *"três
    cliques num botão que nunca deixou de dizer 'Pragmata' apagam o Sackboy"*, e
    que o passo 5 armava *"calado"*. A medição acima derruba as duas: no passo
    6, **ainda sem a cura**, o rótulo já diz "Sackboy" — dentro de um tique de
    500 ms —, então o clique que APAGA nunca acontece sob um botão dizendo
    "Pragmata". E o "calado" é o que menos se sustenta hoje: com
    `_recusou_dizendo` no piloto, o passo 5 **põe a frase em TARJA na tela**, e
    o rótulo fala meio segundo depois. Exagerar o defeito não o torna mais real,
    e a próxima pessoa leria isto como o enunciado.

    Com o alvo, o rótulo volta a "Remover" no instante em que ela troca de
    linha — que é a verdade: o próximo clique naquele botão ARMA, não apaga.
    """
    if (_ARMADO and _ARMADO[0] == alvo
            and (time.monotonic() - _ARMADO[1]) < SEGUNDOS_PARA_CONFIRMAR):
        return f"Remover “{_ARMADO[0]}”? Clique de novo"
    return "Remover"


@registrar("10-perfis.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    """DELEGA para `app/actions/perfis_web.pacote_da_aba` — a camada do PRODUTO.

    ELA JÁ EXISTIA E NUNCA TINHA SIDO LIGADA. O `casa-sabe` a listava como
    promessa sem caminho: `perfis_web.pacote_da_aba` não tinha um chamador em
    produção desde 30/08/2026.

    E ELA SABE MAIS QUE O QUE ESTE PACOTE TINHA: a coluna "Quando usar" diz *"Só
    neste programa"* onde eu escrevia *"Jogo"*; ela traz `com_ajuste` ("0 de 2
    controles com ajuste próprio neste perfil"), a `guarda` dos overrides por
    controle, os `travados` e o `editor` inteiro. Cada uma dessas frases é texto
    de tela que alguém escreveu com ela, e reescrevê-las por fora seria a
    segunda verdade.

    O QUE SOBRA AQUI é o ACHATAMENTO para os `data-hef` da página, que são 77.
    """
    perfil._com_o_src()
    from hefesto_dualsense4unix.profiles.loader import load_all_profiles
    from hefesto_dualsense4unix.profiles.slug import find_by_slug

    try:
        todos = load_all_profiles()
        # O DISCO É LIDO UMA VEZ POR TIQUE, e `_valendo` recebe a lista em vez
        # de relê-la: ele resolve o nome que vale contra os perfis que existem
        # (ver a docstring dele), e são 33 arquivos a cada 500 ms.
        ativo = _valendo(ctx, todos)
        # O `editado` FALTAVA, e o editor mostrava o perfil ERRADO — corrigido
        # em 01/09/2026, ao ligar os campos. Sem ele `pacote_da_aba` cai no
        # ativo (`perfis_web.py:426`), então clicar numa linha mudava o alvo dos
        # botões e o editor ao lado continuava pintando OUTRO perfil. Enquanto
        # nenhum campo tinha gesto isso era só uma tela desalinhada; com o Nome
        # e o Nome do Jogo ligados, seria ela renomear um perfil olhando para o
        # nome de outro.
        escolhido = _escolhido([{"nome": x.name} for x in todos], ativo)
        alvo = find_by_slug(escolhido, todos)
        bruto = _tela.pacote_da_aba(todos, ativo=ativo or None,
                                    mesa=_mesa_com_rotulo(ctx.mesa), editado=alvo)
    except Exception:
        return {"sem_dono": {}, "cobertura": {"pintados": 0, "sem_dono": 1}}

    lista = bruto.get("lista") or []
    editor = bruto.get("editor") or {}
    fora = {
        "perfis.conta": bruto.get("conta", "—"),
        "perfis.com-ajuste": bruto.get("com_ajuste", ""),
        # AS TRÊS COLUNAS SÃO LISTAS, e a tela as distribui pelos blocos de
        # mesmo endereço, na ordem — sem o gerador precisar saber quantos
        # perfis ela tem.
        "perfis.linha.nome": [x.get("nome", "") for x in lista],
        "perfis.linha.prioridade": [x.get("prioridade", "") for x in lista],
        "perfis.linha.quando": [x.get("quando", "") for x in lista],
        # O `ativo` SAIU DAQUI — 02/09/2026, e ele é o achado desta correção.
        # Esta chave carregava o nome resolvido por `_valendo` e **não tinha
        # endereço em página nenhuma**: `data-(campo|papel|hef)="ativo"` dá ZERO
        # ocorrências em `interface/paginas/10-perfis.html` e zero em
        # `mockup/10-perfis.html`. O chip que ela lê é
        # `<span class="pa-nome" data-campo="perfil">` (linha 1035 das duas), e
        # quem o pinta é `pacotes.topo()` — o dono das dez abas.
        #
        # O CUSTO DE TER EXISTIDO foi uma cura declarada sobre uma tela que não
        # mudou: três réguas chamavam este valor de "o chip" e ficavam verdes
        # sem tocar o que ela vê. Ver
        # `tests/unit/test_a_aba_perfis_manda_para_um_endereco_que_existe.py`,
        # que agora cobra endereço de TODA chave emitida por esta aba.
        "quantos": len(lista),
        "travado": bool(ctx.state.get("autoswitch_locked")),
        "sem_dono": {},
    }
    # O SEPARADOR É O PONTO, e não o hífen: a página endereça
    # `editor.prioridade.dica`, e um `editor.prioridade-dica` cai no vazio. Os
    # 77 `data-hef` desta aba usam ponto do começo ao fim.
    # O EDITOR TAMBÉM: sem perfil aberto, os campos vão a travessão em vez de
    # ficar com o texto do desenho.
    for chave in ("nome", "jogo", "estilo", "ambiente"):
        fora.setdefault(f"editor.{chave}", "—")
    fora.setdefault("editor.prioridade.n", "—")
    fora.setdefault("editor.prioridade.dica", "")
    for chave, valor in editor.items():
        if not isinstance(valor, (dict, list)):
            fora[f"editor.{chave.replace('_', '.')}"] = valor
    # A BARRA NÃO RECEBE TRAVESSÃO NEM SINAL DE PORCENTO, e as duas coisas
    # seriam o mesmo estrago — medidas ao tirar este nome de `NAO_PINTAVEIS`,
    # em 02/09/2026. O `escrever()` do piloto faz
    # `el.style.width = t + '%'` (`hefesto_vivo.py`, ramo `largura`) e só conta
    # a pintura quando `el.style.width` MUDA. Um `'—'` vira `'—%'` e um `'45%'`
    # vira `'45%%'`: as duas são CSS inválido, o navegador as recusa, a largura
    # fica no 90% do desenho — e como `el.style.width` nunca volta igual ao que
    # se escreveu, o contador soma +1 por tique, PARA SEMPRE. Um contador que
    # mente é pior que uma barra parada: ele é O instrumento com que esta casa
    # prova que um endereço existe.
    #
    # A CASA JÁ TINHA A CONVENÇÃO, e é número puro: `a03_gatilhos:394` manda
    # `aj["pct"]`, que é um `round(...)` inteiro (`:325`). Quem destoa é o
    # `perfis_web._pacote_do_editor:324`, que formata `f"{pct:.0f}%"` — e destoa
    # sem custo desde 30/08 justamente porque este campo NUNCA foi pintado.
    # O `%` fica lá: `prioridade` é valor do PRODUTO, e o produto o descreve com
    # o sinal. Quem tira a casca é este achatamento, que é o que ele faz.
    fora["editor.prioridade"] = str(editor.get("prioridade") or "0").rstrip("%")

    # OS TRÊS CAMPOS QUE SE PINTAM UMA VEZ SÓ — e a razão é medida, não gosto.
    # Ver `_uma_vez_so`: repintar um `<input>` a cada 500 ms apagaria o que ela
    # está digitando na segunda tecla.
    for chave in _uma_vez_so(str(getattr(alvo, "name", ""))):
        fora.pop(chave, None)

    # O RÓTULO DO REMOVER, e ele é a pergunta que a dica dela promete. Sai daqui
    # e não do JS porque o armamento vive no Python (ver o gesto `remover`).
    #
    # ELE RECEBE O ALVO, e o `escolhido` daqui é o MESMO nome que
    # `_perfil_do_editor` devolve ao gesto: os dois são `_ESCOLHIDO or` o que
    # está valendo, e `_escolhido()` acabou de sincronizar o primeiro. Sem o
    # alvo, o rótulo perguntava por um perfil e o clique agia sobre outro —
    # a medição está na docstring de `_rotulo_do_remover`.
    fora["perfis.remover"] = _rotulo_do_remover(escolhido)

    # A GUARDA são os overrides por controle — o que cada um guarda de próprio
    # neste perfil. O produto já a monta; a tela a distribui por linha.
    #
    # FATO DERRUBADO — 02/09/2026. Aqui estava escrito que *"as chaves saem
    # mesmo vazias, e é o que faz a tela APAGAR a lista do mockup quando não há
    # perfil"*. **A lista vazia não chega à tela.** `pacotes.normalizar` a
    # descarta antes do JS — `if valor and all(...)`, e um `[]` é falso —, então
    # com o disco sem perfil nenhum (ou com a mesa vazia) o `<tbody>` da guarda
    # continua mostrando os quatro controles do DESENHO. Medido com dublê de
    # `load_all_profiles` devolvendo `[]`:
    #
    #     guarda.nome  = []      chega à mesa? False
    #     guarda.secao = []      chega à mesa? False
    #
    # É a oitava aparição de *a tela afirmando um controle que não está*, e a
    # cura mora no despachante (`pacotes/__init__.py`), fora do território desta
    # frente: uma lista VAZIA precisa atravessar, porque o laço do piloto já
    # sabe apagar o que sobra (`i < v.length ? v[i] : ''`). Está no relatório.
    guarda = bruto.get("guarda") or []
    if isinstance(guarda, list):
        fora["guarda.nome"] = [g.get("nome", "") for g in guarda]
        fora["guarda.id"] = [g.get("id", "") for g in guarda]
        # AS DUAS FRENTES ACRESCENTARAM AQUI, e as duas ficam: uma dá COR à barra
        # da linha (identidade), a outra faz a coluna das seções dizer a verdade
        # (ela acendia as quatro seções em todo controle, sempre). Nenhuma
        # substitui a outra — são chaves diferentes do mesmo dicionário.
        # A COR DO PLÁSTICO DA LINHA — 03/09/2026, IDENTIDADE-VEM-DE-CIMA. É a
        # barra de 3px que diz de quem é a linha, e ela era o `--plastico` do
        # DESENHO cravado no `<tr>`: enquanto o nome ao lado já vinha do
        # aparelho, a barra continuava na cor do controle do mockup.
        #
        # A LISTA SE DISTRIBUI pelas barras na ordem, e uma mesa menor que o
        # desenho deixa as barras que sobram com `''` — que APAGA a cor de
        # linha e devolve a barra ao `transparent` da classe. É o lugar vazio
        # não mostrando cor nenhuma, em vez de guardar a do mockup.
        fora["guarda.plastico"] = [g.get("plastico", "") for g in guarda]
        # OS DOIS ABAIXO CONTINUAM SENDO MONTADOS, e o `pop` do fim é quem os
        # retira. Apagar as duas linhas daria o mesmo resultado hoje e deixaria
        # OS VALORES, E NÃO AS CHAVES — 02/09/2026, e o erro só apareceu no dia
        # em que o endereço saiu de `NAO_PINTAVEIS`. `for s in g["secoes"]`
        # itera um `dict` e devolve os NOMES das seções (`"leds"`, `"triggers"`
        # …), iguais para todo perfil e para todo controle; como `ligado()` diz
        # que qualquer palavra é ligada, o alvo `classe` acenderia as quatro
        # seções nos quatro controles, sempre. O que a coluna responde é
        # *"este perfil guarda isto SÓ deste controle?"*, e a resposta é o
        # `bool` que `perfis_web._secoes_do_controle` já calculou.
        #
        # A ORDEM É O CONTRATO, porque o piloto distribui a lista pelos
        # elementos de mesmo endereço na ordem do DOM: `SECOES_POR_CONTROLE`
        # (o produtor) e `aba10.SECOES` (o desenho) têm de dizer as quatro na
        # mesma sequência. Isso não fica ao acaso — a régua é
        # `test_a_coluna_do_ajuste_proprio_acende_pela_classe.py`.
        #
        # E SÓ SAI SE A PÁGINA PUBLICADA SOUBER RECEBER — ver
        # `_a_pagina_acende_a_secao_por_classe`. Sem o `data-hef-alvo="classe"`
        # lá, escrever isto apagaria os dezesseis glifos SVG.
        if _a_pagina_acende_a_secao_por_classe():
            fora["guarda.secao"] = [
                bool(ligada)
                for g in guarda
                for ligada in (g.get("secoes") or {}).values()
            ]
        # O `guarda.linhas` CONTINUA SENDO MONTADO, e o `pop` do fim é quem o
        # retira. Apagar a linha daria o mesmo resultado hoje e deixaria
        # `NAO_PINTAVEIS` sem mordida: uma lista que não segura nada fica verde
        # para sempre e ninguém percebe quando o motivo dela caduca. Assim há
        # UM lugar que decide, e arrancá-lo faz a régua reprovar.
        fora["guarda.linhas"] = str(len(guarda))

    # OS QUE NÃO SAEM — a lista é `NAO_PINTAVEIS`, e cada nome tem lá a sua
    # linha com a medição. (Este comentário dizia "OS QUATRO" quando a lista
    # tinha três: um número escrito em dois lugares diverge no primeiro dia.)
    # Este `pop` é o último ato de propósito: `pacote_da_aba` e o laço do editor
    # acima continuam produzindo tudo — quem decide o que a PÁGINA aguenta é
    # esta lista, num lugar só, e não cada emissão espalhada pelo arquivo.
    for chave in NAO_PINTAVEIS:
        fora.pop(chave, None)

    # A LISTA INTEIRA, TROCADA DE UMA VEZ — e é a maior entrega desta aba.
    # A razão, a prova e o que chega à tela por aqui estão em `_html_da_lista`.
    #
    # AS TRÊS LISTAS ACIMA (`perfis.linha.*`) FICAM, e não são redundância: elas
    # são o caminho de VOLTA. O `blocos` só pousa se `document.querySelector`
    # achar o `<tbody>`; numa página que mude o seletor, a pintura campo a campo
    # continua enchendo as catorze linhas do desenho. Duas portas para o mesmo
    # dado não brigam — o `blocos` roda ANTES no laço do piloto, e a distribuição
    # por endereço encontra os valores já no lugar e escreve zero.
    fora["blocos"] = {SELETOR_DA_LISTA: _html_da_lista(
        lista, str(bruto.get("lista_vazia") or ""))}
    fora["cobertura"] = {"pintados": len(fora) + len(lista) * 3, "sem_dono": 0}
    return fora




# ---------------------------------------------------------------------------
# OS GESTOS — ver o exemplo comentado em `a04_iluminacao.py`
# ---------------------------------------------------------------------------
from . import gesto  # noqa: E402


@gesto("10-perfis.html", "selecionar")
def selecionar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Abrir um perfil no editor. É o clique na CÉLULA DO NOME, na lista.

    ELE NÃO FALA COM O DAEMON, e é o único desta aba que não fala — de
    propósito. Escolher uma linha não muda nada no aparelho; muda o ALVO dos
    botões ao lado, que é o que a janela estável faz no
    `on_profile_selection_changed` (`profiles_actions.py:2984`). Ligar isto ao
    `profile.switch` faria passar o mouse pela lista trocar o perfil que está
    valendo — o oposto da coluna ter um botão "Ativar".

    E ELE NÃO RESPONDE CALADO: o editor ao lado repinta no tique seguinte com a
    prioridade daquele perfil (`editor.prioridade.n`). O campo Nome ainda não
    acompanha, e o motivo está no relato — ele é um `<input>`, e a pintura
    escreve `textContent` nele, que não aparece.

    `texto` é o nome VIVO porque a célula é a mesma que a pintura escreve
    (`perfis.linha.nome`).

    FATO SUBSTITUÍDO — 02/09/2026. Aqui estava escrito que ler o
    `data-hef-perfil` da linha *"traria o nome do MOCKUP: a pintura troca o
    texto e nunca reescreve o atributo"*. **Passou a reescrever, no mesmo commit
    que escreveu a frase:** `_linha_da_lista` emite `data-hef-perfil` com o nome
    vivo e o `blocos` troca o `<tbody>` inteiro. A escolha do `texto` continua
    certa por outra razão, e é a que vale: é o `texto` que o ouvinte do piloto
    manda para TODO gesto (`hefesto_vivo.py`, `texto: alvo.textContent`) — ler
    um atributo obrigaria o piloto a saber que esta aba é especial.
    """
    global _ESCOLHIDO
    nome = str(o.get("texto") or "").strip()
    if not nome:
        raise ValueError("selecionar: o clique não trouxe o nome do perfil")
    _ESCOLHIDO = nome


@gesto("10-perfis.html", "ativar")
def ativar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Ativar o perfil selecionado na tabela. `profile.switch`.

    O NOME VEM DO TEXTO DA LINHA, e não de um `data-` novo: a tabela já mostra o
    nome, e é o nome que o `profile.switch` quer. Marcar um segundo endereço com
    o mesmo valor seria a segunda verdade que esta casa persegue.

    DUAS CORREÇÕES DE 01/09/2026, ao ligar o resto da aba — e as duas são o
    mesmo defeito, que é o botão dizer "aplicado" sem ter aplicado:

    1. **A LINHA NÃO ERA CLICÁVEL.** O gesto lê o texto da linha, mas nenhum
       elemento da lista tinha endereço — o ouvinte do piloto casa
       `[data-gesto],[data-hef-gesto],…` (`hefesto_vivo.py:190`) e a `<tr>` só
       trazia `data-hef-perfil`. Quem clicava num perfil não mandava nada; quem
       clicava no BOTÃO mandava `texto="Ativar"`, e o gesto pedia ao daemon um
       perfil chamado "Ativar". Agora a célula do nome marca `selecionar`, e o
       botão age sobre o escolhido — o `_ESCOLHIDO` vem primeiro, e o `texto`
       fica como último recurso (é o que a prova declarada exercita).
    2. **A RECUSA DO DAEMON SUMIA.** `profile_switch` devolve `False` quando ele
       não confirmou (`ipc_bridge.py:271`, ATIVAR-NAO-MENTE-01) e o retorno era
       descartado: o piloto imprimia "→ aplicado" sobre uma troca que não
       aconteceu. Levantar aqui é o que faz o botão recusar dizendo.
    """
    nome = _ESCOLHIDO or str(o.get("texto") or "").strip()
    if not nome:
        raise ValueError("ativar: escolha um perfil na lista primeiro")
    # A TERCEIRA GUARDA, e ela é POR QUE ESTE GESTO ESTAVA NA LISTA DOS
    # DEZESSEIS — 02/09/2026. O mapa o acusa de *"clicou, respondeu `aplicado`,
    # o estado do daemon não mudou"*, e a acusação está certa no FATO e errada
    # na causa: ele trocava para o perfil que JÁ ESTAVA VALENDO.
    #
    # A CADEIA, medida: `pacote()` roda a cada 500 ms e chama `_escolhido()`,
    # que grava `_ESCOLHIDO = ativo` quando ninguém clicou numa linha ainda
    # (a sincronização inicial, escrita lá de propósito). A régua de cliques
    # aciona os gestos SEM `selecionar` antes — então `ativar` sai com o nome
    # do perfil ATIVO, o daemon reaplica o mesmo arquivo, e `active_profile`
    # continua o mesmo. Nada mudou porque não havia nada a mudar.
    #
    # `mesmo_slug` e não `==`: com "Navegação" no disco e "Navegacao" no daemon
    # um `==` cru diria que são perfis diferentes e a guarda nunca pegaria
    # (R-10, `profiles/slug.py:52`) — o mesmo cuidado do "Voltar à de ontem".
    from hefesto_dualsense4unix.profiles.slug import mesmo_slug

    ativo = _valendo(ctx)
    if ativo and mesmo_slug(ativo, nome):
        raise ValueError(
            f"“{nome}” já é o perfil que está valendo. Escolha outro na lista "
            f"da esquerda e clique em Ativar — reativar o mesmo não muda nada, "
            f"e dizer “aplicado” seria mentira.")
    # `profile_switch` é do `ipc_bridge` — a mesma função que a aba Perfis da
    # GUI estável usa. Nada aqui monta payload.
    if not p.profile_switch(nome):
        raise RuntimeError(f"o Hefesto não confirmou a troca para {nome!r}")


@gesto("10-perfis.html", "voltar-a-de-ontem")
def voltar_a_de_ontem(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Desfazer a última gravação do perfil aberto. `profiles/loader.py`.

    O QUE ELE DESFAZ, e o produto já sabia fazer isto pelo terminal:
    `save_profile` copia o arquivo ANTERIOR para `profiles/.historico/<slug>/`
    a cada gravação (PERFIL-SEM-RASTRO-01, `loader.py:1230`), e
    `restaurar_do_historico` devolve a mais recente **byte a byte**
    (`loader.py:1509`). O único chamador até hoje era `profile restore` da CLI
    (`cli/cmd_profile.py:282`) — este é o segundo, e é uma tela.

    POR QUE NÃO PEDE CONFIRMAÇÃO, e é a diferença dele para o "Remover": a
    própria restauração ARQUIVA a versão atual antes de substituí-la, então
    restaurar por engano também tem volta. É o desfazer, não a perda.

    AS DUAS CHAMADAS DEPOIS DO DISCO NÃO SÃO ENFEITE:

    * `profile.switch` — **o daemon não relê JSON de perfil por conta
      própria** (PERFIL-SAVE-APPLY-01, `profiles_actions.py:3508`). Sem ele o
      arquivo volta ao que era e o controle continua com o de agora, que é o
      sintoma que ela leu como "não está salvando". Só quando o perfil restaurado
      é o que está VALENDO: reaplicar outro trocaria o perfil pelas costas dela.
    * `launch_env.refresh` — a regra pode ter mudado, e com ela o
      `steam_app_<id>.env` de antecipação. É o mesmo aviso que o Salvar e o
      Remover da janela estável mandam (`footer_actions.py:205`), e a ordem é a
      de lá: reaplicar primeiro, avisar depois.

    A COMPARAÇÃO É POR SLUG, não por string: com "Navegação" no disco e
    "Navegacao" no daemon, um `==` cru diria que são perfis diferentes e o
    reaplicar não aconteceria (R-10, `profiles/slug.py:52`).
    """
    from hefesto_dualsense4unix.profiles.loader import restaurar_do_historico
    from hefesto_dualsense4unix.profiles.slug import mesmo_slug

    nome = _ESCOLHIDO or _valendo(ctx)
    if not nome:
        raise ValueError("voltar à de ontem: escolha um perfil na lista primeiro")
    # Levanta `FileNotFoundError` quando não há versão guardada, e a frase dela
    # já diz o que houve — o histórico nasce na PRÓXIMA gravação daquele perfil.
    restaurar_do_historico(nome)
    ativo = _valendo(ctx)
    if ativo and mesmo_slug(ativo, nome):
        p.profile_switch(nome)
    p.chamar("launch_env.refresh")


# ---------------------------------------------------------------------------
# OS GESTOS QUE ESCREVEM NO DISCO — 01/09/2026, a segunda leva desta aba.
#
# O TETO CONTINUA SENDO O MESMO, e é o que dá forma a todos eles: **o daemon
# não tem `profile.save` nem `profile.delete`**. Gravar e apagar perfil roda no
# processo da janela, em `profiles/loader.py`, que é puro. Por isso cada um
# destes gestos tem a MESMA forma de três tempos:
#
#     1. escreve no disco       `save_profile` / `delete_profile`
#     2. reaplica, se for o ativo   `profile.switch` — o daemon NÃO relê JSON de
#                               perfil por conta própria (PERFIL-SAVE-APPLY-01)
#     3. avisa a antecipação    `launch_env.refresh` — a regra pode ter mudado,
#                               e com ela o `steam_app_<id>.env`
#
# A ordem é a da janela estável (`footer_actions.py:205`): reaplicar primeiro,
# avisar depois. Invertida, o refresh leria o perfil que ainda não valia.
# ---------------------------------------------------------------------------


def _perfil_do_editor(ctx: Contexto) -> str:
    """O perfil em que o editor está aberto. Vazio é RECUSA, nunca "o primeiro".

    É o mesmo alvo que `pacote()` manda pintar (`editado=`), e tem de ser: um
    gesto que agisse sobre outro perfil faria ela editar o que não está vendo.
    """
    nome = _ESCOLHIDO or _valendo(ctx)
    if not nome:
        raise ValueError("escolha um perfil na lista primeiro — a coluna da "
                         "esquerda; o editor abre na linha que você clicar.")
    return nome


#: O CAMINHO DE VOLTA do rótulo do seletor para a chave do produto. Ele é a
#: INVERSÃO de `perfis_web.AMBIENTE_DO_PRESET`, e não uma segunda tabela: o
#: dono das quatro palavras é aquele módulo, e digitá-las aqui seria a segunda
#: verdade no dia em que uma delas mudasse.
#:
#: "Estilo de Jogo" É A QUINTA OPÇÃO DO DESENHO e não está aqui — não existe
#: preset para ela (`profiles/simple_match.SIMPLE_MATCH_PRESETS` tem sete, e
#: nenhum é estilo). Cair fora desta tabela é o que faz o gesto RECUSAR
#: dizendo, em vez de gravar `MatchAny()` calado — que é o que
#: `from_simple_choice` faz com chave desconhecida (`simple_match.py:248`), e
#: seria a tela rebaixando a regra dela em silêncio.
PRESET_DO_ROTULO = {v: k for k, v in _tela.AMBIENTE_DO_PRESET.items()}


def _gravar(prof: Any, ctx: Contexto, p: Any, *, era: str = "") -> None:
    """Os três tempos: disco, reaplicar se for o ativo, avisar a antecipação.

    O CORPO MUDOU DE CASA em 01/09/2026, e a razão é que ele ganhou um SEGUNDO
    chamador: o `a06_navegacao`, que devolve os atalhos de botão ao de fábrica,
    precisa exatamente destes três tempos. Uma segunda cópia é a que esquece o
    `launch_env.refresh` no dia em que alguém mexer numa só — então o corpo foi
    para `pacotes/perfil.py`, que é o módulo que as abas já compartilham, e este
    nome fica como a porta desta aba.
    """
    perfil.gravar_e_reaplicar(prof, ctx, p, era=era)


def _nome_livre(base: str, todos: Any) -> str:
    """`base`, ou `base 2`, `base 3`… — o primeiro que não colide por SLUG.

    A colisão é por slug e não por nome à vista porque é o slug que vira nome
    de arquivo (`loader.save_profile:1419`): dois nomes que só diferem no
    acento caem no MESMO arquivo, e o segundo apagaria o primeiro sem uma
    palavra na tela — "Acao (cópia)" e "Ação (cópia)".  (noqa-acento: exemplo)
    """
    from hefesto_dualsense4unix.profiles.slug import slugify

    usados = {slugify(x.name) for x in todos}
    if slugify(base) not in usados:
        return base
    n = 2
    while slugify(f"{base} {n}") in usados:
        n += 1
    return f"{base} {n}"


def _so_mudou(o: dict[str, Any]) -> bool:
    """`False` quando o clique foi só um clique — e aí o campo não age.

    MEDIDO NO CHROME em 01/09/2026, injetando o `BOOTSTRAP` do piloto sobre o
    `layout/10-perfis.html` e trocando o `postMessage` por um coletor. Mexer
    nos quatro campos como ela mexeria produziu **treze** mensagens, e quatro
    delas são `evento=click`:

        editor.nome   tipo=input   evento=change  valor='Elden Ring BR'
        editor.jogo   tipo=input   evento=click   valor='1245620'      ← só cliquei
        editor.jogo   tipo=input   evento=change  valor='1599660'
        editor.nome   tipo=input   evento=click   valor='Elden Ring BR' ← só cliquei

    O ouvinte do piloto escuta `click` E `change` (`hefesto_vivo.py:188-200`), e
    **clicar dentro de um campo para pôr o cursor manda o valor que já estava
    lá**. Sem esta guarda, clicar no "Nome do Jogo" de um perfil em "Todos"
    faria o gesto inferir a regra e GRAVAR — uma troca de regra disparada por
    um clique que não mudou nada.

    A guarda é `!= "click"`, e não `== "change"`, de propósito: um clique de
    régua (um dicionário montado à mão, sem `evento`) tem de continuar valendo.
    """
    return str(o.get("evento") or "") != "click"


@gesto("10-perfis.html", "editor.nome")
def editor_nome(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """Renomear o perfil aberto no editor. `save_profile` + `delete_profile`.

    O VALOR VEM DE `valor`, E NÃO DE `texto` — foi a causa nomeada na primeira
    leva: *"o ouvinte manda `texto: alvo.textContent`, que num `<input>` é
    vazio"*. Desde 01/09 o clique traz o `value` do campo
    (`hefesto_vivo.py:228`) e o piloto escuta `change` além de `click`, que é o
    único evento que um campo de texto dispara com o valor novo.

    POR QUE RENOMEAR NA HORA, e não guardar num rascunho: decisão dela de
    01/09 — *"clicar na cor já deveria aplicar a cor no controle"* —, e esta aba
    não tem "Salvar" próprio (o do rodapé grava o perfil ATIVO a partir do que
    está valendo no daemon, `rodape.py:114`, e nem olha para este campo). Um
    campo que aceita texto e não guarda nada é o botão que responde calado.

    NÃO HÁ `rename` NO PRODUTO — medido: `profiles/loader.py` tem
    `save_profile`, `delete_profile`, `load_profile` e `restaurar_do_historico`,
    e nenhum renomeia. A janela estável faz a mesma dupla no Salvar, com o
    diálogo do R-10 se oferecendo para apagar o antigo. Aqui a ordem é gravar
    PRIMEIRO e apagar depois: invertida, uma falha no meio perderia o perfil.

    E O ANTIGO NÃO SOME DE VEZ: `delete_profile` arquiva a última versão em
    `profiles/.historico/<slug>/` antes do `unlink` (PERFIL-SEM-RASTRO-01,
    `loader.py:1601`). Um renomear por engano se desfaz com
    `hefesto-dualsense4unix profile restore <nome-antigo>`.

    AS DUAS RECUSAS:

    * nome vazio — apagar o campo não pode virar um arquivo `.json`;
    * nome que já é de OUTRO perfil — o `save_profile` grava por SLUG, então
      renomear "Elden Ring" para "Pragmata" gravaria por cima do Pragmata dela,
      calado. É o mesmo estrago que o `_nome_livre` evita no Duplicar.
    """
    global _ESCOLHIDO
    from hefesto_dualsense4unix.profiles.loader import (
        delete_profile,
        load_all_profiles,
        load_profile,
    )
    from hefesto_dualsense4unix.profiles.slug import slugify

    if not _so_mudou(o):
        return
    novo = str(o.get("valor") or "").strip()
    era = _perfil_do_editor(ctx)
    if not novo:
        raise ValueError("o perfil precisa de um nome — o campo ficou vazio.")
    prof = load_profile(era)
    if prof.name == novo:
        return
    troca_de_arquivo = slugify(novo) != slugify(prof.name)
    if troca_de_arquivo:
        for outro in load_all_profiles():
            if slugify(outro.name) == slugify(novo):
                raise ValueError(
                    f"já existe um perfil chamado “{outro.name}”. Escolha outro "
                    f"nome — gravar este por cima apagaria o dele.")
    _gravar(prof.model_copy(update={"name": novo}), ctx, p, era=era)
    if troca_de_arquivo:
        delete_profile(era)
    _ESCOLHIDO = novo


@gesto("10-perfis.html", "editor.ambiente")
def editor_ambiente(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Funciona em": trocar a REGRA que faz o perfil entrar. `from_simple_choice`.

    QUEM MONTA A REGRA É O PRODUTO, e não este arquivo:
    `profiles/simple_match.from_simple_choice:203` é a mesma função que o Salvar
    da janela estável usa (`profiles_actions._build_profile_from_editor`), com
    as frases de recusa já escritas em português ("Diga o número do jogo na
    Steam (ex.: 1599660)"). Montar um `MatchCriteria` aqui seria a segunda
    verdade sobre o que cada opção significa.

    O `regra_do_disco` NÃO É ENFEITE: para "Jogo da Steam" ele preserva o
    `process_name` do MESMO jogo, que ela nunca viu na tela e portanto nunca
    pediu para tirar (ESCONDER-EM-VEZ-DE-SAIR-01, `simple_match.py:382`).

    AS DUAS RECUSAS, e as duas existem para não REBAIXAR a regra dela:

    * **o seletor travado** — quando o perfil casa por uma regra que esta tela
      não sabe mostrar (`window_title_regex`, lista de classes), o produto abre
      o campo travado com a frase do que fazer (`perfis_web.py:172`). Aceitar a
      troca ali seria o defeito R-12: substituir uma regra fina por "Todos".
      MEDIDO: sete dos nove perfis de fábrica caem nesse estado.
    * **"Estilo de Jogo"** — é a quinta opção do desenho e não tem preset
      nenhum atrás. `from_simple_choice` devolve `MatchAny()` para chave
      desconhecida, sem reclamar (`simple_match.py:248`): escolher "Estilo de
      Jogo" gravaria um catch-all no lugar da regra do jogo dela, em silêncio.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile
    from hefesto_dualsense4unix.profiles.simple_match import from_simple_choice

    if not _so_mudou(o):
        return
    rotulo = str(o.get("valor") or o.get("rotulo") or "").strip()
    nome = _perfil_do_editor(ctx)
    chave = PRESET_DO_ROTULO.get(rotulo)
    if chave is None:
        raise ValueError(
            f"“{rotulo}” não é uma regra que o perfil saiba guardar. O produto "
            f"conhece {', '.join(sorted(PRESET_DO_ROTULO))} — “Estilo de Jogo” "
            f"está desenhado e não tem campo nem preset atrás dele.")
    prof = load_profile(nome)
    editor = _editor_de(prof)
    if editor.get("ambiente_travado"):
        raise ValueError(str(editor.get("ambiente_recado") or ""))
    # O NOME DO JOGO VEM DO DISCO, e não do campo ao lado: o `<input>` pode ter
    # texto que ela digitou e ainda não confirmou (o `change` só dispara quando
    # o foco sai). Ler o disco é ler o que o perfil de fato tem.
    prof.match = from_simple_choice(chave, editor.get("jogo") or "",
                                    regra_do_disco=prof.match)
    _gravar(prof, ctx, p)


@gesto("10-perfis.html", "editor.jogo")
def editor_jogo(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Nome do Jogo": o programa (ou o número da Steam) que faz o perfil entrar.

    ELE SÓ TEM EFEITO EM DUAS DAS CINCO OPÇÕES do "Funciona em":
    `from_simple_choice` só lê o `custom_name` em "game" e "steam_game"
    (`simple_match.py:236-247`). Com o seletor em "Todos" ou "Steam", o texto
    seria descartado sem uma palavra — ela digitaria o nome do jogo, veria o
    campo aceitar, e a regra continuaria a mesma.

    ENTÃO O SELETOR ANDA JUNTO, e isso desfaz um IMPASSE que eu mesmo criei e
    medi antes de entregar: com o perfil em "Todos", escolher "Jogo" no seletor
    recusava por falta de nome (`MSG_JOGO_SEM_NOME`), e digitar o nome recusava
    por o seletor estar em "Todos". **Os dois caminhos fechados, e o perfil
    preso em "Todos" para sempre.** Digitar o nome de um jogo é dizer "este
    perfil é deste jogo": o gesto grava a regra inteira, e o seletor mostra o
    resultado no tique seguinte.

    O PRODUTO JÁ FAZ ISSO, e não é invenção desta tela: o
    `_aplicar_nascimento_com_jogo` (`profiles_actions.py:3128`) chama
    `_select_radio("steam_game")` **e** preenche o campo, no mesmo gesto.

    QUAL DAS DUAS ELE ESCOLHE: `normalize_appid` decide — só dígitos (ou um
    endereço da loja, que ele sabe ler) é "Jogo da Steam"; qualquer outra coisa
    é "Jogo", com o nome do programa. E ele SÓ decide quando o seletor não
    estava numa das duas: com "Jogo" ou "Jogo da Steam" já escolhido por ela,
    a escolha dela manda — digitar "1245620" num perfil que ela pôs em "Jogo"
    não pode virar um perfil da Steam pelas costas dela.

    R-12: o nome do programa vai **como ela digitar**, sem `.lower()` — o
    matcher compara com o basename cru de `/proc/PID/exe`, e
    `Cyberpunk2077.exe` nunca casaria com `cyberpunk2077.exe`.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile
    from hefesto_dualsense4unix.profiles.simple_match import (
        from_simple_choice,
        normalize_appid,
    )

    if not _so_mudou(o):
        return
    texto = str(o.get("valor") or "").strip()
    nome = _perfil_do_editor(ctx)
    prof = load_profile(nome)
    editor = _editor_de(prof)
    if editor.get("ambiente_travado"):
        raise ValueError(str(editor.get("ambiente_recado") or ""))
    chave = PRESET_DO_ROTULO.get(str(editor.get("ambiente") or ""))
    if chave not in ("game", "steam_game"):
        chave = "steam_game" if normalize_appid(texto) is not None else "game"
    prof.match = from_simple_choice(chave, texto, regra_do_disco=prof.match)
    _gravar(prof, ctx, p)


@gesto("10-perfis.html", "detectar")
def detectar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Detectar": pegar o jogo em foco e montar a regra com ele.

    A AFIRMAÇÃO QUE ESTAVA NO PRODUTO ESTÁ ERRADA PELA METADE, e é o que
    destravou este botão. `perfis_web.DONOS_DOS_GESTOS["detectar"]` diz *"o IPC
    NÃO PUBLICA o título nem a classe"* — e daí a primeira leva o deixou sem
    dono. MEDIDO em 01/09/2026, contra o daemon `dev` desta árvore, com
    `ipc_bridge.daemon_state_full()`: das 49 chaves do `state_full`, SETE são
    de detecção de janela, e duas delas são a classe —
    `window_detect_last_class` e `window_detect_current_class`. O TÍTULO é que
    não é publicado. A janela estável já lia exatamente esta chave desde o
    PERFIL-NASCE-CERTO-01 (`profiles_actions._aplicar_nascimento_com_jogo`).

    O QUE ELE FAZ E O QUE AINDA NÃO FAZ:

    * **jogo da Steam** — a classe vem como `steam_app_<id>` e o appid sai dela
      pela fonte única do produto (`profiles/steam_app.steam_appid_from_wm_class`,
      UNIFICA-PREDICADO-01). A regra vira "Jogo da Steam" com aquele número.
    * **jogo de fora da Steam** — RECUSA DIZENDO a classe que viu. A dica dela
      promete *"funciona com jogo de qualquer lugar"* e esta metade não tem
      dono: o detector entrega uma **wm_class**, e o produto só sabe guardá-la
      como `MatchCriteria(window_class=…)`, que é uma regra que este editor não
      sabe MOSTRAR — o perfil abriria travado, com a frase de usar a linha de
      comando. Gravar isso a partir de um botão seria empurrar o perfil dela
      para fora da tela. Escrevê-la como `process_name` seria pior: é outro
      dado (o basename de `/proc/PID/exe`), e casaria por acaso.

    `last_class` ANTES de `current_class`: a primeira é a última classe ÚTIL
    vista (`launch_wrapper_dialog.py:81`) e sobrevive ao foco ir para a janela
    do Hefesto — que é exatamente o que acontece quando ela clica neste botão.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile
    from hefesto_dualsense4unix.profiles.simple_match import from_simple_choice
    from hefesto_dualsense4unix.profiles.steam_app import steam_appid_from_wm_class

    nome = _perfil_do_editor(ctx)
    classe = str(ctx.state.get("window_detect_last_class")
                 or ctx.state.get("window_detect_current_class") or "")
    appid = steam_appid_from_wm_class(classe) if classe else None
    if appid is None:
        visto = f"“{classe}”" if classe and classe != "unknown" else "nenhuma janela"
        raise ValueError(
            f"não achei jogo da Steam em foco — o detector está vendo {visto}. "
            f"Abra o jogo, deixe-o em foco por um instante e clique de novo; "
            f"para jogo de fora da Steam, a regra ainda se escreve pela linha "
            f"de comando (`hefesto-dualsense4unix profile`).")
    prof = load_profile(nome)
    prof.match = from_simple_choice("steam_game", str(appid),
                                    regra_do_disco=prof.match)
    _gravar(prof, ctx, p)


@gesto("10-perfis.html", "novo")
def novo(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Novo": um perfil em branco no disco, já com a regra do jogo em foco.

    NASCE NO DISCO, e não num rascunho, porque esta aba não tem "Salvar"
    próprio — a janela estável só PREENCHE O EDITOR (`on_profile_new:3016`) e
    quem grava é o botão seguinte. Aqui, com a ação imediata que ela pediu, o
    arquivo nasce e a lista o mostra no tique seguinte, já aberto no editor.

    A REGRA DO JOGO EM FOCO É A MESMA DO PRODUTO, e a guarda também: o
    `_aplicar_nascimento_com_jogo` (`profiles_actions.py:3088`) só age quando há
    **appid da Steam**, e devolve `False` calado no resto. É o que este gesto
    faz — com jogo da Steam em foco nasce mirando aquele jogo, sem ele nasce
    catch-all, "que é o certo para um perfil de desktop" (palavras de lá).

    O QUE ELE NÃO CARREGA, e é dívida honesta: a janela estável ainda sobe a
    prioridade acima dos catch-all (`_prioridade_acima_dos_catch_all`), e essa
    conta mora num mixin GTK que depende de widget. Este perfil nasce com a
    prioridade padrão do esquema. Ele NÃO é ativado: nascer não é passar a
    valer.
    """
    global _ESCOLHIDO
    from hefesto_dualsense4unix.profiles.loader import load_all_profiles
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
    from hefesto_dualsense4unix.profiles.simple_match import from_simple_choice
    from hefesto_dualsense4unix.profiles.steam_app import steam_appid_from_wm_class

    classe = str(ctx.state.get("window_detect_last_class")
                 or ctx.state.get("window_detect_current_class") or "")
    appid = steam_appid_from_wm_class(classe) if classe else None
    regra = (from_simple_choice("steam_game", str(appid)) if appid is not None
             else MatchAny())
    nome = _nome_livre("Novo perfil", load_all_profiles())
    _gravar(Profile(name=nome, match=regra), ctx, p)
    _ESCOLHIDO = nome


@gesto("10-perfis.html", "duplicar")
def duplicar(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Duplicar": o perfil inteiro numa cópia, e o editor abre nela.

    A DICA DELA DIZ *"Copia o perfil inteiro para o editor, com «(cópia)» no
    nome"*, e as três partes se cumprem — a última por consequência da segunda:
    a cópia nasce no disco e o `_ESCOLHIDO` passa a ser ela, então é ela que o
    editor pinta no tique seguinte.

    "O PERFIL INTEIRO" É LITERAL, e é a diferença para o defeito
    BUG-DUPLICATE-NO-CONFIG-COPY-01, que a janela estável já pagou: a cópia
    tinha só o nome trocado e o resto virava default. O `model_copy` do pydantic
    leva gatilhos, luz, vibração, alto-falante, máscara e os overrides por
    controle — tudo, menos o nome.

    E A CÓPIA NÃO É ATIVADA. Duplicar não é trocar o perfil que está valendo; a
    coluna tem um "Ativar" para isso. Por isso `_gravar` não reaplica aqui: o
    nome novo nunca é o ativo.

    O NÚMERO NO FIM ("(cópia) 2") NÃO É ENFEITE: sem ele, duplicar duas vezes o
    mesmo perfil gravaria a segunda cópia POR CIMA da primeira — `save_profile`
    escreve por slug.
    """
    global _ESCOLHIDO
    from hefesto_dualsense4unix.profiles.loader import load_all_profiles, load_profile

    era = _perfil_do_editor(ctx)
    prof = load_profile(era)
    copia = _nome_livre(f"{prof.name} (cópia)", load_all_profiles())
    _gravar(prof.model_copy(update={"name": copia}), ctx, p)
    _ESCOLHIDO = copia


@gesto("10-perfis.html", "remover")
def remover(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Remover": apagar o perfil do disco. PERGUNTA ANTES, no rótulo do botão.

    É O GESTO MAIS DESTRUTIVO DESTA ABA, e tem TRÊS guardas, nesta ordem:

    1. **precisa de um perfil escolhido.** Sem ele, `_perfil_do_editor` recusa
       — nunca "o primeiro da lista".
    2. **não age sobre o perfil que está VALENDO.** Apagar o ativo deixaria o
       daemon aplicando um arquivo que não existe mais, e o produto já tem uma
       frase para esse risco (`frase_da_remocao_do_perfil_ativo`). Aqui a
       resposta é mais curta: recusa e diz para ativar outro antes.
    3. **pergunta.** O primeiro clique ARMA e levanta; o rótulo do botão vira
       a pergunta no tique seguinte (≤500 ms) e o segundo clique, dentro de
       oito segundos, apaga. Ver `_rotulo_do_remover` para por que a pergunta
       mora no rótulo e não num diálogo.

    O ARMAMENTO É POR PERFIL: escolher outra linha e clicar em Remover não
    aproveita a confirmação da anterior — seria a pior forma de perder o perfil
    errado.

    E O APAGADO TEM VOLTA: `delete_profile` arquiva a última versão em
    `profiles/.historico/<slug>/` antes do `unlink` (PERFIL-SEM-RASTRO-01,
    `loader.py:1601`). O caminho de volta hoje é a linha de comando —
    `hefesto-dualsense4unix profile restore <nome>` —, porque o "Voltar à de
    ontem" desta aba precisa do perfil na LISTA para escolhê-lo.
    """
    global _ARMADO, _ESCOLHIDO
    from hefesto_dualsense4unix.profiles.loader import delete_profile

    nome = _perfil_do_editor(ctx)
    # A FRASE É DO PRODUTO, e não desta tela — 02/09/2026, LEI 0.
    # `frase_da_remocao_do_perfil_ativo` (`profiles_actions:633`) nasceu no §P7
    # e é o aviso do diálogo de Remover da janela estável: três parágrafos que
    # dizem o quê, por quê e o que fazer, na ordem que esta casa exige de toda
    # frase de diagnóstico. Aqui havia uma SEGUNDA verdade, escrita à mão, que
    # dizia menos — não contava que o controle segue com a cor, os gatilhos e a
    # vibração aplicados depois de o arquivo sumir.
    #
    # E ELA DECIDE MELHOR QUE UM `mesmo_slug` LOCAL: recebe o `PerfilQueVale`
    # inteiro e **cala quando a fonte é `nao_sei`** — "não sei qual está
    # valendo" e "não há nenhum valendo" são fatos diferentes, e transformar o
    # primeiro em recusa seria travar o Remover por ignorância nossa.
    #
    # O `nao_sei` É INALCANÇÁVEL DAQUI, e escrever isso é o honesto — 02/09/2026.
    # `perfil_que_esta_valendo` só o devolve quando o `state` NÃO é dicionário
    # (`houve_resposta = isinstance(state, dict)`), e `Contexto.state` é tipado
    # `dict[str, Any]` e nasce dicionário nos dois lugares onde o piloto o monta.
    # O ramo que esta aba alcança é o `nenhum`. A escolha pela função continua
    # certa — ela é o dono da frase e cobre o caso na janela GTK, que a chama sem
    # `state` —, mas ninguém deve ler isto como uma cobertura que esta aba tem.
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        frase_da_remocao_do_perfil_ativo,
        perfil_que_esta_valendo,
    )

    aviso = frase_da_remocao_do_perfil_ativo(nome, perfil_que_esta_valendo(ctx.state))
    if aviso:
        raise ValueError(aviso)
    agora = time.monotonic()
    armado = (_ARMADO and _ARMADO[0] == nome
              and (agora - _ARMADO[1]) < SEGUNDOS_PARA_CONFIRMAR)
    if not armado:
        _ARMADO = (nome, agora)
        raise RuntimeError(
            f"Apagar “{nome}” do disco? Clique em Remover de novo para "
            f"confirmar — o botão espera oito segundos.")
    _ARMADO = None
    delete_profile(nome)
    _ESCOLHIDO = ""
    # SEM `profile.switch` AQUI, de propósito: o perfil apagado não é o ativo
    # (a guarda 2 garante), então não há o que reaplicar. O `launch_env`
    # precisa saber assim mesmo — o `steam_app_<id>.env` do perfil que morreu
    # fica rançoso se ninguém avisar (DEDUP-04, `profiles_actions.py:3199`).
    p.chamar("launch_env.refresh")


def _editor_de(prof: Any) -> dict[str, Any]:
    """Os campos do editor daquele perfil, pela porta da FRENTE do produto.

    `pacote_da_aba` é a função pública de `perfis_web`, e é a mesma que
    `pacote()` chama a cada tique. Ler `_pacote_do_editor` (privada) daria o
    mesmo dicionário com uma linha a menos e um acoplamento a mais; o que se
    quer daqui é justamente o que a TELA está mostrando, e a tela chama esta.

    O `ambiente_travado` que ela devolve é a válvula do R-12 — a razão de os
    dois gestos do editor consultarem isto antes de gravar.
    """
    editor: dict[str, Any] = _tela.pacote_da_aba(
        [prof], ativo=None, editado=prof)["editor"]
    return editor


#: OS DOIS QUE CONTINUAM SEM DONO, e o motivo de cada um é MEDIDO.
#:
#:   recarregar    NÃO HÁ O QUE CHAMAR. A dica dela diz "Relê a lista do disco.
#:                 Não descarta o que está no editor ao lado" — e a lista já é
#:                 relida do disco a cada tique de 500 ms, em `pacote()`, por
#:                 `load_all_profiles()`. Ligar este botão a um `load_all` extra
#:                 seria um botão que finge trabalho que já está feito. O que
#:                 falta não é motor: é o botão sair do desenho, e isso é dela.
#:   editor.estilo NÃO EXISTE EM LUGAR NENHUM, e o produto já o declara assim:
#:                 `perfis_web.GESTOS_SEM_MOTOR["editor.estilo"]` diz *"não
#:                 existe campo de Estilo de Jogo no perfil, nem preset que o
#:                 resolva"*. Conferido em 01/09/2026: não há campo em
#:                 `profiles/schema.Profile`, não há chave em
#:                 `SIMPLE_MATCH_PRESETS` e os quinze estilos do desenho não têm
#:                 arquivo atrás. Quem lhe dá motor é a ONDA-PERFIS-04.
#:                 A TELA MENTIA, e a cura é do DESENHO — 02/09/2026. O campo
#:                 dizia "Luta" para TODO perfil, porque o desenho trazia
#:                 `<option selected>Luta</option>` e a pintura não alcançava um
#:                 `<select>` com valor vazio (ver `NAO_PINTAVEIS`). Decisão
#:                 dela, hoje: o `<select>` ganha PRIMEIRA opção com `value=""`,
#:                 texto `—`, marcada. Está feita no gerador (`aba10.py`) e mora
#:                 na BANCADA — declarada em `mockup/DIVERGENCIAS.md`, esperando
#:                 o ato de publicar DELA. Até lá, a página publicada continua
#:                 abrindo em "Luta"; o pacote parou de escrever nela nos dois
#:                 casos, que é o que impede a tela de piorar.
PONTE = {"profile_switch", "chamar"}
METODOS = {"launch_env.refresh"}


PAGINA = "10-perfis.html"
PISO_DA_ABA = 10
#: SÓ UMA PROVA DECLARADA PARA DEZ GESTOS, e a razão é estrutural, não
#: preguiça: os outros nove agem sobre o perfil ESCOLHIDO, e o `ctx` desta
#: régua é fixo — `active_profile="regua"`, sem `_ESCOLHIDO` (um gesto que
#: dependesse do estado deixado por outro teste seria pior que não ter prova).
#: FATO SUBSTITUÍDO — 02/09/2026. Aqui estava escrito que, "no mesmo lar de
#: mentira que o `conftest.py` monta", `load_all_profiles()` devolve **9
#: perfis** e que a pasta vista por `pacote()` "tem nove". **Sob o `pytest` ela
#: tem ZERO**: a `conftest.py:2114` põe
#: `HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1` em todo teste, e é esse env que
#: desliga a semeadura. A conclusão não muda — nenhum perfil se chama "regua",
#: e os nove gestos levantam antes de tocar a ponte; o que muda é que eles
#: levantam por a pasta estar VAZIA, não por o nome não estar entre nove.
#:
#: ELES FORAM PROVADOS, e não por leitura: com uma pasta de perfis DE VERDADE
#: num diretório temporário, três perfis dela copiados, e um dublê de ponte
#: igual ao desta régua — os números estão no relato desta leva, gesto a gesto,
#: com a mordida de cada um.
PROVAS: list[dict[str, Any]] = [
    {"pagina": PAGINA, "gesto": "ativar", "clique": {"texto": "Ação"},  # (noqa-acento) id
     "chama": [("profile_switch", ["Ação"], {})]},
]

#: O QUE NÃO ECOA NO `state_full`, e são NOVE dos dez. A razão é uma só e está
#: no alto deste arquivo: **o daemon não guarda perfil, o disco guarda**. Ele
#: publica `active_profile` (um nome) e mais nada sobre o conteúdo — renomear,
#: duplicar, apagar, trocar a regra do jogo, restaurar a versão de ontem: nada
#: disso aparece nas 49 chaves que ele devolve. O efeito se vê na LISTA desta
#: aba, que `pacote()` relê do disco a cada tique.
#:
#: `selecionar` é o único que não fala com ninguém, e é de propósito: escolher
#: uma linha muda o ALVO dos botões ao lado, na memória desta janela. Se
#: trocasse o perfil que está valendo, a coluna não precisaria de um "Ativar".
#:
#: E ISSO MUDA A PROVA de quase todos: eles agem sobre o perfil ESCOLHIDO, e
#: uma régua que os clicasse em ordem alfabética — sem `selecionar` antes —
#: veria nove recusas em vez de nove gestos.
SEM_ECO = ("selecionar", "editor.nome", "editor.ambiente", "editor.jogo",
           "detectar", "novo", "duplicar", "remover", "voltar-a-de-ontem")
