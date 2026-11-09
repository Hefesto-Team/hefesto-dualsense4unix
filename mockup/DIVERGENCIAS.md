# As abas em trabalho no desenho

Toda seção aqui é uma aba cujo **desenho já andou** e cujo **produto ainda não
recebeu** — porque ainda não recebeu o OK. O
`scripts/check_o_desenho_aprovado.py` lê este arquivo; a aba que não estiver
aqui, ele reprova.

**A direção é `mockup/` → `layout/`.** O `mockup/` é o desenho de hoje; o produto
só recebe quando a aba é aprovada **inteira**, que é a escolha de
31/08/2026 — nem a cada ponto, nem só no fim da lista.

**Formato** — uma seção por página, com data e o ponto que está aberto:

```
## 01-jogar.html
- **DD/MM/AAAA** — o ponto da lista que está aberto na aba.
```

Quando a aba for aprovada, `--publicar NN` leva o desenho ao produto e **apaga a
seção daqui**: a aba deixou de estar em trabalho.

---

## calibrar-sensores.html
- **07/11/2026** — o desenho da mira com horizontal e vertical, o início do analógico, a velocidade do jogo e os passos do sentido e do início, em duas opções: `calibrar-sensores.html` (A, tudo na coluna da mira) e `escolha/calibrar-sensores-b.html` (B, os três passos na fita). Enquanto a escolha não vem, o produto continua com a sensibilidade única de hoje. Publicar a B é copiar esse arquivo por cima do `calibrar-sensores.html` antes do `--publicar`.

## 08-conexoes.html
- **07/11/2026** — a frase da falta na linha do controle sem ponte, em três opções, no molde `opcoes-da-falta` abaixo da sala. Enquanto a escolha não vem, `a08_conexoes.OPCAO_DA_FALTA` fica vazia e o produto não mostra frase nenhuma. Escolher é gravar a letra nessa constante, o que tira o bloco do desenho, e rodar o `--publicar 08`.

## 09-sistema.html
- **09/11/2026** — o botão «Atualizações» e a «Atualização automática» com o prazo sobem para o cabeçalho do quadro, à esquerda do «Ícone na bandeja», e o registro ganha a altura da linha que saiu; o mapa (`escolha/o-mapa-das-atualizacoes.html`) perde o ajuste, abre com «Escolha o que deve ser atualizado» e «Atualizado» (a cor de em dia). Os campos do produto não mudam (`ESPERA_A_PUBLICACAO` segue vazia); falta o `--publicar 09`.
