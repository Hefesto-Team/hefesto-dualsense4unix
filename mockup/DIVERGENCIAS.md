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
- **03/09/2026** — as duas decisões dela sobre a coluna **Ajuste próprio**:
  - **nº4, as oito dicas das células saíram.** *"Meu Deus melhor nenhuma assim.
    Auto falante é auto falante, gatilho é gatilho."* Eram quatro pares (um
    texto por estado) que repetiam a dica do cabeçalho e ainda re-explicavam o
    que cada peça é. A do CABEÇALHO fica, e é a única.
  - **nº20, o microfone virou o quinto ajuste por controle.** A linha ganhou a
    célula e a dica do cabeçalho passou a dizer *cinco*. O campo
    `ControllerOverrides.mic` ainda não existe no esquema — está declarado em
    `a10_perfis.ESPERANDO_O_ESQUEMA` e a célula fica apagada em todo perfil real
    até ele chegar.

  **O QUE ELA VÊ HOJE, enquanto o produto espera o OK:** a página publicada tem
  QUATRO células por controle, não cinco, e cada uma ainda mostra a dica velha
  ao passar o mouse. **Nada fica pela metade**, e é por construção: o pacote
  distribui a coluna POR NOME de seção (`a10_perfis.SECOES_DA_COLUNA`), então as
  quatro casas que a página tem recebem o estado certo e a quinta simplesmente
  não existe para receber. Não há clique morto nem conteúdo vazando — a única
  diferença até ela publicar é uma coluna a menos e oito dicas a mais.

  **O ENDEREÇO NÃO ESPERA, e já foi.** O `data-hef-alvo="classe"` das células é
  endereço, não desenho: `--publicar-enderecos 10` o levou ao produto em 03/09
  sem mudar um pixel, e é ele que faz a coluna acender pelo perfil em vez de
  pelo mockup. Foi o que deixou os dezesseis campos desta coluna virarem dado
  hoje, sem esperar por ela.
