---
sprint: O-COMO-DAS-21
estado: feita
posse:
  O-COMO-DAS-21:
    - docs/process/sprints/2026-09-07-O-COMO-DAS-21-o-gesto-exato-de-cada-linha.md
bancada: true
---

# O COMO das 21 — o gesto exato de cada linha da bancada

**Encomenda dela, 07/09/2026, verbatim:**

> *"O COMO é obrigatório: escreva o gesto exato que foi aplicado. É isto que se
> perdia quando a sessão morria. isso aqui me quebra. isso eu espero que o
> [assistente] descreva."*

<!-- A palavra entre colchetes é uma ELISÃO, não uma paráfrase: ela
     escreveu ali o nome de um fornecedor, e este arquivo passou a ser
     versionado em 20/09/2026. O `check_anonymity.sh` reprova nome de
     fornecedor em arquivo rastreado, e a regra dela sobre isso é
     absoluta. Nenhuma outra palavra da frase foi tocada. -->

E o defeito que fez este arquivo nascer, apontado por ela olhando a linha 10 na
tela:

> *"sinceramente não entendi o que diabos é pra fazer aqui."*

Ela estava certa. O COMO saía como `linha do roteiro: 10` mais `passa quando:
mudaram` — o roteiro repetido, não o gesto. Um roteiro escrito em telegrama
serve a quem o escreveu e a mais ninguém.

## O que este arquivo é, e por que ele é UM arquivo

O roteiro (`docs/usage/roteiro-da-bancada-de-quatro.md`) diz **o que** se testa, em uma
linha por teste. Este diz **como** se faz, e não cabe numa linha: onde olhar na
tela, o gesto exato na ordem, o que muda em cada um dos quatro, e a armadilha
que faz o teste dar falso verde.

**Os dois têm donos diferentes de propósito.** O roteiro é dela — a decisão do
que vale medir. O COMO é meu, por pedido explícito dela, e é por isso que mora
aqui e não lá: se estivesse na mesma tabela, mexer no gesto pareceria mexer na
decisão.

**A página de medição LÊ deste arquivo.** Nada do que está aqui é digitado lá.
Mudou uma linha aqui, o próximo `F5` da bancada mostra o gesto novo.

## Como isto foi escrito, e o que confere

Quatorze agentes: sete escreveram, sete conferiram — e a conferência não foi de
texto, foi de **medição no produto**. Cada conferente foi ver, nos pacotes que
montam as abas, se o campo citado existe com aquele rótulo. **Um COMO que manda
olhar um campo inexistente é pior que nenhum COMO**, porque manda ela procurar.

Onde a fonte não bastava, está escrito *"a fonte não diz"* — declarar a lacuna
é o certo; inventar um passo faria ela caçar um botão que não existe.

**Reconferido em 24/09/2026**, linha a linha, contra as páginas publicadas, os
pacotes que as pintam e as fotos do dia: o gesto que tinha caído foi reescrito
no lugar, e o «por controle» de cada linha segue a coluna que ela escreveu no
roteiro.

---

---

## Linha 1 — Liga dois no cabo e dois no rádio, um a um

**O que isto prova.** Prova que os quatro controles entram sozinhos, cada um com o seu número de P1 a P4 e com a cor do plástico certa, em menos de cinco segundos depois de você ligar.

**Onde olhar.** Na fita do topo do Hefesto — a linha que fica logo abaixo do nome Hefesto e começa com "Selecionar:". Cada controle que entra vira um chip com três coisas: o número (P1, P2, P3 ou P4), o nome do plástico (a cor dele, a menos que você tenha dado outro nome àquele controle) e por onde ele fala, USB ou BT. A borda do chip é pintada com a cor do plástico. No canto de cima à direita, ao lado de «Perfil ativo», fica a conta dos ligados por transporte — com os quatro, «2 USB · 2 BT». Fique na aba Controles: cada controle ganha ali uma linha com o nome e a bateria.

**Os passos.**

1. Desligue os quatro controles e desencaixe os dois cabos antes de começar.
2. Abra o Hefesto.
3. Clique na aba Controles.
4. Confira que a fita do topo está sem chip nenhum e que o canto de cima à direita diz «Nenhum controle».
5. Deixe os quatro controles na mesa, na ordem em que você vai ligá-los.
6. Encaixe o cabo no PRIMEIRO controle e depois no PC.
7. Conte até cinco, devagar, olhando a fita.
8. Leia o chip que apareceu: ele tem de dizer P1, o nome daquele controle e USB.
9. Encaixe o segundo cabo no SEGUNDO controle e depois no PC, só agora que o P1 já está na fita.
10. Conte até cinco, devagar.
11. Leia o chip novo: P2, o nome daquele controle e USB.
12. Dê um toque curto no botão PS do TERCEIRO controle, só depois de o P2 estar na fita.
13. Conte até cinco, devagar.
14. Leia o chip novo: P3, o nome daquele controle e BT.
15. Dê um toque curto no botão PS do QUARTO controle, só depois de o P3 estar na fita.
16. Conte até cinco, devagar.
17. Leia o chip novo: P4, o nome daquele controle e BT.
18. Confira a conta do canto de cima à direita: «2 USB · 2 BT».
19. Pegue cada controle na mão, um de cada vez, e compare o plástico dele com o nome e a cor da borda do chip que o nomeia.

**Passa quando.** Os quatro chips apareceram sozinhos, um por vez, cada um em menos de cinco segundos depois do gesto de ligar — sem você recarregar nada. Os números saíram P1, P2, P3 e P4, na mesma ordem em que você ligou, sem repetir e sem pular. Ligar um controle novo não mudou o número de nenhum dos que já estavam lá. E o nome e a cor da borda de cada chip batem com o plástico do controle que você tem na mão.

**Por controle.**

* **P1** — Ligue este PRIMEIRO, e pelo cabo. Ele tem de aparecer na fita como P1, com a cor do plástico dele e USB.
* **P2** — Ligue este SEGUNDO, e pelo cabo, só depois de o P1 já estar na fita. Tem de entrar como P2, com USB, e o P1 não pode trocar de número quando ele entra.
* **P3** — Ligue este TERCEIRO, e pelo rádio, com um toque curto no PS. Tem de entrar como P3, com BT, e os dois do cabo têm de ficar parados nos números deles.
* **P4** — Ligue este POR ÚLTIMO, e pelo rádio, com um toque curto no PS. Tem de entrar como P4, com BT, e os três de antes não podem mexer no número nem na cor.

**A armadilha.** Existe um jeito de a fita mentir bonito, e ele já enganou esta casa: quando a tela para de ler os controles de verdade, ela fica mostrando os dois chips do DESENHO — sempre os mesmos dois, «P1 • Cosmic Red • USB» e «P2 • Starlight Blue • BT», com a conta dizendo «1 USB · 1 BT». Se a fita mostrar exatamente esses dois com outra coisa na sua frente, ela não está lendo os seus controles, e o teste não passou nem reprovou — não houve leitura. Duas outras coisas parecem defeito e não são: com um controle só ligado o chip "Todos" não aparece, de propósito; e se a cor do plástico ainda não foi lida, o chip fica sem a borda colorida — isso é a cor faltando, não o número errado.

---

## Linha 2 — Move cada controle dentro do jogo

**O que isto prova.** Prova que, com os quatro dentro do jogo, o jogo vê cada um deles — cada controle move o boneco dele e nenhum move o de outra pessoa — e que nenhum dos quatro some nos dois primeiros minutos.

**Onde olhar.** O lugar que decide é o JOGO: os quatro bonecos na tela. Qual boneco pertence a qual controle quem decide é o jogo, e a fonte não diz — por isso o primeiro passo é você anotar a dupla antes de mexer em qualquer coisa. Se algum boneco errado se mexer, o desempate está no Hefesto, aba Controles, com o chip "Todos" escolhido na fita: os quatro cartões abrem, e dentro de cada um o analógico tem um pontinho que anda quando você mexe no do aparelho e o desenho do botão acende quando você aperta. O cartão que reagir é o dono do movimento.

**Os passos.**

1. Abra o jogo em modo de quatro jogadores, com os quatro bonecos na tela.
2. Anote qual boneco é de qual controle, antes de mexer em nada.
3. Largue os quatro controles na mesa e pegue só o P1.
4. Empurre o analógico esquerdo do P1 para um lado e depois para o outro.
5. Veja o jogo: só o boneco 1 pode se mexer.
6. Solte o P1 e pegue só o P2.
7. Empurre o analógico direito do P2 para um lado e depois para o outro.
8. Veja o jogo: só o boneco 2 pode responder.
9. Solte o P2 e pegue só o P3.
10. Aperte as quatro direções do direcional do P3, uma de cada vez: cima, baixo, esquerda e direita.
11. Veja o jogo: só o boneco 3 pode responder.
12. Solte o P3 e pegue só o P4.
13. Aperte os quatro botões de face do P4 (✕, ○, □ e △), um de cada vez, no meio da partida e não num menu.
14. Veja o jogo: só o boneco 4 pode responder.
15. Jogue dois minutos com os quatro juntos, cada controle no gesto dele, do jeito que se joga mesmo.
16. Repare se algum boneco sai da partida, trava ou troca de dono no meio.
17. Se algum boneco errado tiver se mexido, vá ao Hefesto, aba Controles, clique no chip "Todos" da fita e mexa de novo no controle suspeito.
18. Veja em qual cartão o pontinho anda ou o botão acende — o cartão diz de qual aparelho veio o movimento.

**Passa quando.** O jogo vê os quatro: em cada uma das quatro voltas respondeu o boneco do controle que estava na sua mão, e só ele; nenhum boneco continuou andando depois que você soltou. E nos dois minutos com os quatro jogando juntos nenhum sumiu da partida nem trocou de boneco.

**Por controle.**

* **P1** — Só o analógico esquerdo, com os outros três largados na mesa. Só o boneco 1 pode responder.
* **P2** — Só o analógico direito, com os outros três largados na mesa. Só o boneco 2 pode responder.
* **P3** — Só o direcional, com os outros três largados na mesa. Só o boneco 3 pode responder — e ele está no rádio, que é onde este defeito costuma aparecer.
* **P4** — Só os botões de face, com os outros três largados na mesa. Só o boneco 4 pode responder — este é o último a entrar e o mais propenso a nascer sem dono.

**A armadilha.** Mexer em dois controles ao mesmo tempo esconde exatamente o defeito que este teste procura. Quando um aparelho está alimentando dois jogadores, os dois bonecos andam JUNTOS — e com as duas mãos ocupadas isso parece que cada dono mexeu no seu. Um de cada vez, com os outros três largados na mesa, é o que revela. E se você mexer no P1 e o boneco 3 responder, não conclua nada olhando só o jogo: pode ser o jogo que embaralhou a ordem dos jogadores, não o Hefesto. Quem separa os dois é o cartão da aba Controles, e é para isso que ele está nos passos. O analógico direito, em muito jogo, mexe a câmera e não o boneco — conta como resposta do boneco 2 se for a câmera DELE que girou. E os botões de face num menu fazem o menu andar (o ○ costuma voltar), o que parece defeito sem ser: aperte-os com a partida rodando.

