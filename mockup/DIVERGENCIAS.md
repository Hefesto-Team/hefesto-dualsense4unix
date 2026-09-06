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

## 10-perfis.html

- **06/09/2026** — **UMA OPÇÃO A MAIS no seletor "Funciona em": "Jogo (pela
  janela)"**, a sexta forma que a ONDA5-10-01 (decisão 10-Q2 dela) fez o produto
  saber guardar. É a regra que o botão "Detectar" passa a gravar quando o jogo
  **não é da Steam** — uma classe de janela só.

  **Por que não publiquei:** publicar é ato dela. Aqui a mudança é VISÍVEL (uma
  linha nova no `<select>`), então nem a régua do que-se-vê a absolveria — e
  não deveria.

  **O que ela vê HOJE, até publicar:** a aba Perfis de ontem, com cinco opções
  no seletor. **E o custo da espera NÃO é zero — medido no WebKit vivo** por
  `scripts/ensaios/o_detectar_grava_o_jogo_de_fora_da_steam.py`, com o MESMO
  perfil no disco (`window_class: ["GrimFandango"]`) pintado nas duas páginas:

  | | opções do seletor | a pintura escreveu | o campo mostrou |
  | --- | --- | --- | --- |
  | **bancada** | 6 (com "Jogo (pela janela)") | 3 de 3 | `Jogo (pela janela)` |
  | **publicado** | 5 | **2 de 3** | **`Jogo`** |

  O `escrever()` do piloto só escreve num `<select>` quando alguma opção CASA
  (`hefesto_vivo.py`, `if(!tem) return 0;`), então o campo **fica com o "Jogo"
  que o desenho cravou** — e o cadeado NÃO acende, porque o produto sabe
  descrever a regra. É o defeito que o `aba10.opts` documenta, pelo avesso: a
  tela afirma "Jogo" sobre um perfil que casa por janela, sem nada ao lado
  dizendo que ela não sabe. O `Detectar` **grava certo no disco** nos dois
  casos; o que espera pelo `--publicar 10` é o rótulo.

  **O que fecha:** `scripts/check_o_desenho_aprovado.py --publicar 10`, no OK
  dela da aba. Nada mais espera por isto.

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
