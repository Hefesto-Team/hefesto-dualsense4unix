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

O roteiro (`2026-09-06-MESA-DE-QUATRO-01…`) diz **o que** se testa, em uma
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

---

---

## Linha 1 — Liga dois no cabo e dois no rádio, um a um

**O que isto prova.** Prova que os quatro controles entram sozinhos, cada um com o seu número de P1 a P4 e com a cor do plástico certa, em menos de cinco segundos depois de você ligar.

**Onde olhar.** Na fita do topo do Hefesto — a linha que fica logo abaixo do nome Hefesto e começa com "Selecionar:". Cada controle que entra vira um chip com três coisas: o número (P1, P2, P3 ou P4), o nome da cor do plástico e por onde ele fala (a palavra cabo ou a palavra rádio). A borda do chip é pintada com a cor do plástico. Fique na aba Controles: além da fita, o topo faz a conta dos ligados ("4 controles: 2 USB · 2 BT"), e cada controle ganha um cartão com o nome e a bateria.

**Os passos.**

1. Desligue os quatro controles e desencaixe os dois cabos antes de começar.
2. Abra o Hefesto.
3. Clique na aba Controles.
4. Confira que a fita do topo está sem chip nenhum e que a conta do topo está em zero.
5. Deixe os quatro controles na mesa, na ordem em que você vai ligá-los.
6. Encaixe o cabo no PRIMEIRO controle e depois no PC.
7. Conte até cinco, devagar, olhando a fita.
8. Leia o chip que apareceu: ele tem de dizer P1, o nome da cor daquele controle e a palavra cabo.
9. Encaixe o segundo cabo no SEGUNDO controle e depois no PC, só agora que o P1 já está na fita.
10. Conte até cinco, devagar.
11. Leia o chip novo: P2, a cor daquele controle e a palavra cabo.
12. Dê um toque curto no botão PS do TERCEIRO controle, só depois de o P2 estar na fita.
13. Conte até cinco, devagar.
14. Leia o chip novo: P3, a cor daquele controle e a palavra rádio.
15. Dê um toque curto no botão PS do QUARTO controle, só depois de o P3 estar na fita.
16. Conte até cinco, devagar.
17. Leia o chip novo: P4, a cor daquele controle e a palavra rádio.
18. Confira a conta do topo: quatro controles, dois no cabo e dois no rádio.
19. Pegue cada controle na mão, um de cada vez, e compare o plástico dele com o nome e a cor da borda do chip que o nomeia.

**Passa quando.** Os quatro chips apareceram sozinhos, um por vez, cada um em menos de cinco segundos depois do gesto de ligar — sem você recarregar nada. Os números saíram P1, P2, P3 e P4, na mesma ordem em que você ligou, sem repetir e sem pular. Ligar um controle novo não mudou o número de nenhum dos que já estavam lá. E o nome e a cor da borda de cada chip batem com o plástico do controle que você tem na mão.

**Por controle.**

* **P1** — Ligue este PRIMEIRO, e pelo cabo. Ele tem de aparecer na fita como P1, com a cor do plástico dele e a palavra cabo.
* **P2** — Ligue este SEGUNDO, e pelo cabo, só depois de o P1 já estar na fita. Tem de entrar como P2, com a palavra cabo, e o P1 não pode trocar de número quando ele entra.
* **P3** — Ligue este TERCEIRO, e pelo rádio, com um toque curto no PS. Tem de entrar como P3, com a palavra rádio, e os dois do cabo têm de ficar parados nos números deles.
* **P4** — Ligue este POR ÚLTIMO, e pelo rádio, com um toque curto no PS. Tem de entrar como P4, com a palavra rádio, e os três de antes não podem mexer no número nem na cor.

**A armadilha.** Existe um jeito de a fita mentir bonito, e ele já enganou esta casa: quando a tela para de ler os controles de verdade, ela fica mostrando os dois chips do DESENHO — sempre os mesmos dois, "P1 · Cosmic Red" e "P2 · Starlight Blue". O sinal que os denuncia é a palavra do transporte: no chip vivo está escrito cabo ou rádio; no chip do desenho está escrito USB ou BT. Se você vir USB ou BT dentro de um chip, a fita não está lendo os seus controles, e o teste não passou nem reprovou — não houve leitura. (A conta lá do topo é o contrário: ali USB e BT estão certos, foi decisão sua.) Duas outras coisas que parecem defeito e não são: com um controle só na mesa o chip "Todos" não aparece, de propósito; e se a cor do plástico não tiver sido lida, o chip perde a borda colorida e o nome da cor, e a explicação aparece ao passar o mouse em cima — isso é a cor faltando, não o número errado.

---

## Linha 2 — Move cada controle dentro do jogo

**O que isto prova.** Prova que, com os quatro dentro do jogo, cada controle move só o boneco dele e nenhum controle move o boneco de outra pessoa.

**Onde olhar.** O lugar que decide é o JOGO: os quatro bonecos na tela. Qual boneco pertence a qual controle quem decide é o jogo, e a fonte não diz — por isso o primeiro passo é você anotar a dupla antes de mexer em qualquer coisa. Se algum boneco errado se mexer, o desempate está no Hefesto, aba Controles, com o chip "Todos" escolhido na fita: cada controle abre um cartão, e dentro do cartão o analógico tem um pontinho que anda quando você mexe no do aparelho e o desenho do botão acende quando você aperta. O cartão que reagir é o dono do movimento.

**Os passos.**

1. Abra o jogo em modo de quatro jogadores, com os quatro bonecos na tela.
2. Anote qual boneco é de qual controle, antes de mexer em nada.
3. Largue os quatro controles na mesa e ponha as mãos só no P1.
4. Empurre o analógico esquerdo do P1 para um lado e depois para o outro.
5. Veja o jogo: só o boneco 1 pode se mexer.
6. Empurre o analógico direito do P1 para os dois lados.
7. Veja o jogo de novo: só o boneco 1 pode se mexer.
8. Aperte as quatro direções do direcional do P1, uma de cada vez: cima, baixo, esquerda e direita.
9. Veja o jogo mais uma vez: só o boneco 1 pode se mexer.
10. Solte o P1.
11. Confira que nenhum boneco continua andando sozinho.
12. Refaça a mesma volta com o P2, depois com o P3 e depois com o P4, sempre com as mãos só naquele controle e os outros três largados na mesa.
13. Jogue uns vinte segundos com os quatro juntos, do jeito que se joga mesmo.
14. Repare se alguém troca de boneco no meio.
15. Se algum boneco errado tiver se mexido, vá ao Hefesto, aba Controles, clique no chip "Todos" da fita e mexa de novo no analógico do controle suspeito.
16. Veja em qual cartão o pontinho anda — o cartão diz de qual aparelho veio o movimento.

**Passa quando.** Nas quatro voltas, o boneco que se mexeu foi o do controle que estava na sua mão, e só ele: nenhum outro boneco andou junto, nenhum boneco ficou parado quando o dono dele mexeu, e nada continuou andando depois que você soltou. E nos vinte segundos com os quatro jogando juntos ninguém trocou de boneco no meio.

**Por controle.**

* **P1** — Segure só o P1 e mexa nos dois analógicos e nas quatro direções do direcional. Só o boneco 1 pode responder.
* **P2** — Segure só o P2, com os outros três largados na mesa, e faça os mesmos gestos. Só o boneco 2 pode responder.
* **P3** — Segure só o P3 e faça os mesmos gestos. Só o boneco 3 pode responder — e ele está no rádio, que é onde este defeito costuma aparecer.
* **P4** — Segure só o P4 e faça os mesmos gestos. Só o boneco 4 pode responder — este é o último a entrar e o mais propenso a nascer sem dono.

**A armadilha.** Mexer em dois controles ao mesmo tempo esconde exatamente o defeito que este teste procura. Quando um aparelho está alimentando dois jogadores, os dois bonecos andam JUNTOS — e com as duas mãos ocupadas isso parece que cada dono mexeu no seu. Um de cada vez, com os outros três largados na mesa, é o que revela. E se você mexer no P1 e o boneco 3 responder, não conclua nada olhando só o jogo: pode ser o jogo que embaralhou a ordem dos jogadores, não o Hefesto. Quem separa os dois é o cartão da aba Controles, e é para isso que ele está nos passos. E este teste é longo de propósito, com DEZ atos: os três gestos do P1 — o analógico esquerdo, o analógico direito e o direcional — são atos separados porque cada um tem de ter a olhada no jogo colada nele. Empacotados num ato só, quem lê mexe nos três e olha o jogo no fim, e um boneco alheio que andou no analógico direito passa despercebido — que é exatamente o defeito que esta linha existe para pegar.

---

## Linha 3 — Tira o P1 do cabo e põe no rádio, no meio da partida

**O que isto prova.** Prova que tirar o P1 do cabo e trazê-lo de volta pelo rádio, no meio da partida, não derruba os outros três e devolve a ele o mesmo número de antes.

**Onde olhar.** Três lugares, e o principal não é o controle que você está mexendo. Primeiro, a fita do topo do Hefesto: os chips dos outros três não podem sumir em momento nenhum, e o chip do que voltou tem de dizer P1 de novo, agora com a palavra rádio no lugar de cabo. Segundo, o JOGO: os bonecos 2, 3 e 4. Terceiro, o próprio aparelho que voltou — as cinco lâmpadas brancas em fileira, embaixo do touchpad: elas dizem o número do jogador pelo CONJUNTO que fica aceso.

**Os passos.**

1. Confira que o controle do P1 já foi pareado por rádio nesta máquina alguma vez — sem isso, o toque no PS não o traz de volta e o teste não roda.
2. Abra o jogo com os quatro jogadores dentro da partida.
3. Leia a fita do Hefesto e anote o número dos quatro, antes de mexer em nada.
4. Puxe o cabo de dentro do controle do P1.
5. Dê um toque no botão PS desse mesmo controle, sem demorar — do puxão do cabo até o toque tem de passar menos de trinta segundos.
6. Olhe a fita durante a troca: os chips dos outros três não podem sumir nem trocar de número em nenhum instante.
7. Olhe o jogo: os bonecos 2, 3 e 4 não podem travar, sumir nem parar de responder.
8. Espere o chip do controle que voltou reaparecer na fita e leia o que está escrito nele.
9. Vire para cima o controle que voltou e olhe as cinco lâmpadas brancas embaixo do touchpad.
10. Empurre o analógico esquerdo do controle que voltou e confira que ele move o boneco 1 de novo.
11. Mexa nos outros três, um de cada vez, e confira que cada um continua movendo o boneco dele.

