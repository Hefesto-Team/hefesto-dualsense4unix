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
- **26/10/2026** — A-LISTA-DA-JANELA-CONFIGURAR-NAO-PULA-AO-CLICAR-UM-EFEITO-01: os pedaços da janela Configurar
  (`mod-op-…`, `mod-tela-…`, `mod-livre-pe`) já valem no produto, que monta a janela pelo Python; o desenho só ganhou os ids.
- **26/10/2026** — AS-LINHAS-DA-JANELA-CONFIGURAR-USAM-O-GLIFO-DO-MAPA-DO-CONTROLE-01: as linhas das entradas do controle
  usam o `<use href="#en-…">` do sprite da página. Até publicar, a linha da entrada no produto tem a lista e o rótulo
  na dica, e o glifo fica vazio (a página publicada ainda não tem os `en-…`), por isso o `--publicar 07` sai na
  mesma costura, antes do install. O publicado é igual ao desenho de antes destas sprints, e o `--publicar 07` leva
  só estas duas curas.

## 10-perfis.html
- **26/10/2026** — A-INTERFACE-PASSA-POR-UM-QA-DE-PONTA-A-PONTA-01: a guarda perde a coluna «ID da peça» e o Status
  espalha as seções na largura da célula. Até publicar, o pacote já não escreve `guarda.id` e a página publicada
  mostra na coluna o endereço de exemplo do desenho, por isso o `--publicar 10` sai na mesma costura, antes do
  install. O publicado é igual ao desenho de antes desta sprint, e o `--publicar 10` leva só esta cura.

