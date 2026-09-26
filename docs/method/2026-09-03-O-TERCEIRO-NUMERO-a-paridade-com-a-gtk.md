# O TERCEIRO NÚMERO — a paridade com a GTK

> ## ATENÇÃO — ESTE NÚMERO MEDE A BANCADA, NÃO O QUE ELA ABRE
>
> **Medido em 04/09/2026, e é o achado maior da leva daquele dia.** As dez
> frentes de aba entregaram, e **nenhuma publicou** — `git diff` em
> `src/hefesto_dualsense4unix/interface/paginas/` não mostra **um byte** de
> mudança. O produto que ela abre continua o de antes.
>
> ```
> cadeado         bancada=2  publicado=0
> reenviar        bancada=2  publicado=0
> auto-cores      bancada=1  publicado=0
> forca-mesa      bancada=1  publicado=0
> ```
>
> **E isso está CERTO**, não é falha: a direção é `mockup/` → produto, nunca o
> contrário, e *publicação é o olho dela* (PROVA-DE-TELA-01). As dez frentes
> recusaram publicar porque cada uma move pixel, e pixel é decisão dela.
>
> **A leitura correta da tabela abaixo:** ela diz *"o código sabe fazer"*, não
> *"ela já tem"*. A distância entre as duas é UMA leva — a de publicação, que
> é dela aprovar aba por aba.


**03/09/2026.** Esta casa tinha dois números sobre a interface nova, e os dois
mediam a interface nova **contra ela mesma**:

| número | o que compara | o que ele não pode responder |
| --- | --- | --- |
| a régua de tela | quantos campos da página são escritos pelo produto | se o campo devia existir |
| a régua do mockup | o publicado contra o desenho que ela aprovou | se o desenho cobre o que o produto já fazia |

Nenhum dos dois responde a pergunta da qual sai a fila de trabalho: **o que a
janela GTK faz e a interface em HTML ainda não faz.** Esta é a medição desse
terceiro número, e ele nasce com dono, com dado e com portão.

**O número não se escreve nesta linha.** Ele está na tabela da §2, linha
`TODAS` — gerada da contagem do CSV e conferida pela regra `numero-publicado`.

Aqui havia uma segunda cópia dele, e ela envelheceu: em 04/09/2026 esta linha
dizia **14%** sobre uma tabela do mesmo arquivo que já dizia **27%**. Os dois
números estiveram certos — o 14% é o de 03/09 (`548c0fbc`), o 27% é o de hoje —
e o defeito não foi de medição: **era o número ter dois donos, e só um deles ter
régua.** A cópia sai; o dono fica.

---

## 1. O que se mediu, e como

**396 features**, uma a uma, lendo os dois lados no fonte — a janela GTK
(`gui/main.glade` + `app/actions/` + `app/widgets/`) contra a interface em HTML
(`interface/` + `app/telas/`) — e, em oito das dez abas, **rodando o pacote da
aba contra o daemon vivo dela**, em leitura pura.

Uma feature é uma coisa que a tela **faz ou diz**: um botão, um campo que se
repinta, um aviso que acende sozinho, uma recusa com frase. Cada uma recebeu um
veredito e o **endereço dos dois lados**, para a próxima pessoa conferir sem
refazer a leitura.

| veredito | o que quer dizer |
| --- | --- |
| `IGUAL` | os dois fazem a mesma coisa, pelo mesmo motor |
| `DIFERENTE` | os dois fazem, e não a mesma coisa |
| `FALTA_NO_HTML` | a GTK faz, o HTML não |
| `SO_NO_HTML` | o HTML faz, e a GTK nunca fez |
| `NAO_DA_PARA_SABER` | não se decide lendo — precisa de bancada |

**A paridade é `IGUAL / total`.** É a régua mais dura de propósito: `DIFERENTE`
não conta como paridade, porque a queixa dela que originou tudo foi exatamente
essa — *"o produto via html não funcionou igual o gtk"*.

O dado mora em **[`docs/data/paridade-gtk-html.csv`](../data/paridade-gtk-html.csv)**,
395 linhas, e o portão que o mantém honesto é
**[`scripts/check_paridade_gtk_html.py`](../../scripts/check_paridade_gtk_html.py)**.

---

## 2. O número, por aba

<!-- TABELA-DA-PARIDADE -->
| aba | feats | IGUAL | DIFER | FALTA | SO_HTML | ? | paridade |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 01-jogar | 42 | 11 | 24 | 2 | 4 | 1 | 26% |
| 02-controles | 50 | 16 | 24 | 6 | 4 | 0 | 32% |
| 03-gatilhos | 31 | 15 | 9 | 1 | 5 | 1 | 48% |
| 04-iluminacao | 35 | 9 | 12 | 6 | 7 | 1 | 26% |
| 05-vibracao | 31 | 13 | 11 | 4 | 3 | 0 | 42% |
| 06-navegacao | 40 | 15 | 16 | 0 | 9 | 0 | 38% |
| 07-lancadores | 29 | 9 | 12 | 0 | 8 | 0 | 31% |
| 08-conexoes | 49 | 16 | 26 | 6 | 1 | 0 | 33% |
| 09-sistema | 38 | 13 | 18 | 4 | 3 | 0 | 34% |
| 10-perfis | 50 | 14 | 20 | 7 | 9 | 0 | 28% |
| TODAS | 395 | 131 | 172 | 36 | 53 | 3 | 33% |<!-- /TABELA-DA-PARIDADE -->

A tabela é **gerada da contagem do CSV** e conferida pelo portão (regra
`numero-publicado`): quem mexer no dado e não regerar esta seção é barrado
nomeando a aba que divergiu. Um número publicado que não se pode conferir vira
folheto, e este é o número que ela vai ler para decidir.

