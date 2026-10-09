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

## mapa-do-radio.html
- **08/10/2026** — a caixa e o fone custam 366 fatias (61 pacotes x 6: o 2-DH5 ocupa 5 fatias, mais a
  resposta), e não 244; o número do desenho é demonstrativo e continua estimado (sprint
  O-232-SAI-E-A-CONTA-DA-PONTE-ENTRA-01). Até publicar, a página do produto continua a de antes, com os 244 no dado e no comentário
  da caixa e do fone. A linha da caixa e do fone continua em 61 Hz, mas o ar que sobra no
  adaptador deles cai de 361 para 117 fatias (ele varre: o teto é 849): um controle arrastado
  para lá mostra 0 Hz em vez de 53 Hz. O «Equilibrar» da cena continua apontando a Entrada 4.

## 01-jogar.html
- **08/10/2026** — no Desligado, os botões passam a ser Nativo e Steam Input, no mesmo estilo dos do Ligado; o
  Steam Input sai do Ligado, que fica com Sony DualSense, Xbox e Navegação (sprint
  NO-DESLIGADO-A-STEAM-NAO-SE-METE-E-O-JOGO-MANDA-01, opção a mudada por ela). Até publicar, o produto continua com
  o Steam Input no Ligado e a faixa fixa «Modo Nativo» no Desligado.
