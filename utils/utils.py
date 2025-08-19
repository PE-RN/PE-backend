import unicodedata
import re

class Utils:
  def __init__(self):
        pass
  
  def format_layer_name(self, name: str) -> str:
    # Normaliza para remover acentos
    nfkd_form = unicodedata.normalize("NFKD", name)
    without_accents = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    
    # Substitui espaços por "_"
    formatted = without_accents.replace(" ", "_")
    
    # Remove qualquer caractere não alfanumérico ou "_"
    formatted = re.sub(r"[^a-zA-Z0-9_]", "", formatted)
    
    return formatted