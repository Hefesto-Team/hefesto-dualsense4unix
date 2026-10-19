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
- **18/10/2026** — a aba ganha a linha «Intensidade do gatilho» entre o estilo de jogo e os efeitos: um trilho de 0 a 200%, de 5 em 5, por controle, no formato do trilho da 05, e o travessão nas vagas sem controle; ela multiplica a força do efeito que o estilo escolheu, e o L2/R2 do estilo fica como está (r3b-03-15). Para a grade caber sem rolagem em 940 px, o respiro apertado da grade e da área de criar passa a valer até 830 px de altura (era até 780). O trilho só pinta (`data-hef`): o gesto de gravar espera o produto (A-INTENSIDADE-DA-VIBRACAO-E-DO-GATILHO-SAI-DO-FIRMWARE-COMO-NO-PS5-01, segunda passagem). Espera o olho dela na sessão dos desenhos. Enquanto isso, o produto não tem a linha.
- **20/10/2026** — os efeitos por família e a chave «Avançado» (OS-EFEITOS-APARECEM-POR-FAMILIA-NAS-ABAS-03-04-E-05-01) e o topo que some com o serviço parado chegaram ao publicado à mão, por merge de três vias; a linha «Intensidade do gatilho» e o respiro até 830 px seguem só no desenho.

## 05-vibracao.html
- **18/10/2026** — a «Força da vibração» perde os três botões (Economia, Padrão, Máximo) e fica só o trilho de 0 a 200%, de 5 em 5, com o ícone do DualSense; a linha desce de 79 px para 36 px e o desenho do controle ganha o espaço (r3b-05-12). O controle não tem nível de 150%: de 0 a 100% o trilho vai virar o byte do firmware e acima de 100% o multiplicador do motor, tudo na segunda passagem (A-INTENSIDADE-DA-VIBRACAO-E-DO-GATILHO-SAI-DO-FIRMWARE-COMO-NO-PS5-01). Espera o olho dela na sessão dos desenhos. Enquanto isso, o produto continua com os três degraus, o Máximo em 150% (`degraus_da_forca`), e o trilho até 200%.
- **20/10/2026** — «Padrão dos motores», a háptica com Eco, Grão e Motor de época, e o topo que some com o serviço parado chegaram ao publicado à mão; a Força sem os três degraus segue só no desenho.
