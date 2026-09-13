# SISTEMA-BOTOES-01 — cada botão da aba Sistema faz o que diz

Agente: opus, papel IMPLEMENTA · árvore `hefesto-voo/SISTEMA-BOTOES-01-opus`, branch
`voo/SISTEMA-BOTOES-01-opus`, nascida de `onda/1309` = `e1c7d96b` (conferido).
Sprint: `docs/process/sprints/2026-09-13-SISTEMA-BOTOES-01-cada-botao-da-aba-sistema-faz-o-que-diz.md`.

`bancada: false`: nenhum gesto foi ao daemon, à Steam, ao Proton ou ao WirePlumber.
Toda janela foi oculta; os perfis foram copiados antes e conferidos por md5 depois
de cada uma das sete corridas do piloto fora da suíte (159 arquivos, iguais em todas).

## O que mudou

| §I | onde | o que mudou |
| --- | --- | --- |
| 1 | `app/actions/daemon_actions.py` · `_systemctl_status_text` | `status --no-pager -n 0`, com a mesma assinatura de um argumento. O painel em repouso não traz mais as linhas do diário do daemon. |
| 2 | `pacotes/a09_sistema.py` · `_PERGUNTA`, `_a_pergunta_venceu`, `_para_o_painel(…, pergunta_de=, fica=)` | O texto que um clique 1 escreve fica marcado como a pergunta daquele gesto. Quando o gesto deixa de estar armado (prazo vencido, outro botão armou ou recusou), o tique seguinte tira a pergunta. Só tira se o painel ainda for ela, e deixa o `fica`: no «Tirar a sobreposição Vulkan» sai só a instrução e o censo continua. |
| 3 | `a09_sistema.py` · `ARMOU`, `_so_armou` | Os seis cliques que só armam devolvem `armou` (gêmea de `hefesto_vivo.CHAVE_DO_CLIQUE_QUE_SO_ARMOU`). O botão pousa sem piscar. |
| 4 | `a09_sistema.py` · `_dica_do_desenho`, `_pergunta_do_botao`, `desligar`, `restaurar_de_fabrica`, `refazer_proton` | O clique 1 escreve no painel o `title` publicado do botão, requebrado em `LARGURA_DA_PERGUNTA`, e `CLIQUE_DE_NOVO`. Nenhuma palavra é nova. O clique 2 chama `_limpar_o_painel()` antes de agir. |
| 5 | `a09_sistema.py` · `_confirmado(…, antes_de_armar=)`, `_porque_o_proton_nao_trava` | A Steam aberta recusa no clique 1, depois de desarmar o que estava armado e antes de armar este, e confere de novo no clique 2. Sem `proton-pin.conf` (arquivo ausente, caminho `None` ou função que levanta), a recusa usa a frase de «esta instalação ainda não tem o Proton pinado» com `como_atualizar_esta_instalacao()`. Não sobe mais `FileNotFoundError` cru. |
| 6 | `a09_sistema.py` · `CONSERTOS`; `aba09.py`; `integrations/storm_doctor.py` · `check_wireplumber` | O `--install` do WirePlumber saiu: o próprio script o chama de gesto contrário ao de ligar o mic (DROPIN-AMBIGUO-01). O `title` perdeu as duas promessas que não valiam e ficou «Desliga o Steam Input onde ele atrapalha. Sem senha e sem fechar nada, e com cópia de segurança.». A frase do doctor termina em `PREFIXO_DA_CURA` + `gesto_de_atualizar()`, e não manda mais clicar em «Aplicar correções», que não existe. |
| 7 | `aba09.py` (item e `_CINZAS`), `a09_sistema.py` (gesto, `BOTOES_CINZAS`, `PONTE`, `METODOS`, `PROVAS`, `SEM_ECO`), `gui/aba_sistema.py` (`GESTOS`, `travas`), `scripts/check_cabo_bt_perfil_controle.py`, `docs/data/paridade-gtk-html.csv` | «Ver os plugins» saiu da tela: o botão, a razão cinza e o gesto. A CLI e o IPC ficam. Na paridade, a linha do botão foi de `SO_NO_HTML` para `IGUAL` (nenhum lado lista plugins), com o sinal `D-OS-PLUGINS-APARECEM-ONDE-AGEM` e o veredito antigo guardado com data no `porque`. A linha do «Botão cinza por estado» ganhou nota datada. |
| 8 | `a09_sistema.py` · `_um_chip`, `_linha_do_exame` | O chip sem cor lida perdeu o `title` inteiro. O §I pedia «só o nome da cor», e a sprint caiu aqui: sem cor lida não há nome de cor, e o que a mesa manda é «Não sei», que a régua da base `test_o_chip_sem_leitura_nao_diz_nao_sei_nem_travessao` proíbe no chip. A linha do exame corta texto e `title` em `_exame.PREFIXO_DA_CURA`. |
| 9 | `mockup/09-sistema.html`, `interface/paginas/09-sistema.html` | Regeradas (`09-sistema: OK, 55 divs`) e `--publicar 09`. O diff é só o `title` dos consertos e o botão com o `?` do «Ver os plugins». Antes de publicar, a bancada e o publicado tinham o mesmo md5. |

