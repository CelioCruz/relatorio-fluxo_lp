import gspread
from gspread.exceptions import APIError, SpreadsheetNotFound, WorksheetNotFound
from typing import Dict, List
import streamlit as st
import os
import json
from dateutil import parser
import pytz
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd
from io import StringIO
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive


class GooglePlanilha:
    """
    Classe simplificada para integração com Google Sheets e Drive.
    Funcionalidades:
    - Leitura/escrita em planilhas
    - Backup automático a cada 3 anos
    - Limpeza de reservas expiradas
    - Controle de estoque de lentes
    """

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
            self._verificar_estrutura()
            self._criar_aba_config()

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
        except WorksheetNotFound:
            st.warning(f"⚠️ Aba '{name}' não encontrada.")
            return None

    def _verificar_estrutura(self):
        """Verifica cabeçalhos da aba 'relatorio'."""
        if not self.aba_relatorio:
            return
        cabecalhos = [c.strip() for c in self.aba_relatorio.row_values(1)]
        esperados = [
            'LOJA', 'DATA', 'HORA', 'VENDEDOR', 'CLIENTE', 'ATENDIMENTOS', 'RECEITAS',
            'PERDAS', 'VENDAS', 'RESERVAS', 'PESQUISAS', 'EXAME DE VISTA',
        ]
        if len(cabecalhos) < 12 or cabecalhos[:12] != esperados:
            st.warning("⚠️ Estrutura da aba 'relatorio' incorreta.")

    def _criar_aba_config(self):
        """Cria aba 'Config' se não existir."""
        try:
            self.planilha.worksheet("Config")
        except WorksheetNotFound:
            aba = self.planilha.add_worksheet("Config", rows="10", cols="5")
            aba.update("A1:B2", [["Último Backup", "Data"], ["backup_3_anos", ""]])
            st.success("✅ Aba 'Config' criada.")

    # === BACKUP AUTOMÁTICO ===

    def _obter_data_ultimo_backup(self):
        try:
            aba = self.planilha.worksheet("Config")
            valor = aba.acell("B2").value
            return datetime.strptime(valor, "%Y-%m-%d") if valor else None
        except:
            return None

    def _registrar_data_backup(self, data: datetime):
        try:
            aba = self.planilha.worksheet("Config")
            aba.update("B2", data.strftime("%Y-%m-%d"))
        except Exception as e:
            st.error(f"❌ Falha ao registrar data do backup: {e}")

    def _deve_fazer_backup(self) -> bool:
        ultimo = self._obter_data_ultimo_backup()
        return ultimo is None or (datetime.now() - ultimo) >= timedelta(days=3 * 365.25)

    def rodar_backup_automatico(self):
        """Faz backup a cada 3 anos e limpa backups antigos."""
        if not self._deve_fazer_backup():
            return

        try:
            # Exporta CSV
            df = pd.DataFrame(self.aba_relatorio.get_all_records())
            if df.empty:
                st.info("📭 Nenhum dado para backup.")
                return

            nome_arquivo = f"backup_relatorio_{datetime.now().strftime('%Y-%m-%d')}.csv"
            csv = df.to_csv(index=False)

            # Salva no Drive
            self._salvar_no_drive(nome_arquivo, csv)
            self._registrar_data_backup(datetime.now())
            self._limpar_aba_relatorio()
            self._limpar_backups_antigos_no_drive()

        except Exception as e:
            st.warning(f"⚠️ Falha no backup: {e}")

    def _salvar_no_drive(self, nome_arquivo: str, conteudo: str):
        """Salva arquivo no Google Drive usando Service Account."""
        try:
            gauth = GoogleAuth()
            caminho_temp = "/tmp/service_account.json"
            with open(caminho_temp, "w") as f:
                json.dump(st.secrets["gcp_service_account"], f)
            gauth.service_account_file = caminho_temp
            gauth.CommandLineAuth()
            drive = GoogleDrive(gauth)

            file_drive = drive.CreateFile({'title': nome_arquivo, 'mimeType': 'text/csv'})
            file_drive.SetContentString(conteudo)
            file_drive.Upload()
            st.success(f"✅ Backup salvo: `{nome_arquivo}`")
        except Exception as e:
            st.error(f"❌ Falha ao salvar no Drive: {e}")

    def _limpar_aba_relatorio(self):
        """Limpa dados, mantendo cabeçalho."""
        try:
            cabecalhos = self.aba_relatorio.row_values(1)
            self.aba_relatorio.clear()
            self.aba_relatorio.update("A1", [cabecalhos])
            st.info("🧹 Dados da aba 'relatorio' limpos.")
        except Exception as e:
            st.error(f"❌ Falha ao limpar aba: {e}")

    def _limpar_backups_antigos_no_drive(self):
        """Remove backups com mais de 5 anos."""
        try:
            gauth = GoogleAuth()
            with open("/tmp/service_account.json", "w") as f:
                json.dump(st.secrets["gcp_service_account"], f)
            gauth.service_account_file = "/tmp/service_account.json"
            gauth.CommandLineAuth()
            drive = GoogleDrive(gauth)

            file_list = drive.ListFile({
                'q': "mimeType='text/csv' and trashed=false and title contains 'backup_relatorio_'"
            }).GetList()

            agora = datetime.now()
            for file in file_list:
                match = re.search(r"backup_relatorio_(\d{4}-\d{2}-\d{2})\.csv", file['title'])
                if match:
                    data_arquivo = datetime.strptime(match.group(1), "%Y-%m-%d")
                    if (agora - data_arquivo).days > 5 * 365.25:
                        file.Trash()
                        st.warning(f"🗑️ Backup antigo removido: `{file['title']}`")

        except Exception as e:
            st.error(f"❌ Erro ao limpar backups antigos: {e}")

    # === MÉTODOS PÚBLICOS ===

    def get_all_records(self) -> List[Dict]:
        """Retorna todos os registros da aba 'relatorio'."""
        try:
            return self.aba_relatorio.get_all_records() if self.aba_relatorio else []
        except Exception as e:
            st.error(f"❌ Falha ao ler registros: {e}")
            return []

    def get_vendedores_por_loja(self, loja: str = None) -> List[Dict]:
        """Retorna lista de vendedores."""
        try:
            if 'vendedores_cache' not in st.session_state:
                coluna_a = self.aba_vendedores.col_values(1) if self.aba_vendedores else []
                st.session_state.vendedores_cache = [
                    {"VENDEDOR": nome.strip()} for nome in coluna_a if nome.strip()
                ]
            return st.session_state.vendedores_cache
        except Exception as e:
            st.error(f"❌ Falha ao buscar vendedores: {e}")
            return []

    def registrar_atendimento(self, dados: Dict) -> bool:
        """Registra novo atendimento."""
        try:
            for campo in ['loja', 'vendedor', 'cliente']:
                if not dados.get(campo):
                    st.error(f"❌ {campo.upper()} é obrigatório.")
                    return False

            dados['hora'] = dados.get('hora') or datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%H:%M:%S")

            mapeamento = [
                ('loja', 'LOJA'), ('data', 'DATA'), ('hora', 'HORA'),
                ('vendedor', 'VENDEDOR'), ('cliente', 'CLIENTE'),
                ('atendimento', 'ATENDIMENTOS'), ('receita', 'RECEITAS'),
                ('perda', 'PERDAS'), ('venda', 'VENDAS'), ('reserva', 'RESERVAS'),
                ('pesquisa', 'PESQUISAS'), ('consulta', 'EXAME OFTALMO')
            ]

            valores = [str(dados.get(campo, '')).strip() for campo, _ in mapeamento]
            self.aba_relatorio.append_row(valores, value_input_option='USER_ENTERED')
            return True

        except Exception as e:
            st.error(f"❌ Falha ao salvar: {e}")
            return False

    # === CONTROLE DE LENTES ===

    def buscar_estoque_lentes(self) -> Dict:
        """Retorna estoque de lentes."""
        aba = self._get_worksheet("Lentes")
        if not aba:
            return {}
        try:
            dados = aba.get_all_values()
            if len(dados) < 2:
                return {}
            cilindricos = [c.strip() for c in dados[0][1:]]
            esfericos = [linha[0].strip() for linha in dados[1:] if linha]
            estoque = {esf: {} for esf in esfericos}
            for i, linha in enumerate(dados[1:]):
                esf = esfericos[i]
                for j, cil in enumerate(cilindricos):
                    valor = linha[j + 1] if j + 1 < len(linha) else "0"
                    estoque[esf][cil] = int(valor) if valor.isdigit() else 0
            return estoque
        except Exception as e:
            st.error(f"❌ Erro ao ler estoque: {e}")
            return {}

    def reservar_lente_temporariamente(self, od, oe, cliente, vendedor) -> bool:
        """Reserva lentes por 1 minuto."""
        estoque = self.buscar_estoque_lentes()
        if (estoque.get(od['esf'], {}).get(od['cil'], 0) < od['qtd'] or
            estoque.get(oe['esf'], {}).get(oe['cil'], 0) < oe['qtd']):
            return False

        aba_lentes = self._get_worksheet("Lentes")
        if not aba_lentes:
            return False

        def atualizar(esf, cil, delta):
            col = next((i+1 for i, c in enumerate(aba_lentes.row_values(1)) if c.strip() == cil), None)
            row = next((i+1 for i, e in enumerate(aba_lentes.col_values(1)) if e.strip() == esf), None)
            if not col or not row:
                return False
            atual = aba_lentes.cell(row, col).value
            nova = (int(atual) if atual and atual.isdigit() else 0) + delta
            if nova < 0:
                return False
            aba_lentes.update_cell(row, col, str(nova))
            return True

        if not atualizar(od['esf'], od['cil'], -od['qtd']):
            return False
        if not atualizar(oe['esf'], oe['cil'], -oe['qtd']):
            atualizar(od['esf'], od['cil'], od['qtd'])  # desfaz
            return False

        aba_reservas = self._get_worksheet("reservas")
        if aba_reservas:
            agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
            aba_reservas.append_row([
                agora.strftime("%d/%m/%Y %H:%M"), cliente, vendedor,
                f"{od['esf']} / {od['cil']} / {od['qtd']}",
                f"{oe['esf']} / {oe['cil']} / {oe['qtd']}",
                "PENDENTE"
            ], value_input_option='USER_ENTERED')
        return True

    def limpar_reservas_antigas(self, minutos=1) -> int:
        """Libera reservas expiradas."""
        aba_reservas = self._get_worksheet("reservas")
        if not aba_reservas:
            return 0
        try:
            dados = aba_reservas.get_all_values()
            if len(dados) < 2:
                return 0
            status_idx = next((i for i, h in enumerate(dados[0]) if "STATUS" in h.upper()), None)
            if status_idx is None:
                return 0

            agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
            linhas_para_apagar = []

            for i in range(1, len(dados)):
                linha = dados[i]
                if len(linha) <= status_idx:
                    continue
                if linha[status_idx].strip().upper() != "PENDENTE":
                    continue
                try:
                    data_str = linha[0].strip()
                    hora_criacao = parser.parse(data_str, dayfirst=True)
                    if hora_criacao.tzinfo is None:
                        hora_criacao = hora_criacao.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
                except:
                    continue
                if (agora - hora_criacao).total_seconds() > minutos * 60:
                    linhas_para_apagar.append(i + 1)

            for num in sorted(linhas_para_apagar, reverse=True):
                try:
                    valores = aba_reservas.row_values(num)
                    if len(valores) >= 5:
                        od = self._parse_item(valores[3])
                        oe = self._parse_item(valores[4])
                        aba_lentes = self._get_worksheet("Lentes")
                        if aba_lentes:
                            self._atualizar_celula_estoque(aba_lentes, od['esf'], od['cil'], od['qtd'])
                            self._atualizar_celula_estoque(aba_lentes, oe['esf'], oe['cil'], oe['qtd'])
                    aba_reservas.delete_rows(num)
                except Exception as e:
                    st.error(f"❌ Falha ao limpar linha {num}: {e}")
            return len(linhas_para_apagar)
        except Exception as e:
            st.error(f"❌ Erro ao limpar reservas: {e}")
            return 0

    def _parse_item(self, s: str) -> Dict:
        partes = [x.strip() for x in s.split("/")]
        return {"esf": partes[0], "cil": partes[1], "qtd": int(partes[2])} if len(partes) == 3 else {"esf": "0,00", "cil": "0,00", "qtd": 0}

    def _atualizar_celula_estoque(self, aba, esf: str, cil: str, delta: int):
        try:
            col = next((i + 1 for i, c in enumerate(aba.row_values(1)) if c.strip() == cil), None)
            row = next((i + 1 for i, e in enumerate(aba.col_values(1)) if e.strip() == esf), None)
            if not col or not row:
                return
            atual = aba.cell(row, col).value
            nova = (int(atual) if atual and atual.isdigit() else 0) + delta
            aba.update_cell(row, col, str(nova))
        except Exception as e:
            st.error(f"❌ Erro ao atualizar estoque: {e}")
