# Conferência dos mockups do todo (12/10/2026)

Conferente que corrige, `wf_eec4e930-fe0`. Tudo medido em Chrome sem janela (google-chrome do sistema, com a folha da casa), em 1212x809, 1212x740 e 1918x840. Nenhuma página rola no corpo nos três tamanhos; todos os JSONs ficam com `altura_px` 809 e `rola` false. Toda mudança tem `data-todo` e não sobra `data-todo` sem mudança. Nenhuma frase nova confessa dívida; nenhum noqa novo, nenhum comentário aninhado.

| página | mudanças | a escolher | por baixo | fora |
| --- | --- | --- | --- | --- |
| 01 | 7 | 5 | 8 | 15 |
| 02 | 8 | 6 | 9 | 16 |
| 03 | 3 | 2 | 9 | 27 |
| 04 | 3 | 2 | 5 | 33 |
| 05 | 5 | 2 | 12 | 23 |
| 06 | 18 | 10 | 15 | 8 |
| 07 | 10 | 3 | 12 | 5 |
| 08 | 3 | 2 | 13 | 22 |
| 09 | 10 | 9 | 10 | 11 |
| 10 | 12 | 7 | 11 | 6 |
| calibrar-sensores | 3 | 3 | 3 | 10 |
| mapa-das-portas | 10 | 8 | 8 | 3 |
| mapa-do-controle | 6 | 5 | 3 | 6 |
| mapa-do-radio | 3 | 1 | 2 | 4 |
| **total** | **96** | **64** | 120 | 189 |


## As ordens dela de 12/10 (14h40 e 14h52)

Seis mudanças novas, com a origem «ordem dela de 12/10» na página (etiqueta roxa). Os itens velhos que diziam «par Modo automático | Modo personalizado» (03-2, 04-2, 05-2) perderam a frase.

- **Um botão só, «Modo automático», de 01 a 05** (01-7, 02-7, 03-3, 04-3, 05-4). Um interruptor no topo do quadro, à direita, 28 px de altura, com o ponto que acende. Desligado: borda e texto neutros. Ligado: borda, fundo e ponto em ciano, com brilho fraco (a cor do «ligado» da casa; o roxo já é a seleção e o rosa é a aba ativa). Ligado, os ajustes que o jogo passa a decidir ficam apagados (opacidade .45, sem clique): 01, a escada de modos; 02, os ajustes dos cartões; 03, as colunas dos gatilhos menos a cabeça; 04, as colunas da luz menos o desenho e o nome; 05, a força, o sensor háptico e os motores (o Testar agora segue à mão). Some no `body.nativo.por-controle`, como o par que ele substitui. Na 01 ele toma o lugar do cadeado «Modo Freestyle».
- **A Vibração preenche o quadro** (05-5): o quadro cresce até o rodapé e as linhas se repartem (força 2, cada motor 1, Testar agora 1); medido em 1212x809 e 1680x840 (o tamanho da foto dela de 14h49), sem rolagem.
- **O Desligar do menu diz o que faz** (a frase nova nos itens do menu de todas as páginas com menu; o Mapa do rádio não tem menu): é o mesmo ato do «Desligado» da bandeja (`app/tray.py` → `cmd_tray._definir_o_modo` → `plano_do_modo(MODE_NATIVE)`), o mesmo plano da aba Jogar; o serviço segue de pé. O Ligar liga o serviço se estiver parado e volta ao modo do Hefesto. Vai no `title` do item e o `rotulo()` troca o texto da dica junto com a palavra.
- **A leitura de «Vibração tá faltando guia controles»**: lida como «a Vibração é a aba das cinco que não tem o controle de modo» (03 e 04 tinham o par, a 05 não), e a cura é o 05-4. A outra leitura, «falta a Vibração na aba Controles» (a 02 tem mini painéis de Gatilhos, Barra de luz e LED, e nenhum de vibração), não foi feita: fica para ela dizer.
- **Uma foto por mudança que a foto da aba não mostra** (`pagina/fotografar-estados.py`, 27 fotos `fotos/<aba>-m<n>.png` e `fotos/estados.json`): a janela aberta (06), a sub-aba (07 Meus toques), a lista aberta (10), a seção expandida (08, Mapa do rádio), o Status em Desligado (01), o cartão do P2 (02), a dica do Desligar (01-6) e o Modo automático ligado. A página põe a foto dentro do item, com o estado na legenda; não sobra nenhum «Não aparece na foto».
- Ficou de fora: o Mapa do rádio tem uma `.ajuda` de 20 px (as outras páginas têm 24); a régua `[data-gesto]{min-height:24px}` segue em todas as que tinham.

## Volta 2 (12/10 tarde)

Conferente que corrige. Medido em Chrome sem janela, em 1212x809 e 1680x840 (o tamanho da foto dela de 14h49). As fotos e a página foram refeitas: 101 mudanças, 28 fotos de estado, nenhuma imagem quebrada, nenhum «Não aparece na foto». O `respostas.json` dela não mudou (mesmo md5 antes e depois) e o bloco da página é igual a ele. A cópia de antes desta volta está em `leva-volta/todo-antes-da-volta2/`.