**A decisão citada é dela e está escrita:** `docs/data/decisoes-dela.csv`, linha
`D-OS-PLUGINS-APARECEM-ONDE-AGEM` (26/08/2026, `quem_decidiu=ela`).

**Fora da posse, e por quê.** Cada um reprovaria a cura, e cada mudança tem nota datada:

- `scripts/check_a_tela_nao_confessa.py`: saiu a chave `a09_sistema.py:ver_plugins ← motivo` de `SEM_LETRA`. O portão confere nos dois sentidos.
- `docs/process/2026-09-03-O-TERCEIRO-NUMERO-a-paridade-com-a-gtk.md`: tabela recontada do CSV. A `09-sistema` foi de `11 IGUAL · 7 SO_HTML · 29%` para `12 · 6 · 32%`, e a `TODAS` de `143 · 59` para `144 · 58`. Ganhou a nota de verificação de 13/09.
- `tests/unit/test_a_saude_do_sistema_diz_o_que_fazer.py`: a régua da frase do WirePlumber cobra `gesto_de_atualizar()` e a ausência de «Aplicar correções».
- `tests/unit/test_aba09_o_exame_cortado_guarda_a_frase_inteira.py`: o inteiro cobrado é o estado, antes do `PREFIXO_DA_CURA`.
- `tests/unit/test_aba09_a_fita_vem_de_cima.py`: o chip sem cor não tem `title`.

**Réguas da posse atualizadas:** `test_a_09_sistema_confirma_em_dois_cliques.py` (Steam
dublada), `test_a_09_sistema_fecha_a_paridade.py` (as duas do `ver_plugins` viraram
`test_ver_os_plugins_saiu_da_aba_com_a_trava_dele`), `test_o_gesto_devolve_para_a_tela.py`
e `test_a_aba_09_sistema_fecha_as_linhas.py`.

**Régua nova:** `tests/unit/test_cada_botao_da_aba_sistema_faz_o_que_diz.py`, com 34 casos.
Uma parte roda sem janela, com dublês. A outra abre o piloto do produto oculto, clica pelo
ouvinte de verdade e lê a trilha do botão, o painel, a tela e o diário.

### A tela, antes e depois

As fotos ficam no rascunho, fora do repositório, porque as de daemon vivo mostram
identidade de fábrica.

| cena | antes (`e1c7d96b`) | depois |
| --- | --- | --- |
| repouso, daemon vivo (`hefesto_vivo --oculta`) | o painel mostra as últimas linhas do diário do daemon; o Avançado tem quatro botões | sem linha de diário (fica o `status` e a identidade); três botões |
| clique 1 do «Parar o serviço» (piloto, dublês) | o botão diz «Confirma?» e o painel continua em repouso | o botão diz «Confirma?» e o painel diz o `title` do botão e «Clique de novo para confirmar.» |
| a pergunta vence (relógio empurrado) | o botão volta ao rótulo e o painel continua pedindo o segundo clique | o botão volta ao rótulo e o painel volta ao repouso |

