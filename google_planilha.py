import gspread
from gspread.exceptions import APIError, SpreadsheetNotFound
import streamlit as st
import os

class GooglePlanilha:
    def __init__(self):
        """Inicializa a conexão com o Google Sheets."""
        if 'gsheets_client' not in st.session_state:
            self._criar_conexao()
        else:
            self.client = st.session_state.gsheets_client
            self.planilha = st.session_state.planilha_atendimento
            self.aba_vendedores = self._get_worksheet("vendedor")
            self.aba_relatorio = self._get_worksheet("relatorio")

    def _criar_conexao(self):
        """Cria conexão usando Service Account (sem OAuth)."""
        try:
            # 🔹 Credenciais: produção ou local
            if 'GCP_PROJECT_ID' in os.environ:
                credenciais = {
                    "type": "service_account",
                    "project_id": os.environ["GCP_PROJECT_ID"],
                    "private_key_id": os.environ["GCP_PRIVATE_KEY_ID"],
                    "private_key": os.environ["GCP_PRIVATE_KEY"].replace("\\n", "\n"),
                    "client_email": os.environ["GCP_CLIENT_EMAIL"],
                    "client_id": os.environ["GCP_CLIENT_ID"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_x509_cert_url": os.environ["GCP_CLIENT_X509_CERT_URL"],
                    "universe_domain": "googleapis.com"
                }
            else:
                credenciais = st.secrets["gcp_service_account"]

            # ✅ Conecta
            client = gspread.service_account_from_dict(credenciais)
            st.session_state.gsheets_client = client

            # ✅ Abre planilha
            planilha = client.open("fluxo de loja")
            st.session_state.planilha_atendimento = planilha
            self.planilha = planilha
            self.aba_vendedores = self._get_worksheet("vendedor")
            self.aba_relatorio = self._get_worksheet("relatorio")

            st.success("✅ Planilha carregada com sucesso!")

        except SpreadsheetNotFound:
            st.error("❌ Planilha 'fluxo de loja' não encontrada.")
            st.markdown("💡 Compartilhe com: `seu-email@projeto.iam.gserviceaccount.com` como **Editor**.")
            st.stop()
        except APIError as e:
            st.error(f"🔐 Erro de autenticação: {e}")
            st.stop()
        except Exception as e:
            st.error(f"❌ Falha ao conectar: {e}")
            st.stop()

    def _get_worksheet(self, name: str):
        """Retorna worksheet ou None se não existir."""
        try:
            return self.planilha.worksheet(name)
        except gspread.exceptions.WorksheetNotFound:
            st.warning(f"⚠️ Aba '{name}' não encontrada.")
            return None