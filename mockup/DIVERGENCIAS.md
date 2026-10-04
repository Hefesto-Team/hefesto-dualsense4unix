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
- **03/10/2026** — a faixa «Dispositivos Conectados» em pistas, uma por adaptador, rede e rádio
  vizinho (CADA-FAIXA-TEM-DONO-01), o «Parear de novo» e a janelinha do «Esquecer» sem o
  «Procurar» (O-CONTROLE-JA-PAREADO-SE-PAREIA-DE-NOVO-NUM-CLIQUE-01). Até publicar, a 08 publicada
  traz os selos soltos no cabeçalho. Falta só o `--publicar 08` no fecho.
