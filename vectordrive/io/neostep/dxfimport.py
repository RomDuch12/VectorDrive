"""Sous-ensemble de NeoDrive `vecteur/dxfimport` utilisé par le lecteur STEP
(Cancelled, ImportReport). Code de l'auteur, repris tel quel."""
from __future__ import annotations

UNIT_CHOICES = (('millimètre', 1.0), ('centimètre', 10.0),
                ('mètre', 1000.0), ('pouce', 25.4))


class Cancelled(RuntimeError):
    """L'opérateur a interrompu la lecture en cours.

    Distinct de `DxfError` : rien n'a échoué, on a simplement arrêté. Le
    dire par une exception plutôt que par un retour vide évite d'avoir à
    tester le résultat à chaque étage — et évite surtout d'annoncer
    « fichier illisible » à qui vient de presser *Annuler*.
    """


#: Libellés des unités, pour l'interface.
UNIT_CHOICES = (('millimètre', 1.0), ('centimètre', 10.0),
                ('mètre', 1000.0), ('pouce', 25.4))


class ImportReport:
    """Ce qui a été lu, et ce qui ne l'a pas été."""

    def __init__(self) -> None:
        self.units_mm: float = 1.0
        self.declared_units_mm: float = 1.0
        self.units_overridden: bool = False
        self.layers: dict[str, int] = {}
        self.skipped_text: int = 0
        self.skipped_other: dict[str, int] = {}
        #: Remarques sur la lecture — une cote suspecte, une convention
        #: d'origine qui ne se voit pas dans la géométrie.
        self.notes: list[str] = []
        #: Texte rendu avec une police de substitution plutôt que la
        #: police déclarée : {nom déclaré: nombre d'entités}.
        self.font_substitutions: dict[str, int] = {}
        self.polylines: int = 0
        self.extent: tuple[float, float, float, float] | None = None

    def size_mm(self) -> tuple[float, float]:
        if not self.extent:
            return (0.0, 0.0)
        x1, y1, x2, y2 = self.extent
        return (x2 - x1, y2 - y1)

    def fits(self, field_w: float, field_h: float) -> bool:
        w, h = self.size_mm()
        return w <= field_w and h <= field_h

    def unit_warning(self, field_w: float, field_h: float) -> str:
        """Message si la taille obtenue est manifestement invraisemblable.

        L'en-tête `$INSUNITS` d'un DXF est souvent faux : un fichier tracé
        en millimètres peut se déclarer en mètres. Plutôt que de deviner en
        silence, on signale l'incohérence et on laisse choisir.
        """
        w, h = self.size_mm()
        if self.fits(field_w, field_h):
            return ''
        ratio = max(w / field_w if field_w else 0, h / field_h if field_h else 0)
        message = (f'La géométrie mesure {w:.1f} × {h:.1f} mm, soit '
                   f'{ratio:.0f} fois le champ de marquage '
                   f'({field_w:g} × {field_h:g} mm).')
        for label, factor in UNIT_CHOICES:
            if factor >= self.units_mm:
                continue
            alt_w, alt_h = w * factor / self.units_mm, h * factor / self.units_mm
            if alt_w <= field_w and alt_h <= field_h:
                message += (f'\n\nEn lisant le fichier en {label}s, elle ferait '
                            f'{alt_w:.1f} × {alt_h:.1f} mm — ce qui tiendrait '
                            f'dans le champ.')
                break
        return message

    def summary(self) -> str:
        parts = [f'{self.polylines} polyligne(s)',
                 f'{len(self.layers)} calque(s)']
        if self.extent:
            x1, y1, x2, y2 = self.extent
            parts.append(f'{x2 - x1:.1f} × {y2 - y1:.1f} mm')
        if self.skipped_text:
            parts.append(f'{self.skipped_text} texte(s) ignoré(s)')
        if self.skipped_other:
            total = sum(self.skipped_other.values())
            kinds = ', '.join(sorted(self.skipped_other))
            parts.append(f'{total} entité(s) non gérée(s) : {kinds}')
        if self.font_substitutions:
            total_sub = sum(self.font_substitutions.values())
            noms = ', '.join(sorted(self.font_substitutions))
            parts.append(f'{total_sub} texte(s) avec une police de '
                         f'substitution ({noms})')
        parts.extend(self.notes)
        return ' · '.join(parts)

