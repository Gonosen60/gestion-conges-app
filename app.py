import streamlit as st
import pandas as pd
import requests
import datetime
from datetime import date

# --- CONFIGURATION ---
st.set_page_config(page_title="Gestion Expert Congés", page_icon="🗓️", layout="wide")

# --- CSS PERSONNALISÉ ---
st.markdown("""
<style>
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    div[data-testid="stExpander"] { border: none; box-shadow: none; }
</style>
""", unsafe_allow_html=True)

# --- 1. FONCTIONS MÉTIER ---

@st.cache_data
def get_jours_feries(annee):
    """API Gouv: Jours fériés"""
    url = f"https://calendrier.api.gouv.fr/jours-feries/metropole/{annee}.json"
    try:
        resp = requests.get(url)
        return list(resp.json().keys()) if resp.status_code == 200 else []
    except:
        return []

# Vacances Zone B (Amiens)
VACANCES_ZONE_B = [
    ("2025-02-08", "2025-02-24", "Hiver 2025"),
    ("2025-04-05", "2025-04-22", "Printemps 2025"),
    ("2025-07-05", "2025-09-01", "Été 2025"),
    ("2025-10-18", "2025-11-03", "Toussaint 2025"),
    ("2025-12-20", "2026-01-05", "Noël 2025"),
    ("2026-02-14", "2026-03-02", "Hiver 2026"),
    ("2026-04-11", "2026-04-27", "Printemps 2026"),
    ("2026-07-04", "2026-09-01", "Été 2026"),
]

def est_vacances(d):
    d_ts = pd.to_datetime(d)
    for start, end, name in VACANCES_ZONE_B:
        if pd.to_datetime(start) <= d_ts <= pd.to_datetime(end):
            return name
    return None

def calculer_jours_ouvres(start, end, feries_list):
    """Retourne le nb de jours et le détail textuel"""
    date_range = pd.date_range(start, end)
    feries_dt = pd.to_datetime(feries_list)
    count = 0
    details = []
    
    for d in date_range:
        d_str = d.strftime('%d/%m')
        if d.weekday() >= 5: 
            details.append(f"{d_str}: WE")
        elif d in feries_dt:
            details.append(f"{d_str}: Férié")
        else:
            vac = est_vacances(d)
            count += 1
    return count, details

def recalculer_droits_frac_robuste(df_conges, annee_ref):
    """
    Calcul automatique des droits FRAC (Correction V3.1)
    Gère robuste les formats de dates hétérogènes.
    """
    if df_conges.empty: return 0, 0
    
    jours_hors_periode = 0
    
    # On force tout en Timestamp Pandas pour comparer des pommes avec des pommes
    debut_ete = pd.Timestamp(year=annee_ref, month=5, day=1)
    fin_ete = pd.Timestamp(year=annee_ref, month=10, day=31)

    # Filtrer uniquement les CA
    if 'Type' in df_conges.columns:
        ca_rows = df_conges[df_conges['Type'] == 'CA']
    else:
        return 0, 0
    
    for _, row in ca_rows.iterrows():
        # Conversion sécurisée en Timestamp
        try:
            d_start = pd.to_datetime(row['Début'])
            d_end = pd.to_datetime(row['Fin'])
            
            # Générer la plage
            current_range = pd.date_range(d_start, d_end)
            
            for jour in current_range:
                # Vérification purement calendaire (hors 1er Mai - 31 Oct)
                if jour < debut_ete or jour > fin_ete:
                    jours_hors_periode += 1
        except:
            continue # Si erreur de date sur une ligne, on passe
    
    bonus = 0
    if jours_hors_periode >= 8: bonus = 2
    elif 5 <= jours_hors_periode <= 7: bonus = 1
        
    return bonus, jours_hors_periode

# --- 2. INITIALISATION ---

if 'conges' not in st.session_state:
    st.session_state.conges = []

st.title("🏗️ Gestionnaire Expert Congés")

# --- 3. BARRE LATÉRALE (Paramètres) ---
with st.sidebar:
    st.header("⚙️ Paramètres")
    annee_ref = st.number_input("Année Référence", value=2025, min_value=2024)
    
    st.divider()
    st.subheader("Mes Droits (Soldes initiaux)")
    d_ca = st.number_input("CA", value=25)
    d_rtt = st.number_input("RTT", value=15)
    d_rc = st.number_input("RC", value=0)
    d_cet = st.number_input("CET", value=0)
    d_rtti = st.number_input("RTTI", value=0)

# Préparation données globales
feries = get_jours_feries(annee_ref) + get_jours_feries(annee_ref + 1)
limit_min = datetime.date(annee_ref, 1, 1)
limit_max = datetime.date(annee_ref + 1, 3, 31)

# --- 4. ZONE DE SAISIE (AVEC CALCUL DYNAMIQUE) ---
st.subheader("1. Nouvelle demande")

