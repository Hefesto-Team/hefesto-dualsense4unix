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
- **24/09/2026** — O-MODO-FREESTYLE-02. O motor não espera mais: o
  «Personalizado» virou «Freestyle» no produto (a migração do disco, com a
  cópia no histórico), e o boot o restaura quando a sessão está vazia. O desenho
  muda a legenda (o «Personalizado» virou «Freestyle», e fora do jogo o topo diz
  Freestyle) e a dica do botão («Desligue», não «Desmarque»). Enquanto ela não
  publicar, o produto mostra a palavra e a dica de ontem na tela e o topo já diz
  «Freestyle», que é o nome do perfil no disco. As réguas dos 17 px medem a
  publicada e o desenho, e a regra de altura sai da palavra da página: no
  commit do `--publicar 01`, só `test_a_palavra_de_ontem_tem_prazo` reprova, e a
  mensagem dela lista os ramos que saem junto.
