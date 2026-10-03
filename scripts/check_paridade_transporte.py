#!/usr/bin/env python3
"""Censo do mapa de canais: reprova a AUSÊNCIA de rede em volta do que o mapa afirma.

É a CAMADA 0 do portão desenhado em
o registro «INDICE-o-mapa-que-vira-portao» de 10/08/2026 (seções 4 e 6,
sprint PARIDADE-PORTAO-01). Roda no CI, sem hardware, e responde uma pergunta
só: **o que este mapa afirma tem teste que morda?**

Por que ele existe
------------------
O mapa nasceu com a frase "o mapa de canais existe, e ele é portão — não
documentação". Medido em 11/08/2026: não era. O `--check` do `gerar-mapa.py`
existia e NINGUÉM o chamava — nem workflow, nem hook, nem teste. Pela régua da
casa (PORTÃO-VIVO-01), um gate que ninguém roda não é gate, é arquivo.

E o defeito que o mapa foi feito para pegar é o dela, textual: *"tínhamos algo
para o cabo e na hora do vamos ver a versão de BT não funcionava"*. Uma célula
que diz `aciona = sim, medido` e não aponta um teste é exatamente essa
promessa: se aquela feature quebrar naquele transporte, a suíte inteira
continua verde e ninguém fica sabendo.

O que ele NÃO pega, dito na cara
--------------------------------
Nada aqui toca byte, tempo ou aparelho. O latch da lightbar por rádio (o report
é bem-formado, o CRC bate, e o que separa travar de não travar é o tempo desde
a conexão) passa por este portão sorrindo — quem morde isso são as camadas 1, 2
e 3 do índice. Este arquivo mede AUSÊNCIA, e só.

As regras
---------
FALHA
  1. `sem-mordida`      — célula que afirma `aciona = sim` com
                          `de_onde_sei = medido` e `teste_que_morde` vazio.
                          Afirmação forte sem rede é o defeito-mãe da sprint.
  2. `mordida-fantasma` — `teste_que_morde` que aponta para algo que o pytest
                          NÃO coleta (arquivo, classe ou função que não existe,
                          ou nome fora da convenção de coleta) **ou que ele
                          coleta e que não exercita nada**: corpo vazio (só
                          docstring, `pass` ou `...`) e `skip` incondicional
                          (no teste, na classe ou no `pytestmark` do módulo).
                          A segunda metade é de 26/08/2026 e fecha um buraco
                          estrutural: até então a regra conferia só se o alvo
                          era COLETÁVEL, e um `def test_x(): pass` passa
                          também com a cura arrancada — que é exatamente a
                          rede-que-não-existe que a regra 1 existe para pegar.
                          `skipif` com condição de verdade continua valendo:
                          é honestidade, não teste desligado.
                          Conferido por LEITURA DE AST de `tests/`, nunca
                          executando a suíte: o portão precisa rodar num
                          runner pelado, e um `ImportError` viraria "zero
                          testes" — o que faria a regra acusar todo mundo.
  3. `prova-vencida`    — `provado_em` + `validade_dias` já no passado. Se as
                          DUAS colunas estiverem vazias, não reprova: a política
                          de validade ainda é decisão dela, e portão que castiga
                          a honestidade é pior que portão nenhum. Data ilegível
                          ou `validade_dias` não inteiro reprovam, porque uma
                          régua que não se consegue ler é uma regra desligada em
                          silêncio.
  4. `integridade`      — coluna do cabeçalho que sumiu, `id` vazio ou
                          duplicado, valor fora do domínio declarado abaixo.
  5. `mapa-nao-publicado` — linha do CSV cujo `id` não aparece no `specs.html`
                          publicado. Ver a nota sobre ela, logo abaixo.
  6. `grau-sem-ensaio`  — célula que declara um `ate_onde_foi` que a suíte não
                          sustenta sozinha (hoje: `SAIU NO FIO`,
                          `O APARELHO OBEDECEU`, `O JOGO RECEBEU`,
                          `O JOGO REAGIU` — a lista sai de `ESCADA`, nunca de
                          uma cópia) e NÃO tem ensaio nenhum em
                          `docs/data/ensaios.csv` para aquele `id` NAQUELE
                          transporte. Ver "o buraco de 12/08" abaixo.

AVISO (não derruba o CI hoje)
  7. `assimetria-nao-declarada` — `cabo_aciona` e `radio_aciona` divergem (ou um
                          dos dois nem foi respondido) e `assimetria_declarada`
                          está vazia. Começa como AVISO PORQUE O CSV AINDA ESTÁ
                          SENDO PREENCHIDO: hoje a divergência mais comum é
                          "ninguém respondeu esse lado", que é buraco de censo,
                          não mentira do mapa. Promover para FALHA é trocar
                          `ASSIMETRIA_REPROVA` para True — uma linha, no topo
                          deste arquivo — quando as colunas estiverem fechadas.
  8. `validade-sem-data` — `validade_dias` preenchido com `provado_em` vazio:
                          prazo que não se consegue contar.
  9. `grau-sem-ensaio-que-obedeca` — `ate_onde_foi = O APARELHO OBEDECEU` com
                          ensaios naquele lado, mas nenhum deles dizendo que a FEATURE
                          obedeceu. Desde 13/08/2026 quem responde isso é
                          `resultado_da_feature` quando ela está preenchida, e
                          `resultado` quando não (ver "o preço do `resultado`"
                          abaixo). Segue AVISO e não FALHA porque a coluna nova
                          está preenchida em 1 dos 77 ensaios: enquanto os
                          outros 76 responderem por `resultado`, que é texto
                          livre com semântica de suspeito, promover reprovaria
                          afirmação verdadeira. Promoção por `RESULTADO_REPROVA`.
 10. `grau-sem-olho-dela` — o ensaio que sustenta o `O APARELHO OBEDECEU` existe
                          e diz que obedeceu, mas ninguém do `olho-dela` viu.
                          `docs/method/METODO-DE-ISOLAMENTO.md` (seção "o que
                          registrar em cada linha do mapa") diz que só o olho
                          dela sustenta esse degrau. Promoção por
                          `OLHO_DELA_REPROVA`.
 11. `mordida-nao-provada` — linha com grau forte e `teste_que_morde` preenchido
                          cuja `mordida_provada_em` está vazia: ninguém arrancou
                          a cura e viu reprovar. Medido em 12/08/2026: a coluna
                          está vazia em 293 de 293 linhas e nenhuma regra a lia.
 12. `veredicto-da-feature-mal-declarado` — a guarda da coluna nova, e a razão
                          de ela não ser um afrouxamento. DURA, em duas metades:
                          `resultado_da_feature` fora do vocabulário do caderno
                          reprova, e `resultado_da_feature` que DIVERGE de
                          `resultado` com a `nota` do ensaio vazia reprova
                          também. Quem quiser calar a regra 9 escrevendo
                          `obedece` nesta coluna tem de escrever no caderno, na
                          mesma linha, o que o aparelho fez — que é exatamente o
                          que a casa cobra em toda parte.

 13. `reagiu-sem-olho-dela` — `ate_onde_foi = O JOGO REAGIU` com ensaio que
                          sustenta, mas observado por quem não é `olho-dela`.
                          DURA desde o primeiro dia, ao contrário da regra 10, e
                          o motivo é LEGADO, não princípio: o degrau nasceu em
                          19/08/2026 com zero células no CSV, então não há
                          afirmação antiga que uma regra dura possa machucar.
                          Detalhe em `_achado_sem_olho_dela`.

FALHA (as duas mais novas)
  A numeração desta lista é CRONOLÓGICA, não por severidade — é por isso que as
  regras 12 e 13, que também são DURAS, ficaram no bloco de cima. Estas duas
  nasceram em 20/08/2026, e a 14 estava rodando sem ter sido escrita aqui.

 14. `ensaio-nao-diz-o-degrau` — grau de ENTRADA (`O JOGO RECEBEU`,
                          `O JOGO REAGIU`) numa linha que TEM ensaios, sem que
                          nenhum deles declare `degrau` igual ao afirmado. É o
                          buraco irmão do de 12/08: a lição tinha sido aprendida
                          para "nenhum ensaio" e não para "o ensaio errado".
                          Reproduzido à mão — ver o comentário
                          `ENSAIO-QUE-NAO-DIZ-O-DEGRAU-01`, em `_regra_do_caderno`.
 15. `ponte-nao-declarada` — linha que entrega ao jogo por `canal = uhid`, com
                          afirmação forte (`aciona = sim` + `de_onde_sei =
                          medido`) em algum lado, e `ponte_alcanca` VAZIA.

                          O `uhid` é o canal que só existe sob a máscara
                          DualSense do nosso vpad (`054c:0df2`): quem escolhe a
                          máscara Xbox perde essas linhas INTEIRAS, e perde em
                          silêncio — é o cálculo que põe a DualSense no primeiro
                          degrau de `integrations/ponte_escada.py`. Uma célula
                          que diz "medi, e aciona" sem dizer POR QUAL PONTE mede
                          coisa nenhuma: a mesma feature é `sim` sob uma ponte e
                          inexistente sob outra, e o mapa ficaria verde
                          afirmando as duas.

                          VAZIO É "NÃO DECLAROU", NUNCA "SERVE PARA TODA PONTE"
                          — a mesma convenção da coluna `ponte` do caderno de
                          ensaios, escrita no mesmo dia. Por isso a regra só
                          cobra onde a promessa é máxima; a linha `uhid` que não
                          afirma nada continua podendo calar.

                          A régua do DOMÍNIO desta coluna sai da `ESCADA` de
                          `ponte_escada.py`, LIDA POR AST (ver
                          `dominio_das_pontes`) — sem ela "Steam Input",
                          "steam input" e "SteamInput" viram três pontes.

 16. `causa-nao-declarada` — `aciona = não` MEDIDO (`de_onde_sei = medido`) com
                          `*_por_que_nao_aciona` vazia. Nasceu em 24/08/2026
                          (Z6-05): as duas colunas de causa existiam desde
                          22/08/2026 sem NENHUMA regra que as lesse — a mesma
                          família "a casa sabe e o produto não faz", com dois
                          dias de idade. O domínio ganhou o quinto valor,
                          `o-aparelho-recusa` (causa FORA do nosso código) —
                          ver `DOMINIO_POR_SUFIXO["por_que_nao_aciona"]`
                          e `CAUSA_DE_FORA` em
                          `src/hefesto_dualsense4unix/app/fala_do_mapa.py`.

 18. `escada-de-vibracao` — número de multiplicador citado em célula que NÃO
                          bate com `RUMBLE_POLICY_MULT`, lido por AST do dono
                          (`daemon/subsystems/rumble.py`). Nasceu em
                          25/08/2026: duas células contavam a escada
                          `0,3 / 0,7 / 1,0`, de ANTES de 11/08/2026 — dia em que
                          ela a trocou para `0,3 / 1,0 / 1,5`. Corrigir as
                          células sem deixar régua seria faxina, e faxina volta.
                          A regra não guarda número: ela compara com o dono, e a
                          conta de citações vai ao resumo para que um zero
                          (= parou de olhar) apareça sem ninguém desconfiar.

 19. `lado-sem-regua`  — um lado com `aciona` RESPONDIDO, alguma coluna de
                          CONTEÚDO daquele lado escrita (`*_offset`,
                          `*_report_id`, `*_comando`, `*_evidencia`,
                          `*_detalhe`, `*_ressalva`, `*_codigo_ref` — a lista é
                          `SUFIXOS_DE_CONTEUDO`) e o `*_de_onde_sei` daquele
                          lado VAZIO. Nasceu em 31/08/2026, da cegueira medida
                          logo abaixo.
 20. `causa-sem-negativa` — AVISO. `*_por_que_nao_aciona` preenchida num lado
                          cujo `aciona` NÃO é `não`. É a 16 invertida, e nasceu
                          em 06/09/2026 pedida pela A-RECUSA-QUE-CITOU-O-MAPA-01
                          (§4.5). Ela não acusa a célula: acusa a LEITURA que a
                          célula convida. Hoje há UMA no mapa
                          (`movimento.acelerometro@dualsense`, `sim` +
                          `so-ela-decide`), ela está CERTA e a ressalva diz que
                          é de propósito — e é justamente por isso que a regra é
                          AVISO. No mesmo dia, ler uma coluna de causa como veto
                          fez o coordenador mandar um agente PARAR um passo que
                          funciona.

A pergunta que passou a ter DONO — a procedência (06/09/2026)
--------------------------------------------------------------
*De onde se sabe esta célula?* é respondida por `procedencia_da_celula()`, neste
arquivo, e por mais ninguém. Ela devolve os PONTEIROS que se pode seguir — o
carimbo (`provado_em` + `provado_por`), a mordida (`teste_que_morde`), o
endereço (`*_codigo_ref`), a fonte de fora (`fonte_externa`), a evidência com
endereço e o ensaio do caderno —, e quem a cobra é
`tests/unit/test_a_procedencia_da_linha_nao_e_vazia.py`.

A `scripts/mesa_de_medicao.py` monta o **COMO** de cada célula com metade dessas
colunas (`_como_da_celula`). São perguntas irmãs sobre as mesmas colunas, e a
régua da procedência guarda as duas contra a divergência: no dia em que uma
coluna mudar de nome, as duas leituras respondem coisas diferentes CALADAS, e
uma delas passa a mentir. É o defeito que esta casa já pagou duas vezes —
*a régua estava medindo o mundo de ontem*.

A cegueira que a regra 19 fecha — e a metade que ela NÃO fecha (31/08/2026)
--------------------------------------------------------------------------
Medido em duas leituras independentes, numa leva de levantamento em fonte
externa: este portão é **cego ao CONTEÚDO** das colunas sem domínio. Quatro
estragos plausíveis em células recém-escritas passaram com `rc=0` — o byte do
LED de jogador trocado de 11 para 47, o `report[11]` do clique do touchpad
trocado para `report[27]`, uma `fonte_externa` apontando repositório
inexistente, e um `radio_offset` cheio com o `radio_de_onde_sei` esvaziado —
enquanto o CONTROLE POSITIVO (valor fora do domínio em `radio_canal`, data
ilegível em `provado_em`) reprovou com `rc=1`. A régua estava viva; a cegueira
era localizada.

Três dos quatro estragos **continuam passando, e isso é honesto**: nenhum portão
sem hardware e sem rede consegue dizer que o byte é 11 e não 47, ou que um
repositório existe. O que a regra 19 fecha é o quarto, que é de FORMA e não de
conteúdo: **quem escreve o byte tem de dizer de onde o sabe.** É a mesma forma
da regra 1 (`sem-mordida`) e da 16 (`causa-nao-declarada`) — a régua sabe o QUÊ
e cala sobre o DE ONDE.

Por que ela pode nascer DURA, como a 13 e ao contrário da 7: medida contra o CSV
de 31/08/2026, ela acha **ZERO** células. A versão irrestrita (sem exigir
`aciona` respondido) acharia 4, todas `*_comando` das duas linhas
`entrada.emulacao_mouse.*`, com `aciona` vazio nos dois lados — que é buraco de
censo, exatamente o que a regra 7 aprendeu a não castigar. Por isso a
restrição por `aciona` está no enunciado, e não é conveniência: é a fronteira
entre "ninguém respondeu" e "respondeu e não disse de onde".

Os dois degraus que faltavam (19/08/2026)
-----------------------------------------
Até esta data a escada de `ate_onde_foi` cobria só a IDA — produto para aparelho
—, e dá para conferir no dado: `O APARELHO OBEDECEU` só aparece em linha de
saída. A volta (aparelho → vpad → JOGO) não tinha uma palavra, e o mapa admitia
isso por escrito em duas linhas suas: `toque.touchpad` ("quem ler
`radio_aciona = sim` aqui está lendo 'o vpad ENTREGA', não 'o jogo REAGE'") e
`movimento.giroscopio.jogo` ("o repasse está íntegro e o jogo não reage: a
falha, se existir, é DEPOIS do vpad, e ninguém a localizou"). Era possível o
mapa inteiro ficar verde enquanto ela não conseguia jogar.

`O JOGO RECEBEU` e `O JOGO REAGIU` entram com o critério escrito em `ESCADA` —
sem critério um degrau vira adjetivo — e com a mesma severidade dos degraus
fortes de saída: sem ensaio no caderno, FALHA. NENHUMA célula do CSV foi
preenchida com eles nesta leva, de propósito: `◌ ninguém respondeu` é verdade, e
preencher por analogia é o que destruiria o valor deste arquivo.

O buraco de 12/08/2026, e por que a regra 6 nasceu
--------------------------------------------------
Um agente escreveu numa cópia da árvore a afirmação mais forte que o vocabulário
da casa permite — `cabo_ate_onde_foi = radio_ate_onde_foi = O APARELHO OBEDECEU`,
`provado_por = olho-dela` — numa linha com ZERO ensaios no caderno, e o portão
devolveu exatamente o mesmo número de reprovações de antes: quinze. A mentira
passou inteira, e por três motivos que este arquivo tinha por escrito:

  - `docs/data/ensaios.csv` não era citado aqui uma única vez. O caderno de
    bancada — o arquivo onde mora o que o aparelho FEZ — não era fonte de
    verdade de portão nenhum;
  - as colunas do degrau (hoje `cabo_ate_onde_foi`/`radio_ate_onde_foi`) não
    entravam em domínio nenhum, então `O APARELHO OBEDECEU` era escrevível em
    qualquer linha, de graça;
  - `mordida_provada_em` estava vazia em todas as linhas e ninguém a lia.

A regra que ela aprovou é uma frase: **grau forte exige ensaio correspondente**.
O casamento é por `linha_id` == `id` E por transporte, porque `SAIU NO FIO` no
cabo não se sustenta com ensaio de rádio — foi a assimetria cabo/rádio que fez
este mapa existir. Quem casa os dois é `scripts/eliminacao.py`, reusado aqui em
vez de reimplementado: uma segunda leitura do caderno seria uma segunda régua
para o mesmo dado, e nesta casa o instrumento já mentiu mais que o produto.

O preço do `resultado`, dito na cara
------------------------------------
`resultado` é texto livre. Os quatro valores que o caderno usa hoje (12/08/2026)
foram LIDOS dele, não inventados aqui: `obedece`, `não obedece`, `parcial`,
`inconclusivo`. E a semântica deles é do SUSPEITO da linha, não da feature: o
ensaio `gatilho-lado-nao-esta-invertido` está gravado como `não obedece` — o
suspeito "o mapeamento está invertido" foi eliminado — enquanto a nota do mesmo
ensaio diz que o R2 endureceu, isto é, que o aparelho obedeceu. Cobrar
`resultado` como FALHA seria reprovar uma afirmação verdadeira por causa de uma
coluna que responde outra pergunta. Por isso a regra 6 (dura) cobra a EXISTÊNCIA
do ensaio, e a 9 (aviso) é que olha o resultado.

A coluna que a casa já tinha encomendado (13/08/2026)
-----------------------------------------------------
A constante `RESULTADO_REPROVA` trazia a encomenda por escrito desde 12/08: "o
dia de promover isto é o dia em que o caderno ganhar uma coluna que diga o que a
FEATURE fez, separada do que o SUSPEITO provou". A coluna chegou, e chama-se
`resultado_da_feature` — o nome sai da frase da própria regra 9, que já dizia
"o `resultado` do SUSPEITO em vez do que a FEATURE fez".

Como ela funciona, e por que não é um afrouxamento:

  - VAZIA é o padrão, e vazia quer dizer "`resultado` também responde pela
    feature". Foi assim que 76 dos 77 ensaios ficaram intocados: nenhuma
    medição dela foi reescrita, que era a condição do pedido;
  - PREENCHIDA, ela responde pelas regras 9 e 10 no lugar de `resultado` — e só
    por elas. `scripts/eliminacao.py` continua julgando o suspeito por
    `resultado`, porque é o suspeito que ele julga. Uma coluna, duas perguntas,
    nenhuma régua nova;
  - e ela é CARA de preencher, pela regra 12: o valor tem de estar no
    vocabulário do caderno, e divergir de `resultado` exige `nota` escrita. É o
    que separa "corrigir a leitura de uma coluna" de "desligar a guarda".

O ensaio que motivou tudo isso é um só, e ele tem o par que o confirma: a MESMA
linha (`gatilho.direito.adaptativo@dualsense`) tem `gatilho-dir-radio-isolado-2221`
por rádio com `resultado = obedece`. O degrau estava certo; a coluna é que
estava sendo lida errado.

Por que a regra 5 nasceu, e o que ela ainda faz
-----------------------------------------------
Ela nasceu porque o `--check` do `gerar-mapa.py` comparava MTIME, e mtime no CI
é ordem de checkout, não histórico de edição: o `actions/checkout` escreve os
arquivos em ordem de caminho, e `specs.html` (raiz, "sp") sai depois de `docs/`
e de `scripts/` — então ele nascia sempre "mais novo" que as fontes e passava
SEMPRE, independente do conteúdo. Este censo era o único que mordia por
conteúdo no runner.

Desde a MAPA-CONTEUDO-01 (12/08/2026) aquele `--check` regenera a página em
memória e compara o CONTEÚDO inteiro, então ele morde no CI também — e morde
mais fundo que esta regra, que só pergunta pelo `id`. A regra 5 continua por
duas razões: ela roda sem depender do gerador (se ele quebrar, o censo ainda
responde) e ela aponta a LINHA do CSV que ficou de fora, enquanto o `--check`
manda regerar a página inteira.

Limite honesto da regra 5: ela pega a linha NOVA que ninguém publicou. Linha
REMOVIDA do CSV e ainda publicada no HTML ela não vê — quem vê isso é o
`--check` por conteúdo.

Uso:
    python3 scripts/check_paridade_transporte.py
    python3 scripts/check_paridade_transporte.py --raiz /outro/repo
    python3 scripts/check_paridade_transporte.py --csv /tmp/mapa.csv --raiz /tmp/arvore
"""
from __future__ import annotations

