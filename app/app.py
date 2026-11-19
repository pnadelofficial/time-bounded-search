import streamlit as st
import utils as u
import traitlets
from streamlit_anywidget import anywidget

st.title("Hepatitis C Timeline")

st.set_page_config(layout="wide")

items = u.load_data()
tl = u.VisTimeline(items=items)
anywidget(tl)