import streamlit as st
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
import io

try:
    from google_planilha import GooglePlanilha
except Exception as e:
    st.error(f'Erro ao importar GooglePlanilha: {e}')
    st.stop()

def parse_date(date_str):
    if not date_str or not isinstance(date_str, str): return None
    try:
        return datetime.strptime(date_str.strip().split()[0], '%d/%m/%Y').date()
    except: return None

def mostrar():
    st.title('📊 Relatório Acumulado por Loja e Vendedor')

    try:
        gsheet = GooglePlanilha()
        dados = gsheet.aba_relatorio.get_all_records()
        if not dados:
            st.warning('📭 Nenhum dado encontrado na planilha.')
            return
    except Exception as e:
        st.error(f'❌ Erro ao carregar dados: {e}')
        return

    # Mapeamento EXATO
    col_loja = 'LOJA'
    col_data = 'DATA'
    col_vendedor = 'VENDEDOR'
    col_receitas = 'RECEITAS'
    col_perdas = 'PERDAS'
    col_vendas = 'VENDAS'
    col_reservas = 'RESERVAS'
    col_google = 'GOOGLE'

    # Verificar se as colunas existem
    headers = dados[0].keys()
    for c in [col_loja, col_data, col_vendedor, col_reservas, col_google]:
        if c not in headers:
            st.error(f'❌ Coluna essencial não encontrada: {c}')
            return

    hoje = datetime.now().date()
    ontem = hoje - timedelta(days=1)

    # Acumuladores (até ontem)
    reserva_acumulada = defaultdict(int)
    google_acumulado = defaultdict(int)
    vendedores_vistos = set()

    for row in dados:
        loja = str(row.get(col_loja, '')).strip()
        vendedor = str(row.get(col_vendedor, '')).strip()
        if not loja or not vendedor: continue
        
        chave = f'{loja} - {vendedor}'
        vendedores_vistos.add((loja, vendedor))
        
        data_row = parse_date(row.get(col_data, ''))
        if data_row and data_row <= ontem:
            # Acumular Reservas (regra: 1 ou -1)
            val_res = str(row.get(col_reservas, 0)).replace(',', '.')
            try:
                v_res = float(val_res)
                if v_res == -1: reserva_acumulada[chave] -= 1
                elif v_res > 0: reserva_acumulada[chave] += 1
            except: pass

            # Acumular Google (numeral)
            val_goo = str(row.get(col_google, 0)).replace(',', '.')
            try:
                v_goo = int(float(val_goo))
                google_acumulado[chave] += v_goo
            except: pass

    # Métricas de HOJE
    metricas_hoje = defaultdict(lambda: defaultdict(int))
    for row in dados:
        data_row = parse_date(row.get(col_data, ''))
        if data_row != hoje: continue
        
        loja = str(row.get(col_loja, '')).strip()
        vendedor = str(row.get(col_vendedor, '')).strip()
        chave = (loja, vendedor)

        for campo in [col_receitas, col_perdas, col_vendas, col_reservas, col_google]:
            val = str(row.get(campo, 0)).replace(',', '.')
            try:
                metricas_hoje[chave][campo] += int(float(val))
            except: pass

    # Montar Relatório
    relatorio = []
    for (loja, vendedor) in sorted(vendedores_vistos):
        chave_str = f'{loja} - {vendedor}'
        acc_res = max(0, reserva_acumulada[chave_str])
        acc_goo = google_acumulado[chave_str]
        
        m_hoje = metricas_hoje[(loja, vendedor)]
        
        # Atualizar acumulados com os dados de HOJE
        hoje_res = m_hoje.get(col_reservas, 0)
        if hoje_res == -1: acc_res = max(0, acc_res - 1)
        elif hoje_res > 0: acc_res += 1
        
        acc_goo += m_hoje.get(col_google, 0)

        # Só exibe se houver reserva acumulada
        if acc_res > 0:
            relatorio.append({
                'DATA': hoje.strftime('%d/%m/%Y'),
                'LOJA': loja,
                'VENDEDOR': vendedor,
                'RECEITAS': m_hoje.get(col_receitas, 0),
                'PERDAS': m_hoje.get(col_perdas, 0),
                'VENDAS': m_hoje.get(col_vendas, 0),
                'RESERVA': hoje_res,
                'RESERVA_ACUMULADA': acc_res,
                'GOOGLE_ACUMULADO': acc_goo
            })

    if not relatorio:
        st.info('📭 Nenhum vendedor com reserva acumulada para hoje.')
        return

    df = pd.DataFrame(relatorio)
    # Limpeza para Inteiro Puro e Vazio
    for col in df.columns:
        if col not in ['DATA', 'LOJA', 'VENDEDOR']:
            df[col] = df[col].apply(lambda x: str(int(x)) if x != 0 else '')

    st.dataframe(df, use_container_width=True)

    # Botão Download
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine='openpyxl')
    st.download_button('📥 Baixar Acumulado Excel', buffer.getvalue(), 'Relatorio Acumulado.xlsx')