# ADR-019: WirePlumber default-source — validar o default *ativo*, não o *configured*; rebaixar vs. desabilitar

**Status:** aceito

## Contexto

`FEAT-WIREPLUMBER-DUALSENSE-NOT-DEFAULT-SOURCE-01` entregou o fix do "controle
sequestra o microfone": um drop-in que rebaixa a prioridade do mic do DualSense
(`priority.session/driver = 50`) + um reset one-shot que reelege uma fonte
não-DualSense e reinicia o WirePlumber. Marcada DONE.

O estudo de campo de 2026-05-28
(`docs/research/2026-05-28-dualsense-dropout-usb-e-wireplumber-source.md`) expôs
duas armadilhas:

1. **`configured` ≠ `ativo`.** O WirePlumber guarda dois conceitos:
   `default.configured.audio.source` (preferência persistida, em
   `~/.local/state/wireplumber/default-nodes`) e o default **ativo** (o que
   `pactl get-default-source` / o `*` no `wpctl status` reportam). A política de
   seleção só promove uma fonte *configured* se ela estiver **available**. Foi
   observado o `configured` apontando para a onboard enquanto o **ativo**
   permanecia no DualSense.

2. **Rebaixar não vence escassez.** A prioridade só governa a eleição
   *automática* entre fontes **available**. Com a webcam (mic real) desconectada
   e o jack onboard vazio, o DualSense era a *única* fonte de captura available —
   e o WirePlumber, corretamente, usou-o como default apesar do `priority = 50`.
   A onboard (`priority = 2009`) perdeu por estar indisponível, não por
   prioridade.

Consequência: o script imprime "fonte padrão reeleita" e o `doctor.sh` inspeciona
a chave `configured`, ambos podendo reportar sucesso/`[ OK ]` enquanto o controle
**é** o mic ativo. O critério de aceite original ("`wpctl status` mostra
`Audio/Source` != DualSense") não se sustenta sob escassez — e a própria "Nota
para o executor" da FEAT já apontava que o `configured` é "o efeito imediato
garantido", confundindo-o com o objetivo real (o ativo).

## Decisão

1. **A pós-condição canônica de sucesso é o default ATIVO**, não o `configured`.
   Tanto `fix_wireplumber_default_source.sh` quanto `doctor.sh` passam a verificar
   `pactl get-default-source` (ou o `*` parseado do `wpctl status`), nunca apenas
   a chave persistida.

2. **Rebaixar permanece o comportamento default** (decisão da mantenedora na
   FEAT original: manter o mic do controle usável para seleção manual). Não muda.

3. **Relatório honesto sob escassez.** Quando, após o reset, o default ativo
   ainda for o DualSense *porque ele é a única fonte available*, o script **não**
   declara sucesso: emite um aviso explícito ("DualSense é a única fonte de
   captura disponível — conecte a webcam/mic, ou use `--disable-source`") e o
   `doctor.sh` reporta um estado intermediário (não `[ OK ]`, não `[FAIL]` cego)
   distinguindo "rebaixado, mas único" de "rebaixado e desbancado".

4. **Modo disable opt-in.** A variante `node.disabled = true` (já comentada no
   drop-in) vira um modo de instalação opt-in (`--disable-source`), para quem
   quer o mic do controle nunca available. Documenta o trade-off: perde-se o
   headset-jack/captura do controle. Ver `FEAT-WIREPLUMBER-DISABLE-SOURCE-MODE-01`.

## Consequências

(+) Fim do falso-positivo: o usuário e o `doctor.sh` passam a saber se o controle
**realmente** deixou de ser o microfone do sistema, não só se a preferência foi
gravada.

(+) A distinção "rebaixado mas único" vs. "rebaixado e desbancado" transforma um
falso `[ OK ]` numa orientação acionável (plugar mic / usar disable).

(+) O modo disable cobre o caso de uso "sem webcam garantida" sem tornar o
rebaixamento (mais conservador) obsoleto — os dois coexistem por opção.

(−) Verificar o ativo é mais frágil que ler um arquivo: depende de `pactl`/`wpctl`
disponíveis e do WirePlumber ter assentado após o restart (pode exigir um pequeno
settle/poll). Aceitável; o parse já existe no script.

(−) `--disable-source` remove a captura do DualSense por completo — um usuário
que quisesse usar o headset do controle precisaria reverter. Mitigado por ser
opt-in e reversível (comentar/remover o drop-in).

(−) Em ambientes headless (postinst de `.deb`/Arch rodando como root) não há
sessão WirePlumber do usuário para inspecionar o ativo — a checagem do ativo só
é confiável no contexto do usuário (`doctor.sh`/`install.sh --with-...`). O
postinst continua se limitando a instalar o asset, como hoje.
