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

## 06-navegacao.html
- **19/11/2026** — «Escolher um programa…» sai da lista de cada linha de botão: o `por_grupo` não oferece o que não tem quem faça (`SEM_ATENDENTE`), por delegação a validar (`D-1911-TODA-ACAO-DO-BOTAO-TEM-QUEM-A-FACA`). O resto da aba é o publicado. Enquanto o `--publicar 06` não roda, a linha segue oferecendo a opção, sem efeito, como antes.

## janela-do-modo-imersao.html
- **16/11/2026** — o desenho da janela «Configurar · Modo imersão», gerado pelo `src/hefesto_dualsense4unix/interface/janela_do_imersao.py` com o mesmo `modificacao_miolo_html` do produto, do manifesto 0.5.6 da extensão guardado em `mockup/modo-imersao/`: sem a coluna «Agora», com a faixa do alto (Tocando, Calado com o motivo ou Esperando um jogo, as linhas e as três últimas escritas) e três abas (Sentir, Efeitos e Controles), o «Testar» no pé de cada cartão de efeito, com o veredito, e a marca «Terror». A janela não vira página própria: o produto a desenha pela janela de extensão da 07 (`07-lancadores.html`), e, enquanto a 07 não se publica, abre a janela com a faixa, as três abas, os medidores, as trilhas e o veredito, sem o estilo desses pedaços. O que difere do pedido: as últimas escritas dizem o canal e o plástico, não o nome do efeito (a porta não o anota); sem o botão «Abrir a aba Jogar»; a linha de cada controle não diz USB ou BT (a `controles.lista` não leva o transporte); a «Tensão da cena» é uma linha da faixa; os cartões sem teste na extensão (Clima tenso, Peso da mira, Som no corpo e os Gatilhos que vibram) não têm «Testar»; e «O que o controle sente» é a fileira de chaves dos canais, cada uma com a trilha.
