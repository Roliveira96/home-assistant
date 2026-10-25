# Home Assistant — Casa

Configuração versionada do Home Assistant da casa, rodando em Docker no notebook, com acesso remoto pela Cloudflare Tunnel.

- **Versão:** 2026.6.4 (imagem `ghcr.io/home-assistant/home-assistant:stable`)
- **Endereço local:** http://localhost:9999 (porta definida em `config/configuration.yaml`)
- **Zigbee:** integração ZHA com o dongle Sonoff Zigbee 3.0 USB Dongle Plus V2 (EZSP), mapeado como `/dev/ttyUSB0`
- **Outras integrações:** Tuya, Bluetooth, Google Cloud, Met (previsão do tempo), go2rtc

## Estrutura

```
home-assistant/
├── docker-compose.yml   # Home Assistant + cloudflared
├── .env.example         # modelo do .env (token do túnel)
├── config/              # pasta /config do container
│   ├── configuration.yaml
│   ├── automations.yaml # editado também pela interface
│   ├── scripts.yaml
│   ├── scenes.yaml
│   └── blueprints/
└── README.md
```

### O que vai e o que não vai para o git

Vão para o git apenas os arquivos de configuração em YAML e os blueprints. Ficam **fora** (ver `.gitignore`):

| Fora do git | Motivo |
|---|---|
| `.env`, `config/secrets.yaml` | tokens e senhas |
| `config/.storage/` | usuários, tokens de acesso, integrações e dispositivos configurados pela interface |
| `config/.cloud/`, `config/image/` | dados de conta e imagens enviadas |
| `*.db`, logs, `.cache/`, `deps/`, `tts/` | dados de execução, gerados pelo HA |
| `config/backups/`, `*.tar` | backups (protegidos pelo backup do próprio HA) |

