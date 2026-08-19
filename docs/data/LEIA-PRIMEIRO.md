# LEIA PRIMEIRO — a porta de entrada das specs

Escrito em 16/08/2026, a pedido dela: *"pensa numa IA que vai precisar pegar do
zero o negócio, como economizar tokens nesse sentido mantendo o máximo de
qualidade de informação?"*

**O que este arquivo é:** o caminho barato até as specs. Ele custa ~6 mil tokens
e ensina a ler o mapa, a consultá-lo por chave e a saber quando parar de confiar
nele. **O que ele não é:** um resumo do mapa. Nada aqui substitui a prosa das
células — ele te dá o endereço dela.

**A conta que justifica este arquivo.** Até hoje havia duas portas: ler o CSV
inteiro (621.456 caracteres em células, ~155 mil tokens) ou não ler nada. O
veredito por lado das 302 linhas, sem uma linha de prosa, custa 27.266
caracteres — **4,4%**. A porta barata sempre existiu; faltava alguém dizer onde
ela fica.

---

## 1. O que existe, onde, e quanto custa

Medido em 16/08/2026 com `stat` e `csv.DictReader`.

| Arquivo | Bytes | O que é | Quando abrir |
|---|---:|---|---|
| `docs/data/mapa-controles.csv` | 654.980 | **A FONTE.** 302 linhas x 45 colunas. Uma linha = uma feature em um controle. É portão, não documentação. | Sempre, mas **filtrado** — nunca com `Read` inteiro. Veja a seção 5. |
| `docs/data/ensaios.csv` | 149.495 | **O LASTRO.** 177 ensaios x 12 colunas. Cada linha é uma medição com hardware na mesa. Casa com o mapa por `linha_id == id`. | Quando a célula do mapa diz `medido` e você quer ver a medição. |
| `specs.html` | 1.275.303 | **DERIVADO** do CSV + do caderno, por `scripts/gerar-mapa.py`. Filtra no navegador. | **IA: não abra.** Ele embute o CSV inteiro como JSON: custa ~2x a fonte pela mesma informação. É excelente para olho humano com navegador, e péssimo para leitura por texto. |
| `docs/protocol/dualsense-referencia-canonica.md` | 97.475 | **O PROTOCOLO.** O que o DualSense entende, byte a byte. | Quando a pergunta é "que report/offset/valor eu mando". Use a régua de conversão da seção 6. |
| `docs/protocol/paridade-bluetooth-versus-cabo.md` | 17.383 | Tabela cabo x rádio em prosa. Declara-se desempatador nas linhas `MEDIDO AO VIVO`. | Para visão geral. **Onde divergir do mapa fora das linhas `MEDIDO AO VIVO`, o mapa vence** — ele tem domínio fechado e portão; a tabela é prosa. |
| `docs/process/METODO-DE-ISOLAMENTO.md` | 54.411 | O ciclo de ensaio: perguntas de sanidade, oito passos, as armadilhas A-1..A-25. | Quando você vai **produzir** medição nova, não consumir. Cuidado: ele ainda ensina o nome de coluna `grau`, que o portão de hoje reprova (seção 6). |
| `scripts/check_paridade_transporte.py` | 53.942 | **O PORTÃO** do mapa, e a melhor explicação de método da casa — a docstring nomeia cada regra e o defeito real que a fez nascer. | Antes de escrever no CSV. Leia as linhas 1-90. |
| `scripts/eliminacao.py` | 9.218 | **O JUIZ.** Lê o caderno e devolve um veredito por suspeito. | Seção 4. |
| `bancada.py` | 19.901 | O formulário que grava no mapa. Define a escada de degraus na linha 64. | Quando for editar célula. |
| `docs/data/mapa-controles-v1.csv` | 138.192 | Arqueologia. O mapa antes da migração. | Praticamente nunca. |

