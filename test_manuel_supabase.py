"""Test MANUEL sur un projet Supabase de TEST, jamais sur la production.

Pré-requis : migration SQL appliquée, données exemple et adhésion Auth créées.
Exécuter depuis la racine du dépôt avec PYTHONPATH=erp_hardening.
Aucune clé ni mot de passe n'est écrit sur disque.
"""
from __future__ import annotations

from decimal import Decimal
from getpass import getpass
from uuid import UUID, uuid4

from supabase import create_client
from erp_engine.gateway import ERPGateway

COMPANY_ID = UUID('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa')
RECIPE_ID = UUID('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb')


def main() -> None:
    print('ATTENTION : utiliser exclusivement un projet Supabase DE TEST.')
    url = input('URL Supabase de test (https://...supabase.co) : ').strip()
    key = input('Clé publishable (sb_publishable_...) : ').strip()
    email = input('Email utilisateur Supabase Auth de test : ').strip()
    password = getpass('Mot de passe utilisateur de test : ')
    if not url.startswith('https://') or not key or not email or not password:
        raise ValueError('Informations de test manquantes ou URL invalide')

    client = create_client(url, key)
    try:
        auth_result = client.auth.sign_in_with_password({'email': email, 'password': password})
        if not auth_result.user:
            raise RuntimeError('Utilisateur Supabase Auth absent')
        service = ERPGateway(client)
        run_id = uuid4().hex[:12]

        resin_op = uuid4()
        resin_lot = f'ESSAI-RES-{run_id}'
        first = service.receive_lot(
            company_id=COMPANY_ID, item_code='RESINE', lot_code=resin_lot,
            quantity=Decimal('300'), unit_cost=Decimal('2'), operation_id=resin_op,
        )
        again = service.receive_lot(
            company_id=COMPANY_ID, item_code='RESINE', lot_code=resin_lot,
            quantity=Decimal('300'), unit_cost=Decimal('2'), operation_id=resin_op,
        )
        assert first == again, 'Reprise réseau non idempotente'
        print('OK : réception résine et rejeu idempotent', first['lot_id'])

        filler = service.receive_lot(
            company_id=COMPANY_ID, item_code='CHARGE', lot_code=f'ESSAI-CH-{run_id}',
            quantity=Decimal('700'), unit_cost=Decimal('1'), operation_id=uuid4(),
        )
        print('OK : réception charge', filler['lot_id'])

        produced = service.close_manufacturing(
            company_id=COMPANY_ID, recipe_id=RECIPE_ID,
            finished_lot=f'ESSAI-PF-{run_id}', output_quantity=Decimal('500'),
            operation_id=uuid4(),
        )
        assert Decimal(str(produced['output_quantity'])) == Decimal('500')
        assert Decimal(str(produced['total_material_cost'])) == Decimal('650')
        print('OK : 500 kg fabriqués ; coût matières :', produced['total_material_cost'])
        print('Lots consommés :', produced['consumed_lots'])
        print('Test manuel réussi. Contrôler aussi les mouvements en SQL Editor.')
    finally:
        try:
            client.auth.sign_out()
        except Exception:
            pass


if __name__ == '__main__':
    main()
