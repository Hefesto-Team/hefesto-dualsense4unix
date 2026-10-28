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
- **27/10/2026** — a página deixa a tira e vive dentro da Jogar; o Calibrar giroscópio ganhou o glifo do giroscópio. Até publicar, o produto continua com a Controles como aba própria e o Calibrar sem glifo.

## mapa-das-portas.html
- **27/10/2026** — a página embute a letra das abas (Space Grotesk e JetBrains Mono, do pacote). Até publicar, o produto continua com a letra do sistema.

## mapa-do-radio.html
- **27/10/2026** — a página embute a letra das abas num `<style>` próprio, depois da folha que a aba Conexões lê. Até publicar, o produto continua sem o `@font-face` e cai na letra do sistema onde a Space Grotesk não está instalada.
