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

## 02-controles.html
- **10/09/2026** — a fileira do alto-falante ganhou o TERCEIRO botão,
  **«Ouvir junto»** (a `fonte` do nó: o som do PC cai também neste controle,
  sem sair da televisão). É a sprint SOM-NA-TELA-01, e ela existia porque o
  produto já OBEDECIA a `speaker.fonte` desde a SFX-POR-CONTROLE-01 sem que
  nenhuma aba pudesse gravá-la — *o efeito pronto e sem escolha*.

  **Espera o olho dela**: a decisão de forma era dela (três opções na §2
  daquela sprint), e o que está na bancada é a recomendação — um terceiro
  botão na fileira que já existe, na mesma gramática, sem uma linha de folha
  nova e sem custar altura. O que ela aprovar, `--publicar 02` leva ao
  produto.

  **O QUE O PRODUTO FAZ ENQUANTO ESPERA:** a página publicada tem DOIS botões,
  e o pacote se limita a eles — `a02_controles.A_FILEIRA_TEM_TRES` lê a página
  publicada no import e, sem o terceiro botão lá, a fileira continua
  respondendo só «Sons do jogo» e «Todo o som do PC», exatamente como antes.
  O gesto `rota=junto` existe e grava, mas ninguém pode dispará-lo: não há
  botão na tela dela. **Nada muda para ela até o `--publicar 02`** — e é essa
  a diferença que custou três frentes em 02/09, quando o pacote foi para o
  merge com o rótulo novo e a página ficou com o antigo.