Medido pelo piloto na tela viva, com a mesa dublê:

- as cinco recusas (`retomar` sem pausa, `atualizar` com a ponte muda, `corrigir-modo` com o serviço pelo sistema, `refazer-proton` com a Steam aberta e o clique 2 de `aplicar-aos-jogos` com jogo aberto) pousam `hef-recusou` sem `hef-deu-certo`;
- nas cinco há zero `.hef-recado`, a frase fica fora do texto visível, de `title` e de `data-hef-dica`, e a linha `[gesto falhou]` vai ao diário;
- os seis cliques que armam não acendem piscada nenhuma e deixam «Clique de novo para confirmar.» no painel;
- a fixação do Proton nunca foi chamada, e a janela da Steam só foi pedida uma vez, no clique 2.

## Qual mordida prova

Cada mordida arrancou a cura, rodou a régua e devolveu a cura. Depois de devolver, a
régua voltou a verde, conferida no próprio relato. O script está no rascunho
(`mordidas.py`).

| # | a cura arrancada | o que reprovou |
| --- | --- | --- |
| 1 | `"-n", "0"` fora do `status` | `test_o_painel_em_repouso_nao_pede_o_diario` (1) |
| 2 | `ARMOU = "armado"` | a chave (1) e a tela: os seis que armam piscaram verde (6) |
| 3 | o clique 1 do `desligar` devolve só os rótulos | sem janela e na tela, os dois casos do Parar (2) |
| 4 | `refazer_proton` sem `antes_de_armar` | os casos do Proton (5) |
| 5 | `_porque_o_proton_nao_trava` sem conferir o `proton-pin.conf` | os três jeitos de faltar o arquivo (3) |
| 6 | o censo das camadas sem `fica` | `test_o_censo_das_camadas_fica_quando_a_pergunta_vence` (1) |
| 7 | `_no_painel` sem `_a_pergunta_venceu()` | a pergunta vencida, a recusa de outro botão, o censo e a tela (4) |
| 8 | o clique 2 do Parar sem `_limpar_o_painel()` | `test_o_clique_2_limpa_o_painel_antes_de_agir` (1) |
| 9 | o `--install` do WirePlumber de volta em `CONSERTOS` | `test_os_consertos_so_rodam_o_vigia_da_steam` (1) |
| 10 | a linha do exame sem o corte em `PREFIXO_DA_CURA` | `test_aba09_o_exame_cortado_guarda_a_frase_inteira.py` (2) |
| 11 | o doctor volta a mandar clicar em «Aplicar correções» | `test_a_saude_do_sistema_diz_o_que_fazer.py` (1) |
| 12 | o chip sem cor volta a ter o `title` da confissão | `test_aba09_a_fita_vem_de_cima.py` (1) |
| 13 | «Ver os plugins» de volta na camada, no gerador e na publicação | a página publicada e a bancada (2) |

**A mordida 13 não mordeu na primeira volta.** Devolvida só ao gerador, ela passou
verde, porque o próprio gerador recusou: `ERRO: 'ver-plugins' não está em
aba_sistema.GESTOS`. A página não mudou e a régua não tinha o que ver. Com a entrada
devolvida também a `GESTOS`, a página foi regerada e publicada, e a régua reprovou.

**Um tropeço meu no script:** nessa volta ele não devolveu `gui/aba_sistema.py`. O
próprio relato acusou (`arvore_igual_a_de_antes: false`). A entrada foi devolvida à
mão, e a regeração seguinte disse `55 divs` e zero `ver-plugins` nas duas páginas.

**A régua nova contra a base inteira** (`e1c7d96b`, extraída no rascunho) dá 27
reprovados e 7 aprovados. Os sete aprovados são o que já funcionava:

- quatro recusas na tela, que já piscavam desde a FRASES-E-DICAS-01;
- o clique 2 do Parar limpando o painel;
- a Steam conferida no clique 2 do Proton;
- a fixação nunca chamada.

**As portas avulsas, verdes na árvore final:**

