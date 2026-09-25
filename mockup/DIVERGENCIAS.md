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

## 08-conexoes.html
- **24/09/2026** — A-GESTAO-SEGUE-O-JOGADOR-01, esperando quem coordena
  publicar. O destaque da fita da Gestão de Controles acha o chip pelo número
  do jogador (`data-pref`), com regra para os quatro lugares. Medido no piloto
  com o P1 fora: a publicada acende o P3 quando o P2 abre, e com o P3 aberto
  não abre linha nem acende chip; a bancada acende e abre o do jogador, e com
  um controle só o chip dele acende no «Todos». A seta ▴ diz «todos abrem
  juntos» em vez de contar os do desenho. O texto do desenho que ainda dizia
  cabo/rádio vira USB/BT: as duas dicas do «A luz não acende», o censo das
  entradas e a cena do Check-up. «Turno de rádio», «pesa no rádio» e «ruído no
  rádio» ficam, porque ali o rádio é o recurso. Nada sai do lugar.
  Até publicar, a fita do produto continua acendendo pela posição; as dicas da
  luz e do microfone já dizem BT na publicada (medido no piloto), porque quem
  as repinta é o pacote.
