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

## 01-jogar.html
- **27/10/2026** — a Jogar junta os controles: o quadro Status (Ligado, Desligado, Reconectar e Modo Freestyle na mesma linha, os modos Sony DualSense, Xbox e Nintendo Pro com a silhueta de cada um) e, embaixo, os Dispositivos conectados da antiga Controles. Sai o «O controle é visto como» e o Point and click. Aberto: o daemon e a ponte não conhecem o gesto `modo-nintendo` nem o modo único para todos os controles. Até publicar, o produto continua com a Jogar de hoje, o quadro do «visto como» e a aba Controles.

## 02-controles.html
- **27/10/2026** — a página deixa a tira e vive dentro da Jogar; o Calibrar giroscópio ganhou o glifo do giroscópio. Até publicar, o produto continua com a Controles como aba própria e o Calibrar sem glifo.

## 03-gatilhos.html
- **27/10/2026** — a tira tem nove abas (a Controles entrou na Jogar) e o contador «N controles» saiu do cabeçalho; até publicar, o produto continua com as dez abas e o contador.

## 04-iluminacao.html
- **27/10/2026** — a tira tem nove abas (a Controles entrou na Jogar) e o contador «N controles» saiu do cabeçalho; até publicar, o produto continua com as dez abas e o contador.

## 05-vibracao.html
- **27/10/2026** — a tira tem nove abas (a Controles entrou na Jogar) e o contador «N controles» saiu do cabeçalho; até publicar, o produto continua com as dez abas e o contador.

## 06-navegacao.html
- **27/10/2026** — a tira tem nove abas (a Controles entrou na Jogar) e o contador «N controles» saiu do cabeçalho; até publicar, o produto continua com as dez abas e o contador.

## 07-lancadores.html
- **27/10/2026** — a tira tem nove abas (a Controles entrou na Jogar) e o contador «N controles» saiu do cabeçalho; até publicar, o produto continua com as dez abas e o contador.

## 08-conexoes.html
- **27/10/2026** — a tira tem nove abas (a Controles entrou na Jogar) e o contador «N controles» saiu do cabeçalho; até publicar, o produto continua com as dez abas e o contador.

## 09-sistema.html
- **27/10/2026** — a tira tem nove abas (a Controles entrou na Jogar) e o contador «N controles» saiu do cabeçalho; até publicar, o produto continua com as dez abas e o contador.

## 10-perfis.html
- **27/10/2026** — a tira tem nove abas (a Controles entrou na Jogar) e o contador «N controles» saiu do cabeçalho; até publicar, o produto continua com as dez abas e o contador.
