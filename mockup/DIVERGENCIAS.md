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

## 07-lancadores.html
- **31/10/2026** — AS-FRASES-QUE-SOBRARAM-DA-TELA-SAEM-01: as linhas de impedimento dizem só «Steam Input ligado» e
  «Fora do Proton fixado», sem o que o jogo vê; os botões ficam. A lista viva já sai curta do
  `impedimentos_da_steam`; até publicar, só o exemplo estático da página guarda a frase longa.

## 08-conexoes.html
- **31/10/2026** — AS-FRASES-QUE-SOBRARAM-DA-TELA-SAEM-01: a dica de cada entrada do mapa do gabinete perde
  «O sistema enumera este aparelho como …» e fica com o veredito. O produto vivo já monta o mapa pelo `conexoes.py`
  curado; até publicar, a página estática da 08 guarda as dicas velhas.
