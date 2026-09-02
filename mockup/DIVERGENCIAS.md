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

## 03-gatilhos.html

- **02/09/2026** — **duas correções de PINTURA, nenhuma de desenho.** A aba
  continua com a cena que ela aprovou em 27/08 (*"aba gatilhos perfeita"*):
  mesmos quatro controles, mesmos rótulos, mesma altura de coluna (453px de
  477). O que mudou não se vê parada — vê-se quando o produto pinta.

  1. **As 11 barras de ajuste ganharam `data-hef-alvo="largura"`.** Sem ele o
     piloto escreve o NÚMERO dentro do trilho de 5px em vez de encompridar a
     barra — e a barra fica na largura do mockup. Fotografado em 02/09 com o
     perfil `meu_perfil` (gatilho `Off` nos dois lados): o pacote já corrigia o
     nome e o valor para `—`, e as quatro barras do P1 continuavam em 78%, 44%,
     25% e 90%. É o mesmo defeito que o `data-hef-alvo="valor"` dos `<select>`
     curou em 01/09, no elemento vizinho.

     **O portão não vê esta linha**: `data-hef-alvo` está na lista de
     `INVISIVEIS` do `check_o_desenho_aprovado.py` — ela não muda um pixel do
     que ela aprovou.

  2. **O lugar vazio deixou de aceitar clique** (CSS, e é o que o portão vê).
     `.ctrl[data-conectado="nao"] select` e `.btn` ganharam
     `pointer-events:none`. Fotografado no mesmo dia: as colunas P3 e P4 diziam
     `Desconectado` no cabeçalho e traziam os dois campos de escolha e o
     "Guardar esse efeito" ABERTOS. O seletor pende do `data-conectado`, que o
     piloto reescreve a cada tique — logo a trava acompanha a mesa DELA, e um
     controle ligado no P3 devolve a coluna sem tocar em CSS.

  **Publicar é ato dela.** Enquanto não publicar, o produto pinta o nome e o
  valor certos e deixa as barras na largura do desenho — o estado está descrito
  em `pacotes/a03_gatilhos._casas_e_barras`, que LÊ a página publicada e volta a
  pintar a largura sozinho no dia em que ela receber o atributo.
