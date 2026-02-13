import streamlit as st
import pandas as pd
import requests
import datetime
from io import BytesIO

# --- CONFIGURATION ---
st.set_page_config(page_title="Mes Congés & RTT", page_icon="🗓️", layout="centered")

# --- DONNÉES ZONE B & FÉRIÉS ---
def get_jours_feries(annee):
    url = f"https://calendrier.api.gouv.fr/jours-feries/metropole/{annee}.json"
    try:
        resp = requests.get(url)
        return list(resp.json().keys()) if resp.status_code == 200 else []
    except:
        return []

# Vacances scolaires Zone B (Amiens) - Année 2025/2026
# Format: (Date début, Date fin, Nom)
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

def est_vacances(date_check):
    """Vérifie si une date tombe pendant les vacances scolaires."""
    d = pd.to_datetime(date_check)
    for start, end, name in VACANCES_ZONE_B:
        if pd.to_datetime(start) <= d <= pd.to_datetime(end):
            return name
    return None

def calculer_jours_ouvres(start, end, feries):
    """Calcule les jours à décompter (hors WE et Fériés)."""
    date_range = pd.date_range(start, end)
    feries_dt = pd.to_datetime(feries)
    count = 0
    details = []
    
    for d in date_range:
        if d.weekday() >= 5: # Samedi/Dimanche
            details.append(f"{d.strftime('%d/%m')} : Week-end")
        elif d in feries_dt:
            details.append(f"{d.strftime('%d/%m')} : Férié")
        else:
            vac_name = est_vacances(d)
            info = f" (Vacances {vac_name})" if vac_name else ""
            count += 1
    return count, details

# --- INTERFACE ---
st.title("🏖️ Mon Compteur Congés")
st.caption("Zone B (Amiens) | Jours Fériés France")

# Initialisation session
if 'conges' not in st.session_state:
    st.session_state.conges = []

# Sidebar : Configuration
with st.sidebar:
    st.header("1. Mes Droits Annuels")
    solde_ca = st.number_input("Droits CA", value=25)
    solde_rtt = st.number_input("Droits RTT", value=15)
    solde_cet = st.number_input("Epargne (CET)", value=0)
    solde_frac = st.number_input("Fractionnement", value=2)
    
    st.divider()
    st.header("3. Sauvegarde")
    # Export CSV pour ne pas perdre les données
    if st.session_state.conges:
        df_export = pd.DataFrame(st.session_state.conges)
        csv = df_export.to_csv(index=False).encode('utf-8')
        st.download_button("💾 Sauvegarder mes congés (CSV)", csv, "mes_conges.csv", "text/csv")

# Corps principal
annee_courante = datetime.date.today().year
feries = get_jours_feries(annee_courante) + get_jours_feries(annee_courante + 1)

# Formulaire de pose
st.subheader("2. Poser des dates")
col1, col2, col3 = st.columns(3)
type_c = col1.selectbox("Type", ["CA", "RTT", "CET", "FRAC", "RTTI"])
d_debut = col2.date_input("Début")
d_fin = col3.date_input("Fin")

if d_fin >= d_debut:
    nb, details = calculer_jours_ouvres(d_debut, d_fin, feries)
    st.info(f"Cela représente **{nb} jours** à déduire.")
    
    if st.button("Valider la demande ✅", type="primary"):
        st.session_state.conges.append({
            "Type": type_c, "Début": d_debut, "Fin": d_fin, "Jours": nb
        })
        st.success("Ajouté !")
        st.rerun() # Rafraichir

# Tableau de bord
st.divider()
st.subheader("📊 État des lieux")

# Calculs
df = pd.DataFrame(st.session_state.conges)
pris = {"CA": 0, "RTT": 0, "CET": 0, "FRAC": 0, "RTTI": 0}
if not df.empty:
    gb = df.groupby("Type")["Jours"].sum()
    for t in pris:
        if t in gb: pris[t] = gb[t]

# Affichage des cartes (Métriques)
c1, c2, c3, c4 = st.columns(4)
c1.metric("CA Restants", solde_ca - pris["CA"], delta=f"-{pris['CA']} pris")
c2.metric("RTT Restants", solde_rtt - pris["RTT"], delta=f"-{pris['RTT']} pris")
c3.metric("CET Restant", solde_cet - pris["CET"], delta=f"-{pris['CET']} pris")
c4.metric("FRAC Restant", solde_frac - pris["FRAC"], delta=f"-{pris['FRAC']} pris")

# Historique
if not df.empty:
    st.write("### Historique")
    st.dataframe(df.sort_values(by="Début", ascending=False), use_container_width=True)
