#!/bin/bash
# Cron job para o Render — roda notificações diárias
# Configurar no Render como: Cron Job, Schedule: 0 8 * * *
# (todo dia às 8h UTC = 5h Brasília)
cd /opt/render/project/src/backend
flask enviar-notificacoes
