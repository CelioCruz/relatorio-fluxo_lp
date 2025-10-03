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
            'receita': ['receita', 'receitas', 'faturamento'], 
            'perda': ['perda', 'perdas', 'cancelamentos'],            
            'venda': ['venda', 'vendas', 'pedidos'],
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
                "Vendedor": vendedor_chave,
                "RECEITA": 0,
                "PERDA": 0,
                "VENDA": 0,
                "RESERVA": 0,
            }
            for campo in mapeamento_campos.keys():
                total = round(valores[campo], 2)
                linha[campo.upper()] = int(total) if total.is_integer() else total
            dados_agrupados.append(linha)

        return dados_agrupados

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

    # Acumula reservas até ontem por loja + vendedor
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
                    valor_reserva = float(str(valor_reserva).replace(",", "."))
                    reserva_acumulada_por_loja_vendedor[chave] += valor_reserva
                except (ValueError, TypeError):
                    continue
        except ValueError:
            continue

    # Dados de HOJE
    dados_hoje = [row for row in dados_loja if row.get(coluna_data, "").strip() == str_hoje]
    dados_hoje_agrupados = agrupar_por_vendedor(dados_hoje, loja_selecionada)

    # Monta relatório final
    dados_agrupados = []
    vendedores_processados = set()

    # 1. Com dados de HOJE
    for row in dados_hoje_agrupados:
        loja_vendedor = f"{row['LOJA']} - {row['Vendedor']}"
        vendedores_processados.add(loja_vendedor)
        reserva_acumulada = reserva_acumulada_por_loja_vendedor.get(loja_vendedor, 0.0)
        if reserva_acumulada > 0:
            novo_row = row.copy()
            novo_row["RECEITA"] = int(round(novo_row.get("RECEITA", 0)))
            novo_row["RESERVA_ACUMULADA"] = int(round(reserva_acumulada))
            dados_agrupados.append(novo_row)

    # 2. Sem dados de HOJE, mas com reserva acumulada > 0
    for chave, reserva_acumulada in reserva_acumulada_por_loja_vendedor.items():
        if chave not in vendedores_processados and reserva_acumulada > 0:
            partes = chave.split(" - ", 1)
            loja_chave = partes[0]
            vendedor_chave = partes[1] if len(partes) > 1 else "[SEM VENDEDOR]"
            novo_row = {
                "LOJA": loja_chave,
                "Vendedor": vendedor_chave,
                "RECEITA": 0,
                "PERDA": 0,
                "VENDA": 0,
                "RESERVA": 0,
                "RESERVA_ACUMULADA": int(round(reserva_acumulada)),
            }
            dados_agrupados.append(novo_row)

    if not dados_agrupados:
        st.info("Nenhum vendedor com reservas acumuladas até ontem para esta loja.")
        return

    # Ordenar por RESERVA_ACUMULADA (decrescente)
    df = pd.DataFrame(dados_agrupados)
    df = df.sort_values(by="RESERVA_ACUMULADA", ascending=False).reset_index(drop=True)

    # Exibir SEM índice e em tela cheia
    st.dataframe(
        df.style.format({
            "ATENDIMENTO": "{:.0f}",
            "RECEITA": "{:.0f}",
            "PERDA": "{:.0f}",
            "VENDA": "{:.0f}",
            "RESERVA": "{:.0f}",
            "RESERVA_ACUMULADA": "{:.0f}"
        }),
        use_container_width=True,
        hide_index=True  
    )

    # Botão para download
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Relatório")
    output.seek(0)
    st.download_button(
        label="📥 Baixar Relatório em Excel",
        data=output,
        file_name=f"relatorio_reservas_{loja_selecionada}_{str_hoje.replace('/', '-')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )