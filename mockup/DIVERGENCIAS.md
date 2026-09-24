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
- **24/09/2026** — A-MIRA-POR-MOVIMENTO-NA-TELA-01, esperando a sessão dela. O
  cartão de cada controle ganha o chip «Mira Virtual» ao lado de Giroscópio e
  Acelerômetro, nascendo apagado, com a dica dela («Usar os movimentos do
  controle como mira (analógico R), para pessoas com deficiência motora.»). Os
  três dividem a grade: cada um mede 102,3 px e o grupo foi de 212,6 para
  322,9 px; na linha mais apertada da bancada (o P2, a 1120 px) sobram 17,5 px,
  e o nome de plástico mais longo (146 px) ainda cabe. O cartão continua em
  326,63 px (teto 328). Enquanto ela não publicar, o produto não mostra o chip;
  o gesto `mira` e a pintura `mira-ligada` já esperam no pacote da aba.
- **24/09/2026** — A-MIRA-POR-MOVIMENTO-NA-TELA-02, as respostas dela da mesma
  sessão, esperando a próxima. A dica do Giroscópio sai do botão para um
  invólucro sem caixa (`display:contents`, endereço `giro-dica`) e passa a
  dizer «Com a Mira Virtual acesa, o giro deste controle vai ao jogo pelo
  analógico direito.» quando a Mira daquele controle está acesa. O grupo dos
  três chips ganha o endereço `mira-fora`, e no Modo Nativo o chip da Mira fica
  com o cinza da casa (`cursor:not-allowed`) e não grava. Medido no piloto
  oculto: o grupo continua em 320,3 px e o cartão em 326 px — nenhum pixel no
  estado normal. Enquanto ela não publicar, o pacote não emite os dois campos.

## calibrar-sensores.html
- **24/09/2026** — A-MIRA-POR-MOVIMENTO-NA-TELA-01, esperando a sessão dela.
  Embaixo dos cartões, um bloco «Mira Virtual» com uma coluna por controle e
  dois deslizantes em cada: «O quanto um gesto anda» (1 a 12) e «Ignorar tremor
  até» (1 a 60 graus/s). O bloco é próprio (`data-bloco="miras"`), fora do dos
  cartões, que o produto remonta a cada tique. Enquanto ela não publicar, o
  pacote não o remonta nem o pinta (`a11_calibrar_sensores._a_pagina_tem_a_mira`).
- **24/09/2026** — A-MIRA-POR-MOVIMENTO-NA-TELA-02, esperando a próxima sessão
  dela. Cada coluna ganha, embaixo dos dois deslizantes, o «Só enquanto eu
  segurar» (uma lista com «Sempre» de nascença e os dezesseis botões que o
  esquema aceita, sem o PS) e o «Inverter» (dois interruptores, «Esquerda e
  direita» e «Cima e baixo», apagados de nascença). A coluna foi de 127 para
  220 px; na caixa de 1180 × 777 o miolo continua sem rolar com dois controles.

## 10-perfis.html
- **24/09/2026** — A-MIRA-POR-MOVIMENTO-NA-TELA-01, esperando a sessão dela. A
  coluna «Status» (o ajuste próprio de cada controle) ganha a oitava célula, a
  da Mira Virtual, com o glifo do analógico direito, e a dica do cabeçalho passa
  a contar oito. O campo já está no perfil (`ControllerOverrides.movimento`);
  enquanto ela não publicar, o produto distribui sete células por linha e a
  frase da linha conta sete (`perfis_web.SECOES_ESPERANDO_A_SESSAO_DELA`). Quem
  publicar move o `movimento` de lá para `a10_perfis.SECOES_DA_COLUNA` no mesmo
  commit — a régua reprova até isso.

## 01-jogar.html
- **24/09/2026** — O-MODO-FREESTYLE-01, esperando a sessão dela. O botão do
  canto do bloco Modo passa de «Trava o perfil ativo» a «Modo Freestyle» (a
  palavra dela de 23/09), com a letra de 10,5 para 12,5 px e a altura de 17
  para 26 px. A linha do título cresce 9 px e o resto da aba desce junto; a
  página continua sem rolar a 1212x809 e na vista dela (1918x840). O gesto, o
  campo e a pílula verde não mudam. Enquanto ela não publicar, o produto diz a
  palavra de ontem (`a01_jogar.CADEADO_ROTULO_ESPERANDO_A_SESSAO_DELA`); quem
  publicar apaga essa constante e ajusta as duas réguas que medem os 17 px da
  publicada (`test_a_trava_e_a_pilula_dos_sensores`,
  `test_o_cadeado_mora_no_canto_do_bloco`) no mesmo commit.