**Passa quando.** Do puxão do cabo até o fim, os chips dos outros três continuaram na fita, com os mesmos números, e os bonecos 2, 3 e 4 continuaram respondendo. O controle que trocou voltou à fita como P1 — o mesmo número que tinha antes —, agora dizendo rádio. As lâmpadas dele mostram o desenho do jogador 1: só a do meio acesa. E ele volta a mover o boneco 1.

**Por controle.**

* **P1** — É ESTE que troca: puxe o cabo e devolva-o pelo rádio com um toque no PS, em menos de trinta segundos. Tem de voltar como P1, agora dizendo rádio, com só a lâmpada do meio acesa, e tem de voltar a mover o boneco 1.
* **P2** — Não encoste nele durante a troca. O chip dele não pode sumir da fita nem trocar de número, e depois da troca ele tem de continuar movendo o boneco 2.
* **P3** — Não encoste nele durante a troca. Ele está no rádio, que é onde a queda em cadeia costuma aparecer: o chip dele não pode piscar para fora da fita, e depois ele tem de continuar movendo o boneco 3.
* **P4** — Não encoste nele durante a troca. Também está no rádio e é o último da fila, o primeiro a cair quando alguma coisa desmonta: chip na fita o tempo todo, número intacto, e o boneco 4 respondendo depois.

**A armadilha.** Duas, e as duas fazem você julgar errado. A primeira é a leitura das lâmpadas: as cinco do DualSense não se contam da esquerda para a direita — o número é o CONJUNTO aceso. Jogador 1 é só a do meio. Jogador 2 são a segunda e a quarta. Jogador 3 são a primeira, a do meio e a última. Jogador 4 são as quatro das pontas, com a do meio apagada. Quem lê "a terceira lâmpada acesa" como jogador 3 reprova um produto que está certo. A segunda é o relógio: o lugar de P1 fica guardado por trinta segundos para quem caiu. Se você demorar mais que isso entre puxar o cabo e tocar o PS, ele volta com outro número — e isso é a regra do produto funcionando, não defeito. Refaça mais rápido. E o erro de mira: a tentação é ficar olhando o controle que você está mexendo. Este teste se decide nos OUTROS TRÊS.

---

## Linha 4 — Desliga um controle do rádio, com PS longo

**O que isto prova.** Prova que desligar um controle do rádio não bagunça os outros três, e que o lugar do que saiu fica guardado.

**Onde olhar.** Nos próprios aparelhos: as cinco lâmpadas do indicador de jogador (a fileira logo abaixo do touchpad, no arranjo 1 · vão · 3 · vão · 1) e a barra de luz (as duas tiras que ladeiam o touchpad). No Hefesto, dois lugares: a contagem no alto de qualquer aba, que hoje diz "● 4 controles: 2 USB · 2 BT"; e, na aba Controles, o quadro Dispositivos Conectados, onde o lugar de um controle que saiu passa a dizer "P3 • Desconectado". Se quiser conferir as lâmpadas pela tela em vez de olhar o aparelho, use a aba Iluminação: é a única em que o desenho do controle é grande o bastante para as cinco lâmpadas se lerem.

**Os passos.**

1. Confira que os quatro estão ligados: P1 e P2 no cabo, P3 e P4 no rádio.
2. Abra a aba Iluminação do Hefesto.
3. Anote o número de jogador de cada um dos quatro controles.
4. Anote a cor da barra de luz de cada um dos quatro.
5. Leia a contagem no alto da aba e anote o que ela diz.
6. Pegue o P3, que é um dos dois do rádio.
7. Segure o botão PS do P3 — o redondo com o símbolo da PlayStation, no meio de baixo, entre os dois analógicos.
8. Continue segurando até todas as luzes do P3 apagarem.
9. Solte o botão e ponha o P3 na mesa.
10. Deixe o cronômetro desta página correr os vinte segundos, olhando os três controles que ficaram na mesa.
11. Confira nos três que ficaram se as lâmpadas continuam no mesmo padrão que você anotou.
12. Confira nos três que ficaram se a cor da barra de luz continua a mesma.
13. Volte ao Hefesto e leia a contagem no alto da aba: tem de dizer três controles.
14. Abra a aba Controles e confira que o lugar do P3 diz "Desconectado" e que nenhum outro controle se mudou para ele.
15. Registre nesta página a resposta de cada um dos quatro.

**Passa quando.** Os três que continuaram ligados — P1, P2 e P4 — seguem com o mesmo número de jogador e a mesma cor de barra de luz que tinham antes. Nenhum deles ocupa o lugar que era do P3: esse lugar aparece vazio na tela e continua vazio durante os vinte segundos.

**Por controle.**

* **P1** — Fica ligado, no cabo. Não toque nele. Anote o número e a cor da barra de luz antes de desligar o P3 e confira os dois depois — têm de ser exatamente os mesmos.
* **P2** — Fica ligado, no cabo. Não toque nele. Mesma conferência do P1: número e cor iguais antes e depois. Se algum dos dois do cabo mudar, anote que foi um do CABO.
* **P3** — É ESTE que desliga, e é o único que você toca. Está no rádio. Segure o botão PS até todas as luzes dele apagarem, solte e deixe-o parado na mesa pelos vinte segundos.
* **P4** — Fica ligado, no rádio. Não toque nele. É o vizinho de rádio do que caiu, então é nele que uma bagunça costuma aparecer primeiro: confira número e cor antes e depois, e veja se ele não se mudou para o lugar do P3.

**A armadilha.** Soltar o botão PS cedo demais. Aí o controle não desliga e o teste mede o seu gesto, não o produto — e há um efeito colateral já visto nesta casa: com cerca de cinco segundos de botão, o Hefesto lê o aperto como um toque no PS e abre a Steam. Segure até as luzes apagarem; se a Steam abrir, feche-a e refaça a linha.

---

## Linha 5 — Religa o controle que foi desligado

**O que isto prova.** Prova que o controle que voltou reencontra o lugar que era dele, sem empurrar ninguém dos outros três.

**Onde olhar.** Nos aparelhos: as cinco lâmpadas do indicador de jogador, abaixo do touchpad. O padrão diz o número — jogador 1 acende só a do meio; jogador 2 acende a segunda e a quarta; jogador 3 acende as duas das pontas e a do meio; jogador 4 acende as quatro, menos a do meio. E a barra de luz, as duas tiras ao lado do touchpad: quando ninguém escolheu cor à mão, o Hefesto pinta por número — 1 azul, 2 vermelho, 3 verde, 4 rosa. No Hefesto: a contagem no alto de qualquer aba, que tem de voltar a "● 4 controles: 2 USB · 2 BT", e o quadro Dispositivos Conectados da aba Controles, onde o lugar do P3 tem de deixar de dizer "Desconectado" e voltar com o nome e a cor de plástico dele.

**Os passos.**

1. Deixe P1, P2 e P4 exatamente como estão, sem tocar em nenhum.
2. Pegue o P3, que está desligado.
3. Segure o botão PS do P3 por cerca de cinco segundos.
4. Solte quando a barra de luz dele acender.
5. Ponha o P3 na mesa.
6. Deixe o cronômetro desta página correr os dez segundos.
7. Conte quais das cinco lâmpadas do P3 acenderam.
8. Confira que acenderam as duas das pontas e a do meio — é o padrão do jogador 3.
9. Olhe as lâmpadas dos outros três e confira que nenhum mudou de padrão.
10. Olhe a cor da barra de luz dos quatro e confira que nenhuma trocou de dono.
11. Abra a aba Controles do Hefesto.
12. Leia a contagem no alto: tem de voltar a dizer quatro controles, 2 USB · 2 BT.
13. Confira no quadro Dispositivos Conectados que o P3 voltou com o nome e a cor dele, e que os outros três continuam nos mesmos lugares.
14. Registre nesta página a resposta de cada um dos quatro.

**Passa quando.** O P3 volta como jogador 3 — as mesmas três lâmpadas de antes — e os outros três continuam com os números que já tinham. Ninguém foi empurrado para outro lugar para abrir espaço para ele, e ninguém perdeu o seu.

**Por controle.**

* **P1** — Não pode mudar de posto. Está no cabo. Não toque nele. Confira, depois que o P3 voltar, que o número e a cor da barra de luz continuam os de antes.
* **P2** — Não pode mudar de posto. Está no cabo. Não toque nele. Mesma conferência do P1.
* **P3** — É ESTE que religa, e é o único que você toca. Está no rádio. Segure o botão PS por cerca de cinco segundos, até a barra de luz acender, e ponha-o de volta na mesa. Tem de voltar como jogador 3.
* **P4** — Não pode mudar de posto. Está no rádio. Não toque nele. É aqui que se vê se alguém tomou o lugar do P3 enquanto ele estava fora — olhe as lâmpadas dele com atenção.

**A armadilha.** Demorar, ou religar pelo cabo. O Hefesto guarda o lugar de quem cai por um prazo, e hoje esse prazo é de trinta segundos: passando disso, o que você vê é o prazo ter vencido, não o produto errando. E religar plugando o cabo é outro teste, com resposta possivelmente diferente — ninguém mediu essa ainda. Religue logo, e pelo botão PS.

---

## Linha 6 — Vibração: testa em um de cada vez

**O que isto prova.** Prova que a vibração é de um controle só: quem você mandou tremer treme, e os outros três ficam quietos.

**Onde olhar.** Na aba Vibração do Hefesto: as quatro colunas lado a lado, uma por controle, com o nome de cada um embaixo do desenho ("P1 • cor • cabo"). Duas linhas importam: "Força da vibração", com os três degraus Economia · Balanceado · Máximo, e "Testar agora", com os botões Testar e Parar. O tremor em si não aparece em campo nenhum da tela — a prova dele é a sua mão e o seu ouvido, e é honesto dizer isso. No aparelho, os dois motores ficam um em cada punho: o esquerdo tem o contrapeso maior e soa grosso, o direito soa fino.

