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

## 07-lancadores.html
- **25/11/2026** — a barra de cada aparelho (`aparelhos_acoes.barra`) na linha do nome do cartão, entre a bateria e a chave, com o rótulo e o degrau ao lado (`16/20`); o cartão de exemplo da janela «Minha extensão» mostra a barra no «Teto». Enquanto a 07 não se publica, o produto desenha a barra no cartão de cada aparelho pelo mesmo `aparelhos_geridos_html`, e arrastar e soltar já chegam à extensão; a página de agora ainda não traz o estilo da barra, e a barra aparece com o deslizante e o degrau na largura de fábrica, sem o rótulo encolhido. Origem: D-2511-O-TETO-DA-EXTENSAO-E-DE-CADA-BRINQUEDO.

## janela-do-modo-imersao.html
- **16/11/2026** — o desenho da janela «Configurar · Modo imersão», gerado pelo `src/hefesto_dualsense4unix/interface/janela_do_imersao.py` com o mesmo `modificacao_miolo_html` do produto, do manifesto 0.5.6 da extensão guardado em `mockup/modo-imersao/`: sem a coluna «Agora», com a faixa do alto (Tocando, Calado com o motivo ou Esperando um jogo, as linhas e as três últimas escritas) e três abas (Sentir, Efeitos e Controles), o «Testar» no pé de cada cartão de efeito, com o veredito, e a marca «Terror». A janela não vira página própria: o produto a desenha pela janela de extensão da 07 (`07-lancadores.html`), e, enquanto a 07 não se publica, abre a janela com a faixa, as três abas, os medidores, as trilhas e o veredito, sem o estilo desses pedaços. O que difere do pedido: as últimas escritas dizem o canal e o plástico, não o nome do efeito (a porta não o anota); sem o botão «Abrir a aba Jogar»; a linha de cada controle não diz USB ou BT (a `controles.lista` não leva o transporte); a «Tensão da cena» é uma linha da faixa; os cartões sem teste na extensão (Clima tenso, Peso da mira, Som no corpo e os Gatilhos que vibram) não têm «Testar»; e «O que o controle sente» é a fileira de chaves dos canais, cada uma com a trilha.