**O que o montador entregou e segue de pé**

- Ordem 1: o botão único «Modo automático» está nas cinco abas (01-7, 02-7, 03-3, 04-3, 05-4), e na 01 ocupa o lugar do Modo Freestyle. As fotos do botão ligado mostram o que fica apagado em cada aba.
- Ordem 4: na 05 as linhas se repartem e não sobra vão (05-5), nos dois tamanhos.
- Ordem 5: o Desligar do menu tem dica. Conferi no código: a bandeja não tem um item «Desligar»; o «Desligado» dela (`app/tray.py` → `cmd_tray._definir_o_modo(False)` → `plano_do_modo(MODE_NATIVE)`) é o mesmo plano da aba Jogar, e o serviço segue de pé. O «Parar o serviço» é outro item.
- Ordem 6: a régua de 24 px segue em todas as páginas que a tinham.
- Ordem 7: os 20 itens sem foto ganharam foto de estado com a marca numerada (janela aberta, sub-aba, lista aberta, seção expandida, rolagem da janela, dica do menu).

**O que eu corrigi**

1. **O botão continuava apagado (ordens 1 e 2).** Desligado, ele era cinza sobre cinza, que é a queixa dela de 14h40 («feios e invisíveis») e do 03-1 («a cor ficou péssima, não diferencia em nada»). Agora tem cor própria nos dois estados:
   - desligado: contorno e anel em ciano, letra clara;
   - ligado: fundo cheio de ciano e a bolinha acesa.
   Continua do tipo do Freestyle (pílula com bolinha), só que em outra cor. Vale nas cinco abas, e o texto dos cinco itens foi atualizado.
2. **«Vibração tá faltando guia controles» (ordem 3).** Li a 02, a 03, a 04 e a 05.
   - Nas abas por controle, a 05 já tinha a linha «Controle» com o desenho e a linha «Modelo», iguais às da 04; a 03 tem os nomes coloridos. Nessa leitura, a 05 só não tinha o controle de modo, e isso o 05-4 já resolve.
   - «Guia» é a palavra comum para «aba». Na **guia Controles**, o cartão de cada controle mostra ao vivo tudo o que as outras abas ajustam (touchpad, barra de luz, LED, gatilhos, microfone, alto-falante), menos a vibração.
   - Por isso entrou o **02-8**: um quadro «Vibração» abaixo do Gatilhos, nos quatro cartões. Ele mostra o que o jogo manda agora a cada motor, em laranja como na 05. Só leitura: a força se ajusta na 05.
   - Ficaram as duas leituras; qual vale é a dúvida 2.
3. **Os botões espremidos da 06 (ordem 2 e a resposta dela ao 06-1).** A fila de baixo tinha 5 px entre os botões e a borda. Entrou o **06-18**: 12 px de moldura, botões de 38 px, 14 px entre eles, texto numa linha só.
4. **Rolagem que o montador não viu.**
   - O Mapa do controle rolava 42 px em 1680x840: o desenho crescia com a largura e cortava o Exportar e o Importar. Entrou o **mapa-do-controle-6**: o desenho cede altura, com foto de estado em 1680x840.
   - O Mapa das portas rolava 5 px em 1212x809 (no publicado já rolava 8). Entrou o **mapa-das-portas-10**: o pé passa de 40 a 32 px.
   - Agora nenhuma das 14 páginas rola nos dois tamanhos. A lista de perfis da 10 rola por dentro, de propósito, como já fazia.
5. **O último alvo de 20 px (ordem 6).** O `?` do espectro do Mapa do rádio passou a 24 px: é o **mapa-do-radio-3**.

Anotado para o próximo bloco, fora destas ordens:
- o texto dela no 05-1, que pede o redesenho dos gatilhos por estilo de jogo, com «criar o próprio modo» e os perfis do usuário;
- na 02, o menu desenhado aberto cobre o pé do cartão maior;
- no Mapa do controle, o «led-jogador» sai da coluna (já saía no publicado).

**As dúvidas que são dela**

1. **«não pra continuar».** Esta volta seguiu a leitura de quem coordena («não, é para continuar»).
   - A) Era para continuar: fica tudo como está.
   - B) Era para parar: volto a página e os mockups para `todo-antes-da-volta2/`, ou para antes das ordens de 14h40.
2. **«Vibração tá faltando guia controles».**
   - A) A vibração faltava na aba Controles: fica o quadro novo (02-8) e também o botão da 05.
   - B) Faltava o controle de modo na 05: fica só o 05-4 e o 02-8 sai.
   - C) Era outra coisa: ela diz qual.
3. **A cor e o nome do botão.**
   - A) Ciano nos dois estados, «Modo automático» (feito; a regra é só a primeira letra maiúscula).
   - B) Cinza quando desligado, como o Freestyle, e cor só ao ligar.
   - C) Outra cor, ou «Modo Automático» como ela escreveu.
4. **O «Desligar» do menu.**
   - A) É o «Desligado» da bandeja e da aba Jogar: o jogo lê o controle direto e o serviço segue de pé (feito).
   - B) É o «Parar o serviço» da bandeja.

## A forma única (coerência entre abas)