---

## Linha 3 — Tira o P1 do cabo e põe no rádio, no meio da partida

**O que isto prova.** Prova que tirar o P1 do cabo e trazê-lo de volta pelo rádio, no meio da partida, não derruba os outros três e devolve a ele o mesmo número de antes.

**Onde olhar.** Três lugares, e o principal não é o controle que você está mexendo. Primeiro, a fita do topo do Hefesto: os chips dos outros três não podem sumir em momento nenhum, e o chip do que voltou tem de dizer P1 de novo, agora terminando em BT no lugar de USB. Segundo, o JOGO: os bonecos 2, 3 e 4. Terceiro, o próprio aparelho que voltou — as cinco lâmpadas brancas em fileira, embaixo do touchpad: elas dizem o número do jogador pelo CONJUNTO que fica aceso.

**Os passos.**

1. Confira que o controle do P1 já foi pareado por rádio nesta máquina alguma vez — sem isso, o toque no PS não o traz de volta e o teste não roda.
2. Abra o jogo com os quatro jogadores dentro da partida.
3. Leia a fita do Hefesto e anote o número dos quatro, antes de mexer em nada.
4. Puxe o cabo de dentro do controle do P1.
5. Dê um toque no botão PS desse mesmo controle, sem demorar — do puxão do cabo até o toque tem de passar menos de trinta segundos.
6. Olhe a fita durante a troca: os chips dos outros três não podem sumir em nenhum instante.
7. Olhe o jogo: os bonecos 2, 3 e 4 não podem travar, sumir nem parar de responder.
8. Espere o chip do controle que voltou reaparecer na fita e leia o que está escrito nele.
9. Vire para cima o controle que voltou e olhe as cinco lâmpadas brancas embaixo do touchpad.
10. Empurre o analógico esquerdo do controle que voltou e confira que ele move o boneco 1 de novo.
11. Mexa nos outros três, um de cada vez, e confira que cada um continua movendo o boneco dele.

**Passa quando.** Do puxão do cabo até o fim, os chips dos outros três continuaram na fita e os bonecos 2, 3 e 4 continuaram respondendo — ninguém mais caiu. O controle que trocou voltou à fita como P1 — o mesmo número que tinha antes —, agora terminando em BT. As lâmpadas dele mostram o desenho do jogador 1: só a do meio acesa. E ele volta a mover o boneco 1.

**Por controle.**

* **P1** — É ESTE que troca: puxe o cabo e devolva-o pelo rádio com um toque no PS, em menos de trinta segundos. Tem de voltar como P1, agora terminando em BT, com só a lâmpada do meio acesa, e tem de voltar a mover o boneco 1.
* **P2** — Não encoste nele durante a troca. O chip dele não pode sumir da fita, e depois da troca ele tem de continuar movendo o boneco 2.
* **P3** — Não encoste nele durante a troca. Ele está no rádio, que é onde a queda em cadeia costuma aparecer: o chip dele não pode piscar para fora da fita, e depois ele tem de continuar movendo o boneco 3.
* **P4** — Não encoste nele durante a troca. Também está no rádio e é o último da fila, o primeiro a cair quando alguma coisa desmonta: chip na fita o tempo todo, e o boneco 4 respondendo depois.

**A armadilha.** Três, e todas fazem você julgar errado. A primeira é a leitura das lâmpadas: as cinco do DualSense não se contam da esquerda para a direita — o número é o CONJUNTO aceso. Jogador 1 é só a do meio. Jogador 2 são a segunda e a quarta. Jogador 3 são a primeira, a do meio e a última. Jogador 4 são as quatro das pontas, com a do meio apagada. Quem lê "a terceira lâmpada acesa" como jogador 3 reprova um produto que está certo. A segunda é o relógio: o posto de Jogador 1 fica guardado por trinta segundos para o P1 que caiu. Se você demorar mais que isso entre puxar o cabo e tocar o PS, ele volta com outro número — e isso é a regra do produto funcionando, não defeito. Refaça mais rápido. A terceira: enquanto o P1 está fora, o produto fecha a fila, e os outros podem descer um número (o P2 acender como 1) e voltar ao seu quando o P1 volta. Anote se vir — o que esta linha cobra é que ninguém caia e que o P1 volte P1. E o erro de mira: a tentação é ficar olhando o controle que você está mexendo. Este teste se decide nos OUTROS TRÊS.

---

## Linha 4 — Desliga um controle do rádio, com PS longo

**O que isto prova.** Prova que desligar um controle do rádio não bagunça os outros três: eles seguem ligados, com o mesmo número e a mesma cor de barra, e nada fica vibrando sozinho.

**Onde olhar.** Nos próprios aparelhos: as cinco lâmpadas do indicador de jogador (a fileira logo abaixo do touchpad, no arranjo 1 · vão · 3 · vão · 1) e a barra de luz (as duas tiras que ladeiam o touchpad). No Hefesto, fique na aba Iluminação, que é a única em que o desenho do controle é grande o bastante para as cinco lâmpadas se lerem pela tela. Ali, a linha «Modelo» nomeia cada coluna («P3 • nome • BT»), e a coluna de um controle que saiu passa a dizer «P3 • Desconectado». No canto de cima à direita, a conta por transporte: hoje «2 USB · 2 BT».

**Os passos.**

1. Confira que os quatro estão ligados: P1 e P2 no cabo, P3 e P4 no rádio.
2. Abra a aba Iluminação.
3. Anote o número de jogador de cada um dos quatro controles.
4. Anote a cor da barra de luz de cada um dos quatro.
5. Leia a conta no canto de cima à direita e anote o que ela diz.
6. Pegue o P3, que é um dos dois do rádio.
7. Segure o botão PS do P3 — o redondo com o símbolo da PlayStation, no meio de baixo, entre os dois analógicos.
8. Continue segurando até todas as luzes do P3 apagarem.
9. Solte o botão e ponha o P3 na mesa.
10. Deixe o cronômetro desta página correr os vinte segundos, olhando os três controles que ficaram na mesa.
11. Confira nos três que ficaram se as lâmpadas continuam no mesmo padrão que você anotou.
12. Confira nos três que ficaram se a cor da barra de luz continua a mesma.
13. Confira que nenhum dos três que ficaram está tremendo.
14. Leia a conta no canto de cima à direita: tem de dizer «2 USB · 1 BT».
15. Leia a linha «Modelo»: a coluna do P3 tem de dizer «P3 • Desconectado», e nenhum outro controle pode ter se mudado para ela.
16. Registre nesta página a resposta de cada um dos quatro.

**Passa quando.** Os três que continuaram ligados — P1, P2 e P4 — seguem na tela e no aparelho com o mesmo número de jogador e a mesma cor de barra de luz que tinham antes, e nenhum fica vibrando por causa da saída do P3. O lugar que era do P3 aparece como «P3 • Desconectado» e continua assim durante os vinte segundos.

**Por controle.**

* **P1** — Fica ligado, no cabo. Não toque nele. Anote o número e a cor da barra de luz antes de desligar o P3 e confira os dois depois — têm de ser exatamente os mesmos.
* **P2** — Fica ligado, no cabo. Não toque nele. Mesma conferência do P1: número e cor iguais antes e depois. Se algum dos dois do cabo mudar, anote que foi um do CABO.
* **P3** — É ESTE que desliga, e é o único que você toca. Está no rádio. Segure o botão PS até todas as luzes dele apagarem, solte e deixe-o parado na mesa pelos vinte segundos. Se ele estava vibrando pelo jogo na hora em que apagou, ele tem de voltar parado na linha 5.
* **P4** — Fica ligado, no rádio. Não toque nele. É o vizinho de rádio do que caiu, então é nele que uma bagunça costuma aparecer primeiro: confira número e cor antes e depois, e veja se ele não se mudou para o lugar do P3.

**A armadilha.** Soltar o botão PS cedo demais. Aí o controle não desliga e o teste mede o seu gesto, não o produto — e há um efeito colateral já visto nesta casa: com cerca de cinco segundos de botão, o Hefesto lê o aperto como um toque no PS e abre a Steam. Segure até as luzes apagarem; se a Steam abrir, feche-a e refaça a linha. E se o P4 descer para 3 enquanto o P3 está fora — lâmpadas do jogador 3 e a barra na cor do 3 —, anote como vir: é o produto fechando a fila, e é exatamente o que esta linha existe para mostrar.

---

## Linha 5 — Religa o controle que foi desligado

**O que isto prova.** Prova que o controle que voltou reencontra o lugar que era dele, sem empurrar ninguém dos outros três.

**Onde olhar.** Nos aparelhos: as cinco lâmpadas do indicador de jogador, abaixo do touchpad. O padrão diz o número — jogador 1 acende só a do meio; jogador 2 acende a segunda e a quarta; jogador 3 acende as duas das pontas e a do meio; jogador 4 acende as quatro, menos a do meio. E a barra de luz, as duas tiras ao lado do touchpad: quando ninguém escolheu cor à mão, o Hefesto pinta por número — 1 azul, 2 vermelho, 3 verde, 4 rosa. No Hefesto, aba Iluminação: a conta no canto de cima à direita, que tem de voltar a «2 USB · 2 BT», e a linha «Modelo», onde a coluna do P3 tem de deixar de dizer «P3 • Desconectado» e voltar com o nome dele e BT.

**Os passos.**

1. Deixe P1, P2 e P4 exatamente como estão, sem tocar em nenhum.
2. Pegue o P3, que está desligado.
3. Dê um toque curto no botão PS do P3 e solte.
4. Espere a barra de luz dele acender.
5. Ponha o P3 na mesa.
6. Deixe o cronômetro desta página correr os dez segundos.
7. Conte quais das cinco lâmpadas do P3 acenderam.
8. Confira que acenderam as duas das pontas e a do meio — é o padrão do jogador 3.
9. Confira que o P3 voltou parado, sem tremer.
10. Olhe as lâmpadas dos outros três e confira que nenhum mudou de padrão.
11. Olhe a cor da barra de luz dos quatro e confira que nenhuma trocou de dono.
12. Abra a aba Iluminação do Hefesto.
13. Leia a conta no canto de cima à direita: tem de voltar a dizer «2 USB · 2 BT».
14. Leia a linha «Modelo»: a coluna do P3 voltou com o nome dele e BT, e os outros três continuam nas colunas deles.
15. Registre nesta página a resposta de cada um dos quatro.

**Passa quando.** O P3 volta como jogador 3 — as mesmas três lâmpadas de antes, na mesma coluna — e os outros três terminam com os números que já tinham. Ninguém foi empurrado para outro lugar para abrir espaço para ele, e ninguém perdeu o seu.

**Por controle.**

* **P1** — Não pode mudar de posto. Está no cabo. Não toque nele. Confira, depois que o P3 voltar, que o número e a cor da barra de luz continuam os de antes.
* **P2** — Não pode mudar de posto. Está no cabo. Não toque nele. Mesma conferência do P1.
* **P3** — É ESTE que religa, e é o único que você toca. Está no rádio. Um toque curto no PS, espere a barra de luz acender e ponha-o de volta na mesa. Tem de voltar como jogador 3.
* **P4** — Não pode mudar de posto. Está no rádio. Não toque nele. É aqui que se vê se alguém tomou o lugar do P3 enquanto ele estava fora — olhe as lâmpadas dele com atenção.

**A armadilha.** Religar pelo cabo é outro teste, com resposta possivelmente diferente — ninguém mediu essa ainda. Religue pelo botão PS, com um toque curto: segurar o PS por uns cinco segundos, com o controle já ligado, faz o Hefesto abrir a Steam. O prazo de trinta segundos do Hefesto é o do posto de Jogador 1; o número do P3 é guardado pelo endereço dele e não vence enquanto o Hefesto estiver de pé — se ele voltar com outro número, isso é achado, não demora sua.

---

## Linha 6 — Vibração: testa em um de cada vez

**O que isto prova.** Prova que a vibração é de um controle só — quem você mandou tremer treme, e os outros três ficam quietos — e que o teto de força escolhido na coluna de um controle vale nele.

**Onde olhar.** Na aba Vibração do Hefesto: as quatro colunas lado a lado, uma por controle, com o nome de cada um na linha «Modelo», embaixo do desenho («P1 • nome • USB»). Duas linhas importam: «Força da vibração», com os três degraus Economia · Balanceado · Máximo, e «Testar agora», com os botões Testar e Parar. O «Testar» fica tremendo até você clicar em «Parar», e acompanha na hora o degrau que você mudar. O tremor em si não aparece em campo nenhum da tela — a prova dele é a sua mão e o seu ouvido. No aparelho, os dois motores ficam um em cada punho: o esquerdo tem o contrapeso maior e soa grosso, o direito soa fino.

**Os passos.**

1. Pause o jogo que está aberto, ou deixe-o numa tela parada.
2. Abra a aba Vibração.
3. Anote qual degrau está aceso na linha «Força da vibração» de cada uma das quatro colunas.
4. Clique em «Máximo» na coluna do P1 — ou em «Balanceado», se ele já estiver no Máximo.
5. Confira que só a coluna do P1 mudou de degrau, e que as outras três continuam no que você anotou.
6. Ponha P2, P3 e P4 parados sobre a mesa, sem nada por cima e sem encostar neles.
7. Segure o P1 com uma das mãos.
8. Clique em «Testar» na coluna do P1 com a outra mão.
9. Sinta o P1 tremer nos dois punhos — ele continua tremendo.
10. Olhe e escute os outros três na mesa: nenhum pode se mexer nem zumbir.
11. Clique em «Economia» na coluna do P1, com ele ainda tremendo na sua mão.
12. Sinta o tremor do P1 ficar mais fraco.
13. Clique em «Parar» na coluna do P1.
14. Confira que o P1 parou de tremer.
15. Registre nesta página a resposta de cada um dos quatro.

**Passa quando.** Só o P1 treme, e só enquanto o «Testar» está de pé; P2, P3 e P4 ficam parados e mudos o tempo todo. Trocar o degrau da coluna do P1 muda o tremor na sua mão, e as outras três colunas continuam mostrando o degrau que tinham antes.

**Por controle.**

* **P1** — É ESTE que deve tremer. Está no cabo. Mude o degrau da «Força da vibração» só na coluna dele, segure-o, clique em «Testar» na coluna dele, troque o degrau com ele tremendo e sinta a força mudar. No fim, «Parar».
* **P2** — Não pode tremer. Está no cabo. Deixe-o parado na mesa durante o teste do P1. A coluna dele tem de continuar no degrau que estava — se ela mudou junto com a do P1, o ajuste vazou de um controle para outro.
* **P3** — Não pode tremer. Está no rádio. Parado na mesa, sem encostar. Se ele tremer, anote que quem tremeu sem ser chamado estava no RÁDIO — é o que separa um defeito do cabo de um defeito do rádio.
* **P4** — Não pode tremer. Está no rádio. Parado na mesa, sem encostar. Confira também que a coluna dele não trocou de degrau sozinha quando você mexeu na do P1.

**A armadilha.** Tremor que não é seu, e tremor que não para. Com o jogo aberto, é ele quem manda os controles vibrarem, e um tremor no P2 pode ser do jogo e não do teste — por isso o primeiro passo é pausar. E o «Testar» não para sozinho: sem o «Parar», o P1 continua tremendo e o jogo fica sem vibração nele até alguém parar. Se um motor da coluna estiver com a barra em 0 (as linhas «Motor esquerdo» e «Motor direito»), aquele punho fica mudo no teste — isso é o ajuste, não defeito.

---

## Linha 7 — Gatilhos: aplica um efeito só no P3

**O que isto prova.** Prova que um efeito de gatilho escolhido na coluna de um controle vai só para aquele controle, e os outros três continuam do jeito que estavam.

**Onde olhar.** Na aba Gatilhos do Hefesto. Cada controle tem uma coluna, com a etiqueta dele no alto, na linha «Controle» (o número, o nome e USB ou BT). À esquerda, o desenho do L2 abre a seção do gatilho esquerdo e o desenho do R2 a do direito; em cada seção as linhas são «Modo», «Efeito pronto» e «Ajustes». Mas quem responde este teste é a sua mão, e não a tela: o controle não devolve em que efeito ele está, então o campo Modo mostra o que foi PEDIDO, nunca o que está no aparelho. A resposta é a resistência que você sente ao apertar o L2 e o R2.

**Os passos.**

1. Abra a aba Gatilhos.
2. Confira que as quatro colunas têm etiqueta de controle no alto, e que nenhuma diz «Desconectado».
3. Aperte o L2 e o R2 de cada um dos quatro controles, um por vez, para guardar na mão como cada um está ANTES.
4. Escolha «Rígido» na lista «Modo» da seção do L2, na coluna do P3.
5. Aperte o L2 do P3.
6. Confira, na mão, que ele travou duro do começo ao fim do curso.
7. Escolha «Rígido» na lista «Modo» da seção do R2, na mesma coluna do P3.
8. Aperte o R2 do P3.
9. Confira, na mão, que ele travou também.
10. Aperte o L2 e o R2 do P1, do P2 e do P4 de novo, um por vez.
11. Compare com o que você sentiu no começo: os três têm de estar iguais, nenhum mais duro e nenhum mais solto.
12. Escolha «Desligado» na lista «Modo» das duas seções do P3, a do L2 e a do R2, para desfazer o teste.
13. Aperte o L2 e o R2 do P3.
14. Confira que os dois voltaram a ficar leves.

**Passa quando.** Só o L2 e o R2 do P3 ficam duros. Os gatilhos do P1, do P2 e do P4 continuam exatamente como estavam antes — nenhum endureceu e nenhum ficou mais solto. E, ao escolher «Desligado» nas duas seções do P3, os dois gatilhos dele voltam a ficar leves na sua mão.

**Por controle.**

* **P1** — Não toque na coluna dele. Aperte o L2 e o R2 antes e depois; tem de estar igual nas duas vezes.
* **P2** — Não toque na coluna dele. Aperte o L2 e o R2 antes e depois; tem de estar igual nas duas vezes.
* **P3** — É o único em que você mexe. Ponha «Rígido» no Modo do L2 e no do R2, e sinta os dois travarem. No fim, ponha «Desligado» nos dois para desfazer.
* **P4** — Não toque na coluna dele. Aperte o L2 e o R2 antes e depois; tem de estar igual nas duas vezes.

**A armadilha.** Não use «Desligado» como o efeito do teste. Ele é a escolha que SOLTA o gatilho, e se ela escapar para os quatro você não vê nada — os outros três já estão soltos, e o teste passa por cima do defeito. O efeito do teste tem de ser um que ENDUREÇA, porque endurecer é o que a mão sente. E não julgue pela tela: o campo Modo continua mostrando «Rígido» mesmo se um jogo escrever por cima e o gatilho estiver leve na sua mão. Se você não apertar os quatro ANTES, não tem com o que comparar depois — e aí o teste não mede nada.

---

## Linha 8 — Iluminação: uma cor diferente em cada um, e depois o automático

**O que isto prova.** Prova que cada controle obedece à cor que você escolheu na coluna dele, inclusive os que estão por rádio, sem mexer na cor dos outros, e que a troca automática de perfil continua valendo depois disso.

**Onde olhar.** Na aba Iluminação do Hefesto. Cada controle tem uma coluna, e a linha «Modelo» diz de quem ela é («P1 • nome • USB»). As linhas, nomeadas na coluna da esquerda, são Controle, Modelo, Cor, Brilho, Jogador, LEDs e Opções. A linha «Cor» tem onze tons, sempre na mesma ordem: azul, vermelho, verde, rosa, amarelo, ciano, laranja, roxo, verde-limão, verde-água e branco. O tom que um OUTRO controle está acendendo aparece com um X, e não se escolhe; o tom escolhido ganha uma borda na cor do plástico. A prova, porém, é no aparelho: a barra de luz é a faixa que acende dos dois lados do touchpad. O perfil que está valendo se lê no alto, à direita, em «Perfil ativo», e ele é igual nas dez abas.

**Os passos.**

1. Abra a aba Iluminação.
2. Leia a linha «Modelo» das quatro colunas e anote quais terminam em USB e quais em BT.
3. Clique no amarelo, o quinto tom, na linha Cor da coluna do P1 — é um passo de passagem, para soltar o azul que o P2 vai receber.
4. Confira, no aparelho, que a barra de luz do P1 acendeu amarela.
5. Clique no azul, o primeiro tom, na linha Cor da coluna do P2.
6. Confira a barra do P2 e veja que a do P1 continua amarela.
7. Clique no vermelho, o segundo tom, na linha Cor da coluna do P1.
8. Confira que a barra do P1 ficou vermelha e que a do P2 continua azul.
9. Confira que a barra do P3 continua no verde do número 3 — ninguém clica na coluna dele.
10. Clique no verde-limão, o nono tom, na linha Cor da coluna do P4.
11. Veja os quatro controles juntos: vermelho, azul, verde e verde-limão, acesos ao mesmo tempo.
12. Clique no rosa, o quarto tom, na linha Cor da coluna do P4, para devolvê-lo à cor do número dele.
13. Confira que a barra do P4 voltou ao rosa.
14. Clique na aba Jogar e confira que o «Trava o perfil ativo», no canto direito do quadro Modo, está apagado.
15. Traga para a frente a janela de um jogo que tenha perfil próprio no Hefesto.
16. Volte ao Hefesto com Alt+Tab.
17. Confira o «Perfil ativo» no alto da tela: ele tem de ter trocado para o perfil daquele jogo.

**Passa quando.** As quatro barras de luz ficam acesas ao mesmo tempo, cada uma na cor da coluna dela — inclusive as dos dois controles que estão por rádio —, e pintar uma nunca muda a cor de outra. O P3, que ninguém tocou, fica no verde do número dele do começo ao fim, e o P4 volta ao rosa quando você o devolve. E com o jogo na frente o «Perfil ativo» troca sozinho para o perfil dele.