**Duas correções de fato, e as duas são de 03/09.** O primeiro rascunho desta
medição publicou **394 features**, e duas `FALTA_NO_HTML` a menos que a conta:
as abas 08 e 09 contaram uma feature a menos cada uma **no resumo que
escreveram**, e a lista de features delas — que é o dado — sempre teve **49** e
**38**, como a tabela acima continua mostrando. E o `01-jogar` publicou **11%**
onde a divisão daquele dia dava **12%** (5 de 42).

**A 07 CAIU DE 47% PARA 31% EM 21/09/2026, e não perdeu função.** Ela
pediu os mesmos botões em todos os lançadores, e os sete que só a Steam tinha
saíram: o reparo do atalho e o Steam Input desligado passaram a ser do vigia
`hefesto-steam-input-guard`, sem clique. Um `IGUAL` que vira *"automático"* é
`DIFERENTE` pela régua — que é dura de propósito —, e o «Ver o que impede»,
que só o HTML tinha, saiu do mapa com o botão. Na mesma recontagem a linha do
«Aplicar aos jogos» da 09 fechou: o botão já estava publicado.

**A 08 CAIU DE 45% PARA 33% EM 23/09/2026, e a razão é a mesma régua dura.**
A seção «Rádio e Adaptadores» virou o desenho aprovado dela
(TRANSPLANTE-DA-SECAO-01): a tabela dos adaptadores virou cartões, os vizinhos
viraram selos, a vizinhança passou a ser dita por porta e a ocupação passou a
ser LIDA do daemon em vez de recalculada — quatro `IGUAL` viraram `DIFERENTE`.
E duas ressalvas saíram com a tabela, sem lugar no desenho: o hub em comum e as
contagens do gabinete, agora `FALTA_NO_HTML` declaradas.

**As duas correções ficam; os valores que elas corrigiram, não.** O total de
`FALTA_NO_HTML` e a paridade da `01-jogar` mudam a cada cura, e quem quiser os
de hoje lê a tabela, que tem dono. O que não caduca é a lição:
**o resumo de uma aba não é o dado dela.**

---

## 3. O padrão, e ele é UM SÓ nas dez abas

> **O que tem GESTO migrou. O que é LEITURA AO VIVO não.**

Os botões funcionam, e funcionam bem: reusam o motor da GTK **função por
função** — `rumble_policy_set_checked`, `acao_mic`, `acao_speaker_mudo`,
`LogicaDoMapa`, `ordem_de_exibicao`, `politica_do_rotulo`. É a lei 0 sendo
cumprida: quase nada foi reescrito.

A leitura viva não migrou quase nada. E **isso não é tela vazia — é tela que
mente**, porque o que está na página é o valor que o gerador cravou do desenho
aprovado, e ele fica lá para sempre. Fotografado no HTML publicado, contra o
daemon vivo dela:

| a tela diz | o daemon diz |
| --- | --- |
| três glifos acesos no card do P1 (`cross`, `dpad_up`, `l2`) | ninguém tocou em botão nenhum |
| L2 em `200 / 255` | o gatilho está solto |
| giroscópio em `+143.2 / −412.0 / +22.8` | o controle está parado |
| volume do alto-falante `100` em todo controle | um valor por controle |
| degrau `Máximo` aceso na coluna do P1 | `rumble_policy = 'balanceado'` |
| interruptor do mouse em **Ligado** | `mouse_emulation.enabled = False` |
| chip `Sony DualSense` aceso, e `Xbox 360` no P2 | `flavor = dualsense` nos dois |
| barra de luz `#7EB8D4` | o campo ao lado dela diz `#0000FF` |
| o card do P2 mostra tudo isso igual ao P1 | o daemon só publica leitura para o primário |

A causa é uma só e está no vocabulário de endereço: **a página não tem onde pôr
o valor.** A 01 publicada tem 11 `data-campo` e **zero** `data-hef-alvo` /
`data-hef-quando`; a 08 tem 13 `data-campo` e nenhum deles é `via`, `bateria`,
`ponte` ou `fragil` — que são exatamente os quatro campos que o pacote já emite
por controle.

**A metade boa disso**: em vários pontos o dado JÁ é calculado certo e morre no
caminho. O `a09_sistema` lê o autostart na faixa lenta e o achatamento joga
fora; as `travas` da aba Sistema (quais gestos estão cinza, e por quê) são
calculadas em `gui/aba_sistema.py` e não são reencaminhadas; `AVISOS_DA_TELA`
tem as seis fontes puras da coluna Atenção da aba Início e quem as chama é a
bancada, não o produto. **Boa parte da dívida é ponte entre dois arquivos que já
existem, não código novo.**

---

## 4. As três categorias, com exemplo

### `FALTA_NO_HTML` — a GTK faz, o HTML não

**Quantas são hoje: a coluna `FALTA` da tabela da §2.** Em 03/09 este era o
maior bloco, com 44% do total, e era ele que decidia a fila. **Deixou de ser**,
e é o que as levas pagaram: as curas foram desproporcionalmente daqui, e hoje o
maior bloco é o `DIFERENTE`.

- **`05-vibracao` · qual degrau está aceso.** A GTK tem
  `_apply_policy_to_widgets` (`app/actions/rumble_actions.py:699`) fazendo a
  exclusão mútua entre os quatro. No HTML a classe `on` está cravada da cena do
  mockup: com `rumble_policy = 'balanceado'` no daemon, a tela mostra `Máximo`
  aceso no P1. Ela clica, o daemon obedece, e a tela não muda. **O produto já
  sabe disso por escrito** — `SEM_DONO["degrau-aceso"]`
  (`src/hefesto_dualsense4unix/interface/pacotes/a05_vibracao.py:49`) — e o
  pintor já tem o alvo `classe`. Falta o endereço no HTML e a emissão no pacote.
