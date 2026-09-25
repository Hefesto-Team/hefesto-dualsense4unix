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
- **24/09/2026** — as três pílulas **Fraco · Médio · Forte** na linha «LEDs» de
  cada controle, no molde da linha «Jogador», com o Fraco aceso (decisão dela,
  `D-2409-AS-LUZES-DE-NUMERO-TEM-TRES-BRILHOS`: *"Fraco, Médio e Forte na linha
  LEDs, nascendo no Fraco"*). A faixa dos LEDs foi de 56 para 64 px e a de
  Opções de 72 para 64: a coluna continua em 472 e a aba não rola. Espera
  quem coordena publicar (O-BRILHO-DAS-LUZES-DE-NUMERO-01). Até publicar, a
  tela dela não mostra as pílulas e o pacote não emite o endereço delas
  (`a_pagina_tem_as_pilulas`); o brilho que o perfil guarda — o Fraco, se
  ninguém escolheu — já vai ao aparelho nos dois transportes.
