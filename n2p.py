import os, time, requests
from dataclasses import dataclass
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

@dataclass
class N2PConfig:
    base_url: str
    client_id: str
    client_secret: str
    token_url: str
    sms_url: str

    @staticmethod
    def from_env():
        base = os.getenv("N2P_BASE_URL", "https://api.n2p.io/v2").rstrip("/")
        token_url = os.getenv("N2P_TOKEN_URL", "https://auth.net2phone.com/connect/token")
        sms_url = os.getenv("N2P_SMS_URL", f"{base}/messaging/sms")
        client_id = os.environ["N2P_CLIENT_ID"]
        client_secret = os.environ["N2P_CLIENT_SECRET"]
        return N2PConfig(base, client_id, client_secret, token_url, sms_url)

class N2PClient:
    def __init__(self, cfg: N2PConfig):
        self.cfg = cfg
        self._token = None
        self._exp = 0
        self.session = requests.Session()
        retry = Retry(total=3, backoff_factor=0.5,
                      status_forcelist=[429, 500, 502, 503, 504],
                      allowed_methods=["POST", "GET"])
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.mount("http://", HTTPAdapter(max_retries=retry))

    def _get_token(self, force: bool = False):
        """Obtém e faz cache do access_token.
        Tenta 1) credenciais no body; 2) HTTP Basic; aceita N2P_SCOPE via env."""
        if not force and self._token and time.time() < (self._exp - 30):
            return self._token

        scope = os.getenv("N2P_SCOPE")  # ex.: "messaging"
        base_data = {"grant_type": "client_credentials"}
        if scope:
            base_data["scope"] = scope

        # Tentativa 1: client_id/secret no body
        data_with_creds = {
            **base_data,
            "client_id": self.cfg.client_id,
            "client_secret": self.cfg.client_secret,
        }
        r = self.session.post(self.cfg.token_url, data=data_with_creds, timeout=30)

        # Tentativa 2: HTTP Basic Auth se 400/401
        if r.status_code in (400, 401):
            r = self.session.post(
                self.cfg.token_url,
                data=base_data,
                auth=(self.cfg.client_id, self.cfg.client_secret),
                timeout=30,
            )

        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            raise RuntimeError(f"Token error ({r.status_code}): {r.text}") from e

        j = r.json()
        token = j.get("access_token")
        if not token:
            raise RuntimeError(f"Invalid token response: {j}")
        self._token = token
        self._exp = time.time() + int(j.get("expires_in", 3600))
        return self._token

    def _headers(self, token: str):
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def send_sms(self, to: str, text: str, sender: str | None = None, **extra):
        token = self._get_token()
        payload = {"to": to, "text": text}
        if sender:
            payload["from"] = sender
        if extra:
            payload.update(extra)

        r = self.session.post(self.cfg.sms_url, json=payload, headers=self._headers(token), timeout=30)
        if r.status_code == 401:
            token = self._get_token(force=True)
            r = self.session.post(self.cfg.sms_url, json=payload, headers=self._headers(token), timeout=30)

        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            try:
                detail = r.json()
            except Exception:
                detail = r.text
            raise RuntimeError(f"N2P SMS failed ({r.status_code}): {detail}") from e

        return r.json() if r.content else {"ok": True}
