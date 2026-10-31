# As abas em trabalho no desenho

Toda seção aqui é uma aba cujo **desenho já andou** e cujo **produto ainda não
recebeu** — porque ainda não recebeu o OK. O
`scripts/check_o_desenho_aprovado.py` lê este arquivo; a aba que não estiver
aqui, ele reprova.

**A direção é `mockup/` → `layout/`.** O `mockup/` é o desenho de hoje; o produto
só recebe quando a aba é aprovada **inteira**, que é a escolha de
31/08/2026 — nem a cada ponto, nem só no fim da lista.

**Formato** — uma seção por página, com data e o ponto que está aberto:

```
## 01-jogar.html
- **DD/MM/AAAA** — o ponto da lista que está aberto na aba.
```

Quando a aba for aprovada, `--publicar NN` leva o desenho ao produto e **apaga a
seção daqui**: a aba deixou de estar em trabalho.

---

## 01-jogar.html
- **31/10/2026** — o cabeçalho do controle perde o vão da linha do giroscópio (a frase da máscara Xbox 360, na linha e na dica). Até publicar, o produto ainda tem o vão, que fica vazio: o pacote parou de escrever nele.

## 09-sistema.html
- **31/10/2026** — a linha «Nenhum controle no cabo» do Status perde a dica que explicava o transporte («não há som nem vibração para rotear»): a dica é a própria linha.
