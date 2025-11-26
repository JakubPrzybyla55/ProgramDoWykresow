from dataclasses import dataclass, field
import pandas as pd
from typing import List, Tuple, Dict, Any, Optional

@dataclass
class AppState:
    """Klasa przechowująca stan aplikacji."""
    # Ścieżki i dane
    base_data_path: str = 'data'
    profiles: List[str] = field(default_factory=list)
    selected_profile: Optional[str] = None
    plan_file_path: Optional[str] = None
    roast_files_paths: List[str] = field(default_factory=list)
    selected_roast_path: Optional[str] = None
    plan_df: Optional[pd.DataFrame] = None

    # Ustawienia widoczności
    show_plan: bool = True
    show_ibts: bool = True
    show_probe: bool = True

    # Ustawienia wykresów
    ror_y_lim: Tuple[int, int] = (-5, 35)
    settings_y_lim: Tuple[int, int] = (0, 9)

    # Ustawienia RoR IBTS
    ror_method_ibts: str = 'Średnia Ruchoma'
    ibts_params: Dict[str, Any] = field(default_factory=lambda: {'window_sec': 15})

    # Ustawienia RoR Sonda
    ror_method_probe: str = 'Średnia Ruchoma'
    probe_params: Dict[str, Any] = field(default_factory=lambda: {'window_sec': 15})

    # Ustawienia Dawki Termicznej
    dose_t_base: float = 100.0
    dose_start_time: float = 5.0

    # Analiza teoretyczna
    poly_degree: int = 3
