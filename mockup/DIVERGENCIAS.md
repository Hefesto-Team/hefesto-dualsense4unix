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
  **O motor espera junto:** o Personalizado continua no produto enquanto
  `loader.O_PERSONALIZADO_ESPERA_A_SESSAO_DELA` for `True`, porque sem ele não
  há perfil valendo do boot ao primeiro jogo — o topo diz «—» e as abas 02 a 08
  recusam o ajuste. Quem publicar decide essa linha com a resposta dela no mesmo
  commit (`test_o_modo_freestyle.test_a_saida_espera_a_sessao_dela`).

## 02-controles.html
- **24/09/2026** — O-TERCEIRO-NOME-DELA-01, esperando a olhada de quem coordena
  (delegação dela de 24/09). A fileira do Alto-falante ganha o quarto botão,
  «Tudo no Controle e Nada no PC» (`data-rota="pc"`, o gesto `rota` de sempre:
  rota 3 mais a saída padrão do sistema neste controle), e os três de antes
  trocam «TV» por «PC»: «Efeitos do Jogo no Controle, Áudio do PC no PC»,
  «Efeitos do Jogo e Áudio do PC no Controle» e «Tudo no PC e Nada no
  Controle». Os dois de baixo dividem uma linha (classe `quatro` e `.par`), e
  o rótulo do Alto-falante vira `rot-linha` como o do Microfone. Medido no
  Chrome: o cartão fica em 327 px a 1120 e a 1180 e em 320 a 1440 (teto 328).
  O «?» do Microfone passa a dizer que o 🎙 liga o retorno. Enquanto a 02 não
  for publicada, o produto mostra os três botões de ontem com «TV», e o `pc`
  aceso (byte 3 com a saída padrão no controle) não acende botão nenhum, como
  desde 20/09. As réguas que leem o publicado (`test_o_terceiro_nome_dela`,
  `test_aba02_os_acesos_sao_leitura_e_nao_desenho`) perguntam a esta seção e
  passam a cobrar o quarto sozinhas quando o `--publicar 02` a apagar. **Quem
  publicar acrescenta, no mesmo commit, o passo `.rota button[data-rota="pc"]`
  ao `controles_vivos.ROTEIRO_DA_PROVA_DE_GESTO`** (antes do `jogo`, que
  devolve a saída): hoje a régua do roteiro lê o publicado e reprovaria o
  passo antes da hora.
