# Abrir a janela no início da sessão

A janela do Hefesto não abre sozinha quando o controle é ligado. O que existe é
uma unidade opcional, `hefesto-dualsense4unix-gui-hotplug.service`, que abre a
janela uma vez, no início da sessão gráfica. O nome é de um mecanismo antigo,
que abria a janela ao ligar o controle e foi retirado porque piorava as quedas do
USB.

Se a janela já estiver aberta, a unidade só a traz para a frente.

A janela fica aberta depois que a unidade termina. A unidade é de execução única
(`Type=oneshot`) e termina assim que o lançador sai, e por isso leva
`KillMode=process`: o systemd encerra só o processo principal e deixa a janela
de pé. Com o padrão dele, a janela do início da sessão morria junto com a unidade.

## Ligar e desligar

O instalador pergunta, com a resposta padrão «não». Para decidir sem a pergunta:

```bash
./install.sh --enable-hotplug-gui    # instala e liga
./install.sh --no-hotplug-gui        # pula o passo
```

Depois da instalação:

```bash
systemctl --user enable hefesto-dualsense4unix-gui-hotplug.service
systemctl --user disable hefesto-dualsense4unix-gui-hotplug.service
```

O `./uninstall.sh` a remove.

## Limitações

- Sem `systemd-logind` a sessão gráfica não avisa o systemd, e a unidade nunca
  roda ([ADR-009](../adr/009-systemd-logind-scope.md)).
- Reconectar o controle no meio da sessão não reabre a janela. Abra pelo menu
  de aplicativos, pelo ícone da bandeja ou com `hefesto-dualsense4unix-gui`.
