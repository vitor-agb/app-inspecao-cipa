import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# Simulação do dataframe contendo as semanas 10 a 22 e as volumetrias
data = {
    'Semana': [f'Sem {i}' for i in range(10, 23)],
    'Visao': [1, 2, 1, 3, 2, 1, 4, 2, 1, 3, 2, 1, 2],
    'Realizado': [45, 50, 42, 60, 55, 48, 65, 58, 47, 52, 49, 45, 50]
}
df = pd.DataFrame(data)

# Inicialização da figura do Plotly
fig = go.Figure()

# Inclusão da série correspondente à demanda inicial programada
fig.add_trace(go.Bar(
    x=df['Semana'],
    y=df['Visao'],
    name='Visão (Planejado)',
    marker_color='#D3D3D3' # Cinza claro para indicar menor peso
))

# Inclusão da série correspondente à demanda efetivamente executada
fig.add_trace(go.Bar(
    x=df['Semana'],
    y=df['Realizado'],
    name='Realizado',
    marker_color='#B22222' # Vermelho escuro para evidenciar o volume reativo
))

# Configuração de layout, agrupamento das barras e estilização do fundo
fig.update_layout(
    title='Comparativo: Visão vs Realizado (Semanas 10 a 22)',
    xaxis_title='Semanas',
    yaxis_title='Volume de Demandas',
    barmode='group',
    template='plotly_white',
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1
    )
)

# Renderização do gráfico na interface do Streamlit
st.plotly_chart(fig, use_container_width=True)