**Por controle.**

* **P1** — Põe VERMELHO. Passa antes pelo amarelo, porque o vermelho é a cor do P2 até o P2 sair dela. A barra dele tem de acender em cada tom no clique e ficar no vermelho até o fim.
* **P2** — Põe AZUL, que fica livre quando o P1 vai para o amarelo. No instante em que você pintar este, olhe o P1: ele não pode mudar.
* **P3** — Fica no AUTOMÁTICO: ninguém clica na coluna dele. A barra tem de continuar no verde do número 3 enquanto os outros mudam — e ele está no rádio.
* **P4** — Põe VERDE — o verde-limão, porque o verde puro é o do P3 e está com X — e depois volta à cor automática dele, o rosa do número 4. É o segundo do rádio: a cor tem de chegar igual à de quem está por cabo.

**A armadilha.** A tela não é a prova: o desenho da linha LEDs mostra a cor que o Hefesto pediu, e quem responde é a faixa acesa no plástico. Um tom com X é a cor de outro controle: o clique nele pisca e nada muda, e isso é a regra, não defeito. Não mexa no interruptor «Cores automáticas por controle», no alto da aba: ele é do perfil e vale para os quatro de uma vez, e desligá-lo grava na hora a cor de todos. Pintar uma cor à mão não segura mais a troca de perfil — quem a segura é o «Trava o perfil ativo», da aba Jogar, e é por isso que ele está nos passos. Quando o perfil do jogo entra, as barras podem mudar de cor: são as cores daquele perfil, não o teste falhando. E antes de dar vermelho na última parte, olhe a aba Sistema: se a linha «Trocar de perfil ao abrir o jogo» disser que o Hefesto não está vendo a janela, esta metade não tem como ser medida hoje.

---

## Linha 9 — Microfone: aperta o botão físico de cada um, um por vez

**O que isto prova.** Prova que apertar o botão de microfone de um controle liga ou desliga o microfone daquele controle e só dele, que a luz do botão conta a mesma história que a tela, e que o canal daquele controle aparece no sistema.

**Onde olhar.** No aparelho: o botão do microfone é o botãozinho no plástico, logo abaixo do botão PS, com uma luz vermelha — acesa quer dizer microfone ligado; apagada quer dizer desligado; piscando quer dizer ligado e com um programa ouvindo agora. Na tela: aba Controles, com o chip «Todos» da fita abrindo os quatro cartões. Dentro de cada um, a linha «Microfone» traz um selo que diz ATIVO, DESLIGADO ou «—» (o travessão quer dizer «não consegui ler», e não é nenhum dos dois), e embaixo dele uma barrinha de ondas que mexe com o som que está entrando agora. Fora do Hefesto: nas configurações de Som do sistema, na parte de Entrada, cada controle em «Virtual» (o par Virtual · Nativo fica embaixo do volume do microfone, no cartão) tem o seu «Microfone do Controle N».

**Os passos.**

* Abra a aba Controles.
1. Clique no chip «Todos», na fita do topo, para abrir os quatro cartões.
2. Leia o selo do Microfone dos quatro e anote o que cada um diz — este é o ponto de partida.
3. Olhe a luz do botão de microfone de cada um dos quatro e anote.
4. Fale perto do P1 e confira que a barrinha de ondas do cartão dele mexe.
5. Aperte uma vez o botão do microfone do P1, no plástico.
6. Confira que a luz do botão do P1 mudou e que, dos quatro selos, só o do P1 trocou.
7. Espere um segundo.
8. Aperte o botão do P1 de novo e confira que a luz e o selo voltaram ao que eram.
9. Abra as configurações de Som do sistema, na parte de Entrada, e procure o microfone do P1 — «Microfone do Controle 1» quando o cartão dele está em «Virtual» — e anote como ele aparece.
10. Repita os passos 4 a 9 no P2, no P3 e no P4, trocando o número, e só passe ao seguinte quando o selo do anterior tiver assentado.
11. Confira, no fim, que os quatro selos voltaram a dizer o que diziam no passo 2.

**Passa quando.** Cada aperto mexe no microfone do controle que foi apertado, e só nele: o selo daquele cartão troca e os outros três ficam parados. A luz do botão apertado inverte a cada aperto e acompanha o selo — acesa com ATIVO, apagada com DESLIGADO —, do mesmo jeito nos quatro, no cabo e no rádio. Com o selo em ATIVO, a Entrada do sistema mostra o microfone daquele controle — o «Microfone do Controle N», quando o cartão está em «Virtual». E no fim os quatro voltam ao que estavam no começo.

**Por controle.**

* **P1** — Cabo. Aperte o botão do microfone dele e espere o selo assentar. A luz do botão muda, o selo do P1 troca, e os selos do P2, do P3 e do P4 não se mexem. Aperte de novo para voltar.
* **P2** — Cabo, mesmo gesto. Antes de apertar, olhe onde estão os quatro selos: o erro que este teste caça é o aperto de UM controle mexer no microfone de OUTRO, e ele só se enxerga se você souber o de antes.
* **P3** — Rádio, mesmo gesto. Se ele cair e voltar no meio da linha, anote o que o selo diz na volta: pelo rádio, uma reconexão já desfez o estado do microfone sem nada avisar.
* **P4** — Rádio, mesmo gesto, e é o último. Confira no fim que os quatro selos voltaram ao que diziam no começo.

**A armadilha.** Não clique no 🎙 da TELA, dentro do cartão, ao lado do volume do microfone: ele não é o mudo. Ele liga o retorno — você passa a se ouvir — e fica verde até você clicar de novo; o mudo é o botão do plástico. Dê um segundo entre um aperto e o seguinte NO MESMO controle: apertos mais rápidos que isso são engolidos de propósito, para não contar repique — um segundo aperto que «não fez nada» pode ser só isso. Um selo em «—» não é ATIVO nem DESLIGADO: quer dizer que o Hefesto não conseguiu ler aquele controle; anote e não conte como passa. Luz PISCANDO com o selo em ATIVO não é discordância: é um programa ouvindo aquele microfone agora. E o «Microfone e botões», na aba Conexões, é outro interruptor — ele liga e desliga a ponte do rádio daquele controle; não mexa nele nesta linha.

---

## Linha 10 — Bateria: anota os quatro números e volta neles aos 20 minutos

**O que isto prova.** Prova que o número da bateria dos quatro controles anda com o tempo, em vez de ficar congelado.

**Onde olhar.** Na aba Controles do Hefesto. Cada controle tem uma linha, e no fim dela vem a palavra Bateria, uma barrinha e o número em porcento, com um ✓ quando está cheio e um raio quando está carregando. Um cartão fica sempre aberto, e o número dele fica na primeira linha do cartão; os outros três ficam nas linhas fechadas — os quatro números aparecem juntos na mesma tela. A linha de cada controle também diz, depois do nome, USB ou BT.

**Os passos.**

1. Abra a janela do Hefesto.
2. Clique na aba Controles.
3. Clique na linha do P1 para que o cartão aberto seja o dele — assim as linhas fechadas são as do P2, do P3 e do P4, na ordem.
4. Confira o transporte de cada um: o P1 e o P2 têm de dizer USB, o P3 e o P4 têm de dizer BT.
5. Anote num papel os quatro números de bateria, um embaixo do outro, na ordem P1, P2, P3, P4 — o do P1 está na primeira linha do cartão aberto.
6. Anote a hora ao lado dos quatro números.
7. Marque um alarme de 20 minutos no celular.
8. Saia da frente da tela e siga o roteiro (o campo espera diz o que fazer).
9. Quando o alarme tocar, volte à janela do Hefesto e à aba Controles.
10. Anote os quatro números de novo, embaixo dos primeiros.
11. Compare cada controle com ele mesmo: o número de agora contra o número de vinte minutos atrás.

**Passa quando.** Os quatro números mudaram entre a primeira anotação e a segunda. Os dois do cabo subiram, porque estão carregando; os dois do rádio caíram, porque estão só gastando. Se os quatro estiverem exatamente iguais aos de vinte minutos atrás, reprova — o número congelado é justamente o que este teste procura.

**Por controle.**

* **P1** — No cabo. Anote o número da bateria dele agora e de novo aos vinte minutos. Como ele está carregando, o esperado é o número SUBIR.
* **P2** — No cabo, igual ao P1. Anote agora e aos vinte minutos, e espere o número SUBIR.
* **P3** — No rádio, sem cabo nenhum plugado. Anote agora e aos vinte minutos. Como ele só gasta, o esperado é o número CAIR.
* **P4** — No rádio, igual ao P3. Anote agora e aos vinte minutos, e espere o número CAIR.

**A espera.** São vinte minutos, e nenhum deles é para ficar olhando a tela. Depois de anotar os quatro números e marcar o alarme, siga o roteiro: faça a linha 11 (som pelo rádio) e a linha 19 (alto-falante do P2), que são desta mesma seção, e depois entre na seção seguinte, com as linhas 12, 13 e 14. Nesse tempo não desligue, não desplugue e não troque nenhum controle de cabo para rádio — qualquer uma dessas coisas zera o experimento. Quando o alarme tocar, volte à aba Controles e leia os quatro números.

**A armadilha.** Controle já cheio no cabo fica parado em 100% e isso NÃO é o defeito. Comece o teste com os quatro abaixo de 100% — use os controles um pouco antes, ou espere a carga cair. E o número não anda de um em um: ele pula de dez em dez pontos, então em vinte minutos os dois do rádio podem honestamente não ter dado um pulo. Se só os do cabo mudarem, não reprove ainda: anote e volte a olhar mais tarde. O que reprova de verdade é o número parado nos quatro, ou parado por horas.

---

## Linha 11 — Som pelo rádio: o ensaio 1 da bancada, com a orelha dela

**O que isto prova.** O som já saiu pelo rádio com a orelha dela, em 10/09. O que esta linha prova agora é o resto: que o som mirado no P3 sai SÓ no P3 — não no P4, que está no mesmo rádio, nem na TV —, que mirado na TV ele sai da TV e o P3 cala, e que ela acerta de onde o som sai sem saber para onde ele foi mandado.

**Onde olhar.** O instrumento é o ouvido dela, encostado no alto-falante do próprio controle: são nove furinhos em duas fileiras, no meio da frente do DualSense, logo abaixo e entre os dois analógicos. O volante do teste é a lista de saídas de som — a do tocador, ou a das configurações de Som do sistema —, onde cada controle tem o seu «Alto-falante do Controle N», com o N igual ao número do jogador. No Hefesto, aba Controles, o cartão do P3: o bloco Alto-falante, com o selo ATIVO, o número do volume e três botões — «Efeitos do Jogo no Controle, Áudio da TV na TV», «Efeitos do Jogo e Áudio da TV no Controle» e «Tudo na TV e Nada no Controle».

**Os passos.**

