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

## 06-navegacao.html
- **14/09/2026** — a sexta linha de gesto: **PS + L3 · Próxima Máscara**, ao lado
  do PS + R3 (Próximo Modo). O lugar é escolha dela: *"Tem que ficar na aba
  navegAção."* <!-- noqa-acento: citação literal dela --> Junto, a frase da
  legenda passou de «os cinco gestos» para «os seis gestos». Esperando o olho
  dela na aba inteira para `--publicar 06`.
- **Enquanto não publica:** a aba Navegação instalada mostra cinco linhas e não
  cita o PS + L3 em lugar nenhum. O gesto FUNCIONA no controle desde a instalação
  de 14/09 — quem não o lista é a tela. Até publicar, quem quiser conferir o
  combo lê `docs/usage/hotkeys.md`.
