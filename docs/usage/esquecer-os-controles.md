# Esquecer os controles

Para ver como o Hefesto se comporta na primeira vez que um controle é
conectado, sem perder o que ele já sabe:

```bash
hefesto-dualsense4unix esquecer-controles --seco      # só mostra o que faria
hefesto-dualsense4unix esquecer-controles             # guarda e esquece
hefesto-dualsense4unix esquecer-controles --restaurar # devolve
```

Nada é apagado. O que o Hefesto lembra dos controles é **movido** para uma pasta
datada, e o `--restaurar` o põe de volta, byte a byte.

## O que sai e o que fica

| Sai | Fica |
|---|---|
| a ordem dos números dos jogadores, as máscaras e os nomes de cada controle, os ajustes por controle dentro dos perfis, as versões antigas dos perfis, os lugares dos adaptadores e o diário do Bluetooth | os perfis, os jogos, os lançadores e as preferências |
| com privilégio, os pareamentos Bluetooth **dos controles** e as cópias deles | o fone, o teclado e o mouse pareados |

A parte do sistema pede privilégio pelo `sudo -A`, quando há `SUDO_ASKPASS`, ou
pelo `sudo -n` (depois de um `sudo -v` no mesmo terminal). Sem privilégio, o
comando recusa antes de mover qualquer coisa. Para mover os pareamentos, o
Bluetooth para por alguns segundos, e os aparelhos caem e voltam sozinhos.

## Onde fica guardado

- `~/.local/state/hefesto-memoria-guardada/<data>-controles/`
- `/var/lib/hefesto-memoria-guardada/<data>-controles/`, a parte do sistema,
  que só o root lê porque leva as chaves de pareamento

As duas ficam fora das pastas do Hefesto, e o `./uninstall.sh --purge-config`
não as leva. Depois de devolver, a pasta do sistema continua com as chaves
antigas: apague-a quando não servir mais.

## Devolver

Sem uma pasta indicada, o `--restaurar` usa a mais nova que ainda não foi
devolvida. Quem esqueceu duas vezes desfaz na ordem certa repetindo o comando.

- O que estiver no lugar vai antes para `<pasta>/depois-do-teste/`, e o
  comando diz o que sobrescreveu.
- O que o teste criou onde antes não havia nada também vai para
  `depois-do-teste`: devolver é deixar como estava.
- A pasta guardada fica, e dá para devolver de novo.

**O pareamento é a exceção.** O DualSense guarda uma chave de pareamento só. Se
ele foi pareado de novo durante o teste, a chave antiga morreu no controle, e o
`--restaurar` não a põe por cima do pareamento novo.

## O que o comando não alcança

- O que o serviço guarda só em memória (os números vistos, a cor lida): o
  comando reinicia o serviço, e isso se perde.
- O que outros programas lembram: o volume e a saída padrão de cada aparelho no
  servidor de som, e os controles que a Steam conhece.
- O nome dos adaptadores Bluetooth, que é do computador, não do controle.