- `validar-citacoes-de-linha.py --all`: 3289 citações;
- `test_portao_o_par_com_metade_ligada.py`: 16;
- `check_a_tela_nao_confessa.py`, `check_cabo_bt_perfil_controle.py`, `check_o_desenho_aprovado.py` e `check_paridade_gtk_html.py`;
- as catorze réguas da aba Sistema e a nova, cada uma num processo;
- `ruff` nos arquivos mexidos.

## O que NÃO verifiquei

- **Nenhum ato real**: Parar, Ativar e Reiniciar no systemd; a Steam fechando no «Aplicar aos jogos»; a fixação do Proton no `config.vdf`; os scripts de conserto. Tudo foi por dublê, como manda o §R; é a fila da MESA-DE-QUATRO-01.
- **Os botões clicados com o daemon vivo.** Com daemon vivo só fotografei o repouso. Os cliques foram no piloto com a mesa dublê.
- **O `corrigir-modo` num serviço de fato avulso.** A recusa medida é a do serviço pelo sistema.
- **O painel com quatro controles na mesa**: as quatro linhas de identidade no repouso dentro da caixa de agora.
- **A suíte inteira.** Só réguas pontuais, como manda o despacho.

## O que sobrou para o próximo

1. **A pergunta da Steam rola dentro de Detalhes técnicos.** Com três botões a faixa
   Avançado desceu de 136 px para o piso de 110 px, e a pergunta de 6 linhas deixou de
   caber inteira: com `data-hef-rolar="fim"` a instrução aparece e a primeira linha sai.
   O vão de 8 px entre a lista e o painel foi curado na validação (seção abaixo).
2. **O `title` do Parar diz «os 2»** (o `N` do gerador) e agora vira a pergunta do
   painel. Com um controle na mesa, o número está errado.
3. **O repouso ainda mostra a árvore de processos** do `systemctl status`, as linhas
   de `pw-record` e `parec`. O diário saiu, mas é texto técnico no repouso.
4. **Uma dica flutuante sobre a linha «Trocar de perfil ao abrir o jogo»** («Enxergando
   — o Hefesto vê qual programa está na frente») aparece nas duas fotos de daemon vivo,
   antes e depois. Não é desta sprint.
5. **A âncora `SO_NA_08`** de `test_nenhuma_frase_de_aviso_chega_a_tela.py` ainda diz
   que o «O que fazer» da 09 é de outra sprint. Agora a 09 também corta, e quem cobra
   é `test_aba09_o_exame_cortado_guarda_a_frase_inteira.py`. A âncora pode passar a
   valer nas duas.

## O que a validação refez e corrigiu

Papel VALIDA/CORRIGE, na mesma árvore e na mesma branch. Nada foi aceito pelo relato:
o que está abaixo foi medido de novo.

**Posse.** O diff cabe na posse, nas páginas geradas, na entrega e na sprint, fora os
cinco arquivos declarados acima. Cada um dos cinco foi devolvido à versão da base
`e1c7d96b` sobre o código da branch, e os cinco reprovaram: `check_a_tela_nao_confessa.py`
pela chave órfã do `ver_plugins`, `check_paridade_gtk_html.py` em `numero-publicado`, e
as três réguas pelas asserções velhas. A razão de cada um está medida.

**Botões.** Na 09 publicada: de 19 para 18 `<button>` e de 16 para 15 `data-gesto`; no
`mockup/09`, de 19 para 18. As outras nove páginas estão iguais à base. Nenhum botão novo.

**Mordidas.** Refiz as treze do §V e acrescentei quatro. Cada uma arrancou a cura, rodou a
régua e devolveu pelo `git checkout`, conferida por sha256 e pela árvore limpa. As
dezessete reprovaram:

| a cura arrancada | o que reprovou |
| --- | --- |
| as treze da tabela acima | as mesmas réguas, com os mesmos números |
| `_so_armou` sem pôr a chave `armou`, com a constante intacta | os cinco cliques 1 sem janela e os seis na tela (11) |
| o clique 1 do «Aplicar aos jogos» sem marcar a pergunta | a pergunta vencida na tela (1) |
| `_porque_o_proton_nao_trava` sem conferir a Steam | a recusa de outro botão, os dois cliques do Proton e a recusa na tela (4) |
| `_dica_do_desenho` devolvendo vazio | as três perguntas que são o `title`, sem janela e na tela, e a largura (7) |

