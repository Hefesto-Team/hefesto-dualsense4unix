# As quarenta e uma decisões dela — o laudo do dia

**05/09/2026.** Ela abriu a fila e respondeu **41 decisões**. Onze frentes as
leram aba por aba, mediram cada uma contra o código antes de escrever qualquer
coisa, e a medição virou o enunciado do trabalho do avesso.

---

## A DESCOBERTA: seis não eram decisão de tela — eram DEFEITO

A fila foi montada como se as 41 fossem escolhas de desenho: *onde fica o
aviso*, *que frase dizer*, *qual cor*. **Seis não eram.** Ela não escolheu entre
as opções que eu ofereci: ela disse que o produto está errado.

| decisão | a palavra dela | o que a sprint faz |
| --- | --- | --- |
| **02-Q8** | *"Esse erro não deveria acontecer. Deveria ser só pro controle em questao."* <!-- noqa-acento: citação literal dela --> | não redige o aviso: fecha a rota global que escreve no microfone do vizinho |
| **04-Q4** | *"O Hefesto não pode ter essa falha. Isso tem que aplicar, não justificar a falha"* | não escolhe a frase: o brilho passa a APLICAR nos quatro estados |
| **05-Q6** | *"Parece erro. Não deveria ocorrer ajuste de gambiarra sobre falha de produto nosso"* | não põe o recado num canal melhor: conserta o clique que a interface não entendia |
| **07-Q1** | *"Deve aplicar automaticamente como era no gtk"* | não oferece o reparo manual: aplica, e a linha a copiar some |
| **09-Q3** | *"mas o botão tem de realmente fazer o que promete"* | não escreve "Atualizando…" sobre nada: o botão lê a resposta e recusa quando não fez |
| **10-Q2** | *"Isso é erro do produto."* | não avisa que a regra não cabe: cria a sexta forma de regra e a tela para de mandar ao terminal |

**A regra que as seis deixam escrita, e ela passa a valer para toda frase de
limitação deste produto:**

> ## O Hefesto não explica a própria falha — ele a conserta.

### E uma sétima: a `01-Q1` virou MEDIÇÃO antes de virar desenho

Ela não escolheu opção nenhuma. Escreveu:

> *"Não me lembro disso acontecer. E não deveria. Mas caso ocorra na coluna
> atenção"*

Três frases, três ordens — e a medição diz que ela tem razão nas três. **"Não
me lembro disso acontecer"** porque o produto **conserta** a causa: o mixer UAC
do DualSense martelando o EP0 tem cura de raiz num `quirk_flags` do
`snd_usb_audio` (`src/hefesto_dualsense4unix/integrations/storm_doctor.py:241`),
e o instalador a instala. **"E não deveria"** — a frase que a pergunta oferecia
é a que ela **baniu** em 31/08, e ela continua viva no último lugar em que mora,
PRESA por um teste desta casa que exige a presença dela. **"Mas caso ocorra na
coluna atenção"** — o produto já MEDE se a cura caiu e já escreve a frase certa,
e essa linha chega à aba Sistema, **nunca à coluna Atenção da aba em que ela
joga**.

**A pergunta estava errada.** Ela não pedia uma frase: pedia que alguém medisse
antes de perguntar. É a terceira vez em três dias que a causa está escrita uma
linha acima do defeito.

---

## O PLACAR

| | |
| --- | ---: |
| decisões respondidas | **41** |
| que já estavam no produto, sem uma linha nova | **17** |
| sprints escritas | **24** — 15 de DEFEITO, 9 de DESENHO |
| documento de princípio | **1** |

A fila de execução, com a ordem, o que corre em paralelo e as seis colisões de
arquivo que ninguém resolveu, está em
[ONDA CINCO · o índice](sprints/2026-09-05-ONDA-CINCO-INDICE.md). Por que a fila
repetiu — **as 41 já tinham decisão registrada, no mesmo arquivo, no mesmo
dia** — está em
[POR QUE A FILA REPETE](2026-09-05-POR-QUE-A-FILA-REPETE-a-queixa-dela-medida.md).

---

## AS QUARENTA E UMA, UMA LINHA CADA

`DESENHO` é frase, lugar, cor ou peça de tela. `DEFEITO` é causa medida e
consertada. **FEITA** quer dizer: já estava no produto quando ela respondeu, e
a sprint diz isso em vez de inventar trabalho.

