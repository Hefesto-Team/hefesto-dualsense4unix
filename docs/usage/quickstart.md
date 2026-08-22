# Quickstart — o DualSense funcionando em 2 minutos

Guia de primeira vez: plugou o controle, quer usar. O detalhe de cada assunto
está nas páginas apontadas no fim de cada seção.

---

## 1. Antes de começar

- **Linux com `systemd-logind`.** O caminho deste guia — o `install.sh` na forma
  `native` — instala dependências **só por `apt`**: família Debian, e é ela que
  este guia cobre (Pop!\_OS, Ubuntu, Debian, Mint). Em Fedora, Arch ou Nix há
  pacote da distro, e **nenhum foi rodado com controle real**; o instalador
  avisa isso logo no passo 1 e não aborta.
- **Python 3.10 ou maior**.
- **DualSense** (PS5) ou **DualSense Edge**, por USB ou Bluetooth.

O que rodou de verdade, e em que versão de cada peça, está em
[as versões em que isto funciona](versoes-validadas.md).

Bibliotecas do sistema (uma vez):

```bash
# Debian/Ubuntu/Pop!_OS
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 \
                 gir1.2-ayatanaappindicator3-0.1 libhidapi-hidraw0 \
                 libhidapi-dev libudev-dev libxi-dev

# Fedora
sudo dnf install python3-gobject gtk3 libappindicator-gtk3 hidapi-devel \
                 libudev-devel libXi-devel

# Arch
sudo pacman -S python-gobject gtk3 libappindicator-gtk3 hidapi \
                libudev libxi
```

---

## 2. Instalar

```bash
git clone https://github.com/Hefesto-Team/hefesto-dualsense4unix.git
cd hefesto-dualsense4unix
git checkout v0.9.4.5
./install.sh
```

> **Clone pela tag, não por branch.** As branches de trabalho recebem commits
> durante a sessão e não são ponto estável para instalar.

> **Ligue o DualSense no cabo USB antes de abrir a janela pela primeira vez.**
> Instalar não precisa do controle; usar, sim. É pelo cabo que o Hefesto elege o
> controle principal, cria o gamepad virtual e liga gatilhos, LEDs, toque,
> giroscópio e microfone de uma vez. Por rádio, o microfone custa cerca de 35%
> dos relatórios de input, porque o áudio divide a mesma fila do HID.

Sem flags o instalador mostra um seletor de formato (native · flatpak ·
appimage · deb), pede a senha de administrador uma vez e conduz os passos com
padrões seguros — dá para sair apertando Enter em todas as perguntas.

Todas as formas de instalar, o que o instalador toca no sistema e como reverter:
[`instalacao.md`](instalacao.md). Sandbox e limitações do Flatpak:
[`flatpak.md`](flatpak.md).

---

## 3. Primeira abertura

Abra pelo menu de aplicativos (ou `hefesto-dualsense4unix-gui` no terminal). A
janela tem dez abas: **Início, Status, No jogo, Gatilhos, Lightbar, Rumble,
Perfis, Sistema, Emulação, Navegação**.

Plugue o DualSense por USB ou pareie por Bluetooth. A aba **Status** mostra
conexão, transporte, bateria, perfil ativo, sticks, gatilhos e a grade de botões
ao vivo — tudo isso é o controle **físico**. Para saber o que está chegando ao
**jogo** (giroscópio, vibração, gatilho, luz, clique do touchpad e som do
controle), a aba é a **No jogo**.

> A janela **não** abre sozinha ao plugar o controle: as regras udev que faziam
> isso foram retiradas (elas abriam o controle via `hidraw` a cada evento e
> pioravam o storm `-71`). O que existe hoje é uma unit opcional que abre a
> janela no **início da sessão gráfica** — ver [`hotplug.md`](hotplug.md).

O que cada aba faz, uma a uma: [`interface.md`](interface.md).
Pareamento Bluetooth: [`bluetooth.md`](bluetooth.md).

---

## 4. Escolher o que o controle faz agora

Na aba **Início**, o seletor "O que o controle faz agora" tem três modos:

- **Controlar o PC** — o controle vira mouse e teclado.
- **Jogar pelo Hefesto** — o jogo vê um controle virtual (co-op local, vibração
  e perfis passam pelo Hefesto).
- **Conexão Nativa (Sony)** — o Hefesto solta o controle e o jogo fala direto com
  o hardware (gatilhos adaptativos nativos, giroscópio, touchpad).