- O menu do botão direito é um só: o bloco `style[data-todo-css="menu-do-botao-direito"]` e o `div.todo-menu#todo-menu-direito` da 01, copiados para as outras.
- Com uma janela aberta (`.tela-nova:target`) o menu some, em 06, 07 e 08.
- Alvos: `[data-gesto]{min-height:24px}` em toda página; os poucos que sobravam ganharam regra própria (02, 04, 08).
- Só a primeira letra maiúscula (regra dela de 05/10), também em «modo nativo» e «point and click».
- Um dono por feature (BRIEF-T7): 06 define o point and click, 10 escolhe o estilo, 01 ativa; 05 grava os meus toques e a janela Acessórios só lê.

## 01

6 mudanças, 5 recomendadas a escolher; 8 por baixo, 15 fora.

- O menu do botão direito é a forma comum (bloco `menu-do-botao-direito`), que as outras abas copiaram.
- A mudança 2 diz o que a cena mostra: «Com o Desligado escolhido, a cena o mostra aceso.».
- Conferida contra o BRIEF-T2, opção A: chips e as três dicas.
## 02

6 mudanças, 6 recomendadas a escolher; 9 por baixo, 16 fora.

- `.rota button,.rota.quatro button{min-height:24px}`: os alvos de rota ficam com 24 px; a foto não rola.
- Fora: MUDO-DO-HEFESTO e as costuradas que já estão no antes.

Conflitos:

- 1: Contra a O-TOUCHPAD-MOSTRA-AS-ZONAS-QUE-ELE-APERTA-01 (espera-ela; o commit do desenho e13defb77 não existe). Vence a T1 (12/10, decisão dela); a ZONAS-01 caduca nos botões Cursor/Botões.
- 2: Contra a O-TOUCHPAD-MOSTRA-AS-ZONAS-QUE-ELE-APERTA-01 (espera-ela; o commit do desenho e13defb77 não existe). Vence a T1 (12/10, decisão dela); a ZONAS-01 caduca nos botões Cursor/Botões.
## 03

2 mudanças, 2 recomendadas a escolher; 9 por baixo, 27 fora.

- Menu antigo (`#todo-menu-css`, `.item`) trocado pelo bloco comum da 01 (posição 724/560).
- `[data-gesto]{min-height:24px}`.

Conflitos:

- 1: Duas perguntas do BRIEF-T6 abertas: menu do sistema (A, aplicado) ou desenhado (B); e o Desligar é o interruptor da aba Jogar (aplicado) ou o Parar do serviço da aba Sistema.
- 2: A sprint espera o desenho e não tem recomendação: apliquei a opção 1 (alvos de 24 px, mesma letra). A letra mínima de 12 px e o Tamanho da interface do Sistema ficam para a escolha dela.
## 04

2 mudanças, 2 recomendadas a escolher; 5 por baixo, 33 fora.

- Menu antigo trocado pelo bloco comum da 01 (posição 968/384).
- `[data-gesto]{min-height:24px}` e `.hex.reenvia` com 24 px.
- Em 1212x740 o miolo transborda por dentro (612/549); o antes já transbordava. Só anotado.

Conflitos:

- 1: Duas perguntas do BRIEF-T6 abertas: menu do sistema (A, aplicado) ou desenhado (B); e o Desligar é o interruptor da aba Jogar (aplicado) ou o Parar do serviço da aba Sistema.
- 2: A sprint espera o desenho e não tem recomendação: apliquei a opção 1 (alvos de 24 px, mesma letra). A letra mínima de 12 px e o Tamanho da interface do Sistema ficam para a escolha dela.
## 05

3 mudanças, 2 recomendadas a escolher; 12 por baixo, 23 fora.

- Menu antigo trocado pelo bloco comum da 01 (posição 968/348).
- `[data-gesto]{min-height:24px}`.
- «No Modo Nativo, os seus toques calam» virou «No modo nativo…» (só a primeira maiúscula).
- A 05 é a dona de «Meus toques»; a janela Acessórios da 07 passou a só ler (mudança 10 da 07).
- Fica em dúvida: os ajustes finos do touchpad (altura do dedo, dedo parado, deslize, clique) estão só na dica; e o «Meus toques» não está na tabela de cinco casos do BRIEF-T7, a regra do dono só foi estendida a ele por nós.

Conflitos:

- 1: Duas perguntas do BRIEF-T6 abertas: menu do sistema (A, aplicado) ou desenhado (B); e o Desligar é o interruptor da aba Jogar (aplicado) ou o Parar do serviço da aba Sistema.
- 2: A sprint espera o desenho e não tem recomendação: apliquei a opção 1 (alvos de 24 px, mesma letra). A letra mínima de 12 px e o Tamanho da interface do Sistema ficam para a escolha dela.
- 3: O desenho aprovado em 09/10 põe os mesmos ajustes também na janela Acessórios (abas Meus toques e Touchpad). A T7 (12/10, mais nova) pede um dono só: a aba 05 é a dona e grava, e a janela só lê. Os ajustes finos do touchpad do desenho (a altura do dedo, o dedo parado, o deslize, o clique) não couberam na linha: ficam no padrão do desenho e na dica.
## 06

