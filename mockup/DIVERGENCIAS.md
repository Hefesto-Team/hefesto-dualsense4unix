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
- **03/09/2026** — os rótulos dos modos e as curvas prontas deixaram de ser
  digitados no gerador e passaram a vir do produto
  (`app/actions/trigger_specs.PRESETS` e
  `profiles/trigger_presets.FEEDBACK_POSITION_LABELS`). **O desenho mudou em 25
  lugares, e nenhum deles é opinião nova:** os oito `<select>` de modo trocam
  `Arco de flecha` por `Arco de flecha (Bow)` e `Disparo` por `Disparo
  (Weapon)` — as duas desambiguações que **ela** pediu em 07/08/2026 e que esta
  página nunca acompanhou —, e os oito de "Efeito pronto" ganham `Linear
  médio`, a sexta curva de feedback, que existe no motor e que a janela GTK já
  oferece. A vigésima quinta é a legenda do rodapé, que nomeia o modo do R2.
- **O QUE ELA VÊ HOJE, enquanto a aba espera o OK dela — e não é meia página.**
  Medido no DOM vivo em 03/09/2026, com um controle na mesa e a página
  publicada AINDA na versão antiga: os oito `<select>` mostram os rótulos
  certos e as seis curvas, porque o pacote `a03_gatilhos` monta as duas listas
  a cada tique e as pousa por cima do que o arquivo trouxe. **Antes: 16
  rótulos divergentes + 8 curvas faltando = 24. Depois: 0.** Até publicar, o
  arquivo e a tela discordam de propósito — e é a TELA que está certa, porque
  é ela que pergunta ao produto. O que a publicação muda é uma pintura a menos
  por sessão, não o que ela lê.
- **A largura não muda:** `Arco de flecha (Bow)` tem 20 caracteres, o mesmo que
  `Arma semi-automática` e `Vibração por posição`, que já estavam na lista. A
  coluna mediu 453px de 477 depois da mudança — os mesmos 24px de folga de
  antes.
## 04-iluminacao.html
- **03/09/2026** — as duas cores das lâmpadas (`--led-apagado` e `--led-aceso`)
  passaram a ser declaradas em `.luz-grade`, o escopo que o DESENHO alcança.
  Elas moravam só em `.luzinhas`, que é o indicador PEQUENO da célula LEDs, e
  `.luzinhas` é uma folha da árvore — as cinco lâmpadas do desenho grande não
  acendiam **nenhuma**, medido no DOM vivo. É CSS, e só: nenhuma caixa nova,
  nenhum texto novo, nenhum botão. O que muda na tela é a lâmpada do número
  aparecer, que é o que o `title` da moldura já prometia.
  **O que ela vê HOJE, na página publicada, enquanto isto espera o OK:** a aba
  Iluminação está INTEIRA — as cinco lâmpadas do desenho grande já acendem o
  número vivo e a barra já mostra a luz do aparelho. A metade viva desta cura
  (`a04_iluminacao.folha_da_luz`) não espera publicação nenhuma: ela declara o
  par de cores e escreve as regras dentro do `<style id="plastico-vivo">`, que o
  produto de hoje JÁ tem. O que a publicação acrescenta é a mesma declaração na
  folha estática — o que faz a bancada se ver sozinha, sem daemon, no navegador.
  Nenhum clique fica morto e nada some da tela até lá.
## 08-conexoes.html
- **03/09/2026** — a linha fechada da Gestão de Controles e a confissão do mapa
  ganharam ENDEREÇO, para o produto poder reescrever o que era do desenho:
  `mic-existe` no `<b>` do resumo, `mic-caminho`, `luz-trava` (a classe
  `apagado` do botão da luz) e os três da `.mm-conf-linha`. Nenhum texto novo e
  nenhuma caixa nova — o que muda é quem escreve.
  **Até publicar, a tela dela continua com os quatro valores do desenho:**
  "Microfone **Ligado**" (a ponte deste controle está DESLIGADA no
  `maquina.json`), o caminho e a trava do botão da luz decididos pela posição no
  mockup, e a confissão do mapa dizendo "**três coisas**" onde a bancada dela
  tem uma. O pacote já emite os cinco campos e o `achar()` do piloto não os
  encontra — escreve zero, sem custo e sem estrago.
