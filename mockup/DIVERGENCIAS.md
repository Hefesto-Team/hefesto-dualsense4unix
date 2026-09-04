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

## 01-jogar.html
- **04/09/2026** — a folha das dez peças (D-02 e D-03) entrou pelo `monta.py`.
  **Até publicar, o produto continua exatamente como ela o vê hoje:** nenhum
  elemento desta aba usa as peças, então as regras novas não casam com nada e
  a página publicada desenha o mesmo pixel que a bancada.

## 02-controles.html
- **04/09/2026** — a folha das dez peças (D-02 e D-03) entrou pelo `monta.py`.
  **Até publicar, o produto continua exatamente como ela o vê hoje:** nenhum
  elemento desta aba usa as peças, então as regras novas não casam com nada e
  a página publicada desenha o mesmo pixel que a bancada.
- **04/09/2026 · ONDA2-02** — as dez decisões desta aba viraram desenho na
  BANCADA, e **nada foi publicado**: a publicação é uma leva só, para o olho
  dela (`PROVA-DE-TELA-01`). O que a bancada passou a ter, e o produto ainda
  não:

  | o quê | decisão | o que muda no desenho |
  | --- | --- | --- |
  | o **anel interno** de cada cartão, seguindo a luz viva | D-06 / S-11 | um `<span class="anel-vivo">` de 1px dentro dos 2px do casco. **É o único item desta lista que move pixel**, e é o que ela pediu com todas as letras: *"casco borda externa lightbar borda interna"* |
  | a **palavra curta** no lugar do travessão da Barra de luz | [02] | o campo passa a mostrar `Jogo` · `Steam` · `Não sei` · `Apagada`; o `title` da linha passa a ser PINTADO com a frase inteira |
  | o **`?`** ao lado do 🎙 e do ♪ | [04] / [06] | invisível em repouso (a folha o esconde); ele só aparece com o botão apagado |
  | o **`disabled` do ♪ SAIU** | [04] | o botão continua respondendo ao clique — *"apagado e ainda assim responde"* |
  | a **marca da emulação degradada** na máscara | [07] | um `<sup>` que nasce `display:none` e só aparece quando o produto escreve o motivo no `title` |
  | a **linha de ressalva** do alto-falante | [09] + D-02 | não ocupa nada em repouso (`:empty` e `.nada`, as duas metades da peça) |
  | o **endereço do décimo alvo** no acordeão | T-07 | `data-hef-alvo="marcado"` no rádio — endereço de LEITURA, e nada mais |

  **O QUE O PRODUTO FAZ ENQUANTO ESPERA:** exatamente o que fazia. Os endereços
  novos só existem na bancada, e o pacote pergunta à página PUBLICADA antes de
  emitir (`a02_controles._so_se_a_pagina_tiver`) — nenhum valor novo é escrito
  num vão que não existe, e nenhum órfão entra no `casamento.medir(...)`.

  **O QUE JÁ VALE NO PRODUTO SEM PUBLICAR NADA**, porque é campo que a página
  publicada JÁ TEM: o selo composto do microfone (`mic-selo`), a rota lida nas
  duas camadas (`alto-rota`) e o ato do 🎙 num pedido só.

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

## 08-conexoes.html
- **04/09/2026** — a folha das dez peças (D-02 e D-03) entrou pelo `monta.py`.
  **Até publicar, o produto continua exatamente como ela o vê hoje:** nenhum
  elemento desta aba usa as peças, então as regras novas não casam com nada e
  a página publicada desenha o mesmo pixel que a bancada.

## 09-sistema.html
- **04/09/2026** — a folha das dez peças (D-02 e D-03) entrou pelo `monta.py`.
  **Até publicar, o produto continua exatamente como ela o vê hoje** — e aqui
  isso está fotografado: a foto desta aba sai byte a byte igual à de antes da
  mudança (`olhar.py`, Chrome, 1920x1080).

## 10-perfis.html
- **04/09/2026** — a folha das dez peças (D-02 e D-03) entrou pelo `monta.py`.
  **Até publicar, o produto continua exatamente como ela o vê hoje:** nenhum
  elemento desta aba usa as peças, então as regras novas não casam com nada e
  a página publicada desenha o mesmo pixel que a bancada.
