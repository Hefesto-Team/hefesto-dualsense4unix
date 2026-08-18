# A noite dos quatro controles — o que a validação em hardware provou e o que ela abriu

> **Por que este documento existe.** Em 25/07/2026 o projeto chegou, pela
> primeira vez, a quatro controles numerados e funcionando num jogo real. O que
> se aprendeu naquelas duas horas não está em teste nenhum, e parte disso
> contradiz o que o próprio repositório afirmava. Sem registro, se perde.

## O que foi provado

Quatro controles simultâneos, em um jogo de co-op real:

| jogador | controle | via |
|---|---|---|
| 1 | DualSense | cabo |
| 2 | DualSense | rádio |
| 3 | Nintendo Pro | rádio |
| 4 | 8BitDo Pro (modo Switch) | cabo |

**Os quatro funcionaram.** A numeração saiu 1-2-3-4, sem pular e sem repetir, e
sobreviveu a um reinício do daemon — a ordem de preferência entregue horas antes
pela sprint NUM-01 fez o que prometia.

Também confirmado ao vivo: o modo jogo passou a ligar sozinho, em três jogos
diferentes que **não têm perfil próprio** — exatamente o buraco que a MODO-01
fechou.

## O que se aprendeu, e não estava previsto

### A identidade do 8BitDo muda com o MODO, não com a via

Dois endereços de hardware para o mesmo plástico, ambos reais, do mesmo
fabricante, divergindo nos dois últimos octetos: um em modo Switch, outro em modo
DirectInput/PS4.

Os outros três controles não têm esse comportamento — o DualSense usa o endereço
de rádio como identidade **mesmo no cabo**, o que foi verificado com o mesmo
aparelho visto por rádio às 15:39 e por cabo às 21:00, com o mesmo endereço.

Consequência: trocar o modo do 8BitDo o faz aparecer como aparelho novo, que pega
o próximo número livre. Com quatro na mesa, vira jogador 5 — e o DualSense tem
cinco luzes de jogador, então empurrar alguém para lá é defeito visível. Sprint
**IDENT-01** trata disso, e recusa explicitamente a fusão automática por prefixo
de endereço (o motivo está lá: endereços dentro de um fabricante são sequenciais,
e dois aparelhos irmãos colidiriam).

### O 8BitDo em modo PS4 não sobe pelo cabo, e o kernel diz por quê

```
playstation 054C:05C4: Invalid byte count transferred, expected 16 got 9
    retrying feature reportID 18 in 100 ms (2 attempt(s) left)
    ... três tentativas, sempre 9 bytes
Failed to retrieve DualShock4 pairing info: -22
probe with driver playstation failed with error -22
```

A assimetria que explica tudo: **por Bluetooth o driver nem lê esse relatório** —
o endereço vem do pareamento. **Pelo cabo, é a única fonte.** Por isso o mesmo
controle sobe por rádio e morre no fio.

Detalhe que fecha o diagnóstico: dos 16 bytes o driver usa **7**; o resto é o
endereço do host do último pareamento, que ele nunca lê. Nove bytes **podem**
conter tudo o que importa — é a base do patch escrito nesta noite.

### A ordem de registro do kernel COINCIDE com a nossa

Registrado aqui porque **foi objeto de um erro de análise durante a sessão**, e o
erro quase virou desenho.

Ao listar os dispositivos HID ordenados por nome, `0003:*` (USB) aparece antes de
`0005:*` (Bluetooth), o que sugere que o kernel agrupa por barramento antes da
ordem de chegada. **Isso é artefato da ordenação alfabética.** A ordem real é o
contador hexadecimal no fim do nome do dispositivo:

```
#7   DualSense branco   → nosso jogador 1
#14  DualSense roxo     → nosso jogador 2
#17  Nintendo Pro       → nosso jogador 3
#21  8BitDo             → nosso jogador 4
```

Idêntica à ordem de preferência do Hefesto. **Não há conflito entre a numeração
do kernel e a nossa** — e a hipótese "o jogo segue a ordem de registro" portanto
**não explica** a dessincronia observada.

*Regra de método:* ao inspecionar `/sys/bus/hid/devices/`, ordenar pelo contador,
nunca pelo nome. O nome começa pelo barramento e mente sobre a cronologia.

### A dessincronia: o Hefesto repinta o próprio número por cima do jogo

Aqui houve **um segundo erro de análise durante a sessão**, e ele também merece
registro, porque é uma armadilha que qualquer um repete.

A tentação é ler `/sys/class/leds` do gamepad virtual e concluir "este é o número
que o jogo escreveu". **Não é.** O jogo escreve o padrão de luzes como *output
report* HID, que o nosso código intercepta em espaço de usuário — nunca chega à
classe de LED do kernel. O que o sysfs mostra é o número que o **kernel** deu ao
vpad no probe, por um contador que aloca o menor identificador livre **contando
físicos e virtuais juntos**.

Pior: a tabela de padrões do kernel e a nossa são **idênticas** em 1..4. Logo
`·` é ambíguo por construção — pode ser nosso 4, do kernel, ou do jogo. **O
padrão aceso não identifica quem o escreveu.** A única testemunha do número do
jogo é o journal.

