"""Barra laterale: data e ora in tempo reale (orologio nel browser) e meteo (Open-Meteo, senza chiave).
Citta' predefinita Milano; si cambia con i Secrets METEO_CITTA, METEO_LAT, METEO_LON."""
import json
import os
import urllib.request

import streamlit as st
import streamlit.components.v1 as components

CITTA, LAT, LON = "Milano", 45.4642, 9.1900

# codice WMO -> (icona, testo)
CODICI = {0: ("☀️", "Sereno"), 1: ("🌤️", "Prevalentemente sereno"), 2: ("⛅", "Parzialmente nuvoloso"), 3: ("☁️", "Coperto"),
          45: ("🌫️", "Nebbia"), 48: ("🌫️", "Nebbia con brina"),
          51: ("🌦️", "Pioggerella"), 53: ("🌦️", "Pioggerella"), 55: ("🌦️", "Pioggerella intensa"),
          56: ("🌧️", "Pioggia gelata"), 57: ("🌧️", "Pioggia gelata"),
          61: ("🌧️", "Pioggia debole"), 63: ("🌧️", "Pioggia"), 65: ("🌧️", "Pioggia forte"),
          66: ("🌧️", "Pioggia gelata"), 67: ("🌧️", "Pioggia gelata"),
          71: ("🌨️", "Neve debole"), 73: ("🌨️", "Neve"), 75: ("❄️", "Neve forte"), 77: ("🌨️", "Nevischio"),
          80: ("🌦️", "Rovesci"), 81: ("🌧️", "Rovesci"), 82: ("⛈️", "Rovesci violenti"),
          85: ("🌨️", "Rovesci di neve"), 86: ("🌨️", "Rovesci di neve"),
          95: ("⛈️", "Temporale"), 96: ("⛈️", "Temporale con grandine"), 99: ("⛈️", "Temporale con grandine")}


def descrizione(codice):
    return CODICI.get(codice, ("🌡️", "Meteo"))


def _config():
    def leggi(k, d):
        v = os.environ.get(k)
        if v is None:
            try:
                v = st.secrets.get(k)
            except Exception:
                v = None
        return d if v in (None, "") else v
    try:
        return str(leggi("METEO_CITTA", CITTA)), float(leggi("METEO_LAT", LAT)), float(leggi("METEO_LON", LON))
    except (TypeError, ValueError):
        return CITTA, LAT, LON


def interpreta(js):
    """Dalla risposta di Open-Meteo ai valori da mostrare (None se incompleta)."""
    try:
        c = js["current"]
        d = js["daily"]
        icona, testo = descrizione(int(c["weather_code"]))
        return {"temp": round(float(c["temperature_2m"])), "icona": icona, "testo": testo,
                "vento": round(float(c["wind_speed_10m"])), "max": round(float(d["temperature_2m_max"][0])),
                "min": round(float(d["temperature_2m_min"][0])),
                "pioggia": int(d.get("precipitation_probability_max", [None])[0] or 0)}
    except (KeyError, IndexError, TypeError, ValueError):
        return None


@st.cache_data(ttl=900, show_spinner=False)
def meteo(lat, lon):
    url = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
           "&current=temperature_2m,weather_code,wind_speed_10m"
           "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
           "&timezone=Europe%%2FRome&forecast_days=1" % (lat, lon))
    try:
        with urllib.request.urlopen(url, timeout=2.5) as r:
            return interpreta(json.loads(r.read().decode("utf-8")))
    except Exception:
        return None


OROLOGIO = """<style>
body{margin:0;font-family:'Inter','Segoe UI',system-ui,sans-serif;text-align:center;color:#0f172a;background:transparent}
#h{font-size:1.9rem;font-weight:800;letter-spacing:.03em;font-variant-numeric:tabular-nums;line-height:1.1;background:linear-gradient(135deg,#0a1640,#2563eb);-webkit-background-clip:text;background-clip:text;color:transparent}
#d{font-size:.78rem;color:#64748b;margin-top:3px;text-transform:capitalize}
</style><div id="h">--:--:--</div><div id="d"></div>
<script>
const tz='Europe/Rome';
const fh=new Intl.DateTimeFormat('it-IT',{timeZone:tz,hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
const fd=new Intl.DateTimeFormat('it-IT',{timeZone:tz,weekday:'long',day:'numeric',month:'long',year:'numeric'});
function t(){const n=new Date();document.getElementById('h').textContent=fh.format(n);document.getElementById('d').textContent=fd.format(n);}
t();setInterval(t,1000);
</script>"""


def render_sidebar():
    """Da chiamare dentro `with st.sidebar:`."""
    if hasattr(st, "iframe"):                       # st.components.v1.html e' deprecato e verra' tolto da Streamlit
        st.iframe(OROLOGIO, height=62)
    else:
        components.html(OROLOGIO, height=62)
    if os.environ.get("PYTEST_CURRENT_TEST"):         # nei test niente rete
        return
    citta, lat, lon = _config()
    m = meteo(lat, lon)
    if not m:
        return
    dati = [("min", f"{m['min']}°"), ("max", f"{m['max']}°"), ("vento", f"{m['vento']} km/h")]
    if m["pioggia"]:
        dati.append(("pioggia", f"{m['pioggia']}%"))
    celle = "".join(f"<div class='mt-c'><span>{k}</span><b>{v}</b></div>" for k, v in dati)
    st.markdown(
        f"<div class='sb-meteo'><div class='mt-top'><span class='mt-ico'>{m['icona']}</span>"
        f"<div><div class='mt-temp'>{m['temp']}°C</div><div class='mt-txt'>{m['testo']}</div></div></div>"
        f"<div class='mt-citta'>📍 {citta}</div><div class='mt-grid'>{celle}</div></div>",
        unsafe_allow_html=True)
