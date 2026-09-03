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

- **03/09/2026** — **a TIRA DO DESFECHO**, uma linha nova sob o cabeçalho do
  quadro: o que aconteceu depois do último clique. É paridade com a janela
  estável, onde **todo** gesto desta aba termina num toast no rodapé
  (`profiles_actions._toast_profile`) — "Perfil removido: X",
  "Lista recarregada", `mensagem_de_ativacao`.

  **O QUE MUDA NA TELA, e é só isto:** uma faixa de 15px (mais 7px de vão) entre
  o cabeçalho `Perfis` e o corpo. Ela nasce **invisível** e reserva o espaço
  (`visibility`, não `display`), para a lista de 33 perfis não pular a cada
  clique. O espaço sai da altura da lista, que é quem estica.

  **O QUE ELA VÊ HOJE, sem publicar:** nada muda — a página publicada não tem a
  tira, e o valor emitido cai no vazio (declarado em
  `a10_perfis.SEM_ENDERECO`). **Enquanto** ela não aprova, os nove gestos desta
  aba que gravam no disco continuam mudos no sucesso: ela renomeia um perfil, o
  campo volta ao normal e nada diz que gravou. A recusa continua falando pela
  tarja do piloto, que já existe e não depende desta tira.

  **O que NÃO espera por ela** (já está no produto, sem tocar no desenho): o
  "Recarregar" deixou de ser botão morto, o "Novo" nasce com prioridade acima
  dos que valem sempre, a cópia do "Duplicar" não herda mais o carimbo de ponte,
  o "Ativar" lê o relatório de seções do daemon e pega a carona do wrapper, e
  trocar "Funciona em" para "Todos" num perfil de jogo pergunta antes.