*Regra de método:* nunca atribuir autoria a um padrão de LED lido do sysfs. Para
saber quem escreveu, é o log.

O mecanismo real, encontrado no código:

```
21:18:39  game_output_retido_sem_jogo  campos=['player_leds']  uniq=<primário>
21:18:39  uhid_replica_ativa           categoria=player_leds   player=2
```

Quando o sinal de jogo classifica a autoridade como `daemon`, a camada do jogo é
**descartada do merge** e o topo passa a ser a camada do co-op — o **nosso**
número. E não é omissão passiva: a retenção dispara uma repintura ativa, que
reescreve o nosso número por cima do que o jogo acabou de pedir.

Três defeitos concretos foram isolados:

1. **O aviso de retenção é global, não por controle** — um controle silencia o
   log dos outros. O `uniq` que aparece no journal não é o único retido.
2. **O gate é inconsistente entre categorias** — gatilhos não passam por ele e
   escrevem sempre; luz e número passam. Por isso o journal mostra gatilhos
   replicando enquanto o número era retido, no mesmo instante.
3. **`uhid_replica_ativa` é emitido antes do gate.** "A réplica ativou" **não**
   significa "escreveu no controle". Foi o que confundiu a leitura ao vivo.

E o sintoma que ela descreveu é um **flip-flop**: quando o sinal sobe, vale o
número do jogo; quando cai, a repintura restaura o nosso. A medição das 21:31
pegou a fase "nossa".

**A intenção de projeto já era a certa.** A função que aplica o número do jogo
declara em docstring: *"o número NO CONTROLE passa a ser o número que o JOGO
atribuiu, não o dos nossos registros"*. O caminho existe e é o mesmo para o
jogador 1 e para os do co-op — a suspeita inicial de que o co-op reimpunha o
nosso número foi **refutada lendo o código**. O que há é defeito de
implementação, não escolha pendente.

## A escolha de projeto que isto força

São três saídas, e elas se excluem:

1. **Adotar a numeração do kernel.** Cai por si: ela já coincide com a nossa.
2. **Manter a nossa e aceitar que o jogo discorde.** É o estado atual, e é
   exatamente a queixa.
3. **Influenciar o conjunto que o jogo enumera.** Hoje o jogo vê um arranjo
   misto — dois gamepads virtuais nossos (os DualSense físicos são escondidos
   por variável de ambiente) e dois controles externos crus, porque o inventário
   de externos é declaradamente **read-only**.

A terceira foi a escolhida, e o desenho veio da mantenedora:

> *"Na interface, ao clicarmos no controle — tipo o Switch — ele abre a tela que
> escolhemos como ele deve aparecer na tela."*

Em vez de o projeto decidir que todo controle vira DualSense — e comer em
silêncio o problema dos rótulos de botão, onde o jogo pede `` e o controle diz
`X` —, **a escolha é por controle e é de quem usa**, com o preço dito na hora.
O controle que ganha máscara ganha gamepad virtual, e por consequência entra na
ordem do Hefesto.

O que ainda precisa de resposta antes de virar código: se a máscara é
propriedade do **aparelho** (e mora no registro de identidade, sobrevivendo à
troca de perfil) ou da **configuração do jogo** (e mora no perfil). A inclinação
registrada é a primeira — *"este Nintendo se apresenta como DualSense"* é um fato
sobre o controle, não sobre o jogo aberto.

## O que continua sem prova

- **O critério de numeração do jogo.** Não foi identificado, e a busca no
  repositório confirmou que **nunca foi medido** — as afirmações existentes
  ("o jogo atribui pela ordem de enumeração") são inferência declarada, não
  experimento. O próprio documento da JOGO-01 admite: *"o jogo escolhe quatro
  entre doze, sem critério que possamos prever"*. Sem essa medição, qualquer
  desenho que tente **acertar** a numeração do jogo é chute — e é por isso que a
  terceira via não tenta: ela controla o **conjunto**, não a ordem.
- **Não existe alavanca de ordem.** A varredura não achou nenhuma variável de
  ambiente ou canal que informe número de jogador a um jogo. A única alavanca
  real é **negativa**: tirar dispositivo de cena.
- **O patch do 8BitDo pelo cabo.** Compila limpo, está instalado em disco, e
  **nunca foi carregado** — o módulo em memória é o anterior. Depende do próximo
  reinício.
- **Um controle caiu durante a partida** e apareceu na tela do jogo. Não há
  registro no journal do daemon. Ou o jogo perdeu o dispositivo sem o daemon
  notar, ou foi um externo — que o daemon acompanha com menos detalhe, por serem
  read-only.

## Nota sobre o método

Duas coisas desta sessão merecem ficar como regra:

**O relato de quem usa é evidência, e a leitura dela também.** Foi a mantenedora
quem notou a dessincronia entre luz, jogo e interface — nenhum teste da suíte
chegaria lá, porque os três estão certos isoladamente e só discordam entre si.

**Medir antes de desenhar, e conferir a medição.** O erro de ordenação
documentado acima levou a uma conclusão confiante e falsa, que só não virou
código porque foi verificada uma segunda vez. Uma tabela que bate "quatro de
quatro" é exatamente o tipo de resultado que merece a segunda conferida, não a
primeira comemoração.
