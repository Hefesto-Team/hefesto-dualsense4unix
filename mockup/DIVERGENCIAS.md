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
