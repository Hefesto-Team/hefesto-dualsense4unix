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
- **06/10/2026** — o Wi-Fi em 5 GHz com linha, o «Descobrir a faixa» na faixa do receptor e a seção
  que cabe o painel do «Conectar» (desenho da leva 1.7; sprint OS-OUTROS-SEM-FIO-APARECEM-E-A-PROCURA-CABE-NA-SECAO-01).
  Até publicar, a página publicada continua a de 05/10, sem o estilo da linha do 5 GHz nem do
  botão: o pacote novo só entra no mesmo fecho do `--publicar 08`, senão o trilho sai cru.
- **06/10/2026** — o «Conectar» sem o véu (a caixa de outro adaptador muda o alvo, o «⋮» de outra
  linha troca a gaveta) e a gaveta do «⋮» do tamanho do que mostra, ao lado da linha, com o estado
  do aparelho e o vermelho com letra branca no que apaga (sprint
  O-CONTROLE-NOVO-SE-CONECTA-E-SE-TIRA-PELA-CONEXOES-01). O pacote já manda o estado e a classe
  `apaga`; sem o `--publicar 08` no mesmo fecho, a gaveta da página de 05/10 mostra a linha do
  estado sem estilo.
