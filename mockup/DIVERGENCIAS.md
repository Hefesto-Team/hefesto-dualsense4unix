# As abas em trabalho na bancada

Toda seção aqui é uma aba cujo **desenho já andou** e cujo **produto ainda não
recebeu** — porque ela ainda não deu o OK. O
`scripts/check_o_desenho_aprovado.py` lê este arquivo; a aba que não estiver
aqui, ele reprova.

**A direção é `mockup/` → `layout/`.** A bancada é o desenho de hoje; o produto
só recebe quando ela aprova a aba **inteira**, que é a escolha dela de
31/08/2026 — nem a cada ponto, nem só no fim da lista.

**Formato** — uma seção por página, com data e o ponto que está aberto:

```
## 01-jogar.html
- **DD/MM/AAAA** — o ponto da lista que está aberto nela.
```

Quando ela aprovar a aba, `--publicar NN` leva o desenho ao produto e **apaga a
seção daqui**: a aba deixou de estar em trabalho.

---

## 10-perfis.html

- **06/09/2026** — **UMA OPÇÃO A MAIS no seletor "Funciona em": "Jogo (pela
  janela)"**, a sexta forma que a ONDA5-10-01 (decisão 10-Q2 dela) fez o produto
  saber guardar. É a regra que o botão "Detectar" passa a gravar quando o jogo
  **não é da Steam** — uma classe de janela só.

  **Por que não publiquei:** publicar é ato dela. Aqui a mudança é VISÍVEL (uma
  linha nova no `<select>`), então nem a régua do que-se-vê a absolveria — e
  não deveria.

  **O que ela vê HOJE, até publicar:** a aba Perfis de ontem, com cinco opções
  no seletor. **E o custo da espera NÃO é zero — medido no WebKit vivo** por
  `scripts/ensaios/o_detectar_grava_o_jogo_de_fora_da_steam.py`, com o MESMO
  perfil no disco (`window_class: ["GrimFandango"]`) pintado nas duas páginas:

  | | opções do seletor | a pintura escreveu | o campo mostrou |
  | --- | --- | --- | --- |
  | **bancada** | 6 (com "Jogo (pela janela)") | 3 de 3 | `Jogo (pela janela)` |
  | **publicado** | 5 | **2 de 3** | **`Jogo`** |

  O `escrever()` do piloto só escreve num `<select>` quando alguma opção CASA
  (`hefesto_vivo.py`, `if(!tem) return 0;`), então o campo **fica com o "Jogo"
  que o desenho cravou** — e o cadeado NÃO acende, porque o produto sabe
  descrever a regra. É o defeito que o `aba10.opts` documenta, pelo avesso: a
  tela afirma "Jogo" sobre um perfil que casa por janela, sem nada ao lado
  dizendo que ela não sabe. O `Detectar` **grava certo no disco** nos dois
  casos; o que espera pelo `--publicar 10` é o rótulo.

  **O que fecha:** `scripts/check_o_desenho_aprovado.py --publicar 10`, no OK
  dela da aba. Nada mais espera por isto.

## 02-controles.html

- **05/09/2026** — **UMA LINHA DE COMENTÁRIO CSS, sem um pixel de diferença.**
  O gerador `aba02.py` teve um endereço de linha remedido (o alvo `classe` do
  `escrever()` mudou de lugar quando o piloto ganhou a piscada da `03-Q4`), e o
  comentário que o cita é EMITIDO dentro do `<style>` da página. A bancada foi
  regerada; o produto não.

  **Por que não publiquei:** publicar é ato dela, e a regra existe porque
  publicar troca o que ela abre. Aqui a mudança é provadamente invisível — as
  dez fotos de `docs/usage/assets/aba-NN-*.png` saíram byte a byte idênticas
  antes desta regeração —, mas *"é só um comentário"* é exatamente o argumento
  com que uma exceção vira hábito.

  **O que ela vê HOJE, até publicar:** exatamente a mesma aba Controles de
  ontem. A página que o produto renderiza continua com o endereço antigo dentro
  de um comentário do `<style>` — nenhum clique, nenhuma frase e nenhum pixel
  dependem dele. O custo da espera é zero, e esta é a primeira declaração desta
  lista de que isso se pode dizer com medição por trás.

