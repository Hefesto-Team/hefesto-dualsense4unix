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

## mapa-das-portas.html
- **25/10/2026** — sem leitura deste computador, o mapa diz o porquê («Entradas ainda não mapeadas» ou «Não deu para ler as entradas deste computador») e não desenha o gabinete de exemplo; a validar por ela. Até publicar, a página do produto não tem `hefestoSemLeitura`: o mapa sem leitura continua no gabinete de exemplo, e o piloto registra a cegueira «o arranjo desta máquina não chegou à página».
