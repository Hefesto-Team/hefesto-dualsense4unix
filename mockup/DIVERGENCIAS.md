# As abas em trabalho no desenho

Toda seção aqui é uma aba cujo **desenho já andou** e cujo **produto ainda não
recebeu** — porque ainda não recebeu o OK. O
`scripts/check_o_desenho_aprovado.py` lê este arquivo; a aba que não estiver
aqui, ele reprova.

**A direção é `mockup/` → `layout/`.** O `mockup/` é o desenho de hoje; o produto
só recebe quando a aba é aprovada **inteira**, que é a escolha de
31/08/2026 — nem a cada ponto, nem só no fim da lista.

**Formato** — uma seção por página, com data e o ponto que está aberto:

```
## 01-jogar.html
- **DD/MM/AAAA** — o ponto da lista que está aberto na aba.
```

Quando a aba for aprovada, `--publicar NN` leva o desenho ao produto e **apaga a
seção daqui**: a aba deixou de estar em trabalho.

---

## 01-jogar.html
- **01/11/2026** — O-MODO-QUE-A-EXTENSAO-PEDE-FICA-AO-LADO-DO-AUTOMATICO-01: a vaga do modo da extensão ao lado do
  Modo automático na seção dos controles; vazia sem extensão ligada. Até publicar, a página de hoje não tem a
  vaga: o botão da extensão não aparece e o Modo automático segue sozinho.

## 03-gatilhos.html
- **01/11/2026** — O-MODO-QUE-A-EXTENSAO-PEDE-FICA-AO-LADO-DO-AUTOMATICO-01: a vaga do modo da extensão ao lado do
  Modo automático; vazia sem extensão ligada. Até publicar, a página de hoje não tem a vaga: o botão da
  extensão não aparece e o Modo automático segue sozinho.

## 04-iluminacao.html
- **01/11/2026** — O-MODO-QUE-A-EXTENSAO-PEDE-FICA-AO-LADO-DO-AUTOMATICO-01: a vaga do modo da extensão ao lado do
  Modo automático; vazia sem extensão ligada. Até publicar, a página de hoje não tem a vaga: o botão da
  extensão não aparece e o Modo automático segue sozinho.

## 05-vibracao.html
- **01/11/2026** — O-MODO-QUE-A-EXTENSAO-PEDE-FICA-AO-LADO-DO-AUTOMATICO-01: a vaga do modo da extensão ao lado do
  Modo automático; vazia sem extensão ligada. Até publicar, a página de hoje não tem a vaga: o botão da
  extensão não aparece e o Modo automático segue sozinho.

## 10-perfis.html
- **01/11/2026** — O-MODO-QUE-A-EXTENSAO-PEDE-FICA-AO-LADO-DO-AUTOMATICO-01: o par do modo do perfil inteiro no
  editor (Modo automático e a vaga da extensão). Até publicar, o editor de hoje não tem o par e o pacote deixa
  `editor.modos-*` em `ESPERANDO_A_PUBLICACAO`; no `--publicar`, os dois saem dali.