Na mordida do chip sem cor, `test_nenhuma_frase_de_aviso_chega_a_tela.py` passou com a
confissão de volta: quem a pega na 09 é só `test_aba09_a_fita_vem_de_cima.py`.

**Achado 1, corrigido em `175c2338`: a régua da altura reprovava só na branch.**
`test_tela_tres_a_altura_e_a_caixa_alta.py` (o pedido dela de 08/09, em
`docs/process/sprints/2026-09-08-TELA-TRES-01-a-altura-o-selo-e-a-caixa-alta.md` §1)
reprovou com «a lista termina em 608px e a caixa em 616px» em duas voltas alternadas com
a base, que passou nas duas. A régua cobra as duas bordas juntas E o piso de 110 px, então
nenhuma das duas saídas da pergunta de cima passava. A causa: o piso morava no `.log`, um
filho absoluto que não conta para a fileira. Ele passou à célula do grid (`.col-log` em
`aba09.py`), e a 09 foi regerada e publicada. Medido no Chrome, na página publicada:
antes, 136 e 136 px com quatro botões; depois, 110 e 110 px, as duas bordas no mesmo y.
MORDIDA: `min-height:0` de volta na célula, regerar e publicar, e a régua reprova com os
mesmos 608 e 616; devolvido idêntico. A pergunta da Steam rola 13 px no Chrome.

**Achado 2, corrigido em `5da9ed83`: quatro frases no presente ainda davam o «Ver os
plugins» como vivo.** O `html_faz` da linha «Botão cinza por estado» da paridade, as
docstrings de `test_a_09_sistema_sai_do_desenho.py` e de
`test_a_09_sistema_fecha_a_paridade.py` (que diziam que `travas()` tranca o
`ver-plugins`) e a nota de `_PAINEL`. As notas datadas ficam.

**Visto e mantido, com a razão:**

- **O sinal da linha «Ver os plugins carregados» é uma citação em comentário.** O portão
  aceita por desenho (`ocorre`, em `scripts/check_paridade_gtk_html.py`: «Muitos sinais
  deste CSV são citações por desenho»). Quem impede o botão de voltar é
  `test_o_ver_os_plugins_nao_esta_em_pagina_nenhuma`.
- **O `title` do Parar diz «os 2», e esse `title` agora é a pergunta no painel.** O número
  é o `N` do gerador e já estava na dica; o §D manda o `title` publicado, sem palavra nova.
- **A dica «Enxergando» sobre «Trocar de perfil ao abrir o jogo»** aparece antes e depois.

**Tela.** Fotos `--oculta`, no rascunho e fora do repositório, porque as de daemon vivo
mostram identidade de fábrica. O repouso com o daemon vivo foi fotografado na base
extraída, na branch e depois da cura da altura. Os cliques seguiram o roteiro da régua
nova, na base e na branch.

- **Na base:** as linhas do diário no painel, quatro botões no Avançado, e a pergunta
  vencida da Steam no painel com o rótulo já de volta.
- **Na branch:** nenhuma linha do diário e três botões. O «Confirma?» do Parar põe no
  painel o `title` e «Clique de novo para confirmar.». Quando a pergunta vence, o painel
  volta ao repouso.

**Réguas vizinhas.** 95 arquivos de `tests/unit/` que leem o que a sprint mudou, um
processo cada: 94 verdes e a da altura (achado 1). Depois da cura, as 32 que leem a 09 ou
o gerador, todas verdes. Os perfis, 159 arquivos, saíram iguais por md5 depois de cada
corrida.

**Portões:** `bash scripts/portoes.sh` sobre a árvore com os dois `fix` e esta seção
escrita, depois do `git add -A`: todos verdes, 60 portões.

**O que a validação não verificou:** o clique na janela com o daemon vivo (só o repouso);
a rolagem da pergunta da Steam no WebKit depois da cura (medida no Chrome); e nenhum ato
real, nem de systemd, nem da Steam, nem do Proton, nem dos scripts de conserto.
