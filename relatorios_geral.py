import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os
import io

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from google_planilha import GooglePlanilha
except Exception as e:
    st.error(f"Erro ao importar GooglePlanilha: {e}")
    GooglePlanilha = None

def mostrar():
    st.title("📈 Relatório Geral")
    st.markdown("Selecione o período para gerar o relatório:")

    if GooglePlanilha is None:
        st.warning("⚠️ Módulo GooglePlanilha não carregado.")
        return

    try:
        gsheet = GooglePlanilha()
        dados_brutos = gsheet.aba_relatorio.get_all_records()
        if not dados_brutos:
            st.info("📭 Nenhum dado encontrado na planilha.")
            return
    except FileNotFoundError:
        st.error("❌ Arquivo `credentials.json` não encontrado.")
        return
    except Exception as e:
        st.error(f"❌ Erro ao conectar ao Google Sheets:\n{e}")
        return

    col1, col2 = st.columns(2)
    with col1:
        data_de = st.date_input("Data inicial", value=datetime.today())
    with col2:
        data_ate = st.date_input("Data final", value=datetime.today())

    if data_de > data_ate:
        st.error("⚠️ A data inicial não pode ser maior que a data final.")
        return

    def filtrar_por_data(dados, data_de, data_ate):
        coluna_data = None
        for key in dados[0].keys():
            if key.strip().lower() in ['data', 'datas', 'dt']:
                coluna_data = key
                break

        if not coluna_data:
            st.warning("⚠️ Coluna 'Data' não encontrada. Exibindo todos os dados.")
            return dados

        dados_filtrados = []
        for row in dados:
            data_str = str(row.get(coluna_data, "")).strip()
            if not data_str:
                continue
            try:
                data_row = datetime.strptime(data_str, "%d/%m/%Y").date()
                if data_de <= data_row <= data_ate:
                    dados_filtrados.append(row)
            except ValueError:
                continue
        return dados_filtrados

    dados_filtrados = filtrar_por_data(dados_brutos, data_de, data_ate)
    if not dados_filtrados:
        st.info("📭 Nenhum dado encontrado no período selecionado.")
        return

    df = pd.DataFrame(dados_filtrados)

    # ✅ REMOVER a coluna "HORA", se existir
    if "HORA" in df.columns:
        df = df.drop(columns=["HORA"])

    # ✅ FORÇAR TODAS AS COLUNAS NUMÉRICAS PARA NÚMERO
    colunas_numericas = ["ATENDIMENTO", "RECEITA", "PERDA", "VENDA", "RESERVA", "PESQUISA", "EXAME", "CONSULTA"]
    for col in colunas_numericas:
        if col in df.columns:
            # Forçar tudo para string
            df[col] = df[col].astype(str)
            # Remover espaços e substituir vazios/comuns por "0"
            df[col] = df[col].str.strip().replace(
                ["", "nan", "None", "NaN", "null", "–", "-", " ", "R$", "R$ ", "r$", "r$ ", "ND", "N/A"],
                "0",
                regex=False
            )
            # Remover QUALQUER caractere não numérico (exceto ponto e vírgula)
            df[col] = df[col].str.replace(r"[^\d.,-]", "", regex=True)
            # Substituir vírgula por ponto
            df[col] = df[col].str.replace(",", ".", regex=False)
            # Converter para numérico (erros → NaN)
            df[col] = pd.to_numeric(df[col], errors="coerce")
            # Preencher NaN com 0
            df[col] = df[col].fillna(0)
            # Arredondar e converter para inteiro se for inteiro
            if df[col].apply(lambda x: x == int(x)).all():
                df[col] = df[col].astype(int)
            else:
                df[col] = df[col].round(2)
                
    st.markdown("### Dados")
    st.dataframe(df, use_container_width=True)

    # ✅ Apenas UM botão: Baixar como Excel com nome fixo
    try:
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False, engine="openpyxl")
        st.download_button(
            label="📥 Baixar como Excel",
            data=buffer.getvalue(),
            file_name="Relatorio Geral fluxo de loja.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except ImportError:
        st.info("📦 Instale `openpyxl`: `pip install openpyxl`")
    except Exception as e:
        st.error(f"Erro ao gerar o arquivo Excel: {e}")