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

## mapa-audio.saida_dedicada.payload_do_degrau-cabo — Saída de áudio por rádio — o CONTEÚDO do payload dos degraus · cabo

*Célula:* `audio.saida_dedicada.payload_do_degrau @ cabo`

**O que isto prova.** Prova que, no USB, o som do controle não passa pelo caminho do BT: o controle no USB tem placa de som própria, e o do BT só tem a saída que o Hefesto cria para ele.

**Onde olhar.** Fora do Hefesto, na lista de saídas das configurações de Som do sistema. Cada controle tem ali uma saída que começa com «Alto-falante do Controle», com o número do jogador — é o Hefesto que a cria, nos dois transportes. O controle que está no USB aparece uma segunda vez, com a placa de som do próprio DualSense e o nome da Sony; o que está no BT não tem essa segunda entrada. No Hefesto, a fita do topo diz USB ou BT ao lado de cada controle.

**Os passos.**

1. Confira na fita do topo que P1 e P2 dizem USB e que P3 e P4 dizem BT.
2. Abra as configurações de Som do sistema, na parte das saídas.
3. Confira que há uma saída «Alto-falante do Controle» com o número de cada um dos quatro: 1, 2, 3 e 4.
4. Conte as saídas com o nome DualSense que não começam com «Alto-falante do Controle»: têm de ser duas.
5. Feche as configurações de Som sem escolher nada.

**Passa quando.** A lista tem uma saída «Alto-falante do Controle» com o número de cada um dos quatro e exatamente duas placas DualSense, as do P1 e do P2, que estão no USB. O P3 e o P4 não acrescentam placa nenhuma.

**Por controle.**

* **P1** — No USB: tem as duas entradas, a do Hefesto e a placa do próprio controle.
* **P2** — No USB: a mesma coisa. Se só uma placa DualSense aparecer, um dos dois do USB está sem som próprio — anote.
* **P3** — No BT: só a entrada do Hefesto. É o CONTRASTE: o som dele viaja pelo fio do BT, e é esse fio que a pergunta desta linha examina.
* **P4** — No BT, e é o segundo contraste. Mesma leitura do P3.

**A armadilha.** Do lado do USB esta pergunta não tem objeto: o conteúdo que viaja pelo fio do BT não passa por aqui, e não há o que clicar além de conferir o contraste. As duas placas DualSense têm o mesmo nome e não dizem qual é qual — não é defeito, é a razão de o Hefesto criar a saída com o número do jogador. Se as saídas do Hefesto vierem com «(DualSense Wireless Controller)» no fim do nome, é a forma nova do nome: elas continuam começando com «Alto-falante do Controle», e é só por esse começo que você conta. Uma saída «Alto-falante do Controle» SEM número é de um controle que já passou por aqui e saiu: o Hefesto a mantém para não tirar o dispositivo debaixo de um jogo que o tinha escolhido, e ela não entra na conta.

---

# audio

---

## mapa-audio.alto_falante-cabo — Alto-falante do controle — som saindo · cabo

*Célula:* `audio.alto_falante @ cabo`

**O que isto prova.** Prova que o som sai mesmo pelo alto-falante dos dois controles do USB, um de cada vez, e que os dois do BT não tocam junto.

**Onde olhar.** Na aba Controles, no cartão de cada controle — clique na linha dele e o cartão abre; os outros fecham. Dentro do cartão, o bloco Alto-falante: a pílula ATIVO no rótulo, a barrinha de ondas (ela mexe com o som que o computador está mandando para aquele controle), o deslizante de volume com o número e o ♪, e, um sobre o outro, os botões «Efeitos do Jogo no Controle, Áudio da TV na TV», «Efeitos do Jogo e Áudio da TV no Controle» e «Tudo na TV e Nada no Controle». Mas quem responde é o seu OUVIDO, encostado no alto-falante do controle: os nove furinhos em duas fileiras, na frente do DualSense, entre os dois analógicos.

**Os passos.**

1. Clique na aba Controles.
2. Ponha uma música que se repita para tocar no computador.
3. Abaixe o volume da TV pelo controle remoto da própria TV até não ouvir mais a música, sem mexer no volume do computador.
4. Clique na linha do P1 para abrir o cartão dele.
5. Encoste o ouvido nos nove furinhos do P1 e deixe-o ali pela rodada inteira dele.
6. Arraste o deslizante de volume do bloco Alto-falante do P1 até 80 e solte.
7. Confira que saiu pelo P1 um som curto de confirmação.
8. Clique em «Efeitos do Jogo e Áudio da TV no Controle», no bloco Alto-falante do P1.
9. Confira que a música passou a sair pelo P1 e que a barrinha de ondas do bloco Alto-falante dele se mexe.
10. Clique em «Tudo na TV e Nada no Controle», no bloco do P1.
11. Confira que o P1 emudeceu e que a pílula do bloco continua dizendo ATIVO.
12. Clique em «Efeitos do Jogo no Controle, Áudio da TV na TV», no bloco do P1, para deixá-lo como estava.
13. Clique na linha do P2 e refaça nele a mesma rodada, do ouvido encostado até a volta ao botão de cima.
14. Encoste o ouvido no P3 e depois no P4 e confirme que os dois ficaram mudos o tempo todo.
15. Devolva o volume da TV pelo controle remoto dela.

**Passa quando.** No P1 e no P2 sai o som curto depois do arrasto, a música sai com o botão do meio aceso, e o controle emudece com «Tudo na TV e Nada no Controle». A pílula continua ATIVO nos três botões. O P3 e o P4 ficam mudos do começo ao fim.

**Por controle.**

* **P1** — No USB, e é o primeiro a tocar: o som curto no arrasto, a música com o botão do meio, o silêncio com o de baixo. No fim, volte ao botão de cima.
* **P2** — No USB, e faz a mesma rodada depois do P1. É a segunda prova do USB: se só um dos dois tocar, o defeito é daquele controle — anote qual.
* **P3** — No BT, e é TESTEMUNHA: você não toca nele. Se ele tocar junto com o P1, o comando pegou mais de um controle, e isso é achado.
* **P4** — No BT, e é a segunda testemunha. Mesmo gesto do P3: ouvido encostado, nenhum clique.

**A armadilha.** O botão do meio manda ao controle o MESMO som que vai para a TV — por isso a TV fica baixa, e baixa pelo controle remoto dela: o volume do computador fica parado para a régua não mudar no meio do teste. O som curto de confirmação não sai se outro ainda estiver tocando: solte o deslizante e espere antes do próximo arrasto. A pílula ATIVO não quer dizer que sai som — ela diz que o canal daquele controle existe e que ninguém calou o ♪, e é por isso que não muda com «Tudo na TV e Nada no Controle». Se aparecer «Saída muda» ao lado dela, o canal daquele controle está mudo no sistema, e o silêncio não é do Hefesto. Com um fone plugado no controle o som vai para o fone e o alto-falante cala — tire o fone antes. E o degrau: esta célula já chegou a «o aparelho obedeceu», com o seu ouvido; o que esta rodada confere é que ele continua obedecendo nos três botões de hoje.

---

## mapa-audio.alto_falante.preamp-cabo — Alto-falante — pré-amplificador · cabo

*Célula:* `audio.alto_falante.preamp @ cabo`

**O que isto prova.** Prova que o volume do alto-falante dos dois controles do USB muda de verdade ao longo de TODO o curso do deslizante, sem trecho morto — quem abre esse curso é o reforço de ganho, que viaja junto com o volume.

**Onde olhar.** Na aba Controles, no bloco Alto-falante do cartão aberto: o deslizante de volume e o número ao lado dele. O reforço de ganho NÃO tem campo na tela — ele sai na mesma mensagem que o volume —, e o que se lê é o efeito, com o ouvido encostado nos nove furinhos da frente do controle, entre os dois analógicos.

**Os passos.**

1. Clique na aba Controles.
2. Ponha uma música que se repita para tocar no computador, e não mexa mais no volume do computador até o fim.
3. Abaixe o volume da TV pelo controle remoto da própria TV até não ouvir mais a música.
4. Clique na linha do P1 para abrir o cartão dele.
5. Clique em «Efeitos do Jogo e Áudio da TV no Controle», no bloco Alto-falante do P1.
6. Encoste o ouvido nos nove furinhos do P1 e deixe-o ali pela rodada inteira dele.
7. Arraste o volume do Alto-falante do P1 até 20, solte e escute.
8. Arraste até 40, solte e confira que ficou mais alto que em 20.
9. Arraste até 60, solte e confira que ficou mais alto que em 40.
10. Arraste até 80, solte e confira que ficou mais alto que em 60.
11. Arraste até 100, solte e confira que ficou mais alto que em 80.
12. Arraste até 0, solte e confira que o P1 ficou em silêncio.
13. Clique em «Efeitos do Jogo no Controle, Áudio da TV na TV», no bloco do P1, e devolva o volume dele a 100.
14. Clique na linha do P2 e refaça nele a mesma rodada, do botão do meio até a volta, com as mesmas seis paradas.
15. Encoste o ouvido no P3 e depois no P4 e confirme que os dois ficaram mudos o tempo todo.
16. Devolva o volume da TV pelo controle remoto dela.

**Passa quando.** Em cada parada — 20, 40, 60, 80 e 100 — o P1 e o P2 soam audivelmente mais alto que na anterior: não há trecho em que arrastar não muda nada, nem trecho em que já saturou. Em 0 é silêncio. O P3 e o P4 ficam mudos do começo ao fim.

**Por controle.**

* **P1** — No USB, e é o primeiro. As seis paradas são nele, com a mesma música e o ouvido no mesmo lugar.
* **P2** — No USB, e faz as mesmas seis paradas. É a segunda prova: se o curso for útil num e morto no outro, o defeito é daquele aparelho, e não da conta que o Hefesto faz.
* **P3** — No BT, e é TESTEMUNHA. Não mexa nele. Se ele soar quando você arrasta o volume do P1, o comando pegou mais de um controle.
* **P4** — No BT, e é a segunda testemunha. Mesmo gesto do P3: ouvido encostado, nada arrastado.

**A armadilha.** A cada parada sai também o som curto de confirmação — compare a música, não o som curto. O reforço de ganho não se desliga pela tela, então não existe «com e sem» para comparar: o que se mede é só se o curso é útil de ponta a ponta. Um número velho anda por aí — «mudo até 38, satura em 102» —, levantado sem o reforço e na escala crua do aparelho, que não é o 0 a 100 do deslizante; não o use para julgar esta tela. E a prova desta célula parou em «montou»: o produto manda o reforço junto com o volume, e ninguém ouviu o efeito dele no aparelho — esta rodada é essa escuta.

---

## mapa-audio.alto_falante.preamp-radio — Alto-falante — pré-amplificador · rádio

*Célula:* `audio.alto_falante.preamp @ rádio`

**O que isto prova.** Prova que o volume do alto-falante dos dois controles do BT muda de verdade ao longo de todo o curso do deslizante, com o som chegando pelo próprio fio do BT.

**Onde olhar.** Na aba Controles, no cartão do P3 e no do P4, bloco Alto-falante: o deslizante de volume e o número ao lado. O reforço de ganho não tem campo na tela; o que se lê é o efeito, com o ouvido encostado nos nove furinhos da frente do controle. No BT, quem leva o som até o controle é o Hefesto, pelo mesmo fio por onde passam os botões.

**Os passos.**

1. Clique na aba Controles.
2. Ponha uma música que se repita para tocar no computador, e não mexa mais no volume do computador até o fim.
3. Abaixe o volume da TV pelo controle remoto da própria TV até não ouvir mais a música.
4. Clique na linha do P3 para abrir o cartão dele.
5. Clique em «Efeitos do Jogo e Áudio da TV no Controle», no bloco Alto-falante do P3.
6. Encoste o ouvido nos nove furinhos do P3 e confirme que a música sai por ali.
7. Arraste o volume do Alto-falante do P3 até 20, solte e escute.
8. Arraste até 40, solte e confira que ficou mais alto que em 20.
9. Arraste até 60, solte e confira que ficou mais alto que em 40.
10. Arraste até 80, solte e confira que ficou mais alto que em 60.
11. Arraste até 100, solte e confira que ficou mais alto que em 80.
12. Arraste até 0, solte e confira que o P3 ficou em silêncio.
13. Clique em «Efeitos do Jogo no Controle, Áudio da TV na TV», no bloco do P3, e devolva o volume dele a 100.
14. Clique na linha do P4 e refaça nele a mesma rodada, do botão do meio até a volta, com as mesmas seis paradas.
15. Encoste o ouvido no P1 e depois no P2 e confirme que os dois ficaram mudos o tempo todo.
16. Devolva o volume da TV pelo controle remoto dela.

**Passa quando.** Em cada parada o P3 e o P4 soam audivelmente mais alto que na anterior, sem trecho morto nem trecho saturado, e em 0 é silêncio. O P1 e o P2 ficam mudos do começo ao fim.

**Por controle.**

* **P1** — No USB, e é TESTEMUNHA. Não mexa nele. Se ele soar quando você arrasta o volume do P3, o comando pegou mais de um controle.
* **P2** — No USB, e é a segunda testemunha. Mesmo gesto do P1.
* **P3** — No BT, e é o primeiro. As seis paradas são nele, com a mesma música e o ouvido no mesmo lugar.
* **P4** — No BT, e faz as mesmas seis paradas. É a segunda prova do BT: se o curso for útil num e morto no outro, anote qual.

**A armadilha.** No BT o som leva um instante a mais para chegar: depois de soltar, espere a música assentar antes de comparar uma parada com a outra. No BT a queda e a volta são rotina: se o P3 cair e voltar no meio, a música some e volta e o volume pode voltar ao de antes — anote a hora e refaça aquela parada. O som curto de confirmação também pode sair a cada parada; compare a música, não ele. E a prova desta célula parou em «montou»: o produto manda o reforço de ganho pelo BT, e ninguém ouviu o efeito — esta rodada é essa escuta.

---

## mapa-audio.alto_falante.rota-cabo — Alto-falante — rota de saída · cabo

*Célula:* `audio.alto_falante.rota @ cabo`

**O que isto prova.** Prova que cada um dos três botões do alto-falante, nos dois controles do USB, faz o que o nome dele diz, e que trocar de botão não mata o microfone do mesmo controle.

**Onde olhar.** Na aba Controles, dois blocos do mesmo cartão. No bloco Alto-falante, os três botões, um sobre o outro, com um aceso: «Efeitos do Jogo no Controle, Áudio da TV na TV» (o controle toca só o que for mandado para ele; o som do computador fica na TV), «Efeitos do Jogo e Áudio da TV no Controle» (o som do computador sai também no controle, e continua na TV) e «Tudo na TV e Nada no Controle» (o controle para de tocar). No bloco Microfone, a pílula ao lado da palavra Microfone (ATIVO, DESLIGADO ou um travessão) e a barrinha de ondas, que mexe com o som que entra agora. O ouvido encostado nos nove furinhos do controle é quem confirma para onde o som foi.

**Os passos.**

1. Clique na aba Controles.
2. Ponha um vídeo com som para tocar no computador.
3. Abaixe o volume da TV pelo controle remoto da própria TV até não ouvir mais o vídeo.
4. Clique na linha do P1 para abrir o cartão dele.
5. Encoste o ouvido nos nove furinhos do P1 e deixe-o ali pela rodada inteira dele.
6. Clique em «Efeitos do Jogo no Controle, Áudio da TV na TV», no bloco Alto-falante do P1.
7. Confira que o P1 deu só o som curto de confirmação, sem o som do vídeo.
8. Fale perto do P1 e confira que a barrinha de ondas do bloco Microfone dele mexe e que a pílula do Microfone diz ATIVO.
9. Clique em «Efeitos do Jogo e Áudio da TV no Controle», no bloco do P1.
10. Confira que o som do vídeo passou a sair pelo P1.
11. Clique em «Tudo na TV e Nada no Controle», no bloco do P1.
12. Confira que o P1 emudeceu.
13. Fale perto do P1 e confira de novo que a barrinha do Microfone mexe e que a pílula continua ATIVO.
14. Clique em «Efeitos do Jogo no Controle, Áudio da TV na TV», no bloco do P1, para deixá-lo como estava.
15. Clique na linha do P2 e refaça nele a mesma rodada, do ouvido encostado até a volta ao botão de cima.
16. Clique em «Todos», na fita do topo, e confira que o botão aceso do P3 e o do P4 não mudaram.
17. Devolva o volume da TV pelo controle remoto dela.

**Passa quando.** No P1 e no P2 o botão aceso segue o clique, e o som vai para onde o nome dele diz: com o de cima, só o som curto — o vídeo fica fora do controle; com o do meio, o vídeo sai também no controle; com o de baixo, o controle cala. O microfone do mesmo controle continua vivo depois das trocas: a barrinha mexe quando você fala e a pílula não sai de ATIVO. O botão aceso do P3 e do P4 não trocou.

**Por controle.**

* **P1** — No USB, e é ELE que troca de botão primeiro. As duas conferências do microfone, depois do botão de cima e depois do de baixo, são o teste tanto quanto o som que sai.
* **P2** — No USB, e faz a mesma rodada, inclusive as duas conferências do microfone. Se o microfone morrer num e não no outro, anote em qual — é o que separa um defeito do aparelho de um defeito do comando.
* **P3** — No BT, e é TESTEMUNHA. Não clique em botão nenhum dele. Se o botão aceso dele trocou junto, o comando pegou mais de um controle.
* **P4** — No BT, e é a segunda testemunha. Mesma conferência do P3, e nenhum clique.

**A armadilha.** As duas conferências do microfone são metade do teste: pedir a rota escreve no mesmo byte do aparelho que carrega o caminho do microfone, e em 02/08/2026 isso levou o microfone daquele controle a zero. Foi curado, e esta conferência é o que o mantém curado. Ela é feita com o alto-falante daquele controle calado de propósito: com o vídeo tocando ao lado do microfone, a barrinha mexeria com o vídeo, e não com a sua voz. O «efeito do jogo» é o som que um jogo manda para aquele controle; sem jogo aberto, o único som endereçado ao controle é o som curto de confirmação, e por isso o vídeo NÃO pode sair nele com o botão de cima. A pílula do Alto-falante fica ATIVO nos três botões: ela fala do canal, não do botão. E o degrau: o botão de cima já obedeceu ao seu ouvido; o do meio e o de baixo são mais novos, e esta rodada é a medição deles.

---

## mapa-audio.alto_falante.rota-radio — Alto-falante — rota de saída · rádio

*Célula:* `audio.alto_falante.rota @ rádio`

**O que isto prova.** Prova que cada um dos três botões do alto-falante, nos dois controles do BT, faz o que o nome dele diz, que trocar de botão não apaga o microfone do mesmo controle, e que nada disso vaza para os dois do USB.

**Onde olhar.** Na aba Controles, no cartão do P3 e no do P4. No bloco Alto-falante, os três botões, um sobre o outro, com um aceso: «Efeitos do Jogo no Controle, Áudio da TV na TV», «Efeitos do Jogo e Áudio da TV no Controle» e «Tudo na TV e Nada no Controle» — cada um diz no nome para onde o som vai. No bloco Microfone do mesmo cartão, a pílula ao lado da palavra Microfone e a barrinha de ondas. No BT, quem leva o som até o controle é o Hefesto, pelo próprio fio do BT; o ouvido encostado nos nove furinhos confirma para onde ele foi.

**Os passos.**

1. Clique na aba Controles.
2. Ponha um vídeo com som para tocar no computador.
3. Abaixe o volume da TV pelo controle remoto da própria TV até não ouvir mais o vídeo.
4. Clique na linha do P3 para abrir o cartão dele.
5. Encoste o ouvido nos nove furinhos do P3 e deixe-o ali pela rodada inteira dele.
6. Clique em «Efeitos do Jogo no Controle, Áudio da TV na TV», no bloco Alto-falante do P3.
7. Confira que o som do vídeo não sai pelo P3, e anote se saiu um som curto de confirmação.
8. Fale perto do P3 e confira que a barrinha de ondas do bloco Microfone dele mexe e que a pílula do Microfone diz ATIVO.
9. Clique em «Efeitos do Jogo e Áudio da TV no Controle», no bloco do P3.
10. Confira que o som do vídeo passou a sair pelo P3.
11. Clique em «Tudo na TV e Nada no Controle», no bloco do P3.
12. Confira que o P3 emudeceu.
13. Fale perto do P3 e confira de novo que a barrinha do Microfone mexe e que a pílula continua ATIVO.
14. Clique em «Efeitos do Jogo no Controle, Áudio da TV na TV», no bloco do P3, para deixá-lo como estava.
15. Clique na linha do P4 e refaça nele a mesma rodada, do ouvido encostado até a volta ao botão de cima.
16. Clique em «Todos», na fita do topo, e confira que o botão aceso do P1 e o do P2 não mudaram.
17. Devolva o volume da TV pelo controle remoto dela.

**Passa quando.** No P3 e no P4 o botão aceso segue o clique, e o som vai para onde o nome dele diz: com o de cima, o vídeo fica fora do controle; com o do meio, o vídeo sai também no controle; com o de baixo, o controle cala. O microfone do mesmo controle continua vivo depois das trocas, com a pílula em ATIVO. O botão aceso do P1 e do P2 não trocou.

**Por controle.**

* **P1** — No USB, e é TESTEMUNHA. Não clique em nada nele. Se o botão aceso dele trocou, o comando pegou mais de um controle.
* **P2** — No USB, e é a segunda testemunha. Mesma conferência do P1. Um dos dois trocando e o outro não já diz que a mira do comando está errada — anote qual.
* **P3** — No BT, e é ELE que troca de botão primeiro, com o ouvido encostado e as duas conferências do microfone.
* **P4** — No BT, e faz a mesma rodada. É a segunda prova do BT: se um obedecer e o outro não, anote qual.

**A armadilha.** No BT o começo de um som curto pode ser comido enquanto o fio acorda — por isso o som de confirmação aqui é anotado, e não cobrado; o que decide é o vídeo, que é contínuo. No BT a queda e a volta são rotina: se o P3 cair e voltar no meio, o botão aceso pode voltar sozinho ao que era, e isso é a reconexão, não o seu clique — anote a hora e refaça. As conferências do microfone existem porque pedir a rota já apagou o microfone do mesmo controle, no USB, em 02/08/2026; elas são feitas com o alto-falante calado para a barrinha mexer com a sua voz e não com o vídeo. E a prova desta célula parou em «montou» pelo BT: o produto manda a rota, e ninguém ouviu o controle obedecer — esta rodada é essa escuta.

---

## mapa-audio.alto_falante.volume-cabo — Alto-falante — volume · cabo

*Célula:* `audio.alto_falante.volume @ cabo`

**O que isto prova.** Prova que o deslizante de volume manda no som dos dois controles do USB, e que o ♪ cala e devolve o alto-falante sem perder o número.

**Onde olhar.** Na aba Controles, no bloco Alto-falante do cartão aberto: a pílula ATIVO no rótulo (ela só vira DESLIGADO enquanto o ♪ está calado), o deslizante de volume, o número ao lado e o ♪. O som em si é do seu ouvido, encostado nos nove furinhos da frente do controle, entre os dois analógicos.

**Os passos.**

1. Clique na aba Controles.
2. Ponha uma música que se repita para tocar no computador.
3. Abaixe o volume da TV pelo controle remoto da própria TV até não ouvir mais a música.
4. Clique na linha do P1 para abrir o cartão dele.
5. Confira que o ♪ do bloco Alto-falante está aceso, e anote o número ao lado do deslizante.
6. Clique em «Efeitos do Jogo e Áudio da TV no Controle», no bloco Alto-falante do P1.
7. Encoste o ouvido nos nove furinhos do P1 e deixe-o ali pela rodada inteira dele.
8. Arraste o volume do P1 até 60, solte e escute.
9. Arraste até 100, solte e confira que ficou mais alto que em 60.
10. Arraste até 10, solte e confira que ficou mais baixo que em 60.
11. Clique no ♪ do P1 e confira que o som morreu no ato e que a pílula ao lado da palavra Alto-falante passou a dizer DESLIGADO.
12. Clique no ♪ de novo e confira que o som voltou baixo, como estava, com a pílula em ATIVO e o número ainda em 10.
13. Clique em «Todos», na fita do topo, e confira que os números de volume do P2, do P3 e do P4 não se mexeram.
14. Clique em «Efeitos do Jogo no Controle, Áudio da TV na TV», no bloco do P1, e devolva o volume dele ao número que você anotou.
15. Clique na linha do P2 e refaça nele a mesma rodada, do ♪ aceso até a volta.
16. Devolva o volume da TV pelo controle remoto dela.

**Passa quando.** No P1 e no P2 o ♪ já estava aceso, o número acompanha o arrasto e o quanto se ouve acompanha o número. O ♪ cala e traz de volta sem perder o número, e a pílula diz DESLIGADO só enquanto ele está calado. Os números dos outros três não se mexem enquanto você arrasta o de um.

**Por controle.**

* **P1** — No USB, e é o primeiro. Faça a rodada inteira nele, do ♪ aceso até a volta ao botão de cima.
* **P2** — No USB, e faz a mesma rodada. É a segunda prova: se o ♪ ou o volume funcionarem num e não no outro, anote qual.
* **P3** — No BT, e é TESTEMUNHA. Não arraste nada nele. Se o número dele andar quando você mexe no P1, o comando pegou mais de um controle.
* **P4** — No BT, e é a segunda testemunha. Mesma leitura do P3, com o deslizante intocado.

**A armadilha.** O ♪ nasce aceso porque o Hefesto põe o volume de todo controle em 100 assim que ele chega — decisão sua, de 16/08. Se ele estiver cinza, pare o mouse no «?» ao lado: a frase manda arrastar o volume uma vez, e o arrasto o destrava; anote que ele nasceu cinza, porque não devia. O número na tela é o que o produto PEDIU; só o ouvido diz o que saiu — marcar verde olhando o número é medir a tela contra ela mesma. Calar e trazer de volta são dois cliques separados porque o que se escuta é o silêncio ENTRE eles. O ♪ não mexe no microfone. E a prova desta célula parou em «montou»; o número velho «mudo até 38, satura em 102» é de outra escala e de antes do reforço de ganho, e não serve para julgar este deslizante.

---

## mapa-audio.alto_falante.volume-radio — Alto-falante — volume · rádio

*Célula:* `audio.alto_falante.volume @ rádio`

**O que isto prova.** Prova que o deslizante de volume manda no som dos dois controles do BT — com o som saindo pelo próprio fio do BT —, que o ♪ cala e devolve sem perder o número, e que nada disso vaza para os dois do USB.

**Onde olhar.** Na aba Controles, no cartão do P3 e no do P4, bloco Alto-falante: a pílula ATIVO no rótulo, o deslizante de volume, o número ao lado e o ♪. O som é do seu ouvido, encostado nos nove furinhos da frente do controle. No BT, quem leva o som até o controle é o Hefesto, pelo mesmo fio por onde passam os botões.

**Os passos.**

1. Clique na aba Controles.
2. Ponha uma música que se repita para tocar no computador.
3. Abaixe o volume da TV pelo controle remoto da própria TV até não ouvir mais a música.
4. Clique na linha do P3 para abrir o cartão dele.
5. Confira que o ♪ do bloco Alto-falante está aceso, e anote o número ao lado do deslizante.
6. Clique em «Efeitos do Jogo e Áudio da TV no Controle», no bloco Alto-falante do P3.
7. Encoste o ouvido nos nove furinhos do P3 e confirme que a música sai por ali.
8. Arraste o volume do P3 até 60, solte e escute.
9. Arraste até 100, solte e confira que ficou mais alto que em 60.
10. Arraste até 10, solte e confira que ficou mais baixo que em 60.
11. Clique no ♪ do P3 e confira que o som morreu e que a pílula ao lado da palavra Alto-falante passou a dizer DESLIGADO.
12. Clique no ♪ de novo e confira que o som voltou baixo, como estava, com a pílula em ATIVO e o número ainda em 10.
13. Clique em «Todos», na fita do topo, e confira que os números de volume do P1, do P2 e do P4 não se mexeram.
14. Clique em «Efeitos do Jogo no Controle, Áudio da TV na TV», no bloco do P3, e devolva o volume dele ao número que você anotou.
15. Clique na linha do P4 e refaça nele a mesma rodada, do ♪ aceso até a volta.
16. Devolva o volume da TV pelo controle remoto dela.

**Passa quando.** No P3 e no P4 o ♪ já estava aceso, o número acompanha o arrasto e o quanto se ouve acompanha o número. O ♪ cala e traz de volta sem perder o número, com a pílula em DESLIGADO só enquanto ele está calado. Os números do P1 e do P2 ficam parados.

**Por controle.**

* **P1** — No USB, e é TESTEMUNHA. Não arraste nada nele. Se o número dele andar, o comando pegou mais de um controle.
* **P2** — No USB, e é a segunda testemunha. Mesma leitura do P1. Um andando e o outro não já mostra que a mira do comando está errada.
* **P3** — No BT, e é o primeiro a mexer: o ♪ aceso, as três paradas com o ouvido encostado, o calar e o trazer de volta.
* **P4** — No BT, e faz a mesma rodada. É a segunda prova do BT: o volume e o ♪ dele têm de responder igual aos do P3.

**A armadilha.** No BT a queda e a volta são rotina: se o ♪ mudar sozinho, ou o número voltar ao que era sem você fazer nada, anote a HORA — é exatamente a perda silenciosa que este teste consegue enxergar, e vale mais que o resto do resultado. No BT o som leva um instante a mais para chegar: depois de soltar, espere a música assentar antes de comparar. O número na tela é o que o produto PEDIU; só o ouvido diz o que saiu. E a prova desta célula parou em «montou»: o produto manda o volume pelo BT, e ninguém ouviu o controle obedecer — esta rodada é essa escuta.

---

## mapa-audio.jack.deteccao-cabo — Jack — detecção de fone/microfone plugados · cabo

*Célula:* `audio.jack.deteccao @ cabo`

**O que isto prova.** Prova que, plugando um fone na entrada do próprio controle no USB, o som muda de lugar: sai do alto-falante do controle e passa para o fone.

**Onde olhar.** No aparelho: a entrada de fone fica na borda de baixo do DualSense, no meio, ao lado de onde o cabo entra; o alto-falante são os nove furinhos na frente, entre os dois analógicos. NA TELA NÃO HÁ ONDE LER «fone plugado» — nenhuma das dez abas mostra essa leitura. O que se mede é a consequência, com o ouvido; e, no bloco Alto-falante do cartão, repara-se se o botão aceso muda quando o fone entra.

**Os passos.**

1. Clique na aba Controles.
2. Separe um fone de plugue fino e prove-o antes num celular ou no computador.
3. Ponha uma música que se repita para tocar no computador.
4. Abaixe o volume da TV pelo controle remoto da própria TV até não ouvir mais a música.
5. Clique na linha do P1 para abrir o cartão dele.
6. Clique em «Efeitos do Jogo e Áudio da TV no Controle», no bloco Alto-falante do P1.
7. Encoste o ouvido nos nove furinhos do P1 e confirme que a música sai por ali.
8. Anote qual dos três botões do bloco Alto-falante do P1 está aceso.
9. Plugue o fone na entrada da borda de baixo do P1 e ponha-o num ouvido.
10. Confira que a música passou para o fone.
11. Encoste o outro ouvido nos furinhos do P1 e confira que o alto-falante emudeceu.
12. Olhe o bloco Alto-falante do P1 e anote se o botão aceso mudou.
13. Tire o fone e confira, com o ouvido nos furinhos, que a música voltou para o alto-falante do P1.
14. Clique em «Efeitos do Jogo no Controle, Áudio da TV na TV», no bloco do P1.
15. Clique na linha do P2 e refaça nele a mesma rodada, do botão do meio até a volta, com o mesmo fone.
16. Encoste o ouvido no P3 e depois no P4 e confirme que os dois ficaram mudos do começo ao fim.
17. Devolva o volume da TV pelo controle remoto dela.

**Passa quando.** No P1 e no P2 plugar o fone MUDA o som de lugar: o fone toca e o alto-falante do controle emudece; tirar o fone traz a música de volta ao alto-falante. O P3 e o P4 ficam mudos do começo ao fim.

**Por controle.**

* **P1** — No USB, e é o primeiro: ouvir no alto-falante, plugar, ouvir no fone, conferir o alto-falante mudo, tirar, ouvir o alto-falante de novo.
* **P2** — No USB, e faz a mesma rodada com o MESMO fone. É a segunda prova: se o som mudar de lugar num e não no outro, o problema é daquele controle — anote qual.
* **P3** — No BT, e é TESTEMUNHA. Não plugue nada nele. Se ele começar a soar quando o fone entra no P1, alguma coisa pegou mais de um controle.
* **P4** — No BT, e é a segunda testemunha. Mesmo gesto do P3.

**A armadilha.** Não há campo na tela para ler, e por isso, se o som não mudar de lugar, não conclua logo que a detecção falhou: pode ser o fone — é por isso que ele é provado antes. Se o fone tocar igual nos dois lados, ou só de um, anote: três das quatro rotas do aparelho saem mono no fone, medido por você em 09/09. O botão aceso mudar quando o fone entra não é defeito nem acerto — é anotação; o que decide é o ouvido. E a prova desta célula parou em «montou»: o produto lê o aviso de fone plugado, e ninguém ainda pôs e tirou um fone olhando — esta rodada é a primeira.

---

## mapa-audio.jack.deteccao-radio — Jack — detecção de fone/microfone plugados · rádio

*Célula:* `audio.jack.deteccao @ rádio`

**O que isto prova.** Mede o que acontece quando se pluga um fone num controle do BT que está tocando: se o som passa para o fone, se o alto-falante cala, ou se nada muda.

**Onde olhar.** No aparelho: a entrada de fone na borda de baixo do P3 e do P4, e o alto-falante nos nove furinhos da frente. Na tela não há onde ler «fone plugado»; o que se olha, no cartão do P3 e no do P4 na aba Controles, é se alguma coisa no bloco Alto-falante muda quando o fone entra. No BT, quem leva o som até o controle é o Hefesto, pelo próprio fio do BT.

**Os passos.**

1. Clique na aba Controles.
2. Separe um fone de plugue fino e prove-o antes num celular ou no computador.
3. Ponha uma música que se repita para tocar no computador.
4. Abaixe o volume da TV pelo controle remoto da própria TV até não ouvir mais a música.
5. Clique na linha do P3 para abrir o cartão dele.
6. Clique em «Efeitos do Jogo e Áudio da TV no Controle», no bloco Alto-falante do P3.
7. Encoste o ouvido nos nove furinhos do P3 e confirme que a música sai por ali.
8. Plugue o fone na entrada da borda de baixo do P3 e ponha-o num ouvido.
9. Anote se a música passou para o fone, se continuou no alto-falante, ou se sumiu dos dois.
10. Olhe o cartão do P3 e anote se alguma coisa no bloco Alto-falante mudou quando o fone entrou.
11. Tire o fone e confira, com o ouvido nos furinhos, que a música voltou para o alto-falante do P3.
12. Clique em «Efeitos do Jogo no Controle, Áudio da TV na TV», no bloco do P3.
13. Clique na linha do P4 e refaça nele a mesma rodada, do botão do meio até a volta, com o mesmo fone.
14. Encoste o ouvido no P1 e depois no P2 e confirme que os dois ficaram mudos do começo ao fim.
15. Devolva o volume da TV pelo controle remoto dela.

**Passa quando.** A música sai pelo alto-falante do P3 e do P4 antes do fone e volta para ele depois que o fone sai. O que aconteceu com o fone plugado está anotado nos dois — essa anotação é a entrega, porque ninguém mediu ainda o que o BT faz com um fone. Se o fone tocou num e não no outro, anote qual. O P1 e o P2 ficam mudos.

**Por controle.**

* **P1** — No USB, e é TESTEMUNHA. Não plugue nada nele. Se ele soar durante o teste do P3, alguma coisa pegou mais de um controle.
* **P2** — No USB, e é a segunda testemunha. Mesmo gesto do P1.
* **P3** — No BT, e é ELE que recebe o fone primeiro: a música no alto-falante, o fone plugado, a anotação, o fone fora.
* **P4** — No BT, e recebe o mesmo fone depois. É a segunda prova do BT: a resposta dele tem de ser anotada tanto quanto a do P3.

**A armadilha.** No USB o fone manda por cima do alto-falante — está medido, e é o que o teste irmão do USB confere. No BT ninguém sabe: o caminho do fone que o sistema conhece só existe no USB, e o som que o Hefesto leva pelo BT vai endereçado ao alto-falante. Por isso aqui não há resposta errada — «o fone ficou mudo e o alto-falante continuou» é resultado tão válido quanto «o som passou para o fone»; escreva o que ouviu. Prove o fone antes: sem isso, um fone ruim e o BT dão o mesmo silêncio. E a prova desta célula parou em «montou»: o produto lê o aviso de fone plugado também pelo BT, e ninguém plugou um fone para ver.

---

## mapa-audio.jack.volume-cabo — Fone de ouvido (jack do controle) — volume · cabo

*Célula:* `audio.jack.volume @ cabo`

**O que isto prova.** Prova que, com o fone plugado no controle, o mesmo deslizante do bloco Alto-falante manda também no volume do fone, nos dois controles do USB.

**Onde olhar.** Na aba Controles, no bloco Alto-falante do cartão aberto: o deslizante de volume, o número ao lado e o ♪. NÃO existe na tela um volume próprio do fone — é este mesmo deslizante que vai para os dois. A resposta é o fone no seu ouvido, plugado na borda de baixo do controle, ao lado de onde o cabo entra.

**Os passos.**

1. Clique na aba Controles.
2. Ponha uma música que se repita para tocar no computador, e não mexa mais no volume do computador até o fim.
3. Abaixe o volume da TV pelo controle remoto da própria TV até não ouvir mais a música.
4. Clique na linha do P1 para abrir o cartão dele.
5. Clique em «Efeitos do Jogo e Áudio da TV no Controle», no bloco Alto-falante do P1.
6. Plugue o fone na entrada da borda de baixo do P1 e ponha-o no ouvido.
7. Arraste o volume do P1 até 20, solte e escute no fone.
8. Arraste até 50, solte e confira que o fone ficou mais alto.
9. Arraste até 100, solte e confira que o fone ficou mais alto de novo — e anote o número em que ele parou de subir, se isso acontecer.
10. Arraste até 0, solte e confira que o fone ficou em silêncio.
11. Arraste de volta até 50 e clique no ♪: o fone tem de calar.
12. Clique no ♪ de novo: a música tem de voltar ao fone.
13. Tire o fone e clique em «Efeitos do Jogo no Controle, Áudio da TV na TV», no bloco do P1.
14. Clique na linha do P2 e refaça nele a mesma rodada, do botão do meio até a volta, com o mesmo fone.
15. Clique em «Todos», na fita do topo, e confira que os números de volume do P3 e do P4 não se mexeram.
16. Devolva o volume da TV pelo controle remoto dela.

**Passa quando.** No fone plugado no P1 e no plugado no P2, o quanto se ouve acompanha o deslizante, 0 é silêncio e o ♪ cala e traz de volta. Os números do P3 e do P4 não se mexem enquanto você arrasta o de um controle do USB.

**Por controle.**

* **P1** — No USB, e é o primeiro a receber o fone. As quatro paradas e os dois cliques do ♪ são nele, com o fone no ouvido.
* **P2** — No USB, e recebe o MESMO fone depois. É a segunda prova: se o volume do fone seguir o deslizante num e não no outro, anote qual.
* **P3** — No BT, e é TESTEMUNHA. Não plugue nem arraste nada nele. Se o número dele andar, o comando pegou mais de um controle.
* **P4** — No BT, e é a segunda testemunha. Mesma leitura do P3.

**A armadilha.** O fone não tem deslizante próprio na tela: o do Alto-falante vai para os dois, e o som mudar no fone prova que esse único campo alcança o fone — não que exista um campo do fone. A licença para mexer no volume do fone não está no sistema: veio de fonte de comunidade, e a curva do deslizante foi levantada no alto-falante, nunca no fone. Se acima da metade o fone parar de subir, é ACHADO, e o passo do 100 existe para você anotar onde. Se o fone tocar só de um lado, anote qual. E a prova desta célula parou em «montou»: ninguém desta casa plugou um fone e arrastou este deslizante.

---

## mapa-audio.jack.volume-radio — Fone de ouvido (jack do controle) — volume · rádio

*Célula:* `audio.jack.volume @ rádio`

**O que isto prova.** Prova que o volume é aceito nos dois controles do BT com um fone plugado, e mede se o fone toca pelo BT — e, se tocar, se o volume dele acompanha o deslizante.

**Onde olhar.** Na aba Controles, no cartão do P3 e no do P4, bloco Alto-falante: o deslizante de volume, o número ao lado e o ♪. Não existe na tela um volume próprio do fone: é o mesmo deslizante do alto-falante. O fone vai na borda de baixo do controle.

**Os passos.**

1. Clique na aba Controles.
2. Separe um fone de plugue fino e prove-o antes num celular ou no computador.
3. Ponha uma música que se repita para tocar no computador, e não mexa mais no volume do computador até o fim.
4. Abaixe o volume da TV pelo controle remoto da própria TV até não ouvir mais a música.
5. Clique na linha do P3 para abrir o cartão dele.
6. Clique em «Efeitos do Jogo e Áudio da TV no Controle», no bloco Alto-falante do P3.
7. Plugue o fone na entrada da borda de baixo do P3 e ponha-o no ouvido.
8. Anote se a música sai no fone.
9. Arraste o volume do P3 até 20, solte e escute no fone.
10. Arraste até 50, solte e escute de novo.
11. Arraste até 100, solte e escute de novo.
12. Tire o fone e clique em «Efeitos do Jogo no Controle, Áudio da TV na TV», no bloco do P3.
13. Clique na linha do P4 e refaça nele a mesma rodada, do botão do meio até a volta, com o mesmo fone.
14. Clique em «Todos», na fita do topo, e confira que os números de volume do P1 e do P2 não se mexeram.
15. Devolva o volume da TV pelo controle remoto dela.

**Passa quando.** O número acompanha o deslizante no P3 e no P4, e os números do P1 e do P2 ficam parados. Se o fone tocou, o quanto se ouve nele acompanha o número; se não tocou, o silêncio está anotado — o que o BT faz com um fone plugado ainda não foi medido, e essa anotação é a entrega.

**Por controle.**

* **P1** — No USB, e é TESTEMUNHA. Não plugue nem arraste nada nele. Anote o número do volume dele antes e confira depois.
* **P2** — No USB, e é a segunda testemunha. Mesma leitura do P1.
* **P3** — No BT, e é o primeiro a receber o fone: a anotação de onde a música sai, e as três paradas com o fone no ouvido.
* **P4** — No BT, e recebe o mesmo fone depois. É a segunda prova do BT: a resposta dele tem de ser anotada tanto quanto a do P3.

**A armadilha.** Prove o fone antes: sem isso, um fone ruim e o BT dão exatamente o mesmo silêncio. O som que o Hefesto leva pelo BT vai endereçado ao alto-falante, e ninguém sabe se o controle o desvia para o fone — se o fone ficar mudo e a música continuar nos furinhos, isso é resultado, não erro seu. No BT a queda e a volta são rotina: se o número voltar sozinho ao que era enquanto você testa, anote a HORA. E lembre-se de que o que você arrasta é o deslizante do alto-falante, que carrega os dois.

---

## mapa-audio.leitura_de_volta-cabo — Áudio — leitura de volta (qualquer registrador) · cabo

*Célula:* `audio.leitura_de_volta @ cabo`

**O que isto prova.** Mede o que o Hefesto consegue LER DE VOLTA do som dos dois controles do USB: o mudo do microfone volta do aparelho a cada aperto, e o volume do alto-falante não volta — o número na tela é o último que o Hefesto mandou.

**Onde olhar.** Na aba Controles, no cartão aberto, dois lugares que dão respostas opostas. No bloco Microfone, a pílula ao lado da palavra Microfone: ATIVO, DESLIGADO ou um travessão — o travessão quer dizer «não consegui ler», e não é nenhum dos dois. No bloco Alto-falante, o número do volume e a pílula ATIVO. No aparelho, o botão de microfone é o botãozinho logo abaixo do botão PS, e a luz dele fica acesa com o microfone ligado e apaga no mudo.

**Os passos.**

1. Clique na aba Controles.
2. Clique em «Todos», na fita do topo, e anote a pílula do Microfone e o número do volume do Alto-falante dos quatro.
3. Clique na linha do P1 para abrir o cartão dele.
4. Aperte uma vez o botão de microfone no plástico do P1.
5. Confira que a pílula do Microfone do P1 passou a DESLIGADO e que a luz desse botão apagou.
6. Espere um segundo e aperte o botão do P1 de novo.
7. Confira que a pílula voltou a ATIVO e que a luz acendeu.
8. Arraste o volume do Alto-falante do P1 até 70 e solte.
9. Feche a janela do Hefesto no X e abra-a de novo.
10. Clique na linha do P1 e anote o número do volume do Alto-falante e a pílula dele agora.
11. Clique na linha do P2 e refaça nele a mesma rodada, do primeiro aperto até a anotação depois de reabrir a janela.
12. Clique em «Todos» e confira que a pílula e o número do P3 e do P4 continuam os do começo.

**Passa quando.** No P1 e no P2 a pílula do Microfone SEGUE o botão do plástico a cada aperto — essa é uma leitura que volta do aparelho. O volume do alto-falante não volta de lá: o número depois de reabrir a janela é o último que o Hefesto mandou, e a entrega deste teste é esse número anotado. Nada mudou no P3 e no P4.

**Por controle.**

* **P1** — No USB, e é o primeiro: os dois apertos com um segundo entre eles, olhando a pílula e a luz, e depois o volume e a janela reaberta.
* **P2** — No USB, e faz a mesma rodada. É a segunda prova: se a pílula seguir o botão num e não no outro, anote qual.
* **P3** — No BT, e é TESTEMUNHA. Não aperte nem arraste nada nele. A pílula e o número dele ficam parados o tempo todo.
* **P4** — No BT, e é a segunda testemunha. Mesma conferência do P3.

**A armadilha.** Esta linha ainda não tem resposta, e o que está em disputa é o que «ler de volta» quer dizer — a decisão é sua, e ainda não foi tomada. Se for «qualquer estado relido do aparelho», a pílula do microfone já responde que sim; se for «o volume que nós mandamos, relido», a resposta continua sendo não. Enquanto isso, nada aqui reprova o produto: escreva o que aconteceu, aperto por aperto. Dê um segundo entre um aperto e o seguinte no mesmo controle: apertos mais rápidos são engolidos de propósito. O 🎙 da tela não cala o microfone — ele liga o retorno, para você se ouvir — e não interfere nesta leitura.

---

## mapa-audio.leitura_de_volta-radio — Áudio — leitura de volta (qualquer registrador) · rádio

*Célula:* `audio.leitura_de_volta @ rádio`

**O que isto prova.** Mede o que o Hefesto consegue ler de volta dos dois controles do BT, e o que sobra dessa leitura depois de uma queda e uma volta — que no BT é rotina.

**Onde olhar.** Na aba Controles, no cartão aberto: no bloco Microfone, a pílula ao lado da palavra Microfone (ATIVO, DESLIGADO ou um travessão); no bloco Alto-falante, o número do volume e a pílula ATIVO. No aparelho, o botão de microfone é o botãozinho logo abaixo do botão PS, com a luz acesa no microfone ligado e apagada no mudo; e o botão PS é o redondo do meio, entre os dois analógicos.

**Os passos.**

1. Clique na aba Controles.
2. Clique em «Todos», na fita do topo, e anote a pílula do Microfone e o número do volume do Alto-falante dos quatro.
3. Clique na linha do P3 para abrir o cartão dele.
4. Aperte uma vez o botão de microfone no plástico do P3.
5. Confira que a pílula do Microfone do P3 passou a DESLIGADO e que a luz desse botão apagou.
6. Espere um segundo e aperte o botão do P3 de novo.
7. Confira que a pílula voltou a ATIVO e que a luz acendeu.
8. Arraste o volume do Alto-falante do P3 até 70 e solte.
9. Desligue o P3 segurando o botão PS até TODAS as luzes dele apagarem.
10. Religue o P3 apertando o botão PS e espere a linha dele voltar à aba.
11. Clique na linha do P3 e anote a pílula do Microfone, a luz do botão de microfone, o número do volume e a pílula do Alto-falante agora.
12. Clique na linha do P4 e refaça nele a mesma rodada, do primeiro aperto até a anotação depois da volta.
13. Clique em «Todos» e confira que a pílula e o número do P1 e do P2 continuam os do começo.

**Passa quando.** No P3 e no P4 a pílula do Microfone segue o botão do plástico a cada aperto. O que este teste entrega é o que você anotou depois de o controle cair e voltar — a pílula, a luz, o número e a pílula do alto-falante. Nada mudou no P1 e no P2.

**Por controle.**

* **P1** — No USB, e é TESTEMUNHA. Não toque nele. A pílula e o número dele são os mesmos do começo ao fim.
* **P2** — No USB, e é a segunda testemunha. Se um dos dois do USB mudar quando o P3 cai e volta, isso é achado.
* **P3** — No BT, e é o primeiro: os dois apertos, o volume, e então desligar e religar ELE pelo botão PS. É a queda e a volta que este teste veio medir.
* **P4** — No BT, e faz a mesma rodada, inclusive desligar e religar. Se um perder o estado e o outro não, anote qual.

**A armadilha.** Esta linha ainda não tem resposta, e o sentido dela é decisão sua, ainda não tomada — escreva o que aconteceu, não «passou» nem «reprovou». Quando o controle volta, o Hefesto torna a escrever o volume: o número que aparece vem dele, e não do aparelho. O mudo do microfone mora no vínculo com o aparelho, que se refaz a cada reconexão — se ele voltar diferente do que era, é o achado desta linha, não erro seu; anote a hora. Para desligar, segure o PS até as luzes apagarem de verdade: soltar antes é lido como toque, e o toque abre a Steam — se ela abrir, feche-a e refaça. Dê um segundo entre um aperto e o seguinte no mesmo controle.

---

## mapa-audio.microfone-cabo — Microfone — captação do áudio · cabo

*Célula:* `audio.microfone @ cabo`

**O que isto prova.** Prova que o microfone dos dois controles do USB capta a sua voz e que ela chega ao computador — você se ouve pelo Hefesto, e um programa de fora te ouve —, um controle de cada vez.

**Onde olhar.** Na aba Controles, no bloco Microfone do cartão aberto: a pílula ao lado da palavra Microfone (ATIVO, DESLIGADO ou um travessão), a barrinha de ondas, que mexe com o som que entra agora, e o 🎙 ao lado do número do Volume — ele liga o RETORNO: aceso em verde, você se ouve na TV, com o volume e o ganho do cartão já aplicados. Quando um programa de fora está gravando esse microfone, uma linha embaixo dos botões Virtual e Nativo diz qual. No aparelho, a luz do botão de microfone fica acesa com o microfone ligado, pisca quando um programa de fora grava e entra som, e apaga no mudo. Na aba Conexões, em «Gestão de Controles», a linha de cada controle diz por onde o microfone chega.

**Os passos.**

1. Clique na aba Controles.
2. Clique na linha do P1 para abrir o cartão dele.
3. Confira que a pílula do Microfone diz ATIVO e que a luz do botão de microfone do P1 está acesa.
4. Fale perto do P1 e confira que a barrinha de ondas do bloco Microfone mexe, e que ela desce quando você se cala.
5. Clique no 🎙 ao lado do número do Volume do Microfone do P1 e confira que ele ficou verde.
6. Fale perto do P1 e confira que a sua voz sai na TV.
7. Aperte o botão de microfone no plástico do P1 e confira que a sua voz parou de sair na TV.
8. Aperte o botão do P1 de novo, espere a pílula voltar a ATIVO, e apague o 🎙 se ele ainda estiver verde.
9. Abra um programa que ouça microfone — um gravador ou uma chamada de voz — e escolha como entrada a do P1: «Microfone do Controle 1», ou, se ela não estiver na lista, a do DualSense.
10. Fale e confira que o programa te ouve, que a luz do botão do P1 pisca enquanto você fala, e que o cartão do P1 diz que esse programa está te ouvindo.
11. Feche o programa.
12. Clique na linha do P2 e refaça nele a mesma rodada, da pílula ATIVO até fechar o programa, com «Microfone do Controle 2».
13. Clique na aba Conexões, abra «Gestão de Controles» e confira que as linhas do P1 e do P2 dizem «Microfone Ligado, pelo cabo • Placa do controle».

**Passa quando.** No P1 e no P2 a pílula diz ATIVO, a luz está acesa e a barrinha segue a sua voz. Com o 🎙 verde a voz sai na TV, e para quando o botão do plástico cala aquele controle. Um programa de fora te ouve pela entrada daquele controle, com a luz piscando e o cartão dizendo o nome dele. E a aba Conexões diz, nos dois, que o microfone chega pelo cabo, pela placa do controle.

**Por controle.**

* **P1** — No USB, e é o primeiro: pílula e luz, a barrinha, o retorno, o mudo pelo plástico e o programa de fora.
* **P2** — No USB, e faz a mesma rodada inteira. É a segunda prova: se um capta e o outro não, anote qual — o defeito é daquele aparelho, não do caminho.
* **P3** — No BT, e é TESTEMUNHA. Não mexa nele: a pílula do Microfone dele continua como estava do começo ao fim.
* **P4** — No BT, e é a segunda testemunha. Mesma conferência do P3.

**A armadilha.** O 🎙 não cala o microfone: desde 21/09 ele é o retorno, e quem cala é o botão do plástico. Se a dica do «?» do bloco Microfone ainda disser que o 🎙 cala, ela está velha — vale o que o próprio 🎙 diz quando você para o mouse nele. Se o 🎙 recusar com um recado laranja no cartão, o microfone daquele controle está no mudo: aperte o botão do plástico e tente de novo. E ele pode apagar sozinho quando você cala o controle pelo plástico — o retorno fica sem o que ouvir —, e isso não é defeito. Com a TV alta e o retorno ligado o microfone pode ouvir a própria TV e apitar: fale longe dela. Se nada funcionar nos dois do USB, veja na aba Sistema, em «O exame de hoje», a linha que começa com «regra áudio-off»: com essa regra ativa, o microfone e o fone de todo controle no USB ficam desligados de propósito. Não reprove pela palavra «indisponível» de uma lista de aparelhos — o microfone do DualSense já captou marcado assim; reprove pela barrinha e pelo ouvido. O degrau: esta célula está em «saiu no fio»; o retorno e o programa de fora são os dois degraus acima.

---

## mapa-audio.microfone-radio — Microfone — captação do áudio · rádio

*Célula:* `audio.microfone @ rádio`

**O que isto prova.** Prova que o microfone dos dois controles do BT chega ao computador pela ponte do Hefesto, os dois no ar ao mesmo tempo, e que o «Nativo» fica cinza no BT, com a razão escrita.

**Onde olhar.** Na aba Controles, no bloco Microfone do cartão aberto: a pílula ao lado da palavra Microfone, a barrinha de ondas, o 🎙 ao lado do número do Volume (o retorno: aceso em verde, você se ouve na TV), e, embaixo, os botões «Virtual» e «Nativo» — no BT o «Nativo» e o trilho do Ganho ficam cinza, com a razão no «?» ao lado. Quando um programa de fora grava esse microfone, uma linha embaixo dos dois botões diz qual. Na aba Conexões, em «Gestão de Controles», a linha de cada controle diz por onde o microfone chega.

**Os passos.**

1. Clique na aba Controles.
2. Clique na linha do P3 para abrir o cartão dele.
3. Confira que «Virtual» está aceso e «Nativo» está cinza, e leia a frase do «?» ao lado do «Nativo».
4. Confira que a pílula do Microfone diz ATIVO e que a luz do botão de microfone do P3 está acesa.
5. Fale perto do P3 e confira que a barrinha de ondas mexe, e que ela desce quando você se cala.
6. Clique no 🎙 do Microfone do P3 e confira que ele ficou verde.
7. Clique na linha do P4 e clique no 🎙 do Microfone dele também.
8. Fale perto do P3 e depois perto do P4, e confira que a sua voz sai na TV nas duas vezes.
9. Aperte o botão de microfone no plástico do P3 e confira que a pílula do P3 passou a DESLIGADO, a do P4 continuou ATIVO, e você continua se ouvindo na TV pelo P4.
10. Aperte o botão do P3 de novo, espere a pílula voltar a ATIVO, e apague o 🎙 do P3 e o do P4 que ainda estiverem verdes.
11. Abra um programa que ouça microfone e escolha como entrada «Microfone do Controle 3».
12. Fale e confira que o programa te ouve, que a luz do botão do P3 pisca enquanto você fala, e que o cartão do P3 diz que esse programa está te ouvindo.
13. Troque a entrada do programa para «Microfone do Controle 4» e confira o mesmo no P4.
14. Feche o programa.
15. Clique na aba Conexões, abra «Gestão de Controles» e confira que as linhas do P3 e do P4 dizem «Microfone Ligado, pelo rádio • Pela ponte».

**Passa quando.** No P3 e no P4 a pílula diz ATIVO e a barrinha segue a voz; com os dois 🎙 verdes ao mesmo tempo a voz sai na TV pelos dois, e calar um pelo plástico deixa o outro no ar. Um programa de fora te ouve pela entrada de cada um, com a luz piscando e o cartão dizendo o nome dele. O «Nativo» está cinza, com a razão no «?». E a aba Conexões diz que o microfone dos dois chega pelo rádio, pela ponte.

**Por controle.**

* **P1** — No USB, e é TESTEMUNHA. Não mexa nele. A pílula dele fica como estava; a barrinha dele pode mexer quando você fala — o microfone dele também ouve a sala, e isso não reprova.
* **P2** — No USB, e é a segunda testemunha. Mesma conferência do P1.
* **P3** — No BT, e é o primeiro: o «Nativo» cinza, a pílula, a barrinha, o retorno, o mudo pelo plástico e o programa de fora.
* **P4** — No BT, e é a segunda prova — e a que mostra os dois microfones do BT no ar juntos. Se só um dos dois chegar, anote qual.

**A armadilha.** O «Nativo» cinza é o certo: pelo BT o controle não publica microfone próprio, e o som só chega pelo Hefesto. O microfone no BT custa: com ele no ar, o controle troca parte dos turnos de resposta por turnos de som, e os turnos são do adaptador, divididos entre os controles ligados nele — se os botões do P3 e do P4 responderem atrasados com os dois microfones no ar, é o preço, e vale anotar. O 🎙 não cala o microfone: ele é o retorno, e quem cala é o botão do plástico; se ele recusar com um recado laranja, o microfone está no mudo. O degrau: esta célula está em «saiu no fio» pelo BT; o retorno e o programa de fora são os dois degraus acima.

---

## mapa-audio.microfone.mudo-cabo — Microfone — mudo no firmware · cabo

*Célula:* `audio.microfone.mudo @ cabo`

**O que isto prova.** Prova que o botão de microfone de cada controle do USB cala aquele controle, e só ele, no próprio aparelho — e que a luz do botão, a pílula da tela e o som que chega ao computador contam a mesma história.

**Onde olhar.** No aparelho, o botão de microfone é o botãozinho logo abaixo do botão PS, e a luz dele segue a regra desta casa: acesa é microfone ligado, apagada é mudo. Na aba Controles, no bloco Microfone do cartão: a pílula ao lado da palavra Microfone (ATIVO, DESLIGADO ou um travessão), a barrinha de ondas, e o 🎙 ao lado do número do Volume, que liga o retorno — aceso em verde, você se ouve na TV. Com o cartão fechado, a linha de cada controle também mostra a pílula do Microfone.

**Os passos.**

1. Clique na aba Controles.
2. Clique em «Todos», na fita do topo, e anote o que a pílula do Microfone de cada um dos quatro diz — é o ponto de partida.
3. Clique na linha do P1 para abrir o cartão dele.
4. Clique no 🎙 do Microfone do P1 e fale perto dele: a sua voz tem de sair na TV.
5. Aperte uma vez o botão de microfone no plástico do P1.
6. Confira que a luz desse botão apagou e que a pílula do Microfone do P1 passou a DESLIGADO.
7. Fale perto do P1 e confira que a voz parou de sair na TV e que a barrinha de ondas do Microfone ficou parada.
8. Clique em «Todos» e confira que as pílulas do P2, do P3 e do P4 não mudaram.
9. Espere um segundo e aperte o botão do plástico do P1 de novo.
10. Confira que a luz acendeu e que a pílula voltou a ATIVO.
11. Se o 🎙 apagou sozinho durante o mudo, clique nele de novo; fale e confira que a voz voltou a sair na TV.
12. Clique no 🎙 do P1 para apagar o retorno.
13. Clique na linha do P2 e refaça nele a mesma rodada, do 🎙 aceso até apagá-lo.
14. Confira que as quatro pílulas voltaram ao que diziam no começo.

**Passa quando.** No P1 e no P2 cada aperto cala ou devolve AQUELE controle: com o mudo, a luz apaga, a pílula diz DESLIGADO, a barrinha para e a voz some da TV; com o segundo aperto, tudo volta. As pílulas dos outros três não se mexem, e no fim as quatro dizem o que diziam no começo.

**Por controle.**

* **P1** — No USB, e é ELE que você cala primeiro, com o retorno ligado para ouvir o silêncio acontecer.
* **P2** — No USB, e faz a mesma rodada. Antes de apertar, olhe as quatro pílulas: o erro que este teste caça é calar UM e outro emudecer junto, e isso só se enxerga sabendo o de antes.
* **P3** — No BT, e é TESTEMUNHA. Não aperte o botão dele. A pílula dele tem de ficar parada enquanto você cala os do USB.
* **P4** — No BT, e é a segunda testemunha. Se o P3 ficou parado e o P4 mudou, alguma coisa está escrevendo no controle errado.

**A armadilha.** Na tela não há botão de calar o microfone: o 🎙 é o retorno, e o deslizante de Volume também não cala — a luz fica acesa. O mudo é do botão do plástico: é o sistema que, ao ver o aperto, cala o microfone dentro do próprio controle, e o Hefesto lê esse mudo para pintar a pílula e acender ou apagar a luz. Dê um segundo entre um aperto e o seguinte no mesmo controle: apertos mais rápidos são engolidos de propósito. Uma pílula em travessão não é ATIVO nem DESLIGADO — anote e não conte como passa. O 🎙 pode apagar sozinho quando o microfone vai ao mudo — o retorno fica sem o que ouvir —, e é por isso que o passo depois do segundo aperto manda ligá-lo de novo. Se ele recusar com um recado laranja, o microfone ainda está no mudo: aperte o botão do plástico antes. E a prova desta célula parou em «montou»; esta rodada é a do aparelho.

---

## mapa-audio.microfone.mudo-radio — Microfone — mudo no firmware · rádio

*Célula:* `audio.microfone.mudo @ rádio`

**O que isto prova.** Prova que o botão de microfone de cada controle do BT cala aquele controle, e só ele, e mede se esse mudo sobrevive a uma queda e uma volta.

**Onde olhar.** No aparelho: o botão de microfone logo abaixo do botão PS, com a luz acesa no microfone ligado e apagada no mudo; e o botão PS, o redondo do meio, entre os dois analógicos. Na aba Controles, no bloco Microfone do cartão: a pílula ao lado da palavra Microfone (ATIVO, DESLIGADO ou um travessão), a barrinha de ondas e o 🎙 ao lado do número do Volume, que liga o retorno — aceso em verde, você se ouve na TV.

**Os passos.**

1. Clique na aba Controles.
2. Clique em «Todos», na fita do topo, e anote o que a pílula do Microfone de cada um dos quatro diz — é o ponto de partida.
3. Clique na linha do P3 para abrir o cartão dele.
4. Clique no 🎙 do Microfone do P3 e fale perto dele: a sua voz tem de sair na TV.
5. Aperte uma vez o botão de microfone no plástico do P3.
6. Confira que a luz desse botão apagou e que a pílula do Microfone do P3 passou a DESLIGADO.
7. Fale perto do P3 e confira que a voz parou de sair na TV e que a barrinha de ondas ficou parada.
8. Clique em «Todos» e confira que as pílulas do P1, do P2 e do P4 não mudaram.
9. Desligue o P3 segurando o botão PS até TODAS as luzes dele apagarem.
10. Religue o P3 apertando o botão PS e espere a linha dele voltar à aba.
11. Anote o que a pílula do Microfone do P3 diz agora e se a luz do botão de microfone dele está acesa ou apagada — esta é a entrega do teste.
12. Aperte o botão do plástico do P3 até a pílula dizer ATIVO, e apague o 🎙 do P3 se ele ainda estiver verde.
13. Clique na linha do P4 e refaça nele a mesma rodada, do 🎙 aceso até a anotação depois da volta.

**Passa quando.** No P3 e no P4 o aperto cala aquele controle — luz apagada, pílula DESLIGADO, voz fora da TV — e os outros três não se mexem. E a entrega deste teste é o que você anotou depois da queda e da volta: a pílula e a luz de cada um quando ele voltou.

**Por controle.**

* **P1** — No USB, e é TESTEMUNHA. Não aperte o botão dele. A pílula dele fica parada, inclusive durante a queda e a volta do P3.
* **P2** — No USB, e é a segunda testemunha. Se um controle do USB emudecer junto com um do BT, o comando pegou mais de um.
* **P3** — No BT, e é ELE que você cala e depois desliga e religa. A pílula e a luz lidas DEPOIS da volta são a entrega.
* **P4** — No BT, e faz a mesma rodada, inclusive a queda e a volta. Se um voltar calado e o outro não, anote qual.

**A armadilha.** O mudo mora no vínculo com o aparelho, e pelo BT esse vínculo se refaz a cada reconexão: um mudo que se desfaz sozinho na volta é o resultado esperado de hoje, não erro seu — anote a hora e siga. O que reprova de verdade é o aperto não calar nada, ou calar o controle errado. O retorno cai junto com o controle e não volta sozinho; é por isso que o passo depois da volta manda conferir o 🎙. Para desligar, segure o PS até as luzes apagarem de verdade: soltar antes é lido como toque, e o toque abre a Steam — se ela abrir, feche-a e refaça. Dê um segundo entre um aperto e o seguinte no mesmo controle.

---

## mapa-audio.saida_dedicada-cabo — Saída de áudio dedicada · cabo

*Célula:* `audio.saida_dedicada @ cabo`

**O que isto prova.** Prova que cada controle do USB tem uma saída de som PRÓPRIA — uma por controle, com o número certo —, e que o exame do Hefesto conta as placas de som dos dois.

**Onde olhar.** Na aba Sistema, na seção «O exame de hoje»: a linha que começa com «áudio presente», que conta as placas de som dos controles no USB; a que começa com «regra áudio-off», que diz se o microfone e o fone deles estão liberados — as duas são cortadas na tela, então pare o mouse em cima para ler a frase inteira —; e a que começa com «Som do sistema», que diz por onde o som do computador está saindo. Fora do Hefesto, a lista de saídas das configurações de Som do sistema, onde cada controle tem a sua saída «Alto-falante do Controle N», com o número do jogador.

**Os passos.**

1. Clique na aba Sistema.
2. Na seção «O exame de hoje», pare o mouse na linha que começa com «áudio presente» e leia a frase inteira.
3. Confira que ela conta os 2 controles do USB.
4. Pare o mouse na linha que começa com «regra áudio-off» e leia a frase inteira.
5. Clique na aba Controles e confira que o P1 e o P2 estão com «Efeitos do Jogo no Controle, Áudio da TV na TV» aceso.
6. Abra as configurações de Som do sistema e escolha como saída a que começa com «Alto-falante do Controle 1».
7. Toque uma música no computador e confira, com o ouvido, que ela sai pelo P1 e não sai na TV nem no P2.
8. Escolha como saída a que começa com «Alto-falante do Controle 2» e confira que a música passou para o P2, e só para ele.
9. Encoste o ouvido no P3 e depois no P4 e confirme que os dois estão mudos.
10. Clique na aba Sistema e confira que a linha que começa com «Som do sistema» diz, em poucos segundos, que o som sai em «Alto-falante do Controle 2».
11. Devolva a saída do sistema para a TV e confira que a música voltou para ela e que o P1 e o P2 emudeceram.

**Passa quando.** A linha «áudio presente» conta os 2 controles do USB e a da regra de áudio diz que eles estão liberados. Escolhida a saída «Alto-falante do Controle 1», a música sai só no P1; escolhida a do 2, só no P2; a aba Sistema diz para onde o som foi; e, devolvida a saída para a TV, os dois emudecem. O P3 e o P4 ficam mudos.

**Por controle.**

* **P1** — No USB, e é o primeiro a receber a saída do sistema. A música tem de sair nele e em nenhum outro.
* **P2** — No USB, e recebe a saída depois. É ele que prova que o número não está trocado: o «2» tem de tocar no P2, e não no P1.
* **P3** — No BT, e é TESTEMUNHA. Não entra na conta do exame e fica mudo o tempo todo.
* **P4** — No BT, e é a segunda testemunha. Mesma conferência do P3.

**A armadilha.** As frases do exame são cortadas, e no caso da regra de áudio o corte inverte o sentido: o que sobra ao lado do selo se lê como problema, e o «estão liberados» fica escondido — pare sempre o mouse em cima. As duas placas DualSense do USB têm o mesmo nome e não dizem qual é qual: é por isso que existe «Alto-falante do Controle N», e o que este teste mede é o número cair no controle certo. O número do nome só se renova com aquele controle em silêncio: se o «2» tocar no P1 logo depois de os jogadores trocarem de lugar, pare a música, espere uns segundos e escolha a saída de novo antes de reprovar. Deixe o P1 e o P2 no botão de cima: com o do meio, o outro controle também receberia a música mandada ao primeiro, e o teste não diria mais de onde ela veio. Devolva a saída para a TV no fim — se esquecer, o computador continua tocando só no controle. E a prova desta célula parou em «montou», e está marcada como parcial.

---

## mapa-audio.saida_dedicada-radio — Saída de áudio dedicada · rádio

*Célula:* `audio.saida_dedicada @ rádio`

**O que isto prova.** Prova que cada controle do BT também tem uma saída de som PRÓPRIA, criada pelo Hefesto, e que o som mandado a ela sai só naquele controle, pelo fio do BT.

**Onde olhar.** Fora do Hefesto, a lista de saídas das configurações de Som do sistema: cada controle do BT tem ali a sua saída «Alto-falante do Controle N», com o número do jogador, e nenhuma placa DualSense — pelo BT o controle não publica placa de som, e quem leva o som até ele é o Hefesto. Na aba Sistema, em «O exame de hoje», a linha que começa com «Som do sistema» diz por onde o som do computador está saindo. E o ouvido encostado nos nove furinhos da frente do controle.

**Os passos.**

1. Clique na aba Controles.
2. Confira na fita do topo que P3 e P4 dizem BT, e que os dois estão com «Efeitos do Jogo no Controle, Áudio da TV na TV» aceso.
3. Abra as configurações de Som do sistema e confira que há uma saída que começa com «Alto-falante do Controle 3» e outra com «Alto-falante do Controle 4».
4. Escolha como saída a que começa com «Alto-falante do Controle 3».
5. Toque uma música no computador e confira, com o ouvido, que ela sai pelo P3 e não sai na TV nem no P4.
6. Escolha como saída a que começa com «Alto-falante do Controle 4» e confira que a música passou para o P4, e só para ele.
7. Encoste o ouvido no P1 e depois no P2 e confirme que os dois estão mudos.
8. Clique na aba Sistema e confira que a linha que começa com «Som do sistema» diz, em poucos segundos, que o som sai em «Alto-falante do Controle 4».
9. Devolva a saída do sistema para a TV e confira que a música voltou para ela e que o P3 e o P4 emudeceram.

**Passa quando.** A lista de saídas do sistema tem uma saída própria para o P3 e outra para o P4. Escolhida uma delas, a música sai só naquele controle, pelo BT; a aba Sistema diz para onde o som foi; e, devolvida a saída para a TV, os dois emudecem. O P1 e o P2 ficam mudos.

**Por controle.**

* **P1** — No USB, e é TESTEMUNHA. Não mexa nele. Se ele tocar a música mandada ao P3, o som pegou o controle errado.
* **P2** — No USB, e é a segunda testemunha. Mesma conferência do P1.
* **P3** — No BT, e é o primeiro a receber a saída do sistema. A música tem de sair nele e em nenhum outro.
* **P4** — No BT, e recebe a saída depois. É ele que prova que o número não está trocado: o «4» tem de tocar no P4, e não no P3.

**A armadilha.** A página pode chegar com «nada» já marcado nesta célula: é a pré-marca herdada do mapa, que ainda guarda a medição de antes de 10/09, quando pelo BT o som não saía. Troque-a pelo que você ouviu. O número do nome só se renova com aquele controle em silêncio: se o «4» tocar no P3 logo depois de os jogadores trocarem de lugar, pare a música, espere uns segundos e escolha a saída de novo antes de reprovar. Deixe o P3 e o P4 no botão de cima: com o do meio, o outro controle também receberia a música mandada ao primeiro. No BT o começo da música pode demorar um instante enquanto o fio acorda — espere antes de concluir que não saiu. Devolva a saída para a TV no fim; se esquecer, o computador continua tocando só no controle. E ninguém desta casa pode escrever que «descobriu o som pelo BT» a partir de um canal que responde: o que decide é o ouvido, com o som saindo do controle certo e de nenhum outro.

---

# combinacao

---

## mapa-combinacao.adaptador_no_mesmo_controlador-cabo — O adaptador Bluetooth e o cabo no MESMO controlador USB · cabo

*Célula:* `combinacao.adaptador_no_mesmo_controlador @ cabo`

**O que isto prova.** Prova que ter os dois cabos plugados perto do adaptador de rádio — do mesmo lado do gabinete, e talvez no mesmo controlador USB da máquina — não cobra preço dos dois controles que estão no cabo.

**Onde olhar.** Na aba Conexões, em duas seções. A seção «Rádio e Adaptadores» abre clicando no título dela: cada adaptador de rádio é um cartão, o cartão diz em que entrada ele está encaixado (por exemplo «Entrada 4»), e os controles que falam por ele aparecem dentro do cartão — se a lista estiver fechada, a setinha ao lado do nome a abre. No pé dessa seção fica o botão «Examinar Entradas», que refaz o exame e repinta o «Check-up», a primeira seção da aba. No «Check-up», uma das linhas fala de aparelho encaixado colado a um adaptador Bluetooth: com tudo certo ela diz que nenhum está colado; senão, ela conta os pares em portas coladas. Nenhum campo da tela diz em qual controlador USB cada coisa pendura — essa linha mede entradas COLADAS, que é parecido e não é a mesma coisa. Quem responde de verdade este teste são os aparelhos: a barra de luz do P1 e do P2 (as duas tiras acesas dos lados do touchpad) e o tremor deles na sua mão.

**Os passos.**

* Abra a aba Conexões.
1. Clique no título «Rádio e Adaptadores» para abrir a seção.
2. Ache o cartão do adaptador em que o P3 e o P4 aparecem e anote num papel a entrada em que ele está.
3. Clique em «Examinar Entradas», no pé da seção.
4. Leia, no «Check-up», a linha que fala de aparelho colado a um adaptador Bluetooth, e anote a frase inteira.
5. Passe as pontas dos cabos do P1 e do P2 para as entradas mais próximas desse adaptador, sem tirá-las dos controles — se houver duas entradas coladas nele, use essas.
6. Confira na fita do topo que os quatro chips voltaram e que o P1 e o P2 dizem USB.
7. Clique em «Examinar Entradas» de novo e compare a linha do «Check-up» com a frase que você anotou.
8. Na aba Iluminação, clique numa cor bem viva na linha «Cor» da coluna do P1 e numa bem diferente na do P2 — sempre um quadradinho sem X.
9. Veja as duas barras de luz acenderem na cor escolhida, na hora do clique.
10. Na aba Vibração, segure o P1 e o P2, um em cada mão, clique em «Testar» na coluna do P1 e depois na do P2 — que encerra o do P1 —, e termine no «Parar» da coluna do P2.
11. Confira que os dois tremeram na sua mão.
12. De volta à aba Iluminação, clique em cores novas nas colunas do P1 e do P2, alternando, dez vezes seguidas, o mais rápido que você conseguir.
13. Anote todo clique que não acendeu e toda cor que demorou a chegar.
14. Passe as pontas dos dois cabos para as entradas do outro lado do gabinete, o mais longe do adaptador que der.
15. Refaça os passos 6 a 13 com os cabos na posição nova.
16. Compare no papel as duas rodadas, lado a lado: cabos perto do adaptador e cabos longe dele.

**Passa quando.** Nas duas posições dos cabos, o P1 e o P2 obedeceram do mesmo jeito: cada cor acendeu na hora do clique, nenhum clique da rajada foi engolido, e os dois tremeram no «Testar». Se eles falharam com os cabos perto do adaptador e pararam de falhar com os cabos longe, o teste não reprovou o produto — ele achou o preço da posição, e esse achado vale mais que o verde.

**Por controle.**

* **P1** — No cabo, e é um dos dois que têm de responder. Pinte a barra de luz dele nas duas posições de cabo e sinta o «Testar» na mão. Ele é a vítima possível deste lado: se alguma cor não chegou, anote a posição do cabo dele.
* **P2** — No cabo, o outro que tem de responder. Mesmos gestos do P1, com uma cor bem diferente da dele para você não confundir as duas barras. Se só um dos dois falhar, anote qual — pode ser a entrada, e não o lado.
* **P3** — No rádio, e é testemunha e carga ao mesmo tempo. Não toque nele: ele fica ligado do começo ao fim, ocupando o adaptador enquanto os dois do cabo são medidos. Se a barra dele acender junto com a do P1, o comando pegou mais gente do que devia.
* **P4** — No rádio, a segunda testemunha. Não toque nele. Ele e o P3 juntos são o que faz este teste ser sobre companhia: sem os dois no ar, os dois do cabo estariam sozinhos e o teste não mediria nada.

**A armadilha.** Três coisas fazem você julgar errado aqui. A primeira é a palavra do mapa: nesta linha está escrito que o dano NÃO foi acionado, e isso não quer dizer que a topologia não exista — ela existe e foi medida, o adaptador de rádio e os dois cabos penduram no mesmo controlador da máquina. É justamente esse arranjo o suspeito do defeito antigo em que um controle do cabo matava a saída do controle do rádio. A segunda é o «Check-up»: a linha do aparelho colado olha entradas COLADAS uma na outra, e verde ali não diz que as coisas não dividem o mesmo controlador — a tela não tem campo que diga isso, e não adianta procurar. A terceira é o tamanho da carga: a única medição que existe carregou o controlador com CAPTURA DE MICROFONE, não com o vaivém de comandos de um jogo a plena carga; verde sob carga leve não é verde sempre. E a prova desta linha parou no fio: ninguém mediu com o adaptador mudado de lugar, e ninguém mediu com os comandos a plena carga. Duas coisas miúdas: enquanto um cabo está fora da entrada, os controles que vêm depois dele sobem um número, e cada um recupera o seu quando ele volta — é a ordem de conexão, não defeito; e um quadradinho de cor com X é a cor de outro controle, que não aceita o clique. Por último: se o cartão disser que o adaptador é de dentro da máquina, ele não sai do lugar, e este teste roda só mexendo nos cabos.

---

## mapa-combinacao.adaptador_no_mesmo_controlador-radio — O adaptador Bluetooth e o cabo no MESMO controlador USB · rádio

*Célula:* `combinacao.adaptador_no_mesmo_controlador @ rádio`

**O que isto prova.** Prova que os dois controles do rádio continuam obedecendo mesmo com os dois cabos trabalhando ao lado, e diz se mudar o adaptador de lugar muda a resposta.

**Onde olhar.** Na aba Conexões, seção «Rádio e Adaptadores», que abre clicando no título: cada adaptador é um cartão que diz em que entrada ele está encaixado (por exemplo «Entrada 4»), e os controles que falam por ele aparecem DENTRO do cartão — é assim que você sabe por qual adaptador o P3 e o P4 estão falando. Se a lista de um cartão estiver fechada, a setinha ao lado do nome a abre. No pé da seção fica o botão «Examinar Entradas», que refaz o exame e repinta o «Check-up», no alto da aba, onde uma linha fala de aparelho encaixado colado a um adaptador Bluetooth. Quem responde este teste são os aparelhos: as barras de luz do P3 e do P4 e o tremor deles na sua mão.

**Os passos.**

* Abra a aba Conexões.
1. Clique no título «Rádio e Adaptadores» para abrir a seção.
2. Anote num papel, cartão por cartão, a entrada de cada adaptador e quais controles aparecem dentro dele.
3. Confira na fita do topo que o P3 e o P4 dizem BT.
4. Clique em «Examinar Entradas» e anote a linha do «Check-up» que fala de aparelho colado a um adaptador Bluetooth.
5. Encaixe as pontas dos cabos do P1 e do P2 nas entradas mais próximas do adaptador do P3 e do P4.
6. Na aba Iluminação, clique numa cor bem viva na coluna do P3 e numa bem diferente na do P4 — sempre um quadradinho sem X.
7. Veja a barra de luz de cada um acender na cor clicada, no ato do clique.
8. Clique em cores novas nas colunas do P1 e do P2, alternando, quinze vezes seguidas, o mais rápido que você conseguir — é isto que põe o lado do cabo para trabalhar.
9. Sem parar o ritmo, clique numa cor nova na coluna do P3 e noutra na do P4.
10. Anote toda cor do P3 ou do P4 que demorou a chegar, ou que não chegou.
11. Na aba Vibração, com cada um na mão, clique em «Testar» na coluna do P3 e depois na do P4 — que encerra o do P3 —, e termine no «Parar» da coluna do P4.
12. Desencaixe o adaptador do P3 e do P4, encaixe-o numa entrada do outro lado do gabinete e traga os dois de volta com um toque curto no PS de cada um.
13. Na aba Conexões, confira que o cartão desse adaptador passou a dizer a entrada nova e que o P3 e o P4 voltaram para dentro dele.
14. Refaça os passos 6 a 11 com o adaptador na entrada nova.
15. Escreva as duas rodadas lado a lado.

**Passa quando.** Nas duas posições do adaptador, o P3 e o P4 obedeceram: cada cor acendeu na hora do clique, mesmo com o P1 e o P2 sendo pintados sem parar, e os dois tremeram no «Testar». Se eles falharam com o adaptador do lado dos cabos e pararam de falhar com ele do outro lado, isso é ACHADO — é exatamente a medição que ninguém nunca fez nesta casa, e ela vale mais que um verde.

**Por controle.**

* **P1** — No cabo, e aqui ele não é o medido: ele é a CARGA. Não olhe a barra dele para julgar. O papel dele é receber quinze cores em sequência enquanto você olha os dois do rádio.
* **P2** — No cabo, a segunda metade da carga. Mesmo papel do P1: recebe cor atrás de cor. Os dois juntos são o que faz o controlador da máquina trabalhar, que é o mecanismo suspeito.
* **P3** — No rádio, e é a vítima possível — é ele que este lado do teste mede. A cor tem de acender no ato e o tremor tem de vir, com os dois do cabo em rajada ao lado. Se falhar, anote em qual posição do adaptador foi.
* **P4** — No rádio, a segunda vítima possível. Mesmos gestos do P3, com cor bem diferente. Se um dos dois do rádio falhar e o outro não, anote qual — a diferença entre os dois aparelhos do mesmo lado já apareceu em medição antes, e é dado, não ruído.

**A armadilha.** A pergunta é a COMPARAÇÃO de duas posições do adaptador, então a rodada dos passos 6 a 11 é feita duas vezes, uma de cada lado do gabinete; cortar uma delas apaga a pergunta inteira. Desencaixar o adaptador DERRUBA o P3 e o P4 — isso é o esperado, não é o defeito; enquanto eles estão fora os números se reorganizam, e cada um recupera o seu quando volta. Se o P3 ou o P4 voltarem para dentro do cartão de OUTRO adaptador, você mediu a entrada errada: anote e refaça com os dois no mesmo cartão. A Steam tem de continuar fechada quando os dois voltam: um controle que se conecta pelo rádio com a Steam aberta volta com a barra apagada, fechar a Steam depois não cura, e o que cura é reconectar — o botão «A luz não acende», na linha dele na «Gestão de Controles», faz isso. Se o cartão disser que o adaptador é de dentro da máquina, ele não sai do lugar, e este teste roda só mudando os cabos de entrada. O que está escrito no mapa desta linha é que o dano NÃO foi acionado, o que é diferente de «isto não existe»: a topologia existe e foi medida, o adaptador e os dois cabos penduram no mesmo controlador da máquina. A única carga que já se experimentou foi captura de microfone, não o vaivém de comandos de um jogo, e a prova parou no fio: nada nesta linha diz o que o jogo recebeu. Por fim, a linha do «Check-up» mede entradas COLADAS, e não controlador compartilhado — verde nela não fecha esta pergunta, e é por isso que ela é anotada como contexto e não como veredito.

---

## mapa-combinacao.cabo_e_radio.entrada-cabo — Dois na mesa (um no cabo, um no rádio) — a ENTRADA de cada um continua chegando? · cabo

*Célula:* `combinacao.cabo_e_radio.entrada @ cabo`

**O que isto prova.** Prova que tudo o que você faz nos dois controles do cabo continua chegando na tela mesmo com dois controles no rádio ligados ao lado.

**Onde olhar.** Na aba Controles, no quadro «Dispositivos conectados». Cada controle tem uma linha; clicar numa linha abre o cartão daquele controle e fecha os outros, e o chip «Todos» da fita do topo abre os quatro de uma vez. Dentro do cartão ficam: o quadro «Touchpad», que mostra um ponto onde o seu dedo está e, no canto, quantos dedos estão nele («1 toque»); os dois analógicos desenhados, cada um com um pontinho que anda quando você mexe no do aparelho; os desenhos dos botões, que acendem quando você aperta; e as molduras «Giroscópio» e «Acelerômetro», com os três eixos em números que mudam quando você mexe o controle no ar.

**Os passos.**

* Abra a aba Controles.
1. Confira na fita do topo que há quatro chips e que o P1 e o P2 dizem USB.
2. Clique na linha do P1 para abrir o cartão dele.
3. Empurre os dois analógicos do P1 até o fim para cada lado e solte-os.
4. Veja os dois pontinhos andarem junto com os analógicos e voltarem ao centro quando você solta.
5. Aperte, um de cada vez, o Triângulo, o Círculo, o Quadrado, a Cruz e as quatro direções do direcional do P1.
6. Veja cada desenho acender no aperto.
7. Arraste o dedo devagar pelo touchpad do P1.
8. Veja o ponto seguir o dedo, e o canto do quadro «Touchpad» dizer «1 toque».
9. Gire e incline o P1 na mão.
10. Veja mexerem os três números do «Giroscópio» e os três do «Acelerômetro».
11. Clique na linha do P2 e repita nele os passos 3 a 10.
12. Clique na linha do P1 para deixar aberto só o cartão dele.
13. Ponha o P1 numa mão e o P3 na outra e mexa os dois analógicos esquerdos ao mesmo tempo, em círculos, sem parar, contando até vinte.
14. Veja o cartão do P1 enquanto faz isso: o pontinho não pode travar, parar nem saltar.
15. Solte os dois controles e confira que o pontinho do P1 volta ao centro.
16. Clique na linha do P2 e refaça essa dupla com o P2 numa mão e o P4 na outra.
17. Escreva a resposta do P1 e a do P2, uma embaixo da outra.

**Passa quando.** Com os quatro controles ligados, tudo o que você fez no P1 e no P2 apareceu no cartão de cada um: o pontinho de cada analógico andou e voltou ao centro, cada botão apertado acendeu, o ponto do touchpad seguiu o dedo, e os números dos dois sensores mexeram. E nada disso travou nem atrasou enquanto um controle do rádio era mexido junto, com uma mão em cada.

**Por controle.**

* **P1** — No cabo, e é um dos dois que têm de responder. Faça nele a volta inteira: os dois analógicos, os quatro botões da face, as quatro direções do direcional, o touchpad, o giroscópio e o acelerômetro.
* **P2** — No cabo, o outro que tem de responder. Mesma volta inteira. Se um dos dois responder e o outro não, anote qual — e confira se o cabo dele está bem encaixado nas duas pontas antes de reprovar.
* **P3** — No rádio, e é testemunha e carga. Fica ligado o tempo todo, e na segunda metade você o mexe junto com o P1 — não para medir o P3, mas para ocupar o rádio enquanto o cabo é lido.
* **P4** — No rádio, a segunda testemunha. Fica ligado, e entra na segunda metade junto com o P2. Se o cartão do P2 engasgar só quando você mexe no P4, anote isso: é o rádio atrapalhando o cabo, que é justamente o que esta linha existe para pegar.

**A armadilha.** A medição que existe foi feita com os quatro PARADOS na mesa, ninguém apertou nada — o que este teste faz, que é apertar e mexer com companhia, nunca foi medido, então tudo o que você achar aqui é notícia nova. A prova desta linha parou no fio: ver o número mexer no cartão não diz que o JOGO recebeu. Os cartões são um de cada vez — clicar num fecha o outro; o chip «Todos» abre os quatro. Não clique nos botões «Giroscópio» e «Acelerômetro» do alto do cartão: eles ligam e desligam o que o jogo recebe daquele sensor, e um clique sem querer muda a configuração do controle no meio do teste. E este teste é longo de propósito: ele varre as seis famílias de entrada — os dois analógicos, os quatro botões da face, as quatro direções do direcional, o touchpad, o giroscópio e o acelerômetro — em DOIS controles do cabo, e ainda mede os dois sob a carga do rádio. Cada família é um ato separado com a olhada colada nela; juntá-las numa bolinha só é o que faz alguém varrer tudo de uma vez e não saber depois QUAL delas falhou.

---

## mapa-combinacao.cabo_e_radio.entrada-radio — Dois na mesa (um no cabo, um no rádio) — a ENTRADA de cada um continua chegando? · rádio

*Célula:* `combinacao.cabo_e_radio.entrada @ rádio`

**O que isto prova.** Prova que tudo o que você faz nos dois controles do rádio continua chegando na tela mesmo com dois controles no cabo trabalhando ao lado.

**Onde olhar.** Na aba Controles, no quadro «Dispositivos conectados». Cada controle tem uma linha; clicar numa linha abre o cartão daquele controle e fecha os outros, e o chip «Todos» da fita do topo abre os quatro de uma vez. Dentro do cartão: o quadro «Touchpad», com o ponto do dedo e, no canto, quantos dedos estão nele («1 toque»); os dois analógicos desenhados, cada um com um pontinho que anda; os desenhos dos botões, que acendem ao aperto; e as molduras «Giroscópio» e «Acelerômetro», com os três eixos em números.

**Os passos.**

* Abra a aba Controles.
1. Confira na fita do topo que há quatro chips e que o P3 e o P4 dizem BT.
2. Clique na linha do P3 para abrir o cartão dele.
3. Mexa os dois analógicos do P3 até o fim para cada lado e solte-os.
4. Veja os dois pontinhos andarem junto com os analógicos e voltarem ao centro quando você solta.
5. Aperte, um de cada vez, o Triângulo, o Círculo, o Quadrado, a Cruz e as quatro direções do direcional do P3.
6. Veja cada desenho acender no aperto.
7. Arraste o dedo devagar pelo touchpad do P3.
8. Veja o ponto seguir o dedo, e o canto do quadro «Touchpad» dizer «1 toque».
9. Gire e incline o P3 na mão.
10. Veja mexerem os três números do «Giroscópio» e os três do «Acelerômetro».
11. Clique na linha do P4 e repita nele os passos 3 a 10.
12. Clique na linha do P3, ponha o P3 numa mão e o P1 na outra e gire os dois analógicos esquerdos em círculos, sem parar, contando até vinte.
13. Veja o pontinho do P3: ele não pode travar, parar nem saltar enquanto o controle do cabo é mexido junto.
14. Solte os dois controles e confira que os pontinhos do P3 voltam ao centro.
15. Clique na linha do P4 e repita essa volta de vinte com o P4 numa mão e o P2 na outra.
16. Escreva a resposta do P3 e a do P4, uma embaixo da outra.

**Passa quando.** Com os quatro ligados, tudo o que você fez no P3 e no P4 apareceu no cartão de cada um: o pontinho de cada analógico andou e voltou ao centro, cada botão acendeu, o ponto do touchpad seguiu o dedo, e os números dos dois sensores mexeram. E nada travou nem atrasou enquanto um controle do cabo era mexido junto.

**Por controle.**

* **P1** — No cabo, e aqui ele é testemunha e carga. Não o meça: ele fica ligado e, na volta de vinte, é mexido junto com o P3 só para ocupar o cabo enquanto o rádio é lido.
* **P2** — No cabo, a segunda testemunha. Fica ligado, e entra na volta de vinte junto com o P4. Se o cartão do P4 só engasgar quando você mexe no P2, anote — é o cabo atrapalhando o rádio, e é o defeito que esta família nasceu para pegar.
* **P3** — No rádio, e é um dos dois que têm de responder. Faça nele a volta inteira, as seis famílias de entrada, e depois a volta de vinte com o P1.
* **P4** — No rádio, o outro que tem de responder. Mesma volta inteira. Se ele mostrar analógico e botões mas não mostrar giroscópio nem touchpad, anote a hora: isso é achado, não um controle que ainda não acordou.

**A armadilha.** O silêncio que parece espera é o defeito. Pelo rádio o DualSense nasce num modo que não manda movimento nem touchpad, mas quem o tira desse modo é o próprio sistema, no instante em que reconhece o controle — antes de o Hefesto ler o primeiro quadro. Então um cartão do rádio com analógico e botões e sem giroscópio e touchpad NÃO é um controle «ainda dormindo», e não há cor a pintar para acordá-lo: anote qual e a hora. Segunda: a medição que existe foi feita com os quatro PARADOS na mesa, ninguém apertou nada — apertar e mexer com companhia é exatamente a metade que continua aberta, então o que você achar aqui é notícia nova. Terceira: a prova parou no fio; ver o número mexer no cartão não diz que o JOGO recebeu. Quarta: pelo rádio, um quadro que chega errado é jogado fora inteiro e não vira evento nenhum — quando um aperto some, ele some em silêncio, sem aviso na tela, e é assim mesmo que este defeito se apresenta. E não clique nos botões «Giroscópio» e «Acelerômetro» do alto do cartão: eles ligam e desligam o que o jogo recebe daquele sensor. Este teste é longo de propósito: ele varre as seis famílias de entrada em DOIS controles, e ainda mede os dois sob carga; cortar qualquer uma delas deixaria de fora justamente a família que poderia estar falhando.

---

## mapa-combinacao.cabo_e_radio.saida-cabo — Dois na mesa (um no cabo, um no rádio) — a SAÍDA de cada um sobrevive? · cabo

*Célula:* `combinacao.cabo_e_radio.saida @ cabo`

**O que isto prova.** Prova que os comandos que o Hefesto manda para os dois controles do cabo chegam mesmo quando ele está mandando comando para os dois do rádio ao mesmo tempo.

**Onde olhar.** Nos aparelhos, e não na tela: a barra de luz do P1 e do P2 — as duas tiras acesas dos lados do touchpad — e o tremor deles na sua mão. Na tela, os gestos ficam na aba Iluminação (cada controle tem uma coluna; a linha «Cor» tem os quadradinhos de cor, e um quadradinho com X é a cor de outro controle e não aceita clique) e na aba Vibração (cada controle tem uma coluna, com a linha «Testar agora» e os botões «Testar» e «Parar»). A tela mostra a cor que o Hefesto PEDIU; quem responde é a faixa acesa no plástico. Tenha papel e caneta à mão: o resultado deste teste é a lista dos cliques que não acenderam.

**Os passos.**

1. Abra a aba Iluminação.
2. Confira na fita do topo que há quatro chips: P1 e P2 dizendo USB, P3 e P4 dizendo BT.
3. Anote num papel a cor da barra de luz de cada um dos quatro aparelhos.
4. Clique numa cor bem viva na linha «Cor» de cada uma das quatro colunas, uma coluna de cada vez, uma cor diferente em cada.
5. Confira, a cada clique, que a barra daquele controle acendeu na cor escolhida.
6. Veja os quatro juntos: quatro barras acesas, quatro cores diferentes, ao mesmo tempo.
7. Clique em cores novas nas quatro colunas, uma atrás da outra, o mais rápido que der, e repita a volta três vezes.
8. Repare nas barras do P1 e do P2 durante essa rajada e anote todo clique que não acendeu.
9. Abra a aba Vibração.
10. Segure o P1 na mão e clique em «Testar» na coluna dele.
11. Segure o P2 na outra mão e clique em «Testar» na coluna dele: o P2 começa a tremer e o P1 para, porque o Hefesto testa um controle por vez.
12. Com o P1 e o P2 na mão, clique em «Testar» nas quatro colunas, uma atrás da outra, o mais rápido que der, com o P3 e o P4 largados na mesa para o rádio trabalhar junto.
13. Clique em «Parar» na coluna do último controle que tremeu.
14. Anote se algum comando do P1 ou do P2 não chegou, e o que estava acontecendo no rádio naquele instante.

**Passa quando.** O P1 e o P2 — os dois do cabo — obedeceram a todos os comandos, com o P3 e o P4 recebendo comando ao mesmo tempo: cada cor acendeu no ato, nenhum clique da rajada foi engolido, e os dois tremeram no «Testar», cada um na sua vez, inclusive na volta dos quatro em sequência. Se um comando do P1 ou do P2 não chegou, o achado é esse, e anote qual comando era e o que o rádio estava fazendo na hora.

**Por controle.**

* **P1** — No cabo, e é uma das duas vítimas possíveis deste lado. Recebe cor própria, entra na rajada e treme no «Testar», com você segurando-o na mão.
* **P2** — No cabo, a outra vítima possível. Mesmos comandos, com uma cor bem diferente da do P1 para as duas barras não se confundirem. Se só um dos dois falhar, anote qual e em que entrada ele está.
* **P3** — No rádio, e aqui ele é carga: recebe cor na rajada e recebe «Testar» para o rádio estar trabalhando enquanto o cabo é medido. Deixe-o na mesa; você não precisa senti-lo.
* **P4** — No rádio, a segunda carga. Mesmo papel do P3. Os dois no ar recebendo comando é o que faz este teste ser sobre companhia — sem eles, o P1 e o P2 estariam sozinhos e nada seria medido.

**A armadilha.** O «Testar» fica ligado até o «Parar», e o Hefesto testa um controle por vez: o «Testar» de outra coluna encerra o da anterior, então cada controle treme só na vez dele. Segure na mão os dois que você está medindo, e termine no «Parar» — sem ele o último continua tremendo e a vibração não volta ao jogo. Este teste é com os QUATRO ligados: a peça do Hefesto que divide o esforço entre os controles muda de conta conforme quantos estão ligados, então uma rodada com três não se compara com uma rodada com quatro. A Steam fica fechada durante a bancada, e o motivo não é ela escrever na luz — medido, quem escreve somos nós; o que ela faz é pegar o controle do RÁDIO que se conecta com ela aberta, e aí a barra dele fica apagada. No cabo isso não acontece. E lembre de onde este teste vem: o defeito antigo era um controle NO CABO matando a saída do controle NO RÁDIO — a vítima esperada é a do outro lado. Verde aqui é o resultado previsto e não fecha a pergunta; quem fecha é a rodada do rádio. Por último, a tela mostra a cor que o Hefesto pediu, não a que acendeu: julgue pela faixa acesa no plástico, sempre.

---

## mapa-combinacao.cabo_e_radio.saida-radio — Dois na mesa (um no cabo, um no rádio) — a SAÍDA de cada um sobrevive? · rádio

*Célula:* `combinacao.cabo_e_radio.saida @ rádio`

**O que isto prova.** Prova que os comandos do Hefesto chegam aos dois controles do rádio mesmo quando ele está mandando comando para os dois do cabo ao mesmo tempo — que é exatamente onde o defeito antigo aparecia.

**Onde olhar.** Nos aparelhos: a barra de luz do P3 e do P4 — as duas tiras acesas dos lados do touchpad — e o tremor deles na sua mão. Na tela, os gestos ficam na aba Iluminação (uma coluna por controle; a linha «Cor» tem os quadradinhos de cor, e um quadradinho com X é a cor de outro controle e não aceita clique) e na aba Vibração (uma coluna por controle, com a linha «Testar agora» e os botões «Testar» e «Parar»). A tela mostra a cor PEDIDA; quem responde é a faixa acesa no plástico.

**Os passos.**

1. Abra a aba Iluminação.
2. Confira na fita do topo que há quatro chips: P1 e P2 dizendo USB, P3 e P4 dizendo BT.
3. Anote num papel a cor da barra de luz de cada um dos quatro, antes de mexer em qualquer coisa.
4. Clique numa cor diferente em cada uma das quatro colunas, começando pela do P3 e pela do P4.
5. Veja cada barra acender na cor clicada, no ato do clique.
6. Veja os quatro juntos: quatro barras acesas, quatro cores diferentes, ao mesmo tempo.
7. Clique em cores novas nas quatro colunas, uma atrás da outra, o mais rápido que der, e repita a volta três vezes.
8. Veja as barras do P3 e do P4 durante essa rajada e anote todo clique que não acendeu, e toda cor que chegou atrasada.
9. Comece uma rajada só nas colunas do P1 e do P2, sem parar, contando até quinze.
10. Sem parar a rajada, clique numa cor nova na coluna do P3 e noutra na do P4.
11. Anote toda cor do P3 ou do P4 que não chegou, ou que chegou atrasada.
12. Na aba Vibração, com o P3 e o P4 na mão, clique em «Testar» na coluna do P3 e depois na do P4: o P3 para quando o P4 começa, porque o Hefesto testa um controle por vez.
13. Com os dois ainda na mão, clique em «Testar» nas quatro colunas, uma atrás da outra, o mais rápido que der.
14. Clique em «Parar» na coluna do último controle que tremeu.
15. Anote se o P3 e o P4 tremeram na vez de cada um, nas duas voltas.

**Passa quando.** O P3 e o P4 — os dois do rádio — obedeceram a todos os comandos, inclusive durante a rajada em que o P1 e o P2 estavam sendo pintados sem parar: cada cor acendeu no ato, e os dois tremeram no «Testar», nas duas voltas. Se uma cor do P3 ou do P4 sumiu, ou se o tremor não veio, o achado é esse — anote se aconteceu com o cabo em rajada ou com o cabo parado, porque essa é a diferença que interessa.

**Por controle.**

* **P1** — No cabo, e aqui ele é a CARGA. Não o meça. O papel dele é receber cor atrás de cor durante a rajada, para o cabo estar ocupado enquanto o rádio é medido.
* **P2** — No cabo, a segunda metade da carga. Mesmo papel do P1. Os dois juntos é que reproduzem a situação em que o defeito antigo apareceu.
* **P3** — No rádio, e é a vítima principal deste teste — foi um controle no rádio que ficou mudo, no defeito antigo. Cor no ato, tremor no «Testar», com o cabo em rajada ao lado.
* **P4** — No rádio, a segunda vítima possível. Mesmos comandos, cor bem diferente. Se um dos dois do rádio falhar e o outro não, anote qual: dois aparelhos do mesmo lado já foram medidos respondendo bem diferente um do outro, e isso é dado, não ruído.

**A armadilha.** Se a barra do P3 ou do P4 não acende em cor NENHUMA desde o primeiro clique, a causa conhecida não é este teste: é a Steam ter sido aberta antes de aquele controle se conectar pelo rádio. Fechar a Steam depois não cura — o que cura é reconectar, e o botão «A luz não acende», na linha dele na aba Conexões, faz exatamente isso; reconecte, e só então comece. O «Testar» fica ligado até o «Parar», e o de outra coluna encerra o da anterior: cada controle treme só na vez dele. Segure na mão o controle que está sendo medido, e termine no «Parar», senão o último continua tremendo e a vibração não volta ao jogo. Faça este teste com os QUATRO ligados: a peça do Hefesto que divide o esforço entre os controles muda de conta conforme quantos estão ligados, e uma rodada com três não se compara com uma com quatro. Não julgue pela tela: ela mostra a cor que o Hefesto pediu, não a que acendeu no plástico. E saiba o peso do que você está fazendo: este é o lado do defeito de origem desta família — vermelho aqui é o achado mais valioso deste roteiro, e vale anotar a hora exata e o que estava acontecendo no cabo naquele instante.

---

## mapa-combinacao.cabo_e_radio.taxa-cabo — Dois na mesa (um no cabo, um no rádio) — a TAXA de relatórios de cada um, medida junta · cabo

*Célula:* `combinacao.cabo_e_radio.taxa @ cabo`

**O que isto prova.** Prova que a leitura dos dois controles do cabo continua chegando de forma lisa, sem engasgo, com dois controles no rádio ligados e sendo mexidos ao lado.

**Onde olhar.** Na aba Controles, dentro do cartão de cada controle. Duas coisas: os três números da moldura «Giroscópio», que mudam quando você gira o controle no ar, e o pontinho de cada analógico, que anda quando você mexe. No alto do cartão aberto, ao lado do nome, pode aparecer uma linha discreta que começa com «Giroscópio:» e traz um número por segundo — algo como «Giroscópio: fluindo para o jogo (~250 Hz)». Ela só aparece no cartão do controle cujo movimento está sendo entregue ao jogo; nos outros cartões ela simplesmente não existe, e isso não é defeito. Quantas leituras um controle do CABO entrega no fio não aparece em campo nenhum do produto: a contagem por segundo que existe, na seção «Rádio e Adaptadores» da aba Conexões, mostra só os controles do rádio.

**Os passos.**

* Abra a aba Controles.
1. Confira na fita do topo que há quatro chips e que o P1 e o P2 dizem USB.
2. Clique na linha do P1 para abrir o cartão dele.
3. Leia no alto do cartão a linha que começa com «Giroscópio:»: se ela trouxer um número, anote o número; se ela não aparecer, escreva «não apareceu».
4. Gire o P1 na mão devagar, para um lado e para o outro, contando até vinte.
5. Veja os três números do «Giroscópio» durante esse tempo: eles têm de mudar de forma corrida, sem travar e sem pular.
6. Pare de girar e confira que os números voltam a ficar quase parados.
7. Empurre o analógico esquerdo do P1 em círculos, contando até vinte, e veja o pontinho fazer o mesmo círculo, sem saltar.
8. Clique na linha do P2 e refaça nele os passos 3 a 7.
9. Clique na linha do P1 para abrir o cartão dele de novo.
10. Gire o P1 numa mão e o P3 na outra ao mesmo tempo, sem parar, contando até trinta.
11. Veja os números do «Giroscópio» do P1 durante esse tempo e anote todo engasgo, toda parada e todo salto.
12. Clique na linha do P2 e refaça os passos 10 e 11 com o P2 numa mão e o P4 na outra.
13. Escreva a resposta dos dois do cabo, uma embaixo da outra: engasgou ou não engasgou.

**Passa quando.** O P1 e o P2 mostraram os números do giroscópio e o pontinho do analógico mudando de forma lisa e corrida, sem engasgo e sem salto — com os quatro controles ligados e com um controle do rádio sendo girado junto na outra mão. E, se a linha «Giroscópio:» trouxer um número, ele é parecido nos dois do cabo.

**Por controle.**

* **P1** — No cabo, e é um dos dois medidos. Gire-o e mexa o analógico dele, e depois gire-o junto com o P3, um em cada mão. É a lisura da leitura dele que responde este teste.
* **P2** — No cabo, o outro medido. Mesmos gestos, e depois em par com o P4. Se um dos dois engasgar e o outro não, anote qual e em que entrada ele está plugado.
* **P3** — No rádio, e é carga: entra na segunda metade, girado junto com o P1, só para o rádio estar ocupado enquanto o cabo é lido. Não meça o cartão dele aqui.
* **P4** — No rádio, a segunda carga. Entra girado junto com o P2. Se o P2 só engasgar quando o P4 se mexe, anote — é o rádio atrapalhando o cabo, e é o que esta família procura.

**A armadilha.** O número da linha «Giroscópio:» é o TETO DO PRODUTO, não uma medição do cabo. O Hefesto limita em 250 leituras por segundo o que ele repassa ao jogo, então ler «~250» diz que o limitador está funcionando, e não que o cabo entrega 250. O que se mediu no fio — 250 cravados, iguais nos quatro aparelhos, sem se mover — não aparece em campo nenhum desta tela para os controles do cabo, e não adianta procurar. Segunda: a linha «Giroscópio:» só nasce no cartão do controle cujo movimento está indo para o jogo; em Modo Nativo e com a máscara de Xbox ela diz outra coisa, e nenhum dos três casos é defeito. Terceira, e é a que mais engana: o olho é uma régua ruim para velocidade de leitura — a diferença entre 250 e 400 por segundo você não enxerga. O que o olho enxerga é ENGASGO, e é só isso que este teste pede que você anote. Não clique nos botões «Giroscópio» e «Acelerômetro» do alto do cartão: eles ligam e desligam o que o jogo recebe daquele sensor. E a prova desta linha parou no fio: nada aqui diz o que o jogo recebeu.

---

## mapa-combinacao.cabo_e_radio.taxa-radio — Dois na mesa (um no cabo, um no rádio) — a TAXA de relatórios de cada um, medida junta · rádio

*Célula:* `combinacao.cabo_e_radio.taxa @ rádio`

**O que isto prova.** Prova se a leitura dos dois controles do rádio chega de forma lisa com dois controles no cabo ao lado — e se os dois do rádio se comportam igual entre si.

**Onde olhar.** Em dois lugares. Na aba Conexões, seção «Rádio e Adaptadores» (abre clicando no título): cada controle do rádio aparece dentro do cartão do adaptador dele, e na linha do controle há um número em Hz ao lado de um ícone de sinal — passe o mouse e a dica diz «Movimento por segundo». Ele conta os quadros que chegam AGORA do controle, um por relatório, parado ou não; é o campo mais perto da taxa que o controle entrega pelo rádio, e quando o número cai muito ele muda de cor. Se a lista de um cartão estiver fechada, a setinha ao lado do nome a abre. E na aba Controles, dentro do cartão de cada controle: os três números da moldura «Giroscópio» e o pontinho de cada analógico, e, no alto do cartão aberto, a linha discreta que começa com «Giroscópio:» — ela só existe no cartão do controle cujo movimento está indo para o jogo, e nos outros não, o que não é defeito.

**Os passos.**

* Abra a aba Conexões.
1. Clique no título «Rádio e Adaptadores» e ache o P3 e o P4 dentro do cartão do adaptador deles.
2. Com os dois parados na mesa, olhe o número em Hz de cada um por meio minuto e anote o menor e o maior que cada um mostrou.
3. Anote se algum dos dois números mudou de cor.
4. Na aba Controles, confira na fita do topo que há quatro chips e que o P3 e o P4 dizem BT.
5. Clique na linha do P3 para abrir o cartão dele.
6. Leia no alto do cartão a linha que começa com «Giroscópio:» e anote o que ela diz, com número ou sem.
7. Gire o P3 na mão devagar, para um lado e para o outro, contando até vinte, e veja os três números do «Giroscópio» mudarem de forma corrida, sem travar e sem pular.
8. Empurre o analógico esquerdo do P3 em círculos, contando até vinte, e veja o pontinho fazer o mesmo círculo, sem saltar.
9. Clique na linha do P4 e refaça nele os passos 6 a 8.
10. Clique na linha do P3, ponha o P3 numa mão e o P1 na outra e gire os dois ao mesmo tempo, sem parar, contando até trinta.
11. Anote todo engasgo, toda parada e todo salto dos números do «Giroscópio» do P3.
12. Clique na linha do P4 e refaça os passos 10 e 11 com o P4 numa mão e o P2 na outra.
13. Volte à aba Conexões e anote de novo o menor e o maior número em Hz do P3 e do P4, por meio minuto.
14. Compare as anotações: o P3 e o P4 se comportaram igual, e o começo bateu com o fim?

**Passa quando.** O P3 e o P4 mostraram os números do giroscópio e o pontinho do analógico mudando de forma lisa, sem engasgo e sem salto, com um controle do cabo sendo girado junto. E os números em Hz dos dois, na aba Conexões, ficaram na mesma faixa entre si e entre o começo e o fim. Se um deles fica bem abaixo do outro, muda de cor, ou engasga numa volta e não na outra, anote os dois casos: é exatamente essa diferença que este teste procura.

**Por controle.**

* **P1** — No cabo, e aqui é carga: entra na segunda metade, girado junto com o P3, só para o cabo estar ocupado enquanto o rádio é lido.
* **P2** — No cabo, a segunda carga. Entra girado junto com o P4. Se o P4 só engasgar quando o P2 se mexe, anote — é o cabo atrapalhando o rádio.
* **P3** — No rádio, e é um dos dois medidos. O número em Hz dele, o giro, o analógico e o par com o P1. Anote a resposta dele separada da do P4.
* **P4** — No rádio, o outro medido, e ele é a metade que mais importa desta linha: o que já se mediu foi os dois aparelhos do rádio respondendo com quase o dobro de diferença um do outro, na MESMA janela e com o mesmo adaptador. Compare o número em Hz dele com o do P3 com atenção.

**A armadilha.** São dois números e eles respondem coisas diferentes. O da linha «Giroscópio:», no cartão, é o teto do produto — o Hefesto limita em 250 leituras por segundo o que repassa ao jogo. O de «Movimento por segundo», na aba Conexões, é o que chega do aparelho, e é ele que responde esta linha. E o que se mediu no fio é o oposto da fama: o cabo entrega sempre a mesma coisa e o rádio entrega uma FAIXA larga, instável de janela para janela e diferente entre os dois aparelhos — por isso o passo pede o menor e o maior, e não um número só. Segunda: a desigualdade entre os dois do rádio tem um suspeito forte e ainda não fechado — pode ser o modo de LER, e não o rádio. Por isso este teste não manda você caçar defeito no aparelho quando um responde diferente do outro; manda ANOTAR. A troca de cor do número é um corte do desenho, não medido — é a bancada que vai dizer onde o engasgo começa de verdade. Terceira: um controle do rádio não precisa de cor pintada para mandar movimento; o sistema já o põe no modo completo quando o reconhece, e um cartão sem giroscópio é achado. Quarta: o olho não enxerga a diferença entre 250 e 400 leituras por segundo — o que ele enxerga é engasgo. E a prova desta linha parou no fio: nada aqui diz o que o jogo recebeu.

---

## mapa-combinacao.dois_no_radio.crc-radio — Dois no RÁDIO — os erros de CRC de entrada aumentam? · rádio

*Célula:* `combinacao.dois_no_radio.crc @ rádio`

**O que isto prova.** Prova que dois controles no rádio ao mesmo tempo não passam a perder pedaços da leitura em silêncio.

**Onde olhar.** Não existe campo nenhum no Hefesto que mostre quadro perdido nem conta de erro — o contador existe por dentro do produto e ninguém o lê. Então o lugar de olhar é o EFEITO, e ele é o cartão de cada controle do rádio na aba Controles: o pontinho do analógico, os desenhos dos botões que acendem ao aperto, e os três números da moldura «Giroscópio». Pelo rádio, um pedaço de leitura que chega errado é jogado fora inteiro e não vira evento nenhum — nada aparece e nada avisa. Um aperto que não acende, um pontinho que salta, um número que trava: é assim que uma perda se apresenta. Há um sinal indireto: na aba Conexões, seção «Rádio e Adaptadores», o número em Hz na linha de cada controle («Movimento por segundo») conta só os quadros que chegaram inteiros — um quadro jogado fora não entra na conta. Ele oscila sozinho de janela para janela, então é contexto, não veredito.

**Os passos.**

* Abra a aba Controles.
1. Tire do PC o cabo do P1 e o do P2 e desligue os dois, segurando o PS de cada um até todas as luzes apagarem — ficam só os dois do rádio.
2. Confira na fita do topo que sobraram dois chips, os dois dizendo BT; enquanto os do cabo estão fora eles aparecem como P1 e P2, então chame de A o controle que era o P3 e de B o que era o P4, e siga-os pela cor do plástico.
3. Clique na linha do A para abrir o cartão dele.
4. Segure o A e mexa o analógico esquerdo em círculos, sem parar, contando até trinta.
5. Repare no pontinho do cartão durante todo esse tempo e escreva todo salto, toda parada e todo engasgo.
6. Aperte o Triângulo, o Círculo, o Quadrado e a Cruz do A, dez vezes cada um.
7. Conte quantos desses quarenta apertos não acenderam o desenho no cartão.
8. Clique na linha do B e repita nele os passos 4 a 7.
9. Ponha um controle em cada mão e mexa os dois analógicos ao mesmo tempo, em círculos, sem parar, contando até trinta, olhando o cartão que estiver aberto.
10. Escreva os engasgos que viu.
11. Na aba Conexões, abra «Rádio e Adaptadores» e anote o menor e o maior número em Hz do A e do B, por meio minuto.
12. Encaixe os cabos do P1 e do P2 de volta — se algum deles não voltar à fita sozinho, dê um toque no PS dele — e confira que o A e o B voltaram a ser o P3 e o P4.
13. Refaça a rodada inteira com os quatro ligados: o cartão do P3, o do P4, os dois analógicos juntos e os números em Hz.
14. Compare as duas rodadas lado a lado: dois no rádio sozinhos, e quatro ligados.

**Passa quando.** Nas duas rodadas, tudo o que você fez nos dois controles do rádio apareceu no cartão: nenhum aperto engolido, nenhum salto do pontinho, nenhuma parada dos números. E a rodada com quatro ligados não ficou pior que a rodada com dois. Um aperto que não acende, ou um pontinho que salta, é pedaço de leitura perdido — e é o achado que este teste procura.

**Por controle.**

* **P1** — No cabo, e sai na primeira rodada: tire o cabo dele do PC e desligue-o. Na segunda rodada ele volta, e o papel dele é só ocupar o cabo enquanto os dois do rádio são medidos.
* **P2** — No cabo, sai junto com o P1 na primeira rodada e volta na segunda. Mesmo papel: companhia, não medida.
* **P3** — No rádio, e é um dos dois medidos — o A da primeira rodada. Faça nele a volta inteira — analógico em círculos por trinta contagens e quarenta apertos de botão —, sozinho e depois em par com o P4.
* **P4** — No rádio, o outro medido — o B da primeira rodada —, e é ele quem dá sentido à linha: a pergunta é se DOIS no rádio perdem mais que um. Faça nele a mesma volta, e depois mexa nos dois ao mesmo tempo, um em cada mão.

**A armadilha.** Não existe verde de verdade neste teste, e é honesto dizer: a tela não tem campo de quadro perdido, então tudo o que você pode escrever é «não vi nada acontecer», que não é o mesmo que «nada aconteceu». A única medição que existe contou trinta e cinco mil pedaços de leitura em um minuto sem uma única falha — mas foi com os controles PARADOS na mesa, a distância de bancada e com bateria boa; ninguém variou distância, nem interferência, nem bateria baixa. Zero em um minuto não é zero sempre. Segunda: o P1 e o P2 são desligados, e não só desplugados, porque um controle já pareado por rádio nesta máquina pode voltar pelo rádio quando perde o cabo — e três no rádio já é outra pergunta. Terceira: com os do cabo fora, os dois do rádio passam a ser o P1 e o P2 na tela — é a ordem de conexão, e não é assunto deste teste; é por isso que os passos os chamam de A e B. Quarta: um cartão do rádio sem movimento e sem touchpad não perdeu quadro nenhum e não está «dormindo» — o sistema já o põe no modo completo quando o reconhece; anote como achado à parte. Quinta: a prova desta linha parou no fio — nada aqui diz o que o jogo recebeu. E do lado do cabo não há o que medir: o cabo não carrega esse pedaço de conferência, então não há falha que possa aumentar lá.

---

## mapa-combinacao.dois_no_radio.saida-radio — Dois no RÁDIO ao mesmo tempo — a saída de cada um sobrevive? · rádio

*Célula:* `combinacao.dois_no_radio.saida @ rádio`

**O que isto prova.** Prova que com DOIS controles no rádio e ninguém no cabo os dois continuam obedecendo aos comandos do Hefesto ao mesmo tempo.

**Onde olhar.** Nos aparelhos: a barra de luz de cada um dos dois controles do rádio — as duas tiras acesas dos lados do touchpad — e o tremor deles na sua mão. Na tela, os gestos ficam na aba Iluminação (uma coluna por controle; a linha «Cor» tem os quadradinhos de cor, e um quadradinho com X é a cor de outro controle e não aceita clique) e na aba Vibração (uma coluna por controle, com a linha «Testar agora» e os botões «Testar» e «Parar»). A contagem fica no alto à direita da tela e diz só os transportes que têm controle: com os quatro, «2 USB · 2 BT»; com só os dois do rádio, «2 BT». A tela mostra a cor PEDIDA; quem responde é a faixa acesa no plástico.

**Os passos.**

1. Abra a aba Iluminação.
2. Tire do PC o cabo do P1 e o do P2 e desligue os dois, segurando o PS de cada um até todas as luzes apagarem.
3. Confira na fita do topo que sobraram dois chips, os dois dizendo BT, e que a contagem no alto à direita diz «2 BT».
4. Enquanto os do cabo estão fora, os dois do rádio aparecem como P1 e P2: chame de A o que era o P3 e de B o que era o P4, e siga-os pela cor do plástico.
5. Anote a cor da barra de luz do A e do B.
6. Clique numa cor bem viva na linha «Cor» da coluna de cada um, uma bem diferente da outra.
7. Confira que a barra de cada um acendeu na cor escolhida para ele, e que as duas estão acesas ao mesmo tempo.
8. Clique em cores novas nas duas colunas, alternando, dez vezes seguidas, o mais rápido que der.
9. Anote todo clique que não acendeu.
10. Abra a aba Vibração.
11. Segure na mão um dos dois de cada vez, clique em «Testar» na coluna dele e, depois de sentir, em «Parar».
12. Ponha um controle em cada mão e clique em «Testar» nas duas colunas, uma logo depois da outra, o mais rápido que der.
13. Confira que os dois tremeram na vez de cada um — o segundo «Testar» encerra o primeiro — e clique em «Parar» na coluna do que ficou tremendo.
14. Encaixe os cabos do P1 e do P2 de volta — se algum deles não voltar à fita sozinho, dê um toque no PS dele — e refaça a volta inteira com os quatro ligados, só para comparar.

**Passa quando.** Com só os dois no rádio, os dois obedeceram a tudo ao mesmo tempo: as duas barras acenderam nas cores escolhidas, trocaram em toda a rajada sem pular clique, e as duas tremeram no «Testar», inclusive nos dois cliques em sequência rápida. Nenhum dos dois ficou para trás.

**Por controle.**

* **P1** — No cabo, e sai: tire o cabo dele do PC e desligue-o. Ele só volta na última rodada de comparação. Fora da medida, de propósito — esta linha pergunta pelos dois do rádio SEM ninguém no cabo.
* **P2** — No cabo, sai junto com o P1 pelo mesmo motivo, e volta junto na última rodada.
* **P3** — No rádio, e é um dos dois medidos — o A, enquanto os do cabo estão fora. Recebe cor própria, entra na rajada e treme no «Testar», com você segurando-o na mão.
* **P4** — No rádio, o outro medido — o B —, e é ele que fecha o sentido da linha: a pergunta é se DOIS no rádio cabem juntos. Mesmos comandos, cor bem diferente da do P3. Se um obedecer e o outro não, anote qual.

**A armadilha.** Se a barra de um dos dois não acende em cor NENHUMA desde o primeiro clique, a causa conhecida é a Steam ter sido aberta antes de aquele controle se conectar; fechar a Steam depois não cura — reconectar cura, e o botão «A luz não acende», na linha dele na aba Conexões, faz isso. O «Testar» fica ligado até o «Parar», e o de outra coluna encerra o da anterior: segure na mão o controle que está sendo medido, e não esqueça o «Parar» no fim. Saiba o peso deste teste: ele é a CONTRAPROVA do teste do cabo com rádio. Se a saída morrer aqui também, com ninguém no cabo, então a causa não é o controlador da máquina — é a fila do adaptador de rádio. Um vermelho aqui vale mais que um vermelho lá, porque ele separa duas explicações que ninguém separou ainda. Segunda: com dois controles ligados o Hefesto divide o esforço de um jeito e com quatro de outro, então não compare a rodada de dois com a de quatro para julgar «piorou»; a última rodada é só para você ver as duas cenas. Terceira: o P1 e o P2 são desligados, e não só desplugados, porque um controle já pareado por rádio nesta máquina pode voltar pelo rádio sem o cabo. Quarta: com os do cabo fora, os números dos que ficam mudam — é a ordem de conexão, não defeito, e eles voltam aos de antes quando os cabos voltam. E do lado do cabo não há o que medir nesta linha: a pergunta é sobre dois no rádio, e a pergunta do fio mora no teste de um no cabo com um no rádio.

---

## mapa-combinacao.rumble_simultaneo-cabo — Rumble em dois controles ao mesmo tempo · cabo

*Célula:* `combinacao.rumble_simultaneo @ cabo`

**O que isto prova.** Prova que os dois controles do cabo tremem quando o comando de vibração sai para vários controles quase ao mesmo tempo.

**Onde olhar.** Na aba Vibração do Hefesto: cada controle tem uma coluna, e a linha «Modelo» diz de quem ela é (por exemplo P1, a cor do plástico e USB). Na coluna ficam a linha «Força da vibração», com os degraus Economia, Balanceado e Máximo; as linhas «Motor esquerdo» e «Motor direito», cada uma com um botão que liga ou desliga aquele lado — aceso em laranja quando ligado — e uma barra de 0 a 100 %; e a linha «Testar agora», com os botões «Testar» e «Parar». O tremor não aparece em campo nenhum da tela — a prova é a sua mão e o seu ouvido, e é honesto dizer isso. No aparelho, os dois motores ficam um em cada punho: o esquerdo tem o contrapeso maior e soa grosso, o direito soa fino.

**Os passos.**

1. Abra a aba Vibração.
2. Anote o degrau aceso na linha «Força da vibração» de cada uma das quatro colunas.
3. Confira que as barras «Motor esquerdo» e «Motor direito» das quatro colunas não estão em 0 % e que o botão de cada lado está aceso.
4. Ponha o P1 na sua mão esquerda e deixe o P2 na mesa, sobre uma superfície dura, sem nada por cima.
5. Clique em «Testar» na coluna do P1 e, sem parar, em «Testar» na coluna do P2.
6. Sinta o P1 na mão e escute o P2 na mesa — os dois têm de responder, cada um na sua vez, porque o «Testar» do P2 encerra o do P1 — e anote se algum dos dois não respondeu.
7. Troque as mãos, o P2 na mão e o P1 na superfície dura, e refaça a dupla de cliques na ordem invertida: «Testar» no P2 e logo depois no P1.
8. Anote se algum dos dois não respondeu.
9. Com o P1 na mão, clique em «Testar» nas quatro colunas, uma atrás da outra, o mais rápido que der.
10. Anote se o P1 tremeu nessa volta com os quatro sendo chamados.
11. Repita a volta dos quatro com o P2 na mão e anote se ele tremeu.
12. Clique em «Parar» na coluna do último controle que tremeu — sem isso a vibração do jogo não chega a ele.
13. Abra um jogo que tenha vibração, com os quatro controles dentro dele.
14. Jogue com o P1 na mão até o jogo mandar vibração e anote como foi o tremor: veio, não veio, ou veio e morreu antes da hora.
15. Jogue com o P2 na mão até o jogo mandar vibração e anote a mesma coisa.

**Passa quando.** O P1 e o P2 tremeram todas as vezes em que chegou a vez deles, em qualquer ordem em que você clicou, inclusive quando os quatro foram chamados em sequência. E dentro do jogo os dois tremeram quando o jogo pediu, e o tremor durou o que tinha de durar em vez de morrer no começo. Se um dos dois não tremeu, ou se o tremor foi cortado, anote qual e em qual das duas metades — o botão «Testar» ou o jogo.

**Por controle.**

* **P1** — No cabo, e é um dos dois medidos. Segure-o na mão nas voltas em que ele é o alvo, e deixe-o sobre a superfície dura nas outras — ali o motor dele fica audível. Anote a resposta dele em cada volta.
* **P2** — No cabo, o outro medido. Mesma alternância: na mão numa volta, na superfície dura na outra. Se um dos dois tremer sempre e o outro só às vezes, anote qual e em que entrada o cabo dele está.
* **P3** — No rádio, e aqui ele é companhia: entra na volta em que os quatro são chamados em sequência, para o rádio estar recebendo comando junto. Deixe-o na mesa e só confirme que ele se mexeu.
* **P4** — No rádio, a segunda companhia. Mesmo papel do P3. Os dois no ar recebendo comando ao mesmo tempo é o que torna este teste sobre simultaneidade em vez de sobre um controle só.

**A espera.** O jogo pode levar minutos para chegar ao menu, e nenhum desses minutos é para ficar olhando a tela. Deixe-o carregando e vá fazer outra coisa; volte quando ouvir o som do menu. Nada do que você já mediu se desfaz por você ter saído da frente — os quatro controles continuam ligados e os degraus da «Força da vibração» continuam onde estavam. Ao voltar, comece pelo P1 na mão.

**A armadilha.** O disparo no MESMO instante saiu de instrumento, e com um par de mãos não dá para reproduzir — o que dá é um logo depois do outro, e isso já pega o defeito que interessa: o segundo não tremer. Não anote «não foi simultâneo» como reprovação. Segunda, e é a maior: as duas metades deste teste medem coisas diferentes. Pelo botão «Testar», quem manda o tremor é o próprio Hefesto, um controle por vez — o «Testar» de outra coluna encerra o da anterior —, então essa metade prova que o segundo obedece logo depois do primeiro; tremer JUNTO só a metade do jogo mostra. Dentro do JOGO quem manda é o jogo. Houve um defeito medido em 11/08: o Hefesto reescrevia os motores com zero e apagava a vibração de quem falava direto com o controle; desde 12/08 ele só repete a própria escrita por dois segundos depois de cada mudança que ELE faz. O que sobra disso é prático: mexer em cor, gatilho ou vibração na tela enquanto o jogo vibra pode cortar o tremor do jogo — durante a metade do jogo, não toque na tela. Se mesmo assim o tremor vier cortado ou fraco, anote em qual controle e em que momento: é esse resto que esta linha quer ver. Terceira: com um jogo aberto na primeira metade, um tremor no P2 pode ser do jogo e não do seu clique — por isso a bancada começa com nenhum jogo aberto, conferido na faixa do topo da página, e o jogo só entra no fim. Quarta: o «Testar» não para sozinho — ele fica ligado até o «Parar», e enquanto estiver de pé a vibração do jogo não chega ao controle; por isso o «Parar» vem antes de abrir o jogo. Com o controle largado numa superfície mole você não vê nem ouve, e anota «nada aconteceu» sobre um produto que obedeceu. Quinta: com a barra de um motor em 0 %, ou com o botão daquele lado apagado, aquele punho não treme, por mais certo que esteja o resto.

---

## mapa-combinacao.rumble_simultaneo-radio — Rumble em dois controles ao mesmo tempo · rádio

*Célula:* `combinacao.rumble_simultaneo @ rádio`

**O que isto prova.** Prova que os dois controles do rádio tremem quando o comando de vibração sai para vários controles quase ao mesmo tempo.

**Onde olhar.** Na aba Vibração do Hefesto: uma coluna por controle, e a linha «Modelo» diz de quem ela é (por exemplo P3, a cor do plástico e BT). Na coluna ficam a linha «Força da vibração», com os degraus Economia, Balanceado e Máximo; as linhas «Motor esquerdo» e «Motor direito», cada uma com um botão que liga ou desliga aquele lado — aceso em laranja quando ligado — e uma barra de 0 a 100 %; e a linha «Testar agora», com os botões «Testar» e «Parar». O tremor não aparece em campo nenhum da tela — a prova é a sua mão e o seu ouvido. No aparelho, os dois motores ficam um em cada punho: o esquerdo soa grosso, o direito soa fino.

**Os passos.**

1. Abra a aba Vibração.
2. Anote qual degrau está aceso na linha «Força da vibração» de cada uma das quatro colunas.
3. Confira que as barras «Motor esquerdo» e «Motor direito» das quatro colunas não estão em 0 % e que o botão de cada lado está aceso.
4. Ponha o P3 na sua mão esquerda e deixe o P4 na mesa, sobre uma superfície dura, sem nada por cima.
5. Clique em «Testar» na coluna do P3 e, sem parar, clique em «Testar» na coluna do P4.
6. Sinta o P3 na mão e escute o P4 na mesa — os dois têm de responder, cada um na sua vez, porque o «Testar» do P4 encerra o do P3 — e anote se algum dos dois não respondeu.
7. Troque — o P4 na mão, o P3 na superfície dura — e clique em «Testar» na coluna do P4 e, sem parar, na do P3.
8. Anote se algum dos dois falhou com a ordem invertida.
9. Com o P3 na mão, clique em «Testar» nas quatro colunas, uma atrás da outra, o mais rápido que der.
10. Anote se o P3 tremeu nessa volta com os quatro sendo chamados.
11. Repita essa volta dos quatro com o P4 na mão e anote a resposta dele.
12. Clique em «Parar» na coluna do último controle que tremeu — sem isso a vibração do jogo não chega a ele.
13. Abra um jogo que tenha vibração, com os quatro controles dentro dele.
14. Jogue com o P3 na mão até o jogo mandar vibração, e depois repita com o P4 na mão.
15. Anote, em cada um, como foi o tremor: veio, não veio, ou veio e morreu antes da hora.

**Passa quando.** O P3 e o P4 tremeram todas as vezes em que chegou a vez deles, em qualquer ordem em que você clicou, inclusive quando os quatro foram chamados em sequência. E dentro do jogo os dois tremeram quando o jogo pediu, e o tremor durou o que tinha de durar. Se um dos dois não tremeu, ou se o tremor foi cortado, anote qual e em qual das duas metades — o botão «Testar» ou o jogo.

**Por controle.**

* **P1** — No cabo, e aqui é companhia: entra na volta em que os quatro são chamados em sequência, para o cabo estar recebendo comando junto. Deixe-o na mesa e só confirme que ele se mexeu.
* **P2** — No cabo, a segunda companhia. Mesmo papel do P1. Os dois do cabo recebendo comando ao mesmo tempo é o que faz este teste medir simultaneidade, e não um controle sozinho.
* **P3** — No rádio, e é um dos dois medidos. Segure-o na mão nas voltas em que ele é o alvo e deixe-o na superfície dura nas outras. Anote a resposta dele em cada volta.
* **P4** — No rádio, o outro medido. Mesma alternância. Se um dos dois do rádio tremer sempre e o outro só às vezes, anote qual — e olhe a bateria dele na aba Controles antes de reprovar, porque bateria baixa muda o tremor.

**A espera.** O jogo pode levar minutos para chegar ao menu, e nenhum desses minutos é para ficar olhando a tela. Deixe-o carregando e vá fazer outra coisa; volte quando ouvir o som do menu. Nada do que você já mediu se desfaz por você ter saído da frente — os quatro continuam ligados e os degraus da «Força da vibração» continuam onde estavam. Ao voltar, comece pelo P3 na mão.

**A armadilha.** O disparo no MESMO instante saiu de instrumento; com um par de mãos o que dá é um logo depois do outro, e isso já pega o que interessa — o segundo não tremer. Não anote «não foi simultâneo» como reprovação. Segunda, e é a maior: as duas metades medem coisas diferentes. Pelo botão «Testar», quem manda o tremor é o próprio Hefesto, um controle por vez — o «Testar» de outra coluna encerra o da anterior —, então essa metade prova que o segundo obedece logo depois do primeiro; tremer JUNTO, os dois do cabo e os dois do rádio, só a metade do jogo mostra. Dentro do JOGO quem manda é o jogo, e jogando com o Hefesto no meio os quatro já vibraram pelo rádio sem problema — ali o tremor vem pelo caminho do jogo e o Hefesto é a fonte, não o concorrente. Houve um defeito medido em 11/08, em que o Hefesto reescrevia os motores com zero e apagava a vibração de quem falava direto com o controle; desde 12/08 ele só repete a própria escrita por dois segundos depois de cada mudança que ELE faz. O que sobra é prático: mexer em cor, gatilho ou vibração na tela enquanto o jogo vibra pode cortar o tremor — durante a metade do jogo, não toque na tela, e se o tremor vier cortado assim mesmo, anote em qual controle e em que momento. Terceira: o «Testar» não para sozinho — ele fica ligado até o «Parar», e enquanto estiver de pé a vibração do jogo não chega ao controle; por isso o «Parar» vem antes de abrir o jogo. Numa superfície mole você não vê nem ouve. Quarta: com a barra de um motor em 0 %, ou com o botão daquele lado apagado, aquele punho não treme. Quinta: a primeira metade só vale com NENHUM jogo aberto — é o que a faixa da bancada garante no alto da página, e é por isso que ela está lá; com um jogo aberto, um tremor pode ser dele e não do seu clique.

---

## mapa-combinacao.slot_jogador.estabilidade-cabo — O número de jogador se mantém quando outro controle entra ou sai? · cabo

*Célula:* `combinacao.slot_jogador.estabilidade @ cabo`

**O que isto prova.** Prova que tirar um controle do cabo e devolvê-lo em menos de trinta segundos não mexe no número de ninguém — nem durante a ausência — e que o que saiu volta com o dele.

**Onde olhar.** Em três lugares. Na fita do topo do Hefesto, a linha que começa com «Selecionar:», onde cada controle é um chip com o número, a cor do plástico e a palavra USB ou BT. Na aba Conexões, seção «Gestão de Controles» (abre clicando no título), onde cada linha começa com «Sony», o «Player» e o número, a cor do plástico e USB ou BT. E nos aparelhos, a fileira de cinco lampadinhas brancas embaixo do touchpad: o número não se conta da esquerda para a direita, ele é o CONJUNTO aceso — jogador 1 é só a do meio; jogador 2 são a segunda e a quarta; jogador 3 são as duas das pontas e a do meio; jogador 4 são as quatro, com a do meio apagada.

**Os passos.**

* Abra a aba Conexões.
1. Clique no título «Gestão de Controles» para abrir a seção.
2. Anote num papel o número de Player dos quatro e a cor do plástico de cada um, na ordem em que eles aparecem.
3. Anote também o que cada chip da fita do topo mostra: o número, a cor do plástico e a palavra USB ou BT.
4. Olhe as cinco lampadinhas embaixo do touchpad dos quatro e confira que a figura de cada um bate com o número da tela.
5. Puxe do PC a ponta do cabo do P2 — este é o que sai, e ele está no cabo.
6. Olhe a fita na hora e confira que cada um dos três que ficaram mostra o mesmo número de antes, reconhecendo cada um pela cor do plástico.
7. Leia a lista da «Gestão de Controles» e confira os números dela também.
8. Olhe as lampadinhas dos três que ficaram e confira que a figura de cada um não mudou.
9. Encaixe a ponta do cabo do P2 de volta, em menos de trinta segundos.
10. Espere o chip dele reaparecer na fita.
11. Leia de novo os quatro números, primeiro na fita e depois na lista.
12. Olhe as lampadinhas dos quatro aparelhos.
13. Compare tudo com o que você anotou nos passos 2, 3 e 4.
14. Refaça os passos 5 a 13 puxando o cabo do P1 em vez do do P2, e devolvendo-o em menos de trinta segundos.

**Passa quando.** Enquanto o que saiu está fora, os três que ficaram mostram o mesmo número de antes — na fita, na lista e nas lampadinhas. Quando ele volta, os quatro estão exatamente nos números que você anotou no começo. Nenhum controle fica com o número de outro, nenhum número aparece repetido, e a figura das cinco lampadinhas concorda com a tela nos quatro aparelhos.

**Por controle.**

* **P1** — No cabo. Na primeira volta ele não se toca: anote o número dele antes, durante a ausência do P2 e depois — tem de ser o mesmo nas três. Na segunda volta é ELE que sai — puxe o cabo dele e devolva em menos de trinta segundos.
* **P2** — No cabo, e é o primeiro a sair. Puxe a ponta do cabo dele do PC, olhe os outros três durante a ausência e devolva o cabo em menos de trinta segundos. Ele tem de voltar com o número que tinha no passo 2.
* **P3** — No rádio, e não se toca nele em volta nenhuma. É testemunha: anote o número dele antes, olhe durante a ausência do que saiu, e confira no fim. Ele continua P3 o tempo todo.
* **P4** — No rádio, e também não se toca. Segunda testemunha, e é o último da fila. Confira o número dele na tela e a figura das lampadinhas antes, durante e depois: continua P4.

**A armadilha.** Passar do prazo. O lugar de quem sai fica guardado por trinta segundos, contados de quando o chip dele some da fita — vale para os quatro, e não só para o P1. Passado esse tempo sem ele voltar, a fila se fecha de propósito: quem vinha depois desce um número, na tela na hora e nas lampadinhas junto com a cor da barra. Por isso cada volta tem de caber em trinta segundos; o que sai e volta depois disso continua recuperando o dele, mas o meio do teste é outro. Segunda: as cinco lampadinhas não se contam da esquerda para a direita — o número é o conjunto aceso, e quem lê «a terceira acesa» como jogador 3 reprova um produto certo. Terceira: o número é do Hefesto, sempre — nem a Steam nem um jogo aberto mudam as lampadinhas; tela e lampadinhas discordando é achado. A dica da linha «Jogador» da aba Iluminação ainda diz que um jogo pode mandar o número por cima: essa frase caducou. Quarta: o lado do RÁDIO desta linha nunca foi medido — se você fizer o mesmo gesto desligando um controle do rádio, o que sair dali é achado novo, não repetição.

---

## mapa-combinacao.tres_na_mesa-cabo — TRÊS controles ao mesmo tempo (o caso de co-op dela) · cabo

*Célula:* `combinacao.tres_na_mesa @ cabo`

**O que isto prova.** Prova que com TRÊS controles ligados os dois que estão no cabo continuam obedecendo e continuam sendo lidos.

**Onde olhar.** Na fita do topo, os chips de controle, cada um com o número, a cor do plástico e a palavra USB ou BT; e, no alto à direita, a contagem, que diz só os transportes que têm controle — «2 USB · 1 BT» com três ligados, «2 USB · 2 BT» com os quatro. Na aba Iluminação, uma coluna por controle com a linha «Cor» de quadradinhos — um quadradinho com X é a cor de outro controle e não aceita clique — e a resposta é a barra de luz no aparelho, as duas tiras acesas dos lados do touchpad. Na aba Controles, o cartão de cada controle, com o pontinho de cada analógico e os desenhos dos botões que acendem ao aperto. Na aba Vibração, a coluna de cada controle com a linha «Testar agora» e os botões «Testar» e «Parar».

**Os passos.**

* Abra a aba Iluminação.
1. Desligue o P4 segurando o botão PS dele até todas as luzes apagarem — este teste é com TRÊS ligados.
2. Confira na fita do topo que sobraram três chips: dois dizendo USB e um dizendo BT.
3. Leia a contagem no alto à direita: ela tem de dizer «2 USB · 1 BT».
4. Clique numa cor bem viva na linha «Cor» da coluna do P1, numa cor bem diferente na do P2 e numa terceira na do P3.
5. Veja as três barras de luz acesas ao mesmo tempo, cada uma na sua cor.
6. Na aba Controles, clique na linha do P1 para abrir o cartão dele.
7. Mexa os dois analógicos do P1 e aperte os quatro botões da face dele.
8. Veja cada movimento e cada aperto aparecerem no cartão.
9. Clique na linha do P2 e repita nele os passos 7 e 8.
10. Na aba Vibração, clique em «Testar» na coluna do P1, com ele na mão, e confira que ele tremeu.
11. Clique em «Testar» na coluna do P2, com ele na mão, confira que ele tremeu também e clique em «Parar» na coluna dele.
12. Ligue o P4 com um toque no botão PS.
13. Veja o chip dele entrar na fita e a contagem virar «2 USB · 2 BT».
14. Refaça as três cores e os dois «Testar» com os quatro ligados, terminando no «Parar».
15. Escreva as duas rodadas lado a lado: com três e com quatro.

**Passa quando.** Com três ligados, o P1 e o P2 — os dois do cabo — acenderam a cor escolhida no ato, mostraram no cartão tudo o que você fez neles, e tremeram no «Testar». E nada disso piorou quando o quarto controle entrou: as mesmas cores acenderam igual e os mesmos tremores vieram igual com os quatro.

**Por controle.**

* **P1** — No cabo, e é um dos dois medidos. Recebe cor própria, é lido no cartão e treme no «Testar», com três ligados e depois com quatro.
* **P2** — No cabo, o outro medido. Mesmos gestos, com cor bem diferente da do P1. Se um dos dois responder pior quando o quarto entra, anote qual.
* **P3** — No rádio, e fica ligado o tempo todo: é ele que faz serem TRÊS em vez de dois. Recebe cor própria também, e é isso que o põe para trabalhar enquanto o cabo é medido.
* **P4** — Fica DESLIGADO na primeira metade — segure o PS dele até apagar — e entra só perto do fim. Ele é a comparação: se o P1 e o P2 respondiam bem com três e passam a falhar quando ele entra, o achado é o quarto lugar.

**A armadilha.** A medição que existe mediu PRESENÇA, não partida: os controles estavam parados, sem jogo aberto e sem ninguém apertando nada. O custo dentro de um JOGO — com a Steam aberta, com o espelho que ela faz de cada controle, e com quatro pessoas apertando ao mesmo tempo — é justamente o que continua sem medida, e é como você joga. Segunda, e é um susto conhecido: a Steam faz uma cópia de cada controle que enxerga, inclusive do controle que o próprio Hefesto cria — então três ligados podem virar seis para o jogo. Se ao abrir um jogo aparecerem jogadores a mais, ou um jogador fantasma, isso é a Steam, não o Hefesto; por isso a bancada pede a Steam fechada por inteiro antes de começar. E ela tem de continuar fechada quando o P4 volta: um controle que se conecta pelo rádio com a Steam aberta volta com a barra apagada. Terceira: desligar o P4 não muda o número de ninguém — ele é o último da fila —, e ele volta como P4. Quarta: o «Testar» fica ligado até o «Parar», e o de outra coluna encerra o da anterior — segure na mão o controle que está sendo medido. Quinta: a prova desta linha parou no fio, então nada aqui diz o que o jogo recebeu; o que você prova aqui é que os aparelhos obedecem. E este teste é longo de propósito: ele mede a mesma coisa DUAS vezes — com três ligados e com quatro —, e é a comparação entre as duas rodadas que é a entrega; sem a segunda rodada não há com o que comparar.

---

## mapa-combinacao.tres_na_mesa-radio — TRÊS controles ao mesmo tempo (o caso de co-op dela) · rádio

*Célula:* `combinacao.tres_na_mesa @ rádio`

**O que isto prova.** Prova que com TRÊS controles ligados os dois que estão no rádio continuam obedecendo e continuam sendo lidos.

**Onde olhar.** Na fita do topo, os chips de controle, cada um com o número, a cor do plástico e a palavra USB ou BT; e, no alto à direita, a contagem, que diz só os transportes que têm controle — «1 USB · 2 BT» com três ligados, «2 USB · 2 BT» com os quatro. Na aba Iluminação, uma coluna por controle com a linha «Cor» de quadradinhos — um quadradinho com X é a cor de outro controle e não aceita clique — e a resposta é a barra de luz no aparelho, as duas tiras acesas dos lados do touchpad. Na aba Controles, o cartão de cada controle, com o pontinho de cada analógico, os desenhos dos botões que acendem ao aperto e o quadro «Touchpad». Na aba Vibração, a coluna de cada controle com a linha «Testar agora» e os botões «Testar» e «Parar».

**Os passos.**

1. Abra a aba Iluminação.
2. Tire do PC o cabo do P2 e desligue-o, segurando o PS dele até todas as luzes apagarem — este teste é com TRÊS ligados, e o P2 é o que sai.
3. Confira na fita do topo que sobraram três chips: um dizendo USB e dois dizendo BT.
4. Enquanto o P2 está fora, os dois do rádio sobem um número: chame de A o que era o P3 e de B o que era o P4, e siga-os pela cor do plástico.
5. Leia a contagem no alto à direita e confira que ela diz «1 USB · 2 BT».
6. Clique numa cor bem viva na coluna do A, numa bem diferente na do B e numa terceira na do P1.
7. Confira que a barra de luz de cada um dos três acendeu na cor que você clicou nele, e que as três estão acesas ao mesmo tempo.
8. Na aba Controles, clique na linha do A para abrir o cartão dele.
9. Mexa os dois analógicos do A, aperte os quatro botões da face e arraste o dedo no touchpad; depois clique na linha do B e faça o mesmo nele.
10. Confira que tudo o que você fez nos dois apareceu no cartão de cada um.
11. Na aba Vibração, segure o A e clique em «Testar» na coluna dele; depois segure o B e clique no «Testar» da coluna dele, que encerra o do A, e termine no «Parar» da coluna do B.
12. Confira que cada um tremeu na sua vez.
13. Encaixe o cabo do P2 de volta — se ele não voltar à fita sozinho, dê um toque no PS dele — e confira que a contagem voltou a «2 USB · 2 BT» e que o A e o B voltaram a ser o P3 e o P4.
14. Refaça as três rodadas com os quatro ligados: as cores na aba Iluminação, os cartões do P3 e do P4 na aba Controles, e o «Testar» dos dois na aba Vibração, terminando no «Parar».
15. Escreva as duas rodadas lado a lado: com três e com quatro.

**Passa quando.** Com três ligados, os dois do rádio acenderam a cor escolhida no ato, mostraram no cartão tudo o que você fez neles, e tremeram no «Testar». E nada disso piorou quando o quarto controle voltou para o cabo: as mesmas cores acenderam igual e os mesmos tremores vieram igual com os quatro.

**Por controle.**

* **P1** — No cabo, e fica ligado o tempo todo: é ele que faz serem TRÊS em vez de dois, e que ocupa o cabo enquanto o rádio é medido. Recebe cor própria também.
* **P2** — Fica FORA na primeira metade — sem o cabo e desligado — e volta só no fim. Ele é a comparação: se os dois do rádio respondiam bem com três e passam a falhar quando ele volta, o achado é o segundo cabo entrando na conta.
* **P3** — No rádio, e é um dos dois medidos — o A, enquanto o P2 está fora. Recebe cor própria, é lido no cartão — analógicos, botões e touchpad — e treme no «Testar», com três ligados e depois com quatro.
* **P4** — No rádio, o outro medido — o B. Mesmos gestos, com cor bem diferente da do P3. Se um dos dois do rádio responder pior que o outro, anote qual: dois aparelhos do mesmo lado já foram medidos respondendo bem diferente um do outro, e isso é dado, não ruído.

**A armadilha.** A medição que existe mediu PRESENÇA, não partida: os controles estavam parados, sem jogo aberto e sem ninguém apertando nada. O custo dentro de um JOGO — com a Steam aberta e quatro pessoas apertando ao mesmo tempo — é o que continua sem medida, e é como você joga. Segunda: a Steam faz uma cópia de cada controle que enxerga, inclusive do controle que o próprio Hefesto cria, então três ligados podem virar seis para o jogo — feche-a por inteiro antes de começar; jogador a mais na tela do jogo é isso, e não defeito do Hefesto. Terceira: o P2 é desligado, e não só desplugado, porque um controle já pareado por rádio nesta máquina pode voltar pelo rádio sem o cabo — e aí seriam três no rádio, outra pergunta. Quarta: tirar o P2 muda o número dos dois do rádio enquanto ele está fora — é a ordem de conexão, não defeito —, e é por isso que os passos os chamam de A e B. Quinta: um cartão do rádio sem movimento e sem touchpad não é um controle esperando cor para acordar: o sistema já o põe no modo completo quando o reconhece; anote como achado. E a prova desta linha parou no fio — o que você prova aqui é que os aparelhos obedecem, e não o que o jogo recebeu.

---

## mapa-energia.bateria.degraus-cabo — Bateria — nível em cinco degraus · cabo

*Célula:* `energia.bateria.degraus @ cabo`

**O que isto prova.** Prova que o número da bateria dos dois controles do cabo só pode ser um dos onze valores que o aparelho sabe dizer, e que ele anda de dez em dez.

**Onde olhar.** Na aba Controles do Hefesto, no quadro «Dispositivos conectados». Cada controle tem uma linha, e no fim dela vem a palavra Bateria, uma barrinha e o número em porcento. A linha fechada começa pelo número do controle, a cor do plástico e a palavra USB ou BT. Um cartão fica sempre aberto — um, ou os quatro com «Todos» —, e no cartão aberto o número do controle some do começo da linha; por isso os passos abrem o cartão de um controle que NÃO está sendo medido, e as linhas dos medidos ficam fechadas, cada uma começando pelo número.

**Os passos.**

1. Abra a aba Controles.
2. Clique na linha do P3 para abrir o cartão dele — assim as linhas do P1 e do P2 ficam fechadas, cada uma começando pelo número.
3. Confira que a linha do P1 e a do P2 dizem USB.
4. Anote num papel o número de bateria do P1 e o do P2, com a hora ao lado.
5. Confira que cada um dos dois números termina em 5, ou é exatamente 100.
6. Marque um alarme de 40 minutos no celular.
7. Saia da frente da tela e faça o que a espera, mais abaixo, diz.
8. Volte à aba Controles quando o alarme tocar.
9. Anote os dois números de novo, embaixo dos primeiros.
10. Confira que os dois números novos também terminam em 5, ou são 100.
11. Compare cada controle com ele mesmo e veja de quanto foi o pulo.
12. Confira que, onde houve pulo, ele foi de dez pontos, ou de um múltiplo de dez.

**Passa quando.** Os quatro números anotados — dois controles, duas leituras cada — são todos um destes onze: 5, 15, 25, 35, 45, 55, 65, 75, 85, 95 ou 100. Nenhum número quebrado, nada de 63% nem de 42%. E onde o número mudou, ele mudou de dez em dez, e para cima, porque os dois estão no cabo e estão carregando.

**Por controle.**

* **P1** — No cabo. Anote o número dele agora e de novo aos quarenta minutos. Os dois números têm de terminar em 5 ou ser 100, e o esperado é o segundo ser MAIOR, porque ele está carregando.
* **P2** — No cabo, igual ao P1. Mesma anotação nas duas horas, mesma regra dos onze valores. Se o P1 andar e o P2 ficar parado, anote — dois controles no mesmo cabo e no mesmo estado deveriam andar juntos.
* **P3** — No rádio, e é testemunha. Não plugue cabo nenhum nele durante os quarenta minutos. Anote o número dele nas duas leituras só para saber que ele continuou vivo; a escada dele é o outro teste.
* **P4** — No rádio, e é a segunda testemunha. Mesma coisa do P3: nada de cabo, nada de desligar. Se os dois do cabo pararem e os dois do rádio andarem, o congelamento é do cabo, e isso é o achado.

**A espera.** São quarenta minutos, e nenhum deles é para ficar olhando a tela. Depois de anotar os dois números e marcar o alarme, faça os dois testes de bateria no jogo desta mesma família — eles só olham e não desligam nada. Nesse tempo não desplugue os cabos do P1 e do P2, não desligue nenhum controle e não troque ninguém de cabo para rádio: qualquer uma dessas coisas zera o experimento. Quando o alarme tocar, volte à aba Controles e leia os dois números.

**A armadilha.** Controle já cheio no cabo fica parado em 100%, e isso NÃO é o defeito — comece o teste com o P1 e o P2 abaixo de 100%, usando-os um pouco antes ou esperando a carga cair. E saiba o que este teste NÃO prova: em 06/09 os quatro controles da bancada foram lidos no aparelho e apareceram só DOIS degraus dos onze, porque os quatro estavam no mesmo estado de carga. Dois pontos não desenham uma escada, então um verde aqui é um verde estreito. O que reprova de verdade é um número que não termina em 5 e não é 100 — 63%, por exemplo —, ou um pulo que não seja de dez em dez. Não leia o número no cartão aberto sem conferir de quem ele é: no cartão aberto o número do controle some do começo da linha, e é fácil anotar a bateria do controle errado. Uma última coisa, para você não caçar o que não existe: o nome desta linha fala em cinco degraus, e isso veio do vocabulário de outros controles; o DualSense tem ONZE.

---

## mapa-energia.bateria.degraus-radio — Bateria — nível em cinco degraus · rádio

*Célula:* `energia.bateria.degraus @ rádio`

**O que isto prova.** Prova que o número da bateria dos dois controles do rádio desce pela mesma escada de onze valores, sem inventar número quebrado e sem congelar.

**Onde olhar.** Na aba Controles do Hefesto, no quadro «Dispositivos conectados». Cada controle tem uma linha que termina com a palavra Bateria, uma barrinha e o número em porcento; a linha fechada começa pelo número do controle, a cor do plástico e a palavra USB ou BT. Um cartão fica sempre aberto, e no cartão aberto o número do controle some do começo da linha — por isso os passos abrem o cartão do P1, e as linhas do P3 e do P4 ficam fechadas, cada uma começando pelo número. Confira a palavra BT nas linhas do P3 e do P4 antes de anotar qualquer coisa.

**Os passos.**

1. Abra a aba Controles.
2. Clique na linha do P1 para abrir o cartão dele — assim as linhas do P3 e do P4 ficam fechadas, cada uma começando pelo número.
3. Confira que a linha do P3 e a do P4 dizem BT, e que não há cabo nenhum encaixado neles.
4. Anote num papel o número de bateria do P3 e o do P4, com a hora ao lado.
5. Confira que cada um dos dois números termina em 5, ou é exatamente 100.
6. Marque um alarme de 40 minutos no celular.
7. Saia da frente da tela e faça o que a espera, mais abaixo, diz.
8. Volte à aba Controles quando o alarme tocar.
9. Anote os dois números de novo, embaixo dos primeiros.
10. Confira que os dois números novos também terminam em 5, ou são 100.
11. Compare cada controle com ele mesmo e veja de quanto foi o pulo.
12. Confira que, onde houve pulo, ele foi de dez pontos para BAIXO, ou de um múltiplo de dez.

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

**Onde olhar.** Começa na aba Controles, nas linhas fechadas do quadro «Dispositivos conectados». Passe o mouse no começo da linha de cada controle — o número e a cor do plástico — e leia a dica: ela diz de qual jogador é o gamepad virtual que aquele controle alimenta, e, quando o nome dele no sistema foge do padrão, ela diz também «No sistema ele se chama» e o nome. Com a máscara DualSense, o nome do gamepad virtual termina com «(Hefesto P1)», com o número do jogador. Logo depois da palavra USB a linha diz a máscara que o jogo vê: o espelho da bateria só existe no gamepad virtual de DualSense, e com a máscara de Xbox não há bateria para mostrar. Onde um jogo mostra a bateria de um controle, A FONTE NÃO DIZ. O lugar mais próximo que existe é a lista de controles da Steam, em Configurações, e a tela de controles do próprio jogo, se ele tiver uma. Se nenhum dos dois mostrar bateria, isso é resposta e se escreve.

**Os passos.**

1. Abra a aba Controles.
2. Clique na linha do P3 para abrir o cartão dele, deixando as linhas do P1 e do P2 fechadas.
3. Anote o número de bateria do P1 e o do P2, e a máscara que a linha de cada um diz depois da palavra USB.
4. Passe o mouse no começo da linha do P1 e anote o que a dica diz: o jogador do gamepad virtual e, se houver, o nome depois de «No sistema ele se chama».
5. Faça o mesmo na linha do P2.
6. Abra a Steam.
7. Abra as Configurações da Steam e vá à página de Controle, onde ela lista os controles que enxerga.
8. Procure na lista o gamepad virtual do P1 e o do P2 — o nome termina com «(Hefesto P» e o número do jogador, ou é o que a dica disse.
9. Anote, para cada um dos dois, o que a lista mostra de bateria — o número, ou nada — e se ela diz que ele está carregando.
10. Compare os dois números com os que você anotou no começo.
11. Escreva «não há onde ler» se nenhuma tela fora do Hefesto mostrar bateria.
12. Ao terminar, feche a Steam por inteiro.

**Passa quando.** O número que aparece do lado de fora para o gamepad virtual do P1 e para o do P2 é o mesmo que o Hefesto mostra para eles, com no máximo um degrau de dez de diferença. Se não houver bateria à mostra em lugar nenhum fora do Hefesto, escreva «não há onde ler» e siga adiante — é resposta válida e não é erro seu.

**Por controle.**

* **P1** — No cabo, e é um dos dois que este teste mede. Anote o número dele no Hefesto, o que a dica diz do gamepad virtual dele, e procure esse gamepad na lista de fora.
* **P2** — No cabo, e é o segundo que este teste mede. Mesma sequência. Dois controles em vez de um importam aqui: se o de fora mostrar o MESMO número para os dois, e no Hefesto eles estiverem diferentes, o número de fora não veio destes controles.
* **P3** — No rádio, e é testemunha. Não mexa nele. Anote o número dele no Hefesto e o que a lista de fora diz — ele serve para você ver se o de fora está repetindo o mesmo valor para todo mundo.
* **P4** — No rádio, e é a segunda testemunha. Mesma coisa. Quatro controles com quatro números diferentes no Hefesto e um único número igual lá fora é a assinatura do valor inventado.

**A armadilha.** A PROVA DESTA LINHA PAROU NO MONTOU: o número é montado e escrito no gamepad virtual, e ninguém nunca o viu chegar do outro lado. Por isso a cilada aqui é o valor de fábrica — quando o Hefesto não tem o dado, ele manda «cheio e carregando». Então «100% carregando» nos quatro, para sempre, é o FALSO VERDE deste teste, não a aprovação: é o que o produto diz quando não sabe. Some a isso uma coisa já medida nesta casa: o gamepad virtual tem um registro de bateria próprio no sistema que diz «carregando» eternamente. O Hefesto deixou de ler esses registros em 06/09, mas qualquer outro programa que os leia vê um número que NUNCA muda. Se a linha disser a máscara de Xbox, anote «máscara de Xbox» para aquele controle e siga só com o outro; se a dica disser que ele ainda não alimenta gamepad virtual nenhum, anote isso — é o Modo Nativo, e não há o que espelhar. E cuidado com nome repetido: cada controle físico pode aparecer uma vez na lista de fora e o gamepad virtual dele outra. Se você comparar o físico com o físico, o teste não mediu o caminho até o jogo — foi por isso que os passos mandam anotar a dica primeiro. Por último, feche a Steam ao terminar: com ela aberta, um controle do rádio que se reconectar depois volta com a barra apagada.

---

## mapa-energia.bateria.jogo-radio — Bateria — espelho ao jogo (vpad) · rádio

*Célula:* `energia.bateria.jogo @ rádio`

**O que isto prova.** Prova se o número da bateria do P3 e do P4, que estão no rádio, sai do Hefesto e chega a quem os enxerga como controle de jogo.

**Onde olhar.** Começa na aba Controles, nas linhas fechadas do quadro «Dispositivos conectados». Passe o mouse no começo da linha de cada controle — o número e a cor do plástico — e leia a dica: ela diz de qual jogador é o gamepad virtual que aquele controle alimenta, e, quando o nome dele no sistema foge do padrão, ela diz também «No sistema ele se chama» e o nome. Com a máscara DualSense, o nome do gamepad virtual termina com «(Hefesto P3)», com o número do jogador. Logo depois da palavra BT a linha diz a máscara que o jogo vê: o espelho da bateria só existe no gamepad virtual de DualSense. Onde um jogo mostra a bateria de um controle, A FONTE NÃO DIZ. O lugar mais próximo é a lista de controles da Steam, em Configurações, e a tela de controles do próprio jogo, se ele tiver uma. Nenhum dos dois mostrando bateria também é resposta, e se escreve.

**Os passos.**

1. Abra a aba Controles.
2. Clique na linha do P1 para abrir o cartão dele, deixando as linhas do P3 e do P4 fechadas.
3. Confira que a linha do P3 e a do P4 dizem BT, e anote a máscara que cada uma diz logo depois.
4. Anote o número de bateria do P3 e o do P4.
5. Passe o mouse no começo da linha do P3 e anote o que a dica diz: o jogador do gamepad virtual e, se houver, o nome depois de «No sistema ele se chama».
6. Faça o mesmo na linha do P4.
7. Abra a Steam.
8. Abra as Configurações da Steam e vá à página de Controle.
9. Procure na lista o gamepad virtual do P3 e o do P4 — o nome termina com «(Hefesto P» e o número do jogador, ou é o que a dica disse.
10. Anote o que a lista mostra de bateria para cada um — o número, ou nada — e se ela diz que algum deles está carregando.
11. Compare os dois números com os que você anotou no começo.
12. Anote lado a lado o que a lista mostrou para os dois do cabo e para os dois do rádio.
13. Escreva «não há onde ler» se nenhuma tela fora do Hefesto mostrar bateria.
14. Ao terminar, feche a Steam por inteiro.

**Passa quando.** O número que aparece do lado de fora para o gamepad virtual do P3 e para o do P4 é o mesmo que o Hefesto mostra para eles, com no máximo um degrau de dez de diferença. Se os dois do cabo aparecerem certos lá fora e os dois do rádio não, isso é o achado, e é o que este teste existe para pegar. E se não houver bateria à mostra em lugar nenhum, escreva «não há onde ler».

**Por controle.**

* **P1** — No cabo, e é testemunha. Não mexa nele. Anote o que a lista de fora diz sobre ele: ele é o controle de comparação — se o caminho do cabo mostra número e o do rádio não, a diferença é do rádio.
* **P2** — No cabo, e é a segunda testemunha. Mesma anotação. Dois do cabo dizendo número e dois do rádio mudos é uma resposta muito mais forte que um contra um.
* **P3** — No rádio, e é um dos dois que este teste mede. Anote o número no Hefesto, o que a dica diz do gamepad virtual dele, e o que a lista de fora mostra.
* **P4** — No rádio, e é o segundo que este teste mede. Mesma sequência. Se ele for o único mudo dos quatro, o problema é do quarto lugar na fila, não do rádio.

**A armadilha.** A PROVA DESTA LINHA PAROU NO MONTOU, e do lado do rádio ela parou antes ainda: a régua automática que vigia este caminho só exercita o CABO — o rádio não é tocado por teste nenhum desta casa. O que você anotar aqui é a primeira medição que existe desta metade, inclusive um «não há onde ler». A cilada é o valor de fábrica: sem dado, o Hefesto manda «cheio e carregando», então «100% carregando» no P3 e no P4 enquanto o Hefesto mostra os números deles caindo é o falso verde clássico — e é o resultado mais provável. Junte a isso o registro de bateria do gamepad virtual, que já foi medido dizendo «carregando» para sempre: o Hefesto deixou de lê-lo em 06/09, mas outro programa que o leia vê um número imóvel. Se a linha disser a máscara de Xbox, anote «máscara de Xbox» para aquele controle e siga só com o outro. Não compare o controle físico com ele mesmo: procure na lista o gamepad VIRTUAL, que é o que a dica do cartão lhe deu. E feche a Steam ao terminar: com ela aberta, um controle do rádio que se reconectar depois volta com a barra apagada.

---

## mapa-energia.bateria.leitura_hefesto-cabo — Bateria — leitura pelo Hefesto · cabo

*Célula:* `energia.bateria.leitura_hefesto @ cabo`

**O que isto prova.** Prova que o Hefesto está mesmo lendo a bateria dos dois controles do cabo, e que as três telas que mostram esse número dizem a mesma coisa.

**Onde olhar.** Em três lugares, e é a comparação entre eles que responde. Na aba Controles, nas linhas fechadas do quadro «Dispositivos conectados»: no fim da linha de cada controle vem a palavra Bateria, uma barrinha e o número em porcento. Na aba Jogar, no cartão de cada controle: «Sony», o «Player» e o número, a cor do plástico e USB ou BT, e embaixo um desenho de pilha com o número ao lado. Na aba Conexões, seção «Gestão de Controles» (abre clicando no título), na linha de cada controle: a palavra Bateria e o número — e a dica dessa palavra diz, com todas as letras, que o número vem da aba Controles. Um travessão no lugar do número não é zero: quer dizer que o Hefesto não conseguiu ler aquele controle.

**Os passos.**

* Abra a aba Controles.
1. Clique na linha do P3 para abrir o cartão dele, deixando as linhas do P1 e do P2 fechadas.
2. Confira que a linha do P1 e a do P2 dizem USB.
3. Anote o número de bateria do P1 e o do P2, e confira que nenhum dos dois mostra travessão no lugar do número.
4. Olhe a barrinha ao lado de cada número e confira que ela está cheia mais ou menos na proporção do número.
5. Na aba Jogar, anote o número que aparece ao lado do desenho de pilha no cartão do P1 e no do P2.
6. Na aba Conexões, clique no título «Gestão de Controles» e anote o número que aparece depois da palavra Bateria na linha do P1 e na do P2.
7. Compare os três números de cada controle: os três têm de ser iguais.
8. Volte à aba Controles.
9. Puxe o cabo do P1 e conte até dois.
10. Encaixe o cabo do P1 de novo.
11. Espere a linha do P1 voltar à lista, olhando a tela.
12. Leia o número de bateria do P1 assim que ele voltar.
13. Confira que a bateria do P2, do P3 e do P4 não piscou, não sumiu e não virou travessão nesse meio-tempo — siga os três pela cor do plástico.

**Passa quando.** O P1 e o P2 têm um número de bateria nas TRÊS abas, e os três números de cada um são o mesmo. Nenhum dos dois mostra travessão. E, depois de o cabo do P1 sair e voltar, ele reaparece na lista já com um número — não com travessão e não com a barrinha vazia —, sem você recarregar nada.

**Por controle.**

* **P1** — No cabo, e é nele que você mexe. Anote os três números dele, puxe o cabo, devolva-o em menos de trinta segundos e leia o número de novo quando ele voltar. É a prova de que o Hefesto LÊ o controle quando ele entra, em vez de repetir o que já estava na tela.
* **P2** — No cabo, e não se toca nele. Anote os três números dele. Enquanto o P1 sai e volta, a bateria do P2 não pode piscar, sumir nem virar travessão — se sumir junto, quem caiu não foi o P1, foi a leitura do cabo inteira.
* **P3** — No rádio, e é testemunha. Anote o número dele nas três abas antes e depois. Ele não pode mudar por causa do cabo do P1 ter saído.
* **P4** — No rádio, e é a segunda testemunha. Mesma conferência do P3. Se os dois do rádio virarem travessão quando o P1 sai do cabo, o achado é grande e vale anotar a hora exata.

**A armadilha.** A leitura em si já foi medida no aparelho, em 06/09, com estes quatro controles ligados — o que não foi medido é a escada de degraus, que é outro teste. Quatro números iguais e parados não são aprovação nem defeito: podem ser quatro controles no mesmo estado, e quem decide a escada é o teste dos degraus, com as duas leituras separadas por quarenta minutos. Os gamepads virtuais que o Hefesto cria têm registro de bateria próprio no sistema, que diz «carregando» para sempre; desde 06/09 o Hefesto deixou de lê-los, e o número destas três telas vem do próprio controle. Segunda armadilha: enquanto o P1 está fora, os outros três sobem um número na tela — é a ordem de conexão —, e cada um volta ao seu quando ele volta; é por isso que o passo 13 manda seguir pela cor do plástico. O P1 é o primeiro controle, e o posto dele fica guardado só por trinta segundos: devolva o cabo dentro desse tempo. Se o P1 já foi pareado por rádio nesta máquina, sem o cabo ele pode voltar pelo rádio — a linha dele passa a dizer BT, e aí você mediu outra coisa. E leia a bateria nas linhas fechadas: no cartão aberto o número do controle some do começo da linha, e é fácil anotar o número do controle errado.

---

## mapa-energia.bateria.leitura_hefesto-radio — Bateria — leitura pelo Hefesto · rádio

*Célula:* `energia.bateria.leitura_hefesto @ rádio`

**O que isto prova.** Prova que o Hefesto lê a bateria também dos dois controles do rádio, e que as três telas dizem o mesmo número.

**Onde olhar.** Nos mesmos três lugares do irmão do cabo. Na aba Controles, nas linhas fechadas do quadro «Dispositivos conectados»: no fim da linha de cada controle, a palavra Bateria, uma barrinha e o número. Na aba Jogar, no cartão de cada controle: o desenho de pilha com o número ao lado. Na aba Conexões, seção «Gestão de Controles» (abre clicando no título), na linha de cada controle: a palavra Bateria e o número. E a fita do topo, a linha que começa com «Selecionar:», onde cada controle é um chip — é por ela que você vê o P4 sair e voltar.

**Os passos.**

1. Abra a aba Controles.
2. Clique na linha do P1 para abrir o cartão dele, deixando as linhas do P3 e do P4 fechadas.
3. Confira que a linha do P3 e a do P4 dizem BT.
4. Anote o número de bateria do P3 e o do P4, e confira que nenhum dos dois mostra travessão no lugar do número.
5. Na aba Jogar, anote o número ao lado do desenho de pilha no cartão do P3 e no do P4.
6. Na aba Conexões, clique no título «Gestão de Controles» e anote o número depois da palavra Bateria na linha do P3 e na do P4.
7. Compare os três números de cada um: os três têm de ser iguais.
8. Volte à aba Controles.
9. Segure o botão PS do P4 até todas as luzes dele apagarem.
10. Solte o botão e confira que o chip do P4 saiu da fita do topo.
11. Dê um toque no botão PS do P4 para religá-lo, sem demorar.
12. Espere o chip do P4 voltar à fita, olhando a tela.
13. Leia o número de bateria do P4 assim que a linha dele voltar.
14. Confira que a bateria do P3 não sumiu nem virou travessão enquanto o P4 esteve fora.

**Passa quando.** O P3 e o P4 têm um número de bateria nas TRÊS abas, e os três números de cada um são o mesmo. Nenhum dos dois mostra travessão. E, depois de sair e voltar, o P4 reaparece já com um número — não com travessão —, sem você recarregar nada.

**Por controle.**

* **P1** — No cabo, e é testemunha. Não toque nele. Anote o número dele antes e depois: ele é a prova de que o Hefesto continuou lendo alguém enquanto o P4 estava fora.
* **P2** — No cabo, e é a segunda testemunha. Mesma anotação. Se os dois do cabo mostram número e os dois do rádio mostram travessão, o defeito é do RÁDIO, e é isso que este teste separa.
* **P3** — No rádio, e não se toca nele. Anote os três números. Enquanto o P4 está fora, a bateria do P3 não pode sumir nem virar travessão — vizinho de rádio caindo junto é o defeito que este teste procura.
* **P4** — No rádio, e é o único em que você toca. Anote os três números dele, desligue-o pelo PS longo, religue com um toque no PS e leia o número assim que ele voltar.

**A armadilha.** Pelo rádio o Hefesto só aceita a leitura depois de conferir o quadro que o controle mandou, e o pedaço da bateria fica UMA posição adiante da que fica no cabo. Isso foi medido no aparelho em 06/09, e o jeito como ele erra é conhecido: lendo na posição do cabo, o estado de carga sai como um valor que não existe no aparelho. Ou seja, o sintoma do defeito do rádio não é um número um pouco errado — é travessão, ou um estado de carga sem sentido. Segunda: os gamepads virtuais que o Hefesto cria têm registro de bateria próprio no sistema, que diz «carregando» para sempre; desde 06/09 o Hefesto não os lê, e o número destas três telas vem do próprio controle — quatro números iguais e parados não provam registro errado. Terceira: quem sai é o P4, e não o P3, de propósito — ele é o último da fila, e a saída dele não renumera ninguém; se o P3 saísse, o P4 subiria para 3 enquanto o outro estivesse fora, e isso é a ordem de conexão, não defeito. Quarta: a Steam tem de estar fechada quando o P4 volta — um controle que se conecta pelo rádio com ela aberta volta com a barra apagada. E segurar o PS por mais de um segundo não dispara nada no Hefesto; só o toque curto, com o controle ligado, abre a Steam.

---

## mapa-energia.bateria.percentual-cabo — Bateria — percentual e estado de carga · cabo

*Célula:* `energia.bateria.percentual @ cabo`

**O que isto prova.** Prova que o Hefesto diz, ao lado do número, o estado da carga do P1 e do P2 — e que esse estado é lido do aparelho, não deduzido de eles estarem no cabo.

**Onde olhar.** Na aba Controles, nas linhas fechadas do quadro «Dispositivos conectados». Logo depois do número em porcento aparece um iconezinho: um raio quando está carregando, um certo quando está cheio, um triângulo de atenção quando a carga deu problema. Passe o mouse nele e a dica escreve a palavra: Carregando, Cheio, Fora de faixa ou Erro de carga. Quando o controle está só gastando, NÃO aparece ícone nenhum — a ausência é a resposta, e é decisão dela: o número caindo já diz. No cartão aberto o número do controle some do começo da linha, por isso os passos abrem o cartão de um controle que não está sendo medido.

**Os passos.**

1. Abra a aba Controles.
2. Clique na linha do P3 para abrir o cartão dele, deixando as linhas do P1 e do P2 fechadas.
3. Confira que a linha do P1 e a do P2 dizem USB.
4. Anote o número de bateria do P1 e o do P2.
5. Passe o mouse no ícone que fica logo depois do número do P1 e anote a palavra da dica — sem ícone, escreva «sem ícone».
6. Faça o mesmo no ícone do P2.
7. Confira que a palavra combina com o número: Cheio só pode aparecer em 100%.
8. Anote se os dois disseram a mesma palavra ou palavras diferentes.
9. Puxe o cabo do P1 e conte até dois.
10. Encaixe o cabo do P1 de novo.
11. Espere a linha do P1 voltar à lista.
12. Passe o mouse no ícone do P1 outra vez e anote a palavra.
13. Confira que o P2, o P3 e o P4 não trocaram de ícone nem de número de bateria nesse meio-tempo — siga os três pela cor do plástico.

**Passa quando.** Cada um dos dois controles do cabo mostra um estado que combina com o número dele: Cheio só em 100%, Carregando num número abaixo de 100. Nenhum dos dois diz Carregando só por estar no cabo. E as duas testemunhas do rádio não ganham ícone nenhum nem mudam de número durante o teste.

**Por controle.**

* **P1** — No cabo, e é nele que você mexe. Leia a palavra da dica antes, puxe o cabo, devolva-o em menos de trinta segundos e leia a palavra de novo. Se ele estava em 100% e dizia Cheio, tem de continuar dizendo Cheio depois.
* **P2** — No cabo, e não se toca nele. Leia a palavra da dica dele e compare com a do P1. Os dois estão no mesmo transporte: se um diz Cheio e o outro diz Carregando, isso é LEITURA acontecendo, e é o melhor resultado que este teste pode dar.
* **P3** — No rádio, e é testemunha. Não pode ganhar ícone nenhum enquanto está só gastando. Se aparecer um raio no P3 sem cabo nenhum ligado nele, anote — é o estado saindo do controle errado.
* **P4** — No rádio, e é a segunda testemunha. Mesma conferência do P3: sem ícone, número parado ou caindo devagar.

**A armadilha.** A PROVA DESTA LINHA PAROU NO MONTOU: o percentual e o estado de carga são montados e mostrados, mas nunca foram acompanhados até o outro lado. Duas ciladas de leitura. A primeira: Fora de faixa e Erro de carga usam o MESMO ícone de atenção, e nesses dois casos o número ao lado é um número que o driver da máquina já jogou fora — ele não vale nada, por mais certo que pareça. Se você vir o triângulo, não anote o número como bom; anote a palavra. A segunda: não deduza a carga pelo cabo. Em 06/09 os DOIS controles do cabo diziam Cheio, e não Carregando — um produto que inferisse a carga do transporte estaria errado nos dois naquele instante, e foi essa medição que decidiu que carga e transporte são dois fatos separados. Por fim, enquanto o P1 está fora os outros três sobem um número — é a ordem de conexão, e cada um volta ao seu —, e o posto do P1, que é o primeiro controle, fica guardado só por trinta segundos. Se o P1 já foi pareado por rádio nesta máquina, sem o cabo ele pode voltar pelo rádio, e a linha dele passa a dizer BT: aí você mediu outra coisa.

---

## mapa-energia.bateria.percentual-radio — Bateria — percentual e estado de carga · rádio

*Célula:* `energia.bateria.percentual @ rádio`

**O que isto prova.** Prova que os dois controles do rádio não ganham ícone de carga enquanto só gastam, e que o ícone de carregando aparece se você puser um deles num carregador — sem ele deixar de falar por rádio.

**Onde olhar.** Na aba Controles, nas linhas fechadas do quadro «Dispositivos conectados». Logo depois do número em porcento fica o iconezinho de carga: raio para carregando, certo para cheio, triângulo para carga com problema. Passe o mouse nele e a dica escreve a palavra. Controle que só gasta não mostra ícone nenhum, de propósito. E olhe também a palavra depois da cor do plástico, no começo da linha: ela tem de continuar dizendo BT do começo ao fim deste teste.

**Os passos.**

1. Abra a aba Controles.
2. Clique na linha do P1 para abrir o cartão dele, deixando as linhas do P3 e do P4 fechadas.
3. Confira que a linha do P3 e a do P4 dizem BT, e que não há cabo nenhum encaixado neles.
4. Anote o número de bateria do P3 e o do P4.
5. Confira que nenhum dos dois mostra ícone depois do número.
6. Pegue um carregador de tomada, ou uma bateria portátil — nunca uma porta do PC.
7. Ligue o P3 nesse carregador.
8. Leia a linha do P3 e confira que ela continua dizendo BT.
9. Passe o mouse no ícone que apareceu depois do número do P3 e anote a palavra da dica.
10. Confira que o P4 continua sem ícone nenhum.
11. Tire o P3 do carregador.
12. Confira que o ícone do P3 sumiu de novo.

**Passa quando.** Com os dois só gastando, nem o P3 nem o P4 mostram ícone. Com o P3 no carregador, e a linha dele ainda dizendo BT, aparece o ícone de raio e a dica escreve Carregando. O P4 continua sem ícone o tempo todo, e o P3 volta a ficar sem ícone quando você tira o carregador.

**Por controle.**

* **P1** — No cabo, e é testemunha. Não toque nele. Anote a palavra da dica dele no começo e no fim: ligar um carregador no P3 não pode mudar nada no P1.
* **P2** — No cabo, e é a segunda testemunha. Mesma conferência. Se o ícone do P2 mudar quando você plugar o P3 no carregador, o estado está indo para o controle errado.
* **P3** — No rádio, e é o único em que você mexe. Sem ícone enquanto só gasta; com o carregador ligado, o ícone de raio e a palavra Carregando — e a linha dele continuando a dizer BT, que é o ponto inteiro deste teste.
* **P4** — No rádio, e não se toca nele. Sem cabo, sem carregador, sem ícone, do começo ao fim. Ele é a prova de que o raio que apareceu no P3 é do P3.

**A armadilha.** A PROVA DESTA LINHA PAROU NO MONTOU, e a metade que você vai medir aqui é INÉDITA: em 06/09 os quatro controles foram lidos no aparelho e nenhum dos dois do rádio estava carregando, então «carregando pelo rádio» nunca foi visto nesta casa. O que você anotar é a primeira prova que existe. Duas ciladas. A primeira é o carregador: se, ao ligá-lo, a linha do P3 trocar de BT para USB, o que você ligou não é um carregador — é uma porta que também fala dados, e o teste virou outro. Troque por um carregador de tomada ou uma bateria portátil e refaça. A segunda é o silêncio: um controle que só gasta NÃO mostra ícone, e isso não é campo faltando nem defeito — é decisão dela, porque o número caindo já conta a história. Anotar «não apareceu ícone» com os dois na mão e sem carregador é o resultado CERTO da primeira metade.

---

## mapa-energia.desligar-cabo — Desligar o controle por software · cabo

*Célula:* `energia.desligar @ cabo`

**O que isto prova.** Prova que o Hefesto não oferece nenhum jeito de desligar um controle do cabo pela tela, e que os três botões que parecem isso são outra coisa.

**Onde olhar.** Em três lugares, e nenhum dos três desliga controle do cabo. Na aba Sistema, o botão «Parar o serviço» — passe o mouse e a dica diz que o Hefesto deixa de rodar, que os controles viram gamepads comuns do Linux e que ele pergunta antes. Na aba Iluminação, o botão «Desligar» na linha «Opções» de cada coluna — a dica diz que ele apaga a barra de luz daquele controle. Na aba Conexões, seção «Gestão de Controles», dentro da linha aberta de um controle, o botão «A luz não acende» — no cabo ele fica apagado, e a dica diz que ele só vale no rádio. O único desligamento que existe hoje para o cabo é com o dedo, no botão PS do aparelho. Para acompanhar o que acontece, use a fita do topo que começa com «Selecionar:» e a contagem no alto à direita, que diz só os transportes que têm controle — «2 USB · 2 BT» com os quatro.

**Os passos.**

* Abra a aba Sistema.
1. Passe o mouse no botão «Parar o serviço», leia a dica e NÃO clique.
2. Na aba Iluminação, passe o mouse no botão «Desligar» da coluna do P1, na linha «Opções», leia a dica e NÃO clique.
3. Na aba Conexões, clique no título «Gestão de Controles», clique na linha do P1 para abri-la e passe o mouse no botão «A luz não acende» para ler a dica.
4. Percorra as dez abas e anote se existe, em alguma, um botão que prometa desligar um controle.
5. Anote os quatro chips da fita do topo e o que a contagem no alto à direita diz.
6. Segure o botão PS do P1, que está no cabo, até todas as luzes dele apagarem.
7. Solte o botão e deixe o P1 na mesa, com o cabo ainda encaixado.
8. Anote o que aconteceu com o aparelho: as luzes apagaram, ou não.
9. Olhe a fita do topo e anote se o chip do P1 saiu, e o que a contagem diz agora.
10. Se o P1 saiu, anote o número que cada um dos outros três mostra, reconhecendo cada um pela cor do plástico.
11. Se o P1 ficou apagado e fora da fita, dê um toque no botão PS dele para trazê-lo de volta, e confira que os quatro voltaram aos números de antes.

**Passa quando.** Nenhuma das dez abas oferece desligar um controle, e as três coisas parecidas se explicam sozinhas na dica: uma para o serviço inteiro, outra apaga a barra de luz, e a terceira só vale no rádio. O P1 responde ao PS longo com o cabo encaixado, e o que ele faz fica ANOTADO — apagou e voltou sozinho, ou apagou e ficou fora. Se ele saiu, os outros subiram um número durante a ausência e voltaram aos seus quando ele voltou.

**Por controle.**

* **P1** — No cabo, e é o único em que você toca. Segure o PS até as luzes apagarem, com o cabo encaixado, e anote o que acontece: se ele apaga, se sai da fita e se volta sozinho por causa do cabo. Não invente expectativa — o valor deste teste é o que você escrever aqui.
* **P2** — No cabo, e não se toca nele. É a testemunha do mesmo transporte: o chip dele não pode sair da fita quando o P1 apaga. Se os dois do cabo caírem juntos, o que caiu não foi o controle.
* **P3** — No rádio, e não se toca nele. Testemunha do outro transporte: chip na fita o tempo todo; o número dele pode subir enquanto o P1 está fora, e tem de voltar quando o P1 volta.
* **P4** — No rádio, e não se toca nele. Segunda testemunha, e é o último da fila. Confira o chip e o número dele antes, durante e depois.

**A armadilha.** NÃO CLIQUE em «Parar o serviço». Ele derruba o Hefesto inteiro e os quatro controles viram gamepads comuns do Linux; se clicar sem querer, ele pergunta antes — responda que não. Segurar o PS por mais de um segundo não dispara nada no Hefesto: o que abre a Steam é o toque CURTO no PS de um controle ligado, que é um atalho do produto. Por isso o passo 11 só toca o PS se o P1 estiver apagado; se a Steam abrir, feche-a por inteiro e refaça. Renumerar enquanto o P1 está fora é a ordem de conexão, e o posto do P1, que é o primeiro controle, fica guardado para ele só por trinta segundos. E não escreva «reprovou» porque não achou o botão: aqui a ausência é a resposta certa. Onde a prova parou: ninguém nesta casa localizou o comando de desligar por software, e ninguém mediu se ele existe — a faixa de perguntas que o aparelho responde foi varrida em 15/08 e nada de energia voltou, mas ESCREVER no aparelho para desligá-lo nunca foi tentado. O PS5 desliga este mesmo controle por software, então o caminho existe no aparelho; o que falta é o nosso conhecimento dele.

---

## mapa-energia.desligar-radio — Desligar o controle por software · rádio

*Célula:* `energia.desligar @ rádio`

**O que isto prova.** Prova que nenhuma aba do Hefesto oferece «desligar» um controle do rádio pelo nome, e mede o que acontece no aparelho pelos dois caminhos que tiram um controle do ar: o botão «A luz não acende», que derruba o controle do rádio, e o dedo no PS.

**Onde olhar.** Em três lugares da tela. Na aba Sistema, o botão «Parar o serviço» — a dica diz que o Hefesto deixa de rodar e que ele pergunta antes. Na aba Iluminação, o botão «Desligar» na linha «Opções» de cada coluna — a dica diz que ele apaga a barra de luz daquele controle. Na aba Conexões, seção «Gestão de Controles», dentro da linha aberta de um controle do rádio, o botão «A luz não acende» — a dica diz que ele derruba aquele controle do rádio e que o PS o traz de volta: é o único botão da tela que tira um controle do ar. Para acompanhar a saída e a volta, use a fita do topo que começa com «Selecionar:», a contagem no alto à direita («2 USB · 2 BT» com os quatro), e a linha «Modelo» da aba Iluminação, onde o lugar vazio diz o número e «Desconectado». No aparelho, olhe as cinco lâmpadas brancas em fileira embaixo do touchpad e a barra de luz.

**Os passos.**

* Abra a aba Sistema.
1. Passe o mouse no botão «Parar o serviço», leia a dica e NÃO clique.
2. Na aba Iluminação, passe o mouse no botão «Desligar» da coluna do P4, na linha «Opções», leia a dica e NÃO clique.
3. Percorra as dez abas e anote se existe, em alguma, um botão que prometa desligar um controle.
4. Anote os quatro chips da fita do topo e o que a contagem no alto à direita diz.
5. Na aba Conexões, clique no título «Gestão de Controles» e clique na linha do P4 para abri-la.
6. Passe o mouse no botão «A luz não acende» da linha do P4 e leia a dica.
7. Com o P4 na mão, clique em «A luz não acende».
8. Anote o que o P4 fez: todas as luzes apagaram, ou alguma ficou acesa ou piscando.
9. Confira que o chip do P4 saiu da fita e que a contagem passou a dizer «2 USB · 1 BT».
10. Confira que o P1, o P2 e o P3 continuam com os mesmos números.
11. Dê um toque no botão PS do P4 e confira que o chip dele voltou à fita com o número 4.
12. Agora pelo dedo: segure o botão PS do P4 até todas as luzes dele apagarem, e solte.
13. Na aba Iluminação, confira que a linha «Modelo» da coluna do P4 passou a dizer «Desconectado» e que a contagem voltou a «2 USB · 1 BT».
14. Dê um toque no botão PS do P4 e confira que ele voltou com o número 4.
15. Anote lado a lado o que o aparelho fez nos dois caminhos: o botão da tela e o dedo.

**Passa quando.** Nenhuma das dez abas oferece desligar um controle pelo nome, e os botões parecidos se explicam na dica: um para o serviço inteiro, outro apaga a barra de luz, e o «A luz não acende» derruba o controle do rádio. Pelos dois caminhos o P4 sai do ar: o chip sai da fita, a contagem cai para um BT e o lugar dele fica vazio, sem ninguém tomá-lo. O que o aparelho fez no clique da tela — apagou por inteiro ou ficou aceso procurando — fica ANOTADO, e é a resposta que esta linha não tinha. E ele volta com o número 4 nas duas vezes.

**Por controle.**

* **P1** — No cabo, e é testemunha. Não toque nele. Anote o número dele antes e depois: tirar um do rádio do ar não pode mexer em quem está no cabo.
* **P2** — No cabo, e é a segunda testemunha. Mesma conferência. Se um dos dois do cabo trocar de número enquanto o P4 está fora, anote a hora.
* **P3** — No rádio, e não se toca nele. É o vizinho de rádio do que sai, então é nele que uma bagunça aparece primeiro: confira o chip, o número e as cinco lâmpadas dele antes e depois.
* **P4** — No rádio, e é o único em que você toca. Primeiro pelo botão da tela, depois pelo dedo, e nas duas vezes religue com um toque no PS. Ele tem de voltar com o número 4.

**A armadilha.** NÃO CLIQUE em «Parar o serviço» — ele derruba o Hefesto inteiro; se clicar sem querer, ele pergunta antes, e é só responder que não. O «A luz não acende» derruba e NÃO religa: o Hefesto não reconecta sozinho, o PS é seu; se o botão da linha virar «Cancelar» enquanto espera, clicar nele só desiste da espera e não traz o controle de volta. Quem sai é o P4, e não o P3, de propósito: ele é o último da fila, e a saída dele não renumera ninguém; se o P3 saísse, o P4 subiria para 3 enquanto o outro estivesse fora — é a ordem de conexão, não defeito. A Steam tem de estar fechada: um controle que se conecta pelo rádio com ela aberta volta com a barra apagada, e fechar a Steam depois não cura. Segurar o PS por mais de um segundo não dispara nada no Hefesto; o toque CURTO no PS de um controle ligado abre a Steam, e por isso os toques de religar só vêm com o P4 apagado. Cuidado ao ler as cinco lâmpadas: elas não se contam da esquerda para a direita — o número é o CONJUNTO aceso. Jogador 1 é só a do meio; jogador 2 são a segunda e a quarta; jogador 3 são as duas pontas e a do meio; jogador 4 são as quatro pontas com a do meio apagada. Onde a prova parou: o comando de desligar por software nunca foi localizado nem medido nesta casa; a faixa de perguntas que o aparelho responde foi varrida em 15/08 e nada de energia voltou, e ESCREVER no aparelho para desligá-lo nunca foi tentado — no rádio, os degraus altos desse caminho nunca foram enviados a aparelho nenhum. O «A luz não acende» é outro mecanismo: ele corta a conversa pelo lado do computador, e o que o aparelho faz quando isso acontece é justamente o que o passo 8 mede pela primeira vez.

---

# entrada

---

## mapa-entrada.botoes-cabo — Botões digitais (A/B/X/Y, L/R, ZL/ZR, −, +, Home, Captura, L3/R3) + D-pad · cabo

*Célula:* `entrada.botoes @ cabo`

**O que isto prova.** Prova que cada botão de um controle ligado por cabo acende na tela do Hefesto quando você aperta, e acende só no cartão daquele controle.

**Onde olhar.** Na aba Controles. Clique no chip Todos, na fita do topo, para abrir os quatro cartões de uma vez: eles ficam na ordem P1, P2, P3 e P4, de cima para baixo, e o cabeçalho de cada um diz a cor e USB ou BT. Com os quatro abertos a aba rola — os de baixo se veem rolando. No meio de cada cartão fica a grade de dezesseis desenhos: Cruz, Círculo, Quadrado, Triângulo, as quatro direções do direcional, L1, R1, L2, R2, Share, Options, PS e Touchpad; apertar a peça acende o desenho dela. Os cliques dos analógicos não estão na grade: são as letras L3 e R3, dentro do círculo de cada analógico (Analógico esquerdo e Analógico direito), e elas ganham colchetes quando você aperta: [L3] e [R3]. O dedo apoiado no touchpad aparece no bloco Touchpad, à esquerda do cartão: um ponto e a palavra 1 toque. O botão do microfone não tem desenho; quem responde por ele é o selo ao lado da palavra Microfone, no bloco Microfone, que diz ATIVO, DESLIGADO ou um traço.

**Os passos.**

1. Clique na aba Controles.
2. Clique no chip Todos, na fita do topo.
3. Confira que há quatro cartões abertos, um por controle.
4. Confira que os cartões do P1 e do P2 dizem USB ao lado da cor, e os do P3 e do P4 dizem BT.
5. Deixe o P2, o P3 e o P4 parados e pegue só o P1.
6. Aperte cada uma das catorze peças do P1 que acendem na grade, uma por vez, segurando dois segundos antes de soltar: Cruz, Círculo, Quadrado, Triângulo, as quatro direções do direcional, L1, R1, L2, R2, Share e Options.
7. Confira, a cada peça, que o desenho dela acendeu no cartão do P1 e apagou quando você soltou.
8. Segure uma das peças e role a aba pelos cartões do P2, do P3 e do P4: nada pode ter acendido neles.
9. Aperte o PS do P1 e feche a Steam se ela vier para a frente.
10. Confira que o desenho do PS acendeu no cartão do P1.
11. Encoste um dedo no touchpad do P1 e confira que o bloco Touchpad do cartão dele mostrou o ponto e a palavra 1 toque.
12. Aperte o touchpad do P1 até estalar e anote se o desenho Touchpad da grade acendeu.
13. Aperte cada analógico do P1 para baixo até clicar, um de cada vez, e confira que L3 e R3 ganharam colchetes, cada um no clique do seu analógico.
14. Aperte o botão do microfone do P1 duas vezes, com uma pausa entre elas.
15. Confira que o selo do bloco Microfone do P1 trocou de palavra no primeiro aperto e voltou no segundo.
16. Largue o P1, pegue o P2 e refaça nele tudo, do Cruz ao botão do microfone.
17. Anote quais peças não acenderam, e em qual dos dois controles do cabo.

**Passa quando.** Nos dois controles do cabo, os quinze desenhos de peça da grade — todos menos o Touchpad — acendem quando você aperta e apagam quando solta; o dedo no touchpad acende o ponto do bloco Touchpad; L3 e R3 ganham colchetes no clique e os perdem ao soltar; e o selo do Microfone troca a cada aperto do botãozinho de mudo. Em nenhum momento um aperto no P1 acende alguma coisa no cartão do P2, do P3 ou do P4 — nem o contrário. O desenho Touchpad da grade, no clique, é anotado: acender ou não acender é a resposta que este teste traz.

**Por controle.**

* **P1** — No cabo, e é o primeiro a ser apertado inteiro: as peças uma por vez, com os outros três parados. Só o cartão dele pode reagir.
* **P2** — No cabo, e é o segundo a ser apertado inteiro. Enquanto você aperta o P1, ele é testemunha do próprio cabo: nada no cartão dele pode acender sozinho.
* **P3** — No rádio, e você não encosta nele em momento nenhum. É a testemunha de fora do cabo: se um aperto no P1 acender uma peça no cartão do P3, o Hefesto está misturando controles.
* **P4** — No rádio, e você também não encosta. Segunda testemunha: se o cartão dele mostrar um traço no lugar de L3 e R3, anote — é ausência de leitura, não botão solto.

**A armadilha.** Quatro. O PS sozinho, no controle que diz Navega o PC na aba Navegação, é a linha 6 da tabela Os gestos do controle — Abrir a Steam —, então ele acende o desenho e traz a Steam para a frente: feche-a e siga, não é defeito. Nos outros três controles o PS só acende o desenho. Segunda: o botão do microfone não tem desenho na grade, e procurar um faz você reprovar um produto correto — a resposta dele é o selo do bloco Microfone. Terceira: o dedo apoiado no touchpad não acende a grade, acende o ponto do bloco Touchpad; o clique, que estala, é outra coisa. Quarta, e é a que produz falso vermelho: um cartão com traço no lugar de L3 e R3 está dizendo que o Hefesto não conseguiu ler aquele controle. Cartão sem leitura mostra os gatilhos parados em 0 / 255 e os analógicos no meio, parados, o que se parece com um controle que ninguém está tocando. Antes de reprovar, aperte qualquer botão e veja se ALGUMA coisa naquele cartão se mexe; se nada se mexe nunca, o achado é a falta de leitura, e é isso que se anota.

---

## mapa-entrada.botoes-radio — Botões digitais (A/B/X/Y, L/R, ZL/ZR, −, +, Home, Captura, L3/R3) + D-pad · rádio

*Célula:* `entrada.botoes @ rádio`

**O que isto prova.** Prova que cada botão de um controle ligado por rádio acende na tela do Hefesto quando você aperta, e acende só no cartão daquele controle.

**Onde olhar.** Na aba Controles. Clique no chip Todos, na fita do topo, para abrir os quatro cartões de uma vez: eles ficam na ordem P1, P2, P3 e P4, de cima para baixo, e o cabeçalho de cada um diz a cor e USB ou BT. Com os quatro abertos a aba rola — os de baixo se veem rolando. No meio de cada cartão fica a grade de dezesseis desenhos: Cruz, Círculo, Quadrado, Triângulo, as quatro direções do direcional, L1, R1, L2, R2, Share, Options, PS e Touchpad. Os cliques dos analógicos são as letras L3 e R3, dentro do círculo de cada analógico, e ganham colchetes quando você aperta: [L3] e [R3]. O dedo no touchpad aparece no bloco Touchpad, à esquerda: um ponto e a palavra 1 toque. O botão do microfone responde pelo selo do bloco Microfone. E, no alto de qualquer aba, à direita, a contagem dos ligados: com os quatro na bancada ela diz 2 USB · 2 BT.

**Os passos.**

1. Clique na aba Controles.
2. Clique no chip Todos, na fita do topo, para abrir os quatro cartões.
3. Leia a contagem no alto, à direita, e anote o que ela diz.
4. Confira que os cartões do P3 e do P4 dizem BT ao lado da cor.
5. Deixe o P1, o P2 e o P4 parados e pegue só o P3.
6. Aperte o Cruz do P3, segure dois segundos e solte.
7. Confira que o desenho do Cruz acendeu no cartão do P3 e apagou quando você soltou.
8. Segure o Cruz de novo e role a aba pelos cartões do P1, do P2 e do P4: nada pode ter acendido neles.
9. Repita esse mesmo aperto, uma peça por vez, no Círculo, no Quadrado, no Triângulo, nas quatro direções do direcional, no L1, no R1, no L2, no R2, no Share, no Options e no PS do P3.
10. Confira, a cada peça, que só o desenho dela acendeu no cartão do P3.
11. Encoste um dedo no touchpad do P3 e confira o ponto e a palavra 1 toque no bloco Touchpad do cartão dele.
12. Aperte o touchpad do P3 até estalar e anote se o desenho Touchpad da grade acendeu.
13. Aperte até clicar cada um dos dois analógicos do P3, um por vez, e confira que L3 e R3 ganharam colchetes no clique.
14. Aperte o botão do microfone do P3 duas vezes, com uma pausa entre elas.
15. Confira que o selo do bloco Microfone do P3 trocou de palavra no primeiro aperto e voltou ao que estava no segundo.
16. Leia a contagem no alto de novo e confira que ela continua dizendo 2 USB · 2 BT.
17. Largue o P3, pegue o P4 e refaça nele tudo, do Cruz ao botão do microfone.
18. Anote se alguma peça deixou de acender, qual, e em qual dos dois controles do rádio.

**Passa quando.** Nos dois controles do rádio, os quinze desenhos de peça da grade — todos menos o Touchpad — acendem quando você aperta e apagam quando solta; o dedo no touchpad acende o ponto do bloco Touchpad; L3 e R3 ganham colchetes no clique; e o selo do Microfone troca a cada aperto. Em nenhum momento um aperto no P3 acende alguma coisa no cartão do P4, do P1 ou do P2. E a contagem do alto continua dizendo 2 USB · 2 BT do começo ao fim — sem isso, o que você mediu foi uma queda de conexão, não os botões.

**Por controle.**

* **P1** — No cabo, e você não encosta nele. É testemunha: se um aperto no P3 acender uma peça no cartão do P1, o Hefesto está misturando controles — e o defeito atravessou de um transporte para o outro, que é o pior caso.
* **P2** — No cabo, e você também não encosta. Segunda testemunha do cabo, com a mesma conferência do P1.
* **P3** — No rádio, e é o primeiro a ser apertado inteiro: as peças uma por vez, com os outros três parados.
* **P4** — No rádio, e é o segundo a ser apertado inteiro. Ele é o último a entrar na fila do Hefesto e o primeiro a ficar mudo quando alguma coisa desmonta — se três controles responderem e ele não, anote que o que falhou foi o quarto lugar da fila, e não o rádio.

**A armadilha.** Cinco. O PS sozinho só abre a Steam no controle que diz Navega o PC na aba Navegação; se ela vier para a frente, feche-a e siga — não é defeito. O botão do microfone não tem desenho na grade: quem responde por ele é o selo do bloco Microfone. Cartão que mostra um traço no lugar de L3 e R3 está dizendo que o Hefesto não leu aquele controle, e não que o botão está solto: os gatilhos ficam parados em 0 / 255 e os analógicos no meio, o que se parece com um controle largado. A que é só do rádio: se um cartão inteiro parar de responder no meio do teste, olhe a contagem no alto ANTES de reprovar — se ela passou a dizer 2 USB · 1 BT, o que caiu foi a conexão, e o teste se refaz do começo. E a que é do rádio com o microfone no ar: um desenho que acende sem dedo nenhum, com o selo do Microfone em ATIVO, é a entrada fantasma — o som do microfone lido como botão. Ela foi curada em 10/09; se voltar, anote qual desenho, em qual controle, e se o selo estava em ATIVO. O mapa desta casa prova que os botões chegam pelos dois caminhos; ele nunca mediu QUANDO chegam. Se um aperto responder com atraso visível, isso é achado — anote em qual controle e quantas vezes em quantas.

---

## mapa-entrada.bruta-cabo — Botões, sticks e gatilhos analógicos (entrada bruta) · cabo

*Célula:* `entrada.bruta @ cabo`

**O que isto prova.** Prova que o gatilho de um controle no cabo entrega o quanto ele foi apertado, e não apenas apertado ou solto.

**Onde olhar.** Na aba Controles, dentro do cartão de cada controle. À direita do cartão ficam três blocos — Giroscópio, Acelerômetro e Gatilhos —, e o último traz L2 e R2, cada um com uma barra e um número escrito na forma 0 / 255. No meio do cartão ficam Analógico esquerdo e Analógico direito, com X: e Y: em números, e a grade de desenhos, em que os de L2 e R2 acendem.

**Os passos.**

1. Ligue o P1 e o P2 pelo cabo e o P3 e o P4 pelo rádio.
2. Abra o Hefesto e clique na aba Controles.
3. Clique no chip Todos, na fita do topo, para abrir os quatro cartões.
4. Confira que os cartões do P1 e do P2 dizem USB ao lado da cor.
5. Deixe os quatro controles parados, sem encostar em gatilho nenhum.
6. Leia o bloco Gatilhos dos quatro cartões e confirme que os oito números estão perto de 0.
7. Pegue o P1.
8. Aperte o L2 do P1 bem devagar, um pouquinho por vez, até o fim do curso, acompanhando o número do L2 no bloco Gatilhos do cartão dele.
9. Confirme que ele passou por valores no meio do caminho, e não pulou de 0 direto para 255.
10. Confirme que ele chegou a 255 com o gatilho no fundo.
11. Repare em que altura do curso o desenho do L2 acendeu na grade.
12. Solte o L2 e confirme que o número voltou para perto de 0 e o desenho apagou.
13. Faça o mesmo com o R2 do P1.
14. Segure um gatilho do P1 apertado e role a aba pelos cartões do P2, do P3 e do P4: os números deles ficaram parados.
15. Largue o P1, pegue o P2 e refaça o L2 e o R2 do mesmo jeito.
16. Anote o maior número que cada gatilho alcançou, nos dois controles do cabo.

**Passa quando.** Nos dois controles do cabo, o número do gatilho sobe aos poucos com o dedo, passa por valores no meio do caminho, chega a 255 com o gatilho no fundo e volta para perto de 0 quando você solta. O desenho do gatilho na grade acende só depois que o número passa de 30 — não desde o primeiro milímetro. E os números dos cartões que você não está tocando ficam parados o tempo todo.

**Por controle.**

* **P1** — No cabo. Aperte o L2 e o R2 devagar, um de cada vez, e leia o número subindo no cartão dele. É o primeiro dos dois a medir.
* **P2** — No cabo. Mesma medição do P1, feita depois. Enquanto você aperta o P1, o número do P2 não pode se mexer — é a testemunha do próprio cabo.
* **P3** — No rádio, e você não encosta nele. Testemunha: se o número do gatilho dele andar enquanto o seu dedo está no P1, o Hefesto está lendo um controle e escrevendo no cartão de outro.
* **P4** — No rádio, e você também não encosta. Segunda testemunha, com a mesma conferência do P3.

**A armadilha.** Quatro. O número e o desenho aceso são duas coisas diferentes: o desenho só acende acima de 30, então existe um começo de curso em que o número já anda e o desenho ainda está apagado — isso é o produto certo, e quem esperar os dois juntos reprova sem haver defeito. Segunda: um gatilho que está duro na sua mão trava o número junto; é um efeito da aba Gatilhos guardado para aquele controle, e não a leitura quebrando — anote qual, e meça o outro. Terceira: um cartão que nunca leu aquele controle mostra os gatilhos parados em 0 / 255, exatamente como um gatilho solto; antes de reprovar, aperte o Cruz do mesmo controle e veja se o desenho dele acende — se nem isso acontece, o achado é a falta de leitura naquele cartão. Quarta, e é sobre o alcance desta prova: no mapa desta casa esta linha está provada só até o Hefesto MONTAR a leitura e pô-la na tela. Ninguém provou daqui para a frente que um jogo recebe esse número. Não peça ao jogo para reagir — a resposta deste teste é a tela.

---

## mapa-entrada.bruta-radio — Botões, sticks e gatilhos analógicos (entrada bruta) · rádio

*Célula:* `entrada.bruta @ rádio`

**O que isto prova.** Prova que o gatilho de um controle no rádio entrega o quanto ele foi apertado, e não apenas apertado ou solto.

**Onde olhar.** Na aba Controles, dentro do cartão de cada controle. À direita do cartão ficam três blocos — Giroscópio, Acelerômetro e Gatilhos —, e o último traz L2 e R2, cada um com uma barra e um número escrito na forma 0 / 255. No meio do cartão ficam Analógico esquerdo e Analógico direito, com X: e Y:, e a grade de desenhos, em que os de L2 e R2 acendem. E no alto de qualquer aba, à direita, a contagem dos ligados: 2 USB · 2 BT.

**Os passos.**

1. Ligue o P1 e o P2 pelo cabo e o P3 e o P4 pelo rádio.
2. Abra o Hefesto e clique na aba Controles.
3. Clique no chip Todos, na fita do topo, para abrir os quatro cartões.
4. Leia a contagem no alto, à direita, e anote o que ela diz.
5. Confira que os cartões do P3 e do P4 dizem BT ao lado da cor.
6. Deixe os quatro controles parados, sem encostar em gatilho nenhum.
7. Leia o bloco Gatilhos dos quatro cartões e confirme que os oito números estão perto de 0.
8. Pegue o P3.
9. Aperte o L2 do P3 bem devagar, um pouquinho por vez, até o fim do curso, acompanhando o número do L2 no bloco Gatilhos do cartão dele.
10. Confirme que ele passou por valores no meio do caminho, e não pulou de 0 direto para 255.
11. Confirme que ele chegou a 255 com o gatilho no fundo.
12. Repare em que altura do curso o desenho do L2 acendeu na grade.
13. Solte o L2 e confirme que o número voltou para perto de 0 e o desenho apagou.
14. Faça o mesmo com o R2 do P3.
15. Segure um gatilho do P3 apertado e role a aba pelos cartões do P1, do P2 e do P4: os números deles ficaram parados.
16. Leia a contagem no alto de novo e confirme que ela continua dizendo 2 USB · 2 BT.
17. Largue o P3, pegue o P4 e refaça o L2 e o R2 do mesmo jeito.
18. Anote o maior número que cada gatilho alcançou, nos dois controles do rádio.

**Passa quando.** Nos dois controles do rádio, o número do gatilho sobe aos poucos com o dedo, passa por valores no meio, chega a 255 no fundo do curso e volta para perto de 0 ao soltar — igualzinho ao que os dois do cabo fazem. O desenho do gatilho acende só depois que o número passa de 30. Os números dos cartões que você não está tocando ficam parados. E a contagem do alto continua dizendo 2 USB · 2 BT do começo ao fim.

**Por controle.**

* **P1** — No cabo, e você não encosta nele. Testemunha, e serve de referência: se o número do P3 nunca subir, aperte o L2 do P1 e veja se o dele sobe — assim você separa um defeito do rádio de um defeito da leitura inteira.
* **P2** — No cabo, e você também não encosta. Segunda testemunha do cabo, com a mesma conferência do P1.
* **P3** — No rádio. Aperte o L2 e o R2 devagar, um de cada vez, e leia o número subindo no cartão dele. É o primeiro dos dois a medir.
* **P4** — No rádio. Mesma medição do P3, feita depois. É o último da fila do Hefesto: se o número dele for o único que não anda, o achado é do quarto lugar, e não do rádio.

**A armadilha.** Cinco. O número e o desenho aceso são duas coisas: o desenho só acende acima de 30, então há um começo de curso em que o número já anda e o desenho ainda está apagado — produto certo. Um gatilho duro na sua mão trava o número junto: é um efeito da aba Gatilhos guardado para aquele controle, não a leitura. Cartão que nunca leu aquele controle mostra os gatilhos parados em 0 / 255, igual a um gatilho solto: antes de reprovar, aperte o Cruz do mesmo controle e veja se o desenho acende. Se um cartão inteiro parar de responder no meio, olhe a contagem no alto — se ela passou a dizer 2 USB · 1 BT, o que caiu foi a conexão, e o teste se refaz em vez de reprovar. E o alcance: no mapa desta casa esta linha está provada só até o Hefesto MONTAR a leitura e pô-la na tela; ninguém provou daqui para a frente que um jogo recebe esse número. Não peça ao jogo para reagir — a resposta é a tela.

---

## mapa-entrada.combo.ponte-cabo — Combo PS + R3 — a LEITURA do gesto que pede a próxima ponte · cabo

*Célula:* `entrada.combo.ponte @ cabo`

**O que isto prova.** Prova que segurar o PS e clicar o analógico direito, num controle ligado por cabo, troca o Modo — a forma como o jogo recebe o controle — e que só o controle que navega o PC faz isso.

**Onde olhar.** Em dois lugares. No aparelho: a barra de luz, as duas tiras ao lado do touchpad, pisca três vezes rápido, nos quatro controles, na cor do Modo que ficou de pé — verde é Xbox, laranja é Navegação e rosa é Sony DualSense — e depois volta à cor de cada jogador. Na tela: aba Jogar, quadro Modo, a fileira de quatro cartões (Sony DualSense, Xbox, Steam Input e Navegação), em que um fica aceso; e o Status, logo acima, que tem de estar em Ligado. Quem faz o gesto se lê na aba Navegação: nos cartões do alto, um diz Navega o PC e os outros dizem Só a janela. Na mesma aba, a tabela Os gestos do controle diz o que cada combinação faz: a linha 4, PS + R3, tem de dizer Próximo Modo.

**Os passos.**

1. Abra o Hefesto e clique na aba Jogar.
2. Confira que o Status está em Ligado.
3. Confira que o cartão aceso do quadro Modo é Sony DualSense; se não for, clique nele e espere a barra de luz piscar rosa.
4. Abra a aba Navegação.
5. Leia a linha de cada cartão do alto e ache o que diz Navega o PC.
6. Confira que a linha dele diz USB — é o P1 ou o P2; se disser BT, este teste não é este, é o do rádio.
7. Confira que a linha 4 da tabela Os gestos do controle, PS + R3, diz Próximo Modo.
8. Volte à aba Jogar.
9. Pegue na mão o controle que navega o PC.
10. Segure o botão PS dele e, sem soltar, aperte o analógico direito para baixo até clicar, mantendo os dois juntos por um segundo inteiro; solte os dois.
11. Anote a cor que a barra de luz piscou e qual cartão do quadro Modo acendeu.
12. Repita o mesmo gesto no mesmo controle mais duas vezes, anotando a cor e o cartão em cada uma.
13. Confira que na terceira volta o cartão aceso voltou a ser Sony DualSense.
14. Faça o mesmo gesto em cada um dos outros três controles, um por vez, sempre segurando por um segundo.
15. Confira que nenhum deles piscou a barra nem mudou o cartão aceso.
16. Anote o que aconteceu em cada uma das voltas, inclusive as voltas em que nada aconteceu.

**Passa quando.** Os três gestos no controle que diz Navega o PC andam o ciclo inteiro e voltam ao começo: primeiro a barra pisca verde e o cartão Xbox acende; depois laranja e Navegação; depois rosa e Sony DualSense. O mesmo gesto nos outros três controles não pisca nada e não muda o cartão aceso.

**Por controle.**

* **P1** — No cabo. Se for ele quem diz Navega o PC, é NELE que o gesto se faz, três vezes, e é a barra dele que você olha primeiro.
* **P2** — No cabo. Se o Navega o PC for do P2, o gesto é nele. Se não for, ele é testemunha do próprio cabo: o gesto feito nele não pode mudar nada.
* **P3** — No rádio, e é testemunha. Faça o gesto nele uma vez e confirme que nada muda — não é defeito, é o produto: o gesto sai de um controle só.
* **P4** — No rádio, e é a segunda testemunha. Mesmo gesto, mesma confirmação de que nada muda.

**A armadilha.** Seis, e as duas primeiras produzem falso vermelho. O gesto tem tempo: os dois botões têm de ficar segurados JUNTOS por mais de 0,15 s — um toque rápido conta como dois toques separados, e o PS sozinho abre a Steam. E o gesto sai de um controle só, o que diz Navega o PC; nos outros três ele não faz nada, e isso é o produto certo. Terceira: o cartão Steam Input NUNCA acende por este gesto, porque o ciclo passa só por Sony DualSense, Xbox e Navegação — quem esperar vê-lo aceso vai reprovar um teste bom. Quarta: a barra de luz pisca em TODOS os controles, e não só no que fez o gesto — ela diz que o gesto pegou, não quem o fez; dois pulsos vermelhos antes da cor querem dizer que há um jogo aberto e a troca pode derrubar o controle dentro dele, o que não deve acontecer aqui, com o jogo fechado. Quinta: o gesto grava o Modo no perfil ativo, e é por isso que as três voltas terminam em Sony DualSense; se você parar no meio, clique em Sony DualSense na aba Jogar antes de seguir. Na segunda volta o controle vira mouse e teclado — não encoste no analógico esquerdo, senão o cursor anda. Sexta, e é sobre o alcance: no mapa desta casa esta linha está provada só até o Hefesto DESPACHAR o gesto por dentro. Ninguém, até hoje, apertou PS mais analógico direito num controle de verdade e viu o Modo trocar. Este teste é exatamente o que fecha essa lacuna — anote tudo, inclusive o nada.

---

## mapa-entrada.combo.ponte-radio — Combo PS + R3 — a LEITURA do gesto que pede a próxima ponte · rádio

*Célula:* `entrada.combo.ponte @ rádio`

**O que isto prova.** Prova que segurar o PS e clicar o analógico direito, num controle ligado por rádio, troca o Modo — a forma como o jogo recebe o controle — e que só o controle que navega o PC faz isso.

**Onde olhar.** Em dois lugares. No aparelho: a barra de luz pisca três vezes rápido, nos controles ligados, na cor do Modo que ficou de pé — verde é Xbox, laranja é Navegação e rosa é Sony DualSense. Na tela: aba Jogar, quadro Modo, a fileira de quatro cartões (Sony DualSense, Xbox, Steam Input e Navegação), em que um fica aceso; e o Status, logo acima, em Ligado. Quem faz o gesto se lê na aba Navegação: nos cartões do alto, um diz Navega o PC e os outros dizem Só a janela, e cada cartão tem a cor do plástico do controle. Na mesma aba, a linha 4 da tabela Os gestos do controle, PS + R3, tem de dizer Próximo Modo.

**Os passos.**

1. Abra o Hefesto e clique na aba Jogar.
2. Confira que o Status está em Ligado e que o cartão aceso do quadro Modo é Sony DualSense; se não for, clique nele e espere a barra de luz piscar rosa.
3. Abra a aba Navegação.
4. Confira que a linha 4 da tabela Os gestos do controle, PS + R3, diz Próximo Modo.
5. Puxe o cabo do P1 e o cabo do P2.
6. Conte até cinco e leia os cartões do alto de novo.
7. Ache o cartão que diz Navega o PC e confira que a linha dele diz BT; se nenhum cartão com BT disser Navega o PC, pare aqui e anote — sem isso este teste não roda hoje, e essa é a resposta dele.
8. Anote a cor desse cartão: é por ela, e não pelo número, que você sabe qual controle pegar.
9. Volte à aba Jogar.
10. Pegue na mão o controle do rádio que navega o PC.
11. Segure o botão PS dele e, sem soltar, aperte o analógico direito para baixo até clicar; mantenha os dois juntos por um segundo inteiro e solte.
12. Anote a cor que a barra de luz piscou e qual cartão do quadro Modo acendeu.
13. Repita o mesmo gesto mais duas vezes no mesmo controle, anotando a cor e o cartão de cada vez.
14. Confira que na terceira vez o cartão aceso voltou a ser Sony DualSense.
15. Conte quantas vezes o gesto pegou de primeira e quantas você teve de repetir.
16. Faça o mesmo gesto no outro controle do rádio e confira que nada mudou nele: nem a barra de luz, nem o cartão aceso.
17. Encaixe os dois cabos de volta no P1 e no P2.
18. Confira na fita do topo que os dois voltaram com USB e com o número que tinham.
19. Abra a aba Navegação e leia quem diz Navega o PC: se ainda for um cartão com BT, segure o PS do P3 e do P4 até apagarem, espere meio minuto e ligue os dois de novo com um toque no PS — se a Steam vier para a frente, feche-a.

**Passa quando.** Os três gestos no controle do rádio que diz Navega o PC andam o ciclo inteiro e voltam ao começo: primeiro a barra pisca verde e o cartão Xbox acende; depois laranja e Navegação; depois rosa e Sony DualSense. O gesto no outro controle do rádio não muda nada. E cada gesto pega na primeira tentativa — se você tiver de repetir, anote quantas vezes em quantas: é isso que separa este caminho do caminho do cabo.

**Por controle.**

* **P1** — No cabo, e sai do teste: o cabo dele é puxado para que um controle do rádio assuma o Navega o PC. Enquanto ele está fora, os que ficam contam de 1 em diante na tela — o P3 aparece como P1 e o P4 como P2 —, e é por isso que o controle se reconhece pela cor. No fim, encaixe o cabo de volta e confirme que ele voltou como P1, com USB.
* **P2** — No cabo, e sai do teste pelo mesmo motivo do P1. No fim, encaixe o cabo de volta e confirme que ele voltou como P2, com USB.
* **P3** — No rádio. Se for ele quem passar a dizer Navega o PC, é nele que o gesto se faz, três vezes.
* **P4** — No rádio. Se o Navega o PC ficar com o P4, o gesto é nele; se ficar com o P3, o P4 é a testemunha — o gesto feito nele não pode mudar nada, e isso não é defeito.

**A armadilha.** Sete. O gesto tem tempo: os dois botões têm de ficar segurados JUNTOS por mais de 0,15 s — toque rápido conta como dois toques separados, e o PS sozinho abre a Steam. O gesto sai de um controle só, o que diz Navega o PC; nos outros ele não faz nada, e isso é o produto certo. O cartão Steam Input nunca acende por este gesto — o ciclo passa só por Sony DualSense, Xbox e Navegação. A barra de luz pisca em TODOS os controles, então ela diz que o gesto pegou, não quem o fez; dois pulsos vermelhos antes da cor só aparecem com um jogo aberto. O gesto grava o Modo no perfil ativo: se parar no meio, clique em Sony DualSense na aba Jogar. Sexta: um controle que perde o cabo pode voltar sozinho pelo rádio — o chip dele volta dizendo BT —, e aí ele mesmo serve: o que este teste pede é que quem navega esteja no BT; e quem assume o Navega o PC fica com ele, porque controle que volta depois de meio minuto entra no fim da fila — é por isso que o último passo existe. Sétima, e é a que este teste existe para pegar: o mapa desta casa registra que os dois botões CHEGAM pelo rádio, mas nunca mediu QUANDO chegam — se o gesto pegar às vezes e falhar outras, o achado é esse atraso contra os 0,15 s do combo, e ele só vale escrito com número: tantas vezes em tantas tentativas. O alcance: esta linha está provada só até o Hefesto despachar o gesto por dentro; ninguém apertou isto num controle de verdade até hoje.

---

## mapa-entrada.emulacao_mouse.analogico-cabo — Analogico como movimento do cursor (emulacao) · cabo

*Célula:* `entrada.emulacao_mouse.analogico @ cabo`

**O que isto prova.** Prova que, com um controle no cabo navegando o computador, o analógico esquerdo move o cursor e o direito rola a página.

**Onde olhar.** Na aba Navegação. Nos cartões do alto, um por controle, a linha diz USB • Navega o PC ou BT • Só a janela — só quem diz Navega o PC mexe no cursor. Em As opções de ativação: o Status do Modo, que tem de dizer Ligado, e, logo abaixo das opções, a frase verde Pronto para usar como mouse; Velocidade de cursor, de 1 a 12 (o padrão é 6), e Velocidade da rolagem, de 1 a 5 (o padrão é 1). No pé da aba, o botão Definições Controle e Mouse abre a tabela Botão do controle / O que ele faz: a linha L3 Direção tem de mostrar Movimento do cursor e a linha R3 Direção, Rolagem vertical e horizontal. A prova é o cursor andando na tela do computador — e, para a rolagem, deixe aberta antes de começar uma página longa, que precise rolar.

**Os passos.**

1. Clique na aba Jogar.
2. Clique no cartão Navegação, do quadro Modo, e espere a barra de luz piscar laranja.
3. Abra a aba Navegação.
4. Leia os cartões do alto e ache o que diz Navega o PC.
5. Confira que a linha dele diz USB — é o P1 ou o P2.
6. Leia o Status do Modo: ele tem de dizer Ligado; se disser Desligado, clique nele uma vez.
7. Confira que apareceu, em verde, a frase Pronto para usar como mouse.
8. Clique no botão Definições Controle e Mouse, no pé da aba.
9. Confira que a linha L3 Direção diz Movimento do cursor e a linha R3 Direção diz Rolagem vertical e horizontal, e feche a tabela no ×.
10. Empurre o analógico esquerdo do controle que navega o PC até o fim, um sentido de cada vez — direita, esquerda, cima e baixo —, soltando entre um e outro.
11. Confira que o cursor acompanha os quatro sentidos, e que ele para onde estava assim que você solta.
12. Anote o número da Velocidade da rolagem e arraste a barra dela até 5.
13. Empurre o analógico direito do mesmo controle até o fim para baixo, e depois até o fim para cima.
14. Confira que a página longa rolou para os dois lados.
15. Empurre os dois analógicos de cada um dos outros três controles, um por vez.
16. Confira que o cursor não anda e a página não rola com nenhum deles.
17. Desfaça o teste: devolva a Velocidade da rolagem ao número anotado, volte à aba Jogar e clique no cartão Sony DualSense.

**Passa quando.** O analógico esquerdo do controle do cabo que navega o PC leva o cursor pelos quatro sentidos, e o cursor para assim que você solta. O analógico direito rola a página nos dois sentidos. E os analógicos dos outros três controles não mexem no cursor nem rolam nada.

**Por controle.**

* **P1** — No cabo. Se for ele quem diz Navega o PC, é o analógico esquerdo dele que leva o cursor e o direito que rola a página.
* **P2** — No cabo. Se o Navega o PC for do P2, o teste é nele. Se não for, ele é testemunha do próprio cabo: os analógicos dele não podem mexer no cursor.
* **P3** — No rádio, e é testemunha. Empurre os dois analógicos dele e confira que o cursor não anda — não é defeito, é o produto: o cursor do PC é um só e sai de um controle só.
* **P4** — No rádio, e é a segunda testemunha. Mesmo empurrão, mesma conferência de que nada acontece.

**A armadilha.** Seis. Zona morta: o analógico esquerdo só começa a mover o cursor depois de um sexto do curso, e o direito só começa a rolar depois de quase um terço — o direito precisa de um empurrão bem maior que o esquerdo, e empurrão de leve nos dois parece analógico morto. A rolagem nasce na velocidade 1, a mais lenta que existe: antes de dizer que não rola, ponha a Velocidade da rolagem no 5. O cursor é um só e sai de um controle só, o que diz Navega o PC — os outros três não mexerem nele é o produto certo. Se o Status do Modo estiver cinza e a borda dele piscar em laranja quando você clica, o Modo ainda não é Navegação: o ? ao lado dele diz que o mouse e o teclado só se ligam fora do jogo — volte à aba Jogar e clique em Navegação. Entrar em Navegação derruba o controle virtual: com um jogo aberto ele perde os controles, e é por isso que a bancada começa sem jogo nenhum e o teste se desfaz no fim clicando Sony DualSense — o clique no cartão e a barra da rolagem gravam no perfil ativo, e deixar pela metade é deixar gravado. Não mexa na Navegação Interna: ela é sobre andar dentro da janela do Hefesto e não entra neste teste. E o mapa carrega uma observação dela de 11 de agosto dizendo que pelo rádio o analógico e o gatilho NÃO moviam o cursor, e que pelo cabo funcionavam; em 5 de setembro os dois caminhos foram medidos e responderam. Se hoje o cabo falhar, é defeito novo — anote com essa palavra.

---

## mapa-entrada.emulacao_mouse.analogico-radio — Analogico como movimento do cursor (emulacao) · rádio

*Célula:* `entrada.emulacao_mouse.analogico @ rádio`

**O que isto prova.** Prova que, com um controle no rádio navegando o computador, o analógico esquerdo move o cursor e o direito rola a página.

**Onde olhar.** Na aba Navegação. Nos cartões do alto, um por controle e na cor do plástico dele, a linha diz USB • Navega o PC, BT • Navega o PC ou BT • Só a janela — só quem diz Navega o PC mexe no cursor. Em As opções de ativação: o Status do Modo, que tem de dizer Ligado, e, logo abaixo das opções, a frase verde Pronto para usar como mouse; Velocidade de cursor, de 1 a 12 (o padrão é 6), e Velocidade da rolagem, de 1 a 5 (o padrão é 1). No pé da aba, o botão Definições Controle e Mouse abre a tabela em que a linha L3 Direção tem de mostrar Movimento do cursor e a linha R3 Direção, Rolagem vertical e horizontal. A prova é o cursor andando na tela do computador.

**Os passos.**

1. Clique na aba Jogar.
2. Clique no cartão Navegação, do quadro Modo, e espere a barra de luz piscar laranja.
3. Puxe o cabo do P1 e o cabo do P2.
4. Abra a aba Navegação, conte até cinco e leia os cartões do alto.
5. Ache o cartão que diz Navega o PC, confira que a linha dele diz BT e anote a cor dele; se nenhum cartão com BT disser Navega o PC, pare aqui e anote — é a resposta deste teste hoje, e não uma falha sua.
6. Leia o Status do Modo: ele tem de dizer Ligado; se disser Desligado, clique nele uma vez.
7. Confira que apareceu, em verde, a frase Pronto para usar como mouse.
8. Clique no botão Definições Controle e Mouse, confira que a linha L3 Direção diz Movimento do cursor e a R3 Direção diz Rolagem vertical e horizontal, e feche no ×.
9. Empurre o analógico esquerdo do controle do rádio que navega o PC até o fim, para cada um dos quatro lados, um de cada vez, soltando entre eles.
10. Confira que o cursor atravessa a tela para o lado de cada empurrão e que ele para onde estava assim que você solta.
11. Anote o número da Velocidade da rolagem, arraste a barra dela até 5 e abra uma página longa, que precise rolar.
12. Empurre o analógico direito do mesmo controle para baixo e depois para cima.
13. Confira que a página rola nos dois sentidos.
14. Empurre os dois analógicos do outro controle do rádio e confira que o cursor não anda e a página não rola.
15. Devolva a Velocidade da rolagem ao número anotado e, na aba Jogar, clique no cartão Sony DualSense.
16. Encaixe os dois cabos de volta no P1 e no P2 e confira na fita do topo que os dois voltaram com USB e com o número que tinham.
17. Abra a aba Navegação e leia quem diz Navega o PC: se ainda for um cartão com BT, segure o PS do P3 e do P4 até apagarem, espere meio minuto e ligue os dois de novo com um toque no PS — se a Steam vier para a frente, feche-a.

**Passa quando.** O analógico esquerdo do controle do rádio que navega o PC leva o cursor pelos quatro sentidos e o cursor para assim que você solta; o analógico direito rola a página nos dois sentidos. É a mesma resposta que o cabo dá, e é exatamente esse empate que este teste procura. O outro controle do rádio não mexe no cursor.

**Por controle.**

* **P1** — No cabo, e sai do teste: o cabo dele é puxado para que um controle do rádio assuma o Navega o PC. Enquanto ele está fora, os que ficam contam de 1 em diante na tela, e é pela cor que você reconhece cada um. No fim, encaixe o cabo de volta e confirme que ele voltou como P1, com USB.
* **P2** — No cabo, e sai do teste pelo mesmo motivo. No fim, encaixe o cabo de volta e confirme que ele voltou como P2, com USB.
* **P3** — No rádio. Se for ele quem passar a dizer Navega o PC, é o analógico esquerdo dele que leva o cursor e o direito que rola a página.
* **P4** — No rádio. Se o Navega o PC ficar com o P4, o teste é nele; se ficar com o P3, o P4 é a testemunha — os analógicos dele não podem mexer no cursor, e isso não é defeito.

**A armadilha.** Sete, e a última é o motivo de este teste existir. Zona morta: o analógico esquerdo só começa a mover o cursor depois de um sexto do curso, e o direito só começa a rolar depois de quase um terço — empurrão de leve parece analógico morto. A rolagem nasce na velocidade 1, a mais lenta: ponha a Velocidade da rolagem no 5 antes de dizer que não rola. O cursor é um só e sai de um controle só — o outro do rádio não mexer nele é o produto certo. Se o Status do Modo estiver cinza e a borda dele piscar em laranja quando você clica, o Modo ainda não é Navegação — volte à aba Jogar e clique em Navegação. Um controle que perde o cabo pode voltar sozinho pelo rádio, com o chip dizendo BT; se for ele que passar a dizer Navega o PC, ele serve — o que se pede é que quem navega esteja no BT. Quem assume o Navega o PC fica com ele, porque controle que volta depois de meio minuto entra no fim da fila — é por isso que o último passo existe. E a sétima: o mapa carrega uma observação dela de 11 de agosto dizendo que pelo rádio o analógico e o gatilho NÃO moviam o cursor, e que pelo cabo funcionavam; em 5 de setembro os dois caminhos foram medidos e responderam. Se hoje o rádio falhar, é aquele defeito de volta — e é o achado mais valioso desta linha.

---

## mapa-entrada.emulacao_mouse.gatilhos-cabo — Gatilhos L2/R2 como botao do mouse (emulacao) · cabo

*Célula:* `entrada.emulacao_mouse.gatilhos @ cabo`

**O que isto prova.** Prova que, com um controle no cabo navegando o computador, o L2 clica como o botão esquerdo do mouse e o R2 como o botão direito.

**Onde olhar.** Na aba Navegação. Nos cartões do alto, um por controle, a linha diz USB • Navega o PC ou BT • Só a janela — só quem diz Navega o PC mexe no cursor. Em As opções de ativação, o Status do Modo tem de dizer Ligado, e logo abaixo das opções tem de aparecer, em verde, a frase Pronto para usar como mouse. No pé da aba, o botão Definições Controle e Mouse abre a tabela Botão do controle / O que ele faz, em que a linha L2 tem de mostrar Botão esquerdo e a linha R2, Botão direito. A prova, porém, é na tela do computador: o clique tem de acontecer.

**Os passos.**

1. Clique na aba Navegação.
2. Leia os cartões do alto e ache o que diz Navega o PC.
3. Confira que a linha dele diz USB — é o P1 ou o P2; se disser BT, este teste não é este, é o do rádio.
4. Abra a aba Jogar e clique no cartão Navegação, do quadro Modo; espere a barra de luz piscar laranja.
5. Volte à aba Navegação e leia o Status do Modo: ele tem de dizer Ligado; se disser Desligado, clique nele uma vez.
6. Confira que apareceu, em verde, a frase Pronto para usar como mouse.
7. Clique no botão Definições Controle e Mouse, no pé da aba.
8. Confira que a linha L2 diz Botão esquerdo e a linha R2 diz Botão direito, e feche a tabela no ×.
9. Abra uma pasta de arquivos e deixe-a na frente da tela, com o cursor em cima de um arquivo.
10. Aperte o L2 do controle que navega o PC até o fundo do curso.
11. Confira que o arquivo ficou selecionado, como num clique do botão esquerdo.
12. Aperte o R2 do mesmo controle até o fundo do curso.
13. Confira que abriu o menu do botão direito, e feche o menu.
14. Aperte o L2 e o R2 de cada um dos outros três controles, um por vez, sempre até o fundo.
15. Confira que nenhum deles clicou nada.
16. Volte à aba Jogar e clique no cartão Sony DualSense, para desfazer o teste.

**Passa quando.** O L2 do controle do cabo que navega o PC seleciona o arquivo, como o botão esquerdo do mouse, e o R2 abre o menu do botão direito. Os gatilhos dos outros três controles não clicam nada. E as duas linhas da tabela dizem, antes disso, Botão esquerdo e Botão direito.

**Por controle.**

* **P1** — No cabo. Se for ele quem diz Navega o PC, é nele que o L2 e o R2 são apertados até o fundo, e é o clique dele que decide este teste.
* **P2** — No cabo. Se o Navega o PC for do P2, o teste é nele. Se não for, ele é testemunha do próprio cabo: o L2 e o R2 dele não podem clicar nada.
* **P3** — No rádio, e é testemunha. Aperte o L2 e o R2 dele até o fundo e confirme que o cursor não clica — não é defeito, é o produto: o cursor do PC é um só, e sai de um controle só.
* **P4** — No rádio, e é a segunda testemunha. Mesmo aperto, mesma confirmação de que nada acontece.

**A armadilha.** Cinco. O gatilho tem de passar de um quarto do curso: abaixo disso o Hefesto não conta como aperto, e meia pressão parece gatilho morto. Só um controle mexe no cursor, e a tela diz qual — os outros três não clicarem é o produto certo, e é justamente a testemunha deste teste, não a reprovação dele. Entrar em Navegação derruba o controle virtual: com um jogo aberto ele perde os controles, e é por isso que a bancada começa sem jogo nenhum aberto e o teste se desfaz no fim clicando Sony DualSense — o clique no cartão grava o Modo no perfil ativo. Se o Status do Modo estiver cinza e a borda dele piscar em laranja quando você clica, o Modo ainda não é Navegação: o ? ao lado dele diz que o mouse e o teclado só se ligam fora do jogo — troque no quadro Modo da aba Jogar antes de insistir. E a que dá o nome a este teste: o mapa carrega uma observação dela de 11 de agosto dizendo que pelo rádio o gatilho e o analógico NÃO moviam o cursor, e que pelo cabo funcionavam; em 5 de setembro os dois caminhos foram medidos e responderam. Se hoje falhar, é aquele defeito de volta — anote em qual transporte, porque é isso que o mapa está esperando.

---

## mapa-entrada.emulacao_mouse.gatilhos-radio — Gatilhos L2/R2 como botao do mouse (emulacao) · rádio

*Célula:* `entrada.emulacao_mouse.gatilhos @ rádio`

**O que isto prova.** Prova que, com um controle no rádio navegando o computador, o L2 clica como o botão esquerdo do mouse e o R2 como o botão direito.

**Onde olhar.** Na aba Navegação. Nos cartões do alto, um por controle e na cor do plástico dele, a linha diz se ele está no USB ou no BT e se Navega o PC ou fica Só a janela — só quem diz Navega o PC mexe no cursor. Em As opções de ativação, o Status do Modo tem de dizer Ligado, e logo abaixo das opções tem de aparecer, em verde, a frase Pronto para usar como mouse. No pé da aba, o botão Definições Controle e Mouse abre a tabela em que a linha L2 tem de mostrar Botão esquerdo e a linha R2, Botão direito. A prova é na tela do computador: o clique tem de acontecer.

**Os passos.**

1. Clique na aba Jogar.
2. Clique no cartão Navegação, do quadro Modo, e espere a barra de luz piscar laranja.
3. Puxe o cabo do P1 e o cabo do P2.
4. Abra a aba Navegação, conte até cinco e leia os cartões do alto.
5. Ache o cartão que diz Navega o PC, confira que a linha dele diz BT e anote a cor dele; se nenhum cartão com BT disser Navega o PC, pare aqui e escreva exatamente isso — é a resposta deste teste hoje, e não uma falha sua.
6. Leia o Status do Modo: ele tem de dizer Ligado; se disser Desligado, clique nele uma vez.
7. Confira que apareceu, em verde, a frase Pronto para usar como mouse.
8. Clique no botão Definições Controle e Mouse, confira que a linha L2 diz Botão esquerdo e a R2 diz Botão direito, e feche no ×.
9. Abra uma pasta de arquivos e leve o cursor até cima de um arquivo.
10. Aperte o L2 do controle do rádio que navega o PC, até o fundo do curso.
11. Confira que o arquivo ficou selecionado, como num clique do botão esquerdo.
12. Aperte o R2 do mesmo controle até o fundo do curso e confira que abriu o menu do botão direito; feche o menu.
13. Aperte o L2 e o R2 do OUTRO controle do rádio e confira que ele não clica nada — isso é o produto certo, e não defeito.
14. Volte à aba Jogar e clique no cartão Sony DualSense.
15. Encaixe os dois cabos de volta no P1 e no P2 e confira na fita do topo que os dois voltaram com USB e com o número que tinham.
16. Abra a aba Navegação e leia quem diz Navega o PC: se ainda for um cartão com BT, segure o PS do P3 e do P4 até apagarem, espere meio minuto e ligue os dois de novo com um toque no PS — se a Steam vier para a frente, feche-a.

**Passa quando.** O L2 do controle do rádio que navega o PC seleciona o arquivo, como o botão esquerdo do mouse, e o R2 abre o menu do botão direito — a mesma resposta que o cabo dá. O outro controle do rádio não clica nada. E as duas linhas da tabela dizem, antes disso, Botão esquerdo e Botão direito.

**Por controle.**

* **P1** — No cabo, e sai do teste: o cabo dele é puxado para que um controle do rádio assuma o Navega o PC. Enquanto ele está fora, os que ficam contam de 1 em diante na tela, e é pela cor que você reconhece cada um. No fim, encaixe o cabo de volta e confirme que ele voltou como P1, com USB.
* **P2** — No cabo, e sai do teste pelo mesmo motivo. No fim, encaixe o cabo de volta e confirme que ele voltou como P2, com USB.
* **P3** — No rádio. Se for ele quem passar a dizer Navega o PC, é nele que o L2 e o R2 são apertados até o fundo.
* **P4** — No rádio. Se o Navega o PC ficar com o P4, o teste é nele; se ficar com o P3, o P4 é a testemunha — o L2 e o R2 dele não podem clicar nada, e isso não é defeito.

**A armadilha.** Este teste passa do tamanho de sempre porque ele desmonta a bancada e a monta de volta: puxar os dois cabos é o jeito de um controle do rádio assumir o cursor, e a ida e a volta do Modo são dois cliques que não se cortam — cortar a volta deixa o Modo em Navegação, gravado no perfil ativo, sem controle virtual. Seis cuidados, e o último é o motivo de este teste existir. O gatilho tem de passar de um quarto do curso; abaixo disso o Hefesto não conta como aperto. Só um controle mexe no cursor — o outro do rádio não clicar é o produto certo. Entrar em Navegação derruba o controle virtual, e por isso o jogo tem de estar fechado antes de começar. Se o Status do Modo estiver cinza e a borda dele piscar em laranja quando você clica, o Modo ainda não é Navegação — troque no quadro Modo da aba Jogar. Um controle que perde o cabo pode voltar sozinho pelo rádio, com o chip dizendo BT; se for ele que passar a dizer Navega o PC, ele serve. Quem assume o Navega o PC fica com ele, porque controle que volta depois de meio minuto entra no fim da fila — é por isso que o último passo existe. E a sexta: o mapa carrega uma observação dela de 11 de agosto dizendo que pelo rádio o gatilho e o analógico NÃO moviam o cursor, e que pelo cabo funcionavam; em 5 de setembro os dois caminhos foram medidos e responderam. Se hoje o rádio falhar, é aquele defeito de volta, e é o achado mais valioso desta linha.

---

## mapa-entrada.stick-cabo — Sticks analógicos (dois eixos por stick) · cabo

*Célula:* `entrada.stick @ cabo`

**O que isto prova.** Prova que os dois analógicos de um controle no cabo entregam a posição real do polegar, e que o repouso deles é lido do aparelho em vez de inventado.

**Onde olhar.** Na aba Controles, no meio do cartão de cada controle. Ficam ali Analógico esquerdo, com a marca L3 dentro do círculo, e Analógico direito, com a marca R3. Cada um tem um círculo com um pontinho dentro e dois números embaixo: X: e Y:. O pontinho anda dentro do círculo acompanhando o polegar, e cada número vai de 0 a 255.

**Os passos.**

1. Clique na aba Controles.
2. Clique no chip Todos, na fita do topo, para abrir os quatro cartões.
3. Deixe os quatro controles parados, sem encostar em analógico nenhum.
4. Leia e anote num papel os quatro números de repouso do P1 — X e Y do esquerdo, X e Y do direito — e depois os quatro do P2, do mesmo jeito.
5. Empurre o analógico esquerdo do P1 devagar até o fim, um sentido de cada vez — direita, esquerda, cima e baixo —, soltando entre um e outro.
6. Confira que o número X vai a um extremo num lado e ao outro extremo no lado oposto, e que o Y faz o mesmo em cima e embaixo.
7. Confira que o pontinho encosta na borda do círculo do mesmo lado para onde o seu polegar foi, e volta ao meio quando você solta.
8. Confira que, ao soltar, os dois números voltam para perto do que você anotou.
9. Empurre o analógico direito do P1 do mesmo jeito, um sentido de cada vez.
10. Confira nele as mesmas três coisas que conferiu no analógico esquerdo.
11. Segure um analógico do P1 empurrado e role a aba pelos cartões do P2, do P3 e do P4: os pontinhos deles ficaram parados.
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

**A armadilha.** A maior é esperar 128 no repouso. O centro NÃO é 128, e isso está medido nesta bancada: os centros ficam entre 124 e 130, cada aparelho tem o seu, e um deles ainda passeia um ponto ao longo de minutos. Quem reprovar porque não voltou para 128 reprova um produto certo — e o Hefesto foi consertado justamente para LER o repouso do aparelho em vez de escrever 128. A segunda é o contrário e é mais perigosa: um cartão sem leitura mostra os dois analógicos exatamente no meio e parados para sempre, e um número plausível e congelado se parece com um controle que ninguém está tocando. A diferença se vê apertando o Cruz do mesmo controle: se o desenho do Cruz acende e o analógico continua parado, o achado é do analógico; se nada acende, o achado é a falta de leitura naquele cartão. E não confunda com o pontinho do touchpad, que fica no bloco Touchpad, à esquerda, e só aparece quando há dedo encostado.

---

## mapa-entrada.stick-radio — Sticks analógicos (dois eixos por stick) · rádio

*Célula:* `entrada.stick @ rádio`

**O que isto prova.** Prova que os dois analógicos de um controle no rádio entregam a posição real do polegar, e que o repouso deles é lido do aparelho em vez de inventado.

**Onde olhar.** Na aba Controles, no meio do cartão de cada controle. Ficam ali Analógico esquerdo, com a marca L3 dentro do círculo, e Analógico direito, com a marca R3. Cada um tem um círculo com um pontinho dentro e dois números embaixo: X: e Y:. O pontinho anda dentro do círculo acompanhando o polegar, e cada número vai de 0 a 255. E no alto de qualquer aba, à direita, a contagem dos ligados: 2 USB · 2 BT.

**Os passos.**

1. Abra o Hefesto e clique na aba Controles.
2. Clique no chip Todos, na fita do topo, para abrir os quatro cartões.
3. Leia a contagem no alto, à direita, e anote o que ela diz.
4. Deixe os quatro controles parados, sem encostar em analógico nenhum, e anote num papel os quatro números de repouso do P3 e os quatro do P4: X e Y do esquerdo, X e Y do direito.
5. Pegue o P3 e empurre o analógico esquerdo devagar até o fim, para um lado e depois para o outro, acompanhando o número X.
6. Confira que o número X foi a um extremo de cada vez e que o pontinho encostou na borda do círculo do mesmo lado do seu polegar.
7. Empurre o mesmo analógico até o fim para cima e depois até o fim para baixo, acompanhando o número Y.
8. Confira que o número Y foi aos dois extremos.
9. Solte o analógico.
10. Confira que o pontinho voltou ao meio e que os dois números voltaram para perto do que você anotou.
11. Repita esses mesmos três gestos com o analógico DIREITO do P3: os dois lados, cima e baixo, e soltar.
12. Segure um analógico do P3 empurrado e role a aba pelos cartões do P1, do P2 e do P4: os pontinhos deles têm de ficar parados.
13. Largue o P3, pegue o P4 e refaça nele os dois analógicos do mesmo jeito.
14. Leia a contagem no alto de novo: ela tem de continuar dizendo 2 USB · 2 BT.

**Passa quando.** Empurrando um analógico até um extremo, o número daquele eixo vai até perto de 0 de um lado e perto de 255 do outro, e o pontinho encosta na borda do círculo do mesmo lado para onde o seu polegar foi. Soltando, o pontinho volta ao meio e os números voltam para o que você anotou. Isso nos dois analógicos do P3 e nos dois do P4 — sem atraso visível entre o polegar e o pontinho. E a contagem do alto continua dizendo 2 USB · 2 BT do começo ao fim. Se algum eixo não alcançar os extremos, anote qual é ele e em qual dos dois controles do rádio: é esse o achado que o teste devolve.

**Por controle.**

* **P1** — No cabo, e você não encosta nele. Testemunha, e referência: se o pontinho do P3 não andar, mexa no analógico do P1 e veja se o dele anda — assim você separa um defeito do rádio de um defeito da leitura inteira.
* **P2** — No cabo, e você também não encosta. Segunda testemunha do cabo, com a mesma conferência do P1.
* **P3** — No rádio. Anote os quatro números de repouso dele ANTES de tocar em qualquer coisa, e compare no fim. Os dois analógicos vão aos extremos, um eixo de cada vez.
* **P4** — No rádio. Mesma medição do P3, feita depois. É o último da fila do Hefesto: se o pontinho dele for o único parado, o achado é do quarto lugar, e não do rádio.

**A armadilha.** A maior é esperar 128 no repouso. O centro NÃO é 128, e isso está medido nesta bancada nos dois transportes: os centros ficam entre 124 e 130, cada aparelho tem o seu, e um deles passeia um ponto ao longo de minutos. Reprovar porque não voltou para 128 é reprovar um produto certo. A segunda: cartão sem leitura mostra os dois analógicos exatamente no meio e parados para sempre — um número plausível e congelado se parece com um controle largado. A diferença se vê apertando o Cruz do mesmo controle: se o Cruz acende e o analógico não anda, o achado é do analógico; se nada acende, é falta de leitura. Terceira, só do rádio: se um cartão inteiro parar no meio do teste, olhe a contagem no alto antes de reprovar — 2 USB · 1 BT quer dizer que a conexão caiu, e o teste se refaz. Quarta, também do rádio: com o microfone do controle no ar, um pontinho que pula sozinho, sem polegar nenhum, é a entrada fantasma — o som do microfone lido como analógico; ela foi curada em 10/09, e se voltar é achado: anote em qual controle. E não confunda com o pontinho do touchpad, que fica no bloco Touchpad, à esquerda, e só aparece com dedo encostado.

---

## mapa-gatilho.adaptativo-cabo — Gatilhos adaptativos (resistência por zona) — os dois · cabo

*Célula:* `gatilho.adaptativo @ cabo`

**O que isto prova.** Prova que o L2 e o R2 do mesmo controle ficam duros AO MESMO TEMPO nos dois controles do cabo, sem um lado apagar o outro.

**Onde olhar.** Na aba Gatilhos, no quadro Gatilhos. Cada controle é uma coluna, com o chip dele no alto: o número, a cor do plástico e USB ou BT. A coluna da esquerda nomeia as linhas: primeiro Controle e depois duas seções, cada uma titulada por um desenho — o de cima é o L2, o de baixo é o R2 —, com Modo e Efeito pronto dentro de cada uma. Mas quem responde este teste é a sua mão, e não a tela: o DualSense não devolve em que efeito ele está, então o campo Modo mostra o que foi PEDIDO, nunca o que está no aparelho. O único sinal que a tela dá é o campo piscar em verde por cerca de um segundo e meio quando o comando chega ao controle — e piscar quer dizer que o comando saiu daqui, não que o gatilho está duro agora.

**Os passos.**

1. Abra a aba Gatilhos.
2. Confira que o chip no alto da coluna do P1 e o da coluna do P2 dizem USB.
3. Anote no papel o que está escrito no Modo das duas seções da coluna do P1 e das duas da coluna do P2 — é o que você devolve no fim.
4. Escolha «Desligado» no Modo das duas seções da coluna do P1 e das duas da coluna do P2.
5. Aperte o L2 e o R2 dos quatro controles até o fundo, um controle por vez, e guarde na mão como cada um está agora: os do P1 e do P2 têm de estar leves.
6. Escolha «Rígido» no Modo da seção de CIMA (a do desenho L2), na coluna do P1, e veja o campo piscar em verde.
7. Aperte o L2 do P1 e depois o R2 do mesmo controle, um de cada vez.
8. Confira que o L2 trava duro do começo ao fim do curso e que o R2 continua leve — o efeito pegou um lado só.
9. Escolha «Rígido» no Modo da seção de BAIXO (a do desenho R2), na mesma coluna do P1.
10. Aperte o L2 e o R2 do P1 ao mesmo tempo, com dois dedos; depois solte e aperte de novo um de cada vez.
11. Confira que os dois estão duros e que nenhum amoleceu quando o outro foi ligado.
12. Repita na coluna do P2 tudo o que você fez na do P1, do «Rígido» no L2 até os dois gatilhos apertados juntos.
13. Aperte o L2 e o R2 do P3 e depois os do P4, e compare com o que guardou na mão: os quatro têm de estar iguais ao que estavam.
14. Devolva o Modo das duas seções da coluna do P1 e das duas da coluna do P2 ao que você anotou no papel.

**Passa quando.** No P1 e no P2 — os dois do cabo — o L2 e o R2 ficam duros ao mesmo tempo, e continuam duros quando você aperta um de cada vez: ligar o segundo lado não soltou o primeiro. Os gatilhos do P3 e do P4 continuam exatamente como estavam antes, nenhum endureceu. E, com «Desligado» nas duas seções, os quatro gatilhos do P1 e do P2 estavam leves na sua mão antes do «Rígido».

**Por controle.**

* **P1** — No CABO, e é o primeiro em que você mexe. Ponha «Rígido» no Modo da seção de cima (L2), sinta só o L2 travar, depois ponha «Rígido» na seção de baixo (R2) e sinta os dois travados ao mesmo tempo, com dois dedos.
* **P2** — No CABO, e é o segundo. Os mesmos gestos, na coluna dele. Ele é quem separa "o cabo funciona" de "aquele controle funciona": se der certo no P1 e não no P2, o defeito é do aparelho, não do transporte.
* **P3** — No RÁDIO, testemunha. Não toque na coluna dele. Aperte o L2 e o R2 antes e depois; têm de estar iguais nas duas vezes. Se ele endurecer junto, o comando pegou todo mundo em vez do controle escolhido.
* **P4** — No RÁDIO, segunda testemunha. Não toque na coluna dele. Aperte o L2 e o R2 antes e depois. Se o P3 ficou intacto e o P4 endureceu, o comando não vazou pelo transporte — foi parar no controle errado, que é outro defeito.

**A armadilha.** Não use «Desligado» como o efeito do teste. Ele é a escolha que SOLTA o gatilho: se ela vazar para os quatro controles você não vê nada, porque os outros já estavam soltos. O efeito tem de ser um que ENDUREÇA, porque endurecer é o que a mão sente. E não julgue pela tela: o campo Modo continua mostrando «Rígido» mesmo se um jogo escrever por cima e o gatilho estiver leve no seu dedo — o campo mostra o pedido, nunca o aparelho. Duas coisas mais. A escolha GRAVA: o Modo fica guardado no perfil daquele controle, e é por isso que o terceiro passo anota o que estava lá e o último devolve — deixar o teste pela metade deixa «Rígido» gravado, e o gatilho nasce duro no próximo jogo. E, em agosto, mediu-se o efeito amanhecendo solto alguns MINUTOS depois de aplicado, sem ninguém tocar, e ninguém achou quem o apaga; então sinta LOGO depois de escolher, e se você voltar mais tarde e estiver leve, anote a hora e o nome que aparece ao lado de Perfil ativo, no alto. Por fim, onde a prova desta linha parou: em O APARELHO OBEDECEU, medido com os quatro controles em 11/08 — o dedo é o degrau certo aqui, e o jogo é o degrau seguinte, que ninguém mediu. Não conclua nada sobre gatilho olhando um jogo.

---

## mapa-gatilho.adaptativo-radio — Gatilhos adaptativos (resistência por zona) — os dois · rádio

*Célula:* `gatilho.adaptativo @ rádio`

**O que isto prova.** Prova que o L2 e o R2 do mesmo controle ficam duros AO MESMO TEMPO nos dois controles do rádio, igual aos do cabo — e que o efeito volta com o controle quando ele cai e reconecta.

**Onde olhar.** Na aba Gatilhos, no quadro Gatilhos. Cada controle é uma coluna, com o chip no alto — o número, a cor do plástico e USB ou BT; o da coluna do P3 e o da do P4 têm de dizer BT. A coluna da esquerda nomeia as linhas: Controle e depois duas seções tituladas por um desenho, o L2 em cima e o R2 embaixo, cada uma com Modo e Efeito pronto. As colunas seguem a ordem dos chips e se renumeram quando um controle sai. A prova, porém, é a sua mão: o controle não devolve em que efeito está, e o campo Modo mostra o que foi pedido. A tela só pisca em verde por cerca de um segundo e meio quando o comando sai.

**Os passos.**

1. Abra a aba Gatilhos.
2. Confira que o chip no alto da coluna do P3 e o da coluna do P4 dizem BT.
3. Anote no papel o que está escrito no Modo das duas seções da coluna do P3 e das duas da coluna do P4.
4. Escolha «Desligado» no Modo das duas seções da coluna do P3 e das duas da coluna do P4.
5. Aperte o L2 e o R2 dos quatro controles até o fundo, um controle por vez, e guarde na mão como cada um está agora: os do P3 e do P4 têm de estar leves.
6. Escolha «Rígido» no Modo da seção de CIMA (a do desenho L2), na coluna do P3, e veja o campo piscar em verde.
7. Aperte o L2 do P3 e depois o R2 do mesmo controle, um de cada vez, e confira que só o L2 travou.
8. Escolha «Rígido» no Modo da seção de BAIXO (a do desenho R2), na mesma coluna do P3.
9. Aperte o L2 e o R2 do P3 ao mesmo tempo, com dois dedos; depois solte e aperte de novo um de cada vez.
10. Confira que os dois estão duros e que ligar o segundo lado não soltou o primeiro.
11. Repita na coluna do P4 tudo o que você fez na do P3, do «Rígido» no L2 até os dois gatilhos apertados juntos.
12. Aperte o L2 e o R2 do P1 e depois os do P2, e compare com o que guardou na mão: têm de estar iguais.
13. Segure o PS do P3 até as luzes dele apagarem, e confira que a coluna do P4 passou a dizer P3 no chip.
14. Dê um toque no PS do P3 e espere o chip dele voltar ao alto de uma coluna.
15. Aperte o L2 e o R2 do P3 sem escolher nada: os dois têm de estar duros de novo.
16. Se voltaram leves, anote, e escolha «Desligado» e depois «Rígido» nas duas seções do P3 para mandar o efeito de novo.
17. Devolva o Modo das duas seções da coluna do P3 e das duas da coluna do P4 ao que você anotou no papel.

**Passa quando.** No P3 e no P4 — os dois do rádio — o L2 e o R2 ficam duros ao mesmo tempo, e continuam duros quando você aperta um de cada vez. A sensação é a mesma que os controles do cabo dão: sem fio não pode ser mais fraco nem chegar depois. Os gatilhos do P1 e do P2 continuam exatamente como estavam. E, depois de cair e voltar, o P3 volta com os dois gatilhos duros sem você escolher nada de novo.

**Por controle.**

* **P1** — No CABO, testemunha. Não toque na coluna dele. Aperte o L2 e o R2 antes e depois; têm de estar iguais. Se ele endurecer junto, o comando pegou todo mundo em vez do controle escolhido.
* **P2** — No CABO, segunda testemunha. Não toque na coluna dele. Aperte o L2 e o R2 antes e depois. Se o P1 ficou intacto e o P2 endureceu, o comando foi parar no controle errado.
* **P3** — No RÁDIO, e é o primeiro em que você mexe. Ponha «Rígido» na seção de cima (L2), sinta só ele travar, depois ponha «Rígido» na de baixo (R2) e sinta os dois duros com dois dedos. É ele que cai e volta, para ver se o efeito volta junto.
* **P4** — No RÁDIO, e é o segundo. Os mesmos gestos, na coluna dele. Ele separa "o rádio funciona" de "aquele controle funciona": se o P3 obedecer e o P4 não, o defeito é do aparelho, não do sem fio. Enquanto o P3 está fora, a coluna dele diz P3 — é a tela contando só os presentes, e ele volta a dizer P4 quando o P3 volta.

**A armadilha.** Não use «Desligado» como o efeito do teste: ele é a escolha que SOLTA, e vazar solto num gatilho já solto não se enxerga. E não julgue pela tela — o campo Modo mostra o pedido, não o aparelho; a piscada verde diz que o comando saiu, não que o gatilho está duro. Três avisos que valem especialmente aqui. Primeiro: a escolha GRAVA no perfil daquele controle, e é por isso que o terceiro passo anota e o último devolve. Segundo: a queda e a volta do P3 são o motivo de este teste ter mais passos que o do cabo — o efeito gravado para aquele controle deve voltar sozinho quando ele reconecta, e isso é o defeito próprio do rádio; se não voltar, o achado é esse. Para mandar de novo, escolher o mesmo nome que já está no campo não faz nada: é por isso que o passo passa por «Desligado» antes do «Rígido». Terceiro: em agosto, mediu-se o efeito amanhecendo solto alguns MINUTOS depois, sem ninguém tocar, e ninguém achou quem o apaga; sinta LOGO depois de escolher, e se estiver leve quando você voltar, anote a hora e o nome ao lado de Perfil ativo, no alto. Onde a prova parou: em O APARELHO OBEDECEU, medido em 11/08 com dois controles no rádio — o dedo é o degrau certo. O jogo é o degrau seguinte e ninguém o mediu, então não tente concluir nada sobre gatilho por dentro de um jogo.

---

## mapa-gatilho.analogico-cabo — Gatilhos analógicos (eixo de curso em ZL/ZR ou L2/R2) · cabo

*Célula:* `gatilho.analogico @ cabo`

**O que isto prova.** Prova que o Hefesto lê o CURSO do L2 e do R2 dos dois controles do cabo — o quanto o dedo apertou, e não só apertou ou não apertou.

**Onde olhar.** Na aba Controles. Clique no chip Todos, na fita do topo, para os quatro cartões ficarem abertos ao mesmo tempo. À direita de cada cartão há um bloco chamado Gatilhos com duas linhas, L2 e R2. Cada linha tem uma barra que enche e um número escrito assim: 200 / 255. É esse número que responde este teste. No meio do mesmo cartão fica a grade dos dezesseis desenhos de botão, e os desenhos L2 e R2 acendem — mas só depois de o número passar de 30.

**Os passos.**

1. Clique na aba Controles.
2. Clique na aba Gatilhos, anote no papel o Modo das duas seções da coluna do P1 e das duas da coluna do P2, e escolha «Desligado» nas quatro — senão você mede o efeito, e não o curso.
3. Volte à aba Controles.
4. Clique no chip Todos, na fita do topo.
5. Confira que o cartão do P1 e o do P2 dizem USB ao lado da cor.
6. Leia o número da linha L2 no bloco Gatilhos do cartão do P1, com o dedo fora do gatilho: tem de ser 0 / 255.
7. Aperte o L2 do P1 bem devagar, do ponto solto até a metade do curso, e pare com o dedo ali.
8. Veja o número subir junto com o dedo e parar num valor do meio, sem pular direto para 255.
9. Empurre o L2 do P1 até o fundo e solte, e confira que o número chega a 255 no fundo e volta a 0 quando você solta.
10. Repita esses apertos no R2 do P1 e nos dois gatilhos do P2.
11. Role a aba pelos cartões do P3 e do P4 durante um aperto: os números deles não podem se mexer.
12. Encoste levemente no L2 do P1, só o suficiente para o número sair do zero sem passar de 30, e confira que o desenho do L2 na grade ainda NÃO acendeu.
13. Aperte mais fundo o L2 do P1 e confira que agora o desenho acende.
14. Volte à aba Gatilhos e devolva os quatro Modos ao que você anotou.

**Passa quando.** No P1 e no P2, o número da linha do gatilho que você está apertando caminha por valores do meio entre 0 e 255 — ele não pula de 0 para 255 —, sobe conforme você aperta mais fundo, chega a 255 no fim do curso e volta a 0 quando você solta. Os números do P3 e do P4 não se mexem em momento nenhum. E o desenho do L2 na grade só acende depois que o número passa de 30.

**Por controle.**

* **P1** — No CABO, e é o primeiro. Aperte o L2 e depois o R2, devagar, parando na metade, e leia os dois números do bloco Gatilhos do cartão dele.
* **P2** — No CABO, e é o segundo. Os mesmos gestos, no cartão dele. Ele separa "o cabo lê o curso" de "aquele controle lê o curso": se o P1 andar e o P2 ficar parado, o defeito é do aparelho, não do transporte.
* **P3** — No RÁDIO, testemunha. Não encoste nele. Os números do L2 e do R2 no cartão dele têm de ficar parados em 0 enquanto você aperta os do cabo. Se andarem junto, a tela está mostrando o controle errado.
* **P4** — No RÁDIO, segunda testemunha. Não encoste nele. Mesma conferência: números parados. Se o P3 ficou parado e o P4 andou, o problema não é do rádio — é de alguma coisa apontando o número para o cartão errado.

**A armadilha.** O falso vermelho mais fácil é medir com efeito ligado: um gatilho em «Rígido» trava num ponto do curso e o número trava junto, e você conclui que a leitura quebrou quando quem travou foi o gatilho — por isso as duas seções do P1 e do P2 vão para «Desligado» na aba Gatilhos antes de começar, e voltam ao que eram no fim, porque a escolha fica gravada no perfil daquele controle. Outro que parece defeito e não é: o desenho do L2 acende só depois de 30 de 255, então um toque leve mexe o número sem acender o desenho — isso é o limiar, não um erro. O falso verde é o cartão sem leitura: ele mostra os gatilhos parados em 0 / 255, exatamente como um gatilho solto, e um traço no lugar de L3 e R3; se os números ficarem congelados o tempo todo, aperte o Cruz do mesmo controle e veja se o desenho dele acende — se nem isso, ninguém leu nada. Onde a prova desta linha parou, e isto é o mais importante: o mapa NÃO registra grau para esta célula — ninguém anotou até onde a prova chegou. O que existe é leitura de código mais três documentações externas que concordam sobre qual byte carrega o curso. Então o número na tela do Hefesto é exatamente o degrau que este teste alcança: não tente provar o curso do gatilho por dentro de um jogo, porque ninguém mediu esse degrau.

---

## mapa-gatilho.analogico-radio — Gatilhos analógicos (eixo de curso em ZL/ZR ou L2/R2) · rádio

*Célula:* `gatilho.analogico @ rádio`

**O que isto prova.** Prova que o Hefesto lê o CURSO do L2 e do R2 dos dois controles do rádio, com a mesma fidelidade dos do cabo.

**Onde olhar.** Na aba Controles. Clique no chip Todos, na fita do topo, para os quatro cartões ficarem abertos ao mesmo tempo. À direita de cada cartão há um bloco chamado Gatilhos, com duas linhas, L2 e R2, cada uma com uma barra que enche e um número no formato 200 / 255. É esse número que responde. No meio do mesmo cartão, a grade dos dezesseis desenhos de botão: os desenhos L2 e R2 acendem, mas só depois de o número passar de 30.

**Os passos.**

1. Clique na aba Controles.
2. Clique na aba Gatilhos, anote no papel o Modo das duas seções da coluna do P3 e das duas da coluna do P4, e escolha «Desligado» nas quatro — senão você mede o efeito, e não o curso.
3. Volte à aba Controles.
4. Clique no chip Todos, na fita do topo.
5. Confira que o cartão do P3 e o do P4 dizem BT ao lado da cor.
6. Leia o número da linha L2 no bloco Gatilhos do cartão do P3, com o dedo fora do gatilho: tem de ser 0 / 255.
7. Aperte o L2 do P3 bem devagar e pare com o dedo na metade do curso: o número tem de parar num valor do meio, e não pular direto para 255.
8. Empurre até o fundo e confirme que o número chega a 255; solte e confirme que ele volta a 0.
9. Repita a metade, o fundo e o soltar com o R2 do P3.
10. Repita tudo, L2 e R2, no P4.
11. Role a aba pelos cartões do P1 e do P2 durante um aperto: os números deles não podem se mexer.
12. Compare a subida do número no P3 com a que você viu num controle do cabo: tem de ser o mesmo caminho de 0 a 255, sem degraus grandes nem atraso visível.
13. Encoste levemente no L2 do P3, só até o número sair do zero sem passar de 30, e confira que o desenho do L2 na grade ainda NÃO acendeu.
14. Volte à aba Gatilhos e devolva os quatro Modos ao que você anotou.

**Passa quando.** No P3 e no P4, o número da linha do gatilho que você está apertando caminha por valores do meio entre 0 e 255, sobe conforme você aperta mais fundo, chega a 255 no fundo e volta a 0 quando você solta — do mesmo jeito que num controle do cabo. Os números do P1 e do P2 não se mexem em momento nenhum.

**Por controle.**

* **P1** — No CABO, testemunha. Não encoste nele. Os números do L2 e do R2 no cartão dele têm de ficar parados em 0 enquanto você aperta os do rádio.
* **P2** — No CABO, segunda testemunha. Não encoste nele. Mesma conferência. Se o P1 ficou parado e o P2 andou, alguma coisa está escrevendo o número no cartão errado.
* **P3** — No RÁDIO, e é o primeiro. Aperte o L2 e depois o R2, devagar, parando na metade, e leia os dois números do bloco Gatilhos do cartão dele. É aqui que se compara com o cabo.
* **P4** — No RÁDIO, e é o segundo. Os mesmos gestos, no cartão dele. Ele separa "o rádio lê o curso" de "aquele controle lê o curso": se o P3 andar e o P4 ficar parado, o defeito é do aparelho, não do sem fio.

**A armadilha.** O falso vermelho mais fácil é medir com efeito ligado: um gatilho em «Rígido» trava num ponto do curso e o número trava junto — por isso os Modos vão para «Desligado» antes de começar, e voltam ao que eram no fim, porque a escolha fica gravada no perfil daquele controle. Outro que parece defeito e não é: o desenho do L2 acende só depois de 30 de 255, então um toque leve mexe o número sem acender o desenho. Cartão sem leitura mostra os gatilhos parados em 0 / 255 e um traço no lugar de L3 e R3 — antes de reprovar, aperte o Cruz do mesmo controle e veja se o desenho dele acende. E há uma armadilha que é só do rádio, declarada na fonte: pelo sem fio o DualSense fala em DOIS desenhos de mensagem, um curto que ele emite antes de entrar no modo completo e o completo, e o curso do gatilho não fica no mesmo lugar nos dois — é o único dado de entrada que muda de posição entre os dois desenhos. A fonte não diz que sintoma isso produz na tela; então, se o número do P3 ou do P4 vier congelado ou visivelmente errado logo depois de o controle voltar ao rádio, anote com a hora, porque é exatamente o ponto onde o mapa avisa que os dois desenhos discordam. Onde a prova parou: o mapa NÃO registra grau para esta célula — ninguém anotou até onde a prova chegou; o que existe é leitura de código e três documentações externas que concordam sobre o byte. O número na tela do Hefesto é o degrau que este teste alcança; não tente provar o curso por dentro de um jogo.

---

## mapa-gatilho.direito.adaptativo-cabo — Gatilho adaptativo DIREITO · cabo

*Célula:* `gatilho.direito.adaptativo @ cabo`

**O que isto prova.** Prova que um efeito posto no gatilho DIREITO endurece só o R2 dos controles do cabo, e deixa o L2 do mesmo controle solto.

**Onde olhar.** Na aba Gatilhos, quadro Gatilhos. A coluna da esquerda nomeia as linhas, e a seção de BAIXO é a do R2 — ela é titulada pelo desenho R2, e dentro dela vêm Modo e Efeito pronto. A seção de cima, a do L2, não se toca neste teste. Clicar no desenho R2 da coluna da esquerda abre a linha Ajustes daquele gatilho (só uma fica aberta por vez); com «Rígido» escolhido, ela mostra duas barras com nome e número: Posição e Força. Numa coluna que tem controle elas são arrastáveis, e a alavanca é invisível — arrasta-se em cima da linha da própria barra. Quem responde o teste, porém, é a sua mão: o controle não devolve em que efeito ele está, e o campo Modo mostra só o que foi pedido. A tela apenas pisca em verde por cerca de um segundo e meio quando o comando sai.

**Os passos.**

1. Abra a aba Gatilhos.
2. Confira que o chip no alto da coluna do P1 e o da coluna do P2 dizem USB.
3. Anote no papel o Modo das duas seções da coluna do P1 e das duas da coluna do P2, e escolha «Desligado» nas quatro.
4. Aperte o L2 e o R2 dos quatro controles até o fundo, um controle por vez, e guarde na mão como cada um está.
5. Escolha «Rígido» no Modo da seção de BAIXO (a do desenho R2), na coluna do P1, e veja o campo piscar em verde.
6. Aperte o R2 do P1 e depois o L2 do mesmo controle, na mesma mão, um de cada vez.
7. Confira que o R2 trava duro do começo ao fim do curso e que o L2 continua leve.
8. Clique no desenho R2 da coluna da esquerda para abrir a linha Ajustes.
9. Arraste a barra Força do P1 até o fim da direita, em cima da linha da barra, e aperte o R2 do P1 de novo.
10. Confira que a trava ficou mais firme do que estava.
11. Repita na coluna do P2 o que você fez na do P1 antes da Força: «Rígido» na seção de baixo, e o R2 e o L2 apertados um de cada vez.
12. Aperte o R2 e o L2 do P3 e depois os do P4, e compare com o que guardou na mão: têm de estar iguais ao que estavam.
13. Devolva os quatro Modos do P1 e do P2 ao que você anotou.

**Passa quando.** O R2 do P1 e o do P2 ficam duros, e o L2 dos MESMOS controles continua leve — o comando agiu num lado só e não vazou para o outro lado da mesma mão. Os gatilhos do P3 e do P4 continuam exatamente como estavam. E puxar a Força até o fim deixa a trava mais firme do que estava.

**Por controle.**

* **P1** — No CABO, e é o primeiro. Mexe-se só na seção de BAIXO (R2) da coluna dele. O R2 tem de endurecer e o L2 do mesmo controle é a testemunha na mesma mão — é ele que prova que o comando não pegou os dois lados.
* **P2** — No CABO, e é o segundo. Os mesmos gestos, na coluna dele. Ele separa "o cabo funciona" de "aquele controle funciona": se o R2 do P1 endurecer e o do P2 não, o defeito é do aparelho.
* **P3** — No RÁDIO, testemunha. Não toque na coluna dele. Aperte o R2 e o L2 antes e depois; têm de estar iguais. Se o R2 dele endurecer, o comando pegou todo mundo em vez do controle escolhido.
* **P4** — No RÁDIO, segunda testemunha. Não toque na coluna dele. Mesma conferência. Se o P3 ficou intacto e o R2 do P4 endureceu, o comando foi para o controle errado.

**A armadilha.** A armadilha maior deste teste é apertar o gatilho errado. O R2 é o de baixo do lado DIREITO do controle, e a seção da tela é a de BAIXO, titulada pelo desenho R2. Quem mexe na seção de cima e aperta o R2 conclui que o produto errou de lado quando quem errou foi o gesto — confira o desenho que titula a seção antes de abrir o campo. Não use «Desligado» como o efeito do teste: ele SOLTA, e um vazamento de solto não se enxerga. Não julgue pela tela: o campo Modo mostra o pedido, e a piscada verde diz que o comando saiu, não que o gatilho está duro. A escolha e a barra GRAVAM no perfil daquele controle, e é por isso que o teste anota o que estava lá e devolve no fim. E a medição que sustenta esta linha exercitou UM modo só, «Rígido», com um único jogo de números — nenhum dos outros dezoito foi tocado por lá, e é por isso que o teste pede «Rígido». Em agosto mediu-se o efeito amanhecendo solto alguns MINUTOS depois, sem ninguém tocar: sinta logo depois de escolher, e se estiver leve quando voltar, anote a hora e o nome ao lado de Perfil ativo, no alto. Onde a prova parou: em O APARELHO OBEDECEU, medido em 11/08 com os quatro controles e o lado ocioso servindo de controle negativo — o dedo é o degrau certo. O jogo é o degrau seguinte e ninguém o mediu.

---

## mapa-gatilho.direito.adaptativo-radio — Gatilho adaptativo DIREITO · rádio

*Célula:* `gatilho.direito.adaptativo @ rádio`

**O que isto prova.** Prova que um efeito posto no gatilho DIREITO endurece só o R2 dos controles do rádio, e deixa o L2 do mesmo controle solto.

**Onde olhar.** Na aba Gatilhos, quadro Gatilhos. O chip no alto da coluna do P3 e o da do P4 têm de dizer BT. A seção de BAIXO da coluna da esquerda é a do R2, titulada pelo desenho R2, com Modo e Efeito pronto; a de cima é a do L2 e não se toca. As colunas seguem a ordem dos chips e se renumeram quando um controle sai. A prova é a sua mão: o controle não devolve em que efeito está, e o campo Modo mostra só o pedido; a tela pisca em verde por cerca de um segundo e meio quando o comando sai.

**Os passos.**

1. Abra a aba Gatilhos.
2. Confira que o chip no alto da coluna do P3 e o da coluna do P4 dizem BT.
3. Anote no papel o Modo das duas seções da coluna do P3 e das duas da coluna do P4, e escolha «Desligado» nas quatro.
4. Aperte o L2 e o R2 dos quatro controles até o fundo e guarde na mão como cada um está.
5. Escolha «Rígido» no Modo da seção de BAIXO (a do desenho R2), na coluna do P3, e veja o campo piscar em verde.
6. Aperte o R2 do P3 e, no mesmo controle e na mesma mão, o L2 dele.
7. Confira que o R2 trava duro do começo ao fim do curso e que o L2 continua leve.
8. Compare a firmeza do R2 do P3 com a de um controle do cabo que você já tenha sentido em «Rígido»: pelo rádio não pode ser mais fraca nem demorar mais a chegar.
9. Repita na coluna do P4 o «Rígido» na seção de baixo e os dois apertos.
10. Segure o PS do P3 até as luzes dele apagarem; depois dê um toque no PS e espere o chip dele voltar ao alto de uma coluna.
11. Aperte o R2 e o L2 do P3 sem escolher nada, e confira que o R2 voltou duro e o L2 continua leve; se o R2 voltou leve, anote, e escolha «Desligado» e depois «Rígido» na seção de baixo para mandar de novo.
12. Aperte o R2 e o L2 do P1 e os do P2, e compare com o que guardou na mão: os gatilhos das duas testemunhas têm de estar exatamente como estavam.
13. Devolva os quatro Modos do P3 e do P4 ao que você anotou.

**Passa quando.** O R2 do P3 e o do P4 ficam duros, e o L2 dos MESMOS controles continua leve — o comando agiu num lado só, pelo sem fio, e não vazou para o outro lado da mesma mão. A firmeza é a mesma que um controle do cabo dá. Os gatilhos do P1 e do P2 continuam exatamente como estavam. E, depois de cair e voltar, o P3 volta com o R2 duro e o L2 leve, sem você escolher nada de novo.

**Por controle.**

* **P1** — No CABO, testemunha. Não toque na coluna dele. Aperte o R2 e o L2 antes e depois; têm de estar iguais. Se o R2 dele endurecer, o comando pegou todo mundo.
* **P2** — No CABO, segunda testemunha. Não toque na coluna dele. Mesma conferência. Se o P1 ficou intacto e o R2 do P2 endureceu, o comando foi para o controle errado.
* **P3** — No RÁDIO, e é o primeiro. Mexe-se só na seção de BAIXO (R2) da coluna dele. O R2 endurece; o L2 do mesmo controle é a testemunha na mesma mão. É ele que cai e volta, para ver se o efeito volta junto e continua respeitando o lado.
* **P4** — No RÁDIO, e é o segundo. Os mesmos gestos, na coluna dele. Ele separa "o rádio funciona" de "aquele controle funciona": se o R2 do P3 endurecer e o do P4 não, o defeito é do aparelho, não do sem fio. Enquanto o P3 está fora, a coluna dele diz P3; ela volta a dizer P4 quando o P3 volta.

**A armadilha.** Este teste mede o mesmo dedo em três momentos — antes do efeito, com o efeito posto e depois de o controle cair e voltar — nos quatro controles; tirar qualquer um dos três deixa o teste sem o antes ou sem o depois, e ele passa a dar verde sem prova. A armadilha maior é apertar o gatilho errado: o R2 é o de baixo do lado DIREITO, e a seção da tela é a de BAIXO, titulada pelo desenho R2 — quem mexe na seção de cima e aperta o R2 conclui que o produto errou de lado quando quem errou foi o gesto. Não use «Desligado» como o efeito do teste, e não julgue pela tela: o campo Modo mostra o pedido e a piscada verde diz que o comando saiu, nada mais. A escolha GRAVA no perfil daquele controle: por isso o teste anota e devolve. A medição que sustenta esta linha exercitou UM modo só, «Rígido», com um único jogo de números; os outros dezoito não foram tocados por lá. O efeito gravado para aquele controle deve voltar sozinho quando ele reconecta pelo rádio — se não voltar, é o achado; e para mandar de novo, escolher o mesmo nome que já está no campo não faz nada, por isso o passo passa por «Desligado». Em agosto mediu-se o efeito amanhecendo solto alguns MINUTOS depois, sem ninguém tocar: sinta logo depois de escolher, e se estiver leve quando voltar, anote a hora e o nome ao lado de Perfil ativo, no alto. Onde a prova parou: em O APARELHO OBEDECEU, medido em 11/08 com dois controles no rádio — o dedo é o degrau certo, e o jogo é o degrau seguinte, que ninguém mediu.

---

## mapa-gatilho.esquerdo.adaptativo-cabo — Gatilho adaptativo ESQUERDO · cabo

*Célula:* `gatilho.esquerdo.adaptativo @ cabo`

**O que isto prova.** Prova que um efeito posto no gatilho ESQUERDO endurece só o L2 dos controles do cabo, e deixa o R2 do mesmo controle solto.

**Onde olhar.** Na aba Gatilhos, quadro Gatilhos. A coluna da esquerda nomeia as linhas, e a seção de CIMA é a do L2 — titulada pelo desenho L2, com Modo e Efeito pronto dentro dela. A seção de baixo, a do R2, não se toca neste teste. Clicar no desenho L2 da coluna da esquerda abre a linha Ajustes daquele gatilho (só uma fica aberta por vez); com «Rígido» escolhido, ela mostra duas barras com nome e número: Posição e Força. Numa coluna que tem controle elas são arrastáveis, e a alavanca é invisível — arrasta-se em cima da linha da própria barra. Quem responde é a sua mão: o controle não devolve em que efeito está, e o campo Modo mostra só o pedido. A tela pisca em verde por cerca de um segundo e meio quando o comando sai.

**Os passos.**

1. Abra a aba Gatilhos.
2. Confira que o chip no alto da coluna do P1 e o da coluna do P2 dizem USB.
3. Anote no papel o Modo das duas seções da coluna do P1 e das duas da coluna do P2, e escolha «Desligado» nas quatro.
4. Aperte o L2 e o R2 dos quatro controles até o fundo, um controle de cada vez, e guarde na mão como cada um está.
5. Escolha «Rígido» no Modo da seção de CIMA (a do desenho L2), na coluna do P1, e veja o campo piscar em verde: é o comando saindo.
6. Aperte o L2 do P1 e confira que ele trava duro do começo ao fim do curso.
7. Aperte o R2 do P1, no mesmo controle e na mesma mão, e confira que ele continua leve — é a testemunha do outro lado da mesma mão.
8. Clique no desenho L2 da coluna da esquerda para abrir a linha Ajustes.
9. Arraste a barra Força do P1 até o fim da direita, em cima da linha da barra, e aperte o L2 do P1 de novo.
10. Confira se a trava ficou mais firme.
11. Repita na coluna do P2 o que você fez na do P1 antes da Força: «Rígido» na seção de cima, e o L2 e o R2 apertados um de cada vez.
12. Aperte o L2 e o R2 do P3 e depois os do P4, e confira que os quatro gatilhos estão como você guardou na mão.
13. Devolva os quatro Modos do P1 e do P2 ao que você anotou.

**Passa quando.** O L2 do P1 e o do P2 ficam duros, e o R2 dos MESMOS controles continua leve — o comando agiu num lado só e não vazou para o outro lado da mesma mão. Os gatilhos do P3 e do P4 continuam exatamente como estavam. E puxar a Força até o fim deixa a trava mais firme.

**Por controle.**

* **P1** — No CABO, e é o primeiro. Mexe-se só na seção de CIMA (L2) da coluna dele. O L2 tem de endurecer e o R2 do mesmo controle é a testemunha na mesma mão — é ele que prova que o comando não pegou os dois lados.
* **P2** — No CABO, e é o segundo. Os mesmos gestos, na coluna dele. Ele separa "o cabo funciona" de "aquele controle funciona": se o L2 do P1 endurecer e o do P2 não, o defeito é do aparelho.
* **P3** — No RÁDIO, testemunha. Não toque na coluna dele. Aperte o L2 e o R2 antes e depois; têm de estar iguais. Se o L2 dele endurecer, o comando pegou todo mundo em vez do controle escolhido.
* **P4** — No RÁDIO, segunda testemunha. Não toque na coluna dele. Mesma conferência. Se o P3 ficou intacto e o L2 do P4 endureceu, o comando foi para o controle errado.

**A armadilha.** A armadilha maior deste teste é apertar o gatilho errado. O L2 é o de baixo do lado ESQUERDO do controle, e a seção da tela é a de CIMA, titulada pelo desenho L2. Quem mexe na seção de baixo e aperta o L2 conclui que o produto errou de lado quando quem errou foi o gesto — confira o desenho que titula a seção antes de abrir o campo. Não use «Desligado» como o efeito do teste: ele SOLTA, e um vazamento de solto não se enxerga. Não julgue pela tela: o campo Modo mostra o pedido, e a piscada verde diz que o comando saiu, não que o gatilho está duro. A escolha e a barra GRAVAM no perfil daquele controle, e é por isso que o teste anota o que estava lá e devolve no fim. E a medição que sustenta esta linha exercitou UM modo só, «Rígido», com um único jogo de números — nenhum dos outros dezoito foi tocado por lá, e é por isso que o teste pede «Rígido». Em agosto mediu-se o efeito amanhecendo solto alguns MINUTOS depois, sem ninguém tocar: sinta logo depois de escolher, e se estiver leve quando voltar, anote a hora e o nome ao lado de Perfil ativo, no alto. Onde a prova parou: em O APARELHO OBEDECEU, medido em 11/08 com os quatro controles e o lado ocioso servindo de controle negativo na mesma mão — o dedo é o degrau certo, e o jogo é o degrau seguinte, que ninguém mediu.

---

## mapa-gatilho.esquerdo.adaptativo-radio — Gatilho adaptativo ESQUERDO · rádio

*Célula:* `gatilho.esquerdo.adaptativo @ rádio`

**O que isto prova.** Prova que um efeito posto no gatilho ESQUERDO endurece só o L2 dos controles do rádio, e deixa o R2 do mesmo controle solto.

**Onde olhar.** Na aba Gatilhos, quadro Gatilhos. O chip no alto da coluna do P3 e o da do P4 têm de dizer BT. A seção de CIMA da coluna da esquerda é a do L2, titulada pelo desenho L2, com Modo e Efeito pronto; a de baixo é a do R2 e não se toca. As colunas seguem a ordem dos chips e se renumeram quando um controle sai. A prova é a sua mão: o controle não devolve em que efeito está, e o campo Modo mostra só o pedido; a tela pisca em verde por cerca de um segundo e meio quando o comando sai.

**Os passos.**

1. Abra a aba Gatilhos.
2. Confira que o chip no alto da coluna do P3 e o da coluna do P4 dizem BT.
3. Anote no papel o Modo das duas seções da coluna do P3 e das duas da coluna do P4, e escolha «Desligado» nas quatro.
4. Aperte o L2 e o R2 dos quatro controles até o fundo, um controle de cada vez, e guarde na mão como cada um está — o P1 e o P2 são as testemunhas.
5. Escolha «Rígido» no Modo da seção de CIMA (a do desenho L2), na coluna do P3, e veja o campo piscar em verde.
6. Aperte o L2 do P3 até o fundo do curso e confira que a trava é dura do começo ao fim.
7. Compare essa firmeza com a de um controle do cabo que você já tenha sentido em «Rígido»: pelo rádio não pode ser mais fraca nem demorar mais a chegar.
8. Aperte o R2 do P3, no mesmo controle e na mesma mão, e confira que ele continua leve.
9. Repita na coluna do P4 o «Rígido» na seção de cima e os dois apertos, e confira que o L2 do P4 ficou duro e o R2 dele continua leve.
10. Segure o PS do P3 até as luzes dele apagarem; depois dê um toque no PS e espere o chip dele voltar ao alto de uma coluna.
11. Aperte o L2 e o R2 do P3 sem escolher nada, e confira que o L2 voltou duro e o R2 continua leve; se o L2 voltou leve, anote, e escolha «Desligado» e depois «Rígido» na seção de cima para mandar de novo.
12. Aperte o L2 e o R2 do P1 e depois os do P2, e confira que estão como você guardou na mão.
13. Devolva os quatro Modos do P3 e do P4 ao que você anotou.

**Passa quando.** O L2 do P3 e o do P4 ficam duros, e o R2 dos MESMOS controles continua leve — o comando agiu num lado só, pelo sem fio, e não vazou para o outro lado da mesma mão. A firmeza é a mesma que um controle do cabo dá. Os gatilhos do P1 e do P2 continuam exatamente como estavam. E, depois de cair e voltar, o P3 volta com o L2 duro e o R2 leve, sem você escolher nada de novo.

**Por controle.**

* **P1** — No CABO, testemunha. Não toque na coluna dele. Aperte o L2 e o R2 antes e depois; têm de estar iguais. Se o L2 dele endurecer, o comando pegou todo mundo.
* **P2** — No CABO, segunda testemunha. Não toque na coluna dele. Mesma conferência. Se o P1 ficou intacto e o L2 do P2 endureceu, o comando foi para o controle errado.
* **P3** — No RÁDIO, e é o primeiro. Mexe-se só na seção de CIMA (L2) da coluna dele. O L2 endurece; o R2 do mesmo controle é a testemunha na mesma mão. É ele que cai e volta, para ver se o efeito volta junto e continua respeitando o lado.
* **P4** — No RÁDIO, e é o segundo. Os mesmos gestos, na coluna dele. Ele separa "o rádio funciona" de "aquele controle funciona": se o L2 do P3 endurecer e o do P4 não, o defeito é do aparelho, não do sem fio. Enquanto o P3 está fora, a coluna dele diz P3; ela volta a dizer P4 quando o P3 volta.

**A armadilha.** A armadilha maior é apertar o gatilho errado: o L2 é o de baixo do lado ESQUERDO, e a seção da tela é a de CIMA, titulada pelo desenho L2 — quem mexe na seção de baixo e aperta o L2 conclui que o produto errou de lado quando quem errou foi o gesto. Não use «Desligado» como o efeito do teste, e não julgue pela tela: o campo Modo mostra o pedido e a piscada verde diz que o comando saiu, nada mais. Sem o aperto dos quatro controles no começo este teste não mede nada: é essa mão guardada que vira a régua de tudo o que vem depois. A escolha GRAVA no perfil daquele controle: por isso o teste anota e devolve. A medição que sustenta esta linha exercitou UM modo só, «Rígido», com um único jogo de números; os outros dezoito não foram tocados por lá. O efeito gravado para aquele controle deve voltar sozinho quando ele reconecta pelo rádio — se não voltar, é o achado; e escolher o mesmo nome que já está no campo não manda nada, por isso o passo passa por «Desligado». Em agosto mediu-se o efeito amanhecendo solto alguns MINUTOS depois, sem ninguém tocar: sinta logo depois de escolher, e se estiver leve quando voltar, anote a hora e o nome ao lado de Perfil ativo, no alto. Onde a prova parou: em O APARELHO OBEDECEU, medido em 11/08 com dois controles no rádio e o lado ocioso servindo de controle negativo — o dedo é o degrau certo, e o jogo é o degrau seguinte, que ninguém mediu. Cada aperto é de um gatilho só, num controle só, porque o dedo é o único instrumento que existe aqui; juntar dois apertos numa lembrança só é exatamente o erro que a armadilha maior descreve.

---

## mapa-gatilho.modos_firmware-cabo — Gatilho — modos do firmware (enum) · cabo

*Célula:* `gatilho.modos_firmware @ cabo`

**O que isto prova.** Passa a mão pelos dezenove efeitos da lista, nos dois controles do cabo, para ver quais fazem alguma coisa de verdade e quais não fazem nada.

**Onde olhar.** Na aba Gatilhos, quadro Gatilhos. O campo Modo, dentro da seção de cima (a do desenho L2), abre uma lista com dezenove escolhas — de «Desligado» a «Montar do zero». Clicar no desenho L2 da coluna da esquerda abre a linha Ajustes, que muda de barras conforme o efeito escolhido: alguns têm duas barras, outros mais, outros nenhuma, e nesse caso ela diz Sem ajustes. Parar o mouse em cima do campo mostra uma explicação de uma linha do efeito escolhido. Mas o que responde este teste é o SEU DEDO, e o instrumento é um papel com os dezenove nomes copiados: o DualSense não devolve em que efeito está, então nem o campo nem as barras provam nada sobre o aparelho. A tela só pisca em verde por cerca de um segundo e meio quando o comando sai.

**Os passos.**

1. Abra a aba Gatilhos.
2. Confira que o chip no alto da coluna do P1 e o da coluna do P2 dizem USB.
3. Anote no papel o Modo das duas seções do P1 e do P2 — é o que você devolve no fim.
4. Aperte o L2 e o R2 do P3 e do P4 e anote como eles estão — são as testemunhas, e não podem mudar em momento nenhum.
5. Clique no desenho L2 da coluna da esquerda, para a linha Ajustes ficar à vista.
6. Abra o campo Modo da seção de cima, na coluna do P1, e copie para o papel os dezenove nomes da lista, na ordem em que aparecem.
7. Escolha «Desligado» nesse campo e aperte o L2 do P1: esta é a sua referência de gatilho solto.
8. Escolha o nome seguinte da lista, veja o campo piscar em verde e aperte o L2 do P1 do começo ao fundo do curso, primeiro devagar e depois rápido.
9. Escreva ao lado daquele nome o que a sua mão sentiu de diferente do «Desligado»: nada, duro do começo ao fim, duro a partir de um ponto, um estalo, tremendo, ou outra coisa.
10. Anote também quantas barras a linha Ajustes passou a mostrar, ou se ela passou a dizer Sem ajustes.
11. Repita a escolha, o aperto e as duas anotações para cada nome que sobra na lista, até o último.
12. Volte a «Disparo» e depois a «Vibração», apertando o L2 do P1 com atenção em cada um dos dois, e anote de novo o que sentiu.
13. Faça a volta inteira pelos dezenove nomes também na coluna do P2, o outro controle do cabo, e compare a tabela dele com a do P1, nome por nome.
14. Compare, no fim de tudo, o L2 e o R2 do P3 e do P4 com o que você anotou no começo: têm de estar iguais.
15. Devolva o Modo das duas seções do P1 e do P2 ao que você anotou no começo.

**Passa quando.** Cada nome da lista produz na sua mão uma sensação diferente da do «Desligado», e a MESMA sensação nos dois controles do cabo: o que o P1 fez, o P2 fez igual. Um nome que não muda nada em relação ao «Desligado» é achado do teste e não erro seu — anote e siga. E o P3 e o P4 não podem ter mudado de sensação em momento nenhum do teste.

**Por controle.**

* **P1** — No CABO, e é onde você faz a volta inteira pelos dezenove nomes, no L2. Ele produz a sua tabela no papel: um nome, uma sensação.
* **P2** — No CABO, e é a conferência. Faça a mesma volta na coluna dele e compare nome por nome com a tabela do P1. Onde os dois discordarem, o problema é do aparelho e não da lista — e é justamente por isso que são dois no cabo.
* **P3** — No RÁDIO, testemunha. Não toque na coluna dele. Aperte o L2 e o R2 no começo e no fim; têm de estar iguais. Se ele mudar de sensação no meio da volta, algum dos dezenove escapou para o transporte inteiro.
* **P4** — No RÁDIO, segunda testemunha. Não toque na coluna dele. Mesma conferência. Se o P3 ficou intacto e o P4 mudou, o efeito foi parar no controle errado.

**A armadilha.** O trabalho real é maior do que a lista deixa ver: a escolha, o aperto e as anotações são UM ato repetido dezenove vezes, e a volta inteira se repete no segundo controle. A lista foi encurtada; o teste não. Este é também o teste em que "nada aconteceu" é resposta legítima e prevista: o mapa registra esta linha como PARCIAL, e a medição que existe é dela mesma, pelo TATO, em 01/08 — na época SETE das escolhas não faziam nada (três mandavam ao aparelho o número do desligado; quatro mandavam o número certo sem dizer quais zonas do gatilho usar). Aquelas foram consertadas, e este teste é o que confere se ficaram. Dois nomes, porém, continuam com divergência VIVA declarada no mapa: «Disparo» e «Vibração» mandam ao aparelho, cada um, o número de OUTRO efeito, e ninguém mediu se eles fazem alguma coisa — por isso eles têm passo próprio. Se derem sensação estranha, ou nenhuma, é o achado, e está previsto. O falso verde daqui é julgar pela tela: o campo Modo e a linha Ajustes mudam SEMPRE, porque quem os desenha é o produto e nunca o aparelho — o DualSense não devolve em que efeito está. Só o dedo responde. Dois cuidados. Cada escolha GRAVA no perfil daquele controle, e é por isso que o último passo devolve o que estava lá — parar no meio deixa o último efeito da lista gravado, e o gatilho nasce com ele no próximo jogo. E dezenove escolhas levam um bom tempo: em agosto mediu-se o efeito amanhecendo solto sozinho alguns MINUTOS depois, então sinta LOGO depois de escolher e não volte a conferir o efeito de dez nomes atrás. Onde a prova parou: o mapa NÃO registra grau para esta célula. O degrau que este teste alcança é o seu dedo; o jogo está fora, e ninguém o mediu.

---

## mapa-gatilho.modos_firmware-radio — Gatilho — modos do firmware (enum) · rádio

*Célula:* `gatilho.modos_firmware @ rádio`

**O que isto prova.** Passa a mão pelos dezenove efeitos da lista, nos dois controles do rádio, para ver quais fazem alguma coisa e se o sem fio responde igual ao cabo.

**Onde olhar.** Na aba Gatilhos, quadro Gatilhos. O chip no alto da coluna do P3 e o da do P4 têm de dizer BT. O campo Modo, dentro da seção de cima (a do desenho L2), abre uma lista com dezenove escolhas — de «Desligado» a «Montar do zero». Clicar no desenho L2 da coluna da esquerda abre a linha Ajustes, que muda de barras conforme o efeito escolhido, e quando o efeito não tem o que ajustar ela diz Sem ajustes. Parar o mouse no campo mostra uma explicação de uma linha do efeito. Mas quem responde este teste é o SEU DEDO: nem o campo nem as barras dizem nada sobre o aparelho, porque o DualSense não devolve em que efeito está. A tela apenas pisca em verde por cerca de um segundo e meio quando o comando sai. Tenha papel e caneta à mão antes de começar: a saída deste teste é uma tabela de dezenove linhas por controle — um nome, uma sensação.

**Os passos.**

1. Abra a aba Gatilhos.
2. Confira que o chip no alto da coluna do P3 e o da coluna do P4 dizem BT.
3. Anote no papel o Modo das duas seções do P3 e do P4 — é o que você devolve no fim.
4. Aperte o L2 e o R2 do P1 e do P2 até o fundo e anote como estão — eles são as testemunhas e não podem mudar em momento nenhum.
5. Abra o campo Modo da seção de cima (a do desenho L2), na coluna do P3, e copie para o papel os dezenove nomes da lista, na ordem.
6. Escolha «Desligado» nesse campo e aperte o L2 do P3 do começo ao fundo do curso: esta é a sua referência de gatilho solto.
7. Escolha o próximo nome da lista no mesmo campo e veja o campo piscar em verde.
8. Aperte o L2 do P3 do começo ao fundo do curso, primeiro devagar e depois rápido.
9. Escreva no papel, ao lado daquele nome, o que a sua mão sentiu: nada, duro do começo ao fim, duro a partir de um ponto, um estalo, tremendo, ou outra coisa.
10. Repare se a sensação demorou visivelmente mais a chegar do que chegaria por cabo, e anote isso ao lado.
11. Repita a escolha, o aperto do L2 e a anotação para cada nome que sobra na lista, até o último.
12. Volte a «Disparo» e depois a «Vibração», um de cada vez, apertando o L2 do P3 com atenção em cada um, e anote de novo o que a sua mão sentiu.
13. Refaça a volta inteira na coluna do P4, o outro controle do rádio.
14. Compare nome por nome a tabela do P4 com a do P3 — e com a do cabo, se você a tiver.
15. Aperte de novo o L2 e o R2 do P1 e do P2, e confira que estão iguais ao que você anotou no começo.
16. Devolva o Modo das duas seções do P3 e do P4 ao que você anotou no começo.

**Passa quando.** Cada nome da lista produz na sua mão uma sensação diferente da do «Desligado», e a MESMA sensação nos dois controles do rádio — e a mesma que o cabo dá, se você tiver a tabela do cabo ao lado. Nenhuma escolha pode chegar visivelmente mais tarde pelo sem fio. Um nome que não muda nada em relação ao «Desligado» é achado do teste, não erro seu: anote e siga. E o P1 e o P2 não podem ter mudado de sensação em momento nenhum.

**Por controle.**

* **P1** — No CABO, testemunha. Não toque na coluna dele. Aperte o L2 e o R2 no começo e no fim; têm de estar iguais. Se ele mudar de sensação no meio da volta, algum dos dezenove escapou para todo mundo.
* **P2** — No CABO, segunda testemunha. Não toque na coluna dele. Mesma conferência. Se o P1 ficou intacto e o P2 mudou, o efeito foi parar no controle errado.
* **P3** — No RÁDIO, e é onde você faz a volta inteira pelos dezenove nomes, no L2. Ele produz a sua tabela do sem fio: um nome, uma sensação.
* **P4** — No RÁDIO, e é a conferência. Faça a mesma volta na coluna dele e compare nome por nome com a tabela do P3. Onde os dois discordarem, o problema é do aparelho e não do sem fio — é para isso que são dois no rádio.

**A armadilha.** Este é o teste em que "nada aconteceu" é resposta legítima e prevista: o mapa registra esta linha como PARCIAL, e a medição que existe é dela mesma, pelo TATO, em 01/08 — na época SETE das escolhas não faziam nada (três mandavam ao aparelho o número do desligado; quatro mandavam o número certo sem dizer quais zonas do gatilho usar). Aquelas foram consertadas, e este teste confere se ficaram. Dois nomes continuam com divergência VIVA declarada no mapa: «Disparo» e «Vibração» mandam ao aparelho, cada um, o número de OUTRO efeito, e ninguém mediu se fazem alguma coisa — por isso têm passo próprio. Se derem sensação estranha, ou nenhuma, é o achado. O falso verde é julgar pela tela: o campo Modo e a linha Ajustes mudam SEMPRE, porque quem os desenha é o produto e nunca o aparelho. Só o dedo responde. Três cuidados que são do rádio. Se um controle cair e voltar no meio da volta, o efeito gravado para ele deve voltar junto — mas se uma sequência de nomes seguidos aparecer como "não fez nada", confira na fita se o chip daquele controle sumiu e voltou, porque uma queda só explicaria todos eles; para mandar de novo, escolha outro nome e volte ao que estava, já que escolher o mesmo nome não manda nada. A volta pelos dezenove leva um bom tempo, e em agosto mediu-se o efeito amanhecendo solto sozinho alguns MINUTOS depois, então aperte o L2 LOGO depois de escolher. E cada escolha GRAVA no perfil daquele controle: por isso o último passo devolve o que estava lá. O aperto do L2 é o teste inteiro e se repete dezenove vezes em cada controle, com uma escolha e uma anotação em volta de cada aperto; cortar a volta pela metade não responderia a pergunta. Onde a prova parou: o mapa NÃO registra grau para esta célula. O degrau que este teste alcança é o seu dedo; o jogo está fora, e ninguém o mediu.

---

## mapa-identidade.cor_do_aparelho-cabo — Cor de fábrica do controle (a cor do plástico, lida do aparelho) · cabo

*Célula:* `identidade.cor_do_aparelho @ cabo`

**O que isto prova.** Prova que o Hefesto pergunta ao aparelho, pelo cabo, qual é a cor de fábrica do plástico — e escreve na tela o nome certo dos dois controles do cabo.

**Onde olhar.** Três lugares dizem a mesma coisa e é bom conferir os três. Primeiro, a fita do topo, a linha que começa com Selecionar: cada controle é um chip com o número, o nome da cor e USB ou BT, e a BORDA do chip é pintada na cor do plástico. Segundo, a aba Controles: o cabeçalho de cada cartão diz o número, o nome da cor e USB ou BT. Terceiro, a aba Conexões, quadro Gestão de Controles, que nasce recolhido e se abre clicando no título: a linha diz Sony • Player 1 • nome da cor • USB, com uma barrinha colorida à esquerda. Quando a cor NÃO foi lida, o chip e o cartão põem um travessão no lugar do nome, e a linha da aba Conexões simplesmente omite o nome — não escreve nada ali.

**Os passos.**

1. Clique na aba Controles.
2. Desencaixe os dois cabos e segure o PS de cada um dos quatro controles até as luzes dele apagarem.
3. Confira que a contagem no alto, à direita, diz Nenhum controle.
4. Ponha os quatro com o plástico à vista e anote num papel a cor de cada um, na ordem em que você vai ligá-los.
5. Clique na aba Sistema, clique em Reiniciar o serviço e espere a janela voltar — é isso que faz o Hefesto esquecer as cores que já perguntou.
6. Encaixe o cabo no primeiro controle e depois no PC; faça o mesmo com o segundo.
7. Dê um toque curto no PS do terceiro controle e depois no do quarto.
8. Volte à aba Controles e espere a contagem no alto dizer 2 USB · 2 BT.
9. Leia o nome da cor no cabeçalho do cartão do P1 e compare com o plástico dele; faça o mesmo com o P2.
10. Confira que ao lado do nome, nos dois, está escrito USB.
11. Compare a borda do chip do P1 e a do P2, na fita do topo, com o plástico de cada um.
12. Abra a aba Conexões, clique no título Gestão de Controles e confira que as linhas do P1 e do P2 trazem o nome da cor entre o Player e o USB.
13. Se algum dos dois mostrar travessão, espere dois minutos e meio e leia de novo, anotando as duas leituras.
14. Anote o que os cartões do P3 e do P4 mostram no lugar da cor — este teste não se decide por eles, mas a anotação importa.

**Passa quando.** Os dois controles do cabo aparecem com o nome da cor de fábrica escrito por extenso, e esse nome é a cor do plástico que você tem na mão. A borda do chip de cada um está pintada nesse tom, e ao lado está escrito USB. Nenhum dos dois termina a espera de dois minutos e meio com travessão no lugar do nome.

**Por controle.**

* **P1** — No cabo, e é um dos dois que têm de responder. Compare o nome escrito no cabeçalho do cartão dele com o plástico na sua mão, e depois a borda do chip com o mesmo plástico.
* **P2** — No cabo, o segundo que tem de responder. Ele existe para o caso de o P1 acertar por sorte: se os dois acertam cores DIFERENTES, o Hefesto perguntou a cada aparelho, em vez de espalhar uma resposta só.
* **P3** — No rádio, testemunha. Só anote o que o cartão dele diz. Se ele mostrar a MESMA cor de um dos dois do cabo e o plástico dele for outro, a resposta de um controle está vazando para os outros — e esse é o achado.
* **P4** — No rádio, testemunha, mesma anotação. Se o P3 e o P4 mostram a mesma cor e os plásticos deles são diferentes, é o mesmo achado, e agora com duas provas.

**A armadilha.** Quatro. O desenho da tela nasce com dois chips de exemplo, P1 · Cosmic Red · USB e P2 · Starlight Blue · BT, e é fácil tomá-los por leitura de verdade: conte os chips na fita — os seus são quatro. Se houver dois, com esses nomes, você está olhando o desenho, e o teste não passou nem reprovou. Segunda, e ela dá falso verde: o Hefesto guarda a cor que já leu até o serviço reiniciar. Desplugar e replugar um controle só não faz perguntar de novo — o nome reaparece sem pergunta nenhuma. É por isso que o teste começa com os quatro desligados e Reiniciar o serviço. Terceira: quando a pergunta não volta, o Hefesto pergunta de novo depois de 5 segundos, de 30 e de 120, e só então desiste até o controle sair e voltar. Um travessão lido no primeiro minuto ainda não é a resposta; o de depois dos dois minutos e meio é. E travessão é resposta honesta, não mentira: anote como reprova, mas não confunda com o Hefesto inventando uma cor. Quarta: uma cor declarada à mão para um controle, na configuração do computador, vence a leitura. Neste computador, hoje, nenhum controle tem cor declarada.

---

## mapa-identidade.cor_do_aparelho-radio — Cor de fábrica do controle (a cor do plástico, lida do aparelho) · rádio

*Célula:* `identidade.cor_do_aparelho @ rádio`

**O que isto prova.** Prova que o Hefesto consegue perguntar a cor de fábrica do plástico também pelo rádio, e escreve o nome certo dos dois controles sem fio.

**Onde olhar.** Os mesmos três lugares do teste do cabo, agora no P3 e no P4. Na fita do topo, o chip com o número, o nome da cor e BT, com a borda pintada nessa cor. Na aba Controles, o cabeçalho do cartão. Na aba Conexões, quadro Gestão de Controles (clique no título para abrir), a linha Sony • Player 3 • nome da cor • BT, com a barrinha colorida à esquerda. Sem leitura, o cabeçalho do cartão e o chip põem um travessão, e a linha da aba Conexões omite o nome.

**Os passos.**

1. Clique na aba Controles.
2. Desencaixe os dois cabos e segure o PS de cada um dos quatro controles até as luzes dele apagarem.
3. Confira que a contagem no alto, à direita, diz Nenhum controle, e anote num papel a cor do plástico de cada um.
4. Clique na aba Sistema, clique em Reiniciar o serviço e espere a janela voltar — sem isso o Hefesto mostra a cor que já tinha lido pelo cabo, sem perguntar nada pelo rádio.
5. Encaixe o cabo no primeiro controle e depois no PC; faça o mesmo com o segundo.
6. Dê um toque curto no PS do terceiro controle e espere o chip dele aparecer na fita do topo; depois faça o mesmo com o quarto.
7. Volte à aba Controles.
8. Leia o cabeçalho do cartão do P3 e compare o nome da cor com o plástico daquele controle; faça o mesmo com o P4.
9. Confira que ao lado do nome, nos dois, está escrito BT.
10. Compare a borda do chip do P3 e a do P4, na fita do topo, com os plásticos.
11. Abra a aba Conexões, clique no título Gestão de Controles e confira que as linhas do P3 e do P4 trazem o nome da cor e a barrinha da esquerda pintada.
12. Se algum dos dois mostrar travessão, espere dois minutos e meio e leia de novo, anotando as duas leituras.
13. Leia também as linhas do P1 e do P2 e confira que a cor deles não trocou quando os do rádio entraram.

**Passa quando.** Os dois controles do rádio aparecem com o nome da cor de fábrica escrito por extenso, e o nome bate com o plástico na sua mão. Ao lado está escrito BT nos dois, e a borda do chip está pintada. E os dois do cabo continuam com as cores que já tinham antes de os do rádio entrarem.

**Por controle.**

* **P1** — No cabo, testemunha. Anote a cor dele ANTES de ligar os do rádio e confira depois: ela não pode trocar quando um controle sem fio entra.
* **P2** — No cabo, testemunha, mesma conferência antes e depois.
* **P3** — No rádio, e é um dos dois que têm de responder. Ele precisa entrar pelo rádio depois do Reiniciar o serviço sem ter passado pelo cabo — se este mesmo aparelho passou pelo cabo depois do reinício, o teste não mede o rádio.
* **P4** — No rádio, o segundo que tem de responder, e é ele que dá o tamanho da resposta. A leitura pelo rádio só foi provada em DOIS aparelhos até hoje; estes são o terceiro e o quarto. Um deles ficando em travessão é achado — e é justamente o achado que este teste existe para procurar.

**A armadilha.** O falso verde mais fácil é o da memória do Hefesto: ele guarda a cor de cada aparelho pelo endereço do controle, que é o mesmo no cabo e no rádio, até o serviço reiniciar. Se aquele controle já tinha respondido pelo CABO depois do último reinício, o nome aparece na tela sem que uma única pergunta tenha saído pelo rádio, e o teste dá verde sobre nada. É por isso que os quatro saem e o serviço reinicia antes de tudo. Segunda: pelo rádio o pedido vai assinado, e essa leitura só está provada em duas unidades desta bancada, não nas quatro. Um travessão no P3 ou no P4 pode ser exatamente isso e não é erro seu — anote qual controle recusou e qual é a cor do plástico dele, porque esse par é o dado. Terceira: uma pergunta que não volta é feita de novo depois de 5 segundos, de 30 e de 120; um travessão que vira nome nesse meio-tempo é o produto funcionando, e as duas leituras vão para o papel. Quarta: se a fita mostrar só dois chips, com os nomes Cosmic Red e Starlight Blue, você está olhando o desenho de exemplo, e não os seus controles.

---

## mapa-identidade.cracha_nos_dois_transportes-cabo — O crachá que serve nos DOIS transportes sem escrita (a pergunta dela) · cabo

*Célula:* `identidade.cracha_nos_dois_transportes @ cabo`

**O que isto prova.** Prova que o crachá de um controle que está no cabo é o mesmo aparelho de sempre — ele sai para o rádio e volta ao cabo sem trocar de nome.

**Onde olhar.** O crachá é o conjunto que nomeia o controle, e ele aparece em três lugares: na aba Conexões, quadro Gestão de Controles (clique no título para abrir), a linha Sony • Player 1 • cor • USB; na fita do topo, o chip com o número, a cor e USB ou BT, com a borda pintada na cor; e na aba Controles, o cabeçalho do cartão. As três partes que têm de SOBREVIVER são a marca, a cor e o número do jogador. A quarta, USB ou BT, é justamente a que TEM de mudar. O endereço do aparelho, que é o que faz o crachá funcionar por dentro, não aparece na tela — ele é chave interna, e não vocabulário de tela.

**Os passos.**

1. Clique na aba Conexões.
2. Clique no título Gestão de Controles para abrir o quadro.
3. Confira que o P1 e o P2 já foram pareados pelo rádio neste computador alguma vez — sem isso o teste não roda.
4. Anote a linha inteira de cada um dos quatro controles, palavra por palavra.
5. Puxe o cabo de dentro do P1.
6. Confira que, enquanto ele está fora, os de trás subiram um número: quem era Player 2 passa a dizer Player 1, e assim por diante.
7. Dê um toque no PS do P1, se ele não voltar sozinho, e espere o chip dele voltar à fita do topo.
8. Leia a linha dele: a marca, a cor e o número têm de ser os mesmos de antes, e só o USB pode ter virado BT.
9. Encaixe o cabo de novo no P1 e depois no PC, e espere o chip dele voltar à fita.
10. Leia a linha dele outra vez e compare, palavra por palavra, com a que você anotou no começo.
11. Refaça no P2 a ida ao rádio e a volta ao cabo, do puxão do cabo até a leitura final.
12. Leia as linhas do P3 e do P4 e confira que estão como você anotou.

**Passa quando.** O P1 e o P2 atravessam a ida ao rádio e a volta ao cabo com a mesma marca, a mesma cor e o mesmo número de jogador. A única coisa do crachá que muda é o USB, que vira BT no rádio e volta a ser USB quando o cabo volta. Nenhuma linha nova aparece para eles em momento nenhum, e o P3 e o P4 terminam como começaram.

**Por controle.**

* **P1** — No cabo, e é o primeiro a atravessar. Puxe o cabo, traga-o pelo rádio e devolva-o ao cabo. Marca, cor e número têm de sair iguais dos dois lados.
* **P2** — No cabo, o segundo a atravessar. Ele existe porque o crachá tem de valer para os dois — com um só, um acerto pode ser sorte.
* **P3** — No rádio, testemunha. Enquanto um dos do cabo está fora, a linha dele sobe um número, e volta ao dela quando ele volta; ela não pode sumir nem trocar de cor em instante nenhum.
* **P4** — No rádio, testemunha, e a que mais importa: enquanto o P1 está no rádio há TRÊS controles sem fio ao mesmo tempo, e é aí que um crachá frouxo confunde dois aparelhos. Olhe a linha dele durante a travessia, não só depois.

**A armadilha.** O verde deste teste é fácil de conseguir por engano, e vale saber por quê: o Hefesto guarda a cor do plástico de cada APARELHO pelo endereço, que é o mesmo no cabo e no rádio. Se o crachá funcionar, o nome da cor reaparece no rádio SEM nova pergunta — e é isso que este teste quer ver. Mas o contrário também vale: este teste NÃO prova que a leitura da cor pelo rádio funciona; quem prova isso é o teste próprio dela. Segunda: enquanto um controle está fora, a tela conta só os presentes, e os de trás sobem um número; isso não é crachá quebrado. O número de quem volta é o de antes a qualquer tempo, enquanto o serviço estiver de pé; o que reprova é o P1 VOLTAR com outro número. Terceira: as lampadinhas embaixo do touchpad levam cerca de meio minuto para acompanhar a tela; olhe a tela, não o aparelho. Quarta: se o P1 era o que diz Navega o PC na aba Navegação e ficar mais de meio minuto fora, o posto fica com outro controle — confira no fim e anote, porque os testes de navegação dependem disso. Quinta: até hoje isto foi medido em quatro aparelhos, e é amostra — o que sustenta a generalização é o mecanismo, não a contagem.

---

## mapa-identidade.cracha_nos_dois_transportes-radio — O crachá que serve nos DOIS transportes sem escrita (a pergunta dela) · rádio

*Célula:* `identidade.cracha_nos_dois_transportes @ rádio`

**O que isto prova.** Prova que o crachá de um controle que está no rádio também é o mesmo aparelho de sempre — ele vai para o cabo e volta ao rádio sem trocar de nome.

**Onde olhar.** Os mesmos três lugares, agora no P3 e no P4: a linha Sony • Player 3 • cor • BT no quadro Gestão de Controles, da aba Conexões (clique no título para abrir); o chip do P3 na fita do topo, com a borda pintada; e o cabeçalho do cartão na aba Controles. A marca, a cor e o número têm de sobreviver à travessia; só o BT muda. O endereço do aparelho não aparece na tela — ele é chave de dentro do produto.

**Os passos.**

1. Clique na aba Conexões.
2. Clique no título Gestão de Controles para abrir o quadro.
3. Anote a linha inteira de cada um dos quatro controles, palavra por palavra.
4. Segure o PS do P3 até todas as luzes dele apagarem.
5. Confira que, enquanto ele está fora, a linha do P4 passou a dizer Player 3.
6. Encaixe um cabo no P3 e depois no PC; dê um toque no PS dele se ele não acender sozinho.
7. Espere o chip dele voltar à fita do topo e leia a linha dele: marca, cor e número iguais aos de antes, e só o BT pode ter virado USB.
8. Desencaixe o cabo do P3 e dê um toque no PS para trazê-lo de volta pelo rádio.
9. Espere o chip dele voltar à fita e compare a linha, palavra por palavra, com a que você anotou no começo.
10. Refaça no P4 tudo o que fez no P3, do apagar até a leitura final.
11. Leia as linhas do P1 e do P2 e confira que estão como você anotou.

**Passa quando.** O P3 e o P4 atravessam a ida ao cabo e a volta ao rádio com a mesma marca, a mesma cor e o mesmo número de jogador. A única coisa do crachá que muda é o BT, que vira USB no cabo e volta a ser BT no fim. Nenhuma linha nova aparece para eles, e o P1 e o P2 ficam parados nos números e nas cores deles.

**Por controle.**

* **P1** — No cabo, testemunha. A linha dele não pode sumir nem trocar de número enquanto o P3 e o P4 atravessam — e é durante a travessia que se olha, não só depois.
* **P2** — No cabo, testemunha, mesma vigilância. Enquanto o P3 está no fio há TRÊS controles no cabo ao mesmo tempo, e é aí que um crachá frouxo confunde dois aparelhos.
* **P3** — No rádio, e é o primeiro a atravessar: apaga, vai para o cabo, volta pelo rádio. Marca, cor e número têm de sair iguais dos dois lados.
* **P4** — No rádio, o segundo a atravessar. Enquanto o P3 está apagado, ele aparece como Player 3, e volta a Player 4 quando o P3 volta. Ele é o último da fila — se o P3 volta certo e ele não, o achado é do quarto lugar, não do transporte.

**A armadilha.** A armadilha própria deste lado é o sono do controle: um controle que dormiu não reaparece sozinho quando você pluga o cabo — já foi medido nesta casa. Se ele não acender ao ser plugado, dê um toque no PS; sem isso você anotaria "sumiu no cabo" sobre um aparelho que está apenas dormindo. Segunda: o nome da cor pode APARECER só depois de ele ir para o cabo e nunca antes. Isso não é o crachá falhando — é a leitura da cor pelo rádio, que só está provada em duas unidades e tem teste próprio. O que reprova AQUI é a cor MUDAR entre os dois transportes, ou o número de quem voltou ser outro. Terceira: enquanto um controle está fora, a tela conta só os presentes e os de trás sobem um número; o número de quem volta é o de antes a qualquer tempo, enquanto o serviço estiver de pé. As lampadinhas do aparelho levam cerca de meio minuto para acompanhar a tela. Quarta: não segure o PS por tempo demais ao religar — se a Steam vier para a frente, feche-a e refaça.

---

## mapa-identidade.firmware-cabo — Atualização de firmware · cabo

*Célula:* `identidade.firmware @ cabo`

**O que isto prova.** Prova que o Hefesto não promete atualizar o firmware dos controles pelo cabo — não há botão, não há número de versão, e nenhuma tela finge que existe.

**Onde olhar.** Em nenhum campo, e é isso que se prova. Percorra as dez abas, olhando com atenção os três lugares onde uma coisa dessas caberia: a aba Controles, que é onde mora tudo o que é de um controle só (o cartão de cada um, aberto); a aba Conexões, com o quadro Gestão de Controles, onde cada controle abre uma linha, e a seção Rádio e Adaptadores; e a aba Sistema, com os botões do alto (Retomar, Reiniciar o serviço, Atualizar e Parar o serviço) e as seções O exame de hoje, Preparar os jogos e Avançado. A palavra firmware não aparece em aba nenhuma.

**Os passos.**

1. Clique na aba Controles.
2. Clique no chip Todos e leia os cartões do P1 e do P2 de cima a baixo, procurando um número de versão ou um botão de atualizar.
3. Abra a aba Conexões e clique no título Gestão de Controles.
4. Clique na linha do P1 e leia tudo o que ela mostra aberta; depois faça o mesmo com a do P2.
5. Leia também a seção Rádio e Adaptadores, da mesma aba.
6. Abra a aba Sistema e leia os botões do alto e as seções O exame de hoje, Preparar os jogos e Avançado.
7. Pare o mouse em cima do botão Atualizar, sem clicar, e leia a explicação inteira.
8. Percorra as outras abas, uma de cada vez, procurando o mesmo.
9. Anote qualquer campo que fale em versão de controle ou em atualizar controle, dizendo em que aba ele está.
10. Anote onde você encontrou a palavra firmware, se encontrou, e o que a frase inteira dizia.

**Passa quando.** Nenhuma das dez abas oferece atualizar o firmware de um controle, e nenhuma mostra um número de versão de controle — nem para o P1, nem para o P2, que são os dois do cabo e seriam os únicos por onde uma atualização poderia passar. A palavra firmware não aparece em tela nenhuma. E a explicação do botão Atualizar diz que ele relê os atalhos e reescreve os arquivos que a Steam usa — não fala em controle nenhum.

**Por controle.**

* **P1** — No cabo, e é por aqui que uma atualização passaria se existisse — este tipo de coisa só se faz pelo fio. Leia o cartão dele inteiro e a linha dele inteira.
* **P2** — No cabo, o segundo lugar onde procurar, e ele existe para o caso de o campo aparecer num cartão só. Leia o cartão e a linha dele inteiros.
* **P3** — No rádio, testemunha. Confira que ele também não mostra versão nenhuma e, sobretudo, que não aparece nele uma frase do tipo "ligue no cabo para atualizar" — uma frase dessas é o produto prometendo o que não faz.
* **P4** — No rádio, testemunha, mesma conferência e o mesmo cuidado com convites a ligar no cabo.

**A armadilha.** A maior é o botão Atualizar, da aba Sistema: o nome sugere atualização, e ele não manda um byte ao controle — a explicação dele diz que o serviço relê os atalhos do controle e reescreve os arquivos de ambiente que a Steam usa para lançar os jogos. É por isso que o passo manda ler a explicação antes de anotar qualquer coisa. Os outros botões do alto (Retomar, Reiniciar o serviço, Parar o serviço) mexem no Hefesto, não no controle. Segunda: o painel de Detalhes técnicos, em Avançado, é o registro cru do Hefesto; uma linha de registro com a palavra firmware ali não é oferta de nada. Terceira: existem programas de fora e o próprio console da Sony que atualizam o DualSense pelo cabo — o que este teste mede é o HEFESTO, e o registro é claro: ele nunca mandou um byte de atualização a aparelho nenhum, por transporte nenhum, e essa metade do assunto não tem nem um degrau de prova, porque nunca foi tentada. Se você encontrar um botão, isso é o achado e vale mais que o teste inteiro.

---

## mapa-identidade.firmware-radio — Atualização de firmware · rádio

*Célula:* `identidade.firmware @ rádio`

**O que isto prova.** Prova que o Hefesto também não promete nada sobre firmware para os dois controles do rádio — nem versão, nem convite a ligar o cabo para atualizar.

**Onde olhar.** Nos mesmos lugares do lado do cabo, agora no P3 e no P4: o cartão de cada um na aba Controles, aberto; a linha de cada um no quadro Gestão de Controles, na aba Conexões, aberta, e a seção Rádio e Adaptadores; e as seções O exame de hoje e Preparar os jogos, na aba Sistema. Repare também em onde cada aba nomeia o P3 e o P4 — o chip no alto da coluna da aba Gatilhos, a linha Modelo nas abas Iluminação e Vibração —, que diz o número, a cor e BT: é ali que uma ressalva sobre transporte apareceria, se houvesse.

**Os passos.**

1. Clique na aba Controles.
2. Clique no chip Todos e leia os cartões do P3 e do P4 de cima a baixo.
3. Compare com os cartões do P1 e do P2: procure qualquer campo que exista num par e não exista no outro.
4. Abra a aba Conexões, clique no título Gestão de Controles e abra a linha do P3.
5. Leia a linha aberta inteira, procurando versão ou convite a atualizar, e pare o mouse em cima do botão A luz não acende para ler a explicação.
6. Abra a linha do P4 e faça a mesma leitura.
7. Leia a seção Rádio e Adaptadores, da mesma aba.
8. Abra a aba Sistema e leia O exame de hoje e Preparar os jogos, procurando qualquer item que fale em atualizar controle.
9. Percorra as outras abas e leia o que cada uma diz ao lado do P3 e do P4.
10. Anote qualquer frase que sugira que ligar o cabo destravaria uma atualização.

**Passa quando.** O P3 e o P4 não mostram número de versão em lugar nenhum, e nenhuma tela sugere que ligar o cabo permitiria atualizar alguma coisa. O que os cartões do rádio mostram é o mesmo que os cartões do cabo mostram: os dois pares não diferem em nada que fale de firmware.

**Por controle.**

* **P1** — No cabo, testemunha, e ele é a régua da comparação: leia o cartão dele para saber o que é normal aparecer, e só então diga se falta ou sobra alguma coisa nos do rádio.
* **P2** — No cabo, segunda testemunha e segunda régua. Se um campo aparece só num dos dois cartões do cabo, o problema é de cartão, não de transporte.
* **P3** — No rádio, e é um dos dois que este teste examina. Leia o cartão e a linha dele inteiros. Um convite a ligar o cabo, aqui, seria o achado.
* **P4** — No rádio, o segundo examinado. Mesma leitura. Ele importa porque é o último a entrar, e campos que nascem torto costumam nascer torto no último.

**A armadilha.** A tentação aqui é o contrário da do cabo: como se sabe que atualização de firmware, quando existe, é coisa de fio, é fácil ler qualquer frase que mencione o cabo como se fosse uma promessa de atualização. Leia a frase inteira antes de anotar — a explicação do botão A luz não acende fala do cabo e do rádio, e é sobre a barra de luz voltar a obedecer, não firmware. Segunda: o botão Atualizar da aba Sistema não é atualização de controle — ele relê os atalhos e reescreve os arquivos que a Steam usa, e vale igual para os quatro. Terceira, e é o limite honesto deste teste: sobre atualizar firmware não há degrau de prova nenhum registrado, por transporte nenhum — nunca se tentou, nem pelo cabo nem pelo rádio. O que este teste pode afirmar é só o que a tela diz; ele não prova nada sobre o que o aparelho aceitaria.

---

## mapa-identidade.leitura_de_feature-cabo — Ler feature report do aparelho — a regra de leitura, e o que ela custa por rádio · cabo

*Célula:* `identidade.leitura_de_feature @ cabo`

**O que isto prova.** Prova que, quando o Hefesto pergunta uma coisa ao aparelho pelo cabo e a resposta não vem, ele diz que não sabe em vez de escrever um valor bonito — e que, quando ela vem, é sempre a mesma.

**Onde olhar.** A única pergunta desse tipo que chega à tela hoje é a da cor de fábrica do plástico. Ela aparece no cabeçalho do cartão de cada controle, na aba Controles, no chip da fita do topo e na linha do quadro Gestão de Controles, na aba Conexões. Quando a resposta não vem, o cabeçalho do cartão e o chip põem um travessão, e a linha da aba Conexões omite o nome. Sobre as outras coisas que o aparelho sabe responder, a fonte não diz onde se leriam — o produto não as mostra em campo nenhum.

**Os passos.**

1. Clique na aba Controles.
2. Leia o cabeçalho do cartão do P1 e o do P2 e anote o que está no lugar da cor: um nome, ou um travessão.
3. Compare os dois nomes com os plásticos que estão na sua mão.
4. Abra a aba Conexões, clique no título Gestão de Controles e confira que as linhas do P1 e do P2 dizem o mesmo nome que os cartões.
5. Abra a aba Sistema, clique em Reiniciar o serviço e espere a janela voltar; se ela não fechar e abrir sozinha, feche-a pelo X e abra de novo.
6. Espere a contagem no alto voltar a dizer 2 USB · 2 BT.
7. Volte à aba Controles, leia os cabeçalhos do P1 e do P2 e anote a resposta desta volta.
8. Espere dois minutos e meio, leia de novo e anote ao lado.
9. Repita o reinício e as duas leituras mais três vezes.
10. Conte, no papel, quantas das quatro voltas trouxeram nome e quantas trouxeram travessão, para o P1 e para o P2, na primeira leitura e na segunda.
11. Anote também, a cada volta, o que o P3 e o P4 mostraram.

**Passa quando.** Nas quatro voltas o P1 e o P2 terminam respondendo a mesma coisa: ou o nome da cor, sempre o mesmo e sempre o do plástico na sua mão, ou o travessão. O que reprova é o nome MUDAR de uma volta para outra, ou aparecer um nome que não é a cor daquele plástico — isso é o Hefesto aceitando como boa uma resposta que não era a que ele pediu.

**Por controle.**

* **P1** — No cabo. Leia o cabeçalho dele nas quatro voltas, duas vezes em cada uma, e escreva a resposta de cada leitura, em ordem.
* **P2** — No cabo, e é a segunda amostra. Se um responde sempre e o outro nunca, o achado é daquele aparelho, não do caminho — e essa distinção só existe porque são dois.
* **P3** — No rádio, testemunha. Anote a resposta dele nas quatro voltas também. Ela é o que separa "o cabo falhou" de "o Hefesto não perguntou a ninguém nesta volta".
* **P4** — No rádio, testemunha, mesma anotação. Quatro travessões nos quatro controles em todas as voltas é um resultado diferente de dois travessões só no cabo, e a anotação é o que permite dizer qual dos dois aconteceu.

**A armadilha.** O reinício é o gesto do teste, e sem ele o teste vira uma foto: o Hefesto guarda a resposta boa até o serviço reiniciar, então ler quatro vezes seguidas é ler quatro vezes a mesma resposta guardada. Reinicie sem jogo aberto: o reinício derruba e levanta os controles que o jogo enxerga. Segunda: a leitura da cor confere se a resposta que voltou é a da pergunta que ela fez, e pergunta de novo depois de 5 segundos, de 30 e de 120 quando a resposta não vem. Um travessão na primeira leitura que vira nome na segunda é o produto funcionando, e a contagem das duas é o dado. Um nome de cor que muda entre voltas, ou que não é a cor do plástico, é resposta trocada aceita como boa — foi esse defeito que se mediu nesta casa com um controle, e é ele que este teste procura. Terceira: travessão em todas as voltas, nos quatro, não prova defeito sozinho — pode ser a porta do aparelho fechada neste computador. Anote como "ninguém respondeu" e não como "o Hefesto errou". Quarta, e é o limite: esta linha do mapa não tem degrau de prova preenchido. A leitura da cor é a única que chega à tela e a única que confere a resposta; tudo o mais que o aparelho sabe responder continua sem conferência e sem nova tentativa, foi lido só por instrumento de fora, e nunca chegou à tela.

---

## mapa-identidade.leitura_de_feature-radio — Ler feature report do aparelho — a regra de leitura, e o que ela custa por rádio · rádio

*Célula:* `identidade.leitura_de_feature @ rádio`

**O que isto prova.** Prova a mesma coisa pelo rádio: quando a pergunta ao aparelho sem fio não volta, a tela diz que não sabe, e quando volta ela diz sempre a mesma coisa.

**Onde olhar.** Os mesmos lugares, agora no P3 e no P4: o cabeçalho do cartão na aba Controles, o chip da fita do topo e a linha do quadro Gestão de Controles, na aba Conexões. Sem leitura, o cabeçalho e o chip põem travessão e a linha omite o nome. A fonte não diz onde se leria qualquer outra resposta do aparelho pelo rádio — o produto não mostra nenhuma.

**Os passos.**

1. Clique na aba Controles.
2. Leia o cabeçalho do cartão do P3 e o do P4 e anote: nome, ou travessão.
3. Compare os dois nomes, se houver, com os plásticos que estão na sua mão.
4. Abra a aba Sistema, clique em Reiniciar o serviço e espere a janela voltar; se ela não fechar e abrir sozinha, feche-a pelo X e abra de novo, sem mexer em nenhum controle.
5. Espere a contagem no alto voltar a dizer 2 USB · 2 BT.
6. Volte à aba Controles, leia os cabeçalhos do P3 e do P4 e anote.
7. Espere dois minutos e meio, leia de novo e anote ao lado.
8. Repita o reinício e as duas leituras mais três vezes.
9. Anote também, a cada volta, o que o P1 e o P2 responderam.
10. Conte no papel quantas voltas trouxeram nome e quantas trouxeram travessão, controle por controle, na primeira leitura e na segunda.

**Passa quando.** Nas quatro voltas o P3 e o P4 terminam respondendo a mesma coisa: ou o nome da cor, sempre o mesmo e sempre o do plástico na sua mão, ou o travessão. Um nome que muda entre voltas, ou que não é a cor daquele plástico, reprova. Uma volta com nome e outra com travessão no MESMO controle não reprova sozinha — é o que este teste está medindo, e o número de vezes é o dado.

**Por controle.**

* **P1** — No cabo, testemunha e régua. Anote a resposta dele nas quatro voltas: se o cabo responde sempre e o rádio não, a diferença é do transporte, e é isso que este teste mede.
* **P2** — No cabo, segunda régua. Mesma anotação nas quatro voltas.
* **P3** — No rádio, e é um dos dois medidos. Conte quantas das quatro voltas trouxeram nome. Se trouxe em algumas e travessão em outras, escreva quantas de quantas — esse número É o resultado.
* **P4** — No rádio, o segundo medido. Mesma contagem. Os dois juntos dizem se a falha é de um aparelho ou do caminho sem fio.

**A armadilha.** A intuição erra o sentido aqui, e vale saber antes: pelo rádio essas perguntas foram medidas MAIS RÁPIDAS que pelo cabo — centésimos de segundo contra dois décimos. Então lentidão não é o esperado. O que existe é um limite do sistema: quando uma resposta sem fio demora demais, ela é abandonada perto dos três segundos. A leitura da cor pergunta de novo depois de 5 segundos, de 30 e de 120, e só então desiste até o controle sair e voltar — é por isso que cada volta tem duas leituras, e as quatro voltas existem porque uma volta só mede um instante. Segunda: o reinício é obrigatório, porque o Hefesto guarda a resposta boa até o serviço reiniciar; sem ele você lê quatro vezes a mesma resposta guardada. Reinicie sem jogo aberto. Terceira: se um controle do rádio dormir e cair no meio das voltas, a volta seguinte não mede nada — confira que os quatro chips estão na fita antes de cada leitura. Quarta, e é o limite: esta linha do mapa não tem degrau de prova preenchido, e tudo o que se leu pelo rádio além da cor foi lido por instrumento de fora, com o Hefesto de pé — não pelo produto.

---

## mapa-identidade.pareamento-cabo — Pareamento / bond e esquecer o host · cabo

*Célula:* `identidade.pareamento @ cabo`

**O que isto prova.** Prova que, com o controle no cabo, o Hefesto recusa o gesto de refazer a conexão sem fio — e diz por quê, em vez de fingir que fez.

**Onde olhar.** Aba Conexões, quadro Gestão de Controles, que nasce recolhido e se abre clicando no título. Cada controle ligado é uma linha, e clicar na linha abre só ela: dentro vêm Microfone e botões, Limite da vibração e um botão escrito A luz não acende. Na linha de um controle que está no cabo esse botão nasce APAGADO, num cinza diferente dos botões que funcionam, e a explicação aparece ao parar o mouse em cima: ela diz que ele só vale no rádio. Parear um aparelho NOVO mora em outra seção da mesma aba, Rádio e Adaptadores, com Conectar e Parear ao lado de cada aparelho que o Hefesto achou por perto; esquecer um controle já pareado não existe em aba nenhuma.

**Os passos.**

1. Clique na aba Conexões.
2. Clique no título Gestão de Controles para abrir o quadro.
3. Leia a contagem no alto do quadro e confira que ela diz 4 controles, 2 no cabo e 2 no rádio.
4. Confira que as linhas do P1 e do P2 terminam com USB.
5. Clique na linha do P1 para abri-la e ache o botão A luz não acende.
6. Repare que ele está apagado, num tom diferente dos botões que funcionam.
7. Pare o mouse em cima do botão, sem clicar, e anote a explicação inteira.
8. Clique no botão mesmo assim e olhe a borda dele: ela pisca em laranja.
9. Olhe o P1 e confirme que ele não apagou e não caiu, e que a linha dele não passou a pedir o PS nem mostrou o botão Cancelar.
10. Repita na linha do P2, da abertura da linha até a conferência do P2 aceso.
11. Clique na linha do P3 e confira que ali o mesmo botão está no tom normal, e não apagado — não clique nele.
12. Leia a seção Rádio e Adaptadores e anote se existe, para um controle já ligado, algum botão de esquecer ou de desparear.

**Passa quando.** Nas duas linhas dos controles do cabo o botão está apagado, a explicação diz que ele só vale no rádio, e clicar não derruba o controle — a borda do botão só pisca em laranja. Na linha de um controle do rádio o mesmo botão está no tom normal. E em nenhuma aba existe um botão de esquecer um controle já pareado.

**Por controle.**

* **P1** — No cabo, e é um dos dois que têm de recusar. Abra a linha dele, leia a explicação parando o mouse em cima, clique e confirme que ele continua ligado e aceso.
* **P2** — No cabo, o segundo que tem de recusar. Ele existe porque uma recusa pode estar presa a uma linha só — com dois, ou a recusa vale para o transporte, ou está escrita à mão em um lugar.
* **P3** — No rádio, testemunha, e é a contraprova do teste: se o botão estiver apagado NELE também, a recusa não está olhando o transporte de cada controle — está desligada para todo mundo, e o verde do cabo veio por acaso.
* **P4** — No rádio, segunda testemunha, e o mesmo olhar: o botão dele tem de estar no tom normal. Não clique em nenhum dos dois.

**A armadilha.** A recusa que interessa é a que EXPLICA, e a explicação mora no próprio botão: por isso o passo é parar o mouse em cima e ler a frase inteira ANTES de clicar. Depois do clique a tela não escreve nada — a resposta é a borda piscar em laranja, que é como toda recusa desta interface se mostra; não procure recado. Segunda: não clique no botão do P3 nem no do P4 para conferir se funciona — ali ele derruba o controle do rádio de verdade, e isso é outro teste. Terceira: o Parear da seção Rádio e Adaptadores é para um aparelho novo que o Hefesto achou por perto, e não é este teste; não clique nele aqui. Quarta: o Hefesto não guarda o pareamento dentro do controle. O que existe é um salva-vidas que copia o pareamento do lado do computador; ele é de linha de comando, pede senha de administrador, e a volta é feita à mão — nada disso é tela. Quinta: a porta que escreveria o pareamento dentro do aparelho existe e só existe pelo cabo, e ela nunca foi usada nesta casa, de propósito — mal formada, ela reescreve o pareamento de um controle que você está usando.

---

## mapa-identidade.pareamento-radio — Pareamento / bond e esquecer o host · rádio

*Célula:* `identidade.pareamento @ rádio`

**O que isto prova.** Prova que, com o controle no rádio, o Hefesto derruba a conexão sem fio, pede o PS e devolve o controle ao mesmo lugar — sem abrir um segundo assento para ele.

**Onde olhar.** Aba Conexões, quadro Gestão de Controles, que se abre clicando no título: a contagem no alto (4 controles • 2 no cabo • 2 no rádio), a linha de cada controle (Sony • Player 3 • cor • BT) e, dentro da linha aberta, o botão A luz não acende, cuja explicação diz que ele derruba o controle do rádio e que o PS é seu. Depois do clique, a espera se escreve na linha do controle: ▲ Aperte PS no controle · procurando…, com os segundos correndo a partir de 60, e o mesmo botão passa a dizer Cancelar. No aparelho: a fileira de cinco lampadinhas brancas embaixo do touchpad, que é o que diz o número do jogador.

**Os passos.**

1. Clique na aba Conexões.
2. Clique no título Gestão de Controles para abrir o quadro.
3. Anote a contagem no alto do quadro e o número de Player das quatro linhas.
4. Confira que a linha do P3 termina com BT, e clique nela para abri-la.
5. Pare o mouse em cima do botão A luz não acende, leia a explicação e clique nele.
6. Olhe o P3 e confirme que ele apagou e caiu.
7. Anote o que a tela mostra agora: se o pedido de PS com os segundos correndo e o botão Cancelar estão à vista, e em qual linha.
8. Confira que a linha que era do P4 passou a dizer Player 3, e que as do P1 e do P2 não mudaram.
9. Aperte uma vez o botão PS do P3 e espere o chip dele voltar à fita do topo.
10. Leia de novo a contagem e as quatro linhas: o P3 voltou como Player 3, e o P4 voltou a ser Player 4.
11. Espere meio minuto, vire o P3 para cima e conte quais das cinco lampadinhas embaixo do touchpad estão acesas.
12. Refaça no P4, da abertura da linha até as lampadinhas.

**Passa quando.** O P3 cai de verdade — ele apaga —, e depois do PS ele volta com o mesmo número de Player, sem que nenhuma linha nova apareça para o mesmo controle. A contagem do alto volta ao número de antes, e as lampadinhas dele, meio minuto depois, mostram o número dele. O P4 faz o mesmo quando chega a vez dele. E o P1 e o P2 não se mexem em momento nenhum.

**Por controle.**

* **P1** — No cabo, testemunha. Anote o número de Player dele antes, e olhe a linha dele DURANTE a ausência do P3, não só no fim: ele está na frente do P3 na fila, e não pode mudar.
* **P2** — No cabo, testemunha, mesma vigilância durante a ausência.
* **P3** — No rádio, e é ESTE primeiro. Abra a linha dele, clique em A luz não acende, veja o controle apagar, aperte o PS uma vez e espere voltar.
* **P4** — No rádio, e é ele que fecha o teste: o segundo do mesmo transporte, feito depois. Enquanto o P3 está fora ele aparece como Player 3, e volta a Player 4 quando o P3 volta. Se o P3 volta certo e o P4 não, o achado é do quarto lugar na fila, não do rádio.

**A armadilha.** O falso verde é olhar só a tela: se a borda do botão piscar em laranja e o controle não apagar, nada foi derrubado e nada foi reconectado — o teste não provou coisa nenhuma, refaça. Olhe o controle: se ele não apagou, não caiu. Segunda: enquanto o P3 está fora, a tela conta só os presentes e o P4 sobe para Player 3; isso é a regra do produto, e não o defeito. O número do P3 volta a qualquer tempo enquanto o serviço estiver de pé — o que reprova é ele voltar com outro número ou aparecer uma linha a mais. As lampadinhas do aparelho levam cerca de meio minuto para acompanhar a tela, e é por isso que o passo espera antes de contar. Terceira: Cancelar não religa nada — se você clicar nele, o controle fica fora do rádio até você apertar o PS por conta própria. Quarta: este gesto refaz a conexão de um controle que JÁ está pareado neste computador. Parear um aparelho novo é na seção Rádio e Adaptadores, e não é este teste; se aquele controle nunca foi pareado aqui, o PS não o traz de volta e o teste não roda.

---

## mapa-identidade.req_dev_info-cabo — REQ_DEV_INFO — endereço de rádio e tipo do controle · cabo

*Célula:* `identidade.req_dev_info @ cabo`

**O que isto prova.** Prova que o Hefesto distingue cada controle do cabo pelo endereço do próprio aparelho, e não pelo cabo nem pela porta — trocar de porta não cria um controle novo, e trocar os cabos não troca as identidades.

**Onde olhar.** A contagem no alto de qualquer aba (2 USB · 2 BT). A fita do topo, com um chip por controle. A aba Controles, com um cartão por controle. E, sobretudo, a aba Conexões, quadro Gestão de Controles (clique no título para abrir): a contagem do quadro diz quantos estão no cabo e quantos no rádio, e cada controle é uma linha que começa com a marca — Sony — seguida do Player, da cor do plástico e de USB ou BT. O endereço do aparelho em si não aparece em campo nenhum da tela, e isso é decisão registrada: ele é chave de dentro do produto, não vocabulário de tela. O que você vê é a consequência dele.

**Os passos.**

1. Clique na aba Conexões.
2. Clique no título Gestão de Controles para abrir o quadro.
3. Leia a contagem no alto do quadro, conte as linhas — têm de ser quatro — e anote as quatro linhas inteiras, palavra por palavra.
4. Desencaixe do PC o cabo do P1 e encaixe-o numa porta USB diferente.
5. Espere o chip do P1 voltar à fita do topo.
6. Confira que continuam quatro linhas, que nenhuma linha nova apareceu para o P1, e que ele voltou com o mesmo número, a mesma cor e a mesma marca.
7. Desencaixe os DOIS cabos do PC ao mesmo tempo; se o P1 ou o P2 voltar sozinho pelo BT, segure o PS dele até apagar.
8. Espere a contagem no alto da janela mostrar só os dois do BT.
9. Encaixe os dois cabos de novo, TROCADOS: o cabo que estava no P1 vai para o P2, e o do P2 vai para o P1.
10. Espere os dois voltarem à fita e leia as quatro linhas outra vez.
11. Compare a cor e o número de cada linha com o plástico do controle que está na sua mão.
12. Abra a aba Navegação e leia quem diz Navega o PC: se for um controle do BT, segure o PS do P3 e do P4 até apagarem, espere meio minuto e ligue os dois de novo com um toque no PS — se a Steam vier para a frente, feche-a.

**Passa quando.** Com quatro controles ligados há sempre quatro linhas, quatro cartões e quatro chips — nunca três, nunca cinco. Trocar o P1 de porta USB não cria uma linha nova nem apaga a dele. E depois de trocar os dois cabos entre si, cada controle continua carregando a cor do plástico DELE e o número dele: o Hefesto seguiu o aparelho, e não o cabo nem a porta.

**Por controle.**

* **P1** — No cabo. É ele que muda de porta USB e depois troca de cabo com o P2. Tem de voltar sempre com a mesma cor, o mesmo número e a mesma marca.
* **P2** — No cabo, e é ele que denuncia o defeito: recebe o cabo do P1 na segunda metade. Se depois da troca ele aparecer com a cor ou o número do P1, o Hefesto está identificando o CABO e não o aparelho.
* **P3** — No rádio, testemunha. Enquanto os do cabo estão fora, a linha dele sobe na lista e volta ao lugar quando eles voltam; ela não pode sumir nem trocar de cor, e a contagem do quadro tem de continuar dizendo dois no rádio o tempo todo.
* **P4** — No rádio, testemunha, mesma conferência. Se os dois do rádio piscarem para fora do quadro quando você desencaixa os dois cabos, o achado é outro e vale anotar à parte.

**A armadilha.** Não procure o endereço do controle na tela: ele não está lá, e não é esquecimento — foi decidido que na tela um controle fala por número, cor e marca, e que o endereço é chave de dentro. Um teste que mandasse achar o endereço mandaria você caçar um campo que não existe. Segunda: enquanto um controle está fora, a tela conta só os presentes, e os de trás sobem um número; quando ele volta, cada um recupera o seu, a qualquer tempo, enquanto o serviço estiver de pé. Então o número no fim é prova, e não ruído: o P1 voltar com o número do P2 é o Hefesto seguindo o cabo. Terceira: um controle que perde o cabo pode voltar sozinho pelo BT; se isso acontecer antes do cabo trocado, apague-o pelo PS, senão ele entra pelo rádio e o teste mede outra coisa. Quarta: o posto de Navega o PC não volta com o número — com os dois do cabo fora por mais de meio minuto, ele fica com um controle do BT, e o último passo existe para devolvê-lo. Quinta: se um dos dois do cabo aparecer sem nome de cor depois da troca, isso é a leitura da cor não tendo respondido, e tem teste próprio; o que reprova AQUI é a cor aparecer no controle errado.

---

## mapa-identidade.req_dev_info-radio — REQ_DEV_INFO — endereço de rádio e tipo do controle · rádio

*Célula:* `identidade.req_dev_info @ rádio`

**O que isto prova.** Prova que o Hefesto reconhece cada controle do rádio pelo aparelho, e não pela ordem de chegada — ligar os dois na ordem invertida não faz a cor nem o número trocarem de dono.

**Onde olhar.** Aba Conexões, quadro Gestão de Controles (clique no título para abrir): a contagem no alto e a linha de cada controle, Sony • Player 3 • cor • BT. Também a fita do topo, com um chip por controle, e a aba Controles, com um cartão por controle. O endereço do aparelho não aparece em campo nenhum — ele é chave de dentro do produto. O que se vê é a consequência: quem é quem depois de todo mundo sair e voltar fora de ordem.

**Os passos.**

1. Clique na aba Conexões.
2. Clique no título Gestão de Controles para abrir o quadro.
3. Copie as quatro linhas num papel, palavra por palavra, e anote ao lado de cada uma qual plástico ela é.
4. Segure o PS do P3 até todas as luzes dele apagarem, e depois o do P4.
5. Confira que a contagem no alto da janela passou a mostrar só os dois do USB antes de religar qualquer um.
6. Dê um toque no PS do controle que ANTES era o P4 — agora ele entra primeiro — e veja o chip dele aparecer na fita.
7. Leia a linha dele e anote: enquanto ele está sozinho no BT, ele aparece como Player 3.
8. Dê um toque no PS do controle que antes era o P3 e veja o chip dele aparecer.
9. Leia as quatro linhas de novo e compare a COR e o NÚMERO de cada uma com o que você anotou no começo.
10. Conte as linhas e confira que continuam quatro, sem nenhum controle repetido.

**Passa quando.** Cada um dos dois controles do rádio voltou carregando a cor do plástico DELE, mesmo tendo entrado na ordem invertida. Enquanto só o antigo P4 estava de volta ele aparecia como Player 3, e, com os dois de volta, cada um recuperou o próprio número. E continuam quatro linhas, sem nenhuma sobrando e sem nenhum controle aparecendo duas vezes.

**Por controle.**

* **P1** — No cabo, testemunha. A linha dele não pode sumir nem trocar de cor ou de número enquanto os do rádio saem e voltam.
* **P2** — No cabo, testemunha, mesma conferência. Os dois do cabo juntos provam que a bagunça, se houver, ficou no rádio.
* **P3** — No rádio. Sai primeiro e volta por último — o inverso da ordem em que entrou no começo.
* **P4** — No rádio, e é ele que denuncia o defeito: sai por último e volta primeiro. Se, com os dois de volta, ele ficar com a cor ou o número que estavam na terceira posição, o nome está vindo do LUGAR e não do aparelho — isso já aconteceu nesta casa e é exatamente o que este teste caça.

**A armadilha.** A ordem de partida importa, e é por isso que a primeira coisa a fazer é copiar as quatro linhas — se você não tiver certeza de quem entrou primeiro, o papel do começo é quem responde. O número na tela é contado só entre os presentes, pela ordem em que cada controle chegou pela primeira vez desde que o serviço subiu: enquanto o antigo P3 está fora, o antigo P4 aparece como Player 3, e isso não é defeito; com os dois de volta, cada um tem de recuperar o seu. Não reinicie o serviço no meio do teste — o reinício apaga essa ordem, e aí os números passam a seguir a ordem de entrada. As lampadinhas do aparelho levam cerca de meio minuto para acompanhar a tela; olhe a tela. Segunda: se um dos dois voltar sem nome de cor, a linha simplesmente não traz o nome, e isso é achado da leitura da cor pelo rádio, que tem teste próprio; aqui o que reprova é a cor TROCAR DE DONO. Terceira: espere a contagem cair antes de religar — religar com o Hefesto ainda contando quatro mede outra coisa. Quarta: não plugue cabo em nenhum dos dois durante o teste — pelo cabo a identidade tem outro caminho, e uma passagem pelo fio no meio embaralharia o resultado.

---

## mapa-identidade.revisao_de_placa-cabo — Revisão de placa (`hardware_version` do sysfs) — NÃO é a cor · cabo

*Célula:* `identidade.revisao_de_placa @ cabo`

**O que isto prova.** Prova que o Hefesto nunca nomeia um controle do cabo por um número de placa — o crachá na tela é o número do jogador, a cor e a marca, e mais nada.

**Onde olhar.** Em nenhum campo, e é isso que se prova. Os lugares onde um controle é NOMEADO na tela são estes: o chip da fita do topo (número, cor e USB ou BT); o cabeçalho do cartão na aba Controles; o cartão dele em O controle é visto como:, na aba Jogar; os cartões do alto da aba Navegação; o chip no alto da coluna dele na aba Gatilhos; a linha Modelo nas abas Iluminação e Vibração; a linha do quadro Gestão de Controles, na aba Conexões (marca, Player, cor, USB ou BT); e o nome de cada aparelho na seção Rádio e Adaptadores, da mesma aba. Em nenhum deles deve aparecer um número de placa, uma sigla de revisão ou um número em hexadecimal — aqueles que começam com zero-x.

**Os passos.**

1. Clique na aba Controles.
2. Leia os quatro chips da fita do topo e escreva no papel exatamente o que cada um diz.
3. Clique no chip Todos e leia os cartões do P1 e do P2 inteiros, procurando um número de placa ou de revisão.
4. Abra a aba Conexões, clique no título Gestão de Controles e leia as linhas do P1 e do P2, abertas.
5. Leia também os nomes dos aparelhos na seção Rádio e Adaptadores.
6. Abra as abas Jogar, Gatilhos, Iluminação, Vibração e Navegação e leia, em cada uma, onde o P1 e o P2 são nomeados.
7. Anote qualquer número que apareça junto do nome de um controle e que não seja bateria, volume, brilho, porcentagem ou o código de cor que começa com #.
8. Se algum número aparecer, anote em que aba, em que campo e qual controle, e compare o do P1 com o do P2.

**Passa quando.** Em nenhum lugar da tela o P1 ou o P2 é nomeado por um número de placa, uma revisão ou um número em hexadecimal. O que os nomeia é o número do jogador, a cor do plástico, a marca e USB ou BT.

**Por controle.**

* **P1** — No cabo. Leia todos os lugares onde ele é nomeado: o chip, o cabeçalho do cartão, os cartões e colunas das outras abas e a linha da aba Conexões.
* **P2** — No cabo, e ele importa por uma razão precisa: a placa dele é DIFERENTE da do P1 nesta bancada. Se algum campo mostrasse a placa, os dois números apareceriam diferentes e seria fácil confundir isso com identidade de verdade.
* **P3** — No rádio, testemunha. A mesma varredura em todos os lugares, para o caso de o número aparecer só de um lado.
* **P4** — No rádio, testemunha, mesma varredura.

**A armadilha.** Este número existe, o computador o lê de graça, sem senha e sem atrapalhar nada, e os quatro controles desta bancada têm valores diferentes — o que o faz PARECER um bom crachá. Ele não é, e a decisão de não usá-lo está registrada: ele diz a revisão da PLACA, e os quatro só se distinguem porque foram comprados em lotes diferentes. Dois controles da mesma cor comprados juntos teriam o mesmo número, e quem nomeasse jogador por ele veria dois "controles iguais" no dia da compra. Segunda: o código ao lado de Barra de luz, no cartão da aba Controles — algo como #7EB8D4 —, é a cor que o Hefesto pinta na barra daquele jogador, e não placa. Terceira: não confunda com o nome de fábrica da cor, como Cosmic Red, que o Hefesto tira do aparelho e aparece legitimamente. Quarta, e vale como aviso e não como reprovação: se um número de placa aparecer na tela, ele pode estar IGUAL nos quatro — o controle de mentira que o Hefesto cria para o jogo carrega gravada a placa de um dos controles desta bancada. Um número igual nos quatro não é sinal de que a leitura funciona; é sinal do contrário.

---

## mapa-identidade.revisao_de_placa-radio — Revisão de placa (`hardware_version` do sysfs) — NÃO é a cor · rádio

*Célula:* `identidade.revisao_de_placa @ rádio`

**O que isto prova.** Prova que o Hefesto também não nomeia um controle do rádio por número de placa — nem quando ele cai e volta, que é quando um produto desesperado se agarraria a qualquer número.

**Onde olhar.** Os mesmos lugares onde um controle é nomeado: o chip da fita do topo, o cabeçalho do cartão na aba Controles, o cartão em O controle é visto como: na aba Jogar, os cartões do alto da aba Navegação, o chip no alto da coluna na aba Gatilhos, a linha Modelo nas abas Iluminação e Vibração, a linha do quadro Gestão de Controles e o nome de cada aparelho em Rádio e Adaptadores, na aba Conexões. Nenhum deles deve trazer número de placa, sigla de revisão ou número em hexadecimal — nem com os controles estáveis, nem no instante em que um deles reaparece.

**Os passos.**

1. Clique na aba Controles.
2. Leia os chips do P3 e do P4 na fita do topo e escreva no papel o que cada um diz.
3. Clique no chip Todos e leia os cartões do P3 e do P4 inteiros, procurando número de placa ou de revisão.
4. Abra a aba Conexões, clique no título Gestão de Controles e leia as linhas do P3 e do P4, abertas, e os nomes dos aparelhos na seção Rádio e Adaptadores.
5. Abra as abas Jogar, Gatilhos, Iluminação, Vibração e Navegação e leia, em cada uma, onde o P3 e o P4 são nomeados.
6. Volte à aba Conexões e segure o PS do P3 até todas as luzes dele apagarem.
7. Espere a contagem do quadro Gestão de Controles cair para três controles.
8. Aperte o PS do P3 uma vez para religá-lo, e leia a linha dele no instante em que ela reaparece.
9. Abra o cartão do P3 na aba Controles e leia de novo, procurando qualquer número que não estivesse lá antes.
10. Anote qualquer número que apareça, dizendo em que aba, em que campo e em que momento.

**Passa quando.** Nem com os quatro parados, nem no instante em que o P3 reaparece, nenhum campo mostra um número de placa, uma revisão ou um número em hexadecimal. O P3 e o P4 continuam nomeados por número de jogador, cor, marca e BT — antes e depois da queda.

**Por controle.**

* **P1** — No cabo, testemunha. Leia o cabeçalho do cartão dele antes e depois da queda do P3: nenhum número novo pode nascer ali por causa do vizinho.
* **P2** — No cabo, testemunha, mesma leitura antes e depois.
* **P3** — No rádio, e é ESTE que cai e volta. O instante do reaparecimento é o momento do teste: é aí que um produto que não sabe quem chegou se agarraria a um número de placa para decidir.
* **P4** — No rádio, testemunha, e a que mais importa: é o outro do mesmo transporte. Enquanto o P3 está fora ele aparece como Player 3 — é a tela contando só os presentes. Se um número de placa aparecer nele nesse meio-tempo, o achado é do rádio ficar sozinho, não da volta.

**A armadilha.** A leitura deste número não muda com o transporte: ela sai do mesmo lugar no computador, de graça, esteja o controle no cabo ou no rádio. Então não espere ver uma diferença entre este teste e o do cabo — o que muda aqui é o MOMENTO em que se olha, e o momento é o da volta. Segunda: os quatro controles desta bancada têm placas diferentes, e isso é acaso de lote, não identidade; dois da mesma cor comprados juntos teriam o mesmo número. Terceira: o código ao lado de Barra de luz, no cartão — algo como #7EB8D4 —, é a cor da barra daquele jogador, e não placa. Quarta: se um número de placa aparecer, confira se ele é IGUAL nos quatro antes de comemorar — o controle de mentira que o Hefesto cria para o jogo carrega gravada a placa de um dos aparelhos desta bancada, e um número igual nos quatro é sinal de que ninguém leu nada. Quinta: enquanto o P3 está fora, o P4 aparece como Player 3 e volta a Player 4 quando o P3 volta; isso é a tela contando os presentes, e não a placa mandando na identidade.

---

# luz

---

## mapa-luz.led_jogador-cabo — LED de jogador (as lâmpadas de numeração) · cabo

*Célula:* `luz.led_jogador @ cabo`

**O que isto prova.** Prova que dar outro número a um controle do cabo muda as cinco lâmpadas dele no plástico — junto com as do controle com quem ele troca — e que os dois do rádio não se mexem.

**Onde olhar.** O que decide é o APARELHO: a fileira de cinco lâmpadas brancas entre o touchpad e o botão PS. Na aba Iluminação cada controle tem uma coluna; na linha «Jogador» ficam os botões 1, 2, 3 e 4, e o aceso é o número daquele controle hoje (passe o mouse: a dica diz com quem ele vai trocar). Na linha «Modelo» o nome de cada coluna termina em USB (cabo) ou BT (rádio). A linha «LEDs» desenha as cinco lâmpadas no desenho do número. Os desenhos: 1 é só a do meio; 2 é a segunda e a quarta; 3 é as duas pontas e a do meio; 4 é as quatro de fora, com a do meio apagada.

**Os passos.**

1. Abra a aba Iluminação.
2. Confira na linha «Modelo» que as colunas do P1 e do P2 terminam em USB e as do P3 e do P4 em BT.
3. Anote o desenho das cinco lâmpadas de cada um dos quatro aparelhos.
4. Clique no botão «2» da linha «Jogador», na coluna do P1.
5. Confira no aparelho em que você mexeu que as lâmpadas viraram a segunda e a quarta.
6. Confira no outro aparelho do cabo, que ficou com o 1, que as lâmpadas viraram só a do meio.
7. Confira que nenhuma lâmpada dos dois aparelhos do rádio mudou.
8. Ache a coluna em que o aparelho que você mexeu aparece agora, com P2 na linha «Modelo», e clique no «1» da linha «Jogador» dela.
9. Confira nos quatro aparelhos que as lâmpadas voltaram ao desenho anotado.

**Passa quando.** Com um clique, as lâmpadas dos DOIS controles do cabo trocam de desenho no plástico: quem recebeu o 2 mostra a segunda e a quarta, quem ficou com o 1 mostra só a do meio. As dos dois do rádio não mudam em instante nenhum. E desfazer devolve os quatro ao desenho do começo.

**Por controle.**

* **P1** — Cabo, e é a coluna em que você clica. Dê a ele o 2 e veja as lâmpadas dele virarem o desenho do 2 no plástico.
* **P2** — Cabo, e não se clica na coluna dele: ele recebe o 1 pela troca, no mesmo instante. Sem ele a troca ficou pela metade.
* **P3** — Rádio, testemunha. Não toque. Nenhuma lâmpada pode mudar; se mudar, o clique pegou mais que os dois do cabo.
* **P4** — Rádio, segunda testemunha. Não toque. O número dele tem de continuar o mesmo no fim.

**A armadilha.** Três. (1) O número é o CONJUNTO aceso, e os desenhos são simétricos: quem lê «a terceira acesa» como jogador 3 reprova um produto certo. (2) Com um jogo aberto o botão recusa: a borda dele pisca laranja e nada troca — o produto se nega a repintar no meio da partida. Feche o jogo e refaça. (3) No mapa desta casa esta linha parou em MONTOU: ninguém registrou a troca saindo no fio. Se as lâmpadas não mudarem, anote e siga — este teste é a medição que faltava, não erro seu. Não julgue pela tela: a linha «LEDs» desenha o número, nunca o plástico.

---

## mapa-luz.led_jogador-radio — LED de jogador (as lâmpadas de numeração) · rádio

*Célula:* `luz.led_jogador @ rádio`

**O que isto prova.** Prova que dar outro número a um controle do rádio muda as cinco lâmpadas dele no plástico — junto com as do controle com quem ele troca — e que os dois do cabo não se mexem.

**Onde olhar.** O que decide é o APARELHO: a fileira de cinco lâmpadas brancas entre o touchpad e o botão PS. Na aba Iluminação, a linha «Jogador» de cada coluna, com os botões 1, 2, 3 e 4; o nome da coluna, na linha «Modelo», termina em BT para quem está no rádio. Os desenhos: 3 é as duas pontas e a do meio; 4 é as quatro de fora, com a do meio apagada.

**Os passos.**

1. Abra a aba Iluminação.
2. Confira na linha «Modelo» que as colunas do P3 e do P4 terminam em BT e as do P1 e do P2 em USB.
3. Anote o desenho das cinco lâmpadas de cada um dos quatro aparelhos.
4. Clique no botão «4» da linha «Jogador», na coluna do P3.
5. Confira no aparelho em que você mexeu que as lâmpadas viraram as quatro de fora, com a do meio apagada.
6. Confira no outro aparelho do rádio, que ficou com o 3, que as lâmpadas viraram as duas pontas e a do meio.
7. Confira que nenhuma lâmpada dos dois aparelhos do cabo mudou.
8. Ache a coluna em que o aparelho que você mexeu aparece agora, com P4 na linha «Modelo», e clique no «3» da linha «Jogador» dela.
9. Confira nos quatro aparelhos que as lâmpadas voltaram ao desenho anotado.

**Passa quando.** Com um clique, as lâmpadas dos DOIS controles do rádio trocam de desenho no plástico: quem recebeu o 4 mostra as quatro de fora, quem ficou com o 3 mostra as pontas e o meio. As dos dois do cabo não mudam em instante nenhum. E desfazer devolve os quatro ao desenho do começo.

**Por controle.**

* **P1** — Cabo, testemunha. Não toque. É ele que separa «o clique foi ao controle escolhido» de «o clique pegou a máquina inteira».
* **P2** — Cabo, segunda testemunha. Não toque. Se ele mudar e o P1 não, anote qual.
* **P3** — Rádio, e é a coluna em que você clica. Dê a ele o 4 e veja as lâmpadas dele virarem o desenho do 4 no plástico.
* **P4** — Rádio, e não se clica na coluna dele: ele recebe o 3 pela troca, no mesmo instante.

**A armadilha.** Quatro. (1) O número é o conjunto aceso, e os desenhos são simétricos: não conte da esquerda para a direita. (2) Com um jogo aberto o botão recusa, com a borda piscando laranja: é o produto funcionando. (3) Esta linha parou em MONTOU nos dois transportes, então «as lâmpadas não mudaram» é achado, não erro seu. (4) Só do rádio: se o controle cair e voltar no meio do gesto, o que você vê é a reconexão, não a troca — se o chip dele sumir da fita do topo, refaça.

---

## mapa-luz.led_jogador.escrita_hefesto-cabo — LED de jogador — escrita pelo Hefesto · cabo

*Célula:* `luz.led_jogador.escrita_hefesto @ cabo`

**O que isto prova.** Prova que, quando um controle entra pelo cabo, o Hefesto escreve nas cinco lâmpadas dele o desenho do número que ele tem, por cima do desenho que o Linux acende sozinho — e que não mexe nos outros três.

**Onde olhar.** No aparelho: as cinco lâmpadas brancas entre o touchpad e o botão PS, nos primeiros segundos depois de encaixar o cabo. Na aba Iluminação: a linha «Jogador» (o número de cada coluna, que não pode mudar) e a linha «LEDs» (o desenho que a tela atribui ao número). Os desenhos: 1 é só a do meio; 2 é a segunda e a quarta.

**Os passos.**

1. Abra a aba Iluminação.
2. Anote o número aceso na linha «Jogador» de cada coluna e o desenho das lâmpadas dos quatro aparelhos.
3. Desencaixe o cabo do P1.
4. Espere cinco segundos.
5. Encaixe o cabo de volta, olhando as lâmpadas do P1.
6. Confira que, depois de um primeiro desenho qualquer, as lâmpadas do P1 assentam no desenho do número dele em poucos segundos.
7. Confira na linha «Jogador» que o número do P1 continua o mesmo.
8. Desencaixe o cabo do P2, espere cinco segundos e encaixe de novo, olhando as lâmpadas dele.
9. Confira que as lâmpadas do P2 assentam no desenho do número dele.
10. Confira que nenhuma lâmpada do P3 e do P4 mudou durante as duas voltas.

**Passa quando.** Depois de entrar pelo cabo, cada um dos dois controles do cabo assenta no desenho do PRÓPRIO número, com o número igual ao de antes. O primeiro desenho que pisca ao encaixar não conta: o que conta é onde as lâmpadas param. Os dois do rádio não se mexem.

**Por controle.**

* **P1** — Cabo, e é ESTE. É o primeiro a sair e voltar pelo cabo.
* **P2** — Cabo, e a segunda volta não é enfeite: se o P1 assentar e o P2 não, os dois estão no mesmo cabo e a diferença é do controle.
* **P3** — Rádio, testemunha. Não toque. Nenhuma lâmpada pode mudar enquanto os do cabo vão e voltam.
* **P4** — Rádio, segunda testemunha. Não toque.

**A armadilha.** Três. (1) O primeiro desenho que acende ao encaixar é do Linux, e ele pode ser outro número — quem escolhe é um contador que conta todo aparelho de PlayStation da máquina. A prova é o desenho em que as lâmpadas PARAM. (2) Confira antes, na aba Jogar, que o «Status» está em «Ligado»: em «Desligado» o Hefesto sai do meio e não escreve nada, e você mediria o Linux. (3) As teclas de desenho à mão saíram da aba Iluminação em 07/09, por ordem sua: o que o Hefesto escreve hoje é o desenho do NÚMERO, e é isso que se mede. Não julgue pela tela — a linha «LEDs» desenha o número, nunca o plástico.

---

## mapa-luz.led_jogador.escrita_hefesto-radio — LED de jogador — escrita pelo Hefesto · rádio

*Célula:* `luz.led_jogador.escrita_hefesto @ rádio`

**O que isto prova.** Prova que, quando um controle volta pelo rádio, o Hefesto escreve nas cinco lâmpadas dele o desenho do número que ele tem — e mede o ponto em que o rádio pode perder: a volta do «Status» de «Desligado» para «Ligado», com e sem a Steam aberta.

**Onde olhar.** No aparelho: as cinco lâmpadas brancas entre o touchpad e o botão PS. Na aba Iluminação: a linha «Jogador» (o número de cada coluna) e a linha «LEDs». Na aba Jogar: a linha «Status», com «Ligado» e «Desligado». Os desenhos: 3 é as duas pontas e a do meio; 4 é as quatro de fora, com a do meio apagada.

**Os passos.**

1. Abra a aba Iluminação.
2. Anote o número aceso na linha «Jogador» de cada coluna e o desenho das lâmpadas dos quatro aparelhos.
3. Segure o botão PS do P3 até todas as luzes dele apagarem, e solte.
4. Espere cinco segundos.
5. Dê um toque curto no botão PS do P3, olhando as lâmpadas dele.
6. Confira que as lâmpadas do P3 assentam no desenho do número dele em poucos segundos, com o mesmo número na linha «Jogador».
7. Segure o PS do P4 até apagar, espere cinco segundos e dê um toque curto, olhando as lâmpadas dele.
8. Confira que as lâmpadas do P4 assentam no desenho do número dele.
9. Abra a aba Jogar.
10. Clique em «Desligado», na linha «Status».
11. Espere dez segundos.
12. Clique em «Ligado», na mesma linha.
13. Anote, nos quatro aparelhos, quem ficou no desenho do próprio número e quem não ficou.
14. Abra a Steam e espere ela terminar de abrir.
15. Volte ao Hefesto e clique em «Desligado» e, dez segundos depois, em «Ligado».
16. Anote de novo, nos quatro aparelhos, quem ficou no desenho do próprio número.
17. Feche a Steam de novo, por inteiro.

**Passa quando.** Os dois do rádio voltam pelo PS e assentam no desenho do próprio número, como os do cabo. E depois de cada volta do «Status», os quatro estão no desenho do próprio número. Se os do cabo mantiverem e os do rádio não — sobretudo na volta com a Steam aberta —, o teste achou exatamente o que veio procurar: anote «os do rádio perderam» e em qual volta.

**Por controle.**

* **P1** — Cabo, e aqui ele é o CONTROLE DE COMPARAÇÃO nas duas voltas do «Status». Sem ele você não sabe se quem falhou foi o rádio ou o gesto inteiro.
* **P2** — Cabo, testemunha. Não toque. As lâmpadas dele ficam no desenho do número dele do começo ao fim.
* **P3** — Rádio, e é ESTE. É o primeiro a desligar e voltar pelo PS, e é nele que se olha primeiro depois de cada volta do «Status».
* **P4** — Rádio, e é o segundo alvo. Faz a mesma volta pelo PS.

**A armadilha.** Quatro. (1) Enquanto o «Status» está em «Desligado» o Hefesto não escreve nada, e o que estiver aceso é do sistema: a leitura que vale é a de DEPOIS de voltar a «Ligado». (2) O mapa segura o rádio desta linha em PARCIAL por uma razão só, e ela é a volta com a Steam aberta: depois do «Desligado» o número é reescrito por um caminho que perde quando outro programa segura o controle. Você viu as lâmpadas acenderem em 09/09, mas aquele ensaio não exercitou essa disputa — este passo é a primeira medição dela. (3) Soltar o PS cedo demais não desliga o controle, e aí você não religou nada: segure até TODAS as luzes apagarem. (4) O controle precisa já estar pareado nesta máquina, senão o toque no PS não o traz de volta.

---

## mapa-luz.led_jogador.leitura-cabo — LED de jogador — leitura (saber o que está aceso) · cabo

*Célula:* `luz.led_jogador.leitura @ cabo`

**O que isto prova.** Prova que a tela desenha as cinco lâmpadas a partir do NÚMERO do controle e não lê o plástico: quando um controle do cabo mostra outro desenho, a tela não acompanha.

**Onde olhar.** Três desenhos das mesmas cinco lâmpadas. No aparelho: a fileira entre o touchpad e o botão PS. Na aba Iluminação: a linha «LEDs» da coluna do controle, ao lado do número aceso na linha «Jogador». Na aba Controles: o bloco «LED do jogador», dentro do card aberto do controle. Para o plástico mostrar um desenho que não é o do Hefesto, o gesto é tirar o Hefesto do meio (o «Status» em «Desligado», na aba Jogar) e reencaixar o cabo: aí quem acende as lâmpadas é o Linux.

**Os passos.**

1. Abra a aba Jogar.
2. Clique em «Desligado», na linha «Status».
3. Confira que o quadro «Modo» passou a mostrar «Modo Nativo».
4. Desencaixe o cabo do P1.
5. Espere cinco segundos.
6. Encaixe o cabo de volta.
7. Anote o desenho que as lâmpadas do P1 acendem.
8. Abra a aba Iluminação.
9. Anote o desenho da linha «LEDs» e o número aceso na linha «Jogador», na coluna do P1.
10. Abra a aba Controles.
11. Clique na linha do P1 para abrir o card dele.
12. Anote o desenho do bloco «LED do jogador».
13. Desencaixe o cabo do P2, espere cinco segundos e encaixe de novo.
14. Anote o desenho do plástico do P2, o da linha «LEDs» da coluna dele na aba Iluminação e o do bloco «LED do jogador» do card dele.
15. Abra a aba Jogar e clique em «Ligado», na linha «Status».
16. Anote se as lâmpadas do P1 e do P2 voltaram ao desenho do número deles.

**Passa quando.** Os dois desenhos da tela — a linha «LEDs» e o bloco «LED do jogador» — mostram o desenho do NÚMERO do controle, o mesmo de antes, mesmo quando o plástico mostra outro. Os dois discordarem do plástico é o resultado ESPERADO: é a prova de que a tela não lê o aparelho. Se o plástico acender justamente o desenho do número, esta volta não mediu nada — anote e siga para o P2.

**Por controle.**

* **P1** — Cabo, e é ESTE. Reencaixe com o Hefesto fora do meio e compare os três desenhos.
* **P2** — Cabo, segunda volta. Serve para separar «a tela não lê» de «a tela não leu deste controle» — e dá uma segunda chance de o Linux acender um desenho diferente do número.
* **P3** — Rádio, testemunha. Não toque. O plástico e os dois desenhos de tela dele não podem mudar.
* **P4** — Rádio, segunda testemunha. Não toque. Confira também o bloco «LED do jogador» do card dele: ele sai do número e não pode mudar.

**A armadilha.** Três. (1) A discordância entre tela e plástico é o achado, não defeito de pintura. Defeito seria a tela desenhar outra coisa que não o número. (2) Quem escolhe o desenho do Linux é um contador que conta todo aparelho de PlayStation da máquina, e ele pode coincidir com o número: por isso são dois controles. (3) Enquanto o «Status» está em «Desligado» o Hefesto não escreve nas lâmpadas; o último passo mede se ele as reescreve ao voltar, e a resposta é anotação, não critério deste teste. Esta linha foi respondida por leitura de código: o que você anotar é a primeira medição.

---

## mapa-luz.led_jogador.leitura-radio — LED de jogador — leitura (saber o que está aceso) · rádio

*Célula:* `luz.led_jogador.leitura @ rádio`

**O que isto prova.** Prova que, num controle do rádio, a tela também desenha as cinco lâmpadas a partir do número e não lê o plástico.

**Onde olhar.** Os mesmos três lugares do irmão do cabo: as lâmpadas do aparelho, entre o touchpad e o botão PS; a linha «LEDs» da coluna do controle na aba Iluminação, ao lado do número na linha «Jogador»; e o bloco «LED do jogador» do card aberto, na aba Controles. O gesto que põe no plástico um desenho que não é do Hefesto é o «Status» em «Desligado», na aba Jogar, e desligar e religar o controle pelo PS.

**Os passos.**

1. Abra a aba Jogar.
2. Clique em «Desligado», na linha «Status».
3. Confira que o quadro «Modo» passou a mostrar «Modo Nativo».
4. Segure o botão PS do P3 até todas as luzes dele apagarem, e solte.
5. Espere cinco segundos.
6. Dê um toque curto no botão PS do P3.
7. Anote o desenho que as lâmpadas do P3 acendem.
8. Abra a aba Iluminação.
9. Anote o desenho da linha «LEDs» e o número aceso na linha «Jogador», na coluna do P3.
10. Abra a aba Controles.
11. Clique na linha do P3 para abrir o card dele.
12. Anote o desenho do bloco «LED do jogador».
13. Desligue o P4 segurando o PS até apagar, espere cinco segundos e dê um toque curto no PS.
14. Anote o desenho do plástico do P4, o da linha «LEDs» da coluna dele na aba Iluminação e o do bloco «LED do jogador» do card dele.
15. Abra a aba Jogar e clique em «Ligado», na linha «Status».
16. Anote se as lâmpadas do P3 e do P4 voltaram ao desenho do número deles.

**Passa quando.** A resposta é a MESMA do cabo: os dois desenhos da tela mostram o desenho do número, o mesmo de antes, mesmo com o plástico mostrando outro. Se pelo rádio alguma das duas telas se comportar diferente da do cabo, anote a diferença — é para isso que existem os dois testes irmãos.

**Por controle.**

* **P1** — Cabo, testemunha e comparação. Não toque. No fim, o bloco «LED do jogador» do card dele continua no desenho do número dele.
* **P2** — Cabo, testemunha. Não toque. Nada dele pode mudar.
* **P3** — Rádio, e é ESTE. Religue pelo PS com o Hefesto fora do meio e compare os três desenhos.
* **P4** — Rádio, segunda volta: é ele que diz se a resposta é do transporte ou daquele aparelho.

**A armadilha.** Três. (1) A discordância é o esperado; se o Linux acender o próprio desenho do número, a volta não mediu nada. (2) Soltar o PS cedo demais não desliga o controle — segure até TODAS as luzes apagarem —, e ele precisa estar pareado para voltar com o toque. (3) Se o chip do controle sumir e voltar da fita do topo fora da hora, ele caiu e voltou sozinho: refaça. Aqui não há diferença de transporte esperada: nenhum caminho pergunta ao aparelho o que está aceso. Esta linha foi respondida por leitura de código.

---

## mapa-luz.led_jogador.padrao_driver-cabo — LED de jogador — o padrão que o driver acende na probe · cabo

*Célula:* `luz.led_jogador.padrao_driver @ cabo`

**O que isto prova.** Prova qual desenho de lâmpadas o Linux acende sozinho no instante em que um controle entra pelo cabo, com o Hefesto fora do meio.

**Onde olhar.** O APARELHO, e só ele: as cinco lâmpadas entre o touchpad e o botão PS, no primeiro segundo depois de encaixar o cabo. Esse desenho de partida não aparece em campo nenhum da tela — existe só no plástico, por um instante. Na tela ficam o antes e o depois: a aba Jogar, linha «Status» («Ligado» / «Desligado»), com o quadro «Modo» logo abaixo; e a fita do topo, onde cada chip diz o número que o Hefesto dá (P1, P2…). Os desenhos: 1 é só a do meio; 2 é a segunda e a quarta; 3 é as pontas e o meio; 4 é as quatro de fora; 5 é as cinco.

**Os passos.**

1. Abra a aba Jogar.
2. Clique em «Desligado», na linha «Status».
3. Confira que o quadro «Modo» passou a mostrar «Modo Nativo».
4. Desencaixe o cabo do P1.
5. Espere cinco segundos.
6. Encaixe o cabo de volta, olhando as cinco lâmpadas do P1.
7. Anote o PRIMEIRO desenho que acende, e se ele surge de uma vez ou sobe devagar.
8. Desencaixe o cabo do P2.
9. Espere cinco segundos.
10. Encaixe o cabo de volta, olhando as lâmpadas do P2.
11. Anote o primeiro desenho que acende nele.
12. Clique em «Ligado», na linha «Status».
13. Anote o número que a fita do topo dá a cada um dos dois.
14. Compare, controle por controle, o desenho que o Linux acendeu com o desenho do número que o Hefesto deu.

**Passa quando.** Cada controle do cabo acende sozinho um dos cinco desenhos conhecidos assim que entra, sem o Hefesto no meio, e ele SOBE DEVAGAR em vez de aparecer de uma vez. A entrega é a comparação do último passo: se o desenho de partida não for o do número que o Hefesto dá depois, anote os dois lado a lado — é exatamente isso que se quer medir.

**Por controle.**

* **P1** — Cabo, e é o primeiro a religar. Anote o desenho que ele acende antes de o Hefesto dizer qualquer coisa.
* **P2** — Cabo, e religue-o DEPOIS do P1. É ele que mostra se o Linux avança na fila ou repete o desenho do anterior.
* **P3** — Rádio, testemunha. Não toque. Desencaixar cabo não pode mexer em quem está no rádio.
* **P4** — Rádio, testemunha. Não toque. No fim, as lâmpadas dele têm de estar como estavam.

**A armadilha.** Três. (1) Não espere que o desenho de partida bata com o número do Hefesto: quem escolhe é um contador do Linux que conta QUALQUER aparelho de PlayStation da máquina, virtuais inclusive, e dá a volta a cada cinco. Divergir aqui é o fato, não a falha. (2) A subida devagar é do próprio Linux, e não lentidão da máquina. (3) Com o «Status» em «Ligado» o Hefesto escreve por cima quase na hora e você mediria o Hefesto: o «Desligado» é o primeiro passo, e não sugestão. A prova desta linha veio de leitura do driver; o que você anotar é a primeira medição.

---

## mapa-luz.led_jogador.padrao_driver-radio — LED de jogador — o padrão que o driver acende na probe · rádio

*Célula:* `luz.led_jogador.padrao_driver @ rádio`

**O que isto prova.** Prova qual desenho de lâmpadas o Linux acende sozinho no instante em que um controle volta pelo rádio, com o Hefesto fora do meio.

**Onde olhar.** O APARELHO, e só ele: as cinco lâmpadas entre o touchpad e o botão PS, no primeiro segundo depois de o controle voltar. Esse desenho não aparece em campo nenhum da tela. Na tela ficam o antes e o depois: a aba Jogar, linha «Status», com o quadro «Modo»; e a fita do topo, onde cada chip diz o número que o Hefesto dá e termina em BT para quem está no rádio.

**Os passos.**

1. Abra a aba Jogar.
2. Clique em «Desligado», na linha «Status».
3. Confira que o quadro «Modo» passou a mostrar «Modo Nativo».
4. Segure o botão PS do P3 até todas as luzes dele apagarem, e solte.
5. Espere cinco segundos.
6. Dê um toque curto no botão PS do P3, olhando as cinco lâmpadas dele.
7. Anote o PRIMEIRO desenho que acende, e se ele surge de uma vez ou sobe devagar.
8. Segure o botão PS do P4 até todas as luzes dele apagarem, e solte.
9. Espere cinco segundos.
10. Dê um toque curto no botão PS do P4, olhando as lâmpadas dele.
11. Anote o primeiro desenho que acende nele.
12. Clique em «Ligado», na linha «Status».
13. Anote o número que a fita do topo dá a cada um dos dois.
14. Compare, controle por controle, o desenho que o Linux acendeu com o desenho do número que o Hefesto deu.

**Passa quando.** Cada controle do rádio acende sozinho um dos cinco desenhos conhecidos assim que volta, sem o Hefesto no meio, e ele sobe devagar. A entrega é a comparação do último passo, anotada lado a lado para os dois.

**Por controle.**

* **P1** — Cabo, testemunha. Não toque. As lâmpadas dele não podem mudar enquanto os do rádio vão e voltam.
* **P2** — Cabo, testemunha. Não toque. Se ele mudar quando um do rádio volta, o contador do Linux mexeu em quem não saiu.
* **P3** — Rádio, e é o primeiro a desligar e religar.
* **P4** — Rádio, e religue-o DEPOIS do P3: é ele que diz se o Linux avança na fila ou repete o desenho do anterior.

**A armadilha.** Quatro. (1) Soltar o PS cedo demais não desliga o controle, e você mede o seu gesto, não o produto — segure até TODAS as luzes apagarem. (2) O desenho de partida não tem de bater com o número do Hefesto: o contador do Linux conta todo aparelho de PlayStation, virtuais inclusive, e dá a volta a cada cinco. (3) Com o «Status» em «Ligado» você mediria o Hefesto: o «Desligado» é obrigatório. (4) O controle precisa já estar pareado nesta máquina, senão o toque no PS não o traz de volta. A prova desta linha veio de leitura do driver.

---

## mapa-luz.led_jogador.quinto-cabo — LED de jogador — a quinta lâmpada · cabo

*Célula:* `luz.led_jogador.quinto @ cabo`

**O que isto prova.** Prova que a quinta lâmpada — a da ponta da direita — de um controle do cabo acende e apaga nos desenhos de número: acende no 3 e no 4, apaga no 1 e no 2. O que ele NÃO alcança é se ela acende sozinha, sem a primeira.

**Onde olhar.** O aparelho: as cinco lâmpadas entre o touchpad e o botão PS, contadas AQUI da esquerda para a direita, 1 a 5. Na aba Iluminação: a linha «Jogador» de cada coluna. Os controles do cabo têm os números 1 e 2, e nos dois a quinta está apagada; para ela acender num controle do cabo ele precisa receber o 3 ou o 4, e isso é trocar de número com um controle do rádio.

**Os passos.**

1. Abra a aba Iluminação.
2. Anote o número aceso na linha «Jogador» de cada coluna.
3. Clique no botão «3» da linha «Jogador», na coluna do P1.
4. Confira no aparelho que era o P1 que a primeira, a do meio e a quinta acenderam juntas.
5. Confira que as lâmpadas do P2 e do P4 não mudaram.
6. Ache a coluna em que aquele aparelho aparece agora, com P3 na linha «Modelo», e clique no «1» da linha «Jogador» dela.
7. Confira no mesmo aparelho que a primeira e a quinta apagaram juntas e sobrou só a do meio.
8. Clique no botão «4» da linha «Jogador», na coluna do P2.
9. Confira no aparelho que era o P2 que as quatro de fora acenderam — a quinta junto com a primeira — e a do meio apagou.
10. Ache a coluna em que aquele aparelho aparece agora, com P4 na linha «Modelo», e clique no «2» da linha «Jogador» dela.
11. Confira nos quatro aparelhos que os números e as lâmpadas voltaram ao que você anotou.

**Passa quando.** Nos dois controles do cabo a quinta lâmpada acende quando o número é 3 ou 4 e apaga quando volta a 1 ou 2, sempre acompanhando a primeira, no mesmo clique. E quem não entrou na troca não se mexe.

**Por controle.**

* **P1** — Cabo, e é o primeiro alvo: recebe o 3, mostra a quinta acesa, e volta ao 1.
* **P2** — Cabo, segundo alvo: recebe o 4, mostra a quinta acesa, e volta ao 2. A resposta aqui pode ser de REVISÃO DE HARDWARE, então dois aparelhos podem discordar — e isso é resultado.
* **P3** — Rádio, e nesta célula ele é o PAR DA TROCA do P1: muda de número junto, e isso é o gesto, não defeito. Na segunda troca ele é testemunha e não se mexe.
* **P4** — Rádio, par da troca do P2. Na primeira troca é testemunha e não se mexe.

**A armadilha.** Três. (1) Aqui, e só aqui, conta-se as lâmpadas da esquerda para a direita. (2) Os cinco desenhos de número são simétricos: a primeira e a quinta sempre andam juntas neles. Por isso este teste prova que a quinta ACENDE, e não prova que ela acende SOZINHA — o mapa diz, por uma fonte só, que em revisões novas do DualSense a primeira e a quinta estão ligadas por dentro, e isso só se enxerga com um desenho torto. As teclas de desenho à mão, que davam esse desenho torto, saíram da tela em 07/09 por ordem sua. (3) Com um jogo aberto o botão do número recusa, com a borda piscando laranja: feche o jogo e refaça.

---

## mapa-luz.led_jogador.quinto-radio — LED de jogador — a quinta lâmpada · rádio

*Célula:* `luz.led_jogador.quinto @ rádio`

**O que isto prova.** Prova que a quinta lâmpada — a da ponta da direita — de um controle do rádio acende e apaga nos desenhos de número: acende no 3 e no 4, apaga no 1 e no 2. Como o irmão do cabo, ele não alcança se ela acende sozinha.

**Onde olhar.** O aparelho: as cinco lâmpadas entre o touchpad e o botão PS, contadas AQUI da esquerda para a direita, 1 a 5. Na aba Iluminação: a linha «Jogador» de cada coluna. Os controles do rádio têm os números 3 e 4, e nos dois a quinta está acesa; para ela apagar num controle do rádio ele precisa receber o 1 ou o 2, e isso é trocar de número com um controle do cabo.

**Os passos.**

1. Abra a aba Iluminação.
2. Anote o número aceso na linha «Jogador» de cada coluna.
3. Confira no P3 e no P4 que a quinta lâmpada está acesa, junto com a primeira.
4. Clique no botão «1» da linha «Jogador», na coluna do P3.
5. Confira no aparelho que era o P3 que a primeira e a quinta apagaram juntas e sobrou só a do meio.
6. Confira que as lâmpadas do P2 e do P4 não mudaram.
7. Ache a coluna em que aquele aparelho aparece agora, com P1 na linha «Modelo», e clique no «3» da linha «Jogador» dela.
8. Confira no mesmo aparelho que a primeira e a quinta acenderam de novo.
9. Clique no botão «2» da linha «Jogador», na coluna do P4.
10. Confira no aparelho que era o P4 que a primeira e a quinta apagaram e ficaram a segunda e a quarta.
11. Ache a coluna em que aquele aparelho aparece agora, com P2 na linha «Modelo», e clique no «4» da linha «Jogador» dela.
12. Confira nos quatro aparelhos que os números e as lâmpadas voltaram ao que você anotou.

**Passa quando.** Nos dois controles do rádio a quinta lâmpada apaga quando o número é 1 ou 2 e volta a acender com o 3 ou o 4, sempre junto com a primeira e no mesmo clique — e a resposta é IGUAL à do irmão do cabo. Quem não entrou na troca não se mexe.

**Por controle.**

* **P1** — Cabo, e é o PAR DA TROCA do P3: muda de número junto, e isso é o gesto. Na segunda troca é testemunha.
* **P2** — Cabo, par da troca do P4. Na primeira troca é testemunha e não se mexe.
* **P3** — Rádio, e é o primeiro alvo: recebe o 1, a quinta apaga, e volta ao 3.
* **P4** — Rádio, segundo alvo: recebe o 2, a quinta apaga, e volta ao 4. Dois aparelhos podem discordar, porque a resposta é de revisão de hardware.

**A armadilha.** Três. (1) Aqui se conta da esquerda para a direita. (2) Nos desenhos de número a primeira e a quinta andam sempre juntas: o teste prova que a quinta acende e apaga, não que ela acende sozinha — isso pedia o desenho torto que saiu da tela em 07/09. (3) Só do rádio: se o controle cair e voltar no meio, o desenho muda sem ninguém ter clicado — confira o chip dele na fita do topo antes de anotar.

---

## mapa-luz.led_jogador.udev-cabo — LED de jogador — regra udev que o torna gravável sem sudo · cabo

*Célula:* `luz.led_jogador.udev @ cabo`

**O que isto prova.** Prova que, logo depois de encaixar o cabo, o Hefesto consegue mandar nas lâmpadas daquele controle sem pedir senha e sem recusar.

**Onde olhar.** A tela não tem campo que mostre esta permissão: nenhuma linha de «O exame de hoje», na aba Sistema, fala dela. O que se lê é a CONSEQUÊNCIA: na aba Iluminação, o botão da linha «Jogador» que você clica pisca a borda em verde quando o pedido foi aplicado e em laranja quando foi recusado; e o aparelho, as cinco lâmpadas entre o touchpad e o botão PS.

**Os passos.**

1. Abra a aba Iluminação.
2. Desencaixe o cabo do P1.
3. Espere cinco segundos.
4. Encaixe o cabo de volta.
5. Espere o chip do P1 reaparecer na fita do topo.
6. Clique no botão «2» da linha «Jogador», na coluna do P1.
7. Confira que nada pediu senha e que nenhuma janela de autorização apareceu.
8. Anote a cor em que a borda do botão piscou.
9. Confira nos dois aparelhos do cabo que as lâmpadas trocaram: o que você mexeu mostra a segunda e a quarta, o outro só a do meio.
10. Ache a coluna em que aquele aparelho aparece agora, com P2 na linha «Modelo», e clique no «1» dela para desfazer.
11. Desencaixe o cabo do P2, espere cinco segundos, encaixe de novo e espere o chip dele reaparecer.
12. Clique no botão «1» da linha «Jogador», na coluna do P2.
13. Anote a cor em que a borda piscou e confira que as lâmpadas dos dois do cabo trocaram.
14. Clique no «2» da coluna em que aquele aparelho aparece agora, para desfazer.

**Passa quando.** Depois de entrar pelo cabo, o clique no número obedece nos dois controles do cabo: as lâmpadas trocam no plástico, a borda pisca verde, e nada pede senha nem autorização.

**Por controle.**

* **P1** — Cabo, e é ESTE. O gesto que importa é RELIGAR PELO CABO antes de clicar: a permissão é dada no instante em que o aparelho entra.
* **P2** — Cabo, e a segunda volta separa «a máquina está sem a permissão» de «aquele aparelho entrou torto».
* **P3** — Rádio, testemunha. Não toque. No fim, nenhuma lâmpada dele mudou.
* **P4** — Rádio, testemunha. Não toque. Ele e o P3 mostram que religar um cabo não mexe em quem está no rádio.

**A armadilha.** Três. (1) Este é o teste mais fácil de dar falso VERDE da família: a permissão libera UM caminho, e o Hefesto move as lâmpadas também por outro. As lâmpadas obedecerem NÃO prova que a permissão está lá. O que este teste mede de verdade é o contrário: se algo pedir senha ou a borda piscar laranja, a permissão é a primeira suspeita. (2) A permissão é dada quando o aparelho ENTRA: clicar sem ter religado mede a permissão de ontem. (3) Laranja também aparece com um jogo aberto (o número não troca no meio da partida): confira que não há jogo antes de acusar a permissão. A regra é do Linux, não do aparelho: não há sinal nenhum a procurar no plástico.

---

## mapa-luz.led_jogador.udev-radio — LED de jogador — regra udev que o torna gravável sem sudo · rádio

*Célula:* `luz.led_jogador.udev @ rádio`

**O que isto prova.** Prova que, logo depois de o controle voltar pelo rádio, o Hefesto consegue mandar nas lâmpadas dele sem pedir senha e sem recusar.

**Onde olhar.** A tela não tem campo que mostre esta permissão: nenhuma linha de «O exame de hoje», na aba Sistema, fala dela. O que se lê é a consequência: o botão da linha «Jogador», na aba Iluminação, pisca a borda em verde quando o pedido foi aplicado e em laranja quando foi recusado; e as cinco lâmpadas do aparelho, entre o touchpad e o botão PS.

**Os passos.**

1. Abra a aba Iluminação.
2. Segure o botão PS do P3 até todas as luzes dele apagarem, e solte.
3. Espere cinco segundos.
4. Dê um toque curto no botão PS do P3.
5. Espere o chip do P3 reaparecer na fita do topo.
6. Clique no botão «4» da linha «Jogador», na coluna do P3.
7. Confira que nada pediu senha e que nenhuma janela de autorização apareceu.
8. Anote a cor em que a borda do botão piscou.
9. Confira nos dois aparelhos do rádio que as lâmpadas trocaram: o que você mexeu mostra as quatro de fora, o outro as pontas e o meio.
10. Ache a coluna em que aquele aparelho aparece agora, com P4 na linha «Modelo», e clique no «3» dela para desfazer.
11. Desligue o P4 segurando o PS até apagar, espere cinco segundos, dê um toque curto no PS e espere o chip dele reaparecer.
12. Clique no botão «3» da linha «Jogador», na coluna do P4.
13. Anote a cor em que a borda piscou e confira que as lâmpadas dos dois do rádio trocaram.
14. Clique no «4» da coluna em que aquele aparelho aparece agora, para desfazer.

**Passa quando.** Depois de voltar pelo rádio, o clique no número obedece nos dois controles do rádio: as lâmpadas trocam no plástico, a borda pisca verde, e nada pede senha. Compare com o irmão do cabo: se o cabo obedecer e o rádio não, o achado é o transporte.

**Por controle.**

* **P1** — Cabo, testemunha e comparação. Não toque. Se este teste falhar e o do cabo passar, o par de resultados diz onde está o problema.
* **P2** — Cabo, testemunha. Não toque. No fim, nenhuma lâmpada dele mudou.
* **P3** — Rádio, e é ESTE. O gesto que importa é DESLIGAR E RELIGAR PELO PS antes de clicar: a permissão é dada quando o aparelho entra.
* **P4** — Rádio, e a segunda volta separa «o rádio inteiro» de «aquele aparelho».

**A armadilha.** Três. (1) O falso verde é o mesmo do irmão do cabo, e aqui pesa mais: o mapa diz que é esta regra que sustenta um dos caminhos das lâmpadas no rádio, mas o Hefesto também escreve por outra rota. As lâmpadas obedecerem não prova a permissão; o que o teste entrega é a observação. (2) Soltar o PS cedo demais não desliga o controle — segure até TODAS as luzes apagarem. (3) O controle precisa já estar pareado nesta máquina. A regra é do Linux: não há sinal a procurar no plástico.

---

## mapa-luz.led_microfone-cabo — LED do microfone (o botão de mudo iluminado) · cabo

*Célula:* `luz.led_microfone @ cabo`

**O que isto prova.** Prova que quem acende a luz do botão de microfone de um controle do cabo é o Hefesto, e que ela diz o estado daquele microfone e de nenhum outro: acesa fixa com o microfone ligado, apagada com ele desligado, piscando enquanto um programa grava e entra som.

**Onde olhar.** No APARELHO: a luz dentro do botãozinho de microfone, abaixo do botão PS. Na aba Controles: na linha de cada controle, ao lado de «Microfone», um selo que diz «ATIVO», «DESLIGADO» ou «—» (o travessão quer dizer que não deu para ler). No card aberto, embaixo do bloco «Microfone», aparece o nome do programa que está gravando, seguido de «está te ouvindo.». O 🎙 da fileira do volume é o retorno — você se ouve —, e não entra neste teste.

**Os passos.**

1. Abra a aba Controles.
2. Anote o selo de «Microfone» nas linhas dos quatro controles.
3. Anote a luz do botão de microfone de cada aparelho: acesa, apagada ou piscando.
4. Aperte uma vez o botão de microfone do P1, no próprio controle.
5. Confira que a luz do botão do P1 apagou e que o selo da linha dele virou «DESLIGADO».
6. Confira que a luz e o selo do P2, do P3 e do P4 não mudaram.
7. Aperte de novo o botão de microfone do P1.
8. Confira que a luz do P1 acendeu fixa e que o selo voltou a «ATIVO».
9. Clique na linha do P1 para abrir o card dele.
10. Abra, no computador, um programa que grave pelo microfone do P1 — um gravador de som ou uma chamada de voz —, escolhendo o microfone desse controle, e fale perto dele.
11. Confira que a luz do P1 pisca enquanto você fala, e que embaixo do bloco «Microfone» aparece o nome do programa com «está te ouvindo.».
12. Feche o programa que gravava.
13. Confira que a luz do P1 voltou a ficar acesa fixa.
14. Aperte duas vezes o botão de microfone do P2, olhando a luz e o selo dele a cada aperto.
15. Confira que o P2 fez o mesmo que o P1: apagou com «DESLIGADO» e acendeu com «ATIVO».

**Passa quando.** A luz fica ACESA FIXA com o microfone ligado e apagada com ele desligado — o contrário do que o Linux faz sozinho, em que acesa quer dizer mudo; é isso que prova que quem manda na luz é o Hefesto. Ela pisca enquanto um programa de fora grava e entra som. O selo acompanha. E só o controle apertado muda.

**Por controle.**

* **P1** — Cabo, e é ESTE. Os dois apertos e o programa gravando são nele.
* **P2** — Cabo, e a segunda volta separa «o Hefesto manda na luz» de «o Hefesto manda na luz daquele aparelho».
* **P3** — Rádio, testemunha. Não toque. A luz e o selo dele ficam como estavam.
* **P4** — Rádio, testemunha. Não toque. Os quatro microfones ficam no ar juntos: calar o P1 não pode calar ninguém do rádio.

**A armadilha.** Quatro. (1) A luz tem QUATRO estados, não dois: apagada, acesa, piscando, e piscando mais devagar — este último quer dizer que alguém grava E a bateria daquele controle está abaixo de 30%. Anote o que viu, nunca o que esperava. (2) O 🎙 da tela não cala o microfone: ele liga o retorno, e o retorno é do próprio Hefesto — não faz a luz piscar. Quem cala é o botão do controle. (3) Um selo em «—» não é «ATIVO» nem «DESLIGADO»: acontece logo depois de o controle entrar, e não conta como passa. (4) Piscar exige som entrando: com o programa aberto e você calada, a luz pode ficar fixa, e isso é o produto certo.

---

## mapa-luz.led_microfone-radio — LED do microfone (o botão de mudo iluminado) · rádio

*Célula:* `luz.led_microfone @ rádio`

**O que isto prova.** Prova que quem acende a luz do botão de microfone de um controle do rádio é o Hefesto, com a mesma língua do cabo: acesa fixa com o microfone ligado, apagada com ele desligado, piscando enquanto um programa grava e entra som.

**Onde olhar.** No APARELHO: a luz dentro do botãozinho de microfone, abaixo do botão PS. Na aba Controles: na linha de cada controle, o selo de «Microfone» («ATIVO», «DESLIGADO» ou «—»); no card aberto, os dois botões «Virtual» e «Nativo» do bloco «Microfone» — pelo rádio, o microfone chega ao computador pelo «Virtual» — e, embaixo do bloco, o nome do programa que grava, com «está te ouvindo.». O 🎙 da fileira do volume é o retorno, e não entra neste teste.

**Os passos.**

1. Abra a aba Controles.
2. Anote o selo de «Microfone» nas linhas dos quatro controles.
3. Anote a luz do botão de microfone de cada aparelho: acesa, apagada ou piscando.
4. Aperte uma vez o botão de microfone do P3, no próprio controle.
5. Confira que a luz do P3 apagou e que o selo da linha dele virou «DESLIGADO».
6. Confira que a luz e o selo do P1, do P2 e do P4 não mudaram.
7. Aperte de novo o botão de microfone do P3.
8. Confira que a luz do P3 acendeu fixa e que o selo voltou a «ATIVO».
9. Clique na linha do P3 para abrir o card dele.
10. Confira que o botão «Virtual» do bloco «Microfone» está aceso.
11. Abra, no computador, um programa que grave pelo microfone do P3 — um gravador de som ou uma chamada de voz —, escolhendo o microfone desse controle, e fale perto dele.
12. Confira que a luz do P3 pisca enquanto você fala, e que embaixo do bloco «Microfone» aparece o nome do programa com «está te ouvindo.».
13. Feche o programa que gravava.
14. Confira que a luz do P3 voltou a ficar acesa fixa.
15. Aperte duas vezes o botão de microfone do P4, olhando a luz e o selo dele a cada aperto.
16. Confira que o P4 fez o mesmo que o P3.

**Passa quando.** A resposta é a MESMA do cabo: acesa fixa com o microfone ligado, apagada com ele desligado, piscando enquanto um programa grava e entra som — e só o controle apertado muda. Os quatro estados dessa luz foram medidos por você nos dois transportes; o que este teste acrescenta é que ela segue o BOTÃO, que é a regra desde 19/09.

**Por controle.**

* **P1** — Cabo, testemunha e comparação. Não toque. Se a luz dele responde no irmão do cabo e a do P3 não responde aqui, o achado é o transporte.
* **P2** — Cabo, testemunha. Não toque. A luz e o selo dele ficam como estavam.
* **P3** — Rádio, e é ESTE. Os dois apertos e o programa gravando são nele.
* **P4** — Rádio, e a segunda volta é a que mais importa: se a luz do P4 apagar quando você aperta o do P3, o gesto pegou o rádio inteiro.

**A armadilha.** Quatro. (1) Quatro estados: apagada, acesa, piscando, e piscando mais devagar (alguém grava e a bateria está abaixo de 30%). (2) O 🎙 da tela é o retorno e não cala nada; quem cala é o botão do controle. (3) Sem o «Virtual» aceso o programa não acha o microfone do P3 — pelo rádio não existe outro caminho —, e sem ninguém gravando a luz não pisca: isso é montagem, não defeito. (4) Se o chip do controle sumir e voltar da fita do topo, ele caiu e voltou; o selo pode ficar em «—» até ele ler de novo. Olhe o chip antes de concluir qualquer coisa.

---

## mapa-luz.lightbar.aviso_de_modo-cabo — Lightbar — aviso de MODO (três piscadas na cor do modo novo) · cabo

*Célula:* `luz.lightbar.aviso_de_modo @ cabo`

**O que isto prova.** Prova que trocar de modo faz a barra de luz dos dois controles do cabo piscar três vezes na cor daquele modo e voltar à cor de antes.

**Onde olhar.** Na aba Jogar: a linha «Status» («Ligado» / «Desligado») e o quadro «Modo», com os cartões «Sony DualSense», «Xbox», «Steam Input» e «Navegação»; o «?» do quadro diz que PS + R3 pula para o próximo. «Desligado» é o Modo Nativo. A resposta é toda no APARELHO: a barra de luz, as duas tiras dos lados do touchpad. As cores: «Steam Input» pisca AZUL CLARO, «Xbox» VERDE CLARO, «Sony DualSense» ROSA, «Navegação» ÂMBAR (um laranja claro) e o Modo Nativo BRANCO. Nenhum campo da tela diz que a piscada saiu.

**Os passos.**

1. Abra a aba Jogar.
2. Confira que o «Status» está em «Ligado» e anote qual cartão do quadro «Modo» está aceso.
3. Ponha os quatro controles virados para cima, onde você veja as quatro barras de uma vez.
4. Anote a cor da barra dos quatro.
5. Clique no cartão «Xbox», já com os olhos nas quatro barras.
6. Conte as piscadas do P1 e do P2: três, em verde claro.
7. Confira se as barras do P3 e do P4 piscaram também, e anote.
8. Confira que as quatro barras voltaram às cores anotadas.
9. Clique no cartão «Steam Input».
10. Conte as piscadas: três, em azul claro.
11. Clique no cartão «Sony DualSense».
12. Conte as piscadas: três, em rosa.
13. Clique de novo no mesmo cartão «Sony DualSense».
14. Confira que agora não houve piscada nenhuma.
15. Pegue o P1 e segure PS + R3 até o cartão aceso pular para o próximo.
16. Confira que a piscada saiu igual por esse caminho, nas quatro barras, na cor do cartão que acendeu.
17. Clique em «Desligado», na linha «Status».
18. Conte as piscadas: três, em branco.
19. Clique em «Ligado» e depois no cartão que estava aceso quando você começou.

**Passa quando.** A cada troca de modo, as barras do P1 e do P2 piscam TRÊS vezes na cor daquele modo e voltam sozinhas à cor que tinham. Clicar no modo que já vale não pisca nada. E a piscada sai igual pelo cartão na tela e pelo PS + R3 no controle.

**Por controle.**

* **P1** — No cabo, e é um dos dois desta célula. É também o controle do gesto PS + R3.
* **P2** — No cabo, e é o outro. Tem de piscar junto com o P1, na mesma cor e no mesmo instante.
* **P3** — No rádio, e AQUI A TESTEMUNHA NÃO FICA QUIETA: o aviso é para todos, por pedido seu. Anote se ele piscou.
* **P4** — No rádio, a mesma coisa. Se os do cabo piscarem e os do rádio não, o achado é esse — os dois lados acendem por caminhos diferentes.

**A armadilha.** Cinco. (1) OS QUATRO TÊM DE PISCAR — palavra sua: «o lightbar de todos pisca 3 vezes rápido». Reprovar porque os do rádio piscaram junto seria reprovar o produto certo. (2) A piscada inteira dura pouco mais de meio segundo: olhe as barras ANTES de clicar. (3) O Modo Nativo é caso à parte: ENTRAR nele pisca branco, mas de dentro dele o Hefesto não escreve na barra, e as piscadas seguintes não saem — faça as trocas com o «Status» em «Ligado». (4) Ligar o Hefesto não pisca: a primeira leitura do modo só memoriza. (5) Esta linha foi construída sem controle na mão: o produto sabe que MANDOU a piscada, não que ela acendeu. O seu olho é o que fecha isto. Com a Steam aberta ganha quem escreve por último, e é por isso que ela começa fechada.

---

## mapa-luz.lightbar.aviso_de_modo-radio — Lightbar — aviso de MODO (três piscadas na cor do modo novo) · rádio

*Célula:* `luz.lightbar.aviso_de_modo @ rádio`

**O que isto prova.** Prova que trocar de modo faz a barra dos dois controles do rádio piscar três vezes na cor daquele modo — inclusive com a Steam aberta, que é a promessa deste lado.

**Onde olhar.** Na aba Jogar: a linha «Status» e o quadro «Modo», com os cartões «Sony DualSense», «Xbox», «Steam Input» e «Navegação». A resposta é toda no APARELHO: a barra de luz, as duas tiras dos lados do touchpad. As cores: «Steam Input» AZUL CLARO, «Xbox» VERDE CLARO, «Sony DualSense» ROSA, «Navegação» ÂMBAR e o Modo Nativo BRANCO. Nenhum campo da tela diz que a piscada saiu.

**Os passos.**

1. Abra a aba Jogar.
2. Confira que o «Status» está em «Ligado» e anote qual cartão do quadro «Modo» está aceso.
3. Ponha os quatro controles virados para cima, onde você veja as quatro barras de uma vez.
4. Anote a cor da barra dos quatro.
5. Clique no cartão «Xbox», já com os olhos nas quatro barras.
6. Conte as piscadas do P3 e do P4: três, em verde claro.
7. Confira se as barras do P1 e do P2 piscaram também, e anote.
8. Confira que as quatro barras voltaram às cores anotadas.
9. Clique no cartão «Steam Input».
10. Conte as piscadas do P3 e do P4: três, em azul claro.
11. Abra a Steam e espere ela terminar de abrir.
12. Volte ao Hefesto, na aba Jogar, com os olhos nas quatro barras.
13. Clique no cartão «Sony DualSense».
14. Conte as piscadas do P3 e do P4: três, em rosa — esta é a volta que decide.
15. Anote se o P1 e o P2 piscaram nesta volta.
16. Feche a Steam de novo, por inteiro.
17. Clique no cartão que estava aceso quando você começou.

**Passa quando.** A cada troca de modo, as barras do P3 e do P4 piscam TRÊS vezes na cor daquele modo e voltam sozinhas à cor de antes — com a Steam fechada e com a Steam aberta. A volta com a Steam aberta é a que fecha o teste.

**Por controle.**

* **P1** — No cabo, testemunha que também pisca, porque o aviso é para todos. Se ele piscar com a Steam aberta e os do rádio não, isso separa os dois caminhos e é o achado.
* **P2** — No cabo, segunda testemunha, com a mesma leitura do P1.
* **P3** — No rádio, e é um dos dois desta célula. A piscada dele sai por um caminho feito para pintar mesmo com outro programa segurando o controle, e esse caminho nunca foi visto acendendo durante uma piscada. É o que você vai ver.
* **P4** — No rádio, e é o outro. Se os do cabo piscarem e os do rádio ficarem mudos, esse é o formato conhecido do defeito que este teste procura.

**A armadilha.** Cinco. (1) OS QUATRO TÊM DE PISCAR, de propósito — palavra sua. (2) A piscada dura pouco mais de meio segundo: olhe as barras antes de clicar. (3) UMA CONEXÃO DE RÁDIO PODE NASCER COM A BARRA TRAVADA, ignorando toda escrita, e nada avisa. Antes de reprovar, vá à aba Iluminação e clique no quadradinho amarelo da coluna do P3: se nem a cor pegar, você mediu a barra travada, não o aviso — clique em «Reiniciar o serviço», na aba Sistema, e refaça. (4) De dentro do Modo Nativo as piscadas não saem; ligar o Hefesto também não pisca. (5) Esta linha foi construída sem controle na mão: o produto sabe que mandou, não que acendeu.

---

## mapa-luz.lightbar.brilho-cabo — Lightbar — brilho de hardware · cabo

*Célula:* `luz.lightbar.brilho @ cabo`

**O que isto prova.** Prova que o trilho «Brilho» escurece a barra dos controles do cabo diminuindo a própria cor — a ilusão que você escolheu em 09/09, porque a barra não tem brilho de hardware — e que ele apaga a barra de vez no 0.

**Onde olhar.** Na aba Iluminação, linha «Brilho» de cada coluna: um trilho roxo com puxador e o número em porcento ao lado; a dica diz que ele grava no perfil ao soltar, sem esperar o «Salvar Perfil». Linha «Cor»: onze quadradinhos; os oito primeiros são as cores dos jogadores 1 a 8 — 1 azul, 2 vermelho, 3 verde, 4 rosa, 5 amarelo, 6 ciano, 7 laranja, 8 roxo — e os três últimos são tons a mais. A prova é a barra no aparelho: as duas tiras dos lados do touchpad.

**Os passos.**

1. Abra a aba Iluminação.
2. Anote o número em porcento da linha «Brilho» das quatro colunas.
3. Clique no quadradinho amarelo (o quinto) da linha «Cor», na coluna do P1.
4. Arraste o puxador da linha «Brilho» do P1 até o fim da direita, em 100%.
5. Arraste o mesmo puxador até mais ou menos a metade.
6. Confira que a barra do P1 ficou visivelmente mais fraca e continua amarela.
7. Arraste o puxador até o fim da esquerda, em 0%.
8. Anote se a barra do P1 apagou por completo ou ficou acesa fraquinha.
9. Arraste o puxador do P1 de volta a 100%.
10. Confira que a barra do P1 voltou ao amarelo cheio, e que as barras do P2, do P3 e do P4 não mudaram de brilho em nenhum momento.
11. Clique no quadradinho ciano (o sexto) da linha «Cor», na coluna do P2.
12. Arraste o puxador do P2 até a metade, depois até 0% e de volta a 100%, olhando a barra dele em cada parada.
13. Confira que o brilho do P1 não mudou enquanto você arrastava o do P2.
14. Devolva os quatro números de brilho aos valores anotados.
15. Clique no quadradinho da cor do número de cada um para devolver a cor: o primeiro no P1, o segundo no P2.

**Passa quando.** Nos dois controles do cabo a barra escurece junto com o número, some POR COMPLETO no 0 e volta cheia no 100, sem mudar de cor. Mexer no brilho de um nunca mexe no de outro.

**Por controle.**

* **P1** — No cabo, e é um dos dois desta célula. Amarelo, e o trilho em 100, na metade, em 0 e de volta.
* **P2** — No cabo, e é o outro. Ciano, o mesmo caminho. Enquanto arrasta o do P2, olhe o P1.
* **P3** — No rádio, testemunha. Não toque na coluna dele. O porcento e a barra dele ficam como estavam.
* **P4** — No rádio, segunda testemunha. A mesma conferência do P3.

**A armadilha.** Quatro. (1) O trilho multiplica a cor, e por isso no 0 a barra apaga inteira: se ela ficar acesa fraquinha no 0, isso é o achado. (2) O brilho de três degraus que o aparelho tem por dentro é das CINCO LÂMPADAS, não da barra — você mediu em 09/09 —, e o Hefesto não o comanda. Os três degraus da aba Vibração («Economia», «Balanceado», «Máximo») são força de tremor. (3) Arrastar grava no perfil ativo NA HORA, e a cor escolhida também fica: devolva as duas no fim. (4) Se as tiras da linha «LEDs» da coluna estiverem tracejadas, o Hefesto não afirma a cor de agora (a Steam segurando o controle, o Modo Nativo, ou cor desconhecida): o número vai para o disco e a barra pode não mudar — não é defeito do trilho.

---

## mapa-luz.lightbar.brilho-radio — Lightbar — brilho de hardware · rádio

*Célula:* `luz.lightbar.brilho @ rádio`

**O que isto prova.** Prova que o trilho «Brilho» escurece a barra dos controles do rádio diminuindo a própria cor, como no cabo, e que ele apaga a barra de vez no 0.

**Onde olhar.** Na aba Iluminação, linha «Brilho» de cada coluna: o trilho roxo com o número em porcento; a dica diz que ele grava no perfil ao soltar. Linha «Cor»: os onze quadradinhos (5 é amarelo, 6 é ciano). O nome da coluna, na linha «Modelo», termina em BT para quem está no rádio. A prova é a barra no aparelho.

**Os passos.**

1. Abra a aba Iluminação.
2. Confira na linha «Modelo» que as colunas do P3 e do P4 terminam em BT.
3. Anote o número em porcento da linha «Brilho» das quatro colunas.
4. Clique no quadradinho amarelo (o quinto) da linha «Cor», na coluna do P3.
5. Confira que a barra do P3 ficou amarela — sem isto o teste não roda.
6. Arraste o puxador da linha «Brilho» do P3 até 100%.
7. Arraste o mesmo puxador até mais ou menos a metade.
8. Confira que a barra do P3 ficou visivelmente mais fraca e continua amarela.
9. Arraste o puxador até 0%.
10. Anote se a barra do P3 apagou por completo ou ficou acesa fraquinha.
11. Arraste o puxador do P3 de volta a 100%.
12. Confira que a barra do P3 voltou ao amarelo cheio, e que as do P1, do P2 e do P4 não mudaram.
13. Clique no quadradinho ciano (o sexto) da linha «Cor», na coluna do P4.
14. Arraste o puxador do P4 até a metade, depois até 0% e de volta a 100%, olhando a barra dele em cada parada.
15. Devolva os quatro números de brilho aos valores anotados.
16. Clique no quadradinho da cor do número de cada um para devolver a cor: o terceiro no P3, o quarto no P4.

**Passa quando.** Nos dois controles do rádio a barra escurece junto com o número, some POR COMPLETO no 0 e volta cheia no 100. Mexer no brilho de um nunca mexe no de outro nem nos dois do cabo.

**Por controle.**

* **P1** — No cabo, testemunha e comparação. Não toque. Se o trilho não mexer nada no P3 nem no P4, arraste o do P1: se a barra DELE responder, o defeito é do rádio; se nem ela, o defeito não é do transporte.
* **P2** — No cabo, testemunha. Não toque. O porcento dele fica o mesmo.
* **P3** — No rádio, e é um dos dois desta célula. Amarelo, e o trilho em 100, na metade, em 0 e de volta.
* **P4** — No rádio, e é o outro. Ciano, o mesmo caminho.

**A armadilha.** Quatro. (1) O trilho multiplica a cor: acesa fraquinha no 0 é o achado. (2) UMA CONEXÃO DE RÁDIO PODE NASCER COM A BARRA TRAVADA, ignorando toda escrita, e nada avisa: se o P3 e o P4 não responderem a nada e o P1 responder, o suspeito é esse, e o que já foi medido devolvendo a barra é «Reiniciar o serviço», na aba Sistema. Não conclua que a culpa é de ter reconectado — «reconectar cura» já caiu nesta casa mais de uma vez. (3) O brilho de três degraus do aparelho é das cinco lâmpadas, não da barra (medido por você em 09/09). (4) Arrastar grava no perfil ativo na hora, e a cor escolhida também: devolva as duas.

---

## mapa-luz.lightbar.cor-cabo — Lightbar — cor RGB · cabo

*Célula:* `luz.lightbar.cor @ cabo`

**O que isto prova.** Prova que a cor que você clica na coluna de um controle do cabo acende de verdade na barra de luz dele, e só na dele.

**Onde olhar.** Na aba Iluminação, cada controle tem uma coluna, e o nome dele na linha «Modelo» termina em USB ou BT. A linha «Cor» tem onze quadradinhos: os oito primeiros são as cores dos jogadores 1 a 8 — 1 azul, 2 vermelho, 3 verde, 4 rosa, 5 amarelo, 6 ciano, 7 laranja, 8 roxo — e os três últimos são tons a mais. Um quadradinho com um X é a cor de outro controle, e o produto não a repete. Embaixo fica o código da cor (por exemplo #0000FF); clicar nele manda a mesma cor de novo. A PROVA é a barra no aparelho — as duas tiras dos lados do touchpad. A linha «LEDs» desenha as tiras na cor pedida, e as desenha TRACEJADAS quando o Hefesto não afirma a cor de agora.

**Os passos.**

1. Abra a aba Iluminação.
2. Confira na linha «Modelo» que as colunas do P1 e do P2 terminam em USB.
3. Ponha os quatro controles virados para cima, onde você veja as quatro barras de uma vez.
4. Anote a cor da barra dos quatro.
5. Clique no quadradinho amarelo (o quinto) da linha «Cor», na coluna do P1.
6. Confira que a barra do P1 ficou amarela e que as outras três não mudaram.
7. Clique no quadradinho ciano (o sexto), na coluna do P2.
8. Confira que a barra do P2 ficou ciano, que a do P1 continua amarela e que as do P3 e do P4 continuam como anotado.
9. Clique no código de cor embaixo da linha «Cor», na coluna do P1.
10. Confira que a barra do P1 continua amarela.
11. Espere um minuto sem mexer em nada.
12. Confira que as barras do P1 e do P2 continuam amarela e ciano, e que as tiras da linha «LEDs» deles estão lisas, não tracejadas.
13. Clique no quadradinho da cor do número de cada um para devolver: o primeiro no P1, o segundo no P2.

**Passa quando.** As barras dos dois controles do cabo acendem na cor clicada, no instante do clique, e continuam nela um minuto depois. Pintar um nunca muda a cor do outro, e as barras dos dois do rádio ficam exatamente como estavam.

**Por controle.**

* **P1** — No CABO, e é um dos dois que têm de obedecer. Amarelo, na hora, até o fim.
* **P2** — No CABO, e é o outro. Ciano. No instante em que você o pinta, olhe o P1: ele não pode mudar.
* **P3** — No RÁDIO, testemunha. Não toque na coluna dele. Se a barra dele mudar quando você pinta um do cabo, o clique pegou o transporte inteiro.
* **P4** — No RÁDIO, segunda testemunha. A cor antes e depois tem de ser a mesma.

**A armadilha.** Quatro. (1) A TELA NÃO É A PROVA: o código e o desenho mostram a cor PEDIDA; já se mediu o mesmo valor com a barra verde e com ela apagada. Quem responde é o plástico. (2) USE UMA COR QUE NINGUÉM MAIS QUEIRA: amarelo e ciano são dos números 5 e 6, e ninguém aqui tem esses números. Azul no P1 seria o pior teste — é a cor que o produto já dá ao 1. Se a barra voltar sozinha à cor de antes em menos de um minuto, anote: o seu clique não ficou. (3) Um quadradinho com X é a cor de outro controle: o clique nele é recusado, com a borda piscando laranja — escolha sua de 09/09. (4) Com a Steam aberta ganha quem escreve por último, e as tiras ficam tracejadas: por isso ela começa fechada, e tira tracejada aqui quer dizer que o teste não mede nada naquele momento.

---

## mapa-luz.lightbar.cor-radio — Lightbar — cor RGB · rádio

*Célula:* `luz.lightbar.cor @ rádio`

**O que isto prova.** Prova que a cor que você clica na coluna de um controle do rádio acende de verdade na barra de luz dele, e só na dele.

**Onde olhar.** Na aba Iluminação, a coluna de cada controle; o nome na linha «Modelo» termina em BT para quem está no rádio. A linha «Cor» tem onze quadradinhos: 1 azul, 2 vermelho, 3 verde, 4 rosa, 5 amarelo, 6 ciano, 7 laranja, 8 roxo, e três tons a mais; um quadradinho com X é a cor de outro controle. Embaixo, o código da cor, que manda a mesma cor de novo quando clicado. A prova é a barra no aparelho. A linha «LEDs» desenha as tiras TRACEJADAS quando o Hefesto não afirma a cor de agora.

**Os passos.**

1. Abra a aba Iluminação.
2. Confira na linha «Modelo» que as colunas do P3 e do P4 terminam em BT.
3. Ponha os quatro controles virados para cima, onde você veja as quatro barras de uma vez.
4. Anote a cor da barra dos quatro.
5. Clique no quadradinho amarelo (o quinto) da linha «Cor», na coluna do P3.
6. Confira que a barra do P3 ficou amarela e que as outras três não mudaram.
7. Clique no quadradinho ciano (o sexto), na coluna do P4.
8. Confira que a barra do P4 ficou ciano, que a do P3 continua amarela e que as do P1 e do P2 continuam como anotado.
9. Clique no código de cor embaixo da linha «Cor», na coluna do P3.
10. Confira que a barra do P3 continua amarela.
11. Espere um minuto sem mexer em nada.
12. Confira que as barras do P3 e do P4 continuam amarela e ciano, e que as tiras da linha «LEDs» deles estão lisas, não tracejadas.
13. Clique no quadradinho da cor do número de cada um para devolver: o terceiro no P3, o quarto no P4.

**Passa quando.** As barras dos dois controles do rádio acendem na cor clicada, no instante do clique, e continuam nela um minuto depois. Pintar um nunca muda a cor do outro, e as barras dos dois do cabo ficam exatamente como estavam.

**Por controle.**

* **P1** — No CABO, testemunha. Não toque. Se a barra dele mudar quando você pinta um do rádio, o clique pegou mais do que o controle escolhido.
* **P2** — No CABO, testemunha e comparação. Se NADA obedecer no rádio, pinte o P2 de roxo (o oitavo) e veja se ele obedece: se obedecer, o defeito é do rádio; se nem ele, não é do transporte. Devolva a cor dele no fim.
* **P3** — No RÁDIO, e é um dos dois que têm de obedecer. Amarelo, igual ao que chega a quem está no cabo.
* **P4** — No RÁDIO, e é o outro. Ciano.

**A armadilha.** Quatro. (1) A TELA NÃO É A PROVA: quem responde é o plástico. (2) UMA CONEXÃO DE RÁDIO PODE NASCER COM A BARRA TRAVADA, ignorando toda escrita, e o produto não tem como saber — nada na tela avisa. Se o P3 e o P4 não obedecerem a nada e o P2 obedecer, o suspeito é esse; o que já foi medido devolvendo a barra é «Reiniciar o serviço», na aba Sistema, não desligar o controle. (3) Não conclua que a culpa é de ter reconectado: «reconectar cura» já caiu nesta casa mais de uma vez. (4) Use cor que ninguém mais queira: verde no P3 seria o pior teste, porque é a cor que o produto já dá ao 3.

---

## mapa-luz.lightbar.fade-cabo — Lightbar — fade in/out · cabo

*Célula:* `luz.lightbar.fade @ cabo`

**O que isto prova.** Prova que, nos controles do cabo, a barra de luz troca de cor e apaga em corte seco — o produto nunca pede o acender e o apagar suaves que o aparelho sabe fazer.

**Onde olhar.** A prova é a barra no aparelho, olhada de LADO, pelo canto do olho — de frente o brilho fica na retina e inventa transição. Na tela, a aba Iluminação: a linha «Cor» de cada coluna (5 é amarelo, 8 é roxo) e a linha «Opções», que só tem o botão «Desligar». Não existe em aba nenhuma um ajuste de acender ou apagar suave.

**Os passos.**

1. Abra a aba Iluminação.
2. Confira na linha «Modelo» que as colunas do P1 e do P2 terminam em USB.
3. Ponha o P1 de lado, onde você o veja pelo canto do olho.
4. Clique no quadradinho amarelo (o quinto) da linha «Cor», na coluna do P1.
5. Anote se a barra acendeu de uma vez ou cresceu aos poucos.
6. Clique no quadradinho roxo (o oitavo), na mesma coluna.
7. Anote se a cor velha sumiu de uma vez ou foi desaparecendo.
8. Clique em «Desligar», na linha «Opções» da coluna do P1.
9. Anote se a barra apagou de uma vez ou foi sumindo devagar.
10. Clique de novo no quadradinho amarelo da coluna do P1.
11. Anote se ela acendeu de uma vez ou cresceu aos poucos.
12. Faça os mesmos quatro cliques na coluna do P2 — amarelo, roxo, «Desligar», amarelo —, anotando cada troca.
13. Faça os quatro cliques no P1 uma segunda vez, para descartar impressão sua.
14. Confira que as barras do P3 e do P4 não acenderam, não apagaram nem mudaram de cor em momento nenhum.
15. Clique no quadradinho da cor do número de cada um para devolver: o primeiro no P1, o segundo no P2.

**Passa quando.** Nos dois controles do cabo a barra acende, troca de cor e apaga em corte seco, nas duas voltas. Uma transição suave que se repita nas duas voltas é o ACHADO, porque hoje ninguém a pede ao aparelho.

**Por controle.**

* **P1** — No CABO, e é um dos dois desta célula. Os quatro cliques, olhando de lado, duas vezes.
* **P2** — No CABO, e é o outro. Dois aparelhos iguais têm de se comportar igual: se um esmaecer e o outro cortar seco, o achado é do aparelho.
* **P3** — No RÁDIO, testemunha. Não toque na coluna dele.
* **P4** — No RÁDIO, segunda testemunha. A mesma conferência do P3.

**A armadilha.** Três. (1) O SEU OLHO INVENTA TRANSIÇÃO: olhe de lado e faça duas vezes; só conta o que se repetir. (2) Com a Steam aberta a barra pode apagar sozinha depois do clique — isso é outro escritor, não apagar suave; por isso ela começa fechada. (3) O PERIGO ESTÁ REGISTRADO para quem for atrás disto depois: o aparelho sabe apagar suave, o comando existe no driver desta máquina e já foi mandado ao vivo — NENHUM EFEITO. Quem partir daí escreve código que APAGA a barra achando que a acende. Esta linha é leitura de código, e por isso está na sua fila.

---

## mapa-luz.lightbar.fade-radio — Lightbar — fade in/out · rádio

*Célula:* `luz.lightbar.fade @ rádio`

**O que isto prova.** Prova que, nos controles do rádio, a barra de luz troca de cor e apaga em corte seco — o produto nunca pede o acender e o apagar suaves que o aparelho sabe fazer.

**Onde olhar.** A prova é a barra no aparelho, olhada de lado, pelo canto do olho. Na aba Iluminação: a linha «Cor» de cada coluna (5 é amarelo, 8 é roxo) e a linha «Opções», que só tem «Desligar». Não existe em aba nenhuma um ajuste de acender ou apagar suave.

**Os passos.**

1. Abra a aba Iluminação.
2. Confira na linha «Modelo» que as colunas do P3 e do P4 terminam em BT.
3. Clique no quadradinho amarelo (o quinto) da linha «Cor», na coluna do P3, e confira que a barra dele obedeceu — sem isto o teste não roda.
4. Ponha o P3 de lado, onde você o veja pelo canto do olho.
5. Clique no quadradinho roxo (o oitavo), na mesma coluna.
6. Anote se a cor velha sumiu de uma vez ou foi desaparecendo.
7. Clique em «Desligar», na linha «Opções» da coluna do P3.
8. Anote se a barra apagou de uma vez ou foi sumindo devagar.
9. Clique de novo no quadradinho amarelo da coluna do P3.
10. Anote se ela acendeu de uma vez ou cresceu aos poucos.
11. Faça o mesmo na coluna do P4: amarelo e conferir que obedeceu, roxo, «Desligar», amarelo, anotando cada troca.
12. Faça os cliques do P3 uma segunda vez, para descartar impressão sua.
13. Clique no quadradinho da cor do número de cada um para devolver: o terceiro no P3, o quarto no P4.

**Passa quando.** Nos dois controles do rádio a barra acende, troca de cor e apaga em corte seco, nas duas voltas. Uma transição suave que se repita é o ACHADO. Se a barra do P3 ou a do P4 não obedecer a clique nenhum, o teste NÃO reprovou: ele não mediu fade nenhum, e tem de ser refeito depois de destravar a barra.

**Por controle.**

* **P1** — No CABO, testemunha e comparação. Não toque na coluna dele. Se nada obedecer no rádio, faça os mesmos cliques nele: se a barra DELE cortar seco e a do rádio não obedecer a nada, você mediu a barra travada do rádio, não fade.
* **P2** — No CABO, testemunha. Não toque. A barra dele não pode mudar.
* **P3** — No RÁDIO, e é um dos dois desta célula. Só meça depois de confirmar que ele obedece a uma cor.
* **P4** — No RÁDIO, e é o outro. Se um esmaecer e o outro cortar seco, o achado é do aparelho.

**A armadilha.** Quatro. (1) O SEU OLHO INVENTA TRANSIÇÃO: olhe de lado e faça duas vezes. (2) UMA CONEXÃO DE RÁDIO PODE NASCER COM A BARRA TRAVADA, sem nada avisar, e nesse estado nada acende — dá para ler isso como «apagou suave até sumir». Por isso o terceiro passo existe: primeiro prove que a barra obedece, depois meça como. O que já foi medido destravando é «Reiniciar o serviço», na aba Sistema. (3) Com a Steam aberta a barra pode apagar sozinha depois do clique — não é fade. (4) O comando de apagar suave existe no driver e já foi mandado ao vivo sem efeito nenhum: quem partir dele escreve código que apaga a barra achando que a acende.

---

## mapa-luz.lightbar.release_leds-cabo — Lightbar — devolver o claim (RELEASE_LEDS 0x08) · cabo

*Célula:* `luz.lightbar.release_leds @ cabo`

**O que isto prova.** Prova que o comando que «devolve a barra» não faz nada na barra de um controle do cabo — no cabo não há barra tomada a devolver — e mede o preço já conhecido nas cinco lâmpadas.

**Onde olhar.** No aparelho: a barra de luz (as duas tiras dos lados do touchpad) e as cinco lâmpadas entre o touchpad e o botão PS. Na tela não há mais onde mandar este comando: o botão de cada coluna que fazia isso saiu da aba Iluminação em 07/09, por ordem sua. O gesto que sobrou é um comando de terminal, e quem coordena digita por você: `hefesto-dualsense4unix lightbar-reset --uniq` seguido do endereço do controle. A aba Iluminação serve para pôr uma cor conhecida antes.

**Os passos.**

1. Abra a aba Iluminação.
2. Anote a cor da barra e o desenho das cinco lâmpadas dos quatro aparelhos.
3. Clique no quadradinho amarelo (o quinto) da linha «Cor», na coluna do P1.
4. Confira que a barra do P1 ficou amarela.
5. Peça a quem coordena para mandar o comando que devolve a barra SÓ ao P1.
6. Anote o que a barra do P1 fez: continuou amarela, apagou ou mudou de cor.
7. Anote o que as cinco lâmpadas do P1 fizeram.
8. Confira que a barra e as lâmpadas do P2, do P3 e do P4 não mudaram.
9. Clique no quadradinho amarelo da coluna do P1 de novo e confira que a barra ainda obedece.
10. Clique no quadradinho azul (o primeiro), na coluna do P1, para devolver a cor.
11. Se as lâmpadas do P1 apagaram, abra a aba Sistema, clique em «Reiniciar o serviço» e anote se elas voltaram.

**Passa quando.** A barra do P1 continua na cor que estava e continua obedecendo às cores depois do comando — no cabo não há o que devolver —, e nenhum dos outros três muda. As cinco lâmpadas apagarem é o preço já medido: anota-se, não reprova.

**Por controle.**

* **P1** — No CABO, e é ESTE. Amarelo, o comando só para ele, e a barra lida no plástico.
* **P2** — No CABO, testemunha. Não toque. Barra e lâmpadas iguais antes e depois.
* **P3** — No RÁDIO, testemunha — e aqui ela é o ponto do teste: se a barra ou as lâmpadas dele mudarem quando o comando vai ao P1, ele saiu para mais do que o controle escolhido.
* **P4** — No RÁDIO, segunda testemunha. A mesma conferência do P3.

**A armadilha.** Três. (1) O comando existe para o rádio; a casa decidiu que no cabo ele não se aplica — mas o produto o manda a qualquer controle sem olhar o transporte, e é por isso que este teste do cabo vale. (2) O PREÇO JÁ ESTÁ MEDIDO: esse comando APAGA as cinco lâmpadas de jogador, e elas não voltam sozinhas; o último passo mede se «Reiniciar o serviço» as devolve. (3) Não é o interruptor «Cores automáticas por controle», no alto da aba: aquele é do perfil e vale para os quatro — não mexa nele.

---

## mapa-luz.lightbar.release_leds-radio — Lightbar — devolver o claim (RELEASE_LEDS 0x08) · rádio

*Célula:* `luz.lightbar.release_leds @ rádio`

**O que isto prova.** Prova que o comando que devolve a barra ao sistema, mandado a um controle do rádio já assentado, não deixa a barra dele travada — ela continua obedecendo às cores — e mede o preço conhecido nas cinco lâmpadas.

**Onde olhar.** No aparelho: a barra de luz e as cinco lâmpadas entre o touchpad e o botão PS. Na tela não há mais onde mandar este comando: o botão de cada coluna que fazia isso saiu da aba Iluminação em 07/09, por ordem sua. O gesto que sobrou é o comando de terminal que quem coordena digita por você: `hefesto-dualsense4unix lightbar-reset --uniq` seguido do endereço do controle. A aba Iluminação serve para pôr uma cor conhecida antes e para conferir depois que a barra obedece.

**Os passos.**

1. Confira que o P3 e o P4 estão ligados há mais de um minuto.
2. Abra a aba Iluminação.
3. Anote a cor da barra e o desenho das cinco lâmpadas dos quatro aparelhos.
4. Clique no quadradinho amarelo (o quinto) da linha «Cor», na coluna do P3, e confira que a barra dele ficou amarela.
5. Peça a quem coordena para mandar o comando que devolve a barra SÓ ao P3.
6. Anote o que a barra do P3 fez: continuou amarela, apagou ou mudou de cor.
7. Anote o que as cinco lâmpadas do P3 fizeram.
8. Confira que a barra e as lâmpadas do P1, do P2 e do P4 não mudaram.
9. Clique no quadradinho ciano (o sexto), na coluna do P3.
10. Confira que a barra do P3 ficou ciano — é aqui que se vê se ela travou.
11. Clique no quadradinho verde (o terceiro), na coluna do P3, para devolver a cor.
12. Se as lâmpadas do P3 apagaram, abra a aba Sistema, clique em «Reiniciar o serviço» e anote se elas voltaram.

**Passa quando.** Depois do comando, a barra do P3 continua obedecendo às cores — ela vira ciano quando você clica —, e nenhum dos outros três muda. As cinco lâmpadas apagarem é o preço já medido: anota-se, não reprova. Barra que não obedece mais depois do comando reprova.

**Por controle.**

* **P1** — No CABO, testemunha. Não toque. Se as lâmpadas DELE apagarem quando o comando vai ao P3, ele pegou mais do que o controle escolhido.
* **P2** — No CABO, segunda testemunha. A mesma conferência do P1.
* **P3** — No RÁDIO, e é ESTE: é no rádio que existe barra tomada a devolver.
* **P4** — No RÁDIO, testemunha nesta célula. Não toque. As lâmpadas dele não podem apagar junto.

**A armadilha.** Três. (1) NÃO MANDE O COMANDO NOS PRIMEIROS SEGUNDOS DEPOIS DE O CONTROLE ENTRAR NO RÁDIO. Há suspeita medida de que, mandado dentro de uns três segundos e meio da conexão, ele TRAVA a barra em vez de devolvê-la; fora dessa janela não travou. É por isso que o primeiro passo pede um minuto de controle ligado. (2) O PREÇO JÁ ESTÁ MEDIDO: o comando apaga as cinco lâmpadas de jogador, e elas não voltam sozinhas. (3) Sozinho, o comando só larga a barra: a cor que fica no plástico é a última escrita. O botão que saiu pintava a cor do número por cima; o comando de terminal não pinta.

---

## mapa-luz.recursos_proprios-cabo — Recursos próprios do fabricante (turbo, LEDs de modo) · cabo

*Célula:* `luz.recursos_proprios @ cabo`

**O que isto prova.** Prova que os controles do cabo não têm turbo nem lâmpada de modo, e que o Hefesto não inventa nenhum dos dois: as luzes do aparelho são três, e só três.

**Onde olhar.** No APARELHO, com o P1 e o P2 na mão: as três luzes são a barra de luz (as duas tiras dos lados do touchpad), a fileira de cinco lâmpadas brancas entre o touchpad e o botão PS, e a luz dentro do botãozinho de microfone, abaixo do botão PS. Na TELA, a aba Iluminação: a coluna da esquerda nomeia as sete linhas de cada controle — «Controle», «Modelo», «Cor», «Brilho», «Jogador», «LEDs» e «Opções». Nenhuma fala em turbo nem em lâmpada de modo.

**Os passos.**

1. Pegue o P1, vire-o para cima e diminua a luz do ambiente.
2. Aponte cada luz que você vê acesa no plástico e conte quantas são.
3. Confira que são três: a barra dos lados do touchpad, a fileira de cinco lâmpadas e a luz do botão de microfone.
4. Vire o P1 de cabeça para baixo, olhe os ombros, o fundo e os punhos, e anote se achou qualquer outra luz.
5. Procure no P1 um botão de turbo e anote que não existe.
6. Aperte o botão de microfone do P1 e confira que a luz dele responde.
7. Aperte o botão de microfone do P1 de novo, para devolver o microfone ao que era.
8. Pegue o P2 e faça o mesmo: conte as luzes, olhe o fundo, procure o turbo, e aperte o botão de microfone duas vezes.
9. Abra a aba Iluminação.
10. Leia os nomes das sete linhas na coluna da esquerda e confira que nenhum fala em turbo nem em lâmpada de modo.
11. Passe pelas outras nove abas procurando a palavra turbo.

**Passa quando.** Os dois controles do cabo têm exatamente três luzes, nenhum tem botão de turbo, e a palavra turbo não aparece em aba nenhuma do Hefesto. Uma quarta luz no plástico, ou um ajuste de turbo na tela, é o ACHADO — o mapa diz que nenhum dos dois existe neste aparelho.

**Por controle.**

* **P1** — No CABO, e é um dos dois desta célula. Conte as luzes na mão e procure o turbo.
* **P2** — No CABO, e é a segunda opinião: dois aparelhos iguais têm o mesmo conjunto de luzes. Se um tiver uma luz que o outro não tem, o achado é do aparelho.
* **P3** — No RÁDIO, testemunha. Não precisa mexer nele; só conte as luzes dele e confirme que são as mesmas três.
* **P4** — No RÁDIO, segunda testemunha. A mesma contagem.

**A armadilha.** Esta linha junta DUAS perguntas com respostas opostas. Turbo e lâmpada de modo NÃO EXISTEM neste aparelho — não é o Hefesto que deixou de fazer. Mas existe no DualSense um canal próprio de luz, do lado do fabricante, que ninguém desta casa jamais tocou: não tem botão, não tem tela e não se prova com a mão. ESTE TESTE RESPONDE A PRIMEIRA METADE E NÃO ALCANÇA A SEGUNDA — um verde aqui não quer dizer que não há nada escondido. Os três degraus da aba Vibração («Economia», «Balanceado», «Máximo») são força de tremor, não luz de modo. A luz do botão de microfone tem linha própria no mapa, e está aqui só para fechar a conta das três.

---

## mapa-luz.recursos_proprios-radio — Recursos próprios do fabricante (turbo, LEDs de modo) · rádio

*Célula:* `luz.recursos_proprios @ rádio`

**O que isto prova.** Prova que os controles do rádio não têm turbo nem lâmpada de modo, e que trocar de fio não faz aparecer nenhuma luz que o cabo não tenha.

**Onde olhar.** No APARELHO, com o P3 e o P4 na mão: a barra de luz (as duas tiras dos lados do touchpad), a fileira de cinco lâmpadas entre o touchpad e o botão PS, e a luz dentro do botãozinho de microfone, abaixo do botão PS. Na TELA, a aba Iluminação: as sete linhas de cada controle — «Controle», «Modelo», «Cor», «Brilho», «Jogador», «LEDs» e «Opções» —, nenhuma sobre turbo ou lâmpada de modo.

**Os passos.**

1. Pegue o P3, vire-o para cima e diminua a luz do ambiente.
2. Aponte cada luz que você vê acesa no plástico e conte quantas são.
3. Confira que são três: a barra dos lados do touchpad, a fileira de cinco lâmpadas e a luz do botão de microfone.
4. Vire o P3 de cabeça para baixo, olhe os ombros, o fundo e os punhos, e anote se achou qualquer outra luz.
5. Procure no P3 um botão de turbo e anote que não existe.
6. Aperte o botão de microfone do P3 e confira que a luz dele responde.
7. Aperte o botão de microfone do P3 de novo, para devolver o microfone ao que era.
8. Pegue o P4 e faça o mesmo: conte as luzes, olhe o fundo, procure o turbo, e aperte o botão de microfone duas vezes.
9. Ponha o P3 e o P1 lado a lado e compare luz por luz.
10. Anote qualquer luz que um tenha e o outro não.
11. Abra a aba Iluminação.
12. Leia os nomes das sete linhas na coluna da esquerda e confira que nenhum fala em turbo nem em lâmpada de modo.
13. Passe pelas outras nove abas procurando a palavra turbo.

**Passa quando.** Os dois controles do rádio têm exatamente três luzes, nenhum tem botão de turbo, e a palavra turbo não aparece em aba nenhuma. Um controle do rádio com uma luz que o do cabo não tem é ACHADO GRANDE, porque o aparelho anuncia o mesmo conjunto nos dois fios.

**Por controle.**

* **P1** — No CABO, testemunha — e aqui ela tem trabalho: ao lado do P3, luz por luz. É essa comparação que responde se trocar de fio faz aparecer alguma coisa.
* **P2** — No CABO, segunda testemunha. Conte as luzes dele também, para ter dois do cabo na conta.
* **P3** — No RÁDIO, e é um dos dois desta célula. Conte as luzes e procure o turbo.
* **P4** — No RÁDIO, e é a segunda opinião: se um dos dois do rádio tiver uma luz que o outro não tem, o achado é do aparelho.

**A armadilha.** Duas perguntas com respostas opostas: turbo e lâmpada de modo NÃO EXISTEM neste aparelho; o canal próprio de luz do fabricante existe nos DOIS fios e ninguém desta casa o tocou — este teste não o alcança, e um verde aqui não quer dizer que não há nada escondido. Os três degraus da aba Vibração são força de tremor, não luz de modo. E não conte a barra piscando vermelha quando a bateria acaba como uma luz nova: é a mesma barra fazendo outra coisa.

---

## mapa-luz.replica_output_jogo-cabo — Réplica do output do jogo (lightbar, LED de jogador, gatilho) · cabo

*Célula:* `luz.replica_output_jogo @ cabo`

**O que isto prova.** Prova que, quando o jogo pinta a luz do controle que ele enxerga, a barra do controle de verdade ligado por cabo acende igual.

**Onde olhar.** Na aba Jogar: a linha «Status» em «Ligado»; o quadro «Modo» com o cartão «Sony DualSense» aceso — é o caminho por onde a luz volta do jogo ao controle —; e o quadro «O controle é visto como:», onde cada controle escolhe entre «DualSense», «Xbox 360» e «Nintendo Pro». Para o jogo pintar a luz, o controle tem de ser visto como «DualSense»: um «Xbox 360» não tem barra de luz. Na aba Iluminação, a linha «Cor» para pôr uma cor de partida. A prova é a barra no aparelho. A fonte não diz qual jogo pinta a barra: escolha um que você saiba que pinta e anote o nome.

**Os passos.**

1. Abra a aba Jogar.
2. Confira que o «Status» está em «Ligado» e que o cartão «Sony DualSense» do quadro «Modo» está aceso.
3. Clique em «DualSense» no cartão do P1 e no do P2, no quadro «O controle é visto como:».
4. Abra a aba Iluminação.
5. Clique no quadradinho amarelo (o quinto) da linha «Cor», na coluna do P1 e na do P2.
6. Confira que as duas barras ficaram amarelas — o ponto de partida, numa cor que jogo nenhum pediria.
7. Anote a cor das barras do P3 e do P4.
8. Abra o jogo que você escolheu e deixe-o carregar.
9. Entre na partida SÓ com o P1, deixando os outros três fora.
10. Confira que a barra do P1 deixou de ser amarela e passou à cor que o jogo pediu.
11. Confira que as barras do P2, do P3 e do P4 continuam como estavam.
12. Entre na partida com o P2 também.
13. Confira que a barra do P2 mudou, e que as do P3 e do P4 continuam nas cores anotadas.
14. Anote o nome do jogo e a cor que ele pôs em cada um.
15. Feche o jogo e clique, na aba Iluminação, no quadradinho da cor do número do P1 (o primeiro) e do P2 (o segundo).

**Passa quando.** Nos dois controles do cabo a barra troca do amarelo para a cor que o jogo mandou, sozinha, sem você tocar em nada no Hefesto. E os dois do rádio, fora da partida, não mudam de cor.

**Por controle.**

* **P1** — No CABO, e é um dos dois desta célula. Amarelo, e entra na partida sozinho.
* **P2** — No CABO, e é o outro. Entra depois do P1. Se o P1 virar e o P2 não, o defeito é do segundo lugar na fila, não do transporte.
* **P3** — No RÁDIO, testemunha. Ligado e FORA da partida. Se a barra dele mudar sem ele ter entrado, a cópia está indo para quem não pediu.
* **P4** — No RÁDIO, segunda testemunha, também fora da partida.

**A espera.** O jogo leva minutos para chegar ao menu, e nenhum deles é para ficar olhando. Deixe-o carregando e volte quando ouvir o som do menu: o amarelo continua nas barras até o jogo pintar por cima. Ao voltar, olhe primeiro a barra do P1, antes de entrar na partida — se ela já deixou de ser amarela sem ninguém ter entrado, isso é achado e vale anotar a hora.

**A armadilha.** Cinco, e três delas acendem a barra sem provar nada. (1) MÁSCARA ERRADA MATA O TESTE SEM HAVER DEFEITO: visto como «Xbox 360», o controle não tem barra do lado do jogo. (2) O CAMINHO TAMBÉM: com o cartão «Xbox» do quadro «Modo» aceso, o jogo vê o DualSense pelo canal comum, e por ele a luz não volta. (3) NO MODO NATIVO NÃO HÁ O QUE COPIAR: o jogo fala direto com o controle, e a luz que acende é dele, não uma cópia. (4) A Steam escreve na barra por conta própria e ganha quem escreve por último — por isso ela começa fechada. (5) Se o jogo escolhido nunca pintar, o resultado não é vermelho, é «não mediu»: troque de jogo e anote qual usou. Não julgue pela tela: a prova é o plástico.

---

## mapa-luz.replica_output_jogo-radio — Réplica do output do jogo (lightbar, LED de jogador, gatilho) · rádio

*Célula:* `luz.replica_output_jogo @ rádio`

**O que isto prova.** Prova que, quando o jogo pinta a luz do controle que ele enxerga, a barra do controle de verdade ligado por rádio acende igual — e anota se o gatilho pedido pelo jogo também chega.

**Onde olhar.** Na aba Jogar: «Status» em «Ligado»; o cartão «Sony DualSense» aceso no quadro «Modo» — é o caminho por onde luz e gatilho voltam do jogo —; e o quadro «O controle é visto como:», com «DualSense» escolhido. Na aba Iluminação, a linha «Cor» para a cor de partida. A prova é o aparelho: a barra de luz e a resistência que a sua mão sente no L2 e no R2. Escolha um jogo que você saiba que pinta a barra e anote o nome.

**Os passos.**

1. Abra a aba Jogar.
2. Confira que o «Status» está em «Ligado» e que o cartão «Sony DualSense» do quadro «Modo» está aceso.
3. Clique em «DualSense» no cartão do P3 e no do P4, no quadro «O controle é visto como:».
4. Aperte o L2 e o R2 do P3 até o fundo e guarde na mão como eles estão agora.
5. Abra a aba Iluminação.
6. Clique no quadradinho amarelo (o quinto) da linha «Cor», na coluna do P3 e na do P4.
7. Confira que as duas barras ficaram amarelas — se nem o amarelo pegar, o teste não roda.
8. Anote a cor das barras do P1 e do P2.
9. Abra o jogo que você escolheu e deixe-o carregar.
10. Entre na partida SÓ com o P3, deixando os outros três fora.
11. Confira que a barra do P3 deixou de ser amarela e passou à cor que o jogo pediu.
12. Aperte o L2 e o R2 do P3 até o fundo, dentro do jogo.
13. Anote se a resistência mudou em relação à que você guardou na mão.
14. Confira que as barras do P1, do P2 e do P4 continuam como estavam.
15. Entre na partida com o P4 também.
16. Confira que a barra do P4 mudou, e que as do P1 e do P2 continuam nas cores anotadas.
17. Anote o nome do jogo, a cor que ele pôs em cada um e o que a sua mão sentiu no gatilho.
18. Feche o jogo e clique, na aba Iluminação, no quadradinho da cor do número do P3 (o terceiro) e do P4 (o quarto).

**Passa quando.** Nos dois controles do rádio a barra troca do amarelo para a cor que o jogo mandou, sozinha — e os dois do cabo, fora da partida, não mudam. A resistência do L2 e do R2 é achado a anotar: se a luz chegar e o gatilho não, essa é a metade que o mapa ainda dá como incompleta neste lado.

**Por controle.**

* **P1** — No CABO, testemunha e comparação. Fora da partida. Se as barras do P3 e do P4 não mudarem, entre com o P1: se a dele mudar, o defeito é do rádio; se nem a dele, o jogo não está pintando e o teste não mediu nada.
* **P2** — No CABO, segunda testemunha. Fora da partida, e a barra não muda.
* **P3** — No RÁDIO, e é um dos dois desta célula. Amarelo, entra sozinho, e é nele que se aperta o gatilho.
* **P4** — No RÁDIO, e é o outro. Entra depois do P3.

**A espera.** O jogo leva minutos para chegar ao menu, e nenhum deles é para ficar olhando. Deixe-o carregando e volte quando ouvir o som do menu: o amarelo continua nas barras até o jogo pintar por cima. Ao voltar, olhe primeiro as barras do P3 e do P4, ANTES de entrar na partida — se alguma já deixou de ser amarela sem ninguém ter entrado, anote a hora.

**A armadilha.** Seis. (1) Máscara «Xbox 360» não tem barra do lado do jogo: o teste morre sem defeito. (2) Com o cartão «Xbox» do quadro «Modo» aceso a luz não volta pelo canal comum. (3) No Modo Nativo não há cópia: a luz que acende é do jogo. (4) UMA CONEXÃO DE RÁDIO PODE NASCER COM A BARRA TRAVADA, sem nada avisar: por isso o passo do amarelo existe — se nem ele pegar, clique em «Reiniciar o serviço», na aba Sistema, e refaça. (5) A Steam escreve na barra por conta própria; ela começa fechada. (6) Se o jogo nunca pintar, o resultado é «não mediu», não vermelho. E não some as duas metades: luz e gatilho vêm pelo mesmo caminho, mas são medidas separadas.

---

## mapa-movimento.acelerometro-cabo — Acelerômetro — número para a interface · cabo

*Célula:* `movimento.acelerometro @ cabo`

**O que isto prova.** Prova que os dois controles do cabo mandam a inclinação em número para a tela, e que o número segue o controle que você inclinou — e só ele.

**Onde olhar.** Aba Controles. O chip «Todos», na fita do topo, abre os quatro cards de uma vez. Dentro de cada card, na coluna da direita, há duas molduras: «Giroscópio» em cima e «Acelerômetro» embaixo — é a de BAIXO que importa aqui. Ela tem três linhas, X, Y e Z, cada uma com um número em g, com duas casas (por exemplo +0.98), e uma barrinha ao lado. Um controle deitado e parado dá um dos três perto de 1 e os outros dois perto de zero, porque 1 g é a gravidade. Um traço no lugar do número quer dizer que a leitura ainda não chegou. A linha de cada controle diz USB ou BT logo depois do nome.

**Os passos.**

1. Abra a aba Controles.
2. Confira que as linhas do P1 e do P2 dizem USB e as do P3 e do P4 dizem BT.
3. Deite os quatro controles numa superfície plana, virados para cima, e tire as mãos de todos.
4. Clique no chip «Todos», na fita do topo.
5. Espere uns três segundos com os cards abertos.
6. Anote os três números do «Acelerômetro» de cada um dos quatro.
7. Confira que, nos quatro, um dos três está perto de 1 e os outros dois perto de zero.
8. Pegue só o P1 e incline-o devagar para a esquerda, sem sacudir.
9. Confira que os números do «Acelerômetro» do P1 andam enquanto você inclina, e que os do P2, do P3 e do P4 ficam parados.
10. Incline o P1 para a direita.
11. Confira que os números do P1 andam para o outro lado.
12. Deite o P1 de volta.
13. Confira que os números do P1 voltam para perto do que você anotou.
14. Pegue só o P2 e incline-o devagar para a esquerda e depois para a direita.
15. Confira que só os números do P2 andam, e que eles voltam quando você o deita.
16. Compare o repouso do P1 com o do P2: parecidos, e não iguais casa por casa.

**Passa quando.** Nos dois do cabo, os três números do «Acelerômetro» andam quando você inclina aquele controle, andam para o outro lado quando inclina para o outro lado, e voltam para perto do repouso quando você o deita. Parados e deitados, os quatro dão um dos três perto de 1. E inclinar um controle nunca mexe nos números de outro.

**Por controle.**

* **P1** — No cabo, e é o primeiro que TEM de reagir. Incline-o para os dois lados com os outros três largados.
* **P2** — No cabo, e é o segundo. O repouso dele não pode ser IDÊNTICO ao do P1: dois aparelhos parados dão números parecidos, nunca iguais casa a casa.
* **P3** — No rádio, testemunha. Não encoste nele. Se os números dele andarem junto com os do P1, a tela mostra a leitura de um controle no card de outro.
* **P4** — No rádio, segunda testemunha. Se o P3 ficou parado e o P4 andou junto com o P1, o problema é o endereço do card, não o rádio.

**A armadilha.** Quatro. (1) O DESENHO: quando a tela não está lendo, ela mostra os números fixos do desenho, +0.105 · +0.976 · +0.170, com TRÊS casas. Se você vir esses três, ou dois controles em poses diferentes com números idênticos, não houve leitura — o teste não passou nem reprovou. (2) O PRIMEIRO OLHAR MEDE A AUSÊNCIA: a leitura nasce quando alguém pede e morre cinco segundos depois do último pedido; abrir e olhar no mesmo instante mostra traços. (3) O TRAÇO NÃO É ZERO: anote como não medido. (4) O mapa registra este caminho como MONTADO; ver o número sair do aparelho e chegar íntegro à tela é o que a sua mão faz aqui. Não julgue esta linha pelo que um jogo faz com a inclinação: isso é outra linha.

---

## mapa-movimento.acelerometro-radio — Acelerômetro — número para a interface · rádio

*Célula:* `movimento.acelerometro @ rádio`

**O que isto prova.** Prova que os dois controles do rádio mandam a inclinação em número para a tela, igual aos do cabo, e que o número fica no card do controle certo.

**Onde olhar.** Aba Controles. O chip «Todos», na fita do topo, abre os quatro cards. Em cada card, coluna da direita, a moldura de BAIXO é o «Acelerômetro», com X, Y e Z em g, com duas casas, e uma barrinha ao lado. Deitado e parado, um dos três dá perto de 1 e os outros dois perto de zero. Traço no lugar do número quer dizer que a leitura ainda não chegou. A linha de cada controle diz USB ou BT logo depois do nome: é isso que separa quem tem de reagir de quem é testemunha.

**Os passos.**

1. Abra a aba Controles.
2. Confira que as linhas do P3 e do P4 dizem BT, sem nenhum cabo plugado neles.
3. Deite os quatro controles numa superfície plana, virados para cima, e tire as mãos de todos.
4. Clique no chip «Todos», na fita do topo.
5. Espere uns três segundos com os cards abertos.
6. Anote os três números do «Acelerômetro» dos quatro.
7. Confira que os cards do P3 e do P4 mostram número, e não traço, nas três linhas.
8. Pegue só o P3 e incline-o devagar para a esquerda, sem sacudir.
9. Confira que os números do «Acelerômetro» do P3 andam enquanto você inclina, e que os do P1, do P2 e do P4 ficam parados.
10. Deite o P3 de volta.
11. Confira que os números do P3 voltam para perto do que você anotou.
12. Pegue só o P4 e incline-o devagar para os dois lados.
13. Confira que só os números do P4 andam, e que eles voltam quando você o deita.
14. Compare o repouso do P3 com o do P4, e o dos dois do rádio com o dos dois do cabo: parecidos, com as mesmas duas casas e sem traço.

**Passa quando.** Nos dois do rádio, os três números do «Acelerômetro» andam quando você inclina aquele controle e voltam para perto do repouso quando você o deita. Os dois cards mostram NÚMERO, não traço. Inclinar um nunca mexe nos números de outro. E o número do rádio tem a mesma cara do número do cabo: parado, um eixo perto de 1.

**Por controle.**

* **P1** — No cabo, testemunha. Não encoste nele. É ele que prova que a tela está lendo: se o P1 mostra números vivos e o P3 mostra traço, o buraco é do rádio, não da tela.
* **P2** — No cabo, segunda testemunha. Se os números dele andarem quando você inclina o P3, alguém escreve no card errado.
* **P3** — No rádio, e é o primeiro que TEM de reagir.
* **P4** — No rádio, e é o segundo. Se algum dos quatro mostrar traço para sempre, anote qual.

**A armadilha.** Quatro. (1) O DESENHO tem números fixos no «Acelerômetro», +0.105 · +0.976 · +0.170, com três casas: vê-los, ou ver dois cards com os mesmos três números com os aparelhos em poses diferentes, é sinal de que não houve leitura. (2) O PRIMEIRO OLHAR MEDE A AUSÊNCIA: espere os três segundos. (3) Traço não é zero. (4) O mapa registra o caminho como MONTADO, com uma leitura pelo rádio medida em 03/09 que deu 0,9966 g de gravidade; o degrau seguinte é o que a sua mão confirma aqui. Não julgue esta linha pelo que um jogo faz.

---

## mapa-movimento.acelerometro.jogo-cabo — Acelerômetro — dado para o jogo · cabo

*Célula:* `movimento.acelerometro.jogo @ cabo`

**O que isto prova.** Prova que o interruptor «Acelerômetro» de um controle do cabo mira naquele controle e só naquele sensor — sem encostar no «Giroscópio» dele nem nos outros três.

**Onde olhar.** Aba Controles, na LINHA de cada controle — ela aparece com o card aberto ou fechado. No fim da linha há dois interruptores lado a lado, «Giroscópio» e «Acelerômetro», cada um com uma bolinha verde quando o sensor está ligado e cinza quando está desligado. A dica do «Acelerômetro» diz: «Ligado: o jogo recebe a inclinação e o chacoalhar deste controle.». Mais à esquerda, na mesma linha, a palavra «DualSense», «Xbox 360» ou «Nintendo Pro» é o que o jogo vê daquele controle. Depois do clique, a borda do interruptor pisca verde quando ele pegou inteiro, e laranja quando recusou ou pegou só pela metade.

**Os passos.**

1. Abra a aba Controles.
2. Clique no chip «Todos», na fita do topo.
3. Confira que as linhas do P1 e do P2 dizem «DualSense» no que o jogo vê.
4. Anote a cor das oito bolinhas: «Giroscópio» e «Acelerômetro» das quatro linhas.
5. Clique no interruptor «Acelerômetro» da linha do P1.
6. Confira que a bolinha dele trocou de cor, e anote a cor em que a borda piscou.
7. Confira que o «Giroscópio» da mesma linha e os dois interruptores do P2, do P3 e do P4 não mudaram.
8. Clique de novo no «Acelerômetro» do P1, para devolvê-lo.
9. Clique no interruptor «Acelerômetro» da linha do P2.
10. Confira que só a bolinha dele trocou de cor, e anote a cor da borda.
11. Clique de novo no «Acelerômetro» do P2, para devolvê-lo.
12. Confira que as oito bolinhas voltaram às cores anotadas.

**Passa quando.** O clique no «Acelerômetro» do P1 troca a cor da bolinha DELE e de mais nada, e a borda pisca verde; o mesmo no P2. O «Giroscópio» da mesma linha e as linhas dos outros não se mexem. No fim, os oito voltam ao que eram.

**Por controle.**

* **P1** — No cabo, e é o primeiro em que você clica. O «Giroscópio» da mesma linha é a testemunha mais importante: ele não pode mudar junto.
* **P2** — No cabo, e é o segundo. Antes de clicar, olhe onde estão as oito bolinhas: o defeito que este teste caça é um clique numa linha mexer noutra.
* **P3** — No rádio, testemunha. Não clique em nada na linha dele.
* **P4** — No rádio, segunda testemunha. Se o P3 ficou parado e o P4 mudou junto com o P1, o clique acertou o controle errado.

**A armadilha.** Onde a prova parou, e parou cedo: o mapa registra os bytes da inclinação MONTADOS na janela que vai ao controle virtual, e nada além. Não reprove esta linha porque um jogo não reagiu a você inclinar o controle — o que se mede aqui é o interruptor acertar o controle e o sensor certos. Três coisas que parecem defeito e não são: visto como «Xbox 360», o jogo NÃO TEM acelerômetro; a borda laranja com a bolinha trocando de cor quer dizer meia obediência — em Modo Nativo o jogo lê o controle direto, e o interruptor não o alcança; e a borda laranja com a bolinha parada quer dizer que o Hefesto ainda não disse se o sensor está ligado — ele se nega a chutar o oposto. Não clique nos dois interruptores da mesma linha de uma vez: isso esconde justamente o defeito procurado.

---

## mapa-movimento.acelerometro.jogo-radio — Acelerômetro — dado para o jogo · rádio

*Célula:* `movimento.acelerometro.jogo @ rádio`

**O que isto prova.** Prova que o interruptor «Acelerômetro» de um controle do rádio mira naquele controle e só naquele sensor, igual aos do cabo.

**Onde olhar.** Aba Controles, na LINHA de cada controle — com o card aberto ou fechado. No fim da linha, os dois interruptores «Giroscópio» e «Acelerômetro», com a bolinha verde quando ligado e cinza quando desligado; a dica do «Acelerômetro» diz: «Ligado: o jogo recebe a inclinação e o chacoalhar deste controle.». Mais à esquerda, «DualSense», «Xbox 360» ou «Nintendo Pro» é o que o jogo vê. Depois do clique, a borda do interruptor pisca verde quando pegou inteiro e laranja quando recusou ou pegou pela metade.

**Os passos.**

1. Abra a aba Controles.
2. Clique no chip «Todos», na fita do topo.
3. Confira que as linhas do P3 e do P4 dizem BT e «DualSense» no que o jogo vê.
4. Anote a cor das oito bolinhas: «Giroscópio» e «Acelerômetro» das quatro linhas.
5. Clique no interruptor «Acelerômetro» da linha do P3.
6. Confira que a bolinha dele trocou de cor, e anote a cor em que a borda piscou.
7. Confira que o «Giroscópio» da mesma linha e os dois interruptores do P1, do P2 e do P4 não mudaram.
8. Clique de novo no «Acelerômetro» do P3, para devolvê-lo.
9. Clique no interruptor «Acelerômetro» da linha do P4.
10. Confira que só a bolinha dele trocou de cor, e anote a cor da borda.
11. Clique de novo no «Acelerômetro» do P4, para devolvê-lo.
12. Confira que as oito bolinhas voltaram às cores anotadas.

**Passa quando.** O clique no «Acelerômetro» do P3 troca a cor da bolinha DELE e de mais nada, com a borda piscando verde; o mesmo no P4. No fim, tudo volta ao que era.

**Por controle.**

* **P1** — No cabo, testemunha. Não clique em nada na linha dele.
* **P2** — No cabo, segunda testemunha. Se o P1 ficou parado e o P2 mudou junto com o P3, o clique acertou o controle errado — e não o transporte.
* **P3** — No rádio, e é o primeiro em que você clica. O «Giroscópio» da mesma linha não pode mudar junto.
* **P4** — No rádio, e é o segundo. Sem anotar as oito bolinhas antes, este teste não mede nada.

**A armadilha.** Quatro. (1) PELO RÁDIO, MOVIMENTO E VOZ DIVIDEM A MESMA FILA: com o microfone daquele controle no ar, parte dos pacotes leva voz em vez de movimento, e o Hefesto não entrega ao jogo o pacote que traz voz. O movimento continua, mais ralo — é desenho, não erro seu; o número de cada um está na aba Conexões, em «Rádio e Adaptadores». (2) Visto como «Xbox 360», o jogo não tem acelerômetro. (3) Borda laranja com a bolinha trocando é meia obediência (Modo Nativo); borda laranja com a bolinha parada é o Hefesto sem saber o estado do sensor. (4) O mapa registra os bytes MONTADOS na janela que vai ao controle virtual, e diz que ninguém isolou a inclinação chegando ao jogo pelo rádio. Não reprove porque um jogo não reagiu — reprove se o interruptor errar o alvo.

---

## mapa-movimento.giroscopio-cabo — Giroscópio — número para a interface · cabo

*Célula:* `movimento.giroscopio @ cabo`

**O que isto prova.** Prova que os dois controles do cabo mandam para a tela o quanto giram, e que parados eles NÃO dão zero — cada um tem o seu resto de fábrica.

**Onde olhar.** Aba Controles. O chip «Todos», na fita do topo, abre os quatro cards. Em cada card, coluna da direita, a moldura de CIMA é o «Giroscópio»: três linhas, X, Y e Z, cada uma com um número em graus por segundo, com uma casa (por exemplo +1.2), e uma barrinha ao lado. O «?» ao lado do rótulo diz que aquilo é leitura viva do controle. Traço no lugar do número quer dizer que a leitura ainda não chegou.

**Os passos.**

1. Abra a aba Controles.
2. Confira que as linhas do P1 e do P2 dizem USB depois do nome.
3. Deite os quatro controles numa superfície plana e tire as mãos de todos.
4. Clique no chip «Todos», na fita do topo.
5. Espere uns três segundos com os cards abertos.
6. Anote os três números do «Giroscópio» de cada um dos quatro.
7. Confira que os doze números são pequenos — nenhum passa de 2 — e que nenhum controle dá +0.0 nos três eixos ao mesmo tempo.
8. Pegue só o P1 e gire-o devagar sobre a superfície, como um volante, sem levantar.
9. Confira que um dos três números do P1 cresce bastante enquanto você gira, e que os do P2, do P3 e do P4 não crescem.
10. Gire o P1 para o outro lado.
11. Confira que o número que crescia troca de sinal.
12. Pare e deite o P1.
13. Confira que os três voltam para perto do que você anotou.
14. Pegue só o P2 e gire-o devagar para os dois lados, sobre a superfície.
15. Confira que só os números do P2 crescem, e que eles voltam ao repouso quando você para.
16. Compare o repouso do P1 com o do P2: cada um tem o seu, e eles não são iguais.

**Passa quando.** Nos dois do cabo, girar o controle faz um dos três números crescer bastante, girar para o outro lado troca o sinal dele, e parar devolve os três para perto do repouso. Parados, os números são pequenos e nenhum controle dá zero nos três eixos. Girar um nunca mexe nos números de outro. E o repouso do P1 é diferente do repouso do P2.

**Por controle.**

* **P1** — No cabo, e é o primeiro que TEM de reagir. Parado, ele tem o seu próprio número de repouso, pequeno e diferente de zero.
* **P2** — No cabo, e é o segundo. O repouso dele é DELE: se o P1 e o P2 mostrarem os mesmos três números casa por casa, a tela não está lendo dois aparelhos.
* **P3** — No rádio, testemunha. Não encoste nele. Se os números dele crescerem junto com os do P1, a leitura de um controle cai no card de outro.
* **P4** — No rádio, segunda testemunha. Se o P3 ficou parado e o P4 acompanhou o P1, o defeito é do endereço do card.

**A armadilha.** Três, e a primeira reprova um produto certo. (1) ZERO PARADO SERIA O DEFEITO: o controle não corrige o próprio resto de fábrica, e as unidades desta casa ficam entre 0,2 e 1,5 grau por segundo imóveis. Um eixo sozinho pode dar +0.0; os três ao mesmo tempo, nos quatro controles, é que merecem desconfiança. (2) O DESENHO: os números fixos do desenho são +143.2 · −412.0 · +22.8. Um DualSense parado jamais dá 412 graus por segundo: se você vir esses três, ou dois controles parados com números idênticos, não houve leitura. (3) O PRIMEIRO OLHAR MEDE A AUSÊNCIA: a leitura nasce sob demanda e morre cinco segundos depois do último pedido. O mapa registra este caminho como MONTADO; o que a sua mão faz aqui é o degrau seguinte. Não julgue esta linha pelo que um jogo faz com o giro.

---

## mapa-movimento.giroscopio-radio — Giroscópio — número para a interface · rádio

*Célula:* `movimento.giroscopio @ rádio`

**O que isto prova.** Prova que os dois controles do rádio mandam para a tela o quanto giram, com a mesma qualidade dos do cabo, e cada um no seu card.

**Onde olhar.** Aba Controles. O chip «Todos», na fita do topo, abre os quatro cards. Em cada card, coluna da direita, a moldura de CIMA é o «Giroscópio»: X, Y e Z em graus por segundo, com uma casa, e uma barrinha ao lado. Traço no lugar do número quer dizer que a leitura ainda não chegou. A linha de cada controle diz USB ou BT logo depois do nome.

**Os passos.**

1. Abra a aba Controles.
2. Confira que as linhas do P3 e do P4 dizem BT, sem nenhum cabo plugado neles.
3. Deite os quatro controles numa superfície plana e tire as mãos de todos.
4. Clique no chip «Todos», na fita do topo.
5. Espere uns três segundos com os cards abertos.
6. Anote os três números do «Giroscópio» dos quatro.
7. Confira que os cards do P3 e do P4 mostram NÚMERO, e não traço, nas três linhas.
8. Confira que o repouso dos dois do rádio é pequeno e que nenhum deles dá +0.0 nos três eixos ao mesmo tempo.
9. Pegue só o P3 e gire-o devagar sobre a superfície, como um volante, sem levantar.
10. Confira que um dos três números do P3 cresce bastante, e que os do P1, do P2 e do P4 não crescem.
11. Pare e deite o P3.
12. Confira que os três voltam para perto do repouso anotado.
13. Pegue só o P4 e gire-o devagar para os dois lados.
14. Confira que só os números do P4 crescem, e que eles voltam quando você para.
15. Compare o repouso do P3 com o do P4: cada um tem o seu, e eles não são iguais.

**Passa quando.** Nos dois do rádio, girar o controle faz um dos três números crescer bastante e parar devolve os três para perto do repouso. Os dois cards mostram NÚMERO, não traço. Parados, os números são pequenos e diferentes de zero, e o repouso do P3 é diferente do do P4. Girar um nunca mexe nos números de outro.

**Por controle.**

* **P1** — No cabo, testemunha. Não encoste nele. É ele que prova que a tela lê: se o P1 mostra números vivos e o P3 mostra traço para sempre, o buraco é do rádio.
* **P2** — No cabo, segunda testemunha. Se os números dele crescerem quando você gira o P3, alguém escreve no card errado.
* **P3** — No rádio, e é o primeiro que TEM de reagir.
* **P4** — No rádio, e é o segundo. Se algum dos quatro nascer sem leitura, anote qual.

**A armadilha.** Três. (1) ZERO PARADO SERIA O DEFEITO: o aparelho não corrige o resto de fábrica, e as unidades desta casa ficam entre 0,2 e 1,5 grau por segundo imóveis — o repouso segue o APARELHO, não o transporte. (2) O DESENHO tem os números fixos +143.2 · −412.0 · +22.8; vê-los, ou ver dois cards iguais casa a casa, é sinal de que não houve leitura. (3) O primeiro olhar mede a ausência: espere os três segundos. O mapa registra o caminho como MONTADO e uma leitura pelo rádio medida em 03/09 — repouso de 1,22 · −0,49 · −0,18 grau por segundo, dentro da faixa de fábrica. O degrau seguinte é o que a sua mão confirma aqui.

---

## mapa-movimento.giroscopio.jogo-cabo — Giroscópio — dado para o jogo (espelho ao vpad) · cabo

*Célula:* `movimento.giroscopio.jogo @ cabo`

**O que isto prova.** Prova que o interruptor «Giroscópio» de um controle do cabo mira naquele controle e só naquele sensor — sem levar junto o «Acelerômetro» nem as outras três linhas.

**Onde olhar.** Aba Controles, na LINHA de cada controle — com o card aberto ou fechado. No fim da linha, os dois interruptores «Giroscópio» e «Acelerômetro», com a bolinha verde quando ligado e cinza quando desligado; a dica do «Giroscópio» diz: «Ligado: o jogo recebe o giro deste controle.». Mais à esquerda, «DualSense», «Xbox 360» ou «Nintendo Pro» é o que o jogo vê. Quando o giro daquele controle está indo para um jogo, a linha diz também «Giroscópio: fluindo para o jogo», com o número por segundo. Depois do clique, a borda do interruptor pisca verde quando pegou inteiro e laranja quando recusou ou pegou pela metade.

**Os passos.**

1. Abra a aba Controles.
2. Clique no chip «Todos», na fita do topo.
3. Confira que as linhas do P1 e do P2 dizem «DualSense» no que o jogo vê.
4. Anote a cor das oito bolinhas: «Giroscópio» e «Acelerômetro» das quatro linhas.
5. Clique no interruptor «Giroscópio» da linha do P1.
6. Confira que a bolinha dele trocou de cor, e anote a cor em que a borda piscou.
7. Confira que o «Acelerômetro» da mesma linha e os dois interruptores do P2, do P3 e do P4 não mudaram.
8. Anote o que a moldura «Giroscópio» do card do P1 passou a mostrar: números vivos, números parados ou traço.
9. Clique de novo no «Giroscópio» do P1, para devolvê-lo.
10. Clique no interruptor «Giroscópio» da linha do P2.
11. Confira que só a bolinha dele trocou de cor, e anote a cor da borda.
12. Clique de novo no «Giroscópio» do P2, para devolvê-lo.
13. Confira que as oito bolinhas voltaram às cores anotadas.

**Passa quando.** O clique no «Giroscópio» do P1 troca a cor da bolinha DELE e de mais nada, com a borda piscando verde; o mesmo no P2. O «Acelerômetro» da mesma linha e as linhas dos outros não se mexem. No fim, os oito voltam ao que eram.

**Por controle.**

* **P1** — No cabo, e é o primeiro em que você clica. O «Acelerômetro» da mesma linha é a testemunha mais importante.
* **P2** — No cabo, e é o segundo. Antes de clicar, olhe onde estão as oito bolinhas.
* **P3** — No rádio, testemunha. Não clique em nada na linha dele.
* **P4** — No rádio, segunda testemunha. Se o P3 ficou parado e o P4 mudou junto com o P1, o clique acertou o controle errado.

**A armadilha.** O mapa registra o giro MONTADO na janela que vai ao controle virtual, e é aí que a prova para. Não reprove esta linha porque um jogo não reagiu ao movimento: o jogo só recebe o giro se a biblioteca que ELE carrega enxergar o sensor do controle virtual, e isso é outra pergunta. Quatro coisas que parecem defeito e não são: visto como «Xbox 360», o jogo NÃO TEM giroscópio; borda laranja com a bolinha trocando é meia obediência (Modo Nativo: o jogo lê o controle direto); borda laranja com a bolinha parada é o Hefesto sem saber o estado do sensor; e o que a moldura «Giroscópio» do card faz com o giro desligado não está escrito em lugar nenhum — ANOTE em vez de julgar. Não clique nos dois interruptores da mesma linha de uma vez.

---

## mapa-movimento.giroscopio.jogo-radio — Giroscópio — dado para o jogo (espelho ao vpad) · rádio

*Célula:* `movimento.giroscopio.jogo @ rádio`

**O que isto prova.** Prova que o interruptor «Giroscópio» de um controle do rádio mira naquele controle e só naquele sensor, igual aos do cabo.

**Onde olhar.** Aba Controles, na LINHA de cada controle — com o card aberto ou fechado. No fim da linha, os dois interruptores «Giroscópio» e «Acelerômetro», com a bolinha verde quando ligado e cinza quando desligado; a dica do «Giroscópio» diz: «Ligado: o jogo recebe o giro deste controle.». Mais à esquerda, «DualSense», «Xbox 360» ou «Nintendo Pro» é o que o jogo vê. Depois do clique, a borda do interruptor pisca verde quando pegou inteiro e laranja quando recusou ou pegou pela metade.

**Os passos.**

1. Abra a aba Controles.
2. Clique no chip «Todos», na fita do topo.
3. Confira que as linhas do P3 e do P4 dizem BT e «DualSense» no que o jogo vê.
4. Anote a cor das oito bolinhas: «Giroscópio» e «Acelerômetro» das quatro linhas.
5. Clique no interruptor «Giroscópio» da linha do P3.
6. Confira que a bolinha dele trocou de cor, e anote a cor em que a borda piscou.
7. Confira que o «Acelerômetro» da mesma linha e os dois interruptores do P1, do P2 e do P4 não mudaram.
8. Clique de novo no «Giroscópio» do P3, para devolvê-lo.
9. Clique no interruptor «Giroscópio» da linha do P4.
10. Confira que só a bolinha dele trocou de cor, e anote a cor da borda.
11. Clique de novo no «Giroscópio» do P4, para devolvê-lo.
12. Confira que as oito bolinhas voltaram às cores anotadas.

**Passa quando.** O clique no «Giroscópio» do P3 troca a cor da bolinha DELE e de mais nada, com a borda piscando verde; o mesmo no P4. No fim, tudo volta ao que era.

**Por controle.**

* **P1** — No cabo, testemunha. Não clique em nada na linha dele.
* **P2** — No cabo, segunda testemunha. Se o P1 ficou parado e o P2 mudou junto com o P3, o clique acertou o controle errado — e não o transporte.
* **P3** — No rádio, e é o primeiro em que você clica. O «Acelerômetro» da mesma linha não pode mudar junto.
* **P4** — No rádio, e é o segundo. Sem anotar as oito bolinhas antes, este teste não mede nada.

**A armadilha.** Quatro. (1) Se um jogo não reagir ao movimento pelo rádio, a primeira suspeita é a biblioteca que o jogo carrega, não o Hefesto: o giro chega inteiro ao controle virtual nos dois transportes, e este teste mede o interruptor, não o jogo. (2) PELO RÁDIO, MOVIMENTO E VOZ DIVIDEM A MESMA FILA: com o microfone daquele controle no ar, parte dos pacotes leva voz, e o movimento chega mais ralo — é desenho; o número de cada um está em «Rádio e Adaptadores», na aba Conexões. (3) Visto como «Xbox 360», o jogo não tem giroscópio. (4) Borda laranja com a bolinha trocando é meia obediência (Modo Nativo); com a bolinha parada, o Hefesto sem saber o estado do sensor. O mapa registra o giro MONTADO na janela que vai ao controle virtual.

---

## mapa-movimento.giroscopio.taxa-cabo — Giroscópio — taxa declarada contra entregue · cabo

*Célula:* `movimento.giroscopio.taxa @ cabo`

**O que isto prova.** Prova que o giro de um controle do cabo chega ao jogo a 250 vezes por segundo, e que esse número segue o transporte, não o número do jogador. O que o programa de jogos DECLARA ao jogo não tem tela, e este teste não o alcança.

**Onde olhar.** Aba Controles, na linha de cada controle: depois do nome e do USB ou BT, a frase «Giroscópio: fluindo para o jogo (~250 Hz)» diz quantas vezes por segundo o Hefesto entrega o giro daquele controle ao jogo AGORA. No cabo o número é perto de 250. Para quem está no rádio o número varia, e nunca passa de perto de 250, que é o teto que você escolheu em 19/08.

**Os passos.**

1. Abra a aba Controles.
2. Clique no chip «Todos», na fita do topo.
3. Anote o número da frase «Giroscópio: fluindo para o jogo» nas linhas do P1 e do P2.
4. Confira que os dois estão perto de 250.
5. Anote o número das linhas do P3 e do P4.
6. Pegue o P3, que está no rádio, e plugue um cabo nele.
7. Espere a linha dele passar a dizer USB.
8. Anote o número da frase na linha do P3 agora.
9. Desplugue o cabo do P3 e, em menos de trinta segundos, dê um toque no botão PS dele para devolvê-lo ao rádio.
10. Confira que a linha dele voltou a dizer BT e que o número dele voltou a variar.

**Passa quando.** As linhas do P1 e do P2 dizem perto de 250, e ficam assim. Quando o P3 passa para o cabo, o número dele vai para perto de 250 — o que prova que ele segue o transporte, e não o número do jogador. No fim, o P3 volta ao rádio e o número volta com ele.

**Por controle.**

* **P1** — No cabo, e a frase dele diz perto de 250.
* **P2** — No cabo, e a frase dele diz o mesmo que a do P1. Dois números muito diferentes para dois controles no mesmo transporte é o defeito.
* **P3** — No rádio, testemunha até o fim, quando vira o sujeito: é ele que você pluga no cabo para ver o número mudar.
* **P4** — No rádio, a testemunha que fica. Não encoste nele: o número dele segue o do rádio do começo ao fim.

**A armadilha.** Três. (1) Este número é o que o Hefesto ENTREGA ao jogo, depois do teto de 250; a metade DECLARADA — quantas vezes por segundo o programa de jogos diz ao jogo que o giro chega — nunca foi medida e não aparece em tela nenhuma. É ela que segura esta linha em PARCIAL. (2) A frase só aparece quando o giro daquele controle está indo para um jogo: se alguma linha não tiver a frase, anote, e não conte como zero. (3) O RELÓGIO DO REPLUGUE: entre desplugar o cabo e tocar o PS têm de passar menos de trinta segundos, senão o P3 volta com outro número de jogador — é a regra do produto funcionando; refaça mais rápido.

---

## mapa-movimento.giroscopio.taxa-radio — Giroscópio — taxa declarada contra entregue · rádio

*Célula:* `movimento.giroscopio.taxa @ rádio`

**O que isto prova.** Prova quantas vezes por segundo um controle do rádio manda movimento de verdade — é uma faixa, não um ponto —, e que o que chega ao jogo nunca passa do teto de 250. O que o programa de jogos DECLARA ao jogo não tem tela, e este teste não o alcança.

**Onde olhar.** Dois lugares. Na aba Conexões, a seção «Rádio e Adaptadores»: dentro de cada adaptador (o ▶ mostra os aparelhos dele), a linha de cada controle do rádio traz um número em Hz ao lado do ícone de sinal — a dica diz «Movimento por segundo». É quanto movimento aquele controle manda AGORA; ele fica laranja abaixo de 125. Na aba Controles, a frase «Giroscópio: fluindo para o jogo» na linha de cada controle, com o número por segundo entre parênteses, diz quanto disso o Hefesto entrega ao jogo.

**Os passos.**

1. Abra a aba Conexões.
2. Clique em «Rádio e Adaptadores» para abrir a seção.
3. Clique no ▶ de cada adaptador até achar as linhas do P3 e do P4.
4. Anote o número em Hz das linhas do P3 e do P4.
5. Espere trinta segundos, com os controles parados.
6. Anote de novo os dois números.
7. Abra a aba Controles.
8. Clique no chip «Todos», na fita do topo.
9. Anote o número da frase «Giroscópio: fluindo para o jogo» nas linhas do P3 e do P4.
10. Confira que as linhas do P1 e do P2 dizem perto de 250.

**Passa quando.** Os números do P3 e do P4 em «Rádio e Adaptadores» são reais e mudam entre uma leitura e outra — dois aparelhos do mesmo rádio podem diferir bastante —, e nenhum chega perto dos 1000 que o programa de jogos declara para o rádio. O número que vai ao jogo, na aba Controles, nunca passa de perto de 250. Os do cabo ficam em perto de 250.

**Por controle.**

* **P1** — No cabo, testemunha: a frase dele fica em perto de 250 do começo ao fim.
* **P2** — No cabo, segunda testemunha, com a mesma leitura do P1.
* **P3** — No rádio, e é um dos dois desta célula: os dois números dele, em Conexões e em Controles.
* **P4** — No rádio, e é o outro. Se o P3 e o P4 derem números muito diferentes entre si, anote os dois: já se mediu isso nesta casa, e é do aparelho.

**A armadilha.** Três, e a primeira é um número que já foi derrubado nesta casa. (1) OS 1000 POR SEGUNDO SÃO DECLARAÇÃO, NÃO ENTREGA: o programa de jogos os declara para o rádio, e o aparelho nunca os entregou em medição nenhuma. Quem os escrever como taxa do aparelho reintroduz um fato que a medição derrubou. (2) Com o microfone daquele controle no ar, parte da fila do rádio leva voz, e o número de movimento cai por desenho — a mesma linha mostra a voz ao lado. (3) A metade DECLARADA não tem tela nem medição: é ela que segura esta linha em PARCIAL. O laranja abaixo de 125 é um corte do desenho, não uma medição.

---

## mapa-movimento.imu.calibracao-cabo — Calibração de fábrica da IMU · cabo

*Célula:* `movimento.imu.calibracao @ cabo`

**O que isto prova.** Prova que cada controle do cabo usa a calibração de fábrica DELE, e não a de outro — o repouso de cada um é próprio e se repete.

**Onde olhar.** Dois lugares. A aba Controles: o chip «Todos», na fita do topo, abre os quatro cards; em cada um, na coluna da direita, a moldura «Giroscópio» (X, Y e Z em graus por segundo, uma casa) e a moldura «Acelerômetro» (X, Y e Z em g, duas casas). Deitado e parado, o «Acelerômetro» dá um eixo perto de 1 e os outros perto de zero, e o «Giroscópio» dá três números pequenos que NÃO são zero juntos: é o resto de fábrica daquela unidade. E o botão «Calibrar sensores de movimento», no canto de «Dispositivos conectados», que abre uma página do tamanho da janela com o mesmo título, três passos numerados («Deixe os controles parados», «Não toque neles», «Pronto»), um cartão por controle conectado — com USB ou BT, um selo («Parado», «Medindo…» ou «Calibrado») e os números vivos do giroscópio e do acelerômetro —, e os botões «Começar» e «Fechar».

**Os passos.**

1. Abra a aba Controles.
2. Confira que as linhas do P1 e do P2 dizem USB.
3. Deite os quatro controles numa superfície plana, virados para cima, e tire as mãos de todos.
4. Clique no chip «Todos», na fita do topo.
5. Espere uns três segundos com os cards abertos.
6. Anote os SEIS números do P1: os três do «Giroscópio» e os três do «Acelerômetro».
7. Anote os seis números do P2, do P3 e do P4, do mesmo jeito.
8. Confira que o «Acelerômetro» dos quatro dá um eixo perto de 1 e os outros perto de zero.
9. Compare os seis números do P1 com os seis do P2: não podem ser iguais casa por casa.
10. Levante o P1, gire-o na mão e deite-o de novo na MESMA posição.
11. Espere uns três segundos.
12. Confira que os seis números do P1 voltaram para perto dos que você anotou.
13. Faça o mesmo com o P2: levante, gire, deite na mesma posição, espere e compare.
14. Clique no botão «Calibrar sensores de movimento».
15. Confira que a página lista os quatro controles, cada um com USB ou BT, e que os números de cada cartão batem com os do card dele.
16. Clique em «Fechar».

**Passa quando.** Nos dois do cabo os seis números de repouso são PRÓPRIOS: o acelerômetro fecha na gravidade e o giroscópio dá números pequenos que não são zero juntos. Os seis do P1 não são iguais aos seis do P2. Levantar e deitar de novo devolve os mesmos seis — o repouso de cada aparelho se repete, porque a calibração é dele. E a página de calibrar mostra os quatro, com os mesmos números.

**Por controle.**

* **P1** — No cabo, e é o primeiro cujo repouso TEM de ser próprio e voltar depois de mexer.
* **P2** — No cabo, e é o segundo. O par P1–P2 decide o teste: seis números iguais casa por casa querem dizer a calibração de UM usada nos dois — o defeito que o mapa avisa que faz os outros derivarem.
* **P3** — No rádio, testemunha. Não encoste nele. Os seis dele são diferentes dos do P1 e dos do P2.
* **P4** — No rádio, segunda testemunha. Quatro aparelhos parados dão quatro repousos diferentes.

**A armadilha.** Três. (1) A PÁGINA DE CALIBRAR MOSTRA, MAS NÃO CALIBRA: os números dos cartões são leitura viva desde 11/09, mas «Começar» não zera aparelho nenhum — o Hefesto ainda não tem como fazer isso —, e os três selos trocam quando você clica nos três passos numerados, e só. Não conte nada do selo como resposta do produto. (2) ZERO PARADO SERIA O DEFEITO: as unidades desta casa ficam entre 0,2 e 1,5 grau por segundo imóveis. (3) O DESENHO da aba Controles tem números fixos (+143.2 · −412.0 · +22.8 no giroscópio, +0.105 · +0.976 · +0.170 no acelerômetro): vê-los é sinal de que não houve leitura. O mapa registra que o produto LÊ a calibração de fábrica uma vez e a guarda; «imutável por unidade» continua sem medição direta, e é a consequência dela que a sua mão mede aqui.

---

## mapa-movimento.imu.calibracao-radio — Calibração de fábrica da IMU · rádio

*Célula:* `movimento.imu.calibracao @ rádio`

**O que isto prova.** Prova que cada controle do rádio usa a calibração de fábrica DELE, e que esse repouso viaja com o aparelho quando ele troca de transporte.

**Onde olhar.** Dois lugares. A aba Controles: o chip «Todos» abre os quatro cards; em cada um, a moldura «Giroscópio» (graus por segundo, uma casa) e a moldura «Acelerômetro» (g, duas casas). Deitado e parado, o acelerômetro dá um eixo perto de 1, e o giroscópio dá três números pequenos que não são zero juntos — o resto de fábrica daquela unidade. E o botão «Calibrar sensores de movimento», que abre a página do tamanho da janela com um cartão por controle conectado, com USB ou BT e os números vivos, e os botões «Começar» e «Fechar». Nenhum campo da tela diz se uma calibração chegou embaralhada pelo rádio.

**Os passos.**

1. Abra a aba Controles.
2. Confira que as linhas do P3 e do P4 dizem BT, sem nenhum cabo plugado neles.
3. Deite os quatro controles numa superfície plana, virados para cima, e tire as mãos de todos.
4. Clique no chip «Todos», na fita do topo.
5. Espere uns três segundos com os cards abertos.
6. Anote os SEIS números do P3: os três do «Giroscópio» e os três do «Acelerômetro».
7. Anote os seis números do P4, do P1 e do P2.
8. Confira que o «Acelerômetro» do P3 e do P4 dá um eixo perto de 1 e os outros perto de zero.
9. Compare os seis do P3 com os seis do P4, do P1 e do P2: nenhum par igual casa por casa.
10. Plugue um cabo no P3, sem tirá-lo do lugar.
11. Espere a linha do P3 passar a dizer USB e mais uns três segundos.
12. Confira que os seis números do P3 são praticamente os mesmos que você anotou pelo rádio.
13. Desplugue o cabo do P3 e, em menos de trinta segundos, dê um toque no botão PS dele para devolvê-lo ao rádio.
14. Clique no botão «Calibrar sensores de movimento».
15. Confira que a página lista os quatro controles, cada um com USB ou BT, com os números vivos.
16. Clique em «Fechar».

**Passa quando.** Nos dois do rádio os seis números de repouso são PRÓPRIOS e distintos entre um controle e outro. E o teste que decide: quando o P3 passa do rádio para o cabo, os seis números dele continuam praticamente os mesmos. O repouso segue o APARELHO, não o transporte — foi assim que se mediu em 15/08, com no máximo 0,06 grau por segundo de diferença entre os dois transportes, contra cinco vezes de diferença entre uma unidade e outra.

**Por controle.**

* **P1** — No cabo, testemunha. Não encoste nele. Os seis dele servem de comparação.
* **P2** — No cabo, segunda testemunha. Se os seis do P2 mudarem quando você pluga o P3, alguma coisa troca a calibração de um pela do outro.
* **P3** — No rádio, e é o sujeito deste teste: anote pelo rádio, plugue, leia de novo, devolva ao rádio.
* **P4** — No rádio, e não troca de transporte. Ele é a prova de que o rádio, sozinho, entrega calibração boa: se o P3 só ficar certo no cabo e o P4 der números estranhos o tempo todo, o buraco é do rádio.

**A armadilha.** Três. (1) SÓ PELO RÁDIO a calibração passa por uma conferência antes de ser aceita, e quando ela falha o produto NÃO avisa: cai numa calibração genérica. O sintoma é um controle do rádio com repouso de livro, ou igual ao de outro aparelho — por isso o teste compara os quatro entre si. (2) A PÁGINA DE CALIBRAR MOSTRA, MAS NÃO CALIBRA: «Começar» não zera nada, e os selos trocam quando você clica nos passos numerados. (3) ZERO PARADO SERIA O DEFEITO; e os números fixos do desenho (+143.2 · −412.0 · +22.8) querem dizer que não houve leitura. O mapa registra que o produto LÊ a calibração de fábrica uma vez; «imutável por unidade» continua sem medição direta.

---

## mapa-movimento.imu.perda-cabo — Perda de amostras de IMU · cabo

*Célula:* `movimento.imu.perda @ cabo`

**O que isto prova.** Prova que, no cabo, a leitura de movimento não engasga: os números andam sem travar enquanto você move o controle sem parar.

**Onde olhar.** Aba Controles. O chip «Todos», na fita do topo, abre os quatro cards; em cada card, na coluna da direita, as molduras «Giroscópio» e «Acelerômetro», com X, Y e Z e uma barrinha ao lado de cada número. A barrinha denuncia engasgo melhor que o número: ela anda contínua enquanto o controle se move e para de vez quando a leitura para. Na linha de cada controle, a frase «Giroscópio: fluindo para o jogo (~250 Hz)» diz quanto giro está indo ao jogo. Uma contagem de perdas não existe em tela nenhuma — no cabo o produto nem a conta.

**Os passos.**

1. Abra a aba Controles.
2. Confira que as linhas do P1 e do P2 dizem USB.
3. Clique no chip «Todos», na fita do topo.
4. Espere uns três segundos com os cards abertos.
5. Confira que os cards do P1 e do P2 mostram número, e não traço, nas seis linhas de sensor.
6. Pegue o P1 e gire-o devagar e SEM PARAR, de um lado para o outro, por uns vinte segundos.
7. Confira, o tempo todo, que os números e as barrinhas do «Giroscópio» do P1 andam sem travar num valor e sem virar traço.
8. Anote se houve algum instante em que os números congelaram com a sua mão ainda mexendo.
9. Deite o P1 e faça o mesmo com o P2, por outros vinte segundos.
10. Anote o mesmo para o P2.
11. Confira que, durante as duas voltas, os cards do P3 e do P4 continuaram mostrando número.

**Passa quando.** Nos dois do cabo, os números e as barrinhas andam sem interrupção durante os vinte segundos: não congelam com a sua mão mexendo e não viram traço. Se algum travar enquanto você move, isso é o achado — anote a hora, porque nenhuma contagem confirma.

**Por controle.**

* **P1** — No cabo, e é o primeiro. Medido em 15/08: ZERO pacotes perdidos no cabo em mais de quinze mil seguidos — travar aqui é notícia.
* **P2** — No cabo, e é o segundo. Medido na mesma noite, também zero perdido.
* **P3** — No rádio, testemunha. Não encoste nele. O card dele não pode virar traço enquanto você mexe nos do cabo.
* **P4** — No rádio, segunda testemunha. Se o P3 aguentou e o P4 caiu, o problema é do card dele.

**A armadilha.** Três. (1) TELA SEM MÁ NOTÍCIA NÃO É PROVA DE QUE NADA SE PERDEU: no cabo um pacote que chega errado é descartado em silêncio, sem conta nenhuma. (2) A TELA ATUALIZA DEZ VEZES POR SEGUNDO e o aparelho entrega 250: engasgo de poucos pacotes é invisível nessa cadência; o que este teste enxerga é travamento de meio segundo para cima. (3) JÁ HOUVE PERDA REAL NO CABO, medida em 19/08 — 36% das amostras jogadas fora por um desencontro de menos de 1% entre a fonte e o teto —, e foi curada. Se voltar, aparece assim: números que andam mas «pulam», sem travar de vez. O mapa registra uma cura medida e ainda não aplicada — um contador que viaja no próprio pacote e daria ao cabo a conta que ele nunca teve.

---

## mapa-movimento.imu.perda-radio — Perda de amostras de IMU · rádio

*Célula:* `movimento.imu.perda @ rádio`

**O que isto prova.** Prova que, no rádio, o movimento que chega cai quando o sinal piora — e volta quando ele melhora —, enquanto os do cabo continuam lisos no mesmo instante.

**Onde olhar.** Na aba Conexões, a seção «Rádio e Adaptadores»: dentro de cada adaptador (o ▶ mostra os aparelhos dele), a linha de cada controle do rádio traz um número em Hz ao lado do ícone de sinal — a dica diz «Movimento por segundo». É quanto movimento o computador está recebendo daquele controle AGORA: quando o rádio come pacotes, o número cai, e abaixo de 125 ele fica laranja. Na aba Controles, a frase «Giroscópio: fluindo para o jogo (~250 Hz)» na linha de cada controle do cabo serve de testemunha. Uma contagem de perdas não existe em tela nenhuma.

**Os passos.**

1. Abra a aba Conexões.
2. Clique em «Rádio e Adaptadores» para abrir a seção.
3. Clique no ▶ de cada adaptador até achar as linhas do P3 e do P4.
4. Pegue o P3 e fique ao lado do computador.
5. Anote o número em Hz da linha do P3.
6. Afaste-se devagar do computador com o P3 na mão, até onde você ainda consiga ler a tela.
7. Anote o número do P3 lá longe, e se ele ficou laranja.
8. Ponha o seu corpo entre o P3 e o computador, parada.
9. Anote o número do P3 de novo.
10. Volte para perto do computador.
11. Confira que o número do P3 voltou para perto do que você anotou no começo.
12. Faça a mesma caminhada com o P4, anotando o número perto, longe e com o corpo no caminho.
13. Abra a aba Controles.
14. Confira que as linhas do P1 e do P2 continuam dizendo perto de 250.

**Passa quando.** Perto do computador, os dois do rádio mostram um número estável. Longe, ou com o seu corpo no caminho, é honesto que o número caia — e fique laranja —; voltando para perto, ele se recupera. E os do cabo não mudam em momento nenhum: é essa diferença que o teste procura.

**Por controle.**

* **P1** — No cabo, testemunha. Não encoste nele. Se a frase dele cair junto com o número do P3, o engasgo não é do rádio — é do Hefesto ou da máquina.
* **P2** — No cabo, segunda testemunha. Dois do cabo lisos e dois do rádio caindo é a assinatura que este teste quer.
* **P3** — No rádio, e é o primeiro a se afastar. É nele que a queda tem de aparecer.
* **P4** — No rádio, e é o segundo. Se o P3 caiu e o P4 não, ou o contrário, anote os dois: unidades do mesmo rádio já entregaram números quase duas vezes diferentes entre si.

**A armadilha.** Quatro. (1) CAIR NO RÁDIO É RESPOSTA VÁLIDA, e não erro seu: em 15/08 se mediu 2.242 pacotes sumindo num único salto, com o computador recebendo 27 por segundo enquanto o relógio do próprio controle marcava 398 — o controle mandou e o caminho comeu. Anote o que viu; não fique tentando até dar liso. (2) O número é quanto CHEGA, não quanto se perdeu: a contagem de perdas continua sem tela. O laranja abaixo de 125 é um corte do desenho, não uma medição. (3) Com o microfone daquele controle no ar, parte da fila leva voz, e o número de movimento é menor por desenho — a mesma linha mostra a voz ao lado; compare sempre o mesmo controle com ele mesmo. (4) NÃO CONFUNDA QUEDA DE SINAL COM DESCONEXÃO: se a linha do controle sumir do adaptador, ou o chip dele sumir da fita do topo, ele se desligou — isso é outro teste.

---

# plataforma

---

## mapa-plataforma.adocao-cabo — Adoção pelo Hefesto (grab, vpad, perfil) · cabo

*Célula:* `plataforma.adocao @ cabo`

**O que isto prova.** Prova que, pelo cabo, o Hefesto toma o controle para si e entrega ao jogo um controle montado por ele — e que a escolha de como o jogo enxerga cada aparelho vale só para o aparelho escolhido, a partir do clique.

**Onde olhar.** Na aba Jogar. A linha «Status», com as posições «Ligado» e «Desligado». O quadro «Modo», com os chips «Sony DualSense», «Xbox», «Steam Input» e «Navegação». E o quadro «O controle é visto como:», com um cartão por controle — «Sony • Player N», o nome da cor do plástico e USB ou BT — e, dentro de cada cartão, três chips: «DualSense», «Xbox 360» e «Nintendo Pro». O chip aceso é o que o jogo vê daquele controle. A mesma escolha aparece, só para ler, em dois lugares: na aba Conexões, no quadro «Gestão de Controles», a linha de cada controle traz «Vê como» seguido do nome; e na aba Controles, no alto do cartão de cada controle, logo depois de USB ou BT. Quem fecha o teste é o JOGO: o desenho dos botões na tela dele.

**Os passos.**

1. Confira na fita do topo que os chips do P1 e do P2 terminam em USB e os do P3 e do P4 em BT.
* Abra a aba Jogar.
2. Confira que a linha «Status» está em «Ligado» e que, no quadro «Modo», o chip aceso é «Sony DualSense» ou «Xbox».
3. Leia os quatro cartões do quadro «O controle é visto como:» e anote qual chip está aceso em cada um.
4. Abra o jogo com os quatro jogadores dentro da partida.
5. Anote como o jogo desenha os botões de cada um dos quatro jogadores.
6. Volte para a janela do Hefesto e clique no chip «Xbox 360» do cartão do P1.
7. Confira que só o cartão do P1 trocou de chip aceso, e que os outros três continuam no que você anotou.
8. Volte ao jogo, sem clicar em mais nada, e olhe o desenho dos botões do jogador que você move com o P1: tem de ter virado o do Xbox (Y B A X).
9. Olhe os jogadores do P2, do P3 e do P4 e confira que continuam como estavam.
10. Volte ao Hefesto e clique no chip «Xbox 360» do cartão do P2.
11. Volte ao jogo e confira que agora são dois jogadores desenhados como Xbox, e que são os do P1 e do P2.
12. Abra a aba Conexões, clique no título «Gestão de Controles» e leia o «Vê como» das quatro linhas: tem de contar a mesma história dos cartões.
13. Volte à aba Jogar e clique no chip «DualSense» nos cartões do P1 e do P2, para desfazer.

**Passa quando.** A escolha feita no cartão do P1 muda o desenho dos botões do jogador do P1 dentro do jogo, e de mais ninguém; a do P2 muda o do P2, e de mais ninguém — as duas só com o clique no chip. Os cartões do P3 e do P4 não trocam de chip sozinhos, e os jogadores deles continuam desenhados como estavam. O «Vê como» da aba Conexões diz o mesmo que os cartões da aba Jogar.

**Por controle.**

* **P1** — USB, e é ESTE que muda primeiro. Um clique em «Xbox 360» no cartão dele, e o jogador dele troca de desenho no jogo sem mais nada. No fim, devolva «DualSense».
* **P2** — USB, e é o segundo a mudar. Só mexa nele depois de o P1 já ter trocado — assim você vê os dois estados no mesmo jogo. No fim, devolva «DualSense».
* **P3** — BT, e é TESTEMUNHA. Não toque no cartão dele. Se o chip dele trocar sozinho quando você mexe no do P1, a escolha vazou para todos em vez de ficar no aparelho, e é esse o defeito que este teste caça.
* **P4** — BT, e é a segunda testemunha. Mesma conferência. Se o P3 ficou parado e o P4 mudou, o problema não é do rádio: é a escolha indo para o controle errado.

**A armadilha.** Três. (1) A troca vale no clique: o Hefesto monta de novo, na hora, o controle que o jogo enxerga — não há «Aplicar» nem «Reconectar controles» a apertar. O preço é do jogo, que recebe um controle novo no lugar do antigo: alguns seguem jogando, outros tratam como jogador novo, e há os que só acertam o desenho reabrindo. Se o desenho não mudar, feche e abra o jogo antes de anotar reprovação, e anote qual jogo fez isso. (2) Com o «Status» em «Desligado», ou o Modo em «Navegação», não existe controle montado pelo Hefesto: o chip acende e a escolha fica guardada no aparelho, mas o jogo só muda quando o Hefesto voltar a entregar o controle — é por isso que o passo 2 confere os dois. (3) O chip «Nintendo Pro» funciona desde 07/09: o jogo passa a ver um controle da Nintendo, e o desenho que aparece depende de o jogo conhecer esse controle. E a ordem dos jogadores dentro do jogo pode não ser a do Hefesto: siga pelo controle na sua mão, não pelo número que o jogo escreve. Sobre o degrau: esta linha do mapa não tem degrau escrito, de propósito — tomar o controle e montar um novo é ato do computador, não conversa com o aparelho. O que se mede é o efeito no jogo, e é o que os passos pedem.

---

## mapa-plataforma.adocao-radio — Adoção pelo Hefesto (grab, vpad, perfil) · rádio

*Célula:* `plataforma.adocao @ rádio`

**O que isto prova.** Prova que, pelo rádio, o Hefesto toma o controle para si igual ao cabo — a escolha de como o jogo enxerga o aparelho vale nele, e volta com ele quando ele cai e religa, porque ela é do aparelho e não do lugar.

**Onde olhar.** Na aba Jogar. A linha «Status», com «Ligado» e «Desligado»; o quadro «Modo»; e o quadro «O controle é visto como:», com um cartão por controle — «Sony • Player N», o nome da cor do plástico e USB ou BT — e os três chips dentro de cada um: «DualSense», «Xbox 360» e «Nintendo Pro». Na aba Conexões, no quadro «Gestão de Controles», a linha de cada controle repete a escolha em «Vê como», só para leitura. E quem fecha é o JOGO: o desenho dos botões de cada jogador.

**Os passos.**

1. Confira na fita do topo que os chips do P3 e do P4 terminam em BT e os do P1 e do P2 em USB.
2. Anote o nome da cor do plástico do P3 e o do P4, que estão nos chips da fita — é por eles que você vai seguir o P3 quando ele sair.
3. Abra a aba Jogar.
4. Confira que a linha «Status» está em «Ligado» e que, no quadro «Modo», o chip aceso é «Sony DualSense» ou «Xbox».
5. Leia os quatro cartões do quadro «O controle é visto como:» e anote qual chip está aceso em cada um.
6. Abra o jogo com os quatro jogadores dentro da partida e anote como ele desenha os botões de cada um.
7. Volte ao Hefesto e clique no chip «Xbox 360» do cartão do P3.
8. Confira que só o cartão do P3 trocou de chip aceso.
9. Volte ao jogo e confira que só o jogador do P3 mudou de desenho.
10. Feche o jogo agora.
11. Segure o botão PS do P3 até todas as luzes dele apagarem, e solte.
12. Olhe o quadro «O controle é visto como:»: o cartão «Player 3» passa a mostrar o plástico do P4, com o chip «DualSense» aceso — a escolha acompanha o aparelho, não o lugar.
13. Dê um toque curto no botão PS do P3 para religá-lo e espere o chip dele voltar à fita do topo.
14. Leia o cartão com o plástico do P3: ele tem de voltar a ser «Player 3», com o chip «Xbox 360» aceso de novo, e o do P4 volta a ser «Player 4» com «DualSense».
15. Abra o jogo de novo e confira que o jogador do P3 volta desenhado como Xbox e que os outros três estão como no começo.
16. Clique no chip «DualSense» do cartão do P3, para desfazer.

**Passa quando.** A escolha feita no cartão do P3 muda o desenho dos botões do jogador do P3 no jogo, e de mais ninguém. Enquanto o P3 está desligado, o cartão que passa a ocupar o lugar dele mostra a escolha do P4, e não a do P3. E depois de o P3 cair e voltar pelo rádio, o cartão dele volta com o mesmo número e com a mesma escolha de antes — a escolha é do aparelho, não da sessão nem do lugar.

**Por controle.**

* **P1** — USB, e é TESTEMUNHA. Não toque no cartão dele. Se ele trocar de chip quando você mexe no P3, a escolha vazou para todos.
* **P2** — USB, e é a segunda testemunha. Mesma conferência.
* **P3** — BT, e é ESTE. Ponha «Xbox 360», veja o jogador dele trocar no jogo — e depois desligue-o e religue-o pelo PS para conferir se a escolha volta com ele.
* **P4** — BT, e é o vizinho que prova a outra metade: enquanto o P3 está fora ele aparece no lugar «Player 3» com a escolha DELE, «DualSense». Se ele aparecer ali com «Xbox 360», a escolha ficou presa ao lugar em vez de ao aparelho, e esse é o achado.

**A armadilha.** Quatro. (1) Enquanto um controle está fora, os que vêm depois dele descem um número na tela e nas lâmpadas — o P4 passa a aparecer como P3 — e voltam ao número deles quando o que saiu volta. Isso é o produto (medido em 12/08), não defeito; por isso os passos seguem o P3 pelo plástico. (2) Não há prazo para a volta: o número e a escolha voltam com o aparelho enquanto o serviço estiver de pé, demore o que demorar. (3) A troca de máscara vale no clique, e o jogo recebe um controle novo no lugar do antigo; é por isso que o jogo fica fechado enquanto o P3 cai e volta — um jogo aberto pode tratar a volta como jogador novo, e aí o teste passa a medir o jogo. (4) Com o «Status» em «Desligado», ou o Modo em «Navegação», não há controle montado pelo Hefesto, e nada do que você escolher chega ao jogo até ele voltar a entregar. E o degrau: esta linha do mapa não tem degrau escrito, de propósito — tomar o controle e montar um controle novo é ato do computador, e o mapa registra que pelo rádio isso funciona sem nenhuma trava de transporte: é essa igualdade que os passos medem.

---

## mapa-plataforma.crc32-cabo — CRC-32 no envelope (integridade de report) · cabo

*Célula:* `plataforma.crc32 @ cabo`

**O que isto prova.** Prova que, pelo cabo, o que o Hefesto manda e o que ele lê chegam inteiros mesmo sem nenhum selo de conferência no caminho.

**Onde olhar.** O selo de conferência não tem campo em aba nenhuma — pelo cabo ele simplesmente não existe. O que se lê é o EFEITO, em três lugares. No aparelho: a barra de luz (as duas tiras acesas dos lados do touchpad) e o tremor na sua mão. Na tela: a linha «Cor» da coluna de cada controle, na aba Iluminação — onze quadradinhos de cor, com o código da cor escrito embaixo deles; o botão «Testar» da linha «Testar agora», na aba Vibração; e, na aba Controles, o cartão de cada controle, onde cada analógico tem um pontinho que anda com a sua mão, o desenho do botão acende quando você o aperta e a bateria mostra um número.

**Os passos.**

1. Confira na fita do topo que os chips do P1 e do P2 terminam em USB e os do P3 e do P4 em BT.
2. Abra a aba Iluminação.
3. Na linha «Cor» da coluna do P1, clique num quadradinho cuja cor nenhum dos outros três esteja usando, e olhe a barra de luz dele no aparelho.
4. Faça o mesmo nas colunas do P2, do P3 e do P4, uma cor diferente em cada.
5. Olhe os quatro controles juntos: quatro barras acesas, quatro cores.
6. Abra a aba Vibração.
7. Segure o P1 na mão e clique em «Testar» na coluna dele; sinta o tremor.
8. Repita o «Testar» nos outros três, um de cada vez, com o controle na mão — cada «Testar» encerra o anterior —, e termine no «Parar» da coluna do P4.
9. Abra a aba Controles e clique no chip «Todos» da fita do topo, para abrir os quatro cartões.
10. Mexa o analógico esquerdo do P1 em círculos, devagar, e olhe o pontinho dentro do cartão dele acompanhar.
11. Aperte, um a um, o quadrado, o triângulo, o círculo e o xis do P1, olhando o desenho acender a cada aperto.
12. Repita os dois passos acima no P2.
13. Repita no P3 e no P4.
14. Anote se em algum momento o pontinho pulou para um canto sem a sua mão ir lá, se um botão acendeu sozinho, ou se um número de bateria deu um salto absurdo.
15. Volte à aba Iluminação e, em cada coluna, clique no quadradinho da cor do número daquele controle — o primeiro na coluna do P1, o segundo na do P2, o terceiro na do P3 e o quarto na do P4 —, para desfazer.

**Passa quando.** Os quatro obedecem à cor e ao tremor, e o desenho vivo dos quatro segue a sua mão sem pulos e sem acender nada sozinho. Pelo cabo, o P1 e o P2 fazem tudo isso sem nenhuma conferência de integridade no caminho — é este o ponto da linha: não há selo, e mesmo assim nada chega quebrado.

**Por controle.**

* **P1** — USB, e é um dos dois que provam o lado SEM selo. Cor, tremor e o desenho vivo seguindo a mão.
* **P2** — USB, o segundo. Mesmos gestos. Um pulo que apareça no P1 e no P2 e nunca no P3 e no P4 é justamente a assinatura que este teste procura.
* **P3** — BT, e é comparação. Mesmos gestos. Aqui cada quadro que chega é conferido por selo, e o que não confere é jogado fora antes de virar tinta na tela.
* **P4** — BT, a segunda comparação. Mesmos gestos.

**A armadilha.** «Nada aconteceu» pelo cabo nunca é o selo — pelo cabo não existe selo. Se o P1 não obedecer, procure outra coisa: o serviço parado, a coluna vazia, o jogo escrevendo por cima. E o contrário também engana: um pulo no desenho vivo do P1 não prova que um byte chegou torto; pode ser a sua mão. O que faz o achado é o padrão — pulo nos dois do cabo e em nenhum dos dois do rádio. Na cor, escolha sempre um tom livre: um tom que já é de outro controle não fica no que você clicou, e a tela diz de quem ele era. Sobre até onde a prova chegou: esta linha do mapa não tem degrau escrito. O que está medido é o ENVELOPE — em 06 de setembro os quatro controles foram lidos com o serviço parado, ninguém disputando o aparelho, e pelo cabo nenhum corte de quadro fecha com um selo: os quatro últimos bytes mudam a cada quadro, são carga e não soma de conferência. O degrau que faltava é o seu olho, e é o que os passos acima pedem.

---

## mapa-plataforma.crc32-radio — CRC-32 no envelope (integridade de report) · rádio

*Célula:* `plataforma.crc32 @ rádio`

**O que isto prova.** Prova que, pelo rádio, o que o Hefesto manda vai assinado direito — porque um pedido com a assinatura errada o controle joga fora em silêncio, sem uma palavra.

**Onde olhar.** No aparelho: a barra de luz do P3 e a do P4 (as duas tiras acesas dos lados do touchpad). Na tela: a linha «Cor» da coluna de cada controle, na aba Iluminação — onze quadradinhos de cor, com o código da cor escrito embaixo; o chip de cada controle na fita do topo, que traz o nome da cor do plástico e a borda pintada nessa cor — essa cor é uma resposta que veio do aparelho e, pelo rádio, veio assinada; e o cartão do controle na aba Controles, onde o pontinho do analógico anda com a sua mão. O selo em si não tem campo em tela nenhuma.

**Os passos.**

1. Confira na fita do topo que os chips do P3 e do P4 terminam em BT e os do P1 e do P2 em USB.
2. Abra a aba Iluminação.
3. Na linha «Cor» da coluna do P1, clique num quadradinho cuja cor nenhum outro controle esteja usando, e confirme a cor na barra de luz dele — este é o controle de comparação, pelo cabo.
4. Clique num quadradinho livre de cor bem diferente na linha «Cor» da coluna do P3.
5. Olhe a barra de luz do P3 no aparelho e confirme que ela acendeu nessa cor.
6. Clique numa terceira cor livre na mesma coluna do P3 e confirme que a barra dele trocou.
7. Repita os dois passos acima na coluna do P4.
8. Abra a aba Controles.
9. Leia o chip do P3 na fita do topo: ele tem de trazer o nome de uma cor de plástico e a borda pintada.
10. Pegue o P3 na mão e compare o plástico com o nome que está no chip.
11. Repita a leitura do chip com o P4.
12. Clique no chip «Todos» da fita para abrir os quatro cartões.
13. Mexa o analógico esquerdo do P3 em círculos, devagar, e olhe o pontinho do cartão dele acompanhar sem pular.
14. Repita no P4.
15. Volte à aba Iluminação e clique, em cada coluna em que você mexeu, no quadradinho da cor do número daquele controle — o primeiro para o P1, o terceiro para o P3, o quarto para o P4 —, para desfazer.
16. Anote qualquer coisa que a tela tenha dito que aplicou e que o plástico não tenha feito.

**Passa quando.** As barras de luz do P3 e do P4 acendem na cor escolhida e trocam quando você troca. Os chips deles trazem o nome da cor do plástico e a borda pintada, e o nome bate com o aparelho na sua mão. O pontinho do analógico segue a mão sem pulos. Nada disso chegaria com a assinatura errada — pelo rádio o controle descarta calado.

**Por controle.**

* **P1** — USB, e é a comparação obrigatória. Pinte uma cor NELE primeiro: se ele também não obedecer, o problema não é do rádio e o resto do teste não mede nada.
* **P2** — USB. Não toque nele. Serve de segunda comparação se o P1 der resultado estranho.
* **P3** — BT, e é ESTE que prova a ida (a cor que sai) e a volta (a cor do plástico que chega). Todos os gestos de cor são nele primeiro.
* **P4** — BT, e é o segundo. Confira nele as mesmas duas coisas. Se o P3 responder e o P4 não, o achado é daquele aparelho, e não do rádio.

**A armadilha.** O silêncio é a resposta padrão do erro aqui, e é isso que engana. Pelo rádio um pedido mal assinado é DESCARTADO pelo controle sem erro nenhum: o código embaixo dos quadradinhos pode mudar e o plástico não. Foi assim que «a cor nunca funcionou pelo rádio» viveu meses nesta casa. Por isso o P1, no cabo, entra nos passos: se ele obedecer e os do rádio não, o achado é do rádio; se nenhum obedecer, é outra coisa. Segunda: escolha sempre um tom livre — um tom que já é de outro controle não fica no que você clicou, e a tela diz de quem ele era; isso não é o rádio falhando. Terceira: o nome da cor do plástico pelo rádio está provado em DUAS unidades desta bancada, não nas quatro — se um terceiro controle vier sem cor, o achado é a assinatura daquele aparelho, e a tela devolve «não sei» em vez de inventar uma cor, que é o comportamento certo. E o degrau: esta linha do mapa não tem degrau escrito de propósito. O que foi medido em 06 de setembro foi a VOLTA — duzentos quadros de cada controle do rádio, todos conferindo, com a régua mordida de propósito (virando um bit de três bytes diferentes) para ver a conferência reprovar. A IDA é o que os seus dedos medem aqui.

---

## mapa-plataforma.declarado_sem_resposta-cabo — O que o descritor declara e o firmware NÃO entrega (EPIPE na leitura) · cabo

*Célula:* `plataforma.declarado_sem_resposta @ cabo`

**O que isto prova.** Prova que o buraco do cabo — dez coisas que o controle promete e recusa quando lhe perguntam — não chega à tela: tudo o que o Hefesto lê do aparelho pelo fio aparece preenchido.

**Onde olhar.** Na fita do topo, o chip de cada controle: o número, o nome da cor do plástico e a borda pintada com essa cor. Na aba Controles, dentro do quadro «Dispositivos conectados», o cartão de cada controle: no alto, a frase «Giroscópio: fluindo para o jogo», o selo do «Microfone» (ATIVO ou DESLIGADO) e a «Bateria» com número; dentro, o bloco «Giroscópio» com X, Y e Z. No alto do quadro, o botão «Calibrar sensores de movimento», que abre a página da calibração no lugar da aba. E na aba Iluminação, a linha «Controle», com o desenho de cada controle pintado na cor do plástico. A recusa em si — o «não» que o controle devolve a dez perguntas quando está no fio — não aparece em tela nenhuma, porque o produto nunca faz essas dez perguntas.

**Os passos.**

1. Confira na fita do topo que os chips do P1 e do P2 terminam em USB e os do P3 e do P4 em BT.
2. Abra a aba Controles.
3. Leia o chip do P1 na fita do topo: ele tem de trazer um nome de cor de plástico e a borda pintada.
4. Pegue o P1 na mão e compare o plástico com o nome do chip.
5. Repita a leitura do chip com o P2, com o P3 e com o P4.
6. Clique no chip «Todos» da fita, para abrir os quatro cartões.
7. No cartão do P1, leia a frase «Giroscópio: fluindo para o jogo» no alto; gire o P1 na mão e confira que os números X, Y e Z do bloco «Giroscópio» andam.
8. Leia a «Bateria» e o selo do «Microfone» do P1 e anote os dois.
9. Repita os dois passos acima no P2, no P3 e no P4.
10. Clique em «Calibrar sensores de movimento», no alto do quadro «Dispositivos conectados».
11. Pouse os quatro controles parados numa superfície plana e clique em «Começar».
12. Espere os quatro cartões da página dizerem «Calibrado» — são 5 segundos, e encostar num controle recomeça a conta dele.
13. Clique em «← Voltar» e confira que a frase «Giroscópio: fluindo para o jogo» continua nos quatro cartões.
14. Abra a aba Iluminação e confira, na linha «Controle», que os quatro desenhos estão pintados na cor do plástico, e não cinza.
15. Anote qualquer campo, de qualquer um dos quatro, que tenha vindo vazio, cinza ou com um travessão.

**Passa quando.** Os quatro trazem nome de cor e borda pintada, o desenho pintado, o giroscópio fluindo e andando com a mão, a bateria com número e o microfone com selo, e os quatro chegam a «Calibrado». Nenhum campo do P1 e do P2 — os dois do cabo — vem mais vazio que o do P3 e o do P4.

**Por controle.**

* **P1** — USB, e é um dos dois que provam este lado. Todos os campos preenchidos: cor com nome e borda, desenho pintado, giroscópio fluindo, bateria com número, microfone com selo.
* **P2** — USB, o segundo. Mesma conferência. Se um campo faltar no P1 e no P2 e estiver cheio no P3 e no P4, o achado é do cabo — anote qual campo.
* **P3** — BT, e é comparação. Pelo rádio não há buraco nenhum: tudo o que o controle promete, ele entrega. Os campos dele são a régua contra a qual você lê os do cabo.
* **P4** — BT, a segunda comparação. Mesma conferência.

**A armadilha.** A cor de fábrica é lida por uma pergunta que o cabo ENTREGA — e a pergunta vizinha, de número quase igual, é uma das dez que ele RECUSA. Então, se a cor faltar num controle do cabo, não conclua «é o buraco do cabo»: não é. As dez recusas são de LEITURA, o produto não faz nenhuma delas em lugar nenhum, e a que ele usa para a cor é uma das que respondem. Segunda: o travessão num número quer dizer que a leitura ainda não chegou — não é zero, e não conta como passa. E o degrau: esta linha parou em SAIU NO FIO — o byte saiu e o controle respondeu, com um «não» de um lado e com dado do outro, mas ninguém viu nada acender, girar nem soar. Os passos acima são exatamente o degrau que falta, e é o seu olho que o dá.

---

## mapa-plataforma.declarado_sem_resposta-radio — O que o descritor declara e o firmware NÃO entrega (EPIPE na leitura) · rádio

*Célula:* `plataforma.declarado_sem_resposta @ rádio`

**O que isto prova.** Prova que, pelo rádio, não falta nada: tudo o que o controle promete, ele entrega — e o que ele entrega vazio é resposta, não recusa.

**Onde olhar.** Na fita do topo, o chip de cada controle, com o número, o nome da cor do plástico e a borda pintada. Na aba Controles, dentro do quadro «Dispositivos conectados», o cartão de cada controle: no alto, a frase «Giroscópio: fluindo para o jogo», o selo do «Microfone» — ATIVO, DESLIGADO ou um travessão — e a «Bateria» com número; dentro, o bloco «Giroscópio» com X, Y e Z. O travessão quer dizer «não consegui ler» e não é nenhum dos dois. E na aba Iluminação, a linha «Controle», com o desenho de cada controle pintado na cor do plástico.

**Os passos.**

1. Confira na fita do topo que os chips do P3 e do P4 terminam em BT e os do P1 e do P2 em USB.
2. Abra a aba Controles.
3. Leia os quatro chips da fita do topo e anote, de cada um, se veio o nome da cor e se a borda está pintada.
4. Pegue o P3 na mão e compare o plástico com o nome do chip dele.
5. Faça o mesmo com o P4.
6. Clique no chip «Todos» da fita, para abrir os quatro cartões.
7. Leia, no cartão do P3, a frase do giroscópio, os números do bloco «Giroscópio» enquanto você gira o P3, a «Bateria» e o selo do «Microfone» — e anote os quatro.
8. Repita a leitura no cartão do P4.
9. Repita a leitura nos cartões do P1 e do P2, que estão no cabo.
10. Abra a aba Iluminação e anote, na linha «Controle», quais dos quatro desenhos estão pintados e quais estão cinza.
11. Compare campo a campo: qualquer campo cheio nos do cabo e vazio nos do rádio é o achado.
12. Se algum campo do P3 tiver vindo vazio, encaixe um cabo nele, sem desligá-lo.
13. Leia o mesmo campo de novo e anote se ele encheu.
14. Puxe o cabo do P3 e confirme que o chip dele volta a terminar em BT; se ele não voltar sozinho, dê um toque curto no PS dele.

**Passa quando.** Os dois do rádio trazem exatamente os mesmos campos preenchidos que os dois do cabo: nome de cor e borda, desenho pintado, giroscópio fluindo, bateria com número e microfone com selo — ATIVO ou DESLIGADO, nunca travessão. Nada falta do lado do rádio, e é isso que a linha afirma.

**Por controle.**

* **P1** — USB, e é comparação. Todos os campos anotados antes de você julgar o rádio: sem eles não há com o que comparar.
* **P2** — USB, segunda comparação.
* **P3** — BT, e é ESTE que prova o lado. Se um campo dele vier vazio, leve o mesmo aparelho para o cabo e olhe de novo: encheu no cabo é achado do rádio; ficou vazio nos dois é achado do aparelho.
* **P4** — BT, e é o segundo. A mesma leitura, e ela importa: dois aparelhos que respondem valem muito mais que um.

**A armadilha.** Voltar vazio e recusar são duas respostas diferentes, e o mapa guarda as duas. Pelo rádio há perguntas que respondem com tudo zero, e isso conta como resposta — na tela vira um campo sem valor, não um erro, e não é o buraco de que esta linha fala: buraco, pelo rádio, não existe. Segunda: a leitura da cor do plástico pelo rádio está provada em DUAS unidades desta bancada, não nas quatro; se um terceiro aparelho vier sem cor, o achado é dele e a tela mostra «não sei» em vez de inventar, que é o comportamento certo. Terceira: encaixar e puxar o cabo derruba o P3 por um instante, e enquanto ele está fora o P4 aparece como P3 — ele volta ao 4 quando o P3 volta; siga-os pelo plástico. E o degrau: esta linha parou em SAIU NO FIO — o byte saiu e o controle respondeu com dado, mas ninguém viu nada acender, girar nem soar. Os passos acima são o degrau seguinte, e quem o dá é o seu olho.

---

## mapa-plataforma.descritor_hid-cabo — Descritor HID — o que cada transporte DECLARA (cabo 289 B x rádio 320 B) · cabo

*Célula:* `plataforma.descritor_hid @ cabo`

**O que isto prova.** Prova que o que o controle oferece muda com o BRAÇO em que ele está, e não com o aparelho — e que pelo cabo ele entrega uma coisa que o rádio não tem: a placa de som do próprio controle.

**Onde olhar.** Na aba Conexões, no quadro «Gestão de Controles», que abre clicando no título: uma linha por controle — «Sony • Player N • <o nome da cor do plástico> • USB» ou «• BT». Na mesma linha vem o campo «Microfone», e é ele que muda com o transporte: pelo cabo ele diz «Ligado, pelo cabo • Placa do controle»; pelo rádio, «Ligado, pelo rádio • Pela ponte». Ao lado do título, a contagem, no formato «4 controles • 2 no cabo • 2 no rádio». O tamanho do que cada transporte declara não aparece em tela nenhuma, porque não há campo para ele.

**Os passos.**

1. Confira na fita do topo que os chips do P1 e do P2 terminam em USB e os do P3 e do P4 em BT.
2. Confira que o controle do P1 já foi pareado por rádio nesta máquina alguma vez — sem isso ele não volta pelo PS e o teste não roda.
3. Abra a aba Conexões.
4. Clique no título «Gestão de Controles» para abrir o quadro.
5. Leia as quatro linhas e anote, de cada uma, o nome da cor do plástico, se termina em USB ou em BT, e o que diz o campo «Microfone».
6. Leia a contagem ao lado do título e anote.
7. Puxe o cabo de dentro do controle do P1.
8. Dê um toque no botão PS desse mesmo aparelho.
9. Ache a linha com o plástico do P1: ela tem de terminar em BT agora, com o mesmo nome de cor.
10. Leia o campo «Microfone» dessa linha: ele tem de ter virado «pelo rádio • Pela ponte».
11. Encaixe o cabo de volta no mesmo aparelho.
12. Leia a linha mais uma vez: ela volta a terminar em USB, e o «Microfone» volta para «pelo cabo • Placa do controle».
13. Confira que as linhas do P2, do P3 e do P4 terminam como no começo — mesmo plástico, mesmo USB ou BT, mesmo «Microfone».
14. Leia a contagem de novo e compare com a que você anotou.

**Passa quando.** O mesmo aparelho, atravessando os dois braços, continua sendo o mesmo na tela: mesma cor de plástico e, no fim, o mesmo número de jogador. A única coisa que muda é o que depende do transporte — USB ou BT no fim da linha, e o caminho do microfone. Pelo cabo o som vem da placa do próprio controle; pelo rádio, pela ponte do Hefesto. No fim, as linhas dos outros três estão como começaram.

**Por controle.**

* **P1** — É ESTE que atravessa: sai do cabo, volta pelo rádio com um toque no PS, e depois volta ao cabo. O que tem de mudar na linha dele são duas coisas e só duas: USB ou BT, e o caminho do microfone.
* **P2** — USB, e não sai de lá. É a comparação parada: a linha dele tem de dizer «pelo cabo • Placa do controle» do começo ao fim.
* **P3** — BT, testemunha. Não toque nele. A linha dele não pode sumir do quadro enquanto o P1 atravessa.
* **P4** — BT, segunda testemunha. Mesma conferência.

**A armadilha.** Três. (1) No instante em que o cabo sai e o rádio ainda não subiu, o P1 está fora, e os outros três descem um número — o P2 aparece como Player 1, e assim por diante — e voltam ao número deles quando o P1 volta. Isso é o produto, não defeito: siga cada um pelo nome do plástico, e confira os números só no fim. Não há prazo para a volta: o P1 recupera o número dele pelo rádio, demore o que demorar. (2) Não saia procurando na tela «o que o cabo declara»: não há campo, e você vai procurar para sempre. A única diferença de transporte que esta tela mostra é o caminho do microfone. (3) Declarar não é entregar, e essa distinção é de outra linha: o cabo anuncia MAIS coisas que o rádio e entrega menos da metade delas. Ver isso aqui é impossível, e não é defeito desta tela. E o degrau: esta linha do mapa não tem degrau escrito. O que está medido é o que os dois braços DECLARAM, lido do sistema em 15 de agosto com os quatro aparelhos passando pelos dois braços — e o achado foi que a lista segue o BRAÇO, não a unidade: o mesmo aparelho anuncia uma coisa no fio e outra no ar.

---

## mapa-plataforma.descritor_hid-radio — Descritor HID — o que cada transporte DECLARA (cabo 289 B x rádio 320 B) · rádio

*Célula:* `plataforma.descritor_hid @ rádio`

**O que isto prova.** Prova que o rádio oferece um caminho próprio, que só existe enquanto o aparelho está no ar — e que ele some assim que o mesmo aparelho entra no fio.

**Onde olhar.** Na aba Conexões, em dois quadros que abrem pelo título, um de cada vez. No «Gestão de Controles»: uma linha por controle, terminando em USB ou BT, e o campo «Microfone», que pelo rádio diz «pelo rádio • Pela ponte» e pelo cabo diz «pelo cabo • Placa do controle». No «Rádio e Adaptadores»: ao lado do título, a contagem no formato «2 controles · 3 adaptadores», que conta só os controles do rádio; e um bloco por adaptador Bluetooth, com o nome da entrada em que ele está (por exemplo «Entrada 4.1.4») e um ▶ que abre a lista do que está nele — cada controle do rádio aparece ali com o nome «Player N» e a cor do plástico. Um controle no cabo nunca aparece nessa seção. O tamanho do caminho que cada transporte anuncia não aparece em tela nenhuma.

**Os passos.**

1. Confira na fita do topo que os chips do P3 e do P4 terminam em BT e os do P1 e do P2 em USB.
2. Abra a aba Conexões.
3. Clique no título «Rádio e Adaptadores» e anote a contagem ao lado dele.
4. Clique no ▶ de cada adaptador e anote em qual deles estão o P3 e o P4.
5. Clique no título «Gestão de Controles» e anote o campo «Microfone» das quatro linhas.
6. Encaixe um cabo no controle do P3, sem desligá-lo.
7. Leia de novo a linha dele: ela tem de terminar em USB, e o «Microfone» tem de virar «pelo cabo • Placa do controle».
8. Clique no título «Rádio e Adaptadores»: a contagem tem de ter caído um, e o P3 tem de ter saído da lista do adaptador dele.
9. Confira que o P4 continua na lista do adaptador dele.
10. Puxe o cabo do P3; se ele não voltar ao rádio sozinho, dê um toque curto no PS dele.
11. Em «Gestão de Controles», confira que a linha dele volta a terminar em BT, com o «Microfone» em «pelo rádio • Pela ponte».
12. Em «Rádio e Adaptadores», confira que ele voltou à lista de um adaptador e que a contagem voltou.
13. Repita todos os passos acima com o P4.
14. Confira, no fim, que o P1 e o P2 nunca apareceram em «Rádio e Adaptadores».

**Passa quando.** O mesmo aparelho continua sendo o mesmo na tela — cor de plástico e, no fim, número de jogador —, e o que aparece e some junto com o rádio é o caminho de rádio dele: a presença na lista de um adaptador e o microfone pela ponte. Quando ele entra no fio, sai do adaptador e o microfone passa a vir da placa do próprio controle. Os dois do cabo não se mexem.

**Por controle.**

* **P1** — USB, testemunha. Não toque nele. A linha dele tem de dizer «pelo cabo • Placa do controle» do começo ao fim, e ele nunca pode aparecer num adaptador de «Rádio e Adaptadores».
* **P2** — USB, segunda testemunha. Mesma conferência.
* **P3** — BT, e é ESTE que atravessa primeiro. Entra no fio, sai do fio. O que tem de sumir e voltar com ele é a presença no adaptador e o microfone pela ponte.
* **P4** — BT, e é o segundo a atravessar. Enquanto o P3 está no fio, é ele quem prova que o adaptador continua vivo com um só: ele não pode sumir da lista por causa do vizinho.

**A armadilha.** Três, e as três são de leitura. (1) Encaixar o cabo num controle que está no rádio não o tira do rádio no mesmo instante, e por um momento a tela pode mostrar as duas coisas; espere a linha assentar antes de anotar. (2) Na troca de braço o P3 some por um instante, e enquanto isso o P4 aparece como Player 3 — ele volta ao 4 quando o P3 volta; siga-os pelo plástico. (3) Os números em Hz que aparecem ao lado de cada controle em «Rádio e Adaptadores» são leitura viva do que chega agora, e mudam sozinhos; o que este teste lê ali é a PRESENÇA e a AUSÊNCIA do controle, não o valor. E o degrau: esta linha do mapa não tem degrau escrito. O que está medido é o que cada braço declara, lido em 15 de agosto com os quatro aparelhos passando pelos dois lados: o que só o rádio anuncia continuou sendo só do rádio, com os aparelhos trocados de braço. A lista segue o braço, não a unidade.

---

## mapa-plataforma.diagnostico_morte_radio-cabo — Diagnóstico da morte por rádio (doctor) · cabo

*Célula:* `plataforma.diagnostico_morte_radio @ cabo`

**O que isto prova.** Prova que o produto não inventa diagnóstico de rádio para um controle que está no cabo — e que, quando um controle do cabo cai, o que você vê é a queda dita com todas as letras.

**Onde olhar.** No canto de cima, à direita, a contagem, no formato «● 2 USB · 2 BT». A fita do topo, com um chip por controle — «P1 • <nome da cor do plástico> • USB». Na aba Conexões, o quadro «Gestão de Controles», que abre pelo título: um lugar sem controle passa a dizer «Player N • Desconectado». E na aba Sistema, a faixa «O exame de hoje», com a conta ao lado dela (por exemplo «8 linhas · nenhum aviso») e uma linha por achado, cada uma com um selo — o exame é da máquina: som, Steam Input, regras de permissão.

**Os passos.**

1. Confira que os quatro estão ligados — os chips do P1 e do P2 terminando em USB, os do P3 e do P4 em BT — e anote o nome da cor do plástico de cada um.
2. Abra a aba Sistema e leia a conta ao lado de «O exame de hoje»: anote quantas linhas e quantos avisos.
3. Leia as linhas do exame, uma a uma, e anote o que cada uma diz.
4. Puxe o cabo de dentro do controle do P1.
5. Leia a contagem no alto: ela tem de passar a «● 1 USB · 2 BT».
6. Confira na fita que o chip com o plástico do P1 saiu e que ficaram três chips, com os outros três plásticos.
7. Abra a aba Conexões, clique no título «Gestão de Controles» e confira que a última linha passou a dizer «Player 4 • Desconectado».
8. Volte à aba Sistema e leia o exame de novo.
9. Confira que nenhuma linha NOVA nasceu falando de rádio, de Bluetooth ou de controle sumido.
10. Encaixe o cabo de volta no P1.
11. Confira que a contagem volta a «● 2 USB · 2 BT» e que o chip com o plástico do P1 volta a ser o P1, com os outros três de volta aos números do começo.
12. Repita os passos 4 a 11 com o P2.

**Passa quando.** Puxar o cabo de um controle aparece como o que é — a queda de um controle do CABO: a contagem perde um USB, o chip dele sai da fita, e um lugar passa a dizer «Desconectado». O exame da aba Sistema não ganha linha nova por causa disso, e não diz uma palavra sobre rádio. Com o cabo de volta, os quatro terminam com os números do começo.

**Por controle.**

* **P1** — USB, e é o primeiro a cair. Puxe o cabo dele, leia as três telas, e devolva o cabo antes de passar ao P2.
* **P2** — USB, e é o segundo a cair. Um de cada vez: dois fora ao mesmo tempo esconde quem fez o quê.
* **P3** — BT, testemunha. Não toque nele. O chip dele não pode sumir da fita. Enquanto o P1 está fora ele desce um número e volta ao 3 quando o P1 volta — isso é o produto.
* **P4** — BT, segunda testemunha. Mesma conferência. É ele quem aparece como P3 durante a ausência, e o lugar «Player 4» fica «Desconectado» por isso.

**A armadilha.** Esta célula do mapa é uma AUSÊNCIA declarada: o diagnóstico de que ela fala é o da morte por RÁDIO, e pelo cabo não há o que diagnosticar por esse caminho. Mas a razão desse «não» está registrada como NÃO MEDIDA — ninguém foi ver se existe uma morte de cabo que mereça diagnóstico próprio. Então, se durante este teste um controle do cabo sumir sem você puxar nada, isso é achado e vale anotar com a hora. Segunda: o lugar que fica «Desconectado» é o ÚLTIMO, e não o do P1 — enquanto um controle está fora, os que vêm depois dele descem um número e voltam quando ele volta, e é por isso que os passos seguem cada um pelo plástico. Terceira: não confunda o exame da aba Sistema com diagnóstico de rádio — ele é da máquina e não fala de rádio, e não falar não é falha dele. Uma linha que já existia e conta controles (a do áudio, por exemplo) pode mudar o número quando o cabo sai; isso é a conta. O que reprovaria aqui é uma linha NOVA aparecendo, por causa de um cabo puxado, a falar de rádio.

---

## mapa-plataforma.diagnostico_morte_radio-radio — Diagnóstico da morte por rádio (doctor) · rádio

*Célula:* `plataforma.diagnostico_morte_radio @ rádio`

**O que isto prova.** Prova o que a tela diz quando um controle do rádio sai — e o que ela NÃO diz quando ele morre de verdade, que é o achado desta linha.

**Onde olhar.** No canto de cima, à direita, a contagem («● 2 USB · 2 BT»). A fita do topo, com um chip por controle. Na aba Conexões, o quadro «Gestão de Controles», onde um lugar sem controle diz «Player N • Desconectado», e a seção «Rádio e Adaptadores», com a contagem ao lado do título («2 controles · 3 adaptadores») e, em cada adaptador, um ▶ que abre a lista dos controles que estão nele. Na aba Jogar, o botão «Reconectar controles», embaixo dos cartões: desde 22/09 ele também chama de volta pelo rádio os controles que o Bluetooth do computador conhece e que o Hefesto não está vendo, e diz numa frase o que fez. O diagnóstico da morte por rádio — o aviso de que o controle está pareado, o computador o dá por conectado e mesmo assim ele não existe para o Hefesto — não nasce sozinho em aba nenhuma.

**Os passos.**

1. Confira na fita do topo que os chips do P3 e do P4 terminam em BT e os do P1 e do P2 em USB, e anote o nome da cor do plástico de cada um.
2. Abra a aba Conexões, clique no título «Rádio e Adaptadores», anote a contagem e, abrindo o ▶ de cada adaptador, em qual deles está cada controle do rádio.
3. Abra a aba Sistema e leia a conta ao lado de «O exame de hoje»: anote quantas linhas e quantos avisos.
4. Segure o botão PS do P3 até todas as luzes dele apagarem, e solte.
5. Leia a contagem no alto: ela tem de passar a «● 2 USB · 1 BT».
6. Confira na fita que o chip com o plástico do P3 saiu e que o plástico do P4 aparece agora como P3.
7. Volte à aba Conexões e confira que a contagem de «Rádio e Adaptadores» caiu um, que o P3 saiu da lista do adaptador dele e que o P4 continua na do seu.
8. Volte à aba Sistema e leia o exame de novo: anote se alguma linha nova nasceu.
9. Abra a aba Jogar e clique em «Reconectar controles», com o P3 ainda desligado.
10. Espere a frase que aparece depois do clique — ela pode levar alguns segundos por controle pareado que esteja desligado — e anote-a palavra por palavra.
11. Dê um toque curto no botão PS do P3 para religá-lo.
12. Confira que ele volta com o plástico dele como P3, que o P4 volta a ser P4, e que a contagem volta a «● 2 USB · 2 BT».
13. Repita os passos 4 a 12 com o P4.

**Passa quando.** Desligar um do rádio aparece como três coisas ao mesmo tempo: a contagem perde um BT, o chip dele sai da fita, e ele sai da lista do adaptador em «Rádio e Adaptadores». Nenhum dos outros cai, e no fim os quatro voltam aos números do começo. O exame da aba Sistema continua com as mesmas linhas — ele não fala de rádio, e é honesto que não fale.

**Por controle.**

* **P1** — USB, testemunha. Não toque nele. Ele nunca aparece em «Rádio e Adaptadores», e não pode cair.
* **P2** — USB, segunda testemunha. Mesma conferência.
* **P3** — BT, e é ESTE que sai primeiro. Segure o PS até todas as luzes apagarem — nem antes nem depois — e depois religue-o com um toque curto.
* **P4** — BT, e é o vizinho de rádio de quem caiu. Enquanto o P3 está fora, ele aparece como P3 e tem de continuar na lista do adaptador dele. Depois é a vez dele de sair.

**A armadilha.** Este teste NÃO provoca a morte de que a linha fala, e é preciso dizer. A morte por rádio é outra coisa: o controle está pareado, o computador o dá por conectado, e mesmo assim ele não existe para o Hefesto — nasce órfão. Isso não se provoca com o botão PS, e nenhuma aba avisa sozinha quando acontece. O que a tela tem hoje é a CURA: «Reconectar controles» derruba esse elo morto e pede que você aperte PS. Então, se um dia um controle estiver aceso e pareado e não aparecer no Hefesto, ISSO é a morte por rádio: anote a hora e clique em «Reconectar controles». Segunda, e é o que o passo 10 caça: com o P3 desligado de propósito, a frase do «Reconectar controles» pode dizer que derrubou um elo morto — e não havia elo morto nenhum, o controle só estava desligado. Anote a frase inteira: ela conta todo DualSense pareado neste computador que esteja desligado, não só o P3. Terceira: soltar o botão PS cedo demais não desliga o controle, e um aperto solto no PS abre a Steam; se ela abrir, feche-a e refaça o passo. Quarta: não conte o exame da aba Sistema como diagnóstico de rádio; ele é da máquina.

---

## mapa-plataforma.distinguir_clone-cabo — Distinguir o genuíno do clone · cabo

*Célula:* `plataforma.distinguir_clone @ cabo`

**O que isto prova.** Prova que o Hefesto arranca de cada controle do cabo uma resposta que o clone medido nesta casa não sabe dar: o nome da cor do plástico de fábrica.

**Onde olhar.** Na fita do topo, o chip de cada controle — «P1 • <nome da cor do plástico> • USB» — com a borda pintada nessa cor. Na aba Conexões, no quadro «Gestão de Controles» (abre pelo título), a mesma leitura aparece como uma barra fina de cor na aresta esquerda da linha de cada controle; o «?» do quadro diz que a borda e o desenho usam a cor lida do aparelho e que, sem leitura, ficam neutros. Na aba Iluminação, a linha «Controle» desenha cada controle na cor do plástico. Não existe em tela nenhuma um campo que diga «genuíno» ou «clone», porque o produto não faz verificação de autenticidade.

**Os passos.**

1. Confira na fita do topo que os chips do P1 e do P2 terminam em USB e os do P3 e do P4 em BT.
* Abra a aba Controles.
2. Leia o chip do P1 na fita do topo e anote o nome da cor.
3. Pegue o P1 na mão e compare o plástico com o nome anotado.
4. Repita a leitura e a comparação com o P2.
5. Repita com o P3 e com o P4.
6. Abra a aba Conexões e clique no título «Gestão de Controles».
7. Confira, nas quatro linhas, que a barra da aresta esquerda está pintada e não neutra.
8. Abra a aba Iluminação e confira que os quatro desenhos da linha «Controle» estão pintados na cor do plástico, e não cinza.
9. Anote qual controle, se algum, ficou sem nome de cor, com a barra neutra ou com o desenho cinza.
10. Puxe o cabo do P1, dê um toque no PS para trazê-lo pelo rádio e leia o chip com o plástico dele de novo: o nome da cor tem de continuar lá, agora terminando em BT.
11. Encaixe o cabo de volta e confirme que a cor continua lá, terminando em USB.

**Passa quando.** Os dois do cabo trazem nome de cor e borda pintada, e o nome bate com o plástico na sua mão. Um controle que não devolve essa resposta é o achado — e o produto o mostra como cor não lida, com a barra neutra e o desenho cinza, em vez de inventar uma cor.

**Por controle.**

* **P1** — USB, e é ESTE que responde primeiro. Nome da cor no chip, borda pintada, e o plástico na sua mão batendo com os dois. É também ele que atravessa para o rádio no fim, para você ver a mesma resposta chegando pelos dois braços.
* **P2** — USB, o segundo. Mesma conferência. Dois aparelhos respondendo valem muito mais que um.
* **P3** — BT, e é comparação. Pelo rádio essa resposta chega assinada, e o próprio sistema recusa uma assinatura errada — quem passou por ali já acertou duas contas antes de a cor aparecer.
* **P4** — BT, a segunda comparação. Se um dos dois do rádio vier sem cor e o outro vier com, o achado é do aparelho, não do transporte.

**A armadilha.** Isto não é anti-clone, e dizer que é seria mentira. O Hefesto aceita qualquer aparelho que se apresente com o número de fábrica certo: não há desafio, não há senha, não há como um programa desta casa conferir a assinatura da Sony. O que este teste mede é uma resposta A MAIS, que o clone medido nesta casa não dá — o firmware dele responde três perguntas e mais nada, e a da cor é a quarta. Um clone melhor copia a resposta e passa igual. Segunda: a cor sumir NÃO é prova de clone; pode ser um aparelho cuja assinatura de cor esta casa ainda não conhece, e nesse caso a tela devolve «não sei», que é o certo. Terceira: na travessia do passo 10 o P1 some por um instante e os outros três descem um número até ele voltar; siga-os pelo plástico. Quarta: nenhum degrau foi escrito nesta linha do mapa. Ela foi preenchida lendo o firmware de um clone real e o que os aparelhos declaram, sem uma única escrita nos seus controles — o que você fizer aqui é a primeira vez que um par de mãos a mede.

---

## mapa-plataforma.distinguir_clone-radio — Distinguir o genuíno do clone · rádio

*Célula:* `plataforma.distinguir_clone @ rádio`

**O que isto prova.** Prova que, pelo rádio, o controle tem de acertar mais contas antes de aparecer na tela — e que a resposta que denuncia o clone medido chega assim mesmo.

**Onde olhar.** Na fita do topo, o chip do P3 e o do P4 — «P3 • <nome da cor do plástico> • BT» — com a borda pintada nessa cor. Na aba Conexões, no quadro «Gestão de Controles» (abre pelo título), a barra fina de cor na aresta esquerda da linha de cada controle; barra neutra quer dizer que a cor não foi lida, e o «?» do quadro diz isso. Na aba Iluminação, a linha «Controle», com o desenho de cada controle na cor do plástico — cinza quando a cor não foi lida. Não existe em tela nenhuma um campo que diga «genuíno» ou «clone».

**Os passos.**

1. Confira na fita do topo que os chips do P3 e do P4 terminam em BT e os do P1 e do P2 em USB.
2. Abra a aba Controles.
3. Leia o chip do P3 na fita do topo e anote o nome da cor.
4. Pegue o P3 na mão e compare o plástico com o nome anotado.
5. Repita a leitura e a comparação com o P4.
6. Leia os chips do P1 e do P2, que estão no cabo, e anote as cores deles também.
7. Abra a aba Conexões, clique no título «Gestão de Controles» e confira, nas quatro linhas, quais barras estão pintadas e quais estão neutras.
8. Abra a aba Iluminação e confira quais desenhos da linha «Controle» estão pintados e quais estão cinza.
9. Se o P3 tiver vindo sem cor, encaixe um cabo nele, sem desligá-lo, e leia o chip dele de novo.
10. Puxe o cabo do P3 e confira o que acontece com a cor quando ele volta ao rádio; se ele não voltar sozinho, dê um toque curto no PS dele.
11. Repita os dois passos acima com o P4, se ele também tiver vindo sem cor.
12. Anote, no fim, quantos dos quatro devolveram a cor e por qual braço.

**Passa quando.** Os dois do rádio trazem nome de cor e borda pintada, e o nome bate com o plástico na sua mão. Pelo rádio essa resposta só chega assinada, e uma assinatura errada é recusada antes de virar tinta — então cor na tela, pelo rádio, quer dizer que o aparelho acertou duas contas além do conteúdo.

**Por controle.**

* **P1** — USB, comparação. Anote a cor dele antes de julgar o rádio: se nem no cabo aparecer cor, o problema não é do rádio.
* **P2** — USB, segunda comparação.
* **P3** — BT, e é ESTE que responde primeiro. Se ele vier sem cor, leve o mesmo aparelho ao cabo e olhe de novo — apareceu no cabo e não no rádio, o achado é do rádio; não apareceu nos dois, o achado é do aparelho.
* **P4** — BT, e é ele que fecha a amostra: a leitura da cor pelo rádio está provada em DUAS unidades desta bancada, não nas quatro. Se ele responder, a conta fecha; se recusar, anote o modelo dele, porque o achado é a assinatura daquele aparelho.

**A armadilha.** A barra que o rádio impõe é mais alta e continua copiável: o selo tem semente conhecida, e qualquer clone que leia a mesma tabela o acerta. Nada aqui prova autenticidade — prova só que o aparelho deu uma resposta a mais que o clone medido não dá. Segunda, e é a que faz julgar errado: a cor pelo rádio está provada em duas unidades, então um terceiro controle sem cor NÃO é veredito sobre o transporte; é achado daquele aparelho, e a tela devolve «não sei» em vez de inventar, que é o certo. Antes de concluir qualquer coisa, faça o mesmo aparelho atravessar para o cabo e olhe de novo — e, na travessia, ele some por um instante e o vizinho desce um número até ele voltar. Terceira: nenhum degrau foi escrito nesta linha do mapa — ela nasceu de leitura de firmware de clone e do que os aparelhos declaram, sem uma escrita sequer nos seus controles.

---

## mapa-plataforma.escada_de_output-cabo — Escada de reports de OUTPUT por rádio — 0x31 a 0x39, de 64 em 64 bytes · cabo

*Célula:* `plataforma.escada_de_output @ cabo`

**O que isto prova.** Prova que, pelo cabo, tudo o que o Hefesto manda cabe num caminho de saída só, curto — e que a pergunta «e se coubesse mais?» nunca foi feita a nenhum controle no fio.

**Onde olhar.** No aparelho: a barra de luz (as duas tiras acesas dos lados do touchpad), o tremor na sua mão e a resistência do L2 e do R2. Na tela: a linha «Cor» da coluna de cada controle, na aba Iluminação; o botão «Testar» da linha «Testar agora», na aba Vibração; e, na aba Gatilhos, o campo «Modo» de cada coluna — o do bloco de cima é o do L2, o do bloco de baixo é o do R2. O tamanho do caminho de saída não aparece em tela nenhuma, e nenhum botão desta interface pede um caminho maior pelo cabo.

**Os passos.**

1. Confira na fita do topo que os chips do P1 e do P2 terminam em USB e os do P3 e do P4 em BT.
2. Abra a aba Iluminação e, na linha «Cor» da coluna do P1, clique num quadradinho cuja cor nenhum outro controle esteja usando.
3. Olhe a barra de luz do P1 no aparelho e confirme a cor.
4. Abra a aba Vibração, segure o P1 na mão e clique em «Testar» na coluna dele.
5. Sinta o tremor nos dois punhos e clique em «Parar» na coluna do P1.
6. Abra a aba Gatilhos e anote o «Modo» que está escolhido no L2 e no R2 da coluna do P1.
7. No bloco do L2, escolha «Rígido» no campo «Modo» da coluna do P1.
8. Aperte o L2 do P1 e sinta se ele travou duro do começo ao fim do curso.
9. Escolha «Rígido» também no «Modo» do bloco do R2 da coluna do P1 e aperte o R2.
10. Repita os passos 2 a 9 no P2.
11. Volte à aba Iluminação e confira que a barra de luz do P1 continua na cor que você pôs.
12. Na aba Gatilhos, devolva ao L2 e ao R2 do P1 e do P2 o «Modo» que você anotou, e aperte os quatro gatilhos para sentir que voltaram.
13. Na aba Iluminação, clique no primeiro quadradinho da coluna do P1 e no segundo da coluna do P2 — a cor do número de cada um —, para desfazer.

**Passa quando.** Cor, tremor e gatilho chegam aos dois controles do cabo, e as três coisas viajam pelo mesmo caminho único e curto que o cabo oferece. Não há nada a mais para ver aqui, e é exatamente isso que esta linha do mapa afirma.

**Por controle.**

* **P1** — USB, e é ESTE que prova o caminho: cor na barra de luz, tremor na mão, L2 e R2 travando. Devolva os gatilhos ao que eram no fim.
* **P2** — USB, o segundo. Os mesmos três gestos. Dois aparelhos fazem a prova valer mais que um.
* **P3** — BT, comparação. Não é preciso mexer nele: ele está aqui para lembrar que pelo rádio essas mesmas três coisas viajam por um caminho que tem nove tamanhos, e pelo cabo só um.
* **P4** — BT, segunda comparação. Não toque nele.

**A armadilha.** A pergunta desta linha não é respondível daqui, e o mapa é honesto sobre isso: pelo rádio o controle oferece NOVE caminhos de saída, de tamanhos crescentes; pelo cabo ele oferece um só. Se algum dos caminhos grandes funcionaria pelo fio, NINGUÉM TENTOU — a célula do mapa diz «desconhecido» e não «não», de propósito. Nenhum botão desta tela manda um caminho grande pelo cabo, e não é para você tentar isso com as mãos. Segunda: não declarar não é recusar — o cabo não anuncia esses caminhos, e isso não prova que ele os jogaria fora. Terceira: se o gatilho não travar, não conclua nada sobre o caminho; o DualSense não devolve o modo em que está, a tela mostra o que foi PEDIDO, e um jogo aberto pode estar escrevendo por cima. E o degrau: esta linha do mapa não tem degrau escrito.

---

## mapa-plataforma.escada_de_output-radio — Escada de reports de OUTPUT por rádio — 0x31 a 0x39, de 64 em 64 bytes · rádio

*Célula:* `plataforma.escada_de_output @ rádio`

**O que isto prova.** Prova que o caminho de saída que o Hefesto sabe montar chega ao controle pelo rádio nos DOIS aparelhos do ar — que é exatamente a amostra que faltava.

**Onde olhar.** No aparelho: a barra de luz do P3 e a do P4 (as duas tiras acesas dos lados do touchpad). Na tela, na aba Iluminação: cada controle tem uma coluna; a linha «Modelo» diz de quem ela é («P3 • <cor do plástico> • BT»); a linha «Cor» traz onze quadradinhos, com o código da cor escrito embaixo; a linha «Opções» traz o botão «Desligar»; e a linha «LEDs» desenha a barra e as lâmpadas que o Hefesto PEDIU, não as que estão acesas. Os caminhos maiores de saída não têm botão em tela nenhuma: o produto só sabe montar o menor.

**Os passos.**

1. Confira na fita do topo que os chips do P3 e do P4 terminam em BT e os do P1 e do P2 em USB.
* Abra a aba Iluminação.
2. Leia a linha «Modelo» das quatro colunas e confirme quem termina em USB e quem termina em BT.
3. Clique num quadradinho de cor livre — que nenhum outro controle esteja usando — na linha «Cor» da coluna do P1 e confirme a cor na barra de luz dele: este é o controle de comparação, pelo cabo.
4. Clique numa cor livre bem diferente na linha «Cor» da coluna do P3.
5. Olhe a barra de luz do P3 no aparelho e confirme que ela acendeu nessa cor.
6. Clique numa terceira cor livre na mesma coluna do P3 e confirme que a barra dele trocou.
7. Clique em «Desligar», na linha «Opções» da coluna do P3, e confirme que a barra dele apaga.
8. Clique numa cor de novo na coluna do P3 e confirme que ela volta a acender.
9. Repita os passos 4 a 8 na coluna do P4.
10. Olhe os quatro controles juntos: quatro barras acesas, quatro cores diferentes.
11. Clique, em cada coluna em que você mexeu, no quadradinho da cor do número daquele controle — o primeiro para o P1, o terceiro para o P3, o quarto para o P4 —, para desfazer.
12. Anote o modelo de cada um dos dois do rádio ao lado do resultado.

**Passa quando.** A barra de luz do P3 e a do P4 obedecem à cor escolhida, trocam quando você troca, apagam no «Desligar» e voltam quando você pinta de novo. As duas são do rádio, e é nas DUAS que a prova precisava existir: até hoje ela existia num aparelho só.

**Por controle.**

* **P1** — USB, e é a comparação. Pinte uma cor NELE primeiro: se ele também não obedecer, o achado não é do rádio e o resto do teste não mede nada.
* **P2** — USB. Não toque nele.
* **P3** — BT, e é ESTE que repete o que já foi visto: um aparelho como ele obedeceu com o seu olho em 15 de agosto.
* **P4** — BT, e é o que INTERESSA MAIS. A obediência pelo rádio está vista em UMA unidade só; este é o segundo aparelho. Se ele obedecer, a amostra fecha; se não, o achado é dele — anote o modelo.

**A armadilha.** A tela não é a prova. A linha «LEDs» e o código embaixo dos quadradinhos mostram o que o Hefesto PEDIU, e pelo rádio um pedido mal montado é jogado fora pelo controle sem uma palavra: a tela pode dizer que pediu e o plástico não mudar. Quem responde é a faixa acesa no plástico. Segunda: não mexa no interruptor «Cores automáticas por controle», no alto da aba — ele é do perfil e vale para os quatro de uma vez, e este teste é sobre a coluna de cada um. E escolha sempre um tom livre: um tom que já é de outro controle não fica no que você clicou, e a tela diz de quem ele era. Terceira, e é sobre o alcance: os caminhos GRANDES de saída não têm botão nesta tela. Dois deles já obedeceram, com o seu olho, em 15 de agosto, num aparelho branco — mas o Hefesto de hoje só sabe carimbar o menor para a luz; um grande sairia sem selo e o controle o jogaria fora enquanto o registro diria «escrito». Não procure por eles aqui. E o degrau: esta linha do mapa está com o degrau VAZIO de propósito — a obediência foi vista, mas o caderno de bancada ainda não tem o ensaio que a registra. O que você fizer aqui é o que vai preenchê-lo.

---

## mapa-plataforma.escrita_crua-cabo — Escrita crua por hidraw (qualquer subcomando) · cabo

*Célula:* `plataforma.escrita_crua @ cabo`

**O que isto prova.** Prova que o comando cru que a tela ainda aciona — o que põe o microfone do rádio no ar — nunca vai para os dois controles do cabo, e que eles seguem obedecendo depois.

**Onde olhar.** Na aba Conexões, no quadro «Gestão de Controles» (abre pelo título): a linha de cada controle diz por onde o microfone dele chega — nos do cabo, «pelo cabo • Placa do controle»; nos do rádio, «pelo rádio • Pela ponte». A ponte é o caminho cru, e ela só existe no rádio. Clicando na linha de um controle, ela abre e mostra, abaixo de «Microfone e botões», o campo com «Ligado» e «Desligado». Na aba Controles, no cartão de cada controle, o bloco «Microfone» tem uma barrinha que mexe com o som que está entrando agora. E na aba Iluminação, a linha «Cor» da coluna de cada controle e, no aparelho, a barra de luz. Não existe na tela nenhum campo que diga «o comando cru saiu».

**Os passos.**

1. Confira na fita do topo que os chips do P1 e do P2 terminam em USB.
* Abra a aba Conexões.
2. Clique no título «Gestão de Controles» e leia o que as linhas do P1 e do P2 dizem sobre o microfone: tem de estar escrito «pelo cabo • Placa do controle».
3. Abra a aba Controles, clique na linha do P1 para abrir o cartão dele e fale perto dele: a barrinha do bloco «Microfone» tem de mexer.
4. Volte à aba Conexões, clique na linha do P1 para abri-la e escolha «Desligado» no campo do microfone.
5. Volte à aba Controles e fale perto do P1 de novo: a barrinha tem de continuar mexendo, porque no cabo o microfone não passa pela ponte.
6. Volte à aba Conexões e escolha «Ligado» no campo do microfone do P1, para desfazer.
7. Repita os passos 3 a 6 no P2.
8. Abra a aba Iluminação e clique num quadradinho de cor livre na coluna do P1: a barra de luz dele tem de obedecer.
9. Faça o mesmo na coluna do P2.
10. Clique no primeiro quadradinho da coluna do P1 e no segundo da do P2 — a cor do número de cada um —, para desfazer.

**Passa quando.** As linhas do P1 e do P2 dizem «pelo cabo • Placa do controle» do começo ao fim, nunca «Pela ponte». Desligar a ponte de um controle do cabo não cala o microfone dele, e depois de tudo os dois continuam obedecendo à cor.

**Por controle.**

* **P1** — USB, e é um dos dois que provam que o caminho cru não os alcança. Microfone pela placa do próprio controle, antes e depois de mexer na ponte.
* **P2** — USB, o segundo. Mesma conferência. Se um dos dois do cabo se comportar diferente do outro, o achado é daquele aparelho e não do transporte — anote qual.
* **P3** — BT, testemunha. Não toque nele. A linha dele tem de continuar dizendo «pelo rádio • Pela ponte» enquanto você mexe nos do cabo.
* **P4** — BT, testemunha. Mesma coisa. Se a ponte dele cair quando você desliga a do P1, a escolha foi para o controle errado, e isso é o achado.

**A armadilha.** Três. (1) Este teste prova menos do que o nome da linha, e dizer isso é metade do valor dele: o outro comando cru da casa, o que devolve a barra de luz ao jogo, varre todos os controles, inclusive os do cabo — e ele não tem botão em tela nenhuma: só o instrumento de terminal da casa o manda, e a sua mão não alcança essa metade. (2) O que já está medido é que a escrita SAI e que o sistema a aceita — nunca que o aparelho a executou; é por isso que os passos 8 e 9 conferem que os controles seguem obedecendo depois. (3) O «Desligado» do campo do microfone fica guardado no controle e vale quando ele for para o rádio: se você esquecer o passo 6, o P1 chega ao rádio sem microfone. Devolva «Ligado» sempre.

---

## mapa-plataforma.escrita_crua-radio — Escrita crua por hidraw (qualquer subcomando) · rádio

*Célula:* `plataforma.escrita_crua @ rádio`

**O que isto prova.** Prova que o comando que o Hefesto escreve direto no aparelho para pôr o microfone no ar sai pelos dois controles do rádio — e que ele sobe e desce a ponte de cada um sem mexer no vizinho.

**Onde olhar.** Na aba Conexões, no quadro «Gestão de Controles» (abre pelo título): a linha de cada controle diz por onde o microfone dele chega — nos do rádio, «pelo rádio • Pela ponte»; nos do cabo, «pelo cabo • Placa do controle». A ponte é o caminho cru, que só existe no rádio. Clicando na linha de um controle, ela abre e mostra, abaixo de «Microfone e botões», o campo com «Ligado» e «Desligado» — é ele que sobe e desce a ponte. Na aba Controles, no cartão de cada controle, o bloco «Microfone» tem uma barrinha que mexe com o som que está entrando agora, e é ela que mostra a ponte de pé.

**Os passos.**

* Abra a aba Conexões.
1. Confira na fita do topo que os chips do P3 e do P4 terminam em BT.
2. Clique no título «Gestão de Controles» e leia o que as linhas do P3 e do P4 dizem sobre o microfone: tem de estar escrito «pelo rádio • Pela ponte».
3. Leia a mesma coisa nas linhas do P1 e do P2: nelas tem de estar escrito «pelo cabo • Placa do controle».
4. Abra a aba Controles, clique na linha do P3 para abrir o cartão dele e fale perto dele: a barrinha do bloco «Microfone» tem de mexer.
5. Volte à aba Conexões, clique na linha do P3 para abri-la e escolha «Desligado» no campo do microfone.
6. Volte à aba Controles e fale perto do P3: a barrinha dele tem de parar de mexer, e o bloco «Microfone» dele fica cinza.
7. Fale perto do P4 e confira que a barrinha DELE continua mexendo.
8. Volte à aba Conexões e escolha «Ligado» no campo do microfone do P3.
9. Volte à aba Controles e fale perto do P3: a barrinha tem de voltar a mexer.
10. Refaça os passos 4 a 9 com o P4, conferindo o P3 no lugar do P4 no passo 7.

**Passa quando.** Os dois do rádio dizem, na aba Conexões, que o microfone deles chega pela ponte, e a barrinha do cartão de cada um mexe quando você fala perto dele. «Desligado» derruba a ponte daquele controle — a barrinha dele para — sem calar o vizinho, e «Ligado» a traz de volta. Nada disso acontece no P1 nem no P2: as linhas deles dizem, do começo ao fim, que o microfone vem pela placa do próprio controle.

**Por controle.**

* **P1** — USB, testemunha — e é ela que prova a divisão. A linha dele tem de dizer que o microfone vem pelo cabo, pela placa do próprio controle. Se disser «Pela ponte», o caminho que devia ser só do rádio vazou para o cabo, e esse é o achado.
* **P2** — USB, a segunda testemunha. Mesma leitura da linha.
* **P3** — BT, é um dos dois que recebem. Fale perto dele, desça a ponte, confira o silêncio só nele, e suba de novo.
* **P4** — BT, o segundo que recebe. Mesmos gestos. Se um dos dois do rádio responder e o outro não, o achado é daquele aparelho ou da distância dele até o adaptador, não do transporte — anote qual.

**A armadilha.** Três. (1) O 🎙 do bloco «Microfone», na aba Controles, é o RETORNO: aceso, você se ouve pelo PC até clicar de novo; ele não liga nem desliga a ponte, e com o microfone calado no botão do próprio controle ele recusa dizendo por quê. Não confunda o silêncio do retorno com a ponte caída. (2) O que está provado é que a escrita SAI e que o sistema a aceita, nunca que o aparelho a executou — o que a sua voz prova é o degrau seguinte: a ponte sobe e o som chega. (3) O outro comando cru da casa, o que devolve a barra de luz ao jogo, não tem botão em tela nenhuma: essa metade da linha a sua mão não alcança. E devolva sempre «Ligado» no fim — o «Desligado» fica guardado no controle e é o único registro de que você disse não, então ele não volta sozinho.

---

## mapa-plataforma.feature_f6-cabo — FEATURE 0xF6 (547 B) — existe só no rádio, lê VAZIO, função desconhecida · cabo

*Célula:* `plataforma.feature_f6 @ cabo`

**O que isto prova.** Prova que o Hefesto não promete nada sobre um bloco de dados escondido do controle que, no cabo, nem chega a existir.

**Onde olhar.** O produto não lê nem escreve esse bloco em lugar nenhum, e nenhuma aba tem campo para ele. O que se olha é onde ele apareceria se alguém o tivesse ligado. Primeiro, a aba Controles: clicando na linha de um controle, o cartão abre — no alto, USB ou BT, o nome do que o jogo vê, o selo do «Microfone», a frase do giroscópio, os interruptores «Giroscópio» e «Acelerômetro» e a «Bateria»; dentro, «Touchpad», «Barra de luz», «LED do jogador», os dois analógicos, os botões, os blocos «Microfone» e «Alto-falante», «Giroscópio», «Acelerômetro» e «Gatilhos». Segundo, a aba Sistema: na faixa «Avançado», à esquerda, os botões «Restaurar de fábrica», «Aplicar aos jogos da Steam» e «Ver detalhes»; ao lado, o painel «Detalhes técnicos», que é a saída crua do Hefesto e se preenche sozinho. «Ver detalhes» põe no painel as últimas 80 linhas do registro.

**Os passos.**

1. Confira na fita do topo que os chips do P1 e do P2 terminam em USB.
2. Abra a aba Controles.
3. Clique na linha do P1 para abrir o cartão dele.
4. Leia todos os campos do cartão, um a um, e anote se algum traz um valor que a tela não explica de onde veio.
5. Clique na linha do P2 e faça a mesma leitura no cartão dele.
6. Abra a aba Sistema.
7. Desça até a faixa «Avançado».
8. Leia o painel «Detalhes técnicos», rolando-o de cima a baixo.
9. Clique em «Ver detalhes» e leia as linhas que aparecem no painel.
10. Procure alguma linha que fale de uma leitura de 547 bytes, ou de um bloco que o controle devolva vazio.
11. Anote o que você encontrou; o esperado é não encontrar nada.

**Passa quando.** Nenhuma tela mostra valor nenhum vindo desse bloco escondido, e nenhum campo dos cartões do P1 e do P2 promete um dado que venha dele. O painel «Detalhes técnicos» não traz uma única linha sobre ele. Não acontecer nada é o verde deste teste.

**Por controle.**

* **P1** — USB, e é onde o teste tem mais força: pelo cabo o controle nem chega a declarar que esse bloco existe. Qualquer valor na tela que dissesse vir dele para este controle seria inventado.
* **P2** — USB, a mesma leitura no cartão dele. Dois iguais valem mais que um: se um dos dois mostrar alguma coisa que o outro não mostra, anote qual é.
* **P3** — BT, e aqui ele serve só de contraste — é no rádio que o bloco existe de verdade. Não mexa nele; ele tem a linha dele.
* **P4** — BT, mesma coisa. Não mexa; só confira que o cartão dele não mostra nenhum campo a mais do que o do P1.

**A armadilha.** Este é um dos raros testes em que NADA ACONTECER é o resultado certo, e é fácil registrá-lo como «não consegui testar». Ele existe para a próxima pessoa não gastar um dia procurando. Esse bloco foi lido com instrumento de bancada, nunca com a mão, e voltou vazio nos quatro controles — mas vir vazio numa leitura que não provocou o aparelho não decide nada nos dois sentidos: «só responde depois de um pedido» e «não responde nunca» devolvem o mesmo silêncio, e ninguém nunca o provocou com escrita nenhuma. Então a sua mão não pode provar o que ele faz; ela pode provar que o produto não finge saber. Se algum dia aparecer na tela um campo que diga vir daí, isso é o achado, e é grave: seria a tela afirmando uma função que medição nenhuma sustenta. E não clique em «Restaurar de fábrica», que fica na mesma faixa «Avançado» — não há razão de encostar nele aqui.

---

## mapa-plataforma.feature_f6-radio — FEATURE 0xF6 (547 B) — existe só no rádio, lê VAZIO, função desconhecida · rádio

*Célula:* `plataforma.feature_f6 @ rádio`

**O que isto prova.** Prova que, nos dois controles do rádio — onde esse bloco escondido de fato existe —, o Hefesto continua sem lê-lo e sem prometer nada sobre ele.

**Onde olhar.** O produto não o lê em lugar nenhum, e nenhuma aba tem campo para ele. O que se olha é onde ele apareceria. Na aba Controles, o cartão que abre ao clicar na linha de um controle — no alto, USB ou BT, o nome do que o jogo vê, o selo do «Microfone», a frase do giroscópio, os interruptores e a «Bateria»; dentro, «Touchpad», «Barra de luz», «LED do jogador», os dois analógicos, os botões, os blocos «Microfone» e «Alto-falante», «Giroscópio», «Acelerômetro» e «Gatilhos». E na aba Sistema, na faixa «Avançado», o painel «Detalhes técnicos», ao lado dos botões, que é a saída crua do Hefesto e se preenche sozinho — o botão «Ver detalhes» põe nele as últimas 80 linhas do registro.

**Os passos.**

1. Confira na fita do topo que os chips do P3 e do P4 terminam em BT.
2. Abra a aba Controles.
3. Clique na linha do P1 para abrir o cartão dele e anote quais campos ele mostra, na ordem.
4. Clique na linha do P3 para abrir o cartão dele.
5. Compare campo a campo com o que você anotou do P1: o do rádio não pode ter nenhum campo a mais.
6. Clique na linha do P4 e faça a mesma comparação.
7. Abra a aba Sistema.
8. Desça até a faixa «Avançado» e leia o painel «Detalhes técnicos», rolando-o de cima a baixo.
9. Clique em «Ver detalhes» e leia as linhas que aparecem.
10. Procure alguma linha que fale de um bloco de 547 bytes lido do controle, ou de uma leitura que só aconteça no rádio.
11. Anote o que você encontrou; o esperado é não encontrar nada.

**Passa quando.** Os cartões do P3 e do P4 mostram exatamente os mesmos campos que os do P1 e do P2 — nenhum campo a mais, nenhum valor que só apareça no rádio. E o painel «Detalhes técnicos» não traz uma linha sequer sobre esse bloco. Não acontecer nada é o verde.

**Por controle.**

* **P1** — USB, é a régua de comparação. Anote os campos do cartão dele ANTES de abrir o de um controle do rádio: sem esse antes não há com o que comparar, e o teste não mede nada.
* **P2** — USB, a segunda régua. Confira que ele mostra os mesmos campos do P1 — se os dois do cabo já divergirem entre si, pare e anote, porque a comparação com o rádio deixou de valer.
* **P3** — BT, e é aqui que o bloco existe de verdade. Compare o cartão dele com o do P1, campo a campo, com os dois rótulos lado a lado.
* **P4** — BT, o segundo. Mesma comparação. Se um dos dois do rádio mostrar um campo que o outro não mostra, isso é achado — anote qual, mesmo que não tenha nada a ver com este bloco.

**A armadilha.** Pelo rádio o bloco EXISTE e tem 547 bytes, exatamente o tamanho do maior pacote de saída do aparelho — e essa coincidência de tamanho é a única coisa que alimenta a suspeita de que ele sirva para combinar som. Suspeita, não medição: o conteúdo veio zerado nas quatro unidades lidas, e ninguém provocou o aparelho para ver se ele responde diferente depois de um pedido. O som pelo rádio, quando foi medido em 10/09, saiu por outro degrau da escada, e não por este bloco. Se você ler alguém desta casa dizendo que ele serve para o som, isso é hipótese vestida de fato, e derrubá-la é serviço prestado. Como no lado do cabo, nada acontecer é o verde — o difícil deste teste é registrá-lo como feito em vez de como impossível. E não clique em «Restaurar de fábrica», que fica na mesma faixa «Avançado».

---

## mapa-plataforma.inventario-cabo — Inventário read-only do controle na interface e na CLI · cabo

*Célula:* `plataforma.inventario @ cabo`

**O que isto prova.** Prova que a lista do que o Hefesto sabe de cada controle está completa e certa para os dois do cabo, inclusive o número de série, que só o cabo entrega.

**Onde olhar.** Três lugares. Na aba Controles, o quadro «Dispositivos conectados»: cada controle é uma linha com o número, a cor do plástico e USB ou BT; clicando na linha o cartão abre com a leitura viva — «Bateria» em porcento, «Touchpad» contando os toques, «Barra de luz» com o código da cor, «LED do jogador», os dois analógicos com X e Y, «Gatilhos» com um número de 0 a 255 para o L2 e para o R2, e os blocos «Giroscópio» e «Acelerômetro» com X, Y e Z. Na aba Sistema, na faixa «Avançado», o painel «Detalhes técnicos» se preenche sozinho e mostra o FIM do texto: lá embaixo há um bloco chamado «Identidade de fábrica», com uma linha por controle ligado — no formato «P1 · Cosmic Red · USB · <número de série>». E na aba Conexões, no quadro «Gestão de Controles», cada linha traz «Vê como», que é o que o jogo enxerga.

**Os passos.**

1. Confira na fita do topo que os chips do P1 e do P2 terminam em USB.
* Abra a aba Sistema.
2. Desça até a faixa «Avançado» e leia o painel «Detalhes técnicos», ao lado dos botões.
3. Role o painel até o fim e ache o bloco «Identidade de fábrica».
4. Conte as linhas desse bloco: tem de haver uma para cada um dos quatro controles ligados.
5. Leia a linha do P1: ela tem de trazer P1, a cor do plástico, USB e um número de série comprido.
6. Leia a linha do P2 do mesmo jeito.
7. Pegue o P1 na mão e compare a cor do plástico dele com o nome escrito na linha.
8. Faça a mesma comparação com o P2.
9. Abra a aba Controles e clique na linha do P1 para abrir o cartão dele.
10. Confira que a «Bateria» mostra um número em porcento, e não um traço.
11. Encoste um dedo no touchpad do P1 e confira que o «Touchpad» passa a contar o toque.
12. Empurre o analógico esquerdo do P1 e confira que os números X e Y dele andam no cartão.
13. Aperte o L2 do P1 até o fim e confira que o número dele, em «Gatilhos», sobe até perto de 255.
14. Gire o P1 na mão e confira que os números do «Giroscópio» saem do zero.
15. Repita os passos 9 a 14 no P2.
16. Abra a aba Conexões, clique no título «Gestão de Controles» e leia o que as linhas do P1 e do P2 dizem em «Vê como».

**Passa quando.** As quatro linhas de «Identidade de fábrica» existem, e as do P1 e do P2 trazem USB e um número de série comprido — nenhuma das duas com traço no lugar do serial, e os dois seriais diferentes um do outro. A cor escrita bate com o plástico que você tem na mão. E no cartão de cada um, todo campo que devia responder responde: bateria com número, touchpad contando o toque, analógico andando, gatilho subindo até perto de 255 e giroscópio saindo do zero.

**Por controle.**

* **P1** — USB, e é ele que tem de trazer o número de série inteiro. Confira também o nome da cor contra o plástico na sua mão.
* **P2** — USB. O mesmo, e ele é a segunda prova: dois aparelhos, dois seriais diferentes. Dois controles com o MESMO serial escrito na tela é achado grave — anote os dois.
* **P3** — BT, testemunha. Só confira que a linha dele existe no bloco e que ela diz BT. O serial dele é assunto da outra linha deste par, e a falta dele aqui não é defeito.
* **P4** — BT, testemunha. Mesma conferência. Se faltar a linha de um dos quatro no bloco, o inventário perdeu um controle, e isso é o achado.

**A armadilha.** Esta linha nunca foi medida com controle na mão: ela foi respondida LENDO O CÓDIGO, e o seu teste é o primeiro contato dela com o aparelho — anote tudo o que divergir, mesmo o que parecer bobagem. Duas armadilhas de leitura. A primeira: o painel «Detalhes técnicos» é baixo e mostra sempre o FIM do texto; a identidade fica no fim de propósito, e o resto do diagnóstico está uma rolada acima — quem não rolar vai jurar que o painel só tem o estado do serviço. E se você clicar em «Ver detalhes», o painel passa a mostrar o registro, e a identidade sai dele. A segunda: campo sem informação não mostra nada, por decisão sua — um campo em branco quer dizer «não foi lido», não «zero», e um traço no lugar de um número tem o mesmo sentido; nenhum dos dois conta como passa. E não confunda o que o cartão mostra com o que o jogo recebe: o «Vê como» da aba Conexões diz a máscara que o jogo enxerga, e ela se escolhe na aba Jogar — se estiver dizendo Xbox 360, é escolha sua e não defeito de inventário. Por fim, não clique em «Restaurar de fábrica», que fica na mesma faixa «Avançado».

---

## mapa-plataforma.inventario-radio — Inventário read-only do controle na interface e na CLI · rádio

*Célula:* `plataforma.inventario @ rádio`

**O que isto prova.** Prova que a lista do que o Hefesto sabe dos dois controles do rádio está completa até onde ele publica — e que o que falta aparece dito com todas as letras, em vez de sumir calado.

**Onde olhar.** Os mesmos dois lugares do lado do cabo, agora nas linhas do rádio. Na aba Sistema, faixa «Avançado», o painel «Detalhes técnicos» se preenche sozinho e mostra o FIM do texto: no fim dele está o bloco «Identidade de fábrica», com uma linha por controle ligado. Nas linhas do rádio, no lugar do serial, tem de estar escrita a frase «o serial só é lido no cabo» — por exemplo «P3 · Nova Pink · BT · o serial só é lido no cabo». E na aba Controles, o cartão que abre ao clicar na linha de um controle, com «Bateria» em porcento, «Touchpad», os dois analógicos, «Gatilhos» e os blocos «Giroscópio» e «Acelerômetro».

**Os passos.**

1. Confira na fita do topo que os chips do P3 e do P4 terminam em BT.
* Abra a aba Sistema.
2. Desça até a faixa «Avançado» e leia o painel «Detalhes técnicos».
3. Role o painel até o fim e ache o bloco «Identidade de fábrica».
4. Leia a linha do P3: ela tem de trazer P3, a cor do plástico e BT.
5. Leia o fim dessa mesma linha: no lugar do número de série tem de estar escrito «o serial só é lido no cabo».
6. Leia a linha do P4 do mesmo jeito.
7. Pegue o P3 na mão e compare a cor do plástico dele com o nome escrito na linha.
8. Faça a mesma comparação com o P4.
9. Abra a aba Controles e clique na linha do P3 para abrir o cartão dele.
10. Confira que a «Bateria» mostra um número em porcento, e não um traço.
11. Encoste um dedo no touchpad do P3 e confira que o «Touchpad» passa a contar o toque.
12. Empurre o analógico esquerdo do P3 e confira que os números andam no cartão.
13. Gire o P3 na mão e confira que os números do «Giroscópio» saem do zero.
14. Repita os passos 9 a 13 no P4.
15. Clique na linha do P1 e compare os campos do cartão dele com os do P3: têm de ser os mesmos campos, com os mesmos rótulos.

**Passa quando.** As linhas do P3 e do P4 existem no bloco, dizem BT, trazem o nome da cor do plástico que bate com o aparelho na sua mão, e no lugar do número de série trazem a frase escrita — não um espaço em branco nem um traço seco. E os cartões dos dois respondem: bateria com número, touchpad contando o toque, analógico andando e giroscópio saindo do zero.

**Por controle.**

* **P1** — USB, régua de comparação: a linha dele traz o serial, e é olhando as duas linhas lado a lado que a diferença entre os transportes fica visível.
* **P2** — USB, a segunda régua. Confira que ele também traz serial — se nenhum dos dois do cabo trouxer, o problema não é do rádio e este teste está medindo outra coisa.
* **P3** — BT, é um dos dois medidos. Confira o nome da cor, o BT, a frase no lugar do serial, e os campos vivos do cartão.
* **P4** — BT, o segundo, e é o que mais importa aqui: a leitura da cor do plástico pelo rádio só foi provada em DUAS unidades, e nenhuma delas é necessariamente esta. Se o P4 vier sem nome de cor, o achado é DESTA unidade e não do transporte — anote qual controle é.

**A armadilha.** A frase «o serial só é lido no cabo» diz menos do que parece: o aparelho RESPONDE o serial pelo rádio também — medido em 03/09 —, quem não o publica é o serviço. Então a frase não é o aparelho recusando, e o que É defeito é outra coisa: um número de série aparecendo na linha de um controle do rádio — alguém o inventou —, ou um traço seco no lugar da frase. Duas coisas mais. A cor do plástico pelo rádio está provada em duas unidades, não nas quatro desta bancada; se um terceiro controle recusar, o achado é a assinatura daquele aparelho, e a tela responde «não sei» em vez de mentir uma cor. E, como no lado do cabo: esta linha foi respondida lendo o código, nunca com controle na mão, e o seu teste é o primeiro contato dela com o aparelho.

---

## mapa-plataforma.limitador_subcomando-cabo — Limitador de subcomando (o que governa toda escrita) · cabo

*Célula:* `plataforma.limitador_subcomando @ cabo`

**O que isto prova.** Prova que o Hefesto não perde o último clique quando você muda a mesma coisa muitas vezes seguidas num controle do cabo.

**Onde olhar.** Na aba Iluminação, a coluna do P1 e a do P2: a linha «Cor», com onze quadradinhos de cor lado a lado, e o código da cor escrito logo abaixo deles — é a cor que vai ao aparelho. A resposta é a barra de luz no plástico — as duas tiras acesas dos lados do touchpad. O passo com que o Hefesto junta os pedidos e os manda ao aparelho não tem campo na tela. O que a sua mão mede é só o resultado — se o último clique chegou, e em quanto tempo.

**Os passos.**

1. Confira na fita do topo que os chips do P1 e do P2 terminam em USB.
2. Feche a Steam e qualquer jogo aberto.
* Abra a aba Iluminação.
3. Olhe as quatro colunas e repare quais cores os outros três controles estão usando: a rajada só pode usar quadradinhos que nenhum deles tenha.
4. Clique num quadradinho livre, de cor bem diferente da atual, na linha «Cor» da coluna do P1.
5. Confirme que a barra do P1 acendeu nessa cor.
6. Clique agora, um atrás do outro e o mais rápido que você conseguir, em seis quadradinhos livres DIFERENTES da linha «Cor» do P1, terminando num que você reconheça de longe.
7. Tire a mão do mouse e olhe a barra do P1: ela tem de estar na cor do ÚLTIMO clique.
8. Confira que ela não parou numa cor do meio da sequência.
9. Leia o código da cor escrito abaixo dos quadradinhos e confira que ele é o do último clique.
10. Olhe as barras do P2, do P3 e do P4: nenhuma pode ter mudado.
11. Repita os passos 6 a 10 na coluna do P2.
12. Anote, mais ou menos, quanto tempo a barra levou para assentar na última cor depois de você parar de clicar.
13. Clique no primeiro quadradinho da coluna do P1 e no segundo da do P2 — a cor do número de cada um —, para desfazer.

**Passa quando.** Depois da rajada de cliques, a barra do controle em que você clicou fica na cor do ÚLTIMO quadradinho, e não numa do meio. O código escrito abaixo dos quadradinhos concorda com a barra acesa. As barras dos outros três não mudam. E a barra assenta em menos de um segundo depois do último clique.

**Por controle.**

* **P1** — USB, é o primeiro a receber a rajada. Seis quadradinhos livres diferentes, o mais rápido que você conseguir, e o último tem de ser o que fica.
* **P2** — USB, o segundo. Faça nele a mesma rajada, depois que o P1 já tiver assentado: os dois do cabo têm de se comportar igual, e uma diferença entre eles é achado do aparelho.
* **P3** — BT, testemunha aqui — ele tem linha própria. Não clique na coluna dele; só confira que a barra não mudou durante as duas rajadas.
* **P4** — BT, testemunha. Mesma coisa. Se a cor da rajada do P1 aparecer nele, o pedido foi para o controle errado.

**A armadilha.** Clicar duas vezes no MESMO quadradinho não testa nada: o segundo clique não tem novidade a mandar, e não mandar é o certo — o Hefesto não reenvia um pedido idêntico ao anterior, de propósito. Use quadradinhos diferentes, sempre. E use só os livres: um tom que já é de outro controle não fica no que você clicou, e a tela diz de quem ele era — com isso no meio da rajada, o «último clique» deixa de ser o que você pensa. Outra: o passo com que o Hefesto junta os pedidos cresce com o número de controles ligados; com os quatro ligados ele é mais lento do que seria com um só, e uma barra que demora um pouco mais a assentar não é defeito. Feche a Steam antes de começar: com ela aberta, quem escreve por último na luz ganha, e você pode acabar medindo a Steam. E lembre que esta linha foi respondida lendo o código e nunca com controle na mão — se a barra ficar presa numa cor do meio da sequência, isso é achado novo, e vale anotar exatamente quantos cliques você deu e em que ordem.

---

## mapa-plataforma.limitador_subcomando-radio — Limitador de subcomando (o que governa toda escrita) · rádio

*Célula:* `plataforma.limitador_subcomando @ rádio`

**O que isto prova.** Prova que a rajada de cliques também não se perde nos dois controles do rádio, e separa o que é do passo de envio do que é do sem fio.

**Onde olhar.** Na aba Iluminação, as colunas do P1, do P3 e do P4: a linha «Cor», com onze quadradinhos de cor, e o código da cor escrito logo abaixo — é a cor que vai ao aparelho. A resposta é a barra de luz no plástico, as duas tiras acesas dos lados do touchpad. O passo com que o Hefesto junta os pedidos e os manda não tem campo na tela — e ele é o MESMO número no cabo e no rádio, o que é justamente o que torna a comparação entre os dois útil.

**Os passos.**

1. Confira na fita do topo que os chips do P3 e do P4 terminam em BT e que o do P1 termina em USB.
2. Feche a Steam e qualquer jogo aberto.
* Abra a aba Iluminação.
3. Olhe as quatro colunas e repare quais cores cada controle está usando: a rajada só pode usar quadradinhos que nenhum dos outros tenha.
4. Clique, um atrás do outro e o mais rápido que conseguir, em seis quadradinhos livres DIFERENTES da linha «Cor» da coluna do P1, terminando num que você reconheça de longe.
5. Olhe a barra do P1 e anote se ela ficou na cor do último clique e quanto tempo levou para assentar.
6. Faça a mesma rajada de seis quadradinhos livres diferentes na coluna do P3.
7. Tire a mão do mouse e olhe a barra do P3: ela tem de estar na cor do ÚLTIMO clique.
8. Confira que ela não parou numa cor do meio da sequência.
9. Leia o código da cor abaixo dos quadradinhos do P3 e confira que ele é o do último clique.
10. Olhe as barras do P1, do P2 e do P4: nenhuma pode ter mudado por causa da rajada do P3.
11. Repita os passos 6 a 10 na coluna do P4.
12. Compare o que você anotou do P1 com o que aconteceu no P3 e no P4, e anote a diferença de tempo.
13. Clique, nas colunas do P1, do P3 e do P4, no quadradinho da cor do número de cada um — o primeiro, o terceiro e o quarto —, para desfazer.

**Passa quando.** Depois da rajada, a barra do controle do rádio fica na cor do último quadradinho, e não numa do meio — exatamente como aconteceu no do cabo. O código escrito abaixo dos quadradinhos concorda com a barra. As barras dos outros três não mudam.

**Por controle.**

* **P1** — USB, e é a régua: faça a rajada NELE primeiro e anote o tempo. Sem esse antes não há com o que comparar, e o teste não separa nada.
* **P2** — USB, testemunha. Não clique na coluna dele; só confira que a barra não mudou durante as rajadas dos outros.
* **P3** — BT, é o primeiro a receber a rajada. Seis quadradinhos livres diferentes, e o último tem de ser o que fica na barra.
* **P4** — BT, o segundo. Faça a rajada nele depois que o P3 assentar; se só ele perder cliques, confira em «Rádio e Adaptadores», na aba Conexões, se ele está no mesmo adaptador do P3 — a diferença pode ser do enlace dele, não do envio.

**A armadilha.** O número com que o Hefesto espaça os envios é o MESMO no cabo e no rádio — não existe um valor por transporte. Então, se a rajada se perder só no rádio, a causa não é esse passo: é o enlace sem fio, e é para separar as duas coisas que a rajada no P1 vem primeiro. Sem ela, o teste não mede nada. As outras de sempre: clicar duas vezes no mesmo quadradinho não manda nada de novo, de propósito, então use quadradinhos diferentes; use só os livres, porque um tom que já é de outro controle não fica no que você clicou; e o passo cresce com o número de controles ligados, então com quatro ligados tudo assenta um pouco mais devagar do que assentaria com um. Feche a Steam antes: com ela aberta, quem escreve por último na luz ganha.

---

## mapa-plataforma.link_parametros-cabo — Parâmetros do link (supervisão, sniff negociado, latência) · cabo

*Célula:* `plataforma.link_parametros @ cabo`

**O que isto prova.** Prova que o Hefesto não oferece nem inventa ajuste de enlace sem fio para os dois controles do cabo — onde enlace sem fio nem existe.

**Onde olhar.** Na aba Conexões, três quadros que abrem pelo título, um de cada vez. O «Check-up» é o exame da sala: energia das entradas, rádio, vizinhança. O «Gestão de Controles» tem uma linha por controle ligado, e clicar na linha abre os ajustes dele — o campo do microfone, abaixo de «Microfone e botões», o «Limite da vibração» e o botão «A luz não acende». O «Rádio e Adaptadores» tem um bloco por adaptador Bluetooth, e o ▶ de cada um abre a lista dos controles que estão nele, cada um com o número de pacotes de movimento por segundo que chegam agora. Não existe em tela nenhuma um campo que ofereça mexer em tempo de supervisão, em intervalo de escuta ou em latência do enlace.

**Os passos.**

1. Confira na fita do topo que os chips do P1 e do P2 terminam em USB.
* Abra a aba Conexões.
2. Leia o quadro «Check-up» de cima a baixo e anote cada linha que fale dos controles do cabo.
3. Confira que nenhuma dessas linhas oferece um ajuste de enlace — elas falam de energia, de entrada e de vizinhança de rádio.
4. Clique no título «Gestão de Controles» e clique na linha do P1 para abri-la.
5. Leia os ajustes que abrem e confira que nenhum oferece mexer em tempo de resposta, intervalo ou latência de rádio.
6. Pare o ponteiro sobre o botão «A luz não acende» da linha do P1 e leia a dica: ela diz que ele só funciona com o controle no rádio.
7. Repita os passos 4 a 6 na linha do P2.
8. Clique no título «Rádio e Adaptadores» e clique no ▶ de cada adaptador.
9. Confira que o P1 e o P2 não aparecem em adaptador nenhum, e que o P3 e o P4 aparecem.
10. Anote o que você encontrou; o esperado é nenhum ajuste de enlace e nenhum controle do cabo no rádio.

**Passa quando.** Nenhuma aba oferece ajuste de enlace sem fio para um controle do cabo, e nenhum número na tela é apresentado como medida do enlace deles. O P1 e o P2 não aparecem em «Rádio e Adaptadores», e o «A luz não acende» deles diz que só vale no rádio.

**Por controle.**

* **P1** — USB. Confira que ele não aparece em adaptador nenhum e que nenhum campo da linha dele oferece ajuste de rádio. Ele não tem enlace sem fio: não há o que parametrizar.
* **P2** — USB. Mesma conferência. Se um dos dois do cabo aparecer num adaptador, a tela está cobrando rádio de quem não fala no rádio, e esse é o achado.
* **P3** — BT, testemunha, e é o contraste que dá sentido ao teste: ele SIM tem de aparecer na lista de um adaptador.
* **P4** — BT, testemunha. Mesma coisa. Se ele estiver ligado no rádio e não aparecer em adaptador nenhum, anote — a seção está contando menos gente do que existe.

**A armadilha.** O erro fácil aqui é ler como ajuste de enlace o que é outra coisa. Os números em Hz de «Rádio e Adaptadores» são LEITURA do que chega agora de cada controle do rádio, e não parâmetro que alguém escolha; os canais que a faixa «Quem está no ar» diz que os adaptadores evitam também são leitura, feita no próprio adaptador. Nenhum deles é tempo de supervisão, escuta ou latência — ninguém nesta casa tem instrumento que leia esses três, e o lado do cabo nem tem enlace a ler. Não confunda com o «Check-up»: ele fala de energia das entradas e de vizinhança de rádio, que são outra coisa e existem de verdade.

---

## mapa-plataforma.link_parametros-radio — Parâmetros do link (supervisão, sniff negociado, latência) · rádio

*Célula:* `plataforma.link_parametros @ rádio`

**O que isto prova.** Prova que, nos dois controles do rádio, o Hefesto continua sem mexer no enlace e sem apresentar como medido nenhum número que ninguém mediu.

**Onde olhar.** Na aba Conexões, a seção «Rádio e Adaptadores», que abre pelo título: no alto, a faixa «Quem está no ar», com a frase de quantos aparelhos Bluetooth seus saltam por quantos canais livres e a conta «N/79 evitados» — os canais que os adaptadores evitam, lidos no próprio adaptador; embaixo, um bloco por adaptador, e o ▶ de cada um abre a lista dos controles que estão nele, cada um com o número de pacotes de movimento por segundo que chegam AGORA (em Hz, ao lado do ícone de sinal). Acima, o quadro «Gestão de Controles», com a linha de cada controle, que se abre ao clicar.

**Os passos.**

1. Confira na fita do topo que os chips do P3 e do P4 terminam em BT.
2. Abra a aba Conexões.
3. Clique no título «Rádio e Adaptadores» e clique no ▶ de cada adaptador.
4. Confira que o P3 e o P4 aparecem, cada um na lista de um adaptador, com um número em Hz ao lado.
5. Anote o Hz de cada um; conte até dez e leia de novo — é leitura viva, e pode oscilar.
6. Leia a faixa «Quem está no ar» e anote a conta de canais evitados.
7. Procure, em toda a seção, qualquer campo que ofereça mexer em tempo de resposta, intervalo de escuta ou latência do rádio.
8. Clique no título «Gestão de Controles» e clique na linha do P3 para abri-la.
9. Procure, dentro dela, qualquer campo que ofereça mexer no enlace; os ajustes dela são o microfone, o «Limite da vibração» e o botão «A luz não acende».
10. Repita a procura na linha do P4.
11. Anote qualquer número da tela que seja apresentado como tempo de supervisão, escuta ou latência do enlace.

**Passa quando.** Nenhuma linha dos controles do rádio oferece ajuste de enlace, e os números que a seção mostra são leituras do que chega (os Hz de movimento) e do que o adaptador evita (os canais) — nenhum é apresentado como supervisão, escuta ou latência. A lista mostra os DOIS controles do rádio, cada um no adaptador em que está.

**Por controle.**

* **P1** — USB, testemunha: ele não aparece em «Rádio e Adaptadores», e nenhum campo da linha dele oferece ajuste de rádio.
* **P2** — USB, testemunha. Mesma coisa. Os dois do cabo juntos mostram que a seção sabe separar quem fala no rádio de quem não fala.
* **P3** — BT, é um dos dois medidos. Confira que ele aparece num adaptador com o Hz ao lado, e que nenhum campo da linha dele oferece mexer no enlace.
* **P4** — BT, o segundo. Mesma conferência — e com os dois no ar cada um tem de aparecer com o SEU número; dois Hz sempre idênticos, leitura após leitura, é o achado.

**A armadilha.** O que esta linha do mapa diz é «ninguém sabe», e o teste tem de conseguir enxergar isso. Não há nesta casa instrumento que leia tempo de supervisão, intervalo de escuta ou latência do enlace: quem negocia esses números é o sistema com o firmware, sozinho. E há uma prova de que a ausência é do aparelho e não de quem procurou: o driver desta máquina tem as alavancas todas para um controle mais velho da mesma marca, e nenhuma para o DualSense. Então um verde aqui não diz que o enlace está bom — diz que a tela não mente sobre ele. Segunda: os canais evitados e os Hz são leituras reais, mas de OUTRAS grandezas — não os tome por supervisão ou latência. Terceira: a dica do campo do microfone, numa linha do rádio da «Gestão de Controles», traz uma conta de relatórios e quadros por segundo; ela é uma conta feita com um controle na bancada de agosto, não a leitura do seu enlace de agora — não julgue o seu rádio por ela.

---

## mapa-plataforma.probe-cabo — Subir a probe (o controle EXISTIR para o sistema) · cabo

*Célula:* `plataforma.probe @ cabo`

**O que isto prova.** Prova que encaixar o cabo faz o controle nascer INTEIRO para o Hefesto — com número, bateria, movimento e touchpad — em menos de cinco segundos.

**Onde olhar.** Na fita do topo, a linha que começa com «Selecionar:»: cada controle é um chip no formato «P1 • <nome da cor do plástico> • USB». No canto de cima, à direita, a contagem, no formato «● 2 USB · 2 BT». Na aba Controles, o quadro «Dispositivos conectados», com uma linha por controle, e o cartão que abre ao clicar na linha: «Bateria» em porcento, «Touchpad», os dois analógicos, «Gatilhos» e os blocos «Giroscópio» e «Acelerômetro» com X, Y e Z.

**Os passos.**

1. Deixe o P3 e o P4 ligados no rádio e não encoste neles durante o teste.
* Abra a aba Controles.
2. Anote o nome da cor do plástico de cada um dos quatro chips da fita.
3. Desencaixe o cabo do P1.
4. Conte até dez, devagar.
5. Confira que o chip com o plástico do P1 saiu da fita e que a contagem passou a «● 1 USB · 2 BT».
6. Encaixe o cabo de volta no P1 e no PC.
7. Conte até cinco, devagar, olhando a fita.
8. Leia o chip com o plástico do P1: tem de ser P1 de novo, terminando em USB.
9. Clique na linha do P1 para abrir o cartão dele.
10. Confira que a «Bateria» mostra um número em porcento, e não um traço.
11. Encoste um dedo no touchpad do P1 e confira que o «Touchpad» conta o toque.
12. Gire o P1 na mão e confira que os números do «Giroscópio» saem do zero.
13. Empurre o analógico esquerdo do P1 e confira que os números andam no cartão.
14. Repita os passos 3 a 13 com o P2.
15. Confira, no fim, que a contagem voltou a «● 2 USB · 2 BT» e que os quatro têm os números do começo.

**Passa quando.** Depois de encaixar o cabo, o controle volta à fita em menos de cinco segundos, com o mesmo número de antes, e o cartão dele responde em TODOS os campos vivos: bateria com número, touchpad contando o toque, giroscópio saindo do zero e analógico andando. Meio controle não passa — se ele aparece mas a bateria fica em traço, ou o giroscópio não sai do zero, o teste reprovou.

**Por controle.**

* **P1** — USB, é o primeiro a sair e voltar. Desencaixe o cabo, encaixe de novo, e confira o cartão inteiro depois — não só o chip na fita.
* **P2** — USB, o segundo. Mesmo gesto, e um de cada vez: com os dois fora ao mesmo tempo você não sabe qual voltou primeiro nem qual ficou pela metade.
* **P3** — BT, testemunha. Não encoste nele. O chip dele não pode sumir da fita enquanto o do cabo sai e volta.
* **P4** — BT, testemunha. Mesma coisa. Se ele cair junto quando você mexe num do cabo, o achado não é da entrada do controle e sim de alguma coisa que derruba os quatro — anote a hora exata.

**A armadilha.** Meio controle é o defeito que este teste caça, e ele engana porque o chip APARECE. Quando um controle sobe pela metade, o Hefesto o lista e o cartão fica sem bateria, sem movimento e sem touchpad — e isso se lê como «a tela está lenta». Por isso os passos mandam MEXER no aparelho: touchpad, giroscópio e analógico, um a um. Segunda: enquanto o P1 está fora, os três que ficaram descem um número — o plástico do P2 aparece como P1, e assim por diante — e voltam ao número deles quando o P1 volta. Isso é o produto, não defeito; é por isso que os passos seguem o P1 pelo plástico. Terceira: se o controle não voltar de jeito nenhum, troque de entrada USB antes de reprovar — entrada fraca derruba controle do cabo.

---

## mapa-plataforma.probe-radio — Subir a probe (o controle EXISTIR para o sistema) · rádio

*Célula:* `plataforma.probe @ rádio`

**O que isto prova.** Prova que ligar o controle pelo rádio o faz nascer INTEIRO — e não apenas conectado: com bateria, movimento e touchpad respondendo.

**Onde olhar.** Na fita do topo, a linha que começa com «Selecionar:», onde cada controle é um chip no formato «P3 • <nome da cor do plástico> • BT»; e a contagem no canto de cima, à direita, no formato «● 2 USB · 2 BT». Na aba Controles, o quadro «Dispositivos conectados» e o cartão que abre ao clicar na linha de um controle: «Bateria» em porcento, «Touchpad», os dois analógicos, «Gatilhos» e os blocos «Giroscópio» e «Acelerômetro» com X, Y e Z. São bateria, touchpad e movimento que dizem se ele subiu inteiro.

**Os passos.**

1. Deixe o P1 e o P2 no cabo e não encoste neles durante o teste.
* Abra a aba Controles.
2. Anote o nome da cor do plástico de cada um dos quatro chips da fita.
3. Segure o botão PS do P3 até todas as luzes dele apagarem, e solte.
4. Conte até dez, devagar.
5. Confira que o chip com o plástico do P3 saiu da fita e que a contagem passou a «● 2 USB · 1 BT».
6. Dê um toque curto no botão PS do P3 para religá-lo.
7. Conte até cinco, devagar, olhando a fita.
8. Leia o chip com o plástico do P3: tem de ser P3 de novo, terminando em BT.
9. Clique na linha do P3 para abrir o cartão dele.
10. Confira que a «Bateria» mostra um número em porcento, e não um traço.
11. Encoste um dedo no touchpad do P3 e confira que o «Touchpad» conta o toque.
12. Gire o P3 na mão e confira que os números do «Giroscópio» saem do zero.
13. Empurre o analógico esquerdo do P3 e confira que os números andam no cartão.
14. Repita os passos 3 a 13 com o P4.
15. Confira, no fim, que a contagem voltou a «● 2 USB · 2 BT» e que os quatro têm os números do começo.

**Passa quando.** Depois do toque no PS, o controle volta à fita em poucos segundos com o mesmo número, e o cartão dele responde em TODOS os campos vivos: bateria com número, touchpad contando o toque, giroscópio saindo do zero e analógico andando. Aparecer na lista não basta — um controle listado sem bateria, sem touchpad e sem movimento é reprovação.

**Por controle.**

* **P1** — USB, testemunha. Não encoste nele; o chip dele não pode sumir enquanto os do rádio saem e voltam.
* **P2** — USB, testemunha. Mesma coisa.
* **P3** — BT, é o primeiro a sair e voltar. Segure o PS até apagar, religue com um toque curto, e confira o cartão inteiro depois.
* **P4** — BT, o segundo, e um de cada vez. Enquanto o P3 está fora ele aparece como P3 e volta a ser P4 quando o P3 volta. Se ele cair sozinho quando você desliga o P3, o achado não é da entrada do controle: confira em «Rádio e Adaptadores», na aba Conexões, se os dois dividem o mesmo adaptador, e anote.

**A armadilha.** É NO RÁDIO que o meio controle acontece de verdade, e a razão é do aparelho: pelo rádio o DualSense nasce MUDO — manda só o essencial até alguém lhe pedir uma informação de fábrica, e é esse pedido que o vira para o relatório completo, com movimento, touchpad e bateria dentro. Se o pedido falhar, o controle acende, pareia, entra na lista e fica sem nada disso. Então «ele conectou» não é resposta neste teste: as três conferências dos passos 10 a 12 é que são. E o pedido tem prazo curto: quando expira, a subida inteira é abandonada de uma vez, sem segunda tentativa do lado do sistema — o conserto é desligar e ligar o controle de novo, não esperar. Segunda: enquanto um controle do rádio está fora, os que vêm depois dele descem um número e voltam quando ele volta; siga-os pelo plástico. Terceira: um aperto solto no PS abre a Steam; se ela abrir, feche-a antes de seguir.

---

## mapa-plataforma.probe.retry-cabo — Retry de probe · cabo

*Célula:* `plataforma.probe.retry @ cabo`

**O que isto prova.** Prova que o Hefesto fica tentando sozinho até o controle do cabo entrar, e que ele entra inteiro mesmo depois de várias idas e voltas seguidas.

**Onde olhar.** Na fita do topo, os chips no formato «P1 • <nome da cor do plástico> • USB»; e a contagem no canto de cima, à direita, no formato «● 2 USB · 2 BT». Na aba Controles, o quadro «Dispositivos conectados» e o cartão que abre ao clicar na linha: «Bateria» em porcento, «Touchpad», os analógicos e os blocos «Giroscópio» e «Acelerômetro». E na aba Sistema, na faixa «Avançado», o botão «Ver detalhes», que põe no painel «Detalhes técnicos», ao lado, as últimas 80 linhas do registro, cada uma com o horário na frente.

**Os passos.**

1. Confira que os quatro estão ligados e que a contagem diz «● 2 USB · 2 BT».
* Abra a aba Controles.
2. Anote o nome da cor do plástico de cada chip da fita, e a hora no relógio.
3. Desencaixe o cabo do P1, conte até três, e encaixe de volta.
4. Repita esse desencaixa-e-encaixa mais quatro vezes no P1, sempre contando até três entre uma coisa e a outra.
5. Deixe o cabo encaixado na última vez.
6. Conte até dez, devagar.
7. Confira que o chip com o plástico do P1 está na fita, como P1.
8. Clique na linha do P1 e confira que o cartão responde: bateria com número, touchpad contando o toque e giroscópio saindo do zero.
9. Repita os passos 3 a 8 com o P2.
10. Abra a aba Sistema e desça até a faixa «Avançado».
11. Clique em «Ver detalhes» e leia as últimas linhas do registro.
12. Procure, pelo horário que você anotou, as linhas das idas e voltas do P1 e do P2, e anote se alguma delas fala de tentativa que falhou.

**Passa quando.** Depois de cinco idas e voltas seguidas, os dois controles do cabo estão de volta na fita com os mesmos números de antes, e os cartões deles respondem em todos os campos vivos. Nenhum dos dois ficou de fora e nenhum voltou pela metade.

**Por controle.**

* **P1** — USB, é o primeiro a apanhar: cinco idas e voltas, uma de cada vez, com três segundos entre elas. No fim, o cartão inteiro tem de responder.
* **P2** — USB, o segundo. Mesma sequência, e só depois de o P1 já ter assentado — os dois ao mesmo tempo não deixam saber qual demorou.
* **P3** — BT, testemunha. Não encoste nele; o chip dele não pode sumir enquanto o do cabo entra e sai cinco vezes.
* **P4** — BT, testemunha. Mesma coisa, e ele é o mais sensível: se as idas e voltas de um controle do cabo derrubarem o último do rádio, isso é o achado.

**A armadilha.** O Hefesto refaz a procura a cada cinco segundos, e ela ESPAÇA quando falha muitas vezes seguidas: depois de várias tentativas a espera entre uma e outra cresce, então um controle que demora quinze ou vinte segundos a voltar no fim de uma sequência longa não é defeito — é a espera crescida. Espere mais antes de reprovar, e anote quanto tempo levou. Duas coisas mais. Existem DUAS tentativas diferentes em jogo, e elas não se somam: a do Hefesto refaz a procura inteira a cada cinco segundos, e a do sistema tenta de novo um pedido de informação de fábrica dentro de uma única subida — confundir as duas faz procurar o número errado quando um controle não entra. E a cada saída do P1 os outros três descem um número e voltam quando ele volta; isso pisca na fita cinco vezes, e é o produto. Não faça as idas e voltas depressa demais: encaixar e desencaixar sem esperar maltrata o conector, e o que você mede passa a ser o seu gesto, não o produto. Não clique em «Restaurar de fábrica», que fica na mesma faixa «Avançado».

---

## mapa-plataforma.probe.retry-radio — Retry de probe · rádio

*Célula:* `plataforma.probe.retry @ rádio`

**O que isto prova.** Prova que um controle do rádio que não entra na primeira volta acaba entrando, e mostra o que fazer quando ele acende mas não aparece na lista.

**Onde olhar.** Na fita do topo, os chips no formato «P3 • <nome da cor do plástico> • BT»; e a contagem no canto de cima, à direita, no formato «● 2 USB · 2 BT». Na aba Controles, o cartão que abre ao clicar na linha de um controle: «Bateria» em porcento, «Touchpad», os analógicos e os blocos «Giroscópio» e «Acelerômetro». Na aba Jogar, o botão «Reconectar controles», embaixo dos cartões: desde 22/09 ele derruba o elo morto de um controle que o Bluetooth diz estar aqui e o Hefesto não vê, e diz numa frase o que fez. E na aba Sistema, na faixa «Avançado», o botão «Ver detalhes», que põe no painel «Detalhes técnicos» as últimas 80 linhas do registro, cada uma com o horário na frente.

**Os passos.**

1. Confira que os quatro estão ligados e que a contagem diz «● 2 USB · 2 BT».
* Abra a aba Controles.
2. Anote o nome da cor do plástico de cada chip da fita, e a hora no relógio.
3. Segure o botão PS do P3 até as luzes apagarem e solte.
4. Conte até cinco, devagar, com o P3 parado ao seu lado.
5. Dê um toque curto no botão PS do P3 para religá-lo.
6. Anote quantos segundos levou até o chip com o plástico dele voltar à fita.
7. Anote também se a barra de luz dele acendeu sem o chip aparecer.
8. Repita os passos 3 a 7 mais quatro vezes no P3, sempre esperando o chip voltar antes da volta seguinte.
9. Se em alguma volta ele acendeu e não apareceu em dez segundos, abra a aba Jogar, clique em «Reconectar controles», leia a frase e faça o que ela pedir; se nada mudar, desligue e ligue o P3 mais uma vez.
10. Clique na linha do P3, na aba Controles, e confira que o cartão responde: bateria com número, touchpad contando o toque e giroscópio saindo do zero.
11. Repita os passos 3 a 10 com o P4.
12. Abra a aba Sistema, desça até a faixa «Avançado» e clique em «Ver detalhes».
13. Leia as últimas linhas do registro pelo horário que você anotou e anote qualquer linha que fale de tentativa que falhou.

**Passa quando.** Nas cinco voltas, o controle do rádio termina de volta na fita, com o mesmo número, e o cartão dele responde em todos os campos vivos. Se em alguma volta ele acendeu sem aparecer na lista, o «Reconectar controles» ou um desligar e ligar resolveu — e isso ainda vale como passa, desde que você anote em quantas das cinco aconteceu e qual dos dois gestos resolveu.

**Por controle.**

* **P1** — USB, testemunha: chip na fita o tempo todo e o cartão respondendo no fim.
* **P2** — USB, testemunha. Mesma conferência.
* **P3** — BT, é o primeiro a apanhar: cinco voltas, uma de cada vez, esperando o chip reaparecer entre elas. Anote os segundos de cada volta.
* **P4** — BT, o segundo, e é o que mais costuma sofrer — ele é o último da fila e pode dividir o adaptador com o P3. Enquanto o P3 está fora, ele aparece como P3. Se ele precisar de mais voltas que o P3, anote o número de cada um: é a diferença entre os dois que interessa.

**A armadilha.** Aqui existe uma falha que NÃO se conserta esperando, e reconhecê-la é o ponto do teste. Pelo rádio, o pedido de informação de fábrica que o controle precisa responder para subir inteiro tem prazo de três segundos, e o sistema desta máquina faz UMA tentativa só por padrão. Se ela expira, a subida morre inteira: o controle fica aceso, pareado, e simplesmente não existe para o Hefesto. E o Hefesto refazendo a procura a cada cinco segundos não salva esse caso, porque não há o que procurar. O gesto que resolve é o «Reconectar controles», que derruba esse elo, ou desligar e ligar o controle de novo — ficar esperando não resolve, e é assim que se perde meia hora. Duas outras: conte os segundos a partir de quando você SOLTA o botão, não de quando aperta; e não religue depressa demais — deixe pelo menos cinco segundos desligado entre uma volta e a seguinte. E um aperto solto no PS abre a Steam; se ela abrir, feche-a. Não clique em «Restaurar de fábrica», que fica na mesma faixa «Avançado».

---

## mapa-plataforma.slot_jogador-cabo — Slot / número de jogador atribuído pelo Hefesto · cabo

*Célula:* `plataforma.slot_jogador @ cabo`

**O que isto prova.** Prova que o número de jogador dos dois controles do cabo pertence ao CONTROLE, e não à entrada USB em que ele está espetado.

**Onde olhar.** Três lugares, e eles têm de concordar. Na fita do topo, a linha que começa com «Selecionar:»: cada controle é um chip no formato «P1 • <nome da cor do plástico> • USB». Na aba Conexões, o quadro «Gestão de Controles» (abre pelo título), onde cada linha começa com «Sony • Player N» e termina em USB ou BT. E no aparelho: as cinco lampadinhas brancas embaixo do touchpad, que dizem o número pelo CONJUNTO aceso — jogador 1 é só a do meio; jogador 2 são a segunda e a quarta; jogador 3 são as duas das pontas e a do meio; jogador 4 são as quatro, com a do meio apagada.

**Os passos.**

1. Confira que os quatro estão ligados: os chips do P1 e do P2 terminando em USB, os do P3 e do P4 em BT.
2. Anote num papel o nome da cor do plástico e o número de cada um dos quatro, lidos na fita do topo.
3. Olhe as lampadinhas de cada um dos quatro aparelhos e confira que a figura bate com o número que a tela mostra.
4. Anote em qual entrada USB do PC está o cabo do P1.
5. Puxe o cabo do P1 de dentro do PC — do lado do PC, nunca do lado do controle.
6. Olhe a fita enquanto ele está fora e confira que cada um dos três que ficaram continua com o número que você anotou.
7. Encaixe esse mesmo cabo numa entrada USB DIFERENTE do PC, em menos de trinta segundos.
8. Conte até dez, devagar, olhando a fita do topo.
9. Leia o chip com o plástico do P1: tem de dizer P1 e terminar em USB.
10. Confira que os outros três continuam com os números que você anotou no passo 2.
11. Olhe as lampadinhas do P1 e confira que continuam no desenho do jogador 1.
12. Repita os passos 4 a 11 com o cabo do P2, levando-o para uma terceira entrada USB.
13. Abra a aba Conexões, clique no título «Gestão de Controles» e leia os quatro «Player N».
14. Olhe as lampadinhas dos quatro aparelhos uma última vez e compare com o que você anotou no papel.

**Passa quando.** Cada um dos dois controles do cabo volta com exatamente o mesmo número de jogador que tinha antes de trocar de entrada USB, na tela e nas lampadinhas do aparelho. Enquanto um cabo está fora, ninguém troca de número. No fim, os quatro têm os números do começo, e a contagem volta a «● 2 USB · 2 BT».

**Por controle.**

* **P1** — USB, e é o primeiro a mudar de entrada. Anote o número dele e a entrada USB antes de puxar o cabo. Tem de voltar como o mesmo jogador, com as mesmas lampadinhas acesas, numa entrada que ele nunca tinha visto.
* **P2** — USB, e é o segundo a mudar de entrada. Mesmo gesto, uma entrada ainda diferente. Faça um de cada vez: com os dois cabos fora ao mesmo tempo você não sabe qual dos dois causou o que aparecer.
* **P3** — BT, e é testemunha. Não encoste nele. O chip dele não pode sumir da fita, e ele continua P3 enquanto o P1 ou o P2 está fora.
* **P4** — BT, e é a segunda testemunha. Não encoste nele. Continua P4 o tempo todo; no fim, confira número e lampadinhas.

**A armadilha.** As cinco lampadinhas não se contam da esquerda para a direita — o número é o CONJUNTO aceso, e quem lê «a terceira lampadinha acesa» como jogador 3 reprova um produto que está certo. Segunda: o lugar de quem sai fica guardado por trinta segundos, contados de quando o chip dele some da fita; passado esse tempo, a fila se fecha de propósito e quem vem depois desce um número. Por isso cada troca de entrada tem de caber em trinta segundos. Terceira: o controle que volta recupera o número dele enquanto o serviço estiver de pé, demore o que demorar — o prazo decide só o que os outros mostram no meio. E há uma coisa que o mapa já declara e que muda o veredito: o DualSense NÃO SABE que número ele é. O número é invenção do Hefesto e não tem canal nenhum no aparelho; o que o aparelho mostra são as lampadinhas. Se a tela disser um número e as lampadinhas disserem outro, quem quebrou foi a metade que EXIBE, e é esse o achado a anotar.

---

## mapa-plataforma.slot_jogador-radio — Slot / número de jogador atribuído pelo Hefesto · rádio

*Célula:* `plataforma.slot_jogador @ rádio`

**O que isto prova.** Prova que o número de jogador dos dois controles do rádio segue o controle, e não a ordem em que ele voltou a ligar.

**Onde olhar.** Na fita do topo, a linha que começa com «Selecionar:», onde cada controle é um chip no formato «P3 • <nome da cor do plástico> • BT». Na aba Conexões, o quadro «Gestão de Controles» (abre pelo título), com «Sony • Player N» no começo de cada linha. A contagem no canto de cima, à direita, no formato «● 2 USB · 2 BT». E, nos aparelhos, as cinco lampadinhas brancas embaixo do touchpad: jogador 1 é só a do meio; jogador 2 são a segunda e a quarta; jogador 3 são as duas das pontas e a do meio; jogador 4 são as quatro, com a do meio apagada.

**Os passos.**

1. Confira que os quatro estão ligados: os chips do P1 e do P2 terminando em USB, os do P3 e do P4 em BT.
2. Anote num papel o nome da cor do plástico e o número de cada um dos quatro, lidos na fita do topo.
3. Olhe as lampadinhas dos quatro aparelhos e confira que a figura bate com o número da tela.
4. Segure o botão PS do P3 até todas as luzes dele apagarem.
5. Segure o botão PS do P4 até todas as luzes dele apagarem, logo em seguida.
6. Confira que a contagem passou a «● 2 USB» e que só os chips do P1 e do P2 ficaram na fita.
7. Dê um toque curto no botão PS do P4 — o QUARTO controle, e ele volta PRIMEIRO.
8. Conte até cinco, devagar, olhando a fita.
9. Leia o chip com o plástico do P4: com o P3 ainda fora, ele volta como P4 — o lugar do P3 continua guardado.
10. Dê um toque curto no botão PS do P3.
11. Conte até cinco, devagar.
12. Leia os dois chips: o do plástico do P3 tem de dizer P3, e o do plástico do P4 continua P4.
13. Olhe as lampadinhas do P3 e do P4 e confira que cada um está no desenho do próprio número.
14. Leia a contagem, de volta a «● 2 USB · 2 BT», e as quatro linhas de «Gestão de Controles».
15. Confira que o P1 e o P2 continuam com os números que você anotou no papel.

**Passa quando.** No fim, o P3 é o jogador 3 e o P4 é o jogador 4 — na tela e nas lampadinhas —, mesmo o P3 tendo sido o ÚLTIMO a religar. Se o P3 voltasse como jogador 4, o número estaria seguindo a ordem de chegada em vez de seguir o controle, e isso reprova. E os dois do cabo terminam com os números do começo.

**Por controle.**

* **P1** — USB, e é testemunha. Não encoste nele. Anote o número antes e confira depois: tem de ser o mesmo, com as mesmas lampadinhas.
* **P2** — USB, e é a segunda testemunha. Não encoste nele. Mesma conferência do P1.
* **P3** — BT, e é o que sai PRIMEIRO e volta POR ÚLTIMO. Segure o PS até apagar; depois, quando chegar a vez dele, um toque curto no PS. Tem de voltar como jogador 3, com as duas lampadinhas das pontas e a do meio acesas.
* **P4** — BT, e é o que sai POR ÚLTIMO e volta PRIMEIRO. É nele que o meio do teste se lê: mesmo com o P3 fora, ele volta como jogador 4, com as quatro lampadinhas acesas e a do meio apagada.

**A armadilha.** O prazo. O lugar do P3 fica guardado por trinta segundos, contados de quando o chip dele some da fita. Se passar disso entre desligar o P3 e religar o P4, o P4 volta como P3 até o P3 voltar — é a fila se fechando depois do prazo, não defeito; o que se julga é o FIM. Segunda: o controle que volta recupera o número dele enquanto o serviço estiver de pé, demore o que demorar. Terceira: as cinco lampadinhas não se contam da esquerda para a direita; o número é o conjunto aceso. Quarta: um aperto solto no PS abre a Steam; se ela abrir, feche-a. E o que o mapa já declara: o DualSense não sabe que número ele é — o número é do Hefesto e não tem canal nenhum no aparelho, e o que o aparelho mostra são as lampadinhas. Tela e lampadinhas discordando é a metade que EXIBE quebrada, e é isso que se anota.

---

## mapa-plataforma.taxa_relatorios-cabo — Taxa de relatórios de entrada · cabo

*Célula:* `plataforma.taxa_relatorios @ cabo`

**O que isto prova.** Prova que o Hefesto mostra, para cada controle do cabo, com que frequência o giroscópio dele está sendo entregue ao controle virtual que o jogo enxerga — e que pelo cabo esse número fica firme.

**Onde olhar.** Na aba Controles, no cabeçalho do cartão de cada controle — a linha com a cor do plástico e USB ou BT. Com o cartão ABERTO, ali aparece a frase «Giroscópio: fluindo para o jogo (~250 Hz)», com o número do momento, e ao lado dela os dois interruptores, «Giroscópio» e «Acelerômetro». A frase só aparece com o cartão aberto; o chip «Todos», no começo da fita do topo, abre os quatro de uma vez. Na aba Jogar, a linha «Status» diz Ligado ou Desligado, e o cartão de cada controle mostra a máscara escolhida para ele — DualSense, Xbox 360 ou Nintendo Pro.

**Os passos.**

1. Feche o jogo, se ele estiver aberto.
2. Abra a aba Jogar e confira que a linha «Status» está em «Ligado».
3. Confira, no cartão de cada um dos quatro, qual máscara está escolhida, e anote; não troque nenhuma.
4. Abra a aba Controles e clique no chip «Todos», no começo da fita do topo.
5. Leia a frase do P1 no cabeçalho do cartão dele e anote o número.
6. Conte até dez e leia o número do P1 de novo; anote o segundo valor embaixo do primeiro.
7. Leia o número do P2 e anote; conte até dez e leia de novo.
8. Anote também o que aparece no P3 e no P4, sem mexer em nenhum dos dois.
9. Pegue o P1 na mão e gire-o devagar de um lado para o outro por uns cinco segundos.
10. Leia o número do P1 outra vez e anote o terceiro valor.
11. Deixe o P1 parado, apoiado, por dez segundos e leia uma quarta vez.

**Passa quando.** Nos dois controles do cabo com a máscara DualSense, a frase aparece com um número, e o número fica firme perto de 250 nas quatro leituras — não vai a zero, não some e não pula para valores muito diferentes a cada olhada, nem com o controle girando, nem parado. Cada um dos quatro cartões mostra a SUA frase.

**Por controle.**

* **P1** — USB, e é o que você lê quatro vezes, girando e parado. Esperado: número firme, perto de 250.
* **P2** — USB, e é o segundo a ser lido, duas vezes. Mesmo esperado: firme, perto de 250. Se os dois do cabo derem números bem diferentes um do outro, anote os dois lado a lado — é aí que a diferença aparece.
* **P3** — BT, e é testemunha. Anote o número dele sem tocar em nada: ele é a comparação com a linha do rádio deste mesmo par.
* **P4** — BT, a segunda testemunha. Mesma coisa. Os quatro juntos mostram que cada cartão fala do controle virtual DELE, e não de um só para todos.

**A armadilha.** O número NÃO é a taxa do controle. Ele é a velocidade com que o Hefesto entrega o movimento ao controle virtual que o jogo vê, e essa entrega tem um TETO de 250 por segundo. Por isso 250 no cabo é o esperado e é também o teto: um controle que entregasse mais apareceria exatamente igual. Segunda: a frase muda de texto, e isso é o certo, em três casos. No Modo Nativo ela diz «Giroscópio: o jogo fala direto com o controle». Com a máscara Xbox 360 ela diz que essa API não leva giroscópio e que no Hefesto ele segue ativo. E com a máscara Nintendo Pro ela some — esse controle virtual não leva giroscópio nenhum. Confira o Status e a máscara que você anotou antes de reprovar por ausência. Terceira: o interruptor «Giroscópio» não é o instrumento desta linha — ele corta o giro no que vai ao jogo, e a frase mede a entrega do movimento, que segue; não o use para fazer a frase sumir. Quarta: nada aqui prova que o jogo usou aquele giro; o número mede a entrega ao controle virtual, e o mapa não registra medição do outro lado.

---

## mapa-plataforma.taxa_relatorios-radio — Taxa de relatórios de entrada · rádio

*Célula:* `plataforma.taxa_relatorios @ rádio`

**O que isto prova.** Prova que a mesma frase de entrega do giroscópio aparece nos dois controles do rádio — e revela que o número mostrado ali é o teto do Hefesto, não o que o aparelho entrega.

**Onde olhar.** Dois lugares, e é a comparação entre eles que mede. Primeiro, na aba Controles, o cabeçalho do cartão de cada controle, com o cartão ABERTO: a frase «Giroscópio: fluindo para o jogo (~250 Hz)» — o que o Hefesto ENTREGA ao controle virtual, com teto de 250. O chip «Todos», no começo da fita do topo, abre os quatro cartões de uma vez. Segundo, na aba Conexões, a seção «Rádio e Adaptadores», que abre pelo título: o ▶ de cada adaptador abre a lista dos controles que estão nele, e cada linha traz, ao lado do ícone de sinal, o movimento que CHEGA do controle agora, em Hz — esse número não tem teto. Na aba Jogar, a linha «Status» tem de estar em «Ligado».

**Os passos.**

1. Faça a linha do cabo deste mesmo par antes desta, e tenha à mão o papel com os números do P1 e do P2.
2. Feche o jogo, se ele estiver aberto.
3. Abra a aba Jogar, confira que a linha «Status» está em «Ligado» e anote a máscara escolhida no cartão do P3 e no do P4.
4. Abra a aba Controles e clique no chip «Todos», no começo da fita do topo.
5. Confira, no cabeçalho do cartão do P3, que depois da cor do plástico está escrito BT.
6. Leia a frase do P3 e anote o número; conte até dez e leia de novo; conte até dez e leia uma terceira vez.
7. Faça as três leituras também no P4, anotando os três valores.
8. Abra a aba Conexões, clique no título «Rádio e Adaptadores» e clique no ▶ de cada adaptador.
9. Ache a linha do P3 e a do P4 e anote o Hz de movimento de cada uma, três vezes, contando até dez entre as leituras.
10. Anote também se o P3 e o P4 estão no MESMO adaptador ou em adaptadores diferentes.
11. Ponha lado a lado, no papel, os números do cartão e os da lista do adaptador, para cada um dos dois.
12. Leve o P3 para o outro lado da sala, o mais longe do PC que der, e leia o Hz de movimento dele na lista; anote.
13. Traga o P3 de volta e leia mais uma vez.
14. Volte à aba Controles e confira que os números do P1 e do P2 não mudaram em nenhuma dessas leituras.

**Passa quando.** A frase aparece nos dois controles do rádio com a máscara DualSense, com um número, e não some enquanto eles estiverem ligados. O número do cartão nunca passa de 250, e o da lista do adaptador pode passar: se o cartão mostrar perto de 250 enquanto a lista mostra bem mais, isso não é você errando — é o teto achatando o que passava por cima, e é justamente o achado desta linha. Anote os números dos dois lugares lado a lado.

**Por controle.**

* **P1** — USB, e é testemunha. Não toque nele. O número dele no cartão tem de continuar firme enquanto você lê e passeia com os do rádio. Ele é a régua de comparação: sem o número dele no papel, o do rádio não diz nada.
* **P2** — USB, a segunda testemunha. Mesma coisa. Se o número do P1 ou do P2 se mexer quando você afasta o P3, anote — a distância de um não devia alcançar o outro.
* **P3** — BT, e é ESTE. Três leituras paradas no cartão e na lista, uma leitura longe do PC e uma de volta. Pelo rádio o movimento chega em rajadas, então oscilar entre leituras é o normal, não o defeito.
* **P4** — BT, o segundo. Três leituras paradas, sem sair do lugar. Ele mostra se a variação é do rádio inteiro ou só do controle que você afastou.

**A armadilha.** O teto é o mesmo nos dois transportes, e é ele que engana. O número do cartão é a entrega do Hefesto ao controle virtual, capada em 250 por segundo; o que chega do rádio pode passar disso. E o que chega não é uma taxa do controle: o adaptador tem um orçamento, repartido entre os controles que estão nele — medido nesta casa, um controle SOZINHO num adaptador chegou perto de 800 por segundo, e dois dividindo um adaptador ficaram perto de 400 cada. Por isso anote se o P3 e o P4 dividem o adaptador: é isso que explica boa parte da diferença entre eles. Segunda: número que oscila muito entre uma leitura e outra pelo rádio não é defeito. Terceira: a frase muda de texto, e isso é o certo, no Modo Nativo e com a máscara Xbox 360, e some com a máscara Nintendo Pro. Confira a máscara que você anotou antes de reprovar por ausência. Quarta: nada aqui prova que o jogo recebeu o giro nessa velocidade — o mapa não registra medição do lado do jogo.

---

## mapa-plataforma.transporte_radio-cabo — Transporte de rádio (tipo de link) · cabo

*Célula:* `plataforma.transporte_radio @ cabo`

**O que isto prova.** Prova que o Hefesto acerta, para os dois controles do cabo, por onde eles estão falando — e que a resposta não muda quando o cabo troca de entrada USB.

**Onde olhar.** Quatro lugares, e eles têm de concordar. Na fita do topo, a linha que começa com «Selecionar:»: cada chip termina em USB ou em BT. No canto de cima, à direita, a contagem, no formato «● 2 USB · 2 BT». Na aba Conexões, o quadro «Gestão de Controles» (abre pelo título): cada linha termina em USB ou em BT, e o canto do quadro diz «4 controles • 2 no cabo • 2 no rádio». E, na aba Controles, o cabeçalho do cartão de cada controle, onde, logo depois da cor do plástico, aparece de novo USB ou BT.

**Os passos.**

1. Confira que o P1 e o P2 estão no cabo e que o P3 e o P4 estão no rádio, sem cabo nenhum neles.
* Abra a aba Controles.
2. Anote o nome da cor do plástico de cada chip da fita e a palavra do fim de cada um.
3. Leia a contagem do canto de cima e anote.
4. Abra a aba Conexões, clique no título «Gestão de Controles» e leia as quatro linhas; anote se cada uma termina em USB ou em BT.
5. Confira que os lugares dizem a mesma coisa sobre cada um dos quatro.
6. Puxe o cabo do P1 de dentro do PC — do lado do PC, nunca do lado do controle.
7. Encaixe-o numa entrada USB diferente do PC, sem demorar.
8. Conte até dez, devagar.
9. Leia o chip com o plástico do P1: tem de ser P1 de novo e terminar em USB, nunca em BT.
10. Leia a contagem do canto: tem de continuar «● 2 USB · 2 BT».
11. Repita os passos 6 a 10 com o cabo do P2, numa terceira entrada USB.
12. Olhe os chips do P3 e do P4 e confira que os dois continuaram terminando em BT o tempo todo.

**Passa quando.** Os dois controles do cabo dizem USB em todos os lugares, antes e depois de trocar de entrada, e a contagem volta a «● 2 USB · 2 BT». Os dois do rádio nunca trocam de palavra, nem enquanto os cabos estão fora.

**Por controle.**

* **P1** — USB, e é o primeiro a mudar de entrada. Tem de dizer USB em todos os lugares antes e depois, e não pode passar por BT no meio do caminho.
* **P2** — USB, o segundo a mudar de entrada. Mesma conferência. Faça um de cada vez: com os dois fora ao mesmo tempo a contagem muda por dois motivos e você não separa qual foi.
* **P3** — BT, testemunha. Não encoste nele. A palavra do chip dele tem de continuar BT enquanto os cabos vão e vêm. Se ela virar USB sem ninguém encostar, a leitura pegou o controle errado. Enquanto o P1 está fora, ele aparece como P2 por um instante — isso é o número, não a palavra.
* **P4** — BT, a segunda testemunha. Mesma conferência do P3. Os dois juntos provam que mexer no cabo de um não reescreve o transporte de quem está sem fio.

**A armadilha.** A que o mapa declara: o Hefesto decide isto pelo TAMANHO do que o controle manda e pela entrada que o sistema mostra, e nenhum dos dois separa cabo de DADO de cabo de SÓ CARGA. Se você usar um cabo de carregador que não passa dado, o controle continua dizendo BT com o cabo espetado — e isso está CERTO, porque a entrada dele continua chegando pelo rádio; o que a tela não conta é que ele está carregando. Não reprove: troque por um cabo de dado e refaça. Segunda: enquanto um cabo está fora, os controles que vêm depois dele descem um número e voltam quando ele volta — siga-os pelo plástico, e julgue a PALAVRA do fim do chip, não o número. Terceira: puxe o cabo do lado do PC; mexer no encaixe do controle o derruba à toa.

---

## mapa-plataforma.transporte_radio-radio — Transporte de rádio (tipo de link) · rádio

*Célula:* `plataforma.transporte_radio @ rádio`

**O que isto prova.** Prova que os dois controles do rádio são lidos como BT, e que espetar um cabo de dado num deles vira a resposta para USB — e ela volta para BT quando o cabo sai.

**Onde olhar.** Na fita do topo, a linha que começa com «Selecionar:»: cada chip termina em USB ou em BT. No canto de cima, à direita, a contagem, no formato «● 2 USB · 2 BT». Na aba Conexões, o quadro «Gestão de Controles» (abre pelo título), onde cada linha termina em USB ou em BT. E, na aba Controles, o cabeçalho do cartão de cada controle, com USB ou BT logo depois da cor do plástico.

**Os passos.**

1. Confira que o P3 e o P4 estão no rádio, sem cabo nenhum espetado neles.
2. Abra a aba Controles.
3. Anote o nome da cor do plástico de cada chip da fita e a palavra do fim de cada um.
4. Leia a contagem do canto de cima e anote.
5. Separe um cabo que você sabe que passa dado — um igual ao que o P1 está usando serve.
6. Espete esse cabo no P3 e depois no PC.
7. Conte até dez, devagar, olhando a fita.
8. Leia o chip com o plástico do P3: tem de ter virado USB, ainda como P3.
9. Leia a contagem do canto: tem de dizer «● 3 USB · 1 BT».
10. Olhe o chip do P4 e confirme que ele continua terminando em BT.
11. Puxe o cabo do P3 de dentro do PC.
12. Conte até dez, devagar; se o chip dele não voltar sozinho, dê um toque curto no botão PS do P3.
13. Leia o chip com o plástico do P3 de novo: tem de ter voltado a BT, e como P3.
14. Leia a contagem: tem de voltar a «● 2 USB · 2 BT».
15. Confira que os chips do P1 e do P2 terminaram em USB do começo ao fim.

**Passa quando.** O P3 vira USB em menos de dez segundos com o cabo de dado espetado, e volta a dizer BT quando o cabo sai — com o mesmo número de jogador nas duas pontas. O P4 diz BT o tempo inteiro, e o P1 e o P2 dizem USB o tempo inteiro. A contagem do canto acompanha as duas viradas.

**Por controle.**

* **P1** — USB, testemunha. Não encoste nele. Tem de dizer USB do começo ao fim, e a contagem só pode mudar por causa do P3.
* **P2** — USB, a segunda testemunha. Mesma conferência do P1.
* **P3** — BT, e é ESTE. Recebe o cabo de dado, tem de virar USB, e tem de voltar a BT quando o cabo sai. Confira também o número dele nas duas pontas — a palavra pode mudar, o número não.
* **P4** — BT, e é a testemunha que mais importa: ele está no mesmo tipo de conexão do P3. Se ele também virar USB quando você espeta o cabo no P3, a leitura pegou o rádio inteiro em vez do controle escolhido, e é esse o achado. Se o P3 sumir da fita por um instante na troca, o P4 aparece como P3 até ele voltar — isso é o número, não a palavra.

**A armadilha.** O cabo errado inventa um defeito. O Hefesto decide isto pelo TAMANHO do que o controle manda e pela entrada que o sistema mostra, e nenhum dos dois separa cabo de DADO de cabo de SÓ CARGA: com um cabo de carregador o P3 continua dizendo BT, espetado e carregando — e isso está CERTO, porque a entrada dele continua vindo pelo rádio. Se der isso, troque de cabo antes de anotar qualquer coisa. Segunda: espetar e tirar o cabo pode derrubar o P3 do rádio por um instante; se o chip dele sumir e voltar, isso sozinho não reprova — o que reprova é ele voltar com OUTRO número depois que tudo assentou. Não há prazo para essa volta: o controle recupera o número dele demore o que demorar. Terceira: um aperto solto no PS abre a Steam; se ela abrir, feche-a.

---

## mapa-plataforma.udev_autosuspend-cabo — Regra udev — o controle nunca dorme no barramento USB · cabo

*Célula:* `plataforma.udev_autosuspend @ cabo`

**O que isto prova.** Prova que o sistema está proibido de pôr as entradas USB para dormir — que é o que faz um controle no cabo cair sozinho, sem aviso, no meio do jogo.

**Onde olhar.** Na aba Conexões, no quadro «Check-up», que abre pelo título. Cada linha tem um selo ao lado (CERTO, AJUSTAR ou NOTA) e uma frase com o que se achou. A das entradas diz, no certo, «Nenhuma das N portas USB está em economia de energia.» — N é QUANTAS entradas foram olhadas, não quais. A linha vizinha, «O sistema está proibido de desligar o rádio dos controles.», é OUTRA coisa: ela fala do adaptador do rádio, não das entradas do cabo. As duas se refazem sozinhas a cada instante; o botão «Examinar Entradas», no pé da seção «Rádio e Adaptadores», refaz o exame inteiro.

**Os passos.**

1. Confira que o P1 e o P2 estão ligados pelo cabo, cada um na sua entrada USB.
2. Abra a aba Conexões e clique no título «Check-up».
3. Ache a linha das portas USB e anote o selo e a frase inteira, com o número de portas que ela cita.
4. Puxe os dois cabos de dentro do PC.
5. Conte até cinco e leia a mesma linha de novo; anote o novo número de portas.
6. Compare os dois números: o segundo tem de ser menor que o primeiro, em duas.
7. Encaixe os dois cabos de volta, cada um na entrada de onde saiu.
8. Conte até cinco e confira que o número voltou ao do passo 3 e que o selo continua o mesmo.
9. Se algum número não mexeu, clique em «Examinar Entradas», no pé de «Rádio e Adaptadores», e leia de novo.
10. Leia também a linha do rádio dos controles, no mesmo quadro, e anote o selo e a frase dela.

**Passa quando.** Com os dois cabos espetados, a linha das portas traz o selo CERTO e diz que NENHUMA das portas USB está em economia de energia. E o número de portas cai em duas quando você tira os dois cabos e sobe de volta quando você os devolve — é essa mexida no número que prova que os dois controles estavam entre as portas contadas.

**Por controle.**

* **P1** — USB, e é uma das portas contadas. Tire e devolva o cabo dele e veja o número da frase mexer. Se o número não mexer com nenhum dos dois, esta linha não está olhando os seus controles.
* **P2** — USB, a outra porta contada. Mesmo gesto. Tirando os dois juntos, a queda tem de ser de duas, não de uma.
* **P3** — BT, e ele NÃO entra nesta linha — de propósito. Sem cabo, o controle não está no barramento USB e não há entrada dele para pôr para dormir. Quem responde por ele é a linha do rádio dos controles, que fala do adaptador: leia o selo dela e anote.
* **P4** — BT, igual ao P3. Não entra nesta linha, e é coberto pela mesma linha do adaptador. Se o selo dela não estiver em CERTO, anote a frase inteira e a do `?` ao lado — elas dizem o que falta e o que fazer.

**A espera.** São vinte minutos, e nenhum deles é para ficar olhando a tela. Depois de conferir a linha e devolver os dois cabos, deixe o P1 e o P2 espetados e PARADOS, apoiados, sem tocar em nenhum dos dois — é ficar parado que faz uma entrada adormecida derrubar o controle. Marque um alarme de vinte minutos e vá fazer as outras linhas desta leva; não desencaixe nada nesse tempo. Quando o alarme tocar, volte à fita do topo: os dois chips têm de continuar lá, terminando em USB, com os mesmos números. Mexa então no analógico de cada um e confira que os dois respondem. Se algum tiver caído sozinho enquanto estava parado, anote a hora — é esse o defeito que esta linha existe para pegar.

**A armadilha.** A frase conta QUANTAS portas, nunca QUAIS. Um CERTO com os dois cabos fora não diz coisa nenhuma sobre os seus controles — é exatamente por isso que o exame se faz com eles espetados, e é por isso que este teste tira e devolve os cabos: para ver o número mexer. Segunda: o selo tem três palavras, e NOTA não é passa nem reprova — na linha das portas ela quer dizer que este sistema não deixou ler o estado delas. Anote e não conte como verde. Terceira: não misture as duas linhas do quadro. A do rádio dos controles pode dizer que a regra está no lugar mas o adaptador só a recebe no próximo encaixe — isso é verdade sobre o rádio e não tem nada a ver com esta linha. Quarta: se você trocou cabos de entrada em algum teste anterior, o número de portas já pode ter mudado por causa disso; leia o número de novo antes de comparar.

---

## mapa-plataforma.vigia_zumbi-cabo — Vigia de zumbi (link de pé e controle mudo) · cabo

*Célula:* `plataforma.vigia_zumbi @ cabo`

**O que isto prova.** Prova que um controle do cabo nunca fica na tela sem responder: se o caminho por onde ele fala envelhecer, o Hefesto o troca sozinho em poucos segundos.

**Onde olhar.** Duas coisas ao mesmo tempo, e é o par delas que decide. Primeira, o chip do controle na fita do topo — ele dizendo que o controle está conectado. Segunda, na aba Controles com o cartão daquele controle aberto, o bloco «Analógico esquerdo», com o pontinho que anda e os números X e Y quando você mexe no analógico do aparelho, e o desenho do botão, que acende quando você o aperta. Controle são é chip na fita e cartão respondendo; o que se caça é o par errado — chip na fita e cartão mudo. A troca em si não tem campo na tela: o que se enxerga é o resultado, o cartão voltando a responder.

**Os passos.**

* Abra a aba Controles.
1. Clique na linha do P1 para abrir o cartão dele.
2. Mexa no analógico esquerdo do P1 e confirme que o pontinho anda e os números X e Y mudam.
3. Aperte o botão Círculo do P1 e confirme que o desenho dele acende.
4. Puxe o cabo do P1 de dentro do PC.
5. Encaixe-o de volta na mesma entrada, sem demorar.
6. Repita o par tirar-e-pôr mais quatro vezes seguidas, contando até três entre uma e outra.
7. Espere o chip com o plástico do P1 reaparecer na fita do topo, como P1.
8. Clique na linha do P1 se o cartão tiver fechado, mexa no analógico esquerdo e conte até cinco olhando o pontinho.
9. Aperte o Círculo do P1 e confira que o desenho acende.
10. Faça os passos 1 a 9 no P2.
11. Mexa no analógico do P3 e no do P4, um de cada vez, com o cartão de cada um aberto, e confirme que os dois continuam respondendo.

**Passa quando.** Depois de cada vaivém do cabo, o controle volta à fita E volta a responder — o pontinho anda e o botão acende — em poucos segundos, sem você fechar nem reabrir nada. O que reprova é o par errado: o chip do controle na fita, dizendo que ele está lá, e o cartão mudo, sem pontinho andando e sem botão aceso, por mais de dez segundos.

**Por controle.**

* **P1** — USB, e é o primeiro a levar o vaivém. Cinco vezes tirando e pondo o cabo, e no fim o pontinho e o botão têm de voltar. Se ele voltar à fita e ficar mudo, anote a hora exata.
* **P2** — USB, o segundo. Mesmo gesto. Faça um de cada vez: os dois cabos indo e vindo juntos escondem de qual dos dois veio o problema.
* **P3** — BT, testemunha. Não encoste nele durante os vaivéns. O chip dele não pode sumir da fita, e ele tem de continuar respondendo no cartão. Enquanto o P1 está fora ele aparece como P2 por um instante — isso é o número, não queda.
* **P4** — BT, a segunda testemunha. Igual ao P3. Se os dois do rádio ficarem mudos junto com o vaivém do cabo, o estrago atravessou de um transporte para o outro, e é esse o achado.

**A armadilha.** Este teste passar no cabo NÃO diz nada sobre o rádio, e o mapa já explica por quê: pelo rádio existe, dentro do controle, um contador de vida que fica congelado. Uma checagem construída sobre ele funcionaria perfeitamente no cabo e seria CEGA no rádio — a pior forma de defeito, porque passa em todo teste feito com o cabo espetado. Verde aqui obriga a fazer a linha do rádio deste mesmo par. Segunda: a troca acontece em passadas de dois em dois segundos, então julgar no primeiro segundo dá vermelho falso — conte até cinco antes de decidir. Terceira: sumir da fita e voltar não é reprovação; uma queda honesta é o produto dizendo a verdade. O que reprova é ficar na fita e emudecer. Quarta: nada disto foi medido no aparelho até hoje — o mapa registra a leitura como achado de fonte, não como bancada. O seu resultado aqui vale mais que o que está escrito lá.

---

## mapa-plataforma.vigia_zumbi-radio — Vigia de zumbi (link de pé e controle mudo) · rádio

*Célula:* `plataforma.vigia_zumbi @ rádio`

**O que isto prova.** Prova que um controle do rádio nunca fica na tela sem responder — e é aqui que esse defeito se esconde, porque nenhum teste feito com o cabo o alcança.

**Onde olhar.** Duas coisas ao mesmo tempo, e é o par delas que decide. Primeira, o chip do controle na fita do topo, dizendo que ele está conectado. Segunda, na aba Controles com o cartão daquele controle aberto, o bloco «Analógico esquerdo», com o pontinho que anda e os números X e Y quando você mexe no analógico do aparelho, e o desenho do botão, que acende quando você o aperta. Controle são é chip na fita e cartão respondendo; o que se caça é o par errado — chip na fita e cartão mudo. A troca em si não tem campo na tela: o que se enxerga é o resultado, o cartão voltando a responder.

**Os passos.**

* Abra a aba Controles.
1. Clique na linha do P3 para abrir o cartão dele.
2. Mexa no analógico esquerdo do P3 e aperte o botão Círculo dele.
3. Confira que o pontinho anda e que o desenho do botão acende.
4. Segure o botão PS do P3 até todas as luzes dele apagarem.
5. Dê um toque curto no mesmo botão para religá-lo.
6. Quando o chip com o plástico dele voltar à fita, abra o cartão dele, mexa no analógico e conte até cinco: o pontinho tem de voltar a andar dentro desse tempo.
7. Repita os passos 4 a 6 mais duas vezes, uma atrás da outra.
8. Leve o P3 ligado para o cômodo ao lado, feche a porta, conte até vinte longe da tela e volte com ele.
9. Confira na fita do topo qual das três coisas aconteceu — o chip dele saiu, saiu e voltou, ou ficou lá o tempo todo — e anote.
10. Mexa no analógico do P3 e conte até dez olhando o pontinho: ele tem de voltar a andar dentro desse tempo.
11. Faça no P4 as três voltas de desligar e religar, com a mesma conferência do analógico, sem sair do lugar.
12. Mexa nos analógicos do P1 e do P2, um de cada vez, e confira que os dois continuam respondendo.

**Passa quando.** Depois de cada volta — do desligar e religar, e do passeio até o outro cômodo — o P3 e o P4 voltam a responder no cartão em poucos segundos. O que reprova é o par errado: o chip do controle na fita, dizendo que ele está lá, e o pontinho parado com o botão apagado por mais de dez segundos. Sumir da fita e voltar não reprova.

**Por controle.**

* **P1** — USB, testemunha. Não encoste nele. Tem de continuar respondendo no cartão enquanto os do rádio saem e voltam, e o chip dele não pode piscar para fora da fita.
* **P2** — USB, a segunda testemunha. Igual ao P1.
* **P3** — BT, e é ESTE. Três voltas de desligar e religar, mais o passeio até o outro cômodo. É nele que o defeito desta linha se esconde: um P3 que fica na fita sem responder é exatamente o que ninguém enxergaria com o cabo espetado.
* **P4** — BT, o segundo. Três voltas de desligar e religar, sem sair do lugar. Ele separa o que é do rádio inteiro do que é só do controle que você afastou. Enquanto o P3 está fora, ele aparece como P3 — isso é o número, não queda.

**A armadilha.** É AQUI que o defeito mora, e o mapa diz por quê: pelo rádio existe, dentro do controle, um contador de vida que fica congelado, e uma checagem construída sobre ele passa sempre no cabo e não enxerga nada no rádio. Então um P3 que fique na fita e não responda é o achado inteiro desta leva — anote a hora exata. Segunda: sair da fita ao ir para o outro cômodo é o CERTO, e não defeito; o que se caça é o contrário, o chip que fica e o controle que emudece. Terceira: a troca acontece em passadas de dois em dois segundos; conte até cinco antes de decidir, ou você dá vermelho no seu próprio relógio. Quarta: o controle que ACENDE e não entra na fita é outro defeito, com outro vigia — o do elo de rádio que ficou de pé sem controle nenhum; esse o Hefesto derruba sozinho depois de uns vinte segundos. Se acontecer, anote e desligue e ligue o controle de novo, mas não conte como reprovação desta linha. Quinta: nada disto foi medido no aparelho até hoje — o mapa registra a leitura como achado de fonte, e o seu resultado aqui é a primeira medição que esta casa vai ter.

---

## mapa-plataforma.vpad-cabo — Gamepad virtual (vpad) que o Hefesto cria · cabo

*Célula:* `plataforma.vpad @ cabo`

**O que isto prova.** Prova que o Hefesto cria um controle virtual para cada um dos dois controles do cabo, e que cada aparelho está preso ao controle virtual certo.

**Onde olhar.** Na aba Controles. Pare o ponteiro sobre o NOME do controle, no cabeçalho do cartão dele — a parte com a cor do plástico e USB ou BT. Aparece uma dica dizendo «Alimenta o gamepad virtual do Jogador N», com um endereço entre parênteses que começa pelo jeito como o controle virtual foi feito, «uhid» ou «uinput»; às vezes ela acrescenta com que nome ele aparece no sistema. Quando o controle ainda não tem controle virtual, a dica diz «Este controle ainda não alimenta gamepad virtual nenhum.». Ao lado do nome fica a máscara — DualSense, Xbox 360 ou Nintendo Pro —, que é o desenho de botões que o jogo vê; ela se escolhe no cartão de cada controle, na aba Jogar. Na aba Jogar, a linha «Status» diz Ligado ou Desligado.

**Os passos.**

1. Feche o jogo, se ele estiver aberto.
2. Abra a aba Jogar e confira que a linha «Status» está em «Ligado» — em Desligado não existe controle virtual nenhum e este teste não roda.
3. Anote a máscara escolhida no cartão de cada um dos quatro; não troque nenhuma.
4. Saia da aba Jogar e abra a aba Controles.
5. Pare o ponteiro sobre o nome do P1, no cabeçalho do cartão dele, e espere a dica aparecer.
6. Anote de qual jogador é o controle virtual que o P1 alimenta e a primeira palavra entre parênteses.
7. Faça o mesmo no nome do P2 e anote.
8. Compare as duas: têm de nomear jogadores DIFERENTES.
9. Faça o mesmo nos nomes do P3 e do P4 e anote as duas dicas.
10. Confira que as quatro dicas nomeiam quatro jogadores diferentes, sem nenhum repetido.
11. Confira que cada controle com a máscara DualSense tem «uhid» entre parênteses.

**Passa quando.** Cada um dos dois controles do cabo tem uma dica dizendo que alimenta o controle virtual de um jogador, e os dois jogadores são diferentes. Nenhum dos dois diz «ainda não alimenta gamepad virtual nenhum», e, com a máscara DualSense, os dois trazem «uhid» entre parênteses.

**Por controle.**

* **P1** — USB. A dica dele tem de nomear um controle virtual, com jogador. Anote o número do jogador e o endereço entre parênteses — é esse par que diz a qual controle virtual o aparelho na sua mão está preso.
* **P2** — USB. Mesma leitura, e o jogador tem de ser OUTRO. Dois controles nomeando o mesmo jogador é o defeito que este teste caça, e ele deixaria dois aparelhos empurrando o mesmo boneco.
* **P3** — BT, testemunha. A dica dele também tem de nomear um controle virtual — pelo rádio o Hefesto cria um igualzinho, sem diferença nenhuma. O que reprova aqui é ele repetir o jogador de alguém.
* **P4** — BT, a segunda testemunha. Igual ao P3. Se os quatro nomearem quatro jogadores diferentes, a amarração está certa; se dois se repetirem, anote quais dois e por qual conexão cada um estava.

**A armadilha.** A prova desta linha parou em MONTOU — o mapa registra que o controle virtual é CRIADO, e nada além disso. Então não julgue este teste dentro de um jogo: o que se prova aqui é que ele existe e está preso ao aparelho certo, não que o jogo reagiu. Segunda: a primeira palavra entre parênteses é a única pista, na tela, de que a emulação saiu no modo simples: com a máscara DualSense o esperado é «uhid»; «uinput» ali quer dizer que ele caiu para o modo simples, e isso se anota. Com as máscaras Xbox 360 e Nintendo Pro, «uinput» é o certo. Terceira: a dica SOME quando não há nada a dizer, e sumiço não é a mesma coisa que «ainda não alimenta gamepad virtual nenhum» — anote qual das duas você viu. Quarta, e é a que quebra o jogo: trocar a máscara DESTRÓI e RECRIA o controle virtual na hora, e com o jogo aberto isso o deixa sem controle, e ele pode precisar ser reaberto. Não troque máscara durante este teste, e nunca com jogo aberto.

---

## mapa-plataforma.vpad-radio — Gamepad virtual (vpad) que o Hefesto cria · rádio

*Célula:* `plataforma.vpad @ rádio`

**O que isto prova.** Prova que os dois controles do rádio também ganham cada um o seu controle virtual — e que esse controle virtual nasce sempre com cara de cabo, mesmo com o aparelho sem fio.

**Onde olhar.** Na aba Controles. Pare o ponteiro sobre o NOME do controle, no cabeçalho do cartão dele — a parte com a cor do plástico e USB ou BT. A dica diz «Alimenta o gamepad virtual do Jogador N», com um endereço entre parênteses que começa por «uhid» ou «uinput», e às vezes acrescenta com que nome ele aparece no sistema; quando não há nenhum, ela diz «Este controle ainda não alimenta gamepad virtual nenhum.». Ao lado do nome fica a máscara — DualSense, Xbox 360 ou Nintendo Pro —, escolhida no cartão de cada controle, na aba Jogar. Na aba Jogar, a linha «Status». Para saber se o JOGO enxerga o controle virtual como de cabo ou de rádio, não há onde ler dentro do Hefesto: o lugar mais próximo é a lista de controles da Steam, e se ela não disser por onde cada um está ligado, anote que não deu para ler.

**Os passos.**

1. Feche o jogo, se ele estiver aberto.
2. Abra a aba Jogar, confira que a linha «Status» está em «Ligado» e anote a máscara escolhida no cartão de cada um dos quatro.
3. Saia da aba Jogar e abra a aba Controles.
4. Confira, no cabeçalho do cartão do P3, que depois da cor do plástico está escrito BT.
5. Pare o ponteiro sobre o nome do P3 e espere a dica aparecer.
6. Anote de qual jogador é o controle virtual dele, a primeira palavra entre parênteses e, se a dica trouxer, o nome com que ele aparece no sistema.
7. Faça o mesmo no P4 e anote.
8. Compare as duas dicas: têm de nomear jogadores diferentes entre si, e diferentes dos do P1 e do P2.
9. Segure o botão PS do P3 até as luzes apagarem.
10. Dê um toque curto no PS do P3 para religá-lo e espere o chip com o plástico dele voltar à fita, como P3.
11. Pare o ponteiro sobre o nome do P3 de novo e confira que a dica voltou a nomear um controle virtual, do mesmo jogador de antes.
12. Pare o ponteiro sobre o nome do P4 e confira que ele voltou a ser o jogador de antes.
13. Abra a lista de controles da Steam, se ela estiver instalada, confira que ela lista só os quatro controles virtuais, um por jogador e nenhum a mais, e anote o que ela diz sobre a conexão de cada um.

**Passa quando.** Os dois controles do rádio alimentam cada um o seu controle virtual, com jogadores diferentes entre si e diferentes dos dois do cabo, e nenhum dos dois diz «ainda não alimenta gamepad virtual nenhum». Depois de desligar e religar o P3, a dica dele volta a nomear o controle virtual do mesmo jogador, e o P4 volta ao dele. Na lista da Steam aparecem os quatro controles virtuais e nenhum DualSense a mais.

**Por controle.**

* **P1** — USB, testemunha. Não encoste nele. A dica dele não pode trocar de jogador enquanto você mexe nos do rádio — se trocar, a mexida num controle reescreveu a amarração de outro.
* **P2** — USB, a segunda testemunha. Mesma conferência do P1.
* **P3** — BT, e é ESTE. Leia a dica dele, desligue-o e religue-o pelo PS, e leia a dica de novo. O jogador que ele alimenta tem de ser o mesmo antes e depois; o endereço entre parênteses pode mudar, porque o controle virtual nasce de novo.
* **P4** — BT, o segundo. Leia a dica dele antes e depois da volta do P3. Enquanto o P3 está fora, o P4 aparece como Jogador 3 — a numeração não deixa buraco, e isso não reprova. O que reprova é ele perder a dica, ou não voltar ao jogador dele quando o P3 volta.

**A armadilha.** O controle virtual NASCE SEMPRE COMO SE FOSSE DE CABO, mesmo com o aparelho no rádio — é de propósito, e é justamente isso que faz o jogo funcionar. Então, se a lista da Steam mostrar os controles virtuais como de cabo, isso está CERTO e não é defeito: quem está no rádio é o aparelho na sua mão, não o controle que o jogo enxerga. Segunda: a lista da Steam não mostra mais os próprios DualSense — desde 24/09 o Hefesto esconde os DualSense de verdade de todo programa menos ele — o botão, o toque e o movimento, além do que já escondia —, e só o Modo Nativo os devolve. Se ela mostrar um quinto controle, confira antes na aba Jogar que a linha «Status» está em «Ligado»; ligado e com cinco, o aparelho escapou do esconderijo, e isso é o achado desta linha: anote o nome com que ele aparece. Terceira: a prova desta linha parou em MONTOU — o mapa registra que o controle virtual é criado, e nada além; não julgue este teste dentro de um jogo. Quarta: não há prazo para a volta — o controle recupera o número dele demore o que demorar. Quinta: trocar a máscara destrói e recria o controle virtual na hora; não faça isso durante este teste, e nunca com o jogo aberto. Sexta: a dica some quando não há nada a dizer, e sumiço não é o mesmo que a frase «ainda não alimenta gamepad virtual nenhum» — anote qual das duas você viu. E um aperto solto no PS abre a Steam; se ela abrir sem você pedir, feche-a antes do passo 13.

---

# toque

---

## mapa-toque.touchpad-cabo — Touchpad — os pontos de toque · cabo

*Célula:* `toque.touchpad @ cabo`

**O que isto prova.** Prova que, num controle ligado por cabo, o Hefesto enxerga o dedo no touchpad: a palavra muda e o pontinho acende no lugar onde o dedo está — e só no cartão daquele controle. E prova isso com o touchpad ESCONDIDO: desde 24/09 os nós do aparelho ficam fechados para todo programa menos o Hefesto, que os lê por uma porta própria, e é esta célula que acusa se essa porta falhar e o cartão ficar cego.

**Onde olhar.** Na aba Controles. Clique no chip «Todos» da fita do topo para abrir os quatro cartões. Dentro de cada cartão, no canto de cima à esquerda, tem a moldura Touchpad: na mesma linha do rótulo vem a palavra do estado — «Sem toque», «1 toque», «2 toques» ou um travessão — e, embaixo dela, um retângulo escuro onde cada dedo é um pontinho ciano. O pontinho só aparece enquanto há dedo na superfície, e fica na POSIÇÃO do dedo: canto de cima à esquerda do retângulo é canto de cima à esquerda do touchpad. Com os quatro cartões abertos a caixa rola — role para ver os quatro. O travessão quer dizer «não consegui ler», e não é nem «Sem toque» nem «1 toque». Na fita do topo, cada controle é um chip com o número, a cor do plástico e a palavra do transporte: USB para o cabo, BT para o rádio.

**Os passos.**

1. Abra o Hefesto e clique na aba Controles.
2. Clique no chip «Todos» da fita do topo, para abrir os quatro cartões.
3. Confira na fita que o P1 e o P2 dizem USB, e que o P3 e o P4 dizem BT.
4. Tire as mãos dos quatro controles e deixe-os parados na mesa.
5. Confira que os quatro cartões dizem «Sem toque» no Touchpad, sem pontinho aceso.
6. Encoste UM dedo, de leve, no canto de cima à esquerda do touchpad do P1, e mantenha-o lá.
7. Confira no cartão do P1 que a palavra virou «1 toque» e que o pontinho acendeu perto do canto de cima à esquerda do retângulo.
8. Confira que os cartões do P2, do P3 e do P4 continuam em «Sem toque», sem pontinho, com o seu dedo ainda no P1.
9. Arraste o dedo devagar pelo touchpad do P1 até o canto de baixo à direita, sem tirá-lo da superfície.
10. Confira que o pontinho do P1 andou junto, na mesma direção do dedo.
11. Tire o dedo do P1.
12. Confira que a palavra voltou a «Sem toque» e que o pontinho apagou.
13. Faça no P2 a mesma volta — dedo no canto de cima à esquerda, arrasto até o canto de baixo à direita, dedo fora —, com os outros três largados na mesa.
14. Anote, para o P1 e para o P2, três coisas: se a palavra mudou, se o pontinho acendeu e se ele andou junto com o dedo.

**Passa quando.** Nos dois controles do cabo, a palavra vira «1 toque» no instante em que o dedo encosta e volta a «Sem toque» quando ele sai; o pontinho acende no lugar onde o dedo está e anda junto com ele. E, enquanto o seu dedo está num deles, os cartões dos outros três continuam em «Sem toque», sem pontinho nenhum.

**Por controle.**

* **P1** — Cabo, e é um dos dois que têm de responder. Encoste o dedo de leve, ande de um canto ao outro e tire. São três coisas a conferir: a palavra, o pontinho acendendo e o pontinho ANDANDO.
* **P2** — Cabo, e é o outro que tem de responder. Mesmos gestos, com os outros três largados na mesa. Se o P1 responder e o P2 não, o defeito não é do cabo — é do segundo lugar da fila.
* **P3** — Rádio, testemunha. Não encoste nele. Enquanto o seu dedo está num controle do cabo, o cartão do P3 tem de continuar em «Sem toque». Se ele acender junto, a tela está mostrando o toque de um controle no cartão de outro.
* **P4** — Rádio, segunda testemunha. Não encoste nele e confira o cartão dele do mesmo jeito. É o último da fila, e é nele que a leitura trocada costuma aparecer primeiro.

**A armadilha.** O cartão cego tem cara própria, e é ela que este teste existe para pegar: o P1 e o P2 no travessão enquanto o dedo anda, com a seta do mouse andando junto. A seta é do sistema, que continua lendo o touchpad; o travessão é o Hefesto sem a porta nova — o programa novo foi instalado e o serviço que abre os nós escondidos seguiu com o de antes na memória. Anote e não conte como passa. Um gesto por vez, e esta regra custou caro a esta casa: num ensaio pediu-se para girar o controle E passar o dedo ao mesmo tempo, o toque saiu ZERO, e por pouco não se escreveu que o produto não lia o touchpad. Gesto composto produz ausência falsa. O toque é LEVE: se você apertar até estalar, isso é o clique, e o clique é outro teste. Um dedo só: dois dedos fazem duas bolinhas e a palavra «2 toques», e isso é o teste dos dedos, não este. O pontinho já mentiu de um jeito específico, e vale conhecer: ele acendia e apagava certo e ficava PARADO no ponto em que o desenho o cravou — se ele acender e não andar com o dedo, o defeito é esse, e não a sua mão. O travessão não é «Sem toque»: é «não consegui ler»; anote e não conte como passa. E se a fita mostrar menos chips do que os quatro controles ligados, a tela não está lendo todos eles: nesse estado o teste não passou nem reprovou. Onde a prova parou: a casa provou que o toque entra no controle virtual que o jogo lê, e parou aí — o que o jogo faz com ele não está medido por esta linha.

---

## mapa-toque.touchpad-radio — Touchpad — os pontos de toque · rádio

*Célula:* `toque.touchpad @ rádio`

**O que isto prova.** Prova que o Hefesto enxerga o dedo no touchpad de um controle ligado por rádio do mesmo jeito que enxerga no cabo — e só no cartão daquele controle. Os nós do aparelho ficam fechados para todo programa menos o Hefesto desde 24/09, e os do rádio moram num lugar diferente dos do cabo: a porta própria por onde o Hefesto os lê tem de achar os dois.

**Onde olhar.** Na aba Controles. Clique no chip «Todos» da fita do topo para abrir os quatro cartões. Dentro de cada cartão, no canto de cima à esquerda, tem a moldura Touchpad: na mesma linha do rótulo vem a palavra do estado — «Sem toque», «1 toque», «2 toques» ou um travessão — e, embaixo dela, um retângulo escuro onde cada dedo é um pontinho ciano. O pontinho só aparece enquanto há dedo na superfície, e fica na POSIÇÃO do dedo. Com os quatro cartões abertos a caixa rola — role para ver os quatro. O travessão quer dizer «não consegui ler». Na fita do topo, cada controle é um chip com o número, a cor do plástico e a palavra do transporte: USB para o cabo, BT para o rádio. No alto do bloco Microfone de cada cartão, o selo diz ATIVO ou DESLIGADO — ele entra neste teste por causa da armadilha.

**Os passos.**

1. Abra o Hefesto e clique na aba Controles.
2. Clique no chip «Todos» da fita do topo, para abrir os quatro cartões.
3. Confira na fita que o P3 e o P4 dizem BT, e que o P1 e o P2 dizem USB.
4. Tire as mãos dos quatro controles.
5. Confira que os quatro cartões dizem «Sem toque», sem pontinho.
6. Encoste um dedo de leve no touchpad do P1, que está no cabo.
7. Confira que o cartão do P1 respondeu — ele é o controle de comparação, e sem ele o resto não mede nada.
8. Tire o dedo do P1 e não encoste mais nele.
9. Encoste UM dedo, de leve, no canto de cima à esquerda do touchpad do P3, e mantenha-o lá.
10. Confira no cartão do P3 que a palavra virou «1 toque» e que o pontinho acendeu perto do canto de cima à esquerda do retângulo.
11. Confira que os cartões do P1, do P2 e do P4 continuam em «Sem toque», sem pontinho, com o seu dedo ainda no P3.
12. Arraste o dedo devagar pelo touchpad do P3 até o canto de baixo à direita, sem tirá-lo da superfície.
13. Confira que o pontinho do P3 andou junto, e repare se ele andou liso ou aos saltos.
14. Tire o dedo do P3.
15. Confira que a palavra voltou a «Sem toque» e que o pontinho apagou.
16. Faça no P4 a mesma volta do P3, com os outros três largados na mesa.
17. Anote, para o P3 e para o P4, se a palavra mudou, se o pontinho acendeu, se ele andou junto e se ele andou liso ou aos saltos.

**Passa quando.** Nos dois controles do rádio, a palavra vira «1 toque» com o dedo e volta a «Sem toque» sem ele, e o pontinho acende no lugar do dedo e anda junto. Para o resultado valer, o P1, que está no cabo, tem de ter respondido antes. E, enquanto o seu dedo está num do rádio, os cartões dos dois do cabo continuam em «Sem toque».

**Por controle.**

* **P1** — Cabo, e é o controle de comparação. Faça o gesto nele PRIMEIRO: se o cartão dele não responder, o que acontecer no rádio não mede nada. Depois disso ele vira testemunha e você não encosta mais nele.
* **P2** — Cabo, testemunha. Não encoste nele em momento nenhum. O cartão dele tem de ficar em «Sem toque» do começo ao fim.
* **P3** — Rádio, e é um dos dois que têm de responder. Dedo leve, andando de um canto ao outro, e o pontinho acompanhando. Repare também no ANDAR do pontinho: pelo rádio chegam menos leituras que pelo cabo.
* **P4** — Rádio, e é o outro que tem de responder. Mesmos gestos. Se o P3 responder e o P4 não, o defeito não é do rádio — é do segundo controle sem fio, e isso é outra coisa.

**A armadilha.** Se o P1 responder e o P3 e o P4 ficarem no travessão enquanto o dedo anda, é o rádio que o Hefesto não alcança pelo esconderijo — o cartão cego que esta célula existe para pegar; anote e não conte como passa. Um gesto por vez: num ensaio pediu-se para girar o controle E passar o dedo ao mesmo tempo, o toque saiu ZERO, e por pouco não se acusou o produto de não ler o touchpad. Gesto composto produz ausência falsa. Pelo rádio chegam menos leituras que do aparelho — medido em dez segundos de dedo: 2.807 contra 3.660 —, então o pontinho pode andar mais aos saltos que no cabo, e isso sozinho não reprova. O caso já conhecido, e ele é dela: pelo rádio o toque funciona FORA do jogo e não dentro. Se o pontinho andar aqui e o mesmo dedo não fizer nada dentro do jogo, isso já foi visto, o repasse até o controle virtual está inteiro e a perda é depois dele — continua sem causa. Anote e siga; não é erro seu. A casa também declarou uma ressalva que só existe no rádio: o som do microfone viaja no MESMO pacote em que viaja o toque. Se o pontinho de um controle do rádio acender ou pular sem dedo nenhum, olhe antes o selo do Microfone daquele cartão — ATIVO ou DESLIGADO — e anote as duas coisas juntas. O travessão não é «Sem toque»: é «não consegui ler». E um dedo só: dois dedos fazem duas bolinhas e a palavra «2 toques», e isso é o teste dos dedos. Onde a prova parou: a casa provou que o toque entra no controle virtual que o jogo lê, e parou aí.

---

## mapa-toque.touchpad.clique-cabo — Touchpad — o clique (botão) · cabo

*Célula:* `toque.touchpad.clique @ cabo`

**O que isto prova.** Prova que o clique firme do touchpad de um controle no cabo é um clique de mouse de verdade, e que a recusa do Hefesto em transformá-lo em tecla está marcada na tela e é cumprida.

**Onde olhar.** Na aba Navegação. No quadro «Quem navega, e com qual controle», cada controle tem um cartão, e embaixo do desenho ele diz a palavra do transporte (USB é o cabo, BT é o rádio) e «Navega o PC» ou «Só a janela» — as linhas de botão valem só para o que diz «Navega o PC». No quadro «As opções de ativação» ficam o «Status do Modo» (Ligado ou Desligado) e a «Função do teclado». Embaixo dele, o botão «Definições Controle e Mouse» abre a tela das linhas de botão: o touchpad tem TRÊS linhas nela, uma por terço da superfície — «Touchpad» com «Clique esquerdo», «Clique direito» e «Clique central» ao lado —, e cada uma traz a marca cinza «não dispara»; parando o mouse em cima dela sai a frase inteira, que diz que o touchpad é o ponteiro do computador e que, enquanto for assim, o clique dele não vira tecla. Essa tela grava pelo «Guardar», no pé dela. NÃO existe campo que acenda com o clique do touchpad: o desenho do Touchpad na fileira de botões do cartão, na aba Controles, não acende com ele. O que se lê é o efeito do clique.

**Os passos.**

1. Abra a aba Navegação.
2. Anote qual cartão do quadro «Quem navega, e com qual controle» diz «Navega o PC».
3. Confira nos cartões desse quadro que o P1 e o P2 dizem USB.
4. Confira que o «Status do Modo» está em Ligado — desligado, nada desta aba chega ao PC e o teste não mede nada.
5. Confira que a «Função do teclado» está em «Só fora do jogo».
6. Clique em «Definições Controle e Mouse».
7. Confira que as três linhas do Touchpad trazem a marca «não dispara», e pare o mouse em cima de uma delas para ler a frase inteira.
8. Anote o que está escolhido hoje na lista da linha «Touchpad», «Clique esquerdo».
9. Escolha «Espaço» nessa lista e clique em «Guardar».
10. Abra um editor de texto num documento em branco e leve a seta do mouse para dentro da área branca — o clique do touchpad é um clique de verdade e vai cair onde a seta estiver.
11. Aperte o touchpad do P1 até sentir o estalo, no terço da ESQUERDA.
12. Confira que o editor recebeu um clique de mouse — o cursor de texto pulou para onde a seta estava — e que nenhum espaço nasceu no texto.
13. Aperte o touchpad do P1 até estalar no meio e depois no terço da direita, com a mesma conferência a cada aperto.
14. Aperte o touchpad do P2 nos três terços, do mesmo jeito, com a mesma conferência a cada aperto.
15. Aperte o touchpad do P3 e o do P4 até estalar.
16. Confira que neles também não nasce espaço nenhum.
17. Volte ao Hefesto e clique de novo em «Definições Controle e Mouse».
18. Devolva a lista da linha «Touchpad», «Clique esquerdo», ao que você anotou, e clique em «Guardar».
19. Se quiser o dado do jogo, abra um jogo que use o clique do touchpad, aperte-o no P1 e anote o que acontecer — sem reprovar por isso.

**Passa quando.** As três linhas do Touchpad mostram a marca «não dispara», e a frase dela explica por quê. O touchpad do P1 e o do P2 estalam e o clique chega ao computador como clique de mouse. E nenhum dos quatro digita o «Espaço» que você escolheu: a recusa é a mesma nos quatro, e o produto não finge ter aplicado.

**Por controle.**

* **P1** — Cabo, e é um dos dois que têm de responder. Aperte até estalar uma vez em cada terço: esquerda, meio e direita. Se o cartão dele disser «Navega o PC», é nele que a recusa da tabela está sendo medida de verdade.
* **P2** — Cabo, e é o outro que tem de responder. Mesmos três apertos. Ele também prova que a escolha da tabela não vaza para um controle que não navega o PC.
* **P3** — Rádio, testemunha. Aperte o touchpad dele até estalar e confira que nenhuma tecla nasce. Se o espaço aparecer aqui, a escolha pegou o rádio inteiro em vez do controle escolhido.
* **P4** — Rádio, segunda testemunha. Mesmo aperto, mesma conferência. Se três recusarem e ele não, anote — é o último da fila, e é onde a escolha costuma escapar.

**A armadilha.** O clique é MECÂNICO: encostar o dedo não é clicar, tem de afundar até estalar. Toque de leve é o outro teste. As linhas de botão valem para UM controle só, o que diz «Navega o PC» — esperar que os quatro digitem é reprovar um produto que está certo. Desde 24/09 o touchpad fica escondido dos jogos e continua sendo o ponteiro do computador: o sistema o abre por uma porta que o esconderijo não fecha, a mesma do teclado e do mouse. Por isso a marca continua certa, e um espaço que nascer é defeito. A marca «não dispara» não é defeito: é o produto avisando que, enquanto o touchpad do controle for o ponteiro do computador, o clique dele não vira tecla, e que a escolha fica guardada. Se a marca sumir e a tecla continuar não nascendo, aí sim há o que perguntar. A escolha só vale depois do «Guardar»: mudar a lista e fechar a tela pelo «Cancelar» ou pelo × a desfaz. O falso vermelho mais fácil é olhar a fileira de botões do cartão da aba Controles: o desenho do Touchpad ali não acende com o clique — apagado ali não quer dizer que o clique não chegou. E não aperte com a seta do mouse em cima de qualquer janela: é um clique de verdade, e um clique cego já desfez configuração nesta casa. Onde a prova parou: a casa provou que o clique entra no pacote do controle virtual que o jogo lê, e parou aí. Esse defeito já existiu de verdade — faltava uma linha de ligação e o clique NÃO chegava ao jogo; foi curado. Por isso o passo do jogo é anotação, e não reprovação.

---

## mapa-toque.touchpad.clique-radio — Touchpad — o clique (botão) · rádio

*Célula:* `toque.touchpad.clique @ rádio`

**O que isto prova.** Prova que o clique do touchpad de um controle no rádio é reconhecido e que a recusa em virar tecla é a mesma do cabo — e esta é a primeira vez que alguém mede isso com o dedo.

**Onde olhar.** Na aba Navegação: no quadro «Quem navega, e com qual controle», o cartão de cada controle diz USB ou BT e «Navega o PC» ou «Só a janela»; no quadro «As opções de ativação», o «Status do Modo» e a «Função do teclado»; e o botão «Definições Controle e Mouse», que abre a tela com as TRÊS linhas do touchpad — «Touchpad» com «Clique esquerdo», «Clique direito» e «Clique central» —, cada uma com a marca cinza «não dispara» e a frase inteira ao parar o mouse em cima dela. Essa tela grava pelo «Guardar». E, na aba Controles, o cartão do P3 e o do P4: o selo do Microfone, que diz ATIVO, DESLIGADO ou um travessão, e a fileira de botões, onde o PS acende enquanto está apertado — os dois entram neste teste por causa da armadilha, não por causa do clique. NÃO existe campo que acenda com o clique do touchpad; o que se lê é o efeito dele.

**Os passos.**

1. Abra a aba Navegação.
2. Anote qual cartão do quadro «Quem navega, e com qual controle» diz «Navega o PC».
3. Confira nos cartões desse quadro que o P3 e o P4 dizem BT.
4. Confira que o «Status do Modo» está em Ligado e que a «Função do teclado» está em «Só fora do jogo».
5. Clique em «Definições Controle e Mouse».
6. Confira que as três linhas do Touchpad trazem a marca «não dispara», e pare o mouse em cima de uma delas para ler a frase.
7. Anote o que está escolhido hoje na lista da linha «Touchpad», «Clique esquerdo».
8. Escolha «Espaço» nessa lista e clique em «Guardar».
9. Abra um editor de texto num documento em branco e leve a seta do mouse para dentro da área branca.
10. Aperte o touchpad do P1, que está no cabo, até estalar.
11. Confira que o editor recebeu o clique de mouse — é ele que prova que a sua mão e o editor estão medindo alguma coisa hoje.
12. Clique na aba Controles, abra o cartão do P3 clicando na linha dele, e anote se o selo do Microfone diz ATIVO ou DESLIGADO.
13. Volte ao editor e aperte o touchpad do P3 até estalar, uma vez em cada terço: esquerda, meio, direita.
14. Confira, a cada aperto, que o editor recebeu um clique de mouse e que nenhum espaço nasceu no texto.
15. Aperte o touchpad do P3 mais umas dez vezes seguidas, em qualquer terço.
16. Volte à aba Controles e aperte o botão PS do P3 uma vez.
17. Confira que o PS acendeu e apagou na fileira de botões do cartão do P3, e que o selo do Microfone dele continua no que você anotou.
18. Aperte o botãozinho de microfone do P3, no plástico, para trocar o estado dele, e refaça no P3 a volta dos três terços, dos dez apertos e do PS.
19. Faça no P4 a mesma volta, com o microfone dele nos dois estados.
20. Aperte o touchpad do P1 e o do P2 até estalar.
21. Confira que neles também não nasce tecla nenhuma.
22. Volte à aba Navegação e clique em «Definições Controle e Mouse».
23. Devolva a lista da linha «Touchpad», «Clique esquerdo», ao que você anotou, e clique em «Guardar».

**Passa quando.** O touchpad do P3 e o do P4 estalam e o clique chega ao computador como clique de mouse, igual ao do cabo. Nenhum dos quatro digita a tecla escolhida. E a sequência de apertos no rádio não prende nem embaralha nada: o PS dos dois acende e apaga no cartão e o selo do microfone deles não vira sozinho.

**Por controle.**

* **P1** — Cabo, e é o controle de comparação. Aperte primeiro nele e confirme o estalo e o clique no editor. Depois vira testemunha: aperte-o de novo só no fim, para conferir que ele também não digita.
* **P2** — Cabo, testemunha. Só no fim: um aperto até estalar, e nenhuma tecla pode nascer.
* **P3** — Rádio, e é um dos dois que têm de responder. Três apertos, um por terço, e depois uma sequência de dez. Faça tudo isso DUAS vezes: uma com o microfone dele ATIVO e outra com ele DESLIGADO, trocando pelo botãozinho do plástico.
* **P4** — Rádio, e é o outro. Mesmos apertos. Se o P3 aguentar a sequência e o P4 não, anote: são dois controles no mesmo tipo de conexão, e é aí que a diferença aparece.

**A armadilha.** Ninguém nunca pôs o dedo neste touchpad com o controle no rádio para ver o clique chegar: o que a casa sabe deste caminho veio de leitura de código, não de bancada. O que sair daqui é medição nova — anote tudo, inclusive o que parecer óbvio. A armadilha que só existe no rádio mora exatamente no clique: com o microfone ligado, o controle manda o SOM dentro do mesmo pacote em que manda o clique, o botão PS e o mudo do microfone, e os bytes do som caem em cima justamente desse byte. Foi assim que o PS e o microfone ficaram presos nesta máquina. Existe uma guarda que separa uma coisa da outra, e é ela que este teste está espremendo: se, depois da sequência de apertos com o microfone ativo, o PS ficar aceso no cartão sem ninguém apertar, o selo do microfone virar sozinho, ou aparecer um clique que ninguém deu — isso é o achado, e é o mais valioso deste lote. Troque o estado do microfone pelo botãozinho do PLÁSTICO: na tela, o 🎙 do cartão não cala nada — ele liga o retorno, para você se ouvir. Se o cartão do P3 ou do P4 disser «Navega o PC», o PS dele sozinho abre a Steam: confira o PS pelo desenho do cartão e feche a Steam depois. O resto vale igual ao cabo: o clique é mecânico e tem de estalar; as linhas de botão valem só para o controle que diz «Navega o PC»; a marca «não dispara» é o produto avisando, não defeito — e continua certa desde 24/09, quando o touchpad ficou escondido dos jogos: o sistema o abre por uma porta que o esconderijo não fecha, e ele segue sendo o ponteiro; a escolha só vale depois do «Guardar»; e o desenho do Touchpad na fileira de botões do cartão não acende com o clique. Não aperte com a seta do mouse em cima de qualquer janela — é um clique de verdade. Onde a prova parou: a casa provou que o clique entra no pacote do controle virtual, e parou aí, nos dois transportes.

---

## mapa-toque.touchpad.cursor-cabo — Touchpad — cursor do mouse (o dedo) · cabo

*Célula:* `toque.touchpad.cursor @ cabo`

**O que isto prova.** Prova que passar o dedo no touchpad de um controle do cabo move a seta do mouse na tela — e mostra de quem é essa seta hoje.

**Onde olhar.** O resultado é a SETA DO MOUSE na sua própria tela, e não um campo do Hefesto — deixe à mostra uma área vazia, para a seta ter para onde andar. No Hefesto, aba Navegação: no quadro «Quem navega, e com qual controle», o cartão de cada controle diz USB ou BT e «Navega o PC» ou «Só a janela»; no quadro «As opções de ativação», a linha «Status do Modo», que diz Ligado ou Desligado, e a linha «Velocidade de cursor», um deslizante de 1 a 12 com o número ao lado. A ajuda da «Velocidade de cursor» diz que o mesmo número vale para o analógico esquerdo e para o touchpad; a ajuda de «Quem navega, e com qual controle» diz a outra metade, e ela é o ponto deste teste: o cursor do PC é UM só e sai do controle marcado «Navega o PC».

**Os passos.**

1. Abra a aba Navegação.
2. Confira que o «Status do Modo» está em Ligado.
3. Anote o número da «Velocidade de cursor» e qual cartão diz «Navega o PC».
4. Confira nos cartões do quadro «Quem navega, e com qual controle» que o P1 e o P2 dizem USB.
5. Largue os quatro controles na mesa e passe o dedo devagar no touchpad do P1, da esquerda para a direita e depois de cima para baixo.
6. Confira que a seta andou para a direita quando o dedo foi para a direita, e desceu quando o dedo desceu.
7. Levante o dedo, reapoie-o em outro canto do touchpad do P1 e ande de novo.
8. Confira que a seta NÃO pulou ao reapoiar — ela só anda quando o dedo anda.
9. Faça no P2 as mesmas duas passadas e o mesmo reapoio, com os outros três largados na mesa.
10. Passe o dedo no touchpad do P3 e depois no do P4, um de cada vez.
11. Anote se a seta andou com eles — aqui é anotação, e não reprovação.
12. Arraste a «Velocidade de cursor» até 12.
13. Passe o dedo no touchpad do P1 do mesmo jeito de antes, e anote se a seta ficou mais rápida.
14. Empurre o analógico esquerdo do controle que diz «Navega o PC», e anote se ELE ficou mais rápido.
15. Devolva a «Velocidade de cursor» ao número que você anotou.

**Passa quando.** A seta do mouse anda com o dedo nos DOIS controles do cabo: para a direita quando o dedo vai para a direita, para baixo quando o dedo desce, e sem pular quando você levanta e reapoia o dedo. O que os dois do rádio fazem é anotação, e não reprovação: hoje o esperado é que eles também movam a seta, porque quem a move é o sistema e o sistema ouve os quatro touchpads.

**Por controle.**

* **P1** — Cabo, e é o primeiro que tem de mover a seta. Se o cartão dele disser «Navega o PC», é também o analógico dele que o ato da velocidade mede.
* **P2** — Cabo, e tem de mover a seta igual ao P1. Se o P1 mover e o P2 não, o defeito é do segundo lugar da fila, não do cabo.
* **P3** — Rádio, testemunha — e esta testemunha responde uma pergunta em vez de ficar quieta. Passe o dedo nela e anote se a seta anda: andando, quem move a seta é o sistema, que ouve os quatro; não andando, quem move é o Hefesto, e aí só o controle «Navega o PC» move.
* **P4** — Rádio, segunda testemunha, mesma pergunta. Se o P3 mover e o P4 não, anote — são dois controles no mesmo tipo de conexão, e a diferença entre eles é o achado.

**A armadilha.** O dedo tem de andar APOIADO: a seta só junta movimento enquanto o dedo está na superfície, e levantar zera a referência de propósito — é isso que impede o salto ao reapoiar. Se a seta pular ao reapoiar, isso é o defeito. Quem move a seta com o touchpad físico hoje é o SISTEMA, e não o Hefesto: foi decisão dela em 09/08, o Hefesto devolveu o touchpad ao computador nos dois transportes, e em 03/09 os dois nós foram medidos assim. Continua sendo depois de 24/09, quando o Hefesto passou a esconder os nós do aparelho de todo programa: o sistema os abre por uma porta que o esconderijo não fecha, a mesma do teclado e do mouse. Se a seta PARAR de andar com o dedo desde então, esse é o defeito, e ele é novo. A ajuda de «Quem navega, e com qual controle» diz que os outros controles «não mexem no cursor» — isso vale para o analógico e os seis gestos, que são do Hefesto; o dedo no touchpad é do sistema. Daí saem duas coisas que enganam. A primeira: a seta andar não prova que o Hefesto está funcionando — prova que o touchpad e o nó dele estão de pé. A segunda: a «Velocidade de cursor» pode não mudar NADA no dedo e mudar tudo no analógico esquerdo, porque o número é do Hefesto e o dedo não passa por ele; se for isso que você vir, anote — é o estado medido, não um defeito novo. Rolar com dois dedos EXISTE, e quem faz é o SISTEMA: medido em 18/09/2026 com os dedos dela, o sistema emitiu 922 eventos de rolagem de dois dedos e 8 pinças no mesmo nó. Não é o que este teste mede. E não confunda os dois gestos: apertar até estalar é o clique, e ele é outro teste. Onde a prova parou: a casa provou o caminho até o controle virtual, e parou aí.

---

## mapa-toque.touchpad.cursor-radio — Touchpad — cursor do mouse (o dedo) · rádio

*Célula:* `toque.touchpad.cursor @ rádio`

**O que isto prova.** Prova que passar o dedo no touchpad de um controle ligado por rádio move a seta do mouse na tela — o que nunca foi medido com um dedo até hoje.

**Onde olhar.** O resultado é a SETA DO MOUSE na sua própria tela, e não um campo do Hefesto — deixe à mostra uma área vazia ao lado da janela do Hefesto, para a seta ter para onde andar. No Hefesto, aba Navegação: no quadro «Quem navega, e com qual controle», o cartão de cada controle diz USB ou BT e «Navega o PC» ou «Só a janela» — é esse cartão que decide se o ato do analógico pode ser feito hoje; no quadro «As opções de ativação», a linha «Status do Modo», que diz Ligado ou Desligado, e a linha «Velocidade de cursor», um deslizante de 1 a 12 com o número ao lado.

**Os passos.**

1. Abra o Hefesto e clique na aba Navegação.
2. Confira que o «Status do Modo» está em Ligado.
3. Confira nos cartões do quadro «Quem navega, e com qual controle» que o P3 e o P4 dizem BT.
4. Anote qual cartão diz «Navega o PC».
5. Com os quatro controles largados na mesa, passe o dedo no touchpad do P1, que está no cabo.
6. Confira que a seta andou — é o P1 que prova que a tela e a sua mão estão medindo alguma coisa hoje. Depois disso não encoste mais nele.
7. Passe o dedo devagar no touchpad do P3, da esquerda para a direita e depois de cima para baixo.
8. Confira que a seta foi para a direita e, na segunda passada, desceu.
9. Levante o dedo do P3, reapoie-o em outro canto do touchpad e ande de novo.
10. Confira que a seta NÃO pulou ao reapoiar.
11. Passe o dedo no touchpad do P3 por uns dez segundos, indo e voltando.
12. Anote se a seta andou liso ou aos saltos.
13. Se o cartão que diz «Navega o PC» for o do P3, empurre o analógico esquerdo dele e anote se a seta anda; se for de outro controle, anote que este pedaço não deu para medir hoje.
14. Faça no P4 a mesma volta do P3 — as duas passadas, o reapoio, os dez segundos e, se for ele quem navega o PC, o analógico —, com os outros três largados na mesa.

**Passa quando.** A seta do mouse anda com o dedo nos DOIS controles do rádio: para a direita quando o dedo vai para a direita, para baixo quando o dedo desce, e sem pular quando você levanta e reapoia o dedo. Para o resultado valer, o P1, que está no cabo, tem de ter movido a seta antes. No fim, você tem anotado, para o P3 e para o P4: se a seta andou, se ela pulou ao reapoiar, e se ela andou liso ou aos saltos.

**Por controle.**

* **P1** — Cabo, e é o controle de comparação. Passe o dedo nele PRIMEIRO: sem a seta andar aqui, o que acontecer no rádio não mede nada. Depois não encoste mais nele.
* **P2** — Cabo, testemunha. Não encoste nele. Ele existe neste teste para você ter certeza de que ninguém está movendo a seta pelo cabo enquanto você mexe no rádio.
* **P3** — Rádio, e é um dos dois que têm de mover a seta. Dedo apoiado, andando devagar nos dois sentidos, e depois dez segundos indo e voltando para ver se ela anda liso.
* **P4** — Rádio, e é o outro. Mesmos gestos. Se o P3 mover a seta e o P4 não, anote: são dois controles sem fio, e a diferença entre eles é o achado deste teste.

**A armadilha.** Este é o lado que nunca foi medido com um dedo. Em 03/09 mediu-se que o touchpad existe pelo rádio, com os mesmos eixos e a mesma geometria do cabo, mas ninguém encostou nele — a POSIÇÃO por rádio não tem medição de bancada nenhuma. O que sair daqui é o primeiro número. Existe uma observação dela, de 11/08, que também nunca foi medida: pelo rádio o touchpad move a seta, mas os gatilhos e o analógico não. Por isso o ato do analógico, e por isso ele só vale no controle que diz «Navega o PC»: em qualquer outro o analógico não move a seta de propósito, e cobrar isso dele seria reprovar um produto que está certo. O dedo tem de andar APOIADO: levantar zera a referência, e é isso que impede o salto ao reapoiar; se a seta pular, isso é o defeito. E quem move a seta com o touchpad físico hoje é o SISTEMA, não o Hefesto — decisão dela de 09/08, medida igual nos dois transportes em 03/09, e que continua valendo com os nós do aparelho escondidos de todo programa desde 24/09, porque o sistema os abre por uma porta que o esconderijo não fecha: a seta andar prova que o touchpad e o nó dele estão de pé, não que o Hefesto está movendo. A frase «os outros não mexem no cursor», na ajuda de «Quem navega», fala do analógico e dos gestos, que são do Hefesto — não do dedo. Rolar com dois dedos EXISTE, e quem faz é o SISTEMA: medido em 18/09/2026 com os dedos dela, 922 eventos de rolagem de dois dedos e 8 pinças no mesmo nó. Não é o que este teste mede. Apertar até estalar é o clique, e é outro teste. Onde a prova parou: a casa provou o caminho até o controle virtual, e parou aí.

---

## mapa-toque.touchpad.dedos-cabo — Touchpad — os dedos na TELA (leitura por slot) · cabo

*Célula:* `toque.touchpad.dedos @ cabo`

**O que isto prova.** Prova que o cartão da aba Controles mostra os DOIS dedos que você apoia no touchpad de um controle no cabo — uma bolinha por dedo, cada uma onde o dedo está — e que a palavra do canto conta certo: «Sem toque», «1 toque», «2 toques». Os dois dedos chegam ao cartão pelo nó do touchpad, que desde 24/09 fica fechado para todo programa menos o Hefesto e o ponteiro do sistema: um travessão com dedo na superfície é o cartão cego da célula dos pontos de toque, e não este teste.

**Onde olhar.** Na aba Controles. Clique no chip «Todos» da fita do topo para abrir os quatro cartões — com eles abertos a caixa rola. Em cada cartão, no canto de cima à esquerda, a moldura Touchpad: o retângulo escuro é o touchpad, as bolinhas ciano são os dedos, e a palavra na linha do rótulo, à direita, é a contagem. Na fita, cada controle diz USB (cabo) ou BT (rádio).

**Os passos.**

1. Abra a aba Controles.
2. Clique no chip «Todos» da fita do topo, para abrir os quatro cartões.
3. Confira na fita que o P1 e o P2 dizem USB.
4. Confira que o Touchpad do cartão do P1 diz «Sem toque» e não mostra bolinha nenhuma.
5. Apoie UM dedo no canto de cima à direita do touchpad do P1 e deixe-o parado.
6. Confira que aparece UMA bolinha no canto de cima à direita do retângulo e que a palavra diz «1 toque».
7. Sem tirar o primeiro dedo, apoie um SEGUNDO dedo no canto de baixo à esquerda.
8. Confira que aparecem DUAS bolinhas, uma em cada canto, e que a palavra diz «2 toques».
9. Deixe os dois dedos parados por uns dez segundos.
10. Confira que as duas bolinhas continuam lá — dedo parado não some — e que os cartões do P2, do P3 e do P4 continuam em «Sem toque».
11. Levante SÓ o primeiro dedo, o de cima à direita.
12. Confira que a bolinha que sobrou é a do canto de baixo à esquerda, que ela NÃO pulou para o outro canto, e que a palavra voltou a «1 toque».
13. Levante o segundo dedo.
14. Confira que a palavra voltou a «Sem toque».
15. Apoie TRÊS dedos juntos no touchpad do P1 e anote quantas bolinhas aparecem.
16. Faça no P2 a mesma volta, do primeiro dedo até levantar o segundo, com os outros três largados na mesa.

**Passa quando.** Dois dedos viram duas bolinhas, cada uma onde o seu dedo está, com a palavra «2 toques»; dedo parado continua na tela; levantar um dedo não faz o outro trocar de lugar; e os cartões dos controles que ninguém tocou ficam em «Sem toque». Com três dedos o esperado são DUAS bolinhas, e isso não é defeito — veja a armadilha.

**Por controle.**

* **P1** — Cabo, e é o primeiro que tem de mostrar os dois dedos.
* **P2** — Cabo, e tem de mostrar igual ao P1. Se o P1 mostrar e o P2 não, o defeito é do segundo lugar da fila, não do cabo.
* **P3** — Rádio, testemunha: largado na mesa. Se o cartão DELE mostrar bolinha enquanto você toca o P1, os dedos estão indo para o controle errado, e isso é o achado.
* **P4** — Rádio, segunda testemunha, mesma pergunta.

**A armadilha.** O touchpad do DualSense tem DOIS pontos de toque no aparelho, e não mais: o nó do kernel declara `ABS_MT_SLOT` de 0 a 1, e o terceiro dedo não chega nem ao sistema. O zoom de três dedos parece funcionar porque a pinça do sistema só precisa de dois — por isso três dedos viram duas bolinhas. A segunda armadilha é o sistema: rolar com dois dedos e dar zoom com a pinça são gestos do SISTEMA, que usa o mesmo touchpad ao mesmo tempo — e continua usando com o touchpad escondido dos jogos; eles podem mover a página que estiver sob a seta enquanto você testa, e isso não é o Hefesto. A terceira é o tempo da tela: ela lê o controle dez vezes por segundo, então um toque rápido demais pode não aparecer — os passos pedem dedo parado de propósito. Apertar até estalar é o clique, e é outro teste.

---

## mapa-toque.touchpad.dedos-radio — Touchpad — os dedos na TELA (leitura por slot) · rádio

*Célula:* `toque.touchpad.dedos @ rádio`

**O que isto prova.** Prova que o cartão da aba Controles mostra os DOIS dedos que você apoia no touchpad de um controle no rádio — uma bolinha por dedo, cada uma onde o dedo está — e que a palavra do canto conta certo: «Sem toque», «1 toque», «2 toques». Os dois dedos chegam ao cartão pelo nó do touchpad, que desde 24/09 fica fechado para todo programa menos o Hefesto e o ponteiro do sistema: um travessão com dedo na superfície é o cartão cego da célula dos pontos de toque, e não este teste.

**Onde olhar.** Na aba Controles. Clique no chip «Todos» da fita do topo para abrir os quatro cartões — com eles abertos a caixa rola. Em cada cartão, no canto de cima à esquerda, a moldura Touchpad: o retângulo escuro é o touchpad, as bolinhas ciano são os dedos, e a palavra na linha do rótulo, à direita, é a contagem. Na fita, cada controle diz USB (cabo) ou BT (rádio).

**Os passos.**

1. Abra a aba Controles.
2. Clique no chip «Todos» da fita do topo, para abrir os quatro cartões.
3. Confira na fita que o P3 e o P4 dizem BT.
4. Apoie dois dedos no touchpad do P1, que está no cabo, e deixe-os parados.
5. Confira que o cartão do P1 mostra as duas bolinhas — é a comparação, e sem ela o resto não mede nada.
6. Tire os dedos do P1 e não encoste mais nele.
7. Confira que o Touchpad do cartão do P3 diz «Sem toque» e não mostra bolinha nenhuma.
8. Apoie UM dedo no canto de cima à direita do touchpad do P3 e deixe-o parado.
9. Confira que aparece UMA bolinha no canto de cima à direita do retângulo e que a palavra diz «1 toque».
10. Sem tirar o primeiro dedo, apoie um SEGUNDO dedo no canto de baixo à esquerda.
11. Confira que aparecem DUAS bolinhas, uma em cada canto, e que a palavra diz «2 toques».
12. Deixe os dois dedos parados por uns dez segundos.
13. Confira que as duas bolinhas continuam lá — dedo parado não some — e que os cartões do P1, do P2 e do P4 continuam em «Sem toque».
14. Levante SÓ o primeiro dedo, o de cima à direita.
15. Confira que a bolinha que sobrou é a do canto de baixo à esquerda, que ela NÃO pulou para o outro canto, e que a palavra voltou a «1 toque».
16. Levante o segundo dedo.
17. Confira que a palavra voltou a «Sem toque».
18. Apoie TRÊS dedos juntos no touchpad do P3 e anote quantas bolinhas aparecem.
19. Faça no P4 a mesma volta do P3, do primeiro dedo até levantar o segundo, com os outros três largados na mesa.

**Passa quando.** Nos dois do rádio, dois dedos viram duas bolinhas, cada uma onde o seu dedo está, com a palavra «2 toques»; dedo parado continua na tela; levantar um dedo não faz o outro trocar de lugar; e os cartões dos controles que ninguém tocou ficam em «Sem toque». Com três dedos o esperado são DUAS bolinhas, e isso não é defeito — veja a armadilha.

**Por controle.**

* **P1** — Cabo, e é o controle de comparação: dois dedos nele primeiro, e depois vira testemunha. Se o cartão DELE mostrar bolinha enquanto você toca o P3, os dedos estão indo para o controle errado.
* **P2** — Cabo, testemunha: largado na mesa, mesma pergunta.
* **P3** — Rádio, e é o primeiro que tem de mostrar os dois dedos. O nó de touchpad é o mesmo nos dois transportes, então pelo rádio o esperado é igual ao cabo.
* **P4** — Rádio, e tem de mostrar igual ao P3.

**A armadilha.** O touchpad do DualSense tem DOIS pontos de toque no aparelho, e não mais: o nó do kernel declara `ABS_MT_SLOT` de 0 a 1, e o terceiro dedo não chega nem ao sistema. O zoom de três dedos parece funcionar porque a pinça do sistema só precisa de dois — por isso três dedos viram duas bolinhas. A segunda armadilha é o sistema: rolar com dois dedos e dar zoom com a pinça são gestos do SISTEMA, que usa o mesmo touchpad ao mesmo tempo — e continua usando com o touchpad escondido dos jogos; eles podem mover a página que estiver sob a seta enquanto você testa, e isso não é o Hefesto. A terceira é o tempo da tela: ela lê o controle dez vezes por segundo, e pelo rádio chegam menos leituras que pelo cabo, então um toque rápido demais pode não aparecer — os passos pedem dedo parado de propósito.

---

## mapa-vibracao.rumble.direito-cabo — Rumble — motor DIREITO (weak) · cabo

*Célula:* `vibracao.rumble.direito @ cabo`

**O que isto prova.** Prova que, nos dois controles do cabo, o motor que o Hefesto chama de direito é o punho direito — e que, com a barra do Motor esquerdo em 0, só o punho direito treme, e só naquele controle.

**Onde olhar.** Na aba Vibração, que tem uma coluna por controle — a fita do topo não escolhe nada aqui. Na linha Controle, o desenho do controle: o lado que treme acende em laranja. Na linha Modelo, o número, a cor do plástico e a palavra do transporte — USB é o cabo, BT é o rádio. Mais abaixo, a linha Motor esquerdo e a linha Motor direito, cada uma com um ícone que fica aceso enquanto o motor está ligado, uma barra de 0 a 100 e o número com %. No pé da coluna, «Testar» e «Parar»: o Testar faz aquele controle tremer com os valores das barras da coluna e o deixa tremendo até você clicar em Parar. Ao ser clicado, o botão pisca a borda — verde quando aplicou, laranja quando foi recusado. O juiz final são as suas mãos.

**Os passos.**

1. Feche o jogo, se houver algum aberto.
2. Clique na aba Vibração.
3. Confira na linha Modelo que as colunas do P1 e do P2 dizem USB.
4. Anote os dois números de motor de cada uma das quatro colunas, antes de mexer em qualquer barra.
5. Arraste, na coluna do P1, a barra do Motor esquerdo até 0 e a do Motor direito até 100.
6. Clique em Testar na coluna do P1.
7. Pegue o P1 com uma mão em cada punho, sem apertar, feche os olhos e diga em voz alta qual punho treme.
8. Confira, de olhos abertos, qual lado do desenho da coluna do P1 está aceso em laranja, e que o P2, o P3 e o P4 estão parados na mesa.
9. Clique em Parar na coluna do P1.
10. Faça na coluna do P2 a mesma volta: barra esquerda em 0 e direita em 100, Testar, as duas mãos de olhos fechados, a olhada no desenho, Parar.
11. Arraste as duas barras de motor da coluna do P3 até 100 e clique em Testar na coluna dele.
12. Pegue o P3 com uma mão em cada punho.
13. Confira que no P3 os DOIS punhos tremem.
14. Clique em Parar na coluna do P3.
15. Devolva as barras das quatro colunas aos números que você anotou.

**Passa quando.** No P1 e no P2 — os dois do cabo —, com a barra esquerda em 0, só o punho DIREITO tremeu, e no desenho só o lado direito acendeu em laranja; o punho esquerdo desses dois ficou parado. No P3, com as duas barras em 100, os dois punhos tremeram: é isso que prova que o motor esquerdo está vivo e que quem o calou foi a barra, não um defeito. E nenhum controle tremeu enquanto o Testar era de outro.

**Por controle.**

* **P1** — Está no CABO e é um dos dois que têm de reagir. Barra esquerda em 0, direita em 100: só o punho direito pode tremer, e só o lado direito acende no desenho.
* **P2** — Também no cabo, mesma configuração e mesma resposta esperada. Se os dois do cabo se comportarem diferente um do outro, o defeito é daquele controle e não do transporte — anote qual dos dois.
* **P3** — Está no RÁDIO e é testemunha e contraste: parado enquanto o Testar é do P1 ou do P2, e, com as duas barras em 100, os dois punhos dele têm de tremer quando o Testar é dele.
* **P4** — Também no rádio, testemunha: não mexa nas barras dele, e ele não pode tremer em momento nenhum deste teste. Se tremer junto com o P1, a vibração perdeu o endereço e foi para os quatro.

**A armadilha.** O Testar mudou duas vezes, e as duas mudanças importam aqui. Desde 07/09, por pedido dela, ele NÃO é mais um pulso de meio segundo: fica ligado até você clicar em Parar — é isso que deixa você clicar e só depois pegar o controle com as duas mãos. A ajuda do «Testar agora» ainda fala em meio segundo; vale o que a mão sente. E desde 09/09 o Testar obedece às barras da coluna: com a barra do Motor esquerdo em 0, o punho esquerdo tem de ficar parado também no Testar — se ele tremer, isso é o defeito. Começar o Testar noutra coluna encerra o da anterior, e trocar de aba também o desliga. Se o botão piscar laranja em vez de verde, o Testar foi recusado: confira na aba Jogar se o Status está em Ligado — em Desligado quem manda nos motores é o jogo. O tremor viaja pelo casco: com o controle apoiado na mesa, ou apertado com força, o punho mudo parece tremer também — segure leve. A barra grava no perfil ativo no instante em que você a solta, e fica gravada: por isso os números se anotam antes e se devolvem no fim. O ícone ao lado da barra acende sozinho quando ela passa de 0; clicar nele liga o motor em 100 ou o desliga em 0, e não lembra o número de antes. O «diga em voz alta de olhos fechados» é passo próprio de propósito: falar o punho antes de olhar o desenho é a defesa contra sentir o lado que a tela mostrou. No mapa esta célula chegou até o aparelho obedecer, num teste às cegas com o jogo; aqui é a confirmação pelo Testar, sem jogo — que a barra também vale para a vibração do jogo é o que o teste do rumble por amplitude mede.

---

## mapa-vibracao.rumble.direito-radio — Rumble — motor DIREITO (weak) · rádio

*Célula:* `vibracao.rumble.direito @ rádio`

**O que isto prova.** Prova que, nos dois controles do rádio, o motor direito é o punho direito — e que, com a barra do Motor esquerdo em 0, só o punho direito treme, sem tocar nos controles do cabo.

**Onde olhar.** Na aba Vibração, uma coluna por controle — a fita do topo não escolhe nada aqui. Nas colunas do P3 e do P4, a linha Modelo tem de dizer BT, que é o rádio. Dentro de cada coluna: o desenho do controle, onde o lado que treme acende em laranja; a linha Motor esquerdo e a linha Motor direito, cada uma com um ícone aceso enquanto o motor está ligado, uma barra de 0 a 100 e o número com %; e, no pé, «Testar» e «Parar». O Testar faz aquele controle tremer com os valores das barras da coluna e o deixa tremendo até o Parar; ao ser clicado, o botão pisca a borda verde quando aplicou e laranja quando foi recusado. Quem decide o resultado são as suas mãos.

**Os passos.**

1. Feche o jogo, se houver algum aberto.
2. Clique na aba Vibração.
3. Confira na linha Modelo que as colunas do P3 e do P4 dizem BT.
4. Anote os dois números de motor de cada uma das quatro colunas, antes de mexer em qualquer barra.
5. Arraste, na coluna do P3, a barra do Motor esquerdo até 0 e a do Motor direito até 100.
6. Clique em Testar na coluna do P3.
7. Pegue o P3 com uma mão em cada punho, sem apertar, feche os olhos e diga em voz alta qual punho treme.
8. Confira, de olhos abertos, qual lado do desenho da coluna do P3 está aceso em laranja, e que o P1, o P2 e o P4 estão parados na mesa.
9. Clique em Parar na coluna do P3.
10. Faça na coluna do P4 a mesma volta: barra esquerda em 0 e direita em 100, Testar, as duas mãos de olhos fechados, a olhada no desenho, Parar.
11. Arraste as duas barras de motor da coluna do P1 até 100 e clique em Testar na coluna dele.
12. Pegue o P1 com uma mão em cada punho.
13. Confira que no P1 os DOIS punhos tremem.
14. Clique em Parar na coluna do P1.
15. Devolva as barras das quatro colunas aos números que você anotou.

**Passa quando.** No P3 e no P4 — os dois do rádio —, com a barra esquerda em 0, só o punho DIREITO tremeu, e no desenho só o lado direito acendeu em laranja. O P1, com as duas barras em 100, tremeu dos dois lados quando o Testar era dele: é a prova de que o motor esquerdo está vivo e de que quem o calou no rádio foi a barra. E nenhum dos quatro tremeu enquanto o Testar era de outro.

**Por controle.**

* **P1** — Está no CABO e é testemunha e contraste. Ele não pode tremer enquanto o Testar é do P3 ou do P4 — se tremer, o comando pegou os quatro em vez do controle escolhido. Com as duas barras em 100, os dois punhos dele têm de tremer quando o Testar é dele.
* **P2** — Também no cabo, testemunha: não mexa nas barras dele, e ele não pode tremer em momento nenhum deste teste.
* **P3** — Está no RÁDIO e é um dos dois que têm de reagir. Barra esquerda em 0, direita em 100: só o punho direito treme, e só o lado direito acende no desenho.
* **P4** — Também no rádio, mesma configuração. Se ele responder diferente do P3, anote qual dos dois — dois controles no mesmo transporte discordando aponta para o aparelho, não para o caminho.

**A armadilha.** O Testar NÃO é mais um pulso de meio segundo: desde 07/09, por pedido dela, ele fica ligado até você clicar em Parar — a ajuda do «Testar agora» ainda fala em meio segundo, e vale o que a mão sente. E desde 09/09 ele obedece às barras da coluna: com a barra esquerda em 0, o punho esquerdo tem de ficar parado também no Testar — se ele tremer, isso é o defeito. Começar o Testar noutra coluna encerra o da anterior, e trocar de aba também o desliga. Se o botão piscar laranja em vez de verde, o Testar foi recusado: confira na aba Jogar se o Status está em Ligado. Segunda, e é do rádio: o comando vai numerado e conferido, e um comando que chegue fora de ordem o próprio controle joga fora, sem avisar ninguém. O sintoma é uma vibração que falha de vez em quando, e ele não aparece em campo nenhum da tela — se acontecer, refaça a rodada antes de concluir qualquer coisa. Não deixe o alto-falante do P3 ou do P4 tocando durante o teste: pelo rádio o som e a vibração disputam o mesmo fio. Terceira: a medição de quatro controles na mesa não achou diferença nenhuma entre cabo e rádio nesta família; se aqui os dois do rádio se comportarem diferente dos dois do cabo, isso é informação nova e vale anotar com todas as letras. Quarta: a barra grava no perfil ativo assim que você a solta — escreva os oito números antes, devolva depois. E o «diga em voz alta de olhos fechados» é passo próprio de propósito: falar o punho antes de olhar o desenho é a defesa contra sentir o lado que a tela mostrou.

---

## mapa-vibracao.rumble.esquerdo-cabo — Rumble — motor ESQUERDO (strong) · cabo

*Célula:* `vibracao.rumble.esquerdo @ cabo`

**O que isto prova.** Prova que, nos dois controles do cabo, o motor que o Hefesto chama de esquerdo é o punho esquerdo — o pesado, o que soa grosso — e que, com a barra do Motor direito em 0, o tremor fica só nele.

**Onde olhar.** Na aba Vibração, uma coluna por controle — a fita do topo não escolhe nada aqui. Nas colunas do P1 e do P2, a linha Modelo tem de dizer USB, que é o cabo. Dentro de cada coluna: o desenho do controle, onde o lado que treme acende em laranja; a linha Motor esquerdo e a linha Motor direito, cada uma com um ícone aceso enquanto o motor está ligado, uma barra de 0 a 100 e o número com % — parando o mouse no ? de cada linha sai qual punho é aquele e como ele soa; e, no pé, «Testar» e «Parar». O Testar faz aquele controle tremer com os valores das barras da coluna e o deixa tremendo até o Parar; ao ser clicado, o botão pisca a borda verde quando aplicou e laranja quando foi recusado. As mãos decidem.

**Os passos.**

1. Feche o jogo, se houver algum aberto.
2. Clique na aba Vibração.
3. Confira na linha Modelo que as colunas do P1 e do P2 dizem USB.
4. Anote os dois números de motor das quatro colunas, antes de mexer em qualquer barra.
5. Arraste, na coluna do P1, a barra do Motor direito até 0 e a do Motor esquerdo até 100.
6. Clique em Testar na coluna do P1.
7. Pegue o P1 com uma mão em cada punho, sem apertar, feche os olhos e diga em voz alta em qual punho está o PESO do tremor.
8. Segure o P1 só pelo punho esquerdo.
9. Troque: segure o P1 só pelo punho direito.
10. Confira que no punho direito não vem tremor próprio, só o eco que atravessa o plástico, e que no desenho da coluna do P1 só o lado esquerdo está aceso.
11. Clique em Parar na coluna do P1.
12. Faça na coluna do P2 a mesma volta: barra direita em 0 e esquerda em 100, Testar, as duas mãos de olhos fechados, um punho de cada vez, Parar.
13. Arraste as duas barras de motor da coluna do P3 até 100, clique em Testar na coluna dele e pegue o P3 com as duas mãos.
14. Confira que no P3 os DOIS punhos tremem.
15. Clique em Parar na coluna do P3.
16. Devolva as barras das quatro colunas aos números que você anotou.

**Passa quando.** No P1 e no P2, com a barra direita em 0, o peso do tremor ficou no punho ESQUERDO — e segurando só pelo punho direito não há tremor próprio, só o eco que atravessa o plástico. No desenho, só o lado esquerdo acendeu em laranja. No P3, com as duas barras em 100, os dois punhos tremeram, provando que o motor direito está vivo e que quem o calou foi a barra. E nenhum controle tremeu enquanto o Testar era de outro.

**Por controle.**

* **P1** — Está no CABO e é um dos dois que têm de reagir. Barra direita em 0, esquerda em 100: o peso do tremor fica no punho esquerdo e só o lado esquerdo acende no desenho.
* **P2** — Também no cabo, mesma configuração. Se os dois do cabo discordarem entre si, o defeito é do aparelho e não do caminho — anote qual dos dois.
* **P3** — Está no RÁDIO e é testemunha e contraste: parado enquanto o Testar é do P1 ou do P2, e, com as duas barras em 100, os dois punhos dele têm de tremer quando o Testar é dele.
* **P4** — Também no rádio, testemunha: não mexa nas barras dele, e ele não pode tremer em momento nenhum. Tremendo junto com o P1, a vibração foi para os quatro.

**A armadilha.** O motor esquerdo é o PESADO, e é ele que faz este teste dar falso vermelho. Quando só o esquerdo treme, o casco inteiro balança e a mão direita sente alguma coisa — quem julgar por «senti alguma coisa» conclui que os dois lados tremeram e reprova um produto certo. O que se julga é onde está o PESO, não onde há sensação; e a conferência de verdade é a dos passos que mandam segurar um punho de cada vez — cortar uma dessas trocas devolve o falso vermelho. Segunda: o Testar NÃO é mais um pulso de meio segundo — desde 07/09 ele fica ligado até o Parar, e é isso que dá tempo de trocar de punho sem reclicar; a ajuda do «Testar agora» ainda fala em meio segundo, e vale o que a mão sente. Desde 09/09 ele obedece às barras: com a barra direita em 0, o punho direito tem de ficar sem tremor próprio também no Testar. No par que o Testar manda o esquerdo já sai mais forte que o direito de propósito. Começar o Testar noutra coluna encerra o da anterior, e trocar de aba também o desliga; se o botão piscar laranja, confira na aba Jogar se o Status está em Ligado. Terceira: a barra grava no perfil ativo assim que você a solta, e fica — anote antes, devolva depois. O ícone ao lado da barra liga em 100 ou desliga em 0, e não lembra o número de antes. Quarta: o laranja do desenho apaga sozinho uns três segundos depois de o motor parar; desenho apagado com a vibração já acabada não é defeito.

---

## mapa-vibracao.rumble.esquerdo-radio — Rumble — motor ESQUERDO (strong) · rádio

*Célula:* `vibracao.rumble.esquerdo @ rádio`

**O que isto prova.** Prova que, nos dois controles do rádio, o motor esquerdo é o punho esquerdo — o pesado — e que, com a barra do Motor direito em 0, o tremor fica só nele, sem tocar nos controles do cabo.

**Onde olhar.** Na aba Vibração, uma coluna por controle — a fita do topo não escolhe nada aqui. Nas colunas do P3 e do P4, a linha Modelo tem de dizer BT, que é o rádio. Dentro de cada coluna: o desenho, onde o lado que treme acende em laranja; a linha Motor esquerdo e a linha Motor direito, cada uma com um ícone aceso enquanto o motor está ligado, uma barra de 0 a 100 e o número com %; e, no pé, «Testar» e «Parar». O Testar faz aquele controle tremer com os valores das barras da coluna e o deixa tremendo até o Parar; ao ser clicado, o botão pisca a borda verde quando aplicou e laranja quando foi recusado. As mãos decidem.

**Os passos.**

1. Feche o jogo, se houver algum aberto.
2. Clique na aba Vibração.
3. Confira na linha Modelo que as colunas do P3 e do P4 dizem BT.
4. Anote os dois números de motor das quatro colunas, antes de mexer em qualquer barra.
5. Arraste, na coluna do P3, a barra do Motor direito até 0 e a do Motor esquerdo até 100.
6. Clique em Testar na coluna do P3.
7. Pegue o P3 com uma mão em cada punho, sem apertar, feche os olhos e diga em voz alta em qual punho está o PESO do tremor.
8. Segure o P3 só pelo punho esquerdo.
9. Troque: segure o P3 só pelo punho direito.
10. Confira que no punho direito não vem tremor próprio, e que no desenho da coluna do P3 só o lado esquerdo está aceso.
11. Clique em Parar na coluna do P3.
12. Faça na coluna do P4 a mesma volta: barra direita em 0 e esquerda em 100, Testar, as duas mãos de olhos fechados, um punho de cada vez, Parar.
13. Arraste as duas barras de motor da coluna do P1 até 100, clique em Testar na coluna dele e pegue o P1 com as duas mãos.
14. Confira que no P1 os DOIS punhos tremem.
15. Clique em Parar na coluna do P1.
16. Devolva as barras das quatro colunas aos números que você anotou.

**Passa quando.** No P3 e no P4, com a barra direita em 0, o peso do tremor ficou no punho ESQUERDO, e segurando só pelo punho direito não há tremor próprio. No desenho, só o lado esquerdo acendeu em laranja. O P1, com as duas barras em 100, tremeu dos dois lados quando o Testar era dele. E nenhum dos quatro tremeu enquanto o Testar era de outro.

**Por controle.**

* **P1** — Está no CABO e é testemunha e comparação: não pode tremer enquanto o Testar é do P3 ou do P4, e, com as duas barras em 100, os dois punhos dele tremem quando o Testar é dele.
* **P2** — Também no cabo, testemunha: não mexa nas barras dele, e ele não pode tremer em momento nenhum. Os dois do cabo tremendo junto com o P3 quer dizer que a vibração foi para os quatro.
* **P3** — Está no RÁDIO e é um dos dois que têm de reagir. Barra direita em 0, esquerda em 100: o peso fica no punho esquerdo e só o lado esquerdo acende no desenho.
* **P4** — Também no rádio, mesma configuração e mesma resposta esperada. Se ele discordar do P3, o defeito é do aparelho — anote qual dos dois.

**A armadilha.** O motor esquerdo é o PESADO: quando só ele treme, o casco inteiro balança e a mão direita sente o eco. Julgue pelo PESO do tremor, não por sentir alguma coisa — e o punho certo só se separa do errado segurando um punho de cada vez, que é por que o teste troca de mão. O Testar NÃO é mais um pulso de meio segundo: desde 07/09 ele fica ligado até o Parar, e a ajuda do «Testar agora» ainda fala em meio segundo — vale o que a mão sente. Desde 09/09 ele obedece às barras da coluna. Começar o Testar noutra coluna encerra o da anterior, e trocar de aba também o desliga; se o botão piscar laranja, confira na aba Jogar se o Status está em Ligado. Segunda, e é do rádio: o comando vai numerado e conferido, e o controle descarta sozinho o que chegar fora de ordem, calado; o sintoma é uma vibração que some de vez em quando e não aparece em campo nenhum da tela. Não deixe o alto-falante do P3 ou do P4 tocando durante o teste: pelo rádio o som e a vibração disputam o mesmo fio. Terceira: houve um tempo em que a vibração pelo rádio era gasto de energia e nada mais, porque o comando saía malformado e o controle o descartava inteiro; hoje ele sai certo, mas se os dois do rádio ficarem MUDOS enquanto o P1 treme no mesmo teste, é exatamente isso que você está vendo voltar — anote antes de mexer em qualquer outra coisa. Quarta: a barra grava no perfil ativo assim que você a solta, e é por isso que os números se anotam no começo e voltam para as barras no fim.

---

## mapa-vibracao.rumble.ff-cabo — Rumble por amplitude (FF_RUMBLE — motor esquerdo = strong, direito = weak) · cabo

*Célula:* `vibracao.rumble.ff @ cabo`

**O que isto prova.** Prova que, nos dois controles do cabo, a vibração que o jogo pede chega com a força pedida e DURA o tempo que o jogo segurou — sem ser cortada num piscar.

**Onde olhar.** Na aba Vibração, na COLUNA de cada jogador — a testemunha é por controle. No alto da coluna, o desenho acende em laranja o punho que está recebendo força agora, e apaga uns três segundos depois da última. Parando o mouse em cima do número ao lado da barra de um motor sai a dica: com o jogo vibrando, «O jogo pediu … de 255 neste motor agora.»; sem pedido, ela diz a conta da coluna, «Este motor a …%, força …% — sai …% do que o jogo pedir.». É esse par — punho aceso e a dica do pedido — que diz quem recebeu. Na aba Controles, parando o mouse no nome de um controle, no alto do cartão, a dica diz qual gamepad virtual ele alimenta. A duração quem mede são as suas mãos e a sua contagem em voz alta.

**Os passos.**

1. Clique na aba Vibração.
2. Clique na aba Jogar e confira que o Status está em Ligado.
3. Clique na aba Controles e pare o mouse no nome de cada um dos quatro controles, no alto do cartão.
4. Confira que a dica de cada um diz «Alimenta o gamepad virtual do Jogador …», e não que ainda não alimenta nenhum.
5. Volte à aba Vibração.
6. Clique em Parar em cada uma das quatro colunas, para devolver ao jogo qualquer vibração presa num teste anterior.
7. Anote o degrau aceso na Força da vibração e os dois números de motor de cada coluna.
8. Clique em Balanceado nas quatro colunas e arraste as oito barras de motor até 100.
9. Abra o jogo com os quatro jogadores dentro da partida.
10. Segure o P1 nas duas mãos e provoque uma vibração LONGA para o jogador dele — daquelas que o jogo segura por vários segundos, como um motor acelerando ou uma arma automática.
11. Conte os segundos em voz alta enquanto ela dura.
12. Pare de provocar a vibração.
13. Confira que ela parou junto.
14. Provoque uma vibração CURTA e forte, de um tiro ou de uma batida.
15. Confira que ela chegou com força.
16. Provoque de novo a longa e, com ela correndo, pare o mouse no número ao lado da barra do Motor esquerdo da coluna do P1.
17. Confira que o punho do desenho da coluna do P1 está aceso e que a dica diz «O jogo pediu … de 255 neste motor agora.».
18. Faça no P2 a mesma volta: a longa contada, a curta, e a olhada na coluna dele.
19. Provoque uma vibração longa no P1 e, sem parar, outra no P3.
20. Confira que a do P1 não encolheu.
21. Devolva o degrau e as barras de cada coluna ao que você anotou.

**Passa quando.** Nos dois do cabo, a vibração que o jogo segurou por vários segundos durou esses segundos inteiros na mão, e parou quando o jogo parou de pedir — não virou um estalo de meio segundo. A vibração curta e forte chegou forte. O punho do desenho acendeu em laranja na coluna daquele controle, e a dica da linha do motor daquela coluna trouxe o número que o jogo pediu. E a vibração de um não encurtou a do outro.

**Por controle.**

* **P1** — Está no CABO e é um dos dois que têm de reagir. É nele que a contagem de segundos importa: a vibração longa tem de durar o que o jogo segurou.
* **P2** — Também no cabo, mesma medição. Dois controles no mesmo transporte com durações diferentes é achado — anote os dois números de segundos.
* **P3** — Está no RÁDIO e é testemunha. Ele entra no penúltimo passo: uma vibração provocada nele não pode encurtar a que já está correndo no P1. Se encurtar, um está cortando a vibração do outro.
* **P4** — Também no rádio e também testemunha, com a mesma conferência — e é o último da fila, o primeiro a perder a vez quando alguma coisa disputa a saída. Repita nele o passo do P3 se o P3 não mostrar nada.

**A armadilha.** O corte em meio segundo é um defeito CONHECIDO desta casa e já foi medido por dose: o Hefesto re-afirma o estado dos motores de meio em meio segundo, e essa re-afirmação já zerava a vibração de quem não fosse ele — esticando esse meio segundo para oito, a vibração passou a durar oito segundos exatos, nos dois transportes. O conserto está escrito e ligado; este teste existe para dizer se ele continua de pé. Por isso a contagem em voz alta é o instrumento, e não um detalhe. Segunda: o Testar agora fica LIGADO até alguém clicar em Parar, e enquanto ele está ligado a vibração do jogo naquele controle é ignorada — é o que o Parar em cada coluna, no começo, evita. Terceira: um jogo pode simplesmente não pedir vibração, e quem separa os dois casos é a dica da linha do motor — se ela diz «O jogo pediu …» e a mão não sente nada, a perda é dentro do Hefesto; se ela diz a conta da coluna, «Este motor a …», o jogo não pediu. Quarta: se a aba Controles disser que aquele controle ainda não alimenta gamepad virtual nenhum, o Hefesto saiu do meio e este teste não está medindo o caminho dele. Quinta: o jogo enxerga só os quatro controles virtuais, aberto pelo atalho ou fora dele: desde 24/09 o Hefesto esconde os DualSense de verdade de todo programa menos ele — o botão, o toque e o movimento, além do que já escondia —, e só o Modo Nativo os devolve. Se ele listar mais de quatro, anote: o aparelho escapou do esconderijo, a vibração pode estar indo direto a ele por fora do Hefesto, e este teste não mede nada até isso ser resolvido.

---

## mapa-vibracao.rumble.ff-radio — Rumble por amplitude (FF_RUMBLE — motor esquerdo = strong, direito = weak) · rádio

*Célula:* `vibracao.rumble.ff @ rádio`

**O que isto prova.** Prova que, nos dois controles do rádio, a vibração que o jogo pede chega com a força pedida e dura o tempo que o jogo segurou — igual à dos dois do cabo.

**Onde olhar.** Na aba Vibração, nas colunas do P3 e do P4 — a linha Modelo delas diz BT, que é o rádio. O desenho acende em laranja o punho que recebe força agora, e apaga uns três segundos depois da última; parando o mouse em cima do número ao lado da barra de um motor, com o jogo vibrando, a dica diz «O jogo pediu … de 255 neste motor agora.», e sem pedido ela diz a conta da coluna, «Este motor a …». Na aba Controles, parando o mouse no nome de um controle, a dica diz qual gamepad virtual ele alimenta. A duração quem mede são as suas mãos e a contagem em voz alta.

**Os passos.**

1. Clique na aba Vibração.
2. Clique na aba Jogar e confira que o Status está em Ligado.
3. Clique na aba Controles e pare o mouse no nome de cada um dos quatro controles, no alto do cartão.
4. Confira que a dica de cada um diz «Alimenta o gamepad virtual do Jogador …», e não que ainda não alimenta nenhum.
5. Volte à aba Vibração.
6. Confira na linha Modelo que as colunas do P3 e do P4 dizem BT.
7. Clique em Parar em cada uma das quatro colunas.
8. Anote o degrau aceso na Força da vibração e os dois números de motor de cada coluna.
9. Clique em Balanceado nas quatro colunas e arraste as oito barras de motor até 100.
10. Abra o jogo com os quatro jogadores dentro da partida.
11. Segure o P3 nas duas mãos e provoque uma vibração LONGA para o jogador dele.
12. Conte os segundos em voz alta enquanto ela dura.
13. Pare de provocar a vibração.
14. Confira que ela parou junto.
15. Provoque uma vibração CURTA e forte.
16. Confira que ela chegou forte e que o punho do desenho da coluna do P3 acendeu em laranja enquanto ela chegava.
17. Faça no P4 a mesma volta: a longa contada, a curta, e a olhada na coluna dele.
18. Faça a mesma vibração longa no P1 e conte os segundos dela.
19. Compare os segundos do rádio com os segundos do cabo.
20. Devolva o degrau e as barras de cada coluna ao que você anotou.

**Passa quando.** Nos dois do rádio, a vibração longa durou o tempo em que o jogo a segurou e parou quando ele parou de pedir; a curta chegou forte; e o punho do desenho acendeu em laranja na coluna daquele controle, com a dica da linha do motor trazendo o número pedido. Comparados com o P1, os segundos batem: se o rádio durar menos que o cabo na mesma vibração, isso é o achado do teste.

**Por controle.**

* **P1** — Está no CABO e é testemunha — e aqui ele é a RÉGUA: a mesma vibração longa provocada nele dá o número de segundos com que os do rádio são comparados.
* **P2** — Também no cabo e também testemunha. Use-o para repetir a régua se o número do P1 sair estranho — dois cabos discordando entre si invalidam a comparação antes de acusar o rádio.
* **P3** — Está no RÁDIO e é um dos dois que têm de reagir. Conte os segundos da vibração longa dele e escreva o número.
* **P4** — Também no rádio, mesma medição. Ele é o último a entrar e o primeiro a perder a vez: se só ele encurtar, anote isso separado — é diferente de o rádio inteiro encurtar.

**A armadilha.** O corte em meio segundo já foi medido nesta casa nos DOIS transportes, e a prova foi por dose: esticando o meio segundo da re-afirmação dos motores para oito, a vibração passou a durar oito segundos exatos. O conserto está escrito e ligado; a contagem em voz alta é o que diz se ele continua de pé. Segunda, e é do rádio: o comando vai numerado e conferido, e o controle descarta sozinho o que chegar fora de ordem — uma vibração que falha de vez em quando pelo rádio pode ser isso, e não aparece em campo nenhum da tela. Não deixe o alto-falante do P3 ou do P4 tocando durante o teste: pelo rádio o som e a vibração disputam o mesmo fio. Terceira: a medição com quatro controles na mesa não achou diferença entre cabo e rádio nesta família; quem fazia diferença era o Hefesto estar de pé ou parado. Uma diferença aqui é notícia nova. Quarta: o Testar agora fica LIGADO até alguém clicar em Parar, e enquanto ele está ligado a vibração do jogo naquele controle é ignorada — o Parar no começo é o que evita. Quinta: bateria baixa no rádio muda a força com que o motor responde; se um dos dois estiver quase descarregado, carregue antes de acusar o transporte. E o jogo enxerga só os quatro controles virtuais, aberto pelo atalho ou fora dele: desde 24/09 o Hefesto esconde os DualSense de verdade de todo programa menos ele — o botão, o toque e o movimento, além do que já escondia —, e só o Modo Nativo os devolve. Se ele listar mais de quatro, anote: o aparelho escapou do esconderijo, a vibração pode estar indo direto a ele por fora do Hefesto, e este teste não mede nada até isso ser resolvido.

---

## mapa-vibracao.rumble.habilitar-cabo — Habilitar o motor no firmware (enable vibration) · cabo

*Célula:* `vibracao.rumble.habilitar @ cabo`

**O que isto prova.** Prova que, nos dois controles do cabo, o Hefesto liga a autorização de vibração no controle — sem ela nenhum motor obedeceria a coisa nenhuma.

**Onde olhar.** Não há campo na tela que mostre essa autorização. O que se lê é a CONSEQUÊNCIA dela — o punho tremendo depois de um clique em Testar — e a resposta do próprio botão: ao ser clicado, ele pisca a borda por um segundo e meio, VERDE quando o Hefesto aplicou e LARANJA quando recusou. Na aba Vibração, coluna por coluna: a linha Modelo, que diz USB para o cabo e BT para o rádio; os três degraus da Força da vibração — Economia, Balanceado e Máximo —; as barras do Motor esquerdo e do Motor direito, com o número em %; e, no pé da coluna, «Testar» e «Parar». O Testar deixa aquele controle tremendo até o Parar. As mãos dizem o resto.

**Os passos.**

1. Feche o jogo, se houver algum aberto.
2. Clique na aba Vibração.
3. Confira na linha Modelo que as colunas do P1 e do P2 dizem USB.
4. Anote o degrau aceso e os dois números de motor de cada coluna.
5. Clique em Balanceado nas quatro colunas e arraste as oito barras de motor até 100.
6. Clique em Testar na coluna do P1.
7. Confira que o botão piscou a borda verde, e não laranja.
8. Pegue o P1 nas duas mãos.
9. Confira que ele treme e CONTINUA tremendo, e que os outros três estão parados na mesa.
10. Clique em Parar na coluna do P1.
11. Confira que o tremor parou na hora.
12. Faça na coluna do P2 a mesma volta: Testar, a borda verde, o tremor que continua, Parar.
13. Devolva o degrau e as barras de cada coluna ao que você anotou.

**Passa quando.** Nos dois do cabo, o Testar piscou verde e fez aquele controle — e só ele — tremer sem parar até o Parar; os outros três ficaram parados na mesa; e o Parar cortou o tremor na hora. Um controle que não treme, com Balanceado, as barras em 100 e o botão piscando verde, é a autorização faltando.

**Por controle.**

* **P1** — Está no CABO e é um dos dois que têm de reagir. Ele treme quando o Testar da coluna dele é clicado, e só então.
* **P2** — Também no cabo, mesma resposta esperada. Um dos dois tremendo e o outro não, com a mesma configuração, aponta para aquele aparelho — anote qual.
* **P3** — Está no RÁDIO e é testemunha: não toque nele. Ele não pode tremer quando o Testar clicado é o da coluna do P1 ou do P2. Se tremer, o comando foi para os quatro em vez de ir para o controle escolhido.
* **P4** — Também no rádio e também testemunha, com a mesma conferência — e é o mais propenso a receber comando de outro, por ser o último da fila.

**A armadilha.** Esta célula NÃO TEM MEDIÇÃO NENHUMA no mapa: a coluna que diz até onde a prova chegou está vazia, no cabo e no rádio. Ninguém mediu este aspecto até hoje, então o que você está fazendo aqui é o primeiro degrau — e um verde aqui não quer dizer mais do que «os motores obedecem». Segunda, e ela é do produto: das quatro chavinhas de autorização que o Hefesto deveria ligar, ele liga TRÊS. A quarta, a da vibração nova dos firmwares mais recentes, nunca sobe, e não aparece em campo nenhum da tela. Se um controle ficar completamente mudo nos dois transportes com tudo em 100, esse é o primeiro suspeito, e ele não é o seu gesto. Terceira: o Testar NÃO para sozinho — desde 07/09 ele fica ligado até o Parar; a ajuda do «Testar agora» ainda fala em meio segundo, e vale o que a mão sente. Quarta: se o botão piscar laranja, o Testar foi recusado e a frase da recusa não aparece na tela. As duas causas conhecidas são o Status em Desligado na aba Jogar — o Modo Nativo, em que quem manda nos motores é o jogo — e o controle da coluna ter saído entre o clique e agora. Nos dois casos o produto está recusando direito, e o teste não corre assim.

---

## mapa-vibracao.rumble.habilitar-radio — Habilitar o motor no firmware (enable vibration) · rádio

*Célula:* `vibracao.rumble.habilitar @ rádio`

**O que isto prova.** Prova que, nos dois controles do rádio, o Hefesto liga a autorização de vibração no controle — sem ela nenhum motor obedeceria a coisa nenhuma.

**Onde olhar.** Não há campo na tela que mostre essa autorização. O que se lê é a consequência — o punho tremendo depois de um clique em Testar — e a resposta do próprio botão: ele pisca a borda por um segundo e meio, VERDE quando o Hefesto aplicou e LARANJA quando recusou. Na aba Vibração, nas colunas do P3 e do P4, cuja linha Modelo tem de dizer BT: os três degraus da Força da vibração — Economia, Balanceado e Máximo —; as barras do Motor esquerdo e do Motor direito, com o número em %; e, no pé da coluna, «Testar» e «Parar». O Testar deixa aquele controle tremendo até o Parar. As mãos dizem o resto.

**Os passos.**

1. Feche o jogo, se houver algum aberto.
2. Clique na aba Vibração.
3. Confira na linha Modelo que as colunas do P3 e do P4 dizem BT.
4. Anote o degrau aceso e os dois números de motor de cada coluna.
5. Clique em Balanceado nas quatro colunas e arraste as oito barras de motor até 100.
6. Clique em Testar na coluna do P3.
7. Confira que o botão piscou a borda verde, e não laranja.
8. Pegue o P3 nas duas mãos.
9. Confira que ele treme e CONTINUA tremendo, e que os outros três estão parados na mesa.
10. Clique em Parar na coluna do P3.
11. Confira que o tremor parou na hora.
12. Faça na coluna do P4 a mesma volta: Testar, a borda verde, o tremor que continua, Parar.
13. Clique em Testar na coluna do P1, pegue-o e clique em Parar — é a comparação com o cabo.
14. Confira que o P1 tremeu do mesmo jeito.
15. Devolva o degrau e as barras de cada coluna ao que você anotou.

**Passa quando.** Nos dois do rádio, o Testar piscou verde e fez aquele controle — e só ele — tremer sem parar até o Parar; os outros três ficaram parados; e o Parar cortou na hora. O P1, no cabo, tremeu do mesmo jeito quando foi a vez dele. Um controle do rádio mudo enquanto o do cabo treme, com a mesma configuração e o botão piscando verde, é o achado deste teste.

**Por controle.**

* **P1** — Está no CABO e é testemunha, e também a comparação: ele não pode tremer quando o Testar clicado é o da coluna do P3 ou do P4, mas tem de tremer quando é o dele.
* **P2** — Também no cabo e também testemunha, com a mesma conferência. Use-o para repetir a comparação se o P1 der resposta estranha.
* **P3** — Está no RÁDIO e é um dos dois que têm de reagir. Treme quando o Testar da coluna dele é clicado, continua tremendo, e para na hora com o Parar.
* **P4** — Também no rádio, mesma resposta esperada. Se ele responder e o P3 não, ou o contrário, anote qual dos dois — é o aparelho, não o transporte.

**A armadilha.** Esta célula NÃO TEM MEDIÇÃO NENHUMA no mapa: a coluna que diz até onde a prova chegou está vazia, nos dois transportes. Você está fazendo o primeiro degrau, e um verde aqui só diz que os motores obedecem. Segunda: das quatro chavinhas de autorização, o produto liga três — a quarta, a da vibração nova dos firmwares mais recentes, nunca sobe, e é igual nos dois transportes de propósito. Ela não aparece em campo nenhum da tela, e é a primeira suspeita para um controle mudo em toda parte. Terceira: no rádio o comando vai numerado e conferido, e o controle descarta calado o que chegar fora de ordem — um Testar que não produz tremor nenhum, uma vez só, pede uma segunda tentativa antes de virar defeito. Não deixe o alto-falante do P3 ou do P4 tocando durante o teste: pelo rádio o som e a vibração disputam o mesmo fio. Quarta: o Testar NÃO para sozinho — desde 07/09 ele fica ligado até o Parar, e a ajuda do «Testar agora» ainda fala em meio segundo. Quinta: se o botão piscar laranja, o Testar foi recusado e a frase da recusa não aparece na tela: ou o Status está em Desligado na aba Jogar — o Modo Nativo, em que quem manda nos motores é o jogo —, ou o controle da coluna saiu entre o clique e agora. Nos dois casos o produto está recusando direito.

---

## mapa-vibracao.rumble.passthrough-cabo — Rumble do JOGO roteado pelo Hefesto (vpad → físico) · cabo

*Célula:* `vibracao.rumble.passthrough @ cabo`

**O que isto prova.** Prova que a vibração que o jogo manda para UM jogador chega ao controle daquele jogador quando ele está no cabo — e não chega a mais nenhum.

**Onde olhar.** Na aba Vibração, coluna por coluna — a linha Modelo diz USB para o cabo e BT para o rádio. No alto de cada coluna, o desenho do controle acende em laranja o punho que está recebendo força agora — é ele que diz, na tela, qual controle recebeu. Parando o mouse em cima do número ao lado da barra de um motor, a dica diz, com o jogo vibrando, «O jogo pediu … de 255 neste motor agora.»; onde o jogo não está pedindo nada, ela diz a conta da coluna, «Este motor a …%, força …% — sai …% do que o jogo pedir.», e é essa troca de frase que torna o silêncio dos outros três mensurável. E os quatro controles na mesa dizem o resto: um controle solto no tampo chacoalha de forma audível.

**Os passos.**

1. Clique na aba Vibração.
2. Clique na aba Jogar e confira que o Status está em Ligado.
3. Volte à aba Vibração.
4. Clique em Parar em cada uma das quatro colunas, para devolver ao jogo qualquer vibração presa num teste anterior.
5. Anote o degrau aceso na Força da vibração e os dois números de motor de cada coluna.
6. Clique em Balanceado nas quatro colunas e arraste as oito barras de motor até 100.
7. Abra o jogo com os quatro jogadores dentro da partida.
8. Apoie os quatro controles na mesa, separados uns dos outros, sem ninguém segurando.
9. Provoque no jogo uma vibração só para o jogador do P1 — um dano levado só por ele.
10. Confira, olhando e escutando, que só o P1 chacoalhou na mesa, e que só o desenho da coluna do P1 acendeu em laranja.
11. Provoque o dano de novo e, com ele correndo, pare o mouse no número ao lado da barra do Motor esquerdo da coluna do P1 e depois no da coluna do P2.
12. Confira que a dica do P1 diz «O jogo pediu … de 255 neste motor agora.», e que a do P2 diz a conta da coluna, «Este motor a …», porque nada foi pedido a ele.
13. Faça a mesma volta com o jogador do P2, conferindo agora a coluna do P1 como a que ficou calada.
14. Provoque uma vibração para o jogador do P3 e depois uma para o do P4.
15. Confira que o P1 e o P2 ficam parados nas duas.
16. Devolva o degrau e as barras de cada coluna ao que você anotou.

**Passa quando.** A vibração de cada jogador chegou ao controle daquele jogador e a mais nenhum: os outros três ficaram parados na mesa e apagados no desenho. E a tela bateu com quem levou o dano nos DOIS sentidos — na coluna de quem levou, o punho acendeu em laranja e a dica do motor trouxe o número que o jogo pediu; nas outras três, o punho ficou apagado e a dica disse só a conta da coluna.

**Por controle.**

* **P1** — Está no CABO e é um dos dois que têm de reagir. Ele chacoalha quando o jogador dele leva dano, e o desenho da coluna dele acende.
* **P2** — Também no cabo, mesma resposta. Um dos dois recebendo e o outro não, com a mesma partida, aponta para aquele controle — anote qual.
* **P3** — Está no RÁDIO e é testemunha: tem de ficar parado quando a vibração é do jogador do P1 ou do P2. Se chacoalhar junto, a vibração perdeu o endereço.
* **P4** — Também no rádio e também testemunha, com a mesma conferência. Ele é o último a entrar, e é nele que a falta de endereço costuma aparecer primeiro.

**A armadilha.** São DOIS retratos do MESMO defeito, e os dois enganam de jeitos opostos. Se os quatro chacoalharem juntos quando só um levou dano, a vibração perdeu o endereço e foi para os quatro — é o defeito clássico desta célula. Mas se o controle CERTO ficar mudo enquanto a dica do motor daquela coluna diz «O jogo pediu …», é o mesmo endereço perdido: hoje o Hefesto prefere descartar a espalhar, e o descarte não aparece em campo nenhum da tela. Nos dois casos o que fura é a comparação entre o que a COLUNA daquele jogador diz e o que o controle dele fez. Segunda, e é o tamanho da prova: no mapa esta célula parou em MONTOU — está provado que o Hefesto MONTA o comando, e não que o aparelho obedeceu. O que você está fazendo aqui é o degrau seguinte; um vermelho aqui não é regressão, é a resposta que faltava. Terceira: controle apoiado no mesmo tampo transmite o tremor do vizinho — deixe-os separados, ou levante um de cada vez para decidir. Quarta: o Testar agora fica LIGADO até alguém clicar em Parar, e com ele ligado a vibração do jogo naquele controle é ignorada — o Parar em cada coluna, no começo, é o que evita. Quinta: o jogo enxerga só os quatro controles virtuais, aberto pelo atalho ou fora dele: desde 24/09 o Hefesto esconde os DualSense de verdade de todo programa menos ele — o botão, o toque e o movimento, além do que já escondia —, e só o Modo Nativo os devolve. Se ele listar mais de quatro, anote: o aparelho escapou do esconderijo, a vibração pode estar indo direto a ele por fora do Hefesto — aí nem a coluna nem a barra dizem nada sobre ela —, e este teste não mede nada até isso ser resolvido.

---

## mapa-vibracao.rumble.passthrough-radio — Rumble do JOGO roteado pelo Hefesto (vpad → físico) · rádio

*Célula:* `vibracao.rumble.passthrough @ rádio`

**O que isto prova.** Prova que a vibração que o jogo manda para um jogador chega ao controle dele quando ele está no rádio — a metade desta célula que nunca foi medida.

**Onde olhar.** Na aba Vibração, nas colunas do P3 e do P4 — a linha Modelo delas diz BT, que é o rádio. No alto de cada coluna, o desenho acende em laranja o punho que está recebendo força agora. Parando o mouse em cima do número ao lado da barra de um motor, a dica diz, com o jogo vibrando, «O jogo pediu … de 255 neste motor agora.»; onde o jogo não está pedindo nada, ela diz a conta da coluna, «Este motor a …%, força …% — sai …% do que o jogo pedir.». E os quatro controles na mesa dizem o resto: um controle solto no tampo chacoalha de forma audível.

**Os passos.**

1. Clique na aba Vibração.
2. Clique na aba Jogar e confira que o Status está em Ligado.
3. Volte à aba Vibração.
4. Confira na linha Modelo que as colunas do P3 e do P4 dizem BT.
5. Clique em Parar em cada uma das quatro colunas.
6. Anote o degrau aceso na Força da vibração e os dois números de motor de cada coluna.
7. Clique em Balanceado nas quatro colunas e arraste as oito barras de motor até 100.
8. Abra o jogo com os quatro jogadores dentro da partida.
9. Apoie os quatro controles na mesa, separados uns dos outros, sem ninguém segurando.
10. Provoque no jogo uma vibração só para o jogador do P3.
11. Confira, olhando e escutando, que só o P3 chacoalhou na mesa, e que só o desenho da coluna do P3 acendeu em laranja.
12. Provoque o dano de novo e, com ele correndo, pare o mouse no número ao lado da barra do Motor esquerdo da coluna do P3 e depois no da coluna do P4.
13. Confira que a dica do P3 diz «O jogo pediu … de 255 neste motor agora.», e que a do P4 diz a conta da coluna, «Este motor a …».
14. Faça a mesma volta com o jogador do P4, conferindo agora a coluna do P3 como a que ficou calada.
15. Provoque uma vibração para o jogador do P1.
16. Confira que o P1 chacoalhou e que o P3 e o P4 ficaram parados.
17. Anote, com estas palavras, se os dois do rádio chacoalharam ou ficaram mudos.
18. Devolva o degrau e as barras de cada coluna ao que você anotou.

**Passa quando.** A vibração do jogador do P3 chegou ao P3 e a mais nenhum, e a do P4 chegou ao P4; os outros três ficaram parados na mesa e apagados no desenho em cada rodada. Na coluna de quem levou o dano o punho acendeu e a dica do motor trouxe o número pedido; nas outras três o punho ficou apagado e a dica disse só a conta da coluna. E os dois do rádio responderam como o P1, no cabo, respondeu.

**Por controle.**

* **P1** — Está no CABO e é testemunha, e é também a comparação: ele não pode chacoalhar quando a vibração é do jogador do P3, mas tem de chacoalhar quando é a dele — é isso que separa «o jogo não pediu» de «o rádio não recebeu».
* **P2** — Também no cabo e também testemunha, com a mesma dupla função. Use-o para repetir a comparação se o P1 der resposta estranha.
* **P3** — Está no RÁDIO e é um dos dois que têm de reagir. É a metade desta célula que ninguém nunca mediu: escreva o que aconteceu com ele, mesmo que tenha sido nada.
* **P4** — Também no rádio, mesma medição. Se um dos dois receber e o outro não, anote qual — é diferente de o rádio inteiro ficar mudo.

**A armadilha.** A metade do rádio desta célula está EM BRANCO no mapa: ninguém nunca mediu isto por rádio, e o branco não quer dizer «não funciona», quer dizer que não houve resposta. Então aqui um mudo é resultado, não falha sua — anote com todas as letras. E há história: houve um tempo em que o comando montado para o rádio saía malformado e o controle o descartava inteiro, calado; o rádio vibrava zero e nada na tela dizia isso. O comando de hoje sai certo, mas o aparelho nunca confirmou por este caminho. Se o P3 e o P4 ficarem mudos enquanto a dica do motor das colunas deles diz «O jogo pediu …», e o P1 chacoalhar no mesmo teste, é exatamente essa pergunta que você acabou de responder. Segunda: o defeito irmão anda ao contrário — se os QUATRO chacoalharem quando só um levou dano, a vibração perdeu o endereço e foi para os quatro. Terceira: controle apoiado no mesmo tampo transmite o tremor do vizinho; separe-os, ou levante um de cada vez. Quarta: bateria baixa no rádio abaixa a força do motor — um chacoalho fraco demais para ouvir não é o mesmo que mudo; levante o controle e sinta antes de decidir. Não deixe o alto-falante do P3 ou do P4 tocando: pelo rádio o som e a vibração disputam o mesmo fio. Quinta: o Testar ligado numa coluna faz o jogo ser ignorado naquele controle até o Parar — é o que o Parar no começo evita. E o jogo enxerga só os quatro controles virtuais, aberto pelo atalho ou fora dele: desde 24/09 o Hefesto esconde os DualSense de verdade de todo programa menos ele — o botão, o toque e o movimento, além do que já escondia —, e só o Modo Nativo os devolve. Se ele listar mais de quatro, anote: o aparelho escapou do esconderijo, a vibração pode estar indo direto a ele por fora do Hefesto, e este teste não mede nada até isso ser resolvido.

---

## mapa-audio.alto_falante-radio — Alto-falante do controle — som saindo · rádio

*Célula:* `audio.alto_falante @ rádio`

**O que isto prova.** Prova que o som do computador sai mesmo pelo alto-falante dos dois controles que estão no rádio — o caminho que existe nesta casa desde 10/09/2026 — e entrega as duas metades que faltam para o mapa fechar esta célula: o negativo de rota e a escuta cega. A primeira metade já foi feita e não se repete: o som saiu do plástico por rádio, setenta segundos contínuos, com o seu ouvido. O que falta é provar que ele saiu de LÁ e não de outro lugar.

**Onde olhar.** Na aba Controles do Hefesto. Clique na linha de um controle e o cartão dele abre (o que estava aberto fecha sozinho). Dentro do cartão, o bloco Alto-falante: o selo ATIVO ao lado do nome, as barrinhas que se mexem quando entra som naquele controle, o deslizante de volume com o número ao lado, o botão ♪ — que CALA o alto-falante —, e os três botões de rota: «Efeitos do Jogo no Controle, Áudio da TV na TV» (o de sempre: só o que o jogo mandar para aquele controle), «Efeitos do Jogo e Áudio da TV no Controle» (tudo o que a máquina toca cai também no controle, e continua saindo na TV) e «Tudo na TV e Nada no Controle» (o alto-falante do controle para de tocar). Mas quem responde este teste é o seu OUVIDO, encostado no alto-falante do próprio controle: são nove furinhos em duas fileiras, na frente do DualSense, logo abaixo e entre os dois analógicos. E quem responde a segunda metade é outra pessoa: alguém precisa clicar por você, sem dizer o que clicou.

**Os passos.**

1. Clique na aba Controles.
2. Confira na fita do topo que o P3 e o P4 dizem BT e que o P1 e o P2 dizem USB.
3. Clique na linha do P3 para abrir o cartão dele.
4. Arraste o deslizante de volume do bloco Alto-falante do P3 até o fim da direita.
5. Confira que o número ao lado dele diz 100.
6. Clique em «Efeitos do Jogo e Áudio da TV no Controle» no bloco do P3.
7. Toque no computador um som bem marcado e curto, que se reconheça de ouvido — um toque de aviso, não uma música.
8. Encoste o ouvido no P3 e escute se o som sai por ali.
9. Encoste o ouvido no P4, depois no P1 e no P2, e confirme que os três estão mudos.
10. Agora o NEGATIVO DE ROTA, e ele é o coração deste teste: clique em «Tudo na TV e Nada no Controle» no bloco do P3.
11. Toque o MESMO som e encoste o ouvido no P3: ele sai na TV, e o P3 tem de ficar MUDO.
12. Clique de novo em «Efeitos do Jogo e Áudio da TV no Controle» e toque o mesmo som, para confirmar que ele voltou a sair do P3.
13. Chame outra pessoa e peça que ela faça, sem você ver a tela e sem falar nada, seis passadas em ordem embaralhada: três com «Efeitos do Jogo e Áudio da TV no Controle» aceso no P3 e três com «Tudo na TV e Nada no Controle», tocando o mesmo som em cada uma.
14. A cada passada, com o ouvido no P3, diga em voz alta «controle» ou «só TV», e peça que ela anote a sua resposta ao lado do botão que estava aceso.
15. Clique em «Efeitos do Jogo no Controle, Áudio da TV na TV» no bloco do P3, para devolvê-lo ao de sempre — não pule este passo.
16. Clique na linha do P4 e faça nele a mesma volta — volume em 100, o som no controle, o negativo de rota e a devolução ao botão de sempre —, com o P3 agora de testemunha muda.

**Passa quando.** Sai som pelo alto-falante do P3 e pelo do P4, os dois que estão no rádio. O mesmo som, com «Tudo na TV e Nada no Controle», sai na TV e NÃO sai de nenhum dos dois — esse é o negativo de rota, e sem ele o teste não passa mesmo que você tenha ouvido o som cem vezes. E as seis passadas cegas batem SEIS de seis: você acertou onde o som estava tocando sem saber o que a outra pessoa clicou. Cinco de seis já não passa: uma errada é ruído ou é vazamento, e nos dois casos a resposta é repetir.

**Por controle.**

* **P3** — No rádio, e é o alvo. Ele é quem toca, quem cala no negativo de rota e quem você escuta nas seis passadas cegas.
* **P4** — No rádio, e é a segunda prova do caminho: se só um dos dois tocar, o problema é daquele controle e não do rádio — anote qual falhou. Ele também é testemunha enquanto o P3 toca: se os dois tocarem juntos, o comando pegou o transporte inteiro em vez do controle escolhido, e isso é achado.
* **P1** — No cabo, e é TESTEMUNHA: você não mexe no bloco dele. O som do P3 não pode sair dele.
* **P2** — No cabo, e é a segunda testemunha. Mesmo gesto do P1.

**A armadilha.** O selo ATIVO do alto-falante NÃO apaga com «Tudo na TV e Nada no Controle», e isso é decisão dela: o selo fala do canal, não da rota. Quem responde o negativo de rota é o seu ouvido. O ♪ não é confirmação: ele CALA o alto-falante, e as barrinhas ficam no chão com ele calado — se você clicou nele sem querer, clique de novo antes de concluir que o rádio não toca. Segunda, e é regra desta casa com nome: ninguém pode concluir, de um canal responder, que ele FAZ o que a gente esperava dele. O canal do rádio aceitava bytes muito antes de tocar um som, e foi por isso que a casa mirou no report errado durante semanas. Terceira: «Efeitos do Jogo e Áudio da TV no Controle» deixa o som da máquina saindo também pelo controle até alguém voltar ao botão de sempre — esquecer disso faz o próximo teste ouvir o PC no controle e parece defeito sem ser. Não dispare vibração no P3 ou no P4 enquanto testa: pelo rádio o som e a vibração disputam o mesmo fio. E quarta, que é a razão das seis passadas cegas: você SABE o que quer ouvir, e ouvido que sabe o que quer ouvir ouve. A escuta cega existe porque a sua própria expectativa é a fonte de erro mais provável deste teste — e ela já derrubou uma medição desta casa antes.

---

## mapa-audio.saida_dedicada.payload_do_degrau-radio — Saída de áudio por rádio — o CONTEÚDO do payload dos degraus · rádio

*Célula:* `audio.saida_dedicada.payload_do_degrau @ rádio`

**O que isto prova.** Prova que o que viaja DENTRO do canal do rádio é som de verdade — não que o canal aceitou bytes. São duas perguntas diferentes, e confundi-las custou semanas a esta casa: o aparelho respondia de bom grado a um report que não carregava áudio nenhum. Este teste separa as duas ouvindo o CONTEÚDO: um som que você reconhece sem hesitar, saindo com a forma que você mandou.

**Onde olhar.** Na aba Controles, no cartão do P3 e no do P4, bloco Alto-falante: o volume com o número ao lado, o ♪ — que cala o alto-falante — e os três botões de rota, dos quais este teste usa dois: «Efeitos do Jogo e Áudio da TV no Controle», que põe o som da máquina no controle sem tirá-lo da TV, e «Efeitos do Jogo no Controle, Áudio da TV na TV», o de sempre. O conteúdo do que viaja não tem tela e não vai ter — ele se prova com o ouvido, comparando o que saiu com o que foi mandado. Como o som continua saindo na TV, a TV tem de estar calada pelo controle remoto dela, senão o seu ouvido entende a frase pela TV e não pelo controle.

**Os passos.**

1. Clique na aba Controles.
2. Confira na fita do topo que o P3 e o P4 dizem BT.
3. Escolha TRÊS sons bem diferentes um do outro: um grave longo, um agudo curto e uma voz falando uma frase que você reconheça.
4. Abaixe o volume da própria TV até zero, pelo controle remoto dela.
5. Clique na linha do P3 e arraste o volume do bloco Alto-falante até 100.
6. Clique em «Efeitos do Jogo e Áudio da TV no Controle» no bloco do P3.
7. Toque o grave longo e escute com o ouvido no P3.
8. Toque o agudo curto e escute com o ouvido no P3.
9. Toque a voz e escute com o ouvido no P3: você tem de entender a frase, não só ouvir que tem som.
10. Anote, para cada um dos três, se o que saiu era o MESMO som — e não um estalo, um chiado ou um pedaço dele.
11. Arraste o volume do P3 até 30 e toque a voz de novo: ela tem de sair mais baixa e continuar compreensível.
12. Arraste o volume do P3 de volta a 100 e deixe a voz tocando por dois minutos seguidos, escutando o fim: ela não pode ter engasgado, cortado nem virado chiado no meio do caminho.
13. Clique em «Efeitos do Jogo no Controle, Áudio da TV na TV» no bloco do P3.
14. Clique na linha do P4 e faça nele a mesma volta: volume em 100, o som no controle, os três sons, o volume em 30, os dois minutos e a devolução ao botão de sempre.
15. Devolva o volume da TV ao de antes.

**Passa quando.** Os três sons saem reconhecíveis pelos dois controles do rádio, e a voz é COMPREENSÍVEL — não basta sair barulho. O volume em 30 abaixa o som sem quebrá-lo. E os dois minutos seguidos terminam sem engasgo: um caminho que entrega dez segundos e morre no terceiro minuto não entregou o conteúdo, entregou uma amostra.

**Por controle.**

* **P3** — No rádio, e é o alvo. Os três sons, o volume baixo e os dois minutos seguidos são nele.
* **P4** — No rádio, e faz a mesma volta. Ele é a segunda prova de que o caminho é do RÁDIO e não daquele controle.
* **P1** — No cabo, e é testemunha muda. No cabo o som é uma saída comum do computador e não passa por este canal: se ele tocar junto, o que está tocando não é o que este teste mede.
* **P2** — No cabo, e é a segunda testemunha. Mesma leitura do P1.

**A armadilha.** A pergunta desta linha NÃO é «o canal responde» — é «o que viaja dentro dele é som». Duas fontes de fora descrevem o formato deste conteúdo byte a byte, e as duas DIVERGEM entre si; e as duas erraram o report. Por isso a leitura de fonte não vale como resposta aqui, por mais detalhada que seja: só o ouvido responde. Segunda: a voz é o som que decide, e não por gosto — um estalo, um chiado e um engasgo todos soam como «tem som saindo», e só a fala mostra se o que chegou foi o som ou um pedaço dele. Terceira: com a TV só com o volume baixo, e não zerado, a frase que você entende pode ter vindo dela — zere pelo controle remoto da TV, e não pelo volume do computador: o som que chega ao controle sai da mesma saída, e mexer nela mede outra coisa. Quarta: dois minutos parecem exagero e não são; um trecho longo é o que deixa uma falha de cadência aparecer. Não dispare vibração no P3 ou no P4 durante o teste: pelo rádio o som e a vibração disputam o mesmo fio.

---

## mapa-luz.led_jogador.brilho-cabo — LED de jogador — brilho de hardware (3 degraus) · cabo

*Célula:* `luz.led_jogador.brilho @ cabo`

**O que isto prova.** Prova, no cabo, o que o produto faz hoje com o brilho das lâmpadas de numeração do controle — as cinco luzinhas brancas embaixo do touchpad que dizem quem é P1, P2, P3 e P4. O aparelho sabe mudar esse brilho em três degraus, e isso foi medido; o produto ainda não liga o bit que autoriza esse byte, e por isso o deslizante de Brilho do Hefesto não chega a elas. Esta é a metade que o teste mede e a bancada registra.

**Onde olhar.** Na aba Iluminação do Hefesto, uma coluna por controle — a fita do topo não escolhe nada aqui. Em cada coluna, a linha Modelo diz o número, a cor e a palavra do transporte (USB é o cabo, BT é o rádio), e a linha Brilho tem o deslizante da barra daquele controle, com o número em % ao lado. E no PLÁSTICO: as lâmpadas de numeração ficam na frente do DualSense, embaixo do touchpad, em fileira. Elas NÃO são a barra de luz colorida das duas tiras ao lado do touchpad — a barra é outra grandeza, obedece a este deslizante por outro caminho, e aqui ela entra só como testemunha de que o deslizante chegou ao aparelho.

**Os passos.**

1. Feche a Steam por inteiro.
2. Clique na aba Iluminação.
3. Confira na linha Modelo que as colunas do P1 e do P2 dizem USB.
4. Anote o número do Brilho da coluna do P1.
5. Olhe as lâmpadas de numeração do P1 no plástico e guarde na memória o brilho delas.
6. Arraste o Brilho da coluna do P1 até o mínimo.
7. Confira se as lâmpadas de numeração do P1 mudaram, e anote.
8. Arraste o Brilho da coluna do P1 até o máximo.
9. Confira de novo as lâmpadas de numeração do P1, e anote.
10. Confira se a barra de luz colorida do P1 mudou entre as duas pontas do deslizante, e anote.
11. Devolva o Brilho do P1 ao número anotado.
12. Faça na coluna do P2 a mesma volta: as duas pontas do Brilho, as lâmpadas e a barra olhadas separadamente, e o número devolvido.
13. Anote as quatro respostas lado a lado: lâmpadas do P1, barra do P1, lâmpadas do P2, barra do P2.

**Passa quando.** As lâmpadas de numeração NÃO mudam de brilho em nenhuma das duas pontas do deslizante, nos dois controles do cabo — e a barra de luz colorida muda. É esse contraste que é a entrega: ele mostra que o deslizante chega ao aparelho (a barra prova) e que o degrau das lâmpadas não chega (elas provam). Se as lâmpadas MUDAREM, o produto passou a ligar o bit desde a última medição, e isso é achado: anote e avise, porque o mapa desta célula muda com essa resposta.

**Por controle.**

* **P1** — No cabo, e é o alvo. As duas pontas do deslizante, lâmpadas e barra olhadas separadamente.
* **P2** — No cabo, e é a segunda prova. Se o P1 e o P2 responderem diferente, o problema é de um controle e não do caminho — anote qual.
* **P3** — No rádio, e não entra neste teste: ele tem a volta dele, na linha do rádio. Confira só que as lâmpadas dele não mexeram enquanto você arrastava o Brilho do P1.
* **P4** — No rádio, e também não entra aqui, com a mesma conferência do P3.

**A armadilha.** A barra de luz colorida e as lâmpadas de numeração são DUAS grandezas, e confundi-las é o erro que este teste existe para não repetir: elas ficam a centímetros uma da outra no mesmo plástico, e a barra obedece ao deslizante. Quem olhar a barra vai concluir que o brilho funciona — e o brilho que esta linha mede continua inerte. Olhe as luzinhas brancas da numeração, e só elas. Segunda: o brilho das lâmpadas tem TRÊS degraus no aparelho, não uma rampa contínua; se um dia elas obedecerem, a mudança vai ser em saltos, e um salto entre dois valores vizinhos pode passar despercebido — por isso os passos vão direto ao mínimo e ao máximo, nunca ao meio. Terceira: com a Steam aberta, a barra pode ficar apagada e não responder ao Brilho — é a Steam segurando o controle, e não este teste; por isso ela começa fechada. Quarta: o Brilho grava no perfil ao soltar, sem esperar o Salvar Perfil — por isso o número se anota e se devolve. E nada disso aparece na tela, nem vai aparecer: a dívida é nossa e fica no mapa, por ordem dela de 07/09/2026 — o produto não confessa dívida nossa para quem está usando.

---

## mapa-luz.led_jogador.brilho-radio — LED de jogador — brilho de hardware (3 degraus) · rádio

*Célula:* `luz.led_jogador.brilho @ rádio`

**O que isto prova.** O mesmo que a linha do cabo, e no rádio: o aparelho sabe mudar o brilho das lâmpadas de numeração em três degraus, e o produto ainda não liga o bit que autoriza o byte, então o deslizante de Brilho do Hefesto não chega a elas. A razão de ser um teste próprio é que o envelope é outro — no rádio o degrau viaja noutro report, com uma conta de verificação no fim —, e um caminho que funciona no cabo não prova nada sobre o outro.

**Onde olhar.** Na aba Iluminação do Hefesto, uma coluna por controle — a fita do topo não escolhe nada aqui. Nas colunas do P3 e do P4, a linha Modelo tem de dizer BT, que é o rádio; a linha Brilho tem o deslizante da barra daquele controle, com o número em % ao lado. E no PLÁSTICO: as lâmpadas de numeração, na frente do DualSense, embaixo do touchpad, em fileira. Não é a barra de luz colorida das duas tiras ao lado do touchpad — a barra entra aqui só como testemunha de que o deslizante chegou ao aparelho.

**Os passos.**

1. Feche a Steam por inteiro.
2. Clique na aba Iluminação.
3. Confira na linha Modelo que as colunas do P3 e do P4 dizem BT.
4. Anote o número do Brilho da coluna do P3.
5. Olhe as lâmpadas de numeração do P3 no plástico e guarde na memória o brilho delas.
6. Arraste o Brilho da coluna do P3 até o mínimo.
7. Confira se as lâmpadas de numeração do P3 mudaram, e anote.
8. Arraste o Brilho da coluna do P3 até o máximo.
9. Confira de novo as lâmpadas de numeração do P3, e anote.
10. Confira se a barra de luz colorida do P3 mudou entre as duas pontas do deslizante, e anote.
11. Confira que as lâmpadas do P1 e do P2, que estão no cabo, não mexeram enquanto você arrastava o Brilho do P3.
12. Devolva o Brilho do P3 ao número anotado.
13. Faça na coluna do P4 a mesma volta: as duas pontas do Brilho, as lâmpadas e a barra olhadas separadamente, as testemunhas do cabo e o número devolvido.
14. Anote as respostas lado a lado: lâmpadas do P3, barra do P3, lâmpadas do P4, barra do P4, e as testemunhas do cabo.

**Passa quando.** As lâmpadas de numeração NÃO mudam de brilho em nenhuma das duas pontas do deslizante, nos dois controles do rádio — e a barra de luz colorida muda. As lâmpadas do P1 e do P2 ficam paradas o tempo todo: o deslizante de um controle não pode mexer no outro. Se as lâmpadas do P3 ou do P4 MUDAREM, o produto passou a ligar o bit desde a última medição — anote e avise, porque o mapa desta célula muda com essa resposta.

**Por controle.**

* **P3** — No rádio, e é o alvo. As duas pontas do deslizante, lâmpadas e barra olhadas separadamente.
* **P4** — No rádio, e é a segunda prova do envelope do rádio. Se o P3 e o P4 responderem diferente, o problema é de um controle.
* **P1** — No cabo, e é TESTEMUNHA: você não mexe na coluna dele. As lâmpadas dele não podem reagir ao deslizante do P3.
* **P2** — No cabo, e é a segunda testemunha. Mesma leitura do P1.

**A armadilha.** A mesma da linha do cabo, e uma a mais: no rádio o report leva uma conta de verificação no fim, e um envelope com essa conta errada é DESCARTADO pelo aparelho em silêncio. Ou seja, no rádio o «nada aconteceu» tem duas causas possíveis — o bit não foi ligado (que é o que esta casa sabe) ou o envelope foi recusado inteiro (que ninguém mediu). As duas se parecem exatamente na sua mão, e é por isso que a barra é conferida: se a BARRA muda, o envelope chegou, e então o silêncio das lâmpadas é do bit. Se a barra também não mudar, você está olhando outro defeito, mais grave, e este teste não é quem responde por ele — anote e pare. Com a Steam aberta a barra pode ficar apagada e não responder, e aí ela deixa de servir de testemunha: por isso a Steam começa fechada. E o Brilho grava no perfil ao soltar — anote e devolva.

---

## mapa-audio.microfone.ganho-cabo — Microfone · ganho de entrada · cabo

*Célula:* `audio.microfone.ganho @ cabo`

**O que isto prova.** Prova que o trilho Ganho do bloco Microfone muda de verdade o quanto a placa de som do controle amplifica a sua voz, e que o número que a tela mostra é o que a placa devolveu, não o que foi pedido. O ganho é da PLACA DE SOM do controle, e não do firmware do DualSense — por isso ele só existe no cabo.

**Onde olhar.** Na aba Controles, no cartão de um controle ligado pelo cabo — na fita do topo, o chip dele diz USB. Dentro do cartão, o bloco Microfone: o selo ATIVO ou DESLIGADO ao lado do nome; as barrinhas que se mexem com a sua voz; o trilho Volume, com o número e o 🎙 ao lado; e, embaixo, o trilho Ganho, com o número em dB, de 0 a +48. O 🎙 é o retorno: aceso em verde, você se ouve pela saída de som do computador, com o volume e o ganho do cartão já aplicados, até clicar nele de novo. O ? ao lado do Microfone explica a diferença entre os dois trilhos.

**Os passos.**

1. Clique na aba Controles.
2. Confira na fita do topo que o P1 e o P2 dizem USB.
3. Clique na linha do P1 para abrir o cartão dele.
4. Confira que o selo do Microfone do P1 diz ATIVO — se disser DESLIGADO, aperte o botão de microfone no próprio P1.
5. Anote o número do Ganho do P1.
6. Clique no 🎙 do P1.
7. Confira que ele ficou verde.
8. Fale uma frase no P1 e guarde a altura da sua voz no retorno e das barrinhas.
9. Arraste o Ganho do P1 até perto de +20 dB e solte.
10. Espere dois segundos sem clicar em nada.
11. Confira que o número ficou perto de +20 e não voltou sozinho.
12. Fale a mesma frase.
13. Confira que a voz voltou mais baixa no retorno e que as barrinhas ficaram mais curtas.
14. Clique no 🎙 de novo para desligar o retorno.
15. Clique na linha do P2 e confira que o Ganho dele continua no número de antes — mexer no P1 não pode mexer nele.
16. Volte ao cartão do P1 e arraste o Ganho de volta ao número anotado.
17. Faça no P2 a mesma volta — o retorno, a frase, o Ganho em +20, a frase de novo e o número devolvido —, com o P1 de testemunha.

**Passa quando.** O número do Ganho fica no valor novo e não volta sozinho; com a mesma frase, a voz no retorno e as barrinhas baixam junto com o ganho; e o Ganho do outro controle não se mexe. Se o número saltar de volta ao antigo, o que a tela mostra é o pedido e não a resposta da placa.

**Por controle.**

* **P1** — Está no cabo, e é o alvo. O arrasto, a frase antes e depois, e o número que tem de ficar.
* **P2** — Também no cabo, e é a segunda prova — e, enquanto você mexe no P1, a testemunha de que o ganho é de um controle só.
* **P3** — Está no rádio, testemunha: o trilho Ganho dele fica cinza, porque pelo rádio não há placa de som onde o ganho exista. Você não mexe nele.
* **P4** — Também no rádio, com o trilho cinza, mesma leitura do P3.

**A armadilha.** No mapa esta célula parou em MONTOU: o caminho está escrito e a leitura da placa foi medida, mas o arrasto com o seu ouvido nunca foi feito — é o degrau que falta, e é este teste. Ganho e Volume são dois trilhos diferentes: o Ganho é o quanto a placa amplifica o que entra; o Volume é o quanto desse som o produto entrega ao PC. Mexer num esperando o efeito do outro confunde a leitura. O 🎙 não cala o microfone: ele liga o retorno, e só o clique seguinte o apaga; calar é o botão de microfone do próprio controle. Se você não ouvir o retorno, confira se a saída de som do computador está alta antes de concluir qualquer coisa. E o número que salta de volta ao antigo é o defeito que esta célula caça: a tela mostrando o pedido em vez da resposta da placa.

---

## mapa-audio.microfone.ganho-radio — Microfone · ganho de entrada · rádio

*Célula:* `audio.microfone.ganho @ rádio`

**O que isto prova.** Prova que pelo rádio o produto diz que o ganho não se alcança, e diz por quê — em vez de oferecer um trilho que não faz nada. Pelo rádio o microfone chega como som já digitalizado, pela ponte do Hefesto: não existe placa de som onde o elemento de ganho more. O cinza com a razão é a entrega desta célula.

**Onde olhar.** Na aba Controles, no cartão de um controle ligado pelo rádio — na fita do topo, o chip dele diz BT. Dentro do cartão, o bloco Microfone: o trilho de cima é o Volume, e o de baixo é o Ganho. Pelo rádio o trilho Ganho fica cinza, e o ? ao lado dele, com o mouse parado em cima, traz a razão. No cartão de um controle do cabo o mesmo trilho fica normal — é o contraste.

**Os passos.**

1. Clique na aba Controles.
2. Confira na fita do topo que o P3 e o P4 dizem BT e que o P1 e o P2 dizem USB.
3. Clique na linha do P3 para abrir o cartão dele.
4. Confira que o trilho Ganho do P3 está cinza.
5. Pare o mouse em cima do ? ao lado do Ganho do P3.
6. Leia a frase: ela tem de dizer que o ganho é do aparelho, que só o cabo o alcança, e que pelo rádio o microfone chega sem placa de som.
7. Tente arrastar o trilho cinza do Ganho do P3.
8. Confira que o número dele não mudou.
9. Clique na linha do P4 e faça nele a mesma volta: o cinza, a frase do ? e o arrasto que não muda nada.
10. Clique na linha do P1.
11. Confira que o Ganho do P1 NÃO está cinza e mostra um número em dB.

**Passa quando.** Nos dois do rádio, o trilho Ganho está cinza, o ? explica que pelo rádio não há placa de som onde o ganho exista, e o arrasto não muda número nenhum. No P1, no cabo, o mesmo trilho está normal. O que NÃO pode acontecer é o trilho do rádio parecer normal e não fazer nada.

**Por controle.**

* **P3** — Está no rádio, e é o alvo: o cinza, a frase e o arrasto que não muda nada.
* **P4** — Também no rádio, mesma leitura. Se um dos dois do rádio mostrar o trilho normal, anote qual.
* **P1** — Está no cabo, e é o contraste: o trilho dele tem de estar normal, com número. Sem ele, o cinza do rádio não prova nada.
* **P2** — Também no cabo, testemunha. Não precisa mexer nele.

**A armadilha.** Nos primeiros segundos da aba o trilho pode ainda não estar cinza: enquanto o Hefesto não perguntou à placa, ele não apaga nada, porque «não sei» não é «não dá». Espere uns segundos antes de anotar. Isto não é dívida: é o aparelho — no cabo o DualSense publica placa de som e o ganho mora nela; no rádio não há placa. A própria frase diz «Ligue o cabo e ele acende», e é verdade. E o Volume, logo acima, continua funcionando pelo rádio: é outro trilho, e outro teste.

---

## mapa-audio.microfone.volume-cabo — Microfone · volume · cabo

*Célula:* `audio.microfone.volume @ cabo`

**O que isto prova.** Prova que o número ao lado do trilho Volume do microfone é o volume REAL do canal daquele controle, lido do sistema, e não um número do desenho — e que ele é de um controle só. Até 12/09/2026 a tela mostrava o 80 do desenho para sempre, fizesse o sistema o que fizesse.

**Onde olhar.** Na aba Controles, no cartão de um controle ligado pelo cabo — na fita do topo, o chip dele diz USB. Dentro do cartão, o bloco Microfone: as barrinhas que se mexem com a voz, e o trilho Volume com o número ao lado. Fora do Hefesto, o painel de som do sistema, na lista de ENTRADAS: cada controle tem a sua, «Microfone do Controle 1» para o P1, «Microfone do Controle 2» para o P2.

**Os passos.**

1. Clique na aba Controles.
2. Confira na fita do topo que o P1 e o P2 dizem USB.
3. Clique na linha do P1 para abrir o cartão dele.
4. Anote o número do Volume do microfone do P1.
5. Abra o painel de som do sistema e ache, nas entradas, o «Microfone do Controle 1».
6. Mude o volume dessa entrada para 30.
7. Volte ao Hefesto sem clicar em nada e espere dois segundos.
8. Confira que o número do Volume do P1 foi para 30 e que o trilho acompanhou.
9. Clique na linha do P2 e confira que o Volume dele não mudou.
10. Volte ao cartão do P1 e arraste o Volume de volta ao número anotado.
11. Confira no painel de som que o «Microfone do Controle 1» acompanhou.
12. Faça no P2 a mesma volta, com o «Microfone do Controle 2».

**Passa quando.** O número do Volume acompanha, em poucos segundos, o que você mudou no painel do sistema, sem você clicar em nada no Hefesto; o outro controle não se mexe; e o arrasto de volta no Hefesto aparece no painel. Se o número ficar parado no valor antigo, a leitura não está chegando; se ele mostrar um número que o sistema não tem, a tela está inventando.

**Por controle.**

* **P1** — Está no cabo, e é o alvo: o número tem de seguir o painel, e o painel tem de seguir o arrasto.
* **P2** — Também no cabo, e é a segunda prova — e, enquanto você mexe no P1, a testemunha de que o volume é de um controle só.
* **P3** — Está no rádio, testemunha: o número dele não pode mudar enquanto você mexe no P1 ou no P2. A volta dele é a linha do rádio.
* **P4** — Também no rádio, mesma leitura do P3.

**A armadilha.** A leitura acontece de dois em dois segundos: olhar o número no mesmo instante em que você soltou o painel pode mostrar o valor velho sem defeito nenhum. O número vai de 0 a 100, como o trilho — um volume acima de 100 no sistema aparece como 100. O Volume não é o mudo: a luz vermelha do controle fica acesa e o botão de microfone do plástico continua valendo. Se o painel mostrar mais de uma entrada com cara de DualSense, mude primeiro a «Microfone do Controle» com o número do controle; se o Hefesto não seguir, mude a outra e anote qual fez o número andar — isso diz qual entrada o Hefesto está lendo. E se o número do nome não bater com o do cartão, anote também: o nome da entrada segue o lugar do controle, e um nome velho é achado.

---

## mapa-audio.microfone.volume-radio — Microfone · volume · rádio

*Célula:* `audio.microfone.volume @ rádio`

**O que isto prova.** O mesmo que a linha do cabo, pelo outro transporte — e aqui a pergunta tem uma metade a mais, porque pelo rádio o canal do microfone não é uma placa que o sistema publica sozinho: ele sobe pela ponte do Hefesto. Provar o volume no rádio é provar que a leitura atravessa essa ponte, e que o trilho muda a voz que chega ao PC — o que ninguém mediu pelo rádio até hoje.

**Onde olhar.** Na aba Controles, no cartão de um controle ligado pelo rádio — na fita do topo, o chip dele diz BT. Dentro do cartão, o bloco Microfone: o selo ATIVO ou DESLIGADO ao lado do nome, as barrinhas que se mexem com a voz, o trilho Volume com o número e o 🎙 ao lado. O 🎙 é o retorno: aceso em verde, você se ouve pela saída de som do computador, com o volume do cartão já aplicado, e ele assim FICA até o clique seguinte. Fora do Hefesto, o painel de som do sistema, nas ENTRADAS: «Microfone do Controle 3» para o P3, «Microfone do Controle 4» para o P4.

**Os passos.**

1. Clique na aba Controles.
2. Confira na fita do topo que o P3 e o P4 dizem BT.
3. Clique na linha do P3 para abrir o cartão dele.
4. Confira que o selo do Microfone do P3 diz ATIVO — se disser DESLIGADO, aperte o botão de microfone no próprio P3.
5. Anote o número do Volume do microfone do P3.
6. No painel de som do sistema, mude o volume da entrada «Microfone do Controle 3» para 30.
7. Volte ao Hefesto sem clicar em nada e espere dois segundos.
8. Confira que o número do Volume do P3 foi para 30.
9. Clique no 🎙 do P3.
10. Confira que ele ficou verde e assim continua sem você segurar nada.
11. Fale uma frase no P3 e, falando, arraste o Volume do P3 de 30 até 100.
12. Confira que a sua voz subiu no retorno junto com o trilho.
13. Clique no 🎙 de novo.
14. Confira que ele apagou e que o retorno calou.
15. Arraste o Volume do P3 de volta ao número anotado.
16. Faça no P4 a mesma volta, com o «Microfone do Controle 4».

**Passa quando.** O número acompanha o painel do sistema, igual ao do cabo — a leitura atravessa a ponte. A voz no retorno sobe quando o trilho sobe. E o 🎙 fica verde e assim FICA — ele é uma trava, como a do Discord, e só o clique seguinte o apaga.

**Por controle.**

* **P3** — Está no rádio, e é o alvo: a leitura que segue o painel, a voz que segue o trilho, e o 🎙 que fica aceso.
* **P4** — Também no rádio, mesma volta. Se o P3 responder e o P4 não, anote — são dois controles na mesma ponte.
* **P1** — Está no cabo, testemunha: o número do Volume dele não pode mudar enquanto você mexe no P3.
* **P2** — Também no cabo, mesma leitura do P1.

**A armadilha.** O trilho do Volume mexe em DUAS coisas ao mesmo tempo: no canal daquele controle no sistema e num byte do próprio controle. Pelo rádio ninguém mediu o byte sozinho — a voz subir prova o par, não o byte; é isso que você anota. Se o número do P3 for um travessão, a ponte do microfone daquele controle ainda não subiu: espere alguns segundos antes de concluir. O 🎙 não cala o microfone: ele liga o retorno; calar é o botão de microfone do próprio controle, e com o microfone calado o 🎙 nem liga. Se você não ouvir o retorno, confira se a saída de som do computador está alta. A leitura acontece de dois em dois segundos, então dê esse tempo antes de olhar o número. E se o painel mostrar mais de uma entrada para o mesmo controle, mude primeiro a «Microfone do Controle» com o número dele e anote qual fez o número andar.
