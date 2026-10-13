# ADR-022: UDP na porta 26760 para compatibilidade com emuladores (DSU)

**Status:** aceito

## Contexto
Azahar, Dolphin e Cemu leem toque e movimento de um servidor DSU (cemuhook) em UDP, por padrão em `127.0.0.1:26760`. O caminho pelo SDL não entrega o touchpad do DualSense ao Azahar e depende de o nó de movimento parear; o DSU leva os dois por um caminho que não depende do SDL. O Hefesto já lê toque e movimento do controle (`daemon/sensor_hub.py`), então o servidor só traduz.

## Decisão
Escutar UDP em `127.0.0.1:26760` e falar o protocolo descrito em `docs/protocol/o-protocolo-dsu.md`: versão, portas e dados, com a inscrição por cliente (IP, porta de origem) e o vencimento de 5 s. O servidor **nasce ligado** (decisão dela, 26/09/2026, `D-2609-O-SERVIDOR-DSU-NASCE-LIGADO`), e a máquina o desliga com `"servidor_dsu": {"ligado": false}` no `maquina.json`. O slot é o número do jogador; quem está em «Controlar o PC» não publica (`D-2609-CONTROLAR-O-PC-NAO-PUBLICA-NO-DSU`). Enquanto houver cliente inscrito, o nó «Touchpad» fica com o dedo guardado para o jogo (`D-2609-O-DEDO-FICA-NO-JOGO-ENQUANTO-O-EMULADOR-ESCUTA`).

## Consequências
- **Sem autenticação**, como a porta 6969 do DSX (ADR-003): quem alcança a porta lê o toque e o movimento dos controles. O que contém o estrago é o bind em loopback, fixo em `127.0.0.1`; `0.0.0.0` e IPv6 ficam fora. O servidor só **lê**: não escreve no controle, e a vibração do protocolo não é implementada.
- **O preço de nascer ligado:** a porta fica aberta mesmo para quem não usa emulador, e o leitor de toque e de movimento só trabalha enquanto há cliente (a demanda vence em 5 s). Porta ocupada não derruba o daemon: o subsistema entra em `_failed_subsystems` e o aviso diz de quem é a porta.
- Mesmo limite de taxa do DSX (global 2000 pacotes/s, 1000 por IP).
- A tela do servidor DSU fica para uma sprint própria, na sessão dos desenhos.