1. Abra a aba Controles.
2. Confira que o P3 está só no rádio: nenhum cabo plugado nele, e o chip dele na fita termina em BT.
3. Clique na linha do P3 para abrir o cartão dele.
4. Confira no bloco Alto-falante do P3: o selo diz ATIVO, o volume não está em zero, e o botão aceso não é «Tudo na TV e Nada no Controle».
5. Pause o jogo, se houver um aberto.
6. Toque uma música qualquer num tocador, num volume que dê para ouvir na TV.
7. Escolha «Alto-falante do Controle 1» como a saída do tocador — ou, se ele não tiver essa escolha, como a saída do sistema.
8. Encoste o ouvido nos nove furinhos do P1 e deixe-o ali uns segundos.
9. Confira que a música sai do P1: é ele, no cabo, que prova que o seu ouvido e o caminho do som estão bons.
10. Troque a saída para «Alto-falante do Controle 3».
11. Encoste o ouvido nos nove furinhos do P3.
12. Confira que a música sai do P3.
13. Encoste o ouvido no P4.
14. Confira que o P4 está mudo e que a TV também não toca a música.
15. Troque a saída para a TV.
16. Confira que a música sai da TV e que o P3 ficou mudo.
17. Feche os olhos e peça a quem está com você que troque a saída três vezes, sem dizer para onde, entre «Alto-falante do Controle 3», «Alto-falante do Controle 4» e a TV.
18. Diga, a cada troca, de onde o som está saindo, e peça que anotem se você acertou.
19. Devolva a saída para a TV.

**Passa quando.** Com a saída no «Alto-falante do Controle 3», a música sai do P3 — que está no rádio — e só dele: o P4 fica mudo e a TV não toca. Mirada na TV, ela sai da TV e o P3 cala. No teste de olhos fechados ela acerta as três trocas. E o P1, no cabo, tocou antes: sem isso nada acima vale.

**Por controle.**

* **P1** — No cabo, e é o controle de comparação. Faça nele a primeira escuta: o som tem de sair. Sem isso, o que acontecer no P3 não mede nada.
* **P2** — Ninguém toca. Não abra o cartão dele e não mexa em volume nenhum.
* **P3** — No rádio, e é ESTE que tem de receber o som. É nele que ela encosta o ouvido quando a saída é o «Alto-falante do Controle 3», e é ele que tem de calar quando a saída vai para a TV.
* **P4** — No rádio, e não pode tocar — é o negativo. Ele está no mesmo tipo de conexão do P3: se a música sair nele com a saída no Controle 3, o som foi para o rádio inteiro e não para UM controle.

**A armadilha.** Se o P1, que está no cabo, não tocar, o teste não mediu nada — pode ser o volume do sistema, o selo em DESLIGADO (o ♪ ao lado do volume é o mudo do alto-falante) ou o botão «Tudo na TV e Nada no Controle» aceso; conserte isso antes de olhar o P3. Pelo rádio o som pode levar uns segundos para começar depois de cada troca de saída: dê esse tempo antes de responder. Faça com o jogo pausado — pelo rádio, som e vibração dividem o mesmo fio, e um tremor no meio pode picotar o som. E a lista do sistema pode mostrar também a placa de som do próprio controle, com outro nome: a escolha deste teste é sempre o «Alto-falante do Controle N». Encostar o ouvido é ato numerado, e vem ANTES da escuta de propósito: quem clica primeiro e encosta depois ouve quando o som já passou.

---

## Linha 12 — Fecha o jogo, fecha a janela, e reabre as duas

**O que isto prova.** Prova que fechar e reabrir o jogo e a janela do Hefesto não derruba nenhum dos quatro controles nem troca o perfil.

**Onde olhar.** Na faixa de cima da janela do Hefesto, que é igual nas dez abas. À esquerda dela ficam as etiquetas dos controles, uma por controle, com P1 a P4, o nome e USB ou BT. À direita, na mesma faixa, fica «Perfil ativo» com o nome do perfil, e logo antes dele a conta por transporte, no formato «2 USB · 2 BT». E nos aparelhos, as luzes de jogador — a fileirinha de luzinhas logo abaixo do touchpad — têm de continuar acesas no mesmo número.

**Os passos.**

1. Com o jogo aberto, abra a janela do Hefesto.
2. Leia o nome que está em Perfil ativo, na faixa de cima, e anote no papel.
3. Conte as etiquetas de controle da faixa de cima: têm de ser quatro, com P1 e P2 terminando em USB e P3 e P4 terminando em BT.
4. Olhe a fileira de luzes de jogador de cada controle e anote qual número está aceso em cada um.
5. Feche o jogo pelo jeito normal dele.
6. Feche a janela do Hefesto no X.
7. Conte até dez sem tocar em nada.
8. Abra o jogo de novo.
9. Abra a janela do Hefesto de novo, pelo mesmo ícone por onde você a abriu antes.
10. Leia a conta no canto de cima à direita: tem de dizer «2 USB · 2 BT».
11. Leia as quatro etiquetas da faixa de cima e compare com o que você anotou.
12. Leia o Perfil ativo e compare com o nome anotado.
13. Olhe as luzes de jogador dos quatro e confira que cada um continua no mesmo número.
14. Mexa um analógico de cada controle, um de cada vez, e veja o jogo responder aos quatro.

**Passa quando.** Depois de reabrir, os quatro continuam lá: quatro etiquetas na faixa de cima, com os mesmos números e os mesmos transportes de antes, a conta dizendo «2 USB · 2 BT», as luzes de jogador nos mesmos números, e cada um respondendo dentro do jogo. E o nome em Perfil ativo é exatamente o mesmo que ela anotou antes de fechar.

**Por controle.**

* **P1** — No cabo, e não se desplugue nada. Depois de reabrir tudo, ele tem de voltar como P1, terminando em USB, e responder no jogo.
* **P2** — No cabo, igual ao P1. Depois de reabrir tudo, tem de voltar como P2, terminando em USB, e responder no jogo.
* **P3** — No rádio, e não se desliga nada. Depois de reabrir tudo, ele tem de voltar como P3, terminando em BT, e responder no jogo.
* **P4** — No rádio, igual ao P3. Depois de reabrir tudo, tem de voltar como P4, terminando em BT, e responder no jogo.

**A armadilha.** O perfil pode trocar sozinho quando o jogo fecha, e nisso o Hefesto está fazendo o que deve. Por isso as duas leituras do Perfil ativo têm de ser feitas com o jogo ABERTO: leia antes de fechar o jogo, e leia de novo só depois de o jogo já estar reaberto. Ler com o jogo fechado dá outro nome e parece defeito sem ser. A outra: fechar a janela do Hefesto não desliga o Hefesto — ele continua rodando por trás, e os quatro controles têm de continuar de pé com a janela fechada. Se algum controle cair e voltar em sequência bem na hora em que a janela fecha ou abre, isso é o defeito, e vale anotar a hora exata.

---

## Linha 13 — Perfil vivo por controle, sem clicar em Salvar

**O que isto prova.** Prova que o que você muda num controle, em cada aba, vale nele na hora, não encosta nos outros, e continua lá depois de fechar e reabrir o Hefesto — sem você clicar uma única vez em Aplicar ou em Salvar Perfil.

**Onde olhar.** Nos aparelhos: o punho esquerdo do P1 no «Testar», a resistência do L2 e do R2 do P2 no seu dedo, e a barra de luz do P4 (as duas tiras dos lados do touchpad). Na tela: a coluna de cada controle nas abas Vibração, Gatilhos e Iluminação — cada controle tem a sua coluna, com o nome no alto. E, no alto de qualquer aba, o nome em «Perfil ativo».

**Os passos.**

1. Abra a aba Vibração.
2. Leia o nome que aparece no alto da tela, em «Perfil ativo», e anote-o num papel.
3. Arraste até 0 a barra do «Motor esquerdo», na coluna do P1.
4. Confira que o número ao lado da barra mostra 0 %.
5. Clique em «Testar» na coluna do P1, com ele na mão.
6. Confira que só o punho direito treme.
7. Clique em «Parar» na coluna do P1.
8. Abra a aba Gatilhos.
9. Escolha «Rígido» na lista «Modo» da seção do L2 e na da seção do R2, na coluna do P2.
10. Confira, apertando o L2 e o R2 do P2, que os dois ganharam resistência, e, apertando os do P1, do P3 e do P4, que continuam como estavam.
11. Abra a aba Iluminação.
12. Clique, na linha «Cor» da coluna do P4, num tom sem X e bem diferente do que a barra dele tem agora.
13. Confira que a barra de luz do P4 mudou para o tom novo e que as dos outros três não mudaram.
14. Feche a janela do Hefesto pelo X.
15. Abra o Hefesto de novo.
16. Confira que o nome em «Perfil ativo» é o mesmo que você anotou.
17. Confira que a barra de luz do P4 continua no tom novo.
18. Abra a aba Vibração e clique em «Testar» na coluna do P1, com ele na mão.
19. Confira que a barra do «Motor esquerdo» do P1 continua em 0 e que só o punho direito treme.
20. Clique em «Parar» na coluna do P1.
21. Abra a aba Gatilhos e aperte o L2 e o R2 do P2.
22. Confira que o Modo do L2 e do R2 do P2 continua «Rígido» e que o seu dedo ainda sente a resistência.

**Passa quando.** Cada aba mostra o que foi feito NAQUELE controle, e o aparelho responde no instante do clique: o punho esquerdo do P1 mudo no «Testar», o L2 e o R2 do P2 duros, a barra do P4 no tom novo. O P3 termina exatamente como começou, e nenhum dos outros mudou junto. Depois de fechar e reabrir a janela, as três mudanças continuam lá — e em nenhum momento você clicou em Aplicar ou em Salvar Perfil.

**Por controle.**

* **P1** — Muda a VIBRAÇÃO, na aba Vibração: motor esquerdo em 0. No «Testar» só o punho direito treme, antes e depois de fechar e reabrir.
* **P2** — Muda o GATILHO, na aba Gatilhos: L2 e R2 em «Rígido». A resistência tem de estar lá antes e depois de fechar e reabrir.
* **P3** — Ninguém toca, é a testemunha. Está no rádio, e serve para provar que nenhuma das três mudanças vazou para ele: a barra de luz e os gatilhos dele têm de terminar como começaram.
* **P4** — Muda a COR, na aba Iluminação: um tom novo na barra. Está no rádio: a cor tem de acender no clique e continuar depois de fechar e reabrir.

**A armadilha.** POR QUE ESTE TESTE É LONGO: ele é o mesmo teste feito DUAS vezes — três mudanças em três abas antes de fechar a janela, e as três conferidas de novo depois de reabrir. Cortar a segunda metade seria cortar exatamente o que ele prova, que é o perfil sobreviver ao fechar. NÃO TOQUE em «Aplicar» nem em «Salvar Perfil», no rodapé, do começo ao fim: são eles que o teste existe para dispensar, e um clique neles apaga a prova. Clique em «Parar» antes de fechar a janela — o «Testar» não para sozinho. Feche só a JANELA do Hefesto, pelo X — não pare o serviço pela aba Sistema: com o serviço parado a luz e o gatilho voltam ao que o aparelho faz sozinho, e o teste reprova sem haver defeito. Faça este teste com a Steam fechada por inteiro — com ela aberta a barra de luz pode apagar sozinha depois de cada comando, porque quem escreve por último ganha e a Steam escreve direto no aparelho. Um tom com X é a cor de outro controle e não se escolhe. E não confie só na tela dos gatilhos: ela mostra o que o Hefesto mandou, não o que o gatilho está fazendo — o controle não sabe responder isso, e a prova é o seu dedo.

