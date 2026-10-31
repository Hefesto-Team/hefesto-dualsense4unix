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

## 03-gatilhos.html
- **31/10/2026** — a lista do efeito do gatilho tem um «—» só (o nenhum efeito, sem a segunda opção escondida do lugar vazio), e cada célula ganha o ponto de chegada no canto (verde chegou, amarelo a caminho, vermelho fora do ar, ciano jogo) com a frase do recibo do daemon na dica. Até publicar, o pacote vivo já pinta o nenhum efeito pelo dono novo, mas o publicado não tem o ponto nem a frase da célula.

## 04-iluminacao.html
- **31/10/2026** — a lista do Efeito tem o «—» como nenhum efeito, e a célula ganha o ponto de chegada da luz, com a frase do recibo na dica. Até publicar, o pacote vivo já pinta o nenhum efeito pelo dono novo, mas o publicado não tem o ponto nem a frase da célula.

## 05-vibracao.html
- **31/10/2026** — as listas do Efeito háptico e do Padrão dos motores têm o «—» como nenhum efeito, e cada uma ganha o ponto de chegada, que diz «sem recibo» enquanto o daemon não confirma a háptica e os motores. Até publicar, o pacote vivo já pinta o nenhum efeito pelo dono novo, mas o publicado não tem o ponto nem a frase da célula.