- **`02-controles` · os 16 glifos.** `_refresh_glyphs` no card da GTK; no HTML,
  três glifos com a classe `on` do mockup, acesos o tempo todo.
<!-- A LINHA DO BRILHO SAIU DAQUI EM 03/09/2026, e ela era a maior falta
     desta aba: *"contados os gestos das duas páginas, nenhum de brilho em
     lugar nenhum — o trilho é decoração"*. O trilho passou a GRAVAR (decisão
     dela, "Grava na hora") e a linha virou `DIFERENTE`, com a diferença
     medida e o endereço dos dois lados no CSV. Ela não é decisão a preservar:
     é um fato que a medição derrubou. -->
- **`03-gatilhos` · os 73 parâmetros.** 17 dos 19 modos têm ajuste, e na GTK
  todos são `Gtk.Scale` que ela arrasta. No HTML são barras de leitura, sem
  `data-gesto` e sem `<input>`. Escolher um modo aplica os padrões dele e
  acabou — e "Montar do zero", cujos padrões são oito zeros, é um modo que não
  faz nada.
- **`10-perfis` · o botão "Salvar este perfil".** Com ele foram embora as cinco
  perguntas do Salvar e a fusão com o rascunho das outras abas.

### `DIFERENTE` — os dois fazem, e não a mesma coisa

**Quantas são hoje: a coluna `DIFER` da tabela da §2.** É a categoria que mais
engana, porque a tela não fica vazia: ela responde outra pergunta. E ela
**cresce** enquanto o trabalho anda: das dez linhas que deixaram
`FALTA_NO_HTML` entre 04/09 de manhã e a tarde, quatro pararam aqui e seis
foram direto a `IGUAL`.

- **`05-vibracao` · o número do multiplicador.** A GTK mostra o **pedido**
  (`_POLICY_MULT[policy] * 100` = 100); o HTML mostra o **aplicado**
  (`rumble_mult_applied` = 0,7 → `70%`). Medidos lado a lado, ao vivo. E o 0,7 é
  um valor que o próprio produto documentou como preso em passthrough ocioso —
  o HTML publica exatamente essa aparência.
- **`06-navegacao` · o campo mudou.** A GTK edita `Profile.key_bindings` (9
  botões, combinação livre); o HTML edita `Profile.button_actions` (21 botões,
  lista fechada). Os dois existem e o daemon aplica os dois — mas o
  `apply_button_actions` roda **depois** e reescreve o conjunto inteiro de
  bindings a partir do de fábrica. **No instante em que ela clica "Guardar" na
  tela nova, tudo o que editou na tabela da GTK deixa de valer, em silêncio.**
- **`01-jogar` · a palavra do transporte.** A GTK diz `cabo` e `rádio`, com
  função dona (`palavra_do_transporte`); o HTML diz `USB` e `BT`, com um `if`
  inline. Duas cópias da mesma tradução, e o HTML voltou ao jargão que a GTK
  tinha abandonado.
- **`04-iluminacao` · onde a cor é gravada.** A GTK guarda a **intenção** no
  rascunho; o HTML **fotografa o que está aceso**. A diferença aparece quando o
  daemon não aplicou: a GTK salva o que ela pediu, o HTML salva o que o aparelho
  está mostrando.

### `SO_NO_HTML` — o HTML faz, e a GTK nunca fez

**Quantas são hoje: a coluna `SO_HTML` da tabela da §2.**

**Ninguém pode "consertar" removendo.** Boa parte é motor que já existia em
`integrations/` e nunca tinha tela: o histórico do perfil (`Voltar à de
ontem`), o `Retomar` da pausa do daemon, os cinco lançadores, `Meus efeitos`, a
tabela de ajuste por controle, o `Exportar`. A aba 07 sozinha tem nove, e **as
nove são a lei 0 cumprida**: não se recriou nada, ligou-se o que estava escrito.

E há três lugares em que **o HTML está certo e a GTK errada**, medidos:
escolher "Desligado" no campo de modo manda `trigger.reset` (a GTK arma a trava
com `Off`); o HTML nomeia a curva salva (a GTK sempre mostra "Personalizar"); e
os três pontos em que a GTK aplica o wrapper em massa ignoram a lista "não usar
neste jogo" (o HTML passa `excluir=`). **Três linhas a NÃO copiar de volta.**

### `NAO_DA_PARA_SABER` — não se decide lendo

**Quantas são hoje: a coluna `?` da tabela da §2.**

Elas precisam de bancada: se a lista de 19 modos abre no compositor dela, se o
`Automático` de fato larga a luz para o jogo, se o reparo do HTML repõe a linha
no `.vdf` dela, e se o nome do plástico chega ao cartão. **Ficam registradas como indecidíveis em vez de chutadas** — é a mesma
disciplina do `de_onde_sei` do mapa de canais.

---

## 5. A régua, e por que ela não compara o CSV com ele mesmo

Uma régua que confere o CSV contra o CSV não mede nada. É a família de defeito
que esta casa mais pagou, e uma frente deste mesmo dia pegou uma régua
comparando o produto **contra ele mesmo** — ela concordava com a semente errada
dos dois lados.

Então **o veredito de cada linha virou uma afirmação sobre o código**,
verificável sem o CSV. Cada linha carrega um `sinal` (um símbolo literal) e o
que se espera dele:

| veredito | `sinal_espera` | o que a régua lê no fonte |
| --- | --- | --- |
| `IGUAL` · `DIFERENTE` · `SO_NO_HTML` · `NAO_DA_PARA_SABER` | `PRESENTE` | o símbolo **tem** de estar no arquivo do lado HTML que a linha cita |
| `FALTA_NO_HTML` | `AUSENTE` | o símbolo da GTK **não pode** aparecer no lado HTML |