---

## Linha 14 — Gatilhos: usa o "Todos" com três ligados, e liga o quarto depois

**O que isto prova.** Prova que o botão «Em todos» põe o efeito de gatilho de uma coluna nos três controles ligados de uma vez, e o guarda como o efeito de todo mundo — a ponto de um quarto controle, ligado só depois, já nascer com ele.

**Onde olhar.** Na aba Gatilhos, no pé de cada coluna de controle, o botão «Em todos», ao lado do campo «Nome» e do «Guardar». Depois do clique, as colunas dos outros controles passam a mostrar o mesmo Modo. A prova de verdade é o dedo: aperte o L2 e o R2 de cada controle. E, no fim, a aba Perfis, tabela de baixo, coluna «Status»: ali cada controle tem uma linha, e o desenho do L2 e do R2 fica apagado quando aquele controle usa o gatilho do perfil inteiro, que é o que este teste quer ver.

**Os passos.**

1. Abra a aba Gatilhos.
2. Desligue o P4, segurando o botão PS até as luzes dele apagarem, e deixe-o longe da mesa: ele entra só depois do clique.
3. Confira que há um nome escrito no alto da tela, em «Perfil ativo».
4. Confira que a coluna do P4 passou a dizer «P4 • Desconectado», e que sobraram três colunas com controle.
5. Aperte o L2 e o R2 do P1, do P2 e do P3 e guarde na mão como eles estão hoje.
6. Escolha «Metralhadora» nas duas listas «Modo» da coluna do P1, a da seção do L2 e a da seção do R2.
7. Aperte o L2 e o R2 do P1 e sinta o efeito novo.
8. Clique em «Em todos», no pé da coluna do P1.
9. Confira que as colunas do P2 e do P3 passaram a mostrar «Metralhadora» no Modo do L2 e do R2.
10. Aperte o L2 e o R2 do P2 e os do P3, e sinta se o efeito novo chegou aos dois.
11. Ligue o P4 com um toque curto no PS.
12. Espere a coluna dele voltar com o nome dele.
13. Aperte o L2 e o R2 do P4 e sinta se ele já nasceu com o efeito.
14. Abra a aba Perfis.
15. Confira, na tabela de baixo, coluna «Status», que o desenho do L2 e do R2 está apagado nas quatro linhas de controle.

**Passa quando.** Um clique só põe o mesmo efeito no L2 e no R2 dos três controles ligados, e você sente isso no dedo nos três. O P4, que estava desligado na hora do clique, já nasce com o efeito quando você o liga. E na tabela da aba Perfis o L2 e o R2 ficam apagados nas quatro linhas — apagado ali quer dizer "usa o do perfil inteiro", que é justamente o que o «Em todos» tinha de escrever.

**Por controle.**

* **P1** — É a coluna em que você escolhe o efeito e de onde você clica em «Em todos». Sinta o L2 e o R2 dele antes e depois: é o ponto de partida da comparação.
* **P2** — Não escolha nada nele. Ele recebe pelo «Em todos», e você prova isso apertando o L2 e o R2 dele depois do clique. Está no cabo — se ele receber e o do rádio não, o problema é do rádio.
* **P3** — Não escolha nada nele. Ele também recebe pelo «Em todos», e é o único do rádio nesta rodada. Aperte o L2 e o R2 dele depois do clique.
* **P4** — Fica desligado durante o clique — é a testemunha. Ligue-o só depois. Se ele nascer com o efeito, o Hefesto guardou o efeito como o de todo mundo, que é o ponto inteiro do teste; se nascer sem, o efeito ficou preso nos três de antes e o teste reprovou.

**A armadilha.** Este teste é longo de propósito, e cortar qualquer ato tira prova: ele mede o mesmo dedo antes e depois em quatro controles, e o quarto só entra na mesa depois do clique — é essa entrada tardia que prova que o efeito virou o de todo mundo, e não uma cópia mandada aos três que estavam lá. O clique em «Em todos» não deixa frase na tela: a confirmação é o Modo das outras colunas mudar, e o dedo. Sem nome em «Perfil ativo» não há onde guardar o efeito de todos, e o controle 4 não vai herdar nada. O «Em todos» também apaga o ajuste próprio que cada controle tinha no L2 e no R2 — é o que ele promete, não defeito. E não decida pelo que a tela dos gatilhos mostra: ela mostra o que o Hefesto mandou, não o que o gatilho está fazendo — sem apertar o L2 e o R2 de cada controle, este teste dá verde sem prova.

---

## Linha 15 — Lançadores: cria um lançador para o jogo aberto e abre o jogo por ele

**O que isto prova.** Prova que, depois de o jogo ganhar o atalho do Hefesto e um perfil próprio, abrir esse jogo troca o perfil sozinho e os quatro controles continuam funcionando dentro dele.

**Onde olhar.** O nome do perfil que está valendo se lê no alto de qualquer aba, em «Perfil ativo» — é ali que a troca sozinha aparece. Na aba Jogar, no canto direito do quadro «Modo», o «Trava o perfil ativo». Na aba Lançadores, o botão «Detectar o jogo aberto» e o cartão da Steam, cujo texto passa a dizer o nome do jogo e se ele abre pelo atalho do Hefesto. Na aba Perfis, a lista «Perfis salvos» à esquerda, com o botão «Novo» embaixo, e o quadro «Editar» à direita, com «Nome:», «Funciona em:», «Nome do Jogo:» com o botão «Detectar» ao lado, e o botão «Ativar». No aparelho, a barra de luz do P1. E dentro do jogo, os quatro respondendo.

**Os passos.**

* Abra a aba Jogar.
1. Confira que o «Trava o perfil ativo», no canto direito do quadro «Modo», está apagado — se estiver aceso, clique nele para apagar.
2. Abra pela Steam o jogo que você quer testar.
3. Volte ao Hefesto com Alt+Tab e clique na aba Lançadores.
4. Clique em «Detectar o jogo aberto».
5. Leia a frase que aparece no cartão da Steam: ela diz o nome do jogo e se ele abre ou não pelo atalho do Hefesto.
6. Clique na aba Perfis e clique em «Novo», com o jogo ainda aberto.
7. Preencha o campo «Nome:» com o nome do jogo.
8. Confira que o «Nome do Jogo:» traz o seu jogo e que o «Funciona em:» diz «Steam» — se não, clique em «Detectar», ao lado do «Nome do Jogo:», e confira de novo.
9. Clique em «Ativar».
10. Clique na aba Iluminação e clique no amarelo, o quinto tom da linha «Cor», na coluna do P1.
11. Confira que a barra de luz do P1 ficou amarela.
12. Feche o jogo agora.
13. Se a frase do passo 5 disse que o jogo NÃO abre pelo atalho do Hefesto, vá à aba Sistema e clique em «Aplicar aos jogos da Steam», em Avançado, e clique de novo no mesmo botão para confirmar — ele fecha a Steam por uns 20 segundos.
14. Clique na aba Perfis, escolha outro perfil qualquer da lista e clique em «Ativar».
15. Confira que o alto da tela passou a mostrar esse outro nome em «Perfil ativo» e que a barra de luz do P1 deixou de ser amarela.
16. Abra pela Steam o mesmo jogo outra vez.
17. Veja a barra de luz do P1 assim que o jogo abrir.
18. Volte ao Hefesto com Alt+Tab.
19. Leia o nome que está em «Perfil ativo».
20. Volte ao jogo com Alt+Tab e aperte um botão de cada controle, um por vez, do P1 ao P4.
21. Confira que o jogo responde aos quatro.

**Passa quando.** Ao abrir o jogo, sem você tocar em nada, o nome em «Perfil ativo» vira o do perfil que você criou para ele, e a barra de luz do P1 fica amarela — os dois sinais da troca automática. E dentro do jogo os quatro controles respondem: os dois do cabo e os dois do rádio.

**Por controle.**

* **P1** — É o do cabo que carrega o sinal do perfil: a barra de luz dele fica amarela quando o perfil do jogo entra, e é por ela que você vê a troca acontecer sem sair do jogo. Depois, aperte um botão dele dentro do jogo.
* **P2** — O outro do cabo. Não recebe cor nova. Só tem de responder dentro do jogo — ele prova que a troca de perfil não derrubou quem estava mudo.
* **P3** — O primeiro do rádio. Só tem de responder dentro do jogo. É o que costuma cair primeiro quando alguma coisa dá errado sem fio, então aperte um botão dele com atenção.
* **P4** — O segundo do rádio. Só tem de responder dentro do jogo. Se três responderem e ele não, o defeito é do rádio ou do quarto lugar na fila — não da troca de perfil.

**A espera.** O jogo leva minutos para chegar ao menu, nas duas vezes em que você o abre, e você não precisa ficar olhando. Deixe-o carregando e vá fazer outra coisa; volte quando ouvir o som do menu. A troca de perfil acontece sozinha e continua feita quando você voltar — nada se desfaz por você ter saído da frente. Ao voltar da segunda vez, o primeiro lugar a olhar é a barra de luz do P1; se ela já apagou o amarelo, confirme pelo nome em «Perfil ativo», com Alt+Tab para o Hefesto.

**A armadilha.** O «Trava o perfil ativo», na aba Jogar, desliga a troca automática inteira: aceso, o perfil nunca troca e o teste reprova sem haver defeito. Confira que ele está apagado antes de começar. Trocar de perfil pelo «Ativar» segura a troca automática por trinta segundos — o jogo leva mais que isso para abrir, mas não reabra o jogo no mesmo instante. Perfil que «Funciona em» «Qualquer jogo» nunca conta como o perfil daquele jogo — a troca só acontece com um perfil que nomeia o jogo. A frase do cartão da Steam ainda manda clicar em «Consertar», um botão que saiu da aba: o caminho de hoje para o atalho é o «Aplicar aos jogos da Steam», da aba Sistema, e ele precisa do jogo fechado. O amarelo é para não esbarrar num tom com X: o verde é a cor automática do P3. E se, ao abrir o jogo, a barra de luz do P1 piscar amarela e apagar, olhe a Steam antes de reprovar: com ela aberta, quem escreve por último na luz ganha — nesse caso confie no nome em «Perfil ativo», não na luz. Por fim, o tamanho: este é o teste mais longo dos 21, e é longo de propósito. Ele encadeia quatro coisas que só provam juntas — ver se o jogo tem o atalho, criar o perfil que nomeia o jogo, marcar esse perfil com uma cor que se enxerga de dentro da partida, e só então fechar tudo e abrir de novo para ver a troca acontecer sem a sua mão.

