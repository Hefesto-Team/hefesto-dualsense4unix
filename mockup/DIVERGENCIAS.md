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

## 07-lancadores.html
- **03/09/2026** — o botão **"Abrir o lançador"** ganhou endereço (decisão 17
  dela): `data-gesto="abrir-lancador"` e `data-v` com a chave do cartão, nos
  seis. A legenda da aba trocou junto, porque a linha que dizia *"continua sem
  endereço, e é decisão"* virou fato errado no mesmo minuto.
- **O que ela vê na tela dela ENQUANTO espera o OK:** o botão **já funciona**, e
  não é sorte — a fileira de botões é PINTADA (`{chave}-acoes`, alvo `html`), e
  o pacote a reescreve com `desenho.acoes_html()` a cada tique. Medido no DOM
  vivo da página publicada em 03/09: os seis botões carregam o `data-gesto` e o
  `data-v` certos, e o clique no cartão do Lutris chegou ao Python e recusou
  dizendo. O que a publicação muda é só a página ESTÁTICA — a primeira meia
  volta, antes de a pintura chegar — e a legenda.
- **Quem publica é quem coordena**, no fim da leva, junto com as outras abas.