17 mudanças, 10 recomendadas a escolher; 15 por baixo, 8 fora.

- «Point-and-click» visível virou «point and click» (botão, título e aria-label da janela), igual a 01, 10 e mapa do controle. Os `data-gesto` e o `id` com hífen ficam: não são texto.
- Mudança 10 reescrita: a dica real fala do analógico esquerdo, do touchpad e do point and click; o teto não medido não aparece na tela e fica como bancada da sprint.
- Em 1212x740 o miolo transborda por dentro (585/549). Só anotado.

Conflitos:

- 1: O nome sem hífen é o da volta de 12/10 (BRIEF-T2 e T3), igual nas abas 01, 10 e no mapa do controle.
- 2: O nome sem hífen é o da volta de 12/10 (BRIEF-T2 e T3), igual nas abas 01, 10 e no mapa do controle.
- 3: O desenho A escolhido tinha o −/+ na janela; vence a volta de 12/10 (T3 e T7, um dono por feature).
- 9: BRIEF-T3, opção A aplicada. O liga/desliga sai desta aba: quem ativa é a aba 01 (T7). Os moldes da janela (item 2) e o par Mouse | Teclado precisam de um nome só na escolha dela.
- 10: O teto do trilho é o valor que a sprint mede no aparelho; o desenho usa a escala de hoje, e a tela não fala da medida.
- 14: A exportação leva só os atalhos ou o perfil inteiro: a escolher.
- 15: Ela decide se tem e qual o nome.
- 16: BRIEF-T6 aberto: menu do sistema (A, aplicado; aqui desenhado em HTML só para se ver) ou desenhado (B); o Desligar é o interruptor da aba Jogar (aplicado) ou o Parar do serviço da aba Sistema.
- 17: A sprint espera o desenho e não tem recomendação: aplicada a opção 1 (alvos de 24 px, mesma letra), igual às outras abas. A letra mínima e o Tamanho da interface ficam para a escolha dela.
## 07

10 mudanças, 3 recomendadas a escolher; 12 por baixo, 5 fora.

- «No Modo Nativo» virou «No modo nativo».
- Mudança 10 nova: a aba «Meus toques» da janela Acessórios só lê (valores e o link «Mudar na aba Vibração», que leva à 05). Clicado no Chrome sem janela: a página abre a 05.
- Por baixo: o motor dos acessórios (Buttplug, gestos do PS, a volta no controle e na luz), o prontuário e as marcas do gesto. Fora: reaplicar, receita do jogo e servidor DSU, que não têm tela.
- Fica em dúvida: a aba Touchpad da janela ainda tem a «Leitura» (Pelos lados/Mistura) editável, que repete a da 05; mantive porque ela diz qual motor de qual aparelho, o que é da janela.
- Os dados da Steam são de demonstração (Sackboy e Resident Evil Village).

Conflitos:

- 6: Os dados da Steam são de demonstração (48 jogos, Sackboy e Resident Evil Village).
- 7: Muda a altura da linha do desenho B aprovado.
- 8: BRIEF-T6 aberto: menu do sistema (A, aplicado; aqui desenhado em HTML só para se ver) ou desenhado (B); o Desligar é o interruptor da aba Jogar (aplicado) ou o Parar do serviço da aba Sistema.
- 9: A sprint espera o desenho e não tem recomendação: aplicada a opção 1 (alvos de 24 px, mesma letra), igual às outras abas. A letra mínima e o Tamanho da interface ficam para a escolha dela.
- 10: A sprint O-JOGO-DOS-ACESSORIOS… desenhou os mesmos controles nos dois lugares (05 e janela); a T7 de 12/10 (um dono só, «Temos que evitar features se repetindo») é mais nova e vence: a 05 grava, a janela só lê.
## 08

3 mudanças, 2 recomendadas a escolher; 13 por baixo, 22 fora.

- `.tela-nova:target ~ .todo-menu{display:none}`: o menu some com uma janela aberta, como na 06 e na 07.
- `.cartao-dica .cd-info` com 24x24.
- Fora: O-CONTROLLERS-JSON-ILEGIVEL. Por baixo: O-ASSENTO-GUARDADO-NAO-ANDA-01/02/03.
- Em 1212x740 o miolo transborda por dentro (560/549). Só anotado.

Conflitos:

- 1: Na voo/lancadores-fds (717bd1627, 85f39681b, cecdace53), ainda não costurada; a opção 1 da faixa é a escolha dela de 09/10.
- 2: Duas perguntas do BRIEF-T6 abertas: menu do sistema (A, aplicado) ou desenhado (B); e o Desligar é o interruptor da aba Jogar (aplicado) ou o Parar do serviço da aba Sistema.
- 3: A sprint espera o desenho e não tem recomendação: apliquei a opção 1 (alvos de 24 px, mesma letra), como nas outras abas. A letra mínima de 12 px e o Tamanho da interface do Sistema ficam para a escolha dela.
## 09

10 mudanças, 9 recomendadas a escolher; 10 por baixo, 11 fora.