---

## Linha 16 — Conexões: pareia um controle pela aba, quando a luz não acende

**O que isto prova.** Prova que mandar um controle que já está pareado voltar pelo rádio, pela própria aba Conexões, mostra a espera pelo PS com a contagem, devolve ele ao mesmo lugar — sem abrir um segundo assento para o mesmo controle — e que o «Cancelar» obedece.

**Onde olhar.** Na aba Conexões do Hefesto, na seção «Gestão de Controles», que abre com um clique no nome dela. Três coisas ali: a conta no canto da seção (por exemplo «4 controles • 2 no cabo • 2 no rádio»), a linha de cada controle («Sony • Player 4 • nome • BT» — o fim da linha diz USB para cabo e BT para rádio) e, dentro da linha aberta de um controle, o botão «A luz não acende». Durante a espera, o mesmo botão passa a dizer «Cancelar», e aparece no cartão dele a linha «▲ Aperte PS no controle · procurando…» com os segundos correndo para trás, a partir de 60.

**Os passos.**

1. Abra a aba Conexões.
2. Clique em «Gestão de Controles» para abrir a seção.
3. Anote a conta no canto da seção: quantos controles, quantos no cabo, quantos no rádio.
4. Anote a linha de cada um dos quatro controles: o número de Player e se ela termina em USB ou em BT.
5. Confira que a linha do P4 termina em BT — este teste só vale com ele no rádio.
6. Clique na linha do P4 para abri-la.
7. Clique no botão «A luz não acende», dentro da linha aberta do P4.
8. Confira, na mesa, que o P4 apagou e caiu do rádio.
9. Confira, na tela, que o botão passou a dizer «Cancelar» e que apareceu a linha «▲ Aperte PS no controle» com os segundos correndo para trás.
10. Aperte o botão PS do P4 uma vez.
11. Espere ele voltar — a contagem vai até 60 segundos.
12. Leia de novo a conta da seção e as quatro linhas da lista.
13. Clique de novo em «A luz não acende» na linha do P4.
14. Clique em «Cancelar» enquanto a contagem corre.
15. Confira que o botão voltou a dizer «A luz não acende», que a linha do «▲ Aperte PS» sumiu e que o P4 continua apagado.
16. Aperte o PS do P4 para religá-lo.

**Passa quando.** A espera pelo PS aparece com a contagem, e o P4 volta na mesma linha e com o mesmo número de Player que tinha antes; a conta volta ao mesmo número de antes, e não aparece nenhuma linha nova para o mesmo controle. No «Cancelar», a espera some na hora e o P4 fica fora até você apertar o PS. P1, P2 e P3 terminam com o número que tinham no começo.

**Por controle.**

* **P1** — Não se toca nele. Ele é testemunha: anote o número de Player e o fim da linha (USB ou BT) antes, e confira que estão iguais no fim.
* **P2** — Não se toca nele. Mesma testemunha: anote o número de Player e o fim da linha antes, e confira no fim.
* **P3** — Não se toca nele. Mesma testemunha: anote o número de Player e o fim da linha antes, e confira no fim.
* **P4** — É este. Ele precisa estar no rádio (linha terminando em BT). Abra a linha dele, clique em «A luz não acende», veja o controle apagar, aperte PS nele e espere voltar; depois, a segunda volta com o «Cancelar». De quebra, olhe a barra de luz dele depois da volta: fazer a barra voltar a obedecer é o motivo de este botão existir.

**A armadilha.** Falso vermelho: se o P4 estiver no cabo, o botão nasce cinza e a dica dele explica que só vale no rádio — ali o teste não roda, e isso não é defeito. Falso verde: se o P4 não apagar e o botão não virar «Cancelar», nada foi derrubado e o teste não provou coisa nenhuma — refaça. O «Cancelar» não religa nada: é ele que deixa o controle fora do rádio até você apertar PS por conta própria. E o «Conectar», da seção «Rádio e Adaptadores», é para controle NOVO; este teste é sobre um controle que já está pareado.

---

## Linha 17 — Reserva do posto: desliga o P2 por 20 segundos e religa

**O que isto prova.** Prova que o lugar de um controle fica guardado enquanto ele está desligado: o P2 sai por 20 segundos, volta como P2, e os outros três não trocam de número.

**Onde olhar.** Em dois lugares ao mesmo tempo. Na tela do Hefesto: a fita do topo, a linha que começa com "Selecionar:", onde cada controle é um chip («P2 • Starlight Blue • BT»), e a seção «Gestão de Controles», na aba Conexões, onde cada linha traz «Player 1», «Player 2» e assim por diante. No aparelho: a fileira de lampadinhas brancas embaixo do touchpad, que é o que diz o número — Player 1 acende só a do meio; Player 2 acende a segunda e a quarta; Player 3 acende as duas pontas e a do meio; Player 4 acende quatro, com a do meio apagada.

**Os passos.**

1. Abra a aba Conexões, com os quatro controles ligados.
2. Clique em «Gestão de Controles» para abrir a seção.
3. Anote o número de Player dos quatro, na lista.
4. Olhe as lampadinhas embaixo do touchpad de cada controle e confira que a figura bate com o número que a tela mostra.
5. Confira que a linha do P2 termina em BT — este teste é com ele no rádio.
6. Segure o botão PS do P2 até as luzes dele apagarem.
7. Comece a contar os 20 segundos a partir do momento em que o chip do P2 sai da fita do topo, e não de quando você soltou o botão.
8. Anote o que a lista mostra enquanto ele está fora.
9. Olhe os outros três durante a ausência — na tela e nas lampadinhas — e anote se algum trocou de número.
10. Aos 20 segundos, aperte o botão PS do P2 uma vez para religá-lo.
11. Espere o chip dele reaparecer na fita do topo.
12. Leia os quatro números de novo, primeiro na tela e depois nas lampadinhas dos quatro aparelhos.

**Passa quando.** O P2 volta como Player 2 — na tela e nas lampadinhas embaixo do touchpad. P1, P3 e P4 terminam com o mesmo número com que começaram.

**Por controle.**

* **P1** — Não se toca nele. Anote o número dele antes; ele tem de terminar com o mesmo, e a figura das lampadinhas tem de continuar a mesma.
* **P2** — É este, e ele tem de estar no rádio. Segure PS até apagar, conte 20 segundos a partir de quando o chip dele some da fita, e aperte PS uma vez para religar. No fim ele tem de voltar Player 2, com a segunda e a quarta lampadinhas acesas.
* **P3** — Não se toca nele. Testemunha: anote o número antes, olhe durante a ausência do P2, e confira no fim.
* **P4** — Não se toca nele. Testemunha: anote o número antes, olhe durante a ausência do P2, e confira no fim — as quatro lampadinhas acesas com a do meio apagada.

**A armadilha.** Olhe os outros três DURANTE a ausência, não só no fim: o produto de hoje fecha a fila enquanto alguém está fora — o P3 pode acender como 2 e o P4 como 3 até o P2 voltar, e cada um voltar ao seu depois. Se acontecer, anote com a hora: é exatamente a diferença entre "o assento fica reservado" e "ele volta P2", e é isso que este teste mostra. O prazo de trinta segundos do Hefesto é só o do posto de Jogador 1; o número do P2 é guardado pelo endereço dele, e um P2 que volte com outro número depois dos 20 segundos é achado, não demora sua. Na aba Conexões a linha de um controle desligado some da lista e a conta da seção cai — isso é a lista dizendo quem está ligado, não o lugar sendo perdido.

---

## Linha 18 — Modo Nativo com dois controles no jogo

**O que isto prova.** Prova que, com o Hefesto fora do meio, um jogo de co-op de sofá enxerga os dois controles como DualSense de verdade — dois jogadores, nenhum fantasma, e o movimento do controle respondendo. E que o Modo Nativo é a ÚNICA porta que devolve o aparelho inteiro ao jogo: fora dele, o botão, o toque e o movimento do DualSense ficam escondidos de todo programa menos o Hefesto.

**Onde olhar.** O resultado se lê na tela do JOGO, não na do Hefesto: quantos jogadores ele mostra, se ele pede "aperte um botão para entrar", e se girar o controle mexe alguma coisa. No Hefesto você confere só que o modo está de pé, na aba Jogar: a linha «Status» tem de estar em «Desligado», e o quadro «Modo» tem de mostrar «Modo Nativo · o controle sem o Hefesto no meio». E a conta no canto de cima à direita tem de dizer «2 USB» — com os dois do rádio desligados, o BT some da conta. Na aba Controles, o chip «Mira Virtual» de cada cartão fica cinza neste modo: o movimento vai inteiro ao jogo, sem a Mira no meio. A prova do movimento é no jogo, girando o controle na mão.

**Os passos.**

1. Desligue o P3 e o P4, segurando o botão PS de cada um até apagar — neste teste só o P1 e o P2 ficam na mesa.
2. Feche o jogo, se ele já estiver aberto.
3. Abra o Hefesto na aba Jogar.
4. Clique em «Desligado», na linha «Status».
5. Confira que o quadro «Modo» passou a mostrar «Modo Nativo».
6. Leia a conta no canto de cima à direita e confira que ela diz «2 USB» — se disser mais, algum controle ainda está ligado.
7. Abra o jogo de co-op de sofá agora, depois da troca de modo.
8. Aperte um botão no P1 e confirme que o jogo responde.
9. Aperte um botão no P2 e veja se o jogo mostra um segundo jogador ou pede para ele entrar.
10. Gire cada um dos dois controles na mão e veja se o jogo responde ao movimento.
11. Se o jogo usa o touchpad, passe o dedo no do P1 e veja se ele responde.
12. Anote o nome do jogo e o que apareceu na tela dele.
13. Faça a contraprova: feche o jogo, volte à aba Jogar e clique em «Ligado».
14. Abra o MESMO jogo de novo, com os mesmos dois controles.
15. Repita o aperto de botão de cada um e o giro dos dois, e anote a diferença.

**Passa quando.** No Modo Nativo o jogo mostra os dois jogadores — nem um a menos, nem um terceiro fantasma — e responde ao movimento dos dois. Um jogo que, no Nativo, responde aos botões e não ao movimento recebeu o aparelho pela metade: anote o nome dele. A contraprova é o que fecha o teste: se com o Hefesto Ligado o mesmo jogo mostrar dois jogadores e no Modo Nativo mostrar um só, o problema é do modo; se mostrar um nos dois casos, o jogo é que não tem co-op de sofá e o teste não vale.

**Por controle.**

* **P1** — Fica ligado e entra no jogo. É o controle base: abra o jogo com ele e confirme que responde antes de mexer no segundo.
* **P2** — Fica ligado e entra depois. É ele que responde a pergunta do teste: com o jogo já aberto e o P1 respondendo, aperte um botão no P2 e veja se o jogo abre um segundo jogador.
* **P3** — Fica fora. Desligue-o antes de começar, segurando o PS até apagar, e confira na conta do canto de cima à direita que o BT sumiu.
* **P4** — Fica fora. Desligue-o antes de começar, do mesmo jeito, e não o religue no meio do teste — religar muda a conta que o jogo faz no meio da medição.