### Aba 01 · Jogar

| id | o que ela decidiu | marca | a sprint |
| --- | --- | --- | --- |
| **01-Q1** | *"Não me lembro disso acontecer. E não deveria. Mas caso ocorra na coluna atenção"* | **DEFEITO** (e medição antes de desenho) | [ONDA5-01-01](sprints/2026-09-05-ONDA5-01-01-a-cura-existe-e-a-coluna-atencao-nao-a-conhece.md) — a cura existe e a coluna Atenção não a conhece · [ONDA5-01-02](sprints/2026-09-05-ONDA5-01-02-a-profecia-que-um-teste-prendeu-na-janela-antiga.md) — a profecia que um teste prendeu |
| **01-Q3** | *"Na aba Jogar, sob Modo"* — o interruptor do cadeado | **DESENHO** | [ONDA5-01-03](sprints/2026-09-05-ONDA5-01-03-o-cadeado-ja-esta-na-tela-e-o-que-falta-e-o-verde.md) — a caixa já está no lugar exato que ela escolheu; falta o verde |

### Aba 02 · Controles

| id | o que ela decidiu | marca | a sprint |
| --- | --- | --- | --- |
| **02-Q6** | *"Fica fora, com aviso"* — devolver o volume do alto-falante | **DESENHO** | [ONDA5-02-02](sprints/2026-09-05-ONDA5-02-02-a-borda-do-som-em-duas-cores-e-as-duas-dicas-que-mandam-para-uma-janela-sem-lancador.md) — e o aviso apontava para uma janela sem lançador desde 01/09 |
| **02-Q7** | a marca do que a máscara degrada fica na palavra, com o motivo no hover | **DESENHO** | **FEITA** — `src/hefesto_dualsense4unix/interface/aba02.py:827-829` e `src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py:2147` · **CADUCOU em 13/09/2026**: a marca saiu da tela pela `A-MARCA-DA-DEGRADACAO-01`, porque a terceira lista dela tira as frases de aviso das abas |
| **02-Q8** | *"Esse erro não deveria acontecer. Deveria ser só pro controle em questao."* <!-- noqa-acento: citação literal dela --> | **DEFEITO** | [ONDA5-02-01](sprints/2026-09-05-ONDA5-02-01-o-microfone-do-vizinho-e-a-porta-que-ficou-aberta.md) — e a regra que ela pede já estava escrita um arquivo ao lado |
| **02-Q9** | *"Com cor diferente"* — borda VERDE se ligado, ÂMBAR se mudo | **DESENHO** | [ONDA5-02-02](sprints/2026-09-05-ONDA5-02-02-a-borda-do-som-em-duas-cores-e-as-duas-dicas-que-mandam-para-uma-janela-sem-lancador.md) |
| **02-Q10** | *"Continua com colchetes"* — o clique do analógico | **DESENHO** | **FEITA** — o que sobra é um comentário que ainda pede a palavra dela, e ele é o Passo 5 da ONDA5-02-01 |

### Aba 03 · Gatilhos

| id | o que ela decidiu | marca | a sprint |
| --- | --- | --- | --- |
| **03-Q1** | *"Aparece ao parar o mouse"* — a explicação do modo | **DESENHO** | **FEITA** — só a autoria muda de mão ([ONDA5-03-02](sprints/2026-09-05-ONDA5-03-02-o-recibo-que-repete-o-clique-e-as-tres-que-ja-existem.md) §1) |
| **03-Q2** | *"Aplica na hora, com aviso"* — a curva pronta troca o modo | **DESENHO** | **FEITA** — idem |
| **03-Q3** | *"Nada novo"* — botão para mandar o efeito de novo | **DESENHO** | **nada a construir**, e a pergunta chegou **dezenove horas depois** de o botão nascer. Uma pergunta fica para ela |
| **03-Q4** | *"o campo pisca em verde"*, sem palavra nova na tela | **DESENHO** | [ONDA5-03-01](sprints/2026-09-05-ONDA5-03-01-o-campo-que-pisca-e-o-numero-do-voo-que-ja-o-endereca.md) (o piloto, para as dez abas) · [ONDA5-03-02](sprints/2026-09-05-ONDA5-03-02-o-recibo-que-repete-o-clique-e-as-tres-que-ja-existem.md) (a aba) |

