import streamlit as st
import pandas as pd
from datetime import datetime
import sys
import os
from collections import defaultdict
import io

# Adiciona o diretório raiz ao sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from google_planilha import GooglePlanilha
except Exception as e:
    st.error(f"Erro ao importar GooglePlanilha: {e}")
    GooglePlanilha = None

def mostrar():
    st.title("🏢 Relatório por Loja")
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
            st.warning("⚠️ Coluna 'Data' não encontrada. Usando todos os dados.")
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

    def agrupar_por_loja(dados):
        if not dados:
            return []

        colunas_map = {k.strip().lower(): k for k in dados[0].keys()}
        coluna_loja = next((colunas_map[k] for k in ['loja', 'unidade', 'filial', 'local'] if k in colunas_map), None)

        if not coluna_loja:
            st.error("❌ Coluna 'Loja' não encontrada.")
            return []

        campos = ['receita', 'perda', 'venda', 'pesquisa', 'consulta', 'reserva', 'google']
        colunas_valor = {}
        for campo in campos:
            for key_lower, key_orig in colunas_map.items():
                if campo == 'google':
                    # Procura por 'google' ou 'm' (exato)
                    if 'google' in key_lower or key_lower == 'm':
                        colunas_valor[campo] = key_orig
                        break
                elif campo in key_lower:
                    colunas_valor[campo] = key_orig
                    break

        resultado = defaultdict(lambda: defaultdict(float))
        for row in dados:
            loja = str(row.get(coluna_loja, "")).strip() or "[SEM LOJA]"
            for campo, col_orig in colunas_valor.items():
                try:
                    val = str(row.get(col_orig, "0")).replace(",", ".")
                    resultado[loja][campo] += float(val)
                except:
                    continue

        dados_agrupados = []
        for loja, valores in resultado.items():
            linha = {"Loja": loja}
            for campo in campos:
                total = round(valores[campo], 2)
                linha[campo.upper()] = int(total) if total.is_integer() else int(round(total))
            dados_agrupados.append(linha)

        return sorted(dados_agrupados, key=lambda x: x.get("Loja", ""), reverse=False)

    dados_filtrados = filtrar_por_data(dados_brutos, data_de, data_ate)
    if not dados_filtrados:
        st.info("📭 Nenhum dado encontrado no período selecionado.")
        return

    dados_agrupados = agrupar_por_loja(dados_filtrados)
    if not dados_agrupados:
        st.warning("⚠️ Nenhum dado para exibir.")
        return

    df = pd.DataFrame(dados_agrupados)

    # ✅ Ordem: Loja, Receita, Perda, Venda, Reserva, Google, Pesquisa, Consulta
    colunas_ordem = ["Loja", "RECEITA", "PERDA", "VENDA", "RESERVA", "GOOGLE", "PESQUISA", "CONSULTA"]
    # Manter apenas colunas que existem no df
    colunas_ordem_filtradas = [col for col in colunas_ordem if col in df.columns]
    df = df[colunas_ordem_filtradas]

    # ✅ Garantir que todas as colunas numéricas sejam inteiros
    colunas_numericas = ["RECEITA", "PERDA", "VENDA", "RESERVA", "GOOGLE", "PESQUISA", "CONSULTA"]
    for col in colunas_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    # ✅ Métricas resumo
    st.markdown("### Resumo")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Lojas", len(df))
    col2.metric("Receitas", f"{df['RECEITA'].sum()}" if "RECEITA" in df.columns else "0")    
    col3.metric("Perdas", f"{df['PERDA'].sum()}" if "PERDA" in df.columns else "0")
    col4.metric("Vendas", f"{df['VENDA'].sum()}" if "VENDA" in df.columns else "0")
    col5.metric("Google", f"{df['GOOGLE'].sum()}" if "GOOGLE" in df.columns else "0")

    # ✅ Exibir dataframe SEM índice (isso remove a primeira coluna numérica do pandas)
    st.markdown("### Dados por Loja")
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ✅ Botão de download
    try:
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False, engine="openpyxl")
        st.download_button(
            label="📥 Baixar como Excel",
            data=buffer.getvalue(),
            file_name="Relatorio por Loja.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except ImportError:
        st.info("📦 Instale `openpyxl`: `pip install openpyxl`")
    except Exception as e:
        st.error(f"Erro ao gerar o arquivo Excel: {e}")