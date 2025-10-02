import streamlit as st
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import sys
import os
from collections import defaultdict
import pandas as pd
import io

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from google_planilha import GooglePlanilha
except Exception as e:
    st.error(f"Erro ao importar GooglePlanilha: {e}")
    GooglePlanilha = None

def mostrar():
    st.title("⏱️ Relatório em Tempo Real")
    
    st_autorefresh(interval=30000, key="tempo_real_refresh")

    agora = datetime.now().strftime("%H:%M:%S")
    st.markdown(f"### Hora atual: `{agora}`")

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
        st.error("❌ Coluna 'Loja' não encontrada.")
        return

    lojas_unicas = sorted({
        str(row[coluna_loja]).strip()
        for row in dados_brutos
        if row.get(coluna_loja) and str(row[coluna_loja]).strip().lower() not in ['nan', '', 'none']
    })

    if not lojas_unicas:
        st.warning("📭 Nenhuma loja encontrada.")
        return

    loja = st.selectbox("Selecione a loja:", lojas_unicas)
    if not loja:
        st.warning("⚠️ Selecione uma loja.")
        return

    def normalizar_loja(nome):
        return str(nome).strip().upper().replace(" ", "").replace("-", "")

    def get_col(headers, *names):
        col_map = {k.strip().lower(): k for k in headers}
        for n in names:
            if n.strip().lower() in col_map:
                return col_map[n.strip().lower()]
        return None

    try:
        hoje_str = datetime.now().strftime("%d/%m/%Y")
        headers = dados_brutos[0].keys()

        col_data = get_col(headers, 'data', 'datas', 'dt')
        col_loja_header = get_col(headers, 'loja', 'unidade', 'filial', 'local')
        col_vendedor = get_col(headers, 'vendedor', 'vendedora', 'responsável')
        col_receita = get_col(headers, 'receita', 'receitas', 'faturamento')
        col_venda = get_col(headers, 'venda', 'vendas', 'pedidos')
        col_perda = get_col(headers, 'perda', 'perdas', 'cancelamentos')
        col_reserva = get_col(headers, 'reserva', 'reservas', 'agendamento')
        col_pesquisa = get_col(headers, 'pesquisa', 'pesquisas', 'pesq')
        col_consulta = get_col(headers, 'consulta', 'exame de vista', 'exame', 'consultas')

        if not all([col_data, col_loja_header, col_vendedor]):
            st.error("❌ Colunas obrigatórias não encontradas: DATA, LOJA ou VENDEDOR")
            return

        dados_hoje = []
        for row in dados_brutos:
            if normalizar_loja(row.get(col_loja_header)) != normalizar_loja(loja):
                continue
            data_str = str(row.get(col_data, "")).strip().split()[0] if row.get(col_data) else ""
            try:
                if datetime.strptime(data_str, "%d/%m/%Y").strftime("%d/%m/%Y") == hoje_str:
                    dados_hoje.append(row)
            except:
                continue

        if not dados_hoje:
            st.info("📭 Nenhum dado encontrado para hoje nesta loja.")
            return

        resultado = defaultdict(lambda: defaultdict(int))

        for row in dados_hoje:
            vendedor = str(row.get(col_vendedor, "")).strip() or "[SEM VENDEDOR]"

            def somar(col, campo):
                if col:
                    try:
                        val = float(str(row.get(col, "0")).replace(",", "."))
                        resultado[vendedor][campo] += int(round(val))
                    except:
                        pass

            somar(col_receita, "RECEITAS")
            somar(col_venda, "VENDAS")
            somar(col_perda, "PERDAS")
            somar(col_pesquisa, "PESQUISAS")
            somar(col_consulta, "EXAME DE VISTA")
            somar(col_reserva, "RESERVAS")

        if not resultado:
            st.info("📭 Nenhum dado processado.")
            return

        lista_df = []
        for vendedor, metricas in resultado.items():
            linha = {"Vendedor": vendedor}
            linha.update(metricas)
            lista_df.append(linha)

        df = pd.DataFrame(lista_df)
        colunas_ordem = ["Vendedor", "RECEITAS", "VENDAS", "PERDAS", "RESERVAS", "PESQUISAS", "EXAME DE VISTA"]
        df = df.reindex(columns=colunas_ordem, fill_value=0)

        for col in df.columns:
            if col != "Vendedor":
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

        st.markdown(f"### 🏪 **{loja}**")
        st.markdown("---")

        for _, row in df.iterrows():
            with st.container():
                st.markdown(f"#### 👤 **{row['Vendedor']}**")
                cols = st.columns(6)
                metricas = ["RECEITAS", "VENDAS", "PERDAS", "RESERVAS", "PESQUISAS", "EXAME DE VISTA"]
                for i, m in enumerate(metricas):
                    with cols[i]:
                        st.metric(m, row[m])
                st.markdown("---")

        # ✅ Apenas UM botão: Baixar como Excel com nome fixo
        try:
            buffer = io.BytesIO()
            df.to_excel(buffer, index=False, engine="openpyxl")
            st.download_button(
                label="📥 Baixar como Excel",
                data=buffer.getvalue(),
                file_name="Relatorio em Tempo Real.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except ImportError:
            st.info("📦 Instale `openpyxl`: `pip install openpyxl`")
        except Exception as e:
            st.error(f"❌ Erro no download: {e}")

    except Exception as e:
        st.error(f"Erro ao gerar o arquivo Excel: {e}")