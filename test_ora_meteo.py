import ora_meteo


def test_interpreta_risposta():
    js = {"current": {"temperature_2m": 17.6, "weather_code": 61, "wind_speed_10m": 9.4},
          "daily": {"temperature_2m_max": [19.2], "temperature_2m_min": [11.1], "precipitation_probability_max": [70]}}
    m = ora_meteo.interpreta(js)
    assert m["temp"] == 18 and m["testo"] == "Pioggia debole" and m["max"] == 19 and m["min"] == 11 and m["pioggia"] == 70


def test_risposta_incompleta():
    assert ora_meteo.interpreta({}) is None
    assert ora_meteo.descrizione(999)[1] == "Meteo"