Comparação completa e quando usar cada um: [`modos.md`](modos.md).

---

## 5. Navegação (mouse e teclado pelo controle)

Na aba **Navegação** há **dois interruptores irmãos e independentes**: "Emular
mouse" e "Emular teclado". Eles ficam disponíveis no modo **Controlar o PC**.

| Botão                          | Ação                       |
|--------------------------------|----------------------------|
| Cruz (X) ou L2                 | Botão esquerdo             |
| Triângulo ou R2                | Botão direito              |
| R3 (clique no analógico dir.)  | Botão do meio              |
| Círculo                        | Enter                      |
| Quadrado                       | Esc                        |
| D-pad                          | Setas do teclado           |
| Analógico esquerdo             | Movimento do cursor        |
| Analógico direito              | Rolagem vertical/horizontal|

Os controles deslizantes de velocidade do cursor e da rolagem ficam na mesma
aba. E o **touchpad do controle move o cursor sozinho**, pelo sistema, sem
depender de nenhum destes interruptores e em qualquer um dos três modos — ver
[`modos.md`](modos.md#o-touchpad-é-touchpad-do-sistema).

> **A aba se chamava "Navegação DSX"**; o rótulo na tira é só **"Navegação"**
> desde a PALAVRA-01 — "DSX" é o nome de outro programa.

### Escrever texto: o teclado na tela do L3

**Nenhum atalho de fábrica digita uma letra.** Os de fábrica são atalhos:
Super, PrintScreen, Alt+Tab, Alt+Shift+Tab, Enter, Delete e Backspace. O único
caminho de fábrica para **escrever texto** é o teclado na tela:

| Gesto | Ação |
|---|---|
| **L3** (clique no analógico esquerdo) | abre o teclado na tela |
| **R3** (clique no analógico direito)  | fecha o teclado na tela |

Ele precisa de um programa do sistema, e desde 10/08/2026 o `install.sh` o
instala sozinho, **sem flag**: `wvkbd` em sessão Wayland, `onboard` em X11. Se
você instalou antes dessa data ou pulou o passo:

```bash
sudo apt install wvkbd     # sessão Wayland (COSMIC, GNOME Wayland, KDE Wayland)
sudo apt install onboard   # sessão X11
```

O `onboard` digita por XTEST e, numa sessão Wayland, abriria sem digitar fora do
XWayland — por isso a escolha sai da sessão viva, e não de preferência. Sem
nenhum dos dois, o L3 **avisa na tela** em vez de não fazer nada, e você não
precisa reiniciar o daemon depois de instalar: o Hefesto reconsulta o sistema a
cada 10 segundos.

---

## 6. Perfis

O rodapé opera em tudo de uma vez (gatilhos, LEDs, rumble, navegação):
**Aplicar**, **Salvar Perfil**, **Importar**, **Restaurar Default**.

Perfis pré-instalados na aba **Perfis**: `navegacao`, `fps`, `aventura`, `acao`,
`corrida`, `esportes` e o slot editável `meu_perfil`. O autoswitch por janela
ativa troca sozinho (abrir o navegador → `navegacao`; abrir um jogo de corrida →
`corrida`) — e o cadeado da aba Início desliga esse automatismo quando você quer
mandar na mão.

Escrever um perfil do zero, com critérios de autoswitch:
[`creating-profiles.md`](creating-profiles.md).

---

## 7. Deu errado?

`hefesto-dualsense4unix doctor` roda o diagnóstico ponta a ponta e diz o que
está faltando. Sintomas conhecidos, causa e cura estão em
[`troubleshooting.md`](troubleshooting.md) (e em
[`troubleshooting-8bitdo.md`](troubleshooting-8bitdo.md) para controles
genéricos).

---

## 8. Onde ir em seguida

- **Hotkeys do controle** (PS + D-pad para trocar de perfil): [`hotkeys.md`](hotkeys.md)
- **Linha de comando**: [`cli.md`](cli.md)
- **Integração com mods DSX** (Cyberpunk, Forza, Assetto): [`integrating-mods.md`](integrating-mods.md)
- **COSMIC / Wayland**: [`cosmic.md`](cosmic.md)
- **Métricas Prometheus**: [`metrics.md`](metrics.md)
- **Decisões de arquitetura**: [`../adr/`](../adr/)

---

*"O martelo não constrói o templo. Ele só ensina a pedra a lembrar da forma."*
