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

## 05-vibracao.html
- **28/09/2026** — A-TELA-PERGUNTA-AO-DONO-01: o «Testar» da coluna que está
  vibrando acende (`data-campo="em-teste"`, com o `aria-pressed`), e quem
  responde é o `em_teste()` do dono; o «Parar» apaga. Espera a sessão dos
  desenhos. Até publicar, o pacote já manda o `em-teste` e a página publicada
  não tem onde pintá-lo: o botão fica como é hoje, sem aceso.

## 10-perfis.html
- **28/09/2026** — a coluna do `movimento` passa a se chamar «comandos virtuais» na dica do cabeçalho: ela guarda a Mira Virtual, a Inclinação e o Cursor ou os Botões do touchpad (NO-MODO-XBOX-TUDO-FUNCIONA-01). Até publicar, a dica da tela dela diz «mira virtual», e a coluna acende igual com qualquer um dos três.

## calibrar-sensores.html
- **28/09/2026** — a linha da Mira Virtual diz também o que vale para a Inclinação e para o Cursor do touchpad (NO-MODO-XBOX-TUDO-FUNCIONA-01). Até publicar, a Calibrar dela fala só da Mira Virtual, e os deslizantes já valem para os três.