### Aba 04 · Iluminação

| id | o que ela decidiu | marca | a sprint |
| --- | --- | --- | --- |
| **04-Q3** | *"O código da cor clica"* | **DESENHO** | **FEITA** em 04/09, medida em sete camadas ([ONDA5-04-01](sprints/2026-09-05-ONDA5-04-01-o-brilho-aplica-em-vez-de-justificar-a-falha.md) §0) |
| **04-Q4** | *"O Hefesto não pode ter essa falha. Isso tem que aplicar, não justificar a falha"* | **DEFEITO** | [ONDA5-04-01](sprints/2026-09-05-ONDA5-04-01-o-brilho-aplica-em-vez-de-justificar-a-falha.md) — o gesto deduzia a falha lendo a ressalva da TELA e devolvia uma frase |

### Aba 05 · Vibração

| id | o que ela decidiu | marca | a sprint |
| --- | --- | --- | --- |
| **05-Q1** | *"As três abas de uma vez"* — publicar | **DESENHO** | **FEITA, e são as DEZ** — as dez páginas publicadas são byte a byte idênticas ao mockup, medido em 05/09 |
| **05-Q2** | *"As duas na dica"* | **DESENHO** | [ONDA5-05-01](sprints/2026-09-05-ONDA5-05-01-a-nota-do-testar-volta-para-a-dica.md) — a nota do Testar sai da tela e volta para o `?` |
| **05-Q4** | *"Linha embaixo da grade"* | **DESENHO** | [ONDA5-05-03](sprints/2026-09-05-ONDA5-05-03-a-confirmacao-sai-do-cartao-e-vai-para-a-faixa.md) — a confirmação sai do cartão, que ela cobre por 6 s |
| **05-Q5** | *"Fica como está"* | **DESENHO** | **FEITA** — e chegou lá pela palavra dela no mesmo dia |
| **05-Q6** | *"Parece erro. Não deveria ocorrer ajuste de gambiarra sobre falha de produto nosso"* | **DEFEITO** | [ONDA5-05-02](sprints/2026-09-05-ONDA5-05-02-o-clique-que-a-interface-nao-entendia.md) — a tela acusava o clique dela quando o clique estava certo |

### Aba 06 · Navegação

| id | o que ela decidiu | marca | a sprint |
| --- | --- | --- | --- |
| **06-Q1** | *"Sem clicar mas ativo"* — *"o switch fica apagado (não clicável) MAS mostra o estado real"* | **DESENHO** | [ONDA5-06-02](sprints/2026-09-05-ONDA5-06-02-o-interruptor-apagado-diz-o-lado-e-o-ps-ganha-a-vigesima-segunda-linha.md) — hoje a especificidade do portão apaga o lado do interruptor |
| **06-Q2** | *"Aviso fixo ao lado"* — as três regiões do touchpad | **DESENHO** | **FEITA** pela ONDA2-06, em 04/09 |
| **06-Q3** | *"Aparece e você escolhe"* — o botão PS na tabela | **DEFEITO** + **DESENHO** | [ONDA5-06-01](sprints/2026-09-05-ONDA5-06-01-o-ps-ganha-dono-no-motor-antes-de-ganhar-linha.md) (o motor: o PS é o único botão que a emulação **nunca viu**) · [ONDA5-06-02](sprints/2026-09-05-ONDA5-06-02-o-interruptor-apagado-diz-o-lado-e-o-ps-ganha-a-vigesima-segunda-linha.md) (a 22ª linha) |
| **06-Q4** | *"Tira de aviso sob a tabela"* | **DESENHO** | **FEITA** pela ONDA2-06 |
| **06-Q5** | *"Enquanto estiver desligado"* — o custo de desligar o teclado | **DESENHO** | **FEITA** pela ONDA2-06 |

### Aba 07 · Lançadores

