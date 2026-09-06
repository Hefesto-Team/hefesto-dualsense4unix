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

- **05/09/2026** — **UMA LINHA DE COMENTÁRIO CSS, sem um pixel de diferença.**
  O gerador `aba02.py` teve um endereço de linha remedido (o alvo `classe` do
  `escrever()` mudou de lugar quando o piloto ganhou a piscada da `03-Q4`), e o
  comentário que o cita é EMITIDO dentro do `<style>` da página. A bancada foi
  regerada; o produto não.

  **Por que não publiquei:** publicar é ato dela, e a regra existe porque
  publicar troca o que ela abre. Aqui a mudança é provadamente invisível — as
  dez fotos de `docs/usage/assets/aba-NN-*.png` saíram byte a byte idênticas
  antes desta regeração —, mas *"é só um comentário"* é exatamente o argumento
  com que uma exceção vira hábito.

  **O que ela vê HOJE, até publicar:** exatamente a mesma aba Controles de
  ontem. A página que o produto renderiza continua com o endereço antigo dentro
  de um comentário do `<style>` — nenhum clique, nenhuma frase e nenhum pixel
  dependem dele. O custo da espera é zero, e esta é a primeira declaração desta
  lista de que isso se pode dizer com medição por trás.

  **O que fecha:** o `--publicar 02` da próxima vez que ela aprovar a aba. Nada
  espera por isto — nenhuma sprint depende desta linha.

## 09-sistema.html

- **06/09/2026** — **UMA LINHA, e os dois pixels que ela mudam são PALAVRA
  DELA** (`ONDA5-09-01`, a 09-Q1 e a 09-Q3). O botão do `daemon.reload` volta a
  se chamar **"Atualizar"** e a espera a dizer **"Atualizando…"**; a dica dele
  passa a nomear o que foi MEDIDO do outro lado do clique, e não o que se
  supunha.

  ```
  linha 1245 · bancada  Atualizar          · data-hef-em-voo="Atualizando…"
  linha 1245 · produto  Reaplicar ajustes  · data-hef-em-voo="Reaplicando…"
  ```

  **É uma REVERSÃO, e a reversão é dela.** Em 04/09 o PO decidiu rebatizar o
  botão pela metade cara; em 05/09 ela leu a mesma pergunta e escolheu o
  contrário: *"Segue fazendo os dois. Com mesmo nome"*. O que estava no produto
  desde `a45b7799` é a recomendação que perdeu.

  **A dica mudou de metade, e por medição:** ela prometia *"reaplicar a
  configuração"*, e com `config_overrides` vazio isso **não acontece** —
  `daemon/lifecycle.py:1353` e `:1361` comparam `old` com `new` e nunca
  disparam. O que acontece são duas coisas: o serviço religa o leitor dos
  atalhos do controle (`lifecycle.py:1351-1352`) e reescreve os arquivos de
  ambiente da Steam (`ipc_handlers.py:5472`). A dica passou a dizer essas duas.

  **Por que não publiquei:** publicar é ato dela, e aqui a mudança é VISÍVEL —
  duas palavras que ela lê no botão. A `PROVA-DE-TELA-01` é a regra mais velha
  desta casa, e ela vale exatamente para o caso em que a mudança é a palavra
  dela: quem confere que a palavra chegou certa é ela, olhando.

  **O que ela vê HOJE, até publicar:** a aba Sistema de ontem, com o botão
  ainda dizendo "Reaplicar ajustes". Nada quebra — os quatro botões da coluna,
  os três cinzas e o `data-hef-em-voo` continuam inteiros nos dois lados.

  **O que fecha:** `scripts/check_o_desenho_aprovado.py --publicar 09`, depois
  do olho dela.
