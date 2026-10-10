# ADR-021: modificações por processo

**Status:** aceito · **Data:** 2026-10-09
**Supera:** o [ADR-017](017-plugin-system.md) para tudo o que se instala de fora. O ADR-017 segue
valendo para a receita local de quem escreve o próprio plugin.

## Contexto

O único canal de código de terceiro era o plugin do ADR-017: um `.py` solto, carregado DENTRO do laço
do serviço, sem manifesto, sem versão de API, sem permissão, sem origem e sem isolamento.

Medido em 09/10/2026 com um plugin cujo `on_tick` dorme 200 ms: cada tique do laço levou 200 a 201 ms,
contra 16,7 ms a 60 Hz. O vigia do `PluginsSubsystem` só desliga um plugin depois de três tiques lentos,
e um `while True` num gancho nunca devolve: o vigia nem chega a rodar. Os controles de todos os
jogadores congelam juntos.

O IPC principal (`daemon/ipc_server.py`) também não serve de porta para terceiro. Ele é pergunta e
resposta, não empurra evento, não sabe quem pergunta, e cada método vale tudo.

## Decisão

Uma modificação é uma pasta com o manifesto `hefesto-mod.json` na raiz. Quando ela leva código, ele
roda como **processo filho do serviço** e fala com o serviço só pela **porta das modificações**, com as
permissões que a pessoa aceitou.

1. **O manifesto** (`mods/manifesto.py`) é JSON lido por pydantic com `extra="forbid"`. É JSON porque o
   projeto aceita Python 3.10, que não tem `tomllib`.
   - Campos: `id`, `nome`, `versao`, `api` (faixa como `">=1,<2"`), `licenca` (SPDX), `descricao`,
     `tipos`, `processo.executar`, `permissoes`, `opcoes`, `lancador`, `tema`, `aparelhos`.
   - Fora da faixa de `API_DAS_MODIFICACOES = 1`, a modificação não sobe. A recusa é uma frase:
     ««Nome» pede a porta >=2, e este Hefesto fala a 1.»
   - `opcoes` é o bloco das escolhas que a tela mostra no ajuste de cada modificação: `escolha`,
     `ligado` ou `numero`.
2. **As permissões**, uma palavra cada, aparecem antes de ligar:
   - `ler:<tópico>`;
   - `escrever:luz|vibracao|gatilho`;
   - `rede:nenhuma|local|internet`;
   - `bluetooth`, `lancador`, `tema` e `aparelhos`.

   Toda escrita leva o `uniq`, porque escrever em todos é proibido (BROADCAST-PROIBIDO-01). Ela também
   nunca entra num canal que o jogo está escrevendo naquele controle. Uma atualização que pede permissão
   nova desliga a modificação até o novo «sim».
3. **A porta** é `$XDG_RUNTIME_DIR/hefesto-dualsense4unix/mods.sock`, com modo `0600`, e nunca o socket
   principal. O contrato está em [porta-das-modificacoes.md](../protocol/porta-das-modificacoes.md).
   - A entrada exige duas coisas: a ficha aleatória de cada execução e o `SO_PEERCRED` do processo que o
     supervisor criou (ou de um descendente dele).
   - Cada assinatura é uma fila do barramento que descarta o evento mais antigo. Uma modificação lenta
     perde eventos velhos e nunca atrasa o tique.
4. **O supervisor** (`mods/supervisor.py`) obedece ao registro `mods.json`.
   - Cada filho roda num grupo próprio, com `PR_SET_PDEATHSIG`.
   - **Com `bwrap`**, o filho roda numa caixa:
     - a raiz é só de leitura e a `HOME` nasce vazia;
     - o código é só de leitura e os dados são graváveis;
     - do diretório de execução aparece só a porta;
     - `--unshare-net` entra quando a rede é `nenhuma`;
     - o barramento do sistema fica escondido sem `bluetooth`, e o `/dev` real fica escondido sem
       `aparelhos`.
   - **Sem `bwrap`**, o filho roda sem caixa, e o estado diz isso numa linha.
   - Um filho que cai volta três vezes, esperando 1, 2 e 4 s. Na quarta queda ele fica «parou», com a
     última linha do diário.
   - Parar é mandar `SIGTERM` ao grupo do PID criado e, no fim do prazo, `SIGKILL`. Nunca por nome.
5. **A linha de comando** é `hefesto-dualsense4unix mod instalar|atualizar|listar|permissoes|ligar|desligar|remover`.
   - **De git**, a modificação vem por `git clone --depth 1`, com `GIT_TERMINAL_PROMPT=0` e as
     credenciais que a máquina já tem. O Hefesto nunca guarda senha.
   - **De uma pasta**, a origem é «local».
   - O commit instalado é a identidade da modificação.
   - «Oficial» exige uma tag assinada que o `git verify-tag` confere contra `CHAVES_OFICIAIS`, a lista
     de chaves que o produto carrega. O endereço sozinho não basta. Hoje a lista está vazia, então nada
     instala como «oficial» até o time publicar a chave.
6. **Cada modificação ocupa três lugares**, todos em `utils/xdg_paths.py` e no censo de
   `utils/memoria_dos_controles.py`:
   - o código, em `~/.local/share/hefesto-dualsense4unix/mods/<id>/`;
   - os dados e o diário, em `~/.local/state/hefesto-dualsense4unix/mods/<id>/`;
   - a linha no registro, em `~/.config/hefesto-dualsense4unix/mods.json`.

   `mod remover` para o processo, apaga e confere: só fecha verde quando os três lugares estão vazios.

A porta não sabe de transporte: vale para P1 a P4, por cabo e por rádio, e cada evento e cada escrita
levam o `uniq`.

## Consequências

- Um `while True` numa modificação gasta o processo dela, não o tique do serviço.
- As escritas passam pelos mesmos handlers do IPC (`led.set`, `rumble.set`, `trigger.set`). A política
  de cada canal (Modo Nativo, alvo fora da mesa, teto da vibração) continua com um dono só.
- O que a caixa garante depende do `bwrap` da máquina. Sem ele, a permissão de rede ainda aparece antes
  do «sim», mas não é imposta.
- O `uninstall.sh` ainda não conhece os lugares novos.
