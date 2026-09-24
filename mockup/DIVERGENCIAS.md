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
- **24/09/2026** — A-MIRA-NA-NAVEGACAO-01, esperando a sessão dela. O chip
  «Mira Virtual» (no Nativo) e o «Nativo» do microfone (no BT) passam a avisar
  o leitor de tela quando ficam cinza (`aria-disabled`); o aceso de cada um
  desceu para um invólucro sem caixa, e nenhum pixel muda (medido contra a
  publicada, número a número). A legenda ganha três itens de 24/09. Enquanto
  ela não publicar, o produto continua cinza só para quem enxerga; a dica do
  Giroscópio com o cursor, o «fluindo» que some com o Giroscópio desligado e a
  cor no Nativo já valem na publicada, porque quem os pinta é o pacote.

## 04-iluminacao.html
- **24/09/2026** — A-MIRA-NA-NAVEGACAO-01, esperando a sessão dela. A dica do
  «Jogador» troca «Um jogo em co-op pode mandar o próprio número por cima.»
  por «O número é do Hefesto: se um jogo o trocar, ele volta em até um
  segundo.» (a STEAM-NO-FISICO-01 derrubou o fato). Enquanto ela não
  publicar, a dica da publicada diz a frase velha; a tira em cor no Nativo já
  vale na publicada, porque quem a pinta é o pacote, e a bancada parada não
  tem cena de Nativo.

## 05-vibracao.html
- **24/09/2026** — AS-FRASES-QUE-A-BANCADA-ACHOU-01, esperando quem coordena
  publicar (delegação dela de 24/09). O «?» do «Testar agora» deixa de
  prometer meio segundo: desde 07/09 o Testar fica ligado até o Parar, segue
  as barras ao vivo, e o de outro controle encerra este
  (`a05_vibracao.testar`, `_EM_TESTE`). Só o texto da dica muda; nada sai do
  lugar.

## 08-conexoes.html
- **24/09/2026** — AS-FRASES-QUE-A-BANCADA-ACHOU-01, esperando quem coordena
  publicar. A palavra do transporte vira USB/BT (decisão dela de 21/09, a I9
  revogada) em três frases da Gestão de Controles: a contagem («2 controles •
  1 USB • 1 BT»; o transporte sem controle some, como no canto de cima desde
  17/09), a linha do Microfone («pelo USB • Placa do controle» / «pelo BT •
  Pela ponte») com a dica dela, e o «?» do Ligado/Desligado. A contagem, a
  linha e a dica do microfone são pintadas a cada tique pelos donos
  (`gui.aba_conexoes.texto_da_contagem`, `a08_conexoes.caminho_do_microfone`
  e `dica_do_microfone`): o produto diz USB/BT desde o primeiro tique, e o que
  espera o `--publicar` é o primeiro quadro e o «?» do microfone.
