# Analizator Wypału Kawy

Aplikacja do analizy profili wypału kawy, porównująca zaplanowany profil z rzeczywistymi danymi z RoastTime (lub kompatybilnymi).

## Funkcje

*   Wizualizacja profilu temperatury (Plan vs Rzeczywistość).
*   Wizualizacja szybkości wzrostu (RoR) z opcją wygładzania (Średnia Ruchoma lub Savitzky-Golay).
*   Obsługa danych z sensora IBTS oraz sondy ziarna (Probe).
*   Analiza faz wypału (Start, Turning Point, Yellowing, 1st Crack, Drop).
*   Wizualizacja ustawień Nawiewu (Fan) i Mocy (Power).
*   Automatyczne generowanie raportu porównawczego i metryk RoR.

## Wymagania

*   Python 3.8+
*   Biblioteki (zainstaluj przez `pip install -r requirements.txt`):
    *   streamlit
    *   pandas
    *   plotly
    *   scipy (opcjonalnie, do zaawansowanego wygładzania RoR)

## Uruchomienie

1.  Upewnij się, że masz zainstalowane wymagane biblioteki.
2.  Uruchom aplikację komendą:
    ```bash
    streamlit run app.py
    ```
3.  Otwórz przeglądarkę pod adresem wskazanym w terminalu (zazwyczaj `http://localhost:8501`).

## Struktura Danych

Aplikacja oczekuje określonej struktury katalogów w folderze `data/`:

```
data/
├── NazwaProfilu1/
│   ├── Plan/
│   │   └── plan.csv
│   └── Wypaly/
│       ├── roast_01.csv
│       └── roast_02.csv
└── NazwaProfilu2/
    ...
```

### Format Plików

#### 1. Plik Planu (`plan.csv`)
Plik CSV definiujący docelowy profil. Wymagane kolumny (kolejność dowolna, nazwy case-insensitive):
*   `Faza`: Nazwa punktu kontrolnego (np. Start, Yellowing, 1st Crack).
*   `Czas`: Czas zdarzenia w formacie `mm:ss` (np. 1:30, 8:00).
*   `Temperatura`: Oczekiwana temperatura w °C.
*   `Nawiew` (Opcjonalnie): Ustawienie nawiewu (np. 50, F4).
*   `Moc` (Opcjonalnie): Ustawienie mocy (np. 80, P6).

Przykład:
```csv
Faza,Czas,Temperatura,Nawiew,Moc
Start,0:00,200,50,80
Turning Point,1:30,100,60,70
Yellowing,5:00,150,70,60
1st Crack,8:00,200,80,50
Drop,10:00,215,90,40
```

#### 2. Plik Wypału (`roast.csv`)
Plik eksportowany z oprogramowania RoastTime (lub w formacie kompatybilnym).
Aplikacja szuka sekcji `Timeline` oraz następujących kolumn (nazwy mogą się nieznacznie różnić):
*   `Time`: Czas.
*   `IBTS Temp`: Temperatura z czujnika podczerwieni.
*   `IBTS ROR`: RoR z czujnika podczerwieni.
*   `Bean Probe Temp` (Opcjonalnie): Temperatura z sondy.
*   `Bean Probe ROR` (Opcjonalnie): RoR z sondy.
*   `Fan` (Opcjonalnie): Wartość nawiewu.
*   `Power` (Opcjonalnie): Wartość mocy.

Przykład nagłówka:
```csv
Timeline
Time, IBTS Temp, IBTS ROR, Bean Probe Temp, Bean Probe ROR, Fan, Power
0:00, 200, 0, 200, 0, 50, 80
...
```

## Obsługa

1.  Wybierz **Profil Kawy** z panelu bocznego (folder w `data/`).
2.  Wybierz konkretny plik **Wypału** z listy.
3.  Dostosuj ustawienia wykresów (metoda RoR, zakresy osi) w panelu bocznym.
4.  Analizuj wykresy oraz tabele z metrykami poniżej.
