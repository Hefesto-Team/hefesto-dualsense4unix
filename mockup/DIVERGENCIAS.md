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

## 02-controles.html
- **01/10/2026** — o botão «Mapa do controle» sai do canto da aba (o Calibrar fica sozinho ali), porque o mapa mora só na aba Conexões desde 29/09, por ordem dela; a legenda ganha a lápide do botão (O-MAPA-DO-CONTROLE-MORA-SO-NA-CONEXOES-01). Até publicar, a 02 dela ainda mostra os dois botões.

## 06-navegacao.html
- **01/10/2026** — a porta de canto «Mapa do controle ↗» sai do quadro da Navegação, resposta dela de 29/09 («Sai também»): o mapa se abre só pela aba Conexões (O-MAPA-DO-CONTROLE-MORA-SO-NA-CONEXOES-01). Até publicar, a 06 dela ainda tem a porta.

## 08-conexoes.html
- **01/10/2026** — o «Mapear Entradas» lista toda entrada numerada (com nome ou sem), a conta embaixo é a da lista («15 entradas mapeadas.»), a lista rola na altura da coluna da esquerda, os valores medidos começam com maiúscula («Num hub», «Direto no computador», «Nenhuma em 7 dias») e a frase da entrada encontrada é a que ela ditou em 29/09 (O-MAPEAR-LISTA-O-QUE-JA-FOI-MAPEADO-01). A dica «?» do diálogo deixa de mandar dar nome e lugar (os dois são opcionais) e chama a seção pelo nome de hoje, «Gestão de Controles». Até publicar, a frase, a lista, a conta e as maiúsculas já chegam à tela dela pelo pacote, que pinta esses campos a cada tique, a lista com as 15 entradas dela empurra o diálogo para baixo em vez de rolar (o CSS da rolagem é da página), e a dica ainda diz «dê um nome e o lugar» e «Check-up».

## 10-perfis.html
- **28/09/2026** — a coluna do `movimento` passa a se chamar «comandos virtuais» na dica do cabeçalho: ela guarda a Mira Virtual, a Inclinação e o Cursor ou os Botões do touchpad (NO-MODO-XBOX-TUDO-FUNCIONA-01). Até publicar, a dica da tela dela diz «mira virtual», e a coluna acende igual com qualquer um dos três.

## mapa-das-portas.html
- **01/10/2026** — o Mapa das Conexões cabe na aba: o resumo do Atual numa linha, as entradas de cada face em quantas colunas couberem, a legenda na linha dos modos, «Atualmente conectado» rolando por dentro até o fim da última face, o Adicionar numa linha com «O que você pretende conectar?», o Sugestões com uma linha por movimento (as razões no «?»), o mapa dele só com o veredito, o «então» com acento e o «Já movi» sem repetir o id do «Examinar» (O-MAPA-DAS-CONEXOES-CABE-NA-ABA-E-FALA-MENOS-01). As onze edições esperam em `pagina_do_mapa.EDICOES_ESPERANDO_A_SESSAO_DELA`. Até publicar, a página dela rola no Atual, a legenda fica embaixo do palco e o Sugestões mostra as razões, o parágrafo do «Já movi» e o «Entrada Null» do motor no mapa.

## mapa-do-controle.html
- **01/10/2026** — o «← Voltar» volta para a aba de onde o mapa foi aberto (pergunta à lista de volta do WebView, e não ao `document.referrer`, que no WebKit vem vazio entre arquivos), e os dois botões da barra de provas começam com maiúscula, «Nenhum» e «Apagar» (O-VOLTAR-DO-MAPA-VOLTA-PARA-A-ABA-DE-ONDE-VEIO-01). Até publicar, o «Voltar» da página dela leva sempre à Controles, e a barra diz «nenhum» e «apagar».
- **01/10/2026** — o mapa passa a ser do produto: o botão apertado no controle acende a peça e a linha dela (o pisca da Controles), a troca de botões do perfil aparece como «No jogo: Cruz» na linha e como contorno tracejado no desenho, o «Jogador» vira «Controle» com os chips da mesa (o gesto da fita das abas, mais «Todos» e «Nenhum»), o rótulo diz o papel do controle na Navegação, a barra de luz é a do aparelho, a dica de cada botão diz o que ele faz na Navegação, e o item do PS lista os seis gestos (O-MAPA-DO-CONTROLE-PISCA-E-SEGUE-O-REMAPEAMENTO-01). Até publicar, o mapa dela é o banco de provas de antes, sem nada do produto.

## calibrar-sensores.html
- **28/09/2026** — a linha da Mira Virtual diz também o que vale para a Inclinação e para o Cursor do touchpad (NO-MODO-XBOX-TUDO-FUNCIONA-01). Até publicar, a Calibrar dela fala só da Mira Virtual, e os deslizantes já valem para os três.
- **01/10/2026** — o «← Voltar» pergunta à lista de volta do WebView, o mesmo dono do mapa do controle (`caixa_da_janela.voltar`). Na Calibrar não se vê diferença: só a Controles a abre (O-MAPA-DO-CONTROLE-PISCA-E-SEGUE-O-REMAPEAMENTO-01).
