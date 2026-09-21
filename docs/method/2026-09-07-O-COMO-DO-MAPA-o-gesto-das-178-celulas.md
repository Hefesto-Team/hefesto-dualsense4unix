---
sprint: O-COMO-DO-MAPA
estado: feita
posse:
  O-COMO-DO-MAPA:
    - docs/process/sprints/2026-09-07-O-COMO-DO-MAPA-o-gesto-das-178-celulas.md
bancada: true
---

# O COMO do mapa — o gesto das 178 células

**Ordem dela, 07/09/2026, depois de ver as 21 prontas:**

> *"depois de melhorar os 21. quero que aí sim vc use o novo modelo pra
> remodelar os demais testes via agentes."*

Isto é o modelo das 21 aplicado às 178 células do mapa de canais — as que
sobram depois da bancada. Mesma forma, mesmos sete campos, mesma regra: o que
está aqui a página LÊ, e nada dela é digitado lá.

## O que muda das 21 para estas

**A variação por controle sai do TRANSPORTE.** As 21 trazem, na coluna do
roteiro, o que cada um dos quatro faz — escrito por ela. As 178 não têm essa
coluna, e a variação vem de onde ela sempre veio: *"por isso dois controles
dois bt e dois no cabo. Pra batermos de vez o controle que temos do hardware"*.
Então numa célula do cabo quem reage é P1 e P2, e P3 e P4 são as TESTEMUNHAS —
e testemunha não é enfeite: se a coisa acontecer nelas também, o comando pegou
o transporte inteiro em vez do controle escolhido.

**E o degrau da prova limita o que se pede.** A coluna `ate_onde_foi` do mapa
diz até onde cada célula chegou: MONTOU · SAIU NO FIO · O APARELHO OBEDECEU · O
JOGO RECEBEU · O JOGO REAGIU. Pedir que ela veja o jogo reagir numa célula que
parou em MONTOU produz um vermelho que não é defeito do produto — é a régua
cobrando um degrau que ninguém subiu.

## Como isto foi escrito

Vinte e oito agentes, um por família de canal: cada um aprendeu a aba inteira
antes de escrever, e conferiu no produto se o campo citado existe com aquele
rótulo. Quatorze escreveram, quatorze conferiram.

---

---

# ?

---

## mapa-audio.saida_dedicada.payload_do_degrau-cabo — Prova que, no cabo, o Hefesto não usa nem promete o caminho

**O que isto prova.** Prova que, no cabo, o Hefesto não usa nem promete o caminho de som do rádio — no cabo o som do controle é uma saída comum do computador, e é isso que a tela mostra.

**Onde olhar.** Na aba Controles, no cartão do P1 e no do P2, bloco Alto-falante: embaixo dos dois botões de rota NÃO pode haver a frase do rádio, e o rótulo do bloco traz o sufixo "· acordado" ou "· dormindo", que só existe quando há saída de som daquele controle. Do outro lado, no cartão do P3, a frase do rádio tem de estar lá e o sufixo não — é esse contraste que faz a prova. Onde se leria o CONTEÚDO do caminho de rádio não existe na tela, e nesta linha nem existe pergunta do lado do cabo: a fonte não diz.

**Os passos.**

1. Confira na fita do topo que P1 e P2 dizem cabo e que P3 e P4 dizem rádio.
2. Abra o Hefesto e clique na aba Controles.
3. Clique na linha do P1 para abrir o cartão dele.
4. Leia a linha embaixo dos dois botões de rota e confirme que ela está VAZIA.
5. Leia o rótulo do bloco Alto-falante e confirme que ele traz "· acordado" ou "· dormindo".
6. Arraste o volume do alto-falante do P1 até 80.
7. Clique em "Todo o som do PC" no bloco do P1 e toque uma música.
8. Encoste o ouvido no P1: o som tem de sair.
9. Clique em "Sons do jogo" no bloco do P1 para devolver o som às caixas.
10. Clique na linha do P2 e repita do passo 4 ao 9 nele.
11. Clique na linha do P3 e leia a linha embaixo dos botões de rota: ali a frase do rádio TEM de aparecer.
12. Confira que o rótulo do bloco do P3 não traz "· acordado" nem "· dormindo".
13. Encoste o ouvido no P3 e confirme o silêncio.
14. Clique na linha do P4 e repita os passos 11 a 13 nele.
15. Anote as quatro respostas lado a lado.

**Passa quando.** No P1 e no P2 a linha de ressalva está vazia, o rótulo traz o sufixo e o som sai. No P3 e no P4 a frase do rádio está lá, o sufixo não está e nenhum som sai. Os dois lados descrevem caminhos diferentes, e nenhum deles está emprestando as palavras do outro.

**Por controle.**

* **P1** — No cabo, e é aqui que a prova acontece: nada de frase do rádio no cartão dele, sufixo presente no rótulo, e som saindo. Se aparecer uma ressalva de rádio num cartão do cabo, é esse o defeito que este teste caça.
* **P2** — No cabo, e faz a mesma conferência. É a segunda prova do cabo: se um dos dois trouxer a frase do rádio, anote qual.
* **P3** — No rádio, e é CONTRASTE, não alvo. Você não mexe em nada nele além de ler: a frase tem de estar lá, o sufixo não, e o silêncio confirmado com o ouvido.
* **P4** — No rádio, e é o segundo contraste. Mesma leitura do P3. Os quatro juntos é que fazem a resposta: dois com som e sem frase, dois com frase e sem som.

**A armadilha.** Do lado do cabo esta pergunta NÃO EXISTE, e isso é o ponto inteiro: no cabo o som do controle é uma saída de som comum do computador e não passa pelo canal do rádio de jeito nenhum. Então não há o que clicar aqui além de conferir que o produto não DIZ nada sobre rádio nos cartões do cabo. Segunda, e é regra desta casa com nome: ninguém pode concluir, de um canal responder, que ele FAZ o que a gente esperava dele. Pelo rádio o produto de fato manda por esse canal, e o que viaja dentro dele NUNCA foi identificado — por isso nada do que você vir no lado do cabo prova ou desmente coisa alguma sobre o conteúdo do rádio. Terceira: a prova desta linha está como "não medido" do lado do cabo e vai continuar assim; o que você entrega aqui é o contraste entre os quatro cartões, e esse contraste é a entrega inteira.

---

# audio

---

## mapa-audio.alto_falante-cabo — Alto-falante do controle — som saindo · cabo

*Célula:* `audio.alto_falante @ cabo`

**O que isto prova.** Prova que o som do jogo sai mesmo pelo alto-falante dos dois controles que estão no cabo, e que os dois do rádio ficam mudos.

**Onde olhar.** Na aba Controles do Hefesto. Clique na linha de um controle e o cartão dele abre (o que estava aberto fecha sozinho). Dentro do cartão, o bloco chamado Alto-falante: na linha do rótulo pode vir um sufixo, "· acordado" ou "· dormindo"; abaixo vem a barrinha de ondas, o deslizante de volume com o número ao lado e o botão ♪; depois os dois botões de rota, "Sons do jogo" e "Todo o som do PC"; e, por último, uma linha de ressalva que fica vazia quando não há nada a dizer. Mas quem responde este teste é o seu OUVIDO, encostado no alto-falante do próprio controle: são nove furinhos em duas fileiras, na frente do DualSense, logo abaixo e entre os dois analógicos.

**Os passos.**

1. Clique na aba Controles.
2. Confira na fita do topo que P1 e P2 dizem cabo e que P3 e P4 dizem rádio.
3. Abra um jogo e deixe-o produzindo som.
4. Clique na linha do P1 para abrir o cartão dele.
5. Leia o rótulo do bloco Alto-falante e anote se ele traz "· acordado", "· dormindo" ou nada.
6. Arraste o deslizante de volume do bloco Alto-falante do P1 até o fim da direita.
7. Confira que o número ao lado do deslizante diz 100.
8. Encoste o ouvido no alto-falante do P1 e escute o som curto de confirmação.
9. Clique em "Sons do jogo" no bloco do P1.
10. Faça o jogo produzir um som bem marcado, como um tiro ou uma música de menu.
11. Encoste o ouvido no P1 e escute se o som do jogo sai por ali.
12. Encoste o ouvido no P3 e depois no P4 e confirme que os dois estão mudos.
13. Clique em "Todo o som do PC" no bloco do P1.
14. Toque um vídeo qualquer fora do jogo.
15. Encoste o ouvido no P1 e escute o som do vídeo saindo por ali.
16. Leia a linha de ressalva embaixo dos dois botões e anote se apareceu alguma frase.
17. Clique em "Sons do jogo" no bloco do P1 para devolver o som às caixas — não pule este passo.
18. Clique na linha do P2 e repita nele tudo o que você fez no P1, DA LEITURA DO RÓTULO do bloco Alto-falante até o clique que devolve o som às caixas.
19. Encoste o ouvido no P3 e no P4 uma última vez e confirme o silêncio.

**Passa quando.** Sai som pelo alto-falante do P1 e pelo do P2, os dois que estão no cabo: primeiro o som curto de confirmação depois do arrasto do volume, depois o som do jogo com "Sons do jogo" aceso, e depois o som do computador inteiro com "Todo o som do PC" aceso. O rótulo do bloco foi lido e anotado nos DOIS cartões do cabo, o do P1 e o do P2. O P3 e o P4 ficam mudos do começo ao fim. E a linha de ressalva dos dois cartões do cabo continua vazia — nenhuma frase aparece ali.

**Por controle.**

* **P1** — No cabo, e é o primeiro a tocar. Leia o rótulo do bloco e anote o sufixo, arraste o volume até 100, ouça o som de confirmação, ponha "Sons do jogo" e ouça o jogo, ponha "Todo o som do PC" e ouça o vídeo. No fim, devolva o som às caixas clicando em "Sons do jogo".
* **P2** — No cabo, e faz exatamente o mesmo que o P1, um de cada vez, começando pela leitura do rótulo do bloco dele — o sufixo "· acordado" ou "· dormindo" do P2 é dado próprio e tem de ser anotado, porque é ele que explica um começo de som comido. Ele é a segunda prova do cabo: se só um dos dois tocar, o problema é daquele controle e não do caminho de som — e vale anotar qual dos dois falhou.
* **P3** — No rádio, e é TESTEMUNHA: você não toca nele. Encoste o ouvido nele durante o teste do P1 e de novo no fim. Se ele tocar junto, o comando pegou o transporte inteiro em vez do controle escolhido, e isso é achado.
* **P4** — No rádio, e é a segunda testemunha. Mesmo gesto do P3: ouvido encostado, nenhum toque. Se o P3 ficou mudo e o P4 tocou, não é o rádio — é alguma coisa escrevendo no controle errado.

**A armadilha.** A prova desta linha já chegou até "o aparelho obedeceu": o alto-falante soou com a orelha dela em 02/08/2026, mas por "Todo o som do PC". A rota "Sons do jogo" NUNCA foi exercida — este teste é a primeira vez, e por isso o clique em "Sons do jogo" e a escuta logo depois dele são o coração dele. E há um achado dela ainda em aberto: pela janela do Hefesto o som curto de confirmação NÃO sai hoje nem no cabo, tendo saído antes. Se ele não vier depois do arrasto do volume, isso é a regressão conhecida da janela, não erro seu: anote e siga para o som do jogo, que é o degrau que este teste sobe. Duas outras coisas: "Todo o som do PC" tira o som das caixas e o joga no controle — esquecer de clicar em "Sons do jogo" depois deixa a máquina muda e parece defeito sem ser. E se o rótulo do bloco disser "· dormindo", ou se aparecer um selo "Canal dormindo", o começo do som é comido pelo canal e não pelo alto-falante — anote isso ao lado do resultado, e é por isso que a leitura do rótulo é o PRIMEIRO gesto da volta em cada um dos dois controles do cabo, e não só no P1. Este teste passa dos oito atos — são quinze —, e a razão é o ouvido: cada escuta é um gesto próprio, num controle próprio e numa rota de som própria, e juntar duas escutas num passo só faria você julgar duas rotas com uma lembrança só.

---

## mapa-audio.alto_falante.preamp-cabo — Alto-falante — pré-amplificador · cabo

*Célula:* `audio.alto_falante.preamp @ cabo`

**O que isto prova.** Prova que o volume do alto-falante dos dois controles do cabo muda de verdade ao longo de TODO o curso do deslizante, sem trecho morto.

**Onde olhar.** Na aba Controles, com o cartão do controle aberto: o bloco Alto-falante, o deslizante de volume e o número que fica ao lado dele. O reforço de ganho que este teste persegue NÃO tem campo na tela — a fonte não diz onde ele se lê, porque ele viaja escondido junto com o número do volume. O que se lê é o efeito, e o instrumento é o seu ouvido encostado no alto-falante do controle, os nove furinhos na frente do DualSense, entre os dois analógicos.

**Os passos.**

1. Abra o Hefesto e clique na aba Controles.
2. Clique na linha do P1 para abrir o cartão dele.
3. Clique em "Todo o som do PC" no bloco Alto-falante do P1.
4. Toque uma música que se repita, e não mexa mais no volume do sistema até o fim deste teste.
5. Arraste o deslizante do bloco Alto-falante do P1 até o número 20.
6. Confira, com o ouvido encostado no P1, o quanto se ouve, e anote.
7. Arraste o mesmo deslizante até 40, depois 60, depois 80 e depois 100, parando em cada número.
8. Confira, com o ouvido no mesmo lugar, o quanto se ouve em cada uma das quatro paradas, e anote as quatro impressões.
9. Arraste o deslizante até 0.
10. Confira que o P1 ficou em silêncio completo.
11. Clique em "Sons do jogo" no bloco do P1 para devolver o som às caixas.
12. Clique na linha do P2 e refaça nele a sequência inteira, do "Todo o som do PC" até o "Sons do jogo", com as mesmas cinco posições.
13. Confira, com o ouvido encostado no P3 e depois no P4, que os dois ficaram mudos o tempo todo.

**Passa quando.** Em cada uma das cinco posições — 20, 40, 60, 80 e 100 — o P1 e o P2 soam AUDIVELMENTE diferente da posição anterior. Não existe um trecho do deslizante em que arrastar não muda nada, nem um trecho em que já está no máximo e continuar arrastando não adianta. Em 0 é silêncio completo. E o P3 e o P4 ficam mudos do começo ao fim.

**Por controle.**

* **P1** — No cabo, e é o primeiro. Faça as cinco posições nele, com o ouvido encostado e a mesma música tocando. Anote as cinco impressões antes de passar ao P2.
* **P2** — No cabo, e faz as mesmas cinco posições. Ele é a segunda prova: se o curso for útil num e morto no outro, o defeito é daquele aparelho e não da conta que o Hefesto faz.
* **P3** — No rádio, e é TESTEMUNHA. Não toque no deslizante dele. Encoste o ouvido e confirme silêncio: se ele começar a soar quando você mexe no P1, o comando pegou mais de um controle.
* **P4** — No rádio, e é a segunda testemunha. Mesmo gesto: ouvido encostado, deslizante intocado, silêncio esperado.

**A armadilha.** O reforço de ganho não se desliga pela tela: ele sai na MESMA mensagem que o número do volume, então não existe um "com e sem" para comparar. O que este teste mede é só uma coisa — se o curso é útil de ponta a ponta. E a prova desta célula parou no primeiro degrau: o produto monta e manda o reforço junto, e ninguém mediu no aparelho que ele chegou. Cuidado com um número velho que anda escrito por aí: o "mudo até 38, satura em 102" foi levantado SEM o reforço e em outra escala, a do registrador cru — ele não é o 0 a 100 do deslizante da tela, e comparar os dois é comparar duas réguas diferentes. Por fim, a música e o volume do sistema têm de ficar iguais do começo ao fim: subir o volume da máquina entre duas posições falsifica o degrau e você marca verde sobre nada.

---

## mapa-audio.alto_falante.preamp-radio — Alto-falante — pré-amplificador · rádio

*Célula:* `audio.alto_falante.preamp @ rádio`

**O que isto prova.** Prova que o Hefesto aceita o volume nos dois controles do rádio e AVISA na tela que por rádio o som ainda não sai, em vez de fingir que saiu.

**Onde olhar.** Na aba Controles, no cartão do P3 e no do P4, bloco Alto-falante. Três coisas: o deslizante de volume com o número ao lado; o rótulo do bloco, que nos controles do rádio NÃO ganha o sufixo "· acordado" nem "· dormindo"; e, embaixo dos dois botões de rota, a linha de ressalva, que nos do rádio tem de trazer a frase "Pelo rádio o Hefesto ainda não faz o som sair neste alto-falante."

**Os passos.**

1. Confira na fita do topo que P3 e P4 dizem rádio e que não há cabo plugado neles.
2. Abra o Hefesto e clique na aba Controles.
3. Clique na linha do P3 para abrir o cartão dele.
4. Leia a linha embaixo dos botões "Sons do jogo" e "Todo o som do PC" e anote a frase inteira.
5. Leia o rótulo do bloco Alto-falante e confira que ele não traz "· acordado" nem "· dormindo".
6. Anote o número que está ao lado do deslizante de volume do P3.
7. Arraste o deslizante do P3 até 20 e confira que o número acompanhou.
8. Encoste o ouvido no P3 e escute.
9. Arraste até 50, escute de novo.
10. Arraste até 100, escute de novo.
11. Clique na linha do P1 e leia o número do volume do alto-falante dele.
12. Clique na linha do P2 e leia o número do volume do alto-falante dele.
13. Clique na linha do P4 e repita do passo 4 ao 10 nele.
14. Anote as quatro respostas antes de fechar.

**Passa quando.** A frase "Pelo rádio o Hefesto ainda não faz o som sair neste alto-falante" aparece no cartão do P3 e no do P4. O número ao lado do deslizante acompanha o arrasto nos dois. Nenhum som sai do P3 nem do P4 em nenhuma das três posições — e isso é o esperado, não uma falha. E os números do P1 e do P2 continuam onde estavam, sem se mexer.

**Por controle.**

* **P1** — No cabo, e é TESTEMUNHA. Não arraste nada nele. Leia o número do volume dele antes e depois: se ele andar quando você mexe no P3, o comando pegou o transporte inteiro em vez do controle escolhido.
* **P2** — No cabo, e é a segunda testemunha. Mesma leitura do P1: número anotado antes, conferido depois. Se o P1 ficou parado e o P2 andou, o defeito não é do transporte — é de alguma coisa escrevendo no controle errado.
* **P3** — No rádio, e é ELE que você mexe primeiro. Leia a frase de ressalva, confira que o rótulo não traz sufixo, e arraste o volume até 20, 50 e 100, escutando em cada posição. Silêncio é a resposta certa aqui.
* **P4** — No rádio, e faz exatamente o mesmo que o P3. Ele é a segunda prova do rádio: a frase de ressalva tem de aparecer nele também, não só num dos dois.

**A armadilha.** Silêncio no rádio é a resposta CERTA desta linha, e o próprio cartão diz por quê — a dívida é NOSSA, não do aparelho: o alto-falante existe e ela já o ouviu pelo cabo. O que reprova aqui é outra coisa: a frase de ressalva NÃO aparecer num controle do rádio (aí o produto está calado sobre um som que não entrega), o número não acompanhar o arrasto, ou o número de um controle do cabo andar junto. A prova desta célula parou no primeiro degrau nos dois transportes: o produto monta e manda o reforço de ganho, e ninguém mediu no aparelho que ele chegou — então não escreva "funcionou" nem "não funcionou", escreva o que a tela fez. E o rótulo sem o "· acordado" nos do rádio não é leitura faltando: é o produto dizendo honestamente que não sabe, porque no rádio o controle não publica saída de som nenhuma.

---

## mapa-audio.alto_falante.rota-cabo — Alto-falante — rota de saída · cabo

*Célula:* `audio.alto_falante.rota @ cabo`

**O que isto prova.** Prova que trocar para onde o som vai, nos dois controles do cabo, leva o som para o lugar certo e não mata o microfone do mesmo controle.

**Onde olhar.** Na aba Controles, com o cartão aberto, dois blocos do mesmo cartão. No bloco Alto-falante: os dois botões de rota, "Sons do jogo" e "Todo o som do PC" — um deles fica aceso —, e a linha de ressalva logo abaixo deles. No bloco Microfone, do mesmo cartão: a barrinha de ondas, que mexe com o som que entra AGORA, e o selo ao lado da palavra Microfone, que diz ATIVO, MUDO ou um travessão. O ouvido encostado no alto-falante do controle é quem confirma para onde o som foi.

**Os passos.**

1. Abra o Hefesto e clique na aba Controles.
2. Clique na linha do P1 para abrir o cartão dele.
3. Confira qual dos dois botões de rota está aceso no bloco Alto-falante, e anote qual é.
4. Confira o microfone do P1: fale perto dele e veja a barrinha de ondas do bloco Microfone mexer.
5. Confira o que diz o selo ao lado da palavra Microfone, e anote.
6. Abra um jogo e faça-o produzir som.
7. Clique em "Sons do jogo" no bloco Alto-falante do P1.
8. Confira, com o ouvido encostado no P1, que o som do jogo sai dele.
9. Confira o microfone de novo: fale perto do P1 e veja a barrinha continuar mexendo.
10. Confira que o selo do Microfone continua dizendo o que você anotou.
11. Clique em "Todo o som do PC" no bloco do P1.
12. Confira que o botão aceso trocou.
13. Toque um vídeo fora do jogo.
14. Confira, com o ouvido encostado no P1, que o som do vídeo sai dele.
15. Confira o microfone mais uma vez: fale perto do P1 e veja a barrinha ainda mexer.
16. Leia a linha embaixo dos dois botões e anote se apareceu alguma frase.
17. Clique em "Sons do jogo" no bloco do P1 para devolver o som às caixas.
18. Clique na linha do P2 e refaça nele a sequência inteira, do primeiro clique de rota até devolver o som às caixas — inclusive as três conferências do microfone.
19. Abra o cartão do P3 e depois o do P4.
20. Confira que o botão de rota aceso de cada um dos dois não trocou.

**Passa quando.** No P1 e no P2 o botão aceso segue o seu clique, e o som vai para onde o botão diz: só o som do jogo com "Sons do jogo" aceso, o som do computador inteiro com "Todo o som do PC" aceso. E — esta é a metade que importa — o MICROFONE do mesmo controle continua vivo depois de cada troca: a barrinha de ondas mexe quando você fala e o selo não muda. O botão aceso do P3 e do P4 não trocou sozinho.

**Por controle.**

* **P1** — No cabo, e é ELE que troca de rota primeiro. Antes de cada troca, fale perto dele e olhe a barrinha do Microfone; depois de cada troca, fale de novo. As duas leituras do microfone são o teste, tanto quanto o som que sai.
* **P2** — No cabo, e faz a mesma sequência inteira, inclusive as duas conferências do microfone. Se o microfone morrer num dos dois e não no outro, anote em qual — é o dado que separa um defeito do aparelho de um defeito do comando.
* **P3** — No rádio, e é TESTEMUNHA. Não clique em botão de rota nenhum dele. Só abra o cartão no fim e confira que o botão aceso continua o mesmo. Se ele trocou junto, o comando pegou o transporte inteiro.
* **P4** — No rádio, e é a segunda testemunha. Mesma conferência do P3, e nenhum clique. Se o P3 ficou parado e o P4 trocou, alguma coisa escreveu no controle errado.

**A armadilha.** As três conferências do microfone — a de antes da primeira troca e as duas de depois — são o ponto do teste, não enfeite. Foi medido em 02/08/2026: pedir a rota escrevia por cima da metade do comando que carrega o caminho do microfone, e o microfone daquele controle foi a ZERO. Isso foi curado, e esta conferência é o que mantém curado — um teste de rota que só escuta o alto-falante passa por cima exatamente deste defeito. Segunda: se os DOIS botões apagarem e uma frase aparecer embaixo, isso não é falha — é o produto dizendo que o controle está roteado para receber todo o som mas a saída padrão do sistema é outra, e o som continua saindo onde estava; foi o que ela viu em 03/09, com o botão aceso e o som na TV. Leia a frase e faça o que ela manda. Terceira: com um fone plugado na entrada do controle, os dois botões também apagam, e isso é legítimo — há rotas de som que esses dois botões não representam, e acender um deles seria arredondar. E a prova desta célula chegou até "o aparelho obedeceu"; o degrau que este teste sobe é o jogo receber, e ele está sendo subido aqui pela primeira vez.

---

## mapa-audio.alto_falante.rota-radio — Alto-falante — rota de saída · rádio

*Célula:* `audio.alto_falante.rota @ rádio`

**O que isto prova.** Prova que trocar para onde o som vai, nos dois controles do rádio, é aceito, não apaga o microfone do mesmo controle e não vaza para os dois do cabo.

**Onde olhar.** Na aba Controles, no cartão do P3 e no do P4. No bloco Alto-falante: os dois botões "Sons do jogo" e "Todo o som do PC", com um deles aceso, e a linha de ressalva logo abaixo, que nos do rádio traz a frase "Pelo rádio o Hefesto ainda não faz o som sair neste alto-falante." No bloco Microfone do mesmo cartão: a barrinha de ondas e o selo ao lado da palavra Microfone.

**Os passos.**

1. Confira na fita do topo que P3 e P4 dizem rádio.
2. Abra o Hefesto e clique na aba Controles.
3. Clique na linha do P3 para abrir o cartão dele.
4. Leia a linha embaixo dos dois botões de rota e anote a frase inteira.
5. Anote qual dos dois botões está aceso.
6. Fale perto do P3 e confira que a barrinha do bloco Microfone mexe.
7. Anote o que diz o selo ao lado da palavra Microfone.
8. Clique em "Todo o som do PC" no bloco do P3.
9. Confira que o botão aceso trocou.
10. Fale perto do P3 de novo e confira que a barrinha do Microfone continua mexendo.
11. Confira que o selo do Microfone continua no que você anotou.
12. Encoste o ouvido no P3 e anote se saiu algum som.
13. Clique em "Sons do jogo" no bloco do P3.
14. Clique na linha do P4 e repita do passo 4 ao 13 nele.
15. Abra o cartão do P1 e depois o do P2 e confira que o botão aceso de cada um não trocou.

**Passa quando.** No P3 e no P4 o botão aceso segue o seu clique, e a frase de ressalva continua ali dizendo que por rádio o som ainda não sai. O microfone do mesmo controle continua vivo depois de cada troca — barrinha mexendo e selo igual. Nenhum som sai dos dois do rádio, e isso é o esperado. E o botão aceso do P1 e do P2 não trocou.

**Por controle.**

* **P1** — No cabo, e é TESTEMUNHA. Não clique em nada nele. Confira no fim que o botão de rota aceso dele é o mesmo do começo. Se trocou, o comando pegou o transporte inteiro em vez do controle escolhido.
* **P2** — No cabo, e é a segunda testemunha. Mesma conferência do P1. Um dos dois trocando e o outro não já diz que a mira do comando está errada, e vale anotar qual.
* **P3** — No rádio, e é ELE que troca primeiro. Leia a ressalva, troque de botão, e fale perto dele ANTES e DEPOIS da troca olhando a barrinha do microfone. Silêncio no alto-falante é a resposta certa.
* **P4** — No rádio, e faz a sequência inteira igual. É a segunda prova do rádio: a ressalva tem de aparecer nele também, e o microfone dele tem de sobreviver à troca do mesmo jeito.

**A armadilha.** No rádio não há som para escutar, e não é isso que este teste mede — ele mede três outras coisas: que o gesto é aceito, que ele não apaga o microfone do mesmo controle, e que ele não vaza para os dois do cabo. A prova desta célula parou no primeiro degrau pelo rádio: o produto monta e manda a rota, e ninguém mediu que o aparelho recebeu — então não escreva "a rota funcionou no rádio"; escreva o que você viu, que é o botão trocando e o microfone sobrevivendo. Segunda: no rádio a queda e a volta são rotina. Se o P3 cair e voltar no meio do teste, o botão aceso pode retornar sozinho ao que era, e isso é a reconexão, não o seu clique — anote a hora e refaça. Terceira: a conferência do microfone existe porque essa exata perda já aconteceu no cabo, medida em 02/08/2026; pular os passos 6, 10 e 11 é abrir mão da metade que caça o defeito conhecido.

---

## mapa-audio.alto_falante.volume-cabo — Alto-falante — volume · cabo

*Célula:* `audio.alto_falante.volume @ cabo`

**O que isto prova.** Prova que o deslizante de volume do alto-falante manda no som dos dois controles do cabo, e que o botão de calar só destrava depois do primeiro arrasto.

**Onde olhar.** Na aba Controles, com o cartão aberto, bloco Alto-falante: o deslizante de volume, o número ao lado dele, o botão ♪ (que é o calar) e o "?" ao lado do ♪, cuja frase explica por que ele está cinza. O som em si é do seu ouvido, encostado nos nove furinhos da frente do controle, entre os dois analógicos.

**Os passos.**

1. Abra o Hefesto e clique na aba Controles.
2. Clique na linha do P1 para abrir o cartão dele.
3. Confira que o botão ♪ do bloco Alto-falante está apagado, em cinza.
4. Leia a frase inteira que aparece quando o mouse para no "?" ao lado do ♪, e que explica o cinza.
5. Arraste o deslizante de volume do P1 até 60.
6. Confira que o número ao lado diz 60 e que o ♪ acendeu.
7. Clique em "Todo o som do PC" no bloco do P1 e toque uma música.
8. Encoste o ouvido nos nove furinhos do P1 e deixe-o ali até o fim da rodada dele.
9. Confira que a música sai pelo alto-falante do P1.
10. Arraste o volume do P1 até 100, escute, e só então arraste até 10.
11. Compare os três volumes, com o ouvido encostado: em 100 tem de ficar mais alto que em 60, e em 10, mais baixo.
12. Clique no ♪ do P1 uma vez só.
13. Confira que o som do P1 morreu no ato.
14. Clique no ♪ do P1 de novo.
15. Confira que o som voltou, e no mesmo volume em que estava.
16. Leia os números de volume do P2, do P3 e do P4 e confira que nenhum deles se mexeu.
17. Clique em "Sons do jogo" no bloco do P1, para devolver o som às caixas.
18. Clique na linha do P2 e refaça nele toda a sequência do P1, do ♪ cinza ao "Sons do jogo".

**Passa quando.** No P1 e no P2 o ♪ estava cinza antes do primeiro arrasto e acendeu depois dele. O número acompanha o arrasto. O quanto se ouve acompanha o número, com o ouvido encostado. O ♪ cala e descala sem perder o número. E os números dos outros três controles não se mexem enquanto você arrasta o de um.

**Por controle.**

* **P1** — No cabo, e é o primeiro. Faça a sequência inteira nele, começando pelo ♪ cinza — este é o único momento em que dá para ver o ♪ cinza, e ele se perde se você arrastar antes.
* **P2** — No cabo, e faz a mesma sequência. Ele é a segunda prova: se o ♪ do P1 destravar e o do P2 não, o defeito é daquele controle e vale anotar qual.
* **P3** — No rádio, e é TESTEMUNHA. Não arraste o deslizante dele. Anote o número dele antes e confira depois: se ele andar quando você mexe no P1, o comando pegou mais de um controle.
* **P4** — No rádio, e é a segunda testemunha. Mesma leitura do P3: número anotado antes, conferido depois, deslizante intocado.

**A armadilha.** O ♪ cinza antes do primeiro arrasto NÃO é defeito: é o produto se recusando a calar um alto-falante cujo volume ele não conhece, porque o DualSense não devolve esse número. Se ele já estiver aceso quando você abrir a aba, é porque alguém arrastou antes — outro teste, ou você mesma numa volta anterior — e o passo do ♪ cinza não mede nada; feche a janela do Hefesto no X e abra-a de novo, para que nenhum volume tenha sido escrito nesta sessão, e recomece do primeiro passo. Segunda: a prova desta célula parou no primeiro degrau, e há um número velho que engana — o "mudo até 38, satura em 102" foi levantado numa escala que não é a do deslizante da tela e num estado do produto que não existe mais, sem o reforço de ganho que ele escreve hoje. Não use aqueles números para julgar o curso desta tela. Terceira: o número na tela é o que o produto PEDIU; só o ouvido diz o que saiu. Marcar verde olhando só o número é medir a tela contra ela mesma. E o tamanho, declarado: são NOVE atos, um a mais que o alvo de oito, por duas razões que não se pode cortar. Calar e descalar são dois atos separados porque o que se mede é o silêncio ENTRE eles — num clique duplo não existe quando escutar o mudo, e quem seguisse o passo marcaria verde sobre metade que não ouviu. E o ouvido encostado no controle é ato próprio, não conferência: sem ele este teste vira leitura de número, que é justamente o que a terceira armadilha proíbe.

---

## mapa-audio.alto_falante.volume-radio — Alto-falante — volume · rádio

*Célula:* `audio.alto_falante.volume @ rádio`

**O que isto prova.** Prova que o volume do alto-falante é aceito nos dois controles do rádio, que o produto avisa que por ali o som ainda não sai, e que nada disso vaza para os dois do cabo.

**Onde olhar.** Na aba Controles, no cartão do P3 e no do P4, bloco Alto-falante: o deslizante de volume, o número ao lado, o botão ♪ com o "?" que explica o cinza dele, e a linha de ressalva embaixo dos dois botões de rota, que nos do rádio traz a frase "Pelo rádio o Hefesto ainda não faz o som sair neste alto-falante."

**Os passos.**

1. Feche a janela do Hefesto no X e abra-a de novo.
2. Clique na aba Controles.
3. Clique na linha do P3 para abrir o cartão dele.
4. Leia a linha embaixo dos botões de rota e anote a frase inteira.
5. Olhe o botão ♪ do bloco Alto-falante e confirme que ele está cinza.
6. Arraste o deslizante de volume do P3 até 50.
7. Confira que o número ao lado diz 50 e que o ♪ acendeu.
8. Encoste o ouvido no P3 e anote se saiu som.
9. Arraste até 100 e escute de novo.
10. Arraste até 0 e escute de novo.
11. Leia os números de volume do P1 e do P2 e confirme que nenhum se mexeu.
12. Clique na linha do P4 e repita do passo 4 ao 11 nele.
13. Volte ao cartão do P3 e confira se o ♪ continua aceso e o número continua onde você deixou.

**Passa quando.** No P3 e no P4 o ♪ estava cinza e acendeu depois do primeiro arrasto, e o número acompanha o deslizante. A frase de ressalva aparece nos dois cartões. Nenhum som sai de nenhum dos dois, em nenhuma das três posições — e isso é o esperado. E os números do P1 e do P2 continuam parados.

**Por controle.**

* **P1** — No cabo, e é TESTEMUNHA. Não arraste nada nele. Anote o número do volume dele antes e confira depois: se ele andar, o comando pegou o transporte inteiro em vez do controle escolhido.
* **P2** — No cabo, e é a segunda testemunha. Mesma leitura do P1. Um andando e o outro não já mostra que a mira do comando está errada.
* **P3** — No rádio, e é o primeiro a mexer. Confira o ♪ cinza, arraste até 50, 100 e 0, escutando em cada posição. Silêncio é a resposta certa aqui.
* **P4** — No rádio, e faz a mesma sequência. É a segunda prova do rádio: o ♪ dele também tem de destravar e a frase de ressalva também tem de aparecer.

**A armadilha.** Mexer neste volume pelo rádio é mexer no volume de uma coisa que ninguém está tocando: hoje não existe caminho de dados de som saindo pelo rádio. Então "não saiu som" é a resposta esperada e não reprova nada. O que reprova: o ♪ não destravar depois do arrasto (aí o comando nem saiu), a frase de ressalva não aparecer, ou o número de um controle do cabo andar junto. Segunda: a prova desta célula parou no primeiro degrau — o produto monta e manda o número, e ninguém mediu que o aparelho o recebeu por rádio; escreva o que a tela fez, não uma conclusão sobre o aparelho. Terceira: no rádio a queda e a volta são rotina. Se o ♪ voltar sozinho ao cinza, ou o número voltar ao que era, sem você fechar nada, anote a HORA — é exatamente o tipo de perda silenciosa que este teste consegue enxergar, e ela vale mais que o resto do resultado.

---

## mapa-audio.jack.deteccao-cabo — Jack — detecção de fone/microfone plugados · cabo

*Célula:* `audio.jack.deteccao @ cabo`

**O que isto prova.** Prova que, plugando um fone na entrada do próprio controle no cabo, o som muda de lugar: sai do alto-falante do controle e passa para o fone.

**Onde olhar.** No aparelho: a entrada de fone fica na borda de baixo do DualSense, no meio, ao lado do conector do cabo; e o alto-falante são os nove furinhos na frente, entre os dois analógicos. NA TELA NÃO HÁ ONDE LER "há fone plugado" — a fonte não diz, e nenhuma das dez abas mostra essa leitura. O mais perto disso são duas coisas: no cartão da aba Controles, bloco Alto-falante, os dois botões de rota APAGAM juntos quando o som está indo para o fone; e na aba Sistema, na seção "O exame de hoje", a linha do áudio, que conta as saídas de som dos controles no cabo — mas ela fala da saída do controle, não do fone plugado.

**Os passos.**

1. Abra a aba Controles.
2. Confira que não há fone plugado em controle nenhum, e deixe um fone de plugue 3,5 mm ao alcance da mão.
3. Clique na linha do P1 para abrir o cartão dele.
4. Arraste o volume do bloco Alto-falante do P1 até 80.
5. Clique em "Todo o som do PC" no bloco do P1 e toque uma música que se repita.
6. Confira, com o ouvido encostado no alto-falante do P1, que o som está saindo por ali.
7. Repare qual dos dois botões de rota do P1 está aceso.
8. Plugue o fone na entrada da borda de baixo do P1.
9. Confira, com o fone no ouvido, que o som passou para ele.
10. Confira, com o ouvido no alto-falante do P1, que ele emudeceu.
11. Repare se algum dos dois botões de rota do P1 apagou.
12. Tire o fone do P1.
13. Confira, com o ouvido no alto-falante do P1, que o som voltou para ele.
14. Clique em "Sons do jogo" no bloco do P1 para devolver o som às caixas.
15. Repita a volta inteira no P2, do cartão aberto até "Sons do jogo", com o MESMO fone.
16. Vá à aba Sistema e passe o mouse na linha do áudio da seção "O exame de hoje".
17. Leia a frase inteira que aparece e veja se ela conta os dois controles do cabo.
18. Confira, com o ouvido no P3 e no P4, que os dois ficaram mudos do começo ao fim.

**Passa quando.** No P1 e no P2, que estão no cabo, plugar o fone MUDA o som de lugar: o fone toca e o alto-falante do controle emudece; tirar o fone traz o som de volta para o alto-falante. O P3 e o P4 ficaram mudos do começo ao fim. E a linha do áudio da seção "O exame de hoje" conta os dois controles do cabo.

**Por controle.**

* **P1** — No cabo, e é o primeiro. Faça a sequência inteira nele: ouvir no alto-falante, plugar o fone, ouvir no fone, conferir o alto-falante mudo, tirar o fone, ouvir o alto-falante de novo.
* **P2** — No cabo, e faz a mesma sequência com o MESMO fone. Ele é a segunda prova: se o som mudar de lugar num e não no outro, o problema é daquele controle, e vale anotar qual.
* **P3** — No rádio, e é TESTEMUNHA. Não plugue fone nele neste teste. Encoste o ouvido e confirme silêncio: se ele começar a soar quando o fone entra no P1, alguma coisa pegou o transporte inteiro.
* **P4** — No rádio, e é a segunda testemunha. Mesmo gesto do P3: nada plugado, ouvido encostado, silêncio esperado.

**A armadilha.** Este teste não tem campo na tela para ler: em lugar nenhum das dez abas o produto diz "tem fone plugado", e a fonte não diz onde isso se leria. O que você mede é a CONSEQUÊNCIA, com o ouvido. Por isso, se o som não mudar de lugar, não conclua que a detecção falhou: pode ser a rota, pode ser o volume, pode ser um fone com o plugue ruim — teste o mesmo fone numa saída do PC antes de acusar o controle. Segunda: os dois botões de rota apagarem quando o fone entra é ESPERADO e não é defeito — há rotas legítimas que mandam tudo para o fone e que esses dois botões não representam; acender um deles ali seria arredondar para o botão mais parecido. Terceira: a linha do "O exame de hoje" fala da saída de som do controle, não do fone que você plugou; lê-la como "ele viu meu fone" é ler outra coisa. E a prova desta célula parou no primeiro degrau: o produto lê o dado da detecção, e ninguém nunca pôs e tirou um fone para conferir — esta volta é a primeira.

---

## mapa-audio.jack.deteccao-radio — Jack — detecção de fone/microfone plugados · rádio

*Célula:* `audio.jack.deteccao @ rádio`

**O que isto prova.** Prova que plugar um fone num controle do rádio não faz o Hefesto prometer um som que ele ainda não entrega, e não mexe nos dois do cabo.

**Onde olhar.** No aparelho: a entrada de fone na borda de baixo do P3 e do P4, ao lado de onde o cabo entraria. Na tela, o cartão do P3 e do P4 na aba Controles, bloco Alto-falante: a linha de ressalva embaixo dos dois botões de rota, que nos do rádio traz "Pelo rádio o Hefesto ainda não faz o som sair neste alto-falante.", e o rótulo do bloco, que nos do rádio NÃO ganha "· acordado" nem "· dormindo". Onde se leria "há fone plugado" não existe: a fonte não diz.

**Os passos.**

1. Confira na fita do topo que P3 e P4 dizem rádio e não têm cabo plugado.
2. Plugue o fone na entrada da borda de baixo do P1, que está no cabo, e toque uma música.
3. Ponha o fone no ouvido e confirme que ele toca — isto prova o fone antes de tudo.
4. Tire o fone do P1.
5. Abra o Hefesto e clique na aba Controles.
6. Clique na linha do P3 para abrir o cartão dele.
7. Leia a linha embaixo dos botões de rota e anote a frase inteira.
8. Leia o rótulo do bloco Alto-falante e confira que ele não traz "· acordado" nem "· dormindo".
9. Arraste o volume do alto-falante do P3 até 100.
10. Clique em "Todo o som do PC" no bloco do P3.
11. Plugue o fone na entrada do P3.
12. Ponha o fone no ouvido e anote se saiu som.
13. Olhe a tela e anote se QUALQUER coisa do cartão do P3 mudou quando o fone entrou.
14. Tire o fone do P3 e clique em "Sons do jogo" no bloco dele.
15. Clique na linha do P4 e repita do passo 7 ao 14 nele.
16. Abra o cartão do P1 e depois o do P2 e confira que nada mudou neles.

**Passa quando.** O mesmo fone toca quando plugado no P1, que está no cabo, e não toca quando plugado no P3 nem no P4 — e esse silêncio é o esperado. A frase de ressalva continua nos cartões do P3 e do P4 dizendo que por rádio o som não sai. Nada muda nos cartões do P1 e do P2 durante o teste.

**Por controle.**

* **P1** — No cabo, e é a PROVA DO FONE: é nele que você confirma, antes de tudo, que o fone funciona. Sem esse passo, o silêncio no P3 não quer dizer nada. Depois disso ele vira testemunha e você não mexe mais nele.
* **P2** — No cabo, e é testemunha. Não plugue nada nele. Confira no fim que o cartão dele está como estava.
* **P3** — No rádio, e é ELE que recebe o fone. Leia a ressalva, confira o rótulo sem sufixo, arraste o volume até 100, plugue o fone e escute. Silêncio é a resposta certa.
* **P4** — No rádio, e faz o mesmo que o P3, com o mesmo fone. É a segunda prova do rádio: a ressalva tem de estar nele também.

**A armadilha.** O silêncio no fone plugado num controle do rádio é a resposta certa, e é fácil de confundir com fone quebrado — por isso o passo 2 prova o fone no P1 ANTES de qualquer outra coisa. Se ele toca no P1 e não toca no P3, o fone está bom e o que você mediu foi o rádio. Segunda: o rótulo do bloco sem "· acordado" nos do rádio não é leitura faltando; é o produto dizendo honestamente que não sabe, porque no rádio o controle não publica saída de som nenhuma, e escrever "acordado" a partir de ausência seria prometer som. Terceira: a prova desta célula parou no primeiro degrau — o produto lê o dado da detecção também pelo rádio, e ninguém plugou um fone para ver. Por isso o passo 13 existe: se ALGUMA coisa mudar na tela quando o plugue entra, anote, porque isso é mais do que qualquer pessoa desta casa já mediu.

---

## mapa-audio.jack.volume-cabo — Fone de ouvido (jack do controle) — volume · cabo

*Célula:* `audio.jack.volume @ cabo`

**O que isto prova.** Prova que, com o fone plugado no controle, o mesmo deslizante do bloco Alto-falante manda também no volume do fone, nos dois controles do cabo.

**Onde olhar.** Na aba Controles, com o cartão aberto, bloco Alto-falante: o deslizante de volume, o número ao lado e o botão ♪. NÃO existe na tela um volume próprio do fone — é este mesmo deslizante que vai para os dois. A resposta é o fone no seu ouvido, plugado na borda de baixo do controle, ao lado de onde o cabo entra.

**Os passos.**

1. Abra o Hefesto e clique na aba Controles.
2. Plugue o fone na entrada da borda de baixo do P1 e ponha-o no ouvido.
3. Clique na linha do P1 para abrir o cartão dele.
4. Clique em "Todo o som do PC" no bloco Alto-falante do P1.
5. Toque uma música que se repita e não mexa mais no volume do sistema até o fim.
6. Arraste o deslizante do bloco Alto-falante do P1 pelas paradas 20, 50, 100 e 0, escutando o fone em cada uma, e devolva-o a 50.
7. Confira que de 20 para 50, e de 50 para 100, o fone fica mais alto a cada parada.
8. Confira que em 0 o fone fica em silêncio.
9. Repare em que número o som parou de ficar mais alto, se isso acontecer, e anote esse número.
10. Clique no ♪ do bloco do P1 duas vezes, com uma pausa entre as duas para escutar o fone.
11. Confira que o primeiro clique cala o fone e o segundo traz o som de volta.
12. Tire o fone do P1 e devolva o bloco Alto-falante dele para "Sons do jogo".
13. Refaça os atos 1 a 7 no P2, com o mesmo fone — a música pode continuar tocando.
14. Confira que os números de volume do P3 e do P4 não se mexeram enquanto você arrastava o de um controle do cabo.

**Passa quando.** No fone plugado no P1 e no plugado no P2, o quanto se ouve acompanha o deslizante nas três posições, 0 é silêncio e o ♪ cala e traz de volta. E os números do P3 e do P4 não se mexem enquanto você arrasta o de um controle do cabo.

**Por controle.**

* **P1** — No cabo, e é o primeiro a receber o fone. Faça as três posições e as duas do ♪ com o fone no ouvido, sem mexer no volume do sistema.
* **P2** — No cabo, e recebe o MESMO fone depois. Ele é a segunda prova: se o volume do fone seguir o deslizante num e não no outro, anote qual — é o dado que separa aparelho de comando.
* **P3** — No rádio, e é TESTEMUNHA. Não plugue fone nem arraste nada nele. Anote o número do volume antes e confira depois: se andar, o comando pegou mais de um controle.
* **P4** — No rádio, e é a segunda testemunha. Mesma leitura do P3, sem tocar em nada.

**A armadilha.** O fone NÃO tem volume próprio na tela, e é aí que este teste engana: o mesmo deslizante vai para os dois, então o som mudar no fone não prova que o campo do fone funciona — prova que o único campo alcança os dois. Segunda, e é dívida declarada desta casa: a autorização para mexer no volume do fone NÃO está no núcleo do sistema, veio de fonte de comunidade, e a curva do deslizante foi levantada no ALTO-FALANTE, nunca no fone. Então, se acima de mais ou menos metade do curso o fone parar de ficar mais alto, isso é ACHADO deste teste e não erro seu — a conferência do ato 5 existe para você anotar em que número ele empacou. Terceira: a prova desta célula parou no primeiro degrau; ninguém desta casa jamais plugou um fone e arrastou este deslizante. E mantenha o volume do sistema fixo do começo ao fim, senão o degrau é falso.

---

## mapa-audio.jack.volume-radio — Fone de ouvido (jack do controle) — volume · rádio

*Célula:* `audio.jack.volume @ rádio`

**O que isto prova.** Prova que o volume do fone é aceito nos dois controles do rádio, que nada sai por ali, e que o mesmo fone toca quando vai para um controle do cabo.

**Onde olhar.** Na aba Controles, no cartão do P3 e no do P4, bloco Alto-falante: o deslizante de volume, o número ao lado, o botão ♪, e a linha de ressalva embaixo dos botões de rota, que nos do rádio traz "Pelo rádio o Hefesto ainda não faz o som sair neste alto-falante." O fone vai na borda de baixo do controle. Não existe na tela um volume próprio do fone — é o mesmo deslizante do alto-falante.

**Os passos.**

1. Confira na fita do topo que P3 e P4 dizem rádio.
2. Plugue o fone no P1, que está no cabo, toque uma música e confirme no ouvido que ele toca.
3. Tire o fone do P1.
4. Abra o Hefesto e clique na aba Controles.
5. Clique na linha do P3 para abrir o cartão dele.
6. Leia a linha embaixo dos botões de rota e anote a frase inteira.
7. Plugue o fone na entrada do P3 e ponha-o no ouvido.
8. Clique em "Todo o som do PC" no bloco do P3.
9. Arraste o deslizante de volume do P3 até 20 e escute.
10. Arraste até 50 e escute.
11. Arraste até 100 e escute.
12. Confira que o ♪ acendeu depois do primeiro arrasto.
13. Leia os números de volume do P1 e do P2 e confirme que não se mexeram.
14. Tire o fone do P3 e clique em "Sons do jogo" no bloco dele.
15. Plugue o fone no P4 e repita do passo 6 ao 14 nele.

**Passa quando.** O mesmo fone toca quando plugado no P1, no cabo, e não toca em nenhuma das três posições quando plugado no P3 ou no P4 — e esse silêncio é o esperado. O número acompanha o deslizante nos dois do rádio e o ♪ destrava depois do primeiro arrasto. A frase de ressalva está nos dois cartões do rádio. E os números do P1 e do P2 continuam parados.

**Por controle.**

* **P1** — No cabo, e é a PROVA DO FONE: nele o fone tem de tocar, antes de qualquer outra coisa. Sem isso, o silêncio no rádio não mede nada. Depois ele é testemunha e você não mexe mais nele.
* **P2** — No cabo, e é testemunha. Não plugue nem arraste. Anote o número do volume dele antes e confira depois.
* **P3** — No rádio, e é o primeiro a receber o fone. Leia a ressalva, arraste até 20, 50 e 100 com o fone no ouvido, e confira o ♪ destravando. Silêncio é a resposta certa.
* **P4** — No rádio, e recebe o mesmo fone depois. É a segunda prova do rádio: a ressalva e o comportamento do deslizante têm de ser iguais aos do P3.

**A armadilha.** O silêncio é a resposta esperada aqui, e é por isso que o passo 2 existe: sem provar o fone no P1, um fone ruim e o rádio dão exatamente o mesmo resultado. Segunda: o número na tela é o que o produto PEDIU, não o que o aparelho fez — a prova desta célula parou no primeiro degrau, e pelo rádio ninguém mediu se o comando chegou. Escreva o que a tela fez e o que o ouvido não ouviu, sem concluir sobre o aparelho. Terceira: no rádio a queda e a volta são rotina; se o ♪ voltar sozinho ao cinza ou o número resetar enquanto você testa, anote a HORA — é o tipo de perda silenciosa que este teste enxerga. E lembre-se de que o fone não tem deslizante próprio: o que você está arrastando é o do alto-falante, que carrega os dois.

---

## mapa-audio.leitura_de_volta-cabo — Áudio — leitura de volta (qualquer registrador) · cabo

*Célula:* `audio.leitura_de_volta @ cabo`

**O que isto prova.** Mede o que o Hefesto consegue LER DE VOLTA do som dos dois controles do cabo: o mudo do microfone volta do aparelho, e o volume do alto-falante não volta de lugar nenhum.

**Onde olhar.** Na aba Controles, com o cartão aberto, dois lugares que dão respostas opostas. No bloco Microfone: o selo ao lado da palavra Microfone, que diz ATIVO, MUDO ou um travessão — o travessão quer dizer "não consegui ler", e não é nenhum dos dois. No bloco Alto-falante: o botão ♪ e o "?" ao lado dele, cuja frase diz com todas as letras que o DualSense não publica o volume. No aparelho, o botão de microfone é o botãozinho de mudo no plástico, logo abaixo do touchpad.

**Os passos.**

1. Feche a janela do Hefesto no X e abra-a de novo.
2. Clique na aba Controles.
3. Clique na linha do P1 para abrir o cartão dele.
4. Leia o selo ao lado da palavra Microfone e anote o que ele diz.
5. Aperte uma vez o botão de microfone no plástico do P1.
6. Leia o selo de novo e anote se ele mudou.
7. Espere um segundo e aperte o botão do plástico outra vez.
8. Confira que o selo voltou ao que dizia no passo 4.
9. Olhe o botão ♪ do bloco Alto-falante do P1 e anote se ele está aceso ou cinza.
10. Passe o mouse no "?" ao lado do ♪ e leia a frase inteira.
11. Arraste o volume do alto-falante do P1 até 70.
12. Confira que o ♪ acendeu e que o número diz 70.
13. Feche a janela do Hefesto no X e abra-a de novo.
14. Clique na linha do P1 e anote o número do volume e o estado do ♪ agora.
15. Clique na linha do P2 e repita do passo 4 ao 14 nele.
16. Confira que os selos e os números do P3 e do P4 não se mexeram em nenhum momento.

**Passa quando.** No P1 e no P2, o selo do Microfone SEGUE o botão do plástico a cada aperto — isso é uma leitura que voltou do aparelho. E o volume do alto-falante NÃO volta: o ♪ estava cinza antes do primeiro arrasto, e a frase do "?" diz por quê. O que este teste entrega é o que você anotou no passo 14 — o número e o ♪ depois de fechar e reabrir. Nada mudou no P3 e no P4.

**Por controle.**

* **P1** — No cabo, e é o primeiro. Aperte o botão de microfone do plástico dele duas vezes, com um segundo entre os apertos, olhando o selo. Depois faça a parte do alto-falante inteira, inclusive fechar e reabrir a janela.
* **P2** — No cabo, e faz a mesma sequência. Ele é a segunda prova: se o selo seguir o botão num e não no outro, anote qual — é a diferença entre um aparelho e o produto.
* **P3** — No rádio, e é TESTEMUNHA. Não aperte o botão de microfone dele nem arraste nada. Confira que o selo e o número dele ficaram parados o tempo todo.
* **P4** — No rádio, e é a segunda testemunha. Mesma conferência do P3: selo parado, número parado, nada tocado.

**A armadilha.** Esta é a única linha do lote que ainda NÃO TEM resposta, e o que está em disputa é o que "ler de volta" quer dizer — a decisão é DELA e ainda não foi tomada. Se quiser dizer "qualquer estado relido do aparelho", o selo do microfone já responde que sim. Se quiser dizer estritamente "o comando que NÓS mandamos, relido de volta", a resposta continua sendo não, porque o que volta é um dado que o controle manda sozinho, e não o eco do que enviamos. Enquanto ela não decidir, NADA aqui reprova o produto: não escreva "passou" nem "reprovou" — escreva o que aconteceu, aperto por aperto. E um cuidado que muda o resultado inteiro: não clique no 🎙 da TELA antes deste teste. A partir desse clique o mudo daquele controle passa a ser do Hefesto e o botão do plástico deixa de valer — e aí o selo pararia de seguir o botão por um motivo que não tem nada a ver com ler de volta. Dê um segundo entre um aperto e o seguinte no mesmo controle: apertos mais rápidos que isso são engolidos de propósito.

---

## mapa-audio.leitura_de_volta-radio — Áudio — leitura de volta (qualquer registrador) · rádio

*Célula:* `audio.leitura_de_volta @ rádio`

**O que isto prova.** Mede o que o Hefesto consegue ler de volta dos dois controles do rádio, e se essa leitura sobrevive a uma queda e uma volta — que no rádio é rotina.

**Onde olhar.** Na aba Controles, com o cartão aberto: no bloco Microfone, o selo ao lado da palavra Microfone, que diz ATIVO, MUDO ou um travessão; no bloco Alto-falante, o botão ♪ e o número do volume ao lado do deslizante. No aparelho, o botão de microfone é o botãozinho de mudo no plástico, logo abaixo do touchpad; e o botão PS é o redondo do meio de baixo, entre os dois analógicos.

**Os passos.**

1. Feche a janela do Hefesto no X e abra-a de novo.
2. Clique na aba Controles.
3. Clique na linha do P3 para abrir o cartão dele.
4. Leia o selo ao lado da palavra Microfone e anote o que ele diz.
5. Aperte uma vez o botão de microfone no plástico do P3.
6. Leia o selo de novo e anote se ele mudou.
7. Espere um segundo e aperte o botão do plástico outra vez.
8. Confira que o selo voltou ao que dizia no passo 4.
9. Olhe o botão ♪ do bloco Alto-falante do P3 e anote se está aceso ou cinza.
10. Arraste o volume do alto-falante do P3 até 70 e confira que o ♪ acendeu.
11. Segure o botão PS do P3 até TODAS as luzes dele apagarem, e solte.
12. Segure o botão PS do P3 por cerca de cinco segundos, até a barra de luz acender, e solte.
13. Clique na linha do P3 e anote o selo do Microfone, o número do volume e o estado do ♪ agora.
14. Clique na linha do P4 e repita do passo 4 ao 13 nele.
15. Confira que os selos e os números do P1 e do P2 não se mexeram em nenhum momento.

**Passa quando.** No P3 e no P4, o selo do Microfone segue o botão do plástico a cada aperto, e o ♪ do alto-falante estava cinza até o primeiro arrasto. O que este teste entrega é o que você anotou no passo 13 — o selo, o número e o ♪ DEPOIS de o controle cair e voltar. Nada mudou no P1 e no P2.

**Por controle.**

* **P1** — No cabo, e é TESTEMUNHA. Não toque nele. Confira no fim que o selo do microfone e o número do volume dele são os mesmos do começo.
* **P2** — No cabo, e é a segunda testemunha. Mesma conferência do P1. Se um dos dois do cabo se mexer quando o P3 cai e volta, isso é achado e vale anotar.
* **P3** — No rádio, e é o primeiro a mexer. Faça os dois apertos do botão do plástico, arraste o volume, e então desligue e religue ELE pelo botão PS. É a queda e a volta que este teste veio medir.
* **P4** — No rádio, e faz a sequência inteira igual, inclusive desligar e religar. É a segunda prova do rádio: se um perder o estado e o outro não, anote qual.

**A armadilha.** Esta linha ainda não tem resposta e o sentido dela é DECISÃO DELA, ainda não tomada — então não escreva "passou" nem "reprovou", escreva o que aconteceu. Sobre a queda e a volta, há um defeito conhecido e MEDIDO: em 03/08/2026 um mudo pedido pelo Hefesto EVAPOROU quando o controle caiu e voltou, porque o vínculo com o aparelho se refaz e o pedido não vai junto. A cura foi proposta e NÃO foi feita. Então, se depois do passo 12 o selo ou o ♪ voltarem diferentes, isso é o achado esperado desta linha e não erro seu: anote a hora e siga. E duas armadilhas de gesto: não clique no 🎙 da TELA antes deste teste, porque a partir dali o botão do plástico para de valer e o selo pararia de segui-lo por outro motivo; e segure o PS até as luzes apagarem de verdade para desligar — cerca de cinco segundos é lido como toque curto e ABRE A STEAM. Se a Steam abrir, feche-a e refaça o passo.

---

## mapa-audio.microfone-cabo — Microfone — captação do áudio · cabo

*Célula:* `audio.microfone @ cabo`

**O que isto prova.** Prova que o microfone dos dois controles do cabo capta a voz dela e chega até um programa do computador, um controle de cada vez.

**Onde olhar.** Na aba Controles, com o cartão aberto, bloco Microfone: a barrinha de ondas, que mexe com o som que entra AGORA, e o selo ao lado da palavra Microfone, que diz ATIVO, MUDO ou um travessão. E na aba Conexões: na linha fechada de cada controle está escrito por onde o microfone chega — nos do cabo tem de dizer "Microfone Ligado, pelo cabo • Placa do controle".

**Os passos.**

1. Abra o Hefesto e clique na aba Conexões.
2. Leia a linha do P1 e confira que ela diz Microfone Ligado, pelo cabo • Placa do controle.
3. Leia a linha do P2 e confira o mesmo.
4. Clique na aba Controles.
5. Clique na linha do P1 para abrir o cartão dele.
6. Confira que o selo ao lado da palavra Microfone diz ATIVO.
7. Fale perto do P1, em tom normal, e olhe a barrinha de ondas do bloco Microfone.
8. Fique em silêncio três segundos e confira que a barrinha desce.
9. Abra um programa que ouça microfone — um gravador ou uma chamada de voz.
10. Escolha, nesse programa, a entrada que corresponde ao P1.
11. Fale e confirme que o programa está ouvindo você.
12. Fale perto do P2 e confira que a barrinha do cartão do P1 NÃO mexe.
13. Clique na linha do P2 e repita do passo 6 ao 11 nele.
14. Fale perto do P3 e depois perto do P4 e confira que a barrinha do cartão aberto não mexe.

**Passa quando.** No P1 e no P2 a barrinha de ondas mexe quando você fala e desce no silêncio, o selo diz ATIVO, e um programa do computador ouve a sua voz pela entrada daquele controle. Falar perto de um controle não mexe a barrinha do outro. E a aba Conexões diz, nos dois, que o microfone chega pelo cabo, pela placa do controle.

**Por controle.**

* **P1** — No cabo, e é o primeiro. Fale perto dele, veja a barrinha, escolha a entrada dele no programa e confirme que ele te ouve. Depois fale perto do P2 sem tocar no P1 — a barrinha do P1 não pode mexer.
* **P2** — No cabo, e faz a mesma sequência inteira. É a segunda prova do cabo: se um capta e o outro não, anote qual — o defeito é daquele aparelho, não do caminho.
* **P3** — No rádio, e é TESTEMUNHA. Não fale perto dele durante o teste do P1, a não ser no passo 14, que existe justamente para provar que a voz de perto dele não aparece na barrinha do controle do cabo.
* **P4** — No rádio, e é a segunda testemunha. Mesmo gesto do P3: fale perto dele só no passo 14 e confira que a barrinha do cartão aberto fica parada.

**A armadilha.** Há uma regra do sistema que mata esta linha inteira e que só existe se alguém a instalou de propósito: se a regra que desliga o áudio USB do controle estiver ligada, o microfone E o fone de TODOS os controles do cabo ficam mortos e nada aqui funciona. Quem diz se ela está ligada é a seção "O exame de hoje", na aba Sistema — vá lá antes de acusar o produto. Segunda, e ela já enganou esta casa: o sistema pode marcar o microfone do controle como indisponível e ele captar assim mesmo — medido em 16 e 17/08/2026, com a voz dela, no cabo: com a porta marcada como indisponível o microfone captou 12% da escala em seis segundos de fala contra 0,4% em cinco de silêncio. Então não reprove pela palavra de uma lista de aparelhos; reprove pela barrinha e pelo programa. Terceira: a prova desta célula chegou até "saiu no fio" — o som sai do controle. Que um programa o ouça é o degrau que este teste sobe, e o selo ATIVO já carrega as duas metades, porque ele só acende quando o aparelho não está calando E o som chega ao canal dele.

---

## mapa-audio.microfone-radio — Microfone — captação do áudio · rádio

*Célula:* `audio.microfone @ rádio`

**O que isto prova.** Prova que o microfone dos dois controles do rádio chega ao computador pela ponte do Hefesto, e que o botão Nativo, no rádio, não tem por onde entregar som.

**Onde olhar.** Na aba Controles, com o cartão aberto, bloco Microfone: a barrinha de ondas, o selo ao lado da palavra Microfone e, na fileira embaixo do deslizante, os dois botões de modo, "Virtual" e "Nativo", com um deles aceso. E na aba Conexões: na linha fechada de cada controle está escrito por onde o microfone chega — nos do rádio tem de dizer "Microfone Ligado, pelo rádio • Pela ponte".

**Os passos.**

1. Abra o Hefesto e clique na aba Conexões.
2. Leia a linha do P3 e confira que ela diz Microfone Ligado, pelo rádio • Pela ponte.
3. Leia a linha do P4 e confira o mesmo.
4. Clique na aba Controles.
5. Clique na linha do P3 para abrir o cartão dele.
6. Anote qual dos dois botões de modo está aceso, Virtual ou Nativo.
7. Clique em "Virtual", se ele já não estiver aceso.
8. Confira que o selo ao lado da palavra Microfone diz ATIVO.
9. Fale perto do P3, em tom normal, e olhe a barrinha de ondas.
10. Fique em silêncio três segundos e confira que a barrinha desce.
11. Abra um programa que ouça microfone e escolha a entrada que corresponde ao P3.
12. Fale e confirme que o programa está ouvindo você.
13. Clique em "Nativo" no cartão do P3, fale de novo e anote o que a barrinha faz.
14. Clique em "Virtual" de volta no cartão do P3.
15. Clique na linha do P4 e repita do passo 6 ao 14 nele.
16. Fale perto do P1 e do P2 e confira que a barrinha do cartão aberto não mexe.

**Passa quando.** No P3 e no P4, com "Virtual" aceso, a barrinha de ondas mexe com a sua voz e um programa do computador ouve a voz pela entrada daquele controle — o som do microfone de um controle do rádio chegando ao PC é o degrau que este teste sobe. A aba Conexões diz, nos dois, que ele chega pelo rádio, pela ponte. E falar perto de um controle não mexe a barrinha de outro.

**Por controle.**

* **P1** — No cabo, e é TESTEMUNHA. Não mexa nos botões de modo dele. Fale perto dele no passo 16 e confira que a barrinha do cartão do rádio que está aberto não reage.
* **P2** — No cabo, e é a segunda testemunha. Mesmo gesto do P1. Se falar perto de um controle do cabo mexer a barrinha de um do rádio, alguma coisa está entregando o som do controle errado.
* **P3** — No rádio, e é o primeiro. Ponha "Virtual", fale, confira a barrinha e o programa. Depois clique em "Nativo" só para anotar o que acontece, e volte para "Virtual" antes de sair.
* **P4** — No rádio, e faz a sequência inteira igual. É a segunda prova do rádio, e a que revela o preço: com os dois microfones do rádio ligados ao mesmo tempo, repare se os botões dos dois começam a responder atrasados.

**A armadilha.** O botão "Nativo" num controle do rádio é a armadilha deste teste. Pelo rádio o controle não publica saída de som nenhuma — o DualSense não anuncia perfil de áudio por Bluetooth —, então no modo Nativo não há de onde o som sair, e silêncio ali é a resposta esperada, não defeito. Volte para "Virtual" antes de concluir qualquer coisa. Segunda: o microfone no rádio CUSTA. Com ele ligado, um controle do rádio troca parte dos turnos de resposta por turnos de som, e os turnos são do ADAPTADOR, divididos entre os controles ligados nele — com dois no rádio, cada um fica com cerca de metade. Então, se os botões do P3 e do P4 começarem a responder atrasados com os dois microfones ligados, isso é o preço, ele está medido, e vale anotar. Terceira: a prova desta célula parou no primeiro degrau pelo rádio — a ponte é montada e ninguém mediu o som saindo. Qualquer coisa que você ouvir aqui é mais do que já foi medido, e "não saiu som" é resultado legítimo para anotar.

---

## mapa-audio.microfone.mudo-cabo — Microfone — mudo no firmware · cabo

*Célula:* `audio.microfone.mudo @ cabo`

**O que isto prova.** Prova que calar o microfone pela tela cala o controle escolhido e só ele, nos dois do cabo, e que a luz vermelha do plástico conta a mesma história.

**Onde olhar.** No aparelho: o botão de microfone é o botãozinho de mudo no plástico, logo abaixo do touchpad, e ele tem uma luz vermelha. Na tela, aba Controles, com o cartão aberto, bloco Microfone: o selo ao lado da palavra Microfone (ATIVO, MUDO ou um travessão), a barrinha de ondas e o botão 🎙, que é o de calar.

**Os passos.**

1. Abra o Hefesto e clique na aba Controles.
2. Clique na linha de cada um dos quatro controles, um por vez, e anote o que diz o selo do Microfone de cada um.
3. Clique na linha do P1 para deixar o cartão dele aberto.
4. Fale perto do P1 e confira que a barrinha de ondas mexe.
5. Clique no 🎙 do bloco Microfone do P1.
6. Olhe a luz vermelha do botão de microfone no plástico do P1 e ANOTE o que ela fez.
7. Leia o selo do P1 e confira que ele passou a dizer MUDO.
8. Fale perto do P1 e confira que a barrinha parou de mexer.
9. Abra os cartões do P2, do P3 e do P4, um por vez, e confira que os selos deles não mudaram.
10. Volte ao cartão do P1 e clique no 🎙 de novo.
11. Confira que o selo do P1 voltou a dizer ATIVO e que a barrinha volta a mexer quando você fala.
12. Clique na linha do P2 e repita do passo 4 ao 11 nele.
13. Confira que os quatro selos voltaram ao que diziam no passo 2.
14. Feche a janela do Hefesto no X e abra-a de novo, para devolver o mudo ao botão do plástico.

**Passa quando.** No P1 e no P2 o clique no 🎙 cala AQUELE controle: o selo passa a MUDO, a barrinha para de mexer e a luz vermelha do plástico muda. Os outros três não se mexem. Clicar de novo traz de volta. E a luz vermelha faz a mesma coisa nos dois controles do cabo — se ela acende quando o selo diz MUDO num, tem de acender no outro também.

**Por controle.**

* **P1** — No cabo, e é ELE que você cala primeiro. Antes de clicar, fale perto dele e veja a barrinha; depois de clicar, anote o que a luz vermelha fez e confira o selo. Clique de novo para desfazer.
* **P2** — No cabo, e faz a mesma sequência. Antes de clicar nele, olhe onde estão os quatro selos: o erro que este teste caça é calar UM e outro emudecer junto, e isso só se enxerga sabendo o de antes.
* **P3** — No rádio, e é TESTEMUNHA. Não clique no 🎙 dele nem aperte o botão do plástico dele. O selo dele tem de ficar parado enquanto você cala os do cabo.
* **P4** — No rádio, e é a segunda testemunha. Mesma conferência do P3. Se o P3 ficou parado e o P4 mudou, não é o transporte — é alguma coisa escrevendo no controle errado.

**A armadilha.** O 🎙 da TELA tira o mudo do botão do plástico e NÃO devolve: a partir do clique quem manda no mudo daquele controle é o Hefesto, e o botão do plástico para de valer. É por isso que o último passo fecha e reabre a janela. Se você fizer este teste antes do teste do botão físico e não reabrir, o segundo dá vermelho sobre um controle são. Segunda: são DOIS mudos em série e só um é nosso — o próprio sistema, ao ver o botão do plástico ser apertado, vira o mudo do aparelho por conta própria, sem pedir licença a ninguém. Então um selo que muda sem você ter clicado em nada pode ser ele, e não o Hefesto. Terceira: a prova desta célula parou no primeiro degrau; que o comando é montado e enviado ninguém duvida, e o que você mede aqui — a luz vermelha e a barrinha — é o degrau acima. Por isso o passo 6 manda ANOTAR o que a luz fez, em vez de esperar um sentido: a dica do 🎙 descreve o caminho da tela, não o do botão do plástico, e se os dois discordarem isso é o achado.

---

## mapa-audio.microfone.mudo-radio — Microfone — mudo no firmware · rádio

*Célula:* `audio.microfone.mudo @ rádio`

**O que isto prova.** Prova que calar o microfone pela tela cala o controle escolhido nos dois do rádio, e mede se esse mudo sobrevive a uma queda e uma volta.

**Onde olhar.** No aparelho: o botãozinho de mudo no plástico, logo abaixo do touchpad, com a luz vermelha; e o botão PS, o redondo do meio de baixo, entre os analógicos. Na tela, aba Controles, com o cartão aberto, bloco Microfone: o selo ao lado da palavra Microfone (ATIVO, MUDO ou travessão), a barrinha de ondas e o botão 🎙.

**Os passos.**

1. Abra a aba Controles.
2. Leia o selo do Microfone dos quatro controles, um cartão por vez e terminando no P3, e anote o que cada um diz — é o ponto de partida.
3. Fale perto do P3.
4. Confira que a barrinha de ondas do cartão dele mexe.
5. Clique no 🎙 do bloco Microfone do P3.
6. Veja a luz vermelha do botão de microfone no plástico do P3 e ANOTE o que ela fez.
7. Leia o selo do P3: ele tem de passar a dizer MUDO.
8. Confira, falando perto do P3 outra vez, que a barrinha parou de mexer.
9. Confira, abrindo o cartão de cada um, que os selos do P1, do P2 e do P4 não mudaram.
10. Desligue o P3 segurando o botão PS até TODAS as luzes dele apagarem.
11. Religue o P3 segurando o botão PS por cerca de cinco segundos, até a barra de luz acender.
12. Clique na linha do P3 para reabrir o cartão dele.
13. Leia o selo do Microfone do P3 e ANOTE o que ele diz agora — esta é a entrega do teste.
14. Veja a luz vermelha do plástico do P3 e anote o que ela está fazendo.
15. Clique no 🎙 do P3 até o selo voltar a dizer ATIVO.
16. Repita no P4 tudo o que você fez no P3, do "fale perto" até o selo de volta em ATIVO.
17. Feche a janela do Hefesto no X e abra-a de novo, para devolver o mudo ao botão do plástico.

**Passa quando.** No P3 e no P4 o clique no 🎙 cala aquele controle — selo em MUDO, barrinha parada, luz vermelha mudando — e os outros três não se mexem. E a entrega deste teste é o que você anotou depois da queda e da volta: o que o selo e a luz vermelha do P3 fizeram quando ele voltou.

**Por controle.**

* **P1** — No cabo, e é TESTEMUNHA. Não clique no 🎙 dele. O selo dele tem de ficar parado, inclusive durante a queda e a volta do P3.
* **P2** — No cabo, e é a segunda testemunha. Mesma conferência do P1. Se um controle do cabo emudecer junto com um do rádio, o comando pegou mais de um.
* **P3** — No rádio, e é ELE que você cala e depois desliga e religa. É aqui que o defeito conhecido do rádio aparece, e é por isso que o selo e a luz lidos DEPOIS da volta são a entrega.
* **P4** — No rádio, e faz a sequência inteira igual, inclusive a queda e a volta. Se um perder o mudo e o outro não, anote qual — é o dado que diz se a perda é do rádio ou daquele aparelho.

**A armadilha.** Este é o defeito conhecido do rádio, e ele está MEDIDO: o que segura o mudo vive no vínculo entre o Hefesto e o aparelho, e pelo rádio esse vínculo se refaz a cada reconexão — em 03/08/2026 o mudo pedido evaporou na volta e o pedido não foi junto. A cura foi PROPOSTA e não feita. Então um mudo que se desfaz sozinho depois da queda é o resultado esperado desta linha, não erro seu: anote a hora e siga. O que reprovaria de verdade é o clique não calar nada, ou calar o controle errado. Segunda: o 🎙 da tela tira o mudo do botão do plástico e não devolve — feche e reabra o Hefesto no fim, senão o próximo teste que usar o botão físico dá vermelho sobre um controle são. Terceira: para desligar, segure o PS até as luzes APAGAREM; cerca de cinco segundos é lido como toque curto e abre a Steam. Se abrir, feche-a e refaça o ato.

---

## mapa-audio.saida_dedicada-cabo — Saída de áudio dedicada · cabo

*Célula:* `audio.saida_dedicada @ cabo`

**O que isto prova.** Prova que cada controle no cabo entra no computador com uma saída de som PRÓPRIA — uma por controle, não uma para os dois.

**Onde olhar.** Na aba Sistema, na seção "O exame de hoje": a linha do áudio, que conta as saídas de som dos controles no cabo; ela é cortada na tela, então passe o mouse em cima para ler a frase inteira. Na mesma seção, a linha da regra de áudio desligado, que quando ativa mata o microfone e o fone de todos os controles do cabo. E na aba Controles, no cartão de cada controle, o rótulo do bloco Alto-falante, que ganha o sufixo "· acordado" ou "· dormindo" — esse sufixo só existe quando há saída de som daquele controle, e nos do rádio ele não aparece.

**Os passos.**

1. Confira na fita do topo que P1 e P2 dizem cabo e que P3 e P4 dizem rádio.
2. Abra o Hefesto e clique na aba Sistema.
3. Ache a seção "O exame de hoje".
4. Passe o mouse na linha do áudio e leia a frase inteira.
5. Confira que ela conta DOIS controles no cabo, e não um.
6. Passe o mouse na linha da regra de áudio desligado e leia a frase inteira, até o fim.
7. Clique na aba Controles e clique na linha do P1.
8. Leia o rótulo do bloco Alto-falante e confira que ele traz "· acordado" ou "· dormindo".
9. Clique na linha do P2 e confira o mesmo.
10. Clique na linha do P3 e confira que o rótulo NÃO traz nenhum dos dois.
11. Clique na linha do P4 e confira o mesmo.
12. Puxe o cabo de dentro do P2.
13. Volte à aba Sistema e leia a linha do áudio de novo: ela tem de passar a contar UM controle no cabo.
14. Encaixe o cabo do P2 de volta.
15. Volte à aba Sistema e confira que a linha voltou a contar dois.

**Passa quando.** A linha do áudio do exame conta exatamente quantos controles estão no cabo: dois com os dois plugados, um depois de você puxar o cabo do P2, e dois de novo quando ele volta. O rótulo do bloco Alto-falante traz o sufixo "· acordado" ou "· dormindo" no P1 e no P2, e NÃO traz nem um nem outro no P3 e no P4.

**Por controle.**

* **P1** — No cabo, e fica plugado o tempo todo. Ele é o que sobra na conta quando você puxa o cabo do P2 — se a conta continuar dizendo dois com só ele plugado, ela não está contando de verdade.
* **P2** — No cabo, e é ELE que você desplugua e replugua. Esse gesto é o coração do teste: sem puxar um cabo, uma conta certa e uma conta errada ficam idênticas na tela.
* **P3** — No rádio, e é TESTEMUNHA. Confira que o rótulo do bloco Alto-falante dele não traz sufixo nenhum, e que ele nunca entra na conta do exame.
* **P4** — No rádio, e é a segunda testemunha. Mesma conferência do P3. Se um controle do rádio aparecer na conta dos do cabo, isso é achado.

**A armadilha.** Esta linha já deu VERDE sobre um controle valendo por quatro: ela procurava a palavra do modelo no texto inteiro e um único controle respondia por todos. Hoje ela CONTA — e é exatamente por isso que o passo 12 puxa um cabo: sem puxar, uma conta errada é indistinguível de uma certa. Segunda: as frases dessa seção são CORTADAS na tela, e no caso da regra de áudio o corte INVERTE o sentido — o que sobra ao lado do selo se lê como problema, e as duas metades escondidas são justamente "estão liberados" e "o que fazer: nada". Passe sempre o mouse. Terceira: o sufixo "· acordado" faltando nos do rádio não é leitura faltando, é o produto dizendo honestamente que não sabe — no rádio o controle não publica saída de som nenhuma. E a prova desta célula parou no primeiro degrau e está marcada como parcial: o que se mediu foi o controle ANUNCIAR a saída própria, não tudo o que ela consegue fazer.

---

## mapa-audio.saida_dedicada-radio — Saída de áudio dedicada · rádio

*Célula:* `audio.saida_dedicada @ rádio`

**O que isto prova.** Prova que, pelo rádio, o Hefesto não inventa uma saída de som do controle — e diz isso com uma frase no cartão, em vez de deixar a tela muda.

**Onde olhar.** Na aba Controles, no cartão do P3 e no do P4, bloco Alto-falante: a linha de ressalva embaixo dos dois botões de rota, que tem de dizer "Pelo rádio o Hefesto ainda não faz o som sair neste alto-falante."; e o rótulo do bloco, que nos do rádio não traz "· acordado" nem "· dormindo". Na aba Sistema, seção "O exame de hoje", a linha do áudio, que só conta os controles do cabo. E o ouvido encostado nos nove furinhos da frente do controle.

**Os passos.**

1. Confira na fita do topo que P3 e P4 dizem rádio e que não há cabo plugado neles.
2. Abra o Hefesto e clique na aba Controles.
3. Clique na linha do P3 para abrir o cartão dele.
4. Leia a linha embaixo dos botões "Sons do jogo" e "Todo o som do PC" e anote a frase inteira.
5. Leia o rótulo do bloco Alto-falante e confira que ele não traz "· acordado" nem "· dormindo".
6. Arraste o volume do alto-falante do P3 até 100.
7. Clique em "Todo o som do PC" no bloco do P3.
8. Toque uma música e encoste o ouvido no P3.
9. Anote se saiu som.
10. Clique em "Sons do jogo" no bloco do P3.
11. Clique na linha do P4 e repita do passo 4 ao 10 nele.
12. Clique na linha do P1 e confira que o cartão dele NÃO tem essa linha de ressalva.
13. Encoste o ouvido no P1 e confirme que nele o som sai.
14. Clique na aba Sistema e leia a linha do áudio da seção "O exame de hoje": ela só pode contar os do CABO.

**Passa quando.** A frase de ressalva aparece nos cartões do P3 e do P4, e NÃO aparece nos do P1 e do P2. Os dois do rádio ficam mudos mesmo com o volume em 100 e com "Todo o som do PC" aceso. O P1, no cabo, toca. E a linha do áudio do exame conta só os controles do cabo.

**Por controle.**

* **P1** — No cabo, e é o CONTROLE DE COMPARAÇÃO. Nele o som tem de sair e a linha de ressalva não pode aparecer. Sem essa metade, o silêncio no P3 não prova nada — pode ser volume do sistema ou saída errada.
* **P2** — No cabo, e é testemunha. Não mexa nele. Só confira que o cartão dele também não tem a linha de ressalva do rádio.
* **P3** — No rádio, e é o primeiro que você examina. Leia a frase inteira, confira o rótulo sem sufixo, ponha o volume em 100, escute, e devolva o som às caixas no fim.
* **P4** — No rádio, e faz o mesmo. É a segunda prova do rádio: a frase tem de aparecer nele também, não só num dos dois.

**A armadilha.** O silêncio no rádio é a resposta CERTA, e a frase no cartão é a entrega deste teste — um produto calado sobre isso, com os botões acesos e nada saindo, é exatamente o que esta linha existe para impedir. E a redação da frase importa: ela diz que o HEFESTO ainda não faz, não que o controle não consegue. A dívida é nossa; o alto-falante existe e ela já o ouviu pelo cabo. Ninguém desta casa pode escrever que "descobrimos o som por Bluetooth" ou que "a ponte funciona": não há ponte, há um canal que responde — e concluir que um canal FAZ o que a gente esperava só porque ele responde é o erro que esta linha nomeia. Segunda: não confira isto com um cabo plugado no P3 "só para ver" — com o cabo ele muda de lado e a frase some, corretamente. Terceira: se um dia a ressalva sumir sozinha, isso não é defeito: a frase é lida do mapa, e no dia em que a medição virar ela desaparece sem ninguém tocar em nada.

---

# combinacao

---

## mapa-combinacao.adaptador_no_mesmo_controlador-cabo — O adaptador Bluetooth e o cabo no MESMO controlador USB · cabo

*Célula:* `combinacao.adaptador_no_mesmo_controlador @ cabo`

**O que isto prova.** Prova que ter os dois cabos plugados no mesmo lado do gabinete que o adaptador de rádio não cobra preço dos dois controles que estão no cabo.

**Onde olhar.** Na aba Conexões do Hefesto, em duas seções. Na seção «Rádio e Adaptadores» há uma tabela de três colunas — Nome, Adaptador e «Onde está». A coluna «Onde está» diz onde cada adaptador de rádio está encaixado: «Entrada 3 · traseira» quando você já desenhou a mesa, ou «Barramento 3, porta 4 · Traseira» quando não, ou ainda «Dentro da máquina» para um adaptador que é de fábrica e não sai. Abaixo dela fica a seção «Check-up», com o botão «Examinar Portas» e, entre as linhas de exame, a linha «Vizinhança das portas». A fonte não diz onde a tela mostra em qual controlador USB cada coisa pendura — esse campo não existe. O «Vizinhança das portas» mede entradas COLADAS uma na outra, que é parecido e não é a mesma coisa. Quem responde de verdade este teste são os aparelhos: a barra de luz do P1 e do P2 (as duas tiras ao lado do touchpad) e o tremor deles na sua mão.

**Os passos.**

1. Abra o Hefesto e clique na aba Conexões.
2. Leia a coluna «Onde está» do adaptador de rádio, na seção «Rádio e Adaptadores», e anote num papel o que ela diz.
3. Clique no botão «Examinar Portas», na seção «Check-up».
4. Leia a linha «Vizinhança das portas» e anote a frase inteira.
5. Passe as duas pontas dos cabos para as entradas mais próximas do adaptador de rádio, sem tirá-las dos controles — se houver duas entradas coladas nele, use essas.
6. Confira na fita do topo que os quatro chips voltaram e que o P1 e o P2 dizem cabo.
7. Clique em «Examinar Portas» de novo.
8. Compare a linha «Vizinhança das portas» com a frase que você anotou e repare se ela mudou.
9. Na aba Iluminação, clique numa cor bem viva na linha «Cor» da coluna do P1 e numa cor bem diferente na do P2.
10. Veja as duas barras de luz nos aparelhos: cada uma tem de acender na cor escolhida, na hora do clique.
11. Na aba Vibração, segure o P1 e o P2, um em cada mão, e clique em «Testar» nas duas colunas.
12. Confira que os dois tremeram na sua mão.
13. De volta à aba Iluminação, clique em cores novas nas colunas do P1 e do P2, alternando, dez vezes seguidas, o mais rápido que você conseguir.
14. Veja as duas barras durante essa rajada e anote todo clique que não acendeu, e toda cor que demorou a chegar.
15. Passe as duas pontas dos cabos para as entradas do outro lado do gabinete, o mais longe do adaptador que der.
16. Refaça os atos 4, 5 e 6 com os cabos na posição nova.
17. Compare no papel as duas rodadas, lado a lado: cabos perto do adaptador e cabos longe dele.

**Passa quando.** Nas duas posições dos cabos, o P1 e o P2 obedeceram do mesmo jeito: cada cor acendeu na hora do clique, nenhum clique da rajada foi engolido, e os dois tremeram no «Testar». Se eles falharam com os cabos perto do adaptador e pararam de falhar com os cabos longe, o teste não reprovou o produto — ele achou o preço da posição, e esse achado vale mais que o verde.

**Por controle.**

* **P1** — No cabo, e é um dos dois que têm de responder. Pinte a barra de luz dele nas duas posições de cabo e sinta o «Testar» na mão. Ele é a vítima possível deste lado: se alguma cor não chegou, anote a posição do cabo dele.
* **P2** — No cabo, o outro que tem de responder. Mesmos gestos do P1, com uma cor bem diferente da dele para você não confundir as duas barras. Se só um dos dois falhar, anote qual — pode ser a entrada, e não o lado.
* **P3** — No rádio, e é testemunha e carga ao mesmo tempo. Não toque nele: ele fica ligado do começo ao fim, ocupando o adaptador enquanto os dois do cabo são medidos. Se a barra dele acender junto com a do P1, o comando pegou mais gente do que devia.
* **P4** — No rádio, a segunda testemunha. Não toque nele. Ele e o P3 juntos são o que faz este teste ser sobre companhia: sem os dois no ar, os dois do cabo estariam sozinhos e o teste não mediria nada.

**A armadilha.** Três coisas fazem você julgar errado aqui. A primeira é a palavra do mapa: nesta linha está escrito que o dano NÃO foi acionado, e isso não quer dizer que a topologia não exista — ela existe e foi medida, o adaptador de rádio e os dois cabos penduram no mesmo controlador da máquina. É justamente esse arranjo o suspeito do defeito antigo em que um controle do cabo matava a saída do controle do rádio. A segunda é o Check-up: a linha «Vizinhança das portas» olha entradas COLADAS uma na outra, e verde ali não diz que as coisas não dividem o mesmo controlador — a tela não tem campo que diga isso, e não adianta procurar. A terceira é o tamanho da carga: a única medição que existe carregou o controlador com CAPTURA DE MICROFONE, não com o vaivém de comandos de um jogo a plena carga; verde sob carga leve não é verde sempre. E a prova desta linha parou no fio: ninguém mediu com o adaptador mudado de lugar, e ninguém mediu com os comandos a plena carga. Por último: se a coluna «Onde está» disser «Dentro da máquina», aquele adaptador não sai da posição, e este teste roda só mexendo nos cabos.

---

## mapa-combinacao.adaptador_no_mesmo_controlador-radio — O adaptador Bluetooth e o cabo no MESMO controlador USB · rádio

*Célula:* `combinacao.adaptador_no_mesmo_controlador @ rádio`

**O que isto prova.** Prova que os dois controles do rádio continuam obedecendo mesmo com os dois cabos trabalhando ao lado, e diz se mudar o adaptador de lugar muda a resposta.

**Onde olhar.** Na aba Conexões, seção «Rádio e Adaptadores»: a tabela de três colunas — Nome, Adaptador e «Onde está» —, onde a última diz onde cada adaptador está encaixado («Entrada 3 · traseira», ou «Barramento 3, porta 4 · Traseira», ou «Dentro da máquina»). Na mesma aba, a seção «Check-up», com o botão «Examinar Portas» e a linha «Vizinhança das portas». Se houver mais de um adaptador na tabela, a fonte não diz por qual deles cada controle do rádio está falando — por isso a primeira coisa a fazer é copiar a tabela inteira antes de mexer em qualquer coisa. Quem responde este teste são os aparelhos: as barras de luz do P3 e do P4 e o tremor deles na sua mão.

**Os passos.**

1. Abra o Hefesto e clique na aba Conexões.
2. Leia a seção «Rádio e Adaptadores» e copie num papel a tabela inteira: o nome, o adaptador e o «Onde está» de cada linha.
3. Confira na fita do topo que o P3 e o P4 dizem rádio.
4. Clique em «Examinar Portas».
5. Leia a linha «Vizinhança das portas» e copie a frase dela no mesmo papel.
6. Encaixe as duas pontas dos cabos nas entradas mais próximas do adaptador de rádio.
7. Na aba Iluminação, pinte uma cor bem viva na coluna do P3 e uma bem diferente na do P4.
8. Veja a barra de luz de cada um acender na cor clicada, no ato do clique.
9. Pinte cores novas nas colunas do P1 e do P2, alternando, quinze vezes seguidas, o mais rápido que você conseguir — é isto que põe o lado do cabo para trabalhar.
10. Sem parar o ritmo, pinte uma cor nova na coluna do P3 e outra na do P4.
11. Veja as duas barras e anote toda cor que demorou a chegar, ou que não chegou.
12. Na aba Vibração, clique em «Testar» na coluna do P3 e depois na do P4, com cada um na mão.
13. Desencaixe o adaptador de rádio, encaixe-o numa entrada do outro lado do gabinete e traga o P3 e o P4 de volta com um toque curto no PS de cada um.
14. Confira, na aba Conexões, que a coluna «Onde está» daquele adaptador mudou, e que os dois chips voltaram à fita dizendo rádio.
15. Refaça os atos 3 a 6 com o adaptador na entrada nova, e escreva as duas rodadas lado a lado.

**Passa quando.** Nas duas posições do adaptador, o P3 e o P4 obedeceram: cada cor acendeu na hora do clique, mesmo com o P1 e o P2 sendo pintados sem parar, e os dois tremeram no «Testar». Se eles falharam com o adaptador do lado dos cabos e pararam de falhar com ele do outro lado, isso é ACHADO — é exatamente a medição que ninguém nunca fez nesta casa, e ela vale mais que um verde.

**Por controle.**

* **P1** — No cabo, e aqui ele não é o medido: ele é a CARGA. Não olhe a barra dele para julgar. O papel dele é receber quinze cores em sequência enquanto você olha os dois do rádio.
* **P2** — No cabo, a segunda metade da carga. Mesmo papel do P1: recebe cor atrás de cor. Os dois juntos são o que faz o controlador da máquina trabalhar, que é o mecanismo suspeito.
* **P3** — No rádio, e é a vítima possível — é ele que este lado do teste mede. A cor tem de acender no ato e o tremor tem de vir, com os dois do cabo em rajada ao lado. Se falhar, anote em qual posição do adaptador foi.
* **P4** — No rádio, a segunda vítima possível. Mesmos gestos do P3, com cor bem diferente. Se um dos dois do rádio falhar e o outro não, anote qual — a diferença entre os dois aparelhos do mesmo lado já apareceu em medição antes, e é dado, não ruído.

**A armadilha.** Este teste tem DEZ atos, acima dos oito do alvo de propósito, e o motivo é a pergunta: ela é a COMPARAÇÃO de duas posições do adaptador, então a rodada dos atos 3 a 6 é feita duas vezes, uma de cada lado do gabinete. Cortar uma das rodadas apaga a pergunta inteira. Desencaixar o adaptador DERRUBA o P3 e o P4 — isso é o esperado, não é o defeito; traga cada um de volta com um toque no PS. Se a tabela tiver mais de um adaptador, os dois podem voltar por OUTRO adaptador, e aí você mediu a entrada errada: releia a coluna «Onde está» e o nome de cada linha antes de concluir. Um adaptador que diz «Dentro da máquina» não sai do lugar — com ele, este teste roda só mudando os cabos de entrada. E o que está escrito no mapa desta linha é que o dano NÃO foi acionado, o que é diferente de «isto não existe»: a topologia existe e foi medida, o adaptador e os dois cabos penduram no mesmo controlador da máquina. A única carga que já se experimentou foi captura de microfone, não o vaivém de comandos de um jogo, e a prova parou no fio: nada nesta linha diz o que o jogo recebeu. Por fim, o Check-up mede entradas COLADAS, e não controlador compartilhado — verde nele não fecha esta pergunta, e é por isso que a frase da «Vizinhança das portas» é anotada como contexto e não como veredito.

---

## mapa-combinacao.cabo_e_radio.entrada-cabo — Dois na mesa (um no cabo, um no rádio) — a ENTRADA de cada um continua chegando? · cabo

*Célula:* `combinacao.cabo_e_radio.entrada @ cabo`

**O que isto prova.** Prova que tudo o que você faz nos dois controles do cabo continua chegando na tela mesmo com dois controles no rádio ligados ao lado.

**Onde olhar.** Na aba Controles do Hefesto. Cada controle tem uma linha; clicar numa linha abre o cartão daquele controle e fecha os outros. Para ter os quatro cartões abertos ao mesmo tempo, clique no chip «Todos» na fita do topo. Dentro do cartão ficam: os dois analógicos desenhados, cada um com um pontinho que anda quando você mexe no do aparelho; os desenhos dos botões, que acendem quando você aperta; o touchpad, que mostra o ponto onde o seu dedo está e o número do toque; e as molduras Giroscópio e Acelerômetro, com os três eixos em números que mudam quando você mexe o controle no ar.

**Os passos.**

1. Abra a aba Controles.
2. Confira na fita do topo que há quatro chips e que o P1 e o P2 dizem cabo.
3. Clique na linha do P1 para abrir o cartão dele.
4. Empurre os dois analógicos do P1 até o fim para cada lado e solte-os.
5. Veja os dois pontinhos andarem junto com os analógicos e voltarem ao centro quando você solta.
6. Aperte, um de cada vez, o Triângulo, o Círculo, o Quadrado, a Cruz e as quatro direções do direcional do P1.
7. Veja cada desenho acender no aperto.
8. Arraste o dedo devagar pelo touchpad do P1.
9. Veja o ponto seguir o dedo, com o número do toque ao lado.
10. Gire e incline o P1 na mão.
11. Veja mexerem os três números do Giroscópio e os três do Acelerômetro.
12. Repita no P2 tudo o que você fez no P1, começando por abrir o cartão dele.
13. Clique na linha do P1 para deixar aberto só o cartão dele.
14. Ponha o P1 numa mão e o P3 na outra e mexa os dois analógicos esquerdos ao mesmo tempo, em círculos, sem parar, contando até vinte.
15. Veja o cartão do P1 enquanto faz isso: o pontinho não pode travar, parar nem saltar.
16. Solte os dois controles.
17. Confira que o pontinho do P1 volta ao centro.
18. Refaça essa mesma dupla com o cartão do P2 aberto, o P2 numa mão e o P4 na outra.
19. Compare a resposta do P1 com a do P2 e escreva as duas, uma embaixo da outra.

**Passa quando.** Com os quatro controles ligados, tudo o que você fez no P1 e no P2 apareceu no cartão de cada um: o pontinho de cada analógico andou e voltou ao centro, cada botão apertado acendeu, o ponto do touchpad seguiu o dedo, e os números dos dois sensores mexeram. E nada disso travou nem atrasou enquanto um controle do rádio era mexido junto, com uma mão em cada.

**Por controle.**

* **P1** — No cabo, e é um dos dois que têm de responder. Faça nele a volta inteira: os dois analógicos, os quatro botões da face, as quatro direções do direcional, o touchpad, o giroscópio e o acelerômetro.
* **P2** — No cabo, o outro que tem de responder. Mesma volta inteira. Se um dos dois responder e o outro não, anote qual — e confira se o cabo dele está bem encaixado nas duas pontas antes de reprovar.
* **P3** — No rádio, e é testemunha e carga. Fica ligado o tempo todo, e na segunda metade você o mexe junto com o P1 — não para medir o P3, mas para ocupar o rádio enquanto o cabo é lido.
* **P4** — No rádio, a segunda testemunha. Fica ligado, e entra na segunda metade junto com o P2. Se o cartão do P2 engasgar só quando você mexe no P4, anote isso: é o rádio atrapalhando o cabo, que é justamente o que esta linha existe para pegar.

**A armadilha.** Um controle do rádio que não mostra movimento nem toque de touchpad no cartão pode não estar quebrado: pelo rádio o DualSense começa mudo dessas duas coisas e só passa a mandá-las depois que o Hefesto escreve nele UMA vez — e um controle já acordado não acorda o vizinho. Se o cartão do P3 ou do P4 estiver sem giroscópio e sem touchpad, clique numa cor na coluna daquele controle na aba Iluminação e tente de novo. Segunda: a medição que existe foi feita com os quatro PARADOS na mesa, ninguém apertou nada — o que este teste faz, que é apertar e mexer com companhia, nunca foi medido, então tudo o que você achar aqui é notícia nova. Terceira: a prova desta linha parou no fio; ver o número mexer no cartão não diz que o JOGO recebeu. Quarta: os cartões são um de cada vez — clicar num fecha o outro. Use o chip «Todos» da fita se quiser os quatro abertos, e lembre que com um controle só na mesa esse chip nem aparece. E este teste é longo de propósito: são DEZ atos porque ele varre as seis famílias de entrada — os dois analógicos, os quatro botões da face, as quatro direções do direcional, o touchpad, o giroscópio e o acelerômetro — em DOIS controles do cabo, e ainda mede os dois sob a carga do rádio. Cada família é um ato separado com a olhada colada nela; juntá-las numa bolinha só é o que faz alguém varrer tudo de uma vez e não saber depois QUAL delas falhou.

---

## mapa-combinacao.cabo_e_radio.entrada-radio — Dois na mesa (um no cabo, um no rádio) — a ENTRADA de cada um continua chegando? · rádio

*Célula:* `combinacao.cabo_e_radio.entrada @ rádio`

**O que isto prova.** Prova que tudo o que você faz nos dois controles do rádio continua chegando na tela mesmo com dois controles no cabo trabalhando ao lado.

**Onde olhar.** Na aba Controles do Hefesto. Cada controle tem uma linha; clicar numa linha abre o cartão daquele controle e fecha os outros, e o chip «Todos» da fita do topo abre os quatro de uma vez. Dentro do cartão: os dois analógicos desenhados, cada um com um pontinho que anda; os desenhos dos botões, que acendem ao aperto; o touchpad, que mostra o ponto do dedo com o número do toque; e as molduras Giroscópio e Acelerômetro, com os três eixos em números.

**Os passos.**

1. Abra a aba Controles.
2. Confira na fita do topo que há quatro chips e que o P3 e o P4 dizem rádio.
3. Passe pela aba Iluminação e pinte uma cor na coluna do P3 e outra na do P4 — pelo rádio o movimento e o touchpad só acordam depois que o Hefesto escreve no controle uma vez.
4. Volte à aba Controles e clique na linha do P3 para abrir o cartão dele.
5. Mexa os dois analógicos do P3 até o fim para cada lado e solte-os.
6. Veja os dois pontinhos andarem junto com os analógicos e voltarem ao centro quando você solta.
7. Aperte, um de cada vez, o Triângulo, o Círculo, o Quadrado, a Cruz e as quatro direções do direcional do P3.
8. Veja cada desenho acender no aperto.
9. Arraste o dedo devagar pelo touchpad do P3.
10. Veja o ponto seguir o dedo, com o número do toque ao lado.
11. Gire e incline o P3 na mão.
12. Veja mexerem os três números do Giroscópio e os três do Acelerômetro.
13. Repita no P4 tudo o que você fez no P3, começando por abrir o cartão dele.
14. Com o cartão do P3 aberto, ponha o P3 numa mão e o P1 na outra e gire os dois analógicos esquerdos em círculos, sem parar, contando até vinte.
15. Veja o pontinho do P3: ele não pode travar, parar nem saltar enquanto o controle do cabo é mexido junto.
16. Confira que os dois pontinhos do P3 voltam ao centro quando você solta os analógicos.
17. Repita essa volta de vinte com o cartão do P4 aberto, o P4 numa mão e o P2 na outra.
18. Compare a resposta do P3 com a do P4 e escreva as duas, uma embaixo da outra.

**Passa quando.** Com os quatro ligados, tudo o que você fez no P3 e no P4 apareceu no cartão de cada um: o pontinho de cada analógico andou e voltou ao centro, cada botão acendeu, o ponto do touchpad seguiu o dedo, e os números dos dois sensores mexeram. E nada travou nem atrasou enquanto um controle do cabo era mexido junto.

**Por controle.**

* **P1** — No cabo, e aqui ele é testemunha e carga. Não o meça: ele fica ligado e, na volta de vinte, é mexido junto com o P3 só para ocupar o cabo enquanto o rádio é lido.
* **P2** — No cabo, a segunda testemunha. Fica ligado, e entra na volta de vinte junto com o P4. Se o cartão do P4 só engasgar quando você mexe no P2, anote — é o cabo atrapalhando o rádio, e é o defeito que esta família nasceu para pegar.
* **P3** — No rádio, e é um dos dois que têm de responder. Faça nele a volta inteira. Antes disso, pinte uma cor na coluna dele: pelo rádio o movimento e o touchpad só começam depois que o Hefesto escreve nele uma vez.
* **P4** — No rádio, o outro que tem de responder. Mesma volta inteira, e a mesma cor antes. Se ele mostrar analógico e botões mas não mostrar giroscópio nem touchpad, é a cor que faltou nele — o P3 estar acordado não acorda o P4.

**A armadilha.** A maior armadilha deste teste é o silêncio que parece defeito: pelo rádio o DualSense começa mandando o mínimo, sem movimento e sem touchpad, e só passa a mandar essas duas coisas depois que o Hefesto escreve nele uma vez. Um controle acordado NÃO acorda o vizinho — é por isso que a pintura da cor vem antes de tudo, nos dois. Sem esse ato você reprova um produto são. Segunda: a medição que existe foi feita com os quatro PARADOS na mesa, ninguém apertou nada — apertar e mexer com companhia é exatamente a metade que continua aberta, então o que você achar aqui é notícia nova. Terceira: a prova parou no fio; ver o número mexer no cartão não diz que o JOGO recebeu. Quarta: pelo rádio, um quadro que chega errado é jogado fora inteiro e não vira evento nenhum — quando um aperto some, ele some em silêncio, sem aviso na tela, e é assim mesmo que este defeito se apresenta. E este teste é longo de propósito: são NOVE atos porque ele varre as seis famílias de entrada (dois analógicos, botões, direcional, touchpad, giroscópio e acelerômetro) em DOIS controles, e ainda mede os dois sob carga. Cortar qualquer uma delas deixaria de fora justamente a família que poderia estar falhando.

---

## mapa-combinacao.cabo_e_radio.saida-cabo — Dois na mesa (um no cabo, um no rádio) — a SAÍDA de cada um sobrevive? · cabo

*Célula:* `combinacao.cabo_e_radio.saida @ cabo`

**O que isto prova.** Prova que os comandos que o Hefesto manda para os dois controles do cabo chegam mesmo quando ele está mandando comando para os dois do rádio ao mesmo tempo.

**Onde olhar.** Nos aparelhos, e não na tela: a barra de luz do P1 e do P2 — as duas tiras acesas dos lados do touchpad — e o tremor deles na sua mão. Na tela, os gestos ficam na aba Iluminação (cada controle tem uma coluna; a linha «Cor» tem oito bolinhas de cor, e na faixa do título da aba está o botão «Todos no automático», que escreve nos quatro de uma vez) e na aba Vibração (cada controle tem uma coluna, com a linha «Testar agora» e os botões «Testar» e «Parar»). A tela mostra a cor que o Hefesto PEDIU; quem responde é a faixa acesa no plástico. Tenha papel e caneta à mão: o resultado deste teste é a lista dos cliques que não acenderam.

**Os passos.**

1. Abra a aba Iluminação.
2. Confira na fita do topo que há quatro chips: P1 e P2 dizendo cabo, P3 e P4 dizendo rádio.
3. Repare na barra de luz dos quatro aparelhos e anote num papel a cor de cada uma.
4. Clique numa cor bem viva na linha «Cor» de cada uma das quatro colunas, uma coluna de cada vez, com uma cor diferente em cada.
5. Confira, a cada clique, que a barra daquele controle acendeu na cor escolhida.
6. Veja os quatro juntos: quatro barras acesas, quatro cores diferentes, ao mesmo tempo.
7. Clique em «Todos no automático», na faixa do título da aba — é um clique só que escreve nos quatro.
8. Confira que as quatro barras trocam para a cor do número de cada controle.
9. Clique em cores novas nas quatro colunas, uma atrás da outra, o mais rápido que der, e repita a volta três vezes.
10. Repare nas barras do P1 e do P2 durante essa rajada e anote todo clique que não acendeu.
11. Abra a aba Vibração.
12. Segure o P1 e o P2, um em cada mão, e clique em «Testar» na coluna de cada um.
13. Clique em «Testar» na coluna do P3 e na do P4, com os dois largados na mesa, para o rádio trabalhar junto.
14. Volte à Iluminação, refaça a rajada e, no meio dela, clique em «Testar» no P1 e no P2 outra vez.
15. Confira se algum comando do P1 ou do P2 não chegou, e anote o que estava acontecendo no rádio naquele instante.

**Passa quando.** O P1 e o P2 — os dois do cabo — obedeceram a todos os comandos, com o P3 e o P4 recebendo comando ao mesmo tempo: cada cor acendeu no ato, o «Todos no automático» trocou os dois, nenhum clique da rajada foi engolido, e os dois tremeram no «Testar». Se um comando do P1 ou do P2 não chegou, o achado é esse, e anote qual comando era e o que o rádio estava fazendo na hora.

**Por controle.**

* **P1** — No cabo, e é uma das duas vítimas possíveis deste lado. Recebe cor própria, recebe o «Todos no automático», entra na rajada e treme no «Testar», com você segurando-o na mão.
* **P2** — No cabo, a outra vítima possível. Mesmos comandos, com uma cor bem diferente da do P1 para as duas barras não se confundirem. Se só um dos dois falhar, anote qual e em que entrada ele está.
* **P3** — No rádio, e aqui ele é carga: recebe cor na rajada e recebe «Testar» para o rádio estar trabalhando enquanto o cabo é medido. Deixe-o na mesa; você não precisa senti-lo.
* **P4** — No rádio, a segunda carga. Mesmo papel do P3. Os dois no ar recebendo comando é o que faz este teste ser sobre companhia — sem eles, o P1 e o P2 estariam sozinhos e nada seria medido.

**A armadilha.** Feche a Steam antes de começar: com ela aberta, quem escreve por último na luz ganha, e ela escreve direto no aparelho — a barra pode voltar sozinha e você reprova um produto são. O «Testar» dura meio segundo: com o controle largado na mesa dá para não sentir e anotar «não tremeu» sobre um controle que obedeceu — segure na mão os dois que você está medindo. Este teste é com a mesa CHEIA, quatro controles: a peça do Hefesto que divide o esforço entre os controles muda de conta conforme quantos estão ligados, então uma rodada com três não se compara com uma rodada com quatro. E lembre de onde este teste vem: o defeito antigo era um controle NO CABO matando a saída do controle NO RÁDIO — a vítima esperada é a do outro lado. Verde aqui é o resultado previsto e não fecha a pergunta; quem fecha é a rodada do rádio. Por último, a tela mostra a cor que o Hefesto pediu, não a que acendeu: julgue pela faixa acesa no plástico, sempre.

---

## mapa-combinacao.cabo_e_radio.saida-radio — Dois na mesa (um no cabo, um no rádio) — a SAÍDA de cada um sobrevive? · rádio

*Célula:* `combinacao.cabo_e_radio.saida @ rádio`

**O que isto prova.** Prova que os comandos do Hefesto chegam aos dois controles do rádio mesmo quando ele está mandando comando para os dois do cabo ao mesmo tempo — que é exatamente onde o defeito antigo aparecia.

**Onde olhar.** Nos aparelhos: a barra de luz do P3 e do P4 — as duas tiras acesas dos lados do touchpad — e o tremor deles na sua mão. Na tela, os gestos ficam na aba Iluminação (cada controle tem uma coluna; a linha «Cor» tem oito bolinhas, e na faixa do título há o botão «Todos no automático», que escreve nos quatro de uma vez) e na aba Vibração (uma coluna por controle, com a linha «Testar agora» e os botões «Testar» e «Parar»). A tela mostra a cor PEDIDA; quem responde é a faixa acesa no plástico.

**Os passos.**

1. Abra a aba Iluminação.
2. Confira na fita do topo que há quatro chips: P1 e P2 dizendo cabo, P3 e P4 dizendo rádio.
3. Veja os quatro aparelhos e anote num papel a cor da barra de luz de cada um, antes de mexer em qualquer coisa.
4. Pinte uma cor diferente em cada uma das quatro colunas, começando pela do P3 e pela do P4.
5. Veja cada barra acender na cor clicada, no ato do clique.
6. Veja os quatro juntos: quatro barras acesas, quatro cores diferentes, ao mesmo tempo.
7. Clique em «Todos no automático», na faixa do título da aba — é um clique só que escreve nos quatro.
8. Veja as quatro barras trocarem para a cor do número de cada controle.
9. Pinte cores novas nas quatro colunas, uma atrás da outra, o mais rápido que der, e repita a volta três vezes.
10. Veja as barras do P3 e do P4 durante essa rajada e anote todo clique que não acendeu, e toda cor que chegou atrasada.
11. Na aba Vibração, clique em «Testar» na coluna do P3 e depois na do P4, com cada um na mão.
12. Volte à Iluminação e comece uma rajada só nas colunas do P1 e do P2, sem parar, contando até quinze.
13. Sem parar a rajada, pinte uma cor nova na coluna do P3 e outra na do P4.
14. Veja a barra de cada um e anote toda cor que não chegou, ou que chegou atrasada.
15. Volte à Vibração e clique em «Testar» no P3 e depois no P4, com cada um na mão.

**Passa quando.** O P3 e o P4 — os dois do rádio — obedeceram a todos os comandos, inclusive durante a rajada em que o P1 e o P2 estavam sendo pintados sem parar: cada cor acendeu no ato, o «Todos no automático» trocou os dois, e os dois tremeram no «Testar», nas duas voltas. Se uma cor do P3 ou do P4 sumiu, ou se o tremor não veio, o achado é esse — anote se aconteceu com o cabo em rajada ou com o cabo parado, porque essa é a diferença que interessa.

**Por controle.**

* **P1** — No cabo, e aqui ele é a CARGA. Não o meça. O papel dele é receber cor atrás de cor durante a rajada, para o cabo estar ocupado enquanto o rádio é medido.
* **P2** — No cabo, a segunda metade da carga. Mesmo papel do P1. Os dois juntos é que reproduzem a situação em que o defeito antigo apareceu.
* **P3** — No rádio, e é a vítima principal deste teste — foi um controle no rádio que ficou mudo, no defeito antigo. Cor no ato, tremor no «Testar», com o cabo em rajada ao lado.
* **P4** — No rádio, a segunda vítima possível. Mesmos comandos, cor bem diferente. Se um dos dois do rádio falhar e o outro não, anote qual: dois aparelhos do mesmo lado já foram medidos respondendo bem diferente um do outro, e isso é dado, não ruído.

**A armadilha.** A Steam tem de estar fechada antes de o teste começar: com ela aberta, quem escreve por último na luz ganha, e a Steam escreve direto no aparelho — a barra volta sozinha e você reprova um produto são. O «Testar» dura meio segundo: segure na mão o controle que está sendo medido, senão você anota «não tremeu» sobre um controle que obedeceu. Faça este teste com a mesa CHEIA: a peça do Hefesto que divide o esforço entre os controles muda de conta conforme quantos estão ligados, e uma rodada com três não se compara com uma com quatro. Não julgue pela tela: ela mostra a cor que o Hefesto pediu, não a que acendeu no plástico. E saiba o peso do que você está fazendo: este é o lado do defeito de origem desta família — vermelho aqui é o achado mais valioso deste roteiro, e vale anotar a hora exata e o que estava acontecendo no cabo naquele instante.

---

## mapa-combinacao.cabo_e_radio.taxa-cabo — Dois na mesa (um no cabo, um no rádio) — a TAXA de relatórios de cada um, medida junta · cabo

*Célula:* `combinacao.cabo_e_radio.taxa @ cabo`

**O que isto prova.** Prova que a leitura dos dois controles do cabo continua chegando de forma lisa, sem engasgo, com dois controles no rádio ligados e sendo mexidos ao lado.

**Onde olhar.** Na aba Controles, dentro do cartão de cada controle. Duas coisas: os três números do Giroscópio, que mudam quando você gira o controle no ar, e o pontinho de cada analógico, que anda quando você mexe. Há também, dentro do cartão, uma linha discreta que começa com «Giroscópio:» e que, quando aparece, traz um número por segundo — algo como «Giroscópio: fluindo para o jogo (~250 Hz)». Ela só aparece no cartão do controle cujo movimento está sendo espelhado para o jogo; nos outros cartões ela simplesmente não existe, e isso não é defeito. A fonte não diz onde se lê, nesta tela, a quantidade de leituras que o controle entrega no fio: esse campo não existe em lugar nenhum do produto.

**Os passos.**

1. Abra a aba Controles.
2. Confira na fita do topo que há quatro chips e que o P1 e o P2 dizem cabo.
3. Clique na linha do P1 para abrir o cartão dele.
4. Leia dentro do cartão a linha que começa com «Giroscópio:»: se ela trouxer um número, anote o número; se ela não aparecer, escreva «não apareceu».
5. Gire o P1 na mão devagar, para um lado e para o outro, contando até vinte.
6. Veja os três números do Giroscópio durante esse tempo: eles têm de mudar de forma corrida, sem travar e sem pular.
7. Confira que, quando você para de girar, os números voltam a ficar quase parados.
8. Empurre o analógico esquerdo do P1 em círculos, contando até vinte.
9. Veja o pontinho fazer o mesmo círculo, sem saltar.
10. Refaça os atos 1, 2 e 3 com o P2.
11. Clique na linha do P1 para abrir o cartão dele de novo.
12. Gire o P1 numa mão e o P3 na outra ao mesmo tempo, sem parar, contando até trinta.
13. Veja os números do Giroscópio do P1 durante esse tempo e anote todo engasgo, toda parada e todo salto.
14. Refaça os atos 5 e 6 com o cartão do P2 aberto, o P2 numa mão e o P4 na outra.
15. Compare a resposta dos dois do cabo, uma embaixo da outra: engasgou ou não engasgou.

**Passa quando.** O P1 e o P2 mostraram os números do giroscópio e o pontinho do analógico mudando de forma lisa e corrida, sem engasgo e sem salto — com os quatro controles ligados e com um controle do rádio sendo girado junto na outra mão. E, se a linha «Giroscópio:» trouxer um número, ele é parecido nos dois do cabo.

**Por controle.**

* **P1** — No cabo, e é um dos dois medidos. Gire-o e mexa o analógico dele, e depois gire-o junto com o P3, um em cada mão. É a lisura da leitura dele que responde este teste.
* **P2** — No cabo, o outro medido. Mesmos gestos, e depois em par com o P4. Se um dos dois engasgar e o outro não, anote qual e em que entrada ele está plugado.
* **P3** — No rádio, e é carga: entra na segunda metade, girado junto com o P1, só para o rádio estar ocupado enquanto o cabo é lido. Não meça o cartão dele aqui.
* **P4** — No rádio, a segunda carga. Entra girado junto com o P2. Se o P2 só engasgar quando o P4 se mexe, anote — é o rádio atrapalhando o cabo, e é o que esta família procura.

**A armadilha.** O número que aparece na tela é o TETO DO PRODUTO, não uma medição do cabo. O Hefesto limita em 250 leituras por segundo o que ele repassa ao jogo, então ler «~250» diz que o limitador está funcionando, e não que o cabo entrega 250. O que se mediu no fio — 250 cravados, iguais nos quatro aparelhos, sem se mover — não aparece em campo nenhum desta tela: a fonte não diz onde ler isso, e não adianta procurar. Segunda armadilha: a linha «Giroscópio:» só nasce no cartão do controle cujo movimento está indo para o jogo; nos outros cartões ela não aparece, e isso não é defeito. Em Modo Nativo e com a máscara de Xbox ela diz outra coisa, e também não é defeito. Terceira, e é a que mais engana: o olho é uma régua ruim para velocidade de leitura — a diferença entre 250 e 400 por segundo você não enxerga. O que o olho enxerga é ENGASGO, e é só isso que este teste pede que você anote. E a prova desta linha parou no fio: nada aqui diz o que o jogo recebeu.

---

## mapa-combinacao.cabo_e_radio.taxa-radio — Dois na mesa (um no cabo, um no rádio) — a TAXA de relatórios de cada um, medida junta · rádio

*Célula:* `combinacao.cabo_e_radio.taxa @ rádio`

**O que isto prova.** Prova se a leitura dos dois controles do rádio chega de forma lisa com dois controles no cabo ao lado — e se os dois do rádio se comportam igual entre si.

**Onde olhar.** Na aba Controles, dentro do cartão de cada controle: os três números do Giroscópio, que mudam quando você gira o controle no ar, e o pontinho de cada analógico. Há também uma linha discreta começando por «Giroscópio:» que, quando aparece, traz um número por segundo — e ela só existe no cartão do controle cujo movimento está indo para o jogo, e nos outros não, o que não é defeito. A fonte não diz onde se lê, nesta tela, a quantidade de leituras que o controle entrega no fio: esse campo não existe no produto.

**Os passos.**

1. Abra a aba Controles.
2. Confira na fita do topo que há quatro chips e que o P3 e o P4 dizem rádio.
3. Antes de qualquer outra coisa, abra a aba Iluminação e clique numa cor na coluna do P3 e numa cor na coluna do P4 — sem isso os dois podem não estar mandando movimento nenhum.
4. Clique na linha do P3 para abrir o cartão dele.
5. Leia a linha que começa com «Giroscópio:» e anote o que ela diz, com número ou sem.
6. Gire o P3 na mão devagar, para um lado e para o outro, contando até vinte.
7. Veja os três números do Giroscópio: eles têm de mudar de forma corrida, sem travar e sem pular.
8. Empurre o analógico esquerdo do P3 em círculos, contando até vinte.
9. Veja o pontinho fazer o mesmo círculo, sem saltar.
10. Clique na linha do P4 e refaça nele a mesma volta que você fez no P3.
11. Compare as duas anotações: o P3 e o P4 se comportaram igual?
12. Ponha o P3 numa mão e o P1 na outra, com só o cartão do P3 aberto, e gire os dois ao mesmo tempo, sem parar, contando até trinta.
13. Veja os números do Giroscópio do P3 e anote todo engasgo, toda parada e todo salto.
14. Refaça essa dupla com o cartão do P4 aberto, o P4 numa mão e o P2 na outra.
15. Refaça o teste inteiro uma segunda vez, a partir do cartão do P3, e compare com a primeira volta.

**Passa quando.** O P3 e o P4 mostraram os números do giroscópio e o pontinho do analógico mudando de forma lisa, sem engasgo e sem salto, com um controle do cabo sendo girado junto. E os dois do rádio se comportaram parecido entre si, nas duas voltas. Se um deles engasga e o outro não — ou se o mesmo controle engasga numa volta e não engasga na outra —, anote os dois casos: é exatamente essa diferença que este teste procura.

**Por controle.**

* **P1** — No cabo, e aqui é carga: entra na segunda metade, girado junto com o P3, só para o cabo estar ocupado enquanto o rádio é lido.
* **P2** — No cabo, a segunda carga. Entra girado junto com o P4. Se o P4 só engasgar quando o P2 se mexe, anote — é o cabo atrapalhando o rádio.
* **P3** — No rádio, e é um dos dois medidos. Pinte uma cor nele antes, gire-o, mexa o analógico dele, e depois gire-o em par com o P1. Anote a resposta dele separada da do P4.
* **P4** — No rádio, o outro medido, e ele é a metade que mais importa desta linha: o que já se mediu foi os dois aparelhos do rádio respondendo com quase o dobro de diferença um do outro, na MESMA janela e com o mesmo adaptador. Compare a resposta dele com a do P3 com atenção.

**A armadilha.** Não trate um número da tela como a velocidade do rádio. O Hefesto limita em 250 leituras por segundo o que repassa ao jogo, então o número que aparece é o teto do produto, não o que o aparelho entrega. E o que se mediu no fio é o oposto da fama: o cabo entrega sempre a mesma coisa e o rádio entrega uma FAIXA larga, instável de janela para janela e diferente entre os dois aparelhos — nada disso aparece em campo nenhum desta tela. Segunda: a desigualdade entre os dois do rádio tem um suspeito forte e ainda não fechado — pode ser o modo de LER, e não o rádio. Por isso este teste não manda você caçar defeito no aparelho quando um responde diferente do outro; manda ANOTAR, e fazer duas voltas. Terceira: um controle do rádio começa mudo de movimento até o Hefesto escrever nele uma vez, e por isso a primeira coisa a fazer é pintar uma cor nos dois na aba Iluminação; sem isso você reprova um produto são. Quarta: o olho não enxerga a diferença entre 250 e 400 leituras por segundo — o que ele enxerga é engasgo, e é só isso que se anota. E a prova desta linha parou no fio: nada aqui diz o que o jogo recebeu.

---

## mapa-combinacao.dois_no_radio.crc-radio — Dois no RÁDIO — os erros de CRC de entrada aumentam? · rádio

*Célula:* `combinacao.dois_no_radio.crc @ rádio`

**O que isto prova.** Prova que dois controles no rádio ao mesmo tempo não passam a perder pedaços da leitura em silêncio.

**Onde olhar.** A fonte não diz onde se lê isto na tela: não existe campo nenhum no Hefesto que mostre quadro perdido nem conta de erro — o contador existe por dentro do produto e ninguém o lê. Então o lugar de olhar é o EFEITO, e ele é o cartão de cada controle do rádio na aba Controles: o pontinho do analógico, os desenhos dos botões que acendem ao aperto, e os três números do Giroscópio. Pelo rádio, um pedaço de leitura que chega errado é jogado fora inteiro e não vira evento nenhum — nada aparece e nada avisa. Um aperto que não acende, um pontinho que salta, um número que trava: é assim que uma perda se apresenta.

**Os passos.**

1. Abra a aba Controles.
2. Desencaixe do PC as duas pontas dos cabos — o P1 e o P2 saem da mesa e ficam só os dois do rádio.
3. Confira na fita do topo que sobraram dois chips e que os dois dizem rádio.
4. Clique numa cor na coluna de cada um dos dois do rádio, na aba Iluminação, para acordar o movimento e o touchpad deles.
5. Volte à aba Controles e clique na linha do P3 para abrir o cartão dele.
6. Segure o P3 e mexa o analógico esquerdo em círculos, sem parar, contando até trinta.
7. Repare no pontinho do cartão durante todo esse tempo e escreva todo salto, toda parada e todo engasgo.
8. Aperte o Triângulo, o Círculo, o Quadrado e a Cruz do P3, dez vezes cada um.
9. Conte quantos desses quarenta apertos não acenderam o desenho no cartão.
10. Repita com o P4 a volta inteira do P3: abrir o cartão dele, o analógico em círculos por trinta contagens, e os quarenta apertos de botão com a mesma conta.
11. Ponha um controle em cada mão e mexa os dois analógicos ao mesmo tempo, em círculos, sem parar, contando até trinta.
12. Repare nos engasgos do cartão que estiver aberto durante esse tempo e escreva-os.
13. Encaixe as duas pontas dos cabos de volta, para a mesa voltar a ter quatro controles, e refaça a rodada inteira — cartão do P3, cartão do P4 e os dois analógicos juntos.
14. Compare as duas rodadas lado a lado: dois no rádio sozinhos, e quatro na mesa.

**Passa quando.** Nas duas rodadas, tudo o que você fez nos dois controles do rádio apareceu no cartão: nenhum aperto engolido, nenhum salto do pontinho, nenhuma parada dos números. E a rodada com quatro na mesa não ficou pior que a rodada com dois. Um aperto que não acende, ou um pontinho que salta, é pedaço de leitura perdido — e é o achado que este teste procura.

**Por controle.**

* **P1** — No cabo, e sai da mesa na primeira rodada: desencaixe o cabo dele do PC. Na segunda rodada ele volta, e o papel dele é só ocupar o cabo enquanto os dois do rádio são medidos.
* **P2** — No cabo, sai junto com o P1 na primeira rodada e volta na segunda. Mesmo papel: companhia, não medida.
* **P3** — No rádio, e é um dos dois medidos. Faça nele a volta inteira — analógico em círculos por trinta contagens e quarenta apertos de botão —, sozinho e depois em par com o P4.
* **P4** — No rádio, o outro medido, e é ele quem dá sentido à linha: a pergunta é se DOIS no rádio perdem mais que um. Faça nele a mesma volta, e depois mexa nos dois ao mesmo tempo, um em cada mão.

**A armadilha.** Não existe verde de verdade neste teste, e é honesto dizer: a tela não tem campo de quadro perdido, então tudo o que você pode escrever é «não vi nada acontecer», que não é o mesmo que «nada aconteceu». A única medição que existe contou trinta e cinco mil pedaços de leitura em um minuto sem uma única falha — mas foi com os controles PARADOS na mesa, a distância de bancada e com bateria boa; ninguém variou distância, nem interferência, nem bateria baixa. Zero em um minuto não é zero sempre. Segunda: um controle do rádio que não mostra movimento nem touchpad não perdeu quadro nenhum — ele nasce mudo dessas duas coisas até o Hefesto escrever nele uma vez, e é por isso que o passo da cor na aba Iluminação pinta os dois. Terceira: com os cabos desencaixados os números de jogador podem mudar; isso é a ordem de conexão, e não é assunto deste teste — se o P3 e o P4 trocarem de número, siga os dois controles do rádio, não os rótulos. Quarta: a prova desta linha parou no fio — nada aqui diz o que o jogo recebeu. E do lado do cabo não há o que medir: o cabo não carrega esse pedaço de conferência, então não há falha que possa aumentar lá.

---

## mapa-combinacao.dois_no_radio.saida-radio — Dois no RÁDIO ao mesmo tempo — a saída de cada um sobrevive? · rádio

*Célula:* `combinacao.dois_no_radio.saida @ rádio`

**O que isto prova.** Prova que com DOIS controles no rádio e ninguém no cabo os dois continuam obedecendo aos comandos do Hefesto ao mesmo tempo.

**Onde olhar.** Nos aparelhos: a barra de luz de cada um dos dois controles do rádio — as duas tiras acesas dos lados do touchpad — e o tremor deles na sua mão. Na tela, os gestos ficam na aba Iluminação (uma coluna por controle, com a linha «Cor» de oito bolinhas, e o botão «Todos no automático» na faixa do título, que escreve em todos de uma vez) e na aba Vibração (uma coluna por controle, com a linha «Testar agora» e os botões «Testar» e «Parar»). A contagem de controles fica no alto da tela, e diz quantos são no USB e quantos no BT. A tela mostra a cor PEDIDA; quem responde é a faixa acesa no plástico.

**Os passos.**

1. Abra a aba Iluminação.
2. Desencaixe do PC as duas pontas dos cabos — só os dois do rádio ficam na mesa.
3. Confira na fita do topo que sobraram dois chips e que os dois dizem rádio.
4. Leia a contagem no alto da tela e confira que ela diz dois controles, 0 USB e 2 BT.
5. Repare na barra de luz dos dois aparelhos e anote a cor de cada uma.
6. Clique numa cor bem viva na linha «Cor» da coluna de cada um dos dois, uma cor bem diferente da outra.
7. Confira que a barra de cada um acendeu na cor que você escolheu para ele.
8. Veja os dois juntos: duas barras acesas, duas cores diferentes, ao mesmo tempo.
9. Clique em cores novas nas duas colunas, alternando, dez vezes seguidas, o mais rápido que der.
10. Repare nas duas barras durante a rajada e anote todo clique que não acendeu.
11. Clique em «Todos no automático», na faixa do título da aba.
12. Confira que as duas barras trocam para a cor do número de cada um.
13. Abra a aba Vibração.
14. Segure na mão um dos dois de cada vez e clique em «Testar» na coluna dele.
15. Ponha um controle em cada mão e clique em «Testar» nas duas colunas, uma logo depois da outra, o mais rápido que der.
16. Confira que os dois tremeram nessa sequência rápida.
17. Encaixe os cabos de volta e refaça a volta inteira com os quatro na mesa, só para comparar.

**Passa quando.** Com só os dois no rádio, os dois obedeceram a tudo ao mesmo tempo: as duas barras acenderam nas cores escolhidas, trocaram em toda a rajada sem pular clique, o «Todos no automático» pegou nas duas, e as duas tremeram no «Testar», inclusive nos dois cliques em sequência rápida. Nenhum dos dois ficou para trás.

**Por controle.**

* **P1** — No cabo, e sai da mesa: desencaixe o cabo dele do PC. Ele só volta na última rodada de comparação. Fora da medida, de propósito — esta linha pergunta pelos dois do rádio SEM ninguém no cabo.
* **P2** — No cabo, sai junto com o P1 pelo mesmo motivo, e volta junto na última rodada.
* **P3** — No rádio, e é um dos dois medidos. Recebe cor própria, entra na rajada, recebe o «Todos no automático» e treme no «Testar», com você segurando-o na mão.
* **P4** — No rádio, o outro medido, e é ele que fecha o sentido da linha: a pergunta é se DOIS no rádio cabem juntos. Mesmos comandos, cor bem diferente da do P3. Se um obedecer e o outro não, anote qual.

**A armadilha.** Feche a Steam: com ela aberta, quem escreve por último na luz ganha, e ela escreve direto no aparelho — a barra volta sozinha e você reprova um produto são. O «Testar» dura meio segundo: segure na mão o controle que está sendo medido. Saiba o peso deste teste: ele é a CONTRAPROVA do teste do cabo com rádio. Se a saída morrer aqui também, com ninguém no cabo, então a causa não é o controlador da máquina — é a fila do adaptador de rádio. Um vermelho aqui vale mais que um vermelho lá, porque ele separa duas explicações que ninguém separou ainda. Segunda: com dois controles na mesa o Hefesto divide o esforço de um jeito e com quatro de outro, então não compare a rodada de dois com a de quatro para julgar «piorou»; a última rodada é só para você ver as duas cenas, não para tirar veredito. Terceira: desencaixar os cabos muda os números de jogador dos que ficam, e isso é a ordem de conexão, não defeito. E do lado do cabo não há o que medir nesta linha: a pergunta é sobre dois no rádio, e a pergunta do fio mora no teste de um no cabo com um no rádio.

---

## mapa-combinacao.rumble_simultaneo-cabo — Rumble em dois controles ao mesmo tempo · cabo

*Célula:* `combinacao.rumble_simultaneo @ cabo`

**O que isto prova.** Prova que os dois controles do cabo tremem quando o comando de vibração sai para vários controles quase ao mesmo tempo.

**Onde olhar.** Na aba Vibração do Hefesto: cada controle tem uma coluna, com a etiqueta dele no alto, a linha «Força da vibração» com os degraus Economia, Balanceado, Máximo e Personalizado, as linhas «Motor esquerdo» e «Motor direito» com uma barra de 0 a 255, e a linha «Testar agora» com os botões «Testar» e «Parar». O tremor não aparece em campo nenhum da tela — a prova é a sua mão e o seu ouvido, e é honesto dizer isso. No aparelho, os dois motores ficam um em cada punho: o esquerdo tem o contrapeso maior e soa grosso, o direito soa fino.

**Os passos.**

1. Abra a aba Vibração.
2. Leia o degrau aceso na linha «Força da vibração» de cada uma das quatro colunas e escreva os quatro.
3. Confira que as barras «Motor esquerdo» e «Motor direito» das quatro colunas não estão em zero.
4. Ponha o P1 na sua mão esquerda e deixe o P2 na mesa, sobre uma superfície dura, sem nada por cima.
5. Clique em «Testar» na coluna do P1 e, sem parar, em «Testar» na coluna do P2.
6. Segure o P1 na mão e ponha o ouvido perto do P2, que fica na mesa — os dois têm de responder —, e escreva se algum dos dois não respondeu.
7. Troque as mãos, o P2 na mão e o P1 na mesa, e refaça a dupla de cliques na ordem invertida: «Testar» no P2 e logo depois no P1.
8. Segure o P1 na mão e escute o P2 de novo, e escreva se algum dos dois não respondeu.
9. Clique em «Testar» nas quatro colunas, uma atrás da outra, o mais rápido que der, com o P1 na mão.
10. Repare se o P1 tremeu nessa volta com os quatro sendo chamados, e escreva.
11. Repita essa volta dos quatro com o P2 na mão.
12. Repare se o P2 tremeu nela, e escreva.
13. Abra um jogo que tenha vibração, com os quatro controles dentro dele.
14. Jogue com o P1 na mão até o jogo mandar vibração.
15. Repare em como foi o tremor do P1 e escreva: veio, não veio, ou veio e morreu antes da hora.
16. Jogue com o P2 na mão até o jogo mandar vibração.
17. Repare em como foi o tremor do P2 e escreva a mesma coisa.

**Passa quando.** O P1 e o P2 tremeram todas as vezes, em qualquer ordem em que você clicou, inclusive quando os quatro foram chamados em sequência. E dentro do jogo os dois tremeram quando o jogo pediu, e o tremor durou o que tinha de durar em vez de morrer no começo. Se um dos dois não tremeu, ou se o tremor foi cortado, anote qual e em qual das duas metades — o botão «Testar» ou o jogo.

**Por controle.**

* **P1** — No cabo, e é um dos dois medidos. Segure-o na mão nas voltas em que ele é o alvo, e deixe-o sobre a mesa nas outras — na mesa o motor dele fica audível. Anote a resposta dele em cada volta.
* **P2** — No cabo, o outro medido. Mesma alternância: na mão numa volta, na mesa na outra. Se um dos dois tremer sempre e o outro só às vezes, anote qual e em que entrada o cabo dele está.
* **P3** — No rádio, e aqui ele é companhia: entra na volta em que os quatro são chamados em sequência, para o rádio estar recebendo comando junto. Deixe-o na mesa e só confirme que ele se mexeu.
* **P4** — No rádio, a segunda companhia. Mesmo papel do P3. Os dois no ar recebendo comando ao mesmo tempo é o que torna este teste sobre simultaneidade em vez de sobre um controle só.

**A espera.** O jogo pode levar minutos para chegar ao menu, e nenhum desses minutos é para ficar olhando a tela. Deixe-o carregando e vá fazer outra coisa; volte quando ouvir o som do menu. Nada do que você já mediu se desfaz por você ter saído da frente — os quatro controles continuam ligados e os degraus da «Força da vibração» continuam onde estavam. Ao voltar, comece pelo P1 na mão.

**A armadilha.** O disparo no MESMO instante saiu de instrumento, e com um par de mãos não dá para reproduzir — o que dá é um logo depois do outro, e isso já pega o defeito que interessa: o segundo não tremer. Não anote «não foi simultâneo» como reprovação. Segunda, e é a maior: as duas metades deste teste medem coisas diferentes. Pelo botão «Testar», quem manda o tremor é o próprio Hefesto, e nesse caminho os quatro já foram medidos tremendo juntos. Dentro do JOGO é outro caminho — quem manda é o jogo, e o Hefesto passa por cima escrevendo por conta própria em cima do comando dele. Isso foi medido e tem causa conhecida: o tremor de fora chega a ser apagado. Se o tremor do jogo vier fraco, cortado ou não vier, você não está errando o teste — está vendo o defeito que esta linha nomeia. Terceira: com um jogo aberto na primeira metade, um tremor no P2 pode ser do jogo e não do seu clique — por isso a bancada começa com nenhum jogo aberto, conferido na faixa do topo da página, e o jogo só entra no fim. Quarta: o «Testar» dura meio segundo; com o controle largado numa superfície mole você não vê nem ouve, e anota «nada aconteceu» sobre um produto que obedeceu. Quinta: com a barra de um motor em zero aquele punho não treme, por mais certo que esteja o resto.

---

## mapa-combinacao.rumble_simultaneo-radio — Rumble em dois controles ao mesmo tempo · rádio

*Célula:* `combinacao.rumble_simultaneo @ rádio`

**O que isto prova.** Prova que os dois controles do rádio tremem quando o comando de vibração sai para vários controles quase ao mesmo tempo.

**Onde olhar.** Na aba Vibração do Hefesto: uma coluna por controle, com a etiqueta dele no alto, a linha «Força da vibração» com os degraus Economia, Balanceado, Máximo e Personalizado, as linhas «Motor esquerdo» e «Motor direito» com uma barra de 0 a 255, e a linha «Testar agora» com os botões «Testar» e «Parar». O tremor não aparece em campo nenhum da tela — a prova é a sua mão e o seu ouvido. No aparelho, os dois motores ficam um em cada punho: o esquerdo soa grosso, o direito soa fino.

**Os passos.**

1. Abra a aba Vibração.
2. Anote qual degrau está aceso na linha «Força da vibração» de cada uma das quatro colunas.
3. Confira que as barras «Motor esquerdo» e «Motor direito» das quatro colunas não estão em zero.
4. Ponha o P3 na sua mão esquerda e deixe o P4 na mesa, sobre uma superfície dura, sem nada por cima.
5. Clique em «Testar» na coluna do P3 e, sem parar, clique em «Testar» na coluna do P4.
6. Ponha a mão no P3 e o ouvido no P4 — os dois têm de responder — e anote se algum dos dois não respondeu.
7. Troque as mãos — o P4 na mão, o P3 na mesa dura — e clique em «Testar» na coluna do P4 e, sem parar, na do P3.
8. Confira do mesmo jeito que os dois responderam com a ordem invertida, e anote se algum falhou.
9. Com o P3 na mão, clique em «Testar» nas quatro colunas, uma atrás da outra, o mais rápido que der.
10. Confira se o P3 tremeu nessa volta com os quatro sendo chamados, e anote a resposta.
11. Repita essa volta dos quatro com o P4 na mão, e anote a resposta dele.
12. Abra um jogo que tenha vibração, com os quatro controles dentro dele.
13. Jogue com o P3 na mão até o jogo mandar vibração, e depois repita com o P4 na mão.
14. Repare, em cada um, como foi o tremor: veio, não veio, ou veio e morreu antes da hora — e anote os dois.

**Passa quando.** O P3 e o P4 tremeram todas as vezes, em qualquer ordem em que você clicou, inclusive quando os quatro foram chamados em sequência. E dentro do jogo os dois tremeram quando o jogo pediu, e o tremor durou o que tinha de durar. Se um dos dois não tremeu, ou se o tremor foi cortado, anote qual e em qual das duas metades — o botão «Testar» ou o jogo.

**Por controle.**

* **P1** — No cabo, e aqui é companhia: entra na volta em que os quatro são chamados em sequência, para o cabo estar recebendo comando junto. Deixe-o na mesa e só confirme que ele se mexeu.
* **P2** — No cabo, a segunda companhia. Mesmo papel do P1. Os dois do cabo recebendo comando ao mesmo tempo é o que faz este teste medir simultaneidade, e não um controle sozinho.
* **P3** — No rádio, e é um dos dois medidos. Segure-o na mão nas voltas em que ele é o alvo e deixe-o na mesa dura nas outras. Anote a resposta dele em cada volta.
* **P4** — No rádio, o outro medido. Mesma alternância. Se um dos dois do rádio tremer sempre e o outro só às vezes, anote qual — e olhe a bateria dele na aba Controles antes de reprovar, porque bateria baixa muda o tremor.

**A espera.** O jogo pode levar minutos para chegar ao menu, e nenhum desses minutos é para ficar olhando a tela. Deixe-o carregando e vá fazer outra coisa; volte quando ouvir o som do menu. Nada do que você já mediu se desfaz por você ter saído da frente — os quatro continuam ligados e os degraus da «Força da vibração» continuam onde estavam. Ao voltar, comece pelo P3 na mão.

**A armadilha.** O disparo no MESMO instante saiu de instrumento; com um par de mãos o que dá é um logo depois do outro, e isso já pega o que interessa — o segundo não tremer. Não anote «não foi simultâneo» como reprovação. Segunda, e é a maior: as duas metades medem coisas diferentes. Pelo botão «Testar», quem manda o tremor é o próprio Hefesto, e por esse caminho os quatro já foram medidos tremendo juntos, os dois do cabo e os dois do rádio. Dentro do JOGO é outro caminho, e ali há defeito conhecido: o Hefesto escreve por cima do comando do jogo e chega a apagar o tremor de fora. Se o tremor do jogo vier fraco, cortado ou não vier, você está vendo o defeito que esta linha nomeia, e não errando o teste. Há uma exceção medida e vale saber: jogando com o Hefesto no meio, os quatro chegaram a vibrar pelo rádio sem problema — porque ali o tremor vem pelo caminho do jogo e o Hefesto é a fonte, não o concorrente. Terceira: o «Testar» dura meio segundo; numa superfície mole você não vê nem ouve. Quarta: com a barra de um motor em zero aquele punho não treme. Quinta: a primeira metade só vale com NENHUM jogo aberto — é o que a faixa da bancada garante no alto da página, e é por isso que ela está lá; com um jogo aberto, um tremor pode ser dele e não do seu clique.

## mapa-combinacao.slot_jogador.estabilidade-cabo — O número de jogador se mantém quando outro controle entra ou sai? · cabo

*Célula:* `combinacao.slot_jogador.estabilidade @ cabo`

**O que isto prova.** Prova que tirar e devolver um controle do cabo pode remexer os números de jogador, mas que os quatro voltam exatamente aos números de antes.

**Onde olhar.** Em três lugares. Na fita do topo do Hefesto, a linha que começa com «Selecionar:», onde cada controle é um chip com o número, a cor do plástico e a palavra cabo ou rádio. Na aba Conexões, seção «Gestão de Controles», onde cada linha traz «Player 1», «Player 2» e assim por diante. E nos aparelhos, a fileira de cinco lampadinhas brancas embaixo do touchpad: o número não se conta da esquerda para a direita, ele é o CONJUNTO aceso — jogador 1 é só a do meio; jogador 2 são a segunda e a quarta; jogador 3 são as duas das pontas e a do meio; jogador 4 são as quatro, com a do meio apagada.

**Os passos.**

1. Feche a Steam por inteiro.
2. Confira que os quatro estão ligados: P1 e P2 no cabo, P3 e P4 no rádio.
3. Abra o Hefesto na aba Conexões e ache a seção «Gestão de Controles».
4. Anote num papel o número de Player dos quatro, na ordem em que eles aparecem na lista.
5. Anote também o que cada chip da fita do topo mostra: o número, a cor do plástico e a palavra cabo ou rádio.
6. Olhe as cinco lampadinhas embaixo do touchpad dos quatro e confira que a figura de cada um bate com o número da tela.
7. Puxe do PC a ponta do cabo do P2 — este é o que sai, e ele está no cabo.
8. Olhe a fita imediatamente e anote o número de cada um dos três que ficaram.
9. Leia a lista da «Gestão de Controles» e anote os números dela também.
10. Olhe as lampadinhas dos três que ficaram e anote a figura de cada um.
11. Encaixe a ponta do cabo do P2 de volta, sem demorar.
12. Espere o chip dele reaparecer na fita.
13. Leia de novo os quatro números, primeiro na fita e depois na lista.
14. Olhe as lampadinhas dos quatro aparelhos.
15. Compare tudo com o que você anotou nos passos 4, 5 e 6.
16. Refaça o teste inteiro puxando o cabo do P1 em vez do do P2.

**Passa quando.** A saída de um controle do cabo pode renumerar quem ficou — isso é o combinado, a ordem é a de conexão daquele momento e não um defeito. O que tem de acontecer é a volta: quando o que saiu é devolvido, os quatro voltam exatamente aos números que você anotou no começo. Nenhum controle fica com o número de outro, nenhum número aparece repetido, nenhum some, e a figura das cinco lampadinhas concorda com a tela nos quatro aparelhos.

**Por controle.**

* **P1** — No cabo. Na primeira volta ele não se toca: anote o número dele antes, durante a ausência do P2 e depois, e escreva se ele mudou no meio. Na segunda volta é ELE que sai — puxe o cabo dele e devolva.
* **P2** — No cabo, e é o primeiro a sair. Puxe a ponta do cabo dele do PC, olhe os outros três durante a ausência e devolva o cabo sem demorar. Ele tem de voltar com o número que tinha no passo 4.
* **P3** — No rádio, e não se toca nele em volta nenhuma. É testemunha: anote o número dele antes, olhe durante a ausência do que saiu, e confira no fim. Se ele mudar de número quando alguém do CABO sai, anote — é a informação que este teste procura.
* **P4** — No rádio, e também não se toca. Segunda testemunha, e é o último da fila, o mais propenso a se mexer quando algo desmonta. Confira o número dele na tela e a figura das lampadinhas antes, durante e depois.

**A armadilha.** Renumerar NÃO é defeito, e quem não souber disso reprova um produto que está fazendo o combinado: a ordem dos números é a ordem de conexão daquele momento, por decisão sua. O que reprova é não voltar. Segunda: o lugar de quem cai fica guardado por trinta segundos, e o relógio começa quando o Hefesto percebe a queda, não quando você puxa o cabo — se você demorar mais que isso, o lugar já foi liberado e o número que voltar pode ser outro; isso é a regra funcionando, refaça mais rápido. Terceira: as cinco lampadinhas não se contam da esquerda para a direita — o número é o conjunto aceso, e quem lê «a terceira acesa» como jogador 3 reprova um produto certo. Quarta: a tela e a lâmpada têm donos diferentes. O número que o produto usa é dele e é preso ao aparelho; o número que a LÂMPADA mostra é de quem escreveu por último, e com a Steam aberta quem escreve é a Steam, com a conta dela — por isso o passo 1 fecha a Steam. Quinta: olhe os outros três DURANTE a ausência, e não só no fim; já foi medido, no cabo, um controle mudar de número enquanto o vizinho estava fora e voltar ao certo depois. Sexta: o lado do RÁDIO desta linha nunca foi medido — se você fizer o mesmo gesto desligando um controle do rádio, o que sair dali é achado novo, não repetição.

---

## mapa-combinacao.tres_na_mesa-cabo — TRÊS controles ao mesmo tempo (o caso de co-op dela) · cabo

*Célula:* `combinacao.tres_na_mesa @ cabo`

**O que isto prova.** Prova que com TRÊS controles na mesa os dois que estão no cabo continuam obedecendo e continuam sendo lidos.

**Onde olhar.** Na fita do topo, os chips de controle, cada um com o número, a cor do plástico e a palavra cabo ou rádio; e, no alto à direita, a contagem, no formato «3 controles: 2 USB · 1 BT». Na aba Iluminação, uma coluna por controle com a linha «Cor» de oito bolinhas — e a resposta é a barra de luz no aparelho, as duas tiras acesas dos lados do touchpad. Na aba Controles, o cartão de cada controle, com o pontinho de cada analógico e os desenhos dos botões que acendem ao aperto. Na aba Vibração, a coluna de cada controle com a linha «Testar agora» e os botões «Testar» e «Parar».

**Os passos.**

1. Abra a aba Iluminação.
2. Desligue o P4 segurando o botão PS dele até todas as luzes apagarem — este teste é com TRÊS na mesa.
3. Confira na fita do topo que sobraram três chips: dois dizendo cabo e um dizendo rádio.
4. Leia a contagem no alto à direita: ela tem de dizer três controles, 2 USB e 1 BT.
5. Clique numa cor bem viva na linha «Cor» da coluna do P1, numa cor bem diferente na do P2 e numa terceira na do P3.
6. Veja as três barras de luz acesas ao mesmo tempo, cada uma na sua cor.
7. Vá à aba Controles e abra o cartão do P1 clicando na linha dele.
8. Mexa os dois analógicos do P1 e aperte os quatro botões da face dele.
9. Veja cada movimento e cada aperto aparecerem no cartão.
10. Repita no P2, abrindo o cartão dele antes.
11. Vá à aba Vibração e clique em «Testar» na coluna do P1, com ele na mão.
12. Confira que ele tremeu no meio segundo do teste.
13. Clique em «Testar» na coluna do P2, com ele na mão.
14. Confira que ele tremeu também.
15. Ligue o P4 com um toque no botão PS, para a mesa ficar cheia.
16. Veja o chip dele entrar na fita e a contagem virar quatro controles.
17. Refaça as três cores e os dois «Testar» com os quatro ligados.
18. Compare as duas rodadas — três na mesa e quatro na mesa — e escreva as duas lado a lado.

**Passa quando.** Com três na mesa, o P1 e o P2 — os dois do cabo — acenderam a cor escolhida no ato, mostraram no cartão tudo o que você fez neles, e tremeram no «Testar». E nada disso piorou quando o quarto controle entrou: as mesmas cores acenderam igual e os mesmos tremores vieram igual com a mesa cheia.

**Por controle.**

* **P1** — No cabo, e é um dos dois medidos. Recebe cor própria, é lido no cartão e treme no «Testar», com três na mesa e depois com quatro.
* **P2** — No cabo, o outro medido. Mesmos gestos, com cor bem diferente da do P1. Se um dos dois responder pior quando o quarto entra, anote qual.
* **P3** — No rádio, e fica ligado o tempo todo: é ele que faz a mesa ter TRÊS em vez de dois. Recebe cor própria também, e é isso que o põe para trabalhar enquanto o cabo é medido.
* **P4** — Fica DESLIGADO na primeira metade — segure o PS dele até apagar — e entra só perto do fim. Ele é a comparação: se o P1 e o P2 respondiam bem com três e passam a falhar quando ele entra, o achado é o quarto lugar da mesa.

**A armadilha.** A medição que existe mediu PRESENÇA, não partida: os controles estavam parados na mesa, sem jogo aberto e sem ninguém apertando nada. O custo dentro de um JOGO — com a Steam aberta, com o espelho que ela faz de cada controle, e com quatro pessoas apertando ao mesmo tempo — é justamente o que continua sem medida, e é como você joga. Segunda, e é um susto conhecido: a Steam faz uma cópia de cada controle que enxerga, inclusive do controle que o próprio Hefesto cria — então três na mesa podem virar seis para o jogo. Se ao abrir um jogo aparecerem jogadores a mais, ou um jogador fantasma, isso é a Steam, não o Hefesto; por isso a bancada pede a Steam fechada por inteiro antes de começar. Terceira: desligar o P4 muda os números de jogador dos que ficam, e isso é a ordem de conexão, não defeito, e não é assunto deste teste. Quarta: o «Testar» dura meio segundo — segure na mão o controle que está sendo medido. Quinta: a prova desta linha parou no fio, então nada aqui diz o que o jogo recebeu; o que você prova aqui é que os aparelhos obedecem. E este teste é longo de propósito: são NOVE atos porque ele mede a mesma coisa DUAS vezes — com três na mesa e com quatro —, e é a comparação entre as duas rodadas que é a entrega; sem a segunda rodada não há com o que comparar.

---

## mapa-combinacao.tres_na_mesa-radio — TRÊS controles ao mesmo tempo (o caso de co-op dela) · rádio

*Célula:* `combinacao.tres_na_mesa @ rádio`

**O que isto prova.** Prova que com TRÊS controles na mesa os dois que estão no rádio continuam obedecendo e continuam sendo lidos.

**Onde olhar.** Na fita do topo, os chips de controle, cada um com o número, a cor do plástico e a palavra cabo ou rádio; e, no alto à direita, a contagem, no formato «3 controles: 1 USB · 2 BT». Na aba Iluminação, uma coluna por controle com a linha «Cor» de oito bolinhas — e a resposta é a barra de luz no aparelho, as duas tiras acesas dos lados do touchpad. Na aba Controles, o cartão de cada controle, com o pontinho de cada analógico e os desenhos dos botões que acendem ao aperto. Na aba Vibração, a coluna de cada controle com a linha «Testar agora» e os botões «Testar» e «Parar».

**Os passos.**

1. Abra a aba Iluminação.
2. Desencaixe do PC a ponta do cabo do P2 — este teste é com TRÊS na mesa, e o P2 é o que sai.
3. Confira na fita do topo que sobraram três chips: um dizendo cabo e dois dizendo rádio.
4. Leia a contagem no alto à direita e confira que ela diz três controles, 1 USB e 2 BT.
5. Clique numa cor bem viva na linha «Cor» da coluna do P3, numa cor bem diferente na coluna do P4 e numa terceira na coluna do P1.
6. Confira que a barra de luz de cada um dos três acendeu na cor que você clicou nele.
7. Veja os três juntos: três barras acesas, três cores diferentes, ao mesmo tempo.
8. Abra a aba Controles e clique na linha do P3 para abrir o cartão dele.
9. Mexa os dois analógicos do P3, aperte os quatro botões da face e arraste o dedo no touchpad; depois faça o mesmo no cartão do P4.
10. Confira que tudo o que você fez nos dois apareceu no cartão de cada um.
11. Abra a aba Vibração.
12. Segure o P3 na mão e clique em «Testar» na coluna dele; depois segure o P4 e clique no «Testar» da coluna dele.
13. Confira que cada um tremeu na sua vez.
14. Encaixe o cabo do P2 de volta, espere o chip dele entrar na fita, e refaça as três rodadas com os quatro ligados: as cores na aba Iluminação, os cartões do P3 e do P4 na aba Controles, e o «Testar» dos dois na aba Vibração.
15. Confira que a contagem no alto à direita passou a dizer quatro controles, 2 USB e 2 BT.
16. Compare as duas rodadas lado a lado: três na mesa e quatro na mesa.

**Passa quando.** Com três na mesa, o P3 e o P4 — os dois do rádio — acenderam a cor escolhida no ato, mostraram no cartão tudo o que você fez neles, e tremeram no «Testar». E nada disso piorou quando o quarto controle voltou para o cabo: as mesmas cores acenderam igual e os mesmos tremores vieram igual com a mesa cheia.

**Por controle.**

* **P1** — No cabo, e fica ligado o tempo todo: é ele que faz a mesa ter TRÊS em vez de dois, e que ocupa o cabo enquanto o rádio é medido. Recebe cor própria também.
* **P2** — Fica FORA na primeira metade — desencaixe o cabo dele do PC — e volta só no fim. Ele é a comparação: se o P3 e o P4 respondiam bem com três e passam a falhar quando ele volta, o achado é o segundo cabo entrando na conta.
* **P3** — No rádio, e é um dos dois medidos. Recebe cor própria, é lido no cartão — analógicos, botões e touchpad — e treme no «Testar», com três na mesa e depois com quatro.
* **P4** — No rádio, o outro medido. Mesmos gestos, com cor bem diferente da do P3. Se um dos dois do rádio responder pior que o outro, anote qual: dois aparelhos do mesmo lado já foram medidos respondendo bem diferente um do outro, e isso é dado, não ruído.

**A armadilha.** A medição que existe mediu PRESENÇA, não partida: os controles estavam parados na mesa, sem jogo aberto e sem ninguém apertando nada. O custo dentro de um JOGO — com a Steam aberta e quatro pessoas apertando ao mesmo tempo — é o que continua sem medida, e é como você joga. Segunda: a Steam faz uma cópia de cada controle que enxerga, inclusive do controle que o próprio Hefesto cria, então três na mesa podem virar seis para o jogo — feche-a por inteiro antes de começar; jogador a mais na tela do jogo é isso, e não defeito do Hefesto. Terceira, e é a que mais gera falso vermelho aqui: um controle do rádio começa mudo de movimento e de touchpad, e só passa a mandar essas duas coisas depois que o Hefesto escreve nele UMA vez — é por isso que a cor vem antes de abrir o cartão nos passos. Um controle acordado não acorda o vizinho, então o P3 estar bem não garante o P4. Quarta: tirar o cabo do P2 muda os números de jogador dos que ficam, e isso é a ordem de conexão, não defeito. Quinta: a prova desta linha parou no fio — o que você prova aqui é que os aparelhos obedecem, e não o que o jogo recebeu.

---

## mapa-energia.bateria.degraus-cabo — Bateria — nível em cinco degraus · cabo

*Célula:* `energia.bateria.degraus @ cabo`

**O que isto prova.** Prova que o número da bateria dos dois controles do cabo só pode ser um dos onze valores que o aparelho sabe dizer, e que ele anda de dez em dez.

**Onde olhar.** Na aba Controles do Hefesto, com os quatro cards fechados. Cada controle tem uma linha, e no fim dela vem a palavra Bateria, uma barrinha e o número em porcento. A mesma linha diz, antes disso, o número do controle, a cor do plástico e a palavra cabo ou rádio. Com os quatro cards fechados os quatro números aparecem juntos na mesma tela — e é preciso fechá-los mesmo, porque com o card aberto o P1 e o P2 somem do começo da linha e você perde de vista quem é quem.

**Os passos.**

1. Abra a janela do Hefesto.
2. Clique na aba Controles.
3. Feche os cards que estiverem abertos, clicando na linha de cada um.
4. Confira que a linha do P1 e a do P2 terminam com a palavra cabo.
5. Anote num papel o número de bateria do P1 e o do P2.
6. Anote a hora ao lado dos dois números.
7. Confira que cada um dos dois números termina em 5, ou é exatamente 100.
8. Marque um alarme de 40 minutos no celular.
9. Saia da frente da tela e faça outra coisa (o campo espera diz o quê).
10. Volte à aba Controles quando o alarme tocar.
11. Anote os dois números de novo, embaixo dos primeiros.
12. Confira que os dois números novos também terminam em 5, ou são 100.
13. Compare cada controle com ele mesmo e veja de quanto foi o pulo.
14. Confira que, onde houve pulo, ele foi de dez pontos, ou de um múltiplo de dez.

**Passa quando.** Os quatro números anotados — dois controles, duas leituras cada — são todos um destes onze: 5, 15, 25, 35, 45, 55, 65, 75, 85, 95 ou 100. Nenhum número quebrado, nada de 63% nem de 42%. E onde o número mudou, ele mudou de dez em dez, e para cima, porque os dois estão no cabo e estão carregando.

**Por controle.**

* **P1** — No cabo. Anote o número dele agora e de novo aos quarenta minutos. Os dois números têm de terminar em 5 ou ser 100, e o esperado é o segundo ser MAIOR, porque ele está carregando.
* **P2** — No cabo, igual ao P1. Mesma anotação nas duas horas, mesma regra dos onze valores. Se o P1 andar e o P2 ficar parado, anote — dois controles no mesmo cabo e no mesmo estado deveriam andar juntos.
* **P3** — No rádio, e é testemunha. Não plugue cabo nenhum nele durante os quarenta minutos. Anote o número dele nas duas leituras só para saber que ele continuou vivo; a escada dele é o outro teste.
* **P4** — No rádio, e é a segunda testemunha. Mesma coisa do P3: nada de cabo, nada de desligar. Se os dois do cabo pararem e os dois do rádio andarem, o congelamento é do cabo, e isso é o achado.

**A espera.** São quarenta minutos, e nenhum deles é para ficar olhando a tela. Depois de anotar os dois números e marcar o alarme, faça os dois testes de bateria no jogo desta mesma família — eles só olham e não desligam nada. Nesse tempo não desplugue os cabos do P1 e do P2, não desligue nenhum controle e não troque ninguém de cabo para rádio: qualquer uma dessas coisas zera o experimento. Quando o alarme tocar, volte à aba Controles e leia os dois números.

**A armadilha.** Controle já cheio no cabo fica parado em 100%, e isso NÃO é o defeito — comece o teste com o P1 e o P2 abaixo de 100%, usando-os um pouco antes ou esperando a carga cair. E saiba o que este teste NÃO prova: em 06/09 os quatro controles da mesa foram lidos no aparelho e apareceram só DOIS degraus dos onze, porque os quatro estavam no mesmo estado de carga. Dois pontos não desenham uma escada, então um verde aqui é um verde estreito. O que reprova de verdade é um número que não termina em 5 e não é 100 — 63%, por exemplo —, ou um pulo que não seja de dez em dez. Uma última coisa, para você não caçar o que não existe: o nome desta linha fala em cinco degraus, e isso veio do vocabulário de outros controles; o DualSense tem ONZE.

---

## mapa-energia.bateria.degraus-radio — Bateria — nível em cinco degraus · rádio

*Célula:* `energia.bateria.degraus @ rádio`

**O que isto prova.** Prova que o número da bateria dos dois controles do rádio desce pela mesma escada de onze valores, sem inventar número quebrado e sem congelar.

**Onde olhar.** Na aba Controles do Hefesto, com os quatro cards fechados. Cada controle tem uma linha que termina com a palavra Bateria, uma barrinha e o número em porcento; antes disso a linha diz o número do controle, a cor do plástico e a palavra cabo ou rádio. Confira a palavra rádio nas linhas do P3 e do P4 antes de anotar qualquer coisa.

**Os passos.**

1. Abra a janela do Hefesto.
2. Clique na aba Controles.
3. Feche os cards que estiverem abertos, clicando na linha de cada um.
4. Confira que a linha do P3 e a do P4 terminam com a palavra rádio.
5. Confira que não há cabo nenhum encaixado no P3 nem no P4.
6. Anote num papel o número de bateria do P3 e o do P4.
7. Anote a hora ao lado dos dois números.
8. Confira que cada um dos dois números termina em 5, ou é exatamente 100.
9. Marque um alarme de 40 minutos no celular.
10. Saia da frente da tela e faça outra coisa (o campo espera diz o quê).
11. Volte à aba Controles quando o alarme tocar.
12. Anote os dois números de novo, embaixo dos primeiros.
13. Confira que os dois números novos também terminam em 5, ou são 100.
14. Compare cada controle com ele mesmo e veja de quanto foi o pulo.
15. Confira que, onde houve pulo, ele foi de dez pontos para BAIXO, ou de um múltiplo de dez.

**Passa quando.** Os quatro números anotados — dois controles do rádio, duas leituras cada — são todos um destes onze: 5, 15, 25, 35, 45, 55, 65, 75, 85, 95 ou 100. E, onde o número mudou, ele desceu de dez em dez, porque os dois do rádio só gastam. Um número que subiu num controle sem cabo nenhum é achado, e vale anotar a hora.

**Por controle.**

* **P1** — No cabo, e é testemunha. Não desplugue. Anote o número dele nas duas leituras: ele serve para saber se o Hefesto continuou lendo alguma coisa durante os quarenta minutos.
* **P2** — No cabo, e é a segunda testemunha. Mesma anotação. Se os dois do cabo andarem e os dois do rádio ficarem parados nos mesmos números, o congelamento é do RÁDIO — e é exatamente isso que este teste procura.
* **P3** — No rádio, sem cabo nenhum. Anote agora e aos quarenta minutos. O esperado é o número CAIR, e cair de dez em dez.
* **P4** — No rádio, igual ao P3, e sem cabo nenhum. Anote nas duas horas. Se um dos dois do rádio andar e o outro não, ponha os dois números lado a lado: é a diferença entre um controle parado e a leitura do rádio parada.

**A espera.** São quarenta minutos, e nenhum deles é para ficar olhando a tela. Depois de anotar os dois números e marcar o alarme, jogue com os quatro do jeito que se joga mesmo — usar o P3 e o P4 é o que faz a carga deles descer, e é o que este teste precisa. O que não pode: encaixar cabo no P3 ou no P4, desligá-los, ou deixá-los parados a ponto de dormirem. Quando o alarme tocar, volte à aba Controles e leia os dois números.

**A armadilha.** O número não anda de um em um: ele desce de dez em dez, e em quarenta minutos um DualSense pode honestamente não ter dado um pulo. Se os dois do rádio saírem iguais, NÃO reprove — anote e volte a olhar mais tarde no dia. O que reprova é o número parado por horas, ou parado nos dois do rádio enquanto os dois do cabo andam. E há uma armadilha do lado de dentro que você não enxerga da tela: pelo rádio o Hefesto só aceita a leitura depois de conferir o quadro que o controle mandou, e o pedaço da bateria fica numa posição diferente da do cabo — se isso sair do lugar, o sintoma não é um número errado bonitinho, é um estado de carga sem sentido ou um travessão no lugar do número. Por fim, o mesmo aviso do irmão do cabo: em 06/09 os quatro controles foram lidos no aparelho e só DOIS dos onze degraus apareceram, porque os quatro estavam no mesmo estado. A escada inteira continua sem prova.

---

## mapa-energia.bateria.jogo-cabo — Bateria — espelho ao jogo (vpad) · cabo

*Célula:* `energia.bateria.jogo @ cabo`

**O que isto prova.** Prova se o número da bateria do P1 e do P2 sai do Hefesto e chega a quem os enxerga como controle de jogo.

**Onde olhar.** Começa na aba Controles: passe o mouse em cima do nome de cada card (o pedaço que diz o número, a cor do plástico e a palavra cabo) e leia a dica que aparece — ela diz qual gamepad virtual aquele controle alimenta, e é esse nome que o jogo vê. Onde um jogo mostra a bateria de um controle, A FONTE NÃO DIZ. O lugar mais próximo que existe é a lista de controles da Steam, em Configurações, e a tela de controles do próprio jogo, se ele tiver uma. Se nenhum dos dois mostrar bateria, isso é resposta e se escreve.

**Os passos.**

1. Abra a janela do Hefesto e clique na aba Controles.
2. Feche os cards que estiverem abertos.
3. Anote o número de bateria do P1 e o do P2.
4. Passe o mouse no nome do card do P1 e leia a dica que aparece.
5. Anote o nome do gamepad virtual que a dica diz para o P1.
6. Passe o mouse no nome do card do P2 e anote o nome do gamepad virtual dele.
7. Abra a Steam.
8. Abra as Configurações da Steam e vá à página de Controle, onde ela lista os controles que enxerga.
9. Procure na lista os dois nomes que você anotou.
10. Anote, para cada um dos dois, o que a lista mostra de bateria — o número, ou nada.
11. Anote também se a lista diz que ele está carregando.
12. Compare os dois números com os que você anotou no começo.
13. Escreva 'não há onde ler' se nenhuma tela fora do Hefesto mostrar bateria.

**Passa quando.** O número que aparece do lado de fora para o gamepad virtual do P1 e para o do P2 é o mesmo que o Hefesto mostra para eles, com no máximo um degrau de dez de diferença. Se não houver bateria à mostra em lugar nenhum fora do Hefesto, escreva 'não há onde ler' e siga adiante — é resposta válida e não é erro seu.

**Por controle.**

* **P1** — No cabo, e é um dos dois que este teste mede. Anote o número dele no Hefesto, anote o nome do gamepad virtual que a dica dá, e procure esse nome na lista de fora.
* **P2** — No cabo, e é o segundo que este teste mede. Mesma sequência. Dois controles em vez de um importam aqui: se o de fora mostrar o MESMO número para os dois, e no Hefesto eles estiverem diferentes, o número de fora não veio destes controles.
* **P3** — No rádio, e é testemunha. Não mexa nele. Anote o número dele no Hefesto e o que a lista de fora diz — ele serve para você ver se o de fora está repetindo o mesmo valor para todo mundo.
* **P4** — No rádio, e é a segunda testemunha. Mesma coisa. Quatro controles com quatro números diferentes no Hefesto e um único número igual lá fora é a assinatura do valor inventado.

**A armadilha.** A PROVA DESTA LINHA PAROU NO MONTOU: o número é montado e escrito no gamepad virtual, e ninguém nunca o viu chegar do outro lado. Por isso a cilada aqui é o valor de fábrica — quando o Hefesto não tem o dado, ele manda 'cheio e carregando'. Então '100% carregando' nos quatro, para sempre, é o FALSO VERDE deste teste, não a aprovação: é o que o produto diz quando não sabe. Some a isso uma coisa já medida nesta casa: o gamepad virtual tem um registro de bateria próprio no sistema que diz 'carregando' eternamente, e nenhuma régua desta casa o exclui das contas — quem ler o registro errado vê um número que NUNCA muda e conclui que a bateria congelou. E cuidado com nome repetido: cada controle físico aparece uma vez na lista de fora e o gamepad virtual dele aparece outra. Se você comparar o físico com o físico, o teste não mediu o caminho até o jogo — foi por isso que os passos mandam anotar o nome do virtual primeiro.

---

## mapa-energia.bateria.jogo-radio — Bateria — espelho ao jogo (vpad) · rádio

*Célula:* `energia.bateria.jogo @ rádio`

**O que isto prova.** Prova se o número da bateria do P3 e do P4, que estão no rádio, sai do Hefesto e chega a quem os enxerga como controle de jogo.

**Onde olhar.** Começa na aba Controles: passe o mouse em cima do nome de cada card (o pedaço que diz o número, a cor do plástico e a palavra rádio) e leia a dica — ela diz qual gamepad virtual aquele controle alimenta. Onde um jogo mostra a bateria de um controle, A FONTE NÃO DIZ. O lugar mais próximo é a lista de controles da Steam, em Configurações, e a tela de controles do próprio jogo, se ele tiver uma. Nenhum dos dois mostrando bateria também é resposta, e se escreve.

**Os passos.**

1. Abra a janela do Hefesto e clique na aba Controles.
2. Feche os cards que estiverem abertos.
3. Confira que a linha do P3 e a do P4 dizem rádio.
4. Anote o número de bateria do P3 e o do P4.
5. Passe o mouse no nome do card do P3 e anote o nome do gamepad virtual que a dica diz.
6. Passe o mouse no nome do card do P4 e anote o nome do gamepad virtual dele.
7. Abra a Steam.
8. Abra as Configurações da Steam e vá à página de Controle.
9. Procure na lista os dois nomes que você anotou.
10. Anote o que a lista mostra de bateria para cada um — o número, ou nada.
11. Anote se a lista diz que algum deles está carregando.
12. Compare os dois números com os que você anotou no começo.
13. Anote lado a lado o que a lista mostrou para os dois do cabo e para os dois do rádio.
14. Escreva 'não há onde ler' se nenhuma tela fora do Hefesto mostrar bateria.

**Passa quando.** O número que aparece do lado de fora para o gamepad virtual do P3 e para o do P4 é o mesmo que o Hefesto mostra para eles, com no máximo um degrau de dez de diferença. Se os dois do cabo aparecerem certos lá fora e os dois do rádio não, isso é o achado, e é o que este teste existe para pegar. E se não houver bateria à mostra em lugar nenhum, escreva 'não há onde ler'.

**Por controle.**

* **P1** — No cabo, e é testemunha. Não mexa nele. Anote o que a lista de fora diz sobre ele: ele é o controle de comparação — se o caminho do cabo mostra número e o do rádio não, a diferença é do rádio.
* **P2** — No cabo, e é a segunda testemunha. Mesma anotação. Dois do cabo dizendo número e dois do rádio mudos é uma resposta muito mais forte que um contra um.
* **P3** — No rádio, e é um dos dois que este teste mede. Anote o número no Hefesto, o nome do gamepad virtual que a dica dá, e o que a lista de fora mostra.
* **P4** — No rádio, e é o segundo que este teste mede. Mesma sequência. Se ele for o único mudo dos quatro, o problema é do quarto lugar na fila, não do rádio.

**A armadilha.** A PROVA DESTA LINHA PAROU NO MONTOU, e do lado do rádio ela parou antes ainda: a régua automática que vigia este caminho só exercita o CABO — o rádio não é tocado por teste nenhum desta casa. O que você anotar aqui é a primeira medição que existe desta metade, inclusive um 'não há onde ler'. A cilada é o valor de fábrica: sem dado, o Hefesto manda 'cheio e carregando', então '100% carregando' no P3 e no P4 enquanto o Hefesto mostra os números deles caindo é o falso verde clássico — e é o resultado mais provável. Junte a isso o registro de bateria do gamepad virtual, que já foi medido dizendo 'carregando' para sempre e que nenhuma régua desta casa exclui das contas. E não compare o controle físico com ele mesmo: procure na lista o nome do gamepad VIRTUAL, que é o que a dica do card lhe deu.

---

## mapa-energia.bateria.leitura_hefesto-cabo — Bateria — leitura pelo Hefesto · cabo

*Célula:* `energia.bateria.leitura_hefesto @ cabo`

**O que isto prova.** Prova que o Hefesto está mesmo lendo a bateria dos dois controles do cabo, e que as três telas que mostram esse número dizem a mesma coisa.

**Onde olhar.** Em três lugares, e é a comparação entre eles que responde. Na aba Controles, com os cards fechados: no fim da linha de cada controle vem a palavra Bateria, uma barrinha e o número em porcento. Na aba Jogar, no cartão de cada controle: um desenho de pilha com o número ao lado, embaixo do nome e da cor. Na aba Conexões, na linha de cada controle: a palavra Bateria e o número — e a dica dessa linha diz, com todas as letras, que o número vem da aba Controles. Um travessão no lugar do número ('— %') não é zero: quer dizer que o Hefesto não conseguiu ler aquele controle.

**Os passos.**

1. Abra a janela do Hefesto.
2. Clique na aba Controles e feche os cards que estiverem abertos.
3. Confira que a linha do P1 e a do P2 terminam com a palavra cabo.
4. Anote o número de bateria do P1 e o do P2.
5. Confira que nenhum dos dois mostra travessão no lugar do número.
6. Olhe a barrinha ao lado de cada número e confira que ela está cheia mais ou menos na proporção do número.
7. Clique na aba Jogar.
8. Anote o número que aparece ao lado do desenho de pilha no cartão do P1 e no do P2.
9. Clique na aba Conexões.
10. Anote o número que aparece depois da palavra Bateria na linha do P1 e na do P2.
11. Compare os três números de cada controle: os três têm de ser iguais.
12. Volte à aba Controles.
13. Puxe o cabo do P1 e conte até dois.
14. Encaixe o cabo do P1 de novo.
15. Espere a linha do P1 voltar à lista, olhando a tela.
16. Leia o número de bateria do P1 assim que ele voltar.
17. Confira que o P2, o P3 e o P4 não mudaram de número nesse meio-tempo.

**Passa quando.** O P1 e o P2 têm um número de bateria nas TRÊS abas, e os três números de cada um são o mesmo. Nenhum dos dois mostra travessão. E, depois de o cabo do P1 sair e voltar, ele reaparece na lista já com um número — não com travessão e não com a barrinha vazia —, sem você recarregar nada.

**Por controle.**

* **P1** — No cabo, e é nele que você mexe. Anote os três números dele, puxe o cabo, devolva o cabo em menos de trinta segundos e leia o número de novo quando ele voltar. É a prova de que o Hefesto LÊ o controle quando ele entra, em vez de repetir o que já estava na tela.
* **P2** — No cabo, e não se toca nele. Anote os três números dele. Enquanto o P1 sai e volta, o número do P2 não pode piscar, sumir nem virar travessão — se sumir junto, quem caiu não foi o P1, foi a leitura do cabo inteira.
* **P3** — No rádio, e é testemunha. Anote o número dele nas três abas antes e depois. Ele não pode mudar por causa do cabo do P1 ter saído.
* **P4** — No rádio, e é a segunda testemunha. Mesma conferência do P3. Se os dois do rádio virarem travessão quando o P1 sai do cabo, o achado é grande e vale anotar a hora exata.

**A armadilha.** A leitura em si já foi medida no aparelho, em 06/09, com estes quatro controles na mesa — o que não foi medido é a escada de degraus, que é outro teste. Aqui a armadilha é o NÚMERO QUE NUNCA MUDA. Existem quatro registros de bateria no sistema para dois controles, e dois deles são dos gamepads virtuais que o próprio Hefesto cria; o registro deles diz 'carregando' para sempre e o número não anda nunca. Nenhuma régua desta casa separa um do outro, e a cura prometida para isso NÃO entrou. Então quatro números idênticos e imóveis não são aprovação: podem ser quatro controles cheios, ou podem ser o registro errado. Não conclua nada dos quatro iguais — o que decide é o teste dos degraus, com as duas leituras separadas por quarenta minutos. Segunda armadilha, mais boba: se o P1 não tiver sido pareado por rádio nesta máquina, puxar o cabo dele o tira da lista inteira; devolva o cabo em menos de trinta segundos e ele volta com o mesmo número de jogador que tinha. E feche os cards antes de anotar — com o card aberto, o 'P1' some do começo da linha e é fácil anotar o número do controle errado.

---

## mapa-energia.bateria.leitura_hefesto-radio — Bateria — leitura pelo Hefesto · rádio

*Célula:* `energia.bateria.leitura_hefesto @ rádio`

**O que isto prova.** Prova que o Hefesto lê a bateria também dos dois controles do rádio, e que as três telas dizem o mesmo número.

**Onde olhar.** Nos mesmos três lugares do irmão do cabo. Na aba Controles, com os cards fechados: no fim da linha de cada controle, a palavra Bateria, uma barrinha e o número. Na aba Jogar, no cartão de cada controle: o desenho de pilha com o número ao lado. Na aba Conexões, na linha de cada controle: a palavra Bateria e o número. E a fita do topo da aba Controles, a linha que começa com 'Selecionar:', onde cada controle é um chip — é por ela que você vê o P3 sair e voltar.

**Os passos.**

1. Abra a janela do Hefesto.
2. Clique na aba Controles e feche os cards que estiverem abertos.
3. Confira que a linha do P3 e a do P4 terminam com a palavra rádio.
4. Anote o número de bateria do P3 e o do P4.
5. Confira que nenhum dos dois mostra travessão no lugar do número.
6. Clique na aba Jogar e anote o número ao lado do desenho de pilha no cartão do P3 e no do P4.
7. Clique na aba Conexões e anote o número depois da palavra Bateria na linha do P3 e na do P4.
8. Compare os três números de cada um: os três têm de ser iguais.
9. Volte à aba Controles.
10. Segure o botão PS do P3 até todas as luzes dele apagarem.
11. Solte o botão e confira que o chip do P3 saiu da fita do topo.
12. Dê um toque no botão PS do P3 para religá-lo, sem demorar.
13. Espere o chip do P3 voltar à fita, olhando a tela.
14. Leia o número de bateria do P3 assim que a linha dele voltar.
15. Confira que o número do P4 não mudou enquanto o P3 esteve fora.

**Passa quando.** O P3 e o P4 têm um número de bateria nas TRÊS abas, e os três números de cada um são o mesmo. Nenhum dos dois mostra travessão. E, depois de sair e voltar, o P3 reaparece já com um número — não com travessão —, sem você recarregar nada.

**Por controle.**

* **P1** — No cabo, e é testemunha. Não toque nele. Anote o número dele antes e depois: ele é a prova de que o Hefesto continuou lendo alguém enquanto o P3 estava fora.
* **P2** — No cabo, e é a segunda testemunha. Mesma anotação. Se os dois do cabo mostram número e os dois do rádio mostram travessão, o defeito é do RÁDIO, e é isso que este teste separa.
* **P3** — No rádio, e é o único em que você toca. Anote os três números dele, desligue-o pelo PS longo, religue com um toque no PS e leia o número assim que ele voltar.
* **P4** — No rádio, e não se toca nele. Anote os três números. Enquanto o P3 está fora, o número do P4 não pode sumir nem virar travessão — vizinho de rádio caindo junto é o defeito que este teste procura.

**A armadilha.** Pelo rádio o Hefesto só aceita a leitura depois de conferir o quadro que o controle mandou, e o pedaço da bateria fica UMA posição adiante da que fica no cabo. Isso foi medido no aparelho em 06/09, e o jeito como ele erra é conhecido: lendo na posição do cabo, o estado de carga sai como um valor que não existe no aparelho. Ou seja, o sintoma do defeito do rádio não é um número um pouco errado — é travessão, ou um estado de carga sem sentido. A segunda armadilha é a mesma do irmão do cabo, e é a que mais engana: há quatro registros de bateria no sistema para dois controles, e dois são dos gamepads virtuais que o Hefesto cria; o registro deles diz 'carregando' para sempre e o número não anda nunca. Quem lê o errado vê um número imóvel e acha que a bateria congelou. Terceira: não demore para religar o P3. O lugar dele fica guardado por trinta segundos; passando disso ele volta com outro número de jogador, e isso é a regra do produto funcionando, não defeito.

---

## mapa-energia.bateria.percentual-cabo — Bateria — percentual e estado de carga · cabo

*Célula:* `energia.bateria.percentual @ cabo`

**O que isto prova.** Prova que o Hefesto diz, ao lado do número, o estado da carga do P1 e do P2 — e que esse estado é lido do aparelho, não deduzido de eles estarem no cabo.

**Onde olhar.** Na aba Controles, com os cards fechados. Logo depois do número em porcento aparece um iconezinho: um raio quando está carregando, um certo quando está cheio, um triângulo de atenção quando a carga deu problema. Passe o mouse nele e a dica escreve a palavra: Carregando, Cheio, Fora de faixa ou Erro de carga. Quando o controle está só gastando, NÃO aparece ícone nenhum — a ausência é a resposta, e é decisão dela: o número caindo já diz.

**Os passos.**

1. Abra a janela do Hefesto e clique na aba Controles.
2. Feche os cards que estiverem abertos.
3. Confira que a linha do P1 e a do P2 terminam com a palavra cabo.
4. Anote o número de bateria do P1 e o do P2.
5. Passe o mouse no ícone que fica logo depois do número do P1 e anote a palavra da dica.
6. Passe o mouse no ícone que fica depois do número do P2 e anote a palavra da dica.
7. Confira que a palavra combina com o número: Cheio só pode aparecer em 100%.
8. Anote se os dois disseram a mesma palavra ou palavras diferentes.
9. Puxe o cabo do P1 e conte até dois.
10. Encaixe o cabo do P1 de novo.
11. Espere a linha do P1 voltar à lista.
12. Passe o mouse no ícone do P1 outra vez e anote a palavra.
13. Confira que o P2, o P3 e o P4 não trocaram de ícone nem de número nesse meio-tempo.

**Passa quando.** Cada um dos dois controles do cabo mostra um estado que combina com o número dele: Cheio só em 100%, Carregando num número abaixo de 100. Nenhum dos dois diz Carregando só por estar no cabo. E as duas testemunhas do rádio não ganham ícone nenhum nem mudam de número durante o teste.

**Por controle.**

* **P1** — No cabo, e é nele que você mexe. Leia a palavra da dica antes, puxe o cabo, devolva-o em menos de trinta segundos e leia a palavra de novo. Se ele estava em 100% e dizia Cheio, tem de continuar dizendo Cheio depois.
* **P2** — No cabo, e não se toca nele. Leia a palavra da dica dele e compare com a do P1. Os dois estão no mesmo transporte: se um diz Cheio e o outro diz Carregando, isso é LEITURA acontecendo, e é o melhor resultado que este teste pode dar.
* **P3** — No rádio, e é testemunha. Não pode ganhar ícone nenhum enquanto está só gastando. Se aparecer um raio no P3 sem cabo nenhum ligado nele, anote — é o estado saindo do controle errado.
* **P4** — No rádio, e é a segunda testemunha. Mesma conferência do P3: sem ícone, número parado ou caindo devagar.

**A armadilha.** A PROVA DESTA LINHA PAROU NO MONTOU: o percentual e o estado de carga são montados e mostrados, mas nunca foram acompanhados até o outro lado. Duas ciladas de leitura. A primeira: Fora de faixa e Erro de carga usam o MESMO ícone de atenção, e nesses dois casos o número ao lado é um número que o driver da máquina já jogou fora — ele não vale nada, por mais certo que pareça. Se você vir o triângulo, não anote o número como bom; anote a palavra. A segunda: não deduza a carga pelo cabo. Em 06/09 os DOIS controles do cabo diziam Cheio, e não Carregando — um produto que inferisse a carga do transporte estaria errado nos dois naquele instante, e foi essa medição que decidiu que carga e transporte são dois fatos separados. Por fim, se o P1 não tiver sido pareado por rádio nesta máquina, puxar o cabo dele o tira da lista inteira: devolva o cabo em menos de trinta segundos e ele volta com o mesmo número de jogador.

---

## mapa-energia.bateria.percentual-radio — Bateria — percentual e estado de carga · rádio

*Célula:* `energia.bateria.percentual @ rádio`

**O que isto prova.** Prova que os dois controles do rádio não ganham ícone de carga enquanto só gastam, e que o ícone de carregando aparece se você puser um deles num carregador — sem ele deixar de falar por rádio.

**Onde olhar.** Na aba Controles, com os cards fechados. Logo depois do número em porcento fica o iconezinho de carga: raio para carregando, certo para cheio, triângulo para carga com problema. Passe o mouse nele e a dica escreve a palavra. Controle que só gasta não mostra ícone nenhum, de propósito. E olhe também a palavra no fim do nome da linha, antes da bateria: ela tem de continuar dizendo rádio do começo ao fim deste teste.

**Os passos.**

1. Abra a janela do Hefesto e clique na aba Controles.
2. Feche os cards que estiverem abertos.
3. Confira que a linha do P3 e a do P4 terminam com a palavra rádio.
4. Confira que não há cabo nenhum encaixado no P3 nem no P4.
5. Anote o número de bateria do P3 e o do P4.
6. Confira que nenhum dos dois mostra ícone depois do número.
7. Pegue um carregador de tomada, ou uma bateria portátil — nunca uma porta do PC.
8. Ligue o P3 nesse carregador.
9. Leia a linha do P3 e confira que a palavra continua rádio.
10. Passe o mouse no ícone que apareceu depois do número do P3 e anote a palavra da dica.
11. Confira que o P4 continua sem ícone nenhum.
12. Tire o P3 do carregador.
13. Confira que o ícone do P3 sumiu de novo.

**Passa quando.** Com os dois só gastando, nem o P3 nem o P4 mostram ícone. Com o P3 no carregador, e a linha dele ainda dizendo rádio, aparece o ícone de raio e a dica escreve Carregando. O P4 continua sem ícone o tempo todo, e o P3 volta a ficar sem ícone quando você tira o carregador.

**Por controle.**

* **P1** — No cabo, e é testemunha. Não toque nele. Anote a palavra da dica dele no começo e no fim: ligar um carregador no P3 não pode mudar nada no P1.
* **P2** — No cabo, e é a segunda testemunha. Mesma conferência. Se o ícone do P2 mudar quando você plugar o P3 no carregador, o estado está indo para o controle errado.
* **P3** — No rádio, e é o único em que você mexe. Sem ícone enquanto só gasta; com o carregador ligado, o ícone de raio e a palavra Carregando — e a linha dele continuando a dizer rádio, que é o ponto inteiro deste teste.
* **P4** — No rádio, e não se toca nele. Sem cabo, sem carregador, sem ícone, do começo ao fim. Ele é a prova de que o raio que apareceu no P3 é do P3.

**A armadilha.** A PROVA DESTA LINHA PAROU NO MONTOU, e a metade que você vai medir aqui é INÉDITA: em 06/09 os quatro controles foram lidos no aparelho e nenhum dos dois do rádio estava carregando, então 'carregando pelo rádio' nunca foi visto nesta casa. O que você anotar é a primeira prova que existe. Duas ciladas. A primeira é o carregador: se, ao ligá-lo, a linha do P3 trocar de rádio para cabo, o que você ligou não é um carregador — é uma porta que também fala dados, e o teste virou outro. Troque por um carregador de tomada ou uma bateria portátil e refaça. A segunda é o silêncio: um controle que só gasta NÃO mostra ícone, e isso não é campo faltando nem defeito — é decisão dela, porque o número caindo já conta a história. Anotar 'não apareceu ícone' com os dois na mão e sem carregador é o resultado CERTO da primeira metade.

---

## mapa-energia.desligar-cabo — Desligar o controle por software · cabo

*Célula:* `energia.desligar @ cabo`

**O que isto prova.** Prova que o Hefesto não oferece nenhum jeito de desligar um controle do cabo pela tela, e que os dois botões que parecem isso são outra coisa.

**Onde olhar.** Em três lugares, e nenhum dos três desliga controle. Na aba Sistema, o botão vermelho 'Parar o serviço' — passe o mouse e a dica diz que o Hefesto deixa de rodar e que os controles viram gamepads comuns. Na aba Iluminação, o botão vermelho 'Desligar' no fim da coluna de cada controle — a dica diz que ele apaga a barra de luz daquele controle. Na aba Conexões, dentro da linha aberta de um controle, o botão 'A luz não acende', que refaz a conexão. O único desligamento que existe hoje é com o dedo, no botão PS do aparelho. Para acompanhar o que acontece, use a aba Controles: a fita do topo que começa com 'Selecionar:' e a contagem no alto ('4 controles: 2 USB · 2 BT').

**Os passos.**

1. Abra a janela do Hefesto.
2. Abra a aba Sistema e passe o mouse no botão vermelho 'Parar o serviço' — leia a dica e NÃO clique.
3. Abra a aba Iluminação e passe o mouse no botão vermelho 'Desligar' da coluna do P1 — leia a dica e NÃO clique.
4. Abra a aba Conexões e leia a linha do P1.
5. Percorra as dez abas e anote se existe, em alguma, um botão que prometa desligar um controle.
6. Volte à aba Controles e feche os cards.
7. Anote os quatro chips da fita do topo e o que a contagem do alto diz.
8. Segure o botão PS do P1, que está no cabo, até todas as luzes dele apagarem.
9. Solte o botão e deixe o P1 na mesa, com o cabo ainda encaixado.
10. Anote o que aconteceu com o aparelho: as luzes apagaram, ou não.
11. Olhe a fita do topo e anote se o chip do P1 saiu.
12. Leia a contagem no alto e anote o que ela diz agora.
13. Confira que o P2, o P3 e o P4 continuam com os mesmos números.
14. Dê um toque no botão PS do P1 para trazê-lo de volta, se ele tiver saído.

**Passa quando.** Nenhuma das dez abas oferece desligar um controle, e as duas coisas parecidas se explicam sozinhas na dica: uma para o serviço inteiro, a outra apaga a barra de luz. O P1 responde ao PS longo com o cabo encaixado, e o que ele faz fica ANOTADO — apagou e voltou sozinho, ou apagou e ficou fora. E os outros três não trocam de número em momento nenhum.

**Por controle.**

* **P1** — No cabo, e é o único em que você toca. Segure o PS até as luzes apagarem, com o cabo encaixado, e anote o que acontece: se ele apaga, se sai da fita e se volta sozinho por causa do cabo. Não invente expectativa — o valor deste teste é o que você escrever aqui.
* **P2** — No cabo, e não se toca nele. É a testemunha do mesmo transporte: o chip dele não pode sair da fita nem trocar de número quando o P1 apaga. Se os dois do cabo caírem juntos, o que caiu não foi o controle.
* **P3** — No rádio, e não se toca nele. Testemunha do outro transporte: chip na fita o tempo todo, número intacto.
* **P4** — No rádio, e não se toca nele. Segunda testemunha, e é o último da fila — o primeiro a cair quando alguma coisa desmonta. Confira o chip e o número dele depois.

**A armadilha.** NÃO CLIQUE em 'Parar o serviço'. Ele derruba o Hefesto inteiro, os quatro controles viram gamepads comuns do Linux e a bancada acaba ali; se clicar sem querer, ligue de novo pela mesma aba antes de continuar. Soltar o PS cedo demais mede o SEU gesto e não o produto: com uns cinco segundos de aperto o Hefesto lê aquilo como um toque no PS e abre a Steam — se a Steam abrir, feche e refaça. E não escreva 'reprovou' porque não achou o botão: aqui a ausência é a resposta certa. Onde a prova parou: ninguém nesta casa localizou o comando de desligar por software, e ninguém mediu se ele existe — a faixa de perguntas que o aparelho responde foi varrida em 15/08 e nada de energia voltou, mas ESCREVER no aparelho para desligá-lo nunca foi tentado. O PS5 desliga este mesmo controle por software, então o caminho existe no aparelho; o que falta é o nosso conhecimento dele.

---

## mapa-energia.desligar-radio — Desligar o controle por software · rádio

*Célula:* `energia.desligar @ rádio`

**O que isto prova.** Prova que o Hefesto também não oferece jeito de desligar um controle do rádio pela tela, e mede o que o dedo faz no lugar disso.

**Onde olhar.** Nos mesmos três lugares que não desligam controle: o botão vermelho 'Parar o serviço' da aba Sistema (a dica diz que o Hefesto deixa de rodar), o botão vermelho 'Desligar' da coluna de cada controle na aba Iluminação (a dica diz que ele apaga a barra de luz) e o botão 'A luz não acende' da aba Conexões, que refaz a conexão. Para acompanhar a saída e a volta do P3, use a aba Controles: a fita do topo que começa com 'Selecionar:', a contagem no alto ('4 controles: 2 USB · 2 BT') e o quadro Dispositivos Conectados, onde o lugar de quem saiu passa a dizer Desconectado. No aparelho, olhe as cinco lâmpadas brancas em fileira embaixo do touchpad.

**Os passos.**

1. Abra a janela do Hefesto.
2. Abra a aba Sistema e passe o mouse no botão vermelho 'Parar o serviço' — leia a dica e NÃO clique.
3. Abra a aba Iluminação e passe o mouse no botão vermelho 'Desligar' da coluna do P3 — leia a dica e NÃO clique.
4. Percorra as dez abas e anote se existe, em alguma, um botão que prometa desligar um controle.
5. Volte à aba Controles e feche os cards.
6. Anote os quatro chips da fita do topo e o que a contagem do alto diz.
7. Segure o botão PS do P3 até todas as luzes dele apagarem.
8. Solte o botão e ponha o P3 na mesa.
9. Confira que o chip do P3 saiu da fita do topo.
10. Leia a contagem no alto e confira que ela passou a dizer três controles.
11. Abra o quadro Dispositivos Conectados e confira que o lugar do P3 diz Desconectado.
12. Confira que nenhum dos outros três se mudou para o lugar do P3.
13. Dê um toque no botão PS do P3 antes de passarem trinta segundos, para religá-lo.
14. Confira que o chip do P3 voltou à fita com o mesmo número de antes.

**Passa quando.** Nenhuma das dez abas oferece desligar um controle, e os dois botões parecidos se explicam na dica: um para o serviço inteiro, o outro apaga a barra de luz. Com o dedo, o P3 desliga de verdade: as luzes apagam, o chip sai da fita, a contagem cai para três e o lugar dele fica marcado como Desconectado, sem ninguém tomá-lo. E ele volta com o mesmo número quando você toca o PS.

**Por controle.**

* **P1** — No cabo, e é testemunha. Não toque nele. Anote o número dele antes e depois: desligar um do rádio não pode mexer em quem está no cabo.
* **P2** — No cabo, e é a segunda testemunha. Mesma conferência. Se um dos dois do cabo trocar de número enquanto o P3 está fora, anote a hora — já se mediu isso acontecer nesta casa.
* **P3** — No rádio, e é o único em que você toca. Segure o PS até todas as luzes apagarem, deixe-o na mesa e religue com um toque no PS antes dos trinta segundos. Ele tem de voltar com o mesmo número.
* **P4** — No rádio, e não se toca nele. É o vizinho de rádio do que caiu, então é nele que uma bagunça aparece primeiro: confira o chip, o número e as cinco lâmpadas dele antes e depois, e veja se ele não se mudou para o lugar do P3.

**A armadilha.** NÃO CLIQUE em 'Parar o serviço' — ele derruba o Hefesto inteiro e a bancada acaba ali. Soltar o PS cedo demais mede o seu gesto e não o produto: com uns cinco segundos de aperto o Hefesto lê aquilo como um toque no PS e abre a Steam; se a Steam abrir, feche e refaça. Cuidado ao ler as cinco lâmpadas: elas não se contam da esquerda para a direita — o número é o CONJUNTO aceso. Jogador 1 é só a do meio; jogador 2 são a segunda e a quarta; jogador 3 são as duas pontas e a do meio; jogador 4 são as quatro pontas com a do meio apagada. E o relógio: o lugar de quem cai fica guardado por trinta segundos. Se você demorar mais que isso para tocar o PS, o P3 volta com outro número — e isso é a regra do produto funcionando, não defeito. Onde a prova parou: o comando de desligar por software nunca foi localizado nem medido nesta casa; a faixa de perguntas que o aparelho responde foi varrida em 15/08 e nada de energia voltou, e ESCREVER no aparelho para desligá-lo nunca foi tentado — no rádio, os degraus altos desse caminho nunca foram enviados a aparelho nenhum.

---

# entrada

---

## mapa-entrada.botoes-cabo — Botões digitais (A/B/X/Y, L/R, ZL/ZR, −, +, Home, Captura, L3/R3) + D-pad · cabo

*Célula:* `entrada.botoes @ cabo`

**O que isto prova.** Prova que cada botão de um controle ligado por cabo acende na tela do Hefesto quando você aperta, e acende só no cartão daquele controle.

**Onde olhar.** Na aba Controles. Clique no chip Todos, na fita do topo, para abrir os quatro cartões de uma vez. Dentro de cada cartão fica o desenho do controle, e apertar uma peça acende o desenho dela. São dezesseis desenhos que acendem: Cruz, Círculo, Quadrado, Triângulo, as quatro direções do direcional, L1, R1, L2, R2, Share, Options, PS e Touchpad. Os cliques dos analógicos não acendem no desenho — eles são as palavras L3 e R3, ao lado de Analógico esquerdo e Analógico direito, e ganham colchetes quando você aperta: [L3] e [R3]. O botão do microfone não tem desenho que acenda; quem responde por ele é o selo Microfone do mesmo cartão, que diz ATIVO, MUDO ou um traço.

**Os passos.**

1. Clique na aba Controles.
2. Clique no chip Todos, na fita do topo.
3. Confira que há quatro cartões abertos, um por controle.
4. Confira que os cartões do P1 e do P2 terminam com a palavra cabo, e os do P3 e do P4 com a palavra rádio.
5. Largue o P2, o P3 e o P4 na mesa e pegue só o P1.
6. Aperte cada uma das catorze peças do P1 que acendem no desenho, uma por vez, segurando dois segundos antes de soltar: Cruz, Círculo, Quadrado, Triângulo, as quatro direções do direcional, L1, R1, L2, R2, Share e Options.
7. Confira, a cada peça, que o desenho dela acendeu no cartão do P1 e apagou quando você soltou.
8. Confira, a cada peça, que nada acendeu junto nos cartões do P2, do P3 e do P4.
9. Aperte o PS do P1 e feche a Steam se ela vier para a frente.
10. Confira que o desenho do PS acendeu no cartão do P1.
11. Encoste um dedo no touchpad do P1 e, em seguida, aperte cada analógico para baixo até clicar, um de cada vez.
12. Confira que o desenho do Touchpad acendeu e que as palavras L3 e R3 ganharam colchetes, cada uma no clique do seu analógico.
13. Aperte o botão do microfone do P1 duas vezes, para trocar e devolver.
14. Confira que o selo Microfone do cartão do P1 trocou de palavra no primeiro aperto e voltou no segundo.
15. Largue o P1, pegue o P2 e refaça nele tudo o que você fez no P1, do Cruz ao botão do microfone.
16. Confira quais peças não acenderam, e em qual dos dois controles do cabo — é isso que se anota.

**Passa quando.** Nos dois controles do cabo, cada um dos dezesseis desenhos acende quando você aperta a peça correspondente e apaga quando solta; as palavras L3 e R3 ganham colchetes no clique e os perdem ao soltar; e o selo Microfone troca a cada aperto do botãozinho de mudo. Em nenhum momento um aperto no P1 acende alguma coisa no cartão do P2, do P3 ou do P4 — nem o contrário.

**Por controle.**

* **P1** — No cabo, e é o primeiro a ser apertado inteiro: as dezoito peças, uma por vez, com os outros três largados na mesa. Só o cartão dele pode reagir.
* **P2** — No cabo, e é o segundo a ser apertado inteiro. Enquanto você aperta o P1, ele é testemunha do próprio cabo: nada no cartão dele pode acender sozinho.
* **P3** — No rádio, e você não encosta nele em momento nenhum. É a testemunha de fora do cabo: se um aperto no P1 acender uma peça no cartão do P3, o Hefesto está misturando controles.
* **P4** — No rádio, e você também não encosta. Segunda testemunha, e a que mais nasce sem leitura: se o cartão dele mostrar um traço no lugar de L3 e R3, anote isso — é ausência de leitura, não botão solto.

**A armadilha.** Três, e a primeira já custou tempo nesta casa. Um toque no botão PS ABRE A STEAM — é o que esse botão faz de fábrica. Ele vai acender o desenho do PS e trazer a Steam para a frente; feche a Steam e siga, não é defeito. Segunda: o botão do microfone não tem desenho que acenda, e procurar um faz você reprovar um produto correto — a resposta dele é o selo Microfone do cartão. Terceira, e é a que produz falso vermelho: um cartão que mostra um traço no lugar de L3 e R3 não está dizendo botão solto, está dizendo que o Hefesto não conseguiu ler aquele controle. Cartão sem leitura mostra os gatilhos parados em 0 / 255 e os analógicos no meio para sempre, o que se parece com um controle que ninguém está tocando. Antes de reprovar, aperte qualquer botão e veja se ALGUMA coisa naquele cartão se mexe; se nada nunca se mexe, o achado é a falta de leitura, e é isso que se anota.

---

## mapa-entrada.botoes-radio — Botões digitais (A/B/X/Y, L/R, ZL/ZR, −, +, Home, Captura, L3/R3) + D-pad · rádio

*Célula:* `entrada.botoes @ rádio`

**O que isto prova.** Prova que cada botão de um controle ligado por rádio acende na tela do Hefesto quando você aperta, e acende só no cartão daquele controle.

**Onde olhar.** Na aba Controles. Clique no chip Todos, na fita do topo, para abrir os quatro cartões de uma vez. Dentro de cada cartão fica o desenho do controle, e apertar uma peça acende o desenho dela. São dezesseis desenhos que acendem: Cruz, Círculo, Quadrado, Triângulo, as quatro direções do direcional, L1, R1, L2, R2, Share, Options, PS e Touchpad. Os cliques dos analógicos não acendem no desenho — eles são as palavras L3 e R3, ao lado de Analógico esquerdo e Analógico direito, e ganham colchetes quando você aperta: [L3] e [R3]. O botão do microfone não tem desenho que acenda; quem responde por ele é o selo Microfone do mesmo cartão. E, no alto de qualquer aba, a contagem dos ligados — hoje ela diz 4 controles: 2 USB · 2 BT.

**Os passos.**

1. Clique na aba Controles.
2. Clique no chip Todos, na fita do topo, para abrir os quatro cartões.
3. Leia a contagem no alto e anote o que ela diz.
4. Confira que os cartões do P3 e do P4 terminam com a palavra rádio.
5. Largue o P1, o P2 e o P4 na mesa e pegue só o P3.
6. Aperte o Cruz do P3, segure dois segundos e solte.
7. Confira que o desenho do Cruz acendeu no cartão do P3 e apagou quando você soltou.
8. Confira que nada acendeu junto nos cartões do P1, do P2 e do P4.
9. Repita esse mesmo aperto, uma peça por vez, no Círculo, no Quadrado, no Triângulo, nas quatro direções do direcional, no L1, no R1, no L2, no R2, no Share, no Options e no PS do P3.
10. Confira, a cada peça, que só o desenho dela acendeu no cartão do P3 e que os outros três cartões ficaram parados.
11. Confira que o desenho do PS acendeu como os outros; se a Steam vier para a frente, feche-a e siga.
12. Encoste um dedo no touchpad do P3 e tire.
13. Confira que o desenho do Touchpad acendeu enquanto o dedo estava lá.
14. Aperte até clicar cada um dos dois analógicos do P3, um por vez.
15. Confira que as palavras L3 e R3 ganharam colchetes no clique — [L3] e [R3].
16. Aperte o botão do microfone do P3 duas vezes, com uma pausa entre elas.
17. Confira que o selo Microfone do cartão dele trocou de palavra no primeiro aperto e voltou ao que estava no segundo.
18. Leia a contagem no alto de novo e confira que ela continua dizendo quatro controles.
19. Largue o P3, pegue o P4 e refaça nele tudo, do Cruz ao microfone.
20. Confira, no fim, se alguma peça deixou de acender, e anote qual e em qual dos dois controles do rádio.

**Passa quando.** Nos dois controles do rádio, cada um dos dezesseis desenhos acende quando você aperta a peça correspondente e apaga quando solta; as palavras L3 e R3 ganham colchetes no clique; e o selo Microfone troca a cada aperto. Em nenhum momento um aperto no P3 acende alguma coisa no cartão do P4, do P1 ou do P2. E a contagem do alto continua dizendo quatro controles do começo ao fim — sem isso, o que você mediu foi uma queda de conexão, não os botões.

**Por controle.**

* **P1** — No cabo, e você não encosta nele. É testemunha: se um aperto no P3 acender uma peça no cartão do P1, o Hefesto está misturando controles — e o defeito atravessou de um transporte para o outro, que é o pior caso.
* **P2** — No cabo, e você também não encosta. Segunda testemunha do cabo, com a mesma conferência do P1.
* **P3** — No rádio, e é o primeiro a ser apertado inteiro: as dezoito peças, uma por vez, com os outros três largados na mesa.
* **P4** — No rádio, e é o segundo a ser apertado inteiro. Ele é o último a entrar na fila do Hefesto e o primeiro a ficar mudo quando alguma coisa desmonta — se três controles responderem e ele não, anote que o que falhou foi o quarto lugar da fila, e não o rádio.

**A armadilha.** Quatro. Um toque no botão PS ABRE A STEAM: é o que esse botão faz de fábrica, e não é defeito — feche-a e siga o teste. O botão do microfone não tem desenho que acenda — quem responde por ele é o selo Microfone do cartão. Cartão que mostra um traço no lugar de L3 e R3 está dizendo que o Hefesto não leu aquele controle, e não que o botão está solto: os gatilhos ficam parados em 0 / 255 e os analógicos no meio, o que se parece com um controle largado. E a que é só do rádio: se um cartão inteiro parar de responder no meio do teste, olhe a contagem no alto ANTES de reprovar — se ela passou a dizer três controles, o que caiu foi a conexão, e o teste se refaz do começo. O mapa desta casa prova que os botões chegam pelos dois caminhos; ele nunca mediu QUANDO chegam. Se um aperto responder com atraso visível, isso é achado — anote em qual controle e quantas vezes em quantas.

---

## mapa-entrada.bruta-cabo — Botões, sticks e gatilhos analógicos (entrada bruta) · cabo

*Célula:* `entrada.bruta @ cabo`

**O que isto prova.** Prova que o gatilho de um controle no cabo entrega o quanto ele foi apertado, e não apenas apertado ou solto.

**Onde olhar.** Na aba Controles, dentro do cartão de cada controle, no bloco Giroscópio — a dica dele chama isso de leitura viva do aparelho, dez vezes por segundo. A última linha desse bloco chama-se Gatilhos e traz L2 e R2, cada um com um número escrito na forma 0 / 255. Ao lado do desenho ficam Analógico esquerdo e Analógico direito, com X: e Y:, também em números. E no desenho ficam os riscos de L2 e R2, que acendem.

**Os passos.**

1. Ligue o P1 e o P2 pelo cabo e o P3 e o P4 pelo rádio.
2. Abra o Hefesto e clique na aba Controles.
3. Clique no chip Todos, na fita do topo, para abrir os quatro cartões.
4. Confira que os cartões do P1 e do P2 terminam com a palavra cabo.
5. Largue os quatro controles na mesa, sem encostar em gatilho nenhum.
6. Leia a linha Gatilhos dos quatro cartões e confirme que os oito números estão perto de 0.
7. Pegue o P1.
8. Aperte o L2 do P1 bem devagar, um pouquinho por vez, até o fim do curso.
9. Acompanhe o número do L2 no cartão do P1 enquanto o dedo desce.
10. Confirme que ele passou por valores no meio do caminho, e não pulou de 0 direto para 255.
11. Confirme que ele chegou a 255 com o gatilho no fundo.
12. Repare em que altura do curso o risco do L2 acendeu no desenho.
13. Solte o L2 e confirme que o número voltou para perto de 0 e o risco apagou.
14. Repita os seis passos acima com o R2 do P1.
15. Olhe os cartões do P2, do P3 e do P4 durante os apertos e confirme que os números deles ficaram parados.
16. Largue o P1, pegue o P2 e refaça o L2 e o R2 do mesmo jeito.
17. Anote o maior número que cada gatilho alcançou, nos dois controles do cabo.

**Passa quando.** Nos dois controles do cabo, o número do gatilho sobe aos poucos com o dedo, passa por valores no meio do caminho, chega a 255 com o gatilho no fundo e volta para perto de 0 quando você solta. O risco do gatilho no desenho acende só depois que o número passa de 30 — não desde o primeiro milímetro. E os números dos cartões que você não está tocando ficam parados o tempo todo.

**Por controle.**

* **P1** — No cabo. Aperte o L2 e o R2 devagar, um de cada vez, e leia o número subindo no cartão dele. É o primeiro dos dois a medir.
* **P2** — No cabo. Mesma medição do P1, feita depois. Enquanto você aperta o P1, o número do P2 não pode se mexer — é a testemunha do próprio cabo.
* **P3** — No rádio, e você não encosta nele. Testemunha: se o número do gatilho dele andar enquanto o seu dedo está no P1, o Hefesto está lendo um controle e escrevendo no cartão de outro.
* **P4** — No rádio, e você também não encosta. Segunda testemunha, com a mesma conferência do P3.

**A armadilha.** Três. O número e o risco aceso são duas coisas diferentes: o risco só acende acima de 30, então existe um começo de curso em que o número já anda e o desenho ainda está apagado — isso é o produto certo, e quem esperar os dois juntos reprova sem haver defeito. Segunda: um cartão que nunca leu aquele controle mostra os gatilhos parados em 0 / 255, exatamente como um gatilho solto; antes de reprovar, aperte o Cruz do mesmo controle e veja se o desenho dele acende — se nem isso acontece, o achado é a falta de leitura naquele cartão. Terceira, e é sobre o alcance desta prova: no mapa desta casa esta linha está provada só até o Hefesto MONTAR a leitura e pô-la na tela. Ninguém provou daqui para a frente que um jogo recebe esse número. Não peça ao jogo para reagir — a resposta deste teste é a tela.

---

## mapa-entrada.bruta-radio — Botões, sticks e gatilhos analógicos (entrada bruta) · rádio

*Célula:* `entrada.bruta @ rádio`

**O que isto prova.** Prova que o gatilho de um controle no rádio entrega o quanto ele foi apertado, e não apenas apertado ou solto.

**Onde olhar.** Na aba Controles, dentro do cartão de cada controle, no bloco Giroscópio — a leitura viva do aparelho. A última linha desse bloco chama-se Gatilhos e traz L2 e R2, cada um com um número escrito na forma 0 / 255. Ao lado do desenho ficam Analógico esquerdo e Analógico direito, com X: e Y:. No desenho ficam os riscos de L2 e R2, que acendem. E no alto de qualquer aba, a contagem dos ligados: 4 controles: 2 USB · 2 BT.

**Os passos.**

1. Ligue o P1 e o P2 pelo cabo e o P3 e o P4 pelo rádio.
2. Abra o Hefesto e clique na aba Controles.
3. Clique no chip Todos, na fita do topo, para abrir os quatro cartões.
4. Leia a contagem no alto e anote o que ela diz.
5. Confira que os cartões do P3 e do P4 terminam com a palavra rádio.
6. Largue os quatro controles na mesa, sem encostar em gatilho nenhum.
7. Leia a linha Gatilhos dos quatro cartões e confirme que os oito números estão perto de 0.
8. Pegue o P3.
9. Aperte o L2 do P3 bem devagar, um pouquinho por vez, até o fim do curso.
10. Acompanhe o número do L2 no cartão do P3 enquanto o dedo desce.
11. Confirme que ele passou por valores no meio do caminho, e não pulou de 0 direto para 255.
12. Confirme que ele chegou a 255 com o gatilho no fundo.
13. Repare em que altura do curso o risco do L2 acendeu no desenho.
14. Solte o L2 e confirme que o número voltou para perto de 0 e o risco apagou.
15. Repita os seis passos acima com o R2 do P3.
16. Olhe os cartões do P1, do P2 e do P4 durante os apertos e confirme que os números deles ficaram parados.
17. Leia a contagem no alto de novo e confirme que ela continua dizendo quatro controles.
18. Largue o P3, pegue o P4 e refaça o L2 e o R2 do mesmo jeito.
19. Anote o maior número que cada gatilho alcançou, nos dois controles do rádio.

**Passa quando.** Nos dois controles do rádio, o número do gatilho sobe aos poucos com o dedo, passa por valores no meio, chega a 255 no fundo do curso e volta para perto de 0 ao soltar — igualzinho ao que os dois do cabo fazem. O risco do gatilho acende só depois que o número passa de 30. Os números dos cartões que você não está tocando ficam parados. E a contagem do alto continua dizendo quatro controles do começo ao fim.

**Por controle.**

* **P1** — No cabo, e você não encosta nele. Testemunha, e serve de referência: se o número do P3 nunca subir, aperte o L2 do P1 e veja se o dele sobe — assim você separa um defeito do rádio de um defeito da leitura inteira.
* **P2** — No cabo, e você também não encosta. Segunda testemunha do cabo, com a mesma conferência do P1.
* **P3** — No rádio. Aperte o L2 e o R2 devagar, um de cada vez, e leia o número subindo no cartão dele. É o primeiro dos dois a medir.
* **P4** — No rádio. Mesma medição do P3, feita depois. É o último da fila do Hefesto: se o número dele for o único que não anda, o achado é do quarto lugar, e não do rádio.

**A armadilha.** Quatro. O número e o risco aceso são duas coisas: o risco só acende acima de 30, então há um começo de curso em que o número já anda e o desenho ainda está apagado — produto certo. Cartão que nunca leu aquele controle mostra os gatilhos parados em 0 / 255, igual a um gatilho solto: antes de reprovar, aperte o Cruz do mesmo controle e veja se o desenho acende. Se um cartão inteiro parar de responder no meio, olhe a contagem no alto — se ela passou a dizer três controles, o que caiu foi a conexão, e o teste se refaz em vez de reprovar. E o alcance: no mapa desta casa esta linha está provada só até o Hefesto MONTAR a leitura e pô-la na tela; ninguém provou daqui para a frente que um jogo recebe esse número. Não peça ao jogo para reagir — a resposta é a tela.

---

## mapa-entrada.combo.ponte-cabo — Combo PS + R3 — a LEITURA do gesto que pede a próxima ponte · cabo

*Célula:* `entrada.combo.ponte @ cabo`

**O que isto prova.** Prova que segurar o PS e clicar o analógico direito, num controle ligado por cabo, troca a forma como o jogo enxerga o controle — e que só o controle que navega o PC faz isso.

**Onde olhar.** Em dois lugares. No aparelho: a barra de luz, as duas tiras ao lado do touchpad, pisca a cor da forma que ficou de pé — rosa é a máscara DualSense, verde é a Xbox e laranja é mouse e teclado. Na tela: aba Jogar, quadro Modo, a fileira de cartões (Sony DualSense, Xbox, Steam Input, Point And Click e Navegação), em que um fica aceso; e o interruptor Status, logo acima, que tem de estar em Ligado. Quem é o controle que faz o gesto se lê na aba Navegação, nos cartões do alto: um deles diz Navega o PC e os outros dizem Só a janela.

**Os passos.**

1. Abra o Hefesto e clique na aba Jogar.
2. Confira que o interruptor Status está em Ligado.
3. Leia qual cartão do quadro Modo está aceso e anote.
4. Abra a aba Navegação.
5. Leia a linha de cada cartão do alto e ache o que diz Navega o PC.
6. Confira que quem diz Navega o PC é o P1 ou o P2 — um dos do cabo; se for um do rádio, este teste não é este, é o do rádio.
7. Volte à aba Jogar.
8. Pegue na mão o controle que navega o PC.
9. Segure o botão PS dele e, sem soltar, aperte o analógico direito para baixo até clicar, mantendo os dois juntos por um segundo inteiro.
10. Solte os dois.
11. Confira a barra de luz dos controles e anote a cor que ela piscou.
12. Leia de novo qual cartão do quadro Modo está aceso e compare com o que você anotou no começo.
13. Repita o mesmo gesto no mesmo controle mais duas vezes, anotando a cor e o cartão em cada uma delas.
14. Confira que na terceira volta o cartão aceso voltou a ser o do começo.
15. Faça o mesmo gesto em cada um dos outros três controles, um por vez, sempre segurando por um segundo.
16. Confira que nenhum deles piscou a barra nem mudou o cartão aceso.
17. Confira o que aconteceu em cada uma das voltas e anote tudo, inclusive as voltas em que nada aconteceu.

**Passa quando.** Os três gestos no controle que diz Navega o PC andam o ciclo inteiro e voltam ao começo: a barra de luz pisca rosa, depois verde, depois laranja, e o cartão aceso no quadro Modo acompanha essa mudança. O mesmo gesto nos outros três controles não pisca nada e não muda o cartão aceso.

**Por controle.**

* **P1** — No cabo. Se for ele quem diz Navega o PC, é NELE que o gesto se faz, três vezes, e é a barra dele que você olha primeiro.
* **P2** — No cabo. Se o Navega o PC for do P2, o gesto é nele. Se não for, ele é testemunha do próprio cabo: o gesto feito nele não pode mudar nada.
* **P3** — No rádio, e é testemunha. Faça o gesto nele uma vez e confirme que nada muda — não é defeito, é o produto: o gesto sai de um controle só.
* **P4** — No rádio, e é a segunda testemunha. Mesmo gesto, mesma confirmação de que nada muda.

**A armadilha.** Cinco, e as duas primeiras produzem falso vermelho. O gesto tem tempo: os dois botões têm de ficar segurados JUNTOS por mais de 0,15 s — um toque rápido conta como dois toques separados, e o PS sozinho abre a Steam. E o gesto sai de um controle só, o que diz Navega o PC na aba Navegação; nos outros três ele não faz nada, e isso é o produto certo. Terceira: o cartão Steam Input NUNCA acende, porque o ciclo do gesto não passa por ele e a tela não tem como saber — quem esperar vê-lo aceso vai reprovar um teste bom. Quarta: a barra de luz pisca em TODOS os controles, e não só no que fez o gesto — ela diz que o gesto pegou, não quem o fez; e dois pulsos vermelhos antes da cor querem dizer isto pode derrubar o controle dentro de um jogo, que é aviso e não erro. Quinta, e é sobre o alcance: no mapa desta casa esta linha está provada só até o Hefesto DESPACHAR o gesto por dentro. Ninguém, até hoje, apertou PS mais analógico direito num controle de verdade e viu a forma trocar. Este teste é exatamente o que fecha essa lacuna — anote tudo, inclusive o nada.

---

## mapa-entrada.combo.ponte-radio — Combo PS + R3 — a LEITURA do gesto que pede a próxima ponte · rádio

*Célula:* `entrada.combo.ponte @ rádio`

**O que isto prova.** Prova que segurar o PS e clicar o analógico direito, num controle ligado por rádio, troca a forma como o jogo enxerga o controle — e que só o controle que navega o PC faz isso.

**Onde olhar.** Em dois lugares. No aparelho: a barra de luz, as duas tiras ao lado do touchpad, pisca a cor da forma que ficou de pé — rosa é a máscara DualSense, verde é a Xbox e laranja é mouse e teclado. Na tela: aba Jogar, quadro Modo, a fileira de cartões (Sony DualSense, Xbox, Steam Input, Point And Click e Navegação), em que um fica aceso; e o interruptor Status, logo acima, que tem de estar em Ligado. Quem é o controle que faz o gesto se lê na aba Navegação, nos cartões do alto: um deles diz Navega o PC e os outros dizem Só a janela.

**Os passos.**

1. Abra o Hefesto e clique na aba Navegação.
2. Leia a linha de cada cartão do alto e ache o que diz Navega o PC.
3. Puxe o cabo do P1 e o cabo do P2, se quem navega o PC for um deles — os dois vão se apagar, e é isso mesmo.
4. Conte até cinco.
5. Leia os cartões de novo e confira que agora quem diz Navega o PC é o P3 ou o P4.
6. Confira, antes de seguir, se algum dos dois do rádio assumiu o Navega o PC: se nenhum assumir, pare aqui e anote — sem isso este teste não roda hoje, e essa é a resposta dele.
7. Abra a aba Jogar.
8. Confira que o interruptor Status está em Ligado.
9. Leia qual cartão do quadro Modo está aceso e anote.
10. Pegue na mão o controle do rádio que navega o PC.
11. Segure o botão PS dele e, sem soltar, aperte o analógico direito para baixo até clicar; mantenha os dois juntos por um segundo inteiro e solte.
12. Repare a cor que a barra de luz piscou e anote-a.
13. Leia de novo qual cartão do quadro Modo está aceso e compare com o que você tinha anotado.
14. Repita o mesmo gesto mais duas vezes no mesmo controle, anotando a cor e o cartão de cada vez.
15. Confira que na terceira vez tudo voltou ao que era no começo.
16. Conte quantas vezes o gesto pegou de primeira e quantas você teve de repetir.
17. Faça o mesmo gesto no outro controle do rádio.
18. Confira que nada mudou nele: nem a barra de luz, nem o cartão aceso do quadro Modo.
19. Encaixe os dois cabos de volta no P1 e no P2.
20. Confira que os dois voltaram para a fita do topo, cada um com o número que tinha.

**Passa quando.** Os três gestos no controle do rádio que diz Navega o PC andam o ciclo inteiro e voltam ao começo: a barra pisca rosa, depois verde, depois laranja, e o cartão aceso no quadro Modo acompanha. O gesto no outro controle do rádio não muda nada. E cada gesto pega na primeira tentativa — se você tiver de repetir, anote quantas vezes em quantas: é isso que separa este caminho do caminho do cabo.

**Por controle.**

* **P1** — No cabo, e sai do teste: o cabo dele é puxado para que um controle do rádio assuma o Navega o PC. No fim, encaixe o cabo de volta e confirme que ele voltou para a fita do topo com o número que tinha.
* **P2** — No cabo, e sai do teste pelo mesmo motivo do P1. No fim, encaixe o cabo de volta e confirme que ele voltou com o número que tinha.
* **P3** — No rádio. Se for ele quem passar a dizer Navega o PC, é nele que o gesto se faz, três vezes.
* **P4** — No rádio. Se o Navega o PC ficar com o P4, o gesto é nele; se ficar com o P3, o P4 é a testemunha — o gesto feito nele não pode mudar nada, e isso não é defeito.

**A armadilha.** Seis. O gesto tem tempo: os dois botões têm de ficar segurados JUNTOS por mais de 0,15 s — toque rápido conta como dois toques separados, e o PS sozinho abre a Steam. O gesto sai de um controle só, o que diz Navega o PC; nos outros ele não faz nada, e isso é o produto certo. O cartão Steam Input nunca acende — quem esperar vê-lo aceso reprova um teste bom. A barra de luz pisca em TODOS os controles, então ela diz que o gesto pegou, não quem o fez; dois pulsos vermelhos antes da cor são aviso de que a troca pode derrubar o controle dentro de um jogo. Quinta, e é a que este teste existe para pegar: o mapa desta casa registra que os dois botões CHEGAM pelo rádio, mas nunca mediu QUANDO chegam — se o gesto pegar às vezes e falhar outras, o achado é esse atraso contra os 0,15 s do combo, e ele só vale escrito com número: tantas vezes em tantas tentativas. Sexta, o alcance: esta linha está provada só até o Hefesto despachar o gesto por dentro; ninguém apertou isto num controle de verdade até hoje.

---

## mapa-entrada.emulacao_mouse.analogico-cabo — Analogico como movimento do cursor (emulacao) · cabo

*Célula:* `entrada.emulacao_mouse.analogico @ cabo`

**O que isto prova.** Prova que, com um controle no cabo navegando o computador, o analógico esquerdo move o cursor e o direito rola a página.

**Onde olhar.** Na aba Navegação. Nos cartões do alto, um por controle, a linha diz USB • Navega o PC ou BT • Só a janela — só quem diz Navega o PC mexe no cursor. O interruptor Status do Modo tem de estar em Ligado, com a frase verde Pronto para usar como mouse abaixo dele. Mais abaixo ficam Velocidade de cursor, com um número de 1 a 12 (o padrão é 6), e Velocidade da rolagem, de 1 a 5 (o padrão é 1). Na tabela Definições Controle e Mouse, a linha L3 Direção tem de mostrar Movimento do cursor e a linha R3 Direção, Rolagem vertical e horizontal. A prova é o cursor andando na tela do computador — e, para a rolagem, deixe aberta antes de começar uma página longa, que precise rolar.

**Os passos.**

1. Clique na aba Jogar.
2. Clique no cartão Navegação, do quadro Modo.
3. Abra a aba Navegação.
4. Leia os cartões do alto e ache o que diz Navega o PC.
5. Confira que é o P1 ou o P2 — um dos dois do cabo.
6. Clique no interruptor Status do Modo para deixá-lo em Ligado.
7. Confira que apareceu, em verde, a frase Pronto para usar como mouse.
8. Leia a linha L3 Direção da tabela e confira que ela diz Movimento do cursor.
9. Leia a linha R3 Direção e confira que ela diz Rolagem vertical e horizontal.
10. Empurre o analógico esquerdo do controle que navega o PC até o fim, um sentido de cada vez — direita, esquerda, cima e baixo —, soltando entre um e outro.
11. Confira que o cursor acompanha os quatro sentidos, e que ele para onde estava assim que você solta.
12. Arraste a barra da Velocidade da rolagem até 5.
13. Empurre o analógico direito do mesmo controle até o fim para baixo, e depois até o fim para cima.
14. Confira que a página longa rolou para os dois lados.
15. Empurre os dois analógicos de cada um dos outros três controles, um por vez.
16. Confira que o cursor não anda e a página não rola com nenhum deles.
17. Desfaça o teste: devolva a Velocidade da rolagem ao 1, volte à aba Jogar e clique no cartão Sony DualSense.

**Passa quando.** O analógico esquerdo do controle do cabo que navega o PC leva o cursor pelos quatro sentidos, e o cursor para assim que você solta. O analógico direito rola a página nos dois sentidos. E os analógicos dos outros três controles não mexem no cursor nem rolam nada.

**Por controle.**

* **P1** — No cabo. Se for ele quem diz Navega o PC, é o analógico esquerdo dele que leva o cursor e o direito que rola a página.
* **P2** — No cabo. Se o Navega o PC for do P2, o teste é nele. Se não for, ele é testemunha do próprio cabo: os analógicos dele não podem mexer no cursor.
* **P3** — No rádio, e é testemunha. Empurre os dois analógicos dele e confira que o cursor não anda — não é defeito, é o produto: o cursor do PC é um só e sai de um controle só.
* **P4** — No rádio, e é a segunda testemunha. Mesmo empurrão, mesma conferência de que nada acontece.

**A armadilha.** Cinco. Zona morta: o analógico esquerdo só começa a mover o cursor depois de um sexto do curso, e o direito só começa a rolar depois de quase um terço — o direito precisa de um empurrão bem maior que o esquerdo, e empurrão de leve nos dois parece analógico morto. A rolagem nasce na velocidade 1, a mais lenta que existe: antes de dizer que não rola, ponha a Velocidade da rolagem no 5, que é o ato 5. O cursor é um só e sai de um controle só, o que diz Navega o PC — os outros três não mexerem nele é o produto certo, e a própria aba avisa que o cursor, a rolagem e o teclado valem para todos os controles ligados, e não só para o escolhido na fita de cima. Não confunda com a Navegação Interna, que é outra coisa: ela serve para andar dentro da janela do Hefesto, e hoje não tem quem a atenda no produto. E o mapa carrega uma observação dela de 11 de agosto dizendo que pelo rádio o analógico e o gatilho NÃO moviam o cursor, e que pelo cabo funcionavam; em 5 de setembro os dois caminhos foram medidos e responderam. Se hoje o cabo falhar, é defeito novo — anote com essa palavra.

---

## mapa-entrada.emulacao_mouse.analogico-radio — Analogico como movimento do cursor (emulacao) · rádio

*Célula:* `entrada.emulacao_mouse.analogico @ rádio`

**O que isto prova.** Prova que, com um controle no rádio navegando o computador, o analógico esquerdo move o cursor e o direito rola a página.

**Onde olhar.** Na aba Navegação. Nos cartões do alto, um por controle, a linha diz USB • Navega o PC ou BT • Só a janela — só quem diz Navega o PC mexe no cursor. O interruptor Status do Modo tem de estar em Ligado, com a frase verde Pronto para usar como mouse abaixo dele. Mais abaixo ficam Velocidade de cursor, com um número de 1 a 12 (o padrão é 6), e Velocidade da rolagem, de 1 a 5 (o padrão é 1). Na tabela Definições Controle e Mouse, a linha L3 Direção tem de mostrar Movimento do cursor e a linha R3 Direção, Rolagem vertical e horizontal. A prova é o cursor andando na tela do computador.

**Os passos.**

1. Abra o Hefesto e clique na aba Navegação.
2. Puxe o cabo do P1 e o cabo do P2 — se quem navega o PC for um deles, é assim que um controle do rádio assume; os dois vão se apagar, e é isso mesmo.
3. Conte até cinco e leia os cartões do alto: quem diz Navega o PC agora tem de ser o P3 ou o P4.
4. Na aba Jogar, clique no cartão Navegação, do quadro Modo.
5. Volte à aba Navegação e ponha o interruptor Status do Modo em Ligado.
6. Confira que apareceu, em verde, a frase Pronto para usar como mouse.
7. Leia a linha L3 Direção da tabela: ela tem de dizer Movimento do cursor.
8. Leia a linha R3 Direção: ela tem de dizer Rolagem vertical e horizontal.
9. Empurre o analógico esquerdo do controle do rádio que navega o PC até o fim, para cada um dos quatro lados, um de cada vez, soltando entre eles.
10. Confira que o cursor atravessa a tela para o lado de cada empurrão e que ele para onde estava assim que você solta.
11. Arraste a barra da Velocidade da rolagem até 5 e abra uma página longa, que precise rolar.
12. Empurre o analógico direito do mesmo controle para baixo e depois para cima.
13. Confira que a página rola nos dois sentidos.
14. Empurre os dois analógicos do outro controle do rádio.
15. Confira que o cursor não anda e a página não rola.
16. Devolva a Velocidade da rolagem ao 1 e, na aba Jogar, clique no cartão Sony DualSense, para desfazer o teste.
17. Encaixe os dois cabos de volta no P1 e no P2.
18. Confira que os dois voltaram para a fita do topo, com o número que tinham.

**Passa quando.** O analógico esquerdo do controle do rádio que navega o PC leva o cursor pelos quatro sentidos e o cursor para assim que você solta; o analógico direito rola a página nos dois sentidos. É a mesma resposta que o cabo dá, e é exatamente esse empate que este teste procura. O outro controle do rádio não mexe no cursor.

**Por controle.**

* **P1** — No cabo, e sai do teste: o cabo dele é puxado para que um controle do rádio assuma o Navega o PC. No fim, encaixe o cabo de volta e confirme que ele voltou para a fita com o número que tinha.
* **P2** — No cabo, e sai do teste pelo mesmo motivo. No fim, encaixe o cabo de volta e confirme que ele voltou com o número que tinha.
* **P3** — No rádio. Se for ele quem passar a dizer Navega o PC, é o analógico esquerdo dele que leva o cursor e o direito que rola a página.
* **P4** — No rádio. Se o Navega o PC ficar com o P4, o teste é nele; se ficar com o P3, o P4 é a testemunha — os analógicos dele não podem mexer no cursor, e isso não é defeito.

**A armadilha.** Seis, e a última é o motivo de este teste existir. Zona morta: o analógico esquerdo só começa a mover o cursor depois de um sexto do curso, e o direito só começa a rolar depois de quase um terço — empurrão de leve parece analógico morto. A rolagem nasce na velocidade 1, a mais lenta: ponha a Velocidade da rolagem no 5 antes de dizer que não rola. O cursor é um só e sai de um controle só — o outro do rádio não mexer nele é o produto certo. Não confunda com a Navegação Interna, que serve para andar dentro da janela do Hefesto e hoje não tem quem a atenda no produto. Se, com os dois cabos fora, nenhum controle do rádio assumir o Navega o PC, pare aqui: não há como medir isto hoje, e escrever exatamente isso é a resposta do teste, não falha sua. E a sexta: o mapa carrega uma observação dela de 11 de agosto dizendo que pelo rádio o analógico e o gatilho NÃO moviam o cursor, e que pelo cabo funcionavam; em 5 de setembro os dois caminhos foram medidos e responderam. Se hoje o rádio falhar, é aquele defeito de volta — e é o achado mais valioso desta linha. Sobre o tamanho: nove atos, um a mais que o alvo, porque este teste tem de desmontar a bancada antes de medir — tirar os dois cabos para forçar o rádio a assumir o cursor — e remontá-la depois. Sem esses dois atos de bancada ele mediria o cabo, que é outra célula.

---

## mapa-entrada.emulacao_mouse.gatilhos-cabo — Gatilhos L2/R2 como botao do mouse (emulacao) · cabo

*Célula:* `entrada.emulacao_mouse.gatilhos @ cabo`

**O que isto prova.** Prova que, com um controle no cabo navegando o computador, o L2 clica como o botão esquerdo do mouse e o R2 como o botão direito.

**Onde olhar.** Na aba Navegação. Nos cartões do alto, um por controle, a linha diz USB • Navega o PC ou BT • Só a janela — só quem diz Navega o PC mexe no cursor. O interruptor Status do Modo tem de estar em Ligado, e logo abaixo dele tem de aparecer, em verde, a frase Pronto para usar como mouse. Na tabela Definições Controle e Mouse, a linha marcada L2 tem de mostrar Botão esquerdo e a linha marcada R2, Botão direito. A prova, porém, é na tela do computador: o clique tem de acontecer.

**Os passos.**

1. Abra a aba Navegação.
2. Leia os cartões do alto e ache o que diz Navega o PC.
3. Confira que quem diz Navega o PC é o P1 ou o P2 — um dos do cabo; se for um do rádio, este teste não é este, é o do rádio.
4. Abra a aba Jogar e clique no cartão Navegação, do quadro Modo.
5. Volte à aba Navegação e clique no interruptor Status do Modo para deixá-lo em Ligado.
6. Confira que apareceu, em verde, a frase Pronto para usar como mouse.
7. Leia a linha L2 da tabela Definições Controle e Mouse e confira que ela diz Botão esquerdo.
8. Leia a linha R2 e confira que ela diz Botão direito.
9. Abra uma pasta de arquivos e deixe-a na frente da tela.
10. Com o cursor em cima de um arquivo, aperte o L2 do controle que navega o PC até o fundo do curso.
11. Confira que o arquivo ficou selecionado, como num clique do botão esquerdo.
12. Aperte o R2 do mesmo controle até o fundo do curso.
13. Confira que abriu o menu do botão direito.
14. Feche o menu.
15. Aperte o L2 e o R2 de cada um dos outros três controles, um por vez, sempre até o fundo.
16. Confira que nenhum deles clicou nada.
17. Volte à aba Jogar e clique no cartão Sony DualSense, para desfazer o teste.

**Passa quando.** O L2 do controle do cabo que navega o PC seleciona o arquivo, como o botão esquerdo do mouse, e o R2 abre o menu do botão direito. Os gatilhos dos outros três controles não clicam nada. E as duas linhas da tabela dizem, antes disso, Botão esquerdo e Botão direito.

**Por controle.**

* **P1** — No cabo. Se for ele quem diz Navega o PC, é nele que o L2 e o R2 são apertados até o fundo, e é o clique dele que decide este teste.
* **P2** — No cabo. Se o Navega o PC for do P2, o teste é nele. Se não for, ele é testemunha do próprio cabo: o L2 e o R2 dele não podem clicar nada.
* **P3** — No rádio, e é testemunha. Aperte o L2 e o R2 dele até o fundo e confirme que o cursor não clica — não é defeito, é o produto: o cursor do PC é um só, e sai de um controle só.
* **P4** — No rádio, e é a segunda testemunha. Mesmo aperto, mesma confirmação de que nada acontece.

**A armadilha.** Cinco. O gatilho tem de passar de um quarto do curso: abaixo disso o Hefesto não conta como aperto, e meia pressão parece gatilho morto. Só um controle mexe no cursor, e a tela diz qual — os outros três não clicarem é o produto certo, e é justamente a testemunha deste teste, não a reprovação dele. Entrar em Navegação derruba o controle virtual: com um jogo aberto ele perde os controles, e é por isso que a bancada começa sem jogo nenhum aberto e o teste se desfaz no fim clicando Sony DualSense. Se o interruptor recusar e aparecer uma frase laranja dizendo que o mouse e o teclado só se ligam fora do jogo, o degrau ainda está no jogo — troque no quadro Modo da aba Jogar antes de insistir. E a que dá o nome a este teste: o mapa carrega uma observação dela de 11 de agosto dizendo que pelo rádio o gatilho e o analógico NÃO moviam o cursor, e que pelo cabo funcionavam; em 5 de setembro os dois caminhos foram medidos e responderam. Se hoje falhar, é aquele defeito de volta — anote em qual transporte, porque é isso que o mapa está esperando.

---

## mapa-entrada.emulacao_mouse.gatilhos-radio — Gatilhos L2/R2 como botao do mouse (emulacao) · rádio

*Célula:* `entrada.emulacao_mouse.gatilhos @ rádio`

**O que isto prova.** Prova que, com um controle no rádio navegando o computador, o L2 clica como o botão esquerdo do mouse e o R2 como o botão direito.

**Onde olhar.** Na aba Navegação. Nos cartões do alto, um por controle, a linha diz USB • Navega o PC ou BT • Só a janela — só quem diz Navega o PC mexe no cursor. O interruptor Status do Modo tem de estar em Ligado, e logo abaixo dele tem de aparecer, em verde, a frase Pronto para usar como mouse. Na tabela Definições Controle e Mouse, a linha marcada L2 tem de mostrar Botão esquerdo e a linha marcada R2, Botão direito. A prova é na tela do computador: o clique tem de acontecer.

**Os passos.**

1. Abra o Hefesto e clique na aba Navegação.
2. Leia os cartões do alto e ache o que diz Navega o PC.
3. Puxe o cabo do P1 e o cabo do P2 — os dois vão se apagar, e é isso mesmo.
4. Conte até cinco e leia os cartões de novo: quem diz Navega o PC agora tem de ser o P3 ou o P4. Se nenhum dos dois do rádio assumir, pare aqui e escreva exatamente isso — é a resposta deste teste hoje, e não uma falha sua.
5. Na aba Jogar, clique no cartão Navegação, do quadro Modo.
6. Volte à aba Navegação e clique no interruptor Status do Modo para deixá-lo em Ligado.
7. Confira que apareceu, em verde, a frase Pronto para usar como mouse.
8. Leia a linha L2 e a linha R2 da tabela Definições Controle e Mouse: têm de dizer Botão esquerdo e Botão direito.
9. Abra uma pasta de arquivos e leve o cursor até cima de um arquivo.
10. Aperte o L2 do controle do rádio que navega o PC, até o fundo do curso.
11. Confira que o arquivo ficou selecionado, como num clique do botão esquerdo.
12. Aperte o R2 do mesmo controle até o fundo do curso, e feche o menu que abrir.
13. Confira que o que abriu foi o menu do botão direito.
14. Aperte o L2 e o R2 do OUTRO controle do rádio.
15. Confira que ele não clica nada — isso é o produto certo, e não defeito.
16. Desfaça o teste: volte à aba Jogar, clique no cartão Sony DualSense e encaixe os dois cabos de volta no P1 e no P2.
17. Confira que os dois voltaram para a fita do topo com os números que tinham.

**Passa quando.** O L2 do controle do rádio que navega o PC seleciona o arquivo, como o botão esquerdo do mouse, e o R2 abre o menu do botão direito — a mesma resposta que o cabo dá. O outro controle do rádio não clica nada. E as duas linhas da tabela dizem, antes disso, Botão esquerdo e Botão direito.

**Por controle.**

* **P1** — No cabo, e sai do teste: o cabo dele é puxado para que um controle do rádio assuma o Navega o PC. No fim, encaixe o cabo de volta e confirme que ele voltou para a fita com o número que tinha.
* **P2** — No cabo, e sai do teste pelo mesmo motivo. No fim, encaixe o cabo de volta e confirme que ele voltou com o número que tinha.
* **P3** — No rádio. Se for ele quem passar a dizer Navega o PC, é nele que o L2 e o R2 são apertados até o fundo.
* **P4** — No rádio. Se o Navega o PC ficar com o P4, o teste é nele; se ficar com o P3, o P4 é a testemunha — o L2 e o R2 dele não podem clicar nada, e isso não é defeito.

**A armadilha.** Este teste tem DEZ atos, acima dos oito do alvo porque ele desmonta a mesa e monta de volta: puxar os dois cabos é o único jeito de um controle do rádio assumir o cursor, e os atos 2 e 8 são a ida e a volta do modo. Cortar o ato 8 deixa a mesa dela em Navegação, sem controle virtual. Seis cuidados, e o último é o motivo de este teste existir. O gatilho tem de passar de um quarto do curso; abaixo disso o Hefesto não conta como aperto. Só um controle mexe no cursor — o outro do rádio não clicar é o produto certo. Entrar em Navegação derruba o controle virtual, e por isso o jogo tem de estar fechado antes de começar, e o teste se desfaz no fim clicando Sony DualSense. Se o interruptor recusar com uma frase laranja dizendo que o mouse e o teclado só se ligam fora do jogo, o degrau ainda está no jogo — troque no quadro Modo da aba Jogar. Se, com os dois cabos fora, nenhum controle do rádio assumir o Navega o PC, não há como medir isto hoje: escreva exatamente isso, é uma resposta e não uma falha sua. E a sexta: o mapa carrega uma observação dela de 11 de agosto dizendo que pelo rádio o gatilho e o analógico NÃO moviam o cursor, e que pelo cabo funcionavam; em 5 de setembro os dois caminhos foram medidos e responderam. Se hoje o rádio falhar, é aquele defeito de volta, e é o achado mais valioso desta linha.

---

## mapa-entrada.stick-cabo — Sticks analógicos (dois eixos por stick) · cabo

*Célula:* `entrada.stick @ cabo`

**O que isto prova.** Prova que os dois analógicos de um controle no cabo entregam a posição real do polegar, e que o repouso deles é lido do aparelho em vez de inventado.

**Onde olhar.** Na aba Controles, dentro do cartão de cada controle, ao lado do desenho. Ficam ali Analógico esquerdo, com a marca L3, e Analógico direito, com a marca R3. Cada um tem um círculo com um pontinho dentro e dois números: X: e Y:. O pontinho anda dentro do círculo acompanhando o polegar, e cada número vai de 0 a 255.

**Os passos.**

1. Clique na aba Controles.
2. Clique no chip Todos, na fita do topo, para abrir os quatro cartões.
3. Largue os quatro controles na mesa, sem encostar em analógico nenhum.
4. Leia e anote num papel os quatro números de repouso do P1 — X e Y do esquerdo, X e Y do direito — e depois os quatro do P2, do mesmo jeito.
5. Empurre o analógico esquerdo do P1 devagar até o fim, um sentido de cada vez — direita, esquerda, cima e baixo —, soltando entre um e outro.
6. Confira que o número X vai a um extremo num lado e ao outro extremo no lado oposto, e que o Y faz o mesmo em cima e embaixo.
7. Confira que o pontinho encosta na borda do círculo do mesmo lado para onde o seu polegar foi, e volta ao meio quando você solta.
8. Confira que, ao soltar, os dois números voltam para perto do que você anotou.
9. Empurre o analógico direito do P1 do mesmo jeito, um sentido de cada vez.
10. Confira nele as mesmas três coisas que conferiu no analógico esquerdo.
11. Confira, durante os empurrões, que os pontinhos dos cartões do P2, do P3 e do P4 ficaram parados.
12. Largue o P1 e pegue o P2.
13. Empurre os dois analógicos do P2 do mesmo jeito, um sentido de cada vez.
14. Confira no P2 as mesmas coisas que conferiu no P1.
15. Confira, eixo por eixo, se algum não alcançou os extremos — e anote qual, e em qual dos dois controles do cabo.

**Passa quando.** Empurrando um analógico até um extremo, o número daquele eixo vai até perto de 0 de um lado e perto de 255 do outro, e o pontinho encosta na borda do círculo do mesmo lado para onde o seu polegar foi. Soltando, o pontinho volta ao meio e os dois números voltam para o que você anotou no começo, com folga de poucos pontos. Isso nos dois analógicos do P1 e nos dois do P2. E os cartões que você não está tocando não se mexem.

**Por controle.**

* **P1** — No cabo. Anote os quatro números de repouso dele ANTES de tocar em qualquer coisa, e compare no fim. Os dois analógicos vão aos extremos, um eixo de cada vez.
* **P2** — No cabo. Mesma medição do P1, feita depois. Enquanto você mexe no P1, os pontinhos do P2 não podem andar.
* **P3** — No rádio, e você não encosta nele. Testemunha: se o pontinho dele andar enquanto o seu polegar está no P1, o Hefesto está lendo um controle e desenhando no cartão de outro.
* **P4** — No rádio, e você também não encosta. Segunda testemunha, com a mesma conferência do P3.

**A armadilha.** A maior é esperar 128 no repouso. O centro NÃO é 128, e isso está medido nesta bancada: os centros ficam entre 124 e 130, cada aparelho tem o seu, e um deles ainda passeia um ponto ao longo de minutos. Quem reprovar porque não voltou para 128 reprova um produto certo — e o Hefesto foi consertado justamente para LER o repouso do aparelho em vez de escrever 128. A segunda é o contrário e é mais perigosa: um cartão sem leitura mostra os dois analógicos exatamente no meio e parados para sempre, e um número plausível e congelado se parece com um controle que ninguém está tocando. A diferença se vê apertando o Cruz do mesmo controle: se o desenho do Cruz acende e o analógico continua parado, o achado é do analógico; se nada acende, o achado é a falta de leitura naquele cartão. E não confunda com o pontinho do touchpad, que fica no desenho do touchpad e só aparece quando há dedo encostado.

---

## mapa-entrada.stick-radio — Sticks analógicos (dois eixos por stick) · rádio

*Célula:* `entrada.stick @ rádio`

**O que isto prova.** Prova que os dois analógicos de um controle no rádio entregam a posição real do polegar, e que o repouso deles é lido do aparelho em vez de inventado.

**Onde olhar.** Na aba Controles, dentro do cartão de cada controle, ao lado do desenho. Ficam ali Analógico esquerdo, com a marca L3, e Analógico direito, com a marca R3. Cada um tem um círculo com um pontinho dentro e dois números: X: e Y:. O pontinho anda dentro do círculo acompanhando o polegar, e cada número vai de 0 a 255. E no alto de qualquer aba, a contagem dos ligados: 4 controles: 2 USB · 2 BT.

**Os passos.**

1. Abra o Hefesto e clique na aba Controles.
2. Clique no chip Todos, na fita do topo, para abrir os quatro cartões.
3. Leia a contagem no alto e anote o que ela diz.
4. Largue os quatro controles na mesa, sem encostar em analógico nenhum, e anote num papel os quatro números de repouso do P3 e os quatro do P4: X e Y do esquerdo, X e Y do direito.
5. Pegue o P3 e empurre o analógico esquerdo devagar até o fim, para um lado e depois para o outro, acompanhando o número X.
6. Confira que o número X foi a um extremo de cada vez e que o pontinho encostou na borda do círculo do mesmo lado do seu polegar.
7. Empurre o mesmo analógico até o fim para cima e depois até o fim para baixo, acompanhando o número Y.
8. Confira que o número Y foi aos dois extremos.
9. Solte o analógico.
10. Confira que o pontinho voltou ao meio e que os dois números voltaram para perto do que você anotou.
11. Repita esses mesmos três gestos com o analógico DIREITO do P3: os dois lados, cima e baixo, e soltar.
12. Veja os cartões do P1, do P2 e do P4 durante os empurrões: os pontinhos deles têm de ficar parados.
13. Largue o P3, pegue o P4 e refaça nele os dois analógicos do mesmo jeito.
14. Leia a contagem no alto de novo: ela tem de continuar dizendo quatro controles.

**Passa quando.** Empurrando um analógico até um extremo, o número daquele eixo vai até perto de 0 de um lado e perto de 255 do outro, e o pontinho encosta na borda do círculo do mesmo lado para onde o seu polegar foi. Soltando, o pontinho volta ao meio e os números voltam para o que você anotou. Isso nos dois analógicos do P3 e nos dois do P4 — sem atraso visível entre o polegar e o pontinho. E a contagem do alto continua dizendo quatro controles do começo ao fim. Se algum eixo não alcançar os extremos, anote qual é ele e em qual dos dois controles do rádio: é esse o achado que o teste devolve.

**Por controle.**

* **P1** — No cabo, e você não encosta nele. Testemunha, e referência: se o pontinho do P3 não andar, mexa no analógico do P1 e veja se o dele anda — assim você separa um defeito do rádio de um defeito da leitura inteira.
* **P2** — No cabo, e você também não encosta. Segunda testemunha do cabo, com a mesma conferência do P1.
* **P3** — No rádio. Anote os quatro números de repouso dele ANTES de tocar em qualquer coisa, e compare no fim. Os dois analógicos vão aos extremos, um eixo de cada vez.
* **P4** — No rádio. Mesma medição do P3, feita depois. É o último da fila do Hefesto: se o pontinho dele for o único parado, o achado é do quarto lugar, e não do rádio.

**A armadilha.** A maior é esperar 128 no repouso. O centro NÃO é 128, e isso está medido nesta bancada nos dois transportes: os centros ficam entre 124 e 130, cada aparelho tem o seu, e um deles passeia um ponto ao longo de minutos. Reprovar porque não voltou para 128 é reprovar um produto certo. A segunda: cartão sem leitura mostra os dois analógicos exatamente no meio e parados para sempre — um número plausível e congelado se parece com um controle largado. A diferença se vê apertando o Cruz do mesmo controle: se o Cruz acende e o analógico não anda, o achado é do analógico; se nada acende, é falta de leitura. Terceira, só do rádio: se um cartão inteiro parar no meio do teste, olhe a contagem no alto antes de reprovar — três controles quer dizer que a conexão caiu, e o teste se refaz. E não confunda com o pontinho do touchpad, que fica no desenho do touchpad e só aparece com dedo encostado.

---

## mapa-gatilho.adaptativo-cabo — Gatilhos adaptativos (resistência por zona) — os dois · cabo

*Célula:* `gatilho.adaptativo @ cabo`

**O que isto prova.** Prova que o L2 e o R2 do mesmo controle ficam duros AO MESMO TEMPO nos dois controles do cabo, sem um lado apagar o outro.

**Onde olhar.** Na aba Gatilhos, dentro do quadro "Seleção de Gatilho". Cada controle é uma coluna, com o chip dele no alto: o número, a cor do plástico e a palavra cabo ou rádio. A coluna da esquerda nomeia as linhas: primeiro "Controle" e depois duas seções, cada uma titulada por um desenho — o de cima é o L2, o de baixo é o R2. Dentro de cada seção vêm três linhas: "Modo", "Efeito pronto" e "Ajustes". Mas quem responde este teste é a sua mão, e não a tela: o DualSense não devolve em que efeito ele está, então o campo "Modo" mostra o que foi PEDIDO, nunca o que está no aparelho. O único sinal que a tela dá é o campo piscar em verde por cerca de um segundo e meio quando o comando chega ao controle — e piscar quer dizer "saiu daqui", não "o gatilho está duro agora".

**Os passos.**

1. Abra a aba Gatilhos.
2. Aperte o L2 e o R2 dos quatro controles até o fundo, um controle por vez, e guarde na mão como cada um está agora.
3. Confira que a coluna do P1 e a do P2 terminam, no alto, na palavra cabo.
4. Abra o campo "Modo" da seção de CIMA (a do desenho L2), na coluna do P1, e escolha «Rígido».
5. Veja o campo piscar em verde.
6. Aperte o L2 do P1 e depois o R2 do mesmo controle, um de cada vez.
7. Confira que o L2 trava duro do começo ao fim do curso e que o R2 continua leve — o efeito pegou um lado só.
8. Abra o campo "Modo" da seção de BAIXO (a do desenho R2), na mesma coluna do P1, e escolha «Rígido».
9. Aperte o L2 e o R2 do P1 ao mesmo tempo, com dois dedos; depois solte e aperte de novo um de cada vez.
10. Confira que os dois estão duros e que nenhum amoleceu quando o outro foi ligado.
11. Repita na coluna do P2 tudo o que você fez na do P1, do «Rígido» no L2 até os dois gatilhos apertados juntos.
12. Aperte o L2 e o R2 do P3 e depois os do P4.
13. Compare com o que você sentiu no começo: os quatro têm de estar iguais ao que estavam.
14. Escolha «Desligado» no "Modo" das duas seções da coluna do P1 e das duas da coluna do P2, e aperte os quatro gatilhos do P1 e do P2 de novo.
15. Confira que todos voltaram a ficar leves.

**Passa quando.** No P1 e no P2 — os dois do cabo — o L2 e o R2 ficam duros ao mesmo tempo, e continuam duros quando você aperta um de cada vez: ligar o segundo lado não soltou o primeiro. Os gatilhos do P3 e do P4 continuam exatamente como estavam antes, nenhum endureceu. E, ao escolher «Desligado» nas duas seções dos dois controles, os quatro gatilhos voltam a ficar leves na sua mão.

**Por controle.**

* **P1** — No CABO, e é o primeiro em que você mexe. Ponha «Rígido» no "Modo" da seção de cima (L2), sinta só o L2 travar, depois ponha «Rígido» na seção de baixo (R2) e sinta os dois travados ao mesmo tempo, com dois dedos. No fim, «Desligado» nas duas seções.
* **P2** — No CABO, e é o segundo. Os mesmos gestos, na coluna dele. Ele é quem separa "o cabo funciona" de "aquele controle funciona": se der certo no P1 e não no P2, o defeito é do aparelho, não do transporte.
* **P3** — No RÁDIO, testemunha. Não toque na coluna dele. Aperte o L2 e o R2 antes e depois; têm de estar iguais nas duas vezes. Se ele endurecer junto, o comando pegou todo mundo em vez do controle escolhido.
* **P4** — No RÁDIO, segunda testemunha. Não toque na coluna dele. Aperte o L2 e o R2 antes e depois. Se o P3 ficou intacto e o P4 endureceu, o comando não vazou pelo transporte — foi parar no controle errado, que é outro defeito.

**A armadilha.** Não use «Desligado» como o efeito do teste. Ele é a escolha que SOLTA o gatilho: se ela vazar para os quatro controles você não vê nada, porque os outros já estavam soltos. O efeito tem de ser um que ENDUREÇA, porque endurecer é o que a mão sente. E não julgue pela tela: o campo "Modo" continua mostrando «Rígido» mesmo se um jogo escrever por cima e o gatilho estiver leve no seu dedo — o campo mostra o pedido, nunca o aparelho. Duas coisas mais, e as duas já foram medidas nesta casa. A primeira: o efeito NÃO é eterno. Alguns MINUTOS depois de aplicado ele amanhece solto sozinho, sem ninguém tocar, e até hoje ninguém achou quem o apaga; então sinta LOGO depois de escolher, e se você voltar meia hora depois e estiver leve, isso é o defeito conhecido e não erro seu. A segunda: aplicar qualquer efeito de gatilho PAUSA a troca automática de perfil, e é o «Desligado» do fim que a devolve — deixar o teste pela metade deixa o Hefesto sem trocar de perfil sozinho, e isso vai parecer outro defeito mais tarde. Por fim, onde a prova desta linha parou: em O APARELHO OBEDECEU, medido com os quatro controles na mesa em 11/08 — o dedo é o degrau certo aqui, e o jogo é o degrau seguinte, que ninguém mediu. Não conclua nada sobre gatilho olhando um jogo.

---

## mapa-gatilho.adaptativo-radio — Gatilhos adaptativos (resistência por zona) — os dois · rádio

*Célula:* `gatilho.adaptativo @ rádio`

**O que isto prova.** Prova que o L2 e o R2 do mesmo controle ficam duros AO MESMO TEMPO nos dois controles do rádio, igual aos do cabo.

**Onde olhar.** Na aba Gatilhos, no quadro "Seleção de Gatilho". Cada controle é uma coluna, com o chip no alto — o número, a cor do plástico e a palavra cabo ou rádio; a do P3 e a do P4 têm de terminar em rádio. A coluna da esquerda nomeia as linhas: "Controle" e depois duas seções tituladas por um desenho, o L2 em cima e o R2 embaixo, cada uma com "Modo", "Efeito pronto" e "Ajustes". No pé de cada coluna há um botãozinho redondo com uma seta girando (↻): ele manda de novo ao controle o L2 e o R2 que estão naquela coluna, e existe justamente para quando o controle volta do rádio. A prova, porém, é a sua mão: o controle não devolve em que efeito está, e o campo "Modo" mostra o que foi pedido. A tela só pisca em verde por cerca de um segundo e meio quando o comando sai.

**Os passos.**

1. Abra a aba Gatilhos.
2. Aperte o L2 e o R2 dos quatro controles até o fundo, um controle por vez, e guarde na mão como cada um está agora.
3. Confira que a coluna do P3 e a do P4 terminam, no alto, na palavra rádio.
4. Ponha «Rígido» no campo "Modo" da seção de CIMA (a do desenho L2), na coluna do P3.
5. Veja o campo piscar em verde.
6. Aperte o L2 do P3 e depois o R2 do mesmo controle, um de cada vez.
7. Confira que o L2 travou duro do começo ao fim do curso e que o R2 continua leve — o efeito pegou um lado só.
8. Ponha «Rígido» no campo "Modo" da seção de BAIXO (a do desenho R2), na mesma coluna do P3.
9. Aperte o L2 e o R2 do P3 ao mesmo tempo, com dois dedos; depois solte e aperte de novo um de cada vez.
10. Confira que os dois estão duros e que ligar o segundo lado não soltou o primeiro.
11. Repita na coluna do P4 tudo o que você fez na do P3, do «Rígido» no L2 até os dois gatilhos apertados juntos com dois dedos.
12. Aperte o L2 e o R2 do P1 e depois os do P2.
13. Compare com o que você guardou na mão no começo: os quatro têm de estar iguais.
14. Clique no botãozinho da seta girando (↻) no pé da coluna do P3 e aperte o L2 e o R2 dele de novo.
15. Confira que os dois continuam duros depois do reenvio.
16. Ponha «Desligado» no "Modo" das duas seções da coluna do P3 e das duas da coluna do P4, e aperte os quatro gatilhos de novo.
17. Confira que todos voltaram a ficar leves.

**Passa quando.** No P3 e no P4 — os dois do rádio — o L2 e o R2 ficam duros ao mesmo tempo, e continuam duros quando você aperta um de cada vez. A sensação é a mesma que os controles do cabo dão: sem fio não pode ser mais fraco nem chegar depois. Os gatilhos do P1 e do P2 continuam exatamente como estavam. E «Desligado» nas duas seções solta os quatro gatilhos.

**Por controle.**

* **P1** — No CABO, testemunha. Não toque na coluna dele. Aperte o L2 e o R2 antes e depois; têm de estar iguais. Se ele endurecer junto, o comando pegou todo mundo em vez do controle escolhido.
* **P2** — No CABO, segunda testemunha. Não toque na coluna dele. Aperte o L2 e o R2 antes e depois. Se o P1 ficou intacto e o P2 endureceu, o comando foi parar no controle errado.
* **P3** — No RÁDIO, e é o primeiro em que você mexe. Ponha «Rígido» na seção de cima (L2), sinta só ele travar, depois ponha «Rígido» na de baixo (R2) e sinta os dois duros com dois dedos. É nele que você também clica na seta girando (↻), para ver se o reenvio mantém o efeito.
* **P4** — No RÁDIO, e é o segundo. Os mesmos gestos, na coluna dele. Ele separa "o rádio funciona" de "aquele controle funciona": se o P3 obedecer e o P4 não, o defeito é do aparelho, não do sem fio.

**A armadilha.** Não use «Desligado» como o efeito do teste: ele é a escolha que SOLTA, e vazar solto num gatilho já solto não se enxerga. E não julgue pela tela — o campo "Modo" mostra o pedido, não o aparelho; a piscada verde diz que o comando saiu, não que o gatilho está duro. Três avisos que valem especialmente aqui. Primeiro: o efeito NÃO é eterno, e isso já foi medido — alguns MINUTOS depois ele amanhece solto sozinho, sem ninguém tocar, e ninguém achou ainda quem o apaga; sinta LOGO depois de escolher. Segundo: se um controle do rádio cair e voltar no meio do teste, o efeito não volta com ele — o botãozinho da seta girando (↻) no pé da coluna é o caminho de mandá-lo de novo, e é por isso que ele está nos passos. Terceiro: aplicar qualquer efeito PAUSA a troca automática de perfil, e é o «Desligado» do fim que a devolve. Onde a prova parou: em O APARELHO OBEDECEU, medido em 11/08 com dois controles no rádio na mesa — o dedo é o degrau certo. O jogo é o degrau seguinte e ninguém o mediu, então não tente concluir nada sobre gatilho por dentro de um jogo. E a razão de este teste ter NOVE atos, um a mais que o alvo de oito: o excedente é o botãozinho da seta girando (↻), que só existe deste lado — no gêmeo do cabo não há reenvio a testar. Tirá-lo daqui apagaria justamente o passo que responde ao controle que cai e volta, que é o defeito próprio do rádio.

---

## mapa-gatilho.analogico-cabo — Gatilhos analógicos (eixo de curso em ZL/ZR ou L2/R2) · cabo

*Célula:* `gatilho.analogico @ cabo`

**O que isto prova.** Prova que o Hefesto lê o CURSO do L2 e do R2 dos dois controles do cabo — o quanto o dedo apertou, e não só apertou ou não apertou.

**Onde olhar.** Na aba Controles. Clique na linha de um controle para abrir o cartão dele — é um acordeão, então abrir um fecha o anterior; para ver os quatro abertos ao mesmo tempo, clique no chip "Todos" da fita do topo. Dentro do cartão, no canto de baixo, há um quadro chamado "Gatilhos" com duas linhas, L2 e R2. Cada linha tem uma barra que enche e um número escrito assim: "200 / 255". É esse número que responde este teste. Mais acima, no mesmo cartão, fica a grade dos dezesseis desenhos de botão, e os desenhos L2 e R2 acendem — mas só depois de o número passar de 30.

**Os passos.**

1. Abra a aba Controles.
2. Clique no chip "Todos" da fita do topo, para os quatro cartões ficarem abertos ao mesmo tempo.
3. Confira que a linha do P1 e a do P2 dizem cabo.
4. Vá à aba Gatilhos e ponha o "Modo" das duas seções do P1 e do P2 em «Desligado» — senão você mede o efeito, e não o curso.
5. Volte à aba Controles.
6. Leia o número da linha L2 no quadro "Gatilhos" do cartão do P1, com o dedo fora do gatilho: tem de ser 0 / 255.
7. Aperte o L2 do P1 bem devagar, do ponto solto até a metade do curso, e pare com o dedo ali.
8. Veja o número subir junto com o dedo e parar num valor do meio, sem pular direto para 255.
9. Empurre o L2 do P1 até o fundo e solte.
10. Confira que o número chega a 255 no fundo e volta a 0 quando você solta.
11. Repita esses dois apertos no R2 do P1 e nos dois gatilhos do P2.
12. Veja os números do P3 e do P4 durante todos esses apertos: nenhum deles pode se mexer.
13. Encoste levemente no L2 do P1, só o suficiente para o número sair do zero sem passar de 30.
14. Confira que o desenho do L2 lá em cima ainda NÃO acendeu.
15. Aperte mais fundo o L2 do P1.
16. Confira que agora o desenho acende.

**Passa quando.** No P1 e no P2, o número da linha do gatilho que você está apertando caminha por valores do meio entre 0 e 255 — ele não pula de 0 para 255 —, sobe conforme você aperta mais fundo, chega a 255 no fim do curso e volta a 0 quando você solta. Os números do P3 e do P4 não se mexem em momento nenhum. E o desenho do L2 lá em cima só acende depois que o número passa de 30.

**Por controle.**

* **P1** — No CABO, e é o primeiro. Aperte o L2 e depois o R2, devagar, parando na metade, e leia os dois números do quadro "Gatilhos" do cartão dele.
* **P2** — No CABO, e é o segundo. Os mesmos gestos, no cartão dele. Ele separa "o cabo lê o curso" de "aquele controle lê o curso": se o P1 andar e o P2 ficar parado, o defeito é do aparelho, não do transporte.
* **P3** — No RÁDIO, testemunha. Não encoste nele. Os números do L2 e do R2 no cartão dele têm de ficar parados em 0 enquanto você aperta os do cabo. Se andarem junto, a tela está mostrando o controle errado.
* **P4** — No RÁDIO, segunda testemunha. Não encoste nele. Mesma conferência: números parados. Se o P3 ficou parado e o P4 andou, o problema não é do rádio — é de alguma coisa apontando o número para o cartão errado.

**A armadilha.** O falso vermelho mais fácil é medir com efeito ligado: um gatilho em «Rígido» trava num ponto do curso e o número trava junto, e você conclui que a leitura quebrou quando quem travou foi o gatilho — por isso as duas seções do P1 e do P2 vão para «Desligado» na aba Gatilhos antes de começar. Dois outros que parecem defeito e não são: com o cartão FECHADO o quadro "Gatilhos" não aparece, então um cartão fechado não é leitura falhando, é cartão fechado; e o desenho do L2 lá em cima acende só depois de 30 de 255, então um toque leve mexe o número sem acender o desenho — isso é o limiar, não um erro. O falso verde é olhar um número só: se os quatro números ficarem congelados no MESMO valor o tempo todo, ninguém leu nada. Onde a prova desta linha parou, e isto é o mais importante: o mapa NÃO registra grau para esta célula — ninguém anotou até onde a prova chegou. O que existe é leitura de código mais três documentações externas que concordam sobre qual byte carrega o curso. Então o número na tela do Hefesto é exatamente o degrau que este teste alcança: não tente provar o curso do gatilho por dentro de um jogo, porque ninguém mediu esse degrau.

---

## mapa-gatilho.analogico-radio — Gatilhos analógicos (eixo de curso em ZL/ZR ou L2/R2) · rádio

*Célula:* `gatilho.analogico @ rádio`

**O que isto prova.** Prova que o Hefesto lê o CURSO do L2 e do R2 dos dois controles do rádio, com a mesma fidelidade dos do cabo.

**Onde olhar.** Na aba Controles. Clique na linha de um controle para abrir o cartão dele — abrir um fecha o anterior; para ver os quatro abertos ao mesmo tempo, clique no chip "Todos" da fita do topo. Dentro do cartão há um quadro chamado "Gatilhos", com duas linhas, L2 e R2, cada uma com uma barra que enche e um número no formato "200 / 255". É esse número que responde. Mais acima, no mesmo cartão, a grade dos dezesseis desenhos de botão: os desenhos L2 e R2 acendem, mas só depois de o número passar de 30.

**Os passos.**

1. Abra a aba Controles.
2. Clique no chip "Todos" da fita do topo, para os quatro cartões ficarem abertos ao mesmo tempo.
3. Confira que a linha do P3 e a do P4 dizem rádio.
4. Abra a aba Gatilhos e confira que o "Modo" das duas seções do P3 e do P4 está em «Desligado» — se não estiver, ponha, senão você mede o efeito e não o curso.
5. Volte à aba Controles.
6. Ache o quadro "Gatilhos" dentro do cartão do P3 e leia o número da linha L2 com o dedo fora do gatilho: tem de ser 0 / 255.
7. Aperte o L2 do P3 bem devagar, do ponto solto até o fundo, olhando o número subir.
8. Pare com o dedo na metade do curso e leia o número: tem de parar num valor do meio, e não pular direto para 255.
9. Empurre até o fundo e confirme que o número chega a 255.
10. Solte o L2 e confirme que o número volta a 0.
11. Repita os passos 6 a 10 com o R2 do P3.
12. Repita os passos 6 a 11 com o P4.
13. Olhe os números do P1 e do P2 durante todos esses apertos e confirme que nenhum deles se mexeu.
14. Compare a subida do número no P3 com a que você viu num controle do cabo: tem de ser o mesmo caminho de 0 a 255, sem degraus grandes nem atraso visível.
15. Encoste levemente no L2 do P3, só até o número sair do zero sem passar de 30, e confira que o desenho do L2 lá em cima ainda NÃO acendeu.

**Passa quando.** No P3 e no P4, o número da linha do gatilho que você está apertando caminha por valores do meio entre 0 e 255, sobe conforme você aperta mais fundo, chega a 255 no fundo e volta a 0 quando você solta — do mesmo jeito que num controle do cabo. Os números do P1 e do P2 não se mexem em momento nenhum.

**Por controle.**

* **P1** — No CABO, testemunha. Não encoste nele. Os números do L2 e do R2 no cartão dele têm de ficar parados em 0 enquanto você aperta os do rádio.
* **P2** — No CABO, segunda testemunha. Não encoste nele. Mesma conferência. Se o P1 ficou parado e o P2 andou, alguma coisa está escrevendo o número no cartão errado.
* **P3** — No RÁDIO, e é o primeiro. Aperte o L2 e depois o R2, devagar, parando na metade, e leia os dois números do quadro "Gatilhos" do cartão dele. É aqui que se compara com o cabo.
* **P4** — No RÁDIO, e é o segundo. Os mesmos gestos, no cartão dele. Ele separa "o rádio lê o curso" de "aquele controle lê o curso": se o P3 andar e o P4 ficar parado, o defeito é do aparelho, não do sem fio.

**A armadilha.** O falso vermelho mais fácil é medir com efeito ligado: um gatilho em «Rígido» trava num ponto do curso e o número trava junto — por isso o passo 4 manda pôr as duas seções em «Desligado» antes de começar. Outros dois que parecem defeito e não são: com o cartão fechado o quadro "Gatilhos" não aparece; e o desenho do L2 acende só depois de 30 de 255, então um toque leve mexe o número sem acender o desenho. E há uma armadilha que é só do rádio, declarada na fonte: pelo sem fio o DualSense fala em DOIS desenhos de mensagem, um curto que ele emite antes de entrar no modo completo e o completo, e o curso do gatilho não fica no mesmo lugar nos dois — é o único dado de entrada que muda de posição entre os dois desenhos. A fonte não diz que sintoma isso produz na tela; então, se o número do P3 ou do P4 vier congelado ou visivelmente errado logo depois de o controle voltar ao rádio, anote com a hora, porque é exatamente o ponto onde o mapa avisa que os dois desenhos discordam. Onde a prova parou: o mapa NÃO registra grau para esta célula — ninguém anotou até onde a prova chegou; o que existe é leitura de código e três documentações externas que concordam sobre o byte. O número na tela do Hefesto é o degrau que este teste alcança; não tente provar o curso por dentro de um jogo.

---

## mapa-gatilho.direito.adaptativo-cabo — Gatilho adaptativo DIREITO · cabo

*Célula:* `gatilho.direito.adaptativo @ cabo`

**O que isto prova.** Prova que um efeito posto no gatilho DIREITO endurece só o R2 dos controles do cabo, e deixa o L2 do mesmo controle solto.

**Onde olhar.** Na aba Gatilhos, quadro "Seleção de Gatilho". A coluna da esquerda nomeia as linhas, e a seção de BAIXO é a do R2 — ela é titulada pelo desenho R2, e dentro dela vêm "Modo", "Efeito pronto" e "Ajustes". A seção de cima, a do L2, não se toca neste teste. Em "Ajustes", com «Rígido» escolhido, aparecem duas barras com nome e número: "Posição" e "Força"; numa coluna que tem controle elas são arrastáveis, e a alavanca é invisível — arrasta-se em cima da linha da própria barra. Quem responde o teste, porém, é a sua mão: o controle não devolve em que efeito ele está, e o campo "Modo" mostra só o que foi pedido. A tela apenas pisca em verde por cerca de um segundo e meio quando o comando sai.

**Os passos.**

1. Abra a aba Gatilhos.
2. Aperte o L2 e o R2 dos quatro controles até o fundo, um controle por vez, e guarde na mão como cada um está.
3. Confira que a coluna do P1 e a do P2 terminam, no alto, na palavra cabo.
4. Abra o campo "Modo" da seção de BAIXO (a do desenho R2), na coluna do P1, e escolha «Rígido».
5. Veja o campo piscar em verde.
6. Aperte o R2 do P1 e depois o L2 do mesmo controle, na mesma mão, um de cada vez.
7. Confira que o R2 trava duro do começo ao fim do curso e que o L2 continua leve.
8. Arraste a barra "Força" dos "Ajustes" do R2 do P1 até o fim da direita, em cima da linha da barra.
9. Aperte o R2 do P1 de novo.
10. Confira que a trava ficou mais firme do que estava.
11. Repita na coluna do P2 o que você fez na do P1 antes da "Força": «Rígido» na seção de baixo, e o R2 e o L2 apertados um de cada vez.
12. Aperte o R2 e o L2 do P3 e depois os do P4.
13. Compare com o que você sentiu no começo: os quatro têm de estar iguais ao que estavam.
14. Escolha «Desligado» no "Modo" da seção de baixo (R2) da coluna do P1 e da coluna do P2, e aperte os dois R2 de novo.
15. Confira que os dois voltaram a ficar leves.

**Passa quando.** O R2 do P1 e o do P2 ficam duros, e o L2 dos MESMOS controles continua leve — o comando agiu num lado só e não vazou para o outro lado da mesma mão. Os gatilhos do P3 e do P4 continuam exatamente como estavam. Puxar a "Força" até o fim deixa a trava mais firme do que estava. E «Desligado» na seção do R2 solta os dois R2.

**Por controle.**

* **P1** — No CABO, e é o primeiro. Mexe-se só na seção de BAIXO (R2) da coluna dele. O R2 tem de endurecer e o L2 do mesmo controle é a testemunha na mesma mão — é ele que prova que o comando não pegou os dois lados.
* **P2** — No CABO, e é o segundo. Os mesmos gestos, na coluna dele. Ele separa "o cabo funciona" de "aquele controle funciona": se o R2 do P1 endurecer e o do P2 não, o defeito é do aparelho.
* **P3** — No RÁDIO, testemunha. Não toque na coluna dele. Aperte o R2 e o L2 antes e depois; têm de estar iguais. Se o R2 dele endurecer, o comando pegou todo mundo em vez do controle escolhido.
* **P4** — No RÁDIO, segunda testemunha. Não toque na coluna dele. Mesma conferência. Se o P3 ficou intacto e o R2 do P4 endureceu, o comando foi para o controle errado.

**A armadilha.** A armadilha maior deste teste é apertar o gatilho errado. O R2 é o de baixo do lado DIREITO do controle, e a seção da tela é a de BAIXO, titulada pelo desenho R2. Quem mexe na seção de cima e aperta o R2 conclui que o produto errou de lado quando quem errou foi o gesto — confira o desenho que titula a seção antes de abrir o campo. Não use «Desligado» como o efeito do teste: ele SOLTA, e um vazamento de solto não se enxerga. Não julgue pela tela: o campo "Modo" mostra o pedido, e a piscada verde diz que o comando saiu, não que o gatilho está duro. E a medição que sustenta esta linha exercitou UM modo só, «Rígido», com um único jogo de números — nenhum dos outros dezoito foi tocado por lá, e é por isso que o teste pede «Rígido». Duas coisas medidas que parecem erro seu e não são: o efeito NÃO é eterno, e alguns MINUTOS depois ele amanhece solto sozinho sem ninguém tocar; e aplicar qualquer efeito PAUSA a troca automática de perfil, que só volta com o «Desligado» do fim. Onde a prova parou: em O APARELHO OBEDECEU, medido em 11/08 com os quatro na mesa e o lado ocioso servindo de controle negativo — o dedo é o degrau certo. O jogo é o degrau seguinte e ninguém o mediu.

---

## mapa-gatilho.direito.adaptativo-radio — Gatilho adaptativo DIREITO · rádio

*Célula:* `gatilho.direito.adaptativo @ rádio`

**O que isto prova.** Prova que um efeito posto no gatilho DIREITO endurece só o R2 dos controles do rádio, e deixa o L2 do mesmo controle solto.

**Onde olhar.** Na aba Gatilhos, quadro "Seleção de Gatilho". A coluna do P3 e a do P4 têm de terminar, no alto, na palavra rádio. A seção de BAIXO da coluna da esquerda é a do R2, titulada pelo desenho R2, com "Modo", "Efeito pronto" e "Ajustes"; a de cima é a do L2 e não se toca. Em "Ajustes", com «Rígido» escolhido, aparecem as barras "Posição" e "Força", arrastáveis em cima da própria linha da barra. No pé de cada coluna há um botãozinho redondo com uma seta girando (↻), que manda de novo ao controle o L2 e o R2 daquela coluna — ele existe justamente para quando o controle volta do rádio. A prova é a sua mão: o controle não devolve em que efeito está, e o campo "Modo" mostra só o pedido; a tela pisca em verde por cerca de um segundo e meio quando o comando sai.

**Os passos.**

1. Abra a aba Gatilhos.
2. Confira que a coluna do P3 e a do P4 terminam, no alto, na palavra rádio.
3. Aperte o L2 e o R2 dos quatro controles até o fundo e guarde na mão como cada um está hoje.
4. Escolha «Rígido» no campo "Modo" da seção de BAIXO (a do desenho R2), na coluna do P3.
5. Veja o campo piscar em verde.
6. Aperte o R2 do P3 e, no mesmo controle e na mesma mão, o L2 dele.
7. Confira que o R2 trava duro do começo ao fim do curso e que o L2 continua leve.
8. Compare a firmeza do R2 do P3 com a de um controle do cabo que você já tenha sentido em «Rígido»: pelo rádio não pode ser mais fraco nem demorar mais a chegar.
9. Refaça os atos 2 e 3 na coluna do P4.
10. Clique no botãozinho da seta girando (↻) no pé da coluna do P3.
11. Aperte o R2 e o L2 do P3 de novo.
12. Confira que o R2 continua duro e que o L2 continua leve.
13. Aperte o R2 e o L2 do P1 e os do P2.
14. Compare com o que você guardou no ato 1: os gatilhos das duas testemunhas têm de estar exatamente como estavam.
15. Escolha «Desligado» no "Modo" da seção de baixo (R2) das colunas do P3 e do P4.
16. Aperte o R2 do P3 e o do P4.
17. Confira que os dois voltaram a ficar leves.

**Passa quando.** O R2 do P3 e o do P4 ficam duros, e o L2 dos MESMOS controles continua leve — o comando agiu num lado só, pelo sem fio, e não vazou para o outro lado da mesma mão. A firmeza é a mesma que um controle do cabo dá. Os gatilhos do P1 e do P2 continuam exatamente como estavam. E «Desligado» na seção do R2 solta os dois R2.

**Por controle.**

* **P1** — No CABO, testemunha. Não toque na coluna dele. Aperte o R2 e o L2 antes e depois; têm de estar iguais. Se o R2 dele endurecer, o comando pegou todo mundo.
* **P2** — No CABO, segunda testemunha. Não toque na coluna dele. Mesma conferência. Se o P1 ficou intacto e o R2 do P2 endureceu, o comando foi para o controle errado.
* **P3** — No RÁDIO, e é o primeiro. Mexe-se só na seção de BAIXO (R2) da coluna dele. O R2 endurece; o L2 do mesmo controle é a testemunha na mesma mão. É nele que você clica na seta girando (↻), para ver se o reenvio mantém o efeito e continua respeitando o lado.
* **P4** — No RÁDIO, e é o segundo. Os mesmos gestos, na coluna dele. Ele separa "o rádio funciona" de "aquele controle funciona": se o R2 do P3 endurecer e o do P4 não, o defeito é do aparelho, não do sem fio.

**A armadilha.** Este teste tem NOVE atos de propósito: ele mede o mesmo dedo em três momentos — antes do efeito, com o efeito posto e depois de desfeito — nos quatro controles, e ainda prova o botão de reenvio; tirar qualquer um dos três momentos deixa o teste sem o antes ou sem o depois, e ele passa a dar verde sem prova. A armadilha maior é apertar o gatilho errado: o R2 é o de baixo do lado DIREITO, e a seção da tela é a de BAIXO, titulada pelo desenho R2 — quem mexe na seção de cima e aperta o R2 conclui que o produto errou de lado quando quem errou foi o gesto. Não use «Desligado» como o efeito do teste, e não julgue pela tela: o campo "Modo" mostra o pedido e a piscada verde diz que o comando saiu, nada mais. A medição que sustenta esta linha exercitou UM modo só, «Rígido», com um único jogo de números; os outros dezoito não foram tocados por lá. Duas coisas já medidas que parecem erro seu e não são: se o controle do rádio cair e voltar no meio do teste, o efeito não volta com ele — o botãozinho da seta girando (↻) é o caminho de mandá-lo de novo, e por isso está nos atos; e o efeito NÃO é eterno, amanhecendo solto sozinho depois de alguns MINUTOS, sem ninguém tocar. Aplicar qualquer efeito também PAUSA a troca automática de perfil, que só volta com o «Desligado» do fim. Onde a prova parou: em O APARELHO OBEDECEU, medido em 11/08 com dois controles no rádio na mesa — o dedo é o degrau certo, e o jogo é o degrau seguinte, que ninguém mediu.

---

## mapa-gatilho.esquerdo.adaptativo-cabo — Gatilho adaptativo ESQUERDO · cabo

*Célula:* `gatilho.esquerdo.adaptativo @ cabo`

**O que isto prova.** Prova que um efeito posto no gatilho ESQUERDO endurece só o L2 dos controles do cabo, e deixa o R2 do mesmo controle solto.

**Onde olhar.** Na aba Gatilhos, quadro "Seleção de Gatilho". A coluna da esquerda nomeia as linhas, e a seção de CIMA é a do L2 — titulada pelo desenho L2, com "Modo", "Efeito pronto" e "Ajustes" dentro dela. A seção de baixo, a do R2, não se toca neste teste. Em "Ajustes", com «Rígido» escolhido, aparecem duas barras com nome e número: "Posição" e "Força"; numa coluna que tem controle elas são arrastáveis, e a alavanca é invisível — arrasta-se em cima da linha da própria barra. Quem responde é a sua mão: o controle não devolve em que efeito está, e o campo "Modo" mostra só o pedido. A tela pisca em verde por cerca de um segundo e meio quando o comando sai.

**Os passos.**

1. Abra a aba Gatilhos.
2. Confira que a coluna do P1 e a do P2 terminam, no alto, na palavra cabo.
3. Aperte o L2 e o R2 dos quatro controles até o fundo, um controle de cada vez, e guarde na mão como cada um está.
4. Abra o campo "Modo" da seção de CIMA — a do desenho L2 — na coluna do P1 e escolha «Rígido».
5. Veja o campo piscar em verde: é o comando saindo.
6. Aperte o L2 do P1.
7. Confira que ele trava duro do começo ao fim do curso.
8. Aperte o R2 do P1, no mesmo controle e na mesma mão.
9. Confira que ele continua leve — é a testemunha do outro lado da mesma mão.
10. Arraste a barra "Força" dos "Ajustes" do L2 do P1 até o fim da direita, em cima da linha da barra.
11. Aperte o L2 do P1 de novo.
12. Confira se a trava ficou mais firme.
13. Repita os atos 2 a 4 na coluna do P2.
14. Confira, apertando o L2 e o R2 do P3 e depois os do P4, que os quatro gatilhos estão como você guardou no ato 1.
15. Escolha «Desligado» no "Modo" da seção de cima (L2) da coluna do P1 e no da mesma seção da coluna do P2.
16. Confira, apertando o L2 dos dois, que voltaram a ficar leves.

**Passa quando.** O L2 do P1 e o do P2 ficam duros, e o R2 dos MESMOS controles continua leve — o comando agiu num lado só e não vazou para o outro lado da mesma mão. Os gatilhos do P3 e do P4 continuam exatamente como estavam. Puxar a "Força" até o fim deixa a trava mais firme. E «Desligado» na seção do L2 solta os dois L2.

**Por controle.**

* **P1** — No CABO, e é o primeiro. Mexe-se só na seção de CIMA (L2) da coluna dele. O L2 tem de endurecer e o R2 do mesmo controle é a testemunha na mesma mão — é ele que prova que o comando não pegou os dois lados.
* **P2** — No CABO, e é o segundo. Os mesmos gestos, na coluna dele. Ele separa "o cabo funciona" de "aquele controle funciona": se o L2 do P1 endurecer e o do P2 não, o defeito é do aparelho.
* **P3** — No RÁDIO, testemunha. Não toque na coluna dele. Aperte o L2 e o R2 antes e depois; têm de estar iguais. Se o L2 dele endurecer, o comando pegou todo mundo em vez do controle escolhido.
* **P4** — No RÁDIO, segunda testemunha. Não toque na coluna dele. Mesma conferência. Se o P3 ficou intacto e o L2 do P4 endureceu, o comando foi para o controle errado.

**A armadilha.** A armadilha maior deste teste é apertar o gatilho errado. O L2 é o de baixo do lado ESQUERDO do controle, e a seção da tela é a de CIMA, titulada pelo desenho L2. Quem mexe na seção de baixo e aperta o L2 conclui que o produto errou de lado quando quem errou foi o gesto — confira o desenho que titula a seção antes de abrir o campo. Não use «Desligado» como o efeito do teste: ele SOLTA, e um vazamento de solto não se enxerga. Não julgue pela tela: o campo "Modo" mostra o pedido, e a piscada verde diz que o comando saiu, não que o gatilho está duro. E a medição que sustenta esta linha exercitou UM modo só, «Rígido», com um único jogo de números — nenhum dos outros dezoito foi tocado por lá, e é por isso que o teste pede «Rígido». Duas coisas medidas que parecem erro seu e não são: o efeito NÃO é eterno, e alguns MINUTOS depois ele amanhece solto sozinho; e aplicar qualquer efeito PAUSA a troca automática de perfil, que só volta com o «Desligado» do fim. Onde a prova parou: em O APARELHO OBEDECEU, medido em 11/08 com os quatro na mesa e o lado ocioso servindo de controle negativo na mesma mão — o dedo é o degrau certo, e o jogo é o degrau seguinte, que ninguém mediu.

---

## mapa-gatilho.esquerdo.adaptativo-radio — Gatilho adaptativo ESQUERDO · rádio

*Célula:* `gatilho.esquerdo.adaptativo @ rádio`

**O que isto prova.** Prova que um efeito posto no gatilho ESQUERDO endurece só o L2 dos controles do rádio, e deixa o R2 do mesmo controle solto.

**Onde olhar.** Na aba Gatilhos, quadro "Seleção de Gatilho". A coluna do P3 e a do P4 têm de terminar, no alto, na palavra rádio. A seção de CIMA da coluna da esquerda é a do L2, titulada pelo desenho L2, com "Modo", "Efeito pronto" e "Ajustes"; a de baixo é a do R2 e não se toca. Em "Ajustes", com «Rígido» escolhido, aparecem as barras "Posição" e "Força", arrastáveis em cima da própria linha da barra. No pé de cada coluna há um botãozinho redondo com uma seta girando (↻), que manda de novo ao controle o L2 e o R2 daquela coluna — ele existe justamente para quando o controle volta do rádio. A prova é a sua mão: o controle não devolve em que efeito está, e o campo "Modo" mostra só o pedido; a tela pisca em verde por cerca de um segundo e meio quando o comando sai.

**Os passos.**

1. Abra a aba Gatilhos.
2. Confira que a coluna do P3 e a do P4 terminam, no alto, na palavra rádio.
3. Aperte o L2 e o R2 dos quatro controles até o fundo, um controle de cada vez, e guarde na mão como cada um está — o P1 e o P2 são as testemunhas.
4. Abra o campo "Modo" da seção de CIMA — a do desenho L2 — na coluna do P3 e escolha «Rígido».
5. Veja o campo piscar em verde: é o comando saindo.
6. Aperte o L2 do P3 até o fundo do curso.
7. Confira que a trava é dura do começo ao fim do curso.
8. Compare essa firmeza com a de um controle do cabo que você já tenha sentido em «Rígido»: pelo rádio não pode ser mais fraca nem demorar mais a chegar.
9. Aperte o R2 do P3, no mesmo controle e na mesma mão.
10. Confira que ele continua leve — é a testemunha do outro lado da mesma mão.
11. Repita a abertura do "Modo" e a escolha de «Rígido» na seção de CIMA (L2) da coluna do P4.
12. Aperte o L2 e depois o R2 do P4, do mesmo jeito.
13. Confira que o L2 do P4 ficou duro e que o R2 dele continua leve.
14. Aperte o L2 e o R2 do P1 e depois os do P2.
15. Confira que os quatro gatilhos das testemunhas estão como você guardou no começo.
16. Clique no botãozinho da seta girando (↻) no pé da coluna do P3.
17. Aperte o L2 e o R2 do P3 outra vez.
18. Confira que o L2 continua duro e o R2 continua leve depois do reenvio.
19. Escolha «Desligado» no "Modo" da seção de cima (L2) da coluna do P3 e no da mesma seção da coluna do P4.
20. Aperte o L2 do P3 e o do P4.
21. Confira que os dois voltaram a ficar leves.

**Passa quando.** O L2 do P3 e o do P4 ficam duros, e o R2 dos MESMOS controles continua leve — o comando agiu num lado só, pelo sem fio, e não vazou para o outro lado da mesma mão. A firmeza é a mesma que um controle do cabo dá. Os gatilhos do P1 e do P2 continuam exatamente como estavam. E «Desligado» na seção do L2 solta os dois L2.

**Por controle.**

* **P1** — No CABO, testemunha. Não toque na coluna dele. Aperte o L2 e o R2 antes e depois; têm de estar iguais. Se o L2 dele endurecer, o comando pegou todo mundo.
* **P2** — No CABO, segunda testemunha. Não toque na coluna dele. Mesma conferência. Se o P1 ficou intacto e o L2 do P2 endureceu, o comando foi para o controle errado.
* **P3** — No RÁDIO, e é o primeiro. Mexe-se só na seção de CIMA (L2) da coluna dele. O L2 endurece; o R2 do mesmo controle é a testemunha na mesma mão. É nele que você clica na seta girando (↻), para ver se o reenvio mantém o efeito e continua respeitando o lado.
* **P4** — No RÁDIO, e é o segundo. Os mesmos gestos, na coluna dele. Ele separa "o rádio funciona" de "aquele controle funciona": se o L2 do P3 endurecer e o do P4 não, o defeito é do aparelho, não do sem fio.

**A armadilha.** A armadilha maior é apertar o gatilho errado: o L2 é o de baixo do lado ESQUERDO, e a seção da tela é a de CIMA, titulada pelo desenho L2 — quem mexe na seção de baixo e aperta o L2 conclui que o produto errou de lado quando quem errou foi o gesto. Não use «Desligado» como o efeito do teste, e não julgue pela tela: o campo "Modo" mostra o pedido e a piscada verde diz que o comando saiu, nada mais. Sem o aperto dos quatro gatilhos no começo — o do P3, o do P4 e os das duas testemunhas — este teste não mede nada: é essa mão guardada que vira a régua de tudo o que vem depois, e ela é o primeiro ato de propósito. A medição que sustenta esta linha exercitou UM modo só, «Rígido», com um único jogo de números; os outros dezoito não foram tocados por lá. Duas coisas já medidas que parecem erro seu e não são: se o controle do rádio cair e voltar no meio do teste, o efeito não volta com ele — o botãozinho da seta girando (↻) é o caminho de mandá-lo de novo, e por isso está nos passos; e o efeito NÃO é eterno, amanhecendo solto sozinho depois de alguns MINUTOS, sem ninguém tocar. Aplicar qualquer efeito também PAUSA a troca automática de perfil, que só volta com o «Desligado» do fim. Onde a prova parou: em O APARELHO OBEDECEU, medido em 11/08 com dois controles no rádio na mesa e o lado ocioso servindo de controle negativo — o dedo é o degrau certo, e o jogo é o degrau seguinte, que ninguém mediu. Este teste passa dos oito atos — são doze —, e a razão é o dedo: cada aperto é de um gatilho só, num controle só, e é o único instrumento que existe aqui; juntar dois apertos num passo só faria você julgar dois gatilhos com uma lembrança só, que é exatamente o erro que a armadilha maior descreve.

---

## mapa-gatilho.modos_firmware-cabo — Gatilho — modos do firmware (enum) · cabo

*Célula:* `gatilho.modos_firmware @ cabo`

**O que isto prova.** Passa a mão pelos dezenove efeitos da lista, nos dois controles do cabo, para ver quais fazem alguma coisa de verdade e quais não fazem nada.

**Onde olhar.** Na aba Gatilhos, quadro "Seleção de Gatilho". O campo "Modo", dentro da seção de cima (a do desenho L2), abre uma lista com dezenove escolhas — de «Desligado» a «Montar do zero». Logo abaixo, a linha "Ajustes" muda de barras conforme o efeito escolhido: alguns têm duas barras, outros seis, outros nenhuma, e nesse caso aparece a frase "Este modo não tem o que ajustar.". Parar o mouse em cima do campo mostra uma explicação de uma linha do efeito escolhido. Mas o que responde este teste é o SEU DEDO, e o instrumento é um papel com os dezenove nomes copiados: o DualSense não devolve em que efeito está, então nem o campo nem as barras provam nada sobre o aparelho. A tela só pisca em verde por cerca de um segundo e meio quando o comando sai.

**Os passos.**

1. Abra a aba Gatilhos.
2. Confira que a coluna do P1 e a do P2 terminam, no alto, na palavra cabo.
3. Aperte o L2 e o R2 do P3 e do P4 e anote no papel como eles estão — são as testemunhas, e não podem mudar em momento nenhum.
4. Abra o campo "Modo" da seção de cima (a do desenho L2), na coluna do P1, e copie para o papel os dezenove nomes da lista, na ordem em que aparecem.
5. Escolha «Desligado» nesse campo e aperte o L2 do P1: esta é a sua referência de gatilho solto.
6. Escolha o nome seguinte da lista e aperte o L2 do P1 do começo ao fundo do curso, primeiro devagar e depois rápido.
7. Veja o campo piscar em verde.
8. Escreva ao lado daquele nome o que a sua mão sentiu de diferente do «Desligado»: nada, duro do começo ao fim, duro a partir de um ponto, um estalo, tremendo, ou outra coisa.
9. Conte quantas barras a linha "Ajustes" passou a mostrar, ou repare se apareceu a frase de que não há o que ajustar, e anote também.
10. Repita o ato 4 para cada um dos dezenove nomes da lista, até o último.
11. Volte a «Disparo (Weapon)» e depois a «Vibração», apertando o L2 do P1 com atenção em cada um dos dois, e anote de novo o que sentiu.
12. Escolha «Desligado» na coluna do P1, por último.
13. Confira que o L2 do P1 voltou a ficar leve.
14. Repita os atos 2 a 7 na coluna do P2, o outro controle do cabo.
15. Compare a tabela do P2 com a do P1, nome por nome.
16. Compare, no fim de tudo, o L2 e o R2 do P3 e do P4 com o que você anotou no ato 1: têm de estar iguais.

**Passa quando.** Cada nome da lista produz na sua mão uma sensação diferente da do «Desligado», e a MESMA sensação nos dois controles do cabo: o que o P1 fez, o P2 fez igual. Um nome que não muda nada em relação ao «Desligado» é achado do teste e não erro seu — anote e siga. E o P3 e o P4 não podem ter mudado de sensação em momento nenhum do teste.

**Por controle.**

* **P1** — No CABO, e é onde você faz a volta inteira pelos dezenove nomes, no L2. Ele produz a sua tabela no papel: um nome, uma sensação.
* **P2** — No CABO, e é a conferência. Faça a mesma volta na coluna dele e compare nome por nome com a tabela do P1. Onde os dois discordarem, o problema é do aparelho e não da lista — e é justamente por isso que são dois no cabo.
* **P3** — No RÁDIO, testemunha. Não toque na coluna dele. Aperte o L2 e o R2 no começo e no fim; têm de estar iguais. Se ele mudar de sensação no meio da volta, algum dos dezenove escapou para o transporte inteiro.
* **P4** — No RÁDIO, segunda testemunha. Não toque na coluna dele. Mesma conferência. Se o P3 ficou intacto e o P4 mudou, o efeito foi parar no controle errado.

**A armadilha.** Este teste tem DEZ atos, acima dos oito do alvo, e o trabalho real é maior do que a lista deixa ver: os atos 4 e 5 são UM ato repetido dezenove vezes, e o ato 8 repete tudo no segundo controle. A lista foi encurtada; o teste não. Este é também o teste em que "nada aconteceu" é resposta legítima e prevista: o mapa registra esta linha como PARCIAL, e a medição que existe é dela mesma, pelo TATO, em 01/08 — na época SETE das escolhas não faziam nada (três mandavam ao aparelho o número do desligado; quatro mandavam o número certo sem dizer quais zonas do gatilho usar). Aquelas foram consertadas, e este teste é o que confere se ficaram. Dois nomes, porém, continuam com divergência VIVA declarada no mapa: «Disparo (Weapon)» e «Vibração» mandam ao aparelho, cada um, o número de OUTRO efeito, e ninguém mediu se eles fazem alguma coisa — por isso eles têm ato próprio. Se derem sensação estranha, ou nenhuma, é o achado, e está previsto. O falso verde daqui é julgar pela tela: o campo "Modo" e a caixa "Ajustes" mudam SEMPRE, porque quem os desenha é o produto e nunca o aparelho — o DualSense não devolve em que efeito está. Só o dedo responde. Dois cuidados de tempo: dezenove escolhas levam um bom tempo, e já foi medido que o efeito NÃO é eterno — ele amanhece solto sozinho depois de alguns MINUTOS —, então sinta LOGO depois de escolher e não volte a conferir o efeito de dez atrás. E «Desligado» tem de ser a última escolha nos dois controles: qualquer efeito aplicado PAUSA a troca automática de perfil, e só o «Desligado» a devolve. Onde a prova parou: o mapa NÃO registra grau para esta célula. O degrau que este teste alcança é o seu dedo; o jogo está fora, e ninguém o mediu.

---

## mapa-gatilho.modos_firmware-radio — Gatilho — modos do firmware (enum) · rádio

*Célula:* `gatilho.modos_firmware @ rádio`

**O que isto prova.** Passa a mão pelos dezenove efeitos da lista, nos dois controles do rádio, para ver quais fazem alguma coisa e se o sem fio responde igual ao cabo.

**Onde olhar.** Na aba Gatilhos, quadro "Seleção de Gatilho". A coluna do P3 e a do P4 têm de terminar, no alto, na palavra rádio. O campo "Modo", dentro da seção de cima (a do desenho L2), abre uma lista com dezenove escolhas — de «Desligado» a «Montar do zero». Logo abaixo, a linha "Ajustes" muda de barras conforme o efeito escolhido, e quando o efeito não tem o que ajustar aparece a frase "Este modo não tem o que ajustar.". Parar o mouse no campo mostra uma explicação de uma linha do efeito. No pé de cada coluna há um botãozinho redondo com uma seta girando (↻), que manda de novo ao controle o que está na coluna. Mas quem responde este teste é o SEU DEDO: nem o campo nem as barras dizem nada sobre o aparelho, porque o DualSense não devolve em que efeito está. A tela apenas pisca em verde por cerca de um segundo e meio quando o comando sai. Tenha papel e caneta à mão antes de começar: a saída deste teste é uma tabela de dezenove linhas por controle — um nome, uma sensação.

**Os passos.**

1. Abra a aba Gatilhos.
2. Confira que a coluna do P3 e a do P4 terminam, no alto, na palavra rádio.
3. Aperte o L2 e o R2 do P1 e do P2 até o fundo e anote como estão — eles são as testemunhas e não podem mudar em momento nenhum.
4. Abra o campo "Modo" da seção de cima (a do desenho L2), na coluna do P3, e copie para o papel os dezenove nomes da lista, na ordem.
5. Escolha «Desligado» nesse campo.
6. Aperte o L2 do P3 do começo ao fundo do curso: esta é a sua referência de gatilho solto.
7. Escolha o próximo nome da lista no mesmo campo.
8. Veja o campo piscar em verde.
9. Aperte o L2 do P3 do começo ao fundo do curso, primeiro devagar e depois rápido.
10. Escreva no papel, ao lado daquele nome, o que a sua mão sentiu: nada, duro do começo ao fim, duro a partir de um ponto, um estalo, tremendo, ou outra coisa.
11. Repare se a sensação demorou visivelmente mais a chegar do que chegaria por cabo, e anote isso ao lado.
12. Repita a escolha, o aperto do L2 e a anotação para cada nome que sobra na lista, até o último.
13. Volte a «Disparo (Weapon)» e depois a «Vibração», um de cada vez, apertando o L2 do P3 com atenção em cada um, e anote de novo o que a sua mão sentiu.
14. Escolha «Desligado» na coluna do P3.
15. Aperte o L2 do P3 e confirme que ele voltou a ficar leve.
16. Refaça a volta inteira na coluna do P4, o outro controle do rádio, terminando nela também em «Desligado».
17. Compare nome por nome a tabela do P4 com a do P3 — e com a do cabo, se você a tiver.
18. Aperte de novo o L2 e o R2 do P1 e do P2.
19. Confira que os quatro gatilhos das testemunhas estão iguais ao que você anotou no começo.

**Passa quando.** Cada nome da lista produz na sua mão uma sensação diferente da do «Desligado», e a MESMA sensação nos dois controles do rádio — e a mesma que o cabo dá, se você tiver a tabela do cabo ao lado. Nenhuma escolha pode chegar visivelmente mais tarde pelo sem fio. Um nome que não muda nada em relação ao «Desligado» é achado do teste, não erro seu: anote e siga. E o P1 e o P2 não podem ter mudado de sensação em momento nenhum.

**Por controle.**

* **P1** — No CABO, testemunha. Não toque na coluna dele. Aperte o L2 e o R2 no começo e no fim; têm de estar iguais. Se ele mudar de sensação no meio da volta, algum dos dezenove escapou para todo mundo.
* **P2** — No CABO, segunda testemunha. Não toque na coluna dele. Mesma conferência. Se o P1 ficou intacto e o P2 mudou, o efeito foi parar no controle errado.
* **P3** — No RÁDIO, e é onde você faz a volta inteira pelos dezenove nomes, no L2. Ele produz a sua tabela do sem fio: um nome, uma sensação. Se um controle cair e voltar no meio, use o botãozinho da seta girando (↻) antes de continuar.
* **P4** — No RÁDIO, e é a conferência. Faça a mesma volta na coluna dele e compare nome por nome com a tabela do P3. Onde os dois discordarem, o problema é do aparelho e não do sem fio — é para isso que são dois no rádio.

**A armadilha.** Este é o teste em que "nada aconteceu" é resposta legítima e prevista: o mapa registra esta linha como PARCIAL, e a medição que existe é dela mesma, pelo TATO, em 01/08 — na época SETE das escolhas não faziam nada (três mandavam ao aparelho o número do desligado; quatro mandavam o número certo sem dizer quais zonas do gatilho usar). Aquelas foram consertadas, e este teste confere se ficaram. Dois nomes continuam com divergência VIVA declarada no mapa: «Disparo (Weapon)» e «Vibração» mandam ao aparelho, cada um, o número de OUTRO efeito, e ninguém mediu se fazem alguma coisa — por isso têm passo próprio. Se derem sensação estranha, ou nenhuma, é o achado. O falso verde é julgar pela tela: o campo "Modo" e a caixa "Ajustes" mudam SEMPRE, porque quem os desenha é o produto e nunca o aparelho. Só o dedo responde. Três cuidados que são do rádio: se um controle cair e voltar, o efeito não volta com ele, e o botãozinho da seta girando (↻) no pé da coluna é o caminho de mandá-lo de novo — sem isso, um punhado de nomes seguidos vai aparecer como "não fez nada" por causa de UMA queda; a volta pelos dezenove leva um bom tempo, e já foi medido que o efeito NÃO é eterno, amanhecendo solto sozinho depois de alguns MINUTOS, então aperte o L2 LOGO depois de escolher; e «Desligado» tem de ser a última escolha nos dois controles, porque qualquer efeito aplicado PAUSA a troca automática de perfil e só o «Desligado» a devolve. Este teste passa dos oito atos — são catorze —, e a razão é a lista: o aperto do L2 é o teste inteiro e se repete dezenove vezes em cada controle, com uma escolha e uma anotação em volta de cada aperto; cortar a volta pela metade não responderia a pergunta. Onde a prova parou: o mapa NÃO registra grau para esta célula. O degrau que este teste alcança é o seu dedo; o jogo está fora, e ninguém o mediu.

---

## mapa-identidade.cor_do_aparelho-cabo — Cor de fábrica do controle (a cor do plástico, lida do aparelho) · cabo

*Célula:* `identidade.cor_do_aparelho @ cabo`

**O que isto prova.** Prova que o Hefesto pergunta ao aparelho, pelo cabo, qual é a cor de fábrica do plástico — e escreve na tela o nome certo dos dois controles do cabo.

**Onde olhar.** Três lugares dizem a mesma coisa e é bom conferir os três. Primeiro, a fita do topo, a linha que começa com "Selecionar:": cada controle é um chip com o número, o nome da cor e a palavra do transporte, e a BORDA do chip é pintada nessa cor. Segundo, a aba Controles: o cabeçalho de cada cartão diz "P1 · nome da cor · cabo". Terceiro, a aba Conexões, quadro Gestão de Controles: a linha diz "Sony · Player 1 · nome da cor · cabo", com uma barrinha colorida à esquerda. Quando a cor NÃO foi lida, os dois primeiros põem um travessão no lugar do nome, e a linha da aba Conexões simplesmente omite o nome — não escreve nada ali.

**Os passos.**

1. Desligue os quatro controles e desencaixe os dois cabos.
2. Ponha os quatro na mesa, com o plástico à vista.
3. Anote num papel a cor de cada um, na ordem em que você vai ligá-los.
4. Abra o Hefesto.
5. Encaixe o cabo no primeiro controle e depois no PC.
6. Encaixe o segundo cabo no segundo controle e depois no PC.
7. Dê um toque curto no botão PS do terceiro controle.
8. Dê um toque curto no botão PS do quarto controle.
9. Clique na aba Controles.
10. Leia o nome da cor no cabeçalho do cartão do P1 e compare com o plástico que está na sua mão.
11. Leia o nome da cor no cabeçalho do cartão do P2 e faça a mesma comparação.
12. Confira que a palavra ao lado do nome, nos dois, é cabo.
13. Olhe a borda do chip do P1 na fita do topo e compare o tom com o plástico dele.
14. Olhe a borda do chip do P2 e compare o tom com o plástico dele.
15. Abra a aba Conexões.
16. Leia a linha do P1 no quadro Gestão de Controles e confira que o nome da cor está escrito ali, entre o Player e a palavra do transporte.
17. Leia a linha do P2 e faça a mesma conferência.
18. Anote o que os cartões do P3 e do P4 mostram no lugar da cor — este teste não se decide por eles, mas a anotação importa.

**Passa quando.** Os dois controles do cabo aparecem com o nome da cor de fábrica escrito por extenso, e esse nome é a cor do plástico que você tem na mão. A borda do chip de cada um está pintada nesse tom, e a palavra ao lado é cabo. Nenhum dos dois mostra travessão no lugar do nome.

**Por controle.**

* **P1** — No cabo, e é um dos dois que têm de responder. Compare o nome escrito no cabeçalho do cartão dele com o plástico na sua mão, e depois a borda do chip com o mesmo plástico.
* **P2** — No cabo, o segundo que tem de responder. Ele existe para o caso de o P1 acertar por sorte: se os dois acertam cores DIFERENTES, o Hefesto perguntou a cada aparelho, em vez de espalhar uma resposta só.
* **P3** — No rádio, testemunha. Só anote o que o cartão dele diz. Se ele mostrar a MESMA cor de um dos dois do cabo e o plástico dele for outro, a resposta de um controle está vazando para os outros — e esse é o achado.
* **P4** — No rádio, testemunha, mesma anotação. Se o P3 e o P4 mostram a mesma cor e os plásticos deles são diferentes, é o mesmo achado, e agora com duas provas.

**A armadilha.** O desenho da tela vem com dois chips prontos, "P1 · Cosmic Red" e "P2 · Starlight Blue", e é fácil tomá-los por leitura de verdade. O que os denuncia é a palavra do transporte: no chip vivo está escrito cabo ou rádio; no chip do desenho está escrito USB ou BT. Se você vir USB ou BT dentro de um chip, ninguém leu nada e o teste não passou nem reprovou. (A contagem lá no alto é o contrário: ali USB e BT estão certos, por decisão sua.) Segunda armadilha, e ela dá falso vermelho: a cor é perguntada UMA VEZ por aparelho, no instante em que ele entra, e a resposta fica guardada até você fechar a janela. Desplugar e replugar o cabo não faz o Hefesto perguntar de novo — se saiu travessão, o único jeito de refazer a pergunta é fechar a janela pelo X e abri-la com o controle já ligado. Terceira: travessão é resposta honesta, não mentira; quer dizer que a pergunta não voltou. Anote como reprova, mas não confunda com o Hefesto inventando uma cor.

---

## mapa-identidade.cor_do_aparelho-radio — Cor de fábrica do controle (a cor do plástico, lida do aparelho) · rádio

*Célula:* `identidade.cor_do_aparelho @ rádio`

**O que isto prova.** Prova que o Hefesto consegue perguntar a cor de fábrica do plástico também pelo rádio, e escreve o nome certo dos dois controles sem fio.

**Onde olhar.** Os mesmos três lugares do teste do cabo, agora nas linhas do P3 e do P4. Na fita do topo, o chip "P3 · nome da cor · rádio", com a borda pintada nessa cor. Na aba Controles, o cabeçalho do cartão. Na aba Conexões, quadro Gestão de Controles, a linha "Sony · Player 3 · nome da cor · rádio", com a barrinha colorida à esquerda. Sem leitura, o cabeçalho do cartão e o chip põem um travessão, e a linha da aba Conexões omite o nome.

**Os passos.**

1. Desligue os quatro controles e desencaixe os dois cabos.
2. Feche a janela do Hefesto pelo X e abra-a de novo — fechando a janela ele esquece as cores que já perguntou.
3. Ponha os quatro na mesa e anote num papel a cor do plástico de cada um.
4. Encaixe o cabo no primeiro controle e depois no PC.
5. Encaixe o segundo cabo no segundo controle e depois no PC.
6. Dê um toque curto no botão PS do terceiro controle e espere o chip dele aparecer na fita do topo.
7. Dê um toque curto no botão PS do quarto controle e espere o chip dele aparecer.
8. Clique na aba Controles.
9. Leia o cabeçalho do cartão do P3 e compare o nome da cor com o plástico daquele controle na sua mão.
10. Leia o cabeçalho do cartão do P4 e faça a mesma comparação.
11. Confira que a palavra ao lado do nome, nos dois, é rádio.
12. Olhe a borda do chip do P3 e a do P4 na fita do topo e compare os tons com os plásticos.
13. Abra a aba Conexões e leia as linhas do P3 e do P4 no quadro Gestão de Controles.
14. Confira que o nome da cor está escrito nas duas linhas e que a barrinha da esquerda de cada uma está pintada.
15. Leia também as linhas do P1 e do P2 e confira que a cor deles não trocou quando os do rádio entraram.

**Passa quando.** Os dois controles do rádio aparecem com o nome da cor de fábrica escrito por extenso, e o nome bate com o plástico na sua mão. A palavra ao lado é rádio nos dois, e a borda do chip está pintada. E os dois do cabo continuam com as cores que já tinham antes de os do rádio entrarem.

**Por controle.**

* **P1** — No cabo, testemunha. Anote a cor dele ANTES de ligar os do rádio e confira depois: ela não pode trocar quando um controle sem fio entra.
* **P2** — No cabo, testemunha, mesma conferência antes e depois.
* **P3** — No rádio, e é um dos dois que têm de responder. Ele precisa entrar pelo rádio numa janela recém-aberta — se este mesmo aparelho passou pelo cabo depois de você abrir a janela, o teste não mede o rádio.
* **P4** — No rádio, o segundo que tem de responder, e é ele que dá o tamanho da resposta. A leitura pelo rádio só foi provada em DOIS aparelhos até hoje; estes são o terceiro e o quarto. Um deles ficando em travessão é achado — e é justamente o achado que este teste existe para procurar.

**A armadilha.** O falso verde mais fácil é o da memória do Hefesto: ele pergunta a cor UMA VEZ por aparelho por sessão e guarda a resposta pelo endereço do controle, que é o mesmo no cabo e no rádio. Se aquele controle já tinha respondido pelo CABO nesta mesma janela, o nome aparece na tela sem que uma única pergunta tenha saído pelo rádio, e o teste dá verde sobre nada. É por isso que o segundo passo é fechar e abrir a janela. Segunda: pelo rádio o pedido vai assinado, e essa leitura só está provada em duas unidades desta bancada, não nas quatro. Um travessão no P3 ou no P4 pode ser exatamente isso e não é erro seu — anote qual controle recusou e qual é a cor do plástico dele, porque esse par é o dado. Terceira: se a palavra dentro do chip for USB ou BT em vez de cabo ou rádio, a fita está mostrando o desenho e não os seus controles.

---

## mapa-identidade.cracha_nos_dois_transportes-cabo — O crachá que serve nos DOIS transportes sem escrita (a pergunta dela) · cabo

*Célula:* `identidade.cracha_nos_dois_transportes @ cabo`

**O que isto prova.** Prova que o crachá de um controle que está no cabo é o mesmo aparelho de sempre — ele sai para o rádio e volta ao cabo sem trocar de nome.

**Onde olhar.** O crachá é o conjunto que nomeia o controle, e ele aparece em três lugares: na aba Conexões, quadro Gestão de Controles, a linha "Sony · Player 1 · cor · cabo"; na fita do topo, o chip "P1 · cor · cabo", com a borda pintada na cor; e na aba Controles, o cabeçalho do cartão. As três partes que têm de SOBREVIVER são a marca, a cor e o número do jogador. A quarta, a palavra do transporte, é justamente a que TEM de mudar. O endereço do aparelho, que é o que faz o crachá funcionar por dentro, não aparece na tela — a fonte diz que ele é chave interna e não vocabulário de tela.

**Os passos.**

1. Ligue o P1 e o P2 pelo cabo e o P3 e o P4 pelo rádio.
2. Confira que o P1 e o P2 já foram pareados por rádio nesta máquina alguma vez — sem isso o teste não roda.
3. Abra o Hefesto na aba Conexões.
4. Anote a linha inteira do P1 e a do P2, palavra por palavra.
5. Anote também as linhas do P3 e do P4, para conferir no fim.
6. Puxe o cabo de dentro do P1.
7. Dê um toque no botão PS do P1, sem demorar — do puxão ao toque tem de passar menos de trinta segundos.
8. Espere o chip do P1 voltar à fita do topo.
9. Leia a linha dele agora: a marca, a cor e o número têm de ser os mesmos, e só a palavra do transporte pode ter virado rádio.
10. Encaixe o cabo de novo no P1 e depois no PC.
11. Espere o chip dele voltar à fita.
12. Leia a linha dele outra vez e compare, palavra por palavra, com a que você anotou no começo.
13. Repita os passos 6 a 12 com o P2.
14. Leia as linhas do P3 e do P4 e confira que estão como você anotou.

**Passa quando.** O P1 e o P2 atravessam a ida ao rádio e a volta ao cabo com a mesma marca, a mesma cor e o mesmo número de jogador. A única coisa do crachá que muda é a palavra do transporte, e ela volta ao que era quando o cabo volta. Nenhuma linha nova aparece para eles em momento nenhum, e o P3 e o P4 ficam parados.

**Por controle.**

* **P1** — No cabo, e é o primeiro a atravessar. Puxe o cabo, traga-o pelo rádio com um toque no PS e devolva-o ao cabo. Marca, cor e número têm de sair iguais dos dois lados.
* **P2** — No cabo, o segundo a atravessar. Ele existe porque o crachá tem de valer para os dois — com um só, um acerto pode ser sorte.
* **P3** — No rádio, testemunha. A linha dele não pode sumir nem trocar de número em instante nenhum da travessia.
* **P4** — No rádio, testemunha, e é a que mais importa: enquanto o P1 está no rádio há TRÊS controles sem fio ao mesmo tempo, e é aí que um crachá frouxo confunde dois aparelhos. Olhe a linha dele durante a travessia, não só depois.

**A armadilha.** O verde deste teste é fácil de conseguir por engano, e vale saber por quê: o Hefesto pergunta a cor do plástico uma vez por APARELHO por sessão e guarda a resposta pelo endereço, que é o mesmo no cabo e no rádio. Se o crachá funcionar, o nome da cor reaparece no rádio SEM nova pergunta — e é isso que este teste quer ver. Mas o contrário também vale: este teste NÃO prova que a leitura da cor pelo rádio funciona; quem prova isso é o teste próprio dela, e para ele a janela tem de ser aberta do zero. Segunda: são trinta segundos entre puxar o cabo e apertar o PS. Passando disso ele volta com outro número, e isso é o prazo do lugar guardado, não crachá quebrado — refaça mais rápido. Terceira: o número do jogador não é parte do aparelho; é o lugar na fila, e a fila o devolve porque guardou o lugar. Se o número mudar depois dos trinta segundos, o achado é do relógio. Quarta: até hoje isto foi medido em quatro aparelhos, e é amostra — o que sustenta a generalização é o mecanismo, não a contagem.

---

## mapa-identidade.cracha_nos_dois_transportes-radio — O crachá que serve nos DOIS transportes sem escrita (a pergunta dela) · rádio

*Célula:* `identidade.cracha_nos_dois_transportes @ rádio`

**O que isto prova.** Prova que o crachá de um controle que está no rádio também é o mesmo aparelho de sempre — ele vai para o cabo e volta ao rádio sem trocar de nome.

**Onde olhar.** Os mesmos três lugares, agora nas peças do P3 e do P4: a linha "Sony · Player 3 · cor · rádio" no quadro Gestão de Controles, da aba Conexões; o chip "P3 · cor · rádio" na fita do topo, com a borda pintada; e o cabeçalho do cartão na aba Controles. A marca, a cor e o número têm de sobreviver à travessia; só a palavra do transporte muda. O endereço do aparelho não aparece na tela — a fonte diz que ele é chave de dentro do produto.

**Os passos.**

1. Ligue o P1 e o P2 pelo cabo e o P3 e o P4 pelo rádio.
2. Abra o Hefesto na aba Conexões.
3. Anote a linha inteira do P3 e a do P4, palavra por palavra.
4. Anote também as linhas do P1 e do P2, para conferir no fim.
5. Segure o botão PS do P3 até todas as luzes dele apagarem.
6. Encaixe um cabo no P3 e depois no PC, sem demorar — do apagar ao encaixe tem de passar menos de trinta segundos.
7. Dê um toque no botão PS do P3 se ele não acender sozinho ao ser plugado.
8. Espere o chip dele voltar à fita do topo.
9. Leia a linha dele agora: a marca, a cor e o número têm de ser os mesmos, e só a palavra do transporte pode ter virado cabo.
10. Desencaixe o cabo do P3.
11. Dê um toque no botão PS do P3 para trazê-lo de volta pelo rádio.
12. Espere o chip dele voltar à fita.
13. Leia a linha dele outra vez e compare, palavra por palavra, com a que você anotou no começo.
14. Repita os passos 5 a 13 com o P4.
15. Leia as linhas do P1 e do P2 e confira que estão como você anotou.

**Passa quando.** O P3 e o P4 atravessam a ida ao cabo e a volta ao rádio com a mesma marca, a mesma cor e o mesmo número de jogador. A única coisa do crachá que muda é a palavra do transporte, e ela volta a dizer rádio no fim. Nenhuma linha nova aparece para eles, e o P1 e o P2 ficam parados nos números e nas cores deles.

**Por controle.**

* **P1** — No cabo, testemunha. A linha dele não pode sumir nem trocar de número enquanto o P3 e o P4 atravessam — e é durante a travessia que se olha, não só depois.
* **P2** — No cabo, testemunha, mesma vigilância. Enquanto o P3 está no fio há TRÊS controles no cabo ao mesmo tempo, e é aí que um crachá frouxo confunde dois aparelhos.
* **P3** — No rádio, e é o primeiro a atravessar: apaga, vai para o cabo, volta pelo rádio. Marca, cor e número têm de sair iguais dos dois lados.
* **P4** — No rádio, o segundo a atravessar. Ele é o mais propenso a perder o crachá, porque é o último da fila — se o P3 volta certo e ele não, o achado é do quarto lugar, não do transporte.

**A armadilha.** A armadilha própria deste lado é o sono do controle: um controle que dormiu não reaparece sozinho quando você pluga o cabo — já foi medido nesta casa. Se ele não acender ao ser plugado, dê um toque no PS; sem isso você anotaria "sumiu no cabo" sobre um aparelho que está apenas dormindo. Segunda: o nome da cor pode APARECER só depois de ele ir para o cabo e nunca antes. Isso não é o crachá falhando — é a leitura da cor pelo rádio, que só está provada em duas unidades e tem teste próprio. O que reprova AQUI é a cor MUDAR entre os dois transportes, ou o número trocar. Terceira: são trinta segundos entre apagar e voltar; passando disso ele volta com outro número, e isso é o prazo do lugar guardado. Quarta: não segure o PS por tempo demais ao religar — com uns cinco segundos de botão o aperto é lido como um toque e a Steam abre; se abrir, feche-a e refaça.

---

## mapa-identidade.firmware-cabo — Atualização de firmware · cabo

*Célula:* `identidade.firmware @ cabo`

**O que isto prova.** Prova que o Hefesto não promete atualizar o firmware dos controles pelo cabo — não há botão, não há número de versão, e nenhuma tela finge que existe.

**Onde olhar.** Em nenhum campo, e é isso que se prova. Percorra as dez abas, olhando com atenção os três lugares onde uma coisa dessas caberia: a aba Controles, que é onde mora tudo o que é de um controle só (o cartão de cada um, aberto); a aba Conexões, quadro Gestão de Controles, onde cada controle abre uma linha; e a aba Sistema, onde ficam os botões que mexem no Hefesto e a lista do exame. A palavra firmware APARECE na tela em um lugar só, e não é atualização: é a explicação do botão de microfone, dentro do cartão da aba Controles, que fala em calar o microfone no firmware do controle.

**Os passos.**

1. Ligue o P1 e o P2 pelo cabo e o P3 e o P4 pelo rádio.
2. Abra o Hefesto.
3. Abra a aba Controles.
4. Clique na linha do P1 para abrir o cartão dele.
5. Leia o cartão de cima a baixo, procurando um número de versão ou um botão de atualizar.
6. Clique na linha do P2 e leia o cartão dele do mesmo jeito.
7. Abra a aba Conexões.
8. Clique na linha do P1 no quadro Gestão de Controles e leia tudo o que ela mostra aberta.
9. Clique na linha do P2 e faça a mesma leitura.
10. Abra a aba Sistema.
11. Leia os botões do alto e a lista do exame, procurando qualquer coisa que fale em atualizar o controle.
12. Percorra as outras sete abas, uma de cada vez, procurando o mesmo.
13. Anote qualquer campo que fale em versão de controle ou em atualizar controle, dizendo em que aba ele está.
14. Anote onde você encontrou a palavra firmware, se encontrou, e o que a frase inteira dizia.

**Passa quando.** Nenhuma das dez abas oferece atualizar o firmware de um controle, e nenhuma mostra um número de versão de controle — nem para o P1, nem para o P2, que são os dois do cabo e seriam os únicos por onde uma atualização poderia passar. A única vez que a palavra firmware aparece é na explicação do botão de microfone, e ali ela fala de calar o microfone, não de atualizar nada.

**Por controle.**

* **P1** — No cabo, e é por aqui que uma atualização passaria se existisse — este tipo de coisa só se faz pelo fio. Leia o cartão dele inteiro e a linha dele inteira.
* **P2** — No cabo, o segundo lugar onde procurar, e ele existe para o caso de o campo aparecer num cartão só. Leia o cartão e a linha dele inteiros.
* **P3** — No rádio, testemunha. Confira que ele também não mostra versão nenhuma e, sobretudo, que não aparece nele uma frase do tipo "ligue no cabo para atualizar" — uma frase dessas é o produto prometendo o que não faz.
* **P4** — No rádio, testemunha, mesma conferência e o mesmo cuidado com convites a ligar no cabo.

**A armadilha.** Achar a palavra firmware e concluir que existe atualização. Ela está na tela, dentro do cartão da aba Controles, na explicação do botão de microfone, e ali ela diz que o mudo é aplicado no firmware do controle — é outra coisa. Segunda: os botões da aba Sistema (Reiniciar o serviço, Reaplicar ajustes, Parar o serviço) mexem no Hefesto, não no controle; nenhum deles manda um byte ao aparelho. Terceira: existem programas de fora e o próprio console da Sony que atualizam o DualSense pelo cabo — o que este teste mede é o HEFESTO, e o registro é claro: ele nunca mandou um byte de atualização a aparelho nenhum, por transporte nenhum, e essa metade do assunto não tem nem um degrau de prova, porque nunca foi tentada. Se você encontrar um botão, isso é o achado e vale mais que o teste inteiro.

---

## mapa-identidade.firmware-radio — Atualização de firmware · rádio

*Célula:* `identidade.firmware @ rádio`

**O que isto prova.** Prova que o Hefesto também não promete nada sobre firmware para os dois controles do rádio — nem versão, nem convite a ligar o cabo para atualizar.

**Onde olhar.** Nos mesmos lugares do lado do cabo, agora nas peças do P3 e do P4: o cartão de cada um na aba Controles, aberto; a linha de cada um no quadro Gestão de Controles, na aba Conexões, aberta; e a lista do exame na aba Sistema. Repare também na coluna de cada um nas abas Iluminação, Gatilhos e Vibração, onde o cabeçalho traz o número, a cor e a palavra rádio — é ali que uma ressalva sobre transporte apareceria, se houvesse.

**Os passos.**

1. Ligue o P1 e o P2 pelo cabo e o P3 e o P4 pelo rádio.
2. Abra o Hefesto.
3. Abra a aba Controles.
4. Clique na linha do P3 para abrir o cartão dele e leia de cima a baixo.
5. Clique na linha do P4 e leia o cartão dele do mesmo jeito.
6. Compare o que os cartões do P3 e do P4 mostram com o que os cartões do P1 e do P2 mostram: procure qualquer campo que exista num par e não exista no outro.
7. Abra a aba Conexões e abra a linha do P3 no quadro Gestão de Controles.
8. Leia a linha aberta inteira, procurando versão ou convite a atualizar.
9. Abra a linha do P4 e faça a mesma leitura.
10. Abra a aba Sistema e leia a lista do exame, procurando qualquer item que fale em atualizar controle.
11. Percorra as outras abas e leia o cabeçalho da coluna do P3 e do P4 em cada uma.
12. Anote qualquer frase que sugira que ligar o cabo destravaria uma atualização.

**Passa quando.** O P3 e o P4 não mostram número de versão em lugar nenhum, e nenhuma tela sugere que ligar o cabo permitiria atualizar alguma coisa. O que os cartões do rádio mostram é o mesmo que os cartões do cabo mostram: os dois pares não diferem em nada que fale de firmware.

**Por controle.**

* **P1** — No cabo, testemunha, e ele é a régua da comparação: leia o cartão dele para saber o que é normal aparecer, e só então diga se falta ou sobra alguma coisa nos do rádio.
* **P2** — No cabo, segunda testemunha e segunda régua. Se um campo aparece só num dos dois cartões do cabo, o problema é de cartão, não de transporte.
* **P3** — No rádio, e é um dos dois que este teste examina. Leia o cartão e a linha dele inteiros. Um convite a ligar o cabo, aqui, seria o achado.
* **P4** — No rádio, o segundo examinado. Mesma leitura. Ele importa porque é o último a entrar, e campos que nascem torto costumam nascer torto no último.

**A armadilha.** A tentação aqui é o contrário da do cabo: como se sabe que atualização de firmware, quando existe, é coisa de fio, é fácil ler qualquer frase que mencione o cabo como se fosse uma promessa de atualização. Leia a frase inteira antes de anotar — na aba Conexões há avisos legítimos sobre o cabo que falam de luz, de som e de reconexão, e nenhum deles é firmware. Segunda: a palavra firmware que existe na tela está no cartão, na explicação do botão de microfone, e ela vale igual para os do rádio; não é atualização. Terceira, e é o limite honesto deste teste: sobre atualizar firmware não há degrau de prova nenhum registrado, por transporte nenhum — nunca se tentou, nem pelo cabo nem pelo rádio. O que este teste pode afirmar é só o que a tela diz; ele não prova nada sobre o que o aparelho aceitaria.

---

## mapa-identidade.leitura_de_feature-cabo — Ler feature report do aparelho — a regra de leitura, e o que ela custa por rádio · cabo

*Célula:* `identidade.leitura_de_feature @ cabo`

**O que isto prova.** Prova que, quando o Hefesto pergunta uma coisa ao aparelho pelo cabo e a resposta não vem, ele diz que não sabe em vez de escrever um valor bonito.

**Onde olhar.** A única pergunta desse tipo que chega à tela hoje é a da cor de fábrica do plástico. Ela aparece no cabeçalho do cartão de cada controle, na aba Controles, no chip da fita do topo e na linha do quadro Gestão de Controles, na aba Conexões. Quando a resposta não vem, o cabeçalho do cartão e o chip põem um travessão, e a linha da aba Conexões omite o nome. Sobre as outras coisas que o aparelho sabe responder, a fonte não diz onde se leriam — o produto não as mostra em campo nenhum.

**Os passos.**

1. Ligue o P1 e o P2 pelo cabo e o P3 e o P4 pelo rádio.
2. Abra o Hefesto na aba Controles.
3. Leia o cabeçalho do cartão do P1 e anote o que está no lugar da cor: um nome, ou um travessão.
4. Leia o cabeçalho do cartão do P2 e anote do mesmo jeito.
5. Compare os dois nomes com os plásticos que estão na sua mão.
6. Abra a aba Conexões e confira que as linhas do P1 e do P2 dizem o mesmo nome que os cartões.
7. Feche a janela do Hefesto pelo X.
8. Abra a janela de novo.
9. Volte à aba Controles e leia os mesmos dois cabeçalhos.
10. Anote a resposta desta segunda volta, para cada um dos dois.
11. Repita o fecha-e-abre mais três vezes, anotando os dois cabeçalhos a cada volta.
12. Conte, no papel, quantas das quatro voltas trouxeram nome e quantas trouxeram travessão, para o P1 e para o P2.

**Passa quando.** Nas quatro voltas o P1 e o P2 responderam a mesma coisa: ou o nome da cor, sempre o mesmo e sempre o do plástico na sua mão, ou o travessão. O que reprova é o nome MUDAR de uma volta para outra, ou aparecer um nome que não é a cor daquele plástico — isso é o Hefesto aceitando como boa uma resposta que não era a que ele pediu.

**Por controle.**

* **P1** — No cabo. Leia o cabeçalho dele nas quatro voltas e escreva a resposta de cada uma, em ordem.
* **P2** — No cabo, e é a segunda amostra. Se um responde sempre e o outro nunca, o achado é daquele aparelho, não do caminho — e essa distinção só existe porque são dois.
* **P3** — No rádio, testemunha. Anote a resposta dele nas quatro voltas também. Ela é o que separa "o cabo falhou" de "o Hefesto não perguntou a ninguém nesta volta".
* **P4** — No rádio, testemunha, mesma anotação. Quatro travessões nos quatro controles em todas as voltas é um resultado diferente de dois travessões só no cabo, e a anotação é o que permite dizer qual dos dois aconteceu.

**A armadilha.** O fecha-e-abre é o gesto do teste, e sem ele o teste vira uma foto: a pergunta é feita uma vez por aparelho por sessão, então ler quatro vezes seguidas na mesma janela é ler quatro vezes a mesma resposta guardada. Segunda, e é o defeito que este teste procura: o Hefesto não confere se a resposta que voltou é a resposta da pergunta que ele fez, e não tenta de novo quando ela não vem — numa medição desta casa um controle devolveu uma resposta trocada. Um nome de cor que muda entre voltas, ou que não é a cor do plástico, é exatamente esse defeito aparecendo. Terceira: travessão em todas as voltas, nos quatro, não prova defeito sozinho — pode ser a porta do aparelho fechada nesta máquina. Anote como "ninguém respondeu" e não como "o Hefesto errou". Quarta, e é o limite: esta linha do mapa não tem degrau de prova preenchido. O que já saiu no fio e voltou é a leitura da cor; tudo o mais que o aparelho sabe responder foi lido por instrumento de fora, nunca pelo produto, e nunca chegou à tela.

---

## mapa-identidade.leitura_de_feature-radio — Ler feature report do aparelho — a regra de leitura, e o que ela custa por rádio · rádio

*Célula:* `identidade.leitura_de_feature @ rádio`

**O que isto prova.** Prova a mesma coisa pelo rádio: quando a pergunta ao aparelho sem fio não volta, a tela diz que não sabe, e quando volta ela diz sempre a mesma coisa.

**Onde olhar.** Os mesmos lugares, agora no P3 e no P4: o cabeçalho do cartão na aba Controles, o chip da fita do topo e a linha do quadro Gestão de Controles, na aba Conexões. Sem leitura, o cabeçalho e o chip põem travessão e a linha omite o nome. A fonte não diz onde se leria qualquer outra resposta do aparelho pelo rádio — o produto não mostra nenhuma.

**Os passos.**

1. Ligue o P1 e o P2 pelo cabo.
2. Dê um toque no PS do terceiro controle e espere o chip dele aparecer.
3. Dê um toque no PS do quarto controle e espere o chip dele aparecer.
4. Abra o Hefesto na aba Controles.
5. Leia o cabeçalho do cartão do P3 e anote: nome, ou travessão.
6. Leia o cabeçalho do cartão do P4 e anote do mesmo jeito.
7. Compare os dois nomes, se houver, com os plásticos que estão na sua mão.
8. Feche a janela do Hefesto pelo X.
9. Abra a janela de novo, sem mexer em nenhum controle.
10. Leia os cabeçalhos do P3 e do P4 outra vez e anote.
11. Repita o fecha-e-abre mais três vezes, anotando os dois a cada volta.
12. Anote também, a cada volta, o que o P1 e o P2 responderam.
13. Conte no papel quantas voltas trouxeram nome e quantas trouxeram travessão, controle por controle.

**Passa quando.** Nas quatro voltas o P3 e o P4 responderam a mesma coisa: ou o nome da cor, sempre o mesmo e sempre o do plástico na sua mão, ou o travessão. Um nome que muda entre voltas, ou que não é a cor daquele plástico, reprova. Uma volta com nome e outra com travessão no MESMO controle não reprova sozinha — é o que este teste está medindo, e o número de vezes é o dado.

**Por controle.**

* **P1** — No cabo, testemunha e régua. Anote a resposta dele nas quatro voltas: se o cabo responde sempre e o rádio não, a diferença é do transporte, e é isso que este teste mede.
* **P2** — No cabo, segunda régua. Mesma anotação nas quatro voltas.
* **P3** — No rádio, e é um dos dois medidos. Conte quantas das quatro voltas trouxeram nome. Se trouxe em algumas e travessão em outras, escreva quantas de quantas — esse número É o resultado.
* **P4** — No rádio, o segundo medido. Mesma contagem. Os dois juntos dizem se a falha é de um aparelho ou do caminho sem fio.

**A armadilha.** A intuição erra o sentido aqui, e vale saber antes: pelo rádio essas perguntas foram medidas MAIS RÁPIDAS que pelo cabo — centésimos de segundo contra dois décimos. Então lentidão não é o esperado. O que existe é um limite do sistema: quando uma resposta sem fio demora demais, ela é abandonada perto dos três segundos, e o Hefesto não tenta de novo — uma falha só já vira travessão até a próxima janela. Por isso as quatro voltas: uma volta só mede um instante. Segunda: o fecha-e-abre é obrigatório, porque a pergunta é feita uma vez por aparelho por sessão; sem ele você lê quatro vezes a mesma resposta guardada. Terceira: se um controle do rádio dormir e cair no meio das voltas, a volta seguinte não mede nada — confira que os quatro chips estão na fita antes de cada leitura. Quarta, e é o limite: esta linha do mapa não tem degrau de prova preenchido, e o que se leu pelo rádio até hoje foi lido por instrumento de fora, com o Hefesto de pé — não pelo produto.

---

## mapa-identidade.pareamento-cabo — Pareamento / bond e esquecer o host · cabo

*Célula:* `identidade.pareamento @ cabo`

**O que isto prova.** Prova que, com o controle no cabo, o Hefesto recusa o gesto de refazer a conexão sem fio — e diz por quê, em vez de fingir que fez.

**Onde olhar.** Aba Conexões, quadro Gestão de Controles. Cada controle ligado é uma linha, e clicar na linha abre. Dentro da linha aberta há um botão escrito "A luz não acende". Na linha de um controle que está no cabo ele nasce APAGADO, num cinza diferente dos botões que funcionam, e a explicação aparece ao parar o mouse em cima: ela diz que aquilo só funciona com o controle no rádio e que este controle está no cabo. Não existe botão de parear em aba nenhuma — o Hefesto não pareia e não desemparelha, isso é do sistema.

**Os passos.**

1. Ligue o P1 e o P2 pelo cabo e o P3 e o P4 pelo rádio.
2. Abra o Hefesto e vá para a aba Conexões.
3. Leia a contagem no alto do quadro Gestão de Controles e confira que ela diz quatro controles, dois no cabo e dois no rádio.
4. Confira que as linhas do P1 e do P2 terminam com a palavra cabo.
5. Clique na linha do P1 para abri-la.
6. Ache o botão "A luz não acende" dentro dela.
7. Repare que ele está apagado, num tom diferente dos botões que funcionam.
8. Pare o mouse em cima do botão, sem clicar, e leia a explicação inteira.
9. Anote a explicação no papel.
10. Clique no botão mesmo assim.
11. Olhe o P1 na mesa e confirme que ele não apagou e não caiu.
12. Confira que a linha dele não passou a mostrar contagem de segundos nem o botão "Cancelar".
13. Repita os passos 5 a 12 na linha do P2.
14. Clique na linha do P3 para abri-la e confira que ali o mesmo botão está no tom normal, e não apagado — não clique nele.
15. Percorra as dez abas e anote se encontrou em alguma delas um botão de parear ou de esquecer um controle.

**Passa quando.** Nas duas linhas dos controles do cabo o botão está apagado, a explicação diz que aquilo só vale no rádio e nomeia o cabo como a razão, e clicar não derruba o controle nem muda nada na tela. Na linha de um controle do rádio o mesmo botão está no tom normal. E em nenhuma das dez abas existe um botão de parear ou de esquecer um controle.

**Por controle.**

* **P1** — No cabo, e é um dos dois que têm de recusar. Abra a linha dele, leia a explicação parando o mouse em cima, clique e confirme que ele continua ligado e aceso.
* **P2** — No cabo, o segundo que tem de recusar. Ele existe porque uma recusa pode estar presa a uma linha só — com dois, ou a recusa vale para o transporte, ou está escrita à mão em um lugar.
* **P3** — No rádio, testemunha, e é a contraprova do teste: se o botão estiver apagado NELE também, a recusa não está olhando o transporte de cada controle — está desligada para todo mundo, e o verde do cabo veio por acaso.
* **P4** — No rádio, segunda testemunha, e o mesmo olhar: o botão dele tem de estar no tom normal. Não clique em nenhum dos dois.

**A armadilha.** A recusa que interessa é a que EXPLICA. Um botão apagado sem explicação nenhuma passaria neste teste sem merecer, e por isso o passo é parar o mouse em cima e ler a frase inteira ANTES de clicar. Segunda: não clique no botão do P3 nem no do P4 para conferir se funciona — ali ele derruba o controle do rádio de verdade, e isso é outro teste. Terceira: o Hefesto não guarda o pareamento dentro do controle. O que existe é um salva-vidas que copia o pareamento do lado do computador; ele é de linha de comando, pede senha de administrador, e a volta é feita à mão. Nada disso é produto e nada disso aparece nesta tela — se você procurar um botão para isso e não achar, achou o certo. Quarta: a porta que escreveria o pareamento dentro do aparelho existe e só existe pelo cabo, e ela nunca foi usada nesta casa, de propósito — mal formada, ela reescreve o pareamento de um controle que você está usando.

---

## mapa-identidade.pareamento-radio — Pareamento / bond e esquecer o host · rádio

*Célula:* `identidade.pareamento @ rádio`

**O que isto prova.** Prova que, com o controle no rádio, o Hefesto derruba a conexão sem fio, pede o PS e devolve o controle ao mesmo lugar — sem abrir um segundo assento para ele.

**Onde olhar.** Aba Conexões, quadro Gestão de Controles: a contagem no alto ("4 controles · 2 no cabo · 2 no rádio"), a linha de cada controle ("Sony · Player 3 · cor · rádio") e, dentro da linha aberta, o botão "A luz não acende". No instante do clique aparece no cartão dele um recado dizendo que o controle foi desconectado e pedindo o PS, o botão vira "Cancelar" e os segundos correm para trás até sessenta. No aparelho: a fileira de cinco lampadinhas brancas embaixo do touchpad, que é o que diz o número do jogador.

**Os passos.**

1. Ligue o P1 e o P2 pelo cabo e o P3 e o P4 pelo rádio.
2. Abra o Hefesto e vá para a aba Conexões.
3. Anote a contagem no alto do quadro Gestão de Controles.
4. Anote o número de Player das quatro linhas.
5. Confira que a linha do P3 termina com a palavra rádio.
6. Clique na linha do P3 para abri-la.
7. Clique no botão "A luz não acende".
8. Olhe o P3 na mesa e confirme que ele apagou e caiu.
9. Leia o recado que apareceu no cartão dele e anote a frase inteira.
10. Confira que o botão passou a dizer "Cancelar" e que os segundos estão correndo para trás.
11. Aperte uma vez o botão PS do P3.
12. Espere o chip dele voltar à fita do topo.
13. Leia de novo a contagem do alto do quadro e as quatro linhas.
14. Vire o P3 para cima e conte quais das cinco lampadinhas embaixo do touchpad estão acesas.
15. Repita os passos 6 a 14 no P4.

**Passa quando.** O P3 cai de verdade — ele apaga na mesa —, a tela avisa que o desconectou e pede o PS com os segundos correndo, e depois do PS ele volta na mesma linha, com o mesmo número de Player, sem que nenhuma linha nova apareça para o mesmo controle. A contagem do alto volta ao número de antes. O P4 faz o mesmo quando chega a vez dele. E o P1 e o P2 não se mexem em momento nenhum.

**Por controle.**

* **P1** — No cabo, testemunha. Anote o número de Player dele antes, e olhe a linha dele DURANTE a ausência do P3, não só no fim — já se mediu, nesta casa, um controle trocando de número enquanto o vizinho estava fora e voltando ao certo depois.
* **P2** — No cabo, testemunha, mesma vigilância durante a ausência.
* **P3** — No rádio, e é ESTE primeiro. Abra a linha dele, clique em "A luz não acende", veja o controle apagar na mesa, aperte o PS uma vez e espere voltar.
* **P4** — No rádio, e é ele que fecha o teste: o segundo do mesmo transporte, feito depois. Se o P3 volta certo e o P4 não, o achado é do quarto lugar na fila, não do rádio.

**A armadilha.** O falso verde tem frase própria e é fácil de ler por cima: se a tela responder que o controle não chegou a cair do rádio e que ele continua pareado, nada foi derrubado e nada foi reconectado — o teste não provou coisa nenhuma, refaça. Olhe o controle na mesa: se ele não apagou, não caiu. Segunda, e dá falso vermelho: são sessenta segundos para você apertar o PS, mas o LUGAR do controle fica guardado por trinta. Passando dos trinta ele pode voltar com outro número, e isso é a regra do produto funcionando. Terceira: "Cancelar" não religa nada — se você clicar nele, o controle fica fora do rádio até você apertar o PS por conta própria. Quarta: este gesto refaz a conexão de um controle que JÁ está pareado nesta máquina. O Hefesto não escreve o pareamento dentro do aparelho; se aquele controle nunca foi pareado aqui, o PS não o traz de volta e o teste não roda.

---

## mapa-identidade.req_dev_info-cabo — REQ_DEV_INFO — endereço de rádio e tipo do controle · cabo

*Célula:* `identidade.req_dev_info @ cabo`

**O que isto prova.** Prova que o Hefesto distingue cada controle do cabo pelo endereço do próprio aparelho, e não pelo cabo nem pela porta — trocar de porta não cria um controle novo, e trocar os cabos não troca as identidades.

**Onde olhar.** A contagem no alto de qualquer aba ("4 controles: 2 USB · 2 BT"). A fita do topo, com um chip por controle. A aba Controles, com um cartão por controle. E, sobretudo, a aba Conexões, quadro Gestão de Controles: a contagem do quadro diz quantos estão no cabo e quantos no rádio, e cada controle é uma linha que começa com a marca — Sony — seguida do Player, da cor do plástico e da palavra do transporte. O endereço do aparelho em si não aparece em campo nenhum da tela, e isso é decisão registrada: ele é chave de dentro do produto, não vocabulário de tela. O que você vê é a consequência dele.

**Os passos.**

1. Ligue o P1 e o P2 pelo cabo e o P3 e o P4 pelo rádio.
2. Abra o Hefesto na aba Conexões.
3. Leia a contagem no alto do quadro Gestão de Controles e anote.
4. Conte as linhas do quadro: têm de ser quatro, uma por controle.
5. Anote as quatro linhas inteiras, palavra por palavra.
6. Confira que cada linha começa com a marca Sony.
7. Desencaixe do PC o cabo do P1 e encaixe-o numa porta USB diferente.
8. Espere o chip do P1 voltar à fita do topo.
9. Leia de novo a contagem e as quatro linhas.
10. Confira que continuam quatro linhas e que nenhuma linha nova apareceu para o P1.
11. Confira que o P1 voltou com a mesma cor e a mesma marca de antes.
12. Desencaixe os DOIS cabos do PC ao mesmo tempo.
13. Espere a contagem do quadro cair para dois controles.
14. Encaixe os dois cabos de novo, TROCADOS: o cabo que estava no P1 vai para o P2, e o do P2 vai para o P1.
15. Espere os dois voltarem à fita e leia as quatro linhas outra vez.
16. Compare a cor de cada linha com o plástico do controle que está na sua mão.

**Passa quando.** Com quatro controles ligados há sempre quatro linhas, quatro cartões e quatro chips — nunca três, nunca cinco. Trocar o P1 de porta USB não cria uma linha nova nem apaga a dele. E depois de trocar os dois cabos entre si, cada controle continua carregando a cor do plástico DELE: o Hefesto seguiu o aparelho, e não o cabo nem a porta.

**Por controle.**

* **P1** — No cabo. É ele que muda de porta USB e depois troca de cabo com o P2. Tem de voltar sempre com a mesma cor e a mesma marca.
* **P2** — No cabo, e é ele que denuncia o defeito: recebe o cabo do P1 na segunda metade. Se depois da troca ele aparecer com a cor do P1, o Hefesto está identificando o CABO e não o aparelho.
* **P3** — No rádio, testemunha. A linha dele não pode sumir nem trocar de cor enquanto você mexe nos cabos, e a contagem do quadro tem de continuar dizendo dois no rádio o tempo todo.
* **P4** — No rádio, testemunha, mesma conferência. Se os dois do rádio piscarem para fora do quadro quando você desencaixa os dois cabos, o achado é outro e vale anotar à parte.

**A armadilha.** Não procure o endereço do controle na tela: ele não está lá, e não é esquecimento — foi decidido que na tela um controle fala por número, cor e marca, e que o endereço é chave de dentro. Um teste que mandasse achar o endereço mandaria você caçar um campo que não existe. Segunda: trocar de porta ou desencaixar os dois cabos pode mudar o NÚMERO do jogador, e isso não é o defeito daqui — o que este teste olha é se uma linha se DUPLICA e se a cor muda de dono. Terceira: se um controle passar dos trinta segundos fora, ele volta com outro número, porque o lugar guardado vence — faça a troca dos cabos rápido, e se demorar, refaça em vez de anotar reprovação. Quarta: se um dos dois do cabo aparecer sem nome de cor depois da troca, isso é a leitura da cor não tendo respondido, e tem teste próprio; o que reprova AQUI é a cor aparecer no controle errado.

---

## mapa-identidade.req_dev_info-radio — REQ_DEV_INFO — endereço de rádio e tipo do controle · rádio

*Célula:* `identidade.req_dev_info @ rádio`

**O que isto prova.** Prova que o Hefesto reconhece cada controle do rádio pelo aparelho, e não pela ordem de chegada — ligar os dois na ordem invertida não faz a cor trocar de dono.

**Onde olhar.** Aba Conexões, quadro Gestão de Controles: a contagem no alto e a linha de cada controle, "Sony · Player 3 · cor · rádio". Também a fita do topo, com um chip por controle, e a aba Controles, com um cartão por controle. O endereço do aparelho não aparece em campo nenhum — a fonte diz que ele é chave de dentro do produto. O que se vê é a consequência: quem é quem depois de todo mundo sair e voltar fora de ordem.

**Os passos.**

1. Abra o Hefesto e clique na aba Conexões.
2. Leia as quatro linhas do quadro Gestão de Controles e copie-as num papel, palavra por palavra.
3. Confira qual plástico está na sua mão para cada uma das quatro linhas, e anote ao lado.
4. Segure o botão PS do P3 até todas as luzes dele apagarem.
5. Segure o botão PS do P4 até todas as luzes dele apagarem.
6. Confira que a contagem do quadro caiu para dois controles antes de religar qualquer um.
7. Dê um toque no PS do controle que ANTES era o P4 — agora ele entra primeiro.
8. Veja o chip dele aparecer na fita.
9. Dê um toque no PS do controle que antes era o P3.
10. Veja o chip dele aparecer na fita.
11. Leia as quatro linhas de novo e compare a COR de cada uma com o plástico que está na sua mão.
12. Conte as linhas e confira que continuam quatro, sem nenhum controle repetido.

**Passa quando.** Cada um dos dois controles do rádio voltou carregando a cor do plástico DELE, mesmo tendo entrado na ordem invertida. O número do jogador pode ter trocado entre os dois — isso é a ordem de entrada, e é esperado —, mas a cor não pode seguir a posição. E continuam quatro linhas, sem nenhuma sobrando e sem nenhum controle aparecendo duas vezes.

**Por controle.**

* **P1** — No cabo, testemunha. A linha dele não pode sumir nem trocar de cor enquanto os do rádio saem e voltam.
* **P2** — No cabo, testemunha, mesma conferência. Os dois do cabo juntos provam que a bagunça, se houver, ficou no rádio.
* **P3** — No rádio. Sai primeiro e volta por último — o inverso da ordem em que entrou no começo.
* **P4** — No rádio, e é ele que denuncia o defeito: sai por último e volta primeiro. Se ele voltar com a cor que estava na terceira posição, o nome está vindo do LUGAR e não do aparelho — isso já aconteceu nesta casa e é exatamente o que este teste caça.

**A armadilha.** A ordem de partida é a da faixa fixa do topo da página: o P1 e o P2 já estão no cabo, e pelo rádio o P3 entrou ANTES do P4. É essa ordem que você inverte no meio do teste, e é por isso que a primeira coisa a fazer é copiar as quatro linhas — se você não tiver certeza de quem entrou primeiro, o papel do começo é quem responde. O número do jogador VAI trocar entre os dois, e isso não é o defeito: quem manda no número é a ordem de entrada, e você inverteu a ordem de propósito. Confundir as duas coisas reprova um produto que está certo — o que este teste olha é a COR, que tem de seguir o plástico. Segunda: se um dos dois voltar sem nome de cor, a linha simplesmente não traz o nome, e isso é achado da leitura da cor pelo rádio, que tem teste próprio; aqui o que reprova é a cor TROCAR DE DONO. Terceira: espere a contagem cair para dois antes de religar. Religar com o Hefesto ainda contando quatro mede outra coisa, e o lugar guardado por trinta segundos pode devolver os números antigos e esconder o defeito. Quarta: não plugue cabo em nenhum dos dois durante o teste — pelo cabo a identidade tem outro caminho, e uma passagem pelo fio no meio embaralharia o resultado.

---

## mapa-identidade.revisao_de_placa-cabo — Revisão de placa (`hardware_version` do sysfs) — NÃO é a cor · cabo

*Célula:* `identidade.revisao_de_placa @ cabo`

**O que isto prova.** Prova que o Hefesto nunca nomeia um controle do cabo por um número de placa — o crachá na tela é o número do jogador, a cor e a marca, e mais nada.

**Onde olhar.** Em nenhum campo, e é isso que se prova. Os lugares onde um controle é NOMEADO na tela são quatro: o chip da fita do topo (número, cor e transporte); o cabeçalho do cartão na aba Controles; o cabeçalho da coluna nas abas Iluminação, Gatilhos, Vibração, Navegação e Jogar; e a linha do quadro Gestão de Controles, na aba Conexões (marca, Player, cor, transporte). Em nenhum deles deve aparecer um número de placa, uma sigla de revisão ou um número em hexadecimal — aqueles que começam com zero-x.

**Os passos.**

1. Ligue o P1 e o P2 pelo cabo e o P3 e o P4 pelo rádio.
2. Abra o Hefesto.
3. Leia os quatro chips da fita do topo e escreva no papel exatamente o que cada um diz.
4. Abra a aba Controles e leia o cabeçalho do cartão do P1 e o do P2.
5. Clique na linha do P1 para abrir o cartão e leia tudo o que está dentro, procurando um número de placa ou de revisão.
6. Clique na linha do P2 e faça a mesma leitura.
7. Abra a aba Conexões e leia as linhas do P1 e do P2 no quadro Gestão de Controles.
8. Abra as duas linhas e leia o que aparece dentro de cada uma.
9. Abra as abas Iluminação, Gatilhos, Vibração e Navegação e leia o cabeçalho das colunas do P1 e do P2 em cada uma.
10. Anote qualquer número que apareça e que não seja bateria, volume, brilho ou porcentagem.
11. Se algum número aparecer, anote em que aba, em que campo e qual controle.
12. Compare o número anotado do P1 com o do P2: se forem diferentes, anote isso também.

**Passa quando.** Em nenhum lugar da tela o P1 ou o P2 é nomeado por um número de placa, uma revisão ou um número em hexadecimal. O que os nomeia é o número do jogador, a cor do plástico, a marca e a palavra do transporte.

**Por controle.**

* **P1** — No cabo. Leia os quatro lugares onde ele é nomeado: o chip, o cabeçalho do cartão, o cabeçalho da coluna nas outras abas e a linha da aba Conexões.
* **P2** — No cabo, e ele importa por uma razão precisa: a placa dele é DIFERENTE da do P1 nesta mesa. Se algum campo mostrasse a placa, os dois números apareceriam diferentes e seria fácil confundir isso com identidade de verdade.
* **P3** — No rádio, testemunha. A mesma varredura nos quatro lugares, para o caso de o número aparecer só de um lado.
* **P4** — No rádio, testemunha, mesma varredura.

**A armadilha.** Este número existe, o computador o lê de graça, sem senha e sem atrapalhar nada, e os quatro controles desta mesa têm valores diferentes — o que o faz PARECER um bom crachá. Ele não é, e a decisão de não usá-lo está registrada: ele diz a revisão da PLACA, e os quatro só se distinguem porque foram comprados em lotes diferentes. Dois controles da mesma cor comprados juntos teriam o mesmo número, e quem nomeasse jogador por ele veria dois "controles iguais" no dia da compra. Segunda: não confunda com o nome do modelo do aparelho, que é outra coisa e pode aparecer legitimamente. Terceira, e vale como aviso e não como reprovação: se um número de placa aparecer na tela, ele pode estar IGUAL nos quatro — o controle de mentira que o Hefesto cria para o jogo carrega gravada a placa de um dos controles dela. Um número igual nos quatro não é sinal de que a leitura funciona; é sinal do contrário.

---

## mapa-identidade.revisao_de_placa-radio — Revisão de placa (`hardware_version` do sysfs) — NÃO é a cor · rádio

*Célula:* `identidade.revisao_de_placa @ rádio`

**O que isto prova.** Prova que o Hefesto também não nomeia um controle do rádio por número de placa — nem quando ele cai e volta, que é quando um produto desesperado se agarraria a qualquer número.

**Onde olhar.** Os mesmos quatro lugares onde um controle é nomeado: o chip da fita do topo, o cabeçalho do cartão na aba Controles, o cabeçalho da coluna nas abas Iluminação, Gatilhos, Vibração, Navegação e Jogar, e a linha do quadro Gestão de Controles, na aba Conexões. Nenhum deles deve trazer número de placa, sigla de revisão ou número em hexadecimal — nem com os controles estáveis, nem no instante em que um deles reaparece.

**Os passos.**

1. Ligue o P1 e o P2 pelo cabo e o P3 e o P4 pelo rádio.
2. Abra o Hefesto.
3. Leia os chips do P3 e do P4 na fita do topo e escreva no papel o que cada um diz.
4. Abra a aba Controles e leia o cabeçalho do cartão do P3 e o do P4.
5. Abra os dois cartões e leia tudo o que está dentro, procurando número de placa ou de revisão.
6. Abra a aba Conexões e abra as linhas do P3 e do P4 no quadro Gestão de Controles.
7. Leia as duas linhas abertas inteiras.
8. Abra as abas Iluminação, Gatilhos, Vibração e Navegação e leia o cabeçalho das colunas do P3 e do P4.
9. Segure o botão PS do P3 até todas as luzes dele apagarem.
10. Espere a contagem do quadro cair para três controles.
11. Aperte o PS do P3 uma vez para religá-lo.
12. Olhe a linha dele na aba Conexões no instante em que ela reaparece e leia o que está escrito.
13. Abra o cartão do P3 na aba Controles e leia de novo, procurando qualquer número que não estivesse lá antes.
14. Anote qualquer número que apareça, dizendo em que aba, em que campo e em que momento.

**Passa quando.** Nem com os quatro parados, nem no instante em que o P3 reaparece, nenhum campo mostra um número de placa, uma revisão ou um número em hexadecimal. O P3 e o P4 continuam nomeados por número de jogador, cor, marca e a palavra rádio — antes e depois da queda.

**Por controle.**

* **P1** — No cabo, testemunha. Leia o cabeçalho do cartão dele antes e depois da queda do P3: nenhum número novo pode nascer ali por causa do vizinho.
* **P2** — No cabo, testemunha, mesma leitura antes e depois.
* **P3** — No rádio, e é ESTE que cai e volta. O instante do reaparecimento é o momento do teste: é aí que um produto que não sabe quem chegou se agarraria a um número de placa para decidir.
* **P4** — No rádio, testemunha, e a que mais importa: é o outro do mesmo transporte. Se um número aparecer nele enquanto o P3 está fora, o achado é do rádio ficar sozinho, não da volta.

**A armadilha.** A leitura deste número não muda com o transporte: ela sai do mesmo lugar no computador, de graça, esteja o controle no cabo ou no rádio. Então não espere ver uma diferença entre este teste e o do cabo — o que muda aqui é o MOMENTO em que se olha, e o momento é o da volta. Segunda: os quatro controles desta mesa têm placas diferentes, e isso é acaso de lote, não identidade; dois da mesma cor comprados juntos teriam o mesmo número. Terceira: se um número de placa aparecer, confira se ele é IGUAL nos quatro antes de comemorar — o controle de mentira que o Hefesto cria para o jogo carrega gravada a placa de um dos aparelhos dela, e um número igual nos quatro é sinal de que ninguém leu nada. Quarta: se o P3 demorar mais de trinta segundos para voltar, ele volta com outro número de jogador, e isso é a regra do produto, não a placa mandando na identidade.

---

# luz

---

## mapa-luz.led_jogador-cabo — LED de jogador (as lâmpadas de numeração) · cabo

*Célula:* `luz.led_jogador @ cabo`

**O que isto prova.** Prova que trocar o número de um controle ligado por cabo faz as cinco lâmpadas dele mudarem de desenho no plástico, e que os dois do rádio não se mexem.

**Onde olhar.** O lugar que decide é o APARELHO: a fileira de cinco lâmpadas brancas logo abaixo do touchpad. Na tela, a aba Iluminação: cada controle tem uma coluna, e a linha chamada "Jogador" traz quatro botões — 1, 2, 3 e 4 —, cada um com um anelzinho na cor do plástico de quem tem aquele número hoje. No pé da mesma aba fica a seção "Trocar o número: o antes e o depois", onde cada controle aparece como P1 a P4 com o nome e as cinco lâmpadas desenhadas. E a fita do topo, a linha que começa com "Selecionar:", diz por onde cada um fala: o chip termina em USB para cabo e em BT para rádio.

**Os passos.**

1. Feche o jogo, se houver algum aberto.
2. Confira na fita do topo que os chips do P1 e do P2 terminam em USB e os do P3 e do P4 terminam em BT.
3. Abra a aba Iluminação.
4. Vire os quatro controles para cima e anote quais lâmpadas estão acesas em cada um.
5. Confira que o P1 tem só a do meio, o P2 a segunda e a quarta, o P3 as duas pontas e a do meio, e o P4 as quatro das pontas com a do meio apagada.
6. Clique no botão "2" da linha "Jogador", na coluna do P1.
7. Olhe o aparelho em que você mexeu: as cinco lâmpadas dele têm de virar o desenho do 2 — a segunda e a quarta.
8. Olhe o outro aparelho do cabo: ele recebeu o 1 na troca, e as lâmpadas dele têm de virar o desenho do 1 — só a do meio.
9. Olhe os dois aparelhos do rádio: nenhuma lâmpada pode ter mudado.
10. Leia a seção "Trocar o número: o antes e o depois", no pé da aba, e confira que ela conta essa mesma troca.
11. Ache na tela a coluna do mesmo aparelho de cabo em que você mexeu — agora ele é o P2 — e clique no botão "1" da linha "Jogador" dessa coluna, para desfazer.
12. Confira nos quatro aparelhos que as lâmpadas voltaram ao desenho que você anotou no começo.

**Passa quando.** As cinco lâmpadas dos DOIS controles do cabo trocam de desenho no mesmo gesto: quem recebeu o 2 passa a mostrar o desenho do 2 e quem ficou com o 1 passa a mostrar o do 1 — no plástico, não só na tela. As lâmpadas dos dois do rádio não se mexem em instante nenhum. E desfazer devolve os quatro ao desenho de partida.

**Por controle.**

* **P1** — Cabo, e é a coluna em que você clica. Dê a ele o número 2 e veja as cinco lâmpadas dele virarem o desenho do 2 no plástico.
* **P2** — Cabo, e não se clica na coluna dele: ele recebe o 1 pela troca. As lâmpadas dele têm de virar o desenho do 1 no mesmo instante — é a outra metade do gesto, e sem ela a troca ficou pela metade.
* **P3** — Rádio, testemunha. Não toque. Nenhuma lâmpada dele pode mudar; se mudar, o comando pegou mais do que os dois controles do cabo.
* **P4** — Rádio, segunda testemunha, e a que mais importa: é o último da fila e o primeiro a se desarrumar. Nenhuma lâmpada pode mudar, e o número dele tem de continuar o mesmo no fim.

**A armadilha.** Três. A primeira é contar as lâmpadas da esquerda para a direita: o número é o CONJUNTO aceso, e os cinco desenhos são simétricos — quem lê "a terceira acesa" como jogador 3 reprova um produto que está certo. A segunda é o jogo aberto: com uma partida em curso o botão do número RECUSA e explica, com a frase "Feche o jogo antes de trocar o número" aparecendo na coluna daquele controle e sumindo sozinha; isso é o produto funcionando, não defeito. A terceira é onde a prova parou: no mapa desta casa esta linha está em MONTOU — a ordem é montada e ninguém registrou o instante em que ela saiu no fio. Se as lâmpadas não mudarem, anote e siga: este teste é a medição que faltava, não erro seu. E não confunda a linha "Jogador" com as teclas P1 a P4 da linha "LEDs": elas parecem a mesma coisa e são opostas — aquela dá o NÚMERO, esta dá só o desenho.

---

## mapa-luz.led_jogador-radio — LED de jogador (as lâmpadas de numeração) · rádio

*Célula:* `luz.led_jogador @ rádio`

**O que isto prova.** Prova que trocar o número de um controle ligado por rádio faz as cinco lâmpadas dele mudarem de desenho no plástico, e que os dois do cabo não se mexem.

**Onde olhar.** O lugar que decide é o APARELHO: a fileira de cinco lâmpadas brancas logo abaixo do touchpad. Na tela, a aba Iluminação: a linha "Jogador" da coluna de cada controle, com os quatro botões 1, 2, 3 e 4. No pé da aba, a seção "Trocar o número: o antes e o depois". E a fita do topo, onde o chip do controle do rádio termina em BT.

**Os passos.**

1. Feche o jogo, se houver algum aberto.
2. Confira na fita do topo que os chips do P3 e do P4 terminam em BT e os do P1 e do P2 terminam em USB.
3. Abra a aba Iluminação.
4. Vire os quatro controles para cima e anote quais lâmpadas estão acesas em cada um.
5. Confira que o P3 tem as duas pontas e a do meio, e que o P4 tem as quatro das pontas com a do meio apagada.
6. Clique no botão "4" da linha "Jogador", na coluna do P3.
7. Olhe o aparelho em que você mexeu: as cinco lâmpadas dele têm de virar o desenho do 4 — as quatro das pontas, com a do meio apagada.
8. Olhe o outro aparelho do rádio: ele recebeu o 3 na troca, e as lâmpadas dele têm de virar o desenho do 3 — as duas pontas e a do meio.
9. Olhe os dois aparelhos do cabo: nenhuma lâmpada pode ter mudado.
10. Leia a seção "Trocar o número: o antes e o depois", no pé da aba, e confira que ela conta essa mesma troca.
11. Ache na tela a coluna do mesmo aparelho de rádio em que você mexeu — agora ele é o P4 — e clique no botão "3" da linha "Jogador" dessa coluna, para desfazer.
12. Confira nos quatro aparelhos que as lâmpadas voltaram ao desenho que você anotou no começo.

**Passa quando.** As cinco lâmpadas dos DOIS controles do rádio trocam de desenho no mesmo gesto, no plástico: quem recebeu o 4 mostra o desenho do 4 e quem ficou com o 3 mostra o do 3. As lâmpadas dos dois do cabo não se mexem em instante nenhum. E desfazer devolve os quatro ao desenho de partida.

**Por controle.**

* **P1** — Cabo, testemunha. Não toque. Nenhuma lâmpada dele pode mudar — ele é quem separa "o comando foi para o controle escolhido" de "o comando pegou a máquina inteira".
* **P2** — Cabo, segunda testemunha. Não toque. Se ele mudar junto e o P1 não, anote qual dos dois — a diferença entre eles já seria um achado.
* **P3** — Rádio, e é a coluna em que você clica. Dê a ele o número 4 e veja as cinco lâmpadas dele virarem o desenho do 4 no plástico. Este é o lado do teste que pode falhar de verdade: pelo rádio a ordem viaja num envelope diferente.
* **P4** — Rádio, e não se clica na coluna dele: ele recebe o 3 pela troca, e as lâmpadas dele têm de virar o desenho do 3 no mesmo instante.

**A armadilha.** Quatro. Contar as lâmpadas da esquerda para a direita reprova um produto certo — o número é o conjunto aceso, e os cinco desenhos são simétricos. Com o jogo aberto o botão do número RECUSA e diz "Feche o jogo antes de trocar o número" na coluna daquele controle: é o produto funcionando. No mapa desta casa esta linha está em MONTOU nos dois transportes — a ordem é montada e ninguém registrou o instante em que ela saiu no fio —, então "as lâmpadas não mudaram" é achado publicável e não erro seu. E o rádio tem um risco só dele: se o controle cair e voltar no meio do gesto, o que você vai ver é a reconexão, não a troca; se o chip dele piscar para fora da fita do topo, refaça.

---

## mapa-luz.led_jogador.escrita_hefesto-cabo — LED de jogador — escrita pelo Hefesto · cabo

*Célula:* `luz.led_jogador.escrita_hefesto @ cabo`

**O que isto prova.** Prova que o Hefesto acende e apaga cada uma das cinco lâmpadas de um controle do cabo sem mexer no número dele.

**Onde olhar.** Aba Iluminação, linha "LEDs" da coluna de cada controle. Ali ficam as duas tiras de luz e, entre elas, as cinco lâmpadas — e cada lâmpada é um botão. Ao lado delas há seis teclas: quatro escritas P1, P2, P3 e P4, uma com cinco pontinhos cheios e uma com cinco pontinhos vazios. Embaixo dessa linha pode aparecer uma frase de ressalva — ela é sobre a BARRA de luz, não sobre as lâmpadas. A prova é o aparelho: as cinco lâmpadas brancas abaixo do touchpad. O número do controle se lê na linha "Jogador", logo acima, no botão que está aceso.

**Os passos.**

1. Feche o jogo, se houver algum aberto.
2. Confira que há um nome escrito em "Perfil ativo", no alto da tela.
3. Abra a aba Iluminação.
4. Vire o P1 para cima e anote quais lâmpadas estão acesas.
5. Clique na tecla "P3" da linha "LEDs", na coluna do P1.
6. Olhe o aparelho do P1: as lâmpadas têm de virar as duas pontas e a do meio.
7. Olhe a linha "Jogador" da coluna do P1: o botão aceso tem de continuar sendo o 1.
8. Clique na primeira das cinco lâmpadas da coluna do P1, na tela.
9. Olhe o aparelho: aquela lâmpada tem de apagar, e só ela.
10. Clique nela de novo e confirme que ela volta a acender.
11. Repita os passos 4 a 10 na coluna do P2.
12. Olhe o P3 e o P4 e confirme que nenhuma lâmpada deles mudou em momento nenhum.
13. Clique na tecla dos cinco pontinhos vazios na coluna do P1 e depois na do P2.
14. Confira nos dois aparelhos que o desenho voltou a ser o do número de cada um.

**Passa quando.** Cada clique numa lâmpada acende ou apaga aquela lâmpada no plástico, e só ela. A tecla P3 põe o desenho do 3 no aparelho sem mudar o número do controle, que continua 1 na linha "Jogador". Nada disso acontece no P3 nem no P4. E a tecla dos pontinhos vazios devolve as cinco ao desenho do número.

**Por controle.**

* **P1** — Cabo, e é ESTE. Todos os cliques são na coluna dele: a tecla P3 primeiro, depois uma lâmpada de cada vez.
* **P2** — Cabo, e é a segunda volta — não é enfeite. Ele prova que a escrita é por CONTROLE e não por transporte: se o P1 obedecer e o P2 não, os dois estão no mesmo cabo e a diferença é do controle.
* **P3** — Rádio, testemunha. Não toque na coluna dele. Nenhuma lâmpada pode mudar enquanto você mexe nos do cabo.
* **P4** — Rádio, segunda testemunha. Não toque. Se as lâmpadas dele mudarem junto com as do P1, o comando pegou o transporte inteiro em vez do controle escolhido.

**A armadilha.** Duas recusas parecem defeito e não são. Se um jogo em co-op estiver mandando nas cinco luzes, o clique na lâmpada RECUSA e diz isso na coluna daquele controle — e nesse caso as cinco lâmpadas da TELA nascem apagadas de propósito, porque quem manda não é esta tela; o caminho que ainda move as luzes nesse estado é dar o número, na linha "Jogador". Sem nome em "Perfil ativo" o clique recusa também, porque o desenho é do perfil e não da máquina. Terceira: a tecla dos cinco pontinhos vazios NÃO é "apagar as cinco" — ela tira o desenho próprio e devolve o comando ao número; é o caminho de volta, e é por isso que ela está no fim dos passos e não no meio. Quarta: não julgue pela tela — as cinco lâmpadas desenhadas mostram o que o Hefesto pediu, nunca o que o aparelho está exibindo.

---

## mapa-luz.led_jogador.escrita_hefesto-radio — LED de jogador — escrita pelo Hefesto · rádio

*Célula:* `luz.led_jogador.escrita_hefesto @ rádio`

**O que isto prova.** Prova que o desenho das cinco lâmpadas escrito pelo Hefesto chega a um controle do rádio — e que ele sobrevive quando o Hefesto refaz as contas, que é onde o rádio costuma perder.

**Onde olhar.** Aba Iluminação, linha "LEDs" da coluna de cada controle: as cinco lâmpadas clicáveis e, ao lado, as seis teclas de desenho (P1, P2, P3, P4, uma com cinco pontinhos cheios e uma com cinco vazios). Aba Jogar, linha "Status", com as posições Ligado e Desligado. E o aparelho: as cinco lâmpadas brancas abaixo do touchpad.

**Os passos.**

1. Feche o jogo, se houver algum aberto.
2. Confira na fita do topo que os chips do P3 e do P4 terminam em BT.
3. Confira que há um nome escrito em "Perfil ativo".
4. Abra a aba Iluminação.
5. Clique na tecla "P4" da linha "LEDs", na coluna do P3.
6. Olhe o aparelho do P3: as lâmpadas têm de virar as quatro das pontas, com a do meio apagada.
7. Clique na tecla "P1" da linha "LEDs", na coluna do P4.
8. Olhe o aparelho do P4: tem de ficar só a lâmpada do meio acesa.
9. Clique na tecla "P4" da linha "LEDs", na coluna do P1, e confirme no aparelho dele.
10. Anote os três desenhos que você acabou de escrever, um por controle.
11. Abra a aba Jogar.
12. Clique em "Desligado", na linha "Status".
13. Clique em "Ligado", na mesma linha.
14. Volte a olhar os três aparelhos em que você escreveu.
15. Anote quais mantiveram o desenho escrito e quais voltaram ao desenho do número.
16. Volte à aba Iluminação e clique na tecla dos cinco pontinhos vazios nas colunas do P1, do P3 e do P4, para desfazer.

**Passa quando.** O desenho chega ao plástico dos dois controles do rádio no instante do clique, igual ao do cabo. E depois de passar o Status por Desligado e voltar a Ligado, o desenho continua lá nos três — o do cabo e os dois do rádio. Se o do cabo mantiver e os do rádio voltarem ao desenho do número, o teste achou exatamente o que veio procurar, e a resposta é "os do rádio perderam".

**Por controle.**

* **P1** — Cabo, e aqui ele não é testemunha: é o CONTROLE DE COMPARAÇÃO. Escreva nele o mesmo tipo de desenho e faça a mesma volta pelo Status. Sem ele você não sabe se quem falhou foi o rádio ou o gesto inteiro.
* **P2** — Cabo, testemunha de verdade. Não toque. As lâmpadas dele têm de continuar no desenho do número dele do começo ao fim.
* **P3** — Rádio, e é ESTE. Escreva o desenho do 4 nele e confira no plástico. Depois da volta pelo Status é nele que se olha primeiro.
* **P4** — Rádio, e o segundo alvo. Escreva o desenho do 1 nele — diferente do que você deu ao P3, de propósito: se os dois voltarem iguais depois do Status, os dois perderam para a mesma coisa.

**A armadilha.** O "Desligado" da linha Status é o Modo Nativo: nele o Hefesto sai do meio e não escreve nada no aparelho, então o que estiver aceso durante esses segundos foi o sistema que pôs — a leitura que vale é a de DEPOIS de voltar para Ligado. No mapa desta casa o lado do rádio desta linha está marcado como PARCIAL, e o motivo escrito é justamente que ninguém pôs o aparelho na mesa para as lâmpadas por rádio: este teste é a primeira medição, e "não sobreviveu" é achado publicável, não erro seu. As duas recusas de sempre continuam valendo — co-op mandando nas luzes, e nenhum nome em "Perfil ativo". E não faça este teste com a Steam aberta: com ela viva quem escreve por último no aparelho ganha, e você mediria a disputa em vez do rádio.

---

## mapa-luz.led_jogador.leitura-cabo — LED de jogador — leitura (saber o que está aceso) · cabo

*Célula:* `luz.led_jogador.leitura @ cabo`

**O que isto prova.** Prova que a tela mostra o desenho de lâmpadas que o Hefesto PEDIU, e nunca o que a lâmpada do controle do cabo está fazendo de verdade.

**Onde olhar.** Três desenhos das mesmas cinco lâmpadas, em três lugares. No aparelho: a fileira abaixo do touchpad. Na aba Iluminação: a linha "LEDs" da coluna do controle. Na aba Controles: dentro do card ABERTO daquele controle, o bloco chamado "LED do jogador" — e a dica desse bloco, que aparece ao passar o mouse, diz com todas as letras que ele é derivado do NÚMERO do jogador e não lido do aparelho. Os cards abrem um de cada vez: abrir um fecha o que estava aberto.

**Os passos.**

1. Feche o jogo, se houver algum aberto.
2. Confira que há um nome escrito em "Perfil ativo".
3. Abra a aba Iluminação.
4. Clique na tecla "P3" da linha "LEDs", na coluna do P1.
5. Olhe o aparelho do P1 e anote quais lâmpadas ficaram acesas.
6. Olhe as cinco lâmpadas da linha "LEDs" da coluna do P1 e anote o desenho que a tela mostra.
7. Abra a aba Controles.
8. Clique na linha do P1 para abrir o card dele.
9. Ache o bloco "LED do jogador" dentro do card e anote o desenho que ele mostra.
10. Passe o mouse por cima desse bloco e leia a dica que aparece.
11. Compare os três desenhos anotados: o do plástico, o da aba Iluminação e o do card.
12. Repita os passos 4 a 11 no P2.
13. Volte à aba Iluminação e clique na tecla dos cinco pontinhos vazios nas colunas do P1 e do P2, para desfazer.

**Passa quando.** O desenho da linha "LEDs" da aba Iluminação acompanha o que você escreveu. O bloco "LED do jogador" do card, não: ele continua mostrando o desenho do NÚMERO do controle, que agora é outro. Os dois discordarem é o resultado ESPERADO — é a prova de que nenhuma das duas telas lê o aparelho. Reprova se alguma das duas afirmar, por texto ou por dica, que está lendo o controle.

**Por controle.**

* **P1** — Cabo, e é ESTE. Escreva nele o desenho do 3, depois compare os três lugares no mesmo minuto.
* **P2** — Cabo, segunda volta. O mesmo gesto, e serve para separar "a tela não lê" de "a tela não leu deste controle".
* **P3** — Rádio, testemunha. Não toque. Nem o plástico nem os dois desenhos de tela dele podem mudar.
* **P4** — Rádio, segunda testemunha. Não toque, e confira também o bloco "LED do jogador" do card dele: como ele deriva do número, ele não pode mudar enquanto você só escreve desenho nos outros.

**A armadilha.** Não trate a discordância entre as duas telas como defeito de pintura: ela É o achado deste teste. O que seria defeito é a tela afirmar um desenho e o plástico mostrar outro SEM ninguém ter escrito nada — e para separar os dois casos é obrigatório anotar os três desenhos no mesmo minuto, como os passos pedem. Há um segundo motivo, e ele é de hardware: em revisões novas do DualSense duas lâmpadas ficam presas a outras duas por dentro, então o plástico pode divergir do que foi pedido mesmo com a escrita inteira dando certo — quem mede isso é o teste da quinta lâmpada, e enquanto ele não for feito não se pode acusar a tela por essa diferença. E este lado do mapa está marcado como respondido por leitura de código, sem aparelho na mesa: o que você anotar aqui é a primeira medição.

---

## mapa-luz.led_jogador.leitura-radio — LED de jogador — leitura (saber o que está aceso) · rádio

*Célula:* `luz.led_jogador.leitura @ rádio`

**O que isto prova.** Prova que, num controle do rádio, a tela também mostra só o desenho que o Hefesto pediu — e não o que a lâmpada está fazendo.

**Onde olhar.** Os mesmos três lugares do irmão do cabo. No aparelho: as cinco lâmpadas brancas abaixo do touchpad. Na aba Iluminação: a linha "LEDs" da coluna do controle. Na aba Controles: o bloco "LED do jogador", dentro do card aberto — com a dica que diz que ele é derivado do número, não lido do aparelho. Os cards abrem um de cada vez. A fita do topo confirma que o chip do controle termina em BT.

**Os passos.**

1. Feche o jogo, se houver algum aberto.
2. Confira na fita do topo que os chips do P3 e do P4 terminam em BT.
3. Confira que há um nome escrito em "Perfil ativo".
4. Abra a aba Iluminação.
5. Clique na tecla "P1" da linha "LEDs", na coluna do P3.
6. Olhe o aparelho do P3 e anote quais lâmpadas ficaram acesas.
7. Olhe as cinco lâmpadas da linha "LEDs" da coluna do P3 e anote o desenho que a tela mostra.
8. Abra a aba Controles.
9. Clique na linha do P3 para abrir o card dele.
10. Ache o bloco "LED do jogador" dentro do card e anote o desenho que ele mostra.
11. Compare os três desenhos anotados: o do plástico, o da aba Iluminação e o do card.
12. Repita os passos 5 a 11 no P4.
13. Volte à aba Iluminação e clique na tecla dos cinco pontinhos vazios nas colunas do P3 e do P4, para desfazer.

**Passa quando.** No rádio a resposta tem de ser a MESMA do cabo: a linha "LEDs" acompanha o que você escreveu, e o bloco "LED do jogador" do card continua mostrando o desenho do número. Nenhuma das duas telas muda por causa do que está no plástico. Se pelo rádio alguma delas se comportar diferente da do cabo, anote a diferença — é isso que os dois testes irmãos existem para achar.

**Por controle.**

* **P1** — Cabo, testemunha e comparação. Não escreva nada nele, mas olhe o bloco "LED do jogador" do card dele no fim: ele tem de continuar mostrando o desenho do número.
* **P2** — Cabo, testemunha. Não toque. Nada dele pode mudar enquanto você só escreve nos do rádio.
* **P3** — Rádio, e é ESTE. Escreva nele o desenho do 1 e compare os três lugares no mesmo minuto.
* **P4** — Rádio, segunda volta. O mesmo gesto — e é ele que diz se a resposta é do transporte ou daquele aparelho.

**A armadilha.** A discordância entre as duas telas é o resultado esperado, não um defeito de pintura. E há uma armadilha que só existe no rádio: se o controle cair e voltar no meio do teste, tanto o desenho do plástico quanto o da tela podem mudar sem ninguém ter clicado — olhe o chip dele na fita do topo antes de concluir qualquer coisa, e se ele tiver piscado para fora, refaça. O mapa diz que aqui não há diferença de transporte na leitura: a falta é a mesma dos dois lados, porque não existe caminho nenhum que pergunte ao aparelho o que está aceso. E este lado foi respondido por leitura de código, sem aparelho na mesa — o que você anotar é a primeira medição.

---

## mapa-luz.led_jogador.padrao_driver-cabo — LED de jogador — o padrão que o driver acende na probe · cabo

*Célula:* `luz.led_jogador.padrao_driver @ cabo`

**O que isto prova.** Prova qual desenho de lâmpadas o Linux acende sozinho no instante em que um controle entra pelo cabo, com o Hefesto fora do meio.

**Onde olhar.** O APARELHO, e só ele: as cinco lâmpadas brancas abaixo do touchpad, no primeiro segundo depois de encaixar o cabo. A fonte não diz onde esse desenho de partida apareça em campo nenhum da tela — ele existe só no plástico, e por um instante. Na tela ficam os dois lugares de antes e depois: a aba Jogar, linha "Status" (Ligado / Desligado) com o quadro "Modo" logo abaixo; e a fita do topo, para ler o número que o Hefesto dá a cada um depois.

**Os passos.**

1. Feche o jogo, se houver algum aberto.
2. Abra a aba Jogar.
3. Clique em "Desligado", na linha "Status".
4. Confirme que o quadro "Modo" passou a mostrar "Modo Nativo".
5. Desencaixe o cabo do P1.
6. Conte até cinco, devagar.
7. Encaixe o cabo de volta no P1 olhando as cinco lâmpadas dele.
8. Anote o PRIMEIRO desenho que acende, e anote também se ele aparece de uma vez ou se sobe devagar.
9. Desencaixe o cabo do P2.
10. Conte até cinco, devagar.
11. Encaixe o cabo de volta no P2 olhando as cinco lâmpadas dele.
12. Anote o primeiro desenho que acende nele.
13. Volte à aba Jogar e clique em "Ligado", na linha "Status".
14. Leia a fita do topo e anote o número que o Hefesto deu a cada um dos dois.
15. Compare, controle por controle: o desenho de partida que você anotou é o do mesmo número que o Hefesto deu?

**Passa quando.** Cada controle acende sozinho um dos cinco desenhos conhecidos assim que entra pelo cabo, sem o Hefesto no meio, e ele SOBE DEVAGAR em vez de aparecer de uma vez. O que este teste entrega é a comparação do último passo: se o desenho de partida não for o do número que o Hefesto dá depois, anote os dois lado a lado — era exatamente isso que se queria medir.

**Por controle.**

* **P1** — Cabo, e é o primeiro a religar. Anote o desenho que ele acende sozinho, antes de o Hefesto dizer qualquer coisa.
* **P2** — Cabo, e religue-o DEPOIS do P1. Ele é a metade que interessa: veja se o desenho de partida dele é o seguinte na fila ou se repete o do P1 — é isso que diz se o Linux está contando ou repetindo.
* **P3** — Rádio, não toque. Fica ligado o tempo todo, e serve para provar que desencaixar cabo não mexe em quem está no rádio.
* **P4** — Rádio, não toque. Olhe as lâmpadas dele no fim: o desenho não pode ter mudado por causa dos dois religamentos do cabo.

**A armadilha.** Não espere que o desenho de partida bata com o número que o Hefesto dá. Quem escolhe esse desenho é um contador do Linux que conta QUALQUER aparelho de PlayStation na máquina — inclusive os controles virtuais que o próprio Hefesto cria —, e ele dá a volta a cada cinco: divergência aqui é o fato, não a falha. Segunda: a subida devagar é do próprio Linux, e não lentidão da máquina — quem for cronometrar alguma coisa tem de descontá-la. Terceira: com o Status em Ligado o Hefesto escreve por cima quase na hora e você mediria o Hefesto em vez do Linux — é por isso que o Modo Nativo é o primeiro passo, e não uma sugestão. E a prova desta linha veio de leitura do driver, sem aparelho na mesa: o que você anotar aqui é a primeira medição.

---

## mapa-luz.led_jogador.padrao_driver-radio — LED de jogador — o padrão que o driver acende na probe · rádio

*Célula:* `luz.led_jogador.padrao_driver @ rádio`

**O que isto prova.** Prova qual desenho de lâmpadas o Linux acende sozinho no instante em que um controle volta pelo rádio, com o Hefesto fora do meio.

**Onde olhar.** O APARELHO, e só ele: as cinco lâmpadas brancas abaixo do touchpad, no primeiro segundo depois de o controle voltar. A fonte não diz onde esse desenho de partida apareça em campo nenhum da tela. Na tela ficam o antes e o depois: a aba Jogar, linha "Status" (Ligado / Desligado) com o quadro "Modo"; e a fita do topo, para ler o número que o Hefesto dá depois e confirmar que o chip termina em BT.

**Os passos.**

1. Feche o jogo, se houver algum aberto.
2. Confira na fita do topo que os chips do P3 e do P4 terminam em BT.
3. Abra a aba Jogar.
4. Clique em "Desligado", na linha "Status".
5. Confirme que o quadro "Modo" passou a mostrar "Modo Nativo".
6. Segure o botão PS do P3 até todas as luzes dele apagarem, e solte.
7. Conte até cinco, devagar.
8. Dê um toque curto no botão PS do P3 olhando as cinco lâmpadas dele.
9. Anote o PRIMEIRO desenho que acende, e anote se ele aparece de uma vez ou se sobe devagar.
10. Repita os passos 6 a 9 no P4.
11. Volte à aba Jogar e clique em "Ligado", na linha "Status".
12. Leia a fita do topo e anote o número que o Hefesto deu a cada um dos dois.
13. Compare, controle por controle: o desenho de partida é o do mesmo número que o Hefesto deu?

**Passa quando.** Cada controle do rádio acende sozinho um dos cinco desenhos conhecidos assim que volta, sem o Hefesto no meio, e ele sobe devagar. A entrega é a comparação do último passo: o desenho de partida contra o número que o Hefesto dá depois, anotados lado a lado para os dois controles do rádio.

**Por controle.**

* **P1** — Cabo, não toque. Fica ligado o tempo todo, e as lâmpadas dele não podem mudar enquanto os do rádio vão e voltam.
* **P2** — Cabo, não toque. Segunda testemunha do cabo: se ele mudar de desenho quando um do rádio volta, o contador do Linux mexeu em quem não saiu.
* **P3** — Rádio, e é o primeiro a desligar e religar. Anote o desenho que ele acende sozinho antes de o Hefesto dizer qualquer coisa.
* **P4** — Rádio, e religue-o DEPOIS do P3. É ele que diz se o Linux avança na fila ou repete o desenho do anterior.

**A armadilha.** Soltar o botão PS cedo demais: o controle não desliga e você mede o seu gesto, não o produto — segure até TODAS as luzes apagarem. Não espere que o desenho de partida bata com o número do Hefesto: quem escolhe é um contador do Linux que conta qualquer aparelho de PlayStation da máquina, virtuais inclusive, e dá a volta a cada cinco. A subida devagar é do próprio Linux. E com o Status em Ligado você mediria o Hefesto e não o Linux — o Modo Nativo é obrigatório aqui. Por fim: o controle precisa já estar pareado nesta máquina, senão o toque no PS não o traz de volta e o teste não roda; e esta linha foi respondida por leitura do driver, sem aparelho na mesa.

---

## mapa-luz.led_jogador.quinto-cabo — LED de jogador — a quinta lâmpada · cabo

*Célula:* `luz.led_jogador.quinto @ cabo`

**O que isto prova.** Prova se, num controle do cabo, a quinta lâmpada acende sozinha ou se ela vem colada à primeira.

**Onde olhar.** Aba Iluminação, linha "LEDs" da coluna do controle: as cinco lâmpadas, cada uma um botão, e ao lado as seis teclas de desenho (P1, P2, P3, P4, uma com cinco pontinhos cheios e uma com cinco vazios). O aparelho: as cinco lâmpadas brancas abaixo do touchpad, contadas AQUI da esquerda para a direita como 1, 2, 3, 4 e 5.

**Os passos.**

1. Feche o jogo, se houver algum aberto.
2. Confira que há um nome escrito em "Perfil ativo".
3. Abra a aba Iluminação.
4. Clique na tecla dos cinco pontinhos CHEIOS, na linha "LEDs" da coluna do P1.
5. Confirme no aparelho do P1 que as cinco lâmpadas acenderam.
6. Clique na PRIMEIRA das cinco lâmpadas da coluna do P1, na tela, para apagá-la.
7. Olhe o aparelho: têm de sobrar quatro acesas, com a primeira apagada.
8. Anote o que a QUINTA lâmpada do aparelho está fazendo neste momento.
9. Clique na primeira lâmpada de novo para acendê-la.
10. Clique na QUINTA lâmpada da coluna do P1 para apagá-la.
11. Olhe o aparelho: têm de sobrar quatro acesas, com a última apagada.
12. Anote o que a PRIMEIRA lâmpada do aparelho está fazendo neste momento.
13. Repita os passos 4 a 12 na coluna do P2.
14. Clique na tecla dos cinco pontinhos vazios nas colunas do P1 e do P2, para desfazer.

**Passa quando.** A primeira e a quinta lâmpadas obedecem SEPARADAMENTE: apagar uma deixa a outra acesa, nas duas direções e nos dois controles do cabo. Se apagar a primeira apagar a quinta junto — ou o contrário —, o teste achou o que veio procurar: nesse aparelho as duas estão ligadas por dentro, e a mesma coisa vale para a segunda com a quarta.

**Por controle.**

* **P1** — Cabo, e é ESTE. Acenda as cinco, apague só a primeira, olhe a quinta; depois devolva a primeira, apague só a quinta e olhe a primeira.
* **P2** — Cabo, e a segunda volta é obrigatória: a resposta aqui é de REVISÃO DE HARDWARE, não de programa. Dois aparelhos podem responder diferente, e isso é resultado, não erro.
* **P3** — Rádio, testemunha. Não toque. Nenhuma lâmpada dele pode mudar enquanto você mexe nos do cabo.
* **P4** — Rádio, segunda testemunha. Não toque. Se as lâmpadas dele acompanharem as do P1, o comando saiu do controle escolhido.

**A armadilha.** Este é o ÚNICO teste da família em que se conta as lâmpadas da esquerda para a direita, porque aqui se acende uma por vez e não um dos desenhos de número. Todos os cinco desenhos de número são simétricos — é por isso que essa diferença nunca aparece jogando, e por isso ela só se enxerga com um desenho torto como este. Não use a tecla dos pontinhos vazios no meio do teste: ela tira o desenho próprio e devolve o comando ao número, e você perderia o padrão torto. As duas recusas de sempre valem — co-op mandando nas luzes, e nenhum nome em "Perfil ativo". E o mais importante: o mapa marca esta linha como afirmada por UM documento só, sem segunda fonte independente, e diz que só o aparelho fecha isto — o que você anotar aqui vale mais que a página que a originou.

---

## mapa-luz.led_jogador.quinto-radio — LED de jogador — a quinta lâmpada · rádio

*Célula:* `luz.led_jogador.quinto @ rádio`

**O que isto prova.** Prova se, num controle do rádio, a quinta lâmpada acende sozinha ou se ela vem colada à primeira.

**Onde olhar.** Aba Iluminação, linha "LEDs" da coluna do controle: as cinco lâmpadas, cada uma um botão, e ao lado as seis teclas de desenho (P1, P2, P3, P4, uma com cinco pontinhos cheios e uma com cinco vazios). O aparelho: as cinco lâmpadas brancas abaixo do touchpad, contadas AQUI da esquerda para a direita como 1, 2, 3, 4 e 5. A fita do topo confirma que o chip do controle termina em BT.

**Os passos.**

1. Feche o jogo, se houver algum aberto.
2. Confira na fita do topo que os chips do P3 e do P4 terminam em BT.
3. Confira que há um nome escrito em "Perfil ativo".
4. Abra a aba Iluminação.
5. Clique na tecla dos cinco pontinhos CHEIOS, na linha "LEDs" da coluna do P3.
6. Confirme no aparelho do P3 que as cinco lâmpadas acenderam.
7. Clique na PRIMEIRA das cinco lâmpadas da coluna do P3, para apagá-la.
8. Olhe o aparelho e anote o que a QUINTA lâmpada está fazendo.
9. Clique na primeira lâmpada de novo para acendê-la.
10. Clique na QUINTA lâmpada da coluna do P3 para apagá-la.
11. Olhe o aparelho e anote o que a PRIMEIRA lâmpada está fazendo.
12. Repita os passos 5 a 11 na coluna do P4.
13. Clique na tecla dos cinco pontinhos vazios nas colunas do P3 e do P4, para desfazer.

**Passa quando.** A primeira e a quinta lâmpadas obedecem separadamente nos dois controles do rádio, nas duas direções — e a resposta é IGUAL à do teste irmão do cabo. Se um aparelho colar as duas e o outro não, a diferença é do aparelho e não do rádio, e é isso que os dois testes juntos permitem afirmar.

**Por controle.**

* **P1** — Cabo, testemunha. Não toque. Nenhuma lâmpada dele pode mudar enquanto você mexe nos do rádio.
* **P2** — Cabo, segunda testemunha. Não toque. Se as lâmpadas dele acompanharem as do P3, o comando pegou mais do que o controle escolhido.
* **P3** — Rádio, e é ESTE. Acenda as cinco, apague só a primeira e olhe a quinta; depois devolva a primeira, apague só a quinta e olhe a primeira.
* **P4** — Rádio, segunda volta. A resposta é de revisão de hardware, então dois aparelhos podem discordar — e é exatamente isso que se quer saber.

**A armadilha.** Aqui, e só aqui na família, conta-se as lâmpadas da esquerda para a direita: é o único teste com um desenho torto, e os cinco desenhos de número são simétricos, motivo pelo qual essa colagem nunca aparece jogando. Não use a tecla dos pontinhos vazios no meio do teste — ela devolve o comando ao número e apaga o padrão torto. Pelo rádio há um risco extra: se o controle cair e voltar, o desenho torto se perde sem ninguém ter clicado; confira o chip dele na fita do topo antes de anotar. E o mapa diz que esta linha vem de UMA fonte só, sem confirmação independente, e que só o aparelho a fecha — o que você anotar vale mais que a página que a originou.

---

## mapa-luz.led_jogador.udev-cabo — LED de jogador — regra udev que o torna gravável sem sudo · cabo

*Célula:* `luz.led_jogador.udev @ cabo`

**O que isto prova.** Prova que, logo depois de encaixar o cabo, o Hefesto consegue mandar nas lâmpadas daquele controle sem pedir senha e sem recusar por falta de permissão.

**Onde olhar.** A tela não tem campo que mostre esta permissão, e a fonte não diz onde ela se leria: o exame da aba Sistema traz seis linhas e nenhuma delas é sobre esta regra. O que se lê é a CONSEQUÊNCIA, em dois lugares: a aba Iluminação, linha "LEDs" da coluna do controle, onde o clique obedece ou recusa dizendo — a frase de recusa nasce na própria coluna daquele controle e fica uns trinta segundos; e o aparelho, as cinco lâmpadas brancas abaixo do touchpad.

**Os passos.**

1. Feche o jogo, se houver algum aberto.
2. Confira que há um nome escrito em "Perfil ativo".
3. Desencaixe o cabo do P1.
4. Conte até cinco, devagar.
5. Encaixe o cabo de volta no P1.
6. Espere o chip do P1 reaparecer na fita do topo.
7. Abra a aba Iluminação.
8. Clique na tecla "P3" da linha "LEDs", na coluna do P1.
9. Confira que nada pediu senha e que nenhuma janela de autorização apareceu.
10. Olhe o aparelho do P1 e confira se o desenho mudou.
11. Leia a coluna do P1 nos trinta segundos seguintes e copie qualquer frase que apareça nela.
12. Repita os passos 3 a 11 no P2.
13. Clique na tecla dos cinco pontinhos vazios nas colunas do P1 e do P2, para desfazer.

**Passa quando.** Depois de religar pelo cabo, o clique na tecla de desenho obedece nos dois controles do cabo — sem pedir senha, sem janela de autorização e sem frase de recusa na coluna. Se aparecer uma frase, copie-a inteira: é ela que diz se o que faltou foi permissão ou outra coisa.

**Por controle.**

* **P1** — Cabo, e é ESTE. O gesto que importa é RELIGAR PELO CABO antes de clicar: a permissão é dada no instante em que o aparelho entra, não depois.
* **P2** — Cabo, e a segunda volta é o que separa "a máquina está sem a permissão" de "aquele aparelho entrou torto". Religue e clique nele também.
* **P3** — Rádio, testemunha. Não toque, e confira no fim que nenhuma lâmpada dele mudou.
* **P4** — Rádio, segunda testemunha. Não toque. Ele e o P3 juntos mostram que o religar de um cabo não mexeu em quem está no rádio.

**A armadilha.** Este é o teste mais fácil de dar falso VERDE da família, e o motivo está no mapa: a permissão libera UM caminho, e o caminho que move as lâmpadas do DualSense na prática é OUTRO. Então as lâmpadas obedecerem NÃO prova que a permissão está lá — prova só que alguma rota funcionou. O que este teste mede de verdade é o contrário: se alguma coisa pedir senha, ou recusar, a permissão é a primeira suspeita, e a frase copiada é a prova. Segunda: a permissão é concedida quando o aparelho ENTRA — clicar sem ter religado antes mede a permissão de ontem, e o teste não vale. Terceira: essa regra não é do aparelho, é do Linux, então não há nada a procurar no plástico nem no protocolo — quem for caçar um sinal no controle está caçando fantasma.

---

## mapa-luz.led_jogador.udev-radio — LED de jogador — regra udev que o torna gravável sem sudo · rádio

*Célula:* `luz.led_jogador.udev @ rádio`

**O que isto prova.** Prova que, logo depois de o controle voltar pelo rádio, o Hefesto consegue mandar nas lâmpadas dele sem pedir senha e sem recusar por falta de permissão.

**Onde olhar.** A tela não tem campo que mostre esta permissão, e a fonte não diz onde ela se leria: o exame da aba Sistema traz seis linhas e nenhuma é sobre esta regra. O que se lê é a consequência: a aba Iluminação, linha "LEDs" da coluna do controle — o clique obedece, ou recusa com uma frase que nasce na própria coluna e fica uns trinta segundos —, e o aparelho, as cinco lâmpadas brancas abaixo do touchpad. A fita do topo confirma que o chip termina em BT.

**Os passos.**

1. Feche o jogo, se houver algum aberto.
2. Confira na fita do topo que os chips do P3 e do P4 terminam em BT.
3. Confira que há um nome escrito em "Perfil ativo".
4. Segure o botão PS do P3 até todas as luzes dele apagarem, e solte.
5. Conte até cinco, devagar.
6. Dê um toque curto no botão PS do P3 para trazê-lo de volta.
7. Espere o chip do P3 reaparecer na fita do topo.
8. Abra a aba Iluminação.
9. Clique na tecla "P1" da linha "LEDs", na coluna do P3.
10. Confira que nada pediu senha e que nenhuma janela de autorização apareceu.
11. Olhe o aparelho do P3 e confira se o desenho mudou.
12. Leia a coluna do P3 nos trinta segundos seguintes e copie qualquer frase que apareça nela.
13. Repita os passos 4 a 12 no P4.
14. Clique na tecla dos cinco pontinhos vazios nas colunas do P3 e do P4, para desfazer.

**Passa quando.** Depois de o controle voltar pelo rádio, o clique na tecla de desenho obedece nos dois controles do rádio — sem senha, sem janela de autorização e sem frase de recusa na coluna. Se aparecer uma frase, copie-a inteira. E compare com o irmão do cabo: se o cabo obedecer e o rádio não, o achado é o transporte.

**Por controle.**

* **P1** — Cabo, testemunha e comparação. Não toque. Se este teste falhar e o do cabo tiver passado, o par de resultados é que diz onde está o problema.
* **P2** — Cabo, testemunha. Não toque, e confira no fim que nenhuma lâmpada dele mudou.
* **P3** — Rádio, e é ESTE. O gesto que importa é DESLIGAR E RELIGAR PELO PS antes de clicar: a permissão é dada no instante em que o aparelho entra.
* **P4** — Rádio, e a segunda volta separa "o rádio inteiro" de "aquele aparelho". Faça o mesmo desligar e religar nele.

**A armadilha.** O falso verde é o mesmo do irmão do cabo, e aqui é pior: o mapa desta casa tem DUAS respostas vivas sobre o que essa permissão sustenta no rádio — uma diz que sem ela sobra só um caminho, outra diz que pelo rádio o Hefesto continua escrevendo por outra rota. Logo, as lâmpadas obedecerem não prova que a permissão está lá, e as lâmpadas não obedecerem não diz qual das duas rotas falhou; o que este teste entrega é a observação, não o veredito. Segunda: soltar o PS cedo demais não desliga o controle, e aí você não religou nada — segure até TODAS as luzes apagarem. Terceira: o controle precisa já estar pareado nesta máquina, senão o toque no PS não o traz de volta. E essa regra é do Linux, não do aparelho: não há sinal nenhum a procurar no plástico.

---

## mapa-luz.led_microfone-cabo — LED do microfone (o botão de mudo iluminado) · cabo

*Célula:* `luz.led_microfone @ cabo`

**O que isto prova.** Prova que o Hefesto manda na luz vermelha do botão de microfone de um controle do cabo, e só daquele controle.

**Onde olhar.** No APARELHO: o botãozinho de mudo, logo abaixo do touchpad, com a luz vermelha dentro dele. Na tela: aba Controles, card do controle. Na linha "Microfone" há um selo ao lado do rótulo que diz ATIVO, MUDO ou "—" (o travessão quer dizer que não deu para ler, e não é nenhum dos dois); embaixo vem a barrinha de ondas do som entrando agora, e na fileira do volume um botão com desenho de microfone. Passe o mouse nesse botão ANTES de clicar: a dica diz o que o clique faz e o preço dele. Os cards abrem um de cada vez, mas o selo do Microfone dos outros continua legível na linha fechada de cada um.

**Os passos.**

1. Abra a aba Controles.
2. Anote o selo do Microfone dos quatro controles, lendo as linhas fechadas.
3. Vire os quatro aparelhos e anote se a luz vermelha do botãozinho de cada um está acesa ou apagada.
4. Clique na linha do P1 para abrir o card dele.
5. Passe o mouse pelo botão de microfone da fileira do volume e leia a dica.
6. Clique nesse botão de microfone, no card do P1.
7. Olhe a luz vermelha do botãozinho do P1 no plástico e anote o que ela fez.
8. Olhe as luzes vermelhas do P2, do P3 e do P4 e confirme que nenhuma delas mexeu.
9. Leia o selo do Microfone dos quatro e anote qual mudou.
10. Clique na linha do P2 para abrir o card dele.
11. Repita os passos 5 a 9 no P2.
12. Abra a aba Sistema e clique em "Reiniciar o serviço".
13. Aperte o botãozinho de microfone no plástico do P1 e confirme que a luz dele volta a responder ao aperto.

**Passa quando.** O clique na tela muda a luz vermelha do controle clicado, no plástico, e não mexe na luz dos outros três. O selo do Microfone daquele card acompanha. Os dois controles do cabo respondem do mesmo jeito. E depois de "Reiniciar o serviço" o botãozinho do plástico volta a valer.

**Por controle.**

* **P1** — Cabo, e é ESTE. Clique no botão de microfone DA TELA, dentro do card dele, e leia a luz vermelha do plástico.
* **P2** — Cabo, e a segunda volta é obrigatória: ela separa "o Hefesto manda na luz" de "o Hefesto manda na luz daquele aparelho".
* **P3** — Rádio, testemunha. Não abra o card dele e não clique em nada. A luz vermelha e o selo dele têm de ficar como estavam.
* **P4** — Rádio, segunda testemunha. Não toque. Se a luz de algum do rádio apagar junto, o comando pegou mais do que o controle escolhido.

**A armadilha.** O preço deste teste é real e está escrito na dica do botão: a partir do clique quem manda no mudo daquele controle é o Hefesto, e o botãozinho do plástico PARA DE VALER. Esta tela não devolve o comando — a volta é "Reiniciar o serviço", na aba Sistema, e é por isso que ela é um passo e não pode ser pulada. Segunda: não use o botãozinho do plástico como o gesto deste teste; ali quem cala é o Linux, e o teste passaria sem provar nada — esse é outro teste. Terceira: um selo em "—" não é ATIVO nem MUDO, quer dizer que não deu para ler; anote e não conte como passa. Quarta, e é a que mais engana: no aparelho essa luz tem QUATRO estados, não dois — apagada, acesa, piscando e piscando mais devagar. Se ela piscar, anote "piscando", nunca "acesa".

---

## mapa-luz.led_microfone-radio — LED do microfone (o botão de mudo iluminado) · rádio

*Célula:* `luz.led_microfone @ rádio`

**O que isto prova.** Prova que o Hefesto manda na luz vermelha do botão de microfone de um controle do rádio, e só daquele controle.

**Onde olhar.** No APARELHO: o botãozinho de mudo, logo abaixo do touchpad, com a luz vermelha dentro dele. Na tela: aba Controles, card do controle — a linha "Microfone" com o selo (ATIVO, MUDO ou "—"), a barrinha de ondas embaixo e, na fileira do volume, o botão com desenho de microfone, cuja dica diz o preço do clique. Os cards abrem um de cada vez, mas o selo dos outros continua legível na linha fechada. A fita do topo confirma que o chip do controle termina em BT.

**Os passos.**

1. Abra a aba Controles.
2. Confira na fita do topo que os chips do P3 e do P4 terminam em BT.
3. Anote o selo do Microfone dos quatro controles, lendo as linhas fechadas.
4. Vire os quatro aparelhos e anote se a luz vermelha do botãozinho de cada um está acesa ou apagada.
5. Clique na linha do P3 para abrir o card dele.
6. Passe o mouse pelo botão de microfone da fileira do volume e leia a dica.
7. Clique nesse botão de microfone, no card do P3.
8. Olhe a luz vermelha do botãozinho do P3 no plástico e anote o que ela fez.
9. Olhe as luzes vermelhas do P1, do P2 e do P4 e confirme que nenhuma delas mexeu.
10. Leia o selo do Microfone dos quatro e anote qual mudou.
11. Clique na linha do P4 para abrir o card dele.
12. Repita os passos 6 a 10 no P4.
13. Abra a aba Sistema e clique em "Reiniciar o serviço".
14. Aperte o botãozinho de microfone no plástico do P3 e confirme que a luz dele volta a responder ao aperto.

**Passa quando.** O clique na tela muda a luz vermelha do controle do rádio que foi clicado, no plástico, e não mexe na luz dos outros três. O selo do card acompanha. E a resposta é IGUAL à do cabo: se pelo cabo a luz apaga, pelo rádio também tem de apagar — foi assim que os quatro estados dessa luz foram medidos nos dois transportes.

**Por controle.**

* **P1** — Cabo, testemunha e comparação. Não toque. Se a luz dele responde no teste irmão e a do P3 não responde aqui, o achado é o transporte.
* **P2** — Cabo, segunda testemunha. Não toque. A luz vermelha e o selo dele têm de ficar como estavam.
* **P3** — Rádio, e é ESTE. Clique no botão de microfone DA TELA, dentro do card dele, e leia a luz vermelha do plástico.
* **P4** — Rádio, e a segunda volta é a que mais importa: ele está no mesmo tipo de conexão do P3. Se a luz do P4 apagar quando você clicou no P3, o comando pegou o rádio inteiro em vez do controle escolhido.

**A armadilha.** O preço é o mesmo do irmão do cabo, e é real: a partir do clique quem manda no mudo daquele controle é o Hefesto, e o botãozinho do plástico para de valer; a volta é "Reiniciar o serviço", na aba Sistema, e por isso ela é um passo obrigatório. Não use o botãozinho do plástico como gesto do teste — ali quem cala é o Linux. Um selo em "—" não é ATIVO nem MUDO e não conta como passa. A luz tem QUATRO estados no aparelho — apagada, acesa, piscando e piscando mais devagar —, então anote o que ela realmente fez, não o que você esperava. E o risco que só existe aqui: pelo rádio o mudo pode se desfazer sozinho quando o controle cai e volta, sem nada avisar; olhe o chip dele na fita do topo antes de concluir que a luz voltou por conta própria.

---

## mapa-luz.lightbar.aviso_de_modo-cabo — Lightbar — aviso de MODO (três piscadas na cor do modo novo) · cabo

*Célula:* `luz.lightbar.aviso_de_modo @ cabo`

**O que isto prova.** Prova que trocar de modo faz a barra de luz dos dois controles do cabo piscar três vezes na cor daquele modo, e devolver a cor de antes ao fim.

**Onde olhar.** Na aba Jogar do Hefesto, no quadro Modo, ficam os cartões que trocam o modo: Sony DualSense, Xbox, Steam Input, Navegação e Modo Nativo. Ali mesmo está escrito que, segurando PS + R3, você pula para o próximo sem largar o controle. Mas a resposta deste teste é toda no APARELHO: a barra de luz, as duas tiras dos lados do touchpad. As cores são estas: Steam Input pisca AZUL CLARO, Xbox pisca VERDE CLARO, Sony DualSense pisca ROSA, Navegação pisca ÂMBAR (um laranja claro) e Modo Nativo pisca BRANCO. Não há na tela campo nenhum que diga que a piscada saiu — o produto registra que MANDOU, não que acendeu. A fonte não diz onde se leria isso, e é por isso que o seu olho é a única prova que fecha esta linha.

**Os passos.**

1. Feche a Steam por inteiro antes de começar.
2. Abra o Hefesto e clique na aba Jogar.
3. Confira que a linha Status está em Ligado.
4. Leia o quadro Modo e anote qual cartão está aceso agora.
5. Ponha os quatro controles na mesa, virados para cima, onde você veja as quatro barras de uma vez.
6. Anote a cor da barra dos quatro.
7. Olhe para as quatro barras ANTES de clicar — não clique e depois procure.
8. Clique no cartão Xbox.
9. Conte as piscadas do P1 e do P2: têm de ser três, em VERDE CLARO.
10. Anote se as barras do P3 e do P4 piscaram também.
11. Olhe as quatro barras depois da piscada e confira que voltaram às cores que você anotou.
12. Clique no cartão Steam Input e conte as piscadas: três, em AZUL CLARO.
13. Clique no cartão Sony DualSense e conte as piscadas: três, em ROSA.
14. Clique de novo no MESMO cartão Sony DualSense e confira que agora NÃO houve piscada nenhuma.
15. Pegue o P1 na mão e segure PS + R3 até o modo pular para o próximo.
16. Confira que a piscada saiu igual por esse caminho, nas quatro barras.
17. Volte ao cartão que estava aceso quando você começou.

**Passa quando.** A cada troca de modo, a barra do P1 e a do P2 piscam TRÊS vezes na cor daquele modo e voltam sozinhas à cor que tinham antes. Clicar no modo que já está valendo não pisca nada. E a piscada sai igual pelas duas portas: pelo cartão na tela e pelo PS + R3 no controle.

**Por controle.**

* **P1** — No CABO, e é um dos dois desta célula. A piscada dele sai por um caminho e a dos do rádio sai por OUTRO — é por isso que os dois lados se contam separados. Ele também é o controle do gesto PS + R3.
* **P2** — No CABO, e é o outro desta célula. Tem de piscar junto com o P1, na mesma cor e no mesmo instante. Se o P1 piscar e o P2 não, o defeito é de um controle, não do transporte.
* **P3** — No RÁDIO, e AQUI A TESTEMUNHA NÃO FICA QUIETA: ela também tem de piscar. Foi pedido dela que o aviso saísse na barra de TODOS os controles ligados. Anote se ele piscou.
* **P4** — No RÁDIO, e mesma coisa. Se os dois do cabo piscarem e os dois do rádio ficarem mudos, ESSE é o defeito que este teste procura — e é o formato conhecido dele, porque os dois lados usam caminhos diferentes para acender.

**A armadilha.** Seis, e a primeira inverte o julgamento. (1) ESTE É O ÚNICO TESTE DESTA LEVA EM QUE OS QUATRO TÊM DE REAGIR. O aviso é para todos os controles de propósito — palavra dela: "o lightbar de todos pisca 3 vezes rápido". Reprovar porque os do rádio piscaram junto seria reprovar o produto certo. (2) A PISCADA INTEIRA DURA POUCO MAIS DE MEIO SEGUNDO: três acesas de cerca de um décimo cada. Olhe as quatro barras antes de clicar, com os controles já postos na mesa. Clicar e depois procurar já perdeu a piscada. (3) O MODO NATIVO É CASO À PARTE: ENTRAR nele ainda pisca branco, mas de dentro dele o dono da luz é o jogo e as piscadas seguintes não saem. Faça o teste com os outros modos. (4) LIGAR O HEFESTO NÃO PISCA — a primeira leitura do modo só memoriza, de propósito. (5) COM A STEAM ABERTA GANHA QUEM ESCREVE POR ÚLTIMO, e a piscada pode nunca aparecer. (6) SAIBA DE ONDE VEM ESTA LINHA: ela foi construída sem nenhum controle na mesa. O produto sabe dizer que mandou a piscada, e não sabe dizer que ela acendeu — não há leitura que desminta. O seu olho é a única coisa que fecha isto.

---

## mapa-luz.lightbar.aviso_de_modo-radio — Lightbar — aviso de MODO (três piscadas na cor do modo novo) · rádio

*Célula:* `luz.lightbar.aviso_de_modo @ rádio`

**O que isto prova.** Prova que trocar de modo faz a barra dos dois controles do rádio piscar três vezes na cor daquele modo — inclusive com a Steam aberta, que é a promessa deste lado.

**Onde olhar.** Na aba Jogar do Hefesto, no quadro Modo, ficam os cartões que trocam o modo: Sony DualSense, Xbox, Steam Input, Navegação e Modo Nativo. Ali está escrito que, segurando PS + R3, você pula para o próximo sem largar o controle. A resposta é toda no APARELHO: a barra de luz, as duas tiras dos lados do touchpad. As cores: Steam Input pisca AZUL CLARO, Xbox pisca VERDE CLARO, Sony DualSense pisca ROSA, Navegação pisca ÂMBAR (laranja claro) e Modo Nativo pisca BRANCO. Não há na tela campo nenhum que diga que a piscada saiu — o produto registra que MANDOU, não que acendeu. A fonte não diz onde se leria isso.

**Os passos.**

1. Feche a Steam por inteiro para a primeira volta.
2. Abra o Hefesto e clique na aba Jogar.
3. Confira que a linha Status está em Ligado.
4. Leia o quadro Modo e anote qual cartão está aceso agora.
5. Ponha os quatro controles na mesa, virados para cima, onde você veja as quatro barras de uma vez.
6. Anote a cor da barra dos quatro.
7. Olhe para as quatro barras ANTES de clicar.
8. Clique no cartão Xbox e conte as piscadas do P3 e do P4: têm de ser três, em VERDE CLARO.
9. Anote se as barras do P1 e do P2 piscaram também.
10. Confira que as quatro barras voltaram às cores que você anotou.
11. Clique no cartão Steam Input e conte as piscadas do P3 e do P4: três, em AZUL CLARO.
12. Abra a Steam agora, e espere ela terminar de abrir.
13. Volte ao Hefesto, à aba Jogar, e olhe de novo para as quatro barras.
14. Clique no cartão Sony DualSense e conte as piscadas do P3 e do P4: três, em ROSA — esta é a volta que decide.
15. Anote se o P1 e o P2 piscaram nesta segunda volta.
16. Feche a Steam.
17. Volte ao cartão que estava aceso quando você começou.

**Passa quando.** A cada troca de modo, a barra do P3 e a do P4 piscam TRÊS vezes na cor daquele modo e voltam sozinhas à cor de antes — nas DUAS voltas, com a Steam fechada e com a Steam aberta. A segunda volta é a que fecha o teste: é ela a promessa deste lado.

**Por controle.**

* **P1** — No CABO, e é TESTEMUNHA — mas aqui ela também tem de piscar, porque o aviso é para todos. Anote se ele piscou nas duas voltas. Se ele piscar com a Steam aberta e os do rádio não, isso separa os dois caminhos e é o achado.
* **P2** — No CABO, e é a segunda testemunha, com a mesma leitura do P1.
* **P3** — No RÁDIO, e é um dos dois desta célula. A piscada dele sai por um caminho próprio, feito justamente para pintar mesmo com outro programa segurando o controle — e esse caminho nunca foi visto acendendo durante uma piscada. É o que você vai ver.
* **P4** — No RÁDIO, e é o outro desta célula. Se os dois do cabo piscarem e os dois do rádio ficarem mudos, esse é o formato conhecido do defeito que este teste procura.

**A armadilha.** Sete. (1) OS QUATRO TÊM DE PISCAR, e isso é de propósito — palavra dela: "o lightbar de todos pisca 3 vezes rápido". Reprovar porque os do cabo piscaram junto seria reprovar o produto certo. (2) A PISCADA INTEIRA DURA POUCO MAIS DE MEIO SEGUNDO: olhe as quatro barras antes de clicar. (3) A VOLTA COM A STEAM ABERTA É A QUE IMPORTA AQUI. Com ela aberta, ganha quem escreve por último na barra — e o caminho do rádio existe exatamente para vencer isso. É a única prova desta célula que não se confunde com a do cabo. (4) UMA CONEXÃO DE RÁDIO PODE NASCER COM A BARRA TRAVADA, ignorando toda escrita, e nada avisa. Antes de reprovar, vá à aba Iluminação e pinte o P3 de amarelo: se nem a cor pegar, o que você mediu foi a barra travada, não o aviso — reinicie o Hefesto e refaça. (5) O MODO NATIVO É CASO À PARTE: entrar nele ainda pisca branco, mas de dentro dele as piscadas seguintes não saem. (6) LIGAR O HEFESTO NÃO PISCA. (7) SAIBA DE ONDE VEM ESTA LINHA: ela foi construída sem controle nenhum na mesa, e o produto não sabe dizer se a barra acendeu — só que mandou. O seu olho é a única coisa que fecha isto.

---

## mapa-luz.lightbar.brilho-cabo — Lightbar — brilho de hardware · cabo

*Célula:* `luz.lightbar.brilho @ cabo`

**O que isto prova.** Prova que o trilho Brilho escurece a barra dos controles do cabo apagando a própria cor — e que o brilho de três degraus que o aparelho tem por dentro nunca é comandado por ninguém.

**Onde olhar.** Na aba Iluminação do Hefesto, na linha Brilho de cada coluna: um trilho roxo com um puxador e, ao lado dele, o número em porcento (por exemplo 82%). Ao passar o mouse por cima, a dica diz que ao soltar a barra acende no brilho novo e o valor é gravado no perfil ativo, sem esperar o Salvar Perfil. A prova é a barra de luz no aparelho — as duas tiras dos lados do touchpad. Não existe em nenhuma das dez abas um ajuste de brilho de TRÊS degraus, e é justamente isso que este teste confere.

**Os passos.**

1. Abra o Hefesto e clique na aba Iluminação.
2. Confira que a etiqueta do P1 e a do P2 dizem cabo.
3. Leia o número em porcento da linha Brilho das QUATRO colunas e anote os quatro — você vai devolvê-los no fim.
4. Clique no quadradinho AMARELO da linha Cor, na coluna do P1, para ter uma cor forte de referência.
5. Arraste o puxador da linha Brilho da coluna do P1 pelas três paradas — o fim da direita em 100, mais ou menos a metade do trilho, e o fim da esquerda em 0 —, parando em cada uma para olhar a barra do aparelho.
6. Veja a barra do P1 em 100 e repare no quanto ela acende.
7. Confira que na metade do trilho ela fica visivelmente mais fraca e continua amarela.
8. Repare, no 0, se ela APAGOU por completo ou se ficou acesa fraquinha, e anote qual das duas.
9. Confira que as barras do P2, do P3 e do P4 não mudaram de brilho em nenhuma das três paradas.
10. Arraste o puxador do P1 de volta para 100.
11. Confira que a barra volta ao amarelo cheio.
12. Refaça os atos 1, 2 e 3 na coluna do P2, usando o quadradinho CIANO.
13. Passe pelas dez abas e procure um ajuste de brilho de luz com três degraus.
14. Confira que não existe nenhum.
15. Devolva os quatro números de brilho aos valores que você anotou no começo.

**Passa quando.** Nos dois controles do cabo a barra escurece junto com o número, some POR COMPLETO quando o trilho chega a 0 e volta ao cheio no 100 — e mexer no brilho de um nunca mexe no do outro nem no dos dois do rádio. E em nenhuma das dez abas existe um ajuste de brilho de luz com três degraus: o único brilho que o produto oferece é este trilho.

**Por controle.**

* **P1** — No CABO, e é um dos dois desta célula. Ponha amarelo, leve o trilho a 100, à metade e a 0, e depois de volta a 100. A barra tem de acompanhar os três valores.
* **P2** — No CABO, e é o outro desta célula. Mesmo caminho, com ciano. Enquanto você arrasta o do P2, olhe o P1: o brilho dele não pode mudar junto.
* **P3** — No RÁDIO, e é TESTEMUNHA. Não toque na coluna dele. Anote o número em porcento antes e depois: tem de ser o mesmo, e a barra dele não pode escurecer quando você arrasta um do cabo.
* **P4** — No RÁDIO, e é a segunda testemunha. Mesma conferência do P3.

**A armadilha.** O nome engana, e essa é a armadilha inteira. O aparelho tem um brilho PRÓPRIO, de três degraus, que se comanda por dentro — e o Hefesto NUNCA o comanda, nem no cabo nem no rádio; ninguém desta casa jamais mediu esse caminho. O que este trilho faz é outra grandeza: ele escurece a COR, multiplicando-a. É por isso que em 0 a barra apaga inteira em vez de ficar num brilho baixinho — e se ela ficar acesa fraquinha no 0, isso é o achado, porque quer dizer que alguém está mexendo em outra coisa. Quem lê a tela e a documentação pode concluir que são o mesmo controle; não são. Mais três coisas: os três degraus que EXISTEM no produto são da aba Vibração (Economia, Balanceado, Máximo) e são força de tremor, não luz — não conte como achado. Arrastar este trilho grava no perfil ativo NA HORA, sem você clicar em Salvar Perfil, então devolva os quatro números no fim ou o perfil dela fica com o brilho do teste. E se a coluna estiver com ressalva ("A Steam tem este controle aberto", "Em Nativo o jogo é dono do LED" ou "Lightbar: cor desconhecida"), o número vai para o disco mas a barra não muda agora — isso não é defeito do trilho.

---

## mapa-luz.lightbar.brilho-radio — Lightbar — brilho de hardware · rádio

*Célula:* `luz.lightbar.brilho @ rádio`

**O que isto prova.** Prova que o trilho Brilho escurece a barra dos controles do rádio apagando a própria cor — e que o brilho de três degraus que o aparelho tem por dentro nunca é comandado por ninguém.

**Onde olhar.** Na aba Iluminação do Hefesto, na linha Brilho de cada coluna: um trilho roxo com um puxador e, ao lado, o número em porcento (por exemplo 82%). A dica do trilho diz que ao soltar a barra acende no brilho novo e o valor é gravado no perfil ativo, sem esperar o Salvar Perfil. A prova é a barra de luz no aparelho — as duas tiras dos lados do touchpad. Não existe em nenhuma das dez abas um ajuste de brilho de TRÊS degraus, e é isso que este teste também confere.

**Os passos.**

1. Abra a aba Iluminação.
2. Confira que a etiqueta do P3 e a do P4 dizem rádio.
3. Leia o número em porcento da linha Brilho das QUATRO colunas e anote os quatro — você vai devolvê-los no fim.
4. Clique no quadradinho AMARELO da linha Cor, na coluna do P3.
5. Veja a barra de luz do P3 ficar amarela.
6. Arraste o puxador da linha Brilho da coluna do P3 até o fim da direita, em 100.
7. Repare no quanto a barra do P3 acende.
8. Arraste o mesmo puxador até mais ou menos a metade do trilho.
9. Veja a barra do P3 ficar visivelmente mais fraca, e continuar amarela.
10. Arraste o mesmo puxador até o fim da esquerda, em 0.
11. Veja se a barra do P3 APAGOU por completo ou ficou acesa fraquinha, e anote qual dos dois.
12. Confira que as barras do P1, do P2 e do P4 não mudaram de brilho.
13. Arraste o puxador do P3 de volta para 100.
14. Confira que a barra do P3 volta ao amarelo cheio.
15. Repita o mesmo caminho na coluna do P4, com o quadradinho CIANO: 100, metade, 0 e de volta a 100.
16. Passe pelas dez abas procurando um ajuste de brilho de luz com três degraus.
17. Confira que ele não existe em nenhuma delas.
18. Devolva os quatro números de brilho aos valores que você anotou no começo.

**Passa quando.** Nos dois controles do rádio a barra escurece junto com o número, some POR COMPLETO quando o trilho chega a 0 e volta ao cheio no 100 — e mexer no brilho de um nunca mexe no do outro nem no dos dois do cabo. E em nenhuma das dez abas existe um ajuste de brilho de luz com três degraus.

**Por controle.**

* **P1** — No CABO, e é TESTEMUNHA. Não toque na coluna dele. O brilho dele não pode mudar quando você arrasta um do rádio. Ele também é o controle de comparação: se o trilho não mexer nada no P3 nem no P4, arraste o do P1 — se a barra DELE responder, o defeito é do rádio; se nem ela responder, o defeito não é do transporte.
* **P2** — No CABO, e é a segunda testemunha. Não toque na coluna dele. Anote o número em porcento antes e depois: tem de ser o mesmo.
* **P3** — No RÁDIO, e é um dos dois desta célula. Ponha amarelo, leve o trilho a 100, à metade e a 0, e depois de volta a 100.
* **P4** — No RÁDIO, e é o outro desta célula. Mesmo caminho, com ciano. Enquanto você arrasta o do P4, olhe o P3: o brilho dele não pode mudar junto.

**A armadilha.** O nome engana, e essa é a armadilha inteira. O aparelho tem um brilho PRÓPRIO, de três degraus, e o Hefesto NUNCA o comanda — nem no cabo nem no rádio; ninguém desta casa mediu esse caminho. O que este trilho faz é escurecer a COR, multiplicando-a: por isso em 0 a barra apaga inteira em vez de ficar num brilho baixinho. Barra acesa fraquinha no 0 é o achado. Duas coisas que o rádio acrescenta: uma conexão de rádio pode nascer com a barra TRAVADA, ignorando toda escrita, e nada na tela avisa — se o P3 e o P4 não responderem a nada mas o P1 responder, o suspeito é esse, e o que já foi medido devolvendo a barra é reiniciar o Hefesto. E não conclua que a culpa é de ter reconectado: "reconectar cura" já foi concluído nesta casa antes e caiu depois. Mais: os três degraus que existem no produto são da aba Vibração e são força de tremor, não luz. E arrastar este trilho grava no perfil ativo NA HORA — devolva os quatro números no fim.

---

## mapa-luz.lightbar.cor-cabo — Lightbar — cor RGB · cabo

*Célula:* `luz.lightbar.cor @ cabo`

**O que isto prova.** Prova que a cor que você clica na coluna de um controle ligado por cabo acende de verdade na barra de luz dele, e só na dele.

**Onde olhar.** Na aba Iluminação do Hefesto. Cada controle tem uma coluna, com a etiqueta dele no alto (o número, a cor do plástico e a palavra cabo ou rádio). A coluna da esquerda nomeia as linhas: Controle, Modelo, Cor, Brilho, Jogador, LEDs e Opções. A linha Cor tem oito quadradinhos coloridos — um por número de jogador, nesta ordem: 1 azul, 2 vermelho, 3 verde, 4 rosa, 5 amarelo, 6 ciano, 7 laranja, 8 roxo — mais um nono, o livre, para uma cor fora dessas. Logo abaixo aparece o código da cor, do tipo #0000FF, e ele é clicável: clicar manda a mesma cor de novo. Mas a PROVA não é a tela: é a barra de luz no aparelho — as duas tiras que acendem dos dois lados do touchpad. A tela mostra a cor PEDIDA; embaixo do desenho da linha LEDs nasce uma linha de ressalva quando a luz não é do Hefesto, e ela diz qual das causas: "A Steam tem este controle aberto", "Em Nativo o jogo é dono do LED", "Lightbar: cor desconhecida" ou "Lightbar: apagada".

**Os passos.**

1. Feche a Steam por inteiro antes de começar.
2. Abra o Hefesto e clique na aba Iluminação.
3. Leia a etiqueta no alto das quatro colunas e confirme que a do P1 e a do P2 dizem cabo.
4. Ponha os quatro controles na mesa, virados para cima, de modo que você veja as quatro barras de uma vez.
5. Anote a cor da barra de luz de cada um dos quatro.
6. Clique no quadradinho AMARELO da linha Cor, na coluna do P1.
7. Olhe a barra do P1 no aparelho e confirme que ela ficou amarela.
8. Olhe as barras do P2, do P3 e do P4 e confirme que nenhuma mudou.
9. Clique no quadradinho CIANO da linha Cor, na coluna do P2.
10. Olhe a barra do P2 e confirme que ela ficou ciano.
11. Olhe a barra do P1 e confirme que ela continua amarela.
12. Olhe as barras do P3 e do P4 e confirme que continuam nas cores que você anotou.
13. Leia a linha embaixo do desenho nas colunas do P1 e do P2 e anote se apareceu alguma ressalva.
14. Clique no código de cor que está embaixo da linha Cor da coluna do P1.
15. Confira que a barra do P1 continua amarela depois desse reenvio.
16. Conte até sessenta, devagar, e olhe as barras do P1 e do P2 de novo.

**Passa quando.** As barras dos dois controles do cabo acenderam na cor que você clicou, no instante do clique, sem você recarregar nada — e continuaram nela um minuto depois. Pintar um nunca mudou a cor do outro, e as barras dos dois do rádio ficaram exatamente como estavam.

**Por controle.**

* **P1** — No CABO, e é um dos dois que têm de obedecer. Ponha AMARELO nele. A barra tem de acender amarela na hora e continuar amarela até o fim do teste.
* **P2** — No CABO, e é o outro que tem de obedecer. Ponha CIANO nele. No instante em que você o pintar, olhe o P1: ele não pode mudar.
* **P3** — No RÁDIO, e é TESTEMUNHA. Não toque na coluna dele. Se a barra dele mudar quando você pinta um do cabo, o comando pegou o transporte inteiro em vez do controle escolhido — e é isso que este teste procura.
* **P4** — No RÁDIO, e é a segunda testemunha. Não toque na coluna dele. Anote a cor da barra antes e depois; tem de ser a mesma nas duas vezes.

**A armadilha.** Três, e a primeira já enganou esta casa. (1) A TELA NÃO É A PROVA. O código de cor e o desenho mostram o que o Hefesto PEDIU, nunca o que está aceso — já foi medido ler o mesmo valor com a barra verde e com a barra apagada. Quem responde é o plástico. (2) USE UMA COR QUE NINGUÉM MAIS QUEIRA. Amarelo e ciano são as cores dos números 5 e 6, e não há nenhum P5 nem P6 na sua mesa — por isso ninguém mais as escreve. Pintar o P1 de azul é o pior teste possível, porque azul é justamente a cor que o produto dá ao número 1 sozinho: você não saberia quem pintou. Se a barra voltar sozinha à cor de antes em menos de um minuto, o que aconteceu foi o Hefesto reafirmando a cor DELE — anote, porque quer dizer que o seu clique não ficou gravado. (3) COM A STEAM ABERTA GANHA QUEM ESCREVE POR ÚLTIMO, e já foi medido a barra ficar APAGADA depois de cada comando nosso com ela aberta, e voltar a obedecer com ela fechada. Feche a Steam antes, e se aparecer a linha "A Steam tem este controle aberto", pare: o teste não mede nada nesse estado. As linhas "Em Nativo o jogo é dono do LED" e "Lightbar: cor desconhecida" valem o mesmo — o produto está avisando que a luz não é dele agora.

---

## mapa-luz.lightbar.cor-radio — Lightbar — cor RGB · rádio

*Célula:* `luz.lightbar.cor @ rádio`

**O que isto prova.** Prova que a cor que você clica na coluna de um controle ligado por rádio acende de verdade na barra de luz dele, e só na dele.

**Onde olhar.** Na aba Iluminação do Hefesto. Cada controle tem uma coluna, com a etiqueta dele no alto (o número, a cor do plástico e a palavra cabo ou rádio). A linha Cor tem oito quadradinhos — 1 azul, 2 vermelho, 3 verde, 4 rosa, 5 amarelo, 6 ciano, 7 laranja, 8 roxo — mais um nono, o livre. Embaixo deles fica o código da cor, do tipo #0000FF, que é clicável e reenvia a mesma cor. A prova é a barra de luz no aparelho: as duas tiras que acendem dos dois lados do touchpad. Embaixo do desenho da linha LEDs nasce uma linha de ressalva quando a luz não é do Hefesto — "A Steam tem este controle aberto", "Em Nativo o jogo é dono do LED", "Lightbar: cor desconhecida" ou "Lightbar: apagada".

**Os passos.**

1. Feche a Steam por inteiro antes de começar.
2. Abra o Hefesto e clique na aba Iluminação.
3. Leia a etiqueta no alto das quatro colunas e confirme que a do P3 e a do P4 dizem rádio.
4. Ponha os quatro controles na mesa, virados para cima, de modo que você veja as quatro barras de uma vez.
5. Anote a cor da barra de luz de cada um dos quatro.
6. Clique no quadradinho AMARELO da linha Cor, na coluna do P3.
7. Olhe a barra do P3 no aparelho e confirme que ela ficou amarela.
8. Olhe as barras do P1, do P2 e do P4 e confirme que nenhuma mudou.
9. Clique no quadradinho CIANO da linha Cor, na coluna do P4.
10. Olhe a barra do P4 e confirme que ela ficou ciano.
11. Olhe a barra do P3 e confirme que ela continua amarela.
12. Olhe as barras do P1 e do P2 e confirme que continuam nas cores que você anotou.
13. Leia a linha embaixo do desenho nas colunas do P3 e do P4 e anote se apareceu alguma ressalva.
14. Clique no código de cor embaixo da linha Cor da coluna do P3 e confira que a barra continua amarela.
15. Conte até sessenta, devagar, e olhe as barras do P3 e do P4 de novo.

**Passa quando.** As barras dos dois controles do rádio acenderam na cor que você clicou, no instante do clique, e continuaram nela um minuto depois. Pintar um nunca mudou a cor do outro, e as barras dos dois do cabo ficaram exatamente como estavam.

**Por controle.**

* **P1** — No CABO, e é TESTEMUNHA. Não toque na coluna dele. Se a barra dele mudar quando você pinta um do rádio, o comando pegou o transporte inteiro em vez do controle escolhido.
* **P2** — No CABO, e é a segunda testemunha. Não toque na coluna dele. Anote a cor antes e depois; tem de ser a mesma. Ele também serve de controle de comparação: se NADA obedecer no rádio, pinte o P2 de roxo e veja se ele obedece — se ele obedecer, o defeito é do rádio; se nem ele obedecer, o defeito não é do transporte.
* **P3** — No RÁDIO, e é um dos dois que têm de obedecer. Ponha AMARELO nele. É aqui que mora a metade que interessa: a cor tem de chegar igual à de quem está no cabo.
* **P4** — No RÁDIO, e é o outro que tem de obedecer. Ponha CIANO nele. Ele é o último a entrar na mesa e o primeiro a ficar mudo quando alguma coisa desmonta no rádio.

**A armadilha.** Quatro, e duas são só do rádio. (1) A TELA NÃO É A PROVA: o código de cor e o desenho mostram o que foi PEDIDO, nunca o que está aceso — já foi medido ler o mesmo valor com a barra verde e com a barra apagada. Quem responde é o plástico. (2) UMA CONEXÃO DE RÁDIO PODE NASCER COM A BARRA TRAVADA, ignorando toda escrita até alguém repintar, e o produto NÃO TEM COMO SABER disso — nada na tela avisa. Se o P3 e o P4 não obedecerem a nada e o P2 obedecer, o suspeito é este; o que já foi medido devolvendo a barra é reiniciar o Hefesto, não desligar o controle. Anote e refaça. (3) NÃO CONCLUA QUE A CULPA É DE TER RECONECTADO. "Reconectar cura" já foi concluído nesta casa antes e caiu depois — é falso positivo conhecido, e a palavra dela sobre isso vale mais que um ensaio solto. (4) USE UMA COR QUE NINGUÉM MAIS QUEIRA: amarelo e ciano são as cores dos números 5 e 6, e não há P5 nem P6 na mesa. Pintar o P3 de verde é o pior teste possível, porque verde é a cor que o produto dá ao número 3 sozinho.

---

## mapa-luz.lightbar.fade-cabo — Lightbar — fade in/out · cabo

*Célula:* `luz.lightbar.fade @ cabo`

**O que isto prova.** Prova que, nos controles do cabo, a barra de luz troca de cor e apaga em corte seco — o produto nunca pede o acender e o apagar suaves que o aparelho sabe fazer.

**Onde olhar.** A prova é a barra de luz no aparelho: as duas tiras dos lados do touchpad, nos dois controles do cabo. Ponha o controle que estiver medindo na mesa, de lado, e olhe a barra dele pelo canto do olho, nunca de frente — de frente o brilho fica na retina e inventa transição. Na tela, o que se usa é a aba Iluminação: a linha Cor de cada coluna (os oito quadradinhos, na ordem 1 azul, 2 vermelho, 3 verde, 4 rosa, 5 amarelo, 6 ciano, 7 laranja, 8 roxo) e a linha Opções, com os botões Automático e Desligar. Não existe em aba nenhuma um ajuste de acender ou apagar suave: a fonte não diz onde se leria isso, porque esse campo não existe no produto.

**Os passos.**

1. Abra a aba Iluminação.
2. Confira que a etiqueta do P1 e a do P2 dizem cabo.
3. Clique no quadradinho AMARELO da linha Cor, na coluna do P1.
4. Repare se a barra ACENDEU de uma vez ou se cresceu aos poucos, e anote.
5. Clique no quadradinho ROXO da mesma linha, na mesma coluna.
6. Repare se a cor velha sumiu de uma vez ou se foi desaparecendo, e anote.
7. Clique em Desligar, na linha Opções da coluna do P1.
8. Repare se a barra apagou de uma vez ou se foi sumindo devagar, e anote.
9. Clique de novo no quadradinho AMARELO da coluna do P1, para devolver a luz a ele.
10. Repita os atos 1 a 4 na coluna do P2.
11. Repita os atos 1 a 4 no P1 uma segunda vez, para descartar impressão sua.
12. Confira, enquanto mexe nos do cabo, que as barras do P3 e do P4 não acendem, não apagam nem mudam de cor.
13. Passe pelas dez abas e procure um ajuste de acender ou apagar suave.
14. Confira que ele não existe em aba nenhuma.
15. Devolva a cor dos dois ao que estava antes, ou clique em Automático na coluna de cada um.

**Passa quando.** Nos dois controles do cabo a barra acende, troca de cor e apaga em corte seco, sem transição nenhuma — nas duas voltas. E não existe em aba nenhuma do Hefesto um ajuste de acender ou apagar suave. Uma transição suave que se repita nas duas voltas é o ACHADO, porque hoje ninguém pede isso ao aparelho.

**Por controle.**

* **P1** — No CABO, e é um dos dois desta célula. Faça nele as três trocas — acender amarelo, virar roxo, e Desligar — olhando a barra de lado. Depois devolva a cor.
* **P2** — No CABO, e é o outro desta célula. Mesmos três gestos. Dois aparelhos iguais têm de se comportar igual: se um deles esmaecer e o outro cortar seco, o achado é grande e é do aparelho, não do produto.
* **P3** — No RÁDIO, e é TESTEMUNHA. Não toque na coluna dele. A barra dele não pode acender, apagar nem mudar de cor enquanto você mexe nos do cabo.
* **P4** — No RÁDIO, e é a segunda testemunha. Mesma conferência do P3.

**A armadilha.** Duas de julgamento e uma de perigo. (1) O SEU OLHO INVENTA TRANSIÇÃO. A troca é rápida e, olhando de frente, o brilho fica na retina e parece esmaecer. Olhe de lado, e faça duas vezes: só conta o que se repetir. (2) COM A STEAM ABERTA GANHA QUEM ESCREVE POR ÚLTIMO, e já foi medido a barra apagar sozinha depois de cada comando nosso com ela aberta — isso não é apagar suave, é outro escritor. Feche a Steam por inteiro antes de começar. (3) O PERIGO ESTÁ REGISTRADO, e é para quem for atrás disto depois: o aparelho SABE apagar suave, o comando existe no driver desta máquina, e ele já foi mandado ao vivo — NENHUM EFEITO. Quem partir daí escreve código que APAGA a barra achando que a acende. E fique sabendo de onde vem esta linha: ninguém pôs controle na mesa para medi-la; ela é leitura de código, e é por isso que ela está na sua fila.

---

## mapa-luz.lightbar.fade-radio — Lightbar — fade in/out · rádio

*Célula:* `luz.lightbar.fade @ rádio`

**O que isto prova.** Prova que, nos controles do rádio, a barra de luz troca de cor e apaga em corte seco — o produto nunca pede o acender e o apagar suaves que o aparelho sabe fazer.

**Onde olhar.** A prova é a barra de luz no aparelho: as duas tiras dos lados do touchpad, nos dois controles do rádio. Na tela, o que se usa é a aba Iluminação: a linha Cor de cada coluna (os oito quadradinhos, na ordem 1 azul, 2 vermelho, 3 verde, 4 rosa, 5 amarelo, 6 ciano, 7 laranja, 8 roxo) e a linha Opções, com os botões Automático e Desligar. Não existe em aba nenhuma um ajuste de acender ou apagar suave: a fonte não diz onde se leria isso, porque esse campo não existe no produto.

**Os passos.**

1. Feche a Steam por inteiro antes de começar.
2. Abra o Hefesto e clique na aba Iluminação.
3. Confirme que a etiqueta do P3 e a do P4 dizem rádio.
4. Clique no quadradinho AMARELO da linha Cor, na coluna do P3, e confirme que a barra dele obedeceu — sem isto o teste não roda.
5. Ponha o P3 na mesa, de lado, e olhe a barra dele pelo canto do olho, não de frente.
6. Clique no quadradinho ROXO da mesma linha, na mesma coluna.
7. Anote se a cor velha sumiu de uma vez ou se foi desaparecendo.
8. Clique em Desligar, na linha Opções da coluna do P3.
9. Anote se a barra apagou de uma vez ou se foi sumindo devagar.
10. Clique de novo no quadradinho AMARELO da coluna do P3 para devolver a luz a ele.
11. Anote se ela acendeu de uma vez ou se cresceu aos poucos.
12. Repita os passos 4 a 11 na coluna do P4.
13. Faça o teste do P3 uma segunda vez, para descartar impressão sua.
14. Devolva a cor dos dois ao que estava antes, ou clique em Automático na coluna de cada um.

**Passa quando.** Nos dois controles do rádio a barra acende, troca de cor e apaga em corte seco, sem transição nenhuma — nas duas voltas. Uma transição suave que se repita nas duas voltas é o ACHADO. Se a barra do P3 ou a do P4 não obedecer a nenhum dos cliques, o teste NÃO reprovou: ele não mediu fade nenhum, e você tem de refazê-lo depois de destravar a barra.

**Por controle.**

* **P1** — No CABO, e é TESTEMUNHA. Não toque na coluna dele. Ele também é o controle de comparação: se nada obedecer no rádio, faça os mesmos gestos nele — se a barra DELE cortar seco e a do rádio não obedecer a nada, o que você mediu foi a barra travada do rádio, não fade.
* **P2** — No CABO, e é a segunda testemunha. Não toque na coluna dele. A barra dele não pode mudar enquanto você mexe nos do rádio.
* **P3** — No RÁDIO, e é um dos dois desta célula. Só faça o teste nele DEPOIS de confirmar que ele obedece a uma cor — pelo rádio essa confirmação não é formalidade.
* **P4** — No RÁDIO, e é o outro desta célula. Mesmos gestos. Se um esmaecer e o outro cortar seco, o achado é do aparelho, não do produto.

**A armadilha.** Quatro. (1) O SEU OLHO INVENTA TRANSIÇÃO: olhe a barra de lado e faça duas vezes; só conta o que se repetir. (2) UMA CONEXÃO DE RÁDIO PODE NASCER COM A BARRA TRAVADA, ignorando toda escrita, sem nada na tela avisando. Nesse estado nada acende e você pode ler isso como "apagou suave até sumir" — por isso o passo 4 existe: primeiro prove que a barra obedece, e só então meça como ela obedece. O que já foi medido destravando é reiniciar o Hefesto. (3) COM A STEAM ABERTA GANHA QUEM ESCREVE POR ÚLTIMO, e a barra pode apagar sozinha depois do comando — isso não é fade. (4) O PERIGO REGISTRADO: o aparelho sabe apagar suave, o comando existe no driver desta máquina, e ele já foi mandado ao vivo sem NENHUM EFEITO. Quem partir daí escreve código que APAGA a barra achando que a acende. Esta linha nunca foi medida com controle na mesa — é leitura de código, e é por isso que ela está na sua fila.

---

## mapa-luz.lightbar.release_leds-cabo — Lightbar — devolver o claim (RELEASE_LEDS 0x08) · cabo

*Célula:* `luz.lightbar.release_leds @ cabo`

**O que isto prova.** Prova que o botão Automático de um controle do cabo devolve a luz ao jogo sem deixar a barra preta, e mede o preço já conhecido: as cinco lâmpadas de jogador apagam e não voltam sozinhas.

**Onde olhar.** Na aba Iluminação do Hefesto, na linha Opções de cada coluna, onde ficam dois botões: Automático (roxo) e Desligar (vermelho). No aparelho, duas coisas: a barra de luz — as duas tiras dos lados do touchpad — e as cinco lâmpadas brancas em fileira logo abaixo do touchpad. Depois do Automático a barra tem de ficar na cor do NÚMERO do controle: 1 azul, 2 vermelho, 3 verde, 4 rosa. Nada na tela conta o que aconteceu com as cinco lâmpadas — a fonte não diz onde se leria isso; quem responde por elas é o aparelho na sua mão.

**Os passos.**

1. Feche a Steam por inteiro antes de começar.
2. Abra o Hefesto e clique na aba Iluminação.
3. Confirme que a etiqueta do P1 e a do P2 dizem cabo.
4. Conte quais das cinco lâmpadas brancas estão acesas em CADA um dos quatro controles e anote os quatro desenhos.
5. Anote também a cor da barra dos quatro.
6. Clique no quadradinho AMARELO da linha Cor, na coluna do P1 — assim a barra fica numa cor que não é a do número dele.
7. Confirme que a barra do P1 ficou amarela.
8. Clique em Automático, na linha Opções da coluna do P1.
9. Olhe a barra do P1 no instante do clique: ela tem de sair do amarelo e ir para AZUL, que é a cor do número 1, sem passar por preto.
10. Conte de novo as cinco lâmpadas do P1 e anote o que mudou.
11. Conte as lâmpadas do P2, do P3 e do P4 e anote se alguma apagou junto.
12. Olhe as barras do P2, do P3 e do P4 e confira que nenhuma mudou de cor.
13. Clique no quadradinho CIANO da linha Cor, na coluna do P2, e confirme que a barra ficou ciano.
14. Clique em Automático na coluna do P2.
15. Olhe a barra do P2: ela tem de ir para VERMELHO, a cor do número 2, sem passar por preto.
16. Conte as lâmpadas dos quatro de novo e anote.

**Passa quando.** Nos dois controles do cabo o Automático troca a barra da cor que você pôs para a cor do número do controle, no instante do clique e sem passar por preto. E nenhum dos dois controles do rádio muda de cor por causa disso. O que acontecer com as cinco lâmpadas brancas é ACHADO a anotar, não motivo para reprovar.

**Por controle.**

* **P1** — No CABO, e é um dos dois desta célula. Ponha amarelo, clique em Automático, e confira que a barra vai para azul. Conte as cinco lâmpadas antes e depois.
* **P2** — No CABO, e é o outro. Ponha ciano, clique em Automático, e confira que a barra vai para vermelho. Conte as cinco lâmpadas antes e depois.
* **P3** — No RÁDIO, e é TESTEMUNHA — e aqui ela é o ponto do teste. Não toque na coluna dele. Se a barra dele mudar, ou se as cinco lâmpadas dele apagarem quando você clica no Automático de um do cabo, o comando saiu para o transporte inteiro em vez do controle escolhido. É exatamente isso que este teste procura.
* **P4** — No RÁDIO, e é a segunda testemunha. Mesma conferência do P3: barra e lâmpadas iguais antes e depois.

**A armadilha.** Quatro. (1) NÃO É O INTERRUPTOR DO ALTO DA ABA. "Cores automáticas por controle", na faixa do título, é do PERFIL e vale para os quatro de uma vez; o Automático de cada coluna é outra coisa — ele larga a luz DAQUELE controle para o jogo escolher. Não mexa no interruptor. (2) O COMANDO QUE ESTE BOTÃO MANDA EXISTE PARA O RÁDIO. No cabo não há luz "tomada" a devolver, e por isso a decisão da casa foi que aqui ele não se aplica. Só que o produto manda esse comando para TODOS os controles, sem olhar o transporte — quem foi conferir achou que a separação que o raciocínio pressupõe não existe no código. É por isso que este teste do cabo vale, e é isso que ele mede. (3) O PREÇO JÁ ESTÁ MEDIDO: esse comando APAGA as cinco lâmpadas de jogador, sempre, e elas NÃO voltam sozinhas. A fonte não diz qual gesto as acende de volta. Se apagarem, não é surpresa nem defeito novo — é o custo conhecido; anote e siga. (4) O botão também solta a trava que a luz tinha posto na troca automática de perfil. Se você acabou de mexer no gatilho de algum controle, a troca continua presa por causa DELE, e não por causa da luz — não leia isso como o Automático não ter funcionado.

---

## mapa-luz.lightbar.release_leds-radio — Lightbar — devolver o claim (RELEASE_LEDS 0x08) · rádio

*Célula:* `luz.lightbar.release_leds @ rádio`

**O que isto prova.** Prova que o botão Automático de um controle do rádio devolve mesmo a luz ao jogo — é aqui que existe a luz a devolver — sem deixar a barra preta, e mede o preço conhecido nas cinco lâmpadas de jogador.

**Onde olhar.** Na aba Iluminação do Hefesto, na linha Opções de cada coluna, onde ficam dois botões: Automático (roxo) e Desligar (vermelho). No aparelho, duas coisas: a barra de luz — as duas tiras dos lados do touchpad — e as cinco lâmpadas brancas em fileira logo abaixo do touchpad. Depois do Automático a barra tem de ficar na cor do NÚMERO do controle: 1 azul, 2 vermelho, 3 verde, 4 rosa. Nada na tela conta o que aconteceu com as cinco lâmpadas — a fonte não diz onde se leria isso; quem responde por elas é o aparelho na sua mão.

**Os passos.**

1. Feche a Steam por inteiro antes de começar.
2. Confira que o P3 e o P4 já estão ligados há mais de um minuto — não faça este teste com um controle que acabou de entrar no rádio.
3. Abra o Hefesto e clique na aba Iluminação.
4. Confirme que a etiqueta do P3 e a do P4 dizem rádio.
5. Conte quais das cinco lâmpadas brancas estão acesas em CADA um dos quatro controles e anote os quatro desenhos.
6. Anote também a cor da barra dos quatro.
7. Clique no quadradinho AMARELO da linha Cor, na coluna do P3, e confirme que a barra dele ficou amarela.
8. Clique em Automático, na linha Opções da coluna do P3.
9. Olhe a barra do P3 no instante do clique: ela tem de sair do amarelo e ir para VERDE, que é a cor do número 3, sem passar por preto e sem ficar apagada.
10. Conte de novo as cinco lâmpadas do P3 e anote o que mudou.
11. Conte as lâmpadas do P1, do P2 e do P4 e anote se alguma apagou junto.
12. Olhe as barras do P1, do P2 e do P4 e confira que nenhuma mudou de cor.
13. Clique no quadradinho CIANO da linha Cor, na coluna do P4, e confirme que a barra ficou ciano.
14. Clique em Automático na coluna do P4.
15. Olhe a barra do P4: ela tem de ir para ROSA, a cor do número 4, sem passar por preto.
16. Conte as lâmpadas dos quatro de novo e anote.

**Passa quando.** Nos dois controles do rádio o Automático troca a barra da cor que você pôs para a cor do número do controle, no instante do clique, sem passar por preto e sem a barra ficar apagada depois. E nenhum dos dois do cabo muda de cor por causa disso. O que acontecer com as cinco lâmpadas brancas é ACHADO a anotar, não motivo para reprovar.

**Por controle.**

* **P1** — No CABO, e é TESTEMUNHA. Não toque na coluna dele. Barra e cinco lâmpadas iguais antes e depois. Se as lâmpadas DELE apagarem quando você clica no Automático de um do rádio, o comando pegou o transporte inteiro.
* **P2** — No CABO, e é a segunda testemunha. Mesma conferência do P1.
* **P3** — No RÁDIO, e é um dos dois desta célula — e é aqui que o botão faz o que ele promete, porque é no rádio que existe luz a devolver. Ponha amarelo, clique em Automático, e confira que a barra vai para verde.
* **P4** — No RÁDIO, e é o outro. Ponha ciano, clique em Automático, e confira que a barra vai para rosa. Conte as cinco lâmpadas dele com atenção: é o último da fila e costuma ser o primeiro a ficar às escuras.

**A armadilha.** Cinco, e a segunda muda a hora do teste. (1) NÃO É O INTERRUPTOR DO ALTO DA ABA: "Cores automáticas por controle" é do perfil e vale para os quatro; o Automático da coluna larga a luz daquele controle para o jogo. Não mexa no interruptor. (2) NÃO CLIQUE NOS PRIMEIROS SEGUNDOS DEPOIS DE O CONTROLE ENTRAR NO RÁDIO. Há suspeita medida de que, mandado dentro de uns três segundos e meio da conexão, esse comando TRAVA a barra em vez de devolvê-la — e fora dessa janela ele não travou. Deixe o controle assentar antes. (3) O PREÇO JÁ ESTÁ MEDIDO: o comando APAGA as cinco lâmpadas de jogador, sempre, e elas NÃO voltam sozinhas. A fonte não diz qual gesto as acende de volta — anote e siga. (4) BARRA APAGADA DEPOIS DO CLIQUE É DEFEITO, e é o que o produto prometeu não fazer: largar a luz sozinho deixaria a última cor no plástico, e se a última tivesse sido um Desligar ela ficaria preta; por isso o gesto larga E pinta a cor do número. Preto aqui reprova. (5) O botão também solta a trava que a luz tinha posto na troca automática de perfil; se você acabou de mexer no gatilho de algum controle, a troca continua presa por causa DELE.

---

## mapa-luz.recursos_proprios-cabo — Recursos próprios do fabricante (turbo, LEDs de modo) · cabo

*Célula:* `luz.recursos_proprios @ cabo`

**O que isto prova.** Prova que os controles do cabo não têm turbo nem lâmpada de modo, e que o Hefesto não inventa nenhum dos dois: as luzes do aparelho são três, e só três.

**Onde olhar.** No APARELHO, com o P1 e o P2 na mão: as três luzes são a barra de luz (as duas tiras dos lados do touchpad), a fileira de cinco lâmpadas brancas logo abaixo do touchpad, e a luz vermelha dentro do botão de microfone (o botãozinho de mudo, abaixo do touchpad). Na TELA, a aba Iluminação: a coluna da esquerda nomeia as sete linhas de cada controle — Controle, Modelo, Cor, Brilho, Jogador, LEDs e Opções. Nenhuma delas fala em turbo nem em lâmpada de modo, e é isso que se confere.

**Os passos.**

1. Pegue o P1 na mão, vire-o para cima e diminua a luz do ambiente.
2. Aponte cada luz que você vê acender no plástico e conte quantas são.
3. Confirme que são três: a barra dos dois lados do touchpad, a fileira de cinco lâmpadas brancas embaixo dele e a luz do botão de microfone.
4. Vire o P1 de cabeça para baixo, olhe os ombros, o fundo e os punhos, e anote se achou qualquer outra luz.
5. Procure no P1 um botão de turbo e anote que não existe.
6. Aperte o botão do microfone do P1 e confirme que a luz vermelha dele responde.
7. Repita os passos 1 a 6 no P2.
8. Abra o Hefesto e clique na aba Iluminação.
9. Leia os nomes das sete linhas na coluna da esquerda, de cima para baixo, e anote os sete.
10. Confirme que nenhum deles fala em turbo nem em lâmpada de modo.
11. Passe pelas outras nove abas e procure em cada uma a palavra turbo.
12. Anote quantas luzes você contou em cada um dos quatro controles.

**Passa quando.** Os dois controles do cabo têm exatamente três luzes, e nenhuma outra; nenhum deles tem botão de turbo; e a palavra turbo não aparece em aba nenhuma do Hefesto. Achar uma quarta luz no plástico, ou um ajuste de turbo na tela, é o ACHADO — o mapa diz que nenhum dos dois existe neste aparelho.

**Por controle.**

* **P1** — No CABO, e é um dos dois desta célula. Conte as luzes na mão e procure o turbo. Está no cabo, que é onde tudo o que o Hefesto sabe fazer funciona: se um recurso próprio fosse aparecer em algum lugar, apareceria aqui.
* **P2** — No CABO, e é o outro — e ele é a segunda opinião. Dois aparelhos iguais têm de ter o mesmo conjunto de luzes. Se um tiver uma luz que o outro não tem, o achado é do aparelho, não do produto.
* **P3** — No RÁDIO, e é TESTEMUNHA. Não precisa mexer nele; só conte as luzes dele e confirme que são as mesmas três.
* **P4** — No RÁDIO, e é a segunda testemunha. Mesma contagem.

**A armadilha.** Esta linha junta DUAS perguntas com respostas opostas, e é por isso que ela é a mais fácil de julgar errado. Turbo e lâmpada de modo NÃO EXISTEM neste aparelho — não é o Hefesto que deixou de fazer; não há o que fazer. Mas existe no DualSense um canal próprio de luz, do lado do fabricante, que ninguém desta casa jamais tocou: ele não tem botão, não tem tela e não se prova com a mão. ESTE TESTE RESPONDE A PRIMEIRA METADE E NÃO ALCANÇA A SEGUNDA — e é honesto dizer isso, porque um verde aqui não quer dizer que não há nada escondido. Mais três: os três degraus da aba Vibração (Economia, Balanceado, Máximo) são força de tremor, não luz de modo — não conte como achado. A luz do botão de microfone tem lugar próprio no mapa e não é recurso proprietário; ela está aqui só para você fechar a conta das três. E o resultado bom deste teste não entrega capacidade nenhuma: ele diz "não há o que acionar", e isso é uma resposta, não uma falta.

---

## mapa-luz.recursos_proprios-radio — Recursos próprios do fabricante (turbo, LEDs de modo) · rádio

*Célula:* `luz.recursos_proprios @ rádio`

**O que isto prova.** Prova que os controles do rádio não têm turbo nem lâmpada de modo, e que trocar de fio não faz aparecer nenhuma luz que o cabo não tenha.

**Onde olhar.** No APARELHO, com o P3 e o P4 na mão: as três luzes são a barra de luz (as duas tiras dos lados do touchpad), a fileira de cinco lâmpadas brancas logo abaixo do touchpad, e a luz vermelha dentro do botão de microfone. Na TELA, a aba Iluminação: a coluna da esquerda nomeia as sete linhas de cada controle — Controle, Modelo, Cor, Brilho, Jogador, LEDs e Opções — e nenhuma delas fala em turbo nem em lâmpada de modo.

**Os passos.**

1. Pegue o P3 na mão, vire-o para cima e diminua a luz do ambiente.
2. Aponte cada luz que você vê acender no plástico e conte quantas são.
3. Confirme que são três: a barra dos dois lados do touchpad, a fileira de cinco lâmpadas brancas embaixo dele e a luz do botão de microfone.
4. Vire o P3 de cabeça para baixo, olhe os ombros, o fundo e os punhos, e anote se achou qualquer outra luz.
5. Procure no P3 um botão de turbo e anote que não existe.
6. Aperte o botão do microfone do P3 e confirme que a luz vermelha dele responde.
7. Repita os passos 1 a 6 no P4.
8. Ponha o P3 e o P1 lado a lado na mesa e compare luz por luz.
9. Anote qualquer luz que um tenha e o outro não.
10. Abra o Hefesto e clique na aba Iluminação.
11. Leia os nomes das sete linhas na coluna da esquerda e confirme que nenhum fala em turbo nem em lâmpada de modo.
12. Passe pelas outras nove abas e procure em cada uma a palavra turbo.

**Passa quando.** Os dois controles do rádio têm exatamente três luzes, e nenhuma outra; nenhum deles tem botão de turbo; e a palavra turbo não aparece em aba nenhuma do Hefesto. Um controle do rádio com uma luz que o do cabo não tem é ACHADO GRANDE, porque o aparelho anuncia o mesmo conjunto nos dois fios.

**Por controle.**

* **P1** — No CABO, e é TESTEMUNHA — e aqui ela tem trabalho: ponha o P1 ao lado do P3 e compare luz por luz. É essa comparação que responde se trocar de fio faz alguma coisa aparecer.
* **P2** — No CABO, e é a segunda testemunha. Conte as luzes dele para ter dois aparelhos de cabo na conta, e não um só.
* **P3** — No RÁDIO, e é um dos dois desta célula. Conte as luzes na mão e procure o turbo. A única diferença possível do rádio seria o aparelho anunciar um conjunto diferente — e a fonte diz que ele anuncia o MESMO nos dois fios.
* **P4** — No RÁDIO, e é o outro. Mesma contagem, e ele é a segunda opinião: se um dos dois do rádio tiver uma luz que o outro não tem, o achado é do aparelho.

**A armadilha.** Esta linha junta DUAS perguntas com respostas opostas. Turbo e lâmpada de modo NÃO EXISTEM neste aparelho — não é o Hefesto que deixou de fazer. Mas existe no DualSense um canal próprio de luz, do lado do fabricante, que ninguém desta casa jamais tocou, e ele é anunciado nos DOIS fios igualmente: não tem botão, não tem tela e não se prova com a mão. ESTE TESTE RESPONDE A PRIMEIRA METADE E NÃO ALCANÇA A SEGUNDA — um verde aqui não quer dizer que não há nada escondido. Mais três: os três degraus da aba Vibração são força de tremor, não luz de modo. A luz do botão de microfone tem lugar próprio no mapa e está aqui só para fechar a conta das três. E não conte a barra piscando vermelha quando a bateria acaba como uma luz nova: é a mesma barra fazendo outra coisa.

---

## mapa-luz.replica_output_jogo-cabo — Réplica do output do jogo (lightbar, LED de jogador, gatilho) · cabo

*Célula:* `luz.replica_output_jogo @ cabo`

**O que isto prova.** Prova que, quando o jogo pinta a luz do controle que ele enxerga, a barra do controle de verdade ligado por cabo acende igual.

**Onde olhar.** Na aba Jogar do Hefesto: a linha Status tem de estar em Ligado, e o quadro O Controle é visto como: é onde cada controle escolhe entre DualSense, Xbox 360 e Nintendo Pro — para o jogo poder pintar a luz, o controle tem de estar visto como DualSense, porque um Xbox 360 não tem barra de luz para o jogo pintar. Na aba Iluminação, a linha de ressalva que nasce embaixo do desenho de cada coluna quando a luz não é do Hefesto. A prova é a barra de luz no aparelho — as duas tiras dos lados do touchpad. A fonte não diz qual jogo pinta a barra de luz: escolha um que você saiba que pinta e anote o nome dele na sua resposta.

**Os passos.**

1. Clique na aba Jogar.
2. Confira que a linha Status está em Ligado.
3. Ache o quadro O Controle é visto como: e escolha DualSense no cartão do P1 e no do P2.
4. Abra a aba Iluminação.
5. Clique no quadradinho AMARELO da linha Cor, na coluna do P1 e na do P2.
6. Confira que as duas barras ficaram amarelas — este é o ponto de partida, numa cor que jogo nenhum pediria.
7. Leia a cor das barras do P3 e do P4 e anote as duas.
8. Abra o jogo que você escolheu e deixe-o carregar.
9. Entre na partida SÓ com o P1, deixando os outros três fora.
10. Confira que a barra do P1 deixou de ser amarela e passou à cor que o jogo pediu.
11. Confira que as barras do P2, do P3 e do P4 continuam como estavam.
12. Entre na partida com o P2 também.
13. Confira que a barra do P2 mudou.
14. Confira que as barras do P3 e do P4 continuam nas cores que você anotou.
15. Volte ao Hefesto com Alt+Tab.
16. Leia a linha de ressalva que nasce embaixo do desenho das colunas do P1 e do P2, na aba Iluminação.
17. Leia o nome do jogo e a cor que ele pôs em cada um, e anote os dois na sua resposta.

**Passa quando.** Nos dois controles do cabo a barra troca do amarelo para a cor que o jogo mandou, sozinha, sem você tocar em nada no Hefesto. E os dois controles do rádio, que ficaram fora da partida, não mudam de cor por causa disso.

**Por controle.**

* **P1** — No CABO, e é um dos dois desta célula. Ponha amarelo, entre na partida só com ele e veja a barra virar a cor do jogo.
* **P2** — No CABO, e é o outro. Ponha amarelo, entre na partida depois do P1 e veja a barra dele virar. Se o P1 virar e o P2 não, o defeito é do segundo lugar na fila, não do transporte.
* **P3** — No RÁDIO, e é TESTEMUNHA. Fica ligado e FORA da partida. Se a barra dele mudar de cor sem ele ter entrado, a cópia está indo para quem não pediu.
* **P4** — No RÁDIO, e é a segunda testemunha. Também fica fora da partida, com a mesma leitura.

**A espera.** O jogo leva minutos para chegar ao menu, e nenhum deles é para ficar olhando. Deixe-o carregando e vá fazer outra coisa; volte quando ouvir o som do menu. Nada se desfaz por você ter saído da frente: a cor amarela que você pôs continua nas duas barras até o jogo pintar por cima. Ao voltar, o primeiro lugar a olhar é a barra do P1, antes de entrar na partida — se ela já deixou de ser amarela sem ninguém ter entrado no jogo, isso é achado e vale anotar a hora.

**A armadilha.** Cinco, e três delas acendem a barra sem provar nada. (1) MÁSCARA ERRADA MATA O TESTE SEM HAVER DEFEITO: com o controle visto como Xbox 360, não existe barra de luz do lado que o jogo enxerga, e não há o que copiar. Confira o quadro O Controle é visto como: antes de começar. (2) NO MODO NATIVO TAMBÉM NÃO HÁ O QUE COPIAR: ali o jogo fala direto com o controle, e a luz que acende é do jogo, não uma cópia. A coluna diz isso com a frase "Em Nativo o jogo é dono do LED". Os dois casos acendem a barra e nenhum deles prova o que este teste quer. (3) A STEAM ESCREVE NA BARRA POR CONTA PRÓPRIA e ganha quem escreve por último: com ela aberta, uma cor que apareceu pode não ser do jogo — feche a Steam por inteiro antes de começar. (4) A COR DE PARTIDA TEM DE SER UMA QUE NENHUM JOGO PEDIRIA. Se você deixar a barra na cor do número e o jogo pedir a mesma, você não sabe quem pintou — por isso amarelo. (5) A fonte não diz qual jogo pinta a barra. Se o jogo escolhido nunca pintar, o resultado NÃO é vermelho: é "não mediu". Troque de jogo e anote qual você usou.

---

## mapa-luz.replica_output_jogo-radio — Réplica do output do jogo (lightbar, LED de jogador, gatilho) · rádio

*Célula:* `luz.replica_output_jogo @ rádio`

**O que isto prova.** Prova que, quando o jogo pinta a luz do controle que ele enxerga, a barra do controle de verdade ligado por rádio acende igual — e que o gatilho pedido pelo jogo também chega até ele.

**Onde olhar.** Na aba Jogar do Hefesto: a linha Status tem de estar em Ligado, e o quadro O Controle é visto como: é onde cada controle escolhe entre DualSense, Xbox 360 e Nintendo Pro — para o jogo poder pintar a luz, o controle tem de estar visto como DualSense, porque um Xbox 360 não tem barra de luz para o jogo pintar. Na aba Iluminação, a linha de ressalva embaixo do desenho de cada coluna, que nasce quando a luz não é do Hefesto. A prova é o aparelho: a barra de luz (as duas tiras dos lados do touchpad) e a resistência que a sua mão sente no L2 e no R2. A fonte não diz qual jogo pinta a barra de luz: escolha um que você saiba que pinta e anote o nome dele.

**Os passos.**

1. Abra a aba Jogar.
2. Confira que a linha Status está em Ligado.
3. Escolha DualSense no quadro O Controle é visto como:, no cartão do P3 e no do P4.
4. Abra a aba Iluminação.
5. Repare na cor da barra de luz do P1 e do P2 e escreva as duas.
6. Aperte o L2 e o R2 do P3 e do P4 até o fundo e guarde na mão como eles estão agora, antes de o jogo abrir.
7. Clique no quadradinho AMARELO da linha Cor, na coluna do P3 e depois na do P4.
8. Confira que as duas barras ficaram amarelas.
9. Abra o jogo que você escolheu.
10. Entre na partida SÓ com o P3, deixando os outros três fora.
11. Veja a barra do P3 assim que o jogo pintar: ela tem de deixar de ser amarela e passar à cor que o jogo pediu.
12. Aperte o L2 e o R2 do P3 até o fundo, com ele na mão, ainda dentro do jogo.
13. Compare essa resistência com a que você guardou na mão antes de abrir o jogo, e escreva se mudou.
14. Confira que as barras do P1, do P2 e do P4 continuam como estavam.
15. Entre na partida com o P4 também.
16. Veja a barra do P4 trocar de cor.
17. Compare as barras do P1 e do P2 com as cores que você escreveu no começo: continuam iguais.
18. Leia a linha de ressalva embaixo do desenho das colunas do P3 e do P4, voltando ao Hefesto com Alt+Tab.
19. Repare, para escrever no fim, no nome do jogo, na cor que ele pôs em cada um e no que a sua mão sentiu no gatilho.

**Passa quando.** Nos dois controles do rádio a barra troca do amarelo para a cor que o jogo mandou, sozinha, sem você tocar em nada no Hefesto — e os dois do cabo, que ficaram fora da partida, não mudam de cor. A resistência do L2 e do R2 dentro do jogo é achado a anotar: se a luz chegar e o gatilho não, isso é exatamente a metade que o mapa ainda dá como incompleta neste lado.

**Por controle.**

* **P1** — No CABO, e é TESTEMUNHA — e é também o controle de comparação. Fica FORA da partida. Se a barra do P3 e a do P4 não mudarem, entre na partida com o P1: se a dele mudar, o defeito é do rádio; se nem a dele mudar, o jogo não está pintando e o teste não mediu nada.
* **P2** — No CABO, e é a segunda testemunha. Fica fora da partida, e a barra dele não pode mudar de cor.
* **P3** — No RÁDIO, e é um dos dois desta célula. Ponha amarelo, entre na partida só com ele, veja a barra virar a cor do jogo e aperte o L2 e o R2 para sentir o gatilho.
* **P4** — No RÁDIO, e é o outro. Ponha amarelo, entre na partida depois do P3 e veja a barra dele virar. É o último da fila e o primeiro a ficar de fora quando alguma coisa não alcança o rádio.

**A espera.** O jogo leva minutos para chegar ao menu, e nenhum deles é para ficar olhando. Deixe-o carregando e vá fazer outra coisa; volte quando ouvir o som do menu. Nada se desfaz por você ter saído da frente: o amarelo que você pôs continua nas duas barras até o jogo pintar por cima. Ao voltar, olhe primeiro as barras do P3 e do P4 ANTES de entrar na partida — se alguma já deixou de ser amarela sem ninguém ter entrado, isso é achado e vale anotar a hora.

**A armadilha.** Seis. (1) MÁSCARA ERRADA MATA O TESTE SEM HAVER DEFEITO: com o controle visto como Xbox 360 não existe barra de luz do lado que o jogo enxerga, e não há o que copiar. (2) NO MODO NATIVO TAMBÉM NÃO HÁ O QUE COPIAR: ali o jogo fala direto com o controle e a luz que acende é do jogo, não uma cópia — a coluna diz isso com a frase "Em Nativo o jogo é dono do LED". Os dois casos acendem a barra e nenhum prova o que este teste quer. (3) UMA CONEXÃO DE RÁDIO PODE NASCER COM A BARRA TRAVADA, ignorando toda escrita, sem nada avisando: por isso o passo do quadradinho amarelo existe: se nem o amarelo pegar, você não tem ponto de partida e o teste não roda — reinicie o Hefesto e refaça. (4) A STEAM ESCREVE NA BARRA POR CONTA PRÓPRIA e ganha quem escreve por último; por isso a bancada começa com a Steam fechada por inteiro, conferida na faixa do topo da página. (5) A COR DE PARTIDA TEM DE SER UMA QUE NENHUM JOGO PEDIRIA — por isso amarelo, e não a cor do número. (6) A fonte não diz qual jogo pinta a barra: se o jogo escolhido nunca pintar, o resultado não é vermelho, é "não mediu" — troque de jogo. E não some as duas metades: a luz e o gatilho vêm pelo mesmo caminho mas são medidas separadas, e este lado do mapa está registrado como incompleto justamente porque ninguém isolou o que falta.

---

## mapa-movimento.acelerometro-cabo — Acelerômetro — número para a interface · cabo

*Célula:* `movimento.acelerometro @ cabo`

**O que isto prova.** Prova que os dois controles do cabo mandam a inclinação em número para a tela, e que o número segue o controle que você inclinou — e só ele.

**Onde olhar.** Aba Controles. Na fita do topo, clique no chip Todos para abrir os quatro cards de uma vez. Dentro de cada card, na coluna da direita, há duas molduras uma embaixo da outra: Giroscópio em cima e Acelerômetro embaixo. É a de BAIXO que importa aqui. Ela tem três linhas — X, Y e Z —, cada uma com um número e uma barrinha colorida ao lado. O número é em g, com três casas: um controle deitado e parado dá um dos três perto de 1,000 e os outros dois perto de zero, porque 1 g é a gravidade. Um traço no lugar do número quer dizer que a leitura ainda não chegou — não quer dizer zero. O `?` ao lado do rótulo Giroscópio explica os dois blocos e avisa que ali nada se clica.

**Os passos.**

1. Confira que P1 e P2 estão no cabo e P3 e P4 no rádio, lendo a palavra no fim do nome de cada linha.
2. Deite os quatro controles na mesa, virados para cima, e tire as mãos de todos.
3. Abra a aba Controles.
4. Clique no chip Todos, na fita do topo.
5. Conte até três, devagar, com os cards já abertos.
6. Anote os três números do Acelerômetro de cada um dos quatro, na ordem X, Y, Z.
7. Confira que, nos quatro, um dos três está perto de 1,000 e os outros dois perto de zero.
8. Pegue só o P1 na mão e incline-o devagar para a esquerda, sem sacudir.
9. Olhe os três números do Acelerômetro do P1 enquanto inclina: eles têm de andar.
10. Olhe os números do P2, do P3 e do P4 no mesmo instante: nenhum pode andar.
11. Deite o P1 de volta na mesa e confira que os três voltam para perto do que você anotou.
12. Incline o P1 para a direita e confira que os números andam para o outro lado.
13. Repita os passos 8 a 12 com o P2, com os outros três largados na mesa.
14. Compare os números de repouso do P1 com os do P2: parecidos, mas não idênticos.

**Passa quando.** Nos dois do cabo — P1 e P2 —, os três números do Acelerômetro andam quando você inclina aquele controle, andam para o outro lado quando você inclina para o outro lado, e voltam para perto de onde estavam quando você o deita de novo. Com os quatro parados e deitados, cada um dá um dos três perto de 1,000 e os outros dois perto de zero. E inclinar um controle nunca mexe nos números de outro.

**Por controle.**

* **P1** — No cabo, e é o primeiro que TEM de reagir. Incline-o devagar para a esquerda e para a direita, com os outros três largados na mesa, e veja os três números andarem e voltarem. Deitado e parado, um dos três fica perto de 1,000.
* **P2** — No cabo, e é o segundo que TEM de reagir. Mesmos gestos do P1. Os números de repouso dele não podem ser IDÊNTICOS aos do P1: dois aparelhos diferentes, parados, dão números parecidos e nunca iguais casa a casa.
* **P3** — No rádio, e é TESTEMUNHA. Não encoste nele enquanto você inclina os do cabo. Se os números dele andarem junto com os do P1, a tela está mostrando a leitura de um controle dentro do card de outro.
* **P4** — No rádio, e é a SEGUNDA testemunha. Mesma regra do P3. Se o P3 ficou parado e o P4 andou junto com o P1, o problema não é do rádio — é alguma coisa escrevendo no card errado.

**A armadilha.** Três, e a primeira já enganou esta casa. (1) O DESENHO. Quando a tela para de ler de verdade, ela mostra os números do desenho, e eles são sempre os mesmos três no Acelerômetro: +0.105 · +0.976 · +0.170. Se os quatro cards mostrarem exatamente esses três, ou se dois controles em poses DIFERENTES mostrarem números idênticos, não houve leitura — e o teste não passou nem reprovou. (2) O PRIMEIRO OLHAR MEDE SEMPRE A AUSÊNCIA. O leitor de sensores nasce só quando alguém pede e morre cinco segundos depois do último pedido; abrir o card e olhar no mesmo instante mostra traços em tudo. Deixe o card aberto e conte até três antes de acreditar no que está lá. (3) O TRAÇO NÃO É ZERO. Traço quer dizer que a leitura não chegou; anote como não medido, nunca como número baixo. E onde a prova parou: o mapa registra que este caminho foi MONTADO e conferido no código, e nada além disso — o degrau seguinte, que é ver o número sair do aparelho e chegar íntegro à tela, é justamente o que a sua mão faz aqui. Não julgue esta linha pelo que um jogo faz com a inclinação: isso é outra linha.

---

## mapa-movimento.acelerometro-radio — Acelerômetro — número para a interface · rádio

*Célula:* `movimento.acelerometro @ rádio`

**O que isto prova.** Prova que os dois controles do rádio mandam a inclinação em número para a tela, igual aos do cabo, e que o número fica no card do controle certo.

**Onde olhar.** Aba Controles. Na fita do topo, clique no chip Todos para abrir os quatro cards. Em cada card, coluna da direita, a moldura de BAIXO é o Acelerômetro, com as três linhas X, Y e Z — número em g com três casas e uma barrinha colorida ao lado. Deitado e parado, um dos três dá perto de 1,000 e os outros dois perto de zero. Traço no lugar do número quer dizer que a leitura ainda não chegou. Confira também a palavra no fim do nome de cada linha, que diz cabo ou rádio: é ela que separa quem tem de reagir de quem é testemunha.

**Os passos.**

1. Confira que P3 e P4 estão no rádio, sem nenhum cabo plugado neles.
2. Deite os quatro controles na mesa, virados para cima, e tire as mãos de todos.
3. Abra a aba Controles.
4. Clique no chip Todos, na fita do topo.
5. Conte até três, devagar, com os cards já abertos.
6. Anote os três números do Acelerômetro dos quatro, na ordem X, Y, Z.
7. Confira que os cards do P3 e do P4 têm número, e não traço, nas três linhas.
8. Pegue só o P3 na mão e incline-o devagar para a esquerda, sem sacudir.
9. Olhe os três números do Acelerômetro do P3 enquanto inclina: eles têm de andar.
10. Olhe os números do P1, do P2 e do P4 no mesmo instante: nenhum pode andar.
11. Deite o P3 de volta na mesa e confira que os três voltam para perto do que você anotou.
12. Repita os passos 8 a 11 com o P4.
13. Compare os números de repouso do P3 com os do P4: parecidos, e não idênticos.
14. Compare o repouso dos dois do rádio com o dos dois do cabo: a qualidade do número tem de ser a mesma, sem casas a menos e sem traço.

**Passa quando.** Nos dois do rádio — P3 e P4 —, os três números do Acelerômetro andam quando você inclina aquele controle e voltam para perto do repouso quando você o deita. Os dois cards mostram NÚMERO, e não traço. Inclinar um nunca mexe nos números de outro. E o número que sai pelo rádio tem a mesma cara do que sai pelo cabo — parado, um eixo perto de 1,000.

**Por controle.**

* **P1** — No cabo, e é TESTEMUNHA. Não encoste nele. É ele quem prova que a tela está lendo de verdade: se o P1 mostra números vivos e o P3 mostra traço, o buraco é do rádio, não da tela.
* **P2** — No cabo, e é a SEGUNDA testemunha. Não encoste nele. Se os números do P2 andarem quando você inclina o P3, alguém está escrevendo no card errado.
* **P3** — No rádio, e é o primeiro que TEM de reagir. Incline-o devagar para os dois lados, com os outros três largados na mesa, e veja os três números andarem e voltarem.
* **P4** — No rádio, e é o segundo que TEM de reagir. Mesmos gestos do P3. Ele é o último a entrar na mesa e o mais propenso a nascer sem leitor — se algum dos quatro mostrar traço para sempre, é neste que costuma aparecer.

**A armadilha.** Quatro, e as duas primeiras são só do rádio. (1) OS CARDS QUE NÃO SÃO O PRINCIPAL ficaram cegos por muito tempo: até o começo de setembro o Hefesto só publicava leitura para UM controle, e os outros cards mostravam os números do desenho como se estivessem medindo. Isso foi curado; se voltar, o sinal é este — dois cards com os TRÊS números idênticos, casa por casa, com os aparelhos em poses diferentes. (2) COM O CO-OP LIGADO um controle pode legitimamente não ter leitura no card: quando o co-op segura o sensor daquele aparelho para si, o card não recebe número, e isso é desenho do produto, não defeito. Se o P3 ou o P4 der traço, confira o co-op antes de reprovar. (3) O PRIMEIRO OLHAR MEDE A AUSÊNCIA: o leitor nasce sob demanda e morre cinco segundos depois do último pedido — deixe o card aberto e conte até três. (4) O DESENHO tem números fixos no Acelerômetro (+0.105 · +0.976 · +0.170); vê-los nos quatro cards é sinal de que não houve leitura nenhuma. E onde a prova parou: o mapa registra o caminho MONTADO e conferido, com uma leitura pelo rádio medida em 03/09 que deu 0,9966 g de gravidade — o degrau seguinte é o que a sua mão confirma aqui. Não julgue esta linha pelo que um jogo faz.

---

## mapa-movimento.acelerometro.jogo-cabo — Acelerômetro — dado para o jogo · cabo

*Célula:* `movimento.acelerometro.jogo @ cabo`

**O que isto prova.** Prova que o interruptor Acelerômetro de um controle do cabo mira naquele controle e só naquele sensor — sem encostar no Giroscópio dele nem nos outros três.

**Onde olhar.** Aba Controles, na LINHA de cada controle — ela aparece com o card aberto ou fechado. No fim da linha há dois interruptores lado a lado, Giroscópio e Acelerômetro, cada um com uma bolinha que fica verde quando o sensor está ligado e cinza quando está desligado. Passar o mouse no Acelerômetro abre a dica: «Ligado: o jogo recebe a inclinação e o chacoalhar deste controle». Na mesma linha, mais à esquerda, há um texto que diz DualSense, ou Xbox 360, ou Nintendo Pro — é o que o jogo vê daquele controle, e a dica do mouse diz isso. Quando o produto recusa o clique, ou quando ele pega só pela metade, a frase aparece no cartão daquele controle e fica trinta segundos.

**Os passos.**

1. Abra a aba Controles.
2. Clique no chip Todos, na fita do topo.
3. Leia, na linha dos quatro, o texto que diz o que o jogo vê, e anote.
4. Confira que na linha do P1 e na do P2 ele diz DualSense — o formato de Xbox 360 não tem acelerômetro, e nele este teste não mede nada.
5. Anote a cor da bolinha dos OITO interruptores: Giroscópio e Acelerômetro das quatro linhas.
6. Clique no interruptor Acelerômetro da linha do P1.
7. Olhe a bolinha dele: tem de trocar de cor.
8. Olhe o interruptor Giroscópio da MESMA linha do P1: ele não pode ter mudado.
9. Olhe os dois interruptores das linhas do P2, do P3 e do P4: nenhum pode ter mudado.
10. Leia se apareceu alguma frase no cartão do P1 e anote-a por inteiro.
11. Clique no interruptor Acelerômetro do P1 de novo, para devolvê-lo ao que era.
12. Repita os passos 6 a 11 na linha do P2.
13. Confira, no fim, que os oito interruptores voltaram às cores que você anotou no passo 5.

**Passa quando.** O clique no Acelerômetro do P1 troca a cor da bolinha DELE e de mais nada: o Giroscópio da mesma linha continua como estava, e as linhas do P2, do P3 e do P4 não se mexem. O mesmo acontece no P2. Se aparecer frase no cartão, ela EXPLICA o que não pegou — e explicar é a resposta certa; o que reprova é a bolinha trocar de cor calada quando o comando não pegou. No fim, os oito interruptores voltam ao que estavam.

**Por controle.**

* **P1** — No cabo, e é o primeiro em que você clica. Só o Acelerômetro da linha dele, uma vez para desligar e uma vez para ligar. O Giroscópio da mesma linha é a testemunha mais importante deste teste: ele não pode mudar junto.
* **P2** — No cabo, e é o segundo em que você clica. Mesmo gesto do P1. Antes de clicar, olhe onde estão as oito bolinhas: o defeito que este teste caça é um clique numa linha mexer noutra, e ele só se enxerga se você souber o de antes.
* **P3** — No rádio, e é TESTEMUNHA. Não clique em nada na linha dele. As duas bolinhas têm de ficar exatamente na cor que estavam.
* **P4** — No rádio, e é a SEGUNDA testemunha. Não clique em nada na linha dele. Se o P3 ficou parado e o P4 mudou junto com o P1, o comando não pegou o transporte — pegou o controle errado.

**A armadilha.** Onde a prova parou, e ela parou cedo: o mapa registra que os bytes da inclinação são MONTADOS dentro da mesma janela que segue para o controle virtual, e nada além disso. Ninguém isolou a inclinação chegando a um jogo, em transporte nenhum. Então NÃO reprove esta linha porque um jogo não reagiu a você inclinar o controle: o jogo pode simplesmente não usar esse dado. O que se mede aqui é o interruptor acertar o controle certo e o sensor certo. Três coisas que parecem defeito e não são: se o que o jogo vê disser Xbox 360, esse formato NÃO TEM acelerômetro e o produto está certo em não entregar nada; se o interruptor RECUSAR o clique dizendo que ainda não sabe se o sensor está ligado ou desligado, isso é ele se negando a chutar qual é o oposto — anote e confira se o Hefesto está de pé; e se a frase falar em Modo Nativo, o jogo está falando direto com o controle e o Hefesto saiu do meio, o que também é o produto certo. E a armadilha do gesto: clicar nos dois interruptores da mesma linha de uma vez esconde exatamente o defeito que este teste procura, que é um clique mexer no sensor vizinho.

---

## mapa-movimento.acelerometro.jogo-radio — Acelerômetro — dado para o jogo · rádio

*Célula:* `movimento.acelerometro.jogo @ rádio`

**O que isto prova.** Prova que o interruptor Acelerômetro de um controle do rádio mira naquele controle e só naquele sensor, igual aos do cabo.

**Onde olhar.** Aba Controles, na LINHA de cada controle — aparece com o card aberto ou fechado. No fim da linha estão os dois interruptores lado a lado, Giroscópio e Acelerômetro, com uma bolinha verde quando ligado e cinza quando desligado. A dica do Acelerômetro diz: «Ligado: o jogo recebe a inclinação e o chacoalhar deste controle». Mais à esquerda, na mesma linha, o texto que diz DualSense, Xbox 360 ou Nintendo Pro é o que o jogo vê daquele controle. Recusa ou meia-obediência viram frase no cartão daquele controle, por trinta segundos.

**Os passos.**

1. Confira que P3 e P4 estão no rádio, sem cabo plugado.
2. Abra a aba Controles.
3. Clique no chip Todos, na fita do topo.
4. Leia o texto do que o jogo vê nas quatro linhas e confira que na do P3 e na do P4 diz DualSense.
5. Anote a cor das oito bolinhas: Giroscópio e Acelerômetro das quatro linhas.
6. Clique no interruptor Acelerômetro da linha do P3.
7. Olhe a bolinha dele: tem de trocar de cor.
8. Olhe o interruptor Giroscópio da MESMA linha do P3: ele não pode ter mudado.
9. Olhe os dois interruptores das linhas do P1, do P2 e do P4: nenhum pode ter mudado.
10. Leia se apareceu alguma frase no cartão do P3 e anote-a por inteiro.
11. Clique no Acelerômetro do P3 de novo, para devolvê-lo ao que era.
12. Repita os passos 6 a 11 na linha do P4.
13. Confira, no fim, que as oito bolinhas voltaram às cores do passo 5.

**Passa quando.** O clique no Acelerômetro do P3 troca a cor da bolinha DELE e de mais nada: o Giroscópio da mesma linha fica como estava, e as linhas do P1, do P2 e do P4 não se mexem. O mesmo acontece no P4. Se aparecer frase no cartão, ela explica o que não pegou — e explicar é a resposta certa; o que reprova é a bolinha trocar de cor calada quando o comando não pegou. No fim, tudo volta ao que era.

**Por controle.**

* **P1** — No cabo, e é TESTEMUNHA. Não clique em nada na linha dele. As duas bolinhas dele têm de ficar exatamente onde estavam.
* **P2** — No cabo, e é a SEGUNDA testemunha. Não clique em nada na linha dele. Se o P1 ficou parado e o P2 mudou junto com o P3, o comando acertou o controle errado — e não o transporte.
* **P3** — No rádio, e é o primeiro em que você clica. Só o Acelerômetro da linha dele, uma vez para desligar e uma vez para ligar. O Giroscópio da mesma linha não pode mudar junto.
* **P4** — No rádio, e é o segundo em que você clica. Mesmo gesto do P3. Antes de clicar, olhe onde estão as oito bolinhas: sem o de antes, este teste não mede nada.

**A armadilha.** Quatro, e a primeira é só do rádio. (1) O MICROFONE PODE CALAR A INCLINAÇÃO SEM AVISAR. Pelo rádio, o pacote que traz movimento e o que traz som do microfone são o MESMO pacote, e o Hefesto joga fora inteiro todo pacote que venha carregando áudio. Se o microfone daquele controle estiver sendo levado pelo rádio, a inclinação pode parar de seguir para o jogo — e isso é desenho, não erro seu. Anote o estado do microfone daquele controle antes de reprovar. (2) O PORTÃO DO RÁDIO É MAIS ESTREITO que o do cabo: o pacote só é aceito com tamanho exato e com o número de conferência batendo; um pacote embaralhado no ar é descartado em silêncio. (3) Se o que o jogo vê disser Xbox 360, esse formato NÃO TEM acelerômetro — o produto está certo. (4) Se o interruptor RECUSAR o clique dizendo que ainda não sabe o estado do sensor, ele está se negando a chutar; anote e confira se o Hefesto está de pé. E onde a prova parou: o mapa registra que os bytes são MONTADOS na janela que vai ao controle virtual, e diz com todas as letras que NINGUÉM isolou a inclinação chegando ao jogo pelo rádio. Não reprove esta linha porque um jogo não reagiu — reprove se o interruptor errar o alvo.

---

## mapa-movimento.giroscopio-cabo — Giroscópio — número para a interface · cabo

*Célula:* `movimento.giroscopio @ cabo`

**O que isto prova.** Prova que os dois controles do cabo mandam para a tela o quanto giram, e que parados eles NÃO dão zero — cada um tem o seu resto de fábrica.

**Onde olhar.** Aba Controles. Na fita do topo, clique no chip Todos para abrir os quatro cards. Em cada card, coluna da direita, a moldura de CIMA é o Giroscópio — três linhas, X, Y e Z, cada uma com um número em graus por segundo e uma barrinha colorida ao lado. O `?` ao lado do rótulo diz que aquilo é leitura viva do aparelho, dez vezes por segundo, e que ali nada se clica. Traço no lugar do número quer dizer que a leitura ainda não chegou.

**Os passos.**

1. Confira que P1 e P2 estão no cabo, lendo a palavra no fim do nome de cada linha.
2. Deite os quatro controles na mesa e tire as mãos de todos.
3. Abra a aba Controles.
4. Clique no chip Todos, na fita do topo.
5. Conte até três, devagar, com os cards já abertos.
6. Anote os três números do Giroscópio de cada um dos quatro.
7. Confira que os doze números são pequenos — nenhum passa de 2 — e que nenhum está exatamente em zero.
8. Pegue só o P1 e gire-o devagar sobre a mesa, como um volante, sem levantar.
9. Olhe os números do Giroscópio do P1 enquanto gira: um dos três tem de crescer bastante.
10. Olhe os números do P2, do P3 e do P4 no mesmo instante: nenhum pode crescer.
11. Pare de girar, deite o P1, e confira que os três voltam para perto do que você anotou.
12. Gire o P1 para o outro lado e confira que o número que crescia troca de sinal.
13. Repita os passos 8 a 12 com o P2, com os outros três largados na mesa.
14. Compare os números de repouso do P1 com os do P2: cada um tem o seu, e eles não são iguais.

**Passa quando.** Nos dois do cabo — P1 e P2 —, girar o controle faz um dos três números crescer bastante, girar para o outro lado troca o sinal dele, e parar devolve os três para perto do repouso. Parados, os doze números são pequenos e nenhum é exatamente zero. Girar um controle nunca mexe nos números de outro. E o repouso do P1 é diferente do repouso do P2.

**Por controle.**

* **P1** — No cabo, e é o primeiro que TEM de reagir. Gire-o devagar sobre a mesa para os dois lados, com os outros três largados. Parado, ele tem o seu próprio número de repouso, pequeno e diferente de zero.
* **P2** — No cabo, e é o segundo que TEM de reagir. Mesmos gestos do P1. O repouso dele é DELE: se o P1 e o P2 mostrarem os mesmos três números casa por casa, a tela não está lendo dois aparelhos.
* **P3** — No rádio, e é TESTEMUNHA. Não encoste nele enquanto você gira os do cabo. Se os números dele crescerem junto com os do P1, a leitura de um controle está caindo no card de outro.
* **P4** — No rádio, e é a SEGUNDA testemunha. Mesma regra do P3. Se o P3 ficou parado e o P4 acompanhou o P1, o defeito não é do rádio — é do endereço do card.

**A armadilha.** Três, e a primeira reprova um produto certo. (1) ZERO PARADO SERIA O DEFEITO. O controle não corrige o próprio resto de fábrica, e as quatro unidades desta casa ficam entre 0,19 e 1,53 graus por segundo com o aparelho imóvel. Quem reprovar porque não deu zero está reprovando o certo — e o que merece desconfiança é o contrário: 0,0 exato nos três eixos, nos quatro controles. (2) O DESENHO. Os números do desenho no Giroscópio são +143.2 · −412.0 · +22.8. Um DualSense parado na mesa jamais dá 412 graus por segundo; se você vir esses três, ou se dois controles parados mostrarem números idênticos, não houve leitura e o teste não passou nem reprovou. (3) O PRIMEIRO OLHAR MEDE A AUSÊNCIA: o leitor nasce sob demanda e morre cinco segundos depois do último pedido; abrir e olhar no mesmo instante mostra traços. Deixe o card aberto e conte até três. E onde a prova parou: o mapa registra este caminho como MONTADO e conferido, com o número de repouso medido nos dois transportes — o degrau seguinte, ver o número sair do aparelho e chegar íntegro, é o que a sua mão faz aqui. Não julgue esta linha pelo que um jogo faz com o giro.

---

## mapa-movimento.giroscopio-radio — Giroscópio — número para a interface · rádio

*Célula:* `movimento.giroscopio @ rádio`

**O que isto prova.** Prova que os dois controles do rádio mandam para a tela o quanto giram, com a mesma qualidade dos do cabo, e cada um no seu card.

**Onde olhar.** Aba Controles. Na fita do topo, clique no chip Todos para abrir os quatro cards. Em cada card, coluna da direita, a moldura de CIMA é o Giroscópio — três linhas, X, Y e Z, com o número em graus por segundo e uma barrinha ao lado. Traço no lugar do número quer dizer que a leitura ainda não chegou. A palavra no fim do nome de cada linha diz cabo ou rádio, e é ela que separa quem tem de reagir de quem é testemunha.

**Os passos.**

1. Confira que P3 e P4 estão no rádio, sem nenhum cabo plugado neles.
2. Deite os quatro controles na mesa e tire as mãos de todos.
3. Abra a aba Controles.
4. Clique no chip Todos, na fita do topo.
5. Conte até três, devagar, com os cards já abertos.
6. Anote os três números do Giroscópio dos quatro.
7. Confira que os cards do P3 e do P4 mostram NÚMERO, e não traço, nas três linhas.
8. Confira que os números de repouso dos dois do rádio são pequenos e nenhum é exatamente zero.
9. Pegue só o P3 e gire-o devagar sobre a mesa, como um volante, sem levantar.
10. Olhe os números do Giroscópio do P3 enquanto gira: um dos três tem de crescer bastante.
11. Olhe os números do P1, do P2 e do P4 no mesmo instante: nenhum pode crescer.
12. Pare, deite o P3, e confira que os três voltam para perto do repouso anotado.
13. Repita os passos 9 a 12 com o P4.
14. Compare o repouso do P3 com o do P4: cada um tem o seu, e eles não são iguais.

**Passa quando.** Nos dois do rádio — P3 e P4 —, girar o controle faz um dos três números crescer bastante e parar devolve os três para perto do repouso. Os dois cards mostram NÚMERO, e não traço. Parados, os números são pequenos e nenhum é exatamente zero, e o repouso do P3 é diferente do repouso do P4. Girar um nunca mexe nos números de outro.

**Por controle.**

* **P1** — No cabo, e é TESTEMUNHA. Não encoste nele. É ele quem prova que a tela está lendo de verdade: se o P1 mostra números vivos e o P3 mostra traço para sempre, o buraco é do rádio, não da tela.
* **P2** — No cabo, e é a SEGUNDA testemunha. Não encoste nele. Se os números dele crescerem quando você gira o P3, alguém está escrevendo no card errado.
* **P3** — No rádio, e é o primeiro que TEM de reagir. Gire-o devagar sobre a mesa para os dois lados, com os outros três largados.
* **P4** — No rádio, e é o segundo que TEM de reagir. Mesmos gestos do P3. Ele é o último a entrar na mesa: se algum dos quatro nascer sem leitura, costuma ser este.

**A armadilha.** Quatro, e as duas primeiras são só do rádio. (1) OS CARDS QUE NÃO SÃO O PRINCIPAL ficaram cegos até o começo de setembro: o Hefesto só publicava leitura para UM controle, e os outros cards mostravam os números do desenho como se estivessem medindo. Foi curado. Se voltar, o sinal é este: dois cards com os TRÊS números idênticos, casa por casa, com os aparelhos em poses diferentes. (2) COM O CO-OP LIGADO, o controle cujo sensor o co-op segura para si legitimamente não recebe número no card — é desenho do produto. Se o P3 ou o P4 der traço, confira o co-op antes de reprovar. (3) ZERO PARADO SERIA O DEFEITO: o aparelho não corrige o próprio resto de fábrica, e as unidades desta casa ficam entre 0,19 e 1,53 graus por segundo imóveis. Reprovar porque não deu zero é reprovar o certo. (4) O DESENHO tem os números fixos +143.2 · −412.0 · +22.8; vê-los é sinal de que não houve leitura nenhuma. E onde a prova parou: o mapa registra o caminho MONTADO e uma leitura pelo rádio medida em 03/09 — repouso de 1,22 · −0,49 · −0,18 graus por segundo, dentro da faixa de fábrica. O degrau seguinte é o que a sua mão confirma aqui.

---

## mapa-movimento.giroscopio.jogo-cabo — Giroscópio — dado para o jogo (espelho ao vpad) · cabo

*Célula:* `movimento.giroscopio.jogo @ cabo`

**O que isto prova.** Prova que o interruptor Giroscópio de um controle do cabo mira naquele controle e só naquele sensor — sem levar junto o Acelerômetro nem as outras três linhas.

**Onde olhar.** Aba Controles, na LINHA de cada controle — ela aparece com o card aberto ou fechado. No fim da linha há dois interruptores lado a lado, Giroscópio e Acelerômetro, com uma bolinha verde quando ligado e cinza quando desligado. Passar o mouse no Giroscópio abre a dica: «Ligado: o jogo recebe o giro deste controle», seguida da taxa daquele transporte. Mais à esquerda, na mesma linha, o texto que diz DualSense, Xbox 360 ou Nintendo Pro é o que o jogo vê daquele controle. Quando o produto recusa o clique, ou quando ele pega só pela metade, a frase aparece no cartão daquele controle e fica trinta segundos.

**Os passos.**

1. Abra a aba Controles.
2. Clique no chip Todos, na fita do topo.
3. Leia, nas quatro linhas, o texto que diz o que o jogo vê, e anote.
4. Confira que na linha do P1 e na do P2 ele diz DualSense — o formato de Xbox 360 não tem giroscópio, e nele este teste não mede nada.
5. Anote a cor das oito bolinhas: Giroscópio e Acelerômetro das quatro linhas.
6. Clique no interruptor Giroscópio da linha do P1.
7. Olhe a bolinha dele: tem de trocar de cor.
8. Olhe o interruptor Acelerômetro da MESMA linha do P1: ele não pode ter mudado.
9. Olhe os dois interruptores das linhas do P2, do P3 e do P4: nenhum pode ter mudado.
10. Leia se apareceu alguma frase no cartão do P1 e anote-a por inteiro.
11. Clique no Giroscópio do P1 de novo, para devolvê-lo ao que era.
12. Repita os passos 6 a 11 na linha do P2.
13. Confira, no fim, que as oito bolinhas voltaram às cores do passo 5.

**Passa quando.** O clique no Giroscópio do P1 troca a cor da bolinha DELE e de mais nada: o Acelerômetro da mesma linha continua como estava, e as linhas do P2, do P3 e do P4 não se mexem. O mesmo acontece no P2. Se aparecer frase no cartão, ela EXPLICA o que não pegou — e explicar é a resposta certa; o que reprova é a bolinha trocar de cor calada quando o comando não pegou. No fim, os oito interruptores voltam ao que estavam.

**Por controle.**

* **P1** — No cabo, e é o primeiro em que você clica. Só o Giroscópio da linha dele, uma vez para desligar e uma vez para ligar. O Acelerômetro da mesma linha é a testemunha mais importante deste teste: ele não pode mudar junto.
* **P2** — No cabo, e é o segundo em que você clica. Mesmo gesto do P1. Antes de clicar, olhe onde estão as oito bolinhas — o defeito que este teste caça é um clique numa linha mexer noutra, e sem o de antes ele não se enxerga.
* **P3** — No rádio, e é TESTEMUNHA. Não clique em nada na linha dele. As duas bolinhas dele têm de ficar exatamente onde estavam.
* **P4** — No rádio, e é a SEGUNDA testemunha. Não clique em nada na linha dele. Se o P3 ficou parado e o P4 mudou junto com o P1, o comando acertou o controle errado.

**A armadilha.** Onde a prova parou: o mapa registra que o giro é MONTADO na janela que segue para o controle virtual, e é aí que a prova para. Então não reprove esta linha porque um jogo não reagiu ao movimento — o que se mede aqui é o interruptor acertar o controle certo e o sensor certo. Quatro coisas que parecem defeito e não são: se o que o jogo vê disser Xbox 360, esse formato NÃO TEM giroscópio e o produto está certo em não entregar; se a frase do cartão falar em Modo Nativo, o Hefesto saiu do meio e o jogo lê o movimento direto do controle — o interruptor esconde o sensor de um caminho e não do outro, e a frase existe justamente para não dizer «aplicado» sobre meia obediência; se o interruptor RECUSAR o clique dizendo que ainda não sabe se o sensor está ligado, ele está se negando a chutar qual é o oposto, e a checagem é se o Hefesto está de pé; e desligar o giro de um controle pode apagar os números vivos da moldura Giroscópio daquele card — a fonte não diz se deve, então ANOTE o que aconteceu em vez de julgar. A armadilha do gesto: clicar nos dois interruptores da mesma linha de uma vez esconde exatamente o defeito que este teste procura.

---

## mapa-movimento.giroscopio.jogo-radio — Giroscópio — dado para o jogo (espelho ao vpad) · rádio

*Célula:* `movimento.giroscopio.jogo @ rádio`

**O que isto prova.** Prova que o interruptor Giroscópio de um controle do rádio mira naquele controle e só naquele sensor, igual aos do cabo.

**Onde olhar.** Aba Controles, na LINHA de cada controle — aparece com o card aberto ou fechado. No fim da linha, os dois interruptores lado a lado, Giroscópio e Acelerômetro, com bolinha verde quando ligado e cinza quando desligado. A dica do Giroscópio diz «Ligado: o jogo recebe o giro deste controle» e, na linha de um controle do rádio, continua explicando que ali não há taxa típica. Mais à esquerda, o texto que diz DualSense, Xbox 360 ou Nintendo Pro é o que o jogo vê daquele controle. Recusa ou meia-obediência viram frase no cartão daquele controle, por trinta segundos.

**Os passos.**

1. Confira que P3 e P4 estão no rádio, sem cabo plugado.
2. Abra a aba Controles.
3. Clique no chip Todos, na fita do topo.
4. Leia o texto do que o jogo vê nas quatro linhas e confira que na do P3 e na do P4 diz DualSense.
5. Anote a cor das oito bolinhas: Giroscópio e Acelerômetro das quatro linhas.
6. Clique no interruptor Giroscópio da linha do P3.
7. Olhe a bolinha dele: tem de trocar de cor.
8. Olhe o interruptor Acelerômetro da MESMA linha do P3: ele não pode ter mudado.
9. Olhe os dois interruptores das linhas do P1, do P2 e do P4: nenhum pode ter mudado.
10. Leia se apareceu alguma frase no cartão do P3 e anote-a por inteiro.
11. Clique no Giroscópio do P3 de novo, para devolvê-lo ao que era.
12. Repita os passos 6 a 11 na linha do P4.
13. Confira, no fim, que as oito bolinhas voltaram às cores do passo 5.

**Passa quando.** O clique no Giroscópio do P3 troca a cor da bolinha DELE e de mais nada: o Acelerômetro da mesma linha fica como estava, e as linhas do P1, do P2 e do P4 não se mexem. O mesmo acontece no P4. Se aparecer frase no cartão, ela explica o que não pegou. No fim, tudo volta ao que era.

**Por controle.**

* **P1** — No cabo, e é TESTEMUNHA. Não clique em nada na linha dele. As duas bolinhas têm de ficar exatamente onde estavam.
* **P2** — No cabo, e é a SEGUNDA testemunha. Não clique em nada na linha dele. Se o P1 ficou parado e o P2 mudou junto com o P3, o comando acertou o controle errado — e não o transporte.
* **P3** — No rádio, e é o primeiro em que você clica. Só o Giroscópio da linha dele, uma vez para desligar e uma vez para ligar. O Acelerômetro da mesma linha não pode mudar junto.
* **P4** — No rádio, e é o segundo em que você clica. Mesmo gesto do P3. Sem anotar as oito bolinhas antes, este teste não mede nada.

**A armadilha.** A GRANDE ARMADILHA DESTA LINHA É UM FATO ABERTO, e ele é seu: em 16/08 você mediu, com a mão, que a mira por movimento NÃO responde DENTRO DO JOGO pelo rádio, enquanto pelo cabo responde — e, na mesma medição, os números mostraram o giro chegando INTEIRO ao controle virtual pelos dois caminhos. Os dois fatos ainda não se explicam juntos, e ninguém localizou onde o giro se perde depois disso. Então: se um jogo não reagir ao movimento pelo rádio, isso é achado conhecido e não erro seu, e não reprova este teste — que mede o interruptor, e não o jogo. Mais três: o microfone pelo rádio viaja no MESMO pacote do movimento, e todo pacote que traga áudio é jogado fora inteiro, o que pode calar o giro para o jogo sem aviso — anote o estado do microfone daquele controle antes de concluir; se o que o jogo vê disser Xbox 360, esse formato NÃO TEM giroscópio; e se a frase do cartão falar em Modo Nativo, o Hefesto saiu do meio e o jogo lê direto do controle, o que é o produto sendo honesto sobre meia obediência. E onde a prova parou: MONTADO na janela que vai ao controle virtual.

---

## mapa-movimento.giroscopio.taxa-cabo — Giroscópio — taxa declarada contra entregue · cabo

*Célula:* `movimento.giroscopio.taxa @ cabo`

**O que isto prova.** Prova que a taxa que o produto informa para um controle é a do CABO quando o controle está no cabo — e que ela segue o transporte, não o número do jogador.

**Onde olhar.** Aba Controles, na LINHA de cada controle. No fim da linha há o interruptor Giroscópio; pare o mouse em cima dele, sem clicar, e espere a dica aparecer. Na linha de um controle que está no cabo, a dica diz: «Ligado: o jogo recebe o giro deste controle. No cabo são 250,0 Hz exatos, e três fontes independentes concordam: o relógio do host, o relógio do controle e o descritor USB (bInterval = 6).» Na linha de um controle no rádio, a segunda metade da frase é outra — fala em não haver taxa típica e numa média que vai de 38 a 392 Hz. Confira também a palavra no fim do nome de cada linha, que diz cabo ou rádio: é ela que tem de casar com a frase.

**Os passos.**

1. Abra a aba Controles.
2. Clique no chip Todos, na fita do topo.
3. Leia a palavra no fim do nome das quatro linhas e anote quem está no cabo e quem está no rádio.
4. Pare o mouse em cima do interruptor Giroscópio da linha do P1, sem clicar.
5. Leia a dica inteira e anote a segunda metade dela.
6. Confira que ela fala em 250,0 Hz exatos no cabo.
7. Repita nos passos 4 a 6 na linha do P2.
8. Pare o mouse no interruptor Giroscópio da linha do P3 e leia a dica.
9. Confira que a dica do P3 é a OUTRA frase, a que fala em não haver taxa típica.
10. Repita na linha do P4.
11. Pegue o P3, que está no rádio, e plugue um cabo nele.
12. Conte até cinco e confira, no nome da linha do P3, que a palavra virou cabo.
13. Pare o mouse no interruptor Giroscópio do P3 de novo e leia a dica.
14. Desplugue o cabo do P3 e devolva-o ao rádio com um toque no botão PS.

**Passa quando.** As linhas do P1 e do P2, que estão no cabo, mostram a frase do CABO, a dos 250,0 Hz exatos com as três fontes que concordam. As do P3 e do P4, que estão no rádio, mostram a OUTRA frase. E quando o P3 passa para o cabo, a frase dele TROCA para a do cabo — o que prova que ela sai do transporte, e não do número do jogador. No fim, o P3 volta ao rádio e a frase volta com ele.

**Por controle.**

* **P1** — No cabo, e a dica dele TEM de trazer a frase do cabo, com os 250,0 Hz exatos.
* **P2** — No cabo, e a dica dele tem de trazer exatamente a MESMA frase do P1, palavra por palavra. Duas frases diferentes para dois controles no mesmo transporte é o defeito.
* **P3** — No rádio, e é TESTEMUNHA — até o fim, quando ele vira o sujeito: é ele que você pluga no cabo para ver a frase trocar. Antes disso, a dica dele tem de ser a do rádio.
* **P4** — No rádio, e é a testemunha que fica. Não encoste nele. A dica dele tem de continuar sendo a do rádio do começo ao fim, inclusive enquanto o P3 está plugado no cabo.

**A armadilha.** ESTA FRASE É DE CATÁLOGO, e não medição de agora. Ela é a MESMA para todo controle daquele transporte, a todo momento, com o aparelho parado ou girando — o produto NÃO mede a taxa que está entregando e NÃO compara o que declara com o que entrega. Essa metade continua por fazer, e é ela que o mapa segura como parcial: a taxa que o programa de jogos DECLARA ao jogo nunca foi medida. Então não leia a frase como «250 Hz agora»: leia como «no cabo, medido em 15/08, deu 250,0 Hz em quatro aparelhos». O que este teste mede é se o produto escolhe a frase certa para o transporte certo — e isso já quebrou uma vez, quando alguém procurou o transporte pela palavra da tela em vez do nome de máquina, e a dica sumiu. Se o interruptor de alguma linha não mostrar dica nenhuma, esse é o achado. Duas coisas mais: não CLIQUE no interruptor durante este teste, ou você desliga o sensor sem querer — só pare o mouse em cima; e o mapa não declara até onde a prova desta linha chegou, nem no cabo nem no rádio, então trate o resultado como leitura de frase, e não como medição de taxa.

---

## mapa-movimento.giroscopio.taxa-radio — Giroscópio — taxa declarada contra entregue · rádio

*Célula:* `movimento.giroscopio.taxa @ rádio`

**O que isto prova.** Prova que a taxa que o produto informa para um controle é a do RÁDIO quando o controle está no rádio — e que ela troca junto com o transporte.

**Onde olhar.** Aba Controles, na LINHA de cada controle. No fim da linha há o interruptor Giroscópio; pare o mouse em cima dele, sem clicar, e espere a dica. Na linha de um controle no rádio a dica diz: «Ligado: o jogo recebe o giro deste controle. No rádio não há taxa típica. Medido em cinco janelas de 8 a 10 s no mesmo controle: a média foi de 38 a 392 Hz entre janelas consecutivas, sem que nada mudasse. Os 1000 Hz que o SDL declara para Bluetooth não aparecem em janela nenhuma.» Na linha de um controle no cabo a segunda metade é outra, e fala em 250,0 Hz exatos. A palavra no fim do nome de cada linha diz cabo ou rádio, e é ela que tem de casar com a frase.

**Os passos.**

1. Abra a aba Controles.
2. Clique no chip Todos, na fita do topo.
3. Leia a palavra no fim do nome das quatro linhas e anote quem está no cabo e quem está no rádio.
4. Pare o mouse em cima do interruptor Giroscópio da linha do P3, sem clicar.
5. Leia a dica inteira e anote a segunda metade dela.
6. Confira que ela diz que no rádio não há taxa típica e cita a faixa de 38 a 392 Hz.
7. Repita os passos 4 a 6 na linha do P4.
8. Pare o mouse no interruptor Giroscópio da linha do P1 e leia a dica.
9. Confira que a do P1 é a OUTRA frase, a dos 250,0 Hz exatos.
10. Repita na linha do P2.
11. Desplugue o cabo do P1.
12. Dê um toque no botão PS do P1 para trazê-lo de volta pelo rádio, sem demorar.
13. Conte até cinco e confira, no nome da linha do P1, que a palavra virou rádio.
14. Pare o mouse no interruptor Giroscópio do P1 de novo e leia a dica.
15. Plugue o cabo de volta no P1 para devolver a mesa ao arranjo de dois e dois.

**Passa quando.** As linhas do P3 e do P4, que estão no rádio, mostram a frase do RÁDIO — a que diz que não há taxa típica e cita a faixa de 38 a 392 Hz. As do P1 e do P2, no cabo, mostram a outra. E quando o P1 sai do cabo e volta pelo rádio, a frase dele TROCA para a do rádio: é isso que prova que ela sai do transporte, e não do número do jogador. No fim, com o cabo de volta, ela troca outra vez.

**Por controle.**

* **P1** — No cabo, e é TESTEMUNHA até o fim, quando ele vira o sujeito: é ele que você tira do cabo e devolve pelo rádio, para ver a frase trocar. Antes disso, a dica dele tem de ser a do cabo.
* **P2** — No cabo, e é a testemunha que fica. Não encoste nele, e não desplugue o cabo dele. A dica dele tem de continuar a do cabo do começo ao fim, inclusive enquanto o P1 está no rádio.
* **P3** — No rádio, e a dica dele TEM de trazer a frase do rádio, com a faixa de 38 a 392 Hz.
* **P4** — No rádio, e a dica dele tem de trazer exatamente a MESMA frase do P3, palavra por palavra. Duas frases diferentes para dois controles no mesmo transporte é o defeito.

**A armadilha.** Três, e a primeira é um número que já foi derrubado nesta casa. (1) OS 1000 Hz SÃO DECLARAÇÃO, NÃO ENTREGA. O programa de jogos declara 1000 Hz para Bluetooth, e o aparelho nunca entregou isso em janela nenhuma: o máximo já medido foi 402,9 Hz, e a faixa medida em 16 janelas foi de 173 a 403 Hz. A própria dica diz isso; quem escrever 1000 Hz como taxa do aparelho está reintroduzindo um fato que a medição derrubou. (2) A FRASE É DE CATÁLOGO. Ela é a mesma para todo controle daquele transporte, a todo momento, com o controle parado ou girando — o produto NÃO mede a taxa que está entregando e NÃO compara declarado com entregue; essa metade continua por fazer, e é ela que o mapa segura como parcial. Não leia a dica como uma medição de agora. (3) O RELÓGIO DO REPLUGUE. Do puxão do cabo até o toque no PS têm de passar menos de trinta segundos, senão o P1 volta com outro número de jogador — e isso é a regra do produto funcionando, não defeito; refaça mais rápido. E não CLIQUE no interruptor durante este teste: só pare o mouse em cima, ou você desliga o sensor sem querer. O mapa não declara até onde a prova desta linha chegou, então trate o resultado como leitura de frase, e não como medição de taxa.

---

## mapa-movimento.imu.calibracao-cabo — Calibração de fábrica da IMU · cabo

*Célula:* `movimento.imu.calibracao @ cabo`

**O que isto prova.** Prova que cada controle do cabo usa a calibração de fábrica DELE, e não a de outro — o repouso de cada um é próprio e se repete.

**Onde olhar.** Dois lugares. Primeiro, a aba Controles: clique no chip Todos da fita do topo e leia, dentro de cada card, as duas molduras da coluna da direita — Giroscópio em cima, com X, Y e Z em graus por segundo, e Acelerômetro embaixo, com X, Y e Z em g. Deitado e parado, o Acelerômetro dá um dos três perto de 1,000 e os outros dois perto de zero, e o Giroscópio dá três números pequenos que NÃO são zero: esse é o resto de fábrica daquela unidade, e é ele que este teste persegue. Segundo, o botão «Calibrar Sensores de Movimento», no canto superior direito do quadro da aba Controles: ele abre uma página com o título «Calibrar sensores de movimento», três passos numerados (1 Deixe os controles parados · 2 Não toque neles · 3 Pronto), um selo por controle que diz Parado, Medindo… ou Calibrado, os números de Giroscópio e Acelerômetro de cada um, e os botões Começar e Fechar.

**Os passos.**

1. Confira que P1 e P2 estão no cabo, lendo a palavra no fim do nome de cada linha.
2. Deite os quatro controles numa superfície plana, virados para cima, e tire as mãos de todos.
3. Abra a aba Controles.
4. Clique no chip Todos, na fita do topo.
5. Conte até três, devagar, com os cards já abertos.
6. Anote os SEIS números do P1 — os três do Giroscópio e os três do Acelerômetro.
7. Anote os seis números do P2, do P3 e do P4, do mesmo jeito.
8. Confira que o Acelerômetro dos quatro dá um eixo perto de 1,000 e os outros dois perto de zero.
9. Confira que os três números de Giroscópio do P1 são pequenos e nenhum é exatamente zero.
10. Compare os seis números do P1 com os seis do P2: eles não podem ser iguais casa por casa.
11. Levante o P1, gire-o na mão e deite-o de novo na MESMA posição.
12. Conte até três e leia os seis números do P1 outra vez: eles têm de voltar para perto dos que você anotou.
13. Repita os passos 11 e 12 com o P2.
14. Clique no botão «Calibrar Sensores de Movimento», no canto superior direito do quadro.
15. Leia os três passos da página e anote o que o selo de cada controle diz.
16. Clique em «Fechar» para voltar à aba Controles.

**Passa quando.** Nos dois do cabo — P1 e P2 —, os seis números de repouso são PRÓPRIOS: o Acelerômetro fecha na gravidade (um eixo perto de 1,000, os outros dois perto de zero) e o Giroscópio dá três números pequenos e diferentes de zero. Os seis do P1 não são iguais aos seis do P2, casa por casa. E levantar o controle e deitá-lo de novo devolve os mesmos seis números de antes — o repouso de cada aparelho se repete, porque a calibração dele é dele.

**Por controle.**

* **P1** — No cabo, e é o primeiro cujo repouso TEM de ser próprio. Anote os seis números dele, mexa nele e deite-o de novo, e confira que os seis voltam.
* **P2** — No cabo, e é o segundo. Mesmos gestos do P1. O par P1–P2 é o que decide este teste: se os dois mostrarem os mesmos seis números casa por casa, a calibração de UM está sendo usada nos dois — que é exatamente o defeito que o mapa avisa que faz os outros controles derivarem.
* **P3** — No rádio, e é TESTEMUNHA. Não encoste nele. Anote os seis números dele: eles têm de ser diferentes dos do P1 e dos do P2, porque o resto de fábrica é de cada aparelho.
* **P4** — No rádio, e é a SEGUNDA testemunha. Mesma regra do P3. Quatro aparelhos parados na mesma mesa têm de dar quatro repousos diferentes.

**A armadilha.** A MAIOR DELAS É A PÁGINA. A página «Calibrar sensores de movimento» é DESENHO: ela não tem nenhum campo vivo e nenhum botão ligado ao Hefesto. Os três selos — Parado, Medindo…, Calibrado — trocam porque você clica neles, e clicar em «Começar» muda o que está na tela e NÃO calibra aparelho nenhum. Os números que ela mostra são fixos no arquivo. Não conte nada do que acontecer ali como resposta do produto; abra-a para conferir que ela existe, que os três passos estão legíveis e que os controles conectados aparecem, e mais nada. Duas outras: ZERO PARADO SERIA O DEFEITO, e não o acerto — o aparelho não corrige o próprio resto de fábrica, e as unidades desta casa ficam entre 0,19 e 1,53 graus por segundo imóveis; e o DESENHO da aba Controles tem números fixos (+143.2 · −412.0 · +22.8 no Giroscópio, +0.105 · +0.976 · +0.170 no Acelerômetro), então vê-los é sinal de que não houve leitura. E onde a prova parou: o mapa registra que o produto LÊ a calibração de fábrica uma vez e a carimba, e nada além — «imutável por unidade» é afirmação sobre o aparelho e continua sem medição direta. Este teste é o que mais perto chega disso, medindo a consequência com a sua mão.

---

## mapa-movimento.imu.calibracao-radio — Calibração de fábrica da IMU · rádio

*Célula:* `movimento.imu.calibracao @ rádio`

**O que isto prova.** Prova que cada controle do rádio usa a calibração de fábrica DELE, e que esse repouso viaja com o aparelho quando ele troca de transporte.

**Onde olhar.** Dois lugares. Primeiro, a aba Controles: clique no chip Todos da fita e leia, em cada card, a moldura Giroscópio (X, Y e Z em graus por segundo) e a moldura Acelerômetro (X, Y e Z em g), na coluna da direita. Deitado e parado, o Acelerômetro dá um eixo perto de 1,000 e os outros dois perto de zero, e o Giroscópio dá três números pequenos e diferentes de zero — esse é o resto de fábrica daquela unidade. Segundo, o botão «Calibrar Sensores de Movimento», no canto superior direito do quadro da aba Controles, que abre a página «Calibrar sensores de movimento» com três passos, um selo por controle (Parado · Medindo… · Calibrado) e os botões Começar e Fechar. A fonte não diz onde a tela mostraria uma calibração que chegou embaralhada pelo rádio: não existe campo para isso.

**Os passos.**

1. Confira que P3 e P4 estão no rádio, sem nenhum cabo plugado neles.
2. Deite os quatro controles numa superfície plana, virados para cima, e tire as mãos de todos.
3. Abra a aba Controles.
4. Clique no chip Todos, na fita do topo.
5. Conte até três, devagar, com os cards já abertos.
6. Anote os SEIS números do P3 — os três do Giroscópio e os três do Acelerômetro.
7. Anote os seis números do P4 do mesmo jeito.
8. Confira que o Acelerômetro dos dois dá um eixo perto de 1,000 e os outros dois perto de zero.
9. Compare os seis do P3 com os seis do P4: não podem ser iguais casa por casa.
10. Compare os seis do P3 com os seis do P1 e do P2: também não podem ser iguais.
11. Plugue um cabo no P3.
12. Conte até cinco e confira que a palavra no fim do nome da linha do P3 virou cabo.
13. Conte até três e leia de novo os seis números do P3, com ele deitado e parado.
14. Compare esses seis com os seis que você anotou no passo 6: eles têm de ser praticamente os mesmos.
15. Desplugue o cabo do P3 e devolva-o ao rádio com um toque no botão PS.
16. Clique em «Calibrar Sensores de Movimento» e confira que a página abre com os três passos e os controles conectados.
17. Clique em «Fechar» para voltar.

**Passa quando.** Nos dois do rádio — P3 e P4 —, os seis números de repouso são PRÓPRIOS: o Acelerômetro fecha na gravidade e o Giroscópio dá três números pequenos e diferentes de zero, distintos entre um controle e outro. E o teste que decide: quando o P3 passa do rádio para o cabo, os seis números dele continuam praticamente os mesmos. O repouso segue o APARELHO, e não o transporte — foi assim que se mediu em 15/08, com diferença de no máximo 0,06 grau por segundo entre os dois transportes, contra cinco vezes de diferença entre uma unidade e outra.

**Por controle.**

* **P1** — No cabo, e é TESTEMUNHA. Não encoste nele. Anote os seis números dele para ter com o que comparar: eles têm de ser diferentes dos do P3 e dos do P4.
* **P2** — No cabo, e é a SEGUNDA testemunha. Não encoste nele. Se os seis números do P2 mudarem quando você pluga o P3 no cabo, alguma coisa está trocando a calibração de um pelo do outro.
* **P3** — No rádio, e é o sujeito deste teste. Anote os seis números dele pelo rádio, plugue-o no cabo, leia de novo, e devolva-o ao rádio. Os seis têm de acompanhá-lo nas duas travessias.
* **P4** — No rádio, e é o segundo cujo repouso tem de ser próprio. Não o mova de transporte. Ele é a prova de que o rádio, sozinho, entrega calibração boa: se o P3 só ficar certo no cabo e o P4 der números estranhos o tempo todo, o buraco é do rádio.

**A armadilha.** Quatro, e a primeira é do rádio. (1) SÓ PELO RÁDIO a calibração passa por uma conferência de integridade antes de ser aceita, e quando ela falha o produto NÃO avisa: ele cai numa calibração genérica de catálogo. O sintoma é justamente este — um controle do rádio cujos seis números de repouso parecem de livro, ou iguais aos de outro aparelho. E há uma segunda rede de segurança, no driver do sistema, que aceita uma calibração zerada com um aviso que nunca chega à tela. Por isso o teste é comparar os quatro entre si: nenhum campo da tela conta essa história. (2) A PÁGINA DE CALIBRAR É DESENHO. Ela não tem campo vivo nem botão ligado ao Hefesto; os três selos trocam porque você clica neles, e «Começar» não calibra aparelho nenhum. Abra-a para conferir que existe e está legível, e nada mais. (3) ZERO PARADO SERIA O DEFEITO: o aparelho não corrige o próprio resto de fábrica, e as unidades desta casa ficam entre 0,19 e 1,53 graus por segundo imóveis. (4) O DESENHO da aba Controles tem números fixos; se os quatro cards mostrarem os mesmos três números no Giroscópio, não houve leitura. E onde a prova parou: o mapa registra que o produto LÊ a calibração de fábrica uma vez e a carimba — «imutável por unidade» continua sem medição direta, e é a consequência dela que a sua mão mede aqui.

---

## mapa-movimento.imu.perda-cabo — Perda de amostras de IMU · cabo

*Célula:* `movimento.imu.perda @ cabo`

**O que isto prova.** Prova que, no cabo, a leitura de movimento não engasga: os números andam sem travar enquanto você move o controle sem parar.

**Onde olhar.** Aba Controles. Clique no chip Todos, na fita do topo, para abrir os quatro cards. Em cada card, coluna da direita, as duas molduras: Giroscópio em cima e Acelerômetro embaixo, com X, Y e Z e uma barrinha ao lado de cada número. O `?` ao lado do rótulo Giroscópio avisa que aquilo é leitura viva do aparelho, dez vezes por segundo. É a barrinha que denuncia engasgo melhor que o número: ela anda contínua enquanto o controle se move, e para de vez quando a leitura para. QUANTO A UMA CONTAGEM DE PERDAS: a fonte não diz onde se lê isso, porque o produto NÃO a mostra em campo nenhum — no cabo ele nem a conta.

**Os passos.**

1. Confira que P1 e P2 estão no cabo, lendo a palavra no fim do nome de cada linha.
2. Abra a aba Controles.
3. Clique no chip Todos, na fita do topo.
4. Conte até três, devagar, com os cards já abertos.
5. Confira que o card do P1 e o do P2 mostram número, e não traço, nas seis linhas de sensor.
6. Pegue o P1 e gire-o devagar e SEM PARAR, de um lado para o outro, por uns vinte segundos.
7. Olhe a moldura Giroscópio do P1 o tempo todo: os números e as barrinhas têm de andar continuamente, sem travar num valor e sem sumir.
8. Anote se houve algum instante em que os números congelaram enquanto a sua mão continuava mexendo.
9. Deite o P1 e faça o mesmo com o P2, por outros vinte segundos.
10. Anote o mesmo para o P2.
11. Olhe, durante as duas voltas, se os cards do P3 e do P4 continuaram mostrando número — eles não podem virar traço por causa do que você faz nos do cabo.

**Passa quando.** Nos dois do cabo — P1 e P2 —, os números e as barrinhas andam sem interrupção durante os vinte segundos de movimento contínuo: não congelam num valor com a sua mão ainda mexendo, e não viram traço. Se algum deles travar enquanto você move, isso é o achado — e anote a hora, porque não existe contagem em lugar nenhum que confirme.

**Por controle.**

* **P1** — No cabo, e é o primeiro. Gire-o sem parar por vinte segundos e olhe a moldura Giroscópio dele o tempo todo. No cabo, medido em 15/08, foram ZERO pacotes perdidos em mais de quinze mil seguidos, então travar aqui é notícia.
* **P2** — No cabo, e é o segundo. Mesma volta de vinte segundos. Ele foi medido na mesma noite e também deu zero perdido — os dois do cabo têm de andar liso.
* **P3** — No rádio, e é TESTEMUNHA. Não encoste nele. O card dele não pode virar traço enquanto você mexe nos do cabo: se virar, o que você mexeu derrubou o vizinho de outro transporte.
* **P4** — No rádio, e é a SEGUNDA testemunha. Mesma regra do P3. Se o P3 aguentou e o P4 caiu, o problema não é do rádio — é do card dele.

**A armadilha.** Três, e a primeira desarma a leitura fácil. (1) TELA SEM MÁ NOTÍCIA NÃO É PROVA DE QUE NADA SE PERDEU. No cabo o produto não conta perda nenhuma: um pacote que chega errado é descartado em silêncio, sem entrar em conta alguma. A única contagem que existe é do rádio, e ela conta o que o PRODUTO descartou — não o que o caminho comeu. Chamar aquilo de «amostras de movimento perdidas» seria a mentira barata desta linha, e o mapa a nomeia assim. (2) A TELA ATUALIZA DEZ VEZES POR SEGUNDO e o aparelho entrega 250 vezes — a tela é mais lenta POR DESENHO, e isso não é perda. Um engasgo de poucos pacotes é invisível nesta cadência; o que este teste enxerga é travamento de meio segundo para cima. (3) E JÁ HOUVE PERDA REAL NO CABO, medida em 19/08: 36% das amostras eram jogadas fora por um desencontro de menos de 1% entre a velocidade da fonte e o teto do produto — foi curado, e hoje há uma régua que trava a cadência mínima. Se voltar, é assim que aparece: números que andam mas «pulam», sem travar de vez. E o que o mapa deixa como dívida escrita: existe uma cura MEDIDA E NÃO APLICADA — um contador que já viaja dentro do pacote nos DOIS transportes e que o produto não lê em transporte nenhum. Enquanto ele não for lido, a única régua desta linha é a sua mão.

---

## mapa-movimento.imu.perda-radio — Perda de amostras de IMU · rádio

*Célula:* `movimento.imu.perda @ rádio`

**O que isto prova.** Prova que, no rádio, a leitura de movimento engasga quando o sinal piora — e que os do cabo continuam lisos no mesmo instante.

**Onde olhar.** Aba Controles. Clique no chip Todos, na fita do topo, para abrir os quatro cards. Em cada card, coluna da direita, a moldura Giroscópio em cima e a Acelerômetro embaixo, com X, Y e Z e uma barrinha ao lado de cada número. A barrinha denuncia engasgo melhor que o número: ela anda contínua enquanto o controle se move e para de vez quando a leitura para. Traço no lugar do número quer dizer que a leitura sumiu. QUANTO A UMA CONTAGEM DE PERDAS: a fonte não diz onde se lê isso — o produto não a mostra em campo nenhum. O que ele conta por dentro, no rádio, é o que ELE descartou, e nem isso chega à tela.

**Os passos.**

1. Confira que P3 e P4 estão no rádio, sem cabo plugado, e P1 e P2 no cabo.
2. Abra a aba Controles.
3. Clique no chip Todos, na fita do topo.
4. Conte até três, devagar, com os cards já abertos.
5. Confira que os quatro cards mostram número, e não traço, nas seis linhas de sensor.
6. Pegue o P3 e gire-o devagar e SEM PARAR, de um lado para o outro, ali mesmo ao lado do PC.
7. Olhe a moldura Giroscópio do P3 por uns dez segundos: ela tem de andar lisa a essa distância.
8. Continue girando o P3 sem parar e caminhe devagar para longe do PC, até onde o cabo da tela deixar você ainda enxergar a moldura dele.
9. Olhe a moldura do P3 durante a caminhada e anote se os números travaram, pularam ou viraram traço.
10. Ponha o seu corpo entre o P3 e o PC, continuando a girar, e anote de novo o que a moldura fez.
11. Olhe, nesse mesmo instante, as molduras do P1 e do P2: elas não podem ter travado junto.
12. Volte para perto do PC com o P3 ainda girando e confira que a moldura dele volta a andar lisa.
13. Repita os passos 6 a 12 com o P4.

**Passa quando.** Perto do PC, os dois do rádio andam lisos. Longe, ou com o seu corpo no caminho, é honesto que os números do P3 e do P4 travem, pulem ou virem traço — o mapa mediu, em 15/08, 2.242 pacotes sumindo num salto só quando o sinal de um controle do rádio piorou. E no MESMO instante os cards do P1 e do P2, que estão no cabo, não podem travar: é essa diferença que o teste procura. Voltando para perto, os do rádio voltam a andar.

**Por controle.**

* **P1** — No cabo, e é TESTEMUNHA. Não encoste nele, e deixe-o deitado com o card aberto. Ele tem de andar liso durante as duas caminhadas: se ele travar junto com o P3, o engasgo não é do rádio — é do Hefesto ou da máquina.
* **P2** — No cabo, e é a SEGUNDA testemunha. Mesma regra do P1. Dois no cabo lisos, dois no rádio engasgando, é a assinatura que este teste quer.
* **P3** — No rádio, e é o primeiro a se afastar. Gire-o sem parar enquanto caminha e enquanto se põe na frente dele. É nele que o engasgo tem de aparecer.
* **P4** — No rádio, e é o segundo a se afastar. Mesma volta do P3. Se o P3 engasgou e o P4 não, ou ao contrário, anote os dois: o mapa já mediu unidades do mesmo rádio entregando taxas quase duas vezes diferentes entre si.

**A armadilha.** Quatro. (1) ENGASGAR NO RÁDIO É RESPOSTA VÁLIDA, e não erro seu: o mapa mediu 2.242 pacotes sumindo num único salto, com o computador recebendo 27 por segundo enquanto o RELÓGIO DO PRÓPRIO CONTROLE continuava marcando 398 por segundo — quer dizer, o controle mandou e o caminho comeu. Anote o que viu e siga; não fique tentando até dar liso. (2) A CONTAGEM QUE O PRODUTO TEM CONTA A COISA ERRADA. No rádio ele conta os pacotes que ELE descartou por vir embaralhados, e isso não é o mesmo que amostra de movimento perdida; a perda por o produto ter de jogar fora o excesso não é contada em lugar nenhum. E nada disso aparece na tela. Chamar aquele número de «perda de movimento» seria a mentira barata desta linha. (3) A TELA ATUALIZA DEZ VEZES POR SEGUNDO e o aparelho entrega centenas — a tela é mais lenta por desenho, e engasgo pequeno é invisível nessa cadência. Ausência de travamento na tela NÃO é prova de que nada se perdeu. (4) NÃO CONFUNDA ENGASGO COM QUEDA: se o chip do controle sumir da fita do topo, ele se desconectou, e isso é outro teste — o card virar traço com o chip ainda na fita é que é engasgo. E o que o mapa deixa como dívida escrita: existe uma cura MEDIDA E NÃO APLICADA — um contador que já viaja dentro do pacote nos dois transportes, que daria ao cabo a conta que ele nunca teve e ao rádio uma que mede perda de verdade. Enquanto ele não for lido, a única régua desta linha é a sua mão.

---

# plataforma

---

## mapa-plataforma.adocao-cabo — Adoção pelo Hefesto (grab, vpad, perfil) · cabo

*Célula:* `plataforma.adocao @ cabo`

**O que isto prova.** Prova que, pelo cabo, o Hefesto toma o controle para si e entrega ao jogo um controle montado por ele — e que a escolha de como o jogo enxerga cada aparelho fica no aparelho escolhido.

**Onde olhar.** Na aba Jogar. Primeiro a linha "Status", com as duas posições "Ligado" e "Desligado". Depois o quadro "O Controle é visto como:": um cartão por controle, com o número do jogador, o nome da cor do plástico e por onde ele está ligado; dentro de cada cartão, três chips — DualSense, Xbox 360 e Nintendo Pro. Embaixo dos cartões fica o botão "Reconectar Controles". Quando o Hefesto não está entregando o controle ao jogo, nasce ali a linha "Guardada por controle: o Hefesto não está entregando o controle ao jogo agora, e a escolha vale assim que ele voltar a entregar.". A mesma informação, só para ler, está na aba Controles: dentro do quadro "Dispositivos Conectados", a linha de cada controle traz "Vê como" com o nome do que o jogo enxerga. E quem fecha o teste é o JOGO: o desenho dos botões na tela dele.

**Os passos.**

1. Confira que P1 e P2 estão no cabo e P3 e P4 no rádio.
2. Abra a aba Jogar.
3. Confira que a linha "Status" está na posição "Ligado".
4. Leia os quatro cartões do quadro "O Controle é visto como:" e anote qual chip está aceso em cada um.
5. Abra o jogo com os quatro jogadores dentro da partida.
6. Anote como o jogo desenha os botões de cada um dos quatro jogadores.
7. Volte para a janela do Hefesto.
8. Clique no chip "Xbox 360" do cartão do P1.
9. Confira que só o cartão do P1 trocou de chip aceso, e que os outros três continuam no que você anotou.
10. Clique em "Reconectar Controles", embaixo dos cartões.
11. Volte ao jogo e olhe o desenho dos botões do jogador 1.
12. Olhe os botões dos jogadores 2, 3 e 4 e confira que continuam como estavam.
13. Volte ao Hefesto e clique no chip "Xbox 360" do cartão do P2.
14. Clique em "Reconectar Controles" de novo.
15. Volte ao jogo e confira que agora são dois jogadores desenhados como Xbox, e que são o 1 e o 2.
16. Abra a aba Controles e leia o "Vê como" das quatro linhas: tem de contar a mesma história dos cartões.
17. Volte à aba Jogar, clique no chip "DualSense" nos cartões do P1 e do P2 e clique em "Reconectar Controles" uma última vez, para desfazer.

**Passa quando.** A escolha feita no cartão do P1 muda o desenho dos botões do jogador 1 dentro do jogo, e de mais ninguém; a do P2 muda o jogador 2, e de mais ninguém. Os cartões do P3 e do P4 não trocam de chip sozinhos, e os jogadores 3 e 4 continuam desenhados como estavam. A leitura "Vê como" da aba Controles diz o mesmo que os cartões da aba Jogar.

**Por controle.**

* **P1** — No cabo, e é ESTE que muda primeiro. Ponha "Xbox 360" no cartão dele, clique em "Reconectar Controles" e veja o jogador 1 trocar de desenho no jogo. No fim, devolva "DualSense".
* **P2** — No cabo, e é o segundo a mudar. Só mexa nele depois de o P1 já ter trocado — assim você vê os dois estados na mesma tela. No fim, devolva "DualSense".
* **P3** — No rádio, e é TESTEMUNHA. Não toque no cartão dele. Se o chip dele trocar sozinho quando você mexe no do P1, a escolha vazou para a máquina inteira em vez de ficar no aparelho, e isso é o defeito que este teste caça.
* **P4** — No rádio, e é a segunda testemunha. Mesma conferência. Se o P3 ficou parado e o P4 mudou, o problema não é do rádio: é escrita no controle errado.

**A armadilha.** Três, e a primeira faz o teste medir nada. (1) Clicar no chip e correr para o jogo: a escolha é gravada na hora, mas ela só chega ao jogo quando o Hefesto monta de novo o controle que o jogo enxerga — é para isso que o "Reconectar Controles" está nos passos. (2) O chip "Nintendo Pro" é desenho sem motor: clicar nele RECUSA com uma frase na tela, e isso é o produto certo, não defeito. (3) Se a linha "Guardada por controle: o Hefesto não está entregando o controle ao jogo agora…" estiver na tela, o Hefesto está fora do meio — Status em "Desligado", ou o modo Navegação — e nenhuma escolha vai mudar coisa alguma; ponha o Status em "Ligado" antes de começar. E sobre até onde a prova chegou: esta linha do mapa não tem degrau escrito, e é de propósito — tomar o controle para si e montar um controle novo é ato do computador, não conversa com o aparelho; no DualSense não existe nenhum aviso de "este dono me tomou". O que se mede é o efeito no jogo, e é o que estes passos pedem.

---

## mapa-plataforma.adocao-radio — Adoção pelo Hefesto (grab, vpad, perfil) · rádio

*Célula:* `plataforma.adocao @ rádio`

**O que isto prova.** Prova que, pelo rádio, o Hefesto toma o controle para si igual ao cabo — a escolha de como o jogo enxerga o aparelho vale nele, e sobrevive a ele cair e voltar.

**Onde olhar.** Na aba Jogar. A linha "Status", com "Ligado" e "Desligado". O quadro "O Controle é visto como:", com um cartão por controle — número do jogador, nome da cor do plástico, por onde ele está ligado — e três chips dentro de cada um: DualSense, Xbox 360 e Nintendo Pro. Embaixo, o botão "Reconectar Controles". A linha "Guardada por controle: o Hefesto não está entregando o controle ao jogo agora, e a escolha vale assim que ele voltar a entregar." aparece quando o Hefesto está fora do meio. Na aba Controles, dentro do quadro "Dispositivos Conectados", a linha de cada controle repete a escolha em "Vê como", só para leitura. E quem fecha é o JOGO: o desenho dos botões de cada jogador.

**Os passos.**

1. Confira que P3 e P4 estão no rádio e P1 e P2 no cabo.
2. Abra a aba Jogar.
3. Confira que a linha "Status" está na posição "Ligado".
4. Leia os quatro cartões do quadro "O Controle é visto como:" e anote qual chip está aceso em cada um.
5. Abra o jogo com os quatro jogadores dentro da partida.
6. Anote como o jogo desenha os botões de cada um dos quatro jogadores.
7. Volte ao Hefesto e clique no chip "Xbox 360" do cartão do P3.
8. Confira que só o cartão do P3 trocou de chip aceso.
9. Clique em "Reconectar Controles".
10. Volte ao jogo e confira que só o jogador 3 mudou de desenho.
11. Volte ao Hefesto e clique no chip "Xbox 360" do cartão do P4.
12. Clique em "Reconectar Controles" e confira no jogo que agora os jogadores 3 e 4 estão desenhados como Xbox.
13. Segure o botão PS do P3 até todas as luzes dele apagarem, e solte.
14. Dê um toque no botão PS do P3 para trazê-lo de volta, sem demorar — do apagar até o toque tem de passar menos de trinta segundos.
15. Leia o cartão do P3 quando ele reaparecer: o chip aceso tem de ser "Xbox 360" de novo.
16. Clique em "Reconectar Controles" e confira no jogo que o jogador 3 voltou desenhado como Xbox.
17. Devolva "DualSense" nos cartões do P3 e do P4 e clique em "Reconectar Controles" uma última vez.

**Passa quando.** A escolha feita no cartão do P3 muda o desenho dos botões do jogador 3 no jogo, e de mais ninguém; a do P4 muda o jogador 4. Os cartões do P1 e do P2 não trocam de chip sozinhos e os jogadores 1 e 2 ficam como estavam. E depois de o P3 cair e voltar pelo rádio, o cartão dele volta com a mesma escolha de antes — a escolha é do aparelho, não da sessão.

**Por controle.**

* **P1** — No cabo, e é TESTEMUNHA. Não toque no cartão dele. Se ele trocar de chip quando você mexe no P3, a escolha vazou para a máquina inteira.
* **P2** — No cabo, e é a segunda testemunha. Mesma conferência.
* **P3** — No rádio, e é ESTE que muda primeiro. Ponha "Xbox 360", reconecte, veja o jogador 3 trocar — e depois desligue-o e religue-o pelo PS para conferir se a escolha volta com ele.
* **P4** — No rádio, e é o segundo a mudar. Ponha "Xbox 360" só depois de o P3 já ter mudado. Confira também que ele não trocou sozinho quando você mexeu no P3.

**A armadilha.** Quatro. (1) "Reconectar Controles" NÃO reconecta o rádio, e isso é decisão dela: o botão traz de volta o JOGADOR — o controle que o jogo enxerga —, nunca o link do rádio. Quem religa o aparelho é o botão PS na sua mão. Se o P3 sumiu da tela, esse botão não vai trazê-lo. (2) O prazo: o lugar de quem cai fica guardado por trinta segundos; se você demorar mais que isso entre apagar e religar, ele volta com outro número, e isso é a regra do produto, não defeito. (3) O chip "Nintendo Pro" é desenho sem motor e recusa com uma frase — é o produto certo. (4) Se a linha "Guardada por controle: o Hefesto não está entregando o controle ao jogo agora…" estiver na tela, nada do que você escolher vai chegar ao jogo; ponha o Status em "Ligado" primeiro. E o degrau: esta linha do mapa não tem degrau escrito de propósito — tomar o controle e montar um controle novo é ato do computador, não conversa com o aparelho, e por isso o mapa registra que pelo rádio isso funciona sem nenhuma trava de transporte: é exatamente essa igualdade que os passos acima medem.

---

## mapa-plataforma.crc32-cabo — CRC-32 no envelope (integridade de report) · cabo

*Célula:* `plataforma.crc32 @ cabo`

**O que isto prova.** Prova que, pelo cabo, o que o Hefesto manda e o que ele lê chegam inteiros mesmo sem nenhum selo de conferência no caminho.

**Onde olhar.** O selo de conferência não tem campo em aba nenhuma, e a fonte não diz onde ele se leria — porque pelo cabo ele simplesmente não existe. O que se lê é o EFEITO, em três lugares. No aparelho: a barra de luz (as duas tiras que ladeiam o touchpad) e o tremor na sua mão. Na tela: a linha "Cor" da coluna de cada controle, na aba Iluminação; o botão "Testar" da linha "Testar agora", na aba Vibração; e, na aba Controles, o cartão de cada controle, onde o analógico tem um pontinho que anda com a sua mão, o desenho do botão acende quando você aperta e a bateria mostra um número.

**Os passos.**

1. Confira que P1 e P2 estão no cabo e P3 e P4 no rádio.
2. Abra a aba Iluminação.
3. Clique numa bolinha da linha "Cor" da coluna do P1 e olhe a barra de luz dele no aparelho.
4. Repita nos outros três, com uma cor diferente em cada um.
5. Olhe os quatro controles juntos: quatro barras acesas, quatro cores.
6. Abra a aba Vibração.
7. Segure o P1 na mão e clique em "Testar" na coluna dele; sinta o meio segundo de tremor.
8. Repita o "Testar" nos outros três, um de cada vez, com o controle na mão.
9. Abra a aba Controles e clique no chip "Todos" da fita do topo, para abrir os quatro cartões.
10. Mexa o analógico esquerdo do P1 em círculos, devagar, e olhe o pontinho dentro do cartão dele acompanhar.
11. Aperte, um a um, o quadrado, o triângulo, o círculo e o xis do P1, olhando o desenho acender a cada aperto.
12. Repita os dois passos acima no P2.
13. Repita no P3 e no P4.
14. Anote se em algum momento o pontinho pulou para um canto sem a sua mão ir lá, se um botão acendeu sozinho, ou se um número de bateria deu um salto absurdo.

**Passa quando.** Os quatro obedecem à cor e ao tremor, e o desenho vivo dos quatro segue a sua mão sem pulos e sem acender nada sozinho. Pelo cabo, o P1 e o P2 fazem tudo isso sem nenhuma conferência de integridade no caminho — é este o ponto da linha: não há selo, e mesmo assim nada chega quebrado.

**Por controle.**

* **P1** — No cabo, e é um dos dois que provam o lado SEM selo. Cor, tremor e o desenho vivo seguindo a mão.
* **P2** — No cabo, o segundo. Mesmos gestos. Um pulo que apareça no P1 e no P2 e nunca no P3 e no P4 é justamente a assinatura que este teste procura.
* **P3** — No rádio, e é comparação. Mesmos gestos. Aqui cada quadro que chega é conferido por selo, e o que não confere é jogado fora antes de virar tinta na tela.
* **P4** — No rádio, a segunda comparação. Mesmos gestos.

**A armadilha.** "Não aconteceu nada" pelo cabo nunca é o selo — pelo cabo não existe selo. Se o P1 não obedecer, procure outra coisa: o serviço parado, a coluna vazia, o jogo escrevendo por cima. E o contrário também engana: um pulo no desenho vivo do P1 não prova que um byte chegou torto; pode ser a sua mão. O que faz o achado é o padrão — pulo nos dois do cabo e em nenhum dos dois do rádio. Sobre até onde a prova chegou: esta linha do mapa não tem degrau escrito. O que está medido é o ENVELOPE — em 06 de setembro os quatro controles foram lidos com o serviço parado, ninguém disputando o aparelho, e pelo cabo nenhum corte de quadro fecha com um selo: os quatro últimos bytes mudam a cada quadro, são carga e não soma de conferência. O degrau que faltava é o olho dela, e é o que os passos acima pedem.

---

## mapa-plataforma.crc32-radio — CRC-32 no envelope (integridade de report) · rádio

*Célula:* `plataforma.crc32 @ rádio`

**O que isto prova.** Prova que, pelo rádio, o que o Hefesto manda vai assinado direito — porque um pedido com a assinatura errada o controle joga fora em silêncio, sem uma palavra.

**Onde olhar.** No aparelho: a barra de luz do P3 e do P4 (as duas tiras que ladeiam o touchpad). Na tela: a linha "Cor" da coluna de cada controle, na aba Iluminação; o chip de cada controle na fita do topo, que traz o nome da cor do plástico e a borda pintada nessa cor — essa cor é uma resposta que veio do aparelho e, pelo rádio, veio assinada; e o cartão do controle na aba Controles, onde o pontinho do analógico anda com a sua mão. O selo em si não tem campo em tela nenhuma: a fonte não diz onde ele se leria.

**Os passos.**

1. Confira que P3 e P4 estão no rádio e P1 e P2 no cabo.
2. Abra a aba Iluminação.
3. Clique numa bolinha da linha "Cor" da coluna do P1 e confirme a cor na barra de luz dele — este é o controle de comparação, pelo cabo.
4. Clique numa cor bem diferente na linha "Cor" da coluna do P3.
5. Olhe a barra de luz do P3 no aparelho e confirme que ela acendeu nessa cor.
6. Clique numa terceira cor na mesma coluna do P3 e confirme que a barra dele trocou.
7. Repita os dois passos acima na coluna do P4.
8. Abra a aba Controles.
9. Leia o chip do P3 na fita do topo: ele tem de trazer o nome de uma cor de plástico e a borda pintada.
10. Pegue o P3 na mão e compare o plástico com o nome que está no chip.
11. Repita a leitura do chip com o P4.
12. Clique no chip "Todos" da fita para abrir os quatro cartões.
13. Mexa o analógico esquerdo do P3 em círculos, devagar, e olhe o pontinho do cartão dele acompanhar sem pular.
14. Repita no P4.
15. Anote qualquer coisa que a tela tenha dito que aplicou e que o plástico não tenha feito.

**Passa quando.** As barras de luz do P3 e do P4 acendem na cor escolhida e trocam quando você troca. Os chips deles trazem o nome da cor do plástico e a borda pintada, e o nome bate com o aparelho na sua mão. O pontinho do analógico segue a mão sem pulos. Nada disso chegaria com a assinatura errada — pelo rádio o controle descarta calado.

**Por controle.**

* **P1** — No cabo, e é a comparação obrigatória. Pinte uma cor NELE primeiro: se ele também não obedecer, o problema não é do rádio e o resto do teste não mede nada.
* **P2** — No cabo. Não toque nele. Serve de segunda comparação se o P1 der resultado estranho.
* **P3** — No rádio, e é ESTE que prova a ida (a cor que sai) e a volta (a cor do plástico que chega). Todos os gestos de cor são nele primeiro.
* **P4** — No rádio, e é o segundo. Confira nele as mesmas duas coisas. Se o P3 responder e o P4 não, o achado é daquele aparelho, e não do rádio.

**A armadilha.** O silêncio é a resposta padrão do erro aqui, e é isso que engana. Pelo rádio um pedido mal assinado é DESCARTADO pelo controle sem erro nenhum: a tela pode dizer que aplicou e o plástico não mudar. Foi assim que "a cor nunca funcionou pelo rádio" viveu meses nesta casa. Por isso o P1, no cabo, entra nos passos: se ele obedecer e os do rádio não, o achado é do rádio; se nenhum obedecer, é outra coisa. Segunda: o nome da cor do plástico pelo rádio está provado em DUAS unidades desta bancada, não nas quatro — se um terceiro controle vier sem cor, o achado é a assinatura daquele aparelho, e a tela devolve "não sei" em vez de inventar uma cor, que é o comportamento certo. E o degrau: esta linha do mapa não tem degrau escrito de propósito. O que foi medido em 06 de setembro foi a VOLTA — duzentos quadros de cada controle do rádio, todos conferindo, com a régua mordida de propósito (virando um bit de três bytes diferentes) para ver a conferência reprovar. A IDA é o que os seus dedos medem aqui.

---

## mapa-plataforma.declarado_sem_resposta-cabo — O que o descritor declara e o firmware NÃO entrega (EPIPE na leitura) · cabo

*Célula:* `plataforma.declarado_sem_resposta @ cabo`

**O que isto prova.** Prova que o buraco do cabo — dez coisas que o controle promete e recusa quando lhe perguntam — não chega à tela: tudo o que o Hefesto lê do aparelho pelo fio aparece preenchido.

**Onde olhar.** Na fita do topo, o chip de cada controle: o número, o nome da cor do plástico e a borda pintada com essa cor. Na aba Controles, dentro do quadro "Dispositivos Conectados", o cartão de cada controle: o desenho do modelo (pintado quando a leitura aconteceu, cinza quando não), a linha "Giroscópio", o número da bateria e o selo do Microfone. E, no alto desse quadro, o botão "Calibrar Sensores de Movimento". A recusa em si — o "não" que o controle devolve a dez perguntas quando está no fio — não aparece em tela nenhuma: a fonte não diz onde ela se leria, porque o produto nunca faz essas dez perguntas.

**Os passos.**

1. Confira que P1 e P2 estão no cabo e P3 e P4 no rádio.
2. Abra a aba Controles.
3. Leia o chip do P1 na fita do topo: ele tem de trazer um nome de cor de plástico e a borda pintada.
4. Pegue o P1 na mão e compare o plástico com o nome do chip.
5. Repita a leitura do chip com o P2, com o P3 e com o P4.
6. Clique no chip "Todos" da fita, para abrir os quatro cartões.
7. Confira, no cartão do P1, que o desenho do controle está pintado e não cinza.
8. Leia a linha "Giroscópio" do cartão do P1 e anote o que ela diz.
9. Leia o número da bateria e o selo do Microfone do cartão do P1.
10. Repita os três passos acima no P2, no P3 e no P4.
11. Clique em "Calibrar Sensores de Movimento", no alto do quadro "Dispositivos Conectados".
12. Siga o que a janela pedir, com os quatro controles parados numa superfície plana.
13. Volte à aba Controles e confira que a linha "Giroscópio" dos quatro continua dizendo que está fluindo.
14. Anote qualquer campo, de qualquer um dos quatro, que tenha vindo vazio, cinza ou com um travessão.

**Passa quando.** Os quatro trazem nome de cor e borda pintada, o desenho do modelo colorido, o giroscópio fluindo, a bateria com número e o microfone com selo. Nenhum campo do P1 e do P2 — os dois do cabo — vem mais vazio que o do P3 e o do P4.

**Por controle.**

* **P1** — No cabo, e é um dos dois que provam este lado. Todos os campos preenchidos: cor com nome e borda, desenho pintado, giroscópio fluindo, bateria com número, microfone com selo.
* **P2** — No cabo, o segundo. Mesma conferência. Se um campo faltar no P1 e no P2 e estiver cheio no P3 e no P4, o achado é do cabo — anote qual campo.
* **P3** — No rádio, e é comparação. Pelo rádio não há buraco nenhum: tudo o que o controle promete, ele entrega. Os campos dele são a régua contra a qual você lê os do cabo.
* **P4** — No rádio, a segunda comparação. Mesma conferência.

**A armadilha.** A cor de fábrica é lida por uma pergunta que o cabo ENTREGA — e a pergunta vizinha, de número quase igual, é uma das dez que ele RECUSA. Então, se a cor faltar num controle do cabo, não conclua "é o buraco do cabo": não é. As dez recusas são de LEITURA, o produto não faz nenhuma delas em lugar nenhum, e a que ele usa para a cor é uma das que respondem. E o degrau: esta linha parou em SAIU NO FIO — o byte saiu e o controle respondeu, com um "não" de um lado e com dado do outro, mas ninguém viu nada acender, girar nem soar. Os passos acima são exatamente o degrau que falta, e é o olho dela que o dá.

---

## mapa-plataforma.declarado_sem_resposta-radio — O que o descritor declara e o firmware NÃO entrega (EPIPE na leitura) · rádio

*Célula:* `plataforma.declarado_sem_resposta @ rádio`

**O que isto prova.** Prova que, pelo rádio, não falta nada: tudo o que o controle promete, ele entrega — e o que ele entrega vazio é resposta, não recusa.

**Onde olhar.** Na fita do topo, o chip de cada controle, com o número, o nome da cor do plástico e a borda pintada. Na aba Controles, dentro do quadro "Dispositivos Conectados", o cartão de cada controle: o desenho do modelo (cinza quando a leitura não aconteceu), a linha "Giroscópio", o número da bateria e o selo do Microfone, que diz ATIVO, MUDO ou traz um travessão. O travessão quer dizer "não consegui ler" e não é nenhum dos dois. E, no alto do quadro, o botão "Calibrar Sensores de Movimento".

**Os passos.**

1. Confira que P3 e P4 estão no rádio e P1 e P2 no cabo.
2. Abra a aba Controles.
3. Leia os quatro chips da fita do topo e anote, de cada um, se veio o nome da cor e se a borda está pintada.
4. Pegue o P3 na mão e compare o plástico com o nome do chip dele.
5. Faça o mesmo com o P4.
6. Clique no chip "Todos" da fita, para abrir os quatro cartões.
7. Leia, no cartão do P3, o desenho do modelo, a linha "Giroscópio", a bateria e o selo do Microfone — e anote os quatro.
8. Repita a leitura no cartão do P4.
9. Repita a leitura nos cartões do P1 e do P2, que estão no cabo.
10. Compare campo a campo: qualquer campo cheio nos do cabo e vazio nos do rádio é o achado.
11. Se algum campo do P3 tiver vindo vazio, encaixe um cabo nele, sem desligá-lo.
12. Leia o mesmo campo de novo e anote se ele encheu.
13. Puxe o cabo do P3 e confirme que ele volta ao rádio.

**Passa quando.** Os dois do rádio trazem exatamente os mesmos campos preenchidos que os dois do cabo: nome de cor e borda, desenho pintado, giroscópio fluindo, bateria com número e microfone com selo — ATIVO ou MUDO, nunca travessão. Nada falta do lado do rádio, e é isso que a linha afirma.

**Por controle.**

* **P1** — No cabo, e é comparação. Todos os campos anotados antes de você julgar o rádio: sem eles não há com o que comparar.
* **P2** — No cabo, segunda comparação.
* **P3** — No rádio, e é ESTE que prova o lado. Se um campo dele vier vazio, leve o mesmo aparelho para o cabo e olhe de novo: encheu no cabo é achado do rádio; ficou vazio nos dois é achado do aparelho.
* **P4** — No rádio, e é o segundo. A mesma leitura, e ela importa: dois aparelhos que respondem valem muito mais que um.

**A armadilha.** Voltar vazio e recusar são duas respostas diferentes, e o mapa guarda as duas. Pelo rádio há perguntas que respondem com tudo zero, e isso conta como resposta — na tela vira um campo sem valor, não um erro, e não é o buraco de que esta linha fala: buraco, pelo rádio, não existe. Segunda: a leitura da cor do plástico pelo rádio está provada em DUAS unidades desta bancada, não nas quatro; se um terceiro aparelho vier sem cor, o achado é dele e a tela mostra "não sei" em vez de inventar, que é o comportamento certo. E o degrau: esta linha parou em SAIU NO FIO — o byte saiu e o controle respondeu com dado, mas ninguém viu nada acender, girar nem soar. Os passos acima são o degrau seguinte, e quem o dá é o olho dela.

---

## mapa-plataforma.descritor_hid-cabo — Descritor HID — o que cada transporte DECLARA (cabo 289 B x rádio 320 B) · cabo

*Célula:* `plataforma.descritor_hid @ cabo`

**O que isto prova.** Prova que o que o controle oferece muda com o BRAÇO em que ele está, e não com o aparelho — e que pelo cabo ele entrega uma coisa que o rádio não tem: a placa de som do próprio controle.

**Onde olhar.** Na aba Conexões, quadro "Gestão de Controles": uma linha por controle ligado, com o número do jogador, o nome da cor do plástico e a palavra cabo ou rádio. Na mesma linha vem o campo Microfone, e é ele que muda com o transporte: pelo cabo ele diz "pelo cabo • Placa do controle"; pelo rádio diz "pelo rádio • Pela ponte". O quadro também traz a contagem, no formato "4 controles • 2 no cabo • 2 no rádio". O tamanho do que cada transporte declara não aparece em tela nenhuma: a fonte não diz onde ele se leria, porque não há campo.

**Os passos.**

1. Confira que P1 e P2 estão no cabo e P3 e P4 no rádio.
2. Confira que o controle do P1 já foi pareado por rádio nesta máquina alguma vez — sem isso ele não volta pelo PS e o teste não roda.
3. Abra a aba Conexões.
4. Leia as quatro linhas do quadro "Gestão de Controles" e anote, de cada uma, o nome da cor do plástico, a palavra cabo ou rádio e o que diz o campo Microfone.
5. Leia a contagem do quadro e anote.
6. Puxe o cabo de dentro do controle do P1.
7. Dê um toque no botão PS desse mesmo aparelho, sem demorar — do puxão até o toque tem de passar menos de trinta segundos.
8. Leia de novo a linha dele: o nome da cor do plástico tem de ser o mesmo, e a palavra tem de ter virado rádio.
9. Leia o campo Microfone dessa linha: ele tem de ter virado "pelo rádio • Pela ponte".
10. Encaixe o cabo de volta no mesmo aparelho.
11. Leia a linha mais uma vez: a palavra volta para cabo e o Microfone volta para "pelo cabo • Placa do controle".
12. Confira as linhas do P2, do P3 e do P4 e veja que nenhuma mudou durante a ida e a volta.
13. Leia a contagem do quadro de novo e compare com a que você anotou.

**Passa quando.** O mesmo aparelho, atravessando os dois braços, continua sendo o mesmo na tela: mesma cor de plástico, mesmo desenho, mesmo número de jogador. A única coisa que muda é o que depende do transporte — a palavra cabo ou rádio, e o caminho do microfone. Pelo cabo o som vem da placa do próprio controle; pelo rádio, pela ponte do Hefesto. As linhas dos outros três não se mexem.

**Por controle.**

* **P1** — É ESTE que atravessa: sai do cabo, volta pelo rádio com um toque no PS, e depois volta ao cabo. O que tem de mudar na linha dele são duas coisas e só duas: a palavra do transporte e o caminho do microfone.
* **P2** — No cabo, e não sai de lá. É a comparação parada: a linha dele tem de dizer "pelo cabo • Placa do controle" o tempo todo, do começo ao fim.
* **P3** — No rádio, testemunha. Não toque nele. A linha dele não pode piscar para fora do quadro enquanto o P1 atravessa, e ninguém pode tomar o número dele.
* **P4** — No rádio, segunda testemunha. Mesma conferência. É o último da fila e o primeiro a cair quando alguma coisa desmonta.

**A armadilha.** Três. (1) O relógio: o lugar de quem sai fica guardado por trinta segundos; se você demorar mais que isso entre puxar o cabo e tocar o PS, o P1 volta com outro número — e isso é a regra do produto funcionando, não defeito. (2) Não saia procurando na tela "o que o cabo declara": não há campo, e você vai procurar para sempre. A única diferença de transporte que esta tela mostra é o caminho do microfone. (3) Declarar não é entregar, e essa distinção é de outra linha: o cabo anuncia MAIS coisas que o rádio e entrega menos da metade delas. Ver isso aqui é impossível, e não é defeito desta tela. E o degrau: esta linha do mapa não tem degrau escrito. O que está medido é o que os dois braços DECLARAM, lido do sistema em 15 de agosto com os quatro aparelhos passando pelos dois braços — e o achado foi que a lista segue o BRAÇO, não a unidade: o mesmo aparelho anuncia uma coisa no fio e outra no ar.

---

## mapa-plataforma.descritor_hid-radio — Descritor HID — o que cada transporte DECLARA (cabo 289 B x rádio 320 B) · rádio

*Célula:* `plataforma.descritor_hid @ rádio`

**O que isto prova.** Prova que o rádio oferece um caminho próprio, que só existe enquanto o aparelho está no ar — e que ele some assim que o mesmo aparelho entra no fio.

**Onde olhar.** Na aba Conexões, em dois lugares. No quadro "Gestão de Controles": uma linha por controle, com o número do jogador, o nome da cor do plástico, a palavra cabo ou rádio, e o campo Microfone, que pelo rádio diz "pelo rádio • Pela ponte" e pelo cabo diz "pelo cabo • Placa do controle". E na seção "Desempenho · O rádio de cada adaptador, em turnos": uma pista por adaptador, com um bloco para cada controle que está naquele rádio e um bloco menor ao lado quando o microfone dele também vai por ali; uma pista sem ninguém mostra a frase "Nenhum controle neste rádio". O tamanho do caminho que cada transporte anuncia não aparece em tela nenhuma: a fonte não diz onde ele se leria, porque não há campo.

**Os passos.**

1. Confira que P3 e P4 estão no rádio e P1 e P2 no cabo.
2. Abra a aba Conexões.
3. Leia a seção "Desempenho" e anote quantas pistas há, e qual controle está em cada uma.
4. Leia as quatro linhas do quadro "Gestão de Controles" e anote o campo Microfone de cada uma.
5. Encaixe um cabo no controle do P3, sem desligá-lo.
6. Leia de novo a linha dele: a palavra tem de virar cabo e o Microfone tem de virar "pelo cabo • Placa do controle".
7. Volte à seção "Desempenho" e confira que o bloco do P3 saiu da pista do adaptador.
8. Confira que o bloco do P4 continua na pista dele, do mesmo tamanho.
9. Puxe o cabo do P3.
10. Confira que a linha dele volta a dizer rádio, e o Microfone volta a "pelo rádio • Pela ponte".
11. Volte à seção "Desempenho" e confira que o bloco do P3 voltou para a pista do adaptador.
12. Repita todos os passos acima com o P4.
13. Confira, no fim, que as linhas do P1 e do P2 não se mexeram uma vez sequer.

**Passa quando.** O mesmo aparelho continua sendo o mesmo na tela — cor de plástico, desenho, número de jogador —, e o que aparece e some junto com o rádio é o caminho de rádio dele: o bloco na pista do adaptador e o microfone pela ponte. Quando ele entra no fio, o bloco sai da pista e o microfone passa a vir da placa do próprio controle. Os dois do cabo não se mexem.

**Por controle.**

* **P1** — No cabo, testemunha. Não toque nele. A linha dele tem de dizer "pelo cabo • Placa do controle" do começo ao fim, e ele nunca pode aparecer numa pista da seção "Desempenho".
* **P2** — No cabo, segunda testemunha. Mesma conferência.
* **P3** — No rádio, e é ESTE que atravessa primeiro. Entra no fio, sai do fio. O que tem de aparecer e sumir com ele é o bloco na pista do adaptador e o microfone pela ponte.
* **P4** — No rádio, e é o segundo a atravessar. Enquanto o P3 está no fio, é ele quem prova que a pista do adaptador continua viva com um só: o bloco dele não pode mudar de tamanho por causa do vizinho.

**A armadilha.** Duas, e as duas são de leitura. (1) Encaixar o cabo num controle que está no rádio não o desliga do rádio na mesma hora, e por um instante a tela pode mostrar as duas coisas; espere a linha assentar antes de anotar. (2) Os números de turno da seção "Desempenho" são conta, não medição do momento: eles vêm de um ensaio de bancada com UM controle, e a soma de quatro é derivada. Não vale reprovar a tela porque o número não bateu com uma conta sua — o que este teste lê ali é a PRESENÇA e a AUSÊNCIA do bloco, não o valor dele. E o degrau: esta linha do mapa não tem degrau escrito. O que está medido é o que cada braço declara, lido em 15 de agosto com os quatro aparelhos passando pelos dois lados: o que só o rádio anuncia continuou sendo só do rádio, com os aparelhos trocados de braço. A lista segue o braço, não a unidade.

---

## mapa-plataforma.diagnostico_morte_radio-cabo — Diagnóstico da morte por rádio (doctor) · cabo

*Célula:* `plataforma.diagnostico_morte_radio @ cabo`

**O que isto prova.** Prova que o produto não inventa diagnóstico de rádio para um controle que está no cabo — e que, quando um controle do cabo cai, o que ela vê é a queda dita com todas as letras.

**Onde olhar.** A contagem no alto de qualquer aba, no formato "● 4 controles: 2 USB · 2 BT". A fita do topo, com um chip por controle. Na aba Controles, o quadro "Dispositivos Conectados", onde o lugar de um controle que saiu passa a dizer "Desconectado". E na aba Sistema, a faixa "O exame de hoje", com a conta ao lado dela ("8 linhas · nenhum aviso") e uma linha por achado, cada uma com um selo e um "?" que diz o que foi visto, por que importa e o que fazer.

**Os passos.**

1. Confira que os quatro estão ligados: P1 e P2 no cabo, P3 e P4 no rádio.
2. Abra a aba Sistema e leia a conta ao lado de "O exame de hoje": anote quantas linhas e quantos avisos.
3. Leia as linhas do exame, uma a uma, e anote o que cada uma diz.
4. Puxe o cabo de dentro do controle do P1.
5. Leia a contagem no alto da aba: ela tem de cair para três controles, com um no cabo.
6. Abra a aba Controles e confira que o lugar do P1 diz "Desconectado".
7. Confira que nenhum dos outros três se mudou para o lugar do P1.
8. Volte à aba Sistema e leia o exame de novo.
9. Confira que nenhuma linha nova nasceu falando de rádio, de Bluetooth ou de controle sumido.
10. Encaixe o cabo de volta no P1.
11. Confira que a contagem volta a quatro e que o P1 volta ao lugar dele.
12. Repita os passos 4 a 11 com o P2.

**Passa quando.** Puxar o cabo de um controle aparece como o que é — a queda de um controle do CABO: a contagem cai, o lugar dele diz "Desconectado" e ninguém toma esse lugar. O exame da aba Sistema não ganha nem perde linha por causa disso, e não diz uma palavra sobre rádio. O P3 e o P4 ficam onde estavam.

**Por controle.**

* **P1** — No cabo, e é o primeiro a cair. Puxe o cabo dele, leia as três telas, e devolva o cabo antes de passar ao P2.
* **P2** — No cabo, e é o segundo a cair. Um de cada vez: dois fora ao mesmo tempo esconde quem tomou o lugar de quem.
* **P3** — No rádio, testemunha. Não toque nele. O chip dele não pode sumir da fita, o número não pode mudar, e ele não pode se mudar para o lugar do que caiu.
* **P4** — No rádio, segunda testemunha. Mesma conferência. É o último da fila e o mais propenso a se mexer quando alguma coisa desmonta.

**A armadilha.** Esta célula do mapa é uma AUSÊNCIA declarada: o diagnóstico de que ela fala é o da morte por RÁDIO, e pelo cabo não há o que diagnosticar por esse caminho. Mas a razão desse "não" está registrada como NÃO MEDIDA — ninguém foi ver se existe uma morte de cabo que mereça diagnóstico próprio. Então, se durante este teste um controle do cabo sumir sem você puxar nada, isso é achado e vale anotar com a hora. E não confunda o exame da aba Sistema com diagnóstico de rádio: aquele exame é da MÁQUINA — som, Steam Input, regras de permissão —, ele nunca falou de rádio, e não falar não é falha dele. O que reprovaria aqui é o contrário: uma linha nova aparecendo, por causa de um cabo puxado, a falar de rádio.

---

## mapa-plataforma.diagnostico_morte_radio-radio — Diagnóstico da morte por rádio (doctor) · rádio

*Célula:* `plataforma.diagnostico_morte_radio @ rádio`

**O que isto prova.** Prova o que a tela dela diz quando um controle do rádio sai — e o que ela NÃO diz quando ele morre de verdade, que é o achado desta linha.

**Onde olhar.** Quatro lugares. A contagem no alto de qualquer aba ("● 4 controles: 2 USB · 2 BT"). A fita do topo, com um chip por controle. Na aba Controles, o quadro "Dispositivos Conectados", onde o lugar de quem saiu passa a dizer "Desconectado". E na aba Conexões, a seção "Desempenho · O rádio de cada adaptador, em turnos", onde cada adaptador tem uma pista com um bloco por controle, e uma pista sem ninguém mostra "Nenhum controle neste rádio". O diagnóstico da morte por rádio — o aviso de que o controle está pareado, o computador o dá por conectado e mesmo assim ele não existe para o sistema — não aparece em aba nenhuma: a fonte diz que ele mora fora do produto, numa ferramenta da casa, e não na tela.

**Os passos.**

1. Confira que P3 e P4 estão no rádio e P1 e P2 no cabo.
2. Abra a aba Conexões e leia a seção "Desempenho": anote quantas pistas há e qual controle está em cada uma.
3. Abra a aba Sistema e leia a conta ao lado de "O exame de hoje": anote quantas linhas e quantos avisos.
4. Segure o botão PS do P3 até todas as luzes dele apagarem, e solte.
5. Leia a contagem no alto da aba: tem de cair para três controles, com um no rádio.
6. Abra a aba Controles e confira que o lugar do P3 diz "Desconectado".
7. Confira que nenhum dos outros três se mudou para o lugar dele.
8. Volte à aba Conexões e confira que o bloco do P3 saiu da pista do adaptador.
9. Confira que o bloco do P4 continua na pista, do mesmo tamanho.
10. Volte à aba Sistema e leia o exame de novo: anote se alguma linha nova nasceu.
11. Segure o botão PS do P3 por cerca de cinco segundos, até a barra de luz dele acender, e ponha-o na mesa.
12. Confira que ele volta ao lugar dele, com o mesmo número, e que a contagem volta a quatro.
13. Repita os passos 4 a 12 com o P4.

**Passa quando.** Desligar um do rádio aparece como três coisas ao mesmo tempo, em três abas: a contagem cai, o lugar dele diz "Desconectado", e o bloco dele sai da pista do adaptador na aba Conexões. Os outros três não se mexem e ninguém toma o lugar vago. E o exame da aba Sistema continua com as mesmas linhas de antes — ele não fala de rádio, e é honesto que não fale.

**Por controle.**

* **P1** — No cabo, testemunha. Não toque nele. Número, cor e lugar iguais antes e depois. Ele nunca aparece numa pista da seção "Desempenho".
* **P2** — No cabo, segunda testemunha. Mesma conferência.
* **P3** — No rádio, e é ESTE que sai primeiro. Segure o PS até todas as luzes apagarem — nem antes nem depois — e depois religue-o pelo PS.
* **P4** — No rádio, e é o vizinho de rádio de quem caiu: é nele que a bagunça costuma aparecer primeiro. Confira que o bloco dele continua na pista e que ele não se mudou para o lugar do P3. Depois é a vez dele de sair.

**A armadilha.** Este teste NÃO alcança a morte de que a linha fala, e é preciso dizer. A morte por rádio é outra coisa: o controle está pareado, o computador o dá por conectado, e mesmo assim ele não existe para o sistema — nasce órfão. Isso não se provoca com o botão PS. Quem o detecta hoje é uma ferramenta da casa que não está na tela: nenhuma aba avisa, nenhuma frase nasce. O que os passos acima medem é o degrau de baixo — o desligamento limpo, que a tela conta certo em três lugares. Se um dia o P3 estiver pareado, o computador disser que ele está conectado e mesmo assim ele não aparecer no Hefesto, ISSO é a morte por rádio: anote a hora e não procure a frase, porque ela não existe. Segunda armadilha: soltar o botão PS cedo demais não desliga o controle, e com cerca de cinco segundos de aperto o Hefesto lê aquilo como um toque e abre a Steam — se ela abrir, feche-a e refaça o passo. Terceira: não conte o exame da aba Sistema como diagnóstico de rádio; ele é da máquina.

---

## mapa-plataforma.distinguir_clone-cabo — Distinguir o genuíno do clone · cabo

*Célula:* `plataforma.distinguir_clone @ cabo`

**O que isto prova.** Prova que o Hefesto arranca de cada controle do cabo uma resposta que o clone medido nesta casa não sabe dar: o nome da cor do plástico de fábrica.

**Onde olhar.** Na fita do topo, o chip de cada controle: o número, o nome da cor do plástico e a borda pintada nessa cor. Na aba Conexões, quadro "Gestão de Controles", a mesma leitura aparece como uma barra fina de cor na aresta esquerda da linha de cada controle; quando o Hefesto não conseguiu ler a cor, a barra fica neutra e o desenho do controle fica cinza — e está dito no "?" do quadro e ao passar o ponteiro na linha. Não existe em tela nenhuma um campo que diga "genuíno" ou "clone": a fonte não diz onde ele se leria, porque o produto não faz verificação de autenticidade.

**Os passos.**

1. Confira que P1 e P2 estão no cabo e P3 e P4 no rádio.
2. Abra a aba Controles.
3. Leia o chip do P1 na fita do topo e anote o nome da cor.
4. Pegue o P1 na mão e compare o plástico com o nome anotado.
5. Repita a leitura e a comparação com o P2.
6. Repita com o P3 e com o P4.
7. Abra a aba Conexões.
8. Confira, nas quatro linhas do quadro "Gestão de Controles", que a barra da aresta esquerda está pintada e não neutra.
9. Passe o ponteiro sobre a linha de qualquer controle cuja barra esteja neutra e leia o que o produto diz.
10. Anote qual controle, se algum, ficou sem nome de cor e sem borda.
11. Puxe o cabo do P1, dê um toque no PS para trazê-lo pelo rádio e leia o chip dele de novo.
12. Encaixe o cabo de volta e confirme que a cor continua lá.

**Passa quando.** Os dois do cabo trazem nome de cor e borda pintada, e o nome bate com o plástico na sua mão. Um controle que não devolve essa resposta é o achado — e o produto o mostra como cor não lida, com borda neutra e desenho cinza, em vez de inventar uma cor.

**Por controle.**

* **P1** — No cabo, e é ESTE que responde primeiro. Nome da cor no chip, borda pintada, e o plástico na sua mão batendo com os dois. É também ele que atravessa para o rádio no fim, para você ver a mesma resposta chegando pelos dois braços.
* **P2** — No cabo, o segundo. Mesma conferência. Dois aparelhos respondendo valem muito mais que um.
* **P3** — No rádio, e é comparação. Pelo rádio essa resposta chega assinada, e o próprio sistema recusa uma assinatura errada — quem passou por ali já acertou duas contas antes de a cor aparecer.
* **P4** — No rádio, a segunda comparação. Se um dos dois do rádio vier sem cor e o outro vier com, o achado é do aparelho, não do transporte.

**A armadilha.** Isto não é anti-clone, e dizer que é seria mentira. O Hefesto aceita qualquer aparelho que se apresente com o número de fábrica certo: não há desafio, não há senha, não há como um programa desta casa conferir a assinatura da Sony. O que este teste mede é uma resposta A MAIS, que o clone medido nesta casa não dá — o firmware dele responde três perguntas e mais nada, e a da cor é a quarta. Um clone melhor copia a resposta e passa igual. Segunda: a cor sumir NÃO é prova de clone; pode ser um aparelho cuja assinatura de cor esta casa ainda não conhece, e nesse caso a tela devolve "não sei", que é o certo. Terceira: nenhum degrau foi escrito nesta linha do mapa. Ela foi preenchida lendo o firmware de um clone real e o que os aparelhos declaram, sem uma única escrita nos controles dela — o que você fizer aqui é a primeira vez que um par de mãos a mede.

---

## mapa-plataforma.distinguir_clone-radio — Distinguir o genuíno do clone · rádio

*Célula:* `plataforma.distinguir_clone @ rádio`

**O que isto prova.** Prova que, pelo rádio, o controle tem de acertar mais contas antes de aparecer na tela — e que a resposta que denuncia o clone medido chega assim mesmo.

**Onde olhar.** Na fita do topo, o chip do P3 e o do P4: o número, o nome da cor do plástico e a borda pintada nessa cor. Na aba Conexões, quadro "Gestão de Controles", a barra fina de cor na aresta esquerda da linha de cada controle; barra neutra e desenho cinza querem dizer que a cor não foi lida, e o "?" do quadro explica isso. Não existe em tela nenhuma um campo que diga "genuíno" ou "clone": a fonte não diz onde ele se leria, porque o produto não faz verificação de autenticidade.

**Os passos.**

1. Confira que P3 e P4 estão no rádio e P1 e P2 no cabo.
2. Abra a aba Controles.
3. Leia o chip do P3 na fita do topo e anote o nome da cor.
4. Pegue o P3 na mão e compare o plástico com o nome anotado.
5. Repita a leitura e a comparação com o P4.
6. Leia os chips do P1 e do P2, que estão no cabo, e anote as cores deles também.
7. Abra a aba Conexões e confira, nas quatro linhas do quadro "Gestão de Controles", quais barras estão pintadas e quais estão neutras.
8. Passe o ponteiro sobre a linha de qualquer controle de barra neutra e leia o que o produto diz.
9. Se o P3 tiver vindo sem cor, encaixe um cabo nele, sem desligá-lo, e leia o chip de novo.
10. Puxe o cabo do P3 e confira o que acontece com a cor quando ele volta ao rádio.
11. Repita os dois passos acima com o P4, se ele também tiver vindo sem cor.
12. Anote, no fim, quantos dos quatro devolveram a cor e por qual braço.

**Passa quando.** Os dois do rádio trazem nome de cor e borda pintada, e o nome bate com o plástico na sua mão. Pelo rádio essa resposta só chega assinada, e uma assinatura errada é recusada antes de virar tinta — então cor na tela, pelo rádio, quer dizer que o aparelho acertou duas contas além do conteúdo.

**Por controle.**

* **P1** — No cabo, comparação. Anote a cor dele antes de julgar o rádio: se nem no cabo aparecer cor, o problema não é do rádio.
* **P2** — No cabo, segunda comparação.
* **P3** — No rádio, e é ESTE que responde primeiro. Se ele vier sem cor, leve o mesmo aparelho ao cabo e olhe de novo — apareceu no cabo e não no rádio, o achado é do rádio; não apareceu nos dois, o achado é do aparelho.
* **P4** — No rádio, e é ele que fecha a amostra: a leitura da cor pelo rádio está provada em DUAS unidades desta bancada, não nas quatro. Se ele responder, a conta fecha; se recusar, anote o modelo dele, porque o achado é a assinatura daquele aparelho.

**A armadilha.** A barra que o rádio impõe é mais alta e continua copiável: o selo tem semente conhecida, e qualquer clone que leia a mesma tabela o acerta. Nada aqui prova autenticidade — prova só que o aparelho deu uma resposta a mais que o clone medido não dá. Segunda, e é a que faz julgar errado: a cor pelo rádio está provada em duas unidades, então um terceiro controle sem cor NÃO é veredito sobre o transporte; é achado daquele aparelho, e a tela devolve "não sei" em vez de inventar, que é o certo. Antes de concluir qualquer coisa, faça o mesmo aparelho atravessar para o cabo e olhe de novo. Terceira: nenhum degrau foi escrito nesta linha do mapa — ela nasceu de leitura de firmware de clone e do que os aparelhos declaram, sem uma escrita sequer nos controles dela.

---

## mapa-plataforma.escada_de_output-cabo — Escada de reports de OUTPUT por rádio — 0x31 a 0x39, de 64 em 64 bytes · cabo

*Célula:* `plataforma.escada_de_output @ cabo`

**O que isto prova.** Prova que, pelo cabo, tudo o que o Hefesto manda cabe num caminho de saída só, curto — e que a pergunta "e se coubesse mais?" nunca foi feita a nenhum controle no fio.

**Onde olhar.** No aparelho: a barra de luz (as duas tiras que ladeiam o touchpad), o tremor na sua mão e a resistência do L2 e do R2. Na tela: a linha "Cor" da coluna de cada controle, na aba Iluminação; o botão "Testar" da linha "Testar agora", na aba Vibração; e o campo "Modo" das linhas "Gatilho esquerdo" e "Gatilho direito", na aba Gatilhos. O tamanho do caminho de saída não aparece em tela nenhuma: a fonte não diz onde ele se leria, porque não há campo — e nenhum botão desta interface pede um caminho maior pelo cabo.

**Os passos.**

1. Confira que P1 e P2 estão no cabo e P3 e P4 no rádio.
2. Abra a aba Iluminação e clique numa bolinha da linha "Cor" da coluna do P1.
3. Olhe a barra de luz do P1 no aparelho e confirme a cor.
4. Abra a aba Vibração, segure o P1 na mão e clique em "Testar" na coluna dele.
5. Sinta o meio segundo de tremor nos dois punhos.
6. Abra a aba Gatilhos e escolha "Rígido" no campo "Modo" da linha "Gatilho esquerdo", na coluna do P1.
7. Aperte o L2 do P1 e sinta se ele travou duro do começo ao fim do curso.
8. Escolha "Rígido" também no "Gatilho direito" do P1 e aperte o R2.
9. Repita os passos 2 a 8 no P2.
10. Volte à aba Iluminação e confira que a barra de luz do P1 continua na cor que você pôs.
11. Escolha "Desligado" nos dois gatilhos do P1 e do P2, para desfazer.
12. Aperte o L2 e o R2 dos dois e confirme que voltaram a ficar leves.

**Passa quando.** Cor, tremor e gatilho chegam aos dois controles do cabo, e as três coisas viajam pelo mesmo caminho único e curto que o cabo oferece. Não há nada a mais para ver aqui, e é exatamente isso que esta linha do mapa afirma.

**Por controle.**

* **P1** — No cabo, e é ESTE que prova o caminho: cor na barra de luz, tremor na mão, L2 e R2 travando. Devolva "Desligado" nos gatilhos no fim.
* **P2** — No cabo, o segundo. Os mesmos três gestos. Dois aparelhos fazem a prova valer mais que um.
* **P3** — No rádio, comparação. Não é preciso mexer nele: ele está aqui para lembrar que pelo rádio essas mesmas três coisas viajam por um caminho que tem nove tamanhos, e pelo cabo só um.
* **P4** — No rádio, segunda comparação. Não toque nele.

**A armadilha.** A pergunta desta linha não é respondível daqui, e o mapa é honesto sobre isso: pelo rádio o controle oferece NOVE caminhos de saída, de tamanhos crescentes; pelo cabo ele oferece um só. Se algum dos caminhos grandes funcionaria pelo fio, NINGUÉM TENTOU — a célula do mapa diz "desconhecido" e não "não", de propósito. Nenhum botão desta tela manda um caminho grande pelo cabo, e não é para ela tentar isso com as mãos. Segunda: não declarar não é recusar — o cabo não anuncia esses caminhos, e isso não prova que ele os jogaria fora. Terceira: se o gatilho não travar, não conclua nada sobre o caminho; a tela mostra o que foi PEDIDO, e um jogo aberto pode estar escrevendo por cima. E o degrau: esta linha do mapa não tem degrau escrito.

---

## mapa-plataforma.escada_de_output-radio — Escada de reports de OUTPUT por rádio — 0x31 a 0x39, de 64 em 64 bytes · rádio

*Célula:* `plataforma.escada_de_output @ rádio`

**O que isto prova.** Prova que o caminho de saída que o Hefesto sabe montar chega ao controle pelo rádio nos DOIS aparelhos do ar — que é exatamente a amostra que faltava.

**Onde olhar.** No aparelho: a barra de luz do P3 e a do P4 (as duas tiras que ladeiam o touchpad). Na tela, na aba Iluminação: cada controle tem uma coluna com a etiqueta dele no alto; a linha "Cor" traz oito bolinhas e a linha "Opções" traz os botões "Automático" e "Desligar". A linha "LEDs" mostra a cor que o Hefesto PEDIU, não a que está acesa — e embaixo dela pode nascer uma ressalva quando ele não tem certeza. Os caminhos maiores de saída não têm botão em tela nenhuma: a fonte não diz onde se pediria um, porque o produto só sabe montar o menor.

**Os passos.**

1. Confira que P3 e P4 estão no rádio e P1 e P2 no cabo.
2. Abra a aba Iluminação.
3. Leia a etiqueta no alto das quatro colunas e confirme quem está por cabo e quem está por rádio.
4. Clique numa bolinha da linha "Cor" da coluna do P1 e confirme a cor na barra de luz dele — este é o controle de comparação, pelo cabo.
5. Clique numa cor bem diferente na linha "Cor" da coluna do P3.
6. Olhe a barra de luz do P3 no aparelho e confirme que ela acendeu nessa cor.
7. Clique numa terceira cor na mesma coluna do P3 e confirme que a barra dele trocou.
8. Clique em "Desligar" na linha "Opções" da coluna do P3 e confirme que a barra dele apaga.
9. Clique numa cor de novo na coluna do P3 e confirme que ela volta a acender.
10. Repita os passos 5 a 9 na coluna do P4.
11. Olhe os quatro controles juntos: quatro barras acesas, quatro cores diferentes.
12. Clique em "Automático" na linha "Opções" das colunas do P3 e do P4, para desfazer.
13. Anote o modelo de cada um dos dois do rádio ao lado do resultado.

**Passa quando.** A barra de luz do P3 e a do P4 obedecem à cor escolhida, trocam quando você troca, apagam no "Desligar" e voltam quando você pinta de novo. As duas são do rádio, e é nas DUAS que a prova precisava existir: até hoje ela existia num aparelho só.

**Por controle.**

* **P1** — No cabo, e é a comparação. Pinte uma cor NELE primeiro: se ele também não obedecer, o achado não é do rádio e o resto do teste não mede nada.
* **P2** — No cabo. Não toque nele.
* **P3** — No rádio, e é ESTE que repete o que já foi visto: um aparelho como ele obedeceu com o olho dela em 15 de agosto.
* **P4** — No rádio, e é o que INTERESSA MAIS. A obediência pelo rádio está vista em UMA unidade só; este é o segundo aparelho. Se ele obedecer, a amostra fecha; se não, o achado é dele — anote o modelo.

**A armadilha.** A tela não é a prova. A linha "LEDs" mostra a cor que o Hefesto PEDIU, e pelo rádio um pedido mal montado é jogado fora pelo controle sem uma palavra: a tela pode dizer que pediu e o plástico não mudar. Quem responde é a faixa acesa no plástico. Segunda: não mexa no interruptor "Cores automáticas por controle", no alto da aba — ele é do perfil e vale para os quatro de uma vez, e este teste é sobre a coluna de cada um. Terceira, e é sobre o alcance: os caminhos GRANDES de saída não têm botão nesta tela. Dois deles já obedeceram, com o olho dela, em 15 de agosto, num aparelho branco — mas o Hefesto de hoje só sabe carimbar o menor; um grande sairia sem selo e o controle o jogaria fora enquanto o registro diria "escrito". Não procure por eles aqui. E o degrau: esta linha do mapa está com o degrau VAZIO de propósito — a obediência foi vista, mas o caderno de bancada ainda não tem o ensaio que a registra. O que você fizer aqui é o que vai preenchê-lo.

---

## mapa-plataforma.escrita_crua-cabo — Escrita crua por hidraw (qualquer subcomando) · cabo

*Célula:* `plataforma.escrita_crua @ cabo`

**O que isto prova.** Prova que o comando que o Hefesto escreve direto no aparelho também sai pelos dois controles do cabo, e que eles continuam obedecendo à cor depois disso.

**Onde olhar.** Na aba Iluminação. Cada controle tem uma coluna, com a etiqueta dele no alto — o número, a cor do plástico e por onde ele está ligado. As linhas são nomeadas na coluna da esquerda: Controle, Modelo, Cor, Brilho, Jogador, LEDs e Opções. A linha Cor tem os oito quadradinhos de cor, com o código da cor escrito logo abaixo deles; a linha Opções tem os botões «Automático» e «Desligar». Mas a resposta não é a tela: é a barra de luz no plástico, as duas tiras acesas dos dois lados do touchpad. Se o comando não chegar ao serviço, uma frase de recusa aparece na própria coluna. Não existe na tela nenhum campo que diga «o comando cru saiu» — a fonte não diz onde se leria isso, porque não há onde.

**Os passos.**

1. Confira na fita do topo que o P1 e o P2 dizem cabo.
2. Feche a Steam e qualquer jogo aberto.
3. Abra a aba Iluminação.
4. Olhe as barras de luz dos quatro aparelhos e anote a cor de cada uma.
5. Clique, na linha Cor da coluna do P1, num quadradinho de cor bem diferente da que ele tem agora.
6. Confirme que a barra do P1 acendeu nessa cor.
7. Clique em «Automático», na linha Opções da coluna do P1.
8. Olhe a barra do P1 no aparelho: ela tem de passar para a cor do número dele, que é o azul.
9. Confira que nenhuma frase de recusa apareceu na coluna do P1.
10. Olhe as barras do P3 e do P4: nenhuma pode ter mudado.
11. Clique de novo num quadradinho de cor na coluna do P1 e confirme que a barra ainda obedece.
12. Repita os passos 5 a 11 na coluna do P2, cuja cor de número é o vermelho.
13. Anote qualquer coisa estranha que o P1 ou o P2 fizer logo depois do «Automático» — piscada, apagão, cor errada, ou um instante de barra morta.

**Passa quando.** Nos dois controles do cabo, o «Automático» troca a barra para a cor do número sem nenhuma frase de recusa na coluna, e logo depois o mesmo controle ainda obedece a um clique de cor novo. As barras do P3 e do P4 não mudam em nenhum dos dois momentos.

**Por controle.**

* **P1** — Cabo, e é um dos dois que recebem o comando. Ponha uma cor à mão, clique em «Automático» e veja a barra ir para o azul do número 1. Depois clique numa cor de novo: ele tem de continuar obedecendo.
* **P2** — Cabo, o segundo que recebe. Mesmo gesto, e a cor do número 2 é o vermelho. Se um dos dois do cabo se comportar diferente do outro, o achado é daquele aparelho e não do transporte — anote qual.
* **P3** — Rádio, testemunha. Não toque na coluna dele. A barra dele não pode mudar quando você mexe no P1 nem no P2.
* **P4** — Rádio, testemunha. Mesma coisa. Se a cor que você pôs no P1 aparecer nele, o comando pegou o transporte inteiro em vez do controle escolhido, e isso é o achado.

**A armadilha.** Este teste prova menos do que parece, e dizer isso é metade do valor dele. O que já está medido é que a escrita SAI e que o sistema a aceita — nunca que o aparelho a executou. O canal por onde ela sai é cru: não confere nada, e por isso ela sai igual pelo cabo, onde o controle nem declara esperar esse comando. Um verde aqui diz «o Hefesto mandou e ninguém reclamou», e é exatamente por isso que o passo 11 existe: o único degrau que a sua mão consegue provar é que o controle continua obedecendo depois. Mais duas: não use o interruptor «Cores automáticas por controle», no alto da aba — ele é do perfil e vale para os quatro de uma vez, e este teste é sobre a coluna de um; e o «Automático» LARGA a barra daquele controle para o jogo escolher, então com a Steam ou um jogo abertos a cor pode mudar sozinha depois, e você anotaria como defeito o que é outro programa escrevendo por cima.

---

## mapa-plataforma.escrita_crua-radio — Escrita crua por hidraw (qualquer subcomando) · rádio

*Célula:* `plataforma.escrita_crua @ rádio`

**O que isto prova.** Prova que os dois comandos que o Hefesto escreve direto no aparelho saem pelos dois controles do rádio — o que solta a barra de luz e o que faz o microfone chegar pela ponte.

**Onde olhar.** Dois lugares. Na aba Conexões, no quadro Gestão de Controles, a linha de cada controle diz por onde o microfone dele chega: nos do rádio tem de estar escrito «pelo rádio • Pela ponte», e nos do cabo «pelo cabo • Placa do controle» — a ponte é o caminho cru que só existe no rádio. Na aba Controles, abrindo o cartão de um controle, a linha Microfone traz uma barrinha que mexe com o som que está entrando agora, e é ela que mostra a ponte de pé. E na aba Iluminação, a coluna do P3 e a do P4: a linha Cor com os oito quadradinhos e a linha Opções com «Automático» e «Desligar» — mas quem responde é a barra de luz no plástico, as duas tiras dos lados do touchpad.

**Os passos.**

1. Abra a aba Conexões.
2. Confira na fita do topo que o P3 e o P4 dizem rádio.
3. Leia, no quadro Gestão de Controles, o que a linha do P3 e a do P4 dizem sobre o microfone: tem de estar escrito pelo rádio, e Pela ponte.
4. Leia a mesma coisa nas linhas do P1 e do P2: nelas tem de estar escrito pelo cabo, e Placa do controle.
5. Abra a aba Controles.
6. Clique na linha do P3 para abrir o cartão dele e fale perto dele; depois faça o mesmo na linha do P4.
7. Confira que a barrinha da linha Microfone mexe nos dois, cada uma enquanto você fala perto do seu controle.
8. Abra a aba Iluminação.
9. Repare a cor da barra de luz dos quatro aparelhos, antes de mexer em qualquer coisa.
10. Clique num quadradinho de cor bem diferente na linha Cor da coluna do P3.
11. Confira que a barra do P3 acendeu nessa cor.
12. Clique em «Automático», na linha Opções da coluna do P3.
13. Confira que a barra do P3 passou para a cor do número 3, que é o verde.
14. Confira que nenhuma frase de recusa apareceu na coluna do P3.
15. Confira que as barras do P1 e do P2 não mudaram.
16. Clique de novo num quadradinho de cor na coluna do P3.
17. Confira que ele ainda obedece ao clique.
18. Refaça na coluna do P4 os três cliques que você fez na do P3 — cor à mão, «Automático», e cor à mão de novo —, lembrando que a cor de número dele é o rosa.

**Passa quando.** Os dois do rádio dizem, na aba Conexões, que o microfone deles chega pela ponte, e a barrinha do cartão de cada um mexe quando você fala perto dele. Na aba Iluminação, o «Automático» troca a barra dos dois para a cor do número, sem frase de recusa, e o controle continua obedecendo ao clique de cor seguinte. Nada disso acontece no P1 nem no P2: as linhas deles continuam dizendo que o microfone vem pela placa do próprio controle, e as barras de luz deles não mudam.

**Por controle.**

* **P1** — Cabo, testemunha — e é ela que prova a divisão. A linha dele tem de dizer que o microfone vem pelo cabo, pela placa do próprio controle. Se disser «Pela ponte», o caminho que devia ser só do rádio vazou para o cabo, e esse é o achado.
* **P2** — Cabo, a segunda testemunha. Mesma leitura da linha, e a barra de luz dele não pode mudar quando você mexe nos do rádio.
* **P3** — Rádio, é um dos dois que recebem. Fale perto dele e veja a barrinha mexer; depois ponha uma cor à mão e clique em «Automático» na coluna dele.
* **P4** — Rádio, o segundo que recebe. Mesmos gestos. Se um dos dois do rádio responder e o outro não, o achado é daquele aparelho ou da distância dele até o adaptador, não do transporte — anote qual.

**A armadilha.** NÃO CLIQUE no botão de microfone da tela, o desenho de microfone que fica dentro do cartão: ele passa o comando do mudo para o Hefesto, o botãozinho do plástico para de valer, e esta tela não devolve — a volta é reiniciar o Hefesto. Falar perto do controle e olhar a barrinha é seguro; clicar não é. E vale aqui a mesma medida do lado do cabo: o que está provado é que a escrita SAI e que o sistema a aceita, nunca que o aparelho a executou — o que a sua mão prova é o degrau seguinte, que é o controle continuar obedecendo depois. Por fim, o «Automático» larga a barra para o jogo escolher: com um jogo ou a Steam abertos a cor pode voltar atrás sozinha, e isso não é o comando falhando — por isso a cerimônia manda fechar os dois antes de começar.

---

## mapa-plataforma.feature_f6-cabo — FEATURE 0xF6 (547 B) — existe só no rádio, lê VAZIO, função desconhecida · cabo

*Célula:* `plataforma.feature_f6 @ cabo`

**O que isto prova.** Prova que o Hefesto não promete nada sobre um bloco de dados escondido do controle que, no cabo, nem chega a existir.

**Onde olhar.** A fonte não diz onde se lê este valor na tela — e não diz porque não há onde: o produto não lê nem escreve esse bloco em lugar nenhum, e nenhuma aba tem campo para ele. O que se olha é onde ele apareceria se alguém o tivesse ligado. Primeiro, a aba Controles: clicando na linha de um controle o cartão abre com as linhas Microfone, Bateria, Touchpad, Barra de luz, LED do jogador, os dois analógicos, os Gatilhos e os blocos Giroscópio e Acelerômetro. Segundo, a aba Sistema, na faixa Avançado: o painel Detalhes técnicos, ao lado dos botões, é a saída crua do Hefesto e se preenche sozinho; o botão «Ver detalhes», acima dele, troca o painel pelas últimas linhas do registro.

**Os passos.**

1. Confira na fita do topo que o P1 e o P2 dizem cabo.
2. Abra a aba Controles.
3. Clique na linha do P1 para abrir o cartão dele.
4. Leia todos os campos do cartão, um a um, e anote se algum traz um valor que a tela não explica de onde veio.
5. Clique na linha do P2 e faça a mesma leitura no cartão dele.
6. Abra a aba Sistema.
7. Desça até a faixa Avançado.
8. Leia o painel Detalhes técnicos, ao lado dos botões, rolando-o de cima a baixo.
9. Clique em «Ver detalhes» e leia as linhas que aparecem.
10. Procure alguma linha que fale de uma leitura de 547 bytes, ou de um bloco que o controle devolva vazio.
11. Anote o que você encontrou; o esperado é não encontrar nada.

**Passa quando.** Nenhuma tela mostra valor nenhum vindo desse bloco escondido, e nenhum campo dos cartões do P1 e do P2 promete um dado que venha dele. O painel Detalhes técnicos não traz uma única linha sobre ele. Não acontecer nada é o verde deste teste.

**Por controle.**

* **P1** — Cabo, e é onde o teste tem mais força: pelo cabo o controle nem chega a declarar que esse bloco existe. Qualquer valor na tela que dissesse vir dele para este controle seria inventado.
* **P2** — Cabo, a mesma leitura no cartão dele. Dois iguais valem mais que um: se um dos dois mostrar alguma coisa que o outro não mostra, anote qual é.
* **P3** — Rádio, e aqui ele serve só de contraste — é no rádio que o bloco existe de verdade. Não mexa nele; ele tem a linha dele.
* **P4** — Rádio, mesma coisa. Não mexa; só confira que o cartão dele não mostra nenhum campo a mais do que o do P1.

**A armadilha.** Este é um dos raros testes em que NADA ACONTECER é o resultado certo, e é fácil registrá-lo como «não consegui testar». Ele existe para a próxima pessoa não gastar um dia procurando. Esse bloco foi lido com instrumento de bancada, nunca com a mão, e voltou vazio nos quatro controles — mas vir vazio numa leitura que não provocou o aparelho não decide nada nos dois sentidos: «só responde depois de um pedido» e «não responde nunca» devolvem o mesmo silêncio, e ninguém nunca o provocou com escrita nenhuma. Então a sua mão não pode provar o que ele faz; ela pode provar que o produto não finge saber. Se algum dia aparecer na tela um campo que diga vir daí, isso é o achado, e é grave: seria a tela afirmando uma função que medição nenhuma sustenta. E não clique em «Restaurar de fábrica», que fica na mesma faixa Avançado — não há razão de encostar nele aqui.

---

## mapa-plataforma.feature_f6-radio — FEATURE 0xF6 (547 B) — existe só no rádio, lê VAZIO, função desconhecida · rádio

*Célula:* `plataforma.feature_f6 @ rádio`

**O que isto prova.** Prova que, nos dois controles do rádio — onde esse bloco escondido de fato existe —, o Hefesto continua sem lê-lo e sem prometer nada sobre ele.

**Onde olhar.** A fonte não diz onde se lê este valor na tela: o produto não o lê em lugar nenhum, e nenhuma aba tem campo para ele. O que se olha é onde ele apareceria. Na aba Controles, o cartão que abre ao clicar na linha de um controle, com as linhas Microfone, Bateria, Touchpad, Barra de luz, LED do jogador, os dois analógicos, os Gatilhos e os blocos Giroscópio e Acelerômetro. E na aba Sistema, na faixa Avançado, o painel Detalhes técnicos, ao lado dos botões, que é a saída crua do Hefesto e se preenche sozinho — o botão «Ver detalhes» troca o painel pelas últimas linhas do registro.

**Os passos.**

1. Confira na fita do topo que o P3 e o P4 dizem rádio.
2. Abra a aba Controles.
3. Clique na linha do P1 para abrir o cartão dele e anote quais campos ele mostra, na ordem.
4. Clique na linha do P3 para abrir o cartão dele.
5. Compare campo a campo com o que você anotou do P1: o do rádio não pode ter nenhum campo a mais.
6. Clique na linha do P4 e faça a mesma comparação.
7. Abra a aba Sistema.
8. Desça até a faixa Avançado e leia o painel Detalhes técnicos, rolando-o de cima a baixo.
9. Clique em «Ver detalhes» e leia as linhas que aparecem.
10. Procure alguma linha que fale de um bloco de 547 bytes lido do controle, ou de uma leitura que só aconteça no rádio.
11. Anote o que você encontrou; o esperado é não encontrar nada.

**Passa quando.** Os cartões do P3 e do P4 mostram exatamente os mesmos campos que os do P1 e do P2 — nenhum campo a mais, nenhum valor que só apareça no rádio. E o painel Detalhes técnicos não traz uma linha sequer sobre esse bloco. Não acontecer nada é o verde.

**Por controle.**

* **P1** — Cabo, é a régua de comparação. Anote os campos do cartão dele ANTES de abrir o de um controle do rádio: sem esse antes não há com o que comparar, e o teste não mede nada.
* **P2** — Cabo, a segunda régua. Confira que ele mostra os mesmos campos do P1 — se os dois do cabo já divergirem entre si, pare e anote, porque a comparação com o rádio deixou de valer.
* **P3** — Rádio, e é aqui que o bloco existe de verdade. Compare o cartão dele com o do P1, campo a campo, com os dois rótulos lado a lado.
* **P4** — Rádio, o segundo. Mesma comparação. Se um dos dois do rádio mostrar um campo que o outro não mostra, isso é achado — anote qual, mesmo que não tenha nada a ver com este bloco.

**A armadilha.** Pelo rádio o bloco EXISTE e tem 547 bytes, exatamente o tamanho do maior pacote de saída do aparelho — e essa coincidência de tamanho é a única coisa que alimenta a suspeita de que ele sirva para combinar som. Suspeita, não medição: o conteúdo veio zerado nas quatro unidades lidas, e ninguém provocou o aparelho para ver se ele responde diferente depois de um pedido. Se você ler alguém desta casa dizendo que ele serve para o som, isso é hipótese vestida de fato, e derrubá-la é serviço prestado. Como no lado do cabo, nada acontecer é o verde — o difícil deste teste é registrá-lo como feito em vez de como impossível. E não clique em «Restaurar de fábrica», que fica na mesma faixa Avançado.

---

## mapa-plataforma.inventario-cabo — Inventário read-only do controle na interface e na CLI · cabo

*Célula:* `plataforma.inventario @ cabo`

**O que isto prova.** Prova que a lista do que o Hefesto sabe de cada controle está completa e certa para os dois do cabo, inclusive o número de série, que só o cabo entrega.

**Onde olhar.** Três lugares. Na aba Controles, o quadro Dispositivos Conectados: cada controle é uma linha com o número, a cor do plástico e por onde ele fala; clicando na linha o cartão abre com a leitura viva — Microfone, Bateria em porcento, Touchpad, Barra de luz com o código da cor, LED do jogador, os dois analógicos, os Gatilhos com um número de 0 a 255 cada, e os blocos Giroscópio e Acelerômetro com X, Y e Z. Na aba Sistema, na faixa Avançado, o painel Detalhes técnicos se preenche sozinho e mostra o FIM do texto: lá embaixo há um bloco chamado «Identidade de fábrica», com uma linha por controle ligado — o número, a cor do plástico, a palavra cabo ou rádio, e o número de série. E na aba Conexões, no quadro Gestão de Controles, cada linha traz «Vê como», que é o que o jogo enxerga.

**Os passos.**

1. Confira na fita do topo que o P1 e o P2 dizem cabo.
2. Abra a aba Sistema.
3. Desça até a faixa Avançado e leia o painel Detalhes técnicos, ao lado dos botões.
4. Role o painel até o fim e ache o bloco «Identidade de fábrica».
5. Conte as linhas desse bloco: tem de haver uma para cada um dos quatro controles ligados.
6. Leia a linha do P1: ela tem de trazer o número, a cor do plástico, a palavra cabo e um número de série comprido.
7. Leia a linha do P2 do mesmo jeito.
8. Pegue o P1 na mão e compare a cor do plástico dele com o nome escrito na linha.
9. Faça a mesma comparação com o P2.
10. Abra a aba Controles e clique na linha do P1 para abrir o cartão dele.
11. Confira que a Bateria mostra um número em porcento, e não um traço.
12. Encoste um dedo no touchpad do P1 e confira que a linha Touchpad passa a contar o toque.
13. Empurre o analógico esquerdo do P1 e confira que os números do analógico esquerdo andam no cartão.
14. Aperte o L2 do P1 até o fim e confira que o número dele, na linha Gatilhos, sobe até perto de 255.
15. Gire o P1 na mão e confira que os números do Giroscópio saem do zero.
16. Repita os passos 10 a 15 no P2.
17. Abra a aba Conexões e leia, no quadro Gestão de Controles, o que a linha do P1 e a do P2 dizem em «Vê como».

**Passa quando.** As quatro linhas de «Identidade de fábrica» existem, e as do P1 e do P2 trazem a palavra cabo e um número de série comprido — nenhuma das duas com traço no lugar do serial, e os dois seriais diferentes um do outro. A cor escrita bate com o plástico que você tem na mão. E no cartão de cada um, todo campo que devia responder responde: bateria com número, touchpad contando o toque, analógico andando, gatilho subindo até perto de 255 e giroscópio saindo do zero.

**Por controle.**

* **P1** — Cabo, e é ele que tem de trazer o número de série inteiro. Confira também o nome da cor contra o plástico na sua mão.
* **P2** — Cabo. O mesmo, e ele é a segunda prova: dois aparelhos, dois seriais diferentes. Dois controles com o MESMO serial escrito na tela é achado grave — anote os dois.
* **P3** — Rádio, testemunha. Só confira que a linha dele existe no bloco e que ela diz rádio. O serial dele é assunto da outra linha deste par, e a falta dele aqui não é defeito.
* **P4** — Rádio, testemunha. Mesma conferência. Se faltar a linha de um dos quatro no bloco, o inventário perdeu um controle, e isso é o achado.

**A armadilha.** Esta linha nunca foi medida com controle na mão: ela foi respondida LENDO O CÓDIGO, e o seu teste é o primeiro contato dela com o aparelho — anote tudo o que divergir, mesmo o que parecer bobagem. Duas armadilhas de leitura. A primeira: o painel Detalhes técnicos tem seis linhas de altura e mostra sempre o FIM do texto; a identidade fica no fim de propósito, e o resto do diagnóstico está uma rolada acima — quem não rolar vai jurar que o painel só tem o estado do serviço. A segunda: campo sem informação não mostra nada, por decisão sua — um campo em branco quer dizer «não foi lido», não «zero», e um traço no lugar de um número tem o mesmo sentido; nenhum dos dois conta como passa. E não confunda o que o cartão mostra com o que o jogo recebe: o «Vê como» da aba Conexões diz a máscara que o jogo enxerga, e ela se escolhe na aba Jogar — se estiver dizendo Xbox 360, é escolha sua e não defeito de inventário. Por fim, não clique em «Restaurar de fábrica», que fica na mesma faixa Avançado.

---

## mapa-plataforma.inventario-radio — Inventário read-only do controle na interface e na CLI · rádio

*Célula:* `plataforma.inventario @ rádio`

**O que isto prova.** Prova que a lista do que o Hefesto sabe dos dois controles do rádio está completa até onde o rádio entrega — e que o que falta aparece dito com todas as letras, em vez de sumir calado.

**Onde olhar.** Os mesmos dois lugares do lado do cabo, agora nas linhas do rádio. Na aba Sistema, faixa Avançado, o painel Detalhes técnicos se preenche sozinho e mostra o FIM do texto: no fim dele está o bloco «Identidade de fábrica», com uma linha por controle ligado — o número, a cor do plástico, a palavra cabo ou rádio, e o número de série. Nas linhas do rádio, no lugar do serial, tem de estar escrita a frase que diz que o serial só é lido no cabo. E na aba Controles, o cartão que abre ao clicar na linha de um controle, com Bateria em porcento, Touchpad, os dois analógicos, os Gatilhos e os blocos Giroscópio e Acelerômetro.

**Os passos.**

1. Confira na fita do topo que o P3 e o P4 dizem rádio.
2. Abra a aba Sistema.
3. Desça até a faixa Avançado e leia o painel Detalhes técnicos.
4. Role o painel até o fim e ache o bloco «Identidade de fábrica».
5. Leia a linha do P3: ela tem de trazer o número, a cor do plástico e a palavra rádio.
6. Leia o fim dessa mesma linha: no lugar do número de série tem de estar escrito que o serial só é lido no cabo.
7. Leia a linha do P4 do mesmo jeito.
8. Pegue o P3 na mão e compare a cor do plástico dele com o nome escrito na linha.
9. Faça a mesma comparação com o P4.
10. Abra a aba Controles e clique na linha do P3 para abrir o cartão dele.
11. Confira que a Bateria mostra um número em porcento, e não um traço.
12. Encoste um dedo no touchpad do P3 e confira que a linha Touchpad passa a contar o toque.
13. Empurre o analógico esquerdo do P3 e confira que os números andam no cartão.
14. Gire o P3 na mão e confira que os números do Giroscópio saem do zero.
15. Repita os passos 10 a 14 no P4.
16. Clique na linha do P1 e compare os campos do cartão dele com os do P3: têm de ser os mesmos campos, com os mesmos rótulos.

**Passa quando.** As linhas do P3 e do P4 existem no bloco, dizem rádio, trazem o nome da cor do plástico que bate com o aparelho na sua mão, e no lugar do número de série trazem a frase escrita — não um espaço em branco nem um traço seco. E os cartões dos dois respondem: bateria com número, touchpad contando o toque, analógico andando e giroscópio saindo do zero.

**Por controle.**

* **P1** — Cabo, régua de comparação: a linha dele traz o serial, e é olhando as duas linhas lado a lado que a diferença entre os transportes fica visível.
* **P2** — Cabo, a segunda régua. Confira que ele também traz serial — se nenhum dos dois do cabo trouxer, o problema não é do rádio e este teste está medindo outra coisa.
* **P3** — Rádio, é um dos dois medidos. Confira o nome da cor, a palavra rádio, a frase no lugar do serial, e os campos vivos do cartão.
* **P4** — Rádio, o segundo, e é o que mais importa aqui: a leitura da cor do plástico pelo rádio só foi provada em DUAS unidades, e nenhuma delas é necessariamente esta. Se o P4 vier sem nome de cor e com a borda neutra, o achado é DESTA unidade e não do transporte — anote qual controle é.

**A armadilha.** A frase «o serial só é lido no cabo» é o produto sendo honesto, não um defeito: o aparelho responde, quem cala é quem publica o dado, e escrever a frase foi decisão desta casa para o campo vazio não ler como falha. O que É defeito: um número de série aparecendo na linha de um controle do rádio — alguém o inventou —, ou um traço seco no lugar da frase, que é a explicação tendo sumido. Duas coisas mais. A cor do plástico pelo rádio está provada em duas unidades, não nas quatro desta bancada; se um terceiro controle recusar, o achado é a assinatura daquele aparelho, e a tela responde «não sei» em vez de mentir uma cor — borda neutra é ausência de leitura, não número errado. E, como no lado do cabo: esta linha foi respondida lendo o código, nunca com controle na mão, e o seu teste é o primeiro contato dela com o aparelho.

---

## mapa-plataforma.limitador_subcomando-cabo — Limitador de subcomando (o que governa toda escrita) · cabo

*Célula:* `plataforma.limitador_subcomando @ cabo`

**O que isto prova.** Prova que o Hefesto não perde o último clique quando você muda a mesma coisa muitas vezes seguidas num controle do cabo.

**Onde olhar.** Na aba Iluminação, a coluna do P1 e a do P2: a linha Cor, com os oito quadradinhos de cor lado a lado, e o código da cor escrito logo abaixo deles. A resposta é a barra de luz no plástico — as duas tiras acesas dos lados do touchpad. O passo com que o Hefesto junta os pedidos e os manda ao aparelho não tem campo na tela: a fonte não diz onde se leria esse número, porque não há onde. O que a sua mão mede é só o resultado — se o último clique chegou, e em quanto tempo.

**Os passos.**

1. Confira na fita do topo que o P1 e o P2 dizem cabo.
2. Feche a Steam e qualquer jogo aberto.
3. Abra a aba Iluminação.
4. Clique num quadradinho de cor bem diferente da atual na linha Cor da coluna do P1.
5. Confirme que a barra do P1 acendeu nessa cor.
6. Clique agora, um atrás do outro e o mais rápido que você conseguir, em seis quadradinhos DIFERENTES da linha Cor do P1, terminando num que você reconheça de longe.
7. Tire a mão do mouse e olhe a barra do P1: ela tem de estar na cor do ÚLTIMO clique.
8. Confira que ela não parou numa cor do meio da sequência.
9. Leia o código da cor escrito abaixo dos quadradinhos e confira que ele é o do último clique.
10. Olhe as barras do P2, do P3 e do P4: nenhuma pode ter mudado.
11. Repita os passos 6 a 10 na coluna do P2.
12. Anote, mais ou menos, quanto tempo a barra levou para assentar na última cor depois de você parar de clicar.

**Passa quando.** Depois da rajada de cliques, a barra do controle em que você clicou fica na cor do ÚLTIMO quadradinho, e não numa do meio. O código escrito abaixo dos quadradinhos concorda com a barra acesa. As barras dos outros três não mudam. E a barra assenta em menos de um segundo depois do último clique.

**Por controle.**

* **P1** — Cabo, é o primeiro a receber a rajada. Seis quadradinhos diferentes, o mais rápido que você conseguir, e o último tem de ser o que fica.
* **P2** — Cabo, o segundo. Faça nele a mesma rajada, depois que o P1 já tiver assentado: os dois do cabo têm de se comportar igual, e uma diferença entre eles é achado do aparelho.
* **P3** — Rádio, testemunha aqui — ele tem linha própria. Não clique na coluna dele; só confira que a barra não mudou durante as duas rajadas.
* **P4** — Rádio, testemunha. Mesma coisa. Se a cor da rajada do P1 aparecer nele, o pedido foi para o controle errado.

**A armadilha.** Clicar duas vezes no MESMO quadradinho não testa nada: o segundo clique não tem novidade a mandar, e não mandar é o certo — o Hefesto não reenvia um pedido idêntico ao anterior, de propósito. Use quadradinhos diferentes, sempre. Outra: o passo com que ele junta os pedidos cresce com o número de controles ligados; com os quatro na mesa ele é mais lento do que seria com um só, e uma barra que demora um pouco mais a assentar não é defeito. Feche a Steam antes de começar: com ela aberta, quem escreve por último na luz ganha, e você pode acabar medindo a Steam. E lembre que esta linha foi respondida lendo o código e nunca com controle na mão — se a barra ficar presa numa cor do meio da sequência, isso é achado novo, e vale anotar exatamente quantos cliques você deu e em que ordem.

---

## mapa-plataforma.limitador_subcomando-radio — Limitador de subcomando (o que governa toda escrita) · rádio

*Célula:* `plataforma.limitador_subcomando @ rádio`

**O que isto prova.** Prova que a rajada de cliques também não se perde nos dois controles do rádio, e separa o que é do passo de envio do que é do sem fio.

**Onde olhar.** Na aba Iluminação, as colunas do P1, do P3 e do P4: a linha Cor, com os oito quadradinhos de cor, e o código da cor escrito logo abaixo. A resposta é a barra de luz no plástico, as duas tiras dos lados do touchpad. O passo com que o Hefesto junta os pedidos e os manda não tem campo na tela — a fonte não diz onde se leria, porque não há onde; e ele é o MESMO número no cabo e no rádio, o que é justamente o que torna a comparação entre os dois útil.

**Os passos.**

1. Confira na fita do topo que o P3 e o P4 dizem rádio e que o P1 diz cabo.
2. Feche a Steam e qualquer jogo aberto.
3. Abra a aba Iluminação.
4. Clique, um atrás do outro e o mais rápido que conseguir, em seis quadradinhos DIFERENTES da linha Cor da coluna do P1, terminando num que você reconheça de longe.
5. Olhe a barra do P1 e anote se ela ficou na cor do último clique e quanto tempo levou para assentar.
6. Faça a mesma rajada de seis quadradinhos diferentes na coluna do P3.
7. Tire a mão do mouse e olhe a barra do P3: ela tem de estar na cor do ÚLTIMO clique.
8. Confira que ela não parou numa cor do meio da sequência.
9. Leia o código da cor abaixo dos quadradinhos do P3 e confira que ele é o do último clique.
10. Olhe as barras do P1, do P2 e do P4: nenhuma pode ter mudado por causa da rajada do P3.
11. Repita os passos 6 a 10 na coluna do P4.
12. Compare o que você anotou do P1 com o que aconteceu no P3 e no P4, e anote a diferença de tempo.

**Passa quando.** Depois da rajada, a barra do controle do rádio fica na cor do último quadradinho, e não numa do meio — exatamente como aconteceu no do cabo. O código escrito abaixo dos quadradinhos concorda com a barra. As barras dos outros três não mudam.

**Por controle.**

* **P1** — Cabo, e é a régua: faça a rajada NELE primeiro e anote o tempo. Sem esse antes não há com o que comparar, e o teste não separa nada.
* **P2** — Cabo, testemunha. Não clique na coluna dele; só confira que a barra não mudou durante as rajadas dos outros.
* **P3** — Rádio, é o primeiro a receber a rajada. Seis quadradinhos diferentes, e o último tem de ser o que fica na barra.
* **P4** — Rádio, o segundo, e ele divide o adaptador com o P3. Faça a rajada nele depois que o P3 assentar; se só ele perder cliques, a diferença é do enlace dele, não do envio.

**A armadilha.** O número com que o Hefesto espaça os envios é o MESMO no cabo e no rádio — não existe um valor por transporte. Então, se a rajada se perder só no rádio, a causa não é esse passo: é o enlace sem fio, e é para separar as duas coisas que a rajada no P1 vem primeiro. Sem ela, o teste não mede nada. As outras duas de sempre: clicar duas vezes no mesmo quadradinho não manda nada de novo, de propósito, então use quadradinhos diferentes; e o passo cresce com o número de controles ligados, então com quatro na mesa tudo assenta um pouco mais devagar do que assentaria com um. Feche a Steam antes: com ela aberta, quem escreve por último na luz ganha.

---

## mapa-plataforma.link_parametros-cabo — Parâmetros do link (supervisão, sniff negociado, latência) · cabo

*Célula:* `plataforma.link_parametros @ cabo`

**O que isto prova.** Prova que o Hefesto não oferece nem inventa ajuste de enlace sem fio para os dois controles do cabo — onde enlace sem fio nem existe.

**Onde olhar.** Na aba Conexões. O quadro Check-up é o exame da sala; o quadro Gestão de Controles tem uma linha por controle ligado; e no fim da aba fica a seção Desempenho, com a linha «O rádio de cada adaptador, em turnos» e uma régua por adaptador, onde se lê algo como «276,7 de 1.600». Nessa régua, as vagas TRACEJADAS são os controles que estão no cabo: eles não gastam rádio e aparecem só como «se viessem». Logo abaixo da régua há um parágrafo chamado «De onde vêm os números». Não existe em tela nenhuma um campo que ofereça mexer em tempo de supervisão, em intervalo de escuta ou em latência do enlace — a fonte não diz onde se leria isso porque não há onde.

**Os passos.**

1. Confira na fita do topo que o P1 e o P2 dizem cabo.
2. Abra a aba Conexões.
3. Leia o quadro Check-up de cima a baixo e anote cada linha que fale dos controles do cabo.
4. Confira que nenhuma dessas linhas oferece um ajuste de enlace — elas falam de entrada, de energia e de vizinhança de rádio.
5. Desça até a seção Desempenho.
6. Conte as vagas tracejadas na régua do adaptador: tem de haver uma para cada controle que está no cabo.
7. Confira que o P1 e o P2 aparecem só como tracejados, e não como consumo de agora.
8. Leia o parágrafo «De onde vêm os números», logo abaixo da explicação da régua, e anote o que ele diz sobre a origem de cada número.
9. Suba até o quadro Gestão de Controles e abra a linha do P1.
10. Procure, dentro dela, qualquer campo que ofereça mexer em tempo de resposta, intervalo ou latência de rádio.
11. Repita a procura na linha do P2.
12. Anote o que você encontrou; o esperado é não encontrar nada.

**Passa quando.** Nenhuma aba oferece ajuste de enlace sem fio para um controle do cabo, e nenhum número na tela é apresentado como medida do enlace deles. Na régua da seção Desempenho, o P1 e o P2 aparecem como vagas tracejadas — o que eles custariam se viessem para o rádio —, nunca como consumo de agora.

**Por controle.**

* **P1** — Cabo. Confira que ele aparece só como vaga tracejada na régua e que nenhum campo da linha dele oferece ajuste de rádio. Ele não tem enlace sem fio: não há o que parametrizar.
* **P2** — Cabo. Mesma conferência. Se os dois do cabo aparecerem consumindo turnos, a conta está cobrando de quem não fala no rádio, e esse é o achado.
* **P3** — Rádio, testemunha, e é o contraste que dá sentido ao teste: ele SIM tem de aparecer consumindo turnos na régua.
* **P4** — Rádio, testemunha. Mesma coisa. Se ele estiver ligado no rádio e não aparecer na régua, anote — a régua está contando menos gente do que existe.

**A armadilha.** O erro fácil aqui é ler os números da régua como medida do enlace. Eles não são, e a própria tela diz isso: o parágrafo «De onde vêm os números» escreve que os 1.600 turnos são especificação do Bluetooth e nunca foram medidos aqui, e que o consumo por controle veio de um ensaio com UM controle, com a soma de quatro sendo derivada — o maior ensaio de rádio desta casa foi de dois. Um número honesto sobre a própria origem não vira medida por estar na tela. E é isso que este teste protege: se algum dia aparecer ali um número apresentado como leitura do enlace de agora, sem essa ressalva, isso é o achado — porque ninguém nesta casa tem instrumento que leia esses números, e o lado do cabo nem tem enlace a ler. Não confunda com o exame do Check-up: ele fala de entrada USB fraca e de vizinhança de rádio, que são outra coisa e existem de verdade.

---

## mapa-plataforma.link_parametros-radio — Parâmetros do link (supervisão, sniff negociado, latência) · rádio

*Célula:* `plataforma.link_parametros @ rádio`

**O que isto prova.** Prova que, nos dois controles do rádio, o Hefesto continua sem mexer no enlace e sem apresentar como medido nenhum número que ninguém mediu.

**Onde olhar.** Na aba Conexões, a seção Desempenho, no fim da aba: a linha «O rádio de cada adaptador, em turnos», a régua de cada adaptador — onde cada controle do rádio aparece como uma fatia com o nome da cor do plástico dele —, o número no fim da régua no formato tantos «de 1.600», e o parágrafo «De onde vêm os números» logo abaixo. Acima, o quadro Gestão de Controles, com a linha de cada controle ligado, que se abre ao clicar. E na aba Sistema, no quadro O exame de hoje, a linha que fala de Bluetooth — quantos adaptadores e quantos controles no rádio.

**Os passos.**

1. Confira na fita do topo que o P3 e o P4 dizem rádio.
2. Abra a aba Conexões.
3. Desça até a seção Desempenho.
4. Confira que o P3 e o P4 aparecem na régua do adaptador consumindo turnos, cada um com o nome da cor do plástico dele.
5. Leia o número no fim da régua, no formato tantos «de 1.600», e anote-o.
6. Leia o parágrafo «De onde vêm os números» e anote o que ele diz sobre a origem de cada número.
7. Confira que ele diz, com todas as letras, que os turnos são especificação e nunca foram medidos aqui.
8. Suba até o quadro Gestão de Controles e clique na linha do P3 para abri-la.
9. Procure, dentro dela, qualquer campo que ofereça mexer em tempo de resposta, intervalo de escuta ou latência do rádio.
10. Repita a procura na linha do P4.
11. Abra a aba Sistema e leia, no quadro O exame de hoje, a linha que fala de Bluetooth.
12. Confira que ela conta os adaptadores e quantos controles estão no rádio, e que ela manda para a aba Conexões em vez de oferecer um ajuste.
13. Anote qualquer número da tela que seja apresentado como medida do enlace sem dizer de onde veio.

**Passa quando.** Nenhuma linha dos controles do rádio oferece ajuste de enlace, e todo número da seção Desempenho vem acompanhado do parágrafo que diz de onde ele saiu. A régua mostra os DOIS controles do rádio, cada um com o nome da cor dele. E a linha de Bluetooth do exame da aba Sistema conta o que existe e aponta para a aba Conexões, sem prometer conserto.

**Por controle.**

* **P1** — Cabo, testemunha: ele aparece como vaga tracejada na régua, e nenhum campo da linha dele oferece ajuste de rádio.
* **P2** — Cabo, testemunha. Mesma coisa. Os dois do cabo juntos mostram que a régua sabe separar quem fala no rádio de quem não fala.
* **P3** — Rádio, é um dos dois medidos. Confira que ele aparece consumindo turnos, com o nome da cor dele, e que nenhum campo da linha dele oferece mexer no enlace.
* **P4** — Rádio, o segundo. Mesma conferência — e com os dois no ar a régua tem de SOMAR os dois, não repetir um. Uma régua que mostra um só com dois no rádio é o achado.

**A armadilha.** O que esta linha do mapa diz é «ninguém sabe», e o teste tem de conseguir enxergar isso. Não há nesta casa instrumento que leia tempo de supervisão, intervalo de escuta ou latência do enlace: quem negocia esses números é o sistema com o firmware, sozinho. E há uma prova de que a ausência é do aparelho e não de quem procurou: o driver desta máquina tem as alavancas todas para um controle mais velho da mesma marca, e nenhuma para o DualSense. Então um verde aqui não diz que o enlace está bom — diz que a tela não mente sobre ele. O achado que este teste caça é uma tela que passe a exibir um desses números como se alguém os tivesse lido. Não confunda com a régua de turnos: ela é uma conta declarada, não uma medição do seu enlace, e a própria tela diz isso no parágrafo de origem.

---

## mapa-plataforma.probe-cabo — Subir a probe (o controle EXISTIR para o sistema) · cabo

*Célula:* `plataforma.probe @ cabo`

**O que isto prova.** Prova que encaixar o cabo faz o controle nascer INTEIRO para o Hefesto — com número, bateria, movimento e touchpad — em menos de cinco segundos.

**Onde olhar.** Na fita do topo do Hefesto, a linha que começa com «Selecionar:»: cada controle vira um chip com o número, a cor do plástico e a palavra cabo ou rádio. No alto, a contagem, no formato «4 controles: 2 USB · 2 BT». Na aba Controles, o quadro Dispositivos Conectados, com uma linha por controle, e o cartão que abre ao clicar na linha: Bateria em porcento, Touchpad, os dois analógicos, os Gatilhos e os blocos Giroscópio e Acelerômetro com X, Y e Z.

**Os passos.**

1. Deixe o P3 e o P4 ligados no rádio e não encoste neles durante o teste.
2. Abra o Hefesto na aba Controles.
3. Desencaixe o cabo do P1.
4. Conte até dez, devagar.
5. Confira que o chip do P1 saiu da fita e que a contagem do alto caiu para três controles.
6. Encaixe o cabo de volta no P1 e depois no PC.
7. Conte até cinco, devagar, olhando a fita.
8. Leia o chip que apareceu: número, cor do plástico e a palavra cabo.
9. Clique na linha do P1 para abrir o cartão dele.
10. Confira que a Bateria mostra um número em porcento, e não um traço.
11. Encoste um dedo no touchpad do P1 e confira que a linha Touchpad conta o toque.
12. Gire o P1 na mão e confira que os números do Giroscópio saem do zero.
13. Empurre o analógico esquerdo do P1 e confira que os números andam no cartão.
14. Repita os passos 3 a 13 com o P2.
15. Confira, no fim, que a contagem do alto voltou a dizer quatro controles, dois no cabo e dois no rádio.

**Passa quando.** Depois de encaixar o cabo, o controle volta à fita em menos de cinco segundos, com o mesmo número de antes, e o cartão dele responde em TODOS os campos vivos: bateria com número, touchpad contando o toque, giroscópio saindo do zero e analógico andando. Meio controle não passa — se ele aparece mas a bateria fica em traço, ou o giroscópio não sai do zero, o teste reprovou.

**Por controle.**

* **P1** — Cabo, é o primeiro a sair e voltar. Desencaixe o cabo, encaixe de novo, e confira o cartão inteiro depois — não só o chip na fita.
* **P2** — Cabo, o segundo. Mesmo gesto, e um de cada vez: com os dois fora ao mesmo tempo você não sabe qual voltou primeiro nem qual ficou pela metade.
* **P3** — Rádio, testemunha. Não encoste nele. O chip dele não pode sumir da fita nem trocar de número enquanto o do cabo sai e volta.
* **P4** — Rádio, testemunha. Mesma coisa. Se ele cair junto quando você mexe num do cabo, o achado não é da entrada do controle e sim de alguma coisa que derruba os quatro — anote a hora exata.

**A armadilha.** Meio controle é o defeito que este teste caça, e ele engana porque o chip APARECE. Quando um controle sobe pela metade, o Hefesto o lista e o cartão fica sem bateria, sem movimento e sem touchpad — e isso se lê como «a tela está lenta». Por isso os passos mandam MEXER no aparelho: touchpad, giroscópio e analógico, um a um. Segunda: olhe a palavra do transporte dentro do chip. No chip vivo está escrito cabo ou rádio; se você vir USB ou BT dentro de um chip, a fita não está lendo os seus controles, e o teste não passou nem reprovou — não houve leitura. (Na contagem lá do alto é o contrário: ali USB e BT estão certos, foi decisão sua.) Terceira: se o controle não voltar de jeito nenhum, troque de porta USB antes de reprovar — entrada fraca derruba controle do cabo, e o exame da aba Conexões tem uma linha só sobre isso.

---

## mapa-plataforma.probe-radio — Subir a probe (o controle EXISTIR para o sistema) · rádio

*Célula:* `plataforma.probe @ rádio`

**O que isto prova.** Prova que ligar o controle pelo rádio o faz nascer INTEIRO — e não apenas conectado: com bateria, movimento e touchpad respondendo.

**Onde olhar.** Na fita do topo, a linha que começa com «Selecionar:», onde cada controle é um chip com o número, a cor do plástico e a palavra cabo ou rádio; e a contagem no alto, no formato «4 controles: 2 USB · 2 BT». Na aba Controles, o quadro Dispositivos Conectados e o cartão que abre ao clicar na linha de um controle: Bateria em porcento, Touchpad, os dois analógicos, os Gatilhos e os blocos Giroscópio e Acelerômetro com X, Y e Z. São esses três últimos — bateria, touchpad e movimento — que dizem se ele subiu inteiro.

**Os passos.**

1. Deixe o P1 e o P2 no cabo e não encoste neles durante o teste.
2. Abra o Hefesto na aba Controles.
3. Segure o botão PS do P3 até todas as luzes dele apagarem, e solte.
4. Conte até dez, devagar.
5. Confira que o chip do P3 saiu da fita e que a contagem do alto caiu para três controles.
6. Dê um toque curto no botão PS do P3 para religá-lo.
7. Conte até cinco, devagar, olhando a fita.
8. Leia o chip que apareceu: número, cor do plástico e a palavra rádio.
9. Clique na linha do P3 para abrir o cartão dele.
10. Confira que a Bateria mostra um número em porcento, e não um traço.
11. Encoste um dedo no touchpad do P3 e confira que a linha Touchpad conta o toque.
12. Gire o P3 na mão e confira que os números do Giroscópio saem do zero.
13. Empurre o analógico esquerdo do P3 e confira que os números andam no cartão.
14. Repita os passos 3 a 13 com o P4.
15. Confira, no fim, que a contagem do alto voltou a dizer quatro controles, dois no cabo e dois no rádio.

**Passa quando.** Depois do toque no PS, o controle volta à fita em poucos segundos com o mesmo número, e o cartão dele responde em TODOS os campos vivos: bateria com número, touchpad contando o toque, giroscópio saindo do zero e analógico andando. Aparecer na lista não basta — um controle listado sem bateria, sem touchpad e sem movimento é reprovação.

**Por controle.**

* **P1** — Cabo, testemunha. Não encoste nele; o chip dele não pode sumir nem trocar de número enquanto os do rádio saem e voltam.
* **P2** — Cabo, testemunha. Mesma coisa.
* **P3** — Rádio, é o primeiro a sair e voltar. Segure o PS até apagar, religue com um toque curto, e confira o cartão inteiro depois.
* **P4** — Rádio, o segundo, e um de cada vez. Se ele cair sozinho quando você desliga o P3, o achado não é da entrada do controle: é o adaptador de rádio dividindo banda entre os dois, e isso tem lugar próprio na seção Desempenho da aba Conexões.

**A armadilha.** É NO RÁDIO que o meio controle acontece de verdade, e a razão é do aparelho: pelo rádio o DualSense nasce MUDO — manda só o essencial até alguém lhe pedir uma informação de fábrica, e é esse pedido que o vira para o relatório completo, com movimento, touchpad e bateria dentro. Se o pedido falhar, o controle acende, pareia, entra na lista e fica sem nada disso. Então «ele conectou» não é resposta neste teste: as três conferências dos passos 10 a 12 é que são. E o pedido tem prazo curto: quando expira, a subida inteira é abandonada de uma vez, sem segunda tentativa do lado do sistema — o conserto é desligar e ligar o controle de novo, não esperar. Por fim, olhe a palavra dentro do chip: no chip vivo está escrito cabo ou rádio; USB ou BT dentro de um chip quer dizer que a fita não está lendo os seus controles, e aí não houve leitura nenhuma.

---

## mapa-plataforma.probe.retry-cabo — Retry de probe · cabo

*Célula:* `plataforma.probe.retry @ cabo`

**O que isto prova.** Prova que o Hefesto fica tentando sozinho até o controle do cabo entrar, e que ele entra inteiro mesmo depois de várias idas e voltas seguidas.

**Onde olhar.** Na fita do topo, os chips com o número, a cor do plástico e a palavra cabo ou rádio; e a contagem no alto, no formato «4 controles: 2 USB · 2 BT». Na aba Controles, o quadro Dispositivos Conectados e o cartão que abre ao clicar na linha: Bateria em porcento, Touchpad, os analógicos e os blocos Giroscópio e Acelerômetro. E na aba Sistema, na faixa Avançado, o botão «Ver detalhes», que troca o painel Detalhes técnicos pelas últimas linhas do registro, cada uma com o horário na frente.

**Os passos.**

1. Confira que os quatro estão ligados e que a contagem do alto diz quatro controles.
2. Abra o Hefesto na aba Controles.
3. Anote a hora no relógio.
4. Desencaixe o cabo do P1, conte até três, e encaixe de volta.
5. Repita esse desencaixa-e-encaixa mais quatro vezes no P1, sempre contando até três entre uma coisa e a outra.
6. Deixe o cabo encaixado na última vez.
7. Conte até dez, devagar.
8. Confira que o chip do P1 está na fita, com o mesmo número de antes.
9. Clique na linha do P1 e confira que o cartão responde: bateria com número, touchpad contando o toque e giroscópio saindo do zero.
10. Repita os passos 4 a 9 com o P2.
11. Abra a aba Sistema e desça até a faixa Avançado.
12. Clique em «Ver detalhes» e leia as últimas linhas do registro.
13. Procure, pelo horário que você anotou, as linhas das idas e voltas do P1 e do P2, e anote se alguma delas fala de tentativa que falhou.

**Passa quando.** Depois de cinco idas e voltas seguidas, os dois controles do cabo estão de volta na fita com os mesmos números de antes, e os cartões deles respondem em todos os campos vivos. Nenhum dos dois ficou de fora e nenhum voltou pela metade.

**Por controle.**

* **P1** — Cabo, é o primeiro a apanhar: cinco idas e voltas, uma de cada vez, com três segundos entre elas. No fim, o cartão inteiro tem de responder.
* **P2** — Cabo, o segundo. Mesma sequência, e só depois de o P1 já ter assentado — os dois ao mesmo tempo não deixam saber qual demorou.
* **P3** — Rádio, testemunha. Não encoste nele; o chip dele não pode sumir nem trocar de número enquanto o do cabo entra e sai cinco vezes.
* **P4** — Rádio, testemunha. Mesma coisa, e ele é o mais sensível: se as idas e voltas de um controle do cabo derrubarem o último do rádio, isso é o achado.

**A armadilha.** O Hefesto refaz a procura a cada cinco segundos, e ela ESPAÇA quando falha muitas vezes seguidas: depois de várias tentativas a espera entre uma e outra cresce, então um controle que demora quinze ou vinte segundos a voltar no fim de uma sequência longa não é defeito — é a espera crescida. Espere mais antes de reprovar, e anote quanto tempo levou. Duas coisas mais. Existem DUAS tentativas diferentes em jogo, e elas não se somam: a do Hefesto refaz a procura inteira a cada cinco segundos, e a do sistema tenta de novo um pedido de informação de fábrica dentro de uma única subida — confundir as duas faz procurar o número errado quando um controle não entra. E não faça as idas e voltas depressa demais: encaixar e desencaixar sem esperar maltrata o conector, e o que você mede passa a ser o seu gesto, não o produto. Não clique em «Restaurar de fábrica», que fica na mesma faixa Avançado.

---

## mapa-plataforma.probe.retry-radio — Retry de probe · rádio

*Célula:* `plataforma.probe.retry @ rádio`

**O que isto prova.** Prova que um controle do rádio que não entra na primeira volta acaba entrando, e mostra o que fazer quando ele acende mas não aparece na lista.

**Onde olhar.** Na fita do topo, os chips com o número, a cor do plástico e a palavra cabo ou rádio; e a contagem no alto, no formato «4 controles: 2 USB · 2 BT». Na aba Controles, o cartão que abre ao clicar na linha de um controle: Bateria em porcento, Touchpad, os analógicos e os blocos Giroscópio e Acelerômetro. E na aba Sistema, na faixa Avançado, o botão «Ver detalhes», que troca o painel Detalhes técnicos pelas últimas linhas do registro, cada uma com o horário na frente.

**Os passos.**

1. Confira que os quatro estão ligados e que a contagem do alto diz quatro controles.
2. Abra o Hefesto na aba Controles.
3. Anote a hora no relógio.
4. Segure o botão PS do P3 até as luzes apagarem e solte.
5. Conte até cinco, devagar, com o P3 na mesa.
6. Dê um toque curto no botão PS do P3 para religá-lo.
7. Anote quantos segundos levou até o chip dele voltar à fita.
8. Anote também se a barra de luz dele acendeu sem o chip aparecer.
9. Repita os passos 4 a 8 mais quatro vezes no P3, sempre esperando o chip voltar antes da volta seguinte.
10. Desligue e ligue o P3 mais uma vez, se em alguma das cinco voltas ele tiver acendido sem aparecer.
11. Clique na linha do P3 e confira que o cartão responde: bateria com número, touchpad contando o toque e giroscópio saindo do zero.
12. Repita os passos 4 a 11 com o P4.
13. Abra a aba Sistema, desça até a faixa Avançado e clique em «Ver detalhes».
14. Leia as últimas linhas do registro pelo horário que você anotou e anote qualquer linha que fale de tentativa que falhou.

**Passa quando.** Nas cinco voltas, o controle do rádio termina de volta na fita, com o mesmo número, e o cartão dele responde em todos os campos vivos. Se em alguma volta ele acendeu sem aparecer na lista, desligar e ligar de novo resolveu — e isso ainda vale como passa, desde que você anote em quantas das cinco aconteceu.

**Por controle.**

* **P1** — Cabo, testemunha: chip na fita o tempo todo, número intacto, e o cartão respondendo no fim.
* **P2** — Cabo, testemunha. Mesma conferência.
* **P3** — Rádio, é o primeiro a apanhar: cinco voltas, uma de cada vez, esperando o chip reaparecer entre elas. Anote os segundos de cada volta.
* **P4** — Rádio, o segundo, e é o que mais costuma sofrer — ele é o último da fila e divide o mesmo adaptador com o P3. Se ele precisar de mais voltas que o P3, anote o número de cada um: é a diferença entre os dois que interessa.

**A armadilha.** Aqui existe uma falha que NÃO se conserta esperando, e reconhecê-la é o ponto do teste. Pelo rádio, o pedido de informação de fábrica que o controle precisa responder para subir inteiro tem prazo de três segundos, e o sistema desta máquina faz UMA tentativa só por padrão. Se ela expira, a subida morre inteira: o controle fica aceso, pareado, e simplesmente não existe para o Hefesto. E o Hefesto refazendo a procura a cada cinco segundos não salva esse caso, porque não há o que procurar. O gesto que resolve é desligar e ligar o controle de novo — ficar esperando não resolve, e é assim que se perde meia hora. Duas outras: conte os segundos a partir de quando você SOLTA o botão, não de quando aperta; e não religue depressa demais, porque o Hefesto ainda pode achar que ele está lá — deixe pelo menos cinco segundos desligado entre uma volta e a seguinte. Não clique em «Restaurar de fábrica», que fica na mesma faixa Avançado.

---

## mapa-plataforma.slot_jogador-cabo — Slot / número de jogador atribuído pelo Hefesto · cabo

*Célula:* `plataforma.slot_jogador @ cabo`

**O que isto prova.** Prova que o número de jogador dos dois controles do cabo pertence ao CONTROLE, e não à entrada USB em que ele está espetado.

**Onde olhar.** Três lugares, e eles têm de concordar. Na fita do topo do Hefesto, a linha que começa com "Selecionar:": cada controle é um chip com o número (P1 a P4), a cor do plástico e a palavra cabo ou rádio. No alto, a contagem, no formato "4 controles: 2 USB · 2 BT". Na aba Conexões, o quadro Gestão de Controles, onde cada linha traz "Player 1", "Player 2" e assim por diante, e termina em USB ou em BT. E no aparelho: as cinco lampadinhas brancas embaixo do touchpad, que dizem o número pelo CONJUNTO aceso — jogador 1 é só a do meio; jogador 2 são a segunda e a quarta; jogador 3 são as duas das pontas e a do meio; jogador 4 são as quatro, com a do meio apagada.

**Os passos.**

1. Confira que os quatro estão ligados: P1 e P2 no cabo, P3 e P4 no rádio.
2. Abra o Hefesto e clique na aba Conexões.
3. Anote num papel o número de Player dos quatro, na lista Gestão de Controles.
4. Olhe as lampadinhas de cada um dos quatro aparelhos e confira que a figura bate com o número que a tela mostra.
5. Anote em qual entrada USB do PC está o cabo do P1.
6. Puxe o cabo do P1 de dentro do PC — do lado do PC, nunca do lado do controle.
7. Encaixe esse mesmo cabo numa entrada USB DIFERENTE do PC, sem demorar.
8. Conte até dez, devagar, olhando a fita do topo.
9. Leia o chip do P1: tem de dizer P1 e a palavra cabo.
10. Olhe as lampadinhas do P1 e confira que continuam no desenho do jogador 1.
11. Repita os passos 5 a 10 com o cabo do P2, levando-o para uma terceira entrada USB.
12. Leia de novo a lista Gestão de Controles e a contagem do alto.
13. Olhe as lampadinhas dos quatro aparelhos uma última vez e compare com o que você anotou no papel.

**Passa quando.** Cada um dos dois controles do cabo volta com exatamente o mesmo número de jogador que tinha antes de trocar de entrada USB, na tela e nas lampadinhas do aparelho. A contagem do alto volta a dizer quatro controles, dois no cabo e dois no rádio. E os dois do rádio não trocam de número em instante nenhum, nem enquanto os cabos estão fora.

**Por controle.**

* **P1** — Cabo, e é o primeiro a mudar de entrada. Anote o número dele e a entrada USB antes de puxar o cabo. Tem de voltar como o mesmo jogador, com as mesmas lampadinhas acesas, numa entrada que ele nunca tinha visto.
* **P2** — Cabo, e é o segundo a mudar de entrada. Mesmo gesto, uma entrada ainda diferente. Faça um de cada vez: com os dois cabos fora ao mesmo tempo você não sabe qual dos dois causou o que aparecer.
* **P3** — Rádio, e é testemunha. Não encoste nele. O número dele não pode mudar enquanto os cabos vão e vêm, e o chip dele não pode sumir da fita. Se ele trocar de número junto com a mexida no cabo, a numeração está seguindo a mesa inteira em vez de cada controle.
* **P4** — Rádio, e é a segunda testemunha. Não encoste nele. É o último da fila e o primeiro a se mexer quando alguma coisa se desmonta: confira número e lampadinhas antes e depois.

**A armadilha.** As cinco lampadinhas não se contam da esquerda para a direita — o número é o CONJUNTO aceso, e quem lê "a terceira lampadinha acesa" como jogador 3 reprova um produto que está certo. Segunda: puxar o cabo derruba o controle, e o lugar dele fica guardado por trinta segundos; se você demorar mais que isso entre tirar e devolver o cabo, ele pode voltar com outro número, e isso é a regra do produto valendo, não defeito — refaça mais rápido. Terceira: se um chip da fita disser USB ou BT em vez de cabo ou rádio, a fita não está lendo os seus controles, está mostrando o desenho parado; ali o teste não passou nem reprovou. (Na contagem do alto, USB e BT estão certos — foi decisão sua.) E há uma coisa que o mapa já declara e que muda o veredito: o DualSense NÃO SABE que número ele é. O número é invenção do Hefesto e não tem canal nenhum no aparelho; o que o aparelho mostra são as lampadinhas. Se a tela disser um número e as lampadinhas disserem outro, quem quebrou foi a metade que EXIBE, e é esse o achado a anotar.

---

## mapa-plataforma.slot_jogador-radio — Slot / número de jogador atribuído pelo Hefesto · rádio

*Célula:* `plataforma.slot_jogador @ rádio`

**O que isto prova.** Prova que o número de jogador dos dois controles do rádio segue o controle, e não a ordem em que ele voltou a ligar.

**Onde olhar.** Na fita do topo do Hefesto, a linha que começa com "Selecionar:", onde cada controle é um chip com o número, a cor do plástico e a palavra cabo ou rádio. Na aba Conexões, o quadro Gestão de Controles, com "Player 1", "Player 2" e assim por diante em cada linha. A contagem no alto, no formato "4 controles: 2 USB · 2 BT". E, nos aparelhos, as cinco lampadinhas brancas embaixo do touchpad: jogador 1 é só a do meio; jogador 2 são a segunda e a quarta; jogador 3 são as duas das pontas e a do meio; jogador 4 são as quatro, com a do meio apagada.

**Os passos.**

1. Confira que os quatro estão ligados: P1 e P2 no cabo, P3 e P4 no rádio.
2. Abra o Hefesto e clique na aba Conexões.
3. Anote num papel o número de Player dos quatro, na lista Gestão de Controles.
4. Olhe as lampadinhas dos quatro aparelhos e confira que a figura bate com o número da tela.
5. Ponha o P3 e o P4 lado a lado na mesa, com as duas mãos livres — daqui para a frente você tem trinta segundos.
6. Segure o botão PS do P3 até todas as luzes dele apagarem.
7. Segure o botão PS do P4 até todas as luzes dele apagarem, logo em seguida.
8. Dê um toque curto no botão PS do P4 — o QUARTO controle, e ele volta PRIMEIRO.
9. Conte até cinco, devagar, olhando a fita.
10. Leia o chip que apareceu: tem de dizer P4 e a palavra rádio.
11. Dê um toque curto no botão PS do P3.
12. Conte até cinco, devagar.
13. Leia o chip novo: tem de dizer P3 e a palavra rádio.
14. Olhe as lampadinhas do P3 e do P4 e confira que cada um voltou ao desenho do próprio número.
15. Leia a contagem do alto e as quatro linhas da lista Gestão de Controles.
16. Confira que o P1 e o P2 continuam com os números que você anotou no papel.

**Passa quando.** O P4 volta como jogador 4 mesmo tendo sido o PRIMEIRO a religar, e o P3 volta como jogador 3 mesmo tendo sido o segundo — na tela e nas lampadinhas dos dois aparelhos. Se o P4 voltasse como jogador 3, o número estaria seguindo a ordem de chegada em vez de seguir o controle, e isso reprova. E os dois do cabo não trocam de número em instante nenhum.

**Por controle.**

* **P1** — Cabo, e é testemunha. Não encoste nele. Anote o número antes e confira depois: tem de ser o mesmo, com as mesmas lampadinhas. Se um dos dois do cabo se mexer enquanto os do rádio saem e voltam, anote que quem se mexeu estava no CABO.
* **P2** — Cabo, e é a segunda testemunha. Não encoste nele. Mesma conferência do P1.
* **P3** — Rádio, e é o que sai PRIMEIRO e volta POR ÚLTIMO. Segure o PS até apagar; depois, quando chegar a vez dele, um toque curto no PS. Tem de voltar como jogador 3, com as duas lampadinhas das pontas e a do meio acesas.
* **P4** — Rádio, e é o que sai POR ÚLTIMO e volta PRIMEIRO. É nele que este teste se decide: voltando antes do P3, ele tem de voltar mesmo assim como jogador 4, com as quatro lampadinhas acesas e a do meio apagada.

**A armadilha.** O relógio decide, e ele já reprovou produto são: o lugar de quem cai fica guardado por trinta segundos. Do momento em que você desliga o primeiro até o momento em que o segundo volta tem de passar MENOS de trinta segundos; passando disso os dois lugares são liberados e os números saem mesmo pela ordem de chegada — e isso é a regra do produto vencendo, não defeito. Se estourar o tempo, refaça mais rápido. Segunda: as cinco lampadinhas não se contam da esquerda para a direita; o número é o conjunto aceso. Terceira: chip que diz USB ou BT em vez de cabo ou rádio é o desenho parado, e ali não houve leitura. E o que o mapa já declara: o DualSense não sabe que número ele é — o número é do Hefesto e não tem canal nenhum no aparelho, e o que o aparelho mostra são as lampadinhas. Tela e lampadinhas discordando é a metade que EXIBE quebrada, e é isso que se anota.

---

## mapa-plataforma.taxa_relatorios-cabo — Taxa de relatórios de entrada · cabo

*Célula:* `plataforma.taxa_relatorios @ cabo`

**O que isto prova.** Prova que o Hefesto mostra, para cada controle do cabo, com que frequência o giroscópio dele está sendo entregue ao controle virtual que o jogo enxerga — e que pelo cabo esse número fica firme.

**Onde olhar.** Na aba Controles, na faixa do alto do card de cada controle — a linha em que estão a cor do plástico e a palavra cabo ou rádio. Ali, ao lado, fica a frase "Giroscópio: fluindo para o jogo", com um número e a palavra Hz entre parênteses. Na mesma faixa estão os dois interruptores, Giroscópio e Acelerômetro. A frase só aparece quando o giroscópio daquele controle está mesmo chegando ao controle virtual; sem isso ela some, e o sumiço, por si só, não é alarme. Na aba Jogar, a linha "Status" diz Ligado ou Desligado — no Desligado não existe controle virtual e a frase não tem do que falar.

**Os passos.**

1. Feche o jogo, se ele estiver aberto.
2. Abra o Hefesto e clique na aba Jogar.
3. Confira que a linha "Status" está em "Ligado".
4. Clique na aba Controles.
5. Ache a faixa do alto do card do P1 e confira que o interruptor "Giroscópio" está aceso.
6. Leia a frase "Giroscópio: fluindo para o jogo" na faixa do P1 e anote o número dela.
7. Conte até dez e leia o número do P1 de novo; anote o segundo valor embaixo do primeiro.
8. Leia o número do P2 e anote; conte até dez e leia de novo.
9. Anote também o número que aparece no P3 e no P4, sem mexer em nenhum dos dois.
10. Pegue o P1 na mão e gire-o devagar de um lado para o outro por uns cinco segundos.
11. Leia o número do P1 outra vez e anote o terceiro valor.
12. Clique no interruptor "Giroscópio" da faixa do P1 para desligá-lo.
13. Confira que a frase do P1 sumiu e que as frases dos outros três continuam lá.
14. Clique de novo no interruptor "Giroscópio" do P1 e confira que a frase dele volta.

**Passa quando.** Nos dois controles do cabo a frase aparece com um número, e o número fica firme perto de 250 nas três leituras — não vai a zero, não some e não pula para valores muito diferentes a cada olhada. Girar o P1 na mão não derruba o número dele. E desligar o interruptor Giroscópio do P1 apaga a frase DELE e só dela; ligar de volta a devolve.

**Por controle.**

* **P1** — Cabo, e é o que você lê três vezes e gira na mão. É também o único em que você mexe no interruptor Giroscópio. Esperado: número firme, perto de 250.
* **P2** — Cabo, e é o segundo a ser lido, duas vezes. Mesmo esperado: firme, perto de 250. Se os dois do cabo derem números bem diferentes um do outro, anote os dois lado a lado — é aí que a diferença aparece.
* **P3** — Rádio, e é testemunha. Anote o número dele sem tocar em nada. Ele existe aqui para comparação com a linha do rádio deste mesmo par — e para provar que desligar o giroscópio do P1 não apaga a frase dele.
* **P4** — Rádio, e é a segunda testemunha. Mesma coisa. Se desligar o interruptor do P1 apagar a frase do P3 ou do P4, o comando pegou a mesa inteira em vez do controle escolhido, e esse é o achado.

**A armadilha.** O número NÃO é a taxa do controle. Ele é a velocidade com que o Hefesto entrega o giro ao controle virtual que o jogo vê, e essa entrega tem um TETO de 250 por segundo. Por isso 250 no cabo é o esperado e é também o teto: um controle que entregasse mais apareceria exatamente igual. Segunda: a frase some, e o sumiço é a resposta certa, em três casos — no Modo Nativo, com a máscara Xbox 360 e num controle que não esteja alimentando controle virtual nenhum. Confira o Status e a máscara antes de reprovar por ausência. Terceira, e é a que mais engana: fora do modo de vários jogadores, só o controle PRINCIPAL tem esse espelho de giro. Se a frase aparecer num só dos quatro, isso não é defeito — é que os outros três não têm o que mostrar. Quarta: nada aqui prova que o jogo usou aquele giro; o que este número mede é a entrega ao controle virtual, e o mapa não registra medição do outro lado.

---

## mapa-plataforma.taxa_relatorios-radio — Taxa de relatórios de entrada · rádio

*Célula:* `plataforma.taxa_relatorios @ rádio`

**O que isto prova.** Prova que a mesma frase de entrega do giroscópio aparece nos dois controles do rádio — e revela que o número mostrado ali é o teto do Hefesto, não o que o aparelho entrega.

**Onde olhar.** Na aba Controles, na faixa do alto do card de cada controle — a linha com a cor do plástico e a palavra cabo ou rádio. Ali fica a frase "Giroscópio: fluindo para o jogo", com um número e a palavra Hz entre parênteses, e os interruptores Giroscópio e Acelerômetro. Na aba Jogar, a linha "Status" tem de estar em "Ligado": no Desligado não existe controle virtual e a frase não tem do que falar.

**Os passos.**

1. Faça a linha do cabo deste mesmo par antes desta, e tenha à mão o papel com os números do P1 e do P2.
2. Feche o jogo, se ele estiver aberto.
3. Abra o Hefesto na aba Jogar e confira que a linha "Status" está em "Ligado".
4. Clique na aba Controles.
5. Confira, na faixa do card do P3, que depois da cor do plástico está escrita a palavra rádio.
6. Confira que o interruptor "Giroscópio" do P3 está aceso.
7. Leia a frase do P3 e anote o número.
8. Conte até dez e leia de novo; anote o segundo valor.
9. Conte até dez e leia uma terceira vez; anote o terceiro valor.
10. Faça as três leituras também no P4, anotando os três valores.
11. Ponha os números do P3 e do P4 lado a lado com os do P1 e do P2 no papel.
12. Leve o P3 para o outro lado da sala, o mais longe do PC que der.
13. Volte à tela e leia o número do P3; anote.
14. Traga o P3 de volta para a mesa e leia mais uma vez.
15. Confira que os números do P1 e do P2 não mudaram em nenhuma dessas leituras.

**Passa quando.** A frase aparece nos dois controles do rádio, com um número, e não some enquanto eles estiverem entregando o giro. Se os números do rádio saírem iguais aos do cabo — perto de 250 nos quatro —, isso não é você errando: anote os quatro lado a lado, porque é justamente o achado desta linha.

**Por controle.**

* **P1** — Cabo, e é testemunha. Não toque nele. O número dele tem de continuar firme enquanto você lê e passeia com os do rádio. Ele é a régua de comparação: sem o número dele no papel, o do rádio não diz nada.
* **P2** — Cabo, e é a segunda testemunha. Mesma coisa. Se o número do P1 ou do P2 se mexer quando você afasta o P3, anote — a distância de um não devia alcançar o outro.
* **P3** — Rádio, e é ESTE. Três leituras paradas, uma leitura longe do PC e uma leitura de volta na mesa. Pelo rádio a entrega vem em rajadas, então oscilar entre leituras é o normal, não o defeito.
* **P4** — Rádio, e é o segundo. Três leituras paradas, sem sair da mesa. Ele mostra se a variação é do rádio inteiro ou só do controle que você afastou.

**A armadilha.** O teto é o mesmo nos dois transportes, e é ele que engana. O número que a tela mostra é a entrega do Hefesto ao controle virtual, e ela é capada em 250 por segundo. Pelo cabo a entrega é firme; pelo rádio ela vem em rajadas — medido nesta casa, a média de janelas seguidas do MESMO controle foi de 38 a 392 por segundo, sem que nada mudasse. Logo, um número parado em 250 pelo rádio não é o aparelho: é o teto achatando o que passava por cima. NÃO reprove por causa disso — anote os quatro números, porque é isso que a linha existe para revelar. Segunda: número que oscila muito entre uma leitura e outra pelo rádio também não é defeito. Terceira: a frase some, e o sumiço é o certo, no Modo Nativo, com a máscara Xbox 360 e em controle que não alimenta controle virtual nenhum; e, fora do modo de vários jogadores, só o controle principal tem essa frase. Confira isso antes de reprovar por ausência. Quarta: nada aqui prova que o jogo recebeu o giro nessa velocidade — o mapa não registra medição do lado do jogo.

---

## mapa-plataforma.transporte_radio-cabo — Transporte de rádio (tipo de link) · cabo

*Célula:* `plataforma.transporte_radio @ cabo`

**O que isto prova.** Prova que o Hefesto acerta, para os dois controles do cabo, por onde eles estão falando — e que a resposta não muda quando o cabo troca de entrada USB.

**Onde olhar.** Três lugares, e eles têm de concordar. Na fita do topo, a linha que começa com "Selecionar:": cada chip termina com a palavra cabo ou a palavra rádio. No alto, a contagem, no formato "4 controles: 2 USB · 2 BT". Na aba Conexões, o quadro Gestão de Controles, onde cada linha termina em USB ou em BT. E, na aba Controles, na faixa do alto de cada card, logo depois da cor do plástico, aparece de novo a palavra cabo ou rádio.

**Os passos.**

1. Confira que o P1 e o P2 estão no cabo e que o P3 e o P4 estão no rádio, sem cabo nenhum neles.
2. Abra o Hefesto e clique na aba Controles.
3. Leia os quatro chips da fita do topo e anote a palavra do fim de cada um.
4. Leia a contagem no alto e anote.
5. Clique na aba Conexões e leia as quatro linhas do quadro Gestão de Controles; anote se cada uma termina em USB ou em BT.
6. Confira que os três lugares dizem a mesma coisa sobre cada um dos quatro.
7. Puxe o cabo do P1 de dentro do PC — do lado do PC, nunca do lado do controle.
8. Encaixe-o numa entrada USB diferente do PC, sem demorar.
9. Conte até dez, devagar.
10. Leia o chip do P1: tem de dizer cabo, nunca rádio.
11. Leia a contagem do alto: tem de continuar em 2 USB e 2 BT.
12. Repita os passos 7 a 11 com o cabo do P2, numa terceira entrada USB.
13. Olhe os chips do P3 e do P4 e confira que os dois continuaram dizendo rádio o tempo todo.

**Passa quando.** Os dois controles do cabo dizem cabo nos três lugares, antes e depois de trocar de entrada USB, e a contagem do alto volta a dizer 2 USB e 2 BT. Os dois do rádio nunca trocam de palavra, nem enquanto os cabos estão fora.

**Por controle.**

* **P1** — Cabo, e é o primeiro a mudar de entrada. Tem de dizer cabo nos três lugares antes e depois, e não pode passar por rádio no meio do caminho.
* **P2** — Cabo, e é o segundo a mudar de entrada. Mesma conferência. Faça um de cada vez: com os dois fora ao mesmo tempo a contagem do alto muda por dois motivos e você não separa qual foi.
* **P3** — Rádio, e é testemunha. Não encoste nele. A palavra do chip dele tem de continuar rádio enquanto os cabos vão e vêm. Se ela virar cabo sem ninguém encostar, a leitura pegou a mesa em vez do controle.
* **P4** — Rádio, e é a segunda testemunha. Mesma conferência do P3. Os dois juntos provam que mexer no cabo de um não reescreve o transporte de quem está sem fio.

**A armadilha.** Chip que diz USB ou BT em vez de cabo ou rádio é o desenho parado, não a leitura viva: ali o teste não passou nem reprovou. (Na contagem do alto, USB e BT estão certos — foi decisão sua.) Segunda, e é a que o mapa declara: o Hefesto decide isto pelo TAMANHO do que o controle manda e pela entrada que o sistema mostra, e nenhum dos dois separa cabo de DADO de cabo de SÓ CARGA. Se você usar um cabo de carregador que não passa dado, o controle continua dizendo rádio com o cabo espetado — e isso está CERTO, porque a entrada dele continua chegando pelo rádio; o que a tela não conta é que ele está carregando. Não reprove: troque por um cabo de dado e refaça. Terceira: puxe o cabo do lado do PC. Mexer no encaixe do controle o derruba, e o lugar dele fica guardado só por trinta segundos.

---

## mapa-plataforma.transporte_radio-radio — Transporte de rádio (tipo de link) · rádio

*Célula:* `plataforma.transporte_radio @ rádio`

**O que isto prova.** Prova que os dois controles do rádio são lidos como rádio, e que espetar um cabo de dado num deles vira a resposta para cabo na hora — e ela volta para rádio quando o cabo sai.

**Onde olhar.** Na fita do topo, a linha que começa com "Selecionar:": cada chip termina com a palavra cabo ou rádio. No alto, a contagem, no formato "4 controles: 2 USB · 2 BT". Na aba Conexões, o quadro Gestão de Controles, onde cada linha termina em USB ou em BT. E, na aba Controles, na faixa do alto de cada card, logo depois da cor do plástico, a palavra cabo ou rádio.

**Os passos.**

1. Confira que o P3 e o P4 estão no rádio, sem cabo nenhum espetado neles.
2. Abra o Hefesto e clique na aba Controles.
3. Leia os quatro chips da fita e anote a palavra do fim de cada um.
4. Leia a contagem no alto e anote.
5. Separe um cabo que você sabe que passa dado — um igual ao que o P1 está usando serve.
6. Espete esse cabo no P3 e depois no PC.
7. Conte até dez, devagar, olhando a fita.
8. Leia o chip do P3: tem de ter virado cabo.
9. Leia a contagem do alto: tem de dizer 3 no cabo e 1 no rádio.
10. Olhe o chip do P4 e confirme que ele continua dizendo rádio.
11. Puxe o cabo do P3 de dentro do PC.
12. Conte até dez, devagar.
13. Leia o chip do P3 de novo: tem de ter voltado a dizer rádio, e com o mesmo número de antes.
14. Leia a contagem: tem de voltar a 2 no cabo e 2 no rádio.
15. Confira que os chips do P1 e do P2 disseram cabo do começo ao fim.

**Passa quando.** O P3 vira cabo em menos de dez segundos com o cabo de dado espetado, e volta a dizer rádio em menos de dez segundos quando o cabo sai — com o mesmo número de jogador nas duas pontas. O P4 diz rádio o tempo inteiro, e o P1 e o P2 dizem cabo o tempo inteiro. A contagem do alto acompanha as duas viradas.

**Por controle.**

* **P1** — Cabo, e é testemunha. Não encoste nele. Tem de dizer cabo do começo ao fim, e a contagem só pode mudar por causa do P3.
* **P2** — Cabo, e é a segunda testemunha. Mesma conferência do P1.
* **P3** — Rádio, e é ESTE. Recebe o cabo de dado, tem de virar cabo, e tem de voltar a rádio quando o cabo sai. Confira também o número dele nas duas pontas — a palavra pode mudar, o número não.
* **P4** — Rádio, e é a testemunha que mais importa: ele está no mesmo tipo de conexão do P3. Se ele também virar cabo quando você espeta o cabo no P3, a leitura pegou o rádio inteiro em vez do controle escolhido, e é esse o achado.

**A armadilha.** O cabo errado inventa um defeito. O Hefesto decide isto pelo TAMANHO do que o controle manda e pela entrada que o sistema mostra, e nenhum dos dois separa cabo de DADO de cabo de SÓ CARGA: com um cabo de carregador o P3 continua dizendo rádio, espetado e carregando — e isso está CERTO, porque a entrada dele continua vindo pelo rádio. Se der isso, troque de cabo antes de anotar qualquer coisa. Segunda: chip que diz USB ou BT em vez de cabo ou rádio é o desenho parado, e ali não houve leitura. Terceira: espetar e tirar o cabo pode derrubar o P3 do rádio por um instante; se o chip dele sumir e voltar, isso sozinho não reprova — o que reprova é ele voltar com OUTRO número, e mesmo aí confira se você não passou dos trinta segundos, que é o prazo em que o lugar fica guardado.

---

## mapa-plataforma.udev_autosuspend-cabo — Regra udev — o controle nunca dorme no barramento USB · cabo

*Célula:* `plataforma.udev_autosuspend @ cabo`

**O que isto prova.** Prova que o sistema está proibido de pôr as entradas USB para dormir — que é o que faz um controle no cabo cair sozinho, sem aviso, no meio do jogo.

**Onde olhar.** Na aba Conexões, no quadro Check-up. A linha "Energia das portas", com o selo ao lado dela (CERTO, AJUSTAR ou NOTA) e a frase que explica: ela conta QUANTAS entradas USB foram olhadas e quantas podem entrar em economia de energia. No mesmo quadro fica o botão "Examinar Portas", que refaz o exame. A linha vizinha, "Economia de energia desligada", é OUTRA coisa: ela fala do adaptador do rádio, não das entradas do cabo.

**Os passos.**

1. Confira que o P1 e o P2 estão ligados pelo cabo, cada um na sua entrada USB.
2. Abra o Hefesto e clique na aba Conexões.
3. Ache o quadro Check-up.
4. Clique no botão "Examinar Portas".
5. Leia a linha "Energia das portas": anote o selo e a frase inteira, com o número de entradas que ela cita.
6. Puxe os dois cabos de dentro do PC.
7. Clique em "Examinar Portas" de novo.
8. Leia a linha "Energia das portas" outra vez e anote o novo número de entradas.
9. Compare os dois números: o segundo tem de ser menor que o primeiro.
10. Encaixe os dois cabos de volta, cada um na entrada de onde saiu.
11. Clique em "Examinar Portas" mais uma vez.
12. Confira que o número de entradas voltou ao do passo 5 e que o selo continua o mesmo.
13. Leia também a linha "Economia de energia desligada", logo ali no mesmo quadro, e anote o selo e a frase dela.

**Passa quando.** Com os dois cabos espetados, a linha "Energia das portas" traz o selo CERTO e diz que NENHUMA das entradas USB está em economia de energia. E o número de entradas cai quando você tira os dois cabos e sobe de volta quando você os devolve — é essa mexida no número que prova que os dois controles estavam entre as entradas contadas.

**Por controle.**

* **P1** — Cabo, e é uma das entradas contadas. Tire e devolva o cabo dele e veja o número da frase mexer. Se o número não mexer com nenhum dos dois, esta linha não está olhando os seus controles.
* **P2** — Cabo, e é a outra entrada contada. Mesmo gesto. Tirando os dois juntos, a queda tem de ser de duas entradas, não de uma.
* **P3** — Rádio, e ele NÃO aparece nesta linha — de propósito. Sem cabo, o controle não está no barramento USB e não há entrada dele para pôr para dormir. Quem responde por ele é a linha vizinha, "Economia de energia desligada", que fala do adaptador do rádio: leia o selo dela e anote.
* **P4** — Rádio, igual ao P3. Não aparece nesta linha, e é coberto pela mesma linha vizinha do adaptador. Se o selo de "Economia de energia desligada" não estiver em CERTO, anote a frase inteira — ela diz o que falta e o que fazer.

**A espera.** São vinte minutos, e nenhum deles é para ficar olhando a tela. Depois de conferir a linha e devolver os dois cabos, deixe o P1 e o P2 espetados e PARADOS na mesa, sem tocar em nenhum dos dois — é ficar parado que faz uma entrada adormecida derrubar o controle. Marque um alarme de vinte minutos e vá fazer as outras linhas desta leva; não desencaixe nada nesse tempo. Quando o alarme tocar, volte à fita do topo do Hefesto: os dois chips têm de continuar lá, dizendo cabo, com os mesmos números. Mexa então no analógico de cada um e confira que os dois respondem. Se algum tiver caído sozinho enquanto estava parado, anote a hora — é esse o defeito que esta linha existe para pegar.

**A armadilha.** A frase conta QUANTAS entradas, nunca QUAIS. Um CERTO com os dois cabos fora não diz coisa nenhuma sobre os seus controles — é exatamente por isso que o exame se faz com eles espetados, e é por isso que este teste tira e devolve os cabos: para ver o número mexer. Segunda: o selo tem três palavras, e NOTA não é passa nem reprova — ela quer dizer que este sistema não deixou ler o estado das entradas USB. Anote e não conte como verde. Terceira: não misture as duas linhas do quadro. "Economia de energia desligada" é do adaptador do rádio, e ela pode dizer que a regra está no lugar mas só passa a valer no próximo encaixe do adaptador — isso é verdade sobre o rádio e não tem nada a ver com esta linha. Quarta: se você trocou cabos de entrada em algum teste anterior, o número de entradas já pode ter mudado por causa disso; clique em "Examinar Portas" e leia de novo antes de comparar.

---

## mapa-plataforma.vigia_zumbi-cabo — Vigia de zumbi (link de pé e controle mudo) · cabo

*Célula:* `plataforma.vigia_zumbi @ cabo`

**O que isto prova.** Prova que um controle do cabo nunca fica na tela sem responder: se o caminho por onde ele fala envelhecer, o Hefesto o troca sozinho em poucos segundos.

**Onde olhar.** Duas coisas ao mesmo tempo, e é o par delas que decide. Primeira, o chip do controle na fita do topo — ele dizendo que o controle está conectado. Segunda, na aba Controles com o card daquele controle aberto, o pontinho do analógico, que anda quando você mexe no analógico do aparelho, e o desenho do botão, que acende quando você o aperta. Controle são é chip na fita e card respondendo; o que se caça é o par errado — chip na fita e card mudo. A fonte não diz onde se lê, dentro do Hefesto, que a troca aconteceu: o que se enxerga é o resultado, o card voltando a responder.

**Os passos.**

1. Abra o Hefesto e clique na aba Controles.
2. Clique na linha do P1 para abrir o card dele.
3. Mexa no analógico esquerdo do P1 e confirme que o pontinho anda no desenho.
4. Aperte o botão Círculo do P1 e confirme que o desenho dele acende.
5. Puxe o cabo do P1 de dentro do PC.
6. Encaixe-o de volta na mesma entrada, sem demorar.
7. Repita o par tirar-e-pôr mais quatro vezes seguidas, contando até três entre uma e outra.
8. Espere o chip do P1 reaparecer na fita do topo.
9. Mexa no analógico esquerdo do P1 e conte até cinco olhando o pontinho.
10. Aperte o Círculo do P1 e confira que o desenho acende.
11. Clique na linha do P2 para abrir o card dele e faça nele os passos 3 a 10.
12. Mexa no analógico do P3 e no do P4, um de cada vez, e confirme que os dois continuam respondendo.
13. Confira que os chips do P3 e do P4 não sumiram da fita em nenhum instante.

**Passa quando.** Depois de cada vaivém do cabo, o controle volta à fita E volta a responder — o pontinho anda e o botão acende — em poucos segundos, sem você fechar nem reabrir nada. O que reprova é o par errado: o chip do controle na fita, dizendo que ele está lá, e o card mudo, sem pontinho e sem botão aceso, por mais de dez segundos.

**Por controle.**

* **P1** — Cabo, e é o primeiro a levar o vaivém. Cinco vezes tirando e pondo o cabo, e no fim o pontinho e o botão têm de voltar. Se ele voltar à fita e ficar mudo, anote a hora exata.
* **P2** — Cabo, e é o segundo. Mesmo gesto. Faça um de cada vez: os dois cabos indo e vindo juntos esconde de qual dos dois veio o problema.
* **P3** — Rádio, e é testemunha. Não encoste nele. O chip dele não pode sumir da fita e ele tem de continuar respondendo no card enquanto você mexe nos cabos.
* **P4** — Rádio, e é a segunda testemunha. Igual ao P3. Se os dois do rádio ficarem mudos junto com o vaivém do cabo, o estrago atravessou de um transporte para o outro, e é esse o achado.

**A armadilha.** Este teste passar no cabo NÃO diz nada sobre o rádio, e o mapa já explica por quê: pelo rádio existe, dentro do controle, um contador de vida que fica congelado. Uma checagem construída sobre ele funcionaria perfeitamente no cabo e seria CEGA no rádio — a pior forma de defeito, porque passa em todo teste feito com o cabo espetado. Verde aqui obriga a fazer a linha do rádio deste mesmo par. Segunda: a troca acontece em passadas de dois em dois segundos, então julgar no primeiro segundo dá vermelho falso — conte até cinco antes de decidir. Terceira: sumir da fita e voltar não é reprovação; uma queda honesta é o produto dizendo a verdade. O que reprova é ficar na fita e emudecer. Quarta: nada disto foi medido no aparelho até hoje — o mapa registra a leitura como achado de fonte, não como bancada. O seu resultado aqui vale mais que o que está escrito lá.

---

## mapa-plataforma.vigia_zumbi-radio — Vigia de zumbi (link de pé e controle mudo) · rádio

*Célula:* `plataforma.vigia_zumbi @ rádio`

**O que isto prova.** Prova que um controle do rádio nunca fica na tela sem responder — e é aqui que esse defeito se esconde, porque nenhum teste feito com o cabo o alcança.

**Onde olhar.** Duas coisas ao mesmo tempo, e é o par delas que decide. Primeira, o chip do controle na fita do topo, dizendo que ele está conectado. Segunda, na aba Controles com o card daquele controle aberto, o pontinho do analógico, que anda quando você mexe no analógico do aparelho, e o desenho do botão, que acende quando você o aperta. Controle são é chip na fita e card respondendo; o que se caça é o par errado — chip na fita e card mudo. A fonte não diz onde se lê, dentro do Hefesto, que a troca aconteceu: o que se enxerga é o resultado, o card voltando a responder.

**Os passos.**

1. Abra o Hefesto e clique na aba Controles.
2. Clique na linha do P3 para abrir o card dele.
3. Mexa no analógico esquerdo do P3 e aperte o botão Círculo dele.
4. Confira que o pontinho anda e que o desenho do botão acende.
5. Segure o botão PS do P3 até todas as luzes dele apagarem, dê um toque curto no mesmo botão para religá-lo e, quando o chip dele voltar à fita do topo, mexa no analógico contando até cinco.
6. Confira que o pontinho voltou a andar dentro desses cinco segundos.
7. Repita esse desligar, religar e conferir mais duas vezes, uma atrás da outra.
8. Leve o P3 ligado para o cômodo ao lado, feche a porta, conte até vinte longe da tela e volte com ele para a mesa.
9. Confira na fita do topo qual das três coisas aconteceu — o chip dele saiu, saiu e voltou, ou ficou lá o tempo todo — e anote.
10. Mexa no analógico do P3 e conte até dez olhando o pontinho.
11. Confira que ele voltou a andar dentro desses dez segundos.
12. Clique na linha do P4 e faça nele as três voltas de desligar e religar, com a mesma conferência do analógico, sem sair da mesa.
13. Mexa nos analógicos do P1 e do P2, um de cada vez.
14. Confira que os dois continuam respondendo.

**Passa quando.** Depois de cada volta — do desligar e religar, e do passeio até o outro cômodo — o P3 e o P4 voltam a responder no card em poucos segundos. O que reprova é o par errado: o chip do controle na fita, dizendo que ele está lá, e o pontinho parado com o botão apagado por mais de dez segundos. Sumir da fita e voltar não reprova.

**Por controle.**

* **P1** — Cabo, e é testemunha. Não encoste nele. Tem de continuar respondendo no card enquanto os do rádio saem e voltam, e o chip dele não pode piscar para fora da fita.
* **P2** — Cabo, e é a segunda testemunha. Igual ao P1.
* **P3** — Rádio, e é ESTE. Três voltas de desligar e religar, mais o passeio até o outro cômodo. É nele que o defeito desta linha se esconde: um P3 que fica na fita sem responder é exatamente o que ninguém enxergaria com o cabo espetado.
* **P4** — Rádio, e é o segundo. Três voltas de desligar e religar, sem sair da mesa. Ele separa o que é do rádio inteiro do que é só do controle que você afastou.

**A armadilha.** É AQUI que o defeito mora, e o mapa diz por quê: pelo rádio existe, dentro do controle, um contador de vida que fica congelado, e uma checagem construída sobre ele passa sempre no cabo e não enxerga nada no rádio. Então um P3 que fique na fita e não responda é o achado inteiro desta leva — anote a hora exata. Segunda: sair da fita ao ir para o outro cômodo é o CERTO, e não defeito; o que se caça é o contrário, o chip que fica e o controle que emudece. Terceira: a troca acontece em passadas de dois em dois segundos; conte até cinco antes de decidir, ou você dá vermelho no seu próprio relógio. Quarta: nada disto foi medido no aparelho até hoje — o mapa registra a leitura como achado de fonte, e o seu resultado aqui é a primeira medição que esta casa vai ter.

---

## mapa-plataforma.vpad-cabo — Gamepad virtual (vpad) que o Hefesto cria · cabo

*Célula:* `plataforma.vpad @ cabo`

**O que isto prova.** Prova que o Hefesto cria um controle virtual para cada um dos dois controles do cabo, e que cada aparelho está preso ao controle virtual certo.

**Onde olhar.** Na aba Controles. Passe o mouse sobre o NOME do controle, no alto do card dele — a parte onde estão a cor do plástico e a palavra cabo ou rádio. Aparece uma dica dizendo "Alimenta o gamepad virtual do Jogador N", com um endereço entre parênteses; quando não há nenhum, a dica diz "Este controle ainda não alimenta gamepad virtual nenhum". Na mesma faixa, ao lado do nome, está a máscara — DualSense, Xbox 360 ou Nintendo Pro —, que é o desenho de botões que o jogo vê; um asteriscozinho ao lado dela quer dizer que a emulação saiu no modo simples, e o motivo aparece ao passar o mouse nele. Na aba Jogar, a linha "Status" diz Ligado ou Desligado. O aviso do modo simples NÃO fica na aba Jogar: ele é o asteriscozinho ao lado da máscara, na aba Controles, e o motivo aparece ao parar o mouse nele.

> **A coluna Atenção saiu da aba Jogar em 07/09/2026**, por ordem dela (*"em jogar remover essa seção do atenção, nenhum aviso esse — deixar só o reconectar controles"*). O selo GAMEPAD morava lá. O fato não se perdeu — o asteriscozinho da aba Controles diz a mesma coisa, e diz por CONTROLE em vez de para a mesa inteira, que é o que esta célula precisa.

**Os passos.**

1. Feche o jogo, se ele estiver aberto.
2. Abra o Hefesto e clique na aba Jogar.
3. Confira que a linha "Status" está em "Ligado" — no Modo Nativo não existe controle virtual nenhum e este teste não roda.
4. Na aba Controles, olhe se há asteriscozinho ao lado da máscara de cada controle; havendo, pare o mouse nele e anote o que a dica diz.
5. Clique na aba Controles.
6. Passe o mouse sobre o nome do P1, no alto do card dele, e espere a dica aparecer.
7. Leia a dica e anote de qual jogador é o controle virtual que o P1 alimenta.
8. Passe o mouse sobre o nome do P2 e anote a dica dele do mesmo jeito.
9. Compare as duas: têm de nomear jogadores DIFERENTES.
10. Olhe a máscara ao lado do nome do P1 e do P2 e anote a palavra que aparece em cada um.
11. Confira se há um asteriscozinho ao lado de alguma das duas máscaras; se houver, passe o mouse nele e anote o motivo por escrito.
12. Passe o mouse sobre o nome do P3 e do P4 e anote as dicas dos dois.
13. Confira que as quatro dicas nomeiam quatro jogadores diferentes, sem nenhum repetido.

**Passa quando.** Cada um dos dois controles do cabo tem uma dica dizendo que alimenta o controle virtual de um jogador, e os dois jogadores são diferentes. Nenhum dos dois diz "ainda não alimenta gamepad virtual nenhum", e nenhum dos dois traz o asteriscozinho da emulação em modo simples ao lado da máscara.

**Por controle.**

* **P1** — Cabo. A dica dele tem de nomear um controle virtual, com jogador. Anote o número do jogador e o endereço entre parênteses — é esse par que diz a qual controle virtual o aparelho na sua mão está preso.
* **P2** — Cabo. Mesma leitura, e o jogador tem de ser OUTRO. Dois controles nomeando o mesmo jogador é o defeito que este teste caça, e ele deixaria dois aparelhos empurrando o mesmo boneco.
* **P3** — Rádio, e é testemunha. A dica dele também tem de nomear um controle virtual — pelo rádio o Hefesto cria um igualzinho, sem diferença nenhuma. O que reprova aqui é ele repetir o jogador de alguém.
* **P4** — Rádio, e é a segunda testemunha. Igual ao P3. Se os quatro nomearem quatro jogadores diferentes, a amarração está certa; se dois se repetirem, anote quais dois e por qual conexão cada um estava.

**A armadilha.** A prova desta linha parou em MONTOU — o mapa registra que o controle virtual é CRIADO, e nada além disso. Então não julgue este teste dentro de um jogo: o que se prova aqui é que ele existe e está preso ao aparelho certo, não que o jogo reagiu. Segunda: a dica SOME quando não há nada a dizer, e sumiço não é a mesma coisa que "não alimenta nenhum". A frase escrita é uma resposta; a ausência dela é outra — anote qual das duas você viu. Terceira, e é a que quebra a mesa: trocar a máscara DESTRÓI e RECRIA o controle virtual, e com o jogo aberto isso deixa o jogo sem controle nenhum. Não troque máscara durante este teste, e nunca com jogo aberto. Quarta: no Modo Nativo não existe controle virtual, e a dica sumir ali é o certo — por isso o passo 3 confere o Status antes de tudo.

---

## mapa-plataforma.vpad-radio — Gamepad virtual (vpad) que o Hefesto cria · rádio

*Célula:* `plataforma.vpad @ rádio`

**O que isto prova.** Prova que os dois controles do rádio também ganham cada um o seu controle virtual — e que esse controle virtual nasce sempre com cara de cabo, mesmo com o aparelho sem fio.

**Onde olhar.** Na aba Controles. Passe o mouse sobre o NOME do controle, no alto do card dele — onde estão a cor do plástico e a palavra cabo ou rádio. A dica diz "Alimenta o gamepad virtual do Jogador N", com um endereço entre parênteses, e às vezes acrescenta com que nome ele aparece no sistema; quando não há nenhum, ela diz "Este controle ainda não alimenta gamepad virtual nenhum". Ao lado do nome fica a máscara — DualSense, Xbox 360 ou Nintendo Pro — com um asteriscozinho quando a emulação saiu em modo simples. Na aba Jogar, a linha "Status". (A coluna **Atenção** saiu da aba Jogar em 07/09/2026, por ordem dela; o aviso do modo simples é o asteriscozinho ao lado da máscara, na aba Controles.) Para saber se o JOGO enxerga o controle virtual como de cabo ou de rádio, a fonte não diz onde se lê isso dentro do Hefesto: o lugar mais próximo é a lista de controles da Steam, e se ela não disser por onde cada um está ligado, anote que não deu para ler.

**Os passos.**

1. Feche o jogo, se ele estiver aberto.
2. Abra o Hefesto e clique na aba Jogar.
3. Confira que a linha "Status" está em "Ligado".
4. Na aba Controles, olhe se há asteriscozinho ao lado da máscara de cada controle e anote o que a dica dele diz.
5. Clique na aba Controles.
6. Confira, no alto do card do P3, que depois da cor do plástico está escrita a palavra rádio.
7. Passe o mouse sobre o nome do P3 e espere a dica aparecer.
8. Anote de qual jogador é o controle virtual dele e, se a dica trouxer, o nome com que ele aparece no sistema.
9. Faça o mesmo no P4 e anote.
10. Compare as duas dicas: têm de nomear jogadores diferentes entre si, e diferentes dos do P1 e do P2.
11. Confira que nenhum dos dois traz o asteriscozinho ao lado da máscara.
12. Segure o botão PS do P3 até apagar e religue-o com um toque curto.
13. Espere o chip dele voltar à fita do topo e passe o mouse sobre o nome dele de novo.
14. Confira que a dica voltou a nomear um controle virtual, e anote se é o mesmo jogador de antes.
15. Abra a lista de controles da Steam, se ela estiver instalada, e anote quantos controles ela lista e o que ela diz sobre a conexão de cada um.

**Passa quando.** Os dois controles do rádio alimentam cada um o seu controle virtual, com jogadores diferentes entre si e diferentes dos dois do cabo, e nenhum dos dois diz "ainda não alimenta gamepad virtual nenhum". Depois de desligar e religar o P3, a dica dele volta a nomear um controle virtual.

**Por controle.**

* **P1** — Cabo, e é testemunha. Não encoste nele. A dica dele não pode trocar de jogador enquanto você mexe nos do rádio — se trocar, a mexida num controle reescreveu a amarração de outro.
* **P2** — Cabo, e é a segunda testemunha. Mesma conferência do P1.
* **P3** — Rádio, e é ESTE. Leia a dica dele, desligue-o e religue-o pelo PS, e leia a dica de novo. O jogador que ele alimenta tem de ser o mesmo antes e depois.
* **P4** — Rádio, e é o segundo. Leia a dica dele antes e depois de mexer no P3. Se o P4 perder a dica ou trocar de jogador quando você desliga o P3, o comando pegou o rádio inteiro em vez do controle escolhido, e é esse o achado.

**A armadilha.** O controle virtual NASCE SEMPRE COMO SE FOSSE DE CABO, mesmo com o aparelho no rádio — é de propósito, e é justamente isso que faz o jogo funcionar. Então, se a lista da Steam mostrar os quatro como controles de cabo, isso está CERTO e não é defeito: quem está no rádio é o aparelho na sua mão, não o controle que o jogo enxerga. Segunda: a prova desta linha parou em MONTOU — o mapa registra que o controle virtual é criado, e nada além; não julgue este teste dentro de um jogo. Terceira: desligar e religar pelo rádio pode devolver o controle a um jogador diferente se você demorar mais de trinta segundos, porque é esse o prazo em que o lugar fica guardado — passando dele, o que você viu foi a regra do produto, não defeito. Quarta: trocar a máscara destrói e recria o controle virtual; não faça isso durante este teste, e nunca com o jogo aberto. Quinta: a dica some quando não há nada a dizer, e sumiço não é o mesmo que a frase "ainda não alimenta gamepad virtual nenhum" — anote qual das duas você viu.

---

# toque

---

## mapa-toque.touchpad-cabo — Touchpad — os pontos de toque · cabo

*Célula:* `toque.touchpad @ cabo`

**O que isto prova.** Prova que, num controle ligado por cabo, o Hefesto enxerga o dedo no touchpad: a palavra muda e o pontinho acende no lugar onde o dedo está — e só no cartão daquele controle.

**Onde olhar.** Na aba Controles. Clique no chip «Todos» da fita do topo para abrir os quatro cartões. Dentro de cada cartão, na coluna da esquerda, tem a moldura Touchpad: na mesma linha do rótulo vem a palavra do estado — «Sem toque», «1 toque» ou um travessão — e, embaixo dela, um retângulo cinza com um pontinho ciano. O pontinho só aparece enquanto há dedo na superfície, e ele fica na POSIÇÃO do dedo: canto de cima à esquerda do retângulo é canto de cima à esquerda do touchpad. Com os quatro cartões abertos a caixa rola — role para ver os quatro. O travessão quer dizer «não consegui ler», e não é nem «Sem toque» nem «1 toque». Na fita do topo, cada controle é um chip com o número, a cor do plástico e a palavra do transporte: cabo ou rádio.

**Os passos.**

1. Abra o Hefesto e clique na aba Controles.
2. Clique no chip «Todos» da fita do topo, para abrir os quatro cartões.
3. Confira na fita que o P1 e o P2 dizem cabo, e que o P3 e o P4 dizem rádio.
4. Tire as mãos dos quatro controles e deixe-os parados na mesa.
5. Leia a palavra do Touchpad nos quatro cartões e anote: os quatro têm de dizer «Sem toque».
6. Confira que nenhum dos quatro retângulos tem pontinho aceso.
7. Encoste UM dedo, de leve, no canto de cima à esquerda do touchpad do P1, e mantenha-o lá.
8. Leia o cartão do P1: a palavra tem de virar «1 toque» e o pontinho tem de acender perto do canto de cima à esquerda do retângulo.
9. Olhe os cartões do P2, do P3 e do P4 com o seu dedo ainda apoiado no P1: os três têm de continuar em «Sem toque», sem pontinho.
10. Arraste o dedo devagar pelo touchpad do P1 até o canto de baixo à direita, sem tirá-lo da superfície.
11. Veja o pontinho do P1 andar junto, na mesma direção do dedo.
12. Tire o dedo do P1 e confira que a palavra volta a «Sem toque» e que o pontinho apaga.
13. Repita os passos 7 a 12 no P2, com os outros três largados na mesa.
14. Anote, para o P1 e para o P2, três coisas: se a palavra mudou, se o pontinho acendeu e se ele andou junto com o dedo.

**Passa quando.** Nos dois controles do cabo, a palavra vira «1 toque» no instante em que o dedo encosta e volta a «Sem toque» quando ele sai; o pontinho acende no lugar onde o dedo está e anda junto com ele. E, enquanto o seu dedo está num deles, os cartões dos outros três continuam em «Sem toque», sem pontinho nenhum.

**Por controle.**

* **P1** — Cabo, e é um dos dois que têm de responder. Encoste o dedo de leve, ande de um canto ao outro e tire. São três coisas a conferir: a palavra, o pontinho acendendo e o pontinho ANDANDO.
* **P2** — Cabo, e é o outro que tem de responder. Mesmos gestos, com os outros três largados na mesa. Se o P1 responder e o P2 não, o defeito não é do cabo — é do segundo lugar da fila.
* **P3** — Rádio, testemunha. Não encoste nele. Enquanto o seu dedo está num controle do cabo, o cartão do P3 tem de continuar em «Sem toque». Se ele acender junto, a tela está mostrando o toque de um controle no cartão de outro.
* **P4** — Rádio, segunda testemunha. Não encoste nele e confira o cartão dele do mesmo jeito. É o último da fila, e é nele que a leitura trocada costuma aparecer primeiro.

**A armadilha.** Um gesto por vez, e esta regra custou caro a esta casa: num ensaio pediu-se para girar o controle E passar o dedo ao mesmo tempo, o toque saiu ZERO, e por pouco não se escreveu que o produto não lia o touchpad. Gesto composto produz ausência falsa. O toque é LEVE: se você apertar até estalar, isso é o clique, e o clique é outro teste. O pontinho já mentiu de um jeito específico, e vale conhecer: ele acendia e apagava certo e ficava PARADO no ponto em que o desenho o cravou — se ele acender e não andar com o dedo, o defeito é esse, e não a sua mão. O travessão não é «Sem toque»: é «não consegui ler»; anote e não conte como passa. O cartão enxerga UM dedo só: pousar dois não faz aparecer «2 toques» — a palavra existe na tela, o dado ainda não; não reprove por isso. E se um chip da fita disser USB ou BT em vez de cabo ou rádio, a fita não está lendo os seus controles: são os dois chips do desenho, e nesse estado o teste não passou nem reprovou. Onde a prova parou: a casa provou que o toque entra no controle virtual que o jogo lê, e parou aí — o que o jogo faz com ele não está medido por esta linha.

---

## mapa-toque.touchpad-radio — Touchpad — os pontos de toque · rádio

*Célula:* `toque.touchpad @ rádio`

**O que isto prova.** Prova que o Hefesto enxerga o dedo no touchpad de um controle ligado por rádio do mesmo jeito que enxerga no cabo — e só no cartão daquele controle.

**Onde olhar.** Na aba Controles. Clique no chip «Todos» da fita do topo para abrir os quatro cartões. Dentro de cada cartão, na coluna da esquerda, tem a moldura Touchpad: na mesma linha do rótulo vem a palavra do estado — «Sem toque», «1 toque» ou um travessão — e, embaixo dela, um retângulo cinza com um pontinho ciano. O pontinho só aparece enquanto há dedo na superfície, e fica na POSIÇÃO do dedo. Com os quatro cartões abertos a caixa rola — role para ver os quatro. O travessão quer dizer «não consegui ler». Na fita do topo, cada controle é um chip com o número, a cor do plástico e a palavra do transporte: cabo ou rádio.

**Os passos.**

1. Abra o Hefesto e clique na aba Controles.
2. Clique no chip «Todos» da fita do topo, para abrir os quatro cartões.
3. Confira na fita que o P3 e o P4 dizem rádio, e que o P1 e o P2 dizem cabo.
4. Tire as mãos dos quatro controles e confira que os quatro cartões dizem «Sem toque», sem pontinho.
5. Encoste um dedo de leve no touchpad do P1, que está no cabo, e confira que o cartão dele responde — este é o controle de comparação, e sem ele o resto não mede nada.
6. Tire o dedo do P1 e não encoste mais nele.
7. Encoste UM dedo, de leve, no canto de cima à esquerda do touchpad do P3, e mantenha-o lá.
8. Leia o cartão do P3: a palavra tem de virar «1 toque» e o pontinho tem de acender perto do canto de cima à esquerda do retângulo.
9. Olhe os cartões do P1, do P2 e do P4 com o seu dedo ainda apoiado no P3: os três têm de continuar em «Sem toque», sem pontinho.
10. Arraste o dedo devagar pelo touchpad do P3 até o canto de baixo à direita, sem tirá-lo da superfície.
11. Veja o pontinho do P3 andar junto, na mesma direção do dedo.
12. Tire o dedo do P3 e confira que a palavra volta a «Sem toque» e que o pontinho apaga.
13. Repita os passos 7 a 12 no P4, com os outros três largados na mesa.
14. Anote, para o P3 e para o P4, se a palavra mudou, se o pontinho acendeu, se ele andou junto e se ele andou liso ou aos saltos.

**Passa quando.** Nos dois controles do rádio, a palavra vira «1 toque» com o dedo e volta a «Sem toque» sem ele, e o pontinho acende no lugar do dedo e anda junto. Para o resultado valer, o P1, que está no cabo, tem de ter respondido antes. E, enquanto o seu dedo está num do rádio, os cartões dos dois do cabo continuam em «Sem toque».

**Por controle.**

* **P1** — Cabo, e é o controle de comparação. Faça o gesto nele PRIMEIRO: se o cartão dele não responder, o que acontecer no rádio não mede nada. Depois disso ele vira testemunha e você não encosta mais nele.
* **P2** — Cabo, testemunha. Não encoste nele em momento nenhum. O cartão dele tem de ficar em «Sem toque» do começo ao fim.
* **P3** — Rádio, e é um dos dois que têm de responder. Dedo leve, andando de um canto ao outro, e o pontinho acompanhando. Repare também no ANDAR do pontinho: pelo rádio chegam menos leituras que pelo cabo.
* **P4** — Rádio, e é o outro que tem de responder. Mesmos gestos. Se o P3 responder e o P4 não, o defeito não é do rádio — é do segundo controle sem fio, e isso é outra coisa.

**A armadilha.** Um gesto por vez: num ensaio pediu-se para girar o controle E passar o dedo ao mesmo tempo, o toque saiu ZERO, e por pouco não se acusou o produto de não ler o touchpad. Gesto composto produz ausência falsa. Pelo rádio chegam menos leituras que do aparelho — medido em dez segundos de dedo: 2.807 contra 3.660 —, então o pontinho pode andar mais aos saltos que no cabo, e isso sozinho não reprova. O caso já conhecido, e ele é dela: pelo rádio o toque funciona FORA do jogo e não dentro. Se o pontinho andar aqui e o mesmo dedo não fizer nada dentro do jogo, isso já foi visto, o repasse até o controle virtual está inteiro e a perda é depois dele — continua sem causa. Anote e siga; não é erro seu. A casa também declarou uma ressalva que só existe no rádio: o som do microfone viaja no MESMO pacote em que viaja o toque. Se o pontinho de um controle do rádio acender ou pular sem dedo nenhum, olhe antes se o microfone daquele controle está ligado — o selo do cartão dele diz ATIVO ou MUDO — e anote as duas coisas juntas. O travessão não é «Sem toque»: é «não consegui ler». E o cartão enxerga UM dedo só: dois dedos não fazem aparecer «2 toques». Onde a prova parou: a casa provou que o toque entra no controle virtual que o jogo lê, e parou aí.

---

## mapa-toque.touchpad.clique-cabo — Touchpad — o clique (botão) · cabo

*Célula:* `toque.touchpad.clique @ cabo`

**O que isto prova.** Prova que o clique firme do touchpad de um controle no cabo é um clique de verdade, e que a recusa do Hefesto em transformá-lo em tecla está escrita na tela e é cumprida.

**Onde olhar.** Na aba Navegação, na tabela grande da direita, a que diz o que cada botão faz. O touchpad tem TRÊS linhas nela, uma por terço da superfície: Touchpad · Clique esquerdo, Touchpad · Clique direito e Touchpad · Clique central. Ao lado do nome de cada uma há uma marca cinza escrita «não dispara»; parando o mouse em cima dela sai a frase inteira, que diz que o touchpad do controle continua sendo o mouse do computador e que, enquanto for assim, o Hefesto não transforma o clique dele em tecla. Na ajuda do título dessa tabela — o «?» ao lado do nome — o fim do texto diz para qual controle ela vale: o que navega o PC, nomeado ali. À esquerda, no quadro «As opções de ativação», ficam o «Status do Modo» (Ligado ou Desligado) e a «Função do teclado». NÃO existe campo na tela que acenda com o clique do touchpad: o desenho do Touchpad na fileira de botões do cartão, na aba Controles, é alimentado pela lista de botões do controle, e o clique do touchpad não viaja nessa lista — ele fica apagado mesmo com o clique funcionando. A fonte não diz onde se lê o clique ao vivo; o que se lê é o efeito dele.

**Os passos.**

1. Abra a aba Navegação.
2. Abra a ajuda do título da tabela — o «?» ao lado do nome — e leia, no fim do texto, qual controle navega o PC; anote o número dele.
3. Confira na fita do topo que o P1 e o P2 dizem cabo.
4. Confira que o «Status do Modo», no quadro «As opções de ativação», está em Ligado — desligado, nada desta aba chega ao PC e o teste não mede nada.
5. Confira que a «Função do teclado», no mesmo quadro, está em «Só fora do jogo».
6. Confira que as três linhas do Touchpad, na tabela, têm a marca «não dispara» ao lado do nome.
7. Pare o mouse em cima de uma dessas marcas e leia a frase inteira.
8. Confira que ela fala do touchpad ser o mouse do computador, e anote.
9. Anote o que está escrito hoje na lista da linha Touchpad · Clique esquerdo e escolha «Espaço» nela.
10. Abra um editor de texto qualquer, num documento em branco, e leve a seta do mouse para dentro da área branca — o clique do touchpad é um clique de verdade e vai cair onde a seta estiver.
11. Aperte o touchpad do P1 com força, até sentir o estalo, no terço da ESQUERDA, depois no meio e depois no terço da direita.
12. Confira, em cada um dos três, que o editor recebeu um clique de mouse — o cursor de texto pulou para onde a seta estava.
13. Confira, em cada um dos três, que NÃO nasceu nenhum espaço no texto: a recusa que a tela anunciou tem de valer.
14. Aperte o touchpad do P2 nos três terços, do mesmo jeito.
15. Confira nele as mesmas duas coisas.
16. Aperte o touchpad do P3 e o do P4 até estalar.
17. Confira que neles também não nasce espaço nenhum.
18. Devolva a lista da linha Touchpad · Clique esquerdo ao que você anotou.
19. Abra, se quiser o dado do jogo, um jogo que use o clique do touchpad, aperte-o no P1 e anote o que acontecer — sem reprovar por isso.

**Passa quando.** As três linhas do Touchpad mostram a marca «não dispara», e a frase do hover explica por quê. O touchpad do P1 e o do P2 estalam quando apertados e o clique chega ao computador como clique de mouse. E nenhum dos quatro digita a tecla que você escolheu: a recusa é a mesma nos quatro, e o produto não finge ter aplicado.

**Por controle.**

* **P1** — Cabo, e é um dos dois que têm de responder. Aperte até estalar uma vez em cada terço: esquerda, meio e direita. Se ele for o controle que navega o PC, é nele que a recusa da tabela está sendo medida de verdade.
* **P2** — Cabo, e é o outro que tem de responder. Mesmos três apertos. Ele também prova que a escolha da tabela não vaza para um controle que não navega o PC.
* **P3** — Rádio, testemunha. Aperte o touchpad dele até estalar e confira que nenhuma tecla nasce. Se o espaço aparecer aqui, a escolha pegou o rádio inteiro em vez do controle escolhido.
* **P4** — Rádio, segunda testemunha. Mesmo aperto, mesma conferência. Se três recusarem e ele não, anote — é o último da fila, e é onde a escolha costuma escapar.

**A armadilha.** O clique é MECÂNICO: encostar o dedo não é clicar, tem de afundar até estalar. Toque de leve é o outro teste. A tabela vale para UM controle só, o que navega o PC, nomeado na ajuda do título — esperar que os quatro digitem é reprovar um produto que está certo. A marca «não dispara» não é defeito: é o produto avisando que, enquanto o touchpad do controle for o mouse do computador, ele não vira tecla, e que a escolha fica guardada para o dia em que isso mudar. Se a marca sumir e a tecla continuar não nascendo, aí sim há o que perguntar. O falso vermelho mais fácil é olhar a fileira de botões do cartão da aba Controles: o desenho do Touchpad ali não acende com o clique, porque ele é alimentado pela lista de botões do controle e o clique não viaja nessa lista — apagado ali não quer dizer que o clique não chegou. E não aperte com a seta do mouse em cima de qualquer janela: é um clique de verdade, e um clique cego já desfez configuração nesta casa. Onde a prova parou: a casa provou que o clique entra no pacote do controle virtual que o jogo lê, e parou aí. Este defeito já existiu de verdade — faltava uma linha de ligação e o clique NÃO chegava ao jogo; foi curada. Por isso o passo do jogo é anotação, e não reprovação. Sobre o tamanho: nove atos, um a mais que o alvo, porque este teste troca uma escolha da tabela e tem de devolvê-la no fim — deixar «Espaço» gravado ali muda o produto dela depois que você sair. O ato do jogo, o último, é opcional e só existe para colher o dado que falta.

## mapa-toque.touchpad.clique-radio — Touchpad — o clique (botão) · rádio

*Célula:* `toque.touchpad.clique @ rádio`

**O que isto prova.** Prova que o clique do touchpad de um controle no rádio é reconhecido e que a recusa em virar tecla é a mesma do cabo — e esta é a primeira vez que alguém mede isso com o dedo.

**Onde olhar.** Na aba Navegação, na tabela grande da direita, as TRÊS linhas do touchpad: Touchpad · Clique esquerdo, Touchpad · Clique direito e Touchpad · Clique central, cada uma com a marca cinza «não dispara» ao lado do nome e a frase inteira ao parar o mouse em cima dela. Na ajuda do título da tabela, no fim do texto, está o controle para o qual ela vale: o que navega o PC. À esquerda, no quadro «As opções de ativação», o «Status do Modo» (Ligado ou Desligado) e a «Função do teclado». E, na aba Controles, o cartão do P3 e o do P4: o selo do Microfone, que diz ATIVO, MUDO ou um travessão — ele entra neste teste por causa da armadilha, não por causa do clique. NÃO existe campo na tela que acenda com o clique do touchpad: o desenho do Touchpad na fileira de botões do cartão é alimentado pela lista de botões do controle, e o clique não viaja nessa lista. A fonte não diz onde se lê o clique ao vivo; o que se lê é o efeito dele.

**Os passos.**

1. Abra a aba Navegação.
2. Confira na fita do topo que o P3 e o P4 dizem rádio.
3. Confira que o «Status do Modo» está em Ligado e que a «Função do teclado» está em «Só fora do jogo».
4. Abra a ajuda do título da tabela e anote qual controle navega o PC.
5. Confira que as três linhas do Touchpad têm a marca «não dispara», e leia a frase de uma delas parando o mouse em cima.
6. Anote o que está escrito hoje na lista da linha Touchpad · Clique esquerdo, e escolha «Espaço» nessa lista.
7. Abra um editor de texto num documento em branco e leve a seta do mouse para dentro da área branca.
8. Aperte o touchpad do P1, que está no cabo, até estalar.
9. Confira que o editor recebeu o clique de mouse — é ele que prova que a sua mão e o editor estão medindo alguma coisa hoje.
10. Abra a aba Controles e leia o selo do Microfone do cartão do P3, e anote se ele diz ATIVO ou MUDO.
11. Volte ao editor de texto, com a seta dentro da área branca.
12. Aperte o touchpad do P3 até estalar, com força, uma vez em cada terço: primeiro na ESQUERDA, depois no meio, depois na direita.
13. Confira, a cada aperto, que o editor recebeu um clique de mouse e que NÃO nasceu espaço nenhum no texto.
14. Aperte o touchpad do P3 mais umas dez vezes seguidas, em qualquer terço.
15. Aperte o botão PS do P3 uma vez.
16. Confira que o PS ainda responde, e leia de novo o selo do Microfone do P3 para ver se ele continua no que você anotou.
17. Aperte o botãozinho de microfone do P3 no plástico, para trocar o estado dele, e refaça a volta que vai dos três terços até a leitura do selo.
18. Refaça a volta inteira no P4, também com o microfone nos dois estados.
19. Aperte o touchpad do P1 e o do P2 até estalar.
20. Confira que também neles não nasce tecla nenhuma.
21. Devolva a lista da linha Touchpad · Clique esquerdo ao que você anotou.

**Passa quando.** O touchpad do P3 e o do P4 estalam e o clique chega ao computador como clique de mouse, igual ao do cabo. Nenhum dos quatro digita a tecla escolhida. E a sequência de apertos no rádio não prende nem embaralha nada: o botão PS dos dois continua respondendo e o selo do microfone deles não vira sozinho.

**Por controle.**

* **P1** — Cabo, e é o controle de comparação. Aperte primeiro nele e confirme o estalo e o clique no editor. Depois vira testemunha: aperte-o de novo só no fim, para conferir que ele também não digita.
* **P2** — Cabo, testemunha. Só no fim: um aperto até estalar, e nenhuma tecla pode nascer.
* **P3** — Rádio, e é um dos dois que têm de responder. Três apertos, um por terço, e depois uma sequência de dez. Faça tudo isso DUAS vezes: uma com o microfone dele ATIVO e outra com ele MUDO, trocando pelo botãozinho do plástico.
* **P4** — Rádio, e é o outro. Mesmos apertos. Se o P3 aguentar a sequência e o P4 não, anote: são dois controles no mesmo tipo de conexão, e é aí que a diferença aparece.

**A armadilha.** Ninguém nunca pôs o dedo neste touchpad com o controle no rádio para ver o clique chegar: o que a casa sabe deste caminho veio de leitura de código, não de bancada. O que sair daqui é medição nova — anote tudo, inclusive o que parecer óbvio. A armadilha que só existe no rádio mora exatamente no clique: com o microfone ligado, o controle manda o SOM dentro do mesmo pacote em que manda o clique, o botão PS e o mudo do microfone, e os bytes do som caem em cima justamente desse byte. Foi assim que o PS e o microfone ficaram presos nesta máquina. Existe uma guarda que separa uma coisa da outra, e é ela que este teste está espremendo: se, depois da sequência de apertos com o microfone ativo, o PS parar de responder, o selo do microfone virar sozinho, ou aparecer um clique que ninguém deu — isso é o achado, e é o mais valioso deste lote. Troque o estado do microfone pelo botãozinho do PLÁSTICO, nunca pelo botão de microfone da tela: aquele passa o comando do mudo para o Hefesto, o botão do plástico daquele controle para de valer, e a volta é reiniciar o Hefesto. O resto vale igual ao cabo: o clique é mecânico e tem de estalar; a tabela vale só para o controle que navega o PC; a marca «não dispara» é o produto avisando, não defeito; e o desenho do Touchpad na fileira de botões do cartão não acende com o clique. Não aperte com a seta do mouse em cima de qualquer janela — é um clique de verdade. Onde a prova parou: a casa provou que o clique entra no pacote do controle virtual, e parou aí, nos dois transportes. E este teste é LONGO de propósito, com doze atos: a arrumação da tecla «Espaço» e a devolução dela no fim custam dois, a linha de base no P1 custa outro, e a volta de apertos tem de acontecer QUATRO vezes — P3 e P4, cada um com o microfone ativo e mudo — porque é justamente o cruzamento do som com o clique que ele existe para espremer.

---

## mapa-toque.touchpad.cursor-cabo — Touchpad — cursor do mouse (o dedo) · cabo

*Célula:* `toque.touchpad.cursor @ cabo`

**O que isto prova.** Prova que passar o dedo no touchpad de um controle do cabo move a seta do mouse na tela — e mostra de quem é essa seta hoje.

**Onde olhar.** O resultado é a SETA DO MOUSE na sua própria tela, e não um campo do Hefesto — feche ou minimize o que estiver aberto e deixe à mostra uma área vazia, para a seta ter para onde andar. No Hefesto, na aba Navegação, quadro «As opções de ativação»: a linha «Status do Modo», que diz Ligado ou Desligado, e a linha «Velocidade de cursor», um deslizante de 1 a 12 com o número ao lado. A ajuda da «Velocidade de cursor» diz que o mesmo número vale para o analógico esquerdo e para o dedo no touchpad. A ajuda da linha «Navegação Interna», ali do lado, diz a outra metade, e ela é o ponto deste teste: o cursor do PC é UM só e sai do controle do Player 1.

**Os passos.**

1. Abra a aba Navegação.
2. Confira que o «Status do Modo» está em Ligado.
3. Leia o número que está na linha «Velocidade de cursor» e anote-o.
4. Confira na fita do topo que o P1 e o P2 dizem cabo.
5. Largue os quatro controles na mesa e passe o dedo devagar no touchpad do P1, da esquerda para a direita e depois de cima para baixo.
6. Confira que a seta anda para a direita quando o dedo vai para a direita, e desce quando o dedo desce.
7. Levante o dedo, reapoie-o em outro canto do touchpad do P1 e ande de novo.
8. Confira que a seta NÃO pulou ao reapoiar — ela só anda quando o dedo anda.
9. Repita os atos 1 e 2 no P2, com os outros três largados na mesa.
10. Repita os atos 1 e 2 no P3 e depois no P4, um de cada vez.
11. Confira se a seta anda com eles também, e anote a resposta — aqui é anotação, e não reprovação.
12. Arraste a «Velocidade de cursor» de 6 para 12.
13. Passe o dedo no touchpad do P1 do mesmo jeito de antes.
14. Repare se a seta ficou mais rápida, e anote.
15. Empurre o analógico esquerdo do P1.
16. Repare se ELE ficou mais rápido, e anote.
17. Devolva a «Velocidade de cursor» ao número que você anotou no começo.

**Passa quando.** A seta do mouse anda com o dedo nos DOIS controles do cabo: para a direita quando o dedo vai para a direita, para baixo quando o dedo desce, e sem pular quando você levanta e reapoia o dedo. O que os dois do rádio fazem é anotação, e não reprovação: hoje o esperado é que eles também movam a seta, porque quem a move é o sistema e o sistema ouve os quatro touchpads.

**Por controle.**

* **P1** — Cabo, e é o primeiro que tem de mover a seta. Ele é também o único controle de quem o próprio Hefesto sabe mover o cursor: se um dia a seta andar SÓ com ele, o dono do cursor mudou, e isso é notícia.
* **P2** — Cabo, e tem de mover a seta igual ao P1. Se o P1 mover e o P2 não, o defeito é do segundo lugar da fila, não do cabo.
* **P3** — Rádio, testemunha — e esta testemunha responde uma pergunta em vez de ficar quieta. Passe o dedo nela e anote se a seta anda: andando, quem move a seta é o sistema, que ouve os quatro; não andando, quem move é o Hefesto, e aí só um controle move.
* **P4** — Rádio, segunda testemunha, mesma pergunta. Se o P3 mover e o P4 não, anote — são dois controles no mesmo tipo de conexão, e a diferença entre eles é o achado.

**A armadilha.** O dedo tem de andar APOIADO: a seta só junta movimento enquanto o dedo está na superfície, e levantar zera a referência de propósito — é isso que impede o salto ao reapoiar. Se a seta pular ao reapoiar, isso é o defeito. Quem move a seta com o touchpad físico hoje é o SISTEMA, e não o Hefesto: foi decisão dela em 09/08, o Hefesto devolveu o touchpad ao computador nos dois transportes, e em 03/09 os dois nós foram medidos assim. Daí saem duas coisas que enganam. A primeira: a seta andar não prova que o Hefesto está funcionando — prova que o touchpad e o nó dele estão de pé. A segunda: a «Velocidade de cursor» pode não mudar NADA no dedo e mudar tudo no analógico esquerdo, porque o número é do Hefesto e o dedo não passa por ele; se for isso que você vir, anote — é o estado medido, não um defeito novo. Rolar com dois dedos EXISTE, e quem faz é o SISTEMA, não o Hefesto: medido em 18/09/2026 com os dedos dela, o libinput emitiu 922 eventos de rolagem de dois dedos e 8 pinças no mesmo nó — o DualSense entrega dois pontos de toque. Não é o que este teste mede. E não confunda os dois gestos: apertar até estalar é o clique, e ele é outro teste. Onde a prova parou: a casa provou o caminho até o controle virtual, e parou aí.

---

## mapa-toque.touchpad.cursor-radio — Touchpad — cursor do mouse (o dedo) · rádio

*Célula:* `toque.touchpad.cursor @ rádio`

**O que isto prova.** Prova que passar o dedo no touchpad de um controle ligado por rádio move a seta do mouse na tela — o que nunca foi medido com um dedo até hoje.

**Onde olhar.** O resultado é a SETA DO MOUSE na sua própria tela, e não um campo do Hefesto — então deixe à mostra uma área vazia ao lado da janela do Hefesto, para a seta ter para onde andar. No Hefesto, na aba Navegação, quadro «As opções de ativação»: a linha «Status do Modo», que diz Ligado ou Desligado, e a linha «Velocidade de cursor», um deslizante de 1 a 12 com o número ao lado. A ajuda da «Navegação Interna», ao lado, diz que o cursor do PC é UM só e sai do controle do Player 1. Na ajuda do título da tabela de botões, do outro lado da mesma aba, o fim do texto diz qual controle navega o PC — é esse nome que decide se o ato do analógico pode ser feito hoje.

**Os passos.**

1. Abra o Hefesto e clique na aba Navegação.
2. Confira que o «Status do Modo» está em Ligado.
3. Confira na fita do topo que o P3 e o P4 dizem rádio.
4. Abra a ajuda do título da tabela de botões e anote qual controle navega o PC.
5. Com os quatro controles largados na mesa, passe o dedo no touchpad do P1, que está no cabo.
6. Veja a seta andar — é ele que prova que a tela e a sua mão estão medindo alguma coisa hoje. Depois disso não encoste mais nele.
7. Passe o dedo devagar no touchpad do P3, da esquerda para a direita e depois de cima para baixo.
8. Veja a seta ir para a direita e, na segunda passada, descer.
9. Levante o dedo do P3, reapoie-o em outro canto do touchpad e ande de novo.
10. Confira que a seta NÃO pulou ao reapoiar.
11. Passe o dedo no touchpad do P3 por uns dez segundos, indo e voltando.
12. Repare se a seta anda liso ou aos saltos, e anote.
13. Empurre o analógico esquerdo do P3 — mas só se o controle que navega o PC (ato 1) for um dos do rádio.
14. Veja se a seta anda, e anote. Se quem navega o PC for um do cabo, anote que este pedaço não deu para medir hoje.
15. Repita os atos 3 a 5 no P4, com os outros três largados na mesa.

**Passa quando.** A seta do mouse anda com o dedo nos DOIS controles do rádio: para a direita quando o dedo vai para a direita, para baixo quando o dedo desce, e sem pular quando você levanta e reapoia o dedo. Para o resultado valer, o P1, que está no cabo, tem de ter movido a seta antes. No fim, você tem anotado, para o P3 e para o P4: se a seta andou, se ela pulou ao reapoiar, e se ela andou lisa ou aos saltos.

**Por controle.**

* **P1** — Cabo, e é o controle de comparação. Passe o dedo nele PRIMEIRO: sem a seta andar aqui, o que acontecer no rádio não mede nada. Depois não encoste mais nele.
* **P2** — Cabo, testemunha. Não encoste nele. Ele existe neste teste para você ter certeza de que ninguém está movendo a seta pelo cabo enquanto você mexe no rádio.
* **P3** — Rádio, e é um dos dois que têm de mover a seta. Dedo apoiado, andando devagar nos dois sentidos, e depois dez segundos indo e voltando para ver se ela anda liso.
* **P4** — Rádio, e é o outro. Mesmos gestos. Se o P3 mover a seta e o P4 não, anote: são dois controles sem fio, e a diferença entre eles é o achado deste teste.

**A armadilha.** Este é o lado que nunca foi medido com um dedo. Em 03/09 mediu-se que o touchpad existe pelo rádio, com os mesmos eixos e a mesma geometria do cabo, mas ninguém encostou nele — a POSIÇÃO por rádio não tem medição de bancada nenhuma. O que sair daqui é o primeiro número. Existe uma observação dela, de 11/08, e ela também nunca foi medida: pelo rádio o touchpad move a seta, mas os gatilhos e o analógico não — o touchpad seria o único dos três que funciona sem fio. Por isso o ato do analógico, e por isso ele só vale no controle que navega o PC: em qualquer outro o analógico não move a seta de propósito, e cobrar isso dele seria reprovar um produto que está certo. O dedo tem de andar APOIADO: levantar zera a referência, e é isso que impede o salto ao reapoiar; se a seta pular, isso é o defeito. E quem move a seta com o touchpad físico hoje é o SISTEMA, não o Hefesto — decisão dela de 09/08, medida igual nos dois transportes em 03/09: a seta andar prova que o touchpad e o nó dele estão de pé, não que o Hefesto está movendo. Rolar com dois dedos EXISTE, e quem faz é o SISTEMA, não o Hefesto: medido em 18/09/2026 com os dedos dela, o libinput emitiu 922 eventos de rolagem de dois dedos e 8 pinças no mesmo nó — o DualSense entrega dois pontos de toque. Não é o que este teste mede. Apertar até estalar é o clique, e é outro teste. Onde a prova parou: a casa provou o caminho até o controle virtual, e parou aí.

## mapa-toque.touchpad.dedos-cabo — Touchpad — os dedos na TELA (leitura por slot) · cabo

*Célula:* `toque.touchpad.dedos @ cabo`

**O que isto prova.** Prova que a aba Controles mostra os DOIS dedos que você apoia no touchpad — uma bolinha por dedo, cada uma onde o dedo está — e que a palavra do canto conta certo: «Sem toque», «1 toque», «2 toques».

**Onde olhar.** No Hefesto, aba Controles, o card do controle que você está tocando: o quadro «Touchpad», no canto de cima à esquerda do card. O retângulo escuro é o touchpad; as bolinhas ciano são os dedos; a palavra no canto de cima à direita do quadro é a contagem.

**Os passos.**

1. Abra a aba Controles e escolha o P1 na fita do topo, para o card dele ficar aberto.
2. Confira que o quadro «Touchpad» diz «Sem toque» e não mostra bolinha nenhuma.
3. Apoie UM dedo no canto de cima à direita do touchpad do P1 e deixe-o parado.
4. Confira que aparece UMA bolinha no canto de cima à direita do quadro e que a palavra diz «1 toque».
5. Sem tirar o primeiro dedo, apoie um SEGUNDO dedo no canto de baixo à esquerda.
6. Confira que aparecem DUAS bolinhas, uma em cada canto, e que a palavra diz «2 toques».
7. Deixe os dois dedos parados por uns dez segundos.
8. Confira que as duas bolinhas continuam lá, paradas — dedo parado não some.
9. Levante SÓ o primeiro dedo (o de cima à direita).
10. Confira que a bolinha que sobrou é a do canto de baixo à esquerda, que ela NÃO pulou para o outro canto, e que a palavra voltou para «1 toque».
11. Levante o segundo dedo e confira «Sem toque».
12. Apoie TRÊS dedos juntos e anote quantas bolinhas aparecem.
13. Repita os passos 3 a 11 no P2, com os outros três largados na mesa.

**Por controle.**

* **P1** — Cabo, e é o primeiro que tem de mostrar os dois dedos.
* **P2** — Cabo, e tem de mostrar igual ao P1. Se o P1 mostrar e o P2 não, o defeito é do segundo lugar da fila, não do cabo.
* **P3** — Rádio, testemunha: largado na mesa. Se o card DELE mostrar bolinha enquanto você toca o P1, os dedos estão indo para o controle errado, e isso é o achado.
* **P4** — Rádio, segunda testemunha, mesma pergunta.


**Passa quando.** Dois dedos viram duas bolinhas, cada uma onde o seu dedo está, com a palavra «2 toques»; dedo parado continua na tela; e levantar um dedo não faz o outro trocar de lugar. No passo 12 o esperado são DUAS bolinhas, e isso não é defeito — veja a armadilha.

**A armadilha.** O touchpad do DualSense tem DOIS pontos de toque no aparelho, e não mais: o nó do kernel declara `ABS_MT_SLOT` de 0 a 1, e o terceiro dedo não chega nem ao sistema. O zoom de três dedos parece funcionar porque a pinça do sistema só precisa de dois — por isso três dedos viram duas bolinhas. A segunda armadilha é o sistema: rolar com dois dedos e dar zoom com a pinça são gestos do SISTEMA, que usa o mesmo touchpad ao mesmo tempo; eles podem mover a página que estiver sob a seta enquanto você testa, e isso não é o Hefesto. A terceira é o tempo da tela: ela lê o controle dez vezes por segundo, então um toque rápido demais pode não aparecer — os passos pedem dedo parado de propósito.

---

## mapa-toque.touchpad.dedos-radio — Touchpad — os dedos na TELA (leitura por slot) · rádio

*Célula:* `toque.touchpad.dedos @ rádio`

**O que isto prova.** Prova que a aba Controles mostra os DOIS dedos que você apoia no touchpad — uma bolinha por dedo, cada uma onde o dedo está — e que a palavra do canto conta certo: «Sem toque», «1 toque», «2 toques».

**Onde olhar.** No Hefesto, aba Controles, o card do controle que você está tocando: o quadro «Touchpad», no canto de cima à esquerda do card. O retângulo escuro é o touchpad; as bolinhas ciano são os dedos; a palavra no canto de cima à direita do quadro é a contagem.

**Os passos.**

1. Abra a aba Controles e escolha o P1 na fita do topo, para o card dele ficar aberto.
2. Confira que o quadro «Touchpad» diz «Sem toque» e não mostra bolinha nenhuma.
3. Apoie UM dedo no canto de cima à direita do touchpad do P1 e deixe-o parado.
4. Confira que aparece UMA bolinha no canto de cima à direita do quadro e que a palavra diz «1 toque».
5. Sem tirar o primeiro dedo, apoie um SEGUNDO dedo no canto de baixo à esquerda.
6. Confira que aparecem DUAS bolinhas, uma em cada canto, e que a palavra diz «2 toques».
7. Deixe os dois dedos parados por uns dez segundos.
8. Confira que as duas bolinhas continuam lá, paradas — dedo parado não some.
9. Levante SÓ o primeiro dedo (o de cima à direita).
10. Confira que a bolinha que sobrou é a do canto de baixo à esquerda, que ela NÃO pulou para o outro canto, e que a palavra voltou para «1 toque».
11. Levante o segundo dedo e confira «Sem toque».
12. Apoie TRÊS dedos juntos e anote quantas bolinhas aparecem.
13. Repita os passos 3 a 11 no P3 e depois no P4, um de cada vez, com os outros largados na mesa.

**Por controle.**

* **P3** — Rádio, e é o primeiro que tem de mostrar os dois dedos. O nó de touchpad é o mesmo nos dois transportes, então pelo rádio o esperado é igual ao cabo.
* **P4** — Rádio, e tem de mostrar igual ao P3.
* **P1** — Cabo, testemunha: largado na mesa. Se o card DELE mostrar bolinha enquanto você toca o P3, os dedos estão indo para o controle errado.
* **P2** — Cabo, segunda testemunha, mesma pergunta.


**Passa quando.** Dois dedos viram duas bolinhas, cada uma onde o seu dedo está, com a palavra «2 toques»; dedo parado continua na tela; e levantar um dedo não faz o outro trocar de lugar. No passo 12 o esperado são DUAS bolinhas, e isso não é defeito — veja a armadilha.

**A armadilha.** O touchpad do DualSense tem DOIS pontos de toque no aparelho, e não mais: o nó do kernel declara `ABS_MT_SLOT` de 0 a 1, e o terceiro dedo não chega nem ao sistema. O zoom de três dedos parece funcionar porque a pinça do sistema só precisa de dois — por isso três dedos viram duas bolinhas. A segunda armadilha é o sistema: rolar com dois dedos e dar zoom com a pinça são gestos do SISTEMA, que usa o mesmo touchpad ao mesmo tempo; eles podem mover a página que estiver sob a seta enquanto você testa, e isso não é o Hefesto. A terceira é o tempo da tela: ela lê o controle dez vezes por segundo, então um toque rápido demais pode não aparecer — os passos pedem dedo parado de propósito.

---

## mapa-vibracao.rumble.direito-cabo — Rumble — motor DIREITO (weak) · cabo

*Célula:* `vibracao.rumble.direito @ cabo`

**O que isto prova.** Prova que, nos dois controles do cabo, o motor que o Hefesto chama de direito é o punho direito — e que a barra dele cala aquele punho e mais nenhum.

**Onde olhar.** Na aba Vibração, que tem uma coluna por controle. O cabeçalho da coluna diz o número do jogador, a cor do plástico e por onde ele fala (a palavra cabo ou a palavra rádio). Logo abaixo vem o desenho do controle, e nele o lado que está tremendo acende em laranja. Mais abaixo há duas linhas de motor, cada uma com um ícone, uma barra para arrastar e um número seguido de %: a de cima é Motor de vibração esquerdo, a de baixo é Motor de vibração direito. No pé da coluna ficam os botões Testar e Parar. Embaixo das quatro colunas há uma linha que começa com um pontinho — é ela que conta os pedidos de vibração do jogo, jogador por jogador. O juiz final, porém, são as suas mãos.

**Os passos.**

1. Abra a aba Jogar.
2. Confira que o Status está em Ligado.
3. Confira que o Modo escolhido não é o Modo Nativo.
4. Clique na aba Vibração.
5. Leia os dois números de motor de cada uma das quatro colunas e escreva os oito, antes de arrastar qualquer barra.
6. Clique em Parar em cada uma das quatro colunas, para limpar qualquer vibração fixada de um teste anterior.
7. Ponha, na coluna do P1 e na do P2, a barra do Motor de vibração esquerdo em 0 e a do Motor de vibração direito em 100.
8. Confira que as quatro barras do P3 e do P4 continuam em 100.
9. Abra o jogo com os quatro jogadores dentro da partida.
10. Segure o P1 com uma mão em cada punho, sem apertar, e provoque no jogo a vibração do jogador dele — o dano, o tiro ou a batida que você sabe provocar.
11. Diga em voz alta qual punho tremeu, antes de olhar a tela.
12. Veja, no desenho da coluna do P1 durante a vibração, qual lado acendeu em laranja.
13. Repita a volta inteira com o P2: segure com uma mão em cada punho, provoque a vibração dele, diga o punho em voz alta e só então olhe o desenho.
14. Segure o P3 e provoque uma vibração para o jogador dele.
15. Confira que no P3 os DOIS punhos tremem.
16. Pare o mouse na linha Motor de vibração esquerdo da coluna daquele jogador e leia a dica com o número que o jogo pediu.
17. Devolva as oito barras aos números que você escreveu no começo.

**Passa quando.** No P1 e no P2 — os dois do cabo —, com a barra esquerda em 0, só o punho DIREITO tremeu com a vibração do jogo, e no desenho só o lado direito acendeu em laranja; o punho esquerdo desses dois ficou parado. No P3 e no P4, com as duas barras em 100, os dois punhos tremeram: é isso que prova que o motor esquerdo está vivo e que quem o calou foi a barra, não um defeito. E nenhum controle tremeu quando a vibração era de outro jogador.

**Por controle.**

* **P1** — Está no CABO e é um dos dois que têm de reagir. Barra esquerda em 0, direita em 100: só o punho direito pode tremer, e só o lado direito acende no desenho.
* **P2** — Também no cabo, mesma configuração e mesma resposta esperada. Se os dois do cabo se comportarem diferente um do outro, o defeito é daquele controle e não do transporte — anote qual dos dois.
* **P3** — Está no RÁDIO e é testemunha: não mexa nas barras dele. Duas conferências nele — não pode tremer quando a vibração é do jogador do P1, e quando é a dele os dois punhos têm de tremer.
* **P4** — Também no rádio e também testemunha, com a mesma dupla conferência. Se o P3 e o P4 tremerem junto com o P1, a vibração perdeu o endereço e foi para os quatro em vez de ir para o escolhido.

**A espera.** O jogo pode levar minutos para chegar ao menu, e nenhum desses minutos é para ficar olhando a tela. Deixe-o carregando e vá fazer outra coisa; volte quando ouvir o som do menu. Nada se desfaz por você ter saído da frente: as oito barras continuam onde você as pôs, e o Parar que você clicou continua valendo. Ao voltar, comece pelo P1 na mão.

**A armadilha.** A barra NÃO muda o botão Testar, e é aqui que este teste dá falso vermelho. O Testar manda um par fixo para os DOIS motores e ignora as duas barras da coluna: quem puser a barra esquerda em 0, clicar em Testar, sentir os dois punhos tremerem e concluir que a barra não funciona reprovou um produto certo. A barra só morde a vibração que vem DO JOGO. Segunda: a barra grava no perfil ativo no instante em que você solta o dedo, e fica gravada — por isso os números se escrevem antes e se devolvem no fim. Terceira: o laranja do desenho vem da vibração do jogo e apaga sozinho cerca de três segundos depois da última — desenho apagado com a vibração já terminada não é defeito. Quarta: o tremor viaja pelo casco; com o controle apoiado na mesa, ou apertado com força, o punho mudo parece tremer também. Segure leve. No mapa esta célula chegou até o aparelho obedeceu, e a prova foi um teste às cegas: ela disse o lado sem saber o que tinha sido enviado. E a razão de este teste ter NOVE atos, um a mais que o alvo de oito: o dizer às cegas é passo próprio e numerado de propósito. Ele é a defesa contra o próprio viés — falar o punho ANTES de olhar o desenho —, e dobrado dentro do passo que provoca a vibração ele vira recomendação, que é justamente o que faz alguém olhar a tela primeiro e depois "sentir" o lado que a tela mostrou.

---

## mapa-vibracao.rumble.direito-radio — Rumble — motor DIREITO (weak) · rádio

*Célula:* `vibracao.rumble.direito @ rádio`

**O que isto prova.** Prova que, nos dois controles do rádio, o motor direito é o punho direito — e que a barra dele cala aquele punho sem tocar nos controles do cabo.

**Onde olhar.** Na aba Vibração, nas colunas do P3 e do P4 — o cabeçalho de cada uma tem de dizer a palavra rádio. Dentro da coluna: o desenho do controle, onde o lado que treme acende em laranja; a linha Motor de vibração esquerdo e a linha Motor de vibração direito, cada uma com uma barra e um número seguido de %; e os botões Testar e Parar no pé. Embaixo das quatro colunas, a linha que começa com um pontinho conta os pedidos do jogo por jogador. Quem decide o resultado são as suas mãos.

**Os passos.**

1. Abra a aba Jogar.
2. Confira que o Status está em Ligado.
3. Confira que o Modo escolhido não é o Modo Nativo.
4. Clique na aba Vibração.
5. Confira que o cabeçalho das colunas do P3 e do P4 diz rádio.
6. Leia os dois números de motor de cada uma das quatro colunas e escreva os oito, antes de arrastar qualquer barra.
7. Clique em Parar em cada uma das quatro colunas.
8. Ponha, na coluna do P3 e na do P4, a barra do Motor de vibração esquerdo em 0 e a do Motor de vibração direito em 100.
9. Confira que as quatro barras do P1 e do P2 continuam em 100.
10. Abra o jogo com os quatro jogadores dentro da partida.
11. Segure o P3 com uma mão em cada punho, sem apertar, e provoque no jogo a vibração do jogador dele.
12. Diga em voz alta qual punho tremeu, antes de olhar a tela.
13. Veja, no desenho da coluna do P3 durante a vibração, qual lado acendeu em laranja.
14. Repita a volta inteira com o P4: segure com uma mão em cada punho, provoque a vibração dele, diga o punho em voz alta e só então olhe o desenho.
15. Segure o P1 e provoque uma vibração para o jogador dele.
16. Confira que no P1 os DOIS punhos tremem.
17. Pare o mouse na linha Motor de vibração esquerdo da coluna daquele jogador e leia a dica com o número que o jogo pediu.
18. Devolva as oito barras aos números que você escreveu no começo.

**Passa quando.** No P3 e no P4 — os dois do rádio —, com a barra esquerda em 0, só o punho DIREITO tremeu, e no desenho só o lado direito acendeu em laranja. O P1 e o P2, que ficaram com as duas barras em 100, tremeram dos dois lados quando a vibração era deles: é a prova de que o motor esquerdo está vivo e de que quem o calou no rádio foi a barra. E nenhum dos quatro tremeu quando a vibração era de outro jogador.

**Por controle.**

* **P1** — Está no CABO e é testemunha. Não mexa nas barras dele. Ele não pode tremer quando a vibração é do jogador do P3 — se tremer, o comando pegou a mesa inteira em vez do controle escolhido.
* **P2** — Também no cabo e também testemunha, com a mesma conferência. Ele é ainda o controle de comparação: com as duas barras em 100, os dois punhos dele têm de tremer quando a vibração é dele.
* **P3** — Está no RÁDIO e é um dos dois que têm de reagir. Barra esquerda em 0, direita em 100: só o punho direito treme, e só o lado direito acende no desenho.
* **P4** — Também no rádio, mesma configuração. Se ele responder diferente do P3, anote qual dos dois — dois controles no mesmo transporte discordando aponta para o aparelho, não para o caminho.

**A espera.** O jogo pode levar minutos para chegar ao menu, e nenhum desses minutos é para ficar olhando a tela. Deixe-o carregando e vá fazer outra coisa; volte quando ouvir o som do menu. Nada se desfaz por você ter saído da frente: as oito barras continuam onde você as pôs. Ao voltar, comece pelo P3 na mão — e, se ele tiver caído do rádio enquanto você estava fora, isso é achado e vale anotar a hora.

**A armadilha.** A barra NÃO muda o botão Testar: o Testar manda um par fixo aos dois motores e ignora as barras da coluna. Quem testar a barra pelo Testar sente os dois punhos tremerem e reprova um produto certo — a barra só morde a vibração do JOGO. Segunda, e é do rádio: o comando vai numerado e conferido, e um comando que chegue fora de ordem o próprio controle joga fora, sem avisar ninguém. O sintoma é uma vibração que falha de vez em quando, e ele não aparece em campo nenhum da tela — se acontecer, refaça a rodada antes de concluir qualquer coisa. Terceira: a medição de quatro controles na mesa não achou diferença nenhuma entre cabo e rádio nesta família; o que fazia diferença era o Hefesto estar de pé ou parado. Então, se aqui os dois do rádio se comportarem diferente dos dois do cabo, isso é informação nova e vale anotar com todas as letras. Quarta: a barra grava no perfil ativo assim que você solta o dedo — escreva os oito números antes, devolva depois. E a razão de este teste ter NOVE atos, um a mais que o alvo de oito: o dizer às cegas é passo próprio e numerado de propósito. Ele é a defesa contra o próprio viés — falar o punho ANTES de olhar o desenho —, e dobrado dentro do passo que provoca a vibração ele vira recomendação, que é justamente o que faz alguém olhar a tela primeiro e depois "sentir" o lado que a tela mostrou.

---

## mapa-vibracao.rumble.esquerdo-cabo — Rumble — motor ESQUERDO (strong) · cabo

*Célula:* `vibracao.rumble.esquerdo @ cabo`

**O que isto prova.** Prova que, nos dois controles do cabo, o motor que o Hefesto chama de esquerdo é o punho esquerdo — o pesado, o que soa grosso — e que a barra dele cala só aquele punho.

**Onde olhar.** Na aba Vibração, nas colunas do P1 e do P2 — o cabeçalho de cada uma tem de dizer a palavra cabo. Dentro da coluna: o desenho do controle, onde o lado que treme acende em laranja; a linha Motor de vibração esquerdo e a linha Motor de vibração direito, cada uma com uma barra e um número seguido de %; e os botões Testar e Parar no pé. Parando o mouse em cima do ícone de cada linha aparece a dica que diz qual motor é aquele e como ele soa. Embaixo das quatro colunas, a linha que começa com um pontinho conta os pedidos do jogo. As mãos decidem. Antes de tudo isso, a aba Jogar: é lá que se confere o Status e o Modo escolhido, e é de lá que este teste parte.

**Os passos.**

1. Abra a aba Jogar.
2. Confira que o Status está em Ligado.
3. Confira que o Modo escolhido não é o Modo Nativo.
4. Clique na aba Vibração.
5. Anote os dois números de motor das quatro colunas, antes de arrastar qualquer barra.
6. Clique em Parar em cada uma das quatro colunas.
7. Ponha as barras assim: nas colunas do P1 e do P2, o Motor de vibração direito em 0 e o Motor de vibração esquerdo em 100; nas colunas do P3 e do P4, as quatro em 100.
8. Abra o jogo com os quatro jogadores dentro da partida.
9. Segure o P1 com uma mão em cada punho, sem apertar, e provoque no jogo uma vibração para o jogador dele.
10. Diga em voz alta qual punho tem o PESO do tremor, antes de olhar a tela.
11. Segure o P1 só pelo punho esquerdo e provoque a vibração de novo.
12. Segure o P1 só pelo punho direito e provoque a vibração mais uma vez.
13. Veja o desenho da coluna do P1 durante a vibração e repare qual lado acendeu em laranja.
14. Refaça no P2 os quatro gestos de mão que você fez no P1.
15. Segure o P3 e provoque uma vibração para o jogador dele.
16. Confira que ali os DOIS punhos tremem.
17. Pare o mouse na linha Motor de vibração esquerdo da coluna daquele jogador e leia a dica com o número que o jogo pediu.
18. Devolva as oito barras aos números que você anotou.

**Passa quando.** No P1 e no P2, com a barra direita em 0, o peso do tremor ficou no punho ESQUERDO — e segurando só pelo punho direito não há tremor próprio, só o eco que atravessa o plástico. No desenho, só o lado esquerdo acendeu em laranja. No P3 e no P4, com as duas barras em 100, os dois punhos tremeram, provando que o motor direito está vivo e que quem o calou foi a barra. E nenhum controle tremeu quando a vibração era de outro jogador.

**Por controle.**

* **P1** — Está no CABO e é um dos dois que têm de reagir. Barra direita em 0, esquerda em 100: o peso do tremor fica no punho esquerdo e só o lado esquerdo acende no desenho.
* **P2** — Também no cabo, mesma configuração. Se os dois do cabo discordarem entre si, o defeito é do aparelho e não do caminho — anote qual dos dois.
* **P3** — Está no RÁDIO e é testemunha: não mexa nas barras dele. Não pode tremer quando a vibração é do jogador do P1, e quando é a dele os dois punhos têm de tremer.
* **P4** — Também no rádio e também testemunha, com a mesma dupla conferência. Os dois tremendo junto com o P1 quer dizer que a vibração foi para a mesa inteira.

**A armadilha.** O motor esquerdo é o PESADO, e é ele que faz este teste dar falso vermelho. Quando só o esquerdo treme, o casco inteiro balança e a mão direita sente alguma coisa — quem julgar por senti alguma coisa conclui que os dois lados tremeram e reprova um produto certo. O que se julga é onde está o PESO, não onde há sensação; e a conferência de verdade é a dos passos que mandam segurar um punho de cada vez. Segunda: a barra não muda o botão Testar — o Testar manda um par fixo aos dois motores e ignora as barras, e nesse par o esquerdo já sai mais forte que o direito de propósito. Quem testar a barra pelo Testar sente os dois tremerem e reprova o certo. Terceira: a barra grava no perfil ativo assim que você solta o dedo, e fica — anote antes, devolva depois. Quarta: o laranja apaga sozinho cerca de três segundos depois da última vibração; desenho apagado com a vibração já acabada não é defeito. E este teste é LONGO de propósito, com doze atos: ele nasce na aba Jogar, porque conferir o Status e o Modo com a barra já arrastada seria medir o produto errado, e só depois passa para a aba Vibração; arruma oito barras antes de medir e as devolve no fim; e a prova é a mão trocando de punho três vezes no mesmo controle. Cortar qualquer dessas trocas devolve exatamente o falso vermelho da primeira armadilha.

---

## mapa-vibracao.rumble.esquerdo-radio — Rumble — motor ESQUERDO (strong) · rádio

*Célula:* `vibracao.rumble.esquerdo @ rádio`

**O que isto prova.** Prova que, nos dois controles do rádio, o motor esquerdo é o punho esquerdo — o pesado — e que a barra dele cala aquele punho sem tocar nos controles do cabo.

**Onde olhar.** Na aba Vibração, nas colunas do P3 e do P4 — o cabeçalho de cada uma tem de dizer a palavra rádio. Dentro da coluna: o desenho, onde o lado que treme acende em laranja; a linha Motor de vibração esquerdo e a linha Motor de vibração direito, cada uma com barra e número seguido de %; e os botões Testar e Parar no pé. Embaixo das quatro colunas, a linha que começa com um pontinho conta os pedidos do jogo por jogador. Antes de tudo isso há uma condição, e ela mora na aba Jogar: o Status tem de estar em Ligado e o Modo escolhido não pode ser o Modo Nativo — no Modo Nativo o jogo fala direto com o controle e a barra desta aba não tem o que fazer. As mãos decidem.

**Os passos.**

1. Abra a aba Jogar.
2. Confira que o Status está em Ligado.
3. Confira que o Modo escolhido não é o Modo Nativo.
4. Clique na aba Vibração.
5. Confira que o cabeçalho das colunas do P3 e do P4 diz rádio.
6. Leia os dois números de motor das quatro colunas e copie-os num papel, antes de arrastar qualquer barra.
7. Clique em Parar em cada uma das quatro colunas, para soltar qualquer vibração presa de um teste anterior.
8. Arraste, na coluna do P3 e na do P4, a barra do Motor de vibração direito até 0 e a do Motor de vibração esquerdo até 100 — e deixe em 100 as quatro barras do P1 e do P2.
9. Abra o jogo com os quatro jogadores dentro da partida.
10. Segure o P3 com uma mão em cada punho, sem apertar, e provoque no jogo uma vibração para o jogador dele.
11. Diga em voz alta em qual punho está o PESO do tremor, antes de olhar a tela.
12. Veja qual lado do desenho da coluna do P3 acendeu em laranja.
13. Segure o P3 só pelo punho direito e provoque a vibração de novo.
14. Confira que não vem tremor próprio naquele punho.
15. Repita os atos 5 a 7 com o P4.
16. Segure o P1 e provoque uma vibração para o jogador dele.
17. Confira que ali os DOIS punhos tremem, e que nenhum dos quatro treme quando a vibração é de outro jogador.
18. Pare o mouse na linha Motor de vibração esquerdo da coluna daquele jogador e leia a dica com o número que o jogo pediu.
19. Devolva as oito barras aos números que você anotou no papel.

**Passa quando.** No P3 e no P4, com a barra direita em 0, o peso do tremor ficou no punho ESQUERDO, e segurando só pelo punho direito não há tremor próprio. No desenho, só o lado esquerdo acendeu em laranja. O P1 e o P2, com as duas barras em 100, tremeram dos dois lados quando a vibração era deles. E nenhum dos quatro tremeu quando a vibração era de outro jogador.

**Por controle.**

* **P1** — Está no CABO e é testemunha. Não mexa nas barras dele. Não pode tremer quando a vibração é do jogador do P3, e serve de comparação: com as duas barras em 100, os dois punhos dele tremem quando a vibração é dele.
* **P2** — Também no cabo e também testemunha, com a mesma conferência. Os dois do cabo tremendo junto com o P3 quer dizer que a vibração foi para a mesa inteira.
* **P3** — Está no RÁDIO e é um dos dois que têm de reagir. Barra direita em 0, esquerda em 100: o peso fica no punho esquerdo e só o lado esquerdo acende no desenho.
* **P4** — Também no rádio, mesma configuração e mesma resposta esperada. Se ele discordar do P3, o defeito é do aparelho — anote qual dos dois.

**A armadilha.** Este teste tem DEZ atos, acima dos oito do alvo, e o motivo é a forma da prova: o punho certo só se separa do errado segurando um punho de cada vez, o que dá dois atos por controle, vezes os dois do rádio, mais a comparação no P1 e a devolução das barras ao perfil. Cortar um dos dois modos de segurar apaga a prova. O motor esquerdo é o PESADO: quando só ele treme, o casco inteiro balança e a mão direita sente o eco. Julgue pelo PESO do tremor, não por sentir alguma coisa. Segunda, e é do rádio: o comando vai numerado e conferido, e o controle descarta sozinho o que chegar fora de ordem, calado; o sintoma é uma vibração que some de vez em quando e não aparece em campo nenhum da tela. Terceira: a barra não vale para o botão Testar, que manda um par fixo aos dois motores e ignora as barras. Quarta: houve um tempo em que a vibração pelo rádio era gasto de energia e nada mais, porque o comando saía malformado e o controle o descartava inteiro; hoje ele sai certo, mas se os dois do rádio ficarem MUDOS enquanto os dois do cabo tremem no mesmo teste, é exatamente isso que você está vendo voltar — anote antes de mexer em qualquer outra coisa. Quinta: a barra grava no perfil ativo assim que você solta o dedo, e é por isso que os números vão para o papel no começo e voltam para as barras no fim.

---

## mapa-vibracao.rumble.ff-cabo — Rumble por amplitude (FF_RUMBLE — motor esquerdo = strong, direito = weak) · cabo

*Célula:* `vibracao.rumble.ff @ cabo`

**O que isto prova.** Prova que, nos dois controles do cabo, a vibração que o jogo pede chega com a força pedida e DURA o tempo que o jogo segurou — sem ser cortada num piscar.

**Onde olhar.** Na aba Vibração, na COLUNA de cada jogador — a testemunha aqui é por controle, e não mais uma linha só embaixo de todas. No alto da coluna, o desenho acende em laranja o punho que está tremendo: é ele que responde *chegou força agora, neste controle?*. Parando o mouse em cima da linha Motor de vibração esquerdo ou direito daquela coluna, com o jogo vibrando, aparece a dica dizendo quanto o jogo pediu naquele motor agora, de 0 a 255 — e quando o jogo não está pedindo nada ali, **não aparece dica nenhuma**, porque o Hefesto apaga o aviso em vez de deixar um número velho. É esse par (punho aceso + dica com número) que diz quem recebeu. E a duração quem mede são as suas mãos e a sua contagem em voz alta.

> **A contagem do pé da grade saiu da tela em 07/09/2026**, por ordem dela (*"Vibração remove essa última frase também"*). Ela era cumulativa — dizia quantas vezes o jogo já pediu — e o que a substitui é mais forte para este teste: o punho e a dica são AO VIVO e são por jogador, então dizem quem está recebendo AGORA, que é o que estas células perguntam.

**Os passos.**

1. Abra o Hefesto e clique na aba Jogar.
2. Confira que o Status está em Ligado.
3. Clique na aba Vibração.
4. Vá à aba Controles, pare o mouse no NOME de cada controle e confira que a dica diz que ele alimenta o gamepad virtual de um jogador — e não que ainda não alimenta nenhum. Volte à aba Vibração.
5. Clique em Parar em cada uma das quatro colunas, para soltar qualquer vibração fixada de um teste anterior.
6. Escolha Balanceado nas quatro colunas.
7. Confira que as oito barras de motor estão em 100.
8. Abra o jogo com os quatro jogadores dentro da partida.
9. Segure o P1 nas duas mãos.
10. Provoque uma vibração LONGA no jogo — daquelas que ele segura por vários segundos, como um motor acelerando ou uma arma automática segurada.
11. Conte os segundos em voz alta enquanto ela dura, e segure o gatilho o tempo todo.
12. Solte o gatilho e confira que a vibração parou junto.
13. Provoque agora uma vibração CURTA e forte, de um tiro ou de uma batida, e confira que ela chega com força.
14. Confira que o punho do desenho na coluna do P1 acendeu em laranja enquanto a vibração chegava.
15. Pare o mouse em cima da linha Motor de vibração esquerdo da coluna do P1 enquanto o jogo vibra, e leia a dica.
16. Repita os sete passos acima com o P2.
17. Provoque uma vibração longa no P1 e, sem soltar, provoque outra no P3 — e confira que a do P1 não encolhe.

**Passa quando.** Nos dois do cabo, a vibração que o jogo segurou por vários segundos durou esses segundos inteiros na mão, e parou quando o jogo parou de pedir — não virou um estalo de meio segundo. A vibração curta e forte chegou forte. O punho do desenho acendeu em laranja na coluna daquele controle, e a dica da linha do motor daquela coluna trouxe o número que o jogo pediu. E a vibração de um não encurtou a do outro.

**Por controle.**

* **P1** — Está no CABO e é um dos dois que têm de reagir. É nele que a contagem de segundos importa: a vibração longa tem de durar o que o jogo segurou.
* **P2** — Também no cabo, mesma medição. Dois controles no mesmo transporte com durações diferentes é achado — anote os dois números de segundos.
* **P3** — Está no RÁDIO e é testemunha. Ele entra no último passo: uma vibração provocada nele não pode encurtar a que já está correndo no P1. Se encurtar, um está cortando a vibração do outro.
* **P4** — Também no rádio e também testemunha, com a mesma conferência — e é o último da fila, o primeiro a perder a vez quando alguma coisa disputa a saída. Repita nele o último passo se o P3 não mostrar nada.

**A armadilha.** O corte em meio segundo é um defeito CONHECIDO desta casa e já foi medido por dose: o Hefesto re-afirma o estado dos motores de meio em meio segundo, e essa re-afirmação já zerava a vibração de quem não fosse ele — esticando esse meio segundo para oito, a vibração passou a durar oito segundos exatos, nos dois transportes. O conserto está escrito e ligado; este teste existe para dizer se ele continua de pé. Por isso a contagem em voz alta é o instrumento, e não um detalhe. Segunda: se você clicou em Testar pouco antes, aquele controle pode ficar com a vibração FIXADA, e nesse estado a vibração do jogo é ignorada — é a queixa testei os motores e o jogo não vibra mais. O Parar em cada coluna, no começo, é o que evita isso. Terceira: um jogo pode simplesmente não pedir vibração, e quem separa os dois casos é a dica da linha do motor daquela coluna — se ela traz um número e a mão não sente nada, a perda é dentro do Hefesto; se não há dica nenhuma, o jogo não pediu. Quarta: se a aba Controles disser que aquele controle não alimenta gamepad virtual nenhum, o Hefesto saiu do meio e este teste não está medindo o caminho dele.

---

## mapa-vibracao.rumble.ff-radio — Rumble por amplitude (FF_RUMBLE — motor esquerdo = strong, direito = weak) · rádio

*Célula:* `vibracao.rumble.ff @ rádio`

**O que isto prova.** Prova que, nos dois controles do rádio, a vibração que o jogo pede chega com a força pedida e dura o tempo que o jogo segurou — igual à dos dois do cabo.

**Onde olhar.** Na aba Vibração, nas colunas do P3 e do P4 — cabeçalho com a palavra rádio. O desenho acende em laranja o punho que treme, e parando o mouse na linha de um motor, com o jogo vibrando, a dica diz quanto o jogo pediu naquele motor agora, de 0 a 255; onde o jogo não está pedindo, não há dica. A duração quem mede são as suas mãos e a contagem em voz alta.

> **A contagem do pé da grade saiu da tela em 07/09/2026**, por ordem dela. O que responde *chegou a este controle?* passa a ser a própria coluna dele — punho aceso e dica com número —, que é por jogador e ao vivo.

**Os passos.**

1. Abra o Hefesto e clique na aba Jogar.
2. Confira que o Status está em Ligado.
3. Clique na aba Vibração.
4. Confira que o cabeçalho das colunas do P3 e do P4 diz rádio.
5. Vá à aba Controles, pare o mouse no NOME de cada controle e confira que a dica diz que ele alimenta o gamepad virtual de um jogador — e não que ainda não alimenta nenhum. Volte à aba Vibração.
6. Clique em Parar em cada uma das quatro colunas.
7. Escolha Balanceado nas quatro colunas.
8. Confira que as oito barras de motor estão em 100.
9. Abra o jogo com os quatro jogadores dentro da partida.
10. Segure o P3 nas duas mãos.
11. Provoque uma vibração LONGA no jogo para o jogador dele e segure o gatilho.
12. Conte os segundos em voz alta enquanto ela dura.
13. Solte o gatilho e confira que a vibração parou junto.
14. Provoque uma vibração CURTA e forte e confira que ela chega forte.
15. Confira que o punho do desenho na coluna do P3 acendeu em laranja enquanto a vibração chegava.
16. Repita os cinco passos acima com o P4.
17. Faça a mesma vibração longa no P1 e conte os segundos dela.
18. Compare os segundos do rádio com os segundos do cabo.

**Passa quando.** Nos dois do rádio, a vibração longa durou o tempo em que o jogo a segurou e parou quando ele parou de pedir; a curta chegou forte; e o punho do desenho acendeu em laranja na coluna daquele controle, com a dica da linha do motor trazendo o número pedido. Comparados com o P1, os segundos batem: se o rádio durar menos que o cabo na mesma vibração, isso é o achado do teste.

**Por controle.**

* **P1** — Está no CABO e é testemunha — e aqui ele é a RÉGUA: a mesma vibração longa provocada nele dá o número de segundos com que os do rádio são comparados.
* **P2** — Também no cabo e também testemunha. Use-o para repetir a régua se o número do P1 sair estranho — dois cabos discordando entre si invalidam a comparação antes de acusar o rádio.
* **P3** — Está no RÁDIO e é um dos dois que têm de reagir. Conte os segundos da vibração longa dele e escreva o número.
* **P4** — Também no rádio, mesma medição. Ele é o último a entrar e o primeiro a perder a vez: se só ele encurtar, anote isso separado — é diferente de o rádio inteiro encurtar.

**A armadilha.** O corte em meio segundo já foi medido nesta casa nos DOIS transportes, e a prova foi por dose: esticando o meio segundo da re-afirmação dos motores para oito, a vibração passou a durar oito segundos exatos. O conserto está escrito e ligado; a contagem em voz alta é o que diz se ele continua de pé. Segunda, e é do rádio: o comando vai numerado e conferido, e o controle descarta sozinho o que chegar fora de ordem — uma vibração que falha de vez em quando pelo rádio pode ser isso, e não aparece em campo nenhum da tela. Terceira: a medição com quatro controles na mesa não achou diferença entre cabo e rádio nesta família; quem fazia diferença era o Hefesto estar de pé ou parado. Uma diferença aqui é notícia nova. Quarta: se você clicou em Testar pouco antes, aquele controle pode ter ficado com a vibração fixada, e nesse estado a do jogo é ignorada — o Parar no começo é o que evita. Quinta: bateria baixa no rádio muda a força com que o motor responde; se um dos dois estiver quase descarregado, carregue antes de acusar o transporte.

---

## mapa-vibracao.rumble.habilitar-cabo — Habilitar o motor no firmware (enable vibration) · cabo

*Célula:* `vibracao.rumble.habilitar @ cabo`

**O que isto prova.** Prova que, nos dois controles do cabo, o Hefesto liga a autorização de vibração no controle — sem ela nenhum motor obedeceria a coisa nenhuma.

**Onde olhar.** Não há campo na tela que mostre essa autorização: a fonte não diz onde se lê esse valor. O que se lê é a CONSEQUÜÊNCIA dela — o punho tremendo depois de um clique em Testar. Então olhe a aba Vibração, coluna por coluna: os três botões Economia, Balanceado e Máximo; as duas linhas de motor com suas barras e seus números seguidos de %; e os botões Testar e Parar no pé da coluna. Quando o produto recusa um clique, aparece uma tarja de recado dentro da própria coluna daquele controle, e ela fica cerca de meio minuto na tela. As mãos dizem o resto.

**Os passos.**

1. Feche o jogo, se houver algum aberto.
2. Abra o Hefesto e clique na aba Jogar.
3. Confira que o Status está em Ligado.
4. Confira que o Modo escolhido não é o Modo Nativo.
5. Clique na aba Vibração.
6. Confira que nenhum punho do desenho está aceso em coluna nenhuma, e que parar o mouse nas linhas de motor não abre dica de pedido em nenhuma delas.
7. Escolha Balanceado nas quatro colunas.
8. Ponha as oito barras de motor em 100.
9. Segure o P1 nas duas mãos.
10. Clique em Testar na coluna do P1.
11. Confira que ele treme por cerca de meio segundo e para sozinho.
12. Olhe os outros três em cima da mesa nesse instante e confira que nenhum deles se mexeu.
13. Clique em Testar de novo na coluna do P1 e, antes de o tremor acabar, clique em Parar na mesma coluna.
14. Confira que ele parou na hora.
15. Repita os cinco passos acima com o P2.
16. Confira se apareceu alguma tarja de recado dentro de alguma coluna e leia o que ela diz.

**Passa quando.** Nos dois do cabo, um clique em Testar fez aquele controle — e só ele — tremer por cerca de meio segundo e parar sozinho; os outros três ficaram parados na mesa; e o Parar cortou o tremor na hora. Nenhuma tarja de recado apareceu. Um controle que não treme nem no cabo nem no rádio, com Balanceado escolhido e as barras em 100, é a autorização faltando.

**Por controle.**

* **P1** — Está no CABO e é um dos dois que têm de reagir. Ele treme quando o Testar da coluna dele é clicado, e só então.
* **P2** — Também no cabo, mesma resposta esperada. Um dos dois tremendo e o outro não, com a mesma configuração, aponta para aquele aparelho — anote qual.
* **P3** — Está no RÁDIO e é testemunha: não toque nele. Ele não pode tremer quando o Testar clicado é o da coluna do P1 ou do P2. Se tremer, o comando foi para a mesa inteira em vez de ir para o controle escolhido.
* **P4** — Também no rádio e também testemunha, com a mesma conferência — e é o mais propenso a receber comando de outro, por ser o último da fila.

**A armadilha.** Esta célula NÃO TEM MEDIÇÃO NENHUMA no mapa: a coluna que diz até onde a prova chegou está vazia, no cabo e no rádio. Ninguém mediu este aspecto até hoje, então o que você está fazendo aqui é o primeiro degrau — e um verde aqui não quer dizer mais do que os motores obedecem. Segunda, e ela é do produto: das quatro chavinhas de autorização que o Hefesto deveria ligar, ele liga TRÊS. A quarta, a da vibração nova dos firmwares mais recentes, nunca sobe, e não aparece em campo nenhum da tela. Se um controle ficar completamente mudo nos dois transportes com tudo em 100, esse é o primeiro suspeito, e ele não é o seu gesto. Terceira: se a aba Jogar estiver em Modo Nativo, o Testar é RECUSADO de propósito, com a frase Vibração não aplicada: em Modo Nativo quem manda nos motores é o jogo, numa tarja dentro da coluna. Isso é o produto recusando direito, e não defeito — mas o teste não corre nesse modo. Quarta: se o controle da coluna tiver saído da mesa entre o clique e agora, a recusa diz O controle escolhido não está na mesa — nada foi enviado, e também não é defeito.

---

## mapa-vibracao.rumble.habilitar-radio — Habilitar o motor no firmware (enable vibration) · rádio

*Célula:* `vibracao.rumble.habilitar @ rádio`

**O que isto prova.** Prova que, nos dois controles do rádio, o Hefesto liga a autorização de vibração no controle — sem ela nenhum motor obedeceria a coisa nenhuma.

**Onde olhar.** Não há campo na tela que mostre essa autorização: a fonte não diz onde se lê esse valor. O que se lê é a consequência — o punho tremendo depois de um clique em Testar. Olhe a aba Vibração, nas colunas do P3 e do P4, cujo cabeçalho tem de dizer rádio: os três botões Economia, Balanceado e Máximo; as duas linhas de motor com barra e número seguido de %; e os botões Testar e Parar no pé da coluna. Uma recusa aparece como tarja de recado dentro da própria coluna e fica cerca de meio minuto. As mãos dizem o resto.

**Os passos.**

1. Feche o jogo, se houver algum aberto.
2. Abra o Hefesto e clique na aba Jogar.
3. Confira que o Status está em Ligado.
4. Confira que o Modo escolhido não é o Modo Nativo.
5. Clique na aba Vibração.
6. Confira que o cabeçalho das colunas do P3 e do P4 diz rádio.
7. Escolha Balanceado nas quatro colunas.
8. Ponha as oito barras de motor em 100.
9. Segure o P3 nas duas mãos.
10. Clique em Testar na coluna do P3.
11. Confira que ele treme por cerca de meio segundo e para sozinho.
12. Olhe os outros três na mesa nesse instante e confira que nenhum se mexeu.
13. Clique em Testar de novo na coluna do P3 e, antes de o tremor acabar, clique em Parar na mesma coluna.
14. Confira que ele parou na hora.
15. Repita os cinco passos acima com o P4.
16. Clique em Testar na coluna do P1 e confira que ali também treme — é a comparação com o cabo.
17. Confira se apareceu alguma tarja de recado dentro de alguma coluna e leia o que ela diz.

**Passa quando.** Nos dois do rádio, um clique em Testar fez aquele controle — e só ele — tremer por cerca de meio segundo e parar sozinho; os outros três ficaram parados; e o Parar cortou na hora. O P1, no cabo, tremeu do mesmo jeito quando foi a vez dele. Nenhuma tarja de recado apareceu. Um controle do rádio mudo enquanto o do cabo treme, com a mesma configuração, é o achado deste teste.

**Por controle.**

* **P1** — Está no CABO e é testemunha, e também a comparação: ele não pode tremer quando o Testar clicado é o da coluna do P3 ou do P4, mas tem de tremer quando é o dele.
* **P2** — Também no cabo e também testemunha, com a mesma conferência. Use-o para repetir a comparação se o P1 der resposta estranha.
* **P3** — Está no RÁDIO e é um dos dois que têm de reagir. Treme meio segundo quando o Testar da coluna dele é clicado, e para na hora com o Parar.
* **P4** — Também no rádio, mesma resposta esperada. Se ele responder e o P3 não, ou o contrário, anote qual dos dois — é o aparelho, não o transporte.

**A armadilha.** Esta célula NÃO TEM MEDIÇÃO NENHUMA no mapa: a coluna que diz até onde a prova chegou está vazia, nos dois transportes. Você está fazendo o primeiro degrau, e um verde aqui só diz que os motores obedecem. Segunda: das quatro chavinhas de autorização, o produto liga três — a quarta, a da vibração nova dos firmwares mais recentes, nunca sobe, e é igual nos dois transportes de propósito. Ela não aparece em campo nenhum da tela, e é a primeira suspeita para um controle mudo em toda parte. Terceira: no rádio o comando vai numerado e conferido, e o controle descarta calado o que chegar fora de ordem — um Testar que não produz tremor nenhum, uma vez só, pede uma segunda tentativa antes de virar defeito. Quarta: em Modo Nativo o Testar é recusado de propósito, com a frase Vibração não aplicada: em Modo Nativo quem manda nos motores é o jogo, numa tarja dentro da coluna; e se o controle tiver saído da mesa a recusa diz O controle escolhido não está na mesa — nada foi enviado. Nos dois casos o produto está recusando direito.

---

## mapa-vibracao.rumble.passthrough-cabo — Rumble do JOGO roteado pelo Hefesto (vpad → físico) · cabo

*Célula:* `vibracao.rumble.passthrough @ cabo`

**O que isto prova.** Prova que a vibração que o jogo manda para UM jogador chega ao controle daquele jogador quando ele está no cabo — e não chega a mais nenhum.

**Onde olhar.** Na aba Vibração, coluna por coluna. No alto de cada uma, o desenho do controle acende em laranja o punho que está tremendo — é ele que diz, na tela, qual controle recebeu. Parando o mouse na linha Motor de vibração esquerdo ou direito de uma coluna, a dica diz quanto o jogo pediu naquele motor agora, de 0 a 255; **onde o jogo não está pedindo, não há dica** — o Hefesto apaga o aviso em vez de deixar número velho, e é isso que torna o silêncio dos outros três mensurável. E os quatro controles na mesa dizem o resto: um controle solto no tampo chacoalha de forma audível.

> **A contagem do pé da grade saiu da tela em 07/09/2026**, por ordem dela. Para esta célula a troca é ganho: aquela linha era cumulativa e ficava embaixo de TODAS as colunas, enquanto o punho e a dica são por jogador e ao vivo — que é exatamente o que "chegou a um e a mais nenhum" precisa medir.

**Os passos.**

1. Abra o Hefesto e clique na aba Jogar.
2. Confira que o Status está em Ligado.
3. Clique na aba Vibração.
4. Clique em Parar em cada uma das quatro colunas, para soltar qualquer vibração fixada de um teste anterior.
5. Escolha Balanceado nas quatro colunas.
6. Ponha as oito barras de motor em 100.
7. Abra o jogo com os quatro jogadores dentro da partida.
8. Apoie os quatro controles na mesa, separados uns dos outros, sem ninguém segurando.
9. Provoque no jogo uma vibração só para o jogador do P1 — um dano levado só por ele.
10. Olhe e escute os quatro na mesa: só o do jogador 1 pode chacoalhar.
11. Olhe os desenhos das quatro colunas: só o da coluna do P1 pode acender em laranja.
12. Confira na tela que só a coluna do Jogador 1 respondeu: o punho dela acendeu em laranja e a dica da linha do motor traz o número pedido, enquanto nas outras três o punho ficou apagado e a linha do motor não abre dica nenhuma.
13. Repita os quatro passos acima com o P2.
14. Provoque uma vibração para o jogador do P3 e confira que o P1 e o P2 ficam parados.
15. Repita com o P4.

**Passa quando.** A vibração de cada jogador chegou ao controle daquele jogador e a mais nenhum: os outros três ficaram parados na mesa e apagados no desenho. E a tela bateu com quem levou o dano nos DOIS sentidos — na coluna de quem levou, o punho acendeu em laranja e a dica da linha do motor trouxe o número que o jogo pediu; nas outras três, o punho ficou apagado e parar o mouse na linha do motor **não abriu dica nenhuma**.

**Por controle.**

* **P1** — Está no CABO e é um dos dois que têm de reagir. Ele chacoalha quando o jogador dele leva dano, e o desenho da coluna dele acende.
* **P2** — Também no cabo, mesma resposta. Um dos dois recebendo e o outro não, com a mesma partida, aponta para aquele controle — anote qual.
* **P3** — Está no RÁDIO e é testemunha: tem de ficar parado quando a vibração é do jogador do P1 ou do P2. Se chacoalhar junto, a vibração perdeu o endereço.
* **P4** — Também no rádio e também testemunha, com a mesma conferência. Ele é o último a entrar, e é nele que a falta de endereço costuma aparecer primeiro.

**A armadilha.** São DOIS retratos do MESMO defeito, e os dois enganam de jeitos opostos. Se os quatro chacoalharem juntos quando só um levou dano, a vibração perdeu o endereço e foi para a mesa inteira — é o defeito clássico desta célula. Mas se o controle CERTO ficar mudo enquanto a dica da linha do motor daquela coluna mostra o número que o jogo pediu, é o mesmo endereço perdido: hoje o Hefesto prefere descartar a espalhar, e o descarte não aparece em campo nenhum da tela. Nos dois casos o que fura é a comparação entre o que a COLUNA daquele jogador diz e o que a mão dele sentiu. Segunda, e é o tamanho da prova: no mapa esta célula parou em MONTOU — está provado que o Hefesto MONTA o comando, e não que o aparelho obedeceu. O que você está fazendo aqui é o degrau seguinte, e é a primeira vez que ele é medido; um vermelho aqui não é regressão, é a resposta que faltava. Terceira: controle apoiado no mesmo tampo transmite o tremor do vizinho — deixe-os separados, ou levante um de cada vez para decidir. Quarta: se você clicou em Testar pouco antes, aquele controle pode ter ficado com a vibração fixada, e nesse estado a do jogo é ignorada — o Parar em cada coluna, no começo, é o que evita.

---

## mapa-vibracao.rumble.passthrough-radio — Rumble do JOGO roteado pelo Hefesto (vpad → físico) · rádio

*Célula:* `vibracao.rumble.passthrough @ rádio`

**O que isto prova.** Prova que a vibração que o jogo manda para um jogador chega ao controle dele quando ele está no rádio — a metade desta célula que nunca foi medida.

**Onde olhar.** Na aba Vibração. Embaixo das quatro colunas, a linha que começa com um pontinho conta os pedidos do jogo por jogador. No alto das colunas do P3 e do P4 — cabeçalho com a palavra rádio — o desenho acende em laranja o lado que treme. E os quatro controles na mesa dizem o resto: um controle solto no tampo chacoalha de forma audível.

**Os passos.**

1. Abra o Hefesto e clique na aba Jogar.
2. Confira que o Status está em Ligado.
3. Clique na aba Vibração.
4. Confira que o cabeçalho das colunas do P3 e do P4 diz rádio.
5. Clique em Parar em cada uma das quatro colunas.
6. Escolha Balanceado nas quatro colunas.
7. Ponha as oito barras de motor em 100.
8. Abra o jogo com os quatro jogadores dentro da partida.
9. Apoie os quatro controles na mesa, separados uns dos outros, sem ninguém segurando.
10. Provoque no jogo uma vibração só para o jogador do P3.
11. Olhe e escute os quatro na mesa: só o do jogador 3 pode chacoalhar.
12. Olhe os desenhos das quatro colunas: só o da coluna do P3 pode acender em laranja.
13. Confira na tela que só a coluna do Jogador 3 respondeu: o punho dela acendeu em laranja e a dica da linha do motor traz o número pedido, enquanto nas outras três o punho ficou apagado e a linha do motor não abre dica nenhuma.
14. Repita os quatro passos acima com o P4.
15. Provoque uma vibração para o jogador do P1 e confira que o P3 e o P4 ficam parados.
16. Anote, com estas palavras, se os dois do rádio chacoalharam ou ficaram mudos.

**Passa quando.** A vibração do jogador do P3 chegou ao P3 e a mais nenhum, e a do P4 chegou ao P4; os outros três ficaram parados na mesa e apagados no desenho em cada rodada. Na coluna de quem levou o dano o punho acendeu e a dica do motor trouxe o número pedido; nas outras três o punho ficou apagado e a linha do motor não abriu dica. E os dois do rádio responderam como os dois do cabo respondem.

**Por controle.**

* **P1** — Está no CABO e é testemunha, e é também a comparação: ele não pode chacoalhar quando a vibração é do jogador do P3, mas tem de chacoalhar quando é a dele — é isso que separa o jogo não pediu de o rádio não recebeu.
* **P2** — Também no cabo e também testemunha, com a mesma dupla função. Use-o para repetir a comparação se o P1 der resposta estranha.
* **P3** — Está no RÁDIO e é um dos dois que têm de reagir. É a metade desta célula que ninguém nunca mediu: escreva o que aconteceu com ele, mesmo que tenha sido nada.
* **P4** — Também no rádio, mesma medição. Se um dos dois receber e o outro não, anote qual — é diferente de o rádio inteiro ficar mudo.

**A armadilha.** A metade do rádio desta célula está EM BRANCO no mapa: ninguém nunca mediu isto por rádio, e o branco não quer dizer não funciona, quer dizer que não houve resposta. Então aqui um mudo é resultado, não falha sua — anote com todas as letras. E há história: houve um tempo em que o comando montado para o rádio saía malformado e o controle o descartava inteiro, calado; o rádio vibrava zero e nada na tela dizia isso. O comando de hoje sai certo, mas o aparelho nunca confirmou. Se o P3 e o P4 ficarem mudos enquanto a dica da linha do motor das colunas deles traz o número que o jogo pediu, e o P1 chacoalhar no mesmo teste, é exatamente essa pergunta que você acabou de responder. Segunda: o defeito irmão anda ao contrário — se os QUATRO chacoalharem quando só um levou dano, a vibração perdeu o endereço e foi para a mesa inteira. Terceira: controle apoiado no mesmo tampo transmite o tremor do vizinho; separe-os, ou levante um de cada vez. Quarta: bateria baixa no rádio abaixa a força do motor — um chacoalho fraco demais para ouvir não é o mesmo que mudo; levante o controle e sinta antes de decidir.

---

## mapa-audio.alto_falante-radio — Alto-falante do controle — som saindo · rádio

*Célula:* `audio.alto_falante @ rádio`

**O que isto prova.** Prova que o som do jogo sai mesmo pelo alto-falante dos dois controles que estão no rádio — o caminho que só existe nesta casa desde 10/09/2026 — e entrega as duas metades que faltam para o mapa parar de dizer "não": o negativo de rota e a escuta cega. A primeira metade já foi feita e não se repete: o som saiu do plástico por rádio, setenta segundos contínuos, com o seu ouvido. O que falta é provar que ele saiu de LÁ e não de outro lugar.

**Onde olhar.** Na aba Controles do Hefesto. Clique na linha de um controle e o cartão dele abre (o que estava aberto fecha sozinho). Dentro do cartão, o bloco chamado Alto-falante: o deslizante de volume com o número ao lado, o botão ♪, e os dois botões de rota, "Sons do jogo" e "Todo o som do PC". Mas quem responde este teste é o seu OUVIDO, encostado no alto-falante do próprio controle: são nove furinhos em duas fileiras, na frente do DualSense, logo abaixo e entre os dois analógicos. E quem responde a segunda metade é outra pessoa: alguém precisa clicar por você, sem dizer o que clicou.

**Os passos.**

1. Clique na aba Controles.
2. Confira na fita do topo que P3 e P4 dizem rádio e que P1 e P2 dizem cabo.
3. Clique na linha do P3 para abrir o cartão dele.
4. Arraste o deslizante de volume do bloco Alto-falante do P3 até o fim da direita.
5. Confira que o número ao lado do deslizante diz 100.
6. Clique em "Todo o som do PC" no bloco do P3.
7. Toque um som bem marcado e curto, que se reconheça de ouvido — um toque de aviso, não uma música.
8. Encoste o ouvido no P3 e escute se ele sai por ali.
9. Encoste o ouvido no P4 e confirme que ele está mudo.
10. Encoste o ouvido no P1 e no P2 e confirme que os dois estão mudos.
11. Agora o NEGATIVO DE ROTA, e ele é o coração deste teste: escolha na aba Sistema do seu computador a saída da TV, e toque o MESMO som.
12. Encoste o ouvido no P3 enquanto ele toca na TV: o P3 tem de ficar MUDO.
13. Devolva a saída para o controle e toque o mesmo som mais uma vez para confirmar que ele voltou a sair do P3.
14. Chame outra pessoa e peça que ela faça, sem você ver a tela e sem falar nada, seis passadas em ordem embaralhada: três tocando no P3 e três tocando na TV.
15. A cada passada, com o ouvido no P3, diga em voz alta "controle" ou "TV", e peça que ela anote a sua resposta ao lado do que ela realmente fez.
16. Clique em "Sons do jogo" no bloco do P3 para devolver o som às caixas — não pule este passo.
17. Clique na linha do P4 e repita do passo 4 ao 13 nele, com o P3 agora de testemunha muda.

**Passa quando.** Sai som pelo alto-falante do P3 e pelo do P4, os dois que estão no rádio. O mesmo som, mirado na TV, NÃO sai de nenhum dos dois — esse é o negativo de rota, e sem ele o teste não passa mesmo que você tenha ouvido o som cem vezes. E as seis passadas cegas batem SEIS de seis: você acertou onde o som estava tocando sem saber o que a outra pessoa clicou. Cinco de seis já não passa: uma errada é ruído ou é vazamento, e nos dois casos a resposta é repetir.

**Por controle.**

* **P3** — No rádio, e é o alvo. Ele é quem toca, quem cala no negativo de rota e quem você escuta nas seis passadas cegas.
* **P4** — No rádio, e é a segunda prova do caminho: se só um dos dois tocar, o problema é daquele controle e não do rádio — anote qual falhou. Ele também é testemunha enquanto o P3 toca: se os dois tocarem juntos, o comando pegou o transporte inteiro em vez do controle escolhido, e isso é achado.
* **P1** — No cabo, e é TESTEMUNHA: você não toca nele. O som do P3 não pode sair dele.
* **P2** — No cabo, e é a segunda testemunha. Mesmo gesto do P1.

**A armadilha.** O botão ♪ NÃO faz barulho no rádio, e isso é por desenho, não defeito: a confirmação toca pelo sink daquele controle, e no rádio não há sink próprio para tocar. Se você clicar no ♪ esperando o som curto de confirmação e ele não vier, isso não desmente nada deste teste — o caminho do rádio não passa por ali. Segunda, e é regra desta casa com nome: ninguém pode concluir, de um canal responder, que ele FAZ o que a gente esperava dele. O canal do rádio aceitava bytes muito antes de tocar um som, e foi por isso que a casa mirou no report errado durante semanas. Terceira: "Todo o som do PC" tira o som das caixas e o joga no controle — esquecer de clicar em "Sons do jogo" no fim deixa a máquina muda e parece defeito sem ser. E quarta, que é a razão das seis passadas cegas: você SABE o que quer ouvir, e ouvido que sabe o que quer ouvir ouve. A escuta cega existe porque a sua própria expectativa é a fonte de erro mais provável deste teste — e ela já derrubou uma medição desta casa antes.

---

## mapa-audio.saida_dedicada.payload_do_degrau-radio — Saída de áudio por rádio — o CONTEÚDO do payload dos degraus · rádio

*Célula:* `audio.saida_dedicada.payload_do_degrau @ rádio`

**O que isto prova.** Prova que o que viaja DENTRO do canal do rádio é som de verdade — não que o canal aceitou bytes. São duas perguntas diferentes, e confundi-las custou semanas a esta casa: o aparelho respondia de bom grado a um report que não carregava áudio nenhum. Este teste separa as duas ouvindo o CONTEÚDO: um som que você reconhece sem hesitar, saindo com a forma que você mandou.

**Onde olhar.** Na aba Controles, no cartão do P3 e no do P4, bloco Alto-falante. O que se lê na tela é pouco de propósito: o volume, a rota e o ♪. O conteúdo do que viaja não tem tela e não vai ter — ele se prova com o ouvido, comparando o que saiu com o que foi mandado.

**Os passos.**

1. Clique na aba Controles.
2. Confira na fita do topo que P3 e P4 dizem rádio.
3. Escolha TRÊS sons bem diferentes um do outro: um grave longo, um agudo curto e uma voz falando uma frase que você reconheça.
4. Clique na linha do P3 e arraste o volume do bloco Alto-falante até 100.
5. Clique em "Todo o som do PC" no bloco do P3.
6. Toque o grave longo e escute com o ouvido no P3.
7. Toque o agudo curto e escute com o ouvido no P3.
8. Toque a voz e escute com o ouvido no P3: você tem de entender a frase, não só ouvir que tem som.
9. Anote, para cada um dos três, se o que saiu era o MESMO som — e não um estalo, um chiado ou um pedaço dele.
10. Arraste o volume do P3 até 30 e toque a voz de novo: ela tem de sair mais baixa e continuar compreensível.
11. Clique em "Sons do jogo" no bloco do P3 para devolver o som às caixas.
12. Clique na linha do P4 e repita do passo 4 ao 11 nele.
13. Deixe a voz tocando por dois minutos seguidos no P3 e escute o fim: ela não pode ter engasgado, cortado nem virado chiado no meio do caminho.

**Passa quando.** Os três sons saem reconhecíveis pelos dois controles do rádio, e a voz é COMPREENSÍVEL — não basta sair barulho. O volume em 30 abaixa o som sem quebrá-lo. E os dois minutos seguidos terminam sem engasgo: um caminho que entrega dez segundos e morre no terceiro minuto não entregou o payload, entregou uma amostra.

**Por controle.**

* **P3** — No rádio, e é o alvo. Os três sons, o volume baixo e os dois minutos seguidos são nele.
* **P4** — No rádio, e faz a mesma volta. Ele é a segunda prova de que o caminho é do RÁDIO e não daquele controle.
* **P1** — No cabo, e é testemunha muda. No cabo o som é uma saída comum do computador e não passa por este canal: se ele tocar junto, o que está tocando não é o que este teste mede.
* **P2** — No cabo, e é a segunda testemunha. Mesma leitura do P1.

**A armadilha.** A pergunta desta linha NÃO é "o canal responde" — é "o que viaja dentro dele é som". Duas fontes de fora descrevem o formato deste payload byte a byte, e as duas DIVERGEM entre si; e as duas erraram o report. Por isso a leitura de fonte não vale como resposta aqui, por mais detalhada que seja: só o ouvido responde. Segunda: a voz é o som que decide, e não por gosto — um estalo, um chiado e um engasgo todos soam como "tem som saindo", e só a fala mostra se o que chegou foi o som ou um pedaço dele. Terceira: dois minutos parecem exagero e não são. O caminho já entregou setenta segundos; o que ele nunca entregou é um trecho longo o bastante para uma falha de cadência aparecer.

---

## mapa-luz.led_jogador.brilho-cabo — LED de jogador — brilho de hardware (3 degraus) · cabo

*Célula:* `luz.led_jogador.brilho @ cabo`

**O que isto prova.** Prova que as lâmpadas de numeração do controle — as cinco luzinhas embaixo do touchpad que dizem quem é P1, P2, P3 e P4 — mudam de brilho pelos três degraus que o aparelho tem, no cabo. E prova, no mesmo gesto, uma coisa que hoje não é verdade: o produto ainda não liga o bit que autoriza esse byte, e por isso o degrau que ele manda é inerte. Esta é a metade que o teste mede e a bancada registra.

**Onde olhar.** Na aba Iluminação do Hefesto, no bloco de brilho do controle escolhido. E no PLÁSTICO: as lâmpadas de numeração ficam na frente do DualSense, embaixo do touchpad, em fileira. Elas NÃO são a barra de luz colorida que contorna o touchpad — a barra é outra grandeza, obedece por outro caminho e não entra neste teste. Olhe só as luzinhas brancas da numeração.

**Os passos.**

1. Clique na aba Iluminação.
2. Confira na fita do topo que P1 e P2 dizem cabo.
3. Escolha o P1 na fita do topo.
4. Olhe as lâmpadas de numeração do P1 no plástico e guarde na memória o brilho delas.
5. Arraste o deslizante de brilho até o mínimo.
6. Olhe as lâmpadas de numeração do P1 outra vez e anote se elas mudaram.
7. Arraste o deslizante de brilho até o máximo.
8. Olhe as lâmpadas de numeração do P1 outra vez e anote se elas mudaram.
9. Olhe a barra de luz colorida do P1 nas duas pontas do deslizante e anote se ELA mudou.
10. Escolha o P2 na fita do topo e repita do passo 4 ao 9 nele.
11. Anote as quatro respostas lado a lado: lâmpadas do P1, barra do P1, lâmpadas do P2, barra do P2.

**Passa quando.** As lâmpadas de numeração NÃO mudam de brilho em nenhuma das duas pontas do deslizante, nos dois controles do cabo — e a barra de luz colorida muda. É esse contraste que é a entrega: ele mostra que o deslizante chega ao aparelho (a barra prova) e que o degrau das lâmpadas não chega (elas provam). Se as lâmpadas MUDAREM, o produto passou a ligar o bit desde a última medição, e isso é achado: anote e avise, porque o mapa desta célula muda com essa resposta.

**Por controle.**

* **P1** — No cabo, e é o alvo. As duas pontas do deslizante, lâmpadas e barra olhadas separadamente.
* **P2** — No cabo, e é a segunda prova. Se o P1 e o P2 responderem diferente, o problema é de um controle e não do caminho — anote qual.
* **P3** — No rádio, e não entra neste teste: ele tem a volta dele, na linha do rádio.
* **P4** — No rádio, e também não entra aqui.

**A armadilha.** A barra de luz colorida e as lâmpadas de numeração são DUAS grandezas, e confundi-las é o erro que este teste existe para não repetir: elas ficam a centímetros uma da outra no mesmo plástico, e a barra obedece ao deslizante. Quem olhar a barra vai concluir que o brilho funciona — e o brilho que esta linha mede continua inerte. Olhe as luzinhas brancas da numeração, e só elas. Segunda: o brilho das lâmpadas tem TRÊS degraus no aparelho, não uma rampa contínua; se um dia elas obedecerem, a mudança vai ser em saltos, e um salto entre dois valores vizinhos pode passar despercebido — por isso os passos vão direto ao mínimo e ao máximo, nunca ao meio. Terceira: nada disso aparece na tela, e não vai aparecer. A dívida é nossa e fica no mapa, por ordem dela de 07/09/2026 — o produto não confessa dívida nossa para quem está usando.

---

## mapa-luz.led_jogador.brilho-radio — LED de jogador — brilho de hardware (3 degraus) · rádio

*Célula:* `luz.led_jogador.brilho @ rádio`

**O que isto prova.** O mesmo que a linha do cabo, e no rádio: as lâmpadas de numeração mudam de brilho pelos três degraus do aparelho, e o produto ainda não liga o bit que autoriza o byte. A razão de ser um teste próprio é que o envelope é outro — no rádio o degrau viaja noutro report, com uma conta de verificação no fim —, e um caminho que funciona no cabo não prova nada sobre o outro.

**Onde olhar.** Na aba Iluminação do Hefesto, no bloco de brilho do controle escolhido. E no PLÁSTICO: as lâmpadas de numeração, na frente do DualSense, embaixo do touchpad, em fileira. Não é a barra de luz colorida que contorna o touchpad.

**Os passos.**

1. Clique na aba Iluminação.
2. Confira na fita do topo que P3 e P4 dizem rádio.
3. Escolha o P3 na fita do topo.
4. Olhe as lâmpadas de numeração do P3 no plástico e guarde na memória o brilho delas.
5. Arraste o deslizante de brilho até o mínimo.
6. Olhe as lâmpadas de numeração do P3 outra vez e anote se elas mudaram.
7. Arraste o deslizante de brilho até o máximo.
8. Olhe as lâmpadas de numeração do P3 outra vez e anote se elas mudaram.
9. Olhe a barra de luz colorida do P3 nas duas pontas do deslizante e anote se ELA mudou.
10. Olhe as lâmpadas de numeração do P1, que está no cabo, e confirme que elas não mexeram enquanto você arrastava o deslizante do P3.
11. Escolha o P4 na fita do topo e repita do passo 4 ao 10 nele.
12. Anote as respostas lado a lado: lâmpadas do P3, barra do P3, lâmpadas do P4, barra do P4, e as testemunhas do cabo.

**Passa quando.** As lâmpadas de numeração NÃO mudam de brilho em nenhuma das duas pontas do deslizante, nos dois controles do rádio — e a barra de luz colorida muda. As lâmpadas do P1 e do P2 ficam paradas o tempo todo: o deslizante de um controle não pode mexer no outro. Se as lâmpadas do P3 ou do P4 MUDAREM, o produto passou a ligar o bit desde a última medição — anote e avise, porque o mapa desta célula muda com essa resposta.

**Por controle.**

* **P3** — No rádio, e é o alvo. As duas pontas do deslizante, lâmpadas e barra olhadas separadamente.
* **P4** — No rádio, e é a segunda prova do envelope do rádio. Se o P3 e o P4 responderem diferente, o problema é de um controle.
* **P1** — No cabo, e é TESTEMUNHA: você não toca nele. As lâmpadas dele não podem reagir ao deslizante do P3.
* **P2** — No cabo, e é a segunda testemunha. Mesma leitura do P1.

**A armadilha.** A mesma da linha do cabo, e uma a mais: no rádio o report leva uma conta de verificação no fim, e um envelope com essa conta errada é DESCARTADO pelo aparelho em silêncio. Ou seja, no rádio o "nada aconteceu" tem duas causas possíveis — o bit não foi ligado (que é o que esta casa sabe) ou o envelope foi recusado inteiro (que ninguém mediu). As duas se parecem exatamente na sua mão, e é por isso que o passo 9 existe: se a BARRA muda, o envelope chegou, e então o silêncio das lâmpadas é do bit. Se a barra também não mudar, você está olhando outro defeito, mais grave, e este teste não é quem responde por ele — anote e pare.

---

## mapa-audio.microfone.ganho-cabo — Microfone · ganho de entrada · cabo

*Célula:* `audio.microfone.ganho @ cabo`

**O que isto prova.** Prova que o segundo deslizante do bloco do Microfone — o **Ganho** — muda de verdade o quanto a placa amplifica a sua voz, e que o número que a tela mostra é o que a placa devolveu, não o que foi pedido. O ganho é da PLACA DE SOM do controle, e não do firmware do DualSense: ele não passa pelo daemon.

**Onde olhar.** Na aba Controles. Clique na linha de um controle **ligado pelo cabo** e o cartão dele abre. Dentro do cartão, o bloco do Microfone tem DOIS trilhos: o de cima é **Volume**, o de baixo é **Ganho**.

**Os passos.**

1. Clique na aba Controles.
2. Confira na fita do topo que o controle que você vai usar diz **cabo**.
3. Clique na linha dele para abrir o cartão.
4. Anote o número que o trilho **Ganho** mostra.
5. Arraste o trilho do Ganho para um valor bem diferente — 40, por exemplo — e solte.
6. Espere dois segundos sem clicar em mais nada.
7. Fale no microfone do controle e veja a barra de nível logo acima.

**O que tem de acontecer.** O número do Ganho fica no valor novo e **não volta sozinho**. A barra de nível responde à sua voz com altura diferente da de antes. Se o número saltar de volta ao antigo, o que a tela mostra é o pedido e não a resposta da placa.

**O que anotar.** O número antes, o que você arrastou, o que ficou na tela depois dos dois segundos, e se a barra de nível mudou de altura com a mesma voz.

---

## mapa-audio.microfone.ganho-radio — Microfone · ganho de entrada · rádio

*Célula:* `audio.microfone.ganho @ rádio`

**O que isto prova.** Prova que pelo rádio o produto **diz que não dá, e diz por quê** — em vez de oferecer um trilho que não faz nada. Pelo rádio o microfone chega como som já digitalizado, por um nó da ponte desta casa: não existe placa ALSA onde o elemento de ganho more. A recusa com a razão é a entrega desta célula.

**Onde olhar.** O mesmo lugar: aba Controles, cartão de um controle **ligado pelo rádio**, bloco do Microfone, trilho de baixo (**Ganho**).

**Os passos.**

1. Clique na aba Controles.
2. Confira na fita do topo que o controle que você vai usar diz **rádio**.
3. Clique na linha dele para abrir o cartão.
4. Olhe o trilho do **Ganho**: ele tem de estar **cinza**.
5. Clique no `?` ao lado dele e leia a frase que aparece.
6. Tente arrastar o trilho cinza.

**O que tem de acontecer.** O trilho fica cinza, o `?` explica que pelo rádio não há placa de som onde o ganho exista, e o arrasto não muda número nenhum. O que NÃO pode acontecer é o trilho parecer normal e não fazer nada — é o «efeito pronto e sem escolha» ao contrário.

**O que anotar.** Se o trilho estava cinza, a frase inteira do `?`, e se o arrasto mexeu em alguma coisa.

---

## mapa-audio.microfone.volume-cabo — Microfone · volume · cabo

*Célula:* `audio.microfone.volume @ cabo`

**O que isto prova.** Prova que o número ao lado da barra do microfone é o volume REAL do canal daquele controle, lido do sistema, e não um número do desenho. A célula nasceu em 12/09/2026, com a `MIC-VOLUME-02`: até esse dia a tela mostrava a barra de nível (que se move com a voz) mas o volume do canal não tinha endereço — quem mudasse o volume por fora via a tela continuar dizendo outra coisa.

**Onde olhar.** Na aba Controles. Clique na linha de um controle **ligado pelo cabo** e o cartão dele abre. Dentro do cartão, o bloco do Microfone: a barra de nível, o botão 🎙 e, ao lado, o número do volume.

**Os passos.**

1. Clique na aba Controles.
2. Confira na fita do topo que o controle que você vai usar diz **cabo**.
3. Clique na linha dele para abrir o cartão.
4. Anote o número do volume que a tela mostra.
5. Abra o painel de som do sistema, ache a entrada daquele controle e **mude o volume** — para 30, por exemplo.
6. Volte ao Hefesto sem fechar nada e espere dois segundos.

**O que tem de acontecer.** O número na tela acompanha o que você mudou por fora, sem você clicar em nada. Se ele ficar parado no valor antigo, a leitura não está chegando; se ele mostrar um número que o sistema não tem, a tela está inventando.

**O que anotar.** O número antes, o número que você pôs no painel do sistema, e o número que a tela mostrou depois — os três.

---

## mapa-audio.microfone.volume-radio — Microfone · volume · rádio

*Célula:* `audio.microfone.volume @ rádio`

**O que isto prova.** O mesmo que a de cima, pelo outro transporte — e aqui a pergunta tem uma metade a mais, porque pelo rádio o canal do microfone não é uma placa que o sistema publica sozinho: ele sobe pela ponte desta casa. Provar o volume no rádio é provar que a leitura atravessa essa ponte.

**Onde olhar.** O mesmo lugar: aba Controles, cartão do controle aberto, bloco do Microfone.

**Os passos.**

1. Clique na aba Controles.
2. Confira na fita do topo que o controle que você vai usar diz **rádio**.
3. Clique na linha dele para abrir o cartão.
4. Aperte o botão 🎙 para **ouvir a si mesma**: ele fica verde e assim continua até você clicar de novo.
5. Anote o número do volume.
6. Mude o volume daquele canal pelo painel de som do sistema e volte.

**O que tem de acontecer.** O número acompanha, igual ao do cabo. E há uma segunda coisa a ver: **o botão 🎙 fica verde e assim FICA** — ele é uma trava, como o do Discord, e só o clique seguinte o apaga. Você ouve a própria voz enquanto ele estiver verde; quem se move é a barra de nível.

**O que anotar.** Os três números, se o botão continuou verde sem você segurar nada, e se você se ouviu.
