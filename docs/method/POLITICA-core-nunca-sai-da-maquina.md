# Política — o core dump do `bluetoothd` NUNCA sai desta máquina

- **Escrita em:** 05/08/2026
- **Origem:** [RADIO-ABERTO-01](../process/sprints/arquivados/2026-08-04-RADIO-ABERTO-01-o-que-instalamos-por-padrao-anula-a-autenticacao.md), S3/E7
- **Portão que a protege:** `tests/unit/test_radio_aberto_e7_e9.py`

---

## A regra, em uma linha

**Para relatar upstream vai o BACKTRACE (`coredumpctl info`), nunca o core.**

## Por quê

`scripts/bt_crash_capture.sh --on` grava `kernel.core_pattern` — que é
**global do kernel** — para capturar o crash de heap do `bluetoothd`.

**Um core do `bluetoothd` contém todas as LinkKeys, LTKs e IRKs residentes**,
mais os MACs e os nomes de todos os aparelhos da casa. A LinkKey BR/EDR é a
credencial de rádio: quem a tem se autentica como aquele par.

### O cenário que quase aconteceu — e é o motivo desta página existir

Esta casa quer mandar patch upstream sobre o crash de heap do BlueZ. **O
caminho natural de um relatório de corrupção de heap é anexar o core** — e o
mantenedor upstream vai pedir.

Anexar = publicar as credenciais de rádio de todos os aparelhos dela num
rastreador público, para sempre, com o histórico do bug.

Não é hipótese: é o próximo passo óbvio de um trabalho que já está na fila.

## O que fazer, então

| situação | o que enviar |
|---|---|
| relatório upstream (BlueZ, distro) | `coredumpctl info bluetoothd` — backtrace, registradores, mapa de memória |
| pedido explícito de core pelo mantenedor | **recusar**, oferecer backtrace completo com símbolos de depuração instalados (`debuginfod`) |
| análise local | `coredumpctl gdb bluetoothd` — na máquina, sem cópia |
| arquivamento | nenhum: o core é apagado ao fim da janela |

E a janela de captura **se fecha sozinha**: desde a E8, `--on` arma um timer
transitório que roda o `--off` em 8 horas (`HEFESTO_BT_CAPTURE_HORAS` ajusta).
O desligamento deixou de depender da memória de quem ligou.

## O que o portão reprova

`tests/unit/test_radio_aberto_e7_e9.py` varre os documentos e scripts desta
casa e **reprova qualquer instrução de enviar, anexar ou compartilhar o core**
que não venha acompanhada desta política.

A regra do portão não é *"nunca escreva a palavra core"* — é *"quem instruir a
mandar um core tem de dizer, no mesmo arquivo, por que não se deve"*. Um
documento que discute o risco continua legal; um que diz *"anexe o core no
relatório"* não.

## O que esta política NÃO cobre

- **o journal.** Linhas de log do `bluetoothd` não contêm material de chave, e
  continuam sendo o instrumento de diagnóstico normal desta casa;
- **os snapshots de bond** (`/var/lib/hefesto-dualsense4unix/bt-bonds`). Eles
  **contêm** LinkKeys, e são locais, com permissão de root. Nunca devem ser
  anexados a nada — mas o vetor deles é outro, e está na
  [RADIO-ABERTO-01](../process/sprints/arquivados/2026-08-04-RADIO-ABERTO-01-o-que-instalamos-por-padrao-anula-a-autenticacao.md)
  S4/E10, já curado;
- **um observador de `mgmt`**, que esta casa ainda **não** tem. Se alguém
  escrever um, valem as E4/E5/E6 da sprint: partir em dois, nunca reter o
  frame, `LimitCORE=0`.