- **06/09/2026 — E A LINHA ACIMA DEIXOU DE SER VERDADE NO MESMO DIA.** A
  `ONDA5-02-02` entrou e a aba mudou de VERDADE: o `♪` do alto-falante trocou o
  alvo `classe` pelo `atributo` (`data-som`) e ganhou duas cores lidas do dono
  (`mesa_viva.selo_do_mic`) — ATIVO no `--green` da página, MUDO no `--orange`,
  e sem leitura o piloto REMOVE o atributo e o botão volta ao neutro. O `🎙` do
  segundo cartão perdeu um vermelho que estava **congelado** pelo gerador
  (`rgb(255,85,85)` → `rgb(68,71,90)`, igual ao do primeiro): a classe vinha do
  gerador e o glifo não tinha `data-campo`. Com os dois escritores fora,
  `.mudo-i.on` saiu da folha.

  **E as duas dicas pararam de mandar para uma janela que está saindo:** o `🎙`
  aponta para `hefesto-dualsense4unix mic release` e o `♪` para
  `speaker release`, dizendo que devolve **o controle**, não o valor. A frase
  banida *"janela do aplicativo"* saiu; *"linha de comando"* não entrou — o que
  a tela mostra é o nome do verbo, LIDO de `cmd_speaker._ACOES` e
  `cmd_mic._ACOES_FIRMWARE`.

  **Nenhum botão novo no cartão:** a decisão 02-Q6 dela (Liberar/Devolver ficam
  fora) segue intacta.

  **Quem escreveu esta atualização, e por quê:** o coordenador, na costura da
  ONDA A. O agente da `ONDA5-02-02` mediu que **este arquivo é `nao_toca` em
  quatro sprints e `posse` em nenhuma** — o portão do desenho ficava VERDE
  porque a seção `## 02-controles.html` existia, enquanto o corpo dela
  descrevia uma aba que deixou de existir. *Uma declaração de divergência que
  envelhece em silêncio é um portão verde sobre nada* — a oitava desta casa em
  quatro dias. **Este arquivo passa a ser posse declarada do coordenador na
  costura de cada onda.**

  **O que fecha:** o `--publicar 02` da próxima vez que ela aprovar a aba. Nada
  espera por isto — nenhuma sprint depende desta linha.

---

## 04-iluminacao.html

- **06/09/2026 — LUZES-01.** A célula LEDs ganhou a botoeira das cinco luzes de
  jogador (clicáveis, uma a uma) e seis teclas de desenho — `P1`..`P4`, todas e
  nenhuma —, o indicador virou o botão de reenvio, e a faixa do título ganhou o
  "Todos no automático". **Esta sprint NÃO publica**: o `--publicar 04` continua
  sendo ato dela, e a leva inteira publica de uma vez, no fecho (decisão dela,
  06/09). Enquanto isso, o pacote emite o indicador de LEITURA que o publicado
  sabe desenhar — a guarda é `a04_iluminacao.a_folha_alcanca_a_botoeira()`, e
  ela responde `False` até a folha chegar à página publicada.

  **A densidade é o ponto de olho dela:** a botoeira ocupa 216 dos 220 px da
  célula. Se ela recusar, a saída medida é a faixa nova da grade, e ela custa
  uma rolagem ou a redução do desenho do controle.

  **O que fecha:** o `--publicar 04` depois do OK dela na aba inteira.

## 05-vibracao.html