import argparse
import ast
import csv
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

from eliminacao import carrega_por_lado

ASSIMETRIA_REPROVA = False

LADOS = ("cabo", "radio")

ROTULO_DO_LADO = {"cabo": "cabo", "radio": "rádio"}

RESULTADO_REPROVA = False

OLHO_DELA_REPROVA = False

CSV_RELATIVO = "docs/data/mapa-controles.csv"
ENSAIOS_RELATIVO = "docs/data/ensaios.csv"
SPECS_RELATIVO = "docs/specs.html"
PASTA_DE_TESTES = "tests"

PONTE_ESCADA_RELATIVO = "src/hefesto_dualsense4unix/integrations/ponte_escada.py"

RUMBLE_ESCADA_RELATIVO = "src/hefesto_dualsense4unix/daemon/subsystems/rumble.py"

RUMBLE_ESCADA_DICIONARIO = "RUMBLE_POLICY_MULT"

ROTULO_DO_DEGRAU_DE_VIBRACAO = {
    "economia": "economia",
    "balanceado": "balanceado",
    "máximo": "max",
    "max": "max",
}

CITACAO_DE_DEGRAU_DE_VIBRACAO = re.compile(
    r"\b(economia|balanceado|m[áa]ximo|max)\s*[:=]?\s*(\d+[,.]\d+)\s*[x×]",
    re.IGNORECASE,
)

COLUNAS_EXIGIDAS = (
    "chave",
    "controle",
    "existe",
    "teste_que_morde",
    "provado_em",
    "validade_dias",
    "assimetria_declarada",
    "ponte_alcanca",
    "id",
)

SUFIXOS_EXIGIDOS = ("aciona", "de_onde_sei", "canal", "ate_onde_foi")

DIRECAO_SAIDA = "saída"
DIRECAO_ENTRADA = "entrada"

FECHA_A_SUITE = "a suíte, sem aparelho"
FECHA_A_BANCADA = "a bancada, com o aparelho na mão"
FECHA_O_INSTRUMENTO = "um instrumento, de fora do jogo"
FECHA_A_MAO_DELA = "a mão dela, e mais ninguém"


@dataclass(frozen=True)
class Degrau:
    """Um degrau de `ate_onde_foi`: o que ele afirma, e o que o fecha."""

    valor: str
    direcao: str
    resumo: str
    criterio: str
    fechado_por: str


ESCADA = (
    Degrau(
        valor="MONTOU",
        direcao=DIRECAO_SAIDA,
        resumo="o produto montou o report",
        criterio=(
            "o byte existe na memória do produto e a suíte o lê. Nada saiu do "
            "processo. Tratar MONTOU como `funciona` é a mentira mais cara "
            "desta casa."
        ),
        fechado_por=FECHA_A_SUITE,
    ),
    Degrau(
        valor="SAIU NO FIO",
        direcao=DIRECAO_SAIDA,
        resumo="o byte saiu e algo voltou",
        criterio=(
            "a escrita no nó do transporte não errou e houve resposta do outro "
            "lado. Diz que o canal está aberto — não diz que o aparelho fez "
            "coisa alguma com o que recebeu."
        ),
        fechado_por=FECHA_A_BANCADA,
    ),
    Degrau(
        valor="O APARELHO OBEDECEU",
        direcao=DIRECAO_SAIDA,
        resumo="acendeu, girou, saiu som",
        criterio=(
            "alguém VIU o aparelho fazer o que foi pedido, e registrou o ensaio "
            "no caderno com `observado_por = olho-dela`. É o fim da direção de "
            "saída: depois dele o aparelho já fez a sua parte."
        ),
        fechado_por=FECHA_A_MAO_DELA,
    ),
    Degrau(
        valor="O JOGO RECEBEU",
        direcao=DIRECAO_ENTRADA,
        resumo="o processo do jogo abriu o nó do nosso vpad",
        criterio=(
            "o INODE do nó do vpad (`stat -c %i`) aparece em `/proc/<pid>/fd` de "
            "um processo da árvore do jogo. É observável de fora, sem a pessoa: "
            "a árvore de processos do contêiner é visível do hospedeiro, e quem "
            "segura o vpad é o `winedevice`, não o `.exe`. NUNCA case por "
            "caminho (o minor é reciclado: `event22` foi vpad DualSense às 01:40 "
            "e vpad Xbox às 01:50) e NUNCA pelo carimbo de tempo do fd (ele "
            "marca quando alguém OLHOU, e fica cacheado — medido: dois fds do "
            "MESMO nó com carimbos separados por 1m36s)."
        ),
        fechado_por=FECHA_O_INSTRUMENTO,
    ),
    Degrau(
        valor="O JOGO REAGIU",
        direcao=DIRECAO_ENTRADA,
        resumo="o personagem andou, o gatilho endureceu DENTRO do jogo",
        criterio=(
            "ela jogou e viu. Nenhum instrumento desta casa lê o estado interno "
            "de um jogo sob Proton, e nenhum vai ler: o único sensor deste "
            "degrau é ela. O ensaio tem de trazer `observado_por = olho-dela`, e "
            "o gesto `PS + R3` existe para ela poder fechá-lo sem tirar a mão do "
            "controle."
        ),
        fechado_por=FECHA_A_MAO_DELA,
    ),
)