| id | o que ela decidiu | marca | a sprint |
| --- | --- | --- | --- |
| **07-Q1** | *"Deve aplicar automaticamente como era no gtk"* | **DEFEITO** | [ONDA5-07-01](sprints/2026-09-05-ONDA5-07-01-a-linha-intocavel-e-aplicada-em-vez-de-explicada.md) (a linha intocável) · [ONDA5-07-02](sprints/2026-09-05-ONDA5-07-02-o-rodape-perdeu-a-carona-que-a-janela-velha-pega.md) (a carona que o rodapé perdeu) |
| **07-Q2** | *"O produto aplica ela"* — a frase manda a um botão que não existe | **DEFEITO** | [ONDA5-07-03](sprints/2026-09-05-ONDA5-07-03-o-aviso-do-jogo-aberto-nao-manda-copiar-e-cala-nas-duas-telas.md) |
| **07-Q3** | *"As duas recusas calam tudo"* | **DEFEITO** | [ONDA5-07-03](sprints/2026-09-05-ONDA5-07-03-o-aviso-do-jogo-aberto-nao-manda-copiar-e-cala-nas-duas-telas.md) — uma cura na função dona, que cobre os quatro chamadores |
| **07-Q4** | o corpo nomeia o conjunto ("da sua biblioteca, instalados ou não") | **DESENHO** | **FEITA** em 04/09 — `src/hefesto_dualsense4unix/interface/desenho_dos_lancadores.py:886-888` |

### Aba 08 · Conexões

| id | o que ela decidiu | marca | a sprint |
| --- | --- | --- | --- |
| **08-Q2** | publicar as seis correções | **DESENHO** | **FEITA** — mockup e página publicada da 08 são byte a byte idênticos, e o `mockup/DIVERGENCIAS.md` não tem seção da 08 |
| **08-Q4** | o selo de procedência só quando **não** foi medido aqui | **DESENHO** | **FEITA** — `src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py:1085-1086` devolve vazio para o medido aqui |
| **08-Q5** | *"A recomendação calada continua no lugar dela, em cinza, e o mesmo botão desfaz"* | **DEFEITO** | [ONDA5-08-01](sprints/2026-09-05-ONDA5-08-01-a-ordem-calada-fica-na-tela-e-as-duas-listas-que-escondem.md) — o `⊘` era porta de mão única |
| **08-Q7** | *"Um mais-N no fim"* nas listas que escondem | **DEFEITO** | [ONDA5-08-01](sprints/2026-09-05-ONDA5-08-01-a-ordem-calada-fica-na-tela-e-as-duas-listas-que-escondem.md) — hoje a tela esconde DOIS achados na mesa dela |
| **08-Q8** | *"Trocar pela verdade"* — o rodapé do mapa | **DEFEITO** | [ONDA5-08-02](sprints/2026-09-05-ONDA5-08-02-o-rodape-do-mapa-tem-dois-donos.md) — a decisão já está na tela; a frase é que tem dois donos |

### Aba 09 · Sistema

| id | o que ela decidiu | marca | a sprint |
| --- | --- | --- | --- |
| **09-Q1** | *"Segue fazendo os dois. Com mesmo nome"* | **DESENHO** | [ONDA5-09-01](sprints/2026-09-05-ONDA5-09-01-o-botao-volta-a-se-chamar-atualizar.md) — **é uma reversão**, e a decisão que ela reverte foi minha, não dela |
| **09-Q2** | *"Cinza mas ainda responde"* | **DESENHO** | **FEITA** — a trava que a pergunta declarava caiu em 04/09 |
| **09-Q3** | *"Atualizando e funciona em termo de feature"* — e, no esclarecimento, *"mas o botão tem de realmente fazer o que promete"* | **DESENHO** (a tela) + **DEFEITO** (o mecanismo) | [ONDA5-09-01](sprints/2026-09-05-ONDA5-09-01-o-botao-volta-a-se-chamar-atualizar.md) · [ONDA5-09-02](sprints/2026-09-05-ONDA5-09-02-o-atualizar-nao-diz-pronto-sem-ter-feito.md) — com o serviço desligado o botão dizia "Pronto." sem um byte ter saído |

### Aba 10 · Perfis