**Sobre os estudos.** `docs/process/estudos/` guarda o histórico por frente. O
molde do que um estudo deve ser está em
`docs/process/estudos/2026-08-15-A-LIGHTBAR-TRAVADA-o-que-ja-caiu-e-o-que-nunca-foi-tentado.md`:
cada hipótese com quem a derrubou, separando REFUTADA de SEM PROVA, e quatro
avisos-contra-becos logo no começo. Se sua pergunta for "o que já foi tentado e
falhou", procure o estudo da frente **antes** do mapa — o mapa guarda o estado,
o estudo guarda o caminho.

---

## 2. Como uma linha do mapa é organizada

`id` é sempre exatamente `chave@controle` (confere em 302 de 302 linhas), então
`vibracao.rumble.ff@dualsense` é uma chave de busca legítima. Os três controles
são `dualsense` (108 linhas), `pro` (97) e `sn30` (97).

22 das 45 colunas vêm em pares `cabo_*` / `radio_*` — cabo e rádio respondidos
lado a lado na mesma linha. As que importam para decidir:

- `existe` — a peça existe no aparelho? (`tem` 137 · `desconhecido` 81 ·
  `nao-tem` 65 · `parcial` 19)
- `cabo_aceita` / `radio_aceita` — o **aparelho** aceita o comando por ali?
- `cabo_aciona` / `radio_aciona` — o **Hefesto** aciona aquilo hoje? É a coluna
  do produto, e é a que o portão lê para dizer o que é afirmação forte.
- `cabo_de_onde_sei` / `radio_de_onde_sei` e `cabo_ate_onde_foi` /
  `radio_ate_onde_foi` — **as duas réguas**, seção 3.
- `teste_que_morde` (62 linhas) e `mordida_provada_em` (29) — o teste que
  reprova quando a cura é arrancada, e a prova de que alguém arrancou e viu.
- `provado_em` (58 linhas, data pura) — quando. Cuidado: `mordida_provada_em`
  tem o mesmo sufixo `_em` e **é prosa**, não data.
- `nota` (217 linhas), `cabo_ressalva` / `radio_ressalva`, `*_evidencia`,
  `*_detalhe` — **a prosa**. É onde mora o que salva trabalho, e é o que este
  documento existe para te ajudar a ler **sob demanda, pela chave**.

**Não confie na coluna `transporte`.** Ela tem seis valores e nenhum deles é o
transporte de hoje: `ambos` (36) e `cabo+rádio` (74) são o mesmo valor com duas
grafias, e `sem linha no v1` (157 linhas, metade do mapa) é marca de migração,
não transporte. Quem responde por transporte são os pares `cabo_*` / `radio_*`.

---

## 3. As duas réguas, em um minuto

São **duas perguntas diferentes**, e por isso duas colunas. Elas se confundem
porque até 15/08/2026 se chamavam `confianca` e `grau` — nomes que não diziam o
que mediam. Os domínios são fechados e o portão reprova valor fora deles.

**Régua 1 — `de_onde_sei`: DE ONDE VEM A INFORMAÇÃO.**

| Valor | Significa | Células |
|---|---|---:|
| `medido` | alguém pôs o aparelho na mesa e viu | 123 |
| `inferido-do-codigo` | alguém leu a fonte (nossa ou do driver) | 290 |
| `afirmado-no-doc` | está escrito em alguma página | 7 |
| `incerto` | ninguém sabe de onde saiu | 7 |
| vazio | ninguém respondeu este lado | 177 |

**Régua 2 — `ate_onde_foi`: ATÉ ONDE A PROVA CHEGOU.** É uma escada, e cada
degrau contém o anterior.

| Valor | Direção | Significa | Células |
|---|---|---|---:|
| `MONTOU` | saída | o produto montou o report | 71 |
| `SAIU NO FIO` | saída | o byte saiu e algo voltou | 15 |
| `O APARELHO OBEDECEU` | saída | acendeu, girou, saiu som | 21 |
| `O JOGO RECEBEU` | **entrada** | o processo do jogo ABRIU o nó do nosso vpad | 0 |
| `O JOGO REAGIU` | **entrada** | o jogo agiu sobre o que recebeu | 0 |
| vazio | — | a escada não foi registrada | 509 |