**A segunda metade é a que envelhece o número de propósito.** Quando alguém
fechar uma dívida — o lado HTML passar a chamar a função da GTK que a carregava,
ou a página ganhar o endereço que lhe faltava (`data-campo="fragil"`) —, o
símbolo aparece, o portão **reprova**, e o CSV tem de ser reescrito. Sem isso a
paridade publicada vira propaganda no dia seguinte à primeira cura.

**E a régua fez o que prometia.** Entre 03/09 e 04/09 a paridade andou de 14%
para 27% sem que ninguém a "atualizasse" à mão: cada cura fez o portão reprovar,
e a linha do CSV foi reescrita com o endereço novo lido no código.

### As doze regras

| regra | reprova quando |
| --- | --- |
| `integridade` | cabeçalho, veredito fora do domínio, aba desconhecida, `(aba, feature)` repetido |
| `endereco-morto` | `caminho:linha` cujo arquivo sumiu, ou cuja linha passa do fim |
| `lado-trocado` | endereço da GTK na coluna do HTML, ou o contrário — é o que impede o portão de virar a régua que se compara consigo mesma |
| `sem-endereco` | linha sem endereço nenhum, ou que afirma `PRESENTE` e não diz **onde** |
| `sinal-sumiu` | `PRESENTE` cujo símbolo saiu do escopo — uma feature `IGUAL` pode ter sido removida sem ninguém ver |
| `divida-fechada` | `AUSENTE` cujo símbolo **apareceu** no lado HTML. O caso bom |
| `sinal-morto` | `AUSENTE` cujo símbolo não existe no lado GTK **e** não tem forma de endereço de tela: ninguém vai escrevê-lo, então a linha nunca morderia |
| `numero-publicado` | a tabela da §2 diverge da contagem do CSV |
| `aposentado-vivo` | arquivo declarado em `APOSENTADOS` que voltou à árvore |
| `ponte-morta` | uma ponta de `PONTES` sumiu: o par `(aba, feature)` saiu do CSV, ou o `id` saiu do mapa de canais |
| `transporte-nao-declarado` | a linha AFIRMA paridade e o mapa restringe um transporte do canal embaixo dela — e ela não diz `cabo` nem `rádio` em lugar nenhum |
| `ponte-encolheu` | `PONTES` tem menos entradas que `PISO_DAS_PONTES` |

A `sinal-morto` é a régua se auditando: ela pegou **quatro linhas minhas** na
primeira execução, antes de eu ensinar o portão que `data-campo="fragil"` é um
endereço legítimo *que ainda vai nascer*.

### O que ela NÃO mede, dito na cara

Nada aqui abre janela, clica ou toca aparelho. **Um botão que existe nos dois
lados e está quebrado nos dois passa por este portão sorrindo.** Quem morde isso
é a ponte JS do piloto (`--prova-gesto`), que roda com o daemon vivo. Este
portão responde uma pergunta só: *o CSV continua descrevendo o código de hoje?*

### O que se corrigiu ao escrever a régua

Três endereços da medição original apontavam para o arquivo **vizinho** ou para
uma linha que a árvore já tinha movido, e os três foram lidos e corrigidos:

| era | é | o que está lá |
| --- | --- | --- |
| `app/actions/relancar.py:2794` | `app/actions/home_actions.py:2794` | `render_pendente(self)` — o arquivo velho tem 301 linhas |
| `interface/pacotes/a03_gatilhos.py:864` | `.../a03_gatilhos.py:1084` | `def pacote(ctx: Contexto)` |
| `interface/pacotes/a08_conexoes.py:1966` | `.../a08_conexoes.py:2333` | a frase da recusa do cabo |

É o que a regra `endereco-morto` existe para pegar antes da próxima pessoa.

---

## 6. Como usar

```bash
scripts/check_paridade_gtk_html.py              # o portão (rc=1 no primeiro achado)
scripts/check_paridade_gtk_html.py --tabela     # o número por aba
scripts/check_paridade_gtk_html.py --cruzamento # a ponte com o mapa de canais
```

Ele entra na camada **rápida** do `scripts/portoes.sh` (medido: 0,4 s) e no
`ci.yml`, porque a lista de portões desta casa é uma só.

**Quando o veredito de uma linha mudar** — e ele vai mudar, é para isso que o
trabalho existe —, o conserto é na **linha do CSV**, com o endereço novo lido no
código: veredito, `sinal`, `sinal_espera`, `sinal_escopo` e os dois `onde`. E
regerar a tabela da §2. Nunca afrouxando a regra no script.

---

## 6.1 O CRUZAMENTO COM O MAPA DE CANAIS — 06/09/2026

**O buraco que isto fecha:** `docs/data/paridade-gtk-html.csv` e
`docs/data/mapa-controles.csv` eram lidos juntos por DOIS arquivos do produto
(`interface/aba02.py` e `interface/mesa_viva.py`) e por **portão nenhum** — o
achado §5.4 da A-TELA-NOVA-ENTRA-NA-RÉGUA-DO-MAPA-01. Uma linha podia dizer
`IGUAL` — *a tela nova faz o que a janela fazia* — enquanto o mapa dizia que o
CANAL embaixo dela só aciona num transporte. Os dois números concordavam consigo
mesmos, e ninguém perguntava ao outro.

**Ele INFORMA, nunca VETA.** `D-0609-O-MAPA-INFORMA-NUNCA-VETA`, palavra dela em
06/09/2026: *"Esse mapa é funcional e real. tá desatualizado no sentido de não
ter sido medido. foi e tudo funciona."* <!-- noqa-acento: citação literal dela -->
Uma célula `nao-medido` vira **AVISO impresso**, e o `rc` continua ZERO. Quem a
remede é a bancada, com o relatório de quem passou por ela
(SPECS-A-PROCEDENCIA-01).

