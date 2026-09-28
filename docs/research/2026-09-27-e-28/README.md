# O registro técnico de 27 e 28/09/2026

O que se mediu, a causa achada, o que se decidiu e o que ficou aberto em 27 e
28/09/2026, para quem desenvolve o Hefesto. Cada documento é um tema; a data de
cada medida está no próprio texto, e os de 07 a 10 registram medidas de 26/09.

## Os documentos

| nº | documento | o que traz |
|---|---|---|
| 01 | [A manhã de 28/09](01-a-onda-de-28-09-o-modo-o-som-o-salvar-e-a-raiz.md) | as seis frentes de 28/09: o modo com um dono, o pad do modo Xbox, o servidor de som com um leitor só, o Salvar que lê o perfil, a raiz limpa e o dono das formas do endereço |
| 02 | [O plano das ondas](02-o-plano-das-ondas.md) | as sprints abertas de 26 a 28/09 postas em sete ondas por posse de arquivo e por dependência lógica, e o que a conferência derrubou no plano |
| 03 | [A auditoria para terminar o produto](03-a-auditoria-para-terminar-o-produto.md) | nove auditorias só de leitura sobre as sprints de 26 e 27/09 e o produto inteiro, e a síntese que as põe numa ordem de trabalho |
| 04 | [A história, a raiz e os ganchos](04-a-historia-a-raiz-e-os-ganchos.md) | o rastro de ferramenta de automação no GitHub, na história, na raiz e no pacote, e as travas de máquina e de git que deveriam segurá-lo |
| 05 | [O básico, os jogos e a memória](05-o-basico-os-jogos-e-a-memoria.md) | o protocolo do básico, a bancada de jogos da noite de 27/09, o que falta para outra máquina reproduzir o produto e o ensaio da memória do engasgo |
| 06 | [A triagem do CI](06-a-triagem-do-ci.md) | os vermelhos do CI do `dev` reproduzidos num clone limpo: a causa de cada um, a cura, a mordida |
| 07 | [O engasgo e as camadas Vulkan](07-o-engasgo-e-as-camadas-vulkan.md) | o engasgo periódico do Sackboy e a «cura» por camada Vulkan, que nunca teve medição de cura |
| 08 | [A háptica pelo rádio](08-a-haptica-pelo-radio.md) | por que a vibração do PRAGMATA não chegou ao controle pelo Bluetooth, e a cura do portão «quem joga» |
| 09 | [As Conexões](09-as-conexoes.md) | as quatro rodadas que levaram a aba 08, o «Mapa das Conexões» e o «Aplicar» do rodapé ao produto |
| 10 | [O mapa que ela corrige](10-o-mapa-que-ela-corrige.md) | por que o «Mapa das Conexões» identificou errado as entradas USB de uma máquina real, e o que a tela ganhou para corrigir |
| 11 | [O Freestyle](11-o-freestyle.md) | a tabela do ultra e o Freestyle por cima dos perfis de jogo, e por que nada disso entrou no `dev` |

## Como ler

- **A sprint e a decisão se citam pelo ID** (`O-MODO-XBOX-NAO-E-QUEDA-02`,
  `D-2709-…`). O texto delas mora nos documentos de processo da casa, que não
  viajam com o clone; o ID é o que se procura lá.
- **O código se cita por `arquivo:linha`.** A linha é a do dia da medida: as
  curas que vieram depois moveram linhas. Na dúvida, procure o nome da função.
- **O grau de cada afirmação** vem marcado onde o documento o usa: medido (comando
  rodado, saída guardada), lido (código, commit, diário) ou inferido (conclusão
  sem medida direta).
- **Onde a árvore de hoje já difere, vale a árvore.** `git log --since=2026-09-27
  --format='%h %s'` diz o que entrou depois.
- **Cada documento termina em «O que ficou aberto»**, e é ali que está a fila que
  estes dois dias deixaram.
