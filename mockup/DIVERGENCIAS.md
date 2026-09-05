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

<!-- AS DEZ ESTÃO AQUI PELO MESMO MOTIVO, e ele é UM: a folha das dez ganhou as
     duas peças da D-02 e da D-03 (`monta.CSS_FOLHA`), e o `<style>` do
     esqueleto é um só para as dez páginas. São 50 linhas acrescentadas,
     e NENHUM elemento das dez abas as usa hoje — quem as usa são as frentes da
     Onda 2, aba por aba.

     ZERO PIXEL MUDOU, e está medido: as fotos da `06` e da `09` saem BYTE A
     BYTE iguais às de antes (`olhar.py`, Chrome, 1920x1080). O que mudou foi o
     sha256, porque o portão compara o arquivo e o INVISIVEIS dele só sabe
     descontar ATRIBUTO de endereço, não regra de folha que nada casa.

     ELAS SAEM DAQUI JUNTAS, na leva de publicação — e não uma a uma: o que
     separa cada aba do produto vai ser o desenho NOVO da Onda 2, que é o que
     precisa do olho dela. -->

## 03-gatilhos.html
- **04/09/2026** — a folha das dez peças (D-02 e D-03) entrou pelo `monta.py`.
  **Até publicar, o produto continua exatamente como ela o vê hoje:** nenhum
  elemento desta aba usa as peças, então as regras novas não casam com nada e
  a página publicada desenha o mesmo pixel que a bancada.

## 04-iluminacao.html
- **04/09/2026** — a folha das dez peças (D-02 e D-03) entrou pelo `monta.py`.
  **Até publicar, o produto continua exatamente como ela o vê hoje:** nenhum
  elemento desta aba usa as peças, então as regras novas não casam com nada e
  a página publicada desenha o mesmo pixel que a bancada.

## 05-vibracao.html
- **04/09/2026** — a folha das dez peças (D-02 e D-03) entrou pelo `monta.py`.
  **Até publicar, o produto continua exatamente como ela o vê hoje:** nenhum
  elemento desta aba usa as peças, então as regras novas não casam com nada e
  a página publicada desenha o mesmo pixel que a bancada.
- **04/09/2026 · ONDA2-05** — **QUATRO decisões dela viraram desenho, e três
  delas OCUPAM ESPAÇO. Nada foi publicado.**

  | o que entrou | decisão | o que muda na tela |
  | --- | --- | --- |
  | as duas linhas de motor viraram **barra que arrasta**, de 0 a 100% | dela, 04/09 (*"os slcers … se multiplicam"*) <!-- noqa-acento: citação literal dela --> | mesma linha, mesmo lugar. O que muda é o **significado do número**: era o par 0-255 que o jogo pediu, e passa a ser o AJUSTE que multiplica o degrau. O pedido do jogo não se perdeu — vira o `title` da linha, pintado pelo produto |
  | uma **linha de estado por coluna** | D-14 | uma faixa nova no fim de cada coluna, com um dos três estados que ela nomeou |
  | uma **linha de MESA** embaixo da grade | [05] | uma linha nova com os quatro degraus do ajuste geral, fora das colunas. E as colunas sem ajuste próprio **deixam de acender degrau** |
  | a **nota do Testar** sobe do `?` para a tela | [02] | uma linha em itálico, esmaecida, embaixo de tudo |

  **O QUE ELA PRECISA OLHAR ANTES DE PUBLICAR — e é um número, não uma
  impressão: o quadro passou a ROLAR 103 px.** Medido no Chrome, no tamanho da
  janela do produto (1180×757), com a `.nota` escondida:

  ```
  PUBLICADO (a que ela abre hoje)  miolo 564 visíveis · 564 de conteúdo · rola 0
  BANCADA   (o desenho de hoje)    miolo 564 visíveis · 667 de conteúdo · rola 103
  ```

  O custo, medido peça por peça: **linha de mesa 53 px · faixa de estado 31 px ·
  nota do Testar 21 px**. Na foto, o que fica abaixo da dobra é a linha de mesa.

  **NÃO HÁ PIXEL A DEVOLVER DENTRO DO QUADRO**, e isso também foi medido: a
  única faixa com conteúdo elástico é o desenho do controle (`--r-des`, 124 px),
  e pagar os 103 px ali deixaria o desenho com 21 — a faixa que ela aprovou
  desapareceria. O `.miolo` (que reserva os 564) é do `topo.html`, comum às dez
  abas, e é decisão dela. **O piso do estado já foi apertado ao mínimo** (20 px,
  uma sublinha) e as margens da mesa e da nota também: os 118 px da primeira
  medição viraram 103.

  **O QUE ISSO DEIXA PARA ELA DECIDIR**, e é a única coisa que este trabalho não
  pode escolher sozinho: se a aba pode rolar 103 px, ou se alguma das três sai.
  As três são decisão dela, e nenhuma foi encolhida para economizar pixel.

  **O QUE O PRODUTO CONTINUA FAZENDO ATÉ ELA PUBLICAR:** as duas linhas de motor
  seguem sendo LEITURA (o par 0-255), e o pacote continua emitindo os endereços
  velhos (`motor-e`, `motor-e-pct`) exatamente para isso — a página que ela abre
  hoje não congela. O gesto `motor`, a linha de mesa e a linha de estado por
  coluna **existem no código e não têm onde cair** na página publicada: são
  endereço novo, e endereço novo só chega pelo `--publicar 05`.