**A ponte é declarada, e o veredito NÃO.** As duas planilhas não têm uma palavra
em comum: o `sinal` da paridade é um símbolo do código (`rumble_ff`,
`data-volume="microfone"`) e a `chave` do mapa é o endereço de um canal do
aparelho (`audio.microfone.mudo`). Medido em 06/09/2026: **zero** dos 396 `sinal`
contém uma das 110 `chave`, em qualquer forma. Então alguém declara que a fatia
de tela X anda sobre o canal Y — e o que o portão NÃO deixa digitar é o FATO: ele
lê `aciona` e a causa do mapa a cada execução, e nunca guarda *"esta feature é só
no cabo"*. Três travas impedem a lista de apodrecer: as duas pontas mortas
reprovam (`ponte-morta`) e a lista só pode CRESCER (`ponte-encolheu`, comparação
por `>=`, a forma provada do `PISO_DA_REGUA`).

**As 26 pontes de hoje**, e o que elas encontraram:

| o que o mapa diz | pontes | o que acontece |
| --- | --- | --- |
| sustenta os dois transportes | 16 | nada a declarar; a régua se cala |
| restringe um lado, com causa | 7 | a linha tem de dizer `cabo` ou `rádio` |
| `nao-medido` nos dois lados | 3 | **AVISO**, nunca `rc=1` |

**O achado que sai daqui, e é para a bancada:** as três linhas do BRILHO da barra
(`04-iluminacao`) afirmam paridade sobre `luz.lightbar.brilho@dualsense`, e a
célula diz `aciona=não` nos **dois** transportes com causa `nao-medido`. A tela
tem um trilho de 0 a 100 que grava e reenvia a cor; o mapa nunca foi marcado.
Não é veto — é a primeira linha da fila de remedição.

---

## 7. O que este número diz sobre a fila

Três leituras que a tabela sustenta, e nenhuma delas é opinião. **Quem lê os
extremos lê a tabela da §2, não este parágrafo** — a lista abaixo diz que TIPO
de atraso cada aba tem, que é o que não muda a cada cura.

1. **Nem toda aba atrasada está atrasada pelo mesmo motivo, e é isso que decide
   a ordem.** A `02-controles` é **leitura viva pura** — o dado existe e a
   página não tem onde pô-lo. A `06-navegacao` **mudou de campo**
   (`Profile.key_bindings` → `Profile.button_actions`), e o câmbio apaga em
   silêncio o que ela editou na janela antiga; é dívida de MOTOR, e nenhuma
   pintura a fecha. E a `01-jogar` é quase toda **ponte entre dois arquivos que
   já existem** — 18 das 30 linhas abertas dela caíram no balde `LIGAR` da
   triagem de 04/09, a melhor razão entre trabalho e ganho do inventário.
   <!-- O RANKING SAIU DAQUI EM 04/09/2026, e ele estava certo em 03/09: a
        `03-gatilhos` era a mais adiantada com 32% e a `02`, a `06` e a `09` as
        mais atrasadas com 8%. Hoje a `03` continua na frente e as três de trás
        não são mais as mesmas — a `09` saiu do fundo. Um ranking é uma segunda
        cópia da tabela, e foi a segunda cópia que envelheceu o `14%` desta
        página; ele não volta. -->
2. **Botão morto é pior que botão ausente.** Ele tem rótulo e tooltip, e é
   silencioso: custa pouco e engana muito. **A contagem de 03/09 — sete na 09,
   um na 10 ("Recarregar") — não vale mais**, e as duas curas têm régua:
   `tests/unit/test_a_09_sistema_fecha_a_paridade.py` mede o ATO gesto a gesto
   na 09, e `tests/unit/test_aba10_os_cinco_gestos_calados_passaram_a_falar.py`
   fecha os cinco últimos da 10. O princípio fica; o número tem dono, e o dono
   é o CSV.
3. **UM FATO QUE CAIU EM 04/09/2026, e ele encurtava a fila.** Esta linha dizia
   que quatro campos da 02 (`touch-ponto`, `luz-cor`, `alto-num`,
   `alto-barra`) e o `data-campo="luz"` da 04 esperavam o
   `scripts/check_o_desenho_aprovado.py --publicar` dela. **Não esperam mais** —
   os cinco estão nas páginas que o produto abre, e as duas páginas são
   byte-idênticas ao mockup:

   ```
   $ grep -c 'data-campo="alto-barra"' src/.../interface/paginas/02-controles.html   → 4
   $ grep -c 'data-campo="luz"'        src/.../interface/paginas/04-iluminacao.html  → 2
   $ .venv/bin/python scripts/check_o_desenho_aprovado.py
     o produto já tem ..... 13
     o produto está atrás . 0  (0 em trabalho)
   ```

   **Nenhuma linha desta medição espera o `--publicar` dela.** As treze páginas
   foram publicadas na madrugada de 04/09.

O que o CSV **não** decide é a ordem. Ele diz onde estão os buracos, com
endereço; qual se fecha primeiro é dela.

## Nota de verificação — 05/09/2026

A linha `01-jogar` foi de **21% para 24%** e a `TODAS` de 118 para 119 iguais,
por uma dívida que fechou: *A palavra do transporte no cartão* saiu de
`DIFERENTE` para `IGUAL`.

O que ela era: `interface/mesa_viva.py` montava a palavra curta com `"USB" if
transporte == "usb" else "BT"`, e o `else` pegava a AUSÊNCIA — um controle cujo
transporte o daemon não publicasse aparecia na aba 01 como **"BT"**, a tela
afirmando rádio sobre um campo que ninguém leu. Havia quatro respostas vivas no
produto para o mesmo campo.

O que fechou: o `mesa_viva` passou a LER `pacotes.VIA_DO_TRANSPORTE`, cujo
`.get(..., "")` já respondia certo na aba 02 — e cujo comentário AFIRMAVA (sem
ser verdade) que as duas traduções eram a mesma. Agora são. A razão continua
sendo a do dono da frase longa (`app/actions/home_actions.py:1333`): *"'?' não é
resposta — é a tela encolhendo os ombros"*.

