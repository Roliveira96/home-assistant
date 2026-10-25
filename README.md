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

O `cloudflared` abre uma conexão de saída até a Cloudflare, então **não é preciso abrir porta no roteador** nem ter IP fixo. Pré-requisito: um domínio gerenciado pela Cloudflare.

1. No painel da Cloudflare: **Zero Trust → Networks → Tunnels → Create a tunnel → Cloudflared**. Dê um nome (ex.: `casa`).
2. Na tela de instalação, escolha **Docker** e copie só o token (o texto depois de `--token`). Coloque em `.env`:

   ```
   COMPOSE_PROFILES=tunnel
   TUNNEL_TOKEN=<token>
   ```

3. Em **Public Hostname**, adicione:
   - Subdomínio: `casa` (ou outro), domínio: o seu
   - Service: `HTTP` → `localhost:9999`
4. Subir o túnel: `docker compose up -d cloudflared` e acompanhar com `docker compose logs -f cloudflared`.
5. No Home Assistant, em **Configurações → Sistema → Rede**, preencher a URL da Internet com `https://casa.seudominio.com.br`.

O `configuration.yaml` já tem `use_x_forwarded_for` e `trusted_proxies` (127.0.0.1 e ::1). Sem isso, o HA responde `400 Bad Request` às requisições que chegam pelo túnel.

### Segurança

- Ativar **autenticação em dois fatores** no perfil de cada usuário do HA, já que a página de login ficará exposta na internet.
- Opcional: proteger com **Cloudflare Access**. Atenção: o Access bloqueia o app Companion do celular, a não ser que se configure uma regra de bypass ou mTLS.

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

## Roadmap

- [x] Projeto versionado com docker-compose
- [ ] Migrar o container antigo para o compose (seção [Migração](#migração-da-instalação-antiga-fazer-uma-vez))
- [ ] Acesso remoto pela Cloudflare Tunnel
- [ ] Notificações no celular para eventos dentro de um período (ideia abaixo)
- [ ] Monitoramento: avisar quando a máquina ficar offline ou um sensor ficar indisponível (ideia abaixo)

### Ideia: avisar quando a máquina ou os sensores caírem

**Motivo:** em 20/10/2026, por volta das 21h, a máquina ficou sem internet. O dongle Zigbee perdeu a conexão às 21:15 e só voltou em 24/10. Foram 4 dias sem automações e sem aviso nenhum.

Os dois casos pedem soluções diferentes:

1. **Máquina offline (sem internet ou desligada):** o HA não consegue avisar, porque está sem rede. É preciso um vigia **externo** do tipo *dead man's switch*:
   - uma automação do HA faz um ping a cada 5 min para um serviço como o [healthchecks.io](https://healthchecks.io) (gratuito), via `rest_command`;
   - se os pings param, o serviço manda a mensagem (Telegram, e-mail ou push).
   - Alternativa: monitorar o endereço público do túnel com UptimeRobot, que também pega o caso do túnel cair.
2. **Sensor ou Zigbee indisponível (máquina online):** uma automação no próprio HA. Gatilho: entidade com estado `unavailable` por mais de 30 min. Ação: notificação no celular. Com isso, o problema de 20/10 seria percebido na mesma noite.

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