VALORES_DA_ESCADA = tuple(degrau.valor for degrau in ESCADA)
DEGRAU_POR_VALOR = {degrau.valor: degrau for degrau in ESCADA}

GRAU_MONTOU = "MONTOU"
GRAU_SAIU_NO_FIO = "SAIU NO FIO"
GRAU_OBEDECEU = "O APARELHO OBEDECEU"
GRAU_JOGO_RECEBEU = "O JOGO RECEBEU"
GRAU_JOGO_REAGIU = "O JOGO REAGIU"

GRAUS_DE_ENTRADA: frozenset[str] = frozenset(
    {GRAU_JOGO_RECEBEU, GRAU_JOGO_REAGIU}
)

GRAUS_QUE_EXIGEM_ENSAIO = tuple(
    degrau.valor for degrau in ESCADA if degrau.fechado_por != FECHA_A_SUITE
)

GRAUS_QUE_EXIGEM_VEREDICTO = tuple(
    degrau.valor
    for degrau in ESCADA
    if degrau.fechado_por in (FECHA_O_INSTRUMENTO, FECHA_A_MAO_DELA)
)

GRAUS_QUE_SO_A_MAO_DELA_FECHA = tuple(
    degrau.valor for degrau in ESCADA if degrau.fechado_por == FECHA_A_MAO_DELA
)

GRAUS_SEM_LEGADO = frozenset({GRAU_JOGO_RECEBEU, GRAU_JOGO_REAGIU})

DOMINIO_POR_SUFIXO = {
    "aciona": frozenset({"", "sim", "não", "parcial", "desconhecido"}),
    "aceita": frozenset({"", "sim", "não", "parcial", "desconhecido"}),
    "canal": frozenset(
        {"", "hidraw", "uhid", "evdev", "sysfs", "dbus", "alsa-pipewire", "outro"}
    ),
    "de_onde_sei": frozenset(
        {"", "medido", "inferido-do-codigo", "afirmado-no-doc", "incerto"}
    ),
    "ate_onde_foi": frozenset({"", *VALORES_DA_ESCADA}),
    "por_que_nao_aciona": frozenset(
        {
            "",
            "nada-a-acionar",
            "decisao-tomada",
            "so-ela-decide",
            "divida",
            "o-aparelho-recusa",
            "nao-medido",
        }
    ),
}
DOMINIO_EXISTE = frozenset({"", "tem", "nao-tem", "parcial", "desconhecido"})

SUFIXOS_DE_CONTEUDO = (
    "offset",
    "report_id",
    "comando",
    "evidencia",
    "detalhe",
    "ressalva",
    "codigo_ref",
)

COLUNA_DA_PONTE = "ponte_alcanca"
COLUNA_DA_PONTE_DE_ONDE_SEI = "ponte_de_onde_sei"

#: O canal que SÓ existe sob a máscara DualSense do nosso vpad (`054c:0df2`).
CANAL_QUE_A_MASCARA_DECIDE = "uhid"

DIRECAO_POR_CANAL: dict[str, str] = {
    "hidraw": DIRECAO_SAIDA,
    "sysfs": DIRECAO_SAIDA,
    "dbus": DIRECAO_SAIDA,
    "alsa-pipewire": DIRECAO_SAIDA,
    "evdev": DIRECAO_ENTRADA,
    "uhid": DIRECAO_ENTRADA,
}

_CAMPOS_DA_PONTE = ("kind", "mascara", "steam_input")


ACIONA_FORTE = "sim"
DE_ONDE_SEI_FORTE = "medido"

ACIONA_NAO = "não"

RESULTADOS_QUE_SUSTENTAM = frozenset({"obedece"})

COLUNA_DO_VEREDICTO_DA_FEATURE = "resultado_da_feature"

RESULTADOS_DO_CADERNO = frozenset(
    {"obedece", "não obedece", "parcial", "inconclusivo"}
)

OBSERVADOR_QUE_SUSTENTA = "olho-dela"

PREFIXO_DE_ARQUIVO = "test_"
SUFIXO_DE_ARQUIVO = "_test.py"
PREFIXO_DE_FUNCAO = "test"
PREFIXO_DE_CLASSE = "Test"

_SEPARADOR_DE_ALVOS = re.compile(r"[;\n]+")

_FORMATOS_DE_DATA = ("%Y-%m-%d", "%d/%m/%Y")

FALHA = "FALHA"
AVISO = "AVISO"


@dataclass(frozen=True)
class Achado:
    """Uma reprovação (ou aviso): onde, qual regra, e o que está errado."""

    nivel: str
    regra: str
    linha: int
    ident: str
    lado: str
    texto: str

    def __str__(self) -> str:
        onde = f"linha {self.linha}"
        if self.ident:
            onde += f" ({self.ident})"
        if self.lado:
            onde += f" [{self.lado}]"
        return f"  {self.nivel} {self.regra}: {onde}: {self.texto}"


@dataclass
class ArquivoDeTeste:
    """O que o pytest coletaria de um arquivo, lido por AST."""

    funcoes: frozenset[str] = frozenset()
    classes: dict[str, frozenset[str]] = field(default_factory=dict)
    inertes: frozenset[str] = frozenset()
    puladas: dict[str, str] = field(default_factory=dict)
    modulo_pulado: str = ""


@dataclass
class Resumo:
    """Os números que dizem onde o mapa está cego. Nenhum deles é limiar."""

    linhas: int = 0
    celulas: int = 0
    celulas_mudas: int = 0
    celulas_que_afirmam: int = 0
    celulas_medidas: int = 0
    afirmacoes_fortes: int = 0
    afirmacoes_fortes_sem_rede: int = 0
    linhas_com_mordida: int = 0
    linhas_mudas_dos_dois_lados: int = 0
    assimetrias_nao_declaradas: int = 0
    alvos_de_teste: int = 0
    graus_fortes: int = 0
    graus_fortes_sem_ensaio: int = 0
    graus_de_entrada: int = 0
    ensaios_no_caderno: int = 0
    linhas_que_alcancam_por_uhid: int = 0
    linhas_uhid_com_afirmacao_forte: int = 0
    pontes_nao_declaradas: int = 0
    citacoes_da_escada_de_vibracao: int = 0
    celulas_com_conteudo: int = 0
    conteudo_sem_regua: int = 0


def e_arquivo_que_pytest_coleta(nome: str) -> bool:
    """A convenção padrão: `test_*.py` ou `*_test.py`."""
    return nome.startswith(PREFIXO_DE_ARQUIVO) or nome.endswith(SUFIXO_DE_ARQUIVO)


def _nome_pontilhado(no: ast.expr) -> str:
    """`pytest.mark.skip` a partir do nó do decorador, ou "" se não for um nome."""
    partes: list[str] = []
    atual: ast.expr = no
    while isinstance(atual, ast.Attribute):
        partes.append(atual.attr)
        atual = atual.value
    if not isinstance(atual, ast.Name):
        return ""
    partes.append(atual.id)
    return ".".join(reversed(partes))


def corpo_e_inerte(corpo: list[ast.stmt]) -> bool:
    """True quando o corpo não exercita nada: só docstring, `pass` ou `...`."""
    for no in corpo:
        if isinstance(no, ast.Pass):
            continue
        if isinstance(no, ast.Expr) and isinstance(no.value, ast.Constant):
            continue
        return False
    return True


def marcador_que_desliga_sempre(decorador: ast.expr) -> str:
    """O nome do marcador que desliga o teste SEMPRE, ou "" quando não desliga."""
    alvo = decorador.func if isinstance(decorador, ast.Call) else decorador
    nome = _nome_pontilhado(alvo)
    if not nome:
        return ""
    ultimo = nome.rsplit(".", 1)[-1]
    if ultimo == "skip":
        return nome
    if ultimo == "skipif":
        if isinstance(decorador, ast.Call) and decorador.args:
            condicao = decorador.args[0]
            if isinstance(condicao, ast.Constant) and bool(condicao.value):
                return f"{nome}({condicao.value!r})"
        return ""
    return ""


def primeiro_marcador_que_desliga(decoradores: list[ast.expr]) -> str:
    """O primeiro decorador da lista que desliga sempre, ou ""."""
    for decorador in decoradores:
        marcador = marcador_que_desliga_sempre(decorador)
        if marcador:
            return marcador
    return ""


def _pytestmark_que_desliga(arvore: ast.Module) -> str:
    """O marcador de `pytestmark` que desliga o módulo inteiro, ou ""."""
    for no in arvore.body:
        alvos: list[ast.expr] = []
        if isinstance(no, ast.Assign):
            alvos = list(no.targets)
        elif isinstance(no, ast.AnnAssign):
            alvos = [no.target]
        else:
            continue
        if not any(isinstance(alvo, ast.Name) and alvo.id == "pytestmark" for alvo in alvos):
            continue
        valor = no.value
        if valor is None:
            continue
        marcadores = list(valor.elts) if isinstance(valor, (ast.List, ast.Tuple)) else [valor]
        nome = primeiro_marcador_que_desliga(marcadores)
        if nome:
            return nome
    return ""


