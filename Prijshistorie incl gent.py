import requests
import time
import pandas as pd
import streamlit as st

# --- API instellingen ---
API_BASE_URL = 'https://app-2drive-dab2-100330.proudwave-fe47a2ed.westeurope.azurecontainerapps.io/api'
AUTH_URL = 'https://vinacles.eu.auth0.com/oauth/token'
AUTH_CREDENTIALS = {
    'client_id': 'NlZMoM5v9XBGMpXrRKzqgzzviSZUs9Dp',
    'client_secret': 's_qkClB-Ms8Kzzd17HftdZVHeR1lnp9QWFyroJ0PRNIkN0cxieJm9Mc8YeJ82YYZ',
    'audience': 'api:vinalces.dab.100330',
    'grant_type': 'client_credentials'
}

ACCESS_TOKEN = None
TOKEN_EXPIRY = None

# --- Token ophalen ---
def get_token():
    global ACCESS_TOKEN, TOKEN_EXPIRY
    if ACCESS_TOKEN and time.time() < TOKEN_EXPIRY:
        return ACCESS_TOKEN

    try:
        response = requests.post(AUTH_URL, json=AUTH_CREDENTIALS, headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        token_data = response.json()
        ACCESS_TOKEN = token_data.get('access_token')
        TOKEN_EXPIRY = time.time() + token_data.get('expires_in', 0)
        return ACCESS_TOKEN
    except requests.exceptions.RequestException as e:
        st.error(f"Fout bij ophalen token: {e}")
        return None

# --- Data ophalen met retries ---
def get_data(endpoint, retries=5, delay=2):
    token = get_token()
    if not token:
        return pd.DataFrame()
    for attempt in range(retries):
        try:
            response = requests.get(f'{API_BASE_URL}/{endpoint}', headers={'Authorization': f'Bearer {token}'})
            response.raise_for_status()
            data = response.json()
            return pd.DataFrame(data.get('value', []))
        except requests.exceptions.RequestException as e:
            time.sleep(delay)
    st.warning(f"⚠️ Kan geen data ophalen van {endpoint} na {retries} pogingen")
    return pd.DataFrame()

# --- Werkorders laden per vestiging ---
@st.cache_data(ttl=3600)
def load_werkorders(affiliate_id):
    if affiliate_id == 259:
        df = pd.read_excel('wo tilburg.xlsx')
    else:
        df = get_data(f'GetAftersalesForAffiliateExtended?AffiliateId={affiliate_id}')

    if not df.empty:
        df = df[['WONUMMER', 'InvoicedDate']]
    return df

# --- Onderdelen laden per vestiging ---
@st.cache_data(ttl=3600)
def load_onderdelen(affiliate_id):
    if affiliate_id == 259:
        df = pd.read_excel('onderdelen tilburg.xlsx')  
    else:
        df = get_data(f'GetAftersalesPartsForAffiliateExtended?AffiliateId={affiliate_id}')
    return df

# --- Samengevoegde data per vestiging ---
def load_parts_for_affiliate(affiliate_id, label):
    wo = load_werkorders(affiliate_id)
    time.sleep(1)  # Kleine pauze om API niet te overbelasten
    onderdelen = load_onderdelen(affiliate_id)
    
    

    if wo.empty:
        st.warning(f"⚠️ Werkorders niet geladen ({label})")
        return pd.DataFrame()
    if onderdelen.empty:
        st.warning(f"⚠️ Onderdelen niet geladen ({label})")
        return pd.DataFrame()

    df = onderdelen.merge(wo, on='WONUMMER', how='left')
    df['AffiliateId'] = label

    # Zet om naar datetime
    df['InvoicedDate'] = pd.to_datetime(
        df['InvoicedDate'], errors='coerce'
        )

    # Filter op datum > 01-05-2025
    if affiliate_id == 259:  # Tilburg
        df = df[df['InvoicedDate'] > '2025-10-01']
   

    # Format weer naar string
    df['InvoicedDate'] = df['InvoicedDate'].dt.strftime('%d-%m-%Y')
        
    df = df.rename(columns={
        'PartNumber': 'Onderdeelnummer',
        'Price': 'Verkoopprijs',
        'CompanyName': 'Relatie',
        'AffiliateId': 'Vestiging',
        'InvoicedDate': 'Factuurdatum'
    })
    return df

# --- Prijshistorie van één onderdeel ---
def get_price_history(df, onderdeelnummer):
    history = df[df['Onderdeelnummer'] == onderdeelnummer][
        ['Onderdeelnummer', 'Verkoopprijs', 'Relatie', 'Vestiging', 'Factuurdatum']
    ]
    if history.empty:
        return None
    history['Factuurdatum'] = pd.to_datetime(history['Factuurdatum'], dayfirst=True, errors='coerce')
    history = history.sort_values(by='Factuurdatum', ascending=False)
    history['Factuurdatum'] = history['Factuurdatum'].dt.strftime('%d-%m-%Y')
    return history



# --- Prijshistorie van één onderdeel ---
def get_price_history_gent(df, onderdeelnummer):
    history = df[df['Onderdeelnummer'] == onderdeelnummer][
        ['Onderdeelnummer', 'Verkoopprijs', 'Relatie', 'Vestiging', 'Factuurdatum']
    ]
    if history.empty:
        return None
    history['Factuurdatum'] = pd.to_datetime(history['Factuurdatum'], dayfirst=True, errors='coerce')
    history = history.sort_values(by='Factuurdatum', ascending=False)
    history['Factuurdatum'] = history['Factuurdatum'].dt.strftime('%d-%m-%Y')
    return history

# --- Streamlit UI ---
def main():
    st.title('Prijshistorie van onderdelen')

    correct_password = st.secrets["auth"]["password"]
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        password_input = st.text_input("Voer het wachtwoord in:", type="password")
        if st.button("Inloggen"):
            if password_input == correct_password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.warning("Onjuist wachtwoord.")
        return

    affiliate_map = {
        "Tilburg": 259,
        "Rotterdam": 261,
        "Heerhugowaard": 467,
        "Gent": 123
    }

    vestigingen = ["— Kies een vestiging —"] + list(affiliate_map.keys())
    vestiging = st.selectbox("Kies een vestiging", vestigingen)

    if vestiging == "— Kies een vestiging —":
        st.info("Selecteer eerst een vestiging om data te laden")
        st.stop()

    affiliate_id = affiliate_map[vestiging]

    if "data" not in st.session_state:
        st.session_state.data = pd.DataFrame()

    if affiliate_id == 123:  # Gent heeft geen API, dus laad statisch bestand
        st.session_state.data = pd.read_excel('onderdelen gent.xlsx')


        onderdeelnummer = st.text_input('Voer het onderdeelnummer in:')
        if onderdeelnummer:
            history = get_price_history_gent(data, onderdeelnummer)
            if history is not None:
                st.write(f'Prijshistorie voor onderdeelnummer {onderdeelnummer}:')
                history.index = range(1, len(history)+1)
                st.dataframe(history)
            else:
                st.write(f'Geen resultaten gevonden voor onderdeelnummer {onderdeelnummer}.')




    else:
        # Laad data pas als gebruiker op knop klikt
        if st.button("Laad onderdelen voor deze vestiging"):
            st.session_state.data = load_parts_for_affiliate(affiliate_id, vestiging)

        data = st.session_state.data

        onderdeelnummer = st.text_input('Voer het onderdeelnummer in:')
        if onderdeelnummer:
            history = get_price_history(data, onderdeelnummer)
            if history is not None:
                st.write(f'Prijshistorie voor onderdeelnummer {onderdeelnummer}:')
                history.index = range(1, len(history)+1)
                st.dataframe(history)
            else:
                st.write(f'Geen resultaten gevonden voor onderdeelnummer {onderdeelnummer}.')

if __name__ == '__main__':
    main()