**Os passos.**

1. Pause o jogo que está aberto, ou deixe-o numa tela parada.
2. Abra a aba Vibração do Hefesto.
3. Anote qual degrau está aceso na linha "Força da vibração" de cada uma das quatro colunas.
4. Clique, na coluna do P1, num degrau diferente do que estava aceso — por exemplo, Máximo.
5. Confira que só a coluna do P1 mudou de degrau, e que as outras três continuam no que você anotou.
6. Ponha P2, P3 e P4 parados sobre a mesa, sem nada por cima e sem encostar neles.
7. Segure o P1 com uma das mãos.
8. Clique em "Testar" na coluna do P1 com a outra mão.
9. Sinta o meio segundo de tremor no P1, nos dois punhos.
10. Olhe e escute os outros três na mesa durante esse meio segundo: nenhum pode se mexer nem zumbir.
11. Clique em "Parar" na coluna do P1 se ele continuar tremendo depois do meio segundo.
12. Registre nesta página a resposta de cada um dos quatro.

**Passa quando.** Só o P1 treme, e por meio segundo. P2, P3 e P4 ficam parados e mudos. E o ajuste de força que você mexeu vale só para o P1: as outras três colunas continuam mostrando o degrau que tinham antes.

**Por controle.**

* **P1** — É ESTE que deve tremer. Está no cabo. Antes de testar, mude o degrau da "Força da vibração" só na coluna dele. Depois segure-o na mão, clique em Testar na coluna dele e sinta meio segundo de tremor nos dois punhos.
* **P2** — Não pode tremer. Está no cabo. Deixe-o parado na mesa durante o teste do P1. A coluna dele tem de continuar no degrau que estava — se ela mudou junto com a do P1, o ajuste vazou de um controle para outro.
* **P3** — Não pode tremer. Está no rádio. Parado na mesa, sem encostar. Se ele tremer, anote que quem tremeu sem ser chamado estava no RÁDIO — é o que separa um defeito do cabo de um defeito do rádio.
* **P4** — Não pode tremer. Está no rádio. Parado na mesa, sem encostar. Confira também que a coluna dele não trocou de degrau sozinha quando você mexeu na do P1.

**A armadilha.** Tremor que não é seu, e tremor curto demais. Com o jogo aberto, é ele quem manda os controles vibrarem, e um tremor no P2 pode ser do jogo e não do teste — por isso o primeiro passo é pausar. E o Testar dura meio segundo: com o P1 largado na mesa em vez de na sua mão, dá para não sentir e marcar "nada aconteceu" sobre um produto que obedeceu.

---

## Linha 7 — Gatilhos: aplica um efeito só no P3

**O que isto prova.** Prova que um efeito de gatilho escolhido na coluna de um controle vai só para aquele controle, e os outros três continuam do jeito que estavam.

**Onde olhar.** Na aba Gatilhos do Hefesto. Cada controle tem uma coluna, com a etiqueta dele no alto (o número, a cor do plástico e por onde ele está ligado). A coluna da esquerda nomeia as linhas: Modo, Efeito pronto e Ajustes, uma vez para o Gatilho esquerdo (o L2) e outra para o Gatilho direito (o R2). Mas quem responde este teste é a sua mão, e não a tela: o controle não devolve em que efeito ele está, então o campo Modo mostra o que foi PEDIDO, nunca o que está no aparelho. A resposta é a resistência que você sente ao apertar o L2 e o R2.

**Os passos.**

1. Abra a aba Gatilhos.
2. Confira que as quatro colunas têm etiqueta de controle no alto, e que nenhuma diz que o lugar está vazio.
3. Aperte o L2 e o R2 de cada um dos quatro controles, um por vez, para guardar na mão como cada um está ANTES.
4. Escolha «Rígido» no campo Modo da linha Gatilho esquerdo, na coluna do P3.
5. Aperte o L2 do P3.
6. Confira, na mão, que ele travou duro do começo ao fim do curso.
7. Escolha «Rígido» no campo Modo da linha Gatilho direito, na mesma coluna do P3.
8. Aperte o R2 do P3.
9. Confira, na mão, que ele travou também.
10. Aperte o L2 e o R2 do P1, do P2 e do P4 de novo, um por vez.
11. Compare com o que você sentiu no começo: os três têm de estar iguais, nenhum mais duro e nenhum mais solto.
12. Escolha «Desligado» no campo Modo das duas linhas do P3, o Gatilho esquerdo e o Gatilho direito (com isto o teste está desfeito, e a troca automática de perfil, que o efeito tinha pausado, volta a valer).
13. Aperte o L2 e o R2 do P3.
14. Confira que os dois voltaram a ficar leves.

**Passa quando.** Só o L2 e o R2 do P3 ficam duros. Os gatilhos do P1, do P2 e do P4 continuam exatamente como estavam antes — nenhum endureceu e nenhum ficou mais solto. E, ao escolher «Desligado» nas duas linhas do P3, os dois gatilhos dele voltam a ficar leves na sua mão.

**Por controle.**

* **P1** — Não toque na coluna dele. Aperte o L2 e o R2 antes e depois; tem de estar igual nas duas vezes.
* **P2** — Não toque na coluna dele. Aperte o L2 e o R2 antes e depois; tem de estar igual nas duas vezes.
* **P3** — É o único em que você mexe. Ponha «Rígido» no Modo do Gatilho esquerdo e no do Gatilho direito, e sinta os dois travarem. No fim, ponha «Desligado» nos dois para desfazer.
* **P4** — Não toque na coluna dele. Aperte o L2 e o R2 antes e depois; tem de estar igual nas duas vezes.

**A armadilha.** Não use «Desligado» como o efeito do teste. Ele é a escolha que SOLTA o gatilho, e se ela escapar para os quatro você não vê nada — os outros três já estão soltos, e o teste passa por cima do defeito. O efeito do teste tem de ser um que ENDUREÇA, porque endurecer é o que a mão sente. E não julgue pela tela: o campo Modo continua mostrando «Rígido» mesmo se um jogo escrever por cima e o gatilho estiver leve na sua mão. Se você não apertar os quatro ANTES, não tem com o que comparar depois — e aí o teste não mede nada.

---

## Linha 8 — Iluminação: uma cor diferente em cada um, e depois o automático

**O que isto prova.** Prova que cada controle obedece à cor que você escolheu na coluna dele, inclusive os que estão por rádio, e que o botão «Automático» devolve ao Hefesto o direito de trocar de perfil sozinho.

**Onde olhar.** Na aba Iluminação do Hefesto. Cada controle tem uma coluna e a etiqueta dele no alto. As linhas, nomeadas na coluna da esquerda, são Controle, Modelo, Cor, Brilho, Jogador, LEDs e Opções: a linha Cor tem oito bolinhas de cor, a linha Opções tem os botões «Automático» e «Desligar». A prova, porém, é no aparelho: a barra de luz é a faixa que acende dos dois lados do touchpad, em cada controle. A linha LEDs da tela mostra a cor que o Hefesto PEDIU — e embaixo dela aparece uma ressalva quando ele não tem certeza, do tipo «Lightbar: cor desconhecida». O perfil que está valendo se lê no alto, à direita, em «Perfil ativo», e ele é igual nas dez abas.

**Os passos.**

1. Abra a aba Iluminação.
2. Leia a etiqueta no alto das quatro colunas e anote qual controle está por cabo e qual está por rádio.
3. Clique numa das oito bolinhas da linha Cor, na coluna do P1.
4. Confira, no aparelho, que a barra de luz do P1 acendeu nessa cor.
5. Clique numa bolinha de cor diferente na linha Cor da coluna do P2.
6. Confira a barra do P2 e veja que a do P1 continua na cor dela.
7. Clique numa terceira cor na linha Cor da coluna do P3.
8. Confira a barra do P3 e que as do P1 e do P2 não mudaram.
9. Clique numa quarta cor na linha Cor da coluna do P4.
10. Veja os quatro controles juntos: quatro barras acesas, quatro cores diferentes, ao mesmo tempo.
11. Traga para a frente a janela de um jogo que já tenha perfil próprio no Hefesto.
12. Confira o «Perfil ativo» no alto da tela: agora ele NÃO deve trocar — pintar a cor à mão pausa a troca automática, e é isso que a segunda metade do teste vai destravar.
13. Volte para a janela do Hefesto.
14. Clique em «Automático» na linha Opções de cada uma das quatro colunas, uma coluna de cada vez.
15. Confira, a cada clique, que a barra daquele controle passa a acender a cor do número dele.
16. Traga a janela do mesmo jogo para a frente de novo.
17. Confira o «Perfil ativo»: agora ele tem de trocar para o perfil daquele jogo.

**Passa quando.** As quatro barras de luz ficam acesas ao mesmo tempo, cada uma na cor que você escolheu para ela — inclusive as dos dois controles que estão por rádio —, e pintar uma nunca muda a cor de outra. Depois dos quatro cliques em «Automático», o «Perfil ativo» no alto da tela volta a trocar sozinho quando um jogo com perfil próprio vem para a frente.

**Por controle.**

* **P1** — Ponha uma cor e anote qual. A barra dele tem de acender nela e continuar acesa até o fim do teste.
* **P2** — Ponha uma segunda cor, diferente da do P1. No instante em que você pintar este, olhe o P1: ele não pode mudar.
* **P3** — Ponha uma terceira cor. Se a etiqueta dele disser rádio, é aqui que está a metade que interessa do teste: a cor tem de chegar igual à de quem está por cabo.
* **P4** — Ponha a quarta cor. No fim, os quatro acesos ao mesmo tempo, cada um na sua.

