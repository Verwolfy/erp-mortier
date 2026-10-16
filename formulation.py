"""Calcul pur de nomenclature avec unités explicites et décimales exactes.

Les recettes sont définies POUR une quantité de base de produit fini.
Aucune conversion kg<->L n'est implicite : une densité documentée est obligatoire.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from typing import Literal

Unit = Literal['kg', 'L', 'u']
QUANTITY_SCALE = Decimal('0.000001')
MONEY_SCALE = Decimal('0.01')
VALID_UNITS = frozenset({'kg', 'L', 'u'})
MAX_QTY = Decimal('1000000000000')


class ValidationError(ValueError):
    """Donnée métier invalide : bloquer l'opération avant l'écriture SQL."""


def decimal_value(value: str | int | Decimal, *, positive: bool = False,
                  name: str = 'valeur') -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValidationError(f'{name}: utilisez Decimal ou chaîne, pas float/bool')
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(f'{name}: nombre invalide') from exc
    if not result.is_finite() or abs(result) > MAX_QTY:
        raise ValidationError(f'{name}: nombre hors limites')
    if positive and result <= 0:
        raise ValidationError(f'{name}: valeur strictement positive requise')
    return result


def validate_unit(unit: str) -> str:
    if unit not in VALID_UNITS:
        raise ValidationError(f'Unité non supportée: {unit!r}')
    return unit


@dataclass(frozen=True, slots=True)
class Component:
    sku: str
    quantity: Decimal
    unit: Unit

    def __post_init__(self) -> None:
        if not isinstance(self.sku, str) or not self.sku.strip() or len(self.sku) > 64:
            raise ValidationError('Code matière invalide')
        validate_unit(self.unit)
        object.__setattr__(self, 'quantity', decimal_value(self.quantity, positive=True,
                                                           name='quantité matière'))


@dataclass(frozen=True, slots=True)
class Formula:
    base_quantity: Decimal
    base_unit: Unit
    components: tuple[Component, ...]

    def __post_init__(self) -> None:
        validate_unit(self.base_unit)
        object.__setattr__(self, 'base_quantity', decimal_value(
            self.base_quantity, positive=True, name='quantité de référence'))
        if not self.components or not isinstance(self.components, tuple):
            raise ValidationError('Recette sans matières ou composantes non immuables')
        if not all(isinstance(c, Component) for c in self.components):
            raise ValidationError('Composant de recette invalide')
        if len({c.sku for c in self.components}) != len(self.components):
            raise ValidationError('La recette contient un code matière en double')


@dataclass(frozen=True, slots=True)
class Requirement:
    sku: str
    quantity: Decimal
    unit: Unit


def calculate_requirements(formula: Formula, output_quantity: Decimal,
                           output_unit: Unit) -> tuple[Requirement, ...]:
    """Calcule la consommation théorique, sans accès SQL ni effet de bord.

    Quantités arrondies au microunité (6 décimales), ROUND_HALF_UP.
    Une quantité positive trop petite pour être représentée est refusée.
    """
    validate_unit(output_unit)
    if output_unit != formula.base_unit:
        raise ValidationError('Unité PF incompatible avec unité de la recette')
    q = decimal_value(output_quantity, positive=True, name='quantité OF')
    results: list[Requirement] = []
    with localcontext() as ctx:
        ctx.prec = 40
        for component in formula.components:
            exact = component.quantity * q / formula.base_quantity
            if exact > MAX_QTY:
                raise ValidationError('Consommation hors limites')
            rounded = exact.quantize(QUANTITY_SCALE, rounding=ROUND_HALF_UP)
            if rounded <= 0:
                raise ValidationError(f'Quantité arrondie à zéro pour {component.sku}')
            results.append(Requirement(component.sku, rounded, component.unit))
    return tuple(results)


def convert_quantity(quantity: Decimal, from_unit: Unit, to_unit: Unit,
                     *, density_kg_per_l: Decimal | None = None) -> Decimal:
    """Convertit la masse et le volume à l'aide de la densité réelle du lot.

    La conversion d'une unité de conditionnement 'u' nécessite une BOM
    explicite et n'est jamais supposée égale à 1 kg ou 1 litre.
    """
    validate_unit(from_unit)
    validate_unit(to_unit)
    q = decimal_value(quantity, positive=True, name='quantité')
    if from_unit == to_unit:
        return q
    if 'u' in {from_unit, to_unit}:
        raise ValidationError("L'unité 'u' exige une nomenclature de conditionnement")
    if density_kg_per_l is None:
        raise ValidationError('Densité kg/L manquante')
    rho = decimal_value(density_kg_per_l, positive=True, name='densité')
    with localcontext() as ctx:
        ctx.prec = 40
        converted = q * rho if from_unit == 'L' else q / rho
        if converted > MAX_QTY:
            raise ValidationError('Conversion hors limites')
        result = converted.quantize(QUANTITY_SCALE, rounding=ROUND_HALF_UP)
    if result <= 0:
        raise ValidationError('Conversion arrondie à zéro')
    return result


def money(value: str | int | Decimal) -> Decimal:
    result = decimal_value(value, name='montant')
    return result.quantize(MONEY_SCALE, rounding=ROUND_HALF_UP)
