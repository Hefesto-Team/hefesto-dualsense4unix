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

## 10-perfis.html
- **16/10/2026** — a coluna «Ajuste próprio» ganha os glifos da ativação dos botões e da curva dos analógicos, e o vão entre as seções desce de 6 px para 5 px para as dez caberem na célula. Espera o olho dela na sessão dos desenhos. Enquanto isso, o produto continua com as oito seções de hoje na coluna (`perfis_web.SECOES_ESPERANDO_A_SESSAO_DELA`), e esta aba fica sem o contrato do teclado da base comum e sem a alça da divisa pelas setas.

## 05-vibracao.html
- **18/10/2026** — a «Força da vibração» perde os três botões (Economia, Padrão, Máximo) e fica só o trilho de 0 a 100%, de 5 em 5, com o ícone do DualSense; a linha desce de 79 px para 36 px e o desenho do controle ganha o espaço (r3b-05-12). Espera o olho dela na sessão dos desenhos. Enquanto isso, o produto continua com os três degraus e o teto de 150% (`degraus_da_forca`), e a intensidade que sai do firmware (A-INTENSIDADE-DA-VIBRACAO-E-DO-GATILHO-SAI-DO-FIRMWARE-COMO-NO-PS5-01) é a segunda passagem.
