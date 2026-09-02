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

## 08-conexoes.html
- **02/09/2026** — **dois endereços novos no Check-up, e nenhum pixel mudou.**
  O desenho é o mesmo que ela aprovou; o que a bancada ganhou foram dois
  `data-campo` em elementos que já estavam lá, para que o produto pare de
  mentir neles:

  | onde | o que era | o que passa a escrever |
  | --- | --- | --- |
  | o `?` de cada uma das cinco linhas | a explicação do MOCKUP, ao lado do achado DELA | `secao_exame._dica_do_item` — o que a linha significa, a medição desta rodada e a cura |
  | o `Examinado há 3 minutos` do topo | a frase fixa desde que o mockup nasceu | `secao_exame.frase_de_quando`, com a idade do último **Examinar Portas** |

  Fotografado nesta bancada, com dois controles na mesa: a linha 1 dizia
  **"Economia de energia desligada"** e o `?` ao lado explicava *"as entradas
  em uso entregam 500 mA ou mais"* — a medição de OUTRO achado. Nas duas
  posições que o exame não preencheu, o texto vinha `—` e o `?` continuava
  contando os quatro rádios vizinhos do desenho.

  **O pacote já emite os dois** (`achado-explica` e `examinado`): no dia em que
  ela publicar, a tela nasce certa; até lá o piloto não acha o endereço e
  escreve zero — nada muda no produto que ela usa.