**A armadilha.** Sem a contraprova este teste mente: um jogo que simplesmente não tem dois jogadores locais reprovaria o Modo Nativo sem culpa nenhuma. Segunda armadilha: a troca de modo só vale para o PRÓXIMO jogo que abrir — se o jogo já estava aberto quando você clicou, você vai medir o modo anterior; feche e abra de novo. Terceira: o Modo Nativo não é por controle, ele vale para a máquina inteira — por isso "ficar fora" aqui quer dizer desligado, e por isso a conta do canto de cima precisa dizer «2 USB» e nada de BT. E não julgue este teste pelas lampadinhas de número nem pela cor da barra: desde 24/09 as duas são do Hefesto também neste modo e mostram o número da aba, mesmo com o jogo falando direto com o controle; se o jogo acender outra coisa, o Hefesto devolve a dele em até um segundo.

---

## Linha 19 — Som: escolhe o alto-falante do P2 como saída de um tocador

**O que isto prova.** Prova que dá para escolher o alto-falante do controle 2 como a saída de um tocador, que o som sai só nesse controle, e que a lista de som do sistema tem um alto-falante para cada controle.

**Onde olhar.** Fora do Hefesto: a lista de saídas de áudio — a do tocador, ou a das configurações de Som do sistema —, onde cada controle tem o seu «Alto-falante do Controle N», com o N igual ao número do jogador. No Hefesto: aba Controles, cartão do P2, bloco Alto-falante — o selo ATIVO, o número do volume, o ♪ ao lado dele e os três botões «Efeitos do Jogo no Controle, Áudio da TV na TV», «Efeitos do Jogo e Áudio da TV no Controle» e «Tudo na TV e Nada no Controle». No aparelho: a grade de furinhos do alto-falante, na frente do controle, entre o touchpad e o botão PS.

**Os passos.**

1. Abra a aba Controles.
2. Confira na fita do topo que o P2 está por cabo — o chip dele termina em USB.
3. Clique na linha do P2 para abrir o cartão dele.
4. Confira no bloco Alto-falante do P2 que o selo diz ATIVO e que o número do volume não está em zero.
5. Clique em «Efeitos do Jogo no Controle, Áudio da TV na TV», no bloco do P2, se ele não estiver aceso.
6. Abra o seu tocador de música ou de vídeo e ponha alguma coisa para tocar.
7. Escolha «Alto-falante do Controle 2» como a saída de áudio do tocador — ou, se ele não tiver essa escolha, como a saída nas configurações de Som do sistema.
8. Confira que a lista de saídas mostra um «Alto-falante do Controle N» para cada um dos quatro controles.
9. Encoste o ouvido na grade do alto-falante do P2.
10. Confira que a música sai dali.
11. Encoste o ouvido no P1, depois no P3, depois no P4.
12. Confira que nenhum dos três toca, e que a TV também não toca a música.
13. Devolva a saída do tocador — ou do sistema — para a que estava antes.
14. Confira que a música voltou a sair onde saía.

**Passa quando.** A música do tocador sai pelo alto-falante do P2 e por nenhum dos outros três, nem pela TV, e devolver a saída faz o som voltar para onde estava. A segunda metade: a lista de saídas tem um «Alto-falante do Controle N» para cada controle.

**Por controle.**

* **P1** — Cabo, ninguém toca nele. É o de comparação: encoste o ouvido na grade do alto-falante dele e não pode sair nada.
* **P2** — Cabo, é ESTE. Abra o cartão dele, confira o selo e o volume, e escolha o «Alto-falante do Controle 2» como saída. É o único que pode tocar.
* **P3** — Rádio, ninguém toca nele. Encoste o ouvido: silêncio.
* **P4** — Rádio, ninguém toca nele. Encoste o ouvido: silêncio. Ele e o P3 juntos mostram que o som foi para UM controle, e não para todos os que estão no mesmo tipo de conexão.

**A armadilha.** Três coisas dão falso vermelho. Primeira: o ♪ ao lado do número é o MUDO do alto-falante, não a rota — se clicar nele o selo vira DESLIGADO e o P2 fica calado. Segunda: com o volume do P2 em zero, ou com «Tudo na TV e Nada no Controle» aceso, não sai som nenhum, por mais certa que a saída esteja. Terceira: a lista pode mostrar também a placa de som do próprio controle, com outro nome — a escolha deste teste é o «Alto-falante do Controle 2». E se a música sair num controle que não é o P2, com a saída no «Controle 2», anote: o número do nome não bateu com o do jogador, e esse é um achado deste teste.

---

## Linha 20 — Mudo no rádio: o botão do microfone do P3

**O que isto prova.** Prova que calar o microfone pelo botão de um controle ligado por rádio funciona, que o cartão diz, que a luz do botão acompanha, que o mudo não se desfaz sozinho, e que só aquele controle fica mudo.

**Onde olhar.** No Hefesto: aba Controles, cartão do P3 — o selo do microfone (ATIVO, DESLIGADO, ou «—» quando não foi lido) e a barrinha que mostra o som entrando agora; e, nas linhas fechadas do P1, do P2 e do P4, o selo ao lado da palavra Microfone. No aparelho: a luz vermelha do botãozinho de microfone do P3, logo abaixo do botão PS — acesa quer dizer ligado, apagada quer dizer desligado.

**Os passos.**

1. Abra a aba Controles.
2. Confira na fita do topo que o P3 está por rádio — o chip dele termina em BT.
3. Clique na linha do P3 para abrir o cartão dele.
4. Anote o que o selo do microfone do P3 diz agora, e o dos outros três.
5. Olhe a luz do botãozinho de microfone do P3 e anote se está acesa, apagada ou piscando.
6. Fale perto do P3 por uns segundos e confira que a barrinha do microfone no cartão dele se mexe.
7. Aperte uma vez o botãozinho de microfone do próprio P3.
8. Confira que o selo do microfone do P3 passou a dizer DESLIGADO e que a luz do botãozinho apagou.
9. Fale perto do P3 outra vez e confira que a barrinha fica parada.
10. Deixe o P3 quieto por 20 segundos, olhando o selo e a luz.
11. Confira que nenhum dos dois voltou sozinho.
12. Confira que os selos do P1, do P2 e do P4 continuam como estavam.
13. Aperte o botãozinho do P3 de novo.
14. Confira que o selo voltou a ATIVO e a luz voltou a acender.

**Passa quando.** Depois do aperto, o cartão do P3 passa a dizer DESLIGADO, a luz do botão dele apaga, a barrinha para de mexer com a voz, e os dois ficam assim pelos 20 segundos sem voltar sozinhos. Os outros três continuam exatamente como estavam. O segundo aperto devolve ATIVO e a luz acesa.

**Por controle.**

* **P1** — Cabo, testemunha. Só olhe o selo do microfone na linha fechada dele antes e depois: tem de continuar igual.
* **P2** — Cabo, testemunha. Mesma coisa — o selo do microfone dele não pode mudar.
* **P3** — Rádio, é ESTE. Abra o cartão, fale perto dele, aperte o botão do microfone NO CONTROLE, e depois olhe o selo, a barrinha e a luz — e espere os 20 segundos.
* **P4** — Rádio, testemunha, e é a que mais importa: ele está no mesmo tipo de conexão do P3. Se o selo do P4 também virar DESLIGADO, o aperto pegou o rádio inteiro em vez do controle apertado.

**A armadilha.** O 🎙 do cartão, ao lado do volume do microfone, NÃO é o mudo: ele liga o retorno — você passa a se ouvir — e fica verde até você clicar de novo. O mudo é o botão do plástico, e é ele que esta linha testa. A espera de 20 segundos está nos passos por uma razão medida: pelo rádio, o microfone já se desligou e religou sozinho, com o driver lendo o som do microfone como se fosse o botão — um selo que troca sem ninguém apertar é o achado. Um selo em «—» não é ATIVO nem DESLIGADO: quer dizer que o Hefesto não conseguiu ler o P3; anote e não conte como passa. E luz piscando com o selo em ATIVO é um programa ouvindo aquele microfone agora, não discordância.

---

## Linha 21 — Luz no rádio: uma cor no P4

**O que isto prova.** Prova que dar uma cor à barra de luz funciona num controle ligado por rádio, e que a cor não volta atrás sozinha.

**Onde olhar.** No Hefesto: aba Iluminação, coluna do P4 — a linha «Modelo» traz P4 e termina em BT; na linha «Cor» ficam os onze tons, com um X nos que outro controle está acendendo e o código da cor embaixo deles; na linha «Opções», o botão «Desligar». No aparelho: a barra de luz do P4, as duas tiras acesas dos dois lados do touchpad.

**Os passos.**

1. Abra a aba Iluminação.
2. Confira na linha «Modelo» que a coluna do P4 termina em BT.
3. Olhe a barra de luz do P4 no aparelho e anote a cor que ela tem agora.
4. Clique, na linha «Cor» da coluna do P4, num tom sem X e bem diferente da cor de agora — o amarelo, o quinto dos onze, costuma estar livre.
5. Confira que a barra de luz do P4 virou a cor escolhida na hora.
6. Confira que as barras de luz do P1, do P2 e do P3 não mudaram.
7. Espere 15 segundos sem clicar em nada, olhando a barra do P4.
8. Confira que ela continua na cor escolhida.
9. Clique no rosa, o quarto tom, na coluna do P4, para devolvê-lo à cor do número dele.

**Passa quando.** A barra de luz do P4 vira a cor escolhida no ato, mesmo ele estando por rádio, e continua nessa cor 15 segundos depois. As barras dos outros três não mudam.

**Por controle.**

* **P1** — Cabo, não pode mudar de cor. Olhe a barra dele antes e depois.
* **P2** — Cabo, não pode mudar de cor. Olhe a barra dele antes e depois.
* **P3** — Rádio, não pode mudar de cor — é a testemunha do mesmo tipo de conexão do P4. Se a cor nova acender nele também, o comando foi para o rádio inteiro.
* **P4** — Rádio, é ESTE. Recebe a cor nova pelo tom da coluna dele, e tem de ficar com ela até você devolvê-lo ao rosa.

**A armadilha.** O falso verde é escolher uma cor parecida com a que já estava: sem escolha à mão cada barra fica na cor do número do controle, e a do número 4 é rosa — clicando no rosa a barra não muda e não dá para saber se o clique chegou ao aparelho. Escolha uma cor que você reconhece de longe. Um tom com X é a cor de outro controle: o clique nele pisca e nada muda. O falso vermelho é usar a chave «Cores automáticas por controle» em vez do tom da coluna: aquela chave é do perfil inteiro, e desligá-la grava na hora a cor de todos os controles. Trocar para outra janela durante a espera pode trocar o perfil, e o perfil novo traz a cor dele — isso não é a cor voltando atrás; fique com o Hefesto na frente. E «Desligar» apaga a barra: não é o gesto deste teste.