> O git guarda a **configuração**, não o **estado**. Para restaurar tudo (dispositivos, integrações, histórico), use o backup do Home Assistant (seção [Backup e restauração](#backup-e-restauração)).

## Como subir

```bash
cd ~/home-assistant
cp .env.example .env      # preencha o TUNNEL_TOKEN (ver Cloudflare Tunnel)
docker compose up -d
```

Sem o túnel configurado, deixe `COMPOSE_PROFILES` vazio no `.env` (ou não crie o `.env`) e só o Home Assistant sobe.

Comandos úteis:

```bash
docker compose logs -f homeassistant
docker compose restart homeassistant
docker compose pull && docker compose up -d   # atualizar
```

Antes de reiniciar após editar YAML, valide a configuração em **Ferramentas de desenvolvedor → YAML → Verificar configuração**.

## Migração da instalação antiga (fazer uma vez)

O container antigo foi criado com `docker run` usando o caminho de exemplo da documentação, `/caminho/do/seu/ha/config`. A ideia é passar a usar `~/home-assistant/config`. Os arquivos são do root, por isso os comandos usam `sudo`.

1. Conferir se as automações mudaram desde a cópia para o repositório (se houver diferença, copie de novo antes de seguir):

   ```bash
   sudo diff /caminho/do/seu/ha/config/automations.yaml ~/home-assistant/config/automations.yaml
   ```

2. Parar o container e copiar o restante (estado, bancos, Zigbee). O `--ignore-existing` preserva os YAML do repositório, que já têm os ajustes do túnel:

   ```bash
   docker stop homeassistant
   sudo rsync -a --ignore-existing /caminho/do/seu/ha/config/ ~/home-assistant/config/
   ```

3. Remover o container antigo (os dados continuam na pasta antiga) e subir pelo compose:

   ```bash
   docker rm homeassistant
   cd ~/home-assistant && docker compose up -d homeassistant
   ```

4. Abrir http://localhost:9999 e conferir login, dispositivos Zigbee, Tuya e automações.
5. Só depois de alguns dias funcionando, apagar a pasta antiga: `sudo rm -rf /caminho` (e a cópia antiga em `~/config`).

## Cloudflare Tunnel (acesso de qualquer lugar)

O `cloudflared` abre uma conexão de saída até a Cloudflare, então **não é preciso abrir porta no roteador** nem ter IP fixo. Domínio: `rmo.dev.br` (DNS na Cloudflare). Endereço: **https://casa.rmo.dev.br**.

1. No painel da Cloudflare (dash.cloudflare.com): **Networking → Tunnels → Create a tunnel**. Nome: `casa` → **Create Tunnel**.
2. Escolha **Docker** e copie só o token do comando exibido (o texto depois de `--token`, começa com `eyJ`). Não rode o comando; coloque o token no `.env`:

   ```
   COMPOSE_PROFILES=tunnel
   TUNNEL_TOKEN=<token>
   ```

3. Em seguida, na aba **Routes** do túnel: **Add route → Published application**:
   - Subdomain: `casa` · Domain: `rmo.dev.br`
   - Service URL: `http://localhost:9999`
4. Subir o túnel (a tela da Cloudflare espera a conexão; depois clique em **Continue**): `docker compose up -d cloudflared` e acompanhar com `docker compose logs -f cloudflared`.
5. No Home Assistant, em **Configurações → Sistema → Rede**, preencher a URL da Internet com `https://casa.rmo.dev.br`.

O `configuration.yaml` já tem `use_x_forwarded_for` e `trusted_proxies` (127.0.0.1 e ::1). Sem isso, o HA responde `400 Bad Request` às requisições que chegam pelo túnel.

### Segurança

- Ativar **autenticação em dois fatores** no perfil de cada usuário do HA, já que a página de login ficará exposta na internet.
- Opcional: proteger com **Cloudflare Access**. Atenção: o Access bloqueia o app Companion do celular, a não ser que se configure uma regra de bypass ou mTLS.

## Painel "Casa" (tela inicial)

`config/dashboards/alarme.yaml` (YAML, URL `/dashboard-alarme`) é a **tela inicial padrão** do HA para todos os usuários (`frontend/set_system_data` → `core.default_panel = dashboard-alarme`; também dá para trocar em Configurações → Painéis). Duas abas:

| Aba | Conteúdo |
|---|---|
| **Casa** | badges (alarme, pessoas/animais/campainha hoje, luz do corredor, Zigbee fora do ar só quando houver); Alarme (armar/desarmar, modo noite); Campainha (última vez, toques, testar, luz); Hoje (pessoa/animal/disparos e gráfico 24 h); Registro do alarme armado; Baixar registro e últimos eventos |
| **Ajustes** | sons no notebook e testes; classificação pessoa × animal; detecções por sensor; toques da campainha (48 h) |

## Alarme

`alarm_control_panel.alarme_casa` usa a plataforma `manual` (definida em `configuration.yaml`), sem código:

| Modo | Atraso para armar | Uso |
|---|---|---|
| Armar ausente (`armed_away`) | 30 s (tempo para sair) | ninguém em casa |
| Armar em casa (`armed_home`) | imediato | à noite, com gente em casa |

Disparado, fica em `triggered` por 5 min e volta para armado.

### Humano ou animal (temos gatos)

Os sensores pegam os gatos, então cada detecção é classificada:

- **Possível humano**: dois sensores **diferentes** detectam dentro da *janela de confirmação* (padrão 2 min), **ou** o mesmo sensor fica detectando sem parar pelo *tempo de presença* (padrão 60 s; os PIR ZG-204Z ficam sempre 30–40 s ligados por detecção, por isso o padrão não pode ser 30 s).
- **Possível animalzinho**: detecção isolada que não se confirma.

Peças:

| Entidade | Função |
|---|---|
| `input_number.alarme_janela_confirmacao` | janela para o segundo sensor (min) |
| `input_number.alarme_tempo_presenca` | presença contínua que conta como humano (s) |
| `input_number.alarme_intervalo_aviso_animal` | intervalo mínimo entre notificações de animal (min) |
| `binary_sensor.deteccao_recente_*` | template: fica ligado enquanto o sensor detecta e pela janela depois (não dá para usar `last_changed`, que muda também quando o HA reinicia) |
| `counter.eventos_possivel_humano` / `counter.eventos_possivel_animal` | contagem do dia, zerada à meia-noite |

### Som no notebook

Com o alarme armado (exceto no modo noite) e `input_boolean.alarme_som_notebook` ligado, o notebook toca:

| Classificação | Script | Som | Volume |
|---|---|---|---|
| Possível humano | `script.alarme_som_pessoa` | escolhido em `input_select.alarme_som_pessoa` (Ding-dong, Mensagem, Login, Despertador), 2 vezes | 60% |
| Possível animalzinho | `script.alarme_som_animal` | `bell`, 1 vez, no máximo a cada "Intervalo entre avisos de animal" | 80% |

O painel tem os botões **Testar som de pessoa** e **Testar som de animal**. O `ding-dong.wav` (em `config/sounds/`) foi sintetizado com o `ffmpeg`.

Como funciona: o container monta o socket PulseAudio do PipeWire (`/run/user/1000/pulse`) e os sons do sistema (`/usr/share/sounds`); o `shell_command.alarme_tocar_som` (variáveis `file` e `volume`) toca com o `ffmpeg` do container. O `ffmpeg` encerra ~1,8 s antes de o áudio terminar e o PipeWire descarta o que ainda está no buffer; por isso o comando acrescenta 3 s de silêncio no fim e as repetições são feitas num único comando (`loops`, via `-stream_loop`). O volume final também depende do volume do sistema (`wpctl get-volume @DEFAULT_AUDIO_SINK@`, hoje 50%). O linger do usuário está ativo, então o PipeWire sobe mesmo sem login.

### Modo noite (automático)

- **00:00**: se estiver desarmado, arma em `armed_night` (arma na hora). Um "ausente" armado manualmente não é alterado.
- **07:30**: desarma, mas só se estiver no modo noite.
- À noite há gente em casa dormindo: **sem som no notebook**; **possível humano** liga a lâmpada e notifica o celular; **possível animalzinho** só vai para o registro (sem notificação).
- Também ficam quietos entre 00:00 e 07:30: o aviso de Zigbee indisponível (fica para o lembrete das 9h) e o teste de temperatura.

### Radar e a confirmação de humano

O Sensor de passagem novo (radar mmWave) pulsa a cada ~61 s (10 s ligado), então ele está quase sempre como "detecção recente". Com ele confirmando, qualquer gato na Lateral virava "humano" (85 falsos num dia). Por isso, com `input_boolean.alarme_radar_confirma` **desligado** (padrão), o radar não confirma humano nem conta presença contínua: humano exige **Lateral + Fundos** ou presença contínua num PIR. O radar continua aparecendo nos contadores e no registro. Ligue o botão "Radar confirma humano" no painel quando o radar estiver confiável.

### Registro do alarme armado

Toda detecção classificada dispara o evento `alarme_evento` (`tipo`, `sensores`, `armado` e, no futuro, `foto`). O sensor template `sensor.registro_do_alarme_armado` guarda os **50 últimos eventos com o alarme armado** no atributo `eventos` (sobrevive a reinicializações) e o painel mostra a tabela na seção "Registro do alarme armado". No logbook, os eventos com alarme armado vêm marcados com "(alarme armado)".

Todos os ajustes (e a sensibilidade do radar, padrão 4) ficam no painel **Casa**, aba **Ajustes**, seção "Ajustes da classificação". Os eventos classificados aparecem no logbook do painel. Arme e desarme pelo painel ou pelo app do celular (cartão "Painel de alarme").

## Quirks Zigbee próprios

Dispositivos que o ZHA não reconhece sozinho ganham um *quirk* em `config/custom_zha_quirks/` (ativado por `zha: custom_quirks_path` no `configuration.yaml`). Depois de criar ou mudar um quirk é preciso reiniciar o HA.

| Arquivo | Dispositivo |
|---|---|
| `ts0601_tze284_gnpflcoq.py` | Tuya 4-in-1 mmWave (TS0601 `_TZE284_gnpflcoq`), o "Sensor de passagem novo": presença, temperatura, umidade, luminosidade, bateria, sensibilidade e tempo de desvanecimento. Datapoints tirados do Zigbee2MQTT |

## Backup e restauração

- O HA faz backups automáticos em `config/backups/` (fora do git). Os backups são **criptografados**; a chave fica no *kit de emergência*, que deve ser guardado num gerenciador de senhas, **nunca** no repositório.
- Vale copiar os `.tar` para fora do notebook (ex.: HD compartilhado do PS4 ou nuvem).
- Restaurar numa instalação nova: subir o compose com `config/` vazio, e no onboarding escolher **Restaurar de um backup**, informando a chave.

## Automações

As automações atuais ficam em `config/automations.yaml` e podem ser editadas pela interface (o arquivo é regravado pelo HA) ou direto no YAML. Commite depois de alterar pela interface para manter o histórico.

| Automação | O que faz |
|---|---|
| Automação sensor lateral casa | Sensor de presença lateral ocupado após as 18h → liga o interruptor |
| Area Externa | Gatilho de dispositivo entre 18h e 08h → liga o mesmo interruptor |
| Nova automação | Botão pressionado → ainda sem ação (rascunho) |
| Campainha - botão | **Botão Campainha** (seção "Campainha" do painel: última vez, toques hoje, testar, luz e histórico): cada toque → ding-dong completo 2x no notebook, notificação e **luz do corredor por 1 minuto** (`script.campainha_luz_1min`, recomeça a cada toque; não mexe se a luz já estava ligada por outro motivo; não apaga com o alarme disparado). O ZG-101ZL aparece no ZHA como interruptor: 1 clique = `toggle`, 2 cliques = `on`, segurar = `off` (evento `zha_event`) |
| Teste - temperatura abaixo de 19.4 | Medidor do escritório abaixo de 19,4 °C → notificação no celular (teste) |
| Aviso - Zigbee indisponível | Usa o sensor `sensor.zigbee_indisponiveis` (template em `configuration.yaml`, conta os dispositivos ZHA com todas as entidades indisponíveis). Notifica o celular quando o número aumenta e fica assim por 30 min, lembra às 9h enquanto houver algum fora e avisa quando todos voltam |

| Alarme - classificar movimento (humano ou animal) | Cada detecção do Sensor de passagem novo, Lateral casa ou Fundos Casa é classificada (ver [Alarme](#alarme)). Com o alarme armado: **possível humano** dispara o alarme, liga a lampada corredor e notifica com prioridade alta; **possível animalzinho** só notifica, no máximo uma vez por intervalo |
| Alarme - zerar contadores à meia-noite | Zera os contadores de possível humano e possível animalzinho |

Notificações:

| Destino | Quem recebe | Usado em |
|---|---|---|
| `notify.celulares` (grupo, em `configuration.yaml`) | Ricardo (`mobile_app_android_ricardo`) e Jéssica (`mobile_app_android_jessica`) | alarme (humano/animal/disparo) e campainha |
| `notify.mobile_app_android_ricardo` | só o Ricardo | avisos técnicos (Zigbee indisponível, teste de temperatura) e link do download do registro |

Para incluir outro celular: instalar o app Companion, entrar com um usuário do HA e acrescentar o `mobile_app_<nome>` ao grupo `celulares` (exige reiniciar).

## Roadmap

- [x] Projeto versionado com docker-compose
- [x] Migrar o container antigo para o compose (seção [Migração](#migração-da-instalação-antiga-fazer-uma-vez))
- [x] Acesso remoto pela Cloudflare Tunnel (https://casa.rmo.dev.br)
- [ ] Notificações no celular para eventos dentro de um período (ideia abaixo)
- [ ] Monitoramento: avisar quando a máquina ficar offline ou um sensor ficar indisponível (ideia abaixo)
- [ ] Integrar os dispositivos ao Google Home (ideia abaixo)
- [ ] Câmeras IP: foto a cada evento com o alarme armado (ideia abaixo)

### Ideia: avisar quando a máquina ou os sensores caírem

**Motivo:** em 20/10/2026, por volta das 21h, a máquina ficou sem internet. O dongle Zigbee perdeu a conexão às 21:15 e só voltou em 24/10. Foram 4 dias sem automações e sem aviso nenhum.

Os dois casos pedem soluções diferentes:

1. **Máquina offline (sem internet ou desligada):** o HA não consegue avisar, porque está sem rede. É preciso um vigia **externo** do tipo *dead man's switch*:
   - uma automação do HA faz um ping a cada 5 min para um serviço como o [healthchecks.io](https://healthchecks.io) (gratuito), via `rest_command`;
   - se os pings param, o serviço manda a mensagem (Telegram, e-mail ou push).
   - Alternativa: monitorar o endereço público do túnel com UptimeRobot, que também pega o caso do túnel cair.
2. ✅ **Sensor ou Zigbee indisponível (máquina online)** — feito (automação "Aviso - Zigbee indisponível"): uma automação no próprio HA. Gatilho: entidade com estado `unavailable` por mais de 30 min. Ação: notificação no celular. Com isso, o problema de 20/10 seria percebido na mesma noite.

Lembrete: depois de muito tempo sem o coordenador, os sensores a bateria (Tuya TS0201, HOBEIAN ZG-204Z) podem não reconectar sozinhos. Aperte o botão do sensor; se não voltar, pareie de novo pelo ZHA.

### Ideia: notificar o celular quando um evento ocorrer num período

**Objetivo:** quando algo acontecer dentro de uma janela de horário (ex.: sensor de presença da lateral detectar movimento entre 22h e 06h, campainha tocar quando não há ninguém em casa), receber uma mensagem no celular.

Ainda em definição. Pontos a decidir:

1. **Canal da mensagem**
   - **App Home Assistant Companion** (Android/iOS): notificação push nativa, com ações (botões) e imagem da câmera. Precisa do acesso remoto (Cloudflare Tunnel) para funcionar fora de casa. Opção recomendada.
   - **Telegram**: integração nativa por bot; bom para histórico e para mandar para um grupo da família.
   - **WhatsApp**: só por serviços de terceiros (ex.: CallMeBot), menos confiável.
2. **Quais eventos** disparam (sensores de presença, campainha `botao_campainha`, abertura de porta, etc.).
3. **Qual período**: horário fixo, entre pôr e nascer do sol, ou "quando ninguém está em casa".
4. **Anti-spam**: limitar a uma mensagem a cada X minutos por evento.

Esboço com o app Companion (o nome do serviço `notify.mobile_app_<celular>` aparece depois de instalar o app e logar):

```yaml
- alias: Notificar movimento na lateral de madrugada
  triggers:
    - trigger: state
      entity_id: binary_sensor.sensor_lateral_occupancy  # ajustar para o ID real
      to: "on"
  conditions:
    - condition: time
      after: "22:00:00"
      before: "06:00:00"
  actions:
    - action: notify.mobile_app_celular_do_ricardo
      data:
        title: Movimento na lateral
        message: "Presença detectada às {{ now().strftime('%H:%M') }}"
    - delay: "00:05:00"  # anti-spam com mode: single
  mode: single
```

### Ideia: dispositivos no Google Home

**Objetivo:** controlar e ver os dispositivos do HA (Zigbee, Tuya, interruptores) pelo app Google Home e por voz no Google Assistente/Gemini.

Opções a avaliar:

| Opção | Custo | Como funciona | Observações |
|---|---|---|---|
| **Home Assistant Cloud (Nabu Casa)** | assinatura mensal | Liga a integração em poucos cliques | Mais simples e estável; também financia o projeto HA |
| **Integração manual `google_assistant`** | gratuito | Projeto no Google Cloud + Google Home Developer Console, apontando para `https://casa.rmo.dev.br/api/google_assistant` | Já temos a URL pública pela Cloudflare Tunnel; configuração mais trabalhosa; a chave da conta de serviço (JSON) **não pode ir para o git** |
| **Matter (ex.: Home Assistant Matter Hub / Matterbridge)** | gratuito | Expõe as entidades do HA como dispositivos Matter na rede local | Não depende da nuvem; precisa de um dispositivo Google com Matter (Nest Hub, Nest Mini etc.) |

Pontos a decidir:

1. Qual opção usar.
2. Quais entidades expor: só o que faz sentido controlar ou ver por voz (luzes, interruptores, temperatura); sensores técnicos ficam de fora.
3. Nomes e cômodos: o Google usa o nome e a área de cada entidade, então vale revisar os nomes no HA antes (ex.: "Fundos Casa").

Observação: a integração `google_cloud` (texto para voz) que já existe é outra coisa e hoje dá erro 403 porque a API Text-to-Speech não está ativada no projeto do Google Cloud.

### Ideia: câmeras IP tirando foto nos eventos do alarme

**Objetivo:** com o alarme armado, a cada detecção (humano **ou** animal) tirar uma foto da câmera mais próxima, para mapear o que está acontecendo e conferir se a classificação acerta.

Como encaixar no que já existe:

1. **Integrar as câmeras** ao HA. Preferir câmeras com **RTSP/ONVIF** (integração `onvif` ou `generic`); o `go2rtc` já está ativo e ajuda no streaming. Evitar modelos só-nuvem.
2. **Mapear sensor → câmera** (ex.: Lateral casa → câmera lateral) num dicionário na automação.
3. **Nova automação** com gatilho no evento `alarme_evento` (com `armado: true`):
   - `camera.snapshot` para `/config/www/snapshots/<data>_<hora>_<sensor>.jpg` (ou `/media`);
   - notificação no celular com a imagem anexada (`data.image`), inclusive para animal;
   - repassar o caminho da foto no campo `foto` do evento, para a tabela do **Registro do alarme armado** mostrar a miniatura.
4. **Limpeza**: apagar fotos com mais de X dias (`shell_command` ou automação diária) para não lotar o disco.
5. **Privacidade**: as fotos ficam **fora do git** (`config/www/` e `config/media/` já estão no `.gitignore`, o repositório é público). Arquivos em `/config/www` ficam acessíveis em `/local/...` para quem souber o caminho; preferir `/media` se as fotos forem sensíveis.

Futuro: com câmeras, dá para trocar a heurística humano/animal por **detecção de pessoa por imagem** (ex.: Frigate), bem mais confiável.
