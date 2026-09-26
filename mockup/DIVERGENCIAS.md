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

## 08-conexoes.html
- **25/09/2026** — A-CONEXOES-O-QUE-A-LISTA-DELA-ACHOU-01, esperando quem
  coordena publicar. **A publicação vai JUNTO com o merge**: o pacote já pinta
  o nome do controle como `Nome ● Modelo do plástico ● Pn` (o `.quem` e o
  `.quem-resto`), e a folha da publicada ainda tem a coluna do nome em 13
  caracteres — medido na bancada de tela, o nome quebra em três linhas na
  publicada. A bancada traz as duas decisões dela da lista «Conexões hoje» (o
  formato do nome, com a coluna de 13 a 30 caracteres; e a caixa do adaptador
  que se arrasta pela linha de cima, com a ordem gravada pelo `#rd-reordenar`
  escondido) e três curas do roteiro, todas medidas clicando na bancada: o
  painel aberto segue o molde (o «Procurando» mostra o que a busca acha
  enquanto está aberto, e fecha quando alguém chega), a caixa única não fecha,
  e o «Examinar Entradas» abre o Check-up quando o exame aplica. Nenhuma
  palavra nova na tela; a dica «Arraste para mudar a ordem» é o `title` da
  linha de cima.
