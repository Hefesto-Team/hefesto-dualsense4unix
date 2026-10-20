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
- **20/10/2026** — espera só o `--publicar 03`: a linha «Intensidade do gatilho» (o trilho de 0 a 200%, de 5 em 5, por controle) e o respiro até 830 px estão no desenho, e o produto já grava a escala no perfil e a aplica (A-INTENSIDADE-DA-VIBRACAO-E-DO-GATILHO-SAI-DO-FIRMWARE-COMO-NO-PS5-01, segunda passagem). Enquanto isso, a página publicada não tem a linha, e o gatilho de cada controle segue a 100%.

## 05-vibracao.html
- **20/10/2026** — espera só o `--publicar 05`: a «Força da vibração» sem os três botões, só o trilho de 0 a 200%, de 5 em 5, está no desenho, e o pacote já não pinta o degrau; de 0 a 100% a força sai pelo byte do firmware, e acima de 100% pelo multiplicador do motor (A-INTENSIDADE-DA-VIBRACAO-E-DO-GATILHO-SAI-DO-FIRMWARE-COMO-NO-PS5-01, segunda passagem). Enquanto isso, a página publicada ainda mostra os três botões, que gravam pelo gesto de sempre, ao lado do trilho.
