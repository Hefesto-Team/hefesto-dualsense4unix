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

---

## 05-vibracao.html

- **06/09/2026** — **A NOTA DO TESTAR VOLTOU PARA O `?`** (`ONDA5-05-01`, a
  05-Q2 dela: *"As duas na dica."*). A frase *"Os valores acima ainda passam
  pela intensidade escolhida ali em cima…"* deixou de ser a linha cinza em
  itálico embaixo da grade e voltou para dentro do `?` do **Testar agora**, ao
  lado das duas orações do par. Saíram junto a `.vib-nota` do miolo e a regra
  de CSS que só ela usava.

  **E a dica passou a abrir para a DIREITA, o que é conserto de defeito
  medido:** ela carregava `left:auto;right:22px` — o arranjo das dicas do lado
  direito da página —, e neste `?`, que mora na primeira coluna da grade, isso
  punha **224 dos 330 px da caixa fora da janela**. Medido nos dois motores, a
  1920x1080: Chrome (`interface/olhar.py`) e WebKit (o piloto). Com o padrão da
  casa a caixa vai de x=505 a x=835 dentro de uma janela de 370 a 1550 —
  **sangria zero**.

  **O que ela vê HOJE, até publicar:** a aba Vibração de ontem — a linha cinza
  ainda embaixo da grade, e o `?` do Testar agora ainda cortado pela borda
  esquerda da janela. **O corte é do produto publicado, não desta mudança**:
  medido em `interface/paginas/05-vibracao.html`, a mesma sangria de 224 px já
  existia com as duas orações.

  **O que fecha:** o `--publicar 05` depois do OK dela na aba inteira.
