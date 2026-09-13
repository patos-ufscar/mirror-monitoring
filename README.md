# UFSCar Free Software Mirror

> **Where Free Software Meets Free Infrastructure**

A community-powered Linux distribution mirror with fully transparent operations - featuring open-source management, public metrics, and CI/CD deployment. Proudly hosted at the [Federal University of São Carlos](https://ufscar.br) in partnership with [PATOS](https://patos.dev) and [GELOS](https://gelos.club).

🌐 **Mirror URL**: https://mirror.ufscar.br

## 🤝 Community Partnership
This mirror is maintained through the joint effort of:
- [PATOS](https://patos.dev): Free Software Group at UFSCar  
- [GELOS](https://gelos.club): Free Software Group at USP São Carlos

Join our communities to contribute to free software infrastructure!

## 🔧 Technical Infrastructure
- **Operating System**: [NixOS](https://nixos.org) for reproducible, declarative infrastructure
- **Hardware**: Physical server hosted at UFSCar's datacenter  
  - Location: Secretaria Geral de Informática building, São Carlos
  - Connectivity: See https://bgp.tools/as/52888
- **Management**: Fully automated via GitHub CI/CD
- **Transparency**: All configuration and management code is public

## 📊 Live Monitoring & Metrics
We believe in operational transparency:

### Real-time Dashboard
[![Public Dashboard](https://img.shields.io/badge/Live_Metrics-Public_Dashboard-774aa4?logo=datadog&style=flat)](https://p.us5.datadoghq.com/sb/3b4452e8-11b2-11f0-95f9-1ea5f11b227d-7fd00bf61e9d5674c26afe4c9f89bdd1)  
Track real-time performance including:
- CPU/RAM usage & I/O wait
- Network traffic (packets/s, errors)
- Nginx connections & HTTP requests
- Disk usage/latency with future projections
- Storage read/write operations

### Alert System
[![Telegram Alerts](https://img.shields.io/badge/Instant_Alerts-Telegram_Channel-26A5E4?logo=telegram)](https://t.me/mirror_ufscar_br_alerts)  
Receive immediate notifications for system events

## 🛠️ Monitoring Infrastructure
- **Source Code**: [PATOS/mirror-monitoring](https://github.com/patos-ufscar/mirror-monitoring)
- **Deployment**: Automated CI/CD to Google CloudRun

## ✨ Contributing
We welcome community contributions!
- Submit pull requests for mirror configuration
- Improve monitoring in [PATOS/mirror-monitoring](https://github.com/patos-ufscar/mirror-monitoring)
- Join PATOS/GELOS meetings
- Suggest new metrics or visualizations

## 🌐 Why "Free Meets Free"?
- **Free Software**: We mirror only Free Software distributions
- **Free Infrastructure**: Entire stack is Free Software
- **Free Access**: Public metrics and management
- **Free Community**: Jointly maintained with PATOS & GELOS

[![UFSCar](https://img.shields.io/badge/Hosted%20by-UFSCar-00529B?style=flat&logo=university)](https://ufscar.br)
[![PATOS](https://img.shields.io/badge/Partner-PATOS-8CA1AF?style=flat)](https://patos.dev)
[![GELOS](https://img.shields.io/badge/Partner-GELOS-3D85C6?style=flat)](https://gelos.club)

## Execução dos monitores

`poetry install --no-root` instala as dependências fixadas em `poetry.lock`.
Execute `poetry run python main.py` com `TOKEN` e `CHAT_ID` no ambiente e
credenciais padrão do Google (ADC) com acesso ao Firestore. O agendador externo
continua responsável pela execução a cada 15 minutos.

O processo principal lê **um documento**, `mirror-monitoring/state`, uma única
vez por ciclo, e grava esse mesmo documento no máximo uma vez ao final, apenas
se o estado mudou. Não há leituras por monitor, consultas de coleções,
transações ou tentativas automáticas adicionais do SDK. São 96 leituras e no
máximo 96 gravações por dia, considerando 96 ciclos sem execuções extras.

Cada monitor recebe somente seu estado em JSON e devolve a mensagem e o novo
estado. Os monitores continuam em subprocessos separados, com prazo total de
90 segundos por monitor. Exceções, encerramentos abruptos, respostas inválidas
e estouros de prazo preservam o estado anterior e não interrompem os demais.
Para adicionar um monitor, implemente `check(state)` em `monitors/` e registre
seu nome em `MONITORS`, em `main.py`; permissões de execução não são necessárias.

O estado só é confirmado após o envio bem-sucedido da mensagem ao Telegram.
Uma falha de envio mantém o estado anterior daquele monitor. Falhas no
Firestore são reportadas; uma falha de leitura permite executar os monitores
sem estado, mas impede a gravação para não sobrescrever dados desconhecidos.
Falhas de persistência ou interrupções entre envio e gravação podem repetir
alertas no próximo ciclo. O processo termina com código 1 se houver falhas.

Configure o agendador/Cloud Run para **não sobrepor execuções** (uma tarefa por
execução e prazo do job inferior a 15 minutos). A gravação do documento completo
pressupõe um único escritor; ela não usa transações para disputar o estado.
Reexecuções automáticas do job também contam como novos ciclos para as cotas.

### Alterações nos alertas

- **openSUSE:** guarda o rating de cada protocolo. Notifica a primeira observação
  problemática e as transições seguintes, inclusive recuperação (`SOLVED`).
  Repetições do mesmo rating não geram mensagens. Falhas na obtenção ou leitura
  da seção Health continuam visíveis e não apagam o último estado válido.
- **Arch Linux 32:** consulta o [JSON oficial](https://archlinux32.org/mirrors/status/json/)
  e espera duas entradas para `mirror.ufscar.br`. Detecta `last_sync` ausente ou
  com mais de 12 horas, quedas de disponibilidade e recuperação. Usa o timestamp
  de sincronização diretamente, pois o campo `delay` observado não corresponde
  às unidades anunciadas na página. Dados do serviço com mais de duas horas
  também geram alerta. Os limites ficam em `monitors/archlinux32.py`.
- **Debian:** compara o `archive version` numérico na mesma
  [tabela de status](https://mirror-master.debian.org/status/mirror-status.html).
  Suprime apenas avisos de idade de `mastertrace`, `archive version` e
  `last update` quando ftp-master e os syncproxies principais têm dados válidos
  e nenhum mirror listado apresenta versão mais nova. Um upstream alternativo
  mais atualizado mantém o alerta, mesmo com C3SL atrasado. Dados ausentes ou
  inválidos dos servidores principais impedem a supressão; erros e a coluna
  `extra` continuam gerando alertas. A lista mínima de referências fica em
  `primary_upstreams`, em `monitors/debian.py`.

### Validação

Execute `poetry run python -m unittest discover -s tests -v`. Os testes cobrem
cotas de operações, transições, falhas de envio/persistência, isolamento real de
subprocessos e supressão conservadora no Debian, sem acessar Firestore ou enviar
mensagens. O build Docker também executa os testes com Python 3.13 antes de
produzir a imagem. As dependências de Telegram são usadas diretamente por meio
de `python-telegram-bot`; `telegram-send` não é mais necessário.
