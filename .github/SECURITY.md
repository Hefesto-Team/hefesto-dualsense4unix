# Política de segurança

Achou uma falha de segurança no Hefesto? Conte para nós em particular. Assim a correção sai antes de a falha ser conhecida por todo mundo.

## Como relatar

**Não abra uma issue pública** para uma vulnerabilidade. Há dois caminhos, e o primeiro é o melhor:

1. **Pelo próprio GitHub**, em privado: na página do repositório, aba **Security**, botão **Report a vulnerability** (Relatar uma vulnerabilidade). Só quem mantém o projeto vê o relato, e a conversa e a correção acontecem ali.
2. **Por e-mail**, se você não tem conta no GitHub: `andre.dsbf@gmail.com`, com o assunto `[Hefesto SEC] resumo curto`.

Ajuda muito o relato trazer:

- o que acontece e o que um atacante conseguiria fazer;
- os passos para reproduzir, a partir de uma instalação nova;
- a versão (`hefesto-dualsense4unix --version`), a distribuição e o kernel (`uname -a`);
- uma prova mínima do problema, se tiver, e a correção que você sugere, se tiver.

## O que acontece depois

1. Respondemos confirmando o recebimento em até 7 dias.
2. Em até 14 dias dizemos se o problema se confirmou e qual a gravidade.
3. A correção é feita em particular e sai numa versão nova, com o seu nome no aviso se você quiser.
4. Só então o aviso fica público, pela página de segurança do repositório e pelo `CHANGELOG.md`.

Não há programa de recompensa em dinheiro: o Hefesto é feito por pessoas, sem financiamento.

## Versões que recebem correção

Só a versão mais recente. Não há correção para versões antigas.

| Versão | Recebe correção |
| ------ | --------------- |
| 0.9.x, a mais recente | Sim |
| anteriores | Não |

## O que conta como falha de segurança

- Escapar ou ganhar poder pelo socket local do Hefesto (`$XDG_RUNTIME_DIR/hefesto-dualsense4unix/hefesto-dualsense4unix.sock`).
- Mandar comandos de fora da máquina pela porta UDP de compatibilidade com o DSX (`127.0.0.1:6969`) ou pelas métricas (`127.0.0.1:9090`, quando ligadas).
- Ler ou escrever, sem permissão, arquivos de `~/.config/hefesto-dualsense4unix/`, ou sair da pasta por um nome de perfil montado de propósito.
- Regras do udev instaladas pelo Hefesto que deem acesso a mais do que o controle.
- Um controle virtual criado pelo Hefesto com efeito em outra conta do computador.

## O que não conta

- Falhas do kernel Linux, do GTK, do WebKit, do BlueZ ou de outras dependências: relate a quem mantém cada uma.
- Ataque que precisa de acesso físico ao computador além do controle, ou de outro programa já rodando como você.
- Derrubar o serviço entupindo o socket local, que só aceita quem já está na sua conta.
- A privacidade do protocolo Bluetooth do controle, que é da Sony.

## Chave PGP

Não há. Se o relato precisar de canal cifrado, peça pelo primeiro contato e combinamos o jeito sem mandar o conteúdo antes.

## Avisos publicados

Nenhum até agora. Cada aviso passa a constar na aba Security do repositório.