Régua: `tests/unit/test_a_tela_nao_inventa_o_transporte.py`, com mordida.

## Nota de verificação — 06/09/2026, a remedição das 57

`PARIDADE-REMEDIR-01`. As **57** linhas `FALTA_NO_HTML` foram relidas uma a uma
contra o fonte de hoje, depois de dez sprints fecharem. O número foi de
**137 IGUAL · 139 DIFERENTE · 57 FALTA · 35 %** para
**144 · 150 · 39 · 36 %** — e o que ele mede continua sendo a bancada, não o
publicado (a caixa no topo desta página).

**DEZOITO linhas mudaram de veredito, todas com o endereço lido no código** —
sete viraram `IGUAL` e onze `DIFERENTE`. A maior parte é a aba **02-controles**,
que foi de **24 % para 32 %**: os dois deslizantes de volume (do microfone e do
alto-falante) existem na bancada **e na página publicada**, o número e a barra
do alto-falante saem da curva medida no aparelho, e o hertz do giroscópio
deixou de ser número de catálogo. As duas abas que **zeraram** os `FALTA` são a
`06-navegacao` (o botão PS voltou à tabela, reversão dela na 06-Q3) e a
`07-lancadores` (a carona do wrapper chegou ao rodapé).

**VINTE E UMA linhas ficaram `FALTA_NO_HTML` e ganharam a segunda metade `||`
datada** com o que a medição achou. O padrão delas tem nome, e é o oposto do
que a fila costuma supor: **adiamento não é remoção**. As decisões de 06/09
sobre controles externos, editor avançado de regra, "Mapear Entrada a Entrada"
e o custo da máscara antes do clique são de **prazo** — a §10 da
[24 HORAS](../process/2026-09-06-AS-VINTE-E-QUATRO-HORAS-a-ordem-que-o-orquestrador-despacha-e-as-rotas-corrigidas.md)
as põe fora das 24 horas e fecha dizendo *"o resto dos FALTA fica na régua, que
é onde fila mora"*. Promovê-las a `DIFERENTE` esvaziaria a fila sobre trabalho
que ninguém fez.

**A régua de `DIFERENTE` que esta leva firmou:** ela exige que o lado HTML
entregue a MESMA RESPOSTA por outro caminho, com endereço. Se a resposta não
chega à tela, é `FALTA_NO_HTML` — e é por isso que a *linha da verdade* (56) e
o *"Já movi — reexaminar"* (269) continuam `FALTA` mesmo sendo escolha dela: o
que elas não são é **dívida a pagar**, e isso o `porque` diz.

## Nota de verificação — 11/09/2026, a linha 384 e o fato que ela derrubou

`CADEADO-E-O-FATO-01`. A linha **`10-perfis` · "A seção «Modo» do perfil"** saiu
de `FALTA_NO_HTML` e voltou a **`DIFERENTE`**, e a tabela acima foi **recontada
do CSV** — `10-perfis` vai de `19 DIFER · 8 FALTA` para `20 · 7`, e a linha
`TODAS` de `159 · 31` para `160 · 30`. A paridade (`IGUAL / total`) não se mexe:
nenhuma linha virou `IGUAL`.

**A razão não é uma cura de código — é um fato errado sendo substituído.** A
leva de 11/09 tirou o quadro «Modo» do editor de Perfis por ordem dela e
declarou, em três lugares, uma **«perda de capacidade»**. Quem derrubou a
declaração foi **ELA**, no mesmo dia:

> *"a informação que eu selecionar no modo ou mascara na aba jogar ao salvar o*  <!-- noqa-acento: citação literal dela -->
> *perfil faz a mesma função que o modo tinha na aba perfil isso foi*  <!-- noqa-acento: citação literal dela -->
> *implementado desde o inicio mas voltou e não deVEria ter ocorrido"*  <!-- noqa-acento: citação literal dela -->

E o código concorda: `a01_jogar._gravar_o_modo_do_chip` → `_gravar_o_modo` →
`interface/pacotes/perfil.gravar_o_modo_no_ativo` grava a seção `mode` do perfil
ativo **no clique**, sem passar pelo «Salvar Perfil». O quadro em Perfis era
**duplicata** disso; a retirada desfez a cópia, não a capacidade.

**A régua de `DIFERENTE` firmada em 06/09 é o que sustenta a promoção**: o lado
HTML entrega a MESMA RESPOSTA por outro caminho, com endereço. O que sobra de
diferença é **LUGAR** (fileira de chips na Jogar, não quadro no editor de
Perfis) e **ESCOPO** (só o perfil ATIVO; nunca `"none"`), e os dois são
consequência de decisão dela — está escrito no `porque` da linha e no docstring
de `gravar_o_modo_no_ativo`.

**O SINAL TROCOU JUNTO, e não por conveniência:** `_mode_section_from_editor` é
símbolo da GTK e só serve para cobrar AUSÊNCIA (`usa`, que não conta prosa). Uma
linha que AFIRMA paridade tem de vigiar o que FAZ do lado HTML — passou a ser
`gravar_o_modo_no_ativo`, em `interface/pacotes/perfil.py`.

**A MORDIDA:** devolvido o veredito `FALTA_NO_HTML` na linha 384 e reposto o
sinal velho, o portão reprova em `numero-publicado` nomeando `10-perfis` e
`TODAS` — que é a prova de que esta tabela não envelhece calada.

## Nota de verificação — 13/09/2026, o «Ver os plugins» sai da aba Sistema

