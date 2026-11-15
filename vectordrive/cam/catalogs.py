"""Catalogues d'outils en ligne : fabricants, revendeurs et plateformes.

VectorDrive n'embarque **aucune donnée** des catalogues (elles
appartiennent aux fabricants) : il ouvre leur site, y cherche une
référence, et importe les fichiers que l'utilisateur en télécharge
(`cam.toollib` : GTC / ISO 13399, DIN 4000, CSV, STEP).

`search_url(vendor, ref)` : la page de recherche du fabricant quand on la
connaît, sinon une recherche « marque + référence » sur le web.
"""
from __future__ import annotations

import urllib.parse
from dataclasses import dataclass


@dataclass(frozen=True)
class Vendor:
    key: str
    name: str
    kind: str                 # fabricant, revendeur, plateforme
    country: str
    site: str = ''            # page d'accueil (vide : pas sûre, on cherche)
    search: str = ''          # modèle de recherche directe, {ref} = référence
    formats: str = ''         # données proposées au téléchargement
    note: str = ''


WEB_SEARCH = 'https://duckduckgo.com/?q={q}'

VENDORS = [
    Vendor('datron', 'DATRON', 'fabricant', 'DE', 'https://www.datron.com',
           'https://webshop.datron.de/search?search={ref}', 'fiches produit, STEP',
           'fraises de gravure et micro-usinage'),
    Vendor('sandvik', 'Sandvik Coromant', 'fabricant', 'SE', 'https://www.sandvik.coromant.com', '',
           'GTC (ISO 13399), STEP, DXF'),
    Vendor('kennametal', 'Kennametal', 'fabricant', 'US', 'https://www.kennametal.com', '', 'GTC (ISO 13399), STEP'),
    Vendor('walter', 'Walter', 'fabricant', 'DE', 'https://www.walter-tools.com', '', 'GTC (ISO 13399), STEP'),
    Vendor('iscar', 'ISCAR', 'fabricant', 'IL', 'https://www.iscar.com', '', 'GTC (ISO 13399), STEP'),
    Vendor('seco', 'Seco Tools', 'fabricant', 'SE', 'https://www.secotools.com', '', 'GTC (ISO 13399), STEP'),
    Vendor('mitsubishi', 'Mitsubishi Materials', 'fabricant', 'JP', 'https://www.mmc-carbide.com', '',
           'GTC (ISO 13399), STEP'),
    Vendor('guhring', 'Gühring', 'fabricant', 'DE', 'https://www.guehring.com', '', 'DIN 4000, STEP'),
    Vendor('emuge', 'EMUGE-FRANKEN', 'fabricant', 'DE', 'https://www.emuge-franken.de', '', 'DIN 4000, STEP',
           'taraudage, fraisage'),
    Vendor('osg', 'OSG', 'fabricant', 'JP', '', '', 'STEP'),
    Vendor('yg1', 'YG-1', 'fabricant', 'KR', '', '', 'STEP', 'fraises carbure'),
    Vendor('dormerpramet', 'Dormer Pramet', 'fabricant', 'GB/CZ', 'https://www.dormerpramet.com', '',
           'GTC (ISO 13399), STEP'),
    Vendor('mapal', 'MAPAL', 'fabricant', 'DE', 'https://www.mapal.com', '', 'GTC (ISO 13399), STEP'),
    Vendor('ceratizit', 'CERATIZIT', 'fabricant', 'LU', 'https://www.ceratizit.com', '', 'GTC (ISO 13399), STEP'),
    Vendor('fraisa', 'FRAISA', 'fabricant', 'CH', 'https://www.fraisa.com', '', 'DIN 4000, STEP'),
    Vendor('kyocera_sgs', 'KYOCERA SGS', 'fabricant', 'US', 'https://www.kyocera-sgstool.com', '', 'STEP'),
    Vendor('harvey', 'Harvey Tool', 'fabricant', 'US', 'https://www.harveytool.com', '', 'STEP, DXF',
           'micro-outils, gravure'),
    Vendor('zecha', 'ZECHA', 'fabricant', 'DE', 'https://www.zecha.de', '', 'STEP', 'micro-outils, gravure'),
    Vendor('mikron', 'Mikron Tool', 'fabricant', 'CH', 'https://www.mikrontool.com', '', 'STEP'),
    Vendor('magafor', 'Magafor', 'fabricant', 'FR', 'https://www.magafor.com', '', 'STEP', 'forets, alésoirs'),
    Vendor('gravotech', 'Gravotech (outils de gravure)', 'fabricant', 'FR', 'https://www.gravotech.com', '', '',
           'pointes et fraises de gravure'),
    Vendor('onsrud', 'Onsrud', 'fabricant', 'US', 'https://www.onsrud.com', '', 'STEP', 'bois, plastiques'),
    Vendor('amana', 'Amana Tool', 'fabricant', 'US', 'https://www.amanatool.com', '', '', 'bois, plastiques'),
    Vendor('hoffmann', 'Hoffmann Group (GARANT)', 'revendeur', 'DE', 'https://www.hoffmann-group.com', '',
           'DIN 4000, STEP'),
    Vendor('toolsunited', 'ToolsUnited', 'plateforme', 'DE', 'https://www.toolsunited.com', '',
           'DIN 4000, ISO 13399, STEP', 'données de nombreux fabricants'),
    Vendor('machiningcloud', 'MachiningCloud', 'plateforme', 'US', 'https://www.machiningcloud.com', '',
           'ISO 13399, STEP', 'données de nombreux fabricants'),
]
BY_KEY = {v.key: v for v in VENDORS}


def vendor(name_or_key: str) -> Vendor | None:
    """Fabricant d'après sa clé ou son nom (« Datron », « DATRON », « datron »)."""
    k = (name_or_key or '').strip().lower()
    return BY_KEY.get(k) or next((v for v in VENDORS if v.name.lower() == k or v.name.lower().startswith(k)
                                  and k), None)


def search_url(v: Vendor, ref: str = '') -> str:
    """Page où trouver la référence `ref` chez ce fabricant (ou son site)."""
    ref = (ref or '').strip()
    if ref and v.search:
        return v.search.format(ref=urllib.parse.quote(ref))
    if not ref and v.site:
        return v.site
    q = f'{v.name} {ref}'.strip()
    if v.site:
        q += ' site:' + urllib.parse.urlparse(v.site).netloc.removeprefix('www.')
    return WEB_SEARCH.format(q=urllib.parse.quote_plus(q))