**A armadilha.** A tela não é a prova. O desenho da linha LEDs mostra a cor que o Hefesto pediu, e a ressalva embaixo dele avisa quando ele não tem certeza — «Lightbar: cor desconhecida», por exemplo. Quem responde é a faixa acesa no plástico. Não mexa no interruptor «Cores automáticas por controle», no alto da aba: ele é do perfil e vale para os quatro de uma vez, e este teste é sobre a coluna de cada um. Duas coisas parecem defeito e não são: as cinco lampadinhas de jogador podem apagar depois do «Automático» e não voltam sozinhas — isso já foi medido —; e, se você acabou de fazer o teste dos gatilhos, o «Automático» daqui solta só a luz, o gatilho continua segurando a troca de perfil, e o «Perfil ativo» não vai mudar por causa dele (ponha «Desligado» no gatilho que ficou, ou troque de perfil uma vez na mão). E antes de dar vermelho na última parte, olhe a aba Jogar: se a caixa «Não trocar de perfil sozinho ao abrir um jogo» estiver marcada, ou se estiver escrito lá que o Hefesto não está conseguindo ver qual programa está na frente, esta metade não tem como ser medida hoje.

---

## Linha 9 — Microfone: aperta o botão físico de cada um, um por vez

**O que isto prova.** Prova que apertar o botão de microfone de um controle cala aquele controle e só ele, e que a luz do botão conta a mesma história que a tela.

**Onde olhar.** No aparelho: o botão do microfone é o botãozinho de mudo no plástico, logo abaixo do touchpad, e ele tem uma luz vermelha. Na tela: abra a aba Controles. Cada controle tem um cartão, com o número e a cor do plástico no alto, e dentro dele a linha «Microfone» com um selo ao lado que diz ATIVO, MUDO ou «—» (o travessão quer dizer «não consegui ler», e não é nenhum dos dois). O selo aparece com o cartão aberto ou fechado; com ele aberto vem também uma barrinha de ondas, que mexe com o som que está entrando agora.

**Os passos.**

1. Abra a aba Controles.
2. Abra os quatro cartões.
3. Leia o selo do Microfone dos quatro e anote o que cada um diz — este é o ponto de partida.
4. Fale perto do P1 e confira que a barrinha de ondas do cartão dele mexe.
5. Aperte uma vez o botão do microfone do P1, no plástico.
6. Olhe a luz vermelha do botão do P1 e anote se ela acendeu ou apagou.
7. Olhe os quatro selos na tela e veja qual deles mudou.
8. Espere um segundo.
9. Aperte o botão do P1 de novo e confira que a luz e o selo voltam ao que eram.
10. Repita os passos 4 a 9 no P2, e só passe adiante quando o selo dele tiver assentado.
11. Repita os passos 4 a 9 no P3, e só passe adiante quando o selo dele tiver assentado.
12. Repita os passos 4 a 9 no P4.
13. Confira, no fim, que os quatro selos voltaram a dizer o que diziam no passo 3.

**Passa quando.** Cada aperto mexe no microfone do controle que foi apertado, e só nele: o selo daquele cartão troca e os outros três ficam parados. A luz vermelha do botão apertado muda a cada aperto, e sempre do mesmo jeito nos quatro controles — se ela acende quando o selo diz MUDO num, tem de acender nos outros três também. E no fim os quatro voltam ao que estavam no começo.

**Por controle.**

* **P1** — Aperte o botão do microfone dele e espere o selo assentar. A luz do botão muda, o selo do P1 troca, e os selos do P2, do P3 e do P4 não se mexem. Aperte de novo para voltar.
* **P2** — Mesmo gesto. Antes de apertar, olhe onde estão os quatro selos: o erro que este teste caça é o aperto de UM controle calar o microfone de OUTRO, e ele só se enxerga se você souber o de antes.
* **P3** — Mesmo gesto. Se a etiqueta dele disser rádio, este é o caso já conhecido: pelo rádio o mudo pode se desfazer sozinho quando o controle cai e volta, sem nada avisando. Se acontecer, é achado do teste, e não erro seu.
* **P4** — Mesmo gesto, e é o último. Confira no fim que os quatro selos voltaram ao que diziam no começo.

**A armadilha.** Não clique no botão de microfone da TELA (o 🎙 ao lado do volume, dentro do cartão) antes deste teste. Ele passa o comando do mudo para o Hefesto, e a partir daí o botão do plástico daquele controle para de valer — o controle daria vermelho estando são. Se já clicou, esta tela não devolve o comando: a volta é reiniciar o Hefesto. Dê um segundo entre um aperto e o seguinte NO MESMO controle: apertos mais rápidos que isso são engolidos de propósito, para não contar repique — um segundo aperto que «não fez nada» pode ser só isso. Um selo em «—» não é ATIVO nem MUDO: quer dizer que o Hefesto não conseguiu ler aquele controle; anote e não conte como passa. E sobre a luz: a dica do 🎙 da tela diz que calar APAGA a luz vermelha, mas ela descreve o caminho da tela, não o do botão do plástico — por isso o teste pede que você ANOTE o que a luz fez de verdade a cada aperto, em vez de esperar um sentido. Se ela discordar do selo, ou se fizer coisas diferentes em controles diferentes, isso é o achado.

---

## Linha 10 — Bateria: anota os quatro números e volta neles aos 20 minutos

**O que isto prova.** Prova que o número da bateria dos quatro controles anda com o tempo, em vez de ficar congelado.

**Onde olhar.** Na aba Controles do Hefesto. Cada controle tem uma linha, e no fim dela vem a palavra Bateria, uma barrinha e o número em porcento. Com os quatro cards fechados, os quatro números aparecem juntos na mesma tela. A linha de cada controle também diz, ao lado da cor do plástico, a palavra cabo ou rádio.

**Os passos.**

1. Abra a janela do Hefesto.
2. Clique na aba Controles.
3. Feche os cards que estiverem abertos, clicando na linha de cada um — com os quatro fechados, os quatro números cabem na mesma tela.
4. Confira a palavra no fim do nome de cada linha: P1 e P2 têm de dizer cabo, P3 e P4 têm de dizer rádio.
5. Anote num papel os quatro números de bateria, um embaixo do outro, na ordem P1, P2, P3, P4.
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

**O que isto prova.** Prova, com o ouvido dela, se sai som pelo alto-falante de um controle que está no rádio.

**Onde olhar.** Duas coisas. Primeiro o ouvido dela, encostado no alto-falante do próprio controle: são nove furinhos em duas fileiras, no meio da frente do DualSense, logo abaixo e entre os dois analógicos. Segundo, o card do P3 na aba Controles: o bloco Alto-falante, com o deslizante de volume e os dois botões Sons do jogo e Todo o som do PC, e a linha de ressalva embaixo dele. Se essa linha disser 'Pelo rádio o Hefesto ainda não faz o som sair neste alto-falante', o próprio produto já está avisando que este caminho não existe hoje.

**Os passos.**

1. Clique na aba Controles.
2. Confira que o P3 está só no rádio: nenhum cabo plugado nele.
3. Toque uma música ou um vídeo qualquer, num volume que dê para ouvir nas caixas.
4. Clique na linha do P1 para abrir o card dele.
5. Encoste o ouvido nos nove furinhos do P1 e deixe-o ali pela rodada inteira dele.
6. Arraste o deslizante de volume do bloco Alto-falante do P1 até o fim da direita.
7. Confira que o P1 deu o som curto de confirmação que o controle deve dar ao receber o volume.
8. Clique em Todo o som do PC, no bloco do P1.
9. Confira que a música passou a sair pelo alto-falante do P1.
10. Clique em Sons do jogo, no bloco do P1, para devolver o som às caixas, e clique na linha do P3 para abrir o card dele; o do P1 fecha sozinho.
11. Leia a linha de ressalva embaixo do bloco Alto-falante do P3 e anote se ela apareceu e o que diz.
12. Encoste o ouvido nos nove furinhos do P3 e deixe-o ali pela rodada inteira dele.
13. Refaça no P3, com o ouvido encostado, os dois gestos de tela que fez no P1: o volume até o fim da direita e o Todo o som do PC.
14. Confira se o P3 deu o som de confirmação no volume e se a música saiu por ele no Todo o som do PC — e anote a resposta como ela vier, porque o silêncio também é resposta.
15. Encoste o ouvido no P4, em que ninguém tocou, e escute.
16. Confira que o P4 ficou mudo do começo ao fim.
17. Clique em Sons do jogo, no bloco do P3, para devolver o som às caixas.

**Passa quando.** Sai som pelo alto-falante do P3, o controle que está no rádio, e ela ouve com o controle encostado no ouvido. Para o resultado valer, o P1 — que está no cabo — tem de ter tocado antes: é ele que prova que o ouvido dela e o caminho de som do Hefesto estão funcionando. E o P4 tem de ficar mudo do começo ao fim.

**Por controle.**

* **P1** — No cabo, e é o controle de comparação. Faça nele os mesmos gestos PRIMEIRO e ouça: o som tem de sair. Sem isso, o que acontecer no P3 não mede nada. No fim, devolva o som às caixas clicando em Sons do jogo.
* **P2** — Ninguém toca. Não abra o card dele e não mexa em volume nenhum.
* **P3** — No rádio, e é ESTE que tem de receber o som. Todos os gestos de som são nele, e é nele que ela encosta o ouvido.
* **P4** — No rádio, e não pode tocar. No fim, encoste o ouvido nele e confirme o silêncio.

**A armadilha.** Três. Se o P1, que está no cabo, também não tocar, o teste não mediu nada — pode ser o volume do sistema, a saída de som errada ou o alto-falante calado, e não o rádio; conserte isso antes de olhar o P3. O botão Todo o som do PC tira o som das caixas e o joga no controle: se ela esquecer de clicar em Sons do jogo depois, a máquina fica muda e isso parece defeito sem ser. E um controle por vez: som nos dois ao mesmo tempo não deixa saber qual tocou. Por fim, silêncio no P3 é uma resposta válida e não é erro dela — o Hefesto ainda não montou o caminho de som pelo rádio, e é isso que a linha de ressalva do card diz. Anote 'não saiu som' e siga adiante, sem ficar tentando. E o tamanho, declarado: são DEZ atos, dois a mais que o alvo de oito. O instrumento deste teste é o ouvido dela encostado no plástico, e ele é ato numerado três vezes — no P1, no P3 e no P4 —, cada uma ANTES dos cliques que ela vai escutar. Encostar o ouvido não é conferência: escrito como 'confira, com o ouvido encostado', ele vira linha cinza sem número, e quem executa clica primeiro e ouve depois, quando o som já passou. É por isso que os três encostares têm número próprio, e é o que faz este teste caber numa mão.

