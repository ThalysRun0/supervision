import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import pandas as pd

def generate_plot(df):
    if df.empty:
        st.info("No event data available")
        return
    fig = px.histogram(df, x="timestamp", color="source", nbins=50,
                       title="Weak signals detected in logs",
                       labels={"timestamp": "Hour", "count": "Events"})
    st.plotly_chart(fig, use_container_width=True)

def generate_proc_plot(df):
    df_exploded = df.explode("category").dropna(subset=["category"])
    fig = px.histogram(df_exploded, x="category", color="category", 
#                       title="Process types",
                       labels={"category": "Categories"})
    fig.update_layout(bargap=0.2, xaxis_title="Categories", yaxis_title="Process count")
    st.plotly_chart(fig.update_layout(showlegend=False), use_container_width=True)

def generate_irq_proc(df, top_n=10):
    # Create heatmap with Plotly
    num_cpus = df['num_cpu'].max()
    df_top = df.sort_values("num_cpu", ascending=False).head(top_n)
    df_melted = df_top.melt(id_vars=["device"], value_vars=[f"CPU{i}" for i in range(num_cpus)],
                            var_name="CPU", value_name="Irq")
    pivot_df = df_melted.pivot(index="device", columns="CPU", values="Irq")
    pivot_rotated = pivot_df.T
    fig = px.imshow(
        pivot_rotated,
        color_continuous_scale="Viridis",
        labels={"color": "Irq"},
#        title="Distribution by CPU and Device",
    )
    st.plotly_chart(fig.update_layout(showlegend=False), use_container_width=True)

def generate_power_plot(df):
    if not df.empty:
        fig = px.line(
            df,
            x="timestamp",
            y="watts",
            markers=True,
            labels={"timestamp": "Hour", "watts": "Watts"}
        )
        st.plotly_chart(fig.update_layout(showlegend=False), use_container_width=True)
    else:
        st.info("CPU data consumption not yet available")

def generate_network_plot(df):
    if not df.empty:
        count_df = df.groupby("protocol").size().reset_index(name="count")
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)
        fig = px.bar(count_df, x="protocol", y="count", color="protocol", labels={"protocol": "Protocol", "count": "Connexions"})
#        count_by_time = df.resample("5min").size()
#        fig.add_trace(go.Scatter(
#            x=count_by_time.index,
#            y=count_by_time.values,
#            mode="lines+markers",
#            name="IP count",
#            yaxis="y2",
#            line=dict(color="orange")
#        ))
#        fig.update_layout(
#            yaxis2=dict(
#                title="IP count",
#                overlaying="y",
#                side="right",
#            ),
#            legend=dict(x=0, y=1.1, orientation="h"),
#            margin=dict(t=40, b=20)
#        )
        st.plotly_chart(fig.update_layout(showlegend=False), use_container_width=False)
    else:
        st.info("No active connexion regarding YAML parameters")