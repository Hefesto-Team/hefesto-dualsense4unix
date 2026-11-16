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

## calibrar-sensores.html
- **07/11/2026** — o desenho da mira com horizontal e vertical, o início do analógico, a velocidade do jogo e os passos do sentido e do início, em duas opções: `calibrar-sensores.html` (A, tudo na coluna da mira) e `escolha/calibrar-sensores-b.html` (B, os três passos na fita). Enquanto a escolha não vem, o produto continua com a sensibilidade única de hoje. Publicar a B é copiar esse arquivo por cima do `calibrar-sensores.html` antes do `--publicar`.

## 08-conexoes.html
- **07/11/2026** — a frase da falta na linha do controle sem ponte, em três opções, no molde `opcoes-da-falta` abaixo da sala. Enquanto a escolha não vem, `a08_conexoes.OPCAO_DA_FALTA` fica vazia e o produto não mostra frase nenhuma. Escolher é gravar a letra nessa constante, o que tira o bloco do desenho, e rodar o `--publicar 08`.

## 07-lancadores.html
- **16/11/2026** — a janela de extensão ganha o controle vivo (o molde do desenho do Mapa, o script que o veste, o estilo dos cartões e da fileira de chaves, e a página própria que ocupa a aba), da sprint A-JANELA-DO-MODO-IMERSAO-GANHA-UM-DESENHO-VIVO-01. Até publicar, a página publicada não leva o molde, o script nem o estilo: a extensão que pede o controle vivo ou os cartões (o Modo imersão 0.5.3) abre a janela com o lugar do desenho vazio e os cartões sem a moldura. O `--publicar 07` sai junto da 0.5.3.

## janela-do-modo-imersao.html
- **16/11/2026** — o desenho da janela «Configurar · Modo imersão», gerado pelo `src/hefesto_dualsense4unix/interface/janela_do_imersao.py` com o mesmo `modificacao_miolo_html` do produto, do manifesto e do Estúdio da extensão guardados em `mockup/modo-imersao/`: quatro abas (Jogo, Sentidos, Efeitos e «Ensinar este jogo»), sem a faixa «Ao vivo». A janela não vira página própria: o produto a desenha pela janela de extensão da 07 (`07-lancadores.html`), e, enquanto a 07 não se publica, abre a janela com as quatro abas, o lugar do desenho vazio e os cartões e a fileira sem a moldura. Os pontos que não existem hoje (a tabela L2/R2 por estilo, a grade da comunidade com Enviar e Importar, o L2/R2 por controle e os medidores de cada sentido) esperam a sprint deles.
