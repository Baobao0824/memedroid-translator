from pathlib import Path
import yaml
from functions.config_dict import ConfigDict

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"

with CONFIG_PATH.open("r", encoding="utf-8") as f:
    CONFIG: ConfigDict = yaml.safe_load(f)