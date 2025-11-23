# Coffee Roast Analyzer

Aplikacja do analizy i porównywania profili palenia kawy. Pozwala na zestawienie planowanego profilu (Profile Plan) z rzeczywistymi danymi z palenia (RoastTime Empirical Data).

## Funkcjonalności

- **Wizualizacja Krzywej Temperatury:** Porównanie planu z rzeczywistym przebiegiem temperatury (IBTS).
- **Analiza RoR (Rate of Rise):**
  - Wykres RoR z pliku (RoastTime).
  - Obliczony i wygładzony RoR na podstawie temperatury (okno 10s, wygładzanie 15s).
- **Metryki Faz:**
  - Tabela porównawcza planowanych vs rzeczywistych czasów i temperatur dla kluczowych momentów (Yellowing, 1st Crack itp.).
  - Analiza zmian RoR w poszczególnych fazach (np. spadek RoR w fazie Maillarda).

## Instalacja

Upewnij się, że masz zainstalowanego Pythona. Następnie zainstaluj wymagane biblioteki:

```bash
pip install -r requirements.txt
```

## Uruchomienie

Aby uruchomić aplikację, wpisz w terminalu:

```bash
streamlit run app.py
```

Aplikacja otworzy się automatycznie w Twojej domyślnej przeglądarce internetowej.

## Format Danych

### 1. Profil Palenia (Plan) - CSV
Plik powinien zawierać kolumny: `Faza`, `Czas`, `Temperatura`.
Przykład:
```csv
Faza, Czas, Temperatura
Preheat, 0:00, 220
Turning Point, 1:30, 90
Yellowing End, 5:00, 160
1st Crack, 9:00, 200
Drop, 11:00, 215
```

### 2. Dane Empiryczne (RoastTime) - CSV
Program obsługuje pliki eksportowane z **RoastTime**.
Musi zawierać sekcję `Timeline` z kolumnami takimi jak:
- `Time` (format mm:ss)
- `IBTS Temp`
- `IBTS ROR`
- Oraz metadane zdarzeń (np. `Yellowing`, `1st Crack`) w nagłówku pliku.