---

## Linha 12 — Fecha o jogo, fecha a janela, e reabre as duas

**O que isto prova.** Prova que fechar e reabrir o jogo e a janela do Hefesto não derruba nenhum dos quatro controles nem troca o perfil.

**Onde olhar.** Na faixa de cima da janela do Hefesto, que é igual nas dez abas. À esquerda dela ficam as etiquetas dos controles, uma por controle, com P1 a P4, a cor do plástico e a palavra cabo ou rádio. À direita, na mesma faixa, fica Perfil ativo com o nome do perfil. No canto de cima à direita do cabeçalho fica a contagem, no formato '4 controles: 2 USB · 2 BT'. E nos aparelhos, as luzes de jogador — a fileirinha de luzinhas logo abaixo do touchpad — têm de continuar acesas no mesmo número.

**Os passos.**

1. Com o jogo aberto, abra a janela do Hefesto.
2. Leia o nome que está em Perfil ativo, na faixa de cima, e anote no papel.
3. Conte as etiquetas de controle da faixa de cima: têm de ser quatro, com P1 e P2 dizendo cabo e P3 e P4 dizendo rádio.
4. Olhe a fileira de luzes de jogador de cada controle e anote qual número está aceso em cada um.
5. Feche o jogo pelo jeito normal dele.
6. Feche a janela do Hefesto no X.
7. Conte até dez sem tocar em nada.
8. Abra o jogo de novo.
9. Abra a janela do Hefesto de novo, pelo mesmo ícone por onde você a abriu antes.
10. Leia a contagem no canto de cima à direita: tem de dizer 4 controles, 2 USB e 2 BT.
11. Leia as quatro etiquetas da faixa de cima e compare com o que você anotou.
12. Leia o Perfil ativo e compare com o nome anotado.
13. Olhe as luzes de jogador dos quatro e confira que cada um continua no mesmo número.
14. Mexa um analógico de cada controle, um de cada vez, e veja o jogo responder aos quatro.

**Passa quando.** Depois de reabrir, os quatro continuam lá: quatro etiquetas na faixa de cima, com os mesmos números e os mesmos transportes de antes, a contagem dizendo quatro controles, as luzes de jogador nos mesmos números, e cada um respondendo dentro do jogo. E o nome em Perfil ativo é exatamente o mesmo que ela anotou antes de fechar.

**Por controle.**

* **P1** — No cabo, e não se desplugue nada. Depois de reabrir tudo, ele tem de voltar como P1, no cabo, e responder no jogo.
* **P2** — No cabo, igual ao P1. Depois de reabrir tudo, tem de voltar como P2, no cabo, e responder no jogo.
* **P3** — No rádio, e não se desliga nada. Depois de reabrir tudo, ele tem de voltar como P3, no rádio, e responder no jogo.
* **P4** — No rádio, igual ao P3. Depois de reabrir tudo, tem de voltar como P4, no rádio, e responder no jogo.

**A armadilha.** O perfil pode trocar sozinho quando o jogo fecha, e nisso o Hefesto está fazendo o que deve. Por isso as duas leituras do Perfil ativo têm de ser feitas com o jogo ABERTO: leia antes de fechar o jogo, e leia de novo só depois de o jogo já estar reaberto. Ler com o jogo fechado dá outro nome e parece defeito sem ser. A outra: fechar a janela do Hefesto não desliga o Hefesto — ele continua rodando por trás, e os quatro controles têm de continuar de pé com a janela fechada. Se algum controle cair e voltar em sequência bem na hora em que a janela fecha ou abre, isso é o defeito, e vale anotar a hora exata.

---

## Linha 13 — Perfil vivo por controle, sem clicar em Salvar

**O que isto prova.** Prova que o que você muda num controle vale nele na hora, não encosta nos outros três, e continua lá depois de fechar e reabrir o Hefesto — sem você clicar uma única vez em Salvar Perfil.

**Onde olhar.** Nos aparelhos: a barra de luz do controle 1 (as duas tiras dos lados do touchpad), e o que a sua mão sente no L2, no R2 e no punho esquerdo dele. Na tela: a coluna do controle 1 nas abas Iluminação, Vibração e Gatilhos — cada controle tem a sua coluna, e o nome dele está no cabeçalho. No alto da tela, o nome em "Perfil ativo". E, no fim, a aba Perfis, na tabela de baixo, coluna "Ajuste próprio": ali cada controle tem uma linha, e acendem os nomes das peças que têm ajuste só dele (L2, R2, Motor de vibração esquerdo).

**Os passos.**

1. Abra a aba Iluminação.
2. Leia o nome que aparece no alto da tela, em "Perfil ativo", e anote-o num papel.
3. Clique, na linha "Cor" da coluna do controle 1, num quadradinho de cor bem diferente da que a barra tem agora.
4. Confira que a barra de luz do controle 1 mudou para a cor nova.
5. Confira que as barras de luz dos controles 2, 3 e 4 não mudaram.
6. Abra a aba Vibração.
7. Arraste até 0 a barra do "Motor esquerdo", na coluna do controle 1.
8. Confira que o número ao lado da barra mostra 0.
9. Clique em "Testar" na coluna do controle 1, com ele na mão.
10. Confira que só o punho direito treme.
11. Clique em "Testar" na coluna do controle 2, com ele na mão.
12. Confira que os dois punhos tremem.
13. Abra a aba Gatilhos.
14. Escolha "Rígido" na lista "Modo" do L2 e na do R2, na coluna do controle 1.
15. Confira, apertando o L2 e o R2 do controle 1, que os dois ganharam resistência.
16. Confira, apertando o L2 e o R2 dos controles 2, 3 e 4, que continuam soltos como antes.
17. Feche a janela do Hefesto pelo X.
18. Abra o Hefesto de novo.
19. Confira que o nome em "Perfil ativo" é o mesmo que você anotou.
20. Confira que a barra de luz do controle 1 continua na cor nova.
21. Confira, na aba Vibração, que a barra do "Motor esquerdo" do controle 1 continua em 0.
22. Clique em "Testar" na coluna do controle 1.
23. Confira que só o punho direito treme de novo.
24. Confira, na aba Gatilhos, que o L2 e o R2 do controle 1 continuam em "Rígido", e que o seu dedo ainda sente a resistência.
25. Abra a aba Perfis.
26. Confira, na tabela de baixo, coluna "Ajuste próprio", que a linha do controle 1 tem acesos o L2, o R2 e o Motor de vibração esquerdo.
27. Confira que as linhas dos controles 2, 3 e 4 estão apagadas nessas três peças.

**Passa quando.** As três mudanças do controle 1 aparecem no aparelho no mesmo instante do clique, sem você passar por Salvar Perfil; os controles 2, 3 e 4 continuam exatamente como estavam; e, depois de fechar e reabrir o Hefesto, as três continuam lá — a cor acesa na barra do controle 1, o punho esquerdo mudo no Testar dele e a resistência no L2 e no R2. Na tabela da aba Perfis, só a linha do controle 1 acende L2, R2 e Motor de vibração esquerdo.

**Por controle.**

* **P1** — É o único em que você mexe, e mexe em três coisas: cor nova na barra de luz, motor esquerdo em 0, e L2 e R2 em "Rígido". As três têm de valer no aparelho na hora do clique e continuar depois de fechar e reabrir.
* **P2** — Não toque nele. É a testemunha do cabo: barra de luz na cor de antes, os dois punhos tremendo no "Testar", L2 e R2 soltos. Se alguma coisa dele mudar sozinha, o teste reprovou.
* **P3** — Não toque nele. É a testemunha do rádio, e serve para provar que a mudança não vazou por cima do sem fio. A luz, o tremor e os gatilhos dele têm de estar como estavam.
* **P4** — Não toque nele. É a segunda testemunha do rádio. Se o 3 ficou intacto e o 4 mudou, o defeito não é do rádio — é de alguma coisa que escreveu no controle errado.

**A armadilha.** POR QUE ESTE TESTE É LONGO (onze atos, e não oito): ele é o mesmo teste feito DUAS vezes — três mudanças em três abas antes de fechar a janela, e as três conferidas de novo depois de reabrir. Cortar a segunda metade seria cortar exatamente o que ele prova, que é o perfil sobreviver ao fechar. NÃO TOQUE NO "SALVAR PERFIL", no rodapé, do começo ao fim deste teste: é ele que o teste existe para dispensar, e um clique nele apaga a prova. Feche só a JANELA do Hefesto, pelo X — não desligue o serviço pela aba Sistema: com o serviço parado a luz e o gatilho voltam ao que o aparelho faz sozinho, e o teste reprova sem haver defeito. Faça este teste com a Steam fechada por inteiro — com ela aberta a barra de luz pode apagar sozinha depois de cada comando, porque quem escreve por último ganha e a Steam escreve direto no aparelho. Não tente provar nada pelo "Brilho": ele não muda a luz do aparelho nem no cabo nem no rádio. E não confie só na tela dos gatilhos: ela mostra o que o Hefesto mandou, não o que o gatilho está fazendo — o controle não sabe responder isso, e a prova é o seu dedo. Uma coisa que NÃO é reprovação: a peça "Lightbar" pode ficar apagada na tabela da aba Perfis mesmo com a barra acesa na cor nova — clicar numa cor manda a cor ao controle, mas quem grava a cor no perfil é o "Salvar Perfil", que este teste proíbe de propósito.

---

## Linha 14 — Gatilhos: usa o "Todos" com três ligados, e liga o quarto depois

**O que isto prova.** Prova que o botão "Em todos" põe o efeito de gatilho de uma coluna nos três controles ligados de uma vez, e o guarda como o efeito de todo mundo — a ponto de um quarto controle, ligado só depois, já nascer com ele.

**Onde olhar.** Na aba Gatilhos, no pé de cada coluna de controle, o botão roxo "Em todos", ao lado de "Guardar esse efeito". A resposta nasce como uma tarja verde no alto daquela mesma coluna e some sozinha em uns 6 segundos. A prova de verdade é o dedo: aperte o L2 e o R2 de cada controle. E, no fim, a aba Perfis, tabela de baixo, coluna "Ajuste próprio" — ali apagado quer dizer "este controle usa o do perfil inteiro", que é o que este teste quer ver.

