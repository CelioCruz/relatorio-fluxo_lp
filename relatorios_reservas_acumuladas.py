import streamlit as st
import pandas as pd
from datetime import datetime
from collections import defaultdict
import io

try:
    from google_planilha import GooglePlanilha
except Exception as e:
    st.error(f'Erro ao importar GooglePlanilha: {e}')
    GooglePlanilha = None

def parse_date(date_str):
    if not date_str or not isinstance(date_str, (str, bytes)): return None
    try:
        clean_date = str(date_str).strip().split()[0]
        return datetime.strptime(clean_date, '%d/%m/%Y').date()
    except:
        return None

def to_float(val):
    try: 
        return float(str(val).replace(',', '.')) if val else 0.0
    except: 
        return 0.0

def mostrar():
    st.title('📋 Reservas Acumuladas (Somente Ativas)')
    
    if GooglePlanilha is None: 
        st.error("Erro: Módulo GooglePlanilha não disponível.")
        return

    try:
        gsheet = GooglePlanilha()
        dados = gsheet.aba_relatorio.get_all_records()
        if not dados:
            st.warning('📭 Nenhum dado encontrado na planilha.')
            return
    except Exception as e:
        st.error(f'❌ Erro ao carregar dados da planilha: {e}')
        return

    # Colunas
    col_vendedor = 'VENDEDOR'
    col_loja = 'LOJA'
    col_cliente = 'CLIENTE'
    col_data = 'DATA'
    col_reservas = 'RESERVAS'
    col_receitas = 'RECEITAS'
    col_perdas = 'PERDAS'
    col_vendas = 'VENDAS'

    # Filtro de Vendedor
    vendedores = sorted(list(set(str(row.get(col_vendedor, '')).strip() for row in dados if str(row.get(col_vendedor, '')).strip())))
    vendedor_selecionado = st.selectbox('Filtrar por Vendedor:', ['Todos'] + vendedores)

    # Processamento
    reservas_por_cliente = defaultdict(float)
    ultima_data_cliente = {}
    
    # Totais para o resumo (baseado no filtro)
    total_receita = 0.0
    total_perdas = 0.0
    total_vendas_geral = 0.0
    total_reserva_mov = 0.0

    for row in dados:
        vendedor = str(row.get(col_vendedor, '')).strip()
        if not vendedor: continue
        
        # Aplicar filtro de vendedor
        if vendedor_selecionado != 'Todos' and vendedor != vendedor_selecionado:
            continue

        loja = str(row.get(col_loja, '')).strip()
        cliente = str(row.get(col_cliente, '')).strip()
        if not cliente: cliente = "[SEM NOME]"
        
        chave = (loja, vendedor, cliente)
        
        # Data da última movimentação do cliente
        data_row = parse_date(row.get(col_data, ''))
        if data_row:
            if chave not in ultima_data_cliente or data_row > ultima_data_cliente[chave]:
                ultima_data_cliente[chave] = data_row

        # Lógica de Saldo Ativo: Reservas - Vendas
        v_res = to_float(row.get(col_reservas, 0))
        v_ven = to_float(row.get(col_vendas, 0))
        
        # O saldo diminui quando há uma venda para o mesmo cliente
        reservas_por_cliente[chave] += (v_res - v_ven)
        
        # Totais para o resumo
        total_receita += to_float(row.get(col_receitas, 0))
        total_perdas += to_float(row.get(col_perdas, 0))
        total_vendas_geral += v_ven
        total_reserva_mov += v_res

    # Montar lista apenas com o que está ATIVO (saldo > 0)
    relatorio_lista = []
    for (loja, vendedor, cliente), saldo in reservas_por_cliente.items():
        if saldo > 0:
            dt = ultima_data_cliente.get((loja, vendedor, cliente))
            dt_str = dt.strftime('%d/%m/%Y') if dt else 'N/A'
            relatorio_lista.append({
                'DATA': dt_str,
                'LOJA': loja,
                'VENDEDOR': vendedor,
                'CLIENTE': cliente,
                'QUANTIDADE ACUMULADA': int(saldo)
            })

    if not relatorio_lista:
        st.info('📭 Nenhuma reserva ativa encontrada.')
        exibir_resumo(total_receita, total_perdas, total_vendas_geral, total_reserva_mov, 0)
        return

    df = pd.DataFrame(relatorio_lista)
    
    # Ordenação
    df['_sort_date'] = pd.to_datetime(df['DATA'], format='%d/%m/%Y', errors='coerce')
    df = df.sort_values(['_sort_date', 'CLIENTE'], ascending=[False, True]).drop(columns=['_sort_date'])

    # Exibir Tabela
    st.dataframe(df, width="stretch", hide_index=True)

    # Total acumulado final (soma dos saldos ativos)
    total_acumuladas_final = int(df['QUANTIDADE ACUMULADA'].sum())

    # Exibir Resumo solicitado
    exibir_resumo(total_receita, total_perdas, total_vendas_geral, total_reserva_mov, total_acumuladas_final)

    # Download
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine='openpyxl')
    st.download_button('📥 Baixar Excel Reservas', buffer.getvalue(), 'Reservas_Ativas.xlsx')

def exibir_resumo(receita, perdas, vendas, reserva, acumuladas):
    st.markdown('---')
    st.markdown('### 📊 Resumo')
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric('Receita', f'R$ {int(receita)}')
    c2.metric('Perdas', int(perdas))
    c3.metric('Vendas', int(vendas))
    c4.metric('Reserva', int(reserva))
    c5.metric('Acumuladas', int(acumuladas))