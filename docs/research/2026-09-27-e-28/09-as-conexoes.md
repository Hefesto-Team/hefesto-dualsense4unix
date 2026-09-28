# A aba Conexões em quatro rodadas

As quatro rodadas de 26/09/2026 que levaram a aba 08 (Conexões), o «Mapa das Conexões» e o «Aplicar» do rodapé ao produto: o que se mediu, a causa, a cura e o que ficou aberto.

Cada rodada teve uma implementação e uma conferência independente, que refez as mordidas, achou o que faltava e curou na mesma branch. Onde a conferência mudou um número da implementação, vale o dela.

| rodada | sprints |
|---|---|
| 1 | `O-MAPEAR-NAO-CONGELA-A-JANELA-01`, `O-BRILHO-DAS-LUZES-SOBREVIVE-AO-APLICAR-01` |
| 2 | `O-RADIO-CONECTA-ONDE-ELA-MANDA-01`, `O-MAPA-DAS-CONEXOES-NO-PRODUTO-01` |
| 2b | `O-APLICAR-NAO-SOLTA-O-TETO-DO-CONTROLE-01` |
| 3 | `A-GESTAO-DOS-CONTROLES-NO-PRODUTO-01`, `O-RADIO-CONECTA-ONDE-ELA-MANDA-02`, `O-MAPA-DAS-CONEXOES-NO-PRODUTO-02` |

## 1. O Mapear congelava a janela

**A causa.** O tique da 08 chamava o `estado()` e o `olhar()` do Mapear no fio do GTK. Os dois leem o censo do barramento, que lê `product` e `bMaxPower` sob o lock do aparelho. Com o kernel enumerando o DualSense, cada leitura esperava segundos: em repouso ela custa 8 ms, e enumerando, de 3 a 15 s.

**Medido no piloto oculto, com um `/sys` de mentira preso por 6 s e um coração do GTK a cada 50 ms:**

| | antes | depois |
|---|---|---|
| parada do coração ao abrir o Mapear | 6,055 s | 0,084 s |
| parada do coração no «Terminar» | 6,044 s | 0,082 s |
| tique mais caro | 5971 ms | 109 ms |

**A cura** (`src/hefesto_dualsense4unix/integrations/entrada_a_entrada.py`):

- o tique chama `foto_sem_esperar()`, que pinta a última foto e pede a próxima num fio próprio, o `_VooDaLeitura`, com uma leitura no ar por vez;
- `olhar`, `estado` e `gravar` leem antes de tomar a trava; uma sessão numerada impede que a leitura que volta depois de um parar ou de uma reabertura ande o fluxo;
- a cerimônia (`LacoDaEntrada`) tinha o mesmo defeito e recebeu a mesma cura; o censo da aba (`_censo()`) passou a sair por `_em_fundo`;
- «Procurando…» aparece no campo que já existia, até a primeira foto ou quando a leitura passa de `FOLEGO_DA_LEITURA_S` (1,0 s). Assim a tela não afirma «Entrada encontrada» sobre a porta de onde o cabo já saiu.

**O que a conferência achou.** Tirar a leitura da trava desfez a fila entre gestos, e a própria cura abriu três regressões:

- um «Já chega por hoje» clicado durante a leitura era desfeito quando ela voltava;
- o «Não sei onde fica» mandava a resposta para a pergunta seguinte e gravava errado no `maquina.json`;
- um Salvar antes da primeira foto fazia o `-71` do log sumir da sessão. A leitura do log ganhou marca própria, `_storm_lido`.

Entraram também duas réguas: a da reabertura do Mapear e a do tique inteiro da 08, que exige que os três donos tenham pedido a leitura, para não dar verde sem medir. Com um gancho de auditoria no fio da janela, a base abria `product`, `manufacturer`, `bMaxPower` e `bmAttributes` 70 vezes cada. Com a cura, o fio da janela só abre atributos que o kernel serve sem o lock.

Régua: `tests/unit/test_o_mapear_le_o_barramento_fora_do_fio_da_janela.py`, 15 testes e 15 mordidas.

## 2. O brilho das luzes de número morria no «Aplicar»