## 06-navegacao.html
- **04/09/2026** — a folha das dez peças (D-02 e D-03) entrou pelo `monta.py`.
  **Até publicar, o produto continua exatamente como ela o vê hoje** — e aqui
  isso está fotografado: a foto desta aba sai byte a byte igual à de antes da
  mudança (`olhar.py`, Chrome, 1920x1080).

## 07-lancadores.html
- **04/09/2026** — a folha das dez peças (D-02 e D-03) entrou pelo `monta.py`.
  **Até publicar, o produto continua exatamente como ela o vê hoje:** nenhum
  elemento desta aba usa as peças, então as regras novas não casam com nada e
  a página publicada desenha o mesmo pixel que a bancada.
- **04/09/2026 · ONDA2-07** — **UMA regra de folha, e ZERO pixel no estado que
  ela vê hoje.** A única mudança de HTML é a classe `.linha-do-wrapper` no
  `<style>`, para o bloco da linha de inicialização à mostra (decisão `07[01]`
  do PO: *"os dois, só quando faz falta"*). **Nenhum elemento da página
  estática a usa** — o bloco e o botão «Copiar a linha» só nascem quando o
  produto lê um jogo com a LINHA INTOCÁVEL na biblioteca dela, e a página
  estática é `cartoes(None)`, que ainda não leu disco nenhum.

  **O QUE ELA PRECISA OLHAR ANTES DE PUBLICAR:** o cartão da Steam **no estado
  intocável** — é o único que muda. Medido no Chrome, 1920×1080, com a carga
  que o produto emitiria:

  | estado | altura do cartão da Steam | botões | janela |
  | --- | --- | --- | --- |
  | dia bom (biblioteca em ordem) | **157 px** | Abrir o lançador · Criar perfil | 1180×777, dobra 0 |
  | com jogo intocável | **231 px** | + **Copiar a linha** | 1180×777, dobra 0 |

  O custo é de **74 px, e só naquele estado**; sem rolagem lateral e sem passar
  da dobra nos dois. As outras duas mudanças desta frente não têm desenho: a
  frase do corpo ganhou três palavras (`(instalados ou não)`, decisão `07[04]`)
  e o silêncio do aviso é comportamento (`07[03]`).

  **O QUE O PRODUTO JÁ FAZ SEM PUBLICAR:** o botão, o bloco e o clique chegam à
  tela viva — o `-diz` e o `-acoes` são pintados pelo pacote a cada tique.
  O que falta até a publicação é só a MOLDURA do bloco (a regra acima), então
  hoje a linha aparece como texto solto dentro do cartão. Foto do WebKit vivo
  no relato desta frente.

## 08-conexoes.html
- **04/09/2026** — a folha das dez peças (D-02 e D-03) entrou pelo `monta.py`.
  **Até publicar, o produto continua exatamente como ela o vê hoje:** nenhum
  elemento desta aba usa as peças, então as regras novas não casam com nada e
  a página publicada desenha o mesmo pixel que a bancada.
- **04/09/2026 · ONDA2-08** — quatro decisões do PO viraram desenho, e **três
  delas já valem no produto sem publicar nada**: a coluna da direita do Check-up
  é UM endereço com alvo `html` (`data-campo="ordem"`), e quem a desenha é o
  pacote.

  | o quê | decisão | onde já vale |
  | --- | --- | --- |
  | o **cartão de cura** abaixo da ordem de serviço | [03] | **no produto**, hoje |
  | o **`[derivado da conta]`** nas frases não medidas aqui | [04] | **no produto**, hoje |
  | o **`+N`** das ordens que não couberam | [07] | **no produto**, hoje |
  | a **frase do rodapé do Mapa**, trocada pela verdade | [08] | só na bancada |
  | o `?` da quinta linha e a dica do ⊘, sem o botão morto | [05], a metade do fato errado | só na bancada |

  **O QUE MUDA DE PIXEL NA BANCADA, e é o que ela precisa olhar:** a coluna da
  direita ganhou um segundo card, e com ele a coluna da esquerda estica — as
  cinco linhas do exame passam a repartir mais altura. Medido nas duas fotos
  (`olhar.py`, Chrome, 1920×1080): a `.janela` continua em **1180×777**,
  `passa_da_dobra: 0`, sem rolagem lateral. O card coube na folga que a coluna
  já tinha.

  **A DÍVIDA DECLARADA, e ela é de tinta, nunca de informação:** as regras
  `.col-ordem .mais` e `.ordem.cura` nasceram nesta folha e a página publicada
  ainda não as tem. Fotografado no produto vivo em 04/09: a pílula do card de
  cura sai **certa** (`.selo.warn` é global e já existe), e a linha do `+N` sai
  em corpo de texto normal em vez de 11 px itálico cinza. **A frase está certa
  desde já; a tinta chega no `--publicar`.**