- **06/09/2026** — **A NOTA DO TESTAR VOLTOU PARA O `?`** (`ONDA5-05-01`, a
  05-Q2 dela: *"As duas na dica."*). A frase *"Os valores acima ainda passam
  pela intensidade escolhida ali em cima…"* deixou de ser a linha cinza em
  itálico embaixo da grade e voltou para dentro do `?` do **Testar agora**, ao
  lado das duas orações do par. Saíram junto a `.vib-nota` do miolo e a regra
  de CSS que só ela usava.

  **E a dica passou a abrir para a DIREITA, o que é conserto de defeito
  medido:** ela carregava `left:auto;right:22px` — o arranjo das dicas do lado
  direito da página —, e neste `?`, que mora na primeira coluna da grade, isso
  punha **224 dos 330 px da caixa fora da janela**. Medido nos dois motores, a
  1920x1080: Chrome (`interface/olhar.py`) e WebKit (o piloto). Com o padrão da
  casa a caixa vai de x=505 a x=835 dentro de uma janela de 370 a 1550 —
  **sangria zero**.

  **O que ela vê HOJE, até publicar:** a aba Vibração de ontem — a linha cinza
  ainda embaixo da grade, e o `?` do Testar agora ainda cortado pela borda
  esquerda da janela. **O corte é do produto publicado, não desta mudança**:
  medido em `interface/paginas/05-vibracao.html`, a mesma sangria de 224 px já
  existia com as duas orações.

  **O que fecha:** o `--publicar 05` depois do OK dela na aba inteira.