| id | o que ela decidiu | marca | a sprint |
| --- | --- | --- | --- |
| **10-Q1** | *"Cadeado e frase no rato"* | **DESENHO** | **FEITA** e publicada |
| **10-Q2** | *"Isso é erro do produto."* | **DEFEITO** | [ONDA5-10-01](sprints/2026-09-05-ONDA5-10-01-o-hefesto-nao-manda-ninguem-para-o-terminal.md) — três frases mandavam ela para a linha de comando, e uma delas quebrava a promessa do próprio botão |
| **10-Q3** | *"A sua frase no desenho"* — a prioridade | **DESENHO** | **FEITA**, e amarrada por régua |
| **10-Q4** | *"Rótulo ao lado, ao vivo"* | **DESENHO** | [ONDA5-10-02](sprints/2026-09-05-ONDA5-10-02-o-nome-do-jogo-ao-lado-do-campo-e-a-tira-que-diz-a-metade-curta.md) — a metade "ao vivo" não fecha dentro da aba, e a sprint diz isso |
| **10-Q5** | *"Encurtar as frases longas"* | **DESENHO** | [ONDA5-10-02](sprints/2026-09-05-ONDA5-10-02-o-nome-do-jogo-ao-lado-do-campo-e-a-tira-que-diz-a-metade-curta.md) — e a tira ganhou uma segunda linha ontem |
| **10-Q6** | *"É pra tudo funcionar independente do modo, mascarou forma de conexão."* | **DEFEITO** — e é o **PRINCÍPIO** | [A MÁSCARA NÃO CUSTA FEATURE](2026-09-05-A-MASCARA-NAO-CUSTA-FEATURE-o-principio-e-o-que-ele-cobra.md) · [ONDA5-10-03](sprints/2026-09-05-ONDA5-10-03-as-duas-frases-do-modo-somem-e-o-mecanismo-fica.md) · [ONDA5-MIC-VIRTUAL-01](sprints/2026-09-05-ONDA5-MIC-VIRTUAL-01-o-microfone-do-dualsense-sob-a-mascara-xbox.md) |

---

## A DECISÃO MAIS LARGA DO DIA, E ELA NÃO É DE ABA NENHUMA

A `10-Q6` nasceu de uma pergunta pequena — *dá para tirar da tela o aviso de que
o rádio pode não aguentar a Conexão Nativa?* — e ela **recusou a categoria
inteira**:

> *"Pode medir, mas a ideia é que o de falhas e limitações. Criamos mecanismos <!-- noqa-acento: citação literal dela -->
> pra usarmos todas as feature. Exemplo controle do Xbox não tem microfone mas <!-- noqa-acento: citação literal dela -->
> se o Mic do dualsense passa a ser lido a parte via Mic virtual."* <!-- noqa-acento: citação literal dela -->

**A medição deu razão a ela em três features e a corrigiu em cinco.** O
inventário está no documento do princípio, e o achado que decide trabalho cabe
numa linha de código: a fábrica do gamepad virtual recebe **cinco** canais de
volta do jogo para o aparelho, o daemon monta os quatro de réplica — e em
`src/hefesto_dualsense4unix/integrations/virtual_pad.py:231` só o rumble passa.
**Cinco entram, um sai.** Os gatilhos adaptativos, a barra de luz e os LEDs de
jogador que o jogo pede morrem ali, caladamente.

**E o defeito de tela que ninguém tinha contado:** o produto perde cinco e a
tela conta dois. Os três que sobram seguem para um carimbo de atividade que só
existe no outro tipo de gamepad virtual — então a tela dela diz *"sem pedido
ainda"* sobre três recursos que o jogo **não pode pedir** naquela máscara.

**O precedente é mais velho que o princípio.** Por Bluetooth o DualSense não
publica fonte de áudio nenhuma; o Hefesto não escreveu na tela que o microfone
se perde — leu o áudio tunelado no próprio canal do controle e publicou uma
fonte. Em 25/07/2026, antes de o princípio ter nome.

---

## O QUE ESTE LAUDO NÃO DECIDE

**Ela respondeu 41 e, ao terminar, escreveu que já as tinha respondido antes.**
Ela está certa: as 41 tinham decisão registrada, e a contagem — quantas
divergem do que já existia, quantas mandam arrancar código entregue, e onde
está o desatualizado que faz a fila repetir — é o assunto de
[POR QUE A FILA REPETE](2026-09-05-POR-QUE-A-FILA-REPETE-a-queixa-dela-medida.md),
não deste documento.

**O que sobra para ela nesta onda são três coisas**, e as três estão na §5.1 do
[índice](sprints/2026-09-05-ONDA-CINCO-INDICE.md): a palavra do selo novo da
coluna Atenção, se o botão de reenvio da aba 03 fica ou sai, e a tinta do pino
do interruptor apagado. **Texto de tela e pixel são dela; o resto se mede.**
