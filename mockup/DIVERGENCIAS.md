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

## mapa-das-portas.html
- **04/10/2026** — o painel do aparelho que abre ao clicar nele (nome, tipo, chave Extensor, o que a
  máquina vê, Identificar, Voltar ao automático), o arrastar para trocar de entrada, o aviso de uma
  linha do «Examinar» e a fileira «Sem Lugar»: o produto recebe com o `--publicar mapa-das-portas` do
  fecho do conjunto «Conexões 2». Até publicar, a tela dela segue a de hoje (o extensor como resposta
  de «O que tem na entrada») e o pacote já atende os dois gestos; a integração não é instalada antes.
- **05/10/2026** — o «Descobrir a faixa» no painel do receptor 2.4G (um link para a faixa dele na aba
  Conexões): o produto recebe com o mesmo `--publicar mapa-das-portas`.
- **05/10/2026** — «A faixa dele» no painel do aparelho (os 79 canais, pintado o bom, vazio o perdido
  com a marca de quem o tomou, e «perde para…» ou «briga com…», do desenho 2), pela mesma conta da aba
  Conexões; o «Descobrir a faixa» passa a andar sozinho pelo censo, sem o «já tirei»: o produto recebe
  com o mesmo `--publicar mapa-das-portas`.
