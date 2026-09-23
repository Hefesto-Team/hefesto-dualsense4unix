# hefesto-uhid (DKMS) — a fila cheia que ninguém dizia

Módulo `uhid` patchado para **poder dizer** a quem escreve que a fila de saída
encheu, em vez de descartar o report em silêncio.

**O default do módulo é o vanilla.** O parâmetro `backpressure` nasce
desligado; ligado, ele é opt-in de `/etc/modprobe.d/hefesto-uhid.conf`, que
por sua vez só é instalado com `./install.sh --uhid-contrapressao`.

## O defeito, medido

A queixa dela, em 22/09/2026: *«4 controles conectados só um aparece na
interface agora»*. <!-- noqa-acento: citação literal dela -->

A ponte de áudio por rádio do Hefesto escrevia **93,75 reports de 334 B por
segundo, por controle** — ~254 kbit/s de payload ACL cada, e com quatro
controles ~1,0 Mbit/s só de saída num adaptador só. A corrente que isso fecha:

```
a bomba escreve
  -> a fila de saída do uhid enche (31 lugares)
  -> "playstation …: Output queue is full"   (3807 linhas em um minuto)
  -> o socket L2CAP enche
  -> bluetoothd: hidp_send_message() BT socket write error: EAGAIN (11)
  -> a sessão HIDP cai
  -> o daemon perde o hidraw, e o controle some da interface
```

**E nada disso chegava a quem escrevia.** `escrita_recusada` marcou ZERO no
diário do produto enquanto o kernel descartava 400 reports. A razão está em
três linhas de `drivers/hid/uhid.c`:

```c
static void uhid_queue(...)          /* void: o desfecho não volta */
{
        ...
        } else {
                hid_warn(uhid->hid, "Output queue is full\n");
                kfree(ev);           /* o report morre aqui */
        }
}

static int uhid_hid_output_raw(...)
{
        ...
        uhid_queue(uhid, ev);
        return count;                /* <- sempre "escrevi tudo" */
}
```

## A prova, nesta máquina

`patch/provador` (ver **Como reproduzir**) cria um HID de mentira pelo
`/dev/uhid`, **não lê** o `/dev/uhid` — que é o que o rádio saturado faz — e
escreve 80 reports de saída no `hidrawN` que nasce:

| `uhid.backpressure` | aceitas | recusadas | primeira recusa |
| --- | --- | --- | --- |
| de fábrica | 80 | **0** | — |
| patchado, `N` (default) | 80 | **0** | — |
| patchado, `Y` | 29 | **51** | escrita #29, `EAGAIN` |

29 ≈ os 31 lugares da fila menos os eventos de `START`/`OPEN` que já estavam
nela. O kernel registrou **53** descartes na corrida de fábrica — o outro lado
do livro-razão.

## Por que é opt-in, e não default como os vizinhos

Ligar muda a semântica do `write(2)` para **todo** userspace que escreve
report de saída num HID por Bluetooth — o Steam Input inclusive. Software que
trata falha de escrita como *«o aparelho sumiu»* passa a largar o controle no
primeiro engasgo do rádio; e esse era exatamente o defeito que a
`RADIO-AFOGADO-02` curou do NOSSO lado
(`integrations/alto_falante_bt.FILA_CHEIA_DO_KERNEL`), o que mostra como ele é
fácil de ter. Enquanto não for medido com os jogos dela abertos, ninguém leva
a mudança sem pedir.

**O produto está correto sem este módulo.** A cura de primeira ordem é a
`RADIO-AFOGADO-01`: a ponte de som só existe enquanto há som, e com a mesa
parada as escritas vão de 375/s a ZERO. Este módulo é o que sobra para o dia
em que quatro pontes forem LEGÍTIMAS — quatro jogadores com som no controle —,
e aí o teto de ar é alcançado sem que uma única escrita falhe.

**E ele não levanta o teto.** Contrapressão transforma *«a mesa cai»* em *«o
som engasga»*. Isso é muito melhor e não é a mesma coisa.

## Liga e desliga A QUENTE

O parâmetro é `0644` de propósito, e isso importa: **recarregar o `uhid`
derruba todo HID por Bluetooth da máquina**.

```bash
echo 1 | sudo tee /sys/module/uhid/parameters/backpressure   # liga
echo 0 | sudo tee /sys/module/uhid/parameters/backpressure   # desliga
```

## Proveniência

- `uhid.c` = **vanilla v7.1** + `patch/0001-*.patch`. Nada além do patch —
  invariante verificável, e ela foi PROVADA em 22/09/2026:

  ```bash
  cp uhid.c /tmp/prova.c
  patch -R -p0 /tmp/prova.c < patch/0001-*.patch
  sha256sum /tmp/prova.c   # == SHA256_VANILLA_C de patch/BASELINE
  ```

- O vanilla se confere sem baixar o tarball de 234 MB do fonte do kernel:

  ```bash
  curl -fsSL 'https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/plain/drivers/hid/uhid.c?h=v7.1'
  ```

- Código C e comentários do patch em **inglês**, como os vizinhos: a convenção
  do subsistema HID, visando o upstream.

## Como reproduzir a medição

O provador vive em `scripts/ensaios/uhid_contrapressao.py`. Ele cria e destrói
um aparelho de mentira (`ff:ff:ff:00:00:fe`) e **não encosta em controle
nenhum da mesa**:

```bash
sudo python3 scripts/ensaios/uhid_contrapressao.py
```

Para medir os dois lados é preciso trocar o módulo, e **isso derruba todo HID
por Bluetooth por alguns segundos** — os controles caem e voltam com o PS.
