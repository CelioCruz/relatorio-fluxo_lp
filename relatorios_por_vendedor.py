import streamlit as st
import pandas as pd
from datetime import datetime, date
import sys
import os
import io

# Adiciona o diretório raiz ao sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from google_planilha import GooglePlanilha
except Exception as e:
    st.error(f"Erro ao importar GooglePlanilha: {e}")
    GooglePlanilha = None

def mostrar():
    st.title("👨‍💼 Relatório por Vendedor")
    st.markdown("Selecione o vendedor e o período:")

    if GooglePlanilha is None:
        st.warning("⚠️ Módulo GooglePlanilha não carregado.")
        return

    # === Conexão com Google Sheets ===
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

    # === Carregar lista de vendedores ===
    coluna_vendedor = None
    for key in dados_brutos[0].keys():
        if key.strip().lower() in ['vendedor', 'vendedora', 'funcionário', 'vend']:
            coluna_vendedor = key
            break

    if not coluna_vendedor:
        st.error("❌ Coluna 'Vendedor' não encontrada.")
        return

    vendedores_unicos = sorted({
        str(row[coluna_vendedor]).strip()
        for row in dados_brutos
        if row.get(coluna_vendedor) and str(row[coluna_vendedor]).strip().lower() not in ['nan', '', 'none']
    })

    if not vendedores_unicos:
        st.warning("📭 Nenhum vendedor encontrado.")
        return

    # === Seleção de vendedor e datas ===
    col1, col2, col3 = st.columns(3)
    with col1:
        vendedor = st.selectbox("Vendedor:", vendedores_unicos)
    with col2:
        data_de = st.date_input("Data inicial", value=date.today())
    with col3:
        data_ate = st.date_input("Data final", value=date.today())

    if data_de > data_ate:
        st.error("⚠️ A data inicial não pode ser maior que a data final.")
        return

    if not vendedor:
        st.warning("⚠️ Selecione um vendedor.")
        return

    # === Funções de filtragem ===
    def filtrar_por_vendedor(dados, vendedor):
        return [
            row for row in dados
            if str(row.get(coluna_vendedor, "")).strip().lower() == vendedor.strip().lower()
        ]

    def filtrar_por_data(dados, data_de, data_ate):
        coluna_data = None
        for key in dados[0].keys():
            if key.strip().lower() in ['data', 'datas', 'dt']:
                coluna_data = key
                break

        if not coluna_data:
            st.warning("⚠️ Coluna 'Data' não encontrada.")
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

    # === Processamento ===
    dados_vendedor = filtrar_por_vendedor(dados_brutos, vendedor)
    dados_filtrados = filtrar_por_data(dados_vendedor, data_de, data_ate)

    if not dados_filtrados:
        st.info("📭 Nenhum dado encontrado para este vendedor no período selecionado.")
        return

    # === Criar DataFrame ===
    df = pd.DataFrame(dados_filtrados)

    # === Mapear colunas desejadas ===
    colunas_desejadas = {
        "DATA": ["data", "dt"],
        "LOJA": ["loja", "unidade", "filial"],
        "CLIENTE": ["cliente", "nome"],
        "ATENDIMENTO": ["atendimento", "atend"],
        "RECEITA": ["receita", "faturamento"],
        "VENDA": ["venda", "pedidos"],
        "PERDA": ["perda", "cancelamentos"],
        "PESQUISA": ["pesquisa", "pesquisas"],
        "CONSULTA": ["consulta", "exame", "exame de vista"],
        "RESERVA": ["reserva", "agendamento"]
    }

    colunas_finais = {}
    for nome, palavras in colunas_desejadas.items():
        for col in df.columns:
            if any(p in col.lower() for p in palavras):
                colunas_finais[col] = nome
                break

    if colunas_finais:
        df = df[list(colunas_finais.keys())].rename(columns=colunas_finais)

    # Reordenar colunas
    ordem = ["DATA", "LOJA", "CLIENTE", "ATENDIMENTO", "RECEITA", "VENDA", "PERDA", "PESQUISA", "CONSULTA", "RESERVA"]
    colunas_existentes = [c for c in ordem if c in df.columns]
    df = df[colunas_existentes].copy()

    # ✅ CONVERSÃO NUMÉRICA SEGURA — remove R$, símbolos e formatação
    colunas_numericas = ["ATENDIMENTO", "RECEITA", "VENDA", "PERDA", "PESQUISA", "CONSULTA", "RESERVA"]
    for col in colunas_numericas:
        if col in df.columns:
            df[col] = df[col].astype(str)
            df[col] = df[col].str.strip().replace(
                ["", "nan", "None", "NaN", "null", "–", "-", " ", "R$", "R$ ", "r$", "r$ "],
                "0"
            )
            df[col] = df[col].str.replace(r"[^\d.,-]", "", regex=True)
            df[col] = df[col].str.replace(",", ".", regex=False)
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # ✅ Formatar: inteiros quando possível, float quando necessário
    for col in ["ATENDIMENTO", "PESQUISA", "CONSULTA", "PERDA"]:
        if col in df.columns:
            df[col] = df[col].astype(int)

    for col in ["RECEITA", "VENDA", "RESERVA"]:
        if col in df.columns:
            df[col] = df[col].round(2).apply(lambda x: int(x) if x == int(x) else x)

    # === Exibir tabela ===
    st.markdown("### Dados do Vendedor")
    st.dataframe(df, use_container_width=True, hide_index=True)  # ✅ ÍNDICE REMOVIDO

    # === Resumo ===
    st.markdown("### Resumo")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Atendimentos", len(df))
    col2.metric("Receitas", f"{int(df['RECEITA'].sum())}" if "RECEITA" in df.columns and df["RECEITA"].sum() != 0 else "0")
    col3.metric("Vendas", f"{int(df['VENDA'].sum())}" if "VENDA" in df.columns and df["VENDA"].sum() != 0 else "0")
    col4.metric("Perdas", f"{int(df['PERDA'].sum())}" if "PERDA" in df.columns and df["PERDA"].sum() != 0 else "0")

    # === Botão de download único ===
    try:
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False, engine="openpyxl")
        st.download_button(
            label="📥 Baixar como Excel",
            data=buffer.getvalue(),
            file_name="Relatorio por Vendedor.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except ImportError:
        st.info("📦 Instale `openpyxl`: `pip install openpyxl`")
    except Exception as e:
        st.error(f"Erro ao gerar o arquivo Excel: {e}")