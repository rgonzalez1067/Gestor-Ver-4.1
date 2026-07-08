"""Seed test quotes for iter248: GATEWAY, LINK_PAGO, VPOS in Pagada state."""
import asyncio
import os
import uuid
import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')


async def main():
    client = AsyncIOMotorClient(os.environ['MONGO_URL'])
    db = client[os.environ['DB_NAME']]

    cl = await db.clients.find_one({}, {'_id': 0})
    print('client:', cl.get('client_id'), cl.get('name') or cl.get('company_name'))
    client_id = cl['client_id']
    client_name = cl.get('name') or cl.get('company_name') or 'TEST CLIENT'

    admin = await db.users.find_one({'email': 'rgonzalez@megasoft.com.ve'}, {'_id': 0})
    creator_id = admin['user_id']

    now = datetime.datetime.utcnow().isoformat() + 'Z'

    base = {
        'client_id': client_id,
        'client_name': client_name,
        'quote_category': 'implementation',
        'pricing_model': 'conventional',
        'services': [],
        'hardware': [],
        'equipment_items': [],
        'ft_equipment_items': [],
        'subtotal_usd': 1000.0,
        'total_usd': 1160.0,
        'exchange_rate': 40.0,
        'total_bs': 46400.0,
        'notes': '',
        'quote_status': 'Pagada',
        'sede': 'PYME',
        'client_segment': 'PYME',
        'created_by_user_id': creator_id,
        'creator_name': 'Rafael González',
        'creator_initials': 'RG',
        'creator_departamento': 'Ventas Pyme',
        'creator_cargo': 'Gerente',
        'sent_to_client_at': now,
        'approved_at': now,
        'invoiced_at': now,
        'paid_at': now,
        'attachments': [],
        'branch_details': [],
        'version': 1,
        'created_at': now,
        'quote_pdf_url': '',
    }

    q_gateway = dict(base, **{
        'quote_id': 'quo_TESTITER248_GW_' + uuid.uuid4().hex[:6],
        'quote_number': 'COT-TEST-ITER248-GW-001',
        'quote_type': 'GATEWAY',
        'pg_setup_items': [{'concepto': 'Setup PG', 'costo': 1000}],
        'pg_recurring_cost': {'monto': 100},
    })
    q_link = dict(base, **{
        'quote_id': 'quo_TESTITER248_LP_' + uuid.uuid4().hex[:6],
        'quote_number': 'COT-TEST-ITER248-LP-001',
        'quote_type': 'LINK_PAGO',
        'link_pago_variant': 'link_pago',
        'pg_setup_items': [{'concepto': 'Setup LP', 'costo': 1000}],
    })
    q_vpos = dict(base, **{
        'quote_id': 'quo_TESTITER248_VPOS_' + uuid.uuid4().hex[:6],
        'quote_number': 'COT-TEST-ITER248-VPOS-001',
        'quote_type': 'VPOS',
        'cantidad_cajas': 1,
        'cantidad_bancos': 1,
        'branch_details': [{'store_name': 'Sucursal 1', 'quantity': 1}],
    })

    for q in [q_gateway, q_link, q_vpos]:
        await db.quotes.replace_one({'quote_number': q['quote_number']}, q, upsert=True)
        print('upserted:', q['quote_id'], q['quote_number'], q['quote_type'], q['quote_status'])

    print('DONE')


if __name__ == '__main__':
    asyncio.run(main())
