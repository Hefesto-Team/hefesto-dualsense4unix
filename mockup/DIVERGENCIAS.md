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
- **23/09/2026** — O-ALTO-FALANTE-DIZ-ATIVO-01, esperando a sessão dela. Na cena
  parada, o controle do rádio (P2) passa a mostrar a pílula «ATIVO», como o do
  cabo — desde 10/09 todo controle tem o nó de som dele —, e o lugar vazio (P4)
  perde a pílula, porque lugar sem controle não tem canal. Enquanto ela não
  publicar, o desenho parado continua o velho; a tela viva já pinta pelo
  pacote: «ATIVO» no cabo e no rádio, «DESLIGADO» só com o ♪ calado, e sem o
  «Canal dormindo».

## calibrar-sensores.html
- **23/09/2026** — A-CALIBRACAO-TEM-O-TAMANHO-DO-PROGRAMA-01, esperando a sessão
  dela. A caixa da Calibrar passa a ter o recuo, a largura e a altura da janela
  das abas (lidos do `topo.html` pela `calibrar.moldura()`): na TV dela, de
  1180 x 499 para 1600 x 808, igual à Controles. O que sobra de altura fica
  entre os cartões e o rodapé, que desce para o fim da caixa como o das abas; e
  o miolo rola por dentro quando a janela encolhe. Enquanto ela não publicar, o
  produto continua com a caixa menor.
