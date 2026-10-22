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

## 09-sistema.html
- **22/10/2026** — o Status em seis linhas, com o aviso do Steam Input dentro da linha dele (O-STATUS-DO-SISTEMA-TEM-SEIS-LINHAS-SEMPRE-01). Até publicar, o produto continua com o aviso do Steam Input numa sétima linha; o pacote não muda antes do «pode seguir».

## 10-perfis.html
- **22/10/2026** — o Ativar que sabe ficar cinza com a razão na dica, para a cena do serviço parado (O-ATIVAR-DO-PERFIL-VALE-OU-A-TELA-DIZ-POR-QUE-01). Até publicar, o produto continua com o Ativar verde e sem endereço de razão; o pacote não escreve o campo novo antes do «pode seguir».