`SISTEMA-BOTOES-01`. O botão saiu da tela, e a linha dele no CSV (sinal
`D-OS-PLUGINS-APARECEM-ONDE-AGEM`) foi de `SO_NO_HTML` para **`IGUAL`**: nenhum
dos dois lados lista plugins, e a GTK nunca listou — o que era «só no HTML» deixou
de existir. A tabela acima foi **recontada do CSV**: `09-sistema` vai de
`11 IGUAL · 7 SO_HTML · 29%` para `12 · 6 · 32%`, e `TODAS` de `143 · 59` para
`144 · 58`.

**A razão é decisão dela, e está escrita:** `docs/data/decisoes-dela.csv`, linha
`D-OS-PLUGINS-APARECEM-ONDE-AGEM` (26/08/2026) — *os plugins não ganham seção
própria; a infraestrutura se mostra pelo efeito, não pelo nome*. O `porque` da
linha guarda o veredito de antes, com a data.

## Nota de verificação — 13/09/2026, a guarda sem endereço (linha 57)

`RESTOS-DA-ONDA-TRES-01`. A linha **`02-controles` · Guarda "sem endereço"** saiu
de `FALTA_NO_HTML` e foi para **`DIFERENTE`**, e a tabela acima foi **recontada
do CSV**: `02-controles` vai de `24 DIFER · 6 FALTA` para `25 · 5`, e `TODAS` de
`159 · 30` para `160 · 29`. A paridade (`IGUAL / total`) não se mexe.

**A régua de `DIFERENTE` firmada em 06/09 é o que sustenta a troca.** Sem
endereço, o lado HTML dá a mesma resposta por outro caminho, com endereço: as duas
molduras de som recebem `data-apagado="sem-alvo"` (em `a02_controles.py`, o campo
`alto-apagado` e a `microfone_apagado`), a folha da 02 esmaece o que manda som, o
gesto recusa pelo endereço, e a razão fica no `?` da linha de volume. O que sobra
de diferença é o **caminho** (peça esmaecida e gesto recusado, e não peça
insensível) e o **aviso**, que a tela não tem: a §D da RESTOS-DA-ONDA-DOIS-01 diz
«sem frase nova».

**Não é cura desta sprint: é um fato velho sendo substituído.** A metade visível
nasceu em 06/09 por um endereço que casava `[title]` e nunca acendeu no WebKit; a
RESTOS-DA-ONDA-DOIS-01 curou e publicou a 02 em 13/09, e a linha continuou
dizendo `FALTA_NO_HTML` e citando o endereço morto. **O sinal trocou junto:**
`_pecas_que_escrevem_som` é símbolo da GTK e só cobra ausência; a linha agora
vigia a regra que apaga o alto-falante na folha de `interface/aba02.py`,
`.moldura[data-bloco="alto-falante"][data-apagado="sem-alvo"]`. O
`data-apagado="sem-alvo"` solto não serve: o microfone já o tinha desde a
MIC-SEM-FONTE-01, e ele passava no `aba02.py` de `b791d234`, em que a guarda do
alto-falante nunca acendeu.

**A MORDIDA:** com a tabela devolvida à contagem velha, o portão reprova em
`numero-publicado` nomeando `02-controles` e `TODAS`.

## Nota de verificação — 13/09/2026, a escolha de máscara deixa de ser do chip do Modo

`MODO-DE-CONEXAO-01`. A linha **`01-jogar` · "A escolha de máscara chega ao daemon
(o jogo vê o controle como)"** caiu de `IGUAL` para **`DIFERENTE`**, e a tabela
acima foi **recontada do CSV**: `01-jogar` vai de `14 IGUAL · 22 DIFER · 33%` para
`13 · 23 · 31%`, e `TODAS` de `145 · 160 · 37%` para `144 · 161 · 36%`. **A
paridade desce um ponto, e é por decisão dela, não por defeito.**

**A razão:** a regra dela de 13/09 (`D-1309-O-MODO-E-A-BASE-E-A-MASCARA-VEM-POR-CIMA`
em `docs/data/decisoes-dela.csv`) separa as duas camadas. Os chips «Sony
DualSense» e «Xbox» escolhem o CAMINHO (`mode.caminho`), e a máscara é do cartão
de cada controle, por `gamepad.mask.set`. A GTK continua com UM seletor de máscara
para a máquina. A resposta chega ao daemon dos dois lados por caminhos diferentes,
e é isso que `DIFERENTE` quer dizer nesta tabela.

**Fato substituído na mesma linha:** o `porque` dizia que a máscara «sai de
`painel.CHIPS_DA_ESCADA`». Desde a cura, `CHIPS_DA_ESCADA` nomeia caminhos. A linha
vizinha, «O modo/máscara escolhidos entram no perfil», continua `DIFERENTE`, e o
`html_faz` dela deixou de dizer que a máscara é zerada fora do modo jogo.

**A MORDIDA:** com a tabela devolvida à contagem velha, o portão reprova em
`numero-publicado` nomeando `01-jogar` e `TODAS`.

## Nota de verificação — 13/09/2026, a marca da degradação sai das abas 01 e 02

`A-MARCA-DA-DEGRADACAO-01`. As linhas **`01-jogar` · "Banner de degradação do vpad"**
(`IGUAL`) e **`02-controles` · "Badge de degradação do gamepad virtual"**
(`DIFERENTE`) viraram **`FALTA_NO_HTML`**, e a tabela acima foi **recontada do
CSV**: `01-jogar` vai de `13 IGUAL · 1 FALTA · 31%` para `12 · 2 · 29%`,
`02-controles` de `25 DIFER · 5 FALTA` para `24 · 6`, e `TODAS` de
`144 · 161 · 29 · 36%` para `143 · 160 · 31 · 36%`.

