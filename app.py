import streamlit as st
import pandas as pd
import requests
import datetime
from datetime import date

# --- CONFIGURATION ---
st.set_page_config(page_title="Gestion Congés & FRAC", page_icon="🗓️", layout="wide")

# --- STYLE CSS (Pour forcer l'affichage propre) ---
st.markdown("""
<style>
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# --- 1. FONCTIONS CALENDAIRES (API & LOGIQUE) ---

@st.cache_data
def get_jours_feries(annee):
    """Récupère les jours fériés via l'API officielle."""
    url = f"https://calendrier.api.gouv.fr/jours-feries/metropole/{annee}.json"
    try:
        resp = requests.get(url)
        return list(resp.json().keys()) if resp.status_code == 200 else []
    except:
        return []

# Vacances Zone B (Amiens) - Exemple de structure
VACANCES_ZONE_B = [
    ("2025-02-08", "2025-02-24", "Hiver"),
    ("2025-04-05", "2025-04-22", "Printemps"),
    ("2025-07-05", "2025-09-01", "Été"),
    ("2025-10-18", "2025-11-03", "Toussaint"),
    ("2025-12-20", "2026-01-05", "Noël"),
    ("2026-02-14", "2026-03-02", "Hiver"),
    ("2026-04-11", "2026-04-27", "Printemps"),
]

def est_vacances(d):
    d_ts = pd.to_datetime(d)
    for start, end, name in VACANCES_ZONE_B:
        if pd.to_datetime(start) <= d_ts <= pd.to_datetime(end):
            return name
    return None

def calculer_jours_ouvres(start, end, feries_list):
    """Compte les jours ouvrés (Lun-Ven hors fériés)."""
    date_range = pd.date_range(start, end)
    feries_dt = pd.to_datetime(feries_list)
    count = 0
    details = []
    
    for d in date_range:
        d_str = d.strftime('%d/%m/%Y')
        if d.weekday() >= 5: # Samedi=5, Dimanche=6
            details.append(f"{d_str} : Week-end")
        elif d in feries_dt:
            details.append(f"{d_str} : Férié")
        else:
            vac = est_vacances(d)
            info = f" ({vac})" if vac else ""
            count += 1
    return count, details

# --- 2. ALGORITHME DE CALCUL DES FRAC (AUTOMATIQUE) ---

def recalculer_droits_frac(conges_list, annee_ref):
    """
    Règle :
    - Période principale : 1er mai au 31 octobre.
    - Compte les jours de CA pris EN DEHORS de cette période.
    - Si jours 'hors période' >= 8  -> +2 FRAC
    - Si jours 'hors période' entre 5 et 7 -> +1 FRAC
    """
    jours_hors_periode = 0
    
    # Définition de la période estivale pour l'année de référence
    debut_ete = pd.to_datetime(datetime.date(annee_ref, 5, 1))
    fin_ete = pd.to_datetime(datetime.date(annee_ref, 10, 31))

    for c in conges_list:
        # Seuls les CA déclenchent du fractionnement
        if c['Type'] == 'CA':
            # On génère tous les jours de ce congé
            range_jours = pd.date_range(c['Début'], c['Fin'])
            for jour in range_jours:
                # Vérification : jour ouvré hors férié ? (Simplification : on suppose ici que le congé posé est validé ouvré)
                # Est-ce hors période estivale ?
                if jour < debut_ete or jour > fin_ete:
                    jours_hors_periode += 1
    
    bonus = 0
    if jours_hors_periode >= 8:
        bonus = 2
    elif 5 <= jours_hors_periode <= 7:
        bonus = 1
        
    return bonus, jours_hors_periode

# --- 3. INTERFACE UTILISATEUR ---

st.title("🏗️ Gestionnaire Expert Congés")

# Initialisation Session
if 'conges' not in st.session_state:
    st.session_state.conges = []

# --- SIDEBAR : PARAMÈTRES ---
with st.sidebar:
    st.header("1. Paramétrage")
    annee_ref = st.number_input("Année de référence (N)", value=2025, min_value=2024)
    
    st.subheader("Mes Droits Initiaux")
    droits_ca = st.number_input("Droits CA", value=25)
    droits_rtt = st.number_input("Droits RTT", value=15)
    droits_rc = st.number_input("Droits RC", value=0)
    droits_cet = st.number_input("Solde CET", value=0)
    droits_rtti = st.number_input("Solde RTTI", value=0)
    
    # Calcul automatique des FRAC en temps réel
    bonus_frac, jours_hors_p = recalculer_droits_frac(st.session_state.conges, annee_ref)
    st.markdown("---")
    st.markdown(f"**Calcul Automatique FRAC**")
    st.info(f"Jours CA hors période : {jours_hors_p}\n\n**Droit acquis : +{bonus_frac} jours**")

# --- LOGIQUE PRINCIPALE ---

# Chargement des fériés pour N et N+1
feries = get_jours_feries(annee_ref) + get_jours_feries(annee_ref + 1)

# Définition de la période de validité (Janvier N -> Mars N+1)
limit_min = datetime.date(annee_ref, 1, 1)
limit_max = datetime.date(annee_ref + 1, 3, 31)

st.markdown(f"### 📅 Période active : 01/01/{annee_ref} au 31/03/{annee_ref + 1}")

# --- FORMULAIRE DE SAISIE ---
with st.container():
    st.subheader("✈️ Poser une absence")
    c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
    
    with c1:
        type_c = st.selectbox("Type", ["CA", "RTT", "RC", "CET", "RTTI", "FRAC"])
    with c2:
        d_debut = st.date_input("Du", value=datetime.date.today(), min_value=limit_min, max_value=limit_max, format="DD/MM/YYYY")
    with c3:
        d_fin = st.date_input("Au", value=datetime.date.today(), min_value=limit_min, max_value=limit_max, format="DD/MM/YYYY")
    with c4:
        st.write("") 
        st.write("") 
        btn_add = st.button("Valider ➕")

    # Traitement
    if btn_add:
        if d_fin < d_debut:
            st.error("Erreur : La date de fin est antérieure au début.")
        else:
            nb, details = calculer_jours_ouvres(d_debut, d_fin, feries)
            if nb > 0:
                st.session_state.conges.append({
                    "Type": type_c,
                    "Début": d_debut,
                    "Fin": d_fin,
                    "Jours": nb
                })
                st.success(f"{nb} jours de {type_c} posés.")
                st.rerun()
            else:
                st.warning("Aucun jour ouvré décompté sur cette période (Week-end ou Férié).")

st.divider()

# --- TABLEAU DE BORD (Soldes) ---
st.subheader("📊 Synthèse des Soldes")

# Calcul des jours pris
df = pd.DataFrame(st.session_state.conges)
pris = {"CA": 0, "RTT": 0, "RC": 0, "CET": 0, "RTTI": 0, "FRAC": 0}

if not df.empty:
    gb = df.groupby("Type")["Jours"].sum()
    for t in pris:
        if t in gb: pris[t] = gb[t]

# Affichage Compteurs
cols = st.columns(6)
metriques = [
    ("CA", droits_ca, "blue"),
    ("RTT", droits_rtt, "purple"),
    ("RC", droits_rc, "orange"),
    ("FRAC", bonus_frac, "green"), # Ici on utilise le bonus calculé automatiquement
    ("CET", droits_cet, "gray"),
    ("RTTI", droits_rtti, "red")
]

for i, (label, total, color) in enumerate(metriques):
    conso = pris[label]
    reste = total - conso
    cols[i].metric(label, f"{reste}", delta=f"Pris : {conso}", delta_color="inverse")

# --- HISTORIQUE DÉTAILLÉ ---
st.subheader("📜 Historique")
if not df.empty:
    # Formatage des dates en FR pour l'affichage tableau
    df_display = df.copy()
    df_display['Début'] = pd.to_datetime(df_display['Début']).dt.strftime('%d/%m/%Y')
    df_display['Fin'] = pd.to_datetime(df_display['Fin']).dt.strftime('%d/%m/%Y')
    
    # Tri par date
    df_display = df_display.sort_values(by="Début", ascending=False)
    
    st.dataframe(
        df_display, 
        column_config={
            "Jours": st.column_config.NumberColumn("Jours", format="%d j")
        },
        use_container_width=True,
        hide_index=True
    )
    
    # Bouton Reset
    if st.button("🗑️ Tout effacer (Reset)"):
        st.session_state.conges = []
        st.rerun()
else:
    st.info("Aucune donnée saisie.")
