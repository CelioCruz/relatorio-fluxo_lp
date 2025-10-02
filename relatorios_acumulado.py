import streamlit as st
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
import io

try:
    from google_planilha import GooglePlanilha
except Exception as e:
    st.error(f"Erro ao importar 'google_planilha.py': {e}")
    st.stop()

def mostrar():
    st.title("📊 Relatório por Loja e Vendedor (Reservas Acumuladas até Ontem)")

    try:
        gsheet = GooglePlanilha()
    except Exception as e:
        st.error(f"Não foi possível conectar ao Google Sheets:\n{e}")
        return

    try:
        dados = gsheet.aba_relatorio.get_all_records()
        if not dados:
            st.warning("Nenhum dado encontrado na planilha.")
            return
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return

    def carregar_lojas_unicas(dados):
        coluna_loja = None
        for key in dados[0].keys():
            if key.strip().lower() in ['loja', 'unidade', 'filial', 'local']:
                coluna_loja = key
                break
        if not coluna_loja:
            return []
        lojas = {str(row[coluna_loja]).strip() for row in dados if row.get(coluna_loja)}
        lojas_unicas = sorted([l for l in lojas if l and l.lower() not in ['nan', '']])
        return lojas_unicas

    lojas_unicas = carregar_lojas_unicas(dados)
    if not lojas_unicas:
        st.error("Coluna 'Loja' não encontrada ou sem dados.")
        return

    loja_selecionada = st.selectbox("Selecione uma loja", lojas_unicas, key="select_loja_acumulado")

    if not loja_selecionada:
        st.info("Selecione uma loja para gerar o relatório.")
        return

    def filtrar_por_loja(dados, loja):
        coluna_loja = None
        for key in dados[0].keys():
            if key.strip().lower() in ['loja', 'unidade', 'filial', 'local']:
                coluna_loja = key
                break
        if not coluna_loja:
            return dados
        return [
            row for row in dados
            if str(row.get(coluna_loja, "")).strip().lower() == loja.strip().lower()
        ]

    def agrupar_por_vendedor(dados, loja):
        if not dados:
            return []
        coluna_vendedor = None
        for key in dados[0].keys():
            if key.strip().lower() in ['vendedor', 'vendedora', 'funcionário', 'vend']:
                coluna_vendedor = key
                break
        if not coluna_vendedor:
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
            chave = f"{loja} - {vendedor}"
            for campo, col in colunas_valor.items():
                valor_str = str(row.get(col, "")).strip()
                if not valor_str:
                    continue
                try:
                    valor = float(valor_str.replace(",", "."))
                    resultado[chave][campo] += valor
                except ValueError:
                    continue

        dados_agrupados = []
        for chave, valores in resultado.items():
            partes = chave.split(" - ", 1)
            loja_chave = partes[0]
            vendedor_chave = partes[1]
            linha = {
                "LOJA": loja_chave,
                "Vendedor": vendedor_chave
            }
            for campo in mapeamento_campos.keys():
                total = round(valores[campo], 2)
                linha[campo.upper()] = int(total) if total.is_integer() else total
            dados_agrupados.append(linha)

        return sorted(dados_agrupados, key=lambda x: x.get("ATENDIMENTO", 0), reverse=True)

    hoje = datetime.now()
    str_hoje = hoje.strftime("%d/%m/%Y")
    ontem = hoje - timedelta(days=1)

    dados_loja = filtrar_por_loja(dados, loja_selecionada)

    coluna_reserva = coluna_data = coluna_vendedor = coluna_loja = None
    for key in dados[0].keys():
        k_lower = key.strip().lower()
        if not coluna_reserva and any(p in k_lower for p in ['reserva', 'reservas', 'agendamento']):
            coluna_reserva = key
        if not coluna_data and k_lower in ['data', 'datas', 'dt']:
            coluna_data = key
        if not coluna_vendedor and k_lower in ['vendedor', 'vendedora', 'funcionário', 'vend']:
            coluna_vendedor = key
        if not coluna_loja and k_lower in ['loja', 'unidade', 'filial', 'local']:
            coluna_loja = key

    if not all([coluna_reserva, coluna_data, coluna_vendedor]):
        st.error("Colunas essenciais não encontradas: Data, Vendedor ou Reserva.")
        return

    reserva_acumulada_por_loja_vendedor = defaultdict(float)
    for row in dados_loja:
        data_str = row.get(coluna_data, "").strip()
        if not data_str:
            continue
        try:
            data_row = datetime.strptime(data_str, "%d/%m/%Y")
            if data_row <= ontem:
                vendedor = str(row.get(coluna_vendedor, "")).strip() or "[SEM VENDEDOR]"
                loja_row = str(row.get(coluna_loja, "")).strip() or loja_selecionada
                chave = f"{loja_row} - {vendedor}"
                valor_reserva = row.get(coluna_reserva, 0)
                try:
                    valor_reserva = float(valor_reserva) if isinstance(valor_reserva, str) else float(valor_reserva)
                    reserva_acumulada_por_loja_vendedor[chave] += valor_reserva
                except (ValueError, TypeError):
                    continue
        except ValueError:
            continue

    dados_hoje = [row for row in dados_loja if row.get(coluna_data, "").strip() == str_hoje]
    dados_hoje_agrupados = agrupar_por_vendedor(dados_hoje, loja_selecionada)

    dados_agrupados = []
    vendedores_processados = set()

    for row in dados_hoje_agrupados:
        loja_vendedor = f"{row['LOJA']} - {row['Vendedor']}"
        vendedores_processados.add(loja_vendedor)
        reserva_acumulada = reserva_acumulada_por_loja_vendedor.get(loja_vendedor, 0.0)
        novo_row = row.copy()
        novo_row["RESERVA_ACUMULADA"] = reserva_acumulada
        dados_agrupados.append(novo_row)

    for chave, reserva_acumulada in reserva_acumulada_por_loja_vendedor.items():
        if chave not in vendedores_processados:
            partes = chave.split(" - ", 1)
            loja_chave = partes[0]
            vendedor_chave = partes[1]
            novo_row = {
                "LOJA": loja_chave,
                "Vendedor": vendedor_chave,
                "ATENDIMENTO": 0,
                "RECEITA": 0.0,
                "VENDA": 0.0,
                "PERDA": 0.0,
                "PESQUISA": 0,
                "CONSULTA": 0,
                "RESERVA_ACUMULADA": reserva_acumulada
            }
            dados_agrupados.append(novo_row)

    dados_agrupados.sort(key=lambda x: x.get("ATENDIMENTO", 0), reverse=True)

    if not dados_agrupados:
        st.info("Nenhum dado encontrado para esta loja.")
    else:
        # ✅ CRIAR O DATAFRAME AQUI
        df_exibicao = pd.DataFrame(dados_agrupados)

        # ✅ Converter colunas para numérico (evita erro do Arrow)
        colunas_int = ["ATENDIMENTO", "PESQUISA", "CONSULTA"]
        colunas_float = ["RECEITA", "VENDA", "PERDA", "RESERVA_ACUMULADA"]

        for col in colunas_int:
            if col in df_exibicao.columns:
                df_exibicao[col] = pd.to_numeric(df_exibicao[col], errors='coerce').fillna(0).astype('Int64')

        for col in colunas_float:
            if col in df_exibicao.columns:
                df_exibicao[col] = pd.to_numeric(df_exibicao[col], errors='coerce').fillna(0.0)

        # ✅ Exibir o DataFrame (só uma vez!)
        st.dataframe(df_exibicao, use_container_width=True)

        # ✅ Preparar para exportação
        df_export = df_exibicao.copy()

        # ✅ Botão de download
        try:
            buffer = io.BytesIO()
            df_export.to_excel(buffer, index=False, engine="openpyxl")
            st.download_button(
                label="📥 Baixar como Excel",
                data=buffer.getvalue(),
                file_name="Relatorio de Reservas Acumuladas.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except ImportError:
            st.info("📦 Instale `openpyxl`: `pip install openpyxl`")
        except Exception as e:
            st.error(f"Erro ao gerar o arquivo Excel: {e}")