**A razão:** a terceira lista dela manda as frases de aviso pararem de aparecer
nas abas ([o índice](../process/sprints/arquivados/2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md)), e a
marca era uma: o asterisco com o motivo da queda no `title`. No WebKit ele nunca
acendia, porque a camada de dicas tira o `title` e `.degradou[title]` não casava.
A decisão de 04/09 que o desenhou, `D-02C-DEGRADACAO-VPAD`, ficou `caduca` em
`docs/data/decisoes-dela.csv`. A GTK continua mostrando a tarja. O sinal das duas
linhas passou a ser o símbolo da GTK, `AUSENTE` do lado HTML, e as
autoconferências de `aba01.py` e `aba02.py` recusam a marca de volta.

**A MORDIDA:** com a tabela devolvida à contagem velha, o portão reprova em
`numero-publicado` nomeando `01-jogar`, `02-controles` e `TODAS`.

## Nota de verificação — 21/09/2026, o «Este jogo não funciona» sai da aba 07

`OS-LANCADORES-IGUAIS-E-A-LISTA-DE-EXCLUSAO-01`. A linha **`07-lancadores` ·
"Este jogo não funciona"** foi de `IGUAL` para **`DIFERENTE`**, e a tabela acima
foi **recontada do CSV**: `07-lancadores` vai de `15 IGUAL · 5 DIFER · 50%` para
`14 · 6 · 47%`, e `TODAS` de `143 · 160` para `142 · 161`.

**A razão:** o desenho da lista de exclusão, aprovado por ela, pôs o «Adicionar
à lista de exclusão» no lugar do botão nos oito cartões — e a exclusão é o
contrário da marca. A marca por jogo continua na interface nova pelo chip
«Steam Input» da aba Jogar (`a01_jogar.modo_steam`), com o mesmo dono. As duas
linhas que a citavam (esta e a `09-sistema` · "Steam — Este jogo não
funciona") passaram a ter o escopo do sinal em `a01_jogar.py`.

**A MORDIDA:** com a tabela devolvida à contagem velha, o portão reprova em
`numero-publicado` nomeando `07-lancadores` e `TODAS`.

## Nota de verificação — 24/09/2026, o recibo do «Reconectar» cala o sucesso

`A-FRASE-DO-RECONECTAR-SAI-01`. A linha **`01-jogar` · "O recibo do 'Reconectar'
— quantos jogadores voltaram, se a numeração compactou"** foi de `IGUAL` para
**`DIFERENTE`**, e a tabela acima foi **recontada do CSV**: `01-jogar` vai de
`12 IGUAL · 23 DIFER · 29%` para `11 · 24 · 26%`, e `TODAS` de `131 · 172` para
`130 · 173`. **A paridade desce por decisão dela, não por defeito.**

**A razão:** `D-2409-O-RECONECTAR-NAO-DIZ-NADA` — *«Nada: o número novo aparece
no próprio cartão»*. A GTK diz no toast quantos jogadores voltaram e o que a
numeração fez; o HTML diz só as duas falhas do passo 2 (`painel._NAO_CONFERIU`,
`painel._NAO_COMPACTOU`). O `IGUAL` já estava velho antes desta cura: a JOGAR-02
(09/09) calou o «já estava compacta» e a recusa por jogo aberto, a
TELA-CALADA-01 (13/09) mandou a frase para o diário da janela, e a linha
continuou dizendo que os desfechos da janela chegam à tela.

**Fato substituído na mesma linha:** o `html_faz` dizia que o desfecho era o
recado verde de 6 s no cartão; agora diz o que o gesto faz hoje. Os quatro
endereços foram medidos de novo — os dois do HTML abriam em docstring de outra
função.

**A MORDIDA:** com a tabela devolvida à contagem velha, o portão reprova em
`numero-publicado` nomeando `01-jogar` e `TODAS`.

## Nota de verificação — 25/09/2026, a contagem do exame sai da aba Sistema

`A-09-SISTEMA-EM-TRES-SECOES-01`, os ajustes dela das 22h13: *«Remove esse 8
linhas deixa o espaço vazio»*. A linha da contagem no CSV foi de `SO_NO_HTML`
para **`IGUAL`**, pelo mesmo caminho do «Ver os plugins» (13/09): nenhum dos
dois lados conta as linhas do exame, e o sinal é a decisão escrita no pacote
(`D-A-CONTAGEM-DO-EXAME-SAIU`). A tabela foi recontada do CSV: `09-sistema`
vai de `12 IGUAL · 4 SO_HTML · 32%` para `13 · 3 · 34%`, e `TODAS` de
`130 · 55` para `131 · 54`.

## Nota de verificação — 26/09/2026, o escopo do microfone sai da aba Conexões

`A-08-O-CHECKUP-ABSORVE-A-GESTAO-01`: o «Microfone e botões» saiu da linha do
controle a pedido dela (repetia a aba Jogar/Controles), e com ele o escopo do
botão físico do microfone. A linha do CSV foi de `SO_NO_HTML` para **`IGUAL`**,
pelo mesmo caminho da contagem do exame da 09: nenhum dos dois lados oferece o
escopo nesta aba, e o sinal é a decisão escrita no pacote
(`D-O-ESCOPO-DO-MIC-SAIU-DA-08`). A tabela foi recontada do CSV: `08-conexoes`
vai de `16 IGUAL · 2 SO_HTML · 33%` para `17 · 1 · 35%`, e `TODAS` de
`131 · 54` para `132 · 53`.

## Nota de verificação — 26/09/2026, a Gestão de Controles enxuga

`D-2609-A-GESTAO-ENXUTA`. A linha **`08-conexoes` · "O carimbo 'Examinado há …'"**
foi de `DIFERENTE` para **`FALTA_NO_HTML`**: o canto da seção saiu, a pedido
dela. A bateria foi para o nome do cartão e a contagem ficou no topo da janela;
as duas seguem `DIFERENTE`, com o endereço novo. A tabela acima foi recontada do
CSV: `08-conexoes` vai de `27 DIFER · 5 FALTA` para `26 · 6`, e `TODAS` de
`173 · 35` para `172 · 36`.
