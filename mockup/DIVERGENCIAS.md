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
- **03/09/2026** — a decisão 9 dela: *"tracejado para 'não sei'; lisa e vazia
  para 'apagada'"*. Até hoje as duas pintavam a MESMA tira, byte por byte, e a
  ressalva que as separa viajava só no `title` — quem não passa o mouse não vê.
  A tira do desconhecido passa a ser um contorno tracejado (`.tira-luz.incerta`,
  na folha da bancada) e o estado ganha endereço próprio (`luz-incerta`, alvo
  `classe`), para que régua alguma precise adivinhá-lo.

  **O QUE O PRODUTO FAZ ENQUANTO ESPERA, e ele não perde nada:** o pacote emite
  a tira do "não sei" com a classe `incerta` **e com o estilo de linha da
  apagada** (`background:var(--panel);color:transparent;opacity:1`). Na página
  publicada — cuja folha ainda não tem `.tira-luz.incerta` — a classe chega e
  não pinta: a tira fica exatamente como está hoje, lisa e sem halo. Nada de
  tira branca (o `color` herdado acenderia o halo `currentColor`), nada de
  clique morto, nada de metade nova com metade velha. O `luz-incerta` também
  não acha onde pousar e o pintor passa reto, calado — que é o comportamento
  dele para todo endereço que a página não tem.

  **O que muda no dia da publicação:** a folha nova ACRESCENTA o contorno
  tracejado (`.tira-luz.incerta{border:1px dashed var(--comment)}`). Ela não
  disputa nada com o estilo de linha — fundo, halo e opacidade continuam vindo
  dele. Só isso.
  **Espera a palavra dela** — e a publicação já está na lista do dia
  (decisão 16: *"Publicar 04, 05, 06 e 10 — depois do merge"*).
