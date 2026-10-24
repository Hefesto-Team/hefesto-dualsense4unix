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

## 04-iluminacao.html
- **24/10/2026** — a cena de exemplo não leva mais nome de pessoa: o P1 mostra «P1», como os outros, e o campo do nome nasce vazio (OS-RESTOS-DO-DESENHO-VELHO-SAEM-DAS-ABAS-03-05-08-01). Até publicar, a cópia estática da aba ainda mostra um nome no P1 antes da primeira pintura.

## 05-vibracao.html
- **24/10/2026** — a cena de exemplo não leva mais nome de pessoa, como na 04 (OS-RESTOS-DO-DESENHO-VELHO-SAEM-DAS-ABAS-03-05-08-01); o ícone do controle da «Força da vibração» é o mesmo, byte a byte, agora de um dono comum. Até publicar, a cópia estática da aba ainda mostra um nome no P1 antes da primeira pintura.

## 08-conexoes.html
- **24/10/2026** — três pontos abertos. A cena de exemplo sem nome de pessoa e sem a `LEGENDA` morta (OS-RESTOS-DO-DESENHO-VELHO-SAEM-DAS-ABAS-03-05-08-01). A dica do botão «Mapa do controle» diz «abre aqui, na janela», no lugar de «abre no navegador» (O-BOTAO-DO-MAPA-DA-08-DIZ-ONDE-ELE-ABRE-01). Na «Rádio e adaptadores», a coluna do «onde» cresce até a espera «Segure PS + Create» e o «Onde fica?», sem quebrar a linha e sem passar para baixo do sino, e as barras dos adaptadores seguem na mesma reta (A-LINHA-DO-ADAPTADOR-NAO-CABE-NA-COLUNA-DO-ONDE-01). Até publicar, o produto continua com a coluna de 116 px e a dica velha.

## mapa-do-radio.html
- **24/10/2026** — o desenho da sala acompanha a 08: o ícone do mapa das entradas diz «abre aqui, na janela» (O-BOTAO-DO-MAPA-DA-08-DIZ-ONDE-ELE-ABRE-01), e a grade da linha do adaptador é a da sala, herdada por cada caixa (A-LINHA-DO-ADAPTADOR-NAO-CABE-NA-COLUNA-DO-ONDE-01). Até publicar, a cópia do produto continua com a dica «abre no navegador» e a coluna de 116 px; o produto não abre esta página sozinha, e a 08 recebe a sala pelo gerador dela.
