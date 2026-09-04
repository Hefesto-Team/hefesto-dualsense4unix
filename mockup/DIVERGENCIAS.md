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