**OS DOIS ÚLTIMOS SÃO DE 19/08/2026, e nasceram de um buraco que este arquivo já
confessava em duas linhas** — `toque.touchpad` diz *"quem ler `radio_aciona =
sim` aqui está lendo 'o vpad ENTREGA', não 'o jogo REAGE'"*, e
`movimento.giroscopio.jogo` diz *"o repasse está íntegro e o jogo não reage: a
falha, se existir, é DEPOIS do vpad, e ninguém a localizou"*. Os três degraus
antigos medem só a IDA (produto -> aparelho); os dois novos medem a volta que
importa para jogar.

**`O JOGO REAGIU` só fecha com `olho-dela`**, e o portão derruba quem tentar
outra coisa: não existe régua nesta casa que leia o estado interno de um jogo
sob Proton. `O JOGO RECEBEU` fecha com instrumento — mas o instrumento ainda
não foi escrito, e as duas sondas que existem hoje mentem nesse cenário (uma
conta handle MORTO como fd vivo; a outra varre só os PIDs da Steam, onde o
`winedevice` não está).

**A confusão que custa caro, dita na cara: uma régua não implica a outra.** O
cruzamento das 604 células (302 linhas x 2 lados), medido hoje:

| | vazio | MONTOU | SAIU NO FIO | OBEDECEU |
|---|---:|---:|---:|---:|
| `medido` | **63** | 24 | 15 | 21 |
| `inferido-do-codigo` | 250 | **40** | 0 | 0 |
| `afirmado-no-doc` | 6 | 1 | 0 | 0 |
| `incerto` | 7 | 0 | 0 | 0 |
| vazio | 177 | 0 | 0 | 0 |

Leia as duas casas em negrito e você entendeu o mapa:

- **63 células são `medido` com a escada vazia.** Alguém mediu e não registrou
  até onde a prova chegou. `medido` **não** quer dizer que o aparelho obedeceu.
- **40 células são `inferido-do-codigo` com `MONTOU`.** Ninguém tocou no
  aparelho: leram a fonte e viram que o produto monta o report. Subir o primeiro
  degrau não exige hardware — subir do segundo em diante, exige.

**Afirmação forte** é `aciona=sim` **e** `de_onde_sei=medido`. **Grau forte** é
`SAIU NO FIO` ou `O APARELHO OBEDECEU` — hoje são **36 células, em 21 linhas**,
e a regra 6 do portão exige que cada uma tenha ensaio casado no caderno. Conferi
agora: **36 de 36 têm. Zero órfãos.**

**O mapa da ignorância, de graça:** o caderno cobre **30 das 302 linhas
(9,9%)**. As outras 272 são inferência de código. Antes de gastar leitura,
saiba que o lastro empírico está concentrado em 10% do mapa.

---

## 4. A eliminação, em um parágrafo

`scripts/eliminacao.py` responde outra pergunta que o mapa: não "onde a prova
chegou", mas "**quem é a causa**". O método é o par com/sem: para cada suspeito,
juntam-se os ensaios do caderno em que ele estava presente (`presente=sim`) e
aqueles em que estava ausente, e comparam-se os `resultado`. Se o resultado
**vira** quando o suspeito sai, o veredito é `e-a-causa`; se **não muda**, é
`nao-e-a-causa`; se só existe um dos dois lados, é `inconclusivo`; se o mesmo
lado deu resultados diferentes, é `confuso`; sem nenhum ensaio, é
`nunca-investigado`. O vocabulário é deliberado e está justificado por escrito no
próprio arquivo: **não se diz "culpado"/"inocente"** porque o mesmo instrumento
serve para caçar o report que trava a lightbar e para confirmar o byte que faz o
motor girar — chamar de culpado um mecanismo que funciona já confundiu uma vez,
em 10/08. E `nao-e-a-causa` é a metade que dá lucro: um culpado isolado diz "por
onde eu aciono", os inocentados dizem "**o que eu posso parar de fazer**" — foi
assim que a lightbar caiu de cinco canais escritos para um.

**Onde os dois sistemas não se falam, e você precisa saber:** o portão do mapa
cobra que exista ensaio, nunca qual foi o veredito. Resultado medido hoje: das
36 células de grau forte, **só 12 têm julgamento conclusivo**; 24 descansam sobre
ensaios que o próprio juiz chama de `inconclusivo`. Isso **não é contradição** —
são perguntas diferentes — mas se você ler "O APARELHO OBEDECEU" no mapa e
"falta o ensaio que discrimina" no caderno, é isto que está acontecendo.

---

## 5. Como consultar sem ler tudo

**Cole isto e rode da raiz do repositório.** Ele responde "esta feature está
medida?" e, junto, diz **quanta prosa existe** naquela linha — para você decidir
se paga por ela.

```python
import csv

