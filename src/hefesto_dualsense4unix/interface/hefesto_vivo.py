#!/usr/bin/env python3
"""O PILOTO ÚNICO: uma janela, as dez abas, tudo pintado pelo despachante.

DECISÃO DELA, 01/09/2026: *"melhor assim mesmo. aba a aba. igual vc falou. mas
já usando o trabalho do specs pra fazermos tudo de uma vez. já o trampo final."*
E depois: *"a única que não faremos, só deixamos o botão levando pra ela, é a de
lançadores."*

O QUE ELE SUBSTITUI, e é o motivo de existir: até aqui havia CINCO pilotos, um
por aba — `controles_vivos`, `jogar_vivo`, `conexoes_vivas`, `perfis_vivos`,
`sistema_viva`. Cada um abre a sua página e morre nela; clicar na tira levava a
uma página ESTÁTICA, o mockup sem dado. O produto que ela pediu é uma janela em
que as dez abas estão vivas e a navegação entre elas funciona.

COMO ELE SABE O QUE PINTAR: pelo nome do arquivo à vista. O `load-changed` do
WebView chega em toda carga, e o `pacotes.pacote_da_pagina()` devolve o pacote
daquela página — ou `None`, que quer dizer "esta aba ainda não tem quem a pinte"
e é diferente de um pacote vazio.

AS DUAS LÍNGUAS, e a tradução mora AQUI de propósito:

    o daemon fala `uniq`   — `d4:2f:00:00:…`, o endereço do aparelho
    o desenho fala `pref`  — `p1`, `p2`, que é o que o `data-controle` traz

As funções de pacote falam a língua do daemon, porque é dele que leem. A tela
fala a língua do desenho, porque é o mockup dela. Traduzir no pacote misturaria
as duas e faria cada aba carregar a mesa; traduzir no JS espalharia a regra por
dez páginas. Fica no piloto, que é quem já tem a mesa na mão.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import argparse
import contextlib
import dataclasses
import pathlib
import sys
import threading
import time

AQUI = pathlib.Path(__file__).resolve().parent
# A RAIZ É `parents[2]`, e o `[1]` custou dois instrumentos calados.
#
# MEDIDO EM 04/09/2026: com `AQUI` em `<árvore>/src/hefesto_dualsense4unix/
# interface`, `parents[1]` é o **`src`** — não a árvore. Logo `RAIZ / "src"`
# resolvia para `<árvore>/src/src`, que NÃO EXISTE, e:
#
#   - o `sys.path.insert` virava no-op, e o piloto importava o produto da
#     OUTRA árvore pelo `.pth` do editable install (o defeito `SRC-DESTA-
#     ARVORE-01`, aqui pela terceira porta: script rodado à mão);
#   - `PAGINA` apontava para um HTML inexistente.
#
# É a assinatura de 03/09 outra vez: **as pastas mudaram de nome e a
# aritmética não foi junto** — estes arquivos nasceram em `novo-layout/
# _ferramentas/`, onde `parents[1]` ERA a árvore.
RAIZ = AQUI.parents[2]
for _p in (str(AQUI), str(RAIZ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk  # noqa: E402

# PELO NOME DO PACOTE, e não pelo nome curto do vizinho. Eram
# `import mesa_viva` / `import pacotes`, herdados de quando esta pasta vivia em
# `layout/` e os pilotos entravam nela pelo `sys.path`. Dentro do `src/` isso
# custava caro e em silêncio: uma ferramenta que lê o código ESTÁTICO não
# resolve `import pacotes` para `hefesto_dualsense4unix.interface.pacotes`, e o
# `portao_a_casa_sabe_e_o_produto_nao_faz` chegava a **zero** módulos da interface
# alcançados a partir das bocas do produto. O portão que existe para achar a
# cura escrita e nunca ligada não enxergava a interface INTEIRA — e por isso
# acusava de dívida as camadas que ela já chama.
from hefesto_dualsense4unix.interface import (  # noqa: E402
    mesa_viva,
    monta,
    onde,
    pacotes,
    regua_do_mockup,
)
from hefesto_dualsense4unix.interface.pacotes import ponte  # noqa: E402

from hefesto_dualsense4unix.core.sysfs_leds import norm_mac  # noqa: E402
from hefesto_dualsense4unix.gui.ponte_da_tela import JanelaDaAba  # noqa: E402

#: A PRIMEIRA PÁGINA é a Jogar, que é a primeira da tira. Não é escolha de
#: gosto: é a aba que o `.desktop` dela abre.
PRIMEIRA = "01-jogar.html"

#: O tique da pintura. **100 ms — o mesmo da janela GTK**
#: (`app/constants.LIVE_POLL_INTERVAL_MS`) e o mesmo do `controles_vivos`
#: (`controles_vivos.TIQUE_MS`). As três leituras ao vivo do produto batem.
#:
#: FATO ERRADO, SUBSTITUÍDO EM 04/09/2026: esta linha dizia `500` e o comentário
#: justificava o número afirmando que *"500 ms é o mesmo do `controles_vivos`"*.
#: Não era: o `controles_vivos.py:150` sempre teve `TIQUE_MS = 100`. O número
#: errado tinha consequência medida — ela relatou *"delay absurdo em controles"*
#: olhando a aba 02, onde meio segundo de atraso separa o dedo do desenho.
#:
#: O CUSTO FOI MEDIDO ANTES DE BAIXAR, com o daemon dela vivo e dois DualSense
#: na mesa (04/09/2026, `--passear` pelas dez abas, 52 voltas):
#:
#:     custo do tique: mediana 2,92 ms · max 19,17 ms   ← as dez abas
#:     custo do tique: mediana 1,73 ms · max 23,89 ms   ← só a 02, 91 voltas
#:
#: Num orçamento de 100 ms isso é **2,9% na mediana e 19% no pico** — folga de
#: cinco vezes sobre o pior caso das dez. O tique é o mesmo laço para todas: o
#: `_tique` mede de `t0` (antes do IPC) até o fim da pintura, então o número
#: acima já inclui o `estado_do_daemon()` e o `pacote_da_pagina()`.
TIQUE_MS = 100

#: OS QUATRO LUGARES DA MESA DO DESENHO mudaram de casa em 02/09/2026: vivem em
#: `pacotes.TODOS_OS_LUGARES`, junto com a conta que os apaga
#: (`pacotes.apagar_os_lugares_sem_dono`). O acoplamento entre o molde e quem o
#: aplica tinha aqui uma régua que cobrava LITERAIS deste arquivo — e literal
#: não é comportamento: a cura morria inteira com os três literais em pé.

#: A aba que NÃO tem pacote, por decisão dela — só o botão que leva a ela.
SEM_PACOTE = {"07-lancadores.html"}

#: QUANTO TEMPO A FRASE DE RECUSA FICA NA TELA. Decisão dela, 02/09/2026, sobre
#: a recusa do microfone: *"a frase de recusa SOME depois de um tempo — ~30 s e
#: desaparece. É aviso, não estado."*
#:
#: O CANAL É UM SÓ PARA AS DEZ ABAS, então a vida da frase também é: dois
#: relógios para a mesma coisa seriam a segunda cópia da mesma regra, e a
#: segunda divergiria. Ver `Piloto._recados_para_a_tela`.
SEGUNDOS_DO_RECADO = 30.0

#: QUANTO A FRASE DE SUCESSO FICA NA TELA — D-01, 04/09/2026.
#:
#: **A decisão dela:** *"No próprio cartão, como a recusa."* Mesmo lugar, mesma
#: forma, mesmo mecanismo — o que muda é a COR e o RELÓGIO.
#:
#: E O RELÓGIO É MAIS CURTO DE PROPÓSITO. A recusa é uma coisa a resolver: ela
#: fica os 30 s que ela decidiu, porque quem a lê pode precisar de tempo para
#: entender o que fazer. O sucesso é um recibo — a informação inteira dele é
#: *"foi"*, e ela se esgota na leitura. Um recibo que fica meio minuto no cartão
#: vira estado, e a palavra dela sobre este canal é a de 02/09: **é aviso, não
#: estado**.
SEGUNDOS_DO_RECADO_DE_SUCESSO = 6.0

#: A FRASE QUE O PILOTO DIZIA QUANDO O GESTO NÃO TRAZIA UMA — MORTA em
#: 05/09/2026, decisão dela na `03-Q4`: *"nenhuma palavra nova entra na tela"*.
#:
#: Ela era `"Pronto."`, a mesma palavra que a janela GTK usa para o mesmo fato
#: (`app/actions/daemon_actions._SYSTEMCTL_OK_MSG`), e a escolha de reusá-la
#: continua certa pela D-05 — *pela função dona*. **O que morreu não é a
#: palavra: é o piloto FALAR quando não tem o que dizer.** Quem responde agora é
#: a piscada (`MS_DA_PISCADA`), e a palavra do GTK segue viva no dono dela.
#:
#: **QUEM TEM O QUE DIZER CONTINUA DIZENDO.** Um gesto que devolva
#: `{"recado": "…"}` manda a própria frase para o cartão, exatamente como antes.
#: É onde a D-12 pousa — *"o microfone ligou, mas o canal dele está mudo no
#: sistema"* é frase do dono do assunto, não do piloto.

#: QUANTO TEMPO O CAMPO FICA VERDE depois de um gesto que deu certo — 1,5 s, e
#: o número é dela (`03-Q4`, *"cerca de um segundo e meio"*).
#:
#: **Ele não é o `SEGUNDOS_DO_RECADO_DE_SUCESSO`**, e a diferença é de natureza:
#: o recado verde é frase A LER e tem 6,0 s; a piscada é sinal A VER, e um sinal
#: que dura o tempo de uma frase vira ruído. Dois números, duas coisas.
#:
#: DONO ÚNICO IMPOSSÍVEL, DUAS RÉGUAS NO LUGAR — e a forma é a mesma de
#: `dualsense_bt_audio.PRIORIDADE_SESSAO_DA_PONTE`, que convive com um `.conf`
#: do WirePlumber pelo mesmo motivo. O `BOOTSTRAP` é uma string CRUA de aspas
#: triplas, e tem de continuar sendo: **seis réguas desta casa a extraem do
#: fonte por expressão regular** para rodá-la mutilada num WebKit, e um
#: `.replace()` colado no fecho quebra a âncora delas — medido em 05/09/2026, e
#: o sintoma foram 41 erros de `SyntaxError` no bootstrap, não um vermelho
#: legível. Uma f-string também não serve: o JS é cheio de chaves.
#:
#: **E O TEXTO DESTE COMENTÁRIO É PARTE DO PROBLEMA**, o que se descobriu na
#: mesma noite: uma das seis casa sem âncora de início, e a citação LITERAL do
#: padrão que estava escrita aqui virou a PRIMEIRA ocorrência do arquivo — a
#: régua passou a extrair este comentário em vez do JS, e treze testes caíram
#: com `Unexpected token '.'`. Por isso o padrão não se escreve; descreve-se.
#:
#: Então o número vive nos dois sítios e o
#: `test_o_numero_da_piscada_e_o_mesmo_nos_dois_lados`, em
#: `tests/unit/test_o_recado_de_sucesso_pousa_no_cartao.py`, exige que sejam o
#: MESMO.
MS_DA_PISCADA = 1500

#: O QUE O PILOTO DIZ QUANDO A PÁGINA MORRE E ELE A RECARREGA.
#:
#: PROVISÓRIO — decisão dela. A sprint manda o piloto *"recarregar a página à
#: vista, com um recado no stderr e no cartão"*, e a frase precisava existir
#: para o recado existir. Ela é curta e factual de propósito: diz o que
#: aconteceu e o que foi feito, e não promete que nada se perdeu — porque o que
#: estava digitado e não salvo se perde mesmo.
FRASE_DA_PAGINA_QUE_MORREU = "A tela parou de responder e foi recarregada."

#: O QUE A GUARDA DE CARGA ACEITA. Os pilotos de uma aba só passavam o nome
#: dela — `"Controles"` — e a guarda matava a janela em qualquer outra página.
#: Aqui as DEZ são legítimas, então o esperado é o que as dez compartilham:
#:
#:     Hefesto — aba JOGAR (mockup 26/08/2026)
#:     Hefesto — aba GATILHOS (mockup 26/08/2026)
#:
#: A guarda casa por SUBSTRING, e `"Jogar"` não casa com `"aba JOGAR"` — foi o
#: que matou a primeira execução deste piloto. Continua servindo para o que ela
#: existe: uma página que NÃO é do mockup (um erro de carga, um `about:blank`)
#: não tem este título e a guarda a pega.
TITULO_DE_QUALQUER_ABA = "Hefesto — aba "


def _a_pagina_pedida(pedido: str) -> str:
    """Resolve o que veio no ``--abre`` para o nome de arquivo da página.

    ACEITA AS TRÊS FORMAS QUE ALGUÉM DIGITA, e a razão é medida: o `--abre`
    dizia só *"abrir direto numa aba"* e passava a string CRUA ao
    `onde.pagina`. `--abre 10` virava `paginas/10`, o WebKit carregava a
    página de erro dele, o piloto seguia o passeio e o relatório saía com as
    dez abas zeradas — **rc=0 sobre uma foto que dizia "No such file"**.

    * ``"10"``            → ``"10-perfis.html"``
    * ``"10-perfis"``     → ``"10-perfis.html"``
    * ``"10-perfis.html"`` → ele mesmo

    O que não casar com nenhuma página volta INTACTO — quem reprova é o
    `_ir`, que confere a existência do arquivo. Adivinhar aqui esconderia o
    erro de digitação dela dentro de uma aba que ela não pediu.
    """
    pedido = (pedido or "").strip()
    if not pedido:
        return pedido
    nomes = [caminho.name for caminho in onde.paginas(publicado=True)]
    if pedido in nomes:
        return pedido
    for nome in nomes:
        if nome == f"{pedido}.html" or nome.split("-", 1)[0] == pedido:
            return nome
    return pedido


#: O QUE CONTA COMO DONO DE UM CAMPO — e **assento não é modelo**.
#:
#: O DEFEITO foi relatado pela `ONDA5-05-02` (§4.3) e MEDIDO aqui em 06/09/2026:
#: o desenho compartilhado leva `data-controle="dualsense"`
#: (`interface/ds_limpo.svg:2`), e ali o valor é o MODELO do aparelho, não o
#: assento. O piloto resolvia o dono de um campo subindo a árvore até o primeiro
#: elemento com `data-controle` ou `data-uniq` — então todo campo de dentro do
#: `<svg>` voltava com dono `"dualsense"` em vez de `p1`..`p4`.
#:
#: E ELE NÃO ERA HIPOTÉTICO. Medido nas dez páginas publicadas e nas dez da
#: bancada: `treme-e` e `treme-d` da `05-vibracao` (alvo `classe`) moram DENTRO
#: do `<svg>`, nas colunas do p1 e do p2 — QUATRO campos por arquivo que o
#: `LER_CAMPOS` devolvia com o dono errado, e que a régua do mockup não casava
#: com a coluna que os pinta. A disciplina que segurava o resto está escrita em
#: `a04_iluminacao.banco_de_luzes` — *"nenhum `data-controle` nasce aqui"* —, e
#: disciplina não é cura: ela cobra de toda frente futura o que uma linha aqui
#: resolve.
#:
#: A LISTA É DE PERMITIDOS, e o dono dos assentos é `pacotes.TODOS_OS_LUGARES`.
#: Uma lista de proibidos (*"tudo menos `dualsense`"*) só cresceria quando
#: alguém se lembrasse — e o esquecimento é silencioso, que é a forma de defeito
#: que esta casa nomeia toda semana.
#:
#: O VAZIO ENTRA, E ESSA É A METADE QUE A SPRINT NÃO PREVIA. `data-controle=""`
#: não é um modelo: é o ESCUDO que `monta._endereco_do_chip` põe nos chips da
#: fita para dizer *"este clique não é de controle nenhum"*, e ele foi MEDIDO em
#: 05/09/2026 — sem ele, o "deu certo" de trocar do P1 para o P2 pousava no
#: cartão do P1. Tirá-lo daqui ressuscitaria aquele defeito no mesmo commit que
#: cura este.
#:
#: DONO ÚNICO IMPOSSÍVEL, RÉGUA NO LUGAR — a mesma forma de `MS_DA_PISCADA`: o
#: bootstrap e o leitor de campos são strings CRUAS que seis réguas desta casa
#: extraem do fonte por expressão regular, então nenhuma das duas pode ser
#: concatenada nem interpolada. O seletor vive escrito nelas e aqui, e
#: `test_o_seletor_do_dono_pergunta_ao_dono` exige que os três digam o mesmo.
SELETOR_DO_DONO = '[data-uniq],[data-controle=""],' + ",".join(
    f'[data-controle="{lugar}"]' for lugar in sorted(pacotes.TODOS_OS_LUGARES))

#: O QUE UM GESTO **VIVO** NÃO PODE DEVOLVER — a quarta porta é de LEITURA.
#:
#: As três primeiras são o mesmo fato de forma diferente: um `input` dispara a
#: cada TECLA, e o que estas chaves fazem custa caro dez vezes por segundo.
#:
#: * `blocos` e `fita` TROCAM HTML INTEIRO — `innerHTML` no container, `outerHTML`
#:   no nó. É o defeito que a `A-TELA-SAMBA-01` mediu em 06/09/2026: quem clicou
#:   fica com o `mousedown` num nó que já não existe. Aqui seria pior, porque o
#:   nó arrancado é o campo em que ela está DIGITANDO;
#: * `recado` e `recados` são o canal de AVISO, e ele tem prazo — 30 s a recusa,
#:   6 s o recibo. Um aviso por tecla encheria o cartão de frases que ela não
#:   pediu, e a decisão dela sobre este canal é de 02/09: *é aviso, não estado*.
#:
#: O QUE SOBRA É A CARGA DE PINTURA — `mesa`, `colunas`, `alvo`. É o vocabulário
#: que o `_deu_certo` já usa, e nenhum segundo nasce aqui.
CHAVES_QUE_O_VIVO_RECUSA = ("blocos", "fita", "recado", "recados")

#: O BOOTSTRAP: uma função de pintura, genérica, para as dez.
#:
#: Ela NÃO sabe nada de nenhuma aba — recebe endereço e valor e escreve. Toda a
#: inteligência está do lado Python, nos pacotes, que são puros e testáveis sem
#: abrir janela. Foi assim que 143 valores puderam ser medidos antes de existir
#: esta janela.
#:
#: O CONTADOR É O QUE IMPEDE O VERDE SOBRE NADA. `pintar()` devolve quantos
#: valores escreveu, e o piloto imprime. Uma aba que devolve 0 com pacote não
#: vazio é endereço que não existe na página — e é o defeito que fez a
#: `06-navegacao` publicar zero endereços em 01/09 sem ninguém ver.
BOOTSTRAP = r"""
(function(){
  window.__hef = window.__hef || {};
  // O QUE CONTA COMO LIGADO, e vale só para o alvo `classe`. A lista é a mesma
  // dos dois lados — `regua_do_mockup._ligado` repete estas nove palavras — e
  // é ela que faz o `True` do Python e o `true` do JS quererem dizer a mesma
  // coisa neste alvo. O travessão entra porque é o que o `escrever` põe no
  // lugar de um valor vazio: um lugar VAZIO da mesa apaga a classe.
  function ligado(t){
    const b = String(t).trim().toLowerCase();
    return !(b === '' || b === '—' || b === '0' || b === 'false'
             || b === 'nao' || b === 'não' || b === 'off'  // (noqa-acento) valores
             || b === 'none' || b === 'null');
  }
  // O QUE O ALVO `atributo` PODE ESCREVER, e a lista é curta de propósito.
  //
  // O NOME VEM DA PÁGINA (do `data-hef-atributo` que o gerador escreve), não do
  // daemon — então isto não é guarda contra invasor, é guarda contra ERRO DE
  // GERADOR. Sem ela, um `data-hef-atributo="style"` apagaria, no mesmo tique, o
  // `--plastico` e a `width` que os outros alvos acabaram de pintar no MESMO
  // elemento; um `class` apagaria o alvo `classe`; um `id` quebraria os `url(#…)`
  // que o `monta.svg` prefixa por controle.
  //
  // E A RAZÃO MAIS DURA É O SELO: `escrever()` carimba `data-hef-visto`, e é ele
  // que decide um INDECIDÍVEL na régua do mockup. Um alvo capaz de escrever
  // `data-hef-visto` é um alvo capaz de FORJAR a medição desta casa — por isso
  // todo o prefixo `data-hef` está fora, e não só o selo.
  //
  // Os cinco nomeados são o vocabulário de ENDEREÇO do próprio piloto (`achar()`,
  // os donos de bloco e o ouvinte de gesto): o alvo não pode reescrever a placa
  // da porta por onde ele mesmo entrou.
  //
  // `data-*` e `aria-*` é o que SOBRA, e chega para quase tudo que a lei pede: o
  // `data-colorway` do SVG, o `data-modelo`, e o `aria-label` que um leitor de
  // tela anuncia. Uma lista de proibidos, em vez desta de permitidos, teria de
  // crescer toda vez que o HTML crescer.
  //
  // O `title` É A ÚNICA EXCEÇÃO, e ela é NOMEADA — 03/09/2026. O `fim.html`, que
  // é um só para as dez páginas, pede `data-hef-alvo="atributo"
  // data-hef-atributo="title"` nos botões Salvar e Exportar, para a dica dizer o
  // NOME do perfil ativo em vez de congelar um exemplo (`7db1e0e6`). Aquele
  // commit deu por certo que este alvo "sabe escrever num `title`" — e a guarda o
  // recusava CALADA: as 20 páginas (dez publicadas, dez da bancada) pediam um
  // atributo que nunca pintava, e o único barulho veio do portão
  // `test_todo_data_hef_atributo_publicado_e_escrevivel`.
  //
  // ELE PODE ENTRAR, e as três razões da lista curta não o alcançam: `title` não
  // é `data-hef` (não forja o selo), não é vocabulário de endereço (não move a
  // placa da porta) e não é `style`/`class`/`id` (não desfaz o que outro alvo
  // acabou de pintar no mesmo elemento). É texto de dica, e nada mais.
  //
  // E ELE MUDA UMA DECISÃO DE OUTRA ABA: a dica da linha por controle da
  // `10-perfis` foi REMOVIDA em 03/09 por não haver canal de pintura
  // (`test_aba10_a_dica_da_linha_nao_e_do_mockup`, §4). O canal existe agora —
  // aquela dica pode voltar VIVA, com o modelo e a conta do aparelho.
  const ATRIBUTO_DE_ENDERECO = ['data-campo', 'data-papel', 'data-controle',
                                'data-uniq', 'data-gesto'];
  const ATRIBUTO_A_MAIS = ['title'];
  function atributo_escrevivel(n){
    if(ATRIBUTO_A_MAIS.indexOf(n) >= 0) return true;
    return /^(data|aria)-[a-z0-9]+(-[a-z0-9]+)*$/.test(n)
           && n.indexOf('data-hef') !== 0
           && ATRIBUTO_DE_ENDERECO.indexOf(n) < 0;
  }
  window.__hef.atributoEscrevivel = atributo_escrevivel;
  function escrever(el, v){
    if(!el) return 0;
    const vazio = (v === null || v === undefined || v === '');
    const t = vazio ? '—' : String(v);
    // O ALVO PADRÃO É O TEXTO. `data-hef-alvo` desvia para um atributo quando a
    // tela precisa de outra coisa — a largura de uma barra, o `value` de um
    // campo. Sem isso, pintar uma barra escreveria o número DENTRO dela.
    const alvo = el.dataset.hefAlvo || 'texto';
    // O SELO DA VISITA, e ele é O QUE DECIDE UM INDECIDÍVEL. A régua do mockup
    // lê a TELA e por isso não consegue separar "o produto pintou o mesmo valor
    // que o desenho cravou" de "ninguém tocou aqui" — eram 74 campos em 330.
    // Este selo é o único fato que a tela não mostra: o piloto ESTEVE neste
    // elemento com um valor. Ele é escrito a cada visita, mesmo quando nada
    // muda, porque é justamente a visita SEM mudança que não deixa rastro.
    //
    // ELE NÃO É "LER O CÓDIGO". A casa já se enganou lendo o fonte e publicando
    // 77% onde a tela mostrava 36%. O selo não afirma que um endereço existe no
    // pacote: ele registra que o valor emitido CHEGOU a um elemento desta
    // página — que é exatamente o degrau que faltava entre o `declarado` e o
    // `vivo`. Endereço morto continua sem selo, e continua acusado.
    //
    // E ELE SÓ ESCREVE UMA VEZ — A-TELA-SAMBA-01, 06/09/2026, e é a MAIOR
    // parcela do samba que ela relatou. `el.dataset.hefVisto = '1'` num
    // elemento que já traz `'1'` **é uma mutação de DOM**: a especificação manda
    // enfileirar um `MutationRecord` em toda troca de atributo, e não só quando
    // o valor difere. Medido com `--conta-mutacoes 100`, mesa parada:
    //
    //     01-jogar     7.100 mutações em 100 tiques — 6.700 são este selo
    //     03-gatilhos  6.400 mutações em 100 tiques — 4.700 são este selo
    //
    // O SELO NÃO PERDE NADA COM ISSO, e é o que separa esta cura de uma
    // regressão: o valor dele nunca muda — é `'1'` ou é ausência. A visita SEM
    // mudança continua deixando rastro, porque o rastro é o atributo ESTAR lá,
    // não o ato de reescrevê-lo. Quem nasce sem selo (um nó recriado por uma
    // troca de bloco) ganha o dele no tique seguinte, como sempre ganhou.
    if(el.dataset.hefVisto !== '1'){ el.dataset.hefVisto = '1'; }
    if(alvo === 'largura'){
      if(el.style.width !== t + '%'){ el.style.width = t + '%'; return 1; }
      return 0;
    }
    // O ALVO `altura` — O DÉCIMO PRIMEIRO, e ele é o gêmeo vertical do
    // `largura`. Nasceu em 05/09/2026 para as ONDAS SONORAS da aba 02: as
    // barrinhas do microfone e do alto-falante crescem em `height`, e dos dez
    // alvos que havia nenhum escrevia essa propriedade.
    //
    // POR QUE NÃO O `html` NO CONTÊINER, que era a alternativa e não custava
    // motor nenhum: a régua do mockup lê o alvo `html` **pelo texto visível**
    // (`regua_do_mockup._Leitor`, ramo `alvo in ("fundo", "html")`), e o texto
    // de catorze `<i>` vazios é vazio nos DOIS lados — desenho e produto. As
    // 56 barrinhas ficariam INDECIDÍVEIS para sempre, que é justamente o balde
    // que esta casa passou 02/09 tentando esvaziar. Com `altura` a régua lê
    // `style.height` e decide, exatamente como já decide as barras horizontais.
    //
    // E o `innerHTML` recriaria 56 nós a dez vezes por segundo; este alvo
    // escreve estilo e devolve 0 quando nada mudou, que é o que mantém o
    // contador de pinturas honesto.
    if(alvo === 'altura'){
      if(el.style.height !== t + '%'){ el.style.height = t + '%'; return 1; }
      return 0;
    }
    if(alvo === 'fundo'){
      if(el.style.background !== t){ el.style.background = t; return 1; }
      return 0;
    }
    if(alvo === 'valor'){
      // UM <select> SÓ ACEITA O QUE ELE OFERECE, e escrever nele qualquer outra
      // coisa deixa `selectedIndex = -1` e `value = ''` — o campo RENDERIZA EM
      // BRANCO e, como `el.value` nunca volta igual ao que se escreveu, o
      // contador conta uma pintura NOVA a cada tique, para sempre. Um contador
      // que mente é pior que um campo parado, e ele é O instrumento com que esta
      // casa prova que um endereço existe.
      //
      // MEDIDO em 01/09/2026: o lugar VAZIO da mesa (P2, com um controle só)
      // recebe o travessão de `dict.fromkeys(chaves, "—")`, e o `<select>` do
      // teto da vibração ficava em branco somando +1 por tique. A cura é aqui, e
      // não em cada aba lembrar-se dela — é o mesmo cuidado que
      // `gui.aba_conexoes.teto_que_vale` já tomava do lado Python.
      if(el.tagName === 'SELECT'){
        const tem = Array.prototype.some.call(el.options,
                                              function(o){ return o.value === t || o.text === t; });
        if(!tem) return 0;
      }
      // E UM <input type=range> SÓ ACEITA NÚMERO, com um desfecho PIOR que o do
      // `<select>` acima: ele não devolve vazio, ele SANEIA. Escrever o
      // travessão de um valor vazio faz o navegador trocar o `value` pelo meio
      // da escala, o polegar SALTA para um número que ninguém pediu, e como
      // `el.value` nunca volta igual ao que se escreveu o contador soma uma
      // pintura NOVA a cada tique, para sempre — que é o contador com que esta
      // casa prova que um endereço existe.
      //
      // MEDIDO NESTE MOTOR em 05/09/2026, na barra da Navegação (1..12):
      //
      //     sem esta guarda   pintar({"vel-cursor": null})  →  value "7", +1
      //                       de novo, no tique seguinte    →  value "7", +1 …
      //     com esta guarda                                 →  value "6",  0
      //
      // O CASO NÃO É HIPOTÉTICO: `a06_navegacao` emite as duas velocidades como
      // `rato.get("speed")`, e sem o bloco `mouse_emulation` no estado isso é
      // `None`. É o mesmo chão do `<select>` do teto da vibração, medido em
      // 01/09/2026, e a cura é aqui pela mesma razão: uma aba não pode ter de
      // lembrar-se dela — as três barras da Vibração ganham a mesma rede.
      //
      // ZERO É NÚMERO, e por isso a guarda é `isFinite` sobre `Number(t)` e não
      // um teste de vazio — um trilho cujo piso é 0 (as barras de motor da aba
      // Vibração) tem de aceitar o zero que o produto mandou.
      if(el.tagName === 'INPUT' && String(el.type).toLowerCase() === 'range'
         && !isFinite(Number(t))) return 0;
      if(el.value !== t){ el.value = t; return 1; }
      return 0;
    }
    // O ALVO `marcado` — O DÉCIMO, e o único que escreve `el.checked`.
    //
    // A DECISÃO DELA, 04/09/2026: opção **a**, *décimo alvo `marcado`*. O
    // acordeão do alto-falante da aba 02 é um `<input type="checkbox">` em CSS
    // puro, e o estado da saída não tinha como chegar nele: dos nove alvos, o
    // `valor` escreve `el.value` (que num checkbox é a string `"on"`, e não o
    // estado) e nenhum toca a propriedade que decide se ele está marcado.
    //
    // A LÍNGUA É `sim`, e é a mesma do alvo `classe` booleano — que é quem já
    // responde `sim` na leitura de volta (ver `LER_CAMPOS`). Uma segunda palavra
    // para o mesmo "ligado" seria a terceira maneira de dizer a mesma coisa.
    // Vazio, travessão e qualquer outra palavra DESMARCAM: o lugar sem dono da
    // mesa leva `—` (`pacotes.TRAVESSAO`), e um acordeão que abrisse sozinho num
    // lugar vazio seria a tela afirmando o que não é.
    //
    // IDEMPOTENTE COMO OS OUTROS NOVE: compara antes de mexer e devolve 0
    // quando nada mudou. Um alvo que devolve 1 sempre infla a contagem de
    // pinturas de toda aba que o use — e ela é O instrumento com que esta casa
    // prova que um endereço existe.
    //
    // ELE VALE PARA TODO CHECKBOX E RADIO das dez abas. A metade que falta é o
    // ENDEREÇO — o `data-hef-alvo="marcado"` no elemento —, e essa é da frente
    // da aba que o publicar: atributo invisível, zero pixel.
    if(alvo === 'marcado'){
      const querido = (t === 'sim');
      if(el.checked === querido) return 0;
      el.checked = querido;
      return 1;
    }
    // O ALVO `html` EXISTE PARA UM BLOCO COM MARCAÇÃO — a dica do `?` do teto
    // da vibração (`aba08.teto_dica`) traz `<b>` e `<code>` no desenho dela, e o
    // `textContent` do ramo padrão escreveria os marcadores como texto literal
    // na tela. Acrescentado em 01/09/2026.
    //
    // POR QUE NÃO O `blocos:` QUE JÁ EXISTE: aquele troca UM elemento por
    // `document.querySelector`, e o `?` do teto é um POR CONTROLE. É o mesmo
    // degrau, um tamanho menor — o endereço é `data-campo`, distribuído.
    //
    // E ELE LEMBRA O QUE ESCREVEU — A-TELA-SAMBA-01, 06/09/2026, pela MESMA
    // razão dos blocos (ver o laço `p.blocos` mais abaixo) e com o mesmo
    // mecanismo dos alvos `cor` e `plastico`. `innerHTML` de volta é a
    // SERIALIZAÇÃO do navegador, não o texto que entrou: a indentação some, o
    // atributo é reescrito com aspas duplas, a entidade vira caractere. Onde
    // uma dessas diferenças existir, `el.innerHTML !== t` é verdade para
    // sempre — e o miolo é recriado dez vezes por segundo com o mesmo desenho.
    // Medido com `--conta-mutacoes 40`, mesa parada: `luz` e `players` na
    // `04-iluminacao` (24 nós por tique) e `adaptadores-tabela` na
    // `08-conexoes`.
    if(alvo === 'html'){
      if(el.__hefHtml === t) return 0;
      if(el.innerHTML !== t){ el.innerHTML = t; el.__hefHtml = t; return 1; }
      el.__hefHtml = t;
      return 0;
    }
    // O ALVO `classe` — o ESTADO, que na tela dela é uma classe e não uma
    // palavra. Ele destrava cinco coisas que a página já desenha e o produto
    // não alcançava: qual dos quatro degraus da Vibração está aceso, o rótulo
    // `Máx` do teto, qual botão de jogador acende na Iluminação, o clique do
    // analógico e a coluna "Ajuste próprio" da Perfis.
    //
    // A SEMÂNTICA, e ela é a que os CINCO pilotos de aba já usavam — só que
    // escrita cinco vezes e nunca no piloto único:
    //
    //     cls(b, 'on', b.dataset.rota === d.alto.rota)      controles_vivos:427
    //     cls(chip, 'on', chip.dataset.mascara === d.mascara)  jogar_vivo:297
    //     cls(b, 'on', p.autostart === true)                  sistema_viva:284
    //
    // Cada elemento do grupo diz QUEM ELE É em `data-hef-quando`, e a classe
    // acende no que casar com o valor pintado. `data-hef-classe` nomeia a
    // classe (`on` por omissão).
    //
    // LIGAR UM DESLIGA AS IRMÃS, e não por lista de irmãs: os quatro degraus
    // compartilham o MESMO `data-campo`, então o `achar()` os visita todos com
    // o mesmo valor e cada um decide por si. Um segundo clique não pode deixar
    // dois acesos porque não há caminho no código em que dois casem — é a
    // diferença entre apagar o vizinho e nunca ter acendido dois.
    //
    // SEM `data-hef-quando` O ALVO É BOOLEANO — o elemento acende por si, que é
    // o caso do rótulo `Máx` e da coluna "Ajuste próprio".
    //
    // IDEMPOTENTE: compara antes de mexer e devolve 0 quando nada mudou. O
    // `cls()` dos pilotos velhos devolvia 1 SEMPRE, e um alvo assim infla a
    // contagem de pinturas de toda aba que o use — que é o instrumento com que
    // esta casa prova que um endereço existe.
    // E ELE VESTE UM ATRIBUTO JUNTO, quando o elemento pedir — 04/09/2026, e a
    // dívida foi achada pela frente da FOLHA no dia em que ela construiu o botão
    // cinza (S-03): *"nenhum alvo do `hefesto_vivo.py` escreve atributo E classe
    // no mesmo elemento, e o `aria-disabled` do botão cinza precisa disso"*.
    //
    // O PROBLEMA É REAL E É DE FORMA: `data-hef-alvo` é UM por elemento, e um
    // botão que fica cinza precisa das duas metades ao mesmo tempo — a classe,
    // que é o que a folha pinta, e o `aria-disabled`, que é o que um leitor de
    // tela anuncia. Sem as duas, ou o botão fica cinza sem dizer por quê a quem
    // não vê, ou diz e não fica cinza.
    //
    // POR QUE NÃO UM ALVO COMPOSTO, nem um segundo `data-campo`: alvo composto
    // quebraria tudo que LÊ o alvo por igualdade (o `LER_CAMPOS` aqui embaixo,
    // o `regua_do_mockup._campo`, os `campo.alvo == "…"`), e o comentário do
    // alvo `atributo` já paga essa lição. Dois endereços para o mesmo fato seria
    // pior: dois campos que podem DIVERGIR na tela, e a casa persegue o oposto.
    //
    // A VERDADE É UMA SÓ e ela mora na classe; o atributo é DERIVADO dela, na
    // língua do ARIA (`true`/`false`, que é o que a especificação exige — um
    // `aria-disabled` ausente e um `aria-disabled="false"` NÃO são a mesma coisa
    // para um leitor de tela). O nome vem do MESMO `data-hef-atributo` que o alvo
    // `atributo` já usa, e passa pela MESMA guarda: `aria-*` entra, `data-hef` e
    // o vocabulário de endereço não.
    //
    // A LEITURA DE VOLTA CONTINUA LENDO A CLASSE, de propósito: um endereço, uma
    // leitura. O atributo não é um segundo campo a medir — é a mesma verdade
    // dita para quem não enxerga a cor.
    if(alvo === 'classe'){
      const c = el.dataset.hefClasse || 'on';
      const quando = el.dataset.hefQuando;
      const aceso = (quando === undefined || quando === '') ? ligado(t) : (t === quando);
      let n = 0;
      const junto = (el.dataset.hefAtributo || '').trim().toLowerCase();
      if(junto && atributo_escrevivel(junto)){
        const querido = aceso ? 'true' : 'false';
        if(el.getAttribute(junto) !== querido){
          el.setAttribute(junto, querido);
          n += 1;
        }
      }
      if(el.classList.contains(c) === aceso) return n;
      el.classList.toggle(c, aceso);
      return n + 1;
    }
    // O ALVO `cor` — o `color` do elemento, e ele é o par que faltava do
    // `fundo`. O clique do analógico é COR na GTK
    // (`app/widgets/controller_card.py:5462`, "accent do CONTROLE quando
    // pressionados") e era cor no piloto velho desta aba
    // (`interface/controles_vivos.py:388`,
    // `{color: s.on ? 'var(--plastico)' : ''}`). Sem este alvo, o pacote da
    // aba Controles teve de escrever `[L3]` em TEXTO e deixou a razão escrita
    // em `a02_controles.py:63` — *"enquanto o piloto não tiver o alvo, o texto
    // é o canal honesto"*. Agora tem.
    //
    // ESCREVE E DEPOIS COMPARA, ao contrário dos outros alvos, e é a única
    // forma de ser idempotente aqui: o CSSOM NORMALIZA na atribuição
    // (`#6272a4` volta `rgb(98, 114, 164)` — medido no WebKit desta máquina em
    // 02/09/2026), então comparar o que se vai escrever com o que está escrito
    // acusaria mudança em TODO tique. De quebra, uma cor inválida é recusada
    // pelo CSSOM sem mexer no valor antigo, e isto devolve 0 — em vez de somar
    // uma pintura que não aconteceu.
    //
    // VAZIO APAGA a cor de linha, devolvendo o elemento à folha de estilo. É o
    // que o piloto velho fazia com `''`, e é o que faz um analógico solto
    // voltar à cor de sempre em vez de ficar aceso para sempre.
    //
    // E ESCREVER O MESMO VALOR AQUI NÃO É MUTAÇÃO — MEDIDO em 06/09/2026, na
    // A-TELA-SAMBA-01, e o resultado DERRUBOU a hipótese da sprint.
    //
    // Ela dizia que este ramo era um dos três culpados do samba, por escrever
    // antes de comparar. Escrever antes de comparar ele escreve; o que não
    // acontece é a mutação: o CSSOM só reescreve o atributo `style` quando a
    // DECLARAÇÃO muda, e atribuir a mesma cor não muda declaração nenhuma.
    // Com o observador ligado por 100 tiques e a mesa parada, este ramo não
    // produziu **uma** mutação em nenhuma das dez abas — o que a tabela acusava
    // nos elementos de cor era o SELO da visita, que é outro ramo e foi curado.
    //
    // Por isso a forma FICA como estava. Uma memória de elemento aqui — a que
    // os alvos `html` e os blocos ganharam, onde ela cura de verdade — passaria
    // por cura e não curaria nada, e a régua que a guardasse ficaria verde com
    // ela arrancada. `test_a_cor_e_o_plastico_repetidos_nao_mutam` guarda o
    // CONTRATO (o dia em que alguém trocar o CSSOM por um `setAttribute`
    // direto no `style`, ela reprova), e o docstring dela diz isso.
    if(alvo === 'cor'){
      const antes = el.style.color;
      el.style.color = vazio ? '' : t;
      return el.style.color === antes ? 0 : 1;
    }
    // O ALVO `plastico` — A COR DO APARELHO COMO VARIÁVEL, e é o que a lei de
    // 03/09/2026 pede com todas as letras: *"se identificou o controle como
    // modelo White a cor do card em volta tem que ser branco"*.
    //
    // POR QUE NÃO O `cor` NEM O `fundo`: `--plastico` não pinta UM elemento —
    // ele governa a borda da moldura E o halo do lado que treme, que é um
    // descendente. Escrever `color` obrigaria toda a coluna a herdar o tom do
    // plástico, e `background` pintaria o retângulo inteiro. Uma variável de
    // CSS é exatamente o mecanismo que o desenho já usa (`var(--plastico)` nas
    // dez páginas): o que faltava era o produto poder escrevê-la.
    //
    // VAZIO E TRAVESSÃO APAGAM — e os dois entram porque chegam por caminhos
    // diferentes: `""` é a cor que o aparelho não respondeu (pelo rádio o mapa
    // diz que ela não se lê), e `—` é o que o molde escreve num lugar sem dono
    // (`pacotes.TRAVESSAO`). Apagar devolve a borda ao tom neutro da folha de
    // estilo (`var(--plastico, …)`) em vez de deixar a cor do MOCKUP na tela —
    // regra dela: campo sem informação não mostra nada. Escrever `—` numa
    // variável usada em `border` deixaria a declaração inválida no cálculo e a
    // borda sumiria de vez.
    //
    // ESCREVE E DEPOIS COMPARA, como o `cor`: uma propriedade personalizada
    // aceita qualquer texto, então só a releitura diz se algo mudou — e é isso
    // que impede o contador de somar uma pintura que não aconteceu.
    //
    // E ELE TAMBÉM NÃO MUTA AO REPETIR — ver a nota do alvo `cor` logo acima,
    // que é a mesma medição de 06/09/2026 e a mesma hipótese derrubada:
    // `setProperty` com o mesmo valor e `removeProperty` do que já não está lá
    // não reescrevem o atributo `style`, e o observador não conta nada.
    if(alvo === 'plastico'){
      const antes = el.style.getPropertyValue('--plastico');
      if(vazio || t === '—'){ el.style.removeProperty('--plastico'); }
      else { el.style.setProperty('--plastico', t); }
      return el.style.getPropertyValue('--plastico') === antes ? 0 : 1;
    }
    // O ALVO `atributo` — UM ATRIBUTO DA TAG, e é o que faltava para o desenho
    // do controle seguir o aparelho. A lei dela, 03/09/2026: *"os svgs do
    // dualsense (…) mudam de acordo com o controle identificado no canto
    // superior. É white no p1, mas (…) os svgs não são os que o meu mapa
    // cataloga. Isso tá errado."*
    //
    // O SVG ESCOLHE A COR POR ATRIBUTO: o `monta.svg()` grava
    // `<svg data-colorway="cosmic-red">` e a folha embutida pinta as dez zonas
    // com `svg[data-colorway="…"] .z-casca{fill:var(--z-casca)}`. Havia 181
    // `data-colorway` nas dez páginas publicadas e NENHUM alcançável: dos oito
    // alvos do `escrever()`, nenhum escrevia atributo. A aba 08 desistiu com a
    // razão escrita no próprio HTML publicado (`08-conexoes.html:1033`) —
    // *"a cura certa é um alvo de atributo no piloto"*. É este.
    //
    // O NOME VEM DE `data-hef-atributo`, E NÃO DE UM `data-hef-alvo`
    // COMPOSTO. `atributo:data-colorway` no `data-hef-alvo` seria mais curto de
    // escrever e quebraria tudo que LÊ o alvo: `regua_do_mockup._campo`, o
    // `LER_CAMPOS` aqui embaixo e cada `campo.alvo == "…"` comparam o alvo por
    // IGUALDADE, e um alvo composto viraria 181 palavras diferentes onde hoje
    // há oito. O par alvo/parâmetro em atributos separados é o que o alvo
    // `classe` já faz com `data-hef-classe` e `data-hef-quando` — a casa tem a
    // forma, e inventar uma segunda seria a terceira maneira de dizer o mesmo.
    //
    // VAZIO E TRAVESSÃO APAGAM O ATRIBUTO, e a razão foi MEDIDA antes de
    // escolhida. Sem `data-colorway` nenhuma regra da folha casa, e o desenho
    // cai nos `fill` crus do `ds_limpo.svg`: 62 formas em `#3a3f4b` — um cinza
    // neutro, com o contorno intacto. Não é um SVG quebrado nem invisível: é o
    // controle SEM identidade, que é exatamente o que a regra dela pede quando
    // não há informação. Deixar o atributo faria o contrário — manteria na tela
    // o colorway do MOCKUP sobre um aparelho que é outro, que é o defeito que
    // este alvo nasceu para curar.
    //
    // ESCREVE E DEPOIS RELÊ, como o `cor` e o `plastico`: um atributo aceita
    // qualquer texto, então só a releitura diz se algo mudou. `getAttribute`
    // devolve `null` quando não há atributo, e `null === null` conta 0 — que é o
    // que impede o contador de somar uma pintura que não aconteceu ao apagar o
    // que já estava apagado.
    //
    // ELE É NECESSÁRIO E NÃO É SUFICIENTE, e quem for ligar uma aba precisa
    // saber: `monta._so_o_colorway` guarda na folha de cada SVG **só as regras
    // do modelo pedido** — 3.082 bytes dos 45.452 dos 28. Escrever aqui um
    // colorway que não está embutido dá o MESMO cinza do atributo apagado. Ou o
    // `monta.svg()` deixa de podar, ou a página publica a folha inteira uma vez.
    if(alvo === 'atributo'){
      const nome = (el.dataset.hefAtributo || '').trim().toLowerCase();
      // NOME RECUSADO NÃO PINTA E NÃO MENTE. O selo já foi carimbado acima, mas
      // a tela continua mostrando o valor velho e o pacote continua declarando
      // outro — então a régua do mockup acusa este endereço, que é o barulho
      // certo para um `data-hef-atributo` mal escrito.
      if(!atributo_escrevivel(nome)) return 0;
      const antes = el.getAttribute(nome);
      // COMPARA ANTES DE ESCREVER — A-TELA-SAMBA-01, 06/09/2026, e é a cura do
      // *"algo ativa o tooltip mas ele se desativa"* que ela escreveu com o
      // produto aberto.
      //
      // O RAMO ESCREVIA E DEPOIS RELIA, e o comentário acima explica por quê:
      // um atributo aceita qualquer texto, então só a releitura diria se algo
      // mudou. **A premissa é falsa para um atributo comum**: `setAttribute`
      // não normaliza nada, e `getAttribute` devolve exatamente a string que
      // entrou — logo comparar ANTES dá a mesma resposta sem tocar no DOM.
      //
      // E TOCAR NO DOM ERA O DEFEITO INTEIRO. `setAttribute` com o mesmo valor
      // enfileira um `MutationRecord` na mesma medida que um valor novo, e a
      // DICA NATIVA do WebKit fecha quando o `title` do elemento sob o cursor
      // muda. As dicas vivas desta casa — os `dica-modo-*` da `03-gatilhos`, o
      // `title` do Salvar e do Exportar em todas as dez — passavam por aqui
      // DEZ VEZES POR SEGUNDO: a dica abria e morria antes de ela conseguir
      // ler. Medido com `--conta-mutacoes 100`, mesa parada, na `03-gatilhos`:
      // 1.200 trocas de `title` em 100 tiques, com o texto sempre igual.
      //
      // O `null` DO `getAttribute` É O VAZIO DESTE RAMO, e por isso a
      // comparação do apagamento é contra ele: apagar o que já não existe volta
      // 0 e não escreve, como antes.
      if(vazio || t === '—'){
        if(antes === null) return 0;
        el.removeAttribute(nome);
        return 1;
      }
      if(antes === t) return 0;
      el.setAttribute(nome, t);
      return el.getAttribute(nome) === antes ? 0 : 1;
    }
    if(el.textContent !== t){
      el.textContent = t;
      // O PAINEL QUE MOSTRA O FIM. Um registro tem ordem: o que acabou de
      // acontecer é a última linha, e um painel de seis linhas que abre nas
      // seis PRIMEIRAS de oitenta mostra o mais velho — inútil para quem
      // clicou "Ver detalhes" agora. Fotografado em 01/09/2026.
      //
      // É UM ATRIBUTO, e não uma regra geral por altura: rolar todo elemento
      // que transborde mexeria em painéis onde o começo é o que importa.
      if(el.dataset.hefRolar === 'fim'){ el.scrollTop = el.scrollHeight; }
      return 1;
    }
    return 0;
  }
  // OS TRÊS VOCABULÁRIOS DE ENDEREÇO, e nenhum se aposenta. Medido em
  // 01/09/2026, nas dez páginas publicadas:
  //
  //     data-campo   oito abas          o mais novo, e o do piloto único
  //     data-papel   só a Vibração (28) um PAR com `data-lado`
  //     data-hef     só a Perfis (77)   nomes com ponto: `perfis.linha.nome`
  //
  // Cada um nasceu com o piloto da sua aba, e os pilotos ainda os usam. Trocar
  // tudo por um só renomearia 105 endereços e quebraria cinco pilotos vivos
  // para ganhar consistência de nome — o piloto único aceita os três, que é o
  // que custa uma linha aqui.
  function achar(raiz, chave){
    const esc = chave.replace(/"/g, '\\"');
    return raiz.querySelectorAll(
      '[data-campo="' + esc + '"],[data-papel="' + esc + '"],[data-hef="' + esc + '"]');
  }
  // A CARA DO AVISO, e ela REUSA a paleta das dez páginas em vez de inventar
  // cor: `--orange` é o alerta do mockup e `--elevated` é o fundo de caixa. Os
  // literais só valem se a página não definir a variável.
  const ESTILO_DO_RECADO =
    'margin:6px 0;padding:6px 9px;border-radius:6px;font-size:12px;'
    + 'line-height:1.35;pointer-events:none;'
    + 'color:var(--orange,#ffb86c);background:var(--elevated,#2b2d3a);'
    + 'border:1px solid var(--orange,#ffb86c);';
  // A COR DO SUCESSO, e ela REUSA a paleta como a da recusa: `--green` é o que
  // o mockup já usa para o que deu certo. Trocar só a cor — e não a forma, nem
  // o lugar, nem o mecanismo — é a decisão dela em uma linha: *"No próprio
  // cartão, como a recusa."* Um segundo canal para o mesmo tipo de fato é o que
  // os conflitos C-1, C-3, C-6 e C-7 recusaram no mesmo dia.
  const COR_DO_SUCESSO =
    'color:var(--green,#50fa7b);border-color:var(--green,#50fa7b);';
  //: A TARJA é o recado que não tem cartão a que pertencer — um gesto do
  //: rodapé, uma aba sem coluna de controle (`09-sistema`, `10-perfis`), ou o
  //: cartão daquele controle que não existe NESTA página.
  const ESTILO_DA_TARJA =
    'position:fixed;left:12px;right:12px;bottom:12px;z-index:9999;margin:0;';
  //: O RECADO DENTRO DE UM CARTÃO QUE É GRADE. Ver a razão inteira em
  //: `pintar_recados`: no fluxo, ele come uma célula e desloca a coluna toda.
  //: `left/right:4px` em vez de `0` para não cobrir a borda colorida do cartão,
  //: que é quem diz de quem é a coluna.
  const ESTILO_NA_GRADE =
    'position:absolute;top:4px;left:4px;right:4px;z-index:5;margin:0;';
  // O RECADO DA RECUSA — a frase do produto CHEGANDO AO CARTÃO.
  //
  // POR QUE ELE PRECISOU EXISTIR, medido em 02/09/2026 PELO CAMINHO DELA: o
  // contrato desta casa diz que `RuntimeError` é *"o produto recusou, e a frase
  // VAI PARA A TELA"*. Ela ia para a SAÍDA DE ERRO DO PROCESSO — `[gesto
  // falhou] …` no terminal de quem lançou a janela. Quem clica não lê terminal:
  // o botão respondia calado, e o segundo clique parecia o primeiro. Dois
  // cliques no 🎙 da `02-controles`, com um dublê que faz o daemon recusar: os
  // dois recusaram com a frase certa, o `desfechos` a guardou, e o DOM não tinha
  // uma letra dela.
  //
  // ELE NÃO USA ENDEREÇO DE PÁGINA, e isso é decisão: nenhuma das dez tem
  // `data-campo` de recado, e a `a04_iluminacao` já enterrou um justamente por
  // ser emitido num endereço que NENHUMA página tinha. Publicar HTML é ato
  // dela; o piloto é dono da JANELA e desenha o próprio aviso sem pedir campo a
  // ninguém.
  //
  // E ELE NÃO GANHA `data-campo`/`data-papel`/`data-hef` DE PROPÓSITO: o
  // `LER_CAMPOS` varre exatamente esses três, e um nó novo com um deles entraria
  // na conta da régua do mockup como campo da página — a régua passaria a medir
  // o próprio instrumento.
  function pintar_recados(lista){
    let n = 0;
    const vivas = [];
    // UM LUGAR POR PÁGINA, E DOIS NÃO SE DESEMPATAM POR ORDEM DO DOCUMENTO.
    //
    // O terceiro lugar do recado é declarado pela PÁGINA — um container com
    // `data-hef-recados`, e o `~=` casa por PALAVRA, então um só atributo pode
    // valer para os dois tons. Com DOIS containers declarando o mesmo tom, um
    // `querySelector` escolheria o primeiro do documento: a tela decidindo por
    // ordem de marcação, que é o defeito da lista plana (T-04, a coluna "Ajuste
    // próprio").
    //
    // ENTÃO O PILOTO RECUSA OS DOIS e cai no comportamento de sempre — cartão,
    // depois tarja. Recusar é o que faz o defeito APARECER: escolher em silêncio
    // deixaria a página errada funcionando por acaso até o dia em que a ordem
    // mudasse.
    //
    // E ELE DIZ QUAIS SÃO, em `window.__hef.faixasDemais`, por tom. Uma recusa
    // que não nomeia os dois obriga quem lê a procurar o atributo em mil linhas
    // de HTML publicado.
    //
    // A CONTA SE REFAZ A CADA CHAMADA, e não uma vez na instalação: quem
    // declara o container é um bloco de outra frente, e um bloco se troca
    // inteiro no tique (`p.blocos`). Uma leitura congelada mediria a página que
    // havia quando a janela abriu.
    const declarados = {};
    for(const f of document.querySelectorAll('[data-hef-recados]')){
      const bruto = String(f.getAttribute('data-hef-recados') || '').trim();
      for(const t of (bruto ? bruto.split(/\s+/) : [])){
        if(!declarados[t]) declarados[t] = [];
        declarados[t].push(f.id || (f.tagName.toLowerCase() + '.' + f.className));
      }
    }
    const demais = {};
    for(const t of Object.keys(declarados)){
      if(declarados[t].length > 1) demais[t] = declarados[t];
    }
    window.__hef.faixasDemais = demais;
    for(const r of lista){
      // DOIS ENDEREÇOS, E ELES NÃO SÃO O MESMO. `chave` é a IDENTIDADE do
      // aviso — o `uniq` normalizado do controle que recusou —, e é por ela
      // que este nó se reencontra entre um tique e outro. `cartao` é a COLUNA
      // em que ele pousa AGORA, resolvida contra a mesa deste tique lá no
      // Python. Endereçar o nó pela coluna foi o defeito de 02/09/2026: a
      // coluna troca de dono quando um controle sai da mesa, e a recusa de quem
      // saiu passava a aparecer no cartão de quem ficou.
      const chave = String(r.chave || '');
      const onde = String(r.cartao || '');
      // O TOM — `recusa` (o laranja de sempre) ou `sucesso` (o verde da D-01).
      // Ele viaja no recado e não numa segunda lista: um recado é UM fato, e
      // quem o depositou é quem sabe se ele deu certo.
      const tom = String(r.tom || 'recusa');
      vivas.push(chave);
      // O CARTÃO DAQUELE CONTROLE, quando ele existe NESTA página. Quando não
      // existe — outra aba, ou o controle já fora da mesa —, a frase vira tarja
      // em vez de sumir: um recado depositado e não mostrado é o mesmo silêncio
      // que esta função nasceu para curar.
      const cartao = onde
        ? document.querySelector('[data-controle="' + onde + '"],[data-uniq="' + onde + '"]')
        : null;
      // O TERCEIRO LUGAR — A FAIXA QUE A PÁGINA DECLARA. 05-Q4 dela,
      // 06/09/2026. O endereço é da PÁGINA (`data-hef-recados`), e o tom viaja
      // nele porque só o SUCESSO muda de lugar: a recusa continua no cartão.
      const faixa = demais[tom]
        ? null
        : document.querySelector('[data-hef-recados~="' + tom + '"]');
      const pai = faixa || cartao || document.body;
      let el = document.querySelector('.hef-recado[data-hef-recado="' + chave + '"]');
      // A PINTURA TROCA BLOCOS INTEIROS — a fita, a tabela de perfis, o mapa do
      // gabinete. Um recado que perdeu o pai é recriado no pai de agora, com o
      // estilo do lugar em que passou a morar.
      if(el && el.parentNode !== pai){ el.remove(); el = null; }
      if(!el){
        el = document.createElement('div');
        el.className = 'hef-recado';
        el.setAttribute('data-hef-recado', chave);
        // `role=status` é o que um leitor de tela anuncia sem roubar o foco.
        el.setAttribute('role', 'status');
        // SEM CLIQUE: o aviso mora DENTRO do cartão e o ouvinte é delegado —
        // sem isto um clique nele subiria pelo `closest` e viraria gesto.
        //
        // O CARTÃO DE LINHAS FIXAS PRECISA DA TERCEIRA FORMA, e ela nasceu de um
        // defeito FOTOGRAFADO em 04/09/2026, na aba 05: um recado inserido como
        // primeiro filho de um `[data-controle]` de linhas fixas OCUPA UMA
        // LINHA — o desenho do controle sumia, o nome caía na faixa da Força, e
        // a coluna inteira descia uma casa. O aviso que veio explicar quebrava a
        // tela que estava explicando.
        //
        // Medido no cartão da 05, com a recusa entrando pelo caminho do produto:
        //
        //     sem a cura   topo do desenho 389 -> 454   (65 px, e o recado static)
        //     com a cura   topo do desenho 389 -> 389   (não se move)
        //
        // GRID **E** FLEX, e a segunda metade custou uma medição: a primeira
        // versão desta cura cobria só `grid`, e o `.cartao` da 05 é `flex` —
        // então ela passou verde sem tocar no defeito. Nos dois o filho é
        // posicionado pela ORDEM, que é o que faz o recado empurrar.
        //
        // `block` fica de fora de propósito: ali empurrar é o fluxo normal do
        // documento, o layout aguenta, e tirar do fluxo criaria sobreposição
        // onde não havia problema.
        var foraDoFluxo = false;
        if(!faixa && cartao){
          var disp = getComputedStyle(pai).display;
          foraDoFluxo = disp === 'grid' || disp === 'inline-grid'
                     || disp === 'flex' || disp === 'inline-flex';
          if(foraDoFluxo && getComputedStyle(pai).position === 'static'){
            pai.style.position = 'relative';
          }
        }
        el.dataset.hefLugar = faixa ? 'faixa'
          : (cartao ? (foraDoFluxo ? 'grade' : 'fluxo') : 'tarja');
        if(!faixa && cartao){ pai.insertBefore(el, pai.firstChild); }
        else { pai.appendChild(el); }
        n += 1;
      }
      // O ESTILO SE REFAZ QUANDO O TOM MUDA, e não só quando o nó nasce: no
      // MESMO cartão uma recusa pode virar sucesso no clique seguinte — a chave
      // é o controle, não o desfecho. Sem esta linha o aviso trocaria de frase
      // e ficaria laranja dizendo que deu certo.
      if(el.dataset.hefTom !== tom){
        const lugar = el.dataset.hefLugar || 'tarja';
        if(lugar === 'faixa'){
          // NA FAIXA QUEM PINTA É A PÁGINA: ela já tem o desenho da linha de
          // estado, e o `data-hef-recado-classe` diz com que classes o recado
          // se veste. Uma caixa com borda do piloto ao lado das linhas da
          // faixa seriam dois desenhos para a mesma linha.
          el.className = 'hef-recado ' + (faixa.dataset.hefRecadoClasse || '');
          el.style.cssText = 'pointer-events:none;';
        } else {
          el.style.cssText = ESTILO_DO_RECADO
            + (lugar === 'grade' ? ESTILO_NA_GRADE : (lugar === 'tarja' ? ESTILO_DA_TARJA : ''))
            + (tom === 'sucesso' ? COR_DO_SUCESSO : '');
        }
        el.dataset.hefTom = tom;
        n += 1;
      }
      if(el.textContent !== r.texto){ el.textContent = r.texto; n += 1; }
    }
    for(const el of document.querySelectorAll('.hef-recado')){
      if(vivas.indexOf(el.getAttribute('data-hef-recado') || '') < 0){
        el.remove(); n += 1;
      }
    }
    return n;
  }
  // O ESTADO "EM VOO" DO BOTÃO — decisão dela, `09` [03], 04/09/2026: **o botão
  // diz que está trabalhando**, e diz DURANTE a espera, no lugar exato do
  // clique.
  //
  // O DEFEITO MEDIDO: `daemon.reload` leva **9,5 segundos** (medido no daemon
  // dela em 01/09), o gesto corre em thread para a janela não congelar, e
  // NENHUMA das dez abas tinha estado "em voo" — o clique sumia por nove
  // segundos e meio e o segundo clique parecia o primeiro. É o mesmo enunciado
  // da recusa que ia para o terminal, um degrau antes: ali a resposta existia e
  // não chegava; aqui a ESPERA não tinha como se anunciar.
  //
  // AS DUAS METADES, e a segunda é opcional de propósito:
  //
  //   a CLASSE `hef-em-voo`   sempre. Mora na folha do módulo
  //                           (`gui/ponte_da_tela.FOLHA_DA_CASA`), vale nas dez
  //                           abas sem republicar desenho, e não inventa texto.
  //   `data-hef-em-voo="…"`   quando a página publica um rótulo, ele entra no
  //                           lugar do original — *"Reaplicando…"* na `09`. O
  //                           texto continua sendo dela; o piloto só o troca.
  //
  // O ORIGINAL VOLTA INTEIRO, e por isso ele é guardado como `innerHTML` num
  // mapa, e não como texto num `data-`: os botões desta casa têm `<span>` dentro
  // (o `.pt` da fita, os ícones), e devolver `textContent` os achataria — o
  // botão voltaria da espera diferente de como entrou.
  window.__hef.voo = 0;
  window.__hef.rotulos = {};
  function em_voo(el){
    const n = String(++window.__hef.voo);
    el.setAttribute('data-hef-voo', n);
    el.classList.add('hef-em-voo');
    const dito = el.dataset.hefEmVoo;
    if(dito){
      window.__hef.rotulos[n] = el.innerHTML;
      el.textContent = dito;
    }
    return n;
  }
  // E ELE VOLTA SOZINHO. Um botão que ficasse "trabalhando" para sempre é pior
  // que um botão calado: o calado ao menos não afirma nada.
  //
  // O `querySelectorAll` E NÃO UMA REFERÊNCIA GUARDADA: entre o clique e a
  // volta, a pintura pode ter trocado o bloco inteiro (a fita, a tabela de
  // perfis, o mapa do gabinete). Uma referência apontaria para um nó que já saiu
  // do documento, e o botão que está na tela ficaria em voo para sempre. Zero
  // elementos é a resposta certa nesse caso, e o rótulo guardado é jogado fora
  // junto — senão o mapa cresce a cada gesto, para sempre.
  //
  // E O POUSO PISCA VERDE QUANDO DEU CERTO — 05/09/2026, decisão dela na
  // `03-Q4`. O `certo` chega do `finally` do piloto, que é quem sabe qual dos
  // três desfechos aconteceu; o JS não adivinha. Sem o segundo argumento, o
  // pouso continua sendo só a volta do voo — que é o que uma régua chamando
  // `voltouDoVoo(n)` à mão espera.
  //
  // A CLASSE SAI SOZINHA em MS_DA_PISCADA, e o número é dela (*"cerca de um
  // segundo e meio"*). Um campo que ficasse verde para sempre afirmaria um
  // clique de dez minutos atrás — a mesma doença do botão que fica em voo, que
  // este arquivo já nomeia acima.
  //
  // O `data-hef-voo` SAI ANTES DA PISCADA, e a ordem importa: se ele ficasse
  // até a classe apagar, o pouso seguinte acharia dois elementos com o mesmo
  // número. Por isso a retirada agendada procura pela CLASSE, não pelo número.
  window.__hef.voltouDoVoo = function(n, certo){
    const chave = String(n);
    let k = 0;
    const piscando = [];
    for(const el of document.querySelectorAll('[data-hef-voo="' + chave + '"]')){
      el.classList.remove('hef-em-voo');
      if(window.__hef.rotulos[chave] !== undefined){
        el.innerHTML = window.__hef.rotulos[chave];
      }
      el.removeAttribute('data-hef-voo');
      if(certo){ el.classList.add('hef-deu-certo'); piscando.push(el); }
      k += 1;
    }
    delete window.__hef.rotulos[chave];
    if(piscando.length){
      setTimeout(function(){
        for(const el of piscando){ el.classList.remove('hef-deu-certo'); }
      }, 1500);  // MS_DA_PISCADA — ver o portão logo abaixo do BOOTSTRAP
    }
    return k;
  };
  window.__hef.pintar = function(p){
    let n = 0;
    // O ALVO QUE A FITA ESCOLHEU. Ele NÃO conta como pintura — não há pixel
    // aqui —, e por isso `n` não sobe: um contador que subisse a cada tique
    // faria toda aba parecer inquieta, e a quietude é o que este número mede.
    //
    // ELE É REESCRITO EM TODO TIQUE de propósito: `window.__hef` morre com o
    // documento, e sem isto a escolha dela sobreviveria no Python e sumiria da
    // página na primeira troca de aba — o alvo voltaria a ser vazio sem que
    // nada na tela mudasse.
    if('alvo' in p){ window.__hef.alvoPadrao = p.alvo || ''; }
    // A FITA SE TROCA INTEIRA, e não campo a campo: o número de chips muda com
    // a mesa, e não há endereço para um chip que ainda não existe.
    if(p.fita){
      const f = document.querySelector('.fita');
      if(f){
        // O SELO SAI DA COMPARAÇÃO, e sem isto a fita se trocava A CADA TIQUE.
        // Medido em 03/09/2026: o laço abaixo escreve `data-hef-visto` nos
        // chips, o `outerHTML` do DOM passa a trazer o atributo, o texto que o
        // Python emitiu nunca o traz — e a igualdade nunca mais casava. Treze
        // tiques, treze pinturas, com a mesa parada. Um contador que mente é
        // pior que um campo parado: é O instrumento com que esta casa prova que
        // um endereço existe.
        // A INDENTAÇÃO SAI DOS DOIS LADOS, e sem isto a comparação NUNCA casa:
        // `monta.fita()` devolve o bloco com os quatro espaços com que ele
        // entra no esqueleto (`f'    <div class="fita…'`), e `outerHTML` começa
        // no `<`. Medido em 03/09/2026: treze tiques, treze trocas da fita
        // inteira, com a mesa parada — e cada troca deixava mais um nó de texto
        // de quatro espaços ao lado dela, porque `outerHTML =` insere o
        // fragmento inteiro, espaço e tudo.
        //
        // O DEFEITO É VELHO E ESTAVA DORMINDO: até hoje `_fita` devolvia `""`
        // sempre que UM controle não tinha cor — e pelo rádio nenhum tem —,
        // então o ramo quase nunca corria na mesa dela. Curar a guarda acordou
        // o contador.
        // E NUNCA COM UM CHIP EM VOO DENTRO — A-TELA-SAMBA-01, 06/09/2026, e é
        // o mesmo cuidado do laço de blocos lá embaixo, aqui no caso mais
        // extremo dele: a fita não troca o MIOLO, ela troca o próprio nó
        // (`outerHTML`), então TUDO o que está dentro dela morre junto. Os
        // chips da fita são clicáveis — são eles que escolhem o alvo —, e um
        // chip clicado veste `hef-em-voo` até o gesto responder. Sem esta
        // guarda, um chip em voo desaparece no primeiro tique, com o clique
        // dela no meio do caminho.
        const desejado = String(p.fita).trim();
        const agora = f.outerHTML.split(' data-hef-visto="1"').join('');
        if(agora !== desejado){
          if(f.querySelector('.hef-em-voo') || f.closest('.hef-em-voo')){
            window.__hef.blocosAdiados = (window.__hef.blocosAdiados || 0) + 1;
          } else {
            f.outerHTML = desejado; n += 1;
          }
        }
        // O SELO DA VISITA NOS CHIPS, e sem ele o endereço deles pareceria
        // MORTO. Os chips ganharam `data-campo` em 03/09/2026 (`monta.fita`)
        // para que a régua da identidade saiba que ali não há desenho
        // congelado — mas quem os escreve é esta troca de bloco, e não o laço
        // de campos: sem o selo, a régua do mockup os contaria como endereço
        // que ninguém pinta. Ele é escrito a cada tique, mesmo quando o HTML
        // não mudou, porque é a visita SEM mudança que não deixa rastro.
        // UMA VEZ SÓ, pela mesma razão do selo em `escrever()`: reescrever `'1'`
        // sobre `'1'` é uma mutação de DOM, e o chip da fita é clicável.
        for(const c of document.querySelectorAll('.fita [data-campo]')){
          if(c.dataset.hefVisto !== '1'){ c.dataset.hefVisto = '1'; }
        }
      }
    }
    // OS BLOCOS QUE SE TROCAM INTEIROS, e a fita acima é o primeiro deles —
    // esta é a mesma ideia, com endereço. Um bloco cujo NÚMERO DE FILHOS muda
    // com o dado não tem como ser pintado campo a campo: não há endereço para
    // um filho que ainda não existe.
    //
    // O SEGUNDO CASO É O MAPA DO GABINETE (01/09/2026): as faces e as entradas
    // são as que ELA declarou, e podem ser zero. Enquanto o bloco era estático,
    // a aba mostrava um gabinete de bancada — e os seis botões que mexem no
    // mapa não podiam ser ligados, porque clicar declararia no disco dela o
    // desenho de um exemplo.
    //
    // TROCA O MIOLO, e não o próprio nó: `outerHTML` no container mataria o
    // elemento que o seletor achou, e a próxima pintura não teria onde pousar.
    //
    // E NUNCA COM UM BOTÃO EM VOO DENTRO — A-TELA-SAMBA-01, 06/09/2026, e é a
    // cura de *"botões não funcionam"* e *"cliques não aplicam ou atrasam"*.
    //
    // O DEFEITO É DE TEMPO, e por isso régua nenhuma o via numa foto: um bloco
    // cujo HTML carregue um valor que muda a cada tique (uma contagem, uma
    // bateria, uma hora) é reconstruído DEZ VEZES POR SEGUNDO, e `innerHTML =`
    // destrói todos os descendentes. Quem clicou fica com o `mousedown` num nó
    // que já não existe — o `click` nunca completa — e o `hef-em-voo`, que é a
    // única coisa na tela dizendo *"estou trabalhando"*, some com o nó que o
    // vestia. Um gesto lento desta casa leva 9,5 s (`daemon.reload`): são 95
    // chances de o botão ser arrancado debaixo do dedo dela.
    //
    // ADIAR É A RESPOSTA CERTA, e não "trocar só o pedaço que mudou": o HTML do
    // bloco vem pronto do pacote, e casar filho a filho aqui seria escrever um
    // segundo motor de reconciliação no piloto. O voo dura o gesto; assim que
    // ele pousa, o tique seguinte aplica o bloco inteiro. O que se perde é
    // atualização de UM bloco por alguns tiques; o que se ganha é o clique.
    //
    // O CONTADOR SAI NA TABELA do `--conta-mutacoes`: um bloco que fica adiado
    // para sempre é defeito, e sem contá-lo ele seria invisível.
    // E A COMPARAÇÃO É COM O QUE ESTE LAÇO ESCREVEU, não com o `innerHTML` de
    // agora — A-TELA-SAMBA-01, 06/09/2026, e é o que fazia CINCO abas
    // reconstruírem bloco a dez vezes por segundo com a mesa parada.
    //
    // O DEFEITO É UM CICLO, e ele se fecha DENTRO do mesmo tique: o bloco entra
    // com os endereços que o pacote desenhou; o laço de campos, três passos
    // abaixo, escreve nesses endereços e carimba `data-hef-visto` em cada um;
    // o `innerHTML` do bloco passa a trazer o selo, o texto que o Python emitiu
    // nunca o traz — e a igualdade nunca mais casa. No tique seguinte o bloco é
    // reconstruído inteiro, os selos somem com os nós, e recomeça.
    //
    // **É O MESMO DEFEITO QUE A FITA JÁ TINHA MEDIDO** três dias antes (ver o
    // `split(' data-hef-visto="1"')` logo acima) — e a cura de lá nunca foi
    // trazida para cá. Medido com `--conta-mutacoes 40`, mesa parada:
    //
    //     10-perfis    4.000 mutações em 40 tiques — a lista dos 33 perfis
    //                  inteira, 132 nós por tique, dez vezes por segundo
    //     04-iluminacao  a barra de luz e os players, 24 nós por tique
    //     08-conexoes    a tabela de adaptadores
    //
    // POR QUE A MEMÓRIA E NÃO O `split` DA FITA: o selo é UM dos jeitos de o
    // DOM divergir do texto emitido, e não o único — o CSSOM normaliza cor, um
    // `style` esvaziado deixa `style=""` na tag, e o próximo alvo que nascer
    // trará a sua. Guardar o que ESTE laço escreveu compara duas strings da
    // MESMA língua e fica imune a todas elas de uma vez. É a mesma memória de
    // elemento dos alvos `cor` e `plastico`, e morre com o nó pelo mesmo
    // motivo.
    for(const [seletor, html] of Object.entries(p.blocos || {})){
      const alvo = document.querySelector(seletor);
      if(!alvo) continue;
      if(alvo.__hefBloco === html || alvo.innerHTML === html) continue;
      if(alvo.querySelector('.hef-em-voo') || alvo.closest('.hef-em-voo')){
        window.__hef.blocosAdiados = (window.__hef.blocosAdiados || 0) + 1;
        continue;
      }
      alvo.innerHTML = html;
      alvo.__hefBloco = html;
      n += 1;
    }
    // 1. OS CAMPOS DA MESA — soltos no documento, valem para a página toda.
    for(const [k, v] of Object.entries(p.mesa || {})){
      const alvos = achar(document, k);
      // UMA LISTA SE DISTRIBUI pelos elementos de mesmo endereço, na ordem.
      // É como a aba Conexões mostra os achados do exame e a Perfis a lista de
      // perfis: N blocos iguais, um por item, todos com o mesmo `data-campo`.
      // Sem isto o pacote teria de emitir `achado-0`, `achado-1`… e o gerador
      // teria de saber de antemão QUANTOS itens o exame acha.
      if(Array.isArray(v)){
        alvos.forEach(function(el, i){ n += escrever(el, i < v.length ? v[i] : ''); });
        continue;
      }
      if(v !== null && typeof v === 'object') continue;
      for(const el of alvos) n += escrever(el, v);
    }
    // 1b. OS LUGARES VAZIOS ganham a marca do desenho. `data-conectado` e a
    // classe `off` são o que o gerador escreve nos dois lugares que ela mandou
    // deixar desconectados — usar as MESMAS marcas é o que faz o produto
    // parecer o desenho, em vez de inventar um terceiro estado.
    for(const pref of (p.vazios || [])){
      for(const el of document.querySelectorAll('[data-controle="' + pref + '"]')){
        if(el.dataset.conectado !== 'nao'){  // (noqa-acento) valor do atributo
          el.dataset.conectado = 'nao'; n += 1;  // (noqa-acento) idem
        }
        if(!el.classList.contains('off')){ el.classList.add('off'); }
        // O `remove` TAMBÉM PERGUNTA ANTES — A-TELA-SAMBA-01, 06/09/2026.
        // `classList.remove` de uma classe AUSENTE reserializa o atributo
        // `class` do mesmo jeito, e cada reserialização é uma mutação: 400 por
        // 100 tiques na `01-jogar`, com a mesa parada e nenhum lugar mudando de
        // dono. O `add` acima já perguntava; faltava o irmão.
        if(el.classList.contains('alvo')){ el.classList.remove('alvo'); }
      }
    }
    // 1c. E OS LUGARES QUE TÊM DONO REABREM — o simétrico do passo acima, e
    // ele faltava. Sem esta linha a marca é de mão única: o piloto fechava o
    // cartão de um controle que sai e NUNCA o reabria quando ele voltava. Quem
    // liga o controle depois de a aba estar aberta via o cabeçalho contar `1
    // controle` e o cartão continuar em 24 px, com o travessão — o dado dela
    // chegando invisível. Só recarregar a página desfazia.
    for(const pref of (p.ocupados || [])){
      for(const el of document.querySelectorAll('[data-controle="' + pref + '"]')){
        // COMPARA COM `sim`, e não com o valor de desconectado — a diferença
        // foi medida no DOM vivo em 03/09/2026: nas abas 02, 05 e 08 o lugar
        // CHEIO nasce SEM o atributo, e a versão anterior, que só trocava um
        // valor pelo outro, deixava os três em `null`. A folha não tem como vestir de conectado
        // um lugar sobre o qual a tela não afirma nada.
        if(el.dataset.conectado !== 'sim'){
          el.dataset.conectado = 'sim'; n += 1;
        }
        // PERGUNTA ANTES — ver a nota do `alvo` no passo `1b` logo acima. Este
        // é o pior dos dois, porque roda para todo lugar OCUPADO: numa mesa de
        // dois controles são dois `class` reserializados por tique, para
        // sempre, sem que um lugar tenha mudado de dono.
        if(el.classList.contains('off')){ el.classList.remove('off'); }
      }
    }
    // 2. OS CAMPOS POR CONTROLE — dentro do bloco daquele `data-controle`.
    for(const [pref, campos] of Object.entries(p.colunas || {})){
      for(const raiz of document.querySelectorAll('[data-controle="' + pref + '"]')){
        for(const [k, v] of Object.entries(campos)){
          if(v !== null && typeof v === 'object') continue;
          for(const el of achar(raiz, k)) n += escrever(el, v);
        }
      }
    }
    // 3. OS RECADOS DE RECUSA, e eles vêm por ÚLTIMO porque os passos acima
    // trocam blocos inteiros — recriar antes seria pôr o aviso num cartão que a
    // pintura estava prestes a substituir.
    //
    // `undefined` QUER DIZER "esta carga não fala de recado", e é diferente de
    // uma lista vazia: a resposta de um gesto (`_deu_certo`) pinta o que trouxe
    // e não pode apagar o aviso que acabou de nascer. Quem manda a lista —
    // cheia ou vazia — é o tique, que é o dono do depósito.
    if(p.recados !== undefined){ n += pintar_recados(p.recados || []); }
    return n;
  };
  // O OUVINTE DE CLIQUE, e ele é UM SÓ para a página inteira. Um
  // `addEventListener` por botão seria N ouvintes a religar a cada repintura —
  // e um botão que a pintura substitua perde o seu, calado. Delegar no
  // documento sobrevive a qualquer troca de HTML, que é o que a fita faz a
  // cada mudança de mesa.
  if(!window.__hef.ouvindo){
    window.__hef.ouvindo = true;
    // O `change` ALÉM DO `click`, e ele é o que faltava para metade dos botões
    // sem dono. Um `<select>` não se "clica" no sentido útil — ele MUDA; e um
    // `<input>` de texto nunca dispara clique com o valor novo. Medido em
    // 01/09/2026: os quatro campos do editor da aba Perfis, os selects da
    // Conexões e o nome da face nova ficaram sem dono por isto, e o relato dos
    // agentes nomeia a causa uma vez por aba — *"o ouvinte manda `texto:
    // alvo.textContent`, que num `<input>` é vazio"*.
    document.addEventListener('change', function(ev){ manda_do_alvo(ev); }, true);
    document.addEventListener('click', function(ev){
      // Os quatro atributos que marcam algo CLICÁVEL nas dez páginas. Eles já
      // existiam — cada piloto de aba usava o seu.
      manda_do_alvo(ev);
    }, true);
    // E O `blur`, que é a TERCEIRA porta e faltava — achado pela frente da aba
    // 08 em 04/09/2026, e a forma do defeito é a mesma das outras duas: um
    // `contenteditable` (o apelido do adaptador) **não dispara `click` nem
    // `change`** ao perder o foco. O motor do apelido estava de pé, completo e
    // testado, e simplesmente NUNCA era acionado — o gesto existia e a tela
    // não tinha como chamá-lo.
    //
    // `blur` não borbulha, por isso a captura (`true`) é obrigatória, e não
    // uma preferência de estilo.
    //
    // A LIÇÃO É A DE 01/09, repetida com outro elemento: **o ouvinte único só
    // ouve o que alguém lembrou de ensinar a ele.** Quem puser na tela um
    // elemento novo que carregue valor confere se ele fala por uma destas três
    // portas — senão o gesto nasce mudo, e mudo dá verde em toda régua que
    // pergunte se o motor existe.
    document.addEventListener('blur', function(ev){
      if(ev.target && ev.target.isContentEditable) manda_do_alvo(ev);
    }, true);
    // E O `input`, QUE É A QUARTA PORTA — ver `manda_do_vivo` logo abaixo. Ela
    // é a única das quatro que NÃO despacha o gesto de `data-hef-gesto`, e a
    // razão é que ali o gesto grava no disco dela.
    document.addEventListener('input', function(ev){ manda_do_vivo(ev); }, true);
  }
  // A SÉRIE DO GESTO VIVO. Ela é própria e não o contador do voo: o voo carimba
  // o elemento e volta pelo `voltouDoVoo`; a série do vivo nunca toca o DOM —
  // ela só diz ao Python qual leitura é a mais nova.
  window.__hef.vivoN = window.__hef.vivoN || 0;
  function manda_do_alvo(ev){
      const alvo = ev.target.closest(
        '[data-gesto],[data-modo],[data-hef-gesto],[data-papel],[data-forca],' +
        '[data-player],[data-sensor],[data-rota],[data-mudo],[data-mic-modo],[data-v],' +
        '.r-aplicar,.r-salvar,.r-importar,.r-exportar');
      if(!alvo) return;
      const d = alvo.dataset;
      // O RODAPÉ ENDEREÇA POR CLASSE, e não por `data-`: ele mora no
      // `topo.html`, o esqueleto das dez, e um `data-gesto` ali mudaria as dez
      // páginas de uma vez. A classe `r-<nome>` já era o endereço dele no
      // `jogar_vivo.py` — este é o quarto vocabulário, e é o último.
      const doRodape = (alvo.className.match(/\br-([a-z]+)\b/) || [])[1];
      // O CARIMBO DO VOO, e ele é aplicado ANTES de a mensagem sair: a resposta
      // tem de ser do CLIQUE, não da volta do Python. O gesto atravessa uma
      // thread e o IPC; esperar por ele para dizer "estou trabalhando" seria
      // dizê-lo tarde demais — que é o defeito inteiro.
      //
      // TODO CLIQUE QUE VAI PARA O PYTHON É CARIMBADO, inclusive o que vai ser
      // recusado por não ter dono. O piloto despacha o pouso nos TRÊS desfechos
      // (aplicou, recusou, sem dono), e um botão que ficasse em voo porque o
      // gesto não existia seria a tela mentindo sobre um trabalho que ninguém
      // começou.
      manda(carga_do_alvo(
        alvo, ev, d.gesto || d.hefGesto || d.papel || doRodape || 'clique',
        em_voo(alvo)));
  }
  // A QUARTA PORTA — `data-hef-vivo`, o gesto que LÊ e não grava.
  //
  // POR QUE ELA PRECISOU EXISTIR, e o relato é da `ONDA5-10-02`: a decisão
  // 10-Q4 dela pede o rótulo do jogo *"ao vivo"*, e `input` é o único evento que
  // um campo de texto dispara a cada TECLA. As três portas de hoje despacham o
  // gesto de `data-hef-gesto` — que naquele campo é `editor.jogo`, e ele GRAVA
  // O PERFIL DELA. Ligar `input` ao mesmo atributo regravaria o `.json` a cada
  // letra digitada.
  //
  // ENTÃO O ENDEREÇO É PRÓPRIO, e é essa a peça inteira: um elemento pode
  // carregar `data-hef-vivo="<gesto>"`, e o `input` despacha ESSE gesto — nunca
  // o de `data-hef-gesto`, ainda que o mesmo elemento traga os dois.
  //
  // SEM O ATRIBUTO O `input` NÃO FAZ NADA. Nenhuma das dez abas muda de
  // comportamento por esta porta nascer: quem a usa é quem publicar o atributo,
  // e publicar é ato dela.
  //
  // ELE NÃO VESTE O `em_voo`, e é decisão: o cursor `progress` e a opacidade a
  // cada tecla seriam a tela dizendo *"trabalhando"* sobre uma leitura de
  // milissegundos — o oposto do que aquele sinal existe para dizer.
  //
  // UM VIVO EM VOO POR ELEMENTO. Cada disparo leva um número de série e a
  // identidade do elemento; o Python guarda o último e DESCARTA a resposta que
  // chegar fora de ordem. Sem isso, a leitura da tecla `1` pode voltar depois da
  // leitura de `15` e pintar o rótulo do jogo errado — e ficar assim até a
  // próxima tecla.
  function manda_do_vivo(ev){
      const alvo = ev.target.closest('[data-hef-vivo]');
      if(!alvo) return;
      const g = String(alvo.dataset.hefVivo || '').trim();
      if(!g) return;
      const o = carga_do_alvo(alvo, ev, g, '');
      // A IDENTIDADE DO ELEMENTO, e ela é o endereço que ele já tem: o
      // `data-campo`/`data-hef`/`data-papel` do próprio campo mais o dono. Dois
      // campos vivos diferentes na mesma coluna não compartilham série; dois
      // disparos do MESMO campo, sim — que é exatamente o que se quer cancelar.
      o.vivoChave = g + '|'
        + (alvo.dataset.campo || alvo.dataset.hef || alvo.dataset.papel || '')
        + '|' + String(o.controle || '');
      o.vivo = String(++window.__hef.vivoN);
      manda(o);
  }
  function carga_do_alvo(alvo, ev, gesto, voo){
      const d = alvo.dataset;
      // DE QUAL CONTROLE, e sem isto o gesto é ambíguo: a mesa tem quatro
      // colunas iguais e um "Desligar" clicado na terceira não diz em qual
      // barra de luz mexer. O `closest` sobe até o bloco do controle — é o
      // mesmo `data-controle` que a pintura usa para achar onde escrever.
      //
      // O DONO É O ASSENTO, e o seletor é uma lista de PERMITIDOS — ver
      // `SELETOR_DO_DONO` no Python, que é quem tem a razão inteira e a régua.
      // Em uma linha: o desenho compartilhado carrega o MODELO no mesmo
      // atributo, e um botão posto dentro dele chegaria aqui dizendo que o
      // controle se chama como o plástico.
      const dono = alvo.closest(
        '[data-uniq],[data-controle=""],[data-controle="p1"],[data-controle="p2"],[data-controle="p3"],[data-controle="p4"]');
      // O DATASET INTEIRO VAI JUNTO, e ele vem PRIMEIRO para que a lista
      // explícita abaixo continue mandando no que ela nomeia.
      //
      // POR QUE ISTO PRECISOU EXISTIR, medido em 02/09/2026: a lista explícita
      // tinha catorze nomes, escritos à mão, e os gestos da aba Conexões leem
      // `caminho`, `entrada` e `face` — NENHUM dos três estava nela. O botão
      // "escolher aparelho" traz `data-caminho` (o pacote o gera em
      // `a08_conexoes.py:1340`), as entradas do gabinete trazem `data-entrada`
      // no HTML publicado, e o clique chegava ao Python sem eles. Resultado:
      // SEIS gestos recusavam dizendo *"o clique não disse qual aparelho"* — e
      // recusavam para ELA também, não só para a régua. O diagnóstico que
      // circulava era outro: que faltava dizer em qual CONTROLE agir. Não é o
      // controle; é o argumento do próprio botão.
      //
      // UMA LISTA ESCRITA À MÃO DE ATRIBUTOS QUE A PÁGINA PODE TER É A MESMA
      // FORMA DE DEFEITO QUE ESTA CASA JÁ NOMEOU: ela só cresce quando alguém
      // se lembra, e o esquecimento é silencioso. O dataset inteiro não
      // esquece — e o custo é uma cópia de meia dúzia de strings por clique.
      const tudo = Object.assign({}, d);
      return Object.assign(tudo, {
        voo: voo,
        gesto: gesto,
        // A MARCA DO VIVO NASCE VAZIA AQUI, e quem a preenche é o
        // `manda_do_vivo`. Sem esta linha, uma página que um dia escrevesse
        // `data-vivo` num botão faria um CLIQUE cair no caminho do gesto vivo —
        // sem voo, sem recado e com a guarda de gravação por cima. É a mesma
        // razão de a lista explícita vir depois do dataset, um risco abaixo:
        // aqui o defeito seria calado.
        vivo: '', vivoChave: '',
        modo: d.modo || '', forca: d.forca || '', player: d.player || '',
        lado: d.lado || '', campo: d.campo || '', hef: d.hef || '',
        hex: d.hex || '', sensor: d.sensor || '', rota: d.rota || '',
        mudo: d.mudo || '', micModo: d.micModo || '', v: d.v || '',
        // O ALVO PADRÃO — O CONTROLE QUE A FITA APONTOU.
        //
        // FATO SUBSTITUÍDO EM 06/09/2026, e ele estava aqui desde que a fita
        // aprendeu a escolher. Esta linha dizia que o alvo padrão *"é da RÉGUA —
        // no produto fica indefinido"*. **Não fica**: o tique escreve
        // `carga["alvo"]` nas abas cuja fita ESCOLHE, e o `pintar` o guarda em
        // `window.__hef.alvoPadrao` (ver a nota do `carga["alvo"]` no `_tique`).
        // No produto, um botão que não mora em coluna de controle nenhuma chega
        // ao Python com o controle que ela apontou na fita — e isso é DESENHO,
        // não acidente: *"Esta aba passa a mirar o P2."*
        //
        // O QUE ISSO CUSTA, medido pela ONDA5-01-03 em 06/09 com foto: o
        // ENDEREÇO DO RECADO segue o mesmo caminho, e a recusa de um gesto de
        // PÁGINA (o cadeado da 01, que liga o Hefesto inteiro) pousa no cartão
        // do P1 e cobre o nome dele. O relato está em
        // `docs/process/agentes/2026-09-06/ONDA5-P-01.md` §7; a saída que existe
        // hoje é a página declarar `data-hef-recados`.
        //
        // ELE CURA A VIBRAÇÃO, e só ela. Medido com dublê em 02/09/2026:
        // `testar` e `parar` recusam com *"o clique não disse em qual controle
        // — e sem alvo a mesa inteira treme"*, e passam a chamar a ponte assim
        // que o clique traz um `controle`. Os botões do gabinete da aba
        // Conexões NÃO se curam com isto: o que falta a eles é o argumento do
        // próprio botão (`caminho`, `entrada`, `face`), que o dataset acima
        // agora carrega.
        //
        // POR QUE NÃO NO PRODUTO: escolher o primeiro controle conectado por
        // conta própria é uma DECISÃO de produto — se o botão não diz em qual
        // aparelho age, quem decide é ela, com a tela dizendo. A régua só o usa
        // para conseguir medir, e o relato marca esses cliques como ALVO
        // FORÇADO, para ninguém ler a ajuda dela como o produto funcionando.
        controle: dono ? (dono.dataset.controle || dono.dataset.uniq || '')
                       : (window.__hef.alvoPadrao || ''),
        // O VALOR, e ele é o que o `textContent` não alcança: num `<input>` o
        // texto é vazio, e num `<select>` é a lista INTEIRA de opções. Sem
        // isto, um campo digitado chega ao Python sem o que ela digitou.
        valor: (('value' in alvo) ? String(alvo.value ?? '') : ''),
        // `selectedOptions` dá o rótulo VISÍVEL da opção escolhida — o que ela
        // leu na tela — enquanto `value` dá a chave do contrato. Os dois vão,
        // porque o gesto precisa de um e a mensagem de erro do outro.
        rotulo: (alvo.selectedOptions && alvo.selectedOptions[0]
                 ? alvo.selectedOptions[0].textContent.trim() : ''),
        tipo: (alvo.tagName || '').toLowerCase(),
        evento: ev.type,
        // A FORMA INTEIRA, e ela nasceu em 01/09/2026 para os três "Guardar"
        // das telas de pop-up. O ouvinte manda o valor do elemento CLICADO — e
        // o Guardar é OUTRO elemento, a três telas de distância dos 21
        // `<select>` que ele promete gravar. Sem isto, o botão só podia
        // recusar: não tinha como saber o que estava escolhido em cada linha.
        //
        // SÓ QUANDO O BOTÃO PEDE. `data-hef-forma` nomeia o container a
        // recolher; um clique comum não paga a varredura, e nenhum outro gesto
        // recebe um campo que não pediu.
        forma: (function(){
          const pedido = alvo.dataset.hefForma;
          if(!pedido) return null;
          // DOIS RECIPIENTES, e o segundo nasceu em 01/09/2026 para a aba
          // Gatilhos: lá o "Guardar" é da COLUNA de um controle, e as colunas
          // não têm `id` — elas se endereçam por `data-controle`, que é o
          // vocabulário que a mesa inteira já usa. `@controle` quer dizer "o
          // bloco do controle em que eu estou".
          const cx = pedido === '@controle'
            ? alvo.closest(
                '[data-uniq],[data-controle=""],[data-controle="p1"],[data-controle="p2"],[data-controle="p3"],[data-controle="p4"]')
            : document.getElementById(pedido);
          if(!cx) return null;
          const fora = {};
          // A CHAVE É O `data-linha`, OU o `data-campo` quando não há. A aba
          // Navegação marcou as 21 linhas com `data-linha`; a Gatilhos já tinha
          // `data-campo` em cada valor da coluna, e marcá-los de novo seria a
          // segunda cópia do mesmo endereço.
          for(const el of cx.querySelectorAll('[data-linha],[data-campo]')){
            const chave = el.dataset.linha || el.dataset.campo;
            fora[chave] = ('value' in el)
              ? String(el.value ?? '') : (el.textContent || '').trim();
          }
          return fora;
        })(),
        texto: (alvo.textContent || '').trim().slice(0, 60),
      });
  }
  function manda(o){
    o.pagina = location.pathname.split('/').pop();
    window.webkit.messageHandlers.hefesto.postMessage(JSON.stringify(o));
  }
  return 'ok';
})();
"""


#: A TABELA LOCAL MORREU em 01/09/2026, e a razão é de processo: ela era um
#: dicionário num arquivo só, e ligar as dez abas em paralelo significaria oito
#: pessoas editando a MESMA linha. Cada pacote passa a declarar os seus com
#: `@gesto(...)`, no próprio arquivo — território exclusivo, zero merge.
#:
#: Os dois que moravam aqui foram para `a09_sistema.py` e `a10_perfis.py`.


def _com_dono(ctx: pacotes.Contexto) -> list[str]:
    """Os `pN` que têm controle DE VERDADE agora — QUEM-TEM-DONO-01, 03/09/2026.

    NASCEU DE UMA REGRESSÃO MINHA, no mesmo dia. O passo `1c` do piloto (o que
    REABRE o cartão de um controle que chega) lia `carga["ocupados"]`, e a
    primeira versão daquela conta era `set(colunas)` — as colunas que a aba
    emitiu. Medido no DOM vivo, com UM controle na bancada: a `03-gatilhos`
    manda coluna para os QUATRO lugares, porque as vazias levam travessão de
    propósito, e o piloto passou a escrever `data-conectado="sim"` em dois
    lugares onde não há aparelho nenhum.

    **TER COLUNA NÃO É TER DONO.** A aba manda coluna para desenhar; quem diz
    quem está aqui é a MESA. Esta função é essa pergunta, e ela tem um dono só.

    A DECISÃO QUE ELA SUSTENTA é de 03/09/2026: *"tem que aparecer desligado
    enquanto não tem nenhum controle. A partir do momento que tiver, ele aparece
    o controle devidamente conectado."*
    """
    prefs: list[str] = []
    por_uniq = {str(c.get("uniq") or ""): c.get("pref") for c in ctx.mesa}
    for c in ctx.conectados:
        pref = por_uniq.get(str(c.get("uniq") or ""))
        if pref:
            prefs.append(str(pref))
    return prefs


#: A ESCOLHA DA FITA — quem ela apontou no `Selecionar:`.
#:
#: `""` é *ninguém escolheu ainda*, e nele a fita segue derivando do primeiro da
#: mesa, como sempre fez. `"todos"` é o chip `Todos`. Qualquer outro valor é um
#: `uniq` NORMALIZADO.
#:
#: O ENDEREÇO É O `uniq`, E NÃO O `pref`, e a razão é a lei de identidade desta
#: casa: `pref` é POSIÇÃO (`mesa_viva.mesa_do_estado` reenumera de 1 a cada
#: tique). Guardada por posição, a escolha do controle do rádio passaria para o
#: do cabo no instante em que o primeiro saísse da mesa — o mesmo defeito que
#: fez o recado de recusa aparecer no cartão do vizinho em 02/09/2026.
#:
#: ELE É MÓDULO, E NÃO CAMPO DO PILOTO, porque quem escreve nele é uma função de
#: gesto — `(ctx, o, ipc)`, sem acesso ao piloto — e quem lê é `_fita`. Um
#: processo tem uma janela; dois pilotos no mesmo processo nunca existiram.
class _EscolhaDaFita:
    """O único estado que o chip muda. Nada de perfil, nada de daemon."""

    def __init__(self) -> None:
        self.uniq = ""


ESCOLHA_DA_FITA = _EscolhaDaFita()


def _escolher_na_fita(ctx: pacotes.Contexto, o: dict[str, Any],
                      _ipc: Any) -> dict[str, Any]:
    """O clique no chip do `Selecionar:` — ele só ESCOLHE, e é todo o contrato.

    O QUE ELE NÃO FAZ, e está escrito porque é o risco desta cura: não troca de
    perfil, não fala com o daemon e não grava no disco dela. O `_ipc` chega e
    não é usado de propósito — a assinatura é a das dez abas.

    O `("*", …)` É O MESMO CORINGA DO RODAPÉ: a fita mora no `topo.html`, o
    esqueleto das dez, e registrá-la por página seria a mesma linha dez vezes.

    ELE RECUSA DIZENDO quando o `pref` clicado não está na mesa — um chip de um
    controle que saiu entre o desenho e o clique. Escolher calado o primeiro que
    sobrou é como a tela passa a mostrar um aparelho e a mexer noutro.

    E ELE MANDA A PRÓPRIA FRASE. Todo gesto que volta sem levantar deposita um
    recado na tela — decisão dela, D-01: *"No próprio cartão, como a recusa."*
    Sem esta frase a tela apenas PISCARIA (`MS_DA_PISCADA`), e uma piscada
    sobre uma ESCOLHA não diz qual; com ela, a tarja de rodapé nomeia quem a
    aba passou a mirar. O cartão fica de fora de propósito: ver
    `_endereco_do_chip`.
    """
    pref = str(o.get("pref") or "").strip()
    if pref == "todos":
        if not monta.cabe_o_todos(ctx.mesa):
            raise ValueError(
                "o chip `Todos` não se escolhe com um controle só na mesa: "
                "ele É a escolha.")
        ESCOLHA_DA_FITA.uniq = "todos"
        return {"recado": f"Esta aba passa a mirar os {len(ctx.mesa)} controles."}
    for c in ctx.mesa:
        if str(c.get("pref") or "") == pref:
            ESCOLHA_DA_FITA.uniq = norm_mac(str(c.get("uniq") or "")) or ""
            return {"recado": f"Esta aba passa a mirar o {pref.upper()}."}
    raise ValueError(
        f"o chip {pref!r} não está na mesa de agora — o controle saiu entre o "
        f"desenho da fita e o clique.")


# O REGISTRO É GUARDADO, e o `if` não é zelo: ESTE ARQUIVO É IMPORTÁVEL POR DOIS
# NOMES. O piloto põe a própria pasta no `sys.path` (a herança de quando ele
# vivia em `layout/_ferramentas/`), então `import hefesto_vivo` e
# `from hefesto_dualsense4unix.interface import hefesto_vivo` produzem DOIS
# módulos do mesmo arquivo — e as duas grafias estão em uso na suíte de hoje.
# Sem a guarda, a segunda importação chamaria `@gesto` de novo e o despachante
# mataria o processo com *"o gesto já tem dono"*, que é a proteção dele contra
# dois donos de verdade fazendo o trabalho de um acidente de `sys.path`.
if ("*", monta.GESTO_DA_FITA) not in pacotes.GESTOS:
    pacotes.gesto("*", monta.GESTO_DA_FITA)(_escolher_na_fita)


def _a_fita_desta_pagina_escolhe(pagina: str) -> bool:
    """`monta.a_fita_escolhe`, sem derrubar a janela numa página que não é aba.

    A guarda do dono é do GERADOR: lá, um nome de página errado tem de PARAR a
    geração em vez de gravar dez fitas esmaecidas em silêncio. Aqui ela cobraria
    de quem não protege — `paginas/` tem três páginas que não são abas (o mapa
    do controle, o das portas e a calibração), e a janela pode pousar nelas. Sem
    fita para escolher, a resposta honesta é *não escolhe*; matar o processo
    seria trocar uma tela errada por nenhuma tela.
    """
    try:
        return monta.a_fita_escolhe(pagina)
    except SystemExit:
        return False


def _pref_escolhido(mesa: list[dict[str, Any]]) -> str:
    """Que `pref` a fita acende AGORA, traduzido da escolha dela.

    A ESCOLHA NÃO É APAGADA quando o controle sai da mesa, e é de propósito:
    esta função só decide o que DESENHAR. É a mesma lição de
    `monta.escolha_da_fita` — gravar a queda no lugar da escolha é a marca de
    mão única que já custou caro nesta casa (QUEBRA-CARTAO-QUE-NAO-REABRE-01):
    a escolha cairia na desconexão e nunca mais voltaria quando o controle
    reaparecesse.
    """
    if not mesa:
        return "todos"
    se = ESCOLHA_DA_FITA.uniq
    if se == "todos":
        return "todos"
    if se:
        for c in mesa:
            if norm_mac(str(c.get("uniq") or "")) == se:
                return str(c["pref"])
    # NINGUÉM ESCOLHEU AINDA (ou o escolhido não está aqui): o primeiro da mesa,
    # que é o que esta fita sempre mostrou.
    return str(mesa[0]["pref"])


def _fita(mesa: list[dict[str, Any]], pagina: str) -> str:
    """A fita de chips com a mesa VIVA, pelo mesmo gerador do desenho.

    `monta.fita()` é o dono dela nas dez páginas. Passar `mesa` é obrigatório:
    sem o argumento ele cai nos `CONECTADOS` do mockup, que são derivados no
    IMPORT e nunca recalculados — trocar `monta.MESA` de fora não alcança.

    O `inerte` TAMBÉM É OBRIGATÓRIO, e sem ele esta função MENTIA em sete abas.
    Ela chamava `monta.fita(ativo=…, mesa=mesa)` e o padrão do parâmetro é
    `False`: como o piloto troca o bloco INTEIRO a cada tique, as abas em que a
    fita é LEITURA nasciam esmaecidas (do arquivo publicado) e no primeiro tique
    ficavam ACESAS, com o `title` de quem escolhe — *"O que você mudar nesta aba
    vai para o controle escolhido aqui."* — sobre uma aba onde nada vai.

    MEDIDO EM 05/09/2026, com o daemon dela no ar e um controle na mesa: as DEZ
    abas terminaram `class="fita"` e com aquele `title`, inclusive as sete cujo
    arquivo publicado traz `class="fita inerte"`. Quem responde agora é
    `monta.a_fita_escolhe()`, o mesmo dono que `monta()` consulta ao
    gravar o arquivo — a resposta deixou de ser digitada duas vezes.
    """
    # A VERSÃO DESTA GUARDA É DA FRENTE DA ABA 05, e ela venceu a minha na
    # integração de 03/09/2026. As duas achavam o mesmo defeito; a diferença é
    # o que fazem com o controle SEM cor lida:
    #
    #   a minha  — filtrava (`[c for c in mesa if c.get("cor")]`), e o controle
    #              sem cor SUMIA da fita;
    #   a dela   — deixa todos, e quem trata a cor ausente é o `monta.fita`: o
    #              chip nasce sem `--plastico` e cai no tom neutro do esqueleto.
    #
    # A dela é a certa, e a razão é dela também: ver QUE HÁ um controle ali
    # importa mais do que saber a cor dele. Sumir da fita esconderia o controle
    # do rádio da própria fonte de identidade que a lei manda consultar.
    if not mesa:
        # MESA VAZIA é a única razão de não pintar: sem controle nenhum não há
        # chip a emitir, e devolver "" deixa a fita como está.
        #
        # A GUARDA ERA MAIOR E MENTIA — 03/09/2026. Ela dizia
        # `any(not c.get("cor") for c in mesa)`, e a intenção era esperar a
        # resposta do leitor de plástico, que é perguntado em thread. Só que
        # pelo RÁDIO a resposta NUNCA vem: o mapa de canais responde
        # `identidade.cor_do_aparelho = não` e `mesa_viva.LeitorDeCor` marca
        # aquele endereço como perguntado com `None` para sempre. Com um
        # controle no cabo e outro no rádio — a mesa dela — a fita ficava
        # eternamente no desenho, e a tela dizia `P1 · Cosmic Red · USB` /
        # `P2 · Starlight Blue · BT` sobre um White e um controle sem cor
        # legível. Fotografado nas dez abas em 03/09/2026.
        #
        # ESPERAR PELO QUE NUNCA CHEGA É CAIR DE VOLTA NO MOCKUP, que é
        # exatamente o que a lei da identidade proíbe. Quem trata a cor que não
        # veio é o `monta.fita`: o chip nasce sem `--plastico`, e o `.chip` cai
        # no tom neutro que a folha de estilo já declara como recurso.
        #
        # `SystemExit` NÃO é `Exception` — herda de `BaseException`, e um
        # `except Exception` passa ao lado. O `except` abaixo cobre os dois.
        return ""
    # O TÍTULO É DA PÁGINA, E TEM DONO — 05/09/2026. Sem esta linha a troca do
    # bloco inteiro levava embora o `title` PRÓPRIO da 06 — *"Não se aplica:
    # mouse, teclado e gestos saem de um controle só…"* — e punha no lugar o
    # genérico de leitura, que diz menos e é menos verdadeiro. É a mesma cura
    # que `ABAS_QUE_ESCOLHEM` deu ao `inerte` no mesmo dia: um dono só,
    # consultado pelo gerador do arquivo E por aqui.
    titulo = monta.casca_da_fita(pagina)
    try:
        return monta.fita(ativo=_pref_escolhido(mesa),
                          inerte=not _a_fita_desta_pagina_escolhe(pagina),
                          mesa=mesa, titulo=titulo)
    except (Exception, SystemExit):
        return ""


#: O SELETOR DO CLIQUE SINTÉTICO, e ele cobre os QUATRO vocabulários das dez
#: páginas — `data-gesto`, `data-hef-gesto`, `data-papel` e a classe `r-<nome>`
#: do rodapé, que endereça assim porque mora no esqueleto compartilhado.
#:
#: Um seletor que cobrisse só o primeiro daria "clicou" sobre um `null` — e
#: `null.click()` não levanta com o `||{click(){}}`, então a prova passaria em
#: silêncio sobre um botão nunca tocado. Foi assim que o `--prova-gesto` da
#: Controles deu verde sobre dois botões mortos em 29/08.
SELETOR = ("(document.querySelector('[data-gesto=\"%s\"],[data-hef-gesto=\"%s\"],"
           "[data-papel=\"%s\"],.r-%s')||{click(){}}).click()")

#: O CLIQUE QUE SABE EM QUEM CLICAR — e ele nasceu de uma medição, em
#: 02/09/2026: dos 48 gestos clicados, DEZESSEIS disseram "aplicado" sem mudar
#: o estado do daemon, e SETE deles tinham recusado CORRETAMENTE, porque o
#: clique automático não disse em qual controle agir.
#:
#: `document.querySelector` pega o PRIMEIRO nó da página, que na mesa de quatro
#: colunas do desenho é o do P1 — e o P1 pode ser justamente o lugar VAZIO.
#: Aqui a ordem é outra: primeiro os blocos dos controles CONECTADOS, na ordem
#: da mesa; só então qualquer um.
#:
#: ELE DEVOLVE ONDE CLICOU, e isso é metade do valor: o relato passa a
#: distinguir "cliquei no bloco do p1" de "cliquei num botão que não pertence a
#: controle nenhum, com o alvo forçado pela régua" — que é um DEFEITO DA
#: PÁGINA, não um sucesso do produto.
CLIQUE_COM_ALVO = r"""
(function(g, prefs){
  const sel = '[data-gesto="' + g + '"],[data-hef-gesto="' + g + '"],'
            + '[data-papel="' + g + '"],.r-' + g;
  for(const p of prefs){
    const bloco = document.querySelector('[data-controle="' + p + '"]');
    const dentro = bloco && bloco.querySelector(sel);
    if(dentro){ window.__hef.alvoPadrao = p; dentro.click(); return 'no bloco de ' + p; }
  }
  const el = document.querySelector(sel);
  if(!el) return 'NAO ACHEI NA PAGINA';
  // A MESMA REGRA DO OUVINTE — ver `SELETOR_DO_DONO`. Uma régua que resolvesse
  // o dono de outro jeito mediria um clique que o produto não faz.
  const dono = el.closest(
    '[data-uniq],[data-controle=""],[data-controle="p1"],[data-controle="p2"],[data-controle="p3"],[data-controle="p4"]');
  if(dono){
    const q = dono.dataset.controle || dono.dataset.uniq || '';
    window.__hef.alvoPadrao = q;
    el.click();
    return 'no bloco de ' + q;
  }
  // FORA DE QUALQUER CONTROLE: o botão não diz em quem agir. A régua empresta
  // o primeiro conectado só para conseguir medir, e o relato marca.
  window.__hef.alvoPadrao = prefs[0] || '';
  el.click();
  return 'ALVO FORCADO ' + (prefs[0] || '(mesa vazia)');
})(%s, %s)
"""

#: O PEDIDO DE PINTURA — a expressão exata que o tique manda ao WebView.
#:
#: A GUARDA `window.__hef` NÃO É ZELO: entre o tique começar e o JS rodar, a
#: página pode ter trocado, e o `__hef` é do DOCUMENTO — morre com ele. Medido
#: em 01/09/2026, passeando pelas dez: duas abas devolviam `TypeError:
#: undefined is not an object` a cada travessia. O `-1` diz "a página trocou no
#: meio", que é diferente de "pintei nada", e o relato conta os dois separados.
#:
#: E ELA É UM TERNÁRIO, NÃO UM `|| -1`. Em JavaScript `0 || -1` é `-1`: com o
#: `||`, TODO tique que pintava zero voltava como "a página trocou", nunca
#: entrava na conta, e o detector de aba muda do relato era **ramo morto** —
#: justamente a linha escrita para pegar a `06-navegacao` publicando zero
#: endereços em 01/09. Medido em 02/09/2026: 178 tiques na `02-controles` e a
#: lista de pinturas com UM elemento só.
#:
#: ELA É CONSTANTE, e não uma f-string solta no tique, para que
#: `test_um_tique_que_pinta_zero_nao_vira_pagina_trocada` possa RODÁ-LA no
#: WebKit — a expressão que o produto manda, e não uma reescrita dela.
PEDIR_A_PINTURA = r"""
(window.__hef && window.__hef.pintar) ? window.__hef.pintar(CARGA) : -1
"""

#: O LEITOR DO DOM, e ele é O instrumento do `--prova-de-mockup`: devolve, em
#: ordem de documento, o que a TELA está mostrando em cada endereço de pintura.
#:
#: ELE LÊ O MESMO ALVO QUE O `escrever()` ESCREVE — a largura da barra, o
#: `value` do campo, o texto. Ler sempre `textContent` diria que toda barra de
#: bateria continua no mockup, porque a pintura dela nunca toca texto nenhum.
#:
#: `fundo` e `html` caem no texto de propósito: o WebKit devolve os dois
#: NORMALIZADOS (a cor vira `rgb(…)`, as aspas dos atributos trocam) e comparar
#: a forma do arquivo com a forma do navegador acusaria mudança onde não houve.
#: `regua_do_mockup._campo` lê os mesmos dois pelo texto, e é isso que faz os
#: dois lados casarem.
#:
#: `cor` NÃO CAI NO TEXTO, e a diferença com o `fundo` é medida, não de gosto.
#: Sondado no WebKit desta máquina em 02/09/2026, com a página offscreen:
#:
#:     '#6272a4'   → 'rgb(98, 114, 164)'     'red'         → 'red'
#:     '#fff'      → 'rgb(255, 255, 255)'    'transparent' → 'transparent'
#:     'var(--x)'  → 'var(--x)'              'rgb(1,2,3)'  → 'rgb(1, 2, 3)'
#:
#: **A FRASE QUE ESTAVA AQUI CAIU NO MESMO DIA**: *"a normalização é FECHADA e
#: pequena — hexadecimal e `rgb()` viram uma só forma, e todo o resto volta como
#: foi escrito"*. Não é fechada. A sonda de 51 formas mostrou que o `hsl()`
#: também vira `rgb()`, que o alfa é serializado CURTO, que o alfa cheio some, e
#: que todo CSS inválido volta `''` em vez de voltar como foi escrito.
#: `regua_do_mockup._cor_css` acompanha TODAS essas famílias, e quem confere não
#: é uma transcrição: `test_a_cor_e_medida_no_webkit_e_nao_transcrita` refaz a
#: sonda neste motor a cada execução. Por isso a régua pode ler o `color` de
#: verdade em vez do texto visível. Um campo de cor lido pelo texto seria
#: INDECIDÍVEL para sempre: pintar a cor não mexe numa letra.
#:
#: O QUINTO CAMPO É O SELO DA VISITA, e ele não vem da tela — vem do piloto.
#: Ver o comentário do `el.dataset.hefVisto` no BOOTSTRAP: é o que separa
#: "pintou igual" de "não pintou" nos 74 campos que a régua não decidia.
LER_CAMPOS = r"""
(function(){
  const fora = [];
  for(const el of document.querySelectorAll('[data-campo],[data-papel],[data-hef]')){
    const chave = el.dataset.campo || el.dataset.papel || el.dataset.hef || '';
    // O DONO É O ASSENTO — ver `SELETOR_DO_DONO`. Sem esta lista, os quatro
    // campos que moram dentro do desenho compartilhado (`treme-e` e `treme-d`,
    // nas colunas do p1 e do p2 da `05-vibracao`) voltavam com o nome do MODELO
    // no lugar do assento, e a régua do mockup não os casava com a coluna que
    // os pinta.
    const bloco = el.closest(
      '[data-uniq],[data-controle=""],[data-controle="p1"],[data-controle="p2"],[data-controle="p3"],[data-controle="p4"]');
    const dono = bloco ? (bloco.dataset.controle || bloco.dataset.uniq || '') : '';
    const alvo = el.dataset.hefAlvo || 'texto';
    let v;
    if(alvo === 'largura'){ v = el.style.width; }
    // O gêmeo vertical, na MESMA língua: `style.height` volta com a unidade
    // que o CSSOM acrescenta (`64%`), e `_declarado_neste_elemento` põe o `%`
    // do lado do pacote pelo mesmo ramo que já serve o `largura`.
    else if(alvo === 'altura'){ v = el.style.height; }
    else if(alvo === 'valor'){ v = ('value' in el) ? String(el.value ?? '') : ''; }
    else if(alvo === 'cor'){ v = el.style.color; }
    else if(alvo === 'atributo'){
      // O ATRIBUTO, NA MESMA LÍNGUA DOS DOIS LADOS: o texto que ele guarda, ou
      // `''` quando não há atributo nenhum. `regua_do_mockup._campo` lê o mesmo
      // atributo do arquivo com o mesmo vazio por omissão — sem isso um SVG cujo
      // `data-colorway` o produto APAGOU (o aparelho não disse a cor) seria lido
      // como `null` de um lado e `''` do outro, e a régua acusaria a pintura
      // certa.
      v = el.getAttribute((el.dataset.hefAtributo || '').trim().toLowerCase()) || '';
    }
    else if(alvo === 'marcado'){
      // NA MESMA LÍNGUA DO `escrever`: `sim` quando está marcado, vazio quando
      // não. Devolver `true`/`false` faria a régua do mockup comparar a palavra
      // do arquivo com um booleano do navegador e acusar toda pintura certa —
      // é a mesma cura de forma que o alvo `cor` já custou uma medição.
      v = el.checked ? 'sim' : '';
    }
    else if(alvo === 'classe'){
      // O QUE ESTE ELEMENTO MOSTRA, na MESMA língua em que o `escrever` recebe:
      // o `data-hef-quando` de quem está aceso, ou `sim` quando o alvo é
      // booleano. Devolver "quem do grupo está aceso" exigiria o leitor
      // conhecer o grupo, e o parser de Python do outro lado não conhece — as
      // duas leituras têm de casar endereço a endereço, e é essa igualdade que
      // a guarda do DOM virgem cobra a cada aba.
      const c = el.dataset.hefClasse || 'on';
      v = el.classList.contains(c) ? (el.dataset.hefQuando || 'sim') : '';
    }
    else { v = (el.textContent || '').replace(/\s+/g, ' ').trim(); }
    fora.push([chave, dono, alvo, v, el.dataset.hefVisto === '1']);
  }
  return JSON.stringify(fora);
})()
"""

#: QUANTOS TIQUES A PINTURA CORRE ANTES DE O OBSERVADOR LIGAR.
#:
#: A primeira pintura de uma página MUDA a tela de propósito — ela troca o
#: desenho cravado no arquivo pelo dado do daemon, e cada valor escrito é uma
#: mutação legítima. Contar a partir do tique zero mediria a CHEGADA, não o
#: samba. Dois segundos é o que a `--prova-de-mockup` já usa como assentamento
#: (`--voltas-por-aba`, oito voltas por aba mais a cor do plástico que volta em
#: thread); aqui o dobro, porque a mesa demora a chegar inteira e uma cor que
#: pousa no tique 15 contaria como inquietude.
VOLTAS_ATE_ASSENTAR = 20

#: O OBSERVADOR DE MUTAÇÕES — o instrumento da A-TELA-SAMBA-01.
#:
#: POR QUE ELE PRECISOU EXISTIR, e a razão é de MEDIÇÃO: duas fotos da tela dela
#: com um minuto de intervalo saem IDÊNTICAS enquanto ela relata *"a interface
#: inteira tá sambando"*. O sintoma não está no layout parado — está no
#: MOVIMENTO entre dois tiques, e foto nenhuma o alcança. O contador de pinturas
#: que já existe (`window.__hef.pintar` devolve quantos valores escreveu) também
#: não: ele conta o que o piloto ACHA que escreveu, e o defeito é justamente a
#: escrita que o piloto não conta — um `setAttribute` com o valor igual, um
#: `classList.add` de uma classe que já está lá.
#:
#: **UM `setAttribute` COM O MESMO VALOR É UMA MUTAÇÃO DE DOM.** A especificação
#: manda enfileirar um `MutationRecord` em toda troca de atributo, e não só
#: quando o valor difere — por isso o observador vê o que o contador de pinturas
#: não vê, e por isso ele é a régua certa para este defeito.
#:
#: O ENDEREÇO DE CADA MUTAÇÃO é o `data-campo`/`data-papel`/`data-hef` mais
#: próximo subindo a árvore — o mesmo vocabulário do `achar()`. Sem isso a
#: tabela diria "houve 800 mutações" e ninguém saberia em quem.
OBSERVAR_MUTACOES = r"""
(function(){
  window.__hef = window.__hef || {};
  if(window.__hef.observador){ window.__hef.observador.disconnect(); }
  const linhas = {};
  window.__hef.mutacoes = linhas;
  window.__hef.mutacoesTotal = 0;
  function endereco(no){
    let el = (no && no.nodeType === 1) ? no : (no ? no.parentElement : null);
    while(el && el.getAttribute){
      const c = el.getAttribute('data-campo') || el.getAttribute('data-papel')
                || el.getAttribute('data-hef');
      if(c) return c;
      if(el.classList && el.classList.contains('fita')) return '(a fita)';
      el = el.parentElement;
    }
    return '(sem endereco)';
  }
  function somar(campo, tipo, detalhe, nos){
    const k = campo + '|' + tipo + '|' + detalhe;
    let l = linhas[k];
    if(!l){ l = linhas[k] = {campo: campo, tipo: tipo, detalhe: detalhe,
                             n: 0, nos: 0}; }
    l.n += 1;
    l.nos += (nos || 0);
    window.__hef.mutacoesTotal += 1;
  }
  const obs = new MutationObserver(function(regs){
    for(const r of regs){
      const onde = endereco(r.target);
      if(r.type === 'attributes'){
        somar(onde, 'attributes', r.attributeName || '?', 0);
      } else if(r.type === 'childList'){
        somar(onde, 'childList', '(filhos)',
              r.addedNodes.length + r.removedNodes.length);
      } else {
        somar(onde, 'characterData', '(texto)', 0);
      }
    }
  });
  obs.observe(document.documentElement, {
    attributes: true, childList: true, characterData: true, subtree: true});
  window.__hef.observador = obs;
  window.__hef.mutacoesDesde = Date.now();
  return 'observando';
})()
"""

#: A LEITURA DA TABELA. Devolve as linhas já ordenadas pela contagem, para que
#: quem lê veja o culpado na primeira linha.
LER_MUTACOES = r"""
(function(){
  const h = window.__hef || {};
  const linhas = [];
  for(const k of Object.keys(h.mutacoes || {})) linhas.push(h.mutacoes[k]);
  linhas.sort(function(a, b){ return b.n - a.n; });
  return JSON.stringify({
    total: h.mutacoesTotal || 0,
    ms: Date.now() - (h.mutacoesDesde || Date.now()),
    // OS BLOCOS ADIADOS SAEM NA MESMA LEITURA: um bloco que o piloto NÃO
    // trocou porque havia um botão em voo dentro dele é um fato do mesmo
    // fenômeno, e sem ele a tabela diria só o que aconteceu, nunca o que foi
    // evitado.
    blocos_adiados: h.blocosAdiados || 0,
    linhas: linhas
  });
})()
"""

#: O MÉTODO LENTO DE CADA GESTO, para a prova esperar o tempo dele. Só os que
#: passam do padrão precisam de linha aqui.
_METODO_DO_GESTO = {
    "atualizar": "daemon.reload", "modo-dualsense": "gamepad.emulation.set",
    "modo-xbox": "gamepad.emulation.set", "modo-navegacao": "mouse.emulation.set",
    "hefesto": "native.mode.set", "ativar": "profile.switch",
    "aplicar": "profile.apply_draft", "reconectar": "coop.sync",
}

#: OS GESTOS QUE MEXEM NA MÁQUINA DELA, e que a prova botão a botão NÃO clica
#: sozinha. Não é timidez: `desligar` para o serviço e ela fica sem controle no
#: meio do trabalho; `refazer-proton` apaga configuração; `reiniciar` derruba a
#: sessão do serviço. Uma régua não mexe na máquina de alguém para provar que
#: sabe clicar. Para incluí-los, `--incluir-perigosos` — e aí é escolha de quem
#: roda.
#:
#: **ELA É DERIVADA DESDE 06/09/2026, e deixou de ser digitada** (sprint
#: `ONDA3-GESTO-DECLARA-01`). Cada gesto declara no PRÓPRIO decorador o que ele
#: muda — `@gesto("05-vibracao.html", "motor", grava="rumble_motores_set")` — e
#: esta linha é só a soma: `pacotes.perigosos()`. A razão de cada entrada mora
#: no `grava=` dela, ao lado da função, e não mais aqui.
#:
#: POR QUE A LISTA DIGITADA TINHA DE MORRER, e os dois defeitos são medidos:
#:
#: * **ela chegava atrasada.** QUATRO vezes em três dias um gesto aprendeu a
#:   gravar e a linha veio no commit seguinte — `01-jogar·cadeado`,
#:   `08-conexoes·renomear-adaptador`, os dois da Vibração, os dois da tela de
#:   teclas. A janela entre as duas é a janela em que a `--prova-gesto` escreve
#:   no disco DELA: medido em 03/09/2026, dez gravações em `meu_perfil.json`
#:   entre 07:14 e 07:47, uma por aba provada;
#: * **ela protegia fantasma.** `("09-sistema.html", "restaurar-de-fabrica")`
#:   passou meses aqui protegendo NADA — o gesto sempre se chamou
#:   `refazer-proton`. Uma lista lida só para PULAR não acusa o próprio erro de
#:   digitação. Com a chave saindo do registro, um fantasma não tem como nascer.
#:
#: A QUALIFICAÇÃO POR PÁGINA NÃO É PRECIOSISMO: `detectar` nos Perfis grava no
#: perfil DELA, e o mesmo `detectar` na Lançadores só procura o jogo. `tirar-daqui`
#: existe nas abas 07 e 08, e escreve em arquivos diferentes. Uma lista por nome
#: cru trataria os dois igual, e a escolha seria entre não provar o seguro ou
#: estragar o trabalho dela. O coringa `("*", nome)` é para o rodapé, que é um
#: gesto só nas dez páginas — `_alvos_a_clicar` casa as duas formas.
#:
#: E A DERIVAÇÃO NÃO DISPENSA A RÉGUA: `test_todo_gesto_que_grava_esta_protegido`
#: continua LENDO a árvore de cada gesto, e cobra as duas direções — quem grava
#: e não declarou, e quem declarou uma porta que a árvore não acha. Quem esquece
#: a linha também esquece o `grava=`; duas fontes independentes é o que fecha.
#: O laudo completo, com as medições que cada entrada carregava, está em
#: `docs/process/agentes/2026-09-06/ONDA3-GESTO-DECLARA-01.md`.
PERIGOSOS = pacotes.perigosos()


def _achatar(o: Any, prefixo: str = "") -> dict[str, Any]:
    """O estado do daemon como `{caminho: valor}` — para comparar antes/depois.

    Achatar é o que torna a comparação LEGÍVEL: sem isso, "o estado mudou" seria
    um diff de dois dicionários aninhados de 49 chaves, e ninguém leria qual
    campo se mexeu. Com isso, o relato diz
    `controllers.0.lightbar_rgb: [0,0,255] → [126,184,212]`.
    """
    fora = {}
    if isinstance(o, dict):
        for k, v in o.items():
            fora.update(_achatar(v, f"{prefixo}.{k}" if prefixo else str(k)))
    elif isinstance(o, list):
        for i, v in enumerate(o[:4]):
            fora.update(_achatar(v, f"{prefixo}.{i}"))
    else:
        fora[prefixo] = o
    return fora


#: OS CAMPOS QUE MUDAM SOZINHOS a cada tique — o relógio do daemon, os contadores
#: de força-feedback, a posição dos analógicos. Compará-los faria TODO gesto
#: parecer que mudou alguma coisa, que é o mesmo que não medir nada.
RUIDO = ("visto_ha_s", "ha_s", "_count", "nascimento", "age_sec", "uptime",
         "inputs.", "motion_", "forwards", "counters.", "_ultimos_",
         # OS EIXOS NA RAIZ DO STATE, e não só dentro de `inputs`. O daemon
         # publica `lx`, `ly`, `rx`, `ry`, `l2_raw` e `r2_raw` nos DOIS lugares,
         # e o filtro só cobria o segundo. Um analógico em repouso oscila um
         # ponto — `ry: 128 → 129` — e isso fazia um botão qualquer parecer que
         # mudou o aparelho. Medido em 01/09 na aba Conexões: o `sala-altura`
         # deu ✓ sobre o tremor do polegar dela.
         "lx", "ly", "rx", "ry", "l2_raw", "r2_raw", "buttons",
         "battery_pct", "bt_mic")


def _pagina_da_uri(uri: str | None) -> str:
    """O nome do arquivo à vista, ou `""`.

    É o que o despachante usa de chave, e é o que o `load-changed` entrega. Sai
    da URI e não de um estado que o piloto guarde: guardar seria uma segunda
    fonte da verdade sobre em que aba a janela está, e as duas divergiriam na
    primeira navegação que falhasse no meio.
    """
    if not uri:
        return ""
    return uri.rstrip("/").split("/")[-1].split("?")[0].split("#")[0]


class Piloto:
    #: OS DOIS TETOS DA LEITURA DOS CONTROLES QUE O HEFESTO SÓ VÊ — EXTERNOS-01,
    #: 06/09/2026. **Os dois números são os da janela antiga**, e nenhum se
    #: escolhe aqui: um segundo teto para a mesma pergunta seria a segunda
    #: verdade que esta casa persegue.
    #:
    #: | | valor | de onde |
    #: | --- | --- | --- |
    #: | entre leituras | 4,0 s | `home_actions.HomeActionsMixin.EXTERNOS_THROTTLE_S` |
    #: | espera pela resposta | 3,0 s | o `timeout_s` de `_maybe_fetch_externos` |
    #:
    #: **POR QUE NÃO NO TIQUE**, e o custo está medido no dono
    #: (`daemon/ipc_handlers._handle_controller_list`): a enumeração de
    #: `/dev/input` mais a sonda de holders custa **10-40 ms e um subprocess**, e
    #: foi por isso que o daemon a deixou FORA do `state_full` e atrás de um
    #: opt-in. Num orçamento de 100 ms, pedi-la a cada tique comeria até 40% do
    #: laço para receber a mesma resposta 40 vezes.
    #:
    #: **A ESPERA VAI EXPLÍCITA** porque `ponte.teto` não conhece
    #: `controller.list`: herdar os 0,25 s do bridge daria uma lista VAZIA a cada
    #: leitura, e lista vazia se lê como *"não há externo"*.
    #:
    #: **POR QUE ATRIBUTO DE CLASSE, e não constante de módulo lá em cima ao lado
    #: do `TIQUE_MS`** — o portão `citacoes-no-codigo` foi quem mostrou: QUATRO
    #: arquivos de outras posses citam `hefesto_vivo.py:NNN` em comentário, e um
    #: bloco novo no topo empurra as quatro citações para linhas que não dizem
    #: mais o que elas prometem. Aqui não se move uma linha do que já existia — e
    #: a forma passa a ser a MESMA do dono na janela antiga, que também os guarda
    #: como atributo de classe.
    SEGUNDOS_ENTRE_LEITURAS_DOS_EXTERNOS = 4.0
    SEGUNDOS_DE_ESPERA_DOS_EXTERNOS = 3.0

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.pronto = False
        self.agendado = False
        self.relatou = False
        self.pagina = PRIMEIRA
        self.voltas = 0
        #: Quantos valores cada aba pintou, na ordem em que foram visitadas —
        #: só os tiques que escreveram ALGUMA coisa. É o que mede a quietude:
        #: uma aba sadia pinta uma vez e sossega, e uma que soma pintura a cada
        #: tique tem endereço que o navegador recusa.
        self.pinturas: dict[str, list[int]] = {}
        #: Quantos tiques cada aba levou, PINTANDO OU NÃO. Sem este contador não
        #: dá para dizer "a aba tem pacote e nenhum endereço casou": um tique de
        #: zero valor não deixava rastro nenhum, e o detector de aba muda ficava
        #: inalcançável. Medido em 02/09/2026 — 178 tiques na `02-controles` e um
        #: só elemento em `pinturas`.
        self.tiques: dict[str, int] = {}
        #: Quantas vezes a página TROCOU no meio de um tique. É o `-1`, e ele é
        #: um fato diferente de "pintei nada" — misturar os dois foi o que
        #: engoliu o zero.
        self.trocas: dict[str, int] = {}
        self.visitadas: list[str] = []
        self.custos: list[float] = []
        #: O que ESTE processo mandou ao daemon, e o que recusou por falta de
        #: dono. Os dois contados: sem o segundo, "nada aconteceu" e "não havia
        #: quem atendesse" ficariam indistinguíveis.
        self.gestos: list[dict[str, Any]] = []
        self.aplicados: list[str] = []
        self.recusados: list[str] = []
        #: A mesa e o contexto do último tique — é o que o gesto recebe. Sem
        #: eles, um clique que chega entre dois tiques não teria com que
        #: trabalhar, e resolver o `uniq` na hora exigiria um IPC a mais por
        #: clique.
        #: O que a prova botão a botão mediu, um por gesto.
        self.provas: list[dict[str, Any]] = []
        #: O DESFECHO DE CADA GESTO, por `página:nome`. Sem isto, um gesto que
        #: RECUSOU DIZENDO e um gesto que aplicou e não fez nada saem do relato
        #: iguais — foi assim que os sete "recusaram corretamente" de 02/09
        #: entraram na conta dos dezesseis "aplicado e nada mudou".
        self.desfechos: dict[str, tuple[str, str]] = {}
        #: Em que bloco de controle cada clique caiu — ou se o alvo foi FORÇADO
        #: pela régua, que é defeito da PÁGINA e não sucesso do produto.
        self._onde_clicou: dict[str, str] = {}
        #: A FRASE DE RECUSA DE CADA CONTROLE —
        #: `{uniq_normalizado: (frase, quando_monotônico)}`.
        #:
        #: ELA VIVE NO ESTADO, e não no instante do clique: a tela repinta a cada
        #: 100 ms, e uma frase publicada só no tique da borda tem probabilidade
        #: ~0 de coincidir com o tique em que ela olha — existiria e ninguém a
        #: veria. É a mesma razão pela qual
        #: `daemon/subsystems/recado_do_microfone.py` é um DEPÓSITO e não um
        #: evento, e a chave segue a mesma ideia: uma por controle, porque na
        #: mesa de quatro a recusa de um não pode aparecer no cartão do vizinho.
        #: A chave vazia é o recado da MESA — o gesto que não age em controle
        #: nenhum.
        #:
        #: A CHAVE É O ENDEREÇO, E NÃO A POSIÇÃO, e a mudança é de 02/09/2026.
        #: Guardada por `pref` a frase ficava colada à COLUNA, e a coluna troca
        #: de dono: `mesa_viva.mesa_do_estado` enumera os conectados de 1 a cada
        #: tique (*"o `pref` continua sendo a POSIÇÃO … e `jogador` continua
        #: sendo a IDENTIDADE"*). MEDIDO com dublê de dois controles: recusa no
        #: 🎙 do `p1` (o do cabo), o do cabo SAI da mesa, o do rádio vira `p1` —
        #: e o cartão dele passava a mostrar, por até 30 s, uma frase que
        #: termina em *"ou este controle saiu da mesa"*, sobre OUTRO controle.
        #: É o defeito de identidade que esta casa já pagou várias vezes, e o
        #: dono certo do endereço já existia: `core/sysfs_leds.norm_mac`.
        #:
        #: SÓ O LAÇO DO GTK ESCREVE AQUI. O gesto corre em thread, e depositar de
        #: lá deixaria o tique iterando um dicionário que outra thread muda.
        #:
        #: A TERCEIRA CASA DA TUPLA É O TOM — `recusa` ou `sucesso`, e ela nasceu
        #: com a D-01 em 04/09/2026. Um dicionário SEPARADO para o sucesso seria
        #: a segunda cópia da mesma regra (a poda, a tradução `uniq → pref`, a
        #: sobrevivência à repintura), e a segunda divergiria — é o mesmo
        #: argumento que fez a recusa ter um canal só para as dez abas.
        #:
        #: E A CHAVE CONTINUA UMA POR CONTROLE, de propósito: o último ato daquele
        #: aparelho é o que a coluna dele mostra. Uma recusa seguida de um
        #: sucesso no mesmo botão não pode deixar as duas frases na tela, uma
        #: dizendo o contrário da outra.
        self._recados: dict[str, tuple[str, float, str]] = {}
        #: A SÉRIE MAIS NOVA DE CADA CAMPO VIVO — `{identidade: série}`.
        #:
        #: É a metade Python do *"um gesto vivo em voo por elemento"*. O JS
        #: numera cada disparo e diz de que campo ele é; aqui fica o último
        #: número visto, e a resposta que chegar com um número velho é
        #: DESCARTADA. Sem isso, a leitura da tecla `1` pode voltar depois da
        #: leitura de `15` e pintar o rótulo do jogo errado — e ficar assim até
        #: a próxima tecla, porque nada mais o repinta.
        #:
        #: SÓ O LAÇO DO GTK ESCREVE AQUI, como no depósito de recados: o gesto
        #: corre em thread, e a comparação acontece no `idle_add` da volta.
        self._vivos: dict[str, str] = {}
        #: O QUE A QUARTA PORTA FEZ, para o relato e para a régua. Os três
        #: contados à parte: sem eles, *"o vivo respondeu"*, *"o vivo chegou
        #: tarde"* e *"o vivo foi recusado"* sairiam iguais — que é o silêncio
        #: que esta casa persegue.
        self.vivos_atendidos: list[str] = []
        self.vivos_recusados: list[str] = []
        self.vivos_descartados = 0
        self._fila: list[str] = []
        #: O `--prova-de-mockup`: o que o ARQUIVO crava, o que o DOM mostra
        #: ANTES de qualquer pintura, e o veredito de cada campo por aba.
        self.cravados: dict[str, list[regua_do_mockup._Campo]] = {}
        self.pristino: dict[str, list[list[str]]] = {}
        self.vereditos: dict[str, list[regua_do_mockup._Veredito]] = {}
        #: Onde a régua não conseguiu ler o que prometeu ler. Uma linha aqui é
        #: a régua confessando, e ela reprova por isso.
        self.cegueiras: list[str] = []
        self._fila_de_abas: list[str] = []
        self._voltas_da_aba = 0
        self._medindo = False
        self._carga_de_agora: dict[str, Any] = {}
        self._mesa_de_agora: list[dict[str, Any]] = []
        self._ctx_de_agora = pacotes.Contexto(state={})
        #: O CONTADOR DE MUTAÇÕES (`--conta-mutacoes`): quantos tiques correram
        #: desde que a página ficou de pé, e se a tabela já foi lida.
        #: `getattr` porque quem monta o `Namespace` à mão — as réguas que abrem
        #: um `Piloto` sem passar pelo `argparse` — não conhece a bandeira nova,
        #: e um `AttributeError` ali seria esta sprint quebrando a régua da
        #: vizinha por causa de um contador que ela não usa.
        self._voltas_do_contador = 0
        self._mutacoes_lidas = False
        #: A TABELA QUE O OBSERVADOR DEVOLVEU, para quem mede de dentro. Sem
        #: ela a régua teria de reler a saída impressa — que é a forma de
        #: instrumento que esta casa já pagou caro (*a régua lê o texto, não o
        #: fato*).
        self.mutacoes: dict[str, Any] = {}
        #: OS TIQUES QUE NÃO CORRERAM, e por quê. Um tique pulado é o piloto
        #: RECUSANDO enfileirar — e sem contá-los "o tique é rápido" e "o tique
        #: nunca rodou" sairiam iguais no relato.
        self._pulados_por_voo = 0
        self._pulados_por_custo = 0
        #: Há uma pintura no ar sem resposta? Enquanto houver, o tique seguinte
        #: não manda outra.
        self._pintura_no_ar = False
        #: Quantos tiques ainda pular por causa do custo do último.
        self._pular = 0
        #: O custo das DUAS VIAGENS de IPC, separado do custo total do tique. É
        #: o que responde "quem come o orçamento" sem adivinhação.
        self.custo_do_ipc: list[float] = []
        self.leitor = mesa_viva.LeitorDeCor(ligado=not args.sem_cor)
        #: Os `uniq` já perguntados ao leitor de cor. Sem esta trava, cada tique
        #: abriria uma thread nova para o mesmo controle — 2 por segundo.
        self.perguntados: set[str] = set()
        #: OS CONTROLES QUE O HEFESTO SÓ VÊ, e as duas travas da leitura deles —
        #: EXTERNOS-01, 06/09/2026. A lista é a ÚLTIMA resposta boa; o carimbo
        #: diz quando ela chegou; a bandeira impede duas perguntas no ar.
        #:
        #: A LISTA NÃO SE APAGA ENTRE LEITURAS, e é escolha: entre um tique e o
        #: seguinte não houve resposta nenhuma, e zerá-la faria o card do 8BitDo
        #: PISCAR quarenta vezes por leitura. O `[]` inicial vale "ainda não
        #: perguntei", que é o mesmo que "não há" para quem desenha.
        self._externos: list[dict[str, Any]] = []
        self._externos_lidos_em = 0.0
        self._externos_no_ar = False

        self.tela = JanelaDaAba(
            arquivo=onde.pagina(PRIMEIRA, publicado=True),
            titulo_esperado=TITULO_DE_QUALQUER_ABA,
            ao_carregar=self._instalar,
            ao_receber=self._gesto,
            ao_sair_da_aba=self._navegou,
            # A TELA QUE NÃO FICA NUA — T-01, e é o único defeito VIVO desta
            # frente: ela viu acontecer, com foto. Quem RECARREGA é a janela
            # (`gui/ponte_da_tela.JanelaDaAba._morreu_a_pagina`, e a medição está
            # lá); o que o piloto faz aqui é PARAR de pintar no vazio e DIZER.
            ao_morrer_a_pagina=self._a_pagina_morreu,
            oculta=args.oculta,
            # A MOLDURA NÃO TEM SEGUNDA LINHA — 08/09/2026, e ela saiu porque
            # falava a língua de dentro. Aqui ia `subtitulo="as dez abas,
            # vivas"`, que a `Gtk.HeaderBar` escrevia embaixo de "Hefesto": era
            # o jeito de ESTA CASA dizer que o piloto único monta as dez abas de
            # verdade — registro de obra, não informação para quem usa. Ela
            # fotografou a barra de título e o leu lá.
            #
            # SAIU EM VEZ DE SER TROCADO: a barra já diz "Hefesto", e tudo o
            # que muda — a aba, o alvo, o perfil ativo — já está DENTRO da
            # janela, escrito e vivo. Uma segunda linha aqui repetiria o de
            # dentro ou inventaria assunto.
            #
            # POR QUE ISTO ATRAVESSOU AS DUAS RÉGUAS DE TELA, e é o achado que
            # sobra: `check_a_conferencia_dela` e `check_a_tela_nao_confessa`
            # medem o CORPO das dez páginas. A barra de título é GTK, não HTML —
            # nenhuma das duas a alcançava. *A régua parava na borda da
            # `<body>`, e a tela dela não para.* Quem passa a medir a moldura é
            # `scripts/check_a_janela_nao_confessa.py`, que nasceu com esta
            # linha e reprova se ela voltar.
        )
        self.view = self.tela.view
        self.ponte = self.tela.ponte
        # O SEGUNDO OUVINTE, e ele precisa ser próprio: o `ao_sair_da_aba` da
        # biblioteca dispara UMA vez, na saída da aba desta janela. Daqui em
        # diante toda página é "fora da aba" e o callback não volta. Sem este
        # `connect`, Jogar → Gatilhos → Jogar não produziria evento nenhum e o
        # piloto ficaria pintando a página errada. É a mesma nota que o
        # `controles_vivos` carrega, e a razão é a mesma.
        self.view.connect("load-changed", self._carregou)

        # O SELETOR DE ARQUIVO É DA JANELA, e por isso é ligado AQUI. Os pacotes
        # são puros — um `import gi` neles obrigaria toda régua a ter GTK e o CI
        # a rodar com display. A ponte declara o ponto de extensão recusando; o
        # piloto o preenche ao subir.
        ponte.escolher_arquivo = self._escolher_arquivo
        ponte.salvar_arquivo = self._salvar_arquivo

    # -- o seletor de arquivo, que é do sistema ---------------------------
    def _dialogo(self, titulo: str, acao: Any, rotulo: str, *,
                 sugestao: str = "", padrao: str = "*") -> str | None:
        """Um `FileChooserDialog` modal, e ele RODA NO LAÇO DO GTK.

        POR QUE `Gtk.Dialog.run()` E NÃO UM CALLBACK: o gesto está numa thread
        (os gestos correm fora do laço, porque `daemon.reload` leva 9,5 s), e
        precisa do caminho para seguir. `run()` bombeia o laço do GTK por
        dentro, então a janela continua viva enquanto ela escolhe.

        COM A JANELA OCULTA NÃO HÁ DIÁLOGO: uma `Gtk.OffscreenWindow` não tem
        onde pôr um modal, e abrir um sem pai o jogaria NA TELA DELA — que é
        exatamente o que `--oculta` existe para impedir. Nesse caso devolve
        `None`, e o gesto o lê como "cancelou".
        """
        if self.args.oculta:
            print(f"[seletor] {titulo}: a janela está oculta, não abro diálogo",
                  file=sys.stderr)
            return None
        dlg = Gtk.FileChooserDialog(title=titulo, transient_for=self.tela.janela,
                                    action=acao)
        dlg.add_buttons("Cancelar", Gtk.ResponseType.CANCEL,
                        rotulo, Gtk.ResponseType.ACCEPT)
        if sugestao:
            dlg.set_current_name(pathlib.Path(sugestao).name)
            with contextlib.suppress(Exception):
                dlg.set_current_folder(str(pathlib.Path(sugestao).parent))
        if padrao != "*":
            f = Gtk.FileFilter()
            f.set_name(padrao)
            f.add_pattern(padrao)
            dlg.add_filter(f)
        try:
            escolhido = dlg.get_filename() if dlg.run() == Gtk.ResponseType.ACCEPT else None
        finally:
            dlg.destroy()
        return escolhido

    def _escolher_arquivo(self, titulo: str, padrao: str = "*", **_: Any) -> str | None:
        return self._dialogo(titulo, Gtk.FileChooserAction.OPEN, "Abrir", padrao=padrao)

    def _salvar_arquivo(self, titulo: str, sugestao: str = "", **_: Any) -> str | None:
        return self._dialogo(titulo, Gtk.FileChooserAction.SAVE, "Guardar",
                             sugestao=sugestao)

    # -- os gestos ---------------------------------------------------------
    def _com_uniq(self, o: dict[str, Any]) -> dict[str, Any]:
        """O clique com o `uniq` do controle resolvido contra a mesa de agora.

        A TRADUÇÃO MORA AQUI, e não dentro do gesto: a tela endereça por `pref`
        (`p1`), o daemon por `uniq` (`d4:2f:00:00:…`), e a mesa que traduz é do
        piloto. Cada gesto resolvendo por conta própria seria a mesma tradução
        escrita nove vezes — e a nona estaria errada.

        E ELA É UMA FUNÇÃO desde 06/09/2026, quando a quarta porta nasceu: o
        gesto vivo precisa do MESMO `uniq` que o clique, e uma segunda cópia
        deste laço seria a segunda a divergir.
        """
        pref = str(o.get("controle") or "")
        for c in self._mesa_de_agora:
            if c.get("pref") == pref or str(c.get("uniq") or "") == pref:
                return {**o, "uniq": str(c.get("uniq") or "")}
        return o

    def _gesto_vivo(self, o: dict[str, Any], pagina: str, nome: str) -> None:
        """A quarta porta — o gesto que LÊ enquanto ela digita, e não grava.

        O CONTRATO, e cada linha dele fecha um defeito que a leitura por tecla
        cria e a por clique não tem:

        * **ele não pode gravar.** Quem declara o que muda na máquina dela é o
          próprio gesto, no decorador (`@gesto(..., grava="save_profile")`), e é
          esse registro que esta guarda consulta — `pacotes.GESTOS_QUE_MEXEM`,
          o mesmo dono de que `PERIGOSOS` é derivado. Um `data-hef-vivo` apontado
          para um gesto que grava é RECUSADO aqui, nomeando o gesto, e a função
          nem chega a ser chamada;
        * **a resposta não pode trocar HTML nem falar** — ver
          `CHAVES_QUE_O_VIVO_RECUSA`;
        * **a resposta velha não pinta por cima da nova** — a série do JS decide,
          e a que chegar atrasada é descartada em silêncio (é o caminho normal
          de quem digita depressa, não um defeito a anunciar).

        POR QUE O REGISTRO E NÃO A CONSTANTE `PERIGOSOS`: aquela é avaliada no
        IMPORT deste módulo, e um pacote importado depois — o caminho de toda
        régua que registra um gesto à mão — não entraria nela. A pergunta é
        feita ao dono na hora de despachar, que é quando a resposta importa.
        """
        serial = str(o.get("vivo") or "")
        chave = str(o.get("vivoChave") or f"{pagina}:{nome}")
        acao = pacotes.gesto_da_pagina(pagina, nome)
        if acao is None:
            self.vivos_recusados.append(f"{pagina}:{nome} (sem dono)")
            print(f"[vivo sem dono] {pagina} · {nome} — o `data-hef-vivo` "
                  f"aponta para um gesto que ninguém registrou", file=sys.stderr)
            return
        grava = (pacotes.GESTOS_QUE_MEXEM.get((pagina, nome))
                 or pacotes.GESTOS_QUE_MEXEM.get(("*", nome)) or "")
        if grava:
            self.vivos_recusados.append(f"{pagina}:{nome} (grava: {grava})")
            print(f"[vivo recusado] {pagina} · {nome} declara gravação "
                  f"({grava}) — a quarta porta é de LEITURA, e ela dispara a "
                  f"cada tecla", file=sys.stderr)
            return
        self._vivos[chave] = serial
        o = self._com_uniq(o)

        def trabalhar() -> None:
            try:
                resposta = acao(self._ctx_de_agora, o, ponte)
            except Exception as erro:
                # A RECUSA DE UM GESTO VIVO NÃO VAI PARA O CARTÃO, e é decisão:
                # o canal do recado tem prazo (30 s a recusa) e um aviso por
                # tecla o encheria de frases que ela não pediu. Um vivo que
                # levanta é defeito de quem o ligou, e quem o lê é quem depura.
                self.vivos_recusados.append(
                    f"{pagina}:{nome} ({type(erro).__name__}: {erro})")
                print(f"[vivo falhou] {pagina} · {nome}: {erro}", file=sys.stderr)
            else:
                GLib.idle_add(
                    lambda r=resposta: self._vivo_voltou(pagina, nome, chave,
                                                         serial, r))

        threading.Thread(target=trabalhar, daemon=True).start()

    def _vivo_voltou(self, pagina: str, nome: str, chave: str, serial: str,
                     resposta: object) -> bool:
        """A leitura chegou. Se ainda é a mais nova, ela pinta.

        O DESCARTE É SILENCIOSO DE PROPÓSITO: chegar tarde é o caminho normal de
        quem digita depressa, e um `stderr` por tecla afogaria o terminal de
        quem depura. O contador `vivos_descartados` é onde ele aparece.
        """
        if self._vivos.get(chave) != serial:
            self.vivos_descartados += 1
            return False
        if not isinstance(resposta, dict) or not resposta:
            self.vivos_atendidos.append(f"{pagina}:{nome}")
            return False
        proibidas = [k for k in CHAVES_QUE_O_VIVO_RECUSA if k in resposta]
        if proibidas:
            self.vivos_recusados.append(
                f"{pagina}:{nome} (devolveu {', '.join(proibidas)})")
            print(f"[vivo recusado] {pagina} · {nome} devolveu "
                  f"{', '.join(proibidas)} — a quarta porta dispara a cada "
                  f"tecla, e essas chaves trocam HTML inteiro ou falam no "
                  f"cartão", file=sys.stderr)
            return False
        self.vivos_atendidos.append(f"{pagina}:{nome}")
        # A GUARDA `window.__hef &&` é a mesma da pintura, e pela mesma razão:
        # entre a tecla e a volta da thread a página pode ter trocado.
        self._js(f"window.__hef && window.__hef.pintar({_json(resposta)})")
        return False

    def _gesto(self, o: dict[str, Any]) -> None:
        """tela → Python, já em JSON. Quem recusa o que não é objeto é a ponte.

        O QUE ELE FAZ E O QUE NÃO FAZ, e a diferença é a regra desta casa: ele
        despacha o que tem DONO no daemon e RECUSA o resto **com o motivo na
        tela**. Um botão que responde calado quando não há quem atenda é a
        `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` em miniatura — quem clica conclui que
        funcionou.
        """
        self.gestos.append(o)
        nome = str(o.get("gesto") or "")
        pagina = str(o.get("pagina") or self.pagina)  # (noqa-acento: verbo)  (nome de variável)
        # A QUARTA PORTA SAI AQUI, e antes de tudo: o gesto vivo tem contrato
        # próprio (não veste voo, não deposita recado, não grava, e a resposta
        # velha é descartada). Misturá-lo no caminho do clique faria a leitura de
        # cada tecla percorrer o depósito de avisos e o pouso do botão.
        if str(o.get("vivo") or ""):
            self._gesto_vivo(o, pagina, nome)
            return
        # O NÚMERO DO VOO, carimbado pelo ouvinte no elemento clicado. Ele é o
        # que devolve o botão ao normal — e tem de ser devolvido nos TRÊS
        # desfechos, o "sem dono" incluído.
        voo = str(o.get("voo") or "")
        acao = pacotes.gesto_da_pagina(pagina, nome)
        if acao is None:
            self.recusados.append(f"{pagina}:{nome}")
            self.desfechos[f"{pagina}:{nome}"] = ("sem dono", "")
            print(f"[gesto sem dono] {pagina} · {nome} · {o.get('texto', '')!r}")
            self._pousou(voo)
            return
        o = self._com_uniq(o)
        # O RECADO É ENDEREÇADO AQUI, PELO MESMO `uniq` que o gesto recebe, e
        # não pelo `pref`: a coluna troca de dono entre o clique e o tique
        # seguinte. Ver `self._recados`. Sem `uniq` resolvido (gesto de mesa, ou
        # clique sobre uma coluna que já esvaziou) a chave é vazia, e o aviso
        # vira tarja de rodapé — que é honesto: não há cartão de quem dizer.
        alvo = norm_mac(str(o.get("uniq") or "")) or ""

        # EM THREAD, e não no laço do GTK. MEDIDO em 01/09/2026, com o daemon
        # dela: `daemon.reload` leva **9,5 segundos** — `daemon.resume` leva 1
        # ms e `daemon.status` 57. Um gesto síncrono congelaria a janela inteira
        # por nove segundos e meio, sem nada na tela dizendo por quê, e quem
        # clicou concluiria que o app travou.
        def trabalhar() -> None:
            # O DESFECHO **DESTA** EXECUÇÃO, e ele é o que decide a piscada —
            # ONDA5-01-03, relatado em 06/09/2026 e curado aqui.
            #
            # O DEFEITO É DE FORMA, e não acontece hoje por acaso do JS: a chave
            # de `self.desfechos` é `página:gesto`, e um MESMO clique pode chegar
            # por DUAS portas — o `click` e o `change` de um `<select>`, cada um
            # numa thread. As duas escrevem na mesma chave, e o `finally` de cada
            # uma lia dali para decidir a cor do pouso. Com a primeira recusando
            # e a segunda aplicando, o botão de quem RECUSOU piscaria verde.
            #
            # POR QUE NÃO PÔR O VOO NA CHAVE, que era a outra saída: `desfechos`
            # é o RELATO, e a chave dele é lida por nome em toda régua desta casa
            # e no `--prova-gesto`. Um número de voo ali trocaria um verde falso
            # raro por um relato ilegível em todas.
            #
            # O DONO CONTINUA SENDO UM: as duas atribuições abaixo são a MESMA
            # tupla, escrita no dicionário e nesta variável na mesma linha — quem
            # mudar o desfecho continua mudando o pouso junto, que era a razão de
            # o `finally` ler o dicionário.
            desta_vez: tuple[str, str] = ("", "")
            try:
                resposta = acao(self._ctx_de_agora, o, ponte)
            except Exception as erro:
                # O `erro` é AMARRADO no argumento do lambda, e não capturado
                # do escopo: o `except ... as` do Python apaga o nome ao sair do
                # bloco, e o lambda roda DEPOIS, no laço do GTK. Sem a amarra é
                # `NameError` na hora de relatar a falha — o erro comendo o
                # relato do erro.
                # A FRASE DA RECUSA É GUARDADA, e não só impressa. `ValueError`
                # é clique inválido e `RuntimeError` é o produto recusando com
                # o motivo — as duas coisas são DESFECHO, e um relato que as
                # some com "não fez nada" mente sobre sete botões desta casa.
                desta_vez = ("recusou dizendo", f"{type(erro).__name__}: {erro}")
                self.desfechos[f"{pagina}:{nome}"] = desta_vez
                # A FRASE VAI PARA A TELA, e o `idle_add` é o que a leva ao
                # único laço que pode tocar o DOM e o depósito. Até 02/09/2026
                # esta linha só imprimia no `stderr` — ver `_recusou_dizendo`.
                GLib.idle_add(
                    lambda x=erro: self._recusou_dizendo(pagina, nome, alvo, x))
            else:
                # OS DOIS DESFECHOS SÃO ANOTADOS NO MESMO LUGAR, e é aqui: o
                # `except` logo acima guarda a recusa, e esta linha guarda o
                # "voltou sem levantar". Anotar o sucesso lá no `_deu_certo`
                # separaria os dois ramos do mesmo `try`, e quem lesse um não
                # veria o outro.
                desta_vez = ("aplicou", "")
                self.desfechos[f"{pagina}:{nome}"] = desta_vez
                GLib.idle_add(
                    lambda r=resposta: self._deu_certo_dizendo(pagina, nome, alvo, r))
            finally:
                # O POUSO É DOS TRÊS DESFECHOS, e por isso mora no `finally`: um
                # gesto que levante fora do contrato (nem `RuntimeError` nem
                # `ValueError`) deixaria o botão "trabalhando" para sempre — e um
                # botão que afirma um trabalho que ninguém está fazendo é pior
                # que o silêncio que este estado veio curar.
                #
                # DEPOIS dos dois `idle_add` acima, e é a ordem que importa: o
                # `idle_add` respeita a ordem de agendamento na mesma
                # prioridade, então o recado já está na tela quando o rótulo
                # volta ao normal.
                #
                # E O POUSO LEVA O DESFECHO — 05/09/2026, decisão dela na
                # `03-Q4`. O `finally` continua sendo o dono do pouso pela razão
                # acima; o que ele leva é o fato que os dois ramos do `try`
                # anotaram — **o desta execução**, e não o que estiver na chave
                # compartilhada quando esta thread chegar aqui. Ver `desta_vez`,
                # no alto desta função.
                deu_certo = desta_vez[0] == "aplicou"
                GLib.idle_add(lambda v=voo, c=deu_certo: self._pousou(v, c))

        threading.Thread(target=trabalhar, daemon=True).start()

    def _pousou(self, voo: str, certo: bool = False) -> bool:
        """O botão volta do voo — a classe sai e o rótulo original é devolvido.

        Sem número não há o que devolver: um gesto que chegou por caminho que
        não passa pelo ouvinte (uma régua chamando `_gesto` à mão) não carimbou
        elemento nenhum, e mandar JS por isso seria poluir o console de quem
        depura com uma varredura que não acha nada.

        `certo` PISCA O CAMPO EM VERDE (05/09/2026, decisão dela na `03-Q4`), e
        o default é `False` de propósito: quem chama sem dizer não afirma que
        deu certo. Um default verdadeiro faria a recusa piscar verde, que é a
        tela dizendo as duas coisas de uma vez.
        """
        if not voo:
            return False
        self._js(
            f"window.__hef && window.__hef.voltouDoVoo({_json(voo)}, {_json(bool(certo))})"
        )
        return False

    def _deu_certo(self, pagina: str, nome: str, resposta: object = None) -> bool:
        """O gesto voltou. Se ele TROUXE ALGO, o que trouxe vai para a tela.

        O CAMINHO DE VOLTA, e por que ele precisou existir (01/09/2026): o gesto
        devolvia `None` e não havia por onde escrever um resultado na página.
        Isso deixou sem dono os botões cuja promessa é MOSTRAR — "Ver os
        plugins carregados" e "Ver detalhes" da aba Sistema. O daemon atende
        `plugin.list` desde sempre; o que faltava era o retorno. Um gesto que
        chamasse `plugin.list` e jogasse a lista fora seria o botão que responde
        calado — o defeito que esta casa tem nome para.

        A CARGA É A MESMA DA PINTURA, de propósito: `{"mesa": {...}}`,
        `{"colunas": {...}}`. Nenhum segundo vocabulário nasce aqui, e um gesto
        que devolve endereço escreve no mesmo lugar em que a pintura escreveria
        — logo o tique seguinte não briga com ele, sobrescreve com o valor vivo.
        """
        self.aplicados.append(f"{pagina}:{nome}")
        if isinstance(resposta, dict) and resposta:
            # A GUARDA `window.__hef &&` é a mesma da pintura, e pela mesma
            # razão: entre o clique e a volta da thread a página pode ter
            # trocado, e o `__hef` morre com o documento.
            self._js(f"window.__hef && window.__hef.pintar({_json(resposta)})")
            print(f"[gesto] {pagina} · {nome} → aplicado, e a resposta foi para a tela")
            return False
        print(f"[gesto] {pagina} · {nome} → aplicado")
        return False

    def _recusou_dizendo(self, pagina: str, nome: str, uniq: str,
                         erro: BaseException) -> bool:
        """A recusa do produto chegando ao CARTÃO — e não à saída de erro.

        O CONTRATO É DE ANTES DESTA FUNÇÃO e é explícito: `RuntimeError` quer
        dizer *"o produto recusou, e a frase VAI PARA A TELA"*, escrita para
        quem está com o controle na mão. Até 02/09/2026 ela ia para o `stderr`
        do processo, e quem clica na janela não lê o terminal de quem a lançou.

        MEDIDO PELO CAMINHO DELA, e é a forma de defeito mais cara desta casa —
        *alguém curou o caminho e provou a cura num caminho que ela não usa*:
        dois cliques no 🎙 da `02-controles`, com um dublê que faz o `mic.set`
        recusar, deram DUAS linhas no terminal, `desfechos` com a frase certa, e
        um DOM sem uma letra dela. O segundo clique parecia o primeiro.

        `ValueError` NÃO ENTRA, e a razão é o mesmo contrato: ele é *clique
        inválido*, e as frases que os pacotes escrevem nele falam com quem
        programa — uma delas cita `interface/aba06.py:OPCOES_TECLADO`. Pôr um
        caminho de arquivo no cartão dela trocaria um silêncio por um ruído. O
        que falta ali é uma frase que ela decida, e está no relato desta frente.

        O `uniq` CHEGA NORMALIZADO, e é a chave do depósito. Ele não é o `pref`
        do clique: quem endereça pela coluna endereça um lugar que troca de
        dono. Ver `self._recados`.
        """
        print(f"[gesto falhou] {pagina} · {nome}: {erro}", file=sys.stderr)
        if not isinstance(erro, RuntimeError):
            return False
        self._depositar(uniq, str(erro), "recusa")
        return False

    # -- o canal de SUCESSO (D-01) ----------------------------------------
    def _depositar(self, uniq: str, frase: str, tom: str) -> None:
        """Guarda um aviso e o põe na tela NA HORA. É o canal, e ele é um só.

        NA HORA, e não no próximo tique. Meio segundo entre o clique e a resposta
        basta para ela clicar de novo achando que o primeiro não pegou — que é o
        defeito de origem, não um detalhe de acabamento.

        A RECUSA E O SUCESSO ATRAVESSAM AQUI, os dois, e é essa a peça: o lugar
        (a coluna de quem ela clicou), a sobrevivência à repintura, a tradução
        `uniq → pref` no instante da pintura e a poda por tempo já existiam para
        a recusa e não podiam ser escritos de novo para o sucesso. A D-01 em uma
        linha é *"como a recusa"* — e "como" quer dizer *o mesmo caminho*.
        """
        self._recados[uniq] = (frase, time.monotonic(), tom)
        self._js(f"window.__hef && window.__hef.pintar("
                 f"{_json({'recados': self._recados_para_a_tela()})})")

    def _deu_certo_dizendo(self, pagina: str, nome: str, uniq: str,
                           resposta: object = None) -> bool:
        """O gesto voltou SEM levantar — e agora a tela dela sabe disso.

        **O DEFEITO, e a decisão que o fecha.** Até 04/09/2026 a interface nova
        só falava quando RECUSAVA: um gesto que dava certo imprimia
        `[gesto] … → aplicado` no terminal de quem lançou a janela, e quem clica
        não lê terminal. **Cinco linhas do CSV paravam neste mesmo buraco**, em
        cinco abas (02, 03, 05, 06 e 09). A decisão dela, no mesmo dia:

            *"No próprio cartão, como a recusa."*   — D-01

        DUAS RECOMENDAÇÕES PROPUNHAM OUTRO CANAL e as duas foram recusadas por
        UM FATO, UM SINAL — e é o que faz esta peça fechar as cinco abas de uma
        vez em vez de virar cinco peças que divergem. Esta metade continua
        valendo inteira.

        A OUTRA METADE CADUCOU EM 05/09/2026, e a data importa. Este parágrafo
        dizia que ELA recusara *o campo que pisca* (aba 03) e *a faixa embaixo
        da grade* (aba 05), e mandava: **"não construa nenhum dos dois"**. Quem
        recusou foi o PO, lendo a D-01 (*"no próprio cartão, como a recusa"*)
        como se ela fechasse a FORMA — os conflitos C-3 e C-6 de
        `2026-09-04-O-PO-DECIDE-as-54-e-os-sete-conflitos.md` são dele, não
        dela. Em 05/09 ela respondeu a `03-Q4` vendo as quatro formas lado a
        lado e escolheu o campo que pisca. **A palavra dela vence a leitura que
        o PO fez da palavra dela.**

        E a piscada não é um segundo canal para o mesmo fato: é o mesmo fato num
        sinal mais barato. O cartão passa a dizer só o que tem notícia, e as
        duas peças deixam de disputar.

        A FRASE É DO DONO DO ASSUNTO, e não deste arquivo: um gesto que devolva
        `{"recado": "…"}` manda a própria, e o piloto a leva. O `recado`
        SAI da carga antes de a resposta ir para a pintura: ele não é endereço de
        página nenhuma, e deixá-lo entrar faria o `escrever()` procurar um
        `data-campo="recado"` que não existe.

        E QUANDO NÃO HÁ FRASE, A TELA NÃO FALA — 05/09/2026, decisão dela na
        `03-Q4`. Até aqui valia uma frase do piloto (*"Pronto."*), e ela tirou
        a palavra nova da tela:

            *"nada muda de lugar e nenhuma palavra nova entra na tela"*

        **A regra que isso escreve:** *quando o gesto só repete o que ela acabou
        de fazer, a tela pisca; quando ele tem NOTÍCIA, a tela fala.* O canal
        continua sendo um só — o que muda é que ele para de falar sobre o que não
        tem o que dizer. Quem pisca é o `voltouDoVoo`, no pouso.

        ELE NÃO SUBSTITUI O `_deu_certo`, ele o EMBRULHA — e isso é de propósito:
        `_deu_certo` é o caminho da carga de volta (`plugin.list`, "Ver
        detalhes"), tem régua própria e não precisa saber que existe recado.
        """
        frase = ""
        if isinstance(resposta, dict):
            bruto = resposta.get("recado")
            if isinstance(bruto, str) and bruto.strip():
                frase = bruto.strip()
            if "recado" in resposta:
                resposta = {k: v for k, v in resposta.items() if k != "recado"}
        if frase:
            self._depositar(uniq, frase, "sucesso")
        return self._deu_certo(pagina, nome, resposta)

    def _a_pagina_morreu(self, motivo: str) -> None:
        """O processo web do WebKit caiu. A janela já está recarregando; aqui se DIZ.

        A PINTURA PARA ATÉ A PÁGINA VOLTAR, e sem esta linha o tique continuaria
        mandando JavaScript para um documento que não existe — foi o que a
        medição de 04/09 mostrou: `Unsupported result type (601)` a cada 100 ms,
        para sempre, no `stderr` de quem lançou a janela. O `_carregou` religa o
        `pronto` quando a página nova confirmar.

        O RECADO VAI PARA A CHAVE VAZIA — a tarja de rodapé —, e é o endereço
        honesto: um processo que morre não é de controle nenhum, e pousar a
        frase no cartão de um deles seria a tela afirmando, sobre um aparelho,
        uma coisa que não é dele.

        E ELE SOBREVIVE À RECARGA sem nenhum cuidado extra: o depósito é do
        PILOTO, não do documento — o tique da página nova o repõe. Era esse o
        ponto de o canal ser um depósito e não um evento.
        """
        print(f"[página morreu] {motivo} — a pintura pausou até a página voltar",
              file=sys.stderr)
        self.pronto = False
        self._recados[""] = (FRASE_DA_PAGINA_QUE_MORREU, time.monotonic(), "recusa")

    def _recados_para_a_tela(self) -> list[dict[str, str]]:
        """As frases de recusa ainda vivas, a poda das vencidas, e o CARTÃO de
        cada uma resolvido contra a mesa DE AGORA.

        A PODA MORA NO LEITOR, e não num relógio próprio: um `timeout_add` por
        recado seria um temporizador por clique recusado, e o que apaga a frase
        passaria a ser um agendamento que a troca de aba não cancela. Aqui a
        conta é feita quando alguém pergunta — que é a cada tique, e é o mesmo
        instante em que a lista vai para a tela.

        O RELÓGIO É MONOTÔNICO pelo mesmo motivo do
        `recado_do_microfone.quando_s`: um acerto de hora do sistema não pode
        fazer um aviso de agora parecer de ontem.

        A TRADUÇÃO `uniq → pref` É FEITA AQUI, NO INSTANTE DA PINTURA, e é o que
        fecha o defeito de identidade: o depósito guarda o ENDEREÇO, e quem
        pergunta a que coluna ele corresponde é a mesa deste tique. Quando o
        controle SAIU da mesa não há coluna, e o `cartao` sai vazio: o aviso vira
        tarja de rodapé em vez de pousar no cartão de quem ficou. Deixá-lo
        pousar ali seria a tela afirmando, sobre um controle, uma recusa de
        outro — a forma exata do defeito que o
        `test_a_frase_pousa_no_cartao_de_quem_foi_clicado` já impede no INSTANTE
        e que só aparece no TEMPO.

        SÃO DOIS ENDEREÇOS E NÃO UM: `chave` é a IDENTIDADE do aviso (o `uniq`
        normalizado, e é por ela que o BOOTSTRAP reencontra o próprio nó), e
        `cartao` é ONDE ELE POUSA AGORA. Somar os dois num campo só faria dois
        controles fora da mesa colidirem no mesmo `data-hef-recado` vazio — e a
        segunda frase sumiria calada, que é o silêncio que este canal existe
        para curar.
        """
        agora = time.monotonic()
        for chave, (_frase, quando, tom) in list(self._recados.items()):
            # CADA TOM TEM O SEU PRAZO, e os dois são decisão dela: a recusa
            # vive os 30 s de 02/09; o sucesso é um recibo e vive 6 s. A conta
            # continua sendo UMA — o que muda é o número que ela compara.
            if agora - quando >= (SEGUNDOS_DO_RECADO_DE_SUCESSO
                                  if tom == "sucesso" else SEGUNDOS_DO_RECADO):
                del self._recados[chave]
        onde_esta = {norm_mac(str(c.get("uniq") or "")) or "": str(c.get("pref") or "")
                     for c in self._mesa_de_agora}
        return [{"chave": chave,
                 "cartao": onde_esta.get(chave, "") if chave else "",
                 "texto": frase,
                 "tom": tom}
                for chave, (frase, _quando, tom) in sorted(self._recados.items())]

    # O `_ipc` CRU MORREU em 01/09/2026. Ele abria o socket à mão e montava o
    # JSON-RPC — reescrevendo o que o `app/ipc_bridge.py` já faz há meses, com
    # timeout pensado e a recusa do daemon traduzida em frase de tela. Quem
    # escreve agora é `pacotes/ponte.py`, e ele é UM caminho só.

    # -- navegação ---------------------------------------------------------
    def _navegou(self, titulo: str) -> None:
        """Ela clicou na tira. Aqui isso não pausa nada — é o ponto do piloto."""
        print(f"[navegou] {titulo}")

    def _carregou(self, _view: Any, evento: Any) -> None:
        from gi.repository import WebKit2

        if evento != WebKit2.LoadEvent.FINISHED:
            return
        nova = _pagina_da_uri(self.view.get_uri())
        if not nova or (nova == self.pagina and self.pronto):
            return
        self.pagina = nova
        if nova not in self.visitadas:
            self.visitadas.append(nova)
        # A PONTE MORRE A CADA CARGA — o `window.__hef` é do documento antigo.
        # Reinstalar é obrigatório, e esquecer isso é como uma aba nova nasce
        # muda sem uma linha de erro.
        self.pronto = False
        self._antes_de_instalar()

    def _instalar(self) -> None:
        self._antes_de_instalar()

    def _antes_de_instalar(self) -> None:
        """O DOM VIRGEM é lido AQUI, e é o único instante em que ele existe.

        A pintura começa no `_instalado`, logo abaixo. Depois dela, o que a
        página mostra já é uma mistura do que o arquivo cravou com o que o
        produto escreveu — e não há como desfazer a mistura olhando o resultado.
        Por isso o retrato do virgem vem ANTES do bootstrap, e o `_tique()` se
        recusa a pintar enquanto ele não voltou.

        NO PRODUTO ISTO NÃO ACONTECE: sem `--prova-de-mockup` o `if` é falso e a
        instalação segue exatamente como antes, sem um IPC a mais.
        """
        # O CONTADOR DE MUTAÇÕES VOLTA A ZERO A CADA CARGA, e não é zelo: o
        # observador vive em `window.__hef`, que MORRE com o documento. Sem
        # isto, `--abre 03` ligaria o observador na `01-jogar` (a página em que
        # a janela nasce), navegaria, e leria uma tabela vazia — o vazio mais
        # convincente que existe, porque é indistinguível de "nada se mexeu".
        self._voltas_do_contador = 0
        if self.args.prova_de_mockup and self.pagina not in self.pristino:
            pagina = self.pagina

            def retratou(valor: Any, erro: Any) -> None:
                self._leu_virgem(pagina, valor, erro)

            self.ponte.perguntar(LER_CAMPOS, retratou)
        self.ponte.perguntar(BOOTSTRAP, self._instalado)

    def _leu_virgem(self, pagina: str, valor: Any, erro: Any) -> None:
        import json

        if erro is not None:
            self.cegueiras.append(f"{pagina}: não li o DOM virgem — {erro}")
            # A LISTA VAZIA DESTRAVA O TIQUE. Sem ela a aba ficaria presa para
            # sempre esperando um retrato que não vem, e o passeio inteiro
            # morreria calado na primeira falha de JS.
            self.pristino[pagina] = []
            return
        try:
            self.pristino[pagina] = json.loads(str(valor))
        except ValueError as e:
            self.cegueiras.append(f"{pagina}: o DOM virgem não veio em JSON — {e}")
            self.pristino[pagina] = []

    def _instalado(self, _valor: Any, erro: Any) -> None:
        if erro is not None:
            print(f"ERRO: o bootstrap não instalou em {self.pagina}: {erro}", file=sys.stderr)
            return
        self.pronto = True
        # O TIMER E A SAÍDA SÓ UMA VEZ, e a flag é própria. Testar `voltas == 0`
        # aqui não funciona: `_tique()` roda logo acima e já a incrementa, então
        # a condição era sempre falsa — a janela ficava viva para sempre, sem
        # tique periódico e sem relato. Medido na primeira execução deste piloto.
        self._tique()
        if not self.agendado:
            self.agendado = True
            GLib.timeout_add(TIQUE_MS, self._tique)
            self._agendar()

    # -- a pintura ---------------------------------------------------------
    def _contexto(self, st: dict[str, Any]) -> tuple[pacotes.Contexto, dict[str, str]]:
        """O contexto do tique, e o dicionário `uniq → pref` para traduzir."""
        ctx_conectados = [c for c in (st.get("controllers") or [])
                          if c.get("connected", True)]
        # A COR DO PLÁSTICO vem do leitor, que responde `{}` até a primeira
        # pergunta voltar — por isso a mesa nasce "Não sei" e vira "Starlight
        # Blue" na segunda remontagem. Perguntar é BLOQUEANTE (fala com o
        # aparelho), então vai em thread: no tique ela travaria a janela.
        for c in ctx_conectados:
            uniq = str(c.get("uniq") or "")
            if uniq and uniq not in self.perguntados:
                self.perguntados.add(uniq)
                threading.Thread(
                    target=self.leitor.perguntar, args=(uniq,), daemon=True
                ).start()
        conectados = ctx_conectados
        # OS QUE O HEFESTO SÓ VÊ — EXTERNOS-01, 06/09/2026. A pergunta sai em
        # thread e a resposta é lida do cache, pela mesma razão da cor do
        # plástico três linhas acima: ela fala com `/dev/input` e com um
        # subprocess, e no tique travaria o laço do GTK inteiro.
        self._talvez_ler_os_externos()
        mesa = mesa_viva.mesa_do_estado(st, self.leitor.conhecidos())
        para_pref = {str(c.get("uniq") or ""): c["pref"] for c in mesa}
        ctx = pacotes.Contexto(state=st, mesa=mesa, conectados=conectados, estados={},
                               externos=list(self._externos))
        return ctx, para_pref

    def _talvez_ler_os_externos(self) -> None:
        """Pede `controller.list {external: true}` no tique LENTO, em thread.

        **AS TRÊS GUARDAS, e cada uma fecha um defeito que a janela antiga já
        pagou** (`home_actions._maybe_fetch_externos`, de onde as três vêm):

        1. **uma pergunta de cada vez** (`_externos_no_ar`) — sem ela, um daemon
           lento acumularia uma thread por tique, dez por segundo, todas
           enumerando `/dev/input` ao mesmo tempo;
        2. **o teto de tempo** (`SEGUNDOS_ENTRE_LEITURAS_DOS_EXTERNOS`) — a
           resposta muda quando alguém liga um controle, não dez vezes por
           segundo;
        3. **o relógio anda ANTES da thread sair**, e não quando ela volta: uma
           chamada que nunca responde deixaria a bandeira levantada para sempre,
           e a lista congelaria calada. O carimbo aqui faz a próxima tentativa
           acontecer sozinha assim que a bandeira cair.

        **A RESPOSTA RUIM NÃO APAGA A BOA.** `resultado()` LEVANTA quando o
        daemon não atende (é a escolha declarada em `pacotes/ponte.py`), e um
        `except` que zerasse a lista transformaria *"não consegui perguntar"* em
        *"não há controle nenhum"* — a confusão que esta casa chama de *ausência
        de notícia lida como sucesso*. Só uma resposta BOA troca a lista.
        """
        agora = time.monotonic()
        if self._externos_no_ar:
            return
        if (agora - self._externos_lidos_em
                < self.SEGUNDOS_ENTRE_LEITURAS_DOS_EXTERNOS):
            return
        self._externos_lidos_em = agora
        self._externos_no_ar = True

        def perguntar() -> None:
            try:
                r = ponte.resultado(
                    "controller.list",
                    timeout=self.SEGUNDOS_DE_ESPERA_DOS_EXTERNOS,
                    external=True,
                )
            except Exception as e:
                print(f"[externos] não li o inventário: {e}", file=sys.stderr)
                return
            finally:
                self._externos_no_ar = False
            # O DONO DA LEITURA É `home_actions.externos_na_mesa`, e ele já sabe
            # as duas fontes e o filtro. Repetir o `isinstance` aqui seria a
            # segunda régua para o mesmo payload.
            from hefesto_dualsense4unix.app.actions.home_actions import externos_na_mesa

            bruto = r.get("external") if isinstance(r, dict) else None
            self._externos = externos_na_mesa(
                None, bruto if isinstance(bruto, list) else ())

        threading.Thread(target=perguntar, daemon=True).start()

    def _tique(self) -> bool:
        if not self.pronto:
            return True
        # O TIQUE NÃO ENFILEIRA — A-TELA-SAMBA-01, e é a cura de *"trava por
        # instantes"*.
        #
        # O DEFEITO É DE FORMA, não de velocidade: `GLib.timeout_add` não deixa
        # duas execuções do mesmo `source` se sobreporem, mas as DUAS VIAGENS de
        # IPC do começo deste método são SÍNCRONAS — elas seguram o laço do GTK
        # inteiro. Um `profile.list` que custe 250 ms come dois tiques e meio; o
        # laço só volta a rodar quando ele responde, e a próxima batida do timer
        # já está vencida. O resultado é a janela andando aos solavancos, que é
        # exatamente a palavra dela.
        #
        # E A PINTURA É ASSÍNCRONA, o que é a segunda metade: `perguntar` volta
        # na hora e a resposta chega depois. Sem esta guarda, dez tiques podem
        # ter dez `run_javascript` no ar ao mesmo tempo, cada um mandando uma
        # carga inteira — e o WebKit os executa em ordem, todos com dado velho.
        #
        # PULAR É MELHOR QUE ATRASAR. Um tique pulado custa 100 ms de dado
        # velho; um tique enfileirado custa a fila inteira, e ela não encolhe
        # sozinha. Os dois contadores saem no relato.
        if self._pintura_no_ar:
            self._pulados_por_voo += 1
            return True
        if self._pular > 0:
            self._pular -= 1
            self._pulados_por_custo += 1
            return True
        if self.args.prova_de_mockup:
            if self.pagina not in self.pristino:
                # O RETRATO DO VIRGEM AINDA NÃO VOLTOU. Pintar antes dele
                # apagaria a única testemunha do que o arquivo crava — e a
                # régua passaria a medir a pintura contra ela mesma.
                return True
            self._voltas_da_aba += 1
            # A CONTA SOBE AQUI, ANTES do `pacote is None` lá embaixo, e não é
            # detalhe: a `07-lancadores` não tem pacote e sai daquele `return`
            # sem contar volta nenhuma. Com a conta lá, o passeio ficava preso
            # nela para sempre — a única aba que o `--passear` também nunca
            # visitou, pela mesma razão.
            if self._voltas_da_aba >= self.args.voltas_por_aba and not self._medindo:
                self._medindo = True
                pagina = self.pagina

                def mediu(valor: Any, erro: Any, p: str = pagina) -> None:
                    self._fechou_a_aba(p, valor, erro)

                self.ponte.perguntar(LER_CAMPOS, mediu)
        t0 = time.perf_counter()
        try:
            st = mesa_viva.estado_do_daemon()
        except Exception as e:
            # SERVIÇO MUDO NÃO É TELA PARADA — costura da ONDA E, 06/09/2026.
            #
            # Aqui era `return True`: o tique saía sem chamar o pacote, e a aba
            # ficava congelada no que o último tique bem-sucedido pintou. Para
            # quem olha, a tela CONTINUA AFIRMANDO — o interruptor no lugar em
            # que estava, os cartões com bateria e cor de minutos atrás — sobre
            # um serviço que não responde há minutos. É a mesma classe do card
            # que some: o silêncio é indistinguível do caminho feliz.
            #
            # A `JOGAR-O-QUE-FALTA-01` construiu a metade que faltava, e ela é o
            # ESTADO VAZIO: com `{}` a aba 01 acende a linha do selo `SERVIÇO` na
            # coluna Atenção, com a frase do dono, e para de afirmar —
            # interruptor, chip e cadeado saem vazios e os cartões recebem o
            # travessão pelo molde. Ela mediu que o pacote nunca era chamado
            # neste caminho, e por isso a metade dela não chegava à tela.
            #
            # `{}` E NÃO O ÚLTIMO ESTADO: um estado velho pintado como se fosse
            # de agora é exatamente o que esta linha existe para não fazer.
            print(f"[daemon mudo] {e}", file=sys.stderr)
            st = {}

        try:
            ctx, para_pref = self._contexto(st)
        except Exception as e:
            print(f"[mesa] não montou: {e}", file=sys.stderr)
            return True
        # AS DUAS VIAGENS DE IPC MEDIDAS À PARTE do custo do tique. `estado()`
        # e o `pacote_da_pagina()` logo abaixo são o que pode passar do
        # orçamento — a pintura não, porque ela é assíncrona. Sem esta marca o
        # relato dizia só "o tique custou X" e ninguém sabia se X era o daemon,
        # a mesa ou o JS.
        t_ipc = (time.perf_counter() - t0) * 1000
        # A MESA DE AGORA fica guardada para o gesto: um clique chega entre dois
        # tiques, e sem ela resolver o `uniq` custaria um IPC a mais por clique.
        self._mesa_de_agora, self._ctx_de_agora = ctx.mesa, ctx
        try:
            pacote = pacotes.pacote_da_pagina(self.pagina, ctx)
        except Exception as e:
            # UMA ABA QUE LEVANTA NÃO DERRUBA A JANELA. Ela para de pintar e o
            # motivo sai no relato — que é diferente de a tela congelar sem
            # dizer por quê, e é o estado que o `Contexto.por_uniq` já protege.
            print(f"[{self.pagina}] o pacote levantou: {e}", file=sys.stderr)
            return True
        if pacote is None:
            # A ABA SEM PACOTE AINDA TEM CABEÇALHO, e ele é das DEZ. Antes desta
            # linha ela saía daqui sem pintar nada — nem o topo, nem a fita — e
            # a `07-lancadores` (a única sem pacote, por decisão dela) ficava
            # mostrando o desenho inteiro. Medido pela `--prova-de-mockup` em
            # 02/09/2026, com o daemon dela no ar:
            #
            #     perfil  = 'Mortal Kombat'   ← e o perfil ativo dela era outro
            #
            # É a oitava aparição do defeito que esta casa já nomeou — *a tela
            # afirmando o que não é* —, e ela passa por aqui porque nenhuma aba
            # é dona do topo. Um pacote VAZIO é o que ela é: nada de próprio a
            # pintar, e tudo o que é de todas continua valendo.
            pacote = {}

        # A FORMA CANÔNICA E A TRADUÇÃO `uniq → pref`, as duas no despachante.
        # Ele é quem conhece as três palavras que as abas usam para a mesma
        # coisa (`colunas`, `cartoes`, `cards`) e o que cada uma deixa solto na
        # raiz. Repetir isso aqui seria um segundo dono da mesma regra.
        carga = pacotes.normalizar(pacote, para_pref)
        # O CABEÇALHO É DE TODAS AS ABAS, e não de nenhum pacote: a contagem e o
        # perfil ativo moram no `topo.html`, que é um só para as dez. Sem esta
        # linha os três campos ficavam vazios em TODA aba — cada pacote cuidava
        # da sua e ninguém cuidava do que era de todas.
        for chave, valor in pacotes.topo(ctx).items():
            carga["mesa"].setdefault(chave, valor)

        # A FITA É DE TODAS AS ABAS, e ela MENTE se não for repintada: o HTML
        # publicado traz os dois chips do mockup ("P1 · Cosmic Red · USB",
        # "P2 · Starlight Blue · BT"), e com UM controle no cabo a tela dizia
        # que havia dois, um deles no rádio. É a quinta reincidência do mesmo
        # defeito nesta casa — *uma frase que nomeia um controle fora da mesa* —
        # e a foto da aba Perfis o mostrou de novo em 01/09/2026, já com o topo
        # e a tabela corretos ao lado.
        carga["fita"] = _fita(ctx.mesa, self.pagina)

        # O ALVO QUE A FITA ESCOLHEU, e é o que faz o chip valer alguma coisa.
        #
        # O OUVINTE JÁ TINHA O ENCAIXE, e ele estava vazio no produto de
        # propósito (`window.__hef.alvoPadrao`, o `controle:` do clique): *"o
        # botão que não diz em qual aparelho age — quem decide é ela, com a tela
        # dizendo"*. A fita É a tela dizendo; enquanto ela não deixava escolher,
        # não havia o que pôr aqui.
        #
        # SÓ NAS ABAS QUE ESCOLHEM, e `""` nas outras sete: emprestar um alvo
        # numa aba cuja fita é leitura seria dizer, por baixo, o contrário do
        # que a fita esmaecida diz por cima.
        #
        # `Todos` TAMBÉM É `""`, e é a resposta honesta: um gesto que precisa de
        # UM aparelho e recebe "todos" tem de recusar dizendo, como já recusa
        # hoje. Escolher um dos dois aqui seria o produto decidindo por ela.
        alvo = (_pref_escolhido(ctx.mesa)
                if _a_fita_desta_pagina_escolhe(self.pagina) else "")
        carga["alvo"] = "" if alvo == "todos" else alvo

        # OS LUGARES VAZIOS RECEBEM TRAVESSÃO, e sem isto a tela MENTE. O HTML
        # publicado nasce com quatro colunas — a mesa do desenho, dois
        # conectados e dois vazios. Com UM controle na mesa, a coluna do P2
        # continuava mostrando o que o mockup escreveu: "Sony · Player 2 ·
        # Starlight Blue · BT · 64%". Visível na foto de 01/09, ao lado de um
        # topo que dizia "1 controle" e de uma fita já correta.
        #
        # É a sétima aparição do mesmo defeito nesta casa — *a tela afirmando um
        # controle que não está na mesa* — e a única cura que não depende de
        # cada aba lembrar-se dela é esta: quem pinta apaga o que sobra.
        #
        # A CONTA MORA NO DESPACHANTE, e a mudança é de 02/09/2026: escrita
        # aqui, ela só tinha uma régua que procurava LITERAIS neste arquivo — e
        # a cura morria inteira sem que os literais sumissem. Ver
        # `pacotes.apagar_os_lugares_sem_dono`.
        # A MESA VAI JUNTO — QUEM-TEM-DONO-01, 03/09/2026. Sem ela a conta
        # confundiria "a aba mandou coluna" com "há controle aqui", e o passo
        # `1c` reabriria lugar vazio. O `pref` de cada conectado é o `pN` da
        # posição de jogador, que é o mesmo endereço que a página desenha.
        pacotes.apagar_os_lugares_sem_dono(carga, _com_dono(ctx))

        # O RECADO DA RECUSA VIAJA EM TODO TIQUE, e é isto que o faz sobreviver
        # à repintura: a lista CHEIA recria o aviso se a pintura de blocos tiver
        # levado o cartão embora — e se ela trocou de aba, o aviso a acompanha,
        # porque é dela e não da página. A lista VAZIA é o que apaga o que
        # venceu; sem ela a frase ficaria na tela para sempre.
        carga["recados"] = self._recados_para_a_tela()

        def contou(valor: Any, erro: Any) -> None:
            # A PINTURA POUSOU — e é aqui, e só aqui, que o tique seguinte fica
            # livre para mandar outra. Antes do `return` de erro de propósito:
            # uma pintura que FALHOU também desocupou o ar, e não desmarcar
            # deixaria a janela muda para sempre depois do primeiro erro de JS.
            self._pintura_no_ar = False
            if erro is not None:
                print(f"[{self.pagina}] a pintura falhou: {erro}", file=sys.stderr)
                return
            try:
                n = int(str(valor))
            except (TypeError, ValueError):
                n = -1
            # O `-1` (página trocada no meio) NÃO entra na conta de tiques:
            # contá-lo como zero faria uma aba viva parecer muda na travessia.
            if n < 0:
                self.trocas[self.pagina] = self.trocas.get(self.pagina, 0) + 1
                return
            self.tiques[self.pagina] = self.tiques.get(self.pagina, 0) + 1
            # O ZERO CONTA COMO TIQUE E NÃO COMO PINTURA, e é essa separação que
            # faltava: `pinturas` mede a quietude (uma aba sadia pinta uma vez e
            # para), `tiques` mede que a aba RODOU. Sem os dois, "pintou uma vez
            # e sossegou" e "a página trocou 177 vezes" saíam iguais.
            if n > 0:
                self.pinturas.setdefault(self.pagina, []).append(n)

        self._pintura_no_ar = True
        self.ponte.perguntar(PEDIR_A_PINTURA.replace("CARGA", _json(carga)),
                             contou)
        # A CARGA DESTE TIQUE fica guardada: é ela — e não o código-fonte do
        # pacote — que diz o que o produto DECLAROU pintar nesta aba agora. Ler
        # daqui é o que separa esta régua das anteriores, que perguntavam se o
        # nome do campo aparecia em algum lugar do arquivo .py.
        self._carga_de_agora = carga
        self.voltas += 1
        custo = (time.perf_counter() - t0) * 1000
        self.custos.append(custo)
        self.custo_do_ipc.append(t_ipc)
        # O TETO É O PRÓPRIO TIQUE, e quem passou dele DIZ e cede a vez. Um
        # tique que custa mais que `TIQUE_MS` já entregou dado atrasado; mandar
        # o seguinte na hora só empilha atraso sobre atraso.
        if custo > TIQUE_MS:
            self._pular += 1
            print(f"[tique lento] {self.pagina}: {custo:.0f} ms "
                  f"(IPC {t_ipc:.0f} ms) — teto {TIQUE_MS} ms, pulando o "
                  f"próximo", file=sys.stderr)
        self._contar_mutacoes()
        return True

    # -- o contador de mutações (A-TELA-SAMBA-01) --------------------------
    def _contar_mutacoes(self) -> None:
        """Um passo do `--conta-mutacoes`, por tique. Fora dele, é um `if` falso.

        O ROTEIRO: deixa a pintura assentar `VOLTAS_ATE_ASSENTAR` tiques, LIGA o
        observador, conta N tiques, lê a tabela e sai. Com a mesa parada, tudo o
        que ele contar é a tela se mexendo sem que nada tenha mudado de valor.
        """
        quantos = int(getattr(self.args, "conta_mutacoes", 0) or 0)
        if quantos <= 0 or self._mutacoes_lidas:
            return
        self._voltas_do_contador += 1
        if self._voltas_do_contador == VOLTAS_ATE_ASSENTAR:
            self.ponte.rodar(OBSERVAR_MUTACOES)
            print(f"[mutações] observando {self.pagina} por {quantos} tiques "
                  f"(~{quantos * TIQUE_MS / 1000:.0f} s), com a mesa parada")
        if self._voltas_do_contador >= VOLTAS_ATE_ASSENTAR + quantos:
            self._mutacoes_lidas = True
            self.ponte.perguntar(LER_MUTACOES, self._leu_mutacoes)

    def _leu_mutacoes(self, valor: Any, erro: Any) -> None:
        """Imprime a tabela do observador — e SAI, porque a medição acabou."""
        import json

        if erro is not None:
            print(f"REPROVA: o observador não respondeu — {erro}",
                  file=sys.stderr)
            Gtk.main_quit()
            return
        try:
            fora = json.loads(str(valor))
        except ValueError as e:
            print(f"REPROVA: a tabela não veio em JSON — {e}", file=sys.stderr)
            Gtk.main_quit()
            return
        self.mutacoes = fora
        tiques = int(getattr(self.args, "conta_mutacoes", 0) or 0)
        print(f"\nMUTAÇÕES DE DOM em {tiques} tiques "
              f"({fora.get('ms', 0) / 1000:.1f} s) na {self.pagina}, "
              f"com a mesa parada")
        print(f"{'endereço':34s} {'tipo':14s} {'o quê':22s} {'n':>6s} {'nós':>6s}")
        for linha in fora.get("linhas", []):
            print(f"{str(linha['campo'])[:34]:34s} {linha['tipo']:14s} "
                  f"{str(linha['detalhe'])[:22]:22s} {linha['n']:6d} "
                  f"{linha['nos']:6d}")
        total = int(fora.get("total", 0))
        print(f"TOTAL: {total} mutações · {total / max(tiques, 1):.1f} por tique")
        if fora.get("blocos_adiados"):
            print(f"blocos ADIADOS por haver um `hef-em-voo` dentro: "
                  f"{fora['blocos_adiados']}")
        # O `SystemExit` DAS ABAS MUDAS NÃO PASSA DAQUI, e é de propósito: ele
        # nasce dentro de um callback do laço do GTK, onde o PyGObject o imprime
        # e engole — a janela ficaria aberta para sempre, sem `main_quit`. O
        # veredito desta régua é a TABELA; aba muda é o veredito da outra.
        with contextlib.suppress(SystemExit):
            self._relatar()
        Gtk.main_quit()

    # -- o roteiro e o relato ---------------------------------------------
    def _agendar(self) -> None:
        if self.args.passear:
            # O PASSEIO: clica a tira aba por aba, para provar que as dez
            # pintam. Sem ele o relato só teria a primeira — e "a aba abre" não
            # é o mesmo que "a aba pinta", que é a distinção inteira desta leva.
            for i, alvo in enumerate(sorted(pacotes.PACOTES)):
                GLib.timeout_add(
                    1200 + i * self.args.parada,
                    lambda a=alvo: self._ir(a),
                )
            total = 1600 + len(pacotes.PACOTES) * self.args.parada
        elif self.args.segundos:
            total = int(self.args.segundos * 1000)
        else:
            # SEM PRAZO: a janela fica aberta até ELA fechar. É o padrão do
            # PRODUTO, e o contrário disso foi um defeito que ela sentiu em
            # 01/09/2026 — abriu o `interface.sh`, a janela viveu 8 segundos e
            # sumiu. O `--segundos` tinha `default=6.0`, herdado de quando este
            # arquivo era só régua de bancada.
            #
            # A REGRA QUE ISSO DEIXA: toda flag de bancada nasce DESLIGADA. Um
            # padrão de régua que vira padrão de produto é um produto que se
            # comporta como régua na mão de quem usa.
            return
        def fechar() -> bool:
            # DUAS AÇÕES, e por isso uma função com nome em vez de um `lambda`:
            # relatar e SÓ ENTÃO fechar. Invertidas, o `main_quit` levaria o laço
            # embora antes de a última linha do relato sair.
            self._relatar()
            Gtk.main_quit()
            return False

        GLib.timeout_add(total, fechar)

    # -- a prova do mockup -------------------------------------------------
    def _provar_mockup(self) -> bool:
        """Passa pelas DEZ abas e mede, em cada uma, o que é dado e o que é desenho.

        O ROTEIRO, por aba: abre → retrata o DOM VIRGEM → deixa a pintura correr
        N tiques → lê a tela de novo → compara com o que o ARQUIVO crava.

        POR QUE N TIQUES E NÃO UM: *uma régua que roda o tique uma vez mede um
        INSTANTE, não um comportamento*. Em 29/08/2026 uma leva introduziu uma
        regressão que só aparecia aos 181 segundos, com 67 testes verdes. Aqui o
        padrão são oito voltas — quatro segundos por aba — porque a mesa demora
        a chegar inteira: a cor do plástico é perguntada ao aparelho em thread e
        a primeira volta pinta "Não sei".
        """
        self._fila_de_abas = [
            p.name for p in onde.paginas(publicado=True) if p.name[:2].isdigit()]
        print(f"[prova-de-mockup] {len(self._fila_de_abas)} abas · "
              f"{self.args.voltas_por_aba} voltas de {TIQUE_MS} ms em cada uma")
        return self._proxima_aba()

    def _proxima_aba(self) -> bool:
        if not self._fila_de_abas:
            self._relatar_mockup()
            Gtk.main_quit()
            return False
        self._voltas_da_aba = 0
        self._medindo = False
        # A CARGA DA ABA ANTERIOR NÃO PODE SOBREVIVER À TRAVESSIA: a
        # `07-lancadores` não tem pacote e não produz carga nenhuma, e o que
        # ficasse aqui seria lido como "o pacote da Lançadores declara isto" —
        # os campos da aba anterior, atribuídos a uma aba que não tem dono.
        self._carga_de_agora = {}
        # O `pronto = False` É OBRIGATÓRIO, e a razão é uma armadilha do
        # `_carregou`: quando a aba nova é a MESMA que está à vista (é o caso da
        # primeira), ele volta cedo e não abaixa a bandeira. O tique seguinte
        # pintaria num documento recém-carregado, sem ponte, e contaria a volta.
        self.pronto = False
        self._ir(self._fila_de_abas.pop(0))
        return False

    def _fechou_a_aba(self, pagina: str, valor: Any, erro: Any) -> None:
        """A aba rodou o bastante. Classifica cada campo e segue para a próxima."""
        import json

        if erro is not None:
            self.cegueiras.append(f"{pagina}: não li a tela ao fim — {erro}")
            self._proxima_aba()
            return
        try:
            vivos: list[list[Any]] = json.loads(str(valor))
        except ValueError as e:
            self.cegueiras.append(f"{pagina}: a leitura final não veio em JSON — {e}")
            self._proxima_aba()
            return

        arquivo = onde.pagina(pagina, publicado=True)
        cravados = regua_do_mockup._campos_cravados(arquivo.read_text(encoding="utf-8"))
        self.cravados[pagina] = cravados

        # A GUARDA, E ELA É SOBRE O VIRGEM — não sobre a tela do fim. O DOM
        # ANTES DE QUALQUER PINTURA tem de dizer exatamente o que o arquivo diz:
        # é o parser de Python e o leitor de JS conferidos um contra o outro,
        # endereço a endereço e valor a valor. Se discordarem, a régua está
        # lendo uma coisa e comparando outra — e diria "PRODUTO" sobre um campo
        # que ninguém tocou. Não há como conferir isto sem abrir a página, e é
        # por isso que ela vive aqui e não no teste unitário.
        #
        # NA TELA DO FIM ESTA IGUALDADE NÃO VALE, e supor que valesse foi o
        # primeiro erro desta régua: a pintura TROCA BLOCOS INTEIROS, e a
        # `10-perfis` acabou o passeio com 55 endereços onde o arquivo tem 81.
        # Aquilo não é cegueira — é o produto trabalhando. Quem casa os dois
        # lados é o `_alinhar()`.
        virgem = self.pristino.get(pagina) or []
        if len(virgem) != len(cravados):
            self.cegueiras.append(
                f"{pagina}: o DOM virgem trouxe {len(virgem)} endereços e o "
                f"arquivo {len(cravados)}")
        else:
            for c, linha in zip(cravados, virgem, strict=True):
                k, d, _alvo, v = linha[:4]
                if (str(k), str(d)) != (c.chave, c.dono):
                    self.cegueiras.append(
                        f"{pagina}: o arquivo põe {c.endereco} onde a página "
                        f"virgem põe {d}·{k} — as duas leituras estão fora de ordem")
                elif str(v) != c.valor:
                    self.cegueiras.append(
                        f"{pagina}: a régua lê {c.endereco} como {c.valor!r} no "
                        f"arquivo e a página virgem mostra {v!r} — o parser e o "
                        f"leitor de tela discordam neste alvo ({c.alvo})")

        # O SELO VIAJA JUNTO, e ele é o quinto elemento de cada linha. Vem como
        # `true`/`false` do JSON e é o único que NÃO se converte para texto: o
        # `str(False)` é `'False'`, que é verdadeiro em Python, e isso daria selo
        # a todo campo — todos os 74 indecidíveis viravam PRODUTO de graça.
        alinhados, nasceram = regua_do_mockup._alinhar(
            cravados, [(str(x[0]), str(x[1]), str(x[2]), str(x[3])) for x in vivos])
        selos = regua_do_mockup._selos_alinhados(
            cravados, [(str(x[0]), str(x[1]), str(x[2]), str(x[3]),
                        bool(x[4]) if len(x) > 4 else False) for x in vivos])
        if nasceram:
            print(f"[prova-de-mockup] {pagina}: {len(nasceram)} endereço(s) "
                  f"NASCERAM na tela (o produto trocou um bloco): "
                  f"{', '.join(f'{d}·{k}' if d else k for k, d in nasceram[:8])}")

        if self.args.sem_cravado:
            # A MORDIDA, e ela mora aqui porque é aqui que a cura mora: se o
            # valor cravado deixar de ser o do arquivo, TUDO parece pintado e a
            # régua não acusa mais nada. Uma régua que continue acusando com
            # isto ligado está acusando por outro motivo — e não é a que ela
            # pediu. Vem DEPOIS das duas guardas de propósito: elas conferem a
            # leitura, não a comparação.
            cravados = [dataclasses.replace(c, valor="\x00cura arrancada")
                        for c in cravados]
        declarados = regua_do_mockup._declarados_do_pacote(self._carga_de_agora)
        if self.args.sem_selo:
            # A OUTRA MORDIDA, e ela é do selo: sem ele, todo campo que coincide
            # com o desenho volta a ser INDECIDÍVEL. Uma execução com isto ligado
            # que devolva o MESMO número de indecidíveis está dizendo que o selo
            # não decidiu nada — e aí ele é enfeite, não instrumento.
            selos = [False] * len(cravados)
        self.vereditos[pagina] = regua_do_mockup._classificar(
            cravados, alinhados, declarados, selos)
        contas = regua_do_mockup._contar(self.vereditos[pagina])
        print(f"[prova-de-mockup] {pagina:22s} "
              f"produto {contas[regua_do_mockup.PRODUTO]:3d} · "
              f"mockup {contas[regua_do_mockup.MOCKUP]:3d} · "
              f"indecidível {contas[regua_do_mockup.INDECIDIVEL]:3d}")
        self._proxima_aba()

    def _relatar_mockup(self) -> None:
        """A tabela das três contagens, e a lista NOMINAL do que ainda é desenho."""
        r = regua_do_mockup
        print("\n" + "=" * 74)
        print("A RÉGUA DO MOCKUP — o que a tela mostra é dado, ou é o desenho?")
        print("=" * 74)
        print(f"{'aba':22s} {'campos':>7s} {'PRODUTO':>8s} {'RÓTULO':>7s} "
              f"{'MOCKUP':>7s} {'INDECID':>8s} {'pronto':>7s}")
        soma = {r.PRODUTO: 0, r.ROTULO: 0, r.MOCKUP: 0, r.INDECIDIVEL: 0}
        for pagina in sorted(self.vereditos):
            contas = r._contar(self.vereditos[pagina])
            for classe, quantos in contas.items():
                soma[classe] = soma.get(classe, 0) + quantos
            n = sum(contas.values())
            # PRONTO = PRODUTO + RÓTULO, e a soma é o ponto da categoria nova:
            # rótulo não é dívida, então uma aba com 20 campos escritos e 5
            # rótulos está 100% pronta — não 80%. Sem isto, 100% era
            # inalcançável por construção (decisão dela, 03/09/2026).
            pronto = contas[r.PRODUTO] + contas.get(r.ROTULO, 0)
            print(f"{pagina:22s} {n:7d} {contas[r.PRODUTO]:8d} "
                  f"{contas.get(r.ROTULO, 0):7d} {contas[r.MOCKUP]:7d} "
                  f"{contas[r.INDECIDIVEL]:8d} {(100 * pronto // n) if n else 100:6d}%")
        total = sum(soma.values())
        pronto = soma[r.PRODUTO] + soma[r.ROTULO]
        print(f"{'TODAS':22s} {total:7d} {soma[r.PRODUTO]:8d} "
              f"{soma[r.ROTULO]:7d} {soma[r.MOCKUP]:7d} "
              f"{soma[r.INDECIDIVEL]:8d} {(100 * pronto // total) if total else 100:6d}%")

        print("\nOS CAMPOS QUE AINDA MOSTRAM O DESENHO — é este número que tem de cair:")
        for pagina in sorted(self.vereditos):
            presos = [v for v in self.vereditos[pagina] if v.classe == r.MOCKUP]
            if not presos:
                print(f"  {pagina}: nenhum")
                continue
            print(f"  {pagina} ({len(presos)}):")
            for preso in presos:
                marca = " ← ENDEREÇO MORTO" if preso.declarado is not None else ""
                print(f"      {preso.campo.endereco:28s} = {preso.vivo!r}{marca}")

        # O QUE O SELO DECIDIU, e a conta é ESTREITA de propósito: só os campos
        # em que a tela continua IGUAL ao arquivo. Contar todo PRODUTO cujo
        # declarado bate com o vivo daria 222 — a maioria são campos que a
        # pintura MUDOU, e esses já eram decididos pelo valor. Errei essa conta
        # uma vez e o relato publicou 222 onde a diferença é 74.
        coincidem = sum(
            1 for vs in self.vereditos.values() for v in vs
            if v.classe == r.PRODUTO and v.vivo == v.campo.valor
            and v.declarado is not None and v.declarado == v.vivo)
        if coincidem:
            print(f"\nDESTES, {coincidem} SÃO PRODUTO PELO SELO DA VISITA: o valor que o "
                  "piloto\nescreveu COINCIDE com o que o desenho cravou, e antes do selo "
                  "isso\nera INDECIDÍVEL. O selo não é a tela — é o `escrever()` "
                  "registrando\nque esteve naquele elemento com aquele valor. Para "
                  "conferir que ele\ndecide alguma coisa: `--sem-selo` tem de devolvê-los "
                  "aos indecidíveis.")
        if soma[r.INDECIDIVEL]:
            print(f"\nOS {soma[r.INDECIDIVEL]} INDECIDÍVEIS que SOBRAM são campos em que o "
                  "valor coincide\ncom o desenho e o piloto NÃO passou pelo elemento — "
                  "quase sempre\num bloco que a pintura trocou inteiro. Ler a tela não "
                  "separa\n'pintou igual' de 'não pintou', e a régua prefere dizer "
                  "quantos são\na inventar certeza.")

        if self.cegueiras:
            print(f"\nA RÉGUA NÃO ENXERGOU {len(self.cegueiras)} coisa(s) — e isso reprova, "
                  "porque\numa régua que não sabe o que está lendo mede o que quiser:")
            for cegueira in self.cegueiras:
                print(f"   · {cegueira}")
            raise SystemExit(1)
        if 0 <= self.args.teto_de_mockup < soma[r.MOCKUP]:
            print(f"\nREPROVA: {soma[r.MOCKUP]} campos no desenho, e o teto pedido "
                  f"era {self.args.teto_de_mockup}.")
            raise SystemExit(1)

    def _provar_cliques(self) -> bool:
        """Cliques SINTÉTICOS nos gestos INÓCUOS, para provar o caminho.

        `el.click()` percorre o MESMO caminho de eventos do clique do rato — o
        ouvinte delegado do bootstrap é o que responde. Clicar por coordenada é
        a armadilha que esta casa já pagou duas vezes, e a janela é Offscreen.

        SÓ OS INÓCUOS, e a lista é curta de propósito: `atualizar` é
        `daemon.reload` e `retomar` é `daemon.resume` num daemon que não está
        pausado. `desligar`, `restaurar-de-fabrica` e `refazer-proton` NÃO
        entram — uma régua não mexe na máquina dela para provar que sabe clicar.

        **E ATÉ 06/09/2026 ESSA FRASE ERA SÓ UMA FRASE.** Este caminho clicava o
        que a bandeira nomeasse, sem consultar `PERIGOSOS` uma única vez — só o
        `--prova-no-aparelho` a consultava. Achado pela `ONDA5-03-02`, que
        mediu o próprio estrago: o clique dela **gravou no perfil real** da dona
        (a gravação foi no-op — o valor já era o mesmo desde as 02:46, e nenhum
        arquivo nasceu no `.historico/` — mas a porta estava aberta e nenhum
        agente sabia). É a terceira vez em quatro dias que o comentário que
        AVISA do risco fica ao lado do código que o comete.

        A recusa é BARULHENTA e não um pulo em silêncio: uma régua que pula
        calado ensina quem a roda que ela cobriu o botão. `--incluir-perigosos`
        continua sendo a porta, e aí é escolha de quem roda.
        """
        proibidos = sorted(
            g for g in dict.fromkeys(self.args.prova_clique.split(","))
            if (self.pagina, g.strip()) in PERIGOSOS)
        if proibidos and not self.args.incluir_perigosos:
            print(f"[prova] RECUSA: {', '.join(proibidos)} mexe(m) na máquina "
                  f"dela em {self.pagina}. Use --incluir-perigosos se for "
                  "mesmo isso que você quer.", file=sys.stderr)
            raise SystemExit(1)
        # O PRIMEIRO CLIQUE ESPERAVA UM RELÓGIO, e o relógio estava errado.
        # Medido em 01/09/2026: com `--prova-clique "ver-plugins,ver-detalhes"`
        # só o SEGUNDO saía no relato; sozinho, cada um saía. Aos 600 ms o
        # `BOOTSTRAP` ainda não instalou nesta página, e o `el.click()` acha o
        # botão mas não há ouvinte para responder — o clique some, calado.
        #
        # A cura não é aumentar o número: é PERGUNTAR se a página está pronta.
        # Um prazo maior continuaria sendo uma aposta sobre a máquina de quem
        # roda, e a régua voltaria a perder o primeiro gesto na primeira máquina
        # mais lenta que esta.
        def clicar(g: str) -> bool:
            if not self.pronto:
                return True  # ainda não; o GLib chama de novo no próximo tique
            self._js(SELETOR % (g, g, g, g))
            return False

        for i, gesto in enumerate(self.args.prova_clique.split(",")):
            GLib.timeout_add(600 + i * 900, lambda g=gesto: clicar(g))
        return False

    def _js(self, script: str) -> None:
        self.ponte.rodar(script)

    def _provar_no_aparelho(self) -> bool:
        """A PROVA BOTÃO A BOTÃO, no aparelho dela — pedido dela, 01/09/2026.

        *"no aparelho por favor valida botão a botão tá bom?"*

        E ela está certa sobre o que basta: `[gesto] → aplicado` só prova que a
        função rodou sem levantar. O que prova de verdade é o ESTADO DO DAEMON
        MUDAR — e é o que este modo mede, um gesto por vez:

            lê o estado → clica → espera → lê de novo → diz o que mudou

        Um gesto que aplica e não muda nada aparece como `SEM EFEITO`, que é
        informação e não falha: pode ser um botão que já estava no valor pedido.
        O que ele nunca faz é passar por sucesso calado.
        """
        arquivo = onde.pagina(self.pagina, publicado=True)
        texto = arquivo.read_text(encoding="utf-8")
        da_pagina = regua_do_mockup._gestos_cravados(texto)
        # O `"*"` ENTRA, e sem ele o relato acusa mentira: os quatro botões do
        # rodapé (Aplicar · Salvar · Importar · Exportar) moram no `topo.html`,
        # o esqueleto das dez, e por isso se registram em `("*", nome)` — é o
        # mesmo coringa que o `pacotes.gesto_da_pagina` consulta. Sem esta
        # metade, a régua os listaria como "ninguém os ligou" em TODAS as dez
        # abas, e a primeira execução deste bloco fez exatamente isso.
        registrados = {n for (p, n) in pacotes.GESTOS if p in (self.pagina, "*")}
        perigosos = set() if self.args.incluir_perigosos else PERIGOSOS
        alvos, pulados = regua_do_mockup._alvos_a_clicar(
            da_pagina, registrados, self.pagina, perigosos)
        # A COBERTURA É CONFERIDA ANTES DO PRIMEIRO CLIQUE, e ela é o que faz
        # esta prova deixar de mentir. Em 29/08/2026 o `--prova-gesto` da aba
        # Controles deu VERDE sobre dois botões MORTOS: ele clicava o que o
        # CÓDIGO registrava, e os dois botões novos existiam só na PÁGINA.
        # *Uma validação de interface que não cobre o botão novo é uma validação
        # que mente.*
        faltou = regua_do_mockup._cobertura_dos_gestos(
            da_pagina, registrados, alvos, pulados)
        if faltou:
            print(f"[prova] REPROVA: {len(faltou)} endereço(s) clicável(is) de "
                  f"{self.pagina} ficaram de fora: {', '.join(faltou)}", file=sys.stderr)
            raise SystemExit(1)
        so_na_pagina = sorted({g.nome for g in da_pagina} - registrados)
        so_no_codigo = sorted(registrados - {g.nome for g in da_pagina})
        papeis = sorted({g.nome for g in regua_do_mockup._papeis_cravados(texto)}
                        - registrados)
        print(f"[prova] {self.pagina}: {len(da_pagina)} endereços na página · "
              f"{len(registrados)} registrados no código")
        if so_na_pagina:
            print(f"[prova] SÓ NA PÁGINA (ninguém os ligou): {', '.join(so_na_pagina)}")
        if so_no_codigo:
            print(f"[prova] SÓ NO CÓDIGO (a página não tem `data-gesto`): "
                  f"{', '.join(so_no_codigo)}")
        if papeis:
            print(f"[prova] `data-papel` que o ouvinte aceita como gesto e nenhum "
                  f"pacote registra: {', '.join(papeis)}")
        if pulados:
            print(f"[prova] pulados por mexerem na máquina dela: {', '.join(pulados)}")
        if not alvos:
            print(f"[prova] {self.pagina} não tem gesto seguro a clicar")
            return False
        print(f"[prova] {len(alvos)} gesto(s) em {self.pagina}: {', '.join(alvos)}")
        # UMA FILA SERIAL, e não timers fixos. Com `timeout_add` de intervalo
        # constante os gestos se ATROPELAM: `daemon.reload` leva 9,5 s e o
        # intervalo era 2,5 — o segundo gesto começava com o primeiro no ar, o
        # `_antes_do_gesto` (que é um só) era sobrescrito, e o relato saiu com
        # `retomar` DUAS vezes e `perfil-da-mesa` nenhuma. Medido em 01/09.
        #
        # Cada gesto agenda o próximo quando o SEU termina. O relato passa a ter
        # uma linha por gesto, na ordem, e nenhuma medição pega o efeito da
        # anterior.
        self._fila = list(alvos)
        GLib.timeout_add(400, self._proximo_da_fila)
        return False

    def _proximo_da_fila(self) -> bool:
        """O próximo gesto da prova no aparelho.

        O `False` É O CONTRATO DO GLib — "não me chame de novo" —, e ele passou a
        ser dito AQUI em 01/09/2026. Antes cada sítio de chamada montava
        `(self._proximo_da_fila(), False)[1]`: uma tupla feita para se jogar
        fora o primeiro item, que obriga quem lê a saber de cor que o método
        devolve `None`. Os cinco callbacks desta classe seguem a mesma regra.
        """
        if self._fila:
            self._um_botao(self._fila.pop(0))
        return False

    def _um_botao(self, nome: str) -> None:
        """Um gesto: fotografa o daemon, clica NO ALVO CERTO, e mede o que mudou."""
        try:
            antes = _achatar(mesa_viva.estado_do_daemon())
        except Exception as e:
            print(f"[prova] {nome}: não li o daemon antes ({e})", file=sys.stderr)
            self._proximo_da_fila()
            return
        self._antes_do_gesto = (nome, antes)
        self.desfechos.pop(f"{self.pagina}:{nome}", None)
        # OS CONECTADOS, NA ORDEM DA MESA — e é isto que faltava. Sem alvo, sete
        # gestos da aba Conexões recusaram CORRETAMENTE em 02/09/2026 e o
        # instrumento os contou entre os dezesseis "aplicado e nada mudou".
        # O JS devolve ONDE clicou; o `_onde_clicou` guarda para o relato.
        prefs = [c["pref"] for c in self._mesa_de_agora if c.get("pref")]

        def anotou(valor: Any, erro: Any) -> None:
            self._onde_clicou[nome] = (
                f"o clique falhou: {erro}" if erro is not None else str(valor))

        self.ponte.perguntar(CLIQUE_COM_ALVO % (_json(nome), _json(prefs)), anotou)
        # A ESPERA É OBRIGATÓRIA e não é folga: o daemon escreve no aparelho e
        # só então republica o estado. Medir na hora leria o valor VELHO e diria
        # "sem efeito" sobre um botão que funcionou.
        #
        # E ELA É POR GESTO: o `TETOS` da ponte diz que `daemon.reload` leva 15 s
        # e `gamepad.emulation.set` 2 — esperar o mesmo para os dois faz o
        # instrumento medir antes de o lento terminar, e ler "sem efeito".
        from pacotes import ponte as _p

        espera = max(self.args.espera, int(_p.teto(_METODO_DO_GESTO.get(nome, "")) * 1000) + 800)
        GLib.timeout_add(espera, self._depois_do_gesto)

    def _depois_do_gesto(self) -> bool:
        # O TIPO É DITO, e não inferido do `{}`: o padrão do `getattr` faz o
        # `mypy` ler `antes` como um dicionário VAZIO e sem chaves, e aí
        # `antes.get("qualquer coisa")` vira erro de sobrecarga.
        nome, antes = getattr(self, "_antes_do_gesto", (None, {}))
        antes_do_daemon: dict[str, Any] = dict(antes)
        if nome is None:
            return False
        try:
            depois = _achatar(mesa_viva.estado_do_daemon())
        except Exception as e:
            print(f"[prova] {nome}: não li o daemon depois ({e})", file=sys.stderr)
            self._proximo_da_fila()
            return False
        mudou = {k: (antes_do_daemon.get(k), v) for k, v in depois.items()
                 if antes_do_daemon.get(k) != v
                 and not any(r in k for r in RUIDO)}
        # SEM ECO NÃO É SEM EFEITO, e confundir os dois é o que faria esta régua
        # acusar um botão que funciona. O `state_full` do daemon não publica
        # gatilho — o DualSense não devolve o modo em que está, é comando de ida
        # — então um `trigger.set` aceito não muda campo nenhum aqui.
        #
        # Quem declara isso é o PACOTE, em `SEM_ECO`, e a prova daqueles gestos
        # é outra: o gesto usa a porta `_detalhado`, que levanta quando o daemon
        # recusa. Chegar a "aplicado" já é o daemon ter aceitado.
        sem_eco = nome in self._sem_eco_da_pagina()
        # OS TRÊS DESFECHOS, e antes de 02/09/2026 os três saíam iguais. O que
        # o daemon publica não distingue *recusou dizendo* de *não fez nada* —
        # nos dois casos o estado fica igual. Quem sabe a diferença é o próprio
        # gesto, e agora ele deixa dito em `self.desfechos`.
        desfecho, frase = self.desfechos.get(f"{self.pagina}:{nome}", ("aplicou", ""))
        onde_ = self._onde_clicou.get(nome, "")
        self.provas.append({"gesto": nome, "mudou": mudou, "sem_eco": sem_eco,
                            "desfecho": desfecho, "frase": frase, "onde": onde_})
        cabeca = f"[PROVA] {self.pagina} · {nome}"
        if onde_:
            cabeca += f" ({onde_})"
        if desfecho == "sem dono":
            print(f"{cabeca} → SEM DONO: nenhum pacote registra este gesto")
        elif desfecho == "recusou dizendo":
            # RECUSAR DIZENDO É O COMPORTAMENTO CERTO, e contá-lo como falha
            # é o que fez a medição de 02/09 acusar sete botões que estavam
            # certos. `ValueError` = clique inválido; `RuntimeError` = o
            # produto recusou, e a frase vai para a tela.
            print(f"{cabeca} → RECUSOU DIZENDO: {frase}")
        elif mudou:
            print(f"{cabeca} → MUDOU {len(mudou)} campo(s):")
            for k, (a, d) in sorted(mudou.items())[:6]:
                print(f"          {k}: {a!r} → {d!r}")
        elif sem_eco:
            print(f"{cabeca} → ACEITO, sem eco no state "
                  f"(o daemon não publica este assunto)")
        else:
            print(f"{cabeca} → DISSE APLICADO E NADA MUDOU no estado do daemon")
        return self._proximo_da_fila()

    def _sem_eco_da_pagina(self) -> set[str]:
        """Os gestos daquela aba cujo efeito o daemon não publica.

        O CHIP DA FITA ENTRA NAS DEZ, e não é isenção de conveniência: ele
        ESCOLHE quem a aba mira e, por contrato, não fala com o daemon. Sem esta
        linha a prova botão a botão o classificaria como *"disse aplicado e nada
        mudou"* — a mesma frase com que ela nomeia dezesseis botões mortos —
        sobre o único gesto desta casa que promete não mexer no aparelho.
        """
        import importlib

        sem_eco = {monta.GESTO_DA_FITA}
        for arq in sorted((AQUI / "pacotes").glob("a[0-9][0-9]_*.py")):
            mod = importlib.import_module(f"pacotes.{arq.stem}")
            if getattr(mod, "PAGINA", "") == self.pagina:
                return sem_eco | set(getattr(mod, "SEM_ECO", ()))
        return sem_eco

    def _ir(self, pagina: str) -> bool:
        """Abre uma aba. `False` para o GLib — ver `_proximo_da_fila`."""
        alvo = onde.pagina(_a_pagina_pedida(pagina), publicado=True)
        if not alvo.exists():
            # ARQUIVO QUE NÃO EXISTE NÃO É NAVEGAÇÃO: o WebKit carrega a
            # página de erro DELE, o piloto segue o passeio e o relatório sai
            # com a tabela das dez abas zerada — verde sobre o vazio.
            # MEDIDO EM 05/09/2026 com `--abre 10`: a foto saiu com "Error
            # opening file .../paginas/10" e o comando devolveu rc=0.
            self.tela._morrer(f"não existe a página pedida: {alvo.name}")
            return False
        self.view.load_uri(alvo.as_uri())
        return False

    def _relatar(self) -> bool:
        # UMA VEZ SÓ. O `_agendar` roda no `_instalado`, que dispara a cada
        # carga de página; sem esta trava o passeio agendava dez saídas e o
        # relato saía repetido — dois "foto:" no log de 01/09.
        if self.relatou:
            return False
        self.relatou = True
        if self.args.foto:
            # `fotografar()` JÁ IMPRIME o caminho — a linha que estava aqui era
            # a segunda, e foi ela que fez o log de 01/09 mostrar dois "foto:"
            # e parecer que o relato rodava duas vezes. Não rodava.
            self.tela.fotografar(self.args.foto)
        print(f"\nvoltas: {self.voltas} · abas visitadas: {len(self.visitadas)}")
        print(f"{'aba':22s} {'tiques':>7s} {'pinturas':>8s} {'valores':>8s}")
        mudas = []
        for pagina in sorted(pacotes.PACOTES):
            conta = self.pinturas.get(pagina) or []
            pico = max(conta) if conta else 0
            tiques = self.tiques.get(pagina, 0)
            print(f"{pagina:22s} {tiques:7d} {len(conta):8d} {pico:8d}")
            # A ABA MUDA É A QUE RODOU E NUNCA ESCREVEU UM VALOR. Antes esta
            # linha perguntava `pico == 0` sobre uma lista em que o zero nunca
            # entrava — era ramo morto. Agora `tiques` conta o tique e
            # `pinturas` conta só quem escreveu, e a diferença entre os dois é o
            # fato: pacote com endereço que não casa.
            if tiques and not conta:
                mudas.append(pagina)
        # AS TROCAS SAEM NO RELATO, e não ficam num contador que ninguém lê: um
        # `-1` é a página tendo trocado no meio do tique, e ver muitos deles é
        # ver o passeio andando rápido demais para a pintura acompanhar.
        if self.trocas:
            print("página trocada no meio do tique: " + " · ".join(
                f"{p} {n}" for p, n in sorted(self.trocas.items())))
        if self.provas:
            def classe(p: dict[str, Any]) -> str:
                if p.get("desfecho") == "sem dono":
                    return "sem dono"
                if p.get("desfecho") == "recusou dizendo":
                    return "recusou dizendo"
                if p["mudou"]:
                    return "mudou o daemon"
                if p["sem_eco"]:
                    return "aceito sem eco"
                return "disse aplicado e nada mudou"

            marcas = {"mudou o daemon": "✓", "aceito sem eco": "·",
                      "recusou dizendo": "!", "sem dono": "?",
                      "disse aplicado e nada mudou": "—"}
            contas: dict[str, int] = {}
            for p in self.provas:
                contas[classe(p)] = contas.get(classe(p), 0) + 1
            print("\nPROVA NO APARELHO: " + " · ".join(
                f"{n} {k}" for k, n in sorted(contas.items())))
            for p in self.provas:
                k = classe(p)
                extra = f" — {p['frase']}" if p.get("frase") else ""
                onde_ = f" ({p['onde']})" if p.get("onde") else ""
                print(f"   {marcas[k]} {p['gesto']}{onde_}{extra}")
            mudos = [p["gesto"] for p in self.provas
                     if classe(p) == "disse aplicado e nada mudou"]
            if mudos:
                # UM GESTO MUDO E NÃO DECLARADO é o que esta régua persegue: ou
                # ele não faz nada, ou faz algo que o daemon não conta e ninguém
                # escreveu isso. As duas coisas precisam de alguém.
                print(f"   sem efeito e sem `SEM_ECO`: {', '.join(mudos)}")
            forcados = [p["gesto"] for p in self.provas
                        if str(p.get("onde", "")).startswith("ALVO FORCADO")]
            if forcados:
                # O ALVO EMPRESTADO NÃO É O PRODUTO FUNCIONANDO: estes botões
                # não dizem em qual aparelho agem, e sem a régua emprestando um
                # eles só podem recusar. É defeito da PÁGINA, e está nomeado.
                print(f"   alvo FORÇADO pela régua (a página não diz em quem "
                      f"agir): {', '.join(forcados)}")
        if self.gestos:
            print(f"gestos: {len(self.gestos)} · aplicados: {len(self.aplicados)} · "
                  f"sem dono: {len(set(self.recusados))}")
            for r in sorted(set(self.recusados)):
                print(f"   sem dono: {r}")
        if self.custos:
            ordenado = sorted(self.custos)
            print(f"custo do tique: mediana {ordenado[len(ordenado)//2]:.2f} ms · "
                  f"max {ordenado[-1]:.2f} ms · teto {TIQUE_MS} ms")
        if self.custo_do_ipc:
            # AS DUAS VIAGENS À PARTE, e é o número que decide se o teto é do
            # piloto ou do daemon: um `estado()` que custa mais que o tique é
            # dívida do outro lado do socket, e esta linha é a que a nomeia.
            ipc = sorted(self.custo_do_ipc)
            print(f"custo do IPC:   mediana {ipc[len(ipc)//2]:.2f} ms · "
                  f"max {ipc[-1]:.2f} ms")
        if self._pulados_por_voo or self._pulados_por_custo:
            print(f"tiques pulados: {self._pulados_por_voo} com pintura no ar · "
                  f"{self._pulados_por_custo} pelo custo do anterior")
        if mudas:
            # ZERO É ERRO, NÃO SILÊNCIO. Uma aba que foi visitada, tem pacote e
            # escreveu zero valores é endereço que não casou — e essa é a forma
            # exata do defeito que deixou a `06-navegacao` publicar sem
            # endereço nenhum.
            print(f"\nABAS MUDAS (pacote sem endereço que case): {', '.join(mudas)}")
            raise SystemExit(1)
        return False


def _json(obj: Any) -> str:
    """Serializa para o WebView — e RECUSA o que ela mandou tirar da tela.

    Este é o funil: **todo** valor que chega ao `WebKit2.WebView` passa aqui, a
    pintura e a resposta de gesto. Por isso a guarda de execução das frases
    banidas mora neste ponto e não em cada aba — uma guarda por aba seriam dez
    guardas a divergir, e a décima primeira aba nasceria sem nenhuma.

    POR QUE ELA LEVANTA em vez de limpar: as três frases são constantes
    LITERAIS que já estiveram no produto (`frases_que_ela_baniu`). Código que as
    produz é defeito, não gosto — e limpar produziria uma frase mutilada na tela
    dela, que é pior que o vermelho. O OITAVO CONFLITO de 04/09/2026 nasceu
    exatamente de uma proibição que sabia recusar, mas recusava no LUGAR ERRADO:
    ela lia o HTML estático, e a coluna Atenção é escrita em execução.
    """
    import json

    # E O FUNIL PASSOU A OLHAR AS DUAS LISTAS — costura da ONDA E, 06/09/2026.
    #
    # Ele chamava só `frase_banida_em`, e isso foi decidido — não esquecido — no
    # dia em que a palavra "mesa" saiu da tela: `_json` LEVANTA, e é por ele que
    # todo valor passa a caminho do WebView. Enquanto DEZESSEIS frases de `app/`
    # ainda diziam a palavra, ligá-lo aqui trocaria uma palavra feia por uma
    # JANELA MORTA — e `app/` era o `nao_toca` de quem mediu.
    #
    # As dezesseis foram curadas no dono nesta mesma costura, e a condição que a
    # `A-PALAVRA-MESA-SAI-01` deixou escrita está cumprida. `primeiro_trecho_banido`
    # consulta as duas listas — a das frases que ela baniu e a das palavras —, e
    # é uma linha, como a sprint mediu.
    from hefesto_dualsense4unix.interface.frases_que_ela_baniu import (
        primeiro_trecho_banido,
    )

    saida = json.dumps(obj, ensure_ascii=False, default=str)
    banida = primeiro_trecho_banido(saida)
    if banida is not None:
        raise ValueError(
            f"um texto banido ia para a tela dela: {banida!r}. "
            "Ela, 31/08/2026: NENHUM ALARME SEM MEDIÇÃO — as três frases "
            "alarmavam sobre número que ensaio nenhum deste repositório mede. "
            "A coluna Atenção pode dizer o ESTADO MEDIDO; não pode profetizar "
            "consequência. Ver `interface/frases_que_ela_baniu.py`."
        )
    return saida


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--oculta", action="store_true",
                   help="Gtk.OffscreenWindow — nada aparece na tela dela. "
                        "Ela tem UMA tela; é o padrão de toda régua desta casa.")
    p.add_argument("--segundos", type=float, default=0.0,
                   help="fecha a janela depois de N segundos e relata. ZERO (o "
                        "padrão) mantém a janela aberta até ela fechar — que é "
                        "o comportamento do PRODUTO. Só a bancada põe prazo.")
    p.add_argument("--passear", action="store_true",
                   help="visita as dez abas e mede a pintura de cada uma")
    p.add_argument("--parada", type=int, default=900,
                   help="ms em cada aba durante o passeio")
    p.add_argument("--foto", default="")
    p.add_argument("--abre", default="",
                   help="abrir direto numa aba: o número (`10`), o nome sem "
                        "extensão (`10-perfis`) ou o arquivo "
                        "(`10-perfis.html`). Página que não existe REPROVA")
    p.add_argument("--prova-no-aparelho", action="store_true",
                   help="clica CADA gesto da aba, um por vez, e mede o que mudou "
                        "no estado do daemon — a prova que ela pediu")
    p.add_argument("--entre", type=int, default=2500,
                   help="ms entre um gesto e o próximo")
    p.add_argument("--espera", type=int, default=1200,
                   help="ms entre o clique e a leitura do daemon")
    p.add_argument("--incluir-perigosos", action="store_true",
                   help="inclui os gestos que mexem na máquina dela (desligar, "
                        "reiniciar, restaurar) — escolha de quem roda")
    p.add_argument("--prova-clique", default="",
                   help="lista de gestos a clicar, separada por vírgula — "
                        "eles chegam ao daemon de verdade")
    p.add_argument("--sem-cor", action="store_true",
                   help="MORDIDA: sem o leitor de cor do plástico")
    p.add_argument("--sem-ondas", action="store_true",
                   help="MORDIDA: arranca o medidor de áudio das ondas sonoras "
                        "da aba 02. As catorze barrinhas de cada medidor têm de "
                        "ACHATAR e ficar cinza — se continuarem desenhando a "
                        "onda do arquivo, elas nunca foram dado")
    p.add_argument("--prova-de-mockup", action="store_true",
                   help="passa pelas dez abas e diz, campo a campo, o que é DADO "
                        "e o que ainda é o DESENHO cravado no arquivo")
    p.add_argument("--voltas-por-aba", type=int, default=8,
                   help="quantos tiques a pintura corre em cada aba antes da "
                        "medição. Uma volta só mede um INSTANTE, não um "
                        "comportamento — o padrão dá 4 s por aba")
    p.add_argument("--teto-de-mockup", type=int, default=-1,
                   help="reprova se mais de N campos ainda mostrarem o desenho. "
                        "NEGATIVO (o padrão) só mede e relata — é assim que ele "
                        "vira catraca quando o número começar a cair")
    p.add_argument("--sem-cravado", action="store_true",
                   help="MORDIDA: arranca a comparação com o arquivo publicado e "
                        "compara a tela com ela mesma. A régua tem de parar de "
                        "acusar — se continuar acusando, ela não mede o que diz")
    p.add_argument("--sem-selo", action="store_true",
                   help="MORDIDA: arranca o selo da visita. Os campos que "
                        "coincidem com o desenho voltam a ser INDECIDÍVEIS — e "
                        "se o número não voltar, o selo não estava decidindo nada")
    p.add_argument("--conta-mutacoes", type=int, default=0, metavar="N",
                   help="conta as mutações de DOM em N tiques COM A MESA "
                        "PARADA, por endereço e por tipo, e sai. O número certo "
                        "é ZERO para tudo o que não mudou de valor — o que "
                        "sobrar é a tela sambando")
    args = p.parse_args()

    if args.conta_mutacoes and not args.oculta:
        # MESMA RAZÃO DO `--prova-de-mockup` LOGO ABAIXO: ela tem UMA tela, e
        # esta régua fica minutos com a janela aberta medindo o que não muda.
        print("[conta-mutações] ligando `--oculta`: ela tem UMA tela.")
        args.oculta = True

    if args.prova_de_mockup and not args.oculta:
        # ELA TEM UMA TELA. Uma régua que passeia por dez abas piscando na
        # frente dela quebra o que ela está fazendo — e nenhum ganho de medição
        # paga isso. Aqui a bandeira se acende sozinha, e diz que se acendeu.
        print("[prova-de-mockup] ligando `--oculta`: esta régua abre dez abas e "
              "ela tem UMA tela.")
        args.oculta = True

    # AS ONDAS SONORAS SÓ MEDEM AQUI, e a trava é deliberada. O medidor de
    # `integrations/ondas_de_som.py` nasce DESLIGADO porque a suíte chama
    # `a02_controles.pacote()` centenas de vezes, e um fluxo de captura aberto a
    # cada chamada seguraria o microfone DELA aberto durante a suíte inteira.
    # O piloto é o produto; é ele quem autoriza.
    from hefesto_dualsense4unix.integrations import ondas_de_som

    ondas_de_som.ligar(not args.sem_ondas)

    piloto = Piloto(args)

    def _quando_a_pagina_estiver_de_pe(tarefa: Callable[[], Any]) -> None:
        """Agenda ``tarefa`` para o instante em que a PÁGINA confirmar — não o relógio.

        MEDIDO EM 04/09/2026: com um `timeout_add` fixo, quem navegava antes de
        a carga inicial confirmar recebia a confirmação com o título VAZIO —
        `carregou OUTRA página: título ''`. A janela morria, e a régua saía
        **rc=0 sem medir nada**.

        **A CURA NASCEU APLICADA A UMA DAS QUATRO, e as outras três ficaram com
        o relógio — 05/09/2026.** `--abre 10 --foto` reproduzia o mesmo
        `título ''` em toda execução: `_ir` disparava aos 400 ms, antes de a
        primeira página confirmar. Uma cura que conhece a causa e cobre um
        chamador só deixa a próxima pessoa remedindo o mesmo defeito — foi o
        que aconteceu com a frente da aba 10, que teve de escrever um driver
        próprio.

        O relógio era a suposição; `na_aba` é o FATO. É a mesma lição do
        `_confirmar_a_pagina` um andar abaixo: *quem diz que a carga deu certo
        é a PÁGINA, não o evento nem o URI* — e não é o cronômetro.
        """

        def _tique() -> bool:
            if piloto.tela.morreu is not None:
                return False  # a janela já morreu; o rc de `main` acusa
            if not piloto.tela.na_aba:
                return True   # ainda não confirmou: volta no próximo tique
            tarefa()
            return False

        GLib.timeout_add(120, _tique)

    if args.prova_de_mockup:
        _quando_a_pagina_estiver_de_pe(piloto._provar_mockup)
    if args.prova_no_aparelho:
        # A ESPERA EXTRA CONTINUA, e é outra coisa: a página de pé não quer
        # dizer daemon respondido. Estes 2,5 s são para o primeiro tique pintar
        # antes de alguém clicar no que ele pintou.
        _quando_a_pagina_estiver_de_pe(
            lambda: GLib.timeout_add(2500, piloto._provar_no_aparelho))
    if args.prova_clique:
        _quando_a_pagina_estiver_de_pe(
            lambda: GLib.timeout_add(2000, piloto._provar_cliques))
    if args.abre:
        _quando_a_pagina_estiver_de_pe(lambda: piloto._ir(args.abre))
    Gtk.main()

    # O RC DIZ A VERDADE SOBRE A MEDIÇÃO — e é o que faltava.
    #
    # Uma régua que imprime `ERRO DE CARGA` e sai `rc=0` é pior que régua
    # nenhuma: quem a chama num portão lê verde. Achado em 04/09/2026 pela
    # frente da aba 10, que precisou escrever um driver próprio porque este
    # não mediu nada.
    #
    # Vale para as TRÊS provas, não só para a que falhou: o defeito é da forma
    # de sair, não da régua que o revelou.
    #
    # **E VALE PARA TODA EXECUÇÃO — 05/09/2026.** O gate era `e_regua`, e por
    # isso `--abre 99` imprimia `ERRO DE CARGA` e saía rc=0: quem chamasse o
    # piloto num script leria verde sobre uma janela morta. Página que morreu é
    # execução que falhou, com ou sem régua ligada; a diferença entre os dois
    # casos é só a FRASE, e ela continua abaixo.
    if piloto.tela.morreu is not None:
        print(f"\nREPROVA: a página morreu e nada foi medido — {piloto.tela.morreu}",
              file=sys.stderr)
        raise SystemExit(1)
    if args.prova_de_mockup and not piloto.visitadas:
        # ZERO É ERRO, NÃO SILÊNCIO — a mesma regra que o `_relatar` já aplica
        # às abas mudas, aqui aplicada à régua inteira.
        print("\nREPROVA: `--prova-de-mockup` não visitou aba nenhuma.",
              file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