**A causa.** Bastava um override por controle no perfil (a cor de cada um, que é o caso real). Com ele, o rascunho do rodapé mandava a seção `controllers` sem `player_led_brightness`, porque `DraftConfig._controllers_to_ipc` só conhecia a cor, o brilho da barra e as lâmpadas. O `DraftApplier` troca o mapa inteiro de overrides (`reset_output_overrides`): o Forte do P2 saía do merge e o aparelho voltava ao Fraco do perfil. A pílula pergunta ao daemon vivo, então acendia Fraco sobre um disco que dizia Forte. Por isso «não aplica» e «não salva» eram a mesma queixa.

**A outra metade, no «Salvar».** O tom e a caixa `#RRGGBB` gravam a cor com a procedência (`lightbar_para_o_numero`), e o `with_controller_leds` do «Salvar» a apagava. A cor virava legado, e o P4 no tom do número 2 acendia a cor do número dele na troca seguinte. A conferência achou um sexto gesto na mesma classe, o interruptor «Cores automáticas» (`grava="gravar_e_reaplicar"`), que a varredura não clicava.

**A cura** desta rodada foi uma segunda viagem pelo rodapé: `led.player_brightness_set` para cada controle que escreveu o campo. A rodada 2b a trocou pela cura no lugar certo, o rascunho (seção 5).

Régua: `tests/unit/test_o_brilho_das_luzes_sobrevive_ao_aplicar_e_ao_salvar.py`, 61 testes. Cobre P1 a P4, USB e BT, na mesa de quatro com o `IpcServer`, o merge do `PyDualSenseController` e o `SysfsLedNode` reais.

## 3. O «Conectar» pareia no adaptador aberto

**`O-RADIO-CONECTA-ONDE-ELA-MANDA-01`:**

- o destino do «Conectar» é a caixa aberta (`_destino_do_conectar`); sem caixa aberta, vale a D8 (`destino_da_central`);
- o «esperando» segura a tela por no máximo 60 s. Depois vira «Não Conectou», com «Tentar de Novo» e o X. Os 60 s vêm do diário: janela de 30 s, mais 11 s do Pair, mais 10 s de conferir, dão 51 s;
- o X aparece em todo controle de todo adaptador. Ele pergunta antes e tira o pareamento só daquele adaptador, com o `RemoveDevice` pelo dono e o verbo `esquecer` da ponte. Nada escreve em `/var/lib/bluetooth`. O controle pareado e fora do ar ganha a linha «Desligado»;
- o balão de vizinho sem nome ganha o palpite «Teclado?» ou «Mouse?».

**O que a conferência achou:**

- a tela apagava a meia chave pelo próprio relógio (60 s), mas a central ainda conferia até 120 s. Com isso, matava um pareamento que ainda podia chegar. A tela passou a esperar o «não chegou» da central;
- o «Não Conectou» de um fone ou teclado ficava 10 min sem saída, e ganhou o X;
- `_e_controle_do_bluez` juntava as perguntas com `or`, e um fone da Sony com `054C` no Modalias virava controle. Agora a primeira pergunta que responde decide, a começar pela classe;
- ficou medida a **zona morta**: entre 60 e 120 s os botões apareciam acesos e a central recusava com «ocupado». A prova de tela não a pegou porque o daemon de mentira era mais frouxo que a central.

**A `-02` fechou os três buracos** (`src/hefesto_dualsense4unix/integrations/central_do_radio.py`):

- `PRAZO_DO_PENDENTE_S = 60.0` (era 120) é o dono único do prazo, e o `ESPERA_NA_TELA_S` de `src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py` o lê. A conferência nunca passa do prazo, e `comecar_a_mover`, `comecar_a_conectar`, `mover` e `conectar` chamam `_vencer_os_prazos()` antes de dizer «ocupado»;
- a meia chave sai no daemon, com a janela fechada. `_fechar_sem_chegar` tira só a chave que o Pair deste movimento criou no destino: a que está `Paired`, sem `Connected` e fora do `HID_PHYS` (`_esquecer_a_meia_chave`);
- o nome do controle mora em `ControleDeclarado.nome`, no `maquina.json`, com até 248 bytes, gravado por `gravar_o_nome_do_controle` (`src/hefesto_dualsense4unix/utils/maquina.py`), que nunca levanta. A central aprende o nome por observação em `cuidar_dos_nomes()`, a cada 2 s. Só a mudança num objeto já visto conta como renomear, e o objeto que aparece recebe o nome guardado. Isso cobre também quem renomeia por fora do produto. Só controle grava: fone e teclado seguem com o nome no pareamento.

A conferência da `-02` achou um objeto sem chave, criado no mesmo caminho antes da volta seguinte, lido como «ela apagou o nome»: o nome saía do disco. «Apagou» passou a valer só em objeto com `pareado is True`. E oito curas que nenhuma régua mordia ganharam régua. Entre elas estão as guardas de `Connected` e de `HID_PHYS`, sem as quais sairia a chave de um controle no ar.

Réguas: `tests/unit/test_o_pareamento_que_nao_chega_devolve_os_botoes.py` e `tests/unit/test_o_nome_do_aparelho_volta_na_reconexao.py`, 81 funções ao todo, parametrizadas nos três adaptadores e nos seis pares.

**No install:** no primeiro arranque do daemon, a volta dos nomes grava o `nome` de cada controle que já tem Alias próprio no BlueZ, com uma escrita por controle. O `maquina.json` continua na versão 1.

## 4. O «Mapa das Conexões» grava o que se declara

**`O-MAPA-DAS-CONEXOES-NO-PRODUTO-01`.** O editor da entrada grava no `maquina.json` dois campos opcionais em `mapa.portas[N]`:

- `liga`: «hub» ou «extensor», e «Direto» é a ausência;
- `usb`: 2 ou 3.

Os dois chegam pelos gestos `entrada-o-que-tem` e `entrada-velocidade` do pacote novo `src/hefesto_dualsense4unix/interface/pacotes/a12_mapa_das_portas.py`, e quem os escreve são `declarar_a_ligacao` e `declarar_a_velocidade`, em `src/hefesto_dualsense4unix/integrations/entrada_a_entrada.py`. A velocidade tem um dono só, `velocidade_da_entrada` (`src/hefesto_dualsense4unix/integrations/mapa_das_portas.py`), em três degraus: primeiro o aparelho USB 3 medido, depois a velocidade declarada, depois o par da placa. O hub declarado desenha 4 entradas (`ENTRADAS_DO_HUB_DECLARADO`, `src/hefesto_dualsense4unix/interface/arranjo_desta_maquina.py`).

A conferência achou que nenhuma régua clicava: três mordidas passavam verdes, entre elas «quem nunca declarou nada não grava nunca». Por isso escreveu a régua que percorre, no WebKit, o clique, a mensagem do piloto, o pacote, o disco e a página relida. Também devolveu «Leitura de Exemplo · 24/08/2026» ao cabeçalho, só quando a página mostra o gabinete de exemplo. Sem essa linha, quem nunca mapeou via os aparelhos de outra pessoa sem aviso nenhum, o que era a volta do defeito de 11/09.

**A `-02` fechou o que a `-01` deixou:**

- o «Examinar» relê a máquina. O gesto `reexaminar` devolve o arranjo; o piloto o tira da resposta (`_o_arranjo_relido`, em `src/hefesto_dualsense4unix/interface/hefesto_vivo.py`) e o entrega pela mesma porta da abertura. Isso vale só em `mapa-das-portas.html`, porque na 08 `arranjo` é nome de campo. A primeira entrega também saiu do fio da janela;
- o id do aparelho deixou de ser o caminho. `identidades` (`src/hefesto_dualsense4unix/interface/arranjo_desta_maquina.py`) é um blake2s com sal do processo sobre o serial e o modelo, e nada do id vai a disco. A conferência achou dois erros e os curou guardando `id → (caminho, modelo)` e pondo o modelo na semente do caminho. O primeiro: um receptor parado virava «Mudou de Lugar» quando o gêmeo sem serial chegava ou saía, porque o modelo deixava de ser único. O segundo: outro modelo que chegava no caminho de quem saiu herdava o id. Na cena medida, «4 Aparelhos Mudaram de Lugar» (um deles falso) virou 3;
- o «Hub» fica cinza onde há aparelho direto que não é hub, e a Sugestão nunca manda um aparelho para dentro do hub desenhado. Antes ela chegava a dizer «Mova o Dongle Bluetooth da Entrada 5 para a 5.4»;
- a ponta do extensor grava como `{filha_de: N, …}` e herda a velocidade da mãe. «Direto» na mãe apaga a ponta que só o editor escreveu.

Réguas: `tests/unit/test_a_entrada_declarada_vence_o_firmware.py` (11 testes) e `tests/unit/test_o_examinar_diz_quem_mudou_de_lugar.py` (20 testes). Parte deles roda no WebKit, sob `xvfb-run`.

## 5. O «Aplicar» soltava o teto da economia

**Medido antes da cura:** com o P2 em economia, o «Aplicar» o deixava em `(209,104,0)`, no Médio, com gatilho 182/45 e sem teto de vibração. A ativação o deixa em `(76,38,0)`, no Fraco, com 73/18 e vibração 0,3. A causa é a mesma da seção 2: `reset_output_overrides` troca o mapa inteiro, camada do perfil inclusive. Com a cura, o «Aplicar» dá o mesmo que a ativação.

**A cura** (`O-APLICAR-NAO-SOLTA-O-TETO-DO-CONTROLE-01`):

- o rascunho leva `player_led_brightness`, global e por controle, e a segunda viagem do rodapé saiu;
- `DraftApplier.apply` passa o payload por `_com_o_teto_da_economia` (`src/hefesto_dualsense4unix/daemon/ipc_draft_applier.py`). A leitura do teto fica num lugar só, `_a_vista_da_economia`, sobre o mesmo dono da ativação (`manager._perfil_na_economia`);
- o controle em economia é publicado na camada do perfil. Na camada de quem usa, o teto ficava preso depois de desligar a economia, porque a reaplicação vem como `system`;
- para o controle em economia, o «Salvar» grava no disco o brilho que já estava no disco, e não o teto de 30%;
- um `None` do `apply_draft` recusa com `sem_resposta_do_daemon()`; antes, o botão piscava verde;
- a procedência da cor mora no `DraftConfig` (`_com_a_procedencia_da_mesma_cor`, em `src/hefesto_dualsense4unix/app/draft_config.py`).

A conferência achou que a cor do controle em economia perdia o número, porque entrava como legado pela camada do perfil. O P4 no tom do número 2 acendia a cor do número 4 depois do «Aplicar». A cura foi fazer `lightbar_para_o_numero` viajar no rascunho. Quatro mordidas não mordiam; com a seção nova da régua, as 15 mordem.

Régua: `tests/unit/test_o_aplicar_nao_solta_o_teto_do_controle.py`, 23 testes.

**O inverso**, ligar a economia depois de um «Aplicar», deixava o P2 a 70% e no Médio. A rodada 3 o curou: só quem entra na economia solta, da camada de quem usa, a luz, o `player_led_brightness` e os dois gatilhos. Isso é feito por `_soltar_o_teto_de_quem_entra` (`src/hefesto_dualsense4unix/daemon/lifecycle.py`) com `clear_user_output_fields` (`src/hefesto_dualsense4unix/core/backend_pydualsense.py`). A conferência achou que o Modo Nativo escapava, porque a saída do nativo reaplicava por cima da camada. Por isso a soltura passou para antes do `if self._native_mode`, em `reaplicar_se_a_economia_mudou`.

## 6. A Gestão de Controles publicada

`A-GESTAO-DOS-CONTROLES-NO-PRODUTO-01` publicou as páginas 08 e 09 com o desenho aprovado:

- a seção se chama «Gestão de Controles». A «Sugestão de Conexão» nunca some, tem a altura do exame e numera cada ajuste e a proposta da central. Sem ajuste, diz «Nada a mudar agora.»;
- cada cartão (P1 a P4) tem o Perfil de Desempenho: «Tudo Ligado», «Bateria Longa» ou «Personalizado». Ele passa pelo mesmo `machine.declare` e pelo mesmo dono da aba Sistema. No disco, vira `controles[uniq].economia` com None, True ou False, sem mudar o esquema. «Eu escolho» virou «Personalizado»;
- a «Bateria Longa» global acende os quatro cartões e recusa o clique que a contradiz;
- o controle no USB com chave BT naquele adaptador diz «USB» na linha do rádio. «Microfone por rádio» virou «Microfone por BT», pela decisão de 21/09;
- os botões do perfil cabem inteiros a partir de 1181 px; antes viravam reticências a 1212 px.

**O que a conferência achou.** A Conexões não via o que a Sistema acabara de gravar. `_declaracao` guardava o `maquina.json` até um gesto da própria 08, e um «Tudo Ligado» no P2 gravava por cima da «Bateria Longa» dele. A régua dava verde porque o dublê relia o disco a cada chamada, mais frouxo que o produto. A cura relê o arquivo pelo selo `(inode, mtime_ns, tamanho)` (`_selo_da_declaracao`, em `src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py`). A conferência também achou:

- o palpite «Teclado?» repetia o nome acessível do botão, e ganhou `aria-hidden`;
- no primeiro tique, a Sugestão dizia «Pareie o P2 no adaptador », sem o nome;
- o `mypy` e a `acentuacao` estavam vermelhos, e o `--rapido` não roda nenhum dos dois.

Réguas: `tests/unit/test_o_perfil_de_desempenho_e_de_cada_controle.py`, `tests/unit/test_a_sugestao_de_conexao_diz_cada_ajuste.py` e `tests/unit/test_o_controle_no_usb_diz_usb_na_linha_do_radio.py`. No território de 300 arquivos: 5395 verdes e 0 falhas. Nos portões completos, 63 verdes.

## O que as rodadas repetem

- **Tirar uma leitura da trava desfaz a fila entre gestos.** A cura do congelamento abriu três regressões de ordem, e só a conferência as viu.
- **O dublê mais frouxo que o produto deu verde duas vezes:** com o daemon de mentira que não recusava como a central (a zona morta) e com o disco relido a cada chamada (Conexões × Sistema). Um terceiro, o `radio_de_mentira`, grava Alias `""` literal e também é mais frouxo que o real, mas sem efeito nas réguas de hoje.
- **Régua que não clica não prova gravação:** três mordidas do mapa passavam verdes nos 61 testes do território, porque nenhuma régua clicava.
- **O `--rapido` não é o portão:** `mypy` e `acentuacao` só reprovaram no completo.

## O que ficou aberto

- **O veredito do exame conta ordens, e a Sugestão conta linhas** (`integrations/ordens_da_mesa.cabecalho`). A tela mostra «3 mudanças recomendadas» ao lado de 4 linhas, e «Nada a mudar» em verde ao lado de uma proposta da central.
- **`radio.mover` sem teto em `ponte.TETOS`:** fica com os 250 ms padrão. O clique logo depois do prazo pode passar disso, e o botão treme com o «Conectar» já começado.
- **O Pair que passa dos 60 s** deixa a central ocupada depois de a tela soltar. Quando o Pair volta, a conferência tira a chave recém-feita. É raro.
- **O nome do controle:**
  - apagar não deixa marca, e um adaptador que estava fora da porta volta com o nome velho;
  - um nome acima de 248 bytes gera um aviso no log a cada 2 s;
  - há uma janela de 2 s em que renomear e esquecer a última chave perde o nome;
  - o controle só no cabo não mostra o nome guardado;
  - fone e teclado seguem perdendo o nome com a chave.
- **O mapa:**
  - as entradas do hub desenhado (`5.1…`) não gravam enquanto `utils/maquina._NUMERO_DE_ENTRADA` recusar o ponto;
  - ensinar a entrada pela página (o chip e depois a entrada) não grava, e a frase «Eu Aprendo para Sempre» promete isso;
  - a ponta do extensor, na grade da traseira, cai sob a entrada vizinha (é desenho);
  - `Piloto._carregou` sai cedo quando a mesma página recarrega, e o arranjo não é entregue;
  - o planejador procura o Wi-Fi pelo id `"wifi"` do exemplo e nunca dispara no produto;
  - a regra «aparelho USB 3 vence a declaração» se apoia no `peer` do firmware, que pode estar errado.
- **O legado do «Salvar»:** na prova da rodada 1, a cor do número de P1 e P4, que nunca escolheram cor, foi gravada como override legado.
- **Uma instabilidade de ordem na suíte:** `test_a_faxina_roda_sozinha_e_para_no_fechar` conta 2 fios quando roda depois de `tests/unit/test_mover_um_por_vez.py`. A base dá o mesmo resultado.
- **`docs/data/paridade-gtk-html.csv:328`** ainda diz «Microfone por rádio».
- **A validação com a mão de quem usa, depois do install:**
  - trocar a entrada três vezes com o Mapear aberto, sem nenhum `tique lento` acima de 500 ms;
  - com dois controles, no cabo e no BT, clicar Forte, depois «Aplicar» e depois «Salvar»;
  - ligar os três controles, um em cada adaptador, escolhidos pela lista;
  - renomear, esquecer em todos os adaptadores e conectar de novo.