## 09-sistema.html
- **04/09/2026** — a folha das dez peças (D-02 e D-03) entrou pelo `monta.py`.
  **Até publicar, o produto continua exatamente como ela o vê hoje** — e aqui
  isso está fotografado: a foto desta aba sai byte a byte igual à de antes da
  mudança (`olhar.py`, Chrome, 1920x1080).
- **04/09/2026 · ONDA2-09** — as TRÊS decisões do PO, e **um pixel só muda**.
  1. **O botão "Atualizar" virou "Reaplicar ajustes"** (decisão [01]). Ele fazia
     dois trabalhos com um nome só, e a dica NEGAVA o caro: dizia *"Não muda
     nada"* sobre um clique que manda o serviço reaplicar a configuração e
     reescrever os arquivos de ambiente da Steam. A dica passou a dizer os dois,
     na ordem em que acontecem. **É a ÚNICA mudança visível desta leva**, e está
     medida: comparando as duas fotos do `olhar.py` (Chrome, 1920×1080), a caixa
     que difere é **104×10 px em (796, 339)** — a palavra dentro do botão, e
     nada mais. `.janela` continua em 1180×777, `passa_da_dobra: 0`.
  2. **"Retomar", "Reiniciar o serviço" e "Ver os plugins carregados" ganharam a
     peça do botão cinza** (decisão [02], a D-03 dela). **ZERO pixel na cena que
     ela aprovou:** nessa cena os três TÊM trabalho a fazer, logo nenhum nasce
     `apagado` e a folha comum esconde os três `?`
     (`.btn:not(.apagado) + .ajuda.porque{display:none}`). O que muda só aparece
     na tela viva, e é lá que foi medido: com razão o botão fica cinza, ganha
     `aria-disabled="true"` e encolhe de 184 para 171px para o `?` caber **na
     mesma linha** — a faixa mede os mesmos 156px nos dois estados, e o miolo não
     rola.
  3. **O botão passou a dizer "Reaplicando…" enquanto trabalha** (decisão [03]),
     por um `data-hef-em-voo` — **atributo, zero pixel**. Medido no WebKit do
     produto: durante o gesto o rótulo é "Reaplicando…" e, no pouso, volta a
     "Reaplicar ajustes".

  **O QUE ELA PRECISA OLHAR ANTES DE PUBLICAR:** só o nome do botão. As outras
  duas metades são invisíveis na cena do desenho.

## 10-perfis.html
- **04/09/2026** — a folha das dez peças (D-02 e D-03) entrou pelo `monta.py`.
  **Até publicar, o produto continua exatamente como ela o vê hoje:** nenhum
  elemento desta aba usa as peças, então as regras novas não casam com nada e
  a página publicada desenha o mesmo pixel que a bancada.
- **04/09/2026 · ONDA2-10** — as três decisões de desenho do PO. **Enquanto ela
  não publicar, a página do produto continua a de hoje**, e o pacote emite os
  quatro endereços novos no vazio (declarados em
  `a10_perfis.ESPERANDO_A_PUBLICACAO`).
  - **[01] o cadeado e o ponto de alerta.** O "Funciona em" ganha um cadeado
    laranja à direita e o "Nome do Jogo" um ponto laranja; os dois nascem
    ESCONDIDOS e o produto os acende. A frase inteira aparece ao parar o rato em
    cima. Junto, o "Funciona em" ganha a opção `—` (desabilitada) para o perfil
    cuja regra a tela não sabe mostrar: sem ela o campo ficava com o **"Jogo"
    do mockup** ao lado de um cadeado dizendo "não sei mostrar".
  - **[03] a frase da Prioridade.** O `title` do campo passa a ser a frase que
    ela aprovou em 02/09 — *"Quando dois perfis servem ao mesmo tempo, o de
    número maior entra."* — seguida da explicação do Universal em zero.
  - **[05] a tira do desfecho ganhou a segunda linha.** 15px a mais,
    permanentes, tirados da altura da lista de perfis (≈meia linha). Nada pula:
    o espaço já era reservado. A janela continua com 777px de altura, medida no
    Chrome a 1920x1080 antes e depois.
