from decimal import Decimal
import pytest

from erp_engine.formulation import (
    Component, Formula, ValidationError, calculate_requirements,
    convert_quantity, decimal_value, money,
)


def formula():
    return Formula(Decimal('1000'), 'kg', (
        Component('RESINE', Decimal('300'), 'kg'),
        Component('EAU', Decimal('250'), 'kg'),
        Component('CHARGE', Decimal('450'), 'kg'),
    ))


def test_real_example_500kg():
    q = calculate_requirements(formula(), Decimal('500'), 'kg')
    assert [x.quantity for x in q] == [Decimal('150.000000'), Decimal('125.000000'), Decimal('225.000000')]
    assert sum(x.quantity for x in q) == Decimal('500')


def test_fractional_batch():
    q = calculate_requirements(formula(), Decimal('1250'), 'kg')
    assert [x.quantity for x in q] == [Decimal('375.000000'), Decimal('312.500000'), Decimal('562.500000')]


def test_ones():
    f = Formula(Decimal(1000), 'u', (Component('POT', Decimal(1000), 'u'),))
    assert calculate_requirements(f, Decimal(25), 'u')[0].quantity == 25


def test_no_wrong_units():
    with pytest.raises(ValidationError, match='Unité PF'):
        calculate_requirements(formula(), Decimal('500'), 'L')


@pytest.mark.parametrize('bad', [0, '-2', 'NaN', 'Infinity', '1e20', True, 1.25, None, 'abc'])
def test_quantity_rejected(bad):
    with pytest.raises(ValidationError):
        calculate_requirements(formula(), bad, 'kg')


def test_duplicate_components():
    with pytest.raises(ValidationError, match='en double'):
        Formula(Decimal(1000), 'kg', (
            Component('MP1', Decimal('1'), 'kg'),
            Component('MP1', Decimal('2'), 'kg'),
        ))


def test_bad_component_qty():
    with pytest.raises(ValidationError):
        Component('MP1', Decimal('0'), 'kg')


def test_no_unproved_density():
    with pytest.raises(ValidationError, match='Densité'):
        convert_quantity(Decimal('100'), 'L', 'kg')


def test_density_both_ways():
    assert convert_quantity(Decimal('100'), 'L', 'kg', density_kg_per_l=Decimal('1.4')) == Decimal('140.000000')
    assert convert_quantity(Decimal('140'), 'kg', 'L', density_kg_per_l=Decimal('1.4')) == Decimal('100.000000')


def test_packaging_never_converted_by_assumption():
    with pytest.raises(ValidationError):
        convert_quantity(Decimal('1'), 'u', 'kg', density_kg_per_l=Decimal('1.5'))


def test_rounding_money():
    assert money('10.235') == Decimal('10.24')
    assert money('-10.235') == Decimal('-10.24')


def test_small_positive_component_not_erased():
    f = Formula(Decimal('1000000'), 'kg', (Component('ADDITIF', Decimal('0.001'), 'kg'),))
    with pytest.raises(ValidationError, match='arrondie à zéro'):
        calculate_requirements(f, Decimal('1'), 'kg')


def test_reject_float_even_if_looks_exact():
    with pytest.raises(ValidationError):
        decimal_value(0.1)


def test_bom_immutability():
    f = formula()
    with pytest.raises((AttributeError, TypeError)):
        f.base_quantity = Decimal('2')


def test_formula_rejects_wrong_component_type():
    with pytest.raises(ValidationError):
        Formula(Decimal(1), 'kg', ('non component',))


@pytest.mark.parametrize('recipe_qty,of_qty,expected', [
    ('1000','500','150'), ('1000','1000','300'), ('1000','4000','1200'),
    ('2000','500','75'), ('1','0.5','150'),
])
def test_bom_proportions(recipe_qty, of_qty, expected):
    f = Formula(Decimal(recipe_qty), 'kg', (Component('RESIN', Decimal('300'), 'kg'),))
    assert calculate_requirements(f, Decimal(of_qty), 'kg')[0].quantity == Decimal(expected)
