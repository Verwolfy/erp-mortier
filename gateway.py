"""Façade minimaliste vers deux RPC Supabase atomiques.

Ne jamais passer la clé service_role dans le navigateur. Le client injecté doit
porter le JWT du véritable utilisateur Supabase Auth (auth.uid() en PostgreSQL).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from .formulation import ValidationError, decimal_value


class ERPServiceError(RuntimeError):
    """Echec d'une opération côté base, détails sensibles masqués."""


class RpcQuery(Protocol):
    def execute(self) -> Any: ...


class SupabaseLike(Protocol):
    def rpc(self, function_name: str, params: dict[str, Any]) -> RpcQuery: ...


def _code(value: str, label: str, max_len: int = 64) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > max_len:
        raise ValidationError(f'{label}: code invalide')
    if any(ord(c) < 32 for c in value):
        raise ValidationError(f'{label}: caractères interdits')
    return value


def _uuid(value: str | UUID, label: str) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValidationError(f'{label}: UUID invalide') from exc


def _sql_decimal(value: Decimal | str | int, label: str, *, allow_zero: bool = False) -> str:
    d = decimal_value(value, positive=not allow_zero, name=label)
    if allow_zero and d < 0:
        raise ValidationError(f'{label}: négatif interdit')
    if d != d.quantize(Decimal('0.000001')):
        raise ValidationError(f'{label}: maximum 6 décimales')
    return format(d, 'f')


@dataclass(slots=True)
class ERPGateway:
    client: SupabaseLike

    def _call(self, name: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.client.rpc(name, params).execute()
            payload = response.data
        except Exception:
            # Ne jamais recopier l'exception réseau (tokens, URL, informations SQL).
            raise ERPServiceError('Opération non validée par la base. Consulter les journaux serveur.') from None
        if isinstance(payload, list) and len(payload) == 1:
            payload = payload[0]
        if not isinstance(payload, dict) or payload.get('status') != 'ok':
            raise ERPServiceError('Réponse de transaction inattendue; contrôler avant réémission.')
        return payload

    def receive_lot(self, *, company_id: str | UUID, item_code: str, lot_code: str,
                    quantity: Decimal | str | int, unit_cost: Decimal | str | int,
                    operation_id: str | UUID) -> dict[str, Any]:
        """Réception idempotente : réutiliser le même operation_id lors d'un retry."""
        return self._call('erp_receive_lot', {
            'p_company_id': _uuid(company_id, 'entreprise'),
            'p_item_code': _code(item_code, 'article'),
            'p_lot_code': _code(lot_code, 'lot'),
            'p_quantity': _sql_decimal(quantity, 'quantité'),
            'p_unit_cost': _sql_decimal(unit_cost, 'prix unitaire', allow_zero=True),
            'p_operation_id': _uuid(operation_id, 'opération'),
        })

    def close_manufacturing(self, *, company_id: str | UUID, recipe_id: str | UUID,
                             finished_lot: str, output_quantity: Decimal | str | int,
                             operation_id: str | UUID) -> dict[str, Any]:
        """Clôture d'OF : consommation FIFO + PF dans une transaction PostgreSQL."""
        return self._call('erp_manufacture', {
            'p_company_id': _uuid(company_id, 'entreprise'),
            'p_recipe_id': _uuid(recipe_id, 'formulation'),
            'p_finished_lot': _code(finished_lot, 'lot produit fini'),
            'p_output_quantity': _sql_decimal(output_quantity, 'quantité PF'),
            'p_operation_id': _uuid(operation_id, 'opération'),
        })