- **06/09/2026** — **A CONFIRMAÇÃO SAIU DO CARTÃO E FOI PARA A FAIXA**
  (`ONDA5-05-03`, a 05-Q4 dela: *"Linha embaixo da grade (…) nomeando a coluna
  (`P2 · voltou ao ajuste geral`) e some logo depois; nada se mexe dentro das
  colunas"*). O `#vib-estado` passou a declarar `data-hef-recados="sucesso"` e
  `data-hef-recado-classe="est recibo"`, e a folha ganhou o quarto tom, o
  `recibo`, em `--green`. As três frases do clique encolheram para caber numa
  linha (331 → 134, 267 → 162) e ganharam o `P{n} ·` na frente; o mecanismo do
  `Auto` foi para o `?` do "Força da vibração", que passou de 190 para 262 px de
  altura com sangria zero nos quatro lados.

  **A METADE DO PILOTO ENTROU NA COSTURA** — `pintar_recados` conhece agora o
  TERCEIRO lugar, a faixa que a página declara. Medido pelo coordenador contra a
  bancada da 05, com o sucesso entrando pelo `_depositar`: o recado pousa em
  `#vib-estado` com a classe `hef-recado est recibo`, 16 px de uma linha, e o
  desenho do P1 fica parado em 230 px. Com o terceiro lugar arrancado ele volta
  para DENTRO da coluna, em `y=228` sobre um desenho que começa em 230.

  **O que ela vê HOJE, até publicar:** a aba Vibração de ontem — o aviso do
  clique nascendo dentro da coluna, tarja verde cobrindo o topo do desenho do
  controle por 6 s. Nenhuma das dez páginas publicadas declara
  `data-hef-recados`, então o piloto se comporta hoje como ontem.

  **O que fecha:** o `--publicar 05` depois do OK dela na aba inteira.
## 06-navegacao.html — **JÁ PUBLICADA, e ela precisa saber disso**

- **06/09/2026** — a `ONDA5-06-02` **publicou** `interface/paginas/06-navegacao.html`.
  A aba passou a ter **22 linhas**: o **Botão PS** é a 19ª, e abre em *"Abrir a
  Steam"*, que é o `padrao()["ps"]` do motor.

  **Publicar é ato dela, e esta é a exceção do dia — declarada, não escondida.**
  A decisão de manter foi do coordenador, na costura da ONDA B, com três razões:

  1. **A sprint declarava a posse.** `interface/paginas/06-navegacao.html` está
     em `posse:` da `ONDA5-06-02`, enquanto as irmãs da mesma leva (`ONDA5-05-01`,
     `ONDA5-02-02`) a põem em `nao_toca:`. A diferença é do desenho da fila, não
     escolha do agente.
  2. **Desfazer criaria perda SILENCIOSA de trabalho dela**, que é o defeito que
     esta casa mais persegue: a tela ficaria com 21 linhas sobre um produto de
     22, e o «Guardar» **descartaria a escolha do PS sem dizer uma palavra**,
     porque a varredura não a traria.
  3. **O piloto renderiza o PUBLICADO.** Sem publicar não existe prova de tela —
     e ela é obrigatória —, e duas das sete réguas que a `ONDA5-06-01` deixou
     vermelhas leem a página publicada.

  **O que isso muda para ela, no FECHO:** a volta única de publicação continua
  acontecendo, e a aba 06 entra nela — só que **já publicada**. Se ela olhar a
  linha do PS e disser que não, o desfazer é um comando:
  `git checkout <commit> -- src/hefesto_dualsense4unix/interface/paginas/06-navegacao.html`.

## 08-conexoes.html

- **06/09/2026** — a 08-Q5 e a 08-Q7 (`ONDA5-08-01`). O desenho ganhou a linha
  do exame que fica **em cinza** quando ela manda ignorar, o `title` do ⊘ que
  troca de verbo, e as duas linhas de `+N` (exame e rádios vizinhos).

  **O que ela vê HOJE, enquanto não publicar:** a aba Conexões de ontem, com uma
  diferença medida — o ⊘ grava e desfaz no disco, e a LINHA não muda de cor,
  porque a página publicada não tem o endereço `exame-calada`. O veredito do
  topo continua respondendo.

  **O que fecha:** `--publicar 08`, que é ato dela — e nesta leva isso acontece
  numa volta só, no FECHO (decisão dela, 06/09).

  **Escrito pelo coordenador**, na costura da ONDA A: este arquivo é posse do
  coordenador desde 06/09, e a sprint que produziu a divergência não podia
  declará-la. O texto é o que o agente da `ONDA5-08-01` deixou pronto no
  relatório dele.

## 09-sistema.html

- **06/09/2026** — **UMA LINHA, e os dois pixels que ela mudam são PALAVRA
  DELA** (`ONDA5-09-01`, a 09-Q1 e a 09-Q3). O botão do `daemon.reload` volta a
  se chamar **"Atualizar"** e a espera a dizer **"Atualizando…"**; a dica dele
  passa a nomear o que foi MEDIDO do outro lado do clique, e não o que se
  supunha.

  ```
  linha 1245 · bancada  Atualizar          · data-hef-em-voo="Atualizando…"
  linha 1245 · produto  Reaplicar ajustes  · data-hef-em-voo="Reaplicando…"
  ```

  **É uma REVERSÃO, e a reversão é dela.** Em 04/09 o PO decidiu rebatizar o
  botão pela metade cara; em 05/09 ela leu a mesma pergunta e escolheu o
  contrário: *"Segue fazendo os dois. Com mesmo nome"*. O que estava no produto
  desde `a45b7799` é a recomendação que perdeu.

  **A dica mudou de metade, e por medição:** ela prometia *"reaplicar a
  configuração"*, e com `config_overrides` vazio isso **não acontece** —
  `daemon/lifecycle.py:1353` e `:1361` comparam `old` com `new` e nunca
  disparam. O que acontece são duas coisas: o serviço religa o leitor dos
  atalhos do controle (`lifecycle.py:1351-1352`) e reescreve os arquivos de
  ambiente da Steam (`ipc_handlers.py:5472`). A dica passou a dizer essas duas.

  **Por que não publiquei:** publicar é ato dela, e aqui a mudança é VISÍVEL —
  duas palavras que ela lê no botão. A `PROVA-DE-TELA-01` é a regra mais velha
  desta casa, e ela vale exatamente para o caso em que a mudança é a palavra
  dela: quem confere que a palavra chegou certa é ela, olhando.

  **O que ela vê HOJE, até publicar:** a aba Sistema de ontem, com o botão
  ainda dizendo "Reaplicar ajustes". Nada quebra — os quatro botões da coluna,
  os três cinzas e o `data-hef-em-voo` continuam inteiros nos dois lados.

  **O que fecha:** `scripts/check_o_desenho_aprovado.py --publicar 09`, depois
  do olho dela.
