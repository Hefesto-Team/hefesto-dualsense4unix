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

## 07-lancadores.html
- **17/10/2026** — a aba vira «Experimental» no desenho do todo: o quadro das extensões (Kyty e Lovense, com chave, engrenagem e «⋮») e as filas de lançador com três botões no lugar dos cartões, mais as janelas da Lovense (três jeitos de ligar), do Kyty, dos acessórios (a coluna «Agora», os toques, os jogos e a força no deslizante, com a porta certa de cada jogo com o kit), do servidor Buttplug, de configurar o lançador e dos impedimentos. Espera o olho dela na sessão dos desenhos. Enquanto isso, o produto continua com os cartões e o pacote `a07_lancadores` pinta a página publicada.

## 10-perfis.html
- **16/10/2026** — a coluna «Ajuste próprio» ganha os glifos da ativação dos botões e da curva dos analógicos, e o vão entre as seções desce de 6 px para 5 px para as dez caberem na célula. Espera o olho dela na sessão dos desenhos. Enquanto isso, o produto continua com as oito seções de hoje na coluna (`perfis_web.SECOES_ESPERANDO_A_SESSAO_DELA`), e esta aba fica sem o contrato do teclado da base comum e sem a alça da divisa pelas setas.

## 03-gatilhos.html
- **18/10/2026** — a aba ganha a linha «Intensidade do gatilho» entre o estilo de jogo e os efeitos: um trilho de 0 a 200%, de 5 em 5, por controle, no formato do trilho da 05, e o travessão nas vagas sem controle; ela multiplica a força do efeito que o estilo escolheu, e o L2/R2 do estilo fica como está (r3b-03-15). Para a grade caber sem rolagem em 940 px, o respiro sobe de ≤780 para ≤830 px de altura. O trilho só pinta (`data-hef`): o gesto de gravar espera o produto (A-INTENSIDADE-DA-VIBRACAO-E-DO-GATILHO-SAI-DO-FIRMWARE-COMO-NO-PS5-01, segunda passagem). Espera o olho dela na sessão dos desenhos. Enquanto isso, o produto não tem a linha.

## 05-vibracao.html
- **18/10/2026** — a «Força da vibração» perde os três botões (Economia, Padrão, Máximo) e fica só o trilho de 0 a 200%, de 5 em 5, com o ícone do DualSense; a linha desce de 79 px para 36 px e o desenho do controle ganha o espaço (r3b-05-12). O controle não tem nível de 150%: de 0 a 100% o trilho vai virar o byte do firmware e acima de 100% o multiplicador do motor, tudo na segunda passagem (A-INTENSIDADE-DA-VIBRACAO-E-DO-GATILHO-SAI-DO-FIRMWARE-COMO-NO-PS5-01). Espera o olho dela na sessão dos desenhos. Enquanto isso, o produto continua com os três degraus, o Máximo em 150% (`degraus_da_forca`), e o trilho até 200%.