**Os passos.**

1. Abra a aba Gatilhos.
2. Desligue o controle 4 e deixe-o longe da mesa: ele entra só depois do clique.
3. Confira que há um nome escrito no alto da tela, em "Perfil ativo".
4. Confira que sobraram três colunas na tela, uma para cada controle ligado.
5. Aperte o L2 e o R2 dos controles 1, 2 e 3 e guarde na mão como eles estão hoje.
6. Escolha "Metralhadora" nas duas listas "Modo" da coluna do controle 1, a do L2 e a do R2.
7. Aperte o L2 e o R2 do controle 1 e sinta o efeito novo.
8. Clique no botão roxo "Em todos", no pé da coluna do controle 1.
9. Leia a tarja verde que nasce no alto dessa coluna.
10. Aperte o L2 e o R2 do controle 2 e os do controle 3, e sinta se o efeito novo chegou aos dois.
11. Ligue o controle 4.
12. Veja-o aparecer na tela como uma quarta coluna.
13. Aperte o L2 e o R2 do controle 4 e sinta se ele já nasceu com o efeito.
14. Abra a aba Perfis.
15. Confira, na tabela de baixo, coluna "Ajuste próprio", que o L2 e o R2 estão apagados nas quatro linhas de controle.

**Passa quando.** Um clique só põe o mesmo efeito no L2 e no R2 dos três controles ligados, e você sente isso no dedo nos três. A tarja verde confirma que o efeito passou a valer para todos. O controle 4, que estava desligado na hora do clique, já nasce com o efeito quando você o liga. E na tabela da aba Perfis o L2 e o R2 ficam apagados nas quatro linhas — apagado ali quer dizer "usa o do perfil inteiro", que é justamente o que o "Em todos" tinha de escrever.

**Por controle.**

* **P1** — É a coluna em que você escolhe o efeito e de onde você clica em "Em todos". Sinta o L2 e o R2 dele antes e depois: é o ponto de partida da comparação.
* **P2** — Não escolha nada nele. Ele recebe pelo "Em todos", e você prova isso apertando o L2 e o R2 dele depois do clique. Está no cabo — se ele receber e o do rádio não, o problema é do rádio.
* **P3** — Não escolha nada nele. Ele também recebe pelo "Em todos", e é o único do rádio nesta rodada. Aperte o L2 e o R2 dele depois do clique.
* **P4** — Fica desligado durante o clique — é a testemunha. Ligue-o só depois. Se ele nascer com o efeito, o Hefesto guardou o efeito como o de todo mundo, que é o ponto inteiro do teste; se nascer sem, o efeito ficou preso nos três de antes e o teste reprovou.

**A armadilha.** Este teste tem NOVE atos de propósito, e cortar qualquer um deles tira prova: ele mede o mesmo dedo antes e depois em quatro controles, e o quarto só entra na mesa depois do clique — é essa entrada tardia que prova que o efeito virou o de todo mundo, e não uma cópia mandada aos três que estavam lá. Se o botão roxo "Em todos" não estiver no pé da coluna, pare aqui: o botão está pronto, mas ainda não foi publicado na tela do produto, e publicar é decisão sua. Não é defeito, é fila. A tarja verde não diz um número: ela diz que o efeito passou a valer para todos e que um controle ligado depois já nasce com ele — se você esperar uma contagem, um teste bom vai parecer reprovado. Sem nome em "Perfil ativo", o botão recusa e explica: o efeito vai para os controles ligados, mas não há onde guardá-lo, e o controle 4 não vai herdar nada. E não decida pelo que a tela dos gatilhos mostra: ela mostra o que o Hefesto mandou, não o que o gatilho está fazendo — sem apertar o L2 e o R2 de cada controle, este teste dá verde sem prova.

---

## Linha 15 — Lançadores: cria um lançador para o jogo aberto e abre o jogo por ele

**O que isto prova.** Prova que, depois de o jogo ganhar o atalho do Hefesto, abrir esse jogo troca o perfil sozinho e os quatro controles continuam funcionando dentro dele.

**Onde olhar.** O nome do perfil que está valendo se lê no alto de qualquer aba, em "Perfil ativo" — é ali que a troca sozinha aparece. Na aba Jogar, dentro do quadro "Modo", a caixinha "Não trocar de perfil sozinho ao abrir um jogo". Na aba Lançadores, o cartão da Steam, o botão roxo "Detectar o jogo que está aberto" e o botão verde "Consertar". Na aba Perfis, a lista "Perfis Salvos" à esquerda e o quadro "Definições" à direita, com os campos "Nome:", "Prioridade:", "Funciona em:" e "Nome do Jogo:" com o botão "Detectar" ao lado. No aparelho, a barra de luz do controle 1. E dentro do jogo, os quatro respondendo.

**Os passos.**

1. Abra a aba Jogar.
2. Desmarque a caixinha "Não trocar de perfil sozinho ao abrir um jogo", dentro do quadro "Modo".
3. Abra pela Steam o jogo que você quer testar.
4. Volte ao Hefesto com Alt+Tab e clique na aba Lançadores.
5. Clique em "Detectar o jogo que está aberto".
6. Leia a frase que responde: ela diz o nome do jogo e se ele abre ou não pelo atalho do Hefesto.
7. Clique na aba Perfis e clique em "Novo".
8. Preencha o campo "Nome:" com o nome do jogo e o campo "Prioridade:" com 90.
9. Clique no botão "Detectar", ao lado de "Nome do Jogo:".
10. Leia a frase que responde e confira que o jogo reconhecido é o seu, e não o lançador que estava por cima.
11. Confira que o campo "Funciona em:" mudou sozinho para "Jogo da Steam" ou "Jogo".
12. Clique no nome desse perfil novo, na lista "Perfis Salvos", e clique em "Ativar".
13. Clique na aba Iluminação e clique no quadradinho verde da linha "Cor", na coluna do controle 1.
14. Confira que a barra de luz do controle 1 ficou verde.
15. Clique em "Salvar Perfil", no rodapé.
16. Feche o jogo e saia da Steam por inteiro.
17. Clique na aba Lançadores e clique no botão verde "Consertar" do cartão da Steam, se ele estiver lá.
18. Leia a frase que responde ao "Consertar".
19. Clique na aba Perfis, escolha outro perfil qualquer da lista e clique em "Ativar".
20. Confira que o alto da tela passou a mostrar esse outro nome em "Perfil ativo" e que a barra de luz do controle 1 deixou de ser verde.
21. Abra pela Steam o mesmo jogo outra vez.
22. Veja a barra de luz do controle 1 assim que o jogo abrir.
23. Volte ao Hefesto com Alt+Tab.
24. Leia o nome que está em "Perfil ativo".
25. Volte ao jogo com Alt+Tab e aperte um botão de cada controle, um por vez, do P1 ao P4.
26. Confira que o jogo responde aos quatro.

**Passa quando.** Ao abrir o jogo, sem você tocar em nada, o nome em "Perfil ativo" vira o do perfil que você criou para ele, e a barra de luz do controle 1 fica verde — os dois sinais da troca automática. E dentro do jogo os quatro controles respondem: os dois do cabo e os dois do rádio.

**Por controle.**

* **P1** — É o do cabo que carrega o sinal do perfil: a barra de luz dele fica verde quando o perfil do jogo entra, e é por ela que você vê a troca acontecer sem sair do jogo. Depois, aperte um botão dele dentro do jogo.
* **P2** — O outro do cabo. Não recebe cor nova. Só tem de responder dentro do jogo — ele prova que a troca de perfil não derrubou quem estava mudo.
* **P3** — O primeiro do rádio. Só tem de responder dentro do jogo. É o que costuma cair primeiro quando alguma coisa dá errado sem fio, então aperte um botão dele com atenção.
* **P4** — O segundo do rádio. Só tem de responder dentro do jogo. Se três responderem e ele não, o defeito é do rádio ou do quarto lugar na fila — não da troca de perfil.

**A espera.** O jogo leva minutos para chegar ao menu, nas duas vezes em que você o abre, e você não precisa ficar olhando. Deixe-o carregando e vá fazer outra coisa; volte quando ouvir o som do menu. A troca de perfil acontece sozinha e continua feita quando você voltar — nada se desfaz por você ter saído da frente. Ao voltar da segunda vez, o primeiro lugar a olhar é a barra de luz do controle 1; se ela já apagou o verde, confirme pelo nome em "Perfil ativo", com Alt+Tab para o Hefesto.

**A armadilha.** A caixinha "Não trocar de perfil sozinho ao abrir um jogo", na aba Jogar, desliga a troca automática inteira: marcada, o perfil nunca troca e o teste reprova sem haver defeito. Confira que ela está desmarcada antes de começar. Perfil com "Funciona em: Todos" nunca conta como o perfil daquele jogo — a troca só acontece com um perfil que nomeia o jogo, e foi assim que quatro perfis feitos por você nunca entraram em partida nenhuma. O botão "Criar perfil para um jogo", na aba Lançadores, não faz nada por enquanto: quem cria perfil é a aba Perfis, e ter dois caminhos para o mesmo lugar foi recusado de propósito. O "Consertar" precisa do jogo E da Steam fechados; com a Steam aberta o atalho não entra. E se, ao abrir o jogo, a barra de luz do controle 1 piscar verde e apagar, olhe a Steam antes de reprovar: com ela aberta, quem escreve por último na luz ganha — nesse caso confie no nome em "Perfil ativo", não na luz. Por fim, o tamanho: este é o teste mais longo dos 21, e é longo de propósito. Ele encadeia quatro coisas que só provam juntas — criar o atalho, criar o perfil que nomeia o jogo, marcar esse perfil com uma cor que se enxerga de dentro da partida, e só então fechar tudo e abrir de novo para ver a troca acontecer sem a sua mão. Tirar qualquer um dos quatro elos deixa o teste sem provar a troca automática, que é a única coisa que ele existe para provar.

---

## Linha 16 — Conexões: pareia um controle pela aba, quando a luz não acende

**O que isto prova.** Prova que mandar um controle que já está pareado voltar pelo rádio, pela própria aba Conexões, devolve ele ao mesmo lugar — sem abrir um segundo assento para o mesmo controle.