def indexar_testes(raiz: Path) -> dict[str, ArquivoDeTeste]:
    """Mapeia `caminho relativo -> o que o pytest coletaria`, por AST."""
    indice: dict[str, ArquivoDeTeste] = {}
    pasta = raiz / PASTA_DE_TESTES
    if not pasta.is_dir():
        return indice

    for caminho in sorted(pasta.rglob("*.py")):
        if not e_arquivo_que_pytest_coleta(caminho.name):
            continue
        try:
            arvore = ast.parse(caminho.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):  # pragma: no cover - defensivo
            continue

        funcoes: set[str] = set()
        classes: dict[str, frozenset[str]] = {}
        inertes: set[str] = set()
        puladas: dict[str, str] = {}

        for no in arvore.body:
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if no.name.startswith(PREFIXO_DE_FUNCAO):
                    funcoes.add(no.name)
                    if corpo_e_inerte(no.body):
                        inertes.add(no.name)
                    marcador = primeiro_marcador_que_desliga(no.decorator_list)
                    if marcador:
                        puladas[no.name] = marcador
            elif isinstance(no, ast.ClassDef) and no.name.startswith(PREFIXO_DE_CLASSE):
                metodos: set[str] = set()
                pulada_a_classe = primeiro_marcador_que_desliga(no.decorator_list)
                for metodo in no.body:
                    if not isinstance(metodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    if not metodo.name.startswith(PREFIXO_DE_FUNCAO):
                        continue
                    metodos.add(metodo.name)
                    qualificado = f"{no.name}::{metodo.name}"
                    if corpo_e_inerte(metodo.body):
                        inertes.add(qualificado)
                    marcador = pulada_a_classe or primeiro_marcador_que_desliga(
                        metodo.decorator_list
                    )
                    if marcador:
                        puladas[qualificado] = marcador
                classes[no.name] = frozenset(metodos)
        relativo = caminho.relative_to(raiz).as_posix()
        indice[relativo] = ArquivoDeTeste(
            frozenset(funcoes),
            classes,
            frozenset(inertes),
            puladas,
            _pytestmark_que_desliga(arvore),
        )
    return indice


def alvos_da_celula(texto: str) -> list[str]:
    """Quebra a célula `teste_que_morde` nos alvos que ela aponta."""
    return [pedaco.strip() for pedaco in _SEPARADOR_DE_ALVOS.split(texto) if pedaco.strip()]


def motivo_de_o_pytest_nao_coletar(
    alvo: str, indice: dict[str, ArquivoDeTeste], raiz: Path
) -> str | None:
    """Devolve por que o pytest não coletaria este alvo, ou None se coletaria."""
    caminho, _, resto = alvo.partition("::")
    caminho = caminho.strip()

    if not caminho.startswith(f"{PASTA_DE_TESTES}/"):
        return (
            f"`{alvo}` não é alvo de pytest. Escreva o id do nó "
            f"({PASTA_DE_TESTES}/.../test_x.py::test_y) ou deixe a célula VAZIA "
            "— vazio é pergunta aberta, prosa aqui é rede que não existe"
        )

    arquivo = indice.get(caminho)
    if arquivo is None:
        if (raiz / caminho).is_file():
            return (
                f"`{caminho}` existe mas o pytest NÃO o coleta "
                f"(o nome precisa ser `{PREFIXO_DE_ARQUIVO}*.py` ou `*{SUFIXO_DE_ARQUIVO}`)"
            )
        return f"`{caminho}` não existe nesta árvore"

    partes = [parte for parte in resto.split("::") if parte.strip()]
    if not partes:
        return None
    partes[-1] = partes[-1].split("[", 1)[0].strip()

    if len(partes) == 1:
        nome = partes[0]
        if nome in arquivo.funcoes or nome in arquivo.classes:
            return None
        return f"`{caminho}` não tem `{nome}` que o pytest colete"

    if len(partes) == 2:
        classe, metodo = partes
        if classe not in arquivo.classes:
            return f"`{caminho}` não tem a classe `{classe}` que o pytest colete"
        if metodo not in arquivo.classes[classe]:
            return f"`{classe}` em `{caminho}` não tem o teste `{metodo}`"
        return None

    return f"`{alvo}` tem mais níveis do que um id de nó do pytest carrega"


def testes_cobertos_pelo_alvo(alvo: str, arquivo: ArquivoDeTeste) -> list[str]:
    """Os nomes qualificados que este alvo manda o pytest rodar."""
    resto = alvo.partition("::")[2]
    partes = [parte for parte in resto.split("::") if parte.strip()]
    if partes:
        partes[-1] = partes[-1].split("[", 1)[0].strip()

    todos = sorted(arquivo.funcoes) + [
        f"{classe}::{metodo}"
        for classe in sorted(arquivo.classes)
        for metodo in sorted(arquivo.classes[classe])
    ]
    if not partes:
        return todos
    if len(partes) == 1:
        nome = partes[0]
        if nome in arquivo.funcoes:
            return [nome]
        if nome in arquivo.classes:
            return [f"{nome}::{metodo}" for metodo in sorted(arquivo.classes[nome])]
        return []
    return ["::".join(partes[:2])]


def motivo_de_a_mordida_nao_morder(
    alvo: str, indice: dict[str, ArquivoDeTeste], raiz: Path
) -> str | None:
    """Devolve por que este alvo NÃO é rede, ou None quando é."""
    motivo = motivo_de_o_pytest_nao_coletar(alvo, indice, raiz)
    if motivo is not None:
        return motivo

    caminho = alvo.partition("::")[0].strip()
    arquivo = indice[caminho]

    if arquivo.modulo_pulado:
        return (
            f"`{alvo}` é coletado, mas o módulo inteiro está desligado por "
            f"`{arquivo.modulo_pulado}` em `pytestmark`: nunca roda, logo nunca morde"
        )

    cobertos = testes_cobertos_pelo_alvo(alvo, arquivo)
    if not cobertos:
        return (
            f"`{alvo}` não cobre um teste sequer que o pytest colete: "
            "não há o que morder"
        )

    vivos = [
        nome
        for nome in cobertos
        if nome not in arquivo.inertes and nome not in arquivo.puladas
    ]
    if vivos:
        return None

    mortos = []
    for nome in cobertos:
        if nome in arquivo.puladas:
            mortos.append(f"`{nome}` desligado por `{arquivo.puladas[nome]}`")
        else:
            mortos.append(f"`{nome}` tem corpo vazio (só docstring, `pass` ou `...`)")
    return (
        f"`{alvo}` é coletado, mas não exercita nada: "
        + "; ".join(mortos)
        + ". Um teste que passa com a cura arrancada não é rede: deixe a "
        "célula VAZIA — vazio é pergunta aberta — em vez de apontar para ele"
    )


def le_data(texto: str) -> date | None:
    """A data de `provado_em`, ou None se ilegível."""
    for formato in _FORMATOS_DE_DATA:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def pares_de_transporte(cabecalho: list[str]) -> dict[str, tuple[str, str]]:
    """Descobre os pares `cabo_X`/`radio_X` pelo SUFIXO, lendo o cabeçalho."""
    colunas = set(cabecalho)
    pares: dict[str, tuple[str, str]] = {}
    prefixo = f"{LADOS[0]}_"
    for coluna in cabecalho:
        if not coluna.startswith(prefixo):
            continue
        sufixo = coluna[len(prefixo) :]
        irmao = f"{LADOS[1]}_{sufixo}"
        if irmao in colunas:
            pares[sufixo] = (coluna, irmao)
    return pares


PONTEIRO_QUE_NAO_SE_SEGUE = frozenset({"idem", "idem.", "o mesmo", "mesmo", "ditto"})

_ENDERECO = re.compile(
    r"[\w./+-]+\.(?:py|c|h|sh|kt|cpp|md|csv|html|json|xml|glade|rs|toml|rules)\b"
)


@dataclass(frozen=True)
class Procedencia:
    """De onde se sabe UMA célula — a linha do mapa vista por um transporte."""

    id: str
    lado: str
    de_onde_sei: str
    ate_onde_foi: str
    ponteiros: tuple[tuple[str, str], ...]

    @property
    def tem_ponteiro(self) -> bool:
        return bool(self.ponteiros)

    def rotulos(self) -> tuple[str, ...]:
        return tuple(rotulo for rotulo, _ in self.ponteiros)


def _limpo(linha: dict[str, str], coluna: str) -> str:
    return (linha.get(coluna) or "").strip()


def procedencia_da_celula(
    linha: dict[str, str],
    lado: str,
    ensaios_por_lado: dict[tuple[str, str], list[dict]] | None = None,
) -> Procedencia:
    """A procedência de `(linha, lado)`, com os ponteiros que se pode seguir."""
    ponteiros: list[tuple[str, str]] = []

    carimbo_em = _limpo(linha, "provado_em")
    carimbo_por = _limpo(linha, "provado_por")
    if carimbo_em and carimbo_por:
        ponteiros.append(("carimbo", f"{carimbo_em} · {carimbo_por}"))

    mordida = _limpo(linha, "teste_que_morde")
    if mordida:
        ponteiros.append(("mordida", mordida))

    codigo = _limpo(linha, f"{lado}_codigo_ref")
    if codigo and codigo.lower() not in PONTEIRO_QUE_NAO_SE_SEGUE:
        ponteiros.append(("código", codigo))

    externa = _limpo(linha, "fonte_externa")
    if externa:
        ponteiros.append(("fonte externa", externa))

    evidencia = _limpo(linha, f"{lado}_evidencia")
    if _ENDERECO.search(evidencia):
        ponteiros.append(("evidência com endereço", evidencia))

    if ensaios_por_lado is not None:
        do_caderno = ensaios_por_lado.get((linha.get("id", ""), lado)) or []
        if do_caderno:
            ponteiros.append(
                ("ensaio", "; ".join(e.get("id", "") for e in do_caderno))
            )

    return Procedencia(
        id=linha.get("id", ""),
        lado=lado,
        de_onde_sei=_limpo(linha, f"{lado}_de_onde_sei"),
        ate_onde_foi=_limpo(linha, f"{lado}_ate_onde_foi"),
        ponteiros=tuple(ponteiros),
    )


def ids_publicados(specs: Path) -> str | None:
    """O texto do `specs.html`, ou None quando não há o que conferir."""
    try:
        return specs.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def caderno_de_ensaios(raiz: Path) -> tuple[dict[tuple[str, str], list[dict]] | None, str]:
    """O caderno de bancada indexado por (`linha_id`, transporte), ou None."""
    caminho = raiz / ENSAIOS_RELATIVO
    if not caminho.is_file():
        return None, (
            f"grau-sem-ensaio ({ENSAIOS_RELATIVO} ausente — sem o caderno de "
            "bancada não há o que casar com o grau)"
        )
    try:
        return carrega_por_lado(caminho), ""
    except (OSError, UnicodeDecodeError, KeyError, csv.Error) as erro:
        return None, (
            f"grau-sem-ensaio ({ENSAIOS_RELATIVO} ilegível para o casamento: "
            f"{erro!r} — o caderno precisa das colunas `linha_id` e `transporte`)"
        )


def chave_da_ponte(kind: str, mascara: str | None, steam_input: bool) -> str:
    """A `Ponte.chave` de `ponte_escada.py`, recalculada aqui — e a única cópia."""
    alvo = mascara or "-"
    return f"{kind}/{alvo}{'+steam_input' if steam_input else ''}"


def _valor_constante(no: ast.expr, constantes: dict[str, str]) -> object:
    """O valor literal de um argumento, ou o da constante de módulo que o nomeia."""
    if isinstance(no, ast.Constant):
        return no.value
    if isinstance(no, ast.Name):
        return constantes.get(no.id)
    return None


def dominio_das_pontes(raiz: Path) -> tuple[frozenset[str] | None, str]:
    """As chaves da `ESCADA` de `ponte_escada.py`, lidas por AST."""
    caminho = raiz / PONTE_ESCADA_RELATIVO
    try:
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError) as erro:
        return None, (
            f"integridade da `{COLUNA_DA_PONTE}` ({PONTE_ESCADA_RELATIVO} "
            f"ilegível: {erro!r} — sem a ESCADA não há domínio a conferir)"
        )

    constantes: dict[str, str] = {}
    escada: ast.expr | None = None
    for no in arvore.body:
        if not isinstance(no, (ast.Assign, ast.AnnAssign)):
            continue
        alvos = no.targets if isinstance(no, ast.Assign) else [no.target]
        for alvo in alvos:
            if not isinstance(alvo, ast.Name) or no.value is None:
                continue
            if isinstance(no.value, ast.Constant) and isinstance(no.value.value, str):
                constantes[alvo.id] = no.value.value
            elif alvo.id == "ESCADA":
                escada = no.value

    if escada is None:
        return None, (
            f"integridade da `{COLUNA_DA_PONTE}` (não achei `ESCADA` em "
            f"{PONTE_ESCADA_RELATIVO})"
        )

    chaves: set[str] = set()
    for no in ast.walk(escada):
        if not (
            isinstance(no, ast.Call)
            and isinstance(no.func, ast.Name)
            and no.func.id == "Ponte"
        ):
            continue
        valores: dict[str, object] = dict.fromkeys(_CAMPOS_DA_PONTE, None)
        for campo, argumento in zip(_CAMPOS_DA_PONTE, no.args, strict=False):
            valores[campo] = _valor_constante(argumento, constantes)
        for palavra in no.keywords:
            if palavra.arg in valores:
                valores[palavra.arg] = _valor_constante(palavra.value, constantes)
        kind = valores["kind"]
        if not isinstance(kind, str) or not kind:
            return None, (
                f"integridade da `{COLUNA_DA_PONTE}` (uma `Ponte` da ESCADA tem "
                f"`kind` que este leitor não resolve: {ast.dump(no)[:120]}…)"
            )
        mascara = valores["mascara"]
        chaves.add(
            chave_da_ponte(
                kind,
                mascara if isinstance(mascara, str) else None,
                bool(valores["steam_input"]),
            )
        )

    if not chaves:
        return None, (
            f"integridade da `{COLUNA_DA_PONTE}` (a `ESCADA` de "
            f"{PONTE_ESCADA_RELATIVO} não tem uma única `Ponte`)"
        )
    return frozenset(chaves), ""


def sem_acento(texto: str) -> str:
    """Tira os acentos: `máximo` com e sem o agudo é a MESMA palavra aqui."""
    return "".join(
        letra
        for letra in unicodedata.normalize("NFD", texto)
        if unicodedata.category(letra) != "Mn"
    )


_DEGRAU_POR_ROTULO_SEM_ACENTO = {
    sem_acento(rotulo): chave for rotulo, chave in ROTULO_DO_DEGRAU_DE_VIBRACAO.items()
}


def escada_de_vibracao(raiz: Path) -> tuple[dict[str, float] | None, str]:
    """`RUMBLE_POLICY_MULT`, lido por AST do dono declarado."""
    caminho = raiz / RUMBLE_ESCADA_RELATIVO
    try:
        arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError) as erro:
        return None, (
            f"escada-de-vibracao ({RUMBLE_ESCADA_RELATIVO} ilegível: {erro!r} "
            "— sem o dono não há régua a conferir)"
        )

    bruto: ast.expr | None = None
    for no in ast.walk(arvore):
        if not isinstance(no, (ast.Assign, ast.AnnAssign)):
            continue
        alvos = no.targets if isinstance(no, ast.Assign) else [no.target]
        for alvo in alvos:
            if isinstance(alvo, ast.Name) and alvo.id == RUMBLE_ESCADA_DICIONARIO:
                bruto = no.value

    if not isinstance(bruto, ast.Dict):
        return None, (
            f"escada-de-vibracao (não achei o dicionário "
            f"`{RUMBLE_ESCADA_DICIONARIO}` em {RUMBLE_ESCADA_RELATIVO})"
        )

    escada: dict[str, float] = {}
    for chave, valor in zip(bruto.keys, bruto.values, strict=True):
        if not (isinstance(chave, ast.Constant) and isinstance(chave.value, str)):
            continue
        if isinstance(valor, ast.Constant) and isinstance(valor.value, (int, float)):
            escada[chave.value] = float(valor.value)

    if not escada:
        return None, (
            f"escada-de-vibracao (`{RUMBLE_ESCADA_DICIONARIO}` existe e este "
            "leitor não resolveu nenhum degrau dele)"
        )
    return escada, ""


def _regra_da_escada_de_vibracao(
    linha: dict[str, str],
    numero: int,
    ident: str,
    escada: dict[str, float],
    resumo: Resumo,
) -> list[Achado]:
    """Regra 18: número de multiplicador citado em célula tem de bater com o dono."""
    achados: list[Achado] = []
    for coluna, celula in linha.items():
        if not coluna or not celula:
            continue
        for casamento in CITACAO_DE_DEGRAU_DE_VIBRACAO.finditer(celula):
            rotulo = sem_acento(casamento.group(1).lower())
            chave = _DEGRAU_POR_ROTULO_SEM_ACENTO.get(rotulo)
            if chave is None or chave not in escada:
                continue
            resumo.citacoes_da_escada_de_vibracao += 1
            citado = float(casamento.group(2).replace(",", "."))
            canonico = escada[chave]
            if abs(citado - canonico) < 1e-9:
                continue
            achados.append(
                Achado(
                    FALHA,
                    "escada-de-vibracao",
                    numero,
                    ident,
                    "",
                    f"a célula `{coluna}` diz `{casamento.group(0)}`, e "
                    f"`{RUMBLE_ESCADA_DICIONARIO}[{chave!r}]` vale "
                    f"{canonico:.1f}".replace(".", ",")
                    + f"x em {RUMBLE_ESCADA_RELATIVO} — o mapa está contando "
                    "uma escada que o produto não usa",
                )
            )
    return achados


def censo(
    caminho_csv: Path, raiz: Path, hoje: date
) -> tuple[list[Achado], Resumo, list[str]]:
    """Roda as regras. Devolve (achados, resumo, regras desligadas)."""
    achados: list[Achado] = []
    resumo = Resumo()
    desligadas: list[str] = []

    with caminho_csv.open(encoding="utf-8", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)
        cabecalho = list(leitor.fieldnames or [])
        registros = [(leitor.line_num, linha) for linha in leitor]

    faltando = [coluna for coluna in COLUNAS_EXIGIDAS if coluna not in cabecalho]
    pares = pares_de_transporte(cabecalho)
    faltando += [
        f"{lado}_{sufixo}"
        for sufixo in SUFIXOS_EXIGIDOS
        if sufixo not in pares
        for lado in LADOS
    ]
    if faltando:
        achados.append(
            Achado(
                FALHA,
                "integridade",
                1,
                "",
                "",
                "o cabeçalho perdeu coluna(s): " + ", ".join(sorted(set(faltando))),
            )
        )
        return achados, resumo, desligadas

    indice_de_testes = indexar_testes(raiz)
    if not indice_de_testes:
        desligadas.append(
            "mordida-fantasma (nenhum arquivo de teste indexado sob "
            f"{PASTA_DE_TESTES}/ — a regra se desliga em vez de acusar tudo)"
        )

    texto_do_specs = ids_publicados(raiz / SPECS_RELATIVO)
    if texto_do_specs is None:
        desligadas.append(
            f"mapa-nao-publicado ({SPECS_RELATIVO} ausente — quem cobra a "
            "existência dele é scripts/gerar-mapa.py)"
        )

    ensaios_por_lado, motivo_sem_caderno = caderno_de_ensaios(raiz)
    if ensaios_por_lado is None:
        desligadas.append(motivo_sem_caderno)
    else:
        resumo.ensaios_no_caderno = sum(len(lista) for lista in ensaios_por_lado.values())

    dominio_das_pontes_lido, motivo_sem_escada = dominio_das_pontes(raiz)
    if dominio_das_pontes_lido is None:
        desligadas.append(motivo_sem_escada)

    escada_de_vibracao_canonica, motivo_sem_escada_de_vibracao = escada_de_vibracao(raiz)
    if escada_de_vibracao_canonica is None:
        desligadas.append(motivo_sem_escada_de_vibracao)

    tem_coluna_da_mordida = "mordida_provada_em" in cabecalho
    if not tem_coluna_da_mordida:
        desligadas.append(
            "mordida-nao-provada (a coluna `mordida_provada_em` não está no "
            "cabeçalho deste CSV)"
        )

    vistos: dict[str, int] = {}
    nao_publicados: list[str] = []

    for numero, linha in registros:
        resumo.linhas += 1
        ident = (linha.get("id") or "").strip()

        if not ident:
            achados.append(
                Achado(FALHA, "integridade", numero, "", "", "`id` vazio")
            )
        elif ident in vistos:
            achados.append(
                Achado(
                    FALHA,
                    "integridade",
                    numero,
                    ident,
                    "",
                    f"`id` duplicado — já usado na linha {vistos[ident]}",
                )
            )
        else:
            vistos[ident] = numero

        if None in linha:
            achados.append(
                Achado(
                    FALHA,
                    "integridade",
                    numero,
                    ident,
                    "",
                    "a linha tem MAIS campos que o cabeçalho (vírgula solta fora "
                    "de aspas costuma ser a causa)",
                )
            )
        elif any(valor is None for valor in linha.values()):
            achados.append(
                Achado(
                    FALHA,
                    "integridade",
                    numero,
                    ident,
                    "",
                    "a linha tem MENOS campos que o cabeçalho",
                )
            )

        existe = (linha.get("existe") or "").strip()
        if existe not in DOMINIO_EXISTE:
            achados.append(
                Achado(
                    FALHA,
                    "integridade",
                    numero,
                    ident,
                    "",
                    f"`existe` fora do domínio: {existe!r}",
                )
            )

        ponte = (linha.get(COLUNA_DA_PONTE) or "").strip()
        if ponte and dominio_das_pontes_lido is not None and ponte not in dominio_das_pontes_lido:
            achados.append(
                Achado(
                    FALHA,
                    "integridade",
                    numero,
                    ident,
                    "",
                    f"`{COLUNA_DA_PONTE}` fora do domínio: {ponte!r}. As pontes "
                    f"são as da `ESCADA` de {PONTE_ESCADA_RELATIVO} "
                    f"({', '.join(sorted(dominio_das_pontes_lido))}) — sem esta "
                    "régua, `Steam Input`, `steam input` e `SteamInput` viram "
                    "três pontes e o mapa deixa de casar com o produto",
                )
            )
        ponte_de_onde_sei = (linha.get(COLUNA_DA_PONTE_DE_ONDE_SEI) or "").strip()
        if ponte_de_onde_sei not in DOMINIO_POR_SUFIXO["de_onde_sei"]:
            achados.append(
                Achado(
                    FALHA,
                    "integridade",
                    numero,
                    ident,
                    "",
                    f"`{COLUNA_DA_PONTE_DE_ONDE_SEI}` fora do domínio: "
                    f"{ponte_de_onde_sei!r}",
                )
            )

        mordidas = alvos_da_celula(linha.get("teste_que_morde") or "")
        if mordidas:
            resumo.linhas_com_mordida += 1
            resumo.alvos_de_teste += len(mordidas)
        if mordidas and indice_de_testes:
            for alvo in mordidas:
                motivo = motivo_de_a_mordida_nao_morder(alvo, indice_de_testes, raiz)
                if motivo:
                    achados.append(
                        Achado(FALHA, "mordida-fantasma", numero, ident, "", motivo)
                    )

        mudas_nesta_linha = 0
        graus_fortes_nesta_linha: list[str] = []
        lados_por_uhid: list[str] = []
        lados_por_uhid_que_afirmam: list[str] = []
        for lado in LADOS:
            resumo.celulas += 1
            aciona = (linha[f"{lado}_aciona"] or "").strip()
            de_onde_sei = (linha[f"{lado}_de_onde_sei"] or "").strip()
            por_que_nao_aciona = (linha.get(f"{lado}_por_que_nao_aciona") or "").strip()

            if (
                "por_que_nao_aciona" in pares
                and aciona == ACIONA_NAO
                and not por_que_nao_aciona
            ):
                achados.append(
                    Achado(
                        FALHA,
                        "causa-nao-declarada",
                        numero,
                        ident,
                        lado,
                        f"`{lado}_aciona = {ACIONA_NAO}` e "
                        f"`{lado}_por_que_nao_aciona` está vazia: a régua sabe "
                        "que não aciona e não sabe de quem é a culpa — nem se "
                        "alguém chegou a olhar. Se ninguém mediu, a palavra é "
                        "`nao-medido`, e ela NÃO autoriza dizer que o aparelho "
                        "não faz. Preencha com uma das causas do domínio "
                        f"({sorted(DOMINIO_POR_SUFIXO['por_que_nao_aciona'] - {''})})",
                    )
                )

            if (
                "por_que_nao_aciona" in pares
                and por_que_nao_aciona
                and aciona
                and aciona != ACIONA_NAO
            ):
                achados.append(
                    Achado(
                        AVISO,
                        "causa-sem-negativa",
                        numero,
                        ident,
                        lado,
                        f"`{lado}_aciona = {aciona}` (não é `{ACIONA_NAO}`) e "
                        f"`{lado}_por_que_nao_aciona = {por_que_nao_aciona}`: a "
                        "coluna da causa está preenchida ao lado de uma célula "
                        "que ACIONA. Se é de propósito, a `ressalva` deste lado "
                        "tem de dizer por quê — quem ler só as duas colunas vai "
                        "ler VETO onde há decisão, e foi assim que um passo que "
                        "funciona foi mandado parar em 06/09/2026",
                    )
                )

            escritas_sem_regua = [
                sufixo
                for sufixo in SUFIXOS_DE_CONTEUDO
                if sufixo in pares and (linha.get(f"{lado}_{sufixo}") or "").strip()
            ]
            if escritas_sem_regua:
                resumo.celulas_com_conteudo += 1
            if aciona and not de_onde_sei and escritas_sem_regua:
                resumo.conteudo_sem_regua += 1
                achados.append(
                    Achado(
                        FALHA,
                        "lado-sem-regua",
                        numero,
                        ident,
                        lado,
                        f"`{lado}_aciona = {aciona}` e "
                        + ", ".join(f"`{lado}_{s}`" for s in escritas_sem_regua)
                        + f" escrito(s), mas `{lado}_de_onde_sei` está vazia: a "
                        "célula afirma sobre este transporte sem dizer de onde "
                        "sabe. Preencha com um valor do domínio "
                        f"({sorted(DOMINIO_POR_SUFIXO['de_onde_sei'] - {''})})",
                    )
                )

            for sufixo, (coluna_cabo, coluna_radio) in pares.items():
                dominio = DOMINIO_POR_SUFIXO.get(sufixo)
                if dominio is None:
                    continue
                coluna = coluna_cabo if lado == LADOS[0] else coluna_radio
                valor = (linha[coluna] or "").strip()
                if valor not in dominio:
                    achados.append(
                        Achado(
                            FALHA,
                            "integridade",
                            numero,
                            ident,
                            lado,
                            f"`{coluna}` fora do domínio: {valor!r}",
                        )
                    )

            if not aciona:
                resumo.celulas_mudas += 1
                mudas_nesta_linha += 1
            if aciona in {"sim", "parcial"}:
                resumo.celulas_que_afirmam += 1
            if de_onde_sei == DE_ONDE_SEI_FORTE:
                resumo.celulas_medidas += 1

            if (linha[f"{lado}_canal"] or "").strip() == CANAL_QUE_A_MASCARA_DECIDE:
                lados_por_uhid.append(lado)
                if aciona == ACIONA_FORTE and de_onde_sei == DE_ONDE_SEI_FORTE:
                    lados_por_uhid_que_afirmam.append(lado)

            if aciona == ACIONA_FORTE and de_onde_sei == DE_ONDE_SEI_FORTE:
                resumo.afirmacoes_fortes += 1
                if not mordidas:
                    resumo.afirmacoes_fortes_sem_rede += 1
                    achados.append(
                        Achado(
                            FALHA,
                            "sem-mordida",
                            numero,
                            ident,
                            lado,
                            f"afirma `{lado}_aciona = {ACIONA_FORTE}` com "
                            f"`{lado}_de_onde_sei = {DE_ONDE_SEI_FORTE}` e "
                            "`teste_que_morde` está vazio: se isso quebrar, a "
                            "suíte inteira continua verde",
                        )
                    )

            grau = (linha[f"{lado}_ate_onde_foi"] or "").strip()
            if grau in GRAUS_QUE_EXIGEM_ENSAIO:
                resumo.graus_fortes += 1
                graus_fortes_nesta_linha.append(grau)
                if DEGRAU_POR_VALOR[grau].direcao == DIRECAO_ENTRADA:
                    resumo.graus_de_entrada += 1
                if ensaios_por_lado is not None:
                    achados.extend(
                        _regra_do_caderno(
                            grau,
                            ensaios_por_lado.get((ident, lado), []),
                            numero,
                            ident,
                            lado,
                            resumo,
                        )
                    )

        if mudas_nesta_linha == len(LADOS):
            resumo.linhas_mudas_dos_dois_lados += 1

        if lados_por_uhid:
            resumo.linhas_que_alcancam_por_uhid += 1
        if lados_por_uhid_que_afirmam:
            resumo.linhas_uhid_com_afirmacao_forte += 1
            achados.extend(
                _regra_da_ponte_nao_declarada(
                    ponte, lados_por_uhid_que_afirmam, numero, ident, resumo
                )
            )

        if graus_fortes_nesta_linha and tem_coluna_da_mordida:
            achados.extend(_regra_da_mordida_nao_provada(linha, numero, ident))

        achados.extend(_regra_da_validade(linha, numero, ident, hoje))
        achados.extend(_regra_da_assimetria(linha, numero, ident, resumo))

        if escada_de_vibracao_canonica is not None:
            achados.extend(
                _regra_da_escada_de_vibracao(
                    linha, numero, ident, escada_de_vibracao_canonica, resumo
                )
            )

        if texto_do_specs is not None and ident and ident not in texto_do_specs:
            nao_publicados.append(ident)

    if nao_publicados:
        amostra = ", ".join(nao_publicados[:5])
        resto = "" if len(nao_publicados) <= 5 else f" (e mais {len(nao_publicados) - 5})"
        achados.append(
            Achado(
                FALHA,
                "mapa-nao-publicado",
                1,
                "",
                "",
                f"{len(nao_publicados)} linha(s) do CSV não estão em "
                f"{SPECS_RELATIVO}: {amostra}{resto} — rode "
                "`python3 scripts/gerar-mapa.py`",
            )
        )

    return achados, resumo, desligadas


def _regra_da_ponte_nao_declarada(
    ponte: str,
    lados: list[str],
    numero: int,
    ident: str,
    resumo: Resumo,
) -> list[Achado]:
    """Regra 15 — afirmação forte por `uhid` que não diz por qual ponte.

    A linha `uhid` é a única do mapa em que a PONTE decide se a feature existe:
    sob a nossa máscara DualSense (`054c:0df2`) ela chega ao jogo, e sob a
    máscara Xbox (`045e:028e`) ela não tem por onde chegar — o pacote do Xbox
    360 é fixo desde 2005 e o `xpad` declara sete eixos e um nó só
    (`pilha-steam-input-xpad-sdl.md` §1.5). Por isso `aciona = sim, medido` sem
    `ponte_alcanca` não é uma célula incompleta: é uma célula que afirma duas
    coisas contraditórias ao mesmo tempo e fica verde nas duas.

    Só cobra onde a promessa é máxima, e isso é desenho, não indulgência: as
    linhas `uhid` que ainda não afirmam nada continuam podendo calar, porque
    `◌ ninguém respondeu` é verdade e preencher por analogia é o que destruiria
    o valor deste arquivo. Vazio segue sendo PERGUNTA ABERTA — nunca "serve para
    toda ponte".
    """
    if ponte:
        return []
    resumo.pontes_nao_declaradas += 1
    quais = " e ".join(ROTULO_DO_LADO[lado] for lado in lados)
    return [
        Achado(
            FALHA,
            "ponte-nao-declarada",
            numero,
            ident,
            "",
            f"entrega ao jogo por `{CANAL_QUE_A_MASCARA_DECIDE}` e afirma "
            f"`aciona = {ACIONA_FORTE}` com `de_onde_sei = {DE_ONDE_SEI_FORTE}` "
            f"no {quais}, mas `{COLUNA_DA_PONTE}` está vazia. O "
            f"`{CANAL_QUE_A_MASCARA_DECIDE}` só existe sob a máscara DualSense "
            "do nosso vpad: sob a máscara Xbox esta feature não chega ao jogo de "
            "jeito nenhum. Diga por qual ponte você mediu — as pontes são as da "
            f"`ESCADA` de {PONTE_ESCADA_RELATIVO} — ou baixe a "
            f"`de_onde_sei` para o que a evidência de fato sustenta",
        )
    ]


def _regra_da_validade(
    linha: dict[str, str], numero: int, ident: str, hoje: date
) -> list[Achado]:
    """Regra 3 e regra 8. Silenciosa quando as duas colunas estão vazias."""
    provado = (linha.get("provado_em") or "").strip()
    validade = (linha.get("validade_dias") or "").strip()

    if not provado and not validade:
        return []
    if validade and not provado:
        return [
            Achado(
                AVISO,
                "validade-sem-data",
                numero,
                ident,
                "",
                f"`validade_dias = {validade}` sem `provado_em`: prazo que não "
                "se consegue contar",
            )
        ]
    if provado and not validade:
        return []

    data = le_data(provado)
    if data is None:
        return [
            Achado(
                FALHA,
                "prova-vencida",
                numero,
                ident,
                "",
                f"`provado_em = {provado!r}` é ilegível "
                f"(formatos aceitos: {', '.join(_FORMATOS_DE_DATA)})",
            )
        ]
    try:
        dias = int(validade)
    except ValueError:
        return [
            Achado(
                FALHA,
                "prova-vencida",
                numero,
                ident,
                "",
                f"`validade_dias = {validade!r}` não é um número inteiro de dias",
            )
        ]
    if dias < 0:
        return [
            Achado(
                FALHA,
                "prova-vencida",
                numero,
                ident,
                "",
                f"`validade_dias = {dias}` é negativo",
            )
        ]

    vence = data + timedelta(days=dias)
    if vence < hoje:
        return [
            Achado(
                FALHA,
                "prova-vencida",
                numero,
                ident,
                "",
                f"a prova venceu em {vence.isoformat()} "
                f"(provada em {data.isoformat()}, validade de {dias} dia(s)): "
                "meça de novo ou mude o prazo",
            )
        ]
    return []


def _regra_da_assimetria(
    linha: dict[str, str], numero: int, ident: str, resumo: Resumo
) -> list[Achado]:
    """Regra 7 — o caso que ela descreveu: consolidado no cabo, morto no rádio."""
    cabo = (linha[f"{LADOS[0]}_aciona"] or "").strip()
    radio = (linha[f"{LADOS[1]}_aciona"] or "").strip()
    if cabo == radio:
        return []
    if (linha.get("assimetria_declarada") or "").strip():
        return []

    resumo.assimetrias_nao_declaradas += 1
    if not cabo or not radio:
        respondido, mudo = (LADOS[0], LADOS[1]) if cabo else (LADOS[1], LADOS[0])
        valor = cabo or radio
        texto = (
            f"o {ROTULO_DO_LADO[respondido]} diz `{valor}` e o "
            f"{ROTULO_DO_LADO[mudo]} não foi respondido: é "
            "exatamente a forma da regressão que este mapa existe para pegar"
        )
    else:
        texto = (
            f"o cabo diz `{cabo}` e o rádio diz `{radio}`, e "
            "`assimetria_declarada` está vazia"
        )
    nivel = FALHA if ASSIMETRIA_REPROVA else AVISO
    return [Achado(nivel, "assimetria-nao-declarada", numero, ident, "", texto)]


def veredicto_da_feature(ensaio: dict) -> str:
    """O que a FEATURE fez neste ensaio — a pergunta das regras 9 e 10."""
    declarado = (ensaio.get(COLUNA_DO_VEREDICTO_DA_FEATURE) or "").strip()
    return declarado or (ensaio.get("resultado") or "").strip()


def _regra_do_veredicto_da_feature(
    ensaios: list[dict], numero: int, ident: str, lado: str
) -> list[Achado]:
    """Regra 12 — a guarda da coluna nova, e o que a impede de ser uma saída."""
    achados: list[Achado] = []
    for ensaio in ensaios:
        declarado = (ensaio.get(COLUNA_DO_VEREDICTO_DA_FEATURE) or "").strip()
        if not declarado:
            continue
        id_do_ensaio = (ensaio.get("id") or "").strip() or "(ensaio sem id)"
        if declarado not in RESULTADOS_DO_CADERNO:
            achados.append(
                Achado(
                    FALHA,
                    "veredicto-da-feature-mal-declarado",
                    numero,
                    ident,
                    lado,
                    f"o ensaio `{id_do_ensaio}` tem "
                    f"`{COLUNA_DO_VEREDICTO_DA_FEATURE} = {declarado!r}`, que não "
                    f"está no vocabulário do caderno "
                    f"({', '.join(sorted(RESULTADOS_DO_CADERNO))}). A coluna "
                    "responde a MESMA pergunta que `resultado`, só que sobre a "
                    "feature: valor novo aqui é vocabulário novo, e vocabulário "
                    "novo se declara em RESULTADOS_DO_CADERNO no mesmo gesto",
                )
            )
            continue
        if declarado == (ensaio.get("resultado") or "").strip():
            continue
        if not (ensaio.get("nota") or "").strip():
            achados.append(
                Achado(
                    FALHA,
                    "veredicto-da-feature-mal-declarado",
                    numero,
                    ident,
                    lado,
                    f"o ensaio `{id_do_ensaio}` diz que a feature "
                    f"`{declarado}` enquanto o `resultado` diz "
                    f"`{(ensaio.get('resultado') or '').strip()}`, e a `nota` "
                    "está vazia. Divergir das duas colunas é dizer que o "
                    "`resultado` fala do SUSPEITO — e isso se escreve no "
                    "caderno, na mesma linha, ou não vale",
                )
            )
    return achados


def _regra_do_caderno(
    grau: str,
    ensaios: list[dict],
    numero: int,
    ident: str,
    lado: str,
    resumo: Resumo,
) -> list[Achado]:
    """Regras 6, 9, 10 e 12 — o grau forte contra o caderno de bancada."""
    rotulo = ROTULO_DO_LADO[lado]
    if not ensaios:
        resumo.graus_fortes_sem_ensaio += 1
        return [
            Achado(
                FALHA,
                "grau-sem-ensaio",
                numero,
                ident,
                lado,
                f"declara `{lado}_ate_onde_foi = {grau}` e não há UM ensaio de {rotulo} "
                f"para `{ident}` em {ENSAIOS_RELATIVO}. Registre o ensaio que "
                "você fez (uma linha: `linha_id`, `transporte`, `suspeito`, "
                f"`presente`, `resultado`, `observado_por`) ou baixe o grau para "
                f"`{GRAU_MONTOU}`, que é o que a suíte sozinha sustenta",
            )
        ]

    if grau in GRAUS_DE_ENTRADA:
        declararam = [
            ensaio
            for ensaio in ensaios
            if (ensaio.get("degrau") or "").strip() == grau
        ]
        if not declararam:
            resumo.graus_fortes_sem_ensaio += 1
            return [
                Achado(
                    FALHA,
                    "ensaio-nao-diz-o-degrau",
                    numero,
                    ident,
                    lado,
                    f"declara `{lado}_ate_onde_foi = {grau}` (direção de ENTRADA) "
                    f"e nenhum dos {len(ensaios)} ensaio(s) de `{ident}` em "
                    f"{ENSAIOS_RELATIVO} declara `degrau = {grau}`. Ensaio que "
                    "não diz o que mediu não sustenta degrau de entrada: os "
                    "ensaios desta linha podem ter medido a IDA (o aparelho "
                    "obedeceu) e não a VOLTA (o jogo recebeu). Preencha a coluna "
                    "`degrau` do ensaio que mediu a entrada, ou baixe o grau",
                )
            ]

    guarda = _regra_do_veredicto_da_feature(ensaios, numero, ident, lado)

    if grau not in GRAUS_QUE_EXIGEM_VEREDICTO:
        return guarda

    sustentam = [
        ensaio
        for ensaio in ensaios
        if veredicto_da_feature(ensaio) in RESULTADOS_QUE_SUSTENTAM
    ]
    if not sustentam:
        vistos = sorted({veredicto_da_feature(e) for e in ensaios})
        return [
            *guarda,
            Achado(
                FALHA if RESULTADO_REPROVA else AVISO,
                "grau-sem-ensaio-que-obedeca",
                numero,
                ident,
                lado,
                f"declara `{lado}_ate_onde_foi = {grau}` e os {len(ensaios)} "
                f"ensaio(s) de {rotulo} desta linha dizem {vistos}. Ou o degrau "
                f"está alto demais, ou o ensaio foi gravado com o `resultado` do "
                "SUSPEITO em vez do que a FEATURE fez — se for o segundo, "
                f"`{COLUNA_DO_VEREDICTO_DA_FEATURE}` é a coluna onde se diz o "
                "que a feature fez, e a `nota` do ensaio é onde se explica por "
                "que as duas divergem",
            )
        ]

    if grau not in GRAUS_QUE_SO_A_MAO_DELA_FECHA:
        return guarda

    if not any(
        (e.get("observado_por") or "").strip() == OBSERVADOR_QUE_SUSTENTA for e in sustentam
    ):
        observadores = sorted({(e.get("observado_por") or "").strip() for e in sustentam})
        return [*guarda, _achado_sem_olho_dela(grau, observadores, numero, ident, lado, rotulo)]
    return guarda


def _achado_sem_olho_dela(
    grau: str,
    observadores: list[str],
    numero: int,
    ident: str,
    lado: str,
    rotulo: str,
) -> Achado:
    """Regras 10 e 13 — o degrau que só a mão dela fecha, sem a mão dela."""
    if grau in GRAUS_SEM_LEGADO:
        return Achado(
            FALHA,
            "reagiu-sem-olho-dela",
            numero,
            ident,
            lado,
            f"declara `{lado}_ate_onde_foi = {grau}` no {rotulo} com ensaio "
            f"observado por {observadores}. Este degrau NÃO tem instrumento: "
            "nenhuma régua desta casa lê o estado interno de um jogo sob "
            f"Proton. Só `{OBSERVADOR_QUE_SUSTENTA}` o fecha — grave o ensaio "
            f"com o gesto dela, ou desça para `{GRAU_JOGO_RECEBEU}`, que é o "
            "que um instrumento consegue ver de fora",
        )
    return Achado(
        FALHA if OLHO_DELA_REPROVA else AVISO,
        "grau-sem-olho-dela",
        numero,
        ident,
        lado,
        f"o ensaio que sustenta `{grau}` no {rotulo} foi "
        f"observado por {observadores}, e o METODO-DE-ISOLAMENTO diz que "
        f"só `{OBSERVADOR_QUE_SUSTENTA}` sustenta esse degrau: peça o "
        "olho dela, ou desça para `SAIU NO FIO`",
    )


def _regra_da_mordida_nao_provada(
    linha: dict[str, str], numero: int, ident: str
) -> list[Achado]:
    """Regra 11 — a coluna que existia e ninguém lia."""
    if not (linha.get("teste_que_morde") or "").strip():
        return []
    if (linha.get("mordida_provada_em") or "").strip():
        return []
    return [
        Achado(
            AVISO,
            "mordida-nao-provada",
            numero,
            ident,
            "",
            "tem grau forte e `teste_que_morde`, mas `mordida_provada_em` está "
            "vazia: ninguém registrou ter arrancado a cura e visto reprovar. "
            "Arranque, veja reprovar, devolva — e ponha a data aqui",
        )
    ]


def ids_do_csv_em(contra: str, csv_relativo: str, raiz: Path) -> tuple[set[str] | None, str]:
    """Os `id` do mapa NAQUELA ref, via `git show <ref>:<caminho>`."""
    processo = subprocess.run(
        ["git", "-C", str(raiz), "show", f"{contra}:{csv_relativo}"],
        capture_output=True,
        text=True,
    )
    if processo.returncode != 0:
        motivo = (processo.stderr or processo.stdout or "sem saída do git").strip()
        return None, motivo
    try:
        linhas = list(csv.DictReader(processo.stdout.splitlines()))
    except csv.Error as exc:  # pragma: no cover - defensivo
        return None, f"CSV ilegível em {contra}: {exc}"
    return {(linha.get("id") or "").strip() for linha in linhas if linha.get("id")}, ""


def regra_id_estavel(
    contra: str, csv_relativo: str, raiz: Path, registros_de_hoje: list[dict[str, str]]
) -> list[Achado]:
    """Regra 17 (Z6-07): `id` que desaparece sem virar `id_v1` de outra linha"""
    ids_de_ontem, motivo = ids_do_csv_em(contra, csv_relativo, raiz)
    if ids_de_ontem is None:
        return [
            Achado(
                FALHA,
                "contra-nao-resolve",
                0,
                "",
                "",
                f"`--contra {contra}` não resolveu ({motivo!r}). Provavelmente um "
                "clone raso sem `fetch-depth: 0`, ou a ref não existe. A régua "
                "da estabilidade do `id` reprova em vez de sair calada — sem "
                "histórico ela não tem como saber se um `id` sumiu.",
            )
        ]

    ids_de_hoje = {
        (linha.get("id") or "").strip()
        for linha in registros_de_hoje
        if linha.get("id")
    }
    ids_v1_de_hoje = {
        (linha.get("id_v1") or "").strip()
        for linha in registros_de_hoje
        if (linha.get("id_v1") or "").strip()
    }

    sumidos = sorted(ids_de_ontem - ids_de_hoje)
    achados: list[Achado] = []
    for id_sumido in sumidos:
        if id_sumido in ids_v1_de_hoje:
            continue
        achados.append(
            Achado(
                FALHA,
                "id-sumiu-sem-nota",
                0,
                id_sumido,
                "",
                f"`id={id_sumido!r}` existia em `--contra {contra}` e não existe "
                "mais em nenhuma linha, nem como `id_v1` de nenhuma outra. "
                "Renomear é legítimo — o registro é: a linha nova traz "
                f"`id_v1={id_sumido!r}`, com nota datada dizendo por quê. Sem "
                "isso, toda `Fala` que se apoiava neste endereço quebra em "
                "silêncio.",
            )
        )
    return achados


LEIA_PRIMEIRO_RELATIVO = "docs/data/LEIA-PRIMEIRO.md"

_MARCA_GERADA = re.compile(r"<!--@([A-Za-z0-9:/._-]+)-->(.*?)<!--/-->")

_PREFIXO_DE_BYTES = "bytes:"


def _milhar(numero: int) -> str:
    """`700602` -> `700.602`, que é como esta casa escreve número."""
    return f"{numero:,}".replace(",", ".")


