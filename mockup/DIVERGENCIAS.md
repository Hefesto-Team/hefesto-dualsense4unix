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

## 05-vibracao.html
- **17/09/2026** — a marca do degrau **herdado** (VIBRA-ACESA-01). A coluna sem
  ajuste próprio passou a acender o degrau que está valendo, com borda tracejada
  em vez do preenchimento cheio: aceso porque é a força que ela sente, diferente
  do escolhido porque procedência é informação.

  **O QUE JÁ CHEGA À TELA DELA SEM PUBLICAR, e é a queixa que abriu a sprint:**
  o *acender* — o endereço `data-campo="degrau"` já existe na página publicada,
  então o pacote acende o botão herdado hoje. O que espera o OK dela é só a
  MARCA (`data-campo="degrau-herdado"` na caixa dos três botões, mais a regra
  `.vib .seg.herdado button.on` na folha), que é endereço novo.

  Até ela publicar, um degrau herdado e um escolhido ficam com a mesma cara na
  tela — que é o estado de 04/09 a 17/09 menos o apagão. A procedência não fica
  sem canal nesse intervalo: clicar o degrau que já vale responde na faixa
  dizendo de onde ele vem (`a05_vibracao.FRASE_DO_QUE_A_COLUNA_MOSTRA`).