with st.container():
    col1, col2, col3, col4 = st.columns([1.5, 2, 2, 1.5])
    
    with col1:
        new_type = st.selectbox("Type", ["CA", "RTT", "RC", "CET", "RTTI", "FRAC"])
    with col2:
        new_start = st.date_input("Du", value=date.today(), min_value=limit_min, max_value=limit_max, format="DD/MM/YYYY")
    with col3:
        new_end = st.date_input("Au", value=date.today(), min_value=limit_min, max_value=limit_max, format="DD/MM/YYYY")

    # >>> CALCUL DYNAMIQUE <<<
    jours_calc = 0
    if new_end >= new_start:
        jours_calc, details_calc = calculer_jours_ouvres(new_start, new_end, feries)
        if jours_calc > 0:
            st.info(f"⏱️ **Simulation : {jours_calc} jours** seront décomptés.")
        else:
            st.warning("⚠️ 0 jour décompté (Week-end ou Férié).")
    else:
        st.error("Date de fin incorrecte.")

    with col4:
        st.write("") 
        st.write("")
        if st.button("Valider ✅", type="primary", disabled=(jours_calc==0)):
            st.session_state.conges.append({
                "Type": new_type,
                "Début": new_start,
                "Fin": new_end,
                "Jours": jours_calc,
            })
            st.rerun()

st.divider()

# --- 5. TABLEAU INTERACTIF (HISTORIQUE) ---
st.subheader("2. Historique & Modifications")
st.caption("Sélectionnez une ligne et appuyez sur 'Suppr' (ou la corbeille) pour l'effacer.")

edited_df = pd.DataFrame() # Valeur par défaut

if len(st.session_state.conges) > 0:
    df_current = pd.DataFrame(st.session_state.conges)
    
    # Configuration de l'éditeur
    edited_df = st.data_editor(
        df_current,
        num_rows="dynamic",
        use_container_width=True,
        key="editor_conges",
        column_config={
            "Début": st.column_config.DateColumn("Début", format="DD/MM/YYYY"),
            "Fin": st.column_config.DateColumn("Fin", format="DD/MM/YYYY"),
            "Jours": st.column_config.NumberColumn("Jours", disabled=True),
            "Type": st.column_config.SelectboxColumn("Type", options=["CA", "RTT", "RC", "CET", "RTTI", "FRAC"])
        }
    )
    
    # Synchronisation State <-> Éditeur
    # Si le dataframe édité est différent du state actuel, on met à jour
    if not edited_df.equals(df_current):
        # On nettoie les dates pour éviter les bugs de format
        try:
            edited_df['Début'] = pd.to_datetime(edited_df['Début']).dt.date
            edited_df['Fin'] = pd.to_datetime(edited_df['Fin']).dt.date
            st.session_state.conges = edited_df.to_dict('records')
            st.rerun()
        except Exception as e:
            st.warning("Erreur de format de date lors de l'édition.")

else:
    st.info("Aucun congé posé.")

# --- 6. TABLEAU DE BORD (COMPTEURS) ---
st.divider()
st.subheader("3. Synthèse des Droits")

# Calculs totaux sur la base de edited_df (le visuel actuel)
if edited_df.empty and len(st.session_state.conges) > 0:
     edited_df = pd.DataFrame(st.session_state.conges)

pris = {"CA": 0, "RTT": 0, "RC": 0, "CET": 0, "RTTI": 0, "FRAC": 0}
bonus_frac = 0
jours_hors = 0

if not edited_df.empty:
    # Somme par type
    gb = edited_df.groupby("Type")["Jours"].sum()
    for t in pris:
        if t in gb: pris[t] = gb[t]
    
    # Calcul FRAC corrigé
    bonus_frac, jours_hors = recalculer_droits_frac_robuste(edited_df, annee_ref)

# Affichage Cartes
c1, c2, c3, c4, c5, c6 = st.columns(6)

def show_metric(col, label, total, consomme, color):
    reste = total - consomme
    col.metric(label, f"{reste}", delta=f"Pris: {consomme}", delta_color="inverse")

show_metric(c1, "CA", d_ca, pris["CA"], "blue")
show_metric(c2, "RTT", d_rtt, pris["RTT"], "purple")
show_metric(c3, "RC", d_rc, pris["RC"], "orange")

# FRAC : Total = Droits acquis (bonus) - Pris
show_metric(c4, "FRAC", bonus_frac, pris["FRAC"], "green")

show_metric(c5, "CET", d_cet, pris["CET"], "gray")
show_metric(c6, "RTTI", d_rtti, pris["RTTI"], "red")

# Explication FRAC
if bonus_frac > 0:
    st.success(f"✅ Bonus FRAC : **+{bonus_frac} jours** acquis (Base : {jours_hors} jours CA posés hors période).")
elif jours_hors > 0:
    st.caption(f"ℹ️ Compteur FRAC : {jours_hors} jours CA hors période (Seuil à 5 jours pour +1).")