def ultima_linha_da_docstring(caminho: Path) -> int:
    """A linha em que o docstring de módulo fecha, contando a partir de 1."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    primeiro = arvore.body[0] if arvore.body else None
    if (
        isinstance(primeiro, ast.Expr)
        and isinstance(primeiro.value, ast.Constant)
        and isinstance(primeiro.value.value, str)
        and primeiro.end_lineno is not None
    ):
        return primeiro.end_lineno
    return 0


_PALAVRAS_DE_MEDIDA = (
    "linha", "linhas", "coluna", "colunas", "ensaio", "ensaios", "caractere",
    "caracteres", "token", "tokens", "célula", "células", "byte", "bytes",
    "arquivo", "arquivos", "feature", "features",
)
_NUMERO_SOLTO = re.compile(
    r"(?<![\d.>-])(\d{1,3}(?:\.\d{3})+)(?![\d.<])"
    r"|(?<![\d>-])(\d{2,})\s+(?:mil\s+)?(" + "|".join(_PALAVRAS_DE_MEDIDA) + r")\b"
)
_MEDIDAS_QUE_NAO_SAO_DAQUI: tuple[str, ...] = (
    '10 colunas',
    '102.818',
    '12.717',
    '122.766',
    '128 linhas',
    '14.534',
    '16 linhas',
    '16.050',
    '21.026',
    '225 células',
    '26 colunas',
    '264 linhas',
    '27.828',
    '3.447',
    '37 células',
    '30.711',
    '4.750',
    '5.250',
    '53.899',
    '60 caracteres',
    '600 caracteres',
    '63 células',
    '696.546',
    '700.602',
    '85.063',
)


def numeros_soltos(texto: str) -> list[tuple[int, str]]:
    """Números com cara de medição que estão FORA de `<!--@…-->…<!--/-->`.

    **POR QUE ELA EXISTE, e o buraco é medido — 08/09/2026.** A régua das marcas
    confere só o que está marcado, e por isso NOVE números do documento
    envelheceram calados: eles nunca foram marcados. O pior deles era o aviso de
    custo — *"661.177 caracteres, ~165 mil tokens"* contra 1.396.169 e ~349 mil
    medidos. **Um aviso de custo que erra pela metade convida a leitura que ele
    existe para impedir.**

    E o buraco tem a forma exata da MORDIDA que faltava: tirar a marcação de um
    número passava verde, porque o que não está marcado não é conferido. Uma
    régua que só olha o que alguém lembrou de marcar não trava nada.
    """
    fora, ultimo = [], 0
    limpo: list[tuple[int, str]] = []
    for marca in _MARCA_GERADA.finditer(texto):
        fora.append((ultimo, texto[ultimo:marca.start()]))
        ultimo = marca.end()
    fora.append((ultimo, texto[ultimo:]))
    for inicio, pedaco in fora:
        for achado in _NUMERO_SOLTO.finditer(pedaco):
            trecho = achado.group(0)
            if any(d in trecho for d in _MEDIDAS_QUE_NAO_SAO_DAQUI):
                continue
            linha = texto.count("\n", 0, inicio + achado.start()) + 1
            limpo.append((linha, trecho))
    return limpo


def numeros_do_leia_primeiro(raiz: Path) -> dict[str, str]:
    """Os números que o `LEIA-PRIMEIRO.md` publica, medidos agora."""
    caminho_csv = raiz / CSV_RELATIVO
    with caminho_csv.open(encoding="utf-8", newline="") as arquivo:
        leitor = csv.reader(arquivo)
        cabecalho = next(leitor, [])
        linhas = sum(1 for _ in leitor)
    pares = pares_de_transporte(cabecalho)

    caminho_caderno = raiz / ENSAIOS_RELATIVO
    with caminho_caderno.open(encoding="utf-8", newline="") as arquivo:
        ensaios = list(csv.DictReader(arquivo))
        cabecalho_do_caderno = list(ensaios[0]) if ensaios else []

    def sem_coluna(nome: str) -> int:
        return sum(1 for ensaio in ensaios if not (ensaio.get(nome) or "").strip())

    with (raiz / CSV_RELATIVO).open(encoding="utf-8", newline="") as arquivo:
        celulas = list(csv.DictReader(arquivo))
    caracteres = sum(len(valor or "") for l in celulas for valor in l.values())

    def contar(base: list[dict[str, str]], coluna: str) -> dict[str, int]:
        contagem: dict[str, int] = {}
        for linha in base:
            chave = (linha.get(coluna) or "").strip()
            if chave:
                contagem[chave] = contagem.get(chave, 0) + 1
        return contagem

    provado = contar(celulas, "provado_por")
    observado = contar(ensaios, "observado_por")

    def _escada(valor: str) -> str:
        return {
            "": "vazio",
            "MONTOU": "montou",
            "SAIU NO FIO": "saiu",
            "O APARELHO OBEDECEU": "obedeceu",
        }.get(valor.strip(), "outro")

    def _sei(valor: str) -> str:
        return {
            "": "vazio",
            "medido": "medido",
            "inferido-do-codigo": "inferido",
            "afirmado-no-doc": "afirmado",
            "incerto": "incerto",
        }.get(valor.strip(), "outro")

    lados = [
        (_sei(linha.get(f"{t}_de_onde_sei") or ""), _escada(linha.get(f"{t}_ate_onde_foi") or ""))
        for linha in celulas
        for t in ("cabo", "radio")
    ]
    existe = contar(celulas, "existe")
    por_controle = contar(celulas, "controle")

    grau_forte = sum(1 for _, escada in lados if escada in ("saiu", "obedeceu"))
    afirmacao_forte = sum(
        1
        for linha in celulas
        for t in ("cabo", "radio")
        if (linha.get(f"{t}_aciona") or "").strip() == "sim"
        and (linha.get(f"{t}_de_onde_sei") or "").strip() == "medido"
    )

    divergem_aciona = [
        linha
        for linha in celulas
        if (linha.get("cabo_aciona") or "") != (linha.get("radio_aciona") or "")
    ]
    divergem_veredicto = sum(
        1
        for linha in celulas
        if (linha.get("cabo_aceita") or "").strip()
        and (linha.get("radio_aceita") or "").strip()
        and (linha.get("cabo_aceita") or "", linha.get("cabo_aciona") or "")
        != (linha.get("radio_aceita") or "", linha.get("radio_aciona") or "")
    )
    sem_declarar = sum(
        1 for linha in divergem_aciona if not (linha.get("assimetria_declarada") or "").strip()
    )

    com_ensaio = {ensaio.get("linha_id") for ensaio in ensaios}
    linhas_com_ensaio = sum(1 for linha in celulas if linha.get("id") in com_ensaio)

    def _com(coluna: str) -> int:
        return sum(1 for linha in celulas if (linha.get(coluna) or "").strip())

    transporte = contar(celulas, "transporte")
    linhas_de_grau_forte = sum(
        1
        for linha in celulas
        if any(
            _escada(linha.get(f"{t}_ate_onde_foi") or "") in ("saiu", "obedeceu")
            for t in ("cabo", "radio")
        )
    )

    medidas_do_corpo = {
        "mapa-id-confere": _milhar(
            sum(
                1
                for linha in celulas
                if (linha.get("id") or "")
                == f"{linha.get('chave', '')}@{linha.get('controle', '')}"
            )
        ),
        "mapa-com-ponte-alcanca": _milhar(_com("ponte_alcanca")),
        "mapa-com-mordida-provada": _milhar(_com("mordida_provada_em")),
        "mapa-transporte-ambos": _milhar(transporte.get("ambos", 0)),
        "mapa-transporte-cabo-radio": _milhar(transporte.get("cabo+rádio", 0)),
        "mapa-transporte-sem-linha-v1": _milhar(transporte.get("sem linha no v1", 0)),
        "mapa-linhas-grau-forte": _milhar(linhas_de_grau_forte),
        "mapa-linhas-sem-ensaio": _milhar(len(celulas) - linhas_com_ensaio),
        "mapa-pct-divergem-aciona": (
            f"{100 * len(divergem_aciona) / len(celulas):.1f}".replace(".", ",")
            if celulas
            else "0,0"
        ),
        "mapa-existe-tem": _milhar(existe.get("tem", 0)),
        "mapa-existe-nao-tem": _milhar(existe.get("nao-tem", 0)),
        "mapa-existe-desconhecido": _milhar(existe.get("desconhecido", 0)),
        "mapa-existe-parcial": _milhar(existe.get("parcial", 0)),
        "mapa-linhas-dualsense": _milhar(por_controle.get("dualsense", 0)),
        "mapa-linhas-pro": _milhar(por_controle.get("pro", 0)),
        "mapa-linhas-sn30": _milhar(por_controle.get("sn30", 0)),
        "celulas-do-mapa": _milhar(len(lados)),
        "celulas-grau-forte": _milhar(grau_forte),
        "celulas-afirmacao-forte": _milhar(afirmacao_forte),
        "mapa-divergem-aciona": _milhar(len(divergem_aciona)),
        "mapa-divergem-sem-declarar": _milhar(sem_declarar),
        "mapa-divergem-veredicto": _milhar(divergem_veredicto),
        "mapa-com-teste-que-morde": _milhar(_com("teste_que_morde")),
        "mapa-com-nota": _milhar(_com("nota")),
        "mapa-com-provado-em": _milhar(_com("provado_em")),
        "mapa-linhas-com-ensaio": _milhar(linhas_com_ensaio),
        "mapa-pct-linhas-com-ensaio": (
            f"{100 * linhas_com_ensaio / len(celulas):.1f}".replace(".", ",")
            if celulas
            else "0,0"
        ),
    }
    for nome in ("medido", "inferido", "afirmado", "incerto", "vazio"):
        medidas_do_corpo[f"celulas-sei-{nome}"] = _milhar(
            sum(1 for sei, _ in lados if sei == nome)
        )
    for nome in ("vazio", "montou", "saiu", "obedeceu"):
        medidas_do_corpo[f"celulas-escada-{nome}"] = _milhar(
            sum(1 for _, escada in lados if escada == nome)
        )
    for sei in ("medido", "inferido", "afirmado", "incerto", "vazio"):
        for escada in ("vazio", "montou", "saiu", "obedeceu"):
            medidas_do_corpo[f"cruzamento-{sei}-{escada}"] = _milhar(
                sum(1 for s, e in lados if s == sei and e == escada)
            )

    return {
        **medidas_do_corpo,
        "caracteres-do-mapa": _milhar(caracteres),
        "tokens-do-mapa": _milhar(round(caracteres / 4 / 1000)),
        "mapa-com-provado-por": _milhar(sum(provado.values())),
        "mapa-provado-aparelho": _milhar(provado.get("aparelho", 0)),
        "mapa-provado-fonte-do-driver": _milhar(provado.get("fonte-do-driver", 0)),
        "mapa-provado-olho-dela": _milhar(provado.get("olho-dela", 0)),
        "mapa-provado-descritor": _milhar(provado.get("descritor", 0)),
        "caderno-com-observado-por": _milhar(sum(observado.values())),
        "caderno-observado-olho-dela": _milhar(observado.get("olho-dela", 0)),
        "caderno-observado-bancada": _milhar(observado.get("bancada", 0)),
        "caderno-observado-aparelho": _milhar(observado.get("aparelho", 0)),
        "linhas-do-mapa": _milhar(linhas),
        "colunas-do-mapa": _milhar(len(cabecalho)),
        "colunas-em-pares": _milhar(2 * len(pares)),
        "pares-de-transporte": _milhar(len(pares)),
        "linhas-do-caderno": _milhar(len(ensaios)),
        "colunas-do-caderno": _milhar(len(cabecalho_do_caderno)),
        "caderno-sem-degrau": _milhar(sem_coluna("degrau")),
        "caderno-sem-ponte": _milhar(sem_coluna("ponte")),
        "ultima-linha-da-docstring-do-portao": str(
            ultima_linha_da_docstring(Path(__file__).resolve())
        ),
    }


def valor_gerado(chave: str, fixos: dict[str, str], raiz: Path) -> tuple[str, str | None]:
    """O valor de uma chave, ou `("", motivo)` quando ela não se resolve."""
    if chave.startswith(_PREFIXO_DE_BYTES):
        relativo = chave[len(_PREFIXO_DE_BYTES) :]
        alvo = raiz / relativo
        if not alvo.is_file():
            return "", (
                f"`{chave}`: `{relativo}` não existe nesta árvore. O documento "
                "aponta um endereço que ninguém abre — corrija o caminho, ou "
                "tire a linha"
            )
        return _milhar(alvo.stat().st_size), None
    if chave in fixos:
        return fixos[chave], None
    return "", (
        f"`{chave}` não é uma chave que este gerador saiba medir. As que ele "
        f"sabe: `{_PREFIXO_DE_BYTES}<caminho>`, " + ", ".join(f"`{k}`" for k in sorted(fixos))
    )


def gera_leia_primeiro(texto: str, raiz: Path) -> tuple[str, list[str]]:
    """Reescreve cada marca com o número medido agora."""
    fixos = numeros_do_leia_primeiro(raiz)
    problemas: list[str] = []

    def troca(casamento: re.Match[str]) -> str:
        chave = casamento.group(1)
        valor, motivo = valor_gerado(chave, fixos, raiz)
        if motivo:
            problemas.append(motivo)
            return casamento.group(0)
        return f"<!--@{chave}-->{valor}<!--/-->"

    return _MARCA_GERADA.sub(troca, texto), problemas


def confere_leia_primeiro(raiz: Path, escrever: bool) -> int:
    """`--leia-primeiro`: confere (ou regrava) os números do documento."""
    caminho = raiz / LEIA_PRIMEIRO_RELATIVO
    if not caminho.is_file():
        print(f"ERRO: {LEIA_PRIMEIRO_RELATIVO} inexistente em {raiz}")
        return 2

    antes = caminho.read_text(encoding="utf-8")
    marcas = _MARCA_GERADA.findall(antes)
    soltos = numeros_soltos(antes)
    if not marcas:
        print(
            f"FALHA: {LEIA_PRIMEIRO_RELATIVO} não tem uma única marca "
            "`<!--@chave-->valor<!--/-->`: todo número dele é literal digitado "
            "à mão, e literal caduca calado."
        )
        return 1

    depois, problemas = gera_leia_primeiro(antes, raiz)
    for problema in problemas:
        print(f"  FALHA chave-de-geracao: {problema}")

    divergentes = [
        (chave, publicado, medido)
        for (chave, publicado), (_, medido) in zip(
            marcas, _MARCA_GERADA.findall(depois), strict=True
        )
        if publicado != medido
    ]

    if escrever:
        if depois != antes:
            caminho.write_text(depois, encoding="utf-8")
        for chave, publicado, medido in divergentes:
            print(f"  atualizado `{chave}`: {publicado} -> {medido}")
        print(
            f"{LEIA_PRIMEIRO_RELATIVO}: {len(marcas)} número(s) gerado(s), "
            f"{len(divergentes)} atualizado(s)."
        )
        return 1 if problemas else 0

    for chave, publicado, medido in divergentes:
        print(
            f"  FALHA numero-caduco: `{chave}` publica {publicado} e a medição "
            f"de agora diz {medido}"
        )
    for linha, trecho in soltos:
        print(
            f"  FALHA numero-solto: linha {linha} publica {trecho!r} fora de "
            "marca. Um número desmarcado é invisível para esta régua — "
            "envolva-o em `<!--@chave-->valor<!--/-->` com um gerador que o "
            "meça, ou declare o trecho em `_MEDIDAS_QUE_NAO_SAO_DAQUI`."
        )
    if divergentes or problemas or soltos:
        print("")
        print("Rode: python3 scripts/check_paridade_transporte.py --leia-primeiro --escrever")
        return 1
    print(f"OK: {LEIA_PRIMEIRO_RELATIVO} — os {len(marcas)} números conferem com a medição.")
    return 0


def imprime_resumo(resumo: Resumo, desligadas: list[str]) -> None:
    """O quadro que ela lê para saber ONDE o mapa está cego."""
    print("")
    print("Resumo do censo (nenhum destes números é limiar — são o retrato de hoje):")
    linhas = [
        ("linhas do mapa", resumo.linhas),
        (
            "células de transporte ("
            + " + ".join(ROTULO_DO_LADO[lado] for lado in LADOS)
            + ")",
            resumo.celulas,
        ),
        ("células mudas (ninguém respondeu se aciona)", resumo.celulas_mudas),
        ("linhas mudas nos DOIS lados", resumo.linhas_mudas_dos_dois_lados),
        ("células que afirmam acionar (sim ou parcial)", resumo.celulas_que_afirmam),
        (f"células com `de_onde_sei` = `{DE_ONDE_SEI_FORTE}`", resumo.celulas_medidas),
        (
            f"afirmações fortes (`{ACIONA_FORTE}` + `{DE_ONDE_SEI_FORTE}`)",
            resumo.afirmacoes_fortes,
        ),
        ("     dessas, SEM teste que morda", resumo.afirmacoes_fortes_sem_rede),
        ("linhas com teste que morde", resumo.linhas_com_mordida),
        ("alvos de pytest apontados pelo mapa", resumo.alvos_de_teste),
        ("assimetrias não declaradas", resumo.assimetrias_nao_declaradas),
        (
            "graus que a suíte não sustenta sozinha",
            resumo.graus_fortes,
        ),
        ("     desses, SEM ensaio no caderno", resumo.graus_fortes_sem_ensaio),
        ("     desses, na direção de ENTRADA (o jogo)", resumo.graus_de_entrada),
        ("ensaios lidos do caderno de bancada", resumo.ensaios_no_caderno),
        (
            f"linhas que alcançam o jogo por `{CANAL_QUE_A_MASCARA_DECIDE}`",
            resumo.linhas_que_alcancam_por_uhid,
        ),
        (
            "     dessas, com afirmação forte",
            resumo.linhas_uhid_com_afirmacao_forte,
        ),
        (
            f"     dessas, SEM `{COLUNA_DA_PONTE}`",
            resumo.pontes_nao_declaradas,
        ),
        (
            "citações da escada de vibração conferidas contra o dono",
            resumo.citacoes_da_escada_de_vibracao,
        ),
        (
            "células com conteúdo de um lado (offset, evidência, ressalva…)",
            resumo.celulas_com_conteudo,
        ),
        (
            "     dessas, SEM `de_onde_sei` daquele lado",
            resumo.conteudo_sem_regua,
        ),
    ]
    largura = max(len(rotulo) for rotulo, _ in linhas)
    for rotulo, valor in linhas:
        print(f"  {rotulo.ljust(largura, '.')} {valor}")
    for regra in desligadas:
        print(f"  regra DESLIGADA neste ambiente: {regra}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Censo do mapa de canais: reprova afirmação forte sem teste."
    )
    parser.add_argument(
        "--raiz",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="raiz do repositório (padrão: a deste script)",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help=f"o mapa a censurar (padrão: <raiz>/{CSV_RELATIVO})",
    )
    parser.add_argument(
        "--hoje",
        type=str,
        default=None,
        help="data de referência AAAA-MM-DD (só para teste do prazo de validade)",
    )
    parser.add_argument(
        "--exigir-id-estavel",
        action="store_true",
        help=(
            "regra 17 (Z6-07): reprova `id` que sumiu sem virar `id_v1` de "
            "outra linha, comparando contra --contra. NÃO roda por padrão — "
            "precisa de histórico git, que fixtures de teste sem repo não têm"
        ),
    )
    parser.add_argument(
        "--contra",
        type=str,
        default="HEAD~1",
        help=(
            "ref git para a regra 17 comparar (padrão HEAD~1, só para uso "
            "local — o CI passa a base do evento, nunca HEAD~1: ver "
            "anonymity-check.yml)"
        ),
    )
    parser.add_argument(
        "--leia-primeiro",
        action="store_true",
        help=(
            f"confere os números que {LEIA_PRIMEIRO_RELATIVO} publica contra a "
            "medição de agora, em vez de censurar o mapa"
        ),
    )
    parser.add_argument(
        "--escrever",
        action="store_true",
        help="com --leia-primeiro: regrava os números medidos no documento",
    )
    args = parser.parse_args(argv)

    raiz = args.raiz.resolve()
    if not raiz.is_dir():
        print(f"ERRO: raiz inexistente: {raiz}")
        return 2

    if args.leia_primeiro:
        return confere_leia_primeiro(raiz, args.escrever)
    if args.escrever:
        print("ERRO: --escrever só existe junto de --leia-primeiro")
        return 2

    caminho_csv = args.csv.resolve() if args.csv else raiz / CSV_RELATIVO
    if not caminho_csv.is_file():
        print(f"ERRO: mapa inexistente: {caminho_csv}")
        return 2

    hoje = date.today()
    if args.hoje:
        lida = le_data(args.hoje)
        if lida is None:
            print(f"ERRO: --hoje ilegível: {args.hoje!r}")
            return 2
        hoje = lida

    achados, resumo, desligadas = censo(caminho_csv, raiz, hoje)

    if args.exigir_id_estavel:
        with caminho_csv.open(encoding="utf-8", newline="") as arquivo:
            registros_de_hoje = list(csv.DictReader(arquivo))
        csv_relativo_git = (
            str(caminho_csv.relative_to(raiz))
            if caminho_csv.is_relative_to(raiz)
            else CSV_RELATIVO
        )
        achados.extend(regra_id_estavel(args.contra, csv_relativo_git, raiz, registros_de_hoje))
    falhas = [achado for achado in achados if achado.nivel == FALHA]
    avisos = [achado for achado in achados if achado.nivel == AVISO]

    if avisos:
        print(f"{len(avisos)} aviso(s) — não derrubam este portão hoje:")
        for achado in avisos:
            print(str(achado))
        print("")

    if falhas:
        print(f"FALHA: {len(falhas)} reprovação(ões) em {caminho_csv.name}:")
        for achado in falhas:
            print(str(achado))
        imprime_resumo(resumo, desligadas)
        print("")
        print("Cada linha acima é uma afirmação do mapa sem rede que a sustente.")
        print("Preencha `teste_que_morde` com o id do nó do pytest que reprova")
        print("quando aquela feature quebrar NAQUELE transporte, ou baixe a")
        print("`de_onde_sei` da célula para o que ela de fato é. Vazio é pergunta")
        print("aberta e não reprova; `medido` sem teste, sim.")
        print("")
        pedem = ", ".join(f"`{valor}`" for valor in GRAUS_QUE_EXIGEM_ENSAIO)
        print("E o grau é a MESMA conta na bancada:")
        print(f"{pedem} pedem ensaio do MESMO transporte em")
        print(f"{ENSAIOS_RELATIVO}. Sem ensaio, o degrau honesto é")
        print(f"`{GRAU_MONTOU}` — que já é o que a suíte prova sem aparelho.")
        print("")
        print(f"E `{GRAU_JOGO_REAGIU}` pede mais: só `{OBSERVADOR_QUE_SUSTENTA}`")
        print("o fecha, porque não existe instrumento que leia o estado interno")
        print("de um jogo sob Proton. O degrau que um instrumento vê é")
        print(f"`{GRAU_JOGO_RECEBEU}` — o inode do vpad em `/proc/<pid>/fd`.")
        return 1

    print(f"OK: nenhuma afirmação forte sem rede em {caminho_csv.name}.")
    imprime_resumo(resumo, desligadas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