**Onde olhar.** Na aba Conexões do Hefesto, no primeiro quadro, chamado Gestão de Controles. Três coisas ali: o contador no alto do quadro (por exemplo "2 controles • 1 no cabo • 1 no rádio"), a linha de cada controle ("Sony • Player 1 • Cosmic Red • USB" — o fim da linha diz USB para cabo e BT para rádio) e, dentro da linha aberta de um controle, o botão "A luz não acende". Não existe botão "Parear" nesta aba: este botão é o gesto que refaz a conexão de um controle que já está pareado. Durante a espera aparece, no cartão dele, uma linha com "▲ Aperte PS no controle · procurando… 60s".

**Os passos.**

1. Abra o Hefesto e vá para a aba Conexões.
2. Anote o contador no alto do quadro Gestão de Controles: quantos controles, quantos no cabo, quantos no rádio.
3. Anote a linha de cada um dos quatro controles: o número de Player e se ela termina em USB ou em BT.
4. Confira que a linha do P4 termina em BT — este teste só vale com ele no rádio.
5. Clique na linha do P4 para abri-la.
6. Clique no botão "A luz não acende", dentro da linha aberta do P4.
7. Olhe o controle P4 na mesa e confirme que ele apagou e caiu do rádio.
8. Confira, na tela, que o botão passou a dizer "Cancelar" e que apareceu a linha "▲ Aperte PS no controle" com os segundos correndo para trás.
9. Aperte o botão PS do P4 uma vez.
10. Espere ele voltar — a contagem vai até 60 segundos.
11. Leia de novo o contador do quadro e as quatro linhas da lista.

**Passa quando.** O P4 volta na mesma linha e com o mesmo número de Player que tinha antes; o contador volta ao mesmo número de antes; e não aparece nenhuma linha nova para o mesmo controle. P1, P2 e P3 terminam com o número que tinham no começo.

**Por controle.**

* **P1** — Não se toca nele. Ele é testemunha: anote o número de Player e o fim da linha (USB ou BT) antes, e confira que estão iguais no fim.
* **P2** — Não se toca nele. Mesma testemunha: anote o número de Player e o fim da linha antes, e confira no fim.
* **P3** — Não se toca nele. Mesma testemunha: anote o número de Player e o fim da linha antes, e confira no fim.
* **P4** — É este. Ele precisa estar no rádio (linha terminando em BT). Abra a linha dele, clique em "A luz não acende", veja o controle apagar, aperte PS nele e espere voltar. De quebra, olhe a barra de luz dele depois da volta: fazer a barra voltar a obedecer é o motivo de este botão existir.

**A armadilha.** Falso vermelho: se o P4 estiver no cabo, o botão nasce cinza e a dica dele explica que só vale no rádio — ali o teste não roda, e isso não é defeito. Falso verde: se a tela responder "O controle não chegou a cair do rádio, então não houve o que reconectar. Ele continua pareado", nada foi reconectado e o teste não provou coisa nenhuma — refaça. E "Cancelar" não religa nada: se você clicar nele, o controle fica fora do rádio até você apertar PS por conta própria.

---

## Linha 17 — Reserva do posto: desliga o P2 por 20 segundos e religa

**O que isto prova.** Prova que o lugar de um controle fica guardado enquanto ele está desligado: o P2 sai por 20 segundos, volta como P2, e os outros três não trocam de número.

**Onde olhar.** Em dois lugares ao mesmo tempo. Na tela do Hefesto: a fita do topo, a linha que começa com "Selecionar:", onde cada controle é um chip ("P2 • Starlight Blue • BT"), e a lista Gestão de Controles, na aba Conexões, onde cada linha traz "Player 1", "Player 2" e assim por diante. No aparelho: a fileira de lampadinhas brancas embaixo do touchpad, que é o que diz o número — Player 1 acende só a do meio; Player 2 acende a segunda e a quarta; Player 3 acende as duas pontas e a do meio; Player 4 acende quatro, com a do meio apagada.

**Os passos.**

1. Abra o Hefesto na aba Conexões, com os quatro controles ligados.
2. Anote o número de Player dos quatro, na lista Gestão de Controles.
3. Olhe as lampadinhas embaixo do touchpad de cada controle e confira que a figura bate com o número que a tela mostra.
4. Confira que a linha do P2 termina em BT — este teste é com ele no rádio.
5. Segure o botão PS do P2 até as luzes dele apagarem.
6. Comece a contar os 20 segundos a partir do momento em que o chip do P2 sai da fita do topo, e não de quando você soltou o botão.
7. Anote o que a lista mostra no lugar do P2 enquanto ele está fora.
8. Olhe os outros três durante a ausência e anote se algum trocou de número.
9. Aos 20 segundos, aperte o botão PS do P2 uma vez para religá-lo.
10. Espere o chip dele reaparecer na fita do topo.
11. Leia os quatro números de novo, primeiro na tela e depois nas lampadinhas dos quatro aparelhos.

**Passa quando.** O P2 volta como Player 2 — na tela e nas lampadinhas embaixo do touchpad. P1, P3 e P4 terminam com o mesmo número com que começaram.

**Por controle.**

* **P1** — Não se toca nele. Anote o número dele antes; ele tem de terminar com o mesmo, e a figura das lampadinhas tem de continuar a mesma.
* **P2** — É este, e ele tem de estar no rádio. Segure PS até apagar, conte 20 segundos a partir de quando o chip dele some da fita, e aperte PS uma vez para religar. No fim ele tem de voltar Player 2, com a segunda e a quarta lampadinhas acesas.
* **P3** — Não se toca nele. Testemunha: anote o número antes, olhe durante a ausência do P2, e confira no fim.
* **P4** — Não se toca nele. Testemunha: anote o número antes, olhe durante a ausência do P2, e confira no fim — as quatro lampadinhas acesas com a do meio apagada.

**A armadilha.** O prazo desta reserva é de 30 segundos, e ele começa a correr quando o Hefesto percebe a queda, não quando você segura o PS. Se a volta passar dos 30 segundos o lugar já foi liberado e o resultado não diz nada sobre a reserva — refaça mais rápido. E olhe os outros três DURANTE a ausência, não só no fim: já foi medido, no cabo, um controle mudar de número enquanto o vizinho estava fora e voltar ao número certo depois. Se acontecer, anote — é exatamente isso que este teste procura.

---

## Linha 18 — Modo Nativo com dois controles no jogo

**O que isto prova.** Prova que, com o Hefesto fora do meio, um jogo de co-op de sofá enxerga os dois controles como DualSense de verdade — dois jogadores, e o movimento do controle respondendo.

**Onde olhar.** O resultado se lê na tela do JOGO, não na do Hefesto: quantos jogadores ele mostra, se ele pede "aperte um botão para entrar", e se girar o controle mexe alguma coisa. No Hefesto você confere só que o modo está de pé, na aba Jogar: a linha "Status" tem de estar em "Desligado"; o quadro "Modo" tem de mostrar "Modo Nativo · o DualSense da forma como veio ao mundo"; e a coluna "Atenção", à direita, tem de trazer a linha "Conexão Nativa com 2 controles ligados: neste modo o Hefesto não cria um controle para cada pessoa — quem conta os jogadores é o jogo, pelos controles que ele enxerga". A fonte não diz onde se lê o giroscópio dentro do Hefesto neste modo — a prova do movimento é no jogo, girando o controle na mão.

**Os passos.**

1. Desligue o P3 e o P4, segurando o botão PS de cada um até apagar — neste teste só o P1 e o P2 ficam na mesa.
2. Feche o jogo, se ele já estiver aberto.
3. Abra o Hefesto na aba Jogar.
4. Clique em "Desligado", na linha "Status".
5. Confira que o quadro "Modo" passou a mostrar "Modo Nativo".
6. Leia a coluna "Atenção" e confira que a linha da Conexão Nativa diz "2 controles ligados" — se disser outro número, algum controle ainda está ligado.
7. Abra o jogo de co-op de sofá agora, depois da troca de modo.
8. Aperte um botão no P1 e confirme que o jogo responde.
9. Aperte um botão no P2 e veja se o jogo mostra um segundo jogador ou pede para ele entrar.
10. Gire cada um dos dois controles na mão e veja se o jogo responde ao movimento.
11. Anote o nome do jogo e o que apareceu na tela dele.
12. Faça a contraprova: feche o jogo, volte à aba Jogar e clique em "Ligado".
13. Abra o MESMO jogo de novo, com os mesmos dois controles.
14. Repita o aperto de botão de cada um e o giro dos dois, e anote a diferença.

**Passa quando.** No Modo Nativo o jogo mostra os dois jogadores e responde ao movimento dos dois. A contraprova é o que fecha o teste: se com o Hefesto Ligado o mesmo jogo mostrar dois jogadores e no Modo Nativo mostrar um só, o problema é do modo; se mostrar um nos dois casos, o jogo é que não tem co-op de sofá e o teste não vale.

**Por controle.**

* **P1** — Fica ligado e entra no jogo. É o controle base: abra o jogo com ele e confirme que responde antes de mexer no segundo.
* **P2** — Fica ligado e entra depois. É ele que responde a pergunta do teste: com o jogo já aberto e o P1 respondendo, aperte um botão no P2 e veja se o jogo abre um segundo jogador.
* **P3** — Fica fora. Desligue-o antes de começar, segurando o PS até apagar, e confira no cabeçalho da janela que a conta diz 2 controles e não 3.
* **P4** — Fica fora. Desligue-o antes de começar, do mesmo jeito, e não o religue no meio do teste — religar muda a conta que o jogo faz no meio da medição.

**A armadilha.** Sem a contraprova este teste mente: um jogo que simplesmente não tem dois jogadores locais reprovaria o Modo Nativo sem culpa nenhuma. Segunda armadilha: a troca de modo só vale para o PRÓXIMO jogo que abrir — se o jogo já estava aberto quando você clicou, você vai medir o modo anterior; feche e abra de novo. Terceira: o Modo Nativo não é por controle, ele vale para a máquina inteira — por isso "ficar fora" aqui quer dizer desligado, e por isso a conta do cabeçalho precisa dizer 2 e não 3 ou 4.

