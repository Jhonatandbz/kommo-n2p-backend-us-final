
# Kommo × Net2Phone Backend (US)

Backend FastAPI para integração Kommo CRM <> net2phone SMS (EUA), com quiet hours e boas práticas A2P.

## Endpoints
- `GET /send-sms` (probe para Kommo)
- `POST /send-sms` (envio SMS via N2P)
- `GET|POST /webhooks/dp` (Digital Pipeline Kommo)
- `POST /webhooks/n2p` (inbound/delivery N2P)
- `GET /` e `GET /healthz`

## Start no Render
```
uvicorn main:app --host 0.0.0.0 --port $PORT
```

## Variáveis de ambiente
Vide `.env.example`.
