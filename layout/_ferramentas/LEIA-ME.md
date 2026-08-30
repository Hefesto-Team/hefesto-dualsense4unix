# As ferramentas do mockup — por que elas existem

**27/08/2026.** Os dez arquivos `NN-*.html` desta pasta NÃO se editam à mão: eles
são **gerados** por `aba0N.py`, e conferidos por `regua.py`.

## O que cada uma faz

- **`monta.py`** — o montador. Pega o esqueleto validado da `01-jogar.html`
  (cabeçalho, fita, tira, rodapé, `<style>`) e injeta o miolo da aba. Traz também
  `svg()` (o DualSense de `assets/control-svg/`, com colorway, player e lightbar)
  e `glifo()` (os 19 de `assets/glyphs/`, os mesmos da aba Status).
- **`abaNN.py`** — uma por aba. Só o miolo e o CSS próprio.
- **`regua.py`** — mede as caixas REAIS no Chrome e reprova o que não bate com a
  Jogar. Rode: `python3 regua.py 04-iluminacao.html`

## As duas cicatrizes desta pasta

**1. A régua nasceu FALSA.** A primeira versão comparava cada aba *consigo
mesma* — e por isso era cega numa aba de um quadro só: não havia com o que
comparar. Passou verde numa mordida inteira. A cura foi ancorá-la de fora, na
Jogar, que é a única aba aprovada. **Toda régua nova aqui leva mordida antes de
ser acreditada.**

**2. `min-height` não encolhe.** A escala de alturas usou `min-height` primeiro,
e os botões de 37 e 38 px continuaram 37 e 38 com a régua verde em tudo o mais.
É `height`, e é por isso.

## A escala, e por que ela existe

Havia **quatro** alturas de botão na mesma janela (31 / 35 / 37 / 38 px). Nenhuma
errada sozinha; juntas, é o que fazia a janela parecer montada por pessoas
diferentes. Os tokens estão no `<style>` do esqueleto: `--h-escolha` 36px,
`--h-acao` 34px, `--gap` 14px, `--pad-quadro` 14px, `--rot` 92px.

## O rótulo de um controle

Sempre nesta ordem, decisão dela de 26/08: **marca • player • plástico • transporte**.
Completa (`Sony • Player 1 • Cosmic Red • USB`) onde há espaço; encurtada
(`P1 • Cosmic Red • USB`) nos chips da fita e na Vibração.