> **Duas correções de endereço, 07/09/2026.** Esta linha dizia *"a linha da coluna Atenção"*, e estava errada em duas camadas. A coluna **Atenção** da aba Jogar nunca contou CONTROLES — ela contava AVISOS; quem conta controles é o cabeçalho da janela (*"2 controles: 1 USB · 1 BT"*), que está em todas as abas. E a coluna Atenção **saiu da aba Jogar** em 07/09, por ordem dela (*"em jogar remover essa seção do atenção, nenhum aviso esse — deixar só o reconectar controles"*). O gesto que este teste pede sempre foi o do cabeçalho. E não julgue este teste pelas lampadinhas de número: neste modo o Hefesto não escreve nada no aparelho, então o que estiver aceso ali foi o sistema que pôs.

---

## Linha 19 — Som: escolhe o alto-falante do P2 como saída de um tocador

**O que isto prova.** Prova que dá para mandar o som do computador para o alto-falante do controle 2, e que ele sai só nesse controle.

**Onde olhar.** No Hefesto: aba Controles, cartão do P2, bloco Alto-falante — o número do volume, o botão de nota musical e os dois cartõezinhos "Sons do jogo" e "Todo o som do PC". No aparelho: a grade de furinhos do alto-falante, na frente do controle, entre o touchpad e o botão PS. A segunda metade do teste é fora do Hefesto: a lista de saídas nas configurações de Som do sistema.

**Os passos.**

1. Confira na fita do topo do Hefesto que o P2 está por cabo — a linha dele termina em USB.
2. Abra a aba Controles.
3. Clique na linha do P2 para abrir o cartão dele.
4. Olhe o número do volume ao lado do bloco Alto-falante do P2 e confira que ele não está em zero.
5. Clique no cartãozinho "Todo o som do PC", dentro do bloco Alto-falante do P2.
6. Escute o P2 no instante do clique: o Hefesto toca um som curto de confirmação nele.
7. Abra o seu tocador de música ou de vídeo e ponha alguma coisa para tocar.
8. Encoste o ouvido na grade do alto-falante do P2 e confirme que a música sai dali.
9. Encoste o ouvido no P1, depois no P3, depois no P4, e confirme que nenhum dos três toca.
10. Confirme que a sua caixa de som ou o seu fone ficou em silêncio — o som inteiro do PC foi para o P2.
11. Abra as configurações de Som do sistema e olhe a lista de saídas: procure uma entrada de alto-falante para cada controle.
12. Volte ao Hefesto e clique em "Sons do jogo" no bloco Alto-falante do P2, para devolver o som do PC à saída de antes.
13. Confirme que a música voltou a sair na sua caixa de som ou no seu fone.

**Passa quando.** A música do seu tocador sai pelo alto-falante do P2 e por nenhum dos outros três, e o "Sons do jogo" devolve o som para onde ele estava. A segunda metade: a lista de saídas do sistema mostra um alto-falante para cada controle.

**Por controle.**

* **P1** — Cabo, ninguém toca nele. É o de comparação: encoste o ouvido na grade do alto-falante dele e não pode sair nada.
* **P2** — Cabo, é ESTE. Abra o cartão dele, confira o volume fora do zero e clique em "Todo o som do PC". É o único que pode tocar.
* **P3** — Rádio, ninguém toca nele. Encoste o ouvido: silêncio. Se clicar "Todo o som do PC" nele por engano, o Hefesto recusa e diz o motivo — pelo rádio a recusa é o certo, não um defeito.
* **P4** — Rádio, ninguém toca nele. Encoste o ouvido: silêncio. Ele e o P3 juntos mostram que o som foi para UM controle, e não para todos os que estão no mesmo tipo de conexão.

**A armadilha.** Três coisas dão falso vermelho. Primeira: o botão de nota musical ao lado do número é o MUDO do alto-falante, não a rota — se clicar nele o P2 fica calado e o teste parece reprovar, e esta tela não desfaz esse mudo. Segunda: com o número do volume do P2 em zero não sai som nenhum, por mais certa que a rota esteja. Terceira: a entrada "um alto-falante para cada controle" pode simplesmente não existir ainda na lista do sistema — ela é a metade nova, é ela que este teste está medindo; anote como reprova e siga, porque o som no P2 não depende dela.

---

## Linha 20 — Mudo no rádio: o botão do microfone do P3

**O que isto prova.** Prova que calar o microfone pela tela funciona num controle ligado por rádio, que a luz do botão acompanha, e que só aquele controle fica mudo.

**Onde olhar.** No Hefesto: aba Controles, cartão do P3 — o selo do microfone (a palavra ATIVO ou MUDO), a barrinha que mostra o som entrando agora, e o botão com desenho de microfone na ponta dessa barrinha. No aparelho: a luz vermelha do botãozinho de microfone do P3, logo abaixo do botão PS.

**Os passos.**

1. Confira na fita do topo que o P3 está por rádio — a linha dele termina em BT.
2. Abra a aba Controles.
3. Clique na linha do P3 para abrir o cartão dele.
4. Anote o que o selo do microfone do P3 diz agora: ATIVO ou MUDO.
5. Olhe a luz vermelha do botãozinho de microfone do P3 e anote se está acesa ou apagada.
6. Fale perto do P3 por uns segundos e olhe a barrinha do microfone no cartão dele: ela tem de se mexer.
7. Clique no botão de microfone que fica na ponta dessa barrinha, dentro do cartão do P3.
8. Leia o selo do microfone do P3: ele tem de dizer MUDO.
9. Olhe de novo a luz vermelha do botãozinho do P3: ela tem de apagar — nesta casa mudo e apagado são a mesma coisa.
10. Fale perto do P3 outra vez e olhe a barrinha: ela tem de cair bastante em relação ao que você viu antes do clique.
11. Olhe as linhas fechadas do P1, do P2 e do P4: o selo de microfone dos três tem de continuar como estava.

**Passa quando.** Depois do clique na tela, o cartão do P3 passa a dizer MUDO, a luz vermelha do botãozinho de microfone do P3 apaga, e os outros três continuam exatamente como estavam.

**Por controle.**

* **P1** — Cabo, testemunha. Só olhe o selo do microfone na linha fechada dele antes e depois: tem de continuar igual.
* **P2** — Cabo, testemunha. Mesma coisa — o selo do microfone dele não pode mudar.
* **P3** — Rádio, é ESTE. Abra o cartão, fale perto dele, clique no botão de microfone DA TELA, e depois olhe o selo e a luz vermelha do botãozinho do aparelho.
* **P4** — Rádio, testemunha, e é a que mais importa: ele está no mesmo tipo de conexão do P3. Se o selo do P4 também virar MUDO, o comando pegou o rádio inteiro em vez do controle escolhido.

**A armadilha.** O falso verde é apertar o botãozinho de microfone no próprio controle em vez de clicar na tela: aí quem cala é o Linux, não o Hefesto, e o teste passa sem provar nada — esse gesto já é a linha 9 do roteiro. Dois avisos mais: pelo rádio o mudo já foi medido como PARCIAL, então a barrinha pode não zerar, e só isso não reprova; e esta tela NÃO devolve o microfone — a partir do clique quem manda no mudo é o Hefesto, e a volta é reiniciar o Hefesto. Faça este teste depois dos outros que precisam do microfone do P3.

---

## Linha 21 — Luz no rádio: uma cor no P4

**O que isto prova.** Prova que dar uma cor à barra de luz funciona num controle ligado por rádio, e que a cor não volta atrás sozinha.

**Onde olhar.** No Hefesto: aba Iluminação, coluna do P4 — o cabeçalho da coluna traz P4 e termina em BT; nela ficam a fileira de quadradinhos de cor, o código da cor embaixo deles e os botões Automático e Desligar. No aparelho: a barra de luz do P4, as duas tiras acesas dos dois lados do touchpad.

**Os passos.**

1. Confira na fita do topo que o P4 está por rádio — a linha dele termina em BT.
2. Abra a aba Iluminação.
3. Olhe a barra de luz do P4 no aparelho e anote a cor que ela tem agora.
4. Escolha um quadradinho de cor bem diferente dessa: o verde é o terceiro dos oito; se ele já estiver verde, use o amarelo, que é o quinto.
5. Clique nesse quadradinho na coluna do P4.
6. Olhe a barra de luz do P4 no aparelho: ela tem de virar a cor escolhida na hora.
7. Olhe as barras de luz do P1, do P2 e do P3: nenhuma pode ter mudado.
8. Clique na janela de outro programa e volte para o Hefesto — assim o Hefesto ganha a chance de trocar o perfil sozinho, que é quando a cor costuma voltar atrás.
9. Espere 15 segundos sem clicar em nada.
10. Olhe a barra do P4 outra vez: ela tem de continuar na cor escolhida.
11. Clique em Automático na coluna do P4 para largar a barra dele de novo — a tela diz que esse botão entrega a barra daquele controle para o jogo escolher.

**Passa quando.** A barra de luz do P4 vira a cor escolhida no ato, mesmo ele estando por rádio, e continua nessa cor 15 segundos depois de você ter mexido em outra janela. As barras dos outros três não mudam.

**Por controle.**

* **P1** — Cabo, não pode mudar de cor. Olhe a barra dele antes e depois.
* **P2** — Cabo, não pode mudar de cor. Olhe a barra dele antes e depois.
* **P3** — Rádio, não pode mudar de cor — é a testemunha do mesmo tipo de conexão do P4. Se a cor nova acender nele também, o comando foi para o rádio inteiro.
* **P4** — Rádio, é ESTE. Recebe a cor nova pelo quadradinho da coluna dele, e tem de ficar com ela até você clicar em Automático.

**A armadilha.** O falso verde é escolher uma cor parecida com a que já estava: sem escolha à mão cada barra fica na cor do número do controle, e a do número 4 é rosa — clicando no rosa a barra não muda e não dá para saber se o clique chegou ao aparelho. Escolha uma cor que você reconhece de longe. O falso vermelho é usar a chave "Cores automáticas por controle" em vez do quadradinho da coluna: aquela chave é do perfil inteiro, e desligá-la grava na hora a cor de todos os controles. E não confunda Automático com Desligar, que apaga a barra.
