import os
import sys
import json
import gspread
from google.oauth2.service_account import Credentials


def resource_path(relative_path: str) -> str:
    """Retorna o caminho absoluto, compatível com PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

class GooglePlanilha:
    def __init__(self):
        self.client = None
        self.planilha = None
        self.aba_relatorio = None
        self._criar_conexao()

    def _criar_conexao(self):
        # Tenta carregar do ambiente primeiro
        cred_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
        if cred_json:
            try:
                credenciais = json.loads(cred_json)
            except json.JSONDecodeError:
                raise ValueError("GOOGLE_CREDENTIALS_JSON inválido. Verifique o formato.")
        else:
            # Fallback para arquivo local (só em desenvolvimento)
            cred_path = resource_path("credentials.json")
            if not os.path.exists(cred_path):
                raise FileNotFoundError("credentials.json não encontrado e GOOGLE_CREDENTIALS_JSON não definido")
            with open(cred_path, 'r', encoding='utf-8') as f:
                credenciais = json.load(f)

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(credenciais, scopes=scopes)
        self.client = gspread.authorize(creds)
        self.planilha = self.client.open("fluxo de loja")
        self.aba_relatorio = self.planilha.worksheet("Relatório")