- Por baixo: A-JANELA-DO-INICIO-DA-SESSAO. Fora: O-CODIGO-SEM-NARRADOR-02.
- «Permitir correção pelo Doctor» é texto literal da sprint: fica.

Conflitos:

- 1: Opção A do BRIEF-T5 aplicada; B e C seguem com ela.
- 3: O padrão ligado é nosso, a validar.
- 4: O padrão ligado vem da AS-CONFIGURACOES-CHEGAM-AO-JOGO-NOVO-QUANDO-A-STEAM-FECHA-01 (P4); a validar.
- 8: BRIEF-T6: menu do sistema (A, aplicado) ou desenhado (B); o Desligar é o interruptor da aba Jogar (aplicado) ou o Parar do serviço da 09.
- 9: O lugar é desenho nosso; os outros montadores deixaram o controle para a 09.
- 10: Opção 1 da sprint (24 px); as outras opções seguem com ela.
## 10

12 mudanças, 7 recomendadas a escolher; 11 por baixo, 6 fora.

- O chip Eventos ficou habilitado e saiu o «Chega com as extensões.» (a P10 dá o motor).
- Mudança 12 passou a desenho-escolhido (regra da maiúscula de 05/10).
- Mudança 2: as colunas novas entram no lugar de «Preferência» e «Funciona em»; sai o «Só quando eu escolher» das ESCOLHAS de 08/10, porque o pedido de 12/10 é mais novo.
- A lista de perfis rola por dentro (`div.rolo` 507/389), de propósito, como no antes. O `span.puxador` (9x23) é alça de arrastar: aceito.

Conflitos:

- 2: A ordem e a largura das colunas são nossas, e os nomes também: ela pediu «Data de Criação» e «Data de Modificação» (12/10); o todo usa «Criado em» e «Modificado em», mais curtos. As duas colunas entram no lugar de «Preferência» e «Funciona em», como ela pediu; com isso sai o rótulo «Só quando eu escolher» da coluna «Funciona em» (ESCOLHAS de 08/10, SO-O-FREESTYLE-VALE-EM-TODO-JOGO-01): o pedido de 12/10 é o mais novo e vence.
- 3: BRIEF-T4 opção A aplicada. O nome «Freestyle» é recusado por baixo.
- 4: Resolvido na conferência: o todo é o depois de todas as sprints, e a P10 (O-GATILHO-E-A-HAPTICA-DO-JOGO-VIRAM-EVENTOS-PARA-AS-EXTENSOES-01) dá o motor do Eventos; o chip fica habilitado e sai o «Chega com as extensões.», que confessava dívida. A pergunta 2 do BRIEF-T4 (apagado agora ou só quando funcionar) segue com ela para o produto de antes da P10.
- 7: Na fds, commit 5fa799d63.
- 8: O lugar no select é dela.
- 9: A opção A «escolhida em 09/10» só aparece no BRIEF-T3 e no BRIEF-T7; não achei a frase dela em outro lugar.
- 10: BRIEF-T6: menu do sistema (A, aplicado) ou desenhado (B); o Desligar é o interruptor da aba Jogar (aplicado) ou o Parar do serviço da 09.
- 11: Opção 1 da sprint (24 px); as outras opções seguem com ela.
- 12: Regra dela de 05/10 (primeira maiúscula em toda tela), como no mapa-das-portas, mudança 7.
## calibrar-sensores

3 mudanças, 3 recomendadas a escolher; 3 por baixo, 10 fora.

- As costuradas que tocam o calibrar foram para o «fora» dele.
- Em 1212x740 o corpo transborda por dentro (688/651). Só anotado.

Conflitos:

- 1: Opção recomendada do BRIEF-T7 (a 02 é a dona); a outra segue com ela.
- 2: BRIEF-T6: menu do sistema (A, aplicado) ou desenhado (B); o Desligar é o interruptor da aba Jogar (aplicado) ou o Parar do serviço da 09.
- 3: Opção 1 da sprint (24 px); as outras opções seguem com ela.
## mapa-das-portas

9 mudanças, 8 recomendadas a escolher; 8 por baixo, 3 fora.

- O corpo transbordava por dentro (730/686; o antes já tinha 694/686). Apertei os espaços da bandeja e da face no estilo `cadeia-e-registro`: agora 691/686, dentro do padding de 40 px.

Conflitos:

- 1: BRIEF-ACESSORIOS-USB, opção A (aplicada) contra B (embaixo do painel, faz a página rolar em 1212x700) e C (no log da aba 09, que o BRIEF-T5 redesenha).
- 3: Pergunta do BRIEF: um só (aplicado) ou com os lados 2.0 e 3.0 à vista.
- 7: O BRIEF-ACESSORIOS-USB chama a página de «Mapa das Conexões»; vence a regra dela de 09/10 (só a primeira letra maiúscula).
- 8: Duas perguntas do BRIEF-T6 abertas: menu do sistema (A, aplicado) ou desenhado (B); e o Desligar é o interruptor da aba Jogar (aplicado) ou o Parar do serviço da aba Sistema.
- 9: A sprint espera o desenho e não tem recomendação: apliquei a opção 1 (alvos de 24 px, mesma letra), como nas outras abas. A letra mínima de 12 px e o Tamanho da interface do Sistema ficam para a escolha dela.
## mapa-do-controle

