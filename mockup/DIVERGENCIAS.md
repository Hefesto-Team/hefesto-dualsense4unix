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

## 06-navegacao.html
- **03/09/2026** — a aba ganhou **as três leituras vivas que a GTK tem e ela
  não**, e todas as frases são do produto (nada foi escrito aqui):
  - o **"Status do Modo"** perdeu o `<input type="checkbox" checked>` e a
    palavra de `content:` de CSS. Ele nasce em `—` e passa a ser pintado pelo
    daemon (classe `ligado` + nó de texto). **Era a maior mentira desta aba:**
    a tela dizia *Ligado* com `mouse_emulation.enabled=false`, e clicar virava
    a caixa no DOM mesmo quando o gesto RECUSAVA;
  - **três linhas de estado** sob as opções de ativação, na mesma fileira: *por
    que o cursor não anda* (`mouse_actions`), *o teclado está ligado e calado?*
    (`emulation_actions.descrever_teclado_emulado`) e *há teclado na tela nesta
    máquina?* (`input_actions.frase_do_teclado_na_tela`). A dica do quadro
    Navegação já citava "a linha de estado abaixo" desde 27/08, para uma linha
    que não existia. Cada uma some quando não há o que dizer.

  **O que ela vê de diferente depois de publicar:** o interruptor pode passar a
  dizer *Desligado* (é o que o Hefesto dela responder), e nascem uma ou duas
  frases curtas entre as opções de ativação e a fileira dos botões. Nada mais
  mudou de lugar — medido na foto: a fileira dos botões continua dentro da
  janela.

  **O QUE O PRODUTO FAZ ATÉ ELA PUBLICAR, e é nada — de propósito:** a página
  que o `WebView` renderiza hoje não tem os quatro endereços novos, e o
  `escrever()` do piloto não acha elemento nenhum para eles. Logo **a tela dela
  hoje continua exatamente como estava**, inclusive dizendo *Ligado* sempre —
  a mentira só morre na publicação. Nenhum clique muda de comportamento por
  causa disso: o desenho velho não tem `data-campo` novo, e valor emitido sem
  destino é descartado sem erro. **O que JÁ chega a ela sem publicar** são as
  duas curas que vivem só no Python: a recusa do daemon passa a dizer o motivo
  no cartão (antes voltava como sucesso), e o segundo clique no `−`/`+` das
  velocidades dentro do mesmo tique passa a andar.

