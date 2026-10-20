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
- **20/10/2026** — o piso de 24 px nos alvos e de 12 px na letra, o lugar sem controle que diz só «Player N • Desconectado» e a folha do piso na cabeça da página (escolha «Controles: A» dela, 20/10); espera só o `--publicar 02`. Enquanto isso, a página publicada segue com os alvos e as letras de antes e com o texto antigo no lugar sem controle, e o pacote pinta os mesmos campos nela sem quebrar nada.

## 09-sistema.html
- **20/10/2026** — o piso de 24 px nos alvos e de 12 px na letra, com a folha do piso na cabeça da página (escolha «Sistema: A» dela, 20/10); espera só o `--publicar 09`. Enquanto isso, a página publicada segue com os alvos e as letras de antes, e o pacote pinta os mesmos campos nela sem quebrar nada.

## 08-conexoes.html
- **20/10/2026** — duas palavras de dica em minúscula («tem», «total»: a regra da primeira letra); espera só o `--publicar 08`. Enquanto isso, a página publicada segue com as duas em caixa alta, e o portão `maiuscula-decorativa` fica vermelho nela até a publicação.
