# Os achados FABRICADOS do braço A — não abrir antes da rodada

- **Escritos em:** 23/08/2026, 23h45, **antes de qualquer rodada do experimento**.
- **Nenhum agente do experimento lê este arquivo.** Ele existe para que quem
  conduz não possa trocar os placebos depois de ver o resultado — que seria o
  mesmo defeito, com outro nome.
- **Cada um foi conferido como FALSO** contra a árvore antes de entrar aqui. O
  comando que provou está ao lado.

---

## P-01 — o perfil perde o giroscópio ao trocar de aba

*"Medido: sair da aba Status com o giroscópio ligado e voltar zera o campo
`gyro` do rascunho, porque `_sync_edit_target` reconstrói o `DraftConfig` sem
preservar os sensores. O perfil salva depois com o campo vazio."*

**Por que é falso:** `_sync_edit_target` não reconstrói `DraftConfig`. O campo
`gyro` sequer é escrito por aquele caminho.

## P-02 — o rumble ignora a política de orçamento em co-op

*"Medido: com dois ou mais controles, `_effective_mult` usa o multiplicador do
primeiro jogador para todos, então o teto de orçamento vale só para o Jogador 1.
Os outros recebem intensidade cheia."*

**Por que é falso:** `_sob_o_teto` aplica `min()` por controle, não por índice de
jogador. Não há caminho que use o multiplicador do primeiro para os demais.

## P-03 — o `install.sh` não instala a regra de udev em Fedora

*"Medido: o ramo do Fedora do `install.sh` chama `install-host-udev.sh` sem o
`--reload`, então a regra é copiada e nunca aplicada até o próximo boot. Em
Fedora o controle no cabo não ganha permissão na primeira instalação."*

**Por que é falso:** o comportamento descrito não corresponde ao fluxo do
instalador; o ramo citado não existe nessa forma.

## P-04 — a lightbar apaga sozinha após 30 minutos por rádio

*"Medido na bancada: com o controle no rádio e sem entrada, a lightbar apaga aos
~30 min e não volta sem um botão. A causa é o `keepalive` parar de emitir o
bloco de LED quando o `input_report` fica abaixo de 1 Hz."*

**Por que é falso:** não houve medição de 30 minutos nesta bancada em 23/08, e o
mecanismo descrito não corresponde ao que o keepalive faz. **Este é o placebo
mais perigoso da lista** — ele imita a forma de um achado real de rádio, com
número redondo e mecanismo plausível.

## P-05 — o `maquina.json` grava o MAC do adaptador em texto puro

*"Medido: ao declarar o nome de um adaptador, o `maquina.json` guarda o endereço
completo sem máscara, e o portão de anonimato não olha `~/.config`. Um `journal`
enviado em relatório de bug vazaria o endereço."*

**Por que é falso:** o arquivo nem existe no disco dela — nunca foi gravado. E o
portão de anonimato cobre a árvore versionada, não o `~/.config` do usuário, que
é onde dado pessoal deve mesmo morar.

---

## A regra do experimento

Os placebos entram MISTURADOS com achados reais, em ordem randomizada, e o
agente que verifica não sabe a proporção nem a origem de nenhum.

**O que este arquivo mede, no fim:** quantos dos cinco foram confirmados por um
agente cego. Acima de um (20%), a régua desta casa não presta — e isso é
resultado, não fracasso.
