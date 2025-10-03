import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os
from collections import defaultdict
import io

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from google_planilha import GooglePlanilha
except Exception as e:
    st.error(f"Erro ao importar GooglePlanilha: {e}")
    GooglePlanilha = None

def mostrar():
    st.title("🏢👨‍💼 Relatório por Loja e Vendedor")
    st.markdown("Selecione a loja e o período:")

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

    coluna_loja = None
    for key in dados_brutos[0].keys():
        if key.strip().lower() in ['loja', 'unidade', 'filial', 'local']:
            coluna_loja = key
            break

    if not coluna_loja:
        st.error("❌ Coluna 'Loja' não encontrada na planilha.")
        return

    lojas_unicas = sorted({
        str(row[coluna_loja]).strip()
        for row in dados_brutos
        if row.get(coluna_loja) and str(row[coluna_loja]).strip().lower() not in ['nan', '', 'none']
    })

    if not lojas_unicas:
        st.warning("📭 Nenhuma loja encontrada.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        loja = st.selectbox("Loja:", lojas_unicas)
    with col2:
        data_de = st.date_input("Data inicial", value=datetime.today())
    with col3:
        data_ate = st.date_input("Data final", value=datetime.today())

    if data_de > data_ate:
        st.error("⚠️ A data inicial não pode ser maior que a data final.")
        return

    if not loja:
        st.warning("⚠️ Selecione uma loja.")
        return

    def filtrar_por_loja(dados, loja):
        return [
            row for row in dados
            if str(row.get(coluna_loja, "")).strip().lower() == loja.strip().lower()
        ]

    def filtrar_por_data(dados, data_de, data_ate):
        coluna_data = None
        for key in dados[0].keys():
            if key.strip().lower() in ['data', 'datas', 'dt']:
                coluna_data = key
                break

        if not coluna_data:
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

    def agrupar_por_vendedor(dados):
        if not dados:
            return []

        coluna_vendedor = None
        for key in dados[0].keys():
            if key.strip().lower() in ['vendedor', 'vendedora', 'funcionário', 'vend']:
                coluna_vendedor = key
                break

        if not coluna_vendedor:
            st.error("❌ Coluna 'Vendedor' não encontrada.")
            return []

        mapeamento_campos = {
            'atendimento': ['atendimento', 'atendimentos', 'atend'],
            'receita': ['receita', 'receitas', 'faturamento'],
            'venda': ['venda', 'vendas', 'pedidos'],
            'perda': ['perda', 'perdas', 'cancelamentos'],
            'pesquisa': ['pesquisa', 'pesquisas', 'pesq'],
            'consulta': ['consulta', 'consultas', 'consult'],
            'reserva': ['reserva', 'reservas', 'agendamento']
        }

        colunas_valor = {}
        for campo, possiveis in mapeamento_campos.items():
            for key in dados[0].keys():
                if any(p in key.lower() for p in possiveis):
                    colunas_valor[campo] = key
                    break

        resultado = defaultdict(lambda: defaultdict(float))
        for row in dados:
            vendedor = str(row.get(coluna_vendedor, "")).strip() or "[SEM VENDEDOR]"
            for campo, col in colunas_valor.items():
                valor_str = str(row.get(col, "")).strip()
                if not valor_str:
                    continue
                try:
                    valor = float(valor_str.replace(",", "."))
                    resultado[vendedor][campo] += valor
                except ValueError:
                    continue

        dados_agrupados = []
        for vendedor, valores in resultado.items():
            linha = {"Vendedor": vendedor}
            for campo in mapeamento_campos.keys():
                total = round(valores[campo], 2)
                linha[campo.upper()] = int(total) if total.is_integer() else int(round(total))
            dados_agrupados.append(linha)

        return sorted(dados_agrupados, key=lambda x: x.get("ATENDIMENTO", 0), reverse=True)

    dados_loja = filtrar_por_loja(dados_brutos, loja)
    dados_filtrados = filtrar_por_data(dados_loja, data_de, data_ate)

    if not dados_filtrados:
        st.info("📭 Nenhum dado encontrado para esta loja no período selecionado.")
        return

    dados_agrupados = agrupar_por_vendedor(dados_filtrados)
    if not dados_agrupados:
        st.warning("⚠️ Nenhum dado para exibir após o agrupamento.")
        return

    df = pd.DataFrame(dados_agrupados)
    colunas_ordem = ["Vendedor", "ATENDIMENTO", "RECEITA", "VENDA", "PERDA", "PESQUISA", "CONSULTA", "RESERVA"]
    df = df.reindex(columns=colunas_ordem, fill_value=0)

    for col in ["ATENDIMENTO", "RECEITA", "VENDA", "PERDA", "PESQUISA", "CONSULTA", "RESERVA"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    st.markdown("### Resumo")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Vendedores", len(df))  # Corrigido de "Vendedor" para "Vendedores"
    col2.metric("Receitas", f"{int(df['RECEITA'].sum())}" if "RECEITA" in df.columns and df["RECEITA"].sum() != 0 else "0")
    col3.metric("Vendas", f"{int(df['VENDA'].sum())}" if "VENDA" in df.columns and df["VENDA"].sum() != 0 else "0")
    col4.metric("Perdas", f"{int(df['PERDA'].sum())}" if "PERDA" in df.columns and df["PERDA"].sum() != 0 else "0")

    st.markdown("### Dados por Vendedor")
    st.dataframe(df, use_container_width=True, hide_index=True)  # ✅ ÍNDICE REMOVIDO

    # ✅ Botão de download
    try:
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False, engine="openpyxl")
        st.download_button(
            label="📥 Baixar como Excel",
            data=buffer.getvalue(),
            file_name="Relatorio por Loja e Vendedor.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except ImportError:
        st.info("📦 Instale `openpyxl` para exportar: `pip install openpyxl`")
    except Exception as e:
        st.error(f"Erro ao gerar o arquivo Excel: {e}")