5 mudanças, 5 recomendadas a escolher; 3 por baixo, 6 fora.

- `.todo-menu button:hover` ganhou o recuo `var(--sel-bg,rgba(189,147,249,.16))`, porque o token não existia.
- Mudança 5 reescrita: a página não tem «?»; o que muda é o `[data-gesto]` com 24 px.
- Em 1212x740 e 1918x840 o corpo transborda por dentro (706/651, 793/751). Só anotado.

Conflitos:

- 1: BRIEF-T3 opção A aplicada. O Mouse/Teclado é escolhido na aba Navegação (um dono só); aqui ele só se lê.
- 3: O formato da exportação é pergunta dela.
- 4: BRIEF-T6: menu do sistema (A, aplicado) ou desenhado (B); o Desligar é o interruptor da aba Jogar (aplicado) ou o Parar do serviço da 09.
- 5: Opção 1 da sprint (24 px); as outras opções seguem com ela.
## mapa-do-radio

2 mudanças, 0 recomendadas a escolher; 2 por baixo, 4 fora.

- Já tinha as âncoras por script (`q.dataset.todo`, `v.dataset.todo`). Os 15 noqa vêm do antes.

Conflitos:

- 1: Costurada na integra/1-11 (o mockup já tem), falta o --publicar do fecho.
- 2: Costurada na integra/1-11 (41320a2d6, com a A-PONTE-SE-CONTA-EM-FATIAS-NO-AR-01), falta o --publicar do fecho.

## Cobertura: abertas sem página

Sinal de tela fraco (só a posse de `interface/` ou o código da ponte, sem nada visível nos desenhos): A-BANCADA-DOS-EXTERNOS, O-BASICO-MEDIDO-01, A-DOCSTRING-DIZ-O-CONTRATO…, A-LINHA-DE-COMANDO-ESPERA…, A-LINHA-DE-COMANDO-NAO-TRAVA…, A-TELA-E-DEPENDENCIA-DURA-01, AS-REGRAS-DO-SOM-VALEM…, O-ANALOGICO-CHEGA-AO-JOGO…, O-BLUEZ-DA-CASA…, O-BROKER-SERVE…, O-DIARIO-AVISA…, O-INSTALL-EM-QUALQUER-DISTRO-01, O-PERFIL-DE-FABRICA…, O-PERFIL-FEITO-FORA-DA-JANELA…, O-QUE-E-DA-BANCADA-FICA…, O-TIQUE-TEM-ORCAMENTO…, OS-NUMEROS-DA-SONY….
A-CHAVE-E-A-PERMISSAO-DIZEM-O-QUE-SAO-01 muda o aviso «daemon offline», um estado que os mockups não desenham (todos mostram o daemon no ar).

A-COR-E-O-NUMERO-DO-PERFIL… e AS-MODIFICACOES-RODAM-FORA-DO-DAEMON-01 foram costuradas na fds e não estão na 1-11; nenhuma tem sinal de tela.

Não mudam a tela (código, CI, bancada, install e processo):

2026-08-31-A-BANCADA-QUE-O-RADIO-PEDE-INDICE.md 2026-09-10-OS-GESTOS-QUE-SO-ELA-PODE-FAZER.md 2026-09-17-SOM-CABO-QUALIDADE-01-a-queixa-que-o-codec-nao-explica.md 2026-09-18-RELEASE-NO-CLONE-LIMPO-01-a-esteira-dos-pacotes-cai-por-uma-pasta-que-nao-viaja.md 2026-09-19-HIDE-SO-O-HIDRAW-02-o-fisico-alcancavel-por-quatro-nos-de-entrada.md 2026-09-19-STORM-USB-01-o-ruido-de-porta-que-o-doctor-conta-e-ninguem-cura.md 2026-09-24-A-FAIXA-NA-MESA-FORA-DE-ORDEM-01.md 2026-09-27-A-ARVORE-TEM-UMA-SESSAO-SO-01.md 2026-09-27-A-GUARDA-FECHA-A-PORTA-01.md 2026-09-27-A-HISTORIA-REESCRITA-UMA-VEZ-SO-01.md 2026-09-27-AS-CITACOES-DE-COMMIT-SEGUEM-O-MAPA-01.md 2026-09-27-A-SENHA-SO-PASSA-PELO-ASKPASS-01.md 2026-09-27-O-DESPACHANTE-DAS-REGRAS-DA-CASA-01.md 2026-09-27-O-ENDERECO-NUNCA-CHEGA-A-CONVERSA-01.md 2026-09-27-O-GITHUB-SEM-RASTRO-FORA-DO-GIT-01.md 2026-09-27-O-PRODUTO-EM-QUALQUER-MAQUINA-01.md 2026-09-28-O-NIX-LEVA-AS-REGRAS-DO-HOST-01.md 2026-09-29-A-REPORT-THREAD-SAI-ANTES-DO-HANDLE-FECHAR-01.md 2026-10-01-O-ENGASGO-DO-JOGO-LEVE-SE-SEPARA-EM-ABBA-01.md 2026-10-01-O-FORJA-E-O-BANCO-DE-PROVA-DO-HEFESTO-01.md 2026-10-01-O-JOGO-LEVE-ACORDA-A-PLACA-01.md 2026-10-05-A-FORJA-SEM-RASTRO-01.md 2026-10-05-A-WIKI-NASCE-DO-QUE-O-REPOSITORIO-JA-SABE-01.md 2026-10-05-O-CLAUDE-CHEGA-COM-O-CONTEXTO-CERTO-02.md 2026-10-05-O-REPOSITORIO-NASCE-VIVO-01.md 2026-10-08-A-CASA-NAO-DEIXA-PASSAR-COMENTARIO-CORTADO-IMPORT-RELATIVO-NEM-POSSE-DE-ARQUIVO-QUE-NAO-EXISTE-01.md 2026-10-08-A-CITACAO-CURTA-DO-DIFF-LE-A-CELULA-E-A-SEGUNDA-CHANCE-NAO-DESFAZ-A-CORRECAO-01.md 2026-10-08-A-DIVIDA-DA-BASE-DESCE-POR-ARQUIVO-E-POR-QUEM-TOCA-01.md 2026-10-08-A-GRAVACAO-DO-YML-QUE-FALHA-DEPOIS-DA-ANOTACAO-VAI-AO-DIARIO-01.md 2026-10-08-A-JANELA-ABERTA-CABE-NA-PARTE-01.md 2026-10-08-AS-CITACOES-CURTAS-DO-CSV-ANDAM-COM-A-INTEIRA-01.md 2026-10-08-AS-FERRAMENTAS-DA-LEVA-NAO-CALAM-E-A-BASE-DELAS-FICA-VERDE-01.md 2026-10-08-AS-FERRAMENTAS-DE-MANUTENCAO-NAO-REESCREVEM-ALEM-DO-QUE-PROVAM-01.md 2026-10-08-A-SONDA-DO-BLUEZ-PERGUNTA-
SO-AO-DONO-E-O-ENSAIO-PASSA-NO-TIPO-01.md 2026-10-08-AS-REGUAS-DO-RAMO-INTEIRO-E-DAS-QUATRO-RESPOSTAS-MORDEM-01.md 2026-10-08-O-BIG-PICTURE-SE-PROVA-NA-STEAM-E-O-MAPA-GANHA-AS-LINHAS-01.md 2026-10-08-O-CAMINHO-DO-BLUEZ-SO-NO-DONO-01.md 2026-10-08-O-COSTURAR-ACEITA-O-COMMIT-RESOLVIDO-A-MAO-SE-O-PATCH-FORA-DOS-GERADOS-JA-ESTA-NA-INTEGRACAO-01.md 2026-10-08-O-DUALSENSE-PELO-RADIO-NO-WINE-SE-EXPLICA-01.md 2026-10-08-O-DUBLE-DO-CONTROLE-FICA-DESPLUGADO-E-O-TESTE-DO-DAEMON-ESPERA-A-CONDICAO-01.md 2026-10-08-O-LOTE-DE-TESTES-DO-AGENTE-ISOLA-O-WEBKIT-COMO-A-SUITE-01.md 2026-10-08-O-MOLDE-DA-SPRINT-LISTA-TODO-CAMPO-QUE-O-PORTAO-LE-01.md 2026-10-09-A-BANDEJA-TEM-UM-DONO-SO-01.md 2026-10-09-A-CASCATA-DO-WAYLAND-SO-PERGUNTA-A-QUEM-RESPONDE-01.md 2026-10-09-A-CATRACA-DA-ORIGEM-CONTA-O-SUPPRESS-QUE-SO-ENGOLE-01.md 2026-10-09-A-CITACAO-NOVA-DE-LINHA-PROMETE-O-NOME-01.md 2026-10-09-A-COR-E-O-NUMERO-DO-PERFIL-CHEGAM-POR-TODA-ROTA-01.md 2026-10-09-A-FABRICA-NOVA-DO-FREESTYLE-ALCANCA-A-COPIA-DE-FABRICA-DE-ONTEM-01.md 2026-10-09-A-HAPTICA-DO-RADIO-SE-CONVERTE-SEM-PESAR-NA-PONTE-01.md 2026-10-09-A-LUZ-DO-MIC-SEGUE-O-BOTAO-QUANDO-NAO-SABE-QUEM-OUVE-01.md 2026-10-09-A-MASCARA-DO-PAD-SE-DECIDE-SO-NA-FABRICA-01.md 2026-10-09-A-PERDA-DE-AMOSTRAS-DO-MOVIMENTO-SE-CONTA-PELO-CONTADOR-DO-REPORT-01.md 2026-10-09-A-SETA-SEGURADA-SE-SOLTA-QUANDO-O-PERFIL-TROCA-01.md 2026-10-09-AS-METRICAS-CONTAM-O-QUE-A-PAGINA-PROMETE-01.md 2026-10-09-AS-MODIFICACOES-RODAM-FORA-DO-DAEMON-01.md 2026-10-09-A-SUITE-NAO-ACORDA-A-PLACA-DE-VERDADE-01.md 2026-10-09-A-TROCA-DE-DAEMON-ESPERA-O-DESLIGAMENTO-INTEIRO-01.md 2026-10-09-A-TROCA-PELA-JANELA-NAO-PARA-O-LACO-DO-CONTROLE-01.md 2026-10-09-NADA-QUE-O-GITIGNORE-EXCLUI-ENTRA-NO-REPOSITORIO-01.md 2026-10-09-O-APARELHO-QUE-VIRA-P1-SEGUE-ESCONDIDO-DO-JOGO-01.md 2026-10-09-O-ARQUIVO-DE-MASCARAS-ILEGIVEL-NAO-SE-SOBRESCREVE-CALADO-01.md 2026-10-09-O-BRANCO-DA-TROCA-DE-PERFIL-PISCA-SEM-GRAVAR-01.md 2026-10-09-O-CI-CHAMA-OS-PORTOES-PELO-NOME-01.md 2026-10-09-O-DSX-ACENDE-O-JOGAD
OR-QUE-O-MOD-PEDE-01.md 2026-10-09-O-DSX-PINTA-COMO-JOGO-E-O-RESET-DEVOLVE-O-PERFIL-01.md 2026-10-09-O-ERRO-DO-LACO-DE-60-HZ-VAI-AO-DIARIO-E-NAO-DERRUBA-A-MESA-01.md 2026-10-09-O-GATILHO-QUE-O-CONTROLE-NAO-ACEITA-NAO-DERRUBA-O-PERFIL-01.md 2026-10-09-O-LIMIAR-DO-GATILHO-DO-DSX-VALE-PARA-CADA-JOGADOR-01.md 2026-10-09-O-MAPA-DA-VIBRACAO-DIZ-O-QUE-O-CODIGO-FAZ-01.md 2026-10-09-O-MICROFONE-DO-RADIO-DESLIGA-NO-STOP-MESMO-COM-A-VOLTA-EM-CURSO-01.md 2026-10-09-O-MODIFICADOR-SEGURADO-POR-OUTRO-BOTAO-NAO-SE-SOLTA-01.md 2026-10-09-O-MOUSE-EMULADO-TEM-UM-DONO-SO-01.md 2026-10-09-O-NO-DE-SOM-FICA-QUANDO-O-CONTROLE-SAI-01.md 2026-10-09-O-NO-E-A-PONTE-DO-SOM-NAO-NASCEM-DEPOIS-DO-STOP-01.md 2026-10-09-O-NO-LIGA-A-ROTA-INTEIRA-E-SEGUE-A-SAIDA-PADRAO-01.md 2026-10-09-O-PAD-CEDIDO-CALA-O-GATILHO-E-A-LUZ-TAMBEM-01.md 2026-10-09-O-PAD-QUE-NASCE-NAO-PARA-O-TIQUE-DOS-OUTROS-01.md 2026-10-09-O-PAR-DO-GESTO-DO-PS-NAO-CHEGA-AO-JOGO-01.md 2026-10-09-O-PERFIL-ANTIGO-DE-VIBRACAO-POR-POSICAO-CARREGA-NO-PISO-01.md 2026-10-09-O-PERFIL-DO-JOGO-ENTRA-SEM-LER-A-JANELA-01.md 2026-10-09-O-PLUGIN-RECARREGA-SEM-PERDER-OS-PLUGINS-01.md 2026-10-09-O-PS-ABRE-A-STEAM-PELO-DONO-QUE-JA-SABE-REABRIR-01.md 2026-10-09-O-QUE-SO-A-JANELA-LIGAVA-TEM-VERBO-NO-TERMINAL-01.md 2026-10-09-O-RAPIDO-SO-REPETE-O-QUE-MUDOU-01.md 2026-10-09-O-RECARREGAR-DOS-PLUGINS-NAO-APAGA-OS-PLUGINS-01.md 2026-10-09-OS-COMANDOS-E-OS-TESTES-NAO-SABEM-O-CAMINHO-DESTA-MAQUINA-01.md 2026-10-09-O-SOM-QUE-O-JOGO-MANDA-AO-CONTROLE-TOCA-TAMBEM-PELO-RADIO-01.md 2026-10-09-O-SUBSYSTEM-SOBE-E-DESCE-POR-UMA-LISTA-SO-01.md 2026-10-09-O-TIQUE-DE-30-S-SO-REPINTA-A-LUZ-QUE-O-KERNEL-PERDEU-01.md 2026-10-09-O-TOQUE-CURTO-DO-JOGO-CHEGA-AO-CONTROLE-MESMO-ENTRE-DOIS-TIQUES-01.md 2026-10-09-O-VERMELHO-NOVO-DA-COSTURA-NAO-SE-ESCONDE-NO-HERDADO-01.md 2026-10-09-O-VIGIA-DO-RADIO-SO-TOCA-OS-CONTROLES-DO-HEFESTO-01.md 2026-10-09-QUEM-SOLTA-O-CONTROLE-SOLTA-O-GATILHO-DE-TODOS-01.md 2026-10-12-A-CANONICA-RECEBE-O-QUE-AS-REIMPLEMENTACOES-ABERTAS-DIZEM-DO-SOM-E-DO-TO