ALVO = "vibracao.rumble"          # trecho da chave, ou "" para tudo
CTRL = "dualsense"                # dualsense | pro | sn30, ou "" para todos

with open("docs/data/mapa-controles.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if ALVO not in r["chave"] or (CTRL and r["controle"] != CTRL):
            continue
        print(r["id"])
        for lado in ("cabo", "radio"):
            print(f'  {lado:5} aciona={r[lado+"_aciona"] or "-":12}'
                  f' de_onde_sei={r[lado+"_de_onde_sei"] or "-":18}'
                  f' ate_onde_foi={r[lado+"_ate_onde_foi"] or "-"}')
        print(f'  prosa: nota={len(r["nota"])}c'
              f' cabo_ressalva={len(r["cabo_ressalva"])}c'
              f' radio_ressalva={len(r["radio_ressalva"])}c'
              f' | morde={"sim" if r["teste_que_morde"] else "nao"}'
              f' provado_em={r["provado_em"] or "-"}')
```

Saída real, hoje, para o rumble do DualSense:

```
vibracao.rumble.ff@dualsense
  cabo  aciona=sim          de_onde_sei=medido             ate_onde_foi=O APARELHO OBEDECEU
  radio aciona=sim          de_onde_sei=medido             ate_onde_foi=O APARELHO OBEDECEU
  prosa: nota=263c cabo_ressalva=4750c radio_ressalva=4750c | morde=sim provado_em=2026-08-11
```

Custo: ~600 caracteres em vez de 621 mil. E a última linha é o aviso que
importa — **há 4.750 caracteres de ressalva ali, e você ainda não os leu.**

**Ler a prosa de uma célula, quando o veredito não basta:**

```python
import csv, textwrap
ALVO = "vibracao.rumble.ff@dualsense"
r = next(x for x in csv.DictReader(open("docs/data/mapa-controles.csv", encoding="utf-8"))
         if x["id"] == ALVO)
for c in ("nota", "cabo_ressalva", "radio_ressalva", "cabo_evidencia",
          "radio_evidencia", "estado_hoje", "assimetria_declarada"):
    if r[c]:
        print(f'--- {c}\n{textwrap.fill(r[c], 92)}\n')
```

**Ver os ensaios que sustentam a linha:**

```python
import csv
ALVO = "vibracao.rumble.ff@dualsense"
for x in csv.DictReader(open("docs/data/ensaios.csv", encoding="utf-8")):
    if x["linha_id"] == ALVO:
        print(x["quando"], x["transporte"], x["suspeito"], "presente=" + x["presente"],
              "->", x["resultado"], "|", x["observado_por"])
```

**A tabela cabo x rádio inteira, que cabe em 1.660 caracteres:** só **35 das 302
linhas** têm `cabo_aciona != radio_aciona`. O mapa paga 22 colunas espelhadas em
todas as 302 para uma distinção que existe em 11,6% delas.

```python
import csv
for r in csv.DictReader(open("docs/data/mapa-controles.csv", encoding="utf-8")):
    if r["cabo_aciona"] != r["radio_aciona"]:
        print(f'{r["id"]:58} cabo={r["cabo_aciona"] or "-":6} radio={r["radio_aciona"] or "-":6}'
              f' declarada={"sim" if r["assimetria_declarada"] else "NAO"}')
```

Dessas 35, **14 têm `assimetria_declarada` vazia**. A regra 7 do portão é AVISO
de propósito — a divergência mais comum é "ninguém respondeu esse lado", que é
buraco de censo, não mentira. As 14 são a régua de quando promovê-la a FALHA.

---

## 6. O vocabulário canônico

**A regra para resolver qualquer dúvida de nome: vence o vocabulário que o
PORTÃO lê.** Um nome que nenhum portão lê é apelido, por mais bem escrito que
esteja o documento onde ele aparece.

| Canônico | Onde é lei | Sinônimos e apelidos que apontam para ele |
|---|---|---|
| `de_onde_sei` | domínio em `scripts/check_paridade_transporte.py` | `confianca` (nome até 15/08/2026); "confiança" na prosa das notas |
| `ate_onde_foi` | domínio no mesmo portão | `grau` (nome até 15/08/2026 — **o `METODO-DE-ISOLAMENTO.md` ainda ensina este, e o portão o reprova**); `degrau` (`bancada.py`) |
| `MONTOU` / `SAIU NO FIO` / `O APARELHO OBEDECEU` | `scripts/check_paridade_transporte.ESCADA` (o `bancada.py` importa de lá desde 19/08/2026) e o domínio do portão | maiúsculas exatas, sem variação: um degrau com outra tipografia atravessa a regra 6 sem ser visto |
| `e-a-causa` / `nao-e-a-causa` | `scripts/eliminacao.py`, decisão datada de 10/08 | `culpado` / `inocentado` — **abandonados por decisão escrita**, mas ainda vivos no rodapé do `specs.html` e no `METODO-DE-ISOLAMENTO.md` |
| **rádio** (prosa) · `radio_` (coluna) · `radio` (valor no caderno) | os três coexistem por construção | `Bluetooth`, `BT`. **Ao buscar por texto, procure sem acento** — `grep 'rádio'` não acha uma linha sequer do caderno |
| `nao-tem` | `DOMINIO_EXISTE`, sem acento | `não-tem` aparece acentuado na prosa das notas; o portão rejeita o acentuado |
| **mapa** = `docs/data/mapa-controles.csv` (fonte) | — | "specs", "mapa de canais", "CSV". **`specs.html` é o derivado** — editá-lo à mão é o defeito que o `--check` existe para pegar |
| **caderno** = `docs/data/ensaios.csv` | — | "caderno de ensaios", "caderno de eliminação", "bancada" — mas *bancada* também designa `bancada.py` e a sessão de medição com hardware na mesa |
| **alto-falante** | correção dela, 15/08 | "placa de som" foi usado por engano e ela mandou desfazer; "speaker" só no nome de constante |

**Termos que ainda colidem — não invente a resposta, é decisão dela:**

- `transporte` = `ambos` **ou** `cabo+rádio` (36 e 74 linhas, mesmo sentido). A
  coluna não tem domínio declarado, então o portão não vê. Não filtre por ela.
- `provado_por` (mapa, 58 linhas: `aparelho` 40, `fonte-do-driver` 11,
  `olho-dela` 4, `descritor` 3) e `observado_por` (caderno, 177 linhas:
  `olho-dela` 104, `bancada` 51, `aparelho` 22) fazem a mesma pergunta com
  vocabulários diferentes. **Quem sustenta o degrau mais alto é o
  `observado_por` do caderno** — é lá que a regra 10 do portão foi cobrar.
  Preencher `provado_por` não sustenta grau nenhum.
- `canal` tem dois sentidos: no CSV, `cabo_canal` é o **meio técnico** (`hidraw`,
  `uhid`, `evdev`, `sysfs`, `dbus`, `alsa-pipewire`, `outro`); na fala da casa,
  "canal" é o **suspeito acionável** (foi assim no estudo da lightbar).
- `espelho` tem dois sentidos, e um deles já custou uma investigação: o nosso
  gamepad virtual, e o espelho Xbox que o Steam Input faz de **cada** controle
  que vê — inclusive do nosso.
- `desconhecido` versus **célula vazia**: a legenda do `specs.html` declara vazio
  como "ninguém respondeu". Nada escreve o que os separa. Trate `desconhecido`
  como "perguntamos e não sabemos" e vazio como "ninguém perguntou", mas saiba
  que isso é convenção deste documento, não regra do portão.

**A régua de conversão entre a canônica e o mapa** — as duas primeiras portas
que o `CLAUDE.md` manda abrir usam escalas diferentes, e não havia tradução
escrita em lugar nenhum:

| Grau na `dualsense-referencia-canonica.md` | Equivale, no mapa, a |
|---|---|
| MEDIDO AQUI · MEDIDO NO APARELHO | `de_onde_sei = medido` |
| FONTE DESTA MÁQUINA · LIDO NO FONTE | `de_onde_sei = inferido-do-codigo` |
| ALTA · MÉDIA · BAIXA | `de_onde_sei = afirmado-no-doc` |
| HIPÓTESE | `de_onde_sei = incerto` |
| LIDO NO DESCRITOR | **sem equivalente.** Mais próximo: `provado_por = descritor`. Não escreva `medido` — a própria canônica avisa que o descritor é dado do aparelho e **não** é o que o firmware faz com ele |

---

## 7. Onde este documento para, e a prosa começa

Um esqueleto que parecesse completo seria pior que nenhum. **Vá à prosa quando:**

- a célula tem grau forte (**36 células**) — a ressalva é onde mora a condição
  sob a qual a prova vale;
- a linha tem ensaio no caderno (**30 linhas**) — o caderno tem o "como";
- a linha tem `nota` (**217 linhas**) — é onde ficam as notas datadas, e a regra
  da casa é que **decisão medida não se apaga**;
- os dois lados divergem (**35 linhas**) — leia `assimetria_declarada`, ou saiba
  que ela está vazia em 14 delas.

**Duas prosas que já salvaram medição neste mês**, para você entender o que está
em jogo antes de achar que a ressalva é enfeite: uma célula dizia "nada foi
enviado a aparelho nenhum" e caducou no mesmo dia; outra guardava a observação
dela de 02/08 sobre o alto-falante — que um agente quase enfraqueceu por achar
que não estava medido, porque mediu outra coisa (ausência de placa ALSA no
rádio) e concluiu demais.

**O que eu não consigo te dar barato, e é honesto dizer:** por que uma célula
está vazia. Os blocos que explicam isso vivem na `nota`, e é neles que a
repetição do CSV se concentra (seção 8).

---

## 8. O que falta: `mapa-resumo.csv` — PROPOSTA, não implementado

Nada foi criado nem alterado por este documento além dele mesmo. Isto é uma
proposta com número medido, para decisão dela.

**O artefato.** Um `docs/data/mapa-resumo.csv` de 10 colunas — as 8 do esqueleto
mais dois **ponteiros para a prosa**:

```
chave, controle, cabo_de_onde_sei, cabo_ate_onde_foi, radio_de_onde_sei,
radio_ate_onde_foi, teste_que_morde, provado_em, tem_ensaio, tem_nota
```

`teste_que_morde` entra como `sim`/vazio, não como o texto — o texto é prosa e
fica na fonte. `tem_ensaio` e `tem_nota` são derivados na hora: dizem se aquela
linha aparece no caderno e se tem nota, isto é, **onde parar de confiar no
resumo**. É o que impede o esqueleto de parecer completo.

**Medido, gerando o arquivo em rascunho:** 20.598 caracteres, **~5.150 tokens,
3,3% do CSV**. Sai mais barato que o esqueleto cru de 8 colunas (27.266) porque
o `teste_que_morde` vira booleano. As três primeiras linhas reais:

```
chave,controle,cabo_de_onde_sei,cabo_ate_onde_foi,radio_de_onde_sei,radio_ate_onde_foi,teste_que_morde,provado_em,tem_ensaio,tem_nota
audio.alto_falante,dualsense,medido,O APARELHO OBEDECEU,inferido-do-codigo,,,2026-08-15,sim,sim
audio.alto_falante,pro,inferido-do-codigo,,inferido-do-codigo,,,,,
```

**Como o portão impede que ele envelheça.** Do mesmo jeito que o `specs.html`, e
no mesmo script: `scripts/gerar-mapa.py` já tem `monta()`, que constrói o
conteúdo na memória, e um `--check` que compara o publicado com o que as fontes
produzem **por conteúdo, não por relógio**. O acréscimo é simétrico — um
`monta_resumo()` ao lado, escrito no mesmo `main()`, e o `--check` comparando os
dois arquivos em vez de um. O gerador já lê as duas fontes de que o resumo
precisa. **Não implementei** por três razões: `gerar-mapa.py` está sendo tocado
por outros agentes agora; `--check` **reprova neste minuto** (o `specs.html`
publicado está desatualizado — a contagem 34 contra 35), então eu não teria como
provar verde; e um derivado sem portão é exatamente o que a casa proíbe.

**A ordem certa é regenerar o `specs.html` primeiro** — enquanto ele estiver
velho, o portão de frescor está vermelho e qualquer derivado novo nasce na
sombra dele.

### Repetição medida no CSV — proposta, e nenhuma linha apagada

A regra é dura e eu a respeitei: **não apaguei uma linha de prosa.** O que
segue é medição, para ela decidir.

| O que se repete | Custo | Meu parecer |
|---|---:|---|
| `nota`: o preâmbulo de migração v1, em 128 linhas ("o v1 não tem linha desta chave para este controle") | 14.534 chars no primeiro segmento; 12.717 de eco puro | **É o único corte que passa no teste da casa.** Nas 128 linhas, `id_v1` está vazio em 128 de 128 — a frase afirma o que a coluna já afirma, e é derivável por construção. Não é medição: é contabilidade de migração. O caminho honesto é o **gerador reemitir a frase** a partir de `id_v1` vazio, não apagá-la do que o leitor vê. |
| `cabo_*` idêntico ao `radio_*` na mesma linha (7 pares de colunas) | 53.677 chars, ~8,7% do CSV | A mesma frase dita duas vezes na mesma linha. O caso extremo é `vibracao.rumble.ff@dualsense`: 4.750 caracteres de ressalva duplicados palavra por palavra. Além do custo, é **risco de contradição** — quem corrigir um lado e esquecer o outro deixa a linha se contradizendo sem portão nenhum notar. Um marcador `idem` (que `cabo_detalhe` já usa em algumas linhas) preserva 100% da informação, com o gerador expandindo. |
| `nota`: os blocos "POR QUE ESTA LINHA EXISTE", repetidos entre linhas irmãs | 16.050 chars de eco | **Eu não tocaria por referência.** Esses blocos são justamente os que explicam por que a célula está vazia, e é na linha isolada — achada por `grep`, não por leitura sequencial — que a próxima pessoa cai. Se for encolher, o caminho é a fonte guardar a **chave do bloco** e o gerador expandir; nunca um `ver nota-familia:coop` no que se lê. |
| `cabo_ressalva`, `radio_ressalva`, `*_evidencia` (repetição entre linhas diferentes) | 12% a 20% | **Não tocar.** Ali a repetição é contexto de célula, não boilerplate. |

Para calibrar: a coluna `nota` tem 113.604 caracteres em 217 células. Delas,
29.742 são células byte a byte idênticas a outra, e o eco por trecho (blocos de
60 caracteres ou mais, separados por ` · `) soma 36.950. **Só a linha 1 desta
tabela é corte; as outras são reorganização — a informação que chega ao leitor
não muda em nenhuma delas.**

---

## 9. Se você só vai ler uma coisa

1. As duas réguas são independentes: `medido` **não** implica `O APARELHO
   OBEDECEU` — 63 células provam isso.
2. O caderno cobre 10% do mapa. O resto é leitura de código, e o mapa diz
   qual é qual, de graça, na coluna `de_onde_sei`.
3. Consulte por chave com o código da seção 5. Nunca dê `Read` no CSV, e nunca
   abra o `specs.html`.
4. Quando a célula tiver grau forte, ensaio ou nota, **a prosa é obrigatória** —
   e ela é o motivo de este projeto não repetir trabalho já